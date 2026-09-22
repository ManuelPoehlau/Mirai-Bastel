# AD-017 — Contextual C: Distinct Topology Modes on Shared Split/Connect Helpers

*(File name kept for link stability; the original title "One Cut Engine" was retired by the Artist decision below.)*

**Status:** DECIDED ✓ (2026-09-22) — fully decided, incl. Split and Knife residue
**Date:** proposed 2026-09-21 · decided 2026-09-22
**Owner:** Manu (Project Owner)
**Decision input:** `AD-017_FINAL_DECISIONS_2026-09-22.md` (Artist statement, archived)
**Reviews:** `AD-017_ARTIST_SEMANTICS_2026-09-22.md` (input) · `AD-017_REVIEW_AUTHOR_001.md` (author review, not independent)
**Implementation brief:** `docs/design/artist_playground/WP-AP-CUT_PLAN.md`
**Relates to:** CORE_V1_FREEZE §7 / §7.1, AD-013, AD-016, ARCH-02, `docs/future_ideas/SELECTION.md`

---

## Decision (2026-09-22)

Artist decisions as recorded in `AD-017_FINAL_DECISIONS_2026-09-22.md`, in short:

- **Contextual C:** 1 edge → Split · 2+ edges → Edge Connect · 2+ vertices → Vertex Connect ·
  no selection → Knife. Four distinct modes.
- **No universal operator.** §3 and §5 of the proposal below are **superseded**: there is no shared
  `CutPath`/`apply()`. Shared are only small mode-agnostic helpers (resolve a vertex or edge+t point,
  split at t, connect two vertices through a valid shared face, return created elements). Pairing,
  rejection, interaction state, selection residue and history semantics belong to each mode.
- **Vertex Connect:** Wings-like per-face cyclic pairing; no ordered selection (B3 → B3a).
- **Edge Connect:** Wings-like per-face semantics (Connect Lab KEEP); strip semantics stay rejected.
- **Selection residue (mode-specific):**

  | Mode | After the operation |
  |---|---|
  | Edge Connect | new connecting edge(s) selected |
  | Vertex Connect | selected vertices stay selected, Vertex mode |
  | Split | new vertex selected, mode switches to Vertex |
  | Knife (on commit) | the session's newly created connecting-edge path selected, mode switches to Edge (in-session: new point is the tool-internal knife start, not Selection) |

- **Knife:** incremental explicit path; arbitrary edge position t; two-level history (in-session
  Undo = last cut, Esc = discard session, commit via Enter or click outside the mesh = one history
  operation). Face-interior cutting and the preview/mouse UX are **open**.
- **B1 `split_edge(t)`:** delegated to implementation; the implementation brief resolves it as
  "extend `Mesh.split_edge` with optional `t` (default 0.5, bit-identical)" — see brief §1.1.
- **B2 interior points:** open (Artist question, see brief §7).
- **B4 `add_edge()`:** retained; not removed or repurposed. No active production consumer after
  Connect's strip semantics were rejected; recorded in CORE_V1_FREEZE §7.1.

**D-S — Split residue: CONFIRMED (2026-09-22).** `Selection` stores only the active mode's set
(`src/core/selection.py`), so selecting the new vertex requires switching from Edge to Vertex mode — the
Artist confirmed this literal reading. Consequence: a second `C` right after Split meets "1 vertex
selected", which has no C meaning (no-op).

**Knife residue: DECIDED (2026-09-22).** After a committed session, select the path's connecting edges
(not the split-remnant edges, not the vertices) and switch to Edge mode — mirrors Edge Connect's residue
rule.

The proposal text below is kept unchanged as the record of what was proposed.

---

## 1. Artist statements this AD builds on

Recorded as Artist statements (M4), 2026-09-21:

1. **Connect Lab verdict:** strip semantics (baseline) → **REJECT**; per-face semantics (Wings-like) → **KEEP**.
2. **Intent — one contextual key, modelled on Silo:**

   | Selection | `C` does |
   |---|---|
   | 1 edge | Split |
   | 2+ edges | Connect (edges) |
   | 2+ vertices | Connect (vertices) |
   | nothing | Knife / Cut tool (vertex↔edge, vertex↔vertex, edge↔edge) |

   Rationale given by the Artist: one key whose meaning follows the context is exactly what fast,
   consecutive mesh operations need.
3. **Direction:** the system may be extended / lightly restructured, including `src/core` where justified.

## 2. Problem

The four C contexts are today four unrelated code paths (or missing):

| Context | Today |
|---|---|
| 1 edge → Split | `S`, `topology_ops.split_selected_edge` |
| 2+ edges → Connect | two variants (`connect_edges.py` REJECTED, `connect_per_face.py` KEEP) |
| 2+ vertices → Connect | does not exist (AD-013: "Connect Vertices" deferred) |
| nothing → Knife | does not exist (V1_SPEC §7 wish, no research) |

Discovery D5 showed the practical consequence: *continuing* a cut from an existing point cannot be
expressed with edge selection alone. It needs vertices as endpoints — i.e. the same mechanism a knife uses.

## 3. Key observation (INTERPRETATION, backed by probes)

All four contexts are the **same operation** with different point sources:

> **Insert points on the mesh, then connect consecutive points that share a face.**

| Context | Points | Segments |
|---|---|---|
| Split | 1 edge point (t = 0.5) | none |
| Connect edges (per face) | midpoints of the selected edges | per face, boundary order |
| Connect vertices (per face) | the selected vertices | per face, boundary order |
| Knife | clicked vertices / edge points, in click order | consecutive clicks |

Wings 3D is built the same way (Edge Connect = cut edges → *Vertex Connect* on the new midpoints; see
discovery §2). So the proposal is a **tool-layer unification**, not primarily a Core change.

## 4. What the Core already supports (M1 / Freeze rule step 2)

Checked against the public API, with probes (`experiments/topology/connect_per_face_probe.py`,
and the knife probe recorded in WP-AP-CUT_PLAN §0):

| Need | Public API today | Result |
|---|---|---|
| Point on edge at arbitrary t | `split_edge` + `set_vertex_position` | ✅ works (2 calls, vertex transiently at midpoint) |
| Connect two points in one face | `connect_vertices(face, a, b)` | ✅ any face size; rejects adjacent/degenerate |
| Knife path vertex → edge@t → edge@t → vertex over 3 faces | composition of the two above | ✅ invariants hold |
| Cut with a point *inside* a face | `remove_face` + `add_vertex` + 2× `add_face` | ✅ invariants hold — but the tool layer does face surgery |
| Ordered vertex selection (click order) | `Selection.vertices` is a `set` | ❌ not available |
| Edge pick returning a parameter t | `pick_nearest_edge` returns only the edge id | ❌ not available (src/mirai, not Core) |

**Consequence:** the Artist's model (per-face connect + point-to-point knife) is buildable **without any
Core change.** Core changes are only needed for specific options below. This is stated plainly because
the freeze rule requires the "can it be done with the public API?" check before any Core change.

## 5. Proposal A — tool layer (no Core change)

A single headless **cut engine** in the playground tool layer:

```text
CutPoint  = VertexPoint(vertex) | EdgePoint(edge, t)      # FacePoint only if B2 is chosen
CutPath   = ordered list of CutPoints (knife) or per-face point groups (connect)
apply()   = resolve points (split edges at t) → connect consecutive points sharing a face
contract  = atomic, exactly one MeshStateCommand, mesh unchanged on rejection
```

- `connect_per_face.py` becomes a thin wrapper (points = midpoints).
- Connect Vertices (per face) is a thin wrapper (points = selected vertices).
- Split is the degenerate case (one EdgePoint, no segments).
- Knife feeds the engine an ordered click path.
- Loop Insert stays on its current path until explicitly migrated (discovery D7).
- Location: `playground/topology_tools/` (experiment). Promotion to `src/` is a separate Artist decision (M3).

## 6. Proposal B — Core questions (each needs a decision)

### B1 — `split_edge` with a parameter t

| Option | Description |
|---|---|
| B1a | Keep composition `split_edge` + `set_vertex_position` in the tool layer. No Core change. |
| B1b | Add optional `t: float = 0.5` to `Mesh.split_edge`. Backward compatible; default = today. |

For B1b: atomic; the true geometric relation (edge, t) exists at primitive level — exactly the
information the rigging experiment lacked (FINDINGS-3C, Gap 1: split parent tracking; it fell back to
midpoint-matching heuristics, which break for t ≠ 0.5). Against B1b: not functionally required.
*Agent assessment:* B1b is the smallest Core change with a concrete, documented downstream benefit.
**Decision: Manu.**

### B2 — Cut points inside a face

Product question first: should the knife allow clicking inside a face (not on an edge/vertex)?

| Option | Description |
|---|---|
| B2a | No interior points (Silo/Wings point-to-point). No Core change. |
| B2b | Allow; tool layer composes `remove_face` + `add_face`. No Core change, but face surgery outside Core, against the V1_SPEC mutation-layer principle. |
| B2c | Allow; new Core primitive generalising `connect_vertices`: split a face along a path `a → [interior positions…] → b`. |

*Agent assessment:* start with B2a; if interior points are wanted later, B2c over B2b.

### B3 — Ordered selection

Needed only if "2+ vertices → Connect" should also connect vertices **across faces in selection order**
(Blender "Connect Vertex Path"). Cross-face paths are what the knife does anyway.

| Option | Description |
|---|---|
| B3a | Connect Vertices = per face only (Wings/Silo). Cross-face → knife. No Core change. |
| B3b | Add selection order to `src/core/selection.py` (e.g. insertion-ordered view). Core change. |

*Agent assessment:* B3a — it keeps one mechanism per job.

### B4 — `Mesh.add_edge()` (AP-05 exception)

Its motivating consumer ("kind v" in `connect_edges.py`) is now in the REJECTED baseline, and per
F7 its result was geometrically degenerate. Remaining uses: one test fixture
(`test_topology_loop_insert.py`) and its own contract test.

| Option | Description |
|---|---|
| B4a | Keep; record in CORE_V1_FREEZE §7.1 that its motivating case is gone (no active consumer). |
| B4b | Deprecate: keep code, mark "no consumer, candidate for removal". |
| B4c | Remove from Core together with the "kind v" branch; adjust the fixture. |

*Agent assessment:* B4a or B4b — removal gains little, and a free-edge primitive may matter for later
construction/curve work. **This needs an explicit decision because §7.1 cites it as precedent.**

### B5 — Provenance (ARCH-02) — constraint, not a feature

The cut engine must mutate the mesh **only** through `split_edge` / `connect_vertices` (and B2c if chosen),
so a future provenance layer can hook primitives in operation context (rigging FINDINGS-3C: operation
context is the primary, reliable path). No provenance system is built here.

## 7. Product questions this AD does NOT decide (M4)

- Knife interaction: point-to-point clicks (K1, Silo-like) vs. drag-a-line cutting all crossed edges (K2).
- Knife bindings: finish / cancel / remove last point.
- Residue per C context (what is selected afterwards) — `docs/future_ideas/SELECTION.md`.
- What `S` becomes once Split moves to `C`.
- `C` with exactly 1 vertex, and `C` in face mode.

## 8. Not in scope

Loop Insert migration · stroke knife (K2) · cross-face Connect Vertex Path · provenance system ·
promotion to `src/` · Artist Input Truth changes (happen in the implementation plan, Phase 2).

## 9. Review

Per AGENTS.md §6: an independent review of this proposal should be archived before discussion
(`docs/architecture/AD-017_REVIEW_*.md`), then the decision recorded here (B1–B4).

Archived so far (2026-09-22):
- `AD-017_ARTIST_SEMANTICS_2026-09-22.md` — additional Artist semantics (input).
- `AD-017_REVIEW_AUTHOR_001.md` — author review, **not independent**.
- Independent review: pending.
