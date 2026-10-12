"""§7.1 Box: V/E/F counts, all quads, closed, outward normals, mesh invariants, clamps."""

from __future__ import annotations

import pytest

from mehlsack_lab.box import (
    SEGMENTS_MAX,
    SIZE_MAX,
    SIZE_MIN,
    BoxParams,
    box_positions_and_faces,
    build_box_mesh,
)
from tests.mesh_invariants import assert_mesh_invariants

CASES = [(1, 1), (1, 3), (2, 1), (3, 2), (5, 4), (8, 8)]


def _newell(points):
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return n


@pytest.mark.parametrize("h,n", CASES)
def test_counts_match_formula_and_mesh(h, n):
    params = BoxParams(height=2.0, width=1.5, h=h, n=n)
    mesh = build_box_mesh(params)
    v, e, f = params.counts()
    assert v == 4 * n * (h + 1) + 2 * (n - 1) ** 2
    assert f == 4 * n * h + 2 * n * n
    assert (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())) == (v, e, f)
    assert v - e + f == 2  # closed, genus 0


def test_unit_box_is_a_cube():
    assert BoxParams().counts() == (8, 12, 6)


@pytest.mark.parametrize("h,n", CASES)
def test_all_quads_closed_and_invariants(h, n):
    mesh = build_box_mesh(BoxParams(h=h, n=n))
    assert_mesh_invariants(mesh, context=f"box h={h} n={n}")
    assert all(len(mesh.face_vertices(f)) == 4 for f in mesh.all_face_ids())
    assert all(len(mesh.edge_faces(e)) == 2 for e in mesh.all_edge_ids())  # closed: no boundary


@pytest.mark.parametrize("h,n", CASES)
def test_normals_point_outward(h, n):
    """Box centred on the origin: the Newell normal of every face points away from it,
    and (b - a) × (c - a) agrees (the `create_cube` convention)."""
    mesh = build_box_mesh(BoxParams(height=3.0, width=1.25, h=h, n=n))
    for fid in mesh.all_face_ids():
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
        centre = [sum(p[i] for p in pts) / 4 for i in range(3)]
        newell = _newell(pts)
        assert sum(a * b for a, b in zip(newell, centre)) > 0.0
        a, b, c = pts[0], pts[1], pts[2]
        u = [b[i] - a[i] for i in range(3)]
        w = [c[i] - a[i] for i in range(3)]
        cross = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        assert sum(x * y for x, y in zip(cross, centre)) > 0.0


def test_dimensions_and_centring():
    positions, _ = box_positions_and_faces(BoxParams(height=3.0, width=1.5, h=3, n=2))
    for axis, half in ((0, 0.75), (1, 1.5), (2, 0.75)):
        values = [p[axis] for p in positions]
        assert min(values) == -half and max(values) == half


def test_clamps_and_steps():
    p = BoxParams()
    assert p.with_h_steps(-5).h == 1 and p.with_n_steps(-1).n == 1
    assert p.with_h_steps(100).h == SEGMENTS_MAX and p.with_n_steps(100).n == SEGMENTS_MAX
    assert p.with_height_steps(-100).height == SIZE_MIN
    assert p.with_width_steps(100).width == SIZE_MAX
    # 20 steps up and down land exactly on the start value (no drift).
    q = p
    for _ in range(20):
        q = q.with_height_steps(1)
    for _ in range(20):
        q = q.with_height_steps(-1)
    assert q.height == p.height
    assert BoxParams(h=5).loops == 4
    with pytest.raises(ValueError):
        BoxParams(h=0)
    with pytest.raises(ValueError):
        BoxParams(width=0.0)
