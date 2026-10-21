# WP-04 Implementation Impact — Core Promotion (Option C)

**Status:** Impact Analysis for Decision Support  
**Based on:** Core Architecture Reassessment (Option C)  
**Date:** 2026-09-01

---

## Overview

If **Option C is approved** (promote Transform Ops to Core + document precedent), the following changes apply to WP-04 Gates 3–5.

If **Option B is chosen** (keep external), skip to "Alternative: Option B Implementation" section.

---

## CHANGE 1: Gate 3 Updated — Add Transform Ops Promotion

### New Task 3.13: Promote Transform Operations to src/core

**Objective:** Migrate RotateOperation and ScaleOperation from experiment fork to production Core

**Duration:** 1 work session (parallel to other Gate 3 tasks)

**Pre-Requisites:**
- [ ] Core Reassessment approved (this decision)
- [ ] Tests passing in experiment (verified: 25 tests ✓)
- [ ] No breaking changes to Core APIs

**Tasks:**

#### Task 3.13.1: Copy transform.py to src/core/operations/

```bash
# Source
experiments/mirai_bastel_core_V1/mirai_bastel_core/operations/transform.py (260 lines)

# Destination
src/core/operations/transform.py

# Change: None (exact copy)
```

**Acceptance:**
- [ ] File exists at `src/core/operations/transform.py`
- [ ] 260 lines intact
- [ ] No code changes

---

#### Task 3.13.2: Update src/core/__init__.py

**Add exports:**

```python
# src/core/__init__.py

from .operations.transform import (  # NEW
    RotateOperation,
    ScaleOperation,
    VertexTransformOperation,      # base class
    VertexTransformCommand,        # history command
    rotate_around_axis,            # helper (if needed by users)
)
```

**Acceptance:**
- [ ] Imports resolve without error
- [ ] `from mirai_bastel_core import RotateOperation` works
- [ ] `from mirai_bastel_core import ScaleOperation` works
- [ ] Backward compatibility check: existing imports still work ✓

---

#### Task 3.13.3: Migrate Tests

**Source:** `experiments/mirai_bastel_viewport_V1/tests/test_transform_operations.py` (25 tests)

**Destination:** `src/tests/test_transform_operations.py`

**Changes to test file:**
- Update import paths from experiment fork to Core
- Remove sys.path manipulation (not needed in src/ tests)
- Keep test logic identical

**Before (experiment):**
```python
import sys
from pathlib import Path
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent / "mirai_bastel_core_V1"))
from mirai_bastel_core import RotateOperation, ScaleOperation, ...
```

**After (src/tests):**
```python
from mirai_bastel_core import RotateOperation, ScaleOperation, ...
```

**Acceptance:**
- [ ] All 25 tests pass in new location
- [ ] Imports clean (no sys.path hacks)
- [ ] Test logic unchanged

---

#### Task 3.13.4: Documentation

**Update:** `docs/architecture/CORE_V1_FREEZE.md` §7

**Add to Freeze-Rule section:**

```markdown
## 7.1 Pattern-Filling Operations (Precedent)

Under the Freeze-Rule, pattern-filling operations may be promoted to Core if:

1. **Motivated by concrete WP requirement** — not speculative
2. **Well-tested** — minimum 20 unit tests demonstrating correctness
3. **No new Core APIs/data structures** — uses only existing Operation contract + Mesh APIs
4. **Isolated implementation** — changes only to operations/ subdirectory, no mesh.py/operation.py/history.py modifications

Example: RotateOperation and ScaleOperation were added under this rule in WP-04
because:
- Concrete requirement: WP-04 tools need rotate/scale
- Tested: 25+ unit tests from WP-03
- Pattern-filling: Uses Operation contract proved by MoveOperation
- Isolated: File `operations/transform.py`, no Core changes

This rule does NOT apply to:
- Topology-mutating operations (already in Core, use MeshStateCommand)
- Architectural operations (change-set, provenance, constraints)
- UI/Viewport/Renderer concerns
- Future major subsystems (Rigging, Morphing, Animation) — those require separate architectural work
```

**Update:** `ROADMAP.md` WP-04 section

```markdown
### WP-04 — Production Foundation

**Status:** In Progress (Gate 2 review)

**Scope:**
- Application + Viewport foundation
- Interaction framework + default tools (Move, Rotate, Scale)
- History + Undo/Redo
- Selection + Display

**Core Extension (under Freeze-Rule §7):**
- Promotion of RotateOperation + ScaleOperation from WP-03 experiment to `src/core/operations/transform.py`
- Rationale: concrete requirement, well-tested, pattern-filling only
```

**Acceptance:**
- [ ] CORE_V1_FREEZE.md §7.1 added with clear precedent
- [ ] ROADMAP.md WP-04 section updated
- [ ] Commit message references this decision

---

### Gate 3 Revised Checklist

**Add to Gate 3 Acceptance Criteria:**

- [ ] Transform ops promoted to `src/core/operations/transform.py`
- [ ] `src/core/__init__.py` exports RotateOperation, ScaleOperation
- [ ] 25 transform operation tests passing in `src/tests/`
- [ ] CORE_V1_FREEZE.md §7.1 documented
- [ ] All Core tests still pass (29 + 25 = 54 total) ✓

---

## CHANGE 2: Gate 4 Simplified — Transform Tools Import from Core

### Simplified Task 4.4: Extract RotateTool & ScaleTool (Revised)

**Previous approach (Option B):** Duplicate Operation classes locally

**New approach (Option C):** Import from Core (like MoveTool does)

#### Task 4.4 Revised

**Goal:** Extract RotateTool and ScaleTool from experiment to production, with Core operations

**Files:**
- Source: `experiments/mirai_bastel_viewport_V1/viewport/transform_tool.py`
- Destination: 
  - `src/mirai/interaction/tools/rotate.py` (RotateTool class only)
  - `src/mirai/interaction/tools/scale.py` (ScaleTool class only)

**Changes to tools:**

```python
# src/mirai/interaction/tools/rotate.py

from mirai.core import RotateOperation, OperationContext, VertexId  # Core imports
from .tool import Tool  # production imports
from .constraints import AxisConstraint

class RotateTool(Tool):
    """Rotate tool using Core RotateOperation."""
    
    def _on_begin(self, context):
        # Identical to experiment, but imports RotateOperation from Core
        self._operation = RotateOperation(context)
        self._operation.begin()
```

**Difference from Option B:**
```
Option B (External): from mirai.interaction.operations import RotateOperation
Option C (Core):     from mirai.core import RotateOperation  ← simpler, reusable
```

**Acceptance:**
- [ ] Import `from mirai.core import RotateOperation` works
- [ ] Tool class logic identical to experiment
- [ ] Tests verify tool+operation integration

---

## CHANGE 3: Gate 4 Updated — Simplified Task 4.5

### Task 4.5 Simplified: Tool Routing (No Change to Pattern)

**Status:** No change to logic, only simplification

```python
# src/mirai/interaction/routing.py

from mirai.core import MoveOperation, RotateOperation, ScaleOperation
from .tools.move import MoveTool
from .tools.rotate import RotateTool
from .tools.scale import ScaleTool

def tool_for_command(command: str) -> type[Tool] | None:
    """Route command to tool class."""
    mapping = {
        commands.MOVE: MoveTool,      # Core → MoveOperation
        commands.ROTATE: RotateTool,  # Core → RotateOperation (now available)
        commands.SCALE: ScaleTool,    # Core → ScaleOperation (now available)
    }
    return mapping.get(command)
```

**Cleaner because:** All three tools follow identical pattern (Core ops available for all)

---

## CHANGE 4: Gate 4 Integration Tests — Updated

### Task 4.7 Revised: Integration Tests

**What stays the same:**
- 20+ integration tests covering tool lifecycle
- Full input→tool→operation→history pipeline

**What improves:**
- Tests can directly verify Core operation behavior
- No need to mock Operation classes

**Before (Option B):**
```python
def test_rotate_and_undo():
    app = Application()
    app.init_scene()
    app.dispatch_command("R")  # Activate RotateTool
    tool = app.tool_manager.active_tool
    
    # Simulate interaction
    tool.begin(...)
    tool.update(axis=(0,0,1), angle=0.5)
    tool.commit()
    
    # History from experiment RotateOperation
    assert len(app.scene.history) == 1
```

**After (Option C):**
```python
def test_rotate_and_undo():
    app = Application()
    app.init_scene()
    app.dispatch_command("R")
    tool = app.tool_manager.active_tool
    
    # Same test, but RotateOperation is from Core
    # Tests can import and verify:
    from mirai.core import RotateOperation
    assert isinstance(tool._operation, RotateOperation)
    # All 25 core tests still passing ✓
```

**Benefit:** Single source of truth for transform operations (in Core tests)

---

## CHANGE 5: Gate 8 Validation — Updated

### Task 8.1 Revised: Test Coverage

**Before (Option B):**
```
Core tests:       29 (Core + move)
Production tests: 50+ (tools + integration)
Transform tests:  25 (experiment, not migrated)
TOTAL:            ~104 tests
```

**After (Option C):**
```
Core tests:       29 + 25 = 54 (Core includes transforms)
Production tests: 50+ (tools + integration)
TOTAL:            ~104 tests (same, but organized better)
```

**Benefit:** Core regression suite automatically includes transform stability

---

## CHANGE 6: Documentation & Architecture Docs

### Update Diagrams in Architecture Docs

**Current (conceptual):**
```
Production Application
    ├── Interaction (Tools)
    └── Core V1 (frozen)
```

**Updated (concrete):**
```
src/
├── core/
│   ├── mesh.py
│   ├── operation.py
│   ├── operations/
│   │   ├── move.py         [WP-02]
│   │   └── transform.py    [WP-03, promoted under Freeze-Rule §7.1]
│   ├── selection.py
│   └── history.py
│
├── mirai/
│   ├── interaction/
│   │   ├── tool.py
│   │   └── tools/
│   │       ├── move.py     [imports MoveOperation from Core]
│   │       ├── rotate.py   [imports RotateOperation from Core]
│   │       └── scale.py    [imports ScaleOperation from Core]
│   └── application.py
```

### Update INPUT_COMMAND_TOOL_CONTRACT.md

**Add note:**
```markdown
### Transform Operations Placement

Rotate and Scale operations were promoted to `src/core/operations/transform.py` in WP-04
under Freeze-Rule §7 (pattern-filling operations).

This means:
- All three transform types (Move/Rotate/Scale) now live in Core
- Tools import from Core: `from mirai.core import RotateOperation, ScaleOperation`
- Unified pattern: Tool → Core Operation → Mesh mutation

This decision was made because:
1. Operations follow the Operation contract proven by MoveOperation
2. No new Core APIs needed (uses existing interfaces)
3. Well-tested (25+ unit tests from WP-03)
4. Improves architecture consistency
```

---

## Summary: Option C Implementation Overhead

### New/Changed Files

| File | Change | Effort | Gate |
|------|--------|--------|------|
| `src/core/operations/transform.py` | Create (copy) | ~5 min | 3.13.1 |
| `src/core/__init__.py` | Update exports | ~5 min | 3.13.2 |
| `src/tests/test_transform_operations.py` | Create (migrate) | ~10 min | 3.13.3 |
| `docs/architecture/CORE_V1_FREEZE.md` | Update §7 | ~10 min | 3.13.4 |
| `docs/architecture/ROADMAP.md` | Update WP-04 note | ~5 min | 3.13.4 |
| `src/mirai/interaction/tools/rotate.py` | Create (simpler imports) | ~5 min | 4.4 |
| `src/mirai/interaction/tools/scale.py` | Create (simpler imports) | ~5 min | 4.4 |

**Total overhead:** ~45 minutes (part of Gates 3–4 anyway)

**Benefit:** Cleaner architecture, no duplication, clear precedent for future

---

## Alternative: Option B Implementation (If Chosen)

If **Option B is approved** (keep Transform ops external), use this instead:

### Task 3-ALT: Create Production Operations Package

**Goal:** Implement Rotate/Scale operations in production layer

**New directory:** `src/mirai/interaction/operations/`

```python
# src/mirai/interaction/operations/rotate.py

from dataclasses import dataclass
from typing import Iterable
import math

from mirai.core import (
    Operation, OperationContext, Mesh, Position, VertexId,
)

# Copy vector math from transform.py
def _add(a: Position, b: Position) -> Position:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

# ... (rest of VertexTransformOperation base class + RotateOperation)

class RotateOperation(VertexTransformOperation):
    # ...identical to Core version, but local to production
```

**Challenges with Option B:**
- Need to copy 180 lines of Operation logic (duplication)
- Tools import from `mirai.interaction.operations` instead of Core (inconsistent)
- Experiment and production have divergent operation implementations
- Future WP can't easily share Transform ops

**Test organization for Option B:**
```
src/tests/
├── test_application.py
├── test_interaction/
│   ├── test_tool_manager.py
│   ├── test_move_tool.py
│   ├── test_rotate_tool.py    (no Core rotate tests)
│   └── test_scale_tool.py     (no Core scale tests)
└── test_operations/
    ├── test_rotate_operations.py  (local impl)
    └── test_scale_operations.py   (local impl)

Total: 50 tests (no Core extension)
```

---

## Decision Point: Which Option to Proceed With?

| Question | Answer for Option C | Answer for Option B |
|----------|-------------------|-------------------|
| Clean architecture? | ✓ YES | ~ MIXED |
| No duplication? | ✓ YES | ✗ 180 lines duplication |
| Freeze-compliant? | ✓ YES (documented) | ✓ YES (strictest) |
| Test organization? | ✓ CLEAN | ~ SCATTERED |
| Future reuse? | ✓ HIGH | ~ LOW |
| Gate 3 complexity? | ✓ SAME | ✓ SAME |

---

## Appendix: Exact Files for Option C

**If Option C approved, these files must be changed/created:**

### Phase 1: Core (Gate 3.13)

```
src/core/operations/transform.py          [NEW] copy from experiment
src/core/__init__.py                      [EDIT] add exports
src/tests/test_transform_operations.py    [NEW] migrate from experiment
docs/architecture/CORE_V1_FREEZE.md       [EDIT] document §7.1
docs/architecture/ROADMAP.md              [EDIT] update WP-04 note
```

### Phase 2: Production (Gate 4)

```
src/mirai/interaction/tools/rotate.py     [NEW] import from Core
src/mirai/interaction/tools/scale.py      [NEW] import from Core
src/mirai/interaction/routing.py          [EDIT] route to Core ops
```

### Phase 3: Tests (Gate 4, 8)

```
tests/test_tool_integration.py            [EDIT] verify Core op imports
tests/test_transform_integration.py       [NEW] full pipeline (Core→Tool)
```

---

**End of Impact Analysis**

Use this document to:
1. Brief team on Option C implications
2. Verify Gate 3–4 planning accommodates promotions
3. Ensure test migration plan is clear
4. Document precedent for future Core extensions
