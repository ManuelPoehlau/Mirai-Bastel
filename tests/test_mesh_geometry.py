"""mesh_geometry: Bounds/Center/Radius/Face-Typen-Queries (AD-008).

Logik 1:1 aus `experiments/mirai_bastel_integration_lab/adapters/
obj_to_core.py` portiert — diese Tests prüfen die Zielumgebung (`mirai`),
nicht die Logik neu; siehe dortige Test-Suite für die ursprüngliche
Verifikation gegen das echte Head-Basemesh.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from mirai.mesh_geometry import face_type_counts, mesh_bounds, mesh_center_and_radius, mesh_debug_report
from mirai.scene_factory import create_cube
from core import Mesh


class MeshBoundsTests(unittest.TestCase):
    def test_bounds_of_unit_cube(self):
        mesh = create_cube(size=2.0)
        lo, hi = mesh_bounds(mesh)
        self.assertEqual(lo, (-1.0, -1.0, -1.0))
        self.assertEqual(hi, (1.0, 1.0, 1.0))

    def test_bounds_of_empty_mesh_is_origin(self):
        lo, hi = mesh_bounds(Mesh())
        self.assertEqual(lo, (0.0, 0.0, 0.0))
        self.assertEqual(hi, (0.0, 0.0, 0.0))

    def test_center_and_radius_of_cube(self):
        mesh = create_cube(size=2.0)
        center, radius = mesh_center_and_radius(mesh)
        self.assertEqual(center, (0.0, 0.0, 0.0))
        # Bounding sphere radius = distance center -> corner = sqrt(3) for a unit half-extent cube.
        self.assertAlmostEqual(radius, 3 ** 0.5, places=6)

    def test_center_and_radius_of_offset_cube(self):
        mesh = create_cube(size=2.0)
        # Manually offset all vertices to check center tracks the actual geometry, not the origin.
        for vid in mesh.all_vertex_ids():
            x, y, z = mesh.vertex_position(vid)
            mesh.set_vertex_position(vid, (x + 5.0, y, z))
        center, _radius = mesh_center_and_radius(mesh)
        self.assertAlmostEqual(center[0], 5.0, places=6)


class FaceTypeCountsTests(unittest.TestCase):
    def test_cube_is_all_quads(self):
        mesh = create_cube(size=2.0)
        counts = face_type_counts(mesh)
        self.assertEqual(counts, {"tri": 0, "quad": 6, "ngon": 0})


class MeshDebugReportTests(unittest.TestCase):
    def test_report_contains_counts(self):
        mesh = create_cube(size=2.0)
        report = mesh_debug_report("cube", mesh)
        self.assertIn("cube", report)
        self.assertIn("Vertices : 8", report)
        self.assertIn("Faces    : 6", report)


if __name__ == "__main__":
    unittest.main()
