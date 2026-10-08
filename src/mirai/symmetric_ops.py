"""Symmetric topology coordinators (AD-SYM-03 §3, slices 3b/3c): Edge Connect, Vertex Connect, and
the removal commands Delete, Dissolve and Dissolve (no cleanup).

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
    seam_after_split,
    seam_without_dead_ids,
)
from .topology.connect_per_face import EdgeConnectResult, apply_connect_edges
from .topology.connect_vertices_per_face import apply_connect_vertices
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

    Seam (AD-SYM-03 §6 A1; assumption beyond Case 1, not confirmed by Manu): **Delete** drops the
    seam edge ids that no longer exist from the definition inside this mutation (M), the delta check
    stays the guard — it refuses if a surviving vertex lost its seam. **Dissolve** that would create
    a face spanning the plane or consume a seam edge is refused with `TEXT_SEAM_DISSOLVE` (R,
    Case 2 is UNKNOWN for the Artist). `RemovalRefused` from Core propagates unchanged."""
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

    new_faces = apply_removal(mesh, mode, set(expansion.union), dissolve=dissolve, cleanup=cleanup)
    if not dissolve:
        mesh.symmetry_definition = seam_without_dead_ids(mesh)

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
