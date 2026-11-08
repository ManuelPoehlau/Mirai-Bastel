"""Dynamic Orbit Focus in the production app (docs/WP_DYNAMIC_ORBIT_FOCUS.md, `PROVISIONAL`): committed
geometric work moves the remembered focus to the area actually worked on; navigation, hover, cancel and
non-geometric steps never do; every orbit path (Alt+LMB, Shift snap, Alt during a transform) turns about it
without moving it on screen; the Working Pivot stays untouched; the morph editing view keeps it."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from core import FaceRegion, FaceRegions, PointLayerInfo, SelectionMode
from mirai import object_space
from mirai.interaction.input import Input
from mirai.pivot import WorkingPivot
from tests.test_application_delete_dissolve import _app, _grid_face, _grid_vertex, _select

V, F = SelectionMode.VERTEX, SelectionMode.FACE
WIDTH, HEIGHT = 800, 600
CENTRE = (WIDTH / 2.0, HEIGHT / 2.0)


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


W, T, DELETE, ESC, TAB, U = _key("w"), _key("t"), _key("delete"), _key("ESCAPE"), _key("tab"), _key("u")
CTRL_Z, CTRL_Y, CTRL_N = _key("z", "ctrl"), _key("y", "ctrl"), _key("n", "ctrl")


def _grid_app(n: int = 4):
    app = _app(n)
    app._focus_tracker.close()  # the grid was loaded into the cube's mesh after `init_scene`
    app._focus_tracker.bind(app.scene.mesh)
    return app


def _screen(app, point):
    return app.camera.project_to_screen(point, WIDTH, HEIGHT)


def _move(app, vertices, steps=((12.0, -7.0), (9.0, 4.0))):
    _select(app, V, set(vertices))
    assert app.key_press(W), app.status_message
    for dx, dy in steps:
        app.pointer_motion(400, 300, dx, dy)
    app.key_release(W)


def _focus_world(app):
    point = app.orbit_focus_world()
    assert point is not None
    return point


def _alt_orbit(app, dx=60.0, dy=25.0, steps=6, shift_at=None):
    app.pointer_motion(*CENTRE)
    app.pointer_press(_mouse("LEFT", "alt"), *CENTRE)
    for i in range(steps):
        if shift_at is not None and i == shift_at:
            app.set_shift_held(True)
        app.pointer_drag(dx / steps, dy / steps, *CENTRE)
    app.set_shift_held(False)
    app.pointer_release("LEFT", *CENTRE)


def _close(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


# -- where the focus comes from ----------------------------------------------------------------------------


def test_a_committed_move_puts_the_focus_on_the_moved_vertices():
    app = _grid_app()
    assert app.orbit_focus is None
    v = _grid_vertex(app, 3, 3)
    _move(app, {v})
    assert app.orbit_focus.object_id == app.scene.edit_object_id
    assert _close(_focus_world(app), app.scene.mesh.vertex_position(v))


def test_navigation_hover_and_the_ortho_toggle_never_move_the_focus():
    app = _grid_app()
    _move(app, {_grid_vertex(app, 1, 1)})
    focus = app.orbit_focus
    _alt_orbit(app)
    app.pointer_press(_mouse("LEFT", "alt", "shift"), *CENTRE)
    app.pointer_drag(20.0, 10.0, *CENTRE)
    app.pointer_release("LEFT", *CENTRE)
    app.pointer_scroll(Input("wheel", "UP", frozenset()))
    app.pointer_motion(300.0, 200.0)
    app.key_press(U)
    assert app.orbit_focus == focus


def test_a_cancelled_move_keeps_the_focus():
    app = _grid_app()
    _move(app, {_grid_vertex(app, 1, 1)})
    focus = app.orbit_focus
    _select(app, V, {_grid_vertex(app, 3, 3)})
    app.key_press(W)
    app.pointer_motion(400, 300, 30.0, 0.0)
    app.key_press(ESC)
    app.key_release(W)
    assert app.orbit_focus == focus


def test_extrude_puts_the_focus_on_the_cap_not_the_base():
    app = _grid_app()
    face = _grid_face(app, 1, 1)
    base = app.scene.mesh
    corners = [base.vertex_position(v) for v in base.face_vertices(face)]
    _select(app, F, {face})
    assert app.key_press(T), app.status_message
    for _ in range(4):
        app.pointer_motion(400, 300, 0.0, 30.0)
    assert app.key_release(T)
    mesh = app.scene.mesh
    caps = [f for f in app.selection.faces]
    cap_points = [mesh.vertex_position(v) for f in caps for v in mesh.face_vertices(f)]
    centre = tuple((min(p[i] for p in cap_points) + max(p[i] for p in cap_points)) / 2 for i in range(3))
    focus = _focus_world(app)
    assert _close(focus, centre)
    assert abs(focus[2] - corners[0][2]) > 1e-3  # off the base plane, on the extruded cap


def test_delete_keeps_the_position_of_what_it_removed():
    app = _grid_app()
    v = _grid_vertex(app, 2, 2)
    where = app.scene.mesh.vertex_position(v)
    _select(app, V, {v})
    assert app.key_press(DELETE), app.status_message
    assert not app.scene.mesh.is_valid_vertex(v)
    assert _close(_focus_world(app), where)


def test_region_tints_and_layers_are_no_worked_area():
    app = _grid_app()
    _move(app, {_grid_vertex(app, 1, 1)})
    focus = app.orbit_focus
    mesh = app.scene.mesh
    face = _grid_face(app, 2, 2)
    assert app.apply_mesh_change("tint", lambda: setattr(
        mesh, "face_regions", FaceRegions((FaceRegion("A", frozenset({face})),))))
    lid_box = []
    assert app.apply_mesh_change("layer", lambda: lid_box.append(mesh.add_point_layer(PointLayerInfo("T"))))
    assert app.orbit_focus == focus


def test_undo_and_redo_move_the_focus_to_where_the_mesh_changed():
    app = _grid_app()
    a, b = _grid_vertex(app, 1, 1), _grid_vertex(app, 3, 3)
    _move(app, {a})
    b_before = app.scene.mesh.vertex_position(b)
    _move(app, {b})
    b_after = app.scene.mesh.vertex_position(b)
    assert app.key_press(CTRL_Z)
    assert _close(_focus_world(app), b_before)
    assert app.orbit_focus.source == "undo"
    assert app.key_press(CTRL_Y)
    assert _close(_focus_world(app), b_after)


# -- the orbit turns about it --------------------------------------------------------------------------------


def test_alt_lmb_orbit_turns_about_the_focus():
    app = _grid_app()
    v = _grid_vertex(app, 4, 4)
    _move(app, {v})
    focus = _focus_world(app)
    target, pixel = app.camera.target, _screen(app, focus)
    _alt_orbit(app)
    assert _close(_screen(app, focus), pixel)
    assert app.camera.target != target


def test_shift_snap_mid_orbit_keeps_the_focus_on_its_pixel():
    app = _grid_app()
    _move(app, {_grid_vertex(app, 4, 0)})
    focus = _focus_world(app)
    pixel = _screen(app, focus)
    app.pointer_motion(*CENTRE)
    app.pointer_press(_mouse("LEFT", "alt"), *CENTRE)
    app.pointer_drag(20.0, 5.0, *CENTRE)
    app.set_shift_held(True)
    assert app.view_name is not None and app.camera.ortho
    assert _close(_screen(app, focus), pixel)
    app.pointer_drag(15.0, 0.0, *CENTRE)
    app.set_shift_held(False)
    assert app.view_name is None
    assert _close(_screen(app, focus), pixel)
    app.pointer_release("LEFT", *CENTRE)


def test_alt_during_a_held_move_orbits_about_the_focus_and_alt_up_ends_it():
    app = _grid_app()
    _move(app, {_grid_vertex(app, 0, 4)})
    focus = _focus_world(app)
    _select(app, V, {_grid_vertex(app, 2, 2)})
    assert app.key_press(W)
    pixel = _screen(app, focus)
    app.set_alt_held(True)
    for _ in range(4):
        app.pointer_motion(400, 300, 15.0, 5.0)
    assert _close(_screen(app, focus), pixel)
    assert app._orbit_anchor is not None
    app.set_alt_held(False)
    assert app._orbit_anchor is None
    app.key_release(W)


def test_without_a_focus_the_orbit_turns_about_the_selection_then_the_target():
    app = _grid_app()
    target = app.camera.target
    _alt_orbit(app)
    assert _close(app.camera.target, target)  # nothing worked, nothing selected: the classic orbit
    v = _grid_vertex(app, 4, 4)
    _select(app, V, {v})
    centre = object_space.to_world(app.scene.edit_object, app.scene.mesh.vertex_position(v))
    pixel = _screen(app, centre)
    _alt_orbit(app)
    assert _close(_screen(app, centre), pixel)


def test_flag_off_is_the_classic_orbit():
    app = _grid_app()
    _move(app, {_grid_vertex(app, 4, 4)})
    app.dynamic_orbit_focus = False
    target = app.camera.target
    _alt_orbit(app)
    assert _close(app.camera.target, target)


def test_the_working_pivot_is_neither_read_nor_moved():
    app = _grid_app()
    pivot = WorkingPivot(app.scene.edit_object_id, (0.5, 0.5, 0.0))
    app._pointer_tools.working_pivot = pivot
    v = _grid_vertex(app, 4, 4)
    _move(app, {v})
    _alt_orbit(app)
    assert app._pointer_tools.working_pivot == pivot
    assert not _close(_focus_world(app), pivot.position)


# -- morph editing view -----------------------------------------------------------------------------------------


def test_work_on_the_morph_view_is_the_focus_and_returns_with_the_base():
    app = _grid_app(3)
    assert app.key_press(CTRL_N), app.status_message
    base = app.scene.edit_object
    assert app.key_press(TAB), app.status_message
    view = app.scene.edit_object
    assert view.id != base.id
    v = _grid_vertex(app, 1, 1)
    _move(app, {v})
    local = app.scene.mesh.vertex_position(v)
    assert app.orbit_focus.object_id == view.id
    assert _close(app.orbit_focus.position, local)
    shift_world = _focus_world(app)
    assert app.key_press(TAB), app.status_message
    assert app.scene.edit_object_id == base.id
    assert app.orbit_focus.object_id == base.id
    back = _focus_world(app)
    # Same local position, now on the base beside which the view stood: shifted like the camera.
    assert _close(back, object_space.to_world(base, local))
    assert not _close(back, shift_world)


def test_switching_the_edit_object_falls_back_until_work_happens_there():
    app = _grid_app()
    _move(app, {_grid_vertex(app, 4, 4)})
    app._orbit_focus = type(app.orbit_focus)(app.orbit_focus.object_id + 1000, app.orbit_focus.position)
    target = app.camera.target
    app.selection.clear()
    _alt_orbit(app)
    assert _close(app.camera.target, target)  # the focus belongs to another object: the classic orbit


def test_object_mode_orbits_about_the_selected_objects():
    app = _grid_app()
    _move(app, {_grid_vertex(app, 4, 4)})  # a component focus exists, but mode 4 works on objects
    assert app.key_press(_key("4")), app.status_message
    obj = app.scene.edit_object
    app.selection.objects = {obj.id}
    centre = object_space.to_world(obj, obj.pivot)
    pixel = _screen(app, centre)
    _alt_orbit(app)
    assert _close(_screen(app, centre), pixel)
