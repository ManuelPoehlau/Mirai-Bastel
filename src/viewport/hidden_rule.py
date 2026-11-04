"""The visibility rule of Hide / Isolate (`mirai.hidden`), shared by everything that draws or picks the edit mesh.

Two explicit sets go in: hidden **vertices** (vertex and edge mode, Blender's rule) and hidden **faces** (face mode,
Manu 2026-11-04, I1 "Hide exactly the selected Polygons"). What is hidden follows from them:

- a face is hidden when it is in the face set or one of its corners is a hidden vertex;
- an edge is hidden when an endpoint is a hidden vertex, or it has faces, all of them are hidden and at least one is
  in the face set;
- a vertex is hidden when it is in the vertex set, or it has faces, all of them are hidden and at least one is in the
  face set.

So a hidden polygon takes exactly itself away: its edges and corners stay as long as a visible face still uses them.
The "at least one in the face set" keeps vertex and edge mode exactly on the vertex rule: an isolated vertex or loop
whose faces are all hidden through other corners stays visible as points and wire. A loose edge or vertex (no faces)
follows the vertex set only. One module (Core -> Viewport, no `mirai` import), so the
`RenderMesh`, the wire, the CPU pick cache, the SubD surface and `mirai.hidden.HiddenSet` cannot disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AbstractSet, Iterable, Sequence

from core import EdgeId, FaceId, Mesh, VertexId


@dataclass(frozen=True)
class Resolved:
    """The effective hidden elements of one mesh (`resolve`)."""

    vertices: frozenset = frozenset()
    edges: frozenset = frozenset()
    faces: frozenset = frozenset()

    def __bool__(self) -> bool:
        return bool(self.vertices or self.edges or self.faces)


NOTHING = Resolved()


def _vertex_faces(mesh: Mesh, vertex: VertexId) -> set[FaceId]:
    faces: set[FaceId] = set()
    edge_faces = mesh.edge_faces
    for edge in mesh.vertex_edges(vertex):
        faces.update(edge_faces(edge))
    return faces


def face_is_hidden(mesh: Mesh, face: FaceId, vertices: AbstractSet, faces: AbstractSet) -> bool:
    return face in faces or (bool(vertices) and not vertices.isdisjoint(mesh.face_vertices(face)))


def _covered(mesh: Mesh, around, vertices: AbstractSet, faces: AbstractSet) -> bool:
    """`around` (the faces of an edge or vertex) are all hidden and at least one of them explicitly."""
    return (
        bool(faces)
        and any(f in faces for f in around)
        and all(face_is_hidden(mesh, f, vertices, faces) for f in around)
    )


def edge_is_hidden(mesh: Mesh, edge: EdgeId, vertices: AbstractSet, faces: AbstractSet) -> bool:
    a, b = mesh.edge_vertices(edge)
    if a in vertices or b in vertices:
        return True
    return _covered(mesh, mesh.edge_faces(edge), vertices, faces)


def vertex_is_hidden(mesh: Mesh, vertex: VertexId, vertices: AbstractSet, faces: AbstractSet) -> bool:
    if vertex in vertices:
        return True
    return bool(faces) and _covered(mesh, _vertex_faces(mesh, vertex), vertices, faces)


def resolve(mesh: Mesh, vertices: Iterable[VertexId] = (), faces: Iterable[FaceId] = ()) -> Resolved:
    """The hidden vertices, edges and faces of `mesh` for the explicit sets (stale IDs ignored). Work is proportional
    to the hidden part, or to the visible part when most faces are hidden (Isolate)."""
    vertices, faces = frozenset(vertices), frozenset(faces)
    if not vertices and not faces:
        return NOTHING
    all_vertices = mesh.all_vertex_ids()
    hide_v = vertices.intersection(all_vertices) if vertices else vertices
    explicit_f = faces.intersection(mesh.all_face_ids()) if faces else faces
    if not hide_v and not explicit_f:
        return NOTHING
    vertex_edges, edge_faces = mesh.vertex_edges, mesh.edge_faces
    hidden_edges: set[EdgeId]
    hide_f: set[FaceId]
    if 2 * len(hide_v) > len(all_vertices):
        # Most vertices hidden (vertex Isolate): only edges / faces with every corner kept stay visible, and those all
        # lie around the few kept vertices.
        keep = set(all_vertices) - hide_v
        edge_vertices, face_vertices = mesh.edge_vertices, mesh.face_vertices
        kept_edges: set[EdgeId] = set()
        kept_faces: set[FaceId] = set()
        for v in keep:
            for e in vertex_edges(v):
                a, b = edge_vertices(e)
                if a in keep and b in keep:
                    kept_edges.add(e)
        for e in kept_edges:
            for f in edge_faces(e):
                if f not in kept_faces and keep.issuperset(face_vertices(f)):
                    kept_faces.add(f)
        hidden_edges = set(mesh.all_edge_ids()).difference(kept_edges)
        hide_f = set(mesh.all_face_ids()).difference(kept_faces)
        hide_f.update(explicit_f)
    else:
        hidden_edges = set()
        hide_f = set(explicit_f)
        for v in hide_v:
            for e in vertex_edges(v):
                hidden_edges.add(e)  # an endpoint is hidden
                hide_f.update(edge_faces(e))  # a face with a hidden corner is hidden whole
    hidden_vertices = set(hide_v)
    if not explicit_f:
        return Resolved(frozenset(hidden_vertices), frozenset(hidden_edges), frozenset(hide_f))
    face_vertices = mesh.face_vertices
    explicit_corners = {v for f in explicit_f for v in face_vertices(f)} - hide_v
    all_faces = mesh.all_face_ids()
    if 2 * len(hide_f) > len(all_faces):
        # Most faces hidden (Isolate): walk the few visible faces instead. An edge / corner of an explicitly hidden
        # face that no visible face uses is hidden.
        face_edges = mesh.face_edges
        visible_edges: set[EdgeId] = set()
        visible_corners: set[VertexId] = set()
        for f in all_faces:
            if f not in hide_f:
                visible_corners.update(face_vertices(f))
                visible_edges.update(face_edges(f))
        only_faces = not hide_v  # every hidden face is explicit: an edge of hidden faces only is hidden
        for e in mesh.all_edge_ids():
            if e in hidden_edges or e in visible_edges:
                continue
            around = edge_faces(e)
            if around and (only_faces or any(f in explicit_f for f in around)):
                hidden_edges.add(e)
        hidden_vertices.update(explicit_corners - visible_corners)
    else:
        # Only an edge or corner of an explicitly hidden face can be hidden by its faces.
        face_edges = mesh.face_edges
        for e in {e for f in explicit_f for e in face_edges(f)} - hidden_edges:
            if all(f in hide_f for f in edge_faces(e)):
                hidden_edges.add(e)
        for v in explicit_corners:
            if all(f in hide_f for e in vertex_edges(v) for f in edge_faces(e)):
                hidden_vertices.add(v)
    return Resolved(frozenset(hidden_vertices), frozenset(hidden_edges), frozenset(hide_f))


def resolve_indexed(
    face_corners: Sequence[Sequence[int]],
    edges: Sequence[tuple[int, int]],
    vertices: AbstractSet[int],
    faces: AbstractSet[int],
) -> tuple[frozenset, frozenset]:
    """The same rule on index arrays (a derived topology such as the SubD control cage): returns the indices of the
    hidden faces and of the hidden edges."""
    if not vertices and not faces:
        return frozenset(), frozenset()
    hidden_faces = {
        i for i, corners in enumerate(face_corners)
        if i in faces or (vertices and not vertices.isdisjoint(corners))
    }
    edge_of = {(min(a, b), max(a, b)): i for i, (a, b) in enumerate(edges)}
    visible_face_edges: set[int] = set()
    for i, corners in enumerate(face_corners):
        if i in hidden_faces:
            continue
        n = len(corners)
        for k in range(n):
            a, b = corners[k], corners[(k + 1) % n]
            e = edge_of.get((min(a, b), max(a, b)))
            if e is not None:
                visible_face_edges.add(e)
    face_edges: set[int] = set()  # edges of explicitly hidden faces: only they can be hidden by their faces
    for i in faces:
        corners = face_corners[i]
        n = len(corners)
        for k in range(n):
            a, b = corners[k], corners[(k + 1) % n]
            e = edge_of.get((min(a, b), max(a, b)))
            if e is not None:
                face_edges.add(e)
    hidden_edges = {
        i for i, (a, b) in enumerate(edges)
        if a in vertices or b in vertices or (i in face_edges and i not in visible_face_edges)
    }
    return frozenset(hidden_faces), frozenset(hidden_edges)
