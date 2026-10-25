"""Symmetric topology coordinators (AD-SYM-03 §3, slices 3b/3c/4): Edge Connect, Vertex Connect,
Split, the removal commands Delete, Dissolve and Dissolve (no cleanup), Collapse (WP Toolbox
Gaps B1) and Cap (2026-10-25).

A coordinator is a pure mutation `coordinate_*(mesh, selection[, mode]) -> result` for the
unchanged `apply_*` function of `mirai.topology`: expand the (already canonical, one-sided)
selection with its partners, refuse what cannot be mirrored, call `apply_*` **once** on the union
(M-a style 1), maintain the seam (S1), and check the completeness delta (D-strict). It pushes
nothing and restores nothing: the caller owns the single transaction (`Application.
_mesh_transaction`, T-a), and a raised `SymmetryRefusal` is its rollback signal.

Refusals (`SymmetryRefusal`, the exception carries the status text) are part of the contract of a
*supported* operation ("mirrors correctly or recognisably not at all", INV-5); they apply whenever
a definition is set, in MARK as in BLOCK (AD-013 H2 amendment, "Runtime refusals are not G-3").
Order: plane first (the partner relation is meaningless off an exact plane), then unpaired
selection, then both-sides faces, then — after the op — the delta.

Dependency direction: `symmetric_ops` -> `mirai.symmetry_coordination`, `mirai.topology`, `core`;
never `application`. `mirai.symmetry_declarations` maps `CContext` and the removal commands to these functions.
"""

from __future__ import annotations

from typing import Callable, Iterable

from core import EdgeId, FaceId, SelectionMode, VertexId
from core.mesh import Mesh, SymmetryDefinition
from core.operations.collapse import collapse_elements, collapse_groups

from .symmetry import mirror_position
from .symmetry_coordination import (
    SymmetryIndex,
    both_sides_faces,
    completeness_report,
    delta_check,
    element_side,
    expand_edges,
    expand_faces,
    expand_vertices,
    is_exact_plane,
    seam_after_cleanup_merge,
    seam_after_split,
    seam_without_dead_ids,
)
from .topology.connect_per_face import EdgeConnectResult, apply_connect_edges
from .topology.connect_vertices_per_face import apply_connect_vertices
from .topology.border import border_loop, cap_loops, cap_winding, check_cappable
from .topology.collapse import collapse_input
from .topology.delete_dissolve import apply_removal

#: Refusal texts (visible status line, each says what to do). The Lab README lists them.
TEXT_NON_EXACT_PLANE = (
    "Symmetrie: Ebene nicht achsparallel durch den Ursprung — Operation nicht koordinierbar; "
    "Symmetrie ausschalten (Shift+S)"
)
TEXT_UNPAIRED = (
    "Symmetrie: Auswahl enthält Elemente ohne Spiegelpartner — an einer Stelle mit Partner "
    "arbeiten oder Symmetrie ausschalten (Shift+S)"
)
TEXT_BOTH_SIDES_FACE = (
    "Symmetrie: eine Face würde von beiden Seiten getroffen (Auswahl und Spiegelbild) — "
    "Auswahl verkleinern oder Symmetrie ausschalten (Shift+S)"
)
TEXT_DELTA = (
    "Symmetrie: Ergebnis wäre nicht spiegelbildlich (neue Elemente ohne Partner) — nichts "
    "geändert; an einer Stelle mit Partner arbeiten oder Symmetrie ausschalten (Shift+S)"
)
TEXT_CAP_PLANE = (
    "Symmetrie: das Loch liegt über der Ebene, hat aber nicht genau zwei Seam-Punkte gegenüber — "
    "nichts geändert; Symmetrie ausschalten (Shift+S) oder die Seam bis an den Rand führen"
)
TEXT_SEAM_DISSOLVE = (
    "Symmetrie: Auflösen an der Seam wird noch nicht unterstützt (Seam-Kante oder -Vertex würde "
    "aufgelöst) — nichts geändert; abseits der Seam arbeiten oder Symmetrie ausschalten (Shift+S)"
)


class SymmetryRefusal(Exception):
    """A coordinator refuses; `str(exc)` is the status text. `violations` holds the delta
    detail for `TEXT_DELTA` (diagnostics, not shown)."""

    def __init__(self, text: str, violations: tuple[str, ...] = ()) -> None:
        super().__init__(text)
        self.violations = violations


def _require_definition(mesh: Mesh) -> SymmetryDefinition:
    definition = mesh.symmetry_definition
    if definition is None:
        raise ValueError("a symmetric coordinator needs mesh.symmetry_definition")
    return definition


def _refuse_before(mesh: Mesh, definition: SymmetryDefinition, selected: Iterable, *, mode: str):
    """The shared pre-op refusals; returns `(index, expansion)` of the clean selection."""
    if not is_exact_plane(definition):
        raise SymmetryRefusal(TEXT_NON_EXACT_PLANE)
    index = SymmetryIndex(mesh)
    expand = expand_edges if mode == "edge" else expand_vertices
    expansion = expand(index, selected)
    if expansion.unpaired:
        raise SymmetryRefusal(TEXT_UNPAIRED)
    if both_sides_faces(index, expansion, mode=mode):
        raise SymmetryRefusal(TEXT_BOTH_SIDES_FACE)
    return index, expansion


def _check_delta(before, mesh: Mesh) -> None:
    result = delta_check(before, completeness_report(mesh))
    if not result.ok:
        raise SymmetryRefusal(TEXT_DELTA, result.violations)


def _edge_between(mesh: Mesh, a: VertexId, b: VertexId) -> EdgeId:
    for edge_id in mesh.vertex_edges(a):
        if b in mesh.edge_vertices(edge_id):
            return edge_id
    raise LookupError(f"no edge between {a!r} and {b!r}")


def residue_sides(
    mesh: Mesh, live: Iterable, vertices_of: Callable[[object], Iterable[VertexId]]
) -> frozenset[int]:
    """The sides (+1 normal's side, -1 opposite) a symmetric operation's selection residue goes
    to: those on which the **live** selection (before canonicalisation) has elements; only
    elements on the plane or none at all -> the normal's side. `vertices_of` is
    `mesh.edge_vertices` / `mesh.face_vertices`, so call this before the mutation. Engineering
    default (AD-SYM-03 §4, "Residue under symmetry"), not an Artist decision."""
    definition = _require_definition(mesh)
    sides = {element_side(mesh, definition, vertices_of(e)) for e in live} - {0}
    return frozenset(sides) or frozenset({1})


def on_residue_sides(
    mesh: Mesh,
    created: Iterable,
    sides: frozenset[int],
    vertices_of: Callable[[object], Iterable[VertexId]],
) -> set:
    """The `created` elements that lie on one of `sides`; an element on or spanning the plane
    (its own mirror) always stays."""
    definition = _require_definition(mesh)
    kept = set()
    for element in created:
        side = element_side(mesh, definition, vertices_of(element))
        if side == 0 or side in sides:
            kept.add(element)
    return kept


def coordinate_edge_connect(mesh: Mesh, edge_ids: Iterable[EdgeId]) -> EdgeConnectResult:
    """Edge Connect on `edge_ids` (canonical: each mirror pair once) and their partners, in one
    `apply_connect_edges` call. A seam edge that the op split is replaced by its two halves
    inside the same mutation (seam rule S1), so Undo restores the old seam with the mesh."""
    definition = _require_definition(mesh)
    index, expansion = _refuse_before(mesh, definition, edge_ids, mode="edge")
    before = completeness_report(mesh, index)

    # The endpoints must be read before the op: a split edge no longer exists afterwards.
    seam_ends = {
        e: mesh.edge_vertices(e) for e in expansion.union if e in definition.seam_edges
    }
    result = apply_connect_edges(mesh, set(expansion.union))

    halves = {}
    for old, midpoint in result.midpoints.items():
        if old in seam_ends:
            a, b = seam_ends[old]
            halves[old] = (_edge_between(mesh, midpoint, a), _edge_between(mesh, midpoint, b))
    if halves:
        mesh.symmetry_definition = seam_after_split(definition, halves)

    _check_delta(before, mesh)
    return result


def coordinate_split(mesh: Mesh, edge_ids: Iterable[EdgeId]) -> list[VertexId]:
    """Split of `edge_ids` (canonical: one edge, a mirror pair counts once) and its partner at
    t = 0.5, in one mutation. Returns the new vertices, source first (one, for a seam edge, which
    is its own partner and is split once).

    t = 0.5 is exact on an exact plane (`is_exact_plane`): the midpoints of mirrored edges are
    bit-identical mirrors, so the new vertices pair without a tolerance. A split seam edge is
    replaced by its two halves (seam rule S1) inside this mutation, so the new vertex on the
    plane is a seam vertex and Undo restores the old seam with the mesh. `Mesh.split_edge`
    invalidates only the edge it splits, so the partner id stays valid after the first split."""
    definition = _require_definition(mesh)
    index, expansion = _refuse_before(mesh, definition, edge_ids, mode="edge")
    before = completeness_report(mesh, index)

    # Source first (the canonical, normal's-side edge), then the partner, deterministically.
    ordered = sorted(expansion.selected) + sorted(expansion.partners)
    created: list[VertexId] = []
    halves = {}
    for edge_id in ordered:
        new_vertex, half_a, half_b = mesh.split_edge(edge_id, 0.5)
        created.append(new_vertex)
        if edge_id in definition.seam_edges:
            halves[edge_id] = (half_a, half_b)
    if halves:
        mesh.symmetry_definition = seam_after_split(definition, halves)

    _check_delta(before, mesh)
    return created


def coordinate_vertex_connect(mesh: Mesh, vertex_ids: Iterable[VertexId]) -> list:
    """Vertex Connect on `vertex_ids` (canonical) and their partners, in one
    `apply_connect_vertices` call. Returns `[]` if nothing was connectable (the unchanged
    "nothing happened" signal; the mesh is untouched then, so no delta check is needed)."""
    definition = _require_definition(mesh)
    index, expansion = _refuse_before(mesh, definition, vertex_ids, mode="vertex")
    before = completeness_report(mesh, index)

    created = apply_connect_vertices(mesh, set(expansion.union))
    if not created:
        return created

    _check_delta(before, mesh)
    return created


# ---------------------------------------------------------------------------------------------
# Removal: Delete, Dissolve, Dissolve (no cleanup) — slice 3c
# ---------------------------------------------------------------------------------------------

_REMOVAL_EXPANSION = {
    SelectionMode.VERTEX: ("vertex", expand_vertices),
    SelectionMode.EDGE: ("edge", expand_edges),
    SelectionMode.FACE: (None, expand_faces),
}


def coordinate_removal(
    mesh: Mesh, mode: SelectionMode, ids: Iterable, *, dissolve: bool, cleanup: bool
) -> list[FaceId]:
    """Delete / Dissolve of `ids` (elements of `mode`) and their partners, in one `apply_removal`
    call. `ids` may hold one side or both (a mirror pair counts once, "explicit wins"); no
    canonicalisation is needed because the union is the same.

    Seam (AD-SYM-03 §6 A1): **Delete** drops the seam edge ids that no longer exist from the
    definition inside this mutation (M), the delta check stays the guard — it refuses if a surviving
    vertex lost its seam. **Dissolve** with cleanup first applies seam rule S2
    (`seam_after_cleanup_merge`): two seam edges at a cleaned-up seam vertex become the one edge
    between their outer ends (Artist 2026-10-08, A1 Case 2 refined: an edge *crossing* the seam may
    be dissolved). What is then left — a face spanning the plane or a seam edge consumed (an edge
    directly on the seam, a face pair across it) — is refused with `TEXT_SEAM_DISSOLVE` (R).
    `RemovalRefused` from Core propagates unchanged."""
    definition = _require_definition(mesh)
    if not is_exact_plane(definition):
        raise SymmetryRefusal(TEXT_NON_EXACT_PLANE)
    index = SymmetryIndex(mesh)
    both_sides_mode, expand = _REMOVAL_EXPANSION[mode]
    expansion = expand(index, ids)
    if expansion.unpaired:
        raise SymmetryRefusal(TEXT_UNPAIRED)
    # Face mode relies on the delta check: a face holds no sub-elements that could be hit twice.
    if both_sides_mode is not None and both_sides_faces(index, expansion, mode=both_sides_mode):
        raise SymmetryRefusal(TEXT_BOTH_SIDES_FACE)
    before = completeness_report(mesh, index)

    # Endpoints must be read before the op: a removed edge no longer exists afterwards.
    seam_ends = {e: mesh.edge_vertices(e) for e in definition.seam_edges if mesh.is_valid_edge(e)}
    new_faces = apply_removal(mesh, mode, set(expansion.union), dissolve=dissolve, cleanup=cleanup)
    if not dissolve:
        mesh.symmetry_definition = seam_without_dead_ids(mesh)
    elif cleanup:
        mesh.symmetry_definition = seam_after_cleanup_merge(definition, seam_ends, mesh, before.edges)

    after = completeness_report(mesh)
    result = delta_check(before, after)
    if dissolve and (
        after.self_mirrored_faces - before.self_mirrored_faces
        or after.dead_seam_ids - before.dead_seam_ids
    ):
        raise SymmetryRefusal(TEXT_SEAM_DISSOLVE, result.violations)
    if not result.ok:
        raise SymmetryRefusal(TEXT_DELTA, result.violations)
    return new_faces


def coordinate_delete(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> list[FaceId]:
    return coordinate_removal(mesh, mode, ids, dissolve=False, cleanup=False)


def coordinate_dissolve(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> list[FaceId]:
    return coordinate_removal(mesh, mode, ids, dissolve=True, cleanup=True)


def coordinate_dissolve_no_cleanup(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> list[FaceId]:
    return coordinate_removal(mesh, mode, ids, dissolve=True, cleanup=False)


# ---------------------------------------------------------------------------------------------
# Collapse (WP Toolbox Gaps B1)
# ---------------------------------------------------------------------------------------------


def coordinate_collapse(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> list[VertexId]:
    """Collapse of `ids` (elements of `mode`) and their partners, in one `collapse_elements` call
    on the union. Returns one vertex per group, like `apply_collapse`.

    A group and its mirror image collapse separately; a group that touches its image (through a
    seam vertex or a shared face edge) is one group with the plane in its middle. Centroids are
    not left to float rounding: the survivor of a mirror pair is set to the exact mirror of its
    partner on the normal's side, a self-mirrored group's survivor is projected onto the plane,
    so the pairs stay exact (`vertex_correspondence` pairs by position). Seam (as Delete, M): seam
    edge ids that died inside a group are dropped; the delta check refuses whatever is left
    unmirrored (a vertex off its seam, a face spanning the plane). No both-sides refusal: the
    union is "intent + mirrored intent" here, where groups touching their image merge.
    `CollapseRefused` from Core propagates unchanged."""
    definition = _require_definition(mesh)
    if not is_exact_plane(definition):
        raise SymmetryRefusal(TEXT_NON_EXACT_PLANE)
    index = SymmetryIndex(mesh)
    _, expand = _REMOVAL_EXPANSION[mode]
    expansion = expand(index, ids)
    if expansion.unpaired:
        raise SymmetryRefusal(TEXT_UNPAIRED)
    before = completeness_report(mesh, index)

    vertices, edges = collapse_input(mesh, mode, expansion.union)
    groups = collapse_groups(mesh, vertices, edges)
    survivors = collapse_elements(mesh, vertices, edges)

    group_of = {v: i for i, group in enumerate(groups) for v in group}
    normal = definition.plane_normal
    for i, group in enumerate(groups):
        if len(group) == 1:
            continue
        j = group_of.get(index.vertex_partner(group[0]))
        if j is None:
            continue  # the delta check judges an image that is not a group of its own
        position = mesh.vertex_position(survivors[i])
        if j == i:
            distance = sum((p - o) * n for p, o, n in zip(position, definition.plane_point, normal))
            mesh.set_vertex_position(survivors[i], tuple(p - distance * n for p, n in zip(position, normal)))
        elif j > i:
            source, image = (i, j) if element_side(mesh, definition, [survivors[i]]) >= 0 else (j, i)
            mirrored = mirror_position(
                mesh.vertex_position(survivors[source]), definition.plane_point, normal
            )
            mesh.set_vertex_position(survivors[image], mirrored)

    mesh.symmetry_definition = seam_without_dead_ids(mesh)
    _check_delta(before, mesh)
    return survivors


def coordinate_cap(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> list[FaceId]:
    """Cap of the borders `ids` touch and of their mirror images, in one mutation. Returns the new
    faces.

    A border and its image are capped separately. A border that is its own image (a hole across
    the plane, e.g. the neck of a head) would become one face spanning the plane, which D-strict
    refuses; it is closed with two mirror faces instead, split along a new edge between its two
    seam vertices, and that edge joins the seam (as Split's halves do, S1). Such a hole needs
    exactly two seam vertices that are not neighbours on the border, else `TEXT_CAP_PLANE`.
    `CapRefused` propagates unchanged; the delta check stays the guard."""
    definition = _require_definition(mesh)
    if not is_exact_plane(definition):
        raise SymmetryRefusal(TEXT_NON_EXACT_PLANE)
    index = SymmetryIndex(mesh)
    loops = cap_loops(mesh, mode, ids)
    by_edges = {frozenset(loop.edges): loop for loop in loops}
    for loop in loops:
        images = [index.edge_partner(e) for e in loop.edges]
        if any(image is None for image in images):
            raise SymmetryRefusal(TEXT_UNPAIRED)
        if frozenset(images) not in by_edges:
            image_loop = border_loop(mesh, images[0])
            by_edges[frozenset(image_loop.edges)] = image_loop
    before = completeness_report(mesh, index)

    plans: list[list[list[VertexId]]] = []
    seam_pairs: list[tuple[VertexId, VertexId]] = []
    for loop in by_edges.values():
        check_cappable(mesh, loop)
        winding = cap_winding(mesh, loop)
        if frozenset(index.edge_partner(e) for e in loop.edges) != frozenset(loop.edges):
            plans.append([winding])
            continue
        on_seam = [i for i, v in enumerate(winding) if index.vertex_partner(v) == v]
        if len(on_seam) != 2 or (on_seam[1] - on_seam[0]) in (1, len(winding) - 1):
            raise SymmetryRefusal(TEXT_CAP_PLANE)
        a, b = winding[on_seam[0]], winding[on_seam[1]]
        if any(b in mesh.edge_vertices(e) for e in mesh.vertex_edges(a)):
            raise SymmetryRefusal(TEXT_CAP_PLANE)
        rotated = winding[on_seam[0]:] + winding[: on_seam[0]]
        k = on_seam[1] - on_seam[0]
        plans.append([rotated[: k + 1], rotated[k:] + rotated[:1]])
        seam_pairs.append((a, b))

    new_faces = [mesh.add_face(face) for plan in plans for face in plan]
    if seam_pairs:
        seam = set(definition.seam_edges) | {_edge_between(mesh, a, b) for a, b in seam_pairs}
        mesh.symmetry_definition = SymmetryDefinition(
            definition.plane_point, definition.plane_normal, frozenset(seam)
        )
    _check_delta(before, mesh)
    return new_faces
