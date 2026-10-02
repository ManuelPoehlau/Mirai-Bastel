"""Uniform Catmull-Clark subdivision as topology + stencils (GL-free, pure Python).

WP-SUBD-LAB-01 Slice 1, handoff D1/D5/D6. No NumPy, no GL, no `Scene`.

What is built, once per (control topology, level):

- the refined face list (all quads, `n` quads per `n`-gon),
- provenance: which control vertex/edge/face every derived vertex is born
  from, and which control face every derived face lies in,
- isoline segments (the derived edges that lie along a control edge — for
  display only),
- a **stencil** per derived vertex: sparse `{control_vertex_index: weight}`
  composed across levels, so positions at level L follow from the control
  positions in one pass (`apply_full`), plus the **inverse index**
  `control vertex -> derived vertices whose stencil references it`, so a
  vertex drag only touches those (`apply_local`).

Catmull-Clark rules (research §3.1/3.2, written as stencils on the previous
level, then composed):

- face point = mean of the face's vertices
- interior edge point = mean(2 endpoints, 2 adjacent face points)
- boundary edge point = midpoint
- interior vertex point = (F + 2R + (n-3)P) / n   (F = mean of incident face
  points, R = mean of incident edge midpoints, P = old position, n = valence)
- boundary vertex with exactly two boundary edges = (P_prev + 6P + P_next) / 8

Input that does not satisfy the manifold assumptions behind these rules
(edge with more than two faces, loose edge/vertex, boundary vertex without
exactly two boundary edges, vertex whose faces do not form one fan) raises
`SubdUnsupportedError` with a German message — never silent garbage.

Indices, not ids: control vertices/edges/faces are addressed by their
position in `ControlTopology.vertex_ids/edge_ids/face_ids` (core ids are
opaque handles, AD-001). Derived vertices are plain list indices
`0..n_verts-1`, ordered `[vertex points, edge points, face points]` of the
previous level.

The derived surface is throw-away display data (D1): it never replaces the
control mesh and nothing here writes back to it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

Vec3 = tuple[float, float, float]
Stencil = tuple[tuple[int, ...], tuple[float, ...]]

#: Provenance kinds of a derived vertex (`SubdLevel.vert_kind`).
KIND_VERTEX = 0
KIND_EDGE = 1
KIND_FACE = 2
KIND_NAMES = {KIND_VERTEX: "vertex", KIND_EDGE: "edge", KIND_FACE: "face"}


class SubdUnsupportedError(ValueError):
    """The control mesh is outside what the uniform Catmull-Clark rules cover."""


# -- control mesh extraction ---------------------------------------------------------


@dataclass(frozen=True)
class ControlTopology:
    """Index view of a control `core.Mesh` (topology only; positions are separate)."""

    vertex_ids: tuple
    edge_ids: tuple
    face_ids: tuple
    #: control edges as (vertex index, vertex index), in `edge_ids` order
    edges: tuple[tuple[int, int], ...]
    #: control faces as tuples of vertex indices (core boundary order)
    faces: tuple[tuple[int, ...], ...]

    @property
    def face_sizes(self) -> tuple[int, ...]:
        return tuple(len(f) for f in self.faces)


def extract_control(mesh) -> tuple[ControlTopology, list[Vec3]]:
    """Reads `mesh` through the core query API only. Returns the validated
    topology and the current vertex positions (indexed like `vertex_ids`)."""
    vertex_ids = tuple(mesh.all_vertex_ids())
    index = {vid: i for i, vid in enumerate(vertex_ids)}
    edge_ids = tuple(mesh.all_edge_ids())
    edges = []
    for eid in edge_ids:
        a, b = mesh.edge_vertices(eid)
        edges.append((index[a], index[b]))
    face_ids = tuple(mesh.all_face_ids())
    faces = tuple(tuple(index[v] for v in mesh.face_vertices(fid)) for fid in face_ids)
    topology = ControlTopology(vertex_ids, edge_ids, face_ids, tuple(edges), faces)
    _validate(topology)
    positions = [tuple(mesh.vertex_position(vid)) for vid in vertex_ids]
    return topology, positions


def _validate(topology: ControlTopology) -> None:
    """Raises `SubdUnsupportedError` unless every rule below has a well-defined
    stencil. Messages name the offending element by its core id."""
    n_verts = len(topology.vertex_ids)
    edge_of = {}
    for e, (a, b) in enumerate(topology.edges):
        edge_of[(a, b)] = e
        edge_of[(b, a)] = e
    edge_faces: list[list[int]] = [[] for _ in topology.edges]
    vert_faces: list[list[int]] = [[] for _ in range(n_verts)]
    vert_edges: list[list[int]] = [[] for _ in range(n_verts)]
    for e, (a, b) in enumerate(topology.edges):
        vert_edges[a].append(e)
        vert_edges[b].append(e)

    for f, face in enumerate(topology.faces):
        if len(face) < 3 or len(set(face)) != len(face):
            raise SubdUnsupportedError(
                f"Fläche {int(topology.face_ids[f])} ist degeneriert "
                f"({len(face)} Ecken, doppelte Vertices) — Subdivision braucht Flächen mit mindestens 3 verschiedenen Ecken."
            )
        n = len(face)
        for k in range(n):
            e = edge_of.get((face[k], face[(k + 1) % n]))
            if e is None:
                raise SubdUnsupportedError(
                    f"Fläche {int(topology.face_ids[f])} hat eine Kante, die im Mesh nicht existiert."
                )
            edge_faces[e].append(f)
            vert_faces[face[k]].append(f)

    for e, faces in enumerate(edge_faces):
        if len(faces) > 2:
            raise SubdUnsupportedError(
                f"Kante {int(topology.edge_ids[e])} gehört zu {len(faces)} Flächen (nicht-manifold) — "
                "Subdivision unterstützt nur Kanten mit 1 oder 2 Flächen."
            )
        if not faces:
            raise SubdUnsupportedError(
                f"Kante {int(topology.edge_ids[e])} hat keine Fläche (lose Kante) — Subdivision braucht Flächen an jeder Kante."
            )

    for v in range(n_verts):
        faces = vert_faces[v]
        if not faces:
            raise SubdUnsupportedError(
                f"Vertex {int(topology.vertex_ids[v])} gehört zu keiner Fläche — Subdivision braucht Flächen an jedem Vertex."
            )
        boundary = [e for e in vert_edges[v] if len(edge_faces[e]) == 1]
        if boundary and len(boundary) != 2:
            raise SubdUnsupportedError(
                f"Randvertex {int(topology.vertex_ids[v])} hat {len(boundary)} Randkanten (erwartet: genau 2) — "
                "die Randregel von Catmull-Clark ist dafür nicht definiert."
            )
        if _fan_components(v, faces, vert_edges[v], edge_faces) != 1:
            raise SubdUnsupportedError(
                f"Vertex {int(topology.vertex_ids[v])}: seine Flächen bilden keinen zusammenhängenden Fächer "
                "(Berührpunkt zweier Teile) — nicht-manifold."
            )


def _fan_components(v: int, faces: list[int], edges: list[int], edge_faces: list[list[int]]) -> int:
    """Connected components of the faces around `v`, adjacent via edges at `v`."""
    parent = {f: f for f in faces}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in edges:
        fs = edge_faces[e]
        if len(fs) == 2:
            parent[find(fs[0])] = find(fs[1])
    return len({find(f) for f in faces})


# -- one refinement level -------------------------------------------------------------


@dataclass
class SubdLevel:
    """All position-independent data of one subdivision level (see module docstring)."""

    level: int
    n_verts: int
    #: refined faces (all quads for level >= 1)
    faces: list[tuple[int, ...]]
    #: per derived vertex: (control vertex indices, weights), composed from the control mesh
    stencils: list[Stencil]
    #: per control vertex index: derived vertices whose stencil references it
    inverse: list[list[int]]
    #: per derived vertex: KIND_* of the control element it is born from ...
    vert_kind: list[int]
    #: ... and that element's index (control vertex / edge / face index by kind)
    vert_origin: list[int]
    #: per derived face: index of the control face it lies in
    face_parent: list[int]
    #: derived edges lying along a control edge (display isolines) ...
    iso_edges: list[tuple[int, int]]
    #: ... and, parallel, the control edge index each belongs to
    iso_control_edge: list[int]
    #: seconds spent building this level only (refine + compose + inverse)
    build_seconds: float = 0.0
    # carried to the next level (not part of the public data)
    _edges: list[tuple[int, int]] = field(default_factory=list, repr=False)
    _edge_ctrl: list[int] = field(default_factory=list, repr=False)
    _edge_pface: list[int] = field(default_factory=list, repr=False)

    @property
    def stencil_entries(self) -> int:
        return sum(len(ix) for ix, _ in self.stencils)

    def apply_full(self, control_positions) -> list[Vec3]:
        """Positions of all derived vertices from the control positions."""
        xs = [p[0] for p in control_positions]
        ys = [p[1] for p in control_positions]
        zs = [p[2] for p in control_positions]
        out = []
        append = out.append
        for ix, ws in self.stencils:
            x = y = z = 0.0
            for i, w in zip(ix, ws):
                x += w * xs[i]
                y += w * ys[i]
                z += w * zs[i]
            append((x, y, z))
        return out

    def apply_local(self, control_vertex: int, control_positions, derived_positions: list) -> list[int]:
        """Recomputes, in place in `derived_positions`, exactly the derived
        vertices whose stencil references `control_vertex` (Wings-style local
        update, research §4.5). Reads the *current* control positions, so the
        result equals `apply_full` for those vertices (no accumulated delta).
        Returns the recomputed derived indices."""
        affected = self.inverse[control_vertex]
        stencils = self.stencils
        for d in affected:
            ix, ws = stencils[d]
            x = y = z = 0.0
            for i, w in zip(ix, ws):
                p = control_positions[i]
                x += w * p[0]
                y += w * p[1]
                z += w * p[2]
            derived_positions[d] = (x, y, z)
        return affected


def predicted_face_count(face_sizes, level: int) -> int:
    """Number of faces at `level` without building it: level 1 has one quad per
    control-face corner, every further level quadruples."""
    if level <= 0:
        return len(face_sizes)
    return sum(face_sizes) * 4 ** (level - 1)


def _identity_level(topology: ControlTopology) -> SubdLevel:
    n = len(topology.vertex_ids)
    return SubdLevel(
        level=0, n_verts=n, faces=list(topology.faces),
        stencils=[((i,), (1.0,)) for i in range(n)],
        inverse=[[i] for i in range(n)],
        vert_kind=[KIND_VERTEX] * n, vert_origin=list(range(n)),
        face_parent=list(range(len(topology.faces))),
        iso_edges=list(topology.edges),
        iso_control_edge=list(range(len(topology.edges))),
        _edges=list(topology.edges),
        _edge_ctrl=list(range(len(topology.edges))),
        _edge_pface=[-1] * len(topology.edges),
    )


def _refine(prev: SubdLevel, n_controls: int) -> SubdLevel:
    """One Catmull-Clark step: `prev` (level l) -> level l+1, stencils composed
    onto the control mesh (`n_controls` control vertices)."""
    started = time.perf_counter()
    faces, edges = prev.faces, prev._edges
    n_v, n_e, n_f = prev.n_verts, len(edges), len(faces)

    edge_of: dict[tuple[int, int], int] = {}
    for e, (a, b) in enumerate(edges):
        edge_of[(a, b)] = e
        edge_of[(b, a)] = e
    edge_faces: list[list[int]] = [[] for _ in range(n_e)]
    face_edges: list[list[int]] = []
    vert_edges: list[list[int]] = [[] for _ in range(n_v)]
    vert_faces: list[list[int]] = [[] for _ in range(n_v)]
    for e, (a, b) in enumerate(edges):
        vert_edges[a].append(e)
        vert_edges[b].append(e)
    for f, face in enumerate(faces):
        n = len(face)
        fe = []
        for k in range(n):
            e = edge_of[(face[k], face[(k + 1) % n])]
            fe.append(e)
            edge_faces[e].append(f)
            vert_faces[face[k]].append(f)
        face_edges.append(fe)

    ep_base = n_v
    fp_base = n_v + n_e

    # local stencils on level l, in new-vertex order [vertex pts, edge pts, face pts]
    local: list[dict[int, float]] = []
    for v in range(n_v):
        boundary = [e for e in vert_edges[v] if len(edge_faces[e]) == 1]
        if boundary:
            n1 = edges[boundary[0]][0] + edges[boundary[0]][1] - v
            n2 = edges[boundary[1]][0] + edges[boundary[1]][1] - v
            local.append({v: 0.75, n1: 0.125, n2: 0.125})
            continue
        n = len(vert_edges[v])
        w = {v: (n - 3) / n + 1.0 / n}
        inv_n2 = 1.0 / (n * n)
        for e in vert_edges[v]:
            q = edges[e][0] + edges[e][1] - v
            w[q] = w.get(q, 0.0) + inv_n2
        for f in vert_faces[v]:
            face = faces[f]
            share = inv_n2 / len(face)
            for u in face:
                w[u] = w.get(u, 0.0) + share
        local.append(w)
    for e, (a, b) in enumerate(edges):
        fs = edge_faces[e]
        if len(fs) == 2:
            w = {a: 0.25, b: 0.25}
            for f in fs:
                face = faces[f]
                share = 0.25 / len(face)
                for u in face:
                    w[u] = w.get(u, 0.0) + share
            local.append(w)
        else:
            local.append({a: 0.5, b: 0.5})
    for face in faces:
        share = 1.0 / len(face)
        local.append({u: share for u in face})

    # compose onto the control mesh
    prev_stencils = prev.stencils
    stencils: list[Stencil] = []
    inverse: list[list[int]] = [[] for _ in range(n_controls)]
    for d, terms in enumerate(local):
        acc: dict[int, float] = {}
        for k, w in terms.items():
            ix, ws = prev_stencils[k]
            for c, cw in zip(ix, ws):
                acc[c] = acc.get(c, 0.0) + w * cw
        keys = sorted(acc)
        stencils.append((tuple(keys), tuple(acc[c] for c in keys)))
        for c in keys:
            inverse[c].append(d)

    # refined faces: n quads per n-gon, orientation preserved
    new_faces: list[tuple[int, ...]] = []
    face_parent: list[int] = []
    for f, face in enumerate(faces):
        n = len(face)
        fe = face_edges[f]
        centre = fp_base + f
        for k in range(n):
            new_faces.append((face[k], ep_base + fe[k], centre, ep_base + fe[k - 1]))
            face_parent.append(prev.face_parent[f])

    # next level's edges: the two halves of every old edge, then one spoke per face corner
    new_edges: list[tuple[int, int]] = []
    edge_ctrl: list[int] = []
    edge_pface: list[int] = []
    for e, (a, b) in enumerate(edges):
        mid = ep_base + e
        new_edges.append((a, mid))
        new_edges.append((mid, b))
        edge_ctrl.extend((prev._edge_ctrl[e], prev._edge_ctrl[e]))
        edge_pface.extend((prev._edge_pface[e], prev._edge_pface[e]))
    for f, face in enumerate(faces):
        centre = fp_base + f
        for e in face_edges[f]:
            new_edges.append((ep_base + e, centre))
            edge_ctrl.append(-1)
            edge_pface.append(prev.face_parent[f])

    # provenance of the new vertices
    vert_kind = list(prev.vert_kind)
    vert_origin = list(prev.vert_origin)
    for e in range(n_e):
        ctrl = prev._edge_ctrl[e]
        if ctrl >= 0:
            vert_kind.append(KIND_EDGE)
            vert_origin.append(ctrl)
        else:
            vert_kind.append(KIND_FACE)
            vert_origin.append(prev._edge_pface[e])
    for f in range(n_f):
        vert_kind.append(KIND_FACE)
        vert_origin.append(prev.face_parent[f])

    iso_edges = [new_edges[i] for i, c in enumerate(edge_ctrl) if c >= 0]
    iso_control_edge = [c for c in edge_ctrl if c >= 0]

    return SubdLevel(
        level=prev.level + 1, n_verts=n_v + n_e + n_f, faces=new_faces,
        stencils=stencils, inverse=inverse,
        vert_kind=vert_kind, vert_origin=vert_origin, face_parent=face_parent,
        iso_edges=iso_edges, iso_control_edge=iso_control_edge,
        build_seconds=time.perf_counter() - started,
        _edges=new_edges, _edge_ctrl=edge_ctrl, _edge_pface=edge_pface,
    )


class SubdSurface:
    """Lazily built, cached subdivision levels of one control mesh.

    The control topology is read once (and validated) at construction;
    `level(n)` builds levels 1..n on first use. Positions are never stored
    here — the caller passes control positions to `SubdLevel.apply_*`.
    """

    def __init__(self, control_mesh) -> None:
        self.topology, self.initial_positions = extract_control(control_mesh)
        self._index_of = {vid: i for i, vid in enumerate(self.topology.vertex_ids)}
        self._levels: dict[int, SubdLevel] = {0: _identity_level(self.topology)}

    def index_of_vertex(self, vertex_id) -> int:
        return self._index_of[vertex_id]

    def predicted_face_count(self, level: int) -> int:
        return predicted_face_count(self.topology.face_sizes, level)

    def is_built(self, level: int) -> bool:
        return level in self._levels

    @property
    def built_levels(self) -> tuple[int, ...]:
        return tuple(sorted(self._levels))

    def level(self, n: int) -> SubdLevel:
        if n < 0:
            raise ValueError(f"Stufe muss >= 0 sein, nicht {n}")
        for k in range(1, n + 1):
            if k not in self._levels:
                self._levels[k] = _refine(self._levels[k - 1], len(self.topology.vertex_ids))
        return self._levels[n]

    def build_seconds(self, n: int) -> float:
        """Total seconds spent on levels 1..n (as currently cached)."""
        return sum(self._levels[k].build_seconds for k in range(1, n + 1))
