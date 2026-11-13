"""The reference surface: adjacency, closest point (grid against brute force), immutability."""

from __future__ import annotations

import numpy as np
import pytest

from surface_slide import geometries as G
from surface_slide import harness as H
from surface_slide.refsurf import closest_on_triangles, triangulate


@pytest.fixture(scope="module")
def sphere():
    geo = G.cube_sphere(8)
    return geo, H.build_ref(geo.V, geo.faces)


def test_adjacency_is_symmetric_and_closed(sphere):
    _, ref = sphere
    assert ref.n_boundary_edges == 0 and ref.n_nonmanifold_edges == 0 and ref.n_flipped_edges == 0
    t = np.repeat(np.arange(ref.nt), 3)
    k = np.tile(np.arange(3), ref.nt)
    back = ref.nbr[ref.nbr[t, k], ref.nbr_k[t, k]]
    assert np.array_equal(back, t)
    # the shared edge has the same two vertices on both sides
    a, b = ref.T[t, (k + 1) % 3], ref.T[t, (k + 2) % 3]
    nt, nk = ref.nbr[t, k], ref.nbr_k[t, k]
    assert np.array_equal(ref.T[nt, (nk + 1) % 3], b) and np.array_equal(ref.T[nt, (nk + 2) % 3], a)


def test_boundary_is_found_on_an_open_mesh():
    geo = G.u_shape(0.3, 1.0, 1.0, 0.1, 4)
    ref = H.build_ref(geo.V, geo.faces)
    assert ref.n_boundary_edges > 0
    rim = np.flatnonzero(ref.v_boundary)
    assert len(rim) == ref.n_boundary_edges      # one closed boundary loop


def test_quad_triangulation_covers_every_face_once():
    geo = G.cube_sphere(4)
    T, tri_face = triangulate(geo.V, geo.faces)
    assert len(T) == 2 * len(geo.faces)
    assert np.array_equal(np.bincount(tri_face), np.full(len(geo.faces), 2))


def test_ngon_ear_clipping_keeps_area():
    # a concave L-shaped hexagon in the plane z = 0
    V = np.array([[0, 0, 0], [2, 0, 0], [2, 1, 0], [1, 1, 0], [1, 2, 0], [0, 2, 0]], dtype=float)
    T, _ = triangulate(V, [(0, 1, 2, 3, 4, 5)])
    area = 0.5 * np.linalg.norm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]), axis=1)
    assert len(T) == 4 and area.sum() == pytest.approx(3.0)
    normals = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    assert np.all(normals[:, 2] > 0)             # winding kept


def test_grid_closest_point_equals_brute_force(sphere):
    _, ref = sphere
    rng = np.random.default_rng(0)
    P = rng.normal(size=(300, 3)) * rng.uniform(0.2, 2.5, size=(300, 1))
    tri, bary, d = ref.closest_point(P)
    A, B, C = ref.V[ref.T[:, 0]], ref.V[ref.T[:, 1]], ref.V[ref.T[:, 2]]
    for i in range(len(P)):
        _, d2 = closest_on_triangles(np.broadcast_to(P[i], A.shape), A, B, C)
        assert d[i] == pytest.approx(np.sqrt(d2.min()), abs=1e-12)
    assert np.allclose(np.linalg.norm(ref.point(tri, bary) - P, axis=1), d, atol=1e-12)


def test_reference_arrays_are_read_only(sphere):
    _, ref = sphere
    for name in ("V", "T", "N", "nbr", "VN", "G"):
        with pytest.raises(ValueError):
            getattr(ref, name)[0] = 0


def test_phong_evaluation_interpolates_the_vertices(sphere):
    _, ref = sphere
    v = np.arange(ref.nv)
    tri, bary = ref.vertex_anchor(v)
    assert np.array_equal(ref.point(tri, bary), ref.V)
    assert np.array_equal(ref.point_phong(tri, bary, 0.5), ref.V)
