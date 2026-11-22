"""`lookdev_optics` (AD-038 §6, E6), headless: the parametric studio with the eye's constants is the eye's `td_env`, the
SH9 projection against a numerical integral, the colour pipeline and the frame dict."""

from __future__ import annotations

import math

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from viewport import eye_optics as eo
from viewport import lookdev_optics as lo


def _unit(n: int, seed: int) -> np.ndarray:
    x = np.random.default_rng(seed).normal(size=(n, 3))
    return x / np.linalg.norm(x, axis=1, keepdims=True)


@pytest.mark.parametrize("roughness", [0.0, 0.04, 0.3, 0.8, 1.0])
def test_ld_studio_with_the_eye_constants_is_td_env(roughness):
    d = _unit(2000, 1)
    assert np.abs(lo.ld_studio(d, roughness, lo.EYE_STUDIO) - eo.td_env(d, roughness)).max() <= 1e-6


def _irradiance(studio, normals, count=300_000) -> np.ndarray:
    """E(n) / pi by a dense numerical integral of the sharp studio."""
    d = lo.fibonacci_directions(count)
    radiance = lo.ld_studio(d, 0.0, studio)
    weight = np.maximum(d @ normals.T, 0.0) * (4.0 * math.pi / count) / math.pi  # (count, normals)
    return weight.T @ radiance


def test_sh9_projection_matches_a_numerical_integral():
    """E6: the 4,096-direction projection against the SH9 coefficients of a dense integral (300k directions), as
    irradiance at 200 normals: <= 1 % of the largest irradiance. The band limit itself (SH9 vs the exact irradiance) is
    reported in `test_sh9_band_limit_of_the_presets` (AD-038 implementation note)."""
    studio = lo.EYE_STUDIO
    sh = lo.sh9_project(studio)
    dense = lo.sh9_project(studio, count=300_000)
    normals = lo.fibonacci_directions(200)
    a, b = lo.sh9_eval(sh, normals), lo.sh9_eval(dense, normals)
    assert np.abs(a - b).max() <= 0.01 * np.abs(b).max()
    exact = _irradiance(studio, normals)
    assert np.abs(b - exact).max() <= 0.05 * exact.max()  # SH9's own band limit on the eye's small, bright softbox


def test_sh9_of_a_uniform_dome_is_its_radiance():
    grey = lo.Studio((0.3, 0.3, 0.3), (0.3, 0.3, 0.3), (0.3, 0.3, 0.3))
    normals = _unit(50, 2)
    assert np.abs(lo.sh9_eval(lo.sh9_project(grey), normals) - 0.3).max() < 1e-3  # Lambert: albedo x E/pi = L


def test_project_cached_once_per_studio_content():
    studio = lo.Studio((0.2, 0.2, 0.2), (0.1, 0.1, 0.1), (0.05, 0.05, 0.05))
    assert lo.project_cached(studio) is lo.project_cached(lo.Studio((0.2, 0.2, 0.2), (0.1, 0.1, 0.1),
                                                                    (0.05, 0.05, 0.05)))


def test_colour_pipeline():
    c = np.linspace(0.0, 1.0, 101)
    assert np.abs(lo.srgb_encode(lo.srgb_decode(c)) - c).max() < 1e-12
    assert abs(float(lo.srgb_decode(0.5)) - 0.21404114) < 1e-6
    rgb = np.array([[0.8, 0.4, 0.2], [4.0, 4.0, 4.0]])
    t = lo.tone(rgb)
    assert np.allclose(t[0] / t[0, 0], rgb[0] / rgb[0, 0])  # luminance Reinhard keeps the hue
    assert np.allclose(t[1], 4.0 / 5.0)
    assert np.allclose(lo.tone(rgb, "clamp"), np.clip(rgb, 0, 1))
    assert np.allclose(lo.lookdev_output(rgb, 2.0), lo.srgb_encode(lo.tone(rgb * 2.0)))


def _state(**kw):
    defaults = dict(preset="test", studio=lo.EYE_STUDIO, key=lo.StudioLight(True, 2.0, 45.0, 30.0, 5600.0, 0.1),
                    fill=lo.StudioLight(True, 0.5, -60.0, 5.0, 6500.0, 0.25),
                    rim=lo.StudioLight(False, 1.0, -150.0, 25.0, 7500.0, 0.05))
    defaults.update(kw)
    return lo.LookdevState(**defaults)


def test_frame_uniforms_lights_rotation_and_the_worklight_names():
    values = lo.frame_uniforms(_state())
    key = np.asarray(values["u_ld_light_dir"][0])
    assert np.allclose(key, eo.local_direction(45.0, 30.0))
    assert values["u_ld_light_color"][2] == (0.0, 0.0, 0.0)  # rim off
    assert values["u_key_dir"] == values["u_ld_light_dir"][0] and values["u_fill_color"] == values["u_ld_light_color"][1]
    assert values["u_ambient"] == 0.0 and values["u_key_wrap"] == values["u_fill_wrap"] == 0.0
    assert len(values["u_ld_sh"]) == 9 and len(values["u_ld_studio_centre"]) == 4 and values["u_ld_studio_n"] == 2
    up, right = np.asarray(values["u_ld_key_up"]), np.asarray(values["u_ld_key_right"])
    assert abs(up @ key) < 1e-9 and abs(right @ key) < 1e-9 and abs(up @ right) < 1e-9 and up[1] > 0
    # rotation turns the lights and the studio together: env_rot maps a rotated light back to its studio direction
    turned = lo.frame_uniforms(_state(rotation=90.0))
    rot = np.asarray(turned["u_ld_env_rot"]).reshape(3, 3).T
    assert np.allclose(rot @ np.asarray(turned["u_ld_light_dir"][0]), eo.local_direction(45.0, 30.0))
    assert np.allclose(np.asarray(turned["u_ld_light_dir"][0]), eo.local_direction(135.0, 30.0))
    assert lo.frame_uniforms(_state(exposure=1.0))["u_ld_exposure"] == 2.0


def test_licht_folgt_kamera_takes_the_camera_frame():
    from mirai.viewport.camera import OrbitCamera
    from viewport.light_rig import SPACE_CAMERA, frame_for, world_direction

    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=4.0, yaw=0.7, pitch=0.3)
    world = lo.frame_uniforms(_state(), camera)
    follow = lo.frame_uniforms(_state(follow_camera=True), camera)
    assert world["u_ld_light_dir"][0] == lo.frame_uniforms(_state())["u_ld_light_dir"][0]
    assert np.allclose(follow["u_ld_light_dir"][0], world_direction(45.0, 30.0, frame_for(SPACE_CAMERA, camera)))


def test_ld_diffuse_and_specular_twins():
    values = lo.frame_uniforms(_state(env_intensity=0.0))
    n = np.array([lo.frame_uniforms(_state())["u_ld_light_dir"][0]])
    lambert = lo.ld_diffuse(n, (0.0, 0.0, 0.0), values)
    key = np.asarray(values["u_ld_light_color"][0])
    fill = np.asarray(values["u_ld_light_color"][1]) * max(float(n[0] @ np.asarray(values["u_ld_light_dir"][1])), 0)
    assert np.allclose(lambert[0], key + fill)
    spec = lo.ld_specular(n, n, 0.5, 0.04, values)
    alpha = 0.25 + 0.1
    peak = 1.0 / (math.pi * alpha * alpha) * (0.5 / (2 * 1.0)) * 1.0 * 0.04  # D(1) x V(1, 1) x N.L x F0
    assert np.allclose(spec[0], key * peak + np.asarray(values["u_ld_light_color"][1])
                       * lo.direct_specular(n, n, np.asarray(values["u_ld_light_dir"][1]),
                                            lo.ld_lobe(0.5, 0.25), 0.04)[0])


# -- AD-039 P3: the effect switches and S1's shadow frustum ------------------------------------------------------------

def test_effects_default_on_and_dependencies_and_features():
    from viewport.lookdev_features import FeatureReport

    assert lo.LookdevEffects().shadow and lo.LookdevEffects.names() == ("shadow",)
    assert lo.LookdevState("x", lo.EYE_STUDIO, lo.StudioLight(), lo.StudioLight(), lo.StudioLight()).effects \
        == lo.LookdevEffects()
    on = lo.LookdevEffects(shadow=True)
    assert lo.effective(on) == on and lo.effect_reasons(on) == {"shadow": None}  # nothing probed: nothing missing
    assert lo.effective(on, FeatureReport(depth_texture=True)) == on
    missing = FeatureReport(depth_texture=False)
    assert lo.effective(on, missing) == lo.LookdevEffects(shadow=False)
    assert lo.effect_reasons(on, missing) == {"shadow": "Tiefentextur fehlt"}
    assert missing.status_lines() == ("LookDev: Schatten aus – Tiefentextur nicht verfügbar",)
    assert lo.effective(lo.LookdevEffects(shadow=False)) == lo.LookdevEffects(shadow=False)


def _head_like(rng, n=400):
    """An ellipsoid point cloud about 30 units across (a head in cm), its object bounds and a model matrix."""
    p = rng.normal(size=(n, 3))
    p /= np.linalg.norm(p, axis=1, keepdims=True)
    p *= np.array([12.0, 15.0, 13.0])
    a = 0.4
    model = np.identity(4)
    model[:3, :3] = [[math.cos(a), 0.0, math.sin(a)], [0.0, 1.0, 0.0], [-math.sin(a), 0.0, math.cos(a)]]
    model[:3, 3] = (3.0, 160.0, -2.0)
    return p, (tuple(p.min(0)), tuple(p.max(0)), list(model.T.reshape(-1))), model


def test_shadow_frustum_holds_every_caster_vertex_and_a_pose_inside_its_margin():
    """T1-8: every caster vertex (through its model matrix) is inside the light's box for any key direction; a pose step
    that stays inside the 15 % margin keeps every vertex inside the unchanged frustum."""
    rng = np.random.default_rng(3)
    p, box, model = _head_like(rng)
    teeth = rng.uniform(-2.0, 2.0, (50, 3)) + (0.0, -8.0, 9.0)
    boxes = [box, (tuple(teeth.min(0)), tuple(teeth.max(0)), None)]
    centre, radius = lo.shadow_frustum(boxes)
    world = np.concatenate([p @ model[:3, :3].T + model[:3, 3], teeth])
    for key in rng.normal(size=(24, 3)).tolist() + [[0.0, 1.0, 0.0], [0.0, -1.0, 0.0]]:
        vp = lo.shadow_view_projection(key, centre, radius)
        sp = lo.shadow_coords(world, np.zeros_like(world), vp, 0.0)
        assert np.all((sp >= 0.0) & (sp <= 1.0)), key
        # the light side of the sphere is depth 0, the key looks along -key
        k = np.asarray(key) / np.linalg.norm(key)
        near = lo.shadow_coords(np.asarray(centre) + k * radius * 0.999, np.zeros(3), vp, 0.0)
        assert near[2] < 0.01 and abs(near[0] - 0.5) < 1e-9 and abs(near[1] - 0.5) < 1e-9
    # a pose step: the lower half moves by 10 % of the head's size (a jaw), still inside the grown sphere
    posed = world.copy()
    posed[posed[:, 1] < 160.0] += (0.0, -2.5, 1.5)
    vp = lo.shadow_view_projection((0.4, 0.7, 0.6), centre, radius)
    sp = lo.shadow_coords(posed, np.zeros_like(posed), vp, 0.0)
    assert np.all((sp >= 0.0) & (sp <= 1.0))
    # the sphere grows by the margin around the union's bounding box
    lo_all, hi_all = world.min(0), world.max(0)
    assert radius >= np.linalg.norm(hi_all - lo_all) / 2.0 * 1.15 - 1e-6


def test_shadow_uniforms_spacing_grows_with_the_keys_softness():
    vp = lo.shadow_view_projection((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), 20.0)
    sharp, soft = lo.shadow_uniforms(vp, 20.0, 0.0), lo.shadow_uniforms(vp, 20.0, 0.5)
    assert sharp["u_ld_shadow_radius"] == pytest.approx(1.0 / lo.SHADOW_SIZE)
    assert soft["u_ld_shadow_radius"] == pytest.approx((1.0 + lo.SHADOW_SOFTNESS_TEXELS * 0.5) / lo.SHADOW_SIZE)
    assert sharp["u_ld_shadow_offset"] == pytest.approx(lo.SHADOW_NORMAL_OFFSET_TEXELS * 40.0 / lo.SHADOW_SIZE)


def test_pcf_visibility_and_the_shadowed_key():
    depth = np.full((8, 8), 0.5)
    depth[:, :4] = 0.2  # the left half is occluded at 0.2
    vis = lo.pcf_visibility(depth, np.array([[0.3, 0.5, 0.4], [0.8, 0.5, 0.4], [1.2, 0.5, 0.9], [0.9, 0.5, 0.45]]),
                            1.0 / 8)
    assert vis[0] == 0.0 and vis[1] == 1.0 and vis[2] == 1.0 and vis[3] == 1.0  # occluded, lit, outside, lit
    values = lo.frame_uniforms(lo.LookdevState("x", lo.EYE_STUDIO, lo.StudioLight(True, 1.0, 20.0, 40.0),
                                               lo.StudioLight(True, 0.5, -60.0, 10.0), lo.StudioLight(False)))
    rng = np.random.default_rng(5)
    n = rng.normal(size=(64, 3))
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    v = np.tile([0.0, 0.0, 1.0], (64, 1))
    albedo = np.array([0.5, 0.4, 0.3])
    full = lo.ld_key_shadowed(albedo, n, v, (0.2, 0.1, 0.0), 0.5, 0.04, values, np.ones(64))
    plain = albedo * lo.ld_diffuse(n, (0.2, 0.1, 0.0), values) + lo.ld_specular(n, v, 0.5, 0.04, values)
    assert np.allclose(full, plain)
    dark = lo.ld_key_shadowed(albedo, n, v, (0.2, 0.1, 0.0), 0.5, 0.04, values, np.zeros(64))
    no_key = dict(values, u_ld_light_color=[(0.0, 0.0, 0.0)] + list(values["u_ld_light_color"][1:]))
    assert np.allclose(dark, albedo * lo.ld_diffuse(n, (0.2, 0.1, 0.0), no_key)
                       + lo.ld_specular(n, v, 0.5, 0.04, no_key))
