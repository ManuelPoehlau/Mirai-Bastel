"""Collapse V/E/F (WP Toolbox Gaps B1, 2026-10-23): each connected group of the selection falls
into one point at its centroid.

The groups are the connected components of the given edges (vertex mode: the edges between two
selected vertices; edge mode: the selected edges; face mode: the edges of the selected faces). A
selected vertex without such an edge is a group of its own and stays unchanged (Blender "Merge at
Center", per group). Each group is merged as a chain of `Mesh.collapse_edge`, so the existing,
tested primitive does the topology (edge re-pointing and merging, degenerate faces removed); the
survivor is then set to the centroid of the group's original positions.

ID continuity: per group one vertex of the group survives (the one `collapse_edge` keeps), the
other vertices of the group, the edges inside it and the faces that degenerate become invalid;
everything else keeps its id. No id is created.

Refusals (`CollapseRefused`, a `MeshError`) leave the mesh untouched: a face that would keep a
vertex twice (pinched), two faces that would become the same face, or an edge with more than two
faces. Blender lets these through and leaves non-manifold geometry behind; Mirai's invariants
(`tests/mesh_invariants.py`) do not allow it, so the operation refuses visibly (`PROVISIONAL`).
"""

from __future__ import annotations

from collections.abc import Iterable

from ..ids import EdgeId, FaceId, VertexId
from ..mesh import Mesh, MeshError


class CollapseRefused(MeshError):
    """The collapse would leave invalid topology; the mesh is unchanged. `str(exc)` says why."""


def collapse_groups(
    mesh: Mesh, vertex_ids: Iterable[VertexId], edge_ids: Iterable[EdgeId] | None = None
) -> list[list[VertexId]]:
    """The groups `collapse_elements` merges, each sorted by id, groups sorted by their first id.

    `edge_ids` None = the edges between two of `vertex_ids`. Endpoints of `edge_ids` belong to a
    group even when they are not in `vertex_ids`."""
    vertices = set(vertex_ids)
    for vid in vertices:
        if not mesh.is_valid_vertex(vid):
            raise MeshError(f"Unbekannter Vertex {vid!r}.")
    if edge_ids is None:
        edges = {e for v in vertices for e in mesh.vertex_edges(v) if set(mesh.edge_vertices(e)) <= vertices}
    else:
        edges = set(edge_ids)
        for eid in edges:
            if not mesh.is_valid_edge(eid):
                raise MeshError(f"Unbekannte Edge {eid!r}.")
            vertices.update(mesh.edge_vertices(eid))

    parent = {v: v for v in vertices}

    def find(v: VertexId) -> VertexId:
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for eid in edges:
        a, b = (find(v) for v in mesh.edge_vertices(eid))
        if a != b:
            parent[max(a, b, key=int)] = min(a, b, key=int)

    groups: dict[VertexId, list[VertexId]] = {}
    for v in vertices:
        groups.setdefault(find(v), []).append(v)
    return sorted((sorted(g, key=int) for g in groups.values()), key=lambda g: int(g[0]))


def collapse_elements(
    mesh: Mesh, vertex_ids: Iterable[VertexId], edge_ids: Iterable[EdgeId] | None = None
) -> list[VertexId]:
    """Collapses every group of `collapse_groups(mesh, vertex_ids, edge_ids)` to its centroid.

    Returns one vertex per group in group order (an unchanged single vertex too). Raises
    `CollapseRefused` (mesh unchanged) when the result would not be valid topology."""
    groups = collapse_groups(mesh, vertex_ids, edge_ids)
    merging = [g for g in groups if len(g) > 1]
    if merging:
        _refuse_invalid_result(mesh, merging)
    centroids = {g[0]: _centroid(mesh, g) for g in merging}

    change = mesh.begin_change()
    try:
        survivors = [g[0] if len(g) == 1 else _merge_group(mesh, g) for g in groups]
    except BaseException:
        mesh.rollback_change(change)
        raise
    mesh.release_change(change)
    for group, survivor in zip(groups, survivors):
        if len(group) > 1:
            mesh.set_vertex_position(survivor, centroids[group[0]])
    return survivors


def _centroid(mesh: Mesh, group: list[VertexId]) -> tuple[float, float, float]:
    points = [mesh.vertex_position(v) for v in group]
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n, sum(p[2] for p in points) / n)


def _refuse_invalid_result(mesh: Mesh, groups: list[list[VertexId]]) -> None:
    """Predicts the faces after all groups are merged; refuses before any mutation."""
    rep = {v: g[0] for g in groups for v in g}
    touched: set[FaceId] = {f for v in rep for e in mesh.vertex_edges(v) for f in mesh.edge_faces(e)}
    cycles: dict[frozenset[VertexId], FaceId] = {}
    for fid in sorted(touched, key=int):
        cycle = _merged_cycle([rep.get(v, v) for v in mesh.face_vertices(fid)])
        if len(cycle) < 3:
            continue  # degenerates, collapse_edge removes it
        if len(set(cycle)) != len(cycle):
            raise CollapseRefused("eine Fläche würde eingeschnürt (Vertex doppelt)")
        key = frozenset(cycle)
        if key in cycles:
            raise CollapseRefused("zwei Flächen würden zusammenfallen")
        cycles[key] = fid

    # Faces per edge after the merge: the surviving touched faces plus the untouched faces that
    # already hang on an edge mapping to the same pair.
    count: dict[frozenset[VertexId], int] = {}
    for key in cycles:
        cycle = _merged_cycle([rep.get(v, v) for v in mesh.face_vertices(cycles[key])])
        for pair in zip(cycle, cycle[1:] + cycle[:1]):
            count[frozenset(pair)] = count.get(frozenset(pair), 0) + 1
    # An untouched face holds no group vertex, so it can only share an original edge of a
    # touched face.
    for eid in {e for f in touched for e in mesh.face_edges(f)}:
        a, b = mesh.edge_vertices(eid)
        key = frozenset((rep.get(a, a), rep.get(b, b)))
        if key not in count:
            continue
        count[key] += sum(1 for f in mesh.edge_faces(eid) if f not in touched)
    if any(n > 2 for n in count.values()):
        raise CollapseRefused("eine Kante hinge an mehr als zwei Flächen")


def _merged_cycle(boundary: list[VertexId]) -> list[VertexId]:
    """A face boundary after merging: consecutive repeats dropped, cyclically."""
    cycle: list[VertexId] = []
    for v in boundary:
        if not cycle or cycle[-1] != v:
            cycle.append(v)
    while len(cycle) > 1 and cycle[0] == cycle[-1]:
        cycle.pop()
    return cycle


def _pinches(mesh: Mesh, a: VertexId, b: VertexId) -> bool:
    """Collapsing a-b now would leave a face that holds both, but not next to each other."""
    faces = {f for e in mesh.vertex_edges(a) for f in mesh.edge_faces(e)}
    for fid in faces:
        boundary = mesh.face_vertices(fid)
        if b not in boundary:
            continue
        i, j = boundary.index(a), boundary.index(b)
        if (i - j) % len(boundary) not in (1, len(boundary) - 1):
            return True
    return False


def _merge_group(mesh: Mesh, group: list[VertexId]) -> VertexId:
    """Merges one group by `collapse_edge`, always on an edge inside the group whose collapse
    pinches no face in between (the final result was checked, an intermediate one is not)."""
    alive = set(group)
    while len(alive) > 1:
        candidates = sorted(
            {e for v in alive for e in mesh.vertex_edges(v) if set(mesh.edge_vertices(e)) <= alive},
            key=int,
        )
        if not candidates:
            raise CollapseRefused("Gruppe ist nicht über Kanten verbunden")
        edge = next((e for e in candidates if not _pinches(mesh, *mesh.edge_vertices(e))), None)
        if edge is None:
            raise CollapseRefused("eine Fläche würde eingeschnürt (Vertex doppelt)")
        a, b = mesh.edge_vertices(edge)
        survivor = mesh.collapse_edge(edge)
        alive.discard(b if survivor == a else a)
    return next(iter(alive))
