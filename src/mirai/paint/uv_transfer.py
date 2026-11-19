"""UV transfer: a painted object's layers re-sampled onto changed UVs (AD-037 Phase 3; audit 2026-11-18 §5.3 item 3).

When the UVs of some faces change and the topology stays (a ZBrush return after UV Master, AD-029 §6), the paint of those
faces would no longer fit. The transfer moves it: every texel of a changed face in the **new** layout (the texel map of
the mesh with the new UVs, `TexelMap`) has a triangle and barycentric weights; the same weights over that triangle's
**old** corner UVs give the point of the old layout that held its paint. The topology is the same, so each new UV
triangle maps affinely onto its old one - no ray casting, no 3D search.

- Texels of faces whose UVs did not change are copied exactly (bit for bit).
- Texels of changed faces are read bilinearly from the old layer with premultiplied alpha (no dark fringe at a stroke's
  edge); the old layout's seam padding (`surface.seam_pad`) gives the bilinear read its border.
- A changed face that had no UVs, and old UVs outside [0, 1], give transparent texels (nothing was painted there).
- Texels the new layout does not map are transparent; the result is seam-padded where it has paint, like a stroke.

`transfer_command` makes the Undo step (`PaintLayersCommand`, every layer of the stack, also hidden ones); the caller
runs it with the mesh change (`Application.apply_goz_return`: one Undo step for the return and the moved paint).

**The base texture** (Manu 2026-11-19 after the first UV Master return: „Die Textur wirkt allerdings verschoben“): the
object's own texture is laid out for the old UVs as well - UV Master does not re-lay a ZBrush texture map. When the return
brings no new texture, `transfer_texture` writes the texture re-sampled onto the new UVs as a new PNG beside it (the old
file stays, P-4) and the object shows that one (the same Undo step). A texture the return brings is taken as it is (made
in ZBrush for the new UVs, e.g. from Polypaint).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core import FaceId, Mesh, SceneObject, VertexId

from .store import LayerSnapshot, LivePixels, PaintLayersCommand, PaintStore, occupied, tile_box, tiles_in
from .surface import pad_width, seam_pad
from .texel_map import TexelMap


#: Texels per piece of the plan's and the read's arrays (AD-037 §11.3 "Speed"): ~1-3 MiB of temporaries, inside the
#: reference PC's 6 MiB L2 (the texel map's raster went from 5.5x to ~3x the container with the same step, §10.8d).
CHUNK = 1 << 16


class _Changed:
    """`mesh` as it will be after the change: `uvs` ({face: new UVs in boundary order}) and `positions` ({vertex: new
    position}) over its topology - what `TexelMap` reads (`all_face_ids`, `face_vertices`, `face_uvs`,
    `vertex_position`), without changing the mesh."""

    def __init__(self, mesh: Mesh, uvs: dict, positions: dict | None = None) -> None:
        self._mesh, self._uvs, self._positions = mesh, uvs, positions or {}

    def all_face_ids(self):
        return self._mesh.all_face_ids()

    def face_vertices(self, fid: FaceId):
        return self._mesh.face_vertices(fid)

    def face_uvs(self, fid: FaceId):
        uvs = self._uvs.get(fid)
        return self._mesh.face_uvs(fid) if uvs is None else tuple(tuple(map(float, uv)) for uv in uvs)

    def vertex_position(self, vid: VertexId):
        position = self._positions.get(vid)
        return self._mesh.vertex_position(vid) if position is None else position


@dataclass
class TransferPlan:
    """Where every texel of the new layout takes its paint from (module docstring)."""

    width: int
    height: int
    map: TexelMap
    #: texels copied as they are (faces with unchanged UVs)
    keep: np.ndarray
    #: texels read from the old layout, and the old UV point for each (n, 2)
    move: np.ndarray
    source_uv: np.ndarray
    faces: int
    #: seconds the plan took (the texel map of the new layout and the old UV points; the status line's split)
    seconds: float = 0.0
    #: the bilinear read's four neighbours and weights per moved texel (`_taps`), the same for every layer
    taps: tuple | None = None

    @property
    def texels(self) -> int:
        return int(self.keep.size + self.move.size)


def plan(mesh: Mesh, new_uvs: dict, width: int, height: int, positions: dict | None = None) -> TransferPlan:
    """The transfer for `mesh` (old UVs, unchanged) whose faces `new_uvs` ({face: UVs in boundary order}) get new
    UVs; `positions` the vertices that move with them (the drawn triangulation follows them)."""
    import time

    started = time.perf_counter()
    changed = _Changed(mesh, new_uvs, positions)
    texel_map = TexelMap(changed, width, height, positions=changed)
    mapped = texel_map.mapped()
    slots = texel_map.slot[mapped]
    # table lookups, not sorts of 2.8 M entries (`np.isin`, `np.unique` - the reference PC's "map 2.6 s", 2026-11-19)
    tri_face = texel_map.tri_face
    changed_face = np.zeros(max(int(tri_face.max(initial=0)), max((int(f) for f in new_uvs), default=0)) + 1, bool)
    changed_face[np.fromiter((int(f) for f in new_uvs), dtype=np.int64, count=len(new_uvs))] = True
    resample = changed_face[np.maximum(tri_face[slots], 0)]
    keep, move = mapped[~resample], mapped[resample]
    move_slots = slots[resample]
    # the old corner UVs of every triangle a moved texel lies in (NaN: the face had none)
    in_use = np.zeros(int(tri_face.size), bool)
    in_use[move_slots] = True
    used = np.flatnonzero(in_use)
    old = np.full((int(texel_map.tri_face.size), 3, 2), np.nan, dtype=np.float64)
    if used.size:
        # one pass over the faces, then a sorted lookup of (face, corner) for every triangle (the reference PC:
        # "rest of the plan" 0.4-0.55 s with a Python step per triangle, 2026-11-19)
        keys, values = [], []
        stride = int(texel_map.tri_vertices[used].max()) + 1
        for f in np.unique(tri_face[used]).tolist():
            uvs = mesh.face_uvs(FaceId(f))
            if uvs is None:
                continue
            keys.extend(f * stride + int(v) for v in mesh.face_vertices(FaceId(f)))
            values.extend(uvs)
        if keys:
            keys_a = np.asarray(keys, dtype=np.int64)
            order = np.argsort(keys_a)
            keys_a, values_a = keys_a[order], np.asarray(values, dtype=np.float64)[order]
            query = tri_face[used][:, None] * stride + texel_map.tri_vertices[used]
            at = np.clip(np.searchsorted(keys_a, query), 0, keys_a.size - 1)
            found = keys_a[at] == query
            old[used] = np.where(found[..., None], values_a[at], np.nan)
    source = np.empty((move.size, 2), dtype=np.float64)
    small = np.int16 if max(width, height) < 32768 else np.int32
    taps = (np.empty(move.size, bool), *(np.empty(move.size, small) for _ in range(4)),
            np.empty(move.size, np.float32), np.empty(move.size, np.float32))

    def piece(a: int) -> None:  # cache-sized pieces (module docstring, "Speed"), disjoint: safe from threads
        b = min(a + CHUNK, move.size)
        w = texel_map.bary[move[a:b]].astype(np.float64)
        tri = old[move_slots[a:b]]
        w0 = 1.0 - w[:, 0] - w[:, 1]
        source[a:b] = tri[:, 0] * w0[:, None] + tri[:, 1] * w[:, 0:1] + tri[:, 2] * w[:, 1:2]
        for target, values in zip(taps, _taps(source[a:b], width, height)):
            target[a:b] = values

    _parallel(piece, list(range(0, move.size, CHUNK)))
    return TransferPlan(width, height, texel_map, keep, move, source, len(new_uvs), time.perf_counter() - started,
                        taps)


def _grown(rgba: np.ndarray) -> np.ndarray:
    """Where a texel's 2 x 2 bilinear neighbourhood has alpha: the alpha mask grown by one texel towards -x / -y."""
    painted = rgba[..., 3] != 0
    grown = painted.copy()
    grown[:, :-1] |= painted[:, 1:]
    grown[:-1, :] |= grown[1:, :]
    return grown


def _taps(uv: np.ndarray, width: int, height: int) -> tuple:
    """The bilinear neighbours of `uv` (n, 2): (valid (n,) bool, xa, xb, ya, yb (n,) int16 - clamped to the image -,
    fx, fy (n,) float32). NaN or outside [0, 1] is not valid. Shared by every layer of a transfer."""
    valid = np.isfinite(uv).all(axis=1) & (uv >= 0.0).all(axis=1) & (uv <= 1.0).all(axis=1)
    x = np.where(valid, uv[:, 0], 0.0) * width - 0.5
    y = np.where(valid, uv[:, 1], 0.0) * height - 0.5
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = (x - x0).astype(np.float32), (y - y0).astype(np.float32)
    small = np.int16 if max(width, height) < 32768 else np.int32
    xa, xb = np.clip(x0, 0, width - 1).astype(small), np.clip(x0 + 1, 0, width - 1).astype(small)
    ya, yb = np.clip(y0, 0, height - 1).astype(small), np.clip(y0 + 1, 0, height - 1).astype(small)
    return valid, xa, xb, ya, yb, fx, fy


def _read(rgba: np.ndarray, taps: tuple, grown: np.ndarray, opaque: bool) -> np.ndarray:
    """(n, 4) uint8: `rgba` read bilinearly at `taps` (`_taps`, one piece) - premultiplied alpha, plain for an opaque
    image; only the texels whose 2 x 2 neighbourhood has paint (`grown`) are computed, the rest is transparent."""
    valid, xa, xb, ya, yb, fx, fy = taps
    height, width = rgba.shape[:2]
    out = np.zeros((valid.size, 4), dtype=np.uint8)
    i00 = ya.astype(np.int32) * width + xa
    rows = np.flatnonzero(valid & grown.reshape(-1)[i00])
    if rows.size == 0:
        return out
    i00 = i00[rows]
    i10 = i00 + (xb[rows] - xa[rows])
    step = (yb[rows].astype(np.int32) - ya[rows]) * width
    i01, i11 = i00 + step, i10 + step
    gx, gy = fx[rows, None], fy[rows, None]
    hx, hy = 1.0 - gx, 1.0 - gy
    flat = rgba.reshape(-1).view(np.uint32)  # one gather per pixel, not per channel
    part = np.empty((rows.size, 4), dtype=np.uint8)
    taps4 = ((i00, hx * hy), (i10, gx * hy), (i01, hx * gy), (i11, gx * gy))
    if opaque:  # an opaque image (a base texture): plain bilinear, alpha stays 255
        colour = np.zeros((rows.size, 3), dtype=np.float32)
        for index, weight in taps4:
            colour += flat[index].view(np.uint8).reshape(-1, 4)[:, :3] * weight
        part[:, :3] = np.rint(colour).astype(np.uint8)
        part[:, 3] = 255
    else:  # premultiplied: no dark fringe where a stroke ends (alpha and colour·alpha in 0-255 units)
        acc = np.zeros((rows.size, 3), dtype=np.float32)
        alpha = np.zeros((rows.size, 1), dtype=np.float32)
        for index, weight in taps4:
            texel = flat[index].view(np.uint8).reshape(-1, 4)
            a = texel[:, 3:4] * weight
            acc += texel[:, :3] * a
            alpha += a
        part[:, :3] = np.rint(acc / np.where(alpha > 0, alpha, 1.0)).astype(np.uint8)
        part[:, 3] = np.rint(alpha[:, 0]).astype(np.uint8)
        part[part[:, 3] == 0] = 0
    out[rows] = part
    return out


def _bilinear(rgba: np.ndarray, uv: np.ndarray, grown: np.ndarray | None = None,
              opaque: bool | None = None) -> np.ndarray:
    """(n, 4) uint8: `rgba` (row 0 = v = 0) read at `uv` (n, 2) bilinearly (`_taps` + `_read`); NaN or outside
    [0, 1] reads transparent."""
    height, width = rgba.shape[:2]
    if grown is None:
        grown = _grown(rgba)
    if opaque is None:
        opaque = bool((rgba[..., 3] == 255).all())
    return _read(rgba, _taps(uv, width, height), grown, opaque)


def _row_boxes(grid: np.ndarray, width: int, height: int) -> list[tuple[int, int, int, int]]:
    """The true tiles of an `occupied` grid as one box per run of neighbouring tiles in a tile row (the seam padding's
    windows: the reference PC spent 0.25-0.28 s in one small window per tile, 2026-11-19)."""
    from .store import TILE

    boxes = []
    for ty in np.flatnonzero(grid.any(axis=1)).tolist():
        row = np.r_[False, grid[ty], False]
        edges = np.flatnonzero(row[1:] != row[:-1])
        for a, b in zip(edges[0::2].tolist(), edges[1::2].tolist()):
            boxes.append((a * TILE, ty * TILE, min(b * TILE, width), min((ty + 1) * TILE, height)))
    return boxes


def transfer(rgba: np.ndarray, transfer_plan: TransferPlan, keep_unmapped: bool = False) -> np.ndarray:
    """The layer `rgba` (old layout) on the new layout (module docstring). `keep_unmapped`: texels the new layout does
    not map keep their old pixels instead of becoming transparent (a base texture: opaque everywhere)."""
    p = transfer_plan
    if rgba.shape != (p.height, p.width, 4):
        raise ValueError(f"layer {rgba.shape} does not fit the plan {p.width} x {p.height}")
    out = rgba.copy() if keep_unmapped else np.zeros_like(rgba)
    old, new = rgba.reshape(-1, 4), out.reshape(-1, 4)
    new[p.keep] = old[p.keep]
    if p.move.size and rgba[..., 3].any():
        grown, opaque = _grown(rgba), bool((rgba[..., 3] == 255).all())
        taps = p.taps if p.taps is not None else _taps(p.source_uv, p.width, p.height)

        def piece(a: int) -> None:  # cache-sized pieces (module docstring, "Speed"), disjoint: safe from threads
            b = min(a + CHUNK, p.move.size)
            new[p.move[a:b]] = _read(rgba, tuple(t[a:b] for t in taps), grown, opaque)

        _parallel(piece, list(range(0, p.move.size, CHUNK)))
    boxes = _row_boxes(occupied(out), p.width, p.height)
    if boxes:
        dst, src = seam_pad(p.map, boxes, pad_width(p.width))
        if dst.size:
            new[dst] = new[src]
    return out


#: Worker threads for the pieces of a layer's read (NumPy releases the GIL in its loops; container: 3 layers 0.31 ->
#: 0.18 s with 3 threads, 2026-11-19; the reference PC's Q9550 has 4 cores). 1 = in this thread.
THREADS = 4


def _parallel(fn, items: list) -> list:
    if len(items) < 2 or THREADS < 2:
        return [fn(item) for item in items]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(min(THREADS, len(items))) as pool:
        return list(pool.map(fn, items))


def transfer_command(store: PaintStore, obj: SceneObject, mesh: Mesh, new_uvs: dict, positions: dict | None,
                     description: str, transfer_plan: TransferPlan | None = None) -> PaintLayersCommand:
    """The Undo step that puts every layer of `obj` (painted, its mesh `mesh` with the old UVs) on `new_uvs`; not applied
    yet (`redo()` applies it). `transfer_plan`: one made already at the stack's size (shared with the base)."""
    stack = obj.paint
    if transfer_plan is None or (transfer_plan.width, transfer_plan.height) != (stack.width, stack.height):
        transfer_plan = plan(mesh, new_uvs, stack.width, stack.height, positions)
    import time

    started = time.perf_counter()
    before, after = {}, {}
    names = [spec.name for spec in stack.layers]
    layers = [store.load(obj, name) for name in names]  # the store in this thread (it is not thread-safe)
    for name in names:
        # a layer equal to its file needs no copy: its Undo reads the file again (None); the moved pixels go in as they
        # are and are compressed only if the step is undone (`PaintLayersCommand` "live" pixels)
        saved = not store.is_dirty(obj, name) and store.source(obj, name) is not None
        before[name] = None if saved else store.snapshot(obj, name)
    for name, moved in zip(names, (transfer(rgba, transfer_plan) for rgba in layers)):  # each in parallel pieces
        after[name] = LivePixels(moved, store.source(obj, name), True)
    command = PaintLayersCommand(store, obj, stack, stack, before, after, description)
    command.plan = transfer_plan
    command.layer_seconds = time.perf_counter() - started  # the layers only (the plan has its own)
    return command


def transfer_texture(path: str, mesh: Mesh, new_uvs: dict, positions: dict | None,
                     plans: dict | None = None) -> tuple[str, TransferPlan]:
    """The object's texture image at `path` (laid out for `mesh`'s old UVs) re-sampled onto `new_uvs`, written as a new
    PNG beside it under its content name; returns (the new path, the plan). The file at `path` is not touched (AD-037
    P-4: the base is never written). `plans`: {(width, height): plan} to reuse (the paint's). `OSError` / `ValueError`
    when it cannot be read or written."""
    from pathlib import Path

    from .. import texture_files
    from ..iris_import import encode_png
    from .files import PNG_LEVEL, read_image

    image = np.ascontiguousarray(read_image(path)[::-1])  # row 0 = v = 0, as the texel map
    height, width = image.shape[:2]
    transfer_plan = (plans or {}).get((width, height)) or plan(mesh, new_uvs, width, height, positions)
    moved = transfer(image, transfer_plan, keep_unmapped=True)
    data = encode_png(moved[::-1], PNG_LEVEL)
    source = Path(path)
    match = texture_files._HASHED.match(source.stem)  # "Gollum_cbf9c7702d" -> "Gollum_uv_<new hash>.png"
    stem = match.group("stem") if match else source.stem
    stem = (stem[:-3] if stem.endswith("_uv") else stem) + "_uv"  # a second re-unwrap: "Gollum_uv" again
    return str(texture_files.store(data, source.parent, texture_files.hashed_name(stem, data, ".png"))), transfer_plan
