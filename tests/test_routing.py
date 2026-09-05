"""Command → Tool-Routing: Tests für `mirai.interaction.routing.tool_for_command`.

Prüft, dass die modalen Commands (Move/Rotate/Scale) auf ihre Tools geroutet
werden, nicht-modale Commands None liefern, und dass eine geänderte
Input-Bindung das Routing nicht beeinflusst (Entkopplung Tools ↔ Input).
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.interaction.routing import tool_for_command
from mirai.interaction.tools.move import MoveTool
from mirai.interaction.tools.rotate import RotateTool
from mirai.interaction.tools.scale import ScaleTool


class ToolRoutingTests(unittest.TestCase):
    def test_move_command_routes_to_move_tool(self):
        self.assertIs(tool_for_command(cmd.MOVE), MoveTool)

    def test_rotate_command_routes_to_rotate_tool(self):
        self.assertIs(tool_for_command(cmd.ROTATE), RotateTool)

    def test_scale_command_routes_to_scale_tool(self):
        self.assertIs(tool_for_command(cmd.SCALE), ScaleTool)

    def test_non_modeling_commands_have_no_tool(self):
        self.assertIsNone(tool_for_command(cmd.UNDO))
        self.assertIsNone(tool_for_command(cmd.REDO))
        self.assertIsNone(tool_for_command(cmd.TOGGLE_WIREFRAME_OVERLAY))
        self.assertIsNone(tool_for_command(cmd.CYCLE_DISPLAY_MODE))
        self.assertIsNone(tool_for_command(cmd.SELECT))

    def test_unknown_command_has_no_tool(self):
        self.assertIsNone(tool_for_command("DoesNotExist"))

    def test_binding_change_does_not_affect_routing(self):
        # G statt M → Move: Bindings ändern sich, das Routing bleibt.
        bs = build_default_bindings()
        bs.bind(Input("key", "g"), cmd.MOVE)
        command = bs.command_for(Input("key", "g"))
        self.assertEqual(command, cmd.MOVE)
        self.assertIs(tool_for_command(command), MoveTool)


if __name__ == "__main__":
    unittest.main()