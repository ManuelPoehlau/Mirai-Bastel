"""Application: Knife face points in Production (WP-KNIFE-01 S3, PROVISIONAL).

Headless, same fixture as `test_application_knife.py` (the framed default cube; faces z = +1, x = +1 and
y = +1 face the camera). A click inside a face is a point of the session's path — previewed with a marker
at the hit and a line from the last point, cut at commit; the session's own interior points snap like its
edge points; closing a shape does not commit; the status line names the S3 refusals and what the commit
joined or dropped. The mesh and the pick cache stay untouched while clicking.
"""

from __future__ import annotations

import math

import tests._bootstrap  # noqa: F401

from mirai.topology.knife_pick import knife_pick
from tests.mesh_invariants import assert_mesh_invariants
from tests.test_application_knife import (  # noqa: F401  (the `app` fixture)
    CTRL_Y,
    CTRL_Z,
    ENTER,
    HEIGHT,
    WIDTH,
    _begin,
    _click,
    _edge,
    _edge_point,
    _edge_screen,
    _history_depths,
    _screen,
    _topology,
    _v,
    app,
)
from viewport.overlay import TOOL_ACTIVE_LAYER, TOOL_PREVIEW_LAYER

FRONT = (4, 5, 6, 7)   # z = +1


def _in_front(app, u: float, w: float):
    """World point inside the front face: (u, w) in [0, 1]^2 across it."""
    mesh = app.scene.mesh
    p4, p5, p6, p7 = (mesh.vertex_position(_v(app, i)) for i in FRONT)
    xs = sorted({p[0] for p in (p4, p5, p6, p7)})
    ys = sorted({p[1] for p in (p4, p5, p6, p7)})
    return (xs[0] + u * (xs[1] - xs[0]), ys[0] + w * (ys[1] - ys[0]), p4[2])


def _face_screen(app, u, w):
    pos = _screen(app, _in_front(app, u, w))
    target = knife_pick(app.camera, app.scene.mesh, *pos, WIDTH, HEIGHT, occlusion=True)
    assert target["kind"] == "face", target
    return pos


def _front_edge(app):
    """The front face's edge 5-6 and the edge 4-7 opposite it."""
    return _edge(app, _v(app, 5), _v(app, 6)), _edge(app, _v(app, 4), _v(app, 7))


def test_hovering_inside_a_face_previews_the_point_and_the_line(app):
    mesh = app.scene.mesh
    _begin(app)
    e56, _e47 = _front_edge(app)
    assert _click(app, _edge_screen(app, e56, 0.5))
    pos = _face_screen(app, 0.4, 0.6)
    app.pointer_motion(*pos)
    data = app.knife_render_data
    hit = knife_pick(app.camera, mesh, *pos, WIDTH, HEIGHT, cache=app._pick_cache, occlusion=True)["position"]
    assert data.prospective_point == hit
    assert data.line_preview == (data.start_point, hit)
    assert app.viewport.tool_point_layers[TOOL_PREVIEW_LAYER] == [hit]


def test_a_bent_cut_through_a_face_is_cut_at_enter_only(app):
    mesh = app.scene.mesh
    before = _topology(mesh)
    generation = app._pick_cache._generation
    n_v, n_f = len(mesh.all_vertex_ids()), len(mesh.all_face_ids())
    _begin(app)
    e56, e47 = _front_edge(app)
    assert _click(app, _edge_screen(app, e56, 0.5))
    assert _click(app, _face_screen(app, 0.5, 0.3))
    assert app.status_message == "Knife: cut (1 path segment)"
    assert [p["kind"] for p in app._knife.path] == ["edge", "face"]
    assert _click(app, _edge_screen(app, e47, 0.5))
    assert len(app.knife_render_data.placed_points) == 3 and len(app.knife_render_data.path_segments) == 2
    assert _topology(mesh) == before and app._pick_cache._generation == generation
    assert app.key_press(ENTER)
    assert app.status_message == ("Knife committed (2 path edges selected); "   # edge -> interior -> edge
                                  "next cut ready - Esc leaves the Knife")       # UX1
    assert len(mesh.all_vertex_ids()) == n_v + 3 and len(mesh.all_face_ids()) == n_f + 1
    assert _history_depths(app) == (1, 0)
    assert_mesh_invariants(mesh, context="bent cut through the front")


def test_closing_a_shape_by_clicking_its_start_does_not_commit(app):
    mesh = app.scene.mesh
    n_f = len(mesh.all_face_ids())
    _begin(app)
    corners = [(0.3, 0.3), (0.7, 0.3), (0.5, 0.7)]
    for u, w in corners:
        assert _click(app, _face_screen(app, u, w))
    first = app._knife.points[0]
    start = _screen(app, first["position"])
    assert app._knife_pick(start[0] + 4.0, start[1]) == {"kind": "point", "pid": first["pid"]}   # snap
    assert _click(app, (start[0] + 4.0, start[1]))
    assert app.status_message == "Knife: shape closed - the next click cuts on from its start (3 path segments)"
    assert app.knife_active and _history_depths(app) == (0, 0)
    assert app._knife.last_point is first
    assert len(app.knife_render_data.path_segments) == 3      # the closing segment is drawn
    assert app.viewport.tool_line_layers[TOOL_ACTIVE_LAYER] == list(app.knife_render_data.path_segments)
    assert app.key_press(CTRL_Z) and len(app._knife.points) == 3
    assert app.key_press(CTRL_Y) and app._knife.last_point is first
    assert app.key_press(ENTER)
    assert app.status_message.startswith("Knife committed (")
    assert len(mesh.all_face_ids()) == n_f + 2                 # the closed-shape stand-in: 3 faces from 1
    assert_mesh_invariants(mesh, context="closed shape in the front")


def test_the_last_click_inside_a_face_is_joined_at_enter_and_the_status_says_so(app):
    _begin(app)
    e56, _e47 = _front_edge(app)
    assert _click(app, _edge_screen(app, e56, 0.5))
    assert _click(app, _face_screen(app, 0.35, 0.6))
    assert app.status_message == "Knife: cut (1 path segment)"   # no announcement while cutting
    assert app.key_press(ENTER)
    assert app.status_message == ("Knife committed (2 path edges selected); "
                                  "1 last point(s) inside a face joined to the nearest corner; "
                                  "next cut ready - Esc leaves the Knife")       # UX1


def test_a_lone_interior_click_commits_nothing_and_says_why(app):
    before = _topology(app.scene.mesh)
    _begin(app)
    assert _click(app, _face_screen(app, 0.5, 0.5))
    assert app.status_message == "Knife: start point set"
    assert app.key_press(ENTER)
    assert app.status_message == ("Knife: no cuts made, nothing committed "
                                  "(1 shape(s) inside a face with fewer than 3 points dropped)"
                                  " - Knife still active, Esc leaves")            # UX1
    assert _topology(app.scene.mesh) == before and _history_depths(app) == (0, 0)


def test_refusals_name_the_s3_reasons(app, monkeypatch):
    _begin(app)
    for u, w in ((0.3, 0.3), (0.7, 0.3)):
        assert _click(app, _face_screen(app, u, w))
    first = app._knife.points[0]
    start = _screen(app, first["position"])
    assert not _click(app, start)
    assert app.status_message == "Knife: closing a shape needs at least 3 points"
    assert _click(app, _face_screen(app, 0.5, 0.7))
    second = _screen(app, app._knife.points[1]["position"])
    assert not _click(app, second)
    assert app.status_message == "Knife: an earlier point inside a face cannot be clicked again (not yet)"
    # A face hit closer than 9 px to an edge (an edge the pick did not return, e.g. hidden): refused.
    near = _face_screen(app, 0.5, 0.5)
    real = app._knife_pick
    monkeypatch.setattr(app, "_knife_pick", lambda x, y: dict(real(x, y), distance_px=5.0))
    assert not _click(app, near)
    assert app.status_message == "Knife: too close to an edge - click on the edge or further inside the face"
    assert app.knife_render_data.prospective_point is None    # no preview for a refused target


def test_a_face_point_snaps_only_within_the_vertex_pick_radius(app):
    _begin(app)
    assert _click(app, _face_screen(app, 0.5, 0.5))
    own = app._knife.points[0]
    sx, sy = _screen(app, own["position"])
    assert app._knife_pick(sx + 10.0, sy) == {"kind": "point", "pid": own["pid"]}
    far = app._knife_pick(sx + 30.0, sy)
    assert far["kind"] == "face" and math.dist(far["position"], own["position"]) > 0.0
