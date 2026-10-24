"""Worklight editing in the Production window (AD-024 §8): `DisplayState.set_light`, the Look rows
taken from the Shading Lab, `Application.set_light` / `step_light` and the temporary arrow keys.

Headless (`Application` without GL; the viewport is the trace viewport of `init_scene`).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.viewport.display import DisplayState
from mirai.viewport.look_controls import (
    KEY_INTENSITY_MAX,
    LIGHT_ROW_IDS,
    LIGHT_ROWS,
    LOOK_ROWS,
    clamp_light,
    light_row,
    step_ratio,
)
from viewport.light_rig import (
    AMBIENT_MAX,
    KELVIN_MIN,
    PRESET_RAITT,
    PRESET_SOFTBOX,
    PRESETS,
    RATIO_STEPS,
    LightRig,
)


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


UP, DOWN, LEFT, RIGHT = _key("up"), _key("down"), _key("left"), _key("right")
CTRL_LEFT, CTRL_RIGHT = _key("left", "ctrl"), _key("right", "ctrl")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _select_row(app: Application, row_id: str) -> None:
    while app.look_row.id != row_id:
        assert app.key_press(DOWN) is True


# -- rows (parity with the Shading Lab: experiments/viewport_shading_lab/tests/test_production_look_parity.py)


def test_rows_in_the_lab_order():
    assert LIGHT_ROW_IDS == (
        "space", "key_azimuth", "key_elevation", "key_intensity", "key_kelvin", "key_wrap", "fill_ratio",
        "fill_coupled", "fill_azimuth", "fill_elevation", "fill_kelvin", "fill_wrap", "ambient",
    )


def test_coupling_to_free_keeps_the_fill_where_it_was():
    rig = PRESETS[PRESET_RAITT]
    free = light_row("fill_coupled").step(rig, 1, False)
    assert not free.fill_coupled
    assert free.effective_fill_angles() == rig.effective_fill_angles()


def test_ratio_steps_walk_the_lab_list_and_snap_between_steps():
    assert step_ratio(2.0, 1) == 3.0 and step_ratio(2.0, -1) == 1.5
    assert step_ratio(8.0, 1) is None and step_ratio(None, -1) == 8.0
    assert step_ratio(1.0, -1) == 1.0 and step_ratio(None, 1) is None
    assert step_ratio(2.5, 1) == 3.0 and step_ratio(2.5, -1) == 2.0
    assert [r for r in RATIO_STEPS] == [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, None]


def test_clamp_keeps_values_in_the_lab_ranges():
    rig = clamp_light(LightRig(key_intensity=5.0, ambient=-1.0, key_kelvin=100.0, key_azimuth=540.0,
                               fill_ratio=0.2, key_elevation=120.0))
    assert rig.key_intensity == KEY_INTENSITY_MAX and rig.ambient == 0.0
    assert rig.key_kelvin == KELVIN_MIN and rig.key_azimuth == 180.0
    assert rig.fill_ratio == 1.0 and rig.key_elevation == 90.0
    with pytest.raises(ValueError):
        clamp_light(LightRig(space="sky"))


# -- DisplayState ---------------------------------------------------------------------------------


def test_set_light_edits_and_a_preset_replaces_the_edit():
    display = DisplayState()
    display.set_light(key_azimuth=10.0, ambient=AMBIENT_MAX + 1)
    assert display.light_rig.key_azimuth == 10.0 and display.light_rig.ambient == AMBIENT_MAX
    assert display.light_edited and display.light_label == "Raitt 2:1 angepasst · Kamera"
    display.cycle_light_preset()
    assert display.light_rig == PRESETS[PRESET_SOFTBOX] and not display.light_edited


def test_space_is_a_toggle_that_survives_presets_and_is_no_edit():
    display = DisplayState()
    display.set_light(space="world")
    assert not display.light_edited and display.light_label == "Raitt 2:1 · Welt"
    display.cycle_light_preset()
    assert display.light_rig.space == "world"


def test_set_light_refuses_unknown_parameters():
    with pytest.raises(KeyError):
        DisplayState().set_light(key_brightness=1.0)


# -- Application setters --------------------------------------------------------------------------


def test_set_light_reaches_the_viewport_and_is_no_undo_step(app):
    history = len(app.history)
    assert app.set_light(key_kelvin=4000.0, key_wrap=0.3, fill_ratio=4.0, fill_kelvin=9000.0,
                         fill_wrap=0.5, ambient=0.2, key_azimuth=30.0, key_elevation=10.0) is True
    rig = app.viewport.light_rig
    assert (rig.key_kelvin, rig.key_wrap, rig.fill_ratio, rig.fill_kelvin) == (4000.0, 0.3, 4.0, 9000.0)
    assert (rig.fill_wrap, rig.ambient, rig.key_azimuth, rig.key_elevation) == (0.5, 0.2, 30.0, 10.0)
    assert len(app.history) == history
    assert app.set_light(key_kelvin=4000.0) is False


def test_set_light_changes_the_shader_uniforms(app):
    before = app.viewport.light_uniforms()
    app.set_light(key_azimuth=90.0)
    after = app.viewport.light_uniforms()
    assert after["u_key_dir"] != before["u_key_dir"]
    assert after["u_fill_color"] == before["u_fill_color"]


def test_step_light_uses_the_lab_steps_and_reports(app):
    assert app.step_light("key_azimuth", 1) is True
    assert app.display.light_rig.key_azimuth == -30.0
    assert app.status_message == "Light: Key Azimut -30.0°"
    assert app.step_light("key_azimuth", -1, fine=True) is True
    assert app.display.light_rig.key_azimuth == -31.0


def test_step_light_refuses_an_inactive_row(app):
    rig = app.display.light_rig
    assert app.step_light("fill_azimuth", 1) is False  # coupled
    assert app.display.light_rig == rig
    assert "inaktiv" in app.status_message
    app.set_light(fill_ratio=None)
    assert app.step_light("fill_kelvin", 1) is False


def test_step_at_the_limit_changes_nothing(app):
    app.set_light(ambient=AMBIENT_MAX)
    assert app.step_light("ambient", 1) is False
    assert app.status_message.endswith("(Grenze)")


# -- keys -------------------------------------------------------------------------------------------


def test_arrow_keys_are_the_look_bindings():
    bs = build_default_bindings()
    assert bs.command_for(UP) == cmd.LOOK_ROW_PREV and bs.command_for(DOWN) == cmd.LOOK_ROW_NEXT
    assert bs.command_for(LEFT) == cmd.LOOK_VALUE_DEC and bs.command_for(RIGHT) == cmd.LOOK_VALUE_INC
    assert bs.command_for(CTRL_LEFT) == cmd.LOOK_VALUE_DEC_FINE
    assert bs.command_for(CTRL_RIGHT) == cmd.LOOK_VALUE_INC_FINE
    # Shift+arrows stay the selection steps.
    assert bs.command_for(_key("up", "shift")) == cmd.LOOP_GROW


def test_rows_cycle_and_values_step_by_keys(app):
    assert app.look_row.id == "space"
    assert app.key_press(UP) is True and app.look_row.id == LOOK_ROWS[-1].id
    assert app.key_press(DOWN) is True and app.look_row.id == "space"
    _select_row(app, "key_kelvin")
    assert app.status_message == "Look: Key Temperatur 6500 K"
    assert app.key_press(LEFT) is True and app.display.light_rig.key_kelvin == 6000.0
    assert app.key_press(CTRL_RIGHT) is True and app.display.light_rig.key_kelvin == 6100.0
    _select_row(app, "space")
    assert app.key_press(RIGHT) is True and app.display.light_rig.space == "world"


def test_look_keys_work_in_object_mode_and_while_a_transform_is_armed(app):
    app.key_press(_key("4"))
    _select_row(app, "ambient")
    assert app.key_press(RIGHT) is True
    app.key_press(_key("1"))
    app.selection.vertices = {next(iter(app.scene.mesh.all_vertex_ids()))}
    assert app.key_press(_key("w")) is True and app.interaction_owner == "transform"  # armed, not begun
    assert app.key_press(RIGHT) is True
    assert app.display.light_rig.ambient == pytest.approx(0.2)
