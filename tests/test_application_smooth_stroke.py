"""The Smooth / Relax stroke (Brush research 2026-11-18 §6-§7, Manu 2026-11-23): while S / Alt+S is held, LMB and drag
dabs Smooth / Relax at the surface under the cursor; one History entry per stroke, Esc rolls the running stroke back.

A click is one dab (the selection stays), Alt+S takes Alt+LMB (no orbit), the key let go mid-stroke lets the stroke run
to the LMB release, after a stroke the release is no tap and the motion no dial, a dial already running is dropped by
the LMB press. Radius = the Soft radius (Soft may be off). Symmetry: pairs stay exact; a shown morph mix refuses.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from core import SelectionMode
from mirai.interaction.input import Input
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.soft_selection import RADIUS_STEPS_PERCENT
from mirai.symmetry import mirror_position, vertex_correspondence
from tests.mesh_invariants import assert_mesh_invariants
from tests.test_application_delete_dissolve import _app, _grid_vertex, _select
from tests.test_symmetric_ops import assert_clean, make_app


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


S, ALT_S, ESC = _key("s"), _key("s", "alt"), _key("ESCAPE")
LMB, ALT_LMB = Input("mouse", "LEFT", frozenset()), Input("mouse", "LEFT", frozenset({"alt"}))
N = 10
ON_PATH, OFF_PATH = 5, 2  # grid rows: the stroke runs along row 5; row 2 is three units away


def _bumpy_app():
    """10×10 grid, every interior point of rows 5 and 2 lifted by ±0.3 (alternating); the Soft radius at 5 %."""
    app = _app(N)
    mesh = app.scene.mesh
    for row in (ON_PATH, OFF_PATH):
        for col in range(1, N):
            v = _grid_vertex(app, row, col)
            mesh.set_vertex_position(v, (float(col), float(row), 0.3 if col % 2 else -0.3))
    app.viewport.on_topology_changed()
    step = RADIUS_STEPS_PERCENT.index(10)
    app._soft = app._soft.with_radius_step(step, mesh_center_and_radius(mesh)[1])  # Soft stays off
    return app


def _screen(app, point):
    return app._objects.edit_camera.project_to_screen(tuple(point), *app._services.viewport_size)


def _row_z(app, row):
    mesh = app.scene.mesh
    return [mesh.vertex_position(_grid_vertex(app, row, col))[2] for col in range(1, N)]


def _path(app, row=ON_PATH, cols=(2, 8), steps=24):
    mesh = app.scene.mesh
    a = _screen(app, mesh.vertex_position(_grid_vertex(app, row, cols[0]))[:2] + (0.0,))
    b = _screen(app, mesh.vertex_position(_grid_vertex(app, row, cols[1]))[:2] + (0.0,))
    return [(a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps) for i in range(steps + 1)]


def _arm(app, key=S, at=None):
    x, y = at
    app.pointer_motion(x, y)
    assert app.key_press(key) is True, app.status_message


def _stroke(app, points, button=LMB, release=True):
    x, y = points[0]
    app.pointer_press(button, x, y)
    for (px, py), (qx, qy) in zip(points, points[1:]):
        app.pointer_drag(qx - px, qy - py, qx, qy)
    if release:
        app.pointer_release("LEFT", *points[-1])


def test_a_stroke_smooths_along_its_way_and_is_one_undo_entry():
    app = _bumpy_app()
    mesh = app.scene.mesh
    off_before = _row_z(app, OFF_PATH)
    on_before = _row_z(app, ON_PATH)
    selection = app._services.selection_snapshot()
    before = mesh.export_state()
    path = _path(app)
    _arm(app, S, path[0])
    _stroke(app, path)
    app.key_release(_key("s"))
    on_after = _row_z(app, ON_PATH)
    assert sum(abs(z) for z in on_after[1:8]) < 0.5 * sum(abs(z) for z in on_before[1:8])
    assert _row_z(app, OFF_PATH) == off_before  # out of the radius: untouched, bit for bit
    assert len(app.history) == 1 and app.history._undo_stack[-1].description == "Smooth stroke"
    assert app._services.selection_snapshot() == selection
    assert app._gesture is None
    assert_mesh_invariants(mesh)
    after = mesh.export_state()
    app.key_press(_key("z", "ctrl"))
    assert mesh.export_state() == before
    app.key_press(_key("y", "ctrl"))
    assert mesh.export_state() == after


def test_two_strokes_in_one_hold_are_two_entries_and_the_release_is_no_tap():
    app = _bumpy_app()
    path = _path(app)
    _arm(app, S, path[0])
    _stroke(app, path[:12])
    _stroke(app, path[12:])
    app.key_release(_key("s"))
    assert [c.description for c in app.history._undo_stack] == ["Smooth stroke", "Smooth stroke"]


def test_a_click_is_one_dab_and_keeps_the_selection():
    app = _bumpy_app()
    mesh = app.scene.mesh
    corner = _grid_vertex(app, 1, 1)
    _select(app, SelectionMode.VERTEX, {corner})
    selection = app._services.selection_snapshot()
    target = _grid_vertex(app, ON_PATH, 5)
    z0 = mesh.vertex_position(target)[2]
    point = _screen(app, mesh.vertex_position(target)[:2] + (0.0,))
    _arm(app, S, point)
    app.pointer_press(LMB, *point)
    app.pointer_release("LEFT", *point)
    assert abs(mesh.vertex_position(target)[2]) < abs(z0)
    assert app._services.selection_snapshot() == selection
    assert mesh.vertex_position(corner) == (1.0, 1.0, 0.0)  # the armed selection was not smoothed
    app.key_release(_key("s"))
    assert len(app.history) == 1


def test_esc_rolls_the_running_stroke_back_exactly():
    app = _bumpy_app()
    mesh = app.scene.mesh
    before = mesh.export_state()
    path = _path(app)
    _arm(app, S, path[0])
    _stroke(app, path, release=False)
    assert mesh.export_state() != before
    assert app.key_press(ESC) is True
    assert mesh.export_state() == before
    app.pointer_drag(5.0, 0.0, path[-1][0] + 5.0, path[-1][1])
    app.pointer_release("LEFT", path[-1][0] + 5.0, path[-1][1])
    app.key_release(_key("s"))
    assert mesh.export_state() == before and len(app.history) == 0


def test_the_key_let_go_mid_stroke_lets_the_stroke_run_to_the_lmb_release():
    app = _bumpy_app()
    path = _path(app)
    _arm(app, S, path[0])
    _stroke(app, path[:12], release=False)
    app.key_release(_key("s"))
    assert app._gesture is not None
    z_mid = _row_z(app, ON_PATH)
    for (px, py), (qx, qy) in zip(path[11:], path[12:]):
        app.pointer_drag(qx - px, qy - py, qx, qy)
    assert _row_z(app, ON_PATH) != z_mid  # still dabbing
    app.pointer_release("LEFT", *path[-1])
    assert app._gesture is None
    assert len(app.history) == 1


def test_relax_stroke_on_alt_s_takes_alt_lmb_and_does_not_orbit():
    app = _bumpy_app()
    path = _path(app)
    camera = (app.camera.yaw, app.camera.pitch, app.camera.distance)
    app.set_alt_held(True)
    _arm(app, ALT_S, path[0])
    _stroke(app, path, button=ALT_LMB)
    app.key_release(_key("s", "alt"))
    app.set_alt_held(False)
    assert (app.camera.yaw, app.camera.pitch, app.camera.distance) == camera
    assert [c.description for c in app.history._undo_stack] == ["Relax stroke"]


def test_an_lmb_press_drops_a_running_dial():
    app = _bumpy_app()
    mesh = app.scene.mesh
    seed = _grid_vertex(app, 8, 8)
    mesh.set_vertex_position(seed, (8.0, 8.0, 0.5))
    _select(app, SelectionMode.VERTEX, {seed})
    path = _path(app)
    app.pointer_motion(*path[0])
    assert app.key_press(S) is True
    app.pointer_motion(path[0][0] + 40.0, path[0][1], 40.0, 0.0)  # the dial smooths the selected point
    assert mesh.vertex_position(seed)[2] < 0.5
    _stroke(app, path)
    assert mesh.vertex_position(seed)[2] == 0.5  # the press dropped the dial
    app.pointer_motion(path[-1][0] + 40.0, path[-1][1], 40.0, 0.0)  # after a stroke: no dial
    assert mesh.vertex_position(seed)[2] == 0.5
    app.key_release(_key("s"))
    assert [c.description for c in app.history._undo_stack] == ["Smooth stroke"]


def test_masked_points_stay():
    app = _bumpy_app()
    mesh = app.scene.mesh
    held = [_grid_vertex(app, ON_PATH, c) for c in (4, 5)]
    app._mask.set(held)
    before = {v: mesh.vertex_position(v) for v in held}
    path = _path(app)
    _arm(app, S, path[0])
    _stroke(app, path)
    app.key_release(_key("s"))
    assert {v: mesh.vertex_position(v) for v in held} == before
    assert len(app.history) == 1


def test_a_dialled_in_morph_target_refuses_the_stroke():
    app = _bumpy_app()
    mesh = app.scene.mesh
    lid = app.create_morph_target("Smile")
    assert lid is not None, app.status_message
    assert app.set_morph_weight(40, lid), app.status_message
    before, entries = mesh.export_state(), len(app.history)
    path = _path(app)
    _arm(app, S, path[0])
    _stroke(app, path)
    assert "morph target is dialled in" in app.status_message
    app.key_release(_key("s"))
    assert mesh.export_state() == before and len(app.history) == entries


def test_symmetric_stroke_keeps_the_pairs_exact():
    app = make_app("head_basemesh")
    mesh = app.scene.mesh
    camera = app._objects.edit_camera
    width, height = app._services.viewport_size
    centre = (width / 2.0, height / 2.0)
    face = app._services.pick_face(*centre)
    assert face is not None
    path = [(centre[0] - 60.0 + 5.0 * i, centre[1] + 2.0 * i) for i in range(25)]
    _arm(app, S, path[0])
    _stroke(app, path)
    app.key_release(_key("s"))
    assert len(app.history) == 1, app.status_message
    definition = mesh.symmetry_definition
    for vid, corr in vertex_correspondence(mesh).items():
        if corr.partner is not None and corr.partner != vid:
            expected = mirror_position(mesh.vertex_position(corr.partner), definition.plane_point,
                                       definition.plane_normal)
            assert mesh.vertex_position(vid) == pytest.approx(expected, abs=1e-12)
    assert_clean(mesh)
    assert camera is app._objects.edit_camera


def test_inflate_has_no_stroke_yet():
    app = _bumpy_app()
    path = _path(app)
    app.pointer_motion(*path[0])
    assert app.key_press(_key("i", "shift")) is True, app.status_message
    selection = app._services.selection_snapshot()
    _stroke(app, path)
    app.key_release(_key("i", "shift"))
    assert all(c.description != "Smooth stroke" for c in app.history._undo_stack)
    assert app._services.selection_snapshot() == selection
