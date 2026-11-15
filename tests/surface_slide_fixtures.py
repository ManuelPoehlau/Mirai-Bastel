"""Generated surfaces for the Surface Slide core tests (`tests/test_surface_slide_*.py`).

Self-contained (nothing from `experiments/`, AGENTS.md §8a): small analogues of the prototype's geometries, as index
arrays. Polygons become triangles by the drawn rule for convex polygons (a fan from the first corner,
`viewport.derived.triangulate_face`), so the tests slide on the kind of triangles Production draws.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import tests._bootstrap  # noqa: F401

from viewport.packed_geometry import np  # noqa: E402

from mirai.surface_slide import SlideReference  # noqa: E402


@dataclass
class Surface:
    V: object
    faces: list
    meta: dict = field(default_factory=dict)

    @property
    def T(self):
        return fan(self.faces)

    @property
    def polygon_edges(self):
        pairs = set()
        for f in self.faces:
            for a, b in zip(f, f[1:] + f[:1]):
                pairs.add((min(a, b), max(a, b)))
        return np.array(sorted(pairs), dtype=np.intp).reshape(-1, 2)

    def reference(self, **kw) -> SlideReference:
        return SlideReference(self.V, self.T, **kw)


def fan(faces) -> object:
    return np.array([(f[0], f[i], f[i + 1]) for f in faces for i in range(1, len(f) - 1)], dtype=np.intp)


def grid(nx: int = 8, ny: int = 8, cell: float = 1.0, x0: float = 0.0, y0: float = 0.0) -> Surface:
    """A flat open sheet in z = 0, normals +z; vertex `j * (nx + 1) + i` at `(x0 + i cell, y0 + j cell)`."""
    V = np.array([(x0 + i * cell, y0 + j * cell, 0.0) for j in range(ny + 1) for i in range(nx + 1)])
    w = nx + 1
    faces = [(j * w + i, j * w + i + 1, (j + 1) * w + i + 1, (j + 1) * w + i) for j in range(ny) for i in range(nx)]
    return Surface(V, faces, {"nx": nx, "ny": ny, "cell": cell})


def cube_sphere(n: int, radius: float = 1.0, project: bool = True, scale=(1.0, 1.0, 1.0)) -> Surface:
    """A box of n x n quads per side, pushed onto the sphere (`project`) or left a cube; outward normals. Built so the
    mesh is bit-exactly mirror-symmetric in x (vertices with x == 0 have it exactly when n is even)."""
    u = [(2 * i - n) / n for i in range(n + 1)]
    verts: list = []
    faces = []
    index: dict = {}

    def vid(p):
        key = tuple(int(round(c * n)) for c in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(p)
        return index[key]

    for axis in range(3):
        for sign in (-1.0, 1.0):
            a, b = (axis + 1) % 3, (axis + 2) % 3
            for i in range(n):
                for j in range(n):
                    quad = []
                    for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        p = [0.0, 0.0, 0.0]
                        p[axis] = sign
                        p[a] = u[i + di]
                        p[b] = u[j + dj]
                        quad.append(vid(tuple(p)))
                    if sign < 0:
                        quad.reverse()
                    faces.append(tuple(quad))
    V = np.array(verts)
    if project:
        W = np.where(np.abs(V) == 1.0, V, np.tan(V * (math.pi / 4.0)))
        V = W / np.sqrt(np.einsum("ij,ij->i", W, W))[:, None]
    V = radius * V * np.asarray(scale, dtype=np.float64)
    return Surface(V, faces, {"n": n})


def cylinder(segments: int = 24, rows: int = 12, radius: float = 1.0, height: float = 3.0) -> Surface:
    """An open tube around y (two boundary loops, the rims), outward normals."""
    V = np.array([(radius * math.cos(2 * math.pi * s / segments), -height / 2 + height * r / rows,
                   radius * math.sin(2 * math.pi * s / segments)) for r in range(rows + 1) for s in range(segments)])
    faces = []
    for r in range(rows):
        for s in range(segments):
            a, b = r * segments + s, r * segments + (s + 1) % segments
            faces.append((a, a + segments, b + segments, b))
    return Surface(V, faces, {"segments": segments, "rows": rows})


def u_shape(gap: float = 0.3, depth: float = 2.0, length_y: float = 2.0, cell: float = 0.1, bend: int = 8) -> Surface:
    """Two walls `gap` apart joined by a half cylinder below z = 0, extruded along y; normals point into the gap.
    Developable: `unrolled(s, y)` is the exact point at arc length `s` along the profile (from the top of wall A)."""
    r = gap / 2.0
    n_wall = int(round(depth / cell))
    nodes = [(-r, depth - depth * i / n_wall) for i in range(n_wall + 1)]
    nodes += [(-r * math.cos(math.pi * i / bend), -r * math.sin(math.pi * i / bend)) for i in range(1, bend + 1)]
    nodes += [(r, depth * i / n_wall) for i in range(1, n_wall + 1)]
    profile = np.array(nodes)
    s_nodes = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(profile, axis=0), axis=1))]
    n_y = int(round(length_y / cell))
    m = len(profile)
    V = np.concatenate([np.stack([profile[:, 0], np.full(m, -length_y / 2 + length_y * j / n_y), profile[:, 1]], axis=1)
                        for j in range(n_y + 1)])
    faces = [(j * m + i, j * m + i + 1, (j + 1) * m + i + 1, (j + 1) * m + i) for j in range(n_y) for i in range(m - 1)]
    return Surface(V, faces, {"profile": profile, "s_nodes": s_nodes, "m": m, "n_wall": n_wall, "bend": bend,
                              "wall_len": depth, "bend_len": float(s_nodes[n_wall + bend] - s_nodes[n_wall])})


def u_vertex(u: Surface, node: int, row: int) -> int:
    return row * u.meta["m"] + node


def u_unrolled(u: Surface, s, y):
    """The point at arc length `s` along the profile and extrusion coordinate `y` (exact on the polyhedral U)."""
    profile, s_nodes = u.meta["profile"], u.meta["s_nodes"]
    s = np.asarray(s, dtype=np.float64)
    i = np.clip(np.searchsorted(s_nodes, s, side="right") - 1, 0, len(s_nodes) - 2)
    f = (s - s_nodes[i]) / (s_nodes[i + 1] - s_nodes[i])
    xz = profile[i] + f[:, None] * (profile[i + 1] - profile[i])
    return np.stack([xz[:, 0], np.asarray(y, dtype=np.float64), xz[:, 1]], axis=1)


def u_wall(u: Surface, ref: SlideReference, tri, bary):
    """0 = wall A, 1 = bend, 2 = wall B, from the anchors (arc length is linear inside a triangle)."""
    s_vert = np.tile(u.meta["s_nodes"], len(u.V) // u.meta["m"])
    s = np.einsum("nk,nk->n", bary, s_vert[ref.T[tri]])
    a, b = u.meta["wall_len"], u.meta["wall_len"] + u.meta["bend_len"]
    return np.where(s < a - 1e-12, 0, np.where(s > b + 1e-12, 2, 1))


def geodesic_ring(ref: SlideReference, seed: int, radius: float):
    """Rows within `radius` of `seed` over triangle edges and their smooth falloff weights (3t^2 - 2t^3), seed first."""
    import heapq

    a = np.r_[ref.T[:, 0], ref.T[:, 1], ref.T[:, 2]]
    b = np.r_[ref.T[:, 1], ref.T[:, 2], ref.T[:, 0]]
    nbrs: dict[int, set] = {}
    for x, y in zip(a.tolist(), b.tolist()):
        nbrs.setdefault(x, set()).add(y)
        nbrs.setdefault(y, set()).add(x)
    dist = {seed: 0.0}
    heap = [(0.0, seed)]
    done = {}
    while heap:
        d, v = heapq.heappop(heap)
        if v in done:
            continue
        done[v] = d
        for o in nbrs[v]:
            nd = d + float(np.linalg.norm(ref.V[o] - ref.V[v]))
            if nd < radius and nd < dist.get(o, np.inf):
                dist[o] = nd
                heapq.heappush(heap, (nd, o))
    rows = [seed] + sorted(v for v in done if v != seed)
    t = np.array([1.0 - done[v] / radius for v in rows])
    return np.array(rows, dtype=np.intp), t * t * (3.0 - 2.0 * t)


def nearest(V, point) -> int:
    return int(np.argmin(np.linalg.norm(np.asarray(V) - np.asarray(point, dtype=np.float64), axis=1)))


def point_triangle_distance(P, A, B, C):
    """Distance of each point to the plane of its triangle (the tests check barycentrics separately, so this is the
    tracked deviation from the anchor triangle)."""
    n = np.cross(B - A, C - A)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    return np.abs(np.einsum("ij,ij->i", P - A, n))
