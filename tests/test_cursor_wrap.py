"""Cursor wrap: during a transform the pointer leaves the viewport on one side and re-enters on the other
(`mirai.cursor_wrap.CursorWrapper`, wired in `src/main.py`); the gesture must not notice."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from mirai.cursor_wrap import CursorWrapper
from tests.test_application_gizmo import E, K1, W, HEIGHT, WIDTH, _screen, _vertex, app  # noqa: F401
from tests.test_rotate_dial import PIVOT, QUAD, _expected, _forward, _positions, _select_quad


class FakePlatform:
    """Stand-in for pyglet + the OS: like pyglet it computes `dx`/`dy` against the last position IT delivered
    (the platform's, not ours), answers a warp with a motion event at the target (`reply`), and can have events
    queued at the old edge when the warp happens (`stale`)."""

    def __init__(self, app, width, height, reply=True, stale=0):
        self.width, self.height = width, height
        self.app = app
        self.reply, self.stale = reply, stale
        self.fail = False
        self.wrapper = CursorWrapper(self, app, clock=lambda: 0.0)
        self.pos = None  # the platform's last delivered position (its dx base)
        self.true = None  # where the pointer really is (the hand)
        self.queue = []

    def set_mouse_position(self, x, y):
        if self.fail:
            raise NotImplementedError
        old = self.true
        self.true = (x, y)
        self.queue = [("move", old)] * self.stale  # events that were already in flight at the old edge
        if self.reply:
            self.queue.append(("move", (x, y)))
        elif not self.stale:
            self.pos = (x, y)  # silent platform: its dx base follows the warp

    def deliver(self, x, y):
        """One real mouse event at (x, y), then whatever the warp queued."""
        self.true = (x, y)
        self._event(x, y)
        while self.queue:
            _, (qx, qy) = self.queue.pop(0)
            self._event(qx, qy)

    def _event(self, x, y):
        dx, dy = (x - self.pos[0], y - self.pos[1]) if self.pos is not None else (0.0, 0.0)
        self.pos = (x, y)
        step = self.wrapper.filter(x, y, dx, dy)
        if step is None:
            return
        self.app.pointer_motion(x, y, *step)
        self.wrapper.after_event(x, y)


def _select(app, key):
    ids = [_vertex(app.scene.mesh, x, y) for x, y in QUAD]
    app.key_press(K1)
    app.selection.set(set(ids))
    app.viewport.on_selection_changed()
    return ids


@pytest.mark.parametrize("reply,stale", [(True, 0), (True, 3), (False, 0), (False, 2)])
def test_a_move_across_the_edge_equals_the_unwrapped_move(app, reply, stale):
    ids = _select(app, W)
    plat = FakePlatform(app, WIDTH, HEIGHT, reply=reply, stale=stale)
    start = (WIDTH - 20.0, 300.0)
    steps = 12
    plat.deliver(*start)
    app.key_press(W)
    x = start[0]
    # The hand keeps moving right by 5 px; after a warp the pointer continues from the new spot.
    wraps = 0
    for _ in range(steps):
        x = plat.true[0] + 5.0
        plat.deliver(x, 300.0)
        wraps += plat.true != (x, 300.0)
    app.key_release(W)
    assert wraps >= 1
    moved = [app.scene.mesh.vertex_position(v) for v in ids]

    app.history.undo()
    app.pointer_motion(*start)
    app.key_press(W)
    for i in range(1, steps + 1):
        app.pointer_motion(start[0] + 5.0 * i, 300.0, 5.0, 0.0)
    app.key_release(W)
    for a, b in zip(moved, [app.scene.mesh.vertex_position(v) for v in ids]):
        assert a == pytest.approx(b, abs=1e-9)


@pytest.mark.parametrize("reply,stale", [(True, 0), (True, 3), (False, 0)])
def test_the_dial_stays_continuous_across_a_wrap(app, reply, stale):
    ids = _select_quad(app, E)
    plat = FakePlatform(app, 430, HEIGHT, reply=reply, stale=stale)  # the circle around x=400 crosses x=430
    centre = _screen(app, PIVOT)
    radius = 110.0

    def point(deg):
        a = math.radians(deg)
        return (centre[0] + radius * math.cos(a), centre[1] + radius * math.sin(a))

    plat.deliver(*point(0.0))
    app.key_press(E)
    prev = point(0.0)
    wraps = 0
    for i in range(1, 37):  # a full ccw turn of the hand
        cur = point(10.0 * i)
        hand = (cur[0] - prev[0], cur[1] - prev[1])
        prev = cur
        at = plat.true
        plat.deliver(at[0] + hand[0], at[1] + hand[1])
        wraps += plat.true != (at[0] + hand[0], at[1] + hand[1])
    app.key_release(E)
    assert wraps >= 1
    for got, want in zip(_positions(app, ids), _expected(QUAD, _forward(app), -2.0 * math.pi)):
        assert got == pytest.approx(want, abs=1e-6)


def test_no_wrap_without_a_running_transform_and_none_after_a_failed_warp(app):
    plat = FakePlatform(app, WIDTH, HEIGHT)
    assert plat.wrapper.after_event(0.0, 300.0) is False and not plat.queue
    _select_quad(app, E)
    app.pointer_motion(300.0, 300.0)
    app.key_press(E)
    plat.fail = True
    assert plat.wrapper.after_event(0.0, 300.0) is False
    plat.fail = False
    assert plat.wrapper.after_event(0.0, 300.0) is False  # switched itself off


def test_stale_events_do_not_wrap_again_and_the_warp_window_expires(app):
    now = [0.0]
    plat = FakePlatform(app, WIDTH, HEIGHT)
    plat.wrapper = CursorWrapper(plat, app, clock=lambda: now[0])
    _select_quad(app, E)
    plat.deliver(WIDTH - 40.0, 300.0)
    app.key_press(E)
    plat.deliver(WIDTH - 1.0, 300.0)  # touches the edge: wrap (reply is swallowed)
    assert plat.wrapper._warp is None and app._cursor[0] < 20
    plat.wrapper._warp = ((5, 300), (WIDTH - 1.0, 300.0), 1.0)
    assert plat.wrapper.filter(WIDTH - 2.0, 300.0, 1.0, 0.0) is None  # a stale event at the old edge
    assert plat.wrapper.after_event(WIDTH - 2.0, 300.0) is False  # and no second warp while one is open
    now[0] = 2.0  # no reply ever came (macOS): the window closes, wrapping works again
    assert plat.wrapper.filter(100.0, 300.0, 1.0, 0.0) is not None
