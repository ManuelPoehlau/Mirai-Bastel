"""Eye gaze (`mirai.eye_gaze`, 2026-11-16): the math headless, and on the app path that the gaze is view state - the
drawn eye matrices turn, the document transforms, the file and the Undo stack do not."""

from __future__ import annotations

import json
import math

import pytest

import tests._bootstrap  # noqa: F401

from core import ObjectTransform, SceneObject
from core.ids import ObjectId
from core.mesh import Mesh
from mirai import eye_gaze as eg
from mirai import object_space
from mirai.application import Application
from mirai.eye_object import DEFAULT_EYE


def _eye(translation=(0.0, 0.0, 0.0), rotation=None, scale=0.1, pivot=(0.0, 0.0, 0.0), oid=1) -> SceneObject:
    rotation = rotation or ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    return SceneObject(ObjectId(oid), Mesh(), transform=ObjectTransform(translation, rotation, scale), pivot=pivot,
                       eye=DEFAULT_EYE)


def _forward(transform: ObjectTransform):
    return tuple(transform.rotation[i][2] for i in range(3))


def _angle_between(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b)) / (math.dist(a, (0, 0, 0)) * math.dist(b, (0, 0, 0)))
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


def _yaw(degrees: float):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


# -- math ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("pivot", [(0.0, 0.0, 0.0), (0.3, -0.2, 0.5)])
def test_aimed_eye_points_at_the_target_and_keeps_its_centre(pivot):
    eye = _eye(translation=(1.0, 2.0, 3.0), rotation=_yaw(10.0), pivot=pivot)
    centre = eg.eye_center(eye)
    target = (centre[0] + 0.4, centre[1] + 0.3, centre[2] + 2.0)
    aimed = eg.aimed_transform(eye, target)
    placed = SceneObject(ObjectId(2), Mesh(), transform=aimed, pivot=pivot)
    assert math.dist(object_space.to_world(placed, (0.0, 0.0, 0.0)), centre) < 1e-12
    assert _angle_between(_forward(aimed), tuple(t - c for t, c in zip(target, centre))) < 1e-6
    assert aimed.scale == eye.transform.scale


def test_the_turn_is_the_shortest_one_and_clamped():
    eye = _eye()
    aimed = eg.aimed_transform(eye, (0.0, 0.0, 5.0))  # straight ahead: no turn
    assert _angle_between(_forward(aimed), (0.0, 0.0, 1.0)) < 1e-9
    assert _angle_between(tuple(aimed.rotation[i][1] for i in range(3)), (0.0, 1.0, 0.0)) < 1e-9
    side = eg.aimed_transform(eye, (5.0, 0.0, 5.0))  # 45 degrees right: a pure yaw, no roll (Listing)
    assert abs(_angle_between(_forward(side), (0.0, 0.0, 1.0)) - 45.0) < 1e-9
    assert _angle_between(tuple(side.rotation[i][1] for i in range(3)), (0.0, 1.0, 0.0)) < 1e-9
    behind = eg.aimed_transform(eye, (0.0, 0.0, -5.0))  # never into the skull
    assert abs(_angle_between(_forward(behind), (0.0, 0.0, 1.0)) - eg.MAX_GAZE_DEGREES) < 1e-9
    assert eg.aimed_transform(eye, (0.0, 0.0, 0.0)) == eye.transform  # target at the centre


def test_two_eyes_converge_on_a_near_point():
    left, right = _eye((-0.3, 0.0, 0.0), oid=1), _eye((0.3, 0.0, 0.0), oid=2)
    frame = eg.gaze_frame([left, right])
    assert frame.center == (0.0, 0.0, 0.0) and frame.forward == (0.0, 0.0, 1.0) and frame.right == (1.0, 0.0, 0.0)
    target = eg.pad_target(frame, 0.0, 0.0, 10.0)  # 10 radii = 1 unit ahead
    assert math.dist(target, (0.0, 0.0, 1.0)) < 1e-12
    assert _forward(eg.aimed_transform(left, target))[0] > 0.0 > _forward(eg.aimed_transform(right, target))[0]


def test_pad_target_and_pad_angles_are_inverse():
    frame = eg.gaze_frame([_eye(rotation=_yaw(30.0))])
    for yaw, pitch in ((0.0, 0.0), (25.0, -10.0), (-40.0, 30.0)):
        angles = eg.pad_angles(frame, eg.pad_target(frame, yaw, pitch, 20.0))
        assert abs(angles[0] - yaw) < 1e-9 and abs(angles[1] - pitch) < 1e-9


def test_gaze_state_is_validated():
    assert eg.GazeState().mode == "rest"
    for bad in (dict(mode="look"), dict(focus=0.5), dict(focus=float("nan")), dict(target=(0.0, 1.0))):
        with pytest.raises(ValueError):
            eg.GazeState(**bad)


# -- app path --------------------------------------------------------------------------------------------------------


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _drawn_forward(app, eye):
    m = app.viewport.object_entries[eye.id].model_matrix
    return (m[8], m[9], m[10]), (m[12], m[13], m[14])


def test_rest_draws_the_eyes_own_rotation(app):
    eye = app.add_eye()
    assert app.display.eye_gaze.mode == "rest"
    assert app.viewport.object_entries[eye.id].model_matrix == object_space.model_matrix(eye)
    assert app.eye_gaze_angles() is None


def test_camera_mode_follows_the_orbit_without_touching_the_document(app):
    eye = app.add_eye()
    transform, undo_depth = eye.transform, len(app._selection_undo_stack)
    app.camera.set_view(0.4, 0.2)  # within MAX_GAZE_DEGREES of the eye's rest direction (+Z)
    assert app.set_eye_gaze(mode="camera") is True and "camera" in app.status_message
    forward, centre = _drawn_forward(app, eye)
    to_camera = tuple(c - p for c, p in zip(app.camera.eye(), centre))
    assert _angle_between(forward, to_camera) < 1e-4
    app.camera.orbit(-0.6, 0.1)
    app.update_viewport(0.016)  # the frame tick turns the eyes after the camera
    forward, centre = _drawn_forward(app, eye)
    assert _angle_between(forward, tuple(c - p for c, p in zip(app.camera.eye(), centre))) < 1e-4
    assert eye.transform is transform and len(app._selection_undo_stack) == undo_depth
    assert app.set_eye_gaze(mode="rest") is True
    assert app.viewport.object_entries[eye.id].model_matrix == object_space.model_matrix(eye)


def test_mouse_mode_follows_the_cursor_and_target_freezes_it(app):
    eye = app.add_eye()
    app.set_eye_gaze(mode="mouse")
    app.pointer_motion(400, 300)
    app.update_viewport(0.016)
    first = app.eye_gaze_angles()
    app.pointer_motion(650, 300)  # cursor to the right
    app.update_viewport(0.016)
    second = app.eye_gaze_angles()
    assert second[0] > first[0]
    app.pointer_leave()  # cursor over a panel / outside: the eyes keep the point
    app.update_viewport(0.016)
    assert app.eye_gaze_angles() == second
    assert app.set_eye_gaze(mode="target") is True
    frozen = app.display.eye_gaze.target
    assert frozen is not None and app.eye_gaze_angles() == pytest.approx(second)
    app.camera.orbit(0.4, 0.0)
    app.update_viewport(0.016)
    assert app.display.eye_gaze.target == frozen and app.eye_gaze_angles() == pytest.approx(second)
    assert eye.transform.rotation == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def test_pad_angles_and_focus(app):
    app.add_eye()
    assert app.set_eye_gaze_angles(20.0, -10.0) is True and app.display.eye_gaze.mode == "target"
    assert app.eye_gaze_angles() == pytest.approx((20.0, -10.0))
    assert app.set_eye_gaze(focus=60.0) is True  # the direction stays, the point moves out
    assert app.eye_gaze_angles() == pytest.approx((20.0, -10.0))
    assert app.set_eye_gaze(focus=1.0) is False and "focus" in app.status_message
    assert app.set_eye_gaze(mode="look") is False and "gaze mode" in app.status_message


def test_pad_is_refused_without_an_eye(app):
    assert app.set_eye_gaze_angles(10.0, 0.0) is False and "no eye" in app.status_message


def test_gaze_is_not_saved(app, tmp_path):
    eye = app.add_eye()
    app.set_eye_gaze_angles(30.0, 0.0)
    path = tmp_path / "scene.mirai.json"
    assert app.save_scene_file(path) is True
    text = path.read_text(encoding="utf-8")
    saved = next(o for o in json.loads(text)["objects"] if o["id"] == int(eye.id))
    assert "gaze" not in text
    assert saved["transform"]["rotation"] == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
