"""Box Select, Paint Select and Tweak in the production app (2026-10-15, Playground tools
promoted, Manu): LMB drag from empty space = Box, from the mesh = Paint (no modifier replaces,
Shift adds); Ctrl+LMB drag = Tweak with the last W/E/R (Move by default) on the selection, else
on the element under the press point. Ctrl+LMB click still removes. None of the selections is a
History step; a Tweak is exactly one."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.viewport.box_select import stroke_samples

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


K1, K2, K3, K4 = _key("1"), _key("2"), _key("3"), _key("4")
W, E, ESC, CTRL_Z = _key("w"), _key("e"), _key("ESCAPE"), _key("z", "ctrl")


def _grid(n: int = 4, size: float = 4.0) -> Mesh:
    mesh = Mesh()
    step = size / n
    half = size / 2.0
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((c * step - half, r * step - half, 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_grid().export_state())
    app.frame_scene()
    # Look straight at the grid (+Z), so a screen rectangle is a world rectangle.
    app.camera.yaw = 0.0
    app.camera.pitch = 0.0
    app.camera.camera_revision += 1
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _screen(app, position):
    return app.camera.project_to_screen(position, WIDTH, HEIGHT)


def _vertex(mesh, x: float, y: float):
    (vid,) = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (x, y)]
    return vid


def _drag(app, inp: Input, start, end, steps: int = 10) -> bool:
    app.pointer_motion(*start)
    app.pointer_press(inp, *start)
    (x0, y0), (x1, y1) = start, end
    px, py = x0, y0
    for i in range(1, steps + 1):
        x = x0 + (x1 - x0) * i / steps
        y = y0 + (y1 - y0) * i / steps
        app.pointer_drag(x - px, y - py, x, y)
        px, py = x, y
    return app.pointer_release(inp.value, x1, y1)


def _state(app) -> dict:
    return {k: v for k, v in app.scene.mesh.export_state().items() if not k.endswith("_id_counter")}


# -- bindings -------------------------------------------------------------------------------


def test_drag_bindings():
    bindings = build_default_bindings()
    assert bindings.command_for(Input("drag", "LEFT")) == cmd.SELECT_DRAG
    assert bindings.command_for(Input("drag", "LEFT", frozenset({"shift"}))) == cmd.SELECT_DRAG_ADD
    assert bindings.command_for(Input("drag", "LEFT", frozenset({"ctrl"}))) == cmd.TWEAK
    # The clicks stay as they were.
    assert bindings.command_for(_mouse("LEFT", "ctrl")) == cmd.SELECT_REMOVE
    assert bindings.command_for(Input("drag", "LEFT", frozenset({"alt"}))) == cmd.ORBIT


# -- Box ------------------------------------------------------------------------------------


def test_box_from_empty_space_selects_the_vertices_inside(app):
    mesh = app.scene.mesh
    app.key_press(K1)
    corner = _screen(app, (-2.4, -2.4, 0.0))
    inner = _screen(app, (0.2, 0.2, 0.0))
    assert _drag(app, _mouse("LEFT"), corner, inner) is True
    expected = {_vertex(mesh, x, y) for x in (-2.0, -1.0, 0.0) for y in (-2.0, -1.0, 0.0)}
    assert app.selection.vertices == expected
    assert app.selection_box is None
    assert not app.history.can_undo()


def test_box_replaces_and_shift_box_adds(app):
    app.key_press(K3)
    a0, a1 = _screen(app, (-2.4, -2.4, 0.0)), _screen(app, (-0.9, -0.9, 0.0))
    _drag(app, _mouse("LEFT"), a0, a1)
    assert len(app.selection.faces) == 1
    b0, b1 = _screen(app, (2.4, 2.4, 0.0)), _screen(app, (0.9, 0.9, 0.0))
    _drag(app, _mouse("LEFT", "shift"), b0, b1)
    assert len(app.selection.faces) == 2
    _drag(app, _mouse("LEFT"), b0, b1)
    assert len(app.selection.faces) == 1
    assert app.status_message == "Box: 1 face selected"


def test_box_rect_is_shown_while_dragging_and_esc_discards_it(app):
    app.key_press(K1)
    start = _screen(app, (-2.4, -2.4, 0.0))
    app.pointer_press(_mouse("LEFT"), *start)
    app.pointer_drag(30, 30, start[0] + 30, start[1] + 30)
    assert app.selection_box == (start[0], start[1], start[0] + 30, start[1] + 30)
    assert app.key_press(ESC) is True
    assert app.selection_box is None
    assert app.pointer_release("LEFT", start[0] + 30, start[1] + 30) is False
    assert app.selection.vertices == set()


# -- Paint ----------------------------------------------------------------------------------


def test_drag_from_the_mesh_paints_and_replaces(app):
    mesh = app.scene.mesh
    app.key_press(K3)
    app.selection.faces = set(mesh.all_face_ids())
    start, end = _screen(app, (-1.5, -1.5, 0.0)), _screen(app, (1.5, -1.5, 0.0))
    assert _drag(app, _mouse("LEFT"), start, end) is True
    # The bottom row of four faces, nothing else (the old selection is replaced).
    assert len(app.selection.faces) == 4
    ys = {
        round(sum(mesh.vertex_position(v)[1] for v in mesh.face_vertices(f)) / 4, 6)
        for f in app.selection.faces
    }
    assert ys == {-1.5}
    assert app.status_message == "Paint: 4 faces selected"
    assert not app.history.can_undo()


def test_shift_paint_adds_and_esc_restores_the_selection(app):
    mesh = app.scene.mesh
    app.key_press(K3)
    keep = next(iter(mesh.all_face_ids()))
    app.selection.faces = {keep}
    start, end = _screen(app, (-1.5, 1.5, 0.0)), _screen(app, (1.5, 1.5, 0.0))
    _drag(app, _mouse("LEFT", "shift"), start, end)
    assert keep in app.selection.faces and len(app.selection.faces) == 5
    app.selection.faces = {keep}
    app.pointer_press(_mouse("LEFT"), *start)
    app.pointer_drag(end[0] - start[0], 0, *end)
    assert app.selection.faces != {keep}
    assert app.key_press(ESC) is True
    assert app.selection.faces == {keep}
    app.pointer_release("LEFT", *end)
    assert app.selection.faces == {keep}


def test_box_and_paint_are_refused_in_object_mode(app):
    app.key_press(K4)
    start = _screen(app, (-2.4, -2.4, 0.0))
    _drag(app, _mouse("LEFT"), start, (start[0] + 40, start[1] + 40))
    assert "1/2/3" in app.status_message


def test_stroke_samples_are_spaced():
    points = stroke_samples((0.0, 0.0), (30.0, 0.0), spacing=6.0)
    assert points[-1] == (30.0, 0.0) and len(points) == 5


# -- Tweak ----------------------------------------------------------------------------------


def test_tweak_moves_the_element_under_the_press_point_one_undo_step(app):
    mesh = app.scene.mesh
    app.key_press(K1)
    vid = _vertex(mesh, 0.0, 0.0)
    before = _state(app)
    start = _screen(app, (0.0, 0.0, 0.0))
    _drag(app, _mouse("LEFT", "ctrl"), start, (start[0] + 40, start[1]))
    assert app.status_message.startswith("Move committed")
    assert mesh.vertex_position(vid)[0] > 0.0
    assert app.selection.vertices == set()  # the target was temporary, the selection unchanged
    assert app.key_press(CTRL_Z) is True
    assert _state(app) == before


def test_tweak_uses_the_selection_anywhere_and_the_last_wer(app):
    mesh = app.scene.mesh
    app.key_press(K1)
    picked = {_vertex(mesh, 1.0, 1.0), _vertex(mesh, 2.0, 2.0)}
    app.selection.vertices = set(picked)
    app.key_press(E)
    app.key_release(E)
    assert app.tweak_command == cmd.ROTATE
    empty = _screen(app, (-2.4, 2.4, 0.0))  # nowhere near the selection
    _drag(app, _mouse("LEFT", "ctrl"), empty, (empty[0] + 60, empty[1] + 20))
    assert app.status_message.startswith("Rotate committed")
    assert app.selection.vertices == picked


def test_tweak_esc_cancels_and_the_rest_of_the_drag_does_nothing(app):
    app.key_press(K1)
    before = _state(app)
    start = _screen(app, (0.0, 0.0, 0.0))
    app.pointer_motion(*start)
    app.pointer_press(_mouse("LEFT", "ctrl"), *start)
    app.pointer_drag(20, 0, start[0] + 20, start[1])
    assert app.interaction_owner == "transform"
    assert app.key_press(ESC) is True
    app.pointer_drag(20, 0, start[0] + 40, start[1])
    assert app.interaction_owner is None
    app.pointer_release("LEFT", start[0] + 40, start[1])
    assert _state(app) == before
    assert not app.history.can_undo()


def test_ctrl_click_still_removes(app):
    mesh = app.scene.mesh
    app.key_press(K1)
    vid = _vertex(mesh, 0.0, 0.0)
    app.selection.vertices = {vid}
    pos = _screen(app, (0.0, 0.0, 0.0))
    app.pointer_motion(*pos)
    app.pointer_press(_mouse("LEFT", "ctrl"), *pos)
    assert app.pointer_release("LEFT", *pos) is True
    assert app.selection.vertices == set()


def test_tweak_with_nothing_under_the_press_point_does_nothing(app):
    app.key_press(K1)
    before = _state(app)
    empty = _screen(app, (-2.4, 2.4, 0.0))
    _drag(app, _mouse("LEFT", "ctrl"), empty, (empty[0] + 40, empty[1]))
    assert _state(app) == before
    assert "nothing to move" in app.status_message


def test_box_skips_hidden_vertices_while_faces_are_shown():
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.key_press(K1)
    everything = ((2.0, 2.0), (WIDTH - 2.0, HEIGHT - 2.0))
    _drag(app, _mouse("LEFT"), *everything)
    shaded = len(app.selection.vertices)
    assert 0 < shaded < 8  # the far corner is hidden
    app.key_press(_key("d"))
    app.key_press(_key("d"))  # Wireframe: everything is pickable, as with a click
    assert not app.display.show_faces
    _drag(app, _mouse("LEFT"), *everything)
    assert len(app.selection.vertices) == 8
