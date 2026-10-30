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


# -- Soft Selection (C2 follow-up, Manu 2026-10-24) --------------------------------------------------


def _bumpy_soft_app(n: int = 8):
    """n×n grid with a height pattern on every interior point, Soft bands overlay attached, Soft on."""
    from mirai.soft_selection import GLSoftBandOverlay
    from tests.test_application_delete_dissolve import _build_grid

    app = Application()
    app.init_scene("cube", soft_overlay_type=GLSoftBandOverlay)
    mesh = _build_grid(n)
    for v in mesh.all_vertex_ids():
        x, y, _ = mesh.vertex_position(v)
        if 0 < x < n and 0 < y < n:
            mesh.set_vertex_position(v, (x, y, 0.3 * (((int(x) * 7 + int(y) * 3) % 5) - 2)))
    app.scene.mesh.load_state(mesh.export_state())
    app.viewport.on_topology_changed()
    app.frame_scene()
    app.set_viewport_size(800, 600)
    app.key_press(_key("o"))  # Soft on
    for _ in range(5):  # radius a little above two grid edges
        app.pointer_scroll(Input("wheel", "UP", frozenset({"shift"})))
    assert app.soft_settings.enabled and 1.5 < app.soft_settings.world_radius < 3.0
    return app


def _moved(before: dict, mesh) -> dict:
    return {
        v: sum(abs(a - b) for a, b in zip(mesh.vertex_position(v), p))
        for v, p in before.items()
        if mesh.vertex_position(v) != p
    }


def test_soft_smooth_reaches_the_falloff_and_fades_out():
    app = _bumpy_soft_app()
    mesh = app.scene.mesh
    seed = _grid_vertex(app, 4, 4)
    _select(app, SelectionMode.VERTEX, {seed})
    weights = app._gestures.smooth_soft_weights({seed}, app.soft_settings)
    inside = {v for v, w in weights.items() if 0.0 < w < 1.0}
    outside = set(mesh.all_vertex_ids()) - set(weights)
    assert inside and outside
    before = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    _hold(app, S)
    moved = _moved(before, mesh)
    assert seed in moved
    assert moved.keys() - {seed} and moved.keys() <= set(weights)  # falloff points move, nothing outside
    assert not (outside & moved.keys())
    assert len(app.history) == 1
    app.key_press(_key("z", "ctrl"))
    assert {v: mesh.vertex_position(v) for v in before} == before


def test_soft_weights_scale_the_step():
    app = _bumpy_soft_app()
    seed = _grid_vertex(app, 4, 4)
    _select(app, SelectionMode.VERTEX, {seed})
    assert app.key_press(S)
    plan = app._gestures.session.plan
    assert plan.weights is not None and plan.weights[seed] == 1.0
    full = plan.positions(1.0)
    import dataclasses

    flat = dataclasses.replace(plan, weights={v: 1.0 for v in plan.weights})
    unweighted = flat.positions(1.0)
    falloff = next(v for v, w in plan.weights.items() if 0.0 < w < 1.0 and full[v] != plan.start[v])
    step = [a - b for a, b in zip(full[falloff], plan.start[falloff])]
    step_full = [a - b for a, b in zip(unweighted[falloff], plan.start[falloff])]
    ratio = sum(abs(x) for x in step) / sum(abs(x) for x in step_full)
    assert ratio == pytest.approx(plan.weights[falloff], rel=1e-9)
    app.key_press(ESC)
    app.key_release(_key("s"))


def test_the_bands_show_the_gesture_weights_and_the_preview_resumes():
    from mirai.soft_selection import EMPTY_BANDS, SoftBands

    app = _bumpy_soft_app()
    seed = _grid_vertex(app, 4, 4)
    _select(app, SelectionMode.VERTEX, {seed})
    app._soft_preview_refresh()
    preview = app._soft_bands
    assert preview != EMPTY_BANDS
    _hold(app, S, motions=[30.0], release=False)
    assert _op_running(app)
    assert app._soft_bands == SoftBands.from_weights(app._gestures.session.plan.weights) != EMPTY_BANDS
    app.key_release(_key("s"))
    assert not _op_running(app)
    assert app._soft_bands != EMPTY_BANDS  # the preview resumed



def _op_running(app) -> bool:
    """The running gesture shows its own weights (`GestureSession.soft_op_running`); no gesture, no op."""
    gesture = app._gestures.session
    return gesture is not None and gesture.soft_op_running


def test_the_wheel_changes_the_radius_live_and_never_zooms():
    app = _bumpy_soft_app()
    mesh = app.scene.mesh
    seed = _grid_vertex(app, 4, 4)
    _select(app, SelectionMode.VERTEX, {seed})
    before = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    _hold(app, S, motions=[40.0, 40.0], release=False)
    small = set(_moved(before, mesh))
    distance = app.camera.distance
    step = app.soft_settings.radius_step
    for _ in range(4):
        assert app.pointer_scroll(Input("wheel", "UP")) is True
    assert app.camera.distance == distance
    assert app.soft_settings.radius_step == step + 4
    large = set(_moved(before, mesh))
    assert small < large
    assert app._soft_bands == __import__("mirai.soft_selection", fromlist=["SoftBands"]).SoftBands.from_weights(
        app._gestures.session.plan.weights
    )
    app.key_release(_key("s"))
    assert len(app.history) == 1
    app.key_press(_key("z", "ctrl"))
    assert {v: mesh.vertex_position(v) for v in before} == before


def test_the_wheel_before_the_drag_sets_the_radius_of_the_tap():
    app = _bumpy_soft_app()
    mesh = app.scene.mesh
    seed = _grid_vertex(app, 4, 4)
    _select(app, SelectionMode.VERTEX, {seed})
    before = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    app.pointer_motion(400.0, 300.0)
    app.key_press(S)
    small = set(app._gestures.session.plan.movable)
    for _ in range(4):
        app.pointer_scroll(Input("wheel", "UP"))
    assert set(app._gestures.session.plan.movable) > small
    assert {v: mesh.vertex_position(v) for v in before} == before  # nothing moved yet
    app.key_release(_key("s"))
    assert set(_moved(before, mesh)) - small


def test_esc_after_a_live_radius_step_restores_exactly():
    app = _bumpy_soft_app()
    mesh = app.scene.mesh
    _select(app, SelectionMode.VERTEX, {_grid_vertex(app, 4, 4)})
    before = mesh.export_state()
    _hold(app, ALT_S, motions=[40.0], release=False)
    app.pointer_scroll(Input("wheel", "UP"))
    app.pointer_scroll(Input("wheel", "UP"))
    app.key_press(ESC)
    app.key_release(_key("s"))
    assert mesh.export_state() == before and len(app.history) == 0


def test_soft_off_is_unchanged():
    app, centre = _bumped_app()
    assert not app.soft_settings.enabled
    _select(app, SelectionMode.VERTEX, {centre})
    assert app.key_press(S)
    assert app._gestures.session.plan.weights is None and app._gestures.session.soft is None
    app.key_release(_key("s"))


@pytest.mark.parametrize("asset", PAIRED_ASSETS)
@pytest.mark.parametrize("key", [S, ALT_S], ids=["smooth", "relax"])
def test_symmetric_soft_smooth_stays_exactly_symmetric(asset, key):
    app = make_app(asset)
    mesh = app.scene.mesh
    app.key_press(_key("o"))
    for _ in range(12):  # a wide field, clamped at the largest step
        app.pointer_scroll(Input("wheel", "UP", frozenset({"shift"})))

    def laplacian(v):
        ring = [w for e in mesh.vertex_edges(v) for w in mesh.edge_vertices(e) if w != v]
        mean = [sum(mesh.vertex_position(w)[i] for w in ring) / len(ring) for i in range(3)]
        return sum(abs(m - p) for m, p in zip(mean, mesh.vertex_position(v)))

    seed = max(
        (
            v for v in mesh.all_vertex_ids()
            if mesh.vertex_position(v)[0] > 0.0
            and all(len(mesh.edge_faces(e)) == 2 for e in mesh.vertex_edges(v))
        ),
        key=lambda v: (laplacian(v), -int(v)),
    )
    _select(app, SelectionMode.VERTEX, {seed})
    weights = app._gestures.smooth_soft_weights({seed}, app.soft_settings)
    assert len(weights) > 2  # the field reaches beyond the seed and its partner
    before = _topology(mesh)
    if key is ALT_S:
        app.set_alt_held(True)
    _hold(app, key, motions=[40.0], release=False)
    app.pointer_scroll(Input("wheel", "DOWN"))
    app.key_release(Input("key", "s"))
    app.set_alt_held(False)
    assert len(app.history) == 1
    assert _topology(mesh) != before
    assert_clean(mesh)
