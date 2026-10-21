# Gate 3 Implementation Readiness — Application Foundation

**Status:** Ready to implement  
**Duration:** 2 work sessions  
**Branch:** `wp/04-production-foundation`  
**Target merge:** `main` (after Gate 4)

---

## Overview

Gate 3 extracts production-ready interaction components (`Tool`, `Input`, `Binding`, `Commands`) from experiments and creates a window-free `Application` class.

**Key change from original plan:** Tasks 3.8–3.10 (Window/Rendering) are cancelled. Gate 3 is now **application-layer only**, not viewport-layer.

**New task:** Task 3.13 (Transform Ops promotion to Core) — approved via ADR-001.

---

## Pre-Implementation Checklist

- [ ] Branch `wp/04-production-foundation` created/up-to-date
- [ ] `src/core/` accessible and frozen (no modifications in Gate 3)
- [ ] Experiment sources verified:
  - `experiments/mirai_bastel_viewport_V1/viewport/tool.py` (exists)
  - `experiments/mirai_bastel_viewport_V1/viewport/input_binding.py` (exists)
  - `experiments/mirai_bastel_viewport_V1/viewport/commands.py` (exists)
  - `experiments/mirai_bastel_viewport_V1/viewport/default_bindings.py` (exists)
  - `experiments/mirai_bastel_core_V1/operations/transform.py` (exists)
- [ ] Gate 2 output (Q1–Q4 decisions, Option C) available for reference

---

## Directory Structure (to create)

```
src/mirai/                          # NEW — Production application layer
├── __init__.py
├── application.py                  # NEW — Orchestrator (window-free)
├── interaction/                    # NEW
│   ├── __init__.py
│   ├── tool.py                     # Extracted: Tool base class
│   ├── input.py                    # Extracted: Input, BindingSet, Binding
│   ├── commands.py                 # Extracted: Command enum + constants
│   ├── bindings.py                 # Extracted: build_default_bindings()
│   ├── routing.py                  # NEW: tool_for_command() dispatcher
│   └── tools/                      # NEW
│       ├── __init__.py
│       ├── move.py                 # Extracted: MoveTool
│       ├── rotate.py               # Conditional: RotateTool (if ops promoted)
│       └── scale.py                # Conditional: ScaleTool (if ops promoted)
└── viewport/                       # NEW — Camera/Display (no rendering)
    ├── __init__.py
    ├── camera.py                   # Extracted: OrbitCamera
    ├── picking.py                  # Extracted: Picker (linear scan)
    └── display.py                  # Extracted: DisplayState

tests/                              # NEW test files
├── test_application.py             # 10+ application tests
├── test_tool_lifecycle.py          # 15+ tool lifecycle tests
├── test_input_binding.py           # 8+ binding resolution tests (migrated)
├── test_camera.py                  # 5+ camera math tests (migrated)
├── test_picking.py                 # 5+ picking tests (migrated)
└── test_tool_integration.py        # 10+ full pipeline tests
```

---

## Tasks (Session 1)

### Task 3.1–3.5: Component Extraction (window-free)

**Duration:** ~2 hours (all tasks in parallel possible)

**Files to extract (copy as-is, no logic changes):**

1. **Task 3.1:** `Tool` base class
   - Source: `experiments/mirai_bastel_viewport_V1/viewport/tool.py` (185 lines)
   - Destination: `src/mirai/interaction/tool.py`
   - Changes: Update docstrings if they reference "experiment" → "production"
   - Acceptance: Import works, class unchanged, 3-state lifecycle preserved

2. **Task 3.2:** `Input` and `BindingSet` classes
   - Source: `experiments/mirai_bastel_viewport_V1/viewport/input_binding.py` (~250 lines)
   - Destination: `src/mirai/interaction/input.py`
   - Changes: Module docstring updated to production context
   - Acceptance: Imports work, binding resolution tests pass (10+ existing tests)

3. **Task 3.3:** `Command` enum + constants
   - Source: `experiments/mirai_bastel_viewport_V1/viewport/commands.py` (~50 lines)
   - Destination: `src/mirai/interaction/commands.py`
   - Changes: None (pure enum)
   - Acceptance: All command strings accessible (`commands.MOVE`, `commands.ROTATE`, etc.)

4. **Task 3.4:** Default bindings builder
   - Source: `experiments/mirai_bastel_viewport_V1/viewport/default_bindings.py` (~80 lines)
   - Destination: `src/mirai/interaction/bindings.py`
   - Changes: Import refactored to use `from .commands import commands`
   - Acceptance: `build_default_bindings()` creates valid BindingSet with all defaults

5. **Task 3.5:** Camera, Picking, Display (viewport layer, no rendering)
   - Sources:
     - `experiments/mirai_bastel_viewport_V1/viewport/camera.py` → `src/mirai/viewport/camera.py`
     - `experiments/mirai_bastel_viewport_V1/viewport/picking.py` → `src/mirai/viewport/picking.py`
     - `experiments/mirai_bastel_viewport_V1/viewport/display_state.py` → `src/mirai/viewport/display.py`
     - `experiments/mirai_bastel_viewport_V1/viewport/vecmath.py` → `src/mirai/viewport/vecmath.py`
   - Changes: Update `from mirai_bastel_core` → `from mirai.core`
   - Acceptance: No circular imports, all math/picking tests pass

**Acceptance (all 3.1–3.5):**
- [ ] All imports resolve (`from mirai.interaction import ...` works)
- [ ] No circular dependencies
- [ ] 30+ extracted tests pass unchanged

---

### Task 3.6–3.7: Create Application Class (window-free)

**Duration:** ~3 hours

**Task 3.6:** ToolManager class (NEW)

**File:** `src/mirai/interaction/tool_manager.py`

**Specification:**

```python
from typing import Type, Optional, Dict
from .tool import Tool
from .input import BindingSet
from .commands import Command

class ToolManager:
    """Manages tool activation and lifecycle."""
    
    def __init__(self):
        self._registry: Dict[str, Type[Tool]] = {}
        self.active_tool: Optional[Tool] = None
    
    def register(self, command: str, tool_class: Type[Tool]) -> None:
        """Register a command → tool class mapping."""
        self._registry[command] = tool_class
    
    def activate(self, command: str, context: Optional[dict] = None) -> bool:
        """
        Activate tool for command. If context provided, may start interaction immediately.
        
        Returns True if tool found and activated.
        """
        tool_class = self._registry.get(command)
        if not tool_class:
            return False
        
        # Deactivate existing tool
        if self.active_tool:
            self.active_tool.on_deactivate()
        
        # Activate new tool
        self.active_tool = tool_class()
        self.active_tool.is_active = True
        self.active_tool.on_activate()
        
        # Pattern B: if context provided, start interaction immediately
        if context is not None and self.active_tool:
            self.active_tool.begin(context)
        
        return True
    
    def deactivate(self) -> None:
        """Deactivate current tool."""
        if self.active_tool:
            self.active_tool.on_deactivate()
            self.active_tool.is_active = False
            self.active_tool = None
    
    def dispatch_input(self, event: dict) -> bool:
        """
        Dispatch input event to active tool. 
        Returns True if tool handled the event.
        """
        if not self.active_tool:
            return False
        
        if 'type' == 'mouse_motion':
            self.active_tool.update(dx=event.get('dx'), dy=event.get('dy'))
            return True
        elif event['type'] == 'mouse_press':
            if not self.active_tool.has_context:
                self.active_tool.begin(context={})  # pattern A
            return True
        elif event['type'] == 'mouse_release':
            command = self.active_tool.commit()
            return True
        
        return False
    
    @property
    def registry(self) -> Dict[str, Type[Tool]]:
        """Access to registration map (read-only)."""
        return dict(self._registry)
```

**Acceptance (Task 3.6):**
- [ ] Class instantiable
- [ ] `register()` and `activate()` work
- [ ] Tool lifecycle enforced (only one active at a time)
- [ ] 8+ ToolManager unit tests pass

**Task 3.7:** Application class (NEW)

**File:** `src/mirai/application.py`

**Specification:**

```python
from mirai.core import Scene, Selection, HistoryStack
from mirai.interaction import (
    Tool, ToolManager, BindingSet, Input, commands
)
from mirai.interaction.routing import tool_for_command
from mirai.interaction.bindings import build_default_bindings
from mirai.viewport import OrbitCamera, DisplayState

class Application:
    """Production application orchestrator (window-independent)."""
    
    def __init__(self):
        # Core structures
        self.scene: Scene = Scene()
        self.selection: Selection = self.scene.selection
        self.history: HistoryStack = self.scene.history
        
        # Viewport
        self.camera: OrbitCamera = OrbitCamera()
        self.display: DisplayState = DisplayState()
        
        # Tools
        self.tool_manager: ToolManager = ToolManager()
        self._setup_tools()
        
        # Input
        self.bindings: BindingSet = build_default_bindings()
    
    def _setup_tools(self) -> None:
        """Register default tools."""
        for command, tool_class in [
            (commands.MOVE, tool_for_command(commands.MOVE)),
            (commands.ROTATE, tool_for_command(commands.ROTATE)),
            (commands.SCALE, tool_for_command(commands.SCALE)),
        ]:
            if tool_class:
                self.tool_manager.register(command, tool_class)
    
    def init_scene(self, geometry_type: str = "cube") -> None:
        """Initialize default scene."""
        if geometry_type == "cube":
            from mirai.core import create_cube
            mesh = create_cube()
            self.scene.add_mesh(mesh)
    
    def dispatch_command(
        self, 
        command: str, 
        context: Optional[dict] = None,
        **params
    ) -> bool:
        """
        Dispatch a command (returns True if handled).
        
        Routes to ToolManager if command maps to a tool,
        otherwise executes directly (Undo, Redo, etc.).
        """
        # Route to tool if applicable
        tool_class = tool_for_command(command)
        if tool_class:
            return self.tool_manager.activate(command, context=context)
        
        # Direct commands
        if command == commands.UNDO:
            self.history.undo()
            return True
        elif command == commands.REDO:
            self.history.redo()
            return True
        
        return False
    
    def update_viewport(self, delta_t: float) -> None:
        """Update viewport state (for future animation/preview)."""
        pass
    
    def shutdown(self) -> None:
        """Clean shutdown."""
        self.tool_manager.deactivate()
```

**Acceptance (Task 3.7):**
- [ ] Class instantiable without window
- [ ] 10+ unit tests for init, dispatch, update
- [ ] All public methods have docstrings
- [ ] No window-specific code
- [ ] No Pyglet imports

---

## Tasks (Session 2)

### Task 3.8–3.10: Cancelled ❌

Not implemented in Gate 3 (moved to Gate 5).

---

### Task 3.13: Transform Operations Promotion ✅

**Duration:** ~30 minutes

**Prerequisite:** Decision from ADR-001 approved (already done)

**File:** `src/core/operations/transform.py` (NEW)

**Steps:**

1. Copy `experiments/mirai_bastel_core_V1/operations/transform.py` → `src/core/operations/transform.py`
2. Update `src/core/operations/__init__.py`:
   ```python
   from .transform import RotateOperation, ScaleOperation
   ```
3. Update `src/core/__init__.py`:
   ```python
   from .operations import RotateOperation, ScaleOperation
   ```
4. Run Core test suite: `pytest tests/ -k core` → expect 29/29 pass

**Acceptance:**
- [ ] `from mirai.core import RotateOperation, ScaleOperation` works
- [ ] All 29 Core tests still pass
- [ ] Transform ops usable by Gate 4 tools

**Commit message:**
```
core(transform): promote RotateOperation, ScaleOperation to production

Per ADR-001 (Core Freeze Exception), Transform operations are promoted
from experiments to Core V1 public API.

Rationale: These are fundamental modeling operations, production-grade,
and belong in Core as first-class citizens.

Enables: Gate 4 RotateTool, ScaleTool extraction.
```

---

### Task 3.14: Tool Integration & Routing

**Duration:** ~2 hours

**File:** `src/mirai/interaction/routing.py` (NEW)

**Specification:**

```python
from typing import Optional, Type
from .tool import Tool
from .tools.move import MoveTool
from .tools.rotate import RotateTool  # if promoted
from .tools.scale import ScaleTool    # if promoted
from .commands import commands

def tool_for_command(command: str) -> Optional[Type[Tool]]:
    """
    Route command to tool class.
    
    Returns None if command is not a tool activation command.
    """
    mapping = {
        commands.MOVE: MoveTool,
        commands.ROTATE: RotateTool,
        commands.SCALE: ScaleTool,
    }
    return mapping.get(command)
```

**Extract Tools (if Transform Ops promoted):**

1. **MoveTool** (already extracted)
   - Source: `experiments/mirai_bastel_viewport_V1/viewport/move_tool.py`
   - Destination: `src/mirai/interaction/tools/move.py`
   - Changes: Update imports (`from mirai.core import MoveOperation`)

2. **RotateTool** (NEW, if ops promoted)
   - Source: `experiments/mirai_bastel_viewport_V1/viewport/transform_tool.py` (extract RotateTool only)
   - Destination: `src/mirai/interaction/tools/rotate.py`
   - Changes: Import `from mirai.core import RotateOperation`; parameterless `__init__()`

3. **ScaleTool** (NEW, if ops promoted)
   - Source: `experiments/mirai_bastel_viewport_V1/viewport/transform_tool.py` (extract ScaleTool only)
   - Destination: `src/mirai/interaction/tools/scale.py`
   - Changes: Import `from mirai.core import ScaleOperation`; parameterless `__init__()`

**Acceptance:**
- [ ] All tool imports work
- [ ] Tool routing works (command → correct class)
- [ ] 5+ routing tests pass

---

### Task 3.15: Unit Tests (Integration)

**Duration:** ~3 hours (parallel with 3.14)

**Test files to create:**

1. **`tests/test_application.py`** (12+ tests)
   - Application instantiation (no window)
   - Scene initialization
   - Command dispatch routing
   - Tool activation via dispatch
   - Undo/Redo integration
   - State persistence across commands

2. **`tests/test_tool_lifecycle.py`** (15+ tests)
   - Tool activation → on_activate called
   - Tool begin → context accepted
   - Tool update (drag)
   - Tool commit → history updated
   - Tool cancel → state restored
   - Multiple tools sequentially

3. **`tests/test_tool_integration.py`** (10+ tests)
   - M key → MoveTool activated
   - MoveTool.begin() on context
   - Update on mouse drag
   - Commit on mouse release
   - Undo after commit
   - Full: Input → Binding → Command → Tool → Operation → History

4. **Migrate existing tests:**
   - `tests/test_input_binding.py` (10+ from experiments)
   - `tests/test_camera.py` (5+ from experiments)
   - `tests/test_picking.py` (5+ from experiments)

**Acceptance:**
- [ ] 50+ total tests pass
- [ ] Coverage ≥ 85% for `src/mirai/` (no window dependency)
- [ ] All tool lifecycle scenarios covered
- [ ] Full integration path tested (Input → History)

---

## Gate 3 Acceptance Criteria (Final)

### Structural
- [ ] `src/mirai/` directory structure created (no Window, no Rendering)
- [ ] No circular imports between modules
- [ ] All imports from `mirai.*` work

### Components
- [ ] Tool base class extracted + 3-state lifecycle preserved
- [ ] Input/Binding system extracted + resolution tests pass
- [ ] Commands enum created
- [ ] Default bindings builder works
- [ ] Camera/Picking/Display extracted (no rendering)
- [ ] ToolManager created with registry, activate(), context support
- [ ] Application class instantiable, window-independent
- [ ] Tool routing (tool_for_command) centralized

### Operations
- [ ] Transform Ops (Rotate, Scale) promoted to Core (Task 3.13)
- [ ] Core tests still pass (29/29)

### Tools
- [ ] MoveTool extracted
- [ ] RotateTool + ScaleTool extracted (if ops promoted)
- [ ] All tools inherit Tool lifecycle

### Application
- [ ] Application.dispatch_command() routes correctly
- [ ] Tool activation works (M/R/S keys in bindings)
- [ ] Undo/Redo functional
- [ ] Scene, History, Selection accessible

### Testing
- [ ] 50+ tests pass (application, tools, integration)
- [ ] Coverage ≥ 85% for src/mirai/
- [ ] No window dependency
- [ ] Full Input→Binding→Command→Tool→History pipeline tested

### Documentation
- [ ] `src/mirai/` structure documented
- [ ] Application class docstring complete
- [ ] Tool lifecycle documented
- [ ] Routing logic clear

---

## Known Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Circular imports between Tool/Application/ToolManager** | Code won't run | Create `routing.py` as neutral dispatcher; avoid Tool importing Application |
| **Window code slips into src/mirai** | Gate 3 fails (violates "window-free") | Code review: grep for `pyglet`, `window`, `gl` in src/mirai/ |
| **Experiment APIs differ from expected** | Extraction fails or needs major refactor | Verify experiment code before starting; adapt extraction specs if needed |
| **Core test suite breaks after Promotion** | Gate 3.13 fails | Run test suite immediately after promotion; revert if broken |
| **Tools assume context not provided** | Application.dispatch_command() fails | Test both Pattern A (activate→wait) and Pattern B (activate+context) |

---

## Deliverables Summary

**After Gate 3 complete:**

- `src/mirai/` fully structured and working
- 50+ tests passing
- Application class window-free, testable
- Transform Ops in Core (production)
- Ready for Gate 4 (Interaction expansion)

**Estimated effort:** 2 work sessions (16 hours)

---

**Status:** Ready to implement. No blockers identified.
