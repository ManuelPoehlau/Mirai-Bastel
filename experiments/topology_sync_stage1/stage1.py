"""AD-023 stage 1 as an experiment: V0 + V2 + V3 + H0, installed from the outside.

Nothing under `src/` is changed. `install(...)` replaces a few methods on `viewport.render_mesh.RenderMesh`
and `mirai.application.Application` (class attributes, so every instance - the edit mesh, object entries,
surface meshes - takes the same path); `uninstall()` puts the originals back.

- **V3 - cheaper full rebuild.** `_positions_flat` / `_normals_flat` / `_indices_flat` without the per-rebuild
  sort (`_vertex_index` is built by `enumerate`, so its insertion order is the index order) and with one
  comprehension per buffer instead of `extend` per element.
- **V0 - per-face cache.** `_sync_topology` keeps, per face, its boundary and its triangles, and per vertex the
  position of the last topology sync. A face is re-triangulated (and its normal recomputed) only when it is new,
  its boundary changed or one of its vertices moved since then; vertex normals only around those faces;
  adjacency (`vertex_to_faces`) is patched, not rebuilt; face-data rows are reused for faces whose corners kept
  their normals. Positions moved by a W drag between two topology syncs are recorded by a wrapper around
  `_sync_geometry` (a W drag does not re-triangulate, so those faces must be re-checked; AD-023 V0 "cache key").
  The GPU buffers are still rebuilt whole (that is V1, not stage 1).
- **V2 - no buffer rebuild when the structure is unchanged.** If vertex list, face list, every boundary and every
  triangulation equal the last sync, the topology sync only patches the moved vertices, their normals and face rows
  (the `_sync_geometry` path) instead of recreating the buffers. This turns Extrude's release rebuild into a patch
  (AD-023 V2) and, as a side effect, the Undo/Redo of a positions-only step (W move; AD-023 U "cheaper win").
  Above `V2_PATCH_LIMIT` moved vertices it rebuilds whole (per-element `store.update` is slower than one upload).
- **H0 - no after-snapshot on the `Application._mesh_transaction` path** (Delete, Dissolve, Connect, Split,
  `apply_mesh_change` ...). "Changed?" comes from the element counts; only when they are equal does it fall back to
  the full `export_state()` comparison of today, so the signal is exact. The after-state is exported on the first
  Undo (the mesh is then in exactly that state, the stack is linear), so **Undo pays that export** (AD-023 H0).
  Extrude and Knife build their own `MeshStateCommand`s and are not covered.

Equivalence with the unchanged code is tested headless in `tests/` (buffers, normals within 1e-9: the vertex
normal is a sum over a `set` of faces, whose iteration order can differ between a patched and a fresh set).
"""

from __future__ import annotations

from dataclasses import dataclass, field

ALL = ("V0", "V2", "V3", "H0")
#: V2: above this many moved vertices one whole upload is cheaper than per-element patches (PROVISIONAL).
V2_PATCH_LIMIT = 2000

_originals: dict[tuple[type, str], object] = {}
_active: frozenset[str] = frozenset()


def parse(spec: str) -> frozenset[str]:
    """`"V0,V2,V3,H0"`, `"all"` or `"none"` -> the set of switches."""
    spec = spec.strip()
    if spec.lower() == "all":
        return frozenset(ALL)
    if spec.lower() in ("none", "off", ""):
        return frozenset()
    parts = {p.strip().upper() for p in spec.split(",") if p.strip()}
    unknown = parts - set(ALL)
    if unknown:
        raise ValueError(f"unknown stage-1 switch(es): {sorted(unknown)}; known: {', '.join(ALL)}")
    if "V2" in parts and "V0" not in parts:
        raise ValueError("V2 needs V0 (it compares against the V0 cache)")
    return frozenset(parts)


def active() -> frozenset[str]:
    return _active


@dataclass
class Stats:
    """Counters over all RenderMesh instances since `install()`; read by the probe."""

    topology_syncs: int = 0
    full_buffer_rebuilds: int = 0
    patch_syncs: int = 0
    faces_retriangulated: int = 0
    faces_reused: int = 0
    lazy_after_exports: int = 0
    counts_decided_changed: int = 0
    full_compare_fallbacks: int = 0

    def text(self) -> str:
        return (
            f"topology syncs {self.topology_syncs} (full buffer rebuilds {self.full_buffer_rebuilds}, "
            f"V2 patch syncs {self.patch_syncs}); faces re-triangulated {self.faces_retriangulated}, "
            f"reused {self.faces_reused}; H0: changed by counts {self.counts_decided_changed}, "
            f"full-compare fallbacks {self.full_compare_fallbacks}, lazy after-exports at Undo {self.lazy_after_exports}"
        )


STATS = Stats()


# -- V0 cache -------------------------------------------------------------------------------------


@dataclass
class _Cache:
    vids: list = field(default_factory=list)
    fids: list = field(default_factory=list)
    positions: dict = field(default_factory=dict)  # VertexId -> position at the last topology sync
    faces: dict = field(default_factory=dict)  # FaceId -> (boundary tuple, triangles)
    rows: dict = field(default_factory=dict)  # FaceId -> face-data row (list of floats)
    pending: set = field(default_factory=set)  # vertices a geometry sync moved since then


def _cache(rm) -> _Cache | None:
    return rm.__dict__.get("_stage1_cache")


def _sync_topology_v0(self) -> None:
    self.stats.count("topology_updates")
    STATS.topology_syncs += 1
    if _update_v0(self):
        self.stats.count("structural_rebuilds")
        self.stats.count("mesh_rebuilds")


def _update_v0(self) -> bool:
    """The V0 (+ V2) topology update; True when the buffers were rebuilt whole."""
    from viewport.derived import _normalize, face_normal, triangulate_face

    cache = _cache(self)
    first = cache is None
    if first:
        cache = self.__dict__["_stage1_cache"] = _Cache()
        derived = self.derived
        derived.vertex_to_faces, derived.face_normals, derived.vertex_normals = {}, {}, {}
    mesh, derived = self.mesh, self.derived
    v2f, fnormals, vnormals = derived.vertex_to_faces, derived.face_normals, derived.vertex_normals

    vids = mesh.all_vertex_ids()
    position = mesh.vertex_position
    positions = {v: position(v) for v in vids}
    old_positions = cache.positions
    moved = {v for v, p in positions.items() if old_positions.get(v) != p}
    if cache.pending:
        moved |= cache.pending & positions.keys()
    removed_vertices = old_positions.keys() - positions.keys()

    fids = mesh.all_face_ids()
    old_faces = cache.faces
    new_faces: dict = {}
    dirty_vertices: set = set(moved)
    changed_faces: set = set()
    structure_same = not first and vids == cache.vids and fids == cache.fids
    face_vertices = mesh.face_vertices
    reused = 0
    for f in fids:
        b = tuple(face_vertices(f))
        entry = old_faces.get(f)
        same_boundary = entry is not None and entry[0] == b
        if same_boundary and (not moved or moved.isdisjoint(b)):
            new_faces[f] = entry
            reused += 1
            continue
        if not same_boundary:
            structure_same = False
            if entry is not None:
                for v in entry[0]:
                    faces_of = v2f.get(v)
                    if faces_of is not None:
                        faces_of.discard(f)
                dirty_vertices.update(entry[0])
            for v in b:
                faces_of = v2f.get(v)
                if faces_of is None:
                    v2f[v] = {f}
                else:
                    faces_of.add(f)
        boundary = list(b)
        tris = triangulate_face(boundary, positions)
        if same_boundary and tris != entry[1]:
            structure_same = False
        fnormals[f] = face_normal(positions, boundary)
        new_faces[f] = (b, tris)
        changed_faces.add(f)
        dirty_vertices.update(b)
    if old_faces:
        for f in old_faces.keys() - new_faces.keys():
            structure_same = False
            old_b = old_faces[f][0]
            for v in old_b:
                faces_of = v2f.get(v)
                if faces_of is not None:
                    faces_of.discard(f)
            fnormals.pop(f, None)
            cache.rows.pop(f, None)
            dirty_vertices.update(old_b)
    for v in removed_vertices:
        v2f.pop(v, None)
        vnormals.pop(v, None)
    STATS.faces_retriangulated += len(changed_faces)
    STATS.faces_reused += reused

    # Vertex normals around everything that changed; a vertex left without faces gets (0,0,0) and no
    # adjacency entry, as `full_recompute` gives it.
    rows = cache.rows
    for v in dirty_vertices:
        if v not in positions:
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
            for f in faces_of:
                rows.pop(f, None)
        vnormals[v] = _normalize((sx, sy, sz))
    for f in changed_faces:
        rows.pop(f, None)
    derived.invalidate_bounds(mesh)

    cache.vids, cache.fids, cache.faces, cache.positions = vids, fids, new_faces, positions
    cache.pending = set()

    if structure_same and "V2" in _active and len(moved) <= V2_PATCH_LIMIT:
        _patch_moved(self, moved, dirty_vertices)
        STATS.patch_syncs += 1
        return False

    self._vertex_index = {v: i for i, v in enumerate(vids)}
    triangles: list = []
    face_row: dict = {}
    triangle_face_rows: list = []
    for f in fids:
        row = face_row[f] = len(face_row)
        tris = new_faces[f][1]
        triangles.extend(tris)
        triangle_face_rows.extend([row] * len(tris))
    self._triangle_indices = triangles
    self._face_row = face_row
    self._triangle_face_rows = triangle_face_rows
    self._rebuild_resources()
    STATS.full_buffer_rebuilds += 1
    return True


def _patch_moved(self, moved: set, dirty_vertices: set) -> None:
    """V2: the index layout is unchanged; patch what moved, as `_sync_geometry` does."""
    from viewport.render_mesh import COMPONENTS_PER_VERTEX, FACE_DATA, FACE_ROW_FLOATS, FLOAT_BYTES

    nbytes = COMPONENTS_PER_VERTEX * FLOAT_BYTES
    index, position, normals = self._vertex_index, self.mesh.vertex_position, self.derived.vertex_normals
    for v in moved:
        self.store.update("positions", index[v] * COMPONENTS_PER_VERTEX, list(position(v)), nbytes)
    faces: set = set()
    v2f = self.derived.vertex_to_faces
    for v in dirty_vertices:
        if v in index:
            self.store.update("normals", index[v] * COMPONENTS_PER_VERTEX, list(normals[v]), nbytes)
            faces.update(v2f.get(v, ()))
    for f in faces:
        self.store.update(FACE_DATA, self._face_row[f] * FACE_ROW_FLOATS, self._face_row_data(f),
                          FACE_ROW_FLOATS * FLOAT_BYTES)
    if self.overlay is not None:
        # A full rebuild re-puts the highlight flags; keep that (selection restores ride on undo).
        flags = self.overlay.build_highlight_flags(self.mesh)
        self.store.update("highlight_flags", 0, flags, len(flags) * FLOAT_BYTES)


def _sync_geometry_v0(self) -> None:
    cache = _cache(self)
    if cache is not None and self.dirty.modified_vertices:
        cache.pending |= self.dirty.modified_vertices
    _originals[(_render_mesh_cls(), "_sync_geometry")](self)


def _build_v0(self) -> None:
    """`build()` through the V0 path with an empty cache (= everything new), counted as today."""
    self.__dict__.pop("_stage1_cache", None)
    _update_v0(self)
    self.stats.count("mesh_rebuilds")
    self.stats.count("structural_rebuilds")


def _face_data_flat_v0(self) -> list[float]:
    cache = _cache(self)
    rows = cache.rows if cache is not None else {}
    flat: list[float] = []
    for face_id in self._face_row:
        row = rows.get(face_id)
        if row is None:
            row = rows[face_id] = self._face_row_data(face_id)
        flat += row
    return flat


# -- V3 flattening ----------------------------------------------------------------------------------


def _positions_flat_v3(self) -> list[float]:
    position = self.mesh.vertex_position
    return [c for v in self._vertex_index for c in position(v)]


def _normals_flat_v3(self) -> list[float]:
    normals = self.derived.vertex_normals
    return [c for v in self._vertex_index for c in normals[v]]


def _indices_flat_v3(self) -> list[float]:
    index = self._vertex_index
    return [float(index[v]) for tri in self._triangle_indices for v in tri]


# -- H0 ----------------------------------------------------------------------------------------------


class LazyAfterMeshStateCommand:
    """`MeshStateCommand` whose after-state is exported on the first Undo (AD-023 H0)."""

    def __init__(self, mesh, before_state: dict, description: str) -> None:
        self.mesh = mesh
        self.before_state = before_state
        self.after_state: dict | None = None
        self.description = description

    def undo(self) -> None:
        if self.after_state is None:
            self.after_state = self.mesh.export_state()
            STATS.lazy_after_exports += 1
        self.mesh.load_state(self.before_state)

    def redo(self) -> None:
        self.mesh.load_state(self.after_state)


def _counts(mesh) -> tuple[int, int, int]:
    return len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())


def _mesh_transaction_h0(self, description, mutate, *, on_applied=None, moved_of=None):
    """`Application._mesh_transaction` with the after-snapshot deferred; otherwise the same steps."""
    from core.operations import MeshStateCommand
    from mirai.application import _MeshTransaction

    mesh = self.scene.mesh
    selection_before = self._selection_snapshot()
    before = mesh.export_state()
    counts_before = _counts(mesh)
    try:
        result = mutate(mesh)
    except BaseException:
        mesh.load_state(before)
        raise
    if _counts(mesh) != counts_before:
        STATS.counts_decided_changed += 1
        command = LazyAfterMeshStateCommand(mesh, before, description)
    else:
        STATS.full_compare_fallbacks += 1
        after = mesh.export_state()
        if after == before:
            return _MeshTransaction(False, result)
        command = MeshStateCommand(mesh=mesh, before_state=before, after_state=after, description=description)
    self.history.push(command)
    if on_applied is not None:
        on_applied(result)
    self._record_selection_history(selection_before)
    moved = moved_of(result) if moved_of is not None else None
    if moved is None:
        self._notify_topology_changed()
    else:
        self._pick_cache.invalidate()
        if self.viewport is not None:
            self.viewport.on_vertices_moved(set(moved))
        self._soft_preview_refresh()
        self._refresh_hover()
    return _MeshTransaction(True, result)


# -- install / uninstall -----------------------------------------------------------------------------


def _render_mesh_cls():
    from viewport.render_mesh import RenderMesh

    return RenderMesh


def _replace(cls: type, name: str, fn) -> None:
    _originals.setdefault((cls, name), cls.__dict__[name])
    setattr(cls, name, fn)


def install(switches) -> frozenset[str]:
    """Installs the given switches (an iterable or a `parse` string); returns them."""
    global _active
    if isinstance(switches, str):
        switches = parse(switches)
    switches = frozenset(switches)
    uninstall()
    rm = _render_mesh_cls()
    if "V3" in switches:
        _replace(rm, "_positions_flat", _positions_flat_v3)
        _replace(rm, "_normals_flat", _normals_flat_v3)
        _replace(rm, "_indices_flat", _indices_flat_v3)
    if "V0" in switches:
        _replace(rm, "_sync_topology", _sync_topology_v0)
        _replace(rm, "_sync_geometry", _sync_geometry_v0)
        _replace(rm, "build", _build_v0)
        _replace(rm, "_face_data_flat", _face_data_flat_v0)
    if "H0" in switches:
        from mirai.application import Application

        _replace(Application, "_mesh_transaction", _mesh_transaction_h0)
    _active = switches
    return switches


def uninstall() -> None:
    global _active
    for (cls, name), original in _originals.items():
        setattr(cls, name, original)
    _originals.clear()
    _active = frozenset()


def reset_stats() -> None:
    global STATS
    for name in Stats.__dataclass_fields__:
        setattr(STATS, name, 0)
