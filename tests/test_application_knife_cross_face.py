"""Application: the Knife across faces and into empty space (WP-KNIFE-01 S4, PROVISIONAL).

Headless, same fixture as `test_application_knife.py` (the framed default cube; faces z = +1, x = +1 and
y = +1 face the camera, the left and back faces are hidden). The live camera, viewport size, the shared
pick cache and the occlusion switch (`display.show_faces`) go to the `KnifeTool` at hover and click time;
a far click is planned across faces (only the visible part is cut). Manu, 2026-10-02: a click outside the
mesh inside a session is a point in space and cuts — the hover line runs to the cursor even over empty
space; after the click only the cuts commit will make are drawn (nothing for the stretch outside, no
marker at the space point); `Enter` commits, a click outside never does. Defaults: decision.md
"WP-KNIFE-01 S4".
"""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401

from mirai.interaction import commands as cmd
from mirai.topology.knife_preview import target_position
from tests.mesh_invariants import assert_mesh_invariants
from tests.test_application_knife import (  # noqa: F401  (the `app` fixture)
    CTRL_Y,
    CTRL_Z,
    ENTER,
    ESC,
    HEIGHT,
    WIDTH,
    _begin,
    _click,
    _edge_point,
    _edge_screen,
    _history_depths,
    _screen,
    _topology,
    _v,
    _vertex_screen,
    app,
)
from tests.test_application_knife_faces import _face_screen
from tests.test_application_knife_pen_lift import (  # noqa: F401  (the `clock` fixture)
    E,
    LIFT,
    _edges,
    _rmb_click,
    _shift_click,
    clock,
)
from viewport.overlay import TOOL_ACTIVE_LAYER, TOOL_PREVIEW_LAYER


FAR_LEFT = (60.0, 300.0)      # left of the cube, outside the mesh
FAR_RIGHT = (760.0, 330.0)    # right of the cube, outside the mesh
CORNER = (5.0, 5.0)


def _outside(app, pos) -> None:
    from mirai.topology.knife_pick import knife_pick

    assert knife_pick(app.camera, app.scene.mesh, *pos, WIDTH, HEIGHT, occlusion=True)["kind"] == "outside", pos


def _space_position(app, pos):
    from mirai.topology.knife_pick import space_point

    return space_point(app.camera, *pos, WIDTH, HEIGHT)


def _crossings(app):
    return [p for p in app._knife.path if p.get("crossing")]


# -- far clicks across faces -----------------------------------------------------------------------------


def test_hover_over_a_far_target_previews_its_crossings_and_the_click_stores_them(app):
    e = _edges(app)
    _begin(app)
    assert _click(app, _edge_screen(app, e["56"], 0.5))                 # front / right edge
    far = _edge_screen(app, e["73"], 0.5)                                 # top / back edge: no shared face
    app.pointer_motion(*far)
    data = app.knife_render_data
    assert data.prospective_point == pytest.approx(_edge_point(app, e["73"], 0.5))
    assert data.line_preview is not None and len(data.prospective_crossings) >= 1
    assert all(p in app.viewport.tool_point_layers[TOOL_PREVIEW_LAYER] for p in data.prospective_crossings)
    planned = list(data.prospective_crossings)
    assert _click(app, far)
    stored = [target_position(app.scene.mesh, p) for p in _crossings(app)]
    assert stored == pytest.approx(planned)
    assert "crossing" in app.status_message
    assert app.key_press(ENTER) and _history_depths(app) == (1, 0)
    assert_mesh_invariants(app.scene.mesh, context="S4 Application far click")


def test_a_face_the_last_point_does_not_touch_is_now_planned_across(app):
    """Before S4 (`test_a_face_the_last_point_does_not_touch_…`): refused. Now the planner crosses the edge."""
    _begin(app)
    assert _click(app, _vertex_screen(app, _v(app, 7)))
    pos = _screen(app, (1.0, 0.0, 0.0))                                   # centre of the right face
    app.pointer_motion(*pos)
    assert app.knife_render_data.prospective_point is not None
    assert _click(app, pos) and len(_crossings(app)) >= 1


def test_the_status_names_hidden_crossings_and_skipped_stretches(app):
    """From the front / right edge to the far left: the line passes over the hidden back corner's edges."""
    e = _edges(app)
    _begin(app)
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    _outside(app, FAR_LEFT)
    assert _click(app, FAR_LEFT)
    plan = app._knife.last_plan
    assert plan.hidden > 0
    assert f"{plan.hidden} hidden crossing(s) not cut" in app.status_message


def test_orbit_between_clicks_keeps_the_placed_cut(app):
    e = _edges(app)
    _begin(app)
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    assert _click(app, _edge_screen(app, e["73"], 0.5))
    placed = app._knife.path
    app.camera.orbit(math.radians(30.0), math.radians(10.0))
    app._camera_changed()
    app.pointer_motion(400.0, 300.0)
    assert app._knife.path == placed


def test_wireframe_shows_and_cuts_what_the_shaded_view_hides(app):
    e = _edges(app)
    _begin(app)
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    app.pointer_motion(*FAR_LEFT)
    shaded = len(app.knife_render_data.prospective_crossings)
    app.key_press(ESC)
    assert app.dispatch_command(cmd.SET_WIREFRAME) and not app.display.show_faces
    _begin(app)
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    app.pointer_motion(*FAR_LEFT)
    assert len(app.knife_render_data.prospective_crossings) > shaded
    assert _click(app, FAR_LEFT) and app._knife.last_plan.hidden == 0


def test_a_double_click_closes_across_faces(app, clock):
    _begin(app)
    for world in ((0.2, 1.0, 0.3), (0.3, 0.2, 1.0), (1.0, 0.3, 0.2)):     # top, front, right interiors
        clock.now += 1.0
        assert _click(app, _screen(app, world))
    clock.now += 0.1
    assert _click(app, _screen(app, (1.0, 0.3, 0.2)))                    # the double-click's second click
    path = app._knife.path
    assert path[-1] == LIFT and any(p.get("reason") == "closed" and p.get("cyclic") for p in path)
    assert "closed" in app.status_message
    assert app.key_press(ENTER) and _history_depths(app) == (1, 0)


def test_a_shift_midpoint_start_then_a_cross_face_segment(app):
    e = _edges(app)
    _begin(app)
    assert _shift_click(app, _edge_screen(app, e["47"], 0.3))
    assert _click(app, _edge_screen(app, e["26"], 0.4))                  # 4-7 and 2-6 share no face: planned
    assert app._knife.path[0]["t"] == 0.5
    assert app.key_press(ENTER) and _history_depths(app) == (1, 0)


# -- points in space ---------------------------------------------------------------------------------------


def test_hover_in_empty_space_without_a_last_point_shows_the_start_marker_at_the_cursor(app):
    _begin(app)
    _outside(app, FAR_LEFT)
    app.pointer_motion(*FAR_LEFT)
    data = app.knife_render_data
    assert data.prospective_point == pytest.approx(_space_position(app, FAR_LEFT))
    assert data.line_preview is None and data.target_edge is None


def test_hover_in_empty_space_draws_the_rubber_band_to_the_cursor(app):
    e = _edges(app)
    _begin(app)
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    app.pointer_motion(*FAR_LEFT)
    data = app.knife_render_data
    space = _space_position(app, FAR_LEFT)
    assert data.prospective_point == pytest.approx(space)
    assert data.line_preview[0] == pytest.approx(_edge_point(app, e["56"], 0.5))
    assert data.line_preview[1] == pytest.approx(space)
    assert tuple(data.line_preview) in app.viewport.tool_line_layers[TOOL_PREVIEW_LAYER]


def test_a_click_in_space_adds_a_point_and_only_the_cuts_stay_drawn(app):
    mesh = app.scene.mesh
    before = _topology(mesh)
    e = _edges(app)
    _begin(app)
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    assert _click(app, FAR_LEFT) is True
    rec = app._knife.path[-1]
    assert rec["kind"] == "space" and rec["position"] == pytest.approx(_space_position(app, FAR_LEFT))
    assert "point in space" in app.status_message
    assert app.knife_active and _history_depths(app) == (0, 0) and _topology(mesh) == before
    data = app.knife_render_data
    space = tuple(rec["position"])
    assert all(space not in seg for seg in data.path_segments)          # nothing for the stretch outside
    assert space not in data.placed_points                               # no marker at the space point
    assert len(data.path_segments) >= 1                                   # the cuts on the cube stay
    assert app.viewport.tool_line_layers[TOOL_ACTIVE_LAYER] == list(data.path_segments)
    app.pointer_motion(*FAR_RIGHT)                                        # the next segment starts at the space point
    assert app.knife_render_data.line_preview[0] == pytest.approx(space)


def test_both_ends_in_space_cut_across_the_cube_and_enter_commits(app):
    mesh = app.scene.mesh
    before = _topology(mesh)
    _begin(app)
    _outside(app, FAR_LEFT)
    _outside(app, FAR_RIGHT)
    assert _click(app, FAR_LEFT) and _click(app, FAR_RIGHT)
    assert len(_crossings(app)) >= 3
    assert app.knife_active                                               # a click outside never commits
    assert app.key_press(ENTER) and not app.knife_active
    assert _history_depths(app) == (1, 0)
    assert_mesh_invariants(mesh, context="S4 Application space to space")
    assert app.key_press(CTRL_Z) and _topology(mesh) == before


def test_a_space_segment_crossing_nothing_says_so_and_commits_nothing(app):
    mesh = app.scene.mesh
    before = _topology(mesh)
    _begin(app)
    assert _click(app, CORNER)
    assert _click(app, (5.0, 590.0))
    assert "crosses nothing" in app.status_message
    assert app.key_press(ENTER)
    assert _history_depths(app) == (0, 0) and _topology(mesh) == before


def test_undo_redo_lift_and_esc_with_a_space_point(app):
    mesh = app.scene.mesh
    before = _topology(mesh)
    e = _edges(app)
    _begin(app)
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    one = app._knife.path
    assert _click(app, FAR_LEFT)
    two = app._knife.path
    assert app.key_press(CTRL_Z) and app._knife.path == one
    assert app.key_press(CTRL_Y) and app._knife.path == two
    assert app.key_press(E) and app._knife.path[-1] == LIFT
    assert _rmb_click(app) is False                                       # nothing to lift
    assert app.key_press(ESC) and not app.knife_active
    assert _topology(mesh) == before and _history_depths(app) == (0, 0)


def test_a_double_click_in_space_after_a_space_start_lifts_and_says_why(app, clock):
    e = _edges(app)
    _begin(app)
    clock.now += 1.0
    assert _click(app, FAR_LEFT)
    clock.now += 1.0
    assert _click(app, _edge_screen(app, e["56"], 0.5))
    clock.now += 1.0
    assert _click(app, _screen(app, (0.3, 1.0, 0.3)))
    clock.now += 1.0
    assert _click(app, FAR_RIGHT)
    clock.now += 0.1
    assert _click(app, FAR_RIGHT)                                         # second click: finish the chain
    assert app._knife.path[-1] == LIFT
    assert "space" in app.status_message and "not closed" in app.status_message


def test_shift_has_no_effect_on_a_space_point(app):
    _begin(app)
    app.set_shift_held(True)
    app.pointer_motion(*FAR_LEFT)
    assert app.knife_render_data.prospective_point == pytest.approx(_space_position(app, FAR_LEFT))
    assert _shift_click(app, FAR_LEFT) and app._knife.path[-1]["kind"] == "space"


def test_the_start_hint_names_far_clicks_outside_clicks_and_enter(app):
    _begin(app)
    hint = app.status_message
    for part in ("outside", "across faces", "Enter = commit", "E / right-click", "Shift+click"):
        assert part in hint, part
