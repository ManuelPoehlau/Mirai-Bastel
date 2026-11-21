"""AD-038 §18 (LD-2): `LookMaterial`, `SceneObject.look` and scene format v15 (CORE_V1_FREEZE §7.1 2026-11-21, Manu
"LookDev LD-2 umsetzen") - contract tests (E17, Core part).

The values are data only; presets, the Neutral fallback, F0 and the drawing live in `src/mirai` / `src/viewport`.
Pinned here: the value rules, a scene without looks is written exactly as before (same text, same version), v15 only
with a look and the older version again without it, versions below 15 read with `look = None`, a "look" key below 15
and any invalid material refuse the file, 16 is the first unknown version.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import LookMaterial, Mesh, ObjectId, Scene, SceneObject
from core.scene import LOOK_ALBEDO_SOURCES
from core.serialization import (EYE_SCLERA_FORMAT_VERSION, FORMAT_VERSION, LOOK_FORMAT_VERSION, PAINT_FORMAT_VERSION,
                                scene_from_dict, scene_from_json, scene_to_dict, scene_to_json)

SCENES = Path(__file__).resolve().parents[1] / "scenes"
GOLLUM = SCENES / "Gollum_Head_rigging_test.mirai.json"  # v12, no paint
GOLLUM_PAINTED = SCENES / "Gollum_Head_05.mirai.json"  # v14, painted


def _core_text(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("view", None)
    return json.dumps(data, indent=2)


def _look(**changes) -> LookMaterial:
    values = dict(preset="Creature Skin", base_color=(0.62, 0.52, 0.44), albedo_source="texture", roughness=0.5,
                  specular=0.35, wrap=0.3, wrap_tint=(1.0, 0.65, 0.5), backscatter=0.15,
                  backscatter_color=(1.0, 0.45, 0.3))
    values.update(changes)
    return LookMaterial(**values)


# -- the values ------------------------------------------------------------------------------------------------------


def test_a_look_keeps_its_values_and_has_the_documented_defaults():
    look = LookMaterial("Neutral", (0.5, 0.5, 0.5))
    assert (look.albedo_source, look.roughness, look.specular, look.wrap, look.wrap_tint, look.backscatter,
            look.backscatter_color, look.adjusted) == ("texture", 0.6, 0.5, 0.0, (1.0, 1.0, 1.0), 0.0, (1.0, 1.0, 1.0),
                                                       False)
    assert LOOK_ALBEDO_SOURCES == ("texture", "color")
    skin = _look(adjusted=True)
    assert skin.to_dict() == {"preset": "Creature Skin", "base_color": [0.62, 0.52, 0.44], "albedo_source": "texture",
                              "roughness": 0.5, "specular": 0.35, "wrap": 0.3, "wrap_tint": [1.0, 0.65, 0.5],
                              "backscatter": 0.15, "backscatter_color": [1.0, 0.45, 0.3], "adjusted": True}
    assert LookMaterial.from_dict(skin.to_dict()) == skin
    assert isinstance(LookMaterial("x", [0, 1, 0]).base_color, tuple)  # a list is taken, stored as floats
    assert LookMaterial("x", [0, 1, 0]).base_color == (0.0, 1.0, 0.0)


@pytest.mark.parametrize("changes", [
    {"preset": ""}, {"preset": "  "}, {"preset": 3}, {"preset": None},
    {"base_color": (0.5, 0.5)}, {"base_color": (0.5, 0.5, 1.5)}, {"base_color": "red"}, {"base_color": (0.5, 0.5, True)},
    {"albedo_source": "map"}, {"albedo_source": None},
    {"roughness": -0.1}, {"roughness": 1.5}, {"roughness": float("nan")}, {"roughness": True}, {"roughness": "0.5"},
    {"specular": 2.0}, {"wrap": -1.0}, {"backscatter": float("inf")},
    {"wrap_tint": (1.0, 1.0, -0.1)}, {"backscatter_color": (1.0,)},
    {"adjusted": 1}, {"adjusted": None},
])
def test_an_invalid_look_is_refused(changes):
    with pytest.raises(ValueError):
        _look(**changes)


@pytest.mark.parametrize("raw", [
    {"preset": "x", "base_color": [0.5, 0.5, 0.5]},
    {**_look().to_dict(), "extra": 1},
    {**_look().to_dict(), "base_color": (0.5, 0.5, 0.5)},
    "look",
])
def test_from_dict_takes_exactly_the_field_names(raw):
    with pytest.raises(ValueError):
        LookMaterial.from_dict(raw)


def test_look_defaults_to_none_and_takes_only_a_look():
    assert SceneObject(ObjectId(0), Mesh()).look is None
    look = _look()
    assert SceneObject(ObjectId(0), Mesh(), look=look).look is look
    for wrong in (look.to_dict(), "Creature Skin", 0.5):
        with pytest.raises(TypeError):
            SceneObject(ObjectId(0), Mesh(), look=wrong)


# -- no look: unchanged ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path, version", [(GOLLUM, EYE_SCLERA_FORMAT_VERSION), (GOLLUM_PAINTED, PAINT_FORMAT_VERSION)])
def test_a_scene_without_looks_is_written_exactly_as_before(path, version):
    expected = _core_text(path)
    scene = scene_from_json(expected)
    assert all(obj.look is None for obj in scene.objects.values())
    written = scene_to_json(scene)
    assert written == expected and json.loads(written)["version"] == version
    plain = scene_to_dict(Scene())
    assert plain["version"] == FORMAT_VERSION and all("look" not in o for o in plain["objects"])


# -- a look: v15 -----------------------------------------------------------------------------------------------------


def test_a_look_writes_v15_and_round_trips_to_the_same_text():
    scene = Scene()
    obj = scene.add_object(Mesh(), name="teeth")
    obj.look = _look(preset="Zähne", albedo_source="color", adjusted=True)
    text = scene_to_json(scene)
    data = json.loads(text)
    assert data["version"] == LOOK_FORMAT_VERSION == 15
    assert [o.get("look") is not None for o in data["objects"]] == [False, True]
    loaded = scene_from_json(text)
    assert next(o for o in loaded.objects.values() if o.name == "teeth").look == obj.look
    assert scene_to_json(loaded) == text


def test_the_version_follows_the_content():
    expected = _core_text(GOLLUM_PAINTED)
    scene = scene_from_json(expected)
    head = next(obj for obj in scene.objects.values() if obj.paint is not None)
    head.look = _look()
    assert scene_to_dict(scene)["version"] == LOOK_FORMAT_VERSION  # above paint
    loaded = scene_from_dict(json.loads(json.dumps(scene_to_dict(scene))))
    assert [o.look for o in loaded.objects.values() if o.look is not None] == [head.look]
    head.look = None
    assert scene_to_dict(scene)["version"] == PAINT_FORMAT_VERSION  # the older format again
    assert scene_to_json(scene) == expected
    assert LOOK_FORMAT_VERSION > PAINT_FORMAT_VERSION


# -- older versions and invalid files --------------------------------------------------------------------------------


def test_versions_2_to_14_read_without_looks_and_16_is_refused():
    plain = scene_to_dict(Scene())
    for version in range(2, 16):
        data = json.loads(json.dumps(plain))
        data["version"] = version
        assert all(obj.look is None for obj in scene_from_dict(data).objects.values())
    data = json.loads(json.dumps(plain))
    data["version"] = 16  # the first unknown
    with pytest.raises(ValueError):
        scene_from_dict(data)


def _look_dict() -> dict:
    scene = Scene()
    scene.mesh.add_vertex((0.0, 0.0, 0.0))
    scene.edit_object.look = _look()
    return json.loads(json.dumps(scene_to_dict(scene)))


def test_a_look_below_version_15_refuses_the_file():
    data = _look_dict()
    data["version"] = PAINT_FORMAT_VERSION
    with pytest.raises(ValueError):
        scene_from_dict(data)


@pytest.mark.parametrize("edit", [
    lambda raw: raw.update(roughness=2.0),
    lambda raw: raw.update(albedo_source="map"),
    lambda raw: raw.update(base_color=[0.5, 0.5]),
    lambda raw: raw.pop("adjusted"),
    lambda raw: raw.update(extra=True),
    lambda raw: raw.update(preset=""),
])
def test_an_invalid_look_refuses_the_file(edit):
    data = _look_dict()
    edit(data["objects"][0]["look"])
    with pytest.raises(ValueError):
        scene_from_dict(data)
