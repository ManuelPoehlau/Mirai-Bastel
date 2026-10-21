# AD-022 — GPU ID-Buffer Picking

> **IMPLEMENTED (B2-out) in production, 2026-10-21** — see §11. Basis: `gl_PrimitiveID` and `gl_VertexID` exact on
> the reference driver (§8), the slot layout of AD-023 §9 as the shared buffer contract (§6 "Coupling"), Manu's
> instruction of 2026-10-21 ("Mach mit GPU-Picking weiter") and AGENTS.md §7a. The sections below are the decision
> history; §11 is the current state.

**Status:** PROPOSED (2026-10-17), **revised 2026-10-20** after the independent review
[`AD-022_REVIEW_CLAUDE_001`](../archive/viewport_v02/reviews/AD-022_REVIEW_CLAUDE_001.md) (ACCEPT WITH CHANGES; the
disposition of every finding is in §10). Draft for Manu's decision. Not decided; no production code exists. Per
AGENTS.md §5 this document lists alternatives, it does not select one.
**Mode (M5):** Discovery, decision preparation.
**Work package:** WP-VIEW-PERF-02 (follows WP-VIEW-PERF-01 Slices 1 + 2).
**Artist input:** Manu, 2026-10-17, on the Slice-1 practical test: "Fühlt sich gleich an, nur schneller. Im
Vergleich zu Blender auf meinem PC aber noch wesentlich langsamer. Dort lässt sich 20k Gollum sehr flüssig
zoomen, Komponenten picken oder Topologie-Operationen ausführen." On the Haltepunkt note: "gpu picking bringt
wohl den größten Gewinn" (a priority statement in reply to the agent's own ranking, **not** the choice of an
option) and "ja, ist beides gleich wichtig" (GPU picking and incremental topology,
[AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md)). Intent: Blender-level fluidity on 20k on the
reference PC. Priority: equal with AD-023.
Manu, 2026-10-20 (chat, recorded by the agent on his instruction): fluid = "ohne sichtbare Verzögerung"; Flat
shading without blotches, no visible triangles in Smooth and Flat, runs fluidly (Intake Log 2026-10-20); the
reference PC is the only machine until a modern one is bought in the coming months, a slowdown at very many
morph targets on very dense meshes is acceptable ([REFERENCE_HARDWARE](REFERENCE_HARDWARE.md) §3).
**Basis (only linked):** [`experiments/drag_cost/README.md`](../../experiments/drag_cost/README.md) ("Result: fix
slice 2", "Haltepunkt: what Blender-level fluidity on 20k would need");
[`experiments/gpu_picking_spike/README.md`](../../experiments/gpu_picking_spike/README.md) and its raw outputs
[`RESULTS_REFERENCE_PC_2026-10-20.md`](../../experiments/gpu_picking_spike/RESULTS_REFERENCE_PC_2026-10-20.md) (the
evidence below);
[`VIEWPORT_V02_ARCHITECTURE.md`](../viewport/VIEWPORT_V02_ARCHITECTURE.md) §1 (non-goals), §4.6, §11;
[AD-018](AD-018-PRODUCTION-DRAW-BINDING.md); [REFERENCE_HARDWARE](REFERENCE_HARDWARE.md) §2, §4;
[AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) (object picking, placed objects).
**Decided by:** Artist (Intent, Priority, the semantic checks in §4, the questions in §7) + review. Engineering
decides the variant details inside a decided direction.

**Tags:** **[RPC]** = measured on the reference PC (Core 2 Quad Q9550, GeForce 9800 GTX, Windows 10, GL 3.3.0,
Python 3.14.2). **[C]** = container (Xeon, llvmpipe: software rasteriser, not comparable). *(reading)* =
interpretation. Samples: p50 only, 15 per cost row (8 on 87.5k), one hidden 1024x768 window, two framed cameras;
no p95, no in-loop timing.

---

## 1. Problem

The picking cost on `gollum_20k` (21 875 V) and `gollum` (87 500 V) after the two CPU slices of WP-VIEW-PERF-01
(production CPU picker, spike "cpu" column), ms p50 **[RPC]**:

| | 20k | 87.5k | grows with |
|---|---:|---:|---|
| first pick after a camera change (vertex / edge / face) | 161 / 188 / 150 | 662 / 775 / 619 | V + F, every camera change (`PickCache.refresh` projects every vertex and face bbox) |
| hover / click with a valid cache (vertex / edge / face) | 19 / 43 / 8 | 85 / 197 / 35 | V, E (linear scans) |
| Box 300 px, vertex | 2 384 | 14 522 | elements in the box |

(Container, for comparison: 42-74 ms and 3-4 ms on 20k; the container understated the problem by about 2.5x.)

The camera-change cost is the CPU design itself: a screen-space picker must project the mesh for every new
view. Nothing local to `mirai/viewport` removes it (Slice-2 reading, drag_cost README). Per topology operation the
hover re-pick is 4-13 % of the frame [RPC] ([AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) §1); GPU picking
shrinks that part but does not change the rest of the table.

## 2. Evidence (spike `experiments/gpu_picking_spike/`)

The spike renders faces / edges / vertices with their IDs into an offscreen framebuffer and reads back the
pixels under the cursor; nothing under `src/` changed. It builds its **own** ID buffers (option B1 below), draws no
`gl_PrimitiveID`.

**Cost, ms p50 [RPC]** (GPU = spike; CPU as in §1):

| | 20k CPU | 20k GPU | 87.5k CPU | 87.5k GPU |
|---|---:|---:|---:|---:|
| pick after an orbit (vertex / edge / face) | 161 / 188 / 150 | **3.3 / 3.8 / 2.4** | 662 / 775 / 619 | **14.0 / 15.5 / 11.8** |
| hover, valid state (vertex / edge / face) | 19 / 43 / 8 | **1.7 / 2.0 / 0.7** | 85 / 197 / 35 | **3.3 / 4.1 / 0.7** |
| Box 300 px vertex | 2 384 | **89** (depth variant 85) | 14 522 | **295** (depth variant 332) |
| ID render, GL timer (GPU time) | - | 1.14 | - | 10.3 |
| spike's own buffers per mesh state (B1, Python; n = 1, includes shader compile and FBO creation) | - | 795 | - | 3 087 |

Container (llvmpipe) for the same rows: pick after an orbit 11-17 ms (20k) and 43-49 ms (87.5k); hover 0.06-0.8 ms;
Box 24 ms and 78-92 ms (spike README). On small meshes the GPU hover is **not** faster than the CPU hover (head 0.85
vs 0.21 ms [RPC]); both are far below a frame.

**Same picks.** Raw agreement with the CPU picker [RPC] (spike counts both-"nothing" cursors as agreement, so these
numbers are inflated): vertex 97.7 % / depth oracle 98.7 % (20k), 90.7 % / 96.7 % (87.5k); edge 96.3 % / 89.0 %; face
86.7 % + 13.2 % half-pixel / 78.7 % + 21.3 % half-pixel. On the non-trivial cursors only (review probe P1, container,
20k framed): vertex 95.8-97.5 %, edge 91.8-96.2 %, face 71.2-79.5 % + half-pixel. For **framed** views every real
difference is another element at most 0.73 px farther from the cursor than the CPU's, or the neighbour in the same
pixel; at **close zoom** the review found visibility differences (a vertex 7.2 px farther, an edge 0.97 px nearer,
"one side none" cases), which the depth oracle removes. A face pick differs from the CPU's by the pixel-sampling
convention (centre vs corner), and by real differences in a small number of cases (body: 4 of 600 [RPC]).
**Box:** the `ids` variant loses up to 37 % of a dense Box (one ID per pixel); the **depth oracle** keeps the CPU
rule within 0-6.5 % (review P3), and the deviation is mostly *additional* elements at grazing angles (it selects a
few percent more, including some back-side ones).

**Driver evidence [RPC].** FBO, `glReadPixels` and the GL timer query ran without error on the GL 3.3.0 driver.
Manu reports Flat shading without blotches and no visible triangles in Smooth and Flat. That is a visual check of
the production shader's use of `gl_PrimitiveID` on triangles; it cannot show a small off-by-k ID error (a
neighbouring face's near-identical normal looks the same) and does not cover `gl_PrimitiveID` on `GL_LINES` or
`gl_VertexID`, which B2's edge and point passes need *(reading)*.

**Not covered:** tails (p95/max) and in-loop timing; window sizes other than 1024x768, HiDPI, resize; close zoom
beyond one setting; camera near or inside the surface; other mesh scales; Knife, Paint, object picking, snapping,
placed objects (model matrix), H7 surfaces; B2 itself (a review probe on llvmpipe shows the mechanism works there, not on
the reference driver); the interaction with a W drag.

## 3. Options

All variants keep the CPU picker as the headless reference and as the fallback where no GL context exists
(`TraceStore`, the tests, hosts without a window).

### Status quo (no change)

The costs of §1: every camera change costs 150-190 ms (20k) or 620-775 ms (87.5k) before the first pick; hover 8-43 ms;
Box 2.4 s (20k). Same rules as today, no Artist check.

### A. Stay on the CPU, camera-independent world index (option 9 of the drag_cost README)

BVH / grid over triangles in object space, built per mesh state; rays for face / occlusion, a frustum query for
"nearest within 14 px". Build 0.65 s (21.9k) / 3.2 s (87.5k) in pure Python (audit [C]) after every topology op,
refit per W drag. **Same picks as today by construction** (testable for equivalence on the CPU, no Artist check,
none of the §4 differences). Its unmeasured part is the vertex / edge query (frustum over node bounds) and the
refit per W drag. It moves cost from navigation to editing, as B1 does at a similar size (795 ms per mesh state
[RPC]); it collides with AD-023 unless fed by touched sets. Touches `VIEWPORT_V02` §1 ("BVH / Octree / KD-tree") and
§4.6.

### B. GPU ID-buffer picking

An ID pass per camera state, rendered on demand (only when a pick needs it), read back in small windows.

- **B1 - own buffers (what the spike built):** unindexed face triangles with a per-vertex ID attribute, an edge line
  list, a point list. No `gl_PrimitiveID` (driver-safe). Cost: 3x the triangle vertex data per mesh state (795 ms /
  3.1 s Python build on 20k / 87.5k [RPC]), i.e. about **+0.8 s on every topology operation and every undo on 20k**
  (today 1.9-3.6 s per operation [RPC]), and it is patched on every W drag move in addition to the draw buffers.
- **B2 - from the `RenderMesh` buffers:** a second program over the same `positions` / `indices` VertexList (face ID =
  `gl_PrimitiveID` → face row, the same `u_triangle_faces` buffer texture the Flat shading uses), plus an edge index
  buffer and a point draw over `positions`. No duplicate vertex data, W drags patch nothing extra. **Unbuilt.** Needs
  `gl_PrimitiveID` to be *exact* on the reference driver (open, see §2), explicit `layout(location = …)` for the
  shared attributes (on the reference driver an unused attribute was dropped once, AD-018 §7 hotfix), and a placement
  decision against AD-018:
  - **B2-in:** a second program, an FBO and an edge index buffer inside `GLRenderStore`. This **reverses** the
    AD-018 §5 binding constraint ("not a general GPU resource manager … no pluggable passes") and the §7 rejection of
    "a second drawable group inside `GLRenderStore`" (see also the store's docstring, `gl_render_store.py:29-35`).
  - **B2-out:** an ID pass **outside** the store that draws the store's public `vertex_list()`
    (`gl_render_store.py:604-607`) and the face data, as the overlays do (AD-018 §7). Precedent-conform. It needs an
    injection point for the GL picker into the window-free `Application` (cf. the `store_type` / `point_overlay_type`
    pass-through) and a data direction Viewport → `mirai`.

Within B, two pick variants (spike):

- **ids:** a pick decides among the IDs in the read window by exact screen distance. Fastest, no per-camera CPU work at
  all; Box loses elements that share a pixel (up to 37 %).
- **depth oracle:** the face depth buffer answers "is this point visible"; candidates come from the CPU rule. Box
  keeps today's semantics within 0-6.5 % (more permissive); hover adds the one-ring of the IDs found. For Box the
  candidates need the projection of all vertices (one O(V) pass per Box gesture, not per frame).

### C. Hybrid: GPU only as the occlusion oracle, CPU scans stay

Removes the occlusion tests (already ~0.1 ms after Slice 2) but not the per-camera projection - does not answer the
problem. Listed because it is the smallest change.

### D. Vectorised CPU projection (NumPy)

Not used so far. Recorded reason (drag_cost "Fix options"): a new dependency and an instruction-set risk on the
Core 2. Measured 2026-10-20 [RPC]: NumPy 2.5.4 under Python 3.14.2 does **not** import (x86-64-v2 baseline);
NumPy 2.2.6 under Python 3.12.10 (the PyCharm interpreter) imports (import only, no timing)
([REFERENCE_HARDWARE](REFERENCE_HARDWARE.md) §2). It would still project every vertex per camera change, only faster;
not measured for picking.

### Comparison

| | status quo | A world index | B1 | B2-in / B2-out | C | D NumPy |
|---|---|---|---|---|---|---|
| navigation cost, 20k [RPC] | 150-190 ms | ray queries, no per-camera rebuild (unmeasured for vertex/edge) | 2.4-3.8 ms | 2.4-3.8 ms expected (B1 measured) | CPU projection stays | faster projection, still per camera change (unmeasured) |
| cost per topology op / undo | - | +0.65 s (container build) unless incremental | **+0.8 s** | none extra expected | - | - |
| cost per W move | - | refit | patches ID buffers too | none extra expected | - | - |
| changes the picks (Artist check) | no | no | yes (§4) | yes (§4) | no | no |
| built / measured | yes | only the BVH ray query and build (audit) | spike, [RPC] | mechanism on llvmpipe only | no | no |
| contracts touched | VIEWPORT_V02 §1, §4.6 | VIEWPORT_V02 §1, §4.6 | VIEWPORT_V02, picking path | + AD-018 §5/§7 (B2-in) or an injection point (B2-out) | - | dependency |

Engineering preference (`PROVISIONAL`, an unprototyped one): B2-out if `gl_PrimitiveID` is exact on the reference
PC, else B1 only with a decision on its +0.8 s per operation; `ids` for hover / click / face, the depth oracle for
Box; Paint samples are hover picks (`_pick`) and take the hover variant unless the Artist check shows otherwise.

## 4. What changes for the Artist (needs a practical check, not provable)

1. **Silhouettes / grazing angles:** visibility comes from the depth buffer with a slope-scaled offset, not from the
   ray test with `DEPTH_TOLERANCE` (1e-3 world units, mesh-scale dependent). Elements at the visibility border can
   flip; a Box with the depth oracle selects up to ~6 % more elements (some on the back side). The two thresholds
   scale differently with mesh size and zoom; the spike tests one scale and two framings.
2. **Pixel sampling:** a face pick samples the pixel centre (the CPU uses the pixel corner); 13-21 % of the random
   cursors on a dense mesh sit on a face border where this decides. This is also a **correctness rule** for every
   path that combines a GPU ID with CPU math (§6, mixed paths).
3. **Sub-pixel density:** where several vertices / edges fall into one pixel (87.5k framed whole), the hover picks one
   of them, not necessarily the CPU's nearest.
4. Wireframe stays "everything pickable" (no depth test).
5. **Small meshes:** the GPU path buys nothing on head/body; a size threshold is an option.

## 5. What it touches

- `VIEWPORT_V02_ARCHITECTURE.md`: §1 non-goals ("GPU ID-buffer picking / `glReadPixels` selection"), §4.6 ("Do NOT
  build"), §11; also §5.3 (the hover flow gets a render pass), §5.2 / §5.4 / §7 (B1: ID buffers patched on a move,
  rebuilt on topology), §14 (a stall risk row), §15 ("Hover event time < 5 ms" acceptance), §16 (a future-work item
  becomes current); `VIEWPORT_V02_RESEARCH.md` §13 / §21 (explicit "no `glReadPixels` hover readback": a dated note).
- **AD-018:** §5 binding constraint and §7 rejection (see B2-in / B2-out); resize recreates the FBO.
- `Application` picking path: one picker interface with two implementations (GPU in the window, CPU headless);
  `PickCache` remains for the CPU path, for the Knife's exact math **and for the Knife planner**
  (`knife_planner.py`: crossings use `PickCache.vertex_screen` and CPU occlusion tests, so a Knife session keeps the
  per-camera rebuild unless slice 3 includes it).
- **Call sites that must switch together** (one sampling convention, §6): `_pick` (hover, click, Paint, Tweak press),
  the Box/Paint start-decision `pick_face`, `elements_in_rect`, `_knife_pick` and the planner, `_pick_object`.
- **Hover coalescing does not "fit as is":** `update_viewport` calls `flush_hover()` **before** `viewport.sync()`, and
  after a topology op, an undo/redo and a W commit the hover is re-picked at once, before the buffers are synced.
  A GPU pick reads the buffers of the *previous* mesh state at those points and can return dead or different IDs (the
  project has precedent: a stale hovered ID once crashed the draw loop, `application.py` `_notify_topology_changed`).
  The pick path must sync first, or fall back to the CPU picker before the sync, or defer the re-pick to the tick after
  the sync.
- **AD-021:** RD-4 ("what you can click must not depend on how it is drawn") - the ID pass ignores display style,
  which means no culling although the production draw culls back faces; ghosts and Wireframe-ignoring References are
  opaque in an object pass. RF-2 / RF-6: the component ID pass draws the edit object only; per-object ID spaces or an
  object-ID target for object picking; retopology snapping to a Reference needs its own Reference pass (the
  component pass must not draw it).
- **H7 (display-only surface providers):** the ID pass draws the cage, `self.render_mesh`, never the replacement
  surface (`viewport.py` H7 contract: "Picking ist nicht betroffen"). Whether occlusion *should* follow the shown
  SubD surface is an Artist question (§7).
- **AD-020 §7 8 ms W-drag bar:** B1 adds patch work per move unless deferred to the end of the gesture (hover is off
  during W, so deferral is possible).
- **[AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md):** see §6, "Coupling".
- **Tests:** the CPU/GPU agreement becomes a GL test with tolerances (no bit equivalence); the CPU picker keeps its
  equivalence tests. `test_application_hover_coalescing.py` and all Lab trees run `Application` headless and never reach
  the GPU path; GL tests need Xvfb and are *skipped* without it. llvmpipe differs from the reference driver (line
  rasterisation, polygon-offset units, attribute handling). Needed: known-answer GL scenes (the spike's), an agreement
  floor on **non-trivial** cursors, a stale-buffer test (a pick right after an op and after an undo with no tick in
  between), and a one-command reference-PC GL check run once per driver or hardware change.
- **REFERENCE_HARDWARE §4:** GL 3.3 suffices (FBOs, `glReadPixels`, `gl_PrimitiveID`, `gl_VertexID` are 3.3 core); the
  risk is the driver, not the version. pyglet is unpinned (`requirements-dev.txt`); B2 relies on
  `IndexedVertexDomain.draw_subset` (one `glDrawElements` per list, which is why `gl_PrimitiveID` starts at 0) and on
  the sampler-buffer workaround: pin or test it.
- **CORE_V1_FREEZE:** unaffected (nothing under `src/core`).

## 6. Risks

- Stale ID buffers after an op, an undo or a W commit (§5, hover coalescing).
- **Mixed GPU-ID / CPU-math paths:** `knife_pick` takes the face from the picker and computes the hit position on
  the CPU at the cursor; if a GPU face ID sampled at the pixel centre is combined with CPU math at the cursor corner,
  the face can be one the cursor ray misses and the Knife treats the point as "outside" (a cut in empty space)
  *(reading; not built)*. One sampling convention for every combined path, with a test.
- Read-back stall per pick in the real loop: `glReadPixels` waits for the GPU to drain whatever is queued; measured
  only in a hidden window with nothing else queued, p50 only. Tails, window sizes (a full-screen Box at 1920x1080 is
  unmeasured), HiDPI and viewport-state restoration after the ID pass (`id_picker.render` sets `glViewport` and does
  not restore it) are unmeasured.
- Two pickers to keep in step (GPU in the window, CPU headless); a divergence shows only in GL tests, and the shipped
  path would be the least-tested path.
- Placed objects and several objects (AD-021): model matrices and per-object ID spaces are not in the spike.
- B1 doubles the W-drag patch cost of the ID buffers and adds ~0.8 s to every operation; B2 depends on an exact
  `gl_PrimitiveID`, explicit attribute locations and the AD-018 placement.
- The ID pass renders all three targets per camera state; only the active mode's target plus the face depth is needed
  (87.5k: 10.3 ms GPU time [RPC], about one frame).
- The planned hardware upgrade changes the driver landscape (the reference PC may stop being the floor).

**Coupling with AD-023 (decide together):** the AD-018 buffer contract (B2's pass and AD-023 V1's patching share the index
buffer, the triangle → face-row map and a new edge index buffer; spare or dead triangles must produce no fragment or map
to "no face"), B1 vs B2 (B1's per-operation build conflicts with AD-023's goal), and the sync / hover ordering (V2).
Independent: history H0-H2 and the §4 semantics. With B2 the hover re-pick column of AD-023 §1 shrinks to one ID render
plus a read (about 3 ms [RPC], *(reading)*); AD-023 P (incremental pick cache) is "moot for the window" only if this AD
is decided.

## 7. Questions for Manu

Priority and feel, no technical choice (the technical choice stays with engineering and the review):

1. Which mesh size must be fluid **for editing**: 20k only, or also the 87.5k mesh? (87.5k is about one frame per
   camera change even with B [RPC]. Open in drag_cost.)
2. The reference PC: floor of the product, or today's test machine? (Answered 2026-10-20: test machine until a modern
   PC is bought in the coming months; recorded in REFERENCE_HARDWARE §3. This sets how much a legacy-driver risk weighs.)
3. At the silhouette, should a Box rather take **a few too many** (possibly back-side) elements, or **a few too few**?
   (The depth variant errs towards more.)
4. With SubD / Morph shown (H7), should you pick and see through the **displayed surface** or the **cage**?
5. Order relative to AD-023 (both "equally important"): decided together (§6, Coupling), in parallel slices, or one
   after the other?
6. **After slice 1, behind a switch you can toggle in `src/main.py`:** are the §4 differences acceptable? (A practical
   check only exists then; the spike's "practical test" is a probe run.)

## 8. Evidence still needed

- **Before choosing B1 vs B2:** one reference-PC run that `gl_PrimitiveID` gives exactly the B1 face IDs per pixel
  (the review's probe P2 is that check, about a minute to run), and the AD-018 placement decision (B2-in vs B2-out).
  The check now exists as a script: [`experiments/topology_stage2_delete/check_b2.py`](../../experiments/topology_stage2_delete/check_b2.py)
  (B2-out, built 2026-10-21 for the AD-023 stage-2 Delete prototype; also after a patched Delete with degenerate
  triangles and its Undo, plus the point pass, CPU agreement and pick cost). Container [C]: exact on every pixel;
  the ID vertex shader must use the production expression `u_proj * u_view * (u_model * p)` (another association
  differed on 2 px). **Reference PC (2026-10-21) [RPC]: exact** on every pixel, fresh and after a patched Delete
  and its Undo, point pass (`gl_VertexID`) too; `position` at location 0 in the store's and both ID programs; one
  pick after a camera change 2.8 ms (face) / 5.6 ms (vertex, max 24 ms in 20). This settles the `gl_PrimitiveID`
  question for B2 on the 9800 GTX; the AD-018 placement (B2-in vs B2-out) is still a decision - the prototype is
  B2-out.
- **After the direction is decided, inside slice 1, with the abort criteria of §9:** the in-loop read-back with p95 / max
  (the `loop` scenario of `probe_navigation_gl.py` on the reference PC), the ordering fix, the call-site inventory,
  a playable switch for Manu, the tests of §5.
- **Slice 3:** the Knife sampling convention (§6).

## 9. If decided: proposed slices (not started)

1. The sync / hover ordering fix first. Then B behind a switch for **every** call site of §5 that decides a face, vertex
   or edge from a cursor (`_pick`, the Box/Paint start decision, Tweak press), CPU path unchanged headless; agreement
   GL test on non-trivial cursors; the per-camera `PickCache` rebuild skipped when the GPU path serves the pick. A debug
   mode runs both pickers and logs divergences in the window (cf. AD-023 §4's debug compare).
2. Box (`elements_in_rect`) through the depth oracle. (Paint samples are hover picks and are in slice 1.)
3. Knife: candidates through the ID buffer, exact `t` / hit position on the CPU with the **same sampling convention**;
   the planner either included or stated as keeping its CPU rebuild. Object picking.
4. `VIEWPORT_V02` / AD-018 text, ATELIER, practical test per slice.

**Abort or roll back slice 1 if any of these holds on the reference PC:**
1. the first pick after a camera change or a zoom notch, in the real loop, has p95 > 16.7 ms on `gollum_20k`, or any
   read-back hitch exceeds one frame;
2. the agreement on non-trivial cursors falls below an agreed floor, or any "GPU none / CPU element" occurs on a
   visible element in framed views;
3. any stale-ID or crash case after an op, an undo or a W commit;
4. a GL error or an incomplete FBO at start or resize (the CPU path then takes over automatically);
5. Manu rejects the feel in the switchable practical check.

## 10. Review disposition (CLAUDE-001, 2026-10-20)

| Finding | Disposition |
|---|---|
| F1 evidence is the container run (blocker) | Accepted. §1, §2 rewritten with [RPC] as the primary column; the §8 status note moved into §2/§8; sample sizes stated. |
| F2 agreement denominator | Accepted. Non-trivial figures, the "framed views" qualification, the close-zoom observation and the Box range (0-6.5 %) are in §2. |
| F3 B2 unbuilt, AD-018 collision | Accepted. B2-in vs B2-out in §3; injection point named; recommendation marked unprototyped; P2 as the evidence step (§8). |
| F4 hover coalescing / stale buffers | Accepted. §5, §6, §9 (ordering fix first, test). |
| F5 options not compared equally | Accepted. Status quo and NumPy (D) added with the recorded reason; comparison table; the preference marked `PROVISIONAL`. |
| F6 contract list incomplete | Accepted. §5 completed. |
| F7 AD-023 interaction | Accepted. §6 "Coupling"; AD-023 §1 is corrected there. |
| F8 pixel convention | Accepted. §4.2, §6 (mixed paths), slice 3. |
| F9 Artist questions | Accepted. §7 reworded as priority questions; four questions added; question 2 moved behind a switch after slice 1. |
| F10 abort criteria, call sites | Accepted. §5, §9. |
| F11 tails, in-loop | Accepted. §2 "Not covered", §6, §8. |
| F12 minor corrections | Accepted: "233" dropped; edge agreement 96.3 % / 92.3 %; the "Manu's preferred direction" header quoted as a priority statement; Paint noted; the Reference pass for snapping; small meshes; one-target pass; pyglet pinning. |
| F13 least-tested path | Accepted. §5 Tests. |

## 11. Implementation (2026-10-21, production)

**Direction taken: B2-out**, `ids` for hover / click (slice 1), the depth oracle for Box (slice 2); the Knife, object
mode and every headless path keep the CPU picker (slice 3 not done). Engineering choices, `PROVISIONAL` where marked.

- **`src/viewport/gpu_picker.py` (`GpuPicker`)**, outside `GLRenderStore` (AD-018 §5/§7 untouched): one FBO, three
  RGBA8 targets + depth. Faces = the `RenderMesh` VertexList with `gl_PrimitiveID + 1` → triangle slot → face
  (`RenderMesh.face_of_triangle`); edges = `GL_LINES` from an own element buffer over the same vertex buffer
  (`glDrawElementsBaseVertex`), `gl_PrimitiveID + 1` → edge slot; points = `glDrawArrays(GL_POINTS)`, `gl_VertexID` →
  vertex slot. `position` bound at the store program's location; the ID vertex shader uses the production expression.
  Passes render on demand and are cached per (buffer content revision, layout, camera, model matrix, size, occlusion).
- **Buffer contract with AD-023 V1:** `RenderMesh` gains an **edge slot layout** (`edge_indices`, spare capacity,
  free slots = zero-length lines, patched from the journal like the triangles; `take_edge_changes()` lets the picker
  upload only changed ranges) and `layout_revision` / `content_revision`. Dead triangles are degenerate (no fragment),
  dead vertices sit at `DEAD_POSITION` and are clipped in the ID vertex shader.
- **`src/mirai/viewport/gpu_picking.py`:** the decision among the GPU candidates is the CPU rule: nearest vertex within
  14 px / edge within 9 px by exact screen distance (ties by ID), face = the pixel under the cursor (pixel-centre
  convention). Box = the CPU candidate rule (all corners inside, `PickCache` projections, one O(V) pass per Box) with
  the face depth as the visibility test; a face whose centroid is hidden only by itself counts (its own ID at the
  centroid's pixel).
- **`Application`:** `_pick` (hover, click, Paint, Tweak press), the Box/Paint start decision and Box use the GPU path
  when the window has a GL store (`Viewport.gpu_pick_mesh`), else the CPU picker. **Ordering fix (§5):** the pick
  syncs the edit `RenderMesh` first when anything is pending, so a pick right after an op or an Undo reads the new
  buffers. **Fallback (§9 abort 4):** any exception in the ID pass switches the session to the CPU picker with a status
  line; `MIRAI_CPU_PICKING=1` forces the CPU picker; `Application.gpu_picking` is the switch for comparison runs.
- **Tests (GL, `xvfb-run -a python -m pytest tests/test_gl_gpu_picking.py`)**, each on the compact layout and the slot
  layout: face IDs at pixel centres equal the CPU ray (only face-border neighbours may differ, ≤ 2 %); vertex / edge
  hover agree with the CPU picker on ≥ 88 % of non-trivial cursors and never name a dead element; a pick right after a
  Delete and its Undo (no frame in between) equals the CPU pick; Box within 8 % of the CPU rule per mode; a GL failure
  falls back. Mutation checks: an off-by-one slot mapping and a missing sync before the pick each fail.
  `tests/test_render_mesh_incremental.py` also checks the edge slots after every patch.
- **Measured [C]** (container, llvmpipe = software GL, `probe_picking_app.py`, gollum_20k, p50 ms CPU → GPU; raw:
  [`RESULTS_PICKING_APP_CONTAINER_2026-10-21.md`](../../experiments/drag_cost/RESULTS_PICKING_APP_CONTAINER_2026-10-21.md)):
  first pick after an orbit vertex / edge / face 77 / 68 / 47 → **16 / 21 / 11**; hover 2.7 / 12.8 / 2.4 →
  **0.3 / 0.5 / 0.02**; Box 300 px 1 020 / 1 997 / 1 122 → **85 / 113 / 152**; Delete + re-pick 2.8 → 14 (llvmpipe
  re-renders the ID pass in software; the reference PC rendered it in 1-3 ms, §2). **Reference PC not measured.**
- **Open:** the edge pass relies on `gl_PrimitiveID` for `GL_LINES` and on `glDrawElementsBaseVertex`, **not yet
  checked on the 9800 GTX** (the GL test file is that check); §4 differences are for Manu's practical check; the Knife
  (picker and planner) still projects the whole mesh per camera change; object picking (mode `4`) is CPU; the Box
  still projects every vertex once per gesture; H7 surfaces: the ID pass draws the cage (contract unchanged).

### Praxistest für Manu (ca. 10 Minuten + zwei Befehle)

Technisch belegt durch die GL-Tests (gleiche Faces wie der CPU-Picker, keine toten IDs nach Delete/Undo, Box innerhalb
weniger Prozent). Offen ist, was nur dein PC und dein Gefühl zeigen:

- **Treiber-Check (PowerShell im Repo-Ordner, ganze Ausgabe kopieren):**
  `python -m pytest tests\test_gl_gpu_picking.py -q` — prüft u. a. die Edge-IDs auf deiner Karte (noch nie dort gelaufen).
- **Messen:** `python experiments\drag_cost\probe_picking_app.py`
- **Fühlen:** `python src\main.py`, `Leertaste` → `gollum_20k`. Drehen/Zoomen, dann sofort hovern und klicken in
  Vertex (`1`), Edge (`2`), Face (`3`); Box-Auswahl über viele Faces; Malen. Zum Vergleich einmal mit
  `$env:MIRAI_CPU_PICKING=1; python src\main.py` (alter CPU-Picker).

| Frage | Dein Verdikt                                                                     |
|---|----------------------------------------------------------------------------------|
| Hover/Klick direkt nach dem Drehen ohne sichtbare Verzögerung? | Ja                                                                               |
| Box über viele Faces: schnell genug? | schon sehr viel besser, kann man evtl noch etwas optimieren, aber vorerst gut so |
| Wählt Box an der Silhouette sinnvoll (eher ein paar zu viele als zu wenige, §7 Frage 3)? | vorerst gut so. Dokumentieren, dass das evtl. später nochmal begutachtet wird    |
| Irgendwo ein anderes Element gegriffen als erwartet? | Nein                                                                             |
