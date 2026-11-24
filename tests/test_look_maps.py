"""AD-039 §10 (S7): the LookDev material's image maps, application part, headless (Manu 2026-11-24, Q-P3-2
„Map-Pfade“).

Pinned here: a map is loaded, replaced and removed on the material targets as one Undo step each (`set_lookdev_map`),
refused with the reason for a missing file, an unknown format or an image above `look_maps.MAX_SIZE`; the last map
removed returns the material to its v15 shape; a preset pick keeps the maps; the normal map's strength and green
direction go through `set_lookdev_material_values` and the preview (never "angepasst"); the LookDraw carries the
drawable maps only on an object with UVs; save copies each map into `<scene>_textures/` and writes it scene-relative,
load resolves it; the maps travel with Duplicate (the look is one value). Core contract: `test_look_maps_format.py`.
"""

from __future__ import annotations

import json
import struct

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from core import LookMaps
from core.serialization import LOOK_FORMAT_VERSION, LOOK_MAPS_FORMAT_VERSION
from gui import lookdev_model as gm
from mirai import look_maps
from mirai import lookdev_material as lm
from mirai.application import Application
from mirai.interaction import commands
from mirai.iris_import import encode_png


def _uvs(mesh) -> None:
    for i, fid in enumerate(mesh.all_face_ids()):
        mesh.set_face_uvs(fid, [(i / 6 + du / 6, dv) for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1))])


def _app(uvs: bool = True) -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    if uvs:
        _uvs(app.scene.mesh)
    app.frame_scene()
    return app


@pytest.fixture
def app() -> Application:
    return _app()


def _png(path, size: int = 8, value: int = 128):
    image = np.full((size, size, 4), value, np.uint8)
    image[..., 3] = 255
    path.write_bytes(encode_png(image))
    return path


def _png_header(path, width: int, height: int):
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + bytes(9))
    return path


def _undo(app):
    app.dispatch_command(commands.UNDO)
    app.update_viewport(0.0)


def _redo(app):
    app.dispatch_command(commands.REDO)
    app.update_viewport(0.0)


# -- load, replace, remove: one Undo step each ------------------------------------------------------------------------


def test_load_replace_remove_with_undo(app, tmp_path):
    rough, other = _png(tmp_path / "rough.png"), _png(tmp_path / "rough2.png", value=200)
    obj = app.scene.edit_object
    app.open_lookdev()
    history = len(app.history)
    assert app.set_lookdev_map("roughness", rough) and len(app.history) == history + 1
    assert obj.look.maps == LookMaps(roughness=str(rough)) and obj.look.preset == lm.NEUTRAL  # Neutral with the map
    assert not obj.look.adjusted and "Rauheit-Map rough.png" in app.status_message
    assert app.set_lookdev_map("roughness", other) and obj.look.maps.roughness == str(other)
    assert app.set_lookdev_map("normal", rough) and obj.look.maps.normal == str(rough)
    assert app.set_lookdev_map("roughness", None) and obj.look.maps == LookMaps(normal=str(rough))
    assert app.set_lookdev_map("normal", None) and obj.look is not None and obj.look.maps is None
    assert len(app.history) == history + 5
    assert not app.set_lookdev_map("normal", None)  # nothing to remove: no step
    _undo(app)
    assert obj.look.maps == LookMaps(normal=str(rough))
    _undo(app)
    _undo(app)
    assert obj.look.maps.roughness == str(other)
    _redo(app)
    assert obj.look.maps.normal == str(rough)


def test_a_map_is_refused_with_the_reason(app, tmp_path):
    app.open_lookdev()
    obj = app.scene.edit_object
    assert not app.set_lookdev_map("roughness", tmp_path / "missing.png") and "nicht gefunden" in app.status_message
    text = tmp_path / "note.txt"
    text.write_text("no image")
    assert not app.set_lookdev_map("normal", text) and "unbekanntes Format" in app.status_message
    big = _png_header(tmp_path / "big.png", 4097, 16)  # only the header is read
    assert not app.set_lookdev_map("translucency", big) and "zu groß" in app.status_message
    assert not app.set_lookdev_map("albedo", _png(tmp_path / "a.png")) and "one of" in app.status_message
    assert obj.look is None
    assert look_maps.check(_png(tmp_path / "b.png")).usable
    result = look_maps.check(_png_header(tmp_path / "large.png", 4096, 4096))
    assert result.usable and "Grafikspeicher" in result.note


def test_a_preset_keeps_the_maps_and_reset_drops_them(app, tmp_path):
    rough = _png(tmp_path / "rough.png")
    obj = app.scene.edit_object
    app.open_lookdev()
    assert app.set_lookdev_map("roughness", rough)
    assert app.set_lookdev_material("Creature Skin") and obj.look.preset == "Creature Skin"
    assert obj.look.maps == LookMaps(roughness=str(rough))
    assert app.set_lookdev_material_values(roughness=0.3) and obj.look.maps.roughness == str(rough)
    assert app.reset_lookdev_material() and obj.look is None
    _undo(app)
    assert obj.look.maps.roughness == str(rough)


def test_the_normal_values_preview_and_commit_without_marking_adjusted(app, tmp_path):
    normal = _png(tmp_path / "n.png")
    obj = app.scene.edit_object
    app.open_lookdev()
    assert app.set_lookdev_material("Organisch") and app.set_lookdev_map("normal", normal)
    history = len(app.history)
    edit = gm.MaterialEdit()
    assert edit.hold(app, normal_strength=0.4)
    assert obj.look.maps.normal_strength == 1.0  # a preview: the document is unchanged
    assert app.lookdev.look_draw(obj).normal_strength == 0.4
    assert edit.release(app) and obj.look.maps.normal_strength == 0.4 and len(app.history) == history + 1
    assert app.set_lookdev_material_values(normal_green_down=True) and obj.look.maps.normal_green_down
    assert not obj.look.adjusted
    assert not app.set_lookdev_material_values(normal_strength=3.0) and "normal_strength" in app.status_message
    # without maps the map values change nothing
    assert app.set_lookdev_map("normal", None) and obj.look.maps is None
    assert not app.set_lookdev_material_values(normal_strength=0.5)


def test_with_map_and_with_values_rules():
    base = lm.PRESETS["Organisch"]
    assert lm.with_map(base, "normal", None) is base
    one = lm.with_map(base, "normal", "/n.png")
    assert one.maps == LookMaps(normal="/n.png") and not one.adjusted
    assert lm.with_map(one, "normal", None).maps is None
    assert lm.with_values(base, normal_strength=0.5) == base  # no maps: nothing to change
    assert lm.with_values(one, normal_strength=0.5).maps.normal_strength == 0.5
    assert lm.keep_maps(lm.PRESETS["Zähne"], one).maps == one.maps
    assert lm.keep_maps(lm.PRESETS["Zähne"], None) == lm.PRESETS["Zähne"]
    with pytest.raises(ValueError):
        lm.with_map(base, "albedo", "/a.png")


# -- the LookDraw ------------------------------------------------------------------------------------------------------


def test_the_look_draw_carries_the_drawable_maps_on_an_object_with_uvs(app, tmp_path):
    rough, normal = _png(tmp_path / "rough.png"), _png(tmp_path / "n.png")
    obj = app.scene.edit_object
    app.open_lookdev()
    plain = app.lookdev.look_draw(obj)
    assert plain.map_paths() == {} and not plain.needs_uvs
    app.set_lookdev_map("roughness", rough)
    app.set_lookdev_map("normal", normal)
    app.set_lookdev_material_values(normal_green_down=True)
    draw = app.lookdev.look_draw(obj)
    assert draw.map_paths() == {"roughness": str(rough), "normal": str(normal)} and draw.needs_uvs
    assert draw.normal_green_down and draw.map_uniforms()["u_normal_green"] == -1.0
    normal.unlink()  # a missing file keeps its path in the material and draws without that map
    assert app.lookdev.look_draw(obj).map_paths() == {"roughness": str(rough)}
    assert obj.look.maps.normal == str(normal)
    row = gm.state(app).material
    assert [(r.kind, r.label) for r in row.maps] == [("roughness", "Rauheit-Map"), ("normal", "Normal-Map"),
                                                    ("translucency", "Durchscheinen-Map")]
    assert row.maps[0].text == "rough.png" and "nicht gefunden" in row.maps[1].text and row.maps[2].text == "keine"
    assert row.normal_green_down and not row.no_uvs


def test_without_uvs_the_map_is_kept_but_not_drawn(tmp_path):
    app = _app(uvs=False)
    obj = app.scene.edit_object
    app.open_lookdev()
    assert app.set_lookdev_map("roughness", _png(tmp_path / "r.png"))
    assert "ohne UVs nicht sichtbar" in app.status_message and obj.look.maps.roughness is not None
    assert app.lookdev.look_draw(obj).map_paths() == {}
    assert gm.state(app).material.no_uvs


def test_load_map_from_the_panel_text(app, tmp_path):
    path = _png(tmp_path / "t.png")
    app.open_lookdev()
    assert not gm.load_map(app, "translucency", "  ") and "Pfad" in app.status_message
    assert gm.load_map(app, "translucency", f' "{path}" ')
    assert app.scene.edit_object.look.maps.translucency == str(path)
    assert gm.load_map(app, "translucency", None) and app.scene.edit_object.look.maps is None


# -- save and load --------------------------------------------------------------------------------------------------


def test_save_copies_the_maps_beside_the_scene_and_load_resolves_them(app, tmp_path):
    source = tmp_path / "outside"
    source.mkdir()
    rough = _png(source / "rough.png")
    obj = app.scene.edit_object
    app.open_lookdev()
    app.set_lookdev_map("roughness", rough)
    app.set_lookdev_map("translucency", rough)  # the same image: one copy
    scene_dir = tmp_path / "scene"
    path = scene_dir / "head.mirai.json"
    assert app.save_scene_file(path), app.status_message
    assert "LookDev map copied to head_textures/" in app.status_message
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == LOOK_MAPS_FORMAT_VERSION
    maps = data["objects"][0]["look"]["maps"]
    assert maps["roughness"] == maps["translucency"] and maps["roughness"].startswith("head_textures/")
    copies = list((scene_dir / "head_textures").iterdir())
    assert len(copies) == 1 and copies[0].read_bytes() == rough.read_bytes()
    assert obj.look.maps.roughness == str(copies[0])  # the material points at the copy from now on
    assert rough.exists()  # nothing is deleted
    fresh = _app()
    fresh.load_scene("file", scene_path=path)
    assert fresh.scene.edit_object.look.maps.roughness == str(copies[0])
    # saved again: already beside the scene, no second copy
    assert fresh.save_scene_file(path) and len(list((scene_dir / "head_textures").iterdir())) == 1
    # the last map removed: the v15 file again
    fresh.open_lookdev()
    fresh.set_lookdev_map("roughness", None)
    fresh.set_lookdev_map("translucency", None)
    assert fresh.save_scene_file(path)
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == LOOK_FORMAT_VERSION


def test_a_missing_map_keeps_its_path_on_save(app, tmp_path):
    rough = _png(tmp_path / "rough.png")
    app.open_lookdev()
    app.set_lookdev_map("roughness", rough)
    rough.unlink()
    path = tmp_path / "scene" / "x.mirai.json"
    assert app.save_scene_file(path) and "image not found, path kept: rough.png" in app.status_message
    assert json.loads(path.read_text(encoding="utf-8"))["objects"][0]["look"]["maps"]["roughness"] == str(rough)


def test_duplicate_carries_the_maps(app, tmp_path):
    app.open_lookdev()
    app.set_lookdev_map("normal", _png(tmp_path / "n.png"))
    source = app.scene.edit_object
    app.close_lookdev()
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.select_objects([source.id])
    before = set(app.scene.objects)
    assert app.duplicate_objects(), app.status_message
    (copy_id,) = set(app.scene.objects) - before
    assert app.scene.objects[copy_id].look.maps == source.look.maps
