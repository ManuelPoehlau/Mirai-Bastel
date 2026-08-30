"""WP-02-Follow-up: Viewport-Integration des Command → MoveTool-Pfads.

Der unabhängige Review hatte einen Integrationsfehler identifiziert: Das
`Command.MOVE → MoveTool`-System existierte, wurde im tatsächlichen
Viewport-Workflow aber nicht benutzt — LMB toggelt die Selection weiterhin
zuerst, wodurch ein Klick auf ein bereits selektiertes Element dieses
deselektierte, statt die Interaktion mit dem aktiven MoveTool zu beginnen.

Diese Tests verifizieren die korrigierte Window-Integration headless
(ohne pyglet-Fenster/GL): `_HeadlessModelerWindow` nutzt ausschließlich
den pyglet-freien Fensterzustand (`ModelerWindow._init_state`) und stubbt
die GL-abhängige Geometrie-Erneuerung. Die Event-Handler
(on_key_press/on_mouse_press/on_mouse_drag/on_mouse_release/on_mouse_scroll)
laufen über die realen Default-Bindings — der gesamte Pfad

    Input → Mapping → Command → ToolManager → MoveTool → MoveOperation
    → History

wird also inklusive Binding-Schicht getestet.
"""
import unittest
from pathlib import Path
import sys

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from pyglet.window import key, mouse  # noqa: E402

from mirai_bastel_core import SelectionMode  # noqa: E402

from viewport.app import ModelerWindow  # noqa: E402
from viewport.move_tool import MoveTool  # noqa: E402


class _HeadlessModelerWindow(ModelerWindow):
    """ModelerWindow ohne Fenster/GL: nur der pyglet-freie Logik-Zustand.

    `width`/`height` überschatten die pyglet-Fenster-Properties; die
    GL-abhängige Geometrie-/Caption-Erneuerung wird bewusst als No-op
    geführt (darf in diesen Tests keine Rolle spielen).
    """

    width = 800
    height = 600

    def __init__(self):
        # Bewusst KEIN pyglet.window.Window.__init__ (kein GL-/Fenster-Kontext
        # in Tests); nur der pyglet-freie Logik-Zustand des echten Fensters.
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


def _begin_modal_move(window, vid):
    """Startet den Modal-Pfad: Selection setzen → M → LMB auf das Element."""
    window.scene.selection.set({vid})
    window.on_key_press(key.M, 0)
    px, py = _screen_pos(window, vid)
    window.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
    return int(px), int(py)


class ModalMoveToolIntegrationTests(unittest.TestCase):
    """M → MoveTool → LMB/Drag → Commit/Cancel am echten Window-Pfad."""

    def setUp(self):
        self.w = _HeadlessModelerWindow()
        self.v0 = min(self.w.scene.mesh.all_vertex_ids())

    # --- Test 1: M aktiviert MoveTool ------------------------------------

    def test_m_activates_move_tool(self):
        self.assertIsNone(self.w._tool_manager.active_tool)
        self.w.on_key_press(key.M, 0)
        tool = self.w._tool_manager.active_tool
        self.assertIsInstance(tool, MoveTool)
        self.assertEqual(tool.state.name, "ACTIVE")
        self.assertFalse(self.w._tool_manager.is_interacting)

    def test_second_m_keeps_existing_tool(self):
        self.w.on_key_press(key.M, 0)
        tool = self.w._tool_manager.active_tool
        self.w.on_key_press(key.M, 0)
        self.assertIs(self.w._tool_manager.active_tool, tool)
        self.assertEqual(tool.state.name, "ACTIVE")

    # --- Test 2: aktives MoveTool + LMB (kein Selection-Toggle) ----------

    def test_lmb_with_active_tool_starts_interaction_without_toggle(self):
        # Bereits selektiertes Element: LMB darf es NICHT deselektieren
        # (der Review-Befund), sondern die Interaktion beginnen.
        self.w.scene.selection.set({self.v0})
        self.w.on_key_press(key.M, 0)
        px, py = _screen_pos(self.w, self.v0)
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
        self.assertTrue(self.w._tool_manager.is_interacting)
        self.assertEqual(self.w._drag_mode, "tool")
        self.assertEqual(set(self.w.scene.selection.vertices), {self.v0})
        self.assertEqual(self.w._tool_manager.active_tool.moves, {self.v0})

    def test_lmb_with_active_tool_and_empty_selection_starts_nothing(self):
        self.w.on_key_press(key.M, 0)
        px, py = _screen_pos(self.w, self.v0)
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
        self.assertFalse(self.w._tool_manager.is_interacting)
        self.assertIsNone(self.w._drag_mode)
        self.assertFalse(self.w.scene.selection.vertices)
        self.w.on_mouse_release(int(px), int(py), mouse.LEFT, 0)
        self.assertEqual(len(self.w.scene.history), 0)

    # --- Test 3: mehrere Updates -----------------------------------------

    def test_multiple_updates_move_geometry(self):
        px, py = _begin_modal_move(self.w, self.v0)
        before = _positions(self.w)
        for dx, dy in ((20, 0), (0, 15), (-5, 10)):
            self.w.on_mouse_drag(int(px), int(py), dx, dy, mouse.LEFT, 0)
            self.assertTrue(self.w._tool_manager.is_interacting)
        self.assertNotEqual(_positions(self.w), before)

    # --- Test 4: Commit = genau eine Operation/History-Aktion -------------

    def test_commit_creates_exactly_one_history_action(self):
        px, py = _begin_modal_move(self.w, self.v0)
        for dx, dy in ((20, 0), (0, 15), (-5, 10)):
            self.w.on_mouse_drag(int(px), int(py), dx, dy, mouse.LEFT, 0)
        moved = _positions(self.w)
        self.w.on_mouse_release(int(px), int(py), mouse.LEFT, 0)
        self.assertEqual(len(self.w.scene.history), 1)
        self.assertEqual(_positions(self.w), moved)
        # Modal-State bleibt sauber: Tool weiter aktiv (kein stale Drag).
        self.assertFalse(self.w._tool_manager.is_interacting)
        self.assertIsNone(self.w._drag_mode)
        self.assertEqual(self.w._tool_manager.active_tool.state.name, "ACTIVE")

    def test_commit_is_undoable_and_redoable(self):
        px, py = _begin_modal_move(self.w, self.v0)
        self.w.on_mouse_drag(int(px), int(py), 25, 10, mouse.LEFT, 0)
        self.w.on_mouse_release(int(px), int(py), mouse.LEFT, 0)
        moved = _positions(self.w)
        self.w.scene.history.undo()
        restored = _positions(self.w)
        self.assertNotEqual(restored, moved)
        self.w.scene.history.redo()
        self.assertEqual(_positions(self.w), moved)

    def test_click_without_drag_creates_no_history(self):
        # 0-Delta-Commit: MoveOperation liefert None → kein History-Eintrag.
        px, py = _begin_modal_move(self.w, self.v0)
        self.w.on_mouse_release(int(px), int(py), mouse.LEFT, 0)
        self.assertEqual(len(self.w.scene.history), 0)
        self.assertFalse(self.w._tool_manager.is_interacting)
        self.assertEqual(self.w._tool_manager.active_tool.state.name, "ACTIVE")


    # --- Test 5: Cancel ----------------------------------------------------

    def test_cancel_restores_geometry_without_history(self):
        start = _positions(self.w)
        px, py = _begin_modal_move(self.w, self.v0)
        self.w.on_mouse_drag(int(px), int(py), -200, -200, mouse.LEFT, 0)
        self.assertNotEqual(_positions(self.w), start)
        self.w.on_key_press(key.ESCAPE, 0)
        self.assertEqual(_positions(self.w), start)            # exakt zurück
        self.assertEqual(len(self.w.scene.history), 0)         # keine History
        self.assertFalse(self.w._tool_manager.is_interacting)  # kein stale State
        self.assertIsNone(self.w._drag_mode)
        # Tool-State sauber: modal aktiv, zweites Esc deaktiviert.
        self.assertEqual(self.w._tool_manager.active_tool.state.name, "ACTIVE")
        self.w.on_key_press(key.ESCAPE, 0)
        self.assertIsNone(self.w._tool_manager.active_tool)

    # --- Test 7 / §6: Navigation während Modal -----------------------------

    def test_orbit_during_modal_interaction_cancels_and_keeps_tool(self):
        # RMB cancelt die laufende Interaktion (Geometrie exakt zurück, keine
        # History), das Modal-Tool bleibt aktiv und die Navigation funktioniert.
        px, py = _begin_modal_move(self.w, self.v0)
        self.assertTrue(self.w._tool_manager.is_interacting)
        geometry_before = _positions(self.w)
        self.w.on_mouse_press(int(px) + 50, int(py) + 50, mouse.RIGHT, 0)
        self.assertFalse(self.w._tool_manager.is_interacting)
        self.assertEqual(_positions(self.w), geometry_before)
        self.assertEqual(len(self.w.scene.history), 0)
        self.assertEqual(self.w._drag_mode, "orbit")
        self.assertEqual(self.w._tool_manager.active_tool.state.name, "ACTIVE")
        self.w.on_mouse_drag(int(px) + 50, int(py) + 50, -30, 20, mouse.RIGHT, 0)
        self.w.on_mouse_release(int(px) + 50, int(py) + 50, mouse.RIGHT, 0)
        self.assertIsNone(self.w._drag_mode)
        # Modal-Tool danach weiter benutzbar.
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
        self.assertTrue(self.w._tool_manager.is_interacting)
        self.w.on_mouse_release(int(px), int(py), mouse.LEFT, 0)

    def test_wheel_zoom_during_modal_leaves_tool_untouched(self):
        px, py = _begin_modal_move(self.w, self.v0)
        self.w.on_mouse_release(int(px), int(py), mouse.LEFT, 0)
        distance_before = self.w.camera.distance
        self.w.on_mouse_scroll(400, 300, 0, -1)
        self.assertNotEqual(self.w.camera.distance, distance_before)
        self.assertFalse(self.w._tool_manager.is_interacting)
        self.assertEqual(self.w._tool_manager.active_tool.state.name, "ACTIVE")


class TweakRegressionTests(unittest.TestCase):
    """Bestehendes V1-Tweak-Verhalten bleibt unverändert (Test 6)."""

    def setUp(self):
        self.w = _HeadlessModelerWindow()
        self.v0 = min(self.w.scene.mesh.all_vertex_ids())
        self.v1 = max(self.w.scene.mesh.all_vertex_ids())

    def test_tweak_without_m_selects_and_moves_then_deactivates(self):
        self.assertIsNone(self.w._tool_manager.active_tool)
        px, py = _screen_pos(self.w, self.v0)
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
        # Klick toggelt die Selection und beginnt den Tweak (V1-Verhalten).
        self.assertEqual(set(self.w.scene.selection.vertices), {self.v0})
        self.assertTrue(self.w._tool_manager.is_interacting)
        self.assertTrue(self.w._tweak_tool)
        self.w.on_mouse_drag(int(px), int(py), 15, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(int(px), int(py), mouse.LEFT, 0)
        self.assertEqual(len(self.w.scene.history), 1)
        # Implizites Tweak-Tool ist danach vollständig deaktiviert.
        self.assertIsNone(self.w._tool_manager.active_tool)
        self.assertFalse(self.w._tweak_tool)
        self.assertIsNone(self.w._drag_mode)

    def test_tweak_click_on_selected_element_toggles_off(self):
        self.w.scene.selection.set({self.v0})
        px, py = _screen_pos(self.w, self.v0)
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
        self.assertEqual(set(self.w.scene.selection.vertices), set())
        self.assertFalse(self.w._tool_manager.is_interacting)
        self.assertIsNone(self.w._drag_mode)

    def test_escape_during_tweak_ends_tool_without_leak(self):
        # Regression: Der frühere Stand ließ das implizite Tweak-Tool nach
        # ESC als ACTIVE zurück (stale State) — der LMB-Pfad wäre danach
        # dauerhaft im Modal-Modus hängen geblieben.
        px, py = _screen_pos(self.w, self.v0)
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
        self.w.on_mouse_drag(int(px), int(py), 40, 0, mouse.LEFT, 0)
        self.w.on_key_press(key.ESCAPE, 0)
        self.assertEqual(len(self.w.scene.history), 0)
        self.assertIsNone(self.w._tool_manager.active_tool)  # kein stale Tool
        self.assertFalse(self.w._tweak_tool)
        self.assertIsNone(self.w._drag_mode)
        # Tweak-Flow danach vollständig wiederhergestellt (Klick auf anderes
        # Element: Add-Toggle zur bestehenden Selection + Interaktion).
        p1x, p1y = _screen_pos(self.w, self.v1)
        self.w.on_mouse_press(int(p1x), int(p1y), mouse.LEFT, 0)
        self.assertEqual(set(self.w.scene.selection.vertices), {self.v0, self.v1})
        self.assertTrue(self.w._tool_manager.is_interacting)
        self.w.on_mouse_release(int(p1x), int(p1y), mouse.LEFT, 0)


class SelectionResolutionIntegrationTests(unittest.TestCase):
    """resolve_selection_vertices im Modal-Pfad (§10: Edge-/Face-Selection)."""

    def setUp(self):
        self.w = _HeadlessModelerWindow()
        mesh = self.w.scene.mesh
        self.edge = next(iter(mesh.all_edge_ids()))
        self.face = next(iter(mesh.all_face_ids()))

    def test_modal_move_resolves_edge_selection_to_endpoints(self):
        self.w.on_key_press(key.E, 0)  # Command.SetEdgeMode (kein Tool aktiv)
        self.assertEqual(self.w.selection_mode, SelectionMode.EDGE)
        self.w.scene.selection.set({self.edge})
        self.w.on_key_press(key.M, 0)
        px, py = _screen_pos(self.w, min(self.w.scene.mesh.all_vertex_ids()))
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
        self.assertTrue(self.w._tool_manager.is_interacting)
        endpoints = set(self.w.scene.mesh.edge_vertices(self.edge))
        self.assertEqual(self.w._tool_manager.active_tool.moves, endpoints)
        self.w.on_mouse_drag(int(px), int(py), 10, 5, mouse.LEFT, 0)
        self.w.on_mouse_release(int(px), int(py), mouse.LEFT, 0)
        self.assertEqual(len(self.w.scene.history), 1)
        for vid in endpoints:
            self.assertNotEqual(
                tuple(self.w.scene.mesh.vertex_position(vid)),
                self.w.scene.history._undo_stack[0].start_positions[vid],
            )

    def test_modal_move_resolves_face_selection_to_boundary(self):
        self.w.on_key_press(key.F, 0)  # Command.SetFaceMode
        self.assertEqual(self.w.selection_mode, SelectionMode.FACE)
        self.w.scene.selection.set({self.face})
        self.w.on_key_press(key.M, 0)
        px, py = _screen_pos(self.w, min(self.w.scene.mesh.all_vertex_ids()))
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
        self.assertTrue(self.w._tool_manager.is_interacting)
        boundary = set(self.w.scene.mesh.face_vertices(self.face))
        self.assertEqual(self.w._tool_manager.active_tool.moves, boundary)
        self.w.on_mouse_drag(int(px), int(py), 12, -8, mouse.LEFT, 0)
        self.w.on_mouse_release(int(px), int(py), mouse.LEFT, 0)
        self.assertEqual(len(self.w.scene.history), 1)
        for vid in boundary:
            self.assertNotEqual(
                tuple(self.w.scene.mesh.vertex_position(vid)),
                self.w.scene.history._undo_stack[0].start_positions[vid],
            )


if __name__ == "__main__":
    unittest.main()
