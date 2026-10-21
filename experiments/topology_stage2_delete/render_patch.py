"""AD-023 V1 for Delete and its Undo / Redo: patch the `RenderMesh` buffers from the delta's touched set.

Built on stage 1 (`topology_sync_stage1.stage1`, V0 cache): a full topology sync still goes through V0, and a
V1 patch keeps the V0 cache in step, so a later V0 sync diffs against what the buffers hold.

Layout rule ("slots"): between two full rebuilds every vertex keeps its buffer index and every face its
triangle range and face row, also when it dies.

- A deleted face's triangles become degenerate (`(a, a, a)`): no fragment, but they keep their place, so
  `gl_PrimitiveID` and the triangle -> face-row map (`triangle_faces`) stay valid for every live triangle
  (AD-022 B2 reads the same mapping; AD-023 §5 "one contract"). `triangle_faces` is not touched.
- A deleted vertex keeps its slot; its position is overwritten with `DEAD_POSITION`, which no live triangle
  references and which the GPU point pass clips (`gpu_pick.py`).
- Undo of the Delete revives the same slots (same IDs, same boundaries, the same triangle count). An element
  without a slot (it died before the last full rebuild) makes the patch fall back to the V0 full sync, which
  compacts the layout. Nothing here grows the buffers: spare capacity for new elements (Extrude, Knife) is not
  part of this Delete-only prototype.

Index data is patched through `ResourceStore.update("indices", ...)`; `GLRenderStore` refuses that today
("index buffer only ever changes via a structural rebuild"), so `_patch_attribute_v1` writes the range into the
VertexList's index buffer (the AD-023 V1 "ResourceStore patch contract for index data", AD-018 addendum).
`highlight_flags` follow the slot layout (`_highlight_flags`), as the buffer they belong to.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

from topology_sync_stage1 import stage1

#: Position written into a dead vertex slot. Finite in float32; the GPU point pass clips it.
DEAD_COORD = 1.0e19
DEAD_POSITION = [DEAD_COORD, DEAD_COORD, DEAD_COORD]


@dataclass
class Stats:
    v1_patches: int = 0
    v1_fallbacks: int = 0
    faces_killed: int = 0
    faces_revived: int = 0

    def text(self) -> str:
        return (f"V1 patch syncs {self.v1_patches}, fallbacks to a full sync {self.v1_fallbacks}; "
                f"faces killed {self.faces_killed}, revived {self.faces_revived}")


STATS = Stats()


@dataclass
class _Slots:
    dead_faces: set = field(default_factory=set)
    dead_vertices: set = field(default_factory=set)
    pending: list = field(default_factory=list)  # [(MeshDelta, forward)] since the last sync
    layout_rev: int = 0  # +1 per full rebuild (slots renumbered)
    content_rev: int = 0  # +1 per change of any buffer content (GPU pick cache key)
    _row_face: list | None = None
    _slot_vertex: list | None = None


def slots(rm) -> _Slots:
    st = rm.__dict__.get("_stage2_slots")
    if st is None:
        st = rm.__dict__["_stage2_slots"] = _Slots()
    return st


def row_face(rm) -> list:
    """Face row -> FaceId (a dead face keeps its row; its triangles draw nothing)."""
    st = slots(rm)
    if st._row_face is None:
        table = [None] * len(rm._face_row)
        for f, row in rm._face_row.items():
            table[row] = f
        st._row_face = table
    return st._row_face


def slot_vertex(rm) -> list:
    st = slots(rm)
    if st._slot_vertex is None:
        table = [None] * len(rm._vertex_index)
        for v, i in rm._vertex_index.items():
            table[i] = v
        st._slot_vertex = table
    return st._slot_vertex


# -- RenderMesh / Viewport entry points ------------------------------------------------------------------


def mark_topology_delta(self, delta, forward: bool) -> None:
    """RenderMesh: the mesh changed by `delta` (applied forward = Delete / Redo, backward = Undo)."""
    slots(self).pending.append((delta, forward))


def on_topology_delta(self, delta, forward: bool) -> None:
    """Viewport: as `on_topology_changed`, with the touched set for the edit mesh's buffers. A full rebuild
    re-puts the highlight flags; the patch does not, so the selection (restored by an Undo) is marked too."""
    self.render_mesh.mark_topology_delta(delta, forward)
    self.render_mesh.mark_selection_dirty()
    self._selection_overlays_dirty = True
    self._edges_dirty = True


def _sync_v1(self) -> None:
    st = slots(self)
    pending, st.pending = st.pending, []
    if self.dirty.topology or self.dirty.geometry:
        st.content_rev += 1
    if pending and not self.dirty.topology:
        if _apply(self, pending):
            STATS.v1_patches += 1
            st.content_rev += 1
        else:
            STATS.v1_fallbacks += 1
            self.mark_topology_dirty()
    _originals["sync"](self)


def _rebuild_resources_v1(self) -> None:
    st = slots(self)
    st.dead_faces.clear()
    st.dead_vertices.clear()
    st.layout_rev += 1
    st.content_rev += 1
    st._row_face = st._slot_vertex = None
    _originals["_rebuild_resources"](self)


def _highlight_flags(self) -> list[float]:
    """Highlight flags in buffer (slot) order; the overlay builds them in mesh order."""
    flags = self.overlay.build_highlight_flags(self.mesh)
    st = slots(self)
    if not st.dead_vertices and len(self._vertex_index) == len(flags):
        return flags
    out = [0.0] * len(self._vertex_index)
    index = self._vertex_index
    for v, flag in zip(self.mesh.all_vertex_ids(), flags):
        if flag:
            out[index[v]] = flag
    return out


def _sync_selection_v1(self) -> None:
    if self.overlay is None:
        return
    self.stats.count("selection_updates")
    flags = _highlight_flags(self)
    self.store.update("highlight_flags", 0, flags, len(flags) * 4)
    self.stats.count("partial_updates")


def _patch_moved_v1(rm, moved, dirty_vertices) -> None:
    """stage 1's V2 patch, with the highlight flags in slot order."""
    _originals["_patch_moved"](rm, moved, dirty_vertices)
    if rm.overlay is not None and slots(rm).dead_vertices:
        flags = _highlight_flags(rm)
        rm.store.update("highlight_flags", 0, flags, len(flags) * 4)


# -- the patch ----------------------------------------------------------------------------------------------


def _triangle_range(rm, row: int) -> tuple[int, int]:
    """(first triangle, count) of face row `row`: `_triangle_face_rows` is ascending (full rebuild order)."""
    rows = rm._triangle_face_rows
    t0 = bisect.bisect_left(rows, row)
    return t0, bisect.bisect_right(rows, row, lo=t0) - t0


def _apply(rm, pending) -> bool:
    """Patches the buffers for the net effect of `pending`; False = fall back to the full (V0) sync."""
    from viewport.derived import _normalize, face_normal, triangulate_face
    from viewport.render_mesh import COMPONENTS_PER_VERTEX, FACE_DATA, FACE_ROW_FLOATS, FLOAT_BYTES

    cache = stage1._cache(rm)
    if cache is None:
        return False
    st = slots(rm)
    mesh, derived, store = rm.mesh, rm.derived, rm.store
    v2f, fnormals, vnormals = derived.vertex_to_faces, derived.face_normals, derived.vertex_normals
    index, face_row = rm._vertex_index, rm._face_row

    faces_touched: set = set()
    vertices_touched: set = set()
    for delta, _forward in pending:
        faces_touched.update(delta.faces)
        vertices_touched.update(delta.vertices)

    kill_f, revive_f, kill_v, revive_v = [], [], [], []
    for f in faces_touched:
        alive_now = mesh.is_valid_face(f)
        in_buffers = f in face_row and f not in st.dead_faces
        if alive_now and not in_buffers:
            if f not in face_row:
                return False
            revive_f.append(f)
        elif not alive_now and in_buffers:
            kill_f.append(f)
    for v in vertices_touched:
        alive_now = mesh.is_valid_vertex(v)
        in_buffers = v in index and v not in st.dead_vertices
        if alive_now and not in_buffers:
            if v not in index:
                return False
            revive_v.append(v)
        elif not alive_now and in_buffers:
            kill_v.append(v)

    # Check every revival before changing anything: the slot must take the face's triangulation.
    position = mesh.vertex_position
    revived: dict = {}
    for f in revive_f:
        boundary = mesh.face_vertices(f)
        if any(v not in index for v in boundary):
            return False
        positions = {v: position(v) for v in boundary}
        tris = triangulate_face(boundary, positions)
        t0, n = _triangle_range(rm, face_row[f])
        if len(tris) != n:
            return False
        revived[f] = (boundary, positions, tris, t0)

    nbytes3 = COMPONENTS_PER_VERTEX * FLOAT_BYTES
    dirty: set = set()
    tri_list = rm._triangle_indices

    for f in kill_f:
        boundary = cache.faces[f][0]
        for v in boundary:
            faces_of = v2f.get(v)
            if faces_of is not None:
                faces_of.discard(f)
        fnormals.pop(f, None)
        cache.faces.pop(f, None)
        cache.rows.pop(f, None)
        dirty.update(boundary)
        t0, n = _triangle_range(rm, face_row[f])
        a = boundary[0]
        store.update("indices", t0 * 3, [float(index[a])] * (3 * n), 3 * n * FLOAT_BYTES)
        for t in range(t0, t0 + n):
            tri_list[t] = (a, a, a)
        st.dead_faces.add(f)
        STATS.faces_killed += 1

    for v in kill_v:
        v2f.pop(v, None)
        vnormals.pop(v, None)
        cache.positions.pop(v, None)
        cache.pending.discard(v)
        store.update("positions", index[v] * COMPONENTS_PER_VERTEX, DEAD_POSITION, nbytes3)
        st.dead_vertices.add(v)
    for v in revive_v:
        p = position(v)
        cache.positions[v] = p
        store.update("positions", index[v] * COMPONENTS_PER_VERTEX, list(p), nbytes3)
        st.dead_vertices.discard(v)

    for f, (boundary, positions, tris, t0) in revived.items():
        for v in boundary:
            faces_of = v2f.get(v)
            if faces_of is None:
                v2f[v] = {f}
            else:
                faces_of.add(f)
        fnormals[f] = face_normal(positions, boundary)
        cache.faces[f] = (tuple(boundary), tris)
        cache.rows.pop(f, None)
        flat = [float(index[v]) for tri in tris for v in tri]
        store.update("indices", t0 * 3, flat, len(flat) * FLOAT_BYTES)
        tri_list[t0:t0 + len(tris)] = tris
        st.dead_faces.discard(f)
        dirty.update(boundary)
        STATS.faces_revived += 1

    # Vertex normals around everything that changed (as V0 / `full_recompute`): a vertex left without faces
    # gets (0, 0, 0) and no adjacency entry.
    rows_dirty: set = set(revived)
    for v in dirty:
        if not mesh.is_valid_vertex(v):
            continue
        faces_of = v2f.get(v)
        if faces_of is not None and not faces_of:
            del v2f[v]
            faces_of = None
        sx = sy = sz = 0.0
        if faces_of:
            for f in faces_of:
                n = fnormals[f]
                sx += n[0]
                sy += n[1]
                sz += n[2]
            rows_dirty.update(faces_of)
        normal = vnormals[v] = _normalize((sx, sy, sz))
        store.update("normals", index[v] * COMPONENTS_PER_VERTEX, list(normal), nbytes3)
    for f in rows_dirty:
        row = cache.rows[f] = rm._face_row_data(f)
        store.update(FACE_DATA, face_row[f] * FACE_ROW_FLOATS, row, FACE_ROW_FLOATS * FLOAT_BYTES)
    derived.invalidate_bounds(mesh)
    cache.vids, cache.fids = mesh.all_vertex_ids(), mesh.all_face_ids()
    rm.stats.count("topology_updates")
    rm.stats.count("v1_patches")
    return True


# -- GLRenderStore: index data patch ------------------------------------------------------------------------


def _patch_attribute_v1(self, group, name, data, offset, count) -> None:
    _attributes, index_name = self._groups[group]
    if name != index_name:
        _originals["_patch_attribute"](self, group, name, data, offset, count)
        return
    vlist = self._vertex_lists.get(group)
    if vlist is None:
        return
    start = vlist.start
    vlist.domain.index_buffer.set_region(
        vlist.index_start + offset, count, [int(x) + start for x in data[offset:offset + count]])


# -- install / uninstall ------------------------------------------------------------------------------------

_originals: dict = {}
_installed: list = []


def install() -> None:
    from viewport.gl_render_store import GLRenderStore
    from viewport.render_mesh import RenderMesh
    from viewport.viewport import Viewport

    uninstall()
    for cls, name, fn in (
        (RenderMesh, "sync", _sync_v1),
        (RenderMesh, "_rebuild_resources", _rebuild_resources_v1),
        (RenderMesh, "_sync_selection", _sync_selection_v1),
        (RenderMesh, "mark_topology_delta", mark_topology_delta),
        (Viewport, "on_topology_delta", on_topology_delta),
        (GLRenderStore, "_patch_attribute", _patch_attribute_v1),
    ):
        if name in cls.__dict__:
            _originals[name] = cls.__dict__[name]
        _installed.append((cls, name))
        setattr(cls, name, fn)
    _originals["_patch_moved"] = stage1._patch_moved
    stage1._patch_moved = _patch_moved_v1


def uninstall() -> None:
    for cls, name in _installed:
        if name in _originals:
            setattr(cls, name, _originals[name])
        else:
            delattr(cls, name)
    _installed.clear()
    if "_patch_moved" in _originals:
        stage1._patch_moved = _originals["_patch_moved"]
    _originals.clear()


def reset_stats() -> None:
    for name in Stats.__dataclass_fields__:
        setattr(STATS, name, 0)
