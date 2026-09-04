# WP-04 Gate 4 — Interaction Foundation Architecture Amendment

**Date:** 2026-09-02  
**Status:** Architecture Review Required Before Gate 4 Implementation  
**Scope:** Ensure Gate 4 enables multiple future UX models without locking into one  
**Priority:** CRITICAL — affects long-term UX flexibility

---

## Context

Gate 3 delivered a production foundation with Application + Tools + Input Binding.

Gate 4 originally planned to wire Input Binding → Command → Tool Routing → Tool Lifecycle.

However, we're actively exploring different modeling interaction paradigms:
- Silo (direct gestures)
- Wings/Nendo (tool activate → immediate interaction)
- 3ds Max (manipulator-oriented)
- Blender (modal)
- Mirai-proprietary (TBD via experimentation)

**The core issue:** Don't let Gate 4's implementation lock us into ONE interaction model.

---

## Risk Analysis: Current Gate 4 Design

### Current (Problematic) Architecture Assumption

```
Tool Activation (M key)
        ↓
Tool activated (state change)
        ↓
Tool waits for next input
        ↓
LMB pressed
        ↓
begin()
        ↓
Mouse move
        ↓
update()
        ↓
LMB released
        ↓
commit() or cancel()
```

**Implicit assumption:** This is the ONLY way to start an interaction.

### Risks This Creates

| Risk | Impact | Example |
|------|--------|---------|
| **Rigid activation semantics** | Can't add "M + start immediate" variant | Alt+E on face should extrude immediately (Wings-style) |
| **Tool lifecycle = Interaction lifecycle** | Can't nest/pause interactions | Scale inside Extrude session |
| **Selection tied to activation** | Can't maintain result+base context | After extrude, access original edges |
| **History per-interaction** | Can't batch operations | "Extrude → Scale → Commit" as one undo step? |

---

## Amendment: Flexible Interaction Architecture

### 1. Separate Concepts Clearly

**Define these as INDEPENDENT layers:**

```
Layer 1: Input Binding
  ↓ (routes to)
Layer 2: Commands
  ↓ (dispatches to)
Layer 3: Tool Activation (state change in ToolManager)
  ↓ (independent from)
Layer 4: Interaction Begin (when user starts acting on Tool)
  ↓ (independent from)
Layer 5: History (may batch multiple interactions)
```

**Critical:** Layers 3 and 4 are NOT inherently coupled.

### 2. Tool Activation States (Flexible)

```python
class Tool(ABC):
    """Base tool class with flexible activation patterns."""
    
    # State
    is_active: bool = False          # ToolManager says "this tool is active"
    has_context: bool = False         # Tool has current context (e.g., selection)
    
    # Lifecycle hooks — OPTIONAL, tool chooses when to implement
    def on_activate(self) -> None:
        """Called when ToolManager.activate(tool) — tool may or may not start interacting."""
        pass
    
    def on_deactivate(self) -> None:
        """Called when ToolManager.deactivate() — clean up."""
        pass
    
    # Interaction — WHEN tool chooses to start
    def begin(self, context: dict) -> None:
        """Start interaction with given context (selection, pivot, etc)."""
        pass
    
    def update(self, **params) -> None:
        """Update live state."""
        pass
    
    def commit(self) -> Command:
        """Finish interaction, return history command."""
        pass
    
    def cancel(self) -> None:
        """Abort interaction, restore state."""
        pass
```

**Key:** `on_activate()` and `begin()` are separate.

### 3. Multiple Interaction Start Patterns

**Pattern A: Explicit Activation (Current)**

```python
# User presses M
command_dispatcher.dispatch("Move")
  ↓
tool_manager.activate("Move")
  ↓
MoveTool.on_activate() called
  ↓
MoveTool waits
  ↓
# User presses LMB
input_handler.emit("select")
  ↓
MoveTool.begin(context=current_selection)
```

**Pattern B: Immediate Start (Alt+E example)**

```python
# User presses Alt+E with face selected
command_dispatcher.dispatch("Extrude", context=current_selection)
  ↓
tool_manager.activate("Extrude")
  ↓
ExtrudeTool.on_activate() → immediately calls begin(face_selection)
  ↓
ExtrudeTool live and previewing
```

**Pattern C: Nested/Temporary (Future)**

```python
# Extrude tool running
ExtrudeTool is_active=True, begin() active
  ↓
# User presses R for temporary Scale
command_dispatcher.dispatch("RotateTool", context=extrude_result)
  ↓
RotateTool.activate() + begin(extrude_result)
  ↓
RotateTool preview active (Extrude paused/background)
  ↓
# User commits or cancels
RotateTool.commit()
  ↓
return_to_extrude_context()
```

---

### 4. Selection / Target Architecture

**Design principle:** Interaction doesn't own the Selection.

**For Gate 4:** Keep it simple.

```python
class Scene:
    current_selection: Selection     # Active selection (V/E/F)
```

**Conceptual preparation (NOT implemented in Gate 4):**

Future gates might need to distinguish:
- `result_target` — what was produced by last operation
- `base_target` — what was the base before operation

But we don't know yet HOW that will work (Context-based? Stack-based? UI panel?).

**Architecture principle:** Don't build concrete properties we don't yet understand. Instead:

- Keep Selection/Target access flexible (pass through Scene, not Tool-owned)
- Don't hard-code "current_selection is the only truth"
- Document the POSSIBILITY for future experiments
- Later gates can add richer target management as needed

This keeps Gate 4 focused while leaving room for result/base exploration without architectural blockers.

---

### 5. History: Flexible Batching

**Don't assume 1 interaction = 1 history entry:**

```python
class HistoryStack:
    def begin_batch(self, name: str) -> None:
        """Start collecting multiple operations into one undo step."""
        pass
    
    def end_batch(self) -> None:
        """Commit batch as single undo entry."""
        pass
    
    def push(self, command: Command) -> None:
        """Push command (to batch if active, else to stack)."""
        pass
```

**Example:**

```python
# Session: Extrude → Scale → Commit as ONE undo step
history.begin_batch("ExtrudeWithScale")
extrude_tool.commit()      # → history (batched)
scale_tool.commit()        # → history (batched)
history.end_batch()        # → single undo entry
```

---

## Gate 4 Implementation Guidelines

### DO:

- [x] Keep Input Binding → Command → Tool Routing clean
- [x] Implement MoveTool.begin/update/commit/cancel correctly
- [x] Wire M/R/S keys to tool activation
- [x] Verify Tools can be activated from ToolManager
- [x] Verify LMB preview + commit works for Move
- [x] Write tests for tool lifecycle
- [x] Document where Selection is accessed (Scene scope, not Tool scope)
- [x] Keep undo/redo functional (per-interaction for now)

### DON'T:

- [ ] Hard-code "M activation = immediate begin()"
- [ ] Assume Tools own their Selection/Target
- [ ] Design history batching now (implement simple push/pop for Gate 4)
- [ ] Lock interaction state to tool activation state
- [ ] Copy Blender/Wings/3ds-Max behavior patterns directly
- [ ] Create complex nested tool managers
- [ ] Define final hotkeys in code (make them data-driven for future)

---

## Architecture Decisions to Document

### ADR-G4-001: Tool Activation ≠ Interaction Start

**Decision:** `ToolManager.activate(tool)` only sets tool state. Interaction `begin()` is called separately.

**Rationale:** Enables Pattern A (activate→wait) and Pattern B (activate+begin) without architectural conflict.

**Implications:**
- Tools implement `on_activate()` to do whatever they want
- Most tools will wait for next user input before calling `begin()`
- Some tools (future) may call `begin()` immediately

---

### ADR-G4-002: Selection is Scene-Owned, Not Tool-Owned

**Decision:** `Scene.current_selection` is the authority. Tools read, don't own.

**Rationale:** Enables future toggling between result/base, and switching tools mid-session without losing context.

**Implications:**
- Tools access `scene.selection` to see what's selected
- Tools don't modify `scene.selection` directly (operations modify Mesh, selection tracks)
- `Scene` manages selection lifecycle (not Tool)

---

### ADR-G4-003: History Remains Simple in Gate 4

**Decision:** Each `commit()` → one `HistoryStack.push()`. Batching is future work.

**Rationale:** Keeps Gate 4 focused. Experimentation will reveal if batching is needed.

**Implications:**
- Extrude → Scale → Commit = 2 undo steps (for now)
- Later gate can add history.begin_batch() / end_batch()
- No architectural blocker to adding it

---

## Gate 4 Revised Acceptance Criteria

### Functional (unchanged)

- [x] M/R/S keys activate their tools
- [x] Tools can be activated from ToolManager
- [x] begin() → update() → commit()/cancel() works
- [x] Preview shows during interaction
- [x] Commit creates history entry
- [x] Cancel restores state
- [x] Undo/Redo works

### Architectural (NEW)

- [x] Tool.on_activate() and Tool.begin() are separate method calls
- [x] Tools don't own Scene.selection
- [x] Activation state (is_active) ≠ Interaction state (has_context)
- [x] Scene provides both current_selection and result_target
- [x] History implementation doesn't prevent future batching
- [x] Code doesn't assume "M → immediate begin()" is only path
- [x] Documentation explains multi-pattern possibility

---

## Implementation Plan (Gate 4 — Revised)

### Task 4.1-4.3: ToolManager Enhancements

Update ToolManager to support:
```python
class ToolManager:
    def activate(self, command: str, context: dict | None = None) -> bool:
        """Activate tool. Optionally provide context for immediate begin."""
        tool_class = self.tool_registry.get(command)
        if not tool_class:
            return False
        
        self.active_tool = tool_class()
        self.active_tool.on_activate()
        
        # IF context provided, immediately start interaction
        if context is not None:
            self.active_tool.begin(context)
        
        return True
    
    def begin_current_interaction(self, context: dict) -> None:
        """Explicitly start interaction on active tool (Pattern A)."""
        if self.active_tool:
            self.active_tool.begin(context)
```

**Enables:**
- Pattern A: `activate()` then wait, then `begin_current_interaction()`
- Pattern B: `activate(context=...)` calls both

### Task 4.4-4.5: Move Tool Integration

Implement MoveTool.begin/update/commit/cancel.

**Test both patterns:**
1. M → wait → LMB → move
2. (Future test) Alt+M on selection → immediate move

### Task 4.6-4.7: Rotate & Scale Tools

Same lifecycle as Move.

### Task 4.8: History Integration

Simple per-tool history. Document that batching is future work.

### Task 4.9: Architecture Documentation

Write ADR-G4-001/002/003 to docs/architecture/.

---

## Example: How Pattern B Becomes Possible Later

**Current Gate 4 (Pattern A):**
```python
# Input: M key
tool_manager.activate("Move")
# MoveTool waits

# Input: LMB
tool_manager.begin_current_interaction(context=current_selection)
# MoveTool.begin() called
```

**Future Gate X (Pattern B) — NO architectural changes:**
```python
# Input: Alt+M with selection
command_dispatcher.dispatch("Move", context=current_selection)
# ↓
tool_manager.activate("Move", context=current_selection)
# ↓ (ToolManager calls begin automatically if context provided)
# MoveTool.begin(context) called
# MoveTool live immediately

# Same tool, same lifecycle, different activation path.
```

---

## What This Means for Gate 4

### Small Changes Required

- Add `context` parameter to `ToolManager.activate()`
- Add `on_activate()` hook to Tool base class
- Document the architectural separation
- Test that Pattern A works (no new code needed)

### No New Features Needed

- Pattern B doesn't need implementation in Gate 4
- Nesting/batching don't need implementation
- Result/base don't need UI
- Just ensure architecture allows them

### Gate 4 Stays Small

- All tasks still fit in 2 sessions
- Just more careful architecture
- Better documented design

---

## Sign-Off

This amendment ensures Gate 4 builds a foundation that:

✅ Works for current (Pattern A) usage  
✅ Doesn't block Pattern B (immediate start)  
✅ Doesn't block Pattern C (nested interactions)  
✅ Keeps history flexible  
✅ Keeps selection context accessible  

**Recommendation:** Approve this amendment, then implement Gate 4 with these principles.

The modeling UX will be decided via experimentation, not hardcoded in Gate 4.

---

**Status:** Ready for Gate 4 implementation with amended architecture

**Next:** Gate 4 Kickoff (revised task list + architecture principles)
