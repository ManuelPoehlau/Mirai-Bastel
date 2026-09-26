# AD-018 — Production Draw Binding for `RenderMesh`

**Status:** DECIDED ✓ — Option B, additive form (see §5, 2026-09-25). Original draft status: PROPOSED — draft from the draw-binding spike, not a decision.
Per AGENTS.md §5 ("Never silently change architecture") this document
proposes alternatives; it does not select one. Per M5 (Discovery ↔
Production) any new finding here returns to Discovery, it does not
retroactively validate a Production change.

**Basis:** `experiments/viewport_draw_binding_spike/` (H1 CONFIRMED — see
its README). `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` §7 (GPU Resource
Persistence), `src/viewport/resource_store.py` (the `ResourceStore` ABC
and its documented Scope-Grenze).

**Decided by:** Artist (Promotion — M3/M4). This draft does not claim
Artist validation of any option.

---

## 1. Problem

The first Production app needs a real draw path: `RenderMesh`'s named
resources (`positions`, `normals`, `indices`, `highlight_flags`,
`camera_uniforms`) drawn through a real `ShaderProgram`/`VertexList`, not
a parallel VBO (every prior harness — the V02 demonstrator, the
Playground, the Integration Lab — drew through its own VBO alongside or
instead of `RenderMesh`'s own resources).

`RenderMesh._rebuild_resources()` calls `ResourceStore.allocate()`/
`update()` once per named resource, in isolation. A single indexed
`VertexList` needs several of those resources (`positions`, `normals`,
optionally `highlight_flags`) available together to be constructed. The
`ResourceStore` contract, as it stands, has no way to express "these
names are one GPU object" or "these names are uniforms, not buffers".

## 2. Options

### Option A — `ResourceStore` implementation only (what the spike built)

Defer VertexList construction until the "structural trio" (`positions`,
`normals`, `indices`) has each received a fresh `allocate()`+`update()`
call within one rebuild cycle (tracked by the store itself); treat
`highlight_flags` as an always-optional deferred attachment; treat any
other name (`camera_uniforms`, `material_uniforms`, ...) as pure
CPU-side uniform storage.

**Evidence:** `experiments/viewport_draw_binding_spike/spike_gl_store.py`.
12/12 tests pass (`tests/`), head mesh renders and updates correctly
under real GL (`run.py`, `run_bench.py`), all V02 invariants hold
(camera/selection/position/topology).

**Cost:**
- Zero changes to `src/viewport/`.
- The store's correctness relies on an *inferred*, not *contracted*, call
  order (positions → normals → indices → optional attachments). If a
  future `RenderMesh` change reorders these calls, interleaves a topology
  rebuild's trio with another category's update, or adds a resource
  whose group membership isn't inferable this way, the store silently
  builds an inconsistent VertexList (stale attribute lengths) rather than
  failing loudly — this spike's `_trio_data_consistent()` check catches
  the most obvious case (size mismatch) but not a semantically wrong one
  (right sizes, wrong content, e.g. an interleaved partial update landing
  mid-rebuild).
- Every store implementation that wants a combined multi-attribute
  VertexList (not just this one) has to re-derive and re-implement this
  same ordering inference — no shared, tested primitive for it exists in
  `src/viewport/`.
- `material_uniforms` and any future uniform-shaped resource are
  distinguished from vertex-group resources only by name, not by
  anything the contract states — a naming collision (a future vertex
  attribute happening to be named like today's uniform, or vice versa)
  is not something the type system or the ABC would catch.

### Option B — Extend the `ResourceStore` contract

Add an explicit notion of attribute groups and a uniform category to the
contract itself (e.g. `allocate(name, nbytes, group=None, kind="buffer"|"uniform")`,
or a separate `allocate_group(names, ...)` call `RenderMesh` uses instead
of per-name `allocate()` when constructing structurally-linked
resources).

**Evidence:** Not built in this spike (would require changing
`src/viewport/resource_store.py` and `render_mesh.py`, explicitly out of
scope per the handoff's §5 "Not in scope: any change to `src/`"). Purely
a design sketch, not evidence.

**Cost:**
- Touches `src/viewport/` (`resource_store.py` ABC signature, and
  `render_mesh.py`'s `_rebuild_resources`/`put()` call sites) — a
  Production change, not a spike.
- `TraceStore`/`PygletStore` (already-shipped Gate 5 code) would need
  updating to the new signature, or a compatibility shim.
- Removes the ordering-inference fragility named in Option A's cost:
  the store would be *told* which resources form a group, rather than
  guessing from call order.
- Whether this is worth the Production churn for a benefit that (per
  Option A's evidence) is currently only theoretical — no observed
  failure, just a named risk — is exactly the kind of question this
  draft leaves to Promotion, not something the spike can settle.

### Option C — Separate GL mirror reading RenderMesh CPU data + dirty ranges

Instead of implementing `ResourceStore`, build a renderer that reads
`RenderMesh`'s CPU-side derived data directly (positions/normals/bounds/
etc., already computed by `DerivedGeometry`) and its dirty-range
information, maintaining its own GL buffers independently of the
`ResourceStore` abstraction entirely.

**Evidence:** Not built in this spike (would be a materially different
harness, not a `ResourceStore` implementation — the handoff's stated
scope is specifically "by supplying a `ResourceStore` implementation
only").

**Cost:**
- Bypasses the `ResourceStore` abstraction's stated purpose (GPU Resource
  Persistence made "messbar und testbar", per its module docstring) —
  would need its own persistence/counter story from scratch, duplicating
  work `ResourceStore` already does.
- Two parallel paths to derive GL state from the same `RenderMesh`
  (whatever calls `ResourceStore.allocate/update` today, plus this
  mirror) is the exact anti-pattern every prior harness (demonstrator,
  Playground, Lab) fell into and that this spike's stated goal (§3 of the
  handoff: "RenderMesh → pixel has never existed [through one path]")
  was meant to end.
- Might be more robust against `RenderMesh` internal call-order changes
  (Option A's named risk) since it wouldn't infer structure from call
  order at all — but this is speculative, not measured.

## 3. Recommendation

Not made here — Promotion decision, Artist's (per M3/M4). Option A has
the only actual evidence (this spike); Options B/C are cost/benefit
sketches for the Artist and/or a future implementer to weigh against
Option A's one named fragility (inferred call order) versus its actual
measured cost (zero — none of the four test scenarios or the head-mesh
run tripped it).

## 4. Change Log

| Date | Change |
|---|---|
| 2026-09-25 | Initial draft from `experiments/viewport_draw_binding_spike/` |
| 2026-09-25 | Moved to `docs/architecture/`; §5 Decision appended (Option B, additive). §1–§3 left as drafted. |

---

## 5. Decision — 2026-09-25

**Decision: Option B — extend the `ResourceStore` contract, in additive form.**

**Authority:** Manu delegated this explicitly as a technical decision:
choose the option with the greatest long-term value, no interim solution
chosen only because it is faster. The option was selected by the reviewing
agent (Claude, claude.ai Project), which did not author the spike
(separation of generation and evaluation, Development System §6). This is
**not** an Artist verdict on product behavior and claims no Artist
validation of any rendering result.

### Why B

1. **Single source of truth for render layout.** Under Option A the
   knowledge "which named resources form one drawable object, and which
   are uniforms" exists twice: implicitly in `RenderMesh`'s call order and
   explicitly in the store (`VERTEX_ATTR_NAMES`, `STRUCTURAL_TRIO` in
   `spike_gl_store.py`). Every layout change must be made in both places,
   and a mismatch fails silently (§2 Option A, cost 1). B makes
   `RenderMesh` the only place that states the layout; stores implement it.
2. **Known future requirements add resources.** Already-open questions
   each add names or groups: flat shading (Q2), edge/point overlay data
   (Q3), overlay representation (Q4), later per-object meshes (ARCH-01) and
   evaluated geometry from a deformation stack (ROADMAP WP-05+). With A,
   each addition widens the inferred-order fragility; with B, each is one
   declared entry. This follows "Implement little. Assume much." — known
   future goals must not become unnecessarily expensive.
3. **The draw call belongs to the viewport per the spec.**
   `VIEWPORT_V02_ARCHITECTURE.md` §4.2 lists `RenderMesh.render(camera)` —
   "issue draw call" — as part of the RenderMesh contract. Gate 5 deferred
   it as a scoping choice, not an architectural exclusion. A real draw path
   therefore needs the contract to carry drawable structure, not just
   named byte ranges.
4. **C rejected:** a separate GL mirror recreates the parallel draw path
   that every earlier harness used and that this work set out to end
   (§2 Option C). `C wird nicht verwendet, weil` it duplicates the
   persistence/counter machinery and re-splits the render truth.
5. **A rejected as the permanent design:** it works today (spike evidence
   stands and remains the reference for GL mechanics), but its correctness
   rests on an uncontracted call order. `A wird nicht als Dauerlösung
   verwendet, weil` the fragility grows with every known future resource
   (point 2) and the layout would live in two places (point 1).

### Binding constraints for the implementation

- **Additive, not replacing.** The existing per-name `allocate()` /
  `update()` / `destroy()` primitives, `resource_ids()` semantics (one
  stable ID per named resource) and all `BenchmarkCounters` stay valid.
  The new information (layout declaration: attribute groups, index buffer,
  uniform kind; and an explicit rebuild bracket replacing the inferred
  "trio" cycle) is added with defaults, so stores that do not need it are
  unaffected.
- **Existing tests stay green without edits** (Gate 5/7 viewport tests in
  `tests/`). If a test must change, that is a finding to report, not to
  fix silently.
- **Playground stays unchanged** (AD-010 Addendum 2026-09-25).
  `playground/gl_store.py::PlaygroundPygletStore` subclasses `PygletStore`
  and must keep working without edits. If that proves impossible, stop
  and return to Discovery.
- **Not a general GPU resource manager** (spec §1 non-goal stands). The
  layout declaration describes exactly what `RenderMesh` draws — no
  registry, no render graph, no pluggable passes.
- **The spike is reference, not source.** Mechanics proven in
  `experiments/viewport_draw_binding_spike/` (indexed multi-attribute
  VertexList, in-place attribute slices, uniforms at draw time, rebuild on
  topology) inform the Production implementation; its code is not copied
  into `src/` wholesale (Promotion Boundary, M3).

### Deliberately not decided here

- Exact API names and signatures of the layout declaration / rebuild
  bracket.
- Whether the current `PygletStore` (single-attribute persistence probe)
  is kept as-is next to a new drawable GL store or reimplemented — both
  must satisfy the Playground constraint above.
- Batched range updates for multi-vertex moves (spec §12, spike
  measurement "multi-vertex move"). B makes them expressible; whether and
  when to add them is a separate, measured question.
- Q2–Q7 from the spike README (flat shading, edge/point data, overlay
  representation, triangulation under symmetry, entry-point location,
  tool → viewport notification).

---

## 6. Implementation — 2026-09-25

Implementation package per the handoff "AD-018 Option B: `ResourceStore`
Layout Contract + Drawable GL Store". Built the declared contract extension
and one real drawable `ResourceStore` implementation within the binding
constraints (§5). No architecture redecision — this section records what
was built and what was verified, per §5's own instruction to append rather
than edit §1–§5.

### API shipped

`src/viewport/resource_store.py` — `ResourceStore` gained four optional
methods, all with no-op default bodies in the ABC:

```python
def declare_group(self, group: str, attributes: dict[str, tuple[str, int]], index: str) -> None: ...
def declare_uniform(self, name: str) -> None: ...
def begin_rebuild(self, group: str) -> None: ...
def end_rebuild(self, group: str) -> None: ...
```

- `declare_group(group, attributes, index)` — states once that the named
  resources in `attributes` (mapped to `(gl_attribute_name, components)`,
  e.g. `{"positions": ("position", 3)}`) plus the index resource `index`
  form one drawable GPU object. Replaces the spike's inferred
  `STRUCTURAL_TRIO`/`VERTEX_ATTR_NAMES` name-based guessing with an
  explicit statement from `RenderMesh`.
- `declare_uniform(name)` — states a resource name is CPU-side uniform
  storage (`camera_uniforms`, `material_uniforms`), never a group member.
- `begin_rebuild(group)` / `end_rebuild(group)` — an explicit bracket
  around one structural rebuild cycle, replacing the spike's inference
  "all trio members freshly allocated within this cycle" from call order
  alone.

`src/viewport/render_mesh.py` — `RenderMesh.__init__` calls
`declare_group("mesh", MESH_GROUP_ATTRIBUTES, "indices")` and
`declare_uniform("camera_uniforms"/"material_uniforms")` once, and
`_rebuild_resources()` wraps its existing `put()` calls for
`positions`/`normals`/`indices`/`highlight_flags` in
`begin_rebuild("mesh")`/`end_rebuild("mesh")`. Nothing else in
`_rebuild_resources()`, `sync()`, or any `_sync_*` method changed — what is
computed and when `sync()` dispatches is unchanged; only how the store is
told about resource structure is new. `RenderMesh` also gained
`render(camera)` (VIEWPORT_V02_ARCHITECTURE.md §4.2): it does not mutate
dirty state itself, and delegates the actual draw to `store.draw()` via
duck typing — a no-op for stores without a `draw()` (`TraceStore`,
`PygletStore`).

`src/viewport/gl_render_store.py` (new) — `GLRenderStore(ResourceStore)`:
one real `ShaderProgram.vertex_list_indexed(...)` per declared group,
built from buffered `allocate()`/`update()` calls collected between
`begin_rebuild()`/`end_rebuild()`; outside a rebuild bracket, `update()`
patches the existing VertexList's attribute slice in place (GPU Resource
Persistence, §7). `declare_uniform()`-named resources are pure CPU
dictionaries, applied as program uniforms (`u_view`, `u_proj`,
`u_light_dir`, `u_base_color`) at `draw()` time — never touching the
VertexList. Shader: position/normal/highlight_flag attributes, one
directional light, base color driven by `material_uniforms` (3 floats) if
bound, else a default gray (adapted from the spike's `shaders.py`, extended
with the material-uniform-driven base color named in scope §4).

### Test results

Before (baseline, this implementation's starting point):

```
$ python3 -m pytest tests/ -q --ignore=tests/test_extrude_tool.py
546 passed
$ xvfb-run -a python3 -m pytest playground/tests -q
843 passed
```

After:

```
$ python3 -m pytest tests/ -q --ignore=tests/test_extrude_tool.py
560 passed
$ xvfb-run -a python3 -m pytest playground/tests -q
843 passed
$ xvfb-run -a python3 -m pytest tests/ -q --ignore=tests/test_extrude_tool.py -k "resource_store or render_mesh or viewport_facade or camera_gate"
85 passed, 475 deselected
```

560 − 546 = 14 new tests, all headless/GL-optional:

- `tests/test_resource_store.py` — 4 new tests
  (`TraceStoreLayoutDeclarationTests`): `declare_group`/`declare_uniform`/
  `begin_rebuild`/`end_rebuild` are no-ops on `TraceStore` — the empirical
  proof of "additive", not just the claim. A store that never calls them at
  all (pre-AD-018 code) also still passes unchanged.
- `tests/test_gl_render_store.py` — 10 new tests (real GL, needs Xvfb or a
  display; skips cleanly via `pytest.importorskip`/context-creation
  fallback if none is available): persistence (camera/selection/position →
  same VertexList object + resource IDs, `geometry_uploads` delta 0 for
  camera/selection), topology (new IDs, new VertexList, correct index
  count/content), content equality vs. `TraceStore` for four scenarios
  (initial/geometry/selection/topology, cube mesh), and two pixel-level
  smoke tests: a cube (silhouette visible, single-vertex move changes
  pixels — the sensitive assertion, works reliably on a large-triangle
  mesh) and the real head mesh (silhouette visible through
  `RenderMesh.render(camera)` → `GLRenderStore.draw()`, no separate assert
  for a single-vertex-move pixel diff — see "Findings" below for why).

`playground/gl_store.py::PlaygroundPygletStore` and `playground/tests/`
were not touched; the full playground suite (843) passed unchanged before
and after, run via `xvfb-run -a python3 -m pytest playground/tests -q`
without any edits to `playground/`.

### Practical viewport test (§4/§8)

`experiments/ad018_gl_render_store_verification/run.py` (throwaway, not a
Production entry point) loads `examples/meshes/head_basemesh.obj`, binds
`mirai.viewport.camera.OrbitCamera`, and drives all four V02 scenarios
through `RenderMesh` + `GLRenderStore` end to end under Xvfb:

```
Loaded head_basemesh.obj: 326 vertices
Initial resource_ids: {'positions': 1, 'normals': 2, 'indices': 3, 'highlight_flags': 4, 'camera_uniforms': 5}
After 20x camera.orbit(): vertex_list identity unchanged = True | resource_ids unchanged = True | geometry_uploads = 0
After selection change: positions/normals ids unchanged = True
After single-vertex move: same VertexList object = True | patched position = (-1.443..., 1.353..., -1.229...)
After edge split: vertex_list identity changed = True | new vertex count = 327
Screenshot written to .../head_mesh_render.png
```

The written screenshot shows the head mesh shaded (directional light,
smooth normals) with the selected vertex's highlight (yellow) visible —
confirming the draw call is real GL through `RenderMesh`'s own data, not a
parallel path. `run_visible.py` (non-headless variant, same scene) is
provided for Manu's PC; not run in this environment (no display), not
required for this package's Definition of Done, and not an Artist verdict.

### Findings (boundaries tested, not just assumed)

- **`TraceStore` needed zero changes.** It never overrides the four new
  ABC methods; they resolve to the no-op base implementation. Confirmed by
  `TraceStoreLayoutDeclarationTests`, not merely asserted.
- **`PygletStore`/`PlaygroundPygletStore` needed zero changes** and stay
  fully out of scope for the new declaration — they never call
  `declare_group`/`declare_uniform`, and their existing single-attribute
  persistence-probe behavior (`resource_store.py` "Scope-Grenze" docstring)
  is untouched. `playground/tests` (843) confirm this empirically.
- **A single interior vertex move on the head mesh does not reliably
  change any rasterized pixel at 128×128** (unlike the cube, whose 8
  vertices each own a large fraction of the visible silhouette). This is a
  test-design finding, not a store defect: `GLRenderStore`'s in-place patch
  path was verified correct by the persistence tests (`resource_ids`
  unchanged, buffer content correct via direct `vlist.position[...]`
  readback) independently of whether that patch happens to move a visible
  pixel. The pixel-diff-on-vertex-move assertion therefore uses the cube
  (matches the spike's own test design), and the head mesh gets a
  silhouette-visible-only pixel check plus the practical viewport script's
  explicit position-patch readback instead of a pixel-diff assertion.
- **Sparse normal patching** (`VIEWPORT_V02_ARCHITECTURE.md` §12) is
  unchanged and still open: `RenderMesh._sync_geometry()` issues one
  `store.update()` call per modified vertex for positions and one per
  affected vertex for normals, same as before this package — `GLRenderStore`
  patches each with its own attribute-slice write, same cost shape the
  spike measured. Not addressed here (out of scope, handoff §5).
- **Mesh path discrepancy** (spike README "Mesh path discrepancy"):
  corrected as the one-line doc fix allowed by handoff §9 —
  `VIEWPORT_V02_ARCHITECTURE.md` (Reference Mesh line + Appendix B) now
  point at `examples/meshes/head_basemesh.obj`, matching where the file
  actually is.

### Scope check (`git diff --stat`)

Changes outside `src/viewport/`: this completion record (§6 above) and the
Appendix B / Reference Mesh path fix in `VIEWPORT_V02_ARCHITECTURE.md`
(both allowed by handoff §9/§10), plus new test files
(`tests/test_gl_render_store.py`, new tests appended to
`tests/test_resource_store.py`) and a new throwaway evidence directory
(`experiments/ad018_gl_render_store_verification/`) — both named in scope
§4 ("Tests", "Practical viewport test"). No edits to any existing test file
beyond the additions to `test_resource_store.py`; no edits to `playground/`
or any other `experiments/` directory.

### Definition of Done — status

- [x] Contract extension implemented in `src/viewport/`, additive,
      documented in module docstrings
- [x] New drawable GL store implemented (`GLRenderStore`), real indexed
      multi-attribute VertexList, real `render(camera)` draw call
- [x] All four V02 invariants verified against the new store under real GL
      (Xvfb) — `tests/test_gl_render_store.py` + practical viewport script
- [x] `TraceStore` compatibility with the new declaration confirmed (not
      just assumed) — `TraceStoreLayoutDeclarationTests`
- [x] Existing viewport test suite: 100% still green, zero edits (546→560,
      all additions), exact numbers reported above
- [x] Playground test suite: 100% still green, zero edits (843/843)
- [x] Head mesh renders visibly through the new store under Xvfb,
      evidenced (`head_mesh_render.png` + pixel-non-background assertion in
      `test_head_mesh_renders_visibly_through_new_store`)
- [x] Completion record appended to AD-018 (this section)
- [x] No changes outside `src/viewport/` except the completion record, the
      one-line mesh-path doc fix, and the new tests/evidence script named in
      scope §4 — confirmed via `git diff --stat`

---

## 7. Addendum — 2026-09-26: vertex point overlay (WP-06 Slice B2b)

**Resolves** from §5 "Deliberately not decided here", item Q2–Q7: the
*overlay representation* and the *point data* part (vertex points only).
Edge data, flat shading, triangulation under symmetry and tool → viewport
notification stay open.

**Trigger.** Artist verdict on B2 (Manu, 2026-09-26): highlight readability
**REJECT** — the per-vertex face tint (the `highlight_flags` mix in
`GLRenderStore.FRAGMENT_SRC`) reads like vertex paint. Selected vertices are
to be shown as small round points in the production yellow; vertex hover
comes in as a slightly larger, translucent pale-yellow point
(`PROVISIONAL`, see ROADMAP §7 intake log).

**Decision (E15).** Overlay representation = `VIEWPORT_V02_ARCHITECTURE.md`
§4.7 Option A — separate small overlay geometry drawn after the mesh —
implemented **outside** `GLRenderStore`:

- New module `src/viewport/gl_point_overlay.py`, class `GLPointOverlay`:
  its own flat-color point program (lazily compiled, class-level shared,
  like `GLRenderStore`), one `GL_POINTS` vertex list per layer (`hover`,
  `selected`), rebuilt only when that layer's positions change. Round
  points via `GL_PROGRAM_POINT_SIZE` + `gl_PointCoord` discard with a 1-px
  smoothstep edge; depth test off (points stay visible through the mesh);
  draw order hover, then selected.
- Data is headless (E16): `SelectionOverlay` computes the world positions
  (selected vertices in vertex mode, the hovered vertex); `Viewport.sync()`
  pushes them to the optional point overlay when selection/hover changed
  and after `on_vertices_moved` / `on_topology_changed`. Camera matrices
  come from the same packet `RenderMesh` builds for `camera_uniforms` —
  no second camera-matrix path.
- Wiring (E17): `Viewport(..., point_overlay_type=None)` /
  `Application.init_scene(..., point_overlay_type=None)`, same pass-through
  pattern as `store_type`; `src/main.py` passes `GLPointOverlay`.

`GLRenderStore` keeps its one-group scope boundary (§5 binding constraint
"not a general GPU resource manager"); its only change is E18 below.

**Rejected alternatives.** A second drawable group inside `GLRenderStore`
(breaks its stated one-group scope); keeping the face tint (Artist
REJECT); drawing in `src/main.py` (thin entry point; `Application` stays
window-free).

**E18 — face tint removed.** `GLRenderStore.FRAGMENT_SRC` outputs the
shaded base color only; the `v_highlight` mix is gone. The
`highlight_flags` attribute, its `RenderMesh` layout slot and its
selection-dirty update path are left in place on purpose.

*Hotfix 2026-09-26:* on Manu's Windows machine the driver optimized
`highlight_flag` out of the program once the fragment shader stopped reading
`v_highlight`; pyglet then built the VertexList without it and the kept
selection update path crashed (`AttributeError` in
`GLRenderStore._patch_attribute`, on the first hover). `_patch_attribute`
now skips attributes absent from the VertexList (same as pyglet does at
VertexList creation). Mesa/llvmpipe keeps the attribute, which is why the
Xvfb tests did not catch it; `test_selection_update_survives_driver_dropping_
highlight_attribute` now forces the inactive case on every driver.

**Follow-up (not done here).** Remove the now visually unused
`highlight_flags` pipeline (`MESH_GROUP_ATTRIBUTES` entry, vertex shader
input, `RenderMesh._sync_selection()` upload, `SelectionOverlay.
build_highlight_flags()`). It touches the `RenderMesh` layout, the
dirty-state tests and the benchmark scenarios, so it is a separate
cleanup slice.
