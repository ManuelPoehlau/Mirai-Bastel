# WP-04 — Open Questions & Decision Log

**Date:** 2026-09-01  
**Status:** Awaiting Gate 2 Review & Decisions  
**Critical for:** Gate 3 planning

---

## Overview

Four open questions must be decided **before Gate 3 implementation** can begin. Each has concrete options and recommendations.

---

## Q1: Transform Operations Promotion to Production Core

### Question
**Should `RotateOperation` and `ScaleOperation` be promoted from experiment fork to `src/core/operations/transform.py`?**

Currently, these operations live in `experiments/mirai_bastel_core_V1/operations/transform.py` and are proven working (25 tests passing). The question is whether they count as "Core Extension" (allowed) or "Core Change" (forbidden by freeze).

### Context

**Core V1 Freeze Policy** (`docs/architecture/CORE_V1_FREEZE.md` §7):
```
Before changing the frozen Core:
1. Name concrete new requirement
2. Check if solvable with existing public APIs
3. If not: document architecture problem
4. Determine minimum Core extension needed
5. Add tests/contracts
6. Only then implement
```

**Current situation:**
- `MoveOperation` exists in `src/core/operations/move.py` (reference implementation)
- It validates the `Operation` contract (begin/update/commit/cancel)
- `RotateOperation` and `ScaleOperation` follow the **same contract exactly**
- They don't require new Core APIs or capability
- They're not new architecture — they're filling an established pattern

### Arguments FOR Promotion (Recommended)

| Argument | Strength |
|----------|----------|
| **Pattern-filling, not pattern-breaking** | HIGH |
| The Core freeze blocks design changes, not adding more of the same operation type | Rotate/Scale use the Operation contract that Move already proves | Already in development + tested | |
| **Production app needs them** | HIGH |
| WP-04 scope includes Transform tools; without production ops, tools duplicate operation logic (wasteful) | |
| **Matches historical pattern** | MEDIUM |
| When `connect_vertices` was added, it went straight to Core (operation + MeshStateCommand) | Same reasoning applies here | |
| **Minimizes code duplication** | HIGH |
| Keeping in experiment fork means tools must re-implement transform mutations | One Operation class in Core, tools stay thin | |

### Arguments AGAINST Promotion

| Argument | Strength |
|----------|----------|
| **Freeze means no changes** | MEDIUM |
| Strict interpretation: any addition is a change | Risk of setting precedent for future "just one more operation" | |
| **Transform could be wrong** | LOW |
| Rotate via Rodrigues formula unproven in production | Already tested in Viewport V1 (88 tests); risk is low | |

### Recommendation

**✓ PROMOTE to `src/core/operations/transform.py`**

**Rationale:**
1. Operations are not architectural changes, they're exercises of the established `Operation` contract
2. The freeze protects against Core redesign, not against pattern-filling
3. Move proved the contract; Rotate/Scale follow it faithfully
4. Production app needs them; keeping in experiment forces duplication
5. Tests exist and pass; risk is low

**If promoted:**
- Add to `src/core/__init__.py` exports
- Update CORE_V1_FREEZE.md to document this decision
- Add note: "Core freeze extended to include RotateOperation/ScaleOperation under contract-filling principle"
- Proceed normally to Gate 3

**If NOT promoted:**
- RotateTool/ScaleTool will implement their own `RotateVerticesCommand`/`ScaleVerticesCommand` locally
- Tools become thicker; more duplication
- Acceptable but suboptimal
- Proceed to Gate 3 with tools only (no ops)

### Decision Point

**Required before Gate 3 can start.**

**Who decides?** Human project owner + architecture review (AI or human).

**How to record decision:**
- [ ] Create `docs/architecture/DECISION_Q1_TRANSFORM_OPS.md` with final choice
- [ ] Update CORE_V1_FREEZE.md if promotion chosen
- [ ] Commit to wp/04-production-foundation branch

---

## Q2: Viewport Restructuring Feasibility

### Question
**Can `app.py` (582 lines, monolithic) be cleanly extracted into:
- Application class (window-free)
- Rendering module (geometric logic)
- Window adapter (Pyglet event bridging)?**

### Current State

`app.py` mixes:
- Event handling (on_key_press, on_mouse_drag, etc.)
- Rendering (vertex/edge/face triangle generation)
- Tool/interaction logic
- Camera/selection state
- Input dispatch

**Challenge:** All mixed in one `ModelerWindow(pyglet.window.Window)` subclass.

### Extraction Strategy

**Proposed breakdown:**

```
src/mirai/application.py
├── class Application
│   ├── __init__(scene, camera, tool_manager, bindings, display)
│   ├── init_scene()
│   ├── dispatch_command(command, context, **params)
│   ├── update_viewport(delta_t)  # called per frame
│   └── shutdown()

src/mirai/viewport/render.py
├── def compute_normals(mesh)
├── def face_triangle_arrays(mesh, face_ids)
├── def render_vertices(scene, display_state)
├── def render_edges(scene, display_state)
└── def render_faces(scene, display_state, camera)

src/mirai/viewport/window.py
└── class ModelerWindow(pyglet.window.Window)
    ├── __init__(app: Application)
    ├── on_draw()  # calls app.update_viewport(); render from app state
    ├── on_key_press(symbol, modifiers)
    ├── on_mouse_press/drag/release()
    └── on_mouse_scroll()
```

### Feasibility Assessment

**Can this work?** YES — with moderate refactoring.

**Evidence:**
1. Experiment code already separates concepts (tool.py, camera.py, picking.py exist independently)
2. app.py glues them together; extracting glue is straightforward
3. Rendering math (normals, triangles) is pure functions, easy to extract
4. Event handling is thin wrapper (only translates pyglet → Input)

**Effort:** ~1 session (Task 3.8 in Gate Planning)

**Risk:** LOW — rendering and application logic already loosely coupled

### Challenges

| Challenge | Mitigation |
|-----------|-----------|
| app.py does rendering inline during on_draw | Move rendering to separate module, call from Application.update_viewport() |
| Event handling tied to window class | Create Input adapter; window just translates pyglet events to Input |
| State scattered across methods | Consolidate in Application class (already designed for this) |

### Recommendation

**✓ Proceed with extraction** — it's straightforward and low-risk.

**Detailed plan in Gate 3 Tasks 3.7–3.9.**

### Decision Point

**No decision required** — this is a technical feasibility check (answer: yes).

**Action:** Proceed to Gate 3 with extracted structure.

---

## Q3: Single-View vs Multi-View

### Question
**Is single perspective camera sufficient for WP-04, or should we include Front/Back/Left/Right/Top/Bottom orthographic views?**

### Context

**Mirai/Wings3D pattern:** Multiple orthographic views + perspective, all updating simultaneously.

**Current implementation:** Single perspective camera only.

**WP-04 scope:** Minimal application foundation (not feature-complete modeler).

### Arguments FOR Single View (Recommended)

| Argument | Strength |
|----------|----------|
| **Scope discipline** | HIGH |
| WP-04 goal: prove production architecture, not complete modeler feature set | Multi-view is nice-to-have, not foundational | |
| **Simpler proof** | HIGH |
| Single viewport easier to debug, extend, test | UI layout complexity introduced by multi-view can wait | |
| **Already proven** | MEDIUM |
| Viewport V1 works with single perspective; no blocker for WP-04 | |
| **Future extension** | MEDIUM |
| Multi-view camera system is orthogonal feature; can be added in later WP | No architectural barrier | |

### Arguments FOR Multi-View

| Argument | Strength |
|----------|----------|
| **User expectation** | MEDIUM |
| "Modeler" implies multiple views in user's mind | Single view feels incomplete | |
| **Workflow familiarity** | LOW |
| Users expect Front/Top/Perspective quad layout | Not required for WP-04 validation | |

### Recommendation

**✓ SINGLE VIEW for WP-04**

**Rationale:**
1. WP-04 is architecture proof, not feature-complete modeler
2. Multi-view adds UI layout complexity (window splitting, view management)
3. Single perspective + orbit/pan/zoom is sufficient for validation
4. Multi-view is cleanly extensible in future WP (no architectural changes needed)
5. Keeping scope tight reduces risk and keeps focus on production boundaries

**For future multi-view WP:**
- Decouple viewport rendering (one module per view)
- Manage view transforms + orthographic/perspective toggles
- Sync selection/tool state across views
- No Core changes required

### Decision Point

**No formal decision required** — scope decision is WP-04 design principle.

**Action:** Keep single perspective; document as scope boundary in ROADMAP.md

---

## Q4: Undo/Redo UI Integration

### Question
**How deep should Undo/Redo integration go in WP-04?**

### Options

**Option A: Keybindings only** (Current)
- Ctrl+Z: Undo (calls `history.undo()`)
- Ctrl+Y: Redo (calls `history.redo()`)
- No UI feedback beyond state change
- No undo history panel/list

**Option B: Add visual feedback**
- Show last action name in status bar ("Last: Move Vertices")
- Show undo/redo button state (enabled/disabled)
- Still no history panel

**Option C: Full history UI**
- List of history entries
- Click to jump to any state
- Visual diff preview
- Full history browser

### Arguments FOR Option A (Recommended)

| Argument | Strength |
|-----------|----------|
| **Scope discipline** | HIGH |
| WP-04 proves architecture, not UI completeness | Keybindings prove History works | |
| **Simple to test** | HIGH |
| No UI components to build; just command dispatch | Clean separation: Core History vs UI layer | |
| **Extensible** | MEDIUM |
| Adding UI feedback later doesn't require Core changes | Can build UI on top of existing History API | |

### Arguments FOR Option B

| Argument | Strength |
|-----------|----------|
| **User feedback** | MEDIUM |
| Knowing "what would undo" reduces confusion | Not critical for WP-04 validation | |
| **Minimal effort** | MEDIUM |
| Status bar text + button state is simple | Can add in Gate 6–7 if time | |

### Arguments AGAINST Option C

| Argument | Strength |
|-----------|----------|
| **Out of scope** | HIGH |
| Full history UI is feature work, not architecture | Belongs in future WP (properties/UI framework) | |
| **Complexity** | HIGH |
| Requires state snapshots, diff visualization, jump-to logic | Not needed to prove History contract | |

### Recommendation

**✓ OPTION A: Keybindings only**

**Rationale:**
1. WP-04 scope: prove architecture, not build UI
2. Ctrl+Z/Y work; that's sufficient validation
3. History API is proven by Core tests (29/29 passing)
4. Status bar/UI enhancements → future WP
5. Keeps Gate 3–8 focused on production boundaries

**Future WP can add:**
- Status bar display ("Last: Move 3 vertices")
- Undo/Redo buttons (state-aware)
- History panel (jump to any state)
- Action previews
- Diff visualization

**No Core changes needed** — History API already supports all of this.

### Decision Point

**No decision required** — this is UX scope (Option A is the baseline).

**Action:** Keybindings only in WP-04; document in ROADMAP.md

---

## Decision Recording Template

When each question is decided, use this template:

```markdown
## Decision: [Q1/Q2/Q3/Q4] — [Title]

**Question:** [What was asked]

**Decision:** [A/B/C option chosen]

**Rationale:** [Why this choice]

**Date:** [YYYY-MM-DD]

**Decided by:** [Human/AI, name/role]

**Impact:**
- [ ] Architecture: [any changes needed]
- [ ] Scope: [in/out of WP-04]
- [ ] Timeline: [gates affected]

**Documented in:** [PR/commit/file reference]
```

---

## Summary: What Needs Decision Before Gate 3

| Question | Decision Type | Impact | Recommendation | Prerequisite |
|----------|---------------|--------|-----------------|--------------|
| Q1 | Architecture | HIGH | Promote Transform Ops | Core freeze review |
| Q2 | Feasibility | MEDIUM | Proceed with extraction | None (low-risk) |
| Q3 | Scope | LOW | Single view only | Scope discipline |
| Q4 | Scope | LOW | Keybindings only | Scope discipline |

**Critical path:** Q1 must be decided before Gate 3 (affects file locations).  
**Others:** Can be formalized before Gate 3, but low impact on planning.

---

## Approval Checklist (Gate 2 Review)

- [ ] Q1 decision made and documented (Transform ops promotion)
- [ ] Q2 feasibility confirmed (extraction plan sound)
- [ ] Q3 scope confirmed (single view acceptable)
- [ ] Q4 UX scope confirmed (keybindings sufficient)
- [ ] All decisions recorded in appropriate architecture docs
- [ ] Gate 3 planning can proceed

---

**Document End**
