"""GL-free control model: presets, A/B, row steps, greying, E11 warning, light drag."""

from __future__ import annotations

from viewport_shading_lab.lab_controls import EDITED_NAME, ROW_IDS, ROWS, LabState
from viewport_shading_lab.lab_rig import (
    PRESET_HEUTE,
    PRESET_RAITT,
    PRESET_SOFTBOX,
    PRESETS,
    RATIO_STEPS,
    SPACE_CAMERA,
    SPACE_WORLD,
)


def test_starts_on_heute():
    state = LabState()
    assert state.rig == PRESETS[PRESET_HEUTE]
    assert state.displayed_name() == PRESET_HEUTE


def test_preset_sets_rig_and_name_and_ends_ab():
    state = LabState()
    state.toggle_ab()
    state.apply_preset(PRESET_SOFTBOX)
    assert state.rig == PRESETS[PRESET_SOFTBOX]
    assert state.preset_name == PRESET_SOFTBOX
    assert not state.ab_active


def test_ab_toggles_display_not_rig():
    state = LabState(PRESET_RAITT)
    state.toggle_ab()
    assert state.displayed_rig() == PRESETS[PRESET_HEUTE]
    assert state.rig == PRESETS[PRESET_RAITT]
    state.toggle_ab()
    assert state.displayed_rig() == PRESETS[PRESET_RAITT]


def test_edit_during_ab_returns_to_edited_rig():
    state = LabState(PRESET_RAITT)
    state.toggle_ab()
    state.step_row("ambient", +1)
    assert not state.ab_active
    assert abs(state.displayed_rig().ambient - (PRESETS[PRESET_RAITT].ambient + 0.05)) < 1e-9
    assert state.preset_name == EDITED_NAME


def test_light_drag_during_ab_returns_to_edited_rig():
    state = LabState(PRESET_RAITT)
    state.toggle_ab()
    state.drag_light(10, -4)
    assert not state.ab_active
    assert state.rig.key_azimuth == -40.0
    assert state.rig.key_elevation == 33.0


def test_every_row_changes_rig_in_both_directions():
    for row_id in ROW_IDS:
        state = LabState(PRESET_RAITT)
        if row_id in ("fill_azimuth", "fill_elevation"):
            state.step_row("fill_coupled", +1)  # free fill angles apply only uncoupled
        before = state.rig
        state.step_row(row_id, +1)
        up = state.rig
        state.step_row(row_id, -1)
        back = state.rig
        assert up != before, row_id
        assert back != up, row_id
        assert back == before, row_id  # +1 then -1 is a round trip (toggles flip back)


def test_fine_step_is_smaller():
    state = LabState(PRESET_RAITT)
    state.step_row("key_intensity", +1, fine=True)
    assert abs(state.rig.key_intensity - 0.61) < 1e-9
    state.step_row("key_kelvin", -1, fine=True)
    assert state.rig.key_kelvin == 6400.0


def test_ranges_clamp():
    state = LabState(PRESET_RAITT)
    for _ in range(50):
        state.step_row("ambient", +1)
        state.step_row("key_wrap", +1)
        state.step_row("key_kelvin", -1)
        state.step_row("key_elevation", +1)
    assert state.rig.ambient == 0.6
    assert state.rig.key_wrap == 1.0
    assert state.rig.key_kelvin == 2500.0
    assert state.rig.key_elevation == 90.0


def test_ratio_steps_include_off():
    state = LabState(PRESET_RAITT)
    seen = []
    for _ in range(len(RATIO_STEPS) + 2):
        seen.append(state.rig.fill_ratio)
        state.step_row("fill_ratio", +1)
    assert seen[-1] is None
    assert state.rig.fill_intensity == 0.0
    assert set(seen) <= set(RATIO_STEPS)


def test_uncoupling_keeps_fill_in_place():
    state = LabState(PRESET_RAITT)
    coupled = state.rig.effective_fill_angles()
    state.step_row("fill_coupled", +1)
    assert not state.rig.fill_coupled
    assert state.rig.effective_fill_angles() == coupled


def test_space_toggle():
    state = LabState(PRESET_RAITT)
    assert state.rig.space == SPACE_CAMERA
    state.step_row("space", +1)
    assert state.rig.space == SPACE_WORLD


def _styles(state):
    lines = state.hud_lines()
    return {row.id: lines[i + 1].style for i, row in enumerate(ROWS)}


def test_greying_rules():
    state = LabState(PRESET_RAITT)
    styles = _styles(state)
    assert styles["fill_azimuth"] == styles["fill_elevation"] == "inactive"
    assert styles["fill_kelvin"] != "inactive"
    state.step_row("fill_coupled", +1)
    styles = _styles(state)
    assert styles["fill_azimuth"] != "inactive"
    heute = LabState(PRESET_HEUTE)  # fill off
    styles = _styles(heute)
    for row_id in ("fill_coupled", "fill_azimuth", "fill_elevation", "fill_kelvin", "fill_wrap"):
        assert styles[row_id] == "inactive", row_id
    assert styles["fill_ratio"] != "inactive"


def test_hud_marks_active_row_and_preset():
    state = LabState(PRESET_RAITT)
    state.select_row(+1)
    lines = state.hud_lines(16.7)
    assert PRESET_RAITT in lines[0].text
    assert lines[2].style == "active" and lines[2].text.startswith("▶")
    assert lines[-1].text == "Frame 16.7 ms"
    state.toggle_ab()
    assert "AKTIV" in state.hud_lines()[0].text


def test_overexposure_warning():
    state = LabState(PRESET_RAITT)
    assert all(line.style != "warning" for line in state.hud_lines())
    state.step_row("ambient", +1)
    warnings = [line for line in state.hud_lines() if line.style == "warning"]
    assert len(warnings) == 1 and "1.05" in warnings[0].text
