"""What a slide gesture derives once at `begin`: the influence weights and the tangent transport.

The weights follow `mirai.soft_selection.influence` (multi-source Dijkstra over the visible edges, pruned at the
radius, `smooth` = 3t^2 - 2t^3) but on index arrays, so the prototype needs no `core.Mesh`.

The transport gives every affected vertex a rotation `R_i` that carries a tangent vector of the pivot vertex into
the tangent plane of vertex i: the product of the minimal rotations (normal -> normal) along the Dijkstra tree from
the pivot. It is a discrete parallel transport; on a developable surface it is exact, on a curved one it depends on
the tree path by the enclosed curvature (holonomy), which is small over a soft-selection radius.
"""

from __future__ import annotations

import heapq
import math

import numpy as np

from .refsurf import RefSurface

_I = np.intp


def smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


class EdgeGraph:
    """Vertex adjacency over the visible (polygon) edges, as Python lists for Dijkstra."""

    def __init__(self, nv: int, edges: np.ndarray, V: np.ndarray) -> None:
        length = np.linalg.norm(V[edges[:, 0]] - V[edges[:, 1]], axis=1)
        a = np.r_[edges[:, 0], edges[:, 1]]
        b = np.r_[edges[:, 1], edges[:, 0]]
        w = np.r_[length, length]
        order = np.argsort(a, kind="stable")
        counts = np.bincount(a, minlength=nv)
        self.ptr = np.r_[0, np.cumsum(counts)].tolist()
        self.nbr = b[order].tolist()
        self.w = w[order].tolist()
        self.nv = nv

    def dijkstra(self, sources, radius: float = math.inf, targets: set | None = None
                 ) -> tuple[dict[int, float], dict[int, int]]:
        """Distances `< radius` from `sources` and the tree (`parent[v]`; a source has itself). With `targets` the
        search stops once all of them are settled."""
        dist = {int(s): 0.0 for s in sources}
        parent = {int(s): int(s) for s in sources}
        heap = [(0.0, int(s)) for s in sources]
        heapq.heapify(heap)
        done: set[int] = set()
        left = None if targets is None else set(targets)
        ptr, nbr, w = self.ptr, self.nbr, self.w
        while heap:
            d, v = heapq.heappop(heap)
            if v in done:
                continue
            done.add(v)
            if left is not None:
                left.discard(v)
                if not left:
                    break
            for i in range(ptr[v], ptr[v + 1]):
                o = nbr[i]
                if o in done:
                    continue
                nd = d + w[i]
                if nd >= radius:
                    continue
                if nd < dist.get(o, math.inf):
                    dist[o] = nd
                    parent[o] = v
                    heapq.heappush(heap, (nd, o))
        return {v: dist[v] for v in done}, {v: parent[v] for v in done}


def soft_weights(graph: EdgeGraph, seeds, radius: float) -> tuple[np.ndarray, np.ndarray]:
    """`(vertices, weights)` of the geodesic `smooth` influence: seeds 1.0, 0 < w < 1 inside the radius."""
    seeds = [int(s) for s in seeds]
    if radius <= 0.0:
        return np.array(sorted(seeds), dtype=_I), np.ones(len(seeds))
    dist, _ = graph.dijkstra(seeds, radius)
    verts = np.array(sorted(dist), dtype=_I)
    w = np.array([1.0 if dist[v] == 0.0 else smooth(1.0 - dist[v] / radius) for v in verts.tolist()])
    keep = w > 0.0
    return verts[keep], w[keep]


def minimal_rotation(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The rotation with the smallest angle taking unit `a` to unit `b` (undefined for b == -a: identity there)."""
    v = np.cross(a, b)
    c = float(a @ b)
    if c < -1.0 + 1e-12:
        return np.eye(3)
    vx = np.array([[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]])
    return np.eye(3) + vx + vx @ vx / (1.0 + c)


def transport_frames(ref: RefSurface, graph: EdgeGraph, pivot: int, verts: np.ndarray) -> np.ndarray:
    """`R (n, 3, 3)`: `R[i] @ t` carries a tangent vector `t` of the pivot vertex to `verts[i]` (module docstring).
    A vertex the pivot cannot reach over edges gets the direct minimal rotation between the two normals."""
    targets = set(int(v) for v in verts)
    dist, parent = graph.dijkstra([int(pivot)], targets=targets)
    VN = ref.VN
    R: dict[int, np.ndarray] = {int(pivot): np.eye(3)}
    for v in sorted(dist, key=dist.get):   # parents are settled before their children
        if v not in R:
            p = parent[v]
            R[v] = minimal_rotation(VN[p], VN[v]) @ R[p]
    out = np.empty((len(verts), 3, 3))
    for i, v in enumerate(verts.tolist()):
        out[i] = R[v] if v in R else minimal_rotation(VN[pivot], VN[v])
    return out


def mirror_partners(V: np.ndarray, plane_point=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0)) -> np.ndarray:
    """Position-based mirror partner of each vertex, by exact float equality as `mirai.symmetry` (no tolerance):
    `partner[i]`, `i` itself on the plane, -1 without a partner."""
    n = np.asarray(plane_normal, dtype=np.float64)
    o = np.asarray(plane_point, dtype=np.float64)
    dist = (V - o) @ n
    M = V - 2.0 * dist[:, None] * n
    index = {p.tobytes(): i for i, p in enumerate(V + 0.0)}
    partner = np.full(len(V), -1, dtype=_I)
    for i, m in enumerate(M + 0.0):
        j = index.get(m.tobytes())
        if j is not None:
            partner[i] = j
    return partner


def mirror(P: np.ndarray, plane_point=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0)) -> np.ndarray:
    n = np.asarray(plane_normal, dtype=np.float64)
    o = np.asarray(plane_point, dtype=np.float64)
    return P - 2.0 * ((P - o) @ n)[:, None] * n
