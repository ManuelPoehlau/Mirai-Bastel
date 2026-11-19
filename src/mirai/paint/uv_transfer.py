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
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core import FaceId, Mesh, SceneObject, VertexId

from .store import LayerSnapshot, PaintLayersCommand, PaintStore, occupied, tile_box, tiles_in
from .surface import pad_width, seam_pad
from .texel_map import TexelMap


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

    @property
    def texels(self) -> int:
        return int(self.keep.size + self.move.size)


def plan(mesh: Mesh, new_uvs: dict, width: int, height: int, positions: dict | None = None) -> TransferPlan:
    """The transfer for `mesh` (old UVs, unchanged) whose faces `new_uvs` ({face: UVs in boundary order}) get new
    UVs; `positions` the vertices that move with them (the drawn triangulation follows them)."""
    changed = _Changed(mesh, new_uvs, positions)
    texel_map = TexelMap(changed, width, height, positions=changed)
    mapped = texel_map.mapped()
    slots = texel_map.slot[mapped]
    ids = np.fromiter((int(f) for f in new_uvs), dtype=np.int64, count=len(new_uvs))
    resample = np.isin(texel_map.tri_face[slots], ids)
    keep, move = mapped[~resample], mapped[resample]
    move_slots = slots[resample]
    # the old corner UVs of every triangle a moved texel lies in (NaN: the face had none)
    used = np.unique(move_slots)
    old = np.full((int(texel_map.tri_face.size), 3, 2), np.nan, dtype=np.float64)
    for s in used.tolist():
        fid = FaceId(int(texel_map.tri_face[s]))
        uvs = mesh.face_uvs(fid)
        if uvs is None:
            continue
        corner = dict(zip(mesh.face_vertices(fid), uvs))
        old[s] = [corner[VertexId(int(v))] for v in texel_map.tri_vertices[s]]
    w = texel_map.bary[move].astype(np.float64)
    tri = old[move_slots]
    w0 = 1.0 - w[:, 0] - w[:, 1]
    source = tri[:, 0] * w0[:, None] + tri[:, 1] * w[:, 0:1] + tri[:, 2] * w[:, 1:2]
    return TransferPlan(width, height, texel_map, keep, move, source, len(new_uvs))


def _bilinear(rgba: np.ndarray, uv: np.ndarray) -> np.ndarray:
    """(n, 4) uint8: `rgba` (row 0 = v = 0) read at `uv` (n, 2) bilinearly in premultiplied alpha; NaN or outside
    [0, 1] reads transparent."""
    height, width = rgba.shape[:2]
    out = np.zeros((uv.shape[0], 4), dtype=np.uint8)
    valid = np.isfinite(uv).all(axis=1) & (uv >= 0.0).all(axis=1) & (uv <= 1.0).all(axis=1)
    if not valid.any():
        return out
    u, v = uv[valid, 0], uv[valid, 1]
    x, y = u * width - 0.5, v * height - 0.5
    x0, y0 = np.floor(x), np.floor(y)
    # only reads that touch paint: a texel's 2 x 2 neighbourhood has alpha where the alpha mask grown by one texel
    # towards -x / -y is set (the Gollum head at 2048²: 1.3 s for every texel of a layer, most of them empty)
    painted = rgba[..., 3] != 0
    grown = painted.copy()
    grown[:, :-1] |= painted[:, 1:]
    grown[:-1, :] |= grown[1:, :]
    xi, yi = np.clip(x0, 0, width - 1).astype(np.int64), np.clip(y0, 0, height - 1).astype(np.int64)
    touch = grown[yi, xi]
    rows = np.flatnonzero(valid)[touch]
    if rows.size == 0:
        return out
    x, y, x0, y0 = x[touch], y[touch], x0[touch], y0[touch]
    u = u[touch]
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    x0, y0 = x0.astype(np.int64), y0.astype(np.int64)
    flat = rgba.reshape(-1, 4)
    acc = np.zeros((u.size, 4), dtype=np.float64)
    for dx, dy, weight in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xs = np.clip(x0 + dx, 0, width - 1)
        ys = np.clip(y0 + dy, 0, height - 1)
        texel = flat[ys * width + xs].astype(np.float64)
        alpha = texel[:, 3:4] / 255.0
        acc[:, :3] += texel[:, :3] * alpha * weight
        acc[:, 3:4] += alpha * weight
    alpha = acc[:, 3:4]
    with np.errstate(invalid="ignore", divide="ignore"):
        colour = np.where(alpha > 0, acc[:, :3] / np.where(alpha > 0, alpha, 1.0), 0.0)
    part = np.empty((u.size, 4), dtype=np.uint8)
    part[:, :3] = np.clip(np.rint(colour), 0, 255).astype(np.uint8)
    part[:, 3] = np.clip(np.rint(alpha[:, 0] * 255.0), 0, 255).astype(np.uint8)
    part[part[:, 3] == 0] = 0
    out[rows] = part
    return out


def transfer(rgba: np.ndarray, transfer_plan: TransferPlan) -> np.ndarray:
    """The layer `rgba` (old layout) on the new layout (module docstring)."""
    p = transfer_plan
    if rgba.shape != (p.height, p.width, 4):
        raise ValueError(f"layer {rgba.shape} does not fit the plan {p.width} x {p.height}")
    out = np.zeros_like(rgba)
    old, new = rgba.reshape(-1, 4), out.reshape(-1, 4)
    new[p.keep] = old[p.keep]
    if p.move.size and rgba[..., 3].any():
        new[p.move] = _bilinear(rgba, p.source_uv)
    boxes = [tile_box(tile, p.width, p.height) for tile in tiles_in(occupied(out))]
    if boxes:
        dst, src = seam_pad(p.map, boxes, pad_width(p.width))
        if dst.size:
            new[dst] = new[src]
    return out


def transfer_command(store: PaintStore, obj: SceneObject, mesh: Mesh, new_uvs: dict, positions: dict | None,
                     description: str) -> PaintLayersCommand:
    """The Undo step that puts every layer of `obj` (painted, its mesh `mesh` with the old UVs) on `new_uvs`; not applied
    yet (`redo()` applies it)."""
    stack = obj.paint
    transfer_plan = plan(mesh, new_uvs, stack.width, stack.height, positions)
    before, after = {}, {}
    for spec in stack.layers:
        rgba = store.load(obj, spec.name)
        before[spec.name] = store.snapshot(obj, spec.name)
        after[spec.name] = LayerSnapshot.of(transfer(rgba, transfer_plan), store.source(obj, spec.name), True)
    command = PaintLayersCommand(store, obj, stack, stack, before, after, description)
    command.plan = transfer_plan
    return command
