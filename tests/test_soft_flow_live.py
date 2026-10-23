"""Soft Selection Loop / Ring flow in the Production app path (AD-020 "Loop / Ring flow", `PROVISIONAL`).

Headless `Application` on the head asset with the real influence sinks (data side). Pins:

- Ctrl+Shift+wheel (up = Loop, down = Ring) steps the sticky balance outside a gesture, never zooms, never
  moves anything; the status line names it and says when the seeds give no direction;
- the preview, the op at `begin()` and the display use the same field (`compute_influence` with the flow);
- during a begun Soft Move/Rotate/Scale it re-evaluates the gesture from its start geometry like a live radius
  step: the result equals a gesture begun at that balance, steps never accumulate, pivot / intent are kept,
  the live radius still works and keeps the balance; one History entry, exact Undo/Redo, Cancel;
- the display shows the op's current weights (bands / faces), nothing while hidden;
- under a symmetry definition the symmetric field with the flow, pairs consistent.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from tests.test_soft_live_radius import (
    ALT_O,
    ALT_SHIFT_O,
    CTRL_Y,
    CTRL_Z,
    ESC,
    KEYS,
    MORE,
    MOTIONS,
    O,
    UP,
    W,
    E,
    _close,
    _make_app,
    _move,
    _op,
    _positions,
    _seed,
    _start_mesh,
    _wheel,
)

from mirai.soft_selection import (
    DEFAULT_FLOW_STEP,
    FLOW_STEPS,
    SoftBands,
    compute_influence,
    has_flow_direction,
    symmetric_influence,
)
from mirai.symmetry import CorrespondenceState, vertex_correspondence
from mirai.symmetry_axis import set_symmetry_axis

LOOP_UP, RING_DOWN = _wheel("UP", "ctrl", "shift"), _wheel("DOWN", "ctrl", "shift")


def _influence(mesh, seeds, soft):
    return compute_influence(
        mesh, seeds, soft.world_radius, soft.metric, soft.curve, soft.curve_power, flow_ratio=soft.flow_ratio
    )


def _edge_seeds(app) -> set:
    """The vertex nearest the camera and a neighbour: an edge seed whose field the flow changes."""
    mesh, first = app.scene.mesh, _seed(app)
    soft = app.soft_settings
    for eid in mesh.vertex_edges(first):
        seeds = set(mesh.edge_vertices(eid))
        neutral = compute_influence(mesh, seeds, soft.world_radius, "geodesic")
        if has_flow_direction(mesh, seeds) and all(
            compute_influence(mesh, seeds, soft.world_radius, "geodesic", flow_ratio=r) != neutral
            for r in (0.25, 4.0)
        ):
            return seeds
    raise AssertionError("no edge at the nearest vertex is changed by the flow")


def _ready(cursor: bool = False, flow_steps: int = 0, symmetric: bool = False):
    app = _make_app(cursor)
    if symmetric:
        set_symmetry_axis(app.scene.mesh, "X")
        app.viewport.on_topology_changed()
    assert app.key_press(O)
    for _ in range(3):  # 20 %: a field wide enough to show the anisotropy on the head
        assert app.pointer_scroll(_wheel("UP", "shift"))
    seeds = _edge_seeds(app)
    app.selection.set(seeds)
    app.viewport.on_selection_changed()
    for _ in range(abs(flow_steps)):
        assert app.pointer_scroll(LOOP_UP if flow_steps > 0 else RING_DOWN)
    return app, seeds


# -- outside a gesture ---------------------------------------------------------------------------------


def test_ctrl_shift_wheel_steps_the_sticky_balance_and_nothing_else():
    app, seeds = _ready()
    distance, start = app.camera.distance, _positions(app)
    assert app.soft_settings.flow_step == DEFAULT_FLOW_STEP
    assert "flow 1:1" in app.soft_settings.status_text()
    assert app.pointer_scroll(LOOP_UP)
    assert app.soft_settings.flow_step == DEFAULT_FLOW_STEP + 1 and "flow loop 3:2" in app.status_message
    assert app.pointer_scroll(RING_DOWN) and app.pointer_scroll(RING_DOWN)
    assert "flow ring 3:2" in app.status_message
    assert app.camera.distance == distance and _positions(app) == start
    assert not app.history.can_undo() and app.selection.vertices == seeds


def test_balance_clamps_at_both_ends():
    app, _ = _ready()
    while app.soft_settings.flow_step < len(FLOW_STEPS) - 1:
        assert app.pointer_scroll(LOOP_UP)
    assert app.pointer_scroll(LOOP_UP) is False and "flow loop 4:1" in app.status_message
    while app.soft_settings.flow_step > 0:
        assert app.pointer_scroll(RING_DOWN)
    assert app.pointer_scroll(RING_DOWN) is False and "flow ring 4:1" in app.status_message


def test_status_says_when_the_seeds_have_no_direction():
    app, _ = _ready()
    one = {_seed(app)}
    app.selection.set(one)
    app.viewport.on_selection_changed()
    assert app.pointer_scroll(LOOP_UP)
    assert "no loop/ring direction here" in app.status_message
    app.selection.set(_edge_seeds(app))
    app.viewport.on_selection_changed()
    assert app.pointer_scroll(LOOP_UP)
    assert "no loop/ring direction" not in app.status_message


@pytest.mark.parametrize("mode", ["bands", "faces"])
def test_preview_op_and_display_use_the_same_field(mode):
    app, seeds = _ready(flow_steps=3)
    if mode == "faces":
        assert app.key_press(ALT_SHIFT_O)
    soft = app.soft_settings
    expected = _influence(app.scene.mesh, seeds, soft)
    assert expected != compute_influence(app.scene.mesh, seeds, soft.world_radius, soft.metric)
    shown = app.soft_shading if mode == "faces" else app.soft_bands
    assert shown == (expected if mode == "faces" else SoftBands.from_weights(expected))
    assert app.key_press(W)
    _move(app, MOTIONS)
    assert _op(app).weights == expected
    assert app.key_release(W)


# -- live during a running Soft gesture -----------------------------------------------------------


@pytest.mark.parametrize("op_name", sorted(KEYS))
@pytest.mark.parametrize("wheel,steps", [(LOOP_UP, 3), (RING_DOWN, -3)], ids=["loop", "ring"])
def test_live_balance_reweights_from_the_start_geometry(op_name, wheel, steps):
    app, seeds = _ready()
    start = _positions(app)
    eye = app.camera.eye()
    assert app.key_press(KEYS[op_name])
    _move(app, MOTIONS)
    first = _op(app)
    for _ in range(abs(steps)):
        assert app.pointer_scroll(wheel)
    assert _op(app) is not first and app.camera.eye() == eye
    soft = app.soft_settings
    assert soft.flow_step == DEFAULT_FLOW_STEP + steps
    assert _op(app).weights == _influence(_start_mesh(start, app), seeds, soft)
    assert _op(app).weights != first.weights
    assert app.key_release(KEYS[op_name])


@pytest.mark.parametrize("op_name", sorted(KEYS))
@pytest.mark.parametrize("cursor", [False, True], ids=["drag_x", "dial"])
def test_result_equals_a_gesture_begun_at_that_balance_and_the_drag_continues(op_name, cursor):
    live, _ = _ready(cursor)
    assert live.key_press(KEYS[op_name])
    _move(live, MOTIONS)
    for _ in range(2):
        assert live.pointer_scroll(LOOP_UP)
    fresh, _ = _ready(cursor, flow_steps=2)
    assert fresh.key_press(KEYS[op_name])
    _move(fresh, MOTIONS)
    assert _op(live).weights == _op(fresh).weights
    assert _close(_positions(live), _positions(fresh))
    _move(live, MORE)
    _move(fresh, MORE)
    assert live.key_release(KEYS[op_name]) and fresh.key_release(KEYS[op_name])
    assert _close(_positions(live), _positions(fresh))


@pytest.mark.parametrize("op_name", sorted(KEYS))
def test_balance_steps_never_accumulate(op_name):
    app, _ = _ready()
    assert app.key_press(KEYS[op_name])
    _move(app, MOTIONS)
    before = _positions(app)
    assert app.pointer_scroll(LOOP_UP)
    once = _positions(app)
    assert once != before
    assert app.pointer_scroll(RING_DOWN)
    back = _positions(app)
    assert _close(back, before)
    for _ in range(4):
        assert app.pointer_scroll(LOOP_UP) and _positions(app) == once
        assert app.pointer_scroll(RING_DOWN) and _positions(app) == back
    assert app.key_press(ESC)


def test_pivot_and_intent_are_kept_and_the_live_radius_keeps_the_balance():
    app, seeds = _ready(cursor=True)
    start = _positions(app)
    assert app.key_press(E)
    _move(app, MOTIONS)
    tool = app.tool_manager.active_tool
    pivot, axis, angle = _op(app).pivot, tool.axis, tool._applied_angle
    assert app.pointer_scroll(LOOP_UP) and app.pointer_scroll(LOOP_UP)
    assert _op(app).pivot == pivot and tool.axis == axis and tool._applied_angle == angle
    assert app.pointer_scroll(UP)  # plain wheel: the live radius, the balance stays
    soft = app.soft_settings
    assert soft.flow_step == DEFAULT_FLOW_STEP + 2
    assert _op(app).weights == _influence(_start_mesh(start, app), seeds, soft)
    assert _op(app).pivot == pivot
    assert app.key_press(ESC)


@pytest.mark.parametrize("op_name", sorted(KEYS))
def test_one_history_entry_exact_undo_redo_and_cancel(op_name):
    app, seeds = _ready()
    start = _positions(app)
    assert app.key_press(KEYS[op_name])
    _move(app, MOTIONS)
    for wheel in (LOOP_UP, LOOP_UP, RING_DOWN, UP, LOOP_UP):
        assert app.pointer_scroll(wheel)
    _move(app, MORE)
    assert app.key_release(KEYS[op_name])
    end = _positions(app)
    assert end != start
    assert app.key_press(CTRL_Z) and _positions(app) == start and not app.history.can_undo()
    assert app.key_press(CTRL_Y) and _positions(app) == end

    assert app.key_press(KEYS[op_name])
    _move(app, MOTIONS)
    assert app.pointer_scroll(RING_DOWN)
    assert app.key_press(ESC) and _positions(app) == end
    assert app.selection.vertices == seeds


@pytest.mark.parametrize("mode", ["bands", "faces", "hidden"])
def test_display_follows_the_live_balance(mode):
    app, _ = _ready()
    if mode == "faces":
        assert app.key_press(ALT_SHIFT_O)
    if mode == "hidden":
        assert app.key_press(ALT_O)
    assert app.key_press(W)
    _move(app, MOTIONS)
    assert app.pointer_scroll(LOOP_UP) and app.pointer_scroll(LOOP_UP)
    weights = _op(app).weights
    if mode == "bands":
        assert app.soft_bands == SoftBands.from_weights(weights) and app.soft_shading == {}
    elif mode == "faces":
        assert app.soft_shading == weights and not app.soft_bands.weights
    else:
        assert not app.soft_bands.weights and app.soft_shading == {}
    assert app.key_release(W)


def test_balance_during_a_plain_transform_is_sticky_and_moves_nothing_extra():
    app, seeds = _ready()
    assert app.key_press(O)  # Soft off: a plain Move
    assert app.key_press(W)
    _move(app, MOTIONS)
    moved = _positions(app)
    assert app.pointer_scroll(LOOP_UP)
    assert _positions(app) == moved and app.soft_settings.flow_step == DEFAULT_FLOW_STEP + 1
    assert app.key_release(W)


@pytest.mark.parametrize("op_name", sorted(KEYS))
def test_symmetric_live_balance_keeps_pairs_consistent(op_name):
    app, seeds = _ready(cursor=True, symmetric=True)
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    start = _positions(app)
    assert app.key_press(KEYS[op_name])
    _move(app, MOTIONS)
    assert app.pointer_scroll(LOOP_UP) and app.pointer_scroll(LOOP_UP)
    soft = app.soft_settings
    field = symmetric_influence(
        _start_mesh(start, app), seeds, soft.world_radius, metric=soft.metric, curve=soft.curve,
        curve_power=soft.curve_power, flow_ratio=soft.flow_ratio,
    )
    assert _op(app).weights == field.weights
    _move(app, MORE)
    weights = _op(app).weights
    for vid, w in weights.items():
        c = corr[vid]
        if c.state is CorrespondenceState.PAIRED:
            assert weights.get(c.partner) == w
            p, q = mesh.vertex_position(vid), mesh.vertex_position(c.partner)
            assert p[0] == pytest.approx(-q[0], abs=1e-9) and p[1:] == pytest.approx(q[1:], abs=1e-9)
        elif c.state is CorrespondenceState.SEAM:
            assert mesh.vertex_position(vid)[0] == pytest.approx(0.0, abs=1e-9)
    assert app.key_release(KEYS[op_name])
    assert app.key_press(CTRL_Z) and _positions(app) == start
