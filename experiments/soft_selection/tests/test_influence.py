"""compute_influence(): weights, metrics, curves, seeds (handoff §6, first block)."""

from __future__ import annotations

import math

import pytest

from core import EdgeId, FaceId, Selection, SelectionMode, VertexId

from soft_selection.influence import (
    CURVES,
    METRICS,
    compute_influence,
    primary_pivot,
    seeds_from_selection,
)

from ._fixtures import LIP_HALF_GAP, grid, head, lip

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


# -- seeds from V / E / F, stale ids, empty --------------------------------------


def test_seeds_from_vertex_edge_face_selection():
    mesh, ids = grid(3)
    selection = Selection()
    selection.mode = SelectionMode.VERTEX
    selection.set({ids[1][1]})
    assert seeds_from_selection(mesh, selection) == {ids[1][1]}

    edge = next(e for e in mesh.vertex_edges(ids[0][0]) if ids[0][1] in mesh.edge_vertices(e))
    selection.mode = SelectionMode.EDGE
    selection.set({edge})
    assert seeds_from_selection(mesh, selection) == {ids[0][0], ids[0][1]}

    face = mesh.all_face_ids()[0]
    selection.mode = SelectionMode.FACE
    selection.set({face})
    assert seeds_from_selection(mesh, selection) == set(mesh.face_vertices(face))


def test_stale_ids_are_skipped():
    mesh, ids = grid(3)
    selection = Selection()
    selection.vertices = {ids[1][1], VertexId(9999)}
    selection.edges = {EdgeId(9999)}
    selection.faces = {FaceId(9999)}
    assert seeds_from_selection(mesh, selection, SelectionMode.VERTEX) == {ids[1][1]}
    assert seeds_from_selection(mesh, selection, SelectionMode.EDGE) == set()
    assert seeds_from_selection(mesh, selection, SelectionMode.FACE) == set()
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
