"""Geometry of one face in its own plane — small, mode-agnostic helpers (AD-017 §11 shape).

Moved here from the Knife Face Lab (`playground/experiments/knife_face/engine.py`, WP-KNIFE-01 S1) so
there is one implementation of the face frame: the Knife's commit-time resolver (`knife_resolve`) and
F2's chord predicate (`chord_validity`) both project a face through `FaceFrame` — the Newell plane
`viewport.derived.triangulate_face` projects into, the boundary counter-clockwise (u x v = normal).

Knows nothing about modes, selection, history or a camera. Pure functions of positions / a mesh read.

Two simplicity tests exist on purpose (WP-KNIFE-01 S1, recorded in
`playground/experiments/knife_face/decision.md`, "One Knife S1 — open points"): `polygon_is_simple`
here (the Knife resolver's: a crossing counts only when both ends lie more than `eps` off the other
segment's line; a corner within `eps` of another edge's line *and* bounding box touches it) and
`chord_validity._is_simple` (F2's: any sign-change crossing, or a corner within `eps` *distance* of
another edge). They agree away from the `eps` band; inside it they can differ, so neither was picked
silently — they stay separate until a result an Artist can see is shown identical.
"""

from __future__ import annotations

import math

from core import FaceId
from core.mesh import MeshError

Position = tuple[float, float, float]

# Lengths closer than this (relative to the face's size) are one point.
GEO_EPS = 1e-9


def v_sub(p, q):
    return (p[0] - q[0], p[1] - q[1], p[2] - q[2])


def v_dot(p, q):
    return p[0] * q[0] + p[1] * q[1] + p[2] * q[2]


def v_cross(p, q):
    return (p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0])


def v_len(p) -> float:
    return math.sqrt(v_dot(p, p))


def dist3(p, q) -> float:
    return math.sqrt(sum((p[k] - q[k]) ** 2 for k in range(3)))


def cross2(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def newell(points: list[Position]) -> Position:
    """Newell normal (unnormalised; its length is twice the projected area) of a polygon."""
    nx = ny = nz = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    return (nx, ny, nz)


def loop_matches_winding(loop_positions: list[Position], boundary_positions: list[Position]) -> bool:
    """True if the loop, in the given order, winds like the parent face's boundary (its Newell
    normal points to the same side). A degenerate loop (no area, e.g. a bow-tie) has no winding
    of its own and counts as matching — it is left as clicked."""
    nl, nb = newell(loop_positions), newell(boundary_positions)
    return sum(nl[k] * nb[k] for k in range(3)) >= 0.0


class FaceFrame:
    """One face in its own Newell plane: 2D coordinates in which the boundary runs
    counter-clockwise (u x v = the face normal), the unit normal and a length scale.
    Raises MeshError for a face without area (no plane to work in)."""

    def __init__(self, mesh, face_id: FaceId):
        self.face_id = face_id
        self.boundary = mesh.face_vertices(face_id)
        self._build([mesh.vertex_position(v) for v in self.boundary], face_id)

    @classmethod
    def of_points(cls, points: list[Position]) -> FaceFrame:
        """The frame of a polygon given by its corner positions (boundary order) — no mesh face."""
        frame = cls.__new__(cls)
        frame.face_id = None
        frame.boundary = None
        frame._build(list(points), "polygon")
        return frame

    def _build(self, pts: list[Position], name) -> None:
        n = newell(pts)
        length = v_len(n)
        lo = [min(p[k] for p in pts) for k in range(3)]
        hi = [max(p[k] for p in pts) for k in range(3)]
        self.size = max(1e-12, max(hi[k] - lo[k] for k in range(3)))
        if length <= GEO_EPS * self.size * self.size:
            raise MeshError(f"face {name!r} has no area")
        self.normal = (n[0] / length, n[1] / length, n[2] / length)
        self.area = 0.5 * length
        axis = (1.0, 0.0, 0.0) if abs(self.normal[0]) < 0.9 else (0.0, 1.0, 0.0)
        u = v_cross(axis, self.normal)
        lu = v_len(u)
        self.u = (u[0] / lu, u[1] / lu, u[2] / lu)
        self.v = v_cross(self.normal, self.u)
        self.origin = pts[0]
        self.pts2 = [self.p2(p) for p in pts]
        self.eps = GEO_EPS * self.size

    def p2(self, p: Position) -> tuple[float, float]:
        d = v_sub(p, self.origin)
        return (v_dot(d, self.u), v_dot(d, self.v))

    def height(self, p: Position) -> float:
        return abs(v_dot(v_sub(p, self.origin), self.normal))


def proper_cross2(a, b, c, d, eps: float) -> bool:
    """Segments ab and cd cross at one point strictly inside both: each end of one lies more
    than `eps` (a distance) off the other's line, on opposite sides."""
    lab, lcd = math.dist(a, b), math.dist(c, d)
    if lab <= eps or lcd <= eps:
        return False
    o1, o2 = cross2(a, b, c) / lab, cross2(a, b, d) / lab
    o3, o4 = cross2(c, d, a) / lcd, cross2(c, d, b) / lcd
    return ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and \
           ((o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps))


def polygon_is_simple(pts2: list, eps: float) -> bool:
    """No two boundary edges meet except neighbours at their shared corner, and the
    boundary never turns straight back on itself (a spike) — no two corners coincide either."""
    n = len(pts2)
    for i in range(n):
        for j in range(i + 1, n):
            if math.dist(pts2[i], pts2[j]) <= eps:
                return False
    for i in range(n):
        a, b, c = pts2[i - 1], pts2[i], pts2[(i + 1) % n]
        if abs(cross2(a, b, c)) <= eps * max(math.dist(a, b), math.dist(b, c)) and \
                (a[0] - b[0]) * (c[0] - b[0]) + (a[1] - b[1]) * (c[1] - b[1]) > 0.0:
            return False
    for i in range(n):
        a, b = pts2[i], pts2[(i + 1) % n]
        for j in range(i + 2, n):
            if (j + 1) % n == i:
                continue
            c, d = pts2[j], pts2[(j + 1) % n]
            if proper_cross2(a, b, c, d, eps):
                return False
            # A corner lying on another (non-neighbouring) edge: the boundary touches itself.
            for p, (s, t) in ((a, (c, d)), (b, (c, d)), (c, (a, b)), (d, (a, b))):
                if abs(cross2(s, t, p)) <= eps * math.dist(s, t) and \
                        min(s[0], t[0]) - eps <= p[0] <= max(s[0], t[0]) + eps and \
                        min(s[1], t[1]) - eps <= p[1] <= max(s[1], t[1]) + eps:
                    return False
    return True


def face_problem(mesh, face_id: FaceId) -> str | None:
    """Why a face is geometrically broken ("have no area", "cross itself"), or None."""
    try:
        fr = FaceFrame(mesh, face_id)
    except MeshError:
        return "have no area"
    if not polygon_is_simple(fr.pts2, fr.eps):
        return "cross itself"
    return None


def segment_in_face(mesh, face_id: FaceId, p: Position, q: Position) -> str:
    """Where the straight segment p-q (both on or in the face) lies: "inside" (it may touch the
    boundary only at its own ends), "boundary" (it runs along the boundary) or "outside" (it
    leaves the face or passes through a corner — a concave face)."""
    try:
        fr = FaceFrame(mesh, face_id)
    except MeshError:
        return "outside"
    a2, b2 = fr.p2(p), fr.p2(q)
    m2 = (0.5 * (a2[0] + b2[0]), 0.5 * (a2[1] + b2[1]))
    k = len(fr.pts2)
    inside = False
    for j in range(k):
        c, d = fr.pts2[j], fr.pts2[(j + 1) % k]
        e_len = math.dist(c, d)
        if e_len > 0.0 and abs(cross2(c, d, m2)) <= fr.eps * e_len and \
                min(c[0], d[0]) - fr.eps <= m2[0] <= max(c[0], d[0]) + fr.eps and \
                min(c[1], d[1]) - fr.eps <= m2[1] <= max(c[1], d[1]) + fr.eps:
            return "boundary"
        if (c[1] > m2[1]) != (d[1] > m2[1]) and c[0] + (m2[1] - c[1]) * (d[0] - c[0]) / (d[1] - c[1]) > m2[0]:
            inside = not inside
    if not inside:
        return "outside"
    seg = math.dist(a2, b2)
    for j in range(k):
        c, d = fr.pts2[j], fr.pts2[(j + 1) % k]
        if proper_cross2(a2, b2, c, d, fr.eps):
            return "outside"
        if min(math.dist(c, a2), math.dist(c, b2)) > fr.eps and seg > 0.0 and \
                abs(cross2(a2, b2, c)) <= fr.eps * seg and \
                0.0 < (c[0] - a2[0]) * (b2[0] - a2[0]) + (c[1] - a2[1]) * (b2[1] - a2[1]) < seg * seg:
            return "outside"  # passes through a corner
    return "inside"
