# Mirai-Bastel Viewport v0.2 — Research & Decision Record

**Status:** Research baseline — not the final v0.2 architecture specification  
**Scope:** Viewport V1 performance investigation and preparation for Viewport v0.2  
**Repository:** `ManuelPoehlau/Mirai-Bastel`

> This document records the technical knowledge, measurements, research findings, rejected approaches, and current architectural direction established during the Viewport V1 performance investigation. It intentionally does **not** constitute the final implementation specification for Viewport v0.2. That specification will be derived from this record and reviewed separately before implementation.

---

## 1. Why v0.2 exists

Viewport V1 was an experimental reference/performance viewport created before the production architecture of Mirai-Bastel had matured. It remains useful as a functional and performance reference, but its update model does not scale.

Mirai-Bastel v0.1 may ship with the existing V1 viewport while the production foundations are assembled. Viewport v0.2 is intended to replace V1 with a proper incremental update architecture rather than merely tuning the existing implementation.

The primary design target is a lightweight polygon/SubD modeling viewport with excellent interaction responsiveness, including on older/low-end hardware.

### Core performance principle

> **Interaction latency and modeling responsiveness are more important than graphical luxury.**

The old development PC is therefore a deliberate minimum-tier viewport benchmark, not merely a temporary limitation.

---

## 2. V1 baseline asset

The primary baseline mesh is the real head basemesh used by the existing All-Tools Playground:

`experiments/rigging-skinning-morphing/meshes/head_basemesh.obj`

Characteristics:

- 326 vertices
- 648 edges
- 324 quad faces
- 100% quads
- closed/manifold

The baseline was integrated in commit:

`dc087838e9e1229bac970e265d7888b1da1ae772`

The V1 performance report is maintained separately in the `perf` area of the experimental viewport.

---

## 3. V1 profiling methodology

The investigation deliberately measured the real application instead of replacing it with a synthetic renderer.

Environment:

- Python 3.12.10
- pyglet 2.1.16
- Mirai-Bastel core
- real pyglet window
- VSync disabled for measurement
- 200 events per scenario
- instrumentation added only through monkey-patching on window instances
- no changes to `viewport/*.py`, Core, or Topology were made for the initial profiling
- microbenchmarks were written to mirror the exact application routines headlessly

The purpose was to identify the actual bottleneck before changing architecture.

---

## 4. V1 measured performance

Average frame/event timings on the 324-quad head mesh:

| Scenario | Average time | Approx. CPU-side FPS |
|---|---:|---:|
| Idle | 0.32 ms | ~3100 FPS |
| Orbit | 85.71 ms | ~11.7 FPS |
| Pan | 85.03 ms | ~11.8 FPS |
| Zoom | 117.22 ms | ~8.5 FPS |
| Hover over mesh | 12.78 ms | ~78 FPS |
| Hover-still | 7.47 ms | ~134 FPS |
| Vertex Drag | 100.67 ms | ~9.9 FPS |
| Edge Drag | 72.06 ms | ~13.9 FPS |
| Face Drag | 67.09 ms | ~14.9 FPS |

These numbers are important because the mesh is still very small. A viewport requiring roughly 70–120 ms of work for interaction on a 324-quad mesh has a structural update problem rather than a rendering-capacity problem.

---

## 5. V1 component breakdown

### Orbit

- `rebuild.geometry`: ~74.7 ms (87%)
- normals: ~52.6 ms (61%)
- picking: ~8.0 ms
- GL VertexList work: ~4.8 ms
- `on_draw`: ~3.0 ms

### Pan

- rebuild: ~71.6 ms (84%)
- normals: ~53.0 ms (62%)
- picking: ~7.5 ms
- GL: ~4.5 ms
- draw: ~5.8 ms

### Zoom

- rebuild: ~100.8 ms (86%)
- normals: ~59.1 ms (50%)
- picking: ~10.4 ms
- GL: ~8.9 ms
- draw: ~5.9 ms

### Hover-Move

- rebuild: ~57.0 ms, only on hover changes (19 of 200 events)
- normals: ~49.4 ms
- picking: ~6.7 ms on every relevant event
- GL: ~1.2 ms
- draw: ~0.7 ms

### Vertex Drag

- rebuild: ~95.6 ms (95%)
- normals: ~62.4 ms (62%)
- picking: ~6.8 ms
- GL: ~5.8 ms
- draw: ~4.5 ms

### Edge Drag

- rebuild: ~69.9 ms (97%)
- normals: ~57.2 ms (79%)
- picking: ~21.8 ms
- GL: ~1.9 ms
- draw: ~1.7 ms

### Face Drag

- rebuild: ~65.0 ms (97%)
- normals: ~53.9 ms (80%)
- picking: ~2.1 ms
- GL: ~1.7 ms
- draw: ~1.7 ms

---

## 6. The actual V1 root cause

The dominant V1 update path is effectively:

```text
mouse/event
    -> picking
    -> geometry rebuild
       -> recompute normals globally
       -> flatten render geometry
       -> create/upload new GPU resources
    -> draw
```

The fundamental issue is **not raw OpenGL rendering speed**.

The fundamental issue is the update model:

> **Every interaction event is treated as if the complete mesh render representation had changed.**

The target for v0.2 is therefore not a new renderer. It is a new update mechanism.

---

## 7. cProfile evidence

A mixed orbit + hover + vertex-drag profile took approximately 25.6 seconds.

The dominant functions were:

1. `app.py:_compute_normals`
   - ~10.0 s tottime
   - ~19.5 s cumulative
   - ~76% of cumulative profile time
   - called from `_rebuild_geometry()` for every event
   - uses `mesh.py:face_vertices()` internally
   - effectively O(V×F)
   - approximately 14.88 million calls in the profile
   - `face_vertices()` alone accounted for ~8.7 s

2. `app.py:_rebuild_geometry`
   - ~0.3 s own time
   - ~22.8 s cumulative
   - ~89% cumulative

3. `picking.py:pick_nearest_vertex`
   - ~2.54 s cumulative
   - ~10%

4. `camera.py:project_to_screen`, together with `basis`/`eye`
   - ~3.7 s cumulative
   - primarily from picking/screen-delta calculations

5. pyglet shader/vertexdomain/vertexbuffer paths
   - ~2.4 s cumulative
   - approximately ~9%
   - caused by repeatedly creating VertexLists/VBOs

6. `app.py:_face_triangle_arrays`
   - ~0.91 s cumulative
   - approximately ~4%

### Allocation observations

- `mesh.py:vertex_position`: ~0.64 million calls
- `list.extend`: ~0.73 million calls
- more than 200 KiB peak allocation per rebuild on the head mesh
- GC activity was small: roughly 0–10 generation-0 collections per 200-frame scenario and practically no generation-1/2 collections

**Conclusion:** garbage collection is not the significant bottleneck. Repeated derived-data computation and rebuilding are.

---

## 8. Headless rebuild breakdown

An application-corrected headless benchmark showed approximately:

- `_compute_normals`: ~45.4 ms, ~96% of rebuild CPU time
- `_face_triangle_arrays`: ~1.4 ms, ~3%
- position/edge flattening: ~0.5 ms, ~1%
- pyglet `program.vertex_list` creation/upload: roughly ~4.5 ms per entry in window measurements
- total `_rebuild_geometry` CPU: approximately ~47 ms

This confirms that simply optimizing OpenGL drawing would not solve V1's primary problem.

---

## 9. Picking baseline

The current picker performs linear scans:

- `pick_nearest_vertex`: O(V), projecting all vertices; ~6.9 ms in headless measurement
- `pick_nearest_edge`: O(E), point-to-segment distance for all edges; ~23 ms
- `pick_face`: O(F), ray-triangle tests; ~2.1 ms

Picking is therefore a meaningful secondary hotspot, especially for edge picking, but it is still secondary to the global normal/rebuild path at current mesh sizes.

The important architectural observation is that picking should not force a geometry rebuild merely because the mouse moved.

---

## 10. Scaling evidence

Headless CPU rebuild scaling demonstrated the structural problem:

| Quad faces | Normal calculation | Triangle arrays | Total rebuild |
|---:|---:|---:|---:|
| 324 | ~45.4 ms | ~1.4 ms | ~47.0 ms |
| 1,296 | ~736.8 ms | ~7.7 ms | ~770.2 ms |
| 4,970 | ~21,217 ms | ~32.3 ms | ~22,371 ms |
| 20,022 | ~314,481 ms | ~130 ms extrapolated | ~314,600 ms |

Real-window measurements reinforced the result:

| Quad faces | Orbit frame | Approx. FPS | Rebuild/event |
|---:|---:|---:|---:|
| 324 | 62.6 ms | ~16 | ~55–57 ms |
| 1,296 | 1,211.5 ms | ~0.8 | ~1,134–1,226 ms |
| 4,970 | 12,818.7 ms | ~0.1 | ~12,710–17,594 ms |
| 20,022 | not usable interactively | — | ~314,600 ms CPU |

Hover frame measurements include picking and therefore should not be directly interpreted as rebuild-only timing.

### Scaling conclusion

The V1 normal calculation is effectively O(V×F), and this dominates long before the GPU becomes a limitation.

---

## 11. Research of existing systems

Several open-source systems were examined as architectural references. The goal was not to reproduce them, but to identify principles that apply to a small modeling viewport.

### Blender

Relevant lessons:

- viewport drawing has dedicated GPU/render infrastructure rather than treating viewport rendering as ordinary UI drawing
- render-side state and GPU resources can persist across frames
- overlays are conceptually separate from the base scene geometry
- cached/derived data is reused rather than regenerated for every interaction event

Blender is a strong architectural reference, but its complete draw-manager architecture is far beyond what Mirai-Bastel needs for v0.2.

### Wings 3D

Wings is particularly relevant because it is an open-source polygon/subdivision modeler inspired by Nendo and Mirai.

Research of the source identified dedicated picking and bounding-volume related modules, including `wings_pick*` and `e3d_bvh`.

The important lesson for Mirai is that a CPU-oriented picking strategy is entirely viable for a modeling-focused application. There is no requirement to introduce GPU ID-buffer picking merely because the application has an OpenGL viewport.

### MeshLab

MeshLab was examined as a reference for handling larger/unstructured meshes and separating rendering state from mesh-processing concerns. Its render-state structures reinforce the idea that render-side representations should persist independently of the underlying mesh-processing algorithms.

### FreeCAD

FreeCAD uses Coin3D/Open Inventor's retained-mode scene graph and ViewProvider layer. This demonstrates the broader principle of maintaining a persistent view representation and keeping temporary selection/manipulator helpers separate from the core geometry representation.

### SculptGL

SculptGL was considered as a lightweight WebGL viewport/sculpting reference. Its development is stopped, but its simple architecture remains useful as a conceptual reference for an interactive mesh viewport.

### Open3D / Godot

These systems demonstrate stronger renderer abstractions and scene/render separation. They are useful as references for general rendering architecture, but their scale and requirements exceed the current needs of Mirai-Bastel.

### Proprietary references

Blender-like ideas were also compared conceptually with 3ds Max, Maya, Modo, Houdini, Cinema 4D, Silo, and ZBrush. These systems are useful UX/performance references, but their internal implementations are not sufficiently transparent to serve as primary architectural evidence for this project.

---

## 12. First architectural direction from research

The first research pass suggested a more elaborate architecture containing:

- Viewport Engine
- State/Camera
- Render Scene Cache
- GPU Resource Manager
- Overlay/UI pass
- Picking system
- multiple revisions
- CPU/GPU hybrid picking
- possible spatial acceleration structures

Critical review showed that this was directionally correct but unnecessarily large for Mirai-Bastel v0.2.

The project should **not** become "Blender in miniature".

The central architectural shift is much smaller:

> **from `event → rebuild everything` to `state + dependencies + incremental update`.**

---

## 13. Second research/review pass

A second critical review specifically investigated:

- CPU vs GPU picking
- derived geometry and normal locality
- adjacency requirements
- pyglet 2.x persistent GPU resources
- revision/dirty-state alternatives
- low-end performance targets
- possible overengineering

The resulting direction was deliberately reduced.

### Strong conclusions

- Camera and mesh geometry must be independent.
- Base mesh GPU resources should persist during normal interaction.
- Selection/hover should not invalidate base geometry.
- Position changes should update only affected derived data.
- Topology changes are the natural boundary for a larger render-data rebuild.
- A minimal vertex-to-face adjacency structure is sufficient to begin local normal updates.
- CPU picking is the appropriate starting point.
- BVH/Octree/KD-tree and GPU ID picking should not be introduced without measured need.
- A custom GPU Resource Manager is unnecessary if pyglet's native resource abstractions are sufficient.
- NumPy should not be mandatory for the small-mesh interaction path.

### Explicitly rejected overengineering

For v0.2, there is currently no justification for:

- GPU ID-buffer picking
- `glReadPixels`-based hover picking
- BVH/Octree/KD-tree solely for picking
- compute-shader normal generation
- a complete dependency graph
- ECS
- render graph
- GPU-driven renderer
- custom general GPU resource-management framework
- Vulkan
- multithreaded rendering
- automatic LOD/Fast Navigation

These may become relevant in a later, benchmark-driven phase, but they are not part of the current minimum architecture.

---

## 14. Current conceptual v0.2 model

The current research direction is intentionally small:

```text
                    Core Mesh
                        │
                        │ geometry changes
                        ▼
                  ┌─────────────┐
                  │  RenderMesh │
                  │             │
                  │ positions   │
                  │ normals     │
                  │ indices     │
                  │ adjacency   │
                  │ dirty state │
                  └──────┬──────┘
                         │
                         ▼
                 persistent pyglet
                    VertexList

       Camera ────────────────→ matrices/uniforms

       Picking ───────────────→ hover/selection state

       Overlay ───────────────→ hover/selection visuals
```

This is a **conceptual research result**, not yet the final API/class specification.

A useful mental model is:

> **Mirai v0.2 is not a new renderer. It is a new update mechanism for the viewport.**

---

## 15. Current update-flow hypothesis

### Camera

```text
Camera change
    → update matrices/uniforms
    → redraw
```

No mesh geometry rebuild should occur.

Picking should only be performed when interaction semantics actually require it.

### Hover

```text
Mouse move
    → CPU picker
    → hover changed?
        → update overlay/hover state
    → redraw
```

If the hover target has not changed, no render-mesh work is required.

### Selection

```text
Selection change
    → update selection overlay
    → redraw
```

Base mesh geometry remains untouched.

### Vertex drag

```text
Core position change
    → identify modified vertices
    → resolve affected faces
    → recompute affected derived normals
    → patch persistent GPU buffers
    → redraw
```

No complete render-geometry rebuild should be necessary.

### Topology change

```text
Topology change
    → rebuild render-derived data
    → rebuild adjacency
    → rebuild persistent GPU geometry
    → rebuild picking-related data if required
    → redraw
```

Topology changes are the expected place for larger allocations and rebuild work.

---

## 16. Derived geometry research

The current minimum useful adjacency candidate is:

```text
vertex_id → incident face IDs
```

This permits a changed vertex to identify the directly affected faces without scanning the entire mesh.

For a position change of vertex `V`, the directly affected face normals are the faces incident to `V`.

Vertex-normal invalidation is more subtle and depends on the normal definition. A simple averaged normal may be updated from the affected faces and their incident vertices, but the architecture must not hard-code an overly narrow rule such as an unconditional "2-ring" assumption.

The final implementation specification should therefore use the principle:

> **Recompute the minimal affected normal neighborhood required by the active normal definition.**

Potential future normal definitions such as area-weighted, angle-weighted, hard/soft edge aware, or SubD-related normals may change the exact neighborhood.

### Current adjacency scope

**Candidate minimum for v0.2:**

- `vertex_to_faces`

Potential future additions, only if demanded by actual tools or algorithms:

- `edge_to_faces`
- `face_to_vertices`
- `vertex_to_edges`
- richer topology acceleration structures

No full general-purpose dependency graph is currently justified.

---

## 17. Current invalidation model

The following is the current research-level dependency model:

| Change | Face normals | Vertex normals | Triangulation | Adjacency | Render indices | GPU positions |
|---|---|---|---|---|---|---|
| Position | affected local faces | affected local neighborhood | unchanged | unchanged | unchanged | patch |
| Topology | rebuild | rebuild | may rebuild | rebuild | rebuild | rebuild |
| Selection | unchanged | unchanged | unchanged | unchanged | unchanged | unchanged/base mesh |
| Camera | unchanged | unchanged | unchanged | unchanged | unchanged | unchanged |
| Hover | unchanged | unchanged | unchanged | unchanged | unchanged | unchanged/base mesh |

This table is a design aid, not yet a final implementation contract.

---

## 18. Pyglet 2.x direction

The current research direction is to use pyglet 2.x's modern shader/VertexList infrastructure rather than rebuilding GPU resources during interaction.

Relevant API area:

```python
pyglet.graphics.shader.ShaderProgram
```

The working hypothesis is that existing VertexList attributes can be updated through their exposed buffer-backed interfaces, allowing partial position/normal updates without recreating the entire VertexList.

### Important validation note

The exact behavior of pyglet 2.1.16 partial attribute slicing should be treated as an implementation detail to verify with a small executable experiment before it becomes a hard architectural invariant.

The desired model is:

```text
Topology change
    → recreate/repopulate GPU geometry

Position change
    → partial GPU buffer update

Camera change
    → matrix/uniform update only

Selection/hover
    → overlay update only
```

The final architecture specification should name the exact pyglet APIs verified against the version used by Mirai-Bastel.

---

## 19. NumPy decision direction

NumPy is **not** considered mandatory for v0.2.

For small meshes and tiny local updates, ordinary Python data structures can be competitive and avoid unnecessary array conversion/temporary allocation overhead.

The current preferred strategy is:

- keep the interaction path allocation-light
- allow larger allocations during structural/topology rebuilds
- introduce NumPy only where a benchmark demonstrates that bulk array operations provide a meaningful advantage

NumPy may become useful for larger meshes or heavier vectorized derived-data processing, but its presence should not dictate the initial architecture.

---

## 20. Dirty state / revision research

A minimal candidate state model is:

```text
topology_revision
position_revision
modified_vertices
```

The purpose is not to build a general event system. The viewport only needs enough information to determine what derived render data must be synchronized.

A dirty **set/list of changed vertex IDs** is preferable to an event log containing every intermediate position change during a drag. Repeated changes to the same vertex should not require repeated processing of the same identity.

A possible synchronization pattern is:

```text
if core.position_revision != last_position_revision:
    apply_patch(core.modified_vertices)
```

The exact location and API of these revisions must be decided in the final architecture specification after inspecting the current Core change semantics. The Core should not be modified merely to satisfy an imagined rendering architecture if equivalent existing change notifications already exist.

---

## 21. Picking direction

The current recommended starting point is a simple **CPU picker**.

### Candidate methods

- Vertex: screen-space distance
- Edge: screen-space segment distance
- Face: ray/triangle intersection

For the current target of hundreds to a few thousand elements, a linear scan is acceptable as the first implementation, especially because the current V1 bottleneck is elsewhere.

### Later, if benchmarks require it

A simple CPU spatial grid/hash may reduce candidate counts for larger meshes.

### Explicitly not planned for v0.2

- GPU ID-buffer picking
- `glReadPixels` hover readback
- BVH
- Octree
- KD-tree

The rule is:

> **Picking acceleration must earn its place through measurement.**

A spatial grid may become appropriate when the mesh sizes used by Mirai make linear scanning measurably visible, but it is not currently a mandatory architectural component.

---

## 22. Performance targets — current hypotheses

Early discussion proposed approximate interaction targets such as:

- camera interaction: <1–2 ms
- hover: <2–4 ms
- vertex drag: <5 ms
- selection: <5 ms
- small topology rebuild: <15 ms

These should **not yet be treated as guaranteed requirements**.

The final specification should define:

- end-to-end frame time
- CPU-side event/update time
- average
- 95th percentile
- preferably worst-case or maximum observed interaction frame
- mesh sizes/scenarios used for comparison

The key principle is that a performance claim must state exactly what it measures.

For example, "<5 ms vertex drag" is meaningful only if the measurement includes the complete user-visible interaction path rather than only the local normal calculation.

V0.1/V1 and v0.2 should be benchmarked under the same scenarios and hardware wherever possible.

---

## 23. Hard architectural principles emerging from research

The following principles have high confidence and should survive into the final v0.2 specification unless new evidence contradicts them:

1. **Camera changes never invalidate mesh render data.**
2. **Selection changes never invalidate base mesh geometry.**
3. **Normal interaction should not recreate GPU geometry resources unnecessarily.**
4. **Position changes update only affected derived data.**
5. **Topology changes may trigger larger rebuilds.**
6. **Rendering concerns do not belong in the Core mesh/topology layer.**
7. **Acceleration structures are introduced only when profiling demonstrates the need.**
8. **Low-end hardware is a first-class performance target.**
9. **The interaction path should be allocation-light.**
10. **Structural/topology paths may perform larger allocations when necessary.**
11. **The viewport should remain a small modeling-oriented system, not a general-purpose rendering engine.**

---

## 24. Candidate minimal component model

The current minimal conceptual decomposition is:

```text
Viewport v0.2
├── Camera / Window
│   └── pyglet event handling + matrices
│
├── RenderMesh
│   ├── persistent GPU VertexList(s)
│   ├── render positions
│   ├── render normals
│   ├── render indices/triangulation
│   └── minimal adjacency
│
├── CPU Picker
│   └── vertex / edge / face hit testing
│
└── Overlay
    └── hover / selection / later manipulators
```

This is intentionally a small bridge between the existing Core and pyglet. It is **not** intended to become a universal rendering abstraction.

The final architecture may split or rename these components if implementation evidence shows a clearer boundary.

---

## 25. Explicit non-goals for v0.2

The following are currently outside scope unless a new benchmark or requirement provides a concrete reason:

- complete Blender-style Draw Manager
- full dependency graph
- ECS
- render graph
- custom GPU resource manager
- GPU-driven rendering
- GPU compute normal pipeline
- GPU ID picking
- `glReadPixels` selection/hover pipeline
- BVH/Octree/KD-tree picking acceleration
- automatic LOD
- Fast Navigation system
- Vulkan backend
- multithreaded renderer
- large framework-style abstraction layers

This list exists specifically to prevent architecture drift and overengineering.

---

## 26. What remains to be decided

Before implementation, a separate final architecture specification must settle:

1. Exact `RenderMesh` responsibilities and API.
2. Exact Core-to-viewport change/dirty semantics, based on the existing Core rather than assumptions.
3. Exact pyglet 2.1.16 partial-update API and behavior.
4. Exact normal definition for v0.2 and the corresponding minimal affected-normal neighborhood.
5. Whether the first picker remains entirely linear or receives a tiny optimization based on benchmark evidence.
6. Exact overlay representation.
7. Exact benchmark protocol and acceptance thresholds.
8. Exact implementation sequence for Cline.

These are deliberately left open here because this document is a research/decision record, not the final implementation contract.

---

## 27. Recommended implementation strategy after architecture approval

Once the final architecture specification has been reviewed, implementation should be incremental and measurable rather than one large rewrite.

A likely sequence is:

### Phase 1 — Persistent render geometry / camera separation

- introduce the minimal RenderMesh bridge
- create persistent VertexLists
- stop rebuilding mesh geometry for camera interaction
- keep the existing visual behavior as stable as possible

### Phase 2 — Incremental position updates

- connect Core position changes to render updates
- patch GPU positions rather than rebuilding all geometry
- establish modified-vertex handling

### Phase 3 — Incremental derived normals

- build `vertex_to_faces`
- compute only the affected face normals
- update the minimal required vertex-normal neighborhood
- patch normal buffers

### Phase 4 — Picking separation/optimization

- remove unnecessary picker calls from camera-only interactions
- retain simple CPU picking
- benchmark linear scan before considering acceleration

### Phase 5 — Overlay separation

- move hover/selection visuals out of base geometry
- ensure selection changes never invalidate the base mesh

### Phase 6 — Benchmark and regression verification

- compare against V1 under identical scenarios
- record average and 95th percentile frame times
- verify topology operations still rebuild correctly
- test progressively larger meshes

The exact phase breakdown is subject to the final architecture specification.

---

## 28. Summary

The V1 investigation established a clear root cause:

> **Mirai-Bastel V1 performs expensive global derived-geometry work and GPU resource rebuilding in response to interactions that often change only camera state, hover state, selection state, or a small subset of vertex positions.**

The solution does not require a sophisticated renderer.

The current research direction is a small incremental viewport architecture built around:

```text
persistent render data
        +
local derived-data updates
        +
separate camera/picking/overlay state
        +
benchmark-driven acceleration
```

The guiding rule for v0.2 is:

> **Update what changed — and nothing else.**

The next formal artifact should therefore be a reviewed **`VIEWPORT_V02_ARCHITECTURE.md`**, derived from this research record. Only after that specification is accepted should implementation begin.