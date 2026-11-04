"""Hide / Isolate / Show all: geometry taken out of the way of the edit mesh (docs/future_ideas/MODELING.md,
Priorität 1; `PROVISIONAL`).

The container holds two explicit sets: hidden **vertices** (vertex and edge mode: a face or edge is hidden when one
of its corners / endpoints is, Blender's rule, so topology created later between hidden vertices is hidden without
any bookkeeping) and hidden **faces** (face mode, Manu 2026-11-04, I1 "Hide exactly the selected Polygons": exactly
those polygons go, their neighbours stay whole). An edge or vertex is hidden when all faces around it are hidden. The
rule lives in one place, `viewport.hidden_rule` (Core -> Viewport), so drawing, picking and this container agree.
Like the mask (`mirai.mask`) it is view state, not mesh data: no History entry, no scene file, cleared on scene load,
kept per document object by the `Application`.

Where it acts (one choke point each, all fed by `Application._hidden_push`):

- drawing and GPU picking: the viewport uploads a degenerate triangle for a hidden face and a null line for a hidden
  edge (`RenderMesh.set_hidden(vertices, faces)`), so shading, depth, the wire and the ID pass agree; every
  replacement surface follows (the morph mix and the pose take the same sets, the SubD surface hides the derived
  faces of hidden control faces), also one switched on after the Hide (2026-11-04, AD-013 H7 note);
- CPU picking and box / lasso: `PickCache.set_hidden(vertices, faces)`;
- selection: it never contains a hidden element (Hide removes them; steps and loops stop at them);
- transforms: hidden vertices (also those whose faces are all hidden) count as fully masked
  (`Application._mask_values`); a corner a visible face still uses moves, as in Blender;
- loops, rings and topology commands stop at the corners of hidden faces: a loop does not take a hidden edge, a
  ring does not enter a hidden face, a topology command next to a hidden face or edge is refused (`touches_hidden`).

IDs are never reused (AD-001), so a hidden ID that an Undo brings back is still hidden; stale IDs are
ignored where they are read.
"""

from __future__ import annotations

from typing import Iterable

from core import EdgeId, FaceId, Mesh, VertexId
from viewport.hidden_rule import NOTHING, Resolved, edge_is_hidden, face_is_hidden, resolve, vertex_is_hidden


class HiddenSet:
    """The hidden vertices and faces of one document object."""

    def __init__(self) -> None:
        self._vertices: set[VertexId] = set()
        self._faces: set[FaceId] = set()
        # `resolve` per mesh, reused until the sets or the mesh's topology change (a move keeps it): the selection
        # prune, the mask and Soft read it several times per push.
        self._cache: tuple | None = None  # (mesh, MeshWatch, Resolved)

    def __bool__(self) -> bool:
        return bool(self._vertices or self._faces)

    def __len__(self) -> int:
        return len(self._vertices) + len(self._faces)

    def vertices(self) -> frozenset[VertexId]:
        """The explicitly hidden vertices (vertex / edge mode)."""
        return frozenset(self._vertices)

    def faces(self) -> frozenset[FaceId]:
        """The explicitly hidden faces (face mode)."""
        return frozenset(self._faces)

    def describe(self) -> str:
        """"12 points", "4 faces" or "12 points, 4 faces" - for status lines."""
        parts = []
        if self._vertices:
            parts.append(f"{len(self._vertices)} points")
        if self._faces:
            parts.append(f"{len(self._faces)} faces")
        return ", ".join(parts) or "nothing"

    def hide(self, vertices: Iterable[VertexId]) -> None:
        self._vertices.update(vertices)
        self._changed()

    def hide_faces(self, faces: Iterable[FaceId]) -> None:
        self._faces.update(faces)
        self._changed()

    def show_all(self) -> None:
        self._vertices.clear()
        self._faces.clear()
        self._changed()

    def _changed(self) -> None:
        if self._cache is not None:
            mesh, watch, _resolved = self._cache
            self._cache = (mesh, watch, None)

    def isolate(self, mesh: Mesh, keep: Iterable[VertexId]) -> None:
        """Everything but `keep` becomes hidden (the previous set is replaced: Isolate shows `keep`)."""
        keep = set(keep)
        self._vertices = {v for v in mesh.all_vertex_ids() if v not in keep}
        self._faces = set()
        self._changed()

    def isolate_faces(self, mesh: Mesh, keep: Iterable[FaceId]) -> None:
        """Every face but `keep` becomes hidden, and every vertex on no face (loose points and wire; the previous set
        is replaced)."""
        faces = mesh.all_face_ids()
        self._faces = set(faces).difference(keep)
        on_faces = set().union(*map(mesh.face_vertices, faces))
        self._vertices = set(mesh.all_vertex_ids()).difference(on_faces)
        self._changed()

    def prune(self, mesh: Mesh) -> None:
        vertices = {v for v in self._vertices if mesh.is_valid_vertex(v)}
        faces = {f for f in self._faces if mesh.is_valid_face(f)}
        if vertices != self._vertices or faces != self._faces:
            self._vertices, self._faces = vertices, faces
            self._changed()

    def resolve(self, mesh: Mesh) -> Resolved:
        """Every hidden vertex, edge and face of `mesh` (`viewport.hidden_rule.resolve`)."""
        if not self:
            return NOTHING
        cache = self._cache
        if cache is None or cache[0] is not mesh:
            cache = (mesh, mesh.watch(), None)
        mesh_, watch, resolved = cache
        change = watch.take()
        # Moving vertices changes nothing hidden; any topology change touches an edge or a face (a loose vertex
        # alone neither hides nor shows anything).
        if resolved is None or change.faces or change.edges:
            resolved = resolve(mesh, self._vertices, self._faces)
        self._cache = (mesh_, watch, resolved)
        return resolved

    def hides_everything(self, mesh: Mesh) -> bool:
        """True when nothing of `mesh` would stay visible."""
        resolved = self.resolve(mesh)
        return len(resolved.faces) >= len(mesh.all_face_ids()) and len(resolved.vertices) >= len(mesh.all_vertex_ids())

    def is_hidden_vertex(self, mesh: Mesh, vertex: VertexId) -> bool:
        return vertex_is_hidden(mesh, vertex, self._vertices, self._faces)

    def is_hidden_edge(self, mesh: Mesh, edge: EdgeId) -> bool:
        return edge_is_hidden(mesh, edge, self._vertices, self._faces)

    def is_hidden_face(self, mesh: Mesh, face: FaceId) -> bool:
        return face_is_hidden(mesh, face, self._vertices, self._faces)


def touches_hidden(mesh: Mesh, hidden: HiddenSet, vertices: Iterable[VertexId]) -> bool:
    """True if a vertex, edge or face around any of `vertices` is hidden - i.e. an operation on them would reach
    geometry the artist cannot see (a corner of a hidden face counts). Cheap exit when nothing is hidden."""
    if not hidden:
        return False
    resolved = hidden.resolve(mesh)
    for v in vertices:
        if not mesh.is_valid_vertex(v):
            continue
        if v in resolved.vertices:
            return True
        for e in mesh.vertex_edges(v):
            if e in resolved.edges or any(f in resolved.faces for f in mesh.edge_faces(e)):
                return True
    return False


def mirrored_faces(mesh: Mesh, faces: Iterable[FaceId]) -> set[FaceId]:
    """The mirror partners of `faces` under the mesh's symmetry (a face whose corners are the partners of the given
    face's corners, seam corners standing for themselves); empty without symmetry or partner."""
    from .symmetry import CorrespondenceState, vertex_correspondence

    if mesh.symmetry_definition is None:
        return set()
    faces = set(faces)
    correspondence = vertex_correspondence(mesh)
    out: set[FaceId] = set()
    for face in faces:
        mapped = []
        for v in mesh.face_vertices(face):
            corr = correspondence.get(v)
            if corr is not None and corr.state == CorrespondenceState.PAIRED:
                mapped.append(corr.partner)
            elif corr is not None and corr.state == CorrespondenceState.SEAM:
                mapped.append(v)
            else:
                mapped = None
                break
        if not mapped:
            continue
        target = frozenset(mapped)
        for e in mesh.vertex_edges(mapped[0]):
            for f in mesh.edge_faces(e):
                if f not in faces and frozenset(mesh.face_vertices(f)) == target:
                    out.add(f)
    return out
