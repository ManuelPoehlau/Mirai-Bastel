"""The texel -> surface map (AD-037 §4, audit 2026-11-18 §4.2 principle 2, Phase 1b). Derived data, like the pick cache.

For every texel of a `width` x `height` image the map names the drawn triangle whose UV triangle holds the texel's centre
and the texel's barycentric weights in it. A texel's surface point is then `w0·p0 + w1·p1 + w2·p2` over that triangle's
corners from **any** position table with the mesh's ids and topology - the rest mesh, the morph mix or the posed surface
(`SurfacePositions`, `Application._query_cage`) - so a position change never rebuilds the map.

**Texel layout.** Row `y` = 0 is the image row at v = 0 (the GL / pyglet row order, bottom row first); texel `(x, y)` has
its centre at `((x + 0.5) / width, (y + 0.5) / height)` in UV space and the flat index `y * width + x`. A PNG (top row
first) is flipped once on read and write (`mirai.paint.files`). UVs outside [0, 1] are not wrapped: those parts of a face
have no texels (the UV check names such faces).

**Triangles.** Each mapped face is split exactly as the viewport draws it (`viewport.derived.triangulate_face` on the
positions of the source table), so a texel's weights interpolate the corner UVs as the rasterizer does. A triangle with
no UV area holds no texel. Where triangles overlap in UV (a shared edge, a UV overlap), the texel belongs to the triangle
with the smallest key `(face id, index in the face's triangulation)` - a rule independent of the order the triangles are
written in, which makes `patch` produce exactly what `rebuild` would.

**Patching** (`patch(change)`, a `MeshWatch` / `SurfaceWatch` change): a face is re-rasterized when its boundary or UVs
changed, when it appeared or went, and when a moved vertex changed its triangulation (a concave n-gon); every other
position change costs one triangulation check per non-triangle face around a moved vertex and writes nothing. Texels a
removed triangle owned are refilled from every triangle whose texel box touches them. A patch that touches more than
`REBUILD_SHARE` of the faces (and more than
`REBUILD_MIN_FACES`) rebuilds instead.

**Building** (`rebuild`) is batched (AD-037 §8 Phase 2, the SubD surface: 36,008 faces at level 2 on the Gollum head,
2.0 s per triangle in the container): triangles and convex quads are split without a Python call per face
(`_split_faces`, the same fan and convexity test as `triangulate_face`, bit for bit), small triangles are rasterized
together row by row (`_raster_scan`: per row only the span inside the triangle, ±1 texel, with the same arithmetic as
`raster_triangle`) and every texel goes to its smallest
key in one pass (`np.minimum.at` over the slots, which are handed out in key order). The result equals the per-triangle
build exactly (pinned: `tests/test_paint_texel_map.py`); `patch` keeps the per-triangle path (few faces).

Memory at 2048²: 4 bytes of triangle slot and 8 bytes of weights per texel (48 MiB), plus the triangle table.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np

from core import FaceId, Mesh, VertexId
from viewport.derived import _EAR_EPS as _EAR_EPS_DERIVED, triangulate_face

#: A patch touching more than this share of the mesh's faces rebuilds the whole map (`PROVISIONAL`, agent-set).
REBUILD_SHARE = 0.25
#: ... and touches more than this many faces (a small mesh always patches).
REBUILD_MIN_FACES = 64
#: Texel-space tolerance of the inside test (a centre on an edge counts for both triangles; the key decides).
_INSIDE_EPS = 1e-9
#: Twice the UV area (in texel² units) below which a triangle holds no texel.
_MIN_AREA2 = 1e-12
#: Triangles per face the key can tell apart (an n-gon has n - 2).
_KEY_STRIDE = 1 << 16
_EMPTY = -1


def raster_triangle(a, b, c, width: int, height: int):
    """The texels whose centres lie in the UV triangle `a b c` (each a (u, v) pair), edges included: `(flat indices,
    w1, w2, box)` with float64 weights of corners `b` and `c` (w0 = 1 - w1 - w2) and the texel box (x0, y0, x1, y1,
    inclusive), or None when the triangle has no texel.
    Written for few NumPy calls per triangle (the reference PC's P-D, 2026-11-18): the weights are outer differences of
    a row and a column vector."""
    ax, ay = a[0] * width - 0.5, a[1] * height - 0.5
    bx, by = b[0] * width - 0.5, b[1] * height - 0.5
    cx, cy = c[0] * width - 0.5, c[1] * height - 0.5
    e1x, e1y, e2x, e2y = bx - ax, by - ay, cx - ax, cy - ay
    det = e1x * e2y - e2x * e1y
    if abs(det) < _MIN_AREA2:
        return None
    x0 = max(math.ceil(min(ax, bx, cx) - _INSIDE_EPS), 0)
    x1 = min(math.floor(max(ax, bx, cx) + _INSIDE_EPS), width - 1)
    y0 = max(math.ceil(min(ay, by, cy) - _INSIDE_EPS), 0)
    y1 = min(math.floor(max(ay, by, cy) + _INSIDE_EPS), height - 1)
    if x0 > x1 or y0 > y1:
        return None
    px = (x0 - ax) + np.arange(x1 - x0 + 1, dtype=np.float64)  # x - ax for x = x0 .. x1 (box start + an integer)
    py = ((y0 - ay) + np.arange(y1 - y0 + 1, dtype=np.float64))[:, None]
    inv = 1.0 / det
    w1 = px * (e2y * inv) - py * (e2x * inv)
    w2 = py * (e1x * inv) - px * (e1y * inv)
    inside = (w1 >= -_INSIDE_EPS) & (w2 >= -_INSIDE_EPS) & (w1 + w2 <= 1.0 + _INSIDE_EPS)
    rows, cols = np.nonzero(inside)
    if rows.size == 0:
        return None
    box = (x0 + int(cols.min()), y0 + int(rows[0]), x0 + int(cols.max()), y0 + int(rows[-1]))  # rows ascend
    return (rows + y0) * width + (cols + x0), w1[rows, cols], w2[rows, cols], box


#: Candidate texels per raster step (`_raster_scan`'s memory bound: about 80 bytes each).
_SCAN_CANDIDATES = 1 << 20


def _convex_quads(p: np.ndarray) -> np.ndarray:
    """(n,) bool: which quads (n, 4, 3) `triangulate_face` splits as the fan of their first corner - the same Newell
    normal, plane axes and corner test, the same float operations in the same order (so the same answer bit for bit)."""
    nx = np.zeros(len(p))
    ny = np.zeros(len(p))
    nz = np.zeros(len(p))
    for i in range(4):
        a, b = p[:, i], p[:, (i + 1) % 4]
        nx = nx + (a[:, 1] - b[:, 1]) * (a[:, 2] + b[:, 2])
        ny = ny + (a[:, 2] - b[:, 2]) * (a[:, 0] + b[:, 0])
        nz = nz + (a[:, 0] - b[:, 0]) * (a[:, 1] + b[:, 1])
    ax, ay, az = np.abs(nx), np.abs(ny), np.abs(nz)
    use_z = (az >= ax) & (az >= ay)
    use_x = ~use_z & (ax >= ay)
    use_y = ~use_z & ~use_x
    u = np.where(use_z, 0, np.where(use_x, 1, 2))
    w = np.where(use_z, 1, np.where(use_x, 2, 0))
    normal = np.where(use_z, nz, np.where(use_x, nx, ny))
    sign = np.where(normal >= 0, 1.0, -1.0)
    rows = np.arange(len(p))
    pu = sign[:, None] * p[rows[:, None], np.arange(4)[None, :], u[:, None]]
    pw = p[rows[:, None], np.arange(4)[None, :], w[:, None]]
    convex = np.ones(len(p), dtype=bool)
    for k in range(4):
        o, a, b = (k - 1) % 4, k, (k + 1) % 4
        cross = (pu[:, a] - pu[:, o]) * (pw[:, b] - pw[:, o]) - (pw[:, a] - pw[:, o]) * (pu[:, b] - pu[:, o])
        convex &= cross >= -_EAR_EPS_DERIVED
    del use_y
    return convex


def _raster_all(tri_uvs: np.ndarray, width: int, height: int) -> tuple:
    """Rasterizes every triangle (T, 3, 2) as `raster_triangle` would: `(flat texels, triangle of each, w1, w2, boxes (T,
    4), has texels (T,))` - every (texel, triangle) pair with the centre inside, ownership not yet decided."""
    t = len(tri_uvs)
    boxes = np.zeros((t, 4), dtype=np.int32)
    keep = np.zeros(t, dtype=bool)
    empty = (np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0), np.zeros(0), boxes, keep)
    if t == 0:
        return empty
    ax = tri_uvs[:, 0, 0] * width - 0.5
    ay = tri_uvs[:, 0, 1] * height - 0.5
    bx = tri_uvs[:, 1, 0] * width - 0.5
    by = tri_uvs[:, 1, 1] * height - 0.5
    cx = tri_uvs[:, 2, 0] * width - 0.5
    cy = tri_uvs[:, 2, 1] * height - 0.5
    e1x, e1y, e2x, e2y = bx - ax, by - ay, cx - ax, cy - ay
    det = e1x * e2y - e2x * e1y
    with np.errstate(invalid="ignore", divide="ignore"):
        x0 = np.maximum(np.ceil(np.minimum(np.minimum(ax, bx), cx) - _INSIDE_EPS), 0)
        x1 = np.minimum(np.floor(np.maximum(np.maximum(ax, bx), cx) + _INSIDE_EPS), width - 1)
        y0 = np.maximum(np.ceil(np.minimum(np.minimum(ay, by), cy) - _INSIDE_EPS), 0)
        y1 = np.minimum(np.floor(np.maximum(np.maximum(ay, by), cy) + _INSIDE_EPS), height - 1)
    ok = (np.abs(det) >= _MIN_AREA2) & (x0 <= x1) & (y0 <= y1) & np.isfinite(det)
    bw = np.where(ok, x1 - x0 + 1, 0).astype(np.int64)
    bh = np.where(ok, y1 - y0 + 1, 0).astype(np.int64)
    parts = []
    geometry = (ax, ay, e1x, e1y, e2x, e2y, det, x0, y0, bw, bh)
    members = np.nonzero(ok)[0]
    # chunks of about `_SCAN_CANDIDATES` candidates (a triangle covers about half its box)
    work = np.cumsum((bw[members] * bh[members]) // 2 + bh[members])
    cuts = np.searchsorted(work, np.arange(_SCAN_CANDIDATES, int(work[-1]) + 1, _SCAN_CANDIDATES)) if members.size else []
    for chunk in np.split(members, cuts):
        if chunk.size:
            part = _raster_scan(chunk, geometry, width, boxes, keep)
            if part is not None:
                parts.append(part)
    if not parts:
        return empty
    flat = np.concatenate([part[0] for part in parts])
    owner = np.concatenate([part[1] for part in parts])
    w1 = np.concatenate([part[2] for part in parts])
    w2 = np.concatenate([part[3] for part in parts])
    return flat, owner, w1, w2, boxes, keep


def _raster_scan(chunk, geometry, width, boxes, keep):
    """`raster_triangle` for the triangles `chunk` at once, row by row: per (triangle, row) the interval of `x - ax` where
    all three edge conditions hold is solved, widened by one texel each side, and only those texels are tested - with the
    same expressions on the same float64 values as `raster_triangle`, so the same texels and weights. Writes the chunk's
    boxes and `keep`; returns the part or None."""
    ax, ay, e1x, e1y, e2x, e2y, det, x0, y0, bw, bh = (g[chunk] for g in geometry)
    inv = 1.0 / det
    a1, b1, c2, d2 = e2y * inv, e2x * inv, e1x * inv, e1y * inv  # w1 = px a1 - py b1, w2 = py c2 - px d2
    rows = bh.astype(np.int64)
    tri = np.repeat(np.arange(chunk.size), rows)
    row = np.arange(tri.size) - np.repeat(np.cumsum(rows) - rows, rows)
    py = (y0 - ay)[tri] + row
    lo = np.full(tri.size, -np.inf)
    hi = np.full(tri.size, np.inf)
    empty = np.zeros(tri.size, dtype=bool)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        for k, m in ((a1[tri], _INSIDE_EPS - py * b1[tri]),             # w1 >= -eps
                     (-d2[tri], _INSIDE_EPS + py * c2[tri]),            # w2 >= -eps
                     (d2[tri] - a1[tri], 1.0 + _INSIDE_EPS - py * (c2[tri] - b1[tri]))):  # w1 + w2 <= 1 + eps
            bound = -m / k
            lo = np.where(k > 0, np.maximum(lo, bound), lo)
            hi = np.where(k < 0, np.minimum(hi, bound), hi)
            empty |= (k == 0) & (m < 0)
        start = (x0 - ax)[tri]  # px of the box's first column
        first = np.maximum(np.ceil(lo - start) - 1.0, 0.0)
        last = np.minimum(np.floor(hi - start) + 1.0, (bw[tri] - 1).astype(np.float64))
    count = np.where(empty | ~(last >= first), 0, last - first + 1.0)
    count = np.nan_to_num(count, nan=0.0, posinf=0.0).astype(np.int64)
    total = int(count.sum())
    if total == 0:
        return None
    pair = np.repeat(np.arange(tri.size), count)
    column = first.astype(np.int64)[pair] + (np.arange(total) - np.repeat(np.cumsum(count) - count, count))
    t = tri[pair]
    px = start[pair] + column
    pyc = py[pair]
    w1 = px * a1[t] - pyc * b1[t]
    w2 = pyc * c2[t] - px * d2[t]
    inside = np.flatnonzero((w1 >= -_INSIDE_EPS) & (w2 >= -_INSIDE_EPS) & (w1 + w2 <= 1.0 + _INSIDE_EPS))
    if inside.size == 0:
        return None
    t = t[inside]
    xs = x0.astype(np.int64)[t] + column[inside]
    ys = y0.astype(np.int64)[t] + row[pair[inside]]
    hit = np.zeros(chunk.size, dtype=bool)
    hit[t] = True
    lo_x = np.full(chunk.size, np.iinfo(np.int64).max)
    hi_x = np.full(chunk.size, -1)
    lo_y = np.full(chunk.size, np.iinfo(np.int64).max)
    hi_y = np.full(chunk.size, -1)
    np.minimum.at(lo_x, t, xs)
    np.maximum.at(hi_x, t, xs)
    np.minimum.at(lo_y, t, ys)
    np.maximum.at(hi_y, t, ys)
    members = chunk[hit]
    boxes[members] = np.stack((lo_x[hit], lo_y[hit], hi_x[hit], hi_y[hit]), axis=1)
    keep[members] = True
    return ys * width + xs, chunk[t], w1[inside], w2[inside]


class TexelMap:
    """Texel -> (triangle, barycentric weights) for one mesh at one resolution (module docstring)."""

    def __init__(self, mesh: Mesh, width: int, height: int, positions=None) -> None:
        if width < 1 or height < 1:
            raise ValueError(f"texel map: positive size needed, got {width} x {height}")
        self.mesh = mesh
        self.width, self.height = int(width), int(height)
        self.positions = mesh if positions is None else positions
        self.rebuild()

    # -- building ------------------------------------------------------------------------------------------------

    def rebuild(self) -> None:
        n = self.width * self.height
        self.slot = np.full(n, _EMPTY, dtype=np.int32)
        self.bary = np.zeros((n, 2), dtype=np.float32)
        self._cap = 0
        self.tri_vertices = np.zeros((0, 3), dtype=np.int64)
        self.tri_uvs = np.zeros((0, 3, 2), dtype=np.float64)
        self.tri_face = np.zeros(0, dtype=np.int64)
        self.tri_index = np.zeros(0, dtype=np.int32)
        self._tri_key = np.zeros(0, dtype=np.int64)
        self._tri_box = np.zeros((0, 4), dtype=np.int32)
        self._free: list[int] = []
        self._face_slots: dict[FaceId, list[int]] = {}
        self._face_tris: dict[FaceId, tuple] = {}
        faces = self.mesh.all_face_ids()
        tris, tri_uvs, tri_face, tri_index = self._split_faces(faces)
        flat, slot_of, w1, w2, boxes, keep = _raster_all(tri_uvs, self.width, self.height)
        count = int(keep.sum())
        self._grow(max(count + 16, 2 * len(faces) + 16))
        # slots in key order (faces ascend, triangles ascend inside a face): the smallest slot is the smallest key
        rank = np.cumsum(keep) - 1
        kept = np.nonzero(keep)[0]
        self.tri_vertices[:count] = tris[kept]
        self.tri_uvs[:count] = tri_uvs[kept]
        self.tri_face[:count] = tri_face[kept]
        self.tri_index[:count] = tri_index[kept]
        self._tri_key[:count] = tri_face[kept] * _KEY_STRIDE + tri_index[kept]
        self._tri_box[:count] = boxes[kept]
        self._free = list(range(self._cap - 1, count - 1, -1))
        if flat.size:
            slots = rank[slot_of].astype(np.int32)
            best = np.full(n, np.iinfo(np.int32).max, dtype=np.int32)
            np.minimum.at(best, flat, slots)
            win = np.flatnonzero(slots == best[flat])
            idx = flat[win]
            self.slot[idx] = slots[win]
            weights = np.empty((win.size, 2), dtype=np.float32)
            weights[:, 0] = w1[win]
            weights[:, 1] = w2[win]
            self.bary[idx] = weights
        if count:
            owners = self.tri_face[:count]
            starts = np.flatnonzero(np.r_[True, owners[1:] != owners[:-1]])
            ends = np.r_[starts[1:], count]
            self._face_slots = {FaceId(int(f)): list(range(a, b))
                                for f, a, b in zip(owners[starts].tolist(), starts.tolist(), ends.tolist())}

    def _split_faces(self, faces) -> tuple:
        """Every face's drawn triangles (`triangulate_face` on the source table's positions) and their corner UVs, in key
        order: `(vertex ids (T, 3), UVs (T, 3, 2), face ids (T,), index in the face (T,))`; fills `_face_tris`. Triangles
        and convex quads (the fan of the first corner) are split here in arrays, everything else by `triangulate_face`."""
        mesh, positions = self.mesh, self.positions
        boundaries = [mesh.face_vertices(fid) for fid in faces]
        uvs = [mesh.face_uvs(fid) for fid in faces]
        sizes = np.fromiter((len(b) for b in boundaries), dtype=np.int64, count=len(faces))
        quads = np.nonzero(sizes == 4)[0]
        fast = sizes == 3
        if quads.size:
            corner_ids = np.array([boundaries[i] for i in quads], dtype=np.int64)
            unique, inverse = np.unique(corner_ids, return_inverse=True)
            points = np.array([positions.vertex_position(VertexId(int(v))) for v in unique], dtype=np.float64)
            fast[quads] = _convex_quads(points[inverse.reshape(corner_ids.shape)])
        face_tris = self._face_tris
        rows_t, uvs_t, face_t, index_t = [], [], [], []
        for n, picks in ((3, ((0, 1, 2),)), (4, ((0, 1, 2), (0, 2, 3)))):
            members = np.nonzero(fast & (sizes == n))[0].tolist()
            if n == 3:
                face_tris.update({faces[i]: ((tuple(boundaries[i]),), uvs[i]) for i in members})
            else:
                for i in members:
                    b0, b1, b2, b3 = boundaries[i]
                    face_tris[faces[i]] = (((b0, b1, b2), (b0, b2, b3)), uvs[i])
            mapped = [i for i in members if uvs[i] is not None]
            if not mapped:
                continue
            ids = np.array([boundaries[i] for i in mapped], dtype=np.int64)
            corner_uvs = np.array([uvs[i] for i in mapped], dtype=np.float64)
            fids = np.array([int(faces[i]) for i in mapped], dtype=np.int64)
            for k, pick in enumerate(picks):
                rows_t.append(ids[:, pick])
                uvs_t.append(corner_uvs[:, pick])
                face_t.append(fids)
                index_t.append(np.full(len(mapped), k, dtype=np.int32))
        slow_tris, slow_uvs, slow_face, slow_index = [], [], [], []
        for i in np.nonzero(~fast)[0].tolist():
            boundary, face_uvs = boundaries[i], uvs[i]
            tris = tuple(triangulate_face(boundary, {v: positions.vertex_position(v) for v in boundary}))
            face_tris[faces[i]] = (tris, face_uvs)
            if face_uvs is None:
                continue
            corner = dict(zip(boundary, face_uvs))
            for k, tri in enumerate(tris):
                slow_tris.append(tri)
                slow_uvs.append((corner[tri[0]], corner[tri[1]], corner[tri[2]]))
                slow_face.append(int(faces[i]))
                slow_index.append(k)
        if slow_tris:
            rows_t.append(np.array(slow_tris, dtype=np.int64))
            uvs_t.append(np.array(slow_uvs, dtype=np.float64))
            face_t.append(np.array(slow_face, dtype=np.int64))
            index_t.append(np.array(slow_index, dtype=np.int32))
        if not rows_t:
            return (np.zeros((0, 3), np.int64), np.zeros((0, 3, 2), np.float64), np.zeros(0, np.int64),
                    np.zeros(0, np.int32))
        tris = np.concatenate(rows_t)
        tri_uvs = np.concatenate(uvs_t)
        tri_face = np.concatenate(face_t)
        tri_index = np.concatenate(index_t)
        order = np.argsort(tri_face * _KEY_STRIDE + tri_index, kind="stable")
        return tris[order], tri_uvs[order], tri_face[order], tri_index[order]

    def _grow(self, need: int) -> None:
        if need <= self._cap:
            return
        cap = max(need, 2 * self._cap)
        old = self._cap

        def extended(array, fill, shape):
            out = np.full(shape, fill, dtype=array.dtype)
            out[:old] = array
            return out

        self.tri_vertices = extended(self.tri_vertices, -1, (cap, 3))
        self.tri_uvs = extended(self.tri_uvs, 0.0, (cap, 3, 2))
        self.tri_face = extended(self.tri_face, -1, (cap,))
        self.tri_index = extended(self.tri_index, -1, (cap,))
        self._tri_key = extended(self._tri_key, np.iinfo(np.int64).max, (cap,))
        self._tri_box = extended(self._tri_box, 0, (cap, 4))
        self._free.extend(range(cap - 1, old - 1, -1))
        self._cap = cap

    def _triangles(self, fid: FaceId) -> tuple:
        boundary = self.mesh.face_vertices(fid)
        positions = self.positions
        return tuple(triangulate_face(boundary, {v: positions.vertex_position(v) for v in boundary}))

    def _add_face(self, fid: FaceId) -> list[int]:
        """Rasterizes `fid`'s triangles (smaller key wins) and records them; returns the new slots (a patch)."""
        mesh = self.mesh
        uvs = mesh.face_uvs(fid)
        tris = self._triangles(fid)
        self._face_tris[fid] = (tris, uvs)
        if uvs is None:
            return []
        corner = dict(zip(mesh.face_vertices(fid), uvs))
        slots = []
        for k, tri in enumerate(tris):
            raster = raster_triangle(corner[tri[0]], corner[tri[1]], corner[tri[2]], self.width, self.height)
            if raster is None:
                continue
            if not self._free:
                self._grow(self._cap + 1)
            s = self._free.pop()
            self.tri_vertices[s] = tri
            self.tri_uvs[s] = (corner[tri[0]], corner[tri[1]], corner[tri[2]])
            self.tri_face[s] = int(fid)
            self.tri_index[s] = k
            self._tri_key[s] = int(fid) * _KEY_STRIDE + k
            self._tri_box[s] = raster[3]
            self._write(s, raster)
            slots.append(s)
        if slots:
            self._face_slots[fid] = slots
        return slots

    def _write(self, s: int, raster) -> None:
        flat, w1, w2, _box = raster
        current = self.slot[flat]
        held = current >= 0
        current_key = np.where(held, self._tri_key[np.where(held, current, 0)], np.iinfo(np.int64).max)
        win = self._tri_key[s] < current_key  # its own texels (a refill) hold the same values already
        if not win.any():
            return
        idx = flat[win]
        self.slot[idx] = s
        self.bary[idx, 0] = w1[win]
        self.bary[idx, 1] = w2[win]

    def _raster_slot(self, s: int):
        fid = FaceId(int(self.tri_face[s]))
        tris, uvs = self._face_tris[fid]
        tri = tris[int(self.tri_index[s])]
        corner = dict(zip(self.mesh.face_vertices(fid), uvs))
        return raster_triangle(corner[tri[0]], corner[tri[1]], corner[tri[2]], self.width, self.height)

    def _box_texels(self, box) -> np.ndarray:
        x0, y0, x1, y1 = (int(v) for v in box)
        ys = np.arange(y0, y1 + 1, dtype=np.int64)[:, None] * self.width
        return (ys + np.arange(x0, x1 + 1, dtype=np.int64)[None, :]).ravel()

    def _remove_face(self, fid: FaceId) -> list[np.ndarray]:
        """Frees `fid`'s triangles and clears the texels they owned; returns the boxes (x0, y0, x1, y1) cleared."""
        self._face_tris.pop(fid, None)
        boxes = []
        for s in self._face_slots.pop(fid, ()):
            box = self._tri_box[s].copy()
            region = self._box_texels(box)
            owned = region[self.slot[region] == s]
            self.slot[owned] = _EMPTY
            self.bary[owned] = 0.0
            self.tri_vertices[s] = -1
            self.tri_face[s] = -1
            self.tri_index[s] = -1
            self._tri_key[s] = np.iinfo(np.int64).max
            self._free.append(s)
            boxes.append(box)
        return boxes

    # -- patching ------------------------------------------------------------------------------------------------

    def patch(self, change) -> int:
        """Brings the map up to date with `change` (a taken `MeshWatch` / `SurfaceWatch` change of the mesh, or of the
        position source). Returns how many faces were re-rasterized (-1 = rebuilt)."""
        mesh = self.mesh
        dirty: set[FaceId] = set(getattr(change, "faces", {}) or ()) | set(getattr(change, "face_uvs", {}) or ())
        for fid in self._moved_triangulations(getattr(change, "vertices", {}) or (), dirty):
            dirty.add(fid)
        if not dirty:
            return 0
        if len(dirty) > max(REBUILD_SHARE * len(self._face_tris), REBUILD_MIN_FACES):
            self.rebuild()
            return -1
        cleared: list[np.ndarray] = []
        for fid in dirty:
            cleared.extend(self._remove_face(fid))
        for fid in sorted(dirty):
            if mesh.is_valid_face(fid):
                self._add_face(fid)
        if cleared:
            self._refill(cleared, dirty)
        return len(dirty)

    def _moved_triangulations(self, vertices: Iterable[VertexId], dirty: set[FaceId]) -> list[FaceId]:
        """Faces around moved vertices whose triangulation is no longer the stored one (only n-gons can change)."""
        mesh, seen, out = self.mesh, set(), []
        for vid in vertices:
            if not mesh.is_valid_vertex(vid):
                continue
            for eid in mesh.vertex_edges(vid):
                for fid in mesh.edge_faces(eid):
                    if fid in dirty or fid in seen:
                        continue
                    seen.add(fid)
                    stored = self._face_tris.get(fid)
                    if stored is None or len(stored[0]) < 2:
                        continue
                    if stored[0] != self._triangles(fid):
                        out.append(fid)
        return out

    def _refill(self, boxes: list[np.ndarray], dirty: set[FaceId]) -> None:
        """Cleared texels go to whichever remaining triangle covers them with the smallest key."""
        live = np.nonzero(self.tri_face >= 0)[0]
        if live.size == 0:
            return
        tb = self._tri_box[live]
        touch = np.zeros(live.size, dtype=bool)
        for x0, y0, x1, y1 in boxes:
            touch |= (tb[:, 0] <= x1) & (tb[:, 2] >= x0) & (tb[:, 1] <= y1) & (tb[:, 3] >= y0)
        for s in live[touch]:
            if FaceId(int(self.tri_face[s])) in dirty:
                continue  # just written
            raster = self._raster_slot(int(s))
            if raster is not None:
                self._write(int(s), raster)

    # -- reading -------------------------------------------------------------------------------------------------

    def mapped(self) -> np.ndarray:
        """Flat indices of every texel that belongs to a triangle."""
        return np.nonzero(self.slot >= 0)[0]

    def owner(self, texels) -> list[tuple[FaceId, int, float, float]]:
        """(face, triangle index, w1, w2) per texel (for tests and diagnostics; -1 face = none)."""
        texels = np.asarray(texels, dtype=np.int64)
        out = []
        for t in texels:
            s = int(self.slot[t])
            if s < 0:
                out.append((FaceId(-1), -1, 0.0, 0.0))
            else:
                out.append((FaceId(int(self.tri_face[s])), int(self.tri_index[s]), float(self.bary[t, 0]),
                            float(self.bary[t, 1])))
        return out

    def texel_at(self, u: float, v: float) -> int:
        """The flat index of the texel whose square holds (u, v); -1 outside [0, 1)."""
        x, y = int(np.floor(u * self.width)), int(np.floor(v * self.height))
        if not (0 <= x < self.width and 0 <= y < self.height):
            return -1
        return y * self.width + x

    def texel_uvs(self, texels) -> np.ndarray:
        texels = np.asarray(texels, dtype=np.int64)
        return np.stack(((texels % self.width + 0.5) / self.width, (texels // self.width + 0.5) / self.height), axis=1)

    def surface_points(self, texels, positions=None) -> np.ndarray:
        """(n, 3) float64 surface points of mapped `texels` from `positions` (anything with `vertex_position`; default
        the source the map was built with). A texel without a triangle raises `ValueError`."""
        texels = np.asarray(texels, dtype=np.int64)
        slots = self.slot[texels]
        if np.any(slots < 0):
            raise ValueError("surface_points: a texel without a triangle")
        corners = self.tri_vertices[slots]
        unique, inverse = np.unique(corners, return_inverse=True)
        source = self.positions if positions is None else positions
        table = np.array([source.vertex_position(VertexId(int(v))) for v in unique], dtype=np.float64)
        p = table[inverse.reshape(corners.shape)]
        w = self.bary[texels].astype(np.float64)
        w0 = 1.0 - w[:, 0] - w[:, 1]
        return p[:, 0] * w0[:, None] + p[:, 1] * w[:, 0:1] + p[:, 2] * w[:, 1:2]
