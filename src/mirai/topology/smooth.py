"""Smooth / Relax on a component selection (WP Toolbox Gaps C2, `docs/WP_TOOLBOX_GAPS_PLAN.md`).

`plan_smooth` is taken at the press of S / Alt+S: the vertices that move (the resolved selection
without boundary vertices, which stay fixed), their neighbours and start positions, and - with a
symmetry definition - the mirror side. `SmoothPlan.positions(amount)` always computes from that start
state (`core.operations.smooth.smooth_positions`), so a drag can go back and forth without drift.

Symmetry (like Loop Slide): the selection plus its partners smooth together; a seam vertex stays on
the plane in every step, and each partner is written as the exact mirror of the driving vertex at the
end, so the pairs stay exact. Unpaired selected vertices or an inexact plane are refused at the press.

Soft Selection: the caller passes the influence of the selection (`weights`); every vertex inside the radius
smooths too, its step scaled by its weight. Border vertices stay fixed in the soft region as well.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core import VertexId
from core.mesh import Mesh, Position
from core.operations.smooth import smooth_positions

from ..symmetry import mirror_position
from ..symmetry_coordination import SymmetryIndex, element_side, is_exact_plane

SMOOTH_LABEL = "Smooth"
RELAX_LABEL = "Relax"

#: One tap (press and release without motion) = this many full steps (`PROVISIONAL`).
TAP_AMOUNT = 2.0
#: Horizontal pointer pixels per full step while held (right = more, left = less, down to 0).
PX_PER_STEP = 60.0


class SmoothRefused(ValueError):
    """Smooth / Relax cannot start; `str(exc)` is the status text. Nothing changed."""


@dataclass
class SmoothPlan:
    relax: bool
    #: The vertices the Laplace steps drive (selection, partners too, without boundary vertices).
    movable: frozenset[VertexId]
    start: dict[VertexId, Position]
    neighbors: dict[VertexId, list[VertexId]]
    faces: dict[VertexId, list[list[VertexId]]] | None
    #: Symmetry: partner -> driving vertex (written as its exact mirror); seam vertices stay on the plane.
    mirrors: dict[VertexId, VertexId] = field(default_factory=dict)
    seam: frozenset[VertexId] = frozenset()
    plane: tuple[Position, Position] | None = None
    #: Soft Selection: the influence per movable vertex (None = Soft off, every step full).
    weights: dict[VertexId, float] | None = None

    @property
    def label(self) -> str:
        return RELAX_LABEL if self.relax else SMOOTH_LABEL

    def positions(self, amount: float) -> dict[VertexId, Position]:
        """Every movable vertex at `amount` steps from the start (its start position at 0)."""
        constrain = None
        if self.plane is not None and self.seam:
            point, normal = self.plane
            seam = self.seam

            def constrain(v: VertexId, p: Position) -> Position:
                if v not in seam:
                    return p
                d = sum((a - o) * n for a, o, n in zip(p, point, normal))
                return (p[0] - d * normal[0], p[1] - d * normal[1], p[2] - d * normal[2])

        moved = smooth_positions(
            self.start, self.neighbors, self.movable, amount, faces=self.faces, constrain=constrain,
            weights=self.weights,
        )
        result = {v: moved.get(v, self.start[v]) for v in self.movable}
        if self.plane is not None:
            point, normal = self.plane
            for written, driver in self.mirrors.items():
                result[written] = mirror_position(result[driver], point, normal)
        return result


def _is_boundary(mesh: Mesh, vid: VertexId) -> bool:
    edges = mesh.vertex_edges(vid)
    return not edges or any(len(mesh.edge_faces(e)) < 2 for e in edges)


def plan_smooth(mesh: Mesh, vertex_ids, *, relax: bool, weights=None) -> SmoothPlan:
    """`vertex_ids` = the selection (the Soft seeds). `weights` (Soft on) = the influence of the seeds,
    computed by the caller with the same function as W/E/R (plain or symmetric field): every vertex with a
    weight > 0 smooths, scaled by it; the field is already both-sided under symmetry."""
    label = RELAX_LABEL if relax else SMOOTH_LABEL
    selected = set(vertex_ids)
    if not selected:
        raise SmoothRefused(f"{label}: nothing selected")

    definition = mesh.symmetry_definition
    index = None
    if definition is not None:
        if not is_exact_plane(definition):
            raise SmoothRefused(f"{label}: symmetry plane is not an exact axis plane")
        index = SymmetryIndex(mesh)
        partners = {}
        for v in selected:
            partner = index.vertex_partner(v)
            if partner is None:
                raise SmoothRefused(f"{label}: a selected point has no mirror partner (Shift+S)")
            partners[v] = partner
        selected |= set(partners.values())

    if weights is not None:
        selected |= {v for v, w in weights.items() if w > 0.0}
    movable = frozenset(v for v in selected if not _is_boundary(mesh, v))
    if not movable:
        raise SmoothRefused(f"{label}: only border points selected - they stay fixed")

    neighbors: dict[VertexId, list[VertexId]] = {}
    for v in movable:
        ring = []
        for e in mesh.vertex_edges(v):
            a, b = mesh.edge_vertices(e)
            ring.append(b if a == v else a)
        neighbors[v] = sorted(ring, key=int)
    involved = set(movable).union(*neighbors.values())
    faces = None
    if relax:
        faces = {}
        for v in movable:
            around = sorted({f for e in mesh.vertex_edges(v) for f in mesh.edge_faces(e)}, key=int)
            faces[v] = [mesh.face_vertices(f) for f in around]
            for boundary in faces[v]:
                involved.update(boundary)
    start = {v: mesh.vertex_position(v) for v in involved}

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
    plan_weights = None if weights is None else {v: float(weights.get(v, 0.0)) for v in movable}
    return SmoothPlan(relax, movable, start, neighbors, faces, mirrors, frozenset(seam), plane, plan_weights)
