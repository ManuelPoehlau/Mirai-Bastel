All evidence gathered and tests verified (106 transform-related tests pass). Here is the complete audit.

---

# WP-03 Transform Foundation — Complete Audit

**Canonical definition audited against:** `docs/architecture/ROADMAP.md` §5 WP-03 (lines 253–287) — Goal: *"Establish a reusable transform concept instead of implementing Move, Rotate and Scale as unrelated features."* DoD: *"Transform behavior is a reusable domain capability that can be driven by different tools and later consumers."*
**Supporting spec:** `docs/V1_SPEC.md` §4 (Translate, Rotate, Uniform Scale, Scale X/Y/Z, Axis Constraints, Selection Pivot; generic begin/update/commit/cancel lifecycle, not mesh-specific).
**Governing architecture decisions:** ADR-001 (Core freeze lifted for Move/Rotate/Scale promotion — Core owns transform semantics, Production owns interaction), AD-009 (axis + plane constraints, DECIDED, executed), AD-010 (Playground as live exercise path).

**Verification status:** `tests/test_transform_operations.py`, `test_tool_integration.py`, `test_tool_lifecycle.py`, `test_playground_transformer.py`, `test_tool_manager.py`, `test_routing.py` — **106 passed** (run live during this audit).

---

## Area-by-area findings

### 1. Translation / Move — **Implemented** (with a foundation-coherence debt)
- `src/core/operations/move.py` — `MoveOperation` (line 47): incremental delta update, snapshot begin, exact restore cancel, `MoveVerticesCommand` (line 24, start/end positions, no delta → exact undo/redo).
- `src/mirai/interaction/tools/move.py` — `MoveTool` (line 101): drag → `OrbitCamera.screen_delta_to_world` (line 175), AD-009 axis/plane mask (lines 178–184), anchor-vertex mapping.
- Tested end-to-end: `tests/test_tool_integration.py` `ModalMoveIntegrationTests` (incl. `test_move_explicit_plane_constraint`, line 389).
- **Debt:** `MoveOperation` deliberately did **not** adopt the shared `VertexTransformOperation` base — `src/core/operations/transform.py` docstring lines 10–12: *"MoveOperation bleibt bewusst UNANGETASTET … eine spätere Vereinheitlichung auf diese Basis ist eine explizite Architekturentscheidung"*. Result: two parallel implementations of the same lifecycle contract, two command classes (`MoveVerticesCommand` vs `VertexTransformCommand`), duplicated `_add` helpers, duplicated selection views.

### 2. Rotation — **Implemented**
- `src/core/operations/transform.py` — `RotateOperation` (line 228) on `rotate_around_axis` (line 94, Rodrigues, right-hand rule, null-axis rejected), angle-accumulating incremental updates, fixed pivot.
- `src/mirai/interaction/tools/rotate.py` — `RotateTool` (line 70): default axis = camera forward (screen-plane rotation, lines 94–97), world axes, plane→normal mapping (`_PLANE_ROTATION_AXES`, line 45), chunking-independent cumulative-drag gesture (lines 103–112).
- Tests: `tests/test_transform_operations.py` `RotateOperationTests`; `test_tool_integration.py` lines 251–297 (commit/undo/redo/cancel/plane/invalid axis).

### 3. Scale — **Implemented**
- `src/core/operations/transform.py` — `ScaleOperation` (line 245): uniform float or per-axis triple, multiplicative accumulation, invalid-factor `ValueError` (`_as_triple`, line 75).
- `src/mirai/interaction/tools/scale.py` — `ScaleTool` (line 35): axes mask, plane support, `MIN_SCALE` guard against mirror/degenerate (lines 39–42).
- Tests: `tests/test_transform_operations.py` `ScaleOperationTests` (lines 154–228); `test_tool_integration.py` lines 307–364 (incl. `test_scale_explicit_plane`, line 347).

### 4. Transform Context / shared transform abstraction — **Partial**
- **Exists:** `src/core/operation.py` — generic `OperationContext` (target/selection/history/params, lines 46–61) + `Operation` lifecycle with enforced contracts (incremental update lines 15–25, history-only-in-commit lines 26–28); `VertexTransformOperation` base (`transform.py` line 141) as the shared rotate/scale machinery; tool-side `TransformTool` base (`tools/transform.py` line 68) + shared `_WORLD_AXES` (line 40).
- **Missing:** no typed *transform context* — pivot travels as an implicit dict key `params["pivot"]` (`operation.py` line 57, `transform.py` line 161; `tools/transform.py` line 115). There is no `TransformContext`/`TransformRequest` concept anywhere (search returned zero hits). The "reusable concept" is currently realized as convention (docstrings + parallel base classes), not as an explicit contract.

### 5. Coordinate Space: World / Local / Screen-View — **Partial**
- **World:** the only space of the Core operations — vertex positions are world tuples on a single `Mesh` (`transform.py` `_on_begin`).
- **Screen/View:** exists only at the interaction boundary, in the tool/camera layer — `src/mirai/viewport/camera.py` `screen_delta_to_world` (line 229), `screen_to_ray`, `project_to_screen`, `basis()`; `RotateTool`'s default axis is camera-forward (`rotate.py` line 96). Correctly placed per ADR-001 (interaction, not Core).
- **Local/Object space:** **missing** — a project-wide search for "local" in `src/`, `playground/`, `tests/` returns nothing. No per-object transform, no local axes, no normal-space scale. This is gated by **ARCH-01 (Object/Component Model)**, which is explicitly still open (`ROADMAP.md` lines 336–372) and which the roadmap itself defers object transforms to (WP-03 "Enables: object transforms after the Object Model decision").

### 6. Pivot concept — **Implemented**
- Fixed at `begin()`, never recomputed per update (`transform.py` lines 161–167, tested `test_pivot_stays_fixed_during_interaction`); default = selection centroid (`_selection_center`, line 169; `selection_pivot()` helper in `tools/transform.py` line 141); explicit pivot overridable (`begin(pivot=...)`).
- Not present (fine for WP-03 scope): alternative pivot modes (3D cursor, individual origins, bbox center).

### 7. Axis + Plane Constraints X/Y/Z + XY/XZ/YZ — **Implemented**
- AD-009 (`docs/architecture/AD-009-AXIS-PLANE-CONSTRAINTS.md`, DECIDED 2026-09-17) — consequences executed: `_WORLD_AXES` extended to 6 entries (`tools/transform.py` lines 40–54), Move gained axis/plane masking, Rotate gained plane→normal-axis, Scale gained plane masks. All tested (`test_tool_integration.py` lines 288, 347, 389).
- Note: constraints are **world-axis only**; no view-relative constraint (e.g. axis from current view) and no custom-plane constraint — consistent with AD-009's scope and WP-03's "where justified by current editor needs".

### 8. Multi-selection — **Implemented**
- Multi-vertex sets throughout the Core ops; `resolve_selection_vertices()` (`tools/move.py` line 74) maps Vertex/Edge/Face-mode selections to the union vertex set; tested `SelectionResolutionIntegrationTests` (`test_tool_integration.py` line 169) and consumed by the Playground for all three tools (`playground/transformer.py` line 52).
- Minor placement issue: this shared resolution helper lives in the MoveTool module (`tools/move.py`) but is used by all transform consumers.

### 9. Transform lifecycle begin → update → commit → cancel — **Implemented**
- Core: `Operation` state machine (`operation.py` lines 81–105), `OperationStateError` guards.
- Tool: `Tool` IDLE/ACTIVE/INTERACTING (`tools/../../tool.py` lines 84–149), deactivate-during-INTERACTING forbidden; `ToolManager` auto-cancels in-flight interactions on tool switch (`tool_manager.py` lines 121–129) — tested `test_tool_switch_cancels_in_flight_interaction` (line 409).
- `tests/test_tool_lifecycle.py` (18 cases) + `tests/test_tool_manager.py` green.

### 10. History integration: undo/redo + boundaries — **Implemented**
- Exactly one history entry per interaction, created only in `commit()` (`operation.py` lines 92–99); no-op commit → `None` → no entry (tested); cancel → no history, exact restore; start/end positions (no delta) for rounding-proof reversal (`VertexTransformCommand` lines 117–138).
- Full pipeline verified: input → binding → command → tool → operation → commit → undo → redo (`test_tool_integration.py` `test_full_pipeline_rotate_input_to_history`, line 419).

### 11. Selection / Operations dependencies — **Implemented**, minor duplication
- Selection stays Core domain state; operations read `context.selection.vertices`; tools pass minimal `_VertexSelectionView`/`_MoveSelectionView` (**duplicated in both `tools/transform.py` line 57 and `tools/move.py` line 63**).

### 12. Viewport / Playground integration — **Partial (real-world consumption proven; verification caveats)**
- The Playground consumes the **production** tools with no second implementation: `playground/transformer.py` (wrappers around `MoveTool`/`RotateTool`/`ScaleTool`), wired in `playground/window.py` (lines 57–61, 680–721, 899–910, 996, 1071–1107, 1268–1497; X/R/S held-hotkey → begin, release → commit, ESC → cancel). Tested: `tests/test_playground_transformer.py`.
- Per AD-010 Execution Updates: renderer ported to real `PygletStore` (Update 1) and single-vertex Tweak VBO in-place patching executed (Update 2, commit `a0c9691`) — **but real-hardware confirmation is still outstanding** and multi-vertex transform paths still trigger full VBO rebuilds (`AD-010` §"Still open").
- **Discrepancy:** `playground/transformer.py` swallows all exceptions (`except Exception: return False`) — masks real errors in the transform path.
- The production `Application` (`src/mirai/application.py`, `_setup_tools` lines 78–86, `dispatch_command` 103–125) is headless-verified only; there is no production window consuming it. The living editor experience currently exists only in the Playground.

### 13. Architecture boundaries / coupling — **Healthy, with named decision points**
- Core owns transform semantics, imports nothing from viewport/experiments (`transform.py` docstring lines 43–45; `application.py` imports Core as standalone `core` package, line 23–25). ADR-001 boundary (Input → Production Interaction → Tool → Core Operation → Core Data) is realized in actual call paths.
- Coupling points to be aware of: (a) axis/plane *vocabulary* lives in the tool layer (`_WORLD_AXES`, `_PLANE_ROTATION_AXES`) while the *math* is split between tool masking and Core per-axis factors — a future gizmo or non-tool consumer cannot yet reuse constraint semantics directly; (b) gesture→world mapping depends on `OrbitCamera` duck-typing — fine, but it means "screen-space" behavior is a tool concern, not a foundation contract.

### 14. Implementation vs older roadmap wording — **Code has moved beyond the roadmap text**
- ROADMAP WP-03 scope says axis constraints "where justified" — the implementation went further: full X/Y/Z + XY/YZ/XZ plane constraints (AD-009), and AP-04 Phase 1 Playground transform functions with commit-on-release / ESC-cancel interaction variants (`playground/experiments/transform/variant_move|rotate|scale|press_mode|hold|press_drag_click.py`).
- **Discrepancy to report:** ROADMAP §14 "Current Priority View" (lines 770–779) still lists WP-03 as future ("dependent on WP-04 Application") and does not record that Rotate/Scale are promoted into `src/core` (per ADR-001), AD-009 is decided and executed, and the Playground already exercises the full transform path. The roadmap understates the actual repository state.

---

# WP-03 Completion Map

| Area | Status | Evidence | Blocking WP-03? |
| ---- | ------ | -------- | --------------- |
| Translation / Move | Implemented | `src/core/operations/move.py::MoveOperation`; `tools/move.py::MoveTool`; `test_tool_integration.py` | No — but Move sits **outside** the shared base (coherence debt, decision needed) |
| Rotation | Implemented | `transform.py::RotateOperation`, `rotate_around_axis`; `tools/rotate.py`; `test_transform_operations.py` | No |
| Scale (uniform + per-axis + plane) | Implemented | `transform.py::ScaleOperation`; `tools/scale.py`; `test_tool_integration.py` | No |
| Transform context / shared abstraction | Partial | `operation.py::OperationContext`, `transform.py::VertexTransformOperation`, `tools/transform.py::TransformTool`; pivot via implicit `params["pivot"]`; no typed TransformContext | Not capability-blocking, but blocks the "coherent reusable Foundation" claim |
| Coordinate Space (World) | Implemented | Mesh world positions throughout; `application.py` scene model | No |
| Coordinate Space (Screen/View) | Implemented (interaction boundary only) | `camera.py::screen_delta_to_world`; `rotate.py` camera-forward default | No |
| Coordinate Space (Local/Object) | Missing | No "local" concept anywhere; gated by open ARCH-01 (`ROADMAP.md` 336–372) | No for vertex-level WP-03 (roadmap defers object transforms to ARCH-01) |
| Pivot | Implemented | `transform.py` begin-fixed pivot + selection centroid; `tools/transform.py::selection_pivot` | No |
| Axis constraints X/Y/Z | Implemented | AD-009 + `_WORLD_AXES`; tests 280/336/375 | No |
| Plane constraints XY/XZ/YZ | Implemented | `_WORLD_AXES` planes; `_PLANE_ROTATION_AXES`; tests 288/347/389 | No |
| Multi-selection | Implemented | `tools/move.py::resolve_selection_vertices`; `SelectionResolutionIntegrationTests` | No |
| Lifecycle begin→update→commit→cancel | Implemented | `operation.py`, `tool.py`, `tool_manager.py`; 18+ lifecycle tests | No |
| History boundaries (undo/redo, single entry, cancel-no-history) | Implemented | `VertexTransformCommand`/`MoveVerticesCommand`; `test_tool_integration.py:419` full pipeline | No |
| Playground / practical viewport verification | Partial | `playground/transformer.py` + `window.py` wiring; AD-010: real-hardware confirmation outstanding, multi-vertex VBO still full rebuild | Soft-blocks DoD "practical viewport tests must cover all supported transform modes" |
| Roadmap/doc currency | Discrepancy | ROADMAP §14 vs actual code state (see §14 above) | No (documentation debt, not code) |

---

## A. Already solid
- **Core transform semantics for all three operations** in `src/core` with exact, rounding-proof undo/redo, enforced incremental-update contract, single-history-entry commit, and exact cancel — tested at operation level and full-pipeline level.
- **Two-layer architecture per ADR-001** with real, non-circular call paths: Binding → Command → ToolManager → Tool → Core Operation → Mesh/History (`application.py`, `tool_manager.py`, tools).
- **Axis + plane constraint system** (AD-009) fully decided, executed, and tested across all three tools, with the correct differentiation (mask for Move/Scale, plane-normal axis for Rotate).
- **Fixed-pivot contract** with selection-center default and explicit override, invariant-tested.
- **Production tools consumed unchanged by the Playground** — the DoD phrase "driven by different tools and later consumers" is already demonstrated twice (production tools + playground wrapper).

## B. Partial / needs completion
- **Transform context abstraction:** pivot/constraint state travels via untyped `params` dict and parallel base classes; no single explicit, typed transform contract.
- **Practical viewport verification:** playground paths exist and are Xvfb-verified, but AD-010 records real-hardware confirmation as outstanding; multi-vertex transform updates still fully rebuild VBOs (correctness fine, performance/robustness open).
- **Roadmap/§14 currency:** the canonical roadmap understates the actual WP-03 state.
- **Playground transformer error-swallowing** (`except Exception: return False`) hides real failures in the transform path.

## C. Missing
- **Local/Object coordinate space** — absent; explicitly gated on **ARCH-01** (Object/Component Model), not on WP-03 code.
- **Unification of Move onto the shared transform base** — currently two parallel lifecycle implementations, two command classes, duplicated vector helpers and duplicated selection-view classes.
- **Reusable constraint vocabulary** for non-tool consumers (gizmos, scripted transforms) — axis semantics live only in the tool layer.
- (Deferred by roadmap, do **not** treat as WP-03 gaps: object transforms, soft-selection influence beyond the placeholder weights, view-relative/custom-plane constraints.)

## D. Architecture questions
1. **Move unification (explicit Core decision required):** should `MoveOperation` be consolidated onto `VertexTransformOperation` (or both onto one `VertexTransformCommand`)? `transform.py` itself names this as an "explizite Architekturentscheidung" — it must not happen as a side effect.
2. **Home of constraint semantics:** do axis/plane definitions (`_WORLD_AXES`, `_PLANE_ROTATION_AXES`, masks) belong in the tool layer (current), in Core as part of ADR-001's "geometric constraint semantics", or in a new production-level transform module? This decides whether a future gizmo can reuse the foundation without duplicating vocabulary.
3. **Should a typed TransformContext exist** (pivot, constraint, space, affected IDs) replacing `params["pivot"]` string contracts — or is the current convention acceptable per "implement little"?
4. **ARCH-01 sequencing:** confirm WP-03 vertex-level completion does not require ARCH-01, and record that object-level transforms remain blocked by it (per current roadmap this is already the intent — verify it stays documented).
5. **Roadmap update (capture, not code):** §14 should record the actual WP-03 state (Core promotions per ADR-001, AD-009 executed, Playground AP-04 Phase 1 transforms live) per the repository's own documentation-currency rule.

## E. Recommended next bounded implementation package(s)
*(listed only — deliberately not implemented, per audit constraints)*

1. **PKG-A — Core coherence consolidation (small):** Move/`MoveVerticesCommand` onto the shared `VertexTransformOperation`/one command class; extract the duplicated selection views and vector helpers. Requires the §D-1 decision first; guarded by the existing 106 tests.
2. **PKG-B — Shared selection/constraint placement (tiny):** move `resolve_selection_vertices` and `selection_pivot` to a neutral home (e.g. `tools/transform.py` or a small production helper module) so all three tools and the Playground share one definition.
3. **PKG-C — Transform context contract (optional, small):** a small typed context (pivot, affected IDs, constraint, description) replacing `params["pivot"]`; only if §D-3 answers "yes".
4. **PKG-D — Verification pass (process, no new features):** real-hardware practical viewport run of all supported transform modes (move/rotate/scale × axis/plane/no-constraint × commit/cancel/undo), close the AD-010 real-hardware caveat, and update ROADMAP §14 + a WP-03 status note.

**Bottom line:** WP-03's *capability* (translate/rotate/scale as one reusable, history-correct, tool-independent foundation) exists in production code and is well tested. What separates it from qualifying as a *coherent* Transform Foundation is mostly coherence debt (Move outside the shared base, untyped context, duplicated vocabulary) plus verification and documentation currency — not missing math or missing features. The one genuinely missing scope item (local/object space) is correctly parked behind the open ARCH-01 gate.