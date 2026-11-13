"""The immutable reference surface of one slide gesture: a triangle snapshot with everything the candidates query.

NumPy only (no Core, no viewport, no GUI). A `RefSurface` is built once (`begin`) and never written afterwards; every
array is set read-only so a candidate cannot move the surface it slides on.

Conventions
- `T[t, k]` is corner k of triangle t; *edge k* is the edge opposite corner k, from corner k+1 to corner k+2.
- `nbr[t, k]` is the triangle across edge k (-1: boundary or non-manifold), `nbr_k[t, k]` the corner of that triangle
  opposite the shared edge, `nbr_flip[t, k]` True when the neighbour runs the shared edge in the same direction
  (inconsistent winding; the tracer handles it, a consistently oriented mesh has none).
- An *anchor* is `(triangle, barycentric coordinates)`: the persistent identity of a point on the surface.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_I = np.intp
_EPS_AREA = 1e-30


def _frozen(a: np.ndarray) -> np.ndarray:
    a.flags.writeable = False
    return a


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.sqrt(np.einsum("...j,...j->...", v, v))
    return v / np.where(n > 0.0, n, 1.0)[..., None]


# --- polygon -> triangles -------------------------------------------------------------------------------------------

def _ear_clip(pts: np.ndarray) -> list[tuple[int, int, int]]:
    """Ear clipping of one simple polygon in its Newell plane (the rule of `viewport.derived.triangulate_face`,
    re-stated here so the prototype imports nothing from `src/viewport`)."""
    n = len(pts)
    nxt = np.roll(pts, -1, axis=0)
    normal = np.array([
        np.sum((pts[:, 1] - nxt[:, 1]) * (pts[:, 2] + nxt[:, 2])),
        np.sum((pts[:, 2] - nxt[:, 2]) * (pts[:, 0] + nxt[:, 0])),
        np.sum((pts[:, 0] - nxt[:, 0]) * (pts[:, 1] + nxt[:, 1])),
    ])
    length = float(np.linalg.norm(normal))
    if length < 1e-20:
        return [(0, i, i + 1) for i in range(1, n - 1)]
    normal /= length
    helper = np.eye(3)[int(np.argmin(np.abs(normal)))]
    u = _unit(np.cross(normal, helper))
    w = np.cross(normal, u)
    p2 = np.stack([pts @ u, pts @ w], axis=1)

    def cross(a: int, b: int, c: int) -> float:
        return float((p2[b, 0] - p2[a, 0]) * (p2[c, 1] - p2[a, 1]) - (p2[b, 1] - p2[a, 1]) * (p2[c, 0] - p2[a, 0]))

    ring = list(range(n))
    tris: list[tuple[int, int, int]] = []
    eps = 1e-14
    while len(ring) > 3:
        m = len(ring)
        best = None
        for k in range(m):
            a, b, c = ring[k - 1], ring[k], ring[(k + 1) % m]
            if cross(a, b, c) <= eps:
                continue
            if any(j not in (a, b, c) and cross(a, b, j) >= -eps and cross(b, c, j) >= -eps and cross(c, a, j) >= -eps
                   for j in ring):
                continue
            best = k
            break
        if best is None:  # degenerate: cut the flattest corner, always terminates
            best = min(range(m), key=lambda k: abs(cross(ring[k - 1], ring[k], ring[(k + 1) % m])))
        tris.append((ring[best - 1], ring[best], ring[(best + 1) % m]))
        del ring[best]
    tris.append((ring[0], ring[1], ring[2]))
    return tris


def triangulate(V: np.ndarray, faces: list, partner: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Polygons -> `(T, tri_face)`. Triangles stay; a quad is cut along its shorter diagonal; larger polygons are
    ear-clipped. Neither rule gives a mirrored mesh a mirrored triangulation (equal diagonals, ear order), so with
    `partner` (vertex -> mirror partner, -1 = none) every face whose mirror image is another face takes that face's
    triangles, mirrored: the reference surface is then exactly symmetric wherever the mesh is."""
    T, tri_face = _triangulate(V, faces)
    if partner is None:
        return T, tri_face
    key = {frozenset(f): i for i, f in enumerate(faces)}
    first = np.r_[0, np.cumsum(np.bincount(tri_face, minlength=len(faces)))]
    T = T.copy()
    for i, f in enumerate(faces):
        if any(partner[v] < 0 for v in f):
            continue
        j = key.get(frozenset(int(partner[v]) for v in f))
        if j is None or j <= i:
            continue
        src = T[first[i]:first[i + 1]]
        if first[j + 1] - first[j] != len(src):
            continue
        T[first[j]:first[j + 1]] = partner[src][:, [0, 2, 1]]       # mirrored: winding reversed
    return T, tri_face


def _triangulate(V: np.ndarray, faces: list) -> tuple[np.ndarray, np.ndarray]:
    tris: list[tuple[int, int, int]] = []
    owner: list[int] = []
    quads = [(i, f) for i, f in enumerate(faces) if len(f) == 4]
    if quads:
        q = np.array([f for _, f in quads], dtype=_I)
        d02 = np.einsum("ij,ij->i", V[q[:, 0]] - V[q[:, 2]], V[q[:, 0]] - V[q[:, 2]])
        d13 = np.einsum("ij,ij->i", V[q[:, 1]] - V[q[:, 3]], V[q[:, 1]] - V[q[:, 3]])
        use13 = d13 < d02
        a = np.where(use13[:, None], q[:, [0, 1, 3]], q[:, [0, 1, 2]])
        b = np.where(use13[:, None], q[:, [1, 2, 3]], q[:, [0, 2, 3]])
        quad_tris = np.stack([a, b], axis=1).reshape(-1, 3)
        quad_owner = np.repeat(np.array([i for i, _ in quads], dtype=_I), 2)
    else:
        quad_tris = np.zeros((0, 3), dtype=_I)
        quad_owner = np.zeros(0, dtype=_I)
    for i, f in enumerate(faces):
        n = len(f)
        if n == 3:
            tris.append(tuple(f))
            owner.append(i)
        elif n > 4:
            for a_, b_, c_ in _ear_clip(V[np.asarray(f, dtype=_I)]):
                tris.append((f[a_], f[b_], f[c_]))
                owner.append(i)
    T = np.concatenate([quad_tris, np.array(tris, dtype=_I).reshape(-1, 3)])
    tri_face = np.concatenate([quad_owner, np.array(owner, dtype=_I)])
    order = np.argsort(tri_face, kind="stable")
    return T[order], tri_face[order]


def polygon_edges(faces: list) -> np.ndarray:
    """The distinct polygon edges `(m, 2)`, a < b (the edges the artist sees; no triangulation diagonals)."""
    pairs = set()
    for f in faces:
        n = len(f)
        for i in range(n):
            a, b = f[i], f[(i + 1) % n]
            pairs.add((a, b) if a < b else (b, a))
    return np.array(sorted(pairs), dtype=_I).reshape(-1, 2)


# --- closest point on triangles (batch) ---------------------------------------------------------------------------

def closest_on_triangles(P: np.ndarray, A: np.ndarray, B: np.ndarray, C: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Closest point of each `P[i]` on triangle `(A[i], B[i], C[i])` -> `(bary (n, 3), squared distance (n,))`.
    Ericson, Real-Time Collision Detection 5.1.5, on arrays; degenerate triangles fall back to their best edge."""
    ab, ac, ap = B - A, C - A, P - A
    d1 = np.einsum("ij,ij->i", ab, ap)
    d2 = np.einsum("ij,ij->i", ac, ap)
    bp = P - B
    d3 = np.einsum("ij,ij->i", ab, bp)
    d4 = np.einsum("ij,ij->i", ac, bp)
    cp = P - C
    d5 = np.einsum("ij,ij->i", ab, cp)
    d6 = np.einsum("ij,ij->i", ac, cp)
    vc = d1 * d4 - d3 * d2
    vb = d5 * d2 - d1 * d6
    va = d3 * d6 - d5 * d4
    n = len(P)
    v = np.zeros(n)
    w = np.zeros(n)
    done = np.zeros(n, dtype=bool)

    def take(mask, vv, ww):
        nonlocal done
        m = mask & ~done
        v[m] = vv[m] if isinstance(vv, np.ndarray) else vv
        w[m] = ww[m] if isinstance(ww, np.ndarray) else ww
        done |= m

    zero = np.zeros(n)
    one = np.ones(n)
    with np.errstate(divide="ignore", invalid="ignore"):
        take((d1 <= 0) & (d2 <= 0), zero, zero)                                  # vertex A
        take((d3 >= 0) & (d4 <= d3), one, zero)                                  # vertex B
        take((vc <= 0) & (d1 >= 0) & (d3 <= 0), np.nan_to_num(d1 / (d1 - d3)), zero)   # edge AB
        take((d6 >= 0) & (d5 <= d6), zero, one)                                  # vertex C
        take((vb <= 0) & (d2 >= 0) & (d6 <= 0), zero, np.nan_to_num(d2 / (d2 - d6)))   # edge AC
        t_bc = np.nan_to_num((d4 - d3) / ((d4 - d3) + (d5 - d6)))
        take((va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0), 1.0 - t_bc, t_bc)  # edge BC
        denom = va + vb + vc
        inside_v = np.nan_to_num(vb / denom)
        inside_w = np.nan_to_num(vc / denom)
        take(~done, inside_v, inside_w)
    v = np.clip(v, 0.0, 1.0)
    w = np.clip(w, 0.0, 1.0 - v)
    bary = np.stack([1.0 - v - w, v, w], axis=1)
    Q = A + ab * v[:, None] + ac * w[:, None]
    diff = P - Q
    return bary, np.einsum("ij,ij->i", diff, diff)


# --- the reference surface -------------------------------------------------------------------------------------------

@dataclass
class RayHits:
    hit: np.ndarray    # (n,) bool
    tri: np.ndarray    # (n,)
    bary: np.ndarray   # (n, 3)
    s: np.ndarray      # (n,) signed parameter along the line (0 = origin)


class RefSurface:
    """Module docstring. `faces` (optional) are the source polygons: they give `edges` (the visible edges) and
    `tri_face`; without them the triangles are the faces."""

    def __init__(self, V, T, tri_face=None, faces=None) -> None:
        V = np.array(V, dtype=np.float64)
        T = np.array(T, dtype=_I).reshape(-1, 3)
        nv, nt = len(V), len(T)
        self.nv, self.nt = nv, nt
        self.V, self.T = _frozen(V), _frozen(T)
        self.tri_face = _frozen(np.arange(nt, dtype=_I) if tri_face is None else np.array(tri_face, dtype=_I))
        self.faces = faces

        A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
        cross = np.cross(B - A, C - A)
        area2 = np.sqrt(np.einsum("ij,ij->i", cross, cross))
        self.area2 = _frozen(area2)
        self.degenerate = _frozen(area2 <= 1e-14 * max(1.0, float(np.max(area2, initial=0.0))))
        N = cross / np.where(area2 > _EPS_AREA, area2, 1.0)[:, None]
        self.N = _frozen(N)

        # per (triangle, edge k): unit edge direction, unit inward perpendicular, and the gradient of barycentric k
        corners = V[T]                                                  # (nt, 3, 3)
        e = np.roll(corners, -2, axis=1) - np.roll(corners, -1, axis=1)  # edge k: corner k+1 -> corner k+2
        e_len = np.sqrt(np.einsum("tkj,tkj->tk", e, e))
        E = e / np.where(e_len > 0.0, e_len, 1.0)[..., None]
        to_corner = corners - np.roll(corners, -1, axis=1)              # corner k+1 -> corner k
        perp = to_corner - np.einsum("tkj,tkj->tk", to_corner, E)[..., None] * E
        height = np.sqrt(np.einsum("tkj,tkj->tk", perp, perp))
        Pin = perp / np.where(height > 0.0, height, 1.0)[..., None]
        self.E, self.Pin = _frozen(E), _frozen(Pin)
        self.edge_len = _frozen(e_len)
        # grad(bary_k) = Pin_k / height_k: bary_k grows from 0 on edge k to 1 at corner k
        self.G = _frozen(Pin / np.where(height > 1e-300, height, np.inf)[..., None])
        self.Gn = _frozen(1.0 / np.where(height > 1e-300, height, np.inf))

        self._build_adjacency()
        self._build_vertex_data()
        edges = polygon_edges(faces) if faces is not None else self._triangle_edges()
        self.edges = _frozen(edges)
        el = np.linalg.norm(V[edges[:, 0]] - V[edges[:, 1]], axis=1) if len(edges) else np.zeros(0)
        self.mean_edge = float(np.mean(el)) if len(el) else 0.0
        self.bbox_diag = float(np.linalg.norm(V.max(axis=0) - V.min(axis=0))) if nv else 0.0
        self._grid = None

    # -- construction ------------------------------------------------------------------------------------------------

    def _build_adjacency(self) -> None:
        T, nt, nv = self.T, self.nt, self.nv
        a = np.roll(T, -1, axis=1).ravel()   # edge k start (corner k+1)
        b = np.roll(T, -2, axis=1).ravel()   # edge k end   (corner k+2)
        key = np.minimum(a, b) * nv + np.maximum(a, b)
        order = np.argsort(key, kind="stable")
        ks = key[order]
        start = np.flatnonzero(np.r_[True, ks[1:] != ks[:-1]])
        count = np.diff(np.r_[start, len(ks)])
        nbr = np.full(nt * 3, -1, dtype=_I)
        nbr_k = np.full(nt * 3, -1, dtype=_I)
        flip = np.zeros(nt * 3, dtype=bool)
        pair = start[count == 2]
        h0, h1 = order[pair], order[pair + 1]
        nbr[h0], nbr[h1] = h1 // 3, h0 // 3
        nbr_k[h0], nbr_k[h1] = h1 % 3, h0 % 3
        same_dir = a[h0] == a[h1]
        flip[h0] = same_dir
        flip[h1] = same_dir
        self.nbr = _frozen(nbr.reshape(nt, 3))
        self.nbr_k = _frozen(nbr_k.reshape(nt, 3))
        self.nbr_flip = _frozen(flip.reshape(nt, 3))
        self.n_boundary_edges = int(np.sum(count == 1))
        self.n_nonmanifold_edges = int(np.sum(count > 2))
        self.n_flipped_edges = int(np.sum(same_dir))
        boundary_half = order[np.repeat(count, count) != 2]
        vb = np.zeros(nv, dtype=bool)
        vb[a[boundary_half]] = True
        vb[b[boundary_half]] = True
        self.v_boundary = _frozen(vb)

    def _build_vertex_data(self) -> None:
        T, nt, nv, V = self.T, self.nt, self.nv, self.V
        flat_v = T.ravel()
        order = np.argsort(flat_v, kind="stable")
        counts = np.bincount(flat_v, minlength=nv)
        self.vt_ptr = _frozen(np.r_[0, np.cumsum(counts)].astype(_I))
        self.vt_tri = _frozen((order // 3).astype(_I))
        self.vt_corner = _frozen((order % 3).astype(_I))
        self.valence = _frozen(counts.astype(_I))
        # angle-weighted vertex normals (independent of how a polygon was cut into triangles, up to non-planarity)
        corners = V[T]
        u = _unit(np.roll(corners, -1, axis=1) - corners)
        w = _unit(np.roll(corners, -2, axis=1) - corners)
        ang = np.arccos(np.clip(np.einsum("tkj,tkj->tk", u, w), -1.0, 1.0))
        ang = np.where(self.degenerate[:, None], 0.0, ang)
        VN = np.zeros((nv, 3))
        np.add.at(VN, flat_v, (self.N[:, None, :] * ang[..., None]).reshape(-1, 3))
        self.VN = _frozen(_unit(VN))

    def _triangle_edges(self) -> np.ndarray:
        a = self.T.ravel()
        b = np.roll(self.T, -1, axis=1).ravel()
        e = np.unique(np.stack([np.minimum(a, b), np.maximum(a, b)], axis=1), axis=0)
        return e.astype(_I)

    # -- evaluation ---------------------------------------------------------------------------------------------------

    def point(self, tri: np.ndarray, bary: np.ndarray) -> np.ndarray:
        """The flat (piecewise linear) position of anchors."""
        return np.einsum("nk,nkj->nj", bary, self.V[self.T[tri]])

    def point_phong(self, tri: np.ndarray, bary: np.ndarray, alpha: float = 0.75) -> np.ndarray:
        """Phong tessellation (Boubekeur & Alexa 2008): the flat point pulled towards the vertex tangent planes. It
        interpolates the vertices, is C0 across edges, and curves a facet towards the shape its normals describe."""
        tv = self.T[tri]
        p = np.einsum("nk,nkj->nj", bary, self.V[tv])
        off = np.einsum("nkj,nkj->nk", p[:, None, :] - self.V[tv], self.VN[tv])
        return p - alpha * np.einsum("nk,nkj->nj", bary * off, self.VN[tv])

    def normal_at(self, tri: np.ndarray, bary: np.ndarray) -> np.ndarray:
        """Interpolated (Phong) unit normal of anchors; the face normal where the interpolation vanishes."""
        n = np.einsum("nk,nkj->nj", bary, self.VN[self.T[tri]])
        length = np.linalg.norm(n, axis=1)
        return np.where((length > 1e-12)[:, None], n / np.where(length > 1e-12, length, 1.0)[:, None], self.N[tri])

    def vertex_anchor(self, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """An anchor that is exactly vertex `v` (its first incident triangle)."""
        v = np.asarray(v, dtype=_I)
        first = self.vt_ptr[v]
        tri = self.vt_tri[first]
        bary = np.zeros((len(v), 3))
        bary[np.arange(len(v)), self.vt_corner[first]] = 1.0
        return tri, bary

    # -- global closest point (uniform grid) -------------------------------------------------------------------------

    def build_grid(self, cell: float | None = None) -> None:
        if self._grid is not None:
            return
        V, T = self.V, self.T
        lo = V.min(axis=0)
        hi = V.max(axis=0)
        if cell is None:
            cell = max(2.0 * self.mean_edge, 1e-9, float(np.max(hi - lo)) / 96.0)
        dims = np.maximum(1, np.ceil((hi - lo) / cell).astype(_I) + 1)
        tmin = np.floor((V[T].min(axis=1) - lo) / cell).astype(_I)
        tmax = np.floor((V[T].max(axis=1) - lo) / cell).astype(_I)
        span = tmax - tmin + 1
        per = span[:, 0] * span[:, 1] * span[:, 2]
        tri_rep = np.repeat(np.arange(self.nt, dtype=_I), per)
        local = np.arange(len(tri_rep), dtype=_I) - np.repeat(np.cumsum(per) - per, per)
        sx, sy, sz = span[tri_rep, 0], span[tri_rep, 1], span[tri_rep, 2]
        ix = tmin[tri_rep, 0] + local // (sy * sz)
        iy = tmin[tri_rep, 1] + (local // sz) % sy
        iz = tmin[tri_rep, 2] + local % sz
        cell_id = (ix * dims[1] + iy) * dims[2] + iz
        order = np.argsort(cell_id, kind="stable")
        n_cells = int(dims[0] * dims[1] * dims[2])
        counts = np.bincount(cell_id, minlength=n_cells)
        self._grid = (lo, float(cell), dims, np.r_[0, np.cumsum(counts)].astype(_I), tri_rep[order])

    def grid_bytes(self) -> int:
        return 0 if self._grid is None else int(self._grid[3].nbytes + self._grid[4].nbytes)

    def closest_point(self, P: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Global closest point of each `P[i]` -> `(tri, bary, distance)`. Exact: a ring of grid cells is accepted
        only when the best distance found is within the searched block; what is left is searched brute force."""
        self.build_grid()
        lo, cell, dims, ptr, items = self._grid
        P = np.asarray(P, dtype=np.float64)
        n = len(P)
        best_d2 = np.full(n, np.inf)
        best_tri = np.zeros(n, dtype=_I)
        best_bary = np.zeros((n, 3))
        rel = (P - lo) / cell
        cidx = np.floor(rel).astype(_I)
        # distance from P to the border of its own cell, per axis side (how far the searched block reaches at ring r)
        frac = rel - cidx
        margin = np.minimum(frac, 1.0 - frac).min(axis=1) * cell
        pending = np.arange(n, dtype=_I)
        ring = 1
        max_ring = int(np.max(dims)) + 1
        while len(pending) and ring <= max_ring:
            offs = np.arange(-ring, ring + 1)
            ox, oy, oz = np.meshgrid(offs, offs, offs, indexing="ij")
            off = np.stack([ox.ravel(), oy.ravel(), oz.ravel()], axis=1)
            cells = cidx[pending][:, None, :] + off[None, :, :]
            ok = np.all((cells >= 0) & (cells < dims), axis=2)
            cid = (cells[..., 0] * dims[1] + cells[..., 1]) * dims[2] + cells[..., 2]
            q_idx, c_idx = np.nonzero(ok)
            cid = cid[q_idx, c_idx]
            cnt = ptr[cid + 1] - ptr[cid]
            total = int(cnt.sum())
            if total:
                rep_q = np.repeat(q_idx, cnt)
                pos = np.arange(total, dtype=_I) - np.repeat(np.cumsum(cnt) - cnt, cnt) + np.repeat(ptr[cid], cnt)
                tri = items[pos]
                tv = self.T[tri]
                bary, d2 = closest_on_triangles(P[pending][rep_q], self.V[tv[:, 0]], self.V[tv[:, 1]], self.V[tv[:, 2]])
                order = np.lexsort((d2, rep_q))
                first = order[np.r_[True, rep_q[order][1:] != rep_q[order][:-1]]]
                q_hit = rep_q[first]
                better = d2[first] < best_d2[pending[q_hit]]
                sel = first[better]
                tgt = pending[q_hit[better]]
                best_d2[tgt], best_tri[tgt], best_bary[tgt] = d2[sel], tri[sel], bary[sel]
            # P lies in its own cell, `margin` from that cell's nearest wall: nothing outside the block is closer
            found = np.sqrt(best_d2[pending]) <= ring * cell + margin[pending]
            pending = pending[~found]
            ring = ring + 1 if ring < 3 else ring * 2
            if ring > 8 and len(pending):
                break
        if len(pending):  # far from the surface: exact brute force in chunks
            A, B, C = self.V[self.T[:, 0]], self.V[self.T[:, 1]], self.V[self.T[:, 2]]
            for i in pending:
                bary, d2 = closest_on_triangles(np.broadcast_to(P[i], A.shape), A, B, C)
                j = int(np.argmin(d2))
                best_d2[i], best_tri[i], best_bary[i] = d2[j], j, bary[j]
        return best_tri, best_bary, np.sqrt(best_d2)

    # -- local closest point (adjacency descent) ---------------------------------------------------------------------

    def closest_point_local(self, P: np.ndarray, tri0: np.ndarray, max_iter: int = 64
                            ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Closest point found by descending over triangle adjacency from `tri0`: per step the best of all triangles
        sharing a vertex with the current one; stops when the current triangle is the best. Returns
        `(tri, bary, distance, steps)`. A local minimum of the distance that is connected to `tri0` - by construction
        it cannot jump to a surface part the descent does not reach."""
        P = np.asarray(P, dtype=np.float64)
        n = len(P)
        tri = np.array(tri0, dtype=_I).copy()
        tv = self.T[tri]
        bary, d2 = closest_on_triangles(P, self.V[tv[:, 0]], self.V[tv[:, 1]], self.V[tv[:, 2]])
        steps = np.zeros(n, dtype=_I)
        active = np.arange(n, dtype=_I)
        for _ in range(max_iter):
            if not len(active):
                break
            verts = self.T[tri[active]].ravel()
            cnt = self.vt_ptr[verts + 1] - self.vt_ptr[verts]
            total = int(cnt.sum())
            rep = np.repeat(np.repeat(np.arange(len(active), dtype=_I), 3), cnt)
            pos = np.arange(total, dtype=_I) - np.repeat(np.cumsum(cnt) - cnt, cnt) + np.repeat(self.vt_ptr[verts], cnt)
            cand = self.vt_tri[pos]
            cv = self.T[cand]
            cb, cd2 = closest_on_triangles(P[active][rep], self.V[cv[:, 0]], self.V[cv[:, 1]], self.V[cv[:, 2]])
            order = np.lexsort((cd2, rep))
            first = order[np.r_[True, rep[order][1:] != rep[order][:-1]]]
            better = cd2[first] < d2[active] * (1.0 - 1e-12) - 1e-300
            moved = active[better]
            sel = first[better]
            tri[moved], bary[moved], d2[moved] = cand[sel], cb[sel], cd2[sel]
            steps[moved] += 1
            active = moved
        return tri, bary, np.sqrt(d2), steps

    # -- line / ray intersection (brute force, chunked) --------------------------------------------------------------

    def intersect_lines(self, O: np.ndarray, D: np.ndarray, s_min: float, s_max: float, chunk: int = 200_000
                        ) -> RayHits:
        """For each line `O[i] + s D[i]`, s in [s_min, s_max]: the intersection with the smallest |s|. Brute force
        Moeller-Trumbore (rays x triangles in chunks) - fine for the validation sizes, not a production structure."""
        n = len(O)
        hit = np.zeros(n, dtype=bool)
        best_s = np.full(n, np.inf)
        best_tri = np.zeros(n, dtype=_I)
        best_bary = np.zeros((n, 3))
        A = self.V[self.T[:, 0]]
        e1 = self.V[self.T[:, 1]] - A
        e2 = self.V[self.T[:, 2]] - A
        per = max(1, chunk // max(self.nt, 1))
        for lo in range(0, n, per):
            o, d = O[lo:lo + per], D[lo:lo + per]
            pvec = np.cross(d[:, None, :], e2[None, :, :])
            det = np.einsum("tj,ntj->nt", e1, pvec)
            with np.errstate(divide="ignore", invalid="ignore"):
                inv = 1.0 / det
                tvec = o[:, None, :] - A[None, :, :]
                u = np.einsum("ntj,ntj->nt", tvec, pvec) * inv
                qvec = np.cross(tvec, e1[None, :, :])
                v = np.einsum("nj,ntj->nt", d, qvec) * inv
                s = np.einsum("tj,ntj->nt", e2, qvec) * inv
            eps = 1e-9
            ok = (np.abs(det) > 1e-300) & (u >= -eps) & (v >= -eps) & (u + v <= 1.0 + eps) & (s >= s_min) & (s <= s_max)
            score = np.where(ok, np.abs(s), np.inf)
            j = np.argmin(score, axis=1)
            rows = np.arange(len(o))
            good = np.isfinite(score[rows, j])
            idx = lo + rows[good]
            hit[idx] = True
            best_s[idx] = s[rows[good], j[good]]
            best_tri[idx] = j[good]
            uu = np.clip(u[rows[good], j[good]], 0.0, 1.0)
            vv = np.clip(v[rows[good], j[good]], 0.0, 1.0 - uu)
            best_bary[idx] = np.stack([1.0 - uu - vv, uu, vv], axis=1)
        return RayHits(hit, best_tri, best_bary, best_s)

    # -- sizes --------------------------------------------------------------------------------------------------------

    def nbytes(self) -> int:
        names = ("V", "T", "tri_face", "area2", "N", "E", "Pin", "edge_len", "G", "Gn", "nbr", "nbr_k", "nbr_flip",
                 "vt_ptr", "vt_tri", "vt_corner", "valence", "VN", "edges", "v_boundary", "degenerate")
        return int(sum(getattr(self, n).nbytes for n in names))

    def tracer_nbytes(self) -> int:
        """What the geodesic tracer alone needs (no closest-point grid, no visible edges)."""
        names = ("V", "T", "N", "E", "Pin", "G", "Gn", "nbr", "nbr_k", "nbr_flip", "vt_ptr", "vt_tri", "vt_corner", "VN")
        return int(sum(getattr(self, n).nbytes for n in names))
