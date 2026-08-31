"""WP-03: Window-Integration des Transform-Tool-Pfads (headless).

Analog test_tool_integration.py (WP-02) wird der reale Window-Pfad ohne
pyglet-Fenster/GL getestet: `_HeadlessModelerWindow` nutzt ausschließlich
den pyglet-freien Fensterzustand (`ModelerWindow._init_state`) und stubbt
die GL-abhängige Geometrie-Erneuerung. Der komplette Pfad

    Input → Mapping → Command → ToolManager → RotateTool/ScaleTool
          → RotateOperation/ScaleOperation → History

läuft über die realen Default-Bindings (R/S), die echten Event-Handler und
die bestehende modale Interaktionslogik.

Verifiziert wird insbesondere:
* R/S aktivieren die Transform-Tools (wie M → MoveTool, WP-02).
* LMB + Drag auf der Selection → Live-Preview; Release → genau ein
  History-Eintrag; Esc → exakter Vorzustand ohne History-Eintrag.
* Modal-Tools bleiben nach Commit/Cancel aktiv; Esc deaktiviert (WP-02-
  Semantik, unverändert).
* Tweak-Move (ohne aktives Tool) bleibt unverändert (WP-02-Regression).
* Die Topology-Lab-Bindings S/R behalten im Kontext "topology" Vorrang.
"""
import unittest
from pathlib import Path
import sys

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from pyglet.window import key, mouse  # noqa: E402

from viewport.app import ModelerWindow  # noqa: E402
from viewport.default_bindings import build_default_bindings  # noqa: E402
from viewport.input_binding import GLOBAL_CONTEXT, TOPOLOGY_CONTEXT, Input  # noqa: E402
from viewport.move_tool import MoveTool  # noqa: E402
from viewport.transform_tool import RotateTool, ScaleTool  # noqa: E402


class _HeadlessModelerWindow(ModelerWindow):
    """ModelerWindow ohne Fenster/GL (WP-02-Muster, siehe test_tool_integration)."""

    width = 800
    height = 600

    def __init__(self):
        # Bewusst KEIN pyglet.window.Window.__init__ (kein GL-/Fenster-Kontext);
        # nur der pyglet-freie Logik-Zustand des echten Fensters.
        self._init_state()

    def _rebuild_geometry(self):
        pass

    def _update_caption(self):
        pass


def _screen_pos(window, vid):
    return window.camera.project_to_screen(
        window.scene.mesh.vertex_position(vid), window.width, window.height
    )


def _positions(window):
    mesh = window.scene.mesh
    return {vid: tuple(mesh.vertex_position(vid)) for vid in mesh.all_vertex_ids()}


def _begin_modal_transform(window, v_ids, activate_key):
    """Selection setzen → Transform-Tool aktivieren → LMB beginnt Interaktion."""
    window.scene.selection.set(set(v_ids))
    window.on_key_press(activate_key, 0)
    px, py = _screen_pos(window, min(v_ids))
    window.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
    return int(px), int(py)


class TransformToolActivationTests(unittest.TestCase):
    def setUp(self):
        self.w = _HeadlessModelerWindow()

    def test_r_activates_rotate_tool(self):
        self.assertIsNone(self.w._tool_manager.active_tool)
        self.w.on_key_press(key.R, 0)
        tool = self.w._tool_manager.active_tool
        self.assertIsInstance(tool, RotateTool)
        self.assertEqual(tool.state.name, "ACTIVE")
        self.assertFalse(self.w._tool_manager.is_interacting)

    def test_s_activates_scale_tool(self):
        self.w.on_key_press(key.S, 0)
        tool = self.w._tool_manager.active_tool
        self.assertIsInstance(tool, ScaleTool)
        self.assertEqual(tool.state.name, "ACTIVE")
        self.assertFalse(self.w._tool_manager.is_interacting)

    def test_second_r_keeps_existing_tool(self):
        self.w.on_key_press(key.R, 0)
        tool = self.w._tool_manager.active_tool
        self.w.on_key_press(key.R, 0)
        self.assertIs(self.w._tool_manager.active_tool, tool)

    def test_tool_replacement_replaces_active_tool(self):
        self.w.on_key_press(key.R, 0)
        self.assertIsInstance(self.w._tool_manager.active_tool, RotateTool)
        self.w.on_key_press(key.M, 0)
        self.assertIsInstance(self.w._tool_manager.active_tool, MoveTool)
        self.w.on_key_press(key.S, 0)
        self.assertIsInstance(self.w._tool_manager.active_tool, ScaleTool)


class ModalRotateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.w = _HeadlessModelerWindow()
        self.v_ids = sorted(self.w.scene.mesh.all_vertex_ids())[:2]

    def test_modal_rotate_commit_creates_single_history_entry(self):
        start = _positions(self.w)
        px, py = _begin_modal_transform(self.w, self.v_ids, key.R)
        tool = self.w._tool_manager.active_tool
        self.assertTrue(self.w._tool_manager.is_interacting)
        # Pivot = Selection Center (Zentroid der beiden Vertices).
        a, b = self.v_ids
        expected_pivot = tuple(
            (start[a][i] + start[b][i]) / 2.0 for i in range(3)
        )
        self.assertEqual(tool.operation.pivot, expected_pivot)
        self.w.on_mouse_drag(px, py, 200, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(px, py, mouse.LEFT, 0)
        self.assertEqual(len(self.w.scene.history), 1)
        self.assertEqual(
            self.w.scene.history._undo_stack[0].description, "Rotate Vertices"
        )
        # Modal-Tool bleibt nach Commit aktiv (WP-02-Semantik).
        self.assertEqual(tool.state.name, "ACTIVE")
        self.assertFalse(self.w._tool_manager.is_interacting)

    def test_modal_rotate_undo_redo(self):
        px, py = _begin_modal_transform(self.w, self.v_ids, key.R)
        self.w.on_mouse_drag(px, py, 200, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(px, py, mouse.LEFT, 0)
        committed = _positions(self.w)
        start = {
            vid: self.w.scene.history._undo_stack[0].start_positions[vid]
            for vid in self.v_ids
        }
        self.w.scene.history.undo()
        for vid in self.v_ids:
            self.assertEqual(self.w.scene.mesh.vertex_position(vid), start[vid])
        self.w.scene.history.redo()
        for vid in self.v_ids:
            self.assertEqual(self.w.scene.mesh.vertex_position(vid), committed[vid])

    def test_modal_rotate_cancel_restores_exact_state(self):
        start = _positions(self.w)
        px, py = _begin_modal_transform(self.w, self.v_ids, key.R)
        self.w.on_mouse_drag(px, py, 300, 0, mouse.LEFT, 0)
        self.w.on_key_press(key.ESCAPE, 0)
        # Exakter Vorzustand, keine History.
        self.assertEqual(_positions(self.w), start)
        self.assertEqual(len(self.w.scene.history), 0)
        # Modal-Tool bleibt aktiv; ein weiteres Esc deaktiviert (WP-02-Semantik).
        self.assertIsInstance(self.w._tool_manager.active_tool, RotateTool)
        self.w.on_key_press(key.ESCAPE, 0)
        self.assertIsNone(self.w._tool_manager.active_tool)

    def test_multiple_drags_commit_as_separate_actions(self):
        # Wie beim MoveTool (WP-02): mehrere Drags hintereinander erzeugen
        # pro Release genau einen History-Eintrag, solange das Tool aktiv ist.
        px, py = _begin_modal_transform(self.w, self.v_ids, key.R)
        self.w.on_mouse_drag(px, py, 100, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(px, py, mouse.LEFT, 0)
        self.w.on_mouse_press(px, py, mouse.LEFT, 0)
        self.w.on_mouse_drag(px, py, 100, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(px, py, mouse.LEFT, 0)
        self.assertEqual(len(self.w.scene.history), 2)


class ModalScaleIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.w = _HeadlessModelerWindow()
        self.v_ids = sorted(self.w.scene.mesh.all_vertex_ids())[:2]

    def test_modal_scale_commit_creates_single_history_entry(self):
        start = _positions(self.w)
        px, py = _begin_modal_transform(self.w, self.v_ids, key.S)
        tool = self.w._tool_manager.active_tool
        self.assertTrue(self.w._tool_manager.is_interacting)
        pivot = tool.operation.pivot  # vor dem Commit erfassen (danach None)
        self.w.on_mouse_drag(px, py, 100, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(px, py, mouse.LEFT, 0)
        self.assertEqual(len(self.w.scene.history), 1)
        self.assertEqual(
            self.w.scene.history._undo_stack[0].description, "Scale Vertices"
        )
        # Zielfaktor nach einem Drag von +100px: exakt 1.5 um den Pivot.
        expected_factor = 1.0 + ScaleTool.SCALE_PER_PIXEL * 100.0
        for vid in self.v_ids:
            expected = tuple(
                pivot[i] + expected_factor * (start[vid][i] - pivot[i])
                for i in range(3)
            )
            pos = self.w.scene.mesh.vertex_position(vid)
            for axis_value, want in zip(pos, expected):
                self.assertAlmostEqual(axis_value, want, places=9)

    def test_modal_scale_cancel_restores_exact_state(self):
        start = _positions(self.w)
        px, py = _begin_modal_transform(self.w, self.v_ids, key.S)
        self.w.on_mouse_drag(px, py, -200, -200, mouse.LEFT, 0)
        self.w.on_key_press(key.ESCAPE, 0)
        self.assertEqual(_positions(self.w), start)
        self.assertEqual(len(self.w.scene.history), 0)


class TransformRegressionTests(unittest.TestCase):
    """WP-02-Verhalten bleibt unverändert (Tweak-Move, Leere-Selection)."""

    def setUp(self):
        self.w = _HeadlessModelerWindow()
        self.v0 = min(self.w.scene.mesh.all_vertex_ids())

    def test_tweak_move_still_works_without_active_tool(self):
        px, py = _screen_pos(self.w, self.v0)
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
        # Tweak: Klick toggelt Selection UND startet bei getroffenem Element
        # die Move-Interaktion (WP-02-Verhalten).
        self.assertEqual(set(self.w.scene.selection.vertices), {self.v0})
        self.assertTrue(self.w._tool_manager.is_interacting)
        self.assertIsInstance(self.w._tool_manager.active_tool, MoveTool)
        self.w.on_mouse_drag(int(px), int(py), 30, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(int(px), int(py), mouse.LEFT, 0)
        self.assertEqual(len(self.w.scene.history), 1)
        self.assertEqual(
            self.w.scene.history._undo_stack[0].description, "Move Vertices"
        )
        # Tweak-Tool beendet sich nach Commit selbst (kein stale Tool).
        self.assertIsNone(self.w._tool_manager.active_tool)

    def test_lmb_with_active_tool_and_empty_selection_starts_nothing(self):
        self.w.on_key_press(key.R, 0)
        px, py = _screen_pos(self.w, self.v0)
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
        self.assertFalse(self.w._tool_manager.is_interacting)
        self.assertEqual(len(self.w.scene.history), 0)
        self.assertEqual(self.w._drag_mode, None)


class TransformBindingContextTests(unittest.TestCase):
    """R/S sind global Rotate/Scale; die Topology-Lab-Keys behalten Vorrang."""

    def test_global_context_bindings(self):
        bs = build_default_bindings()
        self.assertEqual(bs.command_for(Input("key", "r"), GLOBAL_CONTEXT), "Rotate")
        self.assertEqual(bs.command_for(Input("key", "s"), GLOBAL_CONTEXT), "Scale")

    def test_topology_context_bindings_win(self):
        bs = build_default_bindings()
        self.assertEqual(
            bs.command_for(Input("key", "r"), TOPOLOGY_CONTEXT), "EdgeRing"
        )
        self.assertEqual(
            bs.command_for(Input("key", "s"), TOPOLOGY_CONTEXT), "SplitEdge"
        )


if __name__ == "__main__":
    unittest.main()
