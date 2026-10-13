"""Slice 3c (Manu 2026-10-13: O17, O18, t3 ITERATE, edge-ring note), headless: the `L`-mode
click in Face mode takes the Ring's faces; double click in Vertex mode = the loop of the edge on
the cursor's side; Shift+double click on an edge = Ring (neighbour of the previous click) /
section (same loop) / another whole loop; face loop sections; the helper rules."""

from __future__ import annotations

from core import SelectionMode, VertexId
from mehlsack_lab import lab_bindings as lb
from mehlsack_lab import lab_state as ls
from mehlsack_lab.box import BoxParams
from mehlsack_lab.lab_selection import face_loop_section, ring_faces, ring_neighbours
from mehlsack_lab.targets import MODE_LOOP, MODE_RING
from mirai.interaction.commands import SELECT, SELECT_ADD, SELECT_REMOVE, SELECT_TOGGLE

from .helpers import horizontal_edge

PARAMS = BoxParams(h=4, n=3)  # rows at y = 0, ±0.5, ±1; 4n = 12 edges around


def edit_state() -> ls.LabState:
    state = ls.LabState(PARAMS)
    state.key("RETURN")
    return state


def ring_neighbour(finder, edge):
    """An edge opposite `edge` in one of its quads."""
    index = finder.index
    for f in index.faces_of_edge[edge]:
        edges = index.edges_of_face[f]
        return edges[(edges.index(edge) + 2) % 4]


def ys(mesh, face):
    return {round(mesh.vertex_position(v)[1], 9) for v in mesh.face_vertices(face)}


# -- O17: L mode in Face mode --------------------------------------------------------------------------


def test_l_mode_face_click_takes_the_faces_of_the_ring():
    state = edit_state()
    state.key("L")
    state.key("_3")
    mesh, finder = state.session.mesh, state.session.finder
    edge = horizontal_edge(mesh, 0.5)
    ring = state.session.target(edge, MODE_RING)
    faces, closed = ring_faces(finder, edge)
    assert closed and len(faces) == len(ring.edges)  # a closed column over both caps
    state.click_loop(SELECT, ring)
    assert state.selection.faces == set(faces)
    state.click_loop(SELECT_REMOVE, ring)
    assert state.selection.is_empty()
    state.click_loop(SELECT_TOGGLE, ring)
    assert state.selection.faces == set(faces)
    # a horizontal band: the Ring of a vertical wall edge
    vertical = next(e for e in mesh.all_edge_ids()
                    if {round(mesh.vertex_position(v)[1], 9) for v in mesh.edge_vertices(e)} == {0.0, 0.5})
    band, band_closed = ring_faces(finder, vertical)
    assert band_closed and len(band) == 12 and all(ys(mesh, f) == {0.0, 0.5} for f in band)


# -- O18: double click in Vertex mode ---------------------------------------------------------------------


def test_vertex_double_click_selects_the_loop_on_the_cursor_side():
    state = edit_state()
    mesh = state.session.mesh
    edge = horizontal_edge(mesh, 0.5)
    vertex = mesh.edge_vertices(edge)[0]
    state.click(SELECT, vertex)
    state.edge_under_cursor = edge  # the window picks it at the double click
    out = state.double_click(lb.DOUBLE_LOOP, SELECT, vertex)
    loop = state.session.target(edge, MODE_LOOP)
    assert ls.SELECTION_CHANGED in out and state.selection.vertices == set(loop.seeds)
    assert len(loop.seeds) == 12 and state.edge_under_cursor is None
    # an edge not at that vertex (or none): an ordinary click and a hint
    other = horizontal_edge(mesh, -0.5)
    state.click(SELECT, vertex)
    state.edge_under_cursor = other
    state.double_click(lb.DOUBLE_LOOP, SELECT, vertex)
    assert state.selection.vertices == {vertex} and "neben dem Punkt" in state.note
    state.double_click(lb.DOUBLE_LOOP, SELECT, VertexId(vertex))
    assert state.selection.vertices == {vertex}


# -- t3 ITERATE and the edge-ring note ---------------------------------------------------------------------


def test_shift_double_click_on_a_ring_neighbour_adds_the_ring_and_more_rings():
    state = edit_state()
    state.key("_2")
    finder = state.session.finder
    x = horizontal_edge(state.session.mesh, 0.5)
    y = ring_neighbour(finder, x)
    assert ring_neighbours(finder, x, y) and not ring_neighbours(finder, x, x)
    state.click(SELECT, x)
    state.click(SELECT_ADD, y)
    state.double_click(lb.DOUBLE_PART, SELECT_ADD, y)
    ring = set(state.session.target(y, MODE_RING).edges)
    assert state.selection.edges == ring and "Edge Ring" in state.note
    # the same method adds another ring
    x2 = next(e for e in state.session.target(x, MODE_LOOP).edges if e not in ring)
    y2 = ring_neighbour(finder, x2)
    state.click(SELECT_ADD, x2)
    state.click(SELECT_ADD, y2)
    state.double_click(lb.DOUBLE_PART, SELECT_ADD, y2)
    assert state.selection.edges == ring | set(state.session.target(y2, MODE_RING).edges)


def test_with_loops_selected_shift_double_click_adds_another_loop():
    """t3: after a double click (anchors cleared) a Shift+double click adds the next whole loop —
    also on the parallel loop right next to the last one (no Ring there: no fresh single click)."""
    state = edit_state()
    state.key("_2")
    mesh = state.session.mesh
    x = horizontal_edge(mesh, 0.5)
    state.click(SELECT, x)
    state.double_click(lb.DOUBLE_LOOP, SELECT, x)
    first = set(state.session.target(x, MODE_LOOP).edges)
    y = ring_neighbour(state.session.finder, x)  # on the parallel loop
    state.click(SELECT_ADD, y)
    state.double_click(lb.DOUBLE_PART, SELECT_ADD, y)
    second = set(state.session.target(y, MODE_LOOP).edges)
    assert state.selection.edges == first | second and "Edge Loop dazu" in state.note


def test_section_still_wins_on_the_same_loop():
    state = edit_state()
    state.key("_2")
    edges = state.session.target(horizontal_edge(state.session.mesh, 0.5), MODE_LOOP).edges
    state.click(SELECT, edges[2])
    state.click(SELECT_ADD, edges[5])
    state.double_click(lb.DOUBLE_PART, SELECT_ADD, edges[5])
    assert state.selection.edges == set(edges[2:6])


# -- O18: face loop sections -------------------------------------------------------------------------------


def test_face_loop_section():
    state = edit_state()
    state.key("_3")
    mesh, finder = state.session.mesh, state.session.finder
    vertical = next(e for e in mesh.all_edge_ids()
                    if {round(mesh.vertex_position(v)[1], 9) for v in mesh.edge_vertices(e)} == {0.0, 0.5})
    band, _ = ring_faces(finder, vertical)  # closed, 12 faces
    a, c = band[0], band[3]
    assert face_loop_section(finder, a, c) == band[0:4]
    assert face_loop_section(finder, a, band[11]) == (band[0], band[11])  # the shorter way
    assert face_loop_section(finder, a, a) is None
    state.click(SELECT, a)
    state.click(SELECT_ADD, c)
    state.double_click(lb.DOUBLE_PART, SELECT_ADD, c)
    assert state.selection.faces == set(band[0:4]) and "Teilstück" in state.note
    # a direct neighbour still gives the whole face loop (t4 KEEP)
    state.click(SELECT, a)
    state.click(SELECT_ADD, band[1])
    state.double_click(lb.DOUBLE_PART, SELECT_ADD, band[1])
    assert state.selection.faces == set(band)
    assert state.selection.mode is SelectionMode.FACE
