# Viewport v0.2 — Produktions-Architektur-Spezifikation

**Status:** Architecture Specification — ready for implementation after review  
**Derives from:** `VIEWPORT_V02_RESEARCH.md` + V0.2 Proof-of-Architecture Review  
**Scope:** Incremental update architecture for responsive polygon/SubD modeling viewport  
**Target Platform:** Low-end developer hardware (Intel i5 Gen 4, 4GB RAM) is first-class  
**Reference Mesh:** `experiments/rigging-skinning-morphing/meshes/head_basemesh.obj` (326V, 324Q)  

---

## 1. Goals and Non-Goals

### Primary Goal

> **Replace V1's "rebuild everything" update model with "update only what changed".**

This addresses the structural root cause: V1 spends ~95% of interaction time on global geometry rebuilds and normal recomputation, not on rendering.

### Secondary Goals

- Keep interaction latency < 15 ms for camera/selection/hover on the reference mesh.
- Remain responsive on 7–10-year-old developer hardware.
- Establish a measurement-driven precedent: performance claims must state exactly what is measured.

### Explicit Non-Goals

**Do not build in v0.2:**

- GPU ID-buffer picking / `glReadPixels` selection
- BVH / Octree / KD-tree
- ECS or Render Graph
- Custom GPU resource manager
- GPU compute normal pipeline
- Automatic LOD / Fast Navigate
- Blender-style Draw Manager
- Multithreaded renderer
- Vulkan backend

These may be introduced **only if a measurement benchmark proves they solve a real bottleneck**. Premature optimization is the primary risk for v0.2.

---

## 2. Core Architecture Principle

```
              Event (camera move, vertex drag, selection, etc.)
                           ↓
                      [Dirty State]
                    (what changed?)
                           ↓
                    [Update Only That]
                  (precise, minimal work)
                           ↓
                   [Persistent GPU State]
                   (no unnecessary recreations)
                           ↓
                         [Draw]
```

**The key rule:**

> For every interaction event, determine the smallest set of render data that must change. Update only that set.

---

## 3. Verified Architecture Invariants

These are established by the V1 profiling investigation and should hold unless new evidence contradicts them:

| Invariant | Evidence | Implication |
|-----------|----------|-------------|
| **Camera changes never invalidate mesh render data** | Profiling: Camera orbit = 87% time in `_rebuild_geometry`, 0% in drawing | Store view/projection in uniform buffers; never recreate mesh geometry for camera moves |
| **Selection changes never invalidate base mesh geometry** | Profiling: Selection is independent of mesh rebuild | Selection state lives in separate overlay layer; highlight is not part of base geometry |
| **Normal interaction should not recreate GPU resources** | V1 profiling: each event recreates VertexLists (~4.5 ms waste) | Pre-allocate persistent VertexLists; patch content instead of recreating |
| **Position changes should update only affected derived data** | V1 bottleneck: global normal recomputation for single-vertex drag (62 ms normals per event) | Build `vertex_to_faces` mapping; compute only affected face normals; update only affected vertex-normal range |
| **Topology changes may trigger larger rebuilds** | V1 profiling: Topology-aware changes (edge operations) vs. position-only | Define clear topology boundary; allow structural rebuild only when index buffer structure changes |
| **Low-end hardware is a first-class target, not a limitation** | Explicit project principle | Design interaction paths to be allocation-light; avoid assumptions about RAM/VRAM availability |

---

## 4. Components and Responsibilities

### 4.1 Camera

**Responsibility:** View and projection matrices; event handling; screen-space math.

**Guarantees:**
- Camera updates never call `rebuild_geometry()`.
- View/projection live in uniform buffers or function parameters, not mesh data.

**Update Path:**
```
camera.orbit(delta)
  → update matrices
  → mark camera_revision++
  → [no geometry invalidation]
  → draw()
```

### 4.2 RenderMesh

**Responsibility:** Persistent GPU geometry; dirty state tracking; update dispatch.

**Owns:**
- Pyglet VertexList(s) for positions, normals, colors, indices (allocated once, patched on update)
- `topology_revision`, `position_revision` (see §5.1)
- `modified_vertices` set (sparse set of vertex indices that changed)
- Minimal adjacency structure: `vertex_to_faces` (precomputed, updated on topology change)
- Bounds/AABB (cached; invalidated with position changes)

**Does NOT own:**
- GPU resource creation/deletion (handle via pyglet; do not wrap it)
- Render passes, layers, or view frustum
- Selection state (belongs to Overlay)

**API contract:**
```python
class RenderMesh:
    def __init__(self, mesh: Topology):
        # Allocate persistent GPU resources once
        pass
    
    def update_positions(self, modified_vertex_ids: set[int]):
        # Patch position buffer for given vertices
        # Recompute affected normals
        # Update bounds
        pass
    
    def update_topology(self, new_mesh: Topology):
        # Structural rebuild (allowed for topology changes)
        # Reallocate index buffer if needed
        # Rebuild adjacency
        pass
    
    def render(self, camera: Camera):
        # Issue draw call with current geometry + camera matrices
        pass
```

### 4.3 Dirty State / Revision Model

**Purpose:** Determine what render data is out of sync with Core.

**Candidates:**
```python
# Option A: Minimal explicit tracking (recommended)
render_mesh.topology_revision     # bumped on edge/face operations
render_mesh.position_revision     # bumped on vertex moves
render_mesh.modified_vertices     # set of affected vertex IDs
render_mesh.bounds_valid          # boolean cache flag

# Option B: Leverage Core notifications (if available)
# Check Core for existing change/dirty semantics
# before inventing new ones
```

**Synchronization Pattern:**
```python
# Main loop
if core.position_revision != last_render_position_revision:
    render_mesh.update_positions(core.modified_vertices)
    last_render_position_revision = core.position_revision

if core.topology_revision != last_render_topology_revision:
    render_mesh.update_topology(core.mesh)
    last_render_topology_revision = core.topology_revision
```

**Note:** Exact Core-to-viewport change semantics must be validated against actual Core behavior during implementation. This model is a candidate, not a requirement.

### 4.4 Derived Geometry: Normals and Bounds

#### Normal Computation

**Current state:** V1 computes face-average normals per face, then averages them per vertex.

**For v0.2:**
- Precompute `vertex_to_faces` on mesh load (one-time cost).
- On position change:
  1. Identify affected faces: `faces_to_update = vertex_to_faces[modified_vertices]`
  2. Recompute normals for those faces only
  3. Update vertex normals: average only affected face normals
  4. Patch normal buffer for affected vertices

**Expected win:** On 326V mesh, single-vertex move: recompute ~2–6 face normals instead of 324.

**GPU Upload Strategy:**
- If affected normals are contiguous (common case): single `glBufferSubData` call.
- If sparse: either upload the whole buffer (simple, acceptable for small meshes) or use multiple small patches (higher complexity, lower win on reference mesh).

#### Bounds (AABB)

**On position change:**
- Recompute bounds from affected vertices only (or whole mesh if sparse modification).
- Cache result; use for frustum culling in next frame.

**GPU Impact:** None (bounds stay on CPU, used for application-level culling, not shaders).

### 4.5 Adjacency Data: vertex_to_faces

**Definition:** For each vertex, list of face indices that include it.

**Allocated:** On mesh load (one-time).

**Updated:** On topology change (rebuild entire structure).

**Used by:** Normal update, bounds update, potential future picking acceleration.

**Memory:** Small overhead (one integer list per vertex). On 326V mesh: ~326 lists ÷ avg 4–6 faces each ≈ ~1.5 KB overhead.

### 4.6 CPU Picker

**Responsibility:** Determine which vertex/edge/face is under cursor.

**Methods:**
- **Vertex:** screen-space distance (project all vertices; find closest within threshold)
- **Edge:** screen-space segment distance (for all edges in mesh)
- **Face:** ray-triangle intersection (for all faces)

**Complexity:** O(V), O(E), O(F) respectively. For 326V reference mesh: ~7 ms (vertex), ~23 ms (edge), ~2 ms (face) in headless measurement.

**Constraint:** Picking must **not** trigger geometry rebuild merely because the mouse moved.

**Future acceleration:** A simple CPU spatial grid may reduce candidate counts if picking becomes a measured bottleneck on larger meshes. **Not mandatory for v0.2; defer unless benchmarks show need.**

**Do NOT build:** GPU ID-buffer, `glReadPixels`, BVH, Octree, KD-tree for v0.2.

### 4.7 Overlay Layer

**Responsibility:** Visual feedback for hover, selection, and future manipulators.

**Does not modify base mesh geometry.**

**Candidates:**

**Option A: Separate highlight mesh**
- On hover/selection: create small overlay geometry (e.g., highlighted vertices, edges)
- Render in separate pass or with different material
- Zero impact on base mesh VertexList

**Option B: Per-vertex material parameters**
- Reserve color channel or separate buffer for selection state
- Use shader conditional to highlight selected vertices
- Render in single pass; selection state is material, not geometry

**Decision:** Option A (separate overlay) is recommended to ensure selection never invalidates base mesh. Implementation choice to be made during detailed design phase.

---

## 5. Data Flow and Update Sequences

### 5.1 Camera Move (orbit/pan/zoom)

```
User input → camera.move()
    ↓
Update view/projection matrices
    ↓
[No geometry invalidation]
    ↓
render_mesh.render(camera)  [issue draw with new matrices]
    ↓
GPU rasterization only
```

**Expected behavior:** No `modified_vertices`, no normals recomputed, no GPU uploads.

**Measured guarantee needed:** compute_time_ms < baseline ± 5%.

### 5.2 Vertex Position Change (user drags vertex)

```
User input → core.move_vertex(v_id, new_pos)
    ↓
Core updates position
    ↓
viewport detects position_revision change
    ↓
render_mesh.update_positions({v_id})
    ├─ recompute bounds (if position outside old AABB)
    ├─ identify affected_faces = vertex_to_faces[v_id]
    ├─ recompute normals for affected_faces only
    ├─ patch position buffer: positions[v_id] = new_pos
    ├─ patch normal buffer: normals[affected_vertices] = updated
    └─ [GPU resources persist; only content patched]
    ↓
render_mesh.render(camera)
```

**Expected behavior:** Structural rebuild forbidden; only position and normal buffers patched.

**Measured guarantee needed:** compute_time_ms < baseline + 2 ms; no mesh_rebuilds counter increment.

### 5.3 Selection / Hover

```
Picker detects vertex/edge/face under cursor
    ↓
viewport.set_hover_id(element_id)
    ↓
overlay.highlight(element_id)
    ├─ [Option A] create/update small overlay geometry
    └─ [Option B] set material state; use shader conditional
    ↓
[No base mesh invalidation]
    ↓
render_mesh.render(camera)  [base mesh unchanged]
overlay.render(camera)       [overlay on top]
```

**Expected behavior:** Base geometry untouched; highlight is orthogonal.

**Measured guarantee needed:** geometry_uploads == 0; visual feedback < 1 frame latency.

### 5.4 Topology Change (edge split, face subdivide, merge)

```
User input → core.split_edge(e_id)
    ↓
Core updates mesh structure (vertices, edges, faces)
    ↓
viewport detects topology_revision change
    ↓
render_mesh.update_topology(new_mesh)
    ├─ allowed to do structural rebuild
    ├─ reallocate index buffer (if size changes)
    ├─ rebuild vertex_to_faces adjacency
    ├─ recompute all normals (necessary after topology change)
    ├─ recompute bounds
    └─ [GPU resources may be recreated]
    ↓
render_mesh.render(camera)
```

**Expected behavior:** Structural rebuild is appropriate and expected.

**Measured guarantee needed:** structural_rebuilds == 1; topology_updates == 1.

### 5.5 Material/Color Change (future)

**Placeholder for non-geometry visual updates (e.g., per-vertex color, selection highlight).**

Currently: Selection is handled via overlay (§4.7).

If colors become part of base geometry (future): separate update path needed to keep position/normal updates independent.

---

## 6. Update Categories and Dirty State

| Category | Triggers | Invalidates | Update Cost | Frequency |
|----------|----------|-------------|------------|-----------|
| **Camera** | Orbit/Pan/Zoom | Nothing | Uniform update only (~0 ms) | Every frame potentially |
| **Position** | Vertex drag | Normals (affected), Bounds | Recompute affected normals (~1–5 ms typical) | Per-drag event |
| **Selection** | Hover change | Overlay state only | Material/shader state (~0.1 ms) | Per-move |
| **Material** (future) | Color/property change | Derived normals: NO | Small buffer patch (~0.5 ms) | Rare |
| **Topology** | Edge/face operation | Everything | Full rebuild (~50–100 ms) | Rare, explicit |

---

## 7. GPU Resource Persistence

**Principle:** Allocate GPU resources once; patch content; never recreate unnecessarily.

**For v0.2:**

```python
# Initialization (once per RenderMesh)
position_vbo = VertexList(...)      # allocated
normal_vbo = VertexList(...)        # allocated
color_vbo = VertexList(...)         # allocated (if used)
index_ibo = VertexList(...)         # allocated

# Position update
position_vbo.vertices = new_positions  # patch, don't recreate

# Topology update (allowed exception)
index_ibo = VertexList(...)         # OK to recreate here
```

**Measurement:** GPU resource IDs must remain constant across non-topology interactions.

```
initial_resource_ids = {position_vbo, normal_vbo, index_ibo}
[... camera, selection, position updates ...]
final_resource_ids = {position_vbo, normal_vbo, index_ibo}
assert initial_resource_ids == final_resource_ids  # for position/selection/camera
```

---

## 8. Performance Measurement Concept

### What to Measure

**For each scenario:**
1. **Event-to-draw CPU time (ms)** — from event handler entry to `glDrawArrays` call.
2. **GPU stall time** — if profiler available (optional for v0.2, but good to measure).
3. **Memory resident (MB)** — VRAM usage; detect leaks.
4. **Counter metrics:**
   - `geometry_uploads` — count of GPU geometry writes
   - `structural_rebuilds` — count of topology rebuilds
   - `normal_recomputations` — count of normal update calls
   - `bounds_invalidations` — count of AABB recalculations
   - `gpu_resource_creations` / `gpu_resource_destroys`
5. **Visual correctness** — screenshot comparison or manual validation.

### Scenarios (from V1 baseline)

- **Camera move (orbit 360°, 100 frames)** — target: < 1 ms event time
- **Vertex drag (10 vertices, continuous)** — target: < 5 ms event time
- **Hover/selection (move over mesh)** — target: < 2 ms event time
- **Topology change (single edge split)** — target: < 20 ms event time
- **Stress (1000 vertex moves)** — target: no memory growth, consistent frame time

### Comparison

Benchmark v0.2 against V1 **under identical scenarios on the same hardware**.

Report:
- Average event time
- 95th percentile event time
- Peak observed time
- Mesh size and scenario specifics

### Explicit Non-Claims

Do **not** claim:
- "v0.2 is X% faster" without stating the exact scenario and hardware.
- "60 FPS interaction on all meshes" without specifying mesh size and hardware tier.
- Performance targets (<1 ms camera, <5 ms drag) are **hypotheses to be verified**, not guaranteed after implementation.

---

## 9. Implementation Sequence (Recommended)

**After this specification is approved, implementation should be incremental and measurable:**

### Phase 1 — Persistent Render Mesh (Week 1)

- Introduce `RenderMesh` class wrapping pyglet VertexList(s).
- Allocate geometry once at startup.
- Move basic mesh render to use RenderMesh.
- Keep update path identical to V1 initially (all geometry repatch every frame).
- **Goal:** Verify persistent VertexList allocation works; establish measurement baseline.

### Phase 2 — Camera Separation (Week 1–2)

- Remove geometry rebuild from camera move path.
- Patch camera matrices only.
- **Verify:** Camera orbit produces zero geometry uploads; measure CPU time delta.

### Phase 3 — Position Update Dispatch (Week 2)

- Connect Core position changes to `render_mesh.update_positions()`.
- Implement sparse `modified_vertices` tracking.
- Patch position buffer for modified vertices only.
- **Verify:** Single vertex move updates only position buffer; measure CPU time.

### Phase 4 — Incremental Normals (Week 2–3)

- Implement `vertex_to_faces` precomputation.
- Compute only affected face normals on position change.
- Patch normal buffer for affected vertex range.
- **Verify:** Normal update time independent of total mesh size; measure.

### Phase 5 — Overlay and Selection (Week 3)

- Separate selection state from base geometry.
- Implement overlay rendering (separate mesh or material layer).
- **Verify:** Selection changes produce zero base-geometry invalidation.

### Phase 6 — Benchmark and V1 Comparison (Week 3–4)

- Run identical scenarios against V1.
- Measure camera, vertex drag, hover, topology on reference mesh.
- Record and document all metrics.
- Validate against acceptance criteria.

**Total estimated effort:** 4 weeks for core implementation + testing + documentation.

---

## 10. Core ↔ Viewport Contract

### Pre-Implementation Questions for Core Review

Before implementation, clarify:

1. **Position change notification:** Does Core provide position revision numbers or modified-vertex sets? Or does viewport poll for changes?
2. **Topology change notification:** Does Core signal topology_revision changes?
3. **Adjacency availability:** Should Core provide `vertex_to_faces` or should viewport compute it from topology?
4. **Existing APIs:** Are there existing change-notification patterns already in Core that viewport should leverage rather than building new ones?

**Decision:** Do not modify Core to satisfy viewport; instead, adapt viewport to use existing Core APIs.

---

## 11. Explicit Scope Boundaries

### Inside Viewport v0.2 Scope

- Persistent GPU geometry management
- Dirty-state tracking and update dispatch
- Local normal computation and patching
- CPU picking (linear scan)
- Overlay rendering (hover/selection)
- Camera and view/projection management
- Performance measurement and benchmarking

### Outside Viewport v0.2 Scope (may be future work)

- WP-02 / WP-03 / Core topology and mesh structure (leave untouched)
- Advanced picking acceleration (BVH, Octree, GPU ID-buffer) — defer unless benchmarks demand
- General rendering engine or abstraction layers
- ECS, Render Graph, custom resource manager
- GPU compute pipeline
- Multithreaded rendering
- Support for meshes > 100k vertices (scale and measure first)

### Interaction with Other Systems

**Core (WP-02):** Viewport reads Core topology and positions; calls Core APIs for moves/operations. Core is authoritative; viewport is read-only consumer (during interaction state queries).

**Existing V1 Viewport:** Run in parallel during development; use as functional and performance reference. Do not modify V1; build v0.2 in `src/viewport/` and prove v0.2 can replace V1.

---

## 12. Unresolved Decisions (to be settled during implementation)

| Question | Impact | Decided By |
|----------|--------|-----------|
| **Normal definition:** Face-average or per-vertex smooth? | Affects adjacent-vertex set for updates | Implement both; measure visual quality and performance; choose based on reference visual |
| **Bounds strategy:** Recompute every position update, or only when position exits old AABB? | Affects perceived latency | Benchmark both strategies; choose simpler unless measurement shows clear win for complex version |
| **Sparse normal patching:** Upload each affected vertex range separately, or always upload full buffer? | Affects GPU bandwidth usage | For reference mesh (326V), full buffer is ~13 KB; likely cheaper than multiple small uploads. Benchmark on low-end hardware. |
| **Selection rendering:** Separate overlay mesh (Option A) or material layer (Option B)? | Affects code structure and rendering complexity | Implement Option A first (simpler). Option B if profiling shows overhead. |
| **Interleaving:** Can multiple update categories apply in one frame (e.g., camera + selection + position)? | Affects dirty-state model complexity | Assume yes; design state model to handle concurrent dirty flags; test with stress scenarios. |
| **Core change semantics:** Exact API for position_revision and modified_vertices? | Affects viewport implementation | Inspect Core during Phase 1; adapt viewport to real API rather than assumed API. |

---

## 13. Testing and Validation Strategy

### Unit Tests

- `test_render_mesh_allocation()` — VertexLists allocated once, not recreated on update
- `test_vertex_to_faces()` — adjacency structure correct
- `test_affected_normals()` — only relevant normals recomputed
- `test_position_patch()` — buffer content updated correctly
- `test_bounds_recalculation()` — AABB correct after vertex move

### Integration Tests

- `test_camera_no_rebuild()` — camera move → zero geometry uploads
- `test_position_update()` — single vertex move → one position upload, affected normal updates
- `test_topology_rebuild()` — edge split → structural rebuild, all data correct
- `test_overlay_independence()` — selection change → base geometry untouched
- `test_interleaving()` — camera + position + selection in one frame → all work correctly

### Benchmark Tests

- `benchmark_camera_orbit()` — compare v0.2 vs. V1 average/95th percentile
- `benchmark_vertex_drag()` — compare v0.2 vs. V1 average/95th percentile
- `benchmark_hover()` — compare v0.2 vs. V1 picker overhead
- `benchmark_large_mesh()` — scaling test with progressively larger meshes
- `stress_test_1000_moves()` — memory stability, no leaks

### Measurement Checklist

Before claiming v0.2 ready:
- [ ] All counter metrics validated (geometry_uploads, rebuilds, etc.)
- [ ] GPU resource IDs stable across non-topology interactions
- [ ] Memory resident stable (no leaks after 1000 operations)
- [ ] Visual output matches V1 reference on all scenarios
- [ ] Benchmark data collected (average, 95th percentile, peak)
- [ ] Low-end hardware tested (reference old developer PC)
- [ ] Topology operations verified correct (edges, faces updated)

---

## 14. Known Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Bounds caching gone stale** | Frustum culling misses visible geometry or includes culled geometry | Validate bounds after each position update; unit test bounds correctness |
| **Normal discontinuity at update boundary** | Lighting artifacts if affected-vertex range is too narrow | Test with reference mesh; visual inspection; adjust neighborhood if needed |
| **Picker slow on large meshes** | Interaction latency spike on bigger models | Benchmark on progressively larger meshes; defer acceleration until needed |
| **Interleaving state corruption** | Dirty flags get out of sync if multiple updates in one frame | Design state model as set of independent flags, not ordered; test stress scenarios |
| **GPU stall from buffer patches** | Latency spike if buffer is currently in-use by GPU | Avoid patching actively-rendered buffer; use double-buffering if needed (implement only if measurement shows problem) |
| **Core API assumptions wrong** | Viewport code breaks if Core change API differs | Inspect Core early (Phase 1); validate assumptions before heavy implementation |

---

## 15. Acceptance Criteria

### Functional

- [ ] Camera moves do not trigger geometry rebuild.
- [ ] Vertex position updates patch geometry without recreating buffers.
- [ ] Selection changes do not invalidate base mesh.
- [ ] Topology changes trigger rebuild and complete correctly.
- [ ] Picker works for vertex/edge/face selection.
- [ ] Visual output matches V1 reference on all test scenarios.

### Performance (Measured on Reference Mesh, 326V)

- [ ] Camera event time < 2 ms (was ~85 ms in V1).
- [ ] Vertex drag event time < 10 ms (was ~100 ms in V1).
- [ ] Hover event time < 5 ms (was ~12 ms in V1).
- [ ] No performance regression on topology operations.
- [ ] Low-end hardware can maintain interactive rates (target: 30+ FPS on 7-year-old PC).

### Resource

- [ ] GPU resources persist across non-topology operations.
- [ ] No memory leaks after 1000+ operations.
- [ ] Allocation-light interaction path.

### Documentation

- [ ] Architecture decisions documented in this file.
- [ ] Dirty-state model documented.
- [ ] Performance measurements recorded.
- [ ] Test results and benchmark data attached.

---

## 16. Future Work (LATER, not v0.2)

- GPU ID-buffer picking (if linear scanning becomes bottleneck)
- CPU spatial grid for picking (if candidate count grows)
- Double-buffering for GPU stall avoidance (if stalls measured)
- Compute shader normal calculation (if normal recomputation becomes bottleneck on large meshes)
- LOD or fast-navigate system (if performance ceiling hit)
- Multithreaded derived-data computation (if available CPU cores go unused)
- Support for meshes > 100k vertices (scale and re-measure at that point)

---

## 17. Summary

The v0.2 architecture is built on a single principle:

> **Update what changed — and nothing else.**

This specification translates that principle into concrete components, contracts, and measurements. It is:

1. **Minimal** — no unnecessary abstractions.
2. **Measurable** — every claim is testable and must be benchmarked.
3. **Verified** — based on V1 profiling evidence, not speculation.
4. **Bounded** — explicit scope prevents feature creep and overengineering.
5. **Production-ready** — implementation sequence is clear; risks are identified.

The next step is implementation review and approval. After that, development can proceed with high confidence in the architecture's suitability.

---

## Appendix A: Counter Definitions

For measurement and validation, these counters must be tracked:

```python
counters = {
    'geometry_uploads': 0,         # count of GPU buffer writes
    'structural_rebuilds': 0,       # count of topology rebuilds
    'normal_recomputations': 0,    # count of normal update calls
    'bounds_recalculations': 0,    # count of AABB invalidations
    'gpu_resource_creations': 0,    # count of VertexList allocations
    'gpu_resource_destroys': 0,     # count of VertexList deletions
    'camera_updates': 0,            # count of camera matrix changes
    'position_updates': 0,          # count of position patch calls
    'selection_updates': 0,         # count of hover/selection changes
    'picking_calls': 0,             # count of picker invocations
    'bytes_uploaded': 0,            # total GPU data transferred (detect amplification)
    'peak_memory_resident': 0,      # max VRAM in use
}
```

---

## Appendix B: Test Mesh Specifications

### Reference Mesh

- Path: `experiments/rigging-skinning-morphing/meshes/head_basemesh.obj`
- Vertices: 326
- Faces: 324 (100% quads)
- Manifold: Yes
- Purpose: V1 baseline; primary benchmark target for v0.2

### Scaling Test Meshes (future)

- Small: 50V (cube with subdivisions)
- Medium: 1–2k V (head with more detail)
- Large: 10–50k V (complex sculpt)
- XLarge: 100k+ V (defer to later phase)

---

## Appendix C: Change Log

| Date | Change | Rationale |
|------|--------|-----------|
| 2026-09-04 | Initial spec created | Derives from VIEWPORT_V02_RESEARCH.md + Adversarial Review |
| — | — | — |

---

**End of Specification**

This document is the authoritative architectural contract for Viewport v0.2 production implementation. Implementation should proceed only after explicit approval.
