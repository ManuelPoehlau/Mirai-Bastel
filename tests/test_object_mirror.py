"""Object mirror pairs, B2: the pure maths in `mirai.object_mirror` (OBJECT_MIRROR_SYMMETRY_PROPOSAL §3).

`F(t, R, s, c) = (H t + 2d n, H R H, s, H c)` and the mirrored mesh (`H p`, winding reversed). The §3
probe is a test here: bit-exact for planes through the origin, 1e-12 for an offset plane.
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401
from tests.mesh_invariants import assert_face_triangulations_sound, assert_mesh_invariants
from tests.test_scene_primitives import _EXPECTED, _centroid, _directed_edges, _face_normal

from core import Mesh, MirrorPair, ObjectId, ObjectTransform, SceneObject, SymmetryDefinition
from mirai import object_space
from mirai.object_mirror import (
    PLANES,
    SYNC_TOLERANCE,
    in_sync,
    mirror_mesh,
    mirror_placement,
    mirror_transform,
    pair_residual,
    plane_label,
    reflect_point,
)
from mirai.scene_factory import PRIMITIVES

X = PLANES["X"][0]
OFFSET_PLANES = [((1.0, 0.0, 0.0), 0.75), ((0.0, 1.0, 0.0), -1.25), ((0.0, 0.0, 1.0), 0.3)]


def _random_rotation(rng: random.Random):
    axis = [rng.uniform(-1, 1) for _ in range(3)]
    norm = math.sqrt(sum(v * v for v in axis)) or 1.0
    return object_space.orthonormalize(
        object_space.axis_angle_rotation(tuple(v / norm for v in axis), rng.uniform(-math.pi, math.pi))
    )


def _random_object(rng: random.Random, oid: int = 0) -> SceneObject:
    return SceneObject(
        ObjectId(oid),
        Mesh(),
        transform=ObjectTransform(
            translation=tuple(rng.uniform(-5, 5) for _ in range(3)),
            rotation=_random_rotation(rng),
            scale=rng.uniform(0.2, 3.0),
        ),
        pivot=tuple(rng.uniform(-2, 2) for _ in range(3)),
    )


def _partner(a: SceneObject, normal, offset, oid: int = 1) -> SceneObject:
    transform, pivot = mirror_placement(a, normal, offset)
    return SceneObject(ObjectId(oid), Mesh(), transform=transform, pivot=pivot)


def _h(normal, p):
    return reflect_point(normal, 0.0, p)


def _rotation_close(a, b, tol=1e-12):
    return all(abs(x - y) <= tol for ra, rb in zip(a, b) for x, y in zip(ra, rb))


# -- F: the placement ------------------------------------------------------------------------


@pytest.mark.parametrize("axis", list(PLANES))
def test_planes_through_the_origin_are_bit_exact(axis):
    """§3 probe: 500 random placements, 5 points each: `to_world(B, H p) == S(to_world(A, p))` exactly."""
    normal, offset = PLANES[axis]
    rng = random.Random(axis)
    for _ in range(500):
        a = _random_object(rng)
        b = _partner(a, normal, offset)
        assert b.transform.scale == a.transform.scale
        for _ in range(5):
            p = tuple(rng.uniform(-3, 3) for _ in range(3))
            assert object_space.to_world(b, _h(normal, p)) == reflect_point(normal, offset, object_space.to_world(a, p))


@pytest.mark.parametrize("normal,offset", OFFSET_PLANES)
def test_offset_planes_are_exact_to_rounding(normal, offset):
    rng = random.Random(str(normal))
    worst = 0.0
    for _ in range(500):
        a = _random_object(rng)
        b = _partner(a, normal, offset)
        for _ in range(5):
            p = tuple(rng.uniform(-3, 3) for _ in range(3))
            got = object_space.to_world(b, _h(normal, p))
            want = reflect_point(normal, offset, object_space.to_world(a, p))
            worst = max(worst, max(abs(g - w) for g, w in zip(got, want)))
    assert worst <= 1e-12


@pytest.mark.parametrize("normal,offset", [PLANES["X"], PLANES["Y"], PLANES["Z"]] + OFFSET_PLANES)
def test_f_is_an_involution_and_the_partner_is_a_proper_rotation(normal, offset):
    rng = random.Random(7)
    for _ in range(100):
        a = _random_object(rng)
        b = _partner(a, normal, offset)
        back = _partner(b, normal, offset, oid=2)
        if offset == 0.0:
            assert back.transform == a.transform and back.pivot == a.pivot  # exact
        else:
            assert all(abs(x - y) <= 1e-12 for x, y in zip(back.transform.translation, a.transform.translation))
            assert _rotation_close(back.transform.rotation, a.transform.rotation)
        # ObjectTransform validates orthonormal and det +1: no negative scale, no reflection
        assert b.transform.scale > 0


def test_translation_reverses_the_normal_component_and_keeps_the_tangential_one():
    """§3 numbers: plane X = 0, t_A = (2, 1, -3), delta (0.5, 0.25, -0.75)."""
    a = SceneObject(ObjectId(0), Mesh(), transform=ObjectTransform(translation=(2.0, 1.0, -3.0)))
    b = _partner(a, X, 0.0)
    assert b.transform.translation == (-2.0, 1.0, -3.0)
    a.transform = ObjectTransform(translation=(2.5, 1.25, -3.75))
    moved = mirror_transform(a.transform, X, 0.0)
    assert moved.translation == (-2.5, 1.25, -3.75)  # not the naive "same vector" (-1.5, 1.25, -3.75)
    delta = tuple(m - s for m, s in zip(moved.translation, b.transform.translation))
    assert delta == (-0.5, 0.25, -0.75)


@pytest.mark.parametrize("axis", list(PLANES))
def test_rotation_about_the_normal_turns_the_partner_the_same_way(axis):
    normal = PLANES[axis][0]
    theta = math.radians(30)
    turned = mirror_transform(ObjectTransform(rotation=object_space.axis_angle_rotation(normal, theta)), normal, 0.0)
    assert _rotation_close(turned.rotation, object_space.axis_angle_rotation(normal, theta))


@pytest.mark.parametrize("axis", list(PLANES))
def test_rotation_about_a_tangential_axis_turns_the_partner_the_other_way(axis):
    normal = PLANES[axis][0]
    theta = math.radians(30)
    for other in PLANES:
        tangent = PLANES[other][0]
        if tangent == normal:
            continue
        turned = mirror_transform(ObjectTransform(rotation=object_space.axis_angle_rotation(tangent, theta)), normal, 0.0)
        assert _rotation_close(turned.rotation, object_space.axis_angle_rotation(tangent, -theta))


def test_uniform_scale_is_kept_and_the_world_pivots_stay_mirrored():
    a = SceneObject(
        ObjectId(0), Mesh(), transform=ObjectTransform(translation=(1.5, 0.5, 0.0), scale=2.5), pivot=(0.25, -0.5, 1.0)
    )
    b = _partner(a, X, 0.0)
    assert b.transform.scale == 2.5
    assert b.pivot == (-0.25, -0.5, 1.0)
    assert object_space.to_world(b, b.pivot) == _h(X, object_space.to_world(a, a.pivot))


def test_identity_placement_mirrors_to_an_identity_placement():
    a = SceneObject(ObjectId(0), Mesh())
    b = _partner(a, X, 0.0)
    assert object_space.is_identity(b.transform)


# -- residual ------------------------------------------------------------------------------


def test_pair_residual_is_zero_in_sync_and_measures_the_offset():
    rng = random.Random(3)
    a = _random_object(rng)
    b = _partner(a, X, 0.0)
    pair = MirrorPair(a.id, b.id, X, 0.0)
    assert pair_residual(a, b, pair) == 0.0 and in_sync(a, b, pair)
    t = b.transform
    b.transform = ObjectTransform(translation=(t.translation[0] + 0.12, *t.translation[1:]), rotation=t.rotation, scale=t.scale)
    assert pair_residual(a, b, pair) == pytest.approx(0.12)
    assert not in_sync(a, b, pair)
    b.transform = t
    b.pivot = (b.pivot[0], b.pivot[1] + 1e-12, b.pivot[2])
    assert in_sync(a, b, pair) and 0 < pair_residual(a, b, pair) <= SYNC_TOLERANCE


def test_plane_labels():
    assert plane_label(*PLANES["X"]) == "X = 0"
    assert plane_label((0.0, 0.0, 1.0), 0.5) == "Z = 0.5"


# -- the mirrored mesh -----------------------------------------------------------------------


@pytest.mark.parametrize("name", list(_EXPECTED))
@pytest.mark.parametrize("axis", list(PLANES))
def test_mirrored_primitives_are_valid_with_reversed_winding(name, axis):
    normal = PLANES[axis][0]
    source = PRIMITIVES[name]()
    mesh = mirror_mesh(source, normal)
    assert_mesh_invariants(mesh, context=f"{name} mirrored {axis}")
    assert_face_triangulations_sound(mesh, context=f"{name} mirrored {axis}")
    assert len(mesh.all_vertex_ids()) == len(source.all_vertex_ids())
    assert len(mesh.all_edge_ids()) == len(source.all_edge_ids())
    assert len(mesh.all_face_ids()) == len(source.all_face_ids())
    assert mesh.symmetry_definition is None
    # positions are H p, vertex by vertex
    for old, new in zip(sorted(source.all_vertex_ids()), sorted(mesh.all_vertex_ids())):
        assert mesh.vertex_position(new) == _h(normal, source.vertex_position(old))
    # winding consistent; closed stays closed, the plane keeps its outline only
    directed = _directed_edges(mesh)
    assert max(directed.values()) == 1
    unmatched = [edge for edge in directed if (edge[1], edge[0]) not in directed]
    closed = _EXPECTED[name][2]
    assert (unmatched == []) if closed else len(unmatched) == len([e for e in _directed_edges(source) if (e[1], e[0]) not in _directed_edges(source)])


@pytest.mark.parametrize("name", ["cube", "sphere", "cylinder"])
@pytest.mark.parametrize("axis", list(PLANES))
def test_mirrored_closed_primitives_face_outward(name, axis):
    mesh = mirror_mesh(PRIMITIVES[name](), PLANES[axis][0])
    centre = _centroid([mesh.vertex_position(v) for v in mesh.all_vertex_ids()])
    for fid in mesh.all_face_ids():
        normal = _face_normal(mesh, fid)
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
        out = tuple(c - o for c, o in zip(_centroid(pts), centre))
        assert sum(n * o for n, o in zip(normal, out)) > 0


def test_mirrored_plane_normals_are_the_reflected_normals():
    source = PRIMITIVES["plane"]()
    mesh = mirror_mesh(source, PLANES["Y"][0])  # plane faces +Y -> the mirror faces -Y
    for fid in mesh.all_face_ids():
        assert _face_normal(mesh, fid)[1] < 0


def test_mirror_mesh_is_independent_and_drops_the_symmetry_definition_keeps_loose_edges():
    source = PRIMITIVES["cube"]()
    source.symmetry_definition = SymmetryDefinition(
        plane_point=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0), seam_edges=frozenset()
    )
    loose_a = source.add_vertex((3.0, 0.0, 0.0))
    loose_b = source.add_vertex((4.0, 1.0, 0.0))
    source.add_edge(loose_a, loose_b)
    mesh = mirror_mesh(source, X)
    assert mesh.symmetry_definition is None
    assert len(mesh.all_edge_ids()) == len(source.all_edge_ids())
    positions = {mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    assert (-3.0, 0.0, 0.0) in positions and (-4.0, 1.0, 0.0) in positions
    vid = sorted(source.all_vertex_ids())[0]
    before = mesh.vertex_position(sorted(mesh.all_vertex_ids())[0])
    source.set_vertex_position(vid, (9.0, 9.0, 9.0))
    assert mesh.vertex_position(sorted(mesh.all_vertex_ids())[0]) == before


def test_mirror_pair_world_geometry_is_the_mirror_image():
    """End to end: a placed sphere and its mirror copy - every world vertex of B is S of A's."""
    rng = random.Random(11)
    a = _random_object(rng)
    a.mesh = PRIMITIVES["sphere"]()
    b = _partner(a, X, 0.0)
    b.mesh = mirror_mesh(a.mesh, X)
    for va, vb in zip(sorted(a.mesh.all_vertex_ids()), sorted(b.mesh.all_vertex_ids())):
        wa = object_space.to_world(a, a.mesh.vertex_position(va))
        assert object_space.to_world(b, b.mesh.vertex_position(vb)) == _h(X, wa)
