"""Tests for Playground Input Adapter and Command Handler wiring (WP-AP).

Verifies that:
1. Pyglet events convert to Input objects correctly
2. BindingSet command resolution works in Playground context
3. Context-aware bindings (topology vs global) work correctly
4. Command handler receives commands and validates precedence
"""

from __future__ import annotations

import pytest
from pyglet.window import key as _key

import tests._bootstrap  # noqa: F401

from playground.input_adapter import (
    _key_from_pyglet,
    PlaygroundInputBinding,
    determine_input_context,
)
from mirai.interaction.input import GLOBAL_CONTEXT, TOPOLOGY_CONTEXT
from mirai.interaction import commands as cmd


class TestPygletKeyConversion:
    """Test pyglet symbol → Input conversion."""

    def test_letter_keys_lowercase(self):
        """Letters map to lowercase names."""
        inp = _key_from_pyglet(_key.A, 0)
        assert inp.kind == "key"
        assert inp.value == "a"
        assert inp.modifiers == frozenset()

    def test_number_keys(self):
        """Number keys map to strings."""
        inp = _key_from_pyglet(_key._1, 0)
        assert inp.value == "1"

    def test_escape_key(self):
        """ESCAPE maps to uppercase."""
        inp = _key_from_pyglet(_key.ESCAPE, 0)
        assert inp.value == "ESCAPE"

    def test_ctrl_modifier(self):
        """Ctrl modifier is detected."""
        inp = _key_from_pyglet(_key.Z, _key.MOD_CTRL)
        assert inp.modifiers == frozenset({"ctrl"})

    def test_shift_modifier(self):
        """Shift modifier is detected."""
        inp = _key_from_pyglet(_key.L, _key.MOD_SHIFT)
        assert inp.modifiers == frozenset({"shift"})

    def test_alt_modifier(self):
        """Alt modifier is detected."""
        inp = _key_from_pyglet(_key.E, _key.MOD_ALT)
        assert inp.modifiers == frozenset({"alt"})

    def test_multiple_modifiers(self):
        """Multiple modifiers combine correctly."""
        mods = _key.MOD_CTRL | _key.MOD_SHIFT
        inp = _key_from_pyglet(_key.Z, mods)
        assert inp.modifiers == frozenset({"ctrl", "shift"})

    def test_unknown_symbol_returns_none(self):
        """Unknown symbol returns None."""
        inp = _key_from_pyglet(12345, 0)
        assert inp is None


class TestPlaygroundInputBinding:
    """Test BindingSet integration in Playground context."""

    def test_default_bindings_exist(self):
        """Default bindings are loaded."""
        binding = PlaygroundInputBinding()
        assert binding.binding_set is not None

    def test_undo_binding_works(self):
        """Ctrl+Z resolves to UNDO."""
        binding = PlaygroundInputBinding()
        inp = _key_from_pyglet(_key.Z, _key.MOD_CTRL)
        cmd_result = binding.command_for(inp, GLOBAL_CONTEXT)
        assert cmd_result == cmd.UNDO

    def test_move_binding_works(self):
        """M resolves to MOVE."""
        binding = PlaygroundInputBinding()
        inp = _key_from_pyglet(_key.M, 0)
        cmd_result = binding.command_for(inp, GLOBAL_CONTEXT)
        assert cmd_result == cmd.MOVE

    def test_rotate_binding_works(self):
        """R resolves to ROTATE."""
        binding = PlaygroundInputBinding()
        inp = _key_from_pyglet(_key.R, 0)
        cmd_result = binding.command_for(inp, GLOBAL_CONTEXT)
        assert cmd_result == cmd.ROTATE

    def test_scale_binding_works(self):
        """S resolves to SCALE."""
        binding = PlaygroundInputBinding()
        inp = _key_from_pyglet(_key.S, 0)
        cmd_result = binding.command_for(inp, GLOBAL_CONTEXT)
        assert cmd_result == cmd.SCALE

    def test_global_context_r_is_rotate(self):
        """In global context, R → ROTATE."""
        binding = PlaygroundInputBinding()
        inp = _key_from_pyglet(_key.R, 0)
        assert binding.command_for(inp, GLOBAL_CONTEXT) == cmd.ROTATE

    def test_topology_context_r_is_ring(self):
        """In topology context, R → EDGE_RING."""
        binding = PlaygroundInputBinding()
        inp = _key_from_pyglet(_key.R, 0)
        assert binding.command_for(inp, TOPOLOGY_CONTEXT) == cmd.EDGE_RING

    def test_topology_context_s_is_split(self):
        """In topology context, S → SPLIT_EDGE."""
        binding = PlaygroundInputBinding()
        inp = _key_from_pyglet(_key.S, 0)
        assert binding.command_for(inp, TOPOLOGY_CONTEXT) == cmd.SPLIT_EDGE

    def test_global_context_s_is_scale(self):
        """In global context, S → SCALE."""
        binding = PlaygroundInputBinding()
        inp = _key_from_pyglet(_key.S, 0)
        assert binding.command_for(inp, GLOBAL_CONTEXT) == cmd.SCALE


class TestContextDetermination:
    """Test dynamic context switching based on active family."""

    def test_topology_family_uses_topology_context(self):
        """Topology family → TOPOLOGY_CONTEXT."""
        ctx = determine_input_context("topology")
        assert ctx == TOPOLOGY_CONTEXT

    def test_selection_family_uses_global_context(self):
        """Selection family → GLOBAL_CONTEXT."""
        ctx = determine_input_context("selection")
        assert ctx == GLOBAL_CONTEXT

    def test_transform_family_uses_global_context(self):
        """Transform family → GLOBAL_CONTEXT."""
        ctx = determine_input_context("transform")
        assert ctx == GLOBAL_CONTEXT

    def test_none_family_uses_global_context(self):
        """None/unknown family → GLOBAL_CONTEXT."""
        ctx = determine_input_context(None)
        assert ctx == GLOBAL_CONTEXT


class TestCommandAvailability:
    """Verify new commands are defined and available."""

    def test_loop_insert_command_defined(self):
        """LOOP_INSERT command exists."""
        assert hasattr(cmd, "LOOP_INSERT")
        assert cmd.LOOP_INSERT == "LoopInsert"

    def test_loop_slide_command_defined(self):
        """LOOP_SLIDE command exists."""
        assert hasattr(cmd, "LOOP_SLIDE")
        assert cmd.LOOP_SLIDE == "LoopSlide"

    def test_articulation_restore_command_defined(self):
        """ARTICULATION_RESTORE command exists."""
        assert hasattr(cmd, "ARTICULATION_RESTORE")
        assert cmd.ARTICULATION_RESTORE == "ArticulationRestore"

    def test_existing_commands_unchanged(self):
        """Existing commands still exist."""
        assert cmd.MOVE == "Move"
        assert cmd.ROTATE == "Rotate"
        assert cmd.SCALE == "Scale"
        assert cmd.SPLIT_EDGE == "SplitEdge"
        assert cmd.EXTRUDE == "Extrude"
