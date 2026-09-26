"""Application: Navigation + Vertex-Selektion über Bindings (WP-06 B2, AD-019).

Headless (TraceStore), kein pyglet/Fenster. Prüft den Pfad
Input → BindingSet → PointerGestures → Application → Camera/Selection/Viewport.
Selektion = Playground-Modifier-Variante (AP-03): LMB ersetzt, Shift fügt
hinzu, Ctrl entfernt, Alt togglet; Klick ins Leere leert nur ohne Modifier.
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


# -- Vertex-Selektion (Modifier-Variante) ---------------------------------------

MISS = (2.0, 2.0)  # Bildecke: weit weg von jedem Würfel-Vertex


def _screen_pos(app: Application, vid):
    pos = app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT)
    assert pos is not None
    return pos


def _two_vertices(app: Application):
    vids = sorted(app.scene.mesh.all_vertex_ids())
    return vids[0], vids[-1]


def _click(app: Application, inp: Input, at) -> None:
    app.pointer_press(inp)
    app.pointer_release(inp.value, *at)


def _selection_rev(app: Application) -> int:
    return app.viewport.render_mesh.dirty.selection_rev


def test_miss_position_really_misses(app):
    from mirai.viewport.picking import pick_nearest_vertex

    assert pick_nearest_vertex(app.camera, app.scene.mesh, *MISS, WIDTH, HEIGHT) is None


def test_click_replaces(app):
    a, b = _two_vertices(app)
    _click(app, _mouse("LEFT"), _screen_pos(app, a))
    assert app.selection.vertices == {a}
    _click(app, _mouse("LEFT"), _screen_pos(app, b))
    assert app.selection.vertices == {b}


def test_click_on_empty_space_clears(app):
    a, _ = _two_vertices(app)
    _click(app, _mouse("LEFT"), _screen_pos(app, a))
    _click(app, _mouse("LEFT"), MISS)
    assert app.selection.is_empty()


def test_shift_click_adds(app):
    a, b = _two_vertices(app)
    _click(app, _mouse("LEFT"), _screen_pos(app, a))
    _click(app, _mouse("LEFT", "shift"), _screen_pos(app, b))
    assert app.selection.vertices == {a, b}


def test_ctrl_click_removes(app):
    a, b = _two_vertices(app)
    app.selection.set({a, b})
    _click(app, _mouse("LEFT", "ctrl"), _screen_pos(app, a))
    assert app.selection.vertices == {b}


def test_alt_click_toggles_on_and_off(app):
    a, b = _two_vertices(app)
    app.selection.set({b})
    _click(app, _mouse("LEFT", "alt"), _screen_pos(app, a))
    assert app.selection.vertices == {a, b}
    _click(app, _mouse("LEFT", "alt"), _screen_pos(app, a))
    assert app.selection.vertices == {b}


@pytest.mark.parametrize("mods", [("shift",), ("ctrl",), ("alt",)])
def test_modifier_click_on_empty_space_keeps_selection(app, mods):
    a, b = _two_vertices(app)
    app.selection.set({a, b})
    rev = _selection_rev(app)
    _click(app, _mouse("LEFT", *mods), MISS)
    assert app.selection.vertices == {a, b}
    assert _selection_rev(app) == rev


def test_small_movement_is_still_a_click(app):
    a, _ = _two_vertices(app)
    app.pointer_press(_mouse("LEFT"))
    app.pointer_drag(2, 1)
    app.pointer_release("LEFT", *_screen_pos(app, a))
    assert app.selection.vertices == {a}


def test_lmb_drag_selects_nothing(app):
    a, _ = _two_vertices(app)
    app.pointer_press(_mouse("LEFT"))
    app.pointer_drag(10, 0)
    app.pointer_release("LEFT", *_screen_pos(app, a))
    assert app.selection.is_empty()


def test_alt_drag_orbits_without_toggling(app):
    a, _ = _two_vertices(app)
    yaw = app.camera.yaw
    app.pointer_press(_mouse("LEFT", "alt"))
    app.pointer_drag(8, 0)
    app.pointer_release("LEFT", *_screen_pos(app, a))
    assert app.camera.yaw != yaw
    assert app.selection.is_empty()


def test_viewport_selection_dirty_only_on_real_change(app):
    a, b = _two_vertices(app)
    rev = _selection_rev(app)
    _click(app, _mouse("LEFT"), _screen_pos(app, a))
    assert _selection_rev(app) == rev + 1
    _click(app, _mouse("LEFT"), _screen_pos(app, a))  # gleiche Auswahl
    _click(app, _mouse("LEFT", "shift"), _screen_pos(app, a))  # schon drin
    _click(app, _mouse("LEFT", "ctrl"), _screen_pos(app, b))  # nicht drin
    assert _selection_rev(app) == rev + 1
    _click(app, _mouse("LEFT"), MISS)
    assert _selection_rev(app) == rev + 2
    _click(app, _mouse("LEFT"), MISS)  # schon leer
    assert _selection_rev(app) == rev + 2


def test_selection_reaches_highlight_flags(app):
    a, _ = _two_vertices(app)
    app.viewport.sync()
    flags_before = list(app.viewport.render_mesh.store.data("highlight_flags"))
    _click(app, _mouse("LEFT"), _screen_pos(app, a))
    app.viewport.sync()
    assert list(app.viewport.render_mesh.store.data("highlight_flags")) != flags_before


def test_selection_creates_no_history_and_keeps_mesh(app):
    a, b = _two_vertices(app)
    mesh = app.scene.mesh
    positions = {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}
    _click(app, _mouse("LEFT"), _screen_pos(app, a))
    _click(app, _mouse("LEFT", "shift"), _screen_pos(app, b))
    _click(app, _mouse("LEFT", "alt"), _screen_pos(app, a))
    _click(app, _mouse("LEFT"), MISS)
    assert not app.history.can_undo()
    assert {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()} == positions


def test_selection_stays_in_vertex_mode(app):
    from core import SelectionMode

    a, _ = _two_vertices(app)
    _click(app, _mouse("LEFT"), _screen_pos(app, a))
    assert app.selection.mode is SelectionMode.VERTEX
    assert not app.selection.edges and not app.selection.faces
