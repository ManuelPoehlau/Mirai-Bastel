"""Geometric validity of a chord a–b inside one face (AD-017 addendum 2026-09-30, F2).

Rule: a chord must never be created through a face in which it does not lie
entirely. `connect_vertices` splits a boundary by index only, so topology alone
cannot tell a chord that runs along the boundary (R3: zero-area child, the
shared edge ends up in four faces) or leaves a concave face (R5: flipped,
overlapping or non-simple children) from a good one.

Mode-agnostic like the rest of `topology_points`: this knows nothing about
pairing, residue or what a mode does when no face qualifies.

Predicate (in the face's best-fit plane, Newell normal — the plane
`viewport.derived.triangulate_face` projects into): the two child polygons the
chord cuts out of the boundary must each be simple (no crossing, no corner
touching a non-neighbouring edge, no spike), have an area above `AREA_EPS` of
the parent's and the parent's winding (positive in this frame). Signed child
areas always sum to the parent's, so no separate sum check is needed.
Together this means the chord lies inside the face: a chord that crosses or
touches the boundary makes one child non-simple, one that lies outside reverses
a child's winding, one along the boundary gives a child no area.

Tolerances: lengths are compared with `LENGTH_EPS` x the face's extent, child
area with `AREA_EPS` x the parent's area. Both are far below any geometry an
Artist can build, and far above float noise of the non-planar `head` quads
(whose chords are children of ~half the area).
"""

from __future__ import annotations

import math
from typing import Iterator

from core import FaceId, VertexId

LENGTH_EPS = 1e-9
AREA_EPS = 1e-9

Point3 = tuple[float, float, float]
Point2 = tuple[float, float]


def _cross2(o: Point2, a: Point2, b: Point2) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _signed_area(pts: list[Point2]) -> float:
    return 0.5 * sum(
        pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
        for i in range(len(pts))
    )


def _point_segment_dist(p: Point2, a: Point2, b: Point2) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0.0:
        return math.dist(p, a)
    s = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return math.dist(p, (a[0] + s * dx, a[1] + s * dy))


def _segments_meet(a: Point2, b: Point2, c: Point2, d: Point2, eps: float) -> bool:
    """Closed segments ab and cd cross, touch or overlap (within `eps`)."""
    if _cross2(a, b, c) * _cross2(a, b, d) < 0.0 and _cross2(c, d, a) * _cross2(c, d, b) < 0.0:
        return True  # proper crossing; touching and overlap fall through to the distance test
    return (
        _point_segment_dist(a, c, d) <= eps or _point_segment_dist(b, c, d) <= eps
        or _point_segment_dist(c, a, b) <= eps or _point_segment_dist(d, a, b) <= eps
    )


def _is_simple(pts: list[Point2], eps: float) -> bool:
    n = len(pts)
    for i in range(n):
        for j in range(i + 1, n):
            if math.dist(pts[i], pts[j]) <= eps:
                return False  # coincident corners
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        # A spike: the boundary turns straight back over itself at b.
        if abs(_cross2(a, b, c)) <= eps * max(math.dist(a, b), math.dist(b, c)) and \
                (a[0] - b[0]) * (c[0] - b[0]) + (a[1] - b[1]) * (c[1] - b[1]) > 0.0:
            return False
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if (j + 1) % n == i:
                continue  # neighbours share a corner by construction
            if _segments_meet(a, b, pts[j], pts[(j + 1) % n], eps):
                return False
    return True


def _newell(pts: list[Point3]) -> Point3:
    nx = ny = nz = 0.0
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    return nx, ny, nz


def _project(pts: list[Point3]) -> tuple[list[Point2], float] | None:
    """2D coordinates in the best-fit plane (boundary counter-clockwise) and the
    parent's area; None for a face without a plane."""
    nx, ny, nz = _newell(pts)
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    size = max(1e-12, max(hi[k] - lo[k] for k in range(3)))
    if length <= LENGTH_EPS * size * size:
        return None
    n = (nx / length, ny / length, nz / length)
    axis = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = (axis[1] * n[2] - axis[2] * n[1], axis[2] * n[0] - axis[0] * n[2], axis[0] * n[1] - axis[1] * n[0])
    ul = math.sqrt(sum(c * c for c in u))
    u = (u[0] / ul, u[1] / ul, u[2] / ul)
    v = (n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0])
    o = pts[0]
    flat = [
        (sum((p[k] - o[k]) * u[k] for k in range(3)), sum((p[k] - o[k]) * v[k] for k in range(3)))
        for p in pts
    ]
    return flat, 0.5 * length


def chord_valid_in_polygon(points: list[Point3], ia: int, ib: int) -> bool:
    """Is the chord between boundary corners `ia` and `ib` of the polygon `points`
    (boundary order) valid — see the module docstring. Adjacent or identical
    corners are never valid."""
    n = len(points)
    if ia == ib or (ib - ia) % n in (1, n - 1):
        return False
    projected = _project(points)
    if projected is None:
        return False
    flat, parent_area = projected
    eps = LENGTH_EPS * max(1e-12, max(
        max(p[k] for p in points) - min(p[k] for p in points) for k in range(3)
    ))
    lo, hi = (ia, ib) if ia < ib else (ib, ia)
    # Same split as `Mesh.connect_vertices`.
    for child in (flat[lo:hi + 1], flat[hi:] + flat[:lo + 1]):
        if _signed_area(child) <= AREA_EPS * parent_area or not _is_simple(child, eps):
            return False
    return True


def chord_valid_in_face(mesh, face: FaceId, a: VertexId, b: VertexId) -> bool:
    """Is the chord a–b valid in `face`? False when either vertex is not on it."""
    boundary = mesh.face_vertices(face)
    if a not in boundary or b not in boundary:
        return False
    return chord_valid_in_polygon(
        [mesh.vertex_position(v) for v in boundary], boundary.index(a), boundary.index(b)
    )


def chord_faces(mesh, a: VertexId, b: VertexId) -> Iterator[FaceId]:
    """Faces in which a–b is a valid chord, lowest FaceId first (deterministic)."""
    if a == b:
        return
    for fid in sorted(mesh.all_face_ids(), key=int):
        if chord_valid_in_face(mesh, fid, a, b):
            yield fid


def chord_valid_to_edge_point(mesh, face: FaceId, a: VertexId, edge, t: float) -> bool:
    """Would the chord from vertex `a` to the point `t` along `edge` be valid in `face`
    once the edge is split there? Non-mutating: the split vertex is inserted into a
    copy of the boundary the way `Mesh.split_edge` does it. False when `a` or the
    edge is not on the face."""
    v0, v1 = mesh.edge_vertices(edge)
    boundary = mesh.face_vertices(face)
    if a not in boundary or a in (v0, v1) or v0 not in boundary or v1 not in boundary:
        return False
    p0, p1 = mesh.vertex_position(v0), mesh.vertex_position(v1)
    mid = tuple(x * (1.0 - t) + y * t for x, y in zip(p0, p1))
    points: list[Point3] = []
    ia = ib = -1
    n = len(boundary)
    for i, v in enumerate(boundary):
        if v == a:
            ia = len(points)
        points.append(mesh.vertex_position(v))
        if {v, boundary[(i + 1) % n]} == {v0, v1}:
            ib = len(points)
            points.append(mid)
    if ib < 0:
        return False
    return chord_valid_in_polygon(points, ia, ib)
