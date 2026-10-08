"""Soft Move/Rotate/Scale: lifecycle, radius-0 identity, path independence (handoff §6)."""

from __future__ import annotations

import math

import pytest

from core import (
    HistoryStack,
    MoveOperation,
    OperationContext,
    RotateOperation,
    ScaleOperation,
    Selection,
    SelectionMode,
    VertexId,
)
from core.operations.transform import rotate_around_axis
from mesh_invariants import assert_mesh_invariants

from soft_selection.influence import compute_influence, primary_pivot
from soft_selection.weighted_ops import (
    SoftMoveOperation,
    SoftRotateOperation,
    SoftScaleOperation,
    _InfluenceView,
    soft_context,
)

from ._fixtures import grid, head

TOL = 1e-12
SOFT_OPS = (SoftMoveOperation, SoftRotateOperation, SoftScaleOperation)

#: A tilted orthonormal basis (rotation of the world axes about z by 30 degrees).
_C, _S = math.cos(math.pi / 6), math.sin(math.pi / 6)
TILTED = ((_C, _S, 0.0), (-_S, _C, 0.0), (0.0, 0.0, 1.0))


def _positions(mesh):
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


def _close(a, b, tol=TOL):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _head_case(radius=1.0, metric="euclidean", curve="smooth"):
    """Head mesh, a 5-vertex primary selection, its influence and pivot."""
    mesh = head()
    first = mesh.all_vertex_ids()[100]
    seeds = {first}
    for eid in mesh.vertex_edges(first):
        seeds.update(mesh.edge_vertices(eid))
    influence = compute_influence(mesh, seeds, radius, metric=metric, curve=curve)
    return mesh, seeds, influence, primary_pivot(mesh, seeds)


def _ctx(mesh, influence, pivot, history=None, **params):
    return OperationContext(
        target=mesh,
        selection=_InfluenceView(set(influence)),
        history=history if history is not None else HistoryStack(),
        params={"influence": influence, "pivot": pivot, **params},
    )


def _run(op, steps):
    op.begin()
    for kwargs in steps:
        op.update(**kwargs)
    return op.commit()


MOVE_STEPS = [{"delta": (0.1, -0.03, 0.02)}, {"delta": (0.07, 0.2, -0.1)}, {"delta": (-0.3, 0.01, 0.0)}]
ROTATE_STEPS = [{"axis": (0.2, 1.0, 0.1), "angle": 0.3}, {"axis": (0.2, 1.0, 0.1), "angle": -0.11},
                {"axis": (1.0, 0.0, 0.0), "angle": 0.7}]
SCALE_STEPS = [{"factor": 1.3}, {"factor": (0.9, 1.0, 1.2)}, {"factor": 0.7}]
SCALE_BASIS_STEPS = [{"factor": (1.4, 1.0, 1.0), "basis": TILTED}, {"factor": (0.8, 1.0, 1.0), "basis": TILTED}]


# -- radius 0 == Core, bit for bit ------------------------------------------------


@pytest.mark.parametrize(
    "soft_cls,core_cls,steps",
    [
        (SoftMoveOperation, MoveOperation, MOVE_STEPS),
        (SoftRotateOperation, RotateOperation, ROTATE_STEPS),
        (SoftScaleOperation, ScaleOperation, SCALE_STEPS),
        (SoftScaleOperation, ScaleOperation, SCALE_BASIS_STEPS),
    ],
)
def test_radius_zero_is_bit_identical_to_core(soft_cls, core_cls, steps):
    mesh_soft, seeds, _, pivot = _head_case()
    mesh_core = head()
    influence = compute_influence(mesh_soft, seeds, 0.0)
    assert influence == {s: 1.0 for s in seeds}
    soft_cmd = _run(soft_cls(_ctx(mesh_soft, influence, pivot)), steps)
    core_cmd = _run(
        core_cls(OperationContext(
            target=mesh_core, selection=_InfluenceView(set(seeds)), history=HistoryStack(),
            params={"pivot": pivot},
        )),
        steps,
    )
    assert _positions(mesh_soft) == _positions(mesh_core)
    assert soft_cmd.start_positions == core_cmd.start_positions
    assert soft_cmd.end_positions == core_cmd.end_positions


# -- path independence (E8) -------------------------------------------------------


def test_move_path_independent():
    mesh_a, _, influence, pivot = _head_case()
    mesh_b = head()
    total = (0.3, -0.12, 0.05)
    n = 17
    _run(SoftMoveOperation(_ctx(mesh_a, influence, pivot)), [{"delta": total}])
    _run(SoftMoveOperation(_ctx(mesh_b, influence, pivot)),
         [{"delta": tuple(c / n for c in total)}] * n)
    a, b = _positions(mesh_a), _positions(mesh_b)
    assert all(_close(a[v], b[v]) for v in a)
    w = next(w for w in influence.values() if w < 1.0)
    vid = next(v for v, ww in influence.items() if ww == w)
    start = head().vertex_position(vid)
    assert _close(a[vid], tuple(s + w * t for s, t in zip(start, total)))


@pytest.mark.parametrize("formula", ["linear", "power"])
@pytest.mark.parametrize("total,basis", [((1.8, 1.8, 1.8), None), ((0.6, 1.0, 1.5), None),
                                          ((1.7, 1.0, 1.0), TILTED)])
def test_scale_path_independent(formula, total, basis):
    mesh_a, _, influence, pivot = _head_case()
    mesh_b = head()
    n = 23
    _run(SoftScaleOperation(_ctx(mesh_a, influence, pivot, scale_formula=formula)),
         [{"factor": total, "basis": basis}])
    _run(SoftScaleOperation(_ctx(mesh_b, influence, pivot, scale_formula=formula)),
         [{"factor": tuple(f ** (1.0 / n) for f in total), "basis": basis}] * n)
    a, b = _positions(mesh_a), _positions(mesh_b)
    assert all(_close(a[v], b[v], 1e-11) for v in a)


@pytest.mark.parametrize("formula", ["linear", "power"])
def test_scale_weighted_factor_formula(formula):
    mesh, _, influence, pivot = _head_case()
    start = _positions(mesh)
    factor = 2.0
    _run(SoftScaleOperation(_ctx(mesh, influence, pivot, scale_formula=formula)),
         [{"factor": factor}])
    for vid, w in influence.items():
        g = 1.0 + w * (factor - 1.0) if formula == "linear" else factor ** w
        expected = tuple(p + g * (s - p) for s, p in zip(start[vid], pivot))
        assert _close(mesh.vertex_position(vid), expected)


def test_rotate_weighted_angle_exact_and_path_independent():
    mesh_a, _, influence, pivot = _head_case()
    mesh_b = head()
    start = _positions(mesh_a)
    axis, total, n = (0.3, 1.0, -0.2), 0.9, 19
    _run(SoftRotateOperation(_ctx(mesh_a, influence, pivot)), [{"axis": axis, "angle": total}])
    _run(SoftRotateOperation(_ctx(mesh_b, influence, pivot)),
         [{"axis": axis, "angle": total / n}] * n)
    assert any(w < 1.0 for w in influence.values())
    for vid, w in influence.items():
        expected = rotate_around_axis(start[vid], pivot, axis, w * total)
        assert _close(mesh_a.vertex_position(vid), expected)
        assert _close(mesh_b.vertex_position(vid), expected)
        # An arc, not a chord: distance to the pivot is preserved.
        assert math.dist(mesh_b.vertex_position(vid), pivot) == pytest.approx(
            math.dist(start[vid], pivot), abs=TOL)


def test_core_placeholder_blend_is_not_path_independent():
    """Characterization (why `_on_update` is replaced): the Core per-step blend
    `pos + w (T(pos) - pos)` pulls a rotating vertex towards the pivot."""
    mesh, _, influence, pivot = _head_case()
    start = _positions(mesh)
    op = RotateOperation(OperationContext(
        target=mesh, selection=_InfluenceView(set(influence)), history=HistoryStack(),
        params={"pivot": pivot}))
    op.begin()
    op._weights = dict(influence)
    for _ in range(20):
        op.update(axis=(0.0, 1.0, 0.0), angle=0.05)
    vid = min(influence, key=influence.get)
    assert math.dist(mesh.vertex_position(vid), pivot) < math.dist(start[vid], pivot) - 1e-6
    op.cancel()


# -- pivot and constraints ---------------------------------------------------------


def test_pivot_comes_from_primary_selection_only():
    mesh, ids = grid()
    selection = Selection()
    selection.set({ids[0][0], ids[0][1]})  # at the border: the influence is one-sided
    ctx = soft_context(mesh, selection, HistoryStack(), radius=3.0)
    influenced = ctx.params["influence"]
    assert ctx.params["pivot"] == (0.5, 0.0, 0.0)
    for cls in (SoftRotateOperation, SoftScaleOperation):
        op = cls(ctx)
        op.begin()
        assert op.pivot == (0.5, 0.0, 0.0)
        op.cancel()
    centroid_of_influenced = tuple(
        sum(mesh.vertex_position(v)[i] for v in influenced) / len(influenced) for i in range(3))
    assert centroid_of_influenced != ctx.params["pivot"]


@pytest.mark.parametrize("cls", [SoftRotateOperation, SoftScaleOperation])
def test_rotate_scale_refuse_without_explicit_pivot(cls):
    mesh, ids = grid(3)
    op = cls(OperationContext(target=mesh, selection=Selection(), history=HistoryStack(),
                              params={"influence": {ids[1][1]: 1.0}}))
    with pytest.raises(ValueError, match="pivot"):
        op.begin()
    assert not op.is_active


def test_move_axis_constraint_keeps_locked_components_exact():
    mesh, _, influence, pivot = _head_case()
    start = _positions(mesh)
    _run(SoftMoveOperation(_ctx(mesh, influence, pivot)), [{"delta": (0.2, 0.0, 0.0)}] * 5)
    for vid in influence:
        p = mesh.vertex_position(vid)
        assert (p[1], p[2]) == (start[vid][1], start[vid][2])
        assert p[0] != start[vid][0]


def test_scale_axis_and_plane_constraints():
    mesh, _, influence, pivot = _head_case()
    start = _positions(mesh)
    _run(SoftScaleOperation(_ctx(mesh, influence, pivot)), [{"factor": (1.5, 1.0, 1.0)}] * 3)
    for vid in influence:
        p, s = mesh.vertex_position(vid), start[vid]
        assert abs(p[1] - s[1]) <= TOL and abs(p[2] - s[2]) <= TOL

    mesh, _, influence, pivot = _head_case()
    _run(SoftScaleOperation(_ctx(mesh, influence, pivot)),
         [{"factor": (1.5, 1.5, 1.0), "basis": TILTED}] * 3)  # "xy" plane in the tilted basis
    for vid in influence:
        assert abs(mesh.vertex_position(vid)[2] - start[vid][2]) <= TOL


def test_rotate_about_z_keeps_z():
    mesh, _, influence, pivot = _head_case()
    start = _positions(mesh)
    _run(SoftRotateOperation(_ctx(mesh, influence, pivot)), [{"axis": (0.0, 0.0, 1.0), "angle": 0.4}] * 3)
    for vid in influence:
        assert abs(mesh.vertex_position(vid)[2] - start[vid][2]) <= TOL


def test_scale_basis_change_mid_gesture_refused_before_anything_moves():
    mesh, _, influence, pivot = _head_case()
    op = SoftScaleOperation(_ctx(mesh, influence, pivot))
    op.begin()
    op.update(factor=(1.2, 1.0, 1.0), basis=TILTED)
    before = _positions(mesh)
    with pytest.raises(ValueError, match="basis"):
        op.update(factor=(1.2, 1.0, 1.0), basis=None)
    assert _positions(mesh) == before
    op.cancel()


def test_scale_power_refuses_negative_factor():
    mesh, _, influence, pivot = _head_case()
    op = SoftScaleOperation(_ctx(mesh, influence, pivot, scale_formula="power"))
    op.begin()
    before = _positions(mesh)
    with pytest.raises(ValueError, match="negative"):
        op.update(factor=(-1.0, 1.0, 1.0))
    assert _positions(mesh) == before
    op.cancel()


def test_unknown_scale_formula_refused():
    mesh, _, influence, pivot = _head_case()
    with pytest.raises(ValueError, match="scale_formula"):
        SoftScaleOperation(_ctx(mesh, influence, pivot, scale_formula="cubic")).begin()


# -- lifecycle: cancel, commit, undo/redo, Selection --------------------------------


@pytest.mark.parametrize("cls,steps", [(SoftMoveOperation, MOVE_STEPS),
                                       (SoftRotateOperation, ROTATE_STEPS),
                                       (SoftScaleOperation, SCALE_STEPS)])
def test_cancel_restores_exact_start(cls, steps):
    mesh, _, influence, pivot = _head_case()
    history = HistoryStack()
    start = _positions(mesh)
    op = cls(_ctx(mesh, influence, pivot, history))
    op.begin()
    for kwargs in steps:
        op.update(**kwargs)
    assert _positions(mesh) != start
    op.cancel()
    assert _positions(mesh) == start
    assert len(history) == 0


@pytest.mark.parametrize("cls,steps", [(SoftMoveOperation, MOVE_STEPS),
                                       (SoftRotateOperation, ROTATE_STEPS),
                                       (SoftScaleOperation, SCALE_STEPS)])
def test_commit_one_entry_covering_influence_and_exact_undo_redo(cls, steps):
    mesh, _, influence, pivot = _head_case()
    history = HistoryStack()
    start = _positions(mesh)
    command = _run(cls(_ctx(mesh, influence, pivot, history)), steps)
    end = _positions(mesh)
    assert len(history) == 1
    assert set(command.start_positions) == set(command.end_positions) == set(influence)
    assert len(influence) > 5
    untouched = set(start) - set(influence)
    assert untouched and all(end[v] == start[v] for v in untouched)
    history.undo()
    assert _positions(mesh) == start
    history.redo()
    assert _positions(mesh) == end
    assert_mesh_invariants(mesh, context=cls.__name__)


@pytest.mark.parametrize("cls", SOFT_OPS)
def test_commit_without_change_returns_none(cls):
    mesh, _, influence, pivot = _head_case()
    history = HistoryStack()
    assert _run(cls(_ctx(mesh, influence, pivot, history)), []) is None
    assert _run(SoftMoveOperation(_ctx(mesh, influence, pivot, history)),
                [{"delta": (0.0, 0.0, 0.0)}]) is None
    assert len(history) == 0


@pytest.mark.parametrize("core_cls,soft_cls,kwargs", [
    (RotateOperation, SoftRotateOperation, {"axis": (0, 1, 0), "angle": 0.0}),
    (ScaleOperation, SoftScaleOperation, {"factor": 1.0}),
])
def test_identity_rotate_scale_round_like_core(core_cls, soft_cls, kwargs):
    """Characterization (FINDINGS): `pivot + (p - pivot)` is not bit-exact, so the Core
    Rotate(angle=0)/Scale(factor=1) already commit a History entry; the soft ops inherit it."""
    mesh, _, influence, pivot = _head_case()
    core_cmd = _run(core_cls(OperationContext(
        target=mesh, selection=_InfluenceView(set(influence)), history=HistoryStack(),
        params={"pivot": pivot})), [kwargs])
    assert core_cmd is not None
    assert all(_close(core_cmd.end_positions[v], core_cmd.start_positions[v]) for v in influence)
    core_cmd.undo()
    soft_cmd = _run(soft_cls(_ctx(mesh, influence, pivot)), [kwargs])
    assert soft_cmd is not None
    assert all(_close(soft_cmd.end_positions[v], soft_cmd.start_positions[v]) for v in influence)


@pytest.mark.parametrize("cls,steps", [(SoftMoveOperation, MOVE_STEPS),
                                       (SoftRotateOperation, ROTATE_STEPS),
                                       (SoftScaleOperation, SCALE_STEPS)])
@pytest.mark.parametrize("mode", [SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE])
def test_selection_unchanged_by_the_whole_gesture(cls, steps, mode):
    mesh = head()
    v = mesh.all_vertex_ids()[100]
    selection = Selection()
    selection.mode = mode
    selection.vertices = {v}
    selection.edges = set(mesh.vertex_edges(v)[:2])
    selection.faces = {mesh.all_face_ids()[50]}
    selection.hovered = v
    snapshot = (selection.mode, set(selection.vertices), set(selection.edges),
                set(selection.faces), selection.hovered)
    history = HistoryStack()
    ctx = soft_context(mesh, selection, history, radius=0.8, metric="geodesic")
    assert len(ctx.params["influence"]) > len(selection.vertices)
    _run(cls(ctx), steps)
    history.undo()
    history.redo()
    assert (selection.mode, selection.vertices, selection.edges, selection.faces,
            selection.hovered) == snapshot


# -- refusals and stale ids -------------------------------------------------------


@pytest.mark.parametrize("cls", SOFT_OPS)
@pytest.mark.parametrize("symmetry", [None, {"plane_normal": (1.0, 0.0, 0.0)}])
def test_symmetry_param_refused(cls, symmetry):
    mesh, _, influence, pivot = _head_case()
    start = _positions(mesh)
    op = cls(_ctx(mesh, influence, pivot, symmetry=symmetry))
    with pytest.raises(ValueError, match="symmetry"):
        op.begin()
    assert not op.is_active
    assert _positions(mesh) == start
    assert cls.supports_symmetry is False


@pytest.mark.parametrize("cls", SOFT_OPS)
def test_stale_ids_in_influence_skipped(cls):
    mesh, _, influence, pivot = _head_case()
    stale = VertexId(10**6)
    op = cls(_ctx(mesh, {**influence, stale: 0.5}, pivot))
    op.begin()
    assert stale not in op.vertex_ids and op.vertex_ids == set(influence)
    op.cancel()


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.5, math.nan])
def test_weights_outside_unit_interval_refused(bad):
    mesh, _, influence, pivot = _head_case()
    vid = next(iter(influence))
    with pytest.raises(ValueError, match="weight"):
        SoftMoveOperation(_ctx(mesh, {**influence, vid: bad}, pivot)).begin()


def test_missing_influence_refused():
    mesh, ids = grid(3)
    with pytest.raises(ValueError, match="influence"):
        SoftMoveOperation(OperationContext(target=mesh, selection=Selection(),
                                           history=HistoryStack())).begin()


def test_empty_influence_is_a_noop():
    mesh, ids = grid(3)
    selection = Selection()
    history = HistoryStack()
    ctx = soft_context(mesh, selection, history, radius=2.0)
    assert ctx.params["influence"] == {} and "pivot" not in ctx.params
    assert _run(SoftMoveOperation(ctx), [{"delta": (1.0, 0.0, 0.0)}]) is None
    assert len(history) == 0
