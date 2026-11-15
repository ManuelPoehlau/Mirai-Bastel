"""`SlideReference`: the immutable triangle snapshot one slide gesture slides on.

Built from index arrays only: `V (n, 3)` positions by row and `T (m, 3)` triangles. The caller supplies the triangles;
in Production they are the drawn ones (`viewport.derived.triangulate_mesh_face`, audit B1), so nothing here
triangulates a polygon. Every array is read-only after construction, so no caller can move the surface it slides on.

Conventions (as the prototype `experiments/surface_slide/refsurf.py`):

- `T[t, k]` is corner k of triangle t; *edge k* is the edge opposite corner k, from corner k+1 to corner k+2.
- `nbr[t, k]` is the triangle across edge k, or a negative code: `BOUNDARY_EDGE` (no neighbour, or a non-manifold
  edge), `BARRIER_EDGE` (the caller cut it: the symmetry seam, a hidden face), `CAPTURE_EDGE` (the border of a
  region-limited capture: the surface goes on there, it was just not captured). `nbr_k[t, k]` is the corner of the
  neighbour opposite the shared edge, `nbr_flip[t, k]` True when the neighbour runs the shared edge the same way
  (inconsistent winding; the tracer handles it, Core meshes have none).
- An *anchor* is `(triangle, barycentric coordinates)`; "on vertex v" is an exact 1.0 at v's corner.

Not ported from the prototype (audit §13): closest-point grid, ray intersection, Phong evaluation, the polygon
triangulation and the mirrored triangulation. Flat evaluation only (E1).
"""

from __future__ import annotations

from viewport.packed_geometry import np  # NumPy behind its pinned-version check (AD-032 §2)

_I = np.intp
_EPS_AREA = 1e-30

BOUNDARY_EDGE = -1
BARRIER_EDGE = -2
CAPTURE_EDGE = -3


def _frozen(a):
    a.flags.writeable = False
    return a


def unit(v):
    """Rows of `v` scaled to length 1; zero rows stay zero."""
    n = np.sqrt(np.einsum("...j,...j->...", v, v))
    return v / np.where(n > 0.0, n, 1.0)[..., None]


def _edge_rows(edges, nv: int):
    e = np.asarray(edges, dtype=_I).reshape(-1, 2)
    if len(e) and (e.min() < 0 or e.max() >= nv):
        raise ValueError("edge refers to a row outside the reference")
    return e


class SlideReference:
    """Immutable arrays of a triangle surface (module docstring).

    `barrier_edges` / `capture_edges`: `(k, 2)` row pairs (either order) that must be edges of `T`. A barrier wins over
    a capture border on the same edge. `vertex_normals`: per-row unit normals to use instead of the angle-weighted ones
    computed here (the prototype's rule). `edge_scale`: the length unit `h` of the tolerances (default: the mean
    triangle edge length)."""

    def __init__(self, V, T, *, barrier_edges=(), capture_edges=(), vertex_normals=None,
                 edge_scale: float | None = None) -> None:
        V = np.array(V, dtype=np.float64).reshape(-1, 3)
        T = np.array(T, dtype=_I).reshape(-1, 3)
        nv, nt = len(V), len(T)
        if nt and (T.min() < 0 or T.max() >= nv):
            raise ValueError("triangle refers to a row outside the reference")
        self.nv, self.nt = nv, nt
        self.V, self.T = _frozen(V), _frozen(T)

        A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
        cross = np.cross(B - A, C - A)
        area2 = np.sqrt(np.einsum("ij,ij->i", cross, cross))
        self.area2 = _frozen(area2)
        self.degenerate = _frozen(area2 <= 1e-14 * max(1.0, float(np.max(area2, initial=0.0))))
        self.N = _frozen(cross / np.where(area2 > _EPS_AREA, area2, 1.0)[:, None])

        # per (triangle, edge k): unit edge direction, unit inward perpendicular, gradient of barycentric k
        corners = V[T]
        e = np.roll(corners, -2, axis=1) - np.roll(corners, -1, axis=1)
        e_len = np.sqrt(np.einsum("tkj,tkj->tk", e, e))
        E = e / np.where(e_len > 0.0, e_len, 1.0)[..., None]
        to_corner = corners - np.roll(corners, -1, axis=1)
        perp = to_corner - np.einsum("tkj,tkj->tk", to_corner, E)[..., None] * E
        height = np.sqrt(np.einsum("tkj,tkj->tk", perp, perp))
        Pin = perp / np.where(height > 0.0, height, 1.0)[..., None]
        self.E, self.Pin = _frozen(E), _frozen(Pin)
        self.edge_len = _frozen(e_len)
        self.G = _frozen(Pin / np.where(height > 1e-300, height, np.inf)[..., None])
        self.Gn = _frozen(1.0 / np.where(height > 1e-300, height, np.inf))

        self._build_adjacency(_edge_rows(barrier_edges, nv), _edge_rows(capture_edges, nv))
        self._build_vertex_data(vertex_normals)
        if edge_scale is None:
            edge_scale = float(np.mean(e_len)) if nt else 0.0
        self.h = float(edge_scale)

    # -- construction ------------------------------------------------------------------------------------------------

    def _build_adjacency(self, barriers, captures) -> None:
        T, nt, nv = self.T, self.nt, self.nv
        a = np.roll(T, -1, axis=1).ravel()   # edge k start (corner k+1)
        b = np.roll(T, -2, axis=1).ravel()   # edge k end   (corner k+2)
        key = np.minimum(a, b) * nv + np.maximum(a, b)
        order = np.argsort(key, kind="stable")
        ks = key[order]
        start = np.flatnonzero(np.r_[True, ks[1:] != ks[:-1]]) if len(ks) else np.zeros(0, dtype=_I)
        count = np.diff(np.r_[start, len(ks)])
        nbr = np.full(nt * 3, BOUNDARY_EDGE, dtype=_I)
        nbr_k = np.full(nt * 3, -1, dtype=_I)
        flip = np.zeros(nt * 3, dtype=bool)
        pair = start[count == 2]
        h0, h1 = order[pair], order[pair + 1]
        nbr[h0], nbr[h1] = h1 // 3, h0 // 3
        nbr_k[h0], nbr_k[h1] = h1 % 3, h0 % 3
        same_dir = a[h0] == a[h1]
        flip[h0] = same_dir
        flip[h1] = same_dir
        self.n_boundary_edges = int(np.sum(count == 1))
        self.n_nonmanifold_edges = int(np.sum(count > 2))
        self.n_flipped_edges = int(np.sum(same_dir))
        boundary_half = order[np.repeat(count, count) != 2]
        vb = np.zeros(nv, dtype=bool)
        vb[a[boundary_half]] = True
        vb[b[boundary_half]] = True
        self.v_boundary = _frozen(vb)

        uniq = ks[start] if len(ks) else ks
        for edges, code in ((captures, CAPTURE_EDGE), (barriers, BARRIER_EDGE)):
            if not len(edges):
                continue
            want = np.minimum(edges[:, 0], edges[:, 1]) * nv + np.maximum(edges[:, 0], edges[:, 1])
            pos = np.searchsorted(uniq, want)
            if not len(uniq) or np.any(pos >= len(uniq)) or np.any(uniq[np.minimum(pos, len(uniq) - 1)] != want):
                raise ValueError("a barrier or capture edge is not an edge of the triangles")
            halves = np.isin(key, want)
            nbr[halves] = code
        self.nbr = _frozen(nbr.reshape(nt, 3))
        self.nbr_k = _frozen(nbr_k.reshape(nt, 3))
        self.nbr_flip = _frozen(flip.reshape(nt, 3))

        def on(mask):
            v = np.zeros(nv, dtype=bool)
            v[a[mask]] = True
            v[b[mask]] = True
            return _frozen(v)

        self.v_wall = on(nbr < 0)                # any edge a trace cannot cross
        self.v_capture = on(nbr == CAPTURE_EDGE)

    def _build_vertex_data(self, vertex_normals) -> None:
        T, nv, V = self.T, self.nv, self.V
        flat_v = T.ravel()
        order = np.argsort(flat_v, kind="stable")
        counts = np.bincount(flat_v, minlength=nv)
        self.vt_ptr = _frozen(np.r_[0, np.cumsum(counts)].astype(_I))
        self.vt_tri = _frozen((order // 3).astype(_I))
        self.vt_corner = _frozen((order % 3).astype(_I))
        self.valence = _frozen(counts.astype(_I))
        if vertex_normals is not None:
            VN = np.array(vertex_normals, dtype=np.float64).reshape(nv, 3)
            self.VN = _frozen(VN)
            return
        # angle-weighted vertex normals (the prototype's rule; nearly independent of how a polygon was cut)
        corners = V[T]
        u = unit(np.roll(corners, -1, axis=1) - corners)
        w = unit(np.roll(corners, -2, axis=1) - corners)
        ang = np.arccos(np.clip(np.einsum("tkj,tkj->tk", u, w), -1.0, 1.0))
        ang = np.where(self.degenerate[:, None], 0.0, ang)
        VN = np.zeros((nv, 3))
        np.add.at(VN, flat_v, (self.N[:, None, :] * ang[..., None]).reshape(-1, 3))
        self.VN = _frozen(unit(VN))

    # -- queries ------------------------------------------------------------------------------------------------------

    def point(self, tri, bary):
        """The flat (piecewise linear) position of anchors."""
        return np.einsum("nk,nkj->nj", bary, self.V[self.T[tri]])

    def vertex_anchor(self, rows):
        """Anchors that are exactly the vertices `rows` (each in its first incident triangle) -> `(tri, bary)`."""
        rows = np.asarray(rows, dtype=_I)
        if len(rows) and np.any(self.valence[rows] == 0):
            raise ValueError("a row is not a corner of any triangle")
        first = self.vt_ptr[rows]
        tri = self.vt_tri[first]
        bary = np.zeros((len(rows), 3))
        bary[np.arange(len(rows)), self.vt_corner[first]] = 1.0
        return tri, bary

    def edge_slots(self, edges):
        """For `(k, 2)` row pairs: one `(triangle, k)` slot per edge whose edge k it is, or `(-1, -1)`."""
        edges = _edge_rows(edges, self.nv)
        a = np.roll(self.T, -1, axis=1).ravel()
        b = np.roll(self.T, -2, axis=1).ravel()
        key = np.minimum(a, b) * self.nv + np.maximum(a, b)
        order = np.argsort(key, kind="stable")
        ks = key[order]
        want = np.minimum(edges[:, 0], edges[:, 1]) * self.nv + np.maximum(edges[:, 0], edges[:, 1])
        if not len(ks):
            none = np.full(len(want), -1, dtype=_I)
            return none, none.copy()
        p = np.minimum(np.searchsorted(ks, want), len(ks) - 1)
        found = ks[p] == want
        half = order[p]
        return np.where(found, half // 3, -1), np.where(found, half % 3, -1)

    def edges_with_code(self, code: int):
        """The distinct edges `(k, 2)` (a < b) whose `nbr` is `code` (e.g. `BOUNDARY_EDGE`)."""
        t, k = np.nonzero(self.nbr == code)
        a = self.T[t, (k + 1) % 3]
        b = self.T[t, (k + 2) % 3]
        e = np.stack([np.minimum(a, b), np.maximum(a, b)], axis=1)
        return np.unique(e, axis=0) if len(e) else e.reshape(0, 2)

    def nbytes(self) -> int:
        names = ("V", "T", "area2", "degenerate", "N", "E", "Pin", "edge_len", "G", "Gn", "nbr", "nbr_k", "nbr_flip",
                 "v_boundary", "v_wall", "v_capture", "vt_ptr", "vt_tri", "vt_corner", "valence", "VN")
        return int(sum(getattr(self, n).nbytes for n in names))
