# One Knife — Promotion Plan: Discovery (Architecture Gate)

**Status:** Discovery — Architecture Gate (Type C), **proposal, no decision**. Fresh first impression; archive
unchanged before discussion (AGENTS.md §6). Manu decides (M3); nothing here is Artist-validated.
**Date:** 2026-09-30
**Mode (M5):** Discovery / Architecture Gate
**Belongs to:** `docs/architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md` (+ `AD-017_FINAL_DECISIONS_2026-09-22.md`) ·
`playground/experiments/knife_face/decision.md` (Q5 = KEEP for the Lab state at `f2d34e8`, Artist 2026-09-30) ·
AD-013 · AD-SYM-02 · `docs/architecture/ROADMAP.md` §9/§13 · `REFERENCE_HARDWARE.md`
**Code examined:** `6cbe522` (= `f2d34e8` + `5a00d45` Playground session-state persistence + the Q5 verdict line; the
knife engines are unchanged since `f2d34e8`)
**Probe:** [`experiments/topology/one_knife_parity_probe.py`](../../../experiments/topology/one_knife_parity_probe.py) —
drives the Production `KnifeTool` and the Lab `KnifeFaceCrossFace` (Q5) through their public session interface only
(`activate/begin/accepts/hover/click/undo_step/redo_step/commit/cancel`, Q5 also `set_view`). No Core, Production or
Playground change.

> **Framing (binding, Artist).** There will be **one** Production Knife for vertex, edge and face. Knife and Knife Face
> are Playground scaffolding. Everything below is about *how* the one Knife gets there — not whether.

**Evidence tags**

| Tag | Meaning |
|---|---|
| `[ART]` | Artist statement recorded in the repository or in the handoff §2. |
| `[CODE]` | Code read at `6cbe522`. |
| `[PROBE]` | Output of `one_knife_parity_probe.py` at `6cbe522`, headless in this container (not the reference PC). |
| `[PROBE-INT]` | Output of the existing `knife_integrity_probe.py` (re-run here with `--production`). |
| `[DOC]` | Stated in a repository document (named). |
| `[ASSUMED]` | Plausible, not verified. |
| `[UNKNOWN]` | Could not be established here. |

*Interpretation* is marked as such; everything else is observation.

---

## 0. History Awareness (M1) — additions to the handoff's table

The handoff §1 table was checked against the code and holds, with these additions `[CODE]`:

- **Production is the click variant.** `Application` (`src/mirai/application.py`, "Knife session (WP-06 B7 / B7.1)")
  has no edge lock or slide; press-slide-release exists only as Playground `knife` Variant B (`playground/window.py`,
  `_knife_slide_armed`, `project_locked_edge`). Confirmed (AD-017 §12, `[DOC]`).
- **Click outside the mesh commits only in `Application`** (`_knife_release`: `kind == "outside"` → `_knife_end(commit=True)`).
  Neither Playground session (`knife`, `knife_face`) does it — the Playground only commits on `Enter`
  (`decision.md` build-time finding, `[DOC]`). This is an AD-017 DECIDED behaviour (FINAL_DECISIONS #8, `[ART]`).
- **Q5's resolver is Variant D's**, shared in `engine.py` (`KnifeFaceCollected._walk_run`, `_build_loops`, `_apply_run`,
  `_integrity_problem`), plus Q5's own path/chain handling in `engine_q5.py` and the camera-dependent planner in
  `planner.py`. The planner imports **private** picking functions from `src` (`_edge_point_occluded`, `_point_occluded`,
  `_vertex_occluded`, `_edge_t_3d`); the face-interior pick (`knife_face_pick`) duplicates `pick_face`'s triangle test
  and imports `viewport.derived.triangulate_mesh_face`.
- **AD-017 §6 B5 is a recorded constraint:** "the cut engine must mutate the mesh **only** through `split_edge` /
  `connect_vertices` (and B2c if chosen)" `[DOC]`. Q5's face-interior constructions use `remove_face` + `add_vertex` +
  `add_face` (B2b). This matters for §3.
- **AD-017 decision #1: no universal Cut Engine** `[ART]`. A promoted Knife resolver must stay Knife-owned (Split /
  Edge Connect / Vertex Connect do not route through it).

Nothing about merging the two was ever rejected; the only prior statements are the Artist requirement (one tool) and
"KEEP ≠ promotion" `[ART]`.

---

## 1. Task 1 — Parity matrix: Production Knife vs Q5

### 1.1 Method

Same click lists, written as world positions, played on a fresh mesh per engine; each target is resolved against that
engine's *current* mesh (Production has already cut, Q5 has not); a click on a point the Q5 session holds becomes the
snap target `{"kind": "path", ...}`, as the window's 14 px snap makes it. After commit: position-canonical faces (ids
ignored, winding kept), selection residue as position pairs, selection mode, History length, Undo/Redo of the entry, and
a geometry check (area, simple polygon, facing, total area of the reference surface, `assert_mesh_invariants`) `[PROBE]`.
Code-only rows (preview, bindings, HUD) are marked `[CODE]` and were **not rendered**.

### 1.2 Run results `[PROBE]`

| # | Clicks (scene) | Production | Q5 | Mesh / residue |
|---|---|---|---|---|
| P01 | edge → edge, one quad (grid) | `++`, 1 entry, 1 edge selected | same | **same / same** |
| P02 | vertex → vertex diagonal | `++` | `++` | **same / same** |
| P03 | vertex → edge → edge → vertex, 3 quads (AD-017 §4) | `++++` | `++++` | **same / same** |
| P04 | zig-zag edge chain, 4 points | `++++` | `++++` | **same / same** |
| P05 | closed diamond on 4 edges, back to the first point | `+++++` (connects to its split vertex) | `+++++` (snap → close, cyclic) | **same / same** |
| P06 | cube: chord across the top corner | `++` | `++` | **same / same** |
| P07 | cube: closed ring over four sides | `+++++` | `+++++` | **same / same** |
| P15 | head: edge rings of 3 / 6 / 10 midpoints, 10 start faces each | — | — | **same / same and clean in 30/30** |
| P08 | vertex → adjacent vertex (along an edge) | 2nd click **refused** (`hover` says valid) | 2nd click **accepted as "skip"** (break "edge"), nothing cut | same (unchanged) |
| P09 | two points on the same edge | 2nd **refused**; commit keeps the 1st split: **V+1/E+1, History 1**, residue empty | both accepted, skip; **no change, no History** | **different** |
| P10 | edge → edge, faces share nothing | 2nd **refused** (`hover` says valid); commit keeps the split | accepted, planner: 2 cuts over 2 quads | **different** |
| P11 | one edge click, `Enter` | **V+1/E+1 committed, History 1**, residue empty (Edge mode) | nothing, no History ("no complete cut") | **different** |
| P12 | one vertex click, `Enter` | nothing | nothing | same |
| P13 | same vertex twice | 2nd refused (`hover` says valid) | 2nd refused ("already the last point") | same |
| P14 | edge click, then click outside (engines only) | click refused; commit keeps the split | refused; nothing | **different** |
| S1 | A→B→C→D, Undo, Redo, commit (AD-017 redo workflow) | = no-undo result | = no-undo result | **same** |
| S2 | … Undo, Undo, commit | A→B | A→B | **same** |
| S3 | … Undo, new click E, Redo | Redo is a no-op (branch cleared) | same | **same** |
| S4 | … Undo ×4 (everything), `Enter` | **History 1 with unchanged content** (an empty Undo step) | History 0 | same mesh, **different History** |
| S5 | edge click → Undo → clicks → Esc | the edge click cuts the mesh during the session; Undo and Cancel restore | nothing changes before commit; Undo and Cancel restore | same result |

`accepts() == click()` held for every click of both engines. Production `KnifeTool.hover()` is looser than `accepts()`
in P08/P10/P13 — documented in `knife.py`; `Application` previews through `accepts()`, the Playground `knife` family
through `hover()` `[CODE]`.

*Interpretation:* S4 is a Production defect (the `commit` "nothing changed" test compares the whole state including the id
counters, which `load_state` only moves forward — the same slip Task B fixed in the Lab, `decision.md`). P09/P11/P14
leave a vertex on an edge with no cut — the `Application` itself reports "no cuts made, nothing committed" for a
cut-free session, which suggests this is unintended; not decided anywhere.

### 1.3 The matrix

**Same (code and run):** one History entry per session; Undo/Redo of the entry; residue = connecting-edge path selected,
Edge mode (AD-017 DECIDED); in-session Undo = last click/cut, Redo re-applies, a new click clears the redo branch
(S1–S3); Cancel restores exactly (S5); `accepts()` as preview gate (Q5: `accepts() = plan().ok`); B8 pick cache +
occlusion (`knife_face_pick` wraps `knife_pick` with the same `cache`/`occlusion`, `_pick_kwargs()` in the Playground,
`display.show_faces` in `Application`) `[CODE]`; 5 % endpoint snap of an edge target to its vertex (same `knife_pick`)
`[CODE]`; session keys `Enter` / `Esc` / `Ctrl+Z` / `Ctrl+Y` / `Ctrl+Shift+Z` and the key gate (`_session_owns_key` treats
`knife` and `knife_face` identically; `KNIFE_CONTEXT` in Production) `[CODE]`; click-vs-drag threshold `[CODE]`; the cut
itself for every edge/vertex-only sequence both engines accept (P01–P07, P15) `[PROBE]`, with the same Core calls
(`split_edge`, `connect_vertices` only, §3) `[PROBE]`.

**Production only:**

| # | Behaviour | Evidence |
|---|---|---|
| G1 | **Live point marker at `t` while hovering an edge** (`KnifeRenderData.prospective_point`, preview layer). Q5 draws the edge highlight and — once a chain exists — the pending line ending at `t`, but **no marker at `t`**; before the first click it shows *nothing* at `t`. Vertex hover (snap square) and face hover (point) have a marker. Manu's claim is **confirmed** in code; not rendered. | `[CODE]` `knife_preview.py`; `window.py` `_knife_face_refresh_hover_q5`, `_kfq5_rebuild_hover` (`snap_position` is set only for vertex targets, `engine_q5.plan`) |
| G2 | **Click outside the mesh = commit** (AD-017 DECIDED). Q5 in the Playground: rejected, `Enter` only. | `[CODE]` `application.py` `_knife_release`; `[DOC]` decision.md build-time finding |
| G3 | **The mesh is really cut during the session** — shaded result, new vertices pickable by the normal vertex pick. Q5 shows overlay lines/dots; the mesh changes at `Enter`. (Allowed by `[ART]` §2: the undo *behaviour* is fixed, the model is an implementation choice.) | `[CODE]`, S5 `[PROBE]` |
| G4 | **Production wiring**: `Application` session routing, status line, `knife_render_data` built from `KnifeTool.start` / `path_edges` (Q5 has no `start`; its `path_edges` stay empty until commit), selection-history record on commit, pick-cache invalidation per click. | `[CODE]` |
| G5 | History description `"Knife"` (Q5: `"Knife Face (Cross-Face)"`). Not shown anywhere today `[ASSUMED]`. | `[CODE]` |

**Q5 only** (all `[CODE]` + `decision.md`; Artist-played and KEEP'd as a whole, `[ART]`): face-interior points (9 px
edge margin); cross-face segments through the planner, visible part only, gaps skipped; crossing cuts → one
intersection vertex; loops closed at a single point (own face + 1 bridge to an outside corner; bow-tie); closed interior
shape (2 bridges); close on the chain start without commit, continuation seeded at the closing vertex; click on an
earlier boundary point connects and continues; last click inside a face joined to the nearest corner **at commit**;
"cutting back the same way does nothing"; commit-time integrity check with whole-session rollback; dropped runs leave no
trace; "nothing changed" ignores id counters; HUD messages (N/M cuts applied, skips, loops); snap to the session's own
points (14 px); segments along an existing edge are skipped, not refused (Lab default, P08/P09).

**Differing:** P08, P09 (refuse vs skip), P10 (refuse vs plan across), P11/P14 (lone split committed vs nothing), S4
(empty History entry vs none), R3/R5 (broken Production geometry vs clean Q5, §4), hover validity vs acceptance
(Production `hover()` looser, Q5 identical), in-session feedback (real cut vs overlay, G3).

**Unknown:** how the two *feel* side by side (only the Artist); timings on the reference PC (§2.3); Production vs Q5 on
imported meshes with concave n-gons beyond the L-face case (§4); rendering of the preview (not rendered here).

### 1.4 Is Q5 a superset?

**Not as it stands.** *For the mesh result:* on every edge/vertex-only sequence Production accepts completely, Q5
produced the identical mesh and residue (P01–P07, 30/30 head rings) `[PROBE]`, and no sequence was found that Production
accepts and Q5 refuses. Where they differ, Q5's result is the clean one (P09/P11/P14/S4, R3/R5). *For the interaction:*
Q5 lacks G1 (Manu's gap — confirmed), **G2 (click outside commits — a DECIDED AD-017 behaviour Manu's list does not
mention)** and the Production wiring G4; G3 is a deliberate model difference. So: "Q5 ⊇ Production" holds for cut
results in the probed space, not for the interaction.

---

## 2. Task 2 — Session model (implementation choice; the visible behaviour is fixed by `[ART]` §2)

### 2.1 Options

- **(A) Real cuts, resolver extended incrementally.** Today's `KnifeTool` model: each click mutates the mesh; in-session
  steps are full mesh snapshots. Interior points cannot be cut on their own (a dangling line is not a face boundary), so A
  still has to hold **pending** interior points and resolve a run when it reaches a boundary — Variant B's shape, which
  the Artist REJECTED for being unable to start inside a face or close a shape `[ART]`; A needs D/Q5's resolver for those
  runs anyway.
- **(B) Q5's virtual path, resolved at commit.** What the Artist played and KEEP'd.
- **(C) Hybrid: virtual path + a throw-away preview mesh.** After each click the whole path is resolved on a copy of the
  session-start mesh and that copy is shown; commit applies the same resolution to the real mesh.

### 2.2 Comparison (same criteria for all three)

| Criterion | (A) real cuts | (B) virtual path (Q5) | (C) hybrid |
|---|---|---|---|
| Undo / Redo A→B→C | literal: snapshot per click (S1–S3 pass today) | path snapshot per click (S1–S3 pass) | as B |
| Cancel | restore snapshot | restore (mesh untouched) | drop the copy |
| One History entry | yes | yes; commit may **roll back** as a whole and return `None` | as B |
| Crossing cut (a segment crosses an earlier cut) | the earlier cut is real; the later run must split *session-created* edges (a new "crossable" rule — Q5's rule is "edge between two pieces of one click-time face") | built: `_walk_run` + intersection vertex, 0/400 fuzz failures `[DOC]` | as B |
| Loop closed at a point / bow-tie | the run is pending until it reaches a boundary, then resolved like B at that click | built (`_build_loops`, dependency order) | as B |
| Close on an interior start + continuation | simpler: the loop is built at the closing click, the seed is a real vertex | placeholder vertex bound at commit (`anchors`) | as B |
| Snap to own points | boundary points: normal vertex pick; interior points: needs Q5's snap anyway | Q5 snap (14 px) | as B, but the shown copy has vertices picking cannot reach |
| Preview = result | mostly (real geometry); pending interior runs are overlay | **no**: dropped runs, tail join and rollback appear only at `Enter` (the tail join *must* not show while cutting `[ART]`) | closer, but the tail join must still be left out → not identical either |
| Feedback on a failing segment | immediate: the click is refused | at `Enter` ("N-1/N"); hover shows skips/crossings, not drops | immediate |
| Determinism / testability | result depends on the mutation sequence; replay needs the same clicks | result = f(session-start mesh, path): pure, fuzzable — 84 Q5 tests + 400-run fuzz exist `[CODE]` `[DOC]` | as B, plus a second render mesh to test |
| Cost (head, this container, four runs) `[PROBE]` | per click 0.6–1.2 ms (snapshot + cut); `load_state` 1.9–2.6 ms per undo | per click 0.6–1.1 ms (it still snapshots the unchanged mesh — avoidable); **commit 3.8–6.3 ms (4 points), 6.8–12.2 ms (8 points)**; hover plan 0.1 ms (shared face), **1.1–3.0 ms across 2–7 faces with the pick cache**, 15–84 ms without | per click ≈ B's commit (grows with the session) + a render-mesh rebuild per click |
| `Tool` lifecycle fit | as today | fits (heavy `commit`, may return `None`) | fits; the viewport must render a mesh that is not `scene.mesh` — new viewport plumbing |
| Symmetry (AD-SYM-02, consideration only) | each click would cut both sides at once; the mirrored intent is not stored | the path *is* the intent: mirroring it before resolution matches "the other side comes from the mirrored intent" (§2.4) and one Operation / one entry | as B |
| Provenance (ARCH-02, consideration) | per click only | whole intent available at commit | as B |
| Re-validation cost (M1) | high: everything Tasks A/B, loops, bow-tie, tails, integrity settled must be rebuilt incrementally and re-played | low: the KEEP'd code | medium: B + preview plumbing |

**Reference PC** (Core 2 Quad Q9550, `REFERENCE_HARDWARE.md`): nothing was measured there. *Assumed* `[ASSUMED]`: a few
times slower per core than this container; B's commit on a long session on the head would then be tens of ms — once, at
`Enter`. Hover without the pick cache is the only number here that would be noticeable; the Playground already passes
the cache, Production has one (`Application._pick_cache`).

*Interpretation:* (B) is the only option whose behaviour the Artist has actually judged; (A) re-derives it; (C) pays
per-click resolution and viewport plumbing and still cannot show the commit-time join. B's real costs are
"preview ≠ result" at `Enter` and a commit that can roll back — both already visible in the Lab.

---

## 3. Task 3 — Core / primitives

| What Q5's resolver does | Built from (public Core API) | `[PROBE]` / `[CODE]` |
|---|---|---|
| point on an edge at `t` | `split_edge(e, t)` | Core since AD-017 B1b |
| straight chord in one face | `connect_vertices` | Core |
| path split through interior points (`split_face_path`, FC1–FC4) | `remove_face` + `add_vertex` + 2× `add_face` (B2b) | FC1/FC3/tail: `add_face 2, add_vertex 1, remove_face 1` |
| closed interior shape, 2 bridges (`close_loop_with_bridges`) | `remove_face` + `add_vertex`×k + 3× `add_face` | `add_face 3, add_vertex 3, remove_face 1` |
| loop at a point, 1 bridge (`close_loop_at_vertex`, pinched ring) | `remove_face` + `add_vertex` + 3× `add_face`, retries via `load_state` | `add_face 3, add_vertex 2, remove_face 1` |
| intersection vertex on an earlier cut | `split_edge` | HB1: `split_edge 4` |
| rollback of a dropped run / whole session | `export_state` / `load_state` | `[CODE]` |
| geometry checks (area, simple, winding, facing) | tool-side (`FaceFrame`, `face_problem`, `_integrity_problem`) | `[CODE]` — Core checks none of this (H7: `add_face` accepts repeated vertices, `KNIFE_FACE_CUT_DISCOVERY.md`) |

Edge/vertex-only sessions — Production's whole scope — call **only** `split_edge` and `connect_vertices` in both engines
(P04, P07; P10 in Q5) `[PROBE]`.

**Answer.** *No Core change is technically needed* — shown, not assumed: every construction above runs on today's
public API, and the Lab's fuzz found 0/400 integrity failures `[DOC]`, the probe's cases are clean `[PROBE]`. **But** the
face-interior constructions are B2b, which contradicts the recorded AD-017 B5 constraint ("only `split_edge` /
`connect_vertices`, and B2c if chosen") and the mutation-layer principle behind it `[DOC]`. So promotion needs **one
explicit decision** either way:

- **K0 — no Core change:** amend AD-017 B5 to allow B2b inside the Knife's resolver in `src/mirai/topology/`, with the
  resolver's own validation (the integrity check) as the guard. Cheapest; face surgery stays outside Core; provenance
  sees "face removed, vertex added (no parent), faces added".
- **K1 — B2c, the smallest Core extension:** one additive primitive of the shape already sketched in
  `KNIFE_FACE_CUT_DISCOVERY.md` §3 — `Mesh.split_face(face, v_a, v_b, positions=()) → (new vertices, new edges, face_1,
  face_2)`, adjacent ends allowed with ≥ 1 position, `MeshError` and unchanged mesh on any violation, no geometric checks
  (like `connect_vertices`), `connect_vertices` untouched. **Sufficiency checked** `[PROBE]` (`--b2c`): both bridge
  constructions are exactly two calls of that shape — the closed shape (bv1 → arc → bv2, then loop[i2] → other arc →
  loop[i1]) and the loop at a point (x → c1..cj → bridge end, then cj → c(j+1).. → x) give the **same faces** as the Lab's
  dedicated functions on the grid. So one primitive covers FC1–FC4, closed shapes and loops at a point; the tool keeps the
  bridge *policy*. Needs the freeze-rule steps (CORE_V1_FREEZE §7: requirement, API check — done here —, AD, tests).

Not Core but `src/mirai` (also needs deciding with the promotion): the planner's use of **private** picking functions
(`_edge_point_occluded`, `_point_occluded`, `_vertex_occluded`) and a face pick that returns a **position** (H1:
`pick_face` returns only the id; `knife_face_pick` duplicates the triangle test). Both belong to `mirai.viewport.picking`
/ `mirai.topology.knife_pick`, not to the resolver — keeping the resolver camera-free (as D/Q5 already are) keeps it
headless-testable and out of the viewport layer.

---

## 4. Task 4 — Defects R3 / R5

| Case | Production `KnifeTool` | Q5 | Evidence |
|---|---|---|---|
| **R3** (HD2): after a split leaves a straight-angle vertex at (1.5, 1), vertex (1,1) → edge point (1.75, 1) | both clicks accepted; commit → **zero-area face**, History 1 | both accepted; the segment is "along the boundary" → skipped, **no change** | `[PROBE]` `--defects`; `[PROBE-INT]` `--production`: `zero_area` |
| **R5**, concave n-gon (an L-shaped hexagon, e.g. imported): vertex (2,1) → vertex (1,2) across the missing corner | accepted; commit → a **flipped** triangle outside the face, **faces cover 4.0 instead of 3.0** (overlap) | accepted; the straight line leaves the face → planner → nothing visible to cut → skipped, **no change** | `[PROBE]` |
| **R5**, L1 on the grid (concave face from an earlier bent cut) | accepted; → **non-simple** face | 3/3 cuts, clean (cut across both faces) | `[PROBE]`, `[PROBE-INT]` `non_simple, tri_area` |
| A click-time gate on the Production chord (Lab's `segment_in_face`) | R3 chord: `"boundary"`; R5 chord: `"outside"` — both detectable at click time | — | `[PROBE]` |

**Observation outside the question (raises priority):** the same R3 shape through the **promoted** Contextual C modes —
after one Split, *Vertex Connect* on (1,1) + (2,1), or *Edge Connect* on the two halves of the split edge — leaves two
zero-area faces **and an edge with 4 faces** (`assert_mesh_invariants` fails) `[PROBE]`. Vertex Connect goes through
`connect_in_shared_face`, Edge Connect through its own lowest-id face search; neither checks geometry `[CODE]`. Reachable
in `src/main.py` by ordinary selections `[ASSUMED]` (not played).

**Standalone fix ahead of the promotion — options (none recommended by default):**

- **F0 — none:** wait for the one Knife (Q5 fixes R3/R5 for the Knife); Contextual C stays exposed.
- **F1 — Knife only:** a geometric gate in `KnifeTool.accepts/click` — refuse a chord that is not *inside* a shared face.
  Small, one file. Visible difference to the future one Knife: F1 **refuses** where Q5 **skips** (R3) or **cuts across**
  (R5) — a temporary behaviour the Artist would see.
- **F2 — shared face choice:** `connect_in_shared_face` (and Edge Connect's copy of the search) take only a face whose
  interior holds the chord, else refuse. Fixes Knife *and* Vertex/Edge Connect, including the invariant break; touches a
  promoted helper of three modes (AD-017 ownership: modes own their rejection rules — this changes all three at once).

*Agent assessment (not a recommendation):* the root causes were recorded as defects against decided behaviour, not
Artist questions (`decision.md`, "Root causes") — so F1/F2 are engineering decisions. F2 is the only one that closes the
invariant break in Vertex/Edge Connect; F1 would be superseded by the one Knife. Either way it is independent of which
§6 option is chosen.

---

## 5. Task 5 — Capability vs UX (AD-013)

| Part | Kind | Owner | Today |
|---|---|---|---|
| Session engine: virtual path, in-session undo/redo, cancel, one `MeshStateCommand`, residue rule | capability (+ decided semantics) | AD-017 / Production | `KnifeTool` (Prod) · `_KnifeFaceSession` (Lab) |
| Resolver: runs, walk through current faces, crossing vertex, loops + bridges, tail join, integrity check / rollback | capability | Production after promotion (Knife-owned — no universal engine) | `engine.py`, `engine_q5.py` |
| Planner: segment → visible crossings with the click's camera | capability (camera input passed in, I2) | Production after promotion | `planner.py` |
| Picking: vertex/edge/`t`/face + position, occlusion, endpoint snap | capability | `mirai.viewport.picking` / `knife_pick` | Prod + Lab duplicate |
| Bridge *policy* (nearest outside corner, 2 bridges), tail join to the nearest corner, "along an edge = skip", earlier point connects, closing on the start | product rules decided by the Artist or flagged Lab defaults | Artist (decided ones) / open (Lab defaults) | `decision.md` |
| HUD / status texts, preview style (lines, dots, snap square, `t` marker), colours | UX | Production UX (PROVISIONAL until a verdict) | Prod status line / Lab HUD |
| Snap radius 14 px, edge margin 9 px, endpoint snap 5 % | UX parameters | Production UX | constants |
| Bindings: `C` start, `Enter` / click outside commit, `Esc`, `Ctrl+Z` / `Ctrl+Y` / `Ctrl+Shift+Z` | UX (Artist Input Truth, A4) | Artist Input Truth | same keys in both; outside-click only in Prod |

**Playground consequences:**

- Families today: `knife` (A live preview, B press-slide) uses the Production `KnifeTool`; `knife_face` (B REJECT,
  D superseded, Q5 KEEP) uses the Lab engines; `C` with an empty selection starts whichever family is focused (`Tab`), `M`
  cycles its variants `[CODE]`. After the one Knife: **one** family whose default variant is the Production tool; `knife`
  Variant B (press-slide) survives only as an interaction variant if wanted (AD-013 A2), B/D of `knife_face` are archive
  material (decision.md keeps the record). `decision.md` gets a pointer, not a rewrite.
- **Key conflicts:** none in the key map — both sessions own exactly `Enter`, `Esc`, `Ctrl+Z`, `Ctrl+Y` (`_session_owns_key`)
  `[CODE]`. The one conflict is **LMB outside the mesh**: commit in Production, rejected in the Playground. Artist Input
  Truth has no entry for the in-session Redo (`Ctrl+Y` / `Ctrl+Shift+Z`) — note only.
- Session state persistence (`5a00d45`) stores the focused family and the active variant by class name `[CODE]` — a
  renamed or retired family/variant falls back per entry (its tolerant load); worth one line in the retiring slice.

---

## 6. Task 6 — Migration: options, recommendation, slices

### 6.1 Options

| | **M1 — Promote Q5 (model B) in slices** | **M2 — Grow `KnifeTool` (model A)** | **M3 — Replace in one step** |
|---|---|---|---|
| What | Move the KEEP'd resolver/planner into `src/mirai/topology`, then switch the one `KnifeTool` to it feature by feature | Keep real cuts; port interior points, cross-face, loops, bridges, tails into `KnifeTool` one at a time | Swap `KnifeTool` for Q5 (+ G1/G2/G4) in one slice |
| For | reuses what the Artist judged (M1 "do not rebuild"); pure resolver, existing 84 + 33 Lab tests and fuzz; fits AD-SYM-02 (intent stored) | preview = result for boundary runs; immediate refusal; no commit-time surprises | fastest to "one tool" |
| Against | preview ≠ result at `Enter`; commit may roll back; Lab code needs hardening (identity by `id()` — one CPython id-reuse bug was already found; ~2 700 lines) | re-implements and re-validates everything Q5 settled; still needs pending (virtual) runs; Artist sees a *different* implementation of the same behaviour | largest change at once; hard to bisect; one practical test for everything |
| Core | K0 or K1 (§3) | K0 or K1 (§3) | K0 or K1 |

**Recommendation (agent, not a decision): M1** — with K1 (B2c) decided before the face-interior slice and F2 as a
separate, independent fix. Reason: it is the only path whose behaviour already has an Artist verdict, it keeps one
implementation from the first slice on (AD-013 I1), and every slice is revertable. M2 is the fallback if the Artist
finds "cut happens at `Enter`" wrong in the practical test of slice 2 — that is the one visible property M1 changes
for today's Production users.

### 6.2 Slices (M1)

| Slice | Goal | Scope | Not in scope | Tests | Practical viewport test | DoD (ROADMAP §9) |
|---|---|---|---|---|---|---|
| **S1** resolver home | one implementation of the resolver in `src` | move (not copy) the camera-free resolver out of `engine.py`/`engine_q5.py` into `src/mirai/topology/`; Playground Q5 imports it; private-by-`id()` identity replaced by explicit point ids; K0 amendment *or* K1 primitive | Production `KnifeTool`, `Application`, planner, picking, UX | Lab tests move with it and pass unchanged in meaning; probe output unchanged; `tests` + `playground/tests` green | Playground Q5: Manu's recorded sequences (cube bow-tie, tail join) look as before | docs: AD-017 amendment (or new AD), ROADMAP intake line, decision.md pointer |
| **S2** one `KnifeTool`, vertex/edge | Production Knife on model B with today's scope | `KnifeTool` session on the virtual path for vertex/edge targets; `Application` render data from the path (+ **G1 marker at `t`**); click outside commits (G2); P11/P14/S4 behave like Q5 | face targets, planner (cross-face still refused), Playground families | parity rows P01–P15/S1–S5 as tests (Production = Q5 results); R3/R5 cases clean | `src/main.py`, head: today's click sequences; watch "cut at `Enter`" | Artist verdict on S2 (PROVISIONAL until then) |
| **S3** face points | interior points, notch, closed shapes, loops at a point, tail join | production face pick with position (H1) + 9 px margin | planner | FC1–FC4, closed shape, P1–P6, tail cases | the Face Cut tasks of decision.md §Tasks | verdict |
| **S4** cross-face | planner with the click's camera, visible part, snap to own points, close/continue, earlier point | planner in `src`, public picking helpers | Knife V2 (drag), Symmetry Knife | Q5 cross-face tests; hover cost with cache | Q5 tasks 1–6 in Production | verdict |
| **S5** one family | Playground: one knife family | retire `knife_face` into `knife`; `M` variants; session-state fallback | new variants | playground tests | `Tab`/`M` walk | decision.md + EXPERIMENT_HOST pointer |

Ordering: S1 → S2 → S3 → S4 → S5; F2 at any time; K1 (if chosen) inside S1. Rollback: each slice is one revertable
commit series; S2 keeps the old `KnifeTool` body until its verdict *only* if Manu wants a fallback — otherwise git revert.

### 6.3 Draft WP spec — S1 (for a later Type A handoff; not started)

```text
# Work Package: WP-KNIFE-01 — One Knife, slice 1: resolver home

## Goal
One authoritative implementation of the Knife's commit-time resolver in src/mirai/topology/,
shared by the Playground Q5 variant; no Artist-visible change anywhere.

## Why now
One Knife is an Artist requirement; the resolver is the KEEP'd part (decision.md, 2026-09-30) and
the base of every later slice. Moving it first makes the Core question (§3) explicit before any UX work.

## Scope
- Move the camera-free resolver (run splitting, _walk_run, _build_loops, _apply_run, tail join,
  _integrity_problem, the B2b/B2c constructions) from playground/experiments/knife_face/ into
  src/mirai/topology/ (name decided in the handoff); the Lab engines import it.
- Replace identity-by-id() with explicit point ids (the id-reuse bug class, decision.md).
- Implement the accepted Core option: K0 (AD-017 B5 amendment, no Core change) or K1 (Mesh.split_face,
  additive, freeze-rule tests).

## Not in scope
KnifeTool, Application, picking, planner, HUD/preview, bindings, Playground families, Vertex/Edge Connect
(F2 is separate), Face Holes, Cut Through, Knife V2, Symmetry Knife.

## Dependencies
Manu's decision on this document (option + K0/K1). AD-017 amendment or new AD.

## Architecture contracts
AD-017 #1 (Knife-owned, no universal engine); AD-001 id continuity; one MeshStateCommand per session;
Core freeze rule for K1; resolver stays camera-free (I2).

## Tests
Lab resolver tests (test_knife_face_q5.py, test_knife_face_lab.py) green without meaning changes;
new src tests for the moved functions incl. the integrity fuzz (seeded); K1: primitive contract tests
(ids, MeshError + unchanged mesh, adjacency rule); one_knife_parity_probe.py and knife_integrity_probe.py
outputs unchanged.

## Practical viewport test
Playground Q5 on the cube: Manu's bow-tie and tail-join sequences give V:13 E:21 F:10 / V:14 E:22 F:10 as recorded.

## Documentation
AD-017 amendment; ROADMAP WP-06 intake line; decision.md pointer; this document's §6 status line.

## Definition of Done
One resolver in src, used by the Lab; both suites green; probes unchanged; no visible change; docs updated.
```

### 6.4 Risks

- **Preview ≠ result** (model B): a run can drop or the session roll back at `Enter`. Mitigated today by hover skips,
  crossing dots and the commit message; the Artist has played it. Open: whether Production needs a pre-commit warning.
- **Lab code hardening:** `id()`-keyed dicts, ~2 700 lines, private picking imports, a viewport import in the Lab engine.
- **Cost on the reference PC:** unmeasured; commit grows with session length; hover needs the pick cache.
- **Contextual C stays exposed** to R3 (invariant break) until F2.
- **B2b without Core validation** (K0): only the resolver's own check guards `add_face` (H7).
- **Symmetry later:** a mirrored path crossing the seam is unexplored.

### 6.5 Decisions for Manu (not Artist questions)

1. Accept M1 / M2 / M3 (or none yet). 2. K0 or K1. 3. F0 / F1 / F2, and when. These are Promotion / Core decisions (M3).

### 6.6 Artist questions (M4 filter)

Only one behaviour is genuinely open and would change what slice S2 ships; everything else is decided `[ART]` or an
engineering matter.

**AQ1 — A click along an existing edge (neighbour vertex, or a second point on the same edge):** today Production
**refuses** it (the start stays); Q5 **accepts** it, cuts nothing and continues from there — a Lab default flagged "not a
decision" (`engine_q5.py` docstring). *5-minute test:* Playground, `grid`. (1) `knife` family: click a vertex, then its
neighbour along an edge, then a vertex across the next quad. (2) `knife_face` Q5: the same three clicks, `Enter`. Which
is right: "refused, I stay where I was" or "accepted, I walk along the edge and continue"? If unanswered, S2 keeps the
KEEP'd Q5 behaviour.

**Assumptions stated, not asked (M2 — correct only if wrong):** a session that cuts nothing leaves the mesh untouched
(P11/P14: no lone vertex after one edge click + `Enter`); click outside the mesh keeps committing (AD-017); the `t` marker
on edge hover returns (G1).

Carried over from `decision.md`, not asked now (do not block the promotion): an earlier **interior** point as a target;
whether vertices created earlier in the same commit are tail-join candidates; where a piece ends next to a gap on curved
surfaces.

---

## 7. Confidence per task

| Task | Confidence | Basis |
|---|---|---|
| 1 Parity | **documented** for the listed sequences (grid, cube, head rings) / **code-only** for preview, bindings, HUD | probe + code; nothing rendered |
| 2 Session model | **documented** (A/B behaviour, costs here) / **assumed** (reference PC, C's viewport cost, A's rebuild effort) | probe timings in this container |
| 3 Core | **documented** (public API suffices; B2c shape suffices for both bridge constructions on the grid) / **assumed** (B2c on non-planar faces) | probe `--core`, `--b2c` |
| 4 R3/R5 | **documented** (reproduced; Q5 clean; Contextual C exposure) / **assumed** (reachability in `src/main.py`, not played) | probe `--defects`, `knife_integrity_probe.py --production` |
| 5 Capability/UX | **documented** from code and AD-013 | code |
| 6 Plan | **proposal** | derived from 1–5 |

## 8. Not investigated

- The two engines side by side in a real window (no rendering here; G1 is a code reading, as the handoff noted).
- Timings on the reference PC; Production `Application` hover timings with the Q5 planner.
- Concave n-gons beyond the L face and the head; orthographic views.
- B2c on non-planar faces and on the cube's folds (the `--b2c` check is on the grid only).
- A mirrored (symmetric) path; provenance records — hook points only.
- Edge Connect / Vertex Connect R5 (concave faces) — only R3 was probed there.
- Knife V2 (drag), Cut Through, Face Holes — out of scope.

## Appendix — probe output (excerpt, long lines shortened with …) `[PROBE]`

```text
[PROBE] P15 head, 3-point edge rings: mesh + residue identical and clean in 10/10
[PROBE] P15 head, 6-point edge rings: mesh + residue identical and clean in 10/10
[PROBE] P15 head, 10-point edge rings: mesh + residue identical and clean in 10/10
[PROBE] S4 A->B->C->D, Undo x4 (everything), commit
      prod: V25/E40/F16; history 1; content changed False; residue 0; …
      q5  : V25/E40/F16; history 0; content changed False; residue 0; …
[PROBE] R3 (HD2) session 2 on prod: clicks ++; V28/E45/F18; history 1; content changed True; broken ['have no area'] …
[PROBE] R3 (HD2) session 2 on q5: clicks ++; V27/E43/F17; history 0; content changed False; broken none …; msg 'no complete cut; 1 stretch(es) skipped …'
[PROBE] R5 (concave L face) prod: clicks ++; V6/E7/F2; history 1; content changed True; broken ['a face flipped', 'faces cover 4.0000 instead of 3.0 (overlap)']
[PROBE] R3 via Vertex Connect (production, shared helper): 2 edge(s) created; broken ['have no area', 'have no area',
        'invariants: Edge EdgeId(42) ist an mehr als 2 Faces angehängt (4)']
[PROBE] closed shape, 2 bridges: Lab 3-way split V29/E46/F18 vs two path splits V29/E46/F18; same faces: True
[PROBE] loop at a point, 1 bridge: Lab V28/E45/F18 vs two path splits V28/E45/F18; same faces: True
[PROBE] head, 8-point edge ring: per click prod 0.65 ms, q5 0.59 ms; commit prod 0.56 ms, q5 6.98 ms; q5 hover plan (shared face) 0.09 ms
[PROBE] head q5 hover across 7 faces (planner, cache on): 3.00 ms; plan ok True, 13 crossing(s)
```

Run: `python experiments/topology/one_knife_parity_probe.py` (all sections, ~1 min) or one of `--parity --session
--defects --core --b2c --cost`.
