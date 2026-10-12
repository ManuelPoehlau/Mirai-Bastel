"""The signed falloff curve (handoff E5) — pure math, no GL.

x = `d / r` in [0, 1] (0 at the seeds, 1 at the radius edge), y = the weight `w`.
Fixed endpoints (0, 1) and (1, 0); four interior control points at x = 0.2 / 0.4 /
0.6 / 0.8 whose y is free in [-1, 1] (x fixed, the panel drags vertically only).

Interpolation: PCHIP (Fritsch–Carlson, the tangent rule of scipy's `PchipInterpolator`,
written out here — the lab is pure Python). Between two control points the curve is
monotone, so it never leaves the range of its two neighbours and needs no output
clamp; a negative control value stays negative.

Mind the axis: `mirai.soft_selection.CURVES` are functions of `t = 1 - d/r` (1 at the
seed). This curve is a function of `x = d/r`; `CURVES["smooth"](1 - x)` is the same
shape. Everything here is `PROVISIONAL` (presets, control x positions).
"""

from __future__ import annotations

import bisect
import math
from typing import Callable, Sequence

from mirai.soft_selection import CURVES

#: Knot x positions: the two fixed endpoints and the four editable interior points.
KNOTS_X: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
INTERIOR_X: tuple[float, ...] = KNOTS_X[1:-1]
Y_MIN, Y_MAX = -1.0, 1.0


def _smooth_of_x(x: float) -> float:
    return CURVES["smooth"](1.0 - x)


PRESET_SMOOTH = "smooth"
PRESET_HAT = "hat"
#: PROVISIONAL presets (keys `1` / `2`): interior y values at x = 0.2 / 0.4 / 0.6 / 0.8.
#: Smooth = `CURVES["smooth"]` sampled at the control points (the Artist default 2026-10-11);
#: "Mexican hat" = positive core, negative lobe around x ≈ 0.6–0.8.
PRESETS: dict[str, tuple[float, ...]] = {
    PRESET_SMOOTH: tuple(_smooth_of_x(x) for x in INTERIOR_X),
    PRESET_HAT: (0.70, 0.10, -0.35, -0.30),
}
PRESET_LABELS = {PRESET_SMOOTH: "Smooth", PRESET_HAT: "Mexican Hat"}


def _sign(v: float) -> int:
    return (v > 0.0) - (v < 0.0)


def pchip_slopes(xs: Sequence[float], ys: Sequence[float]) -> list[float]:
    """Fritsch–Carlson tangents (scipy `PchipInterpolator` rule, incl. its end condition)."""
    count = len(xs)
    h = [xs[k + 1] - xs[k] for k in range(count - 1)]
    delta = [(ys[k + 1] - ys[k]) / h[k] for k in range(count - 1)]
    m = [0.0] * count
    for k in range(1, count - 1):
        d0, d1 = delta[k - 1], delta[k]
        if d0 == 0.0 or d1 == 0.0 or _sign(d0) != _sign(d1):
            m[k] = 0.0  # local extremum or flat piece: horizontal tangent
        else:
            w1 = 2.0 * h[k] + h[k - 1]
            w2 = h[k] + 2.0 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d0 + w2 / d1)  # weighted harmonic mean
    m[0] = _end_slope(h[0], h[1], delta[0], delta[1])
    m[-1] = _end_slope(h[-1], h[-2], delta[-1], delta[-2])
    return m


def _end_slope(h0: float, h1: float, d0: float, d1: float) -> float:
    m = ((2.0 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
    if _sign(m) != _sign(d0):
        return 0.0
    if _sign(d0) != _sign(d1) and abs(m) > abs(3.0 * d0):
        return 3.0 * d0
    return m


class SignedCurve:
    """Immutable: an edit returns a new curve (tangents are computed once per instance)."""

    __slots__ = ("interior", "ys", "slopes", "preset")

    def __init__(self, interior: Sequence[float], preset: str | None = None) -> None:
        values = tuple(float(v) for v in interior)
        if len(values) != len(INTERIOR_X):
            raise ValueError(f"expected {len(INTERIOR_X)} interior values, got {len(values)}")
        if not all(math.isfinite(v) and Y_MIN <= v <= Y_MAX for v in values):
            raise ValueError(f"interior values must be finite and in [-1, 1], got {values!r}")
        self.interior = values
        self.ys: tuple[float, ...] = (1.0,) + values + (0.0,)
        self.slopes = pchip_slopes(KNOTS_X, self.ys)
        #: The preset this curve is (None once a point was dragged).
        self.preset = preset

    @classmethod
    def from_preset(cls, name: str) -> "SignedCurve":
        return cls(PRESETS[name], preset=name)

    def with_point(self, index: int, y: float) -> "SignedCurve":
        """Interior point `index` (0..3) moved to `y` (clamped to [-1, 1])."""
        values = list(self.interior)
        values[index] = max(Y_MIN, min(Y_MAX, float(y)))
        return SignedCurve(values)

    def __eq__(self, other) -> bool:
        return isinstance(other, SignedCurve) and self.interior == other.interior

    def __hash__(self) -> int:
        return hash(self.interior)

    def __repr__(self) -> str:
        return f"SignedCurve({self.interior!r}, preset={self.preset!r})"

    @property
    def label(self) -> str:
        return PRESET_LABELS.get(self.preset, "eigene Kurve") if self.preset else "eigene Kurve"

    @property
    def has_negative(self) -> bool:
        return any(v < 0.0 for v in self.interior)

    def __call__(self, x: float) -> float:
        """w at x = d/r. Endpoints are exact: f(0) = 1, f(1) = 0. x outside [0, 1] is clamped."""
        if x <= 0.0:
            return 1.0
        if x >= 1.0:
            return 0.0
        k = min(bisect.bisect_right(KNOTS_X, x) - 1, len(KNOTS_X) - 2)
        x0, x1 = KNOTS_X[k], KNOTS_X[k + 1]
        y0, y1 = self.ys[k], self.ys[k + 1]
        h = x1 - x0
        s = (x - x0) / h
        s2 = s * s
        s3 = s2 * s
        h00 = 2.0 * s3 - 3.0 * s2 + 1.0
        h10 = s3 - 2.0 * s2 + s
        h01 = -2.0 * s3 + 3.0 * s2
        h11 = s3 - s2
        return h00 * y0 + h10 * h * self.slopes[k] + h01 * y1 + h11 * h * self.slopes[k + 1]

    def as_function(self) -> Callable[[float], float]:
        return self.__call__


DEFAULT_CURVE = SignedCurve.from_preset(PRESET_SMOOTH)
