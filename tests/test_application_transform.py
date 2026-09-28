"""Application: Rotate/Scale auf E/R + Achsen-Constraints (WP-06 B4/B4.1).

Headless (TraceStore), kein pyglet/Fenster. Gleicher AD-016-Pfad wie Move
(`test_application_move.py`): Taste → `Application.key_press` (scharf, Tool
aktiv) → `pointer_motion(x, y, dx, dy)` (erste Bewegung: `begin(space=...)`,
dann `update`) → Release → `commit`. Constraints (B4.1, Playground-Modell):
sticky Toggle, unabhängig vom scharfen Tool, gelesen bei jedem `begin()`.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import VertexId
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.interaction.tools import MoveTool, RotateTool, ScaleTool
from mirai.viewport.picking import pick_nearest_vertex

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)  # Bildecke: weit weg von jedem Würfel-Vertex


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


W, E, R = _key("w"), _key("e"), _key("r")
ESC = _key("ESCAPE")
CTRL_Z = _key("z", "ctrl")
CTRL_Y = _key("y", "ctrl")

TRANSFORM_KEYS = {cmd.MOVE: W, cmd.ROTATE: E, cmd.SCALE: R}
TOOL_CLASSES = {cmd.MOVE: MoveTool, cmd.ROTATE: RotateTool, cmd.SCALE: ScaleTool}
LABELS = {cmd.MOVE: "Move", cmd.ROTATE: "Rotate", cmd.SCALE: "Scale"}

# Constraint-Taste → erwarteter `space` (E32, Blender: Shift+Achse schließt aus).
CONSTRAINTS = [
    (_key("x"), "x"),
    (_key("y"), "y"),
    (_key("z"), "z"),
    (_key("x", "shift"), "yz"),
    (_key("y", "shift"), "xz"),
    (_key("z", "shift"), "xy"),
]

ROTATE_SCALE = [cmd.ROTATE, cmd.SCALE]
ALL_TRANSFORMS = [cmd.MOVE, cmd.ROTATE, cmd.SCALE]


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


@pytest.fixture
def begins(app, monkeypatch) -> list[dict]:
    calls: list[dict] = []
    original = app.tool_manager.begin_current_interaction

    def spy(context=None):
        calls.append(context)
        original(context)

    monkeypatch.setattr(app.tool_manager, "begin_current_interaction", spy)
    return calls


def _positions(app) -> dict:
    mesh = app.scene.mesh
    return {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}


def _screen(app, vid) -> tuple[float, float]:
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT)


def _visible_targets(app) -> list[VertexId]:
    """`occlusion=True` (WP-06 B8): matches `Application._pick()`'s default
    Shaded occlusion, which excludes the cube's one fully hidden corner."""
    hits = []
    for vid in sorted(app.scene.mesh.all_vertex_ids()):
        sx, sy = _screen(app, vid)
        if pick_nearest_vertex(app.camera, app.scene.mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) == vid:
            hits.append(vid)
    assert len(hits) >= 2
    return hits


def _move(app, dx: float = 30.0, dy: float = 20.0, steps: int = 3) -> None:
    x, y = app._cursor or (400.0, 300.0)
    for _ in range(steps):
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, dx, dy)


def _select_all(app) -> None:
    app.selection.set(set(app.scene.mesh.all_vertex_ids()))


def _assert_idle(app) -> None:
    assert app.transform_command is None
    assert not app.transform_interacting
    assert app.transform_target == frozenset()
    assert app.transform_space is None
    assert app.tool_manager.active_tool is None


# -- Scharfschalten (E21/E28) ---------------------------------------------------------


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_arm_with_selection_activates_tool_without_begin(app, begins, command):
    a, b = _visible_targets(app)[:2]
    app.selection.set({a, b})
    assert app.key_press(TRANSFORM_KEYS[command])
    assert app.transform_command == command
    assert not app.transform_interacting
    assert app.transform_target == {a, b}
    tool = app.tool_manager.active_tool
    assert isinstance(tool, TOOL_CLASSES[command])
    assert tool.state.name == "ACTIVE"
    assert begins == []
    key = TRANSFORM_KEYS[command].value.upper()
    assert app.status_message == (
        f"{LABELS[command]}: 2 vertices - move the mouse, release {key} to commit"
    )
    # Die Move-Weiterleitungen bleiben Move-spezifisch (E28).
    assert not app.move_armed
    assert not app.move_interacting
    assert app.move_target == frozenset()


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_arm_without_selection_uses_hovered_vertex(app, command):
    vid = _visible_targets(app)[0]
    app.pointer_motion(*_screen(app, vid))
    assert app.selection.hovered == vid
    assert app.key_press(TRANSFORM_KEYS[command])
    assert app.transform_target == {vid}
    assert app.selection.hovered is None


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_arm_with_nothing_is_rejected(app, command):
    app.pointer_motion(*MISS)
    serial = app.status_serial
    assert not app.key_press(TRANSFORM_KEYS[command])
    _assert_idle(app)
    assert app.status_serial == serial + 1
    verb = LABELS[command].lower()
    assert app.status_message == f"{LABELS[command]}: nothing to {verb} (select or hover a vertex)"


@pytest.mark.parametrize(
    "first, second",
    [(a, b) for a in ALL_TRANSFORMS for b in ALL_TRANSFORMS if a != b],
)
def test_only_one_transform_key_can_be_armed(app, begins, first, second):
    _select_all(app)
    assert app.key_press(TRANSFORM_KEYS[first])
    tool = app.tool_manager.active_tool
    assert not app.key_press(TRANSFORM_KEYS[second])
    assert app.transform_command == first
    assert app.tool_manager.active_tool is tool
    _move(app, steps=1)
    assert not app.key_press(TRANSFORM_KEYS[second])
    assert app.tool_manager.active_tool is tool
    assert app.transform_interacting
    # Das Loslassen der abgelehnten Taste committet nicht.
    assert not app.key_release(TRANSFORM_KEYS[second])
    assert app.key_release(TRANSFORM_KEYS[first])
    assert len(app.history) == 1
    assert len(begins) == 1


# -- Bewegung / Commit (E21) ----------------------------------------------------------


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_first_motion_begins_exactly_once(app, begins, command):
    _select_all(app)
    app.key_press(TRANSFORM_KEYS[command])
    _move(app, steps=4)
    assert len(begins) == 1
    assert begins[0]["scene"] is app.scene
    assert begins[0]["camera"] is app.camera
    assert begins[0]["vertex_ids"] == set(app.scene.mesh.all_vertex_ids())
    assert begins[0]["space"] is None
    assert app.transform_interacting


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_zero_delta_motion_does_not_begin(app, begins, command):
    _select_all(app)
    app.key_press(TRANSFORM_KEYS[command])
    assert not app.pointer_motion(400.0, 300.0, 0.0, 0.0)
    assert begins == []
    assert not app.transform_interacting


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_motion_and_release_commits_one_history_entry(app, monkeypatch, command):
    _select_all(app)
    notified: list[set] = []
    original = app.viewport.on_vertices_moved
    monkeypatch.setattr(
        app.viewport, "on_vertices_moved", lambda ids: (notified.append(set(ids)), original(ids))
    )
    before = _positions(app)
    app.key_press(TRANSFORM_KEYS[command])
    _move(app)
    assert _positions(app) != before
    assert notified and all(ids == set(before) for ids in notified)
    assert app.key_release(TRANSFORM_KEYS[command])
    assert len(app.history) == 1
    assert app.status_message == f"{LABELS[command]} committed"
    _assert_idle(app)


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_tap_without_motion_is_a_noop(app, begins, command):
    _select_all(app)
    before = _positions(app)
    app.key_press(TRANSFORM_KEYS[command])
    assert app.key_release(TRANSFORM_KEYS[command])
    assert _positions(app) == before
    assert len(app.history) == 0
    assert begins == []
    participle = {cmd.ROTATE: "rotated", cmd.SCALE: "scaled"}[command]
    assert app.status_message == f"{LABELS[command]}: tool set (no motion, nothing {participle})"
    _assert_idle(app)


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_single_hovered_vertex_transforms_about_itself(app, command):
    """Befund B4 (offener Punkt für den Praxistest, kein Workaround): Das
    Hover-Ziel ist genau ein Vertex; Pivot = Zentroid = dieser Vertex, also
    lassen Rotate/Scale ihn unverändert — der Release meldet "no change" und
    schreibt keinen History-Eintrag."""
    vid = _visible_targets(app)[0]
    app.pointer_motion(*_screen(app, vid))
    before = _positions(app)
    app.key_press(TRANSFORM_KEYS[command])
    _move(app)
    assert app.key_release(TRANSFORM_KEYS[command])
    assert _positions(app) == before
    assert len(app.history) == 0
    assert app.status_message == f"{LABELS[command]}: no change"


# -- Esc / Undo / Redo (E22/E23) ----------------------------------------------------


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_esc_mid_transform_restores_exactly_without_history(app, command):
    _select_all(app)
    before = _positions(app)
    app.key_press(TRANSFORM_KEYS[command])
    _move(app)
    assert _positions(app) != before
    assert app.key_press(ESC)
    assert _positions(app) == before
    assert len(app.history) == 0
    assert app.status_message == f"{LABELS[command]} cancelled"
    _assert_idle(app)
    # Das spätere Loslassen der Taste ist wirkungslos.
    assert not app.key_release(TRANSFORM_KEYS[command])


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_esc_while_armed_only_disarms(app, command):
    _select_all(app)
    app.key_press(TRANSFORM_KEYS[command])
    assert app.key_press(ESC)
    assert app.status_message == f"{LABELS[command]} disarmed"
    _assert_idle(app)


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_undo_redo_after_commit(app, command):
    _select_all(app)
    before = _positions(app)
    app.key_press(TRANSFORM_KEYS[command])
    _move(app)
    app.key_release(TRANSFORM_KEYS[command])
    after = _positions(app)
    assert app.key_press(CTRL_Z)
    assert _positions(app) == before
    assert app.key_press(CTRL_Y)
    assert _positions(app) == after


@pytest.mark.parametrize("command", ROTATE_SCALE)
def test_undo_ignored_while_transforming_and_disarms_when_armed(app, command):
    _select_all(app)
    app.key_press(W)
    _move(app)
    app.key_release(W)
    assert len(app.history) == 1

    app.key_press(TRANSFORM_KEYS[command])
    _move(app)
    assert not app.key_press(CTRL_Z)
    assert app.transform_interacting
    app.key_press(ESC)

    moved = _positions(app)
    app.key_press(TRANSFORM_KEYS[command])
    assert app.key_press(CTRL_Z)
    _assert_idle(app)
    assert _positions(app) != moved


# -- Constraints (B4.1: sticky Toggle wie im Playground) ------------------------------


@pytest.mark.parametrize("key, space", CONSTRAINTS)
def test_constraint_key_sets_state_without_armed_tool(app, key, space):
    serial = app.status_serial
    assert app.key_press(key)
    assert app.axis_constraint == space
    assert app.status_serial == serial + 1
    label = space.upper() if len(space) == 1 else f"{space.upper()} plane"
    assert app.status_message == f"Constraint: {label}"
    assert app.tool_manager.active_tool is None


@pytest.mark.parametrize("key, space", CONSTRAINTS)
def test_same_key_again_toggles_off(app, key, space):
    app.key_press(key)
    assert app.key_press(key)
    assert app.axis_constraint is None
    assert app.status_message == "Constraint: none"


def test_other_key_replaces(app):
    app.key_press(_key("x"))
    app.key_press(_key("y"))
    assert app.axis_constraint == "y"
    app.key_press(_key("z", "shift"))
    assert app.axis_constraint == "xy"
    app.key_press(_key("x", "shift"))
    assert app.axis_constraint == "yz"
    app.key_press(_key("y", "shift"))
    assert app.axis_constraint == "xz"


def test_axis_and_shift_axis_are_different_constraints(app):
    app.key_press(_key("x"))
    app.key_press(_key("x", "shift"))  # ersetzt, kein Toggle
    assert app.axis_constraint == "yz"


@pytest.mark.parametrize("command", ALL_TRANSFORMS)
@pytest.mark.parametrize("key, space", CONSTRAINTS)
def test_constraint_set_before_arming_reaches_begin(app, begins, command, key, space):
    _select_all(app)
    app.key_press(key)
    app.key_press(TRANSFORM_KEYS[command])
    _move(app)
    assert len(begins) == 1
    assert begins[0]["space"] == space
    assert app.transform_space == space
    assert app.key_release(TRANSFORM_KEYS[command])
    assert len(app.history) == 1
    _assert_idle(app)
    assert app.axis_constraint == space


@pytest.mark.parametrize("command", ALL_TRANSFORMS)
def test_constraint_set_while_armed_before_motion_reaches_begin(app, begins, command):
    _select_all(app)
    app.key_press(TRANSFORM_KEYS[command])
    app.key_press(_key("z"))
    _move(app)
    assert begins[0]["space"] == "z"


@pytest.mark.parametrize("command", ALL_TRANSFORMS)
def test_constraint_persists_across_commit_and_cancel(app, begins, command):
    _select_all(app)
    app.key_press(_key("x"))
    key = TRANSFORM_KEYS[command]

    app.key_press(key)
    _move(app)
    app.key_release(key)  # Commit
    app.key_press(key)
    _move(app)
    app.key_press(ESC)  # Cancel
    app.key_release(key)
    app.key_press(key)
    app.key_release(key)  # Antippen: entschärft nur
    app.key_press(key)
    _move(app)
    app.key_release(key)

    assert app.axis_constraint == "x"
    assert [b["space"] for b in begins] == ["x", "x", "x"]
    assert len(app.history) == 2


def test_constraint_carries_over_between_tools(app, begins):
    _select_all(app)
    app.key_press(_key("z"))
    for key in (W, E, R):
        app.key_press(key)
        _move(app)
        app.key_release(key)
    assert [b["space"] for b in begins] == ["z", "z", "z"]


@pytest.mark.parametrize("command", ALL_TRANSFORMS)
def test_key_during_motion_changes_state_but_not_running_gesture(app, begins, command):
    _select_all(app)
    key = TRANSFORM_KEYS[command]
    app.key_press(key)
    _move(app, steps=1)
    tool = app.tool_manager.active_tool
    assert app.key_press(_key("y"))
    assert app.axis_constraint == "y"
    assert app.status_message == "Constraint: Y"
    # Laufende Geste: kein Neustart, `space` bleibt der von begin().
    assert app.transform_interacting
    assert app.tool_manager.active_tool is tool
    assert app.transform_space is None
    _move(app, steps=2)
    assert len(begins) == 1
    app.key_release(key)
    assert len(app.history) == 1
    # Nächste Geste nutzt den neuen Wert.
    app.key_press(key)
    _move(app)
    assert begins[1]["space"] == "y"


def test_toggle_off_during_motion_frees_the_next_gesture(app, begins):
    _select_all(app)
    app.key_press(_key("x"))
    app.key_press(W)
    _move(app, steps=1)
    app.key_press(_key("x"))  # aus
    _move(app, steps=1)
    app.key_release(W)
    app.key_press(W)
    _move(app)
    assert [b["space"] for b in begins] == ["x", None]


def test_undo_redo_unaffected_by_constraint(app):
    _select_all(app)
    app.key_press(_key("x"))
    before = _positions(app)
    app.key_press(R)
    _move(app)
    app.key_release(R)
    after = _positions(app)
    assert app.key_press(CTRL_Z)
    assert _positions(app) == before
    assert app.axis_constraint == "x"
    assert app.key_press(CTRL_Y)
    assert _positions(app) == after
    assert app.axis_constraint == "x"
    # Ctrl+Z/Ctrl+Y sind keine Constraint-Tasten.
    assert app.status_message == cmd.REDO


@pytest.mark.parametrize(
    "command, constraint_key, arm_suffix",
    [
        (cmd.ROTATE, _key("z"), " (constraint Z)"),
        (cmd.SCALE, _key("x", "shift"), " (constraint YZ plane)"),
        (cmd.MOVE, None, ""),
    ],
)
def test_arm_and_commit_status_show_active_constraint(app, command, constraint_key, arm_suffix):
    _select_all(app)
    if constraint_key is not None:
        app.key_press(constraint_key)
    key = TRANSFORM_KEYS[command]
    app.key_press(key)
    assert app.status_message == (
        f"{LABELS[command]}: 8 vertices{arm_suffix} - move the mouse, "
        f"release {key.value.upper()} to commit"
    )
    _move(app)
    app.key_release(key)
    assert app.status_message == f"{LABELS[command]} committed{arm_suffix}"


def test_commit_status_shows_the_gestures_constraint_not_a_later_change(app):
    _select_all(app)
    app.key_press(_key("x"))
    app.key_press(W)
    _move(app, steps=1)
    app.key_press(_key("y"))
    app.key_release(W)
    assert app.status_message == "Move committed (constraint X)"


# -- Constraint-Wirkung über die bestehenden Tools (E32, keine neue Mathematik) ------


def _changed_components(before: dict, after: dict) -> set[int]:
    changed = set()
    for vid, old in before.items():
        new = after[vid]
        for i in range(3):
            if abs(new[i] - old[i]) > 1e-9:
                changed.add(i)
    return changed


@pytest.mark.parametrize(
    "command, key, frozen",
    [
        (cmd.SCALE, _key("x"), {1, 2}),
        (cmd.SCALE, _key("x", "shift"), {0}),  # YZ-Ebene: X gesperrt
        (cmd.MOVE, _key("y"), {0, 2}),
        (cmd.MOVE, _key("z", "shift"), {2}),  # XY-Ebene: Z gesperrt
        (cmd.ROTATE, _key("z"), {2}),  # um Z: Z-Koordinaten bleiben
        (cmd.ROTATE, _key("z", "shift"), {2}),  # XY-Ebene = um Z
        (cmd.ROTATE, _key("y", "shift"), {1}),  # XZ-Ebene = um Y
    ],
)
def test_constraint_limits_the_changed_components(app, command, key, frozen):
    _select_all(app)
    before = _positions(app)
    app.key_press(TRANSFORM_KEYS[command])
    app.key_press(key)
    _move(app)
    after = _positions(app)
    changed = _changed_components(before, after)
    assert changed
    assert not (changed & frozen)
    app.key_release(TRANSFORM_KEYS[command])
    assert len(app.history) == 1


def test_rotate_plane_constraint_resolves_to_plane_normal(app):
    _select_all(app)
    app.key_press(E)
    app.key_press(_key("x", "shift"))
    _move(app, steps=1)
    assert app.tool_manager.active_tool.axis == (1.0, 0.0, 0.0)


def test_scale_plane_constraint_resolves_to_axis_mask(app):
    _select_all(app)
    app.key_press(R)
    app.key_press(_key("y", "shift"))
    _move(app, steps=1)
    assert app.tool_manager.active_tool.axes_mask == (1.0, 0.0, 1.0)
