"""compute_influence() on the app path (WP-SOFT-01 S2a): weights, metrics, curves, seeds.

Port of the S1 suite `experiments/soft_selection/tests/test_influence.py` against
`mirai.soft_selection`. The seed resolution from V/E/F lives in the tools now (they hand
the seeds in), so those S1 cases are covered through `resolve_selection_vertices` in the
tool/app suites."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401

from core import VertexId

from mirai.soft_selection import (
    CURVES,
    CUSTOM_SHAPE_STEPS,
    METRICS,
    compute_influence,
    custom_curve,
    primary_pivot,
)

from tests.soft_selection_fixtures import LIP_HALF_GAP, grid, head, lip

ALL = [(m, c) for m in sorted(METRICS) for c in sorted(CURVES)]


def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


# -- seeds, zero boundary, monotonicity -------------------------------------------


@pytest.mark.parametrize("metric,curve", ALL)
def test_seeds_weigh_exactly_one(metric, curve):
    mesh, ids = grid()
    seeds = {ids[4][4], ids[4][5]}
    weights = compute_influence(mesh, seeds, 2.5, metric=metric, curve=curve)
    assert all(weights[s] == 1.0 for s in seeds)
    assert all(0.0 < w < 1.0 for v, w in weights.items() if v not in seeds)


@pytest.mark.parametrize("metric,curve", ALL)
def test_weight_is_zero_at_and_beyond_radius(metric, curve):
    mesh, ids = grid()
    weights = compute_influence(mesh, {ids[4][4]}, 2.0, metric=metric, curve=curve)
    assert ids[4][5] in weights and ids[4][6] not in weights  # d = 1 in, d = r = 2 out
    assert ids[4][7] not in weights and ids[0][0] not in weights


@pytest.mark.parametrize("metric,curve", ALL)
def test_weights_monotone_non_increasing_in_distance(metric, curve):
    mesh, ids = grid()
    seed = ids[4][4]
    radius = 3.7
    weights = compute_influence(mesh, {seed}, radius, metric=metric, curve=curve)
    sp = mesh.vertex_position(seed)

    def distance(v):
        p = mesh.vertex_position(v)
        if metric == "euclidean":
            return math.dist(p, sp)
        return abs(p[0] - sp[0]) + abs(p[1] - sp[1])  # edge paths on a unit grid

    ordered = sorted(mesh.all_vertex_ids(), key=distance)
    ws = [weights.get(v, 0.0) for v in ordered]
    assert all(a >= b for a, b in zip(ws, ws[1:]))
    assert len(weights) > 5


@pytest.mark.parametrize("metric", sorted(METRICS))
def test_curves_match_their_formula(metric):
    mesh, ids = grid()
    seed, neighbour = ids[4][4], ids[4][5]  # d = 1 under both metrics
    radius = 4.0
    linear = compute_influence(mesh, {seed}, radius, metric=metric, curve="linear")
    smooth = compute_influence(mesh, {seed}, radius, metric=metric, curve="smooth")
    assert linear[neighbour] == pytest.approx(0.75, abs=1e-15)
    assert smooth[neighbour] == pytest.approx(_smoothstep(0.75), abs=1e-15)
    assert smooth[neighbour] != linear[neighbour]


def test_geodesic_is_the_edge_path_length():
    mesh, ids = grid()
    weights = compute_influence(mesh, {ids[4][4]}, 4.0, metric="geodesic", curve="linear")
    # (2, 2) diagonal: euclidean 2*sqrt(2) ~ 2.83, edge path 2 + 2 = 4 -> outside.
    assert ids[6][6] not in weights
    assert weights[ids[5][5]] == pytest.approx(1.0 - 2.0 / 4.0, abs=1e-15)
    euclid = compute_influence(mesh, {ids[4][4]}, 4.0, metric="euclidean", curve="linear")
    assert euclid[ids[6][6]] == pytest.approx(1.0 - math.sqrt(8.0) / 4.0, abs=1e-15)


def test_geodesic_never_exceeds_euclidean_on_a_real_asset():
    mesh = head()
    seeds = {mesh.all_vertex_ids()[0]}
    euclid = compute_influence(mesh, seeds, 1.0, metric="euclidean")
    geo = compute_influence(mesh, seeds, 1.0, metric="geodesic")
    assert set(geo) <= set(euclid)
    assert all(geo[v] <= euclid[v] + 1e-12 for v in geo)


# -- the lip case: close in space, far on the surface -------------------------------


def test_lip_euclidean_reaches_the_other_sheet_geodesic_does_not():
    mesh, upper, lower = lip()
    radius = 0.5
    euclid = compute_influence(mesh, {upper}, radius, metric="euclidean")
    geo = compute_influence(mesh, {upper}, radius, metric="geodesic")
    assert lower in euclid
    assert euclid[lower] == pytest.approx(_smoothstep(1.0 - 2 * LIP_HALF_GAP / radius))
    assert lower not in geo
    lower_sheet = {v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[2] < 0.0}
    assert lower_sheet & set(euclid)
    assert not lower_sheet & set(geo)


# -- stale ids, empty ------------------------------------------------------------


def test_stale_ids_are_skipped():
    mesh, ids = grid(3)
    for metric in METRICS:
        weights = compute_influence(mesh, {ids[1][1], VertexId(9999)}, 1.5, metric=metric)
        assert VertexId(9999) not in weights and weights[ids[1][1]] == 1.0


@pytest.mark.parametrize("metric,curve", ALL)
def test_empty_or_all_stale_seeds_give_empty_influence(metric, curve):
    mesh, _ = grid(3)
    assert compute_influence(mesh, set(), 5.0, metric=metric, curve=curve) == {}
    assert compute_influence(mesh, {VertexId(9999)}, 5.0, metric=metric, curve=curve) == {}


@pytest.mark.parametrize("metric,curve", ALL)
def test_radius_zero_is_the_seeds_only(metric, curve):
    mesh, ids = grid(3)
    seeds = {ids[0][0], ids[1][1]}
    assert compute_influence(mesh, seeds, 0.0, metric=metric, curve=curve) == {
        s: 1.0 for s in seeds
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"metric": "manhattan"},
        {"curve": "gauss"},
        {"radius": -1.0},
        {"radius": math.inf},
        {"radius": math.nan},
    ],
)
def test_invalid_arguments_raise(kwargs):
    mesh, ids = grid(3)
    args = {"radius": 1.0, **kwargs}
    with pytest.raises(ValueError):
        compute_influence(mesh, {ids[0][0]}, **args)


def test_primary_pivot_is_the_seed_centroid():
    mesh, ids = grid(3)
    assert primary_pivot(mesh, {ids[0][0], ids[0][2], VertexId(9999)}) == (1.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        primary_pivot(mesh, {VertexId(9999)})


# -- the S2d curve set (handoff E1/E2; formulas defined there) ------------------------------------

FORMULAS = {
    "smooth": lambda t: 3 * t * t - 2 * t**3,
    "sphere": lambda t: math.sqrt(2 * t - t * t),
    "root": lambda t: math.sqrt(t),
    "sharp": lambda t: t * t,
    "linear": lambda t: t,
}
T_SAMPLES = [i / 200 for i in range(201)]


def test_curve_registry_order_is_the_cycle_order():
    assert list(CURVES) == ["smooth", "sphere", "root", "sharp", "linear", "custom"]


@pytest.mark.parametrize("name", sorted(FORMULAS))
def test_named_curves_match_their_formula(name):
    for t in T_SAMPLES:
        assert CURVES[name](t) == pytest.approx(FORMULAS[name](t), abs=1e-12)


def _check_curve_properties(f):
    assert f(0.0) == 0.0
    assert f(1.0) == pytest.approx(1.0, abs=1e-15)
    values = [f(t) for t in T_SAMPLES]
    assert all(0.0 <= v <= 1.0 for v in values)
    assert all(a <= b for a, b in zip(values, values[1:]))  # monotone non-decreasing


@pytest.mark.parametrize("name", sorted(CURVES))
def test_every_curve_has_f0_0_f1_1_and_is_monotone(name):
    _check_curve_properties(CURVES[name])


@pytest.mark.parametrize("p", CUSTOM_SHAPE_STEPS)
def test_every_custom_step_has_f0_0_f1_1_and_is_monotone(p):
    _check_curve_properties(custom_curve(p))


def test_custom_is_t_to_the_p_and_matches_root_sharp_linear():
    for t in T_SAMPLES:
        assert custom_curve(1.5)(t) == pytest.approx(t**1.5, abs=1e-15)
        assert custom_curve(0.5)(t) == pytest.approx(CURVES["root"](t), abs=1e-15)
        assert custom_curve(2.0)(t) == pytest.approx(CURVES["sharp"](t), abs=1e-15)
        assert custom_curve(1.0)(t) == pytest.approx(t, abs=1e-15)


def test_custom_steps_order_the_curves_from_round_to_sharp():
    """Smaller p lies above larger p for every t in (0, 1): rounder = more influence."""
    for t in (0.1, 0.3, 0.5, 0.7, 0.9):
        values = [custom_curve(p)(t) for p in CUSTOM_SHAPE_STEPS]
        assert all(a > b for a, b in zip(values, values[1:]))


@pytest.mark.parametrize("bad", [0.0, -1.0, math.inf, math.nan])
def test_custom_curve_rejects_a_non_positive_or_non_finite_power(bad):
    with pytest.raises(ValueError):
        custom_curve(bad)


@pytest.mark.parametrize("metric", sorted(METRICS))
@pytest.mark.parametrize("p", CUSTOM_SHAPE_STEPS)
def test_compute_influence_custom_uses_curve_power(metric, p):
    mesh, ids = grid()
    seed, neighbour = ids[4][4], ids[4][5]  # d = 1 under both metrics
    weights = compute_influence(
        mesh, {seed}, 4.0, metric=metric, curve="custom", curve_power=p
    )
    assert weights[seed] == 1.0
    assert weights[neighbour] == pytest.approx(0.75**p, abs=1e-15)
    assert ids[4][8] not in weights  # d = 4 = r: zero


def test_curve_power_is_ignored_by_the_other_curves():
    mesh, ids = grid()
    a = compute_influence(mesh, {ids[4][4]}, 4.0, curve="smooth", curve_power=3.0)
    b = compute_influence(mesh, {ids[4][4]}, 4.0, curve="smooth")
    assert a == b


@pytest.mark.parametrize("name", sorted(CURVES))
def test_every_curve_gives_seeds_one_and_zero_at_the_radius(name):
    mesh, ids = grid()
    weights = compute_influence(mesh, {ids[4][4]}, 2.0, metric="geodesic", curve=name)
    assert weights[ids[4][4]] == 1.0
    assert ids[4][6] not in weights  # d = r
    assert all(0.0 < w <= 1.0 for w in weights.values())
