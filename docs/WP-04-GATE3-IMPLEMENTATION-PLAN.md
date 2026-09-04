# WP-04 Gate 3 — Concrete Implementation Plan

**Status:** Analysis complete — awaiting GO
**Branch:** wp/04-production-foundation
**Analyst:** Claude (Senior Production/Architecture Engineer)
**Date:** 2026-09-01

**Code reviewed (verbatim, not assumed):** `AGENTS.md`, `CORE_V1_FREEZE.md §7`,
`WP-04_GATE_PLANNING.md`, `WP-04_OPEN_QUESTIONS.md`, `Core Architecture
Reassessment.md`, `WP-04_AGENT_VERIFICATION_REPORT.md`, all of `src/core/*`,
all of `experiments/mirai_bastel_viewport_V1/viewport/*.py`,
`experiments/mirai_bastel_core_V1/.../operations/transform.py`,
`tests/_bootstrap.py`, `run.py`.

---

## 0. Q1 — Resolved by the Brief, Formal Doc Still Owed

The WP-04 brief §6 already states as **VERBINDLICHE ENTSCHEIDUNG**: Move/Rotate/Scale
+ geometric constraint semantics belong in Core. That *is* the Q1 answer
(= Option C, "Promote"). The Reassessment doc and the Agent Verification
Report both independently converge on the same recommendation, and my own
code review confirms it's mechanical (§1 below).

**What's still missing (per AGENTS.md §5 "never silently change
architecture"):** the formal `docs/architecture/DECISION_Q1_TRANSFORM_OPS.md`
recorded by Manuel. I will create the promoted files as part of Gate 3 (Task
0 below) and Manuel signs the decision doc — but this is no longer a content
question, only a paperwork step. I'm not blocked on it to keep planning, but
production code that depends on the promoted ops should not merge to `main`
before that doc exists (AGENTS.md discipline, not a technical constraint).

---

## 1. Core Changes (Task 0 — do first, everything else depends on it)

### 1.1 Promote Transform Operations

| File | Change | Why |
|---|---|---|
| `src/core/operations/transform.py` | **NEW** — copy verbatim from `experiments/mirai_bastel_core_V1/mirai_bastel_core/operations/transform.py` (261 lines). Only the relative imports (`..ids`, `..mesh`, `..operation`) are already correct as-is — no rewrite needed, the fork's package layout is identical to `src/core/`. | Confirmed contract-identical to `MoveOperation` (same `Operation` ABC, same begin/update/commit/cancel, same start/end-position `Command` pattern). Zero new Core API surface. Freeze-Rule §7 steps 1–5 are satisfied (see Reassessment §7, confirmed by my own read of both files side by side). |
| `src/core/operations/__init__.py` | Add `from .transform import RotateOperation, ScaleOperation, VertexTransformCommand` + extend `__all__` | Currently only exports `MoveOperation`, `MoveVerticesCommand`, `MeshStateCommand`. |
| `src/core/__init__.py` | Add `RotateOperation, ScaleOperation` to the top-level import + `__all__` (mirrors existing `MoveOperation` pattern exactly, line for line) | Gate Plan Task 4.3 acceptance: `from core import RotateOperation, ScaleOperation` must work. **Note:** Gate Plan text says `from mirai.core import ...` — that's a doc typo. `src/core` is a sibling of `src/mirai`, not nested under it (confirmed via `tests/_bootstrap.py`, which puts `src/` itself on `sys.path`, making `core` and `mirai` both top-level packages). I'll use `from core import RotateOperation, ScaleOperation` and flag the doc typo to Manuel rather than silently building a `mirai.core` shim. |

**Explicitly not touched:** `mesh.py`, `operation.py`, `history.py`, `selection.py`, `ids.py`. No signature changes anywhere in Core.

### 1.2 Test Migration

| File | Change | Why |
|---|---|---|
| `tests/test_transform_operations.py` | **NEW** — migrate the 18 tests from `experiments/mirai_bastel_viewport_V1/tests/test_transform_operations.py`, retarget import from `mirai_bastel_core` to `core` (via `tests/_bootstrap`, same pattern as existing `tests/test_core.py`) | Repo-level regression coverage for the promoted ops, per Agent Verification Report §F item 3. |

### 1.3 Cleanup (flagged, not executed without Manuel's go-ahead)

`src/core/move.py` is a dead duplicate of `src/core/operations/move.py` (confirmed byte-for-byte relevant content match). Agent report already flagged this; I will **not** delete it in Gate 3 — out of scope for this task, and AGENTS.md discipline says cleanup like this is Manuel's call, not something to fold into an unrelated Gate. I'll leave a one-line note in the Gate 3 PR description instead.

---

## 2. `src/mirai/` Directory Structure (Task 3.1)

```
src/mirai/
    __init__.py
    application.py
    main.py
    interaction/
        __init__.py
        tool.py
        input.py
        commands.py
        bindings.py
        tool_manager.py          (Gate 4, not Gate 3)
        tools/
            __init__.py
    viewport/
        __init__.py
        camera.py
        picking.py
        display.py
        vecmath.py
        render.py
        window.py
```

No circular imports: `viewport/*` and `interaction/*` only import `core` (sibling package) and stdlib; `application.py` imports both `viewport` and `interaction`; `main.py` imports `application` and `viewport.window`. One direction only.

---

## 3. File-by-File Change List (Gate 3 scope)

### 3.1 Straight copies (no logic changes, confirmed pyglet-free at source)

| Source | Destination | Import fixups needed |
|---|---|---|
| `experiments/.../viewport/tool.py` | `src/mirai/interaction/tool.py` | None — zero external imports besides stdlib (`abc`, `enum`, `typing`). |
| `experiments/.../viewport/input_binding.py` | `src/mirai/interaction/input.py` | None — stdlib only (`json`, `dataclasses`, `pathlib`). |
| `experiments/.../viewport/commands.py` | `src/mirai/interaction/commands.py` | None — pure string constants. |
| `experiments/.../viewport/default_bindings.py` | `src/mirai/interaction/bindings.py` | `from . import commands as cmd` stays relative, unchanged, since it lands in the same `interaction/` package. `from .input_binding import ...` becomes `from .input import ...` (filename changed per Gate Plan Task 3.3). |
| `experiments/.../viewport/camera.py` | `src/mirai/viewport/camera.py` | `from . import vecmath as v` stays relative, unchanged (vecmath moves into the same package). |
| `experiments/.../viewport/picking.py` | `src/mirai/viewport/picking.py` | `from mirai_bastel_core import EdgeId, FaceId, Mesh, VertexId` → `from core import EdgeId, FaceId, Mesh, VertexId`. Only real import rewrite in this batch. |
| `experiments/.../viewport/display_state.py` | `src/mirai/viewport/display.py` | None — stdlib only (`enum`). |
| `experiments/.../viewport/vecmath.py` | `src/mirai/viewport/vecmath.py` | None — stdlib only (`math`). |

**Not copied in Gate 3:** `constraints.py` stays in `experiments/` — confirmed unwired (no Tool, no Command, no dispatch references it anywhere in `app.py` or `move_tool.py`/`transform_tool.py`). Bringing it into production now would be dead production code. Documented as Test Spec #2 (F. in Agent report) for a future gate, not built here.

### 3.2 New files (extracted/adapted from `app.py`, not copied verbatim)

`app.py` (582 lines) is a single `pyglet.window.Window` subclass mixing four concerns. I confirmed this by reading the whole file: rendering (`_compute_normals`, `_face_triangle_arrays`, `_rebuild_geometry`, `on_draw`, the two `_draw_*_highlight` helpers), tool/interaction glue (`_activate_tool`, `_begin_move_on_current_selection`, `_start_move_interaction`, `_finish_drag`, `_cancel_ongoing_tool`, `_end_modeling_tool`), command dispatch (`_dispatch_command`, the two `dict`-based routing tables), and pyglet event handlers (`on_key_press`, `on_mouse_press/drag/release/scroll`, `on_mouse_motion`) that only do input-translation + one-line delegation. This maps cleanly to three files:

#### `src/mirai/application.py` (NEW)

Window-free orchestrator. State: `scene: Scene` (from `core`), `camera: OrbitCamera`, `display: DisplayState`, `bindings: BindingSet`, `tool_manager` (Gate 4 stub in Gate 3 — see §4 below), `selection_mode`, `hovered_id`.

Methods pulled from `app.py`, made pyglet-independent:
- `init_scene(geometry_type="cube")` — adapt `demo_scene.build_cube_scene()`, but that function imports `from mirai_bastel_core import Scene` (the fork) — **must** be re-pointed to `from core import Scene` when copied. Decision: don't copy `demo_scene.py` as-is; write a 15-line equivalent directly using `core.Scene`/`core.Mesh` (same vertex/face literal data), since it's the only file in this batch that imports the *fork* rather than being pyglet-glue.
- `dispatch_command(command, context=None, **params)` — body of `_dispatch_command`, mode/display dicts included, minus the `tool_for_command` routing (Gate 4).
- `set_selection_mode(mode)` — from `_set_selection_mode` minus `_update_caption()` (caption is a window concern, moves to `window.py`).
- `pick(x, y)` — from `_pick`, unchanged logic, just relocated.
- `refresh_hover(x, y)` — from `_refresh_hover`.
- `clear_selection()` — from `_clear_selection`.
- `shutdown()` — new, trivial (no teardown state exists yet; placeholder for Gate-3 acceptance criterion).

**Explicitly deferred to Gate 4** (per Gate Plan, and confirmed correct by the dependency: `_activate_tool`/`_begin_move_on_current_selection`/tool-manager wiring all need `ToolManager` + `tool_for_command`, which are Gate 4 tasks): `dispatch_command` in Gate 3 handles only the non-tool commands (`SET_*_MODE`, `UNDO`, `REDO`, `CANCEL`, `CLEAR_SELECTION`, `CYCLE_DISPLAY_MODE`, `TOGGLE_WIREFRAME_OVERLAY`, `SET_SHADED/FLAT_SHADED/WIREFRAME`). Falls through to `False` for `MOVE/ROTATE/SCALE` until Gate 4 wires the ToolManager in. This is a real, honest Gate-3/Gate-4 seam, not a shortcut — it matches Gate Plan Task 3.7's stub signature exactly (`dispatch_command` body marked `# Implement: Command → Tool routing` under Task 4.6, not 3.7).

#### `src/mirai/viewport/render.py` (NEW)

Pure functions, extracted from `app.py`'s geometry methods, made static (no `self`):
- `compute_normals(mesh) -> (face_normals, vertex_normals)` — from `_compute_normals` body, `self.scene.mesh` → `mesh` param.
- `face_triangle_arrays(mesh, face_ids, flat: bool) -> (positions, normals)` — from `_face_triangle_arrays`, `self.display_state.mode is FLAT_SHADED` hoisted to a `flat` bool param (removes the `self` dependency).
- `default_normals(point_count)` — unchanged, already a `@staticmethod`.

These are the only genuinely pure geometry functions in `app.py`; everything else in the rendering path (`_rebuild_geometry`, `on_draw`) touches `pyglet.graphics.Batch`/`vertex_list`/GL calls and therefore has to stay in `window.py`, not here — moving it to `render.py` would just relocate the pyglet dependency, not remove it. I'm keeping `render.py` honest (pure math only) rather than making it a second dumping ground.

#### `src/mirai/viewport/window.py` (NEW)

Thin `pyglet.window.Window` subclass, constructed with an `Application` instance (dependency injection per Gate Plan Task 3.9). Owns: shader/program setup, `_batch`/`*_list` vertex-list state (this is GPU-buffer state, doesn't belong in the window-free `Application`), `on_draw` (calls `render.face_triangle_arrays`/`compute_normals` against `app.scene.mesh`, then does the actual `vertex_list`/`draw()` calls — this part of `_rebuild_geometry` + `on_draw` stays here verbatim), and the five `on_key_press`/`on_mouse_*` handlers, each translating the pyglet event into an `Input` and calling `self.app.bindings.command_for(...)` → `self.app.dispatch_command(...)`, exactly the `_key_input`/`_mouse_input`/`_wheel_input`/`_modifier_set` helpers from `app.py` (copied verbatim, zero logic change — they're already pyglet-translation-only).

**Known Gate-3/Gate-4 seam here too:** `on_mouse_press`'s `SELECT` branch currently starts a Move interaction on drag (`_begin_move_on_current_selection`). In Gate 3 this degrades to select/deselect-only (no drag-to-move) — full parity returns in Gate 4 once `ToolManager` exists. I'm calling this out explicitly rather than silently shipping a behavior regression.

#### `src/mirai/main.py` (NEW)

~15 lines, per Gate Plan Task 3.10 spec verbatim: build `Application()`, call `init_scene("cube")`, construct `ModelerWindow(app)`, `pyglet.app.run()`.

---

## 4. Gate 3 vs Gate 4 Boundary (explicit, so nothing gets silently skipped)

Gate 3 acceptance (`WP-04_GATE_PLANNING.md`) requires the window to "respond to input" and lists Tasks 3.1–3.12 only — `ToolManager`, `MoveTool` extraction, and tool routing are Task 4.1/4.2/4.5, a separate gate. My plan above matches that split exactly:

- **In Gate 3:** selection mode switching, undo/redo, cancel, clear-selection, display-mode cycling, click-to-select/deselect, camera orbit/pan/zoom, picking, rendering. All window-free-testable via `Application`.
- **Deferred to Gate 4 (by the Gate Plan itself, not my choice):** `ToolManager`, `MoveTool`/`RotateTool`/`ScaleTool` extraction, `tool_for_command` routing, drag-to-move.

This means Gate 3's `python src/main.py` will show a cube, orbit/pan/zoom, and let you select/deselect vertices/edges/faces and cycle display modes — but moving geometry will not work until Gate 4 lands. That is what the Gate Plan specifies (Task 3.7's `dispatch_command` stub explicitly excludes tool routing; Task 4.6 adds it), so I'm not narrowing scope on my own initiative — just making the seam visible instead of discovering it mid-implementation.

---

## 5. Test Requirements (Gate 3)

| File | Source | Count | Notes |
|---|---|---|---|
| `tests/test_application.py` | NEW | ~15–20 | `init_scene`, `dispatch_command` for each non-tool command, `set_selection_mode`, `pick` (with a stub mesh), `clear_selection`. No window. |
| `tests/test_mirai_input_binding.py` | migrate from `experiments/.../tests/test_input_binding.py` (8 tests) | 8 | Import path only change (`viewport.input_binding` → `mirai.interaction.input`). |
| `tests/test_mirai_camera_picking.py` | migrate from `experiments/.../tests/test_camera_picking.py` (11 tests) | 11 | Same — import path only. |
| `tests/test_mirai_display_state.py` | migrate from `experiments/.../tests/test_display_state.py` (5 tests) | 5 | Same. |
| `tests/test_mirai_render.py` | NEW | ~6–8 | `compute_normals`/`face_triangle_arrays` against a small stub mesh (reuse the cube from `application.py`'s `init_scene` or a 1-triangle mesh); no pyglet import in this test file — proves `render.py` stayed pure. |
| `tests/test_smoke.py` | NEW, per Gate Plan Task 3.12 spec | 1 | Exact scenario from Gate Plan: `Application()` → `init_scene()` → simulate `Input("key","v")` → `dispatch_command` → assert `selection.mode == VERTEX`. |

Existing 62 `unittest` core tests + the transform ops migration (§1.2) run unchanged as regression. Target: 80+ tests, no window dependency, matches Gate 3 acceptance criterion verbatim.

I'm **not** writing `test_window.py` — a real pyglet window can't run headless in this sandbox and window smoke-testing is explicitly Gate 10 (manual E2E), not Gate 3/8 automated coverage, per the Agent report's 3-tier test strategy (§N.4).

---

## 6. Dependency Order (so nothing gets built against a stub that isn't there yet)

```
1. Core promotion (§1)                — independent, no dependency
2. src/mirai/ + __init__.py skeleton  — trivial, no dependency
3. interaction/tool.py, commands.py   — stdlib only, no dependency
4. interaction/input.py               — stdlib only, no dependency
5. interaction/bindings.py            — needs (3) commands, (4) input
6. viewport/vecmath.py                — stdlib only, no dependency
7. viewport/camera.py                 — needs (6)
8. viewport/picking.py                — needs core (already exists), (7)
9. viewport/display.py                — stdlib only, no dependency
10. viewport/render.py                — needs core (mesh reads only)
11. application.py                    — needs (3)(4)(5)(7)(9), core.Scene
12. viewport/window.py                — needs (11), pyglet
13. main.py                           — needs (11)(12)
14. Tests for 3–11                    — parallel to each step, not deferred to the end
```

---

## 7. Risks

| # | Risk | Real, or hypothetical? | Mitigation |
|---|---|---|---|
| 1 | Gate Plan's `from mirai.core import ...` vs actual `from core import ...` | **Real** — confirmed doc/code mismatch via `tests/_bootstrap.py` | Use `from core import ...` (matches existing convention); note the doc typo to Manuel, don't invent a `mirai.core` re-export shim to paper over it. |
| 2 | `demo_scene.py` imports the experiment fork's `Scene`, not `core.Scene` | **Real** — confirmed by reading the file | Don't copy verbatim; write a small production equivalent against `core.Scene`/`core.Mesh` directly (§3.2). |
| 3 | Gate-3 `dispatch_command`/`window.py` losing drag-to-move vs current experiment behavior | **Real**, but intentional per Gate Plan's own task split (§4) | Documented explicitly above so it isn't mistaken for a regression during Gate 3 review; Gate 4 restores it. |
| 4 | `src/core/move.py` dead duplicate could get imported by accident during Gate 3 work | Low — nothing in my file list imports it | Left untouched, flagged, not acted on without Manuel. |
| 5 | Formal Q1 decision doc missing before merge to `main` | Process risk, not technical | Build the promoted files now (content is settled); flag the missing doc so it isn't forgotten before Gate 12 merge. |

No risk here is about whether the extraction is *technically* feasible — Q2 in `WP-04_OPEN_QUESTIONS.md` already established that (and my read of `app.py` confirms it), so I haven't re-litigated that question.

---

## 8. Gate 3 Implementation Order (what I'll actually build, in sequence)

1. Core promotion: `transform.py`, both `__init__.py` exports, migrated tests → run full core suite, confirm still green.
2. `src/mirai/` skeleton directories + empty `__init__.py`s.
3. Straight-copy files (§3.1) with their import fixups, one at a time, each with its migrated test file, confirmed passing before moving to the next.
4. `viewport/render.py` + its new tests.
5. `application.py` (incl. the small `init_scene` cube builder) + `test_application.py` + `test_smoke.py`.
6. `viewport/window.py` + `main.py` — manual run (`python src/main.py`) to confirm a window opens or an accepted stub windowing failure (sandbox may not have a display; if so, I'll say so rather than claim I verified it).
7. Final full-suite run, coverage check, PR description noting the two flagged-not-fixed items (§1.3, §7-1).

---

## Awaiting GO

Per the brief (§18, §21): I'm stopping here. No files have been created in `src/` or `tests/` yet — everything above is the plan only. Waiting for confirmation before I start writing actual code.
