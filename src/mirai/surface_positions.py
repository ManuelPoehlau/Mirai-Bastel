"""The evaluated surface of a stage as a position table over its base mesh's topology (audit 2026-11-10 option O1,
AD-025 / AD-028 addenda 2026-11-11; the table on arrays since O3 stage 2, AD-032 §11, 2026-11-13). Names
`PROVISIONAL`.

The morph mix (`morph_mix.MixSurface`) and the skin stage (`skinning.SkinSurface`) compute one thing per vertex: a
position. Until O1 each held its result as a complete `core.Mesh` copy of the base (`export_state` -> `Mesh.from_state`,
topology edits replayed element by element, positions written through `set_vertex_position`): per stage at 87.5k
about 0.16 GiB of Python objects and seconds to build, a second topology to keep in step, and a second journal every
position write went through. A `SurfacePositions` holds only the positions; the topology is the base's.

**What it is.** A read-only view with the part of the `Mesh` query API the stage's consumers use (the viewport's
surface and cage `RenderMesh`, `Viewport.set_cage_source` / `_follow_cage`, `Application._query_mesh` with picking,
hover, Box / Lasso / Paint, the Knife and the drag mappings, the pick cache, the hidden-set cache, the soft shading
overlay, the SubD provider as the next stage, the skin stage reading the mix):

- `vertex_position(v)` from the table (three float64 of the array: bit-exact); a vertex the table does not hold raises
  `KeyError`, as `Mesh.vertex_position` does for an unknown id;
- topology, UVs, symmetry definition and regions: the base's own, read live (`face_vertices`, `face_edges`,
  `edge_faces`, `edge_vertices`, `vertex_edges`, `all_*_ids`, `is_valid_*`, `has_face_uvs`, `face_uvs`,
  `corner_uv`) - "same IDs and topology as the base" holds by construction instead of by replay;
- no point layers (`has_point_layers()` False, `point_layer_ids()` empty), as the old stage meshes (`rest_state`);
- `watch()`: a journal of the view itself (`SurfaceWatch`, the `MeshWatch` contract: `take` / `peek` / `close`,
  `.mesh`), so every journal-driven consumer works unchanged. Its change (`SurfaceChange`) names the vertices whose
  shown position changed (before-record = the old position, None = new in the table) and, when the owner follows a
  topology edit, the base's element records of that edit (vertices that went, edges, faces, face UVs). Symmetry,
  regions and layers are never recorded (no consumer of a stage surface reads them);
- the **array hand-over** (AD-032 §11.3, duck-typed for the viewport, which imports nothing from here):
  `position_array()` (the table, rows = slots, read-only), `table_slots(vertex_ids)` and, on a taken change,
  `slot_moves()` - the moved slots as an array when the change holds nothing but position writes.

Nothing can be written through the view: it has no mutation method, and the base is only read. Only the stage that
owns it writes the table (the `_owner_*` methods).

**Consistency window.** Topology queries are live, positions are as of the owner's last update. Between a base edit
and the next stage sync the view can name a vertex it has no position for (`KeyError`) - where the old copy was
consistently stale. Every reader reads after the sync: the viewport syncs the provider before its overlays and
surfaces, `Application._query_mesh` brings the cage up to date first (`Viewport.sync_cage`), the next stage reads after
the earlier one in `ChainedSurface.sync`, and the soft shading overlay already falls back to the rest shape on
`KeyError` (`soft_selection/gl_shading.py`).

**The table** (O3 stage 2): an n x 3 float64 array `P`, rows = slots; a dict `VertexId -> slot` (AD-001: an id is never
an index) and the inverse list slot -> `VertexId` (None = free). A slot is taken when a vertex enters, freed when it
leaves the base and reused; a free slot keeps its last row. The capacity doubles when it runs out (a new array: nobody
keeps the array object across an owner update). A table built with `layout=` another table over the same base
**mirrors** that table's slots (the skin stage over the mix, AD-032 §11.2): it starts as a copy of its layout, frees
what that table freed and puts a new vertex on that table's slot - so both read and write the same rows for a vertex.
Until O3 stage 2 the table was a list of tuples (O1: a float64 read in pure Python cost more than the stage saved);
since the stages and the viewport compute on the array, per-vertex reads are what is left of the per-vertex readers.

**The journal** (AD-032 §11.1). A position write is recorded once per update as a *slot chunk* shared by every watch -
the slots that changed, their rows before the write and the slot -> `VertexId` list in force - instead of one dict entry
per vertex and watch. What changes the slot mapping (a vertex new in the table, a vertex gone) is recorded by id. A
mapping change first copies the slot list if a chunk refers to it (copy-on-write), so a chunk always resolves to the
vertices it was written for. `SurfaceChange.vertices` builds the dict of the `MeshChange` contract from both, in their
order, first record wins - the records the tuple table wrote; `slot_moves()` skips the dict when there is nothing but
position records under the current mapping.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable, Iterable, Set
from typing import Optional

from core.mesh import MeshChange
from viewport.packed_geometry import np  # NumPy behind its pinned-version check (AD-032 §2)

_INDEX = np.intp
#: `MeshChange`'s "not recorded" value of symmetry / regions / layer meta (a stage surface never records them).
_UNSET = MeshChange().symmetry
#: A watch that holds more chunk rows than this many times the table's capacity merges them (bounded memory for a
#: watch that is not taken for a while, e.g. the picking cache during a drag); beyond `_MAX_ENTRIES` entries it folds
#: everything into its dict.
_COMPACT_ROWS = 1
_MAX_ENTRIES = 64
_EMPTY_SLOTS = np.zeros(0, dtype=_INDEX)
_EMPTY_SLOTS.flags.writeable = False


def _frozen(array):
    array.flags.writeable = False
    return array


class _Chunk:
    """One position write of the owner: `slots` (ascending, distinct), their rows before the write, and the slot ->
    `VertexId` list in force (never mutated once a chunk refers to it)."""

    __slots__ = ("slots", "before", "slot_vertex")

    def __init__(self, slots, before, slot_vertex: list) -> None:
        self.slots, self.before, self.slot_vertex = slots, before, slot_vertex


class SurfaceChange:
    """What a `SurfaceWatch` accumulated: the `core.mesh.MeshChange` interface (duck-typed) over position chunks and
    records by id (module docstring, AD-032 §11.1)."""

    keys_only = True
    symmetry = _UNSET
    regions = _UNSET
    layer_meta = _UNSET
    symmetry_touched = False
    regions_touched = False
    layers_touched = False

    def __init__(self, table: "SurfacePositions") -> None:
        self.table = table
        self.edges: dict = {}
        self.faces: dict = {}
        self.face_uvs: dict = {}
        self.layer_values: dict = {}
        self.layer_whole: dict = {}
        #: in recording order: a dict {VertexId: before} (records by id) or a `_Chunk`
        self._entries: list = []
        self._rows = 0

    # -- the MeshChange interface ---------------------------------------------------------------------

    @property
    def vertices(self) -> dict:
        """{VertexId: before}, None = new in the table: every record in order, first record wins."""
        entries = self._entries
        if len(entries) == 1 and type(entries[0]) is dict:
            return entries[0]
        out: dict = {}
        for entry in entries:
            if type(entry) is dict:
                for v, before in entry.items():
                    if v not in out:
                        out[v] = before
            else:
                slot_vertex = entry.slot_vertex
                for s, before in zip(entry.slots.tolist(), entry.before.tolist()):
                    v = slot_vertex[s]
                    if v not in out:
                        out[v] = tuple(before)
        self._entries = [out] if out else []
        self._rows = 0
        return out

    def is_empty(self) -> bool:
        return not (self._entries or self.edges or self.faces or self.face_uvs)

    # -- the fast path ----------------------------------------------------------------------------------

    def slot_moves(self):
        """The table slots (ascending, distinct, an int array) whose position changed, when this change holds nothing
        but position writes under the table's current slot mapping; None otherwise (read `vertices`)."""
        if self.edges or self.faces or self.face_uvs:
            return None
        entries = self._entries
        if not entries:
            return _EMPTY_SLOTS
        current = self.table._slot_vertex
        for entry in entries:
            if type(entry) is dict or entry.slot_vertex is not current:
                return None
        if len(entries) == 1:
            return entries[0].slots
        return np.unique(np.concatenate([entry.slots for entry in entries]))

    # -- recording (the table) ----------------------------------------------------------------------------

    def _record_ids(self, records: dict) -> None:
        entries = self._entries
        last = entries[-1] if entries else None
        if type(last) is dict:
            for v, before in records.items():
                if v not in last:
                    last[v] = before
        else:
            entries.append(dict(records))

    def _record_chunk(self, chunk: _Chunk) -> None:
        self._entries.append(chunk)
        self._rows += len(chunk.slots)
        if self._rows > _COMPACT_ROWS * max(len(self.table.P), 1024):
            self._compact()

    def _compact(self) -> None:
        """Adjacent chunks of one slot mapping become one (`np.unique(..., return_index=True)` keeps each slot's first
        record); more than `_MAX_ENTRIES` entries fold into the dict."""
        merged: list = []
        run: list = []

        def close_run() -> None:
            if len(run) == 1:
                merged.append(run[0])
            elif run:
                slots = np.concatenate([c.slots for c in run])
                before = np.concatenate([c.before for c in run])
                unique, first = np.unique(slots, return_index=True)
                merged.append(_Chunk(_frozen(unique), _frozen(before[first]), run[0].slot_vertex))
            run.clear()

        for entry in self._entries:
            if type(entry) is not dict and (not run or entry.slot_vertex is run[0].slot_vertex):
                run.append(entry)
                continue
            close_run()
            if type(entry) is dict:
                merged.append(entry)
            else:
                run.append(entry)
        close_run()
        self._entries = merged
        self._rows = sum(len(e.slots) for e in merged if type(e) is not dict)
        if len(merged) > _MAX_ENTRIES:
            self.vertices  # noqa: B018 - folds every entry into the dict


class SurfaceWatch:
    """A persistent journal of a `SurfacePositions` (the `core.mesh.MeshWatch` contract): records until `take()` hands
    the accumulated `SurfaceChange` over; stops on `close()` or when garbage-collected."""

    def __init__(self, surface: "SurfacePositions") -> None:
        self.mesh = surface
        self._box = [SurfaceChange(surface)]
        surface._logs.append(self._box[0])
        self._finalizer = weakref.finalize(self, _detach_log, surface._logs, self._box)

    def take(self) -> SurfaceChange:
        box, logs = self._box, self.mesh._logs
        old, new = box[0], SurfaceChange(self.mesh)
        for i, log in enumerate(logs):
            if log is old:
                logs[i] = new
                break
        else:
            return old  # closed
        box[0] = new
        return old

    def peek(self) -> SurfaceChange:
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


class MovedVertices(Set):
    """The vertices one owner update changed (the H7 `sync() -> moved` set, AD-032 §11.1): a read-only `Set` of
    `VertexId`s over a slot array and the slot -> `VertexId` list in force; the ids are built only when iterated or
    tested (`len` / `bool` without). `slots` is the array (the owner's table slots, ascending, distinct)."""

    __slots__ = ("slots", "_slot_vertex", "_ids")

    def __init__(self, slots, slot_vertex: list) -> None:
        self.slots = slots
        self._slot_vertex = slot_vertex
        self._ids: Optional[frozenset] = None

    def _vertices(self) -> frozenset:
        ids = self._ids
        if ids is None:
            slot_vertex = self._slot_vertex
            ids = self._ids = frozenset(slot_vertex[s] for s in self.slots.tolist())
        return ids

    def __len__(self) -> int:
        return len(self.slots)

    def __iter__(self):
        return iter(self._vertices())

    def __contains__(self, vertex_id) -> bool:
        return vertex_id in self._vertices()

    def __repr__(self) -> str:
        return f"MovedVertices({len(self)})"


def _grown(array, size: int, fill=0):
    """`array` with at least `size` rows (doubling; new rows `fill`)."""
    if len(array) >= size:
        return array
    out = np.empty((max(size, 2 * len(array), 16),) + array.shape[1:], dtype=array.dtype)
    out[:len(array)] = array
    out[len(array):] = fill
    return out


class SurfacePositions:
    """A stage's evaluated surface: the base's topology, positions from a slot-indexed float64 table (module docstring).

    `position(v)` gives the starting position of every vertex of `base` (default: the base's rest position).
    `layout`: another `SurfacePositions` over the same base whose slots this table mirrors (its rows are copied as the
    starting positions unless `position` is given)."""

    def __init__(self, base, position: Optional[Callable] = None, layout: Optional["SurfacePositions"] = None) -> None:
        self.base = base
        #: the table whose slots this one mirrors (None = its own layout)
        self._layout = layout
        if layout is not None:
            if layout.base is not base:
                raise ValueError("a mirrored table needs the same base mesh")
            self._index: dict = dict(layout._index)
            self._slot_vertex: list = list(layout._slot_vertex)
            self._held = layout._held.copy()
            self._end = layout._end
            self._free: list = []
            P = layout.P.copy()
            if position is not None and self._index:
                ids = list(self._index)
                slots = np.fromiter(self._index.values(), dtype=_INDEX, count=len(ids))
                P[slots] = np.fromiter((c for v in ids for c in position(v)), dtype=np.float64,
                                       count=3 * len(ids)).reshape(-1, 3)
        else:
            ids = base.all_vertex_ids()
            read = base.vertex_position if position is None else position
            n = len(ids)
            #: VertexId -> slot (the vertices the table holds)
            self._index = dict(zip(ids, range(n)))
            #: slot -> VertexId, None = free (copied before a change once a journal chunk refers to it)
            self._slot_vertex = list(ids)
            self._held = np.ones(n, dtype=bool)
            self._end = n
            self._free = []
            P = np.empty((n, 3))
            if n:
                P[:] = np.fromiter((c for v in ids for c in read(v)), dtype=np.float64, count=3 * n).reshape(n, 3)
        self._set_array(P)
        #: True while a journal chunk or a `MovedVertices` refers to `_slot_vertex` (copy before changing it)
        self._mapping_shared = False
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

    def _set_array(self, P) -> None:
        #: slot -> position (n x 3 float64); a free slot keeps its last row until reused
        self.P = P
        self._flat = memoryview(P).cast("B").cast("d")  # three float reads per `vertex_position`, no NumPy scalar
        self._readonly = P.view()
        self._readonly.flags.writeable = False

    # -- the read API ---------------------------------------------------------------------------------

    def vertex_position(self, vertex_id) -> tuple:
        i = 3 * self._index[vertex_id]
        flat = self._flat
        return (flat[i], flat[i + 1], flat[i + 2])

    def positions(self) -> dict:
        """{VertexId: position} of every vertex the table holds (tests, probes; ascending id)."""
        index = self._index
        ids = sorted(index)
        rows = self.P[np.fromiter(map(index.__getitem__, ids), dtype=_INDEX, count=len(ids))].tolist()
        return {v: tuple(row) for v, row in zip(ids, rows)}

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

    # -- the array hand-over (AD-032 §11.3; duck-typed for the viewport) ----------------------------

    def position_array(self):
        """The table: rows = slots, float64 x 3, read-only (a free slot holds its last row)."""
        return self._readonly

    def table_slots(self, vertex_ids) -> np.ndarray:
        """The slots of `vertex_ids` (a sized iterable of held vertices; `KeyError` for any other), in that order."""
        return np.fromiter(map(self._index.__getitem__, vertex_ids), dtype=_INDEX, count=len(vertex_ids))

    @property
    def capacity(self) -> int:
        return len(self.P)

    @property
    def slot_count(self) -> int:
        """Slots ever handed out (held + free); the rows beyond are spare capacity."""
        return self._end

    # -- the owner's API (the stage that evaluates this surface; nobody else writes) ------------------

    def _mapping(self) -> list:
        """`_slot_vertex` for a change (copied first if a chunk or a moved set refers to it)."""
        if self._mapping_shared:
            self._slot_vertex = list(self._slot_vertex)
            self._mapping_shared = False
        return self._slot_vertex

    def _shared_mapping(self) -> list:
        self._mapping_shared = True
        return self._slot_vertex

    def _owner_set_slots(self, slots, rows) -> None:
        """Rows of held slots without a journal record (the owner's first build)."""
        self.P[slots] = rows

    def _grow(self, size: int) -> None:
        if size > len(self.P):
            self._set_array(_grown(self.P, size))
            self._held = _grown(self._held, len(self.P), False)
            self._slot_vertex.extend([None] * (len(self.P) - len(self._slot_vertex)))

    def _owner_add(self, vertex_id, position) -> int:
        """A vertex enters the table and gets a slot (a free one, else a new one; a mirrored table takes its layout's
        slot); returns it. The caller records it (before None)."""
        layout = self._layout
        if layout is not None:
            s = layout._index[vertex_id]
            if s < len(self.P) and self._held[s]:
                raise RuntimeError(f"mirrored table: slot {s} of {vertex_id!r} is still held by "
                                   f"{self._slot_vertex[s]!r} (the layout moved ahead of this table)")
        elif self._free:
            s = self._free.pop()
        else:
            s = self._end
        self._grow(s + 1)
        self._end = max(self._end, s + 1)
        self._mapping()[s] = vertex_id
        self._held[s] = True
        self._index[vertex_id] = s
        self.P[s] = position
        return s

    def _owner_record(self, moved: dict) -> None:
        """Journal by id: `moved` = {VertexId: before position, None = new in the table} of one update."""
        if moved:
            for log in self._logs:
                log._record_ids(moved)

    def _owner_write_slots(self, slots, rows, always=None):
        """Writes `rows` to the held `slots` (ascending, distinct) where they differ from the table (the tuple `!=`:
        any component, -0.0 == 0.0) and records those as one chunk; `always` (bool per slot, optional) marks slots that
        are written unconditionally and not recorded (new in this update, recorded by id). Returns the changed slots
        (ascending; without the `always` ones)."""
        if not len(slots):
            return _EMPTY_SLOTS
        P = self.P
        old = P[slots]
        diff = (rows != old).any(axis=1)
        if always is not None:
            P[slots[always]] = rows[always]
            diff &= ~always
        moved = slots[diff]
        if len(moved):
            P[moved] = rows[diff]
            if self._logs:
                chunk = _Chunk(_frozen(moved), _frozen(old[diff]), self._shared_mapping())
                for log in self._logs:
                    log._record_chunk(chunk)
        return moved

    def _owner_follow_topology(self, change) -> list:
        """The base's topology changed (`change` names the elements: the base's journal, or the journal of the view the
        owner reads): drops the vertices the base no longer has and forwards the element records to every watch.
        Returns the freed slots. Positions of new vertices come with the owner's next write (recorded there, before
        None)."""
        valid, index, P = self.base.is_valid_vertex, self._index, self.P
        gone = {}
        freed = []
        for v in change.vertices:
            s = index.get(v)
            if s is not None and not valid(v):
                gone[v] = tuple(P[s].tolist())
                del index[v]
                freed.append(s)
        if freed:
            mapping = self._mapping()
            for s in freed:
                mapping[s] = None
                self._held[s] = False
            if self._layout is None:
                self._free.extend(freed)
        for log in self._logs:
            if gone:
                log._record_ids(gone)
            _merge(log.edges, change.edges)
            _merge(log.faces, change.faces)
            _merge(log.face_uvs, change.face_uvs)
        return freed

    def _owner_write(self, items: Iterable) -> set:
        """Writes `(VertexId, position tuple)` pairs; only the positions that differ (or are new) change and are
        recorded (new vertices by id, the others as one chunk). Returns those vertices."""
        index = self._index
        new: dict = {}
        known: dict = {}
        for v, p in items:
            if v in index:
                known[v] = p
            else:
                self._owner_add(v, p)
                new[v] = None
        self._owner_record(new)
        moved: set = set(new)
        if known:
            order = sorted(known, key=index.__getitem__)
            slots = np.fromiter(map(index.__getitem__, order), dtype=_INDEX, count=len(order))
            rows = np.array([known[v] for v in order], dtype=np.float64).reshape(-1, 3)
            changed = self._owner_write_slots(slots, rows)
            mapping = self._slot_vertex
            moved.update(mapping[s] for s in changed.tolist())
        return moved

    def _owner_moved(self, slots) -> MovedVertices:
        """The moved set of an update over the table's current slot mapping (H7 `sync() -> moved`)."""
        if not len(slots):
            return MovedVertices(_EMPTY_SLOTS, [])
        return MovedVertices(slots, self._shared_mapping())
