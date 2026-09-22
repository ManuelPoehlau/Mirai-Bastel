# WP-AP-CUT — Contextual C: Implementation Brief (for Claude Code)

**Status:** IMPLEMENTED (2026-09-22) — all §1 items built and tested; see git history for files changed
**Date:** 2026-09-22 (supersedes the 2026-09-21 plan version of this file)
**Mode (M5):** Production — the product decisions are made. **BUILD must not claim new knowledge:**
if something unexpected appears, stop, record it as an open question, do not decide it while building.
**Authority:** `docs/architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md` → "Decision"
**Artist decisions (archived):** `docs/architecture/AD-017_FINAL_DECISIONS_2026-09-22.md`

---

## 0. Pre-implementation consistency check (2026-09-22)

Result: **implementation-ready.** No contradiction blocks implementation. Findings:

> Split residue (C1) and Knife commit residue are now both **confirmed** Artist decisions (2026-09-22
> addendum to `AD-017_FINAL_DECISIONS_2026-09-22.md`), not open questions. Table below kept for context.

| # | Finding | Handling |
|---|---|---|
| C1 | **Split residue requires a mode switch.** `Selection` stores only the active mode's set (`src/core/selection.py`); "new vertex selected" after an Edge-mode Split is only possible by switching to Vertex mode. | **CONFIRMED by Artist.** Implement the literal reading (switch to Vertex mode, select the new vertex) in **one isolated function**. |
| C2 | Knife start "clicked/selected vertex": the Knife is only entered with an empty selection, so the start is always a **clicked** point. | Start = first valid click. No selection is read. |
| C3 | Contexts without a C meaning: 1 vertex selected, faces selected. After Split (C1) a second C lands in "1 vertex". | No-op + HUD hint. Nothing invented. |
| C4 | Face-interior knife points (Artist's main open question) are incompatible with "each click creates the next cut" as-is: an interior point alone is not valid topology; it would need pending points until the path reaches an edge/vertex, and a face-split primitive (AD-017 B2). | **Out of scope.** Face hits are "on mesh, no target". Session steps must be recorded per click so a later pending-point model is not made expensive. |
| C5 | Knife residue after commit. | **DECIDED by Artist.** Select the session's newly created connecting-edge path (not split-remnant edges, not vertices); switch to Edge mode — mirrors Edge Connect's residue rule. |
| C6 | Existing picking does not filter occluded edges/vertices (`src/mirai/viewport/picking.py`). | Reuse as-is; document as known limitation. Not fixed here. |

---

## 1. Must implement

### 1.1 Core: `Mesh.split_edge(edge_id, t=0.5)` — the only Core change

Decision (AD-017 §12 delegated to implementation): extend the existing primitive.
Reasons: Knife makes non-midpoint splits the normal case; the documented contract ("splits at the
midpoint") would otherwise stop describing the result; the rigging experiment's midpoint fallback
(FINDINGS-3C, 3C-2) fails for t ≠ 0.5, leaving the operation-context path (caller knows edge + t)
as the reliable provenance route (AD-017 B5).

- Signature: `split_edge(self, edge_id: EdgeId, t: float = 0.5) -> tuple[VertexId, EdgeId, EdgeId]`.
- `t` is measured from `edge_vertices(edge_id)[0]` towards `[1]`.
- Validation: `0.0 < t < 1.0`, otherwise `MeshError`; mesh unchanged on error.
- **Default must be bit-identical** to today's midpoint (`(a + b) / 2.0`). Use a formula that yields
  the identical result for `t == 0.5` (e.g. keep the existing expression for 0.5, or `a*(1-t) + b*t`
  and prove equality in a test).
- ID continuity unchanged (same new IDs, same boundary insertion). Docstring updated.
- Contract tests in `tests/test_core.py` + identity-continuity test for t ≠ 0.5.
- Precedent entry in `docs/architecture/CORE_V1_FREEZE.md` §7.1 (AD-017), including the `add_edge()`
  note: retained, no active production consumer.
- `tests/mesh.py` is an old Mesh copy (not the Core). Do not modify it.

### 1.2 Shared helpers — `playground/topology_tools/topology_points.py` (new, small, mode-agnostic)

- `VertexPoint(vertex_id)`, `EdgePoint(edge_id, t)` — plain value types.
- `resolve_point(mesh, point) -> VertexId` — vertex as-is; edge → `mesh.split_edge(edge, t)`.
- `connect_in_shared_face(mesh, a, b) -> EdgeId | None` — among faces containing both vertices,
  choose the **lowest FaceId** where they are not adjacent, call `connect_vertices`; `None` if no such
  face (adjacent, no shared face). Deterministic, documented.
- Helpers **never** touch Selection or History and contain no mode logic.

### 1.3 Split mode

- Context: Edge mode, exactly 1 edge selected.
- Reuse `playground/topology_ops.split_selected_edge` (one `MeshStateCommand`, midpoint).
- Residue (**D-S, CONFIRMED, isolated function**): switch to Vertex mode, select the new vertex.

### 1.4 Edge Connect mode

- Context: Edge mode, 2+ edges.
- Reuse `playground/topology_tools/connect_per_face.py` (Artist KEEP). Refactor it onto 1.2 only if
  behaviour stays identical — the 17 tests in `test_connect_lab.py` (per-face parts) must pass unchanged.
- Residue: new connecting edges selected (existing `window.py` behaviour — keep).

### 1.5 Vertex Connect mode — `playground/topology_tools/connect_vertices_per_face.py` (new)

- Context: Vertex mode, 2+ vertices.
- Pairing (implementation, per AD-017): for each face (snapshot at start, ascending FaceId) with ≥ 2
  selected vertices: selected vertices in boundary order, cyclic pairs, adjacent pairs skipped;
  each pair via `connect_in_shared_face` (faces may have split meanwhile).
- Rejection (implementation, justified by the Artist's repeated-Connect workflow): selected vertices
  without a partner are **ignored**; if nothing is created → HUD message, mesh unchanged, **no**
  history entry. Repeating C on an already connected selection is an idempotent no-op.
- Success → exactly one `MeshStateCommand`.
- Residue: selection and mode unchanged.
- Must **not** use its pairing function for Edge Connect or vice versa (Edge Connect's KEEP behaviour
  must not change when Vertex Connect evolves).

### 1.6 Contextual C dispatch — `playground/topology_tools/contextual_c.py` (new, headless)

- `resolve_c_context(selection) -> CContext` with `SPLIT | EDGE_CONNECT | VERTEX_CONNECT | KNIFE | NONE`.
- Rules: `selection.is_empty()` → `KNIFE` (any component mode); Edge mode 1 → `SPLIT`, ≥ 2 →
  `EDGE_CONNECT`; Vertex mode ≥ 2 → `VERTEX_CONNECT`; everything else → `NONE`.
- `window.py` C branch uses it; keep the existing `_articulation_auto_restore()` call before any mutation.

### 1.7 Knife session — `playground/topology_tools/knife.py` (new)

Modal tool on the existing lifecycle (`mirai.interaction.tool.Tool`, same pattern as
`loop_slide.py` / `extrude.py`). Headless-testable; no window code inside.

- `begin`: snapshot `session_before = mesh.export_state()`; no start point; empty step stack; empty
  `path_edges: list[EdgeId]` (the connecting edges, in creation order — excludes split-remnant edges).
- `hover(target) -> preview info` (target kind, prospective position, valid/invalid). No mutation.
- `click(target)`:
  - no start yet: vertex → start = vertex (step recorded, no mutation, nothing appended to `path_edges`);
    edge@t → split at t, start = new vertex (no connecting edge yet, nothing appended).
  - with start: vertex → valid if `connect_in_shared_face` is possible → connect, append the new edge to
    `path_edges`, start = vertex; edge@t → valid if the edge lies on a face containing the start and is
    not incident to the start → split at t, connect start→new vertex (append to `path_edges`), start = new vertex.
  - invalid target → no-op (start unchanged, `path_edges` unchanged).
  - each accepted click pushes a step `(state_before_step, start_before_step, path_edges_before_step)`.
- `undo_step()`: restore the last step's state, start and `path_edges`; empty stack → no-op.
  The undone step is retained for redo: the redo branch stores the popped step plus the
  `(state, start, path_edges)` snapshot taken at undo time.
- `redo_step()`: re-apply the most recently undone cut — restore its post-cut mesh state, start and
  `path_edges`, and push the step back onto the undo stack; empty redo branch → no-op. Any
  subsequently **accepted** click clears the redo branch (mirrors `HistoryStack.push` — no history
  tree); **rejected** clicks do not. `cancel()` and `commit()` discard the redo branch.
- `cancel()`: `load_state(session_before)`; nothing pushed to history.
- `commit()`: if the mesh changed → exactly **one** `MeshStateCommand(session_before → now)`,
  description "Knife"; **residue (DECIDED):** `selection.mode = EDGE`, `selection.set(path_edges)`
  (only edges still valid — see the t-near-endpoint / edge-identity caveats in
  `AD-017_REVIEW_AUTHOR_001.md` Q3). Commit with no mutation → nothing pushed, selection unchanged.
- In-session mutations never push to the global history.
- The start point is **tool state**, not Selection. Selection is only written once, on commit.

### 1.8 Knife picking — `playground/topology_tools/knife_pick.py` (new, playground only)

- Reuse `pick_nearest_vertex`, `pick_nearest_edge`, `pick_face` from `src/mirai/viewport/picking.py`
  (do **not** modify `src/mirai`).
- Order: vertex hit first; else edge hit with **perspective-correct** 3D `t` (closest point between
  the view ray and the edge segment; screen-space t is not sufficient); t within a documented endpoint
  threshold → treat as that vertex; else face hit → "on mesh, no target"; else "outside mesh".
- Hit-testing considers vertices **and** edges in every component mode (follows from the knife's
  Vertex→Edge semantics).

### 1.9 Knife window wiring (`playground/window.py`)

- C with context `KNIFE` → begin session (HUD action line).
- While active (the knife owns these inputs — AD-013 I3/I4):
  - mouse motion → `hover`;
  - **unmodified LMB click** (press + release within the existing click threshold) → `click`;
    click with "outside mesh" → commit; click "on mesh, no target" → nothing;
  - `Enter` → commit; `Esc` → cancel (add to the existing Esc cancel chain like Loop Slide / Extrude);
  - `Ctrl+Z` → `undo_step` (must not reach the global history while the session is active);
  - `Ctrl+Y` → `redo_step` (canonical binding); `Ctrl+Shift+Z` → `redo_step` (alternative gesture —
    the `Ctrl+Z` branch must exclude Shift so it can never swallow `Ctrl+Shift+Z`). Neither gesture
    may reach the global history while the session is active;
  - navigation inputs pass through unchanged;
  - all other keys, including `C`, are ignored during the session.
- Click on release, not on press — keeps a later drag-slide variant possible without redesign.
- **Provisional preview** (clearly labelled provisional in code): highlight the target and draw a line
  from the start to the prospective point, reusing existing overlay/hover infrastructure. Not the final UX.

### 1.10 Retire the Connect Lab switch

- C no longer consults the `connect` experiment family; unregister it in `window.py`
  (the strip variant must not be reachable from C — strip semantics stay rejected).
- Remove the lab variant wrappers and resolver; keep `connect_per_face.py` and its tests; adapt
  `test_connect_lab.py` (drop resolver/slot tests, keep mechanics tests).
- `playground/experiments/connect/decision.md`: status "concluded, integrated into contextual C (AD-017)".
- Keep `connect_edges.py` (Loop Insert depends on it) and the characterization tests F1–F10.

### 1.11 Artist Input Truth — `tools/Input_Mapping_Tool/artist_input_truth.json` (AD-013 A4)

- `topology.connect` → label "Contextual C (Split / Edge Connect / Vertex Connect / Knife)", notes → AD-017.
- Add knife-context entries: commit `Enter`, commit "LMB outside mesh", cancel `Esc`,
  undo last cut `Ctrl+Z`.
- `topology.split_edge` stays on `S`.

### 1.12 Documentation (same change)

AD-017 (confirm implementation, D-S status) · this brief's status · `CORE_V1_FREEZE.md` §7.1 ·
`CONNECT_EDGES_SPEC.md` (note: C no longer uses strip semantics; Loop Insert still does) ·
`experiments/topology/TOPOLOGY_EXPERIMENT_PLAN.md` phase entry · `playground/MANUAL.md` C table ·
`docs/future_ideas/SELECTION.md` → link to AD-017's residue table (no duplicated table).

---

## 2. Must preserve

- `S` = Split (unchanged binding and behaviour).
- Loop Insert and `connect_edges.py` unchanged; characterization tests F1–F10 green.
- Per-face Edge Connect behaviour (Artist KEEP) unchanged.
- `Mesh.add_edge()` unchanged.
- Default `split_edge` behaviour bit-identical; all existing Core contracts (AD-001 monotonic IDs,
  ID continuity, invariants, serialization).
- `Selection` class unchanged — no ordered selection.
- Navigation, AD-016 Q/W/E ownership, existing Esc cancel chain for other tools.
- History semantics of all other operations.
- HUD structure (only action/hint texts added).

## 3. Explicitly out of scope

Face-interior knife points and a face-split primitive (AD-017 B2) · knife mouse-down/drag slide ·
midpoint-snap modifier · final knife preview/cursor UX · ordered selection · cross-face Vertex Connect
paths · Loop Insert changes · reassigning `S` · C meaning for 1 vertex or for faces · knife residue after
commit · occlusion-aware picking · HUD or input-system redesign · promotion of playground code to `src/`
(the only `src/` change is 1.1) · provenance system · removal/deprecation of `add_edge()` ·
any cleanup unrelated to AD-017.

## 4. Tests required

Core (`tests/`):
- `split_edge` t: 0.25 / 0.75 positions; direction relative to `edge_vertices()[0]`; t ∈ {0, 1, <0, >1}
  → `MeshError`, mesh unchanged; default bit-identical to the old midpoint; ID continuity; invariants.

Helpers:
- `resolve_point` both kinds; `connect_in_shared_face`: shared face, adjacent → `None`, no shared face →
  `None`, two qualifying faces → lowest FaceId.

Modes (headless, `tests/mesh_invariants.py` on every result, one history entry on success, none on no-op):
- Split residue: Vertex mode, exactly the new vertex selected.
- Edge Connect: existing per-face tests unchanged; residue = new edges.
- Vertex Connect: hexagon cases from `experiments/topology/vertex_connect_incremental_probe.py`
  (pinning the accepted per-face results), stray vertex ignored, nothing connectable → no-op without
  history, idempotent repeat, residue unchanged, ngon faces.
- Dispatch: every context incl. `NONE` cases; empty selection in each component mode → `KNIFE`.

Knife (headless state machine):
- first click vertex / first click edge; vertex→vertex, vertex→edge, edge→edge chains over ≥ 3 faces;
  arbitrary t placement; invalid targets (no shared face, adjacent, edge incident to start) → no-op;
  `undo_step` sequence matches the Artist example (A→B→C→D, undo, undo); empty-stack undo no-op;
  cancel restores `session_before` exactly (topology; ID counters stay monotonic); commit → one history
  entry; global undo after commit removes the whole session; commit without changes → no entry;
  **commit residue**: Edge mode active, selection == the session's `path_edges` exactly (no split-remnant
  edges, no vertices, no stale IDs).
- In-session Redo (contract extension, DECIDED 2026-09-22): redo after undo reproduces the exact
  session state (mesh, start, `path_edges`); empty redo branch → no-op; undo/redo round-trips are
  state-identical; an accepted click after undo clears the redo branch, a rejected click does not;
  cancel with redo entries restores `session_before` exactly; commit after redo → one history entry;
  **history isolation**: with a non-empty global redo stack, in-session undo/redo never change the
  global stacks' depths nor replay a pre-session state; `Ctrl+Z`/`Ctrl+Y`/`Ctrl+Shift+Z` routing via
  the real `PlaygroundWindow.on_key_press` (headless window, cf. `test_gizmo.py`).

Picking:
- perspective-correct t against known camera setups; endpoint threshold → vertex; vertex priority over edge.

Window (run under `xvfb-run` in CI-less environments):
- C routes per context; knife owns Enter/Esc/Ctrl+Z/LMB while active; navigation still works;
  Esc chain order with other modal tools.

Regression: full `playground/tests/` and Core suite green.

## 5. Inspect first (M1)

- `docs/architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md` (Decision), `AD-017_FINAL_DECISIONS_2026-09-22.md`,
  `AD-017_REVIEW_AUTHOR_001.md` (Q3/Q7/Q8 edge cases)
- `docs/architecture/CORE_V1_FREEZE.md` §7 / §7.1, `AD-013`, `AD-016`
- `docs/research/topology/CONNECT_EDGES_SPEC.md` §10–§11, `CONNECT_NONQUAD_DISCOVERY.md`
- `src/core/mesh.py` (`split_edge`, `connect_vertices`), `src/core/selection.py`, `tests/test_core.py`,
  `tests/mesh_invariants.py`
- `src/mirai/viewport/picking.py`, `src/mirai/interaction/tool.py`
- `playground/window.py` (C branch ~L1340, Esc chain ~L1579, mode keys ~L1445),
  `playground/topology_ops.py`, `playground/topology_tools/{connect_per_face,connect_edges,loop_slide,loop_insert}.py`,
  `playground/experiments/connect/`, `playground/tests/test_connect_lab.py`,
  `playground/tests/test_topology_connect_edges_characterization.py`
- `experiments/topology/{connect_per_face_probe,knife_composition_probe,vertex_connect_incremental_probe}.py`
- `tools/Input_Mapping_Tool/artist_input_truth.json`

## 6. Acceptance criteria

1. All four C contexts behave as decided on `python playground/run.py grid` and `… head`.
2. Knife: chains over ≥ 3 faces with arbitrary t; in-session undo **and redo** (A→B→C / Undo→A→B /
   Redo→A→B→C), Esc, Enter and click-outside commit behave as in AD-017 §8; while a session is active
   Undo/Redo touch only the session's own history (global history never mutated, consumed or replayed);
   one history entry per committed session; on commit the session's connecting-edge
   path is selected in Edge mode.
3. The only `src/` change is `Mesh.split_edge(t)`, with contract tests and the §7.1 precedent entry.
4. Strip Connect is unreachable from C; Loop Insert unchanged.
5. All tests in §4 exist and pass; existing suites stay green.
6. Documents in 1.12 updated in the same change.
7. No behaviour listed in §7 was decided by the implementation; anything unexpected is recorded as an
   open question instead.

## 7. Open UX questions — must NOT be invented by the implementation

- Face-interior knife cutting and whether hover/cutting treats faces like Silo (Artist: most important
  open question) — incl. its effect on "each click creates a cut" (C4).
- Knife preview: hover-only highlight vs. vertex preview timing; cursor presentation.
- Mouse-down slide / drag-slide of the prospective vertex (Silo vs. 3ds Max models).
- Midpoint-snap modifier.
- What a click on an invalid target should do beyond "nothing" (e.g. restart the path there).
- C meaning for 1 selected vertex and for selected faces.
- What `S` becomes.
- Behaviour of `C` pressed during an active knife session.
