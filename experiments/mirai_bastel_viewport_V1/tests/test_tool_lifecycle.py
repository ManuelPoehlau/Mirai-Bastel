"""WP-02: Tool-Lifecycle-Tests.

Prüft, dass ein Tool die Zustände IDLE/ACTIVE/INTERACTING korrekt
durchläuft und nach Commit oder Cancel kein staler State zurückbleibt.
"""
from pathlib import Path
import unittest
import sys

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from viewport.tool import Tool, ToolStateError


class _RecordingTool(Tool):
    """Minimal-Testtool, das alle Lifecycle-Methoden protokolliert."""

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


class ToolLifecycleTests(unittest.TestCase):
    def _new_tool(self):
        return _RecordingTool()

    def test_activate_begin_updates_commit_deactivate(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin()
        tool.update()
        tool.update()
        tool.commit()
        tool.deactivate()
        self.assertEqual(
            tool.events,
            ["activate", "begin", "update", "update", "commit", "deactivate"],
        )

    def test_cancel_restores_original_state(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin()
        tool.update()
        tool.cancel()
        tool.deactivate()
        self.assertEqual(
            tool.events,
            ["activate", "begin", "update", "cancel", "deactivate"],
        )

    def test_no_updates_before_begin(self):
        tool = self._new_tool()
        with self.assertRaises(ToolStateError):
            tool.update()

    def test_commit_before_begin_raises(self):
        tool = self._new_tool()
        tool.activate()
        with self.assertRaises(ToolStateError):
            tool.commit()

    def test_no_stale_state_after_commit(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin()
        tool.update()
        tool.commit()
        self.assertFalse(tool.is_interacting)

    def test_no_stale_state_after_cancel(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin()
        tool.update()
        tool.cancel()
        self.assertFalse(tool.is_interacting)

    def test_deactivate_without_interaction(self):
        tool = self._new_tool()
        tool.activate()
        tool.deactivate()
        self.assertEqual(tool.state.name, "IDLE")


if __name__ == "__main__":
    unittest.main()
