"""Topological selection steps (WP Toolbox Gaps A1, Manu 2026-10-23): Grow / Shrink, grow and
shrink along the loop, step to the parallel loop.

Pure queries on the edit mesh: in → the selected ids, out → the new ids; no mutation, no
History (like a click, `core.selection`). Built on the conservative loop/ring steps of
`mirai.topology.loop_ring`, so a loop here stops where Shift+L stops (poles, non-quads,
borders).

- Grow / Shrink follow the active mode: vertices over edges, edges over shared vertices, faces
  over shared vertices (Blender's default). Shrink drops every selected element that touches an
  unselected neighbour of the same kind.
- Loop grow / shrink: each open piece of selected loop edges gains / loses one edge at both of
  its ends. Closed loops do not change.
- Parallel loop: every piece of selected loop edges moves across its quads to the parallel
  piece on one side (`ring_step`); which side is the caller's choice (`shift_loops`).
"""

from __future__ import annotations

from dataclasses import dataclass

from core import EdgeId, FaceId, SelectionMode, VertexId

from .loop_ring import _loop_step, _ring_step


# -- Grow / Shrink ------------------------------------------------------------------------


def _vertex_neighbours(mesh, vertex: VertexId) -> set[VertexId]:
    out = set()
    for edge in mesh.vertex_edges(vertex):
        a, b = mesh.edge_vertices(edge)
        out.add(b if a == vertex else a)
    return out


def _edge_neighbours(mesh, edge: EdgeId) -> set[EdgeId]:
    out = set()
    for vertex in mesh.edge_vertices(edge):
        out.update(mesh.vertex_edges(vertex))
    out.discard(edge)
    return out


def _face_neighbours(mesh, face: FaceId) -> set[FaceId]:
    out = set()
    for vertex in mesh.face_vertices(face):
        for edge in mesh.vertex_edges(vertex):
            out.update(mesh.edge_faces(edge))
    out.discard(face)
    return out


def _neighbours(mesh, mode: SelectionMode):
    if mode is SelectionMode.VERTEX:
        return lambda i: _vertex_neighbours(mesh, i)
    if mode is SelectionMode.EDGE:
        return lambda i: _edge_neighbours(mesh, i)
    if mode is SelectionMode.FACE:
        return lambda i: _face_neighbours(mesh, i)
    raise ValueError(f"no component neighbourhood in mode {mode}")


def grow(mesh, mode: SelectionMode, ids) -> set:
    """`ids` plus every element of the same kind adjacent to one of them."""
    neighbours = _neighbours(mesh, mode)
    out = set(ids)
    for i in ids:
        out.update(neighbours(i))
    return out


def shrink(mesh, mode: SelectionMode, ids) -> set:
    """`ids` minus every element that has an unselected neighbour of the same kind."""
    neighbours = _neighbours(mesh, mode)
    selected = set(ids)
    return {i for i in selected if neighbours(i) <= selected}


# -- Pieces of selected loop edges ---------------------------------------------------------


@dataclass(frozen=True)
class LoopPiece:
    """A run of selected edges that follow each other along an edge loop.

    `vertices[i] → vertices[i + 1]` is `edges[i]` (for a closed piece the last edge runs back
    to `vertices[0]`, which is not repeated)."""

    edges: tuple[EdgeId, ...]
    vertices: tuple[VertexId, ...]
    closed: bool


def _selected_step(mesh, edge: EdgeId, vertex: VertexId, selected: set[EdgeId]):
    step = _loop_step(mesh, edge, vertex)
    if step is None or step[0] not in selected:
        return None
    return step


def loop_pieces(mesh, edges) -> list[LoopPiece]:
    """The selected edges split into ordered loop pieces (a lone edge is a piece of one)."""
    selected = set(edges)
    seen: set[EdgeId] = set()
    pieces = []
    for start in sorted(selected):
        if start in seen:
            continue
        a, b = mesh.edge_vertices(start)

        def walk(edge, vertex):
            run = []
            while True:
                step = _selected_step(mesh, edge, vertex, selected)
                if step is None or step[0] in seen or step[0] == start:
                    return run, step is not None and step[0] == start
                edge, vertex = step
                seen.add(edge)
                run.append((edge, vertex))

        seen.add(start)
        forward, closed = walk(start, b)
        if closed:
            edge_list = [start] + [e for e, _ in forward]
            vertex_list = [a, b] + [v for _, v in forward[:-1]]
            pieces.append(LoopPiece(tuple(edge_list), tuple(vertex_list), True))
            continue
        backward, _ = walk(start, a)
        # backward[i] = (edge, the vertex it leads to, away from `start`)
        edge_list = [e for e, _ in reversed(backward)] + [start] + [e for e, _ in forward]
        vertex_list = [v for _, v in reversed(backward)] + [a, b] + [v for _, v in forward]
        pieces.append(LoopPiece(tuple(edge_list), tuple(vertex_list), False))
    return pieces


def loop_grow(mesh, edges) -> set[EdgeId]:
    """The selected edges plus, at both ends of each open piece, the next loop edge."""
    out = set(edges)
    for piece in loop_pieces(mesh, edges):
        if piece.closed:
            continue
        for edge, vertex in ((piece.edges[0], piece.vertices[0]), (piece.edges[-1], piece.vertices[-1])):
            step = _loop_step(mesh, edge, vertex)
            if step is not None:
                out.add(step[0])
    return out


def loop_shrink(mesh, edges) -> set[EdgeId]:
    """The selected edges minus the end edges of each open piece (a lone edge goes)."""
    out = set(edges)
    for piece in loop_pieces(mesh, edges):
        if not piece.closed:
            out.discard(piece.edges[0])
            out.discard(piece.edges[-1])
    return out


# -- Parallel loop -------------------------------------------------------------------------


def _face_runs(mesh, face: FaceId, a: VertexId, b: VertexId) -> bool:
    """True if the face's boundary runs a → b."""
    ring = mesh.face_vertices(face)
    i = ring.index(a)
    return ring[(i + 1) % len(ring)] == b


def _side_face(mesh, edge: EdgeId, a: VertexId, b: VertexId, left: bool) -> FaceId | None:
    """The face on the left (boundary runs a → b) or right (b → a) of edge a → b."""
    for face in mesh.edge_faces(edge):
        if _face_runs(mesh, face, a, b) == left:
            return face
    return None


def piece_edge_ends(piece: LoopPiece, i: int) -> tuple[VertexId, VertexId]:
    vertices = piece.vertices
    return vertices[i], vertices[(i + 1) % len(vertices)]


def shifted_piece(mesh, piece: LoopPiece, left: bool) -> tuple[EdgeId, ...] | None:
    """The piece moved one quad to its left / right side (sides by the faces' winding, so the
    same for the whole piece), or None if a quad on that side is missing."""
    out = []
    for i, edge in enumerate(piece.edges):
        a, b = piece_edge_ends(piece, i)
        face = _side_face(mesh, edge, a, b, left)
        if face is None:
            return None
        step = _ring_step(mesh, edge, face)
        if step is None:
            return None
        out.append(step[0])
    return tuple(out)
