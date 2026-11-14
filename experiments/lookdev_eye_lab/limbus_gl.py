"""P1c GL side: the soft limbus on top of the unchanged P1b lab (2026-11-14).

Everything derives from P1b's classes; no P1 / P1b module changes:
- `LimbusState(RefractionState)`: refraction V2 by default (Manu: "P1b V2 as the primary baseline", V3 selectable),
  the level L0 ... L3, the colour source (shader / image), the asymmetry switch (default off) and the parameters.
- `LimbusStore(RefractionStore)`: at L1 ... L3 (with V2 / V3 and T-B ... T-D) the sclera entry is drawn by the P1c
  sclera pass; everything else as P1b.
- `LimbusRenderer(RefractionRenderer)`: at L0 - and whenever refraction is off, or the ray-class map is on - every
  call goes to P1b's own code, so **L0 is P1b pixel for pixel** (tested); at L1 ... L3 the cornea and the sclera use the
  `limbus_shaders` programs with P1b's explicit GL state (opaque: depth test, depth write, no blending, back faces
  culled).
- `build_scene`: P1b's builder with these types, plus the image's limbal colour (`limbus_model.image_limbal_colour`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from lookdev_gpu_probe import probe_gl_caps as pg
from mirai.viewport.camera import OrbitCamera
from viewport import gl_render_store as grs
from viewport.gl_render_store import GLRenderStore
from viewport.viewport import Viewport

from . import eye_geometry as geo
from . import eye_math as em
from . import gl_lab
from . import iris_source
from . import lab_scene
from . import lab_state as ls
from . import limbus_model as lm
from . import limbus_shaders as lsh
from . import refraction_gl as rg
from . import shaders


@dataclass
class LimbusState(rg.RefractionState):
    refraction: str = "V2"
    limbus_level: str = "L0"
    colour_source: str = "shader"
    shader_colour: str = "P1b dark"
    band_mm: float = 1.0
    strength: float = 1.0
    normal_mm: float = 0.5
    falloff: float = 4.0
    asym: bool = False
    overlap_mm: float = 0.0

    @property
    def level(self) -> int:
        return lm.LEVELS.index(self.limbus_level)

    @property
    def limbus_active(self) -> bool:
        return self.refraction_active and self.level > 0

    @property
    def params(self) -> lm.LimbusParams:
        return lm.LimbusParams(self.band_mm, self.strength, self.normal_mm, self.falloff, self.asym,
                               overlap_mm=self.overlap_mm)

    @property
    def variant(self) -> str:
        base = super().variant
        if not self.limbus_active:
            return base
        return (f"{base}_{self.limbus_level}" + (f"_ov{self.overlap_mm:g}" if self.overlap_mm > 0 else "")
                + ("_asym" if self.asym else ""))


class LimbusStore(rg.RefractionStore):
    def draw(self, group: str = "mesh") -> None:
        lab = self.lab
        if (isinstance(lab, LimbusRenderer) and self.part == "sclera" and lab.limbus_drawn()
                and lab.part_visible("sclera")):
            lab.draw_sclera(self, group)
            return
        super().draw(group)


class LimbusRenderer(rg.RefractionRenderer):
    def __init__(self, state: LimbusState, cache_dir=None, iris_png: Path | None = None, iris_fit=None,
                 image_colour=None, image_note: str = "") -> None:
        super().__init__(state, cache_dir, iris_png, iris_fit)
        #: Linear-light mean colour of the iris image's outer ring (None: not available, the shader colour is used).
        self.image_colour = image_colour
        self.image_note = image_note
        self.limbus_programs: dict = {}

    def limbus_drawn(self) -> bool:
        return self.state.limbus_active and not self.debug_kind

    def limbal_albedo(self) -> tuple:
        s = self.state
        if s.colour_source == "image" and self.image_colour is not None:
            return self.image_colour
        return tuple(float(v) for v in em.srgb_decode(lm.SHADER_COLOURS[s.shader_colour]))

    def limbus_uniforms(self) -> dict:
        p = self.state.params
        return {"u_band": p.band, "u_strength": p.strength, "u_normal_w": p.normal_w, "u_falloff": p.falloff,
                "u_asym": p.asym_units, "u_overlap": p.overlap_units}

    def limbus_program(self, part: str, tech: int, variant: int, level: int, locations: dict) -> gl_lab.LabProgram:
        fit = self.iris_fit is not None
        key = (part, tech, variant, level, fit)
        if key not in self.limbus_programs:
            sources = (lsh.cornea_sources(locations, tech, variant, level, fit) if part == "cornea"
                       else lsh.sclera_sources(locations, tech, level, fit))
            self.limbus_programs[key] = gl_lab.LabProgram(sources)
        return self.limbus_programs[key]

    def draw_cornea(self, store, group: str) -> None:
        if not self.limbus_drawn():
            super().draw_cornea(store, group)  # L0: P1b's own pass
            return
        self._limbus_pass(store, group, "cornea")

    def draw_sclera(self, store, group: str) -> None:
        self._limbus_pass(store, group, "sclera")

    def _limbus_pass(self, store, group: str, part: str) -> None:
        gl = self.gl
        vlist = store.vertex_list(group)
        if vlist is None or self.iris_png is None:
            return
        s = self.state
        tech = shaders.TECH_IDS[s.technique]
        attributes = GLRenderStore.program().attributes
        locations = {"position": attributes["position"]["location"], "normal": attributes["normal"]["location"]}
        program = self.limbus_program(part, tech, rg.rs.VARIANT_IDS[s.refraction], s.level, locations)
        program.use()
        camera = store.uniform_data("camera_uniforms")
        model = store.uniform_data("model_uniforms")
        values = self.common_uniforms()
        values.update(rg.geometry_uniforms())
        values.update(self.limbus_uniforms())
        if part == "cornea":
            surface = {"u_f0": (s.cornea_f0,) * 3, "u_roughness": s.cornea_roughness}
        else:
            material = s.material("sclera")
            surface = {"u_f0": material.f0, "u_roughness": material.roughness, "u_spec_weight": material.spec_weight}
        values.update(surface)
        values.update({
            "u_view": camera[0:16], "u_proj": camera[16:32], "u_model": model if len(model) == 16 else gl_lab._IDENTITY,
            "u_eye": self.camera.eye(), "u_sclera_albedo": s.material("sclera").albedo,
            "u_limbus_albedo": self.limbal_albedo(), "u_pupil_albedo": rg.PUPIL_ALBEDO,
            "u_iris_texture": grs._TEXTURE_UNIT,
        })
        if self.iris_fit is not None:
            values.update(self.iris_fit.uniforms())
        image = GLRenderStore.texture(str(self.iris_png))
        if image is None:
            return
        gl.glActiveTexture(gl.GL_TEXTURE0 + grs._TEXTURE_UNIT)
        gl.glBindTexture(image.target, image.id)
        if tech == shaders.TECH_IDS["T-C"]:
            texture = self.env_cube.ensure(s)
            gl.glActiveTexture(gl.GL_TEXTURE0 + gl_lab.ENV_UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, texture)
            (gl.glEnable if s.seamless else gl.glDisable)(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
            values.update({"u_env": gl_lab.ENV_UNIT, "u_env_last": float(self.env_cube.last_level)})
        gl.glActiveTexture(gl.GL_TEXTURE0)
        program.set(values)
        # Opaque, the same explicit state as P1b's cornea pass.
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)
        gl.glDepthMask(gl.GL_TRUE)
        gl.glDisable(gl.GL_BLEND)
        gl.glEnable(gl.GL_CULL_FACE)
        gl.glCullFace(gl.GL_BACK)
        vlist.draw(gl.GL_TRIANGLES)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glActiveTexture(gl.GL_TEXTURE0 + grs._TEXTURE_UNIT)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        if tech == shaders.TECH_IDS["T-C"]:
            gl.glActiveTexture(gl.GL_TEXTURE0 + gl_lab.ENV_UNIT)
            gl.glBindTexture(gl.GL_TEXTURE_CUBE_MAP, 0)
            gl.glDisable(gl.GL_TEXTURE_CUBE_MAP_SEAMLESS)
        gl.glActiveTexture(gl.GL_TEXTURE0)

    def release(self) -> None:
        for program in self.limbus_programs.values():
            program.delete()
        self.limbus_programs.clear()
        super().release()


def build_scene(state: LimbusState, out_dir: Path, cache_dir: Path | None, width: int,
                height: int) -> lab_scene.Scene:
    """`refraction_gl.build_scene` with `LimbusStore` / `LimbusRenderer` (the same parts, entries, order, camera)."""
    source = iris_source.confirm_loadable(iris_source.choose(out_dir), out_dir)  # the same source as P1 / P1b
    meshes = geo.build_parts(*lab_scene.iris_mesh_mapping(source))
    iris_png = source.path
    colour, note = lm.image_limbal_colour(iris_png, source.fit)
    renderer = LimbusRenderer(state, cache_dir, iris_png, source.fit, colour, note)
    viewport = Viewport(meshes["grey"], store_type=LimbusStore)
    viewport.set_edit_base_color(ls.WORKLIGHT_COLOURS["grey"])
    for part in ("sclera", "iris", "chrome", "cornea"):
        viewport.set_object_entry(
            part, meshes[part], ls.WORKLIGHT_COLOURS[part],
            alpha=ls.CORNEA_GHOST_ALPHA if part == "cornea" else 1.0,
            texture=str(iris_png) if part == "iris" else None,
        )
    stores = {"grey": viewport.render_mesh.store}
    stores.update({part: entry.store for part, entry in viewport.object_entries.items()})
    for part, store in stores.items():
        store.part = part
        store.lab = renderer
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=lab_scene.OVERVIEW_DISTANCE)
    renderer.camera = camera
    viewport.bind_camera(camera)
    viewport.on_camera_changed(aspect=width / height)
    scene = lab_scene.Scene(viewport, camera, renderer, meshes, iris_png, source)
    scene.apply_view(state.view)
    return scene


def describe(state: LimbusState, renderer: LimbusRenderer | None = None) -> list[str]:
    """P1c HUD / probe lines."""
    p = state.params
    if not state.refraction_active:
        active = " (inactive: needs V2 / V3 and T-B ... T-D)"
    elif state.level == 0:
        active = " (P1b as is)"
    else:
        active = ""
    source = state.colour_source
    if source == "image":
        if renderer is not None and renderer.image_colour is None:
            source += f" -> shader ({renderer.image_note})"
        elif renderer is not None:
            source += f" ({renderer.image_note})"
    else:
        source += f" '{state.shader_colour}'"
    return [f"limbus {state.limbus_level}{active}   colour {source}   overlap all round "
            f"{p.overlap_mm:.2f} mm   asymmetry {'ON' if p.asym else 'off'} (+{p.asym_mm:.2f} mm top / bottom)",
            f"band {p.band_mm:.2f} mm   strength {p.strength:.2f}   normal blend +-{p.normal_mm:.2f} mm   "
            f"translucency falloff {p.falloff:.2f}"]


class LimbusParityPass(gl_lab.ParityPass):
    """The ray-function parity pass with the P1c library (inputs: three vec4 per sample, output one vec4)."""

    def __init__(self, gl, res: pg.Resources, params: lm.LimbusParams) -> None:
        super().__init__(gl, res)
        self.program.delete()
        self.program = gl_lab.LabProgram(lsh.parity_sources())
        self.params = params

    def run(self, func: str, inputs: np.ndarray) -> np.ndarray:
        gl = self.gl
        data = np.ascontiguousarray(inputs, dtype=np.float32).reshape(-1, 12)
        count = len(data)
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
            p = self.params
            values = {"u_inputs": pg.SAMPLE_UNIT, "u_width": self.WIDTH, "u_count": count,
                      "u_func": lsh.PARITY_FUNCS[func], "u_band": p.band, "u_strength": p.strength,
                      "u_normal_w": p.normal_w, "u_falloff": p.falloff, "u_asym": p.asym_units,
                      "u_overlap": p.overlap_units}
            values.update(rg.geometry_uniforms())
            self.program.set(values)
            gl.glBindVertexArray(self.vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glReadPixels(0, 0, self.WIDTH, rows, gl.GL_RGBA, gl.GL_FLOAT, out.ctypes.data)
        return out.reshape(-1, 4)[:count].astype(np.float64)
