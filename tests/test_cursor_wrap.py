"""Cursor wrap: during a transform the pointer leaves the viewport on one side and re-enters on the other
(`mirai.cursor_wrap.CursorWrapper`, wired in `src/main.py`); the gesture must not notice."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from mirai.cursor_wrap import CursorWrapper
from tests.test_application_gizmo import E, K1, W, HEIGHT, WIDTH, _screen, _vertex, app  # noqa: F401
from tests.test_rotate_dial import PIVOT, QUAD, _expected, _forward, _positions, _select_quad


class FakeWindow:
    """Stand-in: records the warps and, like a real platform, answers each with a motion event."""

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.warps = []
        self.fail = False

    def set_mouse_position(self, x, y):
        if self.fail:
            raise NotImplementedError
        self.warps.append((x, y))


def _event(app, wrapper, window, x, y, dx, dy):
    if wrapper.swallow(x, y):
        return
    app.pointer_motion(x, y, dx, dy)
    wrapper.after_event(x, y)


def test_a_move_across_the_edge_equals_the_unwrapped_move(app):
    ids = [_vertex(app.scene.mesh, x, y) for x, y in QUAD]
    app.key_press(K1)
    app.selection.set(set(ids))
    app.viewport.on_selection_changed()
    window = FakeWindow(WIDTH, HEIGHT)
    wrapper = CursorWrapper(window, app)
    start = (WIDTH - 20.0, 300.0)
    steps = 12
    # With the wrap: after the warp the pointer continues from the left edge with the same deltas.
    app.pointer_motion(*start)
    app.key_press(W)
    x, y = start
    wrapped_moves = 0
    for _ in range(steps):
        nx = x + 5.0
        _event(app, wrapper, window, nx, y, 5.0, 0.0)
        x = nx
        if window.warps:
            wrapped_moves += 1
            wx, wy = window.warps.pop(0)
            _event(app, wrapper, window, wx, wy, wx - x, wy - y)  # swallowed
            x, y = wx, wy
    app.key_release(W)
    assert wrapped_moves == 1
    moved = [app.scene.mesh.vertex_position(v) for v in ids]

    app.history.undo()
    app.pointer_motion(*start)
    app.key_press(W)
    for i in range(1, steps + 1):
        app.pointer_motion(start[0] + 5.0 * i, 300.0, 5.0, 0.0)
    app.key_release(W)
    for a, b in zip(moved, [app.scene.mesh.vertex_position(v) for v in ids]):
        assert a == pytest.approx(b, abs=1e-9)


def test_the_dial_stays_continuous_across_a_wrap(app):
    ids = _select_quad(app, E)
    window = FakeWindow(430, HEIGHT)  # the viewport is 800 wide, the pivot sits at x=400: the circle crosses x=430
    wrapper = CursorWrapper(window, app)
    centre = _screen(app, PIVOT)
    radius = 110.0

    def point(deg):
        a = math.radians(deg)
        return (centre[0] + radius * math.cos(a), centre[1] + radius * math.sin(a))

    px, py = point(0.0)
    app.pointer_motion(px, py)
    app.key_press(E)
    wraps = 0
    for i in range(1, 37):  # a full ccw turn
        x, y = point(10.0 * i)
        _event(app, wrapper, window, x, y, x - px, y - py)
        px, py = x, y
        while window.warps:
            wraps += 1
            wx, wy = window.warps.pop(0)
            _event(app, wrapper, window, wx, wy, wx - px, wy - py)  # swallowed
            # the hand continues the same circle: the next deltas are relative to the unwrapped point
            px, py = x, y
    app.key_release(E)
    assert wraps >= 1
    for got, want in zip(_positions(app, ids), _expected(QUAD, _forward(app), -2.0 * math.pi)):
        assert got == pytest.approx(want, abs=1e-6)


def test_no_wrap_without_a_running_transform_and_none_after_a_failed_warp(app):
    window = FakeWindow(WIDTH, HEIGHT)
    wrapper = CursorWrapper(window, app)
    assert wrapper.after_event(0.0, 300.0) is False and not window.warps
    _select_quad(app, E)
    app.pointer_motion(300.0, 300.0)
    app.key_press(E)
    window.fail = True
    assert wrapper.after_event(0.0, 300.0) is False
    window.fail = False
    assert wrapper.after_event(0.0, 300.0) is False  # switched itself off


def test_only_the_event_the_warp_caused_is_swallowed(app):
    window = FakeWindow(WIDTH, HEIGHT)
    wrapper = CursorWrapper(window, app)
    _select_quad(app, E)
    app.pointer_motion(WIDTH - 1.0, 300.0)
    app.key_press(E)
    assert wrapper.after_event(WIDTH - 1.0, 300.0) is True
    target = window.warps[0]
    assert target[0] < 20
    assert wrapper.swallow(*target) is True
    assert wrapper.swallow(*target) is False
