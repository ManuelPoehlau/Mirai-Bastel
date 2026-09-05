"""Application: Tests für die Produktions-Orchestrierung (window-frei).

Prüft `mirai.application.Application`:
- Fenster- los Initialisierung (Scene/Selection/History/Camera/Display/
  ToolManager/Bindings)
- Scene-Initialisierung (cube-Factory über öffentliche Core-API)
- Command-Dispatch (Tool-Aktivierung Pattern A/B, Undo/Redo, unbekannte
  Commands)
- Input → Binding → Command → Application-Pfad (M-Taste)
- update_viewport()-No-op und shutdown()-Verhalten
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core import Scene, SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.interaction.tools.move import MoveTool, resolve_selection_vertices
from mirai.interaction.tools.rotate import RotateTool
from mirai.interaction.tools.scale import ScaleTool


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _select_all_vertices(app: Application) -> None:
    app.selection.mode = SelectionMode.VERTEX
    app.selection.set(set(app.scene.mesh.all_vertex_ids()))


def _move_vertices(app: Application, dx: float, dy: float) -> None:
    """Führt eine komplette Move-Interaktion über den ToolManager aus."""
    _select_all_vertices(app)
    vertex_ids = resolve_selection_vertices(
        app.scene.mesh, app.selection, SelectionMode.VERTEX
    )
    app.tool_manager.activate(cmd.MOVE)
    app.tool_manager.begin_current_interaction(
        context={"scene": app.scene, "camera": app.camera, "vertex_ids": vertex_ids}
    )
    app.tool_manager.update(dx=dx, dy=dy, width=800, height=600)
    app.tool_manager.commit()


class ApplicationInstantiationTests(unittest.TestCase):
    def test_instantiates_without_window(self):
        app = Application()  # kein pyglet, kein Fenster
        self.assertIsNotNone(app)

    def test_scene_history_selection_accessible(self):
        app = Application()
        self.assertIsNotNone(app.scene)
        self.assertIsNotNone(app.selection)
        self.assertIsNotNone(app.history)

    def test_application_history_is_scene_history(self):
        app = Application()
        self.assertIs(app.history, app.scene.history)
        self.assertIs(app.selection, app.scene.selection)

    def test_viewport_state_accessible(self):
        app = Application()
        self.assertIsNotNone(app.camera)
        self.assertIsNotNone(app.display)

    def test_default_tools_registered(self):
        app = Application()
        self.assertIs(app.tool_manager.registry[cmd.MOVE], MoveTool)
        self.assertIs(app.tool_manager.registry[cmd.ROTATE], RotateTool)
        self.assertIs(app.tool_manager.registry[cmd.SCALE], ScaleTool)

    def test_bindings_are_default(self):
        app = Application()
        self.assertEqual(app.bindings.command_for(_key("m")), cmd.MOVE)
        self.assertEqual(app.bindings.command_for(_key("z", "ctrl")), cmd.UNDO)
        self.assertEqual(app.bindings.command_for(_key("y", "ctrl")), cmd.REDO)


class ApplicationSceneTests(unittest.TestCase):
    def test_init_scene_cube_has_8_vertices(self):
        app = Application()
        app.init_scene("cube")
        self.assertEqual(len(app.scene.mesh.all_vertex_ids()), 8)

    def test_init_scene_cube_has_6_faces(self):
        app = Application()
        app.init_scene("cube")
        self.assertEqual(len(app.scene.mesh.all_face_ids()), 6)

    def test_init_scene_default_is_cube(self):
        app = Application()
        app.init_scene()
        self.assertEqual(len(app.scene.mesh.all_vertex_ids()), 8)


class ApplicationDispatchTests(unittest.TestCase):
    def setUp(self):
        self.app = Application()
        self.app.init_scene("cube")

    def test_dispatch_move_activates_tool_pattern_a(self):
        self.assertTrue(self.app.dispatch_command(cmd.MOVE))
        self.assertIsInstance(self.app.tool_manager.active_tool, MoveTool)
        self.assertEqual(self.app.tool_manager.active_tool.state.name, "ACTIVE")
        self.assertFalse(self.app.tool_manager.is_interacting)

    def test_dispatch_rotate_scale_activate_tools(self):
        self.assertTrue(self.app.dispatch_command(cmd.ROTATE))
        self.assertIsInstance(self.app.tool_manager.active_tool, RotateTool)
        self.app.tool_manager.deactivate()
        self.assertTrue(self.app.dispatch_command(cmd.SCALE))
        self.assertIsInstance(self.app.tool_manager.active_tool, ScaleTool)

    def test_dispatch_pattern_b_starts_interaction(self):
        _select_all_vertices(self.app)
        vertex_ids = resolve_selection_vertices(
            self.app.scene.mesh, self.app.selection, SelectionMode.VERTEX
        )
        ok = self.app.dispatch_command(
            cmd.MOVE,
            context={"scene": self.app.scene, "camera": self.app.camera,
                     "vertex_ids": vertex_ids},
        )
        self.assertTrue(ok)
        self.assertTrue(self.app.tool_manager.is_interacting)

    def test_dispatch_undo_redo_roundtrip(self):
        _select_all_vertices(self.app)
        before = {v: self.app.scene.mesh.vertex_position(v)
                  for v in self.app.scene.mesh.all_vertex_ids()}
        _move_vertices(self.app, 1.0, 0.0)
        moved = {v: self.app.scene.mesh.vertex_position(v)
                 for v in self.app.scene.mesh.all_vertex_ids()}
        self.assertEqual(len(self.app.history), 1)
        self.assertTrue(self.app.dispatch_command(cmd.UNDO))
        for vid in self.app.scene.mesh.all_vertex_ids():
            self.assertEqual(self.app.scene.mesh.vertex_position(vid), before[vid])
        self.assertTrue(self.app.dispatch_command(cmd.REDO))
        for vid in self.app.scene.mesh.all_vertex_ids():
            self.assertEqual(self.app.scene.mesh.vertex_position(vid), moved[vid])

    def test_dispatch_unknown_command_returns_false(self):
        self.assertFalse(self.app.dispatch_command("NoSuchCommand"))

    def test_dispatch_undo_on_empty_history_is_true_noop(self):
        self.assertTrue(self.app.dispatch_command(cmd.UNDO))
        self.assertEqual(len(self.app.history), 0)

    def test_m_key_through_bindings_dispatch_move(self):
        command = self.app.bindings.command_for(_key("m"))
        self.assertEqual(command, cmd.MOVE)
        self.assertTrue(self.app.dispatch_command(command))
        self.assertIsInstance(self.app.tool_manager.active_tool, MoveTool)

    def test_selection_stays_available_after_dispatch(self):
        _select_all_vertices(self.app)
        self.assertEqual(set(self.app.selection.vertices),
                         set(self.app.scene.mesh.all_vertex_ids()))


class ApplicationLifecycleTests(unittest.TestCase):
    def test_update_viewport_is_noop(self):
        app = Application()
        app.update_viewport(0.016)  # darf nichts werfen/ändern

    def test_shutdown_deactivates_active_tool(self):
        app = Application()
        app.init_scene("cube")
        app.dispatch_command(cmd.MOVE)
        self.assertIsNotNone(app.tool_manager.active_tool)
        app.shutdown()
        self.assertIsNone(app.tool_manager.active_tool)

    def test_full_interaction_through_application(self):
        app = Application()
        app.init_scene("cube")
        _move_vertices(app, 2.0, 0.0)
        self.assertEqual(len(app.history), 1)
        app.dispatch_command(cmd.UNDO)
        moved = {v: app.scene.mesh.vertex_position(v)
                  for v in app.scene.mesh.all_vertex_ids()}
        self.assertEqual(set(moved.values()),
                         {(-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, 1.0, -1.0),
                          (-1.0, 1.0, -1.0), (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0),
                          (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0)})


class SceneFactoryTests(unittest.TestCase):
    def test_build_cube_scene_has_cube_mesh(self):
        from mirai.scene_factory import build_cube_scene

        scene = build_cube_scene()
        self.assertEqual(len(scene.mesh.all_vertex_ids()), 8)
        self.assertEqual(len(scene.mesh.all_edge_ids()), 12)
        self.assertEqual(len(scene.mesh.all_face_ids()), 6)

    def test_create_cube_default_size(self):
        from mirai.scene_factory import create_cube

        mesh = create_cube()
        self.assertEqual(len(mesh.all_vertex_ids()), 8)
        self.assertEqual(len(mesh.all_edge_ids()), 12)
        self.assertEqual(len(mesh.all_face_ids()), 6)


if __name__ == "__main__":
    unittest.main()