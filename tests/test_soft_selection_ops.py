"""Soft Move/Rotate/Scale on the app path (WP-SOFT-01 S2a, AD-020; AD-SYM-05 SS1).

Port of the S1 suite `experiments/soft_selection/tests/test_weighted_ops.py` against the
`mirai.soft_selection` ops. Since SS1 these are thin subclasses of the Core ops and the
weighting runs in the Core loop (`params["influence"]`, AD-SYM-05 §4, M-b §5.1). The AD-020 F3
tripwires were flipped on purpose in the SS1 commit (AD-SYM-05 §5.3):

- (1) "the base never blends" became "the Core's weighted step equals the closed form", for the
  thin ops and for the Core ops with `params["influence"]`; the placeholder-blend
  characterization went with the placeholder;
- (3)/(4) the copied Scale arithmetic and Move tuple sum are gone; bit identity with Q2-D is held
  by the replay oracle in `test_soft_selection_replay.py` (T-3); the radius-0 identity stays;
- `scale_formula` / `"power"` left `src` (S2c kept linear): dropped here are
  `test_scale_path_independent[power-*]`, `test_scale_weighted_factor_formula[power]`,
  `test_scale_power_refuses_negative_factor`, `test_unknown_scale_formula_refused` (the
  comparison lives on in the Mehlsack Lab, against the closed form `F ** w`);
- `total_factor` is gone; the basis-refusal test checks positions instead.

Still here: the stale-ID filter (S1 L10) and the key-set check; the History label; a source scan:
no Core private member in `src/mirai/soft_selection`. Tripwire (8), the symmetry backstop, flipped
in AD-SYM-04 SS2: `params["symmetry"]` passes through to the Core.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

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
from mirai.interaction.tools.selection_helpers import _VertexSelectionView as _InfluenceView
from mirai.soft_selection import (
    SoftMoveOperation,
    SoftRotateOperation,
    SoftScaleOperation,
    compute_influence,
    primary_pivot,
)
from tests.mesh_invariants import assert_mesh_invariants
from tests.soft_selection_fixtures import grid, head, soft_context

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


@pytest.mark.parametrize("total,basis", [((1.8, 1.8, 1.8), None), ((0.6, 1.0, 1.5), None),
                                          ((1.7, 1.0, 1.0), TILTED)])
def test_scale_path_independent(total, basis):
    mesh_a, _, influence, pivot = _head_case()
    mesh_b = head()
    n = 23
    _run(SoftScaleOperation(_ctx(mesh_a, influence, pivot)), [{"factor": total, "basis": basis}])
    _run(SoftScaleOperation(_ctx(mesh_b, influence, pivot)),
         [{"factor": tuple(f ** (1.0 / n) for f in total), "basis": basis}] * n)
    a, b = _positions(mesh_a), _positions(mesh_b)
    assert all(_close(a[v], b[v], 1e-11) for v in a)


def test_scale_weighted_factor_formula():
    mesh, _, influence, pivot = _head_case()
    start = _positions(mesh)
    factor = 2.0
    _run(SoftScaleOperation(_ctx(mesh, influence, pivot)), [{"factor": factor}])
    for vid, w in influence.items():
        g = 1.0 + w * (factor - 1.0)
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


_SYMMETRY_STEPS = {SoftMoveOperation: (MoveOperation, MOVE_STEPS),
                   SoftRotateOperation: (RotateOperation, ROTATE_STEPS),
                   SoftScaleOperation: (ScaleOperation, SCALE_STEPS)}


@pytest.mark.parametrize("cls", SOFT_OPS)
@pytest.mark.parametrize("symmetry", [None, {"plane_normal": (1.0, 0.0, 0.0)}])
def test_symmetry_passes_through_to_the_core(cls, symmetry):
    """Tripwire (8), flipped in AD-SYM-04 SS2: the backstop is gone, `supports_symmetry` is the
    Core op's `True`, and the thin op with `params["symmetry"]` is the Core op bit for bit."""
    assert cls.supports_symmetry is True
    core_cls, steps = _SYMMETRY_STEPS[cls]
    mesh, _, influence, pivot = _head_case()
    reference = head()
    _run(cls(_ctx(mesh, influence, pivot, symmetry=symmetry)), steps)
    _run(core_cls(_ctx(reference, influence, pivot, symmetry=symmetry)), steps)
    assert _positions(mesh) == _positions(reference)


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


# -- what D adds (AD-020 §3.3, review F3 / F10) -------------------------------------


def test_stale_ids_are_filtered_before_the_core_sees_them():
    """E2 / F10: S1 L10 kept - a stale ID in the map and in the view is skipped, not a KeyError
    from the Core base, and the History entry covers the valid vertices only."""
    mesh, _, influence, pivot = _head_case()
    stale = VertexId(10**6)
    history = HistoryStack()
    command = _run(
        SoftMoveOperation(_ctx(mesh, {**influence, stale: 0.5}, pivot, history)), MOVE_STEPS
    )
    assert set(command.start_positions) == set(influence)
    assert stale not in command.end_positions


def test_view_must_be_exactly_the_influenced_set():
    mesh, _, influence, pivot = _head_case()
    start = _positions(mesh)
    extra = next(v for v in mesh.all_vertex_ids() if v not in influence)
    for view in (set(influence) | {extra}, set(list(influence)[1:])):
        op = SoftMoveOperation(OperationContext(
            target=mesh, selection=_InfluenceView(view), history=HistoryStack(),
            params={"influence": influence, "pivot": pivot}))
        with pytest.raises(ValueError, match="influenced vertex set"):
            op.begin()
        assert not op.is_active
    assert _positions(mesh) == start


@pytest.mark.parametrize("cls,steps", [(SoftMoveOperation, MOVE_STEPS[:1]),
                                       (SoftRotateOperation, ROTATE_STEPS[:1]),
                                       (SoftScaleOperation, SCALE_STEPS[:1]),
                                       (MoveOperation, MOVE_STEPS[:1]),
                                       (RotateOperation, ROTATE_STEPS[:1]),
                                       (ScaleOperation, SCALE_STEPS[:1])])
def test_core_weighted_step_equals_the_closed_form(cls, steps):
    """Tripwire (F3 row 1), flipped on purpose in SS1 (AD-SYM-05 §5.3): it used to pin "the
    Core base never blends". Now the Core weights, once: one `update` on a `w < 1` vertex equals
    the closed form, for the thin soft ops and for the Core ops given `params["influence"]`.
    Double weighting (a soft layer weighting again on top of the Core) would break it."""
    mesh, _, influence, pivot = _head_case()
    start = _positions(mesh)
    kwargs = steps[0]
    _run(cls(_ctx(mesh, influence, pivot)), steps)
    lows = [v for v, w in influence.items() if w < 1.0]
    assert lows
    for vid in lows:
        w = influence[vid]
        s = start[vid]
        if issubclass(cls, MoveOperation):
            expected = tuple(c + w * d for c, d in zip(s, kwargs["delta"]))
        elif issubclass(cls, RotateOperation):
            expected = rotate_around_axis(s, pivot, kwargs["axis"], w * kwargs["angle"])
        else:
            g = 1.0 + w * (kwargs["factor"] - 1.0)
            expected = tuple(p + g * (c - p) for c, p in zip(s, pivot))
        assert _close(mesh.vertex_position(vid), expected)


def test_history_entries_carry_the_soft_description():
    """Tripwire (F3 row 7): the base `_on_commit` labels the entry with `description`."""
    assert SoftMoveOperation.description == "Soft Move Vertices"
    assert SoftRotateOperation.description == "Soft Rotate Vertices"
    assert SoftScaleOperation.description == "Soft Scale Vertices"
    mesh, _, influence, pivot = _head_case()
    command = _run(SoftMoveOperation(_ctx(mesh, influence, pivot)), MOVE_STEPS)
    assert command.description == "Soft Move Vertices"


@pytest.mark.parametrize("cls", SOFT_OPS)
def test_pivot_is_the_given_pivot(cls):
    """Tripwire (F3 row 9): `pivot` is the float-converted `params["pivot"]`."""
    mesh, _, influence, pivot = _head_case()
    op = cls(_ctx(mesh, influence, pivot))
    op.begin()
    assert op.pivot == tuple(float(c) for c in pivot)
    op.cancel()


def test_scale_refusals_keep_the_total_at_its_pre_refusal_value():
    """Refused updates (basis change, malformed or non-finite factor) do not accumulate: the
    next valid update lands exactly where it lands without them. (Read `total_factor` before
    SS1; that property went with M-b, AD-SYM-05 §5.1 — behaviour is checked instead.)"""
    mesh, _, influence, pivot = _head_case()
    reference = head()
    op = SoftScaleOperation(_ctx(mesh, influence, pivot))
    op.begin()
    op.update(factor=(1.2, 1.0, 1.0), basis=TILTED)
    before = _positions(mesh)
    with pytest.raises(ValueError, match="basis"):
        op.update(factor=(1.5, 1.0, 1.0), basis=None)
    with pytest.raises(ValueError):
        op.update(factor=(1.0, 1.0), basis=TILTED)  # malformed: refused before accumulation
    with pytest.raises(ValueError, match="finite"):
        op.update(factor=(math.inf, 1.0, 1.0), basis=TILTED)
    assert _positions(mesh) == before
    op.update(factor=(1.1, 1.0, 1.0), basis=TILTED)
    _run(SoftScaleOperation(_ctx(reference, influence, pivot)),
         [{"factor": (1.2, 1.0, 1.0), "basis": TILTED}, {"factor": (1.1, 1.0, 1.0), "basis": TILTED}])
    assert _positions(mesh) == _positions(reference)
    op.cancel()


# -- no Core private member in src/mirai (AD-020 F10, handoff §5) -----------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
#: Core private state and helpers D must not touch (the P-D scan list of AD-020 §3.2).
_CORE_PRIVATES = {
    "_weights", "_start_positions", "_vertex_ids", "_pivot", "_mesh", "_apply", "_as_triple",
    "_add", "_sub", "_scale", "_dot", "_cross", "_length", "_mirror_vector", "_project_onto_plane",
    # added with SS1 (AD-SYM-05): the Core's weighted path
    "_weighted", "_weighted_position", "_validated_influence", "_read_falloff_seam",
    "_falloff_seam_vertex_ids", "_total_angle", "_fixed_axis", "_total_factor", "_basis_fixed",
    "_fixed_basis", "_weighted_factor", "_check_weighted_step", "_accumulate",
}


def _soft_sources() -> list[Path]:
    root = _REPO_ROOT / "src" / "mirai"
    return sorted((root / "soft_selection").glob("*.py"))


def test_no_core_private_member_in_the_soft_selection_package():
    offenders = []
    for path in _soft_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in _CORE_PRIVATES:
                offenders.append(f"{path.name}:{node.lineno} .{node.attr}")
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "core":
                offenders += [
                    f"{path.name}:{node.lineno} import {a.name}"
                    for a in node.names
                    if a.name.startswith("_")
                ]
    assert not offenders, offenders


def test_soft_selection_package_does_not_depend_on_the_interaction_layer():
    """The tools import the package, never the other way (no import cycle)."""
    for path in _soft_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "interaction" not in module and "application" not in module, (path.name, module)
