"""Arithmetic of the face-corner UVs (AD-026, CORE_V1_FREEZE §7.1 2026-10-29).

Core-internal helpers behind `Mesh.face_uvs` / `Mesh.set_face_uvs`: validation of a UV tuple and the
one geometric rule the Core needs for UVs, the weights of a point inside a polygon (`split_face`
interior points without a usable origin). Positions are read by the caller; nothing here knows the
Mesh.

Weights: mean value coordinates (Hormann & Floater, "Mean value coordinates for arbitrary planar
polygons", 2006) in the polygon's Newell plane - the rule AD-025 §4.1 documents for a caller that has
no triangle. Exact for a point on a corner or an edge, smooth inside, defined for concave polygons
(weights may then be negative, which is harmless for UVs).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

UV = tuple[float, float]
FaceUVs = tuple[UV, ...]
Position = tuple[float, float, float]

#: Two UVs closer than this (per component) count as the same corner value, i.e. no UV seam there.
UV_MATCH = 1e-9

_EPS = 1e-12


def uv_tuple(uvs, n: int) -> FaceUVs:
    """`uvs` as a tuple of `n` pairs of finite floats; ValueError otherwise."""
    try:
        out = tuple((float(u), float(v)) for u, v in uvs)
    except (TypeError, ValueError):
        raise ValueError(f"UVs brauchen Paare aus zwei Zahlen: {uvs!r}") from None
    if len(out) != n:
        raise ValueError(f"UVs: {len(out)} Ecken für eine Face mit {n} Ecken")
    if not all(math.isfinite(c) for uv in out for c in uv):
        raise ValueError(f"UVs müssen endlich sein: {uvs!r}")
    return out


def same_uv(a: UV, b: UV) -> bool:
    return abs(a[0] - b[0]) <= UV_MATCH and abs(a[1] - b[1]) <= UV_MATCH


def lerp_uv(a: UV, b: UV, t: float) -> UV:
    s = 1.0 - t
    return (a[0] * s + b[0] * t, a[1] * s + b[1] * t)


def mean_uv(uvs: Sequence[UV]) -> UV:
    n = len(uvs)
    return (sum(u for u, _ in uvs) / n, sum(v for _, v in uvs) / n)


def weighted_uv(weights: Sequence[float], uvs: Sequence[UV]) -> UV:
    return (sum(w * u for w, (u, _) in zip(weights, uvs)), sum(w * v for w, (_, v) in zip(weights, uvs)))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _plane_axes(points: Sequence[Position]):
    nx = ny = nz = 0.0
    m = len(points)
    for i, a in enumerate(points):
        b = points[(i + 1) % m]
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < _EPS:
        return None
    n = (nx / length, ny / length, nz / length)
    # any vector not parallel to n, then Gram-Schmidt
    helper = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    d = helper[0] * n[0] + helper[1] * n[1] + helper[2] * n[2]
    ax = (helper[0] - d * n[0], helper[1] - d * n[1], helper[2] - d * n[2])
    la = math.sqrt(ax[0] ** 2 + ax[1] ** 2 + ax[2] ** 2)
    ax = (ax[0] / la, ax[1] / la, ax[2] / la)
    ay = (n[1] * ax[2] - n[2] * ax[1], n[2] * ax[0] - n[0] * ax[2], n[0] * ax[1] - n[1] * ax[0])
    return ax, ay


def polygon_weights(points: Sequence[Position], p: Position) -> list[float]:
    """Mean value coordinates of `p` over the polygon `points` (module docstring); they sum to 1.
    A degenerate polygon gives the weight 1 to the nearest corner."""
    m = len(points)
    axes = _plane_axes(points)
    if axes is None:
        return _nearest(points, p)
    ax, ay = axes
    s = []
    for q in points:
        d = _sub(q, p)
        s.append((d[0] * ax[0] + d[1] * ax[1] + d[2] * ax[2], d[0] * ay[0] + d[1] * ay[1] + d[2] * ay[2]))
    r = [math.hypot(x, y) for x, y in s]
    scale = max(r) or 1.0
    for i in range(m):
        if r[i] <= 1e-12 * scale:
            return [1.0 if k == i else 0.0 for k in range(m)]
    area = []
    dot = []
    for i in range(m):
        a, b = s[i], s[(i + 1) % m]
        area.append(a[0] * b[1] - a[1] * b[0])
        dot.append(a[0] * b[0] + a[1] * b[1])
    for i in range(m):
        j = (i + 1) % m
        if abs(area[i]) <= 1e-12 * r[i] * r[j] and dot[i] < 0.0:
            # on the edge i -> j: linear along it
            out = [0.0] * m
            out[i] = r[j] / (r[i] + r[j])
            out[j] = r[i] / (r[i] + r[j])
            return out
    weights = []
    for i in range(m):
        w = 0.0
        h = i - 1
        if area[h] != 0.0:
            w += (r[h] - dot[h] / r[i]) / area[h]
        if area[i] != 0.0:
            w += (r[(i + 1) % m] - dot[i] / r[i]) / area[i]
        weights.append(w)
    total = sum(weights)
    if not math.isfinite(total) or abs(total) < _EPS:
        return _nearest(points, p)
    return [w / total for w in weights]


def _nearest(points: Sequence[Position], p: Position) -> list[float]:
    dist = [sum(c * c for c in _sub(q, p)) for q in points]
    k = dist.index(min(dist))
    return [1.0 if i == k else 0.0 for i in range(len(points))]
