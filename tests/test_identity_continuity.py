"""Phase C – Identitätskontinuität (Hardening-Plan §17 Phase C).

Ziel laut Plan: für split_edge/collapse_edge/connect_vertices explizit
feststellen und testen:

1. Welche bestehenden IDs bleiben erhalten?
2. Welche bestehenden IDs werden entfernt?
3. Welche neuen IDs entstehen?
4. Welche Geometrie-/Topologieelemente beziehen sich danach auf die
   erhaltenen bzw. neuen IDs?

Unterschied zu Phase B (test_topology_mutations.py): dort wurde die
Gültigkeit *einzelner* IDs geprüft ("ist X noch gültig?", "ist Y neu?").
Phase C vergleicht stattdessen die *vollständigen* Vertex-/Edge-/Face-ID-
Mengen vor und nach der Operation (Mengendifferenz), damit auch
unerwartete Nebenwirkungen sichtbar würden (z. B. eine zusätzliche,
nicht dokumentierte Edge, die verschwindet oder entsteht) - nicht nur die
explizit erwarteten IDs.

Noch KEIN allgemeines Herkunftssystem, kein Change-Set, kein
Dependency-Graph - das bleibt laut Plan §16 bewusst außerhalb dieser
Phase. Diese Tests dokumentieren nur, was der bestehende Core über seine
Query-API bereits nachvollziehbar macht.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core.ids import EdgeId, FaceId, VertexId
from core.mesh import Mesh
from tests.mesh_invariants import assert_mesh_invariants, build_quad_mesh

IdSnapshot = tuple[set[VertexId], set[EdgeId], set[FaceId]]


def snapshot(mesh: Mesh) -> IdSnapshot:
    """Vollständige ID-Mengen für alle drei Elementtypen - die Grundlage
    jedes Vorher/Nachher-Vergleichs in dieser Phase."""
    return set(mesh.all_vertex_ids()), set(mesh.all_edge_ids()), set(mesh.all_face_ids())


class TestSplitEdgeIdentityContinuity(unittest.TestCase):
    """split_edge: dokumentierter Vertrag (mesh.py) ist
    - alte EdgeId stirbt, beide alten VertexIds bleiben,
    - eine neue VertexId (Mittelpunkt) und zwei neue EdgeIds entstehen,
    - beteiligte FaceIds bleiben erhalten (nur Boundary aktualisiert)."""

    def test_boundary_edge_id_sets(self) -> None:
        mesh, (v0, v1, _v2, _v3), face = build_quad_mesh()
        target = mesh._get_or_create_edge(v0, v1)
        before_v, before_e, before_f = snapshot(mesh)

        mid, e_a, e_b = mesh.split_edge(target)

        after_v, after_e, after_f = snapshot(mesh)

        # 1. Was bleibt erhalten?
        self.assertEqual(before_v, after_v & before_v, "keine bestehende VertexId darf verschwinden")
        self.assertEqual(before_f, after_f, "Face-IDs bleiben bei split_edge unverändert")

        # 2. Was wird entfernt?
        self.assertEqual(before_e - after_e, {target})
        self.assertEqual(before_v - after_v, set(), "split_edge entfernt keine Vertices")
        self.assertEqual(before_f - after_f, set(), "split_edge entfernt keine Faces")

        # 3. Was entsteht neu?
        self.assertEqual(after_v - before_v, {mid})
        self.assertEqual(after_e - before_e, {e_a, e_b})
        self.assertEqual(after_f - before_f, set(), "split_edge erzeugt keine neue Face")

        # 4. Wer referenziert danach die erhaltenen/neuen IDs?
        self.assertIn(mid, mesh.face_vertices(face))
        self.assertEqual({e_a, e_b} & set(mesh.face_edges(face)), {e_a, e_b})
        self.assertNotIn(target, mesh.face_edges(face))
        self.assertEqual(set(mesh.edge_vertices(e_a)), {v0, mid})
        self.assertEqual(set(mesh.edge_vertices(e_b)), {mid, v1})
        assert_mesh_invariants(mesh, context="split boundary edge identity continuity")

    def test_internal_edge_two_faces_id_sets(self) -> None:
        """Edge zwischen zwei Faces: beide FaceIds bleiben erhalten (kein
        Face stirbt/entsteht), beide referenzieren danach mid/e_a/e_b."""
        mesh, (v0, v1, v2, v3), face_a = build_quad_mesh()
        v4 = mesh.add_vertex((2.0, 0.0, 0.0))
        face_b = mesh.add_face([v1, v4, v2])
        shared = mesh._get_or_create_edge(v1, v2)
        before_v, before_e, before_f = snapshot(mesh)

        mid, e_a, e_b = mesh.split_edge(shared)

        after_v, after_e, after_f = snapshot(mesh)

        self.assertEqual(before_v - after_v, set())
        self.assertEqual(after_v - before_v, {mid})
        self.assertEqual(before_e - after_e, {shared})
        self.assertEqual(after_e - before_e, {e_a, e_b})
        self.assertEqual(before_f, after_f, "beide FaceIds bleiben unverändert erhalten")

        for face in (face_a, face_b):
            self.assertIn(mid, mesh.face_vertices(face))
            self.assertEqual({e_a, e_b} & set(mesh.face_edges(face)), {e_a, e_b})
            self.assertNotIn(shared, mesh.face_edges(face))
        assert_mesh_invariants(mesh, context="split internal edge identity continuity")


class TestCollapseEdgeIdentityContinuity(unittest.TestCase):
    """collapse_edge: Survivor ist dokumentiert als v0 des Edge-Objekts
    (erster Konstruktor-Parameter von `_get_or_create_edge`/`add_face`),
    v1 stirbt. Zusätzlich können weitere, nicht direkt kollabierte Edges
    sterben (umbenannt oder mit einer bestehenden Edge verschmolzen -
    siehe collapse_edge-Docstring in mesh.py) - dieser Test dokumentiert
    beide Fälle explizit über die ID-Mengen-Differenz."""

    def test_simple_boundary_collapse_id_sets(self) -> None:
        mesh, (v0, v1, _v2, _v3), face = build_quad_mesh()
        edge = mesh._get_or_create_edge(v0, v1)
        before_v, before_e, before_f = snapshot(mesh)

        survivor = mesh.collapse_edge(edge)

        after_v, after_e, after_f = snapshot(mesh)

        self.assertEqual(survivor, v0, "Survivor ist eindeutig v0 (dokumentierter Vertrag)")
        self.assertEqual(before_v - after_v, {v1})
        self.assertEqual(after_v - before_v, set(), "collapse_edge erzeugt keine neue VertexId")
        self.assertEqual(before_e - after_e, {edge})
        self.assertEqual(after_e - before_e, set(), "im einfachen Fall entsteht keine neue EdgeId")
        self.assertEqual(before_f, after_f, "Quad->Dreieck degeneriert nicht, Face-ID bleibt")

        self.assertIn(survivor, mesh.face_vertices(face))
        self.assertNotIn(v1, mesh.face_vertices(face))
        assert_mesh_invariants(mesh, context="collapse simple identity continuity")

    def test_fan_collapse_renames_third_edge_id_sets(self) -> None:
        """removed (v1) hat eine dritte Kante zu v4, die NICHT über den
        Survivor läuft. Dokumentierter Fall 'Umbenennen': dieselbe EdgeId
        bleibt bestehen, nur ihr Endpunkt wechselt von v1 auf v0 - sie
        taucht NICHT in den entfernten IDs auf, obwohl sie inhaltlich
        verändert wurde. Das ist der Fall, für den der stale-edge-Fix
        (vorherige Chat-Runde) eingebaut wurde."""
        mesh, (v0, v1, v2, _v3), face_a = build_quad_mesh()
        v4 = mesh.add_vertex((2.0, 2.0, 0.0))
        face_b = mesh.add_face([v1, v4, v2])
        edge_v1_v4 = mesh._get_or_create_edge(v1, v4)
        edge = mesh._get_or_create_edge(v0, v1)
        before_v, before_e, before_f = snapshot(mesh)

        survivor = mesh.collapse_edge(edge)

        after_v, after_e, after_f = snapshot(mesh)

        self.assertEqual(before_v - after_v, {v1})
        self.assertEqual(before_e - after_e, {edge}, "nur die kollabierte Kante verschwindet als ID")
        self.assertEqual(after_e - before_e, set())
        self.assertEqual(before_f, after_f, "keine Face degeneriert in diesem Szenario")

        # 4: edge_v1_v4 behält ihre EdgeId, referenziert danach aber v0 statt v1.
        self.assertTrue(mesh.is_valid_edge(edge_v1_v4), "Edge wird umbenannt, nicht entfernt")
        self.assertEqual(set(mesh.edge_vertices(edge_v1_v4)), {survivor, v4})
        self.assertNotIn(v1, mesh.face_vertices(face_b))
        self.assertIn(survivor, mesh.face_vertices(face_b))
        assert_mesh_invariants(mesh, context="collapse fan-rename identity continuity")

    def test_collapse_merges_edge_into_existing_survivor_edge_id_sets(self) -> None:
        """Existiert bereits eine survivor<->other-Edge (hier: die
        Diagonale v0-v2 aus einem vorherigen connect_vertices), wird die
        umzubenennende Edge NICHT umbenannt, sondern gelöscht und ihre
        Face-Referenz in die bestehende Edge übernommen (Merge-Zweig in
        mesh.py). Dokumentierter Unterschied zum Umbenennen-Fall oben:
        hier verschwindet zusätzlich zur kollabierten Kante noch eine
        ZWEITE EdgeId, und dafür entsteht keine neue."""
        mesh, (v0, v1, v2, _v3), face_a = build_quad_mesh()
        _diag, face_b, face_c = mesh.connect_vertices(face_a, v0, v2)
        edge_v1_v2 = mesh._get_or_create_edge(v1, v2)
        edge_v0_v2 = mesh._get_or_create_edge(v0, v2)
        self.assertNotEqual(edge_v1_v2, edge_v0_v2, "Testaufbau-Voraussetzung: zwei getrennte Edges")
        edge_v0_v1 = mesh._get_or_create_edge(v0, v1)
        before_v, before_e, before_f = snapshot(mesh)

        survivor = mesh.collapse_edge(edge_v0_v1)

        after_v, after_e, after_f = snapshot(mesh)

        self.assertEqual(survivor, v0)
        self.assertEqual(before_v - after_v, {v1})
        self.assertEqual(
            before_e - after_e,
            {edge_v0_v1, edge_v1_v2},
            "kollabierte Kante UND die jetzt-redundante v1-v2-Kante sterben",
        )
        self.assertEqual(after_e - before_e, set(), "kein Ersatz nötig - bestehende Diagonale übernimmt")
        self.assertEqual(
            before_f - after_f,
            {face_b},
            "face_b ([v0,v1,v2]) degeneriert zu einer Linie (v0,v2) und wird entfernt",
        )
        self.assertEqual(after_f - before_f, set())

        # 4: die überlebende Diagonale referenziert danach nur noch face_c.
        self.assertTrue(mesh.is_valid_edge(edge_v0_v2))
        self.assertEqual(mesh.edge_faces(edge_v0_v2), [face_c])
        self.assertTrue(mesh.is_valid_face(face_c))
        self.assertIn(survivor, mesh.face_vertices(face_c))
        assert_mesh_invariants(mesh, context="collapse merge-branch identity continuity")


class TestConnectVerticesIdentityContinuity(unittest.TestCase):
    """connect_vertices: dokumentierter Vertrag ist
    - alte FaceId stirbt, zwei neue FaceIds und eine neue EdgeId entstehen,
    - alle VertexIds und alle unberührten Edges bleiben unverändert."""

    def test_diagonal_split_id_sets(self) -> None:
        mesh, (v0, v1, v2, v3), face = build_quad_mesh()
        before_v, before_e, before_f = snapshot(mesh)

        new_edge, face_a, face_b = mesh.connect_vertices(face, v0, v2)

        after_v, after_e, after_f = snapshot(mesh)

        # 1. Was bleibt erhalten?
        self.assertEqual(before_v, after_v, "connect_vertices verändert keine VertexId")
        self.assertEqual(before_e, after_e & before_e, "alle ursprünglichen Edges bleiben gültig")

        # 2. Was wird entfernt?
        self.assertEqual(before_f - after_f, {face})
        self.assertEqual(before_e - after_e, set(), "keine bestehende Edge stirbt bei connect_vertices")

        # 3. Was entsteht neu?
        self.assertEqual(after_f - before_f, {face_a, face_b})
        self.assertEqual(after_e - before_e, {new_edge})

        # 4. Wer referenziert danach die erhaltenen/neuen IDs?
        self.assertEqual(set(mesh.edge_vertices(new_edge)), {v0, v2})
        self.assertIn(new_edge, mesh.face_edges(face_a))
        self.assertIn(new_edge, mesh.face_edges(face_b))
        self.assertEqual(set(mesh.face_vertices(face_a)) | set(mesh.face_vertices(face_b)), {v0, v1, v2, v3})
        for v in (v0, v1, v2, v3):
            self.assertTrue(mesh.is_valid_vertex(v))
        assert_mesh_invariants(mesh, context="connect identity continuity")


if __name__ == "__main__":
    unittest.main()
