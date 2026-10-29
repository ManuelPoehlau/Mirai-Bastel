"""Vertex Slide (2026-10-29, Manu: "Slide (Vertices)", Grundfunktion; `PROVISIONAL`).

Hold `G` in vertex mode: every selected vertex slides along one of its own edges towards that
neighbour (Blender Shift+V, Maya Slide Vertex). `G` in edge mode stays Loop Slide
(`mirai.topology.loop_slide`); the two share the key, the mode decides.

Pure planning + position math, as Loop Slide: `Application` owns the gesture, picks per vertex
the edge whose screen direction best matches the drag (`best_neighbour`) and maps the drag onto
a common amount `t` in [0, 1] (0 = where the vertex was, 1 = on the neighbour). Positions are
always computed from the press state, so going back to the start restores it exactly.

Symmetry (like Loop Slide): the selection plus its partners slide together; the vertices on the
normal's side (and on the plane) are driven, their partners are written as exact mirrors. A
vertex on the plane only slides along edges that stay in the plane (else the seam would break,
INV-8); with none it refuses at the press. The slide stops at `SYMMETRIC_MAX_AMOUNT` of the way.

Mask: a fully masked vertex does not move (as with W/E/R), a partly masked one slides the
fraction `1 - m` of the way. Hidden neighbours are no slide targets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from core import Mesh, VertexId

from ..symmetry import mirror_position
from ..symmetry_coordination import SymmetryIndex, is_exact_plane

Position = tuple[float, float, float]

VERTEX_SLIDE_LABEL = "Vertex Slide"

#: Under a symmetry definition the slide stops short of the neighbour: two vertices on one position would
#: make the position-based mirror pairing ambiguous (`PROVISIONAL`).
SYMMETRIC_MAX_AMOUNT = 0.98


class VertexSlideRefused(ValueError):
    """The vertices cannot slide; the message is the status line."""


@dataclass(frozen=True)
class VertexSlidePlan:
    """What one Vertex Slide gesture moves.

    `origins`: driven vertex -> its press position. `candidates`: driven vertex -> the neighbours
    it may slide to, with their press positions. `gains`: driven vertex -> the fraction of `t` it
    follows (1 - mask). `mirrors`: vertex written as the mirror of a driven vertex -> that vertex."""

    origins: dict[VertexId, Position]
    candidates: dict[VertexId, tuple[tuple[VertexId, Position], ...]]
    gains: dict[VertexId, float]
    mirrors: dict[VertexId, VertexId] = field(default_factory=dict)
    plane: Optional[tuple[Position, Position]] = None
    max_amount: float = 1.0

    @property
    def vertex_ids(self) -> set[VertexId]:
        return set(self.origins) | set(self.mirrors)


def _signed(position: Position, plane: tuple[Position, Position]) -> float:
    point, normal = plane
    return sum((p - o) * n for p, o, n in zip(position, point, normal))


def _neighbours(mesh: Mesh, vid: VertexId) -> list[VertexId]:
    out = []
    for eid in mesh.vertex_edges(vid):
        a, b = mesh.edge_vertices(eid)
        out.append(b if a == vid else a)
    return out


def plan_vertex_slide(
    mesh: Mesh,
    vertex_ids,
    *,
    blocked: frozenset[VertexId] = frozenset(),
    mask: Mapping[VertexId, float] | None = None,
) -> VertexSlidePlan:
    """The slide of `vertex_ids`. `blocked`: vertices that are no target (hidden); `mask`: vertex ->
    mask value in [0, 1]. Raises `VertexSlideRefused`."""
    vertices = {v for v in vertex_ids if mesh.is_valid_vertex(v)}
    if not vertices:
        raise VertexSlideRefused(f"{VERTEX_SLIDE_LABEL}: select or hover a vertex")
    mask = mask or {}

    definition = mesh.symmetry_definition
    index: SymmetryIndex | None = None
    plane = None
    if definition is not None:
        if not is_exact_plane(definition):
            raise VertexSlideRefused(f"{VERTEX_SLIDE_LABEL}: symmetry plane is not an exact axis plane")
        index = SymmetryIndex(mesh)
        plane = (definition.plane_point, definition.plane_normal)
        expanded = set(vertices)
        for vid in vertices:
            partner = index.vertex_partner(vid)
            if partner is None:
                raise VertexSlideRefused(f"{VERTEX_SLIDE_LABEL}: a vertex has no mirror partner (Shift+S)")
            expanded.add(partner)
        vertices = expanded

    origins: dict[VertexId, Position] = {}
    candidates: dict[VertexId, tuple[tuple[VertexId, Position], ...]] = {}
    gains: dict[VertexId, float] = {}
    mirrors: dict[VertexId, VertexId] = {}
    masked = 0
    for vid in sorted(vertices):
        position = mesh.vertex_position(vid)
        if index is not None:
            partner = index.vertex_partner(vid)
            if partner != vid and _signed(position, plane) < 0.0:
                mirrors[vid] = partner  # the partner (normal's side) drives this one
                continue
        gain = 1.0 - max(0.0, min(1.0, float(mask.get(vid, 0.0))))
        if gain <= 0.0:
            masked += 1
            continue
        targets = [n for n in _neighbours(mesh, vid) if n not in blocked]
        if index is not None and index.vertex_partner(vid) == vid:
            targets = [n for n in targets if _signed(mesh.vertex_position(n), plane) == 0.0]
            if not targets:
                raise VertexSlideRefused(
                    f"{VERTEX_SLIDE_LABEL}: a vertex on the mirror plane can only slide along the seam"
                )
        if not targets:
            continue
        origins[vid] = position
        candidates[vid] = tuple((n, mesh.vertex_position(n)) for n in targets)
        gains[vid] = gain
    mirrors = {w: d for w, d in mirrors.items() if d in origins}
    if not origins:
        if masked:
            raise VertexSlideRefused(f"{VERTEX_SLIDE_LABEL}: all selected points are masked (Ctrl+M unmasks)")
        raise VertexSlideRefused(f"{VERTEX_SLIDE_LABEL}: the selected vertices have no edge to slide along")
    return VertexSlidePlan(
        origins=origins, candidates=candidates, gains=gains, mirrors=mirrors, plane=plane,
        max_amount=1.0 if plane is None else SYMMETRIC_MAX_AMOUNT,
    )


def best_neighbour(origin_px, candidates_px, drag) -> int | None:
    """Index of the candidate whose screen vector (`candidates_px[i] - origin_px`) points most along
    `drag` (largest cosine); None if no candidate has a usable screen vector."""
    best, best_cos = None, None
    dlen = (drag[0] ** 2 + drag[1] ** 2) ** 0.5
    if dlen == 0.0 or origin_px is None:
        return None
    for i, px in enumerate(candidates_px):
        if px is None:
            continue
        sx, sy = px[0] - origin_px[0], px[1] - origin_px[1]
        slen = (sx * sx + sy * sy) ** 0.5
        if slen < 1e-9:
            continue
        cos = (sx * drag[0] + sy * drag[1]) / (slen * dlen)
        if best_cos is None or cos > best_cos:
            best, best_cos = i, cos
    return best


def vertex_slide_positions(
    plan: VertexSlidePlan, chosen: Mapping[VertexId, VertexId], t: float
) -> dict[VertexId, Position]:
    """New positions for amount `t` (clamped to [0, `plan.max_amount`]) along the `chosen` neighbour of each
    driven vertex (driven vertex -> neighbour; a driven vertex without a choice stays at its origin)."""
    t = max(0.0, min(plan.max_amount, t))
    result: dict[VertexId, Position] = {}
    for vid, origin in plan.origins.items():
        target = None
        neighbour = chosen.get(vid)
        if neighbour is not None:
            for n, position in plan.candidates[vid]:
                if n == neighbour:
                    target = position
                    break
        if target is None:
            result[vid] = origin
            continue
        f = t * plan.gains[vid]
        result[vid] = tuple(o + f * (g - o) for o, g in zip(origin, target))
    if plan.plane is not None:
        point, normal = plan.plane
        for vid, origin in plan.origins.items():
            if chosen.get(vid) is not None and _signed(origin, plan.plane) == 0.0:
                # Seam vertex along an in-plane edge: pin the plane coordinate exactly (no rounding drift).
                p = result[vid]
                distance = _signed(p, plan.plane)
                result[vid] = tuple(c - distance * n for c, n in zip(p, normal))
        for written, driver in plan.mirrors.items():
            result[written] = mirror_position(result[driver], point, normal)
    return result
