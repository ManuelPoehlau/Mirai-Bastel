"""Application: picking cache + occlusion wiring (WP-06 B8).

Headless (TraceStore), no pyglet/window. Two concerns:

1. Occlusion: `Application._pick()`/`_knife_pick()` pass `occlusion=
   self.display.show_faces` - a hidden cube vertex is unpickable in Shaded/
   Flat Shaded and pickable in Wireframe, in Selection hover and in a Knife
   session alike.
2. Cache invalidation: `Application` owns one `PickCache` (`self._pick_
   cache`) and must invalidate it at every point the handoff lists - orbit,
   zoom, pan, Move/Rotate/Scale commit, Undo/Redo, Split/Connect, Knife cut,
   display-mode change - so picking never returns a stale (pre-mutation)
   result. Orbit/zoom/pan are covered here too even though `PickCache`
   invalidates them automatically via `camera.camera_revision`
   (`tests/test_picking_cache.py` covers that mechanism directly) - this
   file checks the observable Application-level guarantee end-to-end.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import SelectionMode, VertexId
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _screen(app, point) -> tuple[float, float]:
    return app.camera.project_to_screen(point, WIDTH, HEIGHT)


def _vertex_screen(app, vid) -> tuple[float, float]:
    return _screen(app, app.scene.mesh.vertex_position(vid))


def _front_and_hidden(app) -> tuple[VertexId, VertexId]:
    """Same fact as `tests/test_picking_cache.py`: vertex 6 always faces the
    default camera, vertex 0 is the sole fully hidden corner."""
    ids = sorted(app.scene.mesh.all_vertex_ids(), key=int)
    return ids[6], ids[0]


# -- 1. occlusion wiring ---------------------------------------------------------


def test_hidden_vertex_not_hoverable_in_shaded_but_hoverable_in_wireframe(app):
    app.selection.mode = SelectionMode.VERTEX
    _front, hidden = _front_and_hidden(app)
    pos = _vertex_screen(app, hidden)

    app.pointer_motion(*pos)
    assert app.selection.hovered is None  # Shaded (default): occluded

    app.dispatch_command(cmd.SET_WIREFRAME)
    app.pointer_motion(*pos)
    assert app.selection.hovered == hidden

    app.dispatch_command(cmd.SET_SHADED)
    app.pointer_motion(*pos)
    assert app.selection.hovered is None


def test_visible_vertex_stays_hoverable_in_shaded(app):
    app.selection.mode = SelectionMode.VERTEX
    front, _hidden = _front_and_hidden(app)

    app.pointer_motion(*_vertex_screen(app, front))

    assert app.selection.hovered == front


def test_knife_cannot_target_a_hidden_vertex_in_shaded_but_can_in_wireframe(app):
    """Uses the raw `knife_pick()` target (via `app._knife_pick`) rather than
    the rendered preview: at the hidden vertex's exact screen position, a
    coincidentally nearby *visible* edge may legitimately win once the vertex
    itself is excluded (its own separate `max_pixel_distance`) - what matters
    is that the hidden vertex itself is never the target while occluded."""
    app.selection.clear()
    assert app.key_press(_key("c")) is True
    assert app.knife_active
    _front, hidden = _front_and_hidden(app)
    pos = _vertex_screen(app, hidden)

    shaded_target = app._knife_pick(*pos)
    assert not (shaded_target.get("kind") == "vertex" and shaded_target.get("vertex_id") == hidden)

    app.dispatch_command(cmd.SET_WIREFRAME)
    wireframe_target = app._knife_pick(*pos)
    assert wireframe_target == {"kind": "vertex", "vertex_id": hidden}


# -- 2. cache invalidation --------------------------------------------------------


def test_orbit_invalidates_stale_projected_positions(app):
    app.selection.mode = SelectionMode.VERTEX
    front, _hidden = _front_and_hidden(app)
    old_pos = _vertex_screen(app, front)
    app.pointer_motion(*old_pos)
    assert app.selection.hovered == front

    app.pointer_press(_mouse("LEFT", "alt"), 400, 300)
    app.pointer_drag(40, 0, 440, 300)  # modest orbit - keeps vertex 6 the front corner
    app.pointer_release("LEFT", 440, 300)

    new_pos = _vertex_screen(app, front)
    assert new_pos != old_pos
    app.pointer_motion(*new_pos)
    assert app.selection.hovered == front


def test_zoom_invalidates_stale_projected_positions(app):
    app.selection.mode = SelectionMode.VERTEX
    front, _hidden = _front_and_hidden(app)
    old_pos = _vertex_screen(app, front)

    app.pointer_scroll(Input("wheel", "UP"))

    new_pos = _vertex_screen(app, front)
    assert new_pos != old_pos
    app.pointer_motion(*new_pos)
    assert app.selection.hovered == front


def test_pan_invalidates_stale_projected_positions(app):
    app.selection.mode = SelectionMode.VERTEX
    front, _hidden = _front_and_hidden(app)
    old_pos = _vertex_screen(app, front)

    app.pointer_press(_mouse("LEFT", "alt", "shift"), 400, 300)
    app.pointer_drag(60, 40, 460, 340)
    app.pointer_release("LEFT", 460, 340)

    new_pos = _vertex_screen(app, front)
    assert new_pos != old_pos
    app.pointer_motion(*new_pos)
    assert app.selection.hovered == front


def test_move_commit_invalidates_stale_vertex_position(app):
    app.selection.mode = SelectionMode.VERTEX
    front, _hidden = _front_and_hidden(app)
    app.selection.set({front})
    old_pos = _vertex_screen(app, front)

    app.key_press(_key("w"))
    app.pointer_motion(480.0, 300.0, 80.0, 0.0)
    app.key_release(_key("w"))

    new_pos = _vertex_screen(app, front)
    assert new_pos != old_pos
    app.pointer_motion(*new_pos)
    assert app.selection.hovered == front


def test_undo_after_move_invalidates_back_to_the_pre_move_position(app):
    app.selection.mode = SelectionMode.VERTEX
    front, _hidden = _front_and_hidden(app)
    app.selection.set({front})
    pre_move_pos = _vertex_screen(app, front)

    app.key_press(_key("w"))
    app.pointer_motion(480.0, 300.0, 80.0, 0.0)
    app.key_release(_key("w"))

    app.key_press(_key("z", "ctrl"))

    app.pointer_motion(*pre_move_pos)
    assert app.selection.hovered == front


def test_split_edge_makes_the_new_vertex_immediately_hoverable(app):
    """Splits a visible edge (5-6, per the knife fixture geometry) - an edge
    on the cube's hidden side would make the new vertex itself occluded and
    unhoverable regardless of cache freshness, which is not what this test
    checks."""
    mesh = app.scene.mesh
    ids = sorted(mesh.all_vertex_ids(), key=int)
    v5, v6 = ids[5], ids[6]
    eid = next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {v5, v6})
    va, vb = mesh.edge_vertices(eid)
    midpoint = tuple((a + b) / 2.0 for a, b in zip(mesh.vertex_position(va), mesh.vertex_position(vb)))
    app.selection.mode = SelectionMode.EDGE
    app.selection.set({eid})

    assert app.key_press(_key("c")) is True  # Split

    new_vid = next(iter(app.selection.vertices))
    assert mesh.vertex_position(new_vid) == pytest.approx(midpoint)
    pos = _vertex_screen(app, new_vid)
    app.selection.mode = SelectionMode.VERTEX
    app.pointer_motion(*pos)
    assert app.selection.hovered == new_vid


def test_knife_cut_makes_the_new_vertex_immediately_hoverable(app):
    """Fixture geometry (`tests/test_application_knife.py`): vertex 7 is a
    valid Knife start, edge 5-6 is not incident to it and shares a face with
    it (face 1) - a valid second click; the commit splits that edge and
    creates a new vertex (WP-KNIFE-01 S2: at commit, not at the click)."""
    from mirai.topology.knife_pick import knife_pick
    from mirai.topology.knife_preview import target_position

    mesh = app.scene.mesh
    ids = sorted(mesh.all_vertex_ids(), key=int)
    v5, v6, v7 = ids[5], ids[6], ids[7]
    eid = next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {v5, v6})

    app.selection.clear()
    assert app.key_press(_key("c")) is True  # begin Knife session

    start_pos = _vertex_screen(app, v7)
    app.pointer_motion(*start_pos)
    app.pointer_press(_mouse("LEFT"), *start_pos)
    assert app.pointer_release("LEFT", *start_pos) is True  # sets start = v7

    cut_point = target_position(mesh, {"kind": "edge", "edge_id": eid, "t": 0.4})
    cut_screen = app.camera.project_to_screen(cut_point, WIDTH, HEIGHT)
    target = knife_pick(app.camera, mesh, *cut_screen, WIDTH, HEIGHT)
    assert target["kind"] == "edge" and target["edge_id"] == eid, target
    app.pointer_motion(*cut_screen)
    app.pointer_press(_mouse("LEFT"), *cut_screen)
    assert app.pointer_release("LEFT", *cut_screen) is True

    assert app.key_press(_key("enter")) is True  # commit
    new_vid = next(v for v in mesh.all_vertex_ids()
                   if all(abs(a - b) < 1e-9 for a, b in zip(mesh.vertex_position(v), cut_point)))
    # UX1 (Manu 2026-10-01): the Knife stays active after the commit, so the new vertex is hovered by the
    # re-armed session's own (cached) pick - was: selection hover in Vertex mode after the session ended.
    # Not left with Esc first: that would invalidate the cache itself.
    assert app.knife_active
    app.pointer_motion(*_vertex_screen(app, new_vid))
    assert app._knife_target == {"kind": "vertex", "vertex_id": new_vid}


def test_display_mode_change_gives_fresh_occlusion_immediately(app):
    """No intervening pointer_motion between the mode switch and the pick at
    the same screen position - proves the mode change itself (not merely a
    later re-hover) produced a fresh, occlusion-correct result."""
    app.selection.mode = SelectionMode.VERTEX
    _front, hidden = _front_and_hidden(app)
    pos = _vertex_screen(app, hidden)
    app.pointer_motion(*pos)
    assert app.selection.hovered is None

    app.dispatch_command(cmd.SET_WIREFRAME)

    assert app._pick(*pos) == hidden
