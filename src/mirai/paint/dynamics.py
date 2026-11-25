"""Stroke dynamics, the path sampler and the stamp queue (AD-037 §12 Phase 4a; proposal 2026-11-25 §5.2-§5.4).

**Spacing in world arc length** (P-18): `StrokeDynamics.spacing` is a fraction of the stamp's diameter (`2 r`); the
placements of a stroke lie every `spacing * 2 r` along the **surface path** - the polyline of the hits of the cursor's
rays, sampled finely between input events. The arc-length remainder carries across events, so the spacing is exact
across their boundaries. A **hit gap** (a sample misses the object, or the path jumps - a silhouette) ends the run: the
next hit starts a new run with its own first placement, nothing is interpolated across the gap.

**Orientation** "Strich folgen" (P-21, the only mode of 4a): the stamp's "up" follows the path. Placement `k`'s tangent
is the chord from placement `k-1`, exponentially smoothed over arc length (`SMOOTHING_LENGTH`), so mouse jitter does
not rotate the stamps -
smoothed *on the surface*: the previous tangent is first turned onto the new hit's tangent plane (the minimal rotation
between the two hit normals) and the chord projected into it, so crossing a ridge does not make the direction lag
behind the surface's own turn (a twist of up to 22° per placement across the nose at 100 % spacing otherwise). The
first placement of a run waits until the path has a direction (the second placement); a run that ends before it takes
the chord it has, or - a click without movement - none (`tangent` None: the caller's view-fixed rule).

**The queue** (P-27, §5.4): input events only add rays (`add_ray`; the camera can zoom while the stroke runs, so the
screen point becomes a ray at once). Sampling (one ray hit per sample) and evaluating placements (the caller's
`evaluate`) both happen in `run(budget)`, called once per frame within a time budget; the sampler only runs while the
placement queue is empty, so the queue never holds more than one sample's placements and the backlog is the unsampled
path, which trails the cursor and catches up (never gaps). `remaining_estimate()` prices the backlog from running means
on this machine; `frame_budget` raises the frame's budget by the excess over `BACKLOG_S` (up to `CATCHUP_BUDGET_S`). After `end_input()` (the release) `run` drains the rest
over the following frames; `done` says when nothing is left.

Placements are a pure function of the rays and their sample counts: the budget, the frame timing and how the work is
chunked never change them (the 4b replay test builds on this).
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

import numpy as np

#: Spacing range in fractions of the stamp diameter (`PROVISIONAL`, proposal §5.2: 2-300 %).
SPACING_MIN, SPACING_MAX = 0.02, 3.0
#: Default spacing of the round tip: today's look (Phase 2 dabbed every 0.25 r on screen = 12.5 % of the diameter at a
#: frontal view) and of an alpha tip (stamps touching; proposal §5.2 "about 100 %"). `PROVISIONAL`.
ROUND_SPACING = 0.125
ALPHA_SPACING = 1.0
ORIENTATIONS = ("stroke",)
ORIENTATION_LABELS = {"stroke": "Strich folgen"}
#: Exponential smoothing of the stroke direction over arc length (`PROVISIONAL`): a placement's weight is
#: `α = 1 - exp(-spacing / (SMOOTHING_LENGTH * r))` - mouse jitter is a length on the surface, so the smoothing is
#: too. 25 % spacing gives α ≈ 0.63 (the proposal's 0.5 per placement at a dense stroke), 100 % gives 0.98: stamps two
#: radii apart follow the stroke without the lag a fixed α = 0.5 had (up to 25° behind the stroke across the nose).
SMOOTHING_LENGTH = 0.5
#: A run's first placement takes a partial chord at the run's end when it is at least this fraction of the spacing
#: long; below that it counts as a click without movement (`PROVISIONAL`).
PARTIAL_CHORD = 0.1
#: Frame budgets in seconds (`PROVISIONAL`, §5.4, `frame_budget`): while stroking; while stroking with more than
#: `BACKLOG_S` of work behind the cursor the excess is drained at once, up to `CATCHUP_BUDGET_S` (catch-up: the backlog
#: stays near `BACKLOG_S` as long as the input does not outrun that); while finishing after the release (a frame stays
#: below 50 ms with the draw).
BUDGET_S = 0.010
CATCHUP_BUDGET_S = 0.022
FINISH_BUDGET_S = 0.030
BACKLOG_S = 0.150
#: The first estimates of a placement's and a sample's cost before a stroke has measured its own (seconds).
INITIAL_PLACEMENT_S = 0.004
INITIAL_SAMPLE_S = 0.0006


def frame_budget(queue: "StrokeQueue", finishing: bool) -> float:
    """This frame's time budget for `queue` (the constants above)."""
    if finishing:
        return FINISH_BUDGET_S
    excess = queue.remaining_estimate() - BACKLOG_S
    return min(max(BUDGET_S, excess), CATCHUP_BUDGET_S) if excess > 0.0 else BUDGET_S


@dataclass(frozen=True)
class StrokeDynamics:
    spacing: float = ROUND_SPACING
    orientation: str = "stroke"
    angle: float = 0.0  # degrees, the offset of the stamp's "up" from the orientation

    def __post_init__(self) -> None:
        if not (isinstance(self.spacing, (int, float)) and math.isfinite(self.spacing)
                and SPACING_MIN <= self.spacing <= SPACING_MAX):
            raise ValueError(f"spacing must lie in [{SPACING_MIN}, {SPACING_MAX}], got {self.spacing!r}")
        if self.orientation not in ORIENTATIONS:
            raise ValueError(f"orientation one of {ORIENTATIONS}, got {self.orientation!r}")
        if not (isinstance(self.angle, (int, float)) and math.isfinite(self.angle) and -180.0 <= self.angle <= 180.0):
            raise ValueError(f"angle must lie in [-180, 180], got {self.angle!r}")


@dataclass(frozen=True, eq=False)
class Placement:
    """One stamp position of a stroke: `point` on (or on the chord between two hits of) the surface, `normal` the hit
    normal the gather's facing test uses, `tangent` the path direction (world, unit) or None (the view rule)."""

    index: int
    point: np.ndarray
    normal: np.ndarray
    tangent: np.ndarray | None = None


def _unit(v: np.ndarray) -> np.ndarray | None:
    length = float(np.linalg.norm(v))
    return v / length if length > 1e-12 else None


def _turned(u: np.ndarray, v: np.ndarray, w: np.ndarray) -> np.ndarray | None:
    """`w` turned by the minimal rotation taking unit `u` to unit `v` (Rodrigues); None for opposite normals."""
    c = float(np.dot(u, v))
    if c <= -0.999:
        return None
    k = np.cross(u, v)
    return w * c + np.cross(k, w) + k * float(np.dot(k, w)) / (1.0 + c)


class StrokeQueue:
    """The path sampler and the placement queue of one stroke (module docstring).

    `hit(origin, direction)` returns a surface hit (`.point`, `.normal`) or None; `spacing` and `jump` are world lengths
    (a sample farther than `jump` from the previous one ends the run); `directed` = placements need a direction (an alpha
    tip that follows the stroke); `evaluate(placement)` paints one placement."""

    def __init__(self, hit: Callable, spacing: float, jump: float, directed: bool,
                 evaluate: Callable[[Placement], None], radius: float | None = None) -> None:
        self._hit = hit
        self.spacing = float(spacing)
        #: the direction's smoothing weight per placement (`SMOOTHING_LENGTH`; `radius` None: half the spacing)
        length = SMOOTHING_LENGTH * (float(radius) if radius is not None else 0.5 * self.spacing)
        self._alpha = 1.0 - math.exp(-self.spacing / max(length, 1e-300))
        self.jump = float(jump)
        self.directed = directed
        self._evaluate = evaluate
        self._rays: deque = deque()          # (origin, direction, samples) not sampled yet
        self._segment = None                 # (o0, d0, o1, d1, samples) being sampled
        self._sample = 0                     # the next sample of `_segment` (1 .. samples)
        self._ray = None                     # the last ray sampled
        self._prev = None                    # the run's last sample hit
        self._to_next = 0.0                  # arc length from `_prev` to the next placement
        self._held: Placement | None = None  # the run's first placement waiting for a direction
        self._last_point = None              # the run's last placement point and tangent
        self._last_tangent = None
        self._last_normal = None
        self._ended = False
        self._flushed = False
        self.placements: deque[Placement] = deque()
        #: every placement emitted (tests: spacing, gaps; the cursor's last direction)
        self.emitted: list[Placement] = []
        self.evaluated = 0
        self.samples = 0
        self._placement_s = INITIAL_PLACEMENT_S
        self._sample_s = INITIAL_SAMPLE_S
        self._per_sample = 1.0
        self._pending_samples = 0

    # -- input -------------------------------------------------------------------------------------------------------

    def add_ray(self, origin, direction, samples: int = 1) -> None:
        """One input event's ray; `samples` = how many path samples lie between the previous ray and this one (the
        caller's screen distance over its sample step). The first ray is sampled once (the press)."""
        if self._ended:
            raise RuntimeError("the stroke's input has ended")
        samples = max(1, int(samples))
        self._rays.append((np.asarray(origin, dtype=np.float64), np.asarray(direction, dtype=np.float64), samples))
        self._pending_samples += samples

    def end_input(self) -> None:
        """The release: no more rays; `run` drains the rest."""
        self._ended = True

    @property
    def done(self) -> bool:
        return self._ended and self._flushed and not self.placements

    @property
    def last_tangent(self) -> np.ndarray | None:
        return self._last_tangent

    def remaining_estimate(self) -> float:
        """Seconds of work behind the cursor: the queued placements and the unsampled path (running means)."""
        return (len(self.placements) * self._placement_s
                + self._pending_samples * (self._sample_s + self._per_sample * self._placement_s))

    # -- the work ----------------------------------------------------------------------------------------------------

    def run(self, budget: float | None) -> int:
        """Samples and evaluates until `budget` seconds have passed (None: until nothing is left); at least one step.
        Returns the placements evaluated."""
        start = time.perf_counter()
        evaluated = self.evaluated
        while self._step():
            if budget is not None and time.perf_counter() - start >= budget:
                break
        return self.evaluated - evaluated

    def _step(self) -> bool:
        if self.placements:
            placement = self.placements.popleft()
            t = time.perf_counter()
            self._evaluate(placement)
            self._placement_s = 0.8 * self._placement_s + 0.2 * (time.perf_counter() - t)
            self.evaluated += 1
            return True
        if self._segment is not None or self._rays:
            t = time.perf_counter()
            before = len(self.emitted)
            self._sample_one()
            self._sample_s = 0.8 * self._sample_s + 0.2 * (time.perf_counter() - t)
            self._per_sample = 0.8 * self._per_sample + 0.2 * (len(self.emitted) - before)
            return True
        if self._ended and not self._flushed:
            self._end_run()
            self._flushed = True
            return bool(self.placements)
        return False

    def _sample_one(self) -> None:
        if self._segment is None:
            origin, direction, samples = self._rays.popleft()
            if self._ray is None:  # the press: one sample at the ray itself
                self._pending_samples -= samples
                self._ray = (origin, direction)
                self._take(self._hit(origin, direction / max(np.linalg.norm(direction), 1e-300)))
                return
            self._segment = (*self._ray, origin, direction, samples)
            self._sample = 1
        o0, d0, o1, d1, samples = self._segment
        f = self._sample / samples
        origin = o0 + (o1 - o0) * f
        direction = d0 + (d1 - d0) * f
        norm = float(np.linalg.norm(direction))
        self._pending_samples -= 1
        self.samples += 1
        hit = self._hit(origin, direction / norm) if norm > 0.0 else None
        if self._sample >= samples:
            self._ray = (o1, d1)
            self._segment = None
        else:
            self._sample += 1
        self._take(hit)

    def _take(self, hit) -> None:
        """One sample hit into the path: placements every `spacing` of arc length."""
        if hit is None:
            self._end_run()
            return
        point = np.asarray(hit.point, dtype=np.float64)
        normal = np.asarray(hit.normal, dtype=np.float64)
        if self._prev is not None and float(np.linalg.norm(point - self._prev[0])) > self.jump:
            self._end_run()
        if self._prev is None:  # a run starts: a placement at its first hit
            self._prev = (point, normal)
            self._to_next = self.spacing
            self._emit(point, normal)
            return
        p0, n0 = self._prev
        d = float(np.linalg.norm(point - p0))
        pos = 0.0
        while pos + self._to_next <= d:
            pos += self._to_next
            f = pos / d
            self._emit(p0 + (point - p0) * f, n0 if f < 0.5 else normal)
            self._to_next = self.spacing
        self._to_next -= d - pos
        self._prev = (point, normal)

    def _emit(self, point: np.ndarray, normal: np.ndarray) -> None:
        index = len(self.emitted) + (1 if self._held is not None else 0)
        if not self.directed:
            self._push(Placement(index, point, normal))
            return
        if self._last_point is None:  # the run's first placement: wait for the direction
            self._held = Placement(index, point, normal)
            self._last_point = point
            return
        chord = _unit(point - self._last_point)
        if self._held is not None:
            held, self._held = self._held, None
            self._last_tangent = chord
            self._last_normal = _unit(held.normal)
            self._push(Placement(held.index, held.point, held.normal, chord))
        tangent = chord
        if chord is not None and self._last_tangent is not None and self._last_normal is not None:
            unit_n = _unit(normal)
            previous = _turned(self._last_normal, unit_n, self._last_tangent) if unit_n is not None else None
            if unit_n is not None and previous is not None:
                in_plane = _unit(chord - np.dot(chord, unit_n) * unit_n)
                previous = _unit(previous - np.dot(previous, unit_n) * unit_n)
                if in_plane is not None and previous is not None:
                    tangent = _unit(self._alpha * in_plane + (1.0 - self._alpha) * previous)
            if tangent is None:
                tangent = chord
        if tangent is None:
            tangent = self._last_tangent
        self._last_tangent = tangent
        self._last_point = point
        self._last_normal = _unit(normal)
        self._push(Placement(index, point, normal, tangent))

    def _push(self, placement: Placement) -> None:
        self.placements.append(placement)
        self.emitted.append(placement)

    def _end_run(self) -> None:
        """A hit gap or the end: the held first placement takes the chord it has (or none), the run is over."""
        held, self._held = self._held, None
        if held is not None:
            tangent = None
            if self._prev is not None:
                chord = self._prev[0] - held.point
                if float(np.linalg.norm(chord)) >= PARTIAL_CHORD * self.spacing:
                    tangent = _unit(chord)
            self._push(Placement(held.index, held.point, held.normal, tangent))
        self._prev = None
        self._last_point = None
