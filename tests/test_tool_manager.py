"""ToolManager: Registry + Aktivierungs-/Lifecycle-Tests (Pattern A und B).

Prüft `mirai.interaction.tool_manager.ToolManager`:
- Command→Tool-Registry (register/registry)
- Pattern A: activate() → Tool wartet; begin_current_interaction() startet
- Pattern B: activate(command, context=...) → sofortige Interaktion
- genau ein aktives Tool; Wechsel räumt das alte auf (kein stale State)
- update/commit/cancel/deactivate-Weiterleitung an das aktive Tool
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from mirai.interaction import commands as cmd
from mirai.interaction.tool import Tool, ToolStateError
from mirai.interaction.tool_manager import ToolManager
from mirai.interaction.tools.move import MoveTool
from mirai.interaction.tools.rotate import RotateTool
from mirai.interaction.tools.scale import ScaleTool


class _RecordingTool(Tool):
    def __init__(self):
        super().__init__()
        self.events = []

    def _on_activate(self):
        self.events.append("activate")

    def _on_begin(self, **params):
        self.events.append("begin")

    def _on_update(self, **kwargs):
        self.events.append("update")

    def _on_commit(self):
        self.events.append("commit")

    def _on_cancel(self):
        self.events.append("cancel")

    def _on_deactivate(self):
        self.events.append("deactivate")


class ToolManagerRegistryTests(unittest.TestCase):
    def setUp(self):
        self.mgr = ToolManager()

    def test_initial_registry_empty(self):
        self.assertEqual(self.mgr.registry, {})

    def test_register_stores_mapping(self):
        self.mgr.register(cmd.MOVE, MoveTool)
        self.assertIn(cmd.MOVE, self.mgr.registry)
        self.assertIs(self.mgr.registry[cmd.MOVE], MoveTool)

    def test_registry_returns_copy(self):
        self.mgr.register(cmd.MOVE, MoveTool)
        registry = self.mgr.registry
        registry[cmd.MOVE] = RotateTool
        self.assertIs(self.mgr.registry[cmd.MOVE], MoveTool)

    def test_activate_unknown_command_returns_false(self):
        self.mgr.register(cmd.MOVE, MoveTool)
        self.assertFalse(self.mgr.activate("UnknownCommand"))
        self.assertIsNone(self.mgr.active_tool)


class ToolManagerActivationTests(unittest.TestCase):
    def setUp(self):
        self.mgr = ToolManager()
        self.mgr.register(cmd.MOVE, _RecordingTool)
        self.mgr.register(cmd.ROTATE, _RecordingTool)

    def test_activate_known_command_returns_true(self):
        self.assertTrue(self.mgr.activate(cmd.MOVE))

    def test_pattern_a_activate_waits(self):
        self.assertTrue(self.mgr.activate(cmd.MOVE))
        tool = self.mgr.active_tool
        self.assertIsNotNone(tool)
        self.assertEqual(tool.state.name, "ACTIVE")
        self.assertFalse(self.mgr.is_interacting)
        self.assertEqual(tool.events, ["activate"])

    def test_pattern_a_begin_current_interaction_starts(self):
        self.mgr.activate(cmd.MOVE)
        self.mgr.begin_current_interaction(context={"scene": "s"})
        self.assertTrue(self.mgr.is_interacting)
        self.assertEqual(self.mgr.active_tool.events, ["activate", "begin"])

    def test_pattern_a_begin_without_context(self):
        self.mgr.activate(cmd.MOVE)
        self.mgr.begin_current_interaction()
        self.assertTrue(self.mgr.is_interacting)
        self.assertEqual(self.mgr.active_tool.events, ["activate", "begin"])

    def test_pattern_b_activate_with_context_begins_immediately(self):
        self.assertTrue(
            self.mgr.activate(cmd.MOVE, context={"scene": "s", "camera": "c"})
        )
        self.assertTrue(self.mgr.is_interacting)
        self.assertEqual(self.mgr.active_tool.events, ["activate", "begin"])

    def test_only_one_active_tool(self):
        self.mgr.activate(cmd.MOVE)
        first = self.mgr.active_tool
        self.mgr.activate(cmd.ROTATE)
        second = self.mgr.active_tool
        self.assertIsNot(first, second)
        self.assertEqual(first.events, ["activate", "deactivate"])
        self.assertIs(self.mgr.active_tool, second)


class ToolManagerLifecycleDelegationTests(unittest.TestCase):
    def setUp(self):
        self.mgr = ToolManager()
        self.mgr.register(cmd.MOVE, _RecordingTool)

    def test_update_delegates_to_active_tool(self):
        self.mgr.activate(cmd.MOVE)
        self.mgr.begin_current_interaction()
        self.mgr.update(dx=1, dy=2, width=800, height=600)
        self.assertEqual(self.mgr.active_tool.events, ["activate", "begin", "update"])

    def test_commit_delegates(self):
        self.mgr.activate(cmd.MOVE)
        self.mgr.begin_current_interaction()
        self.mgr.commit()
        self.assertEqual(self.mgr.active_tool.events, ["activate", "begin", "commit"])
        self.assertEqual(self.mgr.active_tool.state.name, "ACTIVE")
        self.assertFalse(self.mgr.is_interacting)

    def test_cancel_delegates(self):
        self.mgr.activate(cmd.MOVE)
        self.mgr.begin_current_interaction()
        self.mgr.cancel()
        self.assertEqual(self.mgr.active_tool.events, ["activate", "begin", "cancel"])
        self.assertFalse(self.mgr.is_interacting)

    def test_deactivate_clears_active_tool(self):
        self.mgr.activate(cmd.MOVE)
        self.mgr.deactivate()
        self.assertIsNone(self.mgr.active_tool)

    def test_update_without_active_tool_raises(self):
        with self.assertRaises(ToolStateError):
            self.mgr.update(dx=1, dy=0, width=800, height=600)

    def test_commit_without_active_tool_raises(self):
        with self.assertRaises(ToolStateError):
            self.mgr.commit()

    def test_begin_without_active_tool_raises(self):
        with self.assertRaises(ToolStateError):
            self.mgr.begin_current_interaction()


class ToolManagerSwitchTests(unittest.TestCase):
    def test_switching_cancels_interacting_tool(self):
        mgr = ToolManager()
        mgr.register(cmd.MOVE, _RecordingTool)
        mgr.register(cmd.ROTATE, _RecordingTool)
        mgr.activate(cmd.MOVE, context={})
        self.assertTrue(mgr.is_interacting)
        first = mgr.active_tool
        mgr.activate(cmd.ROTATE)
        # Das interagierende MOVE-Tool wurde per cancel() beendet + deaktiviert.
        self.assertEqual(first.events, ["activate", "begin", "cancel", "deactivate"])
        self.assertEqual(mgr.active_tool.events, ["activate"])

    def test_real_tool_registration(self):
        mm = ToolManager()
        mm.register(cmd.MOVE, MoveTool)
        mm.register(cmd.ROTATE, RotateTool)
        mm.register(cmd.SCALE, ScaleTool)
        self.assertIs(mm.registry[cmd.MOVE], MoveTool)
        self.assertIs(mm.registry[cmd.ROTATE], RotateTool)
        self.assertIs(mm.registry[cmd.SCALE], ScaleTool)


if __name__ == "__main__":
    unittest.main()