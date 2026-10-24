"""Smooth / Relax as a pure function on positions (WP Toolbox Gaps C2, 2026-10-23).

Smooth is the Laplace step: each movable vertex moves toward the mean of its edge neighbours by
`factor`. Relax is the same step with the move projected onto the vertex's tangent plane (the normal
from its faces at the current positions), so the points spread more evenly while the surface keeps its
shape. Both are Jacobi iterations: every step reads the positions of the previous one.

`amount` is continuous so a drag can drive it: `floor(amount)` full steps, then one step with the
fractional part of the factor. Amount 0 changes nothing; the result is continuous in `amount`.

With Soft Selection the caller passes the influence as `weights`: each vertex's step is scaled by its
weight, so the effect fades out toward the edge of the radius.

Pure: no `Mesh` mutation, no History. The caller decides which vertices move (the selection without
boundary vertices, say) and writes the result inside its own transaction.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Hashable, TypeVar

V = TypeVar("V", bound=Hashable)
Vec3 = tuple[float, float, float]

#: The share of the way to the neighbour mean that one full step moves (Blender's Smooth Vertices
#: default 0.5, `PROVISIONAL`).
SMOOTH_FACTOR = 0.5


def smooth_positions(
    positions: Mapping[V, Vec3],
    neighbors: Mapping[V, Sequence[V]],
    movable: Iterable[V],
    amount: float,
    *,
    factor: float = SMOOTH_FACTOR,
    faces: Mapping[V, Sequence[Sequence[V]]] | None = None,
    constrain: Callable[[V, Vec3], Vec3] | None = None,
    weights: Mapping[V, float] | None = None,
) -> dict[V, Vec3]:
    """New positions of `movable` after `amount` steps.

    `positions` must hold every movable vertex and all their neighbours. `faces` given = Relax: per
    movable vertex the boundaries of its faces, for its normal (a vertex whose normal vanishes moves
    like Smooth). `constrain(v, p)` (optional) maps each new position, e.g. back onto a symmetry plane.
    `weights` (optional, Soft Selection) scales each vertex's step: 1 = full, 0 = stays.
    """
    if amount <= 0.0:
        return {}
    moving = [v for v in movable if neighbors.get(v)]
    current: dict[V, Vec3] = dict(positions)
    full = int(math.floor(amount))
    steps = [factor] * full
    if amount - full > 0.0:
        steps.append(factor * (amount - full))
    for step in steps:
        updated: dict[V, Vec3] = {}
        for v in moving:
            p = current[v]
            ring = neighbors[v]
            n = len(ring)
            mean = (
                sum(current[w][0] for w in ring) / n,
                sum(current[w][1] for w in ring) / n,
                sum(current[w][2] for w in ring) / n,
            )
            d = (mean[0] - p[0], mean[1] - p[1], mean[2] - p[2])
            if faces is not None:
                normal = _vertex_normal(current, faces.get(v, ()))
                if normal is not None:
                    k = d[0] * normal[0] + d[1] * normal[1] + d[2] * normal[2]
                    d = (d[0] - k * normal[0], d[1] - k * normal[1], d[2] - k * normal[2])
            s = step if weights is None else step * weights.get(v, 0.0)
            q = (p[0] + s * d[0], p[1] + s * d[1], p[2] + s * d[2])
            updated[v] = constrain(v, q) if constrain is not None else q
        current.update(updated)
    return {v: current[v] for v in moving}


def _vertex_normal(positions: Mapping[V, Vec3], faces: Sequence[Sequence[V]]) -> Vec3 | None:
    """Unit sum of the Newell normals of `faces` (area-weighted), None when it vanishes."""
    sx = sy = sz = 0.0
    for boundary in faces:
        k = len(boundary)
        for i in range(k):
            a = positions[boundary[i]]
            b = positions[boundary[(i + 1) % k]]
            sx += (a[1] - b[1]) * (a[2] + b[2])
            sy += (a[2] - b[2]) * (a[0] + b[0])
            sz += (a[0] - b[0]) * (a[1] + b[1])
    length = math.sqrt(sx * sx + sy * sy + sz * sz)
    if length < 1e-12:
        return None
    return (sx / length, sy / length, sz / length)
