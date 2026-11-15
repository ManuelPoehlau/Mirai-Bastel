"""Surface Slide planning from a `core.Mesh` (Phase 2 of the audit 2026-11-14, §13.2).

`plan_surface_slide` decides at the press what one gesture moves; `SlideSession` runs it: the region capture, the
growth on `FLAG_CAPTURE`, and the positions to write (driven vertices plus the exact mirrors of the passive half).
Nothing here reads a camera, a pointer or a `Selection`, and nothing writes the mesh: the gesture (Phase 3,
`controllers/gestures.py`) writes `SlideStep.positions` through the change journal. Precedent:
`topology/vertex_slide.py` (`plan_vertex_slide`, `VertexSlideRefused`, `vertex_slide_positions`).

- **Weights** come from `soft_selection.compute_influence` / `symmetric_influence` unchanged (radius 0 without Soft:
  the seeds, under symmetry the seeds and their partners), then the mask (`mask_weights` /
  `mask_symmetric_influence`: seeds keep their weight, the falloff `w x (1 - m)`); fully masked seeds are no seeds
  (`unblocked`). The caller passes the effective mask (`mask.effective_mask`, hidden vertices fully masked), as for
  W/E/R.
- **Driver rule (B3).** Under symmetry the pivot's half is driven, plus the seam; every weighted vertex of the other
  half is written as `mirror_position` of its partner, whatever K-near says (the field's categories are not used).
  A pair carries one weight (the larger of the two; the symmetric field gives both the same). A pivot on the seam
  drives the seeds' side, or the +normal side when the seeds are on both or on none (the convention of
  `symmetric_influence`).
- **Seam.** A driven seam vertex walks the declared seam chain (`EdgeChain`, its plane coordinate exactly on the
  plane, pinned again when written); one that is on no captured seam edge (its polygons on the driven side hidden)
  does not move. Driven vertices off the seam stop short of the seam barrier (E3, `tracer.back_off`); open-boundary
  rows walk their boundary (E5) and stop short of the seam and of chain ends (`EdgeChain.stop_short`).
- **Refusals** (`SurfaceSlideRefused`, the message is the status line, `PROVISIONAL`): nothing to slide, everything
  masked, a plane that is not an exact axis plane, weighted vertices without a mirror partner, a polygon straddling
  the plane at a weighted vertex, a bowtie vertex among the driven ones, a pivot that cannot move.
- **Units.** `edge_scale` (`h`) is the mean polygon edge of the polygons around the driven vertices (part of every
  capture, so region and full capture use the same `h`, §13.1 item 7). The capture starts at `CAPTURE_MARGIN` x `h`
  around the driven vertices and doubles on every `FLAG_CAPTURE` (§3.3 item 1).
- **Growth replays.** On a frame with `FLAG_CAPTURE` the session captures the grown region and replays every update
  and settle since the last exact zero drag (the pursuit carries state from frame to frame); the replay is the slide
  of the larger capture, so the result equals the full capture's bit for bit (gate G2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Mapping

from core import FaceId, Mesh, VertexId
from viewport.packed_geometry import np  # NumPy behind its pinned-version check (AD-032 §2)

from ..mask import mask_symmetric_influence, mask_weights, unblocked
from ..soft_selection import SoftSettings, SoftSymmetryRefusal, compute_influence, symmetric_influence
from ..symmetry import mirror_position
from ..symmetry_coordination import SymmetryIndex, is_exact_plane
from .capture import MeshHalf, SlideCapture, all_faces, build_capture, region_faces
from .slide import SurfaceSlide
from .tracer import FLAG_CAPTURE

Position = tuple[float, float, float]

SURFACE_SLIDE_LABEL = "Surface Slide"

#: The first capture reaches this many `h` beyond the driven vertices; it doubles on every `FLAG_CAPTURE`.
CAPTURE_MARGIN = 4.0
CAPTURE_GROWTH = 2.0


class SurfaceSlideRefused(ValueError):
    """The vertices cannot slide; the message is the status line."""


@dataclass(frozen=True)
class SlidePlan:
    """What one Surface Slide gesture moves (module docstring).

    `vertex_ids`: the driven vertices (ascending; the slide's rows), `weights` theirs, `pivot` the one the drag is
    meant for. `origins`: press position of every vertex the slide writes (driven and mirrored). `mirrors`: passive
    vertex -> its driver. `seam_vertex_ids`: driven vertices on the declared seam. `plane` / `side`: the exact plane
    and the driven half (+1 / -1), or None / 0. `hidden_faces`: polygons never captured. `edge_scale`: `h`."""

    vertex_ids: tuple[VertexId, ...]
    weights: tuple[float, ...]
    pivot: VertexId
    origins: dict[VertexId, Position]
    mirrors: dict[VertexId, VertexId]
    seam_vertex_ids: frozenset[VertexId]
    plane: tuple[Position, Position] | None
    side: int
    hidden_faces: frozenset[FaceId]
    edge_scale: float

    @property
    def pivot_index(self) -> int:
        return self.vertex_ids.index(self.pivot)

    @property
    def written_vertex_ids(self) -> frozenset[VertexId]:
        return frozenset(self.origins)

    def half(self, mesh: Mesh) -> MeshHalf:
        """The capturable part of `mesh` at the press state."""
        definition = mesh.symmetry_definition
        seam = definition.seam_edges if (definition is not None and self.plane is not None) else ()
        return MeshHalf(mesh, positions=self.origins, plane=self.plane, side=self.side,
                        hidden_faces=self.hidden_faces, seam_edges=seam)


def _side(position: Position, plane: tuple[Position, Position]) -> int:
    point, normal = plane
    d = sum((p - o) * n for p, o, n in zip(position, point, normal))
    return (d > 0.0) - (d < 0.0)


def _is_bowtie(mesh: Mesh, v: VertexId) -> bool:
    """`v` joins polygon fans that share no edge at `v` (Core edges carry <= 2 polygons, vertices may not)."""
    edges = mesh.vertex_edges(v)
    parent: dict[FaceId, FaceId] = {}

    def find(f):
        while parent[f] != f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    for e in edges:
        for f in mesh.edge_faces(e):
            parent.setdefault(f, f)
    for e in edges:
        faces = mesh.edge_faces(e)
        if len(faces) == 2:
            a, b = find(faces[0]), find(faces[1])
            if a != b:
                parent[a] = b
    return len({find(f) for f in parent}) > 1


def _default_pivot(mesh: Mesh, seeds: set[VertexId]) -> VertexId:
    """The seed nearest to the seeds' centroid (lowest id on a tie)."""
    pts = {s: mesh.vertex_position(s) for s in seeds}
    c = [sum(p[i] for p in pts.values()) / len(pts) for i in range(3)]
    return min(sorted(pts), key=lambda s: sum((pts[s][i] - c[i]) ** 2 for i in range(3)))


def plan_surface_slide(
    mesh: Mesh,
    seeds: Iterable[VertexId],
    *,
    pivot: VertexId | None = None,
    influence: SoftSettings | None = None,
    mask: Mapping[VertexId, float] | None = None,
    symmetry: SymmetryIndex | None = None,
    hidden_faces: Iterable[FaceId] = (),
) -> SlidePlan:
    """The slide of `seeds` (module docstring). `pivot`: the seed the gesture starts on (default: the seed nearest to
    the seeds' centroid). `influence`: the Soft settings (None or disabled: no falloff). `mask`: vertex -> mask value
    (the effective mask). `symmetry`: a `SymmetryIndex` of the current geometry the caller already holds.
    `hidden_faces`: the resolved hidden polygons. Raises `SurfaceSlideRefused`."""
    label = SURFACE_SLIDE_LABEL
    valid = {v for v in seeds if mesh.is_valid_vertex(v)}
    if not valid:
        raise SurfaceSlideRefused(f"{label}: select or hover a vertex")
    if pivot is not None and pivot not in valid:
        raise ValueError("pivot must be one of the seeds")
    free = unblocked(valid, mask)
    if not free or (pivot is not None and pivot not in free):
        raise SurfaceSlideRefused(f"{label}: all selected points are masked (Ctrl+M unmasks)")
    if pivot is None:
        pivot = _default_pivot(mesh, free)
    radius = influence.world_radius if (influence is not None and influence.enabled) else 0.0
    soft = influence if influence is not None else SoftSettings()

    definition = mesh.symmetry_definition
    plane = None
    side = 0
    partner_of: dict[VertexId, VertexId] = {}
    if definition is None:
        weights = compute_influence(mesh, free, radius, metric=soft.metric, curve=soft.curve,
                                    curve_power=soft.curve_power, flow_ratio=soft.flow_ratio)
        weights = mask_weights(weights, free, mask)
    else:
        if not is_exact_plane(definition):
            raise SurfaceSlideRefused(f"{label}: symmetry plane is not an exact axis plane")
        plane = (tuple(definition.plane_point), tuple(definition.plane_normal))
        index = symmetry if symmetry is not None else SymmetryIndex(mesh)
        try:
            field = symmetric_influence(mesh, free, radius, metric=soft.metric, curve=soft.curve,
                                        curve_power=soft.curve_power, flow_ratio=soft.flow_ratio)
        except SoftSymmetryRefusal as exc:
            raise SurfaceSlideRefused(f"{label}: {exc}") from exc
        weights = mask_symmetric_influence(field, mask).weights
        lonely = 0
        for v in weights:
            p = index.vertex_partner(v)
            if p is None:
                lonely += 1
            else:
                partner_of[v] = p
        if lonely:
            raise SurfaceSlideRefused(f"{label}: {lonely} vertices have no mirror partner (Shift+S)")
        side = _side(mesh.vertex_position(pivot), plane)
        if side == 0:
            sides = {_side(mesh.vertex_position(s), plane) for s in free} - {0}
            side = next(iter(sides)) if len(sides) == 1 else 1
    weights = {v: w for v, w in weights.items() if w > 0.0}

    driven: dict[VertexId, float] = {}
    mirrors: dict[VertexId, VertexId] = {}
    for v, w in weights.items():
        d = v
        if plane is not None:
            p = partner_of[v]
            if p != v and _side(mesh.vertex_position(v), plane) != side:
                d = p
                mirrors[v] = p
        driven[d] = max(driven.get(d, 0.0), w)
    if plane is not None:
        for d in driven:
            p = partner_of[d] if d in partner_of else index.vertex_partner(d)
            if p is None:   # a driver is weighted or the partner of a weighted vertex: not reached
                raise SurfaceSlideRefused(f"{label}: a vertex has no mirror partner (Shift+S)")
            if p != d:
                mirrors[p] = d

    seam_edges = definition.seam_edges if plane is not None else ()
    probe = MeshHalf(mesh, plane=plane, side=side, hidden_faces=hidden_faces, seam_edges=seam_edges)
    for v in set(driven) | set(mirrors):
        if any(probe.straddles(f) for f in probe.faces_around(v)):
            raise SurfaceSlideRefused(f"{label}: a polygon crosses the mirror plane")
    for v in sorted(driven):
        if _is_bowtie(mesh, v):
            raise SurfaceSlideRefused(f"{label}: a vertex joins two separate polygon fans (bowtie)")

    # a driven vertex moves only on its captured polygons; a seam vertex only along a captured seam edge
    for v in list(driven):
        faces = [f for f in probe.faces_around(v) if probe.eligible(f)]
        on_seam = v in probe.seam_vertices
        if not faces or (on_seam and not any(probe.eligible(f) for e, _ in probe.chain_edges(v, seam=True)
                                             for f in mesh.edge_faces(e))):
            del driven[v]
    mirrors = {w: d for w, d in mirrors.items() if d in driven}
    if pivot not in driven:
        raise SurfaceSlideRefused(f"{label}: the vertex under the cursor cannot slide")

    lengths: list[float] = []
    for f in sorted({f for v in driven for f in probe.faces_around(v) if probe.eligible(f)}):
        b = mesh.face_vertices(f)
        for i in range(len(b)):
            p, q = mesh.vertex_position(b[i]), mesh.vertex_position(b[(i + 1) % len(b)])
            lengths.append(math.sqrt((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2))
    edge_scale = math.fsum(lengths) / len(lengths)

    order = tuple(sorted(driven))
    origins = {v: mesh.vertex_position(v) for v in (*order, *mirrors)}
    return SlidePlan(
        vertex_ids=order, weights=tuple(driven[v] for v in order), pivot=pivot, origins=origins, mirrors=mirrors,
        seam_vertex_ids=frozenset(v for v in order if v in probe.seam_vertices), plane=plane, side=side,
        hidden_faces=probe.hidden_faces, edge_scale=edge_scale,
    )


@dataclass(frozen=True)
class SlideStep:
    """One frame to write. `positions`: every vertex of `SlidePlan.origins` (driven and mirrored). `flags`: per
    driven vertex (`SlidePlan.vertex_ids` order), `tracer.FLAG_*`. `lagging`: driven vertices still chasing their
    target. `captures`: captures built for this frame (0 = none; > 0 = the region grew and the drag was replayed)."""

    positions: dict[VertexId, Position]
    flags: object
    lagging: int
    captures: int = 0


class SlideSession:
    """One gesture's slide of `plan` on `mesh` (module docstring). Create it at the press, before anything is written:
    it captures from `plan.origins` and the unchanged rest of the mesh. `full_capture`: capture every eligible polygon
    at once (no region, no growth; the reference of gate G2). `margin`: the first region margin in world units
    (default `CAPTURE_MARGIN` x `h`)."""

    def __init__(self, mesh: Mesh, plan: SlidePlan, *, full_capture: bool = False,
                 margin: float | None = None) -> None:
        self.mesh = mesh
        self.plan = plan
        self._half = plan.half(mesh)
        self._margin = None if full_capture else (CAPTURE_MARGIN * plan.edge_scale if margin is None else margin)
        self._ops: list[tuple[str, object]] = []
        self.captures = 0
        self._build()

    @property
    def capture(self) -> SlideCapture:
        return self._capture

    @property
    def slide(self) -> SurfaceSlide:
        return self._slide

    def update(self, delta) -> SlideStep:
        """`delta`: the drag since the press as a world 3-vector (`SurfaceSlide.update`)."""
        delta = np.array(delta, dtype=np.float64).reshape(3)
        n = self._slide.pivot_frame[0]
        if not np.any(delta - (delta @ n) * n):
            self._ops.clear()   # the slide resets: nothing before this can matter again
        return self._run(("update", delta))

    def settle(self, max_step: float) -> SlideStep:
        return self._run(("settle", float(max_step)))

    def start_positions(self) -> dict[VertexId, Position]:
        return dict(self.plan.origins)

    # -- internals ---------------------------------------------------------------------------------------------------

    def _build(self) -> None:
        plan = self.plan
        faces = all_faces(self._half) if self._margin is None else region_faces(self._half, plan.vertex_ids,
                                                                                 self._margin)
        cap = build_capture(self._half, faces, edge_scale=plan.edge_scale, margin=self._margin)
        rows = [cap.row_of[v] for v in plan.vertex_ids]
        self._capture = cap
        self._slide = SurfaceSlide(cap.reference, rows, plan.weights, plan.pivot_index, chains=cap.chains)
        self.captures += 1

    def _apply(self, op):
        kind, arg = op
        return self._slide.update(arg) if kind == "update" else self._slide.settle(arg)

    def _run(self, op) -> SlideStep:
        self._ops.append(op)
        frame = self._apply(op)
        before = self.captures
        hit = bool(np.any(frame.flags & FLAG_CAPTURE))
        while hit and not self._capture.complete:
            self._margin *= CAPTURE_GROWTH
            self._build()
            hit = False
            for past in self._ops:      # only the last op can reach the larger border; checked for every op anyway
                frame = self._apply(past)
                hit |= bool(np.any(frame.flags & FLAG_CAPTURE))
        return self._step(frame, self.captures - before)

    def _step(self, frame, captures: int) -> SlideStep:
        plan = self.plan
        rows = frame.positions.tolist()
        out: dict[VertexId, Position] = {}
        axis = None
        if plan.plane is not None:
            axis = int(np.argmax(np.abs(np.asarray(plan.plane[1], dtype=np.float64))))
        for v, p in zip(plan.vertex_ids, rows):
            if axis is not None and v in plan.seam_vertex_ids:
                p[axis] = plan.plane[0][axis]   # exactly on the plane (no -0.0, no drift)
            out[v] = (p[0], p[1], p[2])
        if plan.plane is not None:
            point, normal = plan.plane
            for w, d in plan.mirrors.items():
                out[w] = mirror_position(out[d], point, normal)
        return SlideStep(out, frame.flags, frame.lagging, captures)
