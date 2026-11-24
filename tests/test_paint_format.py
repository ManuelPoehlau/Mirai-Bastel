"""AD-037 Phase 1d: `PaintLayer`, `PaintStack`, `SceneObject.paint` and scene format v14 (CORE_V1_FREEZE §7.1
2026-11-18, Manu P-3 "Go") - contract tests.

The values are data only; pixels, painting and stroke Undo live in `src/mirai` (`mirai.paint`). Pinned here: the value
rules, a scene without paint is written exactly as before (same text, same version), v14 only with paint and the older
version again without it, versions below 14 read with `paint = None`, a "paint" key below 14 and any invalid stack refuse
the file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh, ObjectId, PaintLayer, PaintStack, Scene, SceneObject
from core.scene import PAINT_BLEND_MODES, PAINT_MAX_SIZE
from core.serialization import (BONE_LINK_FORMAT_VERSION, EYE_SCLERA_FORMAT_VERSION, FORMAT_VERSION,
                                PAINT_FORMAT_VERSION, scene_from_dict, scene_from_json, scene_to_dict, scene_to_json)

GOLLUM = Path(__file__).resolve().parents[1] / "scenes" / "Gollum_Head_rigging_test.mirai.json"


def _core_text(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("view", None)
    return json.dumps(data, indent=2)


def _stack(**changes) -> PaintStack:
    values = dict(width=2048, height=2048, layers=(PaintLayer("Paint 1", "head_textures/paint_ab12cd34ef.png"),))
    values.update(changes)
    return PaintStack(**values)


# -- the values ------------------------------------------------------------------------------------------------------


def test_a_layer_keeps_its_values_and_has_the_documented_defaults():
    layer = PaintLayer("Haut", None)
    assert (layer.image, layer.opacity, layer.visible, layer.blend) == (None, 1.0, True, "normal")
    other = PaintLayer("Adern", "maps/a.png", opacity=0.25, visible=False)
    assert other.to_dict() == {"name": "Adern", "image": "maps/a.png", "opacity": 0.25, "visible": False,
                               "blend": "normal"}
    assert PaintLayer.from_dict(other.to_dict()) == other
    assert PAINT_BLEND_MODES == ("normal", "multiply")


@pytest.mark.parametrize("changes", [
    {"name": ""}, {"name": "  "}, {"name": 3}, {"name": "a\0b"},
    {"image": ""}, {"image": "a\0.png"}, {"image": 5},
    {"opacity": -0.1}, {"opacity": 1.5}, {"opacity": float("nan")}, {"opacity": True}, {"opacity": "1"},
    {"visible": 1}, {"visible": None},
    {"blend": "screen"}, {"blend": None},
])
def test_an_invalid_layer_is_refused(changes):
    values = dict(name="Paint", image=None)
    values.update(changes)
    with pytest.raises(ValueError):
        PaintLayer(**values)


@pytest.mark.parametrize("changes", [
    {"width": 0}, {"height": -1}, {"width": PAINT_MAX_SIZE + 1}, {"width": 2048.0}, {"height": True},
    {"layers": ()}, {"layers": ("Paint",)},
    {"layers": (PaintLayer("A", None), PaintLayer("A", "x.png"))},
])
def test_an_invalid_stack_is_refused(changes):
    with pytest.raises(ValueError):
        _stack(**changes)


def test_a_stack_holds_its_layers_as_a_tuple_bottom_to_top():
    stack = _stack(layers=[PaintLayer("unten", None), PaintLayer("oben", None)])
    assert isinstance(stack.layers, tuple) and [layer.name for layer in stack.layers] == ["unten", "oben"]
    assert PaintStack.from_dict(stack.to_dict()) == stack


@pytest.mark.parametrize("raw", [
    {"width": 4, "height": 4},
    {"width": 4, "height": 4, "layers": [], "extra": 1},
    {"width": 4, "height": 4, "layers": {"name": "a"}},
    {"width": 4, "height": 4, "layers": [{"name": "a", "image": None}]},
    "paint",
])
def test_from_dict_takes_exactly_the_field_names(raw):
    with pytest.raises(ValueError):
        PaintStack.from_dict(raw)


def test_paint_defaults_to_none_and_takes_only_a_stack():
    assert SceneObject(ObjectId(0), Mesh()).paint is None
    stack = _stack()
    assert SceneObject(ObjectId(0), Mesh(), paint=stack).paint is stack
    for wrong in ({"width": 4}, "paint", PaintLayer("a", None)):
        with pytest.raises(TypeError):
            SceneObject(ObjectId(0), Mesh(), paint=wrong)


# -- no paint: unchanged ---------------------------------------------------------------------------------------------


def test_a_scene_without_paint_is_written_exactly_as_before():
    expected = _core_text(GOLLUM)
    scene = scene_from_json(expected)
    assert all(obj.paint is None for obj in scene.objects.values())
    written = scene_to_json(scene)
    assert written == expected
    assert json.loads(written)["version"] == EYE_SCLERA_FORMAT_VERSION
    plain = scene_to_dict(Scene())
    assert plain["version"] == FORMAT_VERSION and all("paint" not in o for o in plain["objects"])


# -- paint: v14 ------------------------------------------------------------------------------------------------------


def test_paint_writes_v14_and_round_trips_to_the_same_text():
    scene = Scene()
    obj = scene.add_object(Mesh(), name="head")
    obj.paint = _stack(layers=(PaintLayer("Basis", "t/a.png", opacity=0.5), PaintLayer("Leer", None, visible=False)))
    text = scene_to_json(scene)
    data = json.loads(text)
    assert data["version"] == PAINT_FORMAT_VERSION == 14
    assert [o.get("paint") is not None for o in data["objects"]] == [False, True]
    loaded = scene_from_json(text)
    assert next(o for o in loaded.objects.values() if o.name == "head").paint == obj.paint
    assert scene_to_json(loaded) == text


def test_the_version_follows_the_content():
    scene = scene_from_json(_core_text(GOLLUM))
    head = next(obj for obj in scene.objects.values() if obj.texture is not None and obj.eye is None)
    head.paint = _stack()
    assert scene_to_dict(scene)["version"] == PAINT_FORMAT_VERSION
    loaded = scene_from_dict(json.loads(json.dumps(scene_to_dict(scene))))
    assert [o.paint for o in loaded.objects.values() if o.paint is not None] == [head.paint]
    head.paint = None
    assert scene_to_dict(scene)["version"] == EYE_SCLERA_FORMAT_VERSION  # the older format again
    assert scene_to_json(scene) == _core_text(GOLLUM)
    assert PAINT_FORMAT_VERSION > BONE_LINK_FORMAT_VERSION


# -- older versions and invalid files --------------------------------------------------------------------------------


def test_versions_2_to_13_read_without_paint_and_18_is_refused():
    plain = scene_to_dict(Scene())
    for version in range(2, 18):  # 15: LookDev material (AD-038 §18), 16: its maps (AD-039 §10), 17: regions (§9)
        data = json.loads(json.dumps(plain))
        data["version"] = version
        assert all(obj.paint is None for obj in scene_from_dict(data).objects.values())
    data = json.loads(json.dumps(plain))
    data["version"] = 18  # the first unknown
    with pytest.raises(ValueError):
        scene_from_dict(data)


def _painted_dict() -> dict:
    scene = Scene()
    scene.mesh.add_vertex((0.0, 0.0, 0.0))
    scene.edit_object.paint = _stack()
    return json.loads(json.dumps(scene_to_dict(scene)))


def test_paint_below_version_14_refuses_the_file():
    data = _painted_dict()
    data["version"] = BONE_LINK_FORMAT_VERSION
    with pytest.raises(ValueError):
        scene_from_dict(data)


@pytest.mark.parametrize("edit", [
    lambda p: p.update(width=0),
    lambda p: p.update(layers=[]),
    lambda p: p["layers"][0].update(opacity=2.0),
    lambda p: p["layers"][0].update(blend="screen"),
    lambda p: p["layers"][0].pop("visible"),
    lambda p: p.update(extra=True),
])
def test_an_invalid_stack_refuses_the_file(edit):
    data = _painted_dict()
    edit(data["objects"][0]["paint"])
    with pytest.raises(ValueError):
        scene_from_dict(data)
