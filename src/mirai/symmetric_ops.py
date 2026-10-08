"""Symmetric topology coordinators (AD-SYM-03 §3, slice 3b): Edge Connect and Vertex Connect.

A coordinator is a pure mutation `coordinate_*(mesh, canonical_selection) -> result` for the
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
never `application`. `mirai.symmetry_declarations` maps `CContext` to these functions.
"""

from __future__ import annotations

from typing import Iterable

from core import EdgeId, VertexId
from core.mesh import Mesh, SymmetryDefinition

from .symmetry_coordination import (
    SymmetryIndex,
    both_sides_faces,
    completeness_report,
    delta_check,
    expand_edges,
    expand_vertices,
    is_exact_plane,
    seam_after_split,
)
from .topology.connect_per_face import EdgeConnectResult, apply_connect_edges
from .topology.connect_vertices_per_face import apply_connect_vertices

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
