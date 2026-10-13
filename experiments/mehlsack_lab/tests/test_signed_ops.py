"""§7.5 Signed Move op: bit-identical to `SoftMoveOperation` for weights in (0, 1]; negative `w`
moves by `w·Δ`; N steps == 1 step; commit → one History entry; cancel exact; Undo/Redo exact;
no Core private member (AST scan, the list of `tests/test_soft_selection_ops.py`)."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from core import HistoryStack, OperationContext, VertexId
from mehlsack_lab.edit_session import EditSession
from mehlsack_lab.signed_curve import PRESET_HAT, SignedCurve
from mehlsack_lab.signed_influence import signed_influence
from mehlsack_lab.signed_ops import SignedSoftMoveOperation, VertexView
from mirai.soft_selection import SoftMoveOperation, compute_influence
from mirai.soft_selection.settings import RADIUS_STEPS_PERCENT

from .helpers import box, mid_target, positions

STEPS = [(0.1, -0.03, 0.02), (0.07, 0.2, -0.1), (-0.3, 0.01, 0.0), (0.013, 0.0, 0.41)]


def _ctx(mesh, weights, history=None, **params):
    return OperationContext(
        target=mesh, selection=VertexView(set(weights)),
        history=history if history is not None else HistoryStack(),
        params={"influence": weights, **params},
    )


def _run(op, steps):
    op.begin()
    for delta in steps:
        op.update(delta=delta)
    return op.commit()


def _case(curve=None, radius=1.2, metric="geodesic"):
    mesh = box(h=8, n=4)
    _, target = mid_target(mesh)
    if curve is None:
        weights = compute_influence(mesh, target.seeds, radius, metric=metric, curve="smooth")
    else:
        weights = signed_influence(mesh, target.seeds, radius, metric, curve)
    return mesh, target, weights


@pytest.mark.parametrize("metric", ["geodesic", "euclidean"])
@pytest.mark.parametrize("radius", [0.0, 0.6, 1.2, 3.0])
def test_positive_weights_bit_identical_to_soft_move(metric, radius):
    mesh_a, _, weights = _case(radius=radius, metric=metric)
    mesh_b = box(h=8, n=4)
    assert all(0.0 < w <= 1.0 for w in weights.values())
    cmd_a = _run(SignedSoftMoveOperation(_ctx(mesh_a, weights)), STEPS)
    cmd_b = _run(SoftMoveOperation(_ctx(mesh_b, weights, pivot=(0.0, 0.0, 0.0))), STEPS)
    assert positions(mesh_a) == positions(mesh_b)
    assert cmd_a.start_positions == cmd_b.start_positions
    assert cmd_a.end_positions == cmd_b.end_positions


def test_negative_weight_moves_opposite_by_w_delta():
    mesh, _, weights = _case(SignedCurve.from_preset(PRESET_HAT), radius=2.0)
    start = positions(mesh)
    delta = (0.0, 0.5, 0.0)
    _run(SignedSoftMoveOperation(_ctx(mesh, weights)), [delta])
    negatives = [v for v, w in weights.items() if w < 0.0]
    assert negatives
    for vid, w in weights.items():
        expected = tuple(s + w * d for s, d in zip(start[vid], delta))
        assert mesh.vertex_position(vid) == expected
    for vid in negatives:
        assert mesh.vertex_position(vid)[1] < start[vid][1]  # dragged up, moved down
    untouched = set(start) - set(weights)
    assert all(mesh.vertex_position(v) == start[v] for v in untouched)


def test_n_steps_equal_one_step():
    mesh_a, _, weights = _case(SignedCurve.from_preset(PRESET_HAT), radius=2.0)
    mesh_b = box(h=8, n=4)
    total = (0.31, -0.12, 0.05)
    n = 17
    _run(SignedSoftMoveOperation(_ctx(mesh_a, weights)), [total])
    _run(SignedSoftMoveOperation(_ctx(mesh_b, weights)), [tuple(c / n for c in total)] * n)
    a, b = positions(mesh_a), positions(mesh_b)
    assert all(math.dist(a[v], b[v]) <= 1e-12 for v in a)


def test_commit_one_entry_cancel_exact_undo_redo_exact():
    mesh, _, weights = _case(SignedCurve.from_preset(PRESET_HAT), radius=2.0)
    start = positions(mesh)
    history = HistoryStack()
    op = SignedSoftMoveOperation(_ctx(mesh, weights, history))
    op.begin()
    for d in STEPS:
        op.update(delta=d)
    op.cancel()
    assert positions(mesh) == start and len(history) == 0

    command = _run(SignedSoftMoveOperation(_ctx(mesh, weights, history)), STEPS)
    end = positions(mesh)
    assert len(history) == 1 and command.description == "Signed Soft Move Vertices"
    assert set(command.start_positions) == set(weights)
    history.undo()
    assert positions(mesh) == start
    history.redo()
    assert positions(mesh) == end


def test_base_never_blends_one_update_equals_the_closed_form():
    """Tripwire (AD-020 F3 row 1): the Core keeps its `_weights` placeholder at 1.0."""
    mesh, _, weights = _case(SignedCurve.from_preset(PRESET_HAT), radius=2.0)
    start = positions(mesh)
    delta = STEPS[0]
    _run(SignedSoftMoveOperation(_ctx(mesh, weights)), [delta])
    for vid, w in weights.items():
        assert mesh.vertex_position(vid) == tuple(s + w * d for s, d in zip(start[vid], delta))


@pytest.mark.parametrize("bad", [0.0, -1.5, 1.5, math.nan, math.inf])
def test_weights_outside_signed_range_refused(bad):
    mesh, _, weights = _case()
    vid = next(iter(weights))
    with pytest.raises(ValueError, match="weight"):
        SignedSoftMoveOperation(_ctx(mesh, {**weights, vid: bad})).begin()


def test_minus_one_is_allowed_and_view_must_match():
    mesh, _, weights = _case()
    vid = next(v for v, w in weights.items() if w < 1.0)
    SignedSoftMoveOperation(_ctx(mesh, {**weights, vid: -1.0})).begin()
    extra = next(v for v in mesh.all_vertex_ids() if v not in weights)
    op = SignedSoftMoveOperation(OperationContext(
        target=mesh, selection=VertexView(set(weights) | {extra}), history=HistoryStack(),
        params={"influence": weights}))
    with pytest.raises(ValueError, match="influenced vertex set"):
        op.begin()


def test_stale_ids_skipped_symmetry_and_missing_influence_refused():
    mesh, _, weights = _case()
    stale = VertexId(10**6)
    op = SignedSoftMoveOperation(_ctx(mesh, {**weights, stale: -0.5}))
    op.begin()
    assert stale not in op.vertex_ids and op.vertex_ids == set(weights)
    op.cancel()
    with pytest.raises(ValueError, match="symmetry"):
        SignedSoftMoveOperation(_ctx(mesh, weights, symmetry=None)).begin()
    with pytest.raises(ValueError, match="influence"):
        SignedSoftMoveOperation(OperationContext(
            target=mesh, selection=VertexView(set()), history=HistoryStack())).begin()


# -- no Core private member in the lab (AD-020 Q2-D, handoff §6) ----------------------------

_LAB_DIR = Path(__file__).resolve().parent.parent
#: The P-D scan list of AD-020 §3.2, as in `tests/test_soft_selection_ops.py`.
_CORE_PRIVATES = {
    "_weights", "_start_positions", "_vertex_ids", "_pivot", "_mesh", "_apply", "_as_triple",
    "_add", "_sub", "_scale", "_dot", "_cross", "_length", "_mirror_vector", "_project_onto_plane",
}


def test_no_core_private_member_in_the_lab():
    sources = sorted(_LAB_DIR.glob("*.py"))
    assert any(p.name == "signed_ops.py" for p in sources)
    offenders = []
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in _CORE_PRIVATES:
                offenders.append(f"{path.name}:{node.lineno} .{node.attr}")
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "core":
                offenders += [f"{path.name}:{node.lineno} import {a.name}" for a in node.names
                              if a.name.startswith("_")]
    assert not offenders, offenders


def test_own_state_uses_the_mehlsack_prefix():
    """Every attribute the signed ops set on `self` (Move, Rotate, Scale and their base)."""
    tree = ast.parse((_LAB_DIR / "signed_ops.py").read_text(encoding="utf-8"))
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name != "VertexView"]
    assert {c.name for c in classes} >= {
        "SignedSoftMoveOperation", "SignedSoftRotateOperation", "SignedSoftScaleOperation"}
    assigned = {
        t.attr for cls in classes for node in ast.walk(cls) if isinstance(node, (ast.Assign, ast.AnnAssign))
        for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self"
    }
    assert assigned and all(a.startswith("_mehlsack_") for a in assigned), assigned
    assert {"_mehlsack_weights", "_mehlsack_start", "_mehlsack_total", "_mehlsack_formula"} <= assigned


def test_deep_curve_weights_are_accepted_by_the_op():
    """Regression (Slice 2b): a curve with knots at -1 must not produce |w| > 1."""
    session = EditSession(box(h=12, n=6, height=3.0))  # the case that raised: 2 × 3 × 2, 50 %
    mesh = session.mesh
    _, target = mid_target(mesh)
    deep = SignedCurve.from_knots((0.3, -1.0, -1.0, -0.5))
    radius = session.world_radius(RADIUS_STEPS_PERCENT.index(50))
    weights = signed_influence(mesh, target.seeds, radius, "geodesic", deep)
    assert min(weights.values()) == -1.0
    _run(SignedSoftMoveOperation(_ctx(mesh, weights)), [(0.0, 0.1, 0.0)])
