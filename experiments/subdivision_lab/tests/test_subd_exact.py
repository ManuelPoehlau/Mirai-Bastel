"""A1–A3: exact values of the Catmull-Clark rules on tiny meshes."""

from __future__ import annotations

import itertools

import pytest

from subdivision_lab.subd import KIND_EDGE, KIND_FACE, KIND_VERTEX, SubdSurface

from .meshes import (
    CUBE_POSITIONS,
    cube_mesh,
    edge_pairs,
    pentagon_mesh,
    plane_2x2_mesh,
    single_quad_mesh,
    triangle_mesh,
)

TOL = 1e-12


def close(p, q, tol=TOL):
    return all(abs(a - b) <= tol for a, b in zip(p, q))


def level1(mesh):
    surface = SubdSurface(mesh)
    level = surface.level(1)
    return surface, level, level.apply_full(surface.initial_positions)


# -- A1 --------------------------------------------------------------------------------


def test_a1_cube_level_1_counts_and_euler():
    surface, level, positions = level1(cube_mesh())
    assert level.n_verts == 26 and len(positions) == 26
    assert len(level.faces) == 24 and all(len(f) == 4 for f in level.faces)
    edges = edge_pairs(level.faces)
    assert level.n_verts - len(edges) + len(level.faces) == 2


def test_a1_cube_corner_points_are_5_9():
    _surface, _level, positions = level1(cube_mesh())
    for i, corner in enumerate(CUBE_POSITIONS):
        expected = tuple(5.0 / 9.0 * c for c in corner)  # sign permutations of (5/9, 5/9, 5/9)
        assert close(positions[i], expected), (i, positions[i])


def test_a1_cube_edge_points():
    surface, level, positions = level1(cube_mesh())
    n_v = len(surface.topology.vertex_ids)
    seen_example = False
    for e, (a, b) in enumerate(surface.topology.edges):
        pa, pb = CUBE_POSITIONS[a], CUBE_POSITIONS[b]
        midpoint = tuple((x + y) / 2 for x, y in zip(pa, pb))
        # cube: the mean of 2 endpoints + 2 adjacent face centres is 3/4 of the edge midpoint
        assert close(positions[n_v + e], tuple(0.75 * m for m in midpoint)), e
        if pa[:2] == (1.0, 1.0) and pb[:2] == (1.0, 1.0):
            assert close(positions[n_v + e], (0.75, 0.75, 0.0))
            seen_example = True
    assert seen_example


def test_a1_cube_face_points_are_face_centres():
    surface, level, positions = level1(cube_mesh())
    base = len(surface.topology.vertex_ids) + len(surface.topology.edges)
    for f, face in enumerate(surface.topology.faces):
        centre = tuple(sum(CUBE_POSITIONS[v][i] for v in face) / 4 for i in range(3))
        assert close(positions[base + f], centre)
        assert level.vert_kind[base + f] == KIND_FACE


def test_a1_cube_all_corner_permutations_covered():
    _surface, _level, positions = level1(cube_mesh())
    signs = {tuple(1 if c > 0 else -1 for c in p) for p in positions[:8]}
    assert signs == set(itertools.product((-1, 1), repeat=3))


# -- A2 --------------------------------------------------------------------------------


def test_a2_single_quad_boundary_rules():
    surface, level, positions = level1(single_quad_mesh())
    assert level.n_verts == 9 and len(level.faces) == 4
    expected_corners = [(1 / 8, 1 / 8, 0), (7 / 8, 1 / 8, 0), (7 / 8, 7 / 8, 0), (1 / 8, 7 / 8, 0)]
    for i, expected in enumerate(expected_corners):
        assert close(positions[i], expected), i
    # boundary edge points = midpoints
    edge_midpoints = [(0.5, 0.0, 0.0), (1.0, 0.5, 0.0), (0.5, 1.0, 0.0), (0.0, 0.5, 0.0)]
    got = sorted(positions[4:8])
    assert all(close(p, q) for p, q in zip(got, sorted(edge_midpoints)))
    assert close(positions[8], (0.5, 0.5, 0.0))


def test_a2_plane_2x2_stays_flat_and_centre_fixed():
    surface, level, positions = level1(plane_2x2_mesh())
    assert all(abs(p[2]) <= TOL for p in positions)
    assert close(positions[4], (1.0, 1.0, 0.0))  # interior vertex, regular valence 4, flat patch
    deeper = SubdSurface(plane_2x2_mesh()).level(3)
    assert all(abs(p[2]) <= TOL for p in deeper.apply_full(surface.initial_positions))


# -- A3 --------------------------------------------------------------------------------


@pytest.mark.parametrize("builder,n", [(triangle_mesh, 3), (pentagon_mesh, 5)])
def test_a3_ngon_produces_n_quads_and_valence_n_face_point(builder, n):
    surface, level, positions = level1(builder())
    assert len(level.faces) == n and all(len(f) == 4 for f in level.faces)
    assert level.n_verts == n + n + 1
    face_point = level.n_verts - 1
    assert level.vert_kind[face_point] == KIND_FACE
    assert sum(face_point in f for f in level.faces) == n  # the face point has valence n
    assert level.face_parent == [0] * n
    # face point = centroid of the n-gon
    initial = surface.initial_positions
    centroid = tuple(sum(p[i] for p in initial) / n for i in range(3))
    assert close(positions[face_point], centroid)


def test_a3_provenance_kinds_of_a_triangle():
    _surface, level, _positions = level1(triangle_mesh())
    assert level.vert_kind == [KIND_VERTEX] * 3 + [KIND_EDGE] * 3 + [KIND_FACE]
