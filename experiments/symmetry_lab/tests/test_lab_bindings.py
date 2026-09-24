"""Lab-Bindings (Handoff Slice 2 §4.5/§7) über das Production-`BindingSet`."""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction import input as input_module
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import GLOBAL_CONTEXT, Input

from symmetry_lab.lab_bindings import SYMMETRY_LAB_CONTEXT, apply_lab_bindings

ALT_LMB = Input("mouse", "LEFT", frozenset({"alt"}))
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))
LMB = Input("mouse", "LEFT")
MMB = Input("mouse", "MIDDLE")
RMB = Input("mouse", "RIGHT")
WHEEL_UP = Input("wheel", "UP")
WHEEL_DOWN = Input("wheel", "DOWN")


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
    ],
)
def test_lab_context_resolution(bindings, inp, expected):
    assert bindings.command_for(inp, SYMMETRY_LAB_CONTEXT) == expected


def test_global_context_unchanged(bindings):
    reference = build_default_bindings()
    probes = [ALT_LMB, SHIFT_LMB, LMB, MMB, RMB, WHEEL_UP, WHEEL_DOWN]
    for inp in probes:
        assert bindings.command_for(inp, GLOBAL_CONTEXT) == reference.command_for(
            inp, GLOBAL_CONTEXT
        )
    assert bindings.command_for(RMB, GLOBAL_CONTEXT) == cmd.ORBIT


def test_context_defined_in_lab_not_in_mirai_interaction():
    assert SYMMETRY_LAB_CONTEXT == "symmetry_lab"
    assert "symmetry_lab" not in vars(input_module).values()
