"""Symmetrisches Move — WP-SYM-01 Slice 2.

Bezug: docs/architecture/AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md
§2.4, docs/architecture/SLICE2_CLAUDE_CODE_HANDOFF.md §5.

Testet auf Operation-Ebene (wie tests/test_transform_operations.py und
tests/test_operation_lifecycle.py) — `MoveOperation` direkt gegen
`OperationContext`, ohne Tool-/Kamera-Schicht. `context.params["symmetry"]`
wird hier so aufgebaut, wie `MoveTool._on_begin()` es in der Produktion tut
(über `mirai.symmetry.mirrored_selection()`/`vertex_correspondence()`) —
siehe `_symmetric_context()` unten, bewusst dieselbe Logik dupliziert statt
Tool-Internals zu reimportieren, analog zum bestehenden Testmuster.

Ausführen mit: pytest tests/test_symmetric_move.py
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401 — Produktionspfad src/core, src/mirai

from core.history import HistoryStack
from core.mesh import Mesh, SymmetryDefinition
from core.operation import Operation, OperationContext
from core.operations.move import MoveOperation
from core.operations.transform import RotateOperation, ScaleOperation
from core.selection import Selection, SelectionMode
from mirai.symmetry import CorrespondenceState, mirrored_selection, vertex_correspondence

PLANE_POINT = (0.0, 0.0, 0.0)
PLANE_NORMAL = (1.0, 0.0, 0.0)


def _close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _build_mesh():
    """Symmetrisches Testmesh: ein Mirror-Paar (left/right) + eine Seam-Edge.

    left/right liegen exakt an x=-2/x=2 (PAIRED). seam0/seam1 liegen exakt
    auf der Plane x=0 und sind Endpunkte der deklarierten Seam-Edge (SEAM).
    """
    mesh = Mesh()
    left = mesh.add_vertex((-2.0, 0.0, 0.0))
    right = mesh.add_vertex((2.0, 0.0, 0.0))
    seam0 = mesh.add_vertex((0.0, 0.0, 0.0))
    seam1 = mesh.add_vertex((0.0, 1.0, 0.0))
    seam_edge = mesh.add_edge(seam0, seam1)
    mesh.symmetry_definition = SymmetryDefinition(
        plane_point=PLANE_POINT, plane_normal=PLANE_NORMAL, seam_edges=frozenset({seam_edge})
    )
    ids = {"left": left, "right": right, "seam0": seam0, "seam1": seam1, "seam_edge": seam_edge}
    return mesh, ids


def _symmetric_context(mesh: Mesh, vertex_ids: set, history: HistoryStack) -> OperationContext:
    """Baut den OperationContext exakt so, wie MoveTool._on_begin() es tut
    (siehe src/mirai/interaction/tools/move.py) — Auflösung der gespiegelten
    Partner + Seam-Klassifikation, übergeben über params["symmetry"]."""
    mirrored_vertex_ids = mirrored_selection(mesh, vertex_ids)
    correspondence = vertex_correspondence(mesh)
    seam_vertex_ids = {
        vid
        for vid in vertex_ids
        if correspondence.get(vid) is not None and correspondence[vid].state is CorrespondenceState.SEAM
    }
    affected = set(vertex_ids) | mirrored_vertex_ids

    selection = Selection()
    selection.mode = SelectionMode.VERTEX
    selection.set(affected)

    return OperationContext(
        target=mesh,
        selection=selection,
        history=history,
        params={
            "symmetry": {
                "plane_normal": mesh.symmetry_definition.plane_normal,
                "mirrored_vertex_ids": mirrored_vertex_ids,
                "seam_vertex_ids": seam_vertex_ids,
            }
        },
    )


class SymmetricMoveTests(unittest.TestCase):
    def test_mirrored_partner_gets_reflected_delta(self):
        mesh, ids = _build_mesh()
        history = HistoryStack()
        context = _symmetric_context(mesh, {ids["left"]}, history)
        op = MoveOperation(context)
        op.begin()

        op.update(delta=(1.0, 2.0, 3.0))

        # Quellseite: normales delta.
        self.assertTrue(_close(mesh.vertex_position(ids["left"]), (-1.0, 2.0, 3.0)))
        # Partnerseite: an der Normalen gespiegeltes delta, NICHT dasselbe delta.
        self.assertTrue(_close(mesh.vertex_position(ids["right"]), (1.0, 2.0, 3.0)))

    def test_mirrored_pair_stays_exact_mirror_after_move(self):
        """Die Symmetrie-Invariante selbst: nach dem Move ist right weiterhin
        exakt die Spiegelung von left an der Plane (nicht nur irgendeine
        Bewegung) — verifiziert über mirror_position()."""
        from mirai.symmetry import mirror_position

        mesh, ids = _build_mesh()
        history = HistoryStack()
        context = _symmetric_context(mesh, {ids["left"]}, history)
        op = MoveOperation(context)
        op.begin()
        op.update(delta=(0.5, -1.5, 4.0))

        left_pos = mesh.vertex_position(ids["left"])
        right_pos = mesh.vertex_position(ids["right"])
        self.assertEqual(mirror_position(left_pos, PLANE_POINT, PLANE_NORMAL), right_pos)

    def test_incremental_updates_respected_for_mirrored_partner(self):
        """AD-003/Handoff §7: mehrere update()-Aufrufe in Folge, nicht nur
        der erste, müssen die Spiegel-Mechanik korrekt anwenden."""
        mesh, ids = _build_mesh()
        history = HistoryStack()
        context = _symmetric_context(mesh, {ids["left"]}, history)
        op = MoveOperation(context)
        op.begin()

        op.update(delta=(1.0, 0.0, 0.0))
        op.update(delta=(1.0, 0.0, 0.0))

        self.assertTrue(_close(mesh.vertex_position(ids["left"]), (0.0, 0.0, 0.0)))
        # Zwei Spiegelungen von (1,0,0) an Normale (1,0,0): je (-1,0,0).
        self.assertTrue(_close(mesh.vertex_position(ids["right"]), (0.0, 0.0, 0.0)))

    def test_single_history_entry_and_undo_restores_both_sides(self):
        mesh, ids = _build_mesh()
        history = HistoryStack()
        context = _symmetric_context(mesh, {ids["left"]}, history)
        op = MoveOperation(context)
        op.begin()
        start_left = mesh.vertex_position(ids["left"])
        start_right = mesh.vertex_position(ids["right"])

        op.update(delta=(1.0, 2.0, 3.0))
        end_left = mesh.vertex_position(ids["left"])
        end_right = mesh.vertex_position(ids["right"])
        command = op.commit()

        self.assertIsNotNone(command)
        self.assertEqual(len(history), 1)

        history.undo()
        self.assertEqual(mesh.vertex_position(ids["left"]), start_left)
        self.assertEqual(mesh.vertex_position(ids["right"]), start_right)

        history.redo()
        self.assertEqual(mesh.vertex_position(ids["left"]), end_left)
        self.assertEqual(mesh.vertex_position(ids["right"]), end_right)

    def test_cancel_restores_exact_start_on_both_sides(self):
        mesh, ids = _build_mesh()
        history = HistoryStack()
        context = _symmetric_context(mesh, {ids["left"]}, history)
        op = MoveOperation(context)
        op.begin()
        start_left = mesh.vertex_position(ids["left"])
        start_right = mesh.vertex_position(ids["right"])

        op.update(delta=(5.0, -3.0, 2.0))
        op.cancel()

        self.assertEqual(mesh.vertex_position(ids["left"]), start_left)
        self.assertEqual(mesh.vertex_position(ids["right"]), start_right)
        self.assertEqual(len(history), 0)

    def test_seam_vertex_move_stays_exactly_on_plane(self):
        mesh, ids = _build_mesh()
        history = HistoryStack()
        context = _symmetric_context(mesh, {ids["seam0"]}, history)
        op = MoveOperation(context)
        op.begin()

        # delta mit Komponente entlang der Normalen (x) UND in der Plane (y,z).
        op.update(delta=(3.0, 1.0, 0.0))
        op.update(delta=(-1.0, 0.5, 2.0))

        pos = mesh.vertex_position(ids["seam0"])
        signed_distance = (pos[0] - PLANE_POINT[0]) * PLANE_NORMAL[0]
        self.assertEqual(signed_distance, 0.0, "Seam-Vertex muss exakt auf der Plane bleiben (INV-2)")
        # y/z-Komponente ist unconstrained und muss die volle Bewegung zeigen.
        self.assertTrue(_close((pos[1], pos[2]), (1.5, 2.0)))

    def test_move_without_active_symmetry_is_unaffected(self):
        """Regression: ohne symmetry_definition verhält sich MoveOperation
        exakt wie vor diesem Slice (kein params["symmetry"] gesetzt)."""
        mesh = Mesh()
        v0 = mesh.add_vertex((1.0, 1.0, 1.0))
        history = HistoryStack()
        selection = Selection()
        selection.mode = SelectionMode.VERTEX
        selection.set({v0})
        context = OperationContext(target=mesh, selection=selection, history=history)

        op = MoveOperation(context)
        op.begin()
        op.update(delta=(2.0, 0.0, 0.0))

        self.assertTrue(_close(mesh.vertex_position(v0), (3.0, 1.0, 1.0)))

    def test_explicitly_selecting_both_sides_moves_both_by_same_delta(self):
        """Randfall Handoff §3.2: Partner ist zusätzlich selbst explizit
        selektiert. Auflösung (siehe core.operations.move-Modul-Docstring):
        die explizite Auswahl gewinnt — kein Vertex wird hier als
        "mirrored partner" behandelt, beide bekommen dasselbe, unmodifizierte
        delta."""
        mesh, ids = _build_mesh()
        history = HistoryStack()
        explicit_selection = {ids["left"], ids["right"]}

        mirrored = mirrored_selection(mesh, explicit_selection)
        self.assertEqual(mirrored, set(), "kein Partner wird zusätzlich aufgelöst, wenn beide Seiten bereits gewählt sind")

        context = _symmetric_context(mesh, explicit_selection, history)
        op = MoveOperation(context)
        op.begin()
        op.update(delta=(1.0, 2.0, 3.0))

        self.assertTrue(_close(mesh.vertex_position(ids["left"]), (-1.0, 2.0, 3.0)))
        self.assertTrue(_close(mesh.vertex_position(ids["right"]), (3.0, 2.0, 3.0)))


class SupportsSymmetryFlagTests(unittest.TestCase):
    """AD-SYM-02 §2.3: Unterstützungsgrad-Aussage, abfragbar vor begin()."""

    def test_default_is_false_on_base_operation(self):
        self.assertFalse(Operation.supports_symmetry)

    def test_move_supports_symmetry(self):
        self.assertTrue(MoveOperation.supports_symmetry)

    def test_rotate_and_scale_do_not_support_symmetry_yet(self):
        """Not in scope (Handoff §4): Rotate/Scale symmetrisch bleibt einem
        späteren Slice vorbehalten — beide melden weiterhin False."""
        self.assertFalse(RotateOperation.supports_symmetry)
        self.assertFalse(ScaleOperation.supports_symmetry)

    def test_queryable_before_any_instance_exists(self):
        """Klassenattribut — abfragbar ohne begin(), ohne Instanz."""
        self.assertIs(MoveOperation.supports_symmetry, True)


if __name__ == "__main__":
    unittest.main()
