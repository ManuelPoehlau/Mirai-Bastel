# Viewport Draw Binding Spike

> Type B — Research Package. See the handoff document for full scope,
> acceptance criteria and known pitfalls. Results here feed
> [`docs/architecture/AD-018-PRODUCTION-DRAW-BINDING.md`](../../docs/architecture/AD-018-PRODUCTION-DRAW-BINDING.md) (drafted here as PROPOSED, decided 2026-09-25) and, per
> AGENTS.md §5/M5, do NOT themselves change any architecture decision.

## Question (H1)

> RenderMesh's named resources (`positions`, `normals`, `indices`,
> `highlight_flags`, `camera_uniforms`) can be drawn as one indexed,
> multi-attribute pyglet VertexList plus program uniforms — by supplying
> a `ResourceStore` implementation only, **without changing
> `src/viewport/`** — while the V02 invariants hold on real GL.

## Result: **H1 CONFIRMED**

`SpikeGLStore` (`spike_gl_store.py`) implements the `ResourceStore` ABC
from `src/viewport/resource_store.py` unmodified — no changes anywhere
under `src/`. It drives one real `ShaderProgram.vertex_list_indexed(...)`
per `RenderMesh` instance, with `positions`/`normals`/`highlight_flags` as
vertex attributes and a real integer index buffer, and treats
`camera_uniforms`/`material_uniforms` as pure CPU-side uniform storage
(never touching the VertexList).

All test scenarios in §7 of the handoff pass (`tests/`, 12/12, run via
`xvfb-run -a python3 -m pytest experiments/viewport_draw_binding_spike/tests`),
the head mesh renders visibly shaded through RenderMesh data only
(`run.py`, manually smoke-tested under Xvfb — see "How this was verified"
below), and the four measurement scenarios in §8 ran against the real
326V head mesh with real GL (`run_bench.py --headless`).

## Setup

- `spike_gl_store.py` — the `ResourceStore` implementation (see its module
  docstring for the mechanism in detail).
- `shaders.py` — minimal GLSL: `position`/`normal`/`highlight_flag`
  attributes, one directional light, no material uniform.
- `drawing.py` — the actual draw call (`draw_frame`), shared by `run.py`,
  `run_bench.py` and the pixel smoke test, so the tests exercise exactly
  what the window draws (see "Why not a parallel path" below).
- `run.py` — throwaway window. Loads the head mesh, binds the Production
  `OrbitCamera`, orbits via mouse drag, debug keys `M` (move 5 vertices),
  `E` (split one edge), `R` (reset), `Esc`/`Q` (quit).
- `run_bench.py` — the four §8 scenarios against the real head mesh;
  `--headless` for Xvfb/EGL, run without a flag for a visible window.
- `tests/` — the §7 test suite (see below).

## The mechanism (how H1 is satisfied)

`RenderMesh._rebuild_resources()` calls `allocate()`/`update()` **once per
named resource, in isolation** — the `ResourceStore` contract has no
concept of "these resources together form one GPU object". A single
indexed `VertexList`, however, needs `positions` + `normals` + `indices`
all at once to be constructed (pyglet 2.x: attributes are declared at
`vertex_list_indexed()` call time, not added afterward).

`SpikeGLStore` resolves this by **deferring** the actual VertexList
construction until all three ("the structural trio") have each received a
fresh `allocate()` + `update()` call within the same rebuild cycle, then
building the VertexList once. `highlight_flags` is treated as an
always-optional, deferred attachment: the VertexList is built with a
zero-filled `highlight_flag` if it hasn't arrived yet, and patched in
place the moment it does (before or after the trio, either order works).

This relies on the **empirically observed call order** in
`RenderMesh._rebuild_resources()` (positions, normals, indices, then
optional highlight_flags/material_uniforms/camera_uniforms) — nothing in
the `ResourceStore` ABC itself guarantees that order or even that these
calls happen close together in time. See "Friction points" below and
AD-018 Option B for the alternative (extend the contract with an explicit
attribute-group / uniform category rather than inferring it from
observed call order).

Everything else follows directly from the invariants already encoded in
`RenderMesh`/`ResourceStore`:

- **Camera** (`camera_uniforms`) is pure CPU storage, applied at draw time
  via a program uniform. It never touches the VertexList — verified live
  (`test_persistence.py::test_camera_orbit_does_not_touch_vertex_list_or_ids`,
  and `run_bench.py`'s orbit scenario: `geometry_uploads (delta) = 0`).
- **Selection** (`highlight_flags`) patches only the `highlight_flag`
  attribute slice in place — `positions`/`normals` resource IDs and the
  VertexList object are untouched
  (`test_persistence.py::test_selection_change_does_not_touch_base_mesh_ids`).
- **Position updates** patch `position`/`normal` attribute slices in
  place, same object identity, same resource IDs
  (`test_persistence.py::test_single_vertex_move_is_same_object_and_id`).
- **Topology** (edge split) destroys the old combined VertexList and
  builds a new one; every named resource's `resource_id` changes
  (`test_topology.py`).

## How this was verified

- **Tests** (`tests/`, all real-GL, run via `xvfb-run -a pytest`):
  - `test_store_contract.py` — allocate/update/destroy counters match
    `TraceStore` for identical `RenderMesh` call sequences.
  - `test_content_equality.py` — GL buffer readback == `TraceStore`
    content, for four scenarios (initial/geometry/selection/topology), on
    two independently-driven cube meshes.
  - `test_persistence.py` — camera/selection/position updates keep the
    same VertexList object and resource IDs.
  - `test_topology.py` — edge split gives new resource IDs, correct
    index count, no stale attribute data.
  - `test_pixel_smoke.py` — framebuffer readback is non-empty and changes
    after a vertex move.
- **`run.py` manual smoke test** (see the session transcript, not
  committed): instantiated the window, drove `on_draw()`, `_move_vertices()`,
  `_split_edge()`, mouse-drag-equivalent orbit, and `on_resize()`
  end-to-end against the real 326V head mesh under Xvfb — no exceptions,
  vertex count went 326 → 327 after the split, VertexList rebuilt.
- **`run_bench.py --headless`** — the four §8 scenarios, real GL, real
  head mesh (see "Measurements" below).

**Not done:** a real, on-screen visual inspection by a human (no display
available in this environment). The pixel smoke test proves *a* silhouette
renders and changes with mesh edits, not that the shading/lighting looks
correct to an eye. Flagged as a limit, not swept under the rug.

## Measurements (sandbox — NOT representative, see handoff §8)

326V/324Q head mesh, `SpikeGLStore`, headless Xvfb + Mesa llvmpipe
(software rasterizer — no `/dev/dri` in this sandbox). Full output is
reproducible via `xvfb-run -a python3 run_bench.py --headless`; one run's
numbers:

| Scenario | avg | p95 | max | Notes |
|---|---|---|---|---|
| Orbit, 100 frames | 0.86 ms | 0.98 ms | 11.4 ms | `geometry_uploads` delta = 0 |
| Single-vertex move, 100× | 1.69 ms | 2.26 ms | 5.7 ms | 12 `partial_updates`/event (1 position + ~5 affected-vertex normals in the moved vertex's 1-ring, on the head mesh) |
| Multi-vertex move (50 verts), 50× | 7.00 ms | 10.70 ms | 11.7 ms | one `store.update()` call per moved vertex — see below |
| Edge split, 10× | 4.52 ms | 5.50 ms | 5.50 ms | 6 `structural_rebuilds`/split (all 4 named resources + 2 extra from adjacent recompute) |

`python run_bench.py` (no `--headless`) is available for Manu's PC. That
run is optional and is **not** an Artist verdict.

**Explicit non-claim:** these numbers are software-rasterizer, single-run,
sandbox timings. They say nothing about the "old Windows 10 PC" target
(Known Constraints §6) — that machine has a real GPU driver, which this
environment does not.

### Note on multi-vertex move (Spec §12 open question)

`RenderMesh._sync_geometry()` issues one `store.update("positions", ...)`
and one `store.update("normals", ...)` call *per modified vertex* — never
a single batched upload for a moved-vertex set. `SpikeGLStore`'s in-place
patch path (`vlist.<attr>[offset:offset+3] = data`) does one Python-level
slice assignment per call, so a 50-vertex move issues ~100+ small slice
writes instead of one contiguous one. This is a `RenderMesh`-level
question (VIEWPORT_V02_ARCHITECTURE.md §12, "Sparse normal patching"),
not something this store can or should paper over — noted here as
observed cost, not fixed.

## Observations vs. interpretation

**Observations** (what the tests/measurements directly show):
- A `ResourceStore` subclass, with no `src/viewport/` changes, can drive
  one real indexed multi-attribute VertexList from `RenderMesh`'s actual
  call sequence.
- The V02 architecture invariants (camera → 0 geometry uploads; selection
  → base mesh untouched; position → same object/IDs; topology → new IDs)
  all hold with a real GL backend on the reference head mesh, not just in
  `TraceStore`'s in-memory simulation.
- The store's correctness depends on an *inferred* call-order guarantee
  (positions, normals, indices, then optional attachments) that the
  `ResourceStore` ABC does not itself state or enforce.

**Interpretation** (not established by the above, left to the AD):
- Whether that inferred-order reliance is an acceptable permanent design
  (Option A, this spike) or should be replaced by an explicit contract
  extension (Option B) or a separate GL mirror (Option C) is an open
  architecture question — see AD-018.
- Whether the per-vertex `update()` cost (multi-vertex move scenario) is a
  real bottleneck on the actual target hardware is unmeasured here (no
  representative hardware available) and not claimed either way.

## Limits

- Sandbox: software GL (Mesa llvmpipe via Xvfb), no `/dev/dri`. Timings
  are not representative of the "old Windows 10 PC" target (handoff §6).
- No human visual inspection (no display attached to this session).
- Only `positions`/`normals`/`highlight_flags`/`camera_uniforms` were
  exercised; `material_uniforms` is implemented generically (any
  non-vertex-group name is treated as a uniform) but never exercised by
  `run.py`/`run_bench.py`, since no material system is in scope (handoff
  §5).
- Fan-triangulation and face-average normals are inherited as-is from
  `RenderMesh`/`DerivedGeometry` — not re-examined here (Q5, out of
  scope).

## Mesh path discrepancy (M1 note)

The handoff (and `VIEWPORT_V02_ARCHITECTURE.md` Appendix B) name
`experiments/rigging-skinning-morphing/meshes/head_basemesh.obj` as the
326V reference mesh. That path does not exist in this repository; the
same mesh (326V/324Q, confirmed by vertex count) is at
`examples/meshes/head_basemesh.obj`, which is what `run.py`/`run_bench.py`
actually load. Per AGENTS.md §9 ("repository reality has priority"),
this is reported as a stale path in existing docs, not silently
special-cased — worth a doc fix wherever else that path is written down,
outside this spike's scope to change.

## Open questions carried, not resolved (§10 of the handoff)

Not decided here — see the handoff for full framing:

- **Q2** (flat shading / indexed vs. expanded layout): not investigated;
  the spike shader is smooth-shaded only.
- **Q3** (edge/point data ownership): not investigated; no edge/point
  draw path was built.
- **Q4** (overlay representation): the existing highlight-flag-in-base-
  buffer approach (already RenderMesh's own design, §7.1 of the Gate 5
  report) was reused as-is; no separate overlay geometry was tried.
- **Q5** (triangulation/normal definition under symmetry): unchanged,
  inherited from `DerivedGeometry`.
- **Q6** (entry-point location, `init_scene` store parameter): `run.py`
  is throwaway; where a real entry point would live is not decided here.
- **Q7** (who calls `on_vertices_moved`/`on_topology_changed` after tool
  ops): `run.py`'s debug keys call them directly and synchronously; no
  tool/command wiring was built (out of scope, handoff §5).

## Files changed outside this directory

None. `git status`/`git diff` confirm no changes under `src/`,
`playground/`, or any other `experiments/` directory.
