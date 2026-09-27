"""Application: Rotate/Scale auf E/R + Achsen-Constraints (WP-06 B4, E28-E35).

Headless (TraceStore), kein pyglet/Fenster. Gleicher AD-016-Pfad wie Move
(`test_application_move.py`): Taste → `Application.key_press` (scharf, Tool
aktiv) → optional Constraint-Taste → `pointer_motion(x, y, dx, dy)` (erste
Bewegung: `begin(space=...)`, dann `update`) → Release → `commit`.
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
    hits = []
    for vid in sorted(app.scene.mesh.all_vertex_ids()):
        sx, sy = _screen(app, vid)
        if pick_nearest_vertex(app.camera, app.scene.mesh, sx, sy, WIDTH, HEIGHT) == vid:
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


# -- Constraints (E30-E33) ---------------------------------------------------------------


@pytest.mark.parametrize("command", ALL_TRANSFORMS)
@pytest.mark.parametrize("key, space", CONSTRAINTS)
def test_constraint_before_first_motion_reaches_begin(app, begins, command, key, space):
    _select_all(app)
    app.key_press(TRANSFORM_KEYS[command])
    assert app.key_press(key)
    assert app.transform_space == space
    _move(app)
    assert len(begins) == 1
    assert begins[0]["space"] == space
    assert app.key_release(TRANSFORM_KEYS[command])
    assert len(app.history) == 1
    _assert_idle(app)


@pytest.mark.parametrize("command", ALL_TRANSFORMS)
def test_constraint_after_first_motion_is_ignored_with_status(app, begins, command):
    _select_all(app)
    app.key_press(TRANSFORM_KEYS[command])
    _move(app, steps=1)
    serial = app.status_serial
    assert not app.key_press(_key("x"))
    assert app.transform_space is None
    assert app.status_serial == serial + 1
    assert app.status_message == (
        f"{LABELS[command]}: axis constraint only before the first mouse motion"
    )
    _move(app, steps=2)
    assert len(begins) == 1
    assert begins[0]["space"] is None


@pytest.mark.parametrize("key, _space", CONSTRAINTS)
def test_constraint_without_armed_transform_is_a_silent_noop(app, key, _space):
    _select_all(app)
    serial = app.status_serial
    assert not app.key_press(key)
    assert app.status_serial == serial
    _assert_idle(app)


def test_constraint_is_not_remembered_for_the_next_arm(app, begins):
    _select_all(app)
    app.key_press(_key("x"))
    app.key_press(E)
    assert app.transform_space is None
    _move(app)
    assert begins[0]["space"] is None


def test_constraint_is_reset_between_arms(app, begins):
    _select_all(app)
    app.key_press(R)
    app.key_press(_key("x"))
    app.key_release(R)  # Antippen: entschärft
    app.key_press(R)
    assert app.transform_space is None
    _move(app)
    assert begins[0]["space"] is None


def test_last_constraint_before_motion_wins(app, begins):
    _select_all(app)
    app.key_press(R)
    app.key_press(_key("x"))
    app.key_press(_key("z", "shift"))
    assert app.transform_space == "xy"
    # Gleiche Taste erneut: kein Toggle zurück auf frei (E31).
    app.key_press(_key("z", "shift"))
    assert app.transform_space == "xy"
    _move(app)
    assert begins[0]["space"] == "xy"


@pytest.mark.parametrize(
    "command, key, expected",
    [
        (cmd.ROTATE, _key("x"), "Rotate: constrained to X"),
        (cmd.ROTATE, _key("z", "shift"), "Rotate: constrained to XY plane (around Z)"),
        (cmd.ROTATE, _key("x", "shift"), "Rotate: constrained to YZ plane (around X)"),
        (cmd.SCALE, _key("y"), "Scale: constrained to Y"),
        (cmd.SCALE, _key("y", "shift"), "Scale: constrained to XZ plane"),
        (cmd.MOVE, _key("z"), "Move: constrained to Z"),
    ],
)
def test_constraint_status_line(app, command, key, expected):
    _select_all(app)
    app.key_press(TRANSFORM_KEYS[command])
    app.key_press(key)
    assert app.status_message == expected


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
