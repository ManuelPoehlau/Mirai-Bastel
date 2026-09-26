"""Application: Navigation über Bindings + PointerGestures (WP-06 B2, AD-019).

Headless (TraceStore), kein pyglet/Fenster. Prüft den Pfad
Input → BindingSet → PointerGestures → Application → Camera/Viewport.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from mirai.application import (
    DOLLY_IN_FACTOR,
    DOLLY_OUT_FACTOR,
    ORBIT_RADIANS_PER_PX,
    Application,
)
from mirai.interaction.input import Input

WIDTH, HEIGHT = 800, 600


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


def _wheel(direction: str) -> Input:
    return Input("wheel", direction)


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _camera_state(app: Application):
    cam = app.camera
    return (cam.yaw, cam.pitch, cam.target, cam.distance)


def _drag(app: Application, inp: Input, steps, release_at=(0, 0)) -> None:
    app.pointer_press(inp)
    for dx, dy in steps:
        app.pointer_drag(dx, dy)
    app.pointer_release(inp.value, *release_at)


def test_constants_moved_unchanged():
    assert ORBIT_RADIANS_PER_PX == 0.005
    assert (DOLLY_IN_FACTOR, DOLLY_OUT_FACTOR) == (0.9, 1.1)


def test_set_viewport_size_pushes_aspect(app):
    rm = app.viewport.render_mesh
    rev = rm.dirty.camera_rev
    app.set_viewport_size(1000, 500)
    assert rm.aspect == pytest.approx(2.0)
    assert rm.dirty.camera_rev == rev + 1


def test_alt_lmb_drag_orbits(app):
    yaw, pitch, target, distance = _camera_state(app)
    rev = app.viewport.render_mesh.dirty.camera_rev
    _drag(app, _mouse("LEFT", "alt"), [(4, 0), (6, -2)])
    # Voller Weg (10, -2), inkl. des bis zur Schwelle aufgelaufenen Deltas.
    assert app.camera.yaw == pytest.approx(yaw - 10 * ORBIT_RADIANS_PER_PX)
    assert app.camera.pitch == pytest.approx(pitch + 2 * ORBIT_RADIANS_PER_PX)
    assert app.camera.target == target
    assert app.camera.distance == distance
    assert app.viewport.render_mesh.dirty.camera_rev > rev


def test_alt_click_does_not_orbit(app):
    before = _camera_state(app)
    _drag(app, _mouse("LEFT", "alt"), [(1, 1)])
    assert _camera_state(app) == before


def test_alt_shift_lmb_drag_pans(app):
    yaw, pitch, target, distance = _camera_state(app)
    _drag(app, _mouse("LEFT", "alt", "shift"), [(10, 5)])
    assert app.camera.target != target
    assert (app.camera.yaw, app.camera.pitch, app.camera.distance) == (yaw, pitch, distance)


@pytest.mark.parametrize(
    "inp",
    [
        _mouse("LEFT"),
        _mouse("LEFT", "shift"),
        _mouse("LEFT", "ctrl"),
        _mouse("RIGHT"),
        _mouse("MIDDLE"),
        _mouse("RIGHT", "alt"),
    ],
)
def test_other_drags_change_no_camera(app, inp):
    before = _camera_state(app)
    rev = app.viewport.render_mesh.dirty.camera_rev
    _drag(app, inp, [(20, 10), (15, -5)])
    assert _camera_state(app) == before
    assert app.viewport.render_mesh.dirty.camera_rev == rev


def test_wheel_dollies(app):
    distance = app.camera.distance
    assert app.pointer_scroll(_wheel("UP"))
    assert app.camera.distance == pytest.approx(distance * DOLLY_IN_FACTOR)
    assert app.pointer_scroll(_wheel("DOWN"))
    assert app.camera.distance == pytest.approx(distance * DOLLY_IN_FACTOR * DOLLY_OUT_FACTOR)


def test_navigation_leaves_mesh_and_history_untouched(app):
    mesh = app.scene.mesh
    positions = {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}
    _drag(app, _mouse("LEFT", "alt"), [(30, 10)])
    _drag(app, _mouse("LEFT", "alt", "shift"), [(30, 10)])
    app.pointer_scroll(_wheel("UP"))
    assert {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()} == positions
    assert not app.history.can_undo()


def test_pointer_before_init_scene_does_not_crash():
    app = Application()
    app.set_viewport_size(WIDTH, HEIGHT)
    _drag(app, _mouse("LEFT", "alt"), [(10, 0)])
    assert app.pointer_scroll(_wheel("UP"))
