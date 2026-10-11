"""Soft Selection in the Symmetry Lab (WP-SOFT-01 S2a, AD-020 §8 / AD-013 G-2 note 2026-10-10).

The soft setting commands are `NON_OPERATION` (state for the next gesture, like the constraints):
O stays allowed under BLOCK, so soft can be switched off while symmetry is on. Soft + symmetry is
refused by `Application`, authoritatively at `begin()`, in MARK and BLOCK alike.
"""

from __future__ import annotations

import pytest

from mirai.application import SOFT_SYMMETRY_REFUSAL
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input

from symmetry_lab.lab_app import BLOCK_NOT_ALLOWED_TEXT, NON_OPERATION, GateMode, block_row

from ._app_lab_support import (  # noqa: F401
    ESC,
    SHIFT_B,
    SHIFT_S,
    W,
    forbid_lab_calls,
    make_lab,
    press,
    screen,
    visible,
)

E = Input("key", "e")
R = Input("key", "r")
O = Input("key", "o")
SHIFT_O = Input("key", "o", frozenset({"shift"}))
CTRL_O = Input("key", "o", frozenset({"ctrl"}))
SHIFT_WHEEL_UP = Input("wheel", "UP", frozenset({"shift"}))
LMB = Input("mouse", "LEFT")

SOFT_COMMANDS = {
    cmd.SOFT_TOGGLE,
    cmd.SOFT_RADIUS_UP,
    cmd.SOFT_RADIUS_DOWN,
    cmd.SOFT_CURVE_CYCLE,
    cmd.SOFT_METRIC_CYCLE,
}


def _symmetric_lab(mode: GateMode):
    app, lab = make_lab()
    assert press(app, lab, SHIFT_S) and lab.axis == "X"
    if lab.gate_mode is not mode:
        assert press(app, lab, SHIFT_B)
    assert lab.gate_mode is mode
    v0 = visible(app)[0]
    app.pointer_press(LMB, *screen(app, v0))
    app.pointer_release("LEFT", *screen(app, v0))
    assert v0 in app.selection.vertices
    app.set_status("")
    return app, lab


def _state(app):
    return app.scene.mesh.export_state(), len(app.history)


def test_the_soft_commands_are_in_non_operation_and_pass_the_block_row():
    assert SOFT_COMMANDS <= NON_OPERATION
    gate = block_row().gate
    assert SOFT_COMMANDS <= gate.allowed
    assert all(gate.refusal(command) is None for command in SOFT_COMMANDS)


def test_o_is_allowed_under_block_and_never_refused_as_not_coordinated():
    app, lab = _symmetric_lab(GateMode.BLOCK)
    assert lab.gate_mode is GateMode.BLOCK
    before = _state(app)
    for key in (O, SHIFT_O, CTRL_O):
        assert press(app, lab, key) is True
        assert app.status_message.startswith("Soft: ")
        assert app.status_message != BLOCK_NOT_ALLOWED_TEXT
    assert app.pointer_scroll(SHIFT_WHEEL_UP) is True  # the wheel path passes the same gate
    assert app.status_message.startswith("Soft: ")
    assert _state(app) == before


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK])
@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_armed_then_o_then_motion_is_refused_visibly(mode, key):
    app, lab = _symmetric_lab(mode)
    before = _state(app)
    assert press(app, lab, key)  # armed (soft is off)
    assert press(app, lab, O)  # soft on while armed: the arm-time check is already past
    assert app.soft_settings.enabled
    assert app.pointer_motion(400, 300, 12.0, 7.0) is False
    assert SOFT_SYMMETRY_REFUSAL in app.status_message and "refused" in app.status_message
    assert app.interaction_owner is None and not app.transform_interacting
    assert _state(app) == before  # no history, mesh unchanged
    # O is the way out: soft off, then the symmetric transform runs as before.
    assert press(app, lab, O) and not app.soft_settings.enabled
    assert press(app, lab, key)
    app.pointer_motion(400, 300, 12.0, 7.0)
    assert app.transform_interacting
    assert press(app, lab, ESC)
    assert _state(app) == before


@pytest.mark.parametrize("mode", [GateMode.BLOCK, GateMode.MARK])
def test_o_then_w_is_refused_at_the_key_press(mode):
    app, lab = _symmetric_lab(mode)
    before = _state(app)
    assert press(app, lab, O)
    assert press(app, lab, W) is False
    assert SOFT_SYMMETRY_REFUSAL in app.status_message
    assert app.interaction_owner is None
    assert _state(app) == before
