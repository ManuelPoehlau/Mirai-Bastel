"""AD-039 §9 (S6): `RegionLook`, `SceneObject.look_regions` and scene format v17 (CORE_V1_FREEZE §7.1 2026-11-24, Manu
LD-D8 „A, Regionen wie vorgeschlagen“) - contract tests (Core part).

Pinned here: the value rules (a `RegionLook` is a region name and a `LookMaterial`; at most `LOOK_REGIONS_MAX` per
object, names unique, the order kept), an object without region materials is written exactly as before (the v16 / v15
text, the same version), v17 only with them and the older text again without them, a "look_regions" key below 17, an
empty list and any invalid entry refuse the file, 18 is the first unknown version.
"""

from __future__ import annotations

import json

import pytest

import tests._bootstrap  # noqa: F401

from core import LookMaps, LookMaterial, Mesh, RegionLook, Scene, SceneObject
from core.ids import ObjectId
from core.scene import LOOK_REGIONS_MAX
from core.serialization import (LOOK_FORMAT_VERSION, LOOK_MAPS_FORMAT_VERSION, LOOK_REGIONS_FORMAT_VERSION,
                                scene_from_dict, scene_from_json, scene_to_dict, scene_to_json)


def _look(**changes) -> LookMaterial:
    values = dict(preset="Creature Skin", base_color=(0.62, 0.52, 0.44), roughness=0.5, specular=0.35, wrap=0.3,
                  wrap_tint=(1.0, 0.65, 0.5), backscatter=0.15, backscatter_color=(1.0, 0.45, 0.3))
    values.update(changes)
    return LookMaterial(**values)


MOUTH = RegionLook("Mouth", _look(preset="Wet Skin", roughness=0.25, specular=0.6))
LIPS = RegionLook("Upper Lip", _look(preset="Lips", base_color=(0.7, 0.4, 0.4)))


def _scene(look: LookMaterial | None = None, regions: tuple = ()) -> Scene:
    scene = Scene()
    scene.mesh.add_vertex((0.0, 0.0, 0.0))
    scene.edit_object.look = look
    scene.edit_object.look_regions = regions
    return scene


# -- the values ------------------------------------------------------------------------------------------------------


def test_a_region_look_is_a_name_and_a_material():
    assert LOOK_REGIONS_MAX == 4 and LOOK_REGIONS_FORMAT_VERSION == 17
    assert MOUTH.to_dict() == {"region": "Mouth", "look": MOUTH.look.to_dict()}
    assert RegionLook.from_dict(MOUTH.to_dict()) == MOUTH
    with_maps = RegionLook("Mouth", _look(maps=LookMaps(normal="n.png")))  # a region's look may carry maps (data)
    assert RegionLook.from_dict(json.loads(json.dumps(with_maps.to_dict()))) == with_maps


@pytest.mark.parametrize("region, look", [
    ("", _look()), ("  ", _look()), (3, _look()), ("a\0b", _look()), ("Mouth", None), ("Mouth", {"preset": "x"}),
])
def test_invalid_region_looks_are_refused(region, look):
    with pytest.raises(ValueError):
        RegionLook(region, look)


@pytest.mark.parametrize("raw", [
    None, [], {"region": "Mouth"}, {"look": MOUTH.look.to_dict()},
    {"region": "Mouth", "look": MOUTH.look.to_dict(), "faces": [1]},
    {"region": "Mouth", "look": None}, {"region": None, "look": MOUTH.look.to_dict()},
])
def test_invalid_region_look_dicts_are_refused(raw):
    with pytest.raises(ValueError):
        RegionLook.from_dict(raw)


def test_an_object_holds_at_most_four_unique_entries_in_order():
    obj = SceneObject(ObjectId(7), Mesh())
    assert obj.look_regions == ()
    entries = tuple(RegionLook(f"Group {i}", _look()) for i in range(LOOK_REGIONS_MAX))
    obj.look_regions = entries
    assert obj.look_regions == entries  # the order is the meaning (the later entry wins on overlap)
    obj.look_regions = entries[::-1]
    assert obj.look_regions == entries[::-1]
    with pytest.raises(ValueError):
        obj.look_regions = entries + (RegionLook("Group 9", _look()),)
    with pytest.raises(ValueError):
        obj.look_regions = (MOUTH, RegionLook("Mouth", _look()))
    with pytest.raises(TypeError):
        obj.look_regions = [MOUTH]  # a tuple, never a list (the value is immutable like `look`)
    with pytest.raises(TypeError):
        obj.look_regions = (MOUTH.to_dict(),)
    with pytest.raises(TypeError):
        SceneObject(ObjectId(8), Mesh(), look_regions=None)
    assert obj.look_regions == entries[::-1]  # a refused value changes nothing
    assert SceneObject(ObjectId(9), Mesh(), look_regions=(MOUTH,)).look_regions == (MOUTH,)


# -- the format ------------------------------------------------------------------------------------------------------


def test_without_region_materials_the_text_and_version_stay_as_before():
    for look, version in ((None, None), (_look(), LOOK_FORMAT_VERSION),
                          (_look(maps=LookMaps(normal="n.png")), LOOK_MAPS_FORMAT_VERSION)):
        text = scene_to_json(_scene(look))
        assert "look_regions" not in text
        if version is not None:
            assert json.loads(text)["version"] == version
        with_regions = _scene(look, (MOUTH,))
        assert json.loads(scene_to_json(with_regions))["version"] == LOOK_REGIONS_FORMAT_VERSION
        with_regions.edit_object.look_regions = ()
        assert scene_to_json(with_regions) == text  # removed again = the older text, byte for byte


def test_v17_round_trips_on_the_json_text_with_the_order():
    scene = _scene(_look(), (LIPS, MOUTH))
    text = scene_to_json(scene)
    data = json.loads(text)
    assert data["version"] == 17
    raw = next(o for o in data["objects"] if o["id"] == int(scene.edit_object_id))
    assert raw["look_regions"] == [LIPS.to_dict(), MOUTH.to_dict()]
    loaded = scene_from_json(text)
    assert loaded.edit_object.look_regions == (LIPS, MOUTH)
    assert scene_to_json(loaded) == text
    # an object without a look of its own may still have region materials (the base draws Neutral)
    bare = scene_from_json(scene_to_json(_scene(None, (MOUTH,))))
    assert bare.edit_object.look is None and bare.edit_object.look_regions == (MOUTH,)


def test_several_objects_keep_their_own_entries():
    scene = _scene(_look(), (MOUTH,))
    mesh = Mesh()
    mesh.add_vertex((1.0, 0.0, 0.0))
    other = scene.add_object(mesh)
    other.look_regions = (LIPS,)
    loaded = scene_from_json(scene_to_json(scene))
    assert loaded.edit_object.look_regions == (MOUTH,) and loaded.objects[other.id].look_regions == (LIPS,)
    third = [o for o in loaded.objects.values() if o.id not in (loaded.edit_object_id, other.id)]
    assert all(o.look_regions == () for o in third)


def test_region_materials_below_version_17_refuse_the_file_and_18_is_unknown():
    data = json.loads(scene_to_json(_scene(_look(), (MOUTH,))))
    for version in (LOOK_FORMAT_VERSION, LOOK_MAPS_FORMAT_VERSION):
        data["version"] = version
        with pytest.raises(ValueError):
            scene_from_dict(data)
    data["version"] = 18
    with pytest.raises(ValueError):
        scene_from_dict(data)
    plain = json.loads(scene_to_json(_scene(_look(maps=LookMaps(normal="n.png")))))
    plain["version"] = LOOK_REGIONS_FORMAT_VERSION  # a v17 file may hold objects without region materials
    loaded = scene_from_dict(plain)
    assert loaded.edit_object.look_regions == () and loaded.edit_object.look.maps.normal == "n.png"


@pytest.mark.parametrize("value", [
    [], None, {}, "Mouth", [None], [{"region": "Mouth"}],
    [MOUTH.to_dict(), MOUTH.to_dict()],  # names unique
    [RegionLook(f"G{i}", _look()).to_dict() for i in range(LOOK_REGIONS_MAX + 1)],  # at most four
    [{"region": "Mouth", "look": dict(MOUTH.look.to_dict(), roughness=2.0)}],  # an invalid material
])
def test_invalid_region_groups_refuse_the_file(value):
    data = json.loads(scene_to_json(_scene(_look(), (MOUTH,))))
    raw = next(o for o in data["objects"] if "look_regions" in o)
    raw["look_regions"] = value
    with pytest.raises((ValueError, TypeError)):
        scene_from_dict(data)


def test_the_dict_round_trip_matches_the_json_round_trip():
    scene = _scene(_look(), (MOUTH, LIPS))
    assert scene_from_dict(scene_to_dict(scene)).edit_object.look_regions == (MOUTH, LIPS)
