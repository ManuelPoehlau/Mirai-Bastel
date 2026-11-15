"""Surface Slide core, Phase 1 (audit 2026-11-14 §13): `SurfaceSlide` - transport, pursuit, exactness, stops, flags.

The prototype's claims re-asserted on generated surfaces (sphere, cone, U, thin fin, sheets, tube) plus the new
behaviour of the port: direct transport with the antipodal fallback, the snap guard, the degenerate-gap chase,
barrier back-off, chain rows (seam, open boundary) and the flags.
"""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from tests.surface_slide_fixtures import (Surface, cube_sphere, cylinder, geodesic_ring, grid, nearest,
                                          point_triangle_distance, u_shape, u_vertex, u_wall)

from viewport.packed_geometry import np

from mirai.surface_slide import (FLAG_BARRIER, FLAG_BLOCKED, FLAG_BOUNDARY, FLAG_CAPTURE, FLAG_LAGGING,
                                 FLAG_MAXITER, FLAG_STUCK, EdgeChain, SlideReference, SurfaceSlide, direct_frames,
                                 frame_jumps, tree_frames)


def cone(segments: int = 16, rings: int = 6, height: float = 1.0) -> Surface:
    """A cone with its apex at (0, height, 0): all its curvature in one vertex (angle defect ~ 4.4 rad at height 1)."""
    V = [(0.0, height, 0.0)]
    for r in range(1, rings + 1):
        rad = r / rings
        V += [(rad * math.cos(2 * math.pi * s / segments), height * (1 - rad), rad * math.sin(2 * math.pi * s / segments))
              for s in range(segments)]
    ring = lambda r, s: 1 + (r - 1) * segments + s % segments  # noqa: E731
    faces = [(0, ring(1, s + 1), ring(1, s)) for s in range(segments)]
    faces += [(ring(r, s), ring(r, s + 1), ring(r + 1, s + 1), ring(r + 1, s)) for r in range(1, rings)
              for s in range(segments)]
    return Surface(np.array(V), faces)


def tangents(slide: SurfaceSlide, delta):
    """The weighted, transported tangent of every row for `delta` (what the speed limit is measured against)."""
    n_p = slide.pivot_frame[0]
    tp = np.asarray(delta, dtype=np.float64) - (np.asarray(delta) @ n_p) * n_p
    t = np.einsum("nij,j->ni", slide.frames, tp)
    n0 = slide.ref.VN[slide.rows]
    return (t - np.einsum("ij,ij->i", t, n0)[:, None] * n0) * slide.weights[:, None]


def run(slide: SurfaceSlide, path):
    """Drive `path` (absolute drags); check the per-update invariants; return the frames."""
    ref, h = slide.ref, slide.ref.h
    frames = []
    prev_pos, prev_t = slide.start_positions(), np.zeros((len(slide.rows), 3))
    for delta in path:
        f = slide.update(delta)
        t = tangents(slide, delta)
        tri, bary = slide.anchors()
        assert np.array_equal(f.positions, ref.point(tri, bary))                        # contract 2
        assert np.all(bary >= 0.0) and np.allclose(bary.sum(axis=1), 1.0)
        corners = ref.V[ref.T[tri]]
        assert point_triangle_distance(f.positions, *corners.transpose(1, 0, 2)).max() <= 1e-12 * h
        step = np.linalg.norm(f.positions - prev_pos, axis=1)
        assert np.all(step <= (1.0 + slide.gain) * np.linalg.norm(t - prev_t, axis=1) + 1e-9 * h)   # contract 3
        assert not f.positions.flags.writeable
        assert f.lagging == int(np.sum((f.flags & FLAG_LAGGING) > 0))
        prev_pos, prev_t = f.positions, t
        frames.append(f)
    return frames


def circle(e1, e2, radius: float, frames: int):
    a = np.linspace(0.0, 2.0 * np.pi, frames + 1)[1:]
    return radius * ((1.0 - np.cos(a))[:, None] * e1 + np.sin(a)[:, None] * e2)


def line(delta, frames: int):
    return [np.asarray(delta, dtype=np.float64) * (k / frames) for k in range(1, frames + 1)]


@pytest.fixture(scope="module")
def sphere():
    s = cube_sphere(12)
    return s, s.reference()


@pytest.fixture(scope="module")
def sphere_patch(sphere):
    s, ref = sphere
    rows, w = geodesic_ring(ref, nearest(s.V, (0.3, 0.2, 0.93)), 0.6)
    return ref, rows, w


# --- exactness ------------------------------------------------------------------------------------------------------

def test_zero_drag_restores_the_start_bit_for_bit(sphere_patch):
    ref, rows, w = sphere_patch
    slide = SurfaceSlide(ref, rows, w)
    n, e1, e2 = slide.pivot_frame
    run(slide, line(0.4 * e1 + 0.2 * e2 + 0.3 * n, 12))
    f = slide.update(np.zeros(3))
    assert np.array_equal(f.positions, ref.V[rows]) and f.lagging == 0 and not np.any(f.flags)
    tri, bary = slide.anchors()
    assert np.array_equal(ref.point(tri, bary), ref.V[rows])
    # a pure normal drag has no tangent either
    assert np.array_equal(slide.update(0.7 * n).positions, ref.V[rows])


def test_the_result_is_a_function_of_the_drag_alone_on_a_smooth_patch(sphere_patch):
    ref, rows, w = sphere_patch
    one = SurfaceSlide(ref, rows, w)
    n, e1, e2 = one.pivot_frame
    target = 0.35 * e1 - 0.15 * e2
    direct = one.update(target).positions
    two = SurfaceSlide(ref, rows, w)
    frames = run(two, [0.2 * e1, 0.4 * e1 + 0.1 * e2, -0.1 * e2, 0.3 * e1 - 0.3 * e2, target])
    assert frames[-1].lagging == 0
    assert np.array_equal(frames[-1].positions, direct)


def test_weight_zero_rows_never_move_and_weights_scale_the_travel():
    s = grid(10, 10, cell=0.1)
    ref = s.reference()
    rows = np.arange(ref.nv)
    w = np.where(np.arange(ref.nv) % 3 == 0, 0.0, np.where(np.arange(ref.nv) % 3 == 1, 1.0, 0.5))
    slide = SurfaceSlide(ref, rows, w, pivot=int(np.flatnonzero(w == 1.0)[0]))
    f = slide.update((0.03, 0.04, 0.0))
    still = w == 0.0
    assert np.array_equal(f.positions[still], ref.V[rows][still])
    travel = np.linalg.norm(f.positions - ref.V[rows], axis=1)
    inside = f.flags == 0                                          # not blocked or stopped at the sheet's rim
    assert np.allclose(travel[(w == 1.0) & inside], 0.05, atol=1e-12)
    assert np.allclose(travel[(w == 0.5) & inside], 0.025, atol=1e-12)


# --- transport ------------------------------------------------------------------------------------------------------

def test_direct_transport_is_continuous_where_the_tree_jumps():
    """Audit §3.2: the tree transport rotates by the enclosed curvature, so neighbours on different branches round
    the apex disagree; the direct rotation follows the normal."""
    c = cone(height=1.0)
    ref = c.reference()
    pivot = nearest(c.V, (0.5, 0.5, 0.0))
    rows, _ = geodesic_ring(ref, pivot, 1.0)
    tree = frame_jumps(ref, pivot, rows, tree_frames(ref, pivot, rows)).max()
    direct = frame_jumps(ref, pivot, rows, direct_frames(ref, pivot, rows)).max()
    assert tree > 90.0 and direct < 25.0


def test_direct_frames_rotate_the_pivot_normal_onto_each_normal(sphere_patch):
    ref, rows, _ = sphere_patch
    R = direct_frames(ref, int(rows[0]), rows)
    assert np.allclose(np.einsum("nij,j->ni", R, ref.VN[rows[0]]), ref.VN[rows], atol=1e-12)
    assert np.allclose(np.einsum("nij,nkj->nik", R, R), np.eye(3), atol=1e-12)


def test_antipodal_normals_are_transported_along_the_surface():
    """On a narrow U the far wall faces the pivot's wall: the direct rotation is undefined there (dot -1). The
    fallback composes it along the surface, so "down wall A" becomes "up wall B" - the way round the bend."""
    u = u_shape(gap=0.1, bend=4)
    ref = u.reference()
    pivot = u_vertex(u, 17, 10)                     # wall A, 3 cells above the bend
    rows, w = geodesic_ring(ref, pivot, 0.8)
    R = direct_frames(ref, pivot, rows)
    wall_b = ref.VN[rows] @ ref.VN[pivot] < -0.99
    assert np.sum(wall_b) > 10
    assert np.allclose(np.einsum("nij,j->ni", R, ref.VN[pivot]), ref.VN[rows], atol=1e-9)
    assert np.allclose(np.einsum("nij,nkj->nik", R, R), np.eye(3), atol=1e-9)
    down = np.einsum("nij,j->ni", R[wall_b], (0.0, 0.0, -1.0))
    assert np.allclose(down, (0.0, 0.0, 1.0), atol=1e-9)
    # the slide: wall-B rows move up their wall; no row jumps across the gap
    slide = SurfaceSlide(ref, rows, w, pivot=0)
    f = run(slide, line((0.0, 0.0, -0.15), 10))[-1]
    moved = f.positions[wall_b] - ref.V[rows][wall_b]
    assert np.all(moved[:, 2][w[wall_b] > 0.05] > 0.0)
    start = u_wall(u, ref, *ref.vertex_anchor(rows))
    end = u_wall(u, ref, *slide.anchors())
    assert np.all(end[start == 2] == 2) and np.all(end[start == 0] != 2)


# --- pursuit ----------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def apex():
    c = cone(height=1.0)
    ref = c.reference()
    rows, w = geodesic_ring(ref, nearest(c.V, (1 / 6, 5 / 6, 0.0)), 0.3)
    return ref, rows, w


def test_a_loop_round_the_apex_tears_is_speed_limited_and_closes(apex):
    ref, rows, w = apex
    slide = SurfaceSlide(ref, rows, w)
    n, e1, e2 = slide.pivot_frame
    frames = run(slide, circle(-e1, e2, 0.3, 48))
    assert max(f.lagging for f in frames) > 0                 # the absolute map tore; the pursuit limited it
    assert frames[-1].lagging == 0
    assert np.array_equal(frames[-1].positions, ref.V[rows])  # the loop ends at exactly zero: exact closure


def test_a_loop_ending_near_zero_keeps_its_lag_bounded(apex):
    """Audit §3.7 item 1: closure is exact only at exactly zero; one pixel off, the lag left is bounded by the
    pursuit rule - here every row has caught up and sits within its own tangent of its start."""
    ref, rows, w = apex
    slide = SurfaceSlide(ref, rows, w)
    n, e1, e2 = slide.pivot_frame
    path = circle(-e1, e2, 0.3, 48)
    path[-1] = 1e-4 * e1
    frames = run(slide, path)
    assert max(f.lagging for f in frames) > 0
    assert frames[-1].lagging == 0
    reach = np.linalg.norm(tangents(slide, path[-1]), axis=1)
    assert np.all(np.linalg.norm(frames[-1].positions - ref.V[rows], axis=1) <= reach + 1e-12)
    assert np.array_equal(slide.update(np.zeros(3)).positions, ref.V[rows])


def test_settle_closes_the_lag_onto_the_target(apex):
    ref, rows, w = apex
    slide = SurfaceSlide(ref, rows, w)
    n, e1, e2 = slide.pivot_frame
    for f in run(slide, circle(-e1, e2, 0.3, 48)):
        if f.lagging:
            break
    assert f.lagging > 0
    lag = slide.lagging_mask
    max_step = 0.25 * ref.h
    for _ in range(200):
        before = slide.anchors()
        s = slide.settle(max_step)
        moved = np.linalg.norm(s.positions - ref.point(*before), axis=1)
        assert np.all(moved[~lag] == 0.0) and np.all(moved <= max_step + 1e-12)
        if not s.lagging:
            break
    assert s.lagging == 0
    assert np.array_equal(s.positions, ref.point(*slide.targets()))
    assert np.array_equal(slide.settle(max_step).positions, s.positions)     # nothing lags: nothing moves


def _slab(thickness: float = 0.02, n: int = 8):
    s = cube_sphere(n, scale=(1.0, 1.0, thickness))
    return s, s.reference()


def test_no_vertex_skips_through_a_thin_fin():
    """Audit §3.7 item 2 (probe_thin): turning drags towards the rim of a 2 % thick fin; vertices may go round the
    rim to the back, never through the fin."""
    thick = 0.02
    s, ref = _slab(thick)
    front = np.flatnonzero(ref.V[:, 2] > 0.5 * thick)
    seed = int(front[np.argmin(np.hypot(ref.V[front, 0] - 0.6, ref.V[front, 1]))])
    rows, w = geodesic_ring(ref, seed, 4.0 * ref.h)
    slide = SurfaceSlide(ref, rows, w)
    frames_n = 240
    ang = np.linspace(0.0, 6.0 * np.pi, frames_n)
    rad = 2.0 * ref.h * np.minimum(1.0, np.linspace(0.0, 3.0, frames_n))
    path = np.stack([rad * np.cos(ang) + np.linspace(0.0, 1.2, frames_n), rad * np.sin(ang), np.zeros(frames_n)], 1)
    path += np.random.default_rng(0).normal(0.0, 0.05 * ref.h, path.shape) * (np.arange(frames_n) > 0)[:, None]
    prev = slide.start_positions()
    crossed = 0
    for f in run(slide, path):
        far = (np.abs(prev[:, 2]) > 0.6 * thick) & (np.abs(f.positions[:, 2]) > 0.6 * thick)
        assert not np.any(far & (np.sign(prev[:, 2]) != np.sign(f.positions[:, 2])))
        crossed = max(crossed, int(np.sum(f.positions[:, 2] < 0.0)))
        prev = f.positions
    assert crossed > 0                                     # some did go round the rim, along the surface


def _inject_target(slide: SurfaceSlide, tri, bary, direction=(0.0, 0.0, 0.0)) -> None:
    """Test hook: give row 0 a target as a torn absolute map would, then let `settle` chase it."""
    slide._tgt_tri[0], slide._tgt_bary[0] = tri, bary
    slide._tgt_dir[0] = direction
    slide._lagging[0] = True


def _front_and_back(ref, thick, x, y):
    tris = np.arange(ref.nt)
    c = ref.V[ref.T].mean(axis=1)
    front = tris[(ref.N[:, 2] > 0.99) & (np.hypot(c[:, 0] - x, c[:, 1] - y) < ref.h)]
    back = tris[(ref.N[:, 2] < -0.99) & (np.hypot(c[:, 0] - x, c[:, 1] - y) < ref.h)]
    return front, back


def test_snap_guard_does_not_adopt_a_target_behind_a_thin_sheet():
    thick = 0.02
    s, ref = _slab(thick)
    row = int(np.flatnonzero(ref.V[:, 2] > 0.5 * thick)[np.argmin(np.hypot(*ref.V[ref.V[:, 2] > 0.5 * thick, :2].T))])
    slide = SurfaceSlide(ref, [row])
    _, back = _front_and_back(ref, thick, ref.V[row, 0] + 0.5 * ref.h, ref.V[row, 1])
    target = (int(back[0]), np.array([1 / 3, 1 / 3, 1 / 3]))
    gap = np.linalg.norm(ref.point(np.array([target[0]]), target[1][None])[0] - ref.V[row])
    budget = 2.0 * gap
    _inject_target(slide, *target)
    f = slide.settle(budget)
    assert f.positions[0, 2] > 0.5 * thick                 # still on the front: the chord was not taken
    assert f.lagging == 1 and f.flags[0] & FLAG_LAGGING
    assert np.linalg.norm(f.positions[0] - ref.V[row]) <= gap + 1e-12


def test_a_gap_along_the_normal_chases_against_the_targets_arrival():
    thick = 0.02
    s, ref = _slab(thick)
    up = ref.V[:, 2] > 0.5 * thick
    row = int(np.flatnonzero(up)[np.argmin(np.hypot(*ref.V[up, :2].T))])         # the front centre
    slide = SurfaceSlide(ref, [row])
    _, back = _front_and_back(ref, thick, ref.V[row, 0], ref.V[row, 1])
    corner = int(np.flatnonzero(ref.T[back[0]] == nearest(ref.V, ref.V[row] * (1.0, 1.0, -1.0)))[0])
    bary = np.zeros(3)
    bary[corner] = 1.0                                     # exactly behind the row
    _inject_target(slide, int(back[0]), bary, direction=(-1.0, 0.0, 0.0))
    f = slide.settle(0.5 * ref.h)
    step = f.positions[0] - ref.V[row]
    gap = np.linalg.norm(ref.point(np.array([back[0]]), bary[None])[0] - ref.V[row])     # the chase walks <= the gap
    assert np.linalg.norm(step) == pytest.approx(gap, rel=1e-4)            # the slab's face is curved a little
    assert step[0] > 0.999 * np.linalg.norm(step) and f.positions[0, 2] > 0.5 * thick
    assert not f.flags[0] & FLAG_STUCK
    stuck = SurfaceSlide(ref, [row])
    _inject_target(stuck, int(back[0]), bary, direction=(0.0, 0.0, 0.0))
    g = stuck.settle(0.5 * ref.h)
    assert g.flags[0] & FLAG_STUCK and np.array_equal(g.positions[0], ref.V[row])


# --- walls, chains, flags ---------------------------------------------------------------------------------------------

def test_barrier_stop_backs_off_the_plane():
    s = grid(16, 8, cell=0.25, x0=-2.0)
    w = 17
    seam = [(j * w + 8, (j + 1) * w + 8) for j in range(8)]
    ref = s.reference(barrier_edges=seam)
    side = np.flatnonzero((ref.V[:, 0] > 0.0) & (ref.V[:, 1] > 0.4) & (ref.V[:, 1] < 1.6))
    slide = SurfaceSlide(ref, side, pivot=0)
    frames = run(slide, line((-3.0, 0.2, 0.0), 12))
    f = frames[-1]
    assert np.all(f.positions[:, 0] > 0.0)
    assert np.all(f.flags & FLAG_BARRIER)
    assert f.positions[:, 0].min() >= 0.02 * 0.25 - 1e-12        # 2 % of the triangle towards the far corner


def test_boundary_rows_slide_along_the_rim():
    """E5: rows on an open boundary walk the boundary chain; interior rows reaching the rim stop there flagged."""
    s = cylinder(24, 8, height=2.0)
    ref = s.reference()
    rim = ref.V[:, 1] == -1.0
    seed = nearest(s.V, (1.0, -1.0, 0.0))
    rows, w = geodesic_ring(ref, seed, 0.9)
    on_rim = rim[rows]
    chained = SurfaceSlide(ref, rows, w, chains=[EdgeChain.boundary(ref)])
    path = line((0.0, -0.6, 0.5), 10)
    f = run(chained, path)[-1]
    assert np.all(f.positions[on_rim, 1] == -1.0)
    moved = np.linalg.norm(f.positions[on_rim] - ref.V[rows][on_rim], axis=1)
    assert np.all(moved[w[on_rim] > 0.2] > 0.05)                 # the along-rim component is kept
    assert np.any(f.flags[~on_rim] & FLAG_BOUNDARY)
    plain = SurfaceSlide(ref, rows, w)                           # without the chain: the prototype rule
    g = run(plain, path)[-1]
    assert np.all(g.flags[on_rim] & FLAG_BLOCKED)
    assert np.array_equal(g.positions[on_rim], ref.V[rows][on_rim])


def test_seam_rows_stay_exactly_on_the_plane_while_the_drag_turns():
    s = cube_sphere(8)
    on = s.V[:, 0] == 0.0
    seam = [e for e in s.polygon_edges.tolist() if on[e[0]] and on[e[1]]]
    ref = s.reference(barrier_edges=seam)
    seed = nearest(s.V, (0.0, 0.3, 0.95))
    rows, w = geodesic_ring(ref, seed, 0.7)
    keep = ref.V[rows, 0] >= 0.0                                  # the driven half plus the seam
    rows, w = rows[keep], w[keep]
    slide = SurfaceSlide(ref, rows, w, chains=[EdgeChain(ref, seam)])
    n, e1, e2 = slide.pivot_frame
    seam_rows = on[rows]
    assert np.sum(seam_rows) > 3
    for f in run(slide, circle(e1, e2, 0.25, 36)[:30]):
        assert np.all(f.positions[seam_rows, 0] == 0.0)
        assert np.all(f.positions[~seam_rows, 0] > 0.0)
        assert not np.any(f.flags & (FLAG_STUCK | FLAG_MAXITER))


def test_a_capture_border_stop_is_flagged_not_backed_off():
    s = grid(8, 4, cell=0.25)
    w = 9
    border = [(j * w + 6, (j + 1) * w + 6) for j in range(4)]
    ref = s.reference(capture_edges=border)
    slide = SurfaceSlide(ref, [2 * w + 3])
    f = slide.update((2.0, 0.0, 0.0))
    assert f.flags[0] == FLAG_CAPTURE and f.positions[0, 0] == pytest.approx(1.5)


def test_tangent_of_is_the_drag_in_the_pivot_frame(sphere_patch):
    ref, rows, w = sphere_patch
    slide = SurfaceSlide(ref, rows, w)
    n, e1, e2 = slide.pivot_frame
    assert slide.tangent_of(0.3 * e1 - 0.2 * e2 + 5.0 * n) == pytest.approx((0.3, -0.2))
    a, b = np.array([0.1, -0.4, 0.2]), np.array([-0.3, 0.05, 0.7])
    assert np.allclose(np.add(slide.tangent_of(a), slide.tangent_of(b)), slide.tangent_of(a + b))


def test_the_constructor_refuses_bad_input(sphere_patch):
    ref, rows, w = sphere_patch
    with pytest.raises(ValueError):
        SurfaceSlide(ref, [rows[0], rows[0]])
    with pytest.raises(ValueError):
        SurfaceSlide(ref, rows, w, pivot=len(rows))
    with pytest.raises(ValueError):
        SurfaceSlide(ref, rows, np.full(len(rows), 1.5))
    with pytest.raises(ValueError):
        SurfaceSlide(ref, rows, w, frames=np.zeros((len(rows), 3)))
    with pytest.raises(ValueError):
        SurfaceSlide(ref, [])
    other = SlideReference(ref.V, ref.T)
    with pytest.raises(ValueError):
        SurfaceSlide(ref, rows, w, chains=[EdgeChain(other, [(int(ref.T[0, 0]), int(ref.T[0, 1]))])])
