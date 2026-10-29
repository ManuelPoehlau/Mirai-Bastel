"""Loop Slide (AP-05; promoted 2026-10-15, Manu: "die Playground-Werkzeuge in Production
einbauen"). Hold `G` in the app: the selected edge loop(s) slide along their side edges.

Pure planning + position math; `Application` owns the gesture, the History entry and the
viewport (same split as the Knife/Extrude: no camera, no history here).

Differences to the Playground's `LoopSlideTool` (`playground/topology_tools/loop_slide.py`,
left as it is, closed loops only):
- open loop pieces slide too (each vertex needs a quad on both sides of its loop edges);
- several disjoint loops slide together, by the same amount;
- with a symmetry definition the mirror side follows exactly (`plan.mirrors`): a loop and its
  mirror loop, or one loop that crosses the plane, end up as exact mirrors. A seam vertex whose
  slide would leave the plane refuses the slide (it would break the seam, INV-8).

Engineering choices (`PROVISIONAL`): `t` in [-1, 1], positive towards side A of the first loop
edge's first face; the gesture maps the pointer onto that direction (see `Application`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core import EdgeId, Mesh, VertexId

from ..symmetry import mirror_position
from ..symmetry_coordination import SymmetryIndex, is_exact_plane

Position = tuple[float, float, float]

LOOP_SLIDE_LABEL = "Loop Slide"

#: Under a symmetry definition the slide stops short of the next loop (2026-10-29): sliding all the way puts two
#: vertices on one position, which makes the position-based mirror pairing ambiguous (`PROVISIONAL`).
SYMMETRIC_MAX_T = 0.98


class LoopSlideRefused(ValueError):
    """The edges cannot slide; the message is the status line."""


@dataclass(frozen=True)
class SlidePlan:
    """What one slide gesture moves.

    `slides`: driven vertex -> (original, target on side A, target on side B).
    `mirrors`: vertex written as the mirror of a driven vertex -> that driven vertex
    (empty without a symmetry definition)."""

    slides: dict[VertexId, tuple[Position, Position, Position]]
    mirrors: dict[VertexId, VertexId] = field(default_factory=dict)
    plane: Optional[tuple[Position, Position]] = None

    @property
    def max_t(self) -> float:
        return 1.0 if self.plane is None else SYMMETRIC_MAX_T

    @property
    def vertex_ids(self) -> set[VertexId]:
        return set(self.slides) | set(self.mirrors)


def _components(mesh: Mesh, edges: set[EdgeId]) -> list[tuple[VertexId, list[EdgeId]]]:
    """Connected pieces of `edges` as (start vertex, edges ordered from it along the path or
    cycle)."""
    by_vertex: dict[VertexId, list[EdgeId]] = {}
    for eid in edges:
        for vid in mesh.edge_vertices(eid):
            by_vertex.setdefault(vid, []).append(eid)
    if any(len(incident) > 2 for incident in by_vertex.values()):
        raise LoopSlideRefused("Loop Slide: the selected edges branch - select edge loops")

    remaining = set(edges)
    pieces: list[tuple[VertexId, list[EdgeId]]] = []
    while remaining:
        seed = min(remaining)
        # Walk to one end first (a cycle has none: the walk stops where it began).
        edge, vertex = seed, mesh.edge_vertices(seed)[0]
        visited = {seed}
        while True:
            others = [e for e in by_vertex[vertex] if e != edge]
            if not others or others[0] in visited:
                break
            edge = others[0]
            visited.add(edge)
            a, b = mesh.edge_vertices(edge)
            vertex = b if a == vertex else a
        ordered = _walk_from(mesh, by_vertex, edge, vertex)
        remaining.difference_update(ordered)
        pieces.append((vertex, ordered))
    return pieces


def _walk_from(mesh, by_vertex, first_edge: EdgeId, from_vertex: VertexId) -> list[EdgeId]:
    """Edges in order, starting with `first_edge` leaving `from_vertex`."""
    ordered = [first_edge]
    seen = {first_edge}
    edge, vertex = first_edge, from_vertex
    while True:
        a, b = mesh.edge_vertices(edge)
        vertex = b if a == vertex else a
        nxt = [e for e in by_vertex[vertex] if e != edge and e not in seen]
        if not nxt:
            return ordered
        edge = nxt[0]
        seen.add(edge)
        ordered.append(edge)


def _neighbour_in_face(mesh: Mesh, face, vertex: VertexId, other: VertexId) -> VertexId:
    """The quad corner next to `vertex` that is not `other` (the slide target on that side)."""
    corners = mesh.face_vertices(face)
    i = corners.index(vertex)
    before, after = corners[i - 1], corners[(i + 1) % 4]
    return before if after == other else after


def _piece_targets(
    mesh: Mesh, start: VertexId, piece: list[EdgeId]
) -> dict[VertexId, tuple[VertexId, VertexId]]:
    """Per vertex of one ordered piece: (target on side A, target on side B)."""
    targets: dict[VertexId, tuple[VertexId, VertexId]] = {}
    vertex = start
    for index, edge in enumerate(piece):
        a, b = mesh.edge_vertices(edge)
        nxt = b if a == vertex else a
        edge_faces = mesh.edge_faces(edge)
        if len(edge_faces) != 2:
            raise LoopSlideRefused(
                "Loop Slide: a loop edge lies on the border (needs faces on both sides)"
            )
        if index == 0:
            side_a, side_b = edge_faces
        else:
            # The side-A face of this edge is the one containing the side-A target of `vertex`
            # (regular valence 4: the slide edge separates the two A faces).
            target_a, target_b = targets[vertex]
            with_a = [f for f in edge_faces if target_a in mesh.face_vertices(f)]
            with_b = [f for f in edge_faces if target_b in mesh.face_vertices(f)]
            if len(with_a) != 1 or len(with_b) != 1 or with_a[0] == with_b[0]:
                raise LoopSlideRefused(
                    "Loop Slide: irregular vertex on the loop (needs four edges per loop vertex)"
                )
            side_a, side_b = with_a[0], with_b[0]
        for face in (side_a, side_b):
            if len(mesh.face_vertices(face)) != 4:
                raise LoopSlideRefused("Loop Slide: needs quads on both sides of the loop")
        for v, other in ((vertex, nxt), (nxt, vertex)):
            pair = (
                _neighbour_in_face(mesh, side_a, v, other),
                _neighbour_in_face(mesh, side_b, v, other),
            )
            known = targets.get(v)
            if known is not None and known != pair:
                raise LoopSlideRefused(
                    "Loop Slide: irregular vertex on the loop (needs four edges per loop vertex)"
                )
            targets[v] = pair
        vertex = nxt
    return targets


def plan_loop_slide(mesh: Mesh, edge_ids) -> SlidePlan:
    """The slide of `edge_ids` (one or more loop pieces). Raises `LoopSlideRefused`."""
    edges = {e for e in edge_ids if mesh.is_valid_edge(e)}
    if not edges:
        raise LoopSlideRefused("Loop Slide: select an edge loop (edge mode)")

    definition = mesh.symmetry_definition
    index: SymmetryIndex | None = None
    if definition is not None:
        if not is_exact_plane(definition):
            raise LoopSlideRefused("Loop Slide: symmetry plane is not an exact axis plane")
        index = SymmetryIndex(mesh)
        # A piece and its mirror piece slide as one: only one of them is driven.
        expanded = set(edges)
        for eid in edges:
            partner = index.edge_partner(eid)
            if partner is None:
                raise LoopSlideRefused("Loop Slide: a loop edge has no mirror partner (Shift+S)")
            expanded.add(partner)
        edges = expanded

    pieces = _components(mesh, edges)
    driven_pieces: list[tuple[VertexId, list[EdgeId]]] = []
    covered: set[EdgeId] = set()
    for start, piece in pieces:
        if covered.intersection(piece):
            continue
        driven_pieces.append((start, piece))
        covered.update(piece)
        if index is not None:
            covered.update(index.edge_partner(e) for e in piece)

    slides: dict[VertexId, tuple[Position, Position, Position]] = {}
    for start, piece in driven_pieces:
        for vid, (ta, tb) in _piece_targets(mesh, start, piece).items():
            slides[vid] = (mesh.vertex_position(vid), mesh.vertex_position(ta), mesh.vertex_position(tb))

    mirrors: dict[VertexId, VertexId] = {}
    plane = None
    if index is not None:
        plane = (definition.plane_point, definition.plane_normal)
        for vid in sorted(slides):
            partner = index.vertex_partner(vid)
            if partner is None:
                raise LoopSlideRefused("Loop Slide: a loop vertex has no mirror partner (Shift+S)")
            if partner == vid:
                _, ta, tb = slides[vid]
                if _signed(ta, plane) != 0.0 or _signed(tb, plane) != 0.0:
                    raise LoopSlideRefused(
                        "Loop Slide: a seam vertex would leave the mirror plane"
                    )
                continue
            if partner in slides and _signed(slides[vid][0], plane) < 0.0:
                continue  # the partner (positive side) drives this one
            mirrors[partner] = vid
        for written in mirrors:
            slides.pop(written, None)
    return SlidePlan(slides=slides, mirrors=mirrors, plane=plane)


def _signed(position: Position, plane: tuple[Position, Position]) -> float:
    point, normal = plane
    return sum((p - o) * n for p, o, n in zip(position, point, normal))


def slide_positions(plan: SlidePlan, t: float) -> dict[VertexId, Position]:
    """New positions for `t` in [-max_t, max_t] (clamped): positive towards side A, negative towards B."""
    t = max(-plan.max_t, min(plan.max_t, t))
    result: dict[VertexId, Position] = {}
    for vid, (orig, ta, tb) in plan.slides.items():
        target, f = (ta, t) if t >= 0.0 else (tb, -t)
        result[vid] = tuple(o + f * (g - o) for o, g in zip(orig, target))
    if plan.plane is not None:
        point, normal = plan.plane
        for written, driver in plan.mirrors.items():
            result[written] = mirror_position(result[driver], point, normal)
    return result
