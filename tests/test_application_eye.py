"""AD-033 §4 / §6 on the app path (headless): add an eye, change its values with Undo (a shell rebuild included),
the refusals (edit object, Apply transform, Attach, a front-to-back mirror), duplicate / mirror copy keep the eye,
save / load, the iris image with its fit file."""

from __future__ import annotations

import json

import pytest

import tests._bootstrap  # noqa: F401

from core import ObjectState
from core.selection import SelectionMode
from mirai.application import Application
from mirai.eye_object import DEFAULT_EYE, EYE_SCALE_CM
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def test_add_eye_selects_it_and_undo_removes_it(app):
    edit = app.scene.edit_object
    eye = app.add_eye()
    assert eye.eye == DEFAULT_EYE and eye.transform.scale == EYE_SCALE_CM and eye.name.startswith("Eye")
    assert app.selection.mode is SelectionMode.OBJECT and app.selection.objects == {eye.id}
    assert app.scene.edit_object is edit  # the edit object stays
    assert eye.id in app.viewport.object_entries
    app.key_press(CTRL_Z)
    assert eye.id not in app.scene.objects and eye.id not in app.viewport.object_entries
    app.key_press(CTRL_Y)
    assert app.scene.objects[eye.id].eye == DEFAULT_EYE


def test_set_eye_shading_value_keeps_the_shell_and_undoes(app):
    eye = app.add_eye()
    shell = eye.mesh
    assert app.set_eye(limbus_level=2, overlap_mm=0.3) is True
    assert eye.eye.limbus_level == 2 and eye.mesh is shell
    app.key_press(CTRL_Z)
    assert eye.eye == DEFAULT_EYE
    app.key_press(CTRL_Y)
    assert eye.eye.overlap_mm == 0.3


def test_set_eye_shape_value_rebuilds_the_shell_with_undo(app):
    eye = app.add_eye()
    shell = eye.mesh
    assert app.set_eye(cornea_radius=0.7) is True
    rebuilt = eye.mesh
    assert rebuilt is not shell and app.viewport.object_entries[eye.id].mesh is rebuilt
    app.key_press(CTRL_Z)
    assert eye.mesh is shell and eye.eye.cornea_radius == 0.65
    assert app.viewport.object_entries[eye.id].mesh is shell
    app.key_press(CTRL_Y)
    assert eye.mesh is rebuilt


def test_invalid_eye_values_are_refused_with_the_reason(app):
    eye = app.add_eye()
    assert app.set_eye(pupil_radius=0.9) is False
    assert "pupil_radius" in app.status_message and eye.eye == DEFAULT_EYE
    app.selection.objects = {app.scene.edit_object_id}
    assert app.set_eye(limbus_level=1) is False and "select an eye" in app.status_message


def test_an_eye_never_becomes_the_edit_object(app):
    edit = app.scene.edit_object
    eye = app.add_eye()
    app.selection.objects = {eye.id}
    app.key_press(_key("1"))
    assert app.scene.edit_object is edit
    assert "is an eye" in app.status_message


def test_apply_transform_is_refused_for_an_eye_clear_is_not(app):
    eye = app.add_eye()
    app.selection.objects = {eye.id}
    assert app.dispatch_command(cmd.APPLY_TRANSFORM) is False or eye.transform.scale == EYE_SCALE_CM
    assert eye.transform.scale == EYE_SCALE_CM and "is an eye" in app.status_message


def test_attach_refuses_an_eye(app):
    eye = app.add_eye()
    app.selection.objects = {eye.id}
    plan = app.attach_plan()
    assert plan.refusal is not None and "is an eye" in plan.refusal


def test_duplicate_and_mirror_copy_keep_the_eye(app):
    eye = app.add_eye()
    app.set_eye(limbus_level=3)
    app.selection.objects = {eye.id}
    assert app.duplicate_objects() is True
    copies = [o for o in app.scene.objects.values() if o.eye is not None and o.id != eye.id]
    assert len(copies) == 1 and copies[0].eye == eye.eye
    app.selection.objects = {eye.id}
    mirrored = app.mirror_copy("X")
    assert mirrored is not None and mirrored.eye == eye.eye
    assert len(mirrored.mesh.all_face_ids()) == len(eye.mesh.all_face_ids())
    app.selection.objects = {copies[0].id}
    assert app.mirror_copy("Z") is None and "look backwards" in app.status_message


def test_eyes_survive_save_and_load(app, tmp_path):
    eye = app.add_eye()
    app.set_eye(limbus_level=2, asymmetry=True)
    path = tmp_path / "eye.mirai.json"
    assert app.save_scene_file(path) is True
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 9
    fresh = Application()
    fresh.init_scene("cube")
    fresh.load_scene("file", scene_path=path)
    eyes = [o for o in fresh.scene.objects.values() if o.eye is not None]
    assert len(eyes) == 1 and eyes[0].eye == eye.eye and eyes[0].state is ObjectState.NORMAL
    assert eyes[0].transform.scale == EYE_SCALE_CM


def test_iris_image_with_its_fit_file_is_one_undo_step(app, tmp_path):
    eye = app.add_eye()
    image = tmp_path / "iris_custom.png"
    image.write_bytes(b"\x89PNG")
    (tmp_path / "iris_custom.json").write_text('{"pupil": 0.22, "limbus": 0.88, "hold_outer_color": true}')
    assert app.set_eye_iris_image(image) is True
    assert eye.texture == str(image)
    assert (eye.eye.fit_pupil, eye.eye.fit_limbus, eye.eye.hold_outer_color) == (0.22, 0.88, True)
    app.key_press(CTRL_Z)
    assert eye.texture is None and eye.eye.fit_pupil is None
    (tmp_path / "iris_custom.json").write_text('{"pupil": 0.9, "limbus": 0.5}')
    assert app.set_eye_iris_image(image) is False and "0 < pupil < limbus" in app.status_message
    assert app.set_eye_iris_image(tmp_path / "missing.png") is False and "not found" in app.status_message
