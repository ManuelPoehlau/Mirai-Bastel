"""AD-039 §10 (S7): `LookMaps`, `LookMaterial.maps` and scene format v16 (CORE_V1_FREEZE §7.1 2026-11-24, Manu
„Map-Pfade“ on Q-P3-2, „S7 jetzt vorziehen“) - contract tests (Core part).

Pinned here: the value rules, a material without maps is written exactly as before (the v15 text, the same version),
v16 only with maps and v15 again without them, a "maps" key below 16 and any invalid map group refuse the file, 18 is
the first unknown version (17: the region materials, AD-039 §9).
"""

from __future__ import annotations

import json

import pytest

import tests._bootstrap  # noqa: F401

from core import LookMaps, LookMaterial, Mesh, Scene
from core.scene import LOOK_MAP_FIELDS, LOOK_NORMAL_STRENGTH_MAX
from core.serialization import (LOOK_FORMAT_VERSION, LOOK_MAPS_FORMAT_VERSION, scene_from_dict, scene_from_json,
                                scene_to_dict, scene_to_json)


def _look(**changes) -> LookMaterial:
    values = dict(preset="Creature Skin", base_color=(0.62, 0.52, 0.44), roughness=0.5, specular=0.35, wrap=0.3,
                  wrap_tint=(1.0, 0.65, 0.5), backscatter=0.15, backscatter_color=(1.0, 0.45, 0.3))
    values.update(changes)
    return LookMaterial(**values)


MAPS = LookMaps(roughness="maps/rough.png", normal="maps/normal.png", normal_strength=0.8)


# -- the values ------------------------------------------------------------------------------------------------------


def test_maps_keep_their_values_and_have_the_documented_defaults():
    assert LOOK_MAP_FIELDS == ("roughness", "normal", "translucency") and LOOK_NORMAL_STRENGTH_MAX == 2.0
    maps = LookMaps(normal="n.png")
    assert (maps.roughness, maps.normal, maps.translucency, maps.normal_strength, maps.normal_green_down) == (
        None, "n.png", None, 1.0, False)
    assert maps.to_dict() == {"normal": "n.png", "normal_strength": 1.0, "normal_green_down": False}
    assert LookMaps.from_dict(maps.to_dict()) == maps
    full = LookMaps("r.png", "n.png", "t.png", 2, True)
    assert full.normal_strength == 2.0 and isinstance(full.normal_strength, float)
    assert LookMaps.from_dict(full.to_dict()) == full
    assert _look().maps is None and "maps" not in _look().to_dict()  # absent = none: the v15 dict
    look = _look(maps=MAPS)
    assert look.to_dict()["maps"] == MAPS.to_dict() and LookMaterial.from_dict(look.to_dict()) == look


@pytest.mark.parametrize("values", [
    {}, {"roughness": None, "normal": None, "translucency": None},  # no map at all: maps None instead
    {"normal": ""}, {"normal": "  "}, {"normal": 3}, {"roughness": "a\0b"},
    {"normal": "n.png", "normal_strength": -0.1}, {"normal": "n.png", "normal_strength": 2.5},
    {"normal": "n.png", "normal_strength": float("nan")}, {"normal": "n.png", "normal_strength": True},
    {"normal": "n.png", "normal_strength": "1"}, {"normal": "n.png", "normal_green_down": 1},
])
def test_invalid_maps_are_refused(values):
    with pytest.raises(ValueError):
        LookMaps(**values)


@pytest.mark.parametrize("raw", [
    {"normal": "n.png"},  # the values are required
    {"normal": "n.png", "normal_strength": 1.0},
    {**MAPS.to_dict(), "albedo": "a.png"},
    {"normal_strength": 1.0, "normal_green_down": False},  # no map
    "maps",
])
def test_from_dict_takes_the_documented_keys(raw):
    with pytest.raises(ValueError):
        LookMaps.from_dict(raw)


def test_a_material_takes_only_maps_or_none():
    for wrong in (MAPS.to_dict(), "n.png", ()):
        with pytest.raises(ValueError):
            _look(maps=wrong)
    raw = _look().to_dict() | {"maps": None}
    with pytest.raises(ValueError):  # absent, not null
        LookMaterial.from_dict(raw)


# -- the file: v16 only with maps -------------------------------------------------------------------------------------


def _scene(look: LookMaterial) -> Scene:
    scene = Scene()
    scene.mesh.add_vertex((0.0, 0.0, 0.0))
    scene.edit_object.look = look
    return scene


def test_maps_write_v16_and_round_trip_to_the_same_text():
    scene = _scene(_look(maps=MAPS))
    text = scene_to_json(scene)
    data = json.loads(text)
    assert data["version"] == LOOK_MAPS_FORMAT_VERSION == 16
    assert data["objects"][0]["look"]["maps"] == {"roughness": "maps/rough.png", "normal": "maps/normal.png",
                                                   "normal_strength": 0.8, "normal_green_down": False}
    loaded = scene_from_json(text)
    assert loaded.edit_object.look == scene.edit_object.look
    assert scene_to_json(loaded) == text


def test_without_maps_the_v15_text_again():
    plain = scene_to_json(_scene(_look()))
    assert json.loads(plain)["version"] == LOOK_FORMAT_VERSION
    scene = _scene(_look(maps=MAPS))
    scene.edit_object.look = _look()
    assert scene_to_json(scene) == plain


def test_maps_below_version_16_refuse_the_file_and_18_is_unknown():
    data = json.loads(scene_to_json(_scene(_look(maps=MAPS))))
    data["version"] = LOOK_FORMAT_VERSION
    with pytest.raises(ValueError):
        scene_from_dict(data)
    data["version"] = 18  # 17: the region materials (AD-039 §9)
    with pytest.raises(ValueError):
        scene_from_dict(data)
    plain = json.loads(scene_to_json(_scene(_look())))
    plain["version"] = LOOK_MAPS_FORMAT_VERSION  # a v16 file may hold looks without maps
    assert scene_from_dict(plain).edit_object.look == _look()


@pytest.mark.parametrize("edit", [
    lambda raw: raw.update(normal_strength=3.0),
    lambda raw: raw.update(normal=""),
    lambda raw: raw.pop("normal_green_down"),
    lambda raw: raw.update(extra=True),
    lambda raw: (raw.pop("roughness"), raw.pop("normal")),
])
def test_invalid_maps_refuse_the_file(edit):
    data = json.loads(scene_to_json(_scene(_look(maps=MAPS))))
    edit(data["objects"][0]["look"]["maps"])
    with pytest.raises(ValueError):
        scene_from_dict(data)


def test_objects_keep_their_maps_in_a_scene_of_several():
    scene = Scene()
    head = scene.add_object(Mesh(), name="head")
    teeth = scene.add_object(Mesh(), name="teeth")
    head.look = _look(maps=LookMaps(translucency="t.png"))
    teeth.look = _look(preset="Zähne")
    loaded = scene_from_json(scene_to_json(scene))
    looks = {o.name: o.look for o in loaded.objects.values()}
    assert looks["head"].maps == LookMaps(translucency="t.png") and looks["teeth"].maps is None
