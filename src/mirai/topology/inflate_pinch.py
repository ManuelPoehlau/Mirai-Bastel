"""Inflate / Pinch on a component selection (2026-11-15, `PROVISIONAL`).

Two localized deformations in the Smooth / Relax family (`mirai.topology.smooth`): no brush system and no topology
change. The press plans (`plan_inflate` / `plan_pinch`) on the selection (else the hovered element) = the Soft seeds:
which vertices move and, per vertex, one displacement vector `offset` in the press geometry. `DeformPlan.positions`
is then `start + amount * offset` - always from the press state, linear in the drag amount, so a drag can go back
and forth without drift, amount 0 is the press state bit for bit, and a motion costs one pass over the moving
vertices (no topology query, no normal, no field recomputed per motion).

**Weights.** Exactly those of Smooth / Relax: with Soft on, the influence of the seeds by the same function and
arguments as a Soft W/E/R (`GestureController.smooth_soft_weights`: plain or symmetric field, curve, metric, Loop /
Ring flow balance); with Soft off the selection (and its mirror partners) with weight 1. Mask Geometry: a fully
masked vertex stays, a partial mask scales its weight. Every offset carries its weight, so the falloff curve shapes
the deformation and the influence boundary is as smooth as the curve (C1 with `smooth`); nothing outside the field
moves. Border vertices move too (unlike Smooth, neither tool shrinks an open border).

**Inflate.** `offset = w * n`: the unit vertex normal of the press geometry (area-weighted Newell normals of the
vertex's faces). Amount in world units, positive outwards, negative inwards. On a sphere a full-weight region stays
spherical (every point moves radially by the same amount).

**Pinch.** Pulls the influenced vertices together; amount = the share of the way to the target (`PINCH_MAX` at most,
1 would collapse them onto it), negative pushes apart. Three directions (`PINCH_DIRECTIONS`):

- `radial` - towards the influence centre: the centroid of the seeds (`primary_pivot`), under symmetry the
  symmetric W/E/R default pivot of the seeds, mirrored for the other side (`symmetric_default_pivot`). The pull is
  projected onto the vertex's tangent plane, so a curved surface is not dented or flattened by the chord.
- `loop` - across the edge loops onto the selected line: each vertex moves along its local **ring** edge direction
  until it would reach the line through its nearest seed in the local **loop** direction (a crease or lip line gets
  tighter; lips, eyelids, wrinkles).
- `ring` - along the edge loops towards the selection: each vertex moves along its local **loop** edge direction
  towards the line through its nearest seed in the local ring direction (the loops bunch up at the selection).

Loop and ring are the families of `soft_selection.flow` (AD-020 "Loop / Ring flow"), not world or screen axes: in a
quad, opposite edges share a family; the family the seed region extends along is Loop - an edge-loop selection's own
edges are Loop, an edge-ring selection's own edges are Ring, as `edge_loop` / `edge_ring` traverse them. The local
direction at a vertex is the sign-aligned mean of its labelled edges of that family; with only one family labelled
there, the other is its perpendicular in the tangent plane. The move is the oblique decomposition of `target - p` on
(moving, other) direction, clamped to `|target - p|`, so a skewed quad grid is followed along its real edges. The
nearest seed is found over the edges of the influenced region (geodesic; a vertex no edge path reaches takes the
nearest seed in space). Vertices with no labelled edge (inside triangle / n-gon regions, behind a pole where two
label fronts meet) do not move. Refusals: no seed region with a direction (one vertex, a single quad, scattered
points: the flow rule), and Soft off (the selection is the line itself, nothing else would move).

**Symmetry** (as Smooth / Loop Slide): exact axis plane only; every seed needs a partner; selection and partners
deform together, the field is the symmetric one; each pair is written as the exact mirror of its driving member (the
one on the plane normal's side), a seam vertex is projected onto the plane in every frame.

Pure apart from reading the mesh: no mutation, no History; the gesture (`controllers.gestures.DeformGesture`) writes
the positions inside its journal.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

from core import EdgeId, VertexId
from core.mesh import Mesh, Position

from ..interaction.tools.selection_helpers import symmetric_default_pivot
from ..soft_selection import LOOP, RING, flow_families_within, primary_pivot
from ..symmetry import mirror_position
from ..symmetry_coordination import SymmetryIndex, element_side, is_exact_plane

INFLATE_LABEL = "Inflate"
PINCH_LABEL = "Pinch"

PINCH_RADIAL = "radial"
PINCH_LOOP = "loop"
PINCH_RING = "ring"
#: The Pinch directions in cycle order; the first is the default (`PROVISIONAL`).
PINCH_DIRECTIONS: tuple[str, ...] = (PINCH_RADIAL, PINCH_LOOP, PINCH_RING)

#: `PROVISIONAL`: the strongest pull (share of the way to the target). 1 would put full-weight vertices exactly on the
#: target - zero-length edges.
PINCH_MAX = 0.9
#: `PROVISIONAL`: the strongest push apart (the vertex moves its distance to the target away from it).
PINCH_MIN = -1.0
#: `PROVISIONAL`: horizontal pointer pixels for a Pinch amount of 1.
PINCH_PX_PER_UNIT = 300.0

Vec3 = tuple[float, float, float]


class DeformRefused(ValueError):
    """Inflate / Pinch cannot start; `str(exc)` is the status text. Nothing changed."""


@dataclass
class DeformPlan:
    label: str
    #: Every vertex the gesture writes (selection, partners, the Soft field - without fully masked ones).
    movable: frozenset[VertexId]
    start: dict[VertexId, Position]
    #: The displacement at amount 1, for every movable vertex that is not a written mirror (weights folded in).
    offsets: dict[VertexId, Vec3]
    #: Symmetry: partner -> driving vertex (written as its exact mirror); seam vertices stay on the plane.
    mirrors: dict[VertexId, VertexId] = field(default_factory=dict)
    seam: frozenset[VertexId] = frozenset()
    plane: tuple[Position, Position] | None = None
    #: Soft Selection: the influence per movable vertex, for the display (None = Soft off).
    weights: dict[VertexId, float] | None = None
    low: float = -math.inf
    high: float = math.inf

    def clamp(self, amount: float) -> float:
        return min(self.high, max(self.low, amount))

    def positions(self, amount: float) -> dict[VertexId, Position]:
        """Every movable vertex at `amount` (clamped to the plan's range); the start positions at 0."""
        a = self.clamp(amount)
        if a == 0.0:
            return {v: self.start[v] for v in self.movable}
        result: dict[VertexId, Position] = {}
        for v, o in self.offsets.items():
            p = self.start[v]
            result[v] = (p[0] + a * o[0], p[1] + a * o[1], p[2] + a * o[2])
        if self.plane is not None:
            point, normal = self.plane
            for v in self.seam:
                q = result[v]
                d = sum((c - o) * n for c, o, n in zip(q, point, normal))
                result[v] = (q[0] - d * normal[0], q[1] - d * normal[1], q[2] - d * normal[2])
            for written, driver in self.mirrors.items():
                result[written] = mirror_position(result[driver], point, normal)
        return result


# --- the shared region (as `plan_smooth`) -------------------------------------------------------------------


@dataclass
class _Region:
    seeds: set[VertexId]
    partners: set[VertexId]
    movable: frozenset[VertexId]
    weight: dict[VertexId, float]
    mirrors: dict[VertexId, VertexId]
    seam: frozenset[VertexId]
    plane: tuple[Position, Position] | None
    index: SymmetryIndex | None

    @property
    def driving(self) -> list[VertexId]:
        """The vertices whose offset is computed (the others are written mirrors), in id order."""
        return sorted((v for v in self.movable if v not in self.mirrors), key=int)


def _region(mesh: Mesh, vertex_ids, label: str, weights, mask) -> _Region:
    seeds = {v for v in vertex_ids if mesh.is_valid_vertex(v)}
    if not seeds:
        raise DeformRefused(f"{label}: nothing selected")
    definition = mesh.symmetry_definition
    index = None
    partners: set[VertexId] = set()
    if definition is not None:
        if not is_exact_plane(definition):
            raise DeformRefused(f"{label}: symmetry plane is not an exact axis plane")
        index = SymmetryIndex(mesh)
        for v in seeds:
            partner = index.vertex_partner(v)
            if partner is None:
                raise DeformRefused(f"{label}: a selected point has no mirror partner (Shift+S)")
            partners.add(partner)

    explicit = seeds | partners
    weight = {v: 1.0 for v in explicit}
    if weights is not None:
        for v, w in weights.items():
            if w > 0.0 and v not in weight and mesh.is_valid_vertex(v):
                weight[v] = float(w)
    if mask:
        weight = {v: w * (1.0 - mask.get(v, 0.0)) for v, w in weight.items()}
        weight = {v: w for v, w in weight.items() if w > 0.0}
        if not weight:
            raise DeformRefused(f"{label}: all selected points are masked")
    movable = frozenset(weight)

    mirrors: dict[VertexId, VertexId] = {}
    seam: set[VertexId] = set()
    plane = None
    if index is not None:
        plane = (definition.plane_point, definition.plane_normal)
        for v in sorted(movable, key=int):
            partner = index.vertex_partner(v)
            if partner == v:
                seam.add(v)
            elif partner is not None and partner in movable and v not in mirrors and partner not in mirrors:
                driver, written = (v, partner) if element_side(mesh, definition, [v]) >= 0 else (partner, v)
                mirrors[written] = driver
    return _Region(seeds, partners, movable, weight, mirrors, frozenset(seam), plane, index)


def _plan(region: _Region, mesh: Mesh, label: str, offsets, soft: bool, low: float, high: float) -> DeformPlan:
    start = {v: mesh.vertex_position(v) for v in region.movable}
    return DeformPlan(
        label=label,
        movable=region.movable,
        start=start,
        offsets=offsets,
        mirrors=region.mirrors,
        seam=region.seam,
        plane=region.plane,
        weights=dict(region.weight) if soft else None,
        low=low,
        high=high,
    )


# --- small vector helpers ------------------------------------------------------------------------------------


def _sub(a: Position, b: Position) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _scaled(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _unit(a: Vec3) -> Vec3 | None:
    length = math.sqrt(_dot(a, a))
    return None if length < 1e-12 else (a[0] / length, a[1] / length, a[2] / length)


def _tangential(a: Vec3, normal: Vec3 | None) -> Vec3:
    if normal is None:
        return a
    k = _dot(a, normal)
    return (a[0] - k * normal[0], a[1] - k * normal[1], a[2] - k * normal[2])


class _Normals:
    """Area-weighted vertex normals of the press geometry, each face's Newell normal computed once."""

    def __init__(self, mesh: Mesh) -> None:
        self.mesh = mesh
        self._face: dict = {}

    def _face_normal(self, face) -> Vec3:
        found = self._face.get(face)
        if found is None:
            mesh = self.mesh
            corners = [mesh.vertex_position(v) for v in mesh.face_vertices(face)]
            sx = sy = sz = 0.0
            k = len(corners)
            for i in range(k):
                a, b = corners[i], corners[(i + 1) % k]
                sx += (a[1] - b[1]) * (a[2] + b[2])
                sy += (a[2] - b[2]) * (a[0] + b[0])
                sz += (a[0] - b[0]) * (a[1] + b[1])
            found = self._face[face] = (sx, sy, sz)  # twice the area, not normalised: area weighting
        return found

    def vertex(self, vid: VertexId) -> Vec3 | None:
        mesh = self.mesh
        faces = {f for e in mesh.vertex_edges(vid) for f in mesh.edge_faces(e)}
        sx = sy = sz = 0.0
        for f in sorted(faces, key=int):
            n = self._face_normal(f)
            sx, sy, sz = sx + n[0], sy + n[1], sz + n[2]
        return _unit((sx, sy, sz))


# --- Inflate ------------------------------------------------------------------------------------------------


def plan_inflate(mesh: Mesh, vertex_ids, *, weights=None, mask=None) -> DeformPlan:
    """`vertex_ids` = the selection (the Soft seeds); `weights` / `mask` as `plan_smooth`. Amount = world units
    along the press normals (module docstring)."""
    region = _region(mesh, vertex_ids, INFLATE_LABEL, weights, mask)
    normals = _Normals(mesh)
    offsets: dict[VertexId, Vec3] = {}
    for v in region.driving:
        n = normals.vertex(v)
        offsets[v] = (0.0, 0.0, 0.0) if n is None else _scaled(n, region.weight[v])
    return _plan(region, mesh, INFLATE_LABEL, offsets, weights is not None, -math.inf, math.inf)


# --- Pinch --------------------------------------------------------------------------------------------------


def pinch_label(direction: str) -> str:
    return f"{PINCH_LABEL} ({direction})"


def plan_pinch(mesh: Mesh, vertex_ids, direction: str = PINCH_RADIAL, *, weights=None, mask=None) -> DeformPlan:
    """`direction` one of `PINCH_DIRECTIONS`; `vertex_ids` / `weights` / `mask` as `plan_inflate`. Amount = the
    share of the way to the target, clamped to [`PINCH_MIN`, `PINCH_MAX`] (module docstring)."""
    if direction not in PINCH_DIRECTIONS:
        raise ValueError(f"Unknown pinch direction {direction!r}; expected one of {PINCH_DIRECTIONS}.")
    label = pinch_label(direction)
    if direction != PINCH_RADIAL and weights is None:
        raise DeformRefused(
            f"{label}: switch Soft Selection on (O) - the selection is the line the falloff is pulled onto"
        )
    region = _region(mesh, vertex_ids, label, weights, mask)
    normals = _Normals(mesh)
    if direction == PINCH_RADIAL:
        offsets = _radial_offsets(mesh, region, normals)
    else:
        offsets = _directional_offsets(mesh, region, normals, direction, label)
    return _plan(region, mesh, label, offsets, weights is not None, PINCH_MIN, PINCH_MAX)


def _radial_offsets(mesh: Mesh, region: _Region, normals: _Normals) -> dict[VertexId, Vec3]:
    if region.index is None:
        centre = primary_pivot(mesh, region.seeds)
        centres = None
    else:
        point, normal = region.plane
        seam_seeds = {s for s in region.seeds if region.index.vertex_partner(s) == s}
        symmetry = {"seam_vertex_ids": seam_seeds, "plane_point": point, "plane_normal": normal}
        centre = symmetric_default_pivot(mesh, region.seeds, region.seeds | region.partners, symmetry)
        side = _side(centre, point, normal)
        # The pivot for the side it lies on, its mirror for the other (on the plane: the same point for both).
        centres = {side: centre, -side: mirror_position(centre, point, normal)} if side else None
    offsets: dict[VertexId, Vec3] = {}
    for v in region.driving:
        p = mesh.vertex_position(v)
        target = centre
        if centres is not None:
            target = centres.get(_side(p, *region.plane), centre)
        pull = _tangential(_sub(target, p), normals.vertex(v))
        offsets[v] = _scaled(pull, region.weight[v])
    return offsets


def _side(p: Position, point: Position, normal: Position) -> int:
    d = sum((c - o) * n for c, o, n in zip(p, point, normal))
    return (d > 0.0) - (d < 0.0)


def _directional_offsets(
    mesh: Mesh, region: _Region, normals: _Normals, direction: str, label: str
) -> dict[VertexId, Vec3]:
    sources = region.seeds | region.partners
    labels = flow_families_within(mesh, sources, region.movable)
    if not labels:
        raise DeformRefused(
            f"{label}: no loop/ring direction here - select an edge, an edge loop or a strip of faces"
        )
    nearest = nearest_sources(mesh, sources, region.movable)
    moving_family = RING if direction == PINCH_LOOP else LOOP
    offsets: dict[VertexId, Vec3] = {}
    for v in region.driving:
        p = mesh.vertex_position(v)
        d = _sub(mesh.vertex_position(nearest[v]), p)
        reach = math.sqrt(_dot(d, d))
        if reach == 0.0:
            offsets[v] = (0.0, 0.0, 0.0)
            continue
        loop_dir, ring_dir = family_directions(mesh, v, labels)
        n = normals.vertex(v)
        if n is not None:
            if loop_dir is None and ring_dir is not None:
                loop_dir = _unit(_cross(n, ring_dir))
            elif ring_dir is None and loop_dir is not None:
                ring_dir = _unit(_cross(n, loop_dir))
        moving, other = (ring_dir, loop_dir) if moving_family == RING else (loop_dir, ring_dir)
        if moving is None:
            offsets[v] = (0.0, 0.0, 0.0)  # no labelled edge here: no topological direction to move along
            continue
        a = _dot(d, moving)
        alpha = a
        if other is not None:
            c = _dot(moving, other)
            det = 1.0 - c * c
            if det > 1e-6:
                alpha = (a - c * _dot(d, other)) / det  # oblique: along `moving` onto the line along `other`
        alpha = max(-reach, min(reach, alpha))
        offsets[v] = _scaled(moving, alpha * region.weight[v])
    return offsets


def family_directions(
    mesh: Mesh, vid: VertexId, labels: dict[EdgeId, int]
) -> tuple[Vec3 | None, Vec3 | None]:
    """`(loop, ring)`: the unit, sign-aligned mean direction of `vid`'s labelled edges of each family (None if it
    has none). Sign-aligned to the family's first edge (by id), so two opposite edges add up instead of cancelling."""
    p = mesh.vertex_position(vid)
    sums: list[Vec3 | None] = [None, None]
    for eid in sorted(mesh.vertex_edges(vid), key=int):
        family = labels.get(eid)
        if family is None:
            continue
        a, b = mesh.edge_vertices(eid)
        e = _unit(_sub(mesh.vertex_position(b if a == vid else a), p))
        if e is None:
            continue
        total = sums[family]
        if total is None:
            sums[family] = e
        else:
            if _dot(e, total) < 0.0:
                e = _scaled(e, -1.0)
            sums[family] = (total[0] + e[0], total[1] + e[1], total[2] + e[2])
    loop_sum, ring_sum = sums[LOOP], sums[RING]
    return (
        None if loop_sum is None else _unit(loop_sum),
        None if ring_sum is None else _unit(ring_sum),
    )


def nearest_sources(mesh: Mesh, sources, region) -> dict[VertexId, VertexId]:
    """Every vertex of `region` -> its nearest source over the edges inside `region` (multi-source Dijkstra, ties to
    the smaller source id); a vertex no such path reaches takes the nearest source in space."""
    allowed = set(region) | set(sources)
    best: dict[VertexId, tuple[float, VertexId]] = {s: (0.0, s) for s in sources}
    heap = [(0.0, s, s) for s in sorted(sources)]
    heapq.heapify(heap)
    done: set[VertexId] = set()
    while heap:
        d, vid, src = heapq.heappop(heap)
        if vid in done:
            continue
        done.add(vid)
        p = mesh.vertex_position(vid)
        for eid in mesh.vertex_edges(vid):
            a, b = mesh.edge_vertices(eid)
            other = b if a == vid else a
            if other in done or other not in allowed:
                continue
            q = mesh.vertex_position(other)
            nd = d + math.sqrt(_dot(_sub(q, p), _sub(q, p)))
            if (nd, src) < best.get(other, (math.inf, src)):
                best[other] = (nd, src)
                heapq.heappush(heap, (nd, other, src))
    result = {v: best[v][1] for v in region if v in best}
    missing = [v for v in region if v not in result]
    if missing:
        positions = [(s, mesh.vertex_position(s)) for s in sorted(sources)]
        for v in missing:
            p = mesh.vertex_position(v)
            result[v] = min(positions, key=lambda item: _dot(_sub(item[1], p), _sub(item[1], p)))[0]
    return result
