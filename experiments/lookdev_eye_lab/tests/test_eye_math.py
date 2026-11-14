"""The NumPy reference of the shading terms (headless). The shader side is compared to it in `test_gl_parity.py`."""

from __future__ import annotations

import math

import numpy as np
import pytest

from lookdev_gpu_probe import cube_math as cm
from lookdev_eye_lab import eye_math as em
from lookdev_eye_lab import studio_env as se


def test_erf_approximation_is_within_its_published_bound():
    x = np.linspace(-4.0, 4.0, 2001)
    assert max(abs(em.erf(v) - math.erf(v)) for v in x) < 1.6e-7


def test_srgb_round_trip_and_known_values():
    c = np.linspace(0.0, 1.0, 1001)
    assert np.max(np.abs(em.srgb_encode(em.srgb_decode(c)) - c)) < 1e-12
    assert em.srgb_decode(1.0) == pytest.approx(1.0)
    assert em.srgb_decode(0.5) == pytest.approx(0.21404, abs=1e-5)


def test_tonemaps_and_display():
    assert em.tonemap(np.array([0.5, 2.0]), 0).tolist() == [0.5, 1.0]
    assert em.tonemap(np.array([1.0, 3.0]), 1).tolist() == [0.5, 0.75]
    assert em.display(np.array([1.0]), 2.0, 0)[0] == pytest.approx(1.0)


def test_cornea_f0_from_its_ior():
    assert em.f0_from_ior(1.376) == pytest.approx(0.02504, abs=1e-5)  # audit §5.4: ~0.025


@pytest.mark.parametrize("alpha", [0.05, 0.2, 0.5, 1.0])
def test_ggx_is_a_normalised_distribution(alpha):
    """Integral of D(h) (n.h) over the hemisphere = 1."""
    t = np.linspace(0.0, math.pi / 2, 200001)
    integrand = em.ggx_d(np.cos(t), alpha) * np.cos(t) * np.sin(t) * 2.0 * math.pi
    assert np.trapezoid(integrand, t) == pytest.approx(1.0, abs=2e-3)


def test_smith_visibility_and_schlick_limits():
    assert em.smith_vis(1.0, 1.0, 1e-6) == pytest.approx(0.25, rel=1e-4)  # G = 1 -> 1 / (4 N.L N.V)
    assert em.schlick(0.04, 1.0) == pytest.approx(0.04)
    assert em.schlick(0.04, 0.0) == pytest.approx(1.0)


def test_direct_specular_is_zero_behind_the_light_and_peaks_at_the_mirror_direction():
    n = np.array([0.0, 0.0, 1.0])
    l = np.array([0.6, 0.0, 0.8])
    mirror = np.array([-0.6, 0.0, 0.8])
    off = np.array([0.0, 0.6, 0.8])
    assert np.all(em.direct_specular(n, mirror, -l, 0.3, (0.04,) * 3) == 0.0)
    assert em.direct_specular(n, mirror, l, 0.3, (0.04,) * 3)[0] > em.direct_specular(n, off, l, 0.3, (0.04,) * 3)[0]


def test_env_brdf_gives_f0_head_on_and_grows_toward_grazing():
    f0 = 0.025
    head_on = em.env_brdf_approx(np.array([f0]), 0.05, 1.0)[0]
    grazing = em.env_brdf_approx(np.array([f0]), 0.05, 0.05)[0]
    assert head_on == pytest.approx(f0, abs=0.01)
    assert grazing > 10 * head_on  # Fresnel: weak facing the camera, strong at the cornea's edge (audit §5.5.2)


@pytest.mark.parametrize("mode", [0, 1])
def test_lod_mappings_invert(mode):
    r = np.linspace(0.0, 1.0, 11)
    assert np.allclose(em.lod_to_roughness(em.roughness_to_lod(r, mode, 6.0), mode, 6.0), r)
    assert em.roughness_to_lod(1.0, mode, 6.0) == 6.0  # roughness 1 -> the 2^2 level


def test_box_profile_integrates_to_its_width():
    x = np.linspace(-2.0, 2.0, 40001)
    assert np.trapezoid(em.box_profile(x, 0.3, 0.1), x) == pytest.approx(0.6, rel=1e-4)


def test_td_softbox_follows_the_prefiltered_cube():
    """T-D's analytic softbox against the GGX prefilter of the same studio (relative RMS over the lit texels). The
    bound is the fit's own result (eye_math docstring); a regression in either side breaks it."""
    env = se.DEFAULT_ENV
    d = cm.texel_directions(16)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    for r, bound in ((0.1, 0.12), (0.3, 0.15), (0.6, 0.20)):
        cube = se.prefilter_level(env, 16, r, 512)
        lit = cube.mean(axis=-1) > 0.3
        approx = se.td_radiance(d, r, env)
        rel = np.sqrt(np.mean((approx - cube)[lit] ** 2)) / np.mean(cube[lit])
        assert rel < bound, (r, rel)


def test_cornea_hit_and_its_cap():
    hit, p, n = em.cornea_hit(np.array([[0.0, 0.0, 5.0], [0.0, 0.0, -5.0]]),
                              np.array([[0.0, 0.0, -1.0], [0.0, 0.0, 1.0]]), (0.0, 0.0, 0.4), 0.65, 0.87,
                              np.array([10.0, 10.0]))
    assert hit.tolist() == [True, False]  # from behind the near hit is below the limbus plane
    assert p[0, 2] == pytest.approx(1.05) and n[0].tolist() == pytest.approx([0.0, 0.0, 1.0])


def test_coverage_framing():
    d = em.distance_for_coverage(0.5, 1.0, 50.0, 1024, 768)
    assert em.sphere_coverage(d, 1.0, 50.0, 1024, 768) == pytest.approx(0.5, abs=0.01)
    assert em.distance_for_coverage(0.5, 1.0, 50.0, 1920, 1080) < d  # wider frame: closer for the same share
