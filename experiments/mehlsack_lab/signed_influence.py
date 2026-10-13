"""Signed influence map: seeds -> per-vertex weight in [-1, 1] (handoff E4, E6).

Distances come unchanged from `mirai.soft_selection.influence.METRICS` (euclidean or
geodesic, pruned at the radius); only the curve step differs from `compute_influence`:

- `w = curve(d / r)` with a lab curve on x = d/r (see `signed_curve`), which may be
  negative — `compute_influence` drops every `w <= 0`, this keeps `w < 0`;
- only `w == 0` is left out (no `abs()`, no clamp to positive);
- seeds carry exactly `1.0`, stale seeds are skipped, `radius == 0` -> the seeds only
  (the same rules as `compute_influence`).

The arithmetic per vertex is `curve(d / radius)`; with
`curve = lambda x: CURVES["smooth"](1.0 - x)` that is the same float operations as
`compute_influence`'s `shape(1.0 - d / radius)` — pinned bit for bit by
`tests/test_signed_influence.py`.

`DistanceCache` keeps the last metric result per `(seeds, radius, metric, token)`,
so a curve edit (preview or Nachführen) does not rerun Dijkstra. `token` names the
mesh state the distances were measured on; the caller changes it whenever positions
change.
"""

from __future__ import annotations

import math
from typing import Callable, Hashable, Iterable

from core import Mesh, VertexId
from mirai.soft_selection import METRICS

Curve = Callable[[float], float]


def _validated(metric: str, radius: float) -> float:
    if metric not in METRICS:
        raise ValueError(f"Unknown metric {metric!r}; expected one of {sorted(METRICS)}.")
    radius = float(radius)
    if not math.isfinite(radius) or radius < 0.0:
        raise ValueError(f"radius must be finite and >= 0, got {radius!r}.")
    return radius


def weights_from_distances(
    seeds: Iterable[VertexId], distances: dict[VertexId, float], radius: float, curve: Curve
) -> dict[VertexId, float]:
    """The curve step on its own (seeds already validated)."""
    weights: dict[VertexId, float] = {s: 1.0 for s in seeds}
    if radius == 0.0:
        return weights
    for vid, d in distances.items():
        if vid in weights:
            continue
        w = curve(d / radius)
        if w != 0.0:
            weights[vid] = w
    return weights


def signed_influence(
    mesh: Mesh,
    seeds: Iterable[VertexId],
    radius: float,
    metric: str,
    curve: Curve,
) -> dict[VertexId, float]:
    """`{vertex: w}` with `w` in [-1, 1] and `w != 0`; seeds exactly `1.0`."""
    radius = _validated(metric, radius)
    valid_seeds = {s for s in seeds if mesh.is_valid_vertex(s)}
    if not valid_seeds:
        return {}
    distances = METRICS[metric](mesh, valid_seeds, radius) if radius > 0.0 else {}
    return weights_from_distances(valid_seeds, distances, radius, curve)


class DistanceCache:
    """One-entry-per-key memo of `METRICS` results (see module docstring)."""

    def __init__(self, max_entries: int = 64) -> None:
        self.max_entries = max_entries
        self._entries: dict[tuple, dict[VertexId, float]] = {}
        #: Diagnostics/tests: metric runs vs cache hits.
        self.misses = 0
        self.hits = 0

    def distances(
        self, mesh: Mesh, seeds: frozenset, radius: float, metric: str, token: Hashable
    ) -> dict[VertexId, float]:
        key = (seeds, radius, metric, token)
        found = self._entries.get(key)
        if found is not None:
            self.hits += 1
            return found
        self.misses += 1
        found = METRICS[metric](mesh, set(seeds), radius) if radius > 0.0 else {}
        if len(self._entries) >= self.max_entries:
            self._entries.pop(next(iter(self._entries)))
        self._entries[key] = found
        return found

    def influence(
        self, mesh: Mesh, seeds: Iterable[VertexId], radius: float, metric: str, curve: Curve,
        token: Hashable,
    ) -> dict[VertexId, float]:
        """`signed_influence`, with the metric result taken from the cache when possible."""
        radius = _validated(metric, radius)
        valid_seeds = frozenset(s for s in seeds if mesh.is_valid_vertex(s))
        if not valid_seeds:
            return {}
        distances = self.distances(mesh, valid_seeds, radius, metric, token)
        return weights_from_distances(valid_seeds, distances, radius, curve)

    def clear(self) -> None:
        self._entries.clear()
