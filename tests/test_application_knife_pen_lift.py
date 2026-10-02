"""Application: the Knife's pen lift, double-click, RMB and Shift midpoint snap (WP-KNIFE-01 UX2, PROVISIONAL).

Headless, same fixture as `test_application_knife.py` (the framed default cube; faces z = +1, x = +1 and y = +1
face the camera). Artist decisions (Manu, 2026-10-02): `E` and an `RMB` click end the current chain without
committing (pen lift); a double-click closes the chain and lifts the pen; a click outside the mesh no longer
commits; `Shift`+click on an edge = midpoint snap. Defaults D1–D13: decision.md "WP-KNIFE-01 UX2". The double-click
clock is injected (`Application.knife_clock`), nothing sleeps.
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import KNIFE_CONTEXT
from mirai.topology.knife_pick import knife_pick
from tests.mesh_invariants import assert_mesh_invariants
from tests.test_application_knife import (  # noqa: F401  (the `app` fixture)
    CTRL_Y,
    CTRL_Z,
    ENTER,
    ESC,
    HEIGHT,
    LMB,
    OUTSIDE,
    WIDTH,
    _begin,
    _click,
    _edge,
    _edge_point,
    _edge_screen,
    _history_depths,
    _key,
    _mouse,
    _screen,
    _topology,
    _v,
    _vertex_screen,
    app,
)
from tests.test_application_knife_faces import _face_screen

UX2 = pytest.mark.xfail(strict=True, reason="WP-KNIFE-01 UX2: pen lift not built yet")

E = _key("e")
RMB = _mouse("RIGHT")
SHIFT_LMB = _mouse("LEFT", "shift")
LIFT = {"kind": "break", "reason": "lift"}


class Clock:
    """Injected double-click clock: `now` is what `Application.knife_clock()` returns."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(app) -> Clock:
    c = Clock()
    app.knife_clock = c
    return c


def _rmb_click(app, pos=None, drag: float = 0.0) -> bool:
    pos = pos if pos is not None else (WIDTH / 2, HEIGHT / 2)
    app.pointer_press(RMB, *pos)
    if drag:
        app.pointer_drag(drag, 0.0, pos[0] + drag, pos[1])
    return app.pointer_release("RIGHT", pos[0] + drag, pos[1])


def _lift_with(app, how: str) -> bool:
    return app.key_press(E) if how == "e" else _rmb_click(app)


def _shift_click(app, pos, drag: float = 0.0) -> bool:
    app.pointer_motion(*pos)
    app.pointer_press(SHIFT_LMB, *pos)
    if drag:
        app.pointer_drag(drag, 0.0, pos[0] + drag, pos[1])
    return app.pointer_release("LEFT", pos[0] + drag, pos[1])


def _edges(app):
    """Front (z = +1): 4-7 and 5-6 opposite; top (y = +1): 7-3 and 2-6; 5-6 and 7-3 share no face."""
    v = {i: _v(app, i) for i in range(8)}
    return {name: _edge(app, v[a], v[b]) for name, (a, b) in
            {"47": (4, 7), "56": (5, 6), "73": (7, 3), "26": (2, 6), "45": (4, 5), "67": (6, 7)}.items()}


def _chain_a(app) -> None:
    e = _edges(app)
    assert _click(app, _edge_screen(app, e["47"], 0.5))
    assert _click(app, _edge_screen(app, e["56"], 0.5))


def _vertices_at(mesh, pos) -> int:
    return sum(1 for v in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(v), pos) < 1e-9)


# -- 1 / 11. E and RMB lift ---------------------------------------------------------------------------


@UX2
@pytest.mark.parametrize("how", ["e", "rmb"])
def test_lift_ends_the_chain_without_commit(app, how):
    mesh = app.scene.mesh
    before = _topology(mesh)
    _begin(app)
    _chain_a(app)

    assert _lift_with(app, how) is True

    knife = app._knife
    assert app.knife_active
    assert knife.path[-1] == LIFT and knife.last_point is None and knife.chain_points == []
    assert _history_depths(app) == (0, 0) and _topology(mesh) == before
    assert app.status_message == "Knife: pen lifted - the next click starts a new cut"


@UX2
@pytest.mark.parametrize("how", ["e", "rmb"])
def test_two_chains_with_a_lift_commit_as_one_entry_and_one_undo_reverts_both(app, how):
    mesh = app.scene.mesh
    before = _topology(mesh)
    e = _edges(app)
    _begin(app)
    _chain_a(app)
    far = _edge_screen(app, e["73"], 0.5)
    app.pointer_motion(*far)
    assert app.knife_render_data.prospective_point is None      # no shared face with the last point

    assert _lift_with(app, how)
    assert _click(app, far) and app.status_message.startswith("Knife: start point set")
    assert _click(app, _edge_screen(app, e["26"], 0.5))
    assert app.key_press(ENTER) is True

    assert not app.knife_active
    assert _history_depths(app) == (1, 0)
    assert len(mesh.all_vertex_ids()) == 12 and len(mesh.all_edge_ids()) == 18 and len(mesh.all_face_ids()) == 8
    assert len(app.selection.edges) == 2
    assert_mesh_invariants(mesh, context="after two lifted chains")
    assert app.key_press(CTRL_Z)
    assert _topology(mesh) == before


@UX2
@pytest.mark.parametrize("how", ["e", "rmb"])
def test_lift_with_nothing_to_lift_is_refused(app, how):
    _begin(app)
    assert _lift_with(app, how) is False
    assert app._knife.path == [] and app.status_message == "Knife: nothing to lift"
    _chain_a(app)
    assert _lift_with(app, how)
    path = app._knife.path
    assert _lift_with(app, how) is False
    assert app._knife.path == path and app.status_message == "Knife: nothing to lift"


@UX2
@pytest.mark.parametrize("how", ["e", "rmb"])
def test_ctrl_z_takes_the_lift_back_and_ctrl_y_lifts_again(app, how):
    _begin(app)
    _chain_a(app)
    before_lift = app._knife.path
    assert _lift_with(app, how)
    lifted = app._knife.path

    assert app.key_press(CTRL_Z)
    assert app._knife.path == before_lift and app._knife.last_point is not None
    assert app.knife_render_data.start_point is not None
    assert app.key_press(CTRL_Y)
    assert app._knife.path == lifted
    assert app.key_press(CTRL_Z)
    assert _click(app, _edge_screen(app, _edges(app)["26"], 0.5))
    assert app.key_press(CTRL_Y) is False                         # the click cleared the redo branch
    assert _history_depths(app) == (0, 0)


@UX2
def test_an_rmb_drag_is_no_lift_and_rmb_never_commits_or_cancels(app):
    mesh = app.scene.mesh
    _begin(app)
    assert _rmb_click(app) is False                                # nothing to lift: no commit, no cancel
    assert app.knife_active
    _chain_a(app)
    path = app._knife.path
    assert _rmb_click(app, drag=40.0) is False
    assert app._knife.path == path and app.knife_active
    assert _rmb_click(app) and app.knife_active
    assert _history_depths(app) == (0, 0) and len(mesh.all_face_ids()) == 6


# -- 3. a branch off an earlier own point ----------------------------------------------------------


@UX2
def test_after_a_lift_a_click_on_an_earlier_own_point_starts_the_new_chain_there(app):
    mesh = app.scene.mesh
    e = _edges(app)
    _begin(app)
    _chain_a(app)
    shared = app._knife.points[1]
    assert app.key_press(E)
    assert _click(app, _edge_screen(app, e["56"], 0.5))           # snaps to the own point
    assert app._knife.path[-1] is shared and app._knife.last_point is shared
    assert _click(app, _edge_screen(app, e["26"], 0.5))
    assert app.key_press(ENTER)
    assert _vertices_at(mesh, _edge_point(app, e["56"], 0.5)) == 1
    assert _history_depths(app) == (1, 0)
    assert_mesh_invariants(mesh, context="after a branch")


# -- 7. double-click ----------------------------------------------------------------------------------


@UX2
def test_a_double_click_on_a_third_point_closes_the_chain_and_lifts(app, clock):
    _begin(app)
    p1, p2, p3 = (_face_screen(app, u, w) for u, w in ((0.3, 0.3), (0.7, 0.3), (0.5, 0.7)))
    assert _click(app, p1)
    clock.now += 1.0
    assert _click(app, p2)
    clock.now += 1.0
    assert _click(app, p3)
    three = app._knife.path
    clock.now += 0.2

    assert _click(app, (p3[0] + 2.0, p3[1] + 1.0)) is True

    knife = app._knife
    assert knife.path == three + [{"kind": "break", "reason": "closed", "cyclic": True}, LIFT]
    assert knife.last_point is None and app.knife_active
    assert app.status_message == "Knife: shape closed, pen lifted - the next click starts a new cut"
    assert app.key_press(CTRL_Z) and knife.path == three        # close + lift = one step
    assert app.key_press(CTRL_Z) and knife.path == three[:2]    # then the third point
    assert _history_depths(app) == (0, 0)


@UX2
def test_a_double_click_on_the_chain_start_closes_with_the_first_click_and_lifts_with_the_second(app, clock):
    _begin(app)
    p1, p2, p3 = (_face_screen(app, u, w) for u, w in ((0.3, 0.3), (0.7, 0.3), (0.5, 0.7)))
    for p in (p1, p2, p3):
        assert _click(app, p)
        clock.now += 1.0
    assert _click(app, p1) and app._knife.last_plan.closing
    closed = app._knife.path
    clock.now += 0.1
    assert _click(app, p1)
    assert app._knife.path == closed[:-1] + [LIFT]
    assert app._knife.last_point is None
    assert app.key_press(ENTER)
    assert _history_depths(app) == (1, 0)


@UX2
def test_a_double_click_with_fewer_than_three_points_only_lifts_and_says_why(app, clock):
    _begin(app)
    e = _edges(app)
    assert _click(app, _edge_screen(app, e["47"], 0.5))
    clock.now += 1.0
    p2 = _edge_screen(app, e["56"], 0.5)
    assert _click(app, p2)
    two = app._knife.path
    clock.now += 0.1
    assert _click(app, p2)
    assert app._knife.path == two + [LIFT]
    assert app.status_message.startswith("Knife: pen lifted (not closed: closing needs at least 3 points)")


@pytest.mark.parametrize("dt, dx", [(0.5, 0.0), (0.1, 10.0)])
def test_a_second_click_outside_the_double_click_window_is_an_ordinary_click(app, clock, dt, dx):
    _begin(app)
    p1, p2 = _face_screen(app, 0.3, 0.3), _face_screen(app, 0.7, 0.3)
    assert _click(app, p1)
    clock.now += 1.0
    assert _click(app, p2)
    clock.now += dt
    second = (p2[0] + dx, p2[1])
    knife = app._knife
    path = knife.path
    accepted = _click(app, second)
    assert LIFT not in knife.path
    if accepted:
        assert len(knife.path) == len(path) + 1                 # a normal click
    else:
        assert knife.path == path                               # refused as the same point


@UX2
def test_a_triple_click_is_one_double_click_and_one_new_start(app, clock):
    _begin(app)
    e = _edges(app)
    assert _click(app, _edge_screen(app, e["47"], 0.5))
    clock.now += 1.0
    p2 = _edge_screen(app, e["56"], 0.5)
    assert _click(app, p2)
    clock.now += 0.1
    assert _click(app, p2)                                        # double-click: lift
    clock.now += 0.1
    assert _click(app, p2)                                        # a new start (on the own point), no 2nd finish
    assert app._knife.last_plan.start
    assert app._knife.path[-2] == LIFT and app._knife.path[-1] is app._knife.points[1]


def test_a_drag_cannot_be_the_second_click_of_a_double_click(app, clock):
    _begin(app)
    p1, p2 = _face_screen(app, 0.3, 0.3), _face_screen(app, 0.7, 0.3)
    assert _click(app, p1)
    clock.now += 1.0
    assert _click(app, p2)
    path = app._knife.path
    clock.now += 0.1
    app.pointer_press(LMB, *p2)
    app.pointer_drag(20.0, 0.0, p2[0] + 20.0, p2[1])
    assert app.pointer_release("LEFT", p2[0], p2[1]) is False
    assert app._knife.path == path


# -- 8. click outside, Enter, Esc ------------------------------------------------------------------------


@UX2
def test_a_click_outside_the_mesh_does_nothing(app):
    mesh = app.scene.mesh
    before = _topology(mesh)
    _begin(app)
    _chain_a(app)
    path = app._knife.path

    assert _click(app, OUTSIDE) is False

    assert app.knife_active and app._knife.path == path
    assert _history_depths(app) == (0, 0) and _topology(mesh) == before
    assert app.status_message == "Knife: outside the mesh: nothing to cut here"
    assert app.knife_render_data.prospective_point is None


@UX2
def test_a_click_outside_on_an_empty_session_keeps_the_knife_active(app):
    _begin(app)
    assert _click(app, OUTSIDE) is False
    assert app.knife_active and app._knife.path == []
    assert app.status_message == "Knife: outside the mesh: nothing to cut here"


def test_enter_still_commits_and_esc_still_cancels(app):
    mesh = app.scene.mesh
    before = _topology(mesh)
    _begin(app)
    _chain_a(app)
    assert app.key_press(ESC) and not app.knife_active
    assert _topology(mesh) == before and _history_depths(app) == (0, 0)
    _begin(app)
    assert app.key_press(ENTER) and not app.knife_active          # empty commit: nothing
    assert _topology(mesh) == before and _history_depths(app) == (0, 0)
    _begin(app)
    _chain_a(app)
    assert app.key_press(ENTER) and not app.knife_active
    assert _history_depths(app) == (1, 0)


@UX2
def test_esc_after_a_lift_restores_mesh_selection_and_history(app):
    mesh = app.scene.mesh
    before = _topology(mesh)
    mode = app.selection.mode
    _begin(app)
    _chain_a(app)
    assert app.key_press(E)
    assert _click(app, _edge_screen(app, _edges(app)["73"], 0.5))
    assert app.key_press(ESC) and not app.knife_active
    assert _topology(mesh) == before and _history_depths(app) == (0, 0)
    assert app.selection.mode is mode and app.selection.is_empty()


@UX2
def test_a_session_of_lifts_only_commits_nothing(app):
    mesh = app.scene.mesh
    before = _topology(mesh)
    _begin(app)
    assert _click(app, _edge_screen(app, _edges(app)["47"], 0.5))
    assert app.key_press(E)
    assert app.key_press(ENTER) and not app.knife_active
    assert _topology(mesh) == before and _history_depths(app) == (0, 0)
    assert app.status_message.startswith("Knife: no cuts made, nothing committed")


# -- 9. bindings ------------------------------------------------------------------------------------------


@UX2
def test_e_and_rmb_are_bound_to_knife_lift_in_the_knife_context_only(app):
    b = app.bindings
    assert b.command_for(E, KNIFE_CONTEXT) == cmd.KNIFE_LIFT
    assert b.command_for(RMB, KNIFE_CONTEXT) == cmd.KNIFE_LIFT
    assert b.command_for(E) == cmd.ROTATE                         # outside a session E stays Rotate
    assert b.command_for(RMB) is None


@UX2
@pytest.mark.parametrize("key", ["w", "r", "1", "d", "c", "x"])
def test_the_session_gate_still_ignores_other_keys(app, key):
    _begin(app)
    _chain_a(app)
    path = app._knife.path
    assert app.key_press(_key(key)) is False
    assert app._knife.path == path and app.knife_active
    assert app.key_press(E) is True


@UX2
def test_knife_lift_is_rebindable_through_keymap_json():
    data = {
        "schemaVersion": 1,
        "bindings": [
            {"context": "knife", "input": {"kind": "key", "value": "q"}, "command": "KnifeLift"},
            {"context": "knife", "input": {"kind": "key", "value": "e"}, "command": None},
            {"context": "knife", "input": {"kind": "mouse", "value": "RIGHT"}, "command": None},
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "keymap.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        app = Application(keymap_path=path)
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    _begin(app)
    _chain_a(app)
    assert app.key_press(E) is False and _rmb_click(app) is False
    assert app._knife.last_point is not None
    assert app.key_press(_key("q")) is True and app._knife.last_point is None


# -- 10. render data after a lift -------------------------------------------------------------------------


@UX2
def test_render_data_after_a_lift_has_no_rubber_band_and_the_next_start_is_marked(app):
    e = _edges(app)
    _begin(app)
    _chain_a(app)
    assert app.key_press(E)
    far = _edge_screen(app, e["73"], 0.5)
    app.pointer_motion(*far)
    data = app.knife_render_data
    assert data.start_point is None and data.line_preview is None
    assert data.prospective_point is not None                     # a valid start is previewed
    assert len(data.placed_points) == 2 and len(data.path_segments) == 1
    app.pointer_leave()
    assert app._cursor is None
    data = app.knife_render_data
    assert data.start_point is None and data.prospective_point is None
    assert _click(app, far)
    data = app.knife_render_data
    assert data.start_point == _edge_point(app, e["73"], 0.5)
    assert len(data.path_segments) == 1


@UX2
def test_after_a_close_and_a_lift_a_new_cyclic_close_draws_its_own_closing_segment(app, clock):
    """The closing segment of a chain after a lift runs back to *that* chain's start, not the first chain's."""
    _begin(app)
    _chain_a(app)
    assert app.key_press(E)
    pts = [_face_screen(app, u, w) for u, w in ((0.3, 0.6), (0.7, 0.6), (0.5, 0.85))]
    for p in pts:
        clock.now += 1.0
        assert _click(app, p)
    clock.now += 1.0
    assert _click(app, pts[0]) and app._knife.last_plan.cyclic
    segments = app.knife_render_data.path_segments
    knife = app._knife

    def touching(point) -> int:
        pos = knife.point_position(point)
        return sum(1 for s in segments if any(math.dist(end, pos) < 1e-9 for end in s))

    assert len(segments) == 4
    assert touching(knife.points[0]) == 1          # chain A's start: only A's own segment
    assert touching(knife.points[2]) == 2          # chain B's start: its first and its closing segment


# -- 12–15. Shift + click = midpoint snap -------------------------------------------------------------------


@UX2
def test_shift_click_on_an_edge_places_the_point_at_its_midpoint_and_the_cut_passes_through_it(app):
    mesh = app.scene.mesh
    e = _edges(app)
    _begin(app)
    assert _shift_click(app, _edge_screen(app, e["47"], 0.3))
    rec = app._knife.path[-1]
    assert rec["kind"] == "edge" and rec["edge_id"] == e["47"] and rec["t"] == 0.5
    assert _click(app, _edge_screen(app, e["56"], 0.3))             # plain click: unchanged
    assert app._knife.path[-1]["t"] == pytest.approx(0.3, abs=0.02)
    mid = _edge_point(app, e["47"], 0.5)
    assert app.key_press(ENTER)
    assert _vertices_at(mesh, mid) == 1
    assert_mesh_invariants(mesh, context="after a midpoint cut")


@UX2
def test_shift_click_on_a_vertex_or_inside_a_face_is_a_plain_click(app):
    _begin(app)
    v7 = _v(app, 7)
    assert _shift_click(app, _vertex_screen(app, v7))
    assert app._knife.path[-1] == {"kind": "vertex", "vertex_id": v7, "pid": app._knife.path[-1]["pid"]}
    assert app.key_press(E)
    pos = _face_screen(app, 0.4, 0.6)
    hit = knife_pick(app.camera, app.scene.mesh, *pos, WIDTH, HEIGHT, cache=app._pick_cache, occlusion=True)
    assert _shift_click(app, pos)
    assert app._knife.path[-1]["kind"] == "face"
    assert app._knife.path[-1]["position"] == tuple(hit["position"])


@UX2
def test_shift_click_near_an_own_edge_point_reaches_that_point(app):
    e = _edges(app)
    _begin(app)
    assert _click(app, _edge_screen(app, e["47"], 0.3))
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    own = app._knife.points[0]
    n = len(app._knife.points)
    assert app.key_press(E)
    assert _shift_click(app, _edge_screen(app, e["47"], 0.3))       # own point first, no midpoint
    assert app._knife.path[-1] is own and len({p["pid"] for p in app._knife.points}) == n


@UX2
def test_shift_click_at_the_midpoint_of_an_edge_carrying_an_own_midpoint_reaches_that_point(app):
    e = _edges(app)
    _begin(app)
    assert _shift_click(app, _edge_screen(app, e["47"], 0.2))
    own = app._knife.path[-1]
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    assert app.key_press(E)
    assert _shift_click(app, _edge_screen(app, e["47"], 0.85))      # far from the own point, same midpoint
    assert app._knife.path[-1] is own


@UX2
def test_shift_click_along_the_last_points_edge_keeps_the_skip_rule(app):
    e = _edges(app)
    _begin(app)
    assert _click(app, _edge_screen(app, e["47"], 0.2))
    assert _shift_click(app, _edge_screen(app, e["47"], 0.8))       # the same edge: a skip, as today
    plan = app._knife.last_plan
    assert plan.skip and app._knife.path[-1]["t"] == 0.5
    assert app._knife.path[-2] == {"kind": "break", "reason": "edge"}


@UX2
def test_shift_lmb_belongs_to_the_knife_alt_and_ctrl_lmb_do_not(app):
    _begin(app)
    pos = _edge_screen(app, _edges(app)["47"], 0.3)
    for mods in (("alt",), ("ctrl",), ("ctrl", "shift"), ("alt", "shift")):
        app.pointer_motion(*pos)
        app.pointer_press(_mouse("LEFT", *mods), *pos)
        assert not app._knife_gesture and app.pointer.active   # the pointer gestures have it
        app.pointer_release("LEFT", *pos)
        assert app._knife.path == []
    assert _shift_click(app, pos) and len(app._knife.path) == 1


def test_a_shift_lmb_drag_past_the_threshold_is_no_cut(app):
    _begin(app)
    pos = _edge_screen(app, _edges(app)["47"], 0.3)
    assert _shift_click(app, pos, drag=20.0) is False
    assert app._knife.path == []


@UX2
def test_the_shift_press_previews_the_midpoint_and_the_plain_hover_the_free_position(app):
    """D10 fallback: the window passes no `Shift` while the mouse only moves (pyglet's key map has no Shift
    key, `mirai.pyglet_input`) — the plain hover shows the free position; the press of `Shift`+`LMB` shows the
    midpoint while the button is held (UX2-f: no live midpoint preview before the press)."""
    e = _edges(app)
    _begin(app)
    pos = _edge_screen(app, e["47"], 0.3)
    app.pointer_motion(*pos)
    free = app.knife_render_data.prospective_point
    assert free == pytest.approx(_edge_point(app, e["47"], 0.3), abs=0.03)
    app.pointer_press(SHIFT_LMB, *pos)
    data = app.knife_render_data
    assert data.prospective_point == pytest.approx(_edge_point(app, e["47"], 0.5))
    assert data.target_edge is not None
    app.pointer_release("LEFT", *pos)
    app.pointer_motion(*pos)
    assert app.knife_render_data.prospective_point == pytest.approx(free)


@UX2
@pytest.mark.parametrize("how", ["e", "rmb"])
def test_midpoint_starts_lift_midpoint_start_enter_one_entry_one_undo(app, how):
    mesh = app.scene.mesh
    before = _topology(mesh)
    e = _edges(app)
    _begin(app)
    assert _shift_click(app, _edge_screen(app, e["47"], 0.3))
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    assert _lift_with(app, how)
    assert _shift_click(app, _edge_screen(app, e["73"], 0.2))
    assert _click(app, _edge_screen(app, e["26"], 0.5))
    assert app.key_press(ENTER)
    assert _vertices_at(mesh, _edge_point(app, e["47"], 0.5)) == 1
    assert _vertices_at(mesh, _edge_point(app, e["73"], 0.5)) == 1
    assert _history_depths(app) == (1, 0)
    assert app.key_press(CTRL_Z) and _topology(mesh) == before


# -- the start hint --------------------------------------------------------------------------------------------


@UX2
def test_the_start_hint_names_the_new_keys_and_no_longer_click_outside(app):
    _begin(app)
    hint = app.status_message
    for part in ("E / right-click", "double-click", "Shift+click", "Enter = commit", "Esc = cancel"):
        assert part in hint, part
    assert "outside" not in hint
