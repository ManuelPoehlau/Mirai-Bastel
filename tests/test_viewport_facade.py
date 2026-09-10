"""Viewport-Fassade: Integration RenderMesh + Overlay + Camera-Bindung.

Gate 5 (Viewport Production).
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core import Selection, SelectionMode
from mirai.scene_factory import create_cube
from mirai.viewport.camera import OrbitCamera
from viewport import Viewport


class ViewportFacadeTests(unittest.TestCase):
    def setUp(self):
        self.mesh = create_cube()
        self.selection = Selection()
        self.viewport = Viewport(self.mesh, selection=self.selection)

    def test_initial_build_allocates_resources(self):
        ids = self.viewport.resource_ids()
        self.assertIn("positions", ids)
        self.assertIn("normals", ids)
        self.assertIn("indices", ids)
        self.assertIn("highlight_flags", ids)

    def test_uses_provided_selection_instance(self):
        self.assertIs(self.viewport.selection, self.selection)
        self.assertIs(self.viewport.overlay.selection, self.selection)

    def test_creates_own_selection_if_none_given(self):
        vp = Viewport(create_cube())
        self.assertIsNotNone(vp.selection)

    def test_bind_camera_allocates_camera_uniforms_immediately(self):
        cam = OrbitCamera()
        self.viewport.bind_camera(cam)
        self.viewport.sync()
        self.assertIn("camera_uniforms", self.viewport.resource_ids())

    def test_on_vertices_moved_triggers_partial_update(self):
        vid = self.mesh.all_vertex_ids()[0]
        old = self.mesh.vertex_position(vid)
        self.mesh.set_vertex_position(vid, (old[0] + 1.0, old[1], old[2]))

        before_ids = self.viewport.resource_ids()
        self.viewport.on_vertices_moved({vid})
        self.viewport.sync()

        self.assertEqual(self.viewport.resource_ids(), before_ids)
        self.assertGreater(self.viewport.benchmark_counters["vertex_updates"], 0)

    def test_on_topology_changed_triggers_structural_rebuild(self):
        before_ids = self.viewport.resource_ids()
        eid = self.mesh.all_edge_ids()[0]
        self.mesh.split_edge(eid)
        self.viewport.on_topology_changed()
        self.viewport.sync()
        self.assertNotEqual(self.viewport.resource_ids(), before_ids)

    def test_on_selection_changed_does_not_affect_base_geometry(self):
        before_ids = self.viewport.resource_ids()
        vid = self.mesh.all_vertex_ids()[0]
        self.selection.mode = SelectionMode.VERTEX
        self.selection.set({vid})
        self.viewport.on_selection_changed()
        self.viewport.sync()
        self.assertEqual(self.viewport.resource_ids(), before_ids)
        self.assertEqual(
            self.viewport.benchmark_counters.get("geometry_uploads", 0), 0
        )

    def test_on_camera_changed_isolated(self):
        cam = OrbitCamera()
        self.viewport.bind_camera(cam)
        self.viewport.sync()
        before_ids = self.viewport.resource_ids()

        cam.orbit(0.1, 0.0)
        self.viewport.on_camera_changed()
        self.viewport.sync()

        self.assertEqual(self.viewport.resource_ids(), before_ids)

    def test_render_is_safe_noop_without_gl_backend(self):
        # Darf nicht raisen, auch ohne gebundene Kamera/GL-Backend.
        self.viewport.render()


if __name__ == "__main__":
    unittest.main()
