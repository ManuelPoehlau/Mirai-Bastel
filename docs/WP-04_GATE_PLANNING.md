# WP-04 — Gate Planning & Acceptance Criteria

**Document Version:** 1.0  
**Status:** Ready for implementation  
**Date:** 2026-09-01

---

## Quick Reference: Gate Overview

| Gate | Phase | Duration | Key Deliverable | Status |
|------|-------|----------|-----------------|--------|
| 2 | Discovery ✓ | Completed | This report + approval | ✓ DONE |
| 3 | App Foundation | 3–4 sessions | src/mirai/ structure + Application class | → NEXT |
| 4 | Interaction | 2 sessions | Tools, routing, integration | → AFTER 3 |
| 5 | Selection | 2 sessions | Selection modes, visualization | → AFTER 4 |
| 6 | Input Config | 1 session | Bindings, keymap.json | → AFTER 5 |
| 7 | Camera | 1 session | Orbit/pan/zoom stable | → AFTER 6 |
| 8 | Validation | 1 session | 150+ tests, coverage ≥85% | → AFTER 7 |
| 9 | AI Review | 1 session | Independent architecture check | → AFTER 8 |
| 10 | E2E Test | 1 session | Manual human workflow validation | → AFTER 9 |
| 11 | Architecture Review | 1 session | Doc update, final green light | → AFTER 10 |
| 12 | Merge | 1 session | Commit to main, plan WP-05 | → FINAL |

**Total estimated effort:** 13–15 work sessions (2–3 weeks of daily focused work)

---

## Gate 3: Application & Viewport Foundation

### Objective
Extract production-ready components from experiments, establish modular structure under `src/mirai/`, create Application lifecycle class, build minimal production entry point.

### Duration
3–4 work sessions (focus: clear separation of concerns, window-free tests)

### Pre-Gate Checklist
- [ ] Approval of this discovery report (Gate 2 review complete)
- [ ] Decision on Transform ops promotion (Q1 from report)
- [ ] Access to experiment code paths confirmed

### Tasks

#### Task 3.1: Create src/mirai/ Directory Structure

**Goal:** Establish clean production boundary

```bash
# Create directories
mkdir -p src/mirai/{interaction,viewport,interaction/tools}
touch src/mirai/__init__.py
touch src/mirai/interaction/__init__.py
touch src/mirai/interaction/tools/__init__.py
touch src/mirai/viewport/__init__.py
```

**Acceptance:**
- [ ] All directories exist with __init__.py files
- [ ] No circular imports possible
- [ ] Structure matches proposed layout in report

---

#### Task 3.2: Extract Tool Framework

**Goal:** Move Tool base class from experiments to production

**Files:**
- Source: `experiments/mirai_bastel_viewport_V1/viewport/tool.py`
- Destination: `src/mirai/interaction/tool.py`

**Changes:**
- [ ] Copy file as-is (no code changes)
- [ ] Update import paths if necessary
- [ ] Verify docstrings reference production context

**Acceptance:**
- [ ] Import `from mirai.interaction import Tool` works
- [ ] Class unchanged (185 lines, 3-state lifecycle)
- [ ] Unit tests pass unchanged

---

#### Task 3.3: Extract Input/Binding System

**Goal:** Move Input and BindingSet classes to production

**Files:**
- Source: `experiments/mirai_bastel_viewport_V1/viewport/input_binding.py`
- Destination: `src/mirai/interaction/input.py`

**Changes:**
- [ ] Copy file as-is
- [ ] Update module docstring to production context
- [ ] No code logic changes

**Acceptance:**
- [ ] Import `from mirai.interaction.input import Input, BindingSet` works
- [ ] Binding resolution tests pass (10+ existing tests)
- [ ] JSON serialization works

---

#### Task 3.4: Extract Command Enum

**Goal:** Move command definitions to production

**Files:**
- Source: `experiments/mirai_bastel_viewport_V1/viewport/commands.py`
- Destination: `src/mirai/interaction/commands.py`

**Changes:**
- [ ] Copy file as-is
- [ ] Simple string constants (MOVE, ROTATE, SCALE, UNDO, REDO, etc.)

**Acceptance:**
- [ ] Import `from mirai.interaction import commands` works
- [ ] All command strings accessible

---

#### Task 3.5: Extract Default Bindings

**Goal:** Move default keybindings to production

**Files:**
- Source: `experiments/mirai_bastel_viewport_V1/viewport/default_bindings.py`
- Destination: `src/mirai/interaction/bindings.py`

**Changes:**
- [ ] Copy file as-is
- [ ] Refactor to use `commands.*` imports

**Acceptance:**
- [ ] Import `from mirai.interaction.bindings import build_default_bindings` works
- [ ] BindingSet created with all default mappings
- [ ] Tests pass

---

#### Task 3.6: Extract Viewport Components

**Goal:** Move camera, picking, display to production

**Files:**
- Source: 
  - `experiments/mirai_bastel_viewport_V1/viewport/camera.py`
  - `experiments/mirai_bastel_viewport_V1/viewport/picking.py`
  - `experiments/mirai_bastel_viewport_V1/viewport/display_state.py`
  - `experiments/mirai_bastel_viewport_V1/viewport/vecmath.py`
- Destination:
  - `src/mirai/viewport/camera.py`
  - `src/mirai/viewport/picking.py`
  - `src/mirai/viewport/display.py`
  - `src/mirai/viewport/vecmath.py`

**Changes:**
- [ ] Copy each file as-is
- [ ] Update internal imports (e.g., `from ..core import` paths)

**Acceptance:**
- [ ] All imports resolve (no circular deps)
- [ ] Camera tests pass (orbit, pan, zoom math)
- [ ] Picking tests pass (ray-cast)
- [ ] Display state tests pass

---

#### Task 3.7: Create Application Class

**Goal:** Core production orchestrator (window-free)

**File:** `src/mirai/application.py` (NEW)

**Specification:**

```python
class Application:
    """Production Application orchestrator (window-independent)."""
    
    def __init__(self) -> None:
        """Initialize application state."""
        self.scene: Scene = Scene()
        self.selection: Selection = self.scene.selection
        self.history: HistoryStack = self.scene.history
        self.camera: OrbitCamera = ...
        self.tool_manager: ToolManager = ...
        self.bindings: BindingSet = ...
        self.display: DisplayState = ...
    
    def init_scene(self, geometry_type: str = "cube") -> None:
        """Initialize default scene (cube or grid)."""
        # Implement: load cube mesh from Core
        pass
    
    def dispatch_command(
        self, 
        command: str, 
        context: str | None = None,
        **params
    ) -> bool:
        """Dispatch a command (returns True if handled)."""
        # Implement: Command → Tool routing
        pass
    
    def update_viewport(self, delta_t: float) -> None:
        """Update viewport state (animation, preview)."""
        # Implement: frame update logic
        pass
    
    def shutdown(self) -> None:
        """Clean shutdown."""
        pass
```

**Key Constraints:**
- NO window dependency (testable in isolation)
- NO Pyglet imports
- All state testable via properties
- Scene/History/Selection from Core V1

**Acceptance:**
- [ ] Class instantiable without window
- [ ] 10+ unit tests for init, dispatch, update
- [ ] All public methods have docstrings
- [ ] No window-specific code

---

#### Task 3.8: Extract Rendering Logic

**Goal:** Isolate geometric rendering from event loop

**Files:**
- Source: `experiments/mirai_bastel_viewport_V1/viewport/app.py` (portions)
- Destination: `src/mirai/viewport/render.py` (NEW)

**Functions to extract:**
- `_compute_normals(mesh)` → `compute_normals()`
- `_face_triangle_arrays(mesh, face_ids)` → `face_triangle_arrays()`
- Edge/vertex rendering logic

**Acceptance:**
- [ ] Rendering functions window-free
- [ ] Tests pass (triangle counts, normal vectors)
- [ ] Called from Application.update_viewport()

---

#### Task 3.9: Create Pyglet Window Adapter

**Goal:** Thin layer connecting Pyglet events to Application

**File:** `src/mirai/viewport/window.py` (NEW)

**Specification:**

```python
class ModelerWindow(pyglet.window.Window):
    """Pyglet window adapter (minimal, event bridging only)."""
    
    def __init__(self, app: Application) -> None:
        """Accept Application instance (dependency injection)."""
        self.app = app
    
    def on_draw(self) -> None:
        """Render from app state."""
        # Call app.update_viewport(), render from app.scene
    
    def on_key_press(self, symbol, modifiers) -> None:
        """Translate to Input, dispatch via app.dispatch_command()."""
        input = Input(kind="key", value=..., modifiers=...)
        command = self.app.bindings.command_for(input)
        self.app.dispatch_command(command)
    
    # on_mouse_press, on_mouse_drag, on_mouse_release, on_mouse_scroll
```

**Acceptance:**
- [ ] Window delegates to Application
- [ ] Application logic testable without window
- [ ] Pyglet imports isolated to this file only

---

#### Task 3.10: Create Entry Point (main.py)

**Goal:** Launch production application

**File:** `src/mirai/main.py` or `src/main.py` (NEW)

**Specification:**

```python
def main() -> None:
    """Launch Mirai-Bastel production application."""
    app = Application()
    app.init_scene(geometry_type="cube")
    
    window = ModelerWindow(app)
    window.set_caption("Mirai-Bastel V1")
    
    pyglet.app.run()

if __name__ == "__main__":
    main()
```

**Acceptance:**
- [ ] `python src/main.py` launches window
- [ ] Window displays cube
- [ ] Application responds to input
- [ ] Can close window cleanly

---

#### Task 3.11: Unit Tests

**Goal:** Verify all extracted components work independently

**Files to create:**
- `tests/test_application.py` (30+ tests)
  - [ ] Application init (scene, history, selection)
  - [ ] Command dispatch routing
  - [ ] Scene update logic
  - [ ] Undo/redo integration
- `tests/test_input_binding.py` (migrate from experiments)
  - [ ] Binding resolution
  - [ ] Context priority
  - [ ] JSON serialization
- `tests/test_camera.py` (migrate)
  - [ ] Orbit/pan/zoom math
  - [ ] Screen-to-world delta
- `tests/test_picking.py` (migrate)
  - [ ] Ray casting
  - [ ] Selection from click
- `tests/test_display_state.py` (migrate)

**Acceptance:**
- [ ] 80+ tests pass
- [ ] No window dependency
- [ ] Coverage ≥ 85% for core modules

---

#### Task 3.12: Smoke Test

**Goal:** Verify basic end-to-end flow (headless)

**File:** `tests/test_smoke.py` (NEW)

**Scenario:**
```python
def test_application_can_init_and_respond():
    """Minimal end-to-end without window."""
    app = Application()
    app.init_scene()
    
    # Simulate input
    input = Input(kind="key", value="v")
    command = app.bindings.command_for(input)
    result = app.dispatch_command(command)
    
    assert result is True
    assert app.selection.mode == SelectionMode.VERTEX
```

**Acceptance:**
- [ ] Application can initialize
- [ ] Commands dispatch without error
- [ ] State changes propagate
- [ ] No window required

---

### Gate 3 Acceptance Criteria

**ALL of the following must pass:**

- [ ] `src/mirai/` directory structure complete
- [ ] All extraction tasks (3.2–3.10) complete
- [ ] `python src/main.py` launches window with cube
- [ ] Window responds to input (keys, mouse)
- [ ] 80+ unit tests pass (no window dependency)
- [ ] Code coverage ≥ 85% for application/interaction/viewport modules
- [ ] No Pyglet imports outside of viewport/window.py and main.py
- [ ] Docstrings complete
- [ ] No circular dependencies
- [ ] All extracted files import cleanly

**If all criteria pass:** Proceed to Gate 4 (Interaction & Tools Integration)

**If any criterion fails:** Fix + retest before proceeding

---

## Gate 4: Interaction & Tools Integration

### Objective
Wire Input→Binding→Command→Tool→Operation→History pipeline. Integrate Move tool reference implementation. Decide on Transform ops promotion. Integrate Rotate/Scale if promoted.

### Duration
2 work sessions

### Pre-Gate Checklist
- [ ] Gate 3 acceptance criteria all pass
- [ ] Decision made: Transform ops promoted to src/core? (Gate 2 Q1)
- [ ] Core freeze review completed (if promoting)

### Key Tasks

#### Task 4.1: Create ToolManager Class

**File:** `src/mirai/interaction/tool_manager.py` (NEW)

```python
class ToolManager:
    """Manages tool lifecycle (activate/deactivate/begin/update/commit/cancel)."""
    
    def __init__(self) -> None:
        self.active_tool: Tool | None = None
        self.tool_registry: dict[str, type[Tool]] = {}
    
    def register_tool(self, command: str, tool_class: type[Tool]) -> None:
        """Register command → tool mapping."""
        pass
    
    def activate(self, command: str) -> bool:
        """Activate tool for command (if not already active)."""
        pass
    
    def deactivate(self) -> None:
        """Deactivate current tool."""
        pass
    
    def begin_interaction(self, **params) -> None:
        """Start interaction (ACTIVE → INTERACTING)."""
        pass
    
    def update(self, **kwargs) -> None:
        """Update active interaction."""
        pass
    
    def commit(self) -> Any:
        """Commit and return history command."""
        pass
    
    def cancel(self) -> None:
        """Cancel without history."""
        pass
```

**Acceptance:**
- [ ] Tool lifecycle enforced (state guards)
- [ ] Only one tool active at a time
- [ ] 15+ unit tests

---

#### Task 4.2: Extract MoveTool (WP-02 Reference)

**Files:**
- Source: `experiments/mirai_bastel_viewport_V1/viewport/move_tool.py`
- Destination: `src/mirai/interaction/tools/move.py`

**Changes:**
- [ ] Update imports (from `mirai_bastel_core` → from `mirai.core`)
- [ ] Copy tool_for_command() logic (will generalize in 4.4)

**Acceptance:**
- [ ] Import `from mirai.interaction.tools.move import MoveTool` works
- [ ] Tool lifecycle follows contract
- [ ] Tests pass (8+ move tool tests)

---

#### Task 4.3: Transform Ops Promotion (Conditional)

**If decision = "Promote to src/core":**

**Files:**
- Source: `experiments/mirai_bastel_core_V1/operations/transform.py`
- Destination: `src/core/operations/transform.py`

**Changes:**
- [ ] Copy as-is to src/core
- [ ] Update src/core/__init__.py to export RotateOperation, ScaleOperation
- [ ] Verify Core freeze policy OK (consult CORE_V1_FREEZE.md §7)

**Acceptance:**
- [ ] Import `from mirai.core import RotateOperation, ScaleOperation` works
- [ ] All Core tests still pass (29/29)
- [ ] Architecture review notes added to commit message

**If decision = "Keep in experiment":**

- [ ] Document decision + rationale
- [ ] Tools will duplicate operation logic (acceptable for WP-04)
- [ ] Skip tasks 4.4 and 4.5

---

#### Task 4.4: Extract RotateTool & ScaleTool (If Ops Promoted)

**Files:**
- Source: `experiments/mirai_bastel_viewport_V1/viewport/transform_tool.py`
- Destination: 
  - `src/mirai/interaction/tools/rotate.py` (RotateTool)
  - `src/mirai/interaction/tools/scale.py` (ScaleTool)

**Changes:**
- [ ] Split TransformTool base class into rotate.py + scale.py
- [ ] Update imports (RotateOperation, ScaleOperation from `mirai.core`)

**Acceptance:**
- [ ] Both imports work
- [ ] Tests pass (12+ per tool)

---

#### Task 4.5: Tool Routing

**File:** `src/mirai/interaction/routing.py` (NEW)

```python
def tool_for_command(command: str) -> type[Tool] | None:
    """Route command to tool class."""
    mapping = {
        commands.MOVE: MoveTool,
        commands.ROTATE: RotateTool,  # if promoted
        commands.SCALE: ScaleTool,    # if promoted
    }
    return mapping.get(command)
```

**Acceptance:**
- [ ] Routing centralized
- [ ] Extensible (add new tools easily)
- [ ] Tests verify mapping

---

#### Task 4.6: Application.dispatch_command() Implementation

**File:** `src/mirai/application.py` (update)

```python
def dispatch_command(self, command: str, context: str | None = None, **params) -> bool:
    """Dispatch command, routing to tool if needed."""
    # 1. Resolve input → command (via bindings)
    # 2. If tool-based: route via ToolManager
    # 3. If direct: execute immediately (Undo, Redo, etc.)
    # 4. Return True if handled
```

**Acceptance:**
- [ ] Command dispatch testable
- [ ] Tool activation works
- [ ] Non-tool commands (Undo, Redo) work directly
- [ ] Tests cover all paths

---

#### Task 4.7: Integration Tests

**File:** `tests/test_tool_integration.py` (NEW, 20+ tests)

**Scenarios:**
- [ ] M key activates MoveTool
- [ ] Tool active, begin interaction
- [ ] Update (dx, dy) during drag
- [ ] Commit on release (1 history entry)
- [ ] Cancel on Esc (no history)
- [ ] Undo/Redo after commit
- [ ] Same for R (Rotate) and S (Scale) if promoted

**Acceptance:**
- [ ] Full input→operation→history pipeline works
- [ ] No window required

---

### Gate 4 Acceptance Criteria

- [ ] ToolManager class created + tested
- [ ] MoveTool extracted + working
- [ ] Transform ops promoted OR decision documented
- [ ] RotateTool/ScaleTool extracted (if ops promoted)
- [ ] Tool routing working
- [ ] Application.dispatch_command() integrated
- [ ] 20+ integration tests pass
- [ ] M, R, S keys activate correct tools
- [ ] Tools follow lifecycle contract

---

## Gate 5: Selection & Display Foundation

### Objective
Integrate selection modes, visualization, display modes. Make selection functional in interaction.

### Duration
2 work sessions

### Key Tasks

#### Task 5.1: Selection Modes

**Goal:** V/E/F mode toggle

```python
# Application should route:
# "V" key → Command.SelectVertexMode → app.selection.set_mode(SelectionMode.VERTEX)
# "E" key → Command.SelectEdgeMode   → app.selection.set_mode(SelectionMode.EDGE)
# "F" key → Command.SelectFaceMode   → app.selection.set_mode(SelectionMode.FACE)
```

**Acceptance:**
- [ ] 5+ tests for mode switching
- [ ] Selection state correct after switch

#### Task 5.2: Selection Visualization

**Goal:** Highlight selected/hovered elements during rendering

- [ ] Selected vertices → cyan dot
- [ ] Selected edges → cyan line
- [ ] Selected faces → cyan fill
- [ ] Hovered element → yellow highlight (before click)

**Acceptance:**
- [ ] Rendering tests verify colors/styles
- [ ] No logic changes to selection (purely visual)

#### Task 5.3: Hover Indication

**Goal:** Show what element would be selected on click

```python
def refresh_hover(self, screen_x, screen_y) -> None:
    """Update hover based on mouse position."""
    element = self.picking.pick(screen_x, screen_y, ...)
    self.selection.hovered = element
```

**Acceptance:**
- [ ] Hover updates on mouse motion
- [ ] Tests verify element type determination

#### Task 5.4: Selection-to-Vertices Resolver

**Goal:** V/E/F selection → affected vertex IDs (for tools)

```python
def resolve_selection_vertices(
    mesh: Mesh, 
    selection: Selection, 
    mode: SelectionMode
) -> set[VertexId]:
    """
    Vertex Mode → selected vertices
    Edge Mode   → vertices of selected edges (union)
    Face Mode   → vertices of selected faces (union)
    """
```

**Acceptance:**
- [ ] 5+ tests for each mode
- [ ] Multi-element union correct

#### Task 5.5: Display Modes

**Goal:** Shaded / Flat Shaded / Wireframe + overlay toggle

```python
# Commands:
# "O" key → toggle display mode (cycle through modes)
# "W" key → toggle wireframe overlay
```

**Acceptance:**
- [ ] Display state persists during interaction
- [ ] Rendering reflects mode changes
- [ ] Tests verify mode cycle

#### Task 5.6: Integration Tests

**File:** `tests/test_selection_and_display.py` (NEW, 15+ tests)

**Scenarios:**
- [ ] V/E/F mode toggle works
- [ ] Click selects element in current mode
- [ ] Click deselects (toggle)
- [ ] Move tool respects selection mode (V/E/F → vertices)
- [ ] Display mode changes rendering
- [ ] Wireframe overlay toggles

**Acceptance:**
- [ ] All scenarios pass
- [ ] No regressions from Gates 3–4

---

### Gate 5 Acceptance Criteria

- [ ] Selection modes switchable (V/E/F)
- [ ] Click-to-select functional
- [ ] Hover indication working
- [ ] Selection-to-vertices resolver tested
- [ ] Display modes functional (Shaded/Flat/Wireframe)
- [ ] Wireframe overlay toggle working
- [ ] 15+ selection/display tests pass
- [ ] Move tool works with all selection modes

---

## Gate 6–12 Summary

| Gate | Focus | Tests | Key Deliverable |
|------|-------|-------|-----------------|
| 6 | Input Config | 10 | keymap.json override, JSON validation |
| 7 | Camera | 10 | Orbit/pan/zoom math verified |
| 8 | Validation | 50+ | 150+ total tests, coverage ≥85% |
| 9 | AI Review | 0 | Independent architecture validation |
| 10 | E2E Test | 0 | Manual user workflow (no automation) |
| 11 | Architecture | 0 | Docs updated, GO/NO-GO final |
| 12 | Merge | 0 | Commit to main, plan WP-05 |

---

**Document End**
