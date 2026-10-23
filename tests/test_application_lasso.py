"""Lasso Select in the production app (2026-10-21, Manu: "Lasso kommt auch in die Production"): while the
Lasso key (Q, `PROVISIONAL`) is held an LMB drag draws a closed outline instead of a Box / Paint stroke -
whatever the press point -, the release selects the elements whose corners all lie inside (as Box, same
occlusion rule); no modifier replaces, Shift adds, Esc discards. Like Box / Paint it is no History step."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.viewport.box_select import (
    elements_in_polygon,
    elements_in_rect,
    point_in_polygon,
    polygon_bounds,
)

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


K1, K2, K3, K4 = _key("1"), _key("2"), _key("3"), _key("4")
Q, W, ESC = _key("q"), _key("w"), _key("ESCAPE")


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
    # Look straight at the grid (+Z), so a screen outline is a world outline.
    app.camera.yaw = 0.0
    app.camera.pitch = 0.0
    app.camera.camera_revision += 1
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _screen(app, x: float, y: float):
    return app.camera.project_to_screen((x, y, 0.0), WIDTH, HEIGHT)


def _vertex(mesh, x: float, y: float):
    (vid,) = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (x, y)]
    return vid


def _stroke(app, inp: Input, outline, *, release: bool = True, steps: int = 6):
    """Press at outline[0], drag through the rest (`steps` motion events per leg), release at the end."""
    app.pointer_motion(*outline[0])
    app.pointer_press(inp, *outline[0])
    px, py = outline[0]
    for (x1, y1) in outline[1:]:
        x0, y0 = px, py
        for i in range(1, steps + 1):
            x = x0 + (x1 - x0) * i / steps
            y = y0 + (y1 - y0) * i / steps
            app.pointer_drag(x - px, y - py, x, y)
            px, py = x, y
    if not release:
        return None
    return app.pointer_release(inp.value, px, py)


def _triangle(app):
    """World triangle whose hypotenuse is x + y = 0.5: the grid points inside are those with x + y <= 0."""
    return [_screen(app, *p) for p in ((-2.5, -2.5), (2.5, -2.0), (-2.0, 2.5))]


# -- binding --------------------------------------------------------------------------------


def test_the_lasso_key_is_bound_and_the_drag_bindings_are_unchanged():
    bindings = build_default_bindings()
    assert bindings.command_for(_key("q")) == cmd.LASSO_ARM
    assert bindings.command_for(Input("drag", "LEFT")) == cmd.SELECT_DRAG
    assert bindings.command_for(Input("drag", "LEFT", frozenset({"shift"}))) == cmd.SELECT_DRAG_ADD


# -- polygon geometry -------------------------------------------------------------------------


def test_point_in_polygon_is_even_odd_and_handles_concave_outlines():
    l_shape = [(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)]
    assert point_in_polygon((0.5, 3.0), l_shape)
    assert point_in_polygon((3.0, 0.5), l_shape)
    assert not point_in_polygon((3.0, 3.0), l_shape)
    bow_tie = [(0, 0), (4, 4), (4, 0), (0, 4)]  # self-crossing: the overlap-free halves count
    assert point_in_polygon((3.0, 2.0), bow_tie)
    assert not point_in_polygon((2.0, 3.5), bow_tie)
    assert polygon_bounds(l_shape) == (0, 0, 4, 4)


@pytest.mark.parametrize("mode_key", [K1, K2, K3])
@pytest.mark.parametrize("occlusion", [False, True])
def test_a_rectangular_lasso_selects_exactly_what_a_box_does(app, mode_key, occlusion):
    app.key_press(mode_key)
    x0, y0 = _screen(app, -1.4, -2.4)
    x1, y1 = _screen(app, 1.6, 0.4)
    rect = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    polygon = [(rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3])]
    args = (app._edit_camera, app.scene.mesh, app.selection.mode)
    kwargs = dict(cache=app._pick_cache, occlusion=occlusion)
    box = elements_in_rect(*args, rect, WIDTH, HEIGHT, **kwargs)
    lasso = elements_in_polygon(*args, polygon, WIDTH, HEIGHT, **kwargs)
    assert box and lasso == box


# -- the gesture ------------------------------------------------------------------------------


def test_lasso_selects_the_vertices_inside_the_outline(app):
    mesh = app.scene.mesh
    app.key_press(K1)
    assert app.key_press(Q) is True
    assert _stroke(app, _mouse("LEFT"), _triangle(app) + [_triangle(app)[0]]) is True
    expected = {_vertex(mesh, x, y) for x in (-2.0, -1.0, 0.0, 1.0, 2.0) for y in (-2.0, -1.0, 0.0, 1.0, 2.0)
                if x + y <= 0}
    assert len(expected) == 15
    assert app.selection.vertices == expected
    assert app.selection_lasso is None
    assert app.status_message == "Lasso: 15 vertices selected"
    assert not app.history.can_undo()


def test_lasso_in_face_mode_needs_all_corners_inside(app):
    app.key_press(K3)
    app.key_press(Q)
    _stroke(app, _mouse("LEFT"), _triangle(app))
    # A quad (c, r) spans x in [c-2, c-1], y in [r-2, r-1]: its far corner has x + y = c + r - 2 <= 0.
    assert len(app.selection.faces) == 6
    assert app.status_message == "Lasso: 6 faces selected"


def test_lasso_replaces_and_shift_lasso_adds(app):
    app.key_press(K1)
    app.key_press(Q)
    around = lambda cx, cy: [  # noqa: E731 - a small square around a grid point
        _screen(app, cx - 0.3, cy - 0.3), _screen(app, cx + 0.3, cy - 0.3),
        _screen(app, cx + 0.3, cy + 0.3), _screen(app, cx - 0.3, cy + 0.3),
    ]
    _stroke(app, _mouse("LEFT"), around(-2.0, -2.0))
    mesh = app.scene.mesh
    assert app.selection.vertices == {_vertex(mesh, -2.0, -2.0)}
    _stroke(app, _mouse("LEFT", "shift"), around(2.0, 2.0))
    assert app.selection.vertices == {_vertex(mesh, -2.0, -2.0), _vertex(mesh, 2.0, 2.0)}
    _stroke(app, _mouse("LEFT"), around(0.0, 0.0))
    assert app.selection.vertices == {_vertex(mesh, 0.0, 0.0)}


def test_lasso_starts_on_the_mesh_too_where_a_plain_drag_would_paint(app):
    app.key_press(K1)
    app.key_press(Q)
    outline = _triangle(app)
    # The press point is on the grid (a plain LMB drag would paint here); the lasso selects nothing until the release.
    _stroke(app, _mouse("LEFT"), outline[:2], release=False)
    assert app.selection.vertices == set()
    assert app.selection_lasso is not None and len(app.selection_lasso) >= 2
    app.pointer_release("LEFT", *outline[1])


def test_the_outline_is_shown_while_dragging_and_esc_discards_it(app):
    app.key_press(K1)
    app.key_press(Q)
    app.selection.set({_vertex(app.scene.mesh, 0.0, 0.0)})
    outline = _triangle(app)
    _stroke(app, _mouse("LEFT"), outline, release=False)
    assert app.selection_lasso[0] == outline[0]
    assert app.key_press(ESC) is True
    assert app.selection_lasso is None
    assert app.status_message == "Lasso cancelled"
    assert app.pointer_release("LEFT", *outline[-1]) is False
    assert app.selection.vertices == {_vertex(app.scene.mesh, 0.0, 0.0)}  # untouched


def test_a_stroke_with_fewer_than_three_outline_points_changes_nothing(app):
    app.key_press(K1)
    app.key_press(Q)
    keep = {_vertex(app.scene.mesh, 1.0, 1.0)}
    app.selection.set(set(keep))
    start = _screen(app, -2.4, -2.4)
    _stroke(app, _mouse("LEFT"), [start, (start[0] + 20, start[1])], steps=1)
    assert app.selection.vertices == keep
    assert app.status_message == "Lasso: draw a closed outline"


# -- the key ----------------------------------------------------------------------------------


def test_letting_go_of_the_lasso_key_gives_the_plain_drag_back(app):
    app.key_press(K1)
    app.key_press(Q)
    assert app.key_release(Q) is True
    assert app.status_message == "Lasso off"
    corner, inner = _screen(app, -2.4, -2.4), _screen(app, 0.2, 0.2)
    app.pointer_motion(*corner)
    app.pointer_press(_mouse("LEFT"), *corner)
    app.pointer_drag(10, 10, corner[0] + 10, corner[1] + 10)
    assert app.selection_lasso is None  # it is a Box now
    assert app.selection_box is not None
    app.pointer_release("LEFT", corner[0] + 10, corner[1] + 10)


def test_the_lasso_key_is_ignored_while_a_transform_key_is_held(app):
    app.key_press(K1)
    app.selection.set({_vertex(app.scene.mesh, 0.0, 0.0)})
    assert app.key_press(W) is True
    assert app.key_press(Q) is False
    app.key_release(W)


def test_lasso_is_refused_in_object_mode_with_a_status_line(app):
    app.key_press(K4)
    app.key_press(Q)
    outline = _triangle(app)
    _stroke(app, _mouse("LEFT"), outline)
    assert app.status_message.startswith("Box/Paint/Lasso:")
    assert app.selection_lasso is None


def test_alt_held_at_the_release_makes_a_lasso_select_through():
    """WP Toolbox Gaps A2 (Manu 2026-10-23): Alt after drawing the outline = through the mesh."""
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.key_press(K1)
    app.key_press(Q)
    outline = [(2.0, 2.0), (WIDTH - 2.0, 2.0), (WIDTH - 2.0, HEIGHT - 2.0), (2.0, HEIGHT - 2.0)]
    _stroke(app, _mouse("LEFT"), outline, release=False)
    hidden_rule = app.selection_through
    app.set_alt_held(True)
    assert hidden_rule is False and app.selection_through is True
    app.pointer_release("LEFT", *outline[-1])
    app.set_alt_held(False)
    assert len(app.selection.vertices) == 8
    assert app.status_message == "Lasso (through): 8 vertices selected"
    app.key_press(Q)  # same outline without Alt: the far corner stays hidden
    _stroke(app, _mouse("LEFT"), outline)
    assert 0 < len(app.selection.vertices) < 8
