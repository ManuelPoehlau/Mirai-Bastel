"""Symmetric Inset and Bevel (2026-10-29, `PROVISIONAL`; the AD-SYM-03 pattern of Extrude, slice 7).

Inset and Bevel are width gestures: the topology is built once when the drag starts, then only the new
vertices move (`mirai.topology.offset_build`). As for Extrude the coordinator is a session object:

- `plan_inset` / `plan_bevel` run **before any mutation**: they expand the selection by its partners
  (one operation on the union, M-a style 1) and refuse what cannot be mirrored (`SymmetryRefusal`);
- every drag step hands the new positions to `place`, which makes them exact mirror images by
  construction: of a vertex and its partner (found through the build's keys) the one on the normal's
  side drives and the other is written as `mirror_position` of it; a vertex that is its own partner is
  projected onto the plane;
- at commit `finish` maintains the seam (surviving seam edges stay; every created edge with both ends
  exactly on the plane joins it, as the wall and cap edges of S3 do) and runs the completeness delta
  (D-strict); a `SymmetryRefusal` there takes the whole gesture back;
- `residue` keeps the new faces / elements on the sides the live selection was on.

Refusals (status text): the plane is not exact, a selected element has no partner, a selected face spans
the plane (Inset), and at commit the delta. Dependency direction: -> `symmetric_ops`,
`symmetry_coordination`, `symmetry`, `core`; never `application`; the topology modules import nothing
from here.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from core import EdgeId, FaceId, SelectionMode, VertexId
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
    expand_edges,
    expand_faces,
    expand_vertices,
    is_exact_plane,
)

TEXT_BEVEL_ON_PLANE = (
    "Symmetrie: Bevel einer Kante oder eines Punkts auf der Mitte wird noch nicht unterstützt, nichts geändert; "
    "abseits der Mitte arbeiten oder Symmetrie ausschalten (Shift+S)"
)
TEXT_OFFSET_SPANNING = (
    "Symmetrie: Eine Fläche liegt über der Mitte (ihr eigenes Spiegelbild) — dort noch nicht unterstützt, "
    "nichts geändert; Flächen auf einer Seite wählen oder Symmetrie ausschalten (Shift+S)"
)


class OffsetSymmetryRefusal(SymmetryRefusal):
    """A refusal of `finish` (the delta): the gesture is taken back, no History entry."""

    commit_refusal = True


class SymmetricOffset:
    """What a symmetric width gesture needs from the symmetry, fixed before the mutation."""

    def __init__(self, mesh: Mesh, index: SymmetryIndex, residue_side_set: frozenset[int]) -> None:
        self.definition = _require_definition(mesh)
        self._before = completeness_report(mesh, index)
        self._residue_sides = residue_side_set
        # The keys name old elements, many of which the build removes: their partners are read now (one table
        # per kind - the ids are ints, VertexId(3) == FaceId(3)).
        self._partners: dict[type, dict] = {
            VertexId: {v: index.vertex_partner(v) for v in mesh.all_vertex_ids()},
            EdgeId: {e: index.edge_partner(e) for e in mesh.all_edge_ids()},
            FaceId: {f: index.face_partner(f) for f in mesh.all_face_ids()},
        }

    # -- partners of keys (old elements) ----------------------------------------------------------

    def _partner(self, element):
        for kind, partners in self._partners.items():
            if isinstance(element, kind):
                return partners.get(element)
        if isinstance(element, frozenset):
            image = frozenset(self._partner(e) for e in element)
            return None if None in image else image
        if isinstance(element, tuple):
            image = tuple(self._partner(e) for e in element)
            return None if None in image else image
        return element

    def _signed(self, position) -> float:
        d = self.definition
        return sum((p - o) * n for p, o, n in zip(position, d.plane_point, d.plane_normal))

    # -- exact mirroring by construction ----------------------------------------------------------

    def place(self, keys: Mapping[VertexId, tuple], positions: Mapping[VertexId, tuple]) -> dict:
        """The positions to write: per mirror pair of new vertices the normal's side drives, the other is
        its exact mirror; a vertex that is its own partner lies exactly on the plane."""
        d = self.definition
        by_key = {key: vid for vid, key in keys.items()}
        out = dict(positions)
        done: set[VertexId] = set()
        for vid in sorted(positions):
            if vid in done or vid not in keys:
                continue
            partner = by_key.get(self._partner(keys[vid]))
            if partner is None or partner not in positions:
                continue  # the delta check judges an image that is not there
            done.update((vid, partner))
            if partner == vid:
                p = out[vid]
                s = self._signed(p)
                out[vid] = tuple(c - s * n for c, n in zip(p, d.plane_normal))
                continue
            driver, image = (vid, partner) if self._signed(out[vid]) >= self._signed(out[partner]) else (partner, vid)
            out[image] = tuple(mirror_position(out[driver], d.plane_point, d.plane_normal))
        return out

    # -- commit -----------------------------------------------------------------------------------

    def finish(self, mesh: Mesh, change) -> None:
        """Seam and delta inside the still active recording `change` (Undo restores the old seam with the
        mesh). Raises `OffsetSymmetryRefusal`; the caller rolls the gesture back."""
        d = mesh.symmetry_definition
        seam = {e for e in d.seam_edges if mesh.is_valid_edge(e)}
        for e, record in change.edges.items():
            if record is not None or not mesh.is_valid_edge(e):
                continue
            a, b = mesh.edge_vertices(e)
            if self._signed(mesh.vertex_position(a)) == 0.0 and self._signed(mesh.vertex_position(b)) == 0.0:
                seam.add(e)
        mesh.symmetry_definition = SymmetryDefinition(d.plane_point, d.plane_normal, frozenset(seam))
        result = delta_check(self._before, completeness_report(mesh))
        if not result.ok:
            raise OffsetSymmetryRefusal(TEXT_DELTA, result.violations)

    def residue(self, mesh: Mesh, created: Iterable, vertices_of) -> set:
        return on_residue_sides(mesh, created, self._residue_sides, vertices_of)


def _start(mesh: Mesh) -> tuple[SymmetryDefinition, SymmetryIndex]:
    definition = _require_definition(mesh)
    if not is_exact_plane(definition):
        raise SymmetryRefusal(TEXT_NON_EXACT_PLANE)
    return definition, SymmetryIndex(mesh)


def plan_inset(mesh: Mesh, faces: Iterable[FaceId]) -> tuple[frozenset[FaceId], SymmetricOffset]:
    """The union the Inset runs on (selection plus partners) and its coordinator. Pure."""
    definition, index = _start(mesh)
    faces = frozenset(faces)
    expansion = expand_faces(index, faces)
    if expansion.unpaired:
        raise SymmetryRefusal(TEXT_UNPAIRED)
    union = expansion.union
    for f in union:
        sides = {element_side(mesh, definition, (v,)) for v in mesh.face_vertices(f)}
        if index.face_partner(f) == f or {1, -1} <= sides:
            raise SymmetryRefusal(TEXT_OFFSET_SPANNING)
    return union, SymmetricOffset(mesh, index, residue_sides(mesh, faces, mesh.face_vertices))


def plan_bevel(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> tuple[frozenset, SymmetricOffset]:
    """The union the Bevel runs on (the vertices / edges of `mode`, plus partners) and its coordinator.
    Face mode bevels the faces' edges (the caller passes them as edges). A vertex or edge on the plane is
    refused (its strip or cap would span the plane). Pure."""
    _, index = _start(mesh)
    ids = frozenset(ids)
    if mode is SelectionMode.VERTEX:
        expansion = expand_vertices(index, ids)
        vertices_of = lambda v: (v,)  # noqa: E731
    else:
        expansion = expand_edges(index, ids)
        vertices_of = mesh.edge_vertices
    if expansion.unpaired:
        raise SymmetryRefusal(TEXT_UNPAIRED)
    partner = index.vertex_partner if mode is SelectionMode.VERTEX else index.edge_partner
    if any(partner(element) == element for element in expansion.union):
        raise SymmetryRefusal(TEXT_BEVEL_ON_PLANE)
    return expansion.union, SymmetricOffset(mesh, index, residue_sides(mesh, ids, vertices_of))
