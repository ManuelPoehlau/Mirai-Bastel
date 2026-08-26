"""Phase B – Topologie-Mutations-Tests (Hardening-Plan §17 Phase B).

Getestet wird ausschließlich, was in src/core/mesh.py und V1_SPEC §7 dokumentiert ist.
Wo Semantik fehlt (z. B. konkrete Face-Zuordnung bei connect), wird nur
Struktur-Invariante geprüft — keine erfundene Erwartung.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core.mesh import Mesh, MeshError
from tests.mesh_invariants import assert_id_monotonic, assert_mesh_invariants, build_quad_mesh


class TestSplitEdgePhaseB(unittest.TestCase):
    def test_split_documented_id_continuity(self) -> None:
        mesh, (v0, v1, _v2, _v3), face = build_quad_mesh()
        target = mesh._get_or_create_edge(v0, v1)
        max_vid_before = max(mesh.all_vertex_ids(), key=int)
        max_eid_before = max(mesh.all_edge_ids(), key=int)

        mid, e_a, e_b = mesh.split_edge(target)

        self.assertFalse(mesh.is_valid_edge(target))
        self.assertTrue(mesh.is_valid_vertex(mid))
        self.assertTrue(mesh.is_valid_edge(e_a))
        self.assertTrue(mesh.is_valid_edge(e_b))
        self.assertTrue(mesh.is_valid_vertex(v0))
        self.assertTrue(mesh.is_valid_vertex(v1))
        self.assertTrue(mesh.is_valid_face(face))
        assert_id_monotonic(mid, max_vid_before)
        assert_id_monotonic(e_a, max_eid_before)
        assert_id_monotonic(e_b, max_eid_before)
        self.assertIn(mid, mesh.face_vertices(face))
        self.assertEqual(len(mesh.face_vertices(face)), 5)
        assert_mesh_invariants(mesh, context="after split_edge")

    def test_split_midpoint_position(self) -> None:
        mesh, (v0, v1, _v2, _v3), _face = build_quad_mesh()
        target = mesh._get_or_create_edge(v0, v1)
        mid, _ea, _eb = mesh.split_edge(target)
        pos = mesh.vertex_position(mid)
        self.assertAlmostEqual(pos[0], 0.5)
        self.assertAlmostEqual(pos[1], 0.0)
        self.assertAlmostEqual(pos[2], 0.0)

    def test_split_on_internal_edge_two_faces(self) -> None:
        """Edge zwischen zwei Faces — beide Boundaries müssen den Mittelpunkt tragen."""
        mesh, (v0, v1, v2, v3), face_a = build_quad_mesh()
        v4 = mesh.add_vertex((2.0, 0.0, 0.0))
        face_b = mesh.add_face([v1, v4, v2])
        shared = mesh._get_or_create_edge(v1, v2)

        mid, _ea, _eb = mesh.split_edge(shared)

        self.assertIn(mid, mesh.face_vertices(face_a))
        self.assertIn(mid, mesh.face_vertices(face_b))
        self.assertTrue(mesh.is_valid_face(face_a))
        self.assertTrue(mesh.is_valid_face(face_b))
        assert_mesh_invariants(mesh, context="split internal edge")


class TestCollapseEdgePhaseB(unittest.TestCase):
    def test_collapse_documented_survivor_and_geometry(self) -> None:
        """Vertrag mesh.collapse_edge: v0 überlebt, v1 ungültig, Position = Mittelpunkt."""
        mesh, (v0, v1, _v2, _v3), face = build_quad_mesh()
        edge = mesh._get_or_create_edge(v0, v1)

        survivor = mesh.collapse_edge(edge)

        self.assertEqual(survivor, v0)
        self.assertFalse(mesh.is_valid_edge(edge))
        self.assertFalse(mesh.is_valid_vertex(v1))
        self.assertTrue(mesh.is_valid_vertex(v0))
        self.assertTrue(mesh.is_valid_face(face))
        self.assertEqual(len(mesh.face_vertices(face)), 3)
        self.assertAlmostEqual(mesh.vertex_position(survivor)[0], 0.5)
        assert_mesh_invariants(mesh, context="collapse boundary edge")

    def test_collapse_no_stale_edge_endpoints(self) -> None:
        """Dokumentierte Invariante: keine Edge referenziert den entfernten Vertex."""
        mesh, (v0, v1, v2, _v3), _face_a = build_quad_mesh()
        v4 = mesh.add_vertex((2.0, 2.0, 0.0))
        face_b = mesh.add_face([v1, v4, v2])
        edge = mesh._get_or_create_edge(v0, v1)

        survivor = mesh.collapse_edge(edge)

        self.assertFalse(mesh.is_valid_vertex(v1))
        for eid in mesh.all_edge_ids():
            ev0, ev1 = mesh.edge_vertices(eid)
            self.assertNotIn(v1, (ev0, ev1))
        self.assertNotIn(v1, mesh.face_vertices(face_b))
        self.assertIn(survivor, mesh.face_vertices(face_b))
        self.assertEqual(len(mesh.face_edges(face_b)), 3)
        assert_mesh_invariants(mesh, context="collapse fan")


class TestConnectVerticesPhaseB(unittest.TestCase):
    def test_connect_documented_id_continuity(self) -> None:
        mesh, (v0, v1, v2, v3), face = build_quad_mesh()
        max_fid_before = max(int(f) for f in mesh.all_face_ids())

        new_edge, face_a, face_b = mesh.connect_vertices(face, v0, v2)

        self.assertFalse(mesh.is_valid_face(face))
        self.assertTrue(mesh.is_valid_face(face_a))
        self.assertTrue(mesh.is_valid_face(face_b))
        self.assertTrue(mesh.is_valid_edge(new_edge))
        self.assertGreater(int(face_a), max_fid_before)
        self.assertGreater(int(face_b), max_fid_before)
        for v in (v0, v1, v2, v3):
            self.assertTrue(mesh.is_valid_vertex(v))
        self.assertEqual(len(mesh.face_vertices(face_a)), 3)
        self.assertEqual(len(mesh.face_vertices(face_b)), 3)
        assert_mesh_invariants(mesh, context="connect v0-v2")

    def test_connect_second_diagonal_invariants_only(self) -> None:
        """v1–v3 ist gültige Alternative; Face-Zuordnung ist nicht spezifiziert — nur Invarianten."""
        mesh, (v0, v1, v2, v3), face = build_quad_mesh()
        _new_edge, _fa, _fb = mesh.connect_vertices(face, v1, v3)
        assert_mesh_invariants(mesh, context="connect v1-v3")
        for v in (v0, v1, v2, v3):
            self.assertTrue(mesh.is_valid_vertex(v))

    def test_connect_adjacent_vertices_raises(self) -> None:
        mesh, (v0, v1, _v2, _v3), face = build_quad_mesh()
        with self.assertRaises(MeshError):
            mesh.connect_vertices(face, v0, v1)

    def test_connect_vertex_not_on_boundary_raises(self) -> None:
        mesh, (v0, _v1, _v2, _v3), face = build_quad_mesh()
        outsider = mesh.add_vertex((5.0, 5.0, 0.0))
        with self.assertRaises(MeshError):
            mesh.connect_vertices(face, v0, outsider)


if __name__ == "__main__":
    unittest.main()
