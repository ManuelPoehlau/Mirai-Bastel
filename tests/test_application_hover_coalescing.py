"""Application: hover coalescing (WP-VIEW-PERF-01 Slice 2, option 5).

Headless (TraceStore). With `coalesce_hover` (the window loop, `src/main.py run`, switches it
on) a plain mouse move or a wheel notch only marks the hover stale; the frame tick
(`update_viewport`) picks once at the latest cursor, and every input that may read the hover
(`key_press`, `pointer_press`, `dispatch_command`) picks it first. Click, Box, Paint and the
Knife hover are not coalesced.

The twin test drives two apps with the same input - one coalescing, one picking per event as
before - and compares hover, selection and Knife preview after every frame tick: the only
difference allowed is *when* the hover is picked (at the tick, i.e. up to one frame later).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from mirai import application as application_module
from mirai.application import Application
from mirai.interaction.input import Input

WIDTH, HEIGHT = 800, 600
_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))  # the OBJ loader (as test_picking_equivalence.py)
_BODY = _EXAMPLES_DIR / "meshes" / "Man_With_Shoes_basemesh.obj"


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


LMB, SHIFT_LMB, ORBIT = _mouse("LEFT"), _mouse("LEFT", "shift"), _mouse("LEFT", "alt")
WHEEL_UP, WHEEL_DOWN = Input("wheel", "UP"), Input("wheel", "DOWN")
K1, K2, K3, C, W, ESC = _key("1"), _key("2"), _key("3"), _key("c"), _key("w"), _key("ESCAPE")


def _app(coalesce: bool) -> Application:
    app = Application()
    if _BODY.is_file():
        app.init_scene("obj", obj_path=_BODY)
    else:
        app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.coalesce_hover = coalesce
    return app


@pytest.fixture
def twins() -> tuple[Application, Application]:
    return _app(False), _app(True)


def _cursor_path(app, n: int) -> list[tuple[float, float]]:
    """`n` points over the mesh: projected vertices plus a small offset (on and next to them)."""
    mesh = app.scene.mesh
    ids = mesh.all_vertex_ids()
    points = []
    for i in range(n):
        vid = ids[(i * 37) % len(ids)]
        x, y = app.camera.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
        points.append((x + (i % 3), y - (i % 2) * 2.0))
    return points


def _state(app) -> tuple:
    s = app.selection
    hovered = s.hovered
    return (s.mode, frozenset(s.vertices), frozenset(s.edges), frozenset(s.faces),
            type(hovered).__name__, hovered)


def _both(twins, action) -> None:
    for app in twins:
        action(app)


def _tick_and_compare(twins) -> None:
    for app in twins:
        app.update_viewport(1 / 60)
    sync, coalesced = twins
    assert _state(coalesced) == _state(sync)
    assert not coalesced._hover_stale
    return coalesced.selection.hovered


def test_default_is_off_and_a_move_picks_at_once():
    app = _app(False)
    assert app.coalesce_hover is False
    x, y = _cursor_path(app, 1)[0]
    assert app.pointer_motion(x, y)
    assert app.selection.hovered is not None


def test_moves_between_two_ticks_pick_once_at_the_latest_cursor(twins, monkeypatch):
    sync, coalesced = twins
    calls = []
    original = application_module.pick_component
    monkeypatch.setattr(application_module, "pick_component",
                        lambda *a, **k: calls.append(a[3:5]) or original(*a, **k))
    path = _cursor_path(sync, 12)
    for start in range(0, len(path), 4):
        calls.clear()
        for x, y in path[start:start + 4]:
            assert coalesced.pointer_motion(x, y) is False  # nothing picked yet
        assert calls == []
        coalesced.update_viewport(1 / 60)
        assert calls == [path[start + 3]]  # one pick, at the last cursor
        for x, y in path[start:start + 4]:
            sync.pointer_motion(x, y)
        assert _state(coalesced) == _state(sync)


def test_hover_in_every_mode_and_after_zoom_bursts_matches(twins):
    path = _cursor_path(twins[0], 24)
    hovers = set()
    for mode_key in (K1, K2, K3):
        _both(twins, lambda app: app.key_press(mode_key))
        _tick_and_compare(twins)
        for i in range(0, len(path), 3):
            for x, y in path[i:i + 3]:
                _both(twins, lambda app: app.pointer_motion(x, y, 1.0, 0.0))
            hovers.add(_tick_and_compare(twins))
            for wheel in (WHEEL_UP, WHEEL_UP, WHEEL_DOWN):
                _both(twins, lambda app: app.pointer_scroll(wheel))
            hovers.add(_tick_and_compare(twins))
    assert len(hovers - {None}) > 10  # not vacuous: the hover moved across elements


def test_a_zoom_notch_only_marks_the_hover_stale(twins, monkeypatch):
    _sync, coalesced = twins
    x, y = _cursor_path(coalesced, 1)[0]
    coalesced.pointer_motion(x, y)
    coalesced.update_viewport(1 / 60)
    calls = []
    original = application_module.pick_component
    monkeypatch.setattr(application_module, "pick_component",
                        lambda *a, **k: calls.append(1) or original(*a, **k))
    for _ in range(5):
        assert coalesced.pointer_scroll(WHEEL_UP)
    assert calls == [] and coalesced._hover_stale
    coalesced.update_viewport(1 / 60)
    assert calls == [1]


def test_click_right_after_a_move_selects_the_same_element(twins):
    """No tick between the move and the click: the press picks the stale hover first, the
    click picks synchronously on the current camera - same selection, same hover."""
    path = _cursor_path(twins[0], 10)
    for x, y in path:
        _both(twins, lambda app: app.pointer_motion(x, y))
        _both(twins, lambda app: app.pointer_scroll(WHEEL_UP))  # the camera changed, too
        _both(twins, lambda app: (app.pointer_press(SHIFT_LMB, x, y), app.pointer_release("LEFT", x, y)))
        sync, coalesced = twins
        assert _state(coalesced) == _state(sync)  # before any tick
        _tick_and_compare(twins)
    assert twins[1].selection.vertices


def test_a_key_that_reads_the_hover_sees_the_current_one(twins):
    """W with nothing selected arms on the hovered element: pressed right after a move (no
    tick), it must arm on the element under the cursor, as without coalescing."""
    x, y = _cursor_path(twins[0], 5)[3]
    _both(twins, lambda app: app.pointer_motion(x, y))
    _both(twins, lambda app: app.key_press(W))
    sync, coalesced = twins
    assert sync.transform_command is not None
    assert coalesced.transform_command == sync.transform_command
    assert coalesced._transform_target == sync._transform_target
    assert coalesced.status_message == sync.status_message
    _both(twins, lambda app: app.key_press(ESC))
    _tick_and_compare(twins)


def test_paint_and_box_select_the_same_elements(twins):
    """Paint samples are picked per drag step (not coalesced); Box at the release."""
    sync, _ = twins
    path = _cursor_path(sync, 8)
    start = path[0]

    def paint(app):
        app.pointer_motion(*start)
        app.pointer_press(LMB, *start)
        px, py = start
        for x, y in path[1:]:
            app.pointer_drag(x - px, y - py, x, y)
            px, py = x, y
        app.pointer_release("LEFT", px, py)

    _both(twins, paint)
    assert sync.selection.vertices
    _tick_and_compare(twins)

    def box(app):
        app.pointer_motion(2.0, 2.0)
        app.pointer_press(LMB, 2.0, 2.0)
        app.pointer_drag(300.0, 200.0, 302.0, 202.0)
        app.pointer_drag(300.0, 200.0, WIDTH - 2.0, HEIGHT - 2.0)
        app.pointer_release("LEFT", WIDTH - 2.0, HEIGHT - 2.0)

    for mode_key in (K1, K2, K3):
        _both(twins, lambda app: app.key_press(mode_key))
        _both(twins, box)
        _tick_and_compare(twins)


def test_orbit_after_a_move_leaves_no_hover_until_the_next_move(twins):
    x, y = _cursor_path(twins[0], 3)[1]
    _both(twins, lambda app: app.pointer_motion(x, y))
    _both(twins, lambda app: (app.pointer_press(ORBIT, x, y), app.pointer_drag(8.0, 0.0, x, y),
                              app.pointer_drag(8.0, 0.0, x, y), app.pointer_release("LEFT", x, y)))
    _tick_and_compare(twins)
    assert twins[1].selection.hovered is None
    _both(twins, lambda app: app.pointer_motion(x + 1.0, y))
    _tick_and_compare(twins)


def test_leaving_the_window_drops_a_stale_hover(twins):
    x, y = _cursor_path(twins[0], 2)[1]
    _both(twins, lambda app: app.pointer_motion(x, y))
    _tick_and_compare(twins)
    _both(twins, lambda app: (app.pointer_motion(x + 2.0, y), app.pointer_leave()))
    _tick_and_compare(twins)
    assert twins[1].selection.hovered is None


def test_knife_hover_is_not_coalesced(twins):
    """During a Knife session a move and a zoom notch update the preview at once, in both apps."""
    _both(twins, lambda app: (app.selection.clear(), app.key_press(K1)))
    _both(twins, lambda app: app.key_press(C))
    sync, coalesced = twins
    assert coalesced.knife_active
    for x, y in _cursor_path(sync, 6):
        _both(twins, lambda app: app.pointer_motion(x, y))
        assert coalesced._knife_target == sync._knife_target
        _both(twins, lambda app: app.pointer_scroll(WHEEL_UP))
        assert coalesced._knife_target == sync._knife_target
        assert not coalesced._hover_stale
    _both(twins, lambda app: app.key_press(ESC))
    _tick_and_compare(twins)
    assert coalesced.selection.mode is SelectionMode.VERTEX
