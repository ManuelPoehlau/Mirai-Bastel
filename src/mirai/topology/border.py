"""Border Select and Cap (Manu 2026-10-25: "Border Select und Cap/Close brauch ich").

A *border* is an open boundary of the surface: a chain of edges that each have exactly one face
(3ds Max "Border", Blender "Select Boundary Loop" / Alt+click on a hole, Maya "Select Border Edge").

- `border_select` maps a V/E/F selection onto whole borders: in vertex / edge mode each selected
  border element grows to its full border loop (nothing selected = every border of the mesh, to
  find holes); in face mode the outline of the selected region becomes the edge selection.
- `apply_cap` closes each closed border loop that the selection touches with one n-gon (3ds Max
  Cap, Blender Fill on a hole) whose winding is the opposite of its neighbours', so normals stay
  consistent. Mutates only; the caller owns the transaction (`Application._mesh_transaction`).

Only the public Mesh API is used (`edge_faces`, `add_face`); Core stays untouched.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from core import EdgeId, FaceId, SelectionMode, VertexId
from core.mesh import Mesh

CAP_LABEL = "Cap"
BORDER_LABEL = "Border"


class CapRefused(ValueError):
    """The selection cannot be capped; mesh and history are unchanged."""


@dataclass(frozen=True)
class BorderLoop:
    """One border, walked in order: `vertices[i]` -> `vertices[i + 1]` is `edges[i]`. Closed: the
    last edge returns to `vertices[0]` (len(vertices) == len(edges)); open: the walk stopped at a
    vertex where more than two border edges meet (a bow-tie), len(vertices) == len(edges) + 1."""

    vertices: tuple[VertexId, ...]
    edges: tuple[EdgeId, ...]
    closed: bool


def is_border_edge(mesh: Mesh, edge: EdgeId) -> bool:
    return len(mesh.edge_faces(edge)) == 1


def border_edges(mesh: Mesh) -> set[EdgeId]:
    return {e for e in mesh.all_edge_ids() if is_border_edge(mesh, e)}


def _border_edges_at(mesh: Mesh, vertex: VertexId) -> list[EdgeId]:
    return [e for e in mesh.vertex_edges(vertex) if is_border_edge(mesh, e)]


def _other(mesh: Mesh, edge: EdgeId, vertex: VertexId) -> VertexId:
    a, b = mesh.edge_vertices(edge)
    return b if vertex == a else a


def _walk(mesh: Mesh, start: VertexId, edge: EdgeId) -> tuple[list[VertexId], list[EdgeId], bool]:
    """From `start` along `edge` and on through vertices with exactly two border edges."""
    vertices, edges = [start], [edge]
    current = _other(mesh, edge, start)
    while current != start:
        vertices.append(current)
        nxt = [e for e in _border_edges_at(mesh, current) if e != edges[-1]]
        if len(nxt) != 1:
            return vertices, edges, False
        edges.append(nxt[0])
        current = _other(mesh, nxt[0], current)
    return vertices, edges, True


def border_loop(mesh: Mesh, edge: EdgeId) -> BorderLoop:
    """The border through `edge` (a border edge). The walk ends at bow-tie vertices (more than two
    border edges), as Blender's boundary loop does; then the loop is open."""
    if not is_border_edge(mesh, edge):
        raise ValueError(f"{edge!r} is not a border edge")
    a, b = mesh.edge_vertices(edge)
    forward_v, forward_e, closed = _walk(mesh, a, edge)
    if closed:
        return BorderLoop(tuple(forward_v), tuple(forward_e), True)
    # Open: walk backwards from `a` too and join the two halves at `edge`.
    back_v, back_e, _ = _walk(mesh, b, edge)
    vertices = list(reversed(back_v[1:])) + forward_v
    edges = list(reversed(back_e[1:])) + forward_e
    return BorderLoop(tuple(vertices), tuple(edges), False)


def border_loops(mesh: Mesh, edges: Iterable[EdgeId]) -> list[BorderLoop]:
    """The distinct borders through the border edges among `edges`, in id order of their seeds."""
    loops: list[BorderLoop] = []
    seen: set[EdgeId] = set()
    for edge in sorted(edges, key=int):
        if edge in seen or not mesh.is_valid_edge(edge) or not is_border_edge(mesh, edge):
            continue
        loop = border_loop(mesh, edge)
        seen.update(loop.edges)
        loops.append(loop)
    return loops


def _seed_edges(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> set[EdgeId]:
    """The border edges a V/E/F selection points at: selected border edges, border edges at a
    selected vertex, border edges of a selected face."""
    ids = set(ids)
    if mode is SelectionMode.EDGE:
        return {e for e in ids if mesh.is_valid_edge(e) and is_border_edge(mesh, e)}
    if mode is SelectionMode.VERTEX:
        return {e for v in ids if mesh.is_valid_vertex(v) for e in _border_edges_at(mesh, v)}
    if mode is SelectionMode.FACE:
        return {e for f in ids if mesh.is_valid_face(f) for e in mesh.face_edges(f) if is_border_edge(mesh, e)}
    raise ValueError(f"Border needs a component mode, not {mode!r}")


def region_outline(mesh: Mesh, faces: Iterable[FaceId]) -> set[EdgeId]:
    """The edges between the face region and the rest (or the open border): Blender "Select
    Boundary Loop"."""
    region = {f for f in faces if mesh.is_valid_face(f)}
    return {
        e
        for f in region
        for e in mesh.face_edges(f)
        if sum(1 for g in mesh.edge_faces(e) if g in region) == 1
    }


def border_select(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> tuple[SelectionMode, set]:
    """(mode, ids) of the Border selection. Vertex / edge mode: the whole border(s) the selection
    touches, in that mode; with nothing selected, all borders of the mesh. Face mode: the outline
    of the selected faces in edge mode (Blender "Select Boundary Loop"). Empty ids = nothing found."""
    ids = set(ids)
    if mode is SelectionMode.FACE:
        return SelectionMode.EDGE, region_outline(mesh, ids)
    seeds = _seed_edges(mesh, mode, ids) if ids else border_edges(mesh)
    edges = {e for loop in border_loops(mesh, seeds) for e in loop.edges}
    if mode is SelectionMode.VERTEX:
        return mode, {v for e in edges for v in mesh.edge_vertices(e)}
    return mode, edges


def cap_loops(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> list[BorderLoop]:
    """The closed borders the selection touches. Raises `CapRefused` if it touches no border or
    only open ones (a bow-tie vertex splits the hole; nothing is guessed there)."""
    loops = border_loops(mesh, _seed_edges(mesh, mode, ids))
    if not loops:
        raise CapRefused("no open border in the selection")
    open_loops = [loop for loop in loops if not loop.closed]
    if open_loops:
        raise CapRefused("border is not closed (several borders meet at one point)")
    return loops


def cap_winding(mesh: Mesh, loop: BorderLoop) -> list[VertexId]:
    """The loop's vertices in the order the cap face uses: against the neighbour face along the
    first edge, so the cap's normal agrees with the surface around it."""
    first, second = loop.vertices[0], loop.vertices[1]
    (face,) = mesh.edge_faces(loop.edges[0])
    boundary = mesh.face_vertices(face)
    i = boundary.index(first)
    if boundary[(i + 1) % len(boundary)] == second:
        return list(reversed(loop.vertices))
    return list(loop.vertices)


def check_cappable(mesh: Mesh, loop: BorderLoop) -> None:
    if len(loop.vertices) < 3:
        raise CapRefused("hole has fewer than three points")
    neighbours = {mesh.edge_faces(e)[0] for e in loop.edges}
    if len(neighbours) == 1:
        # The border is one face's whole outline: the cap would be its back side.
        raise CapRefused("would put a second face onto the same points")


def apply_cap(mesh: Mesh, mode: SelectionMode, ids: Iterable) -> list[FaceId]:
    """Closes each closed border the selection touches with one face; returns the new faces.
    Checks every loop before the first `add_face`, so a refusal leaves the mesh untouched."""
    loops = cap_loops(mesh, mode, ids)
    for loop in loops:
        check_cappable(mesh, loop)
    return [mesh.add_face(cap_winding(mesh, loop)) for loop in loops]
