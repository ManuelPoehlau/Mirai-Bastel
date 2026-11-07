"""T-2 (AD-028 §12): the scene rig in the Core (`core.rig`, `Scene.rig`, file version 7).

Validation (cycle, unknown parent, duplicate name or id, degenerate bone, ids at or above the counter,
types), `rest_frame` (orthonormal, det +1, roll, the parallel-to-X case, the jaw example), pure updates
(ids never reused, re-parenting on delete), the dict / file round trip, the version 7 rules and the
versions 2-7 that are read.
"""

from __future__ import annotations

import json
import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import Bone, BoneId, LayerKind, PointLayerInfo, Rig, Scene, rest_frame
from core.serialization import scene_from_dict, scene_from_json, scene_to_dict, scene_to_json
from tests.test_mesh_change_journal import _grid


def _bone(i, name=None, parent=None, head=(0.0, 0.0, 0.0), tail=(0.0, 1.0, 0.0), roll=0.0) -> Bone:
    return Bone(BoneId(i), name or f"B{i}", None if parent is None else BoneId(parent), head, tail, roll)


def _chain() -> Rig:
    rig = Rig()
    rig, head = rig.with_new_bone("Head", (0.0, 1.0, 0.0), (0.0, 2.0, 0.0))
    rig, jaw = rig.with_new_bone("Jaw", (0.0, 1.2, 0.1), (0.0, 0.9, 0.6), parent=head)
    rig, tongue = rig.with_new_bone("Tongue", (0.0, 1.0, 0.2), (0.0, 1.0, 0.5), parent=jaw, roll=0.3)
    return rig


# -- validation -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "build",
    [
        lambda: Rig((_bone(0), _bone(1, parent=1)), 2),  # own parent
        lambda: Rig((_bone(0, parent=1), _bone(1, parent=0)), 2),  # cycle
        lambda: Rig((_bone(0, parent=5),), 1),  # unknown parent
        lambda: Rig((_bone(0, "A"), _bone(1, "A")), 2),  # duplicate name
        lambda: Rig((_bone(0), _bone(0, "other")), 2),  # duplicate id
        lambda: Rig((_bone(1), _bone(0)), 2),  # not in id order
        lambda: Rig((_bone(2),), 2),  # id at the counter
        lambda: _bone(0, tail=(0.0, 0.0, 1e-10)),  # degenerate
        lambda: _bone(0, head=(0.0, math.nan, 0.0)),
        lambda: _bone(0, roll=math.inf),
        lambda: Bone(BoneId(0), "", None, (0, 0, 0), (0, 1, 0)),
        lambda: Bone(0, "A", None, (0, 0, 0), (0, 1, 0)),  # an int, not a BoneId
        lambda: Bone(BoneId(0), "A", 1, (0, 0, 0), (0, 1, 0)),
        lambda: Rig(("bone",), 1),
        lambda: Rig((), True),
    ],
)
def test_invalid_rigs_are_refused(build):
    with pytest.raises((ValueError, TypeError)):
        build()


def test_a_three_level_chain_is_valid_and_ordered():
    rig = _chain()
    assert rig.bone_ids() == [BoneId(0), BoneId(1), BoneId(2)] and rig.bone_id_counter == 3
    assert rig.ancestors(BoneId(2)) == (BoneId(1), BoneId(0))
    assert rig.children(BoneId(0)) == (BoneId(1),)
    assert rig.topological_order() == (BoneId(0), BoneId(1), BoneId(2))
    assert Rig() == Rig((), 0)  # an empty rig is a value too (its counter persists)


def test_pure_updates_never_reuse_an_id_and_reparent_on_delete():
    rig = _chain()
    without = rig.without_bone(BoneId(1))
    assert without.bone_ids() == [BoneId(0), BoneId(2)]
    tongue = without.bone(BoneId(2))
    assert tongue.parent == BoneId(0)  # re-parented to the deleted bone's parent
    assert (tongue.head, tongue.tail, tongue.roll) == (rig.bone(BoneId(2)).head, rig.bone(BoneId(2)).tail, 0.3)
    assert without.bone_id_counter == 3
    again, new = without.with_new_bone("Jaw", (0.0, 1.2, 0.1), (0.0, 0.9, 0.6))
    assert new == BoneId(3)  # never the freed 1
    with pytest.raises(KeyError):
        without.with_bone(_bone(1, "Jaw"))  # an absent id below the counter would be a reused one
    renamed = rig.with_name(BoneId(1), "Kiefer")
    assert renamed.bone(BoneId(1)).name == "Kiefer" and rig.bone(BoneId(1)).name == "Jaw"
    with pytest.raises(ValueError):
        rig.with_name(BoneId(1), "Head")
    assert rig.without_bone(BoneId(0)).bone(BoneId(1)).parent is None  # a root's children become roots


# -- rest frame -------------------------------------------------------------------------------------


def _check_frame(r):
    cols = [tuple(r[i][j] for i in range(3)) for j in range(3)]
    for i in range(3):
        for j in range(3):
            dot = sum(cols[i][k] * cols[j][k] for k in range(3))
            assert abs(dot - (1.0 if i == j else 0.0)) < 1e-12
    (a, b, c), (d, e, f), (g, h, k) = r
    assert abs(a * (e * k - f * h) - b * (d * k - f * g) + c * (d * h - e * g) - 1.0) < 1e-12
    return cols


def test_rest_frame_is_orthonormal_with_det_plus_one_on_random_bones():
    rng = random.Random(1)
    for _ in range(2000):
        head = tuple(rng.uniform(-3, 3) for _ in range(3))
        d = tuple(rng.uniform(-1, 1) for _ in range(3))
        if math.hypot(*d) < 1e-3:
            continue
        tail = tuple(h + x for h, x in zip(head, d))
        bone = _bone(0, head=head, tail=tail, roll=rng.uniform(-4, 4))
        r, h = rest_frame(bone)
        x, y, z = _check_frame(r)
        assert h == bone.head
        length = math.dist(head, tail)
        assert all(abs(y[i] - (tail[i] - head[i]) / length) < 1e-12 for i in range(3))


def test_rest_frame_roll_and_the_jaw_example():
    # a jaw from the hinge to the chin, roll 0: X is the world X axis (the Lab's hinge axis, F-15)
    r, _ = rest_frame(_bone(0, head=(0.0, 1.0, 0.0), tail=(0.0, 0.5, 0.8)))
    x, y, z = _check_frame(r)
    assert x == (1.0, 0.0, 0.0)
    # roll turns X about Y by the right-hand rule: +90° about +Y takes X to -Z
    r, _ = rest_frame(_bone(0, tail=(0.0, 1.0, 0.0), roll=math.pi / 2))
    x, y, z = _check_frame(r)
    assert all(abs(a - b) < 1e-15 for a, b in zip(x, (0.0, 0.0, -1.0)))
    assert y == (0.0, 1.0, 0.0)


def test_rest_frame_parallel_to_x_uses_the_z_axis():
    for direction in ((1.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (1.0, 1e-4, 0.0)):
        r, _ = rest_frame(_bone(0, tail=direction))
        x, y, z = _check_frame(r)
        assert abs(abs(y[0]) - 1.0) < 1e-6 or direction[1] == 1e-4
    r, _ = rest_frame(_bone(0, tail=(1.0, 0.0, 0.0)))
    x, y, z = _check_frame(r)
    assert x == (0.0, 0.0, 1.0) and y == (1.0, 0.0, 0.0)  # Z projected; then z = x × y
    # just outside the limit the world X is still the reference: the frame stays continuous there
    r, _ = rest_frame(_bone(0, tail=(1.0, 0.01, 0.0)))
    _check_frame(r)


# -- Scene and file -----------------------------------------------------------------------------------


def test_scene_rig_is_typed():
    scene = Scene()
    assert scene.rig is None
    scene.rig = _chain()
    with pytest.raises(TypeError):
        scene.rig = {"bones": []}
    scene.rig = None


def test_rig_dict_round_trip_is_exact():
    rig = _chain().without_bone(BoneId(1))
    raw = json.loads(json.dumps(rig.to_dict()))
    assert raw == {
        "bone_id_counter": 3,
        "bones": [
            {"id": 0, "name": "Head", "parent": None, "head": [0.0, 1.0, 0.0], "tail": [0.0, 2.0, 0.0], "roll": 0.0},
            {"id": 2, "name": "Tongue", "parent": 0, "head": [0.0, 1.0, 0.2], "tail": [0.0, 1.0, 0.5], "roll": 0.3},
        ],
    }
    assert Rig.from_dict(raw) == rig


def test_scene_file_with_a_rig_is_version_7_and_round_trips():
    scene = Scene()
    scene.mesh = _grid(1)
    scene.rig = _chain()
    text = scene_to_json(scene)
    assert json.loads(text)["version"] == 7
    loaded = scene_from_json(text)
    assert loaded.rig == scene.rig and scene_to_json(loaded) == text
    scene.rig = Rig()  # an empty rig keeps its counter: still version 7
    assert scene_to_dict(scene)["version"] == 7 and scene_from_dict(scene_to_dict(scene)).rig == Rig()
    scene.rig = None
    assert scene_to_dict(scene)["version"] == 4


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda r: r["bones"][1].update(parent=7),
        lambda r: r["bones"][0].update(name=""),
        lambda r: r.update(bone_id_counter=1),
        lambda r: r["bones"][1].update(tail=r["bones"][1]["head"]),
        lambda r: r["bones"][0].update(id="0"),
        lambda r: r.pop("bones"),
        lambda r: r["bones"][2].update(parent=2),
    ],
)
def test_an_invalid_rig_makes_the_file_invalid(corrupt):
    scene = Scene()
    scene.rig = _chain()
    data = json.loads(json.dumps(scene_to_dict(scene)))
    corrupt(data["rig"])
    with pytest.raises((ValueError, TypeError)):
        scene_from_dict(data)


def test_versions_2_to_8_are_read():
    scene = Scene()
    scene.mesh = _grid(1)
    plain = scene_to_dict(scene)
    for version in (2, 3, 4, 5, 6, 7, 8):
        data = json.loads(json.dumps(plain))
        data["version"] = version
        loaded = scene_from_dict(data)
        assert loaded.rig is None and len(loaded.mesh.all_vertex_ids()) == 4
    scene.rig = _chain()
    lid = scene.mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    scene.mesh.set_layer_value(lid, scene.mesh.all_vertex_ids()[0], ((1, 0.75),))
    data = json.loads(json.dumps(scene_to_dict(scene)))
    assert data["version"] == 7
    loaded = scene_from_dict(data)
    assert loaded.rig == scene.rig and loaded.mesh.layer_items(lid) == scene.mesh.layer_items(lid)
    data["version"] = 9
    with pytest.raises(ValueError):
        scene_from_dict(data)


# -- Bone.hidden (outliner eye, 2026-11-07) ------------------------------------------------------------------------


def test_bone_hidden_defaults_false_is_validated_and_saved_only_when_set():
    import pytest

    from core.rig import Bone, Rig
    from core.ids import BoneId

    plain = Bone(BoneId(0), "A", None, (0, 0, 0), (0, 1, 0))
    assert plain.hidden is False and "hidden" not in plain.to_dict()
    with pytest.raises(TypeError):
        Bone(BoneId(0), "A", None, (0, 0, 0), (0, 1, 0), hidden=1)
    hidden = Bone(BoneId(0), "A", None, (0, 0, 0), (0, 1, 0), hidden=True)
    assert hidden.to_dict()["hidden"] is True and Bone.from_dict(hidden.to_dict()) == hidden
    raw = plain.to_dict()
    raw["hidden"] = "yes"
    with pytest.raises(ValueError):
        Bone.from_dict(raw)
    rig = Rig((plain,), 1)
    assert rig.with_hidden([BoneId(0)], True).hidden_ids() == {BoneId(0)}
    assert rig.with_hidden([BoneId(0)], True).with_name(BoneId(0), "B").bone(BoneId(0)).hidden
    with pytest.raises(KeyError):
        rig.with_hidden([BoneId(5)], True)
