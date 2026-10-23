"""Selection steps (WP Toolbox Gaps A1, Manu 2026-10-23): Grow / Shrink (Ctrl++ / Ctrl+-),
loop grow / shrink (Shift+Up / Shift+Down), next / previous parallel loop (Shift+Right /
Shift+Left).

Pinned: pure selection changes (no History entry, mesh untouched); grow/shrink per mode V/E/F;
loop steps only in edge mode, at both ends of each open piece, closed loops unchanged, stops at
poles and borders like Shift+L; the parallel loop replaces the piece, Right then Left comes back,
a piece without quads on that side stays."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh, SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.topology import selection_steps as steps

WIDTH, HEIGHT = 800, 600
N = 4


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


GROW, SHRINK = _key("plus", "ctrl"), _key("minus", "ctrl")
UP, DOWN = _key("up", "shift"), _key("down", "shift")
RIGHT, LEFT = _key("right", "shift"), _key("left", "shift")
K1, K2, K3, K4 = _key("1"), _key("2"), _key("3"), _key("4")


def _grid(n: int = N, size: float = 4.0) -> Mesh:
    """n x n quads in the XY plane, unit cells from -2 to 2, facing +Z."""
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


def _cylinder(around: int = 6, rows: int = 3) -> Mesh:
    """An open quad tube: closed loops around, open loops along."""
    mesh = Mesh()
    p = {}
    for r in range(rows + 1):
        for k in range(around):
            a = 2.0 * math.pi * k / around
            p[(r, k)] = mesh.add_vertex((math.cos(a), float(r), math.sin(a)))
    for r in range(rows):
        for k in range(around):
            k1 = (k + 1) % around
            mesh.add_face([p[(r, k)], p[(r + 1, k)], p[(r + 1, k1)], p[(r, k1)]])
    return mesh


def _vertex(mesh, x: float, y: float):
    (vid,) = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (x, y)]
    return vid


def _edge(mesh, a, b):
    (eid,) = [e for e in mesh.vertex_edges(a) if set(mesh.edge_vertices(e)) == {a, b}]
    return eid


def _h_edge(mesh, x: float, y: float):
    """The horizontal edge from (x, y) to (x + 1, y)."""
    return _edge(mesh, _vertex(mesh, x, y), _vertex(mesh, x + 1.0, y))


def _v_edge(mesh, x: float, y: float):
    """The vertical edge from (x, y) to (x, y + 1)."""
    return _edge(mesh, _vertex(mesh, x, y), _vertex(mesh, x, y + 1.0))


def _face_at(mesh, x: float, y: float):
    """The quad whose lower-left corner is (x, y)."""
    corner = _vertex(mesh, x, y)
    (fid,) = [
        f for f in mesh.all_face_ids()
        if corner in mesh.face_vertices(f)
        and all(mesh.vertex_position(v)[0] >= x and mesh.vertex_position(v)[1] >= y for v in mesh.face_vertices(f))
    ]
    return fid


# -- Pure steps --------------------------------------------------------------------------


def test_grow_and_shrink_vertices():
    mesh = _grid()
    centre = _vertex(mesh, 0.0, 0.0)
    grown = steps.grow(mesh, SelectionMode.VERTEX, {centre})
    assert len(grown) == 5  # centre + 4 edge neighbours
    assert steps.shrink(mesh, SelectionMode.VERTEX, grown) == {centre}
    assert steps.shrink(mesh, SelectionMode.VERTEX, {centre}) == set()


def test_grow_edges_over_shared_vertices_and_faces_over_shared_vertices():
    mesh = _grid()
    edge = _h_edge(mesh, 0.0, 0.0)
    assert len(steps.grow(mesh, SelectionMode.EDGE, {edge})) == 7  # 3 + 3 at each end, + itself
    mesh = _grid(6, 6.0)  # the 3 x 3 block below stays off the border
    face = _face_at(mesh, 0.0, 0.0)
    grown = steps.grow(mesh, SelectionMode.FACE, {face})
    assert len(grown) == 9  # the 3 x 3 block around it (vertex neighbourhood, Blender default)
    assert steps.shrink(mesh, SelectionMode.FACE, grown) == {face}


def test_shrink_keeps_elements_on_the_mesh_border_when_their_neighbours_are_selected():
    mesh = _grid()
    everything = set(mesh.all_face_ids())
    assert steps.shrink(mesh, SelectionMode.FACE, everything) == everything


def test_loop_grow_extends_both_ends_and_stops_at_the_border():
    mesh = _grid()
    start = _h_edge(mesh, -1.0, 0.0)
    once = steps.loop_grow(mesh, {start})
    assert once == {_h_edge(mesh, -2.0, 0.0), start, _h_edge(mesh, 0.0, 0.0)}
    twice = steps.loop_grow(mesh, once)
    assert twice == once | {_h_edge(mesh, 1.0, 0.0)}  # the left end is on the border
    assert steps.loop_grow(mesh, twice) == twice


def test_loop_shrink_takes_both_ends_and_a_lone_edge():
    mesh = _grid()
    row = {_h_edge(mesh, x, 0.0) for x in (-2.0, -1.0, 0.0, 1.0)}
    assert steps.loop_shrink(mesh, row) == {_h_edge(mesh, -1.0, 0.0), _h_edge(mesh, 0.0, 0.0)}
    assert steps.loop_shrink(mesh, {_h_edge(mesh, 0.0, 0.0)}) == set()


def test_closed_loops_neither_grow_nor_shrink():
    mesh = _cylinder()
    ring = {e for e in mesh.all_edge_ids() if all(mesh.vertex_position(v)[1] == 1.0 for v in mesh.edge_vertices(e))}
    assert len(ring) == 6
    (piece,) = steps.loop_pieces(mesh, ring)
    assert piece.closed and len(piece.vertices) == 6
    assert steps.loop_grow(mesh, ring) == ring
    assert steps.loop_shrink(mesh, ring) == ring


def test_loop_pieces_are_ordered_vertex_runs():
    mesh = _grid()
    row = [_h_edge(mesh, x, 0.0) for x in (-1.0, 0.0, 1.0)]
    (piece,) = steps.loop_pieces(mesh, set(row))
    assert not piece.closed
    xs = [mesh.vertex_position(v)[0] for v in piece.vertices]
    assert xs in ([-1.0, 0.0, 1.0, 2.0], [2.0, 1.0, 0.0, -1.0])
    for i, edge in enumerate(piece.edges):
        assert set(mesh.edge_vertices(edge)) == set(steps.piece_edge_ends(piece, i))


def test_shifted_piece_reaches_both_neighbours_and_stops_at_the_border():
    mesh = _grid()
    row = {_h_edge(mesh, x, 0.0) for x in (-1.0, 0.0)}
    (piece,) = steps.loop_pieces(mesh, row)
    shifted = {frozenset(steps.shifted_piece(mesh, piece, left)) for left in (True, False)}
    assert shifted == {
        frozenset(_h_edge(mesh, x, 1.0) for x in (-1.0, 0.0)),
        frozenset(_h_edge(mesh, x, -1.0) for x in (-1.0, 0.0)),
    }
    border = {_h_edge(mesh, 0.0, 2.0)}
    (top,) = steps.loop_pieces(mesh, border)
    results = [steps.shifted_piece(mesh, top, left) for left in (True, False)]
    assert results.count(None) == 1


# -- App wiring --------------------------------------------------------------------------


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_grid().export_state())
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _select_edges(app, *edges) -> None:
    app.selection.mode = SelectionMode.EDGE
    app.selection.edges = set(edges)


def test_default_bindings():
    bs = build_default_bindings()
    assert bs.command_for(GROW) == cmd.SELECT_GROW
    assert bs.command_for(SHRINK) == cmd.SELECT_SHRINK
    assert bs.command_for(UP) == cmd.LOOP_GROW
    assert bs.command_for(DOWN) == cmd.LOOP_SHRINK
    assert bs.command_for(RIGHT) == cmd.LOOP_NEXT
    assert bs.command_for(LEFT) == cmd.LOOP_PREVIOUS


def test_grow_and_shrink_keys_change_the_selection_without_history(app):
    mesh = app.scene.mesh
    app.key_press(K1)
    centre = _vertex(mesh, 0.0, 0.0)
    app.selection.vertices = {centre}
    history = len(app.history)
    state = mesh.export_state()
    app.key_press(GROW)
    assert len(app.selection.vertices) == 5
    app.key_press(SHRINK)
    assert app.selection.vertices == {centre}
    assert mesh.export_state() == state
    assert len(app.history) == history


def test_loop_keys_need_edge_mode(app):
    app.key_press(K3)
    app.selection.faces = {_face_at(app.scene.mesh, 0.0, 0.0)}
    for key in (UP, DOWN, RIGHT, LEFT):
        app.key_press(key)
        assert "edge mode" in app.status_message
    assert len(app.selection.faces) == 1


def test_selection_steps_are_refused_in_object_mode(app):
    app.key_press(K4)
    for key in (GROW, SHRINK, UP, RIGHT):
        app.key_press(key)
        assert app.status_message.startswith("Object mode")


def test_shift_up_and_down_grow_and_shrink_the_loop_piece(app):
    mesh = app.scene.mesh
    start = _h_edge(mesh, 0.0, 0.0)
    _select_edges(app, start)
    app.key_press(UP)
    assert app.selection.edges == {_h_edge(mesh, -1.0, 0.0), start, _h_edge(mesh, 1.0, 0.0)}
    app.key_press(DOWN)
    assert app.selection.edges == {start}


def test_shift_right_then_left_returns_to_the_same_loop(app):
    mesh = app.scene.mesh
    row = {_h_edge(mesh, x, 0.0) for x in (-1.0, 0.0)}
    _select_edges(app, *row)
    app.key_press(RIGHT)
    moved = set(app.selection.edges)
    assert moved in (
        {_h_edge(mesh, x, 1.0) for x in (-1.0, 0.0)},
        {_h_edge(mesh, x, -1.0) for x in (-1.0, 0.0)},
    )
    app.key_press(LEFT)
    assert app.selection.edges == row
    app.key_press(LEFT)
    assert app.selection.edges not in (row, moved)


def test_shift_right_moves_towards_screen_right(app):
    mesh = app.scene.mesh
    column = {_v_edge(mesh, 0.0, y) for y in (-1.0, 0.0)}
    _select_edges(app, *column)
    centre_before = app._edges_screen_centre(column)
    app.key_press(RIGHT)
    centre_after = app._edges_screen_centre(app.selection.edges)
    assert centre_after[0] > centre_before[0]
    app.key_press(LEFT)
    app.key_press(LEFT)
    assert app._edges_screen_centre(app.selection.edges)[0] < centre_before[0]


def test_a_piece_on_the_border_stays_on_its_open_side(app):
    mesh = app.scene.mesh
    border = {_h_edge(mesh, x, 2.0) for x in (-1.0, 0.0)}
    _select_edges(app, *border)
    results = []
    for key in (RIGHT, LEFT):
        app.selection.edges = set(border)
        app.key_press(key)
        results.append(set(app.selection.edges))
    assert border in results
    assert any(r != border for r in results)
