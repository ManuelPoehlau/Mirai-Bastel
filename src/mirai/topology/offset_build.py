"""Shared result of the width gestures that build their topology once and then only move the new
vertices (Inset, Bevel; 2026-10-29, `PROVISIONAL`).

`build_*` changes the topology at the start of the gesture and returns an `OffsetBuild`: every new
vertex sits at `origin + width * direction`, so a drag only rewrites positions (exact Esc, one
History entry, no drift). `keys` names each new vertex by the old elements it grew from (a tuple of
`VertexId` / `EdgeId` / `FaceId` / frozensets of them): the symmetric coordinator
(`mirai.symmetric_offset`) finds a vertex's mirror partner through them. This module imports nothing
from symmetry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from core import FaceId, Mesh, VertexId

Position = tuple[float, float, float]
Vector = tuple[float, float, float]

EPS = 1e-12


@dataclass
class OffsetBuild:
    """`moves`: new vertex -> (origin, direction per unit width). `keys`: new vertex -> its key.
    `limit`: the largest width (beyond it the new geometry would overlap). `faces`: the faces the
    selection residue is made of. `vertices`: the new vertices (= `moves`' keys, in creation order)."""

    moves: dict[VertexId, tuple[Position, Vector]]
    keys: dict[VertexId, tuple]
    limit: float
    faces: list[FaceId] = field(default_factory=list)

    @property
    def vertices(self) -> list[VertexId]:
        return list(self.moves)

    def positions(self, width: float) -> dict[VertexId, Position]:
        w = max(0.0, min(self.limit, width))
        return {
            vid: (o[0] + w * d[0], o[1] + w * d[1], o[2] + w * d[2]) for vid, (o, d) in self.moves.items()
        }


class OffsetRefused(ValueError):
    """The operation refuses before any mutation; the message is the status line."""


# -- small vector helpers ---------------------------------------------------------------------------


def sub(a, b) -> Vector:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b) -> Vector:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale(a, s: float) -> Vector:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b) -> Vector:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a) -> float:
    return math.sqrt(dot(a, a))


def unit(a) -> Vector | None:
    n = length(a)
    if n < EPS:
        return None
    return (a[0] / n, a[1] / n, a[2] / n)


def face_normal(mesh: Mesh, face: FaceId) -> Vector:
    """Newell normal of `face` (unit; +Z for a degenerate face, as Extrude)."""
    boundary = mesh.face_vertices(face)
    nx = ny = nz = 0.0
    n = len(boundary)
    for i in range(n):
        c = mesh.vertex_position(boundary[i])
        d = mesh.vertex_position(boundary[(i + 1) % n])
        nx += (c[1] - d[1]) * (c[2] + d[2])
        ny += (c[2] - d[2]) * (c[0] + d[0])
        nz += (c[0] - d[0]) * (c[1] + d[1])
    return unit((nx, ny, nz)) or (0.0, 0.0, 1.0)


def inward(normal: Vector, start: Position, end: Position) -> Vector | None:
    """The unit vector in the face plane perpendicular to the edge `start -> end`, pointing into the
    face whose winding runs `start -> end` (counter-clockwise about `normal`: the left side)."""
    d = unit(sub(end, start))
    if d is None:
        return None
    return unit(cross(normal, d))


#: Longest miter (in units of the width) at a sharp corner; beyond it the corner is cut short instead
#: of shooting far out (`PROVISIONAL`).
MITER_LIMIT = 4.0


def miter(p: Vector, q: Vector) -> Vector:
    """The direction whose distance to both edge lines (inward normals `p`, `q`) grows by 1 per unit:
    `(p + q) / (1 + p.q)`, capped at `MITER_LIMIT` (a hairpin falls back to `p`)."""
    c = 1.0 + dot(p, q)
    if c < EPS:
        return p
    m = scale(add(p, q), 1.0 / c)
    n = length(m)
    if n > MITER_LIMIT:
        m = scale(m, MITER_LIMIT / n)
    return m


def collapse_width(mesh: Mesh, directions) -> float:
    """The smallest width at which an edge at a moving vertex would shrink to zero length, each vertex
    in `directions` moving by `width * direction` from where it is now (the others stay); edges of zero
    length now (copies on their source) are skipped; inf if none shrinks."""
    pos = mesh.vertex_position
    best = float("inf")
    edges = {e for v in directions for e in mesh.vertex_edges(v)}
    for e in edges:
        a, b = mesh.edge_vertices(e)
        along = unit(sub(pos(b), pos(a)))
        if along is None:
            continue
        rate = 0.0
        if a in directions:
            rate += dot(directions[a], along)
        if b in directions:
            rate -= dot(directions[b], along)
        if rate > 1e-9:
            best = min(best, length(sub(pos(b), pos(a))) / rate)
    return best
