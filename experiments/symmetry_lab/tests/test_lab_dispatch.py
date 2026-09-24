"""Dispatcher ohne Fenster (Handoff Slice 2 §7): Command → Lab-Aktion + Auswahl.

Echte Production-`Application`, -`OrbitCamera` und `pick_nearest_vertex`,
geladen mit `subd_cube`; kein GL-Kontext.
"""

from __future__ import annotations

import pytest

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input

from symmetry_lab.lab_bindings import SYMMETRY_LAB_CONTEXT, apply_lab_bindings
from symmetry_lab.lab_dispatch import CLICK_THRESHOLD_PX, LabDispatcher
from symmetry_lab.lab_scene import load_asset_into

W, H = 1280, 800
ALT_LMB = Input("mouse", "LEFT", frozenset({"alt"}))
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))
LMB = Input("mouse", "LEFT")
MMB = Input("mouse", "MIDDLE")
RMB = Input("mouse", "RIGHT")


@pytest.fixture
def app():
    app = Application()
    apply_lab_bindings(app.bindings)
    load_asset_into(app, "subd_cube")
    return app


@pytest.fixture
def dispatcher(app):
    return LabDispatcher(app, W, H)


def camera_state(app):
    c = app.camera
    return (c.yaw, c.pitch, c.distance, c.target)


def screen_pos(app, vid):
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), W, H)


def rightmost_vertex(app):
    """Vertex mit eindeutig größtem Bildschirm-x (keine Überlagerung beim Pick)."""
    return max(app.scene.mesh.all_vertex_ids(), key=lambda v: screen_pos(app, v)[0])


def click(dispatcher, x, y, inp=LMB):
    dispatcher.press(inp)
    return dispatcher.release(inp.value, x, y)


# -- Kamera-Gesten ------------------------------------------------------------


def test_alt_lmb_drag_orbits_until_release(app, dispatcher):
    yaw, pitch = app.camera.yaw, app.camera.pitch
    dispatcher.press(ALT_LMB)
    assert dispatcher.active_command == cmd.ORBIT
    dispatcher.drag(20, 10)
    assert app.camera.yaw != yaw and app.camera.pitch != pitch
    dispatcher.release("LEFT", 0, 0)
    assert dispatcher.active_command is None
    assert app.scene.selection.vertices == set()


@pytest.mark.parametrize("inp", [SHIFT_LMB, MMB])
def test_pan_gestures_move_target(app, dispatcher, inp):
    target = app.camera.target
    dispatcher.press(inp)
    assert dispatcher.active_command == cmd.PAN
    dispatcher.drag(15, 0)
    assert app.camera.target != target
    dispatcher.release(inp.value, 0, 0)
    assert dispatcher.active_command is None


def test_gesture_holds_command_until_same_button_releases(app, dispatcher):
    dispatcher.press(ALT_LMB)
    dispatcher.press(MMB)  # zweiter Press während der Geste: ignoriert
    dispatcher.release("MIDDLE", 0, 0)  # fremde Taste beendet die Geste nicht
    assert dispatcher.active_command == cmd.ORBIT
    target = app.camera.target
    dispatcher.drag(10, 0)
    assert app.camera.target == target  # weiterhin Orbit, kein Pan
    dispatcher.release("LEFT", 0, 0)
    assert dispatcher.active_command is None


def test_wheel_zooms(app, dispatcher):
    d = app.camera.distance
    dispatcher.scroll(Input("wheel", "UP"))
    assert app.camera.distance < d
    d = app.camera.distance
    dispatcher.scroll(Input("wheel", "DOWN"))
    assert app.camera.distance > d
    d = app.camera.distance
    dispatcher.scroll(None)  # wheel_from_pyglet(0) → None: kein Zoom
    assert app.camera.distance == d


def test_rmb_is_unbound_in_lab(app, dispatcher):
    before = camera_state(app)
    dispatcher.press(RMB)
    assert dispatcher.active_command is None
    dispatcher.drag(40, 40)
    dispatcher.release("RIGHT", 10, 10)
    assert camera_state(app) == before


def test_foreign_commands_are_noops(app, dispatcher):
    # Globaler Default (Taste f → SetFaceMode) und ein Maus-Input, der im
    # Lab-Kontext auf ein fremdes Command auflöst: beide ohne Wirkung.
    assert dispatcher.resolve(Input("key", "f")) == cmd.SET_FACE_MODE
    ctrl_lmb = Input("mouse", "LEFT", frozenset({"ctrl"}))
    app.bindings.set_default(ctrl_lmb, cmd.UNDO, context=SYMMETRY_LAB_CONTEXT)
    before = camera_state(app)
    for inp in (Input("key", "f"), ctrl_lmb):
        dispatcher.press(inp)
        assert dispatcher.active_command is None
        dispatcher.drag(30, 30)
        assert dispatcher.release(inp.value, 5, 5) is False
    assert camera_state(app) == before
    assert app.scene.selection.vertices == set()


# -- Auswahl ------------------------------------------------------------------


def test_click_on_vertex_replaces_selection(app, dispatcher):
    vid = rightmost_vertex(app)
    other = next(v for v in app.scene.mesh.all_vertex_ids() if v != vid)
    app.scene.selection.set({other})
    x, y = screen_pos(app, vid)
    assert click(dispatcher, x, y) is True
    assert app.scene.selection.vertices == {vid}


def test_click_into_empty_space_clears_selection(app, dispatcher):
    app.scene.selection.set({rightmost_vertex(app)})
    assert click(dispatcher, 2, 2) is True
    assert app.scene.selection.vertices == set()


def test_select_runs_on_release_below_threshold(app, dispatcher):
    vid = rightmost_vertex(app)
    x, y = screen_pos(app, vid)
    dispatcher.press(LMB)
    dispatcher.drag(1, 1)
    assert app.scene.selection.vertices == set()  # erst bei Release
    assert dispatcher.release("LEFT", x, y) is True
    assert app.scene.selection.vertices == {vid}


def test_lmb_drag_over_threshold_does_not_select(app, dispatcher):
    vid = rightmost_vertex(app)
    x, y = screen_pos(app, vid)
    before = camera_state(app)
    dispatcher.press(LMB)
    dispatcher.drag(CLICK_THRESHOLD_PX, 0)
    assert dispatcher.release("LEFT", x, y) is False
    assert app.scene.selection.vertices == set()
    assert camera_state(app) == before
