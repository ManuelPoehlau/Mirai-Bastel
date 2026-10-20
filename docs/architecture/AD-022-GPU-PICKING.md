# AD-022 — GPU ID-Buffer Picking

**Status:** PROPOSED (2026-10-17) - draft for Manu's decision and an independent review (fresh
session, Development System §6). Not decided; no production code exists. Per AGENTS.md §5 this
document lists alternatives, it does not select one.
**Mode (M5):** Discovery, decision preparation.
**Work package:** WP-VIEW-PERF-02 (follows WP-VIEW-PERF-01 Slices 1 + 2).
**Artist input:** Manu, 2026-10-17, on the Slice-1 practical test: "Fühlt sich gleich an, nur schneller. Im
Vergleich zu Blender auf meinem PC aber noch wesentlich langsamer. Dort lässt sich 20k Gollum sehr flüssig
zoomen, Komponenten picken oder Topologie-Operationen ausführen." On the Haltepunkt note: "gpu picking bringt
wohl den größten Gewinn" and "ja, ist beides gleich wichtig" (GPU picking and incremental topology,
[AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md)). Intent: Blender-level fluidity on 20k on the
reference PC. Priority: equal with AD-023.
**Basis (only linked):** [`experiments/drag_cost/README.md`](../../experiments/drag_cost/README.md) ("Result: fix
slice 2", "Haltepunkt: what Blender-level fluidity on 20k would need");
[`experiments/gpu_picking_spike/README.md`](../../experiments/gpu_picking_spike/README.md) (the evidence below);
[`VIEWPORT_V02_ARCHITECTURE.md`](../viewport/VIEWPORT_V02_ARCHITECTURE.md) §1 (non-goals), §4.6, §11;
[AD-018](AD-018-PRODUCTION-DRAW-BINDING.md); [REFERENCE_HARDWARE](REFERENCE_HARDWARE.md) §2, §4;
[AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) (object picking, placed objects).
**Decided by:** Artist (Intent, Priority, the semantic checks in §4) + review. Engineering decides the variant
details inside a decided direction.

---

## 1. Problem

After the two CPU slices the picking cost on `gollum_20k` (21 875 V; container, Python 3.13, ms p50) is:

| | now | grows with |
|---|---:|---|
| first pick after a camera change (zoom notch, after orbit/pan) | ~60-70 per frame | V + F, every camera change (`PickCache.refresh` projects every vertex and face) |
| hover / click with a valid cache | 3-4 event | V, E (linear scans) |
| Box 300 px | 0.3-0.9 s | elements in the box |

The camera-change cost is the CPU design itself: a screen-space picker must project the mesh for every new
view. Nothing local to `mirai/viewport` removes it (Slice-2 reading, drag_cost README). On the 87.5k Reference
mesh it is 150-230 ms per camera change.

## 2. Evidence (spike, container - llvmpipe, the "GPU" is the CPU)

`experiments/gpu_picking_spike/` renders faces / edges / vertices with their IDs into an offscreen framebuffer
and reads back the pixels under the cursor; nothing under `src/` changed.

- **Cost:** pick after an orbit gollum_20k 42-74 → 11-17 ms, 87.5k 210-233 → 43-49 ms, of which the ID render
  is 13 / 48 ms on llvmpipe (the 9800 GTX draws gollum_20k in 0.56 ms, 2026-10-11, so ~1-3 ms is expected -
  not measured). Hover with a valid render 0.06-0.8 ms on both sizes (CPU 2.4-67). Box 300 px 0.87 s → 24 ms
  (20k), 6.9 s → 78-92 ms (87.5k).
- **Same picks:** hover/click 97-99 % identical on body and gollum_20k (vertex with the depth oracle 98.7 %),
  89-97 % on 87.5k; every difference is the neighbouring element in the same pixel. Face picks differ only by
  the half-pixel sampling convention. Box: the pure ID read loses up to a third of a dense box (one ID per
  pixel); the depth-oracle variant keeps the CPU rule within 0-4 %.
- **Not covered:** the reference PC (cost and driver), Knife, Paint, object picking, snapping, placed objects,
  resize, W drags.

## 3. Options

### A. Stay on the CPU, camera-independent world index (option 9 of the drag_cost README)

BVH / grid over triangles in object space, built per mesh state; rays for face / occlusion, a frustum query
for "nearest within 14 px". Build 0.65 s (21.9k) / 3.2 s (87.5k) in pure Python (audit) after every topology
op, refit per W drag. Keeps bit-level testability on the CPU; moves cost from navigation to editing (collides
with AD-023). Touches `VIEWPORT_V02` §1 ("BVH / Octree / KD-tree") and §4.6. Listed for comparison.

### B. GPU ID-buffer picking (Manu's preferred direction)

An ID pass per camera state, rendered on demand (only when a pick needs it), read back in small windows.

- **B1 - own buffers (what the spike built):** unindexed face triangles with a per-vertex ID attribute, an
  edge line list, a point list. No `gl_PrimitiveID` (driver-safe). Cost: 3x the triangle vertex data per mesh
  state (0.2 / 1.1 s Python build on 20k / 87.5k), patched on every W drag move in addition to the draw buffers.
- **B2 - from the `RenderMesh` buffers:** a second program over the same `positions` / `indices` VertexList
  (face ID = `gl_PrimitiveID` → face row, the same `u_triangle_faces` buffer texture the Flat shading uses since
  2026-10-15), plus an edge index buffer and a point draw over `positions`. No duplicate vertex data, W drags
  patch nothing extra. Needs `gl_PrimitiveID` on the reference driver (open, REFERENCE_HARDWARE §2) and an AD-018
  addendum (a pass that is not the mesh draw, an FBO owned by `GLRenderStore`).

Within B, two pick variants (spike):

- **ids:** a pick decides among the IDs in the read window by exact screen distance. Fastest, no per-camera
  CPU work at all; Box loses elements that share a pixel.
- **depth oracle:** the face depth buffer answers "is this point visible"; candidates come from the CPU rule.
  Box keeps today's semantics (0-4 %); hover adds the one-ring of the IDs found (98.7 % on 20k). For Box the
  candidates need the projection of all vertices (one O(V) pass per Box gesture, not per frame).

Recommended shape if B is chosen (engineering, `PROVISIONAL`): B2 if `gl_PrimitiveID` is reliable on the
reference PC, else B1; ids variant for hover / click / face, depth oracle for Box and Paint; the CPU picker stays
as the headless reference and the fallback where no GL context exists (`TraceStore`, the tests, hosts without
a window).

### C. Hybrid: GPU only as the occlusion oracle, CPU scans stay

Removes the occlusion tests (already ~0.1 ms after Slice 2) but not the per-camera projection - does not answer
the problem. Not recommended; listed because it is the smallest change.

## 4. What changes for the Artist (needs a practical check, not provable)

1. **Silhouettes / grazing angles:** visibility comes from the depth buffer with a slope-scaled offset, not
   from the ray test with `DEPTH_TOLERANCE`; elements at the visibility border can flip (Box: 0-4 % at 300 px
   on dense meshes, depth variant).
2. **Pixel sampling:** a face pick samples the pixel centre (the CPU uses the pixel corner); 13-21 % of the
   random cursors on gollum sit on a face border where this decides.
3. **Sub-pixel density:** where several vertices / edges fall into one pixel (87.5k framed whole), the hover
   picks one of them, not necessarily the CPU's nearest.
4. Wireframe stays "everything pickable" (no depth test).

## 5. What it touches

- `VIEWPORT_V02_ARCHITECTURE.md` §1 non-goals ("GPU ID-buffer picking / `glReadPixels` selection"), §4.6 ("Do NOT
  build: GPU ID-buffer, `glReadPixels`"), §11 (picking acceleration outside v0.2) - amend on decision.
- AD-018: B2 adds a pass, an FBO and an edge index buffer to `GLRenderStore`; resize recreates the FBO.
- `Application` picking path: one picker interface with two implementations (GPU in the window, CPU headless);
  `PickCache` remains for the CPU path and for the Knife's exact math. Hover coalescing (Slice 2) fits as is: the
  tick renders the ID pass once per camera state.
- Knife (`mirai.topology.knife_pick`), Paint, object picking (AD-021 M1, across objects: one ID space per
  object or an object-ID target), retopology snapping (face ID + depth = hit position).
- REFERENCE_HARDWARE §4: GL 3.3 suffices (FBOs, `glReadPixels`, `gl_PrimitiveID` are 3.3 core); the risk is
  the driver, not the version.
- Tests: the CPU/GPU agreement becomes a GL test with tolerances (no bit equivalence); the CPU picker keeps its
  equivalence tests.

## 6. Risks

- Read-back stall per pick on an old driver (`glReadPixels` synchronises the pipeline) - measured only on
  llvmpipe so far.
- Two pickers to keep in step (GPU in the window, CPU headless); a divergence shows only in GL tests.
- Placed objects and several objects (AD-021): model matrices and per-object ID spaces are not in the spike.
- B1 doubles the W-drag patch cost of the ID buffers; B2 depends on `gl_PrimitiveID`.

## 7. Questions for Manu

1. Direction: B (GPU picking) as preferred - confirmed after the reference-PC spike run?
2. Are the §4 differences acceptable after a practical check (they cannot be avoided by any GPU variant)?
3. Order relative to AD-023 (both "equally important"): in parallel slices, or one after the other?

## 8. Evidence still needed before a decision

**Stand 2026-10-20 (Evidenz, keine Entscheidung):** der erste Punkt ist beantwortet - der Spike lief auf dem Referenz-PC (20k und
87,5k, [`RESULTS_REFERENCE_PC_2026-10-20.md`](../../experiments/gpu_picking_spike/RESULTS_REFERENCE_PC_2026-10-20.md)); Manu meldet für den
zweiten Punkt Flat ohne Flecken (und keine sichtbaren Dreiecke in Smooth und Flat, flüssig; Intake Log 2026-10-20). Die unabhängige Review liegt vor ([`AD-022_REVIEW_CLAUDE_001`](../archive/viewport_v02/reviews/AD-022_REVIEW_CLAUDE_001.md), ACCEPT WITH CHANGES); ihre Änderungen am AD-Text sind noch nicht eingearbeitet. Offen:
Knife/Paint/Objekt-Pick, die Wechselwirkung mit H7-Flächen (SubD, Morph) und die Entscheidung.

- The spike probe on the reference PC (README "Praktischer Test"): ID render + read-back cost on the 9800 GTX.
- Flat shading on the reference PC per polygon (evidence for `gl_PrimitiveID`, decides B1 vs B2).
- The independent review of this draft.

## 9. If decided: proposed slices (not started)

1. B behind a switch for hover / click (vertex, edge, face) in the window; CPU path unchanged headless;
   agreement GL test; the per-camera `PickCache` rebuild skipped when the GPU path serves the pick.
2. Box and Paint through the depth oracle.
3. Knife candidates through the ID buffer (exact `t` / hit position on the CPU), object picking.
4. `VIEWPORT_V02` / AD-018 text, ATELIER, practical test per slice.
