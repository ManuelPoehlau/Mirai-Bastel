"""Influence map: primary selection -> per-vertex weight in (0, 1] (WP-SOFT-01 S1).

`docs/architecture/V1_CORE.md` §6: Soft Selection is not a selection mode and not a
vertex type. It is a *derived* map from the primary selection that feeds an
operation. Handoff decisions this module encodes:

- E2: the map is transient. The caller computes it right before `begin()` from the
  current (= start) positions and hands it to the operation; nothing here is stored,
  nothing is written into `Selection`.
- E3: `w = 1` on seeds, `w = 0` at `d >= r` (vertices with `w = 0` are simply absent
  from the returned dict). Seeds come from `resolve_selection_vertices()` (V/E/F).
- E4: metrics `euclidean` (min straight-line distance to any seed) and `geodesic`
  (multi-source Dijkstra over mesh edges, edge length as cost, pruned at `r`).
- E5: curves `smooth` (smoothstep on `t = 1 - d/r`) and `linear` (`t`).

The metric/curve registries (`METRICS`, `CURVES`) are the "replaceable strategy"
seam V1_CORE §6 asks for - deliberately just dicts of functions, no class hierarchy.
Choosing a default is out of scope for this slice (handoff §4).
"""

from __future__ import annotations

import heapq
import math
from typing import Callable, Iterable

from core import Mesh, Selection, SelectionMode, VertexId
from mirai.interaction.tools.selection_helpers import resolve_selection_vertices

Position = tuple[float, float, float]


# --- Curves: t in [0, 1] (1 at the seed, 0 at the radius) -> weight ---------------

def _smooth(t: float) -> float:
    # Smoothstep keeps the influence boundary C1 (no slope jump at d = r); same
    # reasoning as the articulation precedent `_falloff_weight` (read, not imported).
    return t * t * (3.0 - 2.0 * t)


def _linear(t: float) -> float:
    return t


CURVES: dict[str, Callable[[float], float]] = {
    "smooth": _smooth,
    "linear": _linear,
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
) -> dict[VertexId, float]:
    """Influence weights for all vertices within `radius` of the seeds.

    Returns `{vertex: w}` with `0 < w <= 1`; seeds always carry exactly `1.0`,
    vertices at `d >= radius` are absent. Seeds the mesh no longer knows are skipped
    (same rule as `resolve_selection_vertices`); no valid seed -> `{}`.
    `radius == 0` -> exactly the seeds, all `1.0`.
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

    shape = CURVES[curve]
    for vid, d in METRICS[metric](mesh, valid_seeds, radius).items():
        if vid in weights:
            continue
        w = shape(1.0 - d / radius)
        if w > 0.0:
            weights[vid] = w
    return weights


def seeds_from_selection(
    mesh: Mesh, selection: Selection, mode: SelectionMode | None = None
) -> set[VertexId]:
    """E3: the seeds are exactly what the plain transform tools would move."""
    return resolve_selection_vertices(mesh, selection, selection.mode if mode is None else mode)


def primary_pivot(mesh: Mesh, seeds: Iterable[VertexId]) -> Position:
    """E7: centroid of the primary selection (the seeds), never of the influenced set.

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
