"""The LookDev pass (AD-038 §3): draws a store's VertexList with the skin program instead of the Worklight's
`GLRenderStore.draw()` - a foreign pass on the store's buffers, built like `EyePass`. With `Viewport.shading ==
"worklight"` nothing here exists or runs (LD-D10).

- Inputs: `store.vertex_list()`, `uniform_data("camera_uniforms" / "model_uniforms")`, the triangle UVs through
  `GLRenderStore.bind_triangle_uvs` (unit 3, C1) and the albedo through `GLRenderStore.texture_binding` (unit 4). No
  other face data, no store buffer is written (I-10).
- Programs: `lookdev_shaders.skin_sources` (the textured Worklight VS + GS, so the depth contract I-1 holds by
  construction), compiled lazily, cached by the tuple of their defines in a fixed order `(ALBEDO_MAP, ENV_SPEC,
  SHADOW, DUAL_LOBE, THICKNESS)` (AD-039 §2.3 point 4).
- P3 (AD-039): the pass owns the effects' resources - S1's `KeyShadow` (created on the first frame with the shadow on,
  deleted in `release()`) - and the context's `FeatureReport` (`lookdev_features.probe`, once, the first time an effect
  needs it). With the shadow the map is bound on unit 6 for the draw and unbound after it; with the thickness (S4) also
  on unit 7 through its raw-depth sampler object, unbound (texture and sampler) after it. S7 (AD-039 §10): a
  LookDraw's maps through the shared texture cache (`GLRenderStore.texture`, mipmapped) on units 9-11
  (`MAP_UNITS`), with the triangle UVs on unit 3 even without an albedo map; unbound after the draw. A program's key
  gains the three map flags only when a map is drawn (every key without maps stays the 5 values of S4). S5 (AD-039 §8):
  the studio's prefiltered cube (`lookdev_cube.EnvCube`, created on the first frame with the effect on, deleted in
  `release()`) on unit 8 for a draw with `ENV_SPEC`, `GL_TEXTURE_CUBE_MAP_SEAMLESS` on only around that draw (restored
  to what it was); a key with the cube is 9 values (S4's 5, the three map flags, `CUBE_ENV`). S6 (AD-039 §9): a
  LookDraw's region materials (`regions`, `region_faces`) - the RenderMesh's per-triangle slots
  (`RenderMesh.set_triangle_material_slots`, set by the viewport) through `GLRenderStore.bind_triangle_materials` on
  unit 12 (`REGION_UNIT`), the slots' values as uniform arrays; a key with regions is 10 values (the cube's 9 with the
  cube flag False when it is off, then `REGIONS`), every key without regions stays as it was.
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

from .lookdev_shaders import (ALBEDO_UNIT, CUBE_UNIT, MAP_UNITS, REGION_SLOTS, REGION_UNIT, SHADOW_RAW_UNIT,
                              SHADOW_UNIT, UV_UNIT, background_sources, skin_sources)

_IDENTITY_4 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


@dataclass(frozen=True)
class LookDraw:
    """One object in the LookDev pass: the organic material's values (sRGB artist colours; `specular` is the level,
    F0 = 0.08 x level; `roughness` perceptual, alpha = r²) and its albedo source - a path, a `LiveTexture` or None
    (the base colour). AD-039 S7: the material's map paths the pass may load (`roughness_map`, `normal_map`,
    `translucency_map`; None = none), the normal map's strength and its green direction. AD-039 S6: `regions` = the
    materials of the object's face regions (LookDraws whose maps are ignored: the maps are the object's), slot i + 1
    for `region_faces[i]` (the FaceIds of the object's mesh; on overlap the later region wins)."""

    base_color: tuple[float, float, float]
    roughness: float = 0.6
    specular: float = 0.5
    wrap_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)
    backscatter: float = 0.0
    backscatter_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    albedo: object = None
    roughness_map: str | None = None
    normal_map: str | None = None
    translucency_map: str | None = None
    normal_strength: float = 1.0
    normal_green_down: bool = False
    regions: tuple = ()
    region_faces: tuple = ()

    def __post_init__(self) -> None:
        if len(self.regions) != len(self.region_faces) or len(self.regions) >= REGION_SLOTS:
            raise ValueError(f"LookDraw: at most {REGION_SLOTS - 1} regions, each with its faces")

    @property
    def f0(self) -> float:
        return 0.08 * float(self.specular)

    def map_paths(self) -> dict[str, str]:
        """AD-039 S7: {"roughness" / "normal" / "translucency": path} of the maps it has."""
        paths = {"roughness": self.roughness_map, "normal": self.normal_map, "translucency": self.translucency_map}
        return {kind: path for kind, path in paths.items() if path is not None}

    @property
    def needs_uvs(self) -> bool:
        """An albedo map (the object's or a region's) or any map reads the triangle UVs (AD-038 §4.1, AD-039 §10)."""
        return self.albedo_source() is not None or bool(self.map_paths())

    def albedo_source(self, regions: bool = True):
        """The albedo map the draw binds: the object's, or with `regions` the first region's that has one (they share
        the object's UVs and its one source, AD-039 §9)."""
        if self.albedo is not None or not regions:
            return self.albedo
        return next((r.albedo for r in self.regions if r.albedo is not None), None)

    def slot_uniforms(self) -> dict:
        """AD-039 S6: the `REGIONS` program's uniform arrays - slot 0 the object's values, slot i + 1 region i's, the
        unused slots the object's again."""
        slots = [self, *self.regions] + [self] * (REGION_SLOTS - 1 - len(self.regions))
        return {"u_slot_base_color": [tuple(float(c) for c in d.base_color) for d in slots],
                "u_slot_albedo": [1.0 if d.albedo is not None else 0.0 for d in slots],
                "u_slot_roughness": [float(d.roughness) for d in slots], "u_slot_fresnel": [d.f0 for d in slots],
                "u_slot_wrap": [tuple(float(c) for c in d.wrap_rgb) for d in slots],
                "u_slot_backscatter": [float(d.backscatter) for d in slots],
                "u_slot_backscatter_color": [tuple(float(c) for c in d.backscatter_color) for d in slots],
                "u_triangle_material": REGION_UNIT}

    def map_uniforms(self) -> dict:
        return {"u_roughness_map": MAP_UNITS["roughness"], "u_normal_map": MAP_UNITS["normal"],
                "u_translucency_map": MAP_UNITS["translucency"], "u_normal_strength": float(self.normal_strength),
                "u_normal_green": -1.0 if self.normal_green_down else 1.0}

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
        #: AD-039 §2.2: this context's P3 features (None until an effect first needs them).
        self.features = None
        #: The status lines of missing features not yet shown (the viewport hands them to the app once).
        self.notices: list[str] = []
        #: AD-039 §4: the key's shadow map (S1), created on the first frame with the shadow on.
        self.shadow = None
        #: AD-039 §8: the studio's environment cube (S5), created on the first frame with the cube on.
        self.cube = None

    def feature_report(self):
        """The context's P3 features, probed once (AD-039 §2.2); a missing one queues its status line once."""
        if self.features is None:
            from . import lookdev_features

            self.features = lookdev_features.probe()
            self.notices.extend(self.features.status_lines())
        return self.features

    def key_shadow(self):
        """S1's map (AD-039 §4), created on first use."""
        if self.shadow is None:
            from .lookdev_shadow import KeyShadow

            self.shadow = KeyShadow()
        return self.shadow

    def env_cube(self):
        """S5's cube (AD-039 §8), created on first use."""
        if self.cube is None:
            from .lookdev_cube import EnvCube

            self.cube = EnvCube()
        return self.cube

    @staticmethod
    def program_key(albedo_map: bool, env_spec: bool, shadow: bool = False, dual_lobe: bool = False,
                    thickness: bool = False, roughness_map: bool = False, normal_map: bool = False,
                    translucency_map: bool = False, cube_env: bool = False, regions: bool = False) -> tuple:
        """The skin program's cache key: the 5 values of S4, plus the three map flags when a map is drawn (S7), plus
        those and `CUBE_ENV` when the cube is (S5; only with `env_spec`), plus those, the cube flag and `REGIONS` when
        region materials are (S6) - 5, 8, 9 or 10 values, so every key of a frame without the cube or regions stays as
        it was."""
        key = (bool(albedo_map), bool(env_spec), bool(shadow), bool(dual_lobe), bool(thickness) and bool(shadow))
        maps = (bool(roughness_map), bool(normal_map), bool(translucency_map))
        cube = bool(cube_env) and bool(env_spec)
        if regions:
            return key + maps + (cube, True)
        if cube:
            return key + maps + (True,)
        return key + maps if any(maps) else key

    def program(self, albedo_map: bool, env_spec: bool, shadow: bool = False, dual_lobe: bool = False,
                thickness: bool = False, roughness_map: bool = False, normal_map: bool = False,
                translucency_map: bool = False, cube_env: bool = False, regions: bool = False):
        from pyglet.graphics.shader import Shader, ShaderProgram

        from .gl_render_store import GLRenderStore, _register_sampler_buffer_uniform

        key = self.program_key(albedo_map, env_spec, shadow, dual_lobe, thickness, roughness_map, normal_map,
                               translucency_map, cube_env, regions)
        program = self.programs.get(key)
        if program is None:
            _register_sampler_buffer_uniform()
            if shadow:
                from .lookdev_shadow import register_shadow_sampler_uniform

                register_shadow_sampler_uniform()
            attributes = GLRenderStore.program().attributes
            locations = {"position": attributes["position"]["location"], "normal": attributes["normal"]["location"]}
            program = ShaderProgram(*(Shader(src, kind) for src, kind in skin_sources(locations, *key)))
            self.programs[key] = program
        return program

    def draw(self, render_mesh, look: LookDraw, frame: dict, shadow=None, dual_lobe: bool = False,
             thickness: bool = False, maps: bool = False, cube=None, regions: bool = False) -> bool:
        """Draw one object. False = nothing drawn (no VertexList / camera yet, or a Ghost): the caller draws it with the
        Worklight. `shadow` (AD-039 S1): a rendered `KeyShadow` the object receives (the `SHADOW` variant), else None;
        `dual_lobe` (S3): the `DUAL_LOBE` variant; `thickness` (S4): the `THICKNESS` variant, only with a shadow;
        `maps` (S7): the LookDraw's maps that load are drawn (one define each) - on a mesh with triangle UVs;
        `cube` (S5): a built `EnvCube` the studio's reflection reads (the `CUBE_ENV` variant, with `env_spec`), else
        None; `regions` (S6): the LookDraw's region materials by the RenderMesh's triangle slots (the `REGIONS`
        variant, when the look has regions and the store holds slots), else the object's material everywhere."""
        from pyglet import gl

        from .gl_render_store import GLRenderStore

        store = render_mesh.store
        vlist = store.vertex_list() if hasattr(store, "vertex_list") else None
        camera = store.uniform_data("camera_uniforms") if vlist is not None else []
        if vlist is None or len(camera) != 32 or getattr(store, "alpha", 1.0) < 1.0:
            return False
        paths = look.map_paths() if maps else {}
        regions = bool(regions) and bool(look.regions) and hasattr(store, "bind_triangle_materials") \
            and store.bind_triangle_materials(REGION_UNIT)
        albedo = look.albedo_source(regions)
        uvs = (albedo is not None or bool(paths)) and store.bind_triangle_uvs(UV_UNIT)
        texture = GLRenderStore.texture_binding(albedo) if uvs else None
        bound_maps = {}
        for kind, path in paths.items() if uvs else ():
            image = GLRenderStore.texture(path)
            if image is not None:
                bound_maps[kind] = (image.target, image.id)
        if uvs and texture is None and not bound_maps:
            GLRenderStore.unbind_triangle_uvs(UV_UNIT)
            uvs = False
        shadow = shadow if shadow is not None and shadow.ready else None
        thickness = bool(thickness) and shadow is not None
        cube = cube if cube is not None and cube.ready and self.env_spec else None
        program = self.program(texture is not None, self.env_spec, shadow is not None, dual_lobe, thickness,
                               "roughness" in bound_maps, "normal" in bound_maps, "translucency" in bound_maps,
                               cube is not None, regions)
        program.use()
        active = program.uniforms  # pyglet builds this dict on every access: once per draw
        model = store.uniform_data("model_uniforms")
        set_uniforms(program, frame, active)
        set_uniforms(program, look.uniforms(), active)
        set_uniforms(program, {"u_view": tuple(camera[0:16]), "u_proj": tuple(camera[16:32]),
                               "u_model": tuple(model) if len(model) == 16 else _IDENTITY_4,
                               "u_triangle_uvs": UV_UNIT, "u_albedo": ALBEDO_UNIT}, active)
        if regions:
            set_uniforms(program, look.slot_uniforms(), active)
        if texture is not None:
            gl.glActiveTexture(gl.GL_TEXTURE0 + ALBEDO_UNIT)
            gl.glBindTexture(*texture)
            gl.glActiveTexture(gl.GL_TEXTURE0)
        if bound_maps:
            set_uniforms(program, look.map_uniforms(), active)
            for kind, binding in bound_maps.items():
                gl.glActiveTexture(gl.GL_TEXTURE0 + MAP_UNITS[kind])
                gl.glBindTexture(*binding)
            gl.glActiveTexture(gl.GL_TEXTURE0)
        if shadow is not None:
            set_uniforms(program, shadow.uniforms(), active)
            shadow.bind(SHADOW_UNIT)
            if thickness:
                shadow.bind_raw(SHADOW_RAW_UNIT)
        seamless = None
        if cube is not None:
            set_uniforms(program, cube.uniforms(), active)
            cube.bind(CUBE_UNIT)
            seamless = bool(gl.glIsEnabled(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS))
            gl.glEnable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
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
        for kind, (target, _name) in bound_maps.items():
            gl.glActiveTexture(gl.GL_TEXTURE0 + MAP_UNITS[kind])
            gl.glBindTexture(target, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        if uvs:
            GLRenderStore.unbind_triangle_uvs(UV_UNIT)
        if shadow is not None:
            shadow.unbind(SHADOW_UNIT)
            if thickness:
                shadow.unbind_raw(SHADOW_RAW_UNIT)
        if cube is not None:
            cube.unbind(CUBE_UNIT)
            if not seamless:
                gl.glDisable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
        if regions:
            GLRenderStore.unbind_triangle_uvs(REGION_UNIT)  # a buffer texture like the UVs: the same unbind
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
        if self.shadow is not None:
            self.shadow.release()
            self.shadow = None
        if self.cube is not None:
            self.cube.release()
            self.cube = None
        if self._background is not None:
            import ctypes

            from pyglet import gl

            self._background.delete()
            gl.glDeleteVertexArrays(1, ctypes.byref(gl.GLuint(self._vao)))
            self._background, self._vao = None, None


def read_back_buffer():
    """AD-038 §18 (LD-2, "Bild speichern"): the current framebuffer's viewport rectangle as an `(h, w, 4)` uint8 RGBA
    array, top row first. Reads the back buffer (`glReadPixels`), binds nothing (no FBO, I-4); the pack alignment it
    sets for the read is restored."""
    import ctypes

    import numpy as np
    from pyglet import gl

    rect = (gl.GLint * 4)()
    gl.glGetIntegerv(gl.GL_VIEWPORT, rect)
    x, y, width, height = (int(v) for v in rect)
    out = np.empty((height, width, 4), np.uint8)
    alignment = gl.GLint()
    gl.glGetIntegerv(gl.GL_PACK_ALIGNMENT, ctypes.byref(alignment))
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(x, y, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, out.ctypes.data_as(ctypes.c_void_p))
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, alignment.value)
    out = out[::-1].copy()
    out[..., 3] = 255  # the default framebuffer's alpha is not part of the picture
    return out
