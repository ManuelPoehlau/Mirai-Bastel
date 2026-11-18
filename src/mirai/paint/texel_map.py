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

Memory at 2048²: 4 bytes of triangle slot and 8 bytes of weights per texel (48 MiB), plus the triangle table.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np

from core import FaceId, Mesh, VertexId
from viewport.derived import triangulate_face

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
    px = np.arange(x0 - ax, x1 - ax + 0.5, dtype=np.float64)  # x - ax for x = x0 .. x1 (exact steps of 1)
    py = np.arange(y0 - ay, y1 - ay + 0.5, dtype=np.float64)[:, None]
    inv = 1.0 / det
    w1 = px * (e2y * inv) - py * (e2x * inv)
    w2 = py * (e1x * inv) - px * (e1y * inv)
    inside = (w1 >= -_INSIDE_EPS) & (w2 >= -_INSIDE_EPS) & (w1 + w2 <= 1.0 + _INSIDE_EPS)
    rows, cols = np.nonzero(inside)
    if rows.size == 0:
        return None
    box = (x0 + int(cols.min()), y0 + int(rows[0]), x0 + int(cols.max()), y0 + int(rows[-1]))  # rows ascend
    return (rows + y0) * width + (cols + x0), w1[rows, cols], w2[rows, cols], box


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
        self.tri_face = np.zeros(0, dtype=np.int64)
        self.tri_index = np.zeros(0, dtype=np.int32)
        self._tri_key = np.zeros(0, dtype=np.int64)
        self._tri_box = np.zeros((0, 4), dtype=np.int32)
        self._free: list[int] = []
        self._face_slots: dict[FaceId, list[int]] = {}
        self._face_tris: dict[FaceId, tuple] = {}
        faces = self.mesh.all_face_ids()
        self._grow(2 * len(faces) + 16)
        for fid in faces:  # ascending ids = ascending keys: a texel already held keeps its smaller key
            self._add_face(fid, building=True)

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

    def _add_face(self, fid: FaceId, building: bool = False) -> list[int]:
        """Rasterizes `fid`'s triangles (smaller key wins) and records them; returns the new slots. `building`: the
        map is filled in ascending key order, so a held texel is never taken over (no key comparison)."""
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
            self.tri_face[s] = int(fid)
            self.tri_index[s] = k
            self._tri_key[s] = int(fid) * _KEY_STRIDE + k
            self._tri_box[s] = raster[3]
            if building:
                flat = raster[0]
                free = self.slot[flat] < 0
                idx = flat[free]
                self.slot[idx] = s
                self.bary[idx, 0] = raster[1][free]
                self.bary[idx, 1] = raster[2][free]
            else:
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
