"""Transform gizmo in the production app (2026-10-21, AD-016 D3, promoted from the Playground): an LMB press on a
handle takes priority over the selection click; a click only sets the axis constraint, click + drag runs the
current tool (the last W/E/R, Move by default) along it and the release commits (one History step), Esc cancels,
a miss falls through. Off unless the host draws it (`Application.gizmo_enabled`)."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.viewport import gizmo

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


K1, K4 = _key("1"), _key("4")
W, E, R, ESC = _key("w"), _key("e"), _key("r"), _key("ESCAPE")


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
    app.camera.yaw = 0.0
    app.camera.pitch = 0.0
    app.camera.camera_revision += 1
    app.set_viewport_size(WIDTH, HEIGHT)
    app.gizmo_enabled = True
    return app


def _vertex(mesh, x: float, y: float):
    (vid,) = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (x, y)]
    return vid


def _screen(app, point):
    return app.camera.project_to_screen(point, WIDTH, HEIGHT)


def _on_handle(app, pivot, direction, fraction=0.6):
    """Screen point on the handle line `direction` of a gizmo at `pivot`."""
    size = gizmo.gizmo_size(app.camera, pivot)
    return _screen(app, tuple(pivot[i] + direction[i] * size * fraction for i in range(3)))


def _drag(app, inp: Input, start, delta, steps: int = 8, *, release: bool = True):
    app.pointer_motion(*start)
    app.pointer_press(inp, *start)
    px, py = start
    for i in range(1, steps + 1):
        x = start[0] + delta[0] * i / steps
        y = start[1] + delta[1] * i / steps
        app.pointer_drag(x - px, y - py, x, y)
        px, py = x, y
    return app.pointer_release(inp.value, px, py) if release else None


def _select_center(app):
    app.key_press(K1)
    vid = _vertex(app.scene.mesh, 0.0, 0.0)
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    return vid, (0.0, 0.0, 0.0)


# -- shown or not -----------------------------------------------------------------------------


def test_the_gizmo_is_off_by_default_so_labs_get_no_invisible_handles():
    plain = Application()
    plain.init_scene("cube")
    plain.key_press(K1)
    plain.selection.set({next(iter(plain.scene.mesh.all_vertex_ids()))})
    assert plain.gizmo_enabled is False
    assert plain.gizmo_items() == []


def test_it_is_shown_for_a_point_edge_or_face_selection_only(app):
    assert app.gizmo_items() == []  # nothing selected
    vid, _ = _select_center(app)
    assert app.gizmo_items()
    app.key_press(K4)  # object mode: no component gizmo, and no object selected
    assert app.gizmo_items() == []


def test_it_follows_the_selection_centroid_and_the_vertex_positions(app):
    vid, pivot = _select_center(app)
    first = app.gizmo_items()[0].positions[:3]
    assert first == pytest.approx(pivot)
    # Move the vertex through the mesh the way an operation does: the cached pivot must follow.
    app.scene.mesh.set_vertex_position(vid, (0.5, 0.25, 0.0))
    app.viewport.on_vertices_moved({vid})
    moved = app.gizmo_items()[0].positions[:3]
    assert moved == pytest.approx((0.5, 0.25, 0.0))


def test_it_takes_the_shape_of_the_current_tool(app):
    _select_center(app)
    assert app.gizmo_tool == "move"
    app.key_press(E)
    app.key_release(E)  # a tap sets the tool (nothing moved, nothing executed)
    assert app.gizmo_tool == "rotate"
    assert all(item.primitive == "loop" for item in app.gizmo_items())
    app.key_press(R)
    app.key_release(R)
    assert app.gizmo_tool == "scale"


def test_it_is_hidden_while_a_transform_key_is_held(app):
    _select_center(app)
    assert app.key_press(W) is True
    assert app.gizmo_items() == []
    app.key_release(W)
    assert app.gizmo_items()


# -- the entry point (AD-016 D3) --------------------------------------------------------------


def test_a_click_on_a_handle_sets_the_constraint_and_does_not_touch_the_selection(app):
    vid, pivot = _select_center(app)
    point = _on_handle(app, pivot, (1.0, 0.0, 0.0))  # x axis; a plain click here would select / clear instead
    app.pointer_motion(*point)
    app.pointer_press(_mouse("LEFT"), *point)
    app.pointer_release("LEFT", *point)
    assert app.gizmo_constraint == "x"
    assert app.selection.vertices == {vid}
    assert not app.history.can_undo()
    assert app.status_message == "Constraint: X"


def test_a_drag_on_a_handle_moves_along_that_axis_and_commits_one_step(app):
    vid, pivot = _select_center(app)
    mesh = app.scene.mesh
    start = _on_handle(app, pivot, (0.0, 1.0, 0.0))
    assert _drag(app, _mouse("LEFT"), start, (0.0, 60.0)) is True
    x, y, z = mesh.vertex_position(vid)
    assert x == pytest.approx(0.0) and z == pytest.approx(0.0)
    assert y != pytest.approx(0.0)
    assert app.gizmo_constraint == "y"
    assert app.selection.vertices == {vid}
    app.history.undo()
    assert mesh.vertex_position(vid) == pytest.approx((0.0, 0.0, 0.0))
    assert not app.history.can_undo()


def test_the_gizmo_is_hidden_while_the_handle_drag_runs(app):
    _, pivot = _select_center(app)
    start = _on_handle(app, pivot, (1.0, 0.0, 0.0))
    _drag(app, _mouse("LEFT"), start, (40.0, 0.0), release=False)
    assert app.gizmo_items() == []
    app.pointer_release("LEFT", start[0] + 40.0, start[1])
    assert app.gizmo_items()


def test_esc_during_a_handle_drag_restores_the_mesh_without_history(app):
    vid, pivot = _select_center(app)
    mesh = app.scene.mesh
    start = _on_handle(app, pivot, (1.0, 0.0, 0.0))
    _drag(app, _mouse("LEFT"), start, (50.0, 0.0), release=False)
    assert mesh.vertex_position(vid) != pytest.approx((0.0, 0.0, 0.0))
    assert app.key_press(ESC) is True
    assert mesh.vertex_position(vid) == pytest.approx((0.0, 0.0, 0.0))
    app.pointer_drag(10.0, 0.0, start[0] + 60.0, start[1])  # the rest of the drag must not re-arm
    app.pointer_release("LEFT", start[0] + 60.0, start[1])
    assert mesh.vertex_position(vid) == pytest.approx((0.0, 0.0, 0.0))
    assert not app.history.can_undo()


def test_the_tool_is_the_last_w_e_r_and_scale_centre_is_the_uniform_handle(app):
    mesh = app.scene.mesh
    quad = [_vertex(mesh, x, y) for x, y in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))]
    app.key_press(K1)
    app.selection.set(set(quad))
    app.viewport.on_selection_changed()
    app.key_press(R)
    app.key_release(R)  # scale becomes the current tool
    assert app.gizmo_tool == "scale"
    pivot = (0.5, 0.5, 0.0)
    app._axis_constraint = "x"  # a stale constraint: the centre handle clears it
    centre = _screen(app, pivot)
    before = [mesh.vertex_position(v) for v in quad]
    assert _drag(app, _mouse("LEFT"), centre, (40.0, 0.0)) is True
    after = [mesh.vertex_position(v) for v in quad]
    assert app.gizmo_constraint is None
    spread = lambda ps: max(p[0] for p in ps) - min(p[0] for p in ps)  # noqa: E731
    spread_y = lambda ps: max(p[1] for p in ps) - min(p[1] for p in ps)  # noqa: E731
    assert spread(after) != pytest.approx(spread(before))
    assert spread_y(after) != pytest.approx(spread_y(before))  # uniform: y scales too


# -- fall-through -----------------------------------------------------------------------------


def test_a_click_that_misses_the_handles_selects_as_usual(app):
    vid, pivot = _select_center(app)
    other = _vertex(app.scene.mesh, 2.0, 2.0)
    point = _screen(app, (2.0, 2.0, 0.0))
    app.pointer_motion(*point)
    app.pointer_press(_mouse("LEFT"), *point)
    app.pointer_release("LEFT", *point)
    assert app.selection.vertices == {other}
    assert app.gizmo_constraint is None


def test_a_press_with_a_modifier_on_a_handle_is_not_taken(app):
    vid, pivot = _select_center(app)
    point = _on_handle(app, pivot, (1.0, 0.0, 0.0), 0.95)
    app.pointer_motion(*point)
    app.pointer_press(_mouse("LEFT", "shift"), *point)
    app.pointer_release("LEFT", *point)
    assert app.gizmo_constraint is None


# -- object level (2026-10-23): mode `4` shows the gizmo at the selected objects ----------------


def _object_selected(app, *, translation=(0.0, 0.0, 0.0)):
    """Mode `4` with one extra Normal object selected; the grid stays the edit object."""
    from core import ObjectTransform

    obj = app.add_primitive("cube", name="box")  # mode 4, selected
    obj.transform = ObjectTransform(translation=translation)
    app._placement_changed()
    return obj


def test_the_object_gizmo_sits_at_the_selected_objects_world_pivot(app):
    assert app.gizmo_items() == []
    obj = _object_selected(app, translation=(2.0, 1.0, 0.0))
    assert app.gizmo_items()[0].positions[:3] == pytest.approx((2.0, 1.0, 0.0))
    app.selection.objects = set()
    assert app.gizmo_items() == []  # nothing selected
    app.selection.objects = {obj.id}
    other = app.add_primitive("sphere", name="ball")
    app.selection.objects = {obj.id, other.id}
    assert app.gizmo_items()[0].positions[:3] == pytest.approx((1.0, 0.5, 0.0))  # centroid of both pivots


def test_the_object_gizmo_is_hidden_for_a_reference_and_during_the_gesture(app):
    ref = app.add_reference("cube", name="guide")
    app.key_press(K4)
    app.selection.objects = {ref.id}
    assert app.gizmo_items() == []  # locked: nothing to drive
    obj = _object_selected(app)
    assert app.gizmo_items()
    app.key_press(W)
    assert app.gizmo_items() == []
    app.key_release(W)
    assert obj.id in app.selection.objects


def test_the_object_gizmo_is_drawn_in_world_even_when_the_edit_object_is_placed(app):
    from core import ObjectTransform

    app.scene.edit_object.transform = ObjectTransform(translation=(5.0, 0.0, 0.0))
    app._placement_changed()
    _object_selected(app)
    assert app.gizmo_items()  # the component gizmo would be hidden for a placed edit object
    assert app.gizmo_camera_uniforms() == app.viewport.render_mesh._camera_uniforms()
    app.key_press(K1)
    assert app.gizmo_items() == []  # components: hidden for the placed edit object, as before


def test_a_handle_drag_moves_the_object_along_the_axis_in_one_undo_step(app):
    obj = _object_selected(app)
    mesh_state = obj.mesh.export_state()
    pivot = (0.0, 0.0, 0.0)
    start = _on_handle(app, pivot, (0.0, 1.0, 0.0))
    depth = len(app.history)
    assert _drag(app, _mouse("LEFT"), start, (0.0, -60.0)) is True
    x, y, z = obj.transform.translation
    assert x == pytest.approx(0.0) and z == pytest.approx(0.0) and y != pytest.approx(0.0)
    assert app.gizmo_constraint == "y"
    assert obj.id in app.selection.objects and app.selection.mode.name == "OBJECT"
    assert len(app.history) == depth + 1
    assert obj.mesh.export_state() == mesh_state  # object level writes the placement only
    app.history.undo()
    assert obj.transform.translation == (0.0, 0.0, 0.0)


def test_esc_during_an_object_handle_drag_restores_the_placement_without_history(app):
    obj = _object_selected(app)
    start = _on_handle(app, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    depth = len(app.history)
    _drag(app, _mouse("LEFT"), start, (50.0, 0.0), release=False)
    assert obj.transform.translation != (0.0, 0.0, 0.0)
    assert app.key_press(ESC) is True
    assert obj.transform.translation == (0.0, 0.0, 0.0)
    app.pointer_release("LEFT", start[0] + 50.0, start[1])
    assert len(app.history) == depth and obj.transform.translation == (0.0, 0.0, 0.0)


def test_a_click_on_an_object_handle_sets_the_constraint_and_keeps_the_object_selection(app):
    obj = _object_selected(app)
    point = _on_handle(app, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    app.pointer_motion(*point)
    app.pointer_press(_mouse("LEFT"), *point)
    app.pointer_release("LEFT", *point)
    assert app.gizmo_constraint == "x"
    assert app.selection.objects == {obj.id}


def test_the_object_gizmo_follows_the_last_tool_scale(app):
    obj = _object_selected(app)
    app.key_press(R)
    app.key_release(R)  # tap: only sets the tool
    assert app.gizmo_tool == "scale"
    start = _on_handle(app, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    _drag(app, _mouse("LEFT"), start, (60.0, 0.0))
    assert obj.transform.scale != pytest.approx(1.0)
