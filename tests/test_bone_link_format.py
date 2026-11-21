"""AD-036 slice 1: `SceneObject.bone` and scene format v13 (CORE_V1_FREEZE §7.1 2026-11-18) - contract tests.

The field is data only; what following a bone means lives in `src/mirai` (slice 2). Pinned here: the field's type rules,
a scene without a link is written exactly as before (same text, same version), v13 only with a link and the older version
again without it, versions below 13 read with `bone = None`, invalid links refuse the file, a dead link loads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import BoneId, Mesh, ObjectId, Rig, Scene, SceneObject
from core.serialization import (BONE_LINK_FORMAT_VERSION, EYE_SCLERA_FORMAT_VERSION, FORMAT_VERSION,
                                RIG_FORMAT_VERSION, scene_from_dict, scene_from_json, scene_to_dict, scene_to_json)

GOLLUM = Path(__file__).resolve().parents[1] / "scenes" / "Gollum_Head_rigging_test.mirai.json"


def _core_text(path: Path) -> str:
    """The scene file without the app's `"view"` section (`mirai.view_state`, not the Core's)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("view", None)
    return json.dumps(data, indent=2)


def _rigged_scene() -> Scene:
    scene = Scene()
    rig, root = Rig().with_new_bone("Hals", (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    rig, _jaw = rig.with_new_bone("Kiefer", (0.0, 1.0, 0.0), (0.0, 1.0, 1.0), parent=root)
    scene.rig = rig
    scene.add_object(Mesh(), name="tooth")
    return scene


def _tooth(scene: Scene) -> SceneObject:
    return next(obj for obj in scene.objects.values() if obj.name == "tooth")


# -- the field -------------------------------------------------------------------------------------------------------


def test_bone_defaults_to_none_and_takes_only_a_bone_id():
    assert SceneObject(ObjectId(0), Mesh()).bone is None
    assert SceneObject(ObjectId(0), Mesh(), bone=BoneId(3)).bone == BoneId(3)
    for wrong in (3, ObjectId(3), "3", 3.0, True):
        with pytest.raises(TypeError):
            SceneObject(ObjectId(0), Mesh(), bone=wrong)
    with pytest.raises(ValueError):
        SceneObject(ObjectId(0), Mesh(), bone=BoneId(-1))


# -- no link: unchanged ----------------------------------------------------------------------------------------------


def test_a_scene_without_a_link_is_written_exactly_as_before():
    """The Gollum test scene (v12, no link) round-trips to the same text: no `"bone"` key, the same version."""
    expected = _core_text(GOLLUM)
    scene = scene_from_json(expected)
    assert all(obj.bone is None for obj in scene.objects.values())
    written = scene_to_json(scene)
    assert written == expected
    assert json.loads(written)["version"] == EYE_SCLERA_FORMAT_VERSION
    plain = scene_to_dict(Scene())
    assert plain["version"] == FORMAT_VERSION and all("bone" not in o for o in plain["objects"])


# -- a link: v13 -----------------------------------------------------------------------------------------------------


def test_a_link_writes_v13_and_round_trips_to_the_same_text():
    scene = _rigged_scene()
    _tooth(scene).bone = BoneId(1)
    text = scene_to_json(scene)
    data = json.loads(text)
    assert data["version"] == BONE_LINK_FORMAT_VERSION == 13
    assert [o.get("bone") for o in data["objects"]] == [None, 1]
    loaded = scene_from_json(text)
    assert _tooth(loaded).bone == BoneId(1) and isinstance(_tooth(loaded).bone, BoneId)
    assert scene_to_json(loaded) == text  # order-sensitive: the same file


def test_the_version_follows_the_content():
    scene = _rigged_scene()
    _tooth(scene).bone = BoneId(0)
    assert scene_to_dict(scene)["version"] == 13
    _tooth(scene).bone = None
    assert scene_to_dict(scene)["version"] == RIG_FORMAT_VERSION  # the older format again


def test_the_gollum_scene_with_links_is_v13_and_keeps_everything_else():
    scene = scene_from_json(_core_text(GOLLUM))
    rig = scene.rig
    ids = {b.name: b.id for b in rig.bones}
    by_name = {obj.name: obj for obj in scene.objects.values()}
    by_name["Auge_Links"].bone = ids["Auge_Links"]
    by_name["Zahn_1"].bone = ids["Kiefer"]
    data = scene_to_dict(scene)
    assert data["version"] == 13
    loaded = scene_from_dict(json.loads(json.dumps(data)))
    links = {obj.name: obj.bone for obj in loaded.objects.values() if obj.bone is not None}
    assert links == {"Auge_Links": ids["Auge_Links"], "Zahn_1": ids["Kiefer"]}
    for name in ("Auge_Links", "Zahn_1"):
        loaded_by_name = {obj.name: obj for obj in loaded.objects.values()}
        loaded_by_name[name].bone = None
    again = json.loads(json.dumps(scene_to_dict(loaded)))
    assert again["version"] == EYE_SCLERA_FORMAT_VERSION
    assert json.dumps(again, indent=2) == _core_text(GOLLUM)


# -- older versions --------------------------------------------------------------------------------------------------


def test_versions_2_to_12_read_without_links_and_16_is_refused():
    plain = scene_to_dict(Scene())
    for version in range(2, 14):
        data = json.loads(json.dumps(plain))
        data["version"] = version
        assert all(obj.bone is None for obj in scene_from_dict(data).objects.values())
    data = json.loads(json.dumps(plain))
    data["version"] = 16  # the first unknown (14: paint, AD-037; 15: LookDev material, AD-038 §18)
    with pytest.raises(ValueError):
        scene_from_dict(data)


# -- invalid links refuse the file -----------------------------------------------------------------------------------


def _linked_data(value) -> dict:
    scene = _rigged_scene()
    _tooth(scene).bone = BoneId(1)
    data = json.loads(json.dumps(scene_to_dict(scene)))
    data["objects"][1]["bone"] = value
    return data


@pytest.mark.parametrize("value", ["1", 1.0, 1.5, True, False, -1, [1], {"id": 1}])
def test_a_link_that_is_not_a_non_negative_int_refuses_the_file(value):
    with pytest.raises(ValueError):
        scene_from_dict(_linked_data(value))


def test_a_link_at_or_above_the_bone_counter_refuses_the_file():
    data = _linked_data(2)  # the counter is 2: bone 2 never existed
    with pytest.raises(ValueError):
        scene_from_dict(data)


def test_a_link_without_a_rig_refuses_the_file():
    data = _linked_data(0)
    data["rig"] = None
    with pytest.raises(ValueError):
        scene_from_dict(data)


def test_a_link_in_a_file_below_13_refuses_the_file():
    """No build writes one; reading it as "no link" would drop it on the next save (fail-closed)."""
    data = _linked_data(0)
    data["version"] = 12
    with pytest.raises(ValueError):
        scene_from_dict(data)


def test_a_null_link_reads_as_none():
    data = _linked_data(None)
    data["version"] = 12
    assert _tooth(scene_from_dict(data)).bone is None


def test_a_dead_link_loads_and_is_kept():
    """An id below the counter that the rig no longer has (a deleted bone): the object follows nothing (§4.1), and the
    file keeps the id (valid or dead, never wrong)."""
    scene = _rigged_scene()
    rig = scene.rig.without_bone(BoneId(1))
    scene.rig = rig
    _tooth(scene).bone = BoneId(1)
    loaded = scene_from_dict(json.loads(json.dumps(scene_to_dict(scene))))
    assert _tooth(loaded).bone == BoneId(1) and not loaded.rig.has_bone(BoneId(1))
