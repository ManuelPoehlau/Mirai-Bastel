"""The diffuse models of `area_math` (2026-11-24): limits, the lit side, the separation of size and wrap."""

import math

import numpy as np
import pytest

import area_math as am

C = np.linspace(-1.0, 1.0, 2001)


@pytest.mark.parametrize("w", [0.0, 0.3])
def test_a_point_light_is_production(w):
    for f in (lambda: am.area_quad(C, 0.0, w), lambda: am.area_exact(C, 0.0, w), lambda: am.area_samples(C, 0.0, w)):
        assert np.allclose(f(), am.lambert_wrap(C, w), atol=1e-3)


@pytest.mark.parametrize("size", [0.25, 0.5, 1.0])
@pytest.mark.parametrize("w", [0.0, 0.3])
def test_the_lit_side_does_not_change_with_size(size, w):
    """The energy convention: the light colour is the illuminance at normal incidence - only the band moves."""
    s = float(am.size_to_sin(size))
    lit = C + w >= s
    for f in (am.area_quad, am.area_exact):
        assert np.allclose(f(C, s, w)[lit], am.lambert_wrap(C, w)[lit], atol=1e-9)
    # C: 16 spiral directions are not symmetric about the centre - up to ~1 % off on the lit side (a C finding)
    assert np.allclose(am.area_samples(C, s, w, 16)[lit & (C > 0.5)], am.lambert_wrap(C, w)[lit & (C > 0.5)],
                       atol=1.2e-2)


@pytest.mark.parametrize("size", [0.25, 0.5, 1.0])
def test_the_exact_sphere_formula_matches_the_dense_reference(size):
    s = float(am.size_to_sin(size))
    assert np.abs(am.area_exact(C, s) - am.area_reference(C, s, 0.0, 16384)).max() < 2e-3


@pytest.mark.parametrize("size", [0.25, 0.5, 1.0])
@pytest.mark.parametrize("w", [0.0, 0.3])
def test_the_spline_is_within_two_percent_of_the_reference(size, w):
    s = float(am.size_to_sin(size))
    assert np.abs(am.area_quad(C, s, w) - am.area_reference(C, s, w, 16384)).max() < 0.02


def test_a_larger_light_widens_the_band_even_without_wrap():
    """Manu's criterion: the size softens the terminator on a material with wrap 0."""
    past = np.cos(np.radians(100.0))  # 10 degrees past the terminator
    values = [float(am.area_quad(past, float(am.size_to_sin(s)))) for s in (0.0, 0.25, 0.5, 1.0)]
    assert values[0] == 0.0 and values[1] < values[2] < values[3]
    assert values[3] > 0.05


def test_the_spline_is_c1_and_never_below_lambert():
    s = 0.4
    y = am.area_quad(C, s)
    assert np.all(y >= am.lambert_wrap(C) - 1e-12)
    slope = np.gradient(y, C)
    assert np.max(np.abs(np.diff(slope))) < 0.01  # no kink


def test_wrap_and_size_stay_separate():
    """The wrap changes the transition's position and the lit side's shape; the size only the band's width around it."""
    s = float(am.size_to_sin(0.5))
    a = am.area_quad(C, s, 0.3)
    centre = -0.3  # the wrapped terminator
    band = np.abs(C - centre) < s
    assert np.all(a[~band] == pytest.approx(am.lambert_wrap(C, 0.3)[~band]))


def test_the_naive_wrap_by_size_changes_the_lit_side():
    s = float(am.size_to_sin(0.5))
    assert am.wrap_by_size(0.3, 0.0, s) > am.lambert_wrap(0.3) + 0.1


def test_the_sphere_gain_is_s_squared_over_three():
    n, mask = am.sphere_normals(512)
    l = am.direction(90.0, 0.0)  # a side light: the terminator runs across the visible half
    nn = n[mask]
    # all normals of the full sphere: mirror the visible half
    full = np.concatenate([nn, nn * np.array([1.0, 1.0, -1.0])])
    weights = np.concatenate([1.0 / nn[:, 2].clip(1e-3), 1.0 / nn[:, 2].clip(1e-3)])  # orthographic -> per area
    for size in (0.5, 1.0):
        a = np.average(am.shade_normals(full, l, "A", size), weights=weights)
        b = np.average(am.shade_normals(full, l, "B", size), weights=weights)
        s = float(am.size_to_sin(size))
        assert b / a - 1.0 == pytest.approx(am.mean_excess(s), rel=0.15)


def test_mapping():
    assert float(am.sigma_degrees(1.0)) == pytest.approx(40.0)
    assert float(am.size_to_sin(0.0)) == 0.0
    assert float(am.sigma_degrees(0.25)) == pytest.approx(math.degrees(math.asin(0.25 * am.S_MAX)))
