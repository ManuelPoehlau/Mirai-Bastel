"""The evaluated surface of a stage as a position table over its base mesh's topology (audit 2026-11-10 option O1,
AD-025 / AD-028 addenda 2026-11-11). Names `PROVISIONAL`.

The morph mix (`morph_mix.MixSurface`) and the skin stage (`skinning.SkinSurface`) compute one thing per vertex: a
position. Until O1 each held its result as a complete `core.Mesh` copy of the base (`export_state` -> `Mesh.from_state`,
topology edits replayed element by element, positions written through `set_vertex_position`): per stage at 87.5k
about 0.16 GiB of Python objects and seconds to build, a second topology to keep in step, and a second journal every
position write went through. A `SurfacePositions` holds only the positions; the topology is the base's.

**What it is.** A read-only view with the part of the `Mesh` query API the stage's consumers use (the viewport's
surface and cage `RenderMesh`, `Viewport.set_cage_source` / `_follow_cage`, `Application._query_mesh` with picking,
hover, Box / Lasso / Paint, the Knife and the drag mappings, the pick cache, the hidden-set cache, the soft shading
overlay, the SubD provider as the next stage, the skin stage reading the mix):

- `vertex_position(v)` from the table (the stored tuple: bit-exact); a vertex the table does not hold raises
  `KeyError`, as `Mesh.vertex_position` does for an unknown id;
- topology, UVs, symmetry definition and regions: the base's own, read live (`face_vertices`, `face_edges`,
  `edge_faces`, `edge_vertices`, `vertex_edges`, `all_*_ids`, `is_valid_*`, `has_face_uvs`, `face_uvs`,
  `corner_uv`) - "same IDs and topology as the base" now holds by construction instead of by replay;
- no point layers (`has_point_layers()` False, `point_layer_ids()` empty), as the old stage meshes (`rest_state`);
- `watch()`: a journal of the view itself (`SurfaceWatch`, the `MeshWatch` contract: `take` / `peek` / `close`,
  `.mesh`), so every journal-driven consumer works unchanged. It names the vertices whose shown position changed
  (before-record = the old position, None = new in the table) and, when the owner follows a topology edit, the
  base's element records of that edit (vertices that went, edges, faces, face UVs). Symmetry, regions and layers are
  never recorded (no consumer of a stage surface reads them).

Nothing can be written through the view: it has no mutation method, and the base is only read. Only the stage that
owns it writes the table (the `_owner_*` methods and its own hot loops over `_index` / `_pos`).

**Consistency window.** Topology queries are live, positions are as of the owner's last update. Between a base edit
and the next stage sync the view can name a vertex it has no position for (`KeyError`) - where the old copy was
consistently stale. Every reader reads after the sync: the viewport syncs the provider before its overlays and
surfaces, `Application._query_mesh` brings the cage up to date first (`Viewport.sync_cage`), the next stage reads after
the earlier one in `ChainedSurface.sync`, and the soft shading overlay already falls back to the rest shape on
`KeyError` (`soft_selection/gl_shading.py`).

**The table** is slot-indexed: a dict `VertexId -> slot` (AD-001: an id is never an index) and per slot the position
tuple. A slot is taken when a vertex enters, freed when it leaves the base, and reused; a new position replaces the
slot's tuple. The table moves in step with the base's journal through its owner: `_owner_follow_topology` at a
topology edit, writes at every update. Why tuples per slot and not one `array('d')` of three float64 per slot (the
Core's `PackedValues` layout): in pure Python every read of a float64 array allocates three floats and a tuple; the
viewport's `RenderMesh` reads about five positions per moved vertex and frame, and that read measured ≈ 150 ns slower
than `Mesh.vertex_position` (container, 2026-11-11), while the stored tuple reads as fast as the Mesh. O3 (D1: NumPy
with its first stage) moves this storage to an n×3 float64 array together with the readers that then compute on it;
the slot map, the journal and the view contract are what it keeps.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable, Iterable
from typing import Optional

from core.mesh import MeshChange


class SurfaceWatch:
    """A persistent journal of a `SurfacePositions` (the `core.mesh.MeshWatch` contract): records until `take()` hands
    the accumulated `MeshChange` over; stops on `close()` or when garbage-collected."""

    def __init__(self, surface: "SurfacePositions") -> None:
        self.mesh = surface
        self._box = [MeshChange(keys_only=True)]
        surface._logs.append(self._box[0])
        self._finalizer = weakref.finalize(self, _detach_log, surface._logs, self._box)

    def take(self) -> MeshChange:
        box, logs = self._box, self.mesh._logs
        old, new = box[0], MeshChange(keys_only=True)
        for i, log in enumerate(logs):
            if log is old:
                logs[i] = new
                break
        else:
            return old  # closed
        box[0] = new
        return old

    def peek(self) -> MeshChange:
        return self._box[0]

    def close(self) -> None:
        self._finalizer()


def _detach_log(logs: list, box: list) -> None:
    for i, log in enumerate(logs):
        if log is box[0]:
            del logs[i]
            return


def _merge(records: dict, new: dict) -> None:
    """First record wins (the state at the consumer's last `take`)."""
    for key, record in new.items():
        if key not in records:
            records[key] = record


class SurfacePositions:
    """A stage's evaluated surface: the base's topology, positions from a slot-indexed table (module docstring).

    `position(v)` gives the starting position of every vertex of `base` (default: the base's rest position)."""

    def __init__(self, base, position: Optional[Callable] = None) -> None:
        self.base = base
        ids = base.all_vertex_ids()
        read = base.vertex_position if position is None else position
        #: VertexId -> slot (the vertices the table holds)
        self._index: dict = dict(zip(ids, range(len(ids))))
        #: slot -> position tuple (a free slot keeps its last tuple until reused)
        self._pos: list = [tuple(read(v)) for v in ids]
        self._free: list = []
        self._logs: list = []
        # The topology queries are the base's own bound methods (no wrapper call per query; the base is only read).
        self.is_valid_vertex = base.is_valid_vertex
        self.is_valid_edge = base.is_valid_edge
        self.is_valid_face = base.is_valid_face
        self.face_vertices = base.face_vertices
        self.face_edges = base.face_edges
        self.edge_faces = base.edge_faces
        self.edge_vertices = base.edge_vertices
        self.vertex_edges = base.vertex_edges
        self.all_vertex_ids = base.all_vertex_ids
        self.all_edge_ids = base.all_edge_ids
        self.all_face_ids = base.all_face_ids
        self.has_face_uvs = base.has_face_uvs
        self.face_uvs = base.face_uvs
        self.corner_uv = base.corner_uv

    # -- the read API ---------------------------------------------------------------------------------

    def vertex_position(self, vertex_id) -> tuple:
        return self._pos[self._index[vertex_id]]

    def positions(self) -> dict:
        """{VertexId: position} of every vertex the table holds (tests, probes; ascending id)."""
        pos = self._pos
        return {v: pos[s] for v, s in sorted(self._index.items())}

    @property
    def symmetry_definition(self):
        return self.base.symmetry_definition

    @property
    def face_regions(self):
        return self.base.face_regions

    def has_point_layers(self) -> bool:
        return False

    def point_layer_ids(self) -> list:
        return []

    def watch(self) -> SurfaceWatch:
        return SurfaceWatch(self)

    # -- the owner's API (the stage that evaluates this surface; nobody else writes) ------------------

    def _owner_set(self, vertex_id, position: tuple) -> None:
        """Sets a held vertex's position without a journal record (the owner's first build, before anyone watches)."""
        self._pos[self._index[vertex_id]] = position

    def _owner_add(self, vertex_id, position: tuple) -> None:
        """A vertex enters the table (a free slot, else a new one). The caller records it (before None)."""
        if self._free:
            s = self._free.pop()
            self._pos[s] = position
        else:
            s = len(self._pos)
            self._pos.append(position)
        self._index[vertex_id] = s

    def _owner_record(self, moved: dict) -> None:
        """Journal: `moved` = {VertexId: before position, None = new in the table} of one update."""
        if moved:
            for log in self._logs:
                _merge(log.vertices, moved)

    def _owner_follow_topology(self, change) -> None:
        """The base's topology changed (`change` names the elements: the base's journal, or the journal of the view the
        owner reads): drops the vertices the base no longer has and forwards the element records to every watch.
        Positions of new vertices come with the owner's next write (recorded there, before None)."""
        valid, index, pos, free = self.base.is_valid_vertex, self._index, self._pos, self._free
        gone = {}
        for v in change.vertices:
            s = index.get(v)
            if s is not None and not valid(v):
                gone[v] = pos[s]
                del index[v]
                free.append(s)
        for log in self._logs:
            _merge(log.vertices, gone)
            _merge(log.edges, change.edges)
            _merge(log.faces, change.faces)
            _merge(log.face_uvs, change.face_uvs)

    def _owner_write(self, items: Iterable) -> set:
        """Writes `(VertexId, position tuple)` pairs; only the positions that differ (or are new) change and are
        recorded. Returns those vertices. The stages inline this loop in their hot paths (`_recompute`)."""
        index, pos = self._index, self._pos
        moved = {}
        for v, p in items:
            s = index.get(v)
            if s is None:
                self._owner_add(v, p)
                moved[v] = None
                continue
            old = pos[s]
            if old != p:
                moved[v] = old
                pos[s] = p
        self._owner_record(moved)
        return set(moved)
