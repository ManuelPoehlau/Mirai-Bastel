"""Operation: Vertragstests der Lifecycle-Zustandsmaschine (WP-04-Verification).

Bezug: src/core/operation.py — AD-003 (Interactive Operation Lifecycle).

`Operation` erzwingt den Vertrag

    begin() -> update()* -> commit() | cancel()

an einer einzigen Stelle über Zustands-Guards (OperationStateError). Diese
Suite prüft die Guards explizit mit der einzigen Produktions-Operation
(MoveOperation) als konkreter Sonde — sie testet den dokumentierten
Basisklassen-Vertrag, nicht neue Feature-Semantik:

- jede Lifecycle-Methode ist nur im korrekten Zustand gültig (doppeltes
  begin/commit/cancel, update vor/nach dem Lebenszyklus);
- update()/cancel() berühren die History nie;
- commit() erzeugt genau dann einen Eintrag, wenn sich etwas geändert hat
  (No-op → None, kein History-Eintrag);
- leere Selection ist ein dokumentierter No-op der Operation (Boundary);
- eine Operation ist nach commit()/cancel() wiederverwendbar (erneutes begin()).

Ausführen: python -m unittest tests.test_operation_lifecycle -v
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401 — Produktionspfad src/core/

from core.history import HistoryStack
from core.mesh import Mesh
from core.operation import OperationContext, OperationStateError
from core.operations.move import MoveOperation
from core.selection import Selection, SelectionMode


def _make_scene():
    """Quad-Szene wie in tests.test_core.build_quad_scene (ein Vertex selektiert)."""
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    mesh.add_face([v0, v1, v2, v3])

    selection = Selection()
    selection.mode = SelectionMode.VERTEX
    selection.set({v0})

    history = HistoryStack()
    return mesh, selection, history, v0


def _make_operation(mesh, selection, history) -> MoveOperation:
    context = OperationContext(target=mesh, selection=selection, history=history)
    return MoveOperation(context)


class OperationLifecycleStateMachineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mesh, self.selection, self.history, self.v0 = _make_scene()
        self.op = _make_operation(self.mesh, self.selection, self.history)

    # -- Guards: jede Methode nur im dokumentierten Zustand -------------------

    def test_begin_twice_raises(self) -> None:
        self.op.begin()
        with self.assertRaises(OperationStateError):
            self.op.begin()

    def test_update_without_begin_raises(self) -> None:
        with self.assertRaises(OperationStateError):
            self.op.update(delta=(1.0, 0.0, 0.0))

    def test_update_after_commit_raises(self) -> None:
        self.op.begin()
        self.op.update(delta=(1.0, 0.0, 0.0))
        self.op.commit()
        with self.assertRaises(OperationStateError):
            self.op.update(delta=(1.0, 0.0, 0.0))

    def test_update_after_cancel_raises(self) -> None:
        self.op.begin()
        self.op.cancel()
        with self.assertRaises(OperationStateError):
            self.op.update(delta=(1.0, 0.0, 0.0))

    def test_commit_without_begin_raises(self) -> None:
        with self.assertRaises(OperationStateError):
            self.op.commit()

    def test_commit_twice_raises(self) -> None:
        self.op.begin()
        self.op.update(delta=(1.0, 0.0, 0.0))
        self.op.commit()
        with self.assertRaises(OperationStateError):
            self.op.commit()

    def test_cancel_without_begin_raises(self) -> None:
        with self.assertRaises(OperationStateError):
            self.op.cancel()

    def test_cancel_twice_raises(self) -> None:
        self.op.begin()
        self.op.cancel()
        with self.assertRaises(OperationStateError):
            self.op.cancel()
# -- History-Grenzen ------------------------------------------------------

    def test_update_and_cancel_never_touch_history(self) -> None:
        self.op.begin()
        self.op.update(delta=(5.0, 0.0, 0.0))
        self.op.update(delta=(-5.0, 0.0, 0.0))
        self.assertEqual(len(self.history), 0)
        self.op.cancel()
        self.assertEqual(len(self.history), 0)

    def test_commit_is_only_history_grenze(self) -> None:
        self.op.begin()
        for _ in range(5):
            self.op.update(delta=(0.1, 0.0, 0.0))
        self.assertEqual(len(self.history), 0)
        self.op.commit()
        self.assertEqual(len(self.history), 1)

    # -- No-op-/Boundary-Semantik ---------------------------------------------

    def test_noop_commit_returns_none_without_history(self) -> None:
        # begin() + commit() ohne update(): nichts geändert → None, kein Eintrag.
        self.op.begin()
        self.assertIsNone(self.op.commit())
        self.assertEqual(len(self.history), 0)

    def test_zero_delta_commit_returns_none(self) -> None:
        self.op.begin()
        self.op.update(delta=(0.0, 0.0, 0.0))
        self.assertIsNone(self.op.commit())
        self.assertEqual(len(self.history), 0)

    def test_empty_selection_is_noop_operation(self) -> None:
        # Leere Selection ist dokumentiert als No-op der Operation selbst
        # (die Tools guardieren früher). Kein Crash, kein Eintrag.
        self.selection.set(set())
        empty_op = _make_operation(self.mesh, self.selection, self.history)
        empty_op.begin()
        empty_op.update(delta=(1.0, 0.0, 0.0))
        self.assertIsNone(empty_op.commit())
        self.assertEqual(len(self.history), 0)

    # -- Wiederverwendbarkeit --------------------------------------------------

    def test_operation_reusable_after_commit(self) -> None:
        self.op.begin()
        self.op.update(delta=(1.0, 0.0, 0.0))
        self.op.commit()
        self.assertFalse(self.op.is_active)
        # Erneutes begin() auf derselben Instanz ist erlaubt.
        self.op.begin()
        self.op.update(delta=(0.0, 1.0, 0.0))
        self.op.commit()
        self.assertEqual(len(self.history), 2)

    def test_operation_reusable_after_cancel(self) -> None:
        self.op.begin()
        self.op.cancel()
        self.assertFalse(self.op.is_active)
        self.op.begin()
        self.op.update(delta=(1.0, 0.0, 0.0))
        command = self.op.commit()
        self.assertIsNotNone(command)
        self.assertEqual(len(self.history), 1)


if __name__ == "__main__":
    unittest.main()