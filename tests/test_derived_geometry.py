"""DerivedGeometry: Adjazenz, inkrementelle Normalen, Bounds.

Gate 5 (Viewport Production). Verifiziert gegen die reale `core.Mesh`-API
(n-gonale Faces, opake VertexId/FaceId).
"""

from __future__ import annotations

import math
import unittest

import tests._bootstrap  # noqa: F401

from mirai.scene_factory import create_cube
from viewport.derived import (
    DerivedGeometry,
    compute_bounds,
    triangulate_face,
)


def _length(v):
    return math.sqrt(sum(c * c for c in v))


class TriangulateFaceTests(unittest.TestCase):
    def test_triangle_returns_single_triangle(self):
        tris = triangulate_face([1, 2, 3])
        self.assertEqual(tris, [(1, 2, 3)])

    def test_quad_returns_two_triangles_fan(self):
        tris = triangulate_face([1, 2, 3, 4])
        self.assertEqual(tris, [(1, 2, 3), (1, 3, 4)])

    def test_degenerate_returns_empty(self):
        self.assertEqual(triangulate_face([1, 2]), [])
        self.assertEqual(triangulate_face([]), [])


class ComputeBoundsTests(unittest.TestCase):
    def test_empty_returns_origin(self):
        self.assertEqual(compute_bounds([]), ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))

    def test_single_point(self):
        self.assertEqual(
            compute_bounds([(1.0, 2.0, 3.0)]), ((1.0, 2.0, 3.0), (1.0, 2.0, 3.0))
        )

    def test_multiple_points(self):
        pts = [(-1.0, 0.0, 5.0), (2.0, -3.0, 1.0), (0.0, 4.0, 0.0)]
        mins, maxs = compute_bounds(pts)
        self.assertEqual(mins, (-1.0, -3.0, 0.0))
        self.assertEqual(maxs, (2.0, 4.0, 5.0))


class DerivedGeometryTests(unittest.TestCase):
    def setUp(self):
        self.mesh = create_cube()
        self.derived = DerivedGeometry(self.mesh)

    def test_adjacency_covers_all_vertices(self):
        for vid in self.mesh.all_vertex_ids():
            self.assertIn(vid, self.derived.vertex_to_faces)

    def test_adjacency_each_cube_vertex_has_three_incident_faces(self):
        # Ein Würfel-Vertex grenzt an genau 3 Quad-Faces.
        for vid in self.mesh.all_vertex_ids():
            self.assertEqual(len(self.derived.vertex_to_faces[vid]), 3)

    def test_face_normals_computed_for_all_faces(self):
        for fid in self.mesh.all_face_ids():
            self.assertIn(fid, self.derived.face_normals)

    def test_face_normals_are_unit_length(self):
        for fid in self.mesh.all_face_ids():
            n = self.derived.face_normals[fid]
            self.assertAlmostEqual(_length(n), 1.0, places=5)

    def test_vertex_normals_are_unit_length(self):
        for vid in self.mesh.all_vertex_ids():
            n = self.derived.vertex_normals[vid]
            self.assertAlmostEqual(_length(n), 1.0, places=5)

    def test_bounds_match_cube_extent(self):
        # create_cube(size=2.0) -> Extent von -1..1 in jeder Achse.
        mins, maxs = self.derived.bounds_min, self.derived.bounds_max
        for c in mins:
            self.assertAlmostEqual(c, -1.0, places=5)
        for c in maxs:
            self.assertAlmostEqual(c, 1.0, places=5)

    def test_affected_neighborhood_single_vertex(self):
        vid = self.mesh.all_vertex_ids()[0]
        faces, verts = self.derived.affected_neighborhood(self.mesh, {vid})
        # Genau die 3 incident Faces des bewegten Vertex.
        self.assertEqual(faces, self.derived.vertex_to_faces[vid])
        # verts enthält mindestens den bewegten Vertex selbst.
        self.assertIn(vid, verts)
        # Alle betroffenen Vertices müssen Teil mindestens einer betroffenen
        # Face sein.
        for v in verts:
            self.assertTrue(
                any(v in self.mesh.face_vertices(f) for f in faces)
            )

    def test_incremental_normal_update_matches_full_recompute(self):
        vid = self.mesh.all_vertex_ids()[0]
        old_pos = self.mesh.vertex_position(vid)
        self.mesh.set_vertex_position(vid, (old_pos[0] + 0.5, old_pos[1], old_pos[2]))

        faces, verts = self.derived.affected_neighborhood(self.mesh, {vid})
        self.derived.update_face_normals(self.mesh, faces)
        self.derived.update_vertex_normals(self.mesh, verts)
        self.derived.recompute_bounds(self.mesh)

        incremental_normals = dict(self.derived.vertex_normals)
        incremental_bounds = (self.derived.bounds_min, self.derived.bounds_max)

        # Referenz: kompletter Rebuild auf demselben (mutierten) Mesh-Zustand.
        reference = DerivedGeometry(self.mesh)

        for v in self.mesh.all_vertex_ids():
            for a, b in zip(incremental_normals[v], reference.vertex_normals[v]):
                self.assertAlmostEqual(a, b, places=5)

        self.assertEqual(incremental_bounds, (reference.bounds_min, reference.bounds_max))

    def test_update_face_normals_does_not_touch_unrelated_faces(self):
        vid = self.mesh.all_vertex_ids()[0]
        untouched_faces = set(self.mesh.all_face_ids()) - self.derived.vertex_to_faces[vid]
        before = {f: self.derived.face_normals[f] for f in untouched_faces}

        old_pos = self.mesh.vertex_position(vid)
        self.mesh.set_vertex_position(vid, (old_pos[0] + 1.0, old_pos[1], old_pos[2]))
        faces, _ = self.derived.affected_neighborhood(self.mesh, {vid})
        self.derived.update_face_normals(self.mesh, faces)

        for f in untouched_faces:
            self.assertEqual(before[f], self.derived.face_normals[f])

    def test_rebuild_adjacency_after_topology_change(self):
        eid = self.mesh.all_edge_ids()[0]
        self.mesh.split_edge(eid)
        self.derived.full_recompute(self.mesh)
        for vid in self.mesh.all_vertex_ids():
            self.assertIn(vid, self.derived.vertex_to_faces)


if __name__ == "__main__":
    unittest.main()


class FaceNormalStraightAngleVertexTests(unittest.TestCase):
    """Regression (Knife Face Lab Task C, 2026-09-30): a split vertex on an edge made the first
    fan triangle of the neighbouring face degenerate; the face normal was (0, 0, 0) and the face
    was lit by ambient only. The normal now comes from the whole boundary (Newell)."""

    @staticmethod
    def _outward(mesh, fid):
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
        axis = next(k for k in range(3) if all(abs(p[k] - pts[0][k]) < 1e-12 for p in pts))
        out = [0.0, 0.0, 0.0]
        out[axis] = 1.0 if pts[0][axis] > 0 else -1.0
        return tuple(out)

    def test_every_single_edge_split_keeps_all_face_normals(self):
        mesh = create_cube()
        for eid in list(mesh.all_edge_ids()):
            state = mesh.export_state()
            mesh.split_edge(eid, 0.3)
            derived = DerivedGeometry(mesh)
            for fid in mesh.all_face_ids():
                n = derived.face_normals[fid]
                for a, b in zip(n, self._outward(mesh, fid)):
                    self.assertAlmostEqual(a, b, places=12)
            for vid in mesh.all_vertex_ids():
                self.assertAlmostEqual(_length(derived.vertex_normals[vid]), 1.0, places=9)
            mesh.load_state(state)

    def test_incremental_update_gives_the_same_normal_after_a_split(self):
        mesh = create_cube()
        derived = DerivedGeometry(mesh)
        eid = next(iter(mesh.all_edge_ids()))
        vid, _e1, _e2 = mesh.split_edge(eid, 0.5)
        derived.rebuild_adjacency(mesh)
        faces = set(derived.vertex_to_faces[vid])
        derived.update_face_normals(mesh, faces)
        reference = DerivedGeometry(mesh)
        for fid in faces:
            self.assertEqual(derived.face_normals[fid], reference.face_normals[fid])
            self.assertAlmostEqual(_length(derived.face_normals[fid]), 1.0, places=12)
