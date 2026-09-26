"""GL-free rig math: T4 (directions), T5 (temperature), T6 (reference formula)."""

from __future__ import annotations

import math

import pytest

from mirai.viewport.camera import OrbitCamera

from viewport_shading_lab.lab_rig import (
    HEUTE_KEY_AZIMUTH,
    HEUTE_KEY_ELEVATION,
    PRESET_HEUTE,
    PRESET_ORDER,
    PRESET_RAITT,
    PRESETS,
    SPACE_CAMERA,
    SPACE_WORLD,
    LightRig,
    coupled_fill_angles,
    frame_for,
    kelvin_to_rgb,
    local_direction,
    luminance,
    resolve,
    shade,
    world_direction,
)

BASE = (0.72, 0.75, 0.82)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _cameras():
    cams = []
    for yaw, pitch in ((0.0, 0.0), (0.8, 0.3), (-2.1, -0.6), (3.0, 1.2)):
        cam = OrbitCamera(target=(0.1, 1.5, -0.2), distance=4.0)
        cam.orbit(yaw, pitch)
        cams.append(cam)
    return cams


# -- T4 ------------------------------------------------------------------------------


def test_world_mode_direction_is_camera_independent():
    rig = PRESETS[PRESET_RAITT].with_(space=SPACE_WORLD)
    reference = resolve(rig, None)
    for cam in _cameras():
        u = resolve(rig, cam)
        assert _close(u["u_key_dir"], reference["u_key_dir"])
        assert _close(u["u_fill_dir"], reference["u_fill_dir"])


def test_camera_mode_components_constant_under_orbit():
    rig = PRESETS[PRESET_RAITT]
    assert rig.space == SPACE_CAMERA
    cam = OrbitCamera(distance=5.0)
    expected_key = local_direction(rig.key_azimuth, rig.key_elevation)
    expected_fill = local_direction(*rig.effective_fill_angles())
    for step in range(12):
        cam.orbit(0.37, 0.11 if step < 6 else -0.2)
        u = resolve(rig, cam)
        frame = frame_for(SPACE_CAMERA, cam)
        assert _close([_dot(u["u_key_dir"], axis) for axis in frame], expected_key, 1e-12)
        assert _close([_dot(u["u_fill_dir"], axis) for axis in frame], expected_fill, 1e-12)


def test_camera_mode_az0_el0_points_to_viewer():
    cam = _cameras()[1]
    forward, _right, _up = cam.basis()
    d = world_direction(0.0, 0.0, frame_for(SPACE_CAMERA, cam))
    assert _close(d, tuple(-c for c in forward), 1e-12)


@pytest.mark.parametrize("az,el", [(-45.0, 35.0), (0.0, 0.0), (170.0, -20.0), (90.0, 89.0)])
def test_coupling_formula(az, el):
    rig = LightRig(key_azimuth=az, key_elevation=el, fill_coupled=True)
    fill_az, fill_el = rig.effective_fill_angles()
    assert fill_el == -el
    assert math.isclose(math.cos(math.radians(fill_az)), -math.cos(math.radians(az)), abs_tol=1e-12)
    assert math.isclose(math.sin(math.radians(fill_az)), -math.sin(math.radians(az)), abs_tol=1e-12)
    assert coupled_fill_angles(az, el) == (fill_az, fill_el)
    # Uncoupled: own angles.
    free = rig.with_(fill_coupled=False, fill_azimuth=12.0, fill_elevation=7.0)
    assert free.effective_fill_angles() == (12.0, 7.0)


def test_heute_angles_resolve_to_production_light_dir():
    x, y, z = 0.4, 0.6, 0.7
    n = math.sqrt(x * x + y * y + z * z)
    rig = PRESETS[PRESET_HEUTE]
    assert (rig.key_azimuth, rig.key_elevation) == (HEUTE_KEY_AZIMUTH, HEUTE_KEY_ELEVATION)
    assert _close(resolve(rig)["u_key_dir"], (x / n, y / n, z / n), 1e-9)


# -- T5 ------------------------------------------------------------------------------


def test_temperature_luminance_is_one_over_range():
    for kelvin in range(2500, 10001, 50):
        assert abs(luminance(kelvin_to_rgb(kelvin)) - 1.0) <= 1e-6, kelvin


def test_6500k_is_neutral():
    # Documented tolerance: 1e-9 per channel (exact by construction, white balance to 6500 K).
    assert _close(kelvin_to_rgb(6500), (1.0, 1.0, 1.0), 1e-9)


def test_warm_and_cold_hue():
    r, _g, b = kelvin_to_rgb(3000)
    assert r > b
    r, _g, b = kelvin_to_rgb(9000)
    assert b > r


def test_temperature_changes_hue_monotonically():
    reds = [kelvin_to_rgb(k)[0] for k in range(2500, 10001, 500)]
    blues = [kelvin_to_rgb(k)[2] for k in range(2500, 10001, 500)]
    assert reds == sorted(reds, reverse=True)
    assert blues == sorted(blues)


# -- T6 ------------------------------------------------------------------------------


def _uniforms(**overrides):
    u = {
        "u_key_dir": (0.0, 0.0, 1.0),
        "u_key_color": (0.8, 0.8, 0.8),
        "u_key_wrap": 0.0,
        "u_fill_dir": (0.0, 0.0, -1.0),
        "u_fill_color": (0.0, 0.0, 0.0),
        "u_fill_wrap": 0.0,
        "u_ambient": 0.1,
    }
    u.update(overrides)
    return u


def test_wrap_zero_is_lambert():
    u = _uniforms()
    for angle in range(0, 181, 10):
        a = math.radians(angle)
        normal = (math.sin(a), 0.0, math.cos(a))
        lambert = max(math.cos(a), 0.0)
        expected = tuple(BASE[i] * (0.1 + 0.8 * lambert) for i in range(3))
        assert _close(shade(normal, u, BASE), expected, 1e-12)


def test_wrap_lights_beyond_terminator():
    u = _uniforms(u_ambient=0.0, u_key_wrap=0.5)
    a = math.radians(100)  # 10° beyond the terminator
    normal = (math.sin(a), 0.0, math.cos(a))
    assert all(c > 0.0 for c in shade(normal, u, BASE))
    assert all(c == 0.0 for c in shade(normal, _uniforms(u_ambient=0.0), BASE))


def test_fill_off_contributes_nothing():
    rig = PRESETS[PRESET_RAITT].with_(fill_ratio=None, fill_wrap=0.8)
    u = resolve(rig, OrbitCamera())
    assert u["u_fill_color"] == (0.0, 0.0, 0.0)
    no_fill = dict(u, u_fill_dir=(1.0, 0.0, 0.0), u_fill_wrap=0.0)
    for normal in ((0, 0, 1), (0, 0, -1), (1, 0, 0), (0.3, -0.8, 0.2)):
        assert _close(shade(normal, u, BASE), shade(normal, no_fill, BASE), 1e-15)


def test_heute_matches_production_formula():
    # Production: mix(base * 0.35, base, ndl) with ndl = max(dot(n, normalize(LIGHT_DIR)), 0).
    u = resolve(PRESETS[PRESET_HEUTE])
    light = u["u_key_dir"]
    for normal in ((0, 1, 0), (1, 0, 0), (-0.2, 0.3, 0.9), (0, -1, 0), (0.5, -0.5, 0.1)):
        length = math.sqrt(_dot(normal, normal))
        n = tuple(c / length for c in normal)
        ndl = max(_dot(n, light), 0.0)
        production = tuple(BASE[i] * 0.35 * (1 - ndl) + BASE[i] * ndl for i in range(3))
        assert _close(shade(normal, u, BASE), production, 1e-12)


# -- presets / E11 -----------------------------------------------------------------------


def test_presets_exist_in_order_and_sum():
    assert PRESET_ORDER == ("Heute", "Raitt 2:1", "Softbox", "Warm/Kalt")
    for name in PRESET_ORDER:
        assert PRESETS[name].exposure_sum() == pytest.approx(1.0)
