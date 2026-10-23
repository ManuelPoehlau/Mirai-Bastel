"""Smooth / Relax in the app (WP Toolbox Gaps C2): hold S / Alt+S like G (Loop Slide).

A tap (press, release, no motion) = one fixed step, one History entry. Hold + drag: the strength follows
the horizontal motion live (right more, left less, down to the start), computed from the press state;
release = one entry, Esc = exact start state. Border points stay fixed; under symmetry pairs stay exact
and seam points on the plane. Same gates as G: not under a held W/E/R/T, refused in mode `4`.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from core import SelectionMode
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from tests.mesh_invariants import assert_mesh_invariants
from tests.test_application_delete_dissolve import _app, _grid_vertex, _select, _topology
from tests.test_symmetric_ops import PAIRED_ASSETS, assert_clean, make_app


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


S, ALT_S, W, ESC = _key("s"), _key("s", "alt"), _key("w"), _key("ESCAPE")


def _bumped_app() -> tuple[Application, object]:
    """4×4 grid with the centre point lifted; returns (app, centre vertex)."""
    app = _app(4)
    mesh = app.scene.mesh
    centre = _grid_vertex(app, 2, 2)
    mesh.set_vertex_position(centre, (2.0, 2.0, 1.0))
    app.viewport.on_topology_changed()
    return app, centre


def _hold(app, key: Input, motions=(), release=True):
    app.pointer_motion(400.0, 300.0)
    assert app.key_press(key) is True
    x = 400.0
    for dx in motions:
        x += dx
        app.pointer_motion(x, 300.0, dx, 0.0)
    if release:
        app.key_release(Input("key", key.value))


def test_bindings():
    app = _app(2)
    assert app.bindings.command_for(S) == cmd.SMOOTH
    assert app.bindings.command_for(ALT_S) == cmd.RELAX
    assert app.bindings.command_for(_key("s", "shift")) == cmd.SYMMETRY_CYCLE


def test_a_tap_is_one_step_and_one_undo_entry():
    app, centre = _bumped_app()
    mesh = app.scene.mesh
    _select(app, SelectionMode.VERTEX, {centre})
    before = _topology(mesh)
    _hold(app, S)
    z = mesh.vertex_position(centre)[2]
    assert 0.0 < z < 1.0
    assert len(app.history) == 1 and app.history._undo_stack[-1].description == "Smooth"
    assert app.status_message == "Smooth: one step"
    app.key_press(_key("z", "ctrl"))
    assert _topology(mesh) == before
    app.key_press(_key("y", "ctrl"))
    assert mesh.vertex_position(centre)[2] == z


def test_hold_and_drag_follows_the_strength_live_and_commits_once():
    app, centre = _bumped_app()
    mesh = app.scene.mesh
    _select(app, SelectionMode.VERTEX, {centre})
    _hold(app, S, motions=[30.0], release=False)
    after_right = mesh.vertex_position(centre)[2]
    app.pointer_motion(460.0, 300.0, 30.0, 0.0)
    further = mesh.vertex_position(centre)[2]
    assert further < after_right < 1.0
    app.pointer_motion(430.0, 300.0, -30.0, 0.0)  # back: computed from the press state again
    assert mesh.vertex_position(centre)[2] == after_right
    app.key_release(_key("s"))
    assert len(app.history) == 1
    assert_mesh_invariants(mesh)


def test_dragging_back_to_zero_records_nothing():
    app, centre = _bumped_app()
    _select(app, SelectionMode.VERTEX, {centre})
    _hold(app, S, motions=[30.0, -60.0])
    assert app.scene.mesh.vertex_position(centre) == (2.0, 2.0, 1.0)
    assert len(app.history) == 0
    assert app.status_message == "Smooth: no change"


def test_esc_restores_the_start_exactly():
    app, centre = _bumped_app()
    mesh = app.scene.mesh
    _select(app, SelectionMode.VERTEX, {centre})
    before = mesh.export_state()
    _hold(app, S, motions=[50.0, 50.0], release=False)
    assert mesh.vertex_position(centre) != (2.0, 2.0, 1.0)
    assert app.key_press(ESC) is True
    assert mesh.export_state() == before
    app.key_release(_key("s"))
    assert mesh.export_state() == before and len(app.history) == 0


def test_relax_on_alt_s_keeps_a_flat_grid_flat_and_alt_does_not_orbit():
    app = _app(4)
    mesh = app.scene.mesh
    centre = _grid_vertex(app, 2, 2)
    mesh.set_vertex_position(centre, (2.4, 1.7, 0.0))
    app.viewport.on_topology_changed()
    _select(app, SelectionMode.FACE, set(mesh.all_face_ids()))
    camera = (app.camera.yaw, app.camera.pitch)
    app.set_alt_held(True)
    _hold(app, ALT_S, motions=[40.0, 40.0], release=False)
    assert (app.camera.yaw, app.camera.pitch) == camera
    app.key_release(_key("s"))
    app.set_alt_held(False)
    assert app.history._undo_stack[-1].description == "Relax"
    assert all(mesh.vertex_position(v)[2] == 0.0 for v in mesh.all_vertex_ids())
    x, y, _ = mesh.vertex_position(centre)
    assert abs(x - 2.0) + abs(y - 2.0) < 0.4 + 0.3


def test_border_points_stay_and_only_border_is_refused():
    app = _app(2)
    mesh = app.scene.mesh
    corner = _grid_vertex(app, 0, 0)
    _select(app, SelectionMode.VERTEX, {corner})
    assert app.key_press(S) is False
    assert "border" in app.status_message
    assert len(app.history) == 0
    _select(app, SelectionMode.VERTEX, set(mesh.all_vertex_ids()))
    border = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids() if v != _grid_vertex(app, 1, 1)}
    _hold(app, S)
    assert {v: mesh.vertex_position(v) for v in border} == border


def test_refused_in_object_mode_and_under_a_held_w():
    app, centre = _bumped_app()
    _select(app, SelectionMode.VERTEX, {centre})
    app.key_press(W)
    assert app.key_press(S) is False
    app.key_release(W)
    app.key_press(_key("4"))
    assert app.key_press(S) is False
    assert "Object mode" in app.status_message


def test_nothing_selected_uses_the_hover_or_refuses():
    app, _ = _bumped_app()
    _select(app, SelectionMode.VERTEX, set())
    app.selection.hovered = None
    assert app.key_press(S) is False
    assert app.status_message == "Smooth: nothing selected"


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
@pytest.mark.parametrize("key", [S, ALT_S], ids=["smooth", "relax"])
def test_symmetric_smooth_stays_exactly_symmetric(asset, key):
    app = make_app(asset)
    mesh = app.scene.mesh
    plus = {v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] >= 0.0}
    _select(app, SelectionMode.VERTEX, plus)
    before = _topology(mesh)
    if key is ALT_S:
        app.set_alt_held(True)
    _hold(app, key, motions=[40.0, 40.0])
    app.set_alt_held(False)
    assert len(app.history) == 1
    assert _topology(mesh) != before
    assert_clean(mesh)
    app.key_press(_key("z", "ctrl"))
    assert _topology(mesh) == before
