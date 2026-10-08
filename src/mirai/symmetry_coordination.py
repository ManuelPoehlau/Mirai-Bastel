"""Symmetric topology coordination — shared services (AD-SYM-03 §3 item 2, Slice 1).

Pure, stateless helpers above Core that the per-operation coordinators (later slices) build on:
partner resolution for edges and faces, selection canonicalisation and expansion, the exact-plane
predicate, seam rule S1, the completeness report and its delta check.

Nothing here is wired into `Application` or a tool yet, and nothing mutates a mesh. Like
`mirai.symmetry` this module derives everything from `mesh.symmetry_definition` plus the current
mesh on every call (AR-1, INV-3): no cache, no stored table, no tolerance. Callers that already
hold an index for the *current* geometry may pass it on; that it matches the geometry is their
guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from core.ids import EdgeId, FaceId, VertexId
from core.mesh import Mesh, Position, SymmetryDefinition

from .symmetry import CorrespondenceState, vertex_correspondence


def is_exact_plane(definition: SymmetryDefinition) -> bool:
    """True for a +-unit axis normal through a plane point with a zero axis coordinate.

    Only there is `mirror_position` an exact negation of one coordinate, so t=0.5 midpoints of
    mirrored edges are bit-identical mirrors (AD-SYM-03 §2.4, probe G, R4). Everywhere else a
    coordinator must refuse rather than produce pairs the tolerance-free correspondence may not
    confirm.
    """
    normal = definition.plane_normal
    axes = [i for i, n in enumerate(normal) if n != 0.0]
    if len(axes) != 1 or abs(normal[axes[0]]) != 1.0:
        return False
    return definition.plane_point[axes[0]] == 0.0


class SymmetryIndex:
    """Vertex / edge / face partners of one mesh state (indexed, not scanned per query).

    A seam vertex is its own partner; so is a seam edge. A face is its own partner when its vertex
    set is closed under the partner map (a plane-spanning face). Elements without a partner
    (unpaired or ambiguous vertices, or an image that is no element) resolve to `None`.
    """

    def __init__(self, mesh: Mesh) -> None:
        self.mesh = mesh
        self.definition = mesh.symmetry_definition
        self._vertex_partner: dict[VertexId, VertexId | None] = {}
        for vid, corr in vertex_correspondence(mesh).items():
            if corr.state is CorrespondenceState.SEAM:
                self._vertex_partner[vid] = vid
            elif corr.state is CorrespondenceState.PAIRED:
                self._vertex_partner[vid] = corr.partner
            else:
                self._vertex_partner[vid] = None

        self._edge_by_pair: dict[frozenset[VertexId], EdgeId] = {}
        for eid in mesh.all_edge_ids():
            self._edge_by_pair[frozenset(mesh.edge_vertices(eid))] = eid

        # A face is identified by its vertex set; a duplicate set resolves to the lowest id so
        # the lookup stays deterministic.
        self._face_by_vertices: dict[frozenset[VertexId], FaceId] = {}
        for fid in sorted(mesh.all_face_ids()):
            self._face_by_vertices.setdefault(frozenset(mesh.face_vertices(fid)), fid)

    def vertex_partner(self, vertex_id: VertexId) -> VertexId | None:
        return self._vertex_partner.get(vertex_id)

    def edge_partner(self, edge_id: EdgeId) -> EdgeId | None:
        a, b = self.mesh.edge_vertices(edge_id)
        pa, pb = self._vertex_partner.get(a), self._vertex_partner.get(b)
        if pa is None or pb is None:
            return None
        return self._edge_by_pair.get(frozenset((pa, pb)))

    def face_partner(self, face_id: FaceId) -> FaceId | None:
        image = []
        for vid in self.mesh.face_vertices(face_id):
            partner = self._vertex_partner.get(vid)
            if partner is None:
                return None
            image.append(partner)
        return self._face_by_vertices.get(frozenset(image))


def build_index(mesh: Mesh) -> SymmetryIndex:
    return SymmetryIndex(mesh)


# ---------------------------------------------------------------------------------------------
# Selection canonicalisation and expansion
# ---------------------------------------------------------------------------------------------


def _signed_distance(position: Position, definition: SymmetryDefinition) -> float:
    return sum((p - o) * n for p, o, n in zip(position, definition.plane_point, definition.plane_normal))


def _vertex_side(mesh: Mesh, definition: SymmetryDefinition, vertex_ids: Iterable[VertexId]) -> float:
    """Sum of signed distances: > 0 on the normal's side, < 0 opposite, 0 on / spanning the plane."""
    return sum(_signed_distance(mesh.vertex_position(v), definition) for v in vertex_ids)


def canonical_vertices(index: SymmetryIndex, vertex_ids: Iterable[VertexId]) -> set[VertexId]:
    """Count mirror pairs once (A2 = A): of a vertex and its partner keep the normal's side."""
    return _canonical(index, vertex_ids, index.vertex_partner, lambda v: _vertex_side(index.mesh, index.definition, (v,)))


def canonical_edges(index: SymmetryIndex, edge_ids: Iterable[EdgeId]) -> set[EdgeId]:
    return _canonical(index, edge_ids, index.edge_partner, lambda e: _vertex_side(index.mesh, index.definition, index.mesh.edge_vertices(e)))


def canonical_faces(index: SymmetryIndex, face_ids: Iterable[FaceId]) -> set[FaceId]:
    return _canonical(index, face_ids, index.face_partner, lambda f: _vertex_side(index.mesh, index.definition, index.mesh.face_vertices(f)))


def _canonical(index, ids, partner_of, side_of) -> set:
    selected = set(ids)
    result = set()
    for element in selected:
        partner = partner_of(element)
        if partner is None or partner == element or partner not in selected:
            result.add(element)
        elif side_of(element) > side_of(partner):
            result.add(element)
    return result


@dataclass(frozen=True)
class Expansion:
    """A selection plus its partners. `unpaired` are the selected elements with no partner."""

    selected: frozenset
    partners: frozenset
    unpaired: frozenset

    @property
    def union(self) -> frozenset:
        return self.selected | self.partners


def _expand(ids, partner_of) -> Expansion:
    selected = frozenset(ids)
    partners, unpaired = set(), set()
    for element in selected:
        partner = partner_of(element)
        if partner is None:
            unpaired.add(element)
        elif partner != element and partner not in selected:
            # A seam element is its own partner and is counted once; an explicitly selected
            # partner is not added again ("explicit wins").
            partners.add(partner)
    return Expansion(selected, frozenset(partners), frozenset(unpaired))


def expand_vertices(index: SymmetryIndex, vertex_ids: Iterable[VertexId]) -> Expansion:
    return _expand(vertex_ids, index.vertex_partner)


def expand_edges(index: SymmetryIndex, edge_ids: Iterable[EdgeId]) -> Expansion:
    return _expand(edge_ids, index.edge_partner)


def expand_faces(index: SymmetryIndex, face_ids: Iterable[FaceId]) -> Expansion:
    return _expand(face_ids, index.face_partner)


# ---------------------------------------------------------------------------------------------
# Both-sides-in-one-face detection (AD-SYM-03 §3 item 9)
# ---------------------------------------------------------------------------------------------


def both_sides_faces(index: SymmetryIndex, expansion: Expansion, *, mode: str) -> frozenset[FaceId]:
    """Faces where a union call would differ from "intent + mirrored intent" (R1, review F3).

    A face is returned when it holds elements of the selection *and* of its image, or when it is
    self-mirrored and holds any element of the union. `mode` is "edge" or "vertex". A coordinator
    refuses visibly while this is non-empty.
    """
    mesh = index.mesh
    if mode == "edge":
        faces_of = mesh.edge_faces
    elif mode == "vertex":
        vertex_faces: dict[VertexId, list[FaceId]] = {}
        for fid in mesh.all_face_ids():
            for v in mesh.face_vertices(fid):
                vertex_faces.setdefault(v, []).append(fid)
        faces_of = lambda v: vertex_faces.get(v, ())  # noqa: E731
    else:
        raise ValueError(f"mode must be 'edge' or 'vertex', got {mode!r}")

    from_selected = {f for element in expansion.selected for f in faces_of(element)}
    from_partners = {f for element in expansion.partners for f in faces_of(element)}

    conflicts = from_selected & from_partners
    for fid in from_selected | from_partners:
        if index.face_partner(fid) == fid:
            conflicts.add(fid)
    return frozenset(conflicts)


# ---------------------------------------------------------------------------------------------
# Seam rule S1
# ---------------------------------------------------------------------------------------------


def seam_after_split(
    definition: SymmetryDefinition,
    split_seam_edges: Mapping[EdgeId, tuple[EdgeId, EdgeId]],
) -> SymmetryDefinition:
    """Seam rule S1: a seam edge that an op split is replaced by its two halves.

    `split_seam_edges` maps each split seam edge to the halves the op reported (`Mesh.split_edge`
    returns them). Edges that are not in the seam are ignored. Returns a new definition; the
    caller writes it inside the same transaction, so Undo restores it through `MeshStateCommand`.
    """
    seam = set(definition.seam_edges)
    for old, (half_a, half_b) in split_seam_edges.items():
        if old in seam:
            seam.discard(old)
            seam.update((half_a, half_b))
    return SymmetryDefinition(definition.plane_point, definition.plane_normal, frozenset(seam))


# ---------------------------------------------------------------------------------------------
# Completeness report and delta check
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CompletenessReport:
    """Which elements have no partner, derived from the mesh (C-b; `symmetry_state` is untouched).

    The id sets of all current elements are kept so a delta can tell "created" from "survived".
    `sides` (connectivity) is deliberately not part of it: a symmetric face-band delete raises it
    (R3), so it is no delta signal.
    """

    vertices: frozenset[VertexId]
    edges: frozenset[EdgeId]
    faces: frozenset[FaceId]
    unpaired_vertices: frozenset[VertexId]
    edges_without_partner: frozenset[EdgeId]
    faces_without_partner: frozenset[FaceId]
    self_mirrored_faces: frozenset[FaceId]
    dead_seam_ids: frozenset[EdgeId]


def completeness_report(mesh: Mesh, index: SymmetryIndex | None = None) -> CompletenessReport:
    definition = mesh.symmetry_definition
    if definition is None:
        raise ValueError("completeness_report needs mesh.symmetry_definition")
    if index is None:
        index = SymmetryIndex(mesh)

    vertices = frozenset(mesh.all_vertex_ids())
    edges = frozenset(mesh.all_edge_ids())
    faces = frozenset(mesh.all_face_ids())
    return CompletenessReport(
        vertices=vertices,
        edges=edges,
        faces=faces,
        unpaired_vertices=frozenset(v for v in vertices if index.vertex_partner(v) is None),
        edges_without_partner=frozenset(e for e in edges if index.edge_partner(e) is None),
        faces_without_partner=frozenset(f for f in faces if index.face_partner(f) is None),
        self_mirrored_faces=frozenset(f for f in faces if index.face_partner(f) == f),
        dead_seam_ids=frozenset(e for e in definition.seam_edges if not mesh.is_valid_edge(e)),
    )


@dataclass(frozen=True)
class DeltaResult:
    violations: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.violations


def delta_check(before: CompletenessReport, after: CompletenessReport) -> DeltaResult:
    """Delta rule of AD-SYM-03 §2.3 with D-strict (Artist-confirmed, A3 = S "for now").

    Judged by element id, so partial symmetry that existed before is not a violation (INV-10):
    1. no surviving element that was complete before is incomplete after;
    2. no new self-mirrored face and no new dead seam id;
    3. every created element has a partner (D-strict).
    """
    violations: list[str] = []

    for kind, ids_before, ids_after, bad_before, bad_after in (
        ("vertex", before.vertices, after.vertices, before.unpaired_vertices, after.unpaired_vertices),
        ("edge", before.edges, after.edges, before.edges_without_partner, after.edges_without_partner),
        ("face", before.faces, after.faces, before.faces_without_partner, after.faces_without_partner),
    ):
        survivors = ids_before & ids_after
        broken = (bad_after & survivors) - bad_before
        if broken:
            violations.append(f"{len(broken)} {kind}(s) lost their partner")
        created_bad = bad_after - ids_before
        if created_bad:
            violations.append(f"{len(created_bad)} created {kind}(s) without a partner")

    new_self_mirrored = after.self_mirrored_faces - before.self_mirrored_faces
    if new_self_mirrored:
        violations.append(f"{len(new_self_mirrored)} new face(s) spanning the plane")
    new_dead = after.dead_seam_ids - before.dead_seam_ids
    if new_dead:
        violations.append(f"{len(new_dead)} seam edge(s) consumed")

    return DeltaResult(tuple(violations))
