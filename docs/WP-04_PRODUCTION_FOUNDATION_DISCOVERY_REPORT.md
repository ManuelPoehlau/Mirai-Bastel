# WP-04 — Production Foundation Discovery & Analysis Report

**Status:** Complete Repository Analysis  
**Date:** 2026-09-01  
**Branch:** `wp/04-production-foundation`  
**Analyst Role:** Architecture & Repository Analyst (Read-only, no code changes)

---

## Executive Summary

**GO for WP-04 implementation** — the repository contains sufficient, production-ready components from WP-01A/02/03 to begin deriving the first autonomous Production Application.

### Key Findings

| Component | Status | Production-Ready |
|-----------|--------|------------------|
| Core V1 (src/core) | FROZEN | ✓ Yes (hardened, tested, reviewed) |
| Viewport V1 (experiments) | Complete Experiment | ✓ Yes (concepts validated) |
| Interaction Contract | Implemented & Tested | ✓ Yes (88/88 tests pass) |
| Input/Binding System | Complete | ✓ Yes (JSON-configurable) |
| Tool Framework | Complete | ✓ Yes (3-state lifecycle enforced) |
| Command Routing | Complete | ✓ Yes (minimal, extensible) |
| Move Tool (WP-02) | Reference Implementation | ✓ Yes (pattern-setting) |
| Transform Tools (WP-03) | Reference Implementation | ✓ Yes (Rotate/Scale validated) |
| Topology Lab | Experiment | ⚠ Ready for research, not production boundary yet |
| Production Application Entry Point | **MISSING** | ✗ No (need to derive from experiments) |

---

## 1. Repository Overview

### Directory Structure

```
src/
├── core/               # ✓ FROZEN Production Core V1
│   ├── ids.py
│   ├── history.py
│   ├── mesh.py
│   ├── selection.py
│   ├── scene.py
│   ├── operation.py
│   ├── serialization.py
│   └── operations/
│       ├── move.py     (reference only)
│       └── topology.py (atomic topol. mutations)
│
experiments/
├── mirai_bastel_core_V1/     # Experiment fork (WP-01, 02, 03 development)
│   ├── mirai_bastel_core/
│   │   ├── operations/
│   │   │   ├── move.py
│   │   │   ├── transform.py  (WP-03 Foundation)
│   │   │   └── topology.py
│   │   └── ...
│   └── tests/
│
├── mirai_bastel_viewport_V1/ # ✓ Complete Interaction Experiment
│   ├── viewport/
│   │   ├── app.py            (monolithic harness, 582 lines)
│   │   ├── tool.py           (✓ production-ready base class)
│   │   ├── move_tool.py      (✓ reference implementation, WP-02)
│   │   ├── transform_tool.py (✓ reference implementation, WP-03)
│   │   ├── input_binding.py  (✓ production-ready binding system)
│   │   ├── commands.py       (simple enum of command names)
│   │   ├── default_bindings.py
│   │   ├── camera.py
│   │   ├── picking.py
│   │   ├── display_state.py
│   │   ├── demo_scene.py
│   │   ├── constraints.py    (axis constraints for tools)
│   │   ├── vecmath.py        (vector utilities)
│   │   ├── topology_app.py   (topology lab harness)
│   │   ├── topology_tools.py (loop/ring selection)
│   │   └── ...
│   ├── tests/                (88/88 passing)
│   ├── run.py, run_topology.py, run_cylinder.py
│   └── README.md
│
├── rigging-skinning-morphing/ # Parallel research track
│
└── topology/                  # Topology research (now integrated into Viewport V1)
```

### Tests & Validation

- **Viewport V1 Test Suite:** 88/88 unittest passing (WP-01A/02/03 regressions + new tests)
- **Production Core Suite:** 29/29 unittest + architecture contracts PASS
- **Test Coverage:** input binding, tool lifecycle, move/transform operations, topology, picking, display, integration

---

## 2. Current Production State

### What Is Production (src/core)

**Status: FROZEN V1** (see `docs/architecture/CORE_V1_FREEZE.md`)

Hardened through 5 phases (A–E):
- **Phase A:** Mesh invariants (edge/face adjacency, no self-loops, no duplicate vertices in face boundaries)
- **Phase B:** Topology operations (split_edge, collapse_edge, connect_vertices in boundary/interior/fan scenarios)
- **Phase C:** Identity continuity (complete pre/post ID diffs for mutation tracking)
- **Phase D:** Undo/Redo (snapshot-based history via `MeshStateCommand`)
- **Phase E:** Serialization (Scene + Mesh roundtripping with reserved subsystem slots for morph/rig/animation)

**What Core V1 provides:**

```python
Scene
├── Mesh              (frozen topology container)
│   ├── Vertex + Position
│   ├── Edge + Topology
│   └── Face + Boundary
├── Selection         (independent UI state)
├── History           (generic command stack)
└── Morph/Rig/Animation (reserved, currently None)
```

**Explicitly frozen OUT (will not be added to Core V1):**
- Half-Edge/Winged-Edge refactoring
- Generalized change-set/provenance system
- Soft selection / influence kernel
- Morph remapping on topology change
- Plugin/extension framework
- Any UI/Viewport/Renderer dependency

### What Is Complete But Not Yet Production Boundary

**Status: Ready to Derive** (see `docs/architecture/SOURCE_ARCHITECTURE.md`)

From the Viewport V1 experiment, **proven working:**

1. **Input-Binding System** (`input_binding.py`)
   - Physical Input (key/mouse/wheel + modifiers)
   - Two-tier bindings (default + user override from keymap.json)
   - Context-hierarchical resolution (specific context → global context)
   - JSON-serializable
   - Pyglet-free (only dependency: window adapters)

2. **Command System** (`commands.py`, `default_bindings.py`)
   - Simple enum of command names (Move, Rotate, Scale, Undo, Redo, Pan, Orbit, ToggleWireframe, etc.)
   - No hard-coded input mapping
   - Extensible via new command strings + routing

3. **Tool Framework** (`tool.py`)
   - 3-state lifecycle: IDLE → ACTIVE → INTERACTING → ACTIVE → IDLE
   - State guards enforced (e.g., `update()` only in INTERACTING)
   - Subclasses implement only `_on_*` hooks (not lifecycle methods)
   - History-grenze solely in `commit()` (never in `update()`)
   - 185 lines, production-grade quality

4. **Tool Implementations** (`move_tool.py`, `transform_tool.py`)
   - **MoveTool** (WP-02 reference)
     - Activates on `Command.Move`
     - Resolves selection (V/E/F) → affected vertex IDs
     - Snapshot-based history via `MoveOperation.commit()`
     - Cancel restores exact prior state
   - **RotateTool** + **ScaleTool** (WP-03 reference)
     - Same lifecycle pattern
     - Fixed pivot (selection centroid)
     - Rodrigues rotation + uniform/constrained scaling
     - Chunking-independent delta-to-step calculation

5. **Viewport Components** (camera, picking, display)
   - **Camera:** orbit, pan, zoom with screen-to-world delta translation
   - **Picking:** ray-cast 3D selection from screen coordinates
   - **Display State:** mode tracking (Shaded/Flat/Wireframe) + wireframe overlay toggle
   - **Constraints:** axis-restricted transform parameters

6. **Selection Topology** (`loop_ring.py`, `topology_tools.py`)
   - Edge loop detection (conservative: quads only, valence-4 vertices)
   - Edge ring detection
   - Selection wrappers for querying
   - 23 unit tests, all green

### Core V1 Dependencies from Viewport (what production needs from Core)

```python
# What production app calls from Core
from mirai_bastel_core import (
    Scene, Mesh, Selection, SelectionMode,
    VertexId, EdgeId, FaceId,
    MoveOperation, OperationContext,
    HistoryStack,  # for UI undo/redo
    # Future:
    # RotateOperation, ScaleOperation  (when promoted from experiment)
)
```

---

## 3. WP-01/02/03 Dependency Chain

### WP-01A: Viewport & Input Foundation

**Scope:** Establish input/command/binding contract  
**Completed:** ✓  
**Status in Repository:**
- Input mapping logic: `input_binding.py` ✓
- Default keybindings: `default_bindings.py` ✓  
- Command enum: `commands.py` ✓
- Display modes: `display_state.py` ✓
- Camera navigation: `camera.py` ✓
- Picking: `picking.py` ✓
- Selection UI state: `selection.py` (in Core, used by viewport) ✓
- Tests: test_input_binding, test_display_state, test_camera_picking ✓

**Deliverable:** INPUT_COMMAND_TOOL_CONTRACT.md (architecture), fully implemented

---

### WP-02: Interaction & Tool Framework

**Scope:** Tool lifecycle, command → tool routing, Move as reference  
**Completed:** ✓  
**Status in Repository:**
- Tool base class: `tool.py` ✓
- MoveTool reference impl: `move_tool.py` ✓
- Tool-to-command routing: `tool_for_command()` in move_tool.py ✓
- Integration with viewport event loop: `app.py` (experimental harness, not production) ⚠
- Tests: test_move_tool, test_tool_lifecycle, test_tool_integration, test_tool_routing ✓
- 88/88 passing including WP-02 + WP-01A regressions

**Deliverable:** Proven tool framework, Move as pattern-setting reference

---

### WP-03: Transform Foundation

**Scope:** Rotate & Scale tools using same lifecycle as Move  
**Completed:** ✓  
**Status in Repository:**
- RotateOperation, ScaleOperation: `experiments/mirai_bastel_core_V1/operations/transform.py` (experiment fork, **not in src/core**)
- RotateTool, ScaleTool: `viewport/transform_tool.py` ✓
- Constraints framework: `constraints.py` (foundation for axis-restricted ops) ✓
- Tests: test_transform_operations, test_transform_tools, test_transform_integration ✓
- 19 transform-specific tests + 25 tool tests ✓

**Status Note:** WP-03-Implementierung liegt noch im Experiment-Fork wegen der beabsichtigten Phase-Ableitung (wie beim Connect-Edges-Experiment). **Die Promotion nach src/ ist eine explizite WP-04-Entscheidung**, nicht automatisch.

**Deliverable:** Proven transform interaction, reference implementation for future tool patterns

---

### Dependency Map

```
Core V1 (FROZEN)
    ↓ (no deps on anything above)
    
WP-01A (Input/Binding/Display)
    ↓ (uses Core)
    
WP-02 (Tool Framework + Move)
    ↓ (uses WP-01A, Core)
    
WP-03 (Transform Tools)
    ↓ (uses WP-02, Core)
    
WP-04 (Production Application Foundation)
    ↑ (needs to integrate WP-01/02/03 + Core into src/)
```

---

## 4. Production vs Experiment Classification

### A — Production-Ready (Promote Immediately to src/)

| Component | Rationale | Files |
|-----------|-----------|-------|
| **Tool base class** | 3-state lifecycle, state guards, zero magic | `viewport/tool.py` |
| **Input/Binding system** | JSON-serializable, context-hierarchical, minimal | `viewport/input_binding.py` |
| **Command enum** | Simple, extensible | `viewport/commands.py` |
| **MoveTool reference** | Proven pattern for all future tools | `viewport/move_tool.py` |
| **Camera (Orbit/Pan/Zoom)** | Practical validation in experiment | `viewport/camera.py` |
| **Picking (ray-cast)** | Simple, effective | `viewport/picking.py` |
| **Display state tracking** | Minimal state machine | `viewport/display_state.py` |
| **Input → Command → Tool → Operation → History** | Full pipeline proven, 88 tests | all of above |

### B — Validated Concept (Refine & Promote)

| Component | Rationale | Status |
|-----------|-----------|--------|
| **RotateOperation / ScaleOperation** | Tested in experiment fork, not yet in src/core | Need explicit architecture review before promotion (AD-001/Freeze concern?) |
| **RotateTool / ScaleTool** | Reference implementations working, follow Move pattern | Ready once Rotate/Scale ops promoted |
| **Topology loop/ring selection** | 23 tests passing, can integrate | Ready for experimental integration, not production UI yet |
| **Viewport monolithic event loop (app.py)** | Proves concept, but 582 lines need restructuring | Extract reusable patterns (dispatch, state, frame loop) |

### C — Experiment Only (Leave as Reference)

| Component | Rationale | Location |
|-----------|-----------|----------|
| **Topology lab (topology_app.py)** | Specialized keybindings + context switching, research tool | experiments/mirai_bastel_viewport_V1/viewport/ |
| **Demo scene (demo_scene.py)** | Test data, not production asset pipeline | experiments/mirai_bastel_viewport_V1/viewport/ |
| **Cylinder scene (run_cylinder.py)** | Test harness | experiments/mirai_bastel_viewport_V1/ |
| **Entry point harnesses (run.py, etc)** | Pyglet-specific window glue, not architecture | experiments/mirai_bastel_viewport_V1/ |
| **Rigging-skinning-morphing experiments** | Parallel research track, not WP-04 input | experiments/rigging-skinning-morphing/ |

---

## 5. Entry Point Analysis

### Current Entry Points (All Experiments)

```python
# experiments/mirai_bastel_viewport_V1/run.py
def main():
    window = ModelerWindow()
    pyglet.app.run()

# experiments/mirai_bastel_viewport_V1/run_topology.py
def main():
    window = ModelerWindow(init_mode=...)
    pyglet.app.run()

# experiments/mirai_bastel_viewport_V1/_smoke_wp01a.py
# Minimal WP-01A validation (headless window tests)
```

### What app.py (ModelerWindow) does

**Responsibility:** Single pyglet.window.Window subclass handling:
- Scene initialization
- Geometry rendering (vertex/edge/face rendering)
- Event dispatch (mouse, keyboard, window)
- Tool lifecycle management
- Input → Binding → Command → Tool → Operation flow
- Camera state
- Selection visualization

**Why it needs restructuring:**
- **582 lines in one class** — mixing concerns (event handling, rendering, scene state, tool manager, input dispatch)
- **Pyglet hard-coded** — tight coupling to window framework
- **No production application layer** — window IS the application
- **Monolithic event dispatch** — mixing navigation, tool interaction, selection, UI state

### Production Entry Point Requirements

A **Production Application** must separate:

```
Application Boundary
    ├── Lifecycle (init, main loop, shutdown)
    ├── Scene/Document management
    ├── Window/Viewport management (should be swappable)
    ├── Input dispatch (keyboard, mouse)
    ├── Command routing (global + context-specific)
    ├── Tool manager (active tool, state)
    ├── Selection visualization
    ├── Display modes
    └── Undo/Redo UI integration

Where each layer is testable independently from Pyglet/Window specifics.
```

---

## 6. Proposed Production Boundary

### Phase 1: Minimal Production Application

```
src/
└── mirai/
    ├── __init__.py
    ├── core/                    # UNCHANGED (link to src/core)
    │
    ├── application.py           # NEW: Application lifecycle
    │   └── class Application
    │       ├── init_scene()
    │       ├── dispatch_command(name, context=None)
    │       ├── update_viewport()
    │       └── shutdown()
    │
    ├── viewport/                # NEW: Extracted from experiment
    │   ├── __init__.py
    │   ├── camera.py           # MOVE: from experiments
    │   ├── picking.py          # MOVE: from experiments
    │   ├── display.py          # MOVE: from experiments (display_state.py)
    │   ├── render.py           # NEW: geometric rendering (from app.py)
    │   └── window.py           # NEW: Pyglet Window adapter (minimal)
    │
    ├── interaction/             # NEW: Extracted from experiment
    │   ├── __init__.py
    │   ├── input.py            # MOVE: input_binding.py
    │   ├── commands.py         # MOVE: commands.py
    │   ├── bindings.py         # MOVE: default_bindings.py
    │   ├── tool.py             # MOVE: tool.py
    │   └── tools/              # NEW: Tool implementations
    │       ├── __init__.py
    │       ├── move.py         # MOVE: move_tool.py
    │       ├── rotate.py       # MOVE+ADAPT: transform_tool.py RotateTool
    │       └── scale.py        # MOVE+ADAPT: transform_tool.py ScaleTool
    │
    └── main.py                  # NEW: Entry point (Pyglet harness)
```

### Phase 2: Extensibility Hooks (for future features)

```
src/mirai/
├── topology/                    # Placeholder for topology-specific tools
│   ├── __init__.py
│   └── selection.py            # loop_ring.py integration path
│
└── future/
    ├── transform/              # Transform constraints, gizmos
    ├── properties/             # Property UI framework (not WP-04)
    ├── scene/                  # Object/component model (not WP-04)
    └── ...
```

---

## 7. Core V1 Dependency Analysis

### Does Core V1 Suffice for WP-04?

**YES** — no Core changes required.

### Why?

**Operations contract is sufficient:**
```python
# Core already provides:
Operation.begin()      # Setup live state
Operation.update()     # Apply delta
Operation.commit()     # Atomize to history
Operation.cancel()     # Restore prior state

# This contract works for Move/Rotate/Scale without modification.
```

### Potential Future Core Extensions (documented for later gates)

These would be **separate WP** decisions, not WP-04 blockers:

1. **Generic Provenance/Change-Set** (ARCH-02 gate)
   - When morphs/skins need remapping on topology change
   - Not needed for WP-04 (transform only, no topology mutation)

2. **Object/Component Model** (ARCH-01 gate)
   - When multiple objects or hierarchies are needed
   - WP-04 scope: single mesh in single scene only

3. **Transform Constraints** (future, optional)
   - `operation.apply_constraint("x_only")` etc.
   - WP-04 can solve via tool parameters instead

---

## 8. WP-04 Scope Mapping

### IN SCOPE ✓

**Application Foundation**
- [ ] Production entry point (main.py)
- [ ] Application lifecycle (init, main loop, shutdown)
- [ ] Scene/document loading
- [ ] Window management (minimal Pyglet adapter)
- [ ] Basic scene initialization (cube or grid)

**Viewport Foundation**
- [ ] Camera (orbit, pan, zoom around scene center)
- [ ] Rendering (vertex/edge/face display, shaded/flat/wireframe modes)
- [ ] Selection visualization (highlighted elements)
- [ ] Picking (ray-cast screen → 3D)
- [ ] Multiple orthographic views (Front/Back/Left/Right/Top/Bottom as future extension)

**Interaction Foundation**
- [ ] Input mapping (keyboard, mouse, wheel + modifiers)
- [ ] Context-based command routing
- [ ] Default keybindings (Vertex/Edge/Face mode, Move/Rotate/Scale, Undo/Redo)
- [ ] Configurable bindings (keymap.json)

**Tools Foundation**
- [ ] Tool lifecycle management (ToolManager)
- [ ] Move tool (reference WP-02)
- [ ] Rotate tool (WP-03, requires ops promotion)
- [ ] Scale tool (WP-03, requires ops promotion)
- [ ] Tool activation/deactivation
- [ ] Tool preview/commit/cancel

**Selection Foundation**
- [ ] V/E/F selection modes
- [ ] Click-to-select interaction
- [ ] Hover indication
- [ ] Selection-to-vertex resolution (V/E/F → affected vertices)
- [ ] Undo/Redo integration (selection NOT in history)

**Transform Foundation**
- [ ] Move with live preview + commit
- [ ] Rotate around selection pivot + commit
- [ ] Scale around selection pivot + commit
- [ ] Axis constraints (future: interactive hotkeys; WP-04: tool parameters)
- [ ] Cancel (Esc) restores exact state

**History Foundation**
- [ ] Undo/Redo stack (from Core)
- [ ] One history entry per completed tool interaction
- [ ] Selection changes NOT in history
- [ ] Ctrl+Z / Ctrl+Y bindings

### OUT OF SCOPE ✗

**These belong to future WP:**
- [ ] Extrude, Inset, Bevel, Loop Insert, Subdivide, Bridge (topology ops beyond Core support)
- [ ] Snapping, grid, constraints UI
- [ ] Gizmos (3D transform handles)
- [ ] Materials, shading, UV editing
- [ ] Animation, keyframes
- [ ] Rigging, bones, deformation
- [ ] Morphs, blend shapes
- [ ] Multiple objects, object hierarchies, transforms
- [ ] Properties panel, outliner, scene tree
- [ ] Full preferences UI (minimal keymap.json suffices)
- [ ] Plugins, extensions
- [ ] Import/export (beyond JSON save/load)

---

## 9. Risks

### HIGH Priority

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **No Production Entry Point Exists** | Cannot start application without writing new code | Create minimal main.py + Application class first (Gate 3) |
| **app.py is Monolithic (582 lines)** | Impossible to unit-test window-free; hard to refactor | Extract Tool, Input, Camera, Rendering into separate modules during Gate 3 |
| **Core V1 freeze blocks Transform Ops promotion** | Can't use RotateOperation/ScaleOperation in production yet | Explicit promotion review needed before Gate 3; clarify if they count as Core or Experiment |
| **Viewport components tightly coupled to Pyglet** | Hard to test or adapt later; window events scattered | Introduce thin Input adapter layer; keep Binding/Command/Tool/Operation window-free |
| **No documented Production Boundaries** | Unclear what belongs in src/ vs experiments/ | WP-04 Gate 2 (this phase) establishes boundaries; document in SOURCE_ARCHITECTURE.md update |

### MEDIUM Priority

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Experiment fork has Transform ops but src/core frozen** | Confusion about what's production vs research | Decision in Gate 2: promote ops or keep in experiment? Doc explicitly |
| **Topology tools (loop/ring) not yet production-qualified** | Cannot use for general modeling yet | Gate 2: acknowledge as research, not production UI scope |
| **No multi-view support** | Only single perspective viewport in WP-04 | Accepted scope limit; ortho views deferred to future |
| **No transform gizmos or interactive constraints** | UX feels incomplete vs. Blender/Wings3D | By design: pivot+delta interaction proven; gizmos future enhancement |
| **Selection behavior TBD on tool activation** | Does M-Move clear selection? Does Esc return to tweak mode? | Already documented in Viewport V1 README; formalize as WP-04 requirement |
| **History does not track selection changes** | Clicking to select produces no undo entry | By design (matches Mirai); needs UI explanation |

### LOW Priority

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **No asset loading pipeline** | Demo scene hardcoded or minimal | WP-04 suffices with procedural cube/grid; file I/O deferred |
| **No real-time viewport performance tuning** | Complex models might redraw slowly | V1 simple enough; optimization deferred to later WP |
| **Keymap.json errors not validated** | Malformed bindings silently ignored | Add minimal JSON schema validation in WP-04 Gate 3 |
| **Vector math (vecmath.py) minimal** | Potential precision/stability questions | Already used in Viewport V1, tests pass; revisit if issues arise |

---

## 10. Recommended Implementation Sequence

### Gate 2: Repository Analysis & Architecture Review ✓ CURRENT

**Objective:** Establish WP-04 production boundaries  
**Deliverables:**
- [x] This discovery report
- [x] Current state of Core V1 (frozen, validated)
- [x] Current state of WP-01A/02/03 (complete in experiment)
- [x] Production vs Experiment classification
- [x] Core V1 freeze implications
- [ ] (Next) Approval to proceed to Gate 3

---

### Gate 3: Application & Viewport Foundation

**Objective:** Extract and organize production-ready components from experiments  
**Duration:** ~3–4 work sessions  
**Key Tasks:**
1. Create `src/mirai/` directory structure
2. Extract tool.py, input_binding.py, commands.py → src/mirai/interaction/
3. Extract camera.py, picking.py, display_state.py → src/mirai/viewport/
4. Create Application class (init_scene, dispatch_command, update_viewport)
5. Create minimal main.py entry point (Pyglet window adapter)
6. Extract rendering logic from app.py into viewport/render.py
7. Create ToolManager class (activate/deactivate/begin/update/commit/cancel lifecycle)
8. Tests: at least 30 new unit tests for Application, ToolManager, command dispatch (no Pyglet dependency)
9. Smoke test: `python src/main.py` launches window with cube, M activates Move tool

**Acceptance Criteria:**
- [ ] All moved files run under src/ with same tests passing (88/88)
- [ ] Application can be instantiated without Pyglet window
- [ ] Command dispatch testable in isolation (no window dependency)
- [ ] Tool lifecycle testable in isolation
- [ ] Viewport rendering testable via mock (no window dependency)

---

### Gate 4: Interaction & Tools Integration

**Objective:** Wire Input→Binding→Command→Tool→Operation→History pipeline  
**Duration:** ~2 work sessions  
**Key Tasks:**
1. Create tools/ subpackage (move.py, rotate.py, scale.py)
2. Create tool_for_command() routing function
3. Create ToolManager integration with command dispatch
4. Adapt MoveTool from experiment (WP-02 reference)
5. Decision: Promote RotateOperation/ScaleOperation from experiment fork to src/core? (Architecture review)
6. If promoted: adapt RotateTool and ScaleTool from experiment
7. Integration tests: Input → Command → Tool activation → Operation → History
8. Tests: 20+ integration tests covering tool lifecycle, cancel/commit, undo/redo

**Acceptance Criteria:**
- [ ] M key activates move tool
- [ ] LMB drag moves selection (live preview)
- [ ] Release commits (exactly 1 history entry)
- [ ] Esc cancels (no history entry)
- [ ] Ctrl+Z undoes move
- [ ] Same for R (Rotate) and S (Scale) if ops promoted
- [ ] Tool can be dismissed with Esc or by selecting another tool

---

### Gate 5: Selection & Display Foundation

**Objective:** Integrate selection modes and viewport display  
**Duration:** ~2 work sessions  
**Key Tasks:**
1. Integrate Selection from Core
2. Implement selection mode toggle (V/E/F keys)
3. Implement selection visualization (highlighted edges/faces/vertices)
4. Implement hover indication
5. Implement selection-to-vertices resolution (resolve_selection_vertices)
6. Implement display modes (Shaded/Flat/Wireframe) toggle
7. Implement wireframe overlay toggle
8. Tests: 15+ tests for selection modes, visualization, resolution

**Acceptance Criteria:**
- [ ] V/E/F keys toggle selection mode
- [ ] Click on element selects/deselects
- [ ] Hovered element highlighted before click
- [ ] O key toggles display mode
- [ ] W key toggles wireframe overlay
- [ ] Move tool respects current selection mode (vertices of edges/faces)

---

### Gate 6: Input & Bindings Configuration

**Objective:** Stabilize input mapping, test keymap.json override  
**Duration:** ~1 work session  
**Key Tasks:**
1. Finalize default_bindings.py
2. Test keymap.json loading/override
3. Test context-based command resolution (global vs topology context)
4. Add JSON schema validation for keymap.json
5. Tests: 10+ tests for binding resolution, context priority, JSON serialization

**Acceptance Criteria:**
- [ ] keymap.json can override any default binding
- [ ] Invalid JSON is reported (not silently ignored)
- [ ] Context resolution works (topology context overrides global)
- [ ] Default bindings persist if keymap.json missing

---

### Gate 7: Camera & Viewport Navigation

**Objective:** Stabilize camera interaction (orbit, pan, zoom)  
**Duration:** ~1 work session  
**Key Tasks:**
1. Finalize camera implementation (orbit, pan, zoom)
2. Test screen-to-world delta translation
3. Verify navigation doesn't interfere with tools (RMB/MMB should cancel ongoing tool)
4. Tests: 10+ tests for camera math, screen delta, navigation

**Acceptance Criteria:**
- [ ] RMB drag orbits camera around scene center
- [ ] MMB drag pans (grab)
- [ ] Wheel zooms in/out
- [ ] Tool interaction (Move/Rotate/Scale) works with camera state

---

### Gate 8: Automated Validation

**Objective:** Full test coverage, headless validation  
**Duration:** ~1 work session  
**Key Tasks:**
1. Verify all 88 existing tests pass under src/ structure
2. Add 30+ new unit tests (Application, ToolManager, command dispatch, integration)
3. Add 20+ integration tests (full input→operation→history flow)
4. Headless smoke test (no window, just Scene + Application + sequence of commands)
5. Code review: no Pyglet imports outside of main.py/viewport/window.py

**Acceptance Criteria:**
- [ ] All tests pass (150+)
- [ ] Code coverage ≥ 85% for src/mirai/ (excluding main.py)
- [ ] No window-dependent tests (all headless)
- [ ] No circular dependencies
- [ ] All public APIs documented with docstrings

---

### Gate 9: Independent Review (AI)

**Objective:** Fresh architecture review from another AI instance  
**Duration:** ~1 work session  
**Key Tasks:**
1. Provide independent AI reviewer with:
   - This discovery report
   - All source files under src/mirai/
   - Test results + coverage report
   - Architecture decisions (INPUT_COMMAND_TOOL_CONTRACT, etc.)
2. Review checklist:
   - [ ] Production boundaries reasonable?
   - [ ] Dependencies clean?
   - [ ] Core V1 freeze respected?
   - [ ] Experiment patterns cleanly extracted?
   - [ ] Risks adequately mitigated?
   - [ ] Ready for human review?

**Acceptance Criteria:**
- [ ] Independent review identifies no architecture blockers
- [ ] Any gaps documented as future WP, not WP-04 scope creep

---

### Gate 10: Human E2E Test

**Objective:** Live application validation  
**Duration:** ~1 work session  
**Key Tasks:**
1. Launch application: `python src/main.py`
2. Manual test workflow:
   - [ ] Window opens with cube (or grid)
   - [ ] Vertex/Edge/Face selection works (V/E/F keys)
   - [ ] Click-to-select works
   - [ ] M key activates move tool
   - [ ] LMB drag moves selected vertices (live)
   - [ ] Release commits to history (1 entry)
   - [ ] Esc cancels (no history)
   - [ ] Ctrl+Z undoes move
   - [ ] Ctrl+Y redoes move
   - [ ] R key activates rotate (if promoted)
   - [ ] S key activates scale (if promoted)
   - [ ] Display mode toggle (O key) works
   - [ ] Wireframe toggle (W key) works
   - [ ] Camera navigation works (RMB, MMB, wheel)
   - [ ] keymap.json override works
3. Bug report & fix iteration

**Acceptance Criteria:**
- [ ] All manual tests pass
- [ ] No crashes or hangs
- [ ] Responsive interaction
- [ ] Clean shutdown

---

### Gate 11: Architecture Review & Approval

**Objective:** Final green light for merge to main  
**Duration:** ~1 work session  
**Key Tasks:**
1. Update canonical architecture docs:
   - [ ] SOURCE_ARCHITECTURE.md (add actual src/ structure)
   - [ ] ROADMAP.md (update WP-04 status to "Complete")
   - [ ] V1_SPEC.md (reference new Application layer)
2. Final risk review: any new blockers?
3. Decision: merge to main (wp/04-production-foundation → main)

**Acceptance Criteria:**
- [ ] All gates passed
- [ ] Documentation updated
- [ ] No merge conflicts
- [ ] Ready for WP-05 (next work package)

---

### Gate 12: Merge & Next WP Planning

**Objective:** Prepare for continued development  
**Duration:** ~1 work session  
**Key Tasks:**
1. Commit all changes to wp/04-production-foundation branch
2. Create PR summary for human review
3. Merge to main
4. Identify WP-05 focus (topology operations? Multi-view? Properties UI?)
5. Archive this discovery report and gate summaries in docs/

---

## 11. Open Questions for Gate 2 Review

**Q1: Transform Operations Promotion**  
*Decision needed before Gate 3.*

Currently, `RotateOperation` and `ScaleOperation` live in `experiments/mirai_bastel_core_V1/operations/transform.py`, not in `src/core/`.

- **Option A:** Promote to `src/core/operations/transform.py` (counts as Core V1 post-freeze extension)
  - Pro: Production app can use them
  - Con: Requires Core freeze review (AD-001 concerns?)
  
- **Option B:** Keep in experiment fork, extract tools only to production
  - Pro: Preserves Core freeze
  - Con: Tools duplicate operation logic

- **Recommendation:** **Option A** — the Core freeze is on NEW functionality that changes Core design, not on adding more Operations that use the existing Operation contract. Transform is proven, tested, follows the pattern. Move is the reference; Rotate/Scale use the same contract. This feels like filling the established pattern, not breaking the freeze.

**Q2: Viewport Restructuring**  
*Can we extract app.py cleanly without losing functionality?*

Currently, app.py is monolithic. We need:
- Rendering logic (vertex/edge/face triangulation)
- Event dispatch (on_key_press, on_mouse_drag, etc.)
- Window-free Application class

**Recommendation:** Extract rendering + tool/input logic; keep only event bridging in window.py.

**Q3: Multi-View (Future)**  
*Is single perspective camera sufficient for WP-04?*

Experiment has one camera. Mirai had Front/Back/Left/Right/Top/Bottom snapping views.

**Recommendation:** WP-04 scope: single perspective + orbit/pan/zoom. Ortho views → future WP.

**Q4: Undo/Redo UI**  
*Does HistoryStack need UI integration (menu, buttons)?*

Currently, Ctrl+Z/Y via keybindings. No undo history panel.

**Recommendation:** WP-04 suffices with keybindings. History panel → future WP.

---

## 12. Final Recommendation

### Status: **GO for WP-04 Implementation**

**Confidence Level:** HIGH

**Basis:**
1. Core V1 is hardened, frozen, validated (29/29 + contracts passing)
2. Viewport V1 experiment validates entire interaction pipeline (88/88 tests passing)
3. Tool framework is production-grade with clear lifecycle
4. Input→Binding→Command routing proven and minimal
5. Move/Rotate/Scale tools follow same pattern (reference implementations)
6. All WP-01A/02/03 scope complete
7. Clear extraction path from experiments to production
8. Risks identified and mitigated
9. Gates defined with acceptance criteria

**What's needed:**
- Approval of this discovery + architectural boundaries
- Decision on Transform ops promotion (Q1 above)
- Proceed with Gate 3 (Application + Viewport Foundation)

**What's NOT needed:**
- Further experiments
- Core changes
- New dependencies
- Architecture redesign

---

## 13. Summary Scorecard

| Aspect | Status | Evidence |
|--------|--------|----------|
| Core V1 Production-Ready | ✓ GO | 29/29 tests, hardened phases A–E, frozen |
| WP-01A Complete | ✓ GO | Binding system, display, picking, documented |
| WP-02 Complete | ✓ GO | Tool framework, MoveTool reference, 88 tests |
| WP-03 Complete | ✓ GO | Transform tools, Rotate/Scale reference impl. |
| Production Boundary Clear | ✓ GO | Classification A/B/C documented, extraction path known |
| Risks Identified | ✓ GO | HIGH/MEDIUM/LOW with mitigations |
| Entry Point Ready | ✗ NO | Needs Gate 3 (Application class + main.py) |
| Overall Readiness | ✓ GO | Proceed to Gate 3 (App Foundation) |

---

## Appendix A: File Checklist for WP-04 Gates 3–5

### To Extract → src/mirai/interaction/

```
experiments/mirai_bastel_viewport_V1/viewport/
├── tool.py                  → src/mirai/interaction/tool.py
├── input_binding.py         → src/mirai/interaction/input.py
├── commands.py              → src/mirai/interaction/commands.py
├── default_bindings.py      → src/mirai/interaction/bindings.py
├── move_tool.py             → src/mirai/interaction/tools/move.py
├── transform_tool.py (WP-03 TBD)
│   ├── RotateTool           → src/mirai/interaction/tools/rotate.py
│   └── ScaleTool            → src/mirai/interaction/tools/scale.py
└── constraints.py           → src/mirai/interaction/constraints.py
```

### To Extract → src/mirai/viewport/

```
experiments/mirai_bastel_viewport_V1/viewport/
├── camera.py                → src/mirai/viewport/camera.py
├── picking.py               → src/mirai/viewport/picking.py
├── display_state.py         → src/mirai/viewport/display.py
├── vecmath.py               → src/mirai/viewport/vecmath.py
├── app.py (REFACTOR)
│   ├── rendering logic      → src/mirai/viewport/render.py
│   ├── event handling       → src/mirai/viewport/window.py
│   └── scene init           → src/mirai/application.py
```

### To Create → src/mirai/

```
src/mirai/
├── __init__.py
├── application.py           # NEW: Application class
├── main.py                  # NEW: Entry point (Pyglet window adapter)
└── (structure above)
```

### Tests to Create

```
tests/
├── test_application.py      # Application lifecycle, scene init
├── test_command_dispatch.py # Command routing, context resolution
├── test_tool_manager.py     # Tool activation, lifecycle, state guards
├── test_integration.py      # Full input→op→history flow (headless)
└── (migrate existing tests)
```

---

**Report End**
