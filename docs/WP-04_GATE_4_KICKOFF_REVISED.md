# WP-04 Gate 4 — Interaction Foundation Kickoff

**Status:** Ready to Implement  
**Date:** 2026-09-02  
**Duration:** 2 work sessions (~14 hours)  
**Principle:** Build flexible infrastructure, not fixed UX

---

## Core Principle

**Wir bauen die Infrastruktur so, dass wir SPÄTER frei experimentieren können.**

Das bedeutet konkret:

- ✅ Tool activation decoupled from interaction start
- ✅ Selection management flexible (not tool-owned)
- ✅ History integration clean
- ❌ NO hardcoding of Wings/Nendo/Blender/Silo behavior
- ❌ NO result_target/base_target as concrete properties (yet)
- ❌ NO fixed hotkeys or interaction patterns
- ✅ Everything testable + documented

---

## Gate 4 Scope (Tightly Focused)

### What Gets Built

**Task 4.1-4.2: ToolManager Enhancement**
- Add `context` parameter to `activate(command, context=None)`
- Add `on_activate()` hook to Tool base class
- Support both "activate→wait" (Pattern A) and "activate+begin" (Pattern B) paths

**Task 4.3: MoveTool Integration**
- Implement: `begin(context)` → `update(**params)` → `commit()` / `cancel()`
- Test full lifecycle: activate → LMB → move → commit
- Verify preview + undo/redo

**Task 4.4-4.5: RotateTool & ScaleTool Integration**
- Same lifecycle pattern as MoveTool
- All three tools follow identical contract

**Task 4.6: Input Binding Integration**
- Wire M/R/S keys to ToolManager.activate()
- Verify keybindings dispatch correctly

**Task 4.7: History Integration**
- Each tool.commit() → history.push()
- Verify undo/redo restores mesh state
- Simple per-interaction (no batching yet)

**Task 4.8: Architecture Documentation**
- Write ADR-G4-001/002/003 to docs/
- Explain flexibility points for future experimentation

### What Does NOT Get Built (Intentionally)

- ❌ Gizmos or visual manipulators
- ❌ Snapping or constraints UI
- ❌ Modeling sessions or context stacks
- ❌ Result/base target switching
- ❌ History batching
- ❌ Permanent hotkey definitions
- ❌ Wings-specific or Blender-specific behavior

All of these become research topics for the **Viewport Interaction Lab** (future).

---

## Implementation Detail: Tool Lifecycle

### Tool Base Class (Updated)

```python
from abc import ABC, abstractmethod

class Tool(ABC):
    """Base tool with flexible activation patterns."""
    
    def __init__(self):
        self.is_active = False
        self.has_context = False
        self._preview_state = None
    
    def on_activate(self) -> None:
        """Called when ToolManager activates this tool.
        
        Override to implement activation behavior (e.g., immediate begin).
        Default: tool waits for explicit begin() call.
        """
        self.is_active = True
    
    def on_deactivate(self) -> None:
        """Called when tool is deactivated."""
        self.is_active = False
        self.has_context = False
    
    @abstractmethod
    def begin(self, context: dict) -> None:
        """Start interaction with given context.
        
        Args:
            context: dict with:
                - 'scene': Scene object
                - 'selection': Current Selection
                - any tool-specific params
        """
        pass
    
    @abstractmethod
    def update(self, **params) -> None:
        """Update live state during interaction.
        
        Called repeatedly while user is interacting.
        Updates preview state without committing.
        """
        pass
    
    @abstractmethod
    def commit(self) -> None:
        """Commit interaction, create history entry."""
        pass
    
    @abstractmethod
    def cancel(self) -> None:
        """Abort interaction, restore to pre-begin state."""
        pass
```

### ToolManager Enhancement

```python
class ToolManager:
    def __init__(self):
        self.active_tool = None
        self.tool_registry: dict[str, type] = {}
    
    def activate(self, command: str, context: dict | None = None) -> bool:
        """Activate tool, optionally with context for immediate begin.
        
        This enables both patterns:
        - Pattern A: activate(), then wait for user input, then begin()
        - Pattern B: activate(context=...), tool begins immediately
        
        Args:
            command: Tool command name
            context: Optional context dict for immediate begin
            
        Returns:
            True if activation succeeded
        """
        if self.active_tool:
            self.deactivate()
        
        tool_class = self.tool_registry.get(command)
        if not tool_class:
            return False
        
        self.active_tool = tool_class()
        self.active_tool.on_activate()
        
        # Pattern B: if context provided, start interaction immediately
        if context is not None:
            self.active_tool.begin(context)
        
        return True
    
    def begin_current_interaction(self, context: dict) -> None:
        """Explicitly start interaction on active tool (Pattern A).
        
        Called when user presses LMB or other trigger after tool is active.
        """
        if self.active_tool:
            self.active_tool.begin(context)
    
    def deactivate(self) -> None:
        """Deactivate current tool."""
        if self.active_tool:
            self.active_tool.on_deactivate()
            self.active_tool = None
    
    def update(self, **kwargs) -> None:
        """Forward update to active tool."""
        if self.active_tool:
            self.active_tool.update(**kwargs)
    
    def commit(self) -> None:
        """Commit active tool operation."""
        if self.active_tool:
            self.active_tool.commit()
    
    def cancel(self) -> None:
        """Cancel active tool operation."""
        if self.active_tool:
            self.active_tool.cancel()
```

---

## Implementation Approach: Move as Reference

### MoveTool Pattern (Gates 4–5 Reference)

```python
class MoveTool(Tool):
    def __init__(self):
        super().__init__()
        self.scene = None
        self.selection = None
        self.operation = None
        self.initial_state = None
    
    def begin(self, context: dict) -> None:
        """Start move interaction."""
        self.scene = context['scene']
        self.selection = context['selection']
        self.has_context = True
        
        # Create operation but don't commit yet
        self.operation = MoveOperation(OperationContext(self.scene.mesh))
        self.operation.begin()
        
        # Snapshot for cancel
        self.initial_state = self.scene.mesh.export_state()
    
    def update(self, delta: tuple[float, float, float]) -> None:
        """Update move preview."""
        if not self.operation:
            return
        
        # Apply delta to all selected vertices
        vertices = self._resolve_selection()
        self.operation.update(vertices=vertices, delta=delta)
        
        # Store preview (for rendering in Gate 5+)
        self._preview_state = self.operation  # Pseudo-preview
    
    def commit(self) -> None:
        """Finalize move and create history entry."""
        if not self.operation:
            return
        
        # Create history command
        command = self.operation.commit()
        self.scene.history.push(command)
        
        # Cleanup
        self.operation = None
        self.has_context = False
    
    def cancel(self) -> None:
        """Abort move, restore state."""
        if self.initial_state and self.scene:
            self.scene.mesh.load_state(self.initial_state)
        
        self.operation = None
        self.has_context = False
    
    def _resolve_selection(self) -> set:
        """Convert selection to vertices union."""
        if self.selection.mode == SelectionMode.VERTEX:
            return self.selection.vertices
        elif self.selection.mode == SelectionMode.EDGE:
            vertices = set()
            for edge_id in self.selection.edges:
                v1, v2 = self.scene.mesh.edge_vertices(edge_id)
                vertices.add(v1)
                vertices.add(v2)
            return vertices
        elif self.selection.mode == SelectionMode.FACE:
            vertices = set()
            for face_id in self.selection.faces:
                for v in self.scene.mesh.face_vertices(face_id):
                    vertices.add(v)
            return vertices
        return set()
```

Same pattern for RotateTool + ScaleTool.

---

## Test Strategy

### Unit Tests (Task 4.8)

```python
# Test Pattern A: activate → wait → begin
def test_move_tool_pattern_a():
    app = Application()
    app.init_scene()
    
    # Step 1: activate (no context)
    app.tool_manager.activate("Move")
    assert app.tool_manager.active_tool is not None
    assert not app.tool_manager.active_tool.has_context
    
    # Step 2: wait (user presses LMB)
    # Step 3: explicit begin
    context = {
        'scene': app.scene,
        'selection': app.selection,
    }
    app.tool_manager.begin_current_interaction(context)
    assert app.tool_manager.active_tool.has_context
    
    # Step 4: interact
    app.tool_manager.update(delta=(1.0, 0.0, 0.0))
    
    # Step 5: commit
    app.tool_manager.commit()
    assert len(app.history.undo_stack) == 1

# Test Pattern B: activate with context (immediate begin)
def test_move_tool_pattern_b():
    app = Application()
    app.init_scene()
    
    context = {
        'scene': app.scene,
        'selection': app.selection,
    }
    
    # Single call: activate + context
    app.tool_manager.activate("Move", context=context)
    assert app.tool_manager.active_tool.has_context
    
    # Interaction starts immediately
    app.tool_manager.update(delta=(1.0, 0.0, 0.0))
    app.tool_manager.commit()
    assert len(app.history.undo_stack) == 1

# Test all three tools
def test_all_tools_available():
    app = Application()
    app.init_scene()
    
    for command in ["Move", "Rotate", "Scale"]:
        app.tool_manager.activate(command)
        assert app.tool_manager.active_tool is not None
```

### Integration Tests

- M key → MoveTool activation
- R key → RotateTool activation
- S key → ScaleTool activation
- All three tools work independently
- History undo/redo across tools

---

## Acceptance Criteria (Gate 4)

### Functional

- [x] M/R/S keys activate Move/Rotate/Scale
- [x] Each tool can be activated via ToolManager
- [x] begin() → update() → commit() works
- [x] cancel() restores pre-begin state
- [x] Each commit() creates one history entry
- [x] Undo (Ctrl+Z) works across all tools
- [x] Redo (Ctrl+Y) works across all tools
- [x] Tools work on V/E/F selections (resolved to vertices)

### Architectural

- [x] Tool.on_activate() and Tool.begin() are separate
- [x] ToolManager.activate() supports optional context
- [x] Pattern A (activate→wait) works
- [x] Pattern B (activate+begin) works architecturally
- [x] Tools don't modify scene.selection directly
- [x] History kept simple (no batching yet)
- [x] No hardcoding of interaction patterns

### Code Quality

- [x] No Pyglet imports
- [x] All tools follow same contract
- [x] Tools fully testable
- [x] Clean separation: Input → Binding → Command → Tool
- [x] Architecture documented (ADR-G4-001/002/003)

---

## Session Plan (2 work sessions, ~14 hours)

### Session 1: Foundation (7 hours)

- Task 4.1: ToolManager enhancement
- Task 4.2: Tool base class update
- Task 4.3: MoveTool full implementation
- Task 4.4: RotateTool implementation
- Task 4.5: ScaleTool implementation
- Task 4.6: Input binding integration (M/R/S keys)

### Session 2: Integration + Docs (7 hours)

- Task 4.7: History integration testing
- Task 4.8: Full integration tests (all three tools)
- Task 4.9: Architecture documentation (ADRs)
- Task 4.10: Smoke test (Gate 3 + Gate 4 integration)
- Task 4.11: Code cleanup + docstrings

---

## Important Notes

### What We're NOT Deciding Now

- Wings vs Nendo vs Blender vs 3ds Max behavior
- Gizmo appearance or interaction
- Final hotkeys
- Result/base switching UX
- History batching semantics
- Tool stacking or nesting

### All of those become experiments in the Viewport Interaction Lab.

### What We ARE Building

Flexible, clean infrastructure that allows **any** of those to be added later without architectural rework.

---

## Success Criteria Summary

Gate 4 is successful if:

1. ✅ Tools activate, interact, commit cleanly
2. ✅ Both patterns (A + B) work architecturally
3. ✅ History/Undo/Redo stable
4. ✅ Tests pass (Unit + Integration)
5. ✅ Architecture documented
6. ✅ **Ready for UX experimentation in future labs**

---

**Status: Ready to Implement Gate 4**

**Next: Start Session 1 — ToolManager + Tool Implementation**
