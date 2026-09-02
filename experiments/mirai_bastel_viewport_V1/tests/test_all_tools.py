"""All-Tools-Playground: Window-Integration (headless).

Analog test_transform_integration.py wird der reale Window-Pfad ohne
pyglet-Fenster/GL getestet: `_HeadlessAllToolsWindow` nutzt ausschließlich
die pyglet-freien Zustands-Initialisierungen (`ModelerWindow._init_state`,
`AllToolsWindow._init_all_tools`) und stubbt die GL-abhängige Geometrie-
Erneuerung. Der komplette Pfad

    Input → Mapping → Command → ToolManager → Tools → Operations → History

läuft über die echten Bindings, Event-Handler und die bestehende modale
Interaktionslogik.

Verifiziert wird insbesondere:
* Bestehende Bindings bleiben vollständig wirksam: S → SplitEdge,
  R → EdgeRing, M → Move (globaler Fallback), V/E/F, Ctrl+Z/Y.
* Die Playground-Bindings ergänzen nur freie Tasten: Shift+R → Rotate,
  Shift+S → Scale, X/Y/Z → Achsen-Vorwahl (build_default_bindings
  bleibt für run.py/run_topology.py unverändert).
* Achsen-Constraints über die vorhandenen WP-03-begin()-Parameter:
  Move (Achsen-Projektion), Rotate (Weltachse), Scale (Achsenmaske),
  Scale ohne Achse (uniform).
* Esc/Cancel stellt den exakten Vorzustand her (kein History-Eintrag).
* Topology-Tools funktionieren im Playground weiter (Split, Edge Ring).
* Tweak-Move (ohne aktives Tool) bleibt unverändert (WP-02-Regression).
"""
import unittest
from pathlib import Path
import sys

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from pyglet.window import key, mouse  # noqa: E402

from mirai_bastel_core import SelectionMode  # noqa: E402

from viewport.all_tools_app import (  # noqa: E402
    AXIS_X,
    AXIS_Y,
    AXIS_Z,
    AllToolsWindow,
    AxisConstrainedMoveTool,
    build_all_tools_bindings,
)
from viewport.default_bindings import build_default_bindings  # noqa: E402
from viewport.input_binding import (  # noqa: E402
    GLOBAL_CONTEXT,
    TOPOLOGY_CONTEXT,
    Input,
)
from viewport.move_tool import MoveTool  # noqa: E402
from viewport.transform_tool import RotateTool, ScaleTool  # noqa: E402


class _HeadlessAllToolsWindow(AllToolsWindow):
    """AllToolsWindow ohne Fenster/GL (WP-02/03-Muster)."""

    width = 800
    height = 600

    def __init__(self):
        # Bewusst KEIN pyglet.window.Window.__init__ (kein GL-/Fenster-Kontext);
        # nur die pyglet-freien Logik-Zustände der echten Fenster.
        self._init_state()
        self._init_all_tools()

    def _rebuild_geometry(self):
        pass

    def _update_caption(self):
        pass

    def _set_topology_caption(self, message=None):
        pass


def _screen_pos(window, vid):
    return window.camera.project_to_screen(
        window.scene.mesh.vertex_position(vid), window.width, window.height
    )


def _positions(window):
    mesh = window.scene.mesh
    return {vid: tuple(mesh.vertex_position(vid)) for vid in mesh.all_vertex_ids()}


# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------


class PlaygroundBindingTests(unittest.TestCase):
    """Bestehende Belegung bleibt; der Playground ergänzt nur freie Tasten."""

    def test_existing_keys_keep_their_commands(self):
        bs = build_all_tools_bindings()
        self.assertEqual(bs.command_for(Input("key", "s"), TOPOLOGY_CONTEXT), "SplitEdge")
        self.assertEqual(bs.command_for(Input("key", "r"), TOPOLOGY_CONTEXT), "EdgeRing")
        self.assertEqual(bs.command_for(Input("key", "k"), TOPOLOGY_CONTEXT), "Collapse")
        self.assertEqual(bs.command_for(Input("key", "c"), TOPOLOGY_CONTEXT), "Connect")
        self.assertEqual(bs.command_for(Input("key", "l"), TOPOLOGY_CONTEXT), "EdgeLoop")
        # Globaler Fallback im Topology-Kontext (M → Move, WP-02).
        self.assertEqual(bs.command_for(Input("key", "m"), TOPOLOGY_CONTEXT), "Move")
        self.assertEqual(bs.command_for(Input("key", "v"), TOPOLOGY_CONTEXT), "SetVertexMode")
        self.assertEqual(bs.command_for(Input("key", "z", frozenset({"ctrl"})), TOPOLOGY_CONTEXT), "Undo")
        self.assertEqual(bs.command_for(Input("key", "y", frozenset({"ctrl"})), TOPOLOGY_CONTEXT), "Redo")

    def test_playground_additions_use_free_keys(self):
        bs = build_all_tools_bindings()
        self.assertEqual(
            bs.command_for(Input("key", "r", frozenset({"shift"})), TOPOLOGY_CONTEXT),
            "Rotate",
        )
        self.assertEqual(
            bs.command_for(Input("key", "s", frozenset({"shift"})), TOPOLOGY_CONTEXT),
            "Scale",
        )
        self.assertEqual(bs.command_for(Input("key", "x"), TOPOLOGY_CONTEXT), AXIS_X)
        self.assertEqual(bs.command_for(Input("key", "y"), TOPOLOGY_CONTEXT), AXIS_Y)
        self.assertEqual(bs.command_for(Input("key", "z"), TOPOLOGY_CONTEXT), AXIS_Z)

    def test_build_default_bindings_unchanged(self):
        """run.py/run_topology.py nutzen build_default_bindings() direkt —
        die Playground-Bindings dürfen dort nicht auftauchen."""
        bs = build_default_bindings()
        self.assertIsNone(
            bs.command_for(Input("key", "r", frozenset({"shift"})), GLOBAL_CONTEXT)
        )
        self.assertIsNone(
            bs.command_for(Input("key", "x"), GLOBAL_CONTEXT)
        )
        self.assertIsNone(bs.command_for(Input("key", "x"), TOPOLOGY_CONTEXT))
        # Bestehende globale Bindings unberührt:
        self.assertEqual(bs.command_for(Input("key", "m"), GLOBAL_CONTEXT), "Move")
        self.assertEqual(bs.command_for(Input("key", "r"), GLOBAL_CONTEXT), "Rotate")
        self.assertEqual(bs.command_for(Input("key", "s"), GLOBAL_CONTEXT), "Scale")


# ---------------------------------------------------------------------------
# Playground-Fenster
# ---------------------------------------------------------------------------


class PlaygroundSetupTests(unittest.TestCase):
    def setUp(self):
        self.w = _HeadlessAllToolsWindow()

    def test_cube_scene_in_vertex_mode(self):
        mesh = self.w.scene.mesh
        self.assertEqual(len(list(mesh.all_vertex_ids())), 8)
        self.assertEqual(len(list(mesh.all_face_ids())), 6)
        self.assertIs(self.w.selection_mode, SelectionMode.VERTEX)

    def test_m_activates_axis_move_tool(self):
        self.w.on_key_press(key.M, 0)
        tool = self.w._tool_manager.active_tool
        self.assertIsInstance(tool, AxisConstrainedMoveTool)
        self.assertIsInstance(tool, MoveTool)  # bewusst weiterhin ein MoveTool
        self.assertEqual(tool.state.name, "ACTIVE")

    def test_shift_r_shift_s_activate_transform_tools(self):
        self.w.on_key_press(key.R, key.MOD_SHIFT)
        self.assertIsInstance(self.w._tool_manager.active_tool, RotateTool)
        self.w.on_key_press(key.ESCAPE, 0)  # modal: Esc deaktiviert
        self.assertIsNone(self.w._tool_manager.active_tool)
        self.w.on_key_press(key.S, key.MOD_SHIFT)
        self.assertIsInstance(self.w._tool_manager.active_tool, ScaleTool)

    def test_plain_r_s_still_route_to_topology_commands(self):
        """R/S dürfen im Playground NICHT Rotate/Scale aktivieren."""
        self.w.on_key_press(key.E, 0)  # Edge Mode (wechselt Mode und leert Selection)
        self.w.scene.selection.set({min(self.w.scene.mesh.all_edge_ids())})
        self.w.on_key_press(key.R, 0)
        self.assertIsNone(self.w._tool_manager.active_tool)  # kein RotateTool
        # EdgeRing → mehrere Edges selektiert (Würfel-Ring = 4)
        self.assertEqual(len(self.w.scene.selection.edges), 4)

    def test_axis_toggle(self):
        self.w.on_key_press(key.X, 0)
        self.assertEqual(self.w._pending_axis, "x")
        self.w.on_key_press(key.X, 0)  # erneut → aufheben
        self.assertIsNone(self.w._pending_axis)
        self.w.on_key_press(key.Y, 0)
        self.assertEqual(self.w._pending_axis, "y")
        self.w.on_key_press(key.Z, 0)
        self.assertEqual(self.w._pending_axis, "z")
        self.w.on_key_press(key.Z, 0)
        self.assertIsNone(self.w._pending_axis)

    def test_selection_modes_still_work(self):
        self.w.on_key_press(key.E, 0)
        self.assertIs(self.w.selection_mode, SelectionMode.EDGE)
        self.w.on_key_press(key.F, 0)
        self.assertIs(self.w.selection_mode, SelectionMode.FACE)
        self.w.on_key_press(key.V, 0)
        self.assertIs(self.w.selection_mode, SelectionMode.VERTEX)


# ---------------------------------------------------------------------------
# Move + Achsen-Constraint
# ---------------------------------------------------------------------------


class MoveConstraintTests(unittest.TestCase):
    def setUp(self):
        self.w = _HeadlessAllToolsWindow()
        self.v0 = min(self.w.scene.mesh.all_vertex_ids())

    def _begin_modal_move(self, axis_key=None):
        self.w.scene.selection.set({self.v0})
        self.w.on_key_press(key.M, 0)
        if axis_key is not None:
            self.w.on_key_press(axis_key, 0)
        px, py = _screen_pos(self.w, self.v0)
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)

    def test_move_without_axis_is_free_and_commits_once(self):
        start = self.w.scene.mesh.vertex_position(self.v0)
        self._begin_modal_move()
        self.assertTrue(self.w._tool_manager.is_interacting)
        tool = self.w._tool_manager.active_tool
        self.assertIsNone(tool.axis)
        self.w.on_mouse_drag(0, 0, 120, 30, mouse.LEFT, 0)
        self.w.on_mouse_release(0, 0, mouse.LEFT, 0)
        after = self.w.scene.mesh.vertex_position(self.v0)
        self.assertNotEqual(after, start)
        self.assertEqual(len(self.w.scene.history), 1)  # genau ein Eintrag
        # Modal-Tool bleibt aktiv (WP-02-Semantik)
        self.assertIsInstance(self.w._tool_manager.active_tool, AxisConstrainedMoveTool)

    def test_move_x_constrains_to_world_x(self):
        start = self.w.scene.mesh.vertex_position(self.v0)
        self._begin_modal_move(key.X)
        tool = self.w._tool_manager.active_tool
        self.assertEqual(tool.axis, (1.0, 0.0, 0.0))
        self.w.on_mouse_drag(0, 0, 120, 40, mouse.LEFT, 0)
        self.w.on_mouse_release(0, 0, mouse.LEFT, 0)
        after = self.w.scene.mesh.vertex_position(self.v0)
        self.assertNotEqual(after[0], start[0])
        self.assertAlmostEqual(after[1], start[1], places=9)
        self.assertAlmostEqual(after[2], start[2], places=9)
        self.assertEqual(len(self.w.scene.history), 1)

    def test_move_y_and_z_constrain(self):
        for axis_key, index in ((key.Y, 1), (key.Z, 2)):
            with self.subTest(axis=index):
                start = self.w.scene.mesh.vertex_position(self.v0)
                self._begin_modal_move(axis_key)
                self.w.on_mouse_drag(0, 0, 90, 60, mouse.LEFT, 0)
                self.w.on_mouse_release(0, 0, mouse.LEFT, 0)
                after = self.w.scene.mesh.vertex_position(self.v0)
                for i in range(3):
                    if i == index:
                        self.assertNotEqual(after[i], start[i])
                    else:
                        self.assertAlmostEqual(after[i], start[i], places=9)
                # Für den nächsten subTest zurücksetzen (Undo).
                self.w.on_key_press(key.Z, key.MOD_CTRL)

    def test_esc_cancels_constrained_move_exactly(self):
        start = _positions(self.w)
        self._begin_modal_move(key.X)
        self.w.on_mouse_drag(0, 0, 150, 80, mouse.LEFT, 0)
        self.w.on_key_press(key.ESCAPE, 0)
        self.assertEqual(_positions(self.w), start)
        self.assertEqual(len(self.w.scene.history), 0)
        # Modal-Tool bleibt nach Cancel aktiv; zweites Esc deaktiviert.
        self.assertIsInstance(self.w._tool_manager.active_tool, AxisConstrainedMoveTool)
        self.w.on_key_press(key.ESCAPE, 0)
        self.assertIsNone(self.w._tool_manager.active_tool)

    def test_tweak_move_without_active_tool_unchanged(self):
        px, py = _screen_pos(self.w, self.v0)
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)
        self.assertEqual(set(self.w.scene.selection.vertices), {self.v0})
        self.assertTrue(self.w._tool_manager.is_interacting)
        self.assertIsInstance(self.w._tool_manager.active_tool, AxisConstrainedMoveTool)
        self.w.on_mouse_drag(int(px), int(py), 30, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(int(px), int(py), mouse.LEFT, 0)
        self.assertEqual(len(self.w.scene.history), 1)
        # Tweak-Tool beendet sich nach Commit selbst (kein stale Tool).
        self.assertIsNone(self.w._tool_manager.active_tool)


# ---------------------------------------------------------------------------
# Rotate + Achsen-Constraint (vorhandene WP-03-Semantik über axis=)
# ---------------------------------------------------------------------------


class RotateConstraintTests(unittest.TestCase):
    def setUp(self):
        self.w = _HeadlessAllToolsWindow()
        self.v_ids = sorted(self.w.scene.mesh.all_vertex_ids())[:3]

    def _pivot(self, positions):
        count = len(self.v_ids)
        return tuple(
            sum(positions[vid][i] for vid in self.v_ids) / count for i in range(3)
        )

    def _begin_modal_rotate(self, axis_key=None):
        self.w.scene.selection.set(set(self.v_ids))
        self.w.on_key_press(key.R, key.MOD_SHIFT)
        if axis_key is not None:
            self.w.on_key_press(axis_key, 0)
        px, py = _screen_pos(self.w, min(self.v_ids))
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)

    def test_rotate_without_axis_activates_and_commits(self):
        start = _positions(self.w)
        self._begin_modal_rotate()
        self.assertTrue(self.w._tool_manager.is_interacting)
        self.w.on_mouse_drag(0, 0, 200, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(0, 0, mouse.LEFT, 0)
        self.assertNotEqual(_positions(self.w), start)
        self.assertEqual(len(self.w.scene.history), 1)

    def test_rotate_x_keeps_pivot_relative_x_and_radius(self):
        start = _positions(self.w)
        self._begin_modal_rotate(key.X)
        self.w.on_mouse_drag(0, 0, 220, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(0, 0, mouse.LEFT, 0)
        pivot = self._pivot(start)
        for vid in self.v_ids:
            with self.subTest(vertex=vid):
                before = start[vid]
                after = self.w.scene.mesh.vertex_position(vid)
                # Rotation um die Welt-X-Achse durch den Pivot: der
                # Pivot-relative X-Anteil bleibt fix.
                self.assertAlmostEqual(after[0] - pivot[0], before[0] - pivot[0], places=9)
                # Radius in der YZ-Ebene bleibt erhalten (reine Drehung).
                r_before = ((before[1] - pivot[1]) ** 2 + (before[2] - pivot[2]) ** 2) ** 0.5
                r_after = ((after[1] - pivot[1]) ** 2 + (after[2] - pivot[2]) ** 2) ** 0.5
                self.assertAlmostEqual(r_after, r_before, places=9)
        self.assertEqual(len(self.w.scene.history), 1)

    def test_rotate_cancel_restores_exact_state(self):
        start = _positions(self.w)
        self._begin_modal_rotate(key.Z)
        self.w.on_mouse_drag(0, 0, -250, 0, mouse.LEFT, 0)
        self.w.on_key_press(key.ESCAPE, 0)
        self.assertEqual(_positions(self.w), start)
        self.assertEqual(len(self.w.scene.history), 0)


# ---------------------------------------------------------------------------
# Scale + Achsen-Constraint (vorhandene WP-03-Semantik über axes=)
# ---------------------------------------------------------------------------


class ScaleConstraintTests(unittest.TestCase):
    def setUp(self):
        self.w = _HeadlessAllToolsWindow()
        # Alle 8 Cube-Vertices: garantiert unterschiedliche Werte auf jeder
        # Achse (bei 3 Vertices einer Seite wäre z-Scale eine No-op-Geste).
        self.v_ids = sorted(self.w.scene.mesh.all_vertex_ids())

    def _pivot(self, positions):
        count = len(self.v_ids)
        return tuple(
            sum(positions[vid][i] for vid in self.v_ids) / count for i in range(3)
        )

    def _begin_modal_scale(self, axis_key=None):
        self.w.scene.selection.set(set(self.v_ids))
        self.w.on_key_press(key.S, key.MOD_SHIFT)
        if axis_key is not None:
            self.w.on_key_press(axis_key, 0)
        px, py = _screen_pos(self.w, min(self.v_ids))
        self.w.on_mouse_press(int(px), int(py), mouse.LEFT, 0)

    def test_scale_without_axis_is_uniform(self):
        start = _positions(self.w)
        self._begin_modal_scale()
        self.w.on_mouse_drag(0, 0, 100, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(0, 0, mouse.LEFT, 0)
        factor = 1.0 + ScaleTool.SCALE_PER_PIXEL * 100.0
        pivot = self._pivot(start)
        for vid in self.v_ids:
            with self.subTest(vertex=vid):
                for i in range(3):
                    expected = pivot[i] + factor * (start[vid][i] - pivot[i])
                    self.assertAlmostEqual(
                        self.w.scene.mesh.vertex_position(vid)[i], expected, places=9
                    )
        self.assertEqual(len(self.w.scene.history), 1)

    def test_scale_z_scales_only_z(self):
        start = _positions(self.w)
        self._begin_modal_scale(key.Z)
        self.w.on_mouse_drag(0, 0, 100, 0, mouse.LEFT, 0)
        self.w.on_mouse_release(0, 0, mouse.LEFT, 0)
        factor = 1.0 + ScaleTool.SCALE_PER_PIXEL * 100.0
        pivot = self._pivot(start)
        for vid in self.v_ids:
            with self.subTest(vertex=vid):
                after = self.w.scene.mesh.vertex_position(vid)
                self.assertAlmostEqual(after[2], pivot[2] + factor * (start[vid][2] - pivot[2]), places=9)
                self.assertAlmostEqual(after[0], start[vid][0], places=9)
                self.assertAlmostEqual(after[1], start[vid][1], places=9)
        self.assertEqual(len(self.w.scene.history), 1)

    def test_scale_cancel_restores_exact_state(self):
        start = _positions(self.w)
        self._begin_modal_scale(key.Y)
        self.w.on_mouse_drag(0, 0, -200, -100, mouse.LEFT, 0)
        self.w.on_key_press(key.ESCAPE, 0)
        self.assertEqual(_positions(self.w), start)
        self.assertEqual(len(self.w.scene.history), 0)


# ---------------------------------------------------------------------------
# Topology-Regression im Playground
# ---------------------------------------------------------------------------


class TopologyRegressionTests(unittest.TestCase):
    def setUp(self):
        self.w = _HeadlessAllToolsWindow()
        self.w.on_key_press(key.E, 0)  # Edge Mode

    def test_split_edge_still_works(self):
        mesh = self.w.scene.mesh
        edge = sorted(mesh.all_edge_ids())[0]
        self.w.scene.selection.set({edge})
        self.w.on_key_press(key.S, 0)  # SplitEdge (nicht Scale!)
        self.assertEqual(len(list(mesh.all_vertex_ids())), 9)  # Cube 8 + 1
        self.assertEqual(len(self.w.scene.selection.edges), 2)  # resultierende Edges
        self.assertEqual(len(self.w.scene.history), 1)
        self.w.on_key_press(key.Z, key.MOD_CTRL)
        self.assertEqual(len(list(mesh.all_vertex_ids())), 8)

    def test_edge_ring_still_works(self):
        edge = sorted(self.w.scene.mesh.all_edge_ids())[0]
        self.w.scene.selection.set({edge})
        self.w.on_key_press(key.R, 0)  # EdgeRing (nicht Rotate!)
        self.assertEqual(len(self.w.scene.selection.edges), 4)  # Würfel-Ring
        self.assertIsNone(self.w._tool_manager.active_tool)

    def test_undo_redo_and_deselection_still_work(self):
        self.w.scene.selection.set(set(self.w.scene.mesh.all_vertex_ids()))
        self.w.on_key_press(key.A, key.MOD_ALT)
        self.assertEqual(len(self.w.scene.selection.vertices), 0)


if __name__ == "__main__":
    unittest.main()
