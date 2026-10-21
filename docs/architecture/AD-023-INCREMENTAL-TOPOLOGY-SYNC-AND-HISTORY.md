# AD-023 — Incremental Topology Sync and History

> **IMPLEMENTED in production (2026-10-21)** — see §9. The sections below are the decision history; §9 is the
> current state. Basis for going straight to production: the stage-2 Delete prototype (H1 + V1, measured on the
> reference PC) and Manu's statements of 2026-10-21 (Core changes are a must when they bring a clear gain; engineering
> velocity, AGENTS.md §7a).

**Status:** PROPOSED (2026-10-17), **revised 2026-10-20** after the independent review
[`AD-023_REVIEW_CLAUDE_001`](../archive/viewport_v02/reviews/AD-023_REVIEW_CLAUDE_001.md) (ACCEPT WITH CHANGES; the
disposition of every finding is in §8). Draft for Manu's decision. Not decided; no production code exists. Per
AGENTS.md §5 this document lists alternatives, it does not select one.
**Mode (M5):** Discovery, decision preparation.
**Work package:** WP-TOPO-PERF-01 (proposed name).
**Artist input:** Manu, 2026-10-17: Blender on the reference PC runs "Topologie-Operationen" on 20k gollum
fluidly; incremental topology is "gleich wichtig" as GPU picking ([AD-022](AD-022-GPU-PICKING.md)).
**Artist input (2026-10-20, in chat, recorded by the agent on his instruction):** "flüssig" = "ohne sichtbare
Verzögerung"; in Blender he notices no delay on 20k gollum for Extrude, Split or Knife and estimates "nur wenige ms"
(a feeling, not a measurement). He will not give a millisecond value per operation; he judges by feel in the practical
test. Undo depth: 32 steps "würde erstmal passen". Operations that matter: Knife, Extrude, Connect, Soft Selection,
"letztendlich alle". Morph targets: 20-50 in use, no limit wanted. Topology change after morph targets is a planned
strength, locked for now ([ANIMATION.md](../future_ideas/ANIMATION.md)). The reference PC is the only machine until a modern
one is bought in the coming months ([REFERENCE_HARDWARE](REFERENCE_HARDWARE.md) §3).
Engineering proxies for gating (agent, `PROVISIONAL`, **not Manu's numbers**): a pointer update <= 16.7 ms, a discrete
operation including Undo <= 100 ms.
**Basis (only linked):** [`experiments/drag_cost/README.md`](../../experiments/drag_cost/README.md) ("Topology ops on
the current architecture", "Result: topology operations, reference PC", "GC and history depth, reference PC",
"Haltepunkt"); raw outputs in `experiments/drag_cost/RESULTS_TOPOLOGY_*` and
`experiments/architecture_audit_probes/RESULTS_*`; [CORE_V1_FREEZE](CORE_V1_FREEZE.md) (§7.1 exceptions);
[V1_CORE](V1_CORE.md) §11 and AD-001 (ID continuity, in `src/core/ids.py`); `src/core/operations/topology.py`
(`MeshStateCommand`: full snapshots, and why); [AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md),
[AD-SYM-03](AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md); [`VIEWPORT_V02_ARCHITECTURE.md`](../viewport/VIEWPORT_V02_ARCHITECTURE.md)
§3, §4.5, §5.4, §6, §7; [AD-018](AD-018-PRODUCTION-DRAW-BINDING.md).
**Decided by:** Artist (Intent, Priority) + review; a Core change additionally needs the CORE_V1_FREEZE §7
exception process.

**Tags:** **[RPC]** = measured on the reference PC (Core 2 Quad Q9550, GeForce 9800 GTX, Windows 10, GL 3.3.0,
Python 3.14.2 unless noted). **[C]** = container (Linux, Python 3.13, llvmpipe), not comparable to the reference PC.
*(reading)* = interpretation. Estimates are marked "estimate, not measured".

---

## 1. Problem (measured on `gollum_20k`, 21 875 V)

One topology op as the Artist triggers it (probe `probe_navigation_gl.py --scenarios topology`; reference-PC rows: the
run with the GC on, history depth 20, n = 12, ms p50). The "history" column counts **every** `Mesh.export_state()` /
`load_state()` call plus `history.push` inside the event, **whoever calls it** (the probe's wrapper), so it is
"whole-mesh snapshots (history + op-internal)", not history alone.

| Op | frame total | op itself¹ | whole-mesh snapshots² | hover re-pick | viewport sync | undo frame |
|---|---:|---:|---:|---:|---:|---:|
| Extrude 1 face | 2 770 | 0.8 | 208 | 146 | 2 383 (2 rebuilds) | 1 607 |
| Extrude 20 faces | 3 331 | 66 | 588 | 150 | 2 410 (2 rebuilds) | 1 650 |
| Knife commit (1 cut) | 2 193 | 211 | 471 | 248 | 1 197 | 1 733 |
| Dissolve 1 edge | 1 685 | 30 | 204 | 241 | 1 197 | 1 700 |
| Delete 1 face | 1 602 | 25 | 206 | 148 | 1 204 | 1 626 |

¹ `op = event - history - notify - pick`, so it includes the `after == before` comparison (~6 ms in the review's
container probe) and the selection upkeep. ² Extrude (multi-face) prunes leftover geometry through a whole-mesh
`export_state()` + dict edit + `load_state()` (`extrude.py`), so a multi-face Extrude does 3 exports + 1 load, a
single face 2 exports; the Knife resolver checkpoints with `export_state` and rolls back with `load_state` per bridge
/ run / shape, plus one more export in `check_commit`; its `before` snapshot is taken at session start (the `C`
press), outside the measured Enter. H0 and H1 remove none of the op-internal calls.

**Extrude rebuilds the viewport twice, not three times:** begin marks the topology dirty, the move only patches
vertices, the release marks it dirty again although the commit does not change the mesh (`application.py`
`_extrude_begin`, `_extrude_release`); the "3 syncs" are three frames. Reference-PC sync 2 604 ms ≈ 2 x 1 265 ms.

The same rows over four reference-PC runs (n = 3-12, GC on / off / frozen, history depth 0 / 20): frame within ~10 %,
sync within ~5 %, the snapshot column varies up to ~40 % between runs (Extrude 1 face 206-371 ms, Delete 202-505 ms),
undo within ~18 %. Container (2026-10-17, another container): Delete 792 ms, Extrude 1 face 1 273 ms.

**Where one structural viewport rebuild goes [RPC]** (`probe_topology_sync_split.py`, wall clock, nested; average
1 224 ms over 42 rebuilds, n = 3; later runs 1 242-1 307 ms):

| Part | avg ms | share |
|---|---:|---:|
| `DerivedGeometry.full_recompute` (adjacency + all normals) | 298 | 24 % |
| `RenderMesh._rebuild_index_mapping` (index map + triangulation; `triangulate_mesh_face` ~449 ms, the per-call timer inflates it by an estimated 8-15 %) | 512 | 42 % |
| `RenderMesh._rebuild_resources` (flatten + upload) | 413 | 34 % |
| of which GL store (`update` 65 + `end_rebuild`/VertexList 73 + `allocate` 7) | ~145 | ~12 % |
| of which Python flattening of positions, normals, indices, face rows | ~269 | ~22 % |

About 88 % of one rebuild is whole-mesh Python work, ~12 % is the GL store. The snapshots themselves: `export_state`
~145-160 ms and `load_state` ~415-485 ms per call [RPC]. Shares of a Delete frame [RPC]: viewport sync ~75 %, snapshots
~13 %, hover re-pick ~9 %, op ~2 %. Picking (hover re-pick) is 4-13 % of an operation across the rows.

**Cyclic GC.** The review found in the container that the cyclic GC dominates the snapshot cost (`export_state` 228-234
ms with the GC on, 28-31 ms off) and that the worst case grows with the number of live snapshots. **On the reference PC
(Python 3.14.2) the median does not depend on the GC** (on vs off within ~3 %, also with 20 live undo entries); the GC
adds **tail stalls** (worst sample 12.9 s at Extrude 1 face, otherwise +1-2 s; with the GC off the maximum stays within
~10 % of the median), and `gc.freeze()` makes the median 10-20 % slower. Python 3.12.10 (the PyCharm interpreter) is
**not measured**.

**Memory.** One snapshot of `gollum_20k` is ~31 MB, one undo entry (before + after) ~61 MB [C, tracemalloc]; the stack
has no limit anywhere in `src/`. 32 steps (Manu) are ~2 GB on 20k, ~8 GB on 87.5k *(extrapolated)*; the reference PC has 8 GB.
This argues for H1 independently of speed.

**Scenario limits.** The probe has no symmetry (each symmetric operation adds two full `completeness_report`s with a
`SymmetryIndex`), Soft off (`_soft_preview_refresh` runs on every topology change), the wireframe-edge overlay is
rebuilt per dirty frame when shown (12 ms [C]), the Knife session snapshot at `C` is unmeasured, and the history depth
is ~1 (or the padded 20).

The headless part table of the first draft ("re-triangulate every face 154 ms, all normals 112 ms, ... (profile)") had
no reproducible source and is dropped; use the table above and `experiments/architecture_audit_probes/`
(`probe_mesh_cost.py`, `probe_topology_sync_split.py`).

## 2. Options

### H - history

- **H0 - keep full snapshots, drop the redundant work (no Core change).** `MeshStateCommand` is a plain
  `undo()/redo()` object; a `mirai`-level command with the same protocol can take the "after" snapshot lazily and decide
  "changed?" from the op's own result instead of `after == before`. Saves one `export_state` per op that is never
  undone (~145-160 ms [RPC]); **the export moves to the first Undo** (Undo gets slower by one export, Redo needs it).
  Undo still pays `load_state`. Needs a replacement "changed?" signal per op (the Knife uses `mesh_content` without counters
  because counters advance after an internal rollback).
- **H1 - delta entries (Core change).** The op reports the elements it touched; the entry stores their before/after
  records and undo restores just those. The entry must meet the **exactness contract** below. Needs a Core API to
  export / apply a partial state - a CORE_V1_FREEZE §7 exception like the §7.1 entries for `split_face` and
  Delete/Dissolve (V1_CORE §11 left the mechanism - "structural diffs, hybrid" - open, which supports its legitimacy);
  touched sets for every op. Capture mechanism is an open design point (§7): a recording proxy cannot see what
  `delete_faces` removes internally, a Core hook is a Core change, a diff needs the full snapshot. Snapshot and delta
  entries can coexist on one `HistoryStack` (it needs only the `Command` protocol) as long as each is exact, which
  allows a staged migration. Expected: snapshots and undo from ~0.2-0.9 s to ms (estimate, not measured; the snapshot
  share of a Delete frame is ~13 % [RPC], so H1 alone does not make an op or an Undo fast).
  - **Exactness contract (what the snapshot guarantees today):** (1) ID counters stay **forward** on Undo
    (`load_state` never lowers a counter, AD-001); the delta must leave counters alone, not restore them; (2) the
    symmetry definition rides in the state (AD-SYM-01 / AD-SYM-02 §5) and must be carried explicitly; (3) order inside
    records: `edge.faces` list order is used semantically (Loop Slide's `side_a, side_b`), face-boundary rotation decides
    the triangulation fan; (4) dict iteration order of `all_*_ids()` feeds the buffer layout, `triangle_faces`, pick
    tie-breaks and saved files: preserve it, or declare it not part of "exact" and make every consumer order-free;
    (5) rollback and abort paths (`_mesh_transaction`'s restore, Extrude cancel, Knife refusal and `check_commit`,
    symmetric refusals, Loop Slide abort) all use `load_state`: say whether `before` is still taken for rollback (then H1
    saves only the after-snapshot and the undo load) or ops become transactional; (6) the "changed?" signal.
    The equivalence test compares unsorted records, iteration order (or documents the exemption), the symmetry
    definition and the counters.
- **H2 - structural sharing in `Mesh` (Core internals).** Copy-on-write snapshots keep every snapshot cheap in time and
  memory without per-op touched sets; the largest Core change (every container is a dict of dataclasses), no measured
  gain, listed for completeness. Dropped from consideration unless H1's capture problem proves unsolvable.

### G - cyclic GC control (no contract change)

Pause or raise the thresholds of the GC around snapshot-heavy work, or around `_mesh_transaction` and `load_state`
callers. **Measured [RPC]: no gain at the median; it would remove tail stalls of 1-12 s.** `gc.freeze()` after
set-up is slower (median +10-20 %) and is not pursued. Risk: memory held longer; behaviour depends on the Python
version (3.12 not measured). A cheap option for the tails, not for the median.

### V - viewport topology sync

Ranked by the reference-PC split (§1): ~60-65 % of one rebuild is normals + triangulation, ~22 % Python flattening, ~12 % GL.

- **V0 - cache per-face triangulation and normals (no contract change).** `RenderMesh` keeps the triangles per face; a
  topology change re-triangulates only faces whose boundary **or positions** changed, normals only around changed
  vertices (`vertex_to_faces`, §4.5). **Cache key and rule:** triangulation depends on positions (convex faces get the
  fan, concave ones ear clipping, `derived.py`), and a W drag does not re-triangulate; a cache keyed on boundaries
  alone would keep the old triangulation of a quad a W drag made concave, so "incremental == full rebuild" fails
  unless the key includes convexity or V0 re-triangulates faces whose vertices moved since caching. Buffers are
  still rebuilt whole. Expected: the 24 % + ~37 % parts shrink (estimate, not measured).
- **V1 - incremental buffers (AD-018 addendum).** Patch positions / indices / face rows for the touched range, with
  spare capacity so an op that adds a few faces does not recreate the VertexList. Needs touched sets (shared with H1)
  and a `ResourceStore` patch contract for index data. **Constraint:** the index order and `triangle_faces` (per
  triangle, its face row, read through `gl_PrimitiveID`) must stay consistent; spare capacity means degenerate
  triangles that still need a row; [AD-022](AD-022-GPU-PICKING.md) B2 reads the same mapping. V1 inverts the tests
  that require new resource IDs after a topology change (below).
- **V2 - one rebuild per gesture.** Extrude's two rebuilds (begin, release) become one plus vertex patches (the release
  rebuild is not needed when the commit changes nothing); saves one rebuild (~1.2 s on 20k [RPC]). Small, independent.
- **V3 - cheaper full rebuild, no contract change.** `_positions_flat` / `_normals_flat` sort all V per rebuild,
  indices go int → float → int, attributes are copied into tuples. The Python flattening is ~22 % of a rebuild [RPC]; the
  GL store only ~12 %, which is less than the review's reading (a store/upload cost) suggested. Cheap, benefits every op
  and every Undo; to be ranked next to V0.

### U - undo path

Today every mesh Undo marks the topology dirty, because `HistoryStack` does not expose the undone command
(`application.py` `_undo_redo`, comment E23; AD-SYM-03 §2.2 T-d): even Undo of a one-vertex **W move** pays a full
structural rebuild (433 ms in the review's container probe). Undo frame on the reference PC: 1.6-2.0 s ≈ one rebuild
+ `load_state` + pick cache. So H1 alone does not make Undo fast; V0 / V1 on the undo path do. V1 on Undo needs the
entry's touched set: options (a) the selection-mirror stack, which already runs 1:1 with the pushes
(`_record_selection_history`), carries it; (b) a `HistoryStack` accessor (frozen Core); (c) keep the full rebuild.
The W-undo cost has a separate, cheaper win (the mirror entry could say "positions only").

### P - pick cache

`vertex_faces` and the screen positions per touched element instead of a full rebuild. Moot for the window only for hover
and click if [AD-022](AD-022-GPU-PICKING.md) is decided; `PickCache` stays for the Knife's exact math, the Knife planner
and the headless path.

### N - native code or NumPy

Not a dependency today (`requirements-dev.txt`). Recorded reason so far: instruction-set risk on the Core 2
(REFERENCE_HARDWARE §2). Measured 2026-10-20 [RPC]: NumPy 2.5.4 under Python 3.14.2 does not import (x86-64-v2); NumPy
2.2.6 under Python 3.12.10 imports (no timing). *(reading)* Not pursued here because the dominant cost is a Python-object mesh
(dicts of dataclasses), not arithmetic that a vector library accelerates; to be revisited only with a measurement.

## 3. What it touches

- `src/core` (frozen): H1 / H2 need a partial state API or internal changes - CORE_V1_FREEZE §7 exception with contract
  tests (the §7.1 entries for `split_face` and Delete/Dissolve have `MeshStateCommand` round-trip contract tests; AD-014 is
  accepted but not recorded in §7.1, a gap in the freeze document); H0 / V0 / V2 / V3 / G do not touch the Core.
- AD-001 (ID continuity): H1 must meet the exactness contract (§2); the snapshot rationale in
  `operations/topology.py` is the constraint to meet, not to drop. AD-SYM-01 (definition in the state).
- AD-SYM-02 / AD-SYM-03: one gesture = one history entry, symmetric ops through `_mesh_transaction` - unchanged in shape,
  the entry type changes.
- AD-013 H2 addendum (`apply_mesh_change`, the external-host entry: its `mutate` would have to report touched sets, a host
  contract change); AD-021 §4.6 (Apply transform: one `MeshStateCommand` per object inside a `CompositeCommand`); Loop Slide
  (positions only, full snapshots); other `MeshStateCommand` users outside `src/`: `playground/topology_ops.py`,
  `playground/topology_tools/{loop_slide,connect_edges}.py`, `experiments/symmetry_lab/lab_resymmetrize.py`, the Knife Face Lab.
- `VIEWPORT_V02`: §3 invariant "Topology changes may trigger larger rebuilds", §4.5 (adjacency rebuilt on topology
  change), §5.4 ("structural rebuild is appropriate"; the counter clause "structural_rebuilds == 1" is already not what
  the code counts: `render_mesh.py` counts once per recreated resource plus once per sync), §6 table row "Full rebuild
  (~50-100 ms) - rare, explicit" (both the cost and "rare" are contradicted by 1.2 s [RPC]), §7 "Topology update (allowed
  exception) ... OK to recreate".
- AD-018 for V1; the tests that **require** new resource IDs after a topology change (`tests/test_render_mesh.py`,
  `tests/test_benchmark_scenarios.py`) - V1 inverts them, and AD-018 §5 says a test that must change is a finding, not
  a silent fix; the H7 surface providers (`viewport.py`, `tests/test_viewport_surface_provider.py`), which follow topology
  notifications.
- Tests: every topology op needs an equivalence test "incremental result == full rebuild" (mesh state, buffers, undo/redo
  round trip) - testable headless, like Slices 1 and 2 - **plus** property-style tests as a standing guard (random op
  sequences, undo/redo to the start, compare with snapshots), because the debug compare costs a full snapshot and cannot
  run in normal use.

## 4. Risks

- H1: a wrong touched set corrupts undo silently - a debug mode that compares against a full snapshot, and the property
  tests of §3. A half-applied Undo if applying a delta raises (the snapshot has no such state).
- Maintenance: every future op must report a correct touched set; a forgotten element is silent. The AD-SYM-03 "future ops"
  pattern (declaration + gate) is the precedent to copy.
- Memory: the unbounded snapshot stack (§1) - an argument for H1 independent of speed, and it weighs against H0's lazy
  after-snapshot.
- GC tails (§1): occasional multi-second stalls with the GC on, growing with history depth in the container.
- V1: buffer capacity / fragmentation, the pyglet VertexList recreation rules (AD-018), the ordering constraint (§2).
- Scope: every topology tool reports touched elements - the largest code surface of the three directions; staged migration
  (snapshot and delta entries coexist) lowers it.

## 5. Coupling with AD-022

The goal of this AD (op and Undo fast) is the same as what B2 of [AD-022](AD-022-GPU-PICKING.md) reads from; the hover
re-pick column (4-13 % [RPC]) changes with AD-022, so "AD-022 does not change this table" (first draft) was wrong.

| AD-022 variant | effect on this AD |
|---|---|
| B1 (own ID buffers) | adds ~0.8 s (20k [RPC]) to every op and every Undo, a rebuild after each topology op |
| B2 (from the `RenderMesh` buffers) | V1's index patching and B2's `gl_PrimitiveID` mapping are **one contract** (index buffer, triangle → face-row map, a new edge index buffer, spare or dead triangles): decide together |
| A (world index) | a 0.65 s rebuild per op unless fed by touched sets |
| P | "moot" only for hover / click in the window; `PickCache` stays for the Knife and the headless path |

Independent of AD-022: H0 / H1 / G (history) and V0 / V2 / V3. Decided together: the AD-018 buffer contract, B1 vs B2, and the
sync / hover ordering (V2).

## 6. Questions for Manu

Answered 2026-10-20 (see the header): what "flüssig" means (feel, no ms per operation), the Undo depth (32), the operations
that matter (Knife, Extrude, Connect, Soft Selection, all), the reference-PC role.

1. Should Undo on 20k be as fast as the operation itself? (Today ~1.7 s on your PC, also after a simple W move; H1 alone does
   not change that, V0 / V1 on the undo path do.) **Manu, 2026-10-20: yes, Undo as fast as the operation** (chosen in the
   agent session, recorded by the agent on his instruction).
2. A quick partial win first (a cheap stage 1: V2, V3, V0, H0), or wait for the full solution? **Manu, 2026-10-20: stage 1
   first** (same session, same instruction).
3. Order with AD-022: decided together, in parallel slices, or one after the other? (Open.)

Stage 1 result (2026-10-21): measured on the reference PC (op + Undo roughly halved, e.g. Delete 3.7 → 2.0 s;
[experiment README](../../experiments/topology_sync_stage1/README.md)). **Manu, 2026-10-21 (chat, with the raw output,
instruction):** "vielleicht minimal schneller, das zeigen auch die Messungen. Trotzdem viel zu langsam um vernünftig
arbeiten zu können." → the §7 decision point is missed; stage 2 is indicated. **On Core changes (same message):** "core
freeze bedeutet nicht, dass er nicht verändert werden darf. Bringen uns Veränderungen am Core einen deutlichen Gewinn,
sind Core-Änderungen ein Muss." The CORE_V1_FREEZE §7 steps (requirement, contract tests) still apply; whether a Core
change is wanted is no longer the open question.

## 7. Proposed next step (staged, if the direction is accepted)

Success lines are Manu's feel in the practical test; the proxies of the header (16.7 ms pointer update, 100 ms discrete
operation including Undo, `PROVISIONAL`) gate the engineering steps.

- **Stage 1 (no Core change, cheap):** V2 + V3 + V0 + H0 (G only if the tails matter), measured on the reference PC with
  n >= 10 and p95 (the probe prints p50 and max today: extend it), history depth 1 and ~20, GC on / off, under the Python
  the Artist actually uses. Decision point: if op and Undo on `gollum_20k` feel "sofort" to Manu, stop; H1 / V1 are not needed.
  Prototype (experiment, `src/` unchanged): [`experiments/topology_sync_stage1/`](../../experiments/topology_sync_stage1/README.md),
  every switch separately, equivalence tests, a probe with p95, `run.py` for the practical test. H0 shifts one `export_state`
  from the op into the Undo, which runs against answer 1 of §6; it is measured as a switch, not assumed.
- **Stage 2 (only if stage 1 misses):** a touched-set prototype for Delete, Extrude **and** Knife (or Dissolve with
  cleanup) plus one symmetric op (the hard ones: Knife's resolver checkpoints and `integrity_problem`, region merges,
  symmetric coordinators with rollback to `session_before`), with the capture mechanism stated and the exactness contract
  as the test oracle on every sample (randomised op sequences with undo/redo).
  Prototype for Delete only, **together with AD-022 B2-out** (2026-10-21, experiment, `src/` unchanged):
  [`experiments/topology_stage2_delete/`](../../experiments/topology_stage2_delete/README.md). Capture mechanism:
  declared neighbourhood + local diff (no full snapshot, no Core hook; a per-op "mutates nothing outside" contract),
  exactness contract met incl. container order; V1 slot rule (dead triangles degenerate, revived on Undo) shared with
  B2's `gl_PrimitiveID` mapping; pick synced before it reads. Container [C], Delete 1 face frame / Undo: `stage1`
  333 / 1 167 ms, `H1,V1` 103 / 89 ms, with GPU picking 41 / 32 ms; B2 face mapping exact per pixel (llvmpipe).
  **Reference PC (2026-10-21) [RPC]**, p50 frame / Undo: Delete 1 face `none` 1 687 / 1 781, `stage1` 667 / 1 116,
  `H1,V1` 171 / 160, with GPU picking **35 / 19 ms** (op + Undo 54 ms); Delete 20 faces 42 / 55, Delete 1 vertex
  54 / 50 (their Undo p95 ~135 ms: the exact-order rebuild of `_vertices` / `_edges` plus a GC pass). B2 face mapping
  exact on the reference driver. Left whole-mesh: the exact-order Undo rebuild, the Core delete's own edge scan
  (19-25 ms), vertex Delete's `vertex_edges` (no vertex → edge index). **Manu, 2026-10-21 (chat, with the raw output,
  recorded by the agent):** „Die Messungen zeigen deutlich, UNDO und Delete fühlen sich sehr viel schneller an.“ Not shown:
  ops that create elements (Extrude, Knife, Connect), symmetric ops.
- **Abort rule:** stop H1 if any op needs whole-mesh work to compute its touched set, or if the debug compare finds a
  mismatch that is a contract gap rather than a prototype bug.

## 8. Review disposition (CLAUDE-001, 2026-10-20)

| Finding | Disposition |
|---|---|
| B-1 history column mis-attributed; GC; Extrude twice (blocker) | Accepted. §1 relabelled with per-row notes; GC measured on the reference PC (median independent, tails) and option G added with that result; Extrude corrected to two rebuilds, V2 saves one. |
| B-2 the spike cannot decide (blocker) | Accepted. §7 rewritten as stage 1 / stage 2 with an abort rule and a stated capture mechanism problem. |
| M-1 exactness contract | Accepted. §2 H1 "Exactness contract" (six points) and the test oracle. |
| M-2 mutation-path inventory | Accepted. §3; staged migration (snapshot and delta entries coexist). |
| M-3 Undo path | Accepted. §2 U. |
| M-4 V0 equivalence, V1 ordering | Accepted. §2 V0 cache key rule, V1 constraint. |
| M-5 "what it touches" | Accepted. §3. |
| M-6 risks and alternatives | Accepted. §1 memory, §4, §2 G / V3 / N. |
| M-7 AD-022 interaction | Accepted. §5; the AD-022 text carries the matching correction. |
| m-1 part table without source | Dropped the table; the reproducible probes are named. |
| m-2 picking share | Quoted as 4-13 % [RPC]. |
| m-3 "op itself" definition | Footnote 1. |
| m-4 scenario limits | §1 "Scenario limits". |
| m-5 H0 lazy snapshot | §2 H0. |
| m-6 H2 | §2 H2, one line each for cost and risk. |
| m-7 language | The reference-PC paragraph is English. |
| Artist questions | §6; the answered ones are in the header. |

The reviewer's request for a reference-PC rerun with `--profile-top 15` and a GC-off variant: `--profile-top` does not
profile the `topology` scenario; the equivalent is `probe_topology_sync_split.py` (`--gc`, `--history-depth`), run 2026-10-20.

## 9. Implementation (2026-10-21, production)

**Direction taken: H1 + V1 + incremental pick cache, for every operation at once**, through one Core mechanism instead
of per-operation touched sets (this removes the main H1 risk of §4, "every future op must report a correct touched set").

- **Capture mechanism: a Core change journal** (`src/core/mesh.py`). Every `Mesh` mutation records, on first touch, the
  before-record of each element it changes in every active `MeshChange`: `begin_change()` → `end_change()` (net
  `MeshDelta`, only elements whose record differs) or `rollback_change()` / `revert_change()`; `MeshWatch` (`Mesh.watch()`)
  is a persistent journal for derived data. `load_state()` under a journal writes only the differing elements.
  A Core vertex → edge index replaces the O(E) scans (`vertex_edges`, `_delete_region`, `collapse_edge`, Dissolve planning).
- **Exactness contract (§2 H1)**, as met: (1) counters never part of a delta (forward only); (2) the symmetry definition
  is a journaled property and rides in the delta; (3) records keep boundary rotation and `edge.faces` order; (4) the three
  containers are kept in **ascending ID order** as a Core invariant (IDs are appended monotonically; `load_state` and
  `apply_delta` restore the order, resorting without per-entry tuples); `vertex_edges` returns ascending IDs = the old scan
  order; (5) rollback is the journal (no `before` snapshot anywhere in `src/`); (6) "changed?" = non-empty delta.
- **History:** `MeshDeltaCommand` replaces `MeshStateCommand` at every `src/` site (`Application._mesh_transaction`, Apply
  transform, Loop Slide, Extrude tool, Knife commit, the scene-level helpers). The Knife records its session start at commit
  (`SessionStart`, no snapshot at `C`); resolver checkpoints are journal recordings. `MeshStateCommand` stays for other users.
- **Viewport (V1 + V0 + V2 + U):** `RenderMesh` watches its mesh; a topology sync patches the slots the journal reports
  (slot rule as in the prototype: dead triangles degenerate, dead vertices `DEAD_POSITION`; spare capacity
  `SPARE_FRACTION` for growth; triangulation re-done for new / changed faces and faces around moved vertices). Full rebuild
  only on first build, exhausted capacity, changes above `PATCH_MAX_FRACTION`, and meshes below `INCREMENTAL_MIN_ELEMENTS`
  (compact layout). `GLRenderStore` patches index ranges. Undo/Redo take the same path (no `HistoryStack` accessor needed).
- **Pick cache (P):** `PickCache` watches its mesh and re-projects only touched vertices / faces and patches `vertex_faces`.
- **Tests:** `tests/test_mesh_change_journal.py` (randomised sequences over every mutation, undo/redo to the start and back
  against the snapshot oracle incl. order, nested rollback, watch), `tests/test_render_mesh_incremental.py` (patched buffers
  == fresh build per element, random ops with undo/redo), `tests/test_gl_render_mesh_incremental.py` (same image as a fresh
  build in GL). Mutation checks by hand: a missing touch, no resort, no re-triangulation around moved vertices, no GL index
  patch — each fails its test.
- **Measured [C]** (container, `probe_navigation_gl.py --scenarios topology`, gollum_20k, p50 frame / undo frame, ms;
  raw: [`RESULTS_TOPOLOGY_JOURNAL_CONTAINER_2026-10-21.md`](../../experiments/drag_cost/RESULTS_TOPOLOGY_JOURNAL_CONTAINER_2026-10-21.md)):
  Extrude 1 face 1 610 / 1 068 → **36 / 16**; Extrude 20 faces 2 046 / 952 → **41 / 26**; Knife commit 1 397 / 1 431 →
  **67 / 29**; Dissolve 1 edge 973 / 1 224 → **54 / 44**; Delete 1 face 970 / 1 219 → **18 / 17**. **Not measured on the
  reference PC yet**; the stage-2 Delete prototype ran ~2x the container's Python time there, which would put these rows
  roughly at 35-140 ms (estimate, not measured).
- **Left (whole-mesh or open):** first hover / click after a camera change and Box select still use the CPU `PickCache`
  re-projection and occlusion scans (AD-022's part, next step); edge-mode hover is a linear scan; the wire overlay
  (`Shift+D`) is rebuilt whole per dirty frame (E39), also during a W drag; symmetric ops still run whole-mesh symmetry
  reports (`SymmetryIndex`, `completeness_report`); Soft preview refresh per topology change not profiled.

- **Manu, 2026-10-21 (verdict table below):** operations + Undo on gollum_20k "ohne sichtbare Verzögerung", nothing
  looks different. Still slow: **Move / Rotate / Scale on a very large selection, above all with Soft Selection**, and
  the **Knife** compared with the rest — the next targets (the transform drag path and the Knife's per-camera
  projection, AD-022 §11 "Open").

### Praxistest für Manu (ca. 10 Minuten + ein Messlauf)

Die technische Korrektheit ist durch Tests belegt (Undo/Redo exakt, Bild gleich einem vollen Neuaufbau). Offen ist nur,
was dein PC und dein Gefühl zeigen:

- **Fühlen:** `python src/main.py`, `Leertaste` → `gollum_20k` laden. Extrude (`T`), Knife (`C`, Klicks, `Enter`),
  Connect/Split (`C` mit Auswahl), Delete/Dissolve (`Entf`/Rücktaste), Loop einfügen/gleiten (`I`/`G`), jeweils mit
  mehrfachem `Strg+Z`/`Strg+Y`. Frage: **ohne sichtbare Verzögerung?** Sieht nach einer Operation oder einem Undo
  irgendetwas anders aus als erwartet (Schattierung, Löcher, Auswahl)?
- **Messen (PowerShell im Repo-Ordner, ganze Ausgabe kopieren):**
  `python experiments\drag_cost\probe_navigation_gl.py --scenarios topology --assets examples\meshes\gollum_20k.obj`
- Nicht Teil dieses Tests: Hover direkt nach einer Kameradrehung und Box-Auswahl (das ist GPU-Picking, AD-022, der
  nächste Schritt).

| Frage | Dein Verdikt                                                                                                                                                                                                  |
|---|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Operationen + Undo auf gollum_20k ohne sichtbare Verzögerung? | ja,was noch etwas langsam wirkt sind : Move, Rotate; Scale auf eine sehr große Auswahl an Vertices, Faces oder Edges, vor allem in Kombination mit Soft Selection. Knife tool wirkt noch langsam im Vergleich |
| Etwas anders als vorher (Aussehen, Auswahl nach Undo)? | nein                                                                                                                                                                                                          |
