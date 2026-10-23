"""Application: Soft Selection on the app path (WP-SOFT-01 S2a, AD-020; PROVISIONAL).

Headless (TraceStore), kein pyglet/Fenster. Pfad wie bei W/E/R (`test_application_transform.py`):
Taste → `Application.key_press` (scharf) → `pointer_motion` (erste Bewegung: `begin()`, dann
`update`) → Release → `commit`. Neu: O schaltet Soft ein, die sticky `SoftSettings` werden bei
`begin()` gelesen und als `soft=` in den Begin-Payload gelegt - nur wenn Soft an ist.

- Soft aus ≡ heute (Begin-Payload, Operationsklassen, Ergebnis bitgleich);
- Soft an: W/E/R = weiche Operation, genau ein History-Eintrag, exakter Cancel, Undo/Redo;
- die beeinflusste Menge geht an `on_vertices_moved`; der Move-Anchor ist ein Seed;
- Settings sticky über Commit/Cancel/Undo; ein scharfer, noch nicht begonnener Transform nimmt
  den neuen Wert; ein laufender behält seinen; der Weltradius hat eine Quelle.
"""

from __future__ import annotations

import dataclasses

import pytest

import tests._bootstrap  # noqa: F401
from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401  (puts examples/ on sys.path)

from core import SelectionMode, VertexId
from core.operations.move import MoveOperation
from core.operations.transform import RotateOperation, ScaleOperation
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.soft_selection import (
    CURVES,
    CUSTOM_SHAPE_STEPS,
    DEFAULT_RADIUS_STEP,
    RADIUS_STEPS_PERCENT,
    SoftMoveOperation,
    SoftRotateOperation,
    SoftScaleOperation,
    compute_influence,
    primary_pivot,
)

WIDTH, HEIGHT = 800, 600
#: One wheel notch up / down from the default 15 % (the step list is finer since 2026-10-22).
ONE_UP = RADIUS_STEPS_PERCENT[DEFAULT_RADIUS_STEP + 1]
ONE_DOWN = RADIUS_STEPS_PERCENT[DEFAULT_RADIUS_STEP - 1]


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _wheel(direction: str, *modifiers: str) -> Input:
    return Input("wheel", direction, frozenset(modifiers))


W, E, R = _key("w"), _key("e"), _key("r")
O, SHIFT_O, CTRL_O = _key("o"), _key("o", "shift"), _key("o", "ctrl")
ESC, CTRL_Z, CTRL_Y = _key("ESCAPE"), _key("z", "ctrl"), _key("y", "ctrl")
SHIFT_WHEEL_UP, SHIFT_WHEEL_DOWN = _wheel("UP", "shift"), _wheel("DOWN", "shift")
CTRL_WHEEL_UP, CTRL_WHEEL_DOWN = _wheel("UP", "ctrl"), _wheel("DOWN", "ctrl")
ALT_O = _key("o", "alt")

TRANSFORMS = [
    (W, cmd.MOVE, MoveOperation, SoftMoveOperation),
    (E, cmd.ROTATE, RotateOperation, SoftRotateOperation),
    (R, cmd.SCALE, ScaleOperation, SoftScaleOperation),
]
TRANSFORM_IDS = ["move", "rotate", "scale"]


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("obj", obj_path=HEAD_OBJ)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _positions(app) -> dict:
    mesh = app.scene.mesh
    return {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}


def _select_one(app) -> VertexId:
    vid = app.scene.mesh.all_vertex_ids()[100]
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    return vid


def _gesture(app, key: Input, motions=((6, 2), (5, 3), (4, -1)), release: bool = True):
    """Press `key`, move, optionally release (commit)."""
    assert app.key_press(key)
    for dx, dy in motions:
        app.pointer_motion(300.0, 300.0, float(dx), float(dy))
    if release:
        assert app.key_release(key)


def _soft_on(app) -> None:
    assert app.key_press(O)
    assert app.soft_settings.enabled


@pytest.fixture
def begins(app, monkeypatch) -> list[dict]:
    calls: list[dict] = []
    original = app.tool_manager.begin_current_interaction

    def spy(context=None):
        calls.append(context)
        original(context)

    monkeypatch.setattr(app.tool_manager, "begin_current_interaction", spy)
    return calls


@pytest.fixture
def moved_reports(app, monkeypatch) -> list[set]:
    reports: list[set] = []
    original = app.viewport.on_vertices_moved

    def spy(ids):
        reports.append(set(ids))
        original(ids)

    monkeypatch.setattr(app.viewport, "on_vertices_moved", spy)
    return reports


# -- Soft aus ≡ heute ---------------------------------------------------------------


def test_soft_is_off_by_default(app):
    assert app.soft_settings.enabled is False
    assert app.soft_settings.radius_percent == 15
    assert RADIUS_STEPS_PERCENT[DEFAULT_RADIUS_STEP] == 15


@pytest.mark.parametrize("key,command,core_cls,soft_cls", TRANSFORMS, ids=TRANSFORM_IDS)
def test_soft_off_payload_and_operation_are_todays(app, begins, key, command, core_cls, soft_cls):
    _select_one(app)
    _gesture(app, key, release=False)
    assert len(begins) == 1
    # No "soft" key at all: the payload is exactly what it was before Soft Selection.
    assert set(begins[0]) == {"scene", "camera", "vertex_ids", "space"}
    assert type(app.tool_manager.active_tool.operation) is core_cls
    app.key_release(key)


@pytest.mark.parametrize("key,command,core_cls,soft_cls", TRANSFORMS, ids=TRANSFORM_IDS)
def test_switching_soft_on_and_off_again_changes_nothing(key, command, core_cls, soft_cls):
    """Soft off after a round trip ≡ never touched: the same bits."""
    results = []
    for toggled in (False, True):
        app = Application()
        app.init_scene("obj", obj_path=HEAD_OBJ)
        app.frame_scene()
        app.set_viewport_size(WIDTH, HEIGHT)
        if toggled:
            app.key_press(O)
            app.key_press(O)
        assert app.soft_settings.enabled is False
        _select_one(app)
        _gesture(app, key)
        results.append(_positions(app))
    assert results[0] == results[1]


# -- Soft an: W/E/R ---------------------------------------------------------------------


@pytest.mark.parametrize("key,command,core_cls,soft_cls", TRANSFORMS, ids=TRANSFORM_IDS)
def test_soft_gesture_is_one_history_entry_with_exact_undo_redo(
    app, begins, moved_reports, key, command, core_cls, soft_cls
):
    seed = _select_one(app)
    _soft_on(app)
    start = _positions(app)
    entries = len(app.history)
    _gesture(app, key, release=False)
    op = app.tool_manager.active_tool.operation
    assert type(op) is soft_cls
    assert begins[0]["soft"] is app.soft_settings
    influenced = set(op.weights)
    assert seed in influenced and len(influenced) > 1
    assert op.weights[seed] == 1.0 and any(w < 1.0 for w in op.weights.values())
    app.key_release(key)

    end = _positions(app)
    assert len(app.history) == entries + 1
    moved = {v for v in start if end[v] != start[v]}
    assert moved and moved <= influenced
    assert any(v != seed for v in moved)  # the surroundings moved with the seed
    assert app.status_message.startswith({"Move": "Move", "Rotate": "Rotate", "Scale": "Scale"}[command] + " committed")

    assert app.key_press(CTRL_Z)
    assert _positions(app) == start
    assert app.key_press(CTRL_Y)
    assert _positions(app) == end
    assert len(app.history) == entries + 1


@pytest.mark.parametrize("key,command,core_cls,soft_cls", TRANSFORMS, ids=TRANSFORM_IDS)
def test_soft_cancel_is_exact_and_leaves_no_history(app, key, command, core_cls, soft_cls):
    _select_one(app)
    _soft_on(app)
    start = _positions(app)
    entries = len(app.history)
    _gesture(app, key, release=False)
    assert _positions(app) != start
    assert app.key_press(ESC)
    assert _positions(app) == start
    assert len(app.history) == entries
    assert app.interaction_owner is None


@pytest.mark.parametrize("key,command,core_cls,soft_cls", TRANSFORMS, ids=TRANSFORM_IDS)
def test_influenced_set_reaches_on_vertices_moved(app, moved_reports, key, command, core_cls, soft_cls):
    seed = _select_one(app)
    _soft_on(app)
    _gesture(app, key, release=False)
    influenced = set(app.tool_manager.active_tool.operation.weights)
    assert len(influenced) > 1
    assert moved_reports and all(report == influenced for report in moved_reports)
    moved_reports.clear()
    app.key_press(ESC)  # cancel notifies the same set
    assert moved_reports == [influenced]


def test_selection_is_not_touched_by_the_influence(app):
    seed = _select_one(app)
    _soft_on(app)
    snapshot = (app.selection.mode, set(app.selection.vertices), set(app.selection.edges), set(app.selection.faces))
    _gesture(app, W)
    assert (app.selection.mode, app.selection.vertices, app.selection.edges, app.selection.faces) == snapshot
    assert app.selection.vertices == {seed}
    assert app.transform_target == frozenset()  # disarmed after the commit


def test_move_anchor_is_a_seed_and_the_first_step_matches_the_plain_move(app):
    seed = _select_one(app)
    _soft_on(app)
    start = _positions(app)
    _gesture(app, W, motions=((6, 2),), release=False)
    tool = app.tool_manager.active_tool
    assert tool._anchor_vertex == seed  # a seed, not an influenced vertex
    soft_move = {v: tuple(a - b for a, b in zip(app.scene.mesh.vertex_position(v), start[v])) for v in tool.moves}
    app.key_press(ESC)

    plain = Application()
    plain.init_scene("obj", obj_path=HEAD_OBJ)
    plain.frame_scene()
    plain.set_viewport_size(WIDTH, HEIGHT)
    _select_one(plain)
    _gesture(plain, W, motions=((6, 2),))
    # The seed (w = 1) moves exactly like the plain Move: the same screen→world mapping.
    assert plain.scene.mesh.vertex_position(seed) == app_seed_after(start, soft_move, seed)


def app_seed_after(start, delta, seed):
    return tuple(a + b for a, b in zip(start[seed], delta[seed]))


@pytest.mark.parametrize("key,op_cls", [(E, SoftRotateOperation), (R, SoftScaleOperation)])
def test_pivot_is_the_centroid_of_the_seeds(app, key, op_cls):
    mesh = app.scene.mesh
    seeds = set(mesh.all_vertex_ids()[100:103])
    app.selection.set(seeds)
    app.viewport.on_selection_changed()
    _soft_on(app)
    expected = primary_pivot(mesh, seeds)  # before anything moves
    _gesture(app, key, release=False)
    op = app.tool_manager.active_tool.operation
    assert type(op) is op_cls
    assert op.pivot == expected
    assert len(op.weights) > len(seeds)  # the pivot is not the centroid of the influenced set
    app.key_press(ESC)


def test_hover_armed_gesture_is_soft_too(app):
    """No selection: the hovered element is the target (AD-016), and the influence is built from it."""
    mesh = app.scene.mesh
    vid = mesh.all_vertex_ids()[100]
    app.selection.clear()
    app.selection.hovered = vid
    _soft_on(app)
    start = _positions(app)
    _gesture(app, W, release=False)
    op = app.tool_manager.active_tool.operation
    assert type(op) is SoftMoveOperation and op.weights[vid] == 1.0 and len(op.weights) > 1
    app.key_release(W)
    assert _positions(app) != start


@pytest.mark.parametrize("mode", [SelectionMode.EDGE, SelectionMode.FACE])
def test_edge_and_face_modes_use_their_vertices_as_seeds(app, mode):
    mesh = app.scene.mesh
    app.selection.mode = mode
    if mode is SelectionMode.EDGE:
        eid = mesh.all_edge_ids()[40]
        app.selection.set({eid})
        seeds = set(mesh.edge_vertices(eid))
    else:
        fid = mesh.all_face_ids()[40]
        app.selection.set({fid})
        seeds = set(mesh.face_vertices(fid))
    app.viewport.on_selection_changed()
    _soft_on(app)
    _gesture(app, W, release=False)
    weights = app.tool_manager.active_tool.operation.weights
    assert all(weights[s] == 1.0 for s in seeds) and len(weights) > len(seeds)
    assert app.selection.mode is mode
    app.key_press(ESC)


def test_axis_constraint_applies_to_the_soft_gesture(app):
    _select_one(app)
    _soft_on(app)
    app.key_press(_key("x"))
    start = _positions(app)
    _gesture(app, W)
    for vid, p in _positions(app).items():
        assert (p[1], p[2]) == (start[vid][1], start[vid][2])
    assert any(p[0] != start[v][0] for v, p in _positions(app).items())


# -- sticky settings -----------------------------------------------------------------------


def test_settings_are_sticky_across_commit_cancel_and_undo(app):
    _select_one(app)
    _soft_on(app)
    app.key_press(SHIFT_O)
    app.key_press(CTRL_O)
    app.pointer_scroll(SHIFT_WHEEL_UP)
    settings = app.soft_settings
    assert (settings.metric, settings.curve) == ("euclidean", "sphere")
    assert settings.radius_percent == ONE_UP
    _gesture(app, W)  # commit
    assert app.soft_settings == settings
    _gesture(app, E, release=False)
    app.key_press(ESC)  # cancel
    assert app.soft_settings == settings
    app.key_press(CTRL_Z)  # undo
    assert app.soft_settings == settings


def test_armed_but_not_begun_takes_the_new_value(app, begins):
    _select_one(app)
    _soft_on(app)
    app.key_press(W)  # armed, no motion yet
    app.key_press(_key("o", "shift"))  # curve → sphere
    app.pointer_scroll(SHIFT_WHEEL_UP)
    app.pointer_motion(300.0, 300.0, 6.0, 2.0)  # begin() reads the settings now
    assert begins[0]["soft"].curve == "sphere"
    assert begins[0]["soft"].radius_percent == ONE_UP
    app.key_press(ESC)


def test_soft_switched_off_while_armed_gives_a_plain_gesture(app, begins):
    _select_one(app)
    _soft_on(app)
    app.key_press(W)
    app.key_press(O)  # off before the first motion
    app.pointer_motion(300.0, 300.0, 6.0, 2.0)
    assert "soft" not in begins[0]
    assert type(app.tool_manager.active_tool.operation) is MoveOperation
    app.key_press(ESC)


def test_a_running_gesture_keeps_its_own_settings(app, begins):
    _select_one(app)
    _soft_on(app)
    _gesture(app, W, release=False)
    weights = dict(app.tool_manager.active_tool.operation.weights)
    for key in (O, SHIFT_O, CTRL_O):
        app.key_press(key)  # state changes mid-gesture, status line posts ...
    # (the radius is the exception: a running Soft gesture takes it live, test_soft_live_radius.py)
    app.pointer_motion(300.0, 300.0, 3.0, 3.0)  # ... the gesture goes on unchanged
    assert type(app.tool_manager.active_tool.operation) is SoftMoveOperation
    assert dict(app.tool_manager.active_tool.operation.weights) == weights
    assert len(begins) == 1
    app.key_release(W)
    assert not app.soft_settings.enabled  # the key presses took effect for the next gesture
    # next gesture: plain
    _gesture(app, W, release=False)
    assert type(app.tool_manager.active_tool.operation) is MoveOperation
    app.key_press(ESC)


# -- world radius: one source -------------------------------------------------------------


def test_world_radius_is_the_step_times_the_bounding_radius(app):
    _, bounding = mesh_center_and_radius(app.scene.mesh)
    s = app.soft_settings
    assert s.world_radius == pytest.approx(bounding * 0.15)
    app.pointer_scroll(SHIFT_WHEEL_UP)
    assert app.soft_settings.world_radius == pytest.approx(bounding * ONE_UP / 100)


def test_tool_influence_is_computed_from_the_settings_world_radius(app):
    seed = _select_one(app)
    _soft_on(app)
    app.key_press(CTRL_O)
    app.key_press(SHIFT_O)
    settings = app.soft_settings
    expected = compute_influence(
        app.scene.mesh, {seed}, settings.world_radius, metric=settings.metric, curve=settings.curve
    )
    _gesture(app, W, release=False)
    # The same single value, to the last bit - the preview of S2b reads it too.
    assert app.tool_manager.active_tool.operation.weights == expected
    app.key_press(ESC)


def test_world_radius_is_recomputed_on_switch_on_and_on_scene_load():
    app = Application()
    app.init_scene("cube")
    cube_radius = app.soft_settings.world_radius
    assert cube_radius == pytest.approx(mesh_center_and_radius(app.scene.mesh)[1] * 0.15)
    app.init_scene("obj", obj_path=HEAD_OBJ)  # scene load
    head_radius = app.soft_settings.world_radius
    assert head_radius == pytest.approx(mesh_center_and_radius(app.scene.mesh)[1] * 0.15)
    assert head_radius != cube_radius
    # The mesh changes through a gesture (not an event): the stored value stays ...
    _select_one_on(app)
    app.set_viewport_size(WIDTH, HEIGHT)
    app.frame_scene()
    app.key_press(W)
    app.pointer_motion(300.0, 300.0, 40.0, 0.0)
    app.key_release(W)
    assert app.soft_settings.world_radius == head_radius
    # ... until soft is switched on (one of the three events).
    app.key_press(O)
    assert app.soft_settings.world_radius == pytest.approx(mesh_center_and_radius(app.scene.mesh)[1] * 0.15)


def _select_one_on(app) -> None:
    app.selection.set({app.scene.mesh.all_vertex_ids()[100]})


# -- keys, wheel, status line -----------------------------------------------------------


def test_o_toggles_and_posts_the_full_state(app):
    serial = app.status_serial
    assert app.key_press(O)
    assert app.status_serial == serial + 1
    assert app.status_message.startswith("Soft: on · 15 % (")
    assert app.status_message.endswith(") · geodesic · smooth · flow 1:1 · bands on · mono")
    assert app.key_press(O)
    assert app.status_message.startswith("Soft: off · 15 % (")


def test_curve_and_metric_cycle_and_post_the_state(app):
    assert app.key_press(SHIFT_O)
    assert app.soft_settings.curve == "sphere"
    assert app.status_message.endswith("· geodesic · sphere · flow 1:1 · bands on · mono")
    for _ in range(len(CURVES) - 1):  # the whole cycle comes back to smooth
        assert app.key_press(SHIFT_O)
    assert app.soft_settings.curve == "smooth"
    assert app.key_press(CTRL_O)
    assert app.soft_settings.metric == "euclidean"
    assert app.status_message.endswith("· euclidean · smooth · flow 1:1 · bands on · mono")
    assert app.key_press(CTRL_O)
    assert app.soft_settings.metric == "geodesic"


def test_shift_wheel_steps_the_radius_clamped_without_wrap(app):
    percents = []
    for _ in range(len(RADIUS_STEPS_PERCENT) + 3):  # more notches than steps
        app.pointer_scroll(SHIFT_WHEEL_UP)
        percents.append(app.soft_settings.radius_percent)
    assert percents[-1] == RADIUS_STEPS_PERCENT[-1] == 200  # clamped at the top ...
    assert percents[-4:] == [200, 200, 200, 200]  # ... and does not wrap around
    assert app.pointer_scroll(SHIFT_WHEEL_UP) is False  # at the end nothing changes
    assert app.status_message.startswith("Soft: off · 200 % (")  # but the state is still posted
    for _ in range(len(RADIUS_STEPS_PERCENT) + 3):
        app.pointer_scroll(SHIFT_WHEEL_DOWN)
    assert app.soft_settings.radius_percent == RADIUS_STEPS_PERCENT[0] == 2
    assert app.pointer_scroll(SHIFT_WHEEL_DOWN) is False


def test_one_notch_is_one_step_and_up_is_larger(app):
    assert app.soft_settings.radius_percent == 15
    app.pointer_scroll(SHIFT_WHEEL_UP)
    assert app.soft_settings.radius_percent == ONE_UP
    app.pointer_scroll(SHIFT_WHEEL_DOWN)
    app.pointer_scroll(SHIFT_WHEEL_DOWN)
    assert app.soft_settings.radius_percent == ONE_DOWN


def test_shift_wheel_never_zooms_even_with_soft_off(app):
    before = app.camera.distance
    assert not app.soft_settings.enabled
    app.pointer_scroll(SHIFT_WHEEL_UP)
    app.pointer_scroll(SHIFT_WHEEL_DOWN)
    assert app.camera.distance == before
    assert app.soft_settings.radius_percent == 15  # up + down: only the stored step moved and returned


def test_plain_wheel_still_zooms_and_changes_no_soft_state(app):
    settings = app.soft_settings
    before = app.camera.distance
    assert app.pointer_scroll(_wheel("UP"))
    assert app.camera.distance < before
    assert app.pointer_scroll(_wheel("DOWN"))
    assert app.soft_settings == settings


def test_soft_keys_are_inert_inside_a_knife_session(app):
    app.selection.clear()
    app.key_press(_key("c"))  # empty selection: begins a Knife session
    assert app.interaction_owner == "knife"
    settings = app.soft_settings
    for key in (O, SHIFT_O, CTRL_O):
        assert app.key_press(key) is False
    assert app.pointer_scroll(SHIFT_WHEEL_UP) is False
    assert app.soft_settings == settings


def test_soft_keys_are_allowed_while_a_transform_key_is_held(app):
    _select_one(app)
    assert app.key_press(W)
    assert app.key_press(O)
    assert app.interaction_owner == "transform"
    assert app.soft_settings.enabled
    app.key_press(ESC)


def test_soft_commands_never_touch_mesh_selection_or_history(app):
    seed = _select_one(app)
    start, entries = _positions(app), len(app.history)
    for key in (O, SHIFT_O, CTRL_O, O):
        app.key_press(key)
    app.pointer_scroll(SHIFT_WHEEL_UP)
    assert _positions(app) == start and len(app.history) == entries
    assert app.selection.vertices == {seed}


def test_direct_dispatch_reaches_the_same_state(app):
    assert app.dispatch_command(cmd.SOFT_TOGGLE)
    assert app.soft_settings.enabled
    assert app.dispatch_command(cmd.SOFT_RADIUS_UP)
    assert app.soft_settings.radius_percent == ONE_UP


# -- S2d: defaults, curve set, custom shape, radius steps, band switch (S2c verdict 2026-10-11) -----


def test_new_defaults_are_geodesic_smooth_and_bands_on(app):
    soft = app.soft_settings
    assert (soft.metric, soft.curve, soft.bands_visible) == ("geodesic", "smooth", True)
    assert soft.radius_percent == 15 and not soft.enabled


def test_shift_o_walks_the_curve_set_in_order_and_comes_back(app):
    seen = [app.soft_settings.curve]
    for _ in range(len(CURVES)):
        assert app.key_press(SHIFT_O)
        seen.append(app.soft_settings.curve)
    assert seen == ["smooth", "sphere", "root", "sharp", "linear", "custom", "smooth"]


def test_ctrl_wheel_shapes_the_custom_curve_and_selects_it(app):
    assert app.soft_settings.curve == "smooth" and app.soft_settings.curve_power == 1.0
    assert app.pointer_scroll(CTRL_WHEEL_UP)  # up = rounder = smaller p
    assert app.soft_settings.curve == "custom" and app.soft_settings.curve_power == 0.67
    assert app.status_message.endswith("· custom p=0.67 · flow 1:1 · bands on · mono")
    assert app.pointer_scroll(CTRL_WHEEL_DOWN) and app.pointer_scroll(CTRL_WHEEL_DOWN)
    assert app.soft_settings.curve_power == 1.5  # down = sharper
    assert app.status_message.endswith("· geodesic · custom p=1.5 · flow 1:1 · bands on · mono")


def test_ctrl_wheel_clamps_at_both_ends_and_never_zooms(app):
    distance = app.camera.distance
    for _ in range(len(CUSTOM_SHAPE_STEPS) + 2):
        app.pointer_scroll(CTRL_WHEEL_UP)
    assert app.soft_settings.curve_power == CUSTOM_SHAPE_STEPS[0]
    assert app.pointer_scroll(CTRL_WHEEL_UP) is False  # at the end: unchanged ...
    assert app.status_message.endswith("· custom p=0.25 · flow 1:1 · bands on · mono")  # ... but the state is posted
    for _ in range(len(CUSTOM_SHAPE_STEPS) + 2):
        app.pointer_scroll(CTRL_WHEEL_DOWN)
    assert app.soft_settings.curve_power == CUSTOM_SHAPE_STEPS[-1]
    assert app.camera.distance == distance


def test_ctrl_wheel_at_the_end_still_switches_to_custom(app):
    for _ in range(len(CUSTOM_SHAPE_STEPS) + 2):
        app.pointer_scroll(CTRL_WHEEL_UP)
    app.key_press(SHIFT_O)  # custom -> smooth
    assert app.soft_settings.curve == "smooth"
    assert app.pointer_scroll(CTRL_WHEEL_UP)  # p already at the end, but the curve changes
    assert app.soft_settings.curve == "custom" and app.soft_settings.curve_power == 0.25


def test_ctrl_wheel_with_soft_off_changes_only_the_stored_shape(app):
    before = app.soft_settings
    assert not before.enabled
    distance, selection = app.camera.distance, set(app.selection.vertices)
    assert app.pointer_scroll(CTRL_WHEEL_UP)
    after = app.soft_settings
    assert after.enabled is False and after.curve == "custom" and after.curve_power == 0.67
    assert (after.metric, after.radius_step, after.bands_visible) == (
        before.metric, before.radius_step, before.bands_visible)
    assert app.camera.distance == distance and set(app.selection.vertices) == selection
    app.key_press(O)  # switched on later, the stored shape is used
    assert app.soft_settings.curve == "custom" and app.soft_settings.curve_power == 0.67


def test_ctrl_shift_wheel_is_the_flow_balance_and_never_zooms(app):
    """Unbound until 2026-10-22; now the Loop / Ring balance (AD-020 "Loop / Ring flow", `test_soft_flow_live.py`)."""
    distance, settings = app.camera.distance, app.soft_settings
    assert app.pointer_scroll(_wheel("UP", "ctrl", "shift"))
    assert app.soft_settings == dataclasses.replace(settings, flow_step=settings.flow_step + 1)
    assert app.pointer_scroll(_wheel("DOWN", "ctrl", "shift"))
    assert app.camera.distance == distance and app.soft_settings == settings


def test_custom_keeps_its_last_p_through_the_cycle(app):
    app.pointer_scroll(CTRL_WHEEL_DOWN)
    app.pointer_scroll(CTRL_WHEEL_DOWN)  # p = 2 (steps 1.0 -> 1.5 -> 2.0)
    assert app.soft_settings.curve_power == 2.0
    for _ in range(len(CURVES)):
        app.key_press(SHIFT_O)
    assert app.soft_settings.curve == "custom" and app.soft_settings.curve_power == 2.0


def test_the_gesture_uses_the_custom_curve_and_its_power(app, begins):
    seed = _select_one(app)
    _soft_on(app)
    app.pointer_scroll(CTRL_WHEEL_DOWN)  # p = 1.5
    soft = app.soft_settings
    expected = compute_influence(
        app.scene.mesh, {seed}, soft.world_radius,
        metric=soft.metric, curve="custom", curve_power=1.5,
    )  # at the start positions, before the gesture moves anything
    _gesture(app, W, release=False)
    assert begins[0]["soft"].curve == "custom" and begins[0]["soft"].curve_power == 1.5
    assert app.tool_manager.active_tool.operation.context.params["influence"] == expected
    assert len(expected) > 1
    assert app.key_press(ESC)


def test_radius_steps_reach_200_percent_and_the_world_radius_follows(app):
    _, bounding = mesh_center_and_radius(app.scene.mesh)
    for _ in range(len(RADIUS_STEPS_PERCENT)):
        app.pointer_scroll(SHIFT_WHEEL_UP)
    assert app.soft_settings.radius_percent == 200
    assert app.soft_settings.world_radius == pytest.approx(bounding * 2.0)
    assert app.status_message.startswith("Soft: off · 200 % (")


def test_alt_o_toggles_the_bands_state_and_posts_it(app):
    serial = app.status_serial
    assert app.key_press(ALT_O)
    assert app.soft_settings.bands_visible is False and app.status_serial == serial + 1
    assert app.status_message.endswith("· bands off · mono")
    assert app.soft_settings.enabled is False  # Alt+O is not O
    assert app.key_press(ALT_O)
    assert app.soft_settings.bands_visible is True and app.status_message.endswith("· bands on · mono")


def test_bands_switch_is_sticky_and_allowed_while_armed(app):
    _select_one(app)
    _soft_on(app)
    app.key_press(ALT_O)
    _gesture(app, W)  # commit
    assert app.soft_settings.bands_visible is False
    app.key_press(W)  # armed
    assert app.key_press(ALT_O)
    assert app.soft_settings.bands_visible is True
    app.key_press(ESC)


def test_the_bands_switch_does_not_change_the_gesture_weights(app, begins):
    """Display only: the influence the operation gets is the same with the bands on or off."""
    _select_one(app)
    _soft_on(app)
    _gesture(app, W, release=False)
    with_bands = dict(app.tool_manager.active_tool.operation.context.params["influence"])
    app.key_press(ESC)
    app.key_press(ALT_O)
    _gesture(app, W, release=False)
    assert app.tool_manager.active_tool.operation.context.params["influence"] == with_bands
    app.key_press(ESC)
