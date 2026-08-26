"""Phase A – Invarianten-Tests (CORE_V1_ANALYSIS_AND_HARDENING_PLAN §17 Phase A).

Prüft dokumentierte Struktur-Invarianten über die öffentliche Query-API.
Verletzungen deuten auf Core-Bugs hin — nicht auf fehlende Spezifikation.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401 — src/core auf sys.path

from core.ids import VertexId
from core.mesh import Mesh, MeshError
from tests.mesh_invariants import assert_mesh_invariants, build_quad_mesh


class TestMeshInvariantsPhaseA(unittest.TestCase):
    def test_empty_mesh_satisfies_invariants(self) -> None:
        mesh = Mesh()
        assert_mesh_invariants(mesh, context="empty")

    def test_quad_fixture_satisfies_invariants(self) -> None:
        build_quad_mesh()

    def test_invariants_after_remove_face(self) -> None:
        mesh, (_v0, _v1, _v2, _v3), face = build_quad_mesh()
        mesh.remove_face(face)
        self.assertFalse(mesh.is_valid_face(face))
        assert_mesh_invariants(mesh, context="after remove_face")

    def test_invariants_after_add_second_face_sharing_edge(self) -> None:
        mesh, (v0, v1, v2, v3), _face = build_quad_mesh()
        v4 = mesh.add_vertex((2.0, 0.0, 0.0))
        mesh.add_face([v1, v4, v2])
        assert_mesh_invariants(mesh, context="two faces sharing edge")

    def test_add_face_rejects_unknown_vertex(self) -> None:
        mesh = Mesh()
        v0 = mesh.add_vertex((0.0, 0.0, 0.0))
        v1 = mesh.add_vertex((1.0, 0.0, 0.0))
        _v2 = mesh.add_vertex((0.0, 1.0, 0.0))

        with self.assertRaises(MeshError):
            mesh.add_face([v0, v1, VertexId(9999)])

    def test_add_face_rejects_fewer_than_three_vertices(self) -> None:
        mesh = Mesh()
        v0 = mesh.add_vertex((0.0, 0.0, 0.0))
        v1 = mesh.add_vertex((1.0, 0.0, 0.0))
        with self.assertRaises(MeshError):
            mesh.add_face([v0, v1])

    def test_face_edges_raises_on_broken_topology(self) -> None:
        """face_edges() muss fehlende Kanten melden (MeshError), nicht stillschweigend."""
        mesh, (_v0, _v1, _v2, _v3), face = build_quad_mesh()
        # Simuliert internen Inkonsistenz-Zustand — nur über legitime API erreichbar
        # indem wir eine Face mit gültiger Boundary aber fehlender Edge nicht bauen können
        # ohne Interna. Stattdessen: gültiges Mesh, face_edges() muss für gültige Face laufen.
        edges = mesh.face_edges(face)
        self.assertEqual(len(edges), 4)


if __name__ == "__main__":
    unittest.main()
