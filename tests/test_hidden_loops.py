"""Loops, rings and Loop Insert stop at hidden geometry (`blocked`, mirai.hidden; Manu 2026-10-25): isolate the nose and
insert a loop - it must not run on through the invisible part."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from core.mesh import Mesh
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.topology import selection_steps
from mirai.topology.loop_ring import edge_loop, edge_ring

WIDTH, HEIGHT = 800, 600
N = 4


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


I, SHIFT_L, SHIFT_R = _key("i"), _key("l", "shift"), _key("r", "shift")
ISOLATE, SHOW_ALL = _key("h", "ctrl", "shift"), _key("h", "alt")
K1, K2, K3 = _key("1"), _key("2"), _key("3")


def _grid(n: int = N, size: float = 4.0) -> Mesh:
    mesh = Mesh()
    step = size / n
    half = size / 2.0
    p = {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((c * step - half, r * step - half, 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


def _vertex(mesh, x: float, y: float):
    (vid,) = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (x, y)]
    return vid


def _edge(mesh, a, b):
    (eid,) = [e for e in mesh.vertex_edges(a) if set(mesh.edge_vertices(e)) == {a, b}]
    return eid


def _bottom_edge(mesh, x: float = -2.0, y: float = -2.0):
    return _edge(mesh, _vertex(mesh, x, y), _vertex(mesh, x + 1.0, y))


def _blocked_above(mesh, y: float = 0.0) -> frozenset:
    return frozenset(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[1] > y)


# -- Walks ------------------------------------------------------------------------------


def test_ring_ends_at_the_hidden_border_like_at_a_mesh_border():
    mesh = _grid()
    start = _bottom_edge(mesh)
    assert len(edge_ring(mesh, start).edges) == N + 1
    ring = edge_ring(mesh, start, _blocked_above(mesh))
    ys = sorted(mesh.vertex_position(mesh.edge_vertices(e)[0])[1] for e in ring.edges)
    assert ys == [-2.0, -1.0, 0.0] and not ring.closed  # the visible opposite edge still belongs to the ring


def test_ring_through_a_hidden_start_face_is_cut_on_that_side():
    mesh = _grid()
    start = _edge(mesh, _vertex(mesh, -2.0, 0.0), _vertex(mesh, -1.0, 0.0))  # visible/hidden border edge
    ring = edge_ring(mesh, start, _blocked_above(mesh))
    ys = sorted(mesh.vertex_position(mesh.edge_vertices(e)[0])[1] for e in ring.edges)
    assert ys == [-2.0, -1.0, 0.0]  # only the visible side


def test_loop_stops_before_an_edge_with_a_hidden_endpoint():
    mesh = _grid()
    start = _edge(mesh, _vertex(mesh, -2.0, -2.0), _vertex(mesh, -2.0, -1.0))  # a vertical border edge
    full = edge_loop(mesh, start)
    blocked = _blocked_above(mesh, -1.0)  # y > -1 hidden
    loop = edge_loop(mesh, start, blocked)
    assert len(loop.edges) < len(full.edges) or full.edges == [start]
    for e in loop.edges:
        assert not (set(mesh.edge_vertices(e)) & blocked)


def test_loop_steps_respect_blocked():
    mesh = _grid()
    blocked = _blocked_above(mesh, -1.0)
    edges = {_edge(mesh, _vertex(mesh, x, -2.0), _vertex(mesh, x + 1.0, -2.0)) for x in (-1.0, 0.0)}
    grown = selection_steps.loop_grow(mesh, edges, blocked)
    assert all(not (set(mesh.edge_vertices(e)) & blocked) for e in grown)
    assert grown >= edges
    piece = selection_steps.loop_pieces(mesh, edges, blocked)[0]
    assert selection_steps.shifted_piece(mesh, piece, True, blocked) is None or all(
        not (set(mesh.edge_vertices(e)) & blocked)
        for e in selection_steps.shifted_piece(mesh, piece, True, blocked)
    )


# -- App path ---------------------------------------------------------------------------


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_grid().export_state())
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _isolate_lower_half(app):
    mesh = app.scene.mesh
    app.key_press(K1)
    keep = {v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[1] <= 0.0}
    app.selection.set(keep)
    app.viewport.on_selection_changed()
    assert app.key_press(ISOLATE)
    assert app._hidden.vertices() == frozenset(mesh.all_vertex_ids()) - keep
    return keep


def test_loop_insert_only_cuts_the_visible_quads(app):
    mesh = app.scene.mesh
    _isolate_lower_half(app)
    hidden_faces = {f: tuple(mesh.face_vertices(f)) for f in mesh.all_face_ids() if app._hidden.is_hidden_face(mesh, f)}
    assert hidden_faces
    faces_before = len(mesh.all_face_ids())
    app.key_press(K2)
    app.selection.set({_bottom_edge(mesh)})
    app.viewport.on_selection_changed()
    assert app.key_press(I)
    assert len(mesh.all_face_ids()) == faces_before + 2  # the two visible quads of the ring were cut
    for f, boundary in hidden_faces.items():
        assert mesh.is_valid_face(f)  # hidden faces survive (one border edge got a vertex)
    # nothing was added above y = 0 except the border midpoint
    assert all(mesh.vertex_position(v)[1] <= 0.0 or app._hidden.is_hidden_vertex(v) for v in mesh.all_vertex_ids())
    assert app.key_press(_key("z", "ctrl"))
    assert len(mesh.all_face_ids()) == faces_before


def test_loop_insert_without_hidden_geometry_cuts_the_whole_ring(app):
    mesh = app.scene.mesh
    app.key_press(K2)
    app.selection.set({_bottom_edge(mesh)})
    app.viewport.on_selection_changed()
    faces_before = len(mesh.all_face_ids())
    assert app.key_press(I)
    assert len(mesh.all_face_ids()) == faces_before + N


def test_ring_select_stops_at_the_hidden_part(app):
    mesh = app.scene.mesh
    _isolate_lower_half(app)
    app.key_press(K2)
    app.selection.set({_bottom_edge(mesh)})
    app.viewport.on_selection_changed()
    assert app.key_press(SHIFT_R)
    ys = sorted(mesh.vertex_position(mesh.edge_vertices(e)[0])[1] for e in app.selection.edges)
    assert ys == [-2.0, -1.0, 0.0]


def test_a_ring_that_closes_around_the_hidden_part_never_cuts_hidden_quads(app):
    """Hide the middle row: the ring walked from below ends at it from both sides; Loop Insert must not cut it."""
    mesh = app.scene.mesh
    app.key_press(K1)
    row = {v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[1] == 0.0}
    app._hidden.hide(row)
    app._hidden_push()
    hidden_faces = [f for f in mesh.all_face_ids() if app._hidden.is_hidden_face(mesh, f)]
    app.key_press(K2)
    app.selection.set({_bottom_edge(mesh)})
    app.viewport.on_selection_changed()
    app.key_press(I)
    assert all(mesh.is_valid_face(f) for f in hidden_faces)
