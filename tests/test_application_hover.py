"""Application: Vertex-Hover (WP-06 B2b, E20).

Headless (TraceStore), kein pyglet/Fenster. Pfad: Mausbewegung →
`Application.pointer_motion` → `pick_nearest_vertex` → `selection.hovered`
→ `viewport.on_selection_changed()` (nur bei echter Änderung).
"""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401

from core import EdgeId, SelectionMode, VertexId
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_nearest_vertex
from viewport.overlay import HOVER_LAYER

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)  # Bildecke: weit weg von jedem Würfel-Vertex


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


def _wheel(direction: str) -> Input:
    return Input("wheel", direction)


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


@pytest.fixture
def notifications(app, monkeypatch) -> list[None]:
    calls: list[None] = []
    original = app.viewport.on_selection_changed

    def spy() -> None:
        calls.append(None)
        original()

    monkeypatch.setattr(app.viewport, "on_selection_changed", spy)
    return calls


def _screen(app, vid) -> tuple[float, float]:
    return app.camera.project_to_screen(
        app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT
    )


def _visible_target(app) -> VertexId:
    """Ein Vertex, den ein Klick/Hover auf seine Projektion auch trifft.
    `occlusion=True` (WP-06 B8): the default Shaded display hides the cube's
    one fully occluded corner from picking, same as `Application._pick()`."""
    for vid in app.scene.mesh.all_vertex_ids():
        sx, sy = _screen(app, vid)
        if pick_nearest_vertex(app.camera, app.scene.mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) == vid:
            return vid
    raise AssertionError("no pickable vertex")


def test_motion_over_vertex_sets_hovered(app, notifications):
    vid = _visible_target(app)
    assert app.pointer_motion(*_screen(app, vid))
    assert app.selection.hovered == vid
    assert isinstance(app.selection.hovered, VertexId)
    assert len(notifications) == 1
    app.update_viewport(0.0)
    assert app.viewport.point_positions[HOVER_LAYER] == [
        app.scene.mesh.vertex_position(vid)
    ]


def test_motion_over_empty_space_clears_hovered(app, notifications):
    app.pointer_motion(*_screen(app, _visible_target(app)))
    assert app.pointer_motion(*MISS)
    assert app.selection.hovered is None
    assert len(notifications) == 2


def test_no_notification_when_hovered_id_unchanged(app, notifications):
    sx, sy = _screen(app, _visible_target(app))
    app.pointer_motion(sx, sy)
    assert not app.pointer_motion(sx + 1.0, sy)
    assert not app.pointer_motion(sx, sy + 1.0)
    assert len(notifications) == 1
    app.pointer_motion(*MISS)
    assert not app.pointer_motion(*MISS)
    assert len(notifications) == 2


def test_same_int_different_id_type_counts_as_change(app):
    vid = _visible_target(app)
    app.selection.hovered = EdgeId(int(vid))
    assert app.pointer_motion(*_screen(app, vid))
    assert type(app.selection.hovered) is VertexId


def test_no_hover_update_while_a_gesture_runs(app, notifications):
    app.pointer_press(_mouse("LEFT"))  # Klick-Geste läuft
    assert not app.pointer_motion(*_screen(app, _visible_target(app)))
    assert app.selection.hovered is None
    assert notifications == []


@pytest.mark.parametrize("modifiers", [("alt",), ("alt", "shift")])
def test_starting_orbit_or_pan_clears_hover(app, modifiers):
    app.pointer_motion(*_screen(app, _visible_target(app)))
    assert app.selection.hovered is not None
    app.pointer_press(_mouse("LEFT", *modifiers))
    app.pointer_drag(10, 0)  # über der Klick-Schwelle → Drag startet
    assert app.selection.hovered is None
    app.pointer_release("LEFT", 400, 300)
    assert app.selection.hovered is None  # erst die nächste Bewegung pickt neu


def test_alt_click_below_threshold_keeps_hover(app):
    vid = _visible_target(app)
    app.pointer_motion(*_screen(app, vid))
    app.pointer_press(_mouse("LEFT", "alt"))
    app.pointer_drag(1, 1)
    assert app.selection.hovered == vid


def test_wheel_repicks_at_last_cursor_position(app):
    # The radius picker only: on the cube, nearest-on-face (Manu 2026-11-24) keeps the zoomed vertex hovered (the
    # cursor stays on its face); this test is about the re-pick itself.
    app.pick_nearest_on_face = False
    # Ein Vertex weit weg von der Bildmitte wandert beim Zoom am stärksten.
    vid = max(
        (v for v in app.scene.mesh.all_vertex_ids()
         if pick_nearest_vertex(app.camera, app.scene.mesh, *_screen(app, v),
                                WIDTH, HEIGHT) == v),
        key=lambda v: math.dist(_screen(app, v), (WIDTH / 2, HEIGHT / 2)),
    )
    cursor = _screen(app, vid)
    app.pointer_motion(*cursor)
    assert app.selection.hovered == vid

    # Mehrfach reinzoomen: der Vertex wandert unter dem ruhenden Cursor weg.
    for _ in range(5):
        app.pointer_scroll(_wheel("UP"))
    expected = pick_nearest_vertex(app.camera, app.scene.mesh, *cursor, WIDTH, HEIGHT)
    assert math.dist(_screen(app, vid), cursor) > 14.0
    assert expected != vid
    assert app.selection.hovered == expected


def test_wheel_without_known_cursor_does_not_pick(app, notifications):
    app.pointer_scroll(_wheel("UP"))
    assert app.selection.hovered is None
    assert notifications == []


def test_leave_clears_hover_and_forgets_cursor(app, notifications):
    vid = _visible_target(app)
    app.pointer_motion(*_screen(app, vid))
    assert app.pointer_leave()
    assert app.selection.hovered is None
    assert not app.pointer_leave()
    app.pointer_scroll(_wheel("DOWN"))
    assert app.selection.hovered is None
    assert len(notifications) == 2


def test_hover_follows_the_active_mode(app):
    # B2b hatte Hover nur im Vertex-Modus; seit B5b (E43) hovert jeder Modus
    # sein eigenes Element (Details: tests/test_application_component_modes.py).
    app.selection.mode = SelectionMode.EDGE
    assert app.pointer_motion(*_screen(app, _visible_target(app)))
    assert isinstance(app.selection.hovered, EdgeId)


def test_hover_leaves_selection_and_history_untouched(app):
    app.pointer_motion(*_screen(app, _visible_target(app)))
    app.pointer_scroll(_wheel("UP"))
    app.pointer_motion(*MISS)
    app.pointer_leave()
    assert app.selection.is_empty()
    assert not app.history.can_undo()
    assert len(app.history) == 0


def test_hover_before_init_scene_does_not_crash():
    app = Application()
    app.set_viewport_size(WIDTH, HEIGHT)
    assert not app.pointer_motion(10, 10)
    assert not app.pointer_leave()


@pytest.mark.parametrize("mode", [SelectionMode.VERTEX, SelectionMode.EDGE])
def test_inside_a_face_the_nearest_element_hovers_and_clicks(app, mode):
    """Silo / ZBrush (Manu 2026-11-24): the cursor in the middle of a face, outside every pick radius, hovers the
    nearest corner / edge of that face, and a click selects it; empty space stays empty (the click clears)."""
    from mirai.viewport.picking import pick_face

    app.selection.mode = mode
    mesh = app.scene.mesh

    def centroid(f):
        pts = [_screen(app, v) for v in mesh.face_vertices(f)]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

    # The visible face whose screen centroid lies farthest from its corners (the largest one on screen).
    face = max(
        (f for f in mesh.all_face_ids() if pick_face(app.camera, mesh, *centroid(f), WIDTH, HEIGHT) == f),
        key=lambda f: min(math.dist(centroid(f), _screen(app, v)) for v in mesh.face_vertices(f)),
    )
    x, y = centroid(face)
    app.pick_nearest_on_face = False
    app.pointer_motion(x, y)
    assert app.selection.hovered is None  # the face centre lies outside every radius
    app.pick_nearest_on_face = True
    app.pointer_motion(x + 1.0, y)
    hovered = app.selection.hovered
    own = mesh.face_vertices(face) if mode is SelectionMode.VERTEX else mesh.face_edges(face)
    assert hovered is not None and hovered in own
    app.pointer_press(_mouse("LEFT"), x + 1.0, y)
    app.pointer_release("LEFT", x + 1.0, y)
    selected = app.selection.vertices if mode is SelectionMode.VERTEX else app.selection.edges
    assert selected == {hovered}

    app.pointer_motion(2.0, 2.0)
    assert app.selection.hovered is None
    app.pointer_press(_mouse("LEFT"), 2.0, 2.0)
    app.pointer_release("LEFT", 2.0, 2.0)
    assert not app.selection.vertices and not app.selection.edges
