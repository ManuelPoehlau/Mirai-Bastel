"""WP-02: MoveTool × MoveOperation-Integration.

Verifiziert:
* MoveTool nutzt die bestehende Core-`MoveOperation`.
* mehrere update()-Aufrufe verändern den Zustand korrekt.
* Commit erzeugt genau einen History-Schritt.
* Cancel stellt den exakten Ausgangszustand wieder her und erzeugt
  keinen History-Schritt.
"""
import unittest
from pathlib import Path
import sys

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from mirai_bastel_core import Mesh, Selection, SelectionMode, HistoryStack, Scene  # noqa: E402

from viewport.move_tool import MoveTool


def _make_scene():
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    mesh.add_vertex((1.0, 0.0, 0.0))
    mesh.add_vertex((0.0, 1.0, 0.0))
    mesh.add_vertex((2.0, 2.0, 0.0))
    sel = Selection()
    sel.mode = SelectionMode.VERTEX
    sel.set(set(mesh.all_vertex_ids()))
    scene = Scene()
    scene.mesh = mesh
    scene.selection = sel
    history = HistoryStack()
    scene.history = history
    return scene, history


class _StubCamera:
    """Kamera-Stub: Pixel-Delta wird 1:1 als Welt-Delta interpretiert."""

    def screen_delta_to_world(self, anchor_pos, dx, dy, width, height):
        # Einfacher Ersatz: dx→x, dy→y (Test-only, keine echte Projektion).
        return (dx, dy, 0.0)


class MoveToolIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.scene, self.history = _make_scene()
        self.tool = MoveTool(self.scene, _StubCamera())

    def _positions(self):
        mesh = self.scene.mesh
        return tuple(mesh.vertex_position(v) for v in mesh.all_vertex_ids())

    def test_tool_uses_move_operation(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.scene.mesh.all_vertex_ids()))
        self.assertIsNotNone(self.tool.operation)
        self.assertEqual(type(self.tool.operation).__name__, "MoveOperation")
        self.tool.cancel()
        self.tool.deactivate()

    def test_updates_move_vertices(self):
        start = self._positions()
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.scene.mesh.all_vertex_ids()))
        self.tool.update(dx=1.0, dy=0.0, width=800, height=600)
        self.tool.update(dx=0.0, dy=1.0, width=800, height=600)
        after = self._positions()
        self.assertNotEqual(start, after)
        # v0 wurde um (1,1,0) verschoben
        self.assertEqual(tuple(after[0]), (1.0, 1.0, 0.0))
        self.tool.commit()
        self.tool.deactivate()

    def test_commit_creates_single_history_step(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.scene.mesh.all_vertex_ids()))
        self.tool.update(dx=1.0, dy=0.0, width=800, height=600)
        self.tool.update(dx=1.0, dy=0.0, width=800, height=600)
        self.tool.commit()
        self.tool.deactivate()
        self.assertEqual(len(self.history._undo_stack), 1)

    def test_cancel_restores_exact_state(self):
        start = self._positions()
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.scene.mesh.all_vertex_ids()))
        self.tool.update(dx=5.0, dy=5.0, width=800, height=600)
        self.tool.cancel()
        self.tool.deactivate()
        after = self._positions()
        self.assertEqual(start, after)

    def test_cancel_creates_no_history_step(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.scene.mesh.all_vertex_ids()))
        self.tool.update(dx=5.0, dy=5.0, width=800, height=600)
        self.tool.cancel()
        self.tool.deactivate()
        self.assertEqual(len(self.history._undo_stack), 0)

    def test_multiple_updates_single_step(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.scene.mesh.all_vertex_ids()))
        for _ in range(5):
            self.tool.update(dx=0.1, dy=0.0, width=800, height=600)
        self.tool.commit()
        self.tool.deactivate()
        self.assertEqual(len(self.history._undo_stack), 1)

    def test_commit_undo_redo(self):
        self.tool.activate()
        self.tool.begin(vertex_ids=set(self.scene.mesh.all_vertex_ids()))
        self.tool.update(dx=3.0, dy=0.0, width=800, height=600)
        self.tool.commit()
        self.tool.deactivate()
        start = self._positions()
        self.history.undo()
        after_undo = self._positions()
        self.assertNotEqual(start, after_undo)
        self.history.redo()
        after_redo = self._positions()
        self.assertEqual(start, after_redo)


if __name__ == "__main__":
    unittest.main()
