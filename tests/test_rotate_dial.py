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
