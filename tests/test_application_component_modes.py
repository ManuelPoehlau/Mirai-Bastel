"""Application: Component-Modi 1/2/3 — Edges und Faces auswählen (WP-06 B5b).

Headless (TraceStore), kein pyglet/Fenster. Pfade:

- `1`/`2`/`3` → `Application.key_press` → `SET_*_MODE` → `Selection.mode`,
  Auswahl + Hover geleert (Playground R-SEL-2).
- Klick/Hover → `pick_component` (E43) nach `selection.mode`.
- `Viewport.sync()` → `line_layers`/`face_layers` (E44).
- W/E/R: Ziel = aufgelöste Auswahl, sonst die Vertices der gehoverten
  Edge/Face.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import EdgeId, FaceId, SelectionMode, VertexId
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_face, pick_nearest_edge
from viewport import GLTriangleOverlay, triangulate_face
from viewport.overlay import HOVER_LAYER, SELECTED_LAYER

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)  # Bildecke: trifft weder Edge noch Face des Würfels


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


ONE, TWO, THREE = _key("1"), _key("2"), _key("3")
W, E = _key("w"), _key("e")
CTRL_Z = _key("z", "ctrl")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _project(app, point) -> tuple[float, float]:
    return app.camera.project_to_screen(point, WIDTH, HEIGHT)


def _centroid(points) -> tuple[float, float, float]:
    points = list(points)
    return tuple(sum(p[i] for p in points) / len(points) for i in range(3))


def _edge_screen(app, eid) -> tuple[float, float]:
    mesh = app.scene.mesh
    return _project(app, _centroid(mesh.vertex_position(v) for v in mesh.edge_vertices(eid)))


def _face_screen(app, fid) -> tuple[float, float]:
    mesh = app.scene.mesh
    return _project(app, _centroid(mesh.vertex_position(v) for v in mesh.face_vertices(fid)))


def _visible_edges(app) -> list[EdgeId]:
    """Edges, die ein Klick/Hover auf ihre Mitte auch trifft."""
    mesh = app.scene.mesh
    hits = [
        eid
        for eid in sorted(mesh.all_edge_ids())
        if pick_nearest_edge(app.camera, mesh, *_edge_screen(app, eid), WIDTH, HEIGHT) == eid
    ]
    assert len(hits) >= 2
    return hits


def _visible_faces(app) -> list[FaceId]:
    """Faces, die ein Klick/Hover auf ihren Mittelpunkt auch trifft (vorderste)."""
    mesh = app.scene.mesh
    hits = [
        fid
        for fid in sorted(mesh.all_face_ids())
        if pick_face(app.camera, mesh, *_face_screen(app, fid), WIDTH, HEIGHT) == fid
    ]
    assert len(hits) >= 2
    return hits


def _click(app, inp: Input, pos) -> None:
    app.pointer_press(inp)
    app.pointer_release(inp.value, *pos)


def _positions(app) -> dict:
    mesh = app.scene.mesh
    return {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}


def _moved(before: dict, after: dict) -> set[VertexId]:
    return {vid for vid in before if before[vid] != after[vid]}


def _move(app, dx: float = 30.0, dy: float = 20.0, steps: int = 3) -> None:
    x, y = app._cursor or (400.0, 300.0)
    for _ in range(steps):
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, dx, dy)


# -- Modus-Tasten -----------------------------------------------------------------


@pytest.mark.parametrize(
    "key, mode, label",
    [
        (TWO, SelectionMode.EDGE, "Edge"),
        (THREE, SelectionMode.FACE, "Face"),
    ],
)
def test_mode_key_sets_mode_and_clears_selection_and_hover(app, key, mode, label):
    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    app.selection.set({vid})
    app.selection.hovered = vid
    assert app.key_press(key)
    assert app.selection.mode is mode
    assert app.selection.is_empty()
    assert app.selection.hovered is None
    assert app.status_message == f"Mode: {label}"
    assert not app.history.can_undo()

    assert app.key_press(ONE)
    assert app.selection.mode is SelectionMode.VERTEX
    assert app.status_message == "Mode: Vertex"


def test_mode_switch_clears_the_drawn_highlight(app):
    app.key_press(TWO)
    eid = _visible_edges(app)[0]
    _click(app, _mouse("LEFT"), _edge_screen(app, eid))
    app.pointer_motion(*_edge_screen(app, eid))
    app.update_viewport(0.0)
    assert app.viewport.line_layers[SELECTED_LAYER]
    assert app.viewport.line_layers[HOVER_LAYER]
    app.key_press(THREE)
    app.update_viewport(0.0)
    assert app.viewport.line_layers == {HOVER_LAYER: [], SELECTED_LAYER: []}
    assert app.viewport.face_layers == {HOVER_LAYER: [], SELECTED_LAYER: []}


def test_same_mode_key_again_clears_selection_like_the_playground(app):
    # Playground `window.py` (Tasten 1/2/3) leert die Auswahl bei jedem Druck,
    # auch im bereits aktiven Modus (Abweichung vom B5b-Handoff "No-op",
    # gemeldet; Playground gilt).
    app.key_press(TWO)
    eid = _visible_edges(app)[0]
    _click(app, _mouse("LEFT"), _edge_screen(app, eid))
    assert app.selection.edges == {eid}
    assert app.key_press(TWO)
    assert app.selection.mode is SelectionMode.EDGE
    assert app.selection.is_empty()


@pytest.mark.parametrize("key", [ONE, TWO, THREE])
def test_mode_key_ignored_while_transform_key_held(app, key):
    app.key_press(TWO)
    eid = _visible_edges(app)[0]
    _click(app, _mouse("LEFT"), _edge_screen(app, eid))
    assert app.key_press(W)
    assert not app.key_press(key)
    assert app.selection.mode is SelectionMode.EDGE
    assert app.selection.edges == {eid}
    _move(app)
    assert not app.key_press(key)  # auch während der laufenden Bewegung
    assert app.selection.mode is SelectionMode.EDGE
    app.key_release(W)
    assert app.key_press(key)  # danach wieder möglich


@pytest.mark.parametrize("value", ["v", "f"])
def test_legacy_mode_keys_do_nothing(app, value):
    app.key_press(TWO)
    assert not app.key_press(_key(value))
    assert app.selection.mode is SelectionMode.EDGE


def test_mode_commands_dispatch_without_a_key(app):
    from mirai.interaction import commands as cmd

    assert app.dispatch_command(cmd.SET_FACE_MODE)
    assert app.selection.mode is SelectionMode.FACE


# -- Klick-Selektion (Modifier-Variante wie B2) ------------------------------------


def test_edge_click_selection_modifiers(app):
    app.key_press(TWO)
    a, b = _visible_edges(app)[:2]
    _click(app, _mouse("LEFT"), _edge_screen(app, a))
    assert app.selection.edges == {a}
    assert not app.selection.vertices and not app.selection.faces
    _click(app, _mouse("LEFT", "shift"), _edge_screen(app, b))
    assert app.selection.edges == {a, b}
    _click(app, _mouse("LEFT", "ctrl"), _edge_screen(app, a))
    assert app.selection.edges == {b}
    _click(app, _mouse("LEFT", "alt"), _edge_screen(app, a))
    assert app.selection.edges == {a, b}
    _click(app, _mouse("LEFT", "alt"), _edge_screen(app, b))
    assert app.selection.edges == {a}
    for mods in (("shift",), ("ctrl",), ("alt",)):
        _click(app, _mouse("LEFT", *mods), MISS)
        assert app.selection.edges == {a}
    _click(app, _mouse("LEFT"), MISS)
    assert app.selection.is_empty()
    assert not app.history.can_undo()


def test_face_click_selection_modifiers(app):
    app.key_press(THREE)
    a, b = _visible_faces(app)[:2]
    _click(app, _mouse("LEFT"), _face_screen(app, a))
    assert app.selection.faces == {a}
    assert not app.selection.vertices and not app.selection.edges
    _click(app, _mouse("LEFT", "shift"), _face_screen(app, b))
    assert app.selection.faces == {a, b}
    _click(app, _mouse("LEFT", "ctrl"), _face_screen(app, a))
    assert app.selection.faces == {b}
    _click(app, _mouse("LEFT", "alt"), _face_screen(app, a))
    assert app.selection.faces == {a, b}
    for mods in (("shift",), ("ctrl",), ("alt",)):
        _click(app, _mouse("LEFT", *mods), MISS)
        assert app.selection.faces == {a, b}
    _click(app, _mouse("LEFT"), MISS)
    assert app.selection.is_empty()


def test_select_vertex_at_forwards_to_select_at(app):
    assert Application.select_vertex_at is Application.select_at


# -- Hover + Overlay-Daten -------------------------------------------------------------


def test_edge_hover_switches_between_edges(app):
    app.key_press(TWO)
    a, b = _visible_edges(app)[:2]
    assert app.pointer_motion(*_edge_screen(app, a))
    assert app.selection.hovered == a and isinstance(app.selection.hovered, EdgeId)
    assert app.pointer_motion(*_edge_screen(app, b))
    assert app.selection.hovered == b
    assert not app.pointer_motion(*_edge_screen(app, b))  # keine Änderung
    assert app.pointer_motion(*MISS)
    assert app.selection.hovered is None


def test_face_hover_switches_between_faces(app):
    app.key_press(THREE)
    a, b = _visible_faces(app)[:2]
    assert app.pointer_motion(*_face_screen(app, a))
    assert app.selection.hovered == a and isinstance(app.selection.hovered, FaceId)
    assert app.pointer_motion(*_face_screen(app, b))
    assert app.selection.hovered == b
    assert app.pointer_motion(*MISS)
    assert app.selection.hovered is None


def _segment(app, eid):
    mesh = app.scene.mesh
    va, vb = mesh.edge_vertices(eid)
    return (mesh.vertex_position(va), mesh.vertex_position(vb))


def _triangles(app, fid):
    mesh = app.scene.mesh
    return [
        tuple(mesh.vertex_position(v) for v in tri)
        for tri in triangulate_face(mesh.face_vertices(fid))
    ]


def test_line_layers_hold_hovered_and_selected_edges(app):
    app.key_press(TWO)
    a, b = _visible_edges(app)[:2]
    _click(app, _mouse("LEFT"), _edge_screen(app, a))
    app.pointer_motion(*_edge_screen(app, b))
    app.update_viewport(0.0)
    assert app.viewport.line_layers == {
        HOVER_LAYER: [_segment(app, b)],
        SELECTED_LAYER: [_segment(app, a)],
    }
    assert app.viewport.face_layers == {HOVER_LAYER: [], SELECTED_LAYER: []}
    assert app.viewport.point_positions == {HOVER_LAYER: [], SELECTED_LAYER: []}


def test_face_layers_hold_hovered_and_selected_faces(app):
    app.key_press(THREE)
    a, b = _visible_faces(app)[:2]
    _click(app, _mouse("LEFT"), _face_screen(app, a))
    app.pointer_motion(*_face_screen(app, b))
    app.update_viewport(0.0)
    assert app.viewport.face_layers == {
        HOVER_LAYER: _triangles(app, b),
        SELECTED_LAYER: _triangles(app, a),
    }
    assert len(app.viewport.face_layers[SELECTED_LAYER]) == 2  # Quad = 2 Dreiecke
    assert app.viewport.line_layers == {HOVER_LAYER: [], SELECTED_LAYER: []}


def test_overlay_data_follows_move_and_undo(app):
    app.key_press(TWO)
    eid = _visible_edges(app)[0]
    _click(app, _mouse("LEFT"), _edge_screen(app, eid))
    app.update_viewport(0.0)
    original = list(app.viewport.line_layers[SELECTED_LAYER])

    app.key_press(W)
    _move(app)
    app.update_viewport(0.0)
    moved = app.viewport.line_layers[SELECTED_LAYER]
    assert moved != original
    assert moved == [_segment(app, eid)]
    app.key_release(W)

    app.key_press(CTRL_Z)
    app.update_viewport(0.0)
    assert app.viewport.line_layers[SELECTED_LAYER] == original


def test_face_overlay_follows_move_of_a_shared_vertex(app):
    app.key_press(THREE)
    fid = _visible_faces(app)[0]
    _click(app, _mouse("LEFT"), _face_screen(app, fid))
    app.update_viewport(0.0)
    mesh = app.scene.mesh
    vid = mesh.face_vertices(fid)[0]
    x, y, z = mesh.vertex_position(vid)
    mesh.set_vertex_position(vid, (x + 0.5, y, z))
    app.viewport.on_vertices_moved({vid})
    app.update_viewport(0.0)
    assert app.viewport.face_layers[SELECTED_LAYER] == _triangles(app, fid)


def test_overlay_data_is_not_recomputed_without_a_change(app, monkeypatch):
    app.key_press(TWO)
    app.update_viewport(0.0)
    calls = []
    original = app.viewport.overlay.line_layers
    monkeypatch.setattr(
        app.viewport.overlay, "line_layers", lambda mesh: calls.append(1) or original(mesh)
    )
    app.camera.orbit(0.2, 0.1)
    app.viewport.on_camera_changed(WIDTH / HEIGHT)
    app.update_viewport(0.0)
    assert calls == []


def test_selection_change_does_not_rebuild_the_base_mesh(app):
    app.key_press(THREE)
    app.update_viewport(0.0)
    before = app.viewport.benchmark_counters.get("geometry_uploads", 0)
    _click(app, _mouse("LEFT"), _face_screen(app, _visible_faces(app)[0]))
    app.pointer_motion(*_face_screen(app, _visible_faces(app)[1]))
    app.update_viewport(0.0)
    assert app.viewport.benchmark_counters.get("geometry_uploads", 0) == before


# -- Transform auf Edges/Faces ---------------------------------------------------------


def test_move_edge_selection_moves_exactly_its_endpoints(app):
    app.key_press(TWO)
    a, b = _visible_edges(app)[:2]
    _click(app, _mouse("LEFT"), _edge_screen(app, a))
    _click(app, _mouse("LEFT", "shift"), _edge_screen(app, b))
    expected = set(app.scene.mesh.edge_vertices(a)) | set(app.scene.mesh.edge_vertices(b))
    before = _positions(app)
    assert app.key_press(W)
    assert app.transform_target == expected
    assert f"{len(expected)} vertices" in app.status_message
    _move(app)
    app.key_release(W)
    assert _moved(before, _positions(app)) == expected
    app.key_press(CTRL_Z)
    assert _positions(app) == before


def test_rotate_face_selection_moves_exactly_its_boundary(app):
    app.key_press(THREE)
    fid = _visible_faces(app)[0]
    _click(app, _mouse("LEFT"), _face_screen(app, fid))
    expected = set(app.scene.mesh.face_vertices(fid))
    before = _positions(app)
    assert app.key_press(E)
    assert app.transform_target == expected
    _move(app)
    app.key_release(E)
    assert _moved(before, _positions(app)) == expected
    app.key_press(CTRL_Z)
    assert _positions(app) == before


def test_move_without_selection_uses_hovered_edge(app):
    app.key_press(TWO)
    eid = _visible_edges(app)[0]
    app.pointer_motion(*_edge_screen(app, eid))
    assert app.selection.hovered == eid
    expected = set(app.scene.mesh.edge_vertices(eid))
    before = _positions(app)
    assert app.key_press(W)
    assert app.transform_target == expected
    assert app.selection.hovered is None  # kein Hover über dem Ziel
    _move(app)
    app.key_release(W)
    assert _moved(before, _positions(app)) == expected
    assert app.selection.is_empty()  # Hover-Ziel wird nicht zur Auswahl
    app.key_press(CTRL_Z)
    assert _positions(app) == before


def test_move_without_selection_uses_hovered_face(app):
    app.key_press(THREE)
    fid = _visible_faces(app)[0]
    app.pointer_motion(*_face_screen(app, fid))
    expected = set(app.scene.mesh.face_vertices(fid))
    before = _positions(app)
    assert app.key_press(W)
    assert app.transform_target == expected
    _move(app)
    app.key_release(W)
    assert _moved(before, _positions(app)) == expected
    app.key_press(CTRL_Z)
    assert _positions(app) == before


@pytest.mark.parametrize("key, noun", [(TWO, "edge"), (THREE, "face")])
def test_transform_with_nothing_is_rejected(app, key, noun):
    app.key_press(key)
    assert not app.key_press(W)
    assert app.transform_command is None
    assert app.status_message == f"Move: nothing to move (select or hover a {noun})"


def test_arming_clears_hover_on_a_selected_edge_but_keeps_unrelated_hover(app):
    app.key_press(TWO)
    a, b = _visible_edges(app)[:2]
    _click(app, _mouse("LEFT"), _edge_screen(app, a))
    app.pointer_motion(*_edge_screen(app, b))
    assert app.key_press(W)
    assert app.selection.hovered == b  # b ist nicht selektiert
    app.key_release(W)

    app.pointer_motion(*_edge_screen(app, a))
    assert app.selection.hovered == a
    assert app.key_press(W)
    assert app.selection.hovered is None


# -- GLTriangleOverlay headless ----------------------------------------------------------


def test_gl_triangle_overlay_constructs_without_gl_context():
    overlay = GLTriangleOverlay()
    tri = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    overlay.set_triangles(SELECTED_LAYER, [tri, tri])
    overlay.set_triangles(HOVER_LAYER, [tri])
    assert overlay.triangle_count(SELECTED_LAYER) == 2
    assert overlay.triangle_count(HOVER_LAYER) == 1
    assert overlay.vertex_list(SELECTED_LAYER) is None
    assert overlay.uploads == 0
    with pytest.raises(KeyError):
        overlay.set_triangles("wire", [tri])


def test_viewport_pushes_layers_into_the_overlays(app):
    from viewport import GLLineOverlay

    app.init_scene("cube", line_overlay_type=GLLineOverlay, face_overlay_type=GLTriangleOverlay)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.key_press(THREE)
    fid = _visible_faces(app)[0]
    _click(app, _mouse("LEFT"), _face_screen(app, fid))
    app.update_viewport(0.0)
    assert app.viewport.face_overlay.triangle_count(SELECTED_LAYER) == 2
    app.key_press(TWO)
    eid = _visible_edges(app)[0]
    app.pointer_motion(*_edge_screen(app, eid))
    app.update_viewport(0.0)
    assert app.viewport.face_overlay.triangle_count(SELECTED_LAYER) == 0
    assert app.viewport.line_overlay.segment_count(HOVER_LAYER) == 1
    assert app.viewport.line_overlay.segment_count() == 0  # Wire aus (Shaded)


def test_edge_highlight_turns_on_the_face_polygon_offset(app, monkeypatch):
    # Ohne Offset z-fightet die 1-px-Highlight-Linie mit der Fläche (auf dem
    # Kopf-Mesh nur gestrichelt sichtbar) - wie beim Wire (E40).
    styles = []
    monkeypatch.setattr(
        app.viewport.render_mesh.store,
        "set_draw_style",
        lambda flat, polygon_offset: styles.append(polygon_offset),
        raising=False,
    )
    app.key_press(TWO)
    app.update_viewport(0.0)
    assert styles == []  # kein Highlight → nichts zu ändern
    eid = _visible_edges(app)[0]
    app.pointer_motion(*_edge_screen(app, eid))
    app.update_viewport(0.0)
    assert styles == [True]
    app.pointer_motion(*MISS)
    app.update_viewport(0.0)
    assert styles == [True, False]
    # Face-Highlight braucht keinen Offset.
    app.key_press(THREE)
    app.pointer_motion(*_face_screen(app, _visible_faces(app)[0]))
    app.update_viewport(0.0)
    assert styles == [True, False]
