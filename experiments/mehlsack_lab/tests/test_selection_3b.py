"""Slice 3b (Manu 2026-10-13: O12, O13, O15, s2 ITERATE), headless: component hover target and the
empty-selection gestures on it, the `L` mode (toggle, whole Loop/Ring clicks incl. Toggle and
Face mode), double click = edge loop, Shift+double click = loop section / face loop, Shift+1/2/3
conversion ("touching"), the double-click tracker, the new bindings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import EdgeId, FaceId, SelectionMode, VertexId
from mehlsack_lab import lab_bindings as lb
from mehlsack_lab import lab_state as ls
from mehlsack_lab.box import BoxParams
from mehlsack_lab.curve_panel import DOUBLE_CLICK_PX, DOUBLE_CLICK_S
from mehlsack_lab.lab_pointer import ClickSeries
from mehlsack_lab.lab_selection import (
    MODE_COMPONENT,
    component_target,
    convert_selection,
    face_loop,
    loop_segment,
)
from mehlsack_lab.targets import MODE_LOOP, MODE_RING, Target
from mirai.interaction.commands import SELECT, SELECT_ADD, SELECT_REMOVE, SELECT_TOGGLE
from mirai.viewport.camera import OrbitCamera

from .helpers import horizontal_edge, positions

TRUTH = Path(lb.__file__).resolve().parents[2] / "tools" / "Input_Mapping_Tool" / "artist_input_truth.json"
PARAMS = BoxParams(h=4, n=3)  # rows at y = 0, ±0.5, ±1; 4n = 12 edges around


def edit_state(params=PARAMS) -> ls.LabState:
    state = ls.LabState(params)
    state.key("RETURN")
    return state


def wall_face(mesh, y_low, y_high):
    """A wall face between the rows `y_low` and `y_high`."""
    for fid in mesh.all_face_ids():
        ys = sorted(mesh.vertex_position(v)[1] for v in mesh.face_vertices(fid))
        if abs(ys[0] - y_low) < 1e-9 and abs(ys[-1] - y_high) < 1e-9:
            return fid
    raise LookupError


def neighbour_in_row(mesh, finder, face):
    """A face sharing a vertical edge with `face` (same row)."""
    for e in finder.index.edges_of_face[face]:
        a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(e))
        if abs(a[1] - b[1]) > 1e-9:  # vertical edge
            return next(f for f in finder.index.faces_of_edge[e] if f != face)
    raise LookupError


# -- component hover (O13) ------------------------------------------------------------------------------


def test_component_target_per_mode():
    state = edit_state()
    mesh = state.session.mesh
    v, e, f = VertexId(5), horizontal_edge(mesh, 0.5), mesh.all_face_ids()[3]
    tv = component_target(mesh, SelectionMode.VERTEX, v)
    assert (tv.mode, tv.seeds, tv.edges, tv.anchor, tv.edge) == (MODE_COMPONENT, {v}, (), v, None)
    te = component_target(mesh, SelectionMode.EDGE, e)
    assert te.seeds == set(mesh.edge_vertices(e)) and te.edges == (e,) and te.edge == e
    assert te.anchor == min(te.seeds)  # MoveTool anchor rule
    tf = component_target(mesh, SelectionMode.FACE, f)
    assert tf.seeds == set(mesh.face_vertices(f)) and tf.edges == () and tf.edge is None
    # a handle of another mode (ids are ints: EdgeId(5) == VertexId(5)) is no target
    assert component_target(mesh, SelectionMode.VERTEX, EdgeId(5)) is None
    assert component_target(mesh, SelectionMode.EDGE, None) is None


@pytest.mark.parametrize("key,motions", [("W", [(3, 4), (5, -2)]), ("E", [(12, 0)]), ("R", [(-15, -5)])])
def test_empty_selection_gestures_act_on_the_hovered_component(key, motions):
    a = edit_state()
    face = a.session.mesh.all_face_ids()[7]
    a.selection.mode = SelectionMode.FACE
    a.hover_target = component_target(a.session.mesh, SelectionMode.FACE, face)
    assert a.active_target is a.hover_target
    cam = OrbitCamera()
    a.key(key)
    for dx, dy in motions:
        a.hold_motion(dx, dy, 800, 600, cam)
    a.key_release(key)
    assert a.session.last.seeds == set(a.session.mesh.face_vertices(face))
    b = edit_state()
    seeds = frozenset(b.session.mesh.face_vertices(face))
    b.hover_target = Target("loop", None, (), False, seeds, min(seeds))
    b.key(key)
    for dx, dy in motions:
        b.hold_motion(dx, dy, 800, 600, cam)
    b.key_release(key)
    assert positions(a.session.mesh) == positions(b.session.mesh)


# -- L mode (O13) --------------------------------------------------------------------------------------


def test_l_toggles_the_loop_mode_and_is_ignored_while_busy():
    state = edit_state()
    assert not state.loop_mode  # component hover is the default
    state.selection.hovered = VertexId(1)
    out = state.key("L")
    assert state.loop_mode and ls.PREVIEW_CHANGED in out and state.selection.hovered is None
    assert "L-Modus" in state.status_text()
    state.key("L")
    assert not state.loop_mode
    state.hover_target = state.session.target(horizontal_edge(state.session.mesh, 0.0), MODE_LOOP)
    state.key("W")
    state.key("L")
    assert not state.loop_mode  # armed: ignored
    assert ("L", lb.PHASE_LABELS[lb.PHASE_EDIT]) in {(b.gesture(), lb.PHASE_LABELS[b.phase]) for b in lb.LAB_OVERRIDES}


def test_l_mode_clicks_take_whole_loops_and_rings():
    state = edit_state()
    state.key("L")
    state.key("_2")
    mesh = state.session.mesh
    loop = state.session.target(horizontal_edge(mesh, 0.5), MODE_LOOP)
    other = state.session.target(horizontal_edge(mesh, -0.5), MODE_LOOP)
    state.click_loop(SELECT, loop)
    assert state.selection.edges == set(loop.edges)
    state.click_loop(SELECT_ADD, other)
    assert state.selection.edges == set(loop.edges) | set(other.edges)
    state.click_loop(SELECT_REMOVE, loop)
    assert state.selection.edges == set(other.edges)
    state.click_loop(SELECT_TOGGLE, other)  # all selected → off
    assert state.selection.is_empty()
    state.selection.add({loop.edges[0]})
    state.click_loop(SELECT_TOGGLE, loop)  # partly selected → all on
    assert state.selection.edges == set(loop.edges)
    for command in (SELECT_ADD, SELECT_REMOVE, SELECT_TOGGLE):
        state.click_loop(command, None)
        assert state.selection.edges == set(loop.edges)
    state.click_loop(SELECT, None)
    assert state.selection.is_empty()
    state.key("_1")
    state.click_loop(SELECT, loop)
    assert state.selection.vertices == set(loop.seeds)
    state.key("_3")
    out = state.click_loop(SELECT, loop)
    assert state.selection.is_empty() and "Flächenmodus" in state.note and ls.SELECTION_CHANGED not in out


# -- double clicks (s2 ITERATE, O12) ---------------------------------------------------------------------


def test_double_click_selects_the_edge_loop_and_replaces():
    state = edit_state()
    state.key("_2")
    mesh = state.session.mesh
    other = horizontal_edge(mesh, -0.5)
    state.click(SELECT, other)
    edge = horizontal_edge(mesh, 0.5)
    state.click(SELECT, edge)  # first click of the double click
    out = state.double_click(lb.DOUBLE_LOOP, SELECT, edge)
    loop = state.session.target(edge, MODE_LOOP)
    assert ls.SELECTION_CHANGED in out and state.selection.edges == set(loop.edges) and len(loop.edges) == 12
    assert other not in state.selection.edges


def test_double_click_elsewhere_is_an_ordinary_click():
    state = edit_state()  # Vertex mode
    state.double_click(lb.DOUBLE_LOOP, SELECT, VertexId(3))
    assert state.selection.vertices == {VertexId(3)}
    state.key("_3")
    face = state.session.mesh.all_face_ids()[0]
    state.double_click(lb.DOUBLE_LOOP, SELECT, face)  # no plain double click in Face mode
    assert state.selection.faces == {face}
    state.key("_2")
    state.key("L")  # the L mode has no double click
    edge = horizontal_edge(state.session.mesh, 0.5)
    state.double_click(lb.DOUBLE_LOOP, SELECT, edge)
    assert state.selection.edges == {edge}
    state.key("L")
    state.double_click(None, SELECT_TOGGLE, edge)  # Alt / Ctrl: no double-click action
    assert state.selection.edges == set()


def _loop_edges(state, y):
    return state.session.target(horizontal_edge(state.session.mesh, y), MODE_LOOP).edges


def test_shift_double_click_adds_the_loop_section_from_the_previous_click():
    state = edit_state()
    state.key("_2")
    edges = _loop_edges(state, 0.5)  # closed, 12 edges, traversal order
    x, y = edges[1], edges[4]
    state.click(SELECT, x)
    state.click(SELECT_ADD, y)  # first click of the Shift+double click
    out = state.double_click(lb.DOUBLE_PART, SELECT_ADD, y)
    assert ls.SELECTION_CHANGED in out and state.selection.edges == set(edges[1:5])
    # closed loop: the shorter way round
    state.click(SELECT, edges[1])
    state.click(SELECT_ADD, edges[11])
    state.double_click(lb.DOUBLE_PART, SELECT_ADD, edges[11])
    assert state.selection.edges == {edges[1], edges[0], edges[11]}
    # not on the same loop: only the clicked edges, a note
    state.click(SELECT, edges[1])
    far = _loop_edges(state, -0.5)[0]
    state.click(SELECT_ADD, far)
    state.double_click(lb.DOUBLE_PART, SELECT_ADD, far)
    assert state.selection.edges == {edges[1], far} and "nicht im selben Loop" in state.note


def test_loop_segment_on_an_open_loop():
    state = edit_state()
    finder = state.session.finder
    mesh = state.session.mesh
    def corner_column(e):  # a vertical edge on a box corner: its loop stops at the valence-3 corners
        a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(e))
        return abs(a[1] - b[1]) > 0.1 and abs(abs(a[0]) - 1.0) < 1e-9 and abs(abs(a[2]) - 1.0) < 1e-9

    loop = finder.target(next(e for e in mesh.all_edge_ids() if corner_column(e)), MODE_LOOP)
    assert not loop.closed and len(loop.edges) == 4
    e = loop.edges
    assert loop_segment(finder, e[0], e[2]) == (e[0], e[1], e[2]) == loop_segment(finder, e[2], e[0])
    assert loop_segment(finder, horizontal_edge(mesh, 0.5), e[0]) is None


def test_shift_double_click_in_face_mode_adds_the_face_loop():
    state = edit_state()
    state.key("_3")
    mesh, finder = state.session.mesh, state.session.finder
    a = wall_face(mesh, 0.0, 0.5)
    b = neighbour_in_row(mesh, finder, a)
    state.click(SELECT, a)
    state.click(SELECT_ADD, b)
    out = state.double_click(lb.DOUBLE_PART, SELECT_ADD, b)
    assert ls.SELECTION_CHANGED in out
    faces = state.selection.faces
    assert len(faces) == 12  # the band around the box between y = 0 and 0.5
    for f in faces:
        ys = {round(mesh.vertex_position(v)[1], 9) for v in mesh.face_vertices(f)}
        assert ys == {0.0, 0.5}
    assert face_loop(finder, a, b) == face_loop(finder, a, b) and set(face_loop(finder, a, b)) == faces
    # not a neighbour: only the clicked faces
    state.click(SELECT, a)
    far = wall_face(mesh, -1.0, -0.5)
    state.click(SELECT_ADD, far)
    state.double_click(lb.DOUBLE_PART, SELECT_ADD, far)
    assert state.selection.faces == {a, far} and "keine Nachbarfläche" in state.note
    assert face_loop(finder, a, a) is None


def test_face_loop_direction_follows_the_neighbour():
    state = edit_state()
    mesh, finder = state.session.mesh, state.session.finder
    a = wall_face(mesh, 0.0, 0.5)
    # the face above `a` in the same column (shares a horizontal edge)
    above = next(f for f in mesh.all_face_ids()
                 if len(set(finder.index.edges_of_face[f]) & set(finder.index.edges_of_face[a])) == 1
                 and min(mesh.vertex_position(v)[1] for v in mesh.face_vertices(f)) > 0.4)
    column = face_loop(finder, a, above)
    xs = {round(mesh.vertex_position(v)[0], 9) for f in column for v in mesh.face_vertices(f)}
    assert len(column) > 2 and a in column and above in column
    assert len(xs) <= 2  # runs vertically (one column), not around the box


# -- conversion (O15, touching) ---------------------------------------------------------------------------


def test_convert_selection_touching():
    state = edit_state()
    mesh, index = state.session.mesh, state.session.finder.index
    sel = state.selection
    v = VertexId(10)
    sel.add({v})
    state.key("_2", {"shift"})
    assert sel.mode is SelectionMode.EDGE and sel.edges == set(index.edges_of_vertex[v])
    state.key("_1", {"shift"})
    assert sel.mode is SelectionMode.VERTEX
    assert sel.vertices == {u for e in index.edges_of_vertex[v] for u in mesh.edge_vertices(e)}
    sel.clear()
    sel.add({v})
    state.key("_3", {"shift"})
    assert sel.faces == {f for e in index.edges_of_vertex[v] for f in index.faces_of_edge[e]}
    faces = set(sel.faces)
    state.key("_2", {"shift"})
    assert sel.edges == {e for f in faces for e in index.edges_of_face[f]}
    edges = set(sel.edges)
    state.key("_3", {"shift"})
    assert sel.faces == {f for e in edges for f in index.faces_of_edge[e]}
    faces = set(sel.faces)
    state.key("_1", {"shift"})
    assert sel.vertices == {u for f in faces for u in mesh.face_vertices(f)}
    before = set(sel.vertices)
    state.key("_1", {"shift"})  # same mode: unchanged (no clear, unlike plain 1)
    assert sel.vertices == before


def test_convert_from_faces_to_vertices_and_empty():
    state = edit_state()
    mesh, index = state.session.mesh, state.session.finder.index
    face = mesh.all_face_ids()[4]
    state.key("_3")
    state.selection.add({face})
    convert_selection(mesh, index, state.selection, SelectionMode.VERTEX)
    assert state.selection.vertices == set(mesh.face_vertices(face)) and not state.selection.faces
    state.selection.clear()
    state.key("_2", {"shift"})
    assert state.selection.mode is SelectionMode.EDGE and state.selection.is_empty()


# -- double-click tracker and bindings --------------------------------------------------------------------


def test_click_series():
    clicks = ClickSeries()
    assert not clicks.click(SELECT, EdgeId(4), 10, 10, 0.0)
    assert clicks.click(SELECT, EdgeId(4), 11, 10, DOUBLE_CLICK_S * 0.5)
    assert not clicks.click(SELECT, EdgeId(4), 11, 10, 1.0)  # restarted after a double
    assert not clicks.click(SELECT, VertexId(4), 11, 10, 1.1)  # same int, other type
    assert not clicks.click(SELECT_ADD, VertexId(4), 11, 10, 1.15)  # other command
    assert not clicks.click(SELECT_ADD, VertexId(4), 11 + DOUBLE_CLICK_PX + 1, 10, 1.2)  # moved
    assert not clicks.click(SELECT_ADD, VertexId(4), 11 + DOUBLE_CLICK_PX + 1, 10, 1.2 + DOUBLE_CLICK_S + 0.1)
    clicks.click(SELECT, FaceId(1), 0, 0, 5.0)
    assert not clicks.click(SELECT, None, 0, 0, 5.1) and not clicks.click(SELECT, FaceId(1), 0, 0, 5.2)


def test_slice_3b_bindings():
    assert lb.resolve_key(lb.PHASE_EDIT, "L", frozenset()) == lb.LOOP_MODE
    assert lb.resolve_key(lb.PHASE_EDIT, "L", frozenset({"shift"})) == lb.LOOP_SELECT
    for name, action in (("_1", lb.CONVERT_VERTEX), ("_2", lb.CONVERT_EDGE), ("_3", lb.CONVERT_FACE)):
        assert lb.resolve_key(lb.PHASE_EDIT, name, frozenset({"shift"})) == action
    assert lb.resolve_double_click(lb.PHASE_EDIT, frozenset(), in_panel=False) == lb.DOUBLE_LOOP
    assert lb.resolve_double_click(lb.PHASE_EDIT, frozenset({"shift"}), in_panel=False) == lb.DOUBLE_PART
    assert lb.resolve_double_click(lb.PHASE_EDIT, frozenset({"ctrl"}), in_panel=False) is None
    assert lb.resolve_double_click(lb.PHASE_EDIT, frozenset(), in_panel=True) == lb.CURVE_RESET
    assert lb.resolve_double_click(lb.PHASE_CREATE, frozenset(), in_panel=False) is None
    truth = {b["binding"] for b in json.loads(TRUTH.read_text(encoding="utf-8"))["bindings"]}
    for gesture in ("L", "Shift+1", "Shift+2", "Shift+3", "Doppelklick", "Shift+Doppelklick"):
        assert any(b.gesture() == gesture for b in lb.LAB_OVERRIDES), gesture
        assert gesture not in truth  # no clash with the Artist Input Truth
