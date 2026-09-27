"""Application: Tasten über die Bindings — Esc, Undo/Redo, Status (WP-06 B3).

Headless (TraceStore), kein pyglet/Fenster. Pfad: Taste →
`Application.key_press`/`key_release` → `BindingSet` (GLOBAL) → Command.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_nearest_vertex
from viewport.overlay import SELECTED_LAYER

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


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


def _positions(app) -> dict:
    mesh = app.scene.mesh
    return {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}


def _screen(app, vid) -> tuple[float, float]:
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT)


def _visible_target(app):
    for vid in app.scene.mesh.all_vertex_ids():
        sx, sy = _screen(app, vid)
        if pick_nearest_vertex(app.camera, app.scene.mesh, sx, sy, WIDTH, HEIGHT) == vid:
            return vid
    raise AssertionError("no pickable vertex")


def _committed_move(app, vid) -> None:
    """Ein Move-History-Eintrag direkt über den ToolManager (ohne Tasten)."""
    app.dispatch_command(
        cmd.MOVE,
        context={"scene": app.scene, "camera": app.camera, "vertex_ids": {vid}},
    )
    app.tool_manager.update(dx=40.0, dy=25.0, width=WIDTH, height=HEIGHT)
    app.tool_manager.commit()
    app.tool_manager.deactivate()
    app.viewport.on_vertices_moved({vid})


def _topology_spy(app, monkeypatch) -> list[None]:
    calls: list[None] = []
    original = app.viewport.on_topology_changed

    def spy() -> None:
        calls.append(None)
        original()

    monkeypatch.setattr(app.viewport, "on_topology_changed", spy)
    return calls


# -- Esc -----------------------------------------------------------------------


def test_esc_idle_does_nothing(app):
    before = _positions(app)
    assert not app.key_press(ESC)
    assert _positions(app) == before
    assert len(app.history) == 0
    assert app.tool_manager.active_tool is None


# -- Undo / Redo -----------------------------------------------------------------


def test_undo_redo_restore_positions_and_notify_viewport(app, monkeypatch):
    vid = _visible_target(app)
    original = app.scene.mesh.vertex_position(vid)
    _committed_move(app, vid)
    moved = app.scene.mesh.vertex_position(vid)
    assert moved != original
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    rebuilds = _topology_spy(app, monkeypatch)

    assert app.key_press(CTRL_Z)
    assert app.scene.mesh.vertex_position(vid) == original
    assert app.status_message == cmd.UNDO
    assert len(rebuilds) == 1
    app.update_viewport(0.0)
    assert app.viewport.point_positions[SELECTED_LAYER] == [original]

    assert app.key_press(CTRL_Y)
    assert app.scene.mesh.vertex_position(vid) == moved
    assert app.status_message == cmd.REDO
    assert len(rebuilds) == 2
    app.update_viewport(0.0)
    assert app.viewport.point_positions[SELECTED_LAYER] == [moved]


def test_undo_with_empty_history_is_a_noop(app, monkeypatch):
    rebuilds = _topology_spy(app, monkeypatch)
    assert not app.key_press(CTRL_Z)
    assert not app.key_press(CTRL_Y)
    assert rebuilds == []
    assert "nothing" in app.status_message


def test_undo_repicks_hover_at_last_cursor(app):
    vid = _visible_target(app)
    cursor = _screen(app, vid)
    _committed_move(app, vid)
    # Cursor steht an der alten Position des Vertex; dort ist nach dem Move
    # ggf. ein anderer (oder kein) Vertex.
    app.pointer_motion(*cursor)
    hovered_after_move = app.selection.hovered
    app.key_press(CTRL_Z)
    # Nach dem Undo liegt der Vertex wieder unter dem ruhenden Cursor.
    assert app.selection.hovered == vid
    assert hovered_after_move != vid


# -- Status ----------------------------------------------------------------------


def test_status_serial_counts_repeated_messages(app):
    vid = _visible_target(app)
    _committed_move(app, vid)
    _committed_move(app, vid)
    serial = app.status_serial
    app.key_press(CTRL_Z)
    app.key_press(CTRL_Z)
    assert app.status_message == cmd.UNDO
    assert app.status_serial == serial + 2


# -- Rotate / Scale (erst B4) ---------------------------------------------------


@pytest.mark.parametrize("key", ["e", "r"])
def test_rotate_scale_keys_are_inert_until_b4(app, key):
    app.selection.set({_visible_target(app)})
    before = _positions(app)
    serial = app.status_serial
    assert app.bindings.command_for(_key(key)) in (cmd.ROTATE, cmd.SCALE)
    assert not app.key_press(_key(key))
    assert not app.key_release(_key(key))
    assert app.tool_manager.active_tool is None
    assert _positions(app) == before
    assert app.status_serial == serial


def test_q_is_unbound(app):
    assert app.bindings.command_for(_key("q")) is None
    assert not app.key_press(_key("q"))
    assert app.tool_manager.active_tool is None
