"""T-3 (AD-028 §12): the skinning math of `mirai.skinning` (§5.1).

`evaluate` against an independent implementation (4×4 homogeneous matrices, the full product chain down
the hierarchy with no short-circuit, its own rest frames, `math.fsum` over every key incl. unposed ones,
the object share) within 1e-12; the rest pose bit-exact; a child follows its parent; the placement
conjugation (the world result equals the world skin transform of the world point, and equals the
result after Apply transform); dead keys count as the object's share.
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import BoneId, LayerKind, Mesh, ObjectTransform, PointLayerInfo, Rig
from mirai import skinning
from mirai.object_space import axis_angle_rotation
from mirai.skinning import REST, BonePose, evaluate
from tests.test_mesh_change_journal import _grid


# -- the independent oracle ------------------------------------------------------------------------


def _mm(a, b):
    return [[math.fsum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _h(rot, t, s=1.0):
    return [[s * rot[0][0], s * rot[0][1], s * rot[0][2], t[0]],
            [s * rot[1][0], s * rot[1][1], s * rot[1][2], t[1]],
            [s * rot[2][0], s * rot[2][1], s * rot[2][2], t[2]],
            [0.0, 0.0, 0.0, 1.0]]


def _inv_rigid(rot, t, s=1.0):
    """Inverse of x -> s·R·x + t: x -> Rᵀ·(x − t)/s."""
    rt = [[rot[j][i] / s for j in range(3)] for i in range(3)]
    c = [-math.fsum(rt[i][k] * t[k] for k in range(3)) for i in range(3)]
    return [[rt[0][0], rt[0][1], rt[0][2], c[0]], [rt[1][0], rt[1][1], rt[1][2], c[1]],
            [rt[2][0], rt[2][1], rt[2][2], c[2]], [0.0, 0.0, 0.0, 1.0]]


def _frame(bone):
    """The rest frame of AD-028 §3.1, written independently (Rodrigues matrix about y)."""
    d = [bone.tail[i] - bone.head[i] for i in range(3)]
    n = math.sqrt(math.fsum(c * c for c in d))
    y = [c / n for c in d]
    ref = [1.0, 0.0, 0.0] if abs(y[0]) <= 1.0 - 1e-6 else [0.0, 0.0, 1.0]
    dot = math.fsum(ref[i] * y[i] for i in range(3))
    x0 = [ref[i] - dot * y[i] for i in range(3)]
    n0 = math.sqrt(math.fsum(c * c for c in x0))
    x0 = [c / n0 for c in x0]
    rot = axis_angle_rotation(tuple(y), bone.roll)
    x = [math.fsum(rot[i][k] * x0[k] for k in range(3)) for i in range(3)]
    z = [x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0]]
    return [[x[i], y[i], z[i]] for i in range(3)], list(bone.head)


def _world(rig, pose, bid):
    bone = rig.bone(bid)
    rot, h = _frame(bone)
    lp = pose.get(bid, REST)
    local = _mm(_mm(_h(rot, h), _h(lp.rotation, lp.translation, lp.scale)), _inv_rigid(rot, h))
    if bone.parent is None:
        return local
    return _mm(_world(rig, pose, bone.parent), local)


def _oracle(base, rig, pose, transform=None, pivot=(0.0, 0.0, 0.0)):
    lid = skinning.skin_layer(base)
    mats = {int(b): _world(rig, pose, b) for b in rig.bone_ids()}
    if transform is not None:
        s, rot = transform.scale, transform.rotation
        rp = [math.fsum(rot[i][k] * pivot[k] for k in range(3)) for i in range(3)]
        c = [transform.translation[i] + pivot[i] - s * rp[i] for i in range(3)]
        t, ti = _h(rot, c, s), _inv_rigid(rot, c, s)
        mats = {k: _mm(_mm(ti, m), t) for k, m in mats.items()}
    out = {}
    for v in base.all_vertex_ids():
        p = base.vertex_position(v)
        value = base.layer_value(lid, v)
        r = 1.0 - math.fsum(w for _, w in value)
        comps = [[r * p[i]] for i in range(3)]
        for k, w in value:
            m = mats.get(k)
            if m is None:  # a dead key: the object's share
                for i in range(3):
                    comps[i].append(w * p[i])
                continue
            for i in range(3):
                comps[i].append(w * math.fsum((m[i][0] * p[0], m[i][1] * p[1], m[i][2] * p[2], m[i][3])))
        out[v] = tuple(math.fsum(c) for c in comps)
    return out


# -- fixtures ----------------------------------------------------------------------------------------


def _rig() -> Rig:
    rig = Rig()
    rig, head = rig.with_new_bone("Head", (0.0, 0.5, 0.0), (0.0, 2.5, 0.2))
    rig, jaw = rig.with_new_bone("Jaw", (0.5, 1.0, 0.3), (1.5, 0.2, 1.0), parent=head, roll=0.4)
    rig, tip = rig.with_new_bone("Tip", (1.5, 0.2, 1.0), (2.0, 0.0, 1.5), parent=jaw)
    rig, eye = rig.with_new_bone("Eye", (3.0, 3.0, 0.0), (3.0, 3.0, 1.0), roll=-1.1)
    return rig


def _bound_mesh(rng: random.Random, n: int = 4, keys=(0, 1, 2, 3, 9)) -> Mesh:
    mesh = _grid(n)
    for v in mesh.all_vertex_ids():
        x, y, _ = mesh.vertex_position(v)
        mesh.set_vertex_position(v, (x, y, rng.uniform(-0.5, 0.5)))
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in mesh.all_vertex_ids():
        if rng.random() < 0.85:
            chosen = rng.sample(keys, rng.randint(1, 4))
            raw = [rng.random() + 0.05 for _ in chosen]
            scale = 1.0 if rng.random() < 0.5 else rng.uniform(0.3, 0.95)
            mesh.set_layer_value(lid, v, [(k, w / sum(raw) * scale) for k, w in zip(chosen, raw)])
    return mesh


def _random_pose(rng: random.Random, rig: Rig, *, share: float = 0.7) -> dict:
    pose = {}
    for bid in rig.bone_ids():
        if rng.random() < share:
            axis = [rng.uniform(-1, 1) for _ in range(3)]
            n = math.sqrt(sum(c * c for c in axis)) or 1.0
            pose[bid] = BonePose(
                rotation=axis_angle_rotation(tuple(c / n for c in axis), rng.uniform(-1.2, 1.2)),
                translation=tuple(rng.uniform(-0.3, 0.3) for _ in range(3)) if rng.random() < 0.5 else (0.0, 0.0, 0.0),
                scale=rng.uniform(0.6, 1.4) if rng.random() < 0.3 else 1.0,
            )
    return pose


def _random_transform(rng: random.Random) -> ObjectTransform:
    axis = [rng.uniform(-1, 1) for _ in range(3)]
    n = math.sqrt(sum(c * c for c in axis))
    return ObjectTransform(
        translation=tuple(rng.uniform(-2, 2) for _ in range(3)),
        rotation=axis_angle_rotation(tuple(c / n for c in axis), rng.uniform(-3, 3)),
        scale=rng.uniform(0.5, 2.0),
    )


def _max_diff(a: dict, b: dict) -> float:
    return max(max(abs(x - y) for x, y in zip(a[v], b[v])) for v in a)


# -- tests -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(8))
def test_evaluate_matches_the_independent_implementation(seed):
    rng = random.Random(seed)
    rig = _rig()
    mesh = _bound_mesh(rng)
    pose = _random_pose(rng, rig)
    got = evaluate(mesh, None, rig, pose)
    assert _max_diff(got, _oracle(mesh, rig, pose)) <= 1e-12
    transform, pivot = _random_transform(rng), tuple(rng.uniform(-1, 1) for _ in range(3))
    got = evaluate(mesh, None, rig, pose, (transform, pivot))
    assert _max_diff(got, _oracle(mesh, rig, pose, transform, pivot)) <= 1e-12


def test_the_rest_pose_is_bit_exact():
    rng = random.Random(1)
    rig = _rig()
    mesh = _bound_mesh(rng)
    rest = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    transform = (_random_transform(rng), (0.3, 0.1, -0.2))
    for pose in ({}, {b: REST for b in rig.bone_ids()}, {b: BonePose() for b in rig.bone_ids()}):
        for placement in (None, transform):
            assert evaluate(mesh, None, rig, pose, placement) == rest
    assert skinning.skin_transforms(rig, {b: REST for b in rig.bone_ids()}) == {}
    # a posed bone moves only its points: every point without a key of it (or its children) is exact
    pose = {BoneId(3): _random_pose(random.Random(2), rig, share=1.0)[BoneId(3)]}
    got = evaluate(mesh, None, rig, pose)
    lid = skinning.skin_layer(mesh)
    for v, p in got.items():
        if all(k != 3 for k, _ in mesh.layer_value(lid, v)):
            assert p == rest[v]


def test_a_child_follows_its_parent():
    rig = _rig()
    mesh = Mesh()
    a = mesh.add_vertex((1.0, 0.7, 0.6))
    b = mesh.add_vertex((1.0, 0.7, 0.6))
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    mesh.set_layer_value(lid, a, ((1, 1.0),))  # the jaw
    mesh.set_layer_value(lid, b, ((2, 1.0),))  # the jaw's child, unposed
    pose = {BoneId(1): BonePose(rotation=axis_angle_rotation((1.0, 0.0, 0.0), 0.5))}
    got = evaluate(mesh, None, rig, pose)
    assert got[a] == got[b] and got[a] != mesh.vertex_position(a)  # the child's transform is the parent's
    pose[BoneId(0)] = BonePose(translation=(0.0, 0.0, 1.0))  # the head moves: both follow it
    moved = evaluate(mesh, None, rig, pose)
    assert moved[a] == moved[b]
    assert _max_diff(moved, _oracle(mesh, rig, pose)) <= 1e-12


def test_the_placement_is_conjugated_and_apply_transform_keeps_the_world_result():
    from mirai import object_space

    rng = random.Random(4)
    rig = _rig()
    mesh = _bound_mesh(rng)
    pose = _random_pose(rng, rig, share=1.0)
    transform = _random_transform(rng)
    pivot = (0.2, -0.4, 0.1)

    class Obj:
        pass

    obj = Obj()
    obj.transform, obj.pivot = transform, pivot
    skinned = evaluate(mesh, None, rig, pose, (transform, pivot))
    world = skinning.skin_transforms(rig, pose)
    lid = skinning.skin_layer(mesh)
    for v in mesh.all_vertex_ids():
        p_world = object_space.to_world(obj, mesh.vertex_position(v))
        expected = skinning.skin_point(p_world, mesh.layer_value(lid, v), skinning._flat(world))
        got = object_space.to_world(obj, skinned[v])
        assert max(abs(x - y) for x, y in zip(got, expected)) <= 1e-12
    # Apply transform: the mesh holds T·p and T = I - the world result is the same up to rounding
    baked = Mesh.from_state(mesh.export_state())
    for v in baked.all_vertex_ids():
        baked.set_vertex_position(v, object_space.to_world(obj, mesh.vertex_position(v)))
    after = evaluate(baked, None, rig, pose)
    for v in mesh.all_vertex_ids():
        assert max(abs(x - y) for x, y in zip(after[v], object_space.to_world(obj, skinned[v]))) <= 1e-12


def test_dead_keys_count_as_the_object_share():
    rig = _rig()
    mesh = Mesh()
    v = mesh.add_vertex((1.0, 1.0, 0.5))
    u = mesh.add_vertex((1.0, 1.0, 0.5))
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    mesh.set_layer_value(lid, v, ((1, 0.5), (9, 0.3)))  # 9: no such bone
    mesh.set_layer_value(lid, u, ((1, 0.5),))  # the same with the dead share as the object's
    pose = {BoneId(1): BonePose(rotation=axis_angle_rotation((0.0, 0.0, 1.0), 0.9))}
    got = evaluate(mesh, None, rig, pose)
    assert got[v] == got[u]
    assert _max_diff(got, _oracle(mesh, rig, pose)) <= 1e-12


def test_evaluate_reads_the_input_positions_and_a_mesh_without_weights_is_its_input():
    rng = random.Random(6)
    rig = _rig()
    mesh = _bound_mesh(rng)
    pose = _random_pose(rng, rig, share=1.0)
    shifted = {v: tuple(c + 0.25 for c in mesh.vertex_position(v)) for v in mesh.all_vertex_ids()}
    moved = Mesh.from_state(mesh.export_state())
    for v, p in shifted.items():
        moved.set_vertex_position(v, p)
    assert evaluate(mesh, shifted, rig, pose) == evaluate(moved, None, rig, pose)
    assert evaluate(mesh, moved, rig, pose) == evaluate(moved, None, rig, pose)
    plain = _grid(2)
    assert evaluate(plain, None, rig, pose) == {v: plain.vertex_position(v) for v in plain.all_vertex_ids()}
    assert evaluate(mesh, None, None, pose) == {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


def test_bone_pose_validation():
    with pytest.raises(ValueError):
        BonePose(scale=0.0)
    with pytest.raises(ValueError):
        BonePose(rotation=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)))
    assert BonePose().is_identity and not BonePose(translation=(0.0, 1e-300, 0.0)).is_identity
