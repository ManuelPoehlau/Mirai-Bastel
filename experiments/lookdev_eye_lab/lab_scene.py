"""The Eye Proof scene on the production viewport: `Viewport(store_type=EyeLabStore)`, the eye parts and reference
spheres as entries, an `OrbitCamera`, the camera presets and the framing (needs a GL context once synced).

Draw order is the viewport's own (AD-021 RD-1): the edit mesh (the grey sphere), the opaque entries in insertion order
(sclera, iris, chrome), then the Ghost entries - the cornea is a Ghost entry (alpha < 1), so it is drawn last, which is
what the C2 / C3 shells need, and in T-A it shows as the production Ghost.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from mirai.viewport.camera import OrbitCamera
from viewport.viewport import Viewport

from . import eye_geometry as geo
from . import eye_math as em
from . import lab_state as ls
from .gl_lab import EyeLabRenderer, EyeLabStore

#: Interactive framing: the eye and both reference spheres.
OVERVIEW_DISTANCE = 7.5
#: Share of the frame the sclera disc covers in the close-up and in the probe (audit §5.6: about 50 %).
CLOSE_UP_COVERAGE = 0.5


@dataclass
class Scene:
    viewport: Viewport
    camera: OrbitCamera
    renderer: EyeLabRenderer
    meshes: dict
    iris_png: Path

    def apply_view(self, name: str, distance: float | None = None) -> None:
        yaw, pitch = ls.VIEWS[name]
        self.camera.set_view(math.radians(yaw), math.radians(pitch))
        if distance is not None:
            self.camera.distance = distance
        self.renderer.state.view = name

    def set_aspect(self, width: int, height: int) -> None:
        self.viewport.on_camera_changed(aspect=width / height)

    def camera_moved(self) -> None:
        self.camera.camera_revision += 1
        self.viewport.on_camera_changed()

    def release(self) -> None:
        for key in list(self.viewport.object_entries):
            self.viewport.remove_object_entry(key)
        self.viewport.render_mesh.store.release()
        self.renderer.release()


def close_up_distance(width: int, height: int, fov_degrees: float = OrbitCamera.fov_degrees) -> float:
    return em.distance_for_coverage(CLOSE_UP_COVERAGE, geo.SCLERA_RADIUS, fov_degrees, width, height)


def build_scene(state: ls.LabState, out_dir: Path, cache_dir: Path | None, width: int, height: int) -> Scene:
    """Requires a current GL context (the stores build their VertexLists at the first `sync()`)."""
    meshes = geo.build_parts()
    iris_png = geo.write_iris_png(Path(out_dir) / "iris.png")
    renderer = EyeLabRenderer(state, cache_dir)
    viewport = Viewport(meshes["grey"], store_type=EyeLabStore)
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
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=OVERVIEW_DISTANCE)
    renderer.camera = camera
    viewport.bind_camera(camera)
    viewport.on_camera_changed(aspect=width / height)
    scene = Scene(viewport, camera, renderer, meshes, iris_png)
    scene.apply_view(state.view)
    return scene

