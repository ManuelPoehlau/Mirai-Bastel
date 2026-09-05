"""Viewport-Picking: Tests für `mirai.viewport.picking` (window-/GPU-frei).

Migriert aus dem Experiment test_camera_picking.py. Verwendet die
Cube-Factory (`mirai.scene_factory.create_cube`), damit die Tests gegen
denselben Produktions-Pfad laufen wie die Application.
"""

from __future__ import annotations

import math
import unittest

import tests._bootstrap  # noqa: F401

from mirai.scene_factory import create_cube
from mirai.viewport.camera import OrbitCamera
from mirai.viewport.picking import (
    _point_segment_distance,
    _ray_triangle_intersection,
    pick_face,
    pick_nearest_edge,
    pick_nearest_vertex,
)


def _make_cube():
    return create_cube(size=2.0)


class PickingTests(unittest.TestCase):
    def test_pick_nearest_vertex_hits_correct_vertex(self):
        mesh = _make_cube()
        cam = OrbitCamera()
        w, h = 800, 600
        vid = min(mesh.all_vertex_ids())
        sx, sy = cam.project_to_screen(mesh.vertex_position(vid), w, h)
        hit = pick_nearest_vertex(cam, mesh, sx, sy, w, h)
        self.assertEqual(hit, vid)

    def test_pick_nearest_vertex_returns_none_when_far_away(self):
        mesh = _make_cube()
        cam = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0)
        hit = pick_nearest_vertex(cam, mesh, 0.0, 0.0, 800, 600)
        self.assertIsNone(hit)

    def test_pick_nearest_edge_hits_projected_edge(self):
        mesh = _make_cube()
        cam = OrbitCamera()
        w, h = 800, 600
        eid = min(mesh.all_edge_ids())
        va, vb = mesh.edge_vertices(eid)
        a = cam.project_to_screen(mesh.vertex_position(va), w, h)
        b = cam.project_to_screen(mesh.vertex_position(vb), w, h)
        # Mittelpunkt der projizierten Kante.
        sx = (a[0] + b[0]) / 2.0
        sy = (a[1] + b[1]) / 2.0
        hit = pick_nearest_edge(cam, mesh, sx, sy, w, h)
        self.assertEqual(hit, eid)

    def test_pick_face_hits_visible_cube_face(self):
        mesh = _make_cube()
        cam = OrbitCamera()
        w, h = 800, 600
        hit = pick_face(cam, mesh, w / 2.0, h / 2.0, w, h)
        self.assertIsNotNone(hit)

    def test_point_segment_distance_projection(self):
        # Punkt auf der Segmentachse → Abstand = vertikaler Abstand.
        d = _point_segment_distance(2.0, 1.0, 0.0, 0.0, 4.0, 0.0)
        self.assertAlmostEqual(d, 1.0, places=9)
        # Punkt innerhalb des Segments am Endpunkt.
        d2 = _point_segment_distance(4.0, 3.0, 0.0, 0.0, 4.0, 0.0)
        self.assertAlmostEqual(d2, 3.0, places=9)

    def test_ray_triangle_intersection_hits(self):
        origin = (0.0, 0.0, 5.0)
        direction = (0.0, 0.0, -1.0)
        t = _ray_triangle_intersection(
            origin, direction, (-1, -1, 0), (1, -1, 0), (0, 1, 0)
        )
        self.assertIsNotNone(t)
        self.assertAlmostEqual(t, 5.0, places=6)

    def test_ray_triangle_intersection_misses(self):
        origin = (0.0, 0.0, 5.0)
        direction = (0.0, 0.0, -1.0)
        t = _ray_triangle_intersection(
            origin, direction, (1, 1, 0), (2, 1, 0), (1, 2, 0)
        )
        self.assertIsNone(t)


if __name__ == "__main__":
    unittest.main()