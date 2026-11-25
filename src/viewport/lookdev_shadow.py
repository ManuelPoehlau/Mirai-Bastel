"""The key light's shadow map (AD-039 §4, LookDev P3 S1): one 2D depth map from the key, orthographic over the casters'
bounding sphere; the skin pass reads it through `lookdev_shaders.LD_SHADOW_SRC` on unit 6, and since S2 (AD-039 §5) the
eye pass's LOOKDEV + LD_SHADOW variant does (the eyes receive, they never cast).

- **Fixed setting** (`PROVISIONAL`, P3-0 on the reference PC, Q-P3-3): 1024² DEPTH_COMPONENT24, `GL_LINEAR` with
  compare mode (3 x 3 hardware bilinear-compare fetches in the shader), `CLAMP_TO_BORDER` with border depth 1.0 (outside
  the map = lit), the depth pass with a slope-scaled polygon offset (2, 4); the lookup adds a normal offset of about one
  texel; the fetches stay one texel apart with a receiver-plane bias. The key's size ("Weichheit") sets the map's
  effective resolution (`lookdev_optics.shadow_resolution`: a soft key renders fewer texels, a wider smooth ramp;
  AD-039 §16.6).
- **Re-rendered only on a change** (`key`): for each caster `(id(rm), layout_revision, content_revision, model)` - the
  GPU picker's key - the key's world direction and the frustum. A pose step, a morph weight, a SubD re-evaluation, a
  topology edit, Hide / Isolate, a placement, a studio rotation, a key azimuth / elevation or a softness that changes the
  effective resolution re-render it; a camera orbit (the studio is fixed to the world), a material, the exposure or a
  key intensity / colour do not. `renders`
  counts the passes (T1-3).
- **Frustum:** `lookdev_optics.shadow_frustum` over the casters' bounds, recomputed only when the caster set, a
  `layout_revision` or a placement changes - not per pose step, so the shadow does not swim during a drag. A pose that
  leaves the grown sphere clips at the border (lit): a named limitation.
- **GL:** the depth pass runs inside the LookDev frame through its own FBO and saves / restores what
  `EyePass.iris_table` does (draw / read framebuffer, viewport, program, vertex array, depth / blend / cull / scissor /
  polygon offset) plus the depth mask, depth function and polygon offset values. No FBO stays bound. It draws the
  stores' VertexLists with its own program and writes no store buffer (I-10); hidden faces are degenerate triangles, so
  they cast nothing (I-8).
- **Drag options** (AD-039 §11.1, open from P3-0: the drag cost more than the pass): `flush` issues a `glFlush` after the
  pass; `maps = 2` renders into the map the last frame did not sample (ping-pong). Both off by default; the room probe
  measures them (`probe_lookdev_room.py`, rows `lookdev +shadow drag ...`).
- **Postponed updates** (AD-040 §2.2, LD-3a): `update(..., defer)` lets the quality manager keep the last map for a
  caster-only change while the room is Interactive (`shadow_updates` "every_2nd" / "frozen"); the first call without
  `defer` renders it. Maximal (idle) uses a second instance of 2048² (`LookdevPass.key_shadow(size)`).

S4 (AD-039 §7): `bind_raw` binds the same map on `SHADOW_RAW_UNIT` (7) through a sampler object without compare mode
(GL_LINEAR, CLAMP_TO_EDGE; created on first use, deleted in `release()`), so the skin pass reads its raw depth for the
thickness; `unbind_raw` unbinds texture and sampler.

Owned by `LookdevPass` (created on the first LookDev frame with the shadow on, deleted in its `release()`); nothing here
exists with `shading == "worklight"` (G4).
"""

from __future__ import annotations

from . import lookdev_optics as lo
from .lookdev_shaders import SHADOW_RAW_UNIT, SHADOW_UNIT, shadow_depth_sources

_IDENTITY_4 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


def register_shadow_sampler_uniform() -> None:
    """pyglet (2.1) has no setter for `sampler2DShadow` uniforms and raises KeyError while introspecting the program;
    a shadow sampler is an int texture unit like `sampler2D` (the `gl_render_store._register_sampler_buffer_uniform`
    pattern; a no-op once pyglet knows the type)."""
    from pyglet import gl
    from pyglet.graphics import shader

    shader._uniform_setters.setdefault(gl.GL_SAMPLER_2D_SHADOW, shader._uniform_setters[gl.GL_SAMPLER_2D])


def _model(rm) -> tuple:
    model = rm.store.uniform_data("model_uniforms")
    return tuple(model) if len(model) == 16 else _IDENTITY_4


class KeyShadow:
    def __init__(self, size: int = lo.SHADOW_SIZE, maps: int = 1, flush: bool = False) -> None:
        if maps not in (1, 2):
            raise ValueError("maps: 1 or 2")
        self.size = int(size)
        self.maps = maps
        self.flush = bool(flush)
        #: Test hook / probe: how many depth passes ran (T1-3).
        self.renders = 0
        #: AD-040 §2.2: how many caster-only changes were postponed (`update(..., defer)`), and the current run of them.
        self.deferred = 0
        self._postponed = 0
        self._targets: list[tuple[int, int]] = []  # (texture, fbo) per map
        self._current = 0  # the map the skin pass samples
        self._program = None
        self._key = None
        self._frustum_key = None
        self._sphere = ((0.0, 0.0, 0.0), 1.0)
        self._vp = list(_IDENTITY_4)
        self._resolution = self.size
        self._raw_sampler = 0  # S4's sampler object, created on the first `bind_raw`

    # -- the cache key ---------------------------------------------------------------------------------------------

    @staticmethod
    def _drawable(casters) -> list:
        out = []
        for rm in casters:
            store = rm.store
            if hasattr(store, "vertex_list") and store.vertex_list() is not None:
                out.append(rm)
        return out

    def frustum(self, casters) -> tuple[tuple[float, float, float], float]:
        """The sphere the map covers, recomputed only when the caster set, a layout or a placement changed."""
        key = tuple((id(rm), rm.layout_revision, _model(rm)) for rm in casters)
        if key != self._frustum_key:
            boxes = []
            for rm in casters:
                derived = rm.derived
                boxes.append((derived.bounds_min, derived.bounds_max, _model(rm)))
            self._sphere = lo.shadow_frustum(boxes)
            self._frustum_key = key
        return self._sphere

    def key(self, casters, key_dir, key_size: float = 0.0) -> tuple:
        """What the map shows: per caster the GPU picker's key, the key's direction, the frustum, the effective
        resolution (the key's softness). O(casters), no GL."""
        sphere = self.frustum(casters)
        return (tuple((id(rm), rm.layout_revision, rm.content_revision, _model(rm)) for rm in casters),
                tuple(float(c) for c in key_dir), sphere, lo.shadow_resolution(key_size, self.size))

    # -- the pass --------------------------------------------------------------------------------------------------

    def update(self, casters, key_dir, key_size: float = 0.0, defer: int | None = 0) -> bool:
        """Render the map if what it shows changed since the last pass (`key_size`: the key's softness, the map's
        effective resolution). True = it rendered. AD-040 §2.2 (`shadow_updates` while Interactive): a change of the
        casters' content alone (a pose, morph or sculpt step; the same casters, key, frustum and resolution) may be
        postponed `defer` times in a row (0 = never, "every"; 1 = "every_2nd"; None = until a call with a smaller
        `defer`, "frozen") - the map keeps its last pass meanwhile; `deferred` counts the postponed calls."""
        casters = self._drawable(casters)
        key = self.key(casters, key_dir, key_size)
        if key == self._key and self._targets:
            return False
        if (self._key is not None and self._targets and key[1:] == self._key[1:]
                and tuple(c[0] for c in key[0]) == tuple(c[0] for c in self._key[0])
                and (defer is None or self._postponed < defer)):
            self._postponed += 1
            self.deferred += 1
            return False
        self._postponed = 0
        if not self._ensure():
            return False
        centre, radius = self._sphere
        self._vp = lo.shadow_view_projection(key_dir, centre, radius)
        target = (self._current + 1) % len(self._targets) if self._key is not None else self._current
        self._resolution = key[3]
        self._render(casters, self._targets[target][1])
        self._current = target
        self._key = key
        return True

    def _ensure(self) -> bool:
        import ctypes

        from pyglet import gl
        from pyglet.graphics.shader import Shader, ShaderProgram

        from .gl_render_store import GLRenderStore

        if self._program is None:
            attributes = GLRenderStore.program().attributes
            locations = {"position": attributes["position"]["location"]}
            self._program = ShaderProgram(*(Shader(src, kind) for src, kind in shadow_depth_sources(locations)))
        if self._targets:
            return True
        draw_fbo, read_fbo, bound, active = gl.GLint(), gl.GLint(), gl.GLint(), gl.GLint()
        gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING, ctypes.byref(draw_fbo))
        gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING, ctypes.byref(read_fbo))
        gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE, ctypes.byref(active))
        gl.glActiveTexture(gl.GL_TEXTURE0 + SHADOW_UNIT)
        gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D, ctypes.byref(bound))
        border = (gl.GLfloat * 4)(1.0, 1.0, 1.0, 1.0)
        for _ in range(self.maps):
            texture, fbo = gl.GLuint(), gl.GLuint()
            gl.glGenTextures(1, ctypes.byref(texture))
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture.value)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH_COMPONENT24, self.size, self.size, 0,
                            gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, None)
            for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                                (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER),
                                (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER),
                                (gl.GL_TEXTURE_COMPARE_MODE, gl.GL_COMPARE_REF_TO_TEXTURE),
                                (gl.GL_TEXTURE_COMPARE_FUNC, gl.GL_LEQUAL)):
                gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
            gl.glTexParameterfv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_BORDER_COLOR, border)
            gl.glGenFramebuffers(1, ctypes.byref(fbo))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo.value)
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_TEXTURE_2D, texture.value, 0)
            gl.glDrawBuffer(gl.GL_NONE)
            gl.glReadBuffer(gl.GL_NONE)
            complete = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
            self._targets.append((texture.value, fbo.value))
            if not complete:
                break
        gl.glBindTexture(gl.GL_TEXTURE_2D, bound.value)
        gl.glActiveTexture(active.value)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, draw_fbo.value)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, read_fbo.value)
        if len(self._targets) != self.maps or not complete:
            self.release(keep_program=True)
            return False
        return True

    def _render(self, casters, fbo: int) -> None:
        import ctypes

        from pyglet import gl

        def geti(name, count=1):
            buf = (gl.GLint * count)()
            gl.glGetIntegerv(name, buf)
            return buf[0] if count == 1 else tuple(buf)

        def getf(name):
            value = gl.GLfloat()
            gl.glGetFloatv(name, ctypes.byref(value))
            return value.value

        saved = {"draw_fbo": geti(gl.GL_DRAW_FRAMEBUFFER_BINDING), "read_fbo": geti(gl.GL_READ_FRAMEBUFFER_BINDING),
                 "viewport": geti(gl.GL_VIEWPORT, 4), "program": geti(gl.GL_CURRENT_PROGRAM),
                 "vao": geti(gl.GL_VERTEX_ARRAY_BINDING), "depth_mask": geti(gl.GL_DEPTH_WRITEMASK),
                 "depth_func": geti(gl.GL_DEPTH_FUNC), "offset": (getf(gl.GL_POLYGON_OFFSET_FACTOR),
                                                                  getf(gl.GL_POLYGON_OFFSET_UNITS))}
        flags = {cap: bool(gl.glIsEnabled(cap)) for cap in (gl.GL_SCISSOR_TEST, gl.GL_DEPTH_TEST, gl.GL_BLEND,
                                                            gl.GL_CULL_FACE, gl.GL_POLYGON_OFFSET_FILL)}
        try:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glViewport(0, 0, self._resolution, self._resolution)  # the clear below covers the whole map: lit
            for cap in (gl.GL_SCISSOR_TEST, gl.GL_BLEND, gl.GL_CULL_FACE):
                gl.glDisable(cap)
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LESS)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
            gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
            gl.glPolygonOffset(*lo.SHADOW_POLYGON_OFFSET)
            program = self._program
            program.use()
            program["u_ld_shadow_vp"] = tuple(self._vp)
            for rm in casters:
                program["u_model"] = _model(rm)
                rm.store.vertex_list().draw(gl.GL_TRIANGLES)
            self.renders += 1
            if self.flush:
                gl.glFlush()
        finally:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, saved["draw_fbo"])
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, saved["read_fbo"])
            gl.glViewport(*saved["viewport"])
            gl.glUseProgram(saved["program"])
            gl.glBindVertexArray(saved["vao"])
            gl.glDepthMask(saved["depth_mask"])
            gl.glDepthFunc(saved["depth_func"])
            gl.glPolygonOffset(*saved["offset"])
            for cap, on in flags.items():
                (gl.glEnable if on else gl.glDisable)(cap)

    # -- the lookup ------------------------------------------------------------------------------------------------

    @property
    def ready(self) -> bool:
        return self._key is not None and bool(self._targets)

    def uniforms(self) -> dict:
        """`LD_SHADOW_SRC`'s uniforms for the current map (the sampler on `SHADOW_UNIT`)."""
        values = lo.shadow_uniforms(self._vp, self._sphere[1], 0.0, self.size)
        values["u_ld_shadow_scale"] = self._resolution / float(self.size)
        values["u_ld_shadow_offset"] = lo.SHADOW_NORMAL_OFFSET_TEXELS * 2.0 * self._sphere[1] / self._resolution
        values["u_ld_shadow"] = SHADOW_UNIT
        values["u_ld_shadow_depth"] = SHADOW_RAW_UNIT  # S4: the raw depth
        values["u_ld_shadow_range"] = 2.0 * self._sphere[1]  # the map's depth [0, 1] spans the frustum's 2 radius
        return values

    def bind(self, unit: int = SHADOW_UNIT) -> None:
        from pyglet import gl

        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._targets[self._current][0])
        gl.glActiveTexture(gl.GL_TEXTURE0)

    @staticmethod
    def unbind(unit: int = SHADOW_UNIT) -> None:
        from pyglet import gl

        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def bind_raw(self, unit: int = SHADOW_RAW_UNIT) -> None:
        """S4: the current map on `unit` through the sampler object without compare mode (the raw depth)."""
        import ctypes

        from pyglet import gl

        if not self._raw_sampler:
            ident = gl.GLuint()
            gl.glGenSamplers(1, ctypes.byref(ident))
            for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                                (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE),
                                (gl.GL_TEXTURE_COMPARE_MODE, gl.GL_NONE)):
                gl.glSamplerParameteri(ident.value, name, value)
            self._raw_sampler = ident.value
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._targets[self._current][0])
        gl.glBindSampler(unit, self._raw_sampler)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    @staticmethod
    def unbind_raw(unit: int = SHADOW_RAW_UNIT) -> None:
        from pyglet import gl

        gl.glBindSampler(unit, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def release(self, keep_program: bool = False) -> None:
        import ctypes

        from pyglet import gl

        for texture, fbo in self._targets:
            gl.glDeleteFramebuffers(1, ctypes.byref(gl.GLuint(fbo)))
            gl.glDeleteTextures(1, ctypes.byref(gl.GLuint(texture)))
        self._targets = []
        self._key = None
        self._current = 0
        if not keep_program and self._program is not None:
            self._program.delete()
            self._program = None
        if not keep_program and self._raw_sampler:
            gl.glDeleteSamplers(1, ctypes.byref(gl.GLuint(self._raw_sampler)))
            self._raw_sampler = 0
