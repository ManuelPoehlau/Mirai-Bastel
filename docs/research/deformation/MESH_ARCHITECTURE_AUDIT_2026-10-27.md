# Mesh Architecture Audit — Morphing, Rigging and Topology Edits After Morph Targets

**Status:** Discovery, plan only — no decision. First-pass record of the audit as delivered on 2026-10-27 (AGENTS.md §6:
not edited afterwards to agree with later decisions). What changed since is in the dated addenda at the end.
**State audited:** `da6d302` (branch `ccr-cc7c6026-szqyt4`, clean tree); no repository file was changed by the audit.
Two read-only probes ran outside the repository (container timings and memory, numbers below).
**Labels:** **[RPC]** measured on the reference PC (from repo documents) · **[C]** measured in the container for this
audit (Python ≈ 2× slower on the reference PC, REFERENCE_HARDWARE §2) · **[H]** estimate/extrapolation · **[V]**
verified in code or tests during the audit.
**Builds on:** the 2026-10-20 future-requirements audit
([ARCHITECTURE_AUDIT_2026-10-20_FUTURE_REQUIREMENTS.md](../viewport/ARCHITECTURE_AUDIT_2026-10-20_FUTURE_REQUIREMENTS.md)).
Its gaps K4/K6/K7 are closed since 2026-10-21 (journal, delta Undo, incremental viewport); K3 (provenance), K5
(attributes) and K10/K11 (evaluation chain) are still open. Its probes are not repeated here.
**Gate:** input to ROADMAP ARCH-02 (Topology Identity / Provenance / Remapping); artist decisions in §H.

---

## A. Executive summary

**Is the current mesh structure a suitable foundation?** Yes. Mirai stores points (ID + position), edges ("point A –
point B" plus the faces on each side) and faces (an ordered ring of point IDs). IDs are never reused. Since 2026-10-21
every edit writes a "before" record of each touched element into a change journal, which gives exact, fast Undo, exact
rollback when a tool cancels, and lets the viewport patch only what changed. Stable IDs, exact undo and knowing exactly
what changed are the hard prerequisites for keeping deformation data alive through edits — they are in place and tested.

**Its real limitations** (measured or seen in code, not theoretical):

1. **It knows *what* changed, not *where new points came from*.** When a loop cut creates a point 50 % of the way
   between A and B, nothing keeps that fact once the tool is done. Without it, a morph target cannot give the new point
   a correct offset except by guessing from geometry (rated "medium reliability" by the 2026-08 rigging research,
   `docs/archive/experiments_2026-10/rigging-skinning-morphing/FINDINGS-3AB.md`).
2. **No storage for per-point deformation data** (morph offsets, skin weights) that rides Undo, Knife rollbacks and the
   file cheaply. The Morph Lab keeps each target as a full mesh copy: **52 MiB per target at 20k points, 207 MiB at
   87.5k [C]** — 20–50 targets (Manu, AD-023 header) would need 2.6–10 GB on an 8 GB reference PC. A packed offset per
   target is **0.25 MiB / 1 MiB [C]**.
3. **The viewport has one "replacement surface" slot** (AD-013 H7). SubD now uses it in Production, so morphs and SubD
   cannot show together, and SubD reads undeformed positions.
4. **The speed limit for sliders is per-point Python work in the display, not the mesh structure.** Moving 3,339 points
   costs ~91 ms per mouse step [RPC]
   ([RESULTS_DRAG_BATCHED_REFERENCE_PC_2026-10-21](../../../experiments/drag_cost/RESULTS_DRAG_BATCHED_REFERENCE_PC_2026-10-21.md));
   the morph arithmetic itself is small (one target, every point of 20k: 4.6 ms [C]).

**Is a data-structure redesign (Half-Edge) justified now?** No. Topology lookups are already fast (a split costs
0.018 ms at any mesh size [C]; walking every point's neighbours on 87.5k points 180 ms total [C]); none of the four
limitations above is fixed by Half-Edge; a migration would rewrite the 1,695-line `mesh.py`, every tool, and re-prove
~3,000 test functions plus the 351-test Knife oracle — for no measured gain. One small internal fix is justified:
`collapse_edge` scans every face (2 ms at 20k, 8 ms at 87.5k per call [C]).

**Decide before production morphing:**

1. **Where morph data lives:** offsets keyed by the base mesh's point IDs, stored in the mesh and journaled per point —
   not mesh copies.
2. **The topology rule while targets exist** (artist decision H1).
3. **The "where did this point come from" contract (ARCH-02), written down**, so locking now does not block the planned
   strength later (Manu 2026-10-20, ANIMATION.md item 5).
4. **How evaluated (deformed) geometry reaches the viewport and SubD:** a chain of stages instead of one slot.

---

## B. Current-state evidence

Status: **P** = Production, verified in code + tests during the audit · **L** = Lab only · **D** = documented, not
implemented · **O** = proposed/open.

| Capability | Where | Status | Evidence | Remaining limitation |
|---|---|---|---|---|
| Points / edges / faces, adjacency | `src/core/mesh.py` | P | `tests/mesh_invariants.py` (≤ 2 faces per edge, no repeated point in a face) | No point→face index (derived via point→edge, fine); `collapse_edge` scans all faces (`mesh.py:674` at `da6d302`) |
| Stable IDs | `src/core/ids.py` | P | Monotonic, never reused, counters forward on Undo (AD-001) | Per mesh; across objects `(ObjectId, ElementId)` (AD-021) |
| Base vs. evaluated positions | `mesh.py` contract (positions only via `vertex_position()`), AD-021 §4.9 | D | Principle decided: mesh = rest shape; chain morph → skin → SubD derived, never saved | No chain; only the H7 display slot, one provider (AD-013 H7-R4) |
| Change journal, delta, rollback, watch | `mesh.py` (`begin_change` … `watch`) | P | `tests/test_mesh_change_journal.py`: random sequences over every primitive, undo/redo vs. snapshot oracle — passed | Records before-state only; **no origin, no operation parameters** |
| Undo / Redo | `MeshDeltaCommand`, `HistoryStack` | P | Exact, O(changed) | No depth limit (entries now small) |
| File | `serialization.py` v4, `Mesh.export_state` (`symmetry`, `face_regions`) | P | Round-trip tests | `morph_targets`, `rig`, `animation` reserved, always `null` |
| Saved regions following edits | `mesh.face_regions`, `src/mirai/regions.py` (Slice 3) | P | `tests/test_region_inheritance.py` passed; rule inferred from the journal, fail-closed | Inference, faces only; hooks needed in 3 places (`_mesh_transaction`, Extrude commit, Knife `SessionStart.finish`) |
| Mask / Hide | `src/mirai/mask.py`, `hidden.py` | P | Session state, not mesh data | Not in file or Undo (by design) |
| Topology origin information | Scattered: `split_edge(e, t)` / `split_face` arguments; Knife `KeptSplitEdge` / `KeptSplitFace` (`knife_resolve.py`); Connect returns `{edge: midpoint}`; Extrude `_old_to_new`, `_face_source` | P (fragments) | Knife record drives the symmetric replay | No common contract; discarded at commit; Extrude's point map never exposed; ARCH-02 open |
| Morph targets | `experiments/morph_lab/`, `src/morph_bridge.py` (key M) | L | 4 points KEEP (2026-10-17); **Lab does not start at `da6d302`** (below) | Target = full mesh copy; weight is view state only; any topology change switches the morph off; "relative" reference only per session |
| Skinning / rig | none in code; AD-005 (doc only); Lab jaw pose (hard weights, 3-ring falloff) | D | `grep`: no skin or bone code in `src/` | Everything |
| SubD | `src/mirai/subdivision/` | P | Reads the journal; position-only edits through stencils locally | Holds the single H7 slot; reads base positions, not deformed ones |
| Topology op speed | journal + incremental viewport (AD-023 §9) | P | Manu 2026-10-21 [RPC]: "ohne sichtbare Verzögerung" | Large selections still slow: 91 ms per step at 3,339 points [RPC] |

**Test state at `da6d302` (run during the audit):**
- `tests/`: 4,787 passed, **2 failed**, 114 skipped (GL tests inside a combined run, not re-run in their own process).
  `test_knife_resolve.py::…import_no_viewport…` — the region-inheritance commit made the Knife resolver import
  `..regions`, breaking its pinned import boundary. `test_symmetric_transform.py::…switches_symmetry_only_through_its_command`
  — the symmetry display toggle (2026-10-24) was not added to the pinned method list; unrelated to morphing.
- `experiments/morph_lab/tests`: 19 passed, 2 failed, 26 errors — all `LabBindingConflict`: the Lab's `B` collides with
  Border Select (`864c39b`, 2026-10-25). Bare `pytest` (which includes the Morph Lab) is red.

**Where docs contradict code (at `da6d302`):**
- **AD-005** (Rigging) says "DECIDED", but its owner sign-off reads "Manu — TBD"; it describes a Mesh API that never
  existed, puts bones on the Mesh (AD-021 §4.9 puts the rig on the Scene), and its morph rule (a new point copies its
  parent's offset) is wrong for edge splits, which need a blend of both ends. Its experiment was removed on 2026-10-24.
  Treat as superseded by AD-021 §4.9 + ARCH-02.
- `docs/architecture/README.md` says AD-REGIONS-01 has "no automatic inheritance yet" — Slice 3 shipped.
- ATELIER B10 says the Morph Lab does not start because of arrow keys (since 10-23); the keys moved on 10-24, the
  current cause is `B`.
- `core/operations/topology.py` still calls snapshots "die einzige Möglichkeit" for exact IDs, and `history.py` points
  to `MeshStateCommand` — both superseded by the journal.
- `CORE_V1_FREEZE.md` §4 still lists a "generisches Change-Set-System" as outside the Core — it is in the Core
  (authorized in §7.1).
- `CHARACTER_SYSTEMS_RESEARCH.md` sends "topology under active deformation" to the rigging experiment, which no longer
  exists; the topic's only home is ARCH-02.

**Container measurements for this audit [C]** (Python 3.13; `head_basemesh` 326 V, `gollum_20k` 21,875 V, `gollum`
87,500 V):

| Measurement | 20k | 87.5k |
|---|---:|---:|
| `split_edge` + journal, p50 | 0.018 ms | 0.018 ms |
| `collapse_edge` + journal, p50 | 1.97 ms | 8.16 ms |
| one-ring faces of every point (`vertex_edges` + `edge_faces`) | 25 ms | 180 ms |
| `export_state` (full snapshot) | 109 ms | 813 ms |
| morph sum, 1 target, all points / 15 % of points | 4.6 / 0.9 ms | 22.9 / 5.0 ms |
| morph sum, 10 targets, all / 15 % | 27 / 4.2 ms | 111 / 19.5 ms |
| morph sum, 50 targets, all / 15 % | 126 / 19 ms | 627 / 86 ms |
| memory: one full `Mesh` copy (Lab target) | 51.9 MiB | 207.3 MiB |
| memory: one target as dense offset dict / packed `float32` | 3.09 / 0.25 MiB | 12.34 / 1.00 MiB |

---

## C. Architecture alternatives

| | 1. Extend as-is | 2. Targeted additions (recommended) | 3. Half-Edge / BMesh-style |
|---|---|---|---|
| What changes | Morph/skin data outside the mesh; tools report origins ad hoc | Same topology structure + per-point data layers journaled in the Mesh, origin rule applied inside each topology primitive, a whole-mesh-transform rule, an operation gate, a chain of evaluation stages | New internal topology; all 12+ primitives and tools rewritten |
| Correctness | Weak: data outside the journal desynchronises on Knife checkpoints, Extrude cancel, Undo (the AD-REGIONS-01 §1.2 argument); every new tool must remember to report | Strong: values roll back with the same journal already tested against a snapshot oracle | Same goal; the origin problem is not solved by the structure itself |
| Risk | Low now, rising per tool | Medium: Core change under CORE_V1_FREEZE §7 | High: exact ID continuity, element order (Loop Slide reads `edge.faces` order), Knife golden tests all re-proven |
| Performance | Unchanged | A layer write = one record per touched point (to be measured) | No measured gain — the measured costs are display and evaluation |
| Migration effort | None | One Core extension + ≈ 6 commit boundaries | Very large |
| Flexibility | Low | Same mechanism later carries skin weights and UV corners (corner = face + point, unique by invariant) | High in theory |

**What Half-Edge would buy Mirai:** constant-time ordered walks around a point (derivable today in O(valence)), a
native corner domain for UVs (possible today because no face repeats a point), easier non-manifold handling (Mirai's
invariants forbid non-manifold edges). None of these is a measured bottleneck, and AD-002 keeps the door open to swap
internals later without breaking the query API. **Revisit only** if UV/corner tools or retopology strip tools show a
measured traversal cost. **Recommendation: option 2.**

---

## D. Topology-change contract

All operations below already run inside one journal recording with exact rollback on error [V] (`_mesh_transaction`,
Extrude cancel, Knife `SessionStart.abandon`, nested rollback in Collapse).

| Operation | Keeps IDs | Creates / deletes | Origin info today | Per-point data needs |
|---|---|---|---|---|
| Split edge at t (Split, Connect Edges, Loop Insert t = 0.5, Knife on edges) | both ends, both faces (boundary grows) | +1 point, +2 edges / −1 edge | `(edge, t)` in the call; the journal has the removed edge's ends but not t | new point = blend of the two ends at t |
| Split face (Knife interior points) / connect points | all boundary points and edges | −1 face, +2 faces, +k points, +k+1 edges (k = 0 for Connect) | parent face + path positions in the call; Knife keeps `KeptSplitFace` until commit | k > 0: weights over the parent face's corners (mean-value coordinates); k = 0: nothing |
| Extrude (tool builds faces itself) | everything outside the region | +1 copy per region point, walls, caps / region faces, inner edges and points | tool-internal `_old_to_new`; only face sources are passed on (to regions) | new point copies its source point |
| Collapse (groups → centroid) | one survivor per group | other group points, inner edges, degenerate faces / no new IDs | groups inside the op (`collapse_groups`), not exported | survivor = average of the group (matches the centroid rule; H3) |
| Dissolve V/E/F, Delete V/E/F, Cap | everything else | only deletions (+ merged / new faces) | journal before-records; regions use their inference | **nothing** — data of survivors stays exact |
| W/E/R, Tweak, Soft, Loop Slide, Smooth/Relax | all | positions only | journal | relative offsets unchanged (Blender-like); visual check for Slide/Relax |
| Apply transform (bakes placement into points) | all | positions via a linear map | caller knows the transform | **offsets must be rotated/scaled too**, else expressions turn wrong |
| Symmetric versions | per side | each mirror point created by its own primitive call | the symmetric Knife already replays kept calls | covered if origin is recorded at primitive level |
| Undo / Redo | exact | — | delta records | no provenance needed if layers are journaled in the same recording |
| Mirror copy / OBJ import | new ID space | — | mirror: exact index map; import: none | mirror: remap by index map; import: real transfer (phase 7) |

**Smallest useful set of additions:**

1. **Vertex origin in the primitives:** `split_edge` blends the two ends (1−t, t); `split_face` computes mean-value
   weights for its interior points over the parent face's corners (it has both); `add_vertex(position, origin=…)`
   optional for tools (Extrude: "copy of v"); `collapse_edge` folds the removed point into the survivor.
2. **Generic per-point data layers in the Mesh** (offset vectors, normalized weights), journaled **per element** like
   positions — not whole-value like regions (~4 MiB and ~55 ms per change for an 87k-face region, AD-REGIONS-01 §2). The
   primitive writes the interpolated value **at mutation time**, so Undo, Knife checkpoints and the file come for free.
3. **A linear-map rule** for whole-mesh transforms (Apply transform).
4. **A fail-closed operation gate:** while layers exist, an operation that creates or merges points without a declared
   origin is refused visibly — the AD-SYM-03 D-b "declaration = support" pattern.
5. **Not needed now:** edge/face origin (the regions rule suffices), provenance in history, operation logs.

**Why interpolate at mutation time rather than collecting origins afterwards** (the regions approach): the latter needs
every commit boundary to remember the call and its own bookkeeping for nested rollbacks — it already cost a broken
import boundary in `tests/` at `da6d302`. Interpolating inside the primitive and journaling the result is also how
Blender treats shape keys in edit-mode operators (general knowledge of its design, not verified against its source here).

---

## E. Recommended deformation architecture

```
 all tools ──► Mesh (rest shape, object space)
               ├ topology + positions          (today)
               ├ face_regions                  (today)
               └ point layers: morph offsets per target, later skin weights   (new)
                   ↑ interpolated by the topology primitive itself
               change journal covers all of it → Undo, rollback, file
                          │ read-only
                          ▼
 Evaluation (per object; derived, never saved, never in History)
   rest ─► + Σ weightᵢ·offsetᵢ (morph) ─► skin (linear blend skinning) ─► SubD stencils ─► display
 Scene: target list + weights (view state now, animation later), rig/bones (AD-021 §4.9)
 Picking stays on the rest shape (Morph Lab verdict: "hilft")
```

**Editing a target:** keep the KEEP'd "target beside the base" (J-5), but make it an **editing view**: built from base +
offset when opened; shape edits write back into the offset; topology edits only on the base (refused on the view). This
removes the memory problem (one view, not N copies) and the ID-divergence problem (today any topology change switches
the morph off, because the two meshes' IDs can drift apart). How a gesture on the view becomes one Undo step on the
base's offsets is design work for phase 3, not an artist question.

**Simple sums vs. chains.** Additive morphs are linear and order-free: changing one slider only needs
`Δweight · offset` over that target's own points (cheap: one target, every point of 20k: 4.6 ms [C]); the cost is the
display (~27 µs per changed point [RPC]: normals and buffer rows in Python). Skinning after morphing is a nonlinear
per-frame chain and belongs in the vertex shader (GL 3.3 supports it; buffer textures already work on the reference
card; not measured). SubD after deformation is cheap: its stencils are linear in the cage positions, so SubD only has
to read evaluated instead of base positions.

**Techniques:**

| Technique | Use? | Notes |
|---|---|---|
| Edge-parameter / barycentric interpolation | yes, phase 5 | Exact given the recorded origin. Limit: linear — a new loop in a strongly bent area lies on the straight line between old points and may need a sculpt touch-up; non-planar faces are approximated |
| RBF/TPS transfer | not for provenance-backed edits | For *different* meshes (retopology, import). Dense solves, tuning, overshoot. Phase 7 |
| Geodesic vs. Euclidean distance | only for proximity-based transfer | Lips and eyelids are where Euclidean fails (upper lip picks the lower lip). Soft Selection already has a geodesic mode to reuse later |
| Inverse warping | not for phases 3–4 | Needed for sculpting correctives on a posed, skinned mesh (invert each point's blend matrix). Phase 6+ |
| Spatial hash / octree | only for correspondence search | Transfer, retopology snapping. Not needed with recorded origins |

No promise of automatic preservation for arbitrary edits: deterministic for declared operations, a visible refusal
otherwise, optionally a marker on interpolated points.

---

## F. Risks and unresolved decisions

**Confirmed problems** (evidence above): (1) no origin contract — ARCH-02 open; the Knife's exact record is discarded at
commit. (2) Lab target storage does not scale (52 / 207 MiB per target [C]). (3) One H7 slot: Morph and SubD cannot
coexist, SubD reads rest positions. (4) Python display cost per changed point (91 ms for 3,339 points [RPC]).
(5) Whole-value journaling (regions) unsuitable for large layers. (6) `collapse_edge` scans every face. (7) Red tests
(2 in `tests/`, Morph Lab does not start). (8) The documentation drift in B.

**Risks that need targeted tests:** Knife interior-point interpolation on non-planar faces; Loop Slide / Relax on a base
with targets (Blender-like expected; visual check); Apply transform rotating/scaling offsets; symmetric operations (one
origin per side); floating-point drift of incremental sums; journal cost of layer writes; a guard test that enumerates
every commit boundary; normals of the evaluated surface (CPU cost vs. per-target normal offsets on the GPU, glTF-style —
not measured).

**Owner decisions:** §H.

**Can safely wait:** Half-Edge; the corner domain until UV work starts (UVs: "ja", later — MODELING.md); RBF, geodesic
transfer, inverse warping, spatial indices; combination / corrective shapes; animation; any GPU-only path before the
reference-PC GL-limits probe (open since 2026-10-20, P0 b).

---

## G. Phased roadmap

- **Phase 0 — clean baseline (small).** Fix the Morph Lab `B` conflict and the two red tests (Knife/regions boundary:
  move the call or widen the allow-list with a reason); fix the doc drift of §B; optionally make `collapse_edge` local
  using the existing point→edge index. *Acceptance:* default `pytest` green; GL tests green in their own process;
  collapse time independent of mesh size [C]. *Out:* any morph feature.
- **Phase 1 — ARCH-02 decision.** One AD answering ARCH-02's six questions with table D, layer storage, gate and the
  transform rule; independent review (hard to reverse). *Prerequisites:* H1–H3. *Acceptance:* reviewed and recorded.
  *Out:* code.
- **Phase 2 — Core layers + gate.** Per-point layers journaled per element, additive file key, Delete/Dissolve handled,
  operation gate. *Acceptance:* randomized journal tests extended with layers (undo/redo/rollback exact vs. snapshot
  oracle); file round trip exact; memory per layer and journal cost measured; Knife oracle green. *Out:*
  interpolation, UI.
- **Phase 3 — one persistent target in Production (first useful milestone).** Create / rename / delete a target (Undo);
  edit beside the base as a view; weight slider as view state; save/load; topology gate per H1; display via H7.
  *Acceptance:* weight step ≤ 16.7 ms p95 on the reference PC for head and man_with_shoes; offsets bit-exact after save →
  load; Undo exact; a target survives Delete/Dissolve correctly; refused ops say why; Manu's 20–30 min practical test.
  *Out:* multiple targets, morph + SubD, topology propagation, skinning.
- **Phase 4 — multiple targets.** Additive incremental evaluation with a drift guard, packed storage, a stage chain so
  morph + SubD show together, GPU evaluation probe on the reference PC. *Acceptance:* 10 sparse targets on gollum_20k
  within the agreed slider budget [RPC]; 50 targets ≤ 50 MB at 20k; result independent of the order of weight changes
  (≤ 1e-6). *Out:* correctives, animation.
- **Phase 5 — topology edits with targets (recommended before skinning).** Origin interpolation in the primitives,
  Extrude passes origins, Collapse averages, Apply transform rotates/scales offsets; lift the gate per operation as each
  passes. *Acceptance:* per operation, layer values == the analytic rule; Undo exact; Knife golden tests green; artist
  test: loops around eyes and mouth with 3 targets. *Out:* transfer between different meshes.
- **Phase 6 — skinning and rig.** Scene-level rig (AD-021 §4.9); weights as a layer (normalized, ≤ 4 influences), so
  they get phase-5 propagation for free; skinning on the GPU + CPU reference; chain morph → skin → SubD.
  *Prerequisite:* reference-PC GL-limits probe. *Acceptance:* GPU == CPU reference within tolerance; pose step
  ≤ 16.7 ms at 20k [RPC].
- **Phase 7 — advanced remapping and diagnostics.** Transfer between meshes, retopology weight transfer, inverse
  warping, a diagnostics overlay — only with a concrete use case.

---

## H. Artist decisions

1. **H1 — Topology edits while targets exist, first version.** Recommended: allow everything that only removes or
   reconnects (Delete, Dissolve, Vertex Connect, Cap, all moves); refuse with a message the operations that create or
   merge points (Split, Connect Edges, Loop Insert, Knife, Extrude, Collapse) until phase 5. Locking all topology is
   simpler but blocks cleanup; full propagation now roughly doubles the first milestone.
2. **H2 — What a new point does in an existing target.** Recommended: it follows its neighbours linearly (as in
   Blender). Consequence: new loops in strongly bent areas may need a touch-up. Alternative: zero offset — dents when the
   target is dialled in.
3. **H3 — Merging points that carry offsets.** Recommended: average their offsets (matches the "merge at centre"
   position rule). Alternative: keep one point's offset — simpler, can tear slightly at expression peaks.
4. **H4 — Editing a target.** Recommended: keep "beside the base" (J-5 KEEP) as an editing view; shape edits there,
   topology only on the base. Alternative: edit in place on the base with a target switch (Blender-style), no second
   object.
5. **H5 — Scope and order.** Fluid on head/body and "usable, not fluid" on 20k until the GPU phase? Topology-after-morphs
   (phase 5) before skinning (phase 6)? Morph + SubD together not before phase 4? Recommended: yes to all three.
