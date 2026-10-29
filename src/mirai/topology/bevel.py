"""Bevel / Chamfer (2026-10-29, Manu: "Chamfer/Bevel (Edges, Vertices)", Grundfunktion; `PROVISIONAL`).

Hold `Ctrl+B` and drag: one segment, the width follows the mouse (right = wider). Edge mode bevels
the selected edges, face mode the edges of the selected faces, vertex mode the selected vertices
(Blender Bevel with one segment; Maya Chamfer Vertex).

**Edge bevel.** Every beveled edge becomes a strip face between two new edges, one in each of its
faces at the width from the old edge. Around an end vertex the faces are cut into *sectors* by the
beveled edges (and the mesh border); each sector gets one new vertex that replaces the old vertex in
all of its faces:

- a sector of one face (two beveled edges of that face meet) - the vertex sits inside the face on the
  miter of the two edges;
- a sector with unbeveled edges - the vertex slides along the middle one of them (on the border: along
  the border edge), at the width from the beveled edge.

Three or more beveled edges at a vertex get a cap face over the new vertices (a cube corner becomes a
triangle); two continue the strip; at the mesh border the strips end on the border. One beveled edge
ending at a vertex inside the mesh (a *terminal* end) gets two new vertices on the edges next to it;
with three edges at the vertex the old vertex goes (Blender's corner cut), with more it stays and the
strip ends in it (the hexagon of a single beveled grid edge).

**Vertex bevel.** Every edge at a selected vertex gets a new vertex at the width from it, every face
around it loses that corner, and a cap face closes the hole (on the border the cut stays open).

Topology is built once at the start of the drag (`offset_build`): the faces around the vertices are
rebuilt with the replacement corners, then the strips and caps are added, wound against their
neighbours; old edges and vertices left without a face are removed. Refused before any mutation: a
beveled edge on the border, an edge or vertex without faces, a vertex whose faces do not form one fan
(non-manifold or flipped winding).

UVs (AD-026): a rebuilt face gives a new corner the UV of the corner it replaces; strips and caps take
their UVs from their neighbours (`Mesh.add_face` infers them). Point layers: a new vertex is a copy of
the vertex it grew from.
"""

from __future__ import annotations

from dataclasses import dataclass

from core import EdgeId, FaceId, Mesh, SelectionMode, VertexId

from .offset_build import (
    OffsetBuild,
    OffsetRefused,
    collapse_width,
    cross,
    face_normal,
    inward,
    length,
    miter,
    scale,
    sub,
    unit,
)

BEVEL_LABEL = "Bevel"

#: The width stops at this fraction of the first width at which an edge would shrink to zero (`PROVISIONAL`).
LIMIT_FRACTION = 0.98

#: The smallest sine between a slide edge and its beveled edge that still sets the slide speed; flatter
#: angles slide no faster (`PROVISIONAL`).
MIN_SINE = 0.25


class BevelRefused(OffsetRefused):
    """Bevel cannot run on this selection; the message is the status line."""


@dataclass(frozen=True)
class Fan:
    """The faces around a vertex in winding order: `faces[i]` lies between `edges[i]` (its edge
    into the vertex) and `edges[i + 1]` (its edge out of it). Closed: `len(edges) == len(faces)`
    (indices wrap); open (on the border): `len(edges) == len(faces) + 1`."""

    vertex: VertexId
    edges: tuple[EdgeId, ...]
    faces: tuple[FaceId, ...]
    closed: bool


@dataclass(frozen=True)
class BevelPlan:
    """The validated input: the vertices to bevel (vertex mode) or the edges (edge / face mode), and the
    fan of every vertex the bevel changes."""

    vertex_mode: bool
    edges: frozenset[EdgeId]
    vertices: frozenset[VertexId]
    fans: dict[VertexId, Fan]


def _other(mesh: Mesh, edge: EdgeId, vertex: VertexId) -> VertexId:
    a, b = mesh.edge_vertices(edge)
    return b if a == vertex else a


def _edge_between(mesh: Mesh, a: VertexId, b: VertexId) -> EdgeId:
    for e in mesh.vertex_edges(a):
        if b in mesh.edge_vertices(e):
            return e
    raise BevelRefused(f"{BEVEL_LABEL}: broken face (no edge between two corners)")


def fan(mesh: Mesh, vertex: VertexId) -> Fan:
    """The fan of `vertex`. Raises `BevelRefused` if its faces do not form one fan."""
    edges = mesh.vertex_edges(vertex)
    faces = {f for e in edges for f in mesh.edge_faces(e)}
    broken = BevelRefused(f"{BEVEL_LABEL}: a vertex is not on one fan of faces (non-manifold or flipped faces)")
    if not faces or any(not mesh.edge_faces(e) for e in edges):
        raise BevelRefused(f"{BEVEL_LABEL}: an edge without faces is in the way")
    into: dict[FaceId, EdgeId] = {}
    out: dict[FaceId, EdgeId] = {}
    by_into: dict[EdgeId, FaceId] = {}
    for f in faces:
        corners = mesh.face_vertices(f)
        i = corners.index(vertex)
        into[f] = _edge_between(mesh, corners[i - 1], vertex)
        out[f] = _edge_between(mesh, vertex, corners[(i + 1) % len(corners)])
        if into[f] in by_into:
            raise broken
        by_into[into[f]] = f
    border = [e for e in edges if len(mesh.edge_faces(e)) == 1]
    if any(len(mesh.edge_faces(e)) > 2 for e in edges):
        raise broken
    if border:
        starts = [e for e in border if e in by_into]
        if len(border) != 2 or len(starts) != 1:
            raise broken
        f = by_into[starts[0]]
        order_e, order_f = [starts[0]], []
        while f is not None:
            order_f.append(f)
            order_e.append(out[f])
            f = by_into.get(out[f])
    else:
        start = min(faces)
        order_e, order_f = [], []
        f = start
        while True:
            order_e.append(into[f])
            order_f.append(f)
            f = by_into.get(out[f])
            if f is None:
                raise broken
            if f == start:
                break
    if len(order_f) != len(faces) or len(set(order_e)) != len(edges) or len(order_e) != len(set(order_e)):
        raise broken
    return Fan(vertex, tuple(order_e), tuple(order_f), not border)


def plan_bevel(mesh: Mesh, mode: SelectionMode, ids) -> BevelPlan:
    """Validate the bevel of `ids` (vertices in vertex mode, edges in edge mode, faces in face mode -
    their edges with a face on both sides). Pure; raises `BevelRefused`."""
    if mode is SelectionMode.VERTEX:
        vertices = frozenset(v for v in ids if mesh.is_valid_vertex(v))
        if not vertices:
            raise BevelRefused(f"{BEVEL_LABEL}: select or hover a vertex")
        fans = {v: fan(mesh, v) for v in sorted(vertices)}
        return BevelPlan(True, frozenset(), vertices, fans)
    if mode is SelectionMode.FACE:
        faces = [f for f in ids if mesh.is_valid_face(f)]
        edges = frozenset(e for f in faces for e in mesh.face_edges(f) if len(mesh.edge_faces(e)) == 2)
    elif mode is SelectionMode.EDGE:
        edges = frozenset(e for e in ids if mesh.is_valid_edge(e))
        if any(len(mesh.edge_faces(e)) != 2 for e in edges):
            raise BevelRefused(f"{BEVEL_LABEL}: a selected edge lies on the border (needs a face on both sides)")
    else:
        raise BevelRefused(f"{BEVEL_LABEL}: vertex, edge or face mode needed (1/2/3)")
    if not edges:
        raise BevelRefused(f"{BEVEL_LABEL}: select or hover an edge (or faces with inner edges)")
    ends = {v for e in edges for v in mesh.edge_vertices(e)}
    fans = {v: fan(mesh, v) for v in sorted(ends)}
    if any(f.closed and len(f.edges) < 3 for f in fans.values()):
        raise BevelRefused(f"{BEVEL_LABEL}: a beveled edge ends at a vertex with only two edges (dissolve it first)")
    return BevelPlan(False, edges, frozenset(), fans)


# -- building ---------------------------------------------------------------------------------------


class _Builder:
    """Collects, per (face, old corner), the corners that replace it, the new faces and the moves."""

    def __init__(self, mesh: Mesh) -> None:
        self.mesh = mesh
        self.corner: dict[tuple[FaceId, VertexId], list[VertexId]] = {}
        self.moves: dict[VertexId, tuple] = {}
        self.keys: dict[VertexId, tuple] = {}
        self.new_faces: list[list[VertexId]] = []

    def vertex(self, source: VertexId, direction, key: tuple) -> VertexId:
        origin = self.mesh.vertex_position(source)
        vid = self.mesh.add_vertex(origin, origin=((source, 1.0),))
        self.moves[vid] = (origin, direction)
        self.keys[vid] = key
        return vid

    def unit_edge(self, vertex: VertexId, edge: EdgeId):
        pos = self.mesh.vertex_position
        return unit(sub(pos(_other(self.mesh, edge, vertex)), pos(vertex)))


def _sine(a, b) -> float:
    if a is None or b is None:
        return 1.0
    return length(cross(a, b))


def _slide(builder: _Builder, v: VertexId, along: EdgeId, bounds, key: tuple) -> VertexId:
    """A new vertex at `v` sliding along `along`, at the width from the beveled edges `bounds`."""
    u = builder.unit_edge(v, along)
    if u is None:
        raise BevelRefused(f"{BEVEL_LABEL}: an edge of zero length is in the way")
    sines = [_sine(u, builder.unit_edge(v, b)) for b in bounds]
    s = max(MIN_SINE, sum(sines) / len(sines)) if sines else 1.0
    return builder.vertex(v, scale(u, 1.0 / s), key)


def _miter_vertex(builder: _Builder, v: VertexId, first: FaceId, last: FaceId, key: tuple) -> VertexId:
    """A new vertex at `v` on the miter of the edge into `first` and the edge out of `last` (the same
    face for a one-face sector), each offset into its own face."""
    mesh = builder.mesh
    pos = mesh.vertex_position
    corners = mesh.face_vertices(first)
    p = inward(face_normal(mesh, first), pos(corners[corners.index(v) - 1]), pos(v))
    corners = mesh.face_vertices(last)
    q = inward(face_normal(mesh, last), pos(v), pos(corners[(corners.index(v) + 1) % len(corners)]))
    if p is None or q is None:
        raise BevelRefused(f"{BEVEL_LABEL}: an edge of zero length is in the way")
    return builder.vertex(v, miter(p, q), key)


def _bevel_vertex_fan(builder: _Builder, fan_: Fan, beveled: frozenset[EdgeId], ends: dict) -> None:
    """Edge bevel around one vertex: the replacement corners of its faces, `ends[(v, e)]` (the strip's
    corners at `v`, from the side where `e` leaves a face to the side where it enters one) and its cap."""
    v = fan_.vertex
    k_e = len(fan_.edges)
    k_f = len(fan_.faces)
    marks = [i for i, e in enumerate(fan_.edges) if e in beveled]
    if fan_.closed and len(marks) == 1:
        # Terminal end: new vertices on the edges next to the beveled one.
        b = marks[0]
        e0 = fan_.edges[b]
        first, last = fan_.edges[(b + 1) % k_e], fan_.edges[(b - 1) % k_e]
        a = _slide(builder, v, first, (e0,), (v, first))
        z = _slide(builder, v, last, (e0,), (v, last))
        f_first, f_last = fan_.faces[b], fan_.faces[(b - 1) % k_f]
        builder.corner[(f_first, v)] = [a]
        builder.corner[(f_last, v)] = [z]
        if k_f == 3:
            middle = fan_.faces[(b + 1) % k_f]
            builder.corner[(middle, v)] = [a, z]
            ends[(v, e0)] = [z, a]
        else:
            builder.corner[(fan_.faces[(b + 1) % k_f], v)] = [a, v]
            builder.corner[(fan_.faces[(b - 2) % k_f], v)] = [v, z]
            ends[(v, e0)] = [z, v, a]
        return

    # Sectors: runs of faces between consecutive bounding edges (beveled, or the border of an open fan).
    if fan_.closed:
        runs = [(marks[j], marks[(j + 1) % len(marks)]) for j in range(len(marks))]
    else:
        bounds = [0, *marks, k_e - 1]
        runs = [(bounds[j], bounds[j + 1]) for j in range(len(bounds) - 1)]
    sector_vertex: dict[int, VertexId] = {}  # face index -> its sector's new vertex
    cap: list[VertexId] = []
    for start, stop in runs:
        span = (stop - start) % k_e if fan_.closed else stop - start
        face_indices = [(start + j) % k_f for j in range(span)] if fan_.closed else list(range(start, stop))
        inner = [fan_.edges[(start + j) % k_e] for j in range(1, span)]
        bounding = [e for e in (fan_.edges[start], fan_.edges[stop % k_e]) if e in beveled]
        key = (v, frozenset(fan_.faces[i] for i in face_indices))
        first_face, last_face = fan_.faces[face_indices[0]], fan_.faces[face_indices[-1]]
        if len(inner) == 1:
            new = _slide(builder, v, inner[0], bounding, key)
        elif len(bounding) == 2:
            # One face: the miter inside it; several unbeveled edges between: where the two offset lines meet.
            new = _miter_vertex(builder, v, first_face, last_face, key)
        elif inner:
            # An end sector on the border with several edges: along the one next to the beveled edge.
            new = _slide(builder, v, inner[-1] if fan_.edges[stop % k_e] in beveled else inner[0], bounding, key)
        else:
            border = fan_.edges[start] if fan_.edges[start] not in beveled else fan_.edges[stop % k_e]
            new = _slide(builder, v, border, bounding, key)
        for i in face_indices:
            sector_vertex[i] = new
            builder.corner[(fan_.faces[i], v)] = [new]
        cap.append(new)
    for i in marks:
        # Edge i enters face i and leaves face i - 1.
        ends[(v, fan_.edges[i])] = [sector_vertex[(i - 1) % k_f], sector_vertex[i]]
    if fan_.closed and len(marks) >= 3:
        builder.new_faces.append(list(reversed(cap)))


def _bevel_corner(builder: _Builder, fan_: Fan) -> None:
    """Vertex bevel of one vertex: a new vertex on each of its edges, a cap over them."""
    v = fan_.vertex
    on_edge = []
    for e in fan_.edges:
        u = builder.unit_edge(v, e)
        if u is None:
            raise BevelRefused(f"{BEVEL_LABEL}: an edge of zero length is in the way")
        on_edge.append(builder.vertex(v, u, (v, e)))
    k_e = len(fan_.edges)
    for i, f in enumerate(fan_.faces):
        builder.corner[(f, v)] = [on_edge[i], on_edge[(i + 1) % k_e]]
    if k_e >= 3:
        builder.new_faces.append(list(reversed(on_edge)))


def build_bevel(mesh: Mesh, plan: BevelPlan) -> OffsetBuild:
    """Build the bevel of `plan` (new vertices at width 0). `faces` = the new strips and caps."""
    builder = _Builder(mesh)
    ends: dict[tuple[VertexId, EdgeId], list[VertexId]] = {}
    for v, fan_ in plan.fans.items():
        if plan.vertex_mode:
            _bevel_corner(builder, fan_)
        else:
            _bevel_vertex_fan(builder, fan_, plan.edges, ends)

    strips = []
    for e in sorted(plan.edges):
        v1, v2 = mesh.edge_vertices(e)
        # `ends[(v1, e)]` runs from the face that leaves v1 along e (it runs v1 -> v2) to the other one,
        # `ends[(v2, e)]` back: one closed loop, wound against both faces.
        strips.append(ends[(v1, e)] + ends[(v2, e)])

    touched = sorted({f for (f, _) in builder.corner})
    has_uvs = mesh.has_face_uvs()
    rebuilt = []
    for f in touched:
        corners = mesh.face_vertices(f)
        uvs = mesh.face_uvs(f) if has_uvs else None
        boundary, new_uvs = [], []
        for i, c in enumerate(corners):
            replacement = builder.corner.get((f, c), [c])
            boundary.extend(replacement)
            if uvs is not None:
                new_uvs.extend([uvs[i]] * len(replacement))
        rebuilt.append((f, boundary, tuple(new_uvs) if uvs is not None else None))
    old_edges = {e for f in touched for e in mesh.face_edges(f)}
    for f in touched:
        mesh.remove_face(f)
    for _, boundary, uvs in rebuilt:
        mesh.add_face(boundary, uvs, infer_uvs=False)
    created = [mesh.add_face(boundary) for boundary in strips]
    created += [mesh.add_face(boundary) for boundary in builder.new_faces]
    orphans = [e for e in old_edges if mesh.is_valid_edge(e) and not mesh.edge_faces(e)]
    if orphans:
        mesh.delete_edges(orphans)
    limit = LIMIT_FRACTION * collapse_width(mesh, {vid: d for vid, (_, d) in builder.moves.items()})
    return OffsetBuild(moves=builder.moves, keys=builder.keys, limit=limit, faces=created)

