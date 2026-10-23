"""Loop / Ring flow: a topology-oriented anisotropic geodesic field (2026-10-22, `PROVISIONAL`).

AD-020 "Loop / Ring flow". The isotropic `geodesic` metric spreads equally along every mesh edge. Flow
makes the reach depend on the *edge flow*: farther along the seeds' edge loops (Loop) or farther across
their successive edge rings (Ring). Everything is derived from the topology; world or screen axes play
no part.

**Edge families.** In a quad, opposite edges belong to the same edge ring and point the same way;
adjacent edges point across. So the edges of a quad region split into two families: walking along an
edge of family A moves along the A-direction of the flow, and the ring rule (`loop_ring._ring_step`:
opposite edge of a quad) carries a family label from quad to quad. This is the parallelism that
`edge_loop` / `edge_ring` traverse one line at a time, extended to a 2-colouring of a region.

**Which family is Loop (per seed region).** The seeds are vertices (the tools resolve vertex, edge and
face selections, and the hover, to vertices). A seed region is a connected component of the seeds
through the edges between two seeds. Its edges are 2-coloured through the quads touching the region;
the family holding *more* of the region's own edges is Loop - the direction the region extends along
the flow: one edge, an edge path / loop, a strip of faces (n >= 2), an edge-ring selection (n >= 3)
extends across its edges. A region with no edge between seeds (one vertex, scattered vertices), a tie
(one quad face, two parallel edges, a square block) or edges in no quad has **no direction**: it adds
no labels. If no region has a direction, the field is exactly the isotropic geodesic field (fallback).

**Propagation.** The oriented regions' labels spread over the quads of the influence region in the
order of the isotropic geodesic distance (nearest first, ties by face id), first label wins. Labels
never cross a non-quad face. A quad whose labels already disagree (two fronts with different
colourings meet: around a pole of odd valence, between two regions oriented differently) labels
nothing further. Edges left unlabelled (triangle / n-gon regions, behind such a meeting) are neutral.

**Metric.** Dijkstra over the edges as `geodesic`, the edge length scaled by its family: with the
balance `ratio = loop reach / ring reach`, the shorter direction's edges cost `max(ratio, 1/ratio)`
times their length, the other family and neutral edges cost their length. The radius therefore stays
the farthest reach (the dominant direction and neutral edges reach it, the other `radius / k`), the
field is a subset of the isotropic one, and the falloff curves act on `1 - d / radius` unchanged.
`ratio == 1` never reaches this module (`influence.distance_function`), so neutral is bit-identical.
"""

from __future__ import annotations

import heapq
import math

from core import EdgeId, FaceId, Mesh, VertexId

#: Edge families relative to the seeds' flow.
LOOP, RING = 0, 1


def flow_costs(ratio: float) -> tuple[float, float]:
    """`(loop_cost, ring_cost)`: the length factors for the two families at `ratio` (loop / ring reach)."""
    return (1.0 / ratio, 1.0) if ratio < 1.0 else (1.0, ratio)


class _Topology:
    """Lazy edge graph and quads of the region the field reaches (no cache across calls). Lazy instead of
    one pass over all edges as `_geodesic_distances`: `Mesh.vertex_edges` is indexed, and the flow field
    only ever looks near the seeds. The neighbour order does not change a Dijkstra result (a vertex's
    distance is the minimum over its settled neighbours)."""

    def __init__(self, mesh: Mesh) -> None:
        self.mesh = mesh
        self._neighbours: dict[VertexId, list[tuple[VertexId, EdgeId]]] = {}
        self._quad_edges: dict[FaceId, list[EdgeId] | None] = {}

    def neighbours(self, vid: VertexId) -> list[tuple[VertexId, EdgeId]]:
        found = self._neighbours.get(vid)
        if found is None:
            mesh = self.mesh
            found = []
            for eid in mesh.vertex_edges(vid):
                a, b = mesh.edge_vertices(eid)
                found.append((b if a == vid else a, eid))
            self._neighbours[vid] = found
        return found

    def quad_edges(self, face: FaceId) -> list[EdgeId] | None:
        """The four edges of `face` in boundary order, None for a non-quad (lazy: only faces near the seeds)."""
        if face not in self._quad_edges:
            edges = self.mesh.face_edges(face)
            self._quad_edges[face] = edges if len(edges) == 4 else None
        return self._quad_edges[face]


def _dijkstra(
    topo: _Topology, seeds: set[VertexId], radius: float, cost: dict[EdgeId, float] | None = None
) -> dict[VertexId, float]:
    """Multi-source Dijkstra pruned at `radius`; edge cost = length x `cost.get(edge, 1.0)`."""
    mesh = topo.mesh
    dist: dict[VertexId, float] = {s: 0.0 for s in seeds}
    heap: list[tuple[float, VertexId]] = [(0.0, s) for s in seeds]
    heapq.heapify(heap)
    done: set[VertexId] = set()
    while heap:
        d, vid = heapq.heappop(heap)
        if vid in done:
            continue
        done.add(vid)
        p = mesh.vertex_position(vid)
        for other, eid in topo.neighbours(vid):
            if other in done:
                continue
            q = mesh.vertex_position(other)
            # The arithmetic of `influence._geodesic_distances`, so the cost-free run is that field.
            dx, dy, dz = p[0] - q[0], p[1] - q[1], p[2] - q[2]
            length = math.sqrt(dx * dx + dy * dy + dz * dz)
            nd = d + (length if cost is None else length * cost.get(eid, 1.0))
            if nd >= radius:
                continue
            if nd < dist.get(other, math.inf):
                dist[other] = nd
                heapq.heappush(heap, (nd, other))
    return dist


def _implied(position: int, ref_position: int, ref_label: int) -> int:
    # Opposite edges of a quad (even offset) share the family, adjacent ones swap it.
    return ref_label if (position - ref_position) % 2 == 0 else 1 - ref_label


def _propagate(
    topo: _Topology, start: dict[EdgeId, int], face_key
) -> dict[EdgeId, int]:
    """Spread family labels from `start` through quads in `face_key` order (None = face not allowed);
    first label wins, a quad whose labels disagree spreads nothing (module docstring)."""
    labels = dict(start)
    heap: list[tuple] = []
    done: set[FaceId] = set()

    def push_faces(eid: EdgeId) -> None:
        for face in topo.mesh.edge_faces(eid):
            if face in done:
                continue
            key = face_key(face)
            if key is not None:
                heapq.heappush(heap, (key, face))

    for eid in sorted(start):
        push_faces(eid)
    while heap:
        _, face = heapq.heappop(heap)
        if face in done:
            continue
        done.add(face)
        edges = topo.quad_edges(face)
        if edges is None:
            continue  # labels never cross a non-quad (as `edge_ring`)
        known = [(i, labels[e]) for i, e in enumerate(edges) if e in labels]
        ref_i, ref_label = known[0]
        if any(label != _implied(i, ref_i, ref_label) for i, label in known):
            continue  # two fronts with different colourings meet here
        for i, eid in enumerate(edges):
            if eid not in labels:
                labels[eid] = _implied(i, ref_i, ref_label)
                push_faces(eid)
    return labels


def _seed_regions(topo: _Topology, seeds: set[VertexId]) -> list[tuple[set[VertexId], list[EdgeId]]]:
    """The seed regions (module docstring) with their own edges, in a deterministic order."""
    parent = {s: s for s in seeds}

    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    inner: list[EdgeId] = []
    for s in seeds:
        for other, eid in topo.neighbours(s):
            if other in seeds and s < other:
                inner.append(eid)
                ra, rb = find(s), find(other)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    regions: dict[VertexId, tuple[set[VertexId], list[EdgeId]]] = {}
    for s in sorted(seeds):
        regions.setdefault(find(s), (set(), []))[0].add(s)
    for eid in sorted(inner):
        regions[find(topo.mesh.edge_vertices(eid)[0])][1].append(eid)
    return [regions[root] for root in sorted(regions)]


def _region_labels(topo: _Topology, vertices: set[VertexId], edges: list[EdgeId]) -> dict[EdgeId, int]:
    """LOOP / RING for a region's own edges, {} when the region has no direction."""
    edges = [e for e in edges if any(topo.quad_edges(f) for f in topo.mesh.edge_faces(e))]
    if not edges:
        return {}  # no edge between seeds, or none in a quad
    local_faces = {
        face
        for v in vertices
        for _, eid in topo.neighbours(v)
        for face in topo.mesh.edge_faces(eid)
    }
    # Hop order from the region's first edge (the face id breaks ties): deterministic.
    colouring = _propagate(
        topo, {edges[0]: 0}, lambda face: (0, face) if face in local_faces else None
    )
    counts = [0, 0]
    for eid in edges:
        if eid in colouring:
            counts[colouring[eid]] += 1
    if counts[0] == counts[1]:
        return {}  # one quad, two parallel edges, a square block, edges in no quad: no direction
    loop_colour = 0 if counts[0] > counts[1] else 1
    return {
        eid: (LOOP if colouring[eid] == loop_colour else RING) for eid in edges if eid in colouring
    }


def _seed_labels(topo: _Topology, seeds: set[VertexId]) -> dict[EdgeId, int]:
    labels: dict[EdgeId, int] = {}
    for vertices, edges in _seed_regions(topo, seeds):
        labels.update(_region_labels(topo, vertices, edges))
    return labels


def has_flow_direction(mesh: Mesh, seeds) -> bool:
    """True if at least one seed region has a Loop / Ring direction (else flow falls back to isotropic)."""
    valid = {s for s in seeds if mesh.is_valid_vertex(s)}
    return bool(valid) and bool(_seed_labels(_Topology(mesh), valid))


def flow_families(mesh: Mesh, seeds, radius: float) -> dict[EdgeId, int]:
    """The LOOP / RING label of every labelled edge of the influence region (absent = neutral)."""
    valid = {s for s in seeds if mesh.is_valid_vertex(s)}
    topo = _Topology(mesh)
    start = _seed_labels(topo, valid)
    return _families(topo, start, _dijkstra(topo, valid, radius)) if start else {}


def _families(topo: _Topology, start: dict[EdgeId, int], iso: dict[VertexId, float]) -> dict[EdgeId, int]:
    def face_key(face):
        key = min(iso.get(v, math.inf) for v in topo.mesh.face_vertices(face))
        return None if key == math.inf else (key, face)

    return _propagate(topo, start, face_key)


def flow_distances(
    mesh: Mesh, seeds: set[VertexId], radius: float, ratio: float
) -> dict[VertexId, float]:
    """The flow metric (module docstring): `{vertex: distance < radius}` like `METRICS`."""
    topo = _Topology(mesh)
    iso = _dijkstra(topo, seeds, radius)
    start = _seed_labels(topo, seeds)
    if not start:
        return iso  # no seed region with a direction: the isotropic field
    loop_cost, ring_cost = flow_costs(ratio)
    cost = {
        eid: (loop_cost if family == LOOP else ring_cost)
        for eid, family in _families(topo, start, iso).items()
    }
    return _dijkstra(topo, seeds, radius, cost)
