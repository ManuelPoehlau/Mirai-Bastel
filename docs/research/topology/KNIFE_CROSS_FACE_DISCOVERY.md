# Knife — Cross-Face Segments (Q5): Discovery

**Status:** Discovery — Research Package (Type B), **no decision**. Fresh first impression; archive
unchanged before discussion (AGENTS.md §6).
**Date:** 2026-09-29
**Mode (M5):** Discovery
**Belongs to:** [`KNIFE_FACE_CUT_DISCOVERY.md`](KNIFE_FACE_CUT_DISCOVERY.md) §6 (Q5 assessment — the starting
point; not repeated here) · `playground/experiments/knife_face/decision.md` (Variant D = KEEP, 2026-09-29) ·
Artist intent A5 (2026-09-28) · ARCH-02 (`docs/architecture/ROADMAP.md`)
**Code examined:** `main` @ `52d52b8` (Knife Face Cut Lab, Variants B/D)
**Probe:** [`experiments/topology/knife_cross_face_probe.py`](../../../experiments/topology/knife_cross_face_probe.py)
(public Core API + existing read-only helpers; drives Variant D's engine through `click()`/`commit()`;
no Core, Production or Lab change)

> **Framing (binding, Manu).** Knife and Knife Face become **one** Production tool for vertex, edge and
> face. Q5 is therefore treated throughout as **segment resolution inside the one Knife**: how a click
> whose target lies in another face turns into cuts in every face in between. It is not a third tool and
> not a property of the "Knife Face" family; the two Playground families are discovery scaffolding. How the
> two families are unified is out of scope (§11 lists it as an open question only).

> This document answers X1–X9 of the Q5 discovery brief. It makes no product decision and no Core
> decision. Observation and interpretation are kept apart; every external claim carries an evidence tag.

**Evidence tags**

| Tag | Meaning |
|---|---|
| `[SRC]` | Read in published source code (not executed): Blender `editmesh_knife.cc` main @ `363df9d` and `editmesh_knife.c` tag `v2.79`; Wings 3D `wpc_connect_tool.erl` master @ `8ae2bfd`. Line numbers refer to those revisions. |
| `[ART]` | Artist statement (recorded in the repository or in the brief). |
| `[CODE]` | Mirai code read at `52d52b8`. |
| `[PROBE]` | Output of `knife_cross_face_probe.py`, run at `52d52b8` + this probe. Numbers are quoted from its output. |
| `[ASSUMED]` | Plausible, not verified. |
| `[UNKNOWN]` | Could not be established here. |

---

## 0. History Awareness (M1) — what this builds on

Verified against the code `[CODE]`:

- Every Knife in the repository requires consecutive points to share a face: Production `KnifeTool`,
  Playground `knife`, `knife_face` B and D (`KnifeFaceCollected.accepts`, `engine.py:694-743`).
- Variant D keeps a **virtual path** of click dicts (`vertex` / `edge`+`t` / `face`+`position`) and changes the
  mesh only at commit (`_resolve_path`, `engine.py:887-938`): the path is cut into per-face **runs** between
  boundary points; each run is applied with `connect_in_shared_face` (no interior points) or `split_face_path`
  (with interior points); all run-end edge points are resolved once, several points on one edge in `t`
  order (`_resolve_boundary_points`). Leading/trailing interior points are dropped (FC5 rule).
- The A5 lock (`_face_cut_lock`, `engine.py:678`, set in `click`, `engine.py:754-763`) blocks a face click right
  after a `[boundary, interior+, boundary]` run completed, i.e. exactly the "cut → interior click in the
  neighbour face" move.
- The window's close-on-start (`playground/window.py:1676-1692`) commits **without** appending anything when
  `path[0]` is a face point and the click lands within 14 px of it (gap 1 in `decision.md`).
- D's resolver has **no camera**: `commit()` takes no view argument (`engine.py:940`); picking
  (`knife_face_pick`) is the only camera-dependent part.
- Control for any Q5 Lab: "Hangeln" — clicking every intermediate edge — already works in D (confirmed by
  Manu `[ART]`); the probe reproduces it as an edge → crossing → crossing → edge path, accepted by D **as
  built** (P1, below).

Nothing about Q5 was ever rejected; it was excluded from the Face Cut Lab so it would not confound that
verdict `[ART]` (A5).

---

## 1. X1 — References: only the gaps Q5 needs

§1 and §6 of the Face Cut discovery already establish *that* Blender and Wings resolve one segment into
cuts in every crossed face. Filled in here: how each handles the Q5 edge cases.

### 1.1 Blender (main and 2.79 — same mechanism) `[SRC]`

| Q5 question | Blender |
|---|---|
| How are crossings found? | `knife_find_line_hits` (main l. 2777): a plane through the **eye** and both segment ends (main: `cross(v1 - eye, v2 - eye)`, l. 2811-2822; 2.79 builds the same plane from the two unprojected screen rays), BVH-intersected; every candidate edge is intersected with that plane (`isect_ray_plane_v3`, l. 2992) and kept if its screen position lies on the 2D segment. The comment at l. 2988 explicitly rejects screen-space interpolation along the edge ("doesn't work with perspective transformation"). |
| When are they computed / fixed? | Recomputed on every mouse move while a cut is in progress (`knife_update_active`, l. 4091-4097) — this is the preview. Consumed on click by `knife_add_cut` (l. 2305ff), which immediately creates virtual `KnifeVert`s/`KnifeEdge`s in 3D. After that the view no longer matters; view navigation during the knife is allowed (`KNF_MODAL_PANNING`, l. 4470). **Crossings are fixed at click time.** |
| Crossing preview dots | Yes. `linehits` are drawn as points during the cut: vertex hits (snapped) larger (11 px), edge/face hits smaller (7 px) (l. 989-1029; 2.79 draws `linehits` too, l. 1100). |
| Segment passes (almost) through a vertex | Vertex hits are collected **first**: a vertex whose projection lies within `KNIFE_FLT_EPS_PX_VERT` = **0.5 px** of the screen segment is a hit (constants l. 2891-2893, test l. 2909-2930); edges incident to a hit vertex are skipped (l. 2947-2950); an edge hit within 0.05 px of its end is dropped (l. 2987); near-duplicates are merged in `prepare_linehits_for_cut` (l. 1870). Same constants in 2.79 (l. 90-92). |
| Occluded crossing | `point_is_visible` (l. 2623) casts from the hit towards the eye; any face in front → the hit is **dropped** (unless *Cut Through*). No normal/back-face test — only occlusion. |
| What happens to the faces around a dropped / missing hit | Hits are grouped per face (`facehits`, l. 2339-2366); `knife_cut_face` cuts only faces with **≥ 2** hits (l. 2066-2076). A face that loses one of its hits (occluded, beyond the border) is simply not cut: **the cut gets a gap, the click is not refused.** |
| Segment leaves the mesh / into empty space | An end in space has no face hit (`use_hit_prev`/`use_hit_curr`, l. 3015-3019); edge hits along the line still count → faces with two hits are cut up to the border edge. Not refused. |
| Concave face / chord outside the face | Rejected per face: `knife_add_single_cut__is_linehit_outside_face` and `knife_verts_edge_in_face` (l. 2003-2014). |

### 1.2 Wings 3D — Tools → Connect (`wpc_connect_tool.erl`) `[SRC]`

| Q5 question | Wings |
|---|---|
| How are crossings found? | 2D segment between the two vertices' **current** screen positions (`get_line`, l. 481). From the faces around the current vertex, every edge not touching an already-used vertex is intersected with the line (`check_possible`, l. 394) — also intersections with the line's *extension* (`{false,{1,…}}`, lower priority). One is chosen by priority (`select_way`, l. 439): front-facing and on the segment > vertex on a front face > front-facing, extension only > back face… Then the mesh is **cut and connected immediately** and the walk repeats from the new vertex until start and end share a face (`connect_link1`, l. 370; `connect_done`, l. 421). |
| 3D position of a crossing | `pos2Dto3D` (l. 473-479): linear interpolation of the **screen** fraction along the edge — not perspective-correct (the case Blender's comment warns about). |
| Vertex pass-through | Intersection parameter within `?EPS` = 1e-6 of an edge end → vertex hit (`{point,3}`/`{point,4}`, l. 538-539, consumed at l. 411-414). Parametric, not pixels: effectively exact. |
| Back faces | Face normal vs view (`check_normal`, l. 463, threshold z > 0.1); back faces only as a lower priority fallback. **Loop Connect** (key `1`) runs the walk a second time with inverted normals — the connection is also cut around the back (l. 357-368). |
| Failure (no candidate, border, silhouette) | `select_way([])` exits (l. 437); the exception is caught in `do_connect`/`connect_edge` (l. 296-307, 318-327) → **nothing happens** (silent refusal; partial mutations of the same `wings_sel:mapfold` are discarded with it `[ASSUMED]`). |
| Preview | A plain 2D rubber band from the last vertex to the cursor (`draw_connect`, l. 589-601); no crossing dots. |

### 1.3 Summary

| | Blender | Wings | Mirai today |
|---|---|---|---|
| Crossing model | plane through eye ∩ edges, perspective-correct | screen-line walk, screen-linear `t` | none (consecutive points must share a face) |
| Fixed at | click | click (mesh mutates immediately) | — |
| Vertex tolerance | 0.5 px | 1e-6 (parametric) | pick radius 14 px for *clicked* vertices |
| Hidden part of the segment | skipped → gap in the cut | back faces deprioritised; Loop Connect cuts around | — |
| Failure | partial cut, never refused | whole connection refused silently | — |
| Crossing dots | yes | no | — |

Silo, Maya, 3ds Max: no new evidence searched for (§12); §1 of the Face Cut discovery stays their state.

---

## 2. X2 — Segment resolution in Mirai

### 2.1 The shape of the answer `[PROBE]`

A **planner** turns "last path point → clicked target" into the ordered list of crossings — edge points
`(edge_id, t)` or vertices — and inserts them into D's virtual path *before* the target. D's resolver then
applies them **unchanged**: every consecutive pair shares a face by construction, so each becomes an ordinary
per-face run.

| Probe case | Path fed to D | Result |
|---|---|---|
| P1 grid, edge → 3 quads → edge | `[edge, e13@0.40, e16@0.50, edge]` | **D as built** (lock on): `3/3 cut(s) applied`, invariants OK, `{4: 16} -> {4: 18, 5: 1}`, one history step |
| P7 head, face → 11 crossings → face | `[face, e83@0.98 … e115@0.24, face]` | D as built: `10/10 cut(s) applied`, leading/trailing interior dropped, invariants OK, `{4: 324} -> {3: 8, 4: 316, 5: 10}` |
| P5 concave L-face, line leaves and re-enters it | `[edge, e2@0.80, e3@0.20, edge]` (faces L, square, L) | `3/3 cut(s) applied`, invariants OK |
| P8 closed loop over 4 quads (cyclic path) | see §5 | `4/4 cut(s) applied`, 0 bridges |

ID continuity in every applied case `[PROBE]`: all old vertices keep their IDs, replaced faces become
invalid, every new V/E/F id is above the previous maxima (AD-001), exactly one history entry per commit.

**Observation.** Q5 needs no second resolver. The whole difference to D is the planner plus what it stores
(§3). D's `accepts()` still validates planner output: it rejects a pair of points that share no face
(P4 hole) and a vertex–vertex pair along an existing edge (P3 collinear) `[PROBE]`.

### 2.2 Two planners compared

- **WALK (Wings-like, topological):** start in the face of the last point, find where the 2D screen segment
  leaves it (nearest edge crossing, or a vertex within the tolerance), step into the face across that
  element, repeat until the target face/edge/vertex is reached *and* the line does not leave the face again
  before the target. `t` on the edge is taken perspective-correctly from the ray through the 2D crossing
  (the Knife's existing `_edge_t_3d`).
- **PLANE (Blender-like, global):** intersect every edge with the plane (eye, A, B); keep hits whose
  projection lies on the segment; vertices within 0.5 px first; optionally drop hits hidden behind a face
  (the B8 test `_edge_point_occluded`).

| Criterion | WALK | PLANE |
|---|---|---|
| Crossing positions | identical: on the head, where both return the same elements, max \|Δt\| = **4.0e-14**; grid 7e-16 `[PROBE]` P1, P6. Mathematically the same thing: the plane through eye, A, B meets an edge exactly where the edge's projection crosses the screen segment. | ← |
| Correct on `grid` | yes (P1–P5) | yes (P1) |
| Correct on `head` (non-planar quads, H2) | 146 / 150 random visible face→face segments identical to PLANE(visible); 3 differ only by one extra edge hit right before a vertex hit (walk crossed the edge at t ≈ 0.97 before snapping to the vertex in the next face — a tolerance-ordering artefact, not a different path); 1 fails after walking onto a **back-facing** face at a silhouette `[PROBE]` P6. Non-planarity itself caused no failure: crossings are on edges, and edges are straight. | Finds the other side of the head in 148 / 150 segments — without the occlusion filter those would be cut too. In 1 / 150 the visible hits do **not** form a face-connected chain (the segment passes a silhouette and continues on a surface further back) `[PROBE]` P6. |
| Occlusion consistency with B8 | follows connectivity; hidden crossings are possible only after a silhouette and are detectable with the same B8 test (0 occluded crossings in the 149 successful head walks) | needs the B8 test on every hit, plus a "chain" check before D can use it |
| Hole / border (P4) | stops: `mesh border edge crossed` after the first crossing | returns hits on both sides of the hole; fed to D, `accepts()` rejects the jump |
| Determinism | deterministic for a given camera; ties at a vertex resolved by the sector test (face around the vertex whose screen corner contains the line direction) | deterministic; order by screen parameter |
| Cost (pure Python, no cache, head) | **≈ 0.5 ms** per segment | **≈ 20–24 ms** per segment (all 648 edges + occlusion per hit) — hover-rate only with a BVH/cache `[PROBE]` P6 (timings vary per run) |

**Interpretation.** The two planners differ not in *where* they cut but in *which* crossings they admit and
how they fail. WALK only ever produces a face-connected chain (what D's resolver needs) and fails loudly at
borders/silhouettes; PLANE mirrors Blender's "skip what cannot be cut" and needs two extra filters
(occlusion, chain) before D can consume it. A hybrid is possible (WALK for the path, the B8 test to refuse
or cut short when a crossing is hidden). Which failure behaviour is right is a product question (X9, A-Q1),
not a technical one.

---

## 3. X3 — Camera dependency (finding)

`[PROBE]` P9, same A and B, crossings recomputed under different cameras:

- **Planar surface (`grid`):** camera-independent. Every plane through the eye, A and B meets the grid
  plane in the line AB. `cam(20,35)` vs `cam(50,20)`: same edges, max |Δt| = 1.7e-15. One exception, and it
  is the **tolerance**, not the geometry: under `cam(-30,60)` two crossings 0.007 / 0.015 world units from a
  vertex fall inside 0.5 px and snap to vertex `v12` (`[e13, v12, e27]` instead of
  `[e13, e16@0.99, e19@0.98, e27]`); with tolerance 0 the results are identical again.
- **Non-planar surface (`head`):** camera-dependent. 30 segments × 3 orbits:
  - yaw +10°: 2 different edge sequences, 10 with |Δt| ≥ 0.05, 18 with small shifts;
  - yaw +25°, pitch −10°: 5 different sequences, 17 with |Δt| ≥ 0.05, 3 walks fail under the new view;
  - yaw +45°, pitch +10°: 6 different sequences, 16 walks fail (end hidden, silhouette, overshoot).
  - Example: `[e70@0.330, e71@0.830, e195@0.938, e223@0.279, e82@0.860]` becomes
    `[e70@0.293, e71@0.776, e195@0.772, e223@0.806, e82@0.961]` after yaw +25°; max 3D shift of a crossing
    0.16 (head radius 3.37).

**Finding (agent-decidable, evidence clear).** The crossings of a segment must be fixed **at the click that
completes the segment, with the camera of that click** — the view in which the preview line was shown. They
must not be recomputed at commit: D resolves at commit, and a commit after an orbit would otherwise cut along
a different curve than the one previewed, or fail. What to store per segment: the ordered crossings as
`(edge_id, t)` / `vertex_id` — exactly the point dicts D already stores for clicks. This is safe in D
because nothing mutates before commit, so the stored IDs stay valid until the resolver runs (P1–P8 apply them
without a camera). Storing the eye position per segment would be equivalent but forces the resolver to
recompute with a camera; the crossing list is the smaller, resolver-ready form. Blender does the same (crossings
become virtual 3D knife vertices at click, §1.1) `[SRC]`.

Consequences:

- the first point of a segment can be clicked in one view and the target in another; only the second view
  matters (the first point is a fixed 3D point);
- one click then adds **several** path entries (target + its crossings); in-session undo must remove them as
  one step (today `_push_step` runs once per `click()`) — a Lab requirement, not a Core one;
- the vertex tolerance (0.5 px) is screen-space, so the snap decision is also fixed at that click.

---

## 4. X4 — Endpoint and crossing cases

All on the 4×4 `grid`, camera `(20°, 35°)`, fed to D with the A5 lock cleared, unless noted `[PROBE]`.

| Case | Probe result | Classification |
|---|---|---|
| face → neighbour face | walk `[e13@0.45]`; D as built **rejects** the second face click (A5 lock); without lock: `no complete cut` — both ends interior, dropped (FC5 rule) | valid segment; produces a cut only once the path is anchored on both sides (see note) |
| face → face, 3 quads | `[e13@0.475, e16@0.425]` → `1/1 cut(s) applied` (middle quad only) | valid; end faces need anchoring (FC5) |
| face → edge | `[e13@0.50, e16@0.50]` → `2/2 cut(s)`, leading interior dropped | valid |
| edge → face | `[e13@0.46, e16@0.42]` → `2/2 cut(s)`, trailing interior dropped | valid |
| vertex → edge | `[e13@0.167, e16@0.333]` → `3/3 cut(s)` | valid (start face chosen by the line direction) |
| edge → 3 quads → edge | `3/3 cut(s)`, D as built accepts it | valid — this *is* "Hangeln" in one click |
| face → face, then interior clicks in the far face, then edge | `2/2 cut(s)`, sizes `{4: 14, 5: 2, 6: 2}` | valid — crossings and interior points mix in one path |
| exactly through a vertex (diagonal) | tolerance 0: walk **fails** under the oblique camera (edge hit at t = 1.0, no exit); 0.5 px: `[v6]` → `2/2 cut(s)`, two triangles `{3: 2, 4: 15, 5: 1}` | valid with a vertex rule; **a vertex tolerance is required**, 0.5 px (Blender) worked in all three views |
| 0.002 units past the vertex (≈ 0.2 px) | tol 0: `[e1@0.996, e6@0.998]` → a sliver 0.002 long; tol 0.5 px: snaps to `v6` | tolerance prevents slivers |
| 0.02 units past (≈ 1.7–2 px) | 0.5 px: no snap, `[e1@0.96, e6@0.98]`; 5 px: snaps | intended geometry kept; 0.5 px is not over-eager |
| collinear with grid edges `v(0,1) → v(3,1)` | walk `[v6, v7]` (vertex hits along the edges); D `accepts()` rejects vertex → adjacent vertex | **rejection rule candidate:** a run that coincides with an existing edge cuts nothing (Blender skips it, l. 1998-2001) — skip or refuse is open |
| concave face left and re-entered (L-face, P5) | walk `[e2@0.80, e3@0.20]`, faces L → square → L, `3/3 cut(s)`, invariants OK | valid; the walk must not stop at the first touch of the target face. Without crossings, D accepts the direct chord `a → b` (both on L) although it runs through the square — D does **no** geometric in-face check |
| mesh border / hole (quad (1,1) removed) | walk fails `mesh border edge crossed`; plane hits both sides, D rejects the jump | **open:** refuse the click, or cut up to the border (Blender) — A-Q1 |
| cursor beyond the border | `knife_face_pick` → `outside`; in D a click there is *commit*, never a target | no segment case — "click outside = commit" is unaffected |
| silhouette / back face (head) | 1 / 150 walks entered a back-facing face and failed; PLANE found a hidden surface in 148 / 150 | **open:** refuse vs skip hidden part — A-Q1; cut-through — A-Q2 |

**Note on A5 and the FC5 rule.** A5 describes "start in face 1, cursor over neighbour face 2 → one click cuts
through both faces" `[ART]`. Under D's existing resolution rule (KEEP'd), a path whose *both* ends are interior
points cuts nothing, and a path whose start is interior cuts nothing in the start face (P2) — the
cut through both faces appears once the path reaches a boundary on both sides (or closes, §5). This is D's
known interior-end behaviour carried over, not a new Q5 rule; it belongs in the Artist test's "Expected".

---

## 5. X5 — Interaction with D's known gaps

**Closed loops across faces need no bridges** `[PROBE]` P8, variant (c): every run of a loop that crosses
face boundaries ends on crossings (edges), so each face is split by an ordinary run.

| Loop | (a) as built: close-on-start click | (b) closing segment + new click on the start | (c) path rotated to start and end on the **same** crossing object |
|---|---|---|---|
| 4 quads around vertex (2,2) | `2/2 cut(s)`, lead + tail dropped — 2 of 4 faces cut | `3/3 cut(s)` — 3 of 4 | `4/4 cut(s)`, invariants OK, `{4: 16} -> {4: 16, 6: 4}`, 8 cut edges, **0 reach an original vertex (no bridge)** |
| 2 quads, straddling one edge | `1/1` — 1 of 2 | `1/1` — 1 of 2 | `2/2 cut(s)`, `{4: 16} -> {3: 1, 4: 15, 7: 1, 8: 1}`, 5 cut edges, 0 bridges |

- **Gap 1 becomes a correctness gap for cross-face loops** (record only, not fixed). The window's
  close-on-start commits without adding the closing segment, and the resolver then drops the leading and
  trailing interior points. For a single-face loop that is harmless (the all-interior branch closes it
  implicitly); across faces it silently leaves part of the loop uncut (a). Clicking the start position again
  does not help either (b): the new click is a *different* point, so the first face keeps a dangling end.
  (c) shows what a working close would need: the closing segment's crossings, and the loop resolved
  cyclically so that it starts and ends on one shared crossing.
- **Gap 2 becomes more visible.** A cross-face loop is closed by aiming at a point that may sit in a
  different face than the cursor's current one, after several crossings; the 14 px zone gives no hover
  feedback, and a click just outside it adds a new point instead (b's situation) — the Artist cannot tell
  which of the two happened before commit.
- Gap 3 (undo on the virtual list): unchanged in kind; one click = several entries (§3) must undo as one.
- Gap 4 (bridges instead of holes): not triggered by cross-face loops (0 bridges above); still triggered by a
  loop that stays inside one face.

---

## 6. X6 — Preview and the A5 lock

- **The lock loses its reason in a Q5 variant.** It exists only to keep a neighbour-face interior click from
  *looking* like a cross-face cut while none was implemented `[CODE]` (`engine.py:670-678`). The probe had to
  clear it for exactly one pattern: `[face, crossing, face]` (P2, D as built rejects it). Paths with ≥ 2
  crossings or boundary starts passed D **with** the lock on (P1, P7), because the lock is recomputed on every
  boundary-kind click and only a face click right after a completed run is blocked. In a Q5 variant the
  planner's crossings are exactly those "completed runs", so the lock would fire on every neighbour click —
  it has to go in that variant (the B/D Face Cut variants keep it).
- **Line preview.** The window draws a polyline through all path positions plus the hover target, gated by
  `hover()["valid"]` = `accepts()` (`window.py:1826-1836`) `[CODE]`. With the planner's crossings stored in the
  path, the committed part of the line already runs through them. For the *pending* segment, the preview needs
  the planner at hover time: `accepts(target)` for a face/edge/vertex outside the last point's faces becomes
  "the planner reaches it". This follows from the existing gate — no new rule — as long as the planner runs on
  hover (WALK: 0.5 ms; PLANE: too slow without a cache, §2.2).
- **The line stays straight on screen.** Every crossing lies on the 2D segment and every chord between two
  crossings projects onto it, so the preview polyline drawn through the crossings looks like the straight
  rubber band the Artist aims with, on the head as on the grid `[ASSUMED]` from the construction; not rendered.
- **Crossing dots need a new preview element.** Today only `face`-kind path entries are drawn as pending
  points (`_rebuild_knife_face_pending_vbo`, `window.py:1088-1106`) and the hover draws one point at the
  target. Blender's dots (§1.1) would be a new overlay for the hover-time planner result (and, after the
  click, for stored crossings) — additive, but not implied by `accepts`.
- **Refusal feedback.** If the planner fails (border, silhouette, hidden crossing), `accepts` → invalid → no
  point, no line (today's rule for invalid targets). Whether that is enough is part of A-Q1.

---

## 7. X7 — Core / ARCH-02

**Confirmed: Q5 needs no Core change beyond what Face Cut needs** `[PROBE]` `[CODE]`. Per segment with k
crossings: k × `split_edge(e, t)` + k + 1 runs, each either `connect_vertices` (via `connect_in_shared_face`,
existing Core) or the Face Cut split (`split_face_path`, the lab's B2b stand-in for a possible B2c). Stronger:
a cross-face segment **without interior points** (edge/vertex → edge/vertex: P1, P2 vertex → edge, P3) uses
**only** `split_edge` + `connect_vertices` — today's public Core API, no stand-in at all. Only runs that contain
face-interior points need the Face Cut primitive.

Not checked by the Core (tool/planner responsibility, as for Face Cut): a chord leaving a concave face (P5
direct chord accepted), the choice between two faces that share both run ends (`connect_in_shared_face` takes
the lowest id), vertex tolerance.

**Provenance a cross-face segment exposes — hook points only:**

1. **One intention → many operations.** One click = one segment = k edge splits + k + 1 face splits. A grouping
   key per segment (click index in the session) is the natural anchor for "these operations were one user
   intent" — the same grouping in-session undo needs (§3).
2. **Per crossing: `(edge_id, t)` at creation** — the interpolation weights for any attribute on the new vertex,
   same argument as AD-017 B5 for `split_edge(t)`.
3. **Per run: the parent face** and its two children (as for Face Cut, B2c sketch in the Face Cut discovery §3).
4. **The view that defined the segment** (eye position or the stored crossing list) — the only non-topological
   input; ARCH-02 has to decide whether "cut along the curve seen from view X" is part of the record or only
   its result.

No framework proposed.

---

## 8. X8 — Lab options (≤ 3, all variants of the existing `knife_face` family, built on D)

All options: D's session, virtual path, commit-time resolver, history (one entry per commit) and residue stay
as they are. Added: a planner at hover and click time; crossings stored in the path at click time (§3); one
undo step per click; the A5 lock removed in these variants only. No new family, no Production structure;
the control is D as built ("Hangeln").

| Variant | Planner / failure behaviour | Preview | Risk |
|---|---|---|---|
| **Q5-a — Walk, refuse** | WALK, vertex tolerance 0.5 px. A target the walk cannot reach (border, hole, silhouette, a crossing hidden by the B8 test) is **invalid**: no line, click rejected, HUD reason. | line through crossings + crossing dots | refuses more often than Blender at silhouettes; walk quirks near vertices (P6: 3 / 150 extra near-vertex hits) |
| **Q5-b — Walk, cut what is visible** | WALK up to the first failure point, then (Blender-like) the visible, face-connected part is cut and the rest skipped; the click is accepted and the HUD names the skipped part. | as Q5-a, plus the skipped part drawn in a distinct "no cut" style | a click cuts less than the line suggests (Wings-like mismatch §5 of the Face Cut discovery); where the path continues after a gap is a rule to invent |
| *(optional)* **Q5-c — Q5-a + cyclic close** | as Q5-a; clicking the start point of a path that crosses faces adds the closing segment and resolves the loop cyclically (P8 (c)). | as Q5-a | touches gap 1, which the Artist accepted as "not a blocker" — build only if A-Q3 says cross-face closed shapes matter |

PLANE is not proposed as a Lab variant: where both planners succeed they cut identically (§2.2), so the
Artist would not feel the difference; Q5-b covers Blender's user-visible behaviour on top of the cheaper walk.
Cut-through (Blender) / Loop Connect (Wings) is not proposed until A-Q2 asks for it.

### Prepared Artist test (M4) — ≤ 5 min per variant, same format as `decision.md`

- Start: `python playground/run.py grid` (flat 8×8 quads) and `python playground/run.py head`.
- `Tab` until `knife_face` is focused, `M` cycles the variants (D control, Q5-a, Q5-b[, Q5-c]).
- `C` with an empty selection starts the Knife. `Enter` or click outside = commit, `Esc` = cancel,
  `Ctrl+Z` / `Ctrl+Y` = in-session undo / redo (one click = one step, including its crossings).

**Tasks** (same for every variant; the control D does them by clicking every intermediate edge):

1. **Grid — straight across:** click an edge of a quad, move the cursor over two more quads, click the far edge
   of the third. Watch the line and dots before clicking. Commit.
2. **Grid — interior through the neighbour:** click an edge, click inside the quad, click inside the
   *neighbouring* quad, finish on an edge of that quad. Commit.
3. **Grid — start inside, cross over:** first click inside a quad, then click inside the next quad, then an
   edge of it. Commit.
4. **Head — across the cheek, then over the nose:** from an edge on one cheek, click 3–4 quads away on the same
   cheek; then aim at the other cheek so the line passes the nose silhouette. Commit.
5. **Head — orbit between clicks:** click a point, orbit ~25°, click the target (the line seen now is the cut).
   Commit and compare with what the line showed.
6. **Grid — closed loop over 4 quads:** four interior clicks in the four quads around one vertex, then click the
   first point again. Commit.

**Expected, not a verdict on the variant:**

- Task 1: all Q5 variants cut three quads in one click; D needs two extra edge clicks.
- Task 2: cuts both quads (the path is anchored on edges at both ends).
- Task 3: the first quad is **not** cut — the interior start has no second anchor (D's FC5 rule, unchanged);
  the neighbour quad is cut.
- Task 4: Q5-a refuses the click over the nose silhouette (no line); Q5-b cuts the visible part and says what it
  skipped. Differences show only there — across one cheek all variants cut the same.
- Task 5: the cut follows the line seen at the second click.
- Task 6: as built (and Q5-a/b), closing on the start point cuts only part of the loop (gap 1, §5); Q5-c closes
  it without bridges.

**Observe:** does the line + dots read as "this is what will be cut"? Is refusing (Q5-a) or cutting partially
(Q5-b) at the silhouette what Manu expects? Does task 3's untouched start face surprise? How many attempts per
task, where does frustration appear?

#### D — control (Hangeln)

**Verdict:** _KEEP / ITERATE / REJECT / UNKNOWN_

#### Q5-a — Walk, refuse

**Verdict:** _KEEP / ITERATE / REJECT / UNKNOWN_

#### Q5-b — Walk, cut what is visible

**Verdict:** _KEEP / ITERATE / REJECT / UNKNOWN_

#### Q5-c — Q5-a + cyclic close (only if built)

**Verdict:** _KEEP / ITERATE / REJECT / UNKNOWN_

---

## 9. X9 — Questions only the Artist can answer (M4 filter)

Answered here instead of asked: which planner (§2 — same cut; failure behaviour is A-Q1), camera timing (§3),
vertex tolerance (§4), Core need (§7), bridges for cross-face loops (§5 — none).

**Taken from A5, not asked (M2 — correct if wrong):** one segment crosses **any number** of faces, not only the
next one. A5 names the neighbour face as the example and "Blender-like" as the reference; Blender crosses every
face on the line (§1.1).

- **A-Q1 — Where the line cannot be cut** (hole, mesh border, over a silhouette onto a surface further back, or
  a stretch hidden behind the model): should the click be **refused** (nothing happens, HUD reason — Wings) or
  should the **visible part be cut** and the rest skipped (Blender)? From Silo memory, what happens?
- **A-Q2 — Visible only, or through:** should a cross-face segment ever cut the hidden side as well (Blender
  *Cut Through*, Wings *Loop Connect*)? If yes, as a toggle during the cut or a separate tool option?
- **A-Q3 — Closed shapes across faces:** do you need to close a shape that runs over several faces by clicking
  its start point (today that only works inside one face — gap 1)? This decides whether Q5-c is built.

---

## 10. Confidence per question

| X | Confidence | Basis |
|---|---|---|
| X1 | **documented** (Blender, Wings) / **not investigated** (Silo, Maya, 3ds Max) | source read, not run; line numbers at the stated revisions |
| X2 | **documented** | probe: grid, concave, head (150 random segments), applied through D's resolver with invariant checks |
| X3 | **documented** (finding) | probe: grid camera-independent (except tolerance), head camera-dependent in most orbits; Blender fixes at click `[SRC]` |
| X4 | **documented** for the listed cases / **open** for refuse-vs-skip rules | probe; rules are A-Q1 |
| X5 | **documented** | probe P8 (a)(b)(c); gaps 1/2 behaviour derived from `window.py` + resolver code |
| X6 | **partly** | code reading; "straight on screen" follows from the construction, not rendered |
| X7 | **documented** (no Core need) / **assumed** (provenance hooks) | probe uses only `split_edge`, `connect_vertices` and the Face Cut stand-in |
| X8 | **assumed** | options derived from X2–X6; not built, not played |
| X9 | — | questions only |

---

## 11. Open questions (not decided, not recommended)

- **Is D the best model for Q5?** The evidence does not require another one: D's "nothing mutates before commit"
  is what makes click-time `(edge_id, t)` storage safe (§3). An immediate model (Wings; today's Production
  Knife) avoids the question differently — it cuts at the click, so crossings are fixed by the mutation itself.
  Q5 therefore does not decide between the collected (D) and the immediate history model; D's virtual-list
  undo stays a Lab acceptance (`decision.md` gap 3), not a Production decision.
- **Where the planner lives** in the one Knife (tool layer next to picking vs a shared topology helper next to
  `connect_in_shared_face`) — part of the unification question, out of scope here.
- **Unification of Knife and Knife Face** into one Production tool: out of scope by the brief; Q5 adds nothing
  that assumes two tools.
- **Hover-rate cost** on larger meshes: WALK is local (cost ∝ faces crossed); PLANE is global and needs a
  spatial index — only relevant if PLANE's behaviour is chosen (A-Q1).

## 12. Not investigated

- Silo, Maya, 3ds Max cross-face behaviour (no new source reachable in the time box; documentation sites were
  blocked for the earlier discoveries). None of the reference tools was run.
- Rendering of the preview (line + dots) — only derived from the window code.
- Orthographic views (the Playground camera is perspective only).
- Self-intersecting paths across faces; a segment crossing the same edge twice on a curved surface (possible
  in principle — D's resolver handles several points on one edge — not constructed).
- Symmetry Knife, stroke/drag knife (K2 / Knife V2), Face Holes (H0–H5), Active Tool — out of scope.
- Attributes (UV, weights, morphs) across the splits beyond naming the hook points (§7).

## Appendix — probe output (excerpt) `[PROBE]`

`python experiments/topology/knife_cross_face_probe.py` (≈ 20 s; full output P1–P9 on stdout):

```text
== P1  grid 4x4 — straight segment across 3 quads (edge -> edge), camera oblique ==
  WALK ok=True crossings=[e13@0.4000, e16@0.5000] faces=[4, 5, 6]
  PLANE visible hits=[('e13', 0.4), ('e16', 0.5)] hidden=0
  walk == plane: True (max |dt| = 7.22e-16)
  D as built: 3/3 cut(s) applied | invariants OK | sizes {4: 16} -> {4: 18, 5: 1} | old vertices kept=True, +4 V / +11 E (net +7) / faces 16->19 (3 replaced), new ids above old maxima=True | history=1

== P6  head (324 non-planar quads) — WALK vs PLANE on random visible face->face segments ==
  segments: 150 (screen length 40-220 px, both ends visible face points >= 9px from edges)
     146  walk ok, == plane(visible)
       3  walk ok, == plane(visible) except one extra edge hit next to a vertex hit
       1  walk failed: no exit edge found — after entering a back-facing face
     148    (all) plane found hidden hits (other side of the head)
     149    (of ok) walks checked for hidden crossings (B8 test)
       7    (of ok) walk snapped to a vertex (0.5px)
       1    (all) plane(visible) hits do NOT form a face-connected chain (jumps a gap)
  identical crossings: max |dt| walk vs plane = 4.00e-14
  cost per segment (pure Python, no cache): WALK 0.56 ms, PLANE+occlusion 23.92 ms

  -- loop4 around vertex (2,2), 4 quads
    (a) close-on-start (window commits, closing segment never added): D: 2/2 cut(s) applied; leading interior point(s) dropped (no boundary reached before them); trailing interior point(s) dropped ...
    (b) closing segment + new click on the start position: D: 3/3 cut(s) applied; leading interior point(s) dropped (no boundary reached before them); trailing interior point(s) dropped (no boundar...
    (c) cyclic (rotated to start/end on one crossing): 4/4 cut(s) applied | invariants OK | sizes {4: 16} -> {4: 16, 6: 4} | old vertices kept=True, +8 V / +16 E (net +12) / faces 16->20 (4 replace...
        cut edges=8, of which reach an original vertex (= a bridge): 0
```

## Sources

- Blender `editmesh_knife.cc`, main @ `363df9d` —
  https://github.com/blender/blender/blob/main/source/blender/editors/mesh/editmesh_knife.cc
- Blender `editmesh_knife.c`, tag v2.79 —
  https://github.com/blender/blender/blob/v2.79/source/blender/editors/mesh/editmesh_knife.c
- Wings 3D `wpc_connect_tool.erl`, master @ `8ae2bfd` —
  https://github.com/dgud/wings/blob/master/plugins_src/commands/wpc_connect_tool.erl
- Mirai: `playground/experiments/knife_face/engine.py`, `playground/window.py`, `src/mirai/topology/knife_pick.py`,
  `src/mirai/viewport/picking.py`, `src/mirai/topology/topology_points.py` @ `52d52b8`
