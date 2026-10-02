"""Application: the Knife's live midpoint preview while `Shift` is held (WP-KNIFE-01 UX2b, PROVISIONAL).

Headless, same fixture as `test_application_knife.py` (the framed default cube) and the injected clock of
`test_application_knife_pen_lift.py`. Artist request (Manu, 2026-10-02, UX2 practical-test row 7): the `Shift`
midpoint snap shows in the preview **before** the click. The window layer reports "any Shift held"
(`Application.set_shift_held`); defaults A1–A5: decision.md "WP-KNIFE-01 UX2b". The click keeps deciding by the
press modifiers (A2, AD-019): with `Shift` held, the hover preview is the target a `Shift`+click there produces.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from mirai.application import Application
from tests.test_application_knife import (  # noqa: F401  (the `app` fixture)
    CTRL_Z,
    ENTER,
    ESC,
    HEIGHT,
    LMB,
    WIDTH,
    _begin,
    _click,
    _edge_point,
    _edge_screen,
    _history_depths,
    _topology,
    _v,
    _vertex_screen,
    app,
)
from tests.test_application_knife_faces import _face_screen
from tests.test_application_knife_pen_lift import (  # noqa: F401  (the `clock` fixture)
    E,
    LIFT,
    RMB,
    SHIFT_LMB,
    _edges,
    _rmb_click,
    _shift_click,
    clock,
)

pytestmark = pytest.mark.xfail(strict=True, reason="WP-KNIFE-01 UX2b: spec first, not built yet")

_HEAD = Path(__file__).resolve().parent.parent / "examples" / "meshes" / "head_basemesh.obj"


def _preview(app):
    """(prospective target, highlighted edge, drawn prospective point) of the running session."""
    data = app.knife_render_data
    return app._knife_target, app._knife_highlight_edge, data.prospective_point


def _expected(app, x, y, midpoint):
    """What the click at (x, y) would add: the pick with / without the midpoint, if the session accepts it."""
    target = app._knife_pick(x, y, midpoint=midpoint)
    return target if app._knife.accepts(target) else None


def _strip(entries):
    return [{k: v for k, v in p.items() if k != "pid"} for p in entries]


# -- 1. Shift held over an edge: the midpoint ----------------------------------------------------------------


def test_holding_shift_over_an_edge_previews_its_midpoint_and_releasing_it_the_free_position(app):
    e = _edges(app)
    _begin(app)
    pos = _edge_screen(app, e["47"], 0.3)
    app.pointer_motion(*pos)
    free = _preview(app)
    assert free[0]["t"] == pytest.approx(0.3, abs=0.02)

    assert app.set_shift_held(True) is True
    target, highlight, point = _preview(app)
    assert target["kind"] == "edge" and target["edge_id"] == e["47"] and target["t"] == 0.5
    assert highlight == e["47"] and app.knife_render_data.target_edge is not None
    assert point == pytest.approx(_edge_point(app, e["47"], 0.5))

    assert app.set_shift_held(False) is True
    assert _preview(app)[0] == free[0] and _preview(app)[2] == pytest.approx(free[2])


def test_moving_with_shift_held_keeps_the_midpoint_preview(app):
    e = _edges(app)
    _begin(app)
    app.set_shift_held(True)
    for t in (0.2, 0.35, 0.7):
        app.pointer_motion(*_edge_screen(app, e["56"], t))
        target, highlight, point = _preview(app)
        assert target["edge_id"] == e["56"] and target["t"] == 0.5 and highlight == e["56"]
        assert point == pytest.approx(_edge_point(app, e["56"], 0.5))


# -- 2. Invariant (A2): held-Shift preview == Shift+click target ---------------------------------------------


def _sweep(app, positions):
    """With Shift held: the preview equals `_knife_pick(midpoint=True)` (when accepted) and a Shift+click there
    adds exactly what that target plans; each click is undone again so every position sees the same session."""
    knife = app._knife
    app.set_shift_held(True)
    seen = {"edge": 0, "vertex": 0, "face": 0, "point": 0, "refused": 0}
    for x, y in positions:
        app.pointer_motion(x, y)
        expected = _expected(app, x, y, midpoint=True)
        assert app._knife_target == expected, (x, y)
        if expected is None:
            seen["refused"] += 1
            path = knife.path
            assert _shift_click(app, (x, y)) is False and knife.path == path
            continue
        seen[expected["kind"]] += 1
        planned = _strip(knife.plan(expected).entries)
        n = len(knife.path)
        assert _shift_click(app, (x, y)) is True, (x, y)
        assert _strip(knife.path[n:]) == planned, (x, y)
        assert app.key_press(CTRL_Z) and len(knife.path) == n
    return seen


def _grid(step):
    return [(x, y) for x in range(step // 2, WIDTH, step) for y in range(step // 2, HEIGHT, step)]


@pytest.mark.parametrize("started", [False, True])
def test_shift_held_preview_equals_the_shift_click_target_on_the_cube(app, started):
    _begin(app)
    if started:
        assert _click(app, _edge_screen(app, _edges(app)["47"], 0.4))
    seen = _sweep(app, _grid(23))
    assert seen["edge"] > 0 and seen["vertex"] > 0 and seen["face"] > 0


@pytest.fixture
def head_app() -> Application:
    if not _HEAD.is_file():
        pytest.skip("head basemesh asset missing (examples/meshes/)")
    examples = str(_HEAD.parent.parent)
    if examples not in sys.path:
        sys.path.insert(0, examples)
    app = Application()
    app.init_scene("obj", obj_path=_HEAD)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.knife_clock = itertools.count(0.0, 10.0).__next__
    return app


@pytest.mark.parametrize("started", [False, True])
def test_shift_held_preview_equals_the_shift_click_target_on_a_head_patch(head_app, started):
    app = head_app
    _begin(app)
    patch = [(x, y) for x in range(330, 470, 9) for y in range(230, 370, 9)]
    if started:
        start = next(p for p in patch if app._knife_pick(*p).get("kind") == "edge")
        assert _click(app, start)
        # around the start: the faces it shares, their edges and the refused cross-face targets
        patch = [(start[0] + dx, start[1] + dy) for dx in range(-30, 31, 3) for dy in range(-30, 31, 3)]
    seen = _sweep(app, patch)
    assert seen["edge"] > 10 and seen["face"] + seen["vertex"] > 0
    assert seen["refused"] > 0 if started else True


# -- 3. An own earlier point wins over the midpoint (D9) -----------------------------------------------------


def test_with_shift_held_an_own_point_near_the_midpoint_wins_in_preview_and_click(app):
    e = _edges(app)
    _begin(app)
    assert _click(app, _edge_screen(app, e["47"], 0.46))
    own = app._knife.path[-1]
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    assert app.key_press(E)
    pos = _edge_screen(app, e["47"], 0.5)
    app.pointer_motion(*pos)
    app.set_shift_held(True)
    target = app._knife_target
    assert target == {"kind": "point", "pid": own["pid"]}
    assert _preview(app)[2] == pytest.approx(_edge_point(app, e["47"], 0.46))
    assert _shift_click(app, pos) and app._knife.path[-1] is own


# -- 4. Vertex and face targets: unchanged by Shift ---------------------------------------------------------


def test_with_shift_held_a_vertex_and_a_face_target_are_unchanged(app):
    _begin(app)
    for pos in (_vertex_screen(app, _v(app, 7)), _face_screen(app, 0.4, 0.6)):
        app.set_shift_held(False)
        app.pointer_motion(*pos)
        plain = _preview(app)
        app.set_shift_held(True)
        assert _preview(app)[0] == plain[0] and _preview(app)[1] == plain[1]
        assert plain[0] is not None and plain[0]["kind"] in ("vertex", "face")
    assert _shift_click(app, _vertex_screen(app, _v(app, 7)))
    assert app._knife.path[-1]["kind"] == "vertex"


# -- 5. Without a session: harmless ------------------------------------------------------------------------


def test_without_a_session_shift_held_changes_nothing_and_shift_click_still_adds_to_the_selection(app):
    mesh = app.scene.mesh
    before = (_topology(mesh), app.selection.mode, set(app.selection.vertices), _history_depths(app))
    pos = _vertex_screen(app, _v(app, 7))
    app.pointer_motion(*pos)
    hovered = app.selection.hovered
    app.set_shift_held(True)
    app.set_shift_held(True)
    app.set_shift_held(False)
    app.set_shift_held(True)
    assert not app.knife_active and app.knife_render_data is None
    assert (_topology(mesh), app.selection.mode, set(app.selection.vertices), _history_depths(app)) == before
    assert app.selection.hovered == hovered
    app.selection.add({_v(app, 6)})
    app.pointer_press(SHIFT_LMB, *pos)
    assert app.pointer_release("LEFT", *pos) is True
    assert app.selection.mode == SelectionMode.VERTEX
    assert set(app.selection.vertices) == {_v(app, 6), _v(app, 7)}       # SelectAdd


# -- 6. Shift already held when the session starts ----------------------------------------------------------


def test_a_session_started_with_shift_held_shows_the_midpoint_at_once(app):
    e = _edges(app)
    pos = _edge_screen(app, e["47"], 0.3)
    app.set_shift_held(True)
    app.pointer_motion(*pos)
    _begin(app)
    target, highlight, _ = _preview(app)
    assert target["edge_id"] == e["47"] and target["t"] == 0.5 and highlight == e["47"]


# -- 7. No cursor -------------------------------------------------------------------------------------------


def test_without_a_known_cursor_shift_shows_no_preview(app):
    _begin(app)
    assert app._cursor is None
    assert app.set_shift_held(True) is False
    assert _preview(app)[:2] == (None, None) and app.knife_render_data.prospective_point is None
    app.pointer_motion(*_edge_screen(app, _edges(app)["47"], 0.3))
    app.pointer_leave()
    app.set_shift_held(False)
    assert _preview(app)[:2] == (None, None)


# -- 8. Idempotent -------------------------------------------------------------------------------------------


def test_set_shift_held_is_idempotent(app, monkeypatch):
    _begin(app)
    app.pointer_motion(*_edge_screen(app, _edges(app)["47"], 0.3))
    syncs = []
    original = app._knife_sync_overlay
    monkeypatch.setattr(app, "_knife_sync_overlay", lambda: (syncs.append(1), original())[1])
    assert app.set_shift_held(True) is True
    assert len(syncs) == 1
    assert app.set_shift_held(True) is False         # key repeat / both Shift keys: no recompute
    assert len(syncs) == 1
    assert app.set_shift_held(False) is True and len(syncs) == 2
    assert app.set_shift_held(False) is False and len(syncs) == 2


# -- 9. Everything else unchanged with Shift held / not held --------------------------------------------------


@pytest.mark.parametrize("held", [False, True])
def test_a_plain_click_decides_by_its_press_not_by_the_held_shift(app, held):
    e = _edges(app)
    _begin(app)
    app.set_shift_held(held)
    assert _click(app, _edge_screen(app, e["47"], 0.3))                 # the press carries no Shift
    assert app._knife.path[-1]["t"] == pytest.approx(0.3, abs=0.02)


def test_the_press_preview_stays_fixed_while_the_button_is_held(app):
    e = _edges(app)
    _begin(app)
    pos = _edge_screen(app, e["47"], 0.3)
    app.pointer_motion(*pos)
    app.pointer_press(LMB, *pos)
    pressed = _preview(app)
    app.set_shift_held(True)                                             # Shift after the press: no change
    assert _preview(app)[0] == pressed[0]
    assert app.pointer_release("LEFT", *pos)
    assert app._knife.path[-1]["t"] == pytest.approx(0.3, abs=0.02)
    app.pointer_motion(*_edge_screen(app, e["56"], 0.3))                 # after the release: the held Shift counts
    assert _preview(app)[0]["t"] == 0.5


@pytest.mark.parametrize("held", [False, True])
def test_double_click_rmb_lift_enter_and_esc_are_unchanged(app, clock, held):
    mesh = app.scene.mesh
    before = _topology(mesh)
    v = {i: _v(app, i) for i in range(8)}
    _begin(app)
    app.set_shift_held(held)
    for i in (4, 5, 6):                                                   # the front face's corners
        clock.now += 1.0
        assert _click(app, _vertex_screen(app, v[i]))
    clock.now += 0.1
    assert _click(app, _vertex_screen(app, v[6]))                         # double-click: close + lift
    assert app._knife.path[-1] == LIFT
    assert app.knife_render_data.line_preview is None
    clock.now += 1.0
    assert _click(app, _edge_screen(app, _edges(app)["73"], 0.4))
    clock.now += 1.0
    assert _rmb_click(app) and app._knife.path[-1] == LIFT
    assert app.key_press(ESC) and not app.knife_active
    assert _topology(mesh) == before and _history_depths(app) == (0, 0)
    _begin(app)
    clock.now += 1.0
    assert _click(app, _edge_screen(app, _edges(app)["47"], 0.3))
    clock.now += 1.0
    assert _click(app, _edge_screen(app, _edges(app)["56"], 0.3))
    assert app.key_press(ENTER) and not app.knife_active
    assert _history_depths(app) == (1, 0)
