"""Soft Selection: the radius changes live during a running Move/Rotate/Scale (AD-020 "Live radius",
`PROVISIONAL`; `docs/future_ideas/TRANSFORM.md`).

Headless (TraceStore); the influence sinks are the real `GLSoftBandOverlay` / `GLSoftShadingOverlay` (data side
only). Pins:

- during a begun Soft gesture the plain wheel and Shift+wheel step the radius of that gesture and never zoom;
  Ctrl+wheel keeps its custom-curve meaning (next gesture); outside a begun Soft gesture the plain wheel zooms
  and Shift+wheel is the sticky step, as before;
- the new weights are the production influence of the seeds on the gesture-start geometry at the new radius
  (same functions, same metric/curve, symmetric field under a definition), and the deformation is the
  gesture's accumulated intent applied with them - equal to a gesture begun at that radius;
- radius steps never accumulate: up/down/up without motion gives the same bits; the drag continues;
- pivot, axis and the percent reference stay those of the gesture; the steps clamp at both ends;
- one History entry, exact Undo/Redo/Cancel; selection and hover untouched; the display shows the op's
  current weights in either mode, nothing while hidden, and the normal preview again after the gesture.
"""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401  (puts examples/ on sys.path)
from tests.test_application_gizmo import _drag as _gizmo_drag
from tests.test_application_gizmo import _grid, _mouse, _on_handle

from core import Mesh
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.soft_selection import (
    RADIUS_STEPS_PERCENT,
    GLSoftBandOverlay,
    GLSoftShadingOverlay,
    SoftBands,
    compute_influence,
    symmetric_influence,
)
from mirai.symmetry import CorrespondenceState, vertex_correspondence
from mirai.symmetry_axis import set_symmetry_axis

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _wheel(direction: str, *modifiers: str) -> Input:
    return Input("wheel", direction, frozenset(modifiers))


W, E, R = _key("w"), _key("e"), _key("r")
O, ALT_O, ALT_SHIFT_O = _key("o"), _key("o", "alt"), _key("o", "alt", "shift")
ESC, CTRL_Z, CTRL_Y = _key("ESCAPE"), _key("z", "ctrl"), _key("y", "ctrl")
UP, DOWN = _wheel("UP"), _wheel("DOWN")
SHIFT_UP, SHIFT_DOWN = _wheel("UP", "shift"), _wheel("DOWN", "shift")
CTRL_UP = _wheel("UP", "ctrl")

KEYS = {"move": W, "rotate": E, "scale": R}
MOTIONS = ((6.0, 2.0), (5.0, 3.0), (4.0, -1.0))
MORE = ((7.0, -3.0), (2.0, 5.0))


def _make_app(cursor: bool = False) -> Application:
    app = Application()
    app.init_scene(
        "obj", obj_path=HEAD_OBJ,
        soft_overlay_type=GLSoftBandOverlay, soft_shading_overlay_type=GLSoftShadingOverlay,
    )
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    if cursor:
        app.pointer_motion(300.0, 300.0)  # a cursor: Rotate runs as the dial
    return app


def _seed(app):
    eye = app.camera.eye()
    mesh = app.scene.mesh
    return min(mesh.all_vertex_ids(), key=lambda v: math.dist(mesh.vertex_position(v), eye))


def _ready(cursor: bool = False, radius_steps: int = 0) -> tuple[Application, set]:
    """Soft on, the vertex nearest the camera selected, the radius `radius_steps` up from 15 %."""
    app = _make_app(cursor)
    seeds = {_seed(app)}
    app.selection.set(seeds)
    app.viewport.on_selection_changed()
    assert app.key_press(O)
    for _ in range(radius_steps):
        assert app.pointer_scroll(SHIFT_UP)
    return app, seeds


def _positions(app) -> dict:
    mesh = app.scene.mesh
    return {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}


def _move(app, motions) -> None:
    for dx, dy in motions:
        assert app.pointer_motion(300.0, 300.0, dx, dy)


def _op(app):
    return app.tool_manager.active_tool.operation


def _start_mesh(start_positions, app) -> Mesh:
    mesh = Mesh.from_state(app.scene.mesh.export_state())
    for vid, pos in start_positions.items():
        mesh.set_vertex_position(vid, pos)
    return mesh


def _close(a: dict, b: dict, tol: float = 1e-9) -> bool:
    return a.keys() == b.keys() and all(math.dist(a[v], b[v]) <= tol for v in a)


# -- the wheel during a running Soft gesture ---------------------------------------------------------


@pytest.mark.parametrize("op_name", sorted(KEYS))
@pytest.mark.parametrize("wheel", [UP, SHIFT_UP], ids=["wheel", "shift_wheel"])
def test_wheel_steps_the_running_gestures_radius_on_the_start_geometry(op_name, wheel):
    app, seeds = _ready()
    start = _positions(app)
    eye = app.camera.eye()
    assert app.key_press(KEYS[op_name])
    _move(app, MOTIONS)
    first_op = _op(app)

    assert app.pointer_scroll(wheel)
    soft = app.soft_settings
    assert soft.radius_percent == 20
    assert app.camera.eye() == eye  # consumed: no zoom
    assert "20 %" in app.status_message
    assert _op(app) is not first_op
    # The production influence of the seeds on the gesture-start geometry, at the new radius.
    expected = compute_influence(
        _start_mesh(start, app), seeds, soft.world_radius, soft.metric, soft.curve, soft.curve_power
    )
    assert _op(app).weights == expected
    assert app.key_release(KEYS[op_name])


@pytest.mark.parametrize("op_name", sorted(KEYS))
@pytest.mark.parametrize("cursor", [False, True], ids=["drag_x", "dial"])
def test_result_equals_a_gesture_begun_at_that_radius_and_the_drag_continues(op_name, cursor):
    live, _ = _ready(cursor)
    assert live.key_press(KEYS[op_name])
    _move(live, MOTIONS)
    assert live.pointer_scroll(UP)
    after_wheel = _positions(live)

    fresh, _ = _ready(cursor, radius_steps=1)  # 20 % before the gesture
    assert fresh.key_press(KEYS[op_name])
    _move(fresh, MOTIONS)
    assert _close(after_wheel, _positions(fresh))
    # The live radius comes from the gesture's fixed percent reference: equal up to rounding.
    live_w, fresh_w = _op(live).weights, _op(fresh).weights
    assert live_w.keys() == fresh_w.keys()
    assert all(live_w[v] == pytest.approx(fresh_w[v], rel=1e-12, abs=1e-15) for v in live_w)

    _move(live, MORE)  # the same drag goes on from where the pointer is
    _move(fresh, MORE)
    assert _close(_positions(live), _positions(fresh))
    assert live.key_release(KEYS[op_name]) and fresh.key_release(KEYS[op_name])
    assert _close(_positions(live), _positions(fresh))


@pytest.mark.parametrize("op_name", sorted(KEYS))
def test_up_and_down_without_motion_never_drift(op_name):
    app, _ = _ready()
    assert app.key_press(KEYS[op_name])
    _move(app, MOTIONS)
    before = _positions(app)
    assert app.pointer_scroll(UP)
    up_once = _positions(app)
    assert app.pointer_scroll(DOWN)
    back = _positions(app)
    assert _close(back, before)  # the start radius again (replayed as one step: equal up to rounding)
    for _ in range(5):
        assert app.pointer_scroll(UP)
        assert _positions(app) == up_once  # bit for bit: each step starts from the start geometry
        assert app.pointer_scroll(DOWN)
        assert _positions(app) == back
    assert app.key_press(ESC)


def test_pivot_axis_and_accumulated_intent_are_kept():
    app, _ = _ready(cursor=True)
    assert app.key_press(E)
    _move(app, MOTIONS)
    tool = app.tool_manager.active_tool
    pivot, axis, angle = _op(app).pivot, tool.axis, tool._applied_angle
    assert app.pointer_scroll(UP)
    assert _op(app).pivot == pivot and tool.axis == axis and tool._applied_angle == angle
    assert app.key_press(ESC)

    assert app.key_press(R)
    _move(app, MOTIONS)
    tool = app.tool_manager.active_tool
    pivot, scale = _op(app).pivot, tool._applied_scale
    assert app.pointer_scroll(UP)
    assert _op(app).pivot == pivot and tool._applied_scale == scale
    assert app.key_press(ESC)


def test_percent_reference_is_fixed_for_the_gesture():
    """A step mid-gesture is a percent of the bounding radius the gesture's start radius came from,
    not of the deformed mesh: back at the start step, the start world radius."""
    app, _ = _ready()
    start_radius = app.soft_settings.world_radius
    assert app.key_press(R)
    _move(app, ((400.0, 300.0),))  # a big scale changes the bounding sphere
    assert app.pointer_scroll(UP)
    assert app.soft_settings.world_radius == pytest.approx(start_radius * 20 / 15, rel=1e-12)
    assert app.pointer_scroll(DOWN)
    assert app.soft_settings.world_radius == pytest.approx(start_radius, rel=1e-12)
    assert app.key_press(ESC)


def test_steps_clamp_at_both_ends_without_wrapping():
    app, _ = _ready()
    assert app.key_press(W)
    _move(app, MOTIONS)
    while app.soft_settings.radius_step < len(RADIUS_STEPS_PERCENT) - 1:
        assert app.pointer_scroll(UP)
    op = _op(app)
    assert app.pointer_scroll(UP) is False  # clamped: nothing recomputed, no zoom, status posted
    assert _op(app) is op
    assert app.soft_settings.radius_percent == RADIUS_STEPS_PERCENT[-1]
    assert f"{RADIUS_STEPS_PERCENT[-1]} %" in app.status_message
    while app.soft_settings.radius_step > 0:
        assert app.pointer_scroll(DOWN)
    op = _op(app)
    assert app.pointer_scroll(DOWN) is False
    assert _op(app) is op and app.soft_settings.radius_percent == RADIUS_STEPS_PERCENT[0]
    assert app.key_press(ESC)


# -- History, cancel, selection, hover -----------------------------------------------------------------


@pytest.mark.parametrize("op_name", sorted(KEYS))
def test_one_history_entry_and_exact_undo_redo(op_name):
    app, seeds = _ready()
    start = _positions(app)
    assert not app.history.can_undo()
    assert app.key_press(KEYS[op_name])
    _move(app, MOTIONS)
    for wheel in (UP, UP, DOWN, UP):
        assert app.pointer_scroll(wheel)
    _move(app, MORE)
    assert app.key_release(KEYS[op_name])
    end = _positions(app)
    assert end != start
    assert app.selection.vertices == seeds
    assert app.key_press(CTRL_Z)
    assert _positions(app) == start  # exact
    assert not app.history.can_undo()  # the radius steps added no entry of their own
    assert app.key_press(CTRL_Y)
    assert _positions(app) == end


@pytest.mark.parametrize("op_name", sorted(KEYS))
def test_cancel_restores_the_start_geometry_without_history(op_name):
    app, seeds = _ready()
    start = _positions(app)
    assert app.key_press(KEYS[op_name])
    _move(app, MOTIONS)
    assert app.pointer_scroll(UP)
    _move(app, MORE)
    assert app.pointer_scroll(UP)
    assert app.key_press(ESC)
    assert _positions(app) == start
    assert not app.history.can_undo()
    assert app.selection.vertices == seeds


def test_selection_and_hover_do_not_change():
    app, seeds = _ready()
    assert app.key_press(W)
    _move(app, MOTIONS)
    hovered = app.selection.hovered
    selected = set(app.selection.vertices)
    assert app.pointer_scroll(UP) and app.pointer_scroll(UP)
    assert app.selection.hovered == hovered and app.selection.vertices == selected == seeds
    assert app.key_release(W)


def test_viewport_is_told_about_the_old_and_the_new_influenced_set(monkeypatch):
    app, _ = _ready()
    assert app.key_press(W)
    _move(app, MOTIONS)
    old = set(_op(app).weights)
    reports: list[set] = []
    original = app.viewport.on_vertices_moved
    monkeypatch.setattr(app.viewport, "on_vertices_moved", lambda ids: (reports.append(set(ids)), original(ids)))
    assert app.pointer_scroll(DOWN)  # smaller: vertices drop out and return to their start
    assert reports == [old | set(_op(app).weights)] and set(_op(app).weights) < old
    assert app.key_press(ESC)


# -- the display ---------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["bands", "faces"])
def test_display_shows_the_ops_current_weights_then_the_normal_preview(mode):
    app, seeds = _ready()
    if mode == "faces":
        assert app.key_press(ALT_SHIFT_O)
    assert app.key_press(W)
    _move(app, MOTIONS)
    assert app.pointer_scroll(UP)
    weights = _op(app).weights
    if mode == "bands":
        assert app.soft_bands == SoftBands.from_weights(weights) and app.soft_shading == {}
    else:
        assert app.soft_shading == weights and not app.soft_bands.weights
    assert app.key_release(W)
    soft = app.soft_settings
    fresh = compute_influence(app.scene.mesh, seeds, soft.world_radius, soft.metric, soft.curve, soft.curve_power)
    if mode == "bands":
        assert app.soft_bands == SoftBands.from_weights(fresh)
    else:
        assert app.soft_shading == fresh


def test_hidden_display_stays_hidden_while_the_radius_changes():
    app, _ = _ready()
    assert app.key_press(ALT_O)
    assert app.key_press(W)
    _move(app, MOTIONS)
    before = set(_op(app).weights)
    assert app.pointer_scroll(UP)
    assert set(_op(app).weights) > before  # the deformation took the new radius ...
    assert not app.soft_bands.weights and app.soft_shading == {}  # ... nothing is shown
    assert app.key_release(W)
    assert not app.soft_bands.weights and app.soft_shading == {}


def test_display_mode_switched_mid_gesture_still_waits_for_the_gesture_end():
    app, _ = _ready()
    assert app.key_press(W)
    _move(app, MOTIONS)
    assert app.key_press(ALT_SHIFT_O)  # faces from the next gesture on
    assert app.pointer_scroll(UP)
    assert app.soft_bands == SoftBands.from_weights(_op(app).weights) and app.soft_shading == {}
    assert app.key_release(W)
    assert app.soft_shading and not app.soft_bands.weights


# -- outside a begun Soft gesture the wheel keeps its meaning ----------------------------------------


def test_plain_wheel_zooms_when_no_soft_gesture_has_begun():
    app, _ = _ready()
    eye = app.camera.eye()
    assert app.pointer_scroll(UP)  # Soft on, selection, no gesture
    assert app.camera.eye() != eye and app.soft_settings.radius_percent == 15
    assert app.key_press(W)  # armed, not begun
    eye = app.camera.eye()
    assert app.pointer_scroll(UP)
    assert app.camera.eye() != eye and app.soft_settings.radius_percent == 15
    assert app.key_press(ESC)


def test_plain_wheel_zooms_during_a_plain_transform():
    app = _make_app()
    app.selection.set({_seed(app)})
    app.viewport.on_selection_changed()
    assert app.key_press(W)
    _move(app, MOTIONS)
    eye = app.camera.eye()
    assert app.pointer_scroll(UP)
    assert app.camera.eye() != eye and app.soft_settings.radius_percent == 15
    assert app.key_press(ESC)


def test_shift_wheel_outside_a_gesture_is_the_sticky_step_and_moves_nothing():
    app, _ = _ready()
    start, eye = _positions(app), app.camera.eye()
    assert app.pointer_scroll(SHIFT_UP)
    assert app.soft_settings.radius_percent == 20 and app.camera.eye() == eye
    assert _positions(app) == start and not app.history.can_undo()
    assert app.key_press(W)
    _move(app, MOTIONS)
    assert app.soft_settings.radius_percent == 20  # the next gesture begins with it
    assert app.key_press(ESC)


def test_ctrl_wheel_mid_gesture_keeps_its_custom_curve_meaning():
    app, _ = _ready()
    assert app.key_press(W)
    _move(app, MOTIONS)
    op, eye, weights = _op(app), app.camera.eye(), _op(app).weights
    assert app.pointer_scroll(CTRL_UP)
    assert app.soft_settings.curve == "custom"  # the sticky shape, for the next gesture
    assert _op(app) is op and _op(app).weights == weights and app.camera.eye() == eye
    assert app.key_press(ESC)


def test_radius_step_keeps_the_gestures_curve_not_a_mid_gesture_curve_change():
    app, seeds = _ready()
    start = _positions(app)
    assert app.key_press(W)
    _move(app, MOTIONS)
    curve = app.soft_settings.curve
    assert app.pointer_scroll(CTRL_UP)  # sticky curve -> custom, for the next gesture
    assert app.pointer_scroll(UP)
    soft = app.soft_settings
    assert _op(app).weights == compute_influence(
        _start_mesh(start, app), seeds, soft.world_radius, soft.metric, curve, soft.curve_power
    )
    assert app.key_press(ESC)


# -- the gizmo drives the same Soft operation ---------------------------------------------------------


def test_gizmo_handle_drag_takes_the_live_radius():
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_grid(8, 4.0).export_state())
    app.frame_scene()
    app.camera.yaw = 0.0
    app.camera.pitch = 0.0
    app.camera.camera_revision += 1
    app.set_viewport_size(WIDTH, HEIGHT)
    app.gizmo_enabled = True
    mesh = app.scene.mesh
    assert app.key_press(_key("1"))
    (vid,) = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (0.0, 0.0)]
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    assert app.key_press(O)
    start = _positions(app)
    pivot = mesh.vertex_position(vid)
    press = _on_handle(app, pivot, (0.0, 1.0, 0.0))
    _gizmo_drag(app, _mouse("LEFT"), press, (0.0, 60.0), release=False)
    small = set(_op(app).weights)
    eye = app.camera.eye()
    assert app.pointer_scroll(UP) and app.pointer_scroll(UP)
    assert app.camera.eye() == eye and set(_op(app).weights) > small
    assert all(mesh.vertex_position(v)[0] == pytest.approx(start[v][0]) for v in start)  # still the Y axis
    app.pointer_release("LEFT", press[0], press[1] + 60.0)
    assert app.history.can_undo()
    app.history.undo()
    assert _positions(app) == start
    assert not app.history.can_undo()


# -- symmetry ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("op_name", sorted(KEYS))
def test_symmetric_field_and_mirror_stay_consistent(op_name):
    app = _make_app(cursor=True)
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    app.viewport.on_topology_changed()
    corr = vertex_correspondence(mesh)
    seed = min(
        (v for v, c in corr.items() if c.state is CorrespondenceState.PAIRED and mesh.vertex_position(v)[0] > 0),
        key=lambda v: mesh.vertex_position(v)[0],
    )  # nearest the plane: the falloff crosses it
    app.selection.set({seed})
    app.viewport.on_selection_changed()
    assert app.key_press(O)
    start = _positions(app)
    assert app.key_press(KEYS[op_name])
    _move(app, MOTIONS)
    assert app.pointer_scroll(UP)
    soft = app.soft_settings
    field = symmetric_influence(
        _start_mesh(start, app), {seed}, soft.world_radius, metric=soft.metric, curve=soft.curve,
        curve_power=soft.curve_power,
    )
    assert _op(app).weights == field.weights
    symmetry = _op(app).context.params["symmetry"]
    assert symmetry["mirrored_vertex_ids"] and symmetry["falloff_seam_vertex_ids"]  # the field crosses the plane
    _move(app, MORE)
    weights = _op(app).weights
    for vid, w in weights.items():
        c = corr[vid]
        if c.state is CorrespondenceState.PAIRED:
            assert weights.get(c.partner) == w
            p, q = mesh.vertex_position(vid), mesh.vertex_position(c.partner)
            assert p[0] == pytest.approx(-q[0], abs=1e-9)
            assert p[1:] == pytest.approx(q[1:], abs=1e-9)
        elif c.state is CorrespondenceState.SEAM:
            assert mesh.vertex_position(vid)[0] == pytest.approx(0.0, abs=1e-9)
    assert app.key_release(KEYS[op_name])
    assert app.key_press(CTRL_Z) and _positions(app) == start


# -- trackball: the composed rotation is replayed as one step ----------------------------------------


def test_trackball_reweight_keeps_the_seed_rotation_and_never_drifts():
    from mirai.interaction.tools.rotate import RotateTool

    app, (seed,) = _ready()
    mesh = app.scene.mesh
    seeds = {seed} | {w for e in mesh.vertex_edges(seed) for w in mesh.edge_vertices(e)}  # off the pivot
    soft = app.soft_settings
    tool = RotateTool()
    tool.activate()
    tool.begin(
        scene=app.scene, camera=app.camera, vertex_ids=set(seeds), soft=soft,
        gizmo={"mode": "trackball", "press": (300.0, 300.0), "size": (WIDTH, HEIGHT)},
    )
    for dx, dy in ((20.0, 5.0), (-4.0, 30.0), (12.0, -9.0)):
        tool.update(dx=dx, dy=dy, width=WIDTH, height=HEIGHT)
    seeds_before = {v: mesh.vertex_position(v) for v in seeds}
    bigger = soft.with_radius_step(soft.radius_step + 1, soft.world_radius * 100.0 / soft.radius_percent)
    tool.reweight(bigger)
    for v, p in seeds_before.items():  # w = 1: the same composed rotation
        assert mesh.vertex_position(v) == pytest.approx(p, abs=1e-9)
    assert len(seeds) > 2
    once = _positions(app)
    tool.reweight(soft)
    tool.reweight(bigger)
    assert _positions(app) == once
    tool.cancel()
