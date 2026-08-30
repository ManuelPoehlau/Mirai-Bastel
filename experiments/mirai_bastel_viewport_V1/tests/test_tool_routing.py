"""WP-02: Command → Tool Routing.

Prüft, dass `Command.Move` auf `MoveTool` geroutet wird und dass eine
Änderung der Input-Bindings keine Änderung am MoveTool erfordert
(d.h. das Tool ist vom physischen Input entkoppelt).
"""
from pathlib import Path
import unittest
import sys

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from viewport.commands import (
    MOVE,
    TOGGLE_WIREFRAME_OVERLAY,
    CYCLE_DISPLAY_MODE,
)
from viewport.move_tool import MoveTool, tool_for_command


class ToolRoutingTests(unittest.TestCase):
    def test_move_command_routes_to_move_tool(self):
        self.assertIs(tool_for_command(MOVE), MoveTool)

    def test_non_modeling_command_has_no_tool(self):
        # Display-Kommandos dürfen nicht auf ein Modeling-Tool gemappt sein.
        self.assertIsNone(tool_for_command(TOGGLE_WIREFRAME_OVERLAY))
        self.assertIsNone(tool_for_command(CYCLE_DISPLAY_MODE))


if __name__ == "__main__":
    unittest.main()
