"""Soft Selection influence display look (2026-10-22, `PROVISIONAL`; AD-020 "Display look"): Manu, "möglichst
dezent/monochromer machen (mal testen)".

Headless (TraceStore); the sinks are the real `GLSoftBandOverlay` / `GLSoftShadingOverlay` (data side). Pins:

- three looks, `mono` (default) / `tint` / `color`, cycled by Ctrl+Shift+O (rebindable), posted in the status line;
- `mono` and `tint` are one colour each and quieter than `color` (lower shading alpha, smaller band points),
  and never the selection / hover yellow;
- a look change only recolours: weights, mesh, selection, history and a running gesture stay; it applies at once,
  in both display modes;
- the sinks default to `color` (a host that pushes no look keeps the S2b look).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401  (puts examples/ on sys.path)

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.soft_selection import LOOKS, GLSoftBandOverlay, GLSoftShadingOverlay, SoftSettings, shading_color
from mirai.soft_selection.gl_bands import BAND_LAYERS, BAND_LOOKS, band_layer_styles
from mirai.soft_selection.shading import SHADING_LOOKS
from viewport.gl_point_overlay import HOVER_COLOR, SELECTED_COLOR

WIDTH, HEIGHT = 800, 600
CTRL_SHIFT_O = Input("key", "o", frozenset({"ctrl", "shift"}))
O = Input("key", "o")
ALT_SHIFT_O = Input("key", "o", frozenset({"alt", "shift"}))
W, ESC = Input("key", "w"), Input("key", "ESCAPE")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene(
        "obj", obj_path=HEAD_OBJ,
        soft_overlay_type=GLSoftBandOverlay, soft_shading_overlay_type=GLSoftShadingOverlay,
    )
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    vid = app.scene.mesh.all_vertex_ids()[100]
    app.selection.set({vid})
    app.viewport.on_selection_changed()
    return app


def _positions(app) -> dict:
    mesh = app.scene.mesh
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


# -- settings, key, status ---------------------------------------------------------------------------


def test_default_look_is_mono_and_the_cycle_comes_back():
    s = SoftSettings()
    assert LOOKS == ("mono", "tint", "color") and s.look == "mono"
    assert [s.with_next_look().look, s.with_next_look().with_next_look().look] == ["tint", "color"]
    assert s.with_next_look().with_next_look().with_next_look() == s
    with pytest.raises(ValueError):
        SoftSettings(look="neon")


def test_ctrl_shift_o_is_the_look_key_and_rebindable():
    bs = build_default_bindings()
    assert bs.command_for(CTRL_SHIFT_O) == cmd.SOFT_LOOK_CYCLE
    bs.set_default(Input("key", "l", frozenset({"alt"})), cmd.SOFT_LOOK_CYCLE)
    assert bs.command_for(Input("key", "l", frozenset({"alt"}))) == cmd.SOFT_LOOK_CYCLE


def test_look_key_recolours_only_and_posts_the_state(app):
    assert app.key_press(O)
    before = (_positions(app), set(app.selection.vertices), app.history.can_undo(), app.soft_bands)
    seen = []
    for _ in range(len(LOOKS)):
        assert app.key_press(CTRL_SHIFT_O)
        seen.append(app.soft_settings.look)
        assert app.status_message.endswith(f"· bands on · {app.soft_settings.look}")
        assert app._soft_overlay.look == app._soft_shading_overlay.look == app.soft_settings.look
    assert seen == ["tint", "color", "mono"]
    assert (_positions(app), set(app.selection.vertices), app.history.can_undo(), app.soft_bands) == before


# -- the sinks ------------------------------------------------------------------------------------------


def test_sinks_get_the_look_at_scene_load_and_default_to_color_alone(app):
    assert app._soft_overlay.look == "mono" and app._soft_shading_overlay.look == "mono"
    assert app._soft_overlay.LAYER_STYLES == band_layer_styles("mono")
    bare = GLSoftBandOverlay()
    assert bare.look == "color" and bare.LAYER_STYLES == band_layer_styles("color")
    assert GLSoftShadingOverlay().look == "color"


@pytest.mark.parametrize("look", ["mono", "tint"])
def test_quiet_looks_are_one_colour_quieter_than_color_and_not_the_selection(look):
    colors, size = BAND_LOOKS[look]
    color_colors, color_size = BAND_LOOKS["color"]
    assert len({c[:3] for c in colors}) == 1  # monochrome
    alphas = [c[3] for c in colors]
    assert alphas == sorted(alphas, reverse=True) and max(alphas) < 1.0  # strongest band most opaque
    assert size < color_size
    for c in colors:
        assert c[:3] != SELECTED_COLOR[:3] and c[:3] != HOVER_COLOR[:3]
    hues, alpha_min, alpha_max = SHADING_LOOKS[look]
    assert len(set(hues)) == 1
    assert alpha_max < SHADING_LOOKS["color"][2] and alpha_min < SHADING_LOOKS["color"][1]


@pytest.mark.parametrize("look", LOOKS)
def test_shading_alpha_grows_with_the_weight_in_every_look(look):
    assert shading_color(0.0, look)[3] == 0.0
    alphas = [shading_color(w, look)[3] for w in (0.05, 0.25, 0.5, 0.75, 1.0)]
    assert alphas == sorted(alphas) and alphas[0] > 0.0


def test_face_shading_takes_the_look_at_the_next_sync(app):
    assert app.key_press(O)
    assert app.key_press(ALT_SHIFT_O)  # faces
    shading = app._soft_shading_overlay
    app.update_viewport(0.016)
    mono = shading.colors()
    assert mono and all(c == 1.0 for i, c in enumerate(mono) if i % 4 != 3)  # white
    assert app.key_press(CTRL_SHIFT_O)  # tint
    assert shading.dirty
    app.update_viewport(0.016)
    tint = shading.colors()
    assert len(tint) == len(mono) and tint != mono
    assert max(tint[3::4]) <= SHADING_LOOKS["tint"][2] + 1e-12


def test_band_styles_follow_the_look(app):
    assert app.key_press(O)
    assert app.key_press(CTRL_SHIFT_O)
    assert app.key_press(CTRL_SHIFT_O)  # color
    styles = app._soft_overlay.LAYER_STYLES
    assert [styles[layer] for layer in BAND_LAYERS] == [band_layer_styles("color")[layer] for layer in BAND_LAYERS]


def test_look_change_mid_gesture_applies_at_once_and_leaves_the_gesture(app):
    assert app.key_press(O)
    assert app.key_press(W)
    for dx, dy in ((6.0, 2.0), (5.0, 3.0)):
        app.pointer_motion(300.0, 300.0, dx, dy)
    op = app.tool_manager.active_tool.operation
    weights, positions, bands = op.weights, _positions(app), app.soft_bands
    assert app.key_press(CTRL_SHIFT_O)
    assert app._soft_overlay.look == "tint"
    assert app.tool_manager.active_tool.operation is op and op.weights == weights
    assert _positions(app) == positions and app.soft_bands == bands
    assert app.key_press(ESC)
