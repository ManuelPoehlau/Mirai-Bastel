# AD-023 — Incremental Topology Sync and History

**Status:** PROPOSED (2026-10-17) - draft for Manu's decision and an independent review (fresh
session, Development System §6). Not decided; no production code exists. Per AGENTS.md §5 this
document lists alternatives, it does not select one.
**Mode (M5):** Discovery, decision preparation.
**Work package:** WP-TOPO-PERF-01 (proposed name).
**Artist input:** Manu, 2026-10-17: Blender on the reference PC runs "Topologie-Operationen" on 20k gollum
fluidly; incremental topology is "gleich wichtig" as GPU picking ([AD-022](AD-022-GPU-PICKING.md)).
**Basis (only linked):** [`experiments/drag_cost/README.md`](../../experiments/drag_cost/README.md) ("Topology ops on
the current architecture", "Haltepunkt"); [CORE_V1_FREEZE](CORE_V1_FREEZE.md) (§7.1 exceptions);
[V1_CORE](V1_CORE.md) §11 and AD-001 (ID continuity, in `src/core/ids.py`); `src/core/operations/topology.py`
(`MeshStateCommand`: full snapshots, and why); [AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md),
[AD-SYM-03](AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md); [`VIEWPORT_V02_ARCHITECTURE.md`](../viewport/VIEWPORT_V02_ARCHITECTURE.md)
§4.5, §5.4; [AD-018](AD-018-PRODUCTION-DRAW-BINDING.md).
**Decided by:** Artist (Intent, Priority) + review; a Core change additionally needs the CORE_V1_FREEZE §7
exception process.

---

## 1. Problem (measured, container, `gollum_20k` 21 875 V)

One topology op as the Artist triggers it (probe `--scenarios topology`, ms p50):

| Op | total | op itself | history | viewport sync | hover re-pick | undo frame |
|---|---:|---:|---:|---:|---:|---:|
| Extrude 1 face | 1 273 | 0.6 | 388 | 864 (3 syncs) | 51 | 956 |
| Extrude 20 faces | 1 834 | 22 | 889 | 917 (3 syncs) | 49 | 1 008 |
| Knife commit (1 cut) | 1 188 | 74 | 627 | 376 | 99 | 1 184 |
| Dissolve 1 edge | 781 | 11 | 313 | 361 | 85 | 1 000 |
| Delete 1 face | 792 | 13 | 336 | 381 | 50 | 927 |

The operation is 1-74 ms; the rest is whole-mesh work done once or several times per op:

| Part (headless, gollum_20k / 87.5k, ms) | 21.9k | 87.5k | where |
|---|---:|---:|---|
| `Mesh.export_state()` (×2 per op: before + after) | 84 | 660 | `Application._mesh_transaction`, `MeshStateCommand` |
| `Mesh.load_state()` (every undo / redo) | 311 | 2 139 | `MeshStateCommand.undo/redo` |
| re-triangulate every face | 154 | 546 | `RenderMesh._rebuild_index_mapping` |
| all normals | 112 | 522 | `DerivedGeometry.full_recompute` |
| all GPU buffers + face data rows | ~280 (profile) | - | `RenderMesh._rebuild_resources`, `GLRenderStore` |
| pick cache + `vertex_faces` | ~50 + O(E) | ~180 | `PickCache` after `invalidate()` |

Extrude pays the viewport rebuild three times (begin, a move, release). Picking is 5-10 % of an op; AD-022 does
not change this table.

**Referenz-PC (Manu, 2026-10-20, `gollum_20k`, je n = 3):** Delete 1 945, Dissolve 1 951, Knife 2 360, Extrude 3 065-3 599 ms; Undo-Frame
1 717-1 992 ms. Anteile: Viewport-Sync 55-85 %, History 8-26 %, Hover-Neupick 4-13 %; ein Strukturneubau ≈ 1,26 s. Die Reihenfolge
der Posten bleibt wie hier, der Viewport-Teil (V) wiegt auf dem Referenz-PC schwerer als der History-Teil (H). Tabelle und Rohausgabe:
[`experiments/drag_cost/README.md`](../../experiments/drag_cost/README.md) „Result: topology operations, reference PC“.

## 2. Options

### H - history

- **H0 - keep full snapshots, drop the redundant work (no Core change).** `MeshStateCommand` is a plain
  `undo()/redo()` object; a `mirai`-level command with the same protocol can take the "after" snapshot lazily
  (at the first undo the mesh *is* the after state) and decide "changed?" from the op's own result instead of
  `after == before`. Saves one `export_state` per op (~84 ms on 21.9k). Undo still pays `load_state` (311 ms).
- **H1 - delta entries (Core change).** The op reports the elements it touched; the entry stores only their
  before/after records plus the ID counters, and undo restores just those (ID continuity, AD-001, kept because
  IDs are restored, not re-issued). Needs a Core API to export / apply a partial state - a CORE_V1_FREEZE §7
  exception like AD-014 / AD-017; touched sets for every op (`delete_dissolve`, knife, extrude, split/connect,
  loop insert, the symmetric coordinators of AD-SYM-03). Expected: history and undo from ~0.3-1 s to ms (estimate).
- **H2 - structural sharing in `Mesh` (Core internals).** Copy-on-write snapshots; largest Core change, listed
  for completeness.

### V - viewport topology sync

- **V0 - cache per-face triangulation and normals (no contract change).** `RenderMesh` keeps the triangles per
  face; a topology change re-triangulates only faces whose boundary changed (found by comparing boundaries -
  O(F) dict work, but no triangulation), normals only around changed vertices (`vertex_to_faces`, §4.5). Buffers
  are still rebuilt whole. Expected: 154 + 112 ms → tens of ms (estimate); the upload part stays.
- **V1 - incremental buffers (AD-018 addendum).** Patch positions / indices / face rows for the touched range,
  with spare capacity so an op that adds a few faces does not recreate the VertexList. Needs the touched sets
  (shared with H1) and a `ResourceStore` patch contract for index data.
- **V2 - one sync per gesture.** Extrude's three rebuilds (begin, first move, release) collapse to one plus
  vertex patches; small, independent of the rest.

### P - pick cache

`vertex_faces` and the screen positions per touched element instead of a full rebuild; moot for the window if
AD-022 is decided (the GPU path needs no CPU cache), still useful headless.

## 3. What it touches

- `src/core` (frozen): H1 / H2 need a partial state API or internal changes - CORE_V1_FREEZE §7 exception with
  contract tests; H0 / V0 / V2 do not touch the Core.
- AD-001 (ID continuity): H1 must restore IDs and counters exactly; the snapshot rationale in
  `operations/topology.py` is the constraint to meet, not to drop.
- AD-SYM-02 / AD-SYM-03: one gesture = one history entry, symmetric ops through `_mesh_transaction` - unchanged in
  shape, the entry type changes.
- `VIEWPORT_V02` §5.4 ("structural rebuild is appropriate", "structural_rebuilds == 1"), §4.5 (adjacency rebuilt on
  topology change), the `RenderMesh` stats tests; AD-018 for V1.
- Tests: every topology op needs an equivalence test "incremental result == full rebuild" (mesh state, buffers,
  undo/redo round trip) - testable headless, like Slices 1 and 2.

## 4. Risks

- H1: a wrong touched set corrupts undo silently - needs a debug mode that compares against a full snapshot.
- V1: buffer capacity / fragmentation, and the pyglet VertexList recreation rules (AD-018).
- Scope: every topology tool reports touched elements - the largest code surface of the three directions.

## 5. Questions for Manu

1. Is "undo as fast as the op" part of the intent (it is what H1 buys over H0)?
2. Order with AD-022: GPU picking and topology in parallel slices, or one after the other?

## 6. Proposed next step (if the direction is accepted)

A spike in `experiments/` before any decision on H1/V1, as for AD-022: H0 + V0 + V2 measured on the topology
probe rows (no Core change, likely ~2x), and a touched-set delta prototype for two ops (Delete, Extrude) to
measure H1 against full snapshots - then this AD is decided with numbers.
