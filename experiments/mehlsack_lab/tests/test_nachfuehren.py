"""§7.6 Nachführen (E7 b; Slice 2b E21: Rotate/Scale incl. the formula switch) on `EditSession`:
unchanged curve → no change; new curve → equals a fresh gesture with that curve from the same
start; History length unchanged; one Undo restores the pre-gesture mesh; N off → weights fixed
since `begin()` (state level)."""

from __future__ import annotations

import pytest

from core import HistoryStack, OperationContext
from mehlsack_lab.edit_session import ROTATE, SCALE, EditSession
from mehlsack_lab.lab_state import LabState, MESH_CHANGED
from mehlsack_lab.box import BoxParams, build_box_mesh
from mehlsack_lab.signed_curve import DEFAULT_CURVE, PRESET_HAT, SignedCurve
from mehlsack_lab.signed_influence import signed_influence
from mehlsack_lab.signed_ops import (
    SignedSoftMoveOperation,
    SignedSoftRotateOperation,
    SignedSoftScaleOperation,
    VertexView,
)
from mirai.soft_selection import RADIUS_STEPS_PERCENT, primary_pivot

from .helpers import horizontal_edge, positions

#: The radius steps by percent (the shared list got finer on 2026-10-22; 50 % was index 7 before).
_STEP_50 = RADIUS_STEPS_PERCENT.index(50)

PARAMS = BoxParams(height=2.0, width=1.5, h=10, n=5)
DELTAS = [(0.0, 0.05, 0.0), (0.01, 0.07, 0.0), (0.0, 0.11, -0.02), (0.0, 0.03, 0.0)]
HAT = SignedCurve.from_preset(PRESET_HAT)


def _session_after_gesture(curve=DEFAULT_CURVE, radius_step=_STEP_50, metric="geodesic"):
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
    bigger = session.world_radius(RADIUS_STEPS_PERCENT.index(100))
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
    assert session.retune(session.world_radius(RADIUS_STEPS_PERCENT.index(150)), "geodesic", DEFAULT_CURVE)
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
    state.radius_step = _STEP_50
    target = state.session.target(horizontal_edge(state.session.mesh, 0.0), "loop")
    state.begin_drag(target)
    for d in DELTAS:
        state.drag_step(d)
    state.end_drag()
    return state, target


def test_state_with_n_on_retunes_on_preset_radius_and_curve_point():
    state, target = _state_after_gesture()
    assert state.nachfuehren
    out = state.key("K", {"shift"})
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
    out = state.key("K", {"shift"})
    assert MESH_CHANGED not in out
    assert positions(state.session.mesh) == before
    # switching N on again does not re-arm the old gesture
    state.key("N")
    assert MESH_CHANGED not in state.key("K")
    assert positions(state.session.mesh) == before


def test_curve_change_during_a_drag_keeps_the_running_weights():
    """AD-020 E3 semantics: a running gesture keeps the weights it began with."""
    state = LabState(PARAMS)
    state.key("RETURN")
    target = state.session.target(horizontal_edge(state.session.mesh, 0.0), "loop")
    began = state.begin_drag(target)
    state.key("K", {"shift"})
    assert state.session.drag.operation.weights == began
    state.drag_step((0.0, 0.1, 0.0))
    state.end_drag()
    assert state.session.last.weights == began


# -- Slice 2b E21: Nachführen for Rotate and Scale (incl. the formula switch) -----------------

AXIS = (0.0, 1.0, 0.0)
ANGLES = [0.1, 0.07, -0.02, 0.2]
FACTORS = [(1.1, 1.0, 1.1), (1.2, 1.0, 1.2), (0.95, 1.0, 0.95)]


def _session_after(kind, curve=DEFAULT_CURVE, formula="linear", radius_step=_STEP_50):
    session = EditSession(build_box_mesh(PARAMS))
    start = positions(session.mesh)
    target = session.target(horizontal_edge(session.mesh, 0.0), "loop")
    radius = session.world_radius(radius_step)
    session.begin_gesture(kind, target, radius, "geodesic", curve, axis=AXIS, formula=formula)
    for step in (ANGLES if kind == ROTATE else FACTORS):
        session.step(step)
    assert session.commit() is not None
    return session, target, start, radius


def _fresh_signed(kind, seeds, total, radius, curve, formula):
    mesh = build_box_mesh(PARAMS)
    weights = signed_influence(mesh, seeds, radius, "geodesic", curve)
    params = {"influence": weights, "pivot": primary_pivot(mesh, seeds)}
    if kind == SCALE:
        params["scale_formula"] = formula
    cls = SignedSoftRotateOperation if kind == ROTATE else SignedSoftScaleOperation
    op = cls(OperationContext(target=mesh, selection=VertexView(set(weights)), history=HistoryStack(),
                              params=params))
    op.begin()
    op.update(axis=AXIS, angle=total) if kind == ROTATE else op.update(factor=total)
    op.commit()
    return mesh


@pytest.mark.parametrize("kind", [ROTATE, SCALE])
def test_rotate_scale_retune_equals_a_fresh_gesture_from_the_same_start(kind):
    session, target, start, radius = _session_after(kind)
    assert session.last.kind == kind and session.last.pivot == primary_pivot(build_box_mesh(PARAMS), target.seeds)
    assert session.retune(radius, "geodesic", HAT, "linear") is True
    fresh = _fresh_signed(kind, target.seeds, session.last.total, radius, HAT, "linear")
    assert positions(session.mesh) == positions(fresh)
    assert len(session.history) == 1 and session.last.retunes == 1
    session.history.undo()
    assert positions(session.mesh) == start


def test_scale_formula_switch_retunes_the_last_scale():
    session, target, start, radius = _session_after(SCALE, curve=HAT)
    linear = positions(session.mesh)
    assert session.retune(radius, "geodesic", HAT, "power") is True
    fresh = _fresh_signed(SCALE, target.seeds, session.last.total, radius, HAT, "power")
    assert positions(session.mesh) == positions(fresh) != linear
    assert session.last.formula == "power" and len(session.history) == 1
    assert session.retune(radius, "geodesic", HAT, "power") is False  # unchanged → no change
    assert session.retune(radius, "geodesic", HAT, "linear") is True
    back = _fresh_signed(SCALE, target.seeds, session.last.total, radius, HAT, "linear")
    assert positions(session.mesh) == positions(back)
    session.history.undo()
    assert positions(session.mesh) == start


def test_formula_does_not_touch_a_rotate_or_move_gesture():
    session, _, _, radius = _session_after(ROTATE, curve=HAT)
    before = positions(session.mesh)
    assert session.retune(radius, "geodesic", HAT, "power") is False
    assert positions(session.mesh) == before and session.last.formula is None


def test_total_is_what_the_steps_accumulated():
    session, _, _, _ = _session_after(ROTATE)
    assert session.last.total == pytest.approx(sum(ANGLES)) and session.last.axis == AXIS
    session, _, _, _ = _session_after(SCALE)
    assert session.last.total == pytest.approx((1.1 * 1.2 * 0.95, 1.0, 1.1 * 1.2 * 0.95))
