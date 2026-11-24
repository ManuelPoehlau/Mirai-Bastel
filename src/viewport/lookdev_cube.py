"""The studio's environment cube (AD-039 §8, LookDev P3 S5): the analytic studio (`lookdev_optics.Studio`, D-L4: no
HDRI files) prefiltered on the GPU into a 128² RGBA16F cube with mips down to 2²; the skin pass reads its reflection
from it (`lookdev_shaders.LD_CUBE_SRC`, unit 8) instead of evaluating `ld_studio` per pixel. SH9 stays the diffuse
environment, and the eye stays on the analytic studio (§8).

- **Content and prefilter** (`lookdev_shaders.CUBE_PREFILTER_SRC`, `PROVISIONAL` fixed setting): level 0 is
  `ld_studio(d, 0)`, level L the GGX importance-sampled prefilter of it at roughness L / (levels - 1), 64 samples, the
  corner fix (AD-039 C7). Twins: `lookdev_optics.cube_texel_directions` / `prefilter_ggx`.
- **When** (`update(studio)`): only when the studio's *content* changes - the SH9 cache key (`Studio` is hashable,
  V21). Rotation and intensity stay uniforms (`u_ld_env_rot`, `u_ld_env_intensity`). `prefilters` counts the builds.
- **The copy (AD-039 §11.1 run 4 / 5):** on the reference PC's card a cube *rendered* through an FBO samples once and
  then fails every later draw (GL_OUT_OF_MEMORY); a cube *uploaded* from the CPU always works. So the prefilter renders
  into a scratch cube, the chain is read back (`glGetTexImage`, RGBA float) and uploaded into a fresh cube, the one the
  skin samples; the scratch cube and its FBO are deleted (the measured case M, every time). This is a workaround for an
  observed driver defect, applied on every card (features are checked by function, never by GPU name, AD-039 §2.2).
  Reference PC: 12 ms prefilter + 17-24 ms copy, once per studio content change - one frame's hitch, behind the room's
  status line (`Application._set_lookdev_studio_state`).
- **GL:** the prefilter runs inside the LookDev frame (or the room's preparation) through its own FBO and saves /
  restores what `KeyShadow._render` does (draw / read framebuffer, viewport, program, vertex array, depth / blend / cull
  / scissor / polygon offset, depth mask) plus the active unit and its cube binding. No FBO stays bound.
  `GL_TEXTURE_CUBE_MAP_SEAMLESS` is the pass's business: on only around a skin draw that samples the cube.

Owned by `LookdevPass` (created on the first LookDev frame with the effect on, deleted in its `release()`); nothing here
exists with `shading == "worklight"` (G4).
"""

from __future__ import annotations

import time

from . import lookdev_optics as lo
from .lookdev_shaders import CUBE_LEVELS, CUBE_SAMPLES, CUBE_SIZE, CUBE_UNIT, cube_prefilter_sources

_CUBE_PARAMETERS = None  # (name, value) pairs, built on first use (pyglet's gl is imported lazily)


def _cube_parameters(gl) -> tuple:
    global _CUBE_PARAMETERS
    if _CUBE_PARAMETERS is None:
        _CUBE_PARAMETERS = ((gl.GL_TEXTURE_BASE_LEVEL, 0), (gl.GL_TEXTURE_MAX_LEVEL, CUBE_LEVELS - 1),
                            (gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR),
                            (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE),
                            (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE))
    return _CUBE_PARAMETERS


class EnvCube:
    def __init__(self, size: int = CUBE_SIZE, levels: int = CUBE_LEVELS, samples: int = CUBE_SAMPLES) -> None:
        if size >> (levels - 1) < 1:
            raise ValueError("levels: the smallest level needs at least 1 texel")
        self.size = int(size)
        self.levels = int(levels)
        self.samples = int(samples)
        #: Test hook / probe: how many prefilters ran (a studio content change: +1; rotation / intensity: +0).
        self.prefilters = 0
        #: The last build's wall time (prefilter + read-back + upload), ms - the probe's row.
        self.last_ms = 0.0
        self._texture = 0  # the sampled cube (uploaded from the CPU)
        self._studio = None
        self._program = None
        self._vao = 0

    @property
    def ready(self) -> bool:
        return bool(self._texture) and self._studio is not None

    def holds(self, studio) -> bool:
        """The cube shows `studio`'s content (no prefilter needed for it)."""
        return self.ready and self._studio == studio

    # -- the build ---------------------------------------------------------------------------------------------------

    def update(self, studio) -> bool:
        """Prefilter `studio` (a `lookdev_optics.Studio`) into the sampled cube if its content changed. True = built."""
        if self.holds(studio):
            return False
        import ctypes

        import numpy as np
        from pyglet import gl
        from pyglet.graphics.shader import Shader, ShaderProgram

        from .lookdev_pass import set_uniforms

        start = time.perf_counter()
        if self._program is None:
            self._program = ShaderProgram(*(Shader(src, kind) for src, kind in cube_prefilter_sources()))
            vao = gl.GLuint()
            gl.glGenVertexArrays(1, ctypes.byref(vao))
            self._vao = vao.value

        def geti(name, count=1):
            buf = (gl.GLint * count)()
            gl.glGetIntegerv(name, buf)
            return buf[0] if count == 1 else tuple(buf)

        saved = {"draw_fbo": geti(gl.GL_DRAW_FRAMEBUFFER_BINDING), "read_fbo": geti(gl.GL_READ_FRAMEBUFFER_BINDING),
                 "viewport": geti(gl.GL_VIEWPORT, 4), "program": geti(gl.GL_CURRENT_PROGRAM),
                 "vao": geti(gl.GL_VERTEX_ARRAY_BINDING), "depth_mask": geti(gl.GL_DEPTH_WRITEMASK),
                 "active": geti(gl.GL_ACTIVE_TEXTURE)}
        flags = {cap: bool(gl.glIsEnabled(cap)) for cap in (gl.GL_SCISSOR_TEST, gl.GL_DEPTH_TEST, gl.GL_BLEND,
                                                            gl.GL_CULL_FACE, gl.GL_POLYGON_OFFSET_FILL)}
        gl.glActiveTexture(gl.GL_TEXTURE0 + CUBE_UNIT)
        saved["cube"] = geti(gl.GL_TEXTURE_BINDING_CUBE_MAP)
        scratch, fbo, copy = gl.GLuint(), gl.GLuint(), gl.GLuint()
        try:
            # the scratch cube the prefilter renders into
            gl.glGenTextures(1, ctypes.byref(scratch))
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, scratch.value)
            for level in range(self.levels):
                side = self.size >> level
                for face in range(6):
                    gl.glTexImage2D(gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, level, gl.GL_RGBA16F, side, side, 0,
                                    gl.GL_RGBA, gl.GL_FLOAT, None)
            for name, value in _cube_parameters(gl):
                gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, name, value)
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
            gl.glGenFramebuffers(1, ctypes.byref(fbo))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo.value)
            for cap in flags:
                gl.glDisable(cap)
            gl.glDepthMask(gl.GL_FALSE)
            program = self._program
            program.use()
            set_uniforms(program, lo.studio_uniforms(studio))
            gl.glBindVertexArray(self._vao)
            for level in range(self.levels):
                side = self.size >> level
                gl.glViewport(0, 0, side, side)
                program["u_size"] = float(side)
                program["u_roughness"] = lo.cube_level_roughness(level) if self.levels > 1 else 0.0
                program["u_samples"] = 1 if level == 0 else self.samples
                for face in range(6):
                    gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                              gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, scratch.value, level)
                    program["u_face"] = face
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            # AD-039 §11.1 run 4 / 5: sample a CPU copy, never the FBO-rendered cube
            gl.glGenTextures(1, ctypes.byref(copy))
            for level in range(self.levels):
                side = self.size >> level
                data = np.empty((side, side, 4), np.float32)
                for face in range(6):
                    target = gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face
                    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, scratch.value)
                    gl.glGetTexImage(target, level, gl.GL_RGBA, gl.GL_FLOAT, data.ctypes.data_as(ctypes.c_void_p))
                    gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, copy.value)
                    gl.glTexImage2D(target, level, gl.GL_RGBA16F, side, side, 0, gl.GL_RGBA, gl.GL_FLOAT,
                                    data.ctypes.data_as(ctypes.c_void_p))
            for name, value in _cube_parameters(gl):
                gl.glTexParameteri(gl.GL_TEXTURE_CUBE_MAP, name, value)
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
        finally:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, saved["draw_fbo"])
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, saved["read_fbo"])
            if fbo.value:
                gl.glDeleteFramebuffers(1, ctypes.byref(fbo))
            if scratch.value:
                gl.glDeleteTextures(1, ctypes.byref(scratch))
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, saved["cube"])
            gl.glActiveTexture(saved["active"])
            gl.glViewport(*saved["viewport"])
            gl.glUseProgram(saved["program"])
            gl.glBindVertexArray(saved["vao"])
            gl.glDepthMask(saved["depth_mask"])
            for cap, on in flags.items():
                (gl.glEnable if on else gl.glDisable)(cap)
        if self._texture:
            gl.glDeleteTextures(1, ctypes.byref(gl.GLuint(self._texture)))
        self._texture = copy.value
        self._studio = studio
        self.prefilters += 1
        self.last_ms = (time.perf_counter() - start) * 1e3
        return True

    # -- the lookup ----------------------------------------------------------------------------------------------------

    @staticmethod
    def uniforms() -> dict:
        """`LD_CUBE_SRC`'s sampler (the cube on `CUBE_UNIT`)."""
        return {"u_ld_env_cube": CUBE_UNIT}

    def bind(self, unit: int = CUBE_UNIT) -> None:
        from pyglet import gl

        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, self._texture)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    @staticmethod
    def unbind(unit: int = CUBE_UNIT) -> None:
        from pyglet import gl

        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def read_back(self, level: int):
        """The sampled cube's `level` as (6, side, side, 4) float32, faces +X .. -Z, row = t (test hook)."""
        import ctypes

        import numpy as np
        from pyglet import gl

        side = self.size >> level
        out = np.empty((6, side, side, 4), np.float32)
        active, bound = gl.GLint(), gl.GLint()
        gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE, ctypes.byref(active))
        gl.glActiveTexture(gl.GL_TEXTURE0 + CUBE_UNIT)
        gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_CUBE_MAP, ctypes.byref(bound))
        gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, self._texture)
        for face in range(6):
            gl.glGetTexImage(gl.GL_TEXTURE_CUBE_MAP_POSITIVE_X + face, level, gl.GL_RGBA, gl.GL_FLOAT,
                             out[face].ctypes.data_as(ctypes.c_void_p))
        gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, bound.value)
        gl.glActiveTexture(active.value)
        return out

    def release(self) -> None:
        import ctypes

        from pyglet import gl

        if self._texture:
            gl.glDeleteTextures(1, ctypes.byref(gl.GLuint(self._texture)))
            self._texture = 0
        self._studio = None
        if self._program is not None:
            self._program.delete()
            self._program = None
        if self._vao:
            gl.glDeleteVertexArrays(1, ctypes.byref(gl.GLuint(self._vao)))
            self._vao = 0
