# Knife — Cutting into Faces (Face Cut): Discovery

**Status:** Discovery — Research Package (Type B), no decision. Fresh first impression; archive
unchanged before discussion (AGENTS.md §6).
**Date:** 2026-09-28
**Mode (M5):** Discovery
**Belongs to:** `docs/architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md` §6 B2 ("Face-interior cutting … open")
· `docs/design/artist_playground/WP-AP-CUT_PLAN.md` §0 C4, §7 · ARCH-02 (`docs/architecture/ROADMAP.md`)
**Code examined:** `claude/jolly-sagan-qubebh` @ `ae38356` (= WP-06 B8)
**Probe:** `experiments/topology/knife_face_cut_probe.py` (public Core API only, no Core change)

> This document answers Q1–Q5 of the Face Cut discovery brief. It changes no behaviour, makes no
> product decision and no Core decision. It provides evidence, a Lab options table, a prepared Artist
> test and the questions only the Artist can answer. Observation and interpretation are kept apart;
> every external claim carries an evidence tag.

**Evidence tags**

| Tag | Meaning |
|---|---|
| `[SRC]` | Read in the tool's published source code (not executed). |
| `[DOC]` | Official documentation wording — **only as search-engine excerpts**. The documentation sites (docs.blender.org, help.autodesk.com, nevercenter.com) are blocked by this environment's network policy, so no page was read in full. Wording may be paraphrased by the excerpt. |
| `[ART]` | Artist statement (recorded in the repository or in the brief). |
| `[CODE]` | Mirai code read at `ae38356`. |
| `[PROBE]` | Result of `knife_face_cut_probe.py`, run at `ae38356`. |
| `[ASSUMED]` | Plausible, not verified. |
| `[UNKNOWN]` | Could not be established here. |

---

## 0. History Awareness (M1) — known state verified

| Brief claim | Verified | Where |
|---|---|---|
| Knife engine in `src/mirai/topology/knife.py`, `knife_pick.py`; Playground re-imports them (B7). | ✅ | `[CODE]` |
| Explicit click path; points are vertices or edge points at `t`; each segment connects via `connect_in_shared_face`. | ✅ | `knife.py::click`, `topology_points.py` |
| `knife_pick` returns `kind: "face"`; treated as invalid. | ✅ `hover()` and `accepts()` both return invalid for `face`; Production click on a face → HUD "no valid cut target here". | `knife.py`, `application.py::_knife_release` |
| Production = click-only Variant A, line preview start → prospective point only for valid targets. | ✅ `_knife_set_preview` gates on `KnifeTool.accepts`; invalid → no point, no line. | `application.py`, `knife_preview.py` |
| B8 picking: `PickCache` + occlusion; `pick_face` exists with bbox pre-filter. | ✅ | `picking.py`, `picking_cache.py` |

Findings the brief did not list (relevant later):

| # | Finding | Consequence |
|---|---|---|
| H1 | `pick_face` computes the ray hit parameter (`best_t`) but **returns only the FaceId**. `[CODE]` | A face-interior point needs the hit position. Additive change in `src/mirai/viewport/picking.py` (or recompute in `knife_pick`) — not Core. |
| H2 | `pick_face` fan-triangulates from `boundary[0]`. On concave n-gons a hit can be reported outside the polygon; on non-planar quads the hit lies on one of two fan triangles. `[CODE]` | Today this only chooses *which* face. With Face Cut it chooses *where a vertex is created*. The `head` asset is 324 quads and measurably non-planar (4th vertex off the plane of the first three: median 6 %, p90 22 %, max 68 % of the face diagonal; `grid`: 0). Measured once at `ae38356` via `PlaygroundApp().load_head()`; not part of the probe. |
| H3 | Pick radii: vertex 14 px, edge 9 px; vertex wins over edge, edge over face. `[CODE]` | An interior point can only be placed ≥ 9 px (screen) away from every edge of the face. Small on-screen faces leave little interior. |
| H4 | `KnifeTool` already records a **non-mutating step** (first vertex click). `[CODE]` | WP-AP-CUT_PLAN C4 asked that pending points not be made expensive — structurally fulfilled. |
| H5 | AD-017 §4 lists "cut with a point inside a face ✅" from probe K3 — K3 covers exactly one case (FC1 below). `[CODE]` | FC2–FC7 are new evidence here. |
| H6 | AD-017 B2a is labelled "Silo/Wings point-to-point". Silo's documentation allows clicks "anywhere on the interior of faces" `[DOC]`; Wings' Connect tool excludes faces `[SRC]` **but walks cuts across several faces** `[SRC]`. | "B2a = Silo" does not match Silo's docs. Recorded as a discrepancy only; AD-017's proposal text is a record and is not edited. |
| H7 | `Mesh.add_face` does **not** reject repeated boundary vertices; only `tests/mesh_invariants.py` catches them. `[CODE]`, `[PROBE]` FC5a, FC6-1 | Tool-layer face surgery (B2b) can silently build invalid faces unless it re-implements the check. |

**Rejected before:** nothing about Face Cut was ever rejected — only deferred (WP-AP-CUT_PLAN C4, §3, §7;
AD-017 §7, §11, §12). **Binding Artist statements:** Face Cut is the most important open Knife question
`[ART]`; in Silo hover/cut works on vertices, edges and faces in every component mode `[ART]`; the line
preview observation from the B7 window test (Q4b) `[ART]`; click-only Knife (B7.1) `[ART]`; Blender-style
drag cutting is a possible V2 idea, not prepared `[ART]`.

---

## 1. Q1 — Reference behaviour

### 1.1 Per tool

**Blender** — `editmesh_knife.cc` (main @ `d50d020`) and `editmesh_knife.c` (tag `v2.79` @ `b19b25a`); both
versions use the same mechanism for everything below. `[SRC]`

- A cut position is a vertex, an edge point, a **point inside a face** (`KnifePosData.bmface`) or a point in
  empty space. A face hit creates a new knife vertex at the hit (`new_knife_vert`). Start, middle and end
  of a path may all be face points.
- **Nothing in the mesh changes while cutting.** Clicks build a virtual cut graph (`KnifeVert`/`KnifeEdge`);
  `knife_make_cuts` applies it once, on confirm: split edges, then split each touched face by its edge net
  (`BM_face_split_edgenet`).
- **Closed loop inside a face:** before splitting, isolated islands are connected to the face boundary
  (`#define USE_NET_ISLAND_CONNECT /* Detect isolated holes and fill them. */`,
  `BM_face_split_edgenet_connect_islands` — "Connect isolated mesh 'islands' so they form legal regions from
  which we can create faces"). Double-click closes the path back to its first point (`KNF_MODAL_ADD_CUT_CLOSED`).
- **Dangling ends:** after the face split, new edges that ended up in no face are deleted — "Remove dangling
  edges, not essential - but nice for users." The edge split where a dangling cut entered the face stays
  (inferred from the code order, not run). Whether the lone interior vertex stays as a loose vertex:
  `[UNKNOWN]` (no vertex removal found in the knife source).
- **Segments across several faces:** the segment previous → current point is intersected with every edge it
  crosses ("line hits"); each crossed edge is split and each face in between is cut. Only visible faces unless
  *Cut Through* is on.
- Result: arbitrary n-gons (edge-net split).
- Session keys (v2.79 keymap in the same file): LMB add cut, double-click close, `E` end current cut and start
  a new one, `Enter`/`Space` confirm. Main adds freehand cutting while the button is held.

**Silo** — Nevercenter wiki page "Cut", `[DOC]` excerpts only; Silo is closed source.

- "Click with the left mouse button to add new points to your cut. You can click on edges, vertices, or
  anywhere on the interior of faces."
- "click and drag the mouse on a valid face or edge to add and position a new vertex, and start a string of
  edges"; `Delete` removes points from the current cut; `Esc` exits; "Exit the tool to finish your cut";
  holding the Cut key exits the tool on release. With components selected, Cut cuts across the selection;
  without, the interactive tool starts.
- What an interior point becomes, dangling ends, closed loops, cross-face segments, when the mesh changes,
  preview: `[UNKNOWN]`. "Remove points from your current cut" and "exit … to finish" *suggest* a path that
  is edited before it is final — whether the mesh changes per click is not stated. `[ASSUMED]` at most.

**Wings 3D** — Tools → Connect, `plugins_src/commands/wpc_connect_tool.erl` (master @ `8ae2bfd`). `[SRC]`

- Faces are excluded: `wings:mode_restriction([vertex,edge]), %% ,face`. No face-interior points.
- Pressing on an edge cuts it immediately at the cursor and starts a slide; release connects. The mesh
  changes per click (like Mirai today), with an undo step per connection.
- **Across faces:** if two points share no face, the tool walks along the 2D screen line between them — finds
  edges crossed by the line in the faces around the current vertex, prefers front-facing faces, cuts and
  connects face by face until both share a face (`connect_link1`, `check_possible`, `select_way`).
  Key `1` ("Loop Connect") also cuts around the back.
- End: re-select the last vertex, right-click or `Esc`.

**3ds Max** — Editable Poly *Cut*, Autodesk Help (Editable Poly (Edge) / Edit Geometry rollout), `[DOC]`
excerpts only.

- A cut can start by clicking "at the center of a polygon"; right-click ends/exits.
- "One line connects the mouse cursor to the original click location and indicates where the next cut will
  appear"; another line runs to a polygon corner; "if the cursor isn't over an edge or a vertex, a third line
  connects the mouse cursor to another vertex".
- `[ASSUMED]`: the extra line(s) show an automatic edge from an interior point to a polygon vertex, so no
  vertex is left dangling. Cross-face behaviour, closed loops: `[UNKNOWN]`.

**Maya** — Multi-Cut, Maya Help 2020–2025, `[DOC]` excerpts only.

- "A cut must start on a vertex or edge. If you start a cut on a face, the closest vertex is also selected,
  creating two cut points."
- `Enter` or right-click completes; `Shift` snaps along edges; `Ctrl`+drag inserts an edge loop; click-drag
  slices across faces.
- Interior middle/end points, dangling ends, closed loops, preview over a face: `[UNKNOWN]`.

### 1.2 Summary

| Question | Blender | Silo | Wings (Connect) | 3ds Max (Cut) | Maya (Multi-Cut) |
|---|---|---|---|---|---|
| Click in a face — start | yes `[SRC]` | yes `[DOC]` | no `[SRC]` | yes `[DOC]` | yes, nearest vertex added `[DOC]` |
| — middle of path | yes `[SRC]` | yes `[DOC]` | no | `[ASSUMED]` yes | `[UNKNOWN]` |
| Path ends in a face | dangling edges deleted at confirm `[SRC]` | `[UNKNOWN]` | n/a | line to "another vertex" `[DOC]` → auto-edge `[ASSUMED]` | `[UNKNOWN]` |
| Two interior points in one face | yes, part of the face's edge net `[SRC]` | `[ASSUMED]` yes | n/a | `[UNKNOWN]` | `[UNKNOWN]` |
| Closed loop in a face | double-click; island auto-connected to boundary `[SRC]` | `[UNKNOWN]` | n/a | `[UNKNOWN]` | `[UNKNOWN]` |
| One segment across several faces | yes, every crossed edge `[SRC]` | `[UNKNOWN]` | yes, screen-line walk `[SRC]` | `[UNKNOWN]` | slice mode `[DOC]`; point-to-point `[UNKNOWN]` |
| Mesh changes | once, on confirm `[SRC]` | `[UNKNOWN]` | per click `[SRC]` | `[UNKNOWN]` | on complete `[DOC]` (slice) |
| Result | n-gons `[SRC]` | `[UNKNOWN]` | n-gons `[SRC]` | `[UNKNOWN]` | `[UNKNOWN]` |

**Observation.** Every tool that allows face-interior points has *some* rule that prevents a lone interior
vertex: Blender deletes dangling edges and auto-connects islands at confirm; Maya adds the nearest vertex to a
face start; 3ds Max shows a line to another vertex. Wings avoids the question by excluding faces. Silo's rule is
unknown.

**Interpretation.** "Interior points need a rule for loose ends" is universal. The tools differ in *when* the
rule is applied — at confirm on a virtual graph (Blender) or at click time (Maya, probably 3ds Max) — and in
whether the rule adds geometry the user did not click (Blender islands, Maya nearest vertex).

---

## 2. Q2 — Topology meaning under the current invariants

**Facts from the Core** `[CODE]`: a face is **one** ordered boundary list of ≥ 3 distinct vertices; an edge has
0 (free), 1 or 2 faces; there is no representation for a hole or an inner ring. `add_face` itself does not
reject repeated vertices — the invariant catalogue does (H7).

Cases, run on a 4×4 quad grid with two constructions each (`[PROBE]`):

- **B2b** = `remove_face` + `add_vertex` + `add_face` (face surgery; also the stand-in for a B2c primitive —
  same result, different code location);
- **CSM** = `connect_vertices(F, a, b)` → `split_edge` on the new edge k times → `set_vertex_position`
  (only primitives the Knife already uses, plus `set_vertex_position`; **not listed in AD-017**).

| # | Case | B2b | CSM | Meaning |
|---|---|---|---|---|
| FC1 | edge → 1 interior point → edge (ends non-adjacent) | ✅ `{4:13, 5:4}` | ✅ identical geometry | valid |
| FC2 | edge → 2 interior points → edge | ✅ `{4:13, 5:2, 6:2}` | ✅ identical geometry | valid |
| FC3 | notch: in and out through the same edge (ends adjacent) | ✅ triangle + 7-gon | ❌ rejected (`connect_vertices` refuses adjacent ends) | valid, needs B2b/B2c |
| FC4 | vertex → interior → adjacent vertex | ✅ triangle + pentagon | ❌ rejected | valid, needs B2b/B2c |
| FC5 | dangling: edge → interior point, path stops | as a face-boundary spur: ❌ invariant violation (repeated vertex); as a free edge (`add_edge`): passes the structural check, but the face is untouched and the edge lies on top of it (same class as Connect F7 "kind v") | — | **not a valid cut result** |
| FC6 | closed loop inside a face, 0 bridges | inner face over the unchanged outer face: passes the structural check, geometry overlaps | — | **not valid** (no holes) |
| FC6 | … 1 bridge (keyhole) | ❌ invariant violation (repeated vertices) | — | **not valid** |
| FC6 | … 2 bridges | ✅ `{3:1, 4:15, 5:1, 6:1}` (two B2b calls) | ❌ second call rejected (ends adjacent) | valid, needs B2b/B2c |
| FC7 | interior point in F1 → interior point in neighbour F2 | — | — | not a one-face cut; needs the crossing on the shared edge (Q5) |
| — | interior **start** P → boundary | same as FC5 for the first segment | — | valid only if the path later comes back through P's face and ends at P, or P gets a second bridge |
| — | ends at the same vertex (a = b) | ❌ repeated vertex | — | not valid |

ID continuity of the B2b/B2c stand-in (FC1) `[PROBE]`: the old face becomes invalid; two new FaceIds, k new
VertexIds and k + 1 new EdgeIds, all above the previous maxima (AD-001 monotonic, no reuse); all old vertices
and the face's old boundary edges keep their IDs — the same shape as `connect_vertices`' documented contract.
CSM additionally creates and immediately invalidates one edge per face cut (transient ID; allowed by AD-001).

**Not checked by the Core (tool/picking responsibility):** the path leaving a concave face, a self-crossing
path, an interior point outside the polygon (H2). `connect_vertices` does not check geometry either; Blender's
knife does (`knife_verts_edge_in_face`, side-of-edge tests) `[SRC]`.

**Interpretation.** The only valid results are *"split one face along a path whose two ends are distinct
boundary vertices"*, applied once per face, possibly several times (FC6). Everything else must be held back
until the path reaches the boundary, completed automatically, or discarded. Consequently **an interior click
can never be applied as its own mesh mutation**: WP-AP-CUT_PLAN C4 is confirmed — "each click creates a cut"
cannot hold for interior clicks.

---

## 3. Q3 — Core options re-evaluated

| Option | Covers | Core change | Mutation-layer principle (V1_SPEC) | ARCH-02 / provenance | Risk |
|---|---|---|---|---|---|
| **B2a** no interior points | — | none | kept | nothing new | Face Cut does not exist |
| **B2b** tool-layer face surgery | FC1–FC4, FC6 | none | **violated**: the tool rebuilds faces; must re-implement validation Core does not do (H7) | the primitive trace shows "face removed, vertex added (no parent), 2 faces added" — the parent face exists only in tool context | invalid faces slip through unless the tool checks; face bookkeeping duplicated outside Core |
| **B2c** new primitive "split face along a path" | FC1–FC4, FC6 | additive primitive | kept | the primitive knows the parent face, the path and both sides — the natural hook point | new Core surface (needs AD + freeze rule) |
| **CSM** (new here) connect → split → move | FC1, FC2 only | none | kept (only `connect_vertices`, `split_edge`, `set_vertex_position`) | records a *wrong* origin: the interior vertex is born as a split of a transient chord edge at t = 0.5, then moved | cannot do notch, adjacent ends, closed loops |

**Freeze rule (CORE_V1_FREEZE §7), applied:**

1. *Concrete requirement:* Face Cut `[ART]`. Which shapes are required is **not** yet concrete — see Artist
   questions A2.
2. *Solvable with the public API?* FC1/FC2: **yes, without face surgery** (CSM). FC3/FC4/FC6: yes only with face
   surgery (B2b).
3. → A Core change is justified only if the Artist needs FC3/FC4/FC6 **and** tool-layer face surgery stays
   unwanted (AD-017's stated principle).

**B2c sketch — a proposal for an AD, not a decision:**

```text
Mesh.split_face(face_id, v_a, v_b, positions: Sequence[Position] = ())
    -> tuple[list[VertexId], list[EdgeId], FaceId, FaceId]
```

- Preconditions: face valid; `v_a != v_b`, both on the face boundary. `positions == ()` behaves exactly like
  `connect_vertices` (adjacent ends rejected). With ≥ 1 position, adjacent ends are allowed. Both resulting
  loops ≥ 3 vertices. Any violation → `MeshError`, mesh unchanged. No geometric checks (as `connect_vertices`).
- ID continuity: `face_id` invalid; k new VertexIds in path order; k + 1 new EdgeIds in path order `v_a → v_b`;
  two new FaceIds, deterministic order (face 1 = the side running `v_a → v_b` in boundary order); boundary
  vertices and untouched edges keep their IDs; allocation monotonic (AD-001), no reuse.
- Undo: nothing new — `MeshStateCommand` snapshots cover it, as do the Knife's in-session steps.
- `connect_vertices` stays untouched (freeze; the new method is a superset, not a replacement).
- ARCH-02: exposes the parent face, the new vertices with their creation positions and the two sides. For later
  attribute interpolation (UV, weights, morphs) an interior vertex needs the parent face's corner data *at
  creation time* — only the primitive or the operation context sees that moment. This is the same argument
  AD-017 B5 made for `split_edge(t)`.
- Not included: dangling ends, holes (not representable), auto-bridging (tool policy), cross-face (tool composes
  per face).

**Agent assessment (not a decision):** AD-017's "B2a first; B2c over B2b" still holds, with two refinements:
(1) if the Artist only needs pass-through cuts (FC1/FC2), CSM does it with no Core change and the freeze rule
says stop there — its provenance weakness is covered by the operation context (the Knife knows it placed a face
point); (2) the Lab should use the B2b/B2c stand-in (`split_face_path` in the probe) so the Artist can feel all
shapes before the Core question is asked. Any Core change is an AD proposal *after* the Lab verdict.

---

## 4. Q4 — Interaction

How interior points would sit on the Production Knife without redesigning its session, history or overlay model
(mechanics derived from the code `[CODE]`; UX consequences are `[ASSUMED]` until played):

| Existing rule | With interior points |
|---|---|
| Hover dispatch by kind (vertex/edge/face/outside), in every component mode | unchanged; the `face` arm gets a hit position (H1) and becomes valid **inside the current face** (the face the pending path lives in, or one of the start vertex's faces for the first interior click). Hover there = preview point at the ray hit + line from the current point, through the existing `accepts`-gate. A face elsewhere stays invalid. |
| Each click creates a cut; new point becomes start | true for vertex/edge clicks. An interior click adds a **pending point** (tool state, non-mutating step, H4). The next click on the current face's boundary applies the whole in-face path once (split the target edge if needed, then split the face) — one step. |
| `accepts()` rules (edge not incident to start, not adjacent) | become pending-aware: with ≥ 1 pending point, adjacent targets and edges incident to the start are valid (FC3/FC4). |
| `start` is a VertexId | the current point can be a pending position that is not a vertex yet. `KnifeTool.start`, `KnifeRenderData.start_point` need an additive "current point" notion. This is the one structural addition to the session state. |
| In-session Undo/Redo | unchanged model: pending steps are non-mutating steps (like today's first vertex click); step snapshots add the pending list. |
| `Esc` | unchanged: discards everything, including pending points. |
| `Enter` / click outside = commit | **needs a rule for a pending tail** (points that never reached the boundary): drop (Blender-like), refuse with HUD message, or auto-connect (Maya/3ds Max-like). Artist question A4. |
| Residue on commit (path edges, Edge mode) | unchanged; the in-face edges join `path_edges`. A dropped tail contributes nothing. |
| Occlusion (B8) | `pick_face` returns the nearest face along the ray, so an interior point is always on a visible face in Shaded/Flat. In Wireframe faces behind others are pickable — consistent with vertices/edges there, but the user sees no face fill `[ASSUMED minor]`. |
| Overlay layers | pending points → `tool_active` points; pending segments drawn as preview segments (they are not edges yet) — lab default, not a UX decision. |

**First click inside a face.** A pending start P can only become valid if the path later returns through P's
face and ends at P, or if P gets an automatic bridge (Maya adds the nearest vertex `[DOC]`). Without a rule, a
path started in a face ends as a dangling tail. Artist question A3.

**Does "click outside = commit" conflict?** Not with faces as targets as such: outside still means "the ray hit
nothing". The real conflict is the pending tail: a click outside while points are pending can mean "finish" or
"I missed" — that is A4. A minor risk: a click just past the silhouette meant as a face point commits the
session; the 9 px edge radius protects edges but faces have no margin `[ASSUMED low]`.

**Coupling with Q5.** Consecutive points must share a face (current rule). With interior points this becomes
visible: a click inside the *neighbouring* face is invalid (FC7), and — by the current preview rule — shows no
line (Q4b). Face Cut without cross-face segments stays strictly "one face at a time".

---

## 5. Q4b — Line preview over faces

| | Blender | Wings | 3ds Max | Maya | Silo | Mirai Production |
|---|---|---|---|---|---|---|
| Line from start to cursor while over a face | yes, to the face hit point; after the first click always, even into empty space `[SRC]` | yes, to the raw cursor, always, whatever is under it `[SRC]` | yes, "one line connects the mouse cursor to the original click location" `[DOC]` | `[UNKNOWN]` | `[UNKNOWN]`; hover works on faces `[ART]` | no — face = invalid target `[CODE]` |
| Point at the cursor over a face | yes, current-point dot at the face hit (not gated by the first click) `[SRC]` | no `[SRC]` | cursor icon changes by component `[DOC]` | `[UNKNOWN]` | `[UNKNOWN]` | no |
| Preview matches what the click does | yes, plus a dot at every edge the segment will cross ("line hits") `[SRC]` | **no** over faces (the line suggests a cut; the click does nothing) `[SRC]` | partly; extra line(s) to a polygon vertex `[DOC]`, meaning `[ASSUMED]` | `[UNKNOWN]` | `[UNKNOWN]` | yes — only valid targets are previewed |

**Observation.** Blender's line inside a face is not an exception to "preview = what the click does": in Blender
the face point *is* a valid target, and so is empty space. Wings is the only examined tool whose rubber band
promises more than the click delivers.

**Interpretation.** Q4b is mostly answered by the Face Cut decision itself. If faces become valid targets, the
line over the current face follows from the existing `accepts`-gate without a new preview policy. It stays a
separate question in two places: (1) if faces stay invalid (B2a) — show a free rubber band in a distinct
"no cut here" style, or nothing; (2) over faces that are still invalid with Face Cut (neighbour faces, FC7) —
the same choice again, and here Blender's behaviour relies on cross-face cutting (Q5).

---

## 6. Q5 — Cross-face segments (assessment only)

**Observation.** Blender (3D line hits, visible faces unless Cut Through) and Wings (2D screen-line walk, front
faces preferred) both resolve one segment into cuts in every face it crosses `[SRC]`. Mirai rejects a segment
that is not inside one shared face `[CODE]`.

**Assessment.** A variant of the same Knife, not a different tool: same session, steps (one click = one step
that may contain several splits and face cuts), history and residue. What changes is the *segment resolution*
(a planner turning "current point → target" into per-face sub-cuts), the preview (crossing points) and the
rejection rules (segment leaving the mesh, back faces, holes). It needs no Core change beyond what Face Cut
needs (`split_edge` at crossings plus a per-face split). It is independent of the stroke/drag knife (K2): K2 is
about input, Q5 about resolving a segment. Technical risk: on curved or non-planar surfaces a straight 3D segment
leaves the surface, so crossings must be computed in screen/view space (Wings) or against a view plane
(Blender). No recommendation beyond this.

---

## 7. Options for a Playground Knife Lab (≤ 3 variants)

All variants start from Playground Knife Variant A (= the Production click-only interaction). Only the
face-related behaviour differs. The face split in B and C uses a lab-local stand-in (like `split_face_path`
in the probe), clearly marked as lab code; no Core change.

| Variant | Behaviour | Core need | Risk |
|---|---|---|---|
| **A — Rubber band only** (control, B2a) | Faces stay invalid targets. After the first click, a line from the start to the cursor is drawn over faces in a distinct "no cut here" style; valid targets keep today's preview. Isolates Q4b. | none | Wings-like promise the click does not keep. Cheap; can be skipped if the Artist answers A5 directly. |
| **B — Face points, strict** | Interior clicks allowed inside the current face as pending points (point + line drawn). The path is applied when it reaches an edge/vertex of that face — notch and adjacent ends allowed. A face elsewhere is invalid (no line). First click in a face is invalid. Pending tail on `Enter`/click outside is dropped with a HUD note (lab default). | lab stand-in; later CSM (FC1/FC2) or B2c (all shapes) | Interior clicks do not cut immediately; neighbour faces show nothing (Q4b gap remains there); pick precision on small/non-planar faces (H2, H3). |
| **C — Face points, forgiving** | As B, plus: first click in a face allowed; loose ends are completed instead of dropped — a pending start or pending tail is connected to the nearest vertex of its face (Maya/3ds Max-like), and clicking the first pending point closes a loop that is bridged to the boundary with two edges (Blender-like island connect). | as B | Edges the Artist did not click appear; "nearest vertex" can pick an unexpected corner on n-gons; most code of the three. |

Cross-face segments (Q5) are deliberately **not** in these variants — mixing them in would confound the Face
Cut verdict. A separate small Lab can follow if A6 asks for it.

---

## 8. Prepared Artist test (M4) — not built yet

**Goal:** within ≤ 5 minutes per variant, find out whether cutting into faces is wanted in this form, and whether
the Q4b observation is about the line or about the cut.

- Start (once the Lab is built): `python playground/run.py grid` (flat 8×8 quads) and `python playground/run.py head`.
- `Tab` until the Lab family is focused (name set at build time; proposed `knife_face`), `M` cycles A / B / C.
- `C` with an empty selection starts the Knife. `Enter` or click outside = commit, `Esc` = cancel,
  `Ctrl+Z` / `Ctrl+Y` = undo / redo cut. Zoom in so a face is large on screen (interior points need ≥ 9 px
  distance from every edge).
- At build time, copy this section into `playground/experiments/<family>/decision.md`
  (`ExperimentSlot.generate_decision_md()`), in the format of `playground/experiments/connect/decision.md`.

**Tasks** (same four for every variant):

1. **Grid — bent cut through one quad:** click an edge of a quad, click once inside the quad, finish on the
   opposite edge. Commit.
2. **Grid — notch:** from one edge of a quad into the quad and back out through the same edge (a V). Commit.
3. **Grid — start inside:** first click inside a quad, then continue to edges. Commit with `Enter`.
4. **Head — cheek:** from an edge, two points inside one cheek quad, out through another edge of it; then try to
   continue by clicking inside the neighbouring quad. Watch the line while moving over both quads.

**Expected, not a verdict on the variant:** in A, tasks 1–3 cannot cut by design (A tests only the line); in B,
task 3 does not produce a cut and the neighbour-quad click in task 4 is invalid by design; in C, task 3 adds an
edge to the nearest corner.

**Observe:** Does Manu reach the goal? How many attempts? Where does frustration appear? Does the line over a
face change how the tool feels on its own (A)? Which results would he keep?

### A — Rubber band only

**Verdict:** _KEEP / ITERATE / REJECT / UNKNOWN_

### B — Face points, strict

**Verdict:** _KEEP / ITERATE / REJECT / UNKNOWN_

### C — Face points, forgiving

**Verdict:** _KEEP / ITERATE / REJECT / UNKNOWN_

### Observations outside the question

_(incidental evidence — raises priority of other questions, does not decide them)_

---

## 9. Questions only the Artist can answer

A1. **Silo reference:** when you click inside a face in Silo and end the cut without reaching an edge, what is
    left — nothing, a dangling edge, or an automatic connection? Does the face change at the interior click or
    only when the path reaches an edge? (Silo is closed source; its docs are silent.)
A2. **Which shapes matter in your work:** pass-through with bends (FC1/FC2), notch in and out of one edge (FC3),
    a closed shape inside a face (FC6), a start inside a face? (Only FC1/FC2 → no Core change needed.)
A3. **Start inside a face:** should it be possible, and if so, what should connect it to the mesh?
A4. **Loose ends on finish:** `Enter` or click outside with face points that never reached an edge — discard
    them, refuse to finish, or connect them automatically?
A5. **Your Blender observation (Q4b):** is it about *seeing* the line to the cursor, or about being able to cut
    where the line goes (into faces, across faces)?
A6. **Neighbouring faces:** is continuing a segment into the next face (Blender-style crossing) part of what you
    expect from Face Cut, or a later separate step?
A7. **Automatic edges:** may the Knife ever add an edge you did not click (variant C)?

---

## 10. Confidence per question

| Q | Confidence | Basis |
|---|---|---|
| Q1 | **partly** | Blender and Wings: documented from source (read, not run). 3ds Max and Maya: second-hand doc excerpts, several cells `[UNKNOWN]`. Silo: only "click inside faces is allowed" is documented. |
| Q2 | **documented** | Core code + probe with invariant checks. |
| Q3 | **documented** (feasibility) / **assumed** (B2c signature) | probe; the signature is a proposal for an AD. |
| Q4 | **partly** | mechanics derived from the code; the UX consequences need the Artist test. |
| Q4b | **partly** | Blender, Wings from source; 3ds Max from excerpts; Maya, Silo unknown. |
| Q5 | **partly** | Blender, Wings from source; the assessment is interpretation. |

---

## 11. Open questions — possibly a better Knife model (not decided, not recommended)

- **Deferred application (Blender model):** Blender keeps the whole session as a virtual cut graph and applies it
  once on confirm, per face. That would make pending points, dangling ends and closed loops one mechanism at
  confirm time instead of rules at click time. It changes when the mesh changes during a session (today: per
  click, DECIDED in-session history). Recorded as an open question only.
- **Where the "loose end" rule lives:** at click time in the tool (Maya-like) or at commit time on the whole path
  (Blender-like).

## 12. Not investigated

- Full documentation text of Blender, Silo, 3ds Max, Maya (sites blocked from this environment); none of the
  reference tools was run.
- Attributes (UV, weights, morphs) across a face split — only the provenance hook point is named (§3).
- Non-manifold geometry, concave n-gons in practice, self-crossing paths.
- Symmetry / mirrored Knife (Symmetry Lab), Active Tool, stroke/drag knife (K2) — out of scope by the brief.

## Sources

- Blender `editmesh_knife.cc`, main @ `d50d020` —
  https://github.com/blender/blender/blob/main/source/blender/editors/mesh/editmesh_knife.cc
- Blender `editmesh_knife.c`, tag v2.79 —
  https://github.com/blender/blender/blob/v2.79/source/blender/editors/mesh/editmesh_knife.c
- Blender `bmesh_polygon_edgenet.hh` —
  https://github.com/blender/blender/blob/main/source/blender/bmesh/intern/bmesh_polygon_edgenet.hh
- Blender Manual, Knife (excerpts only) — https://docs.blender.org/manual/en/3.1/modeling/meshes/tools/knife.html
- Wings 3D `wpc_connect_tool.erl`, master @ `8ae2bfd` —
  https://github.com/dgud/wings/blob/master/plugins_src/commands/wpc_connect_tool.erl
- Silo wiki, Cut (excerpts only) — https://nevercenter.com/silo3d/wiki/index.php?title=Cut
- 3ds Max Help, Editable Poly (Edge) (excerpts only) —
  https://help.autodesk.com/view/3DSMAX/2024/ENU/?guid=GUID-2C16FF31-BF20-450F-8163-3362A7037603
- Maya Help, Cut faces with the Multi-Cut Tool (excerpts only) —
  https://help.autodesk.com/view/MAYAUL/2022/ENU/?guid=GUID-12DF0D57-6E5E-48E3-8FBF-F787BA4E5410
- Maya Help, Slice faces with the Multi-Cut Tool (excerpts only) —
  https://help.autodesk.com/view/MAYAUL/2025/ENU/?guid=GUID-9E35F145-67E8-44A0-9EFB-E1959199010E
