# Artist Playground — Architecture Map

**Status:** Analysis (pre-implementation)
**Date:** 2026-09-10
**Purpose:** Classify every relevant building block for the Artist Playground.

This document records the current repository state as a starting point for the Artist Playground initiative. It is intentionally an analysis, not an implementation plan.

---

## Classification Legend

| Symbol | Meaning |
|--------|---------|
| 🟢 REUSE | Directly usable in the Playground as-is |
| 🟡 ADAPT | Usable with minor extraction or adjustment |
| 🔵 WRAP | Connect via adapter — Production system stays untouched |
| 🔴 MISSING | New Playground infrastructure required |
| ⚫ OUT | Not relevant for the Playground |
| 🏭 PRODUCTION | Stable production code — must not be changed experimentally |

---

## Pillar 1: Viewport

### 🏭 Production Viewport (`src/viewport/`)

**What:** GPU resource management with Dirty-State / Incremental-Update architecture (v0.2). Core: `render_mesh.py`, `resource_store.py`, `overlay.py`, `derived.py`. ~1,300 LOC.

**Relevant because:** The only complete renderer in the repository that works with the Production Mesh.

**Dependencies:** `src/core/` (Mesh/Selection), duck-typed Camera.

**Status:** Gate 5/7 verified, stable.

**Classification:** 🔵 WRAP

**Reason:** The Playground will test renderer variants (shading modes, debug overlays). This is done via a `PlaygroundRenderer` adapter that delegates to the Production Viewport — without touching `src/viewport/` itself.

---

### 🟢 OrbitCamera (`src/mirai/viewport/camera.py`)

**What:** Yaw/Pitch/Distance orbit, FOV, `screen_to_ray()`, `project_to_screen()`, `build_view_matrix/projection_matrix()`. ~223 LOC.

**Dependencies:** `vecmath.py` only. No pyglet.

**Status:** Headless-testable, stable, Gate 7 bound.

**Classification:** 🟢 REUSE

**Reason:** Fully self-contained, no GL state. Runs directly as the Playground camera. Camera revision counter fits well with Dirty-State tracking.

---

### 🟢 Picking (`src/mirai/viewport/picking.py`)

**What:** Headless picking without GPU (vertex / edge / face). ~113 LOC.

**Dependencies:** `vecmath.py`, `src/core/`.

**Status:** Headless, stable, live-tested in Integration Lab.

**Classification:** 🟢 REUSE

**Reason:** No GL, no pyglet. Directly usable. Baseline for a later GPU-picking variant (which would then become a WRAP candidate).

---

### 🔴 MISSING: Playground Window / GL Host

**What is missing:** A lightweight pyglet window specifically for the Playground — not a production window, but a neutral, configurable environment with an Experiment Slot concept.

**Why:** The Integration Lab `run.py` is too specific (fixed Cube + Head scene). The Playground needs a neutral host.

**Reference:** Integration Lab `lab_viewport.py` as inspiration (not as source to copy directly).

---

## Pillar 2: Interaction

### 🟢 Input System (`src/mirai/interaction/input.py` + `bindings.py`)

**What:** Headless Input abstraction (no pyglet), BindingSet (Input → Command mapping), `build_default_bindings()`, JSON override via `keymap.json`. ~430 LOC.

**Dependencies:** None external.

**Status:** Headless-testable, stable, own test suite.

**Classification:** 🟢 REUSE

**Reason:** Exactly the right abstraction level for the Playground. New bindings can be tested via JSON override — ideal for experiment iteration.

---

### 🔵 Tool System (`src/mirai/interaction/tool.py` + `tool_manager.py`)

**What:** Tool lifecycle state machine (IDLE → ACTIVE → INTERACTING), registry, automatic cancel() on tool switch. ~307 LOC.

**Dependencies:** `commands.py`.

**Status:** Stable, own test suite (lifecycle / manager / integration).

**Classification:** 🔵 WRAP

**Reason:** The system is solid, but the Playground wants to test new tool variants (modal editing, lasso select, paint select). New tools register with the existing `ToolManager` — Production routing (`routing.py`) is not changed. The Playground builds its own `PlaygroundToolRouter` alongside.

---

### 🟢 Commands (`src/mirai/interaction/commands.py`)

**What:** Named user commands as string constants. ~58 LOC.

**Classification:** 🟢 REUSE

**Reason:** Command strings are neutral. The Playground can add its own commands without changing existing ones.

---

### 🔵 Concrete Tools: Move / Rotate / Scale (`src/mirai/tools/`)

**What:** Transform tools on Production Operation base. ~400 LOC.

**Classification:** 🔵 WRAP

**Reason:** These tools work — but the Playground may want Move variants (axis constraint, soft selection influence). Playground-specific tool classes can reuse the Production Operations without replacing the Production tools themselves.

---

### 🔴 MISSING: Select Tools

**What is missing:** Interactive selection tools are completely absent from both Production and Playground. `src/core/selection.py` manages selection *state* (which elements are selected), but there is no interactive tool that connects a Picking hit to `core.selection.set_selection()`.

**Playground relevance:** High. Box-Select, Lasso, Paint-Select, Toggle — exactly what the Playground is intended to research. This is the most important open research question.

---

### 🔴 MISSING: Playground Experiment Slot System

**What is missing:** A minimal mechanism to define experiment variants, switch between them, and record a decision (KEEP / ITERATE / REJECT).

**Why:** Without this, the result is the `final_REAL2/` folder pattern.

**Scope:** Deliberately minimal — see Roadmap.

---

## Pillar 3: Core / Mesh

### 🏭 Core (`src/core/`)

**What:** Frozen domain truth — Mesh, Selection, History, Operations, IDs. ~1,458 LOC.

**Architecture contracts:** AD-001 (Stable IDs), AD-002 (Ordered Boundaries), AD-003 (Operation Lifecycle).

**Status:** V1 Freeze, own test suite (100+ contract checks).

**Classification:** 🏭 PRODUCTION

**Rule:** No experiment touches `src/core/`. The Playground operates exclusively through the public API (queries + operations). Non-negotiable.

---

### 🔵 Application (`src/mirai/application.py`)

**What:** Window-free orchestrator (Scene / Selection / History / Tools / Input). ~141 LOC.

**Classification:** 🔵 WRAP

**Reason:** `Application` is a good starting point, but the Playground wants to control its own orchestration (multiple scenes, experiment switching). A `PlaygroundApp` wrapping `Application` — or a lighter variant without the Production routing logic.

---

### 🟢 Cube

**What:** Created programmatically via `application.init_scene("cube")`. No separate asset.

**Classification:** 🟢 REUSE

**Reason:** Available immediately, no dependencies.

---

### 🟢 Head Basemesh (`experiments/rigging-skinning-morphing/meshes/head_basemesh.obj`)

**What:** 44.8 KB OBJ, Blender export, quad-dominant topology.

**Adapter:** Integration Lab `adapters/obj_to_core.py` (OBJ → core.Scene).

**Classification:** 🟢 REUSE (asset) + 🟢 REUSE (adapter)

**Reason:** Already tested with Production Viewport in the Integration Lab. Perfect Playground asset for realistic tool tests.

---

## Pillar 4: HUD / Feedback

### 🟡 HUD (Integration Lab `integration/lab_viewport.py`)

**What:** Text labels for camera state, object info, debug output via pyglet `text.Label`.

**Known constraints (from WP-IL-01):**
- `\n` without `multiline=True` → invisible
- `program.stop()` required before `Label.draw()`
- `width` must be set when `multiline=True`

**Status:** Works in the Lab, but embedded in `lab_viewport.py` (not standalone).

**Classification:** 🟡 ADAPT

**Reason:** HUD logic is useful but needs to be extracted as a standalone class. The Playground needs a configurable `PlaygroundHUD` (which information is displayed, debug level, etc.).

---

### 🔴 MISSING: Experiment Status Display

**What is missing:** Visual display in the window showing which experiment / variant is currently active — basis for the Artist Feedback loop.

---

## Pillar 5: Test Infrastructure

### 🏭 Production Test Suite (`tests/`)

**What:** 28 files, 5,462 LOC — contract tests for Core, Camera, Tools, Viewport, Application.

**Classification:** 🏭 PRODUCTION

**Rule:** These tests must remain green after every Playground session. No experiment may break them.

---

### 🟢 Integration Lab Tests (`experiments/mirai_bastel_integration_lab/tests/`)

**What:** 52 headless tests for OBJ loading, Core binding, Viewport adapter, Picking.

**Classification:** 🟢 REUSE

**Reason:** Excellent template for Playground tests. The pattern (adapter test without GL) is exactly right.

---

### 🔴 MISSING: Playground Test Harness

**What is missing:** A test harness specifically for Playground experiments — not production contract tests, but quick behavioral checks for experiment variants.

---

## Experiment Structures

### 🟡 Integration Lab (`experiments/mirai_bastel_integration_lab/`)

**What:** First working interactive environment with Production Camera + Viewport. ~1,200 LOC lab-specific.

**Status:** Gate 7 verified, stable.

**Classification:** 🟡 ADAPT

**Reason:** The Lab is too specific for its current purpose (fixed Cube + Head, fixed scene). But its adapter structure (`adapters/`) is excellent and should be adopted for the Playground. The Lab stays as a reference implementation.

---

### ⚫ Viewport V1 (`experiments/mirai_bastel_viewport_V1/`)

**Classification:** ⚫ OUT (structure) — `topology_tools.py` is valuable reference for later topology phases.

**Reason:** V1 viewport system is superseded by Production. Topology tool logic remains useful reference for Phase 4/5 of the Topology roadmap.

---

### ⚫ Viewport V02 (`experiments/mirai_bastel_viewport_V02/`)

**Classification:** ⚫ OUT

**Reason:** Purpose fulfilled. Production `src/viewport/` is the canonical version.

---

### ⚫ Core V1 (`experiments/mirai_bastel_core_V1/`)

**Classification:** ⚫ OUT — archive copy.

---

### ⚫ Rigging / Skinning / Morphing (`experiments/rigging-skinning-morphing/`)

**Classification:** ⚫ OUT (deformation code) / 🟢 REUSE (OBJ loader + Head Basemesh asset)

---

### ⚫ Topology Experiments (`experiments/topology/`)

**Classification:** ⚫ OUT for Playground V1 — relevant later for WP-AP-05.

---

## Summary

```
ARTIST PLAYGROUND
       │
       ├── VIEWPORT
       │      ├── 🟢 OrbitCamera              ← ready now
       │      ├── 🟢 Picking (headless)        ← ready now
       │      ├── 🔵 Production Viewport       ← adapter needed
       │      └── 🔴 Playground Window         ← new build
       │
       ├── INTERACTION
       │      ├── 🟢 Input System              ← ready now
       │      ├── 🟢 Commands                  ← ready now
       │      ├── 🔵 Tool System               ← Playground router needed
       │      ├── 🔵 Move / Rotate / Scale     ← usable as base
       │      └── 🔴 Select Tools              ← new build (core research)
       │
       ├── MESH / SCENE
       │      ├── 🏭 Core                      ← API only, never change
       │      ├── 🟢 Cube                      ← ready now
       │      ├── 🟢 Head Basemesh + OBJ       ← ready now
       │      └── 🔵 Application               ← PlaygroundApp alongside
       │
       ├── HUD / FEEDBACK
       │      ├── 🟡 HUD                       ← extract to PlaygroundHUD
       │      └── 🔴 Experiment Status Display ← new build
       │
       ├── EXPERIMENT INFRASTRUCTURE
       │      └── 🔴 Slot / Variant / Decision ← new build (anti-chaos)
       │
       └── TESTS
              ├── 🏭 Production Suite          ← always green
              ├── 🟢 Lab Test Pattern          ← use as template
              └── 🔴 Playground Test Harness   ← new build
```

### What the Playground has inherited well

- Solid, headless-testable foundation (Core, Camera, Picking, Input)
- A verified rendering path (Integration Lab → Production Viewport)
- A clear adapter pattern (Integration Lab demonstrates how)

### What is still completely missing

1. **Select Tools** — the most important research question for the Playground: *How should selection feel?*
2. **Playground Window** — neutral GL host without a fixed scene
3. **Experiment Slot System** — structure against `final_REAL2/` chaos (deliberately minimal)
4. **PlaygroundHUD** — Artist feedback loop

### What is superseded / no longer relevant

- V1 / V02 experiment structures (purpose fulfilled, moved to Production)
- Core V1 (archived)
- Rigging / deformation code (except OBJ loader + asset)
