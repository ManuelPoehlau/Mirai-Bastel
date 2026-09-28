"""Application: Move auf W, AD-016 hold-key-hover (WP-06 B3, E21-E25).

Headless (TraceStore), kein pyglet/Fenster. Pfad: W-Press →
`Application.key_press` (scharf, Tool aktiv) → `pointer_motion(x, y, dx, dy)`
(erste Bewegung: `begin`, dann `update` + `viewport.on_vertices_moved`) →
W-Release → `commit` (ein History-Eintrag) bzw. Antippen = No-op.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import VertexId
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.interaction.tools import MoveTool
from mirai.viewport.picking import pick_nearest_vertex
from viewport.overlay import HOVER_LAYER, SELECTED_LAYER

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)  # Bildecke: weit weg von jedem Würfel-Vertex


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


W = _key("w")
ESC = _key("ESCAPE")
CTRL_Z = _key("z", "ctrl")
CTRL_Y = _key("y", "ctrl")


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
    """Vertices, die ein Hover/Klick auf ihre Projektion auch trifft.
    `occlusion=True` (WP-06 B8): matches `Application._pick()`'s default
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


def _assert_idle(app) -> None:
    assert not app.move_armed
    assert not app.move_interacting
    assert app.move_target == frozenset()
    assert app.tool_manager.active_tool is None


# -- Scharfschalten (E21) -----------------------------------------------------------


def test_arm_with_selection_activates_tool_without_begin(app, begins):
    a, b = _visible_targets(app)[:2]
    app.selection.set({a, b})
    assert app.key_press(W)
    assert app.move_armed
    assert not app.move_interacting
    assert app.move_target == {a, b}
    tool = app.tool_manager.active_tool
    assert isinstance(tool, MoveTool)
    assert tool.state.name == "ACTIVE"
    assert begins == []
    assert "2 vertices" in app.status_message


def test_arm_without_selection_uses_hovered_vertex(app):
    vid = _visible_targets(app)[0]
    app.pointer_motion(*_screen(app, vid))
    assert app.selection.hovered == vid
    assert app.key_press(W)
    assert app.move_target == {vid}
    # Hover-Ziel = gehoverter Vertex → Hover-Punkt wird beim Scharfschalten gelöscht.
    assert app.selection.hovered is None


def test_arm_with_nothing_is_rejected(app):
    app.pointer_motion(*MISS)
    serial = app.status_serial
    assert not app.key_press(W)
    _assert_idle(app)
    assert app.status_serial == serial + 1
    assert "nothing to move" in app.status_message


def test_press_while_armed_is_ignored(app, begins):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    app.key_press(W)
    tool = app.tool_manager.active_tool
    assert not app.key_press(W)
    assert app.tool_manager.active_tool is tool
    _move(app, steps=1)
    assert not app.key_press(W)
    assert app.move_interacting
    assert len(begins) == 1


def test_target_is_fixed_at_press(app):
    a, b = _visible_targets(app)[:2]
    app.selection.set({a})
    before = _positions(app)
    app.key_press(W)
    app.selection.set({b})  # nach dem Scharfschalten, vor der ersten Bewegung
    _move(app)
    app.key_release(W)
    after = _positions(app)
    assert after[a] != before[a]
    assert after[b] == before[b]


# -- Bewegung / Commit (E21) ----------------------------------------------------------


def test_first_motion_begins_exactly_once(app, begins):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    app.key_press(W)
    _move(app, steps=4)
    assert len(begins) == 1
    assert begins[0]["vertex_ids"] == {vid}
    assert begins[0]["scene"] is app.scene
    assert begins[0]["camera"] is app.camera


def test_single_pixel_motion_starts_the_move(app, begins):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    before = app.scene.mesh.vertex_position(vid)
    app.key_press(W)
    assert app.pointer_motion(401.0, 300.0, 1.0, 0.0)
    assert app.move_interacting
    assert len(begins) == 1
    assert app.scene.mesh.vertex_position(vid) != before


def test_zero_delta_motion_does_not_start_the_move(app, begins):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    app.key_press(W)
    assert not app.pointer_motion(400.0, 300.0, 0.0, 0.0)
    assert not app.move_interacting
    assert begins == []


def test_motion_and_release_commits_one_history_entry(app):
    a, b = _visible_targets(app)[:2]
    app.selection.set({a, b})
    before = _positions(app)
    app.key_press(W)
    _move(app)
    live = _positions(app)
    assert live[a] != before[a] and live[b] != before[b]
    assert len(app.history) == 0  # update() erzeugt keine History
    assert app.key_release(W)
    assert _positions(app) == live
    assert len(app.history) == 1
    assert app.status_message == "Move committed"
    _assert_idle(app)
    # Nur die Ziel-Vertices haben sich bewegt.
    for vid, pos in before.items():
        if vid not in (a, b):
            assert live[vid] == pos


def test_live_update_moves_the_point_overlay(app):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    app.key_press(W)
    _move(app, steps=1)
    app.update_viewport(0.0)
    assert app.viewport.point_positions[SELECTED_LAYER] == [
        app.scene.mesh.vertex_position(vid)
    ]


def test_tap_without_motion_is_a_noop(app, begins):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    before = _positions(app)
    app.key_press(W)
    assert app.key_release(W)
    assert _positions(app) == before
    assert len(app.history) == 0
    assert begins == []
    assert "tool set" in app.status_message
    _assert_idle(app)


def test_release_with_changed_modifiers_still_commits(app):
    # Alt/Shift dürfen zwischen Press und Release dazukommen (z. B. Orbit).
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    app.key_press(W)
    _move(app)
    assert app.key_release(_key("w", "alt"))
    assert len(app.history) == 1
    _assert_idle(app)


def test_release_of_another_key_does_not_commit(app):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    app.key_press(W)
    _move(app)
    assert not app.key_release(_key("e"))
    assert app.move_interacting


def test_rebound_move_key_releases_on_its_own_key(app):
    app.bindings.bind(_key("g"), "Move")
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    app.key_press(_key("g"))
    _move(app)
    assert not app.key_release(W)
    assert app.key_release(_key("g"))
    assert len(app.history) == 1


# -- Esc (E22) --------------------------------------------------------------------------


def test_esc_mid_move_restores_exactly_without_history(app, monkeypatch):
    a, b = _visible_targets(app)[:2]
    app.selection.set({a, b})
    app.viewport.on_selection_changed()
    before = _positions(app)
    app.key_press(W)
    _move(app)
    assert app.key_press(ESC)
    assert _positions(app) == before
    assert len(app.history) == 0
    assert app.status_message == "Move cancelled"
    _assert_idle(app)
    app.update_viewport(0.0)
    assert sorted(app.viewport.point_positions[SELECTED_LAYER]) == sorted(
        [before[a], before[b]]
    )
    # Das spätere Loslassen der noch gehaltenen W-Taste tut nichts mehr.
    assert not app.key_release(W)
    assert len(app.history) == 0


def test_esc_while_armed_only_disarms(app):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    before = _positions(app)
    app.key_press(W)
    assert app.key_press(ESC)
    assert _positions(app) == before
    assert app.status_message == "Move disarmed"
    _assert_idle(app)


# -- Undo / Redo (E23) ----------------------------------------------------------------


def test_undo_redo_after_move(app):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    original = app.scene.mesh.vertex_position(vid)
    app.key_press(W)
    _move(app)
    app.key_release(W)
    moved = app.scene.mesh.vertex_position(vid)

    assert app.key_press(CTRL_Z)
    assert app.scene.mesh.vertex_position(vid) == original
    app.update_viewport(0.0)
    assert app.viewport.point_positions[SELECTED_LAYER] == [original]

    assert app.key_press(CTRL_Y)
    assert app.scene.mesh.vertex_position(vid) == moved
    app.update_viewport(0.0)
    assert app.viewport.point_positions[SELECTED_LAYER] == [moved]


def test_several_undo_redo_steps(app):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    states = [app.scene.mesh.vertex_position(vid)]
    for _ in range(3):
        app.key_press(W)
        _move(app, steps=1)
        app.key_release(W)
        states.append(app.scene.mesh.vertex_position(vid))
    assert len(app.history) == 3
    for expected in reversed(states[:-1]):
        app.key_press(CTRL_Z)
        assert app.scene.mesh.vertex_position(vid) == expected
    for expected in states[1:]:
        app.key_press(CTRL_Y)
        assert app.scene.mesh.vertex_position(vid) == expected


def test_undo_redo_ignored_during_move(app):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    app.key_press(W)
    _move(app, steps=1)
    app.key_release(W)
    committed = app.scene.mesh.vertex_position(vid)

    app.key_press(W)
    _move(app, steps=1)
    live = app.scene.mesh.vertex_position(vid)
    assert not app.key_press(CTRL_Z)
    assert not app.key_press(CTRL_Y)
    assert app.move_interacting
    assert app.scene.mesh.vertex_position(vid) == live
    assert len(app.history) == 1
    app.key_release(W)
    assert len(app.history) == 2
    assert app.scene.mesh.vertex_position(vid) != committed


def test_undo_while_armed_disarms_first(app):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    original = app.scene.mesh.vertex_position(vid)
    app.key_press(W)
    _move(app)
    app.key_release(W)

    app.key_press(W)  # scharf, noch keine Bewegung
    assert app.key_press(CTRL_Z)
    _assert_idle(app)
    assert app.scene.mesh.vertex_position(vid) == original
    # Das spätere Loslassen von W tut nichts mehr.
    assert not app.key_release(W)
    assert len(app.history) == 0


# -- Hover (E24) ----------------------------------------------------------------------------


def test_no_hover_recompute_while_armed_or_moving(app, monkeypatch):
    a, b = _visible_targets(app)[:2]
    app.selection.set({a})
    app.key_press(W)
    picks: list[tuple] = []
    original = app._update_hover
    monkeypatch.setattr(app, "_update_hover", lambda x, y: picks.append((x, y)) or original(x, y))

    app.pointer_motion(*_screen(app, b))  # scharf, dx=dy=0 → kein Move-Schritt
    app.pointer_scroll(Input("wheel", "UP"))
    _move(app)
    app.pointer_scroll(Input("wheel", "DOWN"))
    assert picks == []
    assert app.selection.hovered is None


def test_hover_is_repicked_after_commit(app):
    a, b = _visible_targets(app)[:2]
    app.selection.set({a})
    app.key_press(W)
    _move(app, steps=1)
    app.pointer_motion(*_screen(app, b), 0.0, 0.0)  # Cursor über b, kein Move-Schritt
    assert app.selection.hovered is None
    app.key_release(W)
    assert app.selection.hovered == b
    app.update_viewport(0.0)
    assert app.viewport.point_positions[HOVER_LAYER] == [app.scene.mesh.vertex_position(b)]


def test_hover_is_repicked_after_cancel(app):
    vid = _visible_targets(app)[0]
    cursor = _screen(app, vid)
    app.pointer_motion(*cursor)
    app.key_press(W)  # Hover-Ziel, Hover-Punkt gelöscht
    assert app.selection.hovered is None
    app.pointer_motion(cursor[0] + 30.0, cursor[1], 30.0, 0.0)
    app.pointer_motion(*cursor, -30.0, 0.0)
    app.key_press(ESC)
    # Vertex zurück an der Ausgangsposition, Cursor steht dort.
    assert app.selection.hovered == vid


def test_arming_from_selection_clears_overlapping_hover(app):
    a, b = _visible_targets(app)[:2]
    app.selection.set({a, b})
    app.pointer_motion(*_screen(app, a))
    assert app.selection.hovered == a
    app.key_press(W)
    assert app.selection.hovered is None


def test_arming_from_selection_keeps_unrelated_hover(app):
    a, b = _visible_targets(app)[:2]
    app.selection.set({a})
    app.pointer_motion(*_screen(app, b))
    assert app.selection.hovered == b
    app.key_press(W)
    assert app.selection.hovered == b
    assert app.move_target == {a}


# -- Pointer-Pfad (E25) ---------------------------------------------------------------------


def test_motion_without_move_falls_back_to_hover(app):
    vid = _visible_targets(app)[0]
    before = _positions(app)
    assert app.pointer_motion(*_screen(app, vid), 5.0, 5.0)
    assert app.selection.hovered == vid
    assert _positions(app) == before


def test_camera_gesture_wins_while_armed(app):
    vid = _visible_targets(app)[0]
    app.selection.set({vid})
    before = _positions(app)
    app.key_press(W)
    yaw_before = app.camera.yaw

    app.pointer_press(Input("mouse", "LEFT", frozenset({"alt"})))
    assert app.pointer_drag(40.0, 0.0)  # Orbit
    # Eine (theoretische) Motion während der Kamerageste treibt keinen Move.
    assert not app.pointer_motion(450.0, 300.0, 40.0, 0.0)
    app.pointer_release("LEFT", 450.0, 300.0)

    assert _positions(app) == before
    assert not app.move_interacting
    assert app.move_armed
    assert app.camera.yaw != yaw_before
    # Nach der Kamerageste bewegt die nächste Mausbewegung wieder den Move.
    _move(app, steps=1)
    assert app.move_interacting
    app.key_release(W)
    assert len(app.history) == 1


def test_undo_while_armed_with_empty_history_restores_hover(app):
    vid = _visible_targets(app)[0]
    app.pointer_motion(*_screen(app, vid))
    app.key_press(W)  # Hover-Ziel → Hover-Punkt gelöscht
    assert app.selection.hovered is None
    assert not app.key_press(CTRL_Z)
    _assert_idle(app)
    assert app.selection.hovered == vid
