"""Inflate / Pinch plans (`mirai.topology.inflate_pinch`, 2026-11-15, `PROVISIONAL`).

Headless, on the plan: sphere, cylinder, regular and skewed quad planes, irregular topology (jitter, triangles, an
n-gon), the head basemesh and the Gollum cage (declared X symmetry: lips, cheek, nose, eye) - every frame checked for
symmetry (pairs bitwise mirrored, seam exactly on the plane), nothing outside the field moving, finite positions, the
press state at amount 0, linearity (no drift), and for Pinch that Radial, Loop and Ring differ in the documented way.
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh
from mirai.scene_factory import mesh_from_positions_and_faces
from mirai.soft_selection import compute_influence, symmetric_influence
from mirai.symmetry import CorrespondenceState, vertex_correspondence
from mirai.topology.inflate_pinch import (
    PINCH_DIRECTIONS,
    PINCH_MAX,
    PINCH_MIN,
    DeformRefused,
    plan_inflate,
    plan_pinch,
)
from mirai.topology.loop_ring import edge_loop
from tests.mesh_invariants import assert_mesh_invariants
from tests.surface_slide_fixtures import cube_sphere, cylinder as cylinder_surface
from tests.test_surface_slide_plan import gollum, head, near


# -- fixtures ------------------------------------------------------------------------------------------------------


def as_mesh(surface) -> Mesh:
    positions = [tuple(float(c) for c in p) for p in surface.V]
    return mesh_from_positions_and_faces(positions, [list(f) for f in surface.faces])


def grid(n: int = 11, shear: float = 0.0) -> tuple[Mesh, dict]:
    """n x n vertices in z = 0 (x = c + shear * r, y = r); returns the mesh and (row, col) -> id."""
    positions = [(c + shear * r, float(r), 0.0) for r in range(n) for c in range(n)]
    faces = [[r * n + c, r * n + c + 1, (r + 1) * n + c + 1, (r + 1) * n + c]
             for r in range(n - 1) for c in range(n - 1)]
    mesh = mesh_from_positions_and_faces(positions, faces)
    ids = mesh.all_vertex_ids()
    return mesh, {(r, c): ids[r * n + c] for r in range(n) for c in range(n)}


def irregular(seed: int = 3) -> tuple[Mesh, dict]:
    """An 11 x 11 grid with jittered points, its lower-left quads split into triangles and a 6-gon at the right
    (two quads merged with their shared edge's ends kept): mixed topology, no regular spacing."""
    rng = random.Random(seed)
    n = 11
    positions = [(c + rng.uniform(-0.2, 0.2), r + rng.uniform(-0.2, 0.2), rng.uniform(-0.1, 0.1))
                 for r in range(n) for c in range(n)]
    faces = []
    for r in range(n - 1):
        for c in range(n - 1):
            a, b, d, e = r * n + c, r * n + c + 1, (r + 1) * n + c + 1, (r + 1) * n + c
            if (r, c) == (5, 8):
                faces.append([a, b, b + 1, d + 1, d, e])  # the 6-gon covers (5, 8) and (5, 9)
            elif (r, c) == (5, 9):
                continue
            elif r < 4 and c < 4:
                faces += [[a, b, d], [a, d, e]]
            else:
                faces.append([a, b, d, e])
    mesh = mesh_from_positions_and_faces(positions, faces)
    ids = mesh.all_vertex_ids()
    return mesh, {(r, c): ids[r * n + c] for r in range(n) for c in range(n)}


def field(mesh: Mesh, seeds, radius: float) -> dict:
    """The Soft field as a Soft W/E/R computes it (geodesic, smooth; symmetric under a definition)."""
    if mesh.symmetry_definition is None:
        return compute_influence(mesh, set(seeds), radius, metric="geodesic", curve="smooth")
    return symmetric_influence(mesh, set(seeds), radius, metric="geodesic", curve="smooth").weights


def frame(mesh: Mesh, plan, amount: float) -> dict:
    """All vertex positions with the plan's frame at `amount` written over the press state."""
    result = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    result.update(plan.positions(amount))
    return result


def delta(mesh: Mesh, positions: dict, v) -> tuple[float, float, float]:
    p, q = mesh.vertex_position(v), positions[v]
    return (q[0] - p[0], q[1] - p[1], q[2] - p[2])


def norm(a) -> float:
    return math.sqrt(sum(c * c for c in a))


def check_frame(mesh: Mesh, plan, amount: float, weights=None) -> dict:
    """The common contract of every frame: finite, only the plan's vertices move, nothing outside the field moves,
    amount 0 is the press state, the symmetry stays exact (pairs mirrored bit for bit, seam on the plane)."""
    positions = frame(mesh, plan, amount)
    for v, p in positions.items():
        assert all(math.isfinite(c) for c in p), v
        if v not in plan.movable:
            assert p == mesh.vertex_position(v)
    if weights is not None:
        assert plan.movable <= set(weights)
    zero = plan.positions(0.0)
    assert all(zero[v] == mesh.vertex_position(v) for v in plan.movable)
    definition = mesh.symmetry_definition
    if definition is not None:
        for v, corr in vertex_correspondence(mesh).items():
            p = positions[v]
            if corr.state is CorrespondenceState.SEAM:
                assert p[0] == 0.0, v
            elif corr.state is CorrespondenceState.PAIRED:
                q = positions[corr.partner]
                assert (p[0], p[1], p[2]) == (-q[0], q[1], q[2]), v
    return positions


# -- Inflate -------------------------------------------------------------------------------------------------------


def test_inflate_a_whole_sphere_grows_it_radially():
    mesh = as_mesh(cube_sphere(8))
    plan = plan_inflate(mesh, mesh.all_vertex_ids())
    positions = check_frame(mesh, plan, 0.2)
    for v in mesh.all_vertex_ids():
        p, q = mesh.vertex_position(v), positions[v]
        assert norm(q) == pytest.approx(1.2, abs=2e-3)  # the area-weighted normal of a cube sphere is ~radial
        cosine = sum(a * b for a, b in zip(p, q)) / (norm(p) * norm(q))
        assert cosine > 1.0 - 1e-4  # within ~0.8 degrees at the cube corners


def test_inflate_on_a_sphere_with_soft_follows_the_falloff_and_stays_inside_the_field():
    mesh = as_mesh(cube_sphere(10))
    seed = near(mesh, (0.0, 1.0, 0.0))
    weights = field(mesh, [seed], 0.8)
    plan = plan_inflate(mesh, [seed], weights=weights)
    assert plan.movable == frozenset(weights)
    positions = check_frame(mesh, plan, 0.3, weights)
    for v in plan.movable:
        assert norm(delta(mesh, positions, v)) == pytest.approx(0.3 * weights[v], rel=1e-9)
    # Negative = deflate, and the frame is linear in the amount (no drift).
    back = check_frame(mesh, plan, -0.3, weights)
    for v in plan.movable:
        a, b = delta(mesh, positions, v), delta(mesh, back, v)
        assert a == pytest.approx(tuple(-c for c in b), abs=1e-12)


def test_inflate_on_a_cylinder_moves_only_across_the_axis():
    mesh = as_mesh(cylinder_surface(segments=24, rows=12))
    seed = near(mesh, (1.0, 0.0, 0.0))
    weights = field(mesh, [seed], 1.0)
    plan = plan_inflate(mesh, [seed], weights=weights)
    positions = check_frame(mesh, plan, 0.25, weights)
    for v in plan.movable:
        p, q = mesh.vertex_position(v), positions[v]
        if abs(p[1]) < 1.4:  # not on a rim (an open rim's normal tilts)
            assert q[1] == pytest.approx(p[1], abs=1e-12)
            assert math.hypot(q[0], q[2]) > math.hypot(p[0], p[2])


def test_inflate_on_a_flat_grid_is_the_weight_along_z():
    mesh, ids = grid()
    seed = ids[(5, 5)]
    weights = field(mesh, [seed], 3.5)
    plan = plan_inflate(mesh, [seed], weights=weights)
    positions = check_frame(mesh, plan, 1.0, weights)
    for v in plan.movable:
        d = delta(mesh, positions, v)
        assert d[:2] == (0.0, 0.0) and d[2] == pytest.approx(weights[v], abs=1e-12)
    # The profile along a row is the smooth curve itself: zero slope at the radius, no step at the boundary.
    row = [positions[ids[(5, c)]][2] for c in range(5, 11)]
    assert row == sorted(row, reverse=True) and row[-1] == 0.0


def test_inflate_with_soft_off_moves_only_the_selection():
    mesh, ids = grid()
    selected = {ids[(5, 5)], ids[(5, 6)]}
    plan = plan_inflate(mesh, selected)
    assert plan.movable == frozenset(selected) and plan.weights is None
    positions = check_frame(mesh, plan, 0.5)
    assert {v for v in mesh.all_vertex_ids() if positions[v] != mesh.vertex_position(v)} == selected


def test_inflate_respects_the_mask():
    mesh, ids = grid()
    seed = ids[(5, 5)]
    weights = field(mesh, [seed], 3.5)
    masked, half = ids[(5, 6)], ids[(6, 5)]
    plan = plan_inflate(mesh, [seed], weights=weights, mask={masked: 1.0, half: 0.5})
    assert masked not in plan.movable
    positions = check_frame(mesh, plan, 1.0)
    assert positions[half][2] == pytest.approx(0.5 * weights[half])
    with pytest.raises(DeformRefused, match="masked"):
        plan_inflate(mesh, [seed], mask={seed: 1.0})


# -- Pinch: the three directions -----------------------------------------------------------------------------------


def _edge_seed_plans(mesh, ids):
    """Seed = the horizontal edge (5, 5)-(5, 6): its own edge is the Loop family (it extends along x)."""
    seeds = [ids[(5, 5)], ids[(5, 6)]]
    weights = field(mesh, seeds, 3.5)
    return seeds, weights, {d: plan_pinch(mesh, seeds, d, weights=weights) for d in PINCH_DIRECTIONS}


def test_pinch_radial_loop_and_ring_differ_on_a_quad_plane():
    mesh, ids = grid()
    seeds, weights, plans = _edge_seed_plans(mesh, ids)
    frames = {d: check_frame(mesh, plan, 0.5, weights) for d, plan in plans.items()}
    probe = ids[(6, 7)]  # above and to the right of the edge, inside the field
    radial, loop, ring = (delta(mesh, frames[d], probe) for d in PINCH_DIRECTIONS)
    # Radial: towards the seeds' centroid (5.5, 5), both components.
    assert radial[0] < 0.0 and radial[1] < 0.0
    # Loop: across the loop onto the selected line - along the ring edges (y) only.
    assert loop[0] == 0.0 and loop[1] < 0.0
    # Ring: along the loop towards the selection - along the loop edges (x) only.
    assert ring[1] == 0.0 and ring[0] < 0.0
    for v in plans["loop"].movable:
        assert delta(mesh, frames["loop"], v)[0] == 0.0
        assert delta(mesh, frames["ring"], v)[1] == 0.0
        assert delta(mesh, frames["radial"], v)[2] == 0.0  # a flat sheet stays flat
    # Loop pulls the row above exactly the share `amount * w` of the way onto the seeds' row.
    v = ids[(6, 5)]
    assert frames["loop"][v][1] == pytest.approx(6.0 - 0.5 * weights[v])


def test_pinch_loop_follows_the_real_edges_of_a_skewed_grid():
    mesh, ids = grid(shear=0.6)
    seeds, weights, plans = _edge_seed_plans(mesh, ids)
    positions = check_frame(mesh, plans["loop"], 0.5, weights)
    ring_edge = (0.6, 1.0)  # the sheared "vertical" edges
    for v in plans["loop"].movable:
        d = delta(mesh, positions, v)
        assert d[0] * ring_edge[1] - d[1] * ring_edge[0] == pytest.approx(0.0, abs=1e-12)  # parallel to the edge
    v = ids[(7, 6)]
    assert positions[v][1] == pytest.approx(7.0 - 0.5 * weights[v] * 2.0)  # lands on the way to row 5


def test_pinch_on_an_edge_ring_selection_pulls_across_the_strip():
    """The selected edges of a ring (vertical edges side by side) are the Ring family: Loop pinches the strip's
    neighbours onto it along those edges (y); Ring gathers along the strip (x)."""
    mesh, ids = grid()
    seeds = [ids[(r, c)] for r in (5, 6) for c in (4, 5, 6)]  # rungs (5..6, c) for c = 4, 5, 6
    weights = field(mesh, seeds, 3.5)
    loop = plan_pinch(mesh, seeds, "loop", weights=weights)
    ring = plan_pinch(mesh, seeds, "ring", weights=weights)
    lp, rp = check_frame(mesh, loop, 0.5, weights), check_frame(mesh, ring, 0.5, weights)
    probe = ids[(7, 7)]
    assert delta(mesh, lp, probe)[0] == 0.0 and delta(mesh, lp, probe)[1] < 0.0
    assert delta(mesh, rp, probe)[1] == 0.0 and delta(mesh, rp, probe)[0] < 0.0


def test_pinch_on_a_cylinder_loop_and_ring_follow_the_tube():
    mesh = as_mesh(cylinder_surface(segments=24, rows=12))
    start = near(mesh, (1.0, 0.0, 0.0))
    edge = next(e for e in mesh.vertex_edges(start)
                if abs(mesh.vertex_position(next(v for v in mesh.edge_vertices(e) if v != start))[1]) < 1e-9)
    around = {v for e in edge_loop(mesh, edge).edges for v in mesh.edge_vertices(e)}  # the closed loop at y = 0
    assert len(around) == 24
    weights = field(mesh, around, 0.8)
    loop = plan_pinch(mesh, around, "loop", weights=weights)
    lp = check_frame(mesh, loop, 0.5, weights)
    for v in loop.movable:
        p, q = mesh.vertex_position(v), lp[v]
        assert (q[0], q[2]) == pytest.approx((p[0], p[2]), abs=1e-12)  # along the tube only
        assert abs(q[1]) <= abs(p[1])
    # A vertical seed line along y: it extends along y, so *its* Loop family is vertical (Loop / Ring are relative
    # to the selection, as for the Soft flow). Loop pinches around the tube onto the column (y unchanged), Ring
    # gathers along the column (only y changes).
    column = [near(mesh, (1.0, y, 0.0)) for y in (-0.25, 0.0, 0.25)]
    weights = field(mesh, column, 0.9)
    loop = plan_pinch(mesh, column, "loop", weights=weights)
    ring = plan_pinch(mesh, column, "ring", weights=weights)
    lp, rp = check_frame(mesh, loop, 0.5, weights), check_frame(mesh, ring, 0.5, weights)
    around = [v for v in loop.movable if lp[v] != mesh.vertex_position(v)]
    along = [v for v in ring.movable if rp[v] != mesh.vertex_position(v)]
    assert around and along
    for v in around:
        p, q = mesh.vertex_position(v), lp[v]
        assert q[1] == pytest.approx(p[1], abs=1e-12)
        assert math.atan2(abs(q[2]), q[0]) < math.atan2(abs(p[2]), p[0])  # closer to the seed column at angle 0
    for v in along:
        p, q = mesh.vertex_position(v), rp[v]
        assert (q[0], q[2]) == pytest.approx((p[0], p[2]), abs=1e-12) and abs(q[1]) < abs(p[1])


def test_pinch_radial_on_a_sphere_stays_near_the_surface():
    mesh = as_mesh(cube_sphere(10))
    seed = near(mesh, (0.0, 1.0, 0.0))
    weights = field(mesh, [seed], 0.7)
    plan = plan_pinch(mesh, [seed], "radial", weights=weights)
    positions = check_frame(mesh, plan, 0.6, weights)
    seed_p = mesh.vertex_position(seed)
    for v in plan.movable - {seed}:
        p, q = mesh.vertex_position(v), positions[v]
        assert norm(q) == pytest.approx(1.0, abs=0.03)  # tangential pull: no dent, no flattening
        assert norm(tuple(a - b for a, b in zip(q, seed_p))) < norm(tuple(a - b for a, b in zip(p, seed_p)))


def test_pinch_never_overshoots_and_the_amount_is_clamped():
    mesh, ids = grid()
    seeds, weights, plans = _edge_seed_plans(mesh, ids)
    for plan in plans.values():
        assert plan.positions(5.0) == plan.positions(PINCH_MAX)
        assert plan.positions(-5.0) == plan.positions(PINCH_MIN)
    radial = plans["radial"]
    full = radial.positions(PINCH_MAX)
    for v in radial.movable:
        p, q = mesh.vertex_position(v), full[v]
        # Still on its own side of the centre (5.5, 5): no vertex jumps across it.
        assert (q[0] - 5.5) * (p[0] - 5.5) >= 0.0 and (q[1] - 5.0) * (p[1] - 5.0) >= 0.0


def test_pinch_refusals():
    mesh, ids = grid()
    seed = ids[(5, 5)]
    weights = field(mesh, [seed], 3.0)
    with pytest.raises(DeformRefused, match="no loop/ring direction"):
        plan_pinch(mesh, [seed], "loop", weights=weights)  # one vertex: no direction (the flow rule)
    with pytest.raises(DeformRefused, match="Soft Selection"):
        plan_pinch(mesh, [seed, ids[(5, 6)]], "ring")
    with pytest.raises(DeformRefused, match="nothing selected"):
        plan_pinch(mesh, [], "radial")
    with pytest.raises(ValueError):
        plan_pinch(mesh, [seed], "spiral")
    assert plan_pinch(mesh, [seed], "radial", weights=weights).movable  # Radial needs no direction


# -- irregular topology --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("tool", ["inflate", *PINCH_DIRECTIONS])
def test_irregular_topology_runs_finite_and_local(tool):
    mesh, ids = irregular()
    seeds = [ids[(5, c)] for c in range(3, 8)]  # a vertex path through quads, next to the triangles and the 6-gon
    weights = field(mesh, seeds, 3.0)
    plan = plan_inflate(mesh, seeds, weights=weights) if tool == "inflate" else plan_pinch(
        mesh, seeds, tool, weights=weights)
    for amount in (-0.7, 0.3, 0.9):
        positions = check_frame(mesh, plan, amount, weights)
        centre = tuple(sum(mesh.vertex_position(s)[i] for s in seeds) / len(seeds) for i in range(3))
        for v in plan.movable:
            p = mesh.vertex_position(v)
            reach = 1.0 if tool == "inflate" else max(
                norm(tuple(a - b for a, b in zip(p, q))) for q in [centre, *map(mesh.vertex_position, seeds)])
            assert norm(delta(mesh, positions, v)) <= abs(amount) * weights[v] * reach + 1e-12


def test_irregular_topology_pinch_loop_leaves_unlabelled_triangle_vertices_in_place():
    mesh, ids = irregular()
    seeds = [ids[(5, c)] for c in range(4, 8)]
    weights = field(mesh, seeds, 9.0)
    plan = plan_pinch(mesh, seeds, "loop", weights=weights)
    positions = check_frame(mesh, plan, 0.5, weights)
    inner_triangle = ids[(1, 1)]  # every face around it is a triangle: no family label reaches it
    assert inner_triangle in plan.movable and positions[inner_triangle] == mesh.vertex_position(inner_triangle)
    assert positions[ids[(7, 5)]] != mesh.vertex_position(ids[(7, 5)])


# -- symmetric meshes: head basemesh and the Gollum cage -----------------------------------------------------------


@pytest.mark.parametrize("tool", ["inflate", *PINCH_DIRECTIONS])
def test_head_symmetric_frames_stay_exact(tool):
    mesh = head()
    a = near(mesh, (0.25, 0.3, 0.6), seam=False)
    b = next(v for e in mesh.vertex_edges(a) for v in mesh.edge_vertices(e) if v != a)
    seeds = [a, b]  # an edge on the +x side
    weights = field(mesh, seeds, 0.6)
    plan = plan_inflate(mesh, seeds, weights=weights) if tool == "inflate" else plan_pinch(
        mesh, seeds, tool, weights=weights)
    assert plan.mirrors
    for amount in (-0.4, 0.05, 0.4):
        check_frame(mesh, plan, amount, weights)


def _gollum_regions(mesh):
    lip_start = near(mesh, (0.0, 0.159, 0.353), seam=True)
    lip_edge = next(e for e in mesh.vertex_edges(lip_start)
                    if mesh.vertex_position(next(v for v in mesh.edge_vertices(e) if v != lip_start))[0] > 0.01)
    lip = sorted({v for e in edge_loop(mesh, lip_edge).edges for v in mesh.edge_vertices(e)}, key=int)
    cheek = near(mesh, (0.25, 0.3, 0.25), seam=False)
    cheek_edge = [cheek, next(v for e in mesh.vertex_edges(cheek) for v in mesh.edge_vertices(e) if v != cheek)]
    return {
        "lips": (lip, 0.06),                                           # the lower lip loop, across the seam
        "cheek": (cheek_edge, 0.12),
        "nose": ([near(mesh, (0.0, 0.37, 0.394), seam=True)], 0.06),  # the tip, on the seam
        "eye": ([near(mesh, (0.12, 0.48, 0.28), seam=False)], 0.06),
    }


@pytest.mark.parametrize("region", ["lips", "cheek", "nose", "eye"])
@pytest.mark.parametrize("tool", ["inflate", *PINCH_DIRECTIONS])
def test_gollum_cage_regions_stay_symmetric_local_and_valid(region, tool):
    mesh = gollum()
    seeds, radius = _gollum_regions(mesh)[region]
    weights = field(mesh, seeds, radius)
    try:
        plan = plan_inflate(mesh, seeds, weights=weights) if tool == "inflate" else plan_pinch(
            mesh, seeds, tool, weights=weights)
    except DeformRefused as exc:
        # A single seed vertex has no loop / ring direction: refused, never a guess.
        assert len(seeds) == 1 and tool in ("loop", "ring") and "no loop/ring direction" in str(exc)
        return
    topology = {f: tuple(mesh.face_vertices(f)) for f in mesh.all_face_ids()}
    for amount in (-0.5, 0.01, 0.5):
        positions = check_frame(mesh, plan, amount * (radius if tool == "inflate" else 1.0), weights)
    change = mesh.begin_change()
    for v, p in plan.positions(0.5 if tool != "inflate" else 0.3 * radius).items():
        mesh.set_vertex_position(v, p)
    assert_mesh_invariants(mesh)
    assert {f: tuple(mesh.face_vertices(f)) for f in mesh.all_face_ids()} == topology
    states = {c.state for c in vertex_correspondence(mesh).values()}
    assert CorrespondenceState.AMBIGUOUS not in states and CorrespondenceState.UNPAIRED not in states
    mesh.rollback_change(change)
    assert positions  # the last checked frame


def test_gollum_lips_radial_loop_and_ring_are_meaningfully_different():
    mesh = gollum()
    lip, radius = _gollum_regions(mesh)["lips"]
    weights = field(mesh, lip, radius)
    frames = {d: plan_pinch(mesh, lip, d, weights=weights).positions(0.5) for d in PINCH_DIRECTIONS}
    off_line = [v for v in frames["loop"] if v not in set(lip) and weights.get(v, 0.0) > 0.3]
    assert off_line
    for a, b in (("radial", "loop"), ("radial", "ring"), ("loop", "ring")):
        gap = max(norm(tuple(p - q for p, q in zip(frames[a][v], frames[b][v]))) for v in off_line)
        assert gap > 0.005, (a, b, gap)
    # Loop pulls the neighbouring loops onto the lip line (closer to their nearest lip vertex); Ring keeps that
    # distance roughly and slides them along the lip instead.
    def gap_to_lip(positions, v):
        return min(norm(tuple(a - b for a, b in zip(positions[v], mesh.vertex_position(s)))) for s in lip)
    press = {v: mesh.vertex_position(v) for v in off_line}
    assert sum(gap_to_lip(frames["loop"], v) for v in off_line) < 0.8 * sum(gap_to_lip(press, v) for v in off_line)


def test_plans_are_cheap_per_motion():
    """The press does the work; a motion is one pass over the moving vertices (Gollum cage, a cheek field)."""
    import time
    mesh = gollum()
    seeds, _ = _gollum_regions(mesh)["cheek"]
    weights = field(mesh, seeds, 0.25)
    plan = plan_pinch(mesh, seeds, "loop", weights=weights)
    t0 = time.perf_counter()
    for i in range(50):
        plan.positions(i / 100.0)
    per_motion = (time.perf_counter() - t0) / 50
    assert per_motion < 0.02, per_motion  # generous: container CPU, ~len(movable) tuple ops
