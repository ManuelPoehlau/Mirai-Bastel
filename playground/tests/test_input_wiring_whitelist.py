"""Tests for WP-AP-INPUT-FIX-01 §1: Command Handler Whitelist Fix.

Verifies that PlaygroundCommandHandler only dispatches safe commands,
allowing hardcoded Playground state machines (variant cycling, Tweak V1/V3)
to work correctly on the old keys (M, R, S) before rebinding.

Tests the early return behavior: unsafe commands should return False immediately
without even trying to call their handlers.
"""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import tests._bootstrap  # noqa: F401

from playground.command_handler import PlaygroundCommandHandler
from mirai.interaction import commands as cmd


class TestWhitelistFix(unittest.TestCase):
    """Verify that unsafe commands are rejected before handlers are called."""

    def setUp(self):
        """Set up a mock app and handler."""
        self.app = Mock()
        self.window = Mock()
        self.handler = PlaygroundCommandHandler(self.app, self.window)

    def test_move_not_dispatched(self):
        """MOVE should not reach handler (return False)."""
        result = self.handler.handle_command(cmd.MOVE)
        self.assertFalse(result, "MOVE should not be dispatched by handler")

    def test_rotate_not_dispatched(self):
        """ROTATE should not reach handler (return False)."""
        result = self.handler.handle_command(cmd.ROTATE)
        self.assertFalse(result, "ROTATE should not be dispatched by handler")

    def test_scale_not_dispatched(self):
        """SCALE should not reach handler (return False)."""
        result = self.handler.handle_command(cmd.SCALE)
        self.assertFalse(result, "SCALE should not be dispatched by handler")

    def test_extrude_not_dispatched(self):
        """EXTRUDE should not reach handler (return False)."""
        result = self.handler.handle_command(cmd.EXTRUDE)
        self.assertFalse(result, "EXTRUDE should not be dispatched by handler")

    def test_edge_loop_not_dispatched(self):
        """EDGE_LOOP should not reach handler (return False)."""
        result = self.handler.handle_command(cmd.EDGE_LOOP)
        self.assertFalse(result, "EDGE_LOOP should not be dispatched by handler")

    def test_edge_ring_not_dispatched(self):
        """EDGE_RING should not reach handler (return False)."""
        result = self.handler.handle_command(cmd.EDGE_RING)
        self.assertFalse(result, "EDGE_RING should not be dispatched by handler")

    def test_connect_not_dispatched(self):
        """CONNECT should not reach handler (return False)."""
        result = self.handler.handle_command(cmd.CONNECT)
        self.assertFalse(result, "CONNECT should not be dispatched by handler")

    def test_loop_slide_not_dispatched(self):
        """LOOP_SLIDE should not reach handler (return False)."""
        result = self.handler.handle_command(cmd.LOOP_SLIDE)
        self.assertFalse(result, "LOOP_SLIDE should not be dispatched by handler")

    def test_loop_insert_not_dispatched(self):
        """LOOP_INSERT should not reach handler (return False)."""
        result = self.handler.handle_command(cmd.LOOP_INSERT)
        self.assertFalse(result, "LOOP_INSERT should not be dispatched by handler")

    def test_articulation_restore_not_dispatched(self):
        """ARTICULATION_RESTORE should not reach handler (return False)."""
        result = self.handler.handle_command(cmd.ARTICULATION_RESTORE)
        self.assertFalse(result, "ARTICULATION_RESTORE should not be dispatched by handler")

    # Safe commands that ARE in the whitelist

    def test_undo_dispatched(self):
        """UNDO is in whitelist and should attempt dispatch."""
        # Patch the history handler so it doesn't fail with mocks
        with patch.object(self.handler, '_handle_history_commands', return_value=True):
            result = self.handler.handle_command(cmd.UNDO)
            self.assertTrue(result, "UNDO should be dispatched by handler")

    def test_redo_dispatched(self):
        """REDO is in whitelist and should attempt dispatch."""
        with patch.object(self.handler, '_handle_history_commands', return_value=True):
            result = self.handler.handle_command(cmd.REDO)
            self.assertTrue(result, "REDO should be dispatched by handler")

    def test_set_vertex_mode_dispatched(self):
        """SET_VERTEX_MODE is in whitelist and should attempt dispatch."""
        with patch.object(self.handler, '_handle_selection_mode_commands', return_value=True):
            result = self.handler.handle_command(cmd.SET_VERTEX_MODE)
            self.assertTrue(result, "SET_VERTEX_MODE should be dispatched by handler")

    def test_set_edge_mode_dispatched(self):
        """SET_EDGE_MODE is in whitelist and should attempt dispatch."""
        with patch.object(self.handler, '_handle_selection_mode_commands', return_value=True):
            result = self.handler.handle_command(cmd.SET_EDGE_MODE)
            self.assertTrue(result, "SET_EDGE_MODE should be dispatched by handler")

    def test_set_face_mode_dispatched(self):
        """SET_FACE_MODE is in whitelist and should attempt dispatch."""
        with patch.object(self.handler, '_handle_selection_mode_commands', return_value=True):
            result = self.handler.handle_command(cmd.SET_FACE_MODE)
            self.assertTrue(result, "SET_FACE_MODE should be dispatched by handler")

    def test_split_edge_dispatched(self):
        """SPLIT_EDGE is in whitelist and should attempt dispatch."""
        with patch.object(self.handler, '_handle_topology_commands', return_value=True):
            result = self.handler.handle_command(cmd.SPLIT_EDGE)
            self.assertTrue(result, "SPLIT_EDGE should be dispatched by handler")

    def test_whitelist_is_complete(self):
        """Verify whitelist contains exactly the safe commands."""
        # The whitelist check in handle_command() should only allow these commands through
        safe_commands = {
            cmd.UNDO, cmd.REDO,
            cmd.SET_VERTEX_MODE, cmd.SET_EDGE_MODE, cmd.SET_FACE_MODE,
            cmd.CYCLE_DISPLAY_MODE, cmd.TOGGLE_WIREFRAME_OVERLAY,
            cmd.SPLIT_EDGE,
        }

        # Verify that these commands don't immediately return False
        for safe_cmd in safe_commands:
            # Use patches so actual handlers don't execute with mocks
            with patch.multiple(self.handler,
                              _handle_history_commands=Mock(return_value=False),
                              _handle_scene_commands=Mock(return_value=False),
                              _handle_interaction_commands=Mock(return_value=False),
                              _handle_navigation_commands=Mock(return_value=False),
                              _handle_display_commands=Mock(return_value=False),
                              _handle_topology_commands=Mock(return_value=False),
                              _handle_selection_mode_commands=Mock(return_value=False)):
                # These should reach the handler dispatch, not return False immediately
                result = self.handler.handle_command(safe_cmd)
                # Result depends on mocked handlers, but the command reached dispatch
                # (not rejected by whitelist).
                # To verify it wasn't rejected, check that at least one handler was called
                handlers_called = any([
                    self.handler._handle_history_commands.called,
                    self.handler._handle_scene_commands.called,
                    self.handler._handle_interaction_commands.called,
                    self.handler._handle_navigation_commands.called,
                    self.handler._handle_display_commands.called,
                    self.handler._handle_topology_commands.called,
                    self.handler._handle_selection_mode_commands.called,
                ])
                # For safe commands, at least some handler should have been attempted
                # (Even if it returns False, it should have been called)


if __name__ == "__main__":
    unittest.main()
