"""The signed falloff curve (handoff E5; Slice 2a E11–E13: Bézier handles) — pure math, no GL.

x = `d / r` in [0, 1] (0 at the seeds, 1 at the radius edge), y = the weight `w`.

Shape: a piecewise cubic Bézier through six knots. The endpoints (0, 1) and (1, 0) never
move; each has one handle (its end slope). The four interior knots move in x (strictly
between their neighbours, at least `KNOT_MIN_GAP` apart) and in y ∈ [-1, 1]; each has an
in and an out handle. Segment `k` has the control points
`P0 = knot k, P1 = out handle of k, P2 = in handle of k + 1, P3 = knot k + 1`.

Guarantees, kept by construction (every edit clamps, `_validate()` checks):

- every control point has y ∈ [-1, 1] — a Bézier stays in the convex hull of its control
  points, so the curve stays in [-1, 1] without an output clamp (in floating point the
  Bernstein sum may round past ±1 by a few ulps; the seeded fuzz test measured ≤ 4.4e-16);
- within each segment the control x values are non-decreasing
  (`knot.x ≤ out.x ≤ next in.x ≤ next knot.x`) — then x'(t) ≥ 0, and since the knots differ
  in x it is zero only at isolated t: x(t) is strictly increasing, the curve is a function
  of x.

Evaluation solves x(t) = x per segment with a safeguarded Newton iteration (bisection
bracket; no lookup table), then evaluates y(t).

Handle edits keep the guarantees by clamping or by shrinking a handle toward its knot
(scaling keeps its direction, so aligned handles stay collinear):

- dragging a handle clamps the cursor position to the handle's allowed box (x between its
  knot and the other handle of the same segment, y in [-1, 1]);
- *aligned* knots (default): the opposite handle follows on the other side, collinear, with
  its old length, shrunk toward the knot if it would leave its box;
- `with_handle(..., break_alignment=True)` (Alt+drag) moves one handle only and marks the
  knot as a corner;
- a knot move carries its handles along; a handle leaving [-1, 1] shrinks toward the knot,
  and a segment whose two handles now overlap in x shrinks both proportionally (the
  F-curve rule of common animation editors);
- `with_auto_handles(i)` (double click) restores aligned automatic handles: x reach 1/3 of
  the adjacent segment, slope by the Fritsch–Carlson rule (0 at a local extremum, weighted
  harmonic mean otherwise) — with x linear in t that is exactly the PCHIP Hermite segment
  of Slice 1, so automatic handles never overshoot their knots; end knots get a horizontal
  handle.

Presets (`PROVISIONAL`, keys `1` / `2`, E13):

- `smooth`: **exactly** `CURVES["smooth"]` on the lab's axis. The single segment
  (0, 1) → (1, 0) with handles (1/3, 1) and (2/3, 0) has x(t) = t and y(t) = smooth(1 - x);
  de Casteljau splits at x = 0.2 / 0.4 / 0.6 / 0.8 give the four knots without changing the
  curve (Slice 1 observation B2 — end slope -0.16 — is gone; end slopes are 0).
- `hat` ("Mexican Hat"): the Slice 1 knot values 0.70 / 0.10 / -0.35 / -0.30 at the default x
  positions with aligned automatic handles and horizontal end handles.

Mind the axis: `mirai.soft_selection.CURVES` are functions of `t = 1 - d/r` (1 at the
seed). This curve is a function of `x = d/r`.
"""

from __future__ import annotations

import bisect
import math
from typing import Callable, Optional, Sequence

Point = tuple[float, float]

Y_MIN, Y_MAX = -1.0, 1.0
KNOT_COUNT = 6
#: Default knot x positions (Slice 1's fixed control points).
DEFAULT_KNOTS_X: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
INTERIOR = (1, 2, 3, 4)
FIRST, LAST = 0, KNOT_COUNT - 1
#: PROVISIONAL smallest x distance between two knots (keeps every segment non-degenerate).
KNOT_MIN_GAP = 0.02

HANDLE_IN = "in"
HANDLE_OUT = "out"

#: Newton/bisection stop: bracket width in t.
_T_TOLERANCE = 1e-15
_MAX_ITERATIONS = 64


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _bezier(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    mt = 1.0 - t
    return mt * mt * mt * p0 + 3.0 * mt * mt * t * p1 + 3.0 * mt * t * t * p2 + t * t * t * p3


def _bezier_d(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    mt = 1.0 - t
    return 3.0 * (mt * mt * (p1 - p0) + 2.0 * mt * t * (p2 - p1) + t * t * (p3 - p2))


def split_bezier(points: Sequence[Point], t: float) -> tuple[tuple[Point, ...], tuple[Point, ...]]:
    """de Casteljau: the cubic `points` split at `t` into two cubics (left, right)."""
    p0, p1, p2, p3 = points

    def lerp(a: Point, b: Point) -> Point:
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    a, b, c = lerp(p0, p1), lerp(p1, p2), lerp(p2, p3)
    d, e = lerp(a, b), lerp(b, c)
    f = lerp(d, e)
    return (p0, a, d, f), (f, e, c, p3)


def _fit(knot: Point, handle: Point, xmin: float, xmax: float) -> Point:
    """`handle` shrunk toward `knot` (direction kept) until it lies in
    [xmin, xmax] × [Y_MIN, Y_MAX]. `knot` itself must lie in that box."""
    kx, ky = knot
    dx, dy = handle[0] - kx, handle[1] - ky
    s = 1.0
    for d, k, lo, hi in ((dx, kx, xmin, xmax), (dy, ky, Y_MIN, Y_MAX)):
        if d > 0.0 and k + d > hi:
            s = min(s, (hi - k) / d)
        elif d < 0.0 and k + d < lo:
            s = min(s, (lo - k) / d)
    s = max(0.0, s)
    # Rounding of `k + s * d` must not leave the box by an ulp.
    return (_clamp(kx + s * dx, xmin, xmax), _clamp(ky + s * dy, Y_MIN, Y_MAX))


def _auto_slope(knots: Sequence[Point], i: int) -> float:
    """Fritsch–Carlson tangent at interior knot `i` (0 at a local extremum or a flat piece)."""
    (x0, y0), (x1, y1), (x2, y2) = knots[i - 1], knots[i], knots[i + 1]
    h0, h1 = x1 - x0, x2 - x1
    d0, d1 = (y1 - y0) / h0, (y2 - y1) / h1
    if d0 == 0.0 or d1 == 0.0 or (d0 > 0.0) != (d1 > 0.0):
        return 0.0
    w1, w2 = 2.0 * h1 + h0, h1 + 2.0 * h0
    return (w1 + w2) / (w1 / d0 + w2 / d1)


def _auto_handles(knots: Sequence[Point], i: int) -> tuple[Optional[Point], Optional[Point]]:
    """Automatic (in, out) handles of knot `i` before any fitting."""
    kx, ky = knots[i]
    slope = 0.0 if i in (FIRST, LAST) else _auto_slope(knots, i)
    handle_in = handle_out = None
    if i > FIRST:
        reach = (kx - knots[i - 1][0]) / 3.0
        handle_in = (kx - reach, ky - slope * reach)
    if i < LAST:
        reach = (knots[i + 1][0] - kx) / 3.0
        handle_out = (kx + reach, ky + slope * reach)
    return handle_in, handle_out


class SignedCurve:
    """Immutable: every edit returns a new curve (see module docstring)."""

    __slots__ = ("knots", "handles_in", "handles_out", "aligned", "preset", "_xs", "_segments")

    def __init__(
        self,
        knots: Sequence[Point],
        handles_in: Sequence[Optional[Point]],
        handles_out: Sequence[Optional[Point]],
        aligned: Optional[Sequence[bool]] = None,
        preset: Optional[str] = None,
    ) -> None:
        self.knots: tuple[Point, ...] = tuple((float(x), float(y)) for x, y in knots)
        self.handles_in: tuple[Optional[Point], ...] = tuple(
            None if h is None else (float(h[0]), float(h[1])) for h in handles_in)
        self.handles_out: tuple[Optional[Point], ...] = tuple(
            None if h is None else (float(h[0]), float(h[1])) for h in handles_out)
        self.aligned: tuple[bool, ...] = (
            (True,) * KNOT_COUNT if aligned is None else tuple(bool(a) for a in aligned))
        #: The preset this curve is (None once anything was edited).
        self.preset = preset
        self._validate()
        self._xs = tuple(k[0] for k in self.knots)
        self._segments = tuple(
            (self.knots[k][0], self.handles_out[k][0], self.handles_in[k + 1][0], self.knots[k + 1][0],
             self.knots[k][1], self.handles_out[k][1], self.handles_in[k + 1][1], self.knots[k + 1][1])
            for k in range(KNOT_COUNT - 1)
        )

    def _validate(self) -> None:
        knots, hin, hout = self.knots, self.handles_in, self.handles_out
        if not (len(knots) == len(hin) == len(hout) == len(self.aligned) == KNOT_COUNT):
            raise ValueError(f"expected {KNOT_COUNT} knots with handles")
        if knots[FIRST] != (0.0, 1.0) or knots[LAST] != (1.0, 0.0):
            raise ValueError(f"endpoints must be (0, 1) and (1, 0), got {knots[FIRST]}, {knots[LAST]}")
        if hin[FIRST] is not None or hout[LAST] is not None:
            raise ValueError("the endpoints have one handle each (out at x = 0, in at x = 1)")
        if any(h is None for h in hin[1:]) or any(h is None for h in hout[:-1]):
            raise ValueError("missing handle")
        points = list(knots) + [h for h in hin + hout if h is not None]
        if not all(math.isfinite(x) and math.isfinite(y) and Y_MIN <= y <= Y_MAX for x, y in points):
            raise ValueError(f"control points must be finite with y in [-1, 1]: {points!r}")
        for k in range(KNOT_COUNT - 1):
            x0, x1, x2, x3 = knots[k][0], hout[k][0], hin[k + 1][0], knots[k + 1][0]
            if not x0 < x3:
                raise ValueError(f"knot x must increase strictly: {x0!r} >= {x3!r}")
            if not x0 <= x1 <= x2 <= x3:
                raise ValueError(f"segment {k}: control x must be non-decreasing: {(x0, x1, x2, x3)!r}")

    # -- construction -------------------------------------------------------------------

    @classmethod
    def from_knots(cls, ys: Sequence[float], xs: Sequence[float] = DEFAULT_KNOTS_X[1:-1],
                   preset: Optional[str] = None) -> "SignedCurve":
        """Interior knots `(xs[i], ys[i])` with aligned automatic handles everywhere."""
        knots = [(0.0, 1.0)] + [(float(x), float(y)) for x, y in zip(xs, ys)] + [(1.0, 0.0)]
        if len(knots) != KNOT_COUNT:
            raise ValueError(f"expected {len(INTERIOR)} interior knots")
        if not all(math.isfinite(y) and Y_MIN <= y <= Y_MAX for _x, y in knots):
            raise ValueError(f"knot y must be finite and in [-1, 1], got {ys!r}")
        hin, hout = [None] * KNOT_COUNT, [None] * KNOT_COUNT
        for i in range(KNOT_COUNT):
            a, b = _auto_handles(knots, i)
            # Automatic handles reach 1/3 of a segment from each side: no x overlap possible;
            # Fritsch–Carlson slopes keep them between the knot values (y in range).
            hin[i] = None if a is None else _fit(knots[i], a, knots[i - 1][0], knots[i][0])
            hout[i] = None if b is None else _fit(knots[i], b, knots[i][0], knots[i + 1][0])
        return cls(knots, hin, hout, preset=preset)

    @classmethod
    def from_preset(cls, name: str) -> "SignedCurve":
        return PRESET_CURVES[name]

    def _replace(self, knots=None, hin=None, hout=None, aligned=None) -> "SignedCurve":
        return SignedCurve(
            self.knots if knots is None else knots,
            self.handles_in if hin is None else hin,
            self.handles_out if hout is None else hout,
            self.aligned if aligned is None else aligned,
        )

    # -- edits (each returns a new curve, preset None) -------------------------------------

    def with_knot(self, i: int, x: float, y: float) -> "SignedCurve":
        """Interior knot `i` (1..4) moved to (x, y): x clamped strictly between its neighbours
        (`KNOT_MIN_GAP`), y to [-1, 1]; its handles move along (see module docstring)."""
        if i not in INTERIOR:
            raise ValueError(f"only interior knots move, got {i!r}")
        knots, hin, hout = list(self.knots), list(self.handles_in), list(self.handles_out)
        ox, oy = knots[i]
        nx = _clamp(float(x), knots[i - 1][0] + KNOT_MIN_GAP, knots[i + 1][0] - KNOT_MIN_GAP)
        ny = _clamp(float(y), Y_MIN, Y_MAX)
        dx, dy = nx - ox, ny - oy
        knots[i] = (nx, ny)
        # Carried handles may leave their own side or [-1, 1]: shrink toward the knot.
        hin[i] = _fit(knots[i], (hin[i][0] + dx, hin[i][1] + dy), -math.inf, nx)
        hout[i] = _fit(knots[i], (hout[i][0] + dx, hout[i][1] + dy), nx, math.inf)
        for k in (i - 1, i):
            _repair_segment(knots, hin, hout, k)
        return self._replace(knots, hin, hout)

    def with_handle(self, i: int, side: str, x: float, y: float,
                    break_alignment: bool = False) -> "SignedCurve":
        """Handle `side` ("in"/"out") of knot `i` dragged to (x, y), clamped to its box. An
        aligned knot turns its other handle along (collinear, old length, shrunk to fit);
        `break_alignment` (Alt) moves this handle only and makes the knot a corner."""
        knots, hin, hout = self.knots, list(self.handles_in), list(self.handles_out)
        aligned = list(self.aligned)
        kx, ky = knots[i]
        if side == HANDLE_OUT:
            if i == LAST:
                raise ValueError("the end knot at x = 1 has no out handle")
            new = (_clamp(float(x), kx, hin[i + 1][0]), _clamp(float(y), Y_MIN, Y_MAX))
            hout[i] = new
        elif side == HANDLE_IN:
            if i == FIRST:
                raise ValueError("the end knot at x = 0 has no in handle")
            new = (_clamp(float(x), hout[i - 1][0], kx), _clamp(float(y), Y_MIN, Y_MAX))
            hin[i] = new
        else:
            raise ValueError(f"unknown handle side {side!r}")
        if break_alignment:
            aligned[i] = False
        elif aligned[i] and i in INTERIOR:
            vx, vy = new[0] - kx, new[1] - ky
            length = math.hypot(vx, vy)
            if length > 0.0:
                if side == HANDLE_OUT:
                    other = hin[i]
                    reach = math.hypot(other[0] - kx, other[1] - ky)
                    hin[i] = _fit(knots[i], (kx - vx / length * reach, ky - vy / length * reach),
                                  hout[i - 1][0], kx)
                else:
                    other = hout[i]
                    reach = math.hypot(other[0] - kx, other[1] - ky)
                    hout[i] = _fit(knots[i], (kx - vx / length * reach, ky - vy / length * reach),
                                   kx, hin[i + 1][0])
        return self._replace(None, hin, hout, aligned)

    def with_auto_handles(self, i: int) -> "SignedCurve":
        """Knot `i` gets aligned automatic handles back (double click; module docstring),
        shrunk where a neighbour's handle already claims the segment."""
        knots, hin, hout = self.knots, list(self.handles_in), list(self.handles_out)
        aligned = list(self.aligned)
        a, b = _auto_handles(knots, i)
        if a is not None:
            hin[i] = _fit(knots[i], a, hout[i - 1][0], knots[i][0])
        if b is not None:
            hout[i] = _fit(knots[i], b, knots[i][0], hin[i + 1][0])
        aligned[i] = True
        return self._replace(None, hin, hout, aligned)

    # -- identity ------------------------------------------------------------------------

    @property
    def shape(self) -> tuple:
        """What the function depends on (the handle modes do not change it)."""
        return (self.knots, self.handles_in, self.handles_out)

    @property
    def key(self) -> tuple:
        return self.shape + (self.aligned,)

    def __eq__(self, other) -> bool:
        return isinstance(other, SignedCurve) and self.key == other.key

    def __hash__(self) -> int:
        return hash(self.key)

    def __repr__(self) -> str:
        return f"SignedCurve(knots={self.knots!r}, preset={self.preset!r})"

    @property
    def label(self) -> str:
        return PRESET_LABELS.get(self.preset, "eigene Kurve") if self.preset else "eigene Kurve"

    @property
    def has_negative(self) -> bool:
        """True if a control point lies below zero (only then can the curve go below zero)."""
        return any(y < 0.0 for _x, y in self.control_points())

    def control_points(self) -> list[Point]:
        return list(self.knots) + [h for h in self.handles_in + self.handles_out if h is not None]

    def segment(self, k: int) -> tuple[Point, Point, Point, Point]:
        s = self._segments[k]
        return ((s[0], s[4]), (s[1], s[5]), (s[2], s[6]), (s[3], s[7]))

    # -- evaluation ------------------------------------------------------------------------

    def _locate(self, x: float) -> tuple[tuple, float]:
        k = min(bisect.bisect_right(self._xs, x) - 1, KNOT_COUNT - 2)
        seg = self._segments[k]
        return seg, _solve_t(seg[0], seg[1], seg[2], seg[3], x)

    def __call__(self, x: float) -> float:
        """w at x = d/r. Endpoints are exact: f(0) = 1, f(1) = 0. x outside [0, 1] is clamped."""
        if x <= 0.0:
            return 1.0
        if x >= 1.0:
            return 0.0
        seg, t = self._locate(x)
        return _bezier(seg[4], seg[5], seg[6], seg[7], t)

    def slope(self, x: float) -> float:
        """dw/dx at x (one-sided at the ends; ±inf where a handle is vertical)."""
        x = _clamp(x, 0.0, 1.0)
        if x >= 1.0:
            seg, t = self._segments[-1], 1.0
        else:
            seg, t = self._locate(x)
        dx = _bezier_d(seg[0], seg[1], seg[2], seg[3], t)
        dy = _bezier_d(seg[4], seg[5], seg[6], seg[7], t)
        if dx == 0.0:
            return math.copysign(math.inf, dy) if dy != 0.0 else 0.0
        return dy / dx

    def sample_points(self, per_segment: int = 24) -> list[Point]:
        """Points along the curve, uniform in t per segment (shows steep parts too)."""
        points: list[Point] = [self.knots[0]]
        for seg in self._segments:
            for j in range(1, per_segment + 1):
                t = j / per_segment
                points.append((_bezier(seg[0], seg[1], seg[2], seg[3], t),
                               _bezier(seg[4], seg[5], seg[6], seg[7], t)))
        return points

    def as_function(self) -> Callable[[float], float]:
        return self.__call__


def _solve_t(x0: float, x1: float, x2: float, x3: float, x: float) -> float:
    """t in [0, 1] with x(t) = x for a segment whose x(t) is non-decreasing: Newton steps
    kept inside a shrinking bisection bracket."""
    if x <= x0:
        return 0.0
    if x >= x3:
        return 1.0
    lo, hi = 0.0, 1.0
    t = (x - x0) / (x3 - x0)
    for _ in range(_MAX_ITERATIONS):
        err = _bezier(x0, x1, x2, x3, t) - x
        if err == 0.0:
            return t
        if err > 0.0:
            hi = t
        else:
            lo = t
        if hi - lo <= _T_TOLERANCE:
            break
        d = _bezier_d(x0, x1, x2, x3, t)
        nxt = t - err / d if d > 0.0 else -1.0
        if not lo < nxt < hi:
            nxt = 0.5 * (lo + hi)
        if nxt == t:
            break
        t = nxt
    return t


def _repair_segment(knots, hin, hout, k: int) -> None:
    """Segment `k` with overlapping handles in x: both shrink by the same factor toward their
    knots so they just meet (directions kept)."""
    (kx0, ky0), (kx1, ky1) = knots[k], knots[k + 1]
    out, inn = hout[k], hin[k + 1]
    if out[0] <= inn[0]:
        return
    a, b = out[0] - kx0, kx1 - inn[0]
    f = (kx1 - kx0) / (a + b)
    out = (kx0 + a * f, ky0 + (out[1] - ky0) * f)
    inn = (kx1 - b * f, ky1 + (inn[1] - ky1) * f)
    if out[0] > inn[0]:  # rounding
        out = (inn[0], out[1])
    hout[k], hin[k + 1] = out, inn


PRESET_SMOOTH = "smooth"
PRESET_HAT = "hat"
PRESET_LABELS = {PRESET_SMOOTH: "Smooth", PRESET_HAT: "Mexican Hat"}
#: The Slice 1 knot values of the Mexican Hat (E13), at x = 0.2 / 0.4 / 0.6 / 0.8.
HAT_KNOTS_Y: tuple[float, ...] = (0.70, 0.10, -0.35, -0.30)


def _smooth_curve() -> SignedCurve:
    """Exact smoothstep (module docstring): one segment, split by de Casteljau."""
    rest: tuple[Point, ...] = ((0.0, 1.0), (1.0 / 3.0, 1.0), (2.0 / 3.0, 0.0), (1.0, 0.0))
    pieces = []
    start = 0.0
    for x in DEFAULT_KNOTS_X[1:-1]:
        left, rest = split_bezier(rest, (x - start) / (1.0 - start))  # x(t) is linear in t
        pieces.append(left)
        start = x
    pieces.append(rest)
    knots = [pieces[0][0]] + [p[3] for p in pieces]
    hout = [p[1] for p in pieces] + [None]
    hin = [None] + [p[2] for p in pieces]
    knots[0], knots[-1] = (0.0, 1.0), (1.0, 0.0)
    return SignedCurve(knots, hin, hout, preset=PRESET_SMOOTH)


PRESET_CURVES: dict[str, SignedCurve] = {
    PRESET_SMOOTH: _smooth_curve(),
    PRESET_HAT: SignedCurve.from_knots(HAT_KNOTS_Y, preset=PRESET_HAT),
}

DEFAULT_CURVE = PRESET_CURVES[PRESET_SMOOTH]
