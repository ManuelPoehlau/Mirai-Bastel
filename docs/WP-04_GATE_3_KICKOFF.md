# WP-04 Gate 3 Kickoff

**Status:** Ready to Execute  
**Date:** 2026-09-01  
**Authority:** ADR-001 (Architecture Decision Record)  
**Scope:** Application & Viewport Foundation

---

## ✓ Decision Clarity (from ADR-001)

**ADR-001 has authorized Core V1 extension for Transform Operations.**

### What Goes Into Core

**Definitive (no reassessment needed):**

```
src/core/operations/
├── move.py               (existing, WP-02)
├── transform.py          (NEW: Rotate/Scale/Constraints)
│   ├── RotateOperation
│   ├── ScaleOperation
│   └── AxisConstraint    (NEW: constrain transforms to X/Y/Z axis)
└── topology.py           (existing, WP-01A)
```

**Updated src/core/__init__.py exports:**
```python
from .operations.move import MoveOperation
from .operations.transform import (
    RotateOperation,
    ScaleOperation,
    AxisConstraint,           # NEW
)
```

### Why This Path

- Core contract (Operation) proven by MoveOperation
- Transform ops use existing Mesh APIs only
- AxisConstraint enables axis-restricted interaction
- Unified pattern: Move/Rotate/Scale all from Core
- WP-03 experiment already has these (migration task, not new work)

---

## Gate 3 Implementation Directive

### What This Phase Accomplishes

**Extract experiment components → establish production boundaries**

```
Production Application Layer (NEW)
    ├── Application class (lifecycle, command dispatch)
    ├── Tool framework (ToolManager, Tool base class)
    ├── Tools (MoveTool, RotateTool, ScaleTool)
    ├── Input/Bindings
    ├── Viewport (Camera, Picking, Display)
    └── Main entry point

DEPENDS ON ↓

src/core/ (Extended per ADR-001)
    ├── Mesh + Selection + History (existing)
    └── Operations (existing move.py + NEW transform.py)
```

### Core Task List for Gate 3

**Task 3.1–3.12:** Extract components (original plan unchanged)

**Task 3.13 (NEW): Promote Transform Ops to Core**

```python
# Immediate action:
1. Copy experiments/mirai_bastel_core_V1/mirai_bastel_core/operations/transform.py
   → src/core/operations/transform.py (260 lines)

2. Update src/core/__init__.py
   - Add: RotateOperation, ScaleOperation, AxisConstraint exports

3. Migrate tests: test_transform_operations.py
   from experiments/.../tests/ → src/tests/

4. Update docs/architecture/CORE_V1_FREEZE.md
   - Note: Transform ops added under ADR-001 authorization
   - Reference ADR-001 for precedent

Effort: 45 minutes (minimal, straightforward copy/migrate)
```

### AxisConstraint Explanation

**What it is:**
- Enum/class that restricts transform deltas to specific axes
- Example: `AxisConstraint.X_ONLY` → only move/rotate/scale along X
- Integrated into RotateOperation + ScaleOperation

**Why in Core:**
- Transform contract completeness (Move/Rotate/Scale all support constraints)
- Reusable for future tools (Gizmo-based transforms, etc.)
- Not a new capability, just parameter to existing operations

**In Production:**
- Tools can set constraints during interaction
- Example: `shift+X` locks to X-axis while dragging

---

## Gate 3 Tasks (Updated)

### Prerequisite: Core Extension (Task 3.13)

**Before** extracting tools, ensure transform ops in Core.

**Order:**
1. Task 3.13: Promote transform.py to Core (45 min)
2. Tasks 3.1–3.12: Extract production components (as planned)
3. (Tools will import from Core automatically)

### Task Sequence

| Task | What | Where | Effort |
|------|------|-------|--------|
| **3.13** | Copy transform.py to Core | src/core/operations/ | 45 min |
| 3.1 | Create src/mirai/ structure | src/mirai/ | 15 min |
| 3.2–3.6 | Extract components | src/mirai/interaction/, viewport/ | 2 hrs |
| 3.7 | Application class | src/mirai/application.py | 1 hr |
| 3.8–3.10 | Rendering + Window adapter | src/mirai/viewport/ | 1.5 hrs |
| 3.11–3.12 | Tests + Smoke test | tests/ | 1 hr |
| **3.13** | *(already counted above)* | | |

**Total:** 6–7 hours (3–4 work sessions)

---

## Gate 3 Acceptance Criteria (Unchanged)

- [ ] src/mirai/ structure created
- [ ] All components extracted + imports resolve
- [ ] `python src/main.py` launches window with cube
- [ ] 80+ unit tests pass (no window dependency)
- [ ] No Pyglet imports outside viewport/window.py + main.py
- [ ] **NEW:** src/core/operations/transform.py exists + exports correct
- [ ] **NEW:** 25 transform operation tests pass in src/tests/

---

## Gate 4: Interaction & Tools (Unchanged from Plan)

### What Gate 4 Does

**Wire Input→Binding→Command→Tool→Operation→History pipeline**

```
Input (keyboard/mouse)
    ↓ Input binding
Binding (resolves to Command)
    ↓ Context hierarchy
Command (M/R/S/Undo/Redo/etc.)
    ↓ Tool routing
Tool (MoveTool/RotateTool/ScaleTool)
    ↓ Operation dispatch
Operation (from src/core)
    ├── MoveOperation        (existing)
    ├── RotateOperation      (promoted in Gate 3.13)
    ├── ScaleOperation       (promoted in Gate 3.13)
    └── AxisConstraint       (promoted in Gate 3.13)
    ↓
Mesh.set_vertex_position()
    ↓
HistoryStack.push()
```

### Gate 4 Tasks (No Changes)

| Task | Duration | Key Output |
|------|----------|-----------|
| 4.1 | 1 hr | ToolManager class |
| 4.2 | 1 hr | MoveTool extracted (imports from Core) |
| 4.3 | Skipped | (Transform ops already in Core from 3.13) |
| 4.4 | 1 hr | RotateTool/ScaleTool extracted (import from Core) |
| 4.5 | 1 hr | Tool routing (M/R/S → tools) |
| 4.6 | 1 hr | Application.dispatch_command() |
| 4.7 | 1 hr | Integration tests (20+) |

**Total:** 2 work sessions (7 hours)

---

## Why ADR-001 Removes Uncertainty

**Before (Gate 2 Analysis):**
- "Should we promote transform ops?"
- "Is freeze violation acceptable?"
- "Option A/B/C comparison needed"

**After (ADR-001 Decision):**
- ✓ Promotion is authorized
- ✓ No freeze violation (ADR-001 is the freeze policy, updated)
- ✓ Implementation is clear: migrate ops, build on them

**Effect:**
- Gate 3–4 execution is straightforward
- No architecture debates during implementation
- Team focus: clean code, good tests

---

## File Locations (Concrete)

### Gate 3.13: What Gets Moved

```
BEFORE:
experiments/mirai_bastel_core_V1/
├── mirai_bastel_core/
│   └── operations/
│       └── transform.py          (260 lines, RotateOp + ScaleOp + Constraint)
└── tests/
    └── test_transform_operations.py (25 tests)

AFTER (Gate 3):
src/
├── core/
│   └── operations/
│       ├── move.py               (existing)
│       └── transform.py          (migrated from experiment)
└── tests/
    ├── test_core.py              (29 existing tests)
    ├── test_transform_operations.py (25 migrated tests)
    └── test_*                    (new production tests)
```

### Gate 3–4: Production Structure

```
src/mirai/
├── application.py                (Application class + lifecycle)
├── main.py                        (Entry point + Pyglet window)
├── interaction/
│   ├── tool.py                   (Tool base class)
│   ├── input.py                  (Input binding system)
│   ├── commands.py               (Command enum)
│   ├── bindings.py               (Default keybindings)
│   ├── tool_manager.py           (NEW, manages active tool)
│   └── tools/
│       ├── move.py               (MoveTool → imports MoveOperation)
│       ├── rotate.py             (RotateTool → imports RotateOperation)
│       └── scale.py              (ScaleTool → imports ScaleOperation)
└── viewport/
    ├── camera.py                 (Orbit/pan/zoom)
    ├── picking.py                (Ray-cast selection)
    ├── display.py                (Shaded/Flat/Wireframe modes)
    ├── render.py                 (Geometric rendering)
    ├── window.py                 (Pyglet adapter)
    └── vecmath.py                (Vector utilities)
```

---

## Team Assignments (Suggested)

### Task 3.13 (Core Migration)
- **Responsibility:** 1 developer (experienced with Core)
- **Duration:** 45 minutes
- **Steps:**
  1. Copy transform.py
  2. Update __init__.py
  3. Migrate tests
  4. Verify all tests pass (54/54: 29 core + 25 transform)

### Tasks 3.1–3.12 (Production Extraction)
- **Responsibility:** 2–3 developers
- **Parallel:** Can start after 3.13 (or concurrent)
- **3.2–3.6:** One dev extracts components
- **3.7–3.10:** One dev builds Application + window
- **3.11–3.12:** QA/testing dev writes tests

### Gate 4 (Tool Integration)
- **Responsibility:** 2 developers
- **Duration:** 2 sessions (14 hours)
- **Lead:** One developer on ToolManager, tool routing
- **Support:** One developer on tool implementations (Move/Rotate/Scale)

---

## Approval Gate (Triage to Gate 3)

**Before Gate 3 can begin:**

- [ ] ADR-001 understood and accepted
- [ ] Core extension scope clear (Move/Rotate/Scale/Constraints)
- [ ] Gate 3 tasks assigned
- [ ] Test environment ready
- [ ] Repository branch ready for changes

**Sign-off:**

```
Gate 2 Analysis Complete: _______  Date: ___
Decision (ADR-001): Approved
Gate 3 Kickoff: Ready to execute
```

---

## Success Criteria (End of Gate 3)

- [ ] `python src/main.py` launches window with cube
- [ ] M key activates Move tool (preview + commit)
- [ ] Esc cancels without history
- [ ] Ctrl+Z undoes move
- [ ] 80+ unit tests pass (no window dependency)
- [ ] No Pyglet imports outside viewport/window.py
- [ ] Code coverage ≥85%
- [ ] All docstrings complete
- [ ] Ready for Gate 4 (tool integration)

---

## Success Criteria (End of Gate 4)

- [ ] R key activates Rotate tool
- [ ] S key activates Scale tool
- [ ] All tools follow Move pattern (preview → commit/cancel)
- [ ] Tools import operations from Core (not duplicated locally)
- [ ] 20+ integration tests pass
- [ ] Undo/Redo works for all transforms
- [ ] Ready for Gate 5 (selection + display)

---

## Timeline (No Changes from Original Plan)

| Phase | Sessions | Duration |
|-------|----------|----------|
| Gate 3 (Application) | 3–4 | ~24 hours |
| Gate 4 (Interaction) | 2 | ~14 hours |
| Gate 5 (Selection) | 2 | ~14 hours |
| Gate 6–7 (Input + Camera) | 2 | ~14 hours |
| Gate 8–12 (Validation + Review) | 5 | ~35 hours |
| **TOTAL** | 13–15 | **~2–3 weeks** |

---

## Questions Resolved (No More Uncertainty)

| Q | Old Answer | New Answer (ADR-001) | Status |
|---|-----------|----------------------|--------|
| Promote Transform Ops? | Maybe? | ✓ YES (authorized) | ✓ CLEAR |
| Freeze violation? | Debate needed | ✓ NO (ADR-001 is policy) | ✓ CLEAR |
| Where do constraints go? | Unclear | ✓ In Core with ops | ✓ CLEAR |
| Can Gate 3 proceed? | Pending decision | ✓ YES, immediately | ✓ CLEAR |

---

## Execution Instruction

**After this kickoff approval:**

```bash
# Day 1: Core Migration (Task 3.13)
cd /path/to/mirai-bastel
git checkout wp/04-production-foundation
cd src/core/operations/
# Copy transform.py from experiment
# Update __init__.py
# Migrate tests
python -m pytest tests/test_transform_operations.py  # 25/25 pass

# Day 2–3: Production Extraction (Tasks 3.1–3.12)
mkdir -p src/mirai/{interaction,viewport,interaction/tools}
# Follow Gate Planning §3 tasks 3.1–3.12
# Extract components systematically
# Run tests after each task

# Day 3–4: Final Testing
python src/main.py              # Window launches
pytest tests/                   # 80+ tests pass
pytest --cov=src/mirai tests/   # Coverage ≥85%

# Day 5: Gate 3 Acceptance Review
# All criteria met? → Approve Gate 3
# → Proceed to Gate 4 planning
```

---

## Summary

**ADR-001 has decided:**
- ✓ Core can be extended for Transform Ops
- ✓ Move/Rotate/Scale/Constraints go in Core
- ✓ No freeze violation (ADR-001 updated policy)

**Gate 3 directive:**
- ✓ Task 3.13: Migrate transform.py to Core (45 min)
- ✓ Tasks 3.1–3.12: Extract production components (6 hrs)
- ✓ Total: 6–7 hours (one 3–4 session work block)

**Outcome:**
- ✓ Production app ready to import from Core
- ✓ Tools follow unified pattern (all use Core ops)
- ✓ Gate 4 integration straightforward

**Go/No-Go:** ✓ **GO** — Ready to execute Gate 3 immediately

---

**End of Kickoff Document**

*Based on ADR-001 authorization. No additional decision records needed.*
