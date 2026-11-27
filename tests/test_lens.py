"""The likeness camera's lens math (AD-042 §3, `mirai.viewport.lens`): T-L1 ... T-L6."""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from mirai.viewport import lens as L
from mirai.viewport.lens import Lens

KB = Lens()  # equiv35, diagonal


# -- T-L1: the reference table (3 : 2 frame, gate angles) -----------------------------------------------------------

@pytest.mark.parametrize("focal, vertical, horizontal", [
    (25.73, 50.00, 69.95),  # AD-042 §3.2 prints 69.4°; the formula gives 69.95° (noted in the implementation note)
    (35.0, 37.85, 54.43),
    (50.0, 26.99, 39.60),
    (85.0, 16.07, 23.91),
    (135.0, 10.16, 15.19),
    (200.0, 6.87, 10.29),
])
def test_gate_angles_of_the_reference_table(focal, vertical, horizontal):
    h, v = L.gate_angles_degrees(Lens(focal_mm=focal), 1.5)
    assert v == pytest.approx(vertical, abs=0.01) and h == pytest.approx(horizontal, abs=0.01)


# -- T-L2: today's view ---------------------------------------------------------------------------------------------

def test_todays_fov_is_25_7_mm_over_a_gate_filling_3_2_frame():
    assert L.focal_from_fov(50.0, KB, 1.5, 1.5, 1.0) == pytest.approx(25.734, abs=1e-3)


def test_new_from_view_values_of_the_ad():
    assert L.focal_from_fov(50.0, KB, 1.5, 1024 / 768, 1.15) == pytest.approx(33.3, abs=0.05)
    assert L.focal_from_fov(50.0, KB, 1.5, 1920 / 1080, 1.15) == pytest.approx(29.6, abs=0.05)


# -- T-L3: the fits -------------------------------------------------------------------------------------------------

def test_diagonal_of_3_2_is_the_sensor_and_of_2_3_its_portrait():
    w, h = L.effective_sensor(36.0, 24.0, "diagonal", 1.5)
    assert w == pytest.approx(36.0, abs=1e-12) and h == pytest.approx(24.0, abs=1e-12)
    w, h = L.effective_sensor(36.0, 24.0, "diagonal", 2 / 3)
    assert w == pytest.approx(24.0, abs=1e-12) and h == pytest.approx(36.0, abs=1e-12)
    w, h = L.effective_sensor(36.0, 24.0, "diagonal", 4 / 3)
    assert (round(w, 2), round(h, 2)) == (34.61, 25.96)
    assert math.hypot(w, h) == pytest.approx(math.hypot(36.0, 24.0), abs=1e-12)


@pytest.mark.parametrize("aspect", [1.5, 4 / 3, 1.0, 2 / 3, 9 / 16])
def test_every_fit_keeps_the_frame_aspect(aspect):
    for fit in L.FITS:
        w, h = L.effective_sensor(23.5, 15.6, fit, aspect)
        assert w / h == pytest.approx(aspect, rel=1e-12)
    assert L.effective_sensor(36.0, 24.0, "width", aspect)[0] == 36.0
    assert L.effective_sensor(36.0, 24.0, "height", aspect)[1] == 24.0
    w, h = L.effective_sensor(36.0, 24.0, "auto", aspect)
    assert max(w, h) == 36.0  # the longer sensor side along the frame's longer side


# -- T-L4: the gate rectangle ---------------------------------------------------------------------------------------

def test_gate_rect_for_wider_narrower_and_equal_windows():
    assert L.gate_rect_ndc(1.5, 2.0, 1.25) == pytest.approx((0.75 / 1.25, 0.8))
    assert L.gate_rect_ndc(1.5, 1.0, 1.25) == pytest.approx((0.8, (1.0 / 1.5) / 1.25))
    assert L.gate_rect_ndc(1.5, 1.5, 1.0) == (1.0, 1.0)
    below = L.gate_rect_ndc(1.5, 1.5 - 1e-12, 1.15)
    above = L.gate_rect_ndc(1.5, 1.5 + 1e-12, 1.15)
    assert below == pytest.approx(above, abs=1e-11)
    lens = Lens(focal_mm=85.0)
    assert L.view_tan_half_v(lens, 1.5, 1.5 - 1e-12, 1.15) == pytest.approx(
        L.view_tan_half_v(lens, 1.5, 1.5 + 1e-12, 1.15), abs=1e-12)


# -- T-L5: round trip -----------------------------------------------------------------------------------------------

def test_focal_fov_focal_round_trip_over_a_grid():
    for focal in (10.0, 18.0, 35.0, 50.0, 85.0, 200.0, 600.0):
        for window in (0.5, 1.0, 1.5, 16 / 9, 3.0):  # both branches against a 3 : 2 frame
            for overscan in (1.0, 1.15, 1.5):
                for lens in (Lens(focal_mm=focal), L.with_sensor(Lens(focal_mm=focal), "aps_c")):
                    fov = L.view_fov_degrees(lens, 1.5, window, overscan)
                    back = L.focal_from_fov(fov, lens, 1.5, window, overscan)
                    assert back == pytest.approx(focal, rel=1e-12)


# -- T-L6: errors, presets, frame aspect ----------------------------------------------------------------------------

@pytest.mark.parametrize("call", [
    lambda: L.gate_tan_half(Lens(focal_mm=0.0), 1.5),
    lambda: L.gate_tan_half(Lens(focal_mm=float("nan")), 1.5),
    lambda: L.gate_tan_half(Lens(sensor_w_mm=-1.0), 1.5),
    lambda: L.gate_tan_half(Lens(fit="cover"), 1.5),
    lambda: L.gate_tan_half(Lens(sensor="medium"), 1.5),
    lambda: L.view_tan_half_v(KB, 1.5, 1.5, 0.99),
    lambda: L.view_tan_half_v(KB, 0.0, 1.5, 1.0),
    lambda: L.gate_rect_ndc(1.5, float("inf"), 1.0),
    lambda: L.focal_from_fov(180.0, KB, 1.5, 1.5, 1.0),
    lambda: L.with_sensor(KB, "medium"),
    lambda: L.frame_aspect(KB, (0, 10)),
])
def test_invalid_values_raise(call):
    with pytest.raises(ValueError):
        call()


def test_sensor_presets_and_frame_aspect():
    aps = L.with_sensor(KB, "aps_c")
    assert (aps.sensor, aps.sensor_w_mm, aps.sensor_h_mm, aps.fit) == ("aps_c", 23.5, 15.6, "auto")
    full = L.with_sensor(aps, "full_frame")
    assert (full.sensor_w_mm, full.sensor_h_mm, full.fit) == (36.0, 24.0, "auto")
    custom = L.with_sensor(aps, "custom")
    assert (custom.sensor, custom.sensor_w_mm, custom.fit) == ("custom", 23.5, "auto")
    assert L.frame_aspect(KB, None) == 1.5
    assert L.frame_aspect(KB, (3000, 4000)) == 0.75


def test_pinhole_invariant_of_the_formulas():
    """§3.2: gate-relative NDC = (x / (z tw), y / (z th)) in both branches, any overscan."""
    rng = random.Random(42)
    for _ in range(200):
        lens = Lens(focal_mm=rng.uniform(10, 600))
        a, a_w, o = rng.uniform(0.5, 2.0), rng.uniform(0.5, 2.5), rng.uniform(1.0, 1.5)
        tw, th = L.gate_tan_half(lens, a)
        t = L.view_tan_half_v(lens, a, a_w, o)
        half_w, half_h = L.gate_rect_ndc(a, a_w, o)
        x, y, z = rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(1, 10)
        ndc_x, ndc_y = x / (z * t * a_w), y / (z * t)
        assert ndc_x / half_w == pytest.approx(x / (z * tw), rel=1e-12)
        assert ndc_y / half_h == pytest.approx(y / (z * th), rel=1e-12)
