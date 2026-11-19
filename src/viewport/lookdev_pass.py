"""The LookDev pass (AD-038 §3): draws a store's VertexList with the skin program instead of the Worklight's
`GLRenderStore.draw()` - a foreign pass on the store's buffers, built like `EyePass`. With `Viewport.shading ==
"worklight"` nothing here exists or runs (LD-D10).

- Inputs: `store.vertex_list()`, `uniform_data("camera_uniforms" / "model_uniforms")`, the triangle UVs through
  `GLRenderStore.bind_triangle_uvs` (unit 3, C1) and the albedo through `GLRenderStore.texture_binding` (unit 4). No
  other face data, no store buffer is written (I-10).
- Programs: `lookdev_shaders.skin_sources` (the textured Worklight VS + GS, so the depth contract I-1 holds by
  construction), compiled lazily, cached by `(ALBEDO_MAP, ENV_SPEC)` - at most 4.
- GL state as `EyePass`: during the draw depth test and write on, blend off, back faces culled, polygon offset (1, 1)
  when `store.polygon_offset`; afterwards offset, cull and depth test off, units 3 / 4 unbound, unit 0 active, program
  stopped. No FBO, no float target (the RGBA8 default framebuffer).
- The background (§8): a full-screen triangle (one empty VAO), depth test and write off, the colours as picked; the
  depth test, depth mask and program are left as found.

`LookDraw` is what the viewport needs per object (the app resolves it from the object, never from the Worklight
packet: no selection tint, independent of the texture toggle - AD-038 §3.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from .lookdev_shaders import ALBEDO_UNIT, UV_UNIT, background_sources, skin_sources

_IDENTITY_4 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


@dataclass(frozen=True)
class LookDraw:
    """One object in the LookDev pass: the organic material's values (sRGB artist colours; `specular` is the level,
    F0 = 0.08 x level; `roughness` perceptual, alpha = r²) and its albedo source - a path, a `LiveTexture` or None
    (the base colour)."""

    base_color: tuple[float, float, float]
    roughness: float = 0.6
    specular: float = 0.5
    wrap_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)
    backscatter: float = 0.0
    backscatter_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    albedo: object = None

    @property
    def f0(self) -> float:
        return 0.08 * float(self.specular)

    def uniforms(self) -> dict:
        return {"u_base_color": tuple(float(c) for c in self.base_color), "u_roughness": float(self.roughness),
                "u_f0": self.f0, "u_wrap": tuple(float(c) for c in self.wrap_rgb),
                "u_backscatter": float(self.backscatter),
                "u_backscatter_color": tuple(float(c) for c in self.backscatter_color)}


def set_uniforms(program, values: dict, active: dict | None = None) -> None:
    """Every value whose name `program` declares (arrays cut to the declared size: a driver may shorten an array)."""
    active = program.uniforms if active is None else active
    for name, value in values.items():
        info = active.get(name)
        if info is None:
            continue
        size = info["size"] if isinstance(info, dict) else getattr(info, "size", 1)
        if size > 1 and isinstance(value, list):
            value = value[:size]
        program[name] = value


class LookdevPass:
    """Skin programs (per variant), the background and the draw. Created by the viewport on the first LookDev frame."""

    def __init__(self) -> None:
        self.programs: dict = {}
        self._background = None
        self._vao = None
        #: Render-only lever (AD-038 §9): False drops the studio specular on skin (`ENV_SPEC` 0).
        self.env_spec = True
        #: Test hook / probe: how many objects the last frames drew.
        self.draws = 0

    def program(self, albedo_map: bool, env_spec: bool):
        from pyglet.graphics.shader import Shader, ShaderProgram

        from .gl_render_store import GLRenderStore, _register_sampler_buffer_uniform

        key = (bool(albedo_map), bool(env_spec))
        program = self.programs.get(key)
        if program is None:
            _register_sampler_buffer_uniform()
            attributes = GLRenderStore.program().attributes
            locations = {"position": attributes["position"]["location"], "normal": attributes["normal"]["location"]}
            program = ShaderProgram(*(Shader(src, kind) for src, kind in skin_sources(locations, *key)))
            self.programs[key] = program
        return program

    def draw(self, render_mesh, look: LookDraw, frame: dict) -> bool:
        """Draw one object. False = nothing drawn (no VertexList / camera yet, or a Ghost): the caller draws it with the
        Worklight."""
        from pyglet import gl

        from .gl_render_store import GLRenderStore

        store = render_mesh.store
        vlist = store.vertex_list() if hasattr(store, "vertex_list") else None
        camera = store.uniform_data("camera_uniforms") if vlist is not None else []
        if vlist is None or len(camera) != 32 or getattr(store, "alpha", 1.0) < 1.0:
            return False
        uvs = look.albedo is not None and store.bind_triangle_uvs(UV_UNIT)
        texture = GLRenderStore.texture_binding(look.albedo) if uvs else None
        if uvs and texture is None:
            GLRenderStore.unbind_triangle_uvs(UV_UNIT)
            uvs = False
        program = self.program(texture is not None, self.env_spec)
        program.use()
        active = program.uniforms  # pyglet builds this dict on every access: once per draw
        model = store.uniform_data("model_uniforms")
        set_uniforms(program, frame, active)
        set_uniforms(program, look.uniforms(), active)
        set_uniforms(program, {"u_view": tuple(camera[0:16]), "u_proj": tuple(camera[16:32]),
                               "u_model": tuple(model) if len(model) == 16 else _IDENTITY_4,
                               "u_triangle_uvs": UV_UNIT, "u_albedo": ALBEDO_UNIT}, active)
        if texture is not None:
            gl.glActiveTexture(gl.GL_TEXTURE0 + ALBEDO_UNIT)
            gl.glBindTexture(*texture)
            gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDisable(gl.GL_BLEND)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glCullFace(gl.GL_BACK)
        offset = bool(getattr(store, "polygon_offset", False))
        if offset:
            gl.glEnable(gl.GL_POLYGON_OFFSET_FILL)
            gl.glPolygonOffset(1.0, 1.0)
        vlist.draw(gl.GL_TRIANGLES)
        if offset:
            gl.glDisable(gl.GL_POLYGON_OFFSET_FILL)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_DEPTH_TEST)
        if texture is not None:
            gl.glActiveTexture(gl.GL_TEXTURE0 + ALBEDO_UNIT)
            gl.glBindTexture(texture[0], 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
        if uvs:
            GLRenderStore.unbind_triangle_uvs(UV_UNIT)
        program.stop()
        self.draws += 1
        return True

    def draw_background(self, bottom, top) -> None:
        """The background as picked (solid: bottom == top), before every mesh."""
        import ctypes

        from pyglet import gl
        from pyglet.graphics.shader import Shader, ShaderProgram

        if self._background is None:
            self._background = ShaderProgram(*(Shader(src, kind) for src, kind in background_sources()))
            vao = gl.GLuint()
            gl.glGenVertexArrays(1, ctypes.byref(vao))
            self._vao = vao.value
        depth_test = gl.glIsEnabled(gl.GL_DEPTH_TEST)
        mask = gl.GLboolean()
        gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK, ctypes.byref(mask))
        vao_was = gl.GLint()
        gl.glGetIntegerv(gl.GL_VERTEX_ARRAY_BINDING, ctypes.byref(vao_was))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        program = self._background
        program.use()
        program["u_bottom"] = tuple(float(c) for c in bottom)
        program["u_top"] = tuple(float(c) for c in top)
        gl.glBindVertexArray(self._vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glBindVertexArray(vao_was.value)
        gl.glDepthMask(mask.value)
        if depth_test:
            gl.glEnable(gl.GL_DEPTH_TEST)
        program.stop()

    def release(self) -> None:
        for program in self.programs.values():
            program.delete()
        self.programs.clear()
        if self._background is not None:
            import ctypes

            from pyglet import gl

            self._background.delete()
            gl.glDeleteVertexArrays(1, ctypes.byref(gl.GLuint(self._vao)))
            self._background, self._vao = None, None
