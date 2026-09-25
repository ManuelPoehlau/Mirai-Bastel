# AD-018 — Production Draw Binding for `RenderMesh`

**Status:** PROPOSED — draft from the draw-binding spike, not a decision.
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
