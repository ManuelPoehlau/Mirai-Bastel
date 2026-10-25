"""Hide / Isolate / Show all: geometry taken out of the way of the edit mesh (docs/future_ideas/MODELING.md,
Priorität 1; `PROVISIONAL`).

The container holds hidden **vertices** only. A face or edge is hidden when one of its corners / endpoints
is (Blender's rule), so topology created later between hidden vertices is hidden without any bookkeeping.
Like the mask (`mirai.mask`) it is view state, not mesh data: no History entry, no scene file, cleared on
scene load, kept per object by the `Application`.

Where it acts (one choke point each, all fed by `Application._hidden_push`):

- drawing and GPU picking: the viewport uploads a degenerate triangle for a hidden face
  (`RenderMesh.set_hidden`), so shading, depth and the face-ID pass agree; the SubD surface hides the
  derived faces of hidden control faces;
- CPU picking and box / lasso: `PickCache.set_hidden`;
- selection: it never contains a hidden element (Hide removes them; steps and loops stop at them);
- transforms: hidden vertices count as fully masked (`Application._mask_values`);
- topology commands that would reach a hidden face or edge are refused (`touches_hidden`).

IDs are never reused (AD-001), so a hidden ID that an Undo brings back is still hidden; stale IDs are
ignored where they are read.
"""

from __future__ import annotations

from typing import Iterable

from core import EdgeId, FaceId, Mesh, VertexId


class HiddenSet:
    """The hidden vertices of one edit object."""

    def __init__(self) -> None:
        self._vertices: set[VertexId] = set()

    def __bool__(self) -> bool:
        return bool(self._vertices)

    def __len__(self) -> int:
        return len(self._vertices)

    def vertices(self) -> frozenset[VertexId]:
        return frozenset(self._vertices)

    def hide(self, vertices: Iterable[VertexId]) -> None:
        self._vertices.update(vertices)

    def show_all(self) -> None:
        self._vertices.clear()

    def isolate(self, mesh: Mesh, keep: Iterable[VertexId]) -> None:
        """Everything but `keep` becomes hidden (the previous set is replaced: Isolate shows `keep`)."""
        keep = set(keep)
        self._vertices = {v for v in mesh.all_vertex_ids() if v not in keep}

    def prune(self, mesh: Mesh) -> None:
        self._vertices = {v for v in self._vertices if mesh.is_valid_vertex(v)}

    def is_hidden_vertex(self, vertex: VertexId) -> bool:
        return vertex in self._vertices

    def is_hidden_edge(self, mesh: Mesh, edge: EdgeId) -> bool:
        a, b = mesh.edge_vertices(edge)
        return a in self._vertices or b in self._vertices

    def is_hidden_face(self, mesh: Mesh, face: FaceId) -> bool:
        return any(v in self._vertices for v in mesh.face_vertices(face))


def visible(hidden: HiddenSet, vertices: Iterable[VertexId]) -> set[VertexId]:
    """`vertices` without the hidden ones."""
    hide = hidden.vertices()
    return {v for v in vertices if v not in hide}


def touches_hidden(mesh: Mesh, hidden: HiddenSet, vertices: Iterable[VertexId]) -> bool:
    """True if a face or edge around any of `vertices` is hidden - i.e. an operation on them would reach
    geometry the artist cannot see. Cheap exit when nothing is hidden."""
    if not hidden:
        return False
    hide = hidden.vertices()
    vertices = set(vertices)
    for edge in mesh.all_edge_ids():
        a, b = mesh.edge_vertices(edge)
        if (a in vertices or b in vertices) and (a in hide or b in hide):
            return True
    return False
