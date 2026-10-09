"""Symmetric Face Extrude (AD-SYM-03 slice 7, WP-SYM-EXTRUDE-01; headless).

Extrude is a live gesture: the topology changes at `begin()`, the caps move on every update and one
`MeshStateCommand` is pushed at commit. So, like the Knife (`mirai.symmetric_knife`), the coordinator is a
*session* object the tool is handed at `begin` and the tool imports nothing from symmetry:

- `plan_extrude(mesh, faces) -> SymmetricExtrudePlan` runs **before any mutation** and raises
  `SymmetryRefusal` (a refused `begin()` leaves mesh and tool untouched);
- the unchanged `ExtrudeTool` extrudes the plan's `face_ids` (selection ∪ mirror partners, one operation);
- every update hands the tool's own cap positions to `plan.place(...)`, which makes the result an exact mirror
  image **by construction** (X4): the working side's positions are kept, the partner side is
  `mirror_position` of them, a vertex on the plane gets the plane coordinate exactly the plane's;
- at commit `plan.finish(...)` writes seam rule S3 and runs the completeness delta (D-strict) and raises an
  `ExtrudeRefusal` (`commit_refusal = True`, which is how the tool recognises it) — the tool then takes the
  commit back with no history entry;
- `plan.residue(...)` picks the cap faces that become the selection (engineering default, X8).

Refusals (status text; all visible, none silent):

- the plane is not exact (`TEXT_NON_EXACT_PLANE`), a selected face has no partner (`TEXT_UNPAIRED`);
- a face spanning the plane (its own mirror, `TEXT_EXTRUDE_SPANNING`) and a face that touches the plane at a
  corner the extrusion cannot mirror cleanly (`TEXT_EXTRUDE_CORNER`). **Artist statement 2026-10-09 ("Case 4"):
  refuse visibly, for now.** The statement covers the refusal only; whether the cap of such a corner should get a
  vertex of its own (one cap vertex per component and old vertex) is a Discovery finding, not decided here;
- at commit the delta (`TEXT_DELTA`).

Dependency direction: `symmetric_extrude` -> `symmetric_ops`, `symmetry_coordination`, `symmetry`,
`topology.extrude` (for the Newell normal), `core`; never `application`. `topology/extrude.py` imports nothing
from here.
"""

from __future__ import annotations

from typing import Iterable

from core import FaceId, VertexId
from core.mesh import Mesh, SymmetryDefinition

from .symmetric_ops import (
    TEXT_DELTA,
    TEXT_NON_EXACT_PLANE,
    TEXT_UNPAIRED,
    SymmetryRefusal,
    _require_definition,
    on_residue_sides,
    residue_sides,
)
from .symmetry import mirror_position
from .symmetry_coordination import (
    SymmetryIndex,
    completeness_report,
    delta_check,
    element_side,
    expand_faces,
    is_exact_plane,
    seam_after_extrude,
)
from .topology.extrude import _compute_face_normal

#: Refusal texts (visible status line, each says what happened and what to do). Engineering defaults, the
#: Artist sees them in the practical test. `TEXT_UNPAIRED`, `TEXT_DELTA` and `TEXT_NON_EXACT_PLANE` are
#: `symmetric_ops`'s.
TEXT_EXTRUDE_SPANNING = (
    "Symmetrie: Eine Fläche liegt über der Mitte (ihr eigenes Spiegelbild) — Extrude wird dort noch nicht "
    "unterstützt, nichts geändert; Flächen auf einer Seite wählen oder Symmetrie ausschalten (Shift+S)"
)
TEXT_EXTRUDE_CORNER = (
    "Symmetrie: Die Auswahl berührt die Mitte nur an einer Ecke — Extrude wird dort noch nicht "
    "unterstützt, nichts geändert; Flächen mit einer Kante auf der Mitte wählen, abseits der Mitte "
    "arbeiten oder Symmetrie ausschalten (Shift+S)"
)


class ExtrudeRefusal(SymmetryRefusal):
    """A `SymmetryRefusal` of the commit (`finish`). `commit_refusal` is how `ExtrudeTool` (which imports
    nothing from symmetry) recognises it: it takes the commit back, shows `str(exc)` and pushes no history; any
    other exception propagates. `violations` holds the delta detail (diagnostics, not shown)."""

    commit_refusal = True


class SymmetricExtrudePlan:
    """Everything a symmetric Extrude needs from the symmetry, fixed at `begin` (the mesh does not change
    before the tool's `begin`). Duck-typed for `ExtrudeTool`: `face_ids`, `reference_normal`, `place`,
    `finish`, `residue`."""

    def __init__(
        self,
        mesh: Mesh,
        definition: SymmetryDefinition,
        faces: frozenset[FaceId],
        union: frozenset[FaceId],
        index: SymmetryIndex,
        working_side: int,
        reference_normal: tuple[float, float, float],
        residue_side_set: frozenset[int],
    ) -> None:
        self.definition = definition
        self.face_ids = union
        self.faces = faces
        self.working_side = working_side
        self.reference_normal = reference_normal
        self._residue_sides = residue_side_set
        self._axis = next(i for i, n in enumerate(definition.plane_normal) if n != 0.0)
        self._before = completeness_report(mesh, index)
        self._seam_ends = {e: tuple(mesh.edge_vertices(e)) for e in definition.seam_edges if mesh.is_valid_edge(e)}
        vertices = {v for f in union for v in mesh.face_vertices(f)}
        self._side = {v: element_side(mesh, definition, (v,)) for v in vertices}
        self._partner = {v: index.vertex_partner(v) for v in vertices}

    # -- X4: exact mirroring by construction ------------------------------------------------------

    def place(self, positions: dict[VertexId, tuple]) -> dict[VertexId, tuple]:
        """`positions`: old vertex -> the tool's own cap position (`orig + normal * distance`). Returns the
        positions to use: the working side's are kept, a vertex on the plane is projected onto it (its plane
        coordinate is exactly the plane's, INV-8), the other side's is the exact mirror of its partner's.
        Nothing is computed twice and nothing is compared with a tolerance."""
        d, w, ax = self.definition, self.working_side, self._axis
        out: dict[VertexId, tuple] = {}
        for old, pos in positions.items():
            side = self._side[old]
            if side == w:
                out[old] = pos
            elif side == 0:
                p = list(pos)
                p[ax] = d.plane_point[ax]
                out[old] = tuple(p)
        for old, pos in positions.items():
            if self._side[old] == -w:
                out[old] = tuple(mirror_position(out[self._partner[old]], d.plane_point, d.plane_normal))
        return out

    # -- X6, X7: commit ---------------------------------------------------------------------------

    def finish(self, mesh: Mesh, old_to_new: dict[VertexId, VertexId]) -> None:
        """Seam rule S3 (written in this mutation, so Undo restores the old seam with the mesh), then the
        completeness delta. Raises `ExtrudeRefusal`; the caller takes the mutation back."""
        mesh.symmetry_definition = seam_after_extrude(self.definition, self._seam_ends, mesh, old_to_new)
        result = delta_check(self._before, completeness_report(mesh))
        if not result.ok:
            raise ExtrudeRefusal(TEXT_DELTA, result.violations)

    # -- X8: residue ------------------------------------------------------------------------------

    def residue(self, mesh: Mesh, new_faces: Iterable[FaceId]) -> set[FaceId]:
        """The cap faces that become the selection: those on the sides the live selection was on (a cap
        on the plane always stays). Engineering default (AD-SYM-03 §4), not an Artist decision."""
        return on_residue_sides(mesh, new_faces, self._residue_sides, mesh.face_vertices)


def _boundary_edge_count(mesh: Mesh, vertex: VertexId, union: frozenset[FaceId]) -> int:
    """Edges at `vertex` with exactly one adjacent face in `union` (the tool's boundary rule): each gets a side
    wall that contains the edge `vertex` - `vertex'`."""
    return sum(1 for e in mesh.vertex_edges(vertex) if sum(1 for f in mesh.edge_faces(e) if f in union) == 1)


def plan_extrude(mesh: Mesh, faces: Iterable[FaceId]) -> SymmetricExtrudePlan:
    """The symmetric Extrude of `faces` (selection or hovered face; one side, both, or a pair): refuse what
    cannot be mirrored, else the plan. Pure: nothing is changed. Raises `SymmetryRefusal`.

    Order: plane, unpaired, plane-spanning face, plane corner (the refusals before any mutation); the delta
    follows at commit (`SymmetricExtrudePlan.finish`)."""
    definition = _require_definition(mesh)
    if not is_exact_plane(definition):
        raise SymmetryRefusal(TEXT_NON_EXACT_PLANE)
    faces = frozenset(faces)
    index = SymmetryIndex(mesh)
    expansion = expand_faces(index, faces)
    if expansion.unpaired:
        raise SymmetryRefusal(TEXT_UNPAIRED)
    union = expansion.union
    for f in union:
        vertex_sides = {element_side(mesh, definition, (v,)) for v in mesh.face_vertices(f)}
        if index.face_partner(f) == f or {1, -1} <= vertex_sides:
            raise SymmetryRefusal(TEXT_EXTRUDE_SPANNING)

    # A vertex on the plane keeps one cap copy on the plane; the copy joins the seam only through a consumed
    # seam edge (S3). That is clean when the region's boundary passes the vertex exactly twice (a pair across a
    # seam edge) or not at all (the whole star is extruded); anything else is a corner contact.
    for v in {v for f in union for v in mesh.face_vertices(f)}:
        if element_side(mesh, definition, (v,)) == 0 and _boundary_edge_count(mesh, v, union) not in (0, 2):
            raise SymmetryRefusal(TEXT_EXTRUDE_CORNER)

    # X5: the working side is where most of the live selection is (tie -> the plane normal's side). The drag
    # distance is measured along the working side's faces only: mirrored faces would cancel it.
    sides = {f: element_side(mesh, definition, mesh.face_vertices(f)) for f in union}
    count = {1: 0, -1: 0}
    for f in faces:
        count[sides[f]] += 1
    working_side = 1 if count[1] >= count[-1] else -1
    reference = [f for f in faces if sides[f] == working_side] or [f for f in union if sides[f] == working_side]
    nx = ny = nz = 0.0
    for f in reference:
        fn = _compute_face_normal(mesh, mesh.face_vertices(f))
        nx += fn[0]; ny += fn[1]; nz += fn[2]
    length = (nx * nx + ny * ny + nz * nz) ** 0.5
    normal = (nx / length, ny / length, nz / length) if length >= 1e-12 else (0.0, 0.0, 1.0)

    return SymmetricExtrudePlan(
        mesh,
        definition,
        faces,
        union,
        index,
        working_side,
        normal,
        residue_sides(mesh, faces, mesh.face_vertices),
    )
