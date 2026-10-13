"""Signed Bézier curve (Slice 2a E11–E13): exact Smooth preset, end slopes, the range and
single-value guarantees under seeded random drags, knot clamps, aligned vs broken handles,
double-click reset, Mexican Hat."""

from __future__ import annotations

import math
import random

import pytest

from mehlsack_lab.curve_panel import Element, move_element, pickable_elements
from mehlsack_lab.signed_curve import (
    DEFAULT_CURVE,
    FIRST,
    HANDLE_IN,
    HANDLE_OUT,
    HAT_KNOTS_Y,
    INTERIOR,
    KNOT_COUNT,
    KNOT_MIN_GAP,
    LAST,
    PRESET_HAT,
    PRESET_SMOOTH,
    SignedCurve,
    split_bezier,
)
from mirai.soft_selection import CURVES

#: Required by the handoff (§5): Smooth vs 3t² − 2t³ at >= 1000 samples within 1e-9.
SMOOTH_TOLERANCE = 1e-9
#: The convex hull keeps the curve in [-1, 1] exactly in real arithmetic; the float Bernstein
#: sum may round past ±1 by a few ulps (fuzz below: at most 4.4e-16). No output clamp (E11).
ROUNDING = 1e-12
GRID = [i / 10000 for i in range(10001)]
HAT = SignedCurve.from_preset(PRESET_HAT)


def smoothstep_of_x(x: float) -> float:
    t = 1.0 - x
    return 3.0 * t * t - 2.0 * t * t * t


def assert_guarantees(curve: SignedCurve) -> None:
    """Control points in [-1, 1]; control x non-decreasing per segment; samples in range and
    x(t) monotone (single-valued); endpoints exact."""
    for x, y in curve.control_points():
        assert -1.0 <= y <= 1.0
    for k in range(KNOT_COUNT - 1):
        p0, p1, p2, p3 = curve.segment(k)
        assert p0[0] < p3[0]
        assert p0[0] <= p1[0] <= p2[0] <= p3[0]
    points = curve.sample_points(40)
    assert all(-1.0 - ROUNDING <= y <= 1.0 + ROUNDING for _x, y in points)
    assert all(b[0] >= a[0] for a, b in zip(points, points[1:]))
    assert curve(0.0) == 1.0 and curve(1.0) == 0.0


# -- Smooth -------------------------------------------------------------------------------------


def test_smooth_preset_is_exact_smoothstep():
    errors = [abs(DEFAULT_CURVE(x) - smoothstep_of_x(x)) for x in GRID]
    assert max(errors) <= SMOOTH_TOLERANCE
    assert max(abs(DEFAULT_CURVE(x) - CURVES["smooth"](1.0 - x)) for x in GRID) <= SMOOTH_TOLERANCE
    assert DEFAULT_CURVE.preset == PRESET_SMOOTH and DEFAULT_CURVE.label == "Smooth"


def test_smooth_preset_has_four_interior_knots_on_the_curve():
    xs = [k[0] for k in DEFAULT_CURVE.knots]
    assert xs == pytest.approx([0.0, 0.2, 0.4, 0.6, 0.8, 1.0], abs=1e-15)
    for x, y in DEFAULT_CURVE.knots:
        assert y == pytest.approx(smoothstep_of_x(x), abs=1e-15)
    assert all(DEFAULT_CURVE.aligned)


def test_smooth_end_slopes_are_zero():
    assert DEFAULT_CURVE.slope(0.0) == 0.0
    assert DEFAULT_CURVE.slope(1.0) == 0.0
    # and the interior slope matches smoothstep's derivative -6 t (1 - t)
    for x in (0.1, 0.3, 0.5, 0.75):
        assert DEFAULT_CURVE.slope(x) == pytest.approx(-6.0 * x * (1.0 - x), abs=1e-9)


def test_de_casteljau_split_keeps_the_curve():
    points = ((0.0, 1.0), (0.3, 0.9), (0.5, -0.4), (1.0, 0.0))
    left, right = split_bezier(points, 0.37)
    assert left[3] == right[0] and left[0] == points[0] and right[3] == points[3]


# -- Mexican Hat ---------------------------------------------------------------------------------


def test_hat_preset():
    assert [k[1] for k in HAT.knots[1:-1]] == list(HAT_KNOTS_Y)
    assert [k[0] for k in HAT.knots] == [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    assert HAT.has_negative and not DEFAULT_CURVE.has_negative
    # horizontal end handles, aligned automatic handles (collinear) inside
    assert HAT.handles_out[FIRST][1] == 1.0 and HAT.handles_in[LAST][1] == 0.0
    assert HAT.slope(0.0) == 0.0 and HAT.slope(1.0) == 0.0
    for i in INTERIOR:
        assert _collinear(HAT, i)
    # automatic handles never overshoot their knots: the curve stays within the knot values
    lo = min(k[1] for k in HAT.knots)
    assert min(HAT(x) for x in GRID) == pytest.approx(lo, abs=1e-12)
    assert any(HAT(x) < 0.0 for x in (0.6, 0.7, 0.8))


# -- edits ----------------------------------------------------------------------------------------


def _collinear(curve: SignedCurve, i: int, tol: float = 1e-9) -> bool:
    (kx, ky), (ax, ay), (bx, by) = curve.knots[i], curve.handles_in[i], curve.handles_out[i]
    return abs((ax - kx) * (by - ky) - (ay - ky) * (bx - kx)) <= tol


def test_knot_moves_in_x_and_y_and_is_clamped_between_neighbours():
    c = DEFAULT_CURVE.with_knot(2, 0.47, -0.3)
    assert c.knots[2] == (0.47, -0.3) and c.preset is None
    left, right = c.knots[1][0], c.knots[3][0]
    assert c.with_knot(2, -5.0, 0.0).knots[2][0] == pytest.approx(left + KNOT_MIN_GAP)
    assert c.with_knot(2, 5.0, 0.0).knots[2][0] == pytest.approx(right - KNOT_MIN_GAP)
    assert c.with_knot(2, 0.5, 7.0).knots[2][1] == 1.0
    assert c.with_knot(2, 0.5, -7.0).knots[2][1] == -1.0
    with pytest.raises(ValueError):
        DEFAULT_CURVE.with_knot(0, 0.1, 0.5)  # endpoints never move
    with pytest.raises(ValueError):
        DEFAULT_CURVE.with_knot(5, 0.9, 0.5)
    assert DEFAULT_CURVE.knots[2][0] == pytest.approx(0.4)  # immutable
    for curve in (c, c.with_knot(2, -5.0, 0.0), c.with_knot(2, 5.0, 1.0)):
        assert_guarantees(curve)


def test_knot_move_carries_its_handles():
    before = HAT
    after = HAT.with_knot(2, 0.45, 0.05)
    dx, dy = 0.05, -0.05
    for side in ("handles_in", "handles_out"):
        b, a = getattr(before, side)[2], getattr(after, side)[2]
        assert a == pytest.approx((b[0] + dx, b[1] + dy), abs=1e-12)


def test_aligned_handles_stay_collinear_and_keep_the_other_length():
    i = 2
    c = DEFAULT_CURVE
    other_len = math.dist(c.knots[i], c.handles_in[i])
    d = c.with_handle(i, HANDLE_OUT, c.knots[i][0] + 0.05, c.knots[i][1] + 0.1)
    assert d.aligned[i] and _collinear(d, i)
    assert math.dist(d.knots[i], d.handles_in[i]) == pytest.approx(other_len)
    # opposite sides of the knot
    assert d.handles_in[i][0] <= d.knots[i][0] <= d.handles_out[i][0]


def test_alt_drag_breaks_alignment_and_moves_one_handle_only():
    i = 3
    c = DEFAULT_CURVE
    d = c.with_handle(i, HANDLE_IN, c.knots[i][0] - 0.05, 0.9, break_alignment=True)
    assert not d.aligned[i]
    assert d.handles_out[i] == c.handles_out[i]
    assert d.handles_in[i] == (pytest.approx(c.knots[i][0] - 0.05), 0.9)
    assert not _collinear(d, i)
    # a broken knot stays broken for plain drags: the other handle no longer follows
    e = d.with_handle(i, HANDLE_OUT, c.knots[i][0] + 0.05, -0.2)
    assert e.handles_in[i] == d.handles_in[i] and not e.aligned[i]
    assert_guarantees(e)


def test_double_click_reset_restores_aligned_automatic_handles():
    i = 3
    broken = HAT.with_handle(i, HANDLE_IN, HAT.knots[i][0] - 0.01, 0.95, break_alignment=True)
    reset = broken.with_auto_handles(i)
    assert reset.aligned[i] and _collinear(reset, i)
    assert reset.handles_in[i] == pytest.approx(HAT.handles_in[i])
    assert reset.handles_out[i] == pytest.approx(HAT.handles_out[i])
    # automatic reach = 1/3 of the adjacent segment in x
    h = HAT.knots[i + 1][0] - HAT.knots[i][0]
    assert reset.handles_out[i][0] - reset.knots[i][0] == pytest.approx(h / 3.0)
    # end knots: a horizontal handle
    tilted = HAT.with_handle(FIRST, HANDLE_OUT, 0.1, 0.2)
    assert tilted.slope(0.0) != 0.0
    assert tilted.with_auto_handles(FIRST).slope(0.0) == 0.0


def test_handle_drag_is_clamped_to_its_box():
    c = DEFAULT_CURVE
    i = 2
    d = c.with_handle(i, HANDLE_OUT, 5.0, 9.0, break_alignment=True)
    assert d.handles_out[i] == (c.handles_in[i + 1][0], 1.0)  # not past the next in handle
    d = c.with_handle(i, HANDLE_OUT, -5.0, -9.0, break_alignment=True)
    assert d.handles_out[i] == (c.knots[i][0], -1.0)  # not behind its knot
    d = c.with_handle(LAST, HANDLE_IN, -5.0, 0.5)
    assert d.handles_in[LAST][0] == c.handles_out[LAST - 1][0]
    with pytest.raises(ValueError):
        c.with_handle(FIRST, HANDLE_IN, 0.0, 0.0)
    with pytest.raises(ValueError):
        c.with_handle(LAST, HANDLE_OUT, 1.0, 0.0)


def test_curve_stays_in_range_and_single_valued_under_random_drags():
    """Seeded fuzz: 2000 random drags of random elements to random (also far outside) points,
    with and without Alt, plus double clicks; after every step the guarantees hold."""
    rng = random.Random(20261013)
    for start in (DEFAULT_CURVE, HAT):
        curve = start
        for step in range(1000):
            elements = pickable_elements(curve)
            element = rng.choice(elements)
            if rng.random() < 0.05:
                curve = curve.with_auto_handles(element.index)
            else:
                x, y = rng.uniform(-0.5, 1.5), rng.uniform(-2.0, 2.0)
                curve = move_element(curve, element, x, y, break_alignment=rng.random() < 0.3)
            assert_guarantees(curve)
            if step % 50 == 0:
                values = [curve(x) for x in GRID[::10]]
                assert all(-1.0 - ROUNDING <= v <= 1.0 + ROUNDING for v in values)


def test_evaluation_inverts_x_exactly():
    """At any t, the solved curve value equals y(t) of the segment (x(t) is inverted, not
    approximated)."""
    rng = random.Random(3)
    curve = HAT.with_handle(2, HANDLE_OUT, 0.55, -0.9, break_alignment=True).with_knot(3, 0.63, -0.8)
    for _ in range(500):
        k = rng.randrange(KNOT_COUNT - 1)
        t = rng.random()
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = curve.segment(k)
        mt = 1.0 - t
        x = mt ** 3 * x0 + 3 * mt * mt * t * x1 + 3 * mt * t * t * x2 + t ** 3 * x3
        y = mt ** 3 * y0 + 3 * mt * mt * t * y1 + 3 * mt * t * t * y2 + t ** 3 * y3
        assert curve(x) == pytest.approx(y, abs=1e-9)


def test_invalid_curves_refused():
    good = DEFAULT_CURVE
    with pytest.raises(ValueError):  # handle above 1
        SignedCurve(good.knots, good.handles_in, ((0.05, 1.2),) + good.handles_out[1:])
    with pytest.raises(ValueError):  # x not monotone inside a segment
        SignedCurve(good.knots, good.handles_in, ((0.5, 1.0),) + good.handles_out[1:])
    with pytest.raises(ValueError):  # endpoint moved
        SignedCurve(((0.0, 0.9),) + good.knots[1:], good.handles_in, good.handles_out)
    with pytest.raises(ValueError):
        SignedCurve.from_knots((0.1, 0.2, 0.3, 1.5))
    assert Element("knot", 1) in pickable_elements(good)


def test_knots_at_minus_one_give_weights_the_ops_accept():
    """Regression (found in Slice 2b): the Bernstein sum rounded past -1 (w = -1.0000000000000002)
    and the signed ops refused the weight. The evaluation now rounds back to [-1, 1]."""
    deep = SignedCurve.from_knots((0.3, -1.0, -1.0, -0.5))
    values = [deep(x) for x in GRID]
    assert min(values) == -1.0 and all(-1.0 <= v <= 1.0 for v in values)
    rng = random.Random(11)
    curve = deep
    for _ in range(300):
        element = rng.choice(pickable_elements(curve))
        curve = move_element(curve, element, rng.uniform(-0.5, 1.5), rng.choice([-1.0, 1.0, -3.0, 3.0]))
        assert all(-1.0 <= curve(x) <= 1.0 for x in GRID[::25])
