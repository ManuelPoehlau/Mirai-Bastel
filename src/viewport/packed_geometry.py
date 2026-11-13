"""PackedGeometry - the viewport's derived geometry on slot-indexed NumPy arrays (AD-032, audit 2026-11-10 option O3,
stage 1). Names `PROVISIONAL`.

`RenderMesh` owns one. Every array is indexed by `RenderMesh`'s own layout: a vertex *slot* (the vertex's index in the
GPU vertex buffers) and a face *row* (the face's row in the face-data buffers). The layout rules stay `RenderMesh`'s
(module docstring there): slots and rows keep their index between two full rebuilds, freed ones are reused, a full
rebuild lays everything out compactly with spare capacity. The arrays therefore never grow between two full rebuilds;
only the two ragged pools below do.

What it holds:

- `P`  (slots x 3, float64) - positions; a free slot holds `DEAD_POSITION`;
- `VN` (slots x 3, float64) - vertex normals; a free slot (0, 0, 0);
- `FN` (rows x 3, float64)  - face normals (Newell, normalised); a free row (0, 0, 0);
- `corners` - per row the vertex slots of the face's boundary in boundary order (ragged; `face_size` = its length,
  0 for a free row);
- `vertex_faces` - per slot the rows of the faces around the vertex, **in ascending `FaceId` order** (ragged).

It knows no IDs: `RenderMesh` maps `VertexId` / `FaceId` to slots / rows and back, and writes topology changes in
here from the change journal (`_patch_topology`), the same way it patches its slot layout. NumPy is used only here and in
`RenderMesh` (above the Core; `src/core` imports no NumPy).

**Normals - the definition and the summation order (bit-identity).** A face normal is the normalised Newell sum over the
face's boundary: per corner k, from 0.0, `n += ((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) *
(a.y + b.y))` with a = corner k, b = corner k+1 (wrapping), then `n / sqrt(n.x*n.x + n.y*n.y + n.z*n.z)`, (0, 0, 0) below
a length of 1e-12 - exactly `derived.face_normal`. A vertex normal is the normalised sum of the face normals around the
vertex, added from 0.0 in ascending `FaceId` order - `derived.DerivedGeometry`, the pure-Python reference. The kernels
below add in exactly these orders (one column of corners / faces at a time, never `sum` / `reduceat`, whose internal
order is not the Python one), and NumPy's `+ - * / sqrt` on float64 are the IEEE operations Python's floats use: the
arrays are **bit-identical** to the reference (`tests/test_packed_geometry.py`). Because the face order is a property of
the IDs, not of the layout, a patched layout and a fresh full build hold bit-identical normals too.
"""

from __future__ import annotations

import sys
from importlib import metadata

#: The NumPy `requirements.txt` pins (Manu D1; `tests/test_packed_geometry.py` keeps both equal).
PINNED_NUMPY = "2.2.6"
_RULE = "docs/architecture/REFERENCE_HARDWARE.md §4"


def _warn_unpinned_numpy() -> None:
    """One stderr line, written before NumPy is loaded, when the installed NumPy is not the pinned one: on the
    reference PC a newer NumPy can end the process inside its own import without any Python message (Python 3.14,
    2026-11-13: exit code 0xC0000409), so this is the only place that can still say why."""
    try:
        installed = metadata.version("numpy")
    except metadata.PackageNotFoundError:
        return  # the import below raises ImportError with the hint
    if installed == PINNED_NUMPY:
        return
    print(
        f"Mirai: NumPy {installed} under Python {sys.version.split()[0]} ({sys.executable}); pinned is "
        f"numpy=={PINNED_NUMPY}, on the reference PC under Python 3.12 ({_RULE}). If the process now ends without a "
        "message, this NumPy did not start on this CPU.",
        file=sys.stderr, flush=True,
    )


_warn_unpinned_numpy()
try:
    import numpy as np
except (ImportError, RuntimeError) as exc:  # RuntimeError: a NumPy built for x86-64-v2 on a CPU without it
    raise ImportError(
        f"Mirai needs NumPy (requirements.txt: numpy=={PINNED_NUMPY}; on the reference PC under Python 3.12, see "
        f"{_RULE}): {type(exc).__name__}: {exc}"
    ) from exc

#: Spare entries per vertex in the vertex -> faces pool after a full build: a topology patch that adds a face or two
#: around a vertex writes in place instead of moving the vertex's list to the end of the pool.
VERTEX_FACES_SLACK = 2
#: Below this many candidates per element of the target range, duplicates are removed by sorting; above it, by a mark
#: array over the whole range (O(range), but no sort).
_UNIQUE_SORT_RATIO = 16
_EPS = 1e-12
_INDEX = np.intp


def _unique(values: np.ndarray, size: int) -> np.ndarray:
    """The distinct entries of `values` (ints in [0, size)), ascending."""
    if len(values) * _UNIQUE_SORT_RATIO < size:
        return np.unique(values)
    mark = np.zeros(size, dtype=bool)
    mark[values] = True
    return np.flatnonzero(mark)


def _normalise(acc: np.ndarray) -> np.ndarray:
    """`derived._normalize` per row of `acc` (m x 3), in place: the same operations in the same order."""
    x, y, z = acc[:, 0], acc[:, 1], acc[:, 2]
    length = np.sqrt(x * x + y * y + z * z)
    zero = length < _EPS
    length[zero] = 1.0
    acc /= length[:, None]
    acc[zero] = 0.0
    return acc


class Ragged:
    """Per item (slot or row) a short list of ints in one pool: `start`, `count` and `capacity` per item. A list that
    outgrows its block moves to the end of the pool; the pool is compacted when more than half of it is unused."""

    def __init__(self, n_items: int, counts: np.ndarray, values: np.ndarray, slack: int) -> None:
        counts = counts.astype(_INDEX)
        self.count = counts.copy()
        self.capacity = counts + slack
        self.start = np.zeros(n_items, dtype=_INDEX)
        if n_items:
            np.cumsum(self.capacity[:-1], out=self.start[1:])
        self.end = int(self.capacity.sum())
        self.pool = np.zeros(self.end + max(16, self.end // 8), dtype=_INDEX)
        self.pool[self._where(np.arange(n_items, dtype=_INDEX))] = values
        self.slack = slack

    def _where(self, items: np.ndarray) -> np.ndarray:
        """Pool positions of the entries of `items`, concatenated in that order."""
        counts = self.count[items]
        total = int(counts.sum())
        offsets = np.cumsum(counts) - counts
        return np.repeat(self.start[items] - offsets, counts) + np.arange(total, dtype=_INDEX)

    def gather(self, items: np.ndarray) -> np.ndarray:
        """The entries of `items`, concatenated in that order."""
        return self.pool[self._where(items)]

    def get(self, item: int) -> list[int]:
        start = int(self.start[item])
        return self.pool[start:start + int(self.count[item])].tolist()

    def set(self, item: int, values: list[int]) -> None:
        n = len(values)
        if n > self.capacity[item]:
            need = n + self.slack
            if self.end + need > len(self.pool):
                self._make_room(need)
            self.start[item] = self.end
            self.capacity[item] = need
            self.end += need
        start = int(self.start[item])
        self.pool[start:start + n] = values
        self.count[item] = n

    def _make_room(self, need: int) -> None:
        if 2 * int(self.capacity.sum()) < self.end:
            self._compact()
        if self.end + need > len(self.pool):
            grown = max(2 * len(self.pool), self.end + need)
            self.pool = np.concatenate((self.pool, np.zeros(grown - len(self.pool), dtype=_INDEX)))

    def _compact(self) -> None:
        """Every item's block moved together, in item order (the blocks left behind by moved lists are dropped)."""
        caps = self.capacity
        starts = np.cumsum(caps) - caps
        where = np.repeat(self.start - starts, caps) + np.arange(int(caps.sum()), dtype=_INDEX)
        pool = self.pool[where]
        self.start = starts.astype(_INDEX)
        self.end = len(pool)
        self.pool = np.concatenate((pool, np.zeros(max(16, self.end // 8), dtype=_INDEX)))


class PackedGeometry:
    """Positions, face and vertex normals and the adjacency they need, on `RenderMesh`'s slots and rows (module
    docstring). Built whole by `build`; kept in step by `RenderMesh` through the patch methods."""

    def __init__(self) -> None:
        self.P = np.zeros((0, 3))
        self.VN = np.zeros((0, 3))
        self.FN = np.zeros((0, 3))
        self.live = np.zeros(0, dtype=bool)
        self.corners = Ragged(0, np.zeros(0, dtype=_INDEX), np.zeros(0, dtype=_INDEX), 0)
        self.vertex_faces = Ragged(0, np.zeros(0, dtype=_INDEX), np.zeros(0, dtype=_INDEX), VERTEX_FACES_SLACK)
        self._bounds: tuple | None = None

    # -- the full build ---------------------------------------------------------------------------------

    def build(self, positions: np.ndarray, live: np.ndarray, face_sizes: np.ndarray, corners: np.ndarray,
              face_ids: np.ndarray) -> None:
        """Everything from scratch. `positions` / `live`: per slot (free slots: `live` False, any position);
        `face_sizes`: per row the corner count (0 = free row); `corners`: the vertex slots of all live rows' boundaries,
        row by row; `face_ids`: per row its `FaceId` as an int (free rows: any value)."""
        n_slots, n_rows = len(positions), len(face_sizes)
        self.P = np.ascontiguousarray(positions, dtype=np.float64)
        self.live = np.asarray(live, dtype=bool)
        self.corners = Ragged(n_rows, face_sizes, corners, 0)
        # vertex -> faces: the (slot, row) pairs of every corner, sorted by slot, then by FaceId; a face that holds a
        # vertex twice counts once (like the reference's sets).
        corner_rows = np.repeat(np.arange(n_rows, dtype=_INDEX), face_sizes.astype(_INDEX))
        corner_slots = np.asarray(corners, dtype=_INDEX)
        order = np.lexsort((face_ids[corner_rows], corner_slots))
        slots_sorted, rows_sorted = corner_slots[order], corner_rows[order]
        keep = np.ones(len(order), dtype=bool)
        keep[1:] = (slots_sorted[1:] != slots_sorted[:-1]) | (rows_sorted[1:] != rows_sorted[:-1])
        counts = np.bincount(slots_sorted[keep], minlength=n_slots)
        self.vertex_faces = Ragged(n_slots, counts, rows_sorted[keep], VERTEX_FACES_SLACK)
        self.FN = np.zeros((n_rows, 3))
        self.VN = np.zeros((n_slots, 3))
        self.update_face_normals(np.flatnonzero(face_sizes))
        self.update_vertex_normals(np.flatnonzero(self.live))
        self._bounds = None

    # -- per frame: a position change ------------------------------------------------------------------

    def neighbourhood(self, slots: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(rows, slots), both ascending: the faces around the moved `slots`, and every vertex of those faces - the
        part whose face / vertex normals a move of `slots` changes."""
        rows = _unique(self.vertex_faces.gather(slots), len(self.FN))
        return rows, _unique(self.corners.gather(rows), len(self.P))

    def update_face_normals(self, rows: np.ndarray) -> None:
        """Recomputes `FN` of `rows` from `P` (Newell, module docstring)."""
        m = len(rows)
        if not m:
            return
        corners = self.corners
        sizes = corners.count[rows]
        smin, smax = int(sizes.min()), int(sizes.max())
        if smin != smax:  # longest faces first: the faces that still have a corner k are a prefix
            order = np.argsort(-sizes, kind="stable")
            rows, sizes = rows[order], sizes[order]
        starts, pool, P = corners.start[rows], corners.pool, self.P
        neg = -sizes

        def prefix(k: int) -> int:
            return m if k < smin else int(np.searchsorted(neg, -k, side="left"))

        points = [P[pool[starts[:prefix(k)] + k]] for k in range(smax)]
        acc = np.zeros((m, 3))
        for k in range(smax):
            a = points[k]
            mk = len(a)
            if k + 1 < smin:
                b = points[k + 1]
            else:  # corner k+1, or corner 0 for the faces whose last corner this is
                nxt = points[k + 1] if k + 1 < smax else points[0][:0]
                b = np.concatenate((nxt, points[0][len(nxt):mk]))
            d, s = a - b, a + b
            acc[:mk] += d[:, (1, 2, 0)] * s[:, (2, 0, 1)]
        _normalise(acc)
        if smin < 3:
            acc[sizes < 3] = 0.0
        self.FN[rows] = acc

    def update_vertex_normals(self, slots: np.ndarray) -> None:
        """Recomputes `VN` of `slots` from `FN` (the faces in ascending `FaceId` order, module docstring)."""
        m = len(slots)
        if not m:
            return
        lists = self.vertex_faces
        counts = lists.count[slots]
        cmin, cmax = int(counts.min()), int(counts.max())
        if cmin != cmax:
            order = np.argsort(-counts, kind="stable")
            slots, counts = slots[order], counts[order]
        starts, pool, FN = lists.start[slots], lists.pool, self.FN
        neg = -counts
        acc = np.zeros((m, 3))
        for k in range(cmax):
            mk = m if k < cmin else int(np.searchsorted(neg, -k, side="left"))
            acc[:mk] += FN[pool[starts[:mk] + k]]
        self.VN[slots] = _normalise(acc)

    # -- topology patches (RenderMesh._patch_topology) --------------------------------------------------

    def set_face(self, row: int, slots: list[int]) -> None:
        """Row `row` now holds a face with this boundary (its normal: `update_face_normals`)."""
        self.corners.set(row, slots)

    def clear_face(self, row: int) -> None:
        self.corners.count[row] = 0
        self.FN[row] = 0.0

    def faces_of(self, slot: int) -> list[int]:
        return self.vertex_faces.get(slot)

    def set_faces_of(self, slot: int, rows: list[int]) -> None:
        """The rows around vertex `slot`, in ascending `FaceId` order (the caller sorts)."""
        self.vertex_faces.set(slot, rows)

    def rows_around(self, slots: np.ndarray) -> np.ndarray:
        return _unique(self.vertex_faces.gather(slots), len(self.FN))

    def clear_vertex(self, slot: int, dead_position: tuple) -> None:
        self.P[slot] = dead_position
        self.VN[slot] = 0.0
        self.live[slot] = False
        self.vertex_faces.count[slot] = 0

    def add_vertex(self, slot: int, position) -> None:
        self.P[slot] = position
        self.VN[slot] = 0.0
        self.live[slot] = True
        self.vertex_faces.count[slot] = 0

    # -- bounds (lazy, WP-VIEW-PERF-01) ----------------------------------------------------------------

    def invalidate_bounds(self) -> None:
        self._bounds = None

    def bounds(self, on_recompute=None) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """(min, max) over the live slots, recomputed (and `on_recompute()` called) when positions changed since."""
        if self._bounds is None:
            live = self.P[self.live]
            if not len(live):
                self._bounds = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
            else:
                self._bounds = (tuple(live.min(axis=0).tolist()), tuple(live.max(axis=0).tolist()))
            if on_recompute is not None:
                on_recompute()
        return self._bounds
