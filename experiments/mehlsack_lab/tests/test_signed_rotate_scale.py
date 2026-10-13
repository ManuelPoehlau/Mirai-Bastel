"""Slice 2b E19: signed soft Rotate and Scale.

For weights in (0, 1] the lab ops are bit-identical to `SoftRotateOperation` /
`SoftScaleOperation` (both `scale_formula` values; same pivot, same factors, N steps).
Negative weights: rotation by `w·θ`; Scale `g` = the README table (linear and power), no
clamp (collapse at `F = 1 + 1/|w|`, inversion beyond); N steps == 1 step; commit / cancel /
Undo / Redo exact; one History entry."""

from __future__ import annotations

import math

import pytest

from core import HistoryStack, OperationContext
from core.operations.transform import rotate_around_axis
from mehlsack_lab.signed_curve import PRESET_HAT, SignedCurve
from mehlsack_lab.signed_influence import signed_influence
from mehlsack_lab.signed_ops import (
    SignedSoftRotateOperation,
    SignedSoftScaleOperation,
    VertexView,
    collapsed_count,
    weighted_factor,
)
from mirai.soft_selection import SoftRotateOperation, SoftScaleOperation, compute_influence, primary_pivot

from .helpers import box, mid_target, positions

AXIS = (0.0, 1.0, 0.0)
TILTED = (0.3, 0.9, -0.2)
ANGLES = [0.11, -0.04, 0.27, 0.013, 0.2]
FACTORS = [1.1, 0.97, 1.25, 1.003, 0.8]
MASKS = [(1.0, 1.0, 1.0), (1.0, 0.0, 1.0), (0.0, 1.0, 0.0)]
HAT = SignedCurve.from_preset(PRESET_HAT)


def _ctx(mesh, weights, pivot, history=None, **params):
    return OperationContext(
        target=mesh, selection=VertexView(set(weights)),
        history=history if history is not None else HistoryStack(),
        params={"influence": weights, "pivot": pivot, **params},
    )


def _case(curve=None, radius=1.2, metric="geodesic"):
    mesh = box(h=8, n=4)
    _, target = mid_target(mesh)
    if curve is None:
        weights = compute_influence(mesh, target.seeds, radius, metric=metric, curve="smooth")
    else:
        weights = signed_influence(mesh, target.seeds, radius, metric, curve)
    return mesh, target, weights, primary_pivot(mesh, target.seeds)


def _rotate(op, angles, axis=AXIS):
    op.begin()
    for a in angles:
        op.update(axis=axis, angle=a)
    return op.commit()


def _scale(op, factors, mask=(1.0, 1.0, 1.0)):
    op.begin()
    for f in factors:
        op.update(factor=tuple(f if m else 1.0 for m in mask))
    return op.commit()


# -- bit identity with src for weights in (0, 1] ------------------------------------------------


@pytest.mark.parametrize("axis", [AXIS, TILTED])
@pytest.mark.parametrize("radius", [0.0, 0.6, 1.2, 3.0])
def test_rotate_bit_identical_to_soft_rotate(radius, axis):
    mesh_a, _, weights, pivot = _case(radius=radius)
    mesh_b = box(h=8, n=4)
    assert all(0.0 < w <= 1.0 for w in weights.values())
    cmd_a = _rotate(SignedSoftRotateOperation(_ctx(mesh_a, weights, pivot)), ANGLES, axis)
    cmd_b = _rotate(SoftRotateOperation(_ctx(mesh_b, weights, pivot)), ANGLES, axis)
    assert positions(mesh_a) == positions(mesh_b)
    assert cmd_a.start_positions == cmd_b.start_positions and cmd_a.end_positions == cmd_b.end_positions


@pytest.mark.parametrize("formula", ["linear", "power"])
@pytest.mark.parametrize("mask", MASKS)
@pytest.mark.parametrize("radius", [0.0, 0.6, 1.2, 3.0])
def test_scale_bit_identical_to_soft_scale_for_both_formulas(radius, mask, formula):
    mesh_a, _, weights, pivot = _case(radius=radius)
    mesh_b = box(h=8, n=4)
    op_a = SignedSoftScaleOperation(_ctx(mesh_a, weights, pivot, scale_formula=formula))
    op_b = SoftScaleOperation(_ctx(mesh_b, weights, pivot, scale_formula=formula))
    cmd_a, cmd_b = _scale(op_a, FACTORS, mask), _scale(op_b, FACTORS, mask)
    assert positions(mesh_a) == positions(mesh_b)
    # (radius 0 + Y-only mask on the flat mid loop moves nothing: both commit None)
    assert (cmd_a is None) == (cmd_b is None)
    assert cmd_a is None or cmd_a.end_positions == cmd_b.end_positions
    assert op_a.total_factor == op_b.total_factor and op_a.scale_formula == formula


# -- negative weights -------------------------------------------------------------------------------


def test_negative_weights_rotate_by_w_theta_the_other_way():
    mesh, _, weights, pivot = _case(HAT, radius=2.0)
    start = positions(mesh)
    theta = 0.4
    _rotate(SignedSoftRotateOperation(_ctx(mesh, weights, pivot)), [theta])
    negatives = [v for v, w in weights.items() if w < 0.0]
    assert negatives
    for vid, w in weights.items():
        expected = rotate_around_axis(start[vid], pivot, AXIS, theta if w == 1.0 else w * theta)
        assert mesh.vertex_position(vid) == expected
    # The turned angle about +Y, measured in the (x, z) plane, is exactly w·θ: negatives turn back.
    # (atan2 of the (x, z) cross product counts a right-handed +Y turn as negative.)
    for vid, w in weights.items():
        s, p = start[vid], mesh.vertex_position(vid)
        rs, rp = (s[0] - pivot[0], s[2] - pivot[2]), (p[0] - pivot[0], p[2] - pivot[2])
        if math.hypot(*rs) < 1e-9:
            continue
        turned = -math.atan2(rs[0] * rp[1] - rs[1] * rp[0], rs[0] * rp[0] + rs[1] * rp[1])
        assert turned == pytest.approx(w * theta, abs=1e-12)
        if w < 0.0:
            assert turned < 0.0
    untouched = set(start) - set(weights)
    assert all(mesh.vertex_position(v) == start[v] for v in untouched)


#: The README table "Rotate / Scale mit Vorzeichen-Gewichten": linear g = 1 + w (F − 1).
README_LINEAR = {
    (1.0, 0.5): 0.5, (1.0, 2.0): 2.0, (0.5, 1.5): 1.25, (0.5, 3.0): 2.0,
    (-0.25, 0.5): 1.125, (-0.25, 3.0): 0.5, (-0.25, 5.0): 0.0,
    (-0.5, 1.5): 0.75, (-0.5, 3.0): 0.0, (-0.5, 5.0): -1.0,
    (-1.0, 0.5): 1.5, (-1.0, 2.0): 0.0, (-1.0, 3.0): -1.0, (-1.0, 5.0): -3.0,
}


@pytest.mark.parametrize("wf,g", sorted(README_LINEAR.items()))
def test_scale_values_match_the_readme_table(wf, g):
    w, f = wf
    assert weighted_factor(w, (f, f, f), "linear") == (g, g, g)
    assert weighted_factor(w, (f, f, f), "power") == pytest.approx((f ** w,) * 3)
    if w == -1.0 and f == 2.0:
        assert weighted_factor(w, (f, f, f), "power") == (0.5, 0.5, 0.5)  # README: F ** w → 0.5


@pytest.mark.parametrize("formula", ["linear", "power"])
def test_negative_scale_on_the_mesh_no_clamp(formula):
    """Absolute from the start: p = pivot + g (start − pivot), g unclamped (linear inverts)."""
    mesh, _, weights, pivot = _case(HAT, radius=2.0)
    start = positions(mesh)
    big = 5.0  # beyond F = 1 + 1/|w| for every w < -1/4: linear inverts those
    op = SignedSoftScaleOperation(_ctx(mesh, weights, pivot, scale_formula=formula))
    _scale(op, [big])
    for vid, w in weights.items():
        g = big if w == 1.0 else weighted_factor(w, (big,) * 3, formula)[0]
        s = start[vid]
        expected = tuple(pivot[i] + g * (s[i] - pivot[i]) for i in range(3))
        assert mesh.vertex_position(vid) == pytest.approx(expected, abs=1e-12)
    inverted = collapsed_count(weights, (big,) * 3, formula)
    lowest = min(weights.values())
    if formula == "linear":
        assert lowest < -1.0 / (big - 1.0) and inverted > 0
    else:
        assert inverted == 0


def test_collapse_at_f_one_plus_one_over_w():
    weights = {1: 1.0, 2: -0.5, 3: -1.0, 4: 0.4}
    assert collapsed_count(weights, (2.0, 2.0, 2.0), "linear") == 1   # w = -1 at F = 2: g = 0
    assert collapsed_count(weights, (3.0, 3.0, 3.0), "linear") == 2   # w = -0.5 at F = 3
    assert collapsed_count(weights, (1.9, 1.9, 1.9), "linear") == 0
    assert collapsed_count(weights, (100.0,) * 3, "power") == 0
    # masked axes (F = 1) never count: shrinking only along X/Z
    assert collapsed_count(weights, (3.0, 1.0, 3.0), "linear") == 2


@pytest.mark.parametrize("formula", ["linear", "power"])
def test_scale_n_steps_equal_one_step(formula):
    mesh_a, _, weights, pivot = _case(HAT, radius=2.0)
    mesh_b = box(h=8, n=4)
    total = math.prod(FACTORS)
    _scale(SignedSoftScaleOperation(_ctx(mesh_a, weights, pivot, scale_formula=formula)), [total])
    _scale(SignedSoftScaleOperation(_ctx(mesh_b, weights, pivot, scale_formula=formula)), FACTORS)
    a, b = positions(mesh_a), positions(mesh_b)
    assert all(math.dist(a[v], b[v]) <= 1e-12 for v in a)


def test_rotate_n_steps_equal_one_step():
    mesh_a, _, weights, pivot = _case(HAT, radius=2.0)
    mesh_b = box(h=8, n=4)
    _rotate(SignedSoftRotateOperation(_ctx(mesh_a, weights, pivot)), [sum(ANGLES)], TILTED)
    _rotate(SignedSoftRotateOperation(_ctx(mesh_b, weights, pivot)), ANGLES, TILTED)
    a, b = positions(mesh_a), positions(mesh_b)
    assert all(math.dist(a[v], b[v]) <= 1e-12 for v in a)


@pytest.mark.parametrize("kind", ["rotate", "scale"])
def test_commit_one_entry_cancel_exact_undo_redo_exact(kind):
    mesh, _, weights, pivot = _case(HAT, radius=2.0)
    start = positions(mesh)
    history = HistoryStack()

    def make():
        if kind == "rotate":
            return SignedSoftRotateOperation(_ctx(mesh, weights, pivot, history))
        return SignedSoftScaleOperation(_ctx(mesh, weights, pivot, history, scale_formula="linear"))

    def feed(op):
        op.begin()
        for a, f in zip(ANGLES, FACTORS):
            op.update(axis=AXIS, angle=a) if kind == "rotate" else op.update(factor=(f, 1.0, f))

    op = make()
    feed(op)
    assert positions(mesh) != start
    op.cancel()
    assert positions(mesh) == start and len(history) == 0
    op = make()
    feed(op)
    command = op.commit()
    end = positions(mesh)
    assert len(history) == 1 and command.description.startswith("Signed Soft")
    history.undo()
    assert positions(mesh) == start
    history.redo()
    assert positions(mesh) == end


def test_pivot_required_basis_fixed_power_refuses_negative_factor():
    mesh, _, weights, pivot = _case()
    for cls in (SignedSoftRotateOperation, SignedSoftScaleOperation):
        with pytest.raises(ValueError, match="pivot"):
            cls(_ctx(mesh, weights, None)).begin()
    with pytest.raises(ValueError, match="scale_formula"):
        SignedSoftScaleOperation(_ctx(mesh, weights, pivot, scale_formula="cubic")).begin()
    op = SignedSoftScaleOperation(_ctx(mesh, weights, pivot))
    op.begin()
    op.update(factor=1.2)
    basis = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    with pytest.raises(ValueError, match="same basis"):
        op.update(factor=1.2, basis=basis)
    op.cancel()
    op = SignedSoftScaleOperation(_ctx(mesh, weights, pivot, scale_formula="power"))
    op.begin()
    with pytest.raises(ValueError, match="negative"):
        op.update(factor=-1.0)
    op.cancel()
