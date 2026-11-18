"""AD-035 M1 (Manu 2026-11-17): the sclera's colour map - headless. The Core contract (`EyeSpec.sclera_texture`, scene
format v12), the app path (one Undo step for assign / replace / remove, the iris and look untouched, duplicate / mirror
copy / scene load / morph twins carry it), storage beside the scene (relative paths, Save-As copies, never overwritten,
a missing file keeps its path), presets leave it alone, the size policy (`mirai.sclera_map`), the eye entry's map and
the selection tint rule S-4 (none on eyes while the Eye Lab is open). The GPU side: `tests/test_gl_eye_pass.py`."""

from __future__ import annotations

import dataclasses
import json
import struct
from pathlib import Path

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from core import EyeSpec, Scene, SelectionMode
from core.serialization import (EYE_FORMAT_VERSION, EYE_IRIS_FORMAT_VERSION, EYE_LOOK_FORMAT_VERSION,
                                EYE_SCLERA_FORMAT_VERSION, scene_from_dict, scene_to_dict)
from mirai import eye_presets, sclera_map
from mirai import texture_files as tf
from mirai.application import Application
from mirai.eye_object import DEFAULT_EYE, DEFAULT_IRIS, DEFAULT_LOOK, IRIS_PREFIX
from mirai.interaction.input import Input
from mirai.iris_import import encode_png
from mirai.scene_objects import SELECTED_TINT, SELECTED_TINT_SHARE, object_base_color

CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))
ASSETS = Path(__file__).resolve().parents[1] / "docs" / "research" / "eye_sclera_assets_2026-11-17"
SYNTHETIC = ASSETS / "synthetic_sclera_front_disc_1024.png"
TEMPLATE = ASSETS / "front_disc_template_1024.png"


def _png(path: Path, size: int = 16, colour=(200, 190, 180)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[..., :3] = colour
    rgba[..., 3] = 255
    path.write_bytes(encode_png(rgba))
    return path


def _png_header(path: Path, width: int, height: int) -> Path:
    """Only the PNG signature and IHDR: enough for the size policy (it never decodes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + b"\0\0\0\0")
    return path


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _depth(app) -> int:
    return len(app._selection_undo_stack)


def _entry(app, eye):
    return app.viewport._eye_entries[eye.id]


# -- the Core: EyeSpec.sclera_texture and the file format ---------------------------------------------------------------


def test_the_field_is_optional_validated_and_written_only_when_set():
    assert DEFAULT_EYE.sclera_texture is None and "sclera_texture" not in DEFAULT_EYE.to_dict()
    spec = dataclasses.replace(DEFAULT_EYE, sclera_texture="/maps/sclera L.png")
    assert spec.to_dict()["sclera_texture"] == "/maps/sclera L.png"
    assert EyeSpec.from_dict(spec.to_dict()) == spec and EyeSpec.from_dict(DEFAULT_EYE.to_dict()) == DEFAULT_EYE
    assert EyeSpec.from_dict({**DEFAULT_EYE.to_dict(), "sclera_texture": None}) == DEFAULT_EYE  # null = none
    for bad in ("", "   ", 5, b"x.png", "a\0b.png", ["x.png"], True):
        with pytest.raises(ValueError):
            dataclasses.replace(DEFAULT_EYE, sclera_texture=bad)
        with pytest.raises(ValueError):
            EyeSpec.from_dict({**DEFAULT_EYE.to_dict(), "sclera_texture": bad})
    with pytest.raises(ValueError):
        EyeSpec.from_dict({**DEFAULT_EYE.to_dict(), "sclera_map": "x.png"})  # unknown keys stay refused


def _eye_scene(spec: EyeSpec) -> Scene:
    app = Application()
    app.init_scene("cube")
    eye = app.add_eye()
    eye.eye = spec
    return app.scene


@pytest.mark.parametrize("spec, version", [
    (DEFAULT_EYE, EYE_FORMAT_VERSION),
    (dataclasses.replace(DEFAULT_EYE, look=DEFAULT_LOOK), EYE_LOOK_FORMAT_VERSION),
    (dataclasses.replace(DEFAULT_EYE, look=dataclasses.replace(DEFAULT_LOOK, iris=DEFAULT_IRIS)),
     EYE_IRIS_FORMAT_VERSION),
])
def test_v9_to_v11_files_are_written_and_read_as_before(spec, version):
    data = json.loads(json.dumps(scene_to_dict(_eye_scene(spec))))
    assert data["version"] == version and all("sclera_texture" not in o.get("eye", {}) for o in data["objects"])
    loaded = scene_from_dict(data)
    assert [o.eye for o in loaded.objects.values() if o.eye] == [spec]
    assert json.loads(json.dumps(scene_to_dict(loaded))) == data  # the round trip is the same file


def test_v12_only_with_a_map_and_an_unknown_version_is_refused():
    spec = dataclasses.replace(DEFAULT_EYE, look=DEFAULT_LOOK, sclera_texture="maps/sclera.png")
    data = json.loads(json.dumps(scene_to_dict(_eye_scene(spec))))
    assert data["version"] == EYE_SCLERA_FORMAT_VERSION == 12
    assert [o.eye for o in scene_from_dict(data).objects.values() if o.eye] == [spec]
    removed = json.loads(json.dumps(scene_to_dict(_eye_scene(dataclasses.replace(spec, sclera_texture=None)))))
    assert removed["version"] == EYE_LOOK_FORMAT_VERSION  # without the map: the older format again
    data["version"] = 14  # 13: bone links (AD-036)
    with pytest.raises(ValueError):
        scene_from_dict(data)
    bad = json.loads(json.dumps(scene_to_dict(_eye_scene(spec))))
    next(o for o in bad["objects"] if o.get("eye"))["eye"]["sclera_texture"] = ""
    with pytest.raises(ValueError):
        scene_from_dict(bad)  # an invalid map path makes the file invalid


# -- the size policy (mirai.sclera_map) ---------------------------------------------------------------------------------


def test_header_sizes_and_the_policy(tmp_path):
    assert sclera_map.image_size(SYNTHETIC) == ("PNG", 1024, 1024) and sclera_map.check(SYNTHETIC).usable
    assert sclera_map.check(TEMPLATE) == sclera_map.MapCheck(True, (1024, 1024), "")
    bmp = tmp_path / "a.bmp"
    bmp.write_bytes(b"BM" + bytes(16) + struct.pack("<ii", 512, -512) + bytes(30))
    assert sclera_map.image_size(bmp) == ("BMP", 512, 512)
    jpeg = tmp_path / "a.jpg"
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + bytes(14)
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, 768, 2048, 3) + bytes(3)
    jpeg.write_bytes(b"\xff\xd8" + app0 + sof + b"\xff\xd9")
    assert sclera_map.image_size(jpeg) == ("JPEG", 2048, 768)
    assert sclera_map.check(jpeg).usable and "nicht quadratisch" in sclera_map.check(jpeg).note
    assert sclera_map.check(_png_header(tmp_path / "2k.png", 2048, 2048)).usable
    assert "empfohlen" in sclera_map.check(_png_header(tmp_path / "512.png", 512, 512)).note
    big = sclera_map.check(_png_header(tmp_path / "4k.png", 4096, 4096))
    assert not big.usable and big.size == (4096, 4096) and "zu groß" in big.problem
    assert not sclera_map.check(_png_header(tmp_path / "wide.png", 2049, 16)).usable
    (tmp_path / "x.tga").write_bytes(b"\0" * 40)
    assert "Format" in sclera_map.check(tmp_path / "x.tga").problem
    assert sclera_map.check(tmp_path / "none.png").problem == "nicht gefunden"
    from viewport.eye_pass import SCLERA_MAX_SIZE

    assert SCLERA_MAX_SIZE == sclera_map.MAX_SIZE  # the pass's guard and the app's refusal agree


# -- the app: assign, replace, remove - one Undo step each ---------------------------------------------------------------


def test_assign_replace_remove_are_one_undo_step_each_and_undo_redo_restore_the_path(app, tmp_path):
    first, second = _png(tmp_path / "a.png"), _png(tmp_path / "b.png", colour=(220, 180, 170))
    eye = app.add_eye()
    depth = _depth(app)
    assert app.set_eye_sclera_image(str(first)) is True and _depth(app) == depth + 1
    assert eye.eye.sclera_texture == str(first) and "a.png" in app.status_message
    assert app.set_eye_sclera_image(str(second)) is True and _depth(app) == depth + 2  # replace = load another
    assert app.set_eye_sclera_image(None) is True and _depth(app) == depth + 3
    assert eye.eye.sclera_texture is None and "removed" in app.status_message
    app.key_press(CTRL_Z)
    assert eye.eye.sclera_texture == str(second)
    app.key_press(CTRL_Z)
    assert eye.eye.sclera_texture == str(first)
    app.key_press(CTRL_Z)
    assert eye.eye.sclera_texture is None
    app.key_press(CTRL_Y)
    assert eye.eye.sclera_texture == str(first)
    app.key_press(CTRL_Y)
    app.key_press(CTRL_Y)
    assert eye.eye.sclera_texture is None
    assert app.set_eye_sclera_image(None) is False and _depth(app) == depth + 3  # nothing to remove: no step


def test_refusals_change_nothing(app, tmp_path):
    eye = app.add_eye()
    depth = _depth(app)
    assert app.set_eye_sclera_image(str(tmp_path / "missing.png")) is False and "not found" in app.status_message
    assert app.set_eye_sclera_image(str(_png_header(tmp_path / "4k.png", 4096, 4096))) is False
    assert "2048" in app.status_message
    (tmp_path / "x.tga").write_bytes(b"\0" * 40)
    assert app.set_eye_sclera_image(str(tmp_path / "x.tga")) is False
    assert eye.eye.sclera_texture is None and _depth(app) == depth
    app.selection.objects = set()
    assert app.set_eye_sclera_image(str(SYNTHETIC)) is False and "select an eye" in app.status_message


def test_sclera_operations_leave_iris_fit_relief_and_look_alone_and_vice_versa(app, tmp_path):
    iris = _png(tmp_path / "iris.png")
    eye = app.add_eye()
    app.set_eye(fit_pupil=0.3, fit_limbus=0.9, **{"look.wet_sclera": 0.6, IRIS_PREFIX + "relief": 0.4,
                                                     IRIS_PREFIX + "relief_source": "alpha"})
    eye.texture = str(iris)
    before = dataclasses.replace(eye.eye)
    for path in (SYNTHETIC, TEMPLATE, None):
        assert app.set_eye_sclera_image(None if path is None else str(path)) is True
        assert eye.texture == str(iris)
        assert dataclasses.replace(eye.eye, sclera_texture=None) == before  # fit, look, iris values, relief source
    assert app.set_eye_sclera_image(str(SYNTHETIC)) is True
    assert app.set_eye_iris_image(None) is True and eye.eye.sclera_texture == str(SYNTHETIC)  # the iris: not the map
    assert app.set_eye(**{"look.wet_sclera": 0.2}) is True and eye.eye.sclera_texture == str(SYNTHETIC)


def test_each_eye_its_own_map_and_copies_twins_and_scene_load_carry_it(app, tmp_path):
    left, right = app.add_eye("L"), app.add_eye("R")
    app.selection.objects = {left.id}
    assert app.set_eye_sclera_image(str(SYNTHETIC)) is True
    app.selection.objects = {right.id}
    assert app.set_eye_sclera_image(str(TEMPLATE)) is True
    assert (left.eye.sclera_texture, right.eye.sclera_texture) == (str(SYNTHETIC), str(TEMPLATE))  # S-5
    app.selection.objects = {left.id}
    copy = app.mirror_copy("X")
    assert copy is not None and copy.eye.sclera_texture == str(SYNTHETIC)  # no automatic flip (S-5)
    app.selection.objects = {right.id}
    assert app.duplicate_objects() is True
    duplicate = next(o for o in app.scene.objects.values() if o.eye and o.id not in (left.id, right.id, copy.id))
    assert duplicate.eye.sclera_texture == str(TEMPLATE)
    app.selection.objects = {copy.id}
    assert app.set_eye_sclera_image(str(TEMPLATE)) is True  # then the artist assigns another image to one eye
    assert copy.eye.sclera_texture == str(TEMPLATE) and left.eye.sclera_texture == str(SYNTHETIC)
    scene = tmp_path / "s.mirai.json"
    assert app.save_scene_file(scene) is True
    fresh = Application()
    fresh.init_scene("cube")
    fresh.load_scene("file", scene_path=scene)  # replace_scene
    by_name = {o.name: o for o in fresh.scene.objects.values() if o.eye}
    assert Path(by_name["L"].eye.sclera_texture).read_bytes() == SYNTHETIC.read_bytes()
    assert Path(by_name["R"].eye.sclera_texture).read_bytes() == TEMPLATE.read_bytes()


def test_a_morph_view_twin_draws_the_same_map(app):
    from mirai.controllers.objects import VIEW_TWIN

    eye = app.add_eye()
    assert app.set_eye_sclera_image(str(SYNTHETIC)) is True
    app.add_primitive("cube", "tooth")
    app.selection.mode = SelectionMode.VERTEX
    assert app.create_morph_target() is not None and app.edit_morph_target()
    entries = app.viewport._eye_entries
    assert entries[(VIEW_TWIN, eye.id)] == entries[eye.id] and entries[eye.id].sclera_texture == str(SYNTHETIC)


# -- the eye entry and S-4 ---------------------------------------------------------------------------------------------


def test_the_entry_carries_a_usable_map_only_and_a_missing_one_keeps_its_path(app, tmp_path):
    eye = app.add_eye()
    assert _entry(app, eye).sclera_texture is None
    path = _png(tmp_path / "m.png")
    assert app.set_eye_sclera_image(str(path)) is True and _entry(app, eye).sclera_texture == str(path)
    path.unlink()
    app._objects.sync_views()
    assert eye.eye.sclera_texture == str(path) and _entry(app, eye).sclera_texture is None  # the base colour
    _png_header(path, 4096, 4096)  # replaced on disk by an image above the policy: not loaded silently
    app._objects.sync_views()
    assert _entry(app, eye).sclera_texture is None


def test_no_selection_tint_on_eyes_while_the_eye_lab_is_open(app):
    eye = app.add_eye()
    assert app.set_eye_sclera_image(str(SYNTHETIC)) is True
    base = tuple(object_base_color(eye))
    tinted = _entry(app, eye)
    assert tinted.sclera_colour != base and tinted.sclera_tint == (*SELECTED_TINT, SELECTED_TINT_SHARE)  # outside
    assert app.open_eye_lab() is True
    lab = _entry(app, eye)
    assert lab.sclera_colour == base and lab.sclera_tint == (0.0, 0.0, 0.0, 0.0)
    assert app.viewport.object_entries[eye.id].material.color == base  # preview off: untinted too
    assert eye.id in app._objects.highlighted()  # the eye stays selected (outliner, the lab's header)
    assert app.close_eye_lab() is True
    assert _entry(app, eye).sclera_colour == tinted.sclera_colour  # outside the lab as before


# -- storage beside the scene ------------------------------------------------------------------------------------------


def _eye_raw(path: Path) -> list:
    return [o["eye"] for o in json.loads(path.read_text(encoding="utf-8"))["objects"] if o.get("eye")]


def test_save_copies_writes_relative_and_reopens_absolute(app, tmp_path):
    source = _png(tmp_path / "paint" / "sclera L.png")
    eye = app.add_eye()
    assert app.set_eye_sclera_image(str(source)) is True
    scene = tmp_path / "scenes" / "Gollum.mirai.json"
    assert app.save_scene_file(scene) is True and "sclera image copied" in app.status_message
    copies = sorted((scene.parent / "Gollum_textures").iterdir())
    assert len(copies) == 1 and copies[0].read_bytes() == source.read_bytes()
    assert copies[0].name == tf.hashed_name("sclera L", source.read_bytes(), ".png")
    assert eye.eye.sclera_texture == str(copies[0])
    data = json.loads(scene.read_text(encoding="utf-8"))
    assert data["version"] == 12 and _eye_raw(scene)[0]["sclera_texture"] == f"Gollum_textures/{copies[0].name}"
    reopened = Application()
    reopened.init_scene("cube")
    reopened.load_scene("file", scene_path=scene)
    loaded = next(o for o in reopened.scene.objects.values() if o.eye)
    assert loaded.eye.sclera_texture == str(copies[0]) and Path(loaded.eye.sclera_texture).is_absolute()
    assert reopened.viewport._eye_entries[loaded.id].sclera_texture == str(copies[0])
    assert app.save_scene_file(scene) is True and sorted(copies[0].parent.iterdir()) == copies  # once


def test_save_as_is_independent_and_never_overwrites(app, tmp_path):
    source = _png(tmp_path / "in" / "s.png")
    eye = app.add_eye()
    assert app.set_eye_sclera_image(str(source)) is True
    first = tmp_path / "scenes" / "A.mirai.json"
    assert app.save_scene_file(first) is True
    a_copy = Path(eye.eye.sclera_texture)
    second = tmp_path / "scenes" / "B.mirai.json"
    squatter = second.parent / "B_textures" / a_copy.name  # a file of the copy's name with other content
    squatter.parent.mkdir(parents=True)
    squatter.write_bytes(b"someone else's file")
    assert app.save_scene_file(second) is True
    b_copy = Path(eye.eye.sclera_texture)
    assert b_copy.parent == second.parent / "B_textures" and b_copy != squatter
    assert b_copy.read_bytes() == source.read_bytes() and squatter.read_bytes() == b"someone else's file"
    assert a_copy.exists() and a_copy.read_bytes() == source.read_bytes()  # the first scene's copy untouched
    assert _eye_raw(first)[0]["sclera_texture"] == f"A_textures/{a_copy.name}"
    assert _eye_raw(second)[0]["sclera_texture"] == f"B_textures/{b_copy.name}"
    app.key_press(CTRL_Z)  # the assignment's step: no map; nothing was deleted
    assert eye.eye.sclera_texture is None and source.exists() and a_copy.exists() and b_copy.exists()


def test_a_missing_map_keeps_its_path_and_falls_back_to_the_base_colour(app, tmp_path):
    source = _png(tmp_path / "elsewhere" / "gone.png")  # outside the scene's directory: written as it is
    eye = app.add_eye()
    assert app.set_eye_sclera_image(str(source)) is True
    source.unlink()
    scene = tmp_path / "scenes" / "s.mirai.json"
    assert app.save_scene_file(scene) is True and "not found, path kept: gone.png" in app.status_message
    assert eye.eye.sclera_texture == str(source) and _eye_raw(scene)[0]["sclera_texture"] == str(source)
    reopened = Application()
    reopened.init_scene("cube")
    reopened.load_scene("file", scene_path=scene)
    loaded = next(o for o in reopened.scene.objects.values() if o.eye)
    assert loaded.eye.sclera_texture == str(source) and reopened.viewport._eye_entries[loaded.id].sclera_texture is None
    from gui import eye_model as em

    reopened.selection.mode = SelectionMode.OBJECT
    reopened.selection.objects = {loaded.id}
    assert "nicht gefunden" in em.state(reopened).sclera_text  # visible to the artist


# -- presets ------------------------------------------------------------------------------------------------------------


@pytest.fixture
def preset_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(eye_presets, "PRESET_DIR", tmp_path)
    monkeypatch.setattr(eye_presets.load_presets, "__defaults__", (tmp_path,))
    monkeypatch.setattr(eye_presets.save_preset, "__defaults__", (tmp_path,))
    return tmp_path


def test_presets_neither_write_replace_nor_remove_the_map(app, preset_dir):
    eye = app.add_eye()
    assert app.set_eye_sclera_image(str(SYNTHETIC)) is True
    assert "sclera_texture" in eye_presets.IMAGE_FIELDS and "sclera_texture" not in eye_presets.PRESET_FIELDS
    assert app.save_eye_preset("Mit Bild") is True
    assert "sclera_texture" not in json.loads((preset_dir / "mit_bild.json").read_text(encoding="utf-8"))["values"]
    for name in (eye_presets.BUILTIN_NAME, eye_presets.LOOK_START_NAME, eye_presets.IRIS_START_NAME, "Mit Bild"):
        app.apply_eye_preset(name)
        assert eye.eye.sclera_texture == str(SYNTHETIC), name
    assert app.set_eye_sclera_image(None) is True and app.apply_eye_preset("Mit Bild") is not None
    assert eye.eye.sclera_texture is None  # nor brings one back
    (preset_dir / "bad.json").write_text(json.dumps({"name": "Bad", "values": {"sclera_texture": "x.png"}}),
                                         encoding="utf-8")
    presets, problems = eye_presets.load_presets(preset_dir)
    assert "Bad" not in [p.name for p in presets] and any("sclera_texture" in text for text in problems)


# -- the Eye Lab's model -----------------------------------------------------------------------------------------------


def test_eye_lab_sclera_controls(app, tmp_path):
    from gui import eye_model as em

    eye = app.add_eye()
    assert em.state(app).sclera_text == "Lederhaut: Grundfarbe (kein Bild)" and em.state(app).sclera_path is None
    assert em.set_sclera_image(app, "   ") is False and "type a path" in app.status_message
    assert em.set_sclera_image(app, f'  "{SYNTHETIC}"  ') is True and eye.eye.sclera_texture == str(SYNTHETIC)
    assert em.state(app).sclera_text == f"Lederhaut: {SYNTHETIC.name}"
    small = _png(tmp_path / "small.png")
    assert em.set_sclera_image(app, str(small)) is True and "empfohlen" in em.state(app).sclera_text
    assert em.set_sclera_image(app, None) is True and eye.eye.sclera_texture is None
    assert "1/4" in em.SCLERA_HINT and "eye_sclera_assets_2026-11-17" in em.SCLERA_HINT
