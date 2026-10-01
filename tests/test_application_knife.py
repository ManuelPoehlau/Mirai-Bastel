"""Application: Knife session in Production (WP-06 Slice B7 / B7.1, AD-017).

Headless (TraceStore), no pyglet/window. Path: `C` with an empty selection →
`Application._connect_command` → `_knife_begin` → `mirai.topology.knife.
KnifeTool` (the same session engine the Playground imports). Input during a
session: pointer motion = hover preview (Playground Variant A), a click
(press+release under the click threshold) adds the previewed point to the
session's path - a press that moved past the threshold is not a click and
does nothing (WP-KNIFE-01 S2: the mesh is cut at commit, not per click; a
click along an existing edge is a skip, Artist decision AQ1); Enter /
click outside = commit, Esc = cancel, Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z =
in-session undo / redo; navigation keeps working, every other key is gated.
B7.1 (Artist decision Manu 2026-09-28, after the B7 window test): the F1
edge-lock/slide gesture (Playground Variant B) was removed from Production as
redundant with the live hover preview; `project_locked_edge` stays in
`mirai.topology.knife_pick` for the Playground's own Variant B (AD-013 A2).

Fixture: the framed default cube. Seen from the default camera, vertex 6
(1, 1, 1) is the front corner; faces 1 (z = +1), 3 (x = +1) and 4 (y = +1)
face the camera. The main path cuts across those three faces:
vertex 7 → edge 5-6 → edge 2-6 → edge 7-3.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import EdgeId, SelectionMode, VertexId
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.topology.knife_pick import knife_pick
from mirai.topology.knife_preview import build_knife_render_data, target_position
from mirai.viewport import DisplayMode
from tests.mesh_invariants import assert_mesh_invariants
from viewport.overlay import TOOL_ACTIVE_LAYER, TOOL_PREVIEW_LAYER

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


C = _key("c")
ENTER = _key("enter")
ESC = _key("ESCAPE")
CTRL_Z = _key("z", "ctrl")
CTRL_Y = _key("y", "ctrl")
CTRL_SHIFT_Z = _key("z", "ctrl", "shift")
LMB = _mouse("LEFT")
OUTSIDE = (5.0, 5.0)


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


# -- helpers -------------------------------------------------------------------


def _v(app, index: int) -> VertexId:
    """Cube vertex by `scene_factory.create_cube` construction order (0-7)."""
    return sorted(app.scene.mesh.all_vertex_ids(), key=int)[index]


def _edge(app, a: VertexId, b: VertexId) -> EdgeId:
    mesh = app.scene.mesh
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def _screen(app, point) -> tuple[float, float]:
    return app.camera.project_to_screen(point, WIDTH, HEIGHT)


def _edge_point(app, eid: EdgeId, t: float):
    """World point at `t` along `eid` from its first endpoint."""
    return target_position(app.scene.mesh, {"kind": "edge", "edge_id": eid, "t": t})


def _vertex_screen(app, vid) -> tuple[float, float]:
    return _screen(app, app.scene.mesh.vertex_position(vid))


def _edge_screen(app, eid, t: float) -> tuple[float, float]:
    """Screen position of the point at `t`; asserts the knife picks exactly
    that edge there (so the test really exercises the hovered element)."""
    pos = _screen(app, _edge_point(app, eid, t))
    target = knife_pick(app.camera, app.scene.mesh, *pos, WIDTH, HEIGHT)
    assert target["kind"] == "edge" and target["edge_id"] == eid, target
    return pos


def _click(app, pos) -> bool:
    app.pointer_motion(*pos)
    app.pointer_press(LMB, *pos)
    return app.pointer_release("LEFT", *pos)


def _begin(app) -> None:
    app.selection.clear()
    assert app.key_press(C) is True
    assert app.knife_active


def _history_depths(app) -> tuple[int, int]:
    h = app.scene.history
    return (len(h._undo_stack), len(h._redo_stack))


def _topology(mesh) -> dict:
    """`export_state()` without the monotonic ID counters (AD-001, same
    pattern as `tests/test_application_contextual_c.py::_topology`)."""
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}


def _close(a, b, tol=1e-6) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _cut_three_faces(app):
    """vertex 7 → edge 5-6 @0.3 → edge 2-6 @0.5 → edge 7-3 @0.5 (faces 1, 3, 4).
    WP-KNIFE-01 S2: a click adds a point to the session's path and leaves the
    mesh as it is (asserted after every click). Returns the session path
    (`KnifeTool.path`) after each accepted click (index 0 = the start)."""
    mesh = app.scene.mesh
    before = _topology(mesh)
    v2, v3, v5, v6, v7 = (_v(app, i) for i in (2, 3, 5, 6, 7))
    e56, e26, e73 = _edge(app, v5, v6), _edge(app, v2, v6), _edge(app, v7, v3)
    paths = []
    for pos in (
        lambda: _vertex_screen(app, v7),
        lambda: _edge_screen(app, e56, 0.3),
        lambda: _edge_screen(app, e26, 0.5),
        lambda: _edge_screen(app, e73, 0.5),
    ):
        assert _click(app, pos()) is True
        assert _topology(mesh) == before, "the mesh changed during the session"
        paths.append(app._knife.path)
    return paths


def _start_position(app):
    knife = app._knife
    return None if knife.last_point is None else knife.point_position(knife.last_point)


# -- 1. begin / not begin --------------------------------------------------------


@pytest.mark.parametrize("mode", [SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE])
def test_c_with_empty_selection_begins_session(app, mode):
    app.key_press({SelectionMode.VERTEX: _key("1"), SelectionMode.EDGE: _key("2"),
                   SelectionMode.FACE: _key("3")}[mode])
    app.pointer_motion(*_vertex_screen(app, _v(app, 6)))
    before = _topology(app.scene.mesh)

    assert app.key_press(C) is True

    assert app.knife_active
    assert app.selection.hovered is None  # R-SEL-2: the Knife draws its own preview
    assert app.selection.mode is mode
    assert _topology(app.scene.mesh) == before
    assert _history_depths(app) == (0, 0)
    assert app.status_message.startswith("Knife:")


def test_c_with_selection_does_not_begin_session(app):
    app.selection.mode = SelectionMode.EDGE
    app.selection.set({_edge(app, _v(app, 5), _v(app, 6))})

    assert app.key_press(C) is True  # Split

    assert not app.knife_active
    assert app.status_message == "Split"


# -- 2. click path ---------------------------------------------------------------


def test_click_path_vertex_edge_edge_across_three_faces(app):
    mesh = app.scene.mesh
    _begin(app)
    n_vertices = len(mesh.all_vertex_ids())
    n_faces = len(mesh.all_face_ids())

    _cut_three_faces(app)

    knife = app._knife
    assert len(knife.points) == 4 and len(knife.cut_segments) == 3
    assert knife.path_edges == []  # nothing cut yet (S2: the mesh changes at commit)
    # Nothing reached the mesh, the global history or the Selection yet.
    assert len(mesh.all_vertex_ids()) == n_vertices
    assert _history_depths(app) == (0, 0)
    assert app.selection.is_empty()
    last = knife.point_position(knife.last_point)

    assert app.key_press(ENTER) is True

    assert_mesh_invariants(mesh, context="after knife commit")
    assert len(knife.path_edges) == 3
    assert len(mesh.all_vertex_ids()) == n_vertices + 3  # three edge points
    assert len(mesh.all_face_ids()) == n_faces + 3  # three faces cut in two
    # Consecutive path edges share their endpoints: one connected path from v7.
    ends = [set(mesh.edge_vertices(e)) for e in knife.path_edges]
    assert _v(app, 7) in ends[0]
    assert ends[0] & ends[1] and ends[1] & ends[2]
    assert any(_close(mesh.vertex_position(x), last, 1e-9) for x in ends[2])


def test_edge_first_click_sets_the_start_point_without_cutting(app):
    mesh = app.scene.mesh
    before = _topology(mesh)
    _begin(app)
    e56 = _edge(app, _v(app, 5), _v(app, 6))
    point = _edge_point(app, e56, 0.3)

    assert _click(app, _edge_screen(app, e56, 0.3)) is True

    start = app._knife.last_point
    assert start["kind"] == "edge" and start["edge_id"] == e56
    assert _close(_start_position(app), point, 1e-4)
    assert app._knife.cut_segments == []
    assert app.status_message == "Knife: start point set"
    assert _topology(mesh) == before  # no split before commit (S2)


# -- 3. hover preview and line preview ---------------------------------------------


def test_hover_vertex_shows_point_without_line_before_start(app):
    _begin(app)
    v7 = _v(app, 7)

    app.pointer_motion(*_vertex_screen(app, v7))

    data = app.knife_render_data
    assert data.prospective_point == app.scene.mesh.vertex_position(v7)
    assert data.start_point is None
    assert data.line_preview is None
    assert data.target_edge is None
    assert app.viewport.tool_point_layers[TOOL_PREVIEW_LAYER] == [data.prospective_point]
    assert app.viewport.tool_point_layers[TOOL_ACTIVE_LAYER] == []


def test_hover_edge_shows_point_at_t_and_edge_highlight(app):
    _begin(app)
    e56 = _edge(app, _v(app, 5), _v(app, 6))

    app.pointer_motion(*_edge_screen(app, e56, 0.3))

    data = app.knife_render_data
    assert _close(data.prospective_point, _edge_point(app, e56, 0.3), 1e-4)
    mesh = app.scene.mesh
    assert set(data.target_edge) == {mesh.vertex_position(v) for v in mesh.edge_vertices(e56)}
    assert data.line_preview is None  # no start yet
    assert app.viewport.tool_line_layers[TOOL_PREVIEW_LAYER] == [data.target_edge]


def test_line_preview_runs_from_start_to_prospective_point(app):
    _begin(app)
    v7 = _v(app, 7)
    e56 = _edge(app, _v(app, 5), _v(app, 6))
    _click(app, _vertex_screen(app, v7))

    app.pointer_motion(*_edge_screen(app, e56, 0.3))

    data = app.knife_render_data
    start = app.scene.mesh.vertex_position(v7)
    assert data.start_point == start
    assert data.line_preview == (start, data.prospective_point)
    assert _close(data.prospective_point, _edge_point(app, e56, 0.3), 1e-4)
    # Rendered: edge highlight + line in the preview layer, start in the active layer.
    assert app.viewport.tool_line_layers[TOOL_PREVIEW_LAYER] == [data.target_edge, data.line_preview]
    assert app.viewport.tool_point_layers[TOOL_ACTIVE_LAYER] == [start]


def test_line_preview_follows_the_hover(app):
    _begin(app)
    e56 = _edge(app, _v(app, 5), _v(app, 6))
    _click(app, _vertex_screen(app, _v(app, 7)))

    app.pointer_motion(*_edge_screen(app, e56, 0.3))
    first = app.knife_render_data.line_preview
    app.pointer_motion(*_edge_screen(app, e56, 0.6))
    second = app.knife_render_data.line_preview

    assert first[0] == second[0]
    assert _close(second[1], _edge_point(app, e56, 0.6), 1e-4)


def test_start_and_path_stay_drawn_while_hovering_elsewhere(app):
    _begin(app)
    _click(app, _vertex_screen(app, _v(app, 7)))
    _click(app, _edge_screen(app, _edge(app, _v(app, 5), _v(app, 6)), 0.3))
    start = _start_position(app)

    app.pointer_motion(*OUTSIDE)

    data = app.knife_render_data
    assert data.start_point == start
    assert data.path_segments == ((app.scene.mesh.vertex_position(_v(app, 7)), start),)
    assert data.prospective_point is None and data.line_preview is None
    assert app.viewport.tool_line_layers[TOOL_ACTIVE_LAYER] == list(data.path_segments)
    # S2: every placed point is drawn (the mesh has no split vertex to show yet).
    assert app.viewport.tool_point_layers[TOOL_ACTIVE_LAYER] == [
        app.scene.mesh.vertex_position(_v(app, 7)), start,
    ]


# -- 4. click (press → release under the threshold) ----------------------------------


def test_lmb_drag_over_an_edge_neither_locks_nor_cuts(app):
    """B7.1: the F1 edge lock is gone - a press on a valid edge target
    followed by a drag along it does not track the cursor (no slide) and does
    not cut on release; the preview at the press position stays exactly as
    the last hover showed it."""
    mesh = app.scene.mesh
    _begin(app)
    v4, v5, v7 = _v(app, 4), _v(app, 5), _v(app, 7)
    e45 = _edge(app, v4, v5)  # on face 1 with the start v7, not incident to it
    _click(app, _vertex_screen(app, v7))
    before = _topology(mesh)

    press = _edge_screen(app, e45, 0.3)
    app.pointer_motion(*press)
    app.pointer_press(LMB, *press)
    preview_at_press = app.knife_render_data.prospective_point

    along = _screen(app, _edge_point(app, e45, 0.6))
    assert app.pointer_drag(along[0] - press[0], along[1] - press[1], *along) is False
    assert app.knife_render_data.prospective_point == preview_at_press
    assert len(app._knife.points) == 1

    assert app.pointer_release("LEFT", *along) is False

    assert len(app._knife.points) == 1
    assert _topology(mesh) == before
    assert_mesh_invariants(mesh)


def test_line_preview_after_failed_drag_still_follows_hover(app):
    """B7.1 regression: a drag-release that is not a click must not leave the
    line preview stuck - the next hover updates it exactly as in section 3,
    unaffected by the removed slide."""
    mesh = app.scene.mesh
    _begin(app)
    v7 = _v(app, 7)
    _click(app, _vertex_screen(app, v7))
    e56 = _edge(app, _v(app, 5), _v(app, 6))

    press = _edge_screen(app, e56, 0.2)
    app.pointer_motion(*press)
    app.pointer_press(LMB, *press)
    far = _screen(app, _edge_point(app, e56, 0.8))
    app.pointer_drag(far[0] - press[0], far[1] - press[1], *far)
    assert app.pointer_release("LEFT", *far) is False

    app.pointer_motion(*_edge_screen(app, e56, 0.6))

    data = app.knife_render_data
    assert _close(data.prospective_point, _edge_point(app, e56, 0.6), 1e-4)
    assert data.line_preview == (mesh.vertex_position(v7), data.prospective_point)


def test_press_release_without_movement_is_a_click_at_the_hover_position(app):
    _begin(app)
    e56 = _edge(app, _v(app, 5), _v(app, 6))
    _click(app, _vertex_screen(app, _v(app, 7)))
    pos = _edge_screen(app, e56, 0.3)
    app.pointer_motion(*pos)
    hovered = app.knife_render_data.prospective_point

    app.pointer_press(LMB, *pos)
    assert app.pointer_release("LEFT", *pos) is True

    assert _close(_start_position(app), hovered, 1e-9)
    assert len(app._knife.cut_segments) == 1


def test_unlocked_press_drag_release_is_not_a_click(app):
    mesh = app.scene.mesh
    _begin(app)
    pos = _vertex_screen(app, _v(app, 7))  # a vertex: no edge lock
    before = _topology(mesh)

    app.pointer_press(LMB, *pos)
    app.pointer_drag(20, 0, pos[0] + 20, pos[1])
    assert app.pointer_release("LEFT", pos[0] + 20, pos[1]) is False

    assert app._knife.last_point is None
    assert _topology(mesh) == before


# -- 5. in-session undo / redo -------------------------------------------------------


def test_in_session_undo_redo_restores_session_state_and_never_touches_global_history(app):
    mesh = app.scene.mesh
    # A pre-session global entry the in-session Ctrl+Z must not reach.
    app.selection.mode = SelectionMode.EDGE
    app.selection.set({_edge(app, _v(app, 0), _v(app, 1))})
    app.key_press(C)  # Split
    assert _history_depths(app) == (1, 0)
    split_state = _topology(mesh)
    _begin(app)

    paths = _cut_three_faces(app)
    knife = app._knife

    assert app.key_press(CTRL_Z) is True
    assert knife.path == paths[2]
    assert len(knife.cut_segments) == 2
    assert app.knife_render_data.start_point is not None
    assert app.key_press(CTRL_Z) is True
    assert knife.path == paths[1]
    assert app.key_press(CTRL_Y) is True
    assert knife.path == paths[2]
    assert app.key_press(CTRL_SHIFT_Z) is True
    assert knife.path == paths[3]
    assert len(knife.cut_segments) == 3
    assert app.key_press(CTRL_Y) is False  # redo branch empty
    assert app.status_message == "Knife: nothing to redo"

    # Undo every step, then once more: the session never reaches the Split.
    for _ in range(4):
        assert app.key_press(CTRL_Z) is True
    assert knife.last_point is None
    assert app.key_press(CTRL_Z) is False
    assert _topology(mesh) == split_state  # never touched during the session
    assert _history_depths(app) == (1, 0)
    assert_mesh_invariants(mesh)


def test_dispatch_undo_during_session_is_routed_to_the_session(app):
    _begin(app)
    paths = _cut_three_faces(app)

    assert app.dispatch_command(cmd.UNDO) is True

    assert app._knife.path == paths[2]
    assert _history_depths(app) == (0, 0)


def test_undo_redo_ignored_while_the_knife_button_is_held(app):
    _begin(app)
    paths = _cut_three_faces(app)
    pos = _vertex_screen(app, _v(app, 0))
    app.pointer_press(LMB, *pos)

    assert app.key_press(CTRL_Z) is False
    assert app._knife.path == paths[3]


# -- 6. cancel / commit ------------------------------------------------------------


def test_esc_restores_pre_session_mesh_selection_and_history(app):
    mesh = app.scene.mesh
    app.key_press(_key("2"))  # Edge mode, empty selection
    before_mesh = _topology(mesh)
    _begin(app)
    _cut_three_faces(app)

    assert app.key_press(ESC) is True

    assert not app.knife_active
    assert _topology(mesh) == before_mesh
    assert app.selection.mode is SelectionMode.EDGE
    assert app.selection.is_empty()
    assert _history_depths(app) == (0, 0)
    assert app.status_message == "Knife cancelled"
    assert all(not v for v in app.viewport.tool_point_layers.values())
    assert all(not v for v in app.viewport.tool_line_layers.values())


@pytest.mark.parametrize("finish", ["enter", "click_outside"])
def test_commit_pushes_exactly_one_entry_and_selects_the_path(app, finish):
    mesh = app.scene.mesh
    app.key_press(_key("1"))  # Vertex mode before the session
    _begin(app)
    _cut_three_faces(app)
    knife = app._knife

    if finish == "enter":
        assert app.key_press(ENTER) is True
    else:
        assert _click(app, OUTSIDE) is True

    # UX1 (Manu 2026-10-01): the Knife stays active with a fresh session (was: `not knife_active`).
    assert app.knife_active and app._knife.path == []
    assert _history_depths(app) == (1, 0)
    assert app.selection.mode is SelectionMode.EDGE
    assert len(knife.path_edges) == 3
    assert app.selection.edges == set(knife.path_edges)
    assert app.status_message == "Knife committed (3 path edges selected); next cut ready - Esc leaves the Knife"
    assert_mesh_invariants(mesh, context="after knife commit")
    assert all(not v for v in app.viewport.tool_line_layers.values())


def test_commit_without_cuts_pushes_nothing(app):
    _begin(app)
    _click(app, _vertex_screen(app, _v(app, 7)))  # start only, no mutation

    assert app.key_press(ENTER) is True

    # UX1 (Manu 2026-10-01, default A3): an empty commit keeps the Knife (was: `not knife_active`).
    assert app.knife_active and app._knife.path == []
    assert _history_depths(app) == (0, 0)
    assert app.selection.is_empty()
    assert app.status_message == "Knife: no cuts made, nothing committed - Knife still active, Esc leaves"


def test_global_undo_after_commit_restores_mesh_and_selection_redo_restores_residue(app):
    mesh = app.scene.mesh
    app.key_press(_key("3"))  # Face mode, empty selection
    before_topology = _topology(mesh)
    _begin(app)
    _cut_three_faces(app)
    app.key_press(ENTER)
    after_state = _topology(mesh)
    residue = set(app.selection.edges)

    assert app.key_press(CTRL_Z) is True
    assert _topology(mesh) == before_topology
    assert app.selection.mode is SelectionMode.FACE
    assert app.selection.is_empty()
    assert_mesh_invariants(mesh)

    assert app.key_press(CTRL_Y) is True
    assert _topology(mesh) == after_state
    assert app.selection.mode is SelectionMode.EDGE
    assert app.selection.edges == residue
    assert_mesh_invariants(mesh)


# -- 7. session gate / navigation ---------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [_key("w"), _key("e"), _key("r"), _key("1"), _key("2"), _key("3"),
     _key("d"), _key("d", "shift"), _key("c"), _key("x"), _key("z", "shift")],
    ids=lambda k: "+".join(sorted(k.modifiers) + [k.value]),
)
def test_session_gate_ignores_other_keys(app, key):
    _begin(app)
    paths = _cut_three_faces(app)
    mesh_state = _topology(app.scene.mesh)
    mode, display = app.selection.mode, (app.display.mode, app.display.show_edges)
    constraint = app.axis_constraint

    assert app.key_press(key) is False
    app.key_release(key)

    assert app.knife_active
    assert app._knife.path == paths[3]
    assert _topology(app.scene.mesh) == mesh_state
    assert app.selection.mode is mode
    assert (app.display.mode, app.display.show_edges) == display
    assert app.axis_constraint == constraint
    assert app.transform_command is None


def test_enter_and_ctrl_shift_z_do_nothing_outside_a_session(app):
    assert app.key_press(ENTER) is False
    assert app.key_press(CTRL_SHIFT_Z) is False
    assert not app.knife_active


def test_navigation_keeps_working_during_a_session(app):
    _begin(app)
    _click(app, _vertex_screen(app, _v(app, 7)))
    mesh_state = _topology(app.scene.mesh)
    start = app._knife.last_point
    yaw, target, distance = app.camera.yaw, app.camera.target, app.camera.distance

    # Alt+LMB drag = orbit
    app.pointer_press(_mouse("LEFT", "alt"), 400, 300)
    assert app.pointer_drag(30, 0, 430, 300) is True
    app.pointer_release("LEFT", 430, 300)
    assert app.camera.yaw != yaw
    # Alt+Shift+LMB drag = pan
    app.pointer_press(_mouse("LEFT", "alt", "shift"), 400, 300)
    assert app.pointer_drag(0, 30, 400, 330) is True
    app.pointer_release("LEFT", 400, 330)
    assert app.camera.target != target
    # Wheel = zoom
    assert app.pointer_scroll(Input("wheel", "UP")) is True
    assert app.camera.distance != distance

    assert app.knife_active
    assert app._knife.last_point is start
    assert _topology(app.scene.mesh) == mesh_state
    assert app.selection.is_empty()


def test_modified_click_during_session_neither_cuts_nor_selects(app):
    _begin(app)
    pos = _vertex_screen(app, _v(app, 7))
    before = _topology(app.scene.mesh)

    for modifiers in (("alt",), ("shift",), ("ctrl",)):
        app.pointer_press(_mouse("LEFT", *modifiers), *pos)
        assert app.pointer_release("LEFT", *pos) is False

    assert app._knife.last_point is None
    assert _topology(app.scene.mesh) == before
    assert app.selection.is_empty()


# -- 8. invalid targets ----------------------------------------------------------------


def _face_center_screen(app, vertex_indices):
    mesh = app.scene.mesh
    points = [mesh.vertex_position(_v(app, i)) for i in vertex_indices]
    center = tuple(sum(p[i] for p in points) / len(points) for i in range(3))
    return _screen(app, center)


def _assert_no_preview(app):
    data = app.knife_render_data
    assert data.prospective_point is None
    assert data.line_preview is None
    assert app.viewport.tool_point_layers[TOOL_PREVIEW_LAYER] == []


def _assert_click_rejected(app, pos):
    before = _topology(app.scene.mesh)
    path = app._knife.path
    assert _click(app, pos) is False
    assert app.status_message == "Knife: no valid cut target here"
    assert _topology(app.scene.mesh) == before
    assert app._knife.path == path
    assert app.knife_active
    assert _history_depths(app) == (0, 0)


def test_a_face_the_last_point_does_not_touch_has_no_preview_and_click_does_nothing(app):
    """WP-KNIFE-01 S3: a face hit is a target now (`test_application_knife_faces.py`); this face (x = +1)
    shares no face with the start vertex 7 - a cross-face segment (planner, S4): no preview, refused.
    Before S3 every face hit was refused (S2-d)."""
    _begin(app)
    _click(app, _vertex_screen(app, _v(app, 7)))
    pos = _face_center_screen(app, (2, 6, 5, 1))  # face 3
    assert knife_pick(app.camera, app.scene.mesh, *pos, WIDTH, HEIGHT)["kind"] == "face"

    app.pointer_motion(*pos)
    _assert_no_preview(app)
    _assert_click_rejected(app, pos)


def test_edge_incident_to_start_is_a_skip_along_the_edge(app):
    """AQ1 (Artist decision 2026-10-01, Q5 behaviour; before S2: refused): a point on an edge of
    the start vertex runs along that edge — previewed, accepted, nothing to cut, the chain goes on
    from it."""
    mesh = app.scene.mesh
    before = _topology(mesh)
    _begin(app)
    v7 = _v(app, 7)
    _click(app, _vertex_screen(app, v7))
    e76 = _edge(app, v7, _v(app, 6))
    pos = _edge_screen(app, e76, 0.5)

    app.pointer_motion(*pos)
    data = app.knife_render_data
    assert _close(data.prospective_point, _edge_point(app, e76, 0.5), 1e-4)
    assert data.line_preview == (mesh.vertex_position(v7), data.prospective_point)

    assert _click(app, pos) is True
    assert app.status_message == "Knife: along an existing edge - nothing to cut (0 path segments)"
    assert app._knife.cut_segments == [] and len(app._knife.points) == 2
    assert app.knife_render_data.path_segments == ()  # a skip is not drawn as a cut
    assert _topology(mesh) == before
    # The chain continues from the edge point: across face 4 (y = +1) to vertex 3.
    assert _click(app, _vertex_screen(app, _v(app, 3))) is True
    assert len(app._knife.cut_segments) == 1
    assert app.key_press(ENTER) is True
    assert _history_depths(app) == (1, 0) and len(app.selection.edges) == 1
    assert_mesh_invariants(mesh)


def test_edge_sharing_no_face_with_start_has_no_preview_and_click_does_nothing(app):
    _begin(app)
    _click(app, _vertex_screen(app, _v(app, 7)))
    pos = _edge_screen(app, _edge(app, _v(app, 2), _v(app, 1)), 0.5)  # faces 0, 3

    app.pointer_motion(*pos)
    _assert_no_preview(app)
    _assert_click_rejected(app, pos)


def test_vertex_adjacent_to_start_is_previewed_and_a_skip(app):
    """AQ1 (before S2: no preview, refused): the neighbour along an edge is accepted, nothing cut."""
    _begin(app)
    v7 = _v(app, 7)
    _click(app, _vertex_screen(app, v7))
    pos = _vertex_screen(app, _v(app, 6))  # 6-7 is an edge

    app.pointer_motion(*pos)
    assert app.knife_render_data.prospective_point == app.scene.mesh.vertex_position(_v(app, 6))

    assert _click(app, pos) is True
    assert app._knife.cut_segments == []
    assert app.key_press(ENTER) is True
    assert _history_depths(app) == (0, 0)
    assert app.status_message == "Knife: no cuts made, nothing committed - Knife still active, Esc leaves"  # UX1


def test_start_vertex_again_has_no_preview(app):
    """P13: the same point twice in a row stays refused."""
    _begin(app)
    pos = _vertex_screen(app, _v(app, 7))
    _click(app, pos)

    app.pointer_motion(*pos)
    _assert_no_preview(app)
    _assert_click_rejected(app, pos)


def test_outside_hover_has_no_preview_and_leave_clears_it(app):
    _begin(app)
    _click(app, _vertex_screen(app, _v(app, 7)))
    app.pointer_motion(*_edge_screen(app, _edge(app, _v(app, 5), _v(app, 6)), 0.3))
    assert app.knife_render_data.line_preview is not None

    app.pointer_motion(*OUTSIDE)
    _assert_no_preview(app)

    app.pointer_motion(*_edge_screen(app, _edge(app, _v(app, 5), _v(app, 6)), 0.3))
    assert app.pointer_leave() is True
    _assert_no_preview(app)


# -- 9. engine preview gate and render data -----------------------------------------------


def test_accepts_matches_click_for_every_pickable_target(app):
    """`KnifeTool.accepts` (preview gate) must agree with `click` - checked on
    a fresh copy of the session for each target on a screen grid."""
    mesh = app.scene.mesh
    _begin(app)
    _click(app, _vertex_screen(app, _v(app, 7)))
    _click(app, _edge_screen(app, _edge(app, _v(app, 5), _v(app, 6)), 0.3))
    knife = app._knife
    session_state = _topology(mesh)
    session_path = knife.path
    checked = set()
    for sx in range(20, WIDTH, 23):
        for sy in range(20, HEIGHT, 23):
            target = knife_pick(app.camera, mesh, sx, sy, WIDTH, HEIGHT)
            key = (target["kind"], target.get("vertex_id"), target.get("edge_id"))
            if key in checked:
                continue
            checked.add(key)
            expected = knife.accepts(target)
            assert knife.click(target) is expected, target
            if expected:
                assert knife.undo_step()
            assert knife.path == session_path
            assert _topology(mesh) == session_state
    kinds = {k[0] for k in checked}
    assert {"vertex", "edge", "face", "outside"} <= kinds


def test_render_data_has_line_only_with_start_and_target(app):
    mesh = app.scene.mesh
    v7, e56 = _v(app, 7), _edge(app, _v(app, 5), _v(app, 6))
    target = {"kind": "edge", "edge_id": e56, "t": 0.25}
    start = [{"pid": 0, "kind": "vertex", "vertex_id": v7}]

    assert build_knife_render_data(mesh, [], target, e56).line_preview is None
    assert build_knife_render_data(mesh, start, None, None).line_preview is None
    data = build_knife_render_data(mesh, start, target, e56)
    assert data.line_preview == (mesh.vertex_position(v7), _edge_point(app, e56, 0.25))
    assert data.placed_points == (mesh.vertex_position(v7),)
    # Stale handles (AD-001) are skipped, not raised.
    stale_target = {"kind": "edge", "edge_id": EdgeId(997), "t": 0.5}
    stale_path = [{"pid": 0, "kind": "vertex", "vertex_id": VertexId(999)},
                  {"pid": 1, "kind": "edge", "edge_id": EdgeId(998), "t": 0.5}]
    assert build_knife_render_data(
        mesh, stale_path, stale_target, EdgeId(999)
    ) == build_knife_render_data(mesh, [], None, None)


def test_render_data_draws_points_once_cut_segments_only_and_own_point_targets(app):
    """S2: placed points once each (an earlier point clicked again is not drawn twice), the segments
    commit will cut (not a skip along an existing edge), an own-point target at its position."""
    mesh = app.scene.mesh
    v7, v6, v3 = _v(app, 7), _v(app, 6), _v(app, 3)
    e56 = _edge(app, _v(app, 5), v6)
    a = {"pid": 0, "kind": "vertex", "vertex_id": v7}
    b = {"pid": 1, "kind": "edge", "edge_id": e56, "t": 0.5}
    c = {"pid": 2, "kind": "vertex", "vertex_id": v6}
    d = {"pid": 3, "kind": "vertex", "vertex_id": v3}
    path = [a, b, {"kind": "break", "reason": "edge"}, c, d, a]
    p = {x["pid"]: target_position(mesh, x) for x in (a, b, c, d)}

    data = build_knife_render_data(mesh, path, {"kind": "point", "pid": 1}, None)

    assert data.placed_points == (p[0], p[1], p[2], p[3])
    assert data.path_segments == ((p[0], p[1]), (p[2], p[3]), (p[3], p[0]))
    assert data.start_point == p[0]
    assert data.prospective_point == p[1] and data.line_preview == (p[0], p[1])


def test_shutdown_discards_a_running_session(app):
    before = _topology(app.scene.mesh)
    _begin(app)
    _cut_three_faces(app)

    app.shutdown()

    assert not app.knife_active
    assert _topology(app.scene.mesh) == before
    assert _history_depths(app) == (0, 0)


def test_session_gate_keeps_display_mode(app):
    # D is gated during the session; outside it still cycles (sanity).
    _begin(app)
    app.key_press(_key("d"))
    assert app.display.mode is DisplayMode.SHADED
    app.key_press(ESC)
    app.key_press(_key("d"))
    assert app.display.mode is not DisplayMode.SHADED


# -- 10. WP-KNIFE-01 S2: the virtual path in the window ---------------------------------------


def test_g1_marker_at_t_while_hovering_an_edge_before_and_after_the_first_click(app):
    """G1: the point marker sits at `t` on the hovered edge - before the first click (nothing to
    start a line from) and from a start on, at the end of the line preview."""
    _begin(app)
    e56 = _edge(app, _v(app, 5), _v(app, 6))

    app.pointer_motion(*_edge_screen(app, e56, 0.4))
    marker = _edge_point(app, e56, 0.4)
    data = app.knife_render_data
    assert _close(data.prospective_point, marker, 1e-4) and data.line_preview is None
    assert app.viewport.tool_point_layers[TOOL_PREVIEW_LAYER] == [data.prospective_point]

    _click(app, _vertex_screen(app, _v(app, 7)))
    app.pointer_motion(*_edge_screen(app, e56, 0.4))
    data = app.knife_render_data
    assert _close(data.prospective_point, marker, 1e-4)
    assert data.line_preview[1] == data.prospective_point
    assert app.viewport.tool_point_layers[TOOL_PREVIEW_LAYER] == [data.prospective_point]


def test_clicks_change_neither_the_mesh_nor_the_pick_cache(app):
    """The mesh is cut at commit only, so a click keeps the pick cache (no per-click invalidation);
    the commit invalidates it."""
    mesh = app.scene.mesh
    before = _topology(mesh)
    _begin(app)
    app.pointer_motion(*_vertex_screen(app, _v(app, 7)))
    generation = app._pick_cache._generation

    _cut_three_faces(app)
    app.key_press(CTRL_Z)
    app.key_press(CTRL_Y)

    assert app._pick_cache._generation == generation
    assert _topology(mesh) == before
    app.key_press(ENTER)
    assert app._pick_cache._generation > generation
    assert _topology(mesh) != before


def test_a_click_on_an_own_edge_point_reaches_that_point_again(app):
    """P05 in the window: a triangle round the front corner (vertex 6) through the midpoints of its
    three edges, closed by clicking the first point again. The own-point snap turns that click into
    the first point itself (the real-cut Knife clicked the vertex it had split there) - one vertex
    per point at commit, not a second one next to the first."""
    mesh = app.scene.mesh
    n_vertices, n_faces = len(mesh.all_vertex_ids()), len(mesh.all_face_ids())
    _begin(app)
    v6 = _v(app, 6)
    edges = [_edge(app, _v(app, i), v6) for i in (5, 2, 7)]
    for eid in edges:
        assert _click(app, _edge_screen(app, eid, 0.5)) is True
    first = app._knife.points[0]

    pos = _screen(app, _edge_point(app, edges[0], 0.5))
    assert app._knife_pick(*pos) == {"kind": "point", "pid": first["pid"]}
    app.pointer_motion(*pos)
    assert app.knife_render_data.prospective_point == app._knife.point_position(first)
    assert _click(app, pos) is True
    assert app._knife.last_point is first and len(app._knife.cut_segments) == 3

    assert app.key_press(ENTER) is True
    assert len(mesh.all_vertex_ids()) == n_vertices + 3
    assert len(mesh.all_face_ids()) == n_faces + 3
    assert len(app.selection.edges) == 3
    assert_mesh_invariants(mesh, context="corner triangle")


def test_the_own_point_snap_loses_to_a_nearer_mesh_vertex_and_ignores_far_points(app):
    from mirai.topology.knife_pick import snap_own_point

    mesh = app.scene.mesh
    _begin(app)
    e56 = _edge(app, _v(app, 5), _v(app, 6))
    _click(app, _edge_screen(app, e56, 0.08))  # an own point close to vertex 5
    points = app._knife.points
    own = _screen(app, _edge_point(app, e56, 0.08))
    v5 = _vertex_screen(app, _v(app, 5))
    vertex_target = {"kind": "vertex", "vertex_id": _v(app, 5)}

    assert snap_own_point(app.camera, mesh, *v5, WIDTH, HEIGHT, points, vertex_target) == vertex_target
    assert snap_own_point(app.camera, mesh, *own, WIDTH, HEIGHT, points, vertex_target) == {
        "kind": "point", "pid": points[0]["pid"]}
    far = {"kind": "outside"}
    assert snap_own_point(app.camera, mesh, *OUTSIDE, WIDTH, HEIGHT, points, far) == far


def test_status_line_names_skips_and_cuts(app):
    _begin(app)
    v7 = _v(app, 7)
    _click(app, _vertex_screen(app, v7))
    assert app.status_message == "Knife: start point set"
    _click(app, _vertex_screen(app, _v(app, 6)))  # neighbour along an edge (AQ1)
    assert app.status_message == "Knife: along an existing edge - nothing to cut (0 path segments)"
    _click(app, _edge_screen(app, _edge(app, _v(app, 2), _v(app, 1)), 0.5))  # across face 3
    assert app.status_message == "Knife: cut (1 path segment)"
