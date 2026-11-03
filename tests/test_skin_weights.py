"""T-8 (AD-028 §12): the weight write rule (`mirai.skin_weights`, §3.4, DEVCHAT-001 P-3).

Every case of §3.4 - raise (the other shares and the object's scale), lower to the parent and to the
object for a root, a fifth key (raise and lower), the Soft target, bone deletion; **the path dependence
pinned** (the §3.4 example gives the documented split, not the old one); a stroke computed from its
press values gives the same result whatever its intermediate steps; Undo restores the old split exactly.
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import BoneId, HistoryStack, LayerKind, Mesh, PointLayerInfo, Rig
from core.operations import MeshDeltaCommand, record_mesh_change
from mirai.skin_weights import (
    WeightStroke, bone_share, delete_bone_weights, parent_function, set_bone_weight, soft_target,
)
from tests.mesh_invariants import assert_layer_invariants

# head 0 (root), jaw 1 (child of head), cheek 2 (root), lip 3 (child of jaw), brow 4, ear 5 (roots)
HEAD, JAW, CHEEK, LIP, BROW, EAR = 0, 1, 2, 3, 4, 5


def _rig() -> Rig:
    rig = Rig()
    rig, _ = rig.with_new_bone("Head", (0, 0, 0), (0, 1, 0))
    rig, _ = rig.with_new_bone("Jaw", (0, 0, 0), (0, -1, 1), parent=BoneId(HEAD))
    rig, _ = rig.with_new_bone("Cheek", (1, 0, 0), (1, 1, 0))
    rig, _ = rig.with_new_bone("Lip", (0, -1, 1), (0, -1, 2), parent=BoneId(JAW))
    rig, _ = rig.with_new_bone("Brow", (0, 1, 1), (0, 2, 1))
    rig, _ = rig.with_new_bone("Ear", (2, 0, 0), (2, 1, 0))
    return rig


PARENT = parent_function(_rig())


def _close(value, expected, tol=1e-15) -> bool:
    return [k for k, _ in value] == [k for k, _ in expected] and all(
        abs(a - b) <= tol for (_, a), (_, b) in zip(value, expected)
    )


def _mesh(values) -> tuple[Mesh, object, list]:
    mesh = Mesh()
    vertices = [mesh.add_vertex((float(i), 0.0, 0.0)) for i in range(len(values))]
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v, value in zip(vertices, values):
        mesh.set_layer_value(lid, v, value)
    return mesh, lid, vertices


def test_raise_scales_the_other_shares_and_the_object_share():
    # {jaw 0.2, cheek 0.3}, r 0.5: jaw -> 0.6 scales cheek and r by (1 - 0.6) / (1 - 0.2) = 0.5
    got = set_bone_weight(((JAW, 0.2), (CHEEK, 0.3)), JAW, 0.6, PARENT)
    assert _close(got, ((JAW, 0.6), (CHEEK, 0.15)))
    assert abs(1.0 - math.fsum(w for _, w in got) - 0.25) <= 1e-15  # r 0.5 -> 0.25
    # a new bone on an unbound vertex takes from the object
    assert set_bone_weight((), JAW, 0.4, PARENT) == ((JAW, 0.4),)
    assert set_bone_weight(((JAW, 0.4),), JAW, 0.4, PARENT) == ((JAW, 0.4),)  # Δ = 0: unchanged


def test_lower_gives_to_the_parent_and_a_root_to_the_object():
    got = set_bone_weight(((JAW, 0.7), (CHEEK, 0.3)), JAW, 0.4, PARENT)  # jaw's parent: head
    assert _close(got, ((HEAD, 0.3), (JAW, 0.4), (CHEEK, 0.3)), 1e-15)
    got = set_bone_weight(((HEAD, 0.6), (CHEEK, 0.4)), HEAD, 0.1, PARENT)  # head is a root: to the object
    assert _close(got, ((HEAD, 0.1), (CHEEK, 0.4)))
    got = set_bone_weight(((LIP, 0.5), (JAW, 0.5)), LIP, 0.0, PARENT)  # to 0: the key goes, the parent takes it
    assert got == ((JAW, 1.0),)


def test_the_path_dependence_is_pinned():
    """DEVCHAT-001 P-3 / §3.4: raise then lower back in a second gesture gives the documented split."""
    mesh, lid, (v,) = _mesh([((JAW, 0.4), (CHEEK, 0.6))])
    rig = _rig()
    history = HistoryStack()
    for target in (0.7, 0.4):  # two gestures
        stroke = WeightStroke(mesh, lid, JAW, rig, [v])
        delta, _ = record_mesh_change(mesh, lambda: stroke.step({v: target}))
        history.push(MeshDeltaCommand(mesh, delta, "weight"))
        if target == 0.7:
            assert _close(mesh.layer_value(lid, v), ((JAW, 0.7), (CHEEK, 0.3)), 1e-15)
    after = mesh.layer_value(lid, v)
    assert _close(after, ((HEAD, 0.3), (JAW, 0.4), (CHEEK, 0.3)), 1e-15)
    assert after != ((JAW, 0.4), (CHEEK, 0.6))  # not the old split
    history.undo()
    history.undo()
    assert mesh.layer_value(lid, v) == ((JAW, 0.4), (CHEEK, 0.6))  # Undo restores it exactly


def test_a_fifth_key_keeps_the_bone_and_the_three_largest_others():
    # raise a fifth bone on a full vertex: brow stays at x, the smallest other (ear 0.1) is dropped and
    # its share goes to the remaining others proportionally, the object's share included
    full = ((HEAD, 0.3), (CHEEK, 0.2), (LIP, 0.2), (EAR, 0.1))  # r = 0.2
    got = set_bone_weight(full, BROW, 0.5, PARENT)
    # scaled by 0.5: head .15, cheek .1, lip .1, ear .05, r .1; ear dropped: (.15+.1+.1+.1 + .05) / .45
    grow = 0.5 / 0.45
    assert _close(got, ((HEAD, 0.15 * grow), (CHEEK, 0.1 * grow), (LIP, 0.1 * grow), (BROW, 0.5)), 1e-15)
    assert abs(math.fsum(w for _, w in got) + 0.1 * grow - 1.0) <= 1e-15
    # ties: the smaller key stays (cheek 2 and lip 3 tie at 0.2 with ear 5 dropped first)
    tie = ((HEAD, 0.25), (CHEEK, 0.25), (LIP, 0.25), (EAR, 0.25))
    got = set_bone_weight(tie, BROW, 0.2, PARENT)
    assert [k for k, _ in got] == [HEAD, CHEEK, LIP, BROW]
    # lowering a bone whose parent is new on a full vertex: the parent arrives, the smallest other goes
    full = ((CHEEK, 0.3), (LIP, 0.3), (BROW, 0.2), (EAR, 0.2))
    got = set_bone_weight(full, LIP, 0.05, PARENT)  # lip's parent jaw gets 0.25 -> five keys
    # others: cheek .3, jaw .25, brow .2, ear .2 -> brow and ear tie, the smaller key (brow) stays
    assert [k for k, _ in got] == [JAW, CHEEK, LIP, BROW] and bone_share(got, LIP) == 0.05
    grow = 0.95 / 0.75  # ear's 0.2 to cheek, jaw and brow proportionally (no object share here)
    assert _close(got, ((JAW, 0.25 * grow), (CHEEK, 0.3 * grow), (LIP, 0.05), (BROW, 0.2 * grow)), 1e-15)
    assert abs(math.fsum(w for _, w in got) - 1.0) <= 1e-15


def test_the_soft_target():
    assert soft_target(0.2, 1.0, 1.0) == 1.0
    assert soft_target(0.2, 1.0, 0.0) == 0.2
    assert abs(soft_target(0.2, 1.0, 0.5) - 0.6) <= 1e-15
    assert abs(soft_target(0.8, 0.0, 0.25) - 0.6) <= 1e-15


def test_a_stroke_is_computed_from_its_press_values():
    """The same final targets give the same mesh whatever the intermediate steps (no drift, no path
    dependence inside one gesture); a vertex the field no longer names goes back to its press value."""
    rng = random.Random(3)
    values = []
    for _ in range(40):
        keys = rng.sample([HEAD, JAW, CHEEK, LIP, BROW, EAR], rng.randint(0, 4))
        raw = [rng.random() + 0.05 for _ in keys]
        scale = 1.0 if rng.random() < 0.5 else rng.uniform(0.3, 0.9)
        values.append(tuple((k, w / sum(raw) * scale) for k, w in zip(keys, raw)))
    rig = _rig()
    final = {}
    results = []
    for steps in (0, 1, 7):
        mesh, lid, vertices = _mesh(values)
        final = {v: rng.random() for v in vertices[::2]} if not final else final
        stroke = WeightStroke(mesh, lid, JAW, rig, vertices)
        for _ in range(steps):
            stroke.step({v: rng.random() for v in rng.sample(vertices, 25)})
        stroke.step(final)
        results.append(mesh.export_state()["point_layers"])
        for v in vertices[1::2]:
            assert mesh.layer_value(lid, v) == stroke.press[v]
        assert_layer_invariants(mesh)
    assert results[0] == results[1] == results[2]


def test_deleting_a_bone_gives_its_share_to_its_parent_with_exact_undo():
    mesh, lid, vertices = _mesh([
        ((JAW, 0.6), (CHEEK, 0.4)),
        ((HEAD, 0.2), (JAW, 0.3), (LIP, 0.5)),
        ((JAW, 1.0),),
        ((CHEEK, 0.5),),
        ((HEAD, 0.25), (JAW, 0.25), (CHEEK, 0.25), (EAR, 0.25)),
    ])
    before = mesh.layer_items(lid)
    rig = _rig()
    delta, count = record_mesh_change(mesh, lambda: delete_bone_weights(mesh, lid, JAW, rig))
    assert count == 4
    got = [mesh.layer_value(lid, v) for v in vertices]
    assert _close(got[0], ((HEAD, 0.6), (CHEEK, 0.4)))
    assert _close(got[1], ((HEAD, 0.5), (LIP, 0.5)))
    assert got[2] == ((HEAD, 1.0),)
    assert got[3] == ((CHEEK, 0.5),)
    assert got[4] == ((HEAD, 0.5), (CHEEK, 0.25), (EAR, 0.25))  # the parent takes the bone's place
    assert all(k != JAW for value in got for k, _ in value)
    assert_layer_invariants(mesh)
    mesh.apply_delta(delta, reverse=True)
    assert mesh.layer_items(lid) == before


@pytest.mark.parametrize("x", [-0.1, 1.5, math.nan])
def test_a_weight_outside_zero_to_one_is_refused(x):
    with pytest.raises(ValueError):
        set_bone_weight((), JAW, x, PARENT)


def test_random_writes_keep_the_canonical_form():
    rng = random.Random(8)
    mesh, lid, vertices = _mesh([()] * 30)
    rig = _rig()
    for _ in range(600):
        v = rng.choice(vertices)
        bone = rng.choice([HEAD, JAW, CHEEK, LIP, BROW, EAR])
        x = rng.choice((0.0, 1.0, rng.random()))
        new = set_bone_weight(mesh.layer_value(lid, v), bone, x, parent_function(rig))
        mesh.set_layer_value(lid, v, new)
        assert abs(bone_share(mesh.layer_value(lid, v), bone) - x) <= 1e-12 or x == 0.0
    assert_layer_invariants(mesh)
