"""Application: the soft bands under a symmetry definition (AD-SYM-04 D-5, slice SS3; look
`PROVISIONAL`, AD-020 §5).

- The preview is the symmetric field (`symmetric_influence`), both sides: partners in the same
  band, a seam vertex with its one weight; preview == the weights of the following gesture, bit
  for bit (W/E/R on `subd_cube` X/Z, `head_basemesh` X, both metrics).
- During the gesture the bands are the op's own weights: nothing is computed, neither the field
  nor the pairing.
- The preview is right again after commit, Undo/Redo, Shift+S and a scene load.
- A selection symmetric Soft refuses (D-2) shows no bands (`PROVISIONAL`), never plain Soft's.
- Cost (SS3 decision, `PROVISIONAL`): the preview takes its correspondence from the app's report
  cache, keyed by the geometry signature and shared with the symmetry display - a selection or
  settings trigger pairs nothing; a geometry change pairs once for both readers.
- Bands off (Alt+O): no influence work for display under symmetry either.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from tests.test_symmetric_soft_selection import (  # noqa: F401  (helpers only, no tests)
    CTRL_Y,
    CTRL_Z,
    ESC,
    KEYS,
    METRIC_NAMES,
    O,
    RADIUS_STEPS,
    VALID_CASES,
    _app,
    _drag,
    _seeds,
    _select,
    _side,
    _soft_on,
)

from loaders.assets import asset_path
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.soft_selection import (
    EMPTY_BANDS,
    GLSoftBandOverlay,
    SoftBands,
    compute_influence,
    symmetric_influence,
)
from mirai.symmetry import CorrespondenceState, vertex_correspondence
from mirai.symmetry_axis import current_axis, set_symmetry_axis
from viewport.gl_symmetry_overlay import GLSymmetryOverlay

SHIFT_S = Input("key", "s", frozenset({"shift"}))
ALT_O = Input("key", "o", frozenset({"alt"}))
CTRL_O = Input("key", "o", frozenset({"ctrl"}))


def _band_app(asset: str, axis: str) -> object:
    return _app(asset, axis, overlay=GLSoftBandOverlay)


def _field(app, seeds):
    soft = app.soft_settings
    return symmetric_influence(
        app.scene.mesh, seeds, soft.world_radius, metric=soft.metric, curve=soft.curve,
        curve_power=soft.curve_power,
    )


def _expected(app, seeds) -> SoftBands:
    """What the preview must show: the symmetric field with a fresh correspondence."""
    if app.scene.mesh.symmetry_definition is None:
        soft = app.soft_settings
        return SoftBands.from_weights(compute_influence(
            app.scene.mesh, seeds, soft.world_radius, soft.metric, soft.curve, soft.curve_power
        ))
    return SoftBands.from_weights(_field(app, seeds).weights)


def _set_metric(app, metric):
    while app.soft_settings.metric != metric:
        assert app.key_press(CTRL_O)


def _ready(asset, axis, metric="euclidean"):
    app = _band_app(asset, axis)
    seeds = _seeds(app.scene.mesh, axis, "ring")
    _select(app, seeds)
    _soft_on(app, RADIUS_STEPS[asset])
    _set_metric(app, metric)
    return app, seeds


@pytest.fixture
def preview_calls(monkeypatch) -> list[str]:
    """Every influence computation the preview does (`mirai.application`)."""
    import mirai.application as application_module

    calls: list[str] = []
    for name in ("compute_influence", "symmetric_influence"):
        original = getattr(application_module, name)

        def spy(*args, _name=name, _original=original, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(application_module, name, spy)
    return calls


@pytest.fixture
def pairings(monkeypatch) -> list[str]:
    """Every `vertex_correspondence` run, wherever it is called from."""
    import mirai.interaction.tools.move as move_module
    import mirai.interaction.tools.selection_helpers as helpers_module
    import mirai.soft_selection.symmetric as symmetric_module
    import mirai.symmetry as symmetry_module
    import mirai.symmetry_display as display_module

    calls: list[str] = []
    original = symmetry_module.vertex_correspondence

    def spy(mesh):
        calls.append("pairing")
        return original(mesh)

    for module in (symmetry_module, display_module, symmetric_module, move_module, helpers_module):
        monkeypatch.setattr(module, "vertex_correspondence", spy)
    return calls


# -- the preview is the symmetric field, both sides ----------------------------------------------


@pytest.mark.parametrize("metric", METRIC_NAMES)
@pytest.mark.parametrize("asset,axis", VALID_CASES)
def test_preview_shows_both_sides_partners_in_one_band_seam_with_its_one_weight(asset, axis, metric):
    app, seeds = _ready(asset, axis, metric)
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    bands = app.soft_bands
    assert bands == _expected(app, seeds) and bands.count > 0
    band_of = {v: i for i, band in enumerate(bands.bands) for v in band}
    assert {_side(mesh, v, axis) for v in band_of} >= {1, -1}  # both sides
    seam_shown = 0
    for vid, index in band_of.items():
        c = corr[vid]
        if c.state is CorrespondenceState.PAIRED:
            assert band_of.get(c.partner) == index, vid
            assert bands.weights[c.partner] == bands.weights[vid]
        elif c.state is CorrespondenceState.SEAM:
            seam_shown += 1
    assert seam_shown > 0  # the radius steps cross the plane (RADIUS_STEPS)
    # Plain Soft would show one side only: the preview is not plain Soft's field.
    soft = app.soft_settings
    plain = compute_influence(mesh, seeds, soft.world_radius, soft.metric, soft.curve)
    assert SoftBands.from_weights(plain) != bands


@pytest.mark.parametrize("op_name", sorted(KEYS))
@pytest.mark.parametrize("asset,axis", VALID_CASES)
def test_preview_weights_equal_the_ops_weights_at_begin(asset, axis, op_name):
    app, _seeds_ = _ready(asset, axis)
    preview = app.soft_bands
    assert preview.count > 0
    op = _drag(app, KEYS[op_name], moves=((4.0, 1.0),))
    influence = op.context.params["influence"]
    assert preview.weights == {v: w for v, w in influence.items() if 0.0 < w < 1.0}  # bit for bit
    assert app.soft_bands == preview
    app.key_press(ESC)


@pytest.mark.parametrize("op_name", sorted(KEYS))
def test_during_the_gesture_nothing_is_computed_and_the_bands_follow(op_name, preview_calls, pairings):
    app, _seeds_ = _ready("head_basemesh", "X")
    preview = app.soft_bands
    _drag(app, KEYS[op_name], moves=((4.0, 1.0),))  # begin(): the tool pairs once for its op
    preview_calls.clear()
    pairings.clear()
    for i in range(6):
        assert app.pointer_motion(410.0 + i, 300.0, 7.0, -3.0)
        app.viewport.sync()
    assert preview_calls == [] and pairings == []
    assert app.soft_bands == preview  # the op's weights, at the live positions (overlay sync)
    mesh = app.scene.mesh
    assert app._soft_overlay.points("soft_band_0") == [
        mesh.vertex_position(v) for v in preview.bands[0]
    ]
    app.key_press(ESC)


def test_settings_change_mid_gesture_leaves_the_symmetric_bands_alone(preview_calls):
    app, _seeds_ = _ready("head_basemesh", "X")
    preview = app.soft_bands
    _drag(app, KEYS["move"])
    preview_calls.clear()
    app.dispatch_command(commands.SOFT_RADIUS_UP)
    assert preview_calls == [] and app.soft_bands == preview
    app.key_press(ESC)


# -- the preview is right after gesture end, Undo/Redo, Shift+S, scene load -------------------


@pytest.mark.parametrize("op_name", sorted(KEYS))
def test_commit_undo_redo_each_leave_the_preview_of_the_current_geometry(op_name):
    app, seeds = _ready("head_basemesh", "X")
    start = app.soft_bands
    _drag(app, KEYS[op_name])
    app.key_release(KEYS[op_name])
    after = app.soft_bands
    assert after == _expected(app, seeds)
    assert app.key_press(CTRL_Z) and app.soft_bands == _expected(app, seeds) == start
    assert app.key_press(CTRL_Y) and app.soft_bands == _expected(app, seeds) == after


def test_cancel_restores_the_symmetric_preview_exactly():
    app, _seeds_ = _ready("head_basemesh", "X")
    preview = app.soft_bands
    _drag(app, KEYS["rotate"])
    assert app.key_press(ESC)
    assert app.soft_bands == preview


def test_shift_s_cycle_switches_the_preview_with_the_definition():
    """subd_cube: X and Z are `valid`, Y has no pair (every seed refused, D-2): no bands."""
    app = _band_app("subd_cube", "X")
    set_symmetry_axis(app.scene.mesh, None)
    app.viewport.on_topology_changed()
    seeds = _seeds(_band_app("subd_cube", "X").scene.mesh, "X", "ring")
    _select(app, seeds)
    _soft_on(app, RADIUS_STEPS["subd_cube"])
    plain = app.soft_bands
    assert plain == _expected(app, seeds) and plain.count > 0
    seen = {}
    for _ in range(4):
        assert app.key_press(SHIFT_S)
        axis = current_axis(app.scene.mesh)
        seen[axis] = app.soft_bands
        if axis == "Y":
            assert app.soft_bands == EMPTY_BANDS
        else:
            assert app.soft_bands == _expected(app, seeds)
    assert seen[None] == plain
    assert seen["X"] != plain and seen["Z"] != plain and seen["X"].count > plain.count
    # Undo of a cycle step is the same trigger.
    assert app.key_press(CTRL_Z) and current_axis(app.scene.mesh) == "Z"
    assert app.soft_bands == seen["Z"]


def test_scene_load_takes_the_new_meshs_pairing(preview_calls):
    app, _seeds_ = _ready("head_basemesh", "X")
    reports = app._symmetry_reports
    app.load_scene("obj", obj_path=asset_path("subd_cube"), soft_overlay_type=GLSoftBandOverlay)
    assert app._symmetry_reports is not reports  # fresh per scene
    assert app.soft_bands == EMPTY_BANDS  # the loader clears the selection
    set_symmetry_axis(app.scene.mesh, "X")
    app.viewport.on_topology_changed()
    seeds = _seeds(app.scene.mesh, "X", "ring")
    _select(app, seeds)
    for _ in range(RADIUS_STEPS["subd_cube"]):  # triggers; the cube needs a larger radius
        app.dispatch_command(commands.SOFT_RADIUS_UP)
    assert app.soft_bands == _expected(app, seeds) and app.soft_bands.count > 0


# -- D-2: a refused selection shows no bands ------------------------------------------------------


def test_a_seed_without_partner_shows_no_bands_and_not_plain_softs():
    app = _band_app("man_with_shoes_basemesh", "X")
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    unpaired = next(v for v, c in corr.items() if c.state is CorrespondenceState.UNPAIRED)
    _select(app, {unpaired})
    _soft_on(app, 3)
    assert app.soft_bands == EMPTY_BANDS
    # The same selection without symmetry has bands: the empty preview is the refusal.
    set_symmetry_axis(mesh, None)
    app.viewport.on_topology_changed()
    app.dispatch_command(commands.SOFT_RADIUS_UP)
    assert app.soft_bands.count > 0


def test_a_hover_armed_refused_gesture_shows_no_bands():
    app = _band_app("man_with_shoes_basemesh", "X")
    corr = vertex_correspondence(app.scene.mesh)
    unpaired = next(v for v, c in corr.items() if c.state is CorrespondenceState.UNPAIRED)
    _soft_on(app, 3)
    app.selection.hovered = unpaired
    assert app.key_press(KEYS["move"])  # arms on the hovered vertex
    assert app.soft_bands == EMPTY_BANDS
    assert app.pointer_motion(400.0, 300.0, 9.0, 4.0) is False  # refused at begin(), as SS2
    assert app.status_message.startswith("Move: refused")
    assert app.soft_bands == EMPTY_BANDS


def test_a_hover_armed_gesture_shows_the_symmetric_field_once_at_arm(preview_calls):
    app = _band_app("head_basemesh", "X")
    vid = min(_seeds(app.scene.mesh, "X", "ring"))
    _soft_on(app)
    app.selection.hovered = vid
    assert app.key_press(KEYS["move"])
    assert preview_calls == ["symmetric_influence"]
    shown = app.soft_bands
    assert shown == _expected(app, {vid}) and shown.count > 0
    preview_calls.clear()
    assert app.pointer_motion(400.0, 300.0, 9.0, 4.0)
    assert preview_calls == []
    influence = app.tool_manager.active_tool.operation.context.params["influence"]
    assert shown.weights == {v: w for v, w in influence.items() if 0.0 < w < 1.0}
    assert app.key_release(KEYS["move"])
    assert app.soft_bands == EMPTY_BANDS  # the selection is empty


# -- cost: the correspondence comes from the shared report, not per trigger ---------------------


def test_selection_and_settings_triggers_pair_nothing(pairings):
    app, seeds = _ready("head_basemesh", "X")
    pairings.clear()
    reports = app._symmetry_reports.recomputes
    for _ in range(3):
        app.dispatch_command(commands.SOFT_RADIUS_UP)
    app.dispatch_command(commands.SOFT_METRIC_CYCLE)
    _select(app, set(list(seeds)[:1]))
    app._soft_preview_refresh()
    assert pairings == [] and app._symmetry_reports.recomputes == reports
    assert app.soft_bands == _expected(app, set(list(seeds)[:1]))


def test_a_geometry_change_pairs_once_for_preview_and_display_together():
    app = Application_with_display("head_basemesh")
    assert app.symmetry_display.reports is app._symmetry_reports
    seeds = _seeds(app.scene.mesh, "X", "ring")
    _select(app, seeds)
    _soft_on(app)
    app.viewport.sync()
    runs = app._symmetry_reports.recomputes
    _drag(app, KEYS["move"])
    app.viewport.sync()
    app.key_release(KEYS["move"])  # commit: the preview re-derives for the new positions ...
    assert app._symmetry_reports.recomputes == runs + 1
    app.viewport.sync()  # ... and the display reads the same report
    assert app._symmetry_reports.recomputes == runs + 1
    assert app.symmetry_display.report is app._symmetry_reports.current(app.scene.mesh)
    assert app.soft_bands == _expected(app, seeds)


def Application_with_display(asset):
    from mirai.application import Application

    app = Application()
    app.init_scene(
        "obj", obj_path=asset_path(asset), soft_overlay_type=GLSoftBandOverlay,
        symmetry_overlay_type=GLSymmetryOverlay,
    )
    app.frame_scene()
    app.set_viewport_size(800, 600)
    app.pointer_motion(2.0, 2.0)
    assert app.key_press(SHIFT_S) and current_axis(app.scene.mesh) == "X"
    return app


# -- bands off (Alt+O) under symmetry -------------------------------------------------------------


def test_bands_off_under_symmetry_computes_nothing_for_display(preview_calls, pairings):
    app, _seeds_ = _ready("head_basemesh", "X")
    preview_calls.clear()
    pairings.clear()
    assert app.key_press(ALT_O) and not app.soft_settings.bands_visible
    assert app.soft_bands == EMPTY_BANDS
    app.dispatch_command(commands.SOFT_RADIUS_UP)
    assert preview_calls == [] and pairings == []
    # Geometry triggers (Shift+S, Undo): no field for display (Shift+S's own status line
    # still reads the state, as before SS3).
    assert app.key_press(SHIFT_S) and app.key_press(CTRL_Z)
    assert preview_calls == [] and app.soft_bands == EMPTY_BANDS
    # The gesture still deforms softly (its own pairing at begin()) and shows nothing.
    _drag(app, KEYS["move"])
    assert app.soft_bands == EMPTY_BANDS
    app.key_release(KEYS["move"])
    assert preview_calls == [] and app.soft_bands == EMPTY_BANDS
    assert app.key_press(ALT_O)
    assert app.soft_bands.count > 0


def test_soft_off_under_symmetry_clears_the_bands():
    app, _seeds_ = _ready("head_basemesh", "X")
    assert app.soft_bands.count > 0
    assert app.key_press(O) and not app.soft_settings.enabled
    assert app.soft_bands == EMPTY_BANDS
