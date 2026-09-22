# Work Package: WP-AP-CUT — Contextual C (Split / Connect / Knife)

**Status:** PLANNED — blocked by the AD-017 decision (Phase 0). Nothing implemented.
**Date:** 2026-09-21
**Type (ROADMAP §10):** A (implementation) after AD-017 is decided; Phase 3 contains Discovery variants.
**Architecture document:** `docs/architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md`
**Research basis:** `docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md`, `docs/research/MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §15

---

## 0. Evidence already collected

- Per-face connect on Core primitives: `experiments/topology/connect_per_face_probe.py`,
  playground variant + 17 tests (`playground/tests/test_connect_lab.py`). Artist verdict: KEEP.
- Knife composition on the public Core API: `experiments/topology/knife_composition_probe.py`
  - K1 vertex → edge@0.3 → edge@0.6 → vertex over 3 faces: invariants hold.
  - K3 cut through an interior face point via `remove_face`/`add_face`: invariants hold.
- Gaps found: no edge pick with parameter t (`src/mirai/viewport/picking.py::pick_nearest_edge`
  returns the edge only; its screen-space t is internal), `Selection` is unordered.

## Goal

One key, `C`, whose meaning follows the selection (Artist intent, AD-017 §1), backed by one headless
cut engine, plus an interactive point-to-point Knife for the empty-selection case.

## Why now

Artist verdict on Connect (per-face KEEP) and the D5 finding: continuing a cut needs vertex endpoints —
the knife's mechanism. Without it, local topology control (research §15) stays impractical.

## Scope

1. Headless cut engine (AD-017 Proposal A).
2. Connect Vertices, per face.
3. Contextual `C` dispatch in the playground.
4. Knife K1 (point-to-point, points on vertices and edges only).

## Not in scope

Stroke knife (K2) · interior face points (unless AD-017 B2 decides otherwise) · cross-face Connect Vertex
Path · Loop Insert migration · provenance system · promotion to `src/` · the final residue rule for all
operations · reassigning `S`.

## Dependencies

- AD-017 decisions B1–B4 — **Hard** (Phase 0).
- Core primitives `split_edge`, `connect_vertices`, `set_vertex_position` — **Hard** (exist).
- Modal tool lifecycle begin/update/commit/cancel (WP-02) — **Hard** for Phase 3.
- Input ownership model (AD-013 I3/I4, AD-016) — **Hard** for Phases 2–3: the knife is a modal interaction
  that must own input while active.
- Picking (`src/mirai/viewport/picking.py`) — **Soft**: an edge-parameter pick is added in the playground
  first; promotion to `src/mirai` is a separate decision.

## Phases

### Phase 0 — Decide AD-017 (Artist + review)

B1 split t · B2 interior points · B3 ordered selection · B4 `add_edge()`. Archive an independent review first.

### Phase 1 — Cut engine, headless

- `CutPoint` (vertex | edge@t), engine `apply()`: resolve points → split at t → connect per shared face.
- Rebase `connect_per_face.py` onto the engine; behaviour must stay identical (existing 17 tests unchanged).
- Add Connect Vertices (per face): per face, selected vertices in boundary order, adjacent pairs skipped.
- Rejections atomic; exactly one history entry per operation.
- If B1b is decided: Core `split_edge(edge, t=0.5)` with contract tests first (freeze rule §7 step 5).

### Phase 2 — Contextual C in the playground

| Mode / selection | C |
|---|---|
| Edge, 1 | Split |
| Edge, 2+ | Connect edges (per face) |
| Vertex, 2+ | Connect vertices (per face) |
| none | Knife (Phase 3; until then: no-op + HUD hint) |
| other (1 vertex, faces) | no-op — open Artist question |

- `S` stays Split until the Artist reassigns it (no silent removal).
- Update `tools/Input_Mapping_Tool/artist_input_truth.json` (AD-013 A4) in the same change.
- Retire the REJECTED strip variant from the Connect Lab slot; keep its code until Loop Insert no longer
  depends on it (D7).

### Phase 3 — Knife K1 (interactive)

Mechanics (agent domain):
- Hover snap: vertex first, then edge with perspective-correct parameter t (screen t ≠ 3D t).
- Visible-only candidates (occluded/back-facing edges must not be picked) — known gap in current picking.
- Segment validity: a new point must share a face with the previous point; invalid → preview marked,
  click rejected.
- Preview overlay: committed points, segment to cursor, validity colour.
- Whole cut = one history entry; cancel leaves mesh and history unchanged.

Behaviour variants for the Artist (Discovery, not decided — built as switchable variants):
- Finish: Enter / RMB / click on last point again.
- Remove last point: Backspace / Ctrl+Z inside the knife.
- After finish: stay in knife (continuous cutting) vs. return to selection.

### Phase 4 — Artist test

Prepared task set (≤ 5 min): contextual C on the grid (split → connect → connect vertices → knife);
the D5 continuation task; research §15 L1 (local control without loops leaving the zone).
Verdict KEEP / ITERATE / REJECT / UNKNOWN per behaviour variant, recorded in
`playground/experiments/cut/decision.md`.

## Architecture contracts

- The engine mutates only through Core primitives (AD-017 B5).
- No new binding authority; the knife owns input only while active (AD-013 I3/I4).
- Baseline behaviour unchanged until the Artist verdict (AD-013 A2).

## Tests

- Engine: point resolution, t placement, per-face pairing, multi-face paths, degenerate/adjacent points,
  atomic rejection, one history entry, undo/redo, determinism, `tests/mesh_invariants.py` on every result.
- Regression: characterization tests F1–F10 and Connect Lab tests stay green (or are updated deliberately).
- Dispatch: each C context routes to the right operation (headless resolver test).
- Knife state machine headless: add point, invalid segment, remove last, finish, cancel.
- Edge-parameter pick: perspective-correct t against known camera setups.

## Practical viewport test

Grid scene (`python playground/run.py grid`) and head: all four C contexts, one knife cut over ≥ 3 faces,
cancel mid-cut, undo after commit.

## Documentation

AD-017 decision section · this plan's status · `CONNECT_EDGES_SPEC.md` (superseded semantics note) ·
`TOPOLOGY_EXPERIMENT_PLAN.md` phase entry · `playground/MANUAL.md` C table · `SELECTION.md` observations
on residue collected during Phase 4.

## Definition of Done

All four C contexts work on the grid and the head through one engine; knife K1 behaviour variants are
playable; tests green; Artist verdict recorded; documents above updated. No Core change beyond what
AD-017 decided.

## Open questions (carried)

Knife K1 vs K2 · interior points · residue per context · `S` reassignment · C with 1 vertex / faces ·
Loop Insert migration timing.
