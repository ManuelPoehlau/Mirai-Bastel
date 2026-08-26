"""Phase D – Undo/Redo für Topologieoperationen (Hardening-Plan §17 Phase D).

Voraussetzung (siehe Chat-Absprache vor dieser Phase): split_edge/
collapse_edge/connect_vertices sind atomare Mesh-Mutationen ohne eigene
History-Anbindung. Für jeden Test wird deshalb explizit ein
MeshStateCommand um den Mutationsaufruf herum gebaut (Snapshot vorher/
nachher) und auf `HistoryStack` gepusht - keine automatische Kopplung im
Core, siehe operations/topology.py.

Geprüft wird für jede Operation:

    commit  -> Zustand X
    undo    -> exakt Ausgangszustand (vollständige ID-Mengen + Adjazenz)?
    redo    -> exakt Zustand X (vollständige ID-Mengen + Adjazenz)?

"Exakt" heißt hier bewusst mehr als nur Positionen: vollständige Vertex-/
Edge-/Face-ID-Mengen (wie in Phase C) UND ihre Beziehungen zueinander
(face_vertices/face_edges/edge_vertices/edge_faces), nicht nur "undo()
lief ohne Exception".
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core.history import HistoryStack
from core.mesh import Mesh
from core.operations.topology import MeshStateCommand
from tests.mesh_invariants import assert_mesh_invariants, build_quad_mesh
from tests.test_identity_continuity import snapshot


def full_topology_snapshot(mesh: Mesh) -> dict:
    """Vollständiger Vergleichszustand für diese Phase: nicht nur die
    ID-Mengen (wie Phase C), sondern zusätzlich alle Beziehungen der
    einzelnen Elemente zueinander - genau das, was "exakt derselbe
    Zustand" laut Auftrag bedeuten soll, nicht nur "gleiche Mengen"."""
    vids, eids, fids = snapshot(mesh)
    return {
        "vertex_ids": vids,
        "edge_ids": eids,
        "face_ids": fids,
        "positions": {vid: mesh.vertex_position(vid) for vid in vids},
        "edge_vertices": {eid: mesh.edge_vertices(eid) for eid in eids},
        "edge_faces": {eid: sorted(mesh.edge_faces(eid), key=int) for eid in eids},
        "face_vertices": {fid: mesh.face_vertices(fid) for fid in fids},
        "face_edges": {fid: mesh.face_edges(fid) for fid in fids},
    }


def run_as_command(mesh: Mesh, history: HistoryStack, mutate):
    """Testhilfe: snapshotet vor/nach `mutate()`, baut ein MeshStateCommand
    und pusht es auf die History - genau das manuelle "Drumherumbauen",
    das laut Absprache (noch) keine automatische Core-Kopplung ist.

    Gibt (result_of_mutate, command) zurück.
    """
    before = mesh.export_state()
    result = mutate()
    after = mesh.export_state()
    command = MeshStateCommand(mesh=mesh, before_state=before, after_state=after)
    history.push(command)
    return result, command


class TestSplitEdgeUndoRedo(unittest.TestCase):
    def test_split_commit_undo_redo_exact_state(self) -> None:
        mesh, (v0, v1, _v2, _v3), face = build_quad_mesh()
        history = HistoryStack()
        target = mesh._get_or_create_edge(v0, v1)

        state_before = full_topology_snapshot(mesh)

        (mid, e_a, e_b), _cmd = run_as_command(mesh, history, lambda: mesh.split_edge(target))
        state_after_commit = full_topology_snapshot(mesh)

        # Zwischenkontrolle: der Split hat tatsächlich etwas verändert -
        # sonst wäre ein trivial bestehender Test (undo == redo == nichts).
        self.assertNotEqual(state_before, state_after_commit)
        self.assertIn(mid, state_after_commit["vertex_ids"])

        self.assertTrue(history.can_undo())
        self.assertFalse(history.can_redo())

        history.undo()
        state_after_undo = full_topology_snapshot(mesh)
        self.assertEqual(state_after_undo, state_before, "undo() muss exakt den Ausgangszustand wiederherstellen")
        self.assertTrue(mesh.is_valid_edge(target), "die ursprüngliche Edge lebt nach undo() wieder")
        self.assertFalse(mesh.is_valid_vertex(mid), "der Split-Vertex existiert nach undo() nicht mehr")
        assert_mesh_invariants(mesh, context="split undo")

        self.assertTrue(history.can_redo())
        history.redo()
        state_after_redo = full_topology_snapshot(mesh)
        self.assertEqual(state_after_redo, state_after_commit, "redo() muss exakt den committeten Split-Zustand wiederherstellen")
        assert_mesh_invariants(mesh, context="split redo")

        # AD-001-Kontrollprobe: nach undo() darf eine neue Mutation NICHT
        # die ID des rückgängig gemachten Split-Vertex wiederverwenden.
        history.undo()
        fresh = mesh.add_vertex((9.0, 9.0, 9.0))
        self.assertNotEqual(fresh, mid, "AD-001 verletzt: ID wurde nach Undo wiederverwendet")

    def test_split_internal_edge_undo_redo_both_faces(self) -> None:
        """Split auf einer von zwei Faces geteilten Edge - beide Faces
        müssen nach undo() wieder ihre ursprüngliche Boundary haben und
        nach redo() wieder beide den Mittelpunkt tragen."""
        mesh, (v0, v1, v2, v3), face_a = build_quad_mesh()
        v4 = mesh.add_vertex((2.0, 0.0, 0.0))
        face_b = mesh.add_face([v1, v4, v2])
        shared = mesh._get_or_create_edge(v1, v2)
        history = HistoryStack()

        state_before = full_topology_snapshot(mesh)
        (mid, _ea, _eb), _cmd = run_as_command(mesh, history, lambda: mesh.split_edge(shared))
        state_after_commit = full_topology_snapshot(mesh)

        history.undo()
        self.assertEqual(full_topology_snapshot(mesh), state_before)
        self.assertNotIn(mid, mesh.face_vertices(face_a))
        self.assertNotIn(mid, mesh.face_vertices(face_b))
        assert_mesh_invariants(mesh, context="split-internal undo")

        history.redo()
        self.assertEqual(full_topology_snapshot(mesh), state_after_commit)
        self.assertIn(mid, mesh.face_vertices(face_a))
        self.assertIn(mid, mesh.face_vertices(face_b))
        assert_mesh_invariants(mesh, context="split-internal redo")


class TestCollapseEdgeUndoRedo(unittest.TestCase):
    def test_collapse_commit_undo_redo_exact_state(self) -> None:
        mesh, (v0, v1, _v2, _v3), face = build_quad_mesh()
        history = HistoryStack()
        edge = mesh._get_or_create_edge(v0, v1)

        state_before = full_topology_snapshot(mesh)
        survivor, _cmd = run_as_command(mesh, history, lambda: mesh.collapse_edge(edge))
        state_after_commit = full_topology_snapshot(mesh)

        self.assertNotEqual(state_before, state_after_commit)

        history.undo()
        state_after_undo = full_topology_snapshot(mesh)
        self.assertEqual(state_after_undo, state_before)
        self.assertTrue(mesh.is_valid_vertex(v1), "v1 lebt nach undo() wieder")
        self.assertTrue(mesh.is_valid_edge(edge))
        assert_mesh_invariants(mesh, context="collapse undo")

        history.redo()
        state_after_redo = full_topology_snapshot(mesh)
        self.assertEqual(state_after_redo, state_after_commit)
        self.assertFalse(mesh.is_valid_vertex(v1), "v1 bleibt nach redo() wieder entfernt")
        self.assertTrue(mesh.is_valid_vertex(survivor))
        assert_mesh_invariants(mesh, context="collapse redo")

    def test_collapse_fan_undo_redo_third_edge_renamed_back(self) -> None:
        """Der Fan-Fall aus Phase C: eine dritte Edge wird beim Collapse
        umbenannt (v1->v0). undo() muss ihr wieder GENAU denselben
        Endpunkt (v1, dieselbe VertexId) zurückgeben - keine neue Edge."""
        mesh, (v0, v1, v2, _v3), face_a = build_quad_mesh()
        v4 = mesh.add_vertex((2.0, 2.0, 0.0))
        face_b = mesh.add_face([v1, v4, v2])
        edge_v1_v4 = mesh._get_or_create_edge(v1, v4)
        edge = mesh._get_or_create_edge(v0, v1)
        history = HistoryStack()

        state_before = full_topology_snapshot(mesh)
        _survivor, _cmd = run_as_command(mesh, history, lambda: mesh.collapse_edge(edge))
        state_after_commit = full_topology_snapshot(mesh)

        history.undo()
        self.assertEqual(full_topology_snapshot(mesh), state_before)
        self.assertEqual(set(mesh.edge_vertices(edge_v1_v4)), {v1, v4}, "Edge zeigt nach undo() wieder auf v1")
        assert_mesh_invariants(mesh, context="collapse fan undo")

        history.redo()
        self.assertEqual(full_topology_snapshot(mesh), state_after_commit)
        self.assertEqual(set(mesh.edge_vertices(edge_v1_v4)), {v0, v4}, "Edge zeigt nach redo() wieder auf v0")
        assert_mesh_invariants(mesh, context="collapse fan redo")

    def test_collapse_merge_branch_undo_redo_restores_removed_edge_and_face(self) -> None:
        """Der Merge-Fall aus Phase C: eine Edge UND eine Face sterben
        zusätzlich zur kollabierten Edge. undo() muss beide exakt mit
        ihren ursprünglichen IDs zurückbringen - das ist der stärkste
        Beweis dafür, dass Snapshot/Restore hier nötig ist (eine
        semantische Gegenoperation könnte die verlorene FaceId/EdgeId
        gar nicht wiederherstellen, siehe operations/topology.py)."""
        mesh, (v0, v1, v2, _v3), face_a = build_quad_mesh()
        _diag, face_b, face_c = mesh.connect_vertices(face_a, v0, v2)
        edge_v1_v2 = mesh._get_or_create_edge(v1, v2)
        edge_v0_v2 = mesh._get_or_create_edge(v0, v2)
        edge_v0_v1 = mesh._get_or_create_edge(v0, v1)
        history = HistoryStack()

        state_before = full_topology_snapshot(mesh)
        _survivor, _cmd = run_as_command(mesh, history, lambda: mesh.collapse_edge(edge_v0_v1))
        state_after_commit = full_topology_snapshot(mesh)

        self.assertFalse(mesh.is_valid_face(face_b))
        self.assertFalse(mesh.is_valid_edge(edge_v1_v2))

        history.undo()
        self.assertEqual(full_topology_snapshot(mesh), state_before)
        self.assertTrue(mesh.is_valid_face(face_b), "face_b lebt nach undo() mit derselben FaceId wieder")
        self.assertTrue(mesh.is_valid_edge(edge_v1_v2), "edge_v1_v2 lebt nach undo() mit derselben EdgeId wieder")
        self.assertEqual(mesh.face_vertices(face_b), [v0, v1, v2])
        assert_mesh_invariants(mesh, context="collapse merge-branch undo")

        history.redo()
        self.assertEqual(full_topology_snapshot(mesh), state_after_commit)
        self.assertFalse(mesh.is_valid_face(face_b))
        self.assertFalse(mesh.is_valid_edge(edge_v1_v2))
        self.assertTrue(mesh.is_valid_edge(edge_v0_v2))
        assert_mesh_invariants(mesh, context="collapse merge-branch redo")


class TestConnectVerticesUndoRedo(unittest.TestCase):
    def test_connect_commit_undo_redo_exact_state(self) -> None:
        mesh, (v0, v1, v2, v3), face = build_quad_mesh()
        history = HistoryStack()

        state_before = full_topology_snapshot(mesh)
        (new_edge, face_a, face_b), _cmd = run_as_command(
            mesh, history, lambda: mesh.connect_vertices(face, v0, v2)
        )
        state_after_commit = full_topology_snapshot(mesh)

        self.assertNotEqual(state_before, state_after_commit)

        history.undo()
        state_after_undo = full_topology_snapshot(mesh)
        self.assertEqual(state_after_undo, state_before)
        self.assertTrue(mesh.is_valid_face(face), "ursprüngliche Face lebt nach undo() wieder")
        self.assertFalse(mesh.is_valid_face(face_a))
        self.assertFalse(mesh.is_valid_face(face_b))
        self.assertFalse(mesh.is_valid_edge(new_edge))
        self.assertEqual(mesh.face_vertices(face), [v0, v1, v2, v3])
        assert_mesh_invariants(mesh, context="connect undo")

        history.redo()
        state_after_redo = full_topology_snapshot(mesh)
        self.assertEqual(state_after_redo, state_after_commit)
        self.assertTrue(mesh.is_valid_face(face_a))
        self.assertTrue(mesh.is_valid_face(face_b))
        self.assertTrue(mesh.is_valid_edge(new_edge))
        self.assertFalse(mesh.is_valid_face(face))
        assert_mesh_invariants(mesh, context="connect redo")


class TestMultiStepUndoRedoSequence(unittest.TestCase):
    """Zusätzlich zu den Einzel-Operationen: eine Sequenz aus mehreren
    Topologie-Mutationen hintereinander - deckt ab, dass HistoryStack bei
    mehreren MeshStateCommands in Folge korrekt durchsteppt (nicht nur
    ein einzelnes Undo/Redo-Paar)."""

    def test_split_then_collapse_full_undo_sequence(self) -> None:
        mesh, (v0, v1, _v2, _v3), face = build_quad_mesh()
        history = HistoryStack()
        target = mesh._get_or_create_edge(v0, v1)

        state_0 = full_topology_snapshot(mesh)
        (mid, e_a, _e_b), _c1 = run_as_command(mesh, history, lambda: mesh.split_edge(target))
        state_1 = full_topology_snapshot(mesh)
        _survivor, _c2 = run_as_command(mesh, history, lambda: mesh.collapse_edge(e_a))
        state_2 = full_topology_snapshot(mesh)

        self.assertEqual(len(history), 2)

        history.undo()  # rückgängig: collapse_edge(e_a)
        self.assertEqual(full_topology_snapshot(mesh), state_1)
        assert_mesh_invariants(mesh, context="sequence undo 1/2")

        history.undo()  # rückgängig: split_edge(target)
        self.assertEqual(full_topology_snapshot(mesh), state_0)
        assert_mesh_invariants(mesh, context="sequence undo 2/2")

        self.assertFalse(history.can_undo())

        history.redo()
        self.assertEqual(full_topology_snapshot(mesh), state_1)
        history.redo()
        self.assertEqual(full_topology_snapshot(mesh), state_2)
        self.assertFalse(history.can_redo())
        assert_mesh_invariants(mesh, context="sequence full redo")


if __name__ == "__main__":
    unittest.main()
