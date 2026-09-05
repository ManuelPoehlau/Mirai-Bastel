"""End-to-End-Integration: Input → Binding → Command → Tool → Operation → History.

Vollständiger Produktions-Pfad über `mirai.application.Application` und die
Default-Bindings — headless (kein pyglet, keine GPU):

    Input ("m")
      ↓ BindingSet.command_for       → Command "Move"
      ↓ Application.dispatch_command → ToolManager.activate (Pattern A)
      ↓ begin(scene/camera/vertex_ids) → Operation.begin()
      ↓ update(dx, dy, ...)*          → Operation.update()
      ↓ commit()                      → History-Eintrag
      ↓ Undo/Redo                     → History.undo()/redo()

Zusätzlich: Rotate/Scale-Aktivierung, Cancel (kein History), sequenzielle
Tools und Selection-Auflösung (Vertex/Edge/Face → betroffene Vertex-IDs).
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from core import RotateOperation, ScaleOperation, SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.interaction.tools.move import MoveTool, resolve_selection_vertices
from mirai.interaction.tools.rotate import RotateTool
from mirai.interaction.tools.scale import ScaleTool


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _make_app() -> Application:
    app = Application()
    app.init_scene("cube")
    return app


def _select_all(app: Application) -> None:
    app.selection.mode = SelectionMode.VERTEX
    app.selection.set(set(app.scene.mesh.all_vertex_ids()))


def _context_for(app: Application) -> dict:
    vertex_ids = resolve_selection_vertices(
        app.scene.mesh, app.selection, SelectionMode.VERTEX
    )
    return {"scene": app.scene, "camera": app.camera, "vertex_ids": vertex_ids}


def _positions(app: Application) -> dict:
    return {
        vid: tuple(app.scene.mesh.vertex_position(vid))
        for vid in app.scene.mesh.all_vertex_ids()
    }


class ModalMoveIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.app = _make_app()
        _select_all(self.app)

    def test_m_key_activates_move_tool(self):
        self.assertIsNone(self.app.tool_manager.active_tool)
        command = self.app.bindings.command_for(_key("m"))
        self.assertEqual(command, cmd.MOVE)
        self.assertTrue(self.app.dispatch_command(command))
        self.assertIsInstance(self.app.tool_manager.active_tool, MoveTool)
        self.assertEqual(self.app.tool_manager.active_tool.state.name, "ACTIVE")

    def test_move_tool_begin_on_context(self):
        self.assertTrue(self.app.dispatch_command(cmd.MOVE))
        self.app.tool_manager.begin_current_interaction(context=_context_for(self.app))
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.assertIsNotNone(self.app.tool_manager.active_tool.operation)

    def test_update_on_drag_moves_vertices(self):
        self.app.dispatch_command(cmd.MOVE)
        before = _positions(self.app)
        self.app.tool_manager.begin_current_interaction(context=_context_for(self.app))
        self.app.tool_manager.update(dx=40, dy=0, width=800, height=600)
        self.app.tool_manager.update(dx=0, dy=40, width=800, height=600)
        self.assertNotEqual(before, _positions(self.app))

    def test_commit_creates_single_history_entry(self):
        self.app.dispatch_command(cmd.MOVE)
        self.app.tool_manager.begin_current_interaction(context=_context_for(self.app))
        self.app.tool_manager.update(dx=40, dy=0, width=800, height=600)
        self.app.tool_manager.commit()
        self.assertEqual(len(self.app.history), 1)

    def test_undo_after_commit_restores_positions(self):
        self.app.dispatch_command(cmd.MOVE)
        before = _positions(self.app)
        self.app.tool_manager.begin_current_interaction(context=_context_for(self.app))
        self.app.tool_manager.update(dx=40, dy=0, width=800, height=600)
        self.app.tool_manager.commit()
        self.app.history.undo()
        self.assertEqual(_positions(self.app), before)

    def test_redo_after_undo(self):
        self.app.dispatch_command(cmd.MOVE)
        self.app.tool_manager.begin_current_interaction(context=_context_for(self.app))
        self.app.tool_manager.update(dx=40, dy=0, width=800, height=600)
        self.app.tool_manager.commit()
        after_move = _positions(self.app)
        self.app.history.undo()
        self.app.history.redo()
        self.assertEqual(_positions(self.app), after_move)

    def test_cancel_no_history_and_exact_restore(self):
        self.app.dispatch_command(cmd.MOVE)
        before = _positions(self.app)
        self.app.tool_manager.begin_current_interaction(context=_context_for(self.app))
        self.app.tool_manager.update(dx=100, dy=100, width=800, height=600)
        self.app.tool_manager.cancel()
        self.assertEqual(len(self.app.history), 0)
        self.assertEqual(_positions(self.app), before)


class ModalTransformToolIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.app = _make_app()
        _select_all(self.app)
        self.ctx = _context_for(self.app)

    def test_r_key_activates_rotate_tool(self):
        command = self.app.bindings.command_for(_key("r"))
        self.assertEqual(command, cmd.ROTATE)
        self.assertTrue(self.app.dispatch_command(command))
        self.assertIsInstance(self.app.tool_manager.active_tool, RotateTool)

    def test_s_key_activates_scale_tool(self):
        command = self.app.bindings.command_for(_key("s"))
        self.assertEqual(command, cmd.SCALE)
        self.assertTrue(self.app.dispatch_command(command))
        self.assertIsInstance(self.app.tool_manager.active_tool, ScaleTool)

    def test_rotate_tool_uses_core_rotate_operation(self):
        self.app.dispatch_command(cmd.ROTATE)
        self.app.tool_manager.begin_current_interaction(context=self.ctx)
        self.assertIsInstance(
            self.app.tool_manager.active_tool.operation, RotateOperation
        )

    def test_scale_tool_uses_core_scale_operation(self):
        self.app.dispatch_command(cmd.SCALE)
        self.app.tool_manager.begin_current_interaction(context=self.ctx)
        self.assertIsInstance(
            self.app.tool_manager.active_tool.operation, ScaleOperation
        )

    def test_sequential_tools(self):
        for command, tool_cls in (
            (cmd.MOVE, MoveTool),
            (cmd.ROTATE, RotateTool),
            (cmd.SCALE, ScaleTool),
        ):
            self.assertTrue(self.app.dispatch_command(command))
            self.assertIsInstance(self.app.tool_manager.active_tool, tool_cls)
            self.app.tool_manager.deactivate()
        self.assertIsNone(self.app.tool_manager.active_tool)


class SelectionResolutionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.app = _make_app()
        self.mesh = self.app.scene.mesh

    def test_vertex_mode_resolves_to_selected_vertices(self):
        vid = min(self.mesh.all_vertex_ids())
        self.app.selection.mode = SelectionMode.VERTEX
        self.app.selection.set({vid})
        resolved = resolve_selection_vertices(
            self.mesh, self.app.selection, SelectionMode.VERTEX
        )
        self.assertEqual(resolved, {vid})

    def test_edge_mode_resolves_to_endpoints(self):
        edge = next(iter(self.mesh.all_edge_ids()))
        self.app.selection.mode = SelectionMode.EDGE
        self.app.selection.set({edge})
        resolved = resolve_selection_vertices(
            self.mesh, self.app.selection, SelectionMode.EDGE
        )
        self.assertEqual(resolved, set(self.mesh.edge_vertices(edge)))

    def test_face_mode_resolves_to_boundary(self):
        face = next(iter(self.mesh.all_face_ids()))
        self.app.selection.mode = SelectionMode.FACE
        self.app.selection.set({face})
        resolved = resolve_selection_vertices(
            self.mesh, self.app.selection, SelectionMode.FACE
        )
        self.assertEqual(resolved, set(self.mesh.face_vertices(face)))


class FullPipelineTests(unittest.TestCase):
    def test_input_to_history_full_pipeline(self):
        app = _make_app()
        _select_all(app)

        # Input → Command
        command = app.bindings.command_for(_key("m"))
        self.assertEqual(command, cmd.MOVE)

        # Command → Tool
        self.assertTrue(app.dispatch_command(command))
        self.assertIsInstance(app.tool_manager.active_tool, MoveTool)

        # Tool → Operation
        app.tool_manager.begin_current_interaction(context=_context_for(app))
        operation = app.tool_manager.active_tool.operation
        self.assertIsNotNone(operation)

        # Drag → Update
        before = _positions(app)
        app.tool_manager.update(dx=40, dy=0, width=800, height=600)
        self.assertNotEqual(before, _positions(app))

        # Release → Commit → History
        app.tool_manager.commit()
        self.assertEqual(len(app.history), 1)

        # Undo / Redo
        app.dispatch_command(cmd.UNDO)
        self.assertEqual(_positions(app), before)
        app.dispatch_command(cmd.REDO)
        self.assertNotEqual(_positions(app), before)


class TransformToolLifecycleTests(unittest.TestCase):
    """Full begin/update/commit/cancel/undo lifecycles for Rotate & Scale.

    Validates the Tool -> Operation -> History contract end-to-end beyond mere
    activation, exercising gesture interpretation in
    src/mirai/interaction/tools/{rotate,scale,transform}.py and confirming the
    transform tools mutate geometry through the Core operations and round-trip
    through History.
    """

    def setUp(self):
        self.app = _make_app()
        _select_all(self.app)
        self.ctx = _context_for(self.app)

    def test_rotate_commit_creates_history_entry(self):
        self.app.dispatch_command(cmd.ROTATE)
        self.app.tool_manager.begin_current_interaction(context=self.ctx)
        self.app.tool_manager.update(dx=400, dy=0, width=800, height=600)
        self.app.tool_manager.commit()
        self.assertEqual(len(self.app.history), 1)

    def test_rotate_undo_redo_restores_positions(self):
        self.app.dispatch_command(cmd.ROTATE)
        before = _positions(self.app)
        self.app.tool_manager.begin_current_interaction(context=self.ctx)
        self.app.tool_manager.update(dx=400, dy=0, width=800, height=600)
        self.app.tool_manager.commit()
        after = _positions(self.app)
        self.assertNotEqual(before, after)
        self.app.history.undo()
        self.assertEqual(_positions(self.app), before)
        self.app.history.redo()
        self.assertEqual(_positions(self.app), after)

    def test_rotate_cancel_no_history_exact_restore(self):
        self.app.dispatch_command(cmd.ROTATE)
        before = _positions(self.app)
        self.app.tool_manager.begin_current_interaction(context=self.ctx)
        self.app.tool_manager.update(dx=200, dy=200, width=800, height=600)
        self.app.tool_manager.cancel()
        self.assertEqual(len(self.app.history), 0)
        self.assertEqual(_positions(self.app), before)

    def test_rotate_explicit_axis_resolves_to_world_axis(self):
        self.app.dispatch_command(cmd.ROTATE)
        ctx = dict(self.ctx, axis="z")
        self.app.tool_manager.begin_current_interaction(context=ctx)
        self.assertEqual(
            self.app.tool_manager.active_tool.axis, (0.0, 0.0, 1.0)
        )

    def test_rotate_invalid_axis_raises(self):
        self.app.dispatch_command(cmd.ROTATE)
        with self.assertRaises(ValueError):
            self.app.tool_manager.begin_current_interaction(
                context=dict(self.ctx, axis="bogus")
            )

    # --- Scale -------------------------------------------------------------

    def test_scale_commit_creates_history_entry(self):
        self.app.dispatch_command(cmd.SCALE)
        self.app.tool_manager.begin_current_interaction(context=self.ctx)
        self.app.tool_manager.update(dx=200, dy=0, width=800, height=600)
        self.app.tool_manager.commit()
        self.assertEqual(len(self.app.history), 1)

    def test_scale_undo_redo_restores_positions(self):
        self.app.dispatch_command(cmd.SCALE)
        before = _positions(self.app)
        self.app.tool_manager.begin_current_interaction(context=self.ctx)
        self.app.tool_manager.update(dx=200, dy=0, width=800, height=600)
        self.app.tool_manager.commit()
        after = _positions(self.app)
        self.assertNotEqual(before, after)
        self.app.history.undo()
        self.assertEqual(_positions(self.app), before)
        self.app.history.redo()
        self.assertEqual(_positions(self.app), after)

    def test_scale_cancel_no_history_exact_restore(self):
        self.app.dispatch_command(cmd.SCALE)
        before = _positions(self.app)
        self.app.tool_manager.begin_current_interaction(context=self.ctx)
        self.app.tool_manager.update(dx=100, dy=100, width=800, height=600)
        self.app.tool_manager.cancel()
        self.assertEqual(len(self.app.history), 0)
        self.assertEqual(_positions(self.app), before)

    def test_scale_explicit_single_axis(self):
        self.app.dispatch_command(cmd.SCALE)
        ctx = dict(self.ctx, axes="x")
        self.app.tool_manager.begin_current_interaction(context=ctx)
        self.assertEqual(
            self.app.tool_manager.active_tool.axes_mask, (1.0, 0.0, 0.0)
        )
        self.app.tool_manager.update(dx=200, dy=0, width=800, height=600)
        self.app.tool_manager.commit()
        self.assertEqual(len(self.app.history), 1)

    def test_scale_invalid_axis_raises(self):
        self.app.dispatch_command(cmd.SCALE)
        with self.assertRaises(ValueError):
            self.app.tool_manager.begin_current_interaction(
                context=dict(self.ctx, axes="nope")
            )

    # --- Cross-cutting ------------------------------------------------------

    def test_tool_switch_cancels_in_flight_interaction(self):
        # Wechsel während INTERACTING muss das laufende Tool sauber cancellen
        # (kein History-Eintrag) und das neue aktivieren (ToolManager._end_active).
        self.app.dispatch_command(cmd.ROTATE)
        self.app.tool_manager.begin_current_interaction(context=self.ctx)
        self.assertTrue(self.app.tool_manager.is_interacting)
        self.app.dispatch_command(cmd.SCALE)
        self.assertFalse(self.app.tool_manager.is_interacting)
        self.assertIsInstance(self.app.tool_manager.active_tool, ScaleTool)

    def test_full_pipeline_rotate_input_to_history(self):
        app = _make_app()
        _select_all(app)
        command = app.bindings.command_for(_key("r"))
        self.assertEqual(command, cmd.ROTATE)
        self.assertTrue(app.dispatch_command(command))
        app.tool_manager.begin_current_interaction(context=_context_for(app))
        before = _positions(app)
        app.tool_manager.update(dx=400, dy=0, width=800, height=600)
        self.assertNotEqual(before, _positions(app))
        app.tool_manager.commit()
        self.assertEqual(len(app.history), 1)
        app.dispatch_command(cmd.UNDO)
        self.assertEqual(_positions(app), before)
        app.dispatch_command(cmd.REDO)
        self.assertNotEqual(_positions(app), before)


if __name__ == "__main__":
    unittest.main()