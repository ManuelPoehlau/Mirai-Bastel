"""Lab-Bindings (Handoff Slice 2 §4.5/§7, Slice 3 §4.1/§7, Slice 5 §4.3, Slice 7 E23) über das Production-`BindingSet`."""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction import input as input_module
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import GLOBAL_CONTEXT, TOPOLOGY_CONTEXT, Input

from symmetry_lab.lab_bindings import (
    KNIFE,
    LAB_OVERRIDES,
    RESYMMETRIZE,
    SYMMETRY_CYCLE,
    SYMMETRY_GATE_MODE,
    SYMMETRY_LAB_CONTEXT,
    apply_lab_bindings,
)

ALT_LMB = Input("mouse", "LEFT", frozenset({"alt"}))
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))
LMB = Input("mouse", "LEFT")
MMB = Input("mouse", "MIDDLE")
RMB = Input("mouse", "RIGHT")
WHEEL_UP = Input("wheel", "UP")
WHEEL_DOWN = Input("wheel", "DOWN")
SHIFT_S = Input("key", "s", frozenset({"shift"}))
SHIFT_B = Input("key", "b", frozenset({"shift"}))
Q = Input("key", "q")
W = Input("key", "w")
M = Input("key", "m")
C = Input("key", "c")
ESC = Input("key", "ESCAPE")
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))


@pytest.fixture
def bindings():
    app = Application()
    apply_lab_bindings(app.bindings)
    return app.bindings


@pytest.mark.parametrize(
    "inp,expected",
    [
        (ALT_LMB, cmd.ORBIT),
        (SHIFT_LMB, cmd.PAN),
        (MMB, cmd.PAN),
        (WHEEL_UP, cmd.ZOOM),
        (WHEEL_DOWN, cmd.ZOOM),
        (LMB, cmd.SELECT),
        (RMB, None),
        (SHIFT_S, SYMMETRY_CYCLE),
        (M, RESYMMETRIZE),
        (C, KNIFE),
        (W, cmd.MOVE),
        (Q, None),
        (ESC, cmd.CANCEL),
        (CTRL_Z, cmd.UNDO),
        (CTRL_Y, cmd.REDO),
    ],
)
def test_lab_context_resolution(bindings, inp, expected):
    assert bindings.command_for(inp, SYMMETRY_LAB_CONTEXT) == expected


def test_global_context_unchanged(bindings):
    reference = build_default_bindings()
    probes = [ALT_LMB, SHIFT_LMB, LMB, MMB, RMB, WHEEL_UP, WHEEL_DOWN, SHIFT_S, M, Q, ESC, CTRL_Z]
    for inp in probes:
        assert bindings.command_for(inp, GLOBAL_CONTEXT) == reference.command_for(
            inp, GLOBAL_CONTEXT
        )
    # WP-06 B2 (E8): RMB is unbound in the global defaults.
    assert bindings.command_for(RMB, GLOBAL_CONTEXT) is None
    assert bindings.command_for(SHIFT_S, GLOBAL_CONTEXT) is None
    # Slice 5 §4.3: M ist in den globalen Defaults frei.
    assert bindings.command_for(M, GLOBAL_CONTEXT) is None


def test_context_defined_in_lab_not_in_mirai_interaction():
    assert SYMMETRY_LAB_CONTEXT == "symmetry_lab"
    assert "symmetry_lab" not in vars(input_module).values()


def test_lab_commands_defined_in_lab_not_in_commands():
    assert SYMMETRY_CYCLE not in vars(cmd).values()
    assert RESYMMETRIZE not in vars(cmd).values()
    assert KNIFE not in vars(cmd).values()


def test_c_is_connect_in_global_and_lab_knife_in_symmetry_lab_context(bindings):
    # Seit WP-06 B6 ist C global an Connect gebunden; im Lab-Kontext gewinnt der Lab-Override (E23).
    assert bindings.command_for(C, GLOBAL_CONTEXT) == cmd.CONNECT
    assert bindings.command_for(C, SYMMETRY_LAB_CONTEXT) == KNIFE


def test_key_overrides_are_shift_s_m_c_and_shift_b():
    # W/ESC/Ctrl+Z/Ctrl+Y sind globale Defaults (Fallback), keine Overrides —
    # seit 2026-09-27 bedient sich Move im Lab wie in der App (W, Q ungebunden).
    keys = [o for o in LAB_OVERRIDES if o.input.kind == "key"]
    assert [(o.input, o.command) for o in keys] == [
        (SHIFT_S, SYMMETRY_CYCLE),
        (M, RESYMMETRIZE),
        (C, KNIFE),
        (SHIFT_B, SYMMETRY_GATE_MODE),
    ]
    assert "SymmetryCycle" in keys[0].describe()
    assert "ReSymmetrize" in keys[1].describe()
    assert "Knife" in keys[2].describe()
    assert "Artist E5 test" in keys[3].describe()
