"""Alt held during a transform (2026-10-22, `PROVISIONAL`, Manu "Alt halten um zu orbiten"): while W/E/R is held
or a gizmo / Tweak drag runs, the motion orbits (Alt+Shift: pans) instead of driving the gesture; letting Alt go
resumes it, and the release still commits one History step. Without a transform Alt alone does nothing."""

from __future__ import annotations

import pytest
from pyglet.window import key

import tests._bootstrap  # noqa: F401
from tests.test_application_gizmo import (  # noqa: F401  (app is a fixture)
    W,
    _key,
    _mouse,
    _on_handle,
    _screen,
    _select_center,
    app,
)
from tests.test_soft_selection_input import main_module


def _camera(app):
    return (app.camera.yaw, app.camera.pitch, tuple(app.camera.target))


def _move(app, dx, dy, steps=4, *, button=False):
    x, y = app._cursor
    for _ in range(steps):
        x, y = x + dx / steps, y + dy / steps
        if button:
            app.pointer_drag(dx / steps, dy / steps, x, y)
        else:
            app.pointer_motion(x, y, dx / steps, dy / steps)


def test_alt_during_a_held_key_orbits_and_leaves_the_mesh_alone(app):
    vid, pivot = _select_center(app)
    app.pointer_motion(*_screen(app, pivot))
    app.key_press(W)
    _move(app, 20.0, 0.0)
    moved = app.scene.mesh.vertex_position(vid)
    assert moved[0] > 0.0
    yaw = app.camera.yaw
    app.set_alt_held(True)
    _move(app, 40.0, 10.0)
    assert app.camera.yaw != yaw
    assert app.scene.mesh.vertex_position(vid) == moved
    app.set_alt_held(False)
    _move(app, 0.0, 20.0)
    assert app.scene.mesh.vertex_position(vid) != moved  # the gesture resumed
    app.key_release(W)
    app.key_press(_key("z", "ctrl"))
    assert app.scene.mesh.vertex_position(vid) == pytest.approx(pivot)  # still one undo step


def test_alt_shift_pans_instead(app):
    vid, pivot = _select_center(app)
    app.pointer_motion(*_screen(app, pivot))
    app.key_press(W)
    app.set_shift_held(True)
    app.set_alt_held(True)
    yaw, pitch, target = _camera(app)
    _move(app, 30.0, 0.0)
    assert (app.camera.yaw, app.camera.pitch) == (yaw, pitch)
    assert tuple(app.camera.target) != target
    assert app.scene.mesh.vertex_position(vid) == pivot
    app.set_alt_held(False)
    app.set_shift_held(False)
    app.key_release(W)


def test_alt_during_a_gizmo_drag_orbits_and_the_release_commits(app):
    vid, pivot = _select_center(app)
    start = _on_handle(app, pivot, (1.0, 0.0, 0.0))
    app.pointer_motion(*start)
    app.pointer_press(_mouse("LEFT"), *start)
    _move(app, 30.0, 0.0, button=True)
    moved = app.scene.mesh.vertex_position(vid)
    assert moved[0] > 0.0 and moved[1:] == (0.0, 0.0)  # X constraint
    yaw = app.camera.yaw
    app.set_alt_held(True)
    _move(app, 40.0, 0.0, button=True)
    assert app.camera.yaw != yaw
    assert app.scene.mesh.vertex_position(vid) == moved
    app.set_alt_held(False)
    _move(app, 10.0, 0.0, button=True)
    assert app.scene.mesh.vertex_position(vid) != moved
    assert app.pointer_release("LEFT", *app._cursor) is True
    assert app.transform_command is None
    app.key_press(_key("z", "ctrl"))
    assert app.scene.mesh.vertex_position(vid) == pytest.approx(pivot)


def test_alt_without_a_transform_does_not_orbit(app):
    before = _camera(app)
    app.pointer_motion(400.0, 300.0)
    app.set_alt_held(True)
    _move(app, 40.0, 10.0)
    app.set_alt_held(False)
    assert _camera(app) == before


def test_alt_keys_after_tracks_left_and_right_separately():
    after = main_module.alt_keys_after
    held = after(frozenset(), key.LALT, True)
    assert held == {key.LALT}
    both = after(held, key.RALT, True)
    assert after(both, key.LALT, False) == {key.RALT}
    assert after(held, key.LCTRL, True) is None
