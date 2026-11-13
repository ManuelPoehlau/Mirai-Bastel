"""The candidate slide algorithms behind one interface, so they run under identical conditions.

    cand.begin(setup)            # once per gesture; the reference surface is immutable from here on
    result = cand.update(delta)  # `delta`: the drag as a world-space vector since the gesture began (absolute)

Every candidate takes the *absolute* drag; the incremental ones difference it against the previous call themselves, so
a drag path is the same sequence of calls for all of them. Nothing here knows a camera, a mouse or a `core.Mesh`.

| name            | update    | idea                                                                                  |
|-----------------|-----------|---------------------------------------------------------------------------------------|
| closest_global  | absolute  | free move `p0 + w d`, then the globally closest surface point                           |
| ray_normal      | absolute  | free move, then along the start normal (both ways) to the nearest hit                 |
| ray_view        | absolute  | free move, then along a fixed view direction to the first hit ("face project")        |
| closest_local   | absolute  | free move, then closest point by adjacency descent from the previous anchor           |
| tangent_local   | increment | tangent-plane step at the current anchor, then closest point by adjacency descent     |
| geodesic_inc    | increment | tangent-plane step at the current anchor, walked as a geodesic from the current anchor |
| geodesic_walk   | increment | 2D drag in the start frame; its change walked in a frame transported with the anchor  |
| geodesic_abs    | absolute  | the whole drag as one geodesic from the *start* anchor (exponential map)              |
| geodesic_pursuit| abs+limit | hybrid: geodesic_abs is the target, pursued along the surface at a limited speed      |
| geodesic_seeded | absolute  | hybrid: geodesic_abs finds the region, adjacency descent to the free-move target      |
| lerp(<base>)    | absolute  | negative control for soft selection: `p0 + w (base(w=1) - p0)`                         |
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import geodesic as geo
from .refsurf import RefSurface, _unit

_I = np.intp


@dataclass
class SlideSetup:
    ref: RefSurface
    tri0: np.ndarray               # (n,) start anchors
    bary0: np.ndarray              # (n, 3)
    p0: np.ndarray                 # (n, 3) start positions
    n0: np.ndarray                 # (n, 3) start normals (the tangent planes of the gesture)
    weights: np.ndarray            # (n,) in [0, 1]
    verts: np.ndarray              # (n,) reference vertex the point starts on, -1 = not on a vertex
    pivot: int = 0                 # row of the vertex the drag is meant for (transport origin)
    transport: np.ndarray | None = None   # (n, 3, 3) pivot tangent plane -> each row's (fields.transport_frames)
    nbr: np.ndarray | None = None  # adjacency with barrier edges cut (None = the surface's own)

    @classmethod
    def from_vertices(cls, ref: RefSurface, verts, weights=None, pivot: int = 0, transport=None, nbr=None
                      ) -> "SlideSetup":
        verts = np.asarray(verts, dtype=_I)
        tri0, bary0 = ref.vertex_anchor(verts)
        w = np.ones(len(verts)) if weights is None else np.asarray(weights, dtype=np.float64)
        return cls(ref, tri0, bary0, ref.V[verts].copy(), ref.VN[verts].copy(), w, verts, pivot, transport, nbr)

    @classmethod
    def from_points(cls, ref: RefSurface, points, weights=None, pivot: int = 0) -> "SlideSetup":
        """Points of another mesh: anchored at their closest surface point (their offset from it is dropped)."""
        points = np.asarray(points, dtype=np.float64)
        tri0, bary0, _ = ref.closest_point(points)
        w = np.ones(len(points)) if weights is None else np.asarray(weights, dtype=np.float64)
        return cls(ref, tri0, bary0, ref.point(tri0, bary0), ref.normal_at(tri0, bary0), w,
                   np.full(len(points), -1, dtype=_I), pivot)

    @property
    def n(self) -> int:
        return len(self.tri0)


@dataclass
class SlideResult:
    pos: np.ndarray     # (n, 3)
    tri: np.ndarray     # (n,) anchor triangle the candidate claims
    bary: np.ndarray    # (n, 3)
    flags: np.ndarray   # (n,) uint8, geodesic.FLAG_*
    passes: int = 0


class Candidate:
    name = "?"
    kind = "absolute"

    def __init__(self, evaluator: str = "flat", alpha: float = 0.75) -> None:
        self.evaluator, self.alpha = evaluator, alpha

    def _eval(self, tri: np.ndarray, bary: np.ndarray) -> np.ndarray:
        ref = self.setup.ref
        return ref.point(tri, bary) if self.evaluator == "flat" else ref.point_phong(tri, bary, self.alpha)

    def begin(self, setup: SlideSetup) -> None:
        self.setup = setup
        self._begin()

    def _begin(self) -> None:
        pass

    def update(self, delta) -> SlideResult:
        raise NotImplementedError

    @property
    def label(self) -> str:
        return self.name if self.evaluator == "flat" else f"{self.name}+{self.evaluator}"


def _free_target(setup: SlideSetup, delta: np.ndarray) -> np.ndarray:
    return setup.p0 + setup.weights[:, None] * delta[None, :]


def _tangent(vec: np.ndarray, normal: np.ndarray) -> np.ndarray:
    return vec - np.einsum("ij,ij->i", vec, normal)[:, None] * normal


# --- projection candidates -----------------------------------------------------------------------------------------

class ClosestGlobal(Candidate):
    name = "closest_global"

    def _begin(self) -> None:
        self.setup.ref.build_grid()

    def update(self, delta) -> SlideResult:
        s = self.setup
        tri, bary, _ = s.ref.closest_point(_free_target(s, np.asarray(delta, dtype=np.float64)))
        return SlideResult(self._eval(tri, bary), tri, bary, np.zeros(s.n, dtype=np.uint8))


class RayNormal(Candidate):
    """Free move, then the line through the target along the *start* normal; the hit nearest the target wins. A miss
    falls back to the global closest point (flagged)."""

    name = "ray_normal"

    def _begin(self) -> None:
        self.setup.ref.build_grid()

    def update(self, delta) -> SlideResult:
        s = self.setup
        target = _free_target(s, np.asarray(delta, dtype=np.float64))
        reach = s.ref.bbox_diag
        hits = s.ref.intersect_lines(target, s.n0, -reach, reach)
        tri, bary = hits.tri, hits.bary
        flags = np.zeros(s.n, dtype=np.uint8)
        miss = ~hits.hit
        if np.any(miss):
            t2, b2, _ = s.ref.closest_point(target[miss])
            tri[miss], bary[miss] = t2, b2
            flags[miss] |= geo.FLAG_FALLBACK
        return SlideResult(self._eval(tri, bary), tri, bary, flags)


class RayView(Candidate):
    """Free move, then along one fixed direction (the view direction, pointing away from the eye) to the first hit:
    the vertex stays under the cursor. A miss falls back to the global closest point (flagged)."""

    name = "ray_view"

    def __init__(self, view_dir, evaluator: str = "flat", alpha: float = 0.75) -> None:
        super().__init__(evaluator, alpha)
        self.view_dir = _unit(np.asarray(view_dir, dtype=np.float64))

    def _begin(self) -> None:
        self.setup.ref.build_grid()

    def update(self, delta) -> SlideResult:
        s = self.setup
        target = _free_target(s, np.asarray(delta, dtype=np.float64))
        reach = 2.0 * s.ref.bbox_diag + float(np.linalg.norm(delta))
        origin = target - reach * self.view_dir
        hits = s.ref.intersect_lines(origin, np.broadcast_to(self.view_dir, target.shape), 0.0, 2.0 * reach)
        tri, bary = hits.tri, hits.bary
        flags = np.zeros(s.n, dtype=np.uint8)
        miss = ~hits.hit
        if np.any(miss):
            t2, b2, _ = s.ref.closest_point(target[miss])
            tri[miss], bary[miss] = t2, b2
            flags[miss] |= geo.FLAG_FALLBACK
        return SlideResult(self._eval(tri, bary), tri, bary, flags)


class ClosestLocal(Candidate):
    """Absolute target, local search: the descent starts at the previous call's anchor, so the answer depends on the
    path the drag took whenever the distance has more than one local minimum."""

    name = "closest_local"

    def _begin(self) -> None:
        self._tri = self.setup.tri0.copy()

    def update(self, delta) -> SlideResult:
        s = self.setup
        tri, bary, _, steps = s.ref.closest_point_local(_free_target(s, np.asarray(delta, dtype=np.float64)), self._tri)
        self._tri = tri
        return SlideResult(self._eval(tri, bary), tri, bary, np.zeros(s.n, dtype=np.uint8), int(steps.max(initial=0)))


class TangentLocal(Candidate):
    """Incremental: the step since the last call, projected into the tangent plane at the current anchor, then the
    closest point by adjacency descent."""

    name = "tangent_local"
    kind = "incremental"

    def _begin(self) -> None:
        s = self.setup
        self._tri, self._bary = s.tri0.copy(), s.bary0.copy()
        self._flat = s.p0.copy()
        self._prev = np.zeros(3)

    def update(self, delta) -> SlideResult:
        s = self.setup
        delta = np.asarray(delta, dtype=np.float64)
        step = s.weights[:, None] * (delta - self._prev)[None, :]
        self._prev = delta.copy()
        normal = s.ref.normal_at(self._tri, self._bary)
        tri, bary, _, steps = s.ref.closest_point_local(self._flat + _tangent(step, normal), self._tri)
        self._tri, self._bary = tri, bary
        self._flat = s.ref.point(tri, bary)
        return SlideResult(self._eval(tri, bary), tri, bary, np.zeros(s.n, dtype=np.uint8), int(steps.max(initial=0)))


# --- geodesic candidates -------------------------------------------------------------------------------------------

def _launch(setup: SlideSetup, tri, bary, tangent: np.ndarray, at_vertex: np.ndarray, vertex: np.ndarray):
    """Rays for the tangent vectors `tangent` (length = distance) from the anchors `(tri, bary)`."""
    ref = setup.ref
    n = len(tri)
    length = np.linalg.norm(tangent, axis=1)
    unit_t = tangent / np.where(length > 0.0, length, 1.0)[:, None]
    tri = np.array(tri, dtype=_I)
    bary = np.array(bary, dtype=np.float64)
    d = np.zeros((n, 3))
    flags = np.zeros(n, dtype=np.uint8)
    moving = length > 0.0
    vs = at_vertex & moving
    if np.any(vs):
        t_, b_, d_, f_ = geo.launch_from_vertices(ref, vertex[vs], unit_t[vs], setup.nbr)
        tri[vs], bary[vs], d[vs], flags[vs] = t_, b_, d_, f_
    rest = ~at_vertex & moving
    if np.any(rest):
        d[rest] = geo.launch_from_anchors(ref, tri[rest], unit_t[rest])
    length = np.where((flags & geo.FLAG_BLOCKED) > 0, 0.0, length)
    return tri, bary, d, length, flags


class GeodesicAbs(Candidate):
    """The exponential map from the start anchor: every call traces the whole drag again from where the gesture
    began, so the result is a function of `delta` alone - no state, no drift, `delta = 0` is the start to the bit.

    `direction`:
    - "project":   each point takes the drag projected into its *own* start tangent plane (`w (d - (d.n) n)`).
    - "transport": the pivot takes its projected drag; every other point takes that vector carried to it by the
                   tangent transport (`setup.transport`), scaled by its weight - the selection moves like a decal.
    `length`: "tangent" keeps the projected length; "full" travels `w |d|` in the projected direction.
    """

    name = "geodesic_abs"

    def __init__(self, direction: str = "project", length: str = "tangent", evaluator: str = "flat",
                 alpha: float = 0.75) -> None:
        super().__init__(evaluator, alpha)
        self.direction, self.length = direction, length

    @property
    def label(self) -> str:
        base = f"geodesic_abs[{self.direction}]" + ("" if self.length == "tangent" else "[full]")
        return base if self.evaluator == "flat" else f"{base}+{self.evaluator}"

    def tangents(self, delta: np.ndarray) -> np.ndarray:
        s = self.setup
        if self.direction == "project":
            t = _tangent(np.broadcast_to(delta, s.p0.shape), s.n0)
            scale = np.linalg.norm(delta)
        else:
            if s.transport is None:
                raise ValueError("direction='transport' needs setup.transport")
            np_ = s.n0[s.pivot]
            tp = delta - (delta @ np_) * np_
            t = np.einsum("nij,j->ni", s.transport, tp)
            t = _tangent(t, s.n0)   # the transport is exact up to rounding; keep the vector in the tangent plane
            scale = np.linalg.norm(delta)
        if self.length == "full":
            tl = np.linalg.norm(t, axis=1)
            t = t * (scale / np.where(tl > 1e-12 * max(scale, 1e-300), tl, np.inf))[:, None]
        return t * s.weights[:, None]

    def update(self, delta) -> SlideResult:
        s = self.setup
        delta = np.asarray(delta, dtype=np.float64)
        t = self.tangents(delta)
        tri, bary, d, length, flags = _launch(s, s.tri0, s.bary0, t, s.verts >= 0, s.verts)
        tr = geo.trace(s.ref, tri, bary, d, length, s.nbr)
        return SlideResult(self._eval(tr.tri, tr.bary), tr.tri, tr.bary, flags | tr.flags, tr.passes)


class GeodesicInc(Candidate):
    """Incremental geodesic: the step since the last call, projected at the *current* anchor, walked from the current
    anchor. Cheap per call (a step crosses few edges) but the result depends on the path of the drag."""

    name = "geodesic_inc"
    kind = "incremental"

    def _begin(self) -> None:
        s = self.setup
        self._tri, self._bary = s.tri0.copy(), s.bary0.copy()
        self._prev = np.zeros(3)

    def update(self, delta) -> SlideResult:
        s = self.setup
        ref = s.ref
        delta = np.asarray(delta, dtype=np.float64)
        step = s.weights[:, None] * (delta - self._prev)[None, :]
        self._prev = delta.copy()
        corner = np.argmax(self._bary, axis=1)
        at_vertex = self._bary[np.arange(s.n), corner] == 1.0
        vertex = ref.T[self._tri, corner]
        normal = np.where(at_vertex[:, None], ref.VN[vertex], ref.normal_at(self._tri, self._bary))
        tri, bary, d, length, flags = _launch(s, self._tri, self._bary, _tangent(step, normal), at_vertex, vertex)
        tr = geo.trace(ref, tri, bary, d, length, s.nbr)
        self._tri, self._bary = tr.tri, tr.bary
        return SlideResult(self._eval(tr.tri, tr.bary), tr.tri, tr.bary, flags | tr.flags, tr.passes)


def _rotate_in_plane(d: np.ndarray, normal: np.ndarray, cos_t: np.ndarray, sin_t: np.ndarray) -> np.ndarray:
    return d * cos_t[:, None] + np.cross(normal, d) * sin_t[:, None]


class GeodesicWalk(Candidate):
    """Incremental geodesic in a *transported frame*: the persistent state of a point is its anchor plus one unit
    tangent vector `f` that is carried along every path the point walks (unfolded across each edge with it).

    The drag is first reduced to a 2D vector `u` in the point's start tangent frame - linear in `delta`, so a drag
    that returns to zero has `u = 0` again. A call walks the *change* of `u` since the last call, expressed in the
    transported frame at the current anchor. Unlike `geodesic_inc` nothing is re-projected at the current normal:
    on a flat or developable region the result is exactly path independent; on a curved one two paths to the same
    `u` differ only by the curvature enclosed between them (holonomy). A step never moves a point farther than the
    drag changed, so there are no pops. `u == 0` restores the start state exactly.

    `direction` as in `GeodesicAbs`: "project" (each point its own projected drag) or "transport" (every point
    the pivot's `u`, scaled by its weight, in its own transported start frame: the selection moves like a decal).
    """

    name = "geodesic_walk"
    kind = "incremental"

    def __init__(self, direction: str = "project", evaluator: str = "flat", alpha: float = 0.75) -> None:
        super().__init__(evaluator, alpha)
        self.direction = direction

    @property
    def label(self) -> str:
        base = f"geodesic_walk[{self.direction}]"
        return base if self.evaluator == "flat" else f"{base}+{self.evaluator}"

    def _begin(self) -> None:
        s = self.setup
        n0 = s.n0
        if self.direction == "transport":
            if s.transport is None:
                raise ValueError("direction='transport' needs setup.transport")
            npv = n0[s.pivot]
            helper = np.eye(3)[int(np.argmin(np.abs(npv)))]
            e1p = _unit(np.cross(npv, helper)[None, :])[0]
            self._e1p, self._e2p = e1p, np.cross(npv, e1p)
            e1 = _unit(_tangent(np.einsum("nij,j->ni", s.transport, e1p), n0))
        else:
            helper = np.eye(3)[np.argmin(np.abs(n0), axis=1)]
            e1 = _unit(np.cross(n0, helper))
        self._e1 = e1                       # start frame (in the start tangent plane)
        self._e2 = np.cross(n0, e1)
        self._reset()

    def _reset(self) -> None:
        s = self.setup
        self._tri, self._bary = s.tri0.copy(), s.bary0.copy()
        self._f = self._e1.copy()
        self._normal = s.n0.copy()          # the plane `f` lies in: start normal, later the anchor triangle's
        self._at_start = np.ones(s.n, dtype=bool)
        self._u = np.zeros((s.n, 2))

    def coordinates(self, delta: np.ndarray) -> np.ndarray:
        """The 2D drag `u (n, 2)` of every point in its start frame; linear in `delta`."""
        s = self.setup
        if self.direction == "transport":
            np_ = s.n0[s.pivot]
            tp = delta - (delta @ np_) * np_
            up = np.array([tp @ self._e1p, tp @ self._e2p])
            return s.weights[:, None] * up[None, :]
        t = _tangent(np.broadcast_to(delta, s.p0.shape), s.n0) * s.weights[:, None]
        return np.stack([np.einsum("ij,ij->i", t, self._e1), np.einsum("ij,ij->i", t, self._e2)], axis=1)

    def update(self, delta) -> SlideResult:
        s = self.setup
        ref = s.ref
        delta = np.asarray(delta, dtype=np.float64)
        u = self.coordinates(delta)
        if not np.any(u):
            self._reset()
            return SlideResult(s.p0.copy(), s.tri0.copy(), s.bary0.copy(), np.zeros(s.n, dtype=np.uint8))
        du = u - self._u
        self._u = u
        f, normal = self._f, self._normal
        step = du[:, :1] * f + du[:, 1:] * np.cross(normal, f)
        length = np.linalg.norm(step, axis=1)
        unit = step / np.where(length > 0.0, length, 1.0)[:, None]
        cos_t = np.einsum("ij,ij->i", f, unit)                       # angle from the step to the frame vector
        sin_t = np.einsum("ij,ij->i", np.cross(unit, f), normal)
        at_vertex = self._at_start & (s.verts >= 0)
        tri, bary, d, length, flags = _launch(s, self._tri, self._bary, step, at_vertex, s.verts)
        tr = geo.trace(ref, tri, bary, d, length, s.nbr)
        moved = length > 0.0
        new_normal = np.where(moved[:, None], ref.N[tr.tri], normal)
        new_f = np.where(moved[:, None], _unit(_rotate_in_plane(tr.direction, ref.N[tr.tri], cos_t, sin_t)), f)
        self._tri, self._bary, self._f, self._normal = tr.tri, tr.bary, new_f, new_normal
        self._at_start &= ~moved
        return SlideResult(self._eval(tr.tri, tr.bary), tr.tri, tr.bary, flags | tr.flags, tr.passes)


class GeodesicPursuit(Candidate):
    """Hybrid: the absolute geodesic (`GeodesicAbs`) is the *target*, and each point *pursues* its target along the
    surface at a limited speed: per call it may travel at most `(1 + gain) x` the change of its own tangential drag.

    Where the absolute map is continuous the target is always within reach and the point simply *is* the target:
    the result is the path-independent one, and `delta = 0` is the start to the bit. Where the absolute map tears
    (the straight path from the start flips to the other side of a strongly curved vertex when the drag turns) the
    point does not pop: it slides towards the new target and has caught up after the drag moved on by
    `tear / gain`. If the drag stops before that, the point keeps its lag (it never moves on its own).
    """

    name = "geodesic_pursuit"
    kind = "absolute+limiter"

    def __init__(self, direction: str = "project", gain: float = 1.0, evaluator: str = "flat",
                 alpha: float = 0.75) -> None:
        super().__init__(evaluator, alpha)
        self.direction, self.gain = direction, gain
        self._target = GeodesicAbs(direction)

    @property
    def label(self) -> str:
        base = f"geodesic_pursuit[{self.direction}]"
        return base if self.evaluator == "flat" else f"{base}+{self.evaluator}"

    def _begin(self) -> None:
        self._target.begin(self.setup)
        self._reset()

    def _reset(self) -> None:
        s = self.setup
        self._tri, self._bary, self._pos = s.tri0.copy(), s.bary0.copy(), s.p0.copy()
        self._at_start = np.ones(s.n, dtype=bool)
        self._t = np.zeros((s.n, 3))
        self._last = SlideResult(s.p0.copy(), s.tri0.copy(), s.bary0.copy(), np.zeros(s.n, dtype=np.uint8))
        self.lagging = np.zeros(s.n, dtype=bool)

    def update(self, delta) -> SlideResult:
        s = self.setup
        delta = np.asarray(delta, dtype=np.float64)
        t = self._target.tangents(delta)
        if not np.any(t):
            self._reset()
            return SlideResult(s.p0.copy(), s.tri0.copy(), s.bary0.copy(), np.zeros(s.n, dtype=np.uint8))
        self._last = self._target.update(delta)
        budget = (1.0 + self.gain) * np.linalg.norm(t - self._t, axis=1) + 1e-12 * s.ref.mean_edge
        self._t = t
        return self._chase(budget)

    def settle(self, max_step: float) -> SlideResult:
        """Let lagging points close in on their targets by up to `max_step` each, without any change of the drag
        (for the host to call while the pointer rests, or before a commit). Does nothing when nothing lags."""
        s = self.setup
        return self._chase(np.where(self.lagging, max_step, 0.0))

    def _chase(self, budget: np.ndarray) -> SlideResult:
        s = self.setup
        ref = s.ref
        target = self._last
        target_pos = ref.point(target.tri, target.bary)
        gap_vec = target_pos - self._pos
        gap = np.linalg.norm(gap_vec, axis=1)
        reach = gap <= budget
        tri = np.where(reach, target.tri, self._tri)
        bary = np.where(reach[:, None], target.bary, self._bary)
        flags = target.flags.copy()
        passes = target.passes
        late = ~reach
        if np.any(late):
            idx = np.flatnonzero(late)
            at_vertex = self._at_start[idx] & (s.verts[idx] >= 0)
            normal = np.where(at_vertex[:, None], s.n0[idx], ref.N[self._tri[idx]])
            step = _unit(_tangent(gap_vec[idx], normal)) * np.minimum(budget[idx], gap[idx])[:, None]
            sub = SlideSetup(ref, self._tri[idx], self._bary[idx], self._pos[idx], normal, np.ones(len(idx)),
                             s.verts[idx], 0, None, s.nbr)
            tr_, b_, d_, len_, f_ = _launch(sub, self._tri[idx], self._bary[idx], step, at_vertex, s.verts[idx])
            tr = geo.trace(ref, tr_, b_, d_, len_, s.nbr)
            tri[idx], bary[idx] = tr.tri, tr.bary
            passes += tr.passes
        self.lagging = late
        self._tri, self._bary = tri, bary
        self._pos = ref.point(tri, bary)
        self._at_start &= np.all(bary == s.bary0, axis=1) & (tri == s.tri0)
        return SlideResult(self._eval(tri, bary), tri, bary, flags, passes)


class GeodesicSeeded(Candidate):
    """Hybrid: `geodesic_abs` decides *where on the surface* the point is (continuous, anchored), then an adjacency
    descent from that anchor finds the closest point to the free-move target `p0 + w d`. Absolute like its seed; the
    result follows the world-space drag more closely than the geodesic and cannot leave the region the seed is in
    unless the descent itself walks there."""

    name = "geodesic_seeded"

    def __init__(self, direction: str = "project", evaluator: str = "flat", alpha: float = 0.75) -> None:
        super().__init__(evaluator, alpha)
        self._seed = GeodesicAbs(direction)
        self.name = f"geodesic_seeded[{direction}]"

    def _begin(self) -> None:
        self._seed.begin(self.setup)

    def update(self, delta) -> SlideResult:
        s = self.setup
        delta = np.asarray(delta, dtype=np.float64)
        seed = self._seed.update(delta)
        tri, bary, _, steps = s.ref.closest_point_local(_free_target(s, delta), seed.tri)
        return SlideResult(self._eval(tri, bary), tri, bary, seed.flags, seed.passes + int(steps.max(initial=0)))


class Lerp(Candidate):
    """Negative control: run `base` with every weight 1, then blend each point linearly between its start and that
    full result by its weight. The blended point is a chord point - in general not on the surface."""

    def __init__(self, base: Candidate) -> None:
        super().__init__("flat")
        self.base = base
        self.name = f"lerp({base.label})"
        self.kind = base.kind

    def _begin(self) -> None:
        s = self.setup
        full = SlideSetup(s.ref, s.tri0, s.bary0, s.p0, s.n0, np.ones(s.n), s.verts, s.pivot, s.transport, s.nbr)
        self.base.begin(full)

    def update(self, delta) -> SlideResult:
        s = self.setup
        r = self.base.update(delta)
        pos = s.p0 + s.weights[:, None] * (r.pos - s.p0)
        return SlideResult(pos, r.tri, r.bary, r.flags, r.passes)


def standard_candidates(view_dir=None) -> list[Candidate]:
    """The set every scenario compares (flat evaluation, per-point projected drag)."""
    out: list[Candidate] = [ClosestGlobal(), RayNormal()]
    if view_dir is not None:
        out.append(RayView(view_dir))
    out += [ClosestLocal(), TangentLocal(), GeodesicInc(), GeodesicWalk("project"), GeodesicAbs("project"),
            GeodesicPursuit("project"), GeodesicSeeded("project")]
    return out
