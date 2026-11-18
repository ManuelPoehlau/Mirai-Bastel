"""The surface the Paint Room paints on (AD-037 §8 Phase 2, P-10 revised: the surface that is shown).

A `PaintSurface` is one drawn mesh with its texel map: the edit mesh (the cage, SubD off) or the SubD preview's derived
mesh (SubD on, `SubdSurfaceProvider.surface_mesh`: its faces and linearly refined UVs, AD-026 §6). The hit, the dab
centre, the footprint and the cursor circle all use this one surface, so a dab painted with SubD on is round on the SubD
surface (§8.1: on the cage it was 1.23 : 1 oval at p50).

- **Hit** (`hit`): the nearest ray hit on the drawn triangles (`triangulate_face`, the texel map's split), every face
  counted - one without UVs occludes too -, hidden faces left out. Möller-Trumbore over all triangles in NumPy (72,016
  triangles at SubD level 2 on the Gollum head: no acceleration structure needed for one ray per event).
- **Footprint** (`footprint`, audit §4.2 principle 3): the texels whose surface point lies within the world radius of the
  centre, on triangles facing the same way as the surface at the hit (so the other side of a thin part - the inside of a
  lid or a lip - is not painted through; `PROVISIONAL`). A stroke crosses UV seams without a break: texels of both islands
  are selected by their 3D position.
- **Mirror** (`mirror`): the dab centre and the facing reflected across the mesh's symmetry plane (`SymmetryDefinition`,
  object space - the derived mesh shares it); the mirrored footprint lands on the nearest surface (audit §5.2).
- **Seam padding** (`seam_pad`, principle 5): unmapped texels up to `pad` texels outside an island take the colour of the
  nearest island texel (8-neighbour dilation), so bilinear filtering and mip levels do not show the background at seams.

Positions are re-read when the mesh reports moved vertices, topology and UV changes patch the texel map (`Mesh.watch`,
AD-023); a new derived mesh (another SubD level) is a new `PaintSurface`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core import FaceId, Mesh, VertexId

from .texel_map import TexelMap

#: Footprint triangles must face the hit's way: cosine of the largest angle between their normals (`PROVISIONAL`).
FACING_MIN = 0.0
#: Ray-triangle tolerance (`mirai.viewport.picking._ray_triangle_intersection`'s).
_EPS = 1e-9


def pad_width(width: int) -> int:
    """Seam padding in texels (`PROVISIONAL`, audit §4.2: 4-8 px at 2048²): 4 at 2048², 2 at 1024², at least 2."""
    return max(2, int(width) // 512)


@dataclass(frozen=True)
class Hit:
    point: np.ndarray          # (3,) object space
    normal: np.ndarray         # (3,) unit, the triangle's winding normal
    face: FaceId
    uv: tuple[float, float] | None  # the interpolated UV at the hit (None: the face has no UVs)
    distance: float


class PaintSurface:
    """One drawn mesh, its texel map and the tables the dab reads (module docstring)."""

    def __init__(self, mesh: Mesh, width: int, height: int, kind: str = "cage", hidden_faces=frozenset()) -> None:
        self.mesh = mesh
        self.kind = kind
        self.hidden_faces = frozenset(hidden_faces)
        self.map = TexelMap(mesh, width, height)
        self._watch = mesh.watch()
        self._tables()

    @property
    def width(self) -> int:
        return self.map.width

    @property
    def height(self) -> int:
        return self.map.height

    def close(self) -> None:
        if self._watch is not None:
            self._watch.close()
            self._watch = None

    def set_hidden(self, faces) -> None:
        faces = frozenset(faces)
        if faces != self.hidden_faces:
            self.hidden_faces = faces
            self._hit_tables()

    # -- tables --------------------------------------------------------------------------------------------------

    def _tables(self) -> None:
        mesh = self.mesh
        ids = np.array([int(v) for v in mesh.all_vertex_ids()], dtype=np.int64)
        self._row_of = np.full(int(ids.max()) + 1 if ids.size else 1, -1, dtype=np.int64)
        self._row_of[ids] = np.arange(ids.size)
        self._ids = ids
        # the mapped texels grouped by their triangle slot (the footprint gathers per near triangle)
        texels = self.map.mapped()
        slots = self.map.slot[texels]
        order = np.argsort(slots)
        self._texels = texels[order]
        counts = np.bincount(slots, minlength=self.map.tri_face.size)
        self._offsets = np.concatenate(([0], np.cumsum(counts)))
        self._hit_tables(geometry=False)
        self._positions()

    def _hit_tables(self, geometry: bool = True) -> None:
        """The drawn triangles the ray is tested against: the texel map's triangles plus those it holds no texel for (a
        face without UVs or without UV area still occludes), hidden faces left out."""
        texel_map = self.map
        live = np.nonzero(texel_map.tri_face >= 0)[0]
        rows = [self._row_of[texel_map.tri_vertices[live]]]
        faces = [texel_map.tri_face[live]]
        uvs = [texel_map.tri_uvs[live]]
        has_uv = [np.ones(live.size, dtype=bool)]
        extra_rows, extra_faces, extra_uvs, extra_has = [], [], [], []
        slots_of = texel_map._face_slots
        #: faces drawn without a single texel (no UVs, no UV area, outside 0-1): the dab skips them (P-13)
        self.unpaintable = sum(1 for fid in texel_map._face_tris if fid not in slots_of and fid not in self.hidden_faces)
        for fid, (tris, face_uvs) in texel_map._face_tris.items():
            held = slots_of.get(fid, ())
            if len(held) == len(tris):
                continue
            corner = None if face_uvs is None else dict(zip(self.mesh.face_vertices(fid), face_uvs))
            kept = {int(texel_map.tri_index[s]) for s in held}
            for k, tri in enumerate(tris):
                if k in kept:
                    continue
                extra_rows.append([self._row_of[v] for v in tri])
                extra_faces.append(int(fid))
                extra_uvs.append([(0.0, 0.0)] * 3 if corner is None else [corner[v] for v in tri])
                extra_has.append(corner is not None)
        if extra_rows:
            rows.append(np.array(extra_rows, dtype=np.int64))
            faces.append(np.array(extra_faces, dtype=np.int64))
            uvs.append(np.array(extra_uvs, dtype=np.float64))
            has_uv.append(np.array(extra_has, dtype=bool))
        hit_rows = np.concatenate(rows).reshape(-1, 3)
        hit_face = np.concatenate(faces)
        keep = np.ones(hit_face.size, dtype=bool)
        #: texel-map slots of hidden faces: not drawn, so neither hit nor painted
        self._slot_hidden = np.zeros(texel_map.tri_face.size, dtype=bool)
        if self.hidden_faces:
            hidden = np.fromiter((int(f) for f in self.hidden_faces), dtype=np.int64)
            keep = ~np.isin(hit_face, hidden)
            self._slot_hidden = np.isin(texel_map.tri_face, hidden)
        self._hit_rows = hit_rows[keep]
        self._hit_face = hit_face[keep]
        self._hit_uvs = np.concatenate(uvs).reshape(-1, 3, 2)[keep]
        self._hit_has_uv = np.concatenate(has_uv)[keep]
        if geometry:
            self._hit_geometry()

    def _positions(self) -> None:
        mesh = self.mesh
        self._p = np.array([mesh.vertex_position(VertexId(int(v))) for v in self._ids], dtype=np.float64).reshape(-1, 3)
        texel_map = self.map
        live = texel_map.tri_face >= 0
        corners = np.where(live[:, None], self._row_of[texel_map.tri_vertices.clip(min=0)], 0)
        pts = self._p[corners] if self._p.size else np.zeros((len(corners), 3, 3))
        self._tri_rows = corners
        self._live = live
        self._lo = pts.min(axis=1)
        self._hi = pts.max(axis=1)
        normals = np.cross(pts[:, 1] - pts[:, 0], pts[:, 2] - pts[:, 0])
        length = np.linalg.norm(normals, axis=1)
        self._tri_normal = normals / np.where(length > 0.0, length, 1.0)[:, None]
        # every mapped texel's surface point, in the slot-grouped order of `_texels`, filled per triangle at its first dab
        # (float32: a dab compares distances to a radius; ~12 bytes per mapped texel; reset when positions change)
        self._texel_points = np.empty((self._texels.size, 3), dtype=np.float32)
        self._slot_ready = np.zeros(texel_map.tri_face.size, dtype=bool)
        self._p32 = self._p.astype(np.float32)
        self._slot_clusters = _clusters(np.where(live[:, None], self._lo, np.inf), np.where(live[:, None], self._hi, -np.inf))
        self._hit_geometry()

    def _hit_geometry(self) -> None:
        p = self._p[self._hit_rows] if self._hit_rows.size else np.zeros((0, 3, 3))
        self._v0 = p[:, 0]
        self._e1 = p[:, 1] - p[:, 0]
        self._e2 = p[:, 2] - p[:, 0]
        self._hit_clusters = _clusters(p.min(axis=1), p.max(axis=1))

    def sync(self) -> bool:
        """Brings the surface up to date with its mesh's changes since the last call; True = something changed."""
        if self._watch is None:
            return False
        change = self._watch.take()
        if change.is_empty():
            return False
        structural = bool(change.faces or change.face_uvs or change.edges) or any(
            (int(v) < self._row_of.size and self._row_of[int(v)] >= 0) != self.mesh.is_valid_vertex(v)
            for v in change.vertices)
        if structural:
            self.map.patch(change)
            self._tables()
        else:
            self.map.patch(change)  # a moved vertex can change a concave n-gon's triangulation
            self._positions()
        return True

    # -- queries -------------------------------------------------------------------------------------------------

    def hit(self, origin, direction) -> Hit | None:
        """The nearest hit of the ray on the drawn surface (module docstring), or None."""
        if self._hit_rows.size == 0:
            return None
        o = np.asarray(origin, dtype=np.float64)
        d = np.asarray(direction, dtype=np.float64)
        tris = self._hit_clusters.ray(o, d)
        if tris.size == 0:
            return None
        e1, e2 = self._e1[tris], self._e2[tris]
        h = np.cross(d[None, :], e2)
        det = np.einsum("ij,ij->i", e1, h)
        ok = np.abs(det) >= _EPS
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        s = o[None, :] - self._v0[tris]
        u = inv * np.einsum("ij,ij->i", s, h)
        q = np.cross(s, e1)
        v = inv * (q @ d)
        t = inv * np.einsum("ij,ij->i", e2, q)
        ok &= (u >= -_EPS) & (u <= 1.0 + _EPS) & (v >= -_EPS) & (u + v <= 1.0 + _EPS) & (t > _EPS)
        if not ok.any():
            return None
        candidates = np.nonzero(ok)[0]
        k = int(candidates[np.argmin(t[candidates])])
        i = int(tris[k])
        point = o + t[k] * d
        normal = np.cross(e1[k], e2[k])
        length = float(np.linalg.norm(normal))
        normal = normal / length if length > 0.0 else np.array([0.0, 0.0, 1.0])
        uv = None
        if self._hit_has_uv[i]:
            w = np.array([1.0 - u[k] - v[k], u[k], v[k]])
            uv = tuple(float(x) for x in w @ self._hit_uvs[i])
        return Hit(point, normal, FaceId(int(self._hit_face[i])), uv, float(t[k]))

    def footprint(self, centre, radius: float, facing=None) -> tuple[np.ndarray, np.ndarray]:
        """`(texels, x)`: the mapped texels whose surface point lies within `radius` of `centre` and `x = d / radius`
        in [0, 1); only triangles whose normal is within 90 degrees of `facing` (None = all)."""
        c = np.asarray(centre, dtype=np.float64)
        r = float(radius)
        slots = self._slot_clusters.box(c - r, c + r)
        near = np.all(self._lo[slots] <= c + r, axis=1) & np.all(self._hi[slots] >= c - r, axis=1)
        near &= self._live[slots] & ~self._slot_hidden[slots]
        if facing is not None:
            near &= self._tri_normal[slots] @ np.asarray(facing, dtype=np.float64) > FACING_MIN
        slots = slots[near]
        empty = (np.zeros(0, np.int64), np.zeros(0, np.float64))
        if slots.size == 0:
            return empty
        index = self._ranges(slots)
        if index.size == 0:
            return empty
        todo = slots[~self._slot_ready[slots]]
        if todo.size:
            self._fill_points(todo)
        rel = self._texel_points[index] - c.astype(np.float32)
        d2 = np.einsum("ij,ij->i", rel, rel) / np.float32(r * r)
        inside = np.flatnonzero(d2 < 1.0)
        return self._texels[index[inside]], np.sqrt(d2[inside])

    def _ranges(self, slots: np.ndarray) -> np.ndarray:
        """The positions [start, end) in `_texels` of every slot in `slots`, as one index array."""
        starts, ends = self._offsets[slots], self._offsets[slots + 1]
        lengths = ends - starts
        total = int(lengths.sum())
        if total == 0:
            return np.zeros(0, dtype=np.int64)
        return np.repeat(starts - np.concatenate(([0], np.cumsum(lengths)[:-1])), lengths) + np.arange(total)

    def _fill_points(self, slots: np.ndarray) -> None:
        index = self._ranges(slots)
        if index.size:
            lengths = self._offsets[slots + 1] - self._offsets[slots]
            rows = self._tri_rows[np.repeat(slots, lengths)]
            w = self.map.bary[self._texels[index]]
            p = self._p32
            points = p[rows[:, 0]] * (1.0 - w[:, 0] - w[:, 1])[:, None]
            points += p[rows[:, 1]] * w[:, 0:1]
            points += p[rows[:, 2]] * w[:, 1:2]
            self._texel_points[index] = points
        self._slot_ready[slots] = True

    def texel_of_uv(self, uv) -> int:
        """The texel whose square holds `uv` (-1 outside the image)."""
        return self.map.texel_at(uv[0], uv[1])

    def circle(self, centre, normal, radius: float, segments: int = 48) -> list[tuple]:
        """The cursor circle: `segments` line segments of a circle of `radius` around `centre` in the plane normal to
        `normal` (object space)."""
        n = np.asarray(normal, dtype=np.float64)
        helper = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        a = np.cross(n, helper)
        a /= np.linalg.norm(a)
        b = np.cross(n, a)
        angles = np.linspace(0.0, 2.0 * np.pi, segments + 1)
        ring = np.asarray(centre, dtype=np.float64)[None, :] + radius * (np.cos(angles)[:, None] * a
                                                                          + np.sin(angles)[:, None] * b)
        points = [tuple(float(x) for x in p) for p in ring]
        return [(points[i], points[i + 1]) for i in range(segments)]


#: Triangles per cluster of the culling step (`_Clusters`; `PROVISIONAL`, agent-set).
CLUSTER = 64


class _Clusters:
    """Boxes over runs of `CLUSTER` consecutive triangles (faces are stored in id order, which keeps a run mostly local;
    an incoherent order only culls less, it never misses a triangle)."""

    def __init__(self, lo: np.ndarray, hi: np.ndarray) -> None:
        n = len(lo)
        self.n = n
        groups = max(1, -(-n // CLUSTER))
        pad = groups * CLUSTER - n
        lo_p = np.concatenate((lo, np.full((pad, 3), np.inf))) if pad else lo
        hi_p = np.concatenate((hi, np.full((pad, 3), -np.inf))) if pad else hi
        self.lo = lo_p.reshape(groups, CLUSTER, 3).min(axis=1) if n else np.full((1, 3), np.inf)
        self.hi = hi_p.reshape(groups, CLUSTER, 3).max(axis=1) if n else np.full((1, 3), -np.inf)

    def _members(self, groups: np.ndarray) -> np.ndarray:
        if groups.size == 0:
            return np.zeros(0, dtype=np.int64)
        index = (groups[:, None] * CLUSTER + np.arange(CLUSTER)[None, :]).ravel()
        return index[index < self.n]

    def ray(self, o: np.ndarray, d: np.ndarray) -> np.ndarray:
        """Triangles whose cluster box the ray (t > 0) meets (slab test)."""
        with np.errstate(divide="ignore", invalid="ignore"):
            inv = 1.0 / d
            t0 = (self.lo - o) * inv
            t1 = (self.hi - o) * inv
        near = np.nanmax(np.minimum(t0, t1), axis=1)
        far = np.nanmin(np.maximum(t0, t1), axis=1)
        return self._members(np.nonzero((far >= np.maximum(near, 0.0)) & np.isfinite(far))[0])

    def box(self, lo, hi) -> np.ndarray:
        """Triangles whose cluster box meets the box [lo, hi]."""
        meets = np.all(self.lo <= hi, axis=1) & np.all(self.hi >= lo, axis=1)
        return self._members(np.nonzero(meets)[0])


def _clusters(lo: np.ndarray, hi: np.ndarray) -> _Clusters:
    return _Clusters(lo, hi)


def mirror(definition, point, normal) -> tuple[np.ndarray, np.ndarray]:
    """`point` and `normal` reflected across the plane of `definition` (a `SymmetryDefinition`, unit normal)."""
    q = np.asarray(definition.plane_point, dtype=np.float64)
    n = np.asarray(definition.plane_normal, dtype=np.float64)
    p = np.asarray(point, dtype=np.float64)
    m = np.asarray(normal, dtype=np.float64)
    return p - 2.0 * np.dot(p - q, n) * n, m - 2.0 * np.dot(m, n) * n


_NEIGHBOURS = ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1))


def seam_pad(texel_map: TexelMap, boxes, pad: int) -> tuple[np.ndarray, np.ndarray]:
    """`(destination texels, source texels)`: every unmapped texel within `pad` steps (8-neighbour) of an island and inside
    one of `boxes` (x0, y0, x1, y1 exclusive, each grown by `pad`) takes its nearest island texel (the first neighbour in
    `_NEIGHBOURS` order at each step - a fixed rule, so the same pixels give the same padding)."""
    width, height = texel_map.width, texel_map.height
    mapped = (texel_map.slot >= 0).reshape(height, width)
    dst_all, src_all = [], []
    for x0, y0, x1, y1 in boxes:
        gx0, gy0 = max(int(x0) - pad, 0), max(int(y0) - pad, 0)
        gx1, gy1 = min(int(x1) + pad, width), min(int(y1) + pad, height)
        wx0, wy0 = max(gx0 - pad, 0), max(gy0 - pad, 0)  # sources may lie up to `pad` beyond the grown box
        wx1, wy1 = min(gx1 + pad, width), min(gy1 + pad, height)
        window = mapped[wy0:wy1, wx0:wx1]
        if window.all() or not window.any():
            continue
        ys, xs = np.mgrid[wy0:wy1, wx0:wx1]
        source = np.where(window, ys * width + xs, -1)
        for _ in range(pad):
            previous = source.copy()
            for dy, dx in _NEIGHBOURS:
                shifted = np.full_like(previous, -1)
                sy0, sy1 = max(dy, 0), previous.shape[0] + min(dy, 0)
                sx0, sx1 = max(dx, 0), previous.shape[1] + min(dx, 0)
                shifted[sy0:sy1, sx0:sx1] = previous[sy0 - dy:sy1 - dy, sx0 - dx:sx1 - dx]
                take = (source < 0) & (shifted >= 0)
                source[take] = shifted[take]
        inner = np.zeros_like(window)
        inner[gy0 - wy0:gy1 - wy0, gx0 - wx0:gx1 - wx0] = True
        pick = inner & ~window & (source >= 0)
        dst_all.append((ys * width + xs)[pick])
        src_all.append(source[pick])
    if not dst_all:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    dst = np.concatenate(dst_all).astype(np.int64)
    src = np.concatenate(src_all).astype(np.int64)
    dst, first = np.unique(dst, return_index=True)
    return dst, src[first]
