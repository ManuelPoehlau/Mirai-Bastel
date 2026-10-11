"""Influence map: primary selection -> per-vertex weight in (0, 1] (WP-SOFT-01 S2a).

Home of the S1 experiment's `experiments/soft_selection/influence.py` on the app path
(AD-020); the experiment stays as the record. `docs/architecture/V1_CORE.md` §6: Soft
Selection is not a selection mode and not a vertex type. It is a *derived* map from the
primary selection that feeds an operation:

- The map is transient: the caller computes it right before `begin()` from the current
  (= start) positions and hands it to the operation; nothing here is stored, nothing is
  written into `Selection`.
- `w = 1` on seeds, `w = 0` at `d >= r` (vertices with `w = 0` are absent from the
  returned dict). The seeds are what the plain transform tools would move (the tool
  hands them in; this module never reads a `Selection`).
- Metrics `euclidean` (min straight-line distance to any seed) and `geodesic`
  (multi-source Dijkstra over mesh edges, edge length as cost, pruned at `r`).
- Curves on `t = 1 - d/r` in [0, 1] (S2d, handoff E1; formulas defined here, not copied
  from any product): `smooth` 3t^2 - 2t^3, `sphere` sqrt(2t - t^2), `root` sqrt(t),
  `sharp` t^2, `linear` t, `custom` t^p with `p` handed in (`curve_power`).

The metric/curve registries (`METRICS`, `CURVES`) are the "replaceable strategy" seam
V1_CORE §6 asks for - deliberately just dicts of functions, no class hierarchy. Every
curve has f(0) = 0, f(1) = 1 and is monotone non-decreasing. Which metric/curve is the
default lives in `settings.py` (S2c verdict, AD-020), not here.
"""

from __future__ import annotations

import heapq
import math
from typing import Callable, Iterable

from core import Mesh, VertexId

Position = tuple[float, float, float]


# --- Curves: t in [0, 1] (1 at the seed, 0 at the radius) -> weight ---------------

def _smooth(t: float) -> float:
    # Smoothstep keeps the influence boundary C1 (no slope jump at d = r).
    return t * t * (3.0 - 2.0 * t)


def _sphere(t: float) -> float:
    # Quarter circle through (0, 0) and (1, 1) with a vertical tangent at t = 0; the max()
    # guards a rounding hair below zero, never changes a real value.
    return math.sqrt(max(0.0, 2.0 * t - t * t))


def _root(t: float) -> float:
    return math.sqrt(t)


def _sharp(t: float) -> float:
    return t * t


def _linear(t: float) -> float:
    return t


def custom_curve(power: float) -> Callable[[float], float]:
    """`t^p`: p < 1 is rounder than linear, p > 1 sharper (p = 0.5 is `root`, p = 2 `sharp`)."""
    power = float(power)
    if not math.isfinite(power) or power <= 0.0:
        raise ValueError(f"curve power must be finite and > 0, got {power!r}.")

    def _custom(t: float) -> float:
        return t ** power

    return _custom


#: Insertion order is the Shift+O cycle order (handoff E3). `custom` here is the p = 1
#: instance (so the name validates); the real `p` comes from `compute_influence(curve_power=)`.
CURVES: dict[str, Callable[[float], float]] = {
    "smooth": _smooth,
    "sphere": _sphere,
    "root": _root,
    "sharp": _sharp,
    "linear": _linear,
    "custom": custom_curve(1.0),
}


# --- Metrics: seeds + radius -> {vertex: distance < radius} ------------------------

# Hand-written instead of `math.dist`: on the reference PC (Core 2 Quad, Python 3.14,
# Windows) `math.dist` measured 3.2 us per call vs 1.1 us for this form (FINDINGS R6).

def _dist_sq(p: Position, q: Position) -> float:
    dx, dy, dz = p[0] - q[0], p[1] - q[1], p[2] - q[2]
    return dx * dx + dy * dy + dz * dz


def _euclidean_distances(
    mesh: Mesh, seeds: set[VertexId], radius: float
) -> dict[VertexId, float]:
    seed_positions = [mesh.vertex_position(s) for s in seeds]
    # Cheap reject before the per-seed loop: the seeds' bounding box grown by r.
    lo = [min(p[i] for p in seed_positions) - radius for i in range(3)]
    hi = [max(p[i] for p in seed_positions) + radius for i in range(3)]
    radius_sq = radius * radius
    result: dict[VertexId, float] = {}
    for vid in mesh.all_vertex_ids():
        p = mesh.vertex_position(vid)
        if not (lo[0] <= p[0] <= hi[0] and lo[1] <= p[1] <= hi[1] and lo[2] <= p[2] <= hi[2]):
            continue
        best_sq = min(_dist_sq(p, s) for s in seed_positions)
        if best_sq < radius_sq:
            result[vid] = math.sqrt(best_sq)
    return result


def _geodesic_distances(
    mesh: Mesh, seeds: set[VertexId], radius: float
) -> dict[VertexId, float]:
    """Multi-source Dijkstra over the edge graph. A path is a chain of mesh edges,
    so this is an upper bound of the true surface distance (see FINDINGS)."""
    # One pass over all edges instead of `Mesh.vertex_edges()` per visited vertex:
    # that query is an O(E) scan in Core V1, which made this ~5x slower (FINDINGS).
    neighbours: dict[VertexId, list[VertexId]] = {}
    for eid in mesh.all_edge_ids():
        a, b = mesh.edge_vertices(eid)
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    dist: dict[VertexId, float] = {s: 0.0 for s in seeds}
    heap: list[tuple[float, VertexId]] = [(0.0, s) for s in seeds]
    heapq.heapify(heap)
    done: set[VertexId] = set()
    while heap:
        d, vid = heapq.heappop(heap)
        if vid in done:
            continue
        done.add(vid)
        p = mesh.vertex_position(vid)
        for other in neighbours.get(vid, ()):
            if other in done:
                continue
            nd = d + math.sqrt(_dist_sq(p, mesh.vertex_position(other)))
            if nd >= radius:
                continue  # pruned: w would be 0 there, and nothing behind it is closer
            if nd < dist.get(other, math.inf):
                dist[other] = nd
                heapq.heappush(heap, (nd, other))
    return dist


METRICS: dict[str, Callable[[Mesh, set[VertexId], float], dict[VertexId, float]]] = {
    "euclidean": _euclidean_distances,
    "geodesic": _geodesic_distances,
}


# --- Public API ---------------------------------------------------------------

def compute_influence(
    mesh: Mesh,
    seeds: Iterable[VertexId],
    radius: float,
    metric: str = "euclidean",
    curve: str = "smooth",
    curve_power: float = 1.0,
) -> dict[VertexId, float]:
    """Influence weights for all vertices within `radius` (world units) of the seeds.

    Returns `{vertex: w}` with `0 < w <= 1`; seeds always carry exactly `1.0`,
    vertices at `d >= radius` are absent. Seeds the mesh no longer knows are skipped
    (same rule as `resolve_selection_vertices`); no valid seed -> `{}`.
    `radius == 0` -> exactly the seeds, all `1.0`. `curve_power` is the `p` of the `custom`
    curve and is ignored by every other curve.
    """
    if metric not in METRICS:
        raise ValueError(f"Unknown metric {metric!r}; expected one of {sorted(METRICS)}.")
    if curve not in CURVES:
        raise ValueError(f"Unknown curve {curve!r}; expected one of {sorted(CURVES)}.")
    radius = float(radius)
    if not math.isfinite(radius) or radius < 0.0:
        raise ValueError(f"radius must be finite and >= 0, got {radius!r}.")

    valid_seeds = {s for s in seeds if mesh.is_valid_vertex(s)}
    if not valid_seeds:
        return {}
    weights: dict[VertexId, float] = {s: 1.0 for s in valid_seeds}
    if radius == 0.0:
        return weights

    shape = custom_curve(curve_power) if curve == "custom" else CURVES[curve]
    for vid, d in METRICS[metric](mesh, valid_seeds, radius).items():
        if vid in weights:
            continue
        w = shape(1.0 - d / radius)
        if w > 0.0:
            weights[vid] = w
    return weights


def primary_pivot(mesh: Mesh, seeds: Iterable[VertexId]) -> Position:
    """Centroid of the primary selection (the seeds), never of the influenced set.

    Same arithmetic as `selection_pivot` / `VertexTransformOperation._selection_center`
    (sum per axis, then divide), so a radius-0 gesture lands on the same pivot."""
    positions = [mesh.vertex_position(s) for s in seeds if mesh.is_valid_vertex(s)]
    if not positions:
        raise ValueError("primary_pivot() needs at least one valid seed.")
    count = len(positions)
    return (
        sum(p[0] for p in positions) / count,
        sum(p[1] for p in positions) / count,
        sum(p[2] for p in positions) / count,
    )
