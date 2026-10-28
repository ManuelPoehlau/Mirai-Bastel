"""Slice 3 (E23–E31), headless: click semantics per mode, click vs drag threshold, `1`/`2`/`3`,
curve presets on their new keys, Shift+L / Shift+R (incl. rim loop; Shift+R never arms Scale),
the E26 target rule (selection → seeds = selection vertices; empty → hover, results identical),
W/E/R and the LMB drag on a selection, Nachführen with selection seeds and after a selection
change, Undo/Redo keep the selection, `B` clears it, selection input ignored while busy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core import EdgeId, FaceId, SelectionMode, VertexId
from mehlsack_lab import lab_bindings as lb
from mehlsack_lab import lab_pointer
from mehlsack_lab import lab_state as ls
from mehlsack_lab.box import BoxParams
from mehlsack_lab.lab_pointer import PointerPress
from mehlsack_lab.lab_selection import (
    MODE_SELECTION,
    add_loop_ring,
    apply_click,
    selection_target,
)
from mehlsack_lab.signed_curve import PRESET_HAT, PRESET_SMOOTH
from mehlsack_lab.targets import MODE_LOOP, MODE_RING, Target
from mirai.interaction import pointer
from mirai.interaction.commands import SELECT, SELECT_ADD, SELECT_REMOVE, SELECT_TOGGLE
from mirai.interaction.tools.selection_helpers import resolve_selection_vertices
from mirai.viewport.camera import OrbitCamera

from .helpers import horizontal_edge, positions

# Archived 2026-10-28 (AD-013 addendum): the lab's table is still checked against that historical record.
TRUTH = (Path(lb.__file__).resolve().parents[2] / "docs" / "archive" / "input_truth_2026-10" / "Input_Mapping_Tool"
         / "artist_input_truth.json")
W, H = 800, 600
PARAMS = BoxParams(h=4, n=3)  # rows at y = 0, ±0.5, ±1


def edit_state(params=PARAMS) -> ls.LabState:
    state = ls.LabState(params)
    state.key("RETURN")
    return state


def hover(state, y: float = 0.0, mode: str = MODE_LOOP):
    state.hover_target = state.session.target(horizontal_edge(state.session.mesh, y), mode)
    return state.hover_target


def handles(mesh, mode):
    return {SelectionMode.VERTEX: mesh.all_vertex_ids, SelectionMode.EDGE: mesh.all_edge_ids,
            SelectionMode.FACE: mesh.all_face_ids}[mode]()


def selected(selection):
    return {SelectionMode.VERTEX: selection.vertices, SelectionMode.EDGE: selection.edges,
            SelectionMode.FACE: selection.faces}[selection.mode]


# -- E25 click semantics ------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", [SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE])
def test_click_semantics_per_mode(mode):
    state = edit_state()
    state.selection.mode = mode
    a, b, c = handles(state.session.mesh, mode)[:3]
    assert ls.SELECTION_CHANGED in state.click(SELECT, a)
    assert selected(state.selection) == {a}
    state.click(SELECT, b)  # replace
    assert selected(state.selection) == {b}
    state.click(SELECT_ADD, c)
    assert selected(state.selection) == {b, c}
    state.click(SELECT_REMOVE, b)
    assert selected(state.selection) == {c}
    state.click(SELECT_TOGGLE, a)
    state.click(SELECT_TOGGLE, c)
    assert selected(state.selection) == {a}
    # unchanged → no effect
    assert ls.SELECTION_CHANGED not in state.click(SELECT_ADD, a)
    assert ls.SELECTION_CHANGED not in state.click(SELECT_REMOVE, b)


def test_click_into_empty_space():
    state = edit_state()
    state.click(SELECT, VertexId(0))
    state.click(SELECT_ADD, VertexId(1))
    for command in (SELECT_ADD, SELECT_REMOVE, SELECT_TOGGLE):
        assert ls.SELECTION_CHANGED not in state.click(command, None)
        assert state.selection.vertices == {VertexId(0), VertexId(1)}
    out = state.click(SELECT, None)  # only SELECT clears
    assert ls.SELECTION_CHANGED in out and ls.PREVIEW_CHANGED in out
    assert state.selection.is_empty()


def test_apply_click_matches_the_app_and_refuses_other_commands():
    from core import Selection

    sel = Selection()
    assert apply_click(sel, SELECT, VertexId(3)) and sel.vertices == {VertexId(3)}
    assert not apply_click(sel, SELECT, VertexId(3))
    with pytest.raises(ValueError):
        apply_click(sel, "Orbit", None)


def test_clicks_only_in_the_edit_phase():
    state = ls.LabState()
    state.click(SELECT, VertexId(0))
    assert state.selection.is_empty()


# -- E24 click vs drag ----------------------------------------------------------------------------------


def test_threshold_is_read_from_the_app_resolver():
    assert lab_pointer.CLICK_THRESHOLD_PX is pointer.CLICK_THRESHOLD_PX
    assert PointerPress(SELECT, lb.DRAG_TARGET).threshold == pointer.CLICK_THRESHOLD_PX


def test_click_below_threshold_drag_at_threshold():
    press = PointerPress(SELECT, lb.DRAG_TARGET)
    assert press.motion(1.0, 1.0) == [] and press.motion(0.0, -2.0) == []  # 4 px: open
    assert press.release() == SELECT
    press = PointerPress(SELECT, lb.DRAG_TARGET)
    assert press.motion(1.0, 1.0) == [] and press.motion(2.0, -1.0) == [(1.0, 1.0), (2.0, -1.0)]
    assert press.dragging and press.motion(0.5, 0.0) == [(0.5, 0.0)]  # then one by one
    assert press.release() is None


def test_click_only_and_drag_only_presses():
    press = PointerPress(SELECT_ADD, None)  # Shift: only a click is bound
    assert press.motion(3.0, 0.0) == [] and press.release() == SELECT_ADD
    press = PointerPress(SELECT_ADD, None)
    press.motion(3.0, 3.0)
    assert not press.dragging and press.release() is None  # moved: no click, no drag
    press = PointerPress(None, lb.PAN)  # only a drag: no dead zone
    assert press.dragging and press.motion(1.0, 0.0) == [(1.0, 0.0)]


def test_click_bindings():
    assert lb.resolve_click(lb.PHASE_EDIT, "LEFT", frozenset()) == SELECT
    assert lb.resolve_click(lb.PHASE_EDIT, "LEFT", frozenset({"shift"})) == SELECT_ADD
    assert lb.resolve_click(lb.PHASE_EDIT, "LEFT", frozenset({"ctrl"})) == SELECT_REMOVE
    assert lb.resolve_click(lb.PHASE_EDIT, "LEFT", frozenset({"alt"})) == SELECT_TOGGLE
    assert lb.resolve_click(lb.PHASE_EDIT, "LEFT", frozenset({"alt", "shift"})) is None  # pan only
    assert lb.resolve_click(lb.PHASE_CREATE, "LEFT", frozenset()) is None
    assert lb.resolve_click(lb.PHASE_EDIT, "RIGHT", frozenset()) is None
    # the drags on the same button stay
    assert lb.resolve_drag(lb.PHASE_EDIT, {"LEFT"}, frozenset()) == lb.DRAG_TARGET
    assert lb.resolve_drag(lb.PHASE_EDIT, {"LEFT"}, frozenset({"alt"})) == lb.ORBIT


# -- E28 keys -----------------------------------------------------------------------------------------------


def test_mode_keys_set_the_mode_and_clear_like_the_app():
    state = edit_state()
    assert state.selection.mode is SelectionMode.VERTEX  # Core default
    state.click(SELECT, VertexId(0))
    for name, mode in (("_2", SelectionMode.EDGE), ("_3", SelectionMode.FACE), ("_1", SelectionMode.VERTEX)):
        out = state.key(name)
        assert ls.SELECTION_CHANGED in out and state.selection.mode is mode
        assert state.selection.is_empty()
    state.click(SELECT, VertexId(0))
    state.key("_1")  # the active mode too (app / Playground behaviour)
    assert state.selection.is_empty()


def test_presets_moved_off_the_mode_keys_to_keys_outside_the_truth():
    state = edit_state()
    state.key("_2")
    assert state.curve.preset == PRESET_SMOOTH  # `2` is the Edge mode now
    state.key("K", {"shift"})
    assert state.curve.preset == PRESET_HAT
    state.key("K")
    assert state.curve.preset == PRESET_SMOOTH
    truth = {b["binding"] for b in json.loads(TRUTH.read_text(encoding="utf-8"))["bindings"]}
    for binding in lb.LAB_OVERRIDES:
        if binding.action in (lb.PRESET_1, lb.PRESET_2):
            assert binding.gesture() not in truth and binding.value not in truth
    for gesture in ("1", "2", "3", "LMB Klick", "Shift+LMB Klick", "Ctrl+LMB Klick", "Alt+LMB Klick",
                    "Shift+L", "Shift+R"):
        assert any(b.gesture() == gesture and b.note.startswith("Artist Input Truth") for b in lb.LAB_OVERRIDES)


# -- E27 Loop / Ring select ------------------------------------------------------------------------------------


def test_shift_l_and_shift_r_add_loop_and_ring_in_edge_mode():
    state = edit_state()
    state.key("_2")
    target = hover(state)
    other = state.session.target(horizontal_edge(state.session.mesh, 0.5), MODE_LOOP)
    state.selection.add(set(other.edges))
    out = state.key("L", {"shift"})
    assert ls.SELECTION_CHANGED in out
    loop = state.session.target(target.edge, MODE_LOOP)
    assert state.selection.edges == set(loop.edges) | set(other.edges)  # added, not replaced
    state.key("R", {"shift"})
    ring = state.session.target(target.edge, MODE_RING)
    assert state.selection.edges == set(loop.edges) | set(other.edges) | set(ring.edges)
    assert not state.armed  # Shift+R never arms the Scale hold
    assert state.key_release("R").effects == set()
    assert ls.SELECTION_CHANGED not in state.key("L", {"shift"})  # already in
    assert "schon" in state.note


def test_loop_select_follows_the_hover_even_in_ring_mode_and_takes_the_rim_loop():
    state = edit_state(BoxParams(h=4, n=3))
    state.key("_2")
    state.key("TAB")  # hover shows rings; Shift+L still selects the loop
    mesh = state.session.mesh
    rim_edge = next(iter(state.session.finder.rim_of_edge))
    state.hover_target = state.session.target(rim_edge, MODE_RING)
    state.key("L", {"shift"})
    rim = state.session.finder.rim_of_edge[rim_edge]
    assert state.selection.edges == set(rim) and len(rim) == 4 * 3  # closed around the corners (E15)
    assert all(mesh.is_valid_edge(e) for e in rim)


def test_loop_select_in_vertex_mode_adds_vertices_and_face_mode_refuses():
    state = edit_state()
    target = hover(state)
    state.key("L", {"shift"})
    assert state.selection.mode is SelectionMode.VERTEX
    assert state.selection.vertices == set(state.session.target(target.edge, MODE_LOOP).seeds)
    state.key("_3")
    out = state.key("L", {"shift"})
    assert ls.SELECTION_CHANGED not in out and state.selection.is_empty()
    assert "Flächenmodus" in state.note
    state.key("_2")
    state.hover_target = None
    assert ls.SELECTION_CHANGED not in state.key("R", {"shift"}) and "keine Kante" in state.note


def test_add_loop_ring_rejects_unknown_kind():
    state = edit_state()
    with pytest.raises(ValueError):
        add_loop_ring(state.selection, state.session.finder, horizontal_edge(state.session.mesh, 0.0), "x")


# -- E26 target rule ----------------------------------------------------------------------------------------


def test_active_target_is_the_selection_else_the_hover():
    state = edit_state()
    target = hover(state)
    assert state.active_target is target and state.gesture_target(False) is target
    state.key("_3")
    faces = state.session.mesh.all_face_ids()[:2]
    state.selection.add(set(faces))
    active = state.active_target
    expected = resolve_selection_vertices(state.session.mesh, state.selection, SelectionMode.FACE)
    assert active.mode == MODE_SELECTION and active.seeds == frozenset(expected)
    assert active.edges == () and active.anchor == min(expected)  # MoveTool anchor rule
    assert state.gesture_target(True) == active
    assert state.gesture_target(False) is None  # with a selection: only pressed over the mesh
    state.click(SELECT, None)
    assert state.active_target is target


def test_hold_arms_on_the_selection_wherever_the_hover_is():
    state = edit_state()
    hover(state, 0.5)
    state.selection.add({VertexId(0), VertexId(5)})
    state.key("W")
    assert state.hold.target.seeds == {VertexId(0), VertexId(5)}
    state.cancel_drag()
    state.hover_target = None
    state.key("E")
    assert state.armed and state.hold.target.seeds == {VertexId(0), VertexId(5)}


def _hold(state, key, motions, cam):
    state.key(key)
    for dx, dy in motions:
        state.hold_motion(dx, dy, W, H, cam)
    state.key_release(key)


@pytest.mark.parametrize("key,motions", [("W", [(3, 4), (5, -2)]), ("E", [(12, 0), (7, 3)]),
                                         ("R", [(-15, -5), (-9, 0)])])
def test_gestures_on_the_selection_equal_a_target_with_those_seeds(key, motions):
    a = edit_state()
    a.key("_2")
    edges = {horizontal_edge(a.session.mesh, 0.5), horizontal_edge(a.session.mesh, -0.5)}
    a.selection.add(edges)
    hover(a, 0.0)  # a hover elsewhere: ignored
    _hold(a, key, motions, OrbitCamera())
    seeds = selection_target(a.session.mesh, a.selection).seeds
    assert a.session.last.seeds == seeds
    b = edit_state()
    b.hover_target = selection_target(b.session.mesh, a.selection)  # the same seeds as a hover
    _hold(b, key, motions, OrbitCamera())
    assert positions(a.session.mesh) == positions(b.session.mesh)
    start = positions(edit_state().session.mesh)
    assert all(a.session.mesh.vertex_position(v) != start[v] for v in seeds)


@pytest.mark.parametrize("key,motions", [("W", [(3, 4), (5, -2)]), ("E", [(12, 0), (7, 3)]),
                                         ("R", [(-15, -5), (-9, 0)])])
def test_empty_selection_gestures_are_unchanged(key, motions):
    """A selection made and cleared again leaves every hover gesture as before (E26)."""
    fresh = edit_state()
    hover(fresh)
    _hold(fresh, key, motions, OrbitCamera())
    used = edit_state()
    used.key("_3")
    used.click(SELECT, FaceId(2))
    used.click(SELECT, None)
    hover(used)
    _hold(used, key, motions, OrbitCamera())
    assert positions(fresh.session.mesh) == positions(used.session.mesh)
    assert used.session.last.seeds == fresh.session.last.seeds == fresh.hover_target.seeds


def test_lmb_drag_on_the_selection_and_without_one():
    state = edit_state()
    state.key("_2")
    edge = horizontal_edge(state.session.mesh, 0.5)
    state.click(SELECT, edge)
    start = positions(state.session.mesh)
    hover(state, 0.0)
    target = state.gesture_target(True)
    weights = state.begin_drag(target)
    state.drag_step((0.0, 0.25, 0.0))
    state.end_drag()
    ends = set(state.session.mesh.edge_vertices(edge))
    assert set(target.seeds) == ends and all(weights[v] == 1.0 for v in ends)
    for v in ends:
        assert state.session.mesh.vertex_position(v)[1] == start[v][1] + 0.25
    assert all(state.session.mesh.vertex_position(v) == start[v] for v in start if v not in weights)
    assert not state.hover_target.seeds <= set(weights)  # the hover loop is not the target
    # without a selection the same drag moves the hover target, as in Slices 1–2b
    plain = edit_state()
    plain_target = hover(plain, 0.0)
    assert plain.gesture_target(True) is plain_target and plain.gesture_target(False) is plain_target


# -- E30 Nachführen -----------------------------------------------------------------------------------------


def test_nachfuehren_with_selection_seeds_survives_a_selection_change():
    state = edit_state()
    for _ in range(5):  # a radius that reaches the neighbour rows, so the curve matters
        state.wheel(0, 1, {"shift"})
    state.key("_2")
    state.click(SELECT, horizontal_edge(state.session.mesh, 0.5))
    seeds = state.active_target.seeds
    cam = OrbitCamera()
    _hold(state, "W", [(0, 9)], cam)
    total = state.session.last.total
    state.click(SELECT, horizontal_edge(state.session.mesh, -0.5))  # change: no geometry, no end
    state.key("_1")
    assert state.session.can_retune and state.session.last.seeds == seeds
    out = state.key("K", {"shift"})
    assert ls.MESH_CHANGED in out and state.session.last.retunes == 1
    assert state.session.last.seeds == seeds  # the gesture keeps its frozen seeds
    assert len(state.session.history) == 1
    # = the same Move on the old seeds with the new curve from the start
    reference = edit_state()
    for _ in range(5):
        reference.wheel(0, 1, {"shift"})
    reference.key("K", {"shift"})
    reference.session.begin_drag(Target(MODE_SELECTION, None, (), False, seeds, min(seeds)),
                                 reference.world_radius, reference.metric, reference.curve)
    reference.session.step(total)
    reference.session.commit()
    assert positions(state.session.mesh) == positions(reference.session.mesh)
    # the preview shows the *new* (here empty) selection, not the retuned gesture
    assert state.active_target is None or state.active_target.seeds != seeds


# -- E31 lifecycle ------------------------------------------------------------------------------------------


def test_undo_redo_keep_the_selection_and_new_box_clears_it():
    state = edit_state()
    state.key("_2")
    state.click(SELECT, horizontal_edge(state.session.mesh, 0.5))
    _hold(state, "W", [(0, 9)], OrbitCamera())
    kept = set(state.selection.edges)
    state.key("Z", {"ctrl"})
    assert state.selection.edges == kept
    state.key("Y", {"ctrl"})
    assert state.selection.edges == kept
    state.key("B")
    out = state.key("B")
    assert ls.SELECTION_CHANGED in out and state.selection.is_empty()
    assert state.selection.mode is SelectionMode.EDGE  # the mode is sticky like the other settings


def test_selection_input_ignored_while_busy():
    state = edit_state()
    state.click(SELECT, VertexId(0))
    before = (state.selection.mode, set(state.selection.vertices))

    def unchanged():
        return (state.selection.mode, set(state.selection.vertices)) == before

    hover(state)
    state.key("W")  # armed
    for out in (state.click(SELECT, VertexId(1)), state.key("_2"), state.key("L", {"shift"})):
        assert ls.SELECTION_CHANGED not in out
    assert unchanged()
    state.hold_motion(0, 5, W, H, OrbitCamera())  # running
    state.click(SELECT_ADD, VertexId(2))
    state.key("_3")
    assert unchanged()
    state.key_release("W")
    state.begin_drag(state.active_target)  # LMB drag running
    state.click(SELECT_TOGGLE, VertexId(0))
    assert unchanged()
    state.end_drag()
    state.pointer_pending = True  # undecided LMB press
    state.click(SELECT, None)
    state.key("R")
    assert unchanged() and not state.armed
    state.pointer_pending = False
    state.click(SELECT, None)
    assert state.selection.is_empty()


def test_hud_names_the_rule():
    state = edit_state()
    texts = [line.text for line in state.hud_lines(None)]
    assert any("Auswahl (Punkte): leer" in t for t in texts)
    state.click(SELECT, VertexId(0))
    texts = [line.text for line in state.hud_lines(None)]
    assert any("1 gewählt" in t and "alle Gesten wirken auf die Auswahl" in t for t in texts)
    assert "Auswahl Punkte" in state.status_text()


def test_handles_are_core_ids():
    state = edit_state()
    state.key("_2")
    edge = horizontal_edge(state.session.mesh, 0.5)
    state.click(SELECT, edge)
    assert all(isinstance(e, EdgeId) for e in state.selection.edges)
