"""Eye LookDev phase 5 (Manu 2026-11-16): texture paths relative to the scene file and the iris image copied beside it
(`mirai.texture_files`, `Application.save_scene_file` / `load_scene`). Headless: the paths and files only."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from mirai import texture_files as tf
from mirai.application import Application
from mirai.interaction.input import Input

CTRL_Z = Input("key", "z", frozenset({"ctrl"}))


# -- the helpers -------------------------------------------------------------------------------------------------------


def test_absolute_on_either_system():
    assert tf.is_absolute("/home/x/a.png") and tf.is_absolute("C:\\Users\\x\\a.png") and tf.is_absolute("\\\\srv\\a.png")
    assert not tf.is_absolute("Gollum_textures/a.png") and not tf.is_absolute("a b/c.png")


def test_resolve_and_to_file_round_trip(tmp_path):
    scene_dir = tmp_path / "my scenes"
    inner = str(scene_dir / "Kopf 1_textures" / "iris a.png")
    assert tf.to_file(inner, scene_dir) == "Kopf 1_textures/iris a.png"
    assert tf.resolve("Kopf 1_textures/iris a.png", scene_dir) == os.path.normpath(inner)
    assert tf.resolve("Kopf 1_textures\\iris a.png", scene_dir) == os.path.normpath(inner)  # written on Windows
    outside = str(tmp_path / "elsewhere" / "a.png")
    assert tf.to_file(outside, scene_dir) == outside  # outside the scene directory: absolute as before
    assert tf.resolve(outside, scene_dir) == outside
    windows = "C:\\Users\\Manuel\\Mirai_Bastel\\scenes\\x_textures\\a.png"
    assert tf.resolve(windows, scene_dir) == windows  # never joined to the scene directory
    if os.name != "nt":
        assert tf.to_file(windows, scene_dir) == windows


def test_store_never_overwrites(tmp_path):
    first = tf.store(b"one", tmp_path, "a.png")
    assert tf.store(b"one", tmp_path, "a.png") == first  # the same bytes: the existing file
    other = tf.store(b"two", tmp_path, "a.png")
    assert other.name == "a_2.png" and first.read_bytes() == b"one" and other.read_bytes() == b"two"
    name = tf.hashed_name("iris_custom", b"x", ".PNG")
    assert name == f"iris_custom_{tf.content_hash(b'x')}.png"
    assert tf.hashed_name(Path(name).stem, b"x", ".png") == name  # a copy of a copy keeps one hash


# -- the app: save and load --------------------------------------------------------------------------------------------


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _image(path: Path, data: bytes = b"\x89PNG fake iris") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _textures(path: Path) -> list:
    return [o.get("texture") for o in json.loads(path.read_text(encoding="utf-8"))["objects"]]


def _load(path: Path) -> Application:
    fresh = Application()
    fresh.init_scene("cube")
    fresh.load_scene("file", scene_path=path)
    return fresh


def test_absolute_relative_missing_and_spaces_round_trip(app, tmp_path):
    scene = tmp_path / "scenes with space" / "Kopf A.mirai.json"
    cube = app.scene.edit_object
    beside = _image(scene.parent / "Kopf A_textures" / "face map.png")
    outside = _image(tmp_path / "library" / "skin.png")
    cube.texture = str(beside)
    assert app.save_scene_file(scene) is True
    assert _textures(scene) == ["Kopf A_textures/face map.png"]
    fresh = _load(scene)
    assert fresh.scene.edit_object.texture == os.path.normpath(str(beside)) and fresh.scene_path == scene
    cube.texture = str(outside)  # outside the scene directory: absolute, as before phase 5
    assert app.save_scene_file(scene) is True and _textures(scene) == [str(outside)]
    assert _load(scene).scene.edit_object.texture == str(outside)
    missing = scene.parent / "Kopf A_textures" / "gone.png"
    cube.texture = str(missing)  # a missing texture keeps its path
    assert app.save_scene_file(scene) is True and _textures(scene) == ["Kopf A_textures/gone.png"]
    fresh = _load(scene)
    assert fresh.scene.edit_object.texture == os.path.normpath(str(missing))
    assert fresh.save_scene_file(scene) is True and _textures(scene) == ["Kopf A_textures/gone.png"]


def test_a_relative_path_resolves_against_the_scene_not_the_working_directory(app, tmp_path, monkeypatch):
    scene = tmp_path / "a" / "s.mirai.json"
    image = _image(scene.parent / "s_textures" / "t.png")
    app.scene.edit_object.texture = str(image)
    assert app.save_scene_file(scene) is True
    monkeypatch.chdir(tmp_path)  # another working directory (a fresh clone elsewhere)
    assert Path(_load(Path("a/s.mirai.json")).scene.edit_object.texture) == image


def test_older_files_and_foreign_absolute_paths_are_kept(app, tmp_path):
    scene = tmp_path / "old.mirai.json"
    windows = "C:\\Users\\Manuel\\Mirai_Bastel\\experiments\\lookdev_eye_lab\\out\\iris_custom.png"
    app.add_eye().texture = windows
    assert app.save_scene_file(scene) is True  # an iris that does not exist here: not copied, the string kept
    assert windows in _textures(scene) and "not found" in app.status_message
    assert windows in [o.texture for o in _load(scene).scene.objects.values()]


def test_the_iris_image_is_copied_beside_the_scene_on_save(app, tmp_path):
    source = _image(tmp_path / "lab" / "out" / "iris_custom.png")
    left, right = app.add_eye("L"), app.add_eye("R")
    for eye in (left, right):
        eye.texture = str(source)
    face = _image(tmp_path / "lab" / "face.png", b"face")
    app.scene.edit_object.texture = str(face)  # not an eye: never copied
    scene = tmp_path / "scenes" / "Gollum.mirai.json"
    assert app.save_scene_file(scene) is True
    folder = scene.parent / "Gollum_textures"
    copies = sorted(folder.iterdir())
    assert len(copies) == 1 and copies[0].read_bytes() == source.read_bytes()  # both eyes: one file
    assert copies[0].name == f"iris_custom_{tf.content_hash(source.read_bytes())}.png"
    assert left.texture == right.texture == str(copies[0])  # the eyes point at the copy after the save
    assert sorted(t for t in _textures(scene) if t) == sorted([str(face)] + [f"Gollum_textures/{copies[0].name}"] * 2)
    assert source.exists() and app.save_scene_file(scene) is True and sorted(folder.iterdir()) == copies  # once


def test_save_as_makes_an_independent_folder_and_leaves_the_original(app, tmp_path):
    source = _image(tmp_path / "in" / "iris.png")
    eye = app.add_eye()
    eye.texture = str(source)
    first = tmp_path / "scenes" / "A.mirai.json"
    assert app.save_scene_file(first) is True
    a_copy = Path(eye.texture)
    before = {p: p.read_bytes() for p in (first.parent / "A_textures").iterdir()}
    first_text = first.read_text(encoding="utf-8")
    second = tmp_path / "scenes" / "B.mirai.json"
    assert app.save_scene_file(second) is True
    b_copy = Path(eye.texture)
    assert b_copy.parent == second.parent / "B_textures" and b_copy.read_bytes() == a_copy.read_bytes()
    assert {p: p.read_bytes() for p in (first.parent / "A_textures").iterdir()} == before
    assert first.read_text(encoding="utf-8") == first_text  # the original scene file untouched
    assert f"B_textures/{b_copy.name}" in _textures(second)
    assert Path(next(o.texture for o in _load(first).scene.objects.values() if o.eye)) == a_copy


def test_a_failed_save_changes_no_reference(app, tmp_path, monkeypatch):
    source = _image(tmp_path / "iris.png")
    eye = app.add_eye()
    eye.texture = str(source)

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(tf, "copy_into", fail)
    with pytest.raises(OSError):
        app.save_scene_file(tmp_path / "s.mirai.json")
    assert eye.texture == str(source) and not (tmp_path / "s.mirai.json").exists() and app.scene_path is None
    monkeypatch.undo()
    scene = tmp_path / "t.mirai.json"
    real_replace = os.replace

    def fail_write(src, dst):
        if str(dst) == str(scene):
            raise OSError("read-only")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", fail_write)
    with pytest.raises(OSError):
        app.save_scene_file(scene)
    assert eye.texture == str(source)  # the copy may exist; the eye points at it only after the file is written


def test_undo_after_the_copy_returns_to_an_existing_file(app, tmp_path):
    source = _image(tmp_path / "in" / "iris.png")
    other = _image(tmp_path / "in" / "other.png", b"other")
    eye = app.add_eye()
    assert app.set_eye_iris_image(str(source)) is True
    assert app.save_scene_file(tmp_path / "s.mirai.json") is True and Path(eye.texture).parent.name == "s_textures"
    copy = Path(eye.texture)
    assert app.set_eye_iris_image(str(other)) is True
    app.key_press(CTRL_Z)
    assert Path(eye.texture) == copy and copy.exists()
    app.key_press(CTRL_Z)  # the first image's step: back to no image
    assert eye.texture is None and source.exists() and copy.exists()  # nothing was deleted


def test_the_repository_test_scene_opens_with_its_iris_from_anywhere(tmp_path, monkeypatch):
    """§H row 5 "the scene opens on a fresh clone with its iris": `scenes/Eye_Iris_Import_Test.mirai.json` (synthetic
    images only - a painted iris and a traced "photo" of it, both made by Mirai's own code) names its copies
    scene-relative, so it opens from any working directory and any clone location."""
    from mirai import iris_import as ii
    from mirai.eye_object import look_value

    scene = Path(__file__).resolve().parents[1] / "scenes" / "Eye_Iris_Import_Test.mirai.json"
    raw = json.loads(scene.read_text(encoding="utf-8"))
    stored = [o["texture"] for o in raw["objects"] if "texture" in o]
    assert len(stored) == 2 and all(t.startswith("Eye_Iris_Import_Test_textures/") for t in stored)
    monkeypatch.chdir(tmp_path)
    fresh = Application()
    fresh.init_scene("cube")
    fresh.load_scene("file", scene_path=scene)
    eyes = [o for o in fresh.scene.objects.values() if o.eye is not None]
    assert len(eyes) == 2
    for eye in eyes:
        path = Path(eye.texture)
        assert path.is_file() and path.parent == scene.parent / "Eye_Iris_Import_Test_textures"
        assert ii.has_alpha(ii.decode_png(path.read_bytes())) and look_value(eye.eye, "iris.relief_source") == "alpha"
