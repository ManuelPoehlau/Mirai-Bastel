"""R-1 (AD-038 §2.2, LD-D13), headless: entering, leaving or switching rooms - LookDev, the Paint Room, the Eye Lab -
never resets or changes the pose, the morph weights and current targets, the gaze or the SubD settings; a room that
cannot host the state refuses with a status line and changes nothing.

On `scenes/Gollum_Head_05.mirai.json` (a rig, morph targets, two eyes): the morphed head as the edit object in a pose
with a morph mix, gaze on, SubD on; the snapshot is compared bit for bit before and after every transition."""

from __future__ import annotations

import os

import pytest

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.interaction import commands
from mirai.morph_targets import morph_target_ids
from mirai.skinning import BonePose

SCENE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "scenes", "Gollum_Head_05.mirai.json")


def snapshot(app) -> dict:
    provider = app.morph.provider
    sub = app.subdivision
    return {
        "pose": {bid: (p.rotation, p.translation, p.scale) for bid, p in app.pose.items()},
        "morph": {oid: (dict(provider.object_weights(oid)), provider.current_target(oid)) for oid in app.scene.objects},
        "gaze": app.display.eye_gaze,
        "subd": (sub.view, sub.level, sub.cage_depth_test, sub.secondary_strength, sub.lines_shown),
    }


def _head(app):
    return next(obj for obj in app.scene.objects.values() if obj.name == "Gollum")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.set_viewport_size(800, 600)
    app.init_scene("file", scene_path=SCENE)
    head = _head(app)
    app.set_objects_hidden([head.id], False)
    app._objects.set_edit_object(head.id)
    return app


def _deform(app) -> None:
    """A pose (the jaw open), a morph mix, gaze on, SubD on."""
    head = app.scene.edit_object
    lids = morph_target_ids(head.mesh)
    assert app.set_morph_weight(40, lids[1]), app.status_message
    jaw = next(b.id for b in app.scene.rig.bones if b.name == "Kiefer")
    c, s = 0.9659258262890683, 0.25881904510252074  # 15 degrees about X
    app._skeleton.set_pose({jaw: BonePose(rotation=((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c)))})
    assert app.set_eye_gaze(mode="camera"), app.status_message
    assert app.subdivision.set_view("cage"), app.status_message
    _tick(app)  # as the app between two clicks: the SubD level cap and the posed / mixed surface settle here
    state = snapshot(app)
    assert state["pose"] and state["morph"][head.id][0] and state["gaze"].mode == "camera" and state["subd"][0] == "cage"


def _tick(app) -> None:
    app.update_viewport(1 / 60)


def _select_an_eye(app) -> None:
    app.dispatch_command(commands.SET_OBJECT_MODE)
    eye = next(obj for obj in app.scene.objects.values() if obj.eye is not None)
    assert app.select_objects([eye.id])


def test_entering_and_leaving_lookdev_keeps_the_deformation_state(app):
    _deform(app)
    before = snapshot(app)
    assert app.open_lookdev() and app.lookdev_open
    _tick(app)
    assert snapshot(app) == before
    assert app.close_lookdev() and not app.lookdev_open
    _tick(app)
    assert snapshot(app) == before


def test_lookdev_to_paint_room_in_a_pose_switches_and_changes_nothing(app):
    """Manu 2026-11-25 lifts P-8: the Paint Room opens in a pose and with a mix; LookDev closes (R-1)."""
    _deform(app)
    assert app.open_lookdev()
    before = snapshot(app)
    assert app.open_paint_room(), app.status_message
    assert app.paint_room_open and not app.lookdev_open
    _tick(app)
    assert snapshot(app) == before
    assert app.close_paint_room() and not app.paint_room_open
    _tick(app)
    assert snapshot(app) == before


def test_paint_room_opens_with_a_morph_mix_and_keeps_it(app):
    """Manu 2026-11-25: a target dialled in (e.g. mouth open, to paint inside the mouth) does not block the room."""
    head = app.scene.edit_object
    assert app.set_morph_weight(40, morph_target_ids(head.mesh)[1]), app.status_message
    _tick(app)
    assert app._query_cage() is not None  # the mix is what the window shows
    before = snapshot(app)
    assert app.open_paint_room(), app.status_message
    assert app.paint_room_open
    _tick(app)
    assert snapshot(app) == before
    assert app.close_paint_room() and not app.paint_room_open
    _tick(app)
    assert snapshot(app) == before


def test_a_stroke_paints_in_a_pose_with_a_mix(app):
    """Manu 2026-11-25 lifts P-8: the stroke lands on the posed, mixed surface the window shows."""
    from mirai.interaction.input import Input

    app.set_paint_resolution(1024)
    _deform(app)
    assert app.open_paint_room(), app.status_message
    obj = app.scene.edit_object
    width, height = app._services.viewport_size
    x, y = width / 2, height / 2
    app.pointer_motion(x, y)
    app.pointer_press(Input("mouse", "LEFT", frozenset()), x, y)
    for i in range(1, 13):
        app.pointer_drag(4.0, 0.0, x + 4 * i, y)
    app.pointer_release("LEFT", x + 48, y)
    assert obj.paint is not None and app.paint.pixels(obj, "Ebene 1")[..., 3].any()


def test_lookdev_and_paint_room_at_rest(app):
    before = snapshot(app)
    assert app.open_lookdev()
    assert app.open_paint_room(), app.status_message
    assert app.paint_room_open and not app.lookdev_open
    _tick(app)
    assert snapshot(app) == before
    assert app.open_lookdev()
    assert app.lookdev_open and not app.paint_room_open
    _tick(app)
    assert snapshot(app) == before
    app.close_lookdev()
    _tick(app)
    assert snapshot(app) == before


def test_eye_lab_to_lookdev_and_eye_lab_refused_inside(app):
    _deform(app)
    _select_an_eye(app)
    before = snapshot(app)
    assert app.open_eye_lab(), app.status_message
    assert app.open_lookdev() and app.lookdev_open and not app.eye_lab_open  # LD-D14: the Eye Lab closes
    _tick(app)
    assert snapshot(app) == before
    assert app.open_eye_lab() is False and app.status_message == "Eye Lab: erst LookDev schließen"
    assert app.lookdev_open and not app.eye_lab_open
    _tick(app)
    assert snapshot(app) == before
    app.close_lookdev()
    _tick(app)
    assert snapshot(app) == before
