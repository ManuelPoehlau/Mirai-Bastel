"""Transform-Operations: RotateOperation/ScaleOperation auf Produktions-Core.

Migriert aus `experiments/mirai_bastel_core_V1` + Experiment-Tests
(`test_transform_operations.py`) und läuft gegen den per ADR-001
promovierten Produktions-Core-Pfad (`src/core`).

Verifiziert auf Ebene der Core-Operationen:
- Rotate/Scale-Mathematik um einen fixen Pivot (Default: Selection Center)
- inkrementelle update()-Semantik (Winkel addieren sich, Faktoren
  multiplizieren sich)
- Commit erzeugt genau einen History-Eintrag; No-op-Commit liefert None
- Cancel stellt die exakten Ausgangspositionen wieder her (kein History)
- Undo/Redo ist über Start-/Endpositionen exakt
"""

from __future__ import annotations

import math
import unittest

import tests._bootstrap  # noqa: F401

from core import (
    HistoryStack,
    Mesh,
    OperationContext,
    RotateOperation,
    ScaleOperation,
    Selection,
    SelectionMode,
)

Z_AXIS = (0.0, 0.0, 1.0)


def _close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class TransformOperationTestBase(unittest.TestCase):
    def _make_mesh(self):
        mesh = Mesh()
        ids = (
            mesh.add_vertex((2.0, 0.0, 0.0)),
            mesh.add_vertex((1.0, 0.0, 0.0)),
            mesh.add_vertex((0.0, 3.0, 0.0)),
        )
        return mesh, ids

    def _begin(self, operation_cls, mesh, ids, history, pivot=None):
        sel = Selection()
        sel.mode = SelectionMode.VERTEX
        sel.set(set(ids))
        context = OperationContext(
            target=mesh,
            selection=sel,
            history=history,
            params={"pivot": pivot} if pivot is not None else {},
        )
        operation = operation_cls(context)
        operation.begin()
        return operation

    def _positions(self, mesh, ids):
        return {vid: mesh.vertex_position(vid) for vid in ids}


class RotateOperationTests(TransformOperationTestBase):
    def test_rotate_around_z_at_explicit_pivot(self):
        mesh, (v0, v1, _) = self._make_mesh()
        history = HistoryStack()
        op = self._begin(RotateOperation, mesh, (v0, v1), history, pivot=(1.0, 0.0, 0.0))
        op.update(axis=Z_AXIS, angle=math.pi / 2)
        self.assertTrue(_close(mesh.vertex_position(v0), (1.0, 1.0, 0.0)))
        self.assertTrue(_close(mesh.vertex_position(v1), (1.0, 0.0, 0.0)))

    def test_default_pivot_is_selection_center(self):
        mesh, (v0, v1, v2) = self._make_mesh()
        op = self._begin(RotateOperation, mesh, (v0, v1, v2), HistoryStack())
        self.assertTrue(_close(op.pivot, (1.0, 1.0, 0.0)))

    def test_pivot_stays_fixed_during_interaction(self):
        mesh, ids = self._make_mesh()
        op = self._begin(RotateOperation, mesh, ids, HistoryStack())
        expected_pivot = op.pivot
        op.update(axis=Z_AXIS, angle=0.4)
        op.update(axis=Z_AXIS, angle=0.6)
        self.assertEqual(op.pivot, expected_pivot)

    def test_incremental_updates_accumulate(self):
        mesh_a, ids_a = self._make_mesh()
        op_a = self._begin(RotateOperation, mesh_a, ids_a, HistoryStack())
        op_a.update(axis=Z_AXIS, angle=math.pi / 2)
        mesh_b, ids_b = self._make_mesh()
        op_b = self._begin(RotateOperation, mesh_b, ids_b, HistoryStack())
        op_b.update(axis=Z_AXIS, angle=math.pi / 4)
        op_b.update(axis=Z_AXIS, angle=math.pi / 4)
        for va, vb in zip(ids_a, ids_b):
            self.assertTrue(
                _close(mesh_a.vertex_position(va), mesh_b.vertex_position(vb))
            )

    def test_commit_description_and_history(self):
        mesh, ids = self._make_mesh()
        history = HistoryStack()
        op = self._begin(RotateOperation, mesh, ids, history)
        op.update(axis=Z_AXIS, angle=0.4)
        command = op.commit()
        self.assertIsNotNone(command)
        self.assertEqual(len(history), 1)
        self.assertEqual(command.description, "Rotate Vertices")

    def test_commit_undo_redo_exact(self):
        mesh, ids = self._make_mesh()
        history = HistoryStack()
        op = self._begin(RotateOperation, mesh, ids, history, pivot=(1.0, 0.0, 0.0))
        start = self._positions(mesh, ids)
        op.update(axis=Z_AXIS, angle=math.pi / 2)
        committed = self._positions(mesh, ids)
        op.commit()
        history.undo()
        for vid in ids:
            self.assertEqual(mesh.vertex_position(vid), start[vid])
        history.redo()
        for vid in ids:
            self.assertEqual(mesh.vertex_position(vid), committed[vid])

    def test_noop_commit_returns_none(self):
        mesh, ids = self._make_mesh()
        history = HistoryStack()
        op = self._begin(RotateOperation, mesh, ids, history)
        op.update(axis=Z_AXIS, angle=0.0)
        self.assertIsNone(op.commit())
        self.assertEqual(len(history), 0)

    def test_cancel_restores_exact_start(self):
        mesh, ids = self._make_mesh()
        history = HistoryStack()
        op = self._begin(RotateOperation, mesh, ids, history)
        start = self._positions(mesh, ids)
        op.update(axis=Z_AXIS, angle=1.0)
        op.cancel()
        for vid in ids:
            self.assertEqual(mesh.vertex_position(vid), start[vid])
        self.assertEqual(len(history), 0)

    def test_zero_axis_raises(self):
        mesh, ids = self._make_mesh()
        op = self._begin(RotateOperation, mesh, ids, HistoryStack())
        with self.assertRaises(ValueError):
            op.update(axis=(0.0, 0.0, 0.0), angle=0.5)


class ScaleOperationTests(TransformOperationTestBase):
    def test_scale_uniform_around_explicit_pivot(self):
        mesh, (v0, v1, _) = self._make_mesh()
        history = HistoryStack()
        op = self._begin(ScaleOperation, mesh, (v0, v1), history, pivot=(1.0, 0.0, 0.0))
        op.update(factor=2.0)
        self.assertTrue(_close(mesh.vertex_position(v0), (3.0, 0.0, 0.0)))
        self.assertTrue(_close(mesh.vertex_position(v1), (1.0, 0.0, 0.0)))

    def test_scale_incremental_multiplies(self):
        mesh, ids = self._make_mesh()
        v0 = ids[0]
        history = HistoryStack()
        op = self._begin(ScaleOperation, mesh, (v0,), history, pivot=(0.0, 0.0, 0.0))
        op.update(factor=2.0)
        op.update(factor=2.0)
        self.assertTrue(_close(mesh.vertex_position(v0), (8.0, 0.0, 0.0)))
        self.assertEqual(len(history), 0)

    def test_scale_per_axis_triple(self):
        mesh, ids = self._make_mesh()
        v0 = ids[0]
        op = self._begin(ScaleOperation, mesh, (v0,), HistoryStack(), pivot=(0.0, 0.0, 0.0))
        op.update(factor=(2.0, 1.0, 1.0))
        self.assertTrue(_close(mesh.vertex_position(v0), (4.0, 0.0, 0.0)))

    def test_scale_commit_description_and_history(self):
        mesh, ids = self._make_mesh()
        history = HistoryStack()
        op = self._begin(ScaleOperation, mesh, ids, history)
        op.update(factor=1.5)
        command = op.commit()
        self.assertIsNotNone(command)
        self.assertEqual(len(history), 1)
        self.assertEqual(command.description, "Scale Vertices")

    def test_scale_commit_undo_redo_exact(self):
        mesh, ids = self._make_mesh()
        history = HistoryStack()
        op = self._begin(ScaleOperation, mesh, ids, history, pivot=(1.0, 0.0, 0.0))
        start = self._positions(mesh, ids)
        op.update(factor=3.0)
        committed = self._positions(mesh, ids)
        op.commit()
        history.undo()
        for vid in ids:
            self.assertEqual(mesh.vertex_position(vid), start[vid])
        history.redo()
        for vid in ids:
            self.assertEqual(mesh.vertex_position(vid), committed[vid])

    def test_scale_noop_commit_returns_none(self):
        mesh, ids = self._make_mesh()
        history = HistoryStack()
        op = self._begin(ScaleOperation, mesh, ids, history)
        op.update(factor=1.0)
        self.assertIsNone(op.commit())
        self.assertEqual(len(history), 0)

    def test_scale_cancel_restores_exact_start(self):
        mesh, ids = self._make_mesh()
        history = HistoryStack()
        op = self._begin(ScaleOperation, mesh, ids, history)
        start = self._positions(mesh, ids)
        op.update(factor=0.2)
        op.cancel()
        for vid in ids:
            self.assertEqual(mesh.vertex_position(vid), start[vid])
        self.assertEqual(len(history), 0)

    def test_scale_invalid_factor_raises(self):
        mesh, ids = self._make_mesh()
        op = self._begin(ScaleOperation, mesh, ids, HistoryStack())
        with self.assertRaises(ValueError):
            op.update(factor=(1.0, 2.0))


if __name__ == "__main__":
    unittest.main()