"""§7.6 Nachführen (E7 b) on `EditSession`: unchanged curve → no change; new curve → equals a
fresh gesture with that curve from the same start; History length unchanged; one Undo restores
the pre-gesture mesh; N off → weights fixed since `begin()` (state level)."""

from __future__ import annotations

from core import HistoryStack, OperationContext
from mehlsack_lab.edit_session import EditSession
from mehlsack_lab.lab_state import LabState, MESH_CHANGED
from mehlsack_lab.box import BoxParams, build_box_mesh
from mehlsack_lab.signed_curve import DEFAULT_CURVE, PRESET_HAT, SignedCurve
from mehlsack_lab.signed_influence import signed_influence
from mehlsack_lab.signed_ops import SignedSoftMoveOperation, VertexView

from .helpers import horizontal_edge, positions

PARAMS = BoxParams(height=2.0, width=1.5, h=10, n=5)
DELTAS = [(0.0, 0.05, 0.0), (0.01, 0.07, 0.0), (0.0, 0.11, -0.02), (0.0, 0.03, 0.0)]
HAT = SignedCurve.from_preset(PRESET_HAT)


def _session_after_gesture(curve=DEFAULT_CURVE, radius_step=7, metric="geodesic"):
    session = EditSession(build_box_mesh(PARAMS))
    start = positions(session.mesh)
    target = session.target(horizontal_edge(session.mesh, 0.0), "loop")
    radius = session.world_radius(radius_step)
    session.begin_drag(target, radius, metric, curve)
    for d in DELTAS:
        session.drag_step(d)
    assert session.commit() is not None
    return session, target, start, radius


def _fresh(target_seeds, total, radius, metric, curve):
    mesh = build_box_mesh(PARAMS)
    weights = signed_influence(mesh, target_seeds, radius, metric, curve)
    op = SignedSoftMoveOperation(OperationContext(
        target=mesh, selection=VertexView(set(weights)), history=HistoryStack(),
        params={"influence": weights}))
    op.begin()
    op.update(delta=total)
    op.commit()
    return mesh


def test_unchanged_settings_change_nothing():
    session, target, _, radius = _session_after_gesture()
    before = positions(session.mesh)
    assert session.retune(radius, "geodesic", DEFAULT_CURVE) is False
    assert session.retune(radius, "geodesic", SignedCurve(DEFAULT_CURVE.knots, DEFAULT_CURVE.handles_in, DEFAULT_CURVE.handles_out)) is False
    assert positions(session.mesh) == before and len(session.history) == 1


def test_new_curve_equals_a_fresh_gesture_and_replaces_the_entry():
    session, target, start, radius = _session_after_gesture()
    total = session.last.total
    assert session.retune(radius, "geodesic", HAT) is True
    expected = _fresh(target.seeds, total, radius, "geodesic", HAT)
    assert positions(session.mesh) == positions(expected)
    assert len(session.history) == 1 and not session.history.can_redo()
    assert session.last.retunes == 1
    session.history.undo()
    assert positions(session.mesh) == start


def test_new_radius_and_metric_also_retune():
    session, target, start, radius = _session_after_gesture(curve=HAT)
    total = session.last.total
    bigger = session.world_radius(9)
    assert session.retune(bigger, "geodesic", HAT)
    assert session.retune(bigger, "euclidean", HAT)
    assert positions(session.mesh) == positions(_fresh(target.seeds, total, bigger, "euclidean", HAT))
    assert len(session.history) == 1
    # back to the gesture's own settings: equals the one-step re-evaluation of them
    assert session.retune(radius, "geodesic", HAT)
    assert positions(session.mesh) == positions(_fresh(target.seeds, total, radius, "geodesic", HAT))
    assert len(session.history) == 1
    session.undo()
    assert positions(session.mesh) == start


def test_retune_reports_the_touched_vertices():
    session, target, _, radius = _session_after_gesture()
    old = set(session.last.weights)
    assert session.retune(session.world_radius(10), "geodesic", DEFAULT_CURVE)
    assert session.last_changed == old | set(session.last.weights)


def test_nachfuehren_ends_with_next_gesture_undo_redo():
    session, target, start, radius = _session_after_gesture()
    session.undo()
    assert not session.can_retune and session.retune(radius, "geodesic", HAT) is False
    session.redo()
    assert not session.can_retune
    session.begin_drag(target, radius, "geodesic", DEFAULT_CURVE)
    assert not session.can_retune
    session.cancel()
    assert not session.can_retune and len(session.history) == 1


def _state_after_gesture():
    state = LabState(PARAMS)
    state.key("RETURN")
    state.radius_step = 7
    target = state.session.target(horizontal_edge(state.session.mesh, 0.0), "loop")
    state.begin_drag(target)
    for d in DELTAS:
        state.drag_step(d)
    state.end_drag()
    return state, target


def test_state_with_n_on_retunes_on_preset_radius_and_curve_point():
    state, target = _state_after_gesture()
    assert state.nachfuehren
    out = state.key("_2")
    assert MESH_CHANGED in out and out.changed
    out = state.wheel(0, 1, {"shift"})
    assert MESH_CHANGED in out
    out = state.set_curve(state.curve.with_knot(4, 0.8, -0.8))
    assert MESH_CHANGED in out
    assert len(state.session.history) == 1


def test_state_with_n_off_keeps_the_gesture_weights_from_begin():
    state, target = _state_after_gesture()
    state.key("N")
    assert not state.nachfuehren
    before = positions(state.session.mesh)
    out = state.key("_2")
    assert MESH_CHANGED not in out
    assert positions(state.session.mesh) == before
    # switching N on again does not re-arm the old gesture
    state.key("N")
    assert MESH_CHANGED not in state.key("_1")
    assert positions(state.session.mesh) == before


def test_curve_change_during_a_drag_keeps_the_running_weights():
    """AD-020 E3 semantics: a running gesture keeps the weights it began with."""
    state = LabState(PARAMS)
    state.key("RETURN")
    target = state.session.target(horizontal_edge(state.session.mesh, 0.0), "loop")
    began = state.begin_drag(target)
    state.key("_2")
    assert state.session.drag.operation.weights == began
    state.drag_step((0.0, 0.1, 0.0))
    state.end_drag()
    assert state.session.last.weights == began
