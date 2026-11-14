"""P1b GL side: the refraction variants on top of the unchanged P1 lab (2026-11-14).

Everything here derives from P1's classes; no P1 module changes:
- `RefractionState(LabState)` adds `refraction` ("V1" / "V2" / "V3"); V1 is P1 exactly.
- `RefractionStore(EyeLabStore)`: in V2 / V3 (techniques T-B ... T-D) the cornea entry is drawn by the refractive
  opaque pass and the iris entry is not drawn (the cornea pass shows the iris through the refraction); in every other
  case the store does what `EyeLabStore` does, so V1 renders P1 pixel for pixel (tested).
- `RefractionRenderer(EyeLabRenderer)`: the cornea pass (`draw_cornea`) with its explicit GL state - depth test on,
  depth write on, blending off, back faces culled - and everything P1's renderer does.
- `build_scene`: P1's `lab_scene.build_scene` with these two types (the same parts, entries and draw order).
- `RefractionParityPass`: the ray functions of `refraction_shaders.REFRACTION_LIB_SRC` per fragment, read back.

T-A (the production Worklight) has no refraction: with T-A every variant draws P1's T-A.
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

from . import cornea_optics as co
from . import eye_geometry as geo
from . import eye_math as em
from . import gl_lab
from . import lab_scene
from . import lab_state as ls
from . import refraction_shaders as rs
from . import shaders

REFRACTION_VARIANTS = co.VARIANTS
#: The iris image's colour outside the visible limbus (`eye_geometry.iris_image`), decoded: the dark end of the limbal
#: tissue blend.
LIMBUS_ALBEDO = tuple(float(v) for v in em.srgb_decode((0.10, 0.11, 0.13)))
#: The iris image's pupil colour (`eye_geometry.iris_image`), decoded.
PUPIL_ALBEDO = tuple(float(v) for v in em.srgb_decode((0.012, 0.012, 0.012)))


@dataclass
class RefractionState(ls.LabState):
    refraction: str = "V1"

    @property
    def refraction_active(self) -> bool:
        return self.refraction in ("V2", "V3") and self.technique != "T-A"

    @property
    def variant(self) -> str:
        return f"{self.technique}_{self.refraction if self.refraction_active else self.cornea}"


def geometry_uniforms(g: co.CorneaGeometry = co.GEOMETRY) -> dict:
    return {
        "u_ant_centre": (0.0, 0.0, g.anterior_centre_z), "u_ant_radius": g.anterior_radius,
        "u_post_centre": (0.0, 0.0, g.posterior_centre_z), "u_post_radius": g.posterior_radius,
        "u_cap_z": g.limbus_z, "u_angle": g.angle, "u_iris_a": g.iris_a, "u_iris_b": g.iris_b,
        "u_iris_radius": g.iris_radius, "u_pupil_radius": g.pupil_radius, "u_limbus_radius": g.limbus_radius,
    }


class RefractionStore(gl_lab.EyeLabStore):
    def draw(self, group: str = "mesh") -> None:
        lab = self.lab
        if isinstance(lab, RefractionRenderer) and lab.state.refraction_active and self.part == "cornea":
            if lab.part_visible("cornea"):
                lab.draw_cornea(self, group)
            return
        super().draw(group)  # the iris entry is hidden in V2 / V3 by `RefractionRenderer.part_visible`


class RefractionRenderer(gl_lab.EyeLabRenderer):
    def __init__(self, state: RefractionState, cache_dir=None, iris_png: Path | None = None) -> None:
        super().__init__(state, cache_dir)
        self.iris_png = iris_png
        self.cornea_programs: dict = {}
        #: Draw the ray-class map instead of colour (red iris, green pupil, blue limbal tissue): the GPU / CPU check.
        self.debug_kind = False
        #: Test hook: keep drawing the iris mesh in V2 / V3 (the opaque cornea must hide it completely).
        self.keep_iris_mesh = False

    def part_visible(self, part: str) -> bool:
        if part == "iris" and self.state.refraction_active and not self.keep_iris_mesh:
            return False
        return super().part_visible(part)

    def cornea_program(self, tech: int, variant: int, locations: dict) -> gl_lab.LabProgram:
        key = (tech, variant, self.debug_kind)
        if key not in self.cornea_programs:
            self.cornea_programs[key] = gl_lab.LabProgram(rs.cornea_sources(locations, tech, variant,
                                                                             self.debug_kind))
        return self.cornea_programs[key]

    def draw_cornea(self, store: RefractionStore, group: str) -> None:
        gl = self.gl
        vlist = store.vertex_list(group)
        if vlist is None or self.iris_png is None:
            return
        s = self.state
        tech = shaders.TECH_IDS[s.technique]
        attributes = GLRenderStore.program().attributes
        locations = {"position": attributes["position"]["location"], "normal": attributes["normal"]["location"]}
        program = self.cornea_program(tech, rs.VARIANT_IDS[s.refraction], locations)
        program.use()
        camera = store.uniform_data("camera_uniforms")
        model = store.uniform_data("model_uniforms")
        values = self.common_uniforms()
        values.update(geometry_uniforms())
        values.update({
            "u_view": camera[0:16], "u_proj": camera[16:32], "u_model": model if len(model) == 16 else gl_lab._IDENTITY,
            "u_eye": self.camera.eye(), "u_f0": (s.cornea_f0,) * 3, "u_roughness": s.cornea_roughness,
            "u_sclera_albedo": s.material("sclera").albedo, "u_limbus_albedo": LIMBUS_ALBEDO,
            "u_pupil_albedo": PUPIL_ALBEDO,
            "u_iris_texture": grs._TEXTURE_UNIT,
        })
        image = GLRenderStore.texture(str(self.iris_png))
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
        # Opaque: the cornea is the front surface of the eye; it writes depth like any opaque part and does not blend.
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
        for program in self.cornea_programs.values():
            program.delete()
        self.cornea_programs.clear()
        super().release()


def build_scene(state: RefractionState, out_dir: Path, cache_dir: Path | None, width: int,
                height: int) -> lab_scene.Scene:
    """`lab_scene.build_scene` with `RefractionStore` / `RefractionRenderer`: the same parts, colours, entries,
    insertion order (the cornea a Ghost entry, drawn last), camera and preset."""
    meshes = geo.build_parts()
    iris_png = geo.write_iris_png(Path(out_dir) / "iris.png")
    renderer = RefractionRenderer(state, cache_dir, iris_png)
    viewport = Viewport(meshes["grey"], store_type=RefractionStore)
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
    scene = lab_scene.Scene(viewport, camera, renderer, meshes, iris_png)
    scene.apply_view(state.view)
    return scene


class RefractionParityPass(gl_lab.ParityPass):
    """P1's parity pass with the refraction program (inputs: three vec4 per sample, output one vec4)."""

    def __init__(self, gl, res: pg.Resources) -> None:
        super().__init__(gl, res)
        self.program.delete()
        self.program = gl_lab.LabProgram(rs.parity_sources())

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
            values = {"u_inputs": pg.SAMPLE_UNIT, "u_width": self.WIDTH, "u_count": count,
                      "u_func": rs.PARITY_FUNCS[func]}
            values.update(geometry_uniforms())
            self.program.set(values)
            gl.glBindVertexArray(self.vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glReadPixels(0, 0, self.WIDTH, rows, gl.GL_RGBA, gl.GL_FLOAT, out.ctypes.data)
        return out.reshape(-1, 4)[:count].astype(np.float64)
