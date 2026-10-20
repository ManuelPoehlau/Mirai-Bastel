# Independent Review — AD-023 "Incremental Topology Sync and History" (PROPOSED)

> **Reviewer:** Claude (claude.ai/code, fresh session, no prior chat or plan context)
> **Review ID:** CLAUDE-001
> **Target path:** `docs/archive/viewport_v02/reviews/AD-023_REVIEW_CLAUDE_001.md`
> **Repository state reviewed:** branch `claude/architecture-audit-summary-2026-10-20` @ `f25fe6a`
> (AD-023 last changed in `81de8eb`; the commits after it do not touch AD-023, `src/`, `tests/` or
> `experiments/drag_cost/`).
> **Subject:** `docs/architecture/AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md` (PROPOSED, 2026-10-17,
> reference-PC paragraph 2026-10-20)
> **Mode:** review only. No source, test, AD or other document edited; this file is the only change.
> **Status:** Archived first-pass review — preserved verbatim; answers belong in AD-023.
>
> This document is intentionally preserved as the original independent review. Do not edit it to
> reflect later decisions.

Evidence tags: **VERIFIED (code)** = read at `f25fe6a`, `file:line`; **VERIFIED (probe X)** = a throwaway
probe, code and output in the appendix; **UNVERIFIED** = not checked here; *(reading)* = my interpretation.
Every number I produced is a **container number** (Linux 6.18, Intel Xeon, 4 logical cores, Python 3.13.16,
headless `TraceStore`, no GL, no pyglet installed). None is a reference-PC number (REFERENCE_HARDWARE §4).

Independence: I did not read `docs/research/viewport/ARCHITECTURE_AUDIT_2026-10-20*.md`,
`experiments/architecture_audit_probes/`, or the D1c / research-README references to them. I saw only the
file names of commit `2d9e559` in `git show --stat` while checking which commits touched AD-023.

---

## What was read, what was run

**Read in full:** AD-023; AD-022; `experiments/drag_cost/README.md` §§ "Audit at HEAD" to "Next step";
`RESULTS_TOPOLOGY_REFERENCE_PC_2026-10-20.md`; `CORE_V1_FREEZE.md` §1, §7.1 (all entries), §7;
`src/core/operations/topology.py`, `history.py`, `ids.py`; `src/viewport/render_mesh.py`;
`tests/test_topology_history.py` (head + test list), `test_identity_continuity.py` (head + test list),
`test_history_contract.py` (test list).
**Read in part:** `V1_CORE.md` §11; AD-SYM-02 §5; AD-SYM-03 §2.2 and the T-a / slice-7 rows; AD-021 F-4,
§4.6; AD-018 §5 binding constraints and the 2026-10-15 face-data addendum; AD-014 header;
`VIEWPORT_V02_ARCHITECTURE.md` §1, §3, §4.5, §5.4, §6, §7, §11; `REFERENCE_HARDWARE.md` §1-§2;
`src/core/mesh.py` (classes, `all_*_ids`, `remove_face`, `export_state`, `load_state`);
`src/mirai/application.py` (`_mesh_transaction`, `apply_mesh_change`, `_apply_undo_redo`, `_undo_redo`,
`_notify_topology_changed`, `_refresh_hover`, extrude arm/begin/release/abort, `_transform_step`, loop slide,
Apply transform, `_soft_preview_refresh`); `src/mirai/topology/extrude.py`, `knife.py` (begin, commit),
`knife_resolve.py` (contract, `RecordedMesh`, checkpoint/rollback, `check_commit`, `integrity_problem`),
`delete_dissolve.py`, `loop_slide.py:115-130`, `loop_ring.py:95-125`; `src/mirai/symmetry_coordination.py`
(function list, `completeness_report`); `src/viewport/derived.py`, `viewport.py` (notifications, `sync`,
`_sync_surface`), `gl_render_store.py` (`allocate`, `update`, `_rebuild_vertex_list`);
`experiments/drag_cost/probe_navigation_gl.py` (topology scenario); `tests/test_render_mesh.py:350-400`,
`tests/test_benchmark_scenarios.py:105-118`.
**Grepped:** every `export_state` / `load_state` / `MeshStateCommand` / `history.push` in `src/`, `playground/`,
`experiments/`; `structural_rebuilds` / `topology_updates` in the test trees.
**Run:** four throwaway probes (appendix), headless in the container. No test suite run (review only, nothing
changed). The GL probe was not re-run: the reference-PC numbers exist and a container GL run would add nothing.

---

## Verdict

**ACCEPT WITH CHANGES** — as a decision basis for *the direction and the spike*, which is what AD-023 asks for
(§6: H1/V1 are decided only after the spike). It is **not** yet a basis for choosing between the options or for
the order AD-022 ↔ AD-023, because the cost split in §1 is partly mis-attributed (B-1) and the spike as written
cannot decide (B-2). Both are fixable in the text plus one reference-PC rerun; no prototype is needed first.

What holds: the reference-PC numbers are quoted correctly; "picking is a small share of a topology op" and
"viewport sync > history on the reference PC" are supported; H0/V0/V2 not touching the Core is correct; the AD
treats AD-001 as a constraint to meet, not to drop; it asks for equivalence tests and a debug compare. What does
not hold: the "history" column is not history, the snapshot cost is dominated by something no option names
(cyclic GC), Extrude rebuilds twice not three times, and the H1 contract leaves out several things the snapshot
silently guarantees today.

**Blockers:** B-1, B-2. **Major:** M-1 … M-7. **Minor:** m-1 … m-7.

---

## Answers to the review questions (short; details in the findings)

1. **Evidence.** Reference-PC figures in AD §1:47-50 match the raw output exactly (shares: sync 54.5-85 %,
   history 8-25.5 %, hover 4-13 %; one structural rebuild ≈ Delete's 1 265 ms) — VERIFIED (raw file :21-35).
   They carry the *ranking* V before H, because the gap is large. They do not carry gain estimates or H1 vs H0:
   n = 3, no p95, no profile split on the reference PC (the README says so itself), one camera, history depth ≈ 1,
   no symmetry, Soft off. The headless table (§1:35-42) has no source run, commit or script (m-1).
2. **Cause analysis.** Partly wrong: B-1 (history column, GC, Extrude count), M-3 (undo), m-3/m-4 (op column,
   missing cost items: edge overlay, symmetry reports, Soft preview, Knife session snapshot).
3. **Options.** H0/V0/V2 are fair; H1/V1 under-specify their preconditions (M-1, M-3, M-4); "estimates" are
   asserted, not derived (B-1). Missing: GC control (G), a constant-factor rebuild (V3), an app-side touched-set
   carrier for Undo (M-3), and an explicit numpy/native ruling (M-6).
4. **History correctness.** A delta *can* keep AD-001 and exact Undo/Redo, but only with the contract in M-1
   (counters untouched on undo, symmetry definition, record-internal order, iteration order, rollback paths,
   change signal). The mutation-path list is incomplete (M-2). One gesture = one entry (AD-SYM-02/03) is
   unaffected in shape; multi-object (AD-021 §4.6) fits because each command holds its own mesh.
5. **Contracts.** §3 is incomplete (M-5): VIEWPORT_V02 §3/§6/§7, two tests that pin resource recreation,
   AD-SYM-01, AD-013 H2 `apply_mesh_change`, the Freeze contract tests, AD-018 face-data ordering.
6. **Risks.** Missing: memory (≈ 61 MB per topology entry on 20k, unbounded stack), GC tail growing with history
   depth, half-applied undo, maintenance of touched sets for every future op, debuggability (M-6). The debug
   compare is necessary but not sufficient (M-6).
7. **AD-022.** Not independent where they share buffers or rebuild per mesh state (M-7). Independent in
   history (H*) and in triangulation/normals caching (V0).
8. **Spike.** As written it cannot decide (B-2): no targets, no abort rule, the two easiest ops, no stated way to
   get touched sets without a Core change.
9. **Artist questions.** Q1 attributes fast Undo to H1, but Undo is mostly the viewport rebuild (M-3); Q2 is fine.
   Missing: a target, which ops matter, undo depth / memory (see "Artist questions").
10. **Decision readiness.** See the last section.

---

## Findings

### B-1 — The §1 cost split mis-attributes the "history" column and misses its dominant mechanism (BLOCKER)

**Evidence.**
- The probe's `history` is every `export_state` / `load_state` call plus `history.push` inside the event, whoever
  calls it — VERIFIED (code) `experiments/drag_cost/probe_navigation_gl.py:909-919`. Some of those calls belong to
  the *operations*, not to history:
  - Extrude prunes leftover geometry through a whole-mesh `export_state()` + dict edit + `load_state()`
    (`src/mirai/topology/extrude.py:362-389`; the frozen Core has no edge/vertex removal). Multi-face Extrude
    therefore does 3 exports + 1 load, single-face 2 exports — VERIFIED (probe A: `extrude 20 … {'export': 3,
    'load': 1}`). This is why "Extrude 20 faces" history is 889/910 ms vs 388/244 ms for one face.
  - The Knife resolver checkpoints with `export_state` and rolls back with `load_state` per bridge / run / shape
    (`knife_resolve.py:227-236`, call sites `:401`, `:965`, `:999`), and `check_commit` exports once more
    (`:540`). Its `before` snapshot is taken at session start (`knife.py:239`, the `C` press), outside the
    measured Enter. So the Knife's 627/525 ms "history" is mostly resolver work.
  - H1 removes none of these; H0 removes at most the commit export (and not for the Knife, whose
    `check_commit` needs `current` anyway). AD §2:60-64's "history and undo from ~0.3-1 s to ms" and the
    "op itself 1-74 ms" (§1:33) are therefore both off for Extrude-multi and Knife.
- **Cyclic GC dominates the snapshot cost.** With a full headless app and five snapshots alive, `export_state`
  is 228-234 ms with GC on and 28-31 ms with GC off; `load_state` 417-444 vs 60-65 ms — VERIFIED (probe C).
  The worst-case export grows with the number of live snapshots (history depth): max 65 / 184 / 353 / 694 ms at
  0 / 2 / 10 / 30 live snapshots — VERIFIED (probe D). The topology probe undoes after every sample, so it
  measures history depth ≈ 1; a real session pays more, in occasional long stalls. *(reading)* This is also the
  most likely reason the reference PC (Python 3.14) is *not* slower than the container (3.13) in the history
  column while everything else is 2-3.5x slower — Python 3.14 changed the cyclic GC (UNVERIFIED on the
  reference PC). The README leaves this open ("n = 3 does not decide it").
- **Extrude rebuilds the viewport twice, not three times** (§1:44, §2:77-78). Begin marks topology dirty, the
  move only patches vertices, the release marks topology dirty again although the commit does not change the
  mesh (`application.py:3075`, `:2832`, `:3108`; `extrude.py:297-326`) — VERIFIED (probe A: `[(1, 582), (0, 0),
  (1, 607)]` structural syncs per step). Consistent with the reference PC: 2 604 ms ≈ 2 × 1 265 ms.
- Sync gains little from GC control (269 vs 236 ms, probe C), so the V side is real Python / store work; its split
  on the reference PC is unknown (README "Open: … `--profile-top 15`").

**Why blocking.** Manu is asked to order AD-022 vs AD-023 and to say whether fast Undo is intent; both answers
rest on §1. The gains attached to H0/H1 and the "likely ~2x" in §6 cannot be checked from the text, and one
option that may take most of the H cost away without any contract change (GC control) is absent.

**Change to the AD text.**
1. Relabel the `history` column as "whole-mesh snapshots (history + op-internal)" and add a note per row: Extrude
   (multi-face) prune = 1 export + 1 load; Knife = resolver checkpoints + `check_commit`; session snapshot at `C`
   not measured.
2. Add a GC row to the part table and an option **G — GC control around snapshots / rebuilds** (e.g.
   `gc.freeze()` after load, raised thresholds, or GC paused inside `_mesh_transaction` / `load_state`
   callers), with the risk (memory held longer, behaviour depends on the Python version) and "measure on the
   reference PC first".
3. Correct Extrude to "two structural rebuilds (begin, release) plus one vertex patch"; V2 then saves one
   rebuild (≈ 1.26 s on the reference PC for Extrude), not two.
4. Mark every gain as "estimate, not measured" until the reference-PC profile exists.

### B-2 — The spike (§6) cannot decide between the options as written (BLOCKER)

**Evidence.** §6:111-113 names what to build, not what would count as success. No target per op or per Undo, no
abort rule, no reference-PC run size. Delete and Extrude are the two ops with the simplest touched sets
(new elements plus removed faces); the hard ones — Knife (resolver checkpoints, `integrity_problem` reads the whole
`before_state["faces"]`, `knife_resolve.py:450-460`), Dissolve with cleanup (region merges), and any symmetric
coordinator (both sides, seam definition, rollback to `session_before`, `symmetric_knife.py:575`) — are where
H1's scope and correctness risk sit. The spike also does not say how a touched set is obtained without a Core
change: a recording proxy (prior art: `RecordedMesh` / `kept_calls`, `knife_resolve.py:175-215`) cannot see what
`delete_faces` removes internally; a Core hook is a Core change; a diff needs the full snapshot.

**Change to the AD text.** Rewrite §6 as:
- **Stage 1 (no Core change, cheap):** G + V2 + V3 (M-6) + H0, measured on the reference PC with
  `--profile-top 15`, n ≥ 10 with p95, history depth 1 and ~20, GC on/off. Decision point: if op + Undo on
  `gollum_20k` are under a target Manu names (see Artist questions), stop; H1/V1 are not needed.
- **Stage 2 (only if stage 1 misses the target):** touched-set prototype for Delete, Extrude **and** Knife (or
  Dissolve-with-cleanup), plus one symmetric op; state the capture mechanism; correctness = M-1 contract
  checked against the snapshot on every sample (randomised op sequences with undo/redo).
- **Abort rule:** stop H1 if any op needs whole-mesh work to compute its touched set, or if the debug compare
  finds a mismatch that is not a bug in the prototype but a contract gap.

### M-1 — H1's "exact" contract is incomplete; the snapshot guarantees more than the AD lists (MAJOR)

A full `export_state` / `load_state` round trip restores, without anyone stating it:
- **ID counters stay forward on undo.** `load_state` never lowers a counter (`mesh.py:1157-1159`,
  `ids.py:84-89`). AD §2:61-62 says the entry stores "the ID counters, and undo restores just those". Restoring
  them would re-issue IDs after Undo + a new op — an AD-001 violation. The delta must leave counters alone.
- **The symmetry definition** rides in the state (`mesh.py:1067-1099`, `:1161-1169`); AD-SYM-01 §1.1 / AD-SYM-02
  §5 rely on that, and the seam rules (`seam_after_extrude`, S1) write it inside the transaction. A delta must
  carry it explicitly.
- **Order inside records.** `edge.faces` list order is used semantically: Loop Slide takes
  `side_a, side_b = edge_faces` (`loop_slide.py:125`), so a re-built list flips the slide side. Face boundary
  rotation decides the triangulation fan (`derived.py:126`). The existing tests compare sorted / set data
  (`test_topology_history.py:47`) and would not catch either.
- **Dict iteration order.** `all_*_ids()` return dict order (`mesh.py:184-191`); after a snapshot undo the order
  is the pre-op order. A delta that re-inserts deleted elements appends them. That order feeds the buffer layout
  and `triangle_faces` (`render_mesh.py:176-195`), pick tie-breaks and saved files. Either preserve it or state
  that it is not part of "exact" and make every consumer order-free.
- **Rollback and abort paths.** `_mesh_transaction` restores from `before` on any exception
  (`application.py:3273-3278`); Extrude cancel (`extrude.py:328-330`), Knife refusal (`knife.py:751`),
  `check_commit` rollback, symmetric refusals and Loop Slide abort (`application.py:1945-1951`) all use
  `load_state`. A delta design must say whether `before` is still taken for rollback (then H1 saves only the
  after-snapshot and the undo load) or whether ops become transactional.
- **"Changed?" signal.** Today it is snapshot equality (`application.py:3280`; `delete_dissolve.py:46`: "nothing
  happened has no other trace"). Equality includes counters, which advance after an internal rollback (the
  Knife uses `mesh_content` without counters for this reason, `knife_resolve.py:443-447`). H0 and H1 both need a
  replacement signal per op.

**Change.** Add an "Exactness contract" subsection to H1 listing these six points, and make the §3 equivalence test
compare unsorted records, iteration order (or document its exemption), the symmetry definition and the counters.

### M-2 — The inventory of mesh-mutation paths is incomplete (MAJOR)

§2:63-64 lists `delete_dissolve`, Knife, Extrude, split/connect, loop insert, symmetric coordinators. Also pushing
`MeshStateCommand` or mutating outside the op function: **Apply transform** (one `MeshStateCommand` per object
inside a `CompositeCommand`, `application.py:1214-1242`), **Loop Slide** (positions only, full snapshots,
`:1901-1944`), **`apply_mesh_change`** (the external-host entry, `:3228`, AD-013 H2 addendum — its `mutate`
would have to report touched sets, a host contract change), Extrude's raw-dict prune (`extrude.py:362-389`),
and outside `src/`: `playground/topology_ops.py`, `playground/topology_tools/{loop_slide,connect_edges}.py`,
`experiments/symmetry_lab/lab_resymmetrize.py`, the Knife Face Lab engine. *(reading)* Because `HistoryStack`
only needs the `Command` protocol (`history.py:29-40`), snapshot and delta entries can coexist on one stack as
long as each is exact — the AD should say so; it turns "every tool at once" into a staged migration and lowers
the scope risk in §4:102.

### M-3 — Undo cannot get a touched set today; every mesh Undo rebuilds the whole viewport (MAJOR)

`_undo_redo` marks the topology dirty for every mesh step because `HistoryStack` does not expose the undone
command (`application.py:3159-3169`, comment E23; AD-SYM-03 §2.2 T-d confirms there is no top-of-stack access).
So even Undo of a one-vertex **W move** pays a full structural rebuild — VERIFIED (probe A: `W move 1 vertex … undo:
structural 1, 433 ms`). The undo frame on the reference PC (1.7-2.0 s) is ≈ 1.26 s rebuild + `load_state` +
pick cache. Consequences: (a) H1 alone does not make Undo fast; V0/V1 on the undo path do; (b) V1 on Undo needs
the entry's touched set, which needs either a `HistoryStack` change (frozen Core) or an app-side carrier — the
selection mirror stack already runs 1:1 with pushes (`_record_selection_history`, `application.py:3336`)
and could hold it; (c) the W-undo cost is a separate, cheaper win (the mirror entry could say "positions only").
**Change.** Add an "Undo path" row to §2 (options: mirror-carried touched set / Core accessor / keep full rebuild),
and correct §2:64 to "history part of Undo".

### M-4 — V0's equivalence claim and V1's ordering contract (MAJOR)

- Triangulation depends on positions: convex faces get the fan, concave ones ear clipping
  (`derived.py:105-174`). Today a W drag does not re-triangulate, but the next topology op re-triangulates every
  face with current positions. A V0 cache keyed on boundaries keeps the old triangulation of a quad a W drag made
  concave, so "incremental == full rebuild" (§3:95) fails unless the key includes convexity or V0 re-triangulates
  faces whose vertices moved since caching. *(reading)* Shading hides the diagonal (AD-018 face-data addendum:
  the bilinear patch does not depend on it), silhouettes do not.
- V1 must keep the index order and `triangle_faces` (per triangle, its face row, read through `gl_PrimitiveID`)
  consistent (`render_mesh.py:176-195`, AD-018 addendum 2026-10-15); spare capacity means degenerate triangles that
  still need a row. AD-022 B2 would read the same mapping (M-7).
**Change.** V0: state the cache key and the "moved since cached" rule. V1: name the `triangle_faces` /
`gl_PrimitiveID` ordering as a constraint.

### M-5 — §3 "What it touches" is incomplete (MAJOR)

Add: VIEWPORT_V02 **§3** invariant row "Topology changes may trigger larger rebuilds" (`:77`), **§6** table row
"Full rebuild (~50–100 ms) | Rare, explicit" (`:378` — both the cost and "rare" are now contradicted), **§7**
"Topology update (allowed exception) … OK to recreate" (`:398`); the tests that *require* new resource IDs after a
topology change (`tests/test_render_mesh.py:353-365`, `tests/test_benchmark_scenarios.py:105-117`) — V1 inverts
them, and AD-018 §5 says a test that must change is a finding, not a silent fix; the §5.4 counter clause
"structural_rebuilds == 1" (`:358`) is already not what the code counts (`render_mesh.py:241-243` counts once per
recreated resource plus once per sync), so it needs settling anyway; AD-SYM-01 (definition in the state);
AD-013 H2 addendum (`apply_mesh_change`); the Freeze §7.1 entries for `split_face` and Delete/Dissolve, whose
contract tests include `MeshStateCommand` round trips; AD-021 §4.6 (Apply transform composite); the H7 surface
providers (`viewport.py:448-470`, `tests/test_viewport_surface_provider.py`), which follow topology
notifications. Also cite V1_CORE §11, which left the mechanism ("structural diffs, hybrid") open — it supports
H1's legitimacy. §2:62-63 cites "a §7 exception like AD-014 / AD-017"; AD-014 is accepted but not recorded in §7.1
(a gap in the freeze document, not in AD-023) — cite the §7.1 entries instead.

### M-6 — Risks and alternatives that are missing (MAJOR)

Risks (§4):
- **Memory.** One snapshot of `gollum_20k` = 30.7 MB (tracemalloc), so ≈ 61 MB per topology or Loop-Slide entry;
  the stack is unbounded (no limit anywhere in `src/`) — VERIFIED (probe B, grep). 50 entries ≈ 3 GB on an 8 GB
  reference PC; 87.5k ≈ 4x. This is an argument *for* H1 independent of speed and weighs H0's lazy after-snapshot.
- **GC tail grows with history depth** (B-1, probe D) — users feel it as random stalls.
- **Half-applied undo** if applying a delta raises; the snapshot has no such state.
- **Maintenance.** Every future op must report a correct touched set; a forgotten element is silent. The AD-SYM-03
  "future ops" pattern (declaration + gate) is the precedent to copy.
- **Debug compare** (§4:100) costs the full snapshot, so it cannot run in normal use; add property-style tests
  (random op sequences, undo/redo to the start, compare with snapshots) as the standing guard.
Alternatives (§2):
- **G** (B-1).
- **V3 — cheaper full rebuild, no contract change:** `_positions_flat` / `_normals_flat` sort all V per rebuild
  (`render_mesh.py:194-201`), indices go int → float → int (`render_mesh.py:202-206`, `gl_render_store.py:562`),
  attributes are copied into tuples (`gl_render_store.py:560`). On the reference PC the sync is 2.7-3.5x the
  container vs ~2x for other Python, which points at the store / upload path *(reading)*. Cheap, benefits every
  op and every Undo; should be ranked before V0/V1.
- **numpy / native code:** not a dependency today (`requirements-dev.txt`); REFERENCE_HARDWARE §2 warns about
  wheels needing newer instruction sets. Rule it in or out in the form "X wird nicht verwendet, weil Y" (M1).

### M-7 — AD-022 interaction is understated (MAJOR)

§1:44-45 says "AD-022 does not change this table". It does, per variant: **B1** adds its own ID buffers (3x
triangle data, ~0.2 s Python build on 20k, AD-022 :68-70) to rebuild after every topology op; **B2** reuses
`indices` and `u_triangle_faces` (AD-022 :71-75), so V1's index patching and B2's `gl_PrimitiveID` mapping are one
contract and must be decided together; **A** (world index) adds a 0.65 s rebuild per op (AD-022 :59-62) unless fed
by touched sets. **P** is "moot" only for hover / click in the window: AD-022 §5 keeps `PickCache` for the Knife's
exact math and the headless path (:111-114). Independent: H0/H1/G (history) and V0/V2/V3.
**Change.** Add a short "Coupling with AD-022" table: B1 → per-op cost +; B2 ↔ V1 decided together; A ↔ touched
sets; P scope.

### m-1 — The headless part table has no source (MINOR)
§1:35-42 gives no run, commit or script; it mixes headless timings with a "(profile)" figure (cProfile-inflated),
and the drag_cost README gives different profile numbers (0.36 / 0.23 / 0.28 s). My container: export 128, load 190,
triangulate 111, normals 84, `_rebuild_resources` 65 ms (probe A) — same order, other ratios. Add the source or mark
the table "indicative, not reproducible from the repo".

### m-2 — "Picking is 5-10 %" (§1:44) — measured 3-11 % (container) and 4-13 % (reference PC). Quote the range.

### m-3 — "op itself" includes the `after == before` comparison (~6 ms, probe A) and selection upkeep
(`probe_navigation_gl.py:269-272`, `op = event − history − notify − pick`). Say so in the column header.

### m-4 — Scenario limits not stated: no symmetry (each symmetric op adds two full `completeness_report`s with a
`SymmetryIndex`, `symmetric_ops.py:148-262`, `symmetry_coordination.py:397-416`), Soft off
(`_soft_preview_refresh` runs on every topology change, `application.py:2048`), wireframe-edge overlay rebuilt per
dirty frame when shown (`viewport.py:637`, 12 ms container), Knife session snapshot at `C` unmeasured, history
depth ≈ 1.

### m-5 — H0's lazy after-snapshot moves the export to the first Undo (Undo gets slower by one export, Redo
needs it); "saves one export per op" holds only for ops never undone. State this.

### m-6 — H2 is listed "for completeness" without cost or risk; either give one line each or drop it with a reason.

### m-7 — The reference-PC paragraph (§1:47-50) is German inside an English AD (AGENTS §4b: canonical docs for
agents in English). Cosmetic; keep it consistent when the AD is edited.

---

## Artist questions (§5)

- Q1 should not tie fast Undo to H1 (M-3). Suggested: "Soll Rückgängig auf 20k genauso schnell sein wie die
  Operation selbst? (Heute ~2 s auf deinem PC, auch nach einem einfachen W.)"
- Q2 is decidable as is.
- Missing, only Manu can answer: (a) **Ziel:** what counts as "flüssig" for one op and one Undo on 20k (e.g.
  "unter einer Viertelsekunde" or "wie Blender") — the spike needs it as its success line; (b) **Welche
  Operationen zuerst** (Extrude, Knife, Delete, Loop …) — decides the spike ops; (c) **Undo-Tiefe:** how many
  steps back on a 20k mesh he expects (memory, M-6); (d) **Schneller Teilgewinn zuerst?** a cheap stage 1
  (G/V2/V3/H0) now, or wait for the full solution.

## Decision readiness

**Before Manu decides the direction / order:** fix B-1 in the text; run the topology scenario once more on the
reference PC with `--profile-top 15`, n ≥ 10, and a GC-off variant (one flag in the probe), ideally with a history
depth of ~20; add M-3, M-5, M-7 to the text; add the Artist questions above.
**Before deciding H1 / V1:** the staged spike of B-2 with the M-1 contract as its test oracle.
**Can wait until after the decision:** API names, the capture mechanism details, V1 capacity policy, the
debug-mode switch, the VIEWPORT_V02 / AD-018 wording.

## What I could not check

- Anything on the reference PC: the sync split, GL upload cost through pyglet on the Windows driver, Python 3.14's
  GC behaviour, whether G or V3 help there.
- The GL path in the container (no pyglet installed); my sync numbers are `TraceStore` only.
- Knife and symmetric ops in my probe (counts above are from code reading); Loop insert / Connect paths were not run.
- Whether any consumer besides Loop Slide and the triangulation fan depends on record-internal or iteration order
  (I grepped `src/mirai` for the obvious patterns only).
- The Playground / Lab / experiment users of `MeshStateCommand` beyond their file names.
- The AD-022 spike code and its reference-PC results file (not needed for the AD-023 questions).

---

## Appendix — review probes (container, throwaway, not in the repo)

All run as `python3 -I -B <probe> /home/user/mirai-bastel` from the repository root on `f25fe6a`.

### Probe A — cost parts, snapshot calls and structural syncs per op (`probe_ad023.py`)

```python
import sys, time, statistics, collections
REPO = sys.argv[1]
for p in (REPO + "/src", REPO, REPO + "/examples"): sys.path.insert(0, p)
from mirai.application import Application
from mirai.interaction.input import Input
from viewport.wireframe import edge_segments
def ms(f, n=3):
    out = []
    for _ in range(n):
        t = time.perf_counter(); r = f(); out.append((time.perf_counter() - t) * 1000)
    return statistics.median(out), r
app = Application(); app.init_scene("obj", obj_path=REPO + "/examples/meshes/gollum_20k.obj")
app.frame_scene(); app.set_viewport_size(1024, 768)
mesh = app.scene.mesh; vp = app.viewport; rm = vp.render_mesh
t, s = ms(mesh.export_state); print(f"export_state {t:.0f} ms")
t, _ = ms(lambda: mesh.load_state(s)); print(f"load_state {t:.0f} ms")
s2 = mesh.export_state(); t, _ = ms(lambda: s == s2); print(f"after == before (equal) {t:.0f} ms")
t, _ = ms(lambda: rm.derived.full_recompute(mesh)); print(f"derived.full_recompute {t:.0f} ms")
t, _ = ms(rm._rebuild_index_mapping); print(f"_rebuild_index_mapping {t:.0f} ms")
t, _ = ms(rm._rebuild_resources); print(f"_rebuild_resources (TraceStore) {t:.0f} ms")
t, _ = ms(lambda: edge_segments(mesh)); print(f"wireframe edge_segments {t:.0f} ms")
t, _ = ms(lambda: (vp.on_topology_changed(), vp.sync())); print(f"Viewport.sync after topology {t:.0f} ms")
calls = collections.Counter(); oe, ol = mesh.export_state, mesh.load_state
def wrap(n, f):
    def g(*a, **k): calls[n] += 1; return f(*a, **k)
    return g
mesh.export_state = wrap("export", oe); mesh.load_state = wrap("load", ol)
topo = lambda: rm.stats.counters.get("topology_updates", 0)
def run(label, steps):
    calls.clear(); per = []
    for st in steps:
        b = topo(); t = time.perf_counter(); st(); vp.sync()
        per.append((topo() - b, round((time.perf_counter() - t) * 1000)))
    c = dict(calls); calls.clear(); b = topo(); t = time.perf_counter()
    app.key_press(Input("key", "z", frozenset({"ctrl"}))); vp.sync()
    print(f"{label}: per step (structural syncs, ms) {per}; export/load {c}; undo: structural "
          f"{topo()-b}, export/load {dict(calls)}, {round((time.perf_counter()-t)*1000)} ms")
K = lambda v: Input("key", v)
faces = mesh.all_face_ids(); seed = faces[len(faces) // 2]
def patch(n):  # breadth-first face patch around `seed`
    out, q, seen = [seed], [seed], {seed}
    while q and len(out) < n:
        f = q.pop(0)
        for e in mesh.face_edges(f):
            for o in mesh.edge_faces(e):
                if o not in seen and len(out) < n: seen.add(o); out.append(o); q.append(o)
    return out
cx, cy = 512.0, 384.0; app.pointer_motion(cx, cy)
for n in (1, 20):
    p = patch(n)
    def arm():
        app.key_press(K("3")); app.selection.set(set(p)); vp.on_selection_changed()
        app.key_press(K("t")); app.pointer_motion(cx, cy + 8, 0, 8)
    run(f"extrude {n}", [arm, lambda: app.pointer_motion(cx, cy + 16, 0, 8), lambda: app.key_release(K("t"))])
run("delete 1 face", [lambda: (app.key_press(K("3")), app.selection.set({seed}),
                               vp.on_selection_changed(), app.key_press(K("delete")))])
edge = mesh.face_edges(seed)[0]
run("dissolve 1 edge", [lambda: (app.key_press(K("2")), app.selection.set({edge}),
                                 vp.on_selection_changed(), app.key_press(K("backspace")))])
vid = mesh.face_vertices(seed)[0]
def wmove():
    app.key_press(K("1")); app.selection.set({vid}); vp.on_selection_changed()
    app.key_press(K("w")); app.pointer_motion(cx + 5, cy, 5, 0); app.pointer_motion(cx + 10, cy, 5, 0)
run("W move 1 vertex", [wmove, lambda: app.key_release(K("w"))])
```

Output (gollum_20k, 21 875 V / 43 750 E / 21 875 F; `show_edges` False headless):

```
export_state 128 ms
load_state 190 ms
after == before (equal) 6 ms
derived.full_recompute 84 ms        (of it rebuild_adjacency 14 ms)
_rebuild_index_mapping (triangulate all) 111 ms
_rebuild_resources (TraceStore, flatten only) 65 ms
wireframe edge_segments 12 ms
Viewport.sync after on_topology_changed (TraceStore) 252 ms
extrude 1: per step (structural syncs, ms) [(1, 582), (0, 0), (1, 607)]; export/load {'export': 2}; undo: structural 1, export/load {'load': 1}, 773 ms
extrude 20: per step (structural syncs, ms) [(1, 1005), (0, 1), (1, 641)]; export/load {'export': 3, 'load': 1}; undo: structural 1, export/load {'load': 1}, 795 ms
delete 1 face: per step (structural syncs, ms) [(1, 598)]; export/load {'export': 2}; undo: structural 1, export/load {'load': 1}, 792 ms
dissolve 1 edge: per step (structural syncs, ms) [(1, 615)]; export/load {'export': 2}; undo: structural 1, export/load {'load': 1}, 587 ms
W move 1 vertex: per step (structural syncs, ms) [(0, 2), (0, 99)]; export/load {}; undo: structural 1, export/load {}, 433 ms
```

(A second run gave dissolve 562 / undo 568 ms; counts identical.)

### Probe B — memory of one snapshot (`probe_mem.py`)

```python
import sys, tracemalloc
REPO = sys.argv[1]
for p in (REPO + "/src", REPO, REPO + "/examples"): sys.path.insert(0, p)
from mirai.scene_factory import build_core_scene_from_obj
mesh = build_core_scene_from_obj(REPO + "/examples/meshes/gollum_20k.obj").mesh
tracemalloc.start(); s = mesh.export_state(); cur, _ = tracemalloc.get_traced_memory()
print(f"one export_state snapshot: {cur/1e6:.1f} MB (tracemalloc); a MeshStateCommand holds two")
```

```
one export_state snapshot: 30.7 MB (tracemalloc); a MeshStateCommand holds two
```

### Probe C — share of cyclic GC (`probe_gc.py`)

```python
import sys, time, gc, statistics
REPO = sys.argv[1]
for p in (REPO + "/src", REPO, REPO + "/examples"): sys.path.insert(0, p)
from mirai.application import Application
app = Application(); app.init_scene("obj", obj_path=REPO + "/examples/meshes/gollum_20k.obj")
app.frame_scene(); app.set_viewport_size(1024, 768); app.viewport.sync()
mesh, vp, keep = app.scene.mesh, app.viewport, []
def t(f, n=5):
    out = []
    for _ in range(n):
        a = time.perf_counter(); keep.append(f()); out.append((time.perf_counter() - a) * 1000)
    return statistics.median(out)
s = mesh.export_state()
for label in ("gc on", "gc off"):
    if label == "gc off": gc.disable()
    keep.clear()
    print(f"{label}: export_state {t(mesh.export_state):.0f} ms, load_state {t(lambda: mesh.load_state(s)):.0f} ms")
gc.enable()
for label in ("gc on", "gc off"):
    if label == "gc off": gc.disable()
    print(f"{label}: Viewport.sync after on_topology_changed {t(lambda: (vp.on_topology_changed(), vp.sync())):.0f} ms")
gc.enable()
```

```
gc on: export_state 234 ms, load_state 417 ms     (first run: 228 / 444)
gc off: export_state 31 ms, load_state 65 ms      (first run: 28 / 60)
gc on: Viewport.sync after on_topology_changed (TraceStore) 269 ms
gc off: Viewport.sync after on_topology_changed (TraceStore) 236 ms
```

### Probe D — export cost vs live snapshots (`probe_gc_depth.py`)

```python
import sys, time, statistics
REPO = sys.argv[1]
for p in (REPO + "/src", REPO, REPO + "/examples"): sys.path.insert(0, p)
from mirai.scene_factory import build_core_scene_from_obj
mesh = build_core_scene_from_obj(REPO + "/examples/meshes/gollum_20k.obj").mesh
live = []
for target in (0, 2, 10, 30):
    while len(live) < target: live.append(mesh.export_state())
    out = []
    for _ in range(5):
        a = time.perf_counter(); s = mesh.export_state(); out.append((time.perf_counter() - a) * 1000); del s
    print(f"live snapshots {target:3d}: export_state p50 {statistics.median(out):.0f} ms, max {max(out):.0f} ms")
```

```
live snapshots   0 (~0 topology entries): export_state p50 39 ms, max 65 ms
live snapshots   2 (~1 topology entries): export_state p50 94 ms, max 184 ms
live snapshots  10 (~5 topology entries): export_state p50 34 ms, max 353 ms
live snapshots  30 (~15 topology entries): export_state p50 47 ms, max 694 ms
```

---

## Kurzfassung für Manu (Deutsch)

AD-023 taugt als Grundlage für die Richtung, nach Korrekturen. Die Zahlen von deinem PC sind richtig zitiert:
Der Viewport-Neuaufbau ist der größte Posten, das Picking ein kleiner. Drei Dinge stimmen aber nicht ganz:
(1) Die Spalte „History“ enthält auch Arbeit der Werkzeuge selbst (Extrude mit mehreren Faces, Knife). Den größten
Teil der Snapshot-Zeit verbraucht im Container Pythons Garbage Collector, und er wächst mit der Zahl der
Undo-Schritte. Dagegen gibt es eine billige Maßnahme ohne Vertragsänderung, die im AD fehlt. (2) Extrude baut den
Viewport zweimal neu auf, nicht dreimal. (3) Rückgängig ist vor allem langsam, weil danach der ganze Viewport neu
aufgebaut wird, auch nach einem einfachen W, und nicht wegen der History. Vor deiner Entscheidung fehlen eine
Messung auf deinem PC mit Profil und ohne Garbage Collector sowie dein Ziel: Was heißt für dich „flüssig“ bei
einer Operation und bei Rückgängig auf 20k, welche Operationen zuerst, wie viele Undo-Schritte brauchst du?
