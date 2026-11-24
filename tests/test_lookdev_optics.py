"""`lookdev_optics` (AD-038 §6, E6), headless: the parametric studio with the eye's constants is the eye's `td_env`, the
SH9 projection against a numerical integral, the colour pipeline and the frame dict."""

from __future__ import annotations

import math

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from viewport import eye_optics as eo
from viewport import lookdev_optics as lo
from viewport import lookdev_shaders as ls


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

    assert lo.LookdevEffects().shadow
    assert lo.LookdevEffects.names() == ("shadow", "eye_shadow", "dual_lobe", "thickness", "cube", "regions", "maps",
                                         "area_diffuse", "soft_shadow")
    assert not lo.LookdevEffects().area_diffuse  # S8: off until Manu's practical test (AD-039 §23)
    assert not lo.LookdevEffects().soft_shadow  # S9: off until Manu's practical test (AD-039 §24)
    assert lo.LookdevState("x", lo.EYE_STUDIO, lo.StudioLight(), lo.StudioLight(), lo.StudioLight()).effects \
        == lo.LookdevEffects()
    on = lo.LookdevEffects(shadow=True)
    assert lo.effective(on) == on  # nothing probed: nothing missing
    assert lo.effect_reasons(on) == {"shadow": None, "eye_shadow": None, "dual_lobe": None, "thickness": None,
                                     "cube": None, "regions": None, "maps": None, "area_diffuse": None,
                                     "soft_shadow": None}
    assert lo.effective(on, FeatureReport(depth_texture=True)) == on
    missing = FeatureReport(depth_texture=False)
    # S3 needs no feature and no other effect: it stays on without a depth texture
    assert lo.effective(on, missing) == lo.LookdevEffects(shadow=False, eye_shadow=False, dual_lobe=True,
                                                          thickness=False)
    assert lo.effect_reasons(on, missing) == {"shadow": "Tiefentextur fehlt", "eye_shadow": "braucht Schatten",
                                              "dual_lobe": None, "thickness": "braucht Schatten", "cube": None,
                                              "regions": None, "maps": None, "area_diffuse": None,
                                              "soft_shadow": "braucht Schatten"}
    assert missing.status_lines() == ("LookDev: Schatten aus – Tiefentextur nicht verfügbar",)
    assert lo.effective(lo.LookdevEffects(shadow=False)) == lo.LookdevEffects(shadow=False, eye_shadow=False,
                                                                               thickness=False)
    # S4 needs sampler objects: without them only the thickness is off, with its feature's reason
    no_samplers = FeatureReport(sampler_objects=False)
    assert lo.effective(on, no_samplers) == lo.LookdevEffects(thickness=False)
    assert lo.effect_reasons(on, no_samplers)["thickness"] == "Sampler-Objekte fehlen"
    assert no_samplers.status_lines() == ("LookDev: Durchleuchtung aus – Sampler-Objekte nicht verfügbar",)
    assert lo.effective(lo.LookdevEffects(dual_lobe=False)) == lo.LookdevEffects(dual_lobe=False)
    # S7 / S6 need enough texture units, nothing else: without them only the maps and the region materials are off
    few_units = FeatureReport(texture_units=False)
    assert lo.effective(on, few_units) == lo.LookdevEffects(regions=False, maps=False)
    assert lo.effect_reasons(on, few_units)["maps"] == "zu wenige Textureinheiten"
    assert lo.effect_reasons(on, few_units)["regions"] == "zu wenige Textureinheiten"
    assert few_units.status_lines() == ("LookDev: Maps und Region-Materialien aus – zu wenige Textureinheiten",)
    assert lo.effective(lo.LookdevEffects(shadow=False)).maps
    # S5 needs a complete RGBA16F cube target, nothing else: without it only the cube is off
    no_cube = FeatureReport(cube_rgba16f=False)
    assert lo.effective(on, no_cube) == lo.LookdevEffects(cube=False)
    assert lo.effect_reasons(on, no_cube)["cube"] == "Cube-Ziel fehlt"
    assert no_cube.status_lines() == ("LookDev: Umgebungs-Cube aus – Cube-Ziel nicht verfügbar",)
    assert lo.effective(lo.LookdevEffects(shadow=False)).cube
    assert lo.effective(lo.LookdevEffects(shadow=False)).regions
    # S8 needs no feature and no other effect: on stays on, without the shadow and with every feature missing
    soft = lo.LookdevEffects(area_diffuse=True)
    assert lo.effective(soft, FeatureReport(depth_texture=False, sampler_objects=False, cube_rgba16f=False,
                                            texture_units=False)).area_diffuse
    assert lo.effective(lo.LookdevEffects(shadow=False, area_diffuse=True)).area_diffuse
    # S9 needs the shadow and sampler objects (the raw depth on unit 7, as S4)
    sharp = lo.LookdevEffects(soft_shadow=True)
    assert lo.effective(sharp) == sharp
    assert not lo.effective(lo.LookdevEffects(shadow=False, soft_shadow=True)).soft_shadow
    assert lo.effect_reasons(lo.LookdevEffects(shadow=False, soft_shadow=True))["soft_shadow"] == "braucht Schatten"
    assert not lo.effective(sharp, no_samplers).soft_shadow
    assert lo.effect_reasons(sharp, no_samplers)["soft_shadow"] == "Sampler-Objekte fehlen"
    assert not lo.effective(sharp, missing).soft_shadow


# -- AD-039 S6: region materials ---------------------------------------------------------------------------------------

def test_face_material_slots_let_the_later_region_win():
    """AD-039 §9: slot i + 1 for region i; a face in two regions takes the later one; `faces` limits the map."""
    a, b = frozenset({1, 2, 3}), frozenset({3, 4})
    assert lo.face_material_slots((a, b)) == {1: 1, 2: 1, 3: 2, 4: 2}
    assert lo.face_material_slots((b, a)) == {1: 2, 2: 2, 3: 2, 4: 1}
    assert lo.face_material_slots((a, b), faces={2, 3, 9}) == {2: 1, 3: 2}
    assert lo.face_material_slots(()) == {}


def test_region_slot_rounds_and_draws_slot_0_outside_the_slots():
    """The `REGIONS` block's pick: the stored float rounded; below 0 or past the last slot = the object's material."""
    texel = np.array([0.0, 1.0, 1.0001, 1.9999, 4.0, 5.0, -1.0, 2.49])
    assert lo.region_slot(texel, 4).tolist() == [0, 1, 1, 2, 4, 0, 0, 2]


# -- AD-039 S5: the environment cube -----------------------------------------------------------------------------------

def test_cube_directions_follow_the_gl_table_and_the_corner_fix():
    """GLSL `ld_cube_direction`: each face's centre is its axis; (s, t) run as GL's table; the corner fix puts a
    corner texel on the cube corner's direction, the same for the three faces that meet there."""
    axes = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    for face, axis in enumerate(axes):
        assert np.allclose(lo.cube_face_direction(face, 0.0, 0.0), axis)
    assert np.allclose(lo.cube_face_direction(0, 0.5, 0.25), (1.0, -0.25, -0.5))  # +X: (1, -t, -s)
    assert np.allclose(lo.cube_face_direction(2, 0.5, 0.25), (0.5, 1.0, 0.25))   # +Y: (s, 1, t)
    side = 8
    fixed, plain = lo.cube_texel_directions(0, side), lo.cube_texel_directions(0, side, corner_fix=False)
    assert np.allclose(np.linalg.norm(fixed, axis=-1), 1.0)
    assert np.allclose(fixed[0, 0], np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0))  # +X, s = t = -1: (1, 1, 1)
    assert not np.allclose(plain[0, 0], fixed[0, 0]) and np.allclose(plain[1:-1], fixed[1:-1])
    # the corner (1, 1, 1) on +X (s = t = -1), +Y (s = 1, t = 1) and +Z (s = 1, t = -1)
    corner = [lo.cube_texel_directions(0, side)[0, 0], lo.cube_texel_directions(2, side)[-1, -1],
              lo.cube_texel_directions(4, side)[0, -1]]
    assert np.allclose(corner[0], corner[1]) and np.allclose(corner[0], corner[2])


def test_radical_inverse_and_the_cube_lod():
    assert [float(lo.radical_inverse(i)) for i in range(5)] == [0.0, 0.5, 0.25, 0.75, 0.125]
    assert lo.cube_level_roughness(0) == 0.0 and lo.cube_level_roughness(ls.CUBE_LEVELS - 1) == 1.0
    assert np.allclose(lo.cube_lod([-0.2, 0.0, 0.5, 1.0, 1.7]), [0.0, 0.0, 3.0, 6.0, 6.0])


def test_prefilter_ggx_is_the_studio_at_level_0_and_keeps_a_constant_environment():
    """`prefilter_ggx` with one sample is `ld_studio(d, 0)`; a constant studio stays constant at every roughness (the
    N.L-weighted mean of a constant); a rough level of a real studio is smoother than its sharp content and stays in its
    range."""
    d = lo.fibonacci_directions(64)
    studio = lo.EYE_STUDIO
    assert np.allclose(lo.prefilter_ggx(d, 0.0, studio, samples=1), lo.ld_studio(d, 0.0, studio))
    grey = lo.Studio((0.3, 0.2, 0.1), (0.3, 0.2, 0.1), (0.3, 0.2, 0.1))
    for r in (1 / 6, 0.5, 1.0):
        assert np.allclose(lo.prefilter_ggx(d, r, grey), (0.3, 0.2, 0.1), atol=1e-9)
    sharp = lo.ld_studio(d, 0.0, studio)
    rough = lo.prefilter_ggx(d, 1.0, studio)
    assert rough.max() < sharp.max() and rough.min() >= sharp.min() - 1e-9


# -- AD-039 S3: dual-lobe specular ------------------------------------------------------------------------------------

def test_ld_specular_dual_is_the_mix_of_two_widened_lobes():
    """AD-039 §6: per light 0.85 x the lobe at roughness x 0.75 and 0.15 x the lobe at x 1.3, each widened by the
    light's size as `ld_lobe`; summed over the three lights like `ld_specular`."""
    from viewport.lookdev_shaders import DUAL_LOBE_MIX, DUAL_LOBE_SCALES

    assert (DUAL_LOBE_SCALES, DUAL_LOBE_MIX) == ((0.75, 1.3), 0.85)  # Q-P3-7: fixed in P3
    values = lo.frame_uniforms(_state())
    n, v = _unit(64, 1), _unit(64, 2)
    v = eo.normalize(n + 0.5 * v)
    rough = np.linspace(0.1, 1.0, 64)
    want = 0.0
    for d, c, size in zip(values["u_ld_light_dir"], values["u_ld_light_color"], values["u_ld_light_size"]):
        one = (0.85 * lo.direct_specular(n, v, d, lo.ld_lobe(0.75 * rough, size), 0.04)
               + 0.15 * lo.direct_specular(n, v, d, lo.ld_lobe(1.3 * rough, size), 0.04))
        assert np.allclose(lo.ld_direct_dual(n, v, d, rough, size, 0.04), one)
        want = want + np.asarray(c) * one[:, None]
    assert np.allclose(lo.ld_specular_dual(n, v, rough, 0.04, values), want)
    # in the light (visibility 1) the shadowed twin is the plain sum with the dual highlight
    albedo, wrap = np.array([0.4, 0.3, 0.25]), (0.2, 0.1, 0.05)
    lit = lo.ld_key_shadowed(albedo, n, v, wrap, rough, 0.04, values, np.ones(64), dual=True)
    assert np.allclose(lit, albedo * lo.ld_diffuse(n, wrap, values) + want)
    # in the key's full shadow the key's dual highlight and its wrapped diffuse are gone, the fill's and rim's stay
    dark = lo.ld_key_shadowed(albedo, n, v, wrap, rough, 0.04, values, np.zeros(64), dual=True)
    d, c, size = values["u_ld_light_dir"][0], np.asarray(values["u_ld_light_color"][0]), values["u_ld_light_size"][0]
    key = c * (albedo * lo.ld_wrap(n @ np.asarray(d), wrap)
               + lo.ld_direct_dual(n, v, d, rough, size, 0.04)[:, None])
    assert np.allclose(dark, lit - key)


def _directional_albedo(specular, mu: float, count: int = 600) -> float:
    """The integral of `specular(l)` x dω over the hemisphere around n = +Z, seen from cos θ_v = mu (F0 = 1)."""
    theta = (np.arange(count) + 0.5) / count * (math.pi / 2)
    phi = (np.arange(count) + 0.5) / count * (2 * math.pi)
    t, p = np.meshgrid(theta, phi, indexing="ij")
    l = np.stack([np.sin(t) * np.cos(p), np.sin(t) * np.sin(p), np.cos(t)], -1).reshape(-1, 3)
    weight = (np.sin(t) * (math.pi / 2 / count) * (2 * math.pi / count)).reshape(-1)
    v = np.array([math.sqrt(1.0 - mu * mu), 0.0, mu])
    return float(np.sum(specular(np.array([0.0, 0.0, 1.0]), v, l) * weight))


@pytest.mark.parametrize("roughness", [0.2, 0.4, 0.6, 0.8])
def test_the_dual_lobe_keeps_energy(roughness):
    """AD-039 §6 / §18.2 (S3-1): each lobe is a normalised GGX distribution, so their mix is one (within 2 %); the mix
    reflects no more than comes in (F0 = 1: directional albedo <= 1) and no less than the single lobe (its sharper main
    lobe loses less to Smith masking, the single-scatter GGX's known loss) - near the single lobe for r <= 0.4, up to a
    third more at r = 0.8 (the table in §18.2)."""
    for scale in (0.75, 1.3):
        alpha = min(roughness * scale, 1.0) ** 2
        count = 1200
        theta = (np.arange(count) + 0.5) / count * (math.pi / 2)
        ndf = np.sum(lo.ggx_d(np.cos(theta), alpha) * np.cos(theta) * np.sin(theta)) * (math.pi / 2 / count) * 2 * math.pi
        assert abs(ndf - 1.0) < 0.02, (scale, ndf)
    for mu in (1.0, 0.7, 0.35):
        single = _directional_albedo(lambda n, v, l: lo.direct_specular(n, v, l, roughness, 1.0), mu)
        dual = _directional_albedo(lambda n, v, l: lo.ld_direct_dual(n, v, l, roughness, 0.0, 1.0), mu)
        assert single - 0.01 <= dual <= 1.0, (mu, single, dual)
        if roughness <= 0.4:
            assert dual <= single * 1.05, (mu, single, dual)


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


def test_the_keys_softness_is_the_maps_effective_resolution():
    assert lo.shadow_resolution(0.0) == lo.SHADOW_SIZE
    sizes = [lo.shadow_resolution(s) for s in (0.0, 0.1, 0.26, 0.5, 1.0)]
    assert sizes == sorted(sizes, reverse=True) and sizes[-1] >= lo.SHADOW_MIN_RESOLUTION
    assert lo.shadow_resolution(1.0) == round(lo.SHADOW_SIZE / (1.0 + lo.SHADOW_SOFTNESS))
    vp = lo.shadow_view_projection((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), 20.0)
    sharp, soft = lo.shadow_uniforms(vp, 20.0, 0.0), lo.shadow_uniforms(vp, 20.0, 0.5)
    assert sharp["u_ld_shadow_radius"] == soft["u_ld_shadow_radius"] == pytest.approx(1.0 / lo.SHADOW_SIZE)
    assert sharp["u_ld_shadow_scale"] == 1.0
    assert soft["u_ld_shadow_scale"] == pytest.approx(lo.shadow_resolution(0.5) / lo.SHADOW_SIZE)
    assert sharp["u_ld_shadow_offset"] == pytest.approx(lo.SHADOW_NORMAL_OFFSET_TEXELS * 40.0 / lo.SHADOW_SIZE)
    assert soft["u_ld_shadow_offset"] == pytest.approx(lo.SHADOW_NORMAL_OFFSET_TEXELS * 40.0 / lo.shadow_resolution(0.5))


def test_the_receiver_plane_bias():
    """A tilted receiver (slope 0.5 depth per uv) on the surface the map holds (with the depth pass's slope-scaled
    polygon offset: one texel of slope): without the receiver-plane bias the fetches toward the light dip under the
    stored depth (self-shadow), with it none does."""
    sp = np.array([[0.5, 0.5, 0.5 - 0.0002]])
    texel = 1.0 / 16
    tilted = np.full((16, 16), 0.5) + 0.5 * ((np.arange(16)[None, :] + 0.5) * texel - 0.5) + 0.5 * texel
    assert lo.pcf_visibility(tilted, sp, 1.0, (0.5, 0.0))[0] == 1.0
    assert lo.pcf_visibility(tilted, sp, 1.0, (0.0, 0.0))[0] < 0.9


def test_the_normal_offset_goes_sideways_and_the_wrap_lookup_is_lifted_out():
    """AD-039 §16.7: the normal offset is the normal projected off the key (a surface facing the key is not moved toward
    it); the wrap's lookup point is lifted `SHADOW_WRAP_LIFT` offsets out along the normal."""
    vp = lo.shadow_view_projection((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), 1.0)
    p = np.array([0.1, 0.2, 0.3])
    facing = lo.shadow_coords(p, (0.0, 0.0, 1.0), vp, 0.01, key_dir=(0.0, 0.0, 1.0))
    assert np.allclose(facing, lo.shadow_coords(p, (0.0, 0.0, 1.0), vp, 0.0))  # facing the key: not moved
    grazing = lo.shadow_coords(p, (1.0, 0.0, 0.0), vp, 0.01, key_dir=(0.0, 0.0, 1.0))
    assert grazing[0] > facing[0] and grazing[2] == pytest.approx(facing[2])  # sideways only
    lifted = lo.shadow_coords(p, (0.0, 0.0, 1.0), vp, 0.01, key_dir=(0.0, 0.0, 1.0), lift=lo.SHADOW_WRAP_LIFT)
    assert lifted[2] < facing[2]  # out along the normal: toward the key here
    assert lo.SHADOW_WRAP_LIFT > 1.0


def test_pcf_visibility_and_the_shadowed_key():
    depth = np.full((8, 8), 0.5)
    depth[:, :4] = 0.2  # the left half is occluded at 0.2
    vis = lo.pcf_visibility(depth, np.array([[0.3, 0.5, 0.4], [0.8, 0.5, 0.4], [1.2, 0.5, 0.9], [0.9, 0.5, 0.45]]))
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


# -- AD-039 S8 (§23): „Weiches Licht“ - the lights' diffuse term as finite emitters ---------------------------------------

_C = np.linspace(-1.0, 1.0, 2001)


def _area_reference(c, s: float, w, count: int = 16384) -> np.ndarray:
    """The diffuse factor of a sphere light (sin sigma = s) by `count` directions on its cap (a Vogel spiral, uniform in
    solid angle), each wrapped cosine scaled by 2 / (1 + cos sigma) so the lit side stays Lambert - the dense reference
    of the assessment's prototype (`experiments/lookdev_diffuse_area/area_math.area_reference`), the normal in the XZ
    plane at acos(c) from the light's centre (+Z)."""
    i = np.arange(count, dtype=np.float64)
    u, phi = (i + 0.5) / count, i * math.pi * (3.0 - math.sqrt(5.0))
    cos_sigma = math.sqrt(1.0 - s * s)
    cos_a = 1.0 - u * (1.0 - cos_sigma)
    sin_a = np.sqrt(np.maximum(1.0 - cos_a * cos_a, 0.0))
    d = np.stack([sin_a * np.cos(phi), sin_a * np.sin(phi), cos_a], -1)
    n = np.stack([np.sqrt(np.maximum(1.0 - c * c, 0.0)), np.zeros_like(c), c], -1)
    ci = (n @ d.T) * (2.0 / (1.0 + cos_sigma))
    return np.mean(np.maximum((ci + w) / (1.0 + w), 0.0), axis=-1)


def _area(c, size, w=0.0) -> np.ndarray:
    return lo.ld_area_wrap(c, (w, w, w), size)[..., 0]


def test_the_area_mapping_is_provisionally_40_degrees():
    assert ls.AREA_SIN_MAX == pytest.approx(math.sin(math.radians(40.0))) and ls.AREA_SIN_MIN == 1e-4
    assert f"const float LD_AREA_SIN_MAX = {ls.AREA_SIN_MAX!r};" in ls.LD_AREA_SRC


@pytest.mark.parametrize("w", [0.0, 0.3])
def test_a_point_light_is_ld_wrap(w):
    """Size 0: the floor s = 1e-4 leaves at most s / 4 between the spline and `ld_wrap`."""
    assert np.abs(_area(_C, 0.0, w) - lo.ld_wrap(_C, (w, w, w))[..., 0]).max() <= 2.5e-5 + 1e-12


@pytest.mark.parametrize("size", [0.25, 0.5, 1.0])
@pytest.mark.parametrize("w", [0.0, 0.3])
def test_the_lit_side_is_unchanged(size, w):
    """Where the wrapped cosine is at or above sin sigma the light is fully above the horizon: exactly `ld_wrap`."""
    lit = _C + w >= size * ls.AREA_SIN_MAX
    assert np.array_equal(_area(_C, size, w)[lit], lo.ld_wrap(_C, (w, w, w))[..., 0][lit])


@pytest.mark.parametrize("size", [0.1, 0.5, 1.0])
@pytest.mark.parametrize("w", [0.0, 0.3])
def test_the_spline_is_never_below_the_wrap_and_c1(size, w):
    y = _area(_C, size, w)
    assert np.all(y >= lo.ld_wrap(_C, (w, w, w))[..., 0] - 1e-12)
    slope = np.gradient(y, _C)
    assert np.max(np.abs(np.diff(slope))) < 0.01  # no kink (the wrap's knee is one: 1 / (1 + w) at once)


@pytest.mark.parametrize("w", [0.0, 0.3])
def test_a_larger_light_widens_the_band_even_without_wrap(w):
    past = math.cos(math.radians(100.0)) - w  # 10 degrees past the (wrapped) terminator
    values = [float(_area(np.array(past), size, w)) for size in (0.0, 0.25, 0.5, 1.0)]
    assert values[0] == 0.0 and values[1] < values[2] < values[3]
    assert values[3] > 0.05


@pytest.mark.parametrize("size", [0.25, 0.5, 1.0])
@pytest.mark.parametrize("w", [0.0, 0.3])
def test_the_spline_is_within_two_percent_of_the_dense_reference(size, w):
    s = size * ls.AREA_SIN_MAX
    assert np.abs(_area(_C, size, w) - _area_reference(_C, s, w)).max() < 0.02


def test_ld_diffuse_area_is_ld_diffuse_with_each_lights_size():
    values = lo.frame_uniforms(_state())
    n = _unit(256, 3)
    wrap = (0.2, 0.1, 0.05)
    want = values["u_ld_env_intensity"] * lo.sh9_eval(values["u_ld_sh"], n @ np.asarray(values["u_ld_env_rot"])
                                                      .reshape(3, 3))
    for d, c, size in zip(values["u_ld_light_dir"], values["u_ld_light_color"], values["u_ld_light_size"]):
        want = want + np.asarray(c) * lo.ld_area_wrap(n @ np.asarray(d), wrap, size)
    assert np.allclose(lo.ld_diffuse_area(n, wrap, values), want)
    point = dict(values, u_ld_light_size=[0.0, 0.0, 0.0])
    assert np.abs(lo.ld_diffuse_area(n, wrap, point) - lo.ld_diffuse(n, wrap, point)).max() < 1e-4
    assert np.any(np.abs(lo.ld_diffuse_area(n, wrap, values) - lo.ld_diffuse(n, wrap, values)) > 1e-3)


@pytest.mark.parametrize("dual", [False, True])
def test_the_shadowed_key_with_the_soft_light(dual):
    """`ld_key_shadowed(..., area=True)`: lit = the plain sum with `ld_diffuse_area`; in the key's full shadow the key's
    area term is gone; with the surface in shadow and the lifted point lit only the Lambert part goes - the band past
    the terminator stays with the wrap's excess (rule „lifted“)."""
    values = lo.frame_uniforms(_state(key=lo.StudioLight(True, 2.0, 45.0, 30.0, 5600.0, 0.5)))
    n, v = _unit(64, 1), _unit(64, 2)
    v = eo.normalize(n + 0.5 * v)
    albedo, wrap, rough = np.array([0.4, 0.3, 0.25]), (0.2, 0.1, 0.05), 0.4
    spec = (lo.ld_specular_dual if dual else lo.ld_specular)(n, v, rough, 0.04, values)
    lit = lo.ld_key_shadowed(albedo, n, v, wrap, rough, 0.04, values, np.ones(64), dual=dual, area=True)
    assert np.allclose(lit, albedo * lo.ld_diffuse_area(n, wrap, values) + spec)
    d, c, size = values["u_ld_light_dir"][0], np.asarray(values["u_ld_light_color"][0]), values["u_ld_light_size"][0]
    ndl = n @ np.asarray(d)
    key_spec = (lo.ld_direct_dual(n, v, d, rough, size, 0.04) if dual
                else lo.direct_specular(n, v, d, lo.ld_lobe(rough, size), 0.04))
    dark = lo.ld_key_shadowed(albedo, n, v, wrap, rough, 0.04, values, np.zeros(64), dual=dual, area=True)
    assert np.allclose(dark, lit - c * (albedo * lo.ld_area_wrap(ndl, wrap, size) + key_spec[:, None]))
    lifted = lo.ld_key_shadowed(albedo, n, v, wrap, rough, 0.04, values, np.zeros(64), np.ones(64), dual=dual,
                                area=True)
    assert np.allclose(lifted, lit - c * (albedo * np.maximum(ndl, 0.0)[:, None] + key_spec[:, None]))
    # area off: the S1 / S3 twin as before
    assert np.allclose(lo.ld_key_shadowed(albedo, n, v, wrap, rough, 0.04, values, np.ones(64), dual=dual),
                       albedo * lo.ld_diffuse(n, wrap, values) + spec)


# -- AD-039 S4: the key's light through thin parts ------------------------------------------------------------------

def test_bilinear_depth_reads_texel_centres_and_blends_between_them():
    depth = np.arange(16, dtype=np.float64).reshape(4, 4) / 16.0  # row 0 = v 0
    centre = lambda ix, iy: ((ix + 0.5) / 4.0, (iy + 0.5) / 4.0)  # noqa: E731
    assert np.isclose(lo.bilinear_depth(depth, centre(1, 2)), depth[2, 1])
    mid = ((1.5 + 0.5) / 4.0, (2 + 0.5) / 4.0)  # halfway between texels (1, 2) and (2, 2)
    assert np.isclose(lo.bilinear_depth(depth, mid), (depth[2, 1] + depth[2, 2]) / 2)
    assert np.isclose(lo.bilinear_depth(depth, (0.0, 0.0)), depth[0, 0])  # clamp to edge
    assert np.isclose(lo.bilinear_depth(depth, (1.0, 1.0)), depth[3, 3])


def test_key_transmission_falls_with_the_path_inside_the_mesh():
    """AD-039 §7: a fragment `t` world units behind the map's nearest surface transmits exp(-t / scale); outside the
    map's box none (the AD's named limit)."""
    depth = np.full((8, 8), 0.25)
    depth_range = 2.0  # world units per unit of map depth
    scale = lo.THICKNESS_SCALE
    ts = np.array([lo.THICKNESS_EDGE, 0.5 * scale, scale, 4 * scale])
    sp = np.array([[0.5, 0.5, 0.25 + t / depth_range] for t in ts])
    got = lo.key_transmission(depth, sp, depth_range)
    assert np.allclose(got, np.exp(-ts / scale), atol=1e-9)
    assert lo.key_transmission(depth, [1.2, 0.5, 0.3], depth_range) == 0.0
    assert lo.key_transmission(depth, [0.5, 0.5, 1.1], depth_range) == 0.0
    # the rendered part of the map (a soft key's effective resolution): the lookup scales the UV
    half = np.full((8, 8), 1.0)
    half[:4, :4] = 0.25
    assert np.isclose(lo.key_transmission(half, [0.6, 0.6, 0.25 + scale / depth_range], depth_range, scale=0.5),
                      math.exp(-1.0))


def test_no_tissue_in_front_lets_no_light_through():
    """AD-039 §19.6 (Manu 2026-11-24, a red patch on the cheek): a fragment that is itself the nearest surface toward
    the key (no thickness: the key reached it through an opening - the socket behind a non-casting eye whose back
    polygons were deleted) gets none of it; the transmission rises over `THICKNESS_EDGE` (smoothstep) to exp(-t / s)."""
    depth = np.full((8, 8), 0.25)
    depth_range = 2.0
    edge = lo.THICKNESS_EDGE
    assert 0.0 < edge <= 0.1 * lo.THICKNESS_SCALE + 1e-12
    at = lambda t: float(lo.key_transmission(depth, [0.5, 0.5, 0.25 + t / depth_range], depth_range))  # noqa: E731
    assert at(0.0) == 0.0  # the surface itself
    assert lo.key_transmission(depth, [0.5, 0.5, 0.1], depth_range) == 0.0  # in front of the stored surface
    assert np.isclose(at(0.5 * edge), 0.5 * math.exp(-0.5 * edge / lo.THICKNESS_SCALE))  # smoothstep(0.5) = 0.5
    rising = [at(t) for t in np.linspace(0.0, edge, 11)]
    assert all(b >= a for a, b in zip(rising, rising[1:]))
    assert np.isclose(at(edge), math.exp(-edge / lo.THICKNESS_SCALE))


def test_ld_backscatter_proxy_and_transmission():
    """AD-039 §7: with the thickness the transmission replaces M1's view-rim proxy (1 - n.v)^3; both only on the side
    facing away from the key, times the backscatter, its colour, the albedo and the key's colour."""
    values = lo.frame_uniforms(_state())
    key = np.asarray(values["u_ld_light_dir"][0])
    colour = np.asarray(values["u_ld_light_color"][0])
    albedo, bcol = np.array([0.5, 0.4, 0.3]), (1.0, 0.45, 0.3)
    n = -key[None]
    v = eo.normalize(np.array([[0.3, 0.2, 1.0]]))
    nv = max(float(n[0] @ v[0]), 1e-4)  # as the shader's nv
    proxy = lo.ld_backscatter(albedo, n, v, values, 0.15, bcol)
    want = 0.15 * (1.0 - nv) ** 3 * lo.srgb_decode(bcol) * albedo * colour
    assert np.allclose(proxy[0], want)
    thick = lo.ld_backscatter(albedo, n, v, values, 0.15, bcol, transmission=np.array([0.5]))
    assert np.allclose(thick[0], 0.15 * 0.5 * lo.srgb_decode(bcol) * albedo * colour)
    assert np.allclose(lo.ld_backscatter(albedo, key[None], v, values, 0.15, bcol, np.array([1.0])), 0.0)


# -- S7: the maps' twins (AD-039 §10) ---------------------------------------------------------------------------------


def test_a_flat_normal_map_does_not_tilt_and_strength_and_green_scale_the_tilt():
    flat = np.array([128.0, 128.0, 255.0]) / 255.0
    t = lo.normal_map_tangent(flat)
    assert t[0] == 0.0 and t[1] == 0.0 and t[2] > 0.99
    tilted = np.array([200.0, 90.0, 230.0]) / 255.0
    one, half, down = (lo.normal_map_tangent(tilted, s, g) for s, g in ((1.0, False), (0.5, False), (1.0, True)))
    assert np.allclose(half[:2], one[:2] * 0.5) and half[2] == one[2]
    assert down[0] == one[0] and down[1] == -one[1]
    assert np.allclose(lo.normal_map_tangent(tilted, 0.0)[:2], 0.0)


def test_the_cotangent_frame_follows_the_uv_and_a_flat_map_keeps_the_normal():
    n = np.array([0.0, 0.0, 1.0])
    # screen x moves along world +x and u, screen y along world +y and v: tangent +x, bitangent +y
    frame = lo.cotangent_frame(n, [0.01, 0.0, 0.0], [0.0, 0.01, 0.0], [0.02, 0.0], [0.0, 0.02])
    assert np.allclose(frame[:, 0], [1.0, 0.0, 0.0]) and np.allclose(frame[:, 1], [0.0, 1.0, 0.0])
    assert np.allclose(frame[:, 2], n)
    flat = np.array([128.0, 128.0, 255.0]) / 255.0
    assert np.allclose(lo.ld_normal_mapped(n, [0.01, 0, 0], [0, 0.01, 0], [0.02, 0], [0, 0.02], flat), n)
    # a map tilted toward +u tilts the normal toward the tangent, a mirrored UV (u running against x) away from it
    texel = np.array([1.0, 128.0 / 255.0, 1.0])
    toward = lo.ld_normal_mapped(n, [0.01, 0, 0], [0, 0.01, 0], [0.02, 0], [0, 0.02], texel)
    mirrored = lo.ld_normal_mapped(n, [0.01, 0, 0], [0, 0.01, 0], [-0.02, 0], [0, 0.02], texel)
    assert toward[0] > 0.5 and mirrored[0] < -0.5 and np.isclose(np.linalg.norm(toward), 1.0)
    # a degenerate UV (no change across the pixel) keeps the normal
    assert np.allclose(lo.ld_normal_mapped(n, [0.01, 0, 0], [0, 0.01, 0], [0, 0], [0, 0], texel), n)


def test_the_roughness_map_multiplies_the_roughness():
    assert np.allclose(lo.map_roughness(0.6, [1.0, 0.5, 0.0]), [0.6, 0.3, 0.0])


def test_the_edge_of_an_opening_lets_no_light_through():
    """AD-039 §19.7 (Manu 2026-11-24: the patch dark, a red outline round it): beside an opening the bilinear depth
    blends the surface's own depth (no tissue) with the frame's (much nearer the key) and reads a small thickness; the
    4-texel rule sees the surface itself among the texels and lets nothing through. Away from the edge the frame's
    thickness holds."""
    depth = np.full((8, 8), 0.2)  # the frame, nearer the key
    depth[:, 4:] = 0.6            # through the opening: the surface itself
    depth_range, z = 2.0, 0.6
    xs = (np.arange(8) + 0.5) / 8.0
    edge = xs[3] + 0.99 * (xs[4] - xs[3])  # just before the first surface texel: mostly its own depth
    blended = lo.bilinear_depth(depth, (edge, 0.5))
    assert 0.0 < (z - blended) * depth_range < lo.THICKNESS_SCALE  # the bilinear read: thin, would glow
    assert lo.key_transmission(depth, [edge, 0.5, z], depth_range) == 0.0
    assert lo.key_transmission(depth, [xs[1], 0.5, z], depth_range) < 1e-6  # the frame: 0.8 thick
    assert lo.farthest_depth(depth, (edge, 0.5)) == 0.6



def test_a_facet_turned_toward_the_key_is_its_own_nearest_surface_rightly():
    """AD-039 §19.8 (Manu 2026-11-24: jagged black in the red on the cage): with smooth normals on a faceted cage, a
    facet whose geometric normal faces the key (`face_l` >= 0) is the map's nearest surface without being reached
    through an opening; it keeps exp(-t / s) (t = 0: all of it, times the smooth normal's max(-n.l, 0) in the shader).
    The opening rule holds from `face_l` <= -THICKNESS_FACE on, between them it fades."""
    depth = np.full((8, 8), 0.25)
    sp = [0.5, 0.5, 0.25]  # the surface itself: no tissue in front
    assert lo.key_transmission(depth, sp, 2.0, face_l=0.0) == 1.0
    assert lo.key_transmission(depth, sp, 2.0, face_l=0.3) == 1.0
    assert lo.key_transmission(depth, sp, 2.0, face_l=-lo.THICKNESS_FACE) == 0.0
    assert lo.key_transmission(depth, sp, 2.0) == 0.0  # default: a facet facing away
    assert np.isclose(lo.key_transmission(depth, sp, 2.0, face_l=-0.5 * lo.THICKNESS_FACE), 0.5)


# -- AD-039 S9 (§24): „Weicher Schatten“ - the key's penumbra from the blocker distance ---------------------------------

def _plate_map(height: float, size: int = 256) -> np.ndarray:
    """A receiver plane at map depth 0.7 with a blocker over its left half `height` (map depth units) above it."""
    depth = np.full((size, size), 0.7)
    depth[:, : size // 2] = 0.7 - height
    return depth


def _profile(depth: np.ndarray, size: float, row: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """(u, vis) along a line across the blocker's edge (at u = 0.5), receivers on the plane (slope 0)."""
    u = np.linspace(0.3, 0.7, 801)
    sp = np.stack([u, np.full_like(u, row), np.full_like(u, 0.7)], -1)
    return u, lo.soft_shadow_visibility(depth, sp, sp, size)[0]


def _penumbra_width(u, vis) -> float:
    partial = (vis > 0.02) & (vis < 0.98)
    return float(u[partial].max() - u[partial].min()) if partial.any() else 0.0


def test_the_soft_shadow_lift_grows_with_the_cube_of_sin_sigma():
    assert lo.soft_shadow_lift(0.0, 1.0, 0.003) == lo.SHADOW_WRAP_LIFT
    extra = [lo.soft_shadow_lift(size, 1.0, 0.003) - lo.SHADOW_WRAP_LIFT for size in (0.5, 1.0)]
    assert extra[1] / extra[0] == pytest.approx(8.0)
    s = ls.AREA_SIN_MAX
    assert extra[1] * 0.003 == pytest.approx(ls.SOFT_SHADOW_BAND_LIFT * s ** 3)  # world units = 0.23 R s³


def test_the_soft_shadow_taps_fill_the_unit_disc_and_the_search_is_denser_near_the_centre():
    for taps in (ls.SOFT_SHADOW_SEARCH_TAPS, ls.SOFT_SHADOW_PCF_TAPS):
        radii = np.hypot(*np.asarray(taps).T)
        assert len(taps) == ls.SOFT_SHADOW_TAPS and radii.max() <= 1.0 and len(set(taps)) == len(taps)
    assert np.median(np.hypot(*np.asarray(ls.SOFT_SHADOW_SEARCH_TAPS).T)) < np.median(
        np.hypot(*np.asarray(ls.SOFT_SHADOW_PCF_TAPS).T))


@pytest.mark.parametrize("size", [0.0, 0.45, 1.0])
def test_without_a_blocker_the_soft_shadow_is_lit(size):
    """A plane facing the key (its own depth everywhere, tilted or not): no fetch is a blocker - lit, no acne."""
    depth = np.full((128, 128), 0.7)
    u = np.random.default_rng(3).uniform(0.05, 0.95, (500, 2))
    sp = np.concatenate([u, np.full((500, 1), 0.7)], -1)
    vis, vis_wrap = lo.soft_shadow_visibility(depth, sp, sp, size)
    assert (vis == 1.0).all() and (vis_wrap == 1.0).all()
    yy, xx = np.mgrid[0:128, 0:128] / 128.0  # a tilted plane, its receiver-plane slope given
    tilted = 0.5 + 0.3 * xx
    sp = np.concatenate([u, (0.5 + 0.3 * (u[:, :1] - 0.5 / 128))], -1)
    vis, _ = lo.soft_shadow_visibility(tilted, sp, sp, size, slope=(0.3, 0.0))
    assert (vis > 0.99).mean() > 0.99


def test_the_soft_penumbra_grows_with_the_blocker_distance_and_the_key_size():
    """The point of S9 (Manu 2026-11-24): the penumbra's width is (receiver - blocker) x tan sigma - a far blocker
    softer than a near one, a larger key softer than a smaller; the core under the blocker dark, the plane beside it
    lit; a hard key (size 0) keeps today's few-texel edge whatever the distance."""
    widths = {}
    for height in (0.02, 0.2):
        for size in (0.0, 0.45, 1.0):
            u, vis = _profile(_plate_map(height), size)
            widths[height, size] = _penumbra_width(u, vis)
            assert vis[u < 0.35].max() < 0.02 or size == 1.0  # the core under the blocker (size 1: wider than this)
            assert vis[u > 0.6].min() > 0.98  # beside it: lit
    texel = 1.0 / 256
    assert widths[0.02, 0.0] <= 4 * texel and widths[0.2, 0.0] <= 4 * texel
    assert widths[0.2, 0.45] > 3 * widths[0.02, 0.45]
    assert widths[0.2, 1.0] > widths[0.2, 0.45] > widths[0.2, 0.0]
    # the inner half of the penumbra (under the blocker) matches (z - blocker) x tan sigma within the fetches' spacing
    s = 0.45 * ls.AREA_SIN_MAX
    u, vis = _profile(_plate_map(0.2), 0.45)
    inner = u[(vis > 0.02) & (u < 0.5)]
    assert inner.min() == pytest.approx(0.5 - 0.2 * s / math.sqrt(1 - s * s), abs=4 * texel)


def test_a_contact_blocker_keeps_a_sharp_edge_at_a_large_key():
    """A blocker 0.005 above the receiver (a lip on a lip, a nostril's rim): at size 1 the edge stays a few texels."""
    u, vis = _profile(_plate_map(0.005), 1.0)
    assert _penumbra_width(u, vis) <= 6 / 256
