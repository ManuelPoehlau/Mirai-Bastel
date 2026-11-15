"""Inflate / Pinch in the app (2026-11-15, `PROVISIONAL`): hold Shift+I / Shift+P like S (Smooth).

Hold + drag: the signed amount follows the horizontal motion live, computed from the press state; release = one History
entry, Esc = exact start state, a tap or a drag back to zero records nothing. Soft: the gesture's own field, the
wheel (also Shift+wheel, the key's own modifier) steps the radius live. Alt+P cycles the sticky Pinch direction.
Under symmetry pairs stay exact and seam points on the plane. Same gates as S: not under a held W, refused in mode `4`.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from core import SelectionMode
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.soft_selection import SoftBands
from tests.mesh_invariants import assert_mesh_invariants
from tests.test_application_delete_dissolve import _app, _grid_vertex, _select, _topology
from tests.test_application_smooth import _bumpy_soft_app
from tests.test_symmetric_ops import PAIRED_ASSETS, assert_clean, make_app


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


INFLATE, PINCH, CYCLE, W, ESC = _key("i", "shift"), _key("p", "shift"), _key("p", "alt"), _key("w"), _key("ESCAPE")
UNDO, REDO = _key("z", "ctrl"), _key("y", "ctrl")


def _hold(app, key: Input, motions=(), release=True):
    app.pointer_motion(400.0, 300.0)
    assert app.key_press(key) is True, app.status_message
    x = 400.0
    for dx in motions:
        x += dx
        app.pointer_motion(x, 300.0, dx, 0.0)
    if release:
        app.key_release(Input("key", key.value))


def _positions(mesh) -> dict:
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


def test_bindings_are_free_engineering_keys():
    app = _app(2)
    assert app.bindings.command_for(INFLATE) == cmd.INFLATE
    assert app.bindings.command_for(PINCH) == cmd.PINCH
    assert app.bindings.command_for(CYCLE) == cmd.PINCH_DIRECTION_CYCLE
    # I and P keep their own commands.
    assert app.bindings.command_for(_key("i")) == cmd.LOOP_INSERT
    assert app.bindings.command_for(_key("p")) == cmd.PIVOT_PLACE


def test_inflate_drag_moves_along_the_normal_and_commits_once():
    app = _app(4)
    mesh = app.scene.mesh
    centre = _grid_vertex(app, 2, 2)
    _select(app, SelectionMode.VERTEX, {centre})
    before = _positions(mesh)
    _hold(app, INFLATE, motions=[20.0, 20.0], release=False)
    out = mesh.vertex_position(centre)
    assert out[:2] == before[centre][:2] and out[2] != 0.0
    app.key_release(Input("key", "i"))
    assert len(app.history) == 1 and app.history._undo_stack[-1].description == "Inflate"
    assert app.status_message.startswith("Inflate committed")
    after = _positions(mesh)
    assert {v for v in after if after[v] != before[v]} == {centre}
    app.key_press(UNDO)
    assert _positions(mesh) == before
    app.key_press(REDO)
    assert _positions(mesh) == after


def test_right_and_left_are_opposite_and_back_to_zero_records_nothing():
    app = _app(4)
    mesh = app.scene.mesh
    centre = _grid_vertex(app, 2, 2)
    _select(app, SelectionMode.VERTEX, {centre})
    z0 = mesh.vertex_position(centre)[2]
    _hold(app, INFLATE, motions=[30.0], release=False)
    right = mesh.vertex_position(centre)[2] - z0
    app.pointer_motion(340.0, 300.0, -60.0, 0.0)
    left = mesh.vertex_position(centre)[2] - z0
    assert right == pytest.approx(-left) and right != 0.0
    app.pointer_motion(370.0, 300.0, 30.0, 0.0)
    assert mesh.vertex_position(centre)[2] == z0
    app.key_release(Input("key", "i"))
    assert len(app.history) == 0 and app.status_message == "Inflate: no change"


def test_a_tap_changes_nothing_and_esc_restores_exactly():
    app = _app(4)
    mesh = app.scene.mesh
    _select(app, SelectionMode.VERTEX, {_grid_vertex(app, 2, 2)})
    before = mesh.export_state()
    _hold(app, PINCH)
    assert mesh.export_state() == before and len(app.history) == 0
    assert "no change" in app.status_message
    _hold(app, INFLATE, motions=[25.0, 25.0], release=False)
    assert mesh.export_state() != before
    app.key_press(ESC)
    app.key_release(Input("key", "i"))
    assert mesh.export_state() == before and len(app.history) == 0


def test_refused_in_object_mode_and_under_a_held_w():
    app = _app(4)
    _select(app, SelectionMode.VERTEX, {_grid_vertex(app, 2, 2)})
    app.key_press(W)
    assert app.key_press(INFLATE) is False
    app.key_release(W)
    app.key_press(_key("4"))
    assert app.key_press(PINCH) is False
    assert "Object mode" in app.status_message


def test_nothing_selected_refuses():
    app = _app(4)
    _select(app, SelectionMode.VERTEX, set())
    app.selection.hovered = None
    assert app.key_press(INFLATE) is False
    assert app.status_message == "Inflate: nothing selected"


def test_the_pinch_direction_cycles_and_is_read_at_the_press():
    app = _bumpy_soft_app()
    mesh = app.scene.mesh
    assert app._gestures.pinch_direction == "radial"
    assert app.key_press(CYCLE) and app.status_message == "Pinch direction: loop"
    edge_seeds = {_grid_vertex(app, 4, 3), _grid_vertex(app, 4, 4)}
    _select(app, SelectionMode.VERTEX, edge_seeds)
    before = _positions(mesh)
    _hold(app, PINCH, motions=[40.0, 40.0])
    assert app.history._undo_stack[-1].description == "Pinch (loop)"
    moved = {v for v in before if mesh.vertex_position(v) != before[v]}
    assert moved and all(mesh.vertex_position(v)[0] == before[v][0] for v in moved)  # across the loop (y) only
    app.key_press(UNDO)
    assert app.key_press(CYCLE) and app._gestures.pinch_direction == "ring"
    assert app.key_press(CYCLE) and app._gestures.pinch_direction == "radial"


def test_pinch_loop_without_soft_is_refused_with_a_hint():
    app = _app(4)
    _select(app, SelectionMode.VERTEX, {_grid_vertex(app, 2, 1), _grid_vertex(app, 2, 2)})
    app.key_press(CYCLE)
    assert app.key_press(PINCH) is False
    assert app.status_message.startswith("Pinch (loop): switch Soft Selection on")


# -- Soft -----------------------------------------------------------------------------------------------------------


def test_soft_inflate_shows_its_weights_and_the_wheel_steps_the_radius_live():
    app = _bumpy_soft_app()
    mesh = app.scene.mesh
    seed = _grid_vertex(app, 4, 4)
    _select(app, SelectionMode.VERTEX, {seed})
    before = _positions(mesh)
    _hold(app, INFLATE, motions=[30.0], release=False)
    session = app._gestures.session
    assert app._soft_bands == SoftBands.from_weights(session.plan.weights)
    small = {v for v in before if mesh.vertex_position(v) != before[v]}
    distance = app.camera.distance
    for wheel in (Input("wheel", "UP"), Input("wheel", "UP", frozenset({"shift"})), Input("wheel", "UP"),
                  Input("wheel", "UP", frozenset({"shift"}))):
        assert app.pointer_scroll(wheel) is True  # plain wheel and the held key's own Shift+wheel
    assert app.camera.distance == distance
    large = {v for v in before if mesh.vertex_position(v) != before[v]}
    assert small < large
    app.key_release(Input("key", "i"))
    assert len(app.history) == 1
    live = _positions(mesh)
    app.key_press(UNDO)
    assert _positions(mesh) == before
    # The live result is the gesture begun at that radius with the same motion (no drift, no accumulation).
    _hold(app, INFLATE, motions=[30.0])
    assert _positions(mesh) == live


def test_esc_after_a_live_radius_step_restores_exactly():
    app = _bumpy_soft_app()
    mesh = app.scene.mesh
    _select(app, SelectionMode.VERTEX, {_grid_vertex(app, 4, 4)})
    before = mesh.export_state()
    _hold(app, PINCH, motions=[40.0], release=False)
    app.pointer_scroll(Input("wheel", "UP"))
    app.key_press(ESC)
    app.key_release(Input("key", "p"))
    assert mesh.export_state() == before and len(app.history) == 0


# -- symmetry -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
@pytest.mark.parametrize("key", [INFLATE, PINCH], ids=["inflate", "pinch"])
def test_symmetric_soft_gesture_stays_exactly_symmetric(asset, key):
    app = make_app(asset)
    mesh = app.scene.mesh
    app.key_press(_key("o"))
    for _ in range(12):  # a wide field, clamped at the largest step (the SubD cube has 26 points)
        app.pointer_scroll(Input("wheel", "UP", frozenset({"shift"})))
    seed = max((v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] > 0.0), key=lambda v: (
        mesh.vertex_position(v)[0], -int(v)))
    _select(app, SelectionMode.VERTEX, {seed})
    before = _topology(mesh)
    faces = {f: tuple(mesh.face_vertices(f)) for f in mesh.all_face_ids()}
    _hold(app, key, motions=[30.0, 30.0])
    assert len(app.history) == 1, app.status_message
    assert _topology(mesh) != before
    assert {f: tuple(mesh.face_vertices(f)) for f in mesh.all_face_ids()} == faces
    assert_clean(mesh)
    assert_mesh_invariants(mesh)
    app.key_press(UNDO)
    assert _topology(mesh) == before
