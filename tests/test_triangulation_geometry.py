"""Ear-Clipping-Triangulierung (`triangulate_face` mit Positionen) und Picking.

Hintergrund: docs/research/topology/FACE_HOLES_DISCOVERY.md §4 (Q4) — die
Index-only-Fan-Triangulierung überdeckte konkave Faces doppelt und ließ
`pick_face` die Ring-Face statt der inneren Face liefern.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core import Mesh
from mirai.scene_factory import create_cube
from mirai.viewport.camera import OrbitCamera
from mirai.viewport.picking import pick_face
from tests.mesh_invariants import assert_face_triangulations_sound
from viewport.derived import DerivedGeometry, triangulate_face, triangulate_mesh_face

# Die Ring-/Inner-Polygone der drei Face-Holes-Probe-Konstruktionen (Grid-Quad
# (1,1)-(2,2) mit Dreieck), so wie sie `face_holes_probe.py` heute liefert.
L_HEXAGON = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]
LAB_CCW_RING_5 = [(1.0, 1.0), (2.0, 1.0), (1.7, 1.3), (1.5, 1.7), (1.3, 1.3)]
LAB_CCW_RING_6 = [(2.0, 1.0), (2.0, 2.0), (1.0, 2.0), (1.0, 1.0), (1.3, 1.3), (1.7, 1.3)]
LAB_CW_RING_7 = [(2.0, 1.0), (2.0, 2.0), (1.0, 2.0), (1.0, 1.0), (1.3, 1.3), (1.5, 1.7), (1.7, 1.3)]
FC6_RING_5 = [(2.0, 2.0), (1.0, 2.0), (1.0, 1.0), (1.3, 1.3), (1.5, 1.7)]
FC6_RING_6 = [(1.3, 1.3), (1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.5, 1.7), (1.7, 1.3)]
L_HEXAGON_ROT = [(1, 2), (0, 2), (0, 0), (2, 0), (2, 1), (1, 1)]  # Fan von v0 ragt hier in den Ausschnitt
COMB = [(0, 0), (5, 0), (5, 3), (4, 3), (4, 1), (3, 1), (3, 3), (2, 3), (2, 1), (1, 1), (1, 3), (0, 3)]


def _mesh_of(*polygons, plane="xy", reverse=False):
    mesh = Mesh()
    for poly in polygons:
        pts = list(reversed(poly)) if reverse else poly
        if plane == "xy":
            coords = [(x, y, 0.0) for x, y in pts]
        elif plane == "xz":
            coords = [(x, 0.0, y) for x, y in pts]
        else:
            coords = [(0.0, x, y) for x, y in pts]
        mesh.add_face([mesh.add_vertex(c) for c in coords])
    return mesh


class ConcaveTriangulationTests(unittest.TestCase):
    def test_probe_shapes_are_single_covered(self):
        cases = {
            "L hexagon": [L_HEXAGON],
            "L hexagon rotated": [L_HEXAGON_ROT],
            "lab-ccw rings": [LAB_CCW_RING_5, LAB_CCW_RING_6],
            "lab-cw ring": [LAB_CW_RING_7],
            "fc6 rings": [FC6_RING_5, FC6_RING_6],
            "comb": [COMB],
        }
        for name, polys in cases.items():
            for plane in ("xy", "xz", "yz"):
                for reverse in (False, True):
                    with self.subTest(shape=name, plane=plane, reverse=reverse):
                        mesh = _mesh_of(*polys, plane=plane, reverse=reverse)
                        assert_face_triangulations_sound(mesh, context=name)

    def test_fan_would_fail_the_same_check(self):
        """Guard: der Test darf nicht trivial grün sein — der alte Fan fällt durch."""
        mesh = _mesh_of(LAB_CW_RING_7)
        fid = next(iter(mesh.all_face_ids()))
        boundary = mesh.face_vertices(fid)
        fan = triangulate_face(boundary)  # ohne Positionen = Fan
        self.assertNotEqual(fan, triangulate_mesh_face(mesh, fid))

    def test_triangles_keep_boundary_orientation_and_ids(self):
        mesh = _mesh_of(L_HEXAGON)
        fid = next(iter(mesh.all_face_ids()))
        boundary = mesh.face_vertices(fid)
        tris = triangulate_mesh_face(mesh, fid)
        self.assertEqual(len(tris), 4)
        self.assertTrue(all(v in boundary for t in tris for v in t))
        self.assertEqual({v for t in tris for v in t}, set(boundary))

    def test_convex_input_is_unchanged_fan(self):
        mesh = _mesh_of([(0, 0), (2, 0), (3, 1), (2, 2), (0, 2)])
        fid = next(iter(mesh.all_face_ids()))
        b = mesh.face_vertices(fid)
        self.assertEqual(
            triangulate_mesh_face(mesh, fid),
            [(b[0], b[i], b[i + 1]) for i in range(1, len(b) - 1)],
        )

    def test_degenerate_still_empty(self):
        self.assertEqual(triangulate_face([1, 2], {1: (0, 0, 0), 2: (1, 0, 0)}), [])
        self.assertEqual(triangulate_face([], {}), [])

    def test_collinear_vertices_terminate(self):
        mesh = _mesh_of([(0, 0), (1, 0), (2, 0), (2, 2), (1, 1), (0, 2)])
        fid = next(iter(mesh.all_face_ids()))
        self.assertEqual(len(triangulate_mesh_face(mesh, fid)), 4)

    def test_cube_render_data_unchanged(self):
        mesh = create_cube()
        assert_face_triangulations_sound(mesh, context="cube")
        for fid in mesh.all_face_ids():
            b = mesh.face_vertices(fid)
            self.assertEqual(
                triangulate_mesh_face(mesh, fid),
                [(b[0], b[i], b[i + 1]) for i in range(1, len(b) - 1)],
            )

    def test_face_normal_of_concave_face_follows_winding(self):
        mesh = _mesh_of(L_HEXAGON)
        fid = next(iter(mesh.all_face_ids()))
        self.assertEqual(DerivedGeometry(mesh).face_normals[fid], (0.0, 0.0, 1.0))
        mesh = _mesh_of(L_HEXAGON, reverse=True)
        fid = next(iter(mesh.all_face_ids()))
        self.assertEqual(DerivedGeometry(mesh).face_normals[fid], (0.0, 0.0, -1.0))


class ConcavePickingTests(unittest.TestCase):
    """`pick_face` konsumiert dieselbe Triangulierung (Face-Holes-Probe: fc6)."""

    @staticmethod
    def _pick(mesh, point):
        cam = OrbitCamera(target=(1.5, 1.5, 0.0), distance=6.0, yaw=0.0, pitch=0.0)
        sx, sy = cam.project_to_screen(point, 400, 400)
        return pick_face(cam, mesh, sx, sy, 400, 400)

    def test_fc6_centroid_picks_inner_not_ring(self):
        mesh = Mesh()
        faces = []
        for poly in (FC6_RING_5, FC6_RING_6, [(1.5, 1.7), (1.3, 1.3), (1.7, 1.3)]):
            faces.append(mesh.add_face([mesh.add_vertex((x, y, 0.0)) for x, y in poly]))
        inner = faces[2]
        centroid = (1.5, (1.3 + 1.3 + 1.7) / 3.0, 0.0)
        self.assertEqual(self._pick(mesh, centroid), inner)
        self.assertEqual(self._pick(mesh, (1.1, 1.8, 0.0)), faces[0])


if __name__ == "__main__":
    unittest.main()
