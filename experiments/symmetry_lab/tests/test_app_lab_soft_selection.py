"""Soft Selection in the Symmetry Lab (WP-SOFT-01 S2a/S2d, AD-020 §8 / AD-013 G-2 note 2026-10-10, 2026-10-11).

The soft setting commands (S2d: custom-curve shape and the band switch included) are `NON_OPERATION`
(state for the next gesture, like the constraints):
O stays allowed under BLOCK, so soft can be switched off while symmetry is on. Since AD-SYM-04 SS2
Soft + symmetry runs as symmetric Soft (no gate row changed: W/E/R are Core ops that declare
`supports_symmetry`, the soft commands stay `NON_OPERATION`); MARK and BLOCK behave the same, for
the gesture and for the refusals that remain (`soft_selection.symmetric`).
"""

from __future__ import annotations

import pytest

from mirai.symmetry import CorrespondenceState, vertex_correspondence
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input

from symmetry_lab.lab_app import BLOCK_NOT_ALLOWED_TEXT, NON_OPERATION, GateMode, block_row, e5_warning_text

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
CTRL_WHEEL_UP = Input("wheel", "UP", frozenset({"ctrl"}))
CTRL_WHEEL_DOWN = Input("wheel", "DOWN", frozenset({"ctrl"}))
ALT_O = Input("key", "o", frozenset({"alt"}))
LMB = Input("mouse", "LEFT")

SOFT_COMMANDS = {
    cmd.SOFT_TOGGLE,
    cmd.SOFT_RADIUS_UP,
    cmd.SOFT_RADIUS_DOWN,
    cmd.SOFT_CURVE_CYCLE,
    cmd.SOFT_METRIC_CYCLE,
    cmd.SOFT_CURVE_SHAPE_ROUNDER,
    cmd.SOFT_CURVE_SHAPE_SHARPER,
    cmd.SOFT_BANDS_TOGGLE,
    cmd.SOFT_VIEW_MODE_CYCLE,
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


def test_curve_shape_and_band_switch_pass_block_and_change_nothing_else():
    """S2d: Ctrl+wheel (custom-curve shape) and Alt+O (bands) are state commands like the others."""
    app, lab = _symmetric_lab(GateMode.BLOCK)
    before = _state(app)
    assert app.pointer_scroll(CTRL_WHEEL_UP) is True  # the wheel path passes the same gate
    assert app.pointer_scroll(CTRL_WHEEL_DOWN) is True
    assert app.soft_settings.curve == "custom"
    assert app.status_message.startswith("Soft: ") and app.status_message != BLOCK_NOT_ALLOWED_TEXT
    assert press(app, lab, ALT_O) is True
    assert app.soft_settings.bands_visible is False
    assert app.status_message.endswith("bands off")
    assert press(app, lab, ALT_O) is True and app.soft_settings.bands_visible
    assert _state(app) == before


def _ring_on_plus_x(app):
    """The paired +X vertex nearest the plane and its paired +X one-ring (subd_cube)."""
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    side = sorted((mesh.vertex_position(v)[0], int(v), v) for v, c in corr.items()
                  if c.state is CorrespondenceState.PAIRED and mesh.vertex_position(v)[0] > 0.0)
    seeds = {side[0][2]}
    for eid in mesh.vertex_edges(side[0][2]):
        seeds.update(w for w in mesh.edge_vertices(eid)
                     if corr[w].state is CorrespondenceState.PAIRED and mesh.vertex_position(w)[0] > 0.0)
    return seeds, corr


def _soft_gesture(mode, key, seeds_of=_ring_on_plus_x, armed_first=False):
    app, lab = _symmetric_lab(mode)
    seeds, corr = seeds_of(app)
    app.selection.set(seeds)
    app.viewport.on_selection_changed()
    if armed_first:
        assert press(app, lab, key)  # armed (soft off), O after the arm: read at begin()
        assert press(app, lab, O)
    else:
        assert press(app, lab, O)
        for _ in range(6):  # 15 % -> 100 %: the falloff crosses the plane on subd_cube
            assert app.pointer_scroll(SHIFT_WHEEL_UP) is True
        assert press(app, lab, key)
    before = _state(app)
    moved = app.pointer_motion(400, 300, 12.0, 7.0)
    if moved:
        assert e5_warning_text(lab) == ""  # W/E/R declare `supports_symmetry`: no one-sided warning
        app.pointer_motion(410, 300, 20.0, -6.0)
        app.key_release(key)
    return app, lab, corr, before, moved


@pytest.mark.parametrize("armed_first", [False, True], ids=["o-then-key", "key-then-o"])
@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_symmetric_soft_runs_alike_in_mark_and_block(key, armed_first):
    results = {}
    for mode in (GateMode.BLOCK, GateMode.MARK):
        app, lab, corr, before, moved = _soft_gesture(mode, key, armed_first=armed_first)
        assert moved, app.status_message
        mesh = app.scene.mesh
        assert len(app.history) == before[1] + 1
        for vid, c in corr.items():
            p = mesh.vertex_position(vid)
            if c.state is CorrespondenceState.PAIRED:
                assert mesh.vertex_position(c.partner) == (-p[0], p[1], p[2])
            elif c.state is CorrespondenceState.SEAM:
                assert p[0] == 0.0
        results[mode] = mesh.export_state()
    assert results[GateMode.BLOCK] == results[GateMode.MARK]


def _both_sides(app):
    seeds, corr = _ring_on_plus_x(app)
    seed = min(seeds)
    return {seed, corr[seed].partner}, corr


def _seam_only(app):
    _seeds, corr = _ring_on_plus_x(app)
    return {min(v for v, c in corr.items() if c.state is CorrespondenceState.SEAM)}, corr


@pytest.mark.parametrize("seeds_of", [_both_sides, _seam_only], ids=["both-sides", "seam-only"])
def test_both_sides_and_seam_only_selections_run_alike_in_mark_and_block(seeds_of):
    """Manu 2026-10-14: no refusal any more (explicit selection wins / in the plane)."""
    results = {}
    for mode in (GateMode.BLOCK, GateMode.MARK):
        app, lab, _corr, before, moved = _soft_gesture(mode, W, seeds_of=seeds_of)
        assert moved, app.status_message
        assert len(app.history) == before[1] + 1
        results[mode] = app.scene.mesh.export_state()
    assert results[GateMode.BLOCK] == results[GateMode.MARK]


# -- bands (AD-SYM-04 D-5, SS3): they come from `Application`; MARK and BLOCK show the same -----


def _band_lab(mode: GateMode):
    from mirai.soft_selection import GLSoftBandOverlay
    from symmetry_lab.run import HEADLESS_GL_TYPES, build_app_lab

    from ._app_lab_support import HEIGHT, WIDTH

    app, lab = build_app_lab(
        "subd_cube", WIDTH, HEIGHT,
        gl_types={**HEADLESS_GL_TYPES, "soft_overlay_type": GLSoftBandOverlay},
    )
    assert press(app, lab, SHIFT_S) and lab.axis == "X"
    if lab.gate_mode is not mode:
        assert press(app, lab, SHIFT_B)
    return app, lab


def test_symmetric_bands_are_the_apps_and_alike_in_mark_and_block():
    from mirai.soft_selection import SoftBands, symmetric_influence

    shown = {}
    for mode in (GateMode.BLOCK, GateMode.MARK):
        app, lab = _band_lab(mode)
        seeds, corr = _ring_on_plus_x(app)
        app.selection.set(seeds)
        app.viewport.on_selection_changed()
        assert press(app, lab, O)
        for _ in range(6):  # 15 % -> 100 %: the falloff crosses the plane on subd_cube
            assert app.pointer_scroll(SHIFT_WHEEL_UP) is True
        soft = app.soft_settings
        field = symmetric_influence(
            app.scene.mesh, seeds, soft.world_radius, soft.metric, soft.curve, soft.curve_power
        )
        preview = app.soft_bands
        assert preview == SoftBands.from_weights(field.weights) and preview.count > 0
        assert press(app, lab, W) and app.pointer_motion(400, 300, 12.0, 7.0)
        during = app.soft_bands
        assert during == preview  # the op's own weights (fixed at begin())
        app.key_release(W)
        shown[mode] = (preview, during, app.soft_bands)
    assert shown[GateMode.BLOCK] == shown[GateMode.MARK]
