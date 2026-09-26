"""Application OBJ scene + framing (WP-06 Slice B1).

`examples/` must be on `sys.path` for the shared OBJ loader (AD-007/AD-008),
so this test's local sys.path setup mirrors
`tests/test_scene_factory_obj_import.py` rather than `tests/_bootstrap.py`,
keeping the rest of `tests/` free of an `examples/` dependency.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import tests._bootstrap  # noqa: F401

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES_DIR = _REPO_ROOT / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from mirai.application import Application
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.viewport import OrbitCamera

_HEAD_ASSET = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"


@unittest.skipUnless(_HEAD_ASSET.is_file(), "Head-Basemesh-Asset nicht gefunden (examples/meshes/)")
class ApplicationObjSceneTests(unittest.TestCase):
    def test_init_scene_obj_loads_head_basemesh(self):
        app = Application()
        app.init_scene("obj", obj_path=_HEAD_ASSET)
        faces = app.scene.mesh.all_face_ids()
        self.assertEqual(len(faces), 324)
        for fid in faces:
            self.assertEqual(len(app.scene.mesh.face_vertices(fid)), 4)

    def test_init_scene_obj_preserves_scene_identity(self):
        app = Application()
        scene_before, selection_before, history_before = (
            app.scene, app.selection, app.history,
        )
        app.init_scene("obj", obj_path=_HEAD_ASSET)
        self.assertIs(app.scene, scene_before)
        self.assertIs(app.selection, selection_before)
        self.assertIs(app.history, history_before)

    def test_init_scene_obj_binds_viewport_to_new_mesh(self):
        app = Application()
        app.init_scene("obj", obj_path=_HEAD_ASSET)
        self.assertIs(app.viewport.render_mesh.mesh, app.scene.mesh)

    def test_init_scene_obj_without_path_raises(self):
        app = Application()
        with self.assertRaises(ValueError):
            app.init_scene("obj")

    def test_frame_scene_centers_camera_on_mesh(self):
        app = Application()
        app.init_scene("obj", obj_path=_HEAD_ASSET)
        positions_before = {
            vid: app.scene.mesh.vertex_position(vid)
            for vid in app.scene.mesh.all_vertex_ids()
        }
        history_len_before = len(app.history)

        app.frame_scene()

        center, radius = mesh_center_and_radius(app.scene.mesh)
        reference_camera = OrbitCamera()
        reference_camera.frame_on_bounds(center, radius)

        self.assertEqual(app.camera.target, center)
        self.assertEqual(app.camera.distance, reference_camera.distance)
        for vid in app.scene.mesh.all_vertex_ids():
            self.assertEqual(app.scene.mesh.vertex_position(vid), positions_before[vid])
        self.assertEqual(len(app.history), history_len_before)
        self.assertGreater(radius, 0.0)

    def test_frame_scene_before_init_scene_is_noop(self):
        app = Application()
        target_before = app.camera.target
        distance_before = app.camera.distance
        app.frame_scene()
        self.assertEqual(app.camera.target, target_before)
        self.assertEqual(app.camera.distance, distance_before)


if __name__ == "__main__":
    unittest.main()
