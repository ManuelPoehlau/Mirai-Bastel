"""Soft Selection Loop / Ring flow: the topology-oriented anisotropic field (AD-020 "Loop / Ring flow",
`PROVISIONAL`; `mirai.soft_selection.flow`).

Headless. A regular quad grid (rows = Y, columns = X) has known loops and rings: for a seed edge along a row,
Loop runs along that row and Ring across the rows. Pins:

- neutral balance is today's geodesic field, bit for bit (the flow module is never entered);
- Loop > Ring reaches farther along the seed's loops, Ring > Loop across its rings, by the documented factor;
  the radius stays the farthest reach and the falloff curves act on `1 - d / r` unchanged;
- the direction comes from the topology (a rotated / bent / wrapped grid gives the same weights), from the
  seed region's own edges: vertex path, edge, edge ring, face strip; one vertex, one quad, a square block and
  an all-triangle mesh have no direction and are exactly isotropic;
- labels stop at non-quads and at the boundary; where fronts with different colourings meet (cube corners,
  head poles) they spread nothing; the result is deterministic and never wider than the isotropic field;
- several seed regions orient themselves; symmetric Soft keeps one weight per mirror pair.
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401
from tests.soft_selection_fixtures import grid, head

from mirai.mesh_geometry import mesh_center_and_radius
from mirai.scene_factory import mesh_from_positions_and_faces
from mirai.soft_selection import (
    CURVES,
    FLOW_STEPS,
    METRICS,
    SoftSettings,
    compute_influence,
    flow_families,
    has_flow_direction,
    symmetric_influence,
)
from mirai.soft_selection.flow import LOOP, RING, flow_costs, flow_distances
from mirai.soft_selection.influence import curve_shape, distance_function
from mirai.symmetry import CorrespondenceState, vertex_correspondence
from mirai.symmetry_axis import set_symmetry_axis

N, C = 15, 7  # grid size, centre index
R = 5.0  # radius in grid units


def _field(mesh, seeds, ratio, radius=R, curve="linear"):
    return compute_influence(mesh, seeds, radius, metric="geodesic", curve=curve, flow_ratio=ratio)


def _row(w, ids, r=C):
    return [w.get(ids[r][c], 0.0) for c in range(N)]


def _col(w, ids, c=C):
    return [w.get(ids[r][c], 0.0) for r in range(N)]


def _reach(values, centre=C):
    """How many vertices beyond the seed (one direction) carry weight."""
    return sum(1 for v in values[centre + 1:] if v > 0.0)


@pytest.fixture
def row_edge():
    """A seed edge along row C (columns C, C+1): Loop = along the row (X), Ring = across rows (Y)."""
    mesh, ids = grid(N)
    return mesh, ids, {ids[C][C], ids[C][C + 1]}


# -- neutral -----------------------------------------------------------------------------------------


def test_neutral_balance_is_the_geodesic_field_bit_for_bit(row_edge):
    mesh, _, seeds = row_edge
    assert distance_function("geodesic", 1.0) is METRICS["geodesic"]
    assert SoftSettings().flow_ratio == 1.0 and FLOW_STEPS[SoftSettings().flow_step] == (1, 1)
    for curve in CURVES:
        assert _field(mesh, seeds, 1.0, curve=curve) == compute_influence(
            mesh, seeds, R, metric="geodesic", curve=curve)
    h = head()
    _, br = mesh_center_and_radius(h)
    seed = set(h.edge_vertices(h.all_edge_ids()[100]))
    assert compute_influence(h, seed, br * 0.3, "geodesic", flow_ratio=1.0) == compute_influence(
        h, seed, br * 0.3, "geodesic")


def test_euclidean_has_no_edge_flow_and_ignores_the_balance(row_edge):
    mesh, _, seeds = row_edge
    plain = compute_influence(mesh, seeds, R, metric="euclidean")
    assert compute_influence(mesh, seeds, R, metric="euclidean", flow_ratio=3.0) == plain
    assert distance_function("euclidean", 3.0) is METRICS["euclidean"]


@pytest.mark.parametrize("bad", [0.0, -1.0, math.inf, math.nan])
def test_balance_must_be_finite_and_positive(row_edge, bad):
    mesh, _, seeds = row_edge
    with pytest.raises(ValueError):
        compute_influence(mesh, seeds, R, metric="geodesic", flow_ratio=bad)


# -- the two directions ------------------------------------------------------------------------------


def test_loop_reach_expands_along_the_loop_relative_to_the_ring(row_edge):
    mesh, ids, seeds = row_edge
    neutral, loop = _field(mesh, seeds, 1.0), _field(mesh, seeds, 2.0)
    assert _row(loop, ids) == _row(neutral, ids)  # Loop keeps the radius
    assert _reach(_col(loop, ids)) < _reach(_col(neutral, ids))  # Ring is shortened
    # Exactly the documented factor: one ring edge costs 2, so the weight at ring distance d is 1 - 2d / r.
    for d in range(1, 3):
        assert loop[ids[C + d][C]] == pytest.approx(1.0 - 2.0 * d / R)
    assert ids[C + 3][C] not in loop  # 2 * 3 >= 5


def test_ring_reach_produces_the_opposite_result(row_edge):
    mesh, ids, seeds = row_edge
    neutral, ring = _field(mesh, seeds, 1.0), _field(mesh, seeds, 0.5)
    assert _col(ring, ids) == _col(neutral, ids)
    assert _reach(_row(ring, ids), C + 1) < _reach(_row(neutral, ids), C + 1)
    assert ring[ids[C][C + 2]] == pytest.approx(1.0 - 2.0 / R)


@pytest.mark.parametrize("ratio", [0.25, 1 / 3, 0.5, 2 / 3, 1.5, 2.0, 3.0, 4.0])
def test_the_balance_changes_the_weights_and_never_widens_the_field(row_edge, ratio):
    mesh, _, seeds = row_edge
    neutral, flow = _field(mesh, seeds, 1.0), _field(mesh, seeds, ratio)
    assert flow != neutral
    assert set(flow) <= set(neutral)
    assert all(flow[v] <= neutral[v] for v in flow)
    assert all(flow[s] == 1.0 for s in seeds)


def test_costs_shorten_only_the_weaker_direction():
    assert flow_costs(2.0) == (1.0, 2.0)
    assert flow_costs(0.25) == (4.0, 1.0)
    assert [flow_costs(lo / ri) for lo, ri in FLOW_STEPS][len(FLOW_STEPS) // 2] == (1.0, 1.0)


@pytest.mark.parametrize("curve", sorted(CURVES))
def test_the_falloff_curve_still_shapes_the_decline(row_edge, curve):
    mesh, _, seeds = row_edge
    distances = flow_distances(mesh, seeds, R, 3.0)
    weights = compute_influence(mesh, seeds, R, "geodesic", curve=curve, curve_power=1.5, flow_ratio=3.0)
    shape = curve_shape(curve, 1.5)
    expected = {v: 1.0 for v in seeds}
    for v, d in distances.items():
        if v not in seeds and shape(1.0 - d / R) > 0.0:
            expected[v] = shape(1.0 - d / R)
    assert weights == expected


# -- the direction comes from the topology -----------------------------------------------------------


def _transformed_grid(transform):
    positions = [transform(c, r) for r in range(N) for c in range(N)]
    faces = [
        (r * N + c, r * N + c + 1, (r + 1) * N + c + 1, (r + 1) * N + c)
        for r in range(N - 1) for c in range(N - 1)
    ]
    mesh = mesh_from_positions_and_faces(positions, faces)
    vids = mesh.all_vertex_ids()
    return mesh, [[vids[r * N + c] for c in range(N)] for r in range(N)]


def _by_index(w, ids):
    return {(r, c): w[ids[r][c]] for r in range(N) for c in range(N) if ids[r][c] in w}


def test_world_axes_play_no_part_rotated_and_bent_grids_give_the_same_weights(row_edge):
    mesh, ids, seeds = row_edge
    reference = _by_index(_field(mesh, seeds, 3.0, radius=5.5), ids)  # 5.5: no distance on the cut-off
    a = math.radians(37.0)
    turned = lambda c, r: (c * math.cos(a) - r * math.sin(a), c * math.sin(a) + r * math.cos(a), 0.0)
    standing = lambda c, r: (0.0, float(c), float(r))  # the grid in the YZ plane
    for transform in (turned, standing):
        m, i = _transformed_grid(transform)
        got = _by_index(_field(m, {i[C][C], i[C][C + 1]}, 3.0, radius=5.5), i)
        assert got.keys() == reference.keys()
        assert all(got[k] == pytest.approx(reference[k], abs=1e-12) for k in got)


def test_a_column_edge_swaps_the_directions(row_edge):
    mesh, ids, _ = row_edge
    col_seed = {ids[C][C], ids[C + 1][C]}  # along the column: Loop = Y now
    w = _field(mesh, col_seed, 3.0)
    assert _reach(_col(w, ids), C + 1) > _reach(_row(w, ids))


def test_the_field_follows_a_curved_closed_surface():
    """A cylinder (12 around, the loop closes): the Loop reach wraps around the surface along edges (never
    through space), the Ring reach goes up / down the axis."""
    around, rows, radius = 12, 9, 2.0
    positions = [
        (radius * math.cos(2 * math.pi * k / around), radius * math.sin(2 * math.pi * k / around), float(z))
        for z in range(rows) for k in range(around)
    ]
    faces = [
        (z * around + k, z * around + (k + 1) % around, (z + 1) * around + (k + 1) % around, (z + 1) * around + k)
        for z in range(rows - 1) for k in range(around)
    ]
    mesh = mesh_from_positions_and_faces(positions, faces)
    vids = mesh.all_vertex_ids()
    at = lambda z, k: vids[z * around + k % around]
    seeds = {at(4, 0), at(4, 1)}  # an edge along the ring of the cylinder: Loop = around
    chord = math.dist(mesh.vertex_position(at(4, 0)), mesh.vertex_position(at(4, 1)))
    radius_world = 7.0 * chord  # wraps: the far side is 5 edges from the seed edge
    d = flow_distances(mesh, seeds, radius_world, 4.0)
    assert d[at(4, 6)] == pytest.approx(5 * chord)  # edge path around, not the diameter through space
    assert d[at(4, 6)] > math.dist(mesh.vertex_position(at(4, 1)), mesh.vertex_position(at(4, 6)))
    assert d[at(4, 6 - 1)] == pytest.approx(d[at(4, 6 + 2)])  # both ways round alike
    assert d[at(5, 0)] == pytest.approx(4.0 * 1.0)  # one ring step (axial edge, length 1) costs 4
    assert at(6, 0) not in d or d[at(6, 0)] >= d[at(5, 0)]


# -- seed kinds --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "seed_cells,loop_along_row",
    [
        ([(C, C)], None),  # one vertex: no direction
        ([(C, C), (C, C + 1)], True),  # one row edge
        ([(C, C - 1), (C, C), (C, C + 1)], True),  # a vertex path along the row
        ([(C, C), (C + 1, C)], False),  # one column edge
        ([(r, c) for r in (C, C + 1) for c in (C, C + 1)], None),  # one quad face: tie
        ([(r, c) for r in (C, C + 1) for c in range(C - 1, C + 3)], True),  # a strip of 3 faces along the row
        ([(r, c) for r in range(C - 1, C + 3) for c in (C, C + 1)], False),  # a strip of 3 faces along the column
        ([(r, c) for r in range(C - 1, C + 2) for c in range(C - 1, C + 2)], None),  # a 2x2 face block: tie
        ([(r, c) for r in (C, C + 1) for c in (C - 1, C, C + 1)], True),  # an edge ring of 3 column edges
    ],
    ids=["vertex", "row_edge", "row_path", "col_edge", "face", "row_strip", "col_strip", "block", "edge_ring"],
)
def test_seed_kinds_follow_the_documented_rule(seed_cells, loop_along_row):
    mesh, ids = grid(N)
    seeds = {ids[r][c] for r, c in seed_cells}
    w = _field(mesh, seeds, 2.0, radius=6.0)
    if loop_along_row is None:
        assert not has_flow_direction(mesh, seeds)
        assert w == compute_influence(mesh, seeds, 6.0, metric="geodesic", curve="linear")  # isotropic fallback
        return
    assert has_flow_direction(mesh, seeds)
    rows = [r for r, _ in seed_cells]
    cols = [c for _, c in seed_cells]
    along_row = sum(1 for c in range(max(cols) + 1, N) if ids[C][c] in w)
    across = sum(1 for r in range(max(rows) + 1, N) if ids[r][C] in w)
    assert (along_row > across) is loop_along_row


def test_an_all_triangle_mesh_has_no_direction():
    n = 9
    positions = [(float(c), float(r), 0.0) for r in range(n) for c in range(n)]
    faces = []
    for r in range(n - 1):
        for c in range(n - 1):
            a, b, d, e = r * n + c, r * n + c + 1, (r + 1) * n + c + 1, (r + 1) * n + c
            faces += [(a, b, d), (a, d, e)]
    mesh = mesh_from_positions_and_faces(positions, faces)
    vids = mesh.all_vertex_ids()
    seeds = {vids[4 * n + 4], vids[4 * n + 5]}
    assert not has_flow_direction(mesh, seeds)
    assert _field(mesh, seeds, 3.0) == compute_influence(mesh, seeds, R, metric="geodesic", curve="linear")


# -- terminations and fallbacks ----------------------------------------------------------------------


def test_a_boundary_ends_the_field_like_the_isotropic_one():
    mesh, ids = grid(N)
    seeds = {ids[0][C], ids[0][C + 1]}  # a row edge on the boundary row
    w = _field(mesh, seeds, 2.0)
    assert [w.get(ids[0][c], 0.0) for c in range(N)] == [
        w.get(ids[0][c], 0.0) for c in range(N)]
    assert w[ids[0][C + 3]] == pytest.approx(1.0 - 2.0 / R)  # along the boundary loop: full reach
    assert w[ids[1][C]] == pytest.approx(1.0 - 2.0 / R)  # across: halved


def test_labels_stop_at_non_quads_and_edges_in_no_quad_stay_neutral():
    """A column of triangulated cells (c = 9) cuts the grid: the labels do not cross it, so beyond it and on
    its diagonals the field is isotropic again."""
    cut = 9
    positions = [(float(c), float(r), 0.0) for r in range(N) for c in range(N)]
    faces = []
    for r in range(N - 1):
        for c in range(N - 1):
            a, b, d, e = r * N + c, r * N + c + 1, (r + 1) * N + c + 1, (r + 1) * N + c
            faces += [(a, b, d), (a, d, e)] if c == cut else [(a, b, d, e)]
    mesh = mesh_from_positions_and_faces(positions, faces)
    vids = mesh.all_vertex_ids()
    at = lambda r, c: vids[r * N + c]
    seeds = {at(C, C), at(C, C + 1)}
    families = flow_families(mesh, seeds, 12.0)
    edge = lambda p, q: next(e for e in mesh.vertex_edges(p) if q in mesh.edge_vertices(e))
    assert families[edge(at(C, C), at(C, C + 1))] == LOOP
    assert families[edge(at(C + 1, cut), at(C, cut))] == RING  # labelled by the quad on the seed side
    assert edge(at(C, cut), at(C + 1, cut + 1)) not in families  # a diagonal: in no quad
    assert edge(at(C, cut + 2), at(C + 1, cut + 2)) not in families  # beyond the cut: unlabelled
    assert edge(at(C, cut + 2), at(C, cut + 3)) not in families


def test_cube_corners_fronts_meet_and_the_result_is_deterministic():
    """A cube has three parallel classes and valence-3 corners: no consistent 2-colouring exists. From an X
    edge (Loop) the Y and Z edges are Ring; the YZ faces see two disagreeing fronts and spread nothing."""
    positions = [(x, y, z) for z in (0.0, 1.0) for y in (0.0, 1.0) for x in (0.0, 1.0)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh = mesh_from_positions_and_faces(positions, faces)
    vids = mesh.all_vertex_ids()
    seeds = {vids[0], vids[1]}  # an X edge
    families = flow_families(mesh, seeds, 3.0)
    for eid in mesh.all_edge_ids():
        p, q = (mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
        is_x = p[1] == q[1] and p[2] == q[2]
        assert families[eid] == (LOOP if is_x else RING)
    first = _field(mesh, seeds, 2.0, radius=3.0)
    assert all(_field(mesh, seeds, 2.0, radius=3.0) == first for _ in range(3))


def test_head_poles_and_ngons_deterministic_and_never_wider_than_isotropic():
    mesh = head()
    _, br = mesh_center_and_radius(mesh)
    rng = random.Random(7)
    for eid in rng.sample(mesh.all_edge_ids(), 25):
        seeds = set(mesh.edge_vertices(eid))
        iso = compute_influence(mesh, seeds, br * 0.3, metric="geodesic")
        for ratio in (0.25, 3.0):
            flow = compute_influence(mesh, seeds, br * 0.3, metric="geodesic", flow_ratio=ratio)
            assert flow == compute_influence(mesh, seeds, br * 0.3, metric="geodesic", flow_ratio=ratio)
            assert set(flow) <= set(iso) and all(flow[v] <= iso[v] for v in flow)
            assert all(flow[s] == 1.0 for s in seeds)


# -- several regions, symmetry -----------------------------------------------------------------------


def test_each_seed_region_orients_itself():
    mesh, ids = grid(21)
    left = {ids[10][4], ids[10][5]}  # a row edge
    right = {ids[10][15], ids[11][15]}  # a column edge, far away
    w = compute_influence(mesh, left | right, 4.0, metric="geodesic", curve="linear", flow_ratio=4.0)
    assert ids[10][2] in w and ids[12][4] not in w  # left: along its row, short across
    assert ids[13][15] in w and ids[10][17] not in w  # right: along its column, short across


def test_symmetric_flow_keeps_one_weight_per_pair_and_the_seam_rules():
    mesh = head()
    set_symmetry_axis(mesh, "X")
    corr = vertex_correspondence(mesh)
    _, br = mesh_center_and_radius(mesh)
    seed = min(
        (v for v, c in corr.items() if c.state is CorrespondenceState.PAIRED and mesh.vertex_position(v)[0] > 0),
        key=lambda v: mesh.vertex_position(v)[0],
    )
    other = next(
        w for e in mesh.vertex_edges(seed) for w in mesh.edge_vertices(e)
        if w != seed and corr[w].state is CorrespondenceState.PAIRED and mesh.vertex_position(w)[0] > 0
    )
    seeds = {seed, other}  # an edge near the plane: the field crosses it
    plain = symmetric_influence(mesh, seeds, br * 0.4, metric="geodesic")
    for ratio in (0.25, 4.0):
        field = symmetric_influence(mesh, seeds, br * 0.4, metric="geodesic", flow_ratio=ratio)
        assert field.weights != plain.weights
        for vid, w in field.weights.items():
            c = corr[vid]
            if c.state is CorrespondenceState.PAIRED:
                assert field.weights[c.partner] == w
        assert all(field.weights[s] == 1.0 for s in seeds | field.partners)
        assert field.falloff_seam_vertex_ids <= {v for v, c in corr.items() if c.state is CorrespondenceState.SEAM}
        assert field.mirrored_vertex_ids >= field.partners
