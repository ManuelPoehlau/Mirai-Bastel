"""Collapse V/E/F on a component selection (WP Toolbox Gaps B1, `docs/WP_TOOLBOX_GAPS_PLAN.md`).

Maps the selection of a component mode onto the input of `core.operations.collapse_elements`:
vertex mode = the selected vertices (groups over the edges between two of them), edge mode = the
selected edges, face mode = the edges of the selected faces. Mutates only; the caller owns the one
transaction (`Application._mesh_transaction`), as with `delete_dissolve.apply_removal`.
"""

from __future__ import annotations

from collections.abc import Iterable

from core import EdgeId, SelectionMode, VertexId
from core.mesh import Mesh
from core.operations.collapse import collapse_elements

COLLAPSE_LABEL = "Collapse"


def collapse_input(
    mesh: Mesh, mode: SelectionMode, ids: Iterable
) -> tuple[set[VertexId], set[EdgeId] | None]:
    """(vertices, edges) for `collapse_elements`; edges None = the edges between the vertices."""
    if mode is SelectionMode.VERTEX:
        return set(ids), None
    if mode is SelectionMode.EDGE:
        edges = set(ids)
    elif mode is SelectionMode.FACE:
        edges = {e for f in ids for e in mesh.face_edges(f)}
    else:
        raise ValueError(f"Collapse needs a component mode, not {mode!r}")
    return {v for e in edges for v in mesh.edge_vertices(e)}, edges


def apply_collapse(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> list[VertexId]:
    """Collapses each connected group of the selection to its centroid; returns one vertex per
    group. Raises `core.operations.CollapseRefused` before any mutation."""
    vertices, edges = collapse_input(mesh, mode, ids)
    return collapse_elements(mesh, vertices, edges)
