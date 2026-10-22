"""SoftSettings (WP-SOFT-01 S2a/S2d, AD-020 §13): defaults, curve cycle, custom shape, radius steps,
band switch and the status line (handoff E2-E5, E7, E8)."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from mirai.soft_selection import (
    CURVES,
    CUSTOM_SHAPE_STEPS,
    DEFAULT_CUSTOM_SHAPE_STEP,
    DEFAULT_RADIUS_STEP,
    RADIUS_STEPS_PERCENT,
    SoftSettings,
    world_radius_for,
)


def test_defaults_are_geodesic_smooth_15_percent_bands_on():
    s = SoftSettings()
    assert (s.enabled, s.metric, s.curve) == (False, "geodesic", "smooth")
    assert s.radius_percent == 15 and s.bands_visible is True
    assert s.curve_power == 1.0 and CUSTOM_SHAPE_STEPS[DEFAULT_CUSTOM_SHAPE_STEP] == 1.0


def test_radius_steps_go_up_to_200_percent():
    # 2026-10-22: finer (Manu: "kleinere Sprünge"); every earlier step is still in the list.
    assert RADIUS_STEPS_PERCENT[0] == 2 and RADIUS_STEPS_PERCENT[-1] == 200
    assert set((2, 5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200)) <= set(RADIUS_STEPS_PERCENT)
    assert list(RADIUS_STEPS_PERCENT) == sorted(set(RADIUS_STEPS_PERCENT))
    # From 10 % up one notch changes the radius by at most 20 % (the old list: up to 50 %).
    big = [b / a for a, b in zip(RADIUS_STEPS_PERCENT, RADIUS_STEPS_PERCENT[1:]) if a >= 10]
    assert max(big) <= 1.2
    assert RADIUS_STEPS_PERCENT[DEFAULT_RADIUS_STEP] == 15
    assert world_radius_for(2.0, len(RADIUS_STEPS_PERCENT) - 1) == pytest.approx(4.0)


def test_radius_step_is_clamped_without_wrap():
    s = SoftSettings().with_radius_step(99, 1.0)
    assert s.radius_percent == 200 and s.world_radius == pytest.approx(2.0)
    assert s.with_radius_step(-5, 1.0).radius_percent == 2


def test_curve_cycle_order_and_wraps_to_smooth():
    s = SoftSettings()
    seen = []
    for _ in range(len(CURVES)):
        seen.append(s.curve)
        s = s.with_next_curve()
    assert seen == ["smooth", "sphere", "root", "sharp", "linear", "custom"]
    assert s.curve == "smooth"


def test_custom_curve_keeps_its_last_p_through_the_cycle():
    s = SoftSettings().with_custom_shape_step(+2)  # p = 2
    assert s.curve == "custom" and s.curve_power == 2.0
    for _ in range(len(CURVES)):  # a full cycle comes back to custom
        s = s.with_next_curve()
    assert s.curve == "custom" and s.curve_power == 2.0


def test_ctrl_wheel_steps_clamp_at_both_ends_and_always_select_custom():
    s = SoftSettings()
    for _ in range(len(CUSTOM_SHAPE_STEPS) + 3):
        s = s.with_custom_shape_step(-1)  # rounder
    assert s.curve_power == CUSTOM_SHAPE_STEPS[0] == 0.25
    again = s.with_custom_shape_step(-1)
    assert again == s  # clamped, unchanged
    sharp = SoftSettings()
    for _ in range(len(CUSTOM_SHAPE_STEPS) + 3):
        sharp = sharp.with_custom_shape_step(+1)
    assert sharp.curve_power == CUSTOM_SHAPE_STEPS[-1] == 4.0
    # Any step switches to custom, also one that is clamped at the end of the list.
    other = SoftSettings(curve="sphere", custom_shape_step=0).with_custom_shape_step(-1)
    assert other.curve == "custom" and other.custom_shape_step == 0


def test_invalid_shape_step_is_rejected():
    with pytest.raises(ValueError):
        SoftSettings(custom_shape_step=len(CUSTOM_SHAPE_STEPS))


def test_status_text_shows_the_full_state():
    s = SoftSettings(enabled=True).with_bounding_radius(3.4)
    assert s.status_text() == "Soft: on · 15 % (0.51) · geodesic · smooth · bands on · mono"
    custom = s.with_custom_shape_step(+1)  # p = 1.5
    assert custom.status_text() == "Soft: on · 15 % (0.51) · geodesic · custom p=1.5 · bands on · mono"
    assert custom.with_bands_toggled().status_text().endswith("· custom p=1.5 · bands off · mono")
    assert s.with_next_curve().status_text().endswith("· sphere · bands on · mono")  # no p unless custom
    assert s.with_next_look().status_text().endswith("· bands on · tint")


def test_bands_toggle_changes_nothing_else():
    s = SoftSettings(enabled=True, curve="sharp")
    t = s.with_bands_toggled()
    assert t.bands_visible is False
    assert (t.enabled, t.curve, t.metric, t.radius_step) == (s.enabled, s.curve, s.metric, s.radius_step)
    assert t.with_bands_toggled() == s
