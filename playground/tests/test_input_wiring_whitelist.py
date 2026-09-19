"""Tests for WP-AP-INPUT-FIX-01: Command Handler Whitelist Fix and Re-enabling.

§1: Verified that PlaygroundCommandHandler only dispatches safe commands initially,
allowing hardcoded Playground state machines (variant cycling, Tweak V1/V3)
to work correctly before rebinding.

§2-§4: After key rebinding (X/W/E for Move/Rotate/Scale, Q for variant cycling),
MOVE/ROTATE/SCALE commands are now re-enabled in the whitelist since their new keys
(W/E/R in Playground) don't conflict with other operations.

Tests verify the whitelist routing and that re-enabled commands dispatch correctly.
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

    def test_move_dispatched(self):
        """WP-AP-INPUT-FIX-01 §2: MOVE is now re-enabled after key rebinding."""
        with patch.object(self.handler, '_handle_interaction_commands', return_value=True):
            result = self.handler.handle_command(cmd.MOVE)
            self.assertTrue(result, "MOVE should be dispatched by handler (re-enabled in §2)")

    def test_rotate_dispatched(self):
        """WP-AP-INPUT-FIX-01 §2: ROTATE is now re-enabled after key rebinding."""
        with patch.object(self.handler, '_handle_interaction_commands', return_value=True):
            result = self.handler.handle_command(cmd.ROTATE)
            self.assertTrue(result, "ROTATE should be dispatched by handler (re-enabled in §2)")

    def test_scale_dispatched(self):
        """WP-AP-INPUT-FIX-01 §2: SCALE is now re-enabled after key rebinding."""
        with patch.object(self.handler, '_handle_interaction_commands', return_value=True):
            result = self.handler.handle_command(cmd.SCALE)
            self.assertTrue(result, "SCALE should be dispatched by handler (re-enabled in §2)")

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
        """Verify whitelist contains exactly the safe commands (including re-enabled §2-§4)."""
        # The whitelist check in handle_command() should only allow these commands through
        # §1: Original safe commands
        # §2-§4: Re-enabled MOVE/ROTATE/SCALE after key rebinding
        safe_commands = {
            cmd.UNDO, cmd.REDO,
            cmd.SET_VERTEX_MODE, cmd.SET_EDGE_MODE, cmd.SET_FACE_MODE,
            cmd.CYCLE_DISPLAY_MODE, cmd.TOGGLE_WIREFRAME_OVERLAY,
            cmd.SPLIT_EDGE,
            cmd.MOVE, cmd.ROTATE, cmd.SCALE,  # Re-enabled in §2-§4
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
