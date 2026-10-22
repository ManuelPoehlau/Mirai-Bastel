"""Gizmo Rotate handles in the production app: the ring is a Blender-style dial (cursor angle on the ring plane,
the grab point follows the cursor), the centre circle is a trackball, the centre circle also frees Move."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from core.operations.transform import rotate_around_axis
from mirai.viewport import gizmo
from mirai.viewport import vecmath as v
from tests.test_application_gizmo import (  # noqa: F401  (app is a fixture)
    E, K1, W, HEIGHT, WIDTH, _drag, _mouse, _screen, _vertex, app,
)

PIVOT = (0.5, 0.5, 0.0)
QUAD = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


def _select_quad(app, key):
    mesh = app.scene.mesh
    ids = [_vertex(mesh, x, y) for x, y in QUAD]
    app.key_press(K1)
    app.selection.set(set(ids))
    app.viewport.on_selection_changed()
    app.key_press(key)
    app.key_release(key)
    return ids


def _positions(app, ids):
    return [app.scene.mesh.vertex_position(i) for i in ids]


def _expected(ids_start, axis, angle):
    return [rotate_around_axis((x, y, 0.0), PIVOT, axis, angle) for x, y in ids_start]


def _ring_cursor(app, axis, angle):
    """Screen point of the z-ring's sample 0 turned by `angle` about `axis` (and the sample itself)."""
    size = gizmo.gizmo_size(app.camera, PIVOT)
    ring = gizmo.axis_ring_positions(PIVOT, axis, size)
    p0 = rotate_around_axis(tuple(ring[0:3]), PIVOT, axis, math.pi / 4)  # clear of the edge-on rings
    p = rotate_around_axis(p0, PIVOT, axis, angle)
    return _screen(app, p), _screen(app, p0)


def _dial_drag(app, axis, total, steps):
    start = _ring_cursor(app, axis, 0.0)[1]
    app.pointer_motion(*start)
    app.pointer_press(_mouse("LEFT"), *start)
    assert app.gizmo_constraint == "z"
    px, py = start
    for i in range(1, steps + 1):
        x, y = _ring_cursor(app, axis, total * i / steps)[0]
        app.pointer_drag(x - px, y - py, x, y)
        px, py = x, y
    app.pointer_release("LEFT", px, py)


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_the_dial_turns_by_the_cursor_angle_about_the_ring_axis(app, sign):
    ids = _select_quad(app, E)
    _dial_drag(app, (0.0, 0.0, 1.0), sign * math.pi / 2, 12)
    for got, want in zip(_positions(app, ids), _expected(QUAD, (0.0, 0.0, 1.0), sign * math.pi / 2)):
        assert got == pytest.approx(want, abs=1e-6)
    assert app.history.can_undo()


def test_the_dial_result_does_not_depend_on_how_the_drag_is_chunked(app):
    ids = _select_quad(app, E)
    _dial_drag(app, (0.0, 0.0, 1.0), 1.2, 3)
    coarse = _positions(app, ids)
    app.history.undo()
    _dial_drag(app, (0.0, 0.0, 1.0), 1.2, 40)
    for a, b in zip(coarse, _positions(app, ids)):
        assert a == pytest.approx(b, abs=1e-6)


def test_the_dial_counts_full_turns(app):
    ids = _select_quad(app, E)
    _dial_drag(app, (0.0, 0.0, 1.0), 2.0 * math.pi + math.pi / 2, 60)
    for got, want in zip(_positions(app, ids), _expected(QUAD, (0.0, 0.0, 1.0), math.pi / 2)):
        assert got == pytest.approx(want, abs=1e-6)


def test_the_dial_undoes_as_one_step(app):
    ids = _select_quad(app, E)
    before = _positions(app, ids)
    _dial_drag(app, (0.0, 0.0, 1.0), 1.0, 10)
    app.history.undo()
    assert _positions(app, ids) == pytest.approx(before)
    assert not app.history.can_undo()


def test_the_centre_circle_is_a_trackball_about_the_frozen_camera_axes(app):
    ids = _select_quad(app, E)
    _, right, up = app.camera.basis()
    centre = _screen(app, PIVOT)
    _drag(app, _mouse("LEFT"), centre, (40.0, 0.0))
    angle = 40.0 * math.pi / 400.0
    for got, want in zip(_positions(app, ids), _expected(QUAD, up, angle)):
        assert got == pytest.approx(want, abs=1e-6)


def test_the_trackball_follows_the_drag_direction(app):
    """Dragging right turns the near side right, dragging up turns it up (what a ball under the cursor does)."""
    forward, right, up = app.camera.basis()
    near = v.scale(forward, -1.0)  # towards the viewer
    for delta, axis_of in (((30.0, 0.0), lambda: up), ((0.0, 30.0), lambda: v.scale(right, -1.0))):
        axis = axis_of()
        moved = v.cross(axis, near)  # direction the near point travels
        want = right if delta[0] else up
        assert v.dot(moved, want) > 0.5
    ids = _select_quad(app, E)
    _drag(app, _mouse("LEFT"), _screen(app, PIVOT), (0.0, 30.0))
    angle = 30.0 * math.pi / 400.0
    for got, want in zip(_positions(app, ids), _expected(QUAD, v.scale(right, -1.0), angle)):
        assert got == pytest.approx(want, abs=1e-6)


def test_the_trackball_is_independent_of_chunking(app):
    ids = _select_quad(app, E)
    centre = _screen(app, PIVOT)
    _drag(app, _mouse("LEFT"), centre, (30.0, 20.0), steps=2)
    coarse = _positions(app, ids)
    app.history.undo()
    _drag(app, _mouse("LEFT"), centre, (30.0, 20.0), steps=30)
    for a, b in zip(coarse, _positions(app, ids)):
        assert a == pytest.approx(b, abs=1e-6)


def test_the_outer_ring_rotates_about_the_view_axis(app):
    ids = _select_quad(app, E)
    forward, right, _ = app.camera.basis()
    r = gizmo.gizmo_size(app.camera, PIVOT) * gizmo.SCREEN_RING_RATIO
    start = _screen(app, v.add(PIVOT, v.scale(right, r)))
    app.pointer_motion(*start)
    app.pointer_press(_mouse("LEFT"), *start)
    assert app.gizmo_constraint is None
    app.pointer_drag(0.0, 0.0, *start)
    quarter = _screen(app, v.add(PIVOT, v.scale(basis_up(app), r)))
    app.pointer_drag(quarter[0] - start[0], quarter[1] - start[1], *quarter)
    app.pointer_release("LEFT", *quarter)
    for got, want in zip(_positions(app, ids), _expected(QUAD, forward, -math.pi / 2)):
        assert got == pytest.approx(want, abs=1e-6)


def basis_up(app):
    return app.camera.basis()[2]


def test_the_centre_circle_frees_a_constrained_move(app):
    ids = _select_quad(app, W)
    app._axis_constraint = "x"
    before = _positions(app, ids)
    _drag(app, _mouse("LEFT"), _screen(app, PIVOT), (30.0, 30.0))
    after = _positions(app, ids)
    shifts = [tuple(a[i] - b[i] for i in range(3)) for a, b in zip(after, before)]
    assert all(s == pytest.approx(shifts[0]) for s in shifts)
    assert abs(shifts[0][0]) > 1e-3 and abs(shifts[0][1]) > 1e-3  # both screen directions


# -- every rotate gesture follows the cursor like the dial (R/E key, Tweak, objects), Shift / Ctrl -----------------

FORWARD_AXIS = "forward"


def _circle(centre, radius, degrees):
    a = math.radians(degrees)
    return (centre[0] + radius * math.cos(a), centre[1] + radius * math.sin(a))


def _hold_e_and_circle(app, a0, a1, steps, *, radius=110.0, before=None):
    """E held, the cursor circles the pivot's screen position from a0 to a1 (degrees, ccw on screen)."""
    centre = _screen(app, PIVOT)
    px, py = _circle(centre, radius, a0)
    app.pointer_motion(px, py)
    if before:
        before()
    assert app.key_press(E)
    for i in range(1, steps + 1):
        x, y = _circle(centre, radius, a0 + (a1 - a0) * i / steps)
        app.pointer_motion(x, y, x - px, y - py)
        px, py = x, y
    return (px, py)


def _forward(app):
    return app.camera.basis()[0]


def test_the_e_key_turns_like_the_dial_cursor_circle_follows(app):
    ids = _select_quad(app, E)
    _hold_e_and_circle(app, 0.0, 90.0, 18)
    app.key_release(E)
    # ccw on screen = clockwise about the view direction (it points away from the viewer)
    for got, want in zip(_positions(app, ids), _expected(QUAD, _forward(app), -math.pi / 2)):
        assert got == pytest.approx(want, abs=1e-6)


def test_tweak_turns_like_the_dial(app):
    ids = _select_quad(app, E)
    centre = _screen(app, PIVOT)
    px, py = _circle(centre, 110.0, 0.0)
    app.pointer_motion(px, py)
    app.pointer_press(_mouse("LEFT", "ctrl"), px, py)
    for i in range(1, 19):
        x, y = _circle(centre, 110.0, 90.0 * i / 18)
        app.pointer_drag(x - px, y - py, x, y)
        px, py = x, y
    app.pointer_release("LEFT", px, py)
    for got, want in zip(_positions(app, ids), _expected(QUAD, _forward(app), -math.pi / 2)):
        assert got == pytest.approx(want, abs=1e-6)


def test_shift_is_precision_and_stays_continuous_when_toggled(app):
    ids = _select_quad(app, E)

    app.set_shift_held(False)
    centre = _screen(app, PIVOT)
    px, py = _circle(centre, 110.0, 0.0)
    app.pointer_motion(px, py)
    app.key_press(E)
    for i in range(1, 19):  # 0 -> 90 degrees at full gain
        x, y = _circle(centre, 110.0, 90.0 * i / 18)
        app.pointer_motion(x, y, x - px, y - py)
        px, py = x, y
    app.set_shift_held(True)
    for i in range(1, 19):  # 90 -> 180 degrees at 0.2
        x, y = _circle(centre, 110.0, 90.0 + 90.0 * i / 18)
        app.pointer_motion(x, y, x - px, y - py)
        px, py = x, y
    app.key_release(E)
    want = -(math.pi / 2 + 0.2 * math.pi / 2)
    for got, exp in zip(_positions(app, ids), _expected(QUAD, _forward(app), want)):
        assert got == pytest.approx(exp, abs=1e-6)


def test_ctrl_snaps_the_turn_to_five_degrees_and_shift_ctrl_to_one(app):
    ids = _select_quad(app, E)
    _hold_e_and_circle(app, 0.0, 17.4, 6, before=lambda: app.set_ctrl_held(True))
    for got, exp in zip(_positions(app, ids), _expected(QUAD, _forward(app), -math.radians(15.0))):
        assert got == pytest.approx(exp, abs=1e-6)
    app.key_release(E)
    app.set_ctrl_held(False)


def test_shift_ctrl_snaps_the_precise_turn_to_one_degree(app):
    ids = _select_quad(app, E)
    app.set_shift_held(True)
    _hold_e_and_circle(app, 0.0, 17.4, 6, before=lambda: app.set_ctrl_held(True))
    # 17.4 degrees of cursor travel at 0.2 = 3.48 degrees -> 3
    for got, exp in zip(_positions(app, ids), _expected(QUAD, _forward(app), -math.radians(3.0))):
        assert got == pytest.approx(exp, abs=1e-6)
    app.key_release(E)
    app.set_ctrl_held(False)
    app.set_shift_held(False)


def test_ctrl_held_from_the_tweak_press_does_not_snap_until_it_is_pressed_again(app):
    ids = _select_quad(app, E)
    centre = _screen(app, PIVOT)
    px, py = _circle(centre, 110.0, 0.0)
    app.pointer_motion(px, py)
    app.set_ctrl_held(True)  # Ctrl+LMB: Ctrl is part of the gesture
    app.pointer_press(_mouse("LEFT", "ctrl"), px, py)
    for i in range(1, 7):
        x, y = _circle(centre, 110.0, 17.4 * i / 6)
        app.pointer_drag(x - px, y - py, x, y)
        px, py = x, y
    free = _positions(app, ids)
    for got, exp in zip(free, _expected(QUAD, _forward(app), -math.radians(17.4))):
        assert got == pytest.approx(exp, abs=1e-6)  # not snapped
    app.set_ctrl_held(False)
    app.set_ctrl_held(True)  # pressed again: snap now (and at once)
    for got, exp in zip(_positions(app, ids), _expected(QUAD, _forward(app), -math.radians(15.0))):
        assert got == pytest.approx(exp, abs=1e-6)
    app.pointer_release("LEFT", px, py)
    app.set_ctrl_held(False)


def test_the_dial_snaps_with_ctrl(app):
    ids = _select_quad(app, E)
    app.set_ctrl_held(True)
    _dial_drag(app, (0.0, 0.0, 1.0), math.radians(33.0), 10)
    for got, exp in zip(_positions(app, ids), _expected(QUAD, (0.0, 0.0, 1.0), math.radians(35.0))):
        assert got == pytest.approx(exp, abs=1e-6)
    app.set_ctrl_held(False)


def test_shift_slows_the_trackball(app):
    ids = _select_quad(app, E)
    _, _, up = app.camera.basis()
    app.set_shift_held(True)
    _drag(app, _mouse("LEFT"), _screen(app, PIVOT), (40.0, 0.0))
    app.set_shift_held(False)
    for got, want in zip(_positions(app, ids), _expected(QUAD, up, 0.2 * 40.0 * math.pi / 400.0)):
        assert got == pytest.approx(want, abs=1e-6)


def test_an_object_rotates_like_the_dial(app):
    from mirai import object_space
    from tests.test_object_transform import FOUR

    app.key_press(FOUR)
    obj = app.scene.edit_object
    app.selection.objects = {obj.id}
    pivot = object_space.to_world(obj, obj.pivot)
    centre = _screen(app, pivot)
    px, py = _circle(centre, 110.0, 0.0)
    before = obj.transform.rotation
    app.pointer_motion(px, py)
    app.key_press(E)
    for i in range(1, 19):
        x, y = _circle(centre, 110.0, 90.0 * i / 18)
        app.pointer_motion(x, y, x - px, y - py)
        px, py = x, y
    app.key_release(E)
    turn = object_space.axis_angle_rotation(_forward(app), -math.pi / 2)
    want = object_space.orthonormalize(object_space.matmul3(turn, before))
    for got_row, want_row in zip(obj.transform.rotation, want):
        assert got_row == pytest.approx(want_row, abs=1e-6)
