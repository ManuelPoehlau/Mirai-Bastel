# Architecture Decision Records — Gate 4 Interaction Foundation

**Date:** 2026-09-02  
**Status:** APPROVED  
**Section:** Interaction Layer (Input → Command → Tool)

---

## ADR-G4-004: Input → Command → Tool Routing Architecture

**Context:**

Gate 4 integrates input binding with tool activation. The challenge is to create a clean chain:

```
Input (physical: key/mouse)
  ↓
BindingSet.command_for(input)
  ↓
Command (semantic: "Move", "Undo", etc.)
  ↓
Application.dispatch_command(command)
  ↓
Tool Activation or UI Action
```

We need this chain to:
1. Keep Input Binding and Tool Management separate
2. Allow future tool activation patterns (Pattern A + B)
3. Handle non-tool commands (Undo, Selection, Display)
4. Remain window-independent and testable

**Decision:**

Implement a three-stage dispatch system in `Application`:

1. **Stage 1 — Input → Command (BindingSet)**
   - Input objects describe physical events (key, mouse, wheel)
   - BindingSet maps inputs to command strings
   - Context-aware (global vs topology mode)
   - Remains unchanged from existing design

2. **Stage 2 — Command → Handler (Application.dispatch_command())**
   - Application receives command string
   - Dispatcher routes to appropriate handler:
     - Tool commands → `_activate_tool_on_selection(command)`
     - History commands → `scene.history.undo()` / `redo()`
     - Selection commands → `selection.mode = ...`
     - Display commands → `display.cycle_mode()` / `toggle_wireframe()`
     - Other commands → return False
   - Returns boolean: True if handled, False otherwise

3. **Stage 3 — Tool Activation (ToolManager.activate_command())**
   - Application checks selection status
   - Calls `tool_manager.activate_command(command)`
   - ToolManager handles Tool registration + instantiation
   - Enables both Pattern A (explicit wait) and Pattern B (immediate)

**Rationale:**

- **Separation of concerns:** BindingSet ↔ Application ↔ ToolManager are independently testable
- **Flexibility:** Input binding can be changed (keymap.json) without affecting tool code
- **Future patterns:** Pattern B can be added without changing the dispatcher
- **Window independence:** Application doesn't import/depend on Pyglet or input loop

**Implications:**

1. Window/Input handlers (future) will call `app.dispatch_command(command)` when user provides input
2. Tool activation automatically checks selection:
   - No selection → tool activation fails (returns False)
   - With selection → tool activates in waiting state (Pattern A)
3. Non-tool commands handled directly by Application
4. History, display, selection changes are local Application updates

**Trade-offs:**

- **Pro:** Clean separation, testable, flexible
- **Con:** Three-stage dispatch adds minor latency (negligible for interactive UI)
- **Pro:** Makes input remapping trivial (only BindingSet changes)
- **Con:** Tool activation hardcoded to Pattern A (explicit wait) by default

**Example Usage:**

```python
# When user presses M key:
input_m = Input("key", "m")
command = app.bindings.command_for(input_m)  # → "Move"
result = app.dispatch_command(command)       # → True if selection exists

# When user presses Ctrl+Z:
input_undo = Input("key", "z", frozenset(["ctrl"]))
command = app.bindings.command_for(input_undo)  # → "Undo"
result = app.dispatch_command(command)           # → True
```

---

## ADR-G4-005: Selection-Gated Tool Activation

**Context:**

Tools require something to work on (vertices to move, rotate, scale). Empty selection should not activate tools.

Question: Where should this check live?

Options:
- A) ToolManager: "I don't activate tools without checking"
- B) Application: "I check selection before asking ToolManager"
- C) Window loop: "I check before dispatching"

**Decision:**

Check selection in `Application._activate_tool_on_selection()`.

```python
def _activate_tool_on_selection(self, command: str) -> bool:
    if self.selection.is_empty():
        return False  # ← Check here
    self.tool_manager.activate_command(command)
    return True
```

**Rationale:**

- **Responsibility:** Application is responsible for user-facing constraints
- **Separation:** ToolManager shouldn't know about Selection (tool-agnostic)
- **Testing:** Easy to test: `dispatch_command("Move") returns False when selection empty`
- **Future:** Different tools might have different requirements (Pattern B selection-immediate)

**Implications:**

- Tool activation always fails silently if no selection exists
- Future patterns (Pattern B) can override this (e.g., "Alt+M creates and extrudes")
- Selection mode changes don't automatically deactivate tools

---

## ADR-G4-006: Command Dispatch Completeness vs Minimalism

**Context:**

How many commands should `Application.dispatch_command()` handle?

All non-tool commands (Undo, Redo, Display, Selection)?
Or just Route tool commands and defer others?

**Decision:**

Application handles ALL commands: tool + non-tool.

Supported in Gate 4:
- Move, Rotate, Scale (→ ToolManager)
- Undo, Redo (→ History)
- Cancel (→ Active tool.cancel())
- Set Vertex/Edge/Face Mode (→ Selection.mode)
- Cycle Display Mode (→ Display)
- Toggle Wireframe (→ Display)
- Clear Selection (→ Selection)

Returns `False` for unknown commands.

**Rationale:**

- **Unified entry point:** Single `dispatch_command()` for ALL user actions
- **Testing:** Single method to mock and test
- **Future:** Easy to add new commands (Display Shading, Camera Preset, etc.)
- **Window integration:** Window loop calls one method for everything

**Trade-off:**

- **Pro:** No need to duplicate command routing logic in window handlers
- **Con:** Application becomes "command hub" (could split later if needed)

**Future Extension:**

```python
# Could be refactored to delegation pattern if it grows:
self._tool_dispatcher(command) or \
self._history_dispatcher(command) or \
self._selection_dispatcher(command) or \
self._display_dispatcher(command)
```

For Gate 4, single flat method is sufficient.

---

## ADR-G4-007: Input Binding Remains Read-Only for Tools

**Context:**

BindingSet exists. Tools can query it. Should tools be able to change bindings at runtime?

**Decision:**

Tools CANNOT modify BindingSet. Input binding is Application-owned and immutable at tool level.

**Rationale:**

- **Single responsibility:** Tools operate on geometry, not input configuration
- **Predictability:** User bindings don't change mid-interaction
- **Isolation:** Tool changes can't break input layer
- **Future remapping:** Only user/preferences system changes bindings

**Implication:**

Future dynamic remapping (e.g., Alt+X for Cut) requires Application-level request, not Tool-initiated.

---

## Implementation Checklist (Gate 4)

- [x] BindingSet supports context-aware command resolution
- [x] Application.dispatch_command() routes all commands
- [x] _activate_tool_on_selection() gates on empty selection
- [x] ToolManager.activate_command() handles registration + instantiation
- [x] All commands testable (Input → Command → Handler verified)
- [x] Window-independent (no Pyglet imports in Application)

---

## Future Gates Enabled

These ADRs enable future work without architectural changes:

1. **Gate 4.9-4.10 (planned):** Window event loop + Pyglet integration
   - Window translates Pyglet events → Input objects
   - Calls `app.dispatch_command(command)`
   - No changes to Application or Tools needed

2. **Future Gate (Modeling UX Lab):** UX pattern experimentation
   - Pattern B: `activate_command(cmd, context=selection)` for immediate start
   - Tool stacking: nested tool contexts
   - No changes to dispatcher needed

3. **Future Gate (Interaction Enhancements):** Tool options
   - Alt+M for "Move with specific mode"
   - Could map to new commands or pattern variants
   - Binding system unchanged

---

## Summary

Gate 4's Input-Command-Tool architecture is:
- ✅ Clean (three independent stages)
- ✅ Flexible (supports future patterns)
- ✅ Testable (all stages independently testable)
- ✅ Window-independent (no Pyglet in production code)
- ✅ Future-proof (enable multiple UX models)

The door is open for experimentation without architectural rework.

