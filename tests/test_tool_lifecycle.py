"""Tool-Lifecycle: Tests für den 3-Zustands-Lebenszyklus (IDLE/ACTIVE/INTERACTING).

Migriert aus `experiments/mirai_bastel_viewport_V1/tests/test_tool_lifecycle.py`
und erweitert für den Produktions-Tool-Vertrag (src/mirai/interaction/tool.py).

Geprüft: korrekte Zustandsübergänge, Lifecycle-Guards (Methoden im falschen
Zustand werfen ToolStateError) und „kein stale State" nach commit/cancel.
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401

from mirai.interaction.tool import Tool, ToolState, ToolStateError


class _RecordingTool(Tool):
    """Minimal-Testtool, das alle Lifecycle-Methoden protokolliert."""

    def __init__(self):
        super().__init__()
        self.events = []
        self.last_begin_params = None
        self.last_update_kwargs = None

    def _on_activate(self):
        self.events.append("activate")

    def _on_begin(self, **params):
        self.events.append("begin")
        self.last_begin_params = dict(params)

    def _on_update(self, **kwargs):
        self.events.append("update")
        self.last_update_kwargs = dict(kwargs)

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
        self.assertEqual(tool.state, ToolState.IDLE)
        tool.activate()
        self.assertEqual(tool.state, ToolState.ACTIVE)
        tool.begin()
        self.assertEqual(tool.state, ToolState.INTERACTING)
        tool.update()
        tool.update()
        tool.commit()
        self.assertEqual(tool.state, ToolState.ACTIVE)
        tool.deactivate()
        self.assertEqual(tool.state, ToolState.IDLE)
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

    def test_is_active_and_is_interacting_properties(self):
        tool = self._new_tool()
        self.assertFalse(tool.is_active)
        self.assertFalse(tool.is_interacting)
        tool.activate()
        self.assertTrue(tool.is_active)
        self.assertFalse(tool.is_interacting)
        tool.begin()
        self.assertTrue(tool.is_active)
        self.assertTrue(tool.is_interacting)
        tool.cancel()
        tool.deactivate()
        self.assertFalse(tool.is_active)

    def test_begin_params_forwarded_to_hook(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin(scene="s", camera="c", vertex_ids={1, 2})
        self.assertEqual(
            tool.last_begin_params, {"scene": "s", "camera": "c", "vertex_ids": {1, 2}}
        )

    def test_update_kwargs_forwarded_to_hook(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin()
        tool.update(dx=10, dy=5, width=800, height=600)
        self.assertEqual(
            tool.last_update_kwargs, {"dx": 10, "dy": 5, "width": 800, "height": 600}
        )

    def test_update_before_begin_raises(self):
        tool = self._new_tool()
        with self.assertRaises(ToolStateError):
            tool.update()

    def test_commit_before_begin_raises(self):
        tool = self._new_tool()
        tool.activate()
        with self.assertRaises(ToolStateError):
            tool.commit()

    def test_cancel_before_begin_raises(self):
        tool = self._new_tool()
        tool.activate()
        with self.assertRaises(ToolStateError):
            tool.cancel()

    def test_begin_without_activate_raises(self):
        tool = self._new_tool()
        with self.assertRaises(ToolStateError):
            tool.begin()

    def test_activate_twice_raises(self):
        tool = self._new_tool()
        tool.activate()
        with self.assertRaises(ToolStateError):
            tool.activate()

    def test_begin_twice_raises(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin()
        with self.assertRaises(ToolStateError):
            tool.begin()

    def test_deactivate_while_interacting_raises(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin()
        with self.assertRaises(ToolStateError):
            tool.deactivate()

    def test_no_stale_state_after_commit(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin()
        tool.update()
        tool.commit()
        self.assertFalse(tool.is_interacting)
        self.assertEqual(tool.state, ToolState.ACTIVE)

    def test_no_stale_state_after_cancel(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin()
        tool.update()
        tool.cancel()
        self.assertFalse(tool.is_interacting)
        self.assertEqual(tool.state, ToolState.ACTIVE)

    def test_deactivate_without_interaction(self):
        tool = self._new_tool()
        tool.activate()
        tool.deactivate()
        self.assertEqual(tool.state.name, "IDLE")
        self.assertEqual(tool.events, ["activate", "deactivate"])

    def test_commit_returns_hook_result(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin()
        self.assertIsNone(tool.commit())

    def test_full_cycle_leaves_idle(self):
        tool = self._new_tool()
        tool.activate()
        tool.begin()
        tool.commit()
        tool.deactivate()
        tool.activate()  # erneute Nutzung desselben Tools (nach deactivate)
        tool.begin()
        tool.cancel()
        tool.deactivate()
        self.assertEqual(tool.state, ToolState.IDLE)


if __name__ == "__main__":
    unittest.main()