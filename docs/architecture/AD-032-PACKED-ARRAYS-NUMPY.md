# AD-032 — Packed arrays (NumPy) for the viewport's derived geometry (audit O3, stage 1)

**Status:** IMPLEMENTED, stage 1 (2026-11-12). Agent decision within Manu's plan and decisions of 2026-11-11 (O3 after
O2 and O1; **D1**: NumPy as a production dependency, pinned `numpy==2.2.6`, Python 3.12.10 the verified runtime on the
reference PC, no x86-64-v2 requirement, NumPy enters `requirements.txt` with the first O3 stage). Names `PROVISIONAL`.
No Core change (CORE_V1_FREEZE untouched); `src/core` imports no NumPy. Stage 2 (skin and morph on arrays, the O1
position table as an n×3 float64 array) and the SubD stencils are **not** part of it (§9).
**Reference PC (Manu, 2026-11-13):** D1 verified — the production import and execution under Python 3.12.10 + NumPy 2.2.6
on the Q9550, the array tests (normals bit-identical on that CPU) and the GL tests (165, pixel gate) pass; before /
after measured (§8). Not run there yet: `pytest tests` and `experiments/morph_lab/tests` under 3.12.
**Source:** [audit 2026-11-10](../research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md) §E.3, §E.5, §G.3
row O3, §H step 5, "Decisions (Manu, 2026-11-11)" D1–D3, the addenda "O1 in the container" / "O1 on the reference PC";
[AD-025 §18](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md#18-addendum-2026-11-11-the-evaluated-surface-as-a-position-table-audit-o1)
(the position table); [AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) (slot layout, journal-driven patches);
[AD-018](AD-018-PRODUCTION-DRAW-BINDING.md) (store contract, O2 face-data layout).

**Why a new AD and not an addendum to AD-018 / AD-023.** Two things are decided here that neither covers: a
project-wide dependency with a hardware constraint (NumPy, D1 — it binds every module above the Core, not the draw
binding or the topology sync), and a representation that stage 2 extends from the viewport to the evaluation stages
(AD-025 §18, AD-028 §17.4). AD-018 (the store contract accepts float32 arrays) and AD-023 (§N "native code or NumPy")
get a one-paragraph addendum pointing here.

---

## 1. What changed

`RenderMesh` (`src/viewport/render_mesh.py`) no longer computes its derived geometry per vertex in Python over dicts
keyed by ID (`DerivedGeometry.vertex_to_faces` / `face_normals` / `vertex_normals`, tuples per element), but on NumPy
arrays indexed by its own slot layout: `src/viewport/packed_geometry.py`, class `PackedGeometry`, one per `RenderMesh`
(`RenderMesh.packed`).

| Array | Shape, type | Indexed by |
|---|---|---|
| `P` positions | slots × 3, float64 (a free slot holds `DEAD_POSITION`) | vertex slot |
| `VN` vertex normals | slots × 3, float64 | vertex slot |
| `FN` face normals | rows × 3, float64 | face row |
| `corners` | ragged int lists: the vertex slots of each row's boundary, in boundary order | face row |
| `vertex_faces` | ragged int lists: the rows around each vertex, in ascending `FaceId` order | vertex slot |
| CPU mirrors (in `RenderMesh._mirror`) | slots × 3 / rows × 4, float32 | slot / row |

A ragged list lives in one pool with a start, a count and a capacity per item (`Ragged`); a list that outgrows its block
moves to the end of the pool, and the pool is compacted when more than half of it is unused. A full rebuild lays the
pools out compactly (vertex lists with two spare entries each).

Per frame (`_sync_geometry`): `_read_moved` turns the moved `VertexId`s into slots and reads each moved vertex's
position once into `P`; `PackedGeometry.neighbourhood` gathers the faces around the moved slots and the vertices of
those faces (marks or a sort, no Python sets); `update_face_normals` / `update_vertex_normals` recompute them on the
arrays; the float32 mirrors are patched with fancy indexing and handed to the store in merged ranges (`_upload_slots`,
`_upload_face_normals`; the range merge is vectorised). The full build computes every normal with the same kernels.
`_patch_topology` keeps all of its bookkeeping (slots, rows, triangles, edges, hidden, UVs) and writes the journal's
changes into the arrays: freed rows / slots cleared, new boundaries into `corners`, the adjacency of every touched
vertex rewritten in FaceId order, then the normals of the re-triangulated faces and of every vertex around them.

What is not changed: the slot layout and its rules (AD-023 V1), the journal, the face-data layout and shader (O2), the
store's GL calls, the triangulation (per face in Python, at topology syncs only), the wire and the GPU picker (they read
the same buffers), hide, region tints, UVs, `content_revision` / `layout_revision`, every counter in `stats`.

## 2. Where the array mirror lives

In the viewport, owned by each `RenderMesh`, on that `RenderMesh`'s slots and rows. Reasons:

- **Data flow Core → Viewport stays as it is.** The arrays are derived data of the viewport (VIEWPORT_V02 §4.4, like
  `DerivedGeometry` before); they are filled from what `RenderMesh` already reads — `mesh.vertex_position`,
  `face_vertices` and the change journal — whether the mesh is a `core.Mesh` or a stage's `SurfacePositions`.
- **The viewport imports nothing from `src/mirai`** (unchanged; `packed_geometry` imports only NumPy).
- **NumPy above the Core only.** `src/core` imports no NumPy; `tests/test_packed_geometry.py` checks every module of
  `src/core` for it. The Core's own packed layers (`LayerSlots` + `PackedValues`, `array('d')`) are untouched.
- **A wrong NumPy says so before it loads** (2026-11-13): `packed_geometry` compares the installed NumPy with
  `PINNED_NUMPY` (= `requirements.txt`, test-pinned) through package metadata and writes one stderr line (version,
  Python, interpreter path) before `import numpy` - on the reference PC `src/main.py` under the global Python 3.14
  ended with exit code `0xC0000409` and no Python message, so the `ImportError` hint never came. Missing NumPy keeps
  the `ImportError` with the hint.
- **No second ID map.** `PackedGeometry` knows no IDs; `RenderMesh`'s `_vertex_index` / `_slot_vertex` / `_face_row` /
  `_row_face` are the only maps (the pattern of `LayerSlots` + `PackedValues`: a dict ID → slot, values per slot).
  `RenderMesh.derived` is now a read-only view by ID over the arrays (`DerivedView`: `vertex_normals`, `face_normals`,
  `vertex_to_faces`, bounds, `affected_neighborhood`) for tests, probes and the oracle comparisons.

## 3. How it stays in step with the journal

Exactly where the slot layout does, in the same methods: a full rebuild (`_rebuild_index_mapping` → `PackedGeometry.build`)
lays out slots and rows compactly in mesh order with `SPARE_FRACTION` spare and builds the arrays on that layout; a
topology sync patches what the journal names (`_patch_topology`, below), or falls back to the full rebuild for the same
reasons as before (spare exhausted, a change above `PATCH_MAX_FRACTION`, small meshes). Between two full rebuilds a slot
or row keeps its index, so `P`, `VN`, `FN` never resize; only the ragged pools grow.

In `_patch_topology`, the adjacency of every vertex an old or new boundary touches is read from `vertex_faces` *before*
anything moves (rows → FaceIds), edited as FaceId sets exactly as the old dict-of-sets was, and written back as rows in
ascending FaceId order once every new face has its row. The faces to re-triangulate around moved vertices are read from
the arrays at the same moment (their faces before the patch minus the removed ones, plus the new / changed faces — the
same set the old code read from its edited dict). "Patch == full rebuild" is pinned per element as before
(`tests/test_render_mesh_incremental.py`, ten random sequences with Undo / Redo) — now **bit-identical**, positions and
both normal sets included (§5).

## 4. How positions get into the arrays

- **Per frame, only the moved vertices are read**: `_read_moved` reads `vertex_position(v)` once per moved vertex
  (from the edit mesh or the shown stage's `SurfacePositions`) into `P[slots]`. Nothing per frame reads the whole mesh.
  Before O3 the same frame read about five positions per moved vertex (once for the upload, again per adjacent face for
  the Newell sums). The per-vertex cost that remains is this read and the ID → slot lookup (row 2f of the split, §8).
- **Topology patches** read the new and moved vertices of the journal; **full rebuilds** read every vertex once, as
  before (the triangulation needs them anyway).
- **Why the O1 table stays a list of tuples in stage 1.** With the reads cut to one per moved vertex, a float64 table
  (AD-025 §18 measured +120–190 ns per tuple read) would gain nothing here; the table becomes an array in stage 2 together
  with the stage kernels that write it and a hand-over of positions as arrays (stage → `RenderMesh` without a read per
  vertex). That changes the H7 contract and is stage 2's decision, not this one.

## 5. Normals: definition, summation order, bit-identity

The definition is the one `derived.py` has documented since 2026-09-30, with one change of **order**:

- **Face normal:** the normalised Newell sum over the boundary: per corner k from 0.0,
  `n += ((a.y−b.y)(a.z+b.z), (a.z−b.z)(a.x+b.x), (a.x−b.x)(a.y+b.y))`, a = corner k, b = corner k+1 (wrapping); then
  `n / sqrt(n.x·n.x + n.y·n.y + n.z·n.z)`, (0, 0, 0) below 1e-12. Unchanged.
- **Vertex normal:** the normalised sum of the face normals around the vertex — **added in ascending `FaceId` order**
  (before: in the iteration order of a Python `set` of `FaceId`s, i.e. an order that depends on the set's history).

The array kernels add in exactly these orders: one corner column / one face column at a time (`acc[:m_k] += …` over
the faces that still have a corner k, sorted longest first so they form a prefix), never `np.sum` / `np.add.reduceat`,
whose internal order is not Python's left-to-right order (that is where the prototype's ≤ 3·10⁻¹⁴ came from, audit
§E.5). NumPy's float64 `+ − × ÷ sqrt` are the same IEEE-754 operations as Python's floats, so the result is
**bit-identical** to the pure-Python reference — no tolerance anywhere:

- `derived.face_normal` / `DerivedGeometry` stay as the pure-Python reference (test oracle) of the definition;
  `DerivedGeometry` now sums in FaceId order too (`sorted(...)`, two lines).
- `tests/test_packed_geometry.py`: arrays == reference, float for float, after a full build, after position patches of
  1 / 30 / 100 % and after random topology sequences with Undo / Redo (pools relocated and compacted), on quads,
  triangles, a pentagon, a 9-gon, a valence-12 pole, collinear first corners, a face without area, a vertex without
  faces, `head_basemesh` and `gollum_20k`.
- Because the order is a property of the IDs, not of the layout, a patched layout and a fresh build now hold
  bit-identical normals: `test_render_mesh_incremental.py` compares positions, vertex normals and face-normal rows with
  `==` (until now within 1e-9 / 1e-6, "a sum over a set of faces whose iteration order may differ").

**What the new order changes against the old code** (container, scratch script, every vertex normal of the mesh):
float64 components that differ — `head_basemesh` 28 %, `gollum_20k` 22 %, 87.5k fixture 18 %, each by at most
2.2·10⁻¹⁶; after the float32 rounding the GPU sees: 15 of 978 components on `head_basemesh` (one float32 step), none
on `gollum_20k` and the 87.5k fixture. Images: the one-time cross-check of O2 repeated against the pre-O3 tree (16
scenes: `head_basemesh` and `gollum_20k` × Smooth / Flat × perspective / ortho × two views, deformed through the patch
path, 640×480, each tree in its own process) — **16 of 16 byte-identical**.

## 6. The hand-over to the store

`ResourceStore.update(name, offset, data, nbytes)` now also takes a contiguous 1-D float32 array (a NumPy view of a
mirror range) besides a list; the store copies it. `RenderMesh` passes views of its float32 mirrors for positions,
normals and face normals (full rebuilds included).

- `GLRenderStore` keeps the vertex attributes' CPU copy as `array('f')` (float32 like the GPU buffer) and patches
  pyglet's backing store with one `memmove` per range instead of an element-wise slice assignment from a Python list;
  face data is copied byte for byte into its `array('f')`. The GL calls are unchanged (the face data's
  `glBufferSubData` ranges; pyglet's commit of the vertex buffers — reading the attribute still marks pyglet's whole
  region dirty, which is the separate "GPU vertex-buffer upload" package of the audit addendum, untouched here).
- `TraceStore` stores `data.tolist()`. It therefore holds float32 values after a full build too (before O3 it held the
  float64 values of a full build and float32 values after patches); `test_render_mesh_face_data.py` now compares the
  store with the float32 rounding exactly instead of within 1e-9.

## 7. The prototype kernels (`experiments/drag_cost/probe_kernels.py`)

They stay in `experiments/` unchanged, as the measurement reference; nothing is imported from there. Taken over as a
**design**, rewritten in `src/viewport/packed_geometry.py`: positions per slot as n×3 float64, the corner lists and the
vertex → faces lists as packed int arrays, the O(touched) gather (faces of the moved vertices, then their vertices),
float32 mirrors. **Not** taken over: the `reduceat` sums (order, §5); `np.unique` for every gather (a mark array above
1/16 of the range); the switch to "all normals" above 25 % moved (not needed: the gather is O(touched) and the full build
uses the same kernels); CSR arrays that are rebuilt whole (the production arrays are patched from the journal, with
ragged pools); `FlatPython` and the native C column (O4, only per D2).

## 8. Measured [C]

Container, not the reference PC (REFERENCE_HARDWARE §4): Intel Xeon @ 2.10 GHz, 4 logical cores, Linux, Python 3.13.18,
NumPy 2.2.6, Mesa llvmpipe. Before = `7153fae` (the probe commit; `src/` as `3a96ee3`, src/ tree `559d88b8e2`) from a
git worktree; after = the O3 tree. Raw outputs, the pairs and the reference-PC commands:
[`RESULTS_O3_STAGE1_CONTAINER_2026-11-12.md`](../../experiments/drag_cost/RESULTS_O3_STAGE1_CONTAINER_2026-11-12.md).

| 87.5k, 15 % region | before | after |
|---|---:|---:|
| `RenderMesh._sync_geometry` per pose step (split, skin only), p50 | 70.8–82.6 ms | **11.9 ms** |
| of it: neighbourhood / face normals / vertex normals | 7.9–9.7 / 25.2–28.1 / 11.3–14.2 ms | 1.2 / 2.6 / 1.6 ms |
| of it: positions + normals → store / face data → store | 14.3–17.7 / 7.0–8.2 ms | 2.1 / 0.7 ms |
| of it: ids → slots, positions → arrays (new, row 2f) | — | 3.2 ms |
| pose step (split), p50 | 97.0–117.4 ms | **35.8–35.9 ms** |
| D3 frame, pose / weight, wire off, p50 (pair 2) | 139.0 / 169.6 ms | **79.5 / 107.2 ms** |
| D3 frame, pose / weight, wire ON, p50 (pair 2) | 163.1 / 190.1 ms | **99.8 / 125.6 ms** |
| D3 `_sync_geometry` p50, all four rows | 71.2–91.2 ms | **11.9–12.6 ms** |
| new surface `RenderMesh` (first weight / pose step) | 2.1–3.0 s | **1.0–1.1 s** |
| load + first frame | 3.7–5.5 s | **2.7–2.9 s** |
| process memory with both stages | 974–976 MiB | **880–881 MiB** |
| bytes to the store per frame | 556,940 | 556,940 |

**D3 [C]: OVER** in every row, before and after (in the container the software rasteriser alone takes 24–47 ms of a
frame). What is left of the tick: the stage evaluation (23–43 ms, stage 2), `_sync_geometry` 12 ms, of which 3.2 ms
is the remaining per-vertex read (row 2f), and the HUD in weight rows (7 ms, its own package). On the reference PC the
same split after O1 was 222 ms `_sync_geometry` of a 307 ms pose frame.

**Reference PC [RPC]** (Manu, 2026-11-13, Python 3.12.10 + NumPy 2.2.6, panels on, before and after with the same
interpreter; [`RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md`](../../experiments/drag_cost/RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md)):
`_sync_geometry` per pose step 204.80 → **34.60 ms** (row 2f 9.50 ms), the pose step 267.25 → 96.66 ms; D3 frame p50 /
p95 pose 294.63 / 298.94 → **117.77 / 122.87 ms**, weight 361.96 / 388.13 → **189.17 / 199.91 ms** (wire ON within
1–2 ms at p50), `_sync_geometry` in every D3 row 207–211 → 32–33 ms; a new surface `RenderMesh` 6.2–6.6 → 3.0 s;
process memory with both stages 714 → 619 MiB. **D3 still OVER** (p95 3.7× pose, 6× weight). Every part of the new sync
costs ≈ 3× its container time there, the NumPy parts included (per-call overhead at 13k elements, not arithmetic).

## 9. Not in this stage

- **Stage 2:** skin and morph evaluation on arrays, the O1 table as an n×3 float64 array, positions handed from the
  stage to `RenderMesh` as arrays (no read per vertex, H7 contract). Its oracles are the existing ones
  (`morph_mix.evaluate`, `skinning.evaluate`, bit-identical). Not started in this session: after stage 1 the D3 tick
  in the container is ≈ 23–43 ms stage evaluation against 12 ms `_sync_geometry`, so stage 2 is the next lever — but
  only the arithmetic is a kernel; the rest of a stage frame is per-vertex Python that an array table alone does not
  remove, and it crosses contracts:
  - **the journal** — `SurfacePositions._owner_record` merges one before-record per moved vertex into every watch, and
    consumers read them (`morph_mix.topology_touched`, `Viewport._follow_cage`: `before is None` = new; `regions`,
    `orbit_focus`); an array stage needs a record form for "these slots moved" with the same meaning;
  - **candidates** — the skin stage's bone → points index and the mix's offset caches are dicts / sets of `VertexId`s;
    as arrays they become slot index arrays kept in step with the weights / offsets journal;
  - **the hand-over** — `RenderMesh` reads each moved position once (row 2f, 3.2 ms here); without that read it needs
    the stage's positions and a slot map stage-table → render slots (H7 is duck-typed; the viewport still imports
    nothing from `src/mirai`);
  - **bit-identity details** — the mix adds "the first term as it is, then += in ascending LayerId order"; the skin's
    remainder weight is `1.0 - math.fsum(...)` over the bones present in the pose (no NumPy equivalent: precompute per
    point when weights or the bone set change), its first term is taken as it is, `c == 0.0` skips the rest term.
  A design pass for these four points comes before code (an AD addendum to AD-025 §18 / AD-028 §17.4 or here).
  *(2026-11-13: the design is §11.)*
- SubD stencils on arrays (own package); O4 (C kernels; only per D2, if O3 leaves the D3 bar unmet on the reference
  PC); D6; the GPU shading cost of O2's fetches; the HUD during a weight drag; the GPU vertex-buffer upload of pyglet's
  whole region (each its own small package, audit addenda).
- The triangulation stays per face in Python (topology syncs and full builds only).
- `transform_space.SelectionNormals` (the gizmo's frame) keeps its own small Python computation.

## 10. Tests

New `tests/test_packed_geometry.py` (bit-identity, pools, the id view, the store's float32 values, NumPy above the Core,
the error message without NumPy). Made stricter: `test_render_mesh_incremental.py` (patch == rebuild bit-identical),
`test_render_mesh_face_data.py` (store == float32 rounding). Unchanged and passing: `test_gl_face_data_layout.py`
(production path against the frozen pre-O2 shader, byte-identical), the GL tests, picking, hide, tints, UVs, wire, the
surface-provider and stage tests.

Container: `tests/` 6,928 passed, 1 failed (the pre-existing `test_scene_menu_local_tmp.py`, audit §I.7), 8 skipped (GL
modules in the combined run); `tests/test_gl_*.py` in its own process 165 passed; `experiments/morph_lab/tests` 49,
`experiments/drag_cost/tests` 84 passed. Six hand mutations, each caught: vertex normals in another order, Newell
wrapping to the wrong corner, the adjacency not written back, the adjacency in set order, the last upload range
dropped, the faces around moved vertices not re-triangulated. The pixel cross-check against the pre-O3 tree: §5.

---

## 11. Stage 2 — design (2026-11-13)

Scope (audit §H step 5, second stage): `MixSurface` and `SkinSurface` evaluate on arrays, the O1 table
(`SurfacePositions`) holds its positions as an n×3 float64 array, and the surface `RenderMesh` takes the moved positions
as arrays (row 2f without a read per vertex). Agent decision within Manu's plan (O3, D1). **No Core change and no
tolerance** — both reasons for a stop (§ "Haltepunkt" of the task) are absent, so the design is implemented in the same
session. The four points of §9, in that order:

### 11.1 The journal: "these slots moved", same meaning

A watch of a `SurfacePositions` accumulates a `SurfaceChange` (the `MeshChange` interface, duck-typed) with an ordered
list of entries of two kinds:

- **position records as slot chunks** — `(slots, before, slot_vertex)`: the table slots one stage write changed
  (distinct), their positions before that write (float64 rows) and the slot → `VertexId` list in force when it was
  recorded. One chunk per write, shared by every watch (immutable arrays): recording costs O(watches), not
  O(moved × watches) as `_owner_record`'s per-vertex merge did;
- **records by id** (a dict `VertexId -> before`) for everything that changes the slot mapping: a vertex new in the table
  (before None) and a vertex gone (its last shown position) — plus, as now, the base's edge / face / UV records of a
  topology edit forwarded by `_owner_follow_topology`.

**Meaning unchanged.** `change.vertices` is a plain dict, built on first access from the entries in their order, first
record wins (the state at the consumer's last `take`), None = new, gone = last position — the records the tuple table
wrote. A change of the slot mapping first copies the slot → `VertexId` list if a chunk refers to it (copy-on-write),
so a chunk always resolves to the vertices it was recorded for, and every mapping change leaves a record by id in every
watch. `is_empty()` and `peek()` never build the dict.

**The fast path (new, duck-typed): `change.slot_moves()`** returns the ascending, distinct slots when the change is
nothing but position records under the table's current mapping (no record by id, no edge / face / UV record), else
None — then the reader reads `change.vertices` as before. Readers, checked one by one:

| Reader | Watches | Reads after stage 2 |
|---|---|---|
| `RenderMesh` (surface, entry surfaces, cage pick) | the stage surface it draws | `slot_moves()` per frame; the dict at topology changes (as now) |
| `SkinSurface` (input = the mix) | the mix | `slot_moves()` per frame; the dict and `morph_mix.topology_touched` at topology changes |
| `Viewport._follow_cage`, the soft shading's cage | the cage (the mix) | `is_empty()` / `take()` only |
| `Viewport._cage_pick_render_mesh`, `PickCache`, the hidden-set cache, SubD as the next stage | the cage / their input | the dict (`before is None`, keys, `before[:2]` of edges) on their own refresh — unchanged |
| `regions`, `orbit_focus` | the edit mesh (`core.Mesh`, `FocusTracker.bind(scene.mesh)`; a Core edit's change) | never a stage surface — unchanged by construction |

**Bounded.** A watch that is not taken for a while (the picking cache during a drag) merges adjacent chunks of one
mapping once its rows exceed the table's capacity (`np.unique(..., return_index=True)`: first occurrence wins) and folds
into the dict beyond 64 entries; its memory stays O(table).

**The moved set of a stage update** (H7 `sync() -> moved`, `entry_moved`) becomes a `MovedVertices`: a read-only `Set`
of `VertexId`s over a slot array and its slot → `VertexId` list, built into ids only when iterated or tested; `len` and
`bool` without that. The viewport hands it to `RenderMesh.mark_vertices_dirty` without `set(...)`.

### 11.2 Candidates as slot indices, kept in step with the journal

- **Mix.** Per shown target the offsets cache becomes arrays on the table's slots — `present` (bool) and `D` (n×3
  float64) — kept in step with the base's journal by the same rules as the dict it replaces (a whole-layer write reloads
  the layer's stored items; a per-key write sets `present` iff `d != (0, 0, 0)`, the same comparison); a freed slot
  clears its presence in every loaded target, a new vertex starts absent. The base positions are cached as `B` (n×3
  float64), refreshed for exactly the vertices the base's journal names. A weight step's candidates are the present
  slots of each target whose weight changed (cached `flatnonzero`), an edit's the slots of the journal's vertices; a
  vertex new in the base gets its slot before the offsets are read.
- **Skin.** The weights cache and the bone → points index stay by id (they change with weight writes, per element);
  each key gets a cached slot array, rebuilt when its point set or the slot mapping changed. The **posed terms** of every
  slot are padded arrays of width 4 (`WEIGHTS_WIDTH`): the transform row of each posed key, its weight, the count, `c`
  and `c == 0` — rebuilt for the points whose weights changed and for the points of keys that entered or left the posed
  set (identity ↔ posed, a bone added / deleted), not per pose step. A pose step's candidates are the slot arrays of the
  keys whose transform changed; a morph step's the input's `slot_moves()`.
- **Layout.** The skin's table **mirrors its input's slot layout** when the input is a table (the mix): built as a copy
  of the input's layout, it frees what the input freed and puts a new vertex on the input's slot. So the skin reads its
  input as `input.P[slots]` without a map, and the mix's `slot_moves()` are the skin's candidates as they are. Over the
  base mesh (no target) the skin keeps its own layout and caches the input positions like the mix's `B`.

### 11.3 The hand-over to `RenderMesh` without a read per vertex

Duck-typed (H7; the viewport still imports nothing from `src/mirai`): a mesh with `position_array()` (its n×3 float64
table, rows = its slots) and `table_slots(vertex_ids)` (their slots) gives `RenderMesh` a **table path**:

- full rebuild: the table slots of its vertices once, the positions from `position_array()[slots]` (the same floats
  `vertex_position` returns), and two int maps — table slot → render slot, render slot → table slot;
- topology patch: as now from the dict; the maps are patched for the vertices that went (through render → table) and
  came (`table_slots`);
- per frame: its own watch's `slot_moves()` → render slots through the map → `packed.P[render] =
  position_array()[table]` (`_read_table_moves`, row 2f). The host's moved set only marks geometry dirty; the journal is
  the truth (as it already is for topology). A `RenderMesh` over a `core.Mesh` (the edit mesh) keeps `_read_moved`.

### 11.4 Bit-identity, no tolerance

- **Mix**, per component and target column: the first present term `f * d` as it is (not added to 0.0), then
  `acc += f * d` in ascending `LayerId` order, then `b + acc`; a point without a term is `b` as stored.
- **Skin**, per term column j (the value's order = ascending key): `t = w * (((a0*x + a1*y) + a2*z) + a3)` per component,
  the first term as it is, then `+=`; `c = 1.0 - math.fsum(posed weights)` per point in Python when its terms are
  rebuilt; `c == 0.0` → `acc`, else `c*p + acc`; no posed term → `p` exactly.
- **Writes** only where `(new != old).any(axis=1)` — the tuple `!=` (−0.0 == 0.0, NaN != NaN).
- NumPy's float64 `*` and `+` are the IEEE operations Python's floats use (§5), one column at a time, never a reduction;
  `evaluate` (both modules) stays the pure-Python definition and the oracle.
- **Per-vertex reads** of the table (`vertex_position`) read three floats from a flat memoryview of the array: bit-exact,
  ≈ 100 ns slower than the stored tuple (container: 138 vs 36 ns). The per-frame readers move to arrays above; the
  remaining ones (picking cache refresh, overlays of selected elements, SubD as the next stage, triangulation at
  topology patches) read what they read before.

---

## Kurzfassung für Manu (Deutsch)

- **Was:** Die Anzeige rechnet ihre abgeleiteten Daten (Flächen- und Punktnormalen, welche Flächen an einem Punkt
  hängen, die Kopien für die Grafikkarte) jetzt mit NumPy auf kompakten Zahlen-Arrays statt Punkt für Punkt in Python.
  Inkrementell wie bisher: nur der bewegte Bereich wird neu gerechnet, Topologie-Änderungen werden aus dem
  Änderungs-Journal nachgezogen. Der Core ist unverändert und kennt kein NumPy.
- **Ergebnis gleich, bis aufs Bit:** Normalen sind identisch zur bisherigen Python-Definition. Einzige Festlegung: die
  Punktnormale summiert ihre Flächen jetzt in fester Reihenfolge (aufsteigende Flächen-ID) statt in zufälliger
  Mengen-Reihenfolge — Unterschied höchstens in der 16. Stelle, im Bild nichts (16 von 16 Testbildern byte-gleich).
- **Gemessen im Container (nicht dein PC):** Anzeige-Sync im Kieferbereich (87,5k, 15 %) 71–91 → 12 ms; ein
  Pose-Schritt 97–117 → 36 ms; D3-Frame Pose 139 → 80 ms (immer noch über 33 ms — hier rechnet die Grafik in Software,
  und die Skin-/Morph-Auswertung ist Stufe 2). Neues Anzeige-Mesh 2–3 s → 1 s.
- **NumPy:** `numpy==2.2.6` steht jetzt in `requirements.txt`. Auf deinem PC läuft das nur unter **Python 3.12**
  (nicht 3.14). D1 ist auf deinem PC geprüft (2026-11-13): Import, Ausführung, Bit-Gleichheit der Normalen, GL-Tests.
- **Auf deinem PC gemessen (2026-11-13):** Anzeige-Sync 205 → 35 ms, D3-Frame Pose 295 → 118 ms, Gewicht 362 →
  189 ms, neues Anzeige-Mesh 6,2–6,6 → 3,0 s. D3 noch nicht erreicht; größter Rest ist jetzt die Skin-/Morph-Auswertung
  (Stufe 2).

