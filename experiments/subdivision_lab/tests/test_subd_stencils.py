"""A4 (stencils = direct recursive Catmull-Clark), A5 non-GL part (local = full),
A7 (provenance) on the cube asset and the head asset."""

from __future__ import annotations

import random

import pytest
from loaders.assets import asset_path
from mirai.scene_factory import build_core_scene_from_obj

from subdivision_lab.subd import KIND_EDGE, KIND_FACE, KIND_VERTEX, SubdSurface

from .meshes import face_centroids, reference_levels, sorted_close


def asset_surface(name):
    mesh = build_core_scene_from_obj(str(asset_path(name))).mesh
    return SubdSurface(mesh)


@pytest.fixture(scope="module")
def cube_surface():
    return asset_surface("subd_cube")


@pytest.fixture(scope="module")
def head_surface():
    return asset_surface("head_basemesh")


def perturbed(positions, seed, amount=0.05):
    rng = random.Random(seed)
    return [tuple(c + rng.uniform(-amount, amount) for c in p) for p in positions]


# -- A4 ----------------------------------------------------------------------------------


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_a4_stencil_equals_direct_recursive_catmull_clark(asset, level, cube_surface, head_surface):
    surface = cube_surface if asset == "subd_cube" else head_surface
    control = perturbed(surface.initial_positions, seed=1234 + level)
    derived_level = surface.level(level)
    got = derived_level.apply_full(control)

    ref_positions, ref_faces = reference_levels(control, [list(f) for f in surface.topology.faces], level)
    assert len(got) == len(ref_positions) and len(derived_level.faces) == len(ref_faces)
    assert sorted_close(got, ref_positions, 1e-9)
    # same structure, not just the same point cloud: face centroids agree as a multiset
    assert sorted_close(face_centroids(got, derived_level.faces), face_centroids(ref_positions, ref_faces), 1e-9)


@pytest.mark.parametrize("level", [1, 2, 3])
def test_a4_stencil_weights_sum_to_one(level, head_surface):
    for ix, ws in head_surface.level(level).stencils:
        assert abs(sum(ws) - 1.0) <= 1e-12
        assert len(ix) == len(ws) and list(ix) == sorted(ix)


def test_a4_expected_sizes_head(head_surface):
    # handoff §5 sanity numbers (sandbox)
    expected = {1: (1298, 1296, 8102), 2: (5186, 5184, 54998), 3: (20738, 20736, 274166)}
    for level, (n_verts, n_faces, entries) in expected.items():
        lv = head_surface.level(level)
        assert (lv.n_verts, len(lv.faces), lv.stencil_entries) == (n_verts, n_faces, entries)
        assert head_surface.predicted_face_count(level) == n_faces


# -- A5 (non-GL) --------------------------------------------------------------------------


@pytest.mark.parametrize("level", [1, 2])
@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_a5_local_update_equals_full_and_touches_exactly_the_inverse_set(asset, level, cube_surface, head_surface):
    surface = cube_surface if asset == "subd_cube" else head_surface
    lv = surface.level(level)
    rng = random.Random(99 + level)
    control = perturbed(surface.initial_positions, seed=7)
    derived = lv.apply_full(control)
    n_controls = len(control)
    for _ in range(50):
        v = rng.randrange(n_controls)
        before = list(derived)
        p = control[v]
        control[v] = (p[0] + rng.uniform(-0.1, 0.1), p[1] + rng.uniform(-0.1, 0.1), p[2] + rng.uniform(-0.1, 0.1))
        recomputed = lv.apply_local(v, control, derived)
        full = lv.apply_full(control)
        assert all(abs(a - b) <= 1e-12 for da, fa in zip(derived, full) for a, b in zip(da, fa))
        changed = {d for d in range(len(derived)) if derived[d] != before[d]}
        assert changed == set(lv.inverse[v]) == set(recomputed)


def test_a5_inverse_index_is_consistent_with_stencils(head_surface):
    lv = head_surface.level(2)
    pairs = {(c, d) for d, (ix, _ws) in enumerate(lv.stencils) for c in ix}
    inverse_pairs = {(c, d) for c, ds in enumerate(lv.inverse) for d in ds}
    assert pairs == inverse_pairs


# -- A7 ----------------------------------------------------------------------------------------


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_a7_provenance(asset, level, cube_surface, head_surface):
    surface = cube_surface if asset == "subd_cube" else head_surface
    topology = surface.topology
    lv = surface.level(level)
    n_v, n_e, n_f = len(topology.vertex_ids), len(topology.edges), len(topology.faces)

    # every derived face maps to exactly one control face; a control n-gon owns n * 4^(L-1) of them
    assert len(lv.face_parent) == len(lv.faces)
    per_face = [0] * n_f
    for parent in lv.face_parent:
        per_face[parent] += 1
    for f, face in enumerate(topology.faces):
        assert per_face[f] == len(face) * 4 ** (level - 1)

    # each control edge has exactly 2^L isoline segments (two at level 1)
    iso_per_edge = [0] * n_e
    for control_edge in lv.iso_control_edge:
        iso_per_edge[control_edge] += 1
    assert iso_per_edge == [2 ** level] * n_e
    assert len(lv.iso_edges) == len(lv.iso_control_edge)

    kinds = [lv.vert_kind.count(k) for k in (KIND_VERTEX, KIND_EDGE, KIND_FACE)]
    assert kinds[0] == n_v
    assert kinds[1] == n_e * (2 ** level - 1)
    assert sum(kinds) == lv.n_verts
    if level == 1:
        assert kinds == [n_v, n_e, n_f]
        # level 1: the isoline pairs are exactly (vertex point of an endpoint) <-> (edge point of that edge)
        for (a, b), control_edge in zip(lv.iso_edges, lv.iso_control_edge):
            kind_a, kind_b = lv.vert_kind[a], lv.vert_kind[b]
            assert {kind_a, kind_b} == {KIND_VERTEX, KIND_EDGE}
            vertex_point, edge_point = (a, b) if kind_a == KIND_VERTEX else (b, a)
            assert lv.vert_origin[edge_point] == control_edge
            assert lv.vert_origin[vertex_point] in topology.edges[control_edge]

    # origin indices are valid for their kind
    limits = {KIND_VERTEX: n_v, KIND_EDGE: n_e, KIND_FACE: n_f}
    assert all(0 <= o < limits[k] for k, o in zip(lv.vert_kind, lv.vert_origin))


def test_a7_control_vertices_keep_their_index(head_surface):
    lv = head_surface.level(3)
    n_v = len(head_surface.topology.vertex_ids)
    assert lv.vert_kind[:n_v] == [KIND_VERTEX] * n_v
    assert lv.vert_origin[:n_v] == list(range(n_v))
