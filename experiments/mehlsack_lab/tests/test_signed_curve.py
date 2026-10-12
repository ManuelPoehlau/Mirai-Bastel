"""§7.3 Signed curve: endpoints exact, PCHIP stays within neighbouring control points, Smooth
preset vs `CURVES["smooth"]`, negative values survive."""

from __future__ import annotations

import random

import pytest

from mehlsack_lab.signed_curve import (
    DEFAULT_CURVE,
    INTERIOR_X,
    KNOTS_X,
    PRESET_HAT,
    PRESET_SMOOTH,
    PRESETS,
    SignedCurve,
)
from mirai.soft_selection import CURVES

#: Stated tolerance of the Smooth preset against `CURVES["smooth"]` (max abs difference on a
#: 10 001-sample grid; measured 0.00975 — four control points cannot carry smoothstep exactly,
#: and PCHIP's end slopes are -0.16 where smoothstep's are 0).
SMOOTH_TOLERANCE = 0.01

GRID = [i / 10000 for i in range(10001)]


def _random_curves(count=200, seed=7):
    rng = random.Random(seed)
    yield SignedCurve.from_preset(PRESET_SMOOTH)
    yield SignedCurve.from_preset(PRESET_HAT)
    yield SignedCurve((-1.0, 1.0, -1.0, 1.0))
    yield SignedCurve((1.0, 1.0, 1.0, 1.0))
    yield SignedCurve((0.0, 0.0, 0.0, 0.0))
    for _ in range(count):
        yield SignedCurve([rng.uniform(-1.0, 1.0) for _ in INTERIOR_X])


def test_endpoints_exact():
    for curve in _random_curves(50):
        assert curve(0.0) == 1.0 and curve(1.0) == 0.0
        assert curve(-0.5) == 1.0 and curve(1.5) == 0.0


def test_passes_through_control_points():
    for curve in _random_curves(50):
        for x, y in zip(KNOTS_X, curve.ys):
            assert curve(x) == pytest.approx(y, abs=1e-12)


def test_never_leaves_the_range_of_neighbouring_control_points():
    for curve in _random_curves():
        for k in range(len(KNOTS_X) - 1):
            lo, hi = sorted((curve.ys[k], curve.ys[k + 1]))
            x0, x1 = KNOTS_X[k], KNOTS_X[k + 1]
            for i in range(1, 200):
                y = curve(x0 + (x1 - x0) * i / 200)
                assert lo - 1e-12 <= y <= hi + 1e-12, (curve, k, i, y)


def test_monotone_between_control_points():
    for curve in _random_curves(100):
        for k in range(len(KNOTS_X) - 1):
            x0, x1 = KNOTS_X[k], KNOTS_X[k + 1]
            samples = [curve(x0 + (x1 - x0) * i / 100) for i in range(101)]
            diffs = [b - a for a, b in zip(samples, samples[1:])]
            assert all(d >= -1e-12 for d in diffs) or all(d <= 1e-12 for d in diffs)


def test_smooth_preset_matches_soft_selection_smooth():
    assert PRESETS[PRESET_SMOOTH] == tuple(CURVES["smooth"](1.0 - x) for x in INTERIOR_X)
    error = max(abs(DEFAULT_CURVE(x) - CURVES["smooth"](1.0 - x)) for x in GRID)
    assert error <= SMOOTH_TOLERANCE
    assert DEFAULT_CURVE.preset == PRESET_SMOOTH


def test_negative_values_survive():
    hat = SignedCurve.from_preset(PRESET_HAT)
    assert hat.has_negative
    assert min(hat(x) for x in GRID) == pytest.approx(min(PRESETS[PRESET_HAT]))
    assert any(hat(x) < 0.0 for x in (0.6, 0.7, 0.8))
    deep = SignedCurve((0.5, -1.0, -1.0, -0.5))
    assert deep(0.5) == -1.0 and deep(0.3) < 0.0


def test_point_edit_is_vertical_and_clamped():
    curve = DEFAULT_CURVE.with_point(2, -3.0)
    assert curve.interior[2] == -1.0 and curve.preset is None
    assert curve.interior[:2] == DEFAULT_CURVE.interior[:2]
    assert DEFAULT_CURVE.with_point(0, 7.0).interior[0] == 1.0
    assert DEFAULT_CURVE.interior == PRESETS[PRESET_SMOOTH]  # immutable


@pytest.mark.parametrize("bad", [(0.1, 0.2, 0.3), (0.0, 0.0, 0.0, 1.5), (0.0, float("nan"), 0.0, 0.0)])
def test_bad_control_values_refused(bad):
    with pytest.raises(ValueError):
        SignedCurve(bad)
