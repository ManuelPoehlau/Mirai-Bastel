"""Core contract of the per-object material (AD-024 §2/§3, CORE_V1_FREEZE §7.1): `ObjectMaterial`
(value, validation), `SceneObject.material` (default None), scene file v4 round trip and the
v2/v3 migration (no material = the app default look)."""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh, ObjectMaterial, ObjectState, Scene, SceneObject
from core.ids import ObjectId
from core.serialization import FORMAT_VERSION, scene_from_dict, scene_from_json, scene_to_dict, scene_to_json

RED = ObjectMaterial((0.8, 0.1, 0.1), specular=0.6, glossiness=0.9)


def test_material_is_a_validated_value():
    assert RED.base_color == (0.8, 0.1, 0.1) and RED.specular == 0.6 and RED.glossiness == 0.9
    assert RED == ObjectMaterial([0.8, 0.1, 0.1], 0.6, 0.9)
    assert hash(RED) == hash(ObjectMaterial((0.8, 0.1, 0.1), 0.6, 0.9))
    with pytest.raises(Exception):
        RED.specular = 0.1  # frozen


@pytest.mark.parametrize(
    "color, specular, glossiness",
    [
        ((1.2, 0.0, 0.0), 0.5, 0.5),
        ((0.0, -0.1, 0.0), 0.5, 0.5),
        ((0.0, 0.0), 0.5, 0.5),
        ((math.nan, 0.0, 0.0), 0.5, 0.5),
        ((0.5, 0.5, 0.5), 1.5, 0.5),
        ((0.5, 0.5, 0.5), 0.5, -0.1),
        ((0.5, 0.5, 0.5), math.inf, 0.5),
    ],
)
def test_invalid_values_are_refused(color, specular, glossiness):
    with pytest.raises(ValueError):
        ObjectMaterial(color, specular, glossiness)


def test_object_material_defaults_to_none_and_only_takes_a_material():
    scene = Scene()
    obj = scene.add_object(Mesh())
    assert obj.material is None
    obj.material = RED
    assert scene.objects[obj.id].material is RED
    with pytest.raises(TypeError):
        SceneObject(ObjectId(7), Mesh(), material=(1.0, 0.0, 0.0))


def _scene_with_material() -> tuple[Scene, SceneObject, SceneObject]:
    scene = Scene()
    plain = scene.edit_object
    red = scene.add_object(Mesh(), name="red", state=ObjectState.REFERENCE)
    red.material = RED
    return scene, plain, red


def test_file_v4_writes_and_reads_the_material():
    scene, plain, red = _scene_with_material()
    data = scene_to_dict(scene)
    assert FORMAT_VERSION == 4 and data["version"] == 4
    by_id = {o["id"]: o for o in data["objects"]}
    assert by_id[int(plain.id)]["material"] is None
    assert by_id[int(red.id)]["material"] == {"base_color": [0.8, 0.1, 0.1], "specular": 0.6, "glossiness": 0.9}
    restored = scene_from_json(scene_to_json(scene))
    assert restored.objects[plain.id].material is None
    assert restored.objects[red.id].material == RED


@pytest.mark.parametrize("version", [2, 3])
def test_older_files_load_with_the_default_material(version):
    scene, plain, red = _scene_with_material()
    data = scene_to_dict(scene)
    data["version"] = version
    for raw in data["objects"]:
        del raw["material"]
    if version == 2:
        del data["mirror_pairs"]
    restored = scene_from_dict(data)
    assert all(obj.material is None for obj in restored.objects.values())
    assert scene_to_dict(restored)["version"] == FORMAT_VERSION


def test_v4_without_the_material_key_reads_as_none():
    scene, plain, red = _scene_with_material()
    data = scene_to_dict(scene)
    for raw in data["objects"]:
        raw.pop("material")
    assert all(obj.material is None for obj in scene_from_dict(data).objects.values())


def test_an_invalid_material_makes_the_file_invalid():
    scene, plain, red = _scene_with_material()
    data = scene_to_dict(scene)
    data["objects"][1]["material"]["specular"] = 2.0
    with pytest.raises(ValueError):
        scene_from_dict(data)
