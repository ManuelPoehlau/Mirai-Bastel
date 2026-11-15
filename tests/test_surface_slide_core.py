"""Surface Slide core, Phase 1 (audit 2026-11-14 §13): the reference, the tracer, the chain walker.

The slide itself: `test_surface_slide_slide.py`. The comparison with the prototype (gate G1):
`experiments/surface_slide/tests/test_production_oracle.py`.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from tests.surface_slide_fixtures import cube_sphere, cylinder, grid, u_shape, u_unrolled, u_vertex

from viewport.packed_geometry import np

from mirai.surface_slide import (BARRIER_EDGE, BARRIER_MAX_AMOUNT, BOUNDARY_EDGE, CAPTURE_EDGE, FLAG_BARRIER,
                                 FLAG_BLOCKED, FLAG_BOUNDARY, FLAG_CAPTURE, FLAG_CHAIN_END, EdgeChain, SlideReference,
                                 back_off, trace)
from mirai.surface_slide.tracer import launch_from_vertices


def _trace_from_vertices(ref, rows, tangents):
    rows = np.asarray(rows, dtype=np.intp)
    t = np.asarray(tangents, dtype=np.float64).reshape(len(rows), 3)
    length = np.linalg.norm(t, axis=1)
    tri, bary, d, flags = launch_from_vertices(ref, rows, t / length[:, None])
    length = np.where(flags & FLAG_BLOCKED, 0.0, length)
    tr = trace(ref, tri, bary, d, length)
    return tr, flags | tr.flags


# --- reference ------------------------------------------------------------------------------------------------------

def test_reference_adjacency_is_closed_and_consistent():
    ref = cube_sphere(6).reference()
    assert ref.n_boundary_edges == 0 and ref.n_nonmanifold_edges == 0 and ref.n_flipped_edges == 0
    t = np.repeat(np.arange(ref.nt), 3)
    k = np.tile(np.arange(3), ref.nt)
    assert np.array_equal(ref.nbr[ref.nbr[t, k], ref.nbr_k[t, k]], t)
    a, b = ref.T[t, (k + 1) % 3], ref.T[t, (k + 2) % 3]
    nt, nk = ref.nbr[t, k], ref.nbr_k[t, k]
    assert np.array_equal(ref.T[nt, (nk + 1) % 3], b) and np.array_equal(ref.T[nt, (nk + 2) % 3], a)
    assert np.allclose(np.linalg.norm(ref.VN, axis=1), 1.0)
    assert np.all(np.einsum("ij,ij->i", ref.VN, ref.V) > 0.99)          # outward on the unit sphere


def test_reference_arrays_are_read_only_and_copies():
    s = grid(3, 3)
    V = s.V.copy()
    ref = SlideReference(V, s.T)
    V[0] = 99.0
    assert ref.V[0, 0] == 0.0
    for name in ("V", "T", "N", "E", "Pin", "G", "Gn", "nbr", "nbr_k", "nbr_flip", "vt_ptr", "vt_tri", "vt_corner",
                 "valence", "VN", "v_boundary", "v_wall", "v_capture", "degenerate"):
        arr = getattr(ref, name)
        assert not arr.flags.writeable, name
        with pytest.raises(ValueError):
            arr.flat[0] = arr.flat[0]


def test_vertex_anchor_is_exactly_the_vertex():
    ref = cube_sphere(5).reference()
    rows = np.arange(ref.nv)
    tri, bary = ref.vertex_anchor(rows)
    assert np.array_equal(ref.point(tri, bary), ref.V)
    assert np.all(np.sort(bary, axis=1) == [0.0, 0.0, 1.0])


def test_edge_codes_boundary_barrier_capture():
    s = grid(4, 4)
    w = 5
    line = [(j * w + 2, (j + 1) * w + 2) for j in range(4)]           # the column x = 2, interior edges
    border = [(j * w + 4, (j + 1) * w + 4) for j in range(4)]         # the column x = 4: the sheet's boundary
    ref = s.reference(barrier_edges=line, capture_edges=border)
    assert set(map(tuple, ref.edges_with_code(BARRIER_EDGE).tolist())) == set(line)
    assert set(map(tuple, ref.edges_with_code(CAPTURE_EDGE).tolist())) == set(border)
    assert len(ref.edges_with_code(BOUNDARY_EDGE)) == 16 - 4
    assert ref.v_wall[2] and ref.v_capture[4] and not ref.v_capture[2]
    both = s.reference(barrier_edges=line, capture_edges=line)       # a barrier wins over a capture border
    assert len(both.edges_with_code(CAPTURE_EDGE)) == 0


def test_reference_refuses_edges_it_does_not_have():
    s = grid(2, 2)
    with pytest.raises(ValueError):
        s.reference(barrier_edges=[(1, 3)])        # the diagonal the fan did not draw
    with pytest.raises(ValueError):
        s.reference(capture_edges=[(0, 99)])
    with pytest.raises(ValueError):
        SlideReference(s.V, [(0, 1, 99)])


def test_reference_size_is_bounded_per_vertex():
    ref = cube_sphere(16).reference()
    assert ref.nbytes() / ref.nv < 1024               # P8: <= 1 KB per captured vertex


# --- tracer -------------------------------------------------------------------------------------------------------------

def test_geodesics_on_the_u_match_the_unrolled_strip_exactly():
    """On the polyhedral U a geodesic is a straight line in the unrolled (s, y) chart: an exact ground truth, also
    around the bend and up the other wall."""
    u = u_shape(gap=0.3, bend=8)
    ref = u.reference()
    rows = np.array([u_vertex(u, 17, r) for r in range(6, 15, 2)] + [u_vertex(u, 10, r) for r in range(6, 15, 2)])
    s0 = u.meta["s_nodes"][rows % u.meta["m"]]
    y0 = u.V[rows, 1]
    for down, along_y in ((1.0, 0.0), (0.6, 0.3), (0.25, -0.4), (2.1, 0.2)):
        tangent = np.tile([0.0, along_y, -down], (len(rows), 1))     # down wall A (x = -r) and along y
        tr, flags = _trace_from_vertices(ref, rows, tangent)
        want = u_unrolled(u, s0 + down, y0 + along_y)
        assert np.abs(ref.point(tr.tri, tr.bary) - want).max() < 1e-12
        assert not np.any(flags)


def test_boundary_stop_names_the_edge():
    s = grid(6, 6)
    ref = s.reference()
    row = 3 * 7 + 3
    tr, flags = _trace_from_vertices(ref, [row], [(10.0, 0.0, 0.0)])
    assert flags[0] == FLAG_BOUNDARY
    p = ref.point(tr.tri, tr.bary)[0]
    assert p[0] == 6.0 and abs(p[1] - 3.0) < 1e-12
    assert tr.edge[0] >= 0 and ref.nbr[tr.tri[0], tr.edge[0]] == BOUNDARY_EDGE
    assert tr.remaining[0] == pytest.approx(7.0)


def test_barrier_and_capture_stops_and_back_off():
    s = grid(8, 4, x0=-4.0)                       # x from -4 to 4, the barrier column at x = 0
    w = 9
    seam = [(j * w + 4, (j + 1) * w + 4) for j in range(4)]
    rim = [(j * w + 7, (j + 1) * w + 7) for j in range(4)]     # x = 3: a capture border inside the sheet
    ref = s.reference(barrier_edges=seam, capture_edges=rim)
    rows = [2 * w + 6, 2 * w + 6]
    tr, flags = _trace_from_vertices(ref, rows, [(-4.0, 0.3, 0.0), (5.0, 0.2, 0.0)])
    assert flags[0] == FLAG_BARRIER and flags[1] == FLAG_CAPTURE
    hit = ref.point(tr.tri, tr.bary)
    assert hit[0, 0] == 0.0 and hit[1, 0] == pytest.approx(3.0, abs=1e-12)
    backed = back_off(tr.bary[:1], tr.edge[:1])
    p = ref.point(tr.tri[:1], backed)[0]
    assert p[0] > 0.0                                                    # strictly off the plane, on the start side
    assert np.all(backed >= 0.0) and backed.sum() == pytest.approx(1.0)
    corner = ref.V[ref.T[tr.tri[0], tr.edge[0]]]
    assert np.allclose(p, corner + BARRIER_MAX_AMOUNT * (hit[0] - corner))


def test_a_wall_start_pointing_off_the_surface_is_blocked():
    s = grid(4, 4)
    ref = s.reference()
    tr, flags = _trace_from_vertices(ref, [2, 2], [(0.0, -1.0, 0.0), (0.3, 1.0, 0.0)])   # bottom edge vertex
    assert flags[0] == FLAG_BLOCKED and flags[1] == 0
    assert np.array_equal(ref.point(tr.tri[:1], tr.bary[:1])[0], ref.V[2])
    cap = s.reference(capture_edges=[(i, i + 1) for i in range(4)])
    _, flags = _trace_from_vertices(cap, [2], [(0.0, -1.0, 0.0)])
    assert flags[0] == FLAG_BLOCKED | FLAG_CAPTURE                      # Phase 2 grows the capture here


def test_inconsistent_winding_traces_the_same_path():
    s = grid(6, 6)
    T = s.T.copy()
    ref = SlideReference(s.V, T)
    flipped_T = T.copy()
    flipped_T[10:30:3] = flipped_T[10:30:3][:, [0, 2, 1]]
    flipped = SlideReference(s.V, flipped_T)
    assert flipped.n_flipped_edges > 0
    rows = [8, 9, 15]
    tangents = [(4.0, 3.0, 0.0), (1.0, 4.5, 0.0), (3.0, -0.5, 0.0)]
    a, _ = _trace_from_vertices(ref, rows, tangents)
    b, _ = _trace_from_vertices(flipped, rows, tangents)
    assert np.abs(ref.point(a.tri, a.bary) - flipped.point(b.tri, b.bary)).max() < 1e-12


# --- chain walker -----------------------------------------------------------------------------------------------------

def test_seam_chain_keeps_the_plane_coordinate_exactly():
    s = cube_sphere(8)
    ref = s.reference()
    on = s.V[:, 0] == 0.0
    seam = [e for e in s.polygon_edges.tolist() if on[e[0]] and on[e[1]]]
    chain = EdgeChain(ref, seam)
    assert np.array_equal(chain.on_chain, on)
    for v in np.flatnonzero(on).tolist():
        for t in ((0.3, 0.7, -0.2), (-0.5, -0.1, 0.9), (0.0, 2.5, 0.0), (0.4, 0.0, 0.0)):
            arm, length = chain.arm(v, np.array(t))
            tri, bary, travelled, flags = chain.walk(v, arm, length)
            p = ref.point(np.array([tri]), bary[None])[0]
            assert p[0] == 0.0
            assert travelled == pytest.approx(length) or flags & FLAG_CHAIN_END
            assert np.sort(bary)[0] == 0.0                              # on a reference edge


def test_boundary_loop_chain_walks_the_rim_and_stops_at_its_start():
    s = cylinder(24, 6)
    ref = s.reference()
    chain = EdgeChain.boundary(ref)
    assert chain.n_edges == 48 and np.array_equal(chain.on_chain, ref.v_boundary)
    v = 0                                                                # bottom rim, angle 0
    arm, length = chain.arm(v, np.array([0.0, 0.0, 0.5]))             # along the rim (+z at angle 0)
    e = s.V[1] - s.V[0]
    assert arm == 1 and length == pytest.approx(0.5 * e[2] / np.linalg.norm(e))
    tri, bary, travelled, flags = chain.walk(v, arm, 1.3)
    p = ref.point(np.array([tri]), bary[None])[0]
    assert p[1] == s.V[0, 1] and flags == 0 and travelled == pytest.approx(1.3)
    assert np.hypot(p[0], p[2]) <= 1.0                                   # on a chord of the rim polygon
    rim = 24 * np.linalg.norm(s.V[1] - s.V[0])
    tri, bary, travelled, flags = chain.walk(v, arm, rim + 0.5)        # once round: stops where it started
    assert flags == FLAG_CHAIN_END and travelled == pytest.approx(rim)
    assert np.array_equal(ref.point(np.array([tri]), bary[None])[0], s.V[0])


def test_open_chain_ends_and_refuses_foreign_edges():
    s = grid(4, 1)
    ref = s.reference()
    chain = EdgeChain(ref, [(0, 1), (1, 2), (2, 3)])
    tri, bary, travelled, flags = chain.walk(1, 2, 5.0)
    assert flags == FLAG_CHAIN_END and travelled == 2.0
    assert np.array_equal(ref.point(np.array([tri]), bary[None])[0], s.V[3])
    assert chain.arm(1, np.array([0.0, 1.0, 0.0])) == (-1, 0.0)        # perpendicular: no arm
    with pytest.raises(ValueError):
        EdgeChain(ref, [(1, 5)])                                         # the diagonal not drawn
