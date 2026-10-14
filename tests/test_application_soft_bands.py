"""Application: the Soft Selection influence bands in the window (WP-SOFT-01 S2b, AD-020 §5;
PROVISIONAL).

Headless (TraceStore); the sink is the real `GLSoftBandOverlay`, whose data side needs no GL
context. Pins the handoff's E1-E5 contracts:

- soft off ≡ today: nothing computed, nothing pushed, no overlay work;
- the preview comes from the selection and is recomputed once per triggering event
  (selection, mode, settings, scene load, Undo/Redo, topology / mesh change, gesture end) -
  never from hover and never per pointer move;
- preview weights == the op's weights at `begin()` (F9); during a gesture the overlay shows the
  op's weights at the live positions; the preview resumes after commit / cancel / Undo;
- a hover-armed gesture computes its bands once, at arm (F11).
"""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401  (puts examples/ on sys.path)

from core import VertexId
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.soft_selection import (
    BAND_LAYERS,
    EMPTY_BANDS,
    GLSoftBandOverlay,
    SoftBands,
    compute_influence,
)

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


W, E, R = _key("w"), _key("e"), _key("r")
O, SHIFT_O, CTRL_O = _key("o"), _key("o", "shift"), _key("o", "ctrl")
ESC, CTRL_Z, CTRL_Y = _key("ESCAPE"), _key("z", "ctrl"), _key("y", "ctrl")
SHIFT_WHEEL_UP = Input("wheel", "UP", frozenset({"shift"}))
KEY_1, KEY_2 = _key("1"), _key("2")
ALT_O = _key("o", "alt")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("obj", obj_path=HEAD_OBJ, soft_overlay_type=GLSoftBandOverlay)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


@pytest.fixture
def influence_calls(monkeypatch) -> list[tuple]:
    """Every influence computation of the app path: the preview (`mirai.application`) and
    the tools' `begin()` (`move`, `transform`)."""
    calls: list[tuple] = []
    import mirai.application as application_module
    import mirai.interaction.tools.move as move_module
    import mirai.interaction.tools.transform as transform_module

    for module in (application_module, move_module, transform_module):
        original = module.compute_influence

        def spy(mesh, seeds, radius, *args, _where=module.__name__, _original=original, **kwargs):
            calls.append((_where, frozenset(seeds)))
            return _original(mesh, seeds, radius, *args, **kwargs)

        monkeypatch.setattr(module, "compute_influence", spy)
    return calls


def _preview_calls(calls) -> list:
    return [c for c in calls if c[0] == "mirai.application"]


def _front_vertices(app) -> list[VertexId]:
    """Vertex ids nearest to the camera first (visible, so a click picks them)."""
    eye = app.camera.eye()
    mesh = app.scene.mesh
    return sorted(mesh.all_vertex_ids(), key=lambda v: math.dist(mesh.vertex_position(v), eye))


def _screen(app, vid) -> tuple[float, float]:
    return app.camera.project_to_screen(
        app.scene.mesh.vertex_position(vid), app.viewport_width, app.viewport_height
    )


def _click_select(app, vid: VertexId) -> None:
    x, y = _screen(app, vid)
    assert app.select_at(cmd.SELECT, x, y)
    assert app.selection.vertices == {vid}


def _overlay(app) -> GLSoftBandOverlay:
    return app._soft_overlay


def _expected(app, seeds) -> SoftBands:
    soft = app.soft_settings
    return SoftBands.from_weights(
        compute_influence(
            app.scene.mesh, seeds, soft.world_radius, soft.metric, soft.curve, soft.curve_power
        )
    )


def _move(app, motions=((6, 2), (5, 3), (4, -1))) -> None:
    for dx, dy in motions:
        app.pointer_motion(300.0, 300.0, float(dx), float(dy))


def _band_vertex_positions(app) -> list:
    """Positions of the band vertices, in the layer order of the overlay."""
    mesh = app.scene.mesh
    return [[mesh.vertex_position(v) for v in band] for band in app.soft_bands.bands]


def _overlay_points(app) -> list:
    return [_overlay(app).points(layer) for layer in BAND_LAYERS]


# -- wiring -------------------------------------------------------------------------


def test_overlay_is_attached_as_an_extra_overlay(app):
    assert isinstance(_overlay(app), GLSoftBandOverlay)
    assert app.viewport.extra_overlays == [_overlay(app)]
    assert app.soft_bands == EMPTY_BANDS


def test_no_soft_overlay_type_means_no_overlay_and_no_influence_work(influence_calls):
    app = Application()
    app.init_scene("obj", obj_path=HEAD_OBJ)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    assert app.viewport.extra_overlays == []
    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    assert app.soft_bands == EMPTY_BANDS
    assert influence_calls == []


# -- soft off ≡ today -----------------------------------------------------------------


def test_soft_off_nothing_computed_nothing_pushed(app, influence_calls):
    _click_select(app, _front_vertices(app)[0])
    assert app.key_press(KEY_2) is True  # mode change
    assert app.key_press(KEY_1) is True
    _click_select(app, _front_vertices(app)[3])
    assert app.key_press(W)
    _move(app)
    assert app.key_release(W)
    assert app.key_press(CTRL_Z)
    app.update_viewport(0.016)
    assert influence_calls == []
    assert _overlay(app).pushes == 0
    assert app.soft_bands == EMPTY_BANDS
    assert _overlay_points(app) == [[], [], [], []]


# -- preview triggers (E3) -------------------------------------------------------------


def test_preview_from_selection_with_soft_on(app, influence_calls):
    assert app.key_press(O)
    assert influence_calls == []  # nothing selected: nothing to show, nothing computed
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    assert len(_preview_calls(influence_calls)) == 1
    assert app.soft_bands == _expected(app, {vid})
    assert app.soft_bands.count > 0
    assert vid not in app.soft_bands.weights  # the seed keeps the selection look
    app.update_viewport(0.016)
    assert _overlay_points(app) == _band_vertex_positions(app)


def test_toggle_on_with_an_existing_selection_shows_bands(app, influence_calls):
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    assert app.soft_bands == EMPTY_BANDS
    assert app.key_press(O)
    assert len(_preview_calls(influence_calls)) == 1
    assert app.soft_bands == _expected(app, {vid})


def test_soft_off_clears_the_bands(app):
    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    assert app.soft_bands.count > 0
    assert app.key_press(O)
    assert app.soft_bands == EMPTY_BANDS
    app.update_viewport(0.016)
    assert _overlay_points(app) == [[], [], [], []]


def test_radius_curve_and_metric_each_recompute_once(app, influence_calls):
    assert app.key_press(O)
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    influence_calls.clear()

    before = app.soft_bands
    assert app.pointer_scroll(SHIFT_WHEEL_UP)
    assert len(_preview_calls(influence_calls)) == 1
    assert app.soft_bands == _expected(app, {vid})
    assert app.soft_bands.count > before.count  # larger radius, more points

    assert app.key_press(SHIFT_O)
    assert len(_preview_calls(influence_calls)) == 2
    assert app.soft_settings.curve == "sphere"
    assert app.soft_bands == _expected(app, {vid})

    assert app.key_press(CTRL_O)
    assert len(_preview_calls(influence_calls)) == 3
    assert app.soft_settings.metric == "euclidean"
    assert app.soft_bands == _expected(app, {vid})


def test_radius_at_the_end_of_the_list_computes_nothing(app, influence_calls):
    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    for _ in range(20):
        app.pointer_scroll(SHIFT_WHEEL_UP)
    influence_calls.clear()
    assert app.pointer_scroll(SHIFT_WHEEL_UP) is False  # clamped, unchanged
    assert influence_calls == []


def test_mode_change_clears_selection_and_bands(app, influence_calls):
    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    assert app.soft_bands.count > 0
    assert app.key_press(KEY_2)
    assert app.selection.vertices == set() and app.soft_bands == EMPTY_BANDS


def test_selection_change_replaces_the_bands(app):
    assert app.key_press(O)
    a, b = _front_vertices(app)[0], _front_vertices(app)[40]
    _click_select(app, a)
    first = app.soft_bands
    _click_select(app, b)
    assert app.soft_bands == _expected(app, {b}) != first
    assert app.select_at(cmd.SELECT, 1.0, 1.0)  # a click into empty space clears
    assert app.selection.vertices == set()
    assert app.soft_bands == EMPTY_BANDS


def test_edge_mode_selection_previews_from_the_edge_vertices(app):
    assert app.key_press(O)
    assert app.key_press(_key("2"))
    mesh = app.scene.mesh
    edge = mesh.vertex_edges(_front_vertices(app)[0])[0]
    app.selection.set({edge})
    app.viewport.on_selection_changed()
    assert app.key_press(SHIFT_O)  # any event: the preview is rebuilt
    seeds = set(mesh.edge_vertices(edge))
    assert app.soft_bands == _expected(app, seeds)


def test_scene_load_recomputes(app, influence_calls):
    assert app.key_press(O)
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    influence_calls.clear()
    app.init_scene("obj", obj_path=HEAD_OBJ, soft_overlay_type=GLSoftBandOverlay)
    assert len(_preview_calls(influence_calls)) == 1
    assert app.viewport.extra_overlays == [_overlay(app)]
    assert app.soft_bands == _expected(app, {vid})
    app.update_viewport(0.016)
    assert _overlay_points(app) == _band_vertex_positions(app)


def test_apply_mesh_change_recomputes_once_for_moves_and_topology(app, influence_calls):
    assert app.key_press(O)
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    influence_calls.clear()
    mesh = app.scene.mesh

    def nudge():
        x, y, z = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (x + 0.05, y, z))
        return {vid}

    assert app.apply_mesh_change("nudge", nudge)
    assert len(_preview_calls(influence_calls)) == 1
    assert app.soft_bands == _expected(app, {vid})

    influence_calls.clear()
    edge = mesh.vertex_edges(_front_vertices(app)[5])[0]
    assert app.apply_mesh_change("split", lambda: mesh.split_edge(edge) and None)
    assert len(_preview_calls(influence_calls)) == 1
    assert app.soft_bands == _expected(app, {vid})


def test_undo_and_redo_recompute_once_each(app, influence_calls):
    assert app.key_press(O)
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    pre = app.soft_bands
    assert app.key_press(W)
    _move(app)
    assert app.key_release(W)
    committed = app.soft_bands
    assert committed != pre

    influence_calls.clear()
    assert app.key_press(CTRL_Z)
    assert len(_preview_calls(influence_calls)) == 1
    assert app.soft_bands == pre  # exact positions back -> the same bands

    influence_calls.clear()
    assert app.key_press(CTRL_Y)
    assert len(_preview_calls(influence_calls)) == 1
    assert app.soft_bands == committed


# -- no recompute on hover / pointer motion ---------------------------------------------


def test_hover_and_pointer_motion_never_compute_influence(app, influence_calls):
    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    influence_calls.clear()
    bands = app.soft_bands
    pushes = _overlay(app).pushes
    for vid in _front_vertices(app)[:25]:
        x, y = _screen(app, vid)
        app.pointer_motion(x, y, 1.0, 1.0)
        app.update_viewport(0.016)
    assert app.selection.hovered is not None  # hover really changed along the way
    app.pointer_leave()
    app.update_viewport(0.016)
    assert influence_calls == []
    assert app.soft_bands is bands and _overlay(app).pushes == pushes


def test_hover_alone_shows_no_bands(app, influence_calls):
    assert app.key_press(O)
    x, y = _screen(app, _front_vertices(app)[0])
    app.pointer_motion(x, y, 1.0, 1.0)
    assert app.selection.hovered is not None
    assert influence_calls == [] and app.soft_bands == EMPTY_BANDS


# -- preview == begin weights (F9) --------------------------------------------------------


@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_preview_weights_equal_the_ops_weights_at_begin(app, key):
    assert app.key_press(O)
    assert app.pointer_scroll(SHIFT_WHEEL_UP)
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    preview = app.soft_bands
    assert app.key_press(key)
    _move(app, ((4, 1),))
    influence = app.tool_manager.active_tool.operation.context.params["influence"]
    shown = {v: w for v, w in influence.items() if 0.0 < w < 1.0}
    assert preview.weights == shown  # exact: one function, one radius, one start state
    assert app.soft_bands == preview
    assert app.key_release(key)


# -- during a gesture -----------------------------------------------------------------------


def test_gesture_shows_the_ops_weights_at_live_positions_without_recomputing(app, influence_calls):
    assert app.key_press(O)
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    influence_calls.clear()
    assert app.key_press(W)
    _move(app, ((6, 2),))
    # Exactly one computation for the whole gesture start: the tool's own `begin()`.
    assert [c[0] for c in influence_calls] == ["mirai.interaction.tools.move"]
    bands_at_begin = app.soft_bands
    assert bands_at_begin.count > 0

    start = _band_vertex_positions(app)
    _move(app, [(5, 3)] * 15)
    app.update_viewport(0.016)
    assert [c[0] for c in influence_calls] == ["mirai.interaction.tools.move"]  # no more
    assert app.soft_bands is bands_at_begin  # the op's weights, fixed
    now = _band_vertex_positions(app)
    assert now != start  # the points moved with the vertices ...
    assert _overlay_points(app) == now  # ... and the overlay shows exactly those positions
    assert app.key_release(W)


def test_settings_change_mid_gesture_leaves_the_bands_alone(app):
    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    assert app.key_press(W)
    _move(app, ((6, 2),))
    bands = app.soft_bands
    assert app.pointer_scroll(SHIFT_WHEEL_UP)
    assert app.key_press(SHIFT_O)
    assert app.soft_bands is bands
    assert app.key_release(W)
    # The new settings show up as soon as the gesture is over.
    assert app.soft_bands == _expected(app, app.selection.vertices)


def test_soft_off_mid_gesture_clears_bands_when_the_gesture_ends(app):
    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    assert app.key_press(W)
    _move(app, ((6, 2),))
    assert app.key_press(O)
    assert app.key_release(W)
    assert app.soft_bands == EMPTY_BANDS


def test_commit_resumes_the_preview_at_the_new_positions(app, influence_calls):
    assert app.key_press(O)
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    assert app.key_press(W)
    _move(app)
    influence_calls.clear()
    assert app.key_release(W)
    assert len(_preview_calls(influence_calls)) == 1
    assert app.soft_bands == _expected(app, {vid})
    app.update_viewport(0.016)
    assert _overlay_points(app) == _band_vertex_positions(app)


def test_cancel_restores_the_preview_exactly(app):
    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    before = app.soft_bands
    assert app.key_press(W)
    _move(app)
    assert app.key_press(ESC)
    assert app.soft_bands == before
    app.update_viewport(0.016)
    assert _overlay_points(app) == _band_vertex_positions(app)


def test_tap_without_motion_keeps_the_preview(app, influence_calls):
    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    before = app.soft_bands
    influence_calls.clear()
    assert app.key_press(W)
    assert app.key_release(W)
    assert influence_calls == [] and app.soft_bands is before


def test_armed_but_not_begun_takes_new_settings_in_the_preview(app):
    assert app.key_press(O)
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    assert app.key_press(W)
    assert app.pointer_scroll(SHIFT_WHEEL_UP)
    assert app.soft_bands == _expected(app, {vid})
    assert app.key_press(ESC)


# -- hover-armed (F11) ---------------------------------------------------------------------


def test_hover_armed_gesture_computes_its_bands_once_at_arm(app, influence_calls):
    assert app.key_press(O)
    vid = _front_vertices(app)[0]
    x, y = _screen(app, vid)
    app.pointer_motion(x, y, 1.0, 1.0)
    assert app.selection.hovered == vid and app.selection.vertices == set()
    assert influence_calls == []

    assert app.key_press(W)  # arms on the hovered vertex
    assert [c[0] for c in influence_calls] == ["mirai.application"]
    assert app.soft_bands == _expected(app, {vid})
    assert app.soft_bands.count > 0

    influence_calls.clear()
    _move(app, ((6, 2),))
    assert [c[0] for c in influence_calls] == ["mirai.interaction.tools.move"]
    assert app.soft_bands.weights == {
        v: w
        for v, w in app.tool_manager.active_tool.operation.context.params["influence"].items()
        if 0.0 < w < 1.0
    }
    assert app.key_release(W)
    # The selection stays empty, so the preview has nothing to show afterwards.
    assert app.soft_bands == EMPTY_BANDS


def test_hover_armed_tap_and_cancel_leave_no_bands(app):
    assert app.key_press(O)
    x, y = _screen(app, _front_vertices(app)[0])
    app.pointer_motion(x, y, 1.0, 1.0)
    assert app.key_press(W)
    assert app.soft_bands.count > 0
    assert app.key_release(W)  # tap
    assert app.soft_bands == EMPTY_BANDS

    app.pointer_motion(x, y, 1.0, 1.0)
    assert app.key_press(W)
    _move(app, ((4, 1),))
    assert app.key_press(ESC)
    assert app.soft_bands == EMPTY_BANDS


def test_hover_armed_with_soft_off_shows_nothing(app, influence_calls):
    x, y = _screen(app, _front_vertices(app)[0])
    app.pointer_motion(x, y, 1.0, 1.0)
    assert app.key_press(W)
    assert influence_calls == [] and app.soft_bands == EMPTY_BANDS
    assert app.key_press(ESC)


# -- symmetry: no preview (bands on both sides are AD-SYM-04 D-5, slice SS3) -------------------


def test_no_preview_under_a_symmetry_definition(app):
    from core.mesh import SymmetryDefinition

    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    assert app.soft_bands.count > 0
    app.scene.mesh.symmetry_definition = SymmetryDefinition(
        plane_point=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0), seam_edges=frozenset()
    )
    assert app.key_press(SHIFT_O)  # any trigger
    assert app.soft_bands == EMPTY_BANDS


# -- bands switch (S2d E7, S2c verdict: "needs an option to switch the bands off") --------------


def test_bands_off_pushes_no_points_and_computes_nothing_for_display(app, influence_calls):
    assert app.key_press(O)
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    assert app.soft_bands.count > 0
    influence_calls.clear()
    pushes = _overlay(app).pushes
    assert app.key_press(ALT_O)
    assert app.soft_bands == EMPTY_BANDS  # the points are gone ...
    assert _overlay(app).pushes == pushes + 1
    assert influence_calls == []  # ... and nothing was computed for it
    app.update_viewport(0.016)
    assert _overlay_points(app) == [[], [], [], []]

    # Every event that would refresh the preview stays silent while the bands are off.
    assert app.pointer_scroll(SHIFT_WHEEL_UP)
    assert app.key_press(SHIFT_O) and app.key_press(CTRL_O)
    assert app.pointer_scroll(Input("wheel", "UP", frozenset({"ctrl"})))
    _click_select(app, _front_vertices(app)[7])
    assert app.key_press(KEY_2) and app.key_press(KEY_1)
    assert influence_calls == [] and _overlay(app).pushes == pushes + 1
    assert app.soft_bands == EMPTY_BANDS


def test_bands_back_on_restores_the_preview(app, influence_calls):
    assert app.key_press(O)
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    shown = app.soft_bands
    assert app.key_press(ALT_O)
    influence_calls.clear()
    assert app.key_press(ALT_O)
    assert len(_preview_calls(influence_calls)) == 1  # one computation for the switch-on
    assert app.soft_bands == shown == _expected(app, {vid})
    app.update_viewport(0.016)
    assert _overlay_points(app) == _band_vertex_positions(app)


def test_bands_off_gesture_still_deforms_softly_but_shows_nothing(app, influence_calls):
    assert app.key_press(O)
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    assert app.key_press(ALT_O)
    mesh = app.scene.mesh
    before = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    influence_calls.clear()
    assert app.key_press(W)
    _move(app)
    # The operation still computes its own influence (once, at begin) - the display adds nothing.
    assert [c[0] for c in influence_calls] == ["mirai.interaction.tools.move"]
    influence = app.tool_manager.active_tool.operation.context.params["influence"]
    assert len(influence) > 1  # a soft gesture: more than the seed
    assert app.soft_bands == EMPTY_BANDS and _overlay_points(app) == [[], [], [], []]
    assert app.key_release(W)
    moved = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v) != before[v]]
    assert set(moved) == set(influence)
    assert app.soft_bands == EMPTY_BANDS


def test_bands_off_hover_armed_gesture_shows_nothing(app, influence_calls):
    assert app.key_press(O)
    assert app.key_press(ALT_O)
    vid = _front_vertices(app)[0]
    x, y = _screen(app, vid)
    app.pointer_motion(x, y, 0.0, 0.0)
    assert app.selection.hovered is not None
    influence_calls.clear()
    assert app.key_press(W)
    assert _preview_calls(influence_calls) == []
    assert app.soft_bands == EMPTY_BANDS
    assert app.key_press(ESC)


def test_bands_toggled_on_mid_gesture_shows_when_the_gesture_ends(app):
    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    assert app.key_press(ALT_O)
    assert app.key_press(W)
    _move(app, ((6, 2),))
    assert app.key_press(ALT_O)
    assert app.soft_bands == EMPTY_BANDS  # a running gesture keeps its display
    assert app.key_release(W)
    assert app.soft_bands == _expected(app, app.selection.vertices)
    assert app.soft_bands.count > 0


def test_bands_toggled_off_mid_gesture_clears_when_the_gesture_ends(app):
    assert app.key_press(O)
    _click_select(app, _front_vertices(app)[0])
    assert app.key_press(W)
    _move(app, ((6, 2),))
    shown = app.soft_bands
    assert shown.count > 0
    assert app.key_press(ALT_O)
    assert app.soft_bands is shown
    assert app.key_release(W)
    assert app.soft_bands == EMPTY_BANDS


def test_custom_curve_preview_equals_the_ops_weights(app):
    assert app.key_press(O)
    app.pointer_scroll(Input("wheel", "DOWN", frozenset({"ctrl"})))  # custom, p = 1.5
    assert app.soft_settings.curve == "custom"
    vid = _front_vertices(app)[0]
    _click_select(app, vid)
    preview = app.soft_bands
    assert preview == _expected(app, {vid}) and preview.count > 0
    assert app.key_press(W)
    _move(app, ((4, 1),))
    influence = app.tool_manager.active_tool.operation.context.params["influence"]
    assert preview.weights == {v: w for v, w in influence.items() if 0.0 < w < 1.0}
    assert app.key_release(W)
