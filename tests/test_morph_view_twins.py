"""AD-033 §14 (Manu 2026-11-16: "morph twins for eyes and teeth"): while a morph target's editing view is open, every
drawn Normal object other than the base is drawn a second time beside the view, shifted as the view is. The twins are
viewport entries only - the scene, the selection, the pick caches, the file and the Undo stack do not know them."""

from __future__ import annotations

import json
import math

import pytest

import tests._bootstrap  # noqa: F401

from core import ObjectState, SelectionMode
from mirai import object_space
from mirai.application import Application
from mirai.controllers.objects import VIEW_TWIN
from mirai.interaction.input import Input


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


CTRL_Z = _key("z", "ctrl")


def _translation(matrix) -> tuple[float, float, float]:
    return (0.0, 0.0, 0.0) if matrix is None else (matrix[12], matrix[13], matrix[14])


def _rotation_scale(matrix) -> list[float]:
    identity = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    return identity if matrix is None else list(matrix[:12])


def _angle_between(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b)) / (math.dist(a, (0, 0, 0)) * math.dist(b, (0, 0, 0)))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


@pytest.fixture
def app() -> Application:
    """A head stand-in (the cube, with one morph target), an eye and a tooth (a second cube), in component mode."""
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    app.add_eye()
    app.add_primitive("cube", "tooth")
    app.selection.mode = SelectionMode.VERTEX
    assert app.create_morph_target() is not None
    return app


def _named(app, name):
    return next(obj for obj in app.scene.objects.values() if obj.name == name)


def _shift(app, base) -> tuple[float, float, float]:
    view = app.scene.edit_object
    return tuple(view.transform.translation[i] - base.transform.translation[i] for i in range(3))


def test_eyes_and_teeth_are_drawn_beside_the_view_shifted_as_the_view_is(app):
    base, eye, tooth = app.scene.edit_object, _named(app, "Eye"), _named(app, "tooth")
    entries = app.viewport.object_entries
    assert not any(isinstance(key, tuple) for key in entries)  # no view: no twins
    assert app.edit_morph_target()
    shift = _shift(app, base)
    assert shift != (0.0, 0.0, 0.0)
    for obj in (eye, tooth):
        twin, own = entries[(VIEW_TWIN, obj.id)], entries[obj.id]
        assert twin.mesh is obj.mesh  # the actual object, not a copy of its geometry
        assert _translation(twin.model_matrix) == pytest.approx(
            tuple(a + b for a, b in zip(_translation(own.model_matrix), shift)), abs=1e-12)
        assert _rotation_scale(twin.model_matrix) == pytest.approx(_rotation_scale(own.model_matrix), abs=1e-12)
    assert (VIEW_TWIN, base.id) not in entries  # the view itself stands for the base
    assert base.id in entries and eye.id in entries  # the base beside the view keeps its own eyes


def test_a_twin_eye_is_drawn_by_the_eye_pass_like_its_original(app):
    eye = _named(app, "Eye")
    assert app.edit_morph_target()
    eye_entries = app.viewport._eye_entries
    assert eye_entries[(VIEW_TWIN, eye.id)] == eye_entries[eye.id]
    assert (VIEW_TWIN, _named(app, "tooth").id) not in eye_entries


def test_the_twins_go_when_the_view_closes(app):
    assert app.edit_morph_target()
    assert any(isinstance(key, tuple) for key in app.viewport.object_entries)
    assert app.leave_morph_target()
    assert not any(isinstance(key, tuple) for key in app.viewport.object_entries)
    assert app.edit_morph_target()
    app.init_scene("cube")  # a scene load closes the view
    assert not any(isinstance(key, tuple) for key in app.viewport.object_entries)


def test_a_hidden_object_and_a_reference_have_no_twin(app):
    eye, tooth = _named(app, "Eye"), _named(app, "tooth")
    assert app.set_objects_hidden([tooth.id], True)
    eye.state = ObjectState.REFERENCE
    assert app.edit_morph_target()
    entries = app.viewport.object_entries
    assert (VIEW_TWIN, tooth.id) not in entries and tooth.id not in entries
    assert (VIEW_TWIN, eye.id) not in entries and eye.id in entries  # a Reference stays where it is


def test_the_document_does_not_know_the_twins(app, tmp_path):
    eye, tooth = _named(app, "Eye"), _named(app, "tooth")
    closed, opened = tmp_path / "closed.mirai.json", tmp_path / "open.mirai.json"
    assert app.save_scene_file(closed)
    objects, undo_depth = set(app.scene.objects), len(app.history._undo_stack)
    assert app.edit_morph_target()
    view = app.scene.edit_object
    assert set(app.scene.objects) == objects | {view.id}  # the view object only, as before
    assert not any(isinstance(key, tuple) for key in app._objects.pick_caches)
    width, height = app.viewport_width, app.viewport_height
    for x in range(0, width, 40):  # nothing under the cursor is ever a twin
        picked = app._objects.pick(float(x), height / 2)
        assert picked is None or picked in app.scene.objects
    assert len(app.history._undo_stack) == undo_depth
    assert app.save_scene_file(opened)
    # The file holds the same objects with and without an open view (the view's own traces - the id counter it
    # raised, the camera it moved - are as before this change).
    assert json.loads(opened.read_text())["objects"] == json.loads(closed.read_text())["objects"]
    assert eye.eye is not None and all(obj.mesh is not eye.mesh for obj in (view, tooth))


def test_a_twin_follows_an_undo_that_rebuilds_the_eyes_shell(app):
    eye = _named(app, "Eye")
    app.selection.mode = SelectionMode.OBJECT
    app.selection.objects = {eye.id}
    before = eye.mesh
    assert app.set_eye(cornea_radius=0.7)
    assert eye.mesh is not before
    app.selection.mode = SelectionMode.VERTEX
    assert app.edit_morph_target()
    assert app.viewport.object_entries[(VIEW_TWIN, eye.id)].mesh is eye.mesh
    assert app.key_press(CTRL_Z)
    assert eye.mesh is before
    if app.morph_view_open:  # the Undo of an older step keeps the view open
        assert app.viewport.object_entries[(VIEW_TWIN, eye.id)].mesh is before


def test_a_twin_eye_looks_at_the_camera_from_its_own_place(app):
    eye = _named(app, "Eye")
    assert app.edit_morph_target()
    app.camera.set_view(0.3, 0.1)
    assert app.set_eye_gaze(mode="camera")
    app.update_viewport(0.016)
    camera = app.camera.eye()
    for key in (eye.id, (VIEW_TWIN, eye.id)):
        m = app.viewport.object_entries[key].model_matrix
        centre = (m[12], m[13], m[14])  # the eye's pivot is its centre
        assert _angle_between((m[8], m[9], m[10]), tuple(c - p for c, p in zip(camera, centre))) < 1e-4
    assert eye.transform.rotation == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))  # view state only


def test_a_twin_eye_keeps_the_direction_of_a_fixed_gaze(app):
    eye = _named(app, "Eye")
    assert app.edit_morph_target()
    assert app.set_eye_gaze_angles(20.0, -10.0)  # the pad: mode "target"
    entries = app.viewport.object_entries
    own, twin = entries[eye.id].model_matrix, entries[(VIEW_TWIN, eye.id)].model_matrix
    assert _rotation_scale(twin) == pytest.approx(_rotation_scale(own), abs=1e-12)
    assert _rotation_scale(own) != pytest.approx(_rotation_scale(object_space.placement_matrix(eye.transform, eye.pivot)))
