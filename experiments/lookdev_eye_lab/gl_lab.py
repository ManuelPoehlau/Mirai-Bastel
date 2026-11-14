"""GL side of the Eye Proof: the store, the renderer, the environment cube and the parity pass (P1, 2026-11-14).

**Seam under test (audit §4.2 / §5).** The eye parts are ordinary production object entries: `core.Mesh` ->
`RenderMesh` -> a store, drawn by `Viewport.render()` in its own order (edit mesh, opaque entries, Ghost entries). The
store is `EyeLabStore(GLRenderStore)`: it keeps every production mechanism (VertexList assembly, face data, triangle
UVs, texture cache) and only replaces `draw()`. For T-A it calls `GLRenderStore.draw` unchanged; for T-B ... T-D it
draws the **same VertexList** with a lab program on the production attribute locations - a third consumer of the
store's buffers after the GPU picker and the wire (audit §1.1). Nothing in `src/` changes.

**GL resources.** The lab's own objects (cube textures, full-frame VAO, queries, offscreen targets) go through
`lookdev_gpu_probe.probe_gl_caps.Resources`, so they are counted, deleted and leak-checked like the probe's. Programs
are pyglet `ShaderProgram`s (geometry-shader support, as production builds them); uniforms are set by raw `glUniform*`
after introspecting each program, so a uniform the compiler removed is skipped instead of raising.

Texture units: 0 stays pyglet's (HUD text), 1-7 are the production store's (face data, triangle UVs, the 2D image on 4),
the lab adds the environment cube on `ENV_UNIT` 8.
"""

from __future__ import annotations

import ctypes
import math
import time

import numpy as np

from lookdev_gpu_probe import cube_math as cm
from lookdev_gpu_probe import probe_gl_caps as pg
from viewport import gl_render_store as grs
from viewport.gl_render_store import GLRenderStore

from . import eye_geometry as geo
from . import lab_state as ls
from . import shaders
from . import studio_env as se

ENV_UNIT = 8
_IDENTITY = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


# -- programs and uniforms -------------------------------------------------------------------------------------------


class LabProgram:
    """A pyglet ShaderProgram plus its active uniforms (name -> (location, GL type, array size))."""

    def __init__(self, sources: list[tuple[str, str]]) -> None:
        from pyglet import gl
        from pyglet.graphics.shader import Shader, ShaderProgram

        grs._register_sampler_buffer_uniform()
        self.gl = gl
        self.program = ShaderProgram(*[Shader(src, kind) for src, kind in sources])
        self.id = self.program.id
        self.uniforms: dict[str, tuple[int, int, int]] = {}
        count = gl.GLint()
        gl.glGetProgramiv(self.id, gl.GL_ACTIVE_UNIFORMS, ctypes.byref(count))
        name = ctypes.create_string_buffer(256)
        for i in range(count.value):
            length, size, kind = gl.GLsizei(), gl.GLint(), gl.GLenum()
            gl.glGetActiveUniform(self.id, i, 256, ctypes.byref(length), ctypes.byref(size), ctypes.byref(kind),
                                  ctypes.cast(name, ctypes.POINTER(gl.GLchar)))
            text = name.value.decode("ascii")
            base = text[:-3] if text.endswith("[0]") else text
            self.uniforms[base] = (gl.glGetUniformLocation(self.id, name), kind.value, size.value)

    def use(self) -> None:
        self.gl.glUseProgram(self.id)

    def set(self, values: dict) -> None:
        """Sets each present uniform from a number, a sequence or a NumPy array (a matrix as its column-major
        floats, an array uniform as its elements concatenated). Requires the program in use."""
        gl = self.gl
        for key, value in values.items():
            entry = self.uniforms.get(key)
            if entry is None:
                continue
            loc, kind, size = entry
            if kind in (gl.GL_INT, gl.GL_BOOL, gl.GL_SAMPLER_2D, gl.GL_SAMPLER_CUBE, gl.GL_SAMPLER_BUFFER):
                gl.glUniform1i(loc, int(value))
                continue
            data = np.asarray(value, dtype=np.float32).ravel()
            ptr = data.ctypes.data_as(ctypes.POINTER(gl.GLfloat))
            if kind == gl.GL_FLOAT:
                gl.glUniform1fv(loc, data.size, ptr)
            elif kind == gl.GL_FLOAT_VEC2:
                gl.glUniform2fv(loc, data.size // 2, ptr)
            elif kind == gl.GL_FLOAT_VEC3:
                gl.glUniform3fv(loc, data.size // 3, ptr)
            elif kind == gl.GL_FLOAT_VEC4:
                gl.glUniform4fv(loc, data.size // 4, ptr)
            elif kind == gl.GL_FLOAT_MAT3:
                gl.glUniformMatrix3fv(loc, 1, gl.GL_FALSE, ptr)
            elif kind == gl.GL_FLOAT_MAT4:
                gl.glUniformMatrix4fv(loc, 1, gl.GL_FALSE, ptr)
            else:
                raise TypeError(f"uniform {key}: GL type {kind:#x} not handled")

    def delete(self) -> None:
        self.program.delete()


def env_uniforms(env: se.StudioEnv) -> dict:
    lights = env.lights[:shaders.MAX_LIGHTS]
    frames = [light.frame() for light in lights]
    return {
        "u_light_centre": [f[0] for f in frames], "u_light_right": [f[1] for f in frames],
        "u_light_up": [f[2] for f in frames],
        "u_light_half": [(math.radians(l.half_width), math.radians(l.half_height)) for l in lights],
        "u_light_radiance": [l.radiance for l in lights], "u_light_count": len(lights),
        "u_zenith": env.zenith, "u_horizon": env.horizon, "u_floor": env.floor,
        "u_horizon_width": env.horizon_width, "u_edge_sigma": env.edge_sigma,
    }


def mat3_columns(m: np.ndarray) -> np.ndarray:
    """A row-major 3x3 as the column-major floats `glUniformMatrix3fv(..., GL_FALSE, ...)` reads."""
    return np.asarray(m, dtype=np.float64).T.ravel()


# -- the environment cube --------------------------------------------------------------------------------------------


class EnvCube:
    """The prefiltered environment on the GPU, rebuilt when size / mapping / format change. Prefiltered chains are
    kept in memory and in the disk cache (`studio_env.prefilter`)."""

    def __init__(self, gl, res: pg.Resources, cache_dir) -> None:
        self.gl, self.res, self.cache_dir = gl, res, cache_dir
        self.key = None
        self.texture = 0
        self.last_level = 0
        self.chains: dict = {}
        self.info: dict = {}

    def chain(self, env: se.StudioEnv, size: int, mapping: int) -> se.Prefiltered:
        key = (env.fingerprint(), size, mapping)
        if key not in self.chains:
            self.chains[key] = se.prefilter(env, size, mapping, self.cache_dir)
        return self.chains[key]

    def ensure(self, state: ls.LabState) -> int:
        key = (state.env.fingerprint(), state.env_size, state.lod_mapping, state.env_format)
        if key == self.key:
            return self.texture
        chain = self.chain(state.env, state.env_size, state.lod_mapping)
        if state.env_format == "RGBA16F":
            fmt, levels = cm.RGBA16F, [se.to_rgba(level) for level in chain.levels]
        else:
            fmt, levels = cm.RGBA8, [se.rgbm_encode(level) for level in chain.levels]
        extensions = self.info.get("extensions", set())
        free_before = pg.free_kib(self.gl, extensions)
        if self.texture:
            self.res.delete("texture", self.texture)
        start = time.perf_counter()
        self.texture, errors, driver = pg.make_cube(self.gl, self.res, fmt, levels)
        self.gl.glFinish()
        upload = time.perf_counter() - start
        free_after = pg.free_kib(self.gl, extensions)
        self.key, self.last_level = key, chain.last_level
        self.info.update({
            "size": state.env_size, "format": state.env_format, "mapping": state.lod_mapping,
            "levels": len(levels), "roughness": chain.roughness, "samples": chain.samples,
            "prefilter_s": chain.seconds, "from_cache": chain.from_cache, "upload_s": upload,
            "bytes": se.chain_bytes(state.env_size, fmt.bytes_per_texel), "driver": driver, "errors": errors,
            "free_kib_drop": (free_before - free_after) if free_before is not None and free_after is not None else None,
        })
        return self.texture


# -- the store -------------------------------------------------------------------------------------------------------


class EyeLabStore(GLRenderStore):
    """`GLRenderStore` whose `draw()` asks the lab renderer which technique to use. `part` and `lab` are set by
    `lab_scene.build_scene` right after the entry exists; a store without them draws like production."""

    def __init__(self, stats) -> None:
        super().__init__(stats)
        self.part: str | None = None
        self.lab: "EyeLabRenderer | None" = None

    def draw(self, group: str = "mesh") -> None:
        lab = self.lab
        if lab is None or self.part is None:
            super().draw(group)
            return
        state = lab.state
        if not lab.part_visible(self.part):
            return
        if self.part == "cornea" and state.cornea == "C1":
            return
        if state.technique == "T-A":
            super().draw(group)  # production, unchanged (the cornea entry is a Ghost: alpha < 1)
            return
        lab.draw_surface(self, group)


# -- the renderer ----------------------------------------------------------------------------------------------------


class EyeLabRenderer:
    """Owns the lab's programs, the environment cube and the background pass; draws one frame of the scene."""

    def __init__(self, state: ls.LabState, cache_dir=None) -> None:
        from pyglet import gl

        self.gl = gl
        self.state = state
        self.res = pg.Resources(gl)
        self.env_cube = EnvCube(gl, self.res, cache_dir)
        self.programs: dict = {}
        self.background_program: LabProgram | None = None
        self.vao = 0
        self.camera = None
        self.ambient = {}
        #: None = the parts the state shows; a set = only these (probe: background alone, the chrome sweep).
        self.only_parts: set | None = None

    # -- state

    def part_visible(self, part: str) -> bool:
        if self.only_parts is not None:
            return part in self.only_parts
        return self.state.show_references or part not in ("chrome", "grey")

    def ambient_for(self, env: se.StudioEnv) -> tuple[np.ndarray, np.ndarray]:
        key = env.fingerprint()
        if key not in self.ambient:
            self.ambient[key] = se.ambient_colours(env)
        return self.ambient[key]

    def program(self, tech: int, textured: bool, c1: bool, shell: int | None, locations: dict) -> LabProgram:
        key = (tech, textured, c1, shell)
        if key not in self.programs:
            self.programs[key] = LabProgram(shaders.surface_sources(locations, tech, textured, c1, shell))
        return self.programs[key]

    def common_uniforms(self) -> dict:
        s = self.state
        sky, ground = self.ambient_for(s.env)
        scale = s.env_scale()
        values = {
            "u_key_dir": s.key_direction(), "u_key_irradiance": s.key_irradiance(),
            "u_sky": sky * scale, "u_ground": ground * scale, "u_env_intensity": scale,
            "u_env_rot": mat3_columns(s.env_rotation()), "u_exposure": s.exposure, "u_tonemap": s.tonemap,
            "u_lod_mode": s.lod_mapping, "u_env_rgbm": 1 if s.env_format == "RGBM8" else 0,
            "u_rgbm_range": se.RGBM_RANGE, "u_cornea_centre": (0.0, 0.0, geo.CORNEA_CENTRE_Z),
            "u_cornea_radius": geo.CORNEA_RADIUS, "u_limbus_z": geo.LIMBUS_Z, "u_cornea_f0": (s.cornea_f0,) * 3,
            "u_cornea_roughness": s.cornea_roughness,
        }
        values.update(env_uniforms(s.env))
        return values

    # -- drawing

    def draw_surface(self, store: EyeLabStore, group: str) -> None:
        gl = self.gl
        vlist = store.vertex_list(group)
        if vlist is None:
            return
        s = self.state
        tech = shaders.TECH_IDS[s.technique]
        textured = store.part == "iris" and store._textured()
        shell = shaders.SHELL_IDS[s.cornea] if store.part == "cornea" else None
        c1 = store.part == "iris" and s.cornea == "C1"
        attributes = GLRenderStore.program().attributes
        locations = {"position": attributes["position"]["location"], "normal": attributes["normal"]["location"]}
        program = self.program(tech, textured, c1, shell, locations)
        program.use()
        camera = store.uniform_data("camera_uniforms")
        model = store.uniform_data("model_uniforms")
        material = s.material(store.part)
        values = self.common_uniforms()
        values.update({
            "u_view": camera[0:16], "u_proj": camera[16:32], "u_model": model if len(model) == 16 else _IDENTITY,
            "u_eye": self.camera.eye(), "u_albedo": material.albedo, "u_f0": material.f0,
            "u_roughness": material.roughness, "u_spec_weight": material.spec_weight,
        })
        if tech == shaders.TECH_IDS["T-C"]:
            texture = self.env_cube.ensure(s)
            gl.glActiveTexture(gl.GL_TEXTURE0 + ENV_UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, texture)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            (gl.glEnable if s.seamless else gl.glDisable)(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
            values.update({"u_env": ENV_UNIT, "u_env_last": float(self.env_cube.last_level)})
        if textured:
            store._flush_face_data()  # uploads the triangle UVs (and the face data, unused here) and binds them
            image = store.texture(store._texture_path)
            gl.glActiveTexture(gl.GL_TEXTURE0 + grs._TEXTURE_UNIT)
            gl.glBindTexture(image.target, image.id)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            values.update({"u_texture": grs._TEXTURE_UNIT, "u_triangle_uvs": grs._TRIANGLE_UVS_UNIT})
        program.set(values)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glCullFace(gl.GL_BACK)
        if shell is not None:
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_ONE, gl.GL_ONE if shell == 2 else gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glDepthMask(gl.GL_FALSE)
        vlist.draw(gl.GL_TRIANGLES)
        if shell is not None:
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_DEPTH_TEST)
        if textured:
            store._unbind_face_data()
            gl.glActiveTexture(gl.GL_TEXTURE0 + grs._TEXTURE_UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        if tech == shaders.TECH_IDS["T-C"]:
            gl.glActiveTexture(gl.GL_TEXTURE0 + ENV_UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
            gl.glDisable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def draw_background(self, width: int, height: int) -> None:
        gl = self.gl
        s = self.state
        if self.background_program is None:
            self.background_program = LabProgram(shaders.background_sources())
            self.vao = pg.fullscreen_triangle(gl, self.res)
        forward, right, up = self.camera.basis()
        program = self.background_program
        program.use()
        values = {
            "u_size": (float(width), float(height)), "u_cam_right": right, "u_cam_up": up, "u_cam_forward": forward,
            "u_tan_half": math.tan(math.radians(self.camera.fov_degrees) / 2.0),
            "u_env_rot": mat3_columns(s.env_rotation()), "u_env_intensity": s.env_scale(),
            "u_blur": ls.BACKGROUND_BLUR, "u_solid": 1 if s.background == "solid" else 0,
            "u_solid_colour": ls.SOLID_BACKGROUND, "u_exposure": s.exposure, "u_tonemap": s.tonemap,
        }
        values.update(env_uniforms(s.env))
        program.set(values)
        gl.glBindVertexArray(self.vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glBindVertexArray(0)

    def frame(self, viewport, width: int, height: int) -> None:
        """Clear (T-A: the production clear colour) or the background, then the viewport's own render."""
        gl = self.gl
        gl.glViewport(0, 0, width, height)
        gl.glClearColor(0.1, 0.1, 0.11, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        if self.state.technique != "T-A":
            self.draw_background(width, height)
        viewport.sync()
        viewport.render()
        gl.glUseProgram(0)

    def release(self) -> None:
        for program in self.programs.values():
            program.delete()
        self.programs.clear()
        if self.background_program is not None:
            self.background_program.delete()
            self.background_program = None
        self.res.release_all()
        self.env_cube.texture = 0
        self.env_cube.key = None


# -- offscreen target and read-back ----------------------------------------------------------------------------------


class Target:
    """An offscreen RGBA8 + DEPTH24 framebuffer (the GPU picker's formats, TESTED [RPC]) of an exact size, so the
    measured frame sizes do not depend on the screen."""

    def __init__(self, gl, res: pg.Resources, width: int, height: int) -> None:
        self.gl, self.res, self.width, self.height = gl, res, width, height
        self.fbo, self.colour, self.depth = res.framebuffer(), res.renderbuffer(), res.renderbuffer()
        with pg.preserved(gl):
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.colour)
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_RGBA8, width, height)
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.depth)
            gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_DEPTH_COMPONENT24, width, height)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_RENDERBUFFER, self.colour)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER, self.depth)
            status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        self.status = pg.FBO_STATUS.get(status, hex(status))

    def bind(self) -> None:
        self.gl.glBindFramebuffer(self.gl.GL_FRAMEBUFFER, self.fbo)

    def unbind(self) -> None:
        self.gl.glBindFramebuffer(self.gl.GL_FRAMEBUFFER, 0)

    def read_rgb(self) -> np.ndarray:
        """(height, width, 3) uint8, row 0 at the top."""
        gl = self.gl
        out = np.empty((self.height, self.width, 3), dtype=np.uint8)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self.fbo)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        gl.glReadPixels(0, 0, self.width, self.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, out.ctypes.data)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 4)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
        return out[::-1].copy()

    def release(self) -> None:
        for kind, name in (("framebuffer", self.fbo), ("renderbuffer", self.colour), ("renderbuffer", self.depth)):
            self.res.delete(kind, name)


def read_window_rgb(gl, width: int, height: int) -> np.ndarray:
    out = np.empty((height, width, 3), dtype=np.uint8)
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, width, height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, out.ctypes.data)
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 4)
    return out[::-1].copy()


# -- parity ----------------------------------------------------------------------------------------------------------


class ParityPass:
    """Evaluates one `LIB_SRC` function per fragment: inputs (n, 12) float32 (three vec4 per sample) from an RGBA32F
    buffer texture, outputs (n, 4) read back from an RGBA32F colour target (TESTED [RPC] by the probe)."""

    WIDTH, ROWS = 256, 64

    def __init__(self, gl, res: pg.Resources, env: se.StudioEnv = se.DEFAULT_ENV) -> None:
        self.gl, self.res = gl, res
        self.program = LabProgram(shaders.parity_sources())
        self.vao = pg.fullscreen_triangle(gl, res)
        self.buffer, self.buffer_texture = res.buffer(), res.texture()
        self.fbo, self.rb, self.status = pg.colour_target(gl, res, gl.GL_RGBA32F, self.WIDTH, self.ROWS)
        self.env = env

    def run(self, func: str, inputs: np.ndarray) -> np.ndarray:
        gl = self.gl
        data = np.ascontiguousarray(inputs, dtype=np.float32).reshape(-1, 12)
        count = len(data)
        if count > self.WIDTH * self.ROWS:
            raise ValueError(f"{count} samples > {self.WIDTH * self.ROWS}")
        rows = -(-count // self.WIDTH)
        out = np.zeros((rows, self.WIDTH, 4), dtype=np.float32)
        with pg.preserved(gl):
            gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, self.buffer)
            gl.glBufferData(gl.GL_TEXTURE_BUFFER, data.nbytes, data.ctypes.data, gl.GL_STREAM_DRAW)
            gl.glActiveTexture(gl.GL_TEXTURE0 + pg.SAMPLE_UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_BUFFER, self.buffer_texture)
            gl.glTexBuffer(gl.GL_TEXTURE_BUFFER, gl.GL_RGBA32F, self.buffer)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
            gl.glViewport(0, 0, self.WIDTH, rows)
            self.program.use()
            values = {"u_inputs": pg.SAMPLE_UNIT, "u_width": self.WIDTH, "u_count": count,
                      "u_func": shaders.PARITY_FUNCS[func]}
            values.update(env_uniforms(self.env))
            self.program.set(values)
            gl.glBindVertexArray(self.vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glReadPixels(0, 0, self.WIDTH, rows, gl.GL_RGBA, gl.GL_FLOAT, out.ctypes.data)
        return out.reshape(-1, 4)[:count].astype(np.float64)

    def release(self) -> None:
        self.program.delete()
