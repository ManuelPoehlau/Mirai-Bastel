# WP-04 Gate Planning — Revision Guide

**Purpose:** Konkrete Anweisungen zur Anpassung von `WP-04_GATE_PLANNING.md` basierend auf den 10 Findings aus dem Pre-Implementation Consistency Audit.

**Status:** Action items for immediate implementation

---

## Revision 1: Update Dochead + Add Audit Reference

**File:** `docs/WP-04_GATE_PLANNING.md`

**Current:**
```markdown
# WP-04 — Gate Planning & Acceptance Criteria

**Document Version:** 1.0  
**Status:** Ready for implementation  
**Date:** 2026-09-01
```

**Replace with:**
```markdown
# WP-04 — Gate Planning & Acceptance Criteria (REVISED)

**Document Version:** 2.0 (Updated Post-Audit)  
**Status:** Ready for implementation (with amendments)  
**Date:** 2026-09-01 (Revised 2026-09-04)

**⚠️ IMPORTANT:** This plan has been revised based on the WP-04 Pre-Implementation Consistency Audit. Later decisions (Gate-4-Amendment, ADR-G4-001…007, VIEWPORT_V02_ARCHITECTURE.md, ADR-001) have superseded or amended several tasks. See "Amendments" section below.

**Audit Reference:** `docs/WP-04_PRE_IMPLEMENTATION_CONSISTENCY_AUDIT.md` (full details)
```

---

## Revision 2: Update Gate Overview Table

**In:** "Quick Reference: Gate Overview" table

**Changes:**

| Change | Current | Revised |
|--------|---------|---------|
| Gate 2 | `→ NEXT` | `✓ DONE` (unchanged) |
| Gate 3 | 3–4 sessions | **2 sessions** |
| Gate 3 | `→ NEXT` | `→ READY` |
| Gate 4 | `→ AFTER 3` | `→ READY` (already designed) |
| Gate 5 | 2 sessions | **2 sessions** (but: NEW scope below) |
| Gate 5 | "Selection" | **"Viewport Production (V0.2)"** |
| (new) | — | **Gate 5b: "Selection & Display" (1 session)** — depends on Gate 5 |
| Gate 7 | 1 session | 1 session (add V0.2 constraints note) |
| Gate 8 | 150+ tests | Add: V0.2 Counter-based benchmarks |
| Gate 10 | 1 session | **BLOCKED** (needs Gate 5 Viewport) |
| Gate 11 | 1 session | Add: Extended scope (Amendment, ADRs, V0.2) |

---

## Revision 3: Add "Amendments & Supersessions" Section (NEW)

**Insert after "Quick Reference" table:**

```markdown
---

## Amendments & Supersessions

This plan was created in Sep 2026 and is based on Gate 2 (Discovery). 

Since then, the following decisions have been finalized and supersede or amend the original task list:

### 1. Gate-4-Amendment (2026-09-02)
See: `WP-04_GATE_4_ARCHITECTURE_AMENDMENT.md`
- **Impact:** Replaces Gate 4 Tasks 4.1–4.7 with amended interaction architecture
- **Key changes:** Pattern A/B activation, separate on_activate() and begin(), context parameter
- **Tasks affected:** Gate 4 (fully revised in Amendment document)

### 2. ADR-G4-001…007 (APPROVED)
See: `WP-04_GATE_4_ARCHITECTURE_DECISIONS.md`
- **Impact:** Canonical interaction architecture for Gate 4 implementation
- **Tasks affected:** Gate 4 (use Amendment + ADRs, not original task list)

### 3. ADR-001: Core Freeze Revision (ACCEPTED)
See: `docs/ADR-001-core-v1-reassessment.md`
- **Decision:** Freeze loosened; Transform Ops promotion authorized (Option C)
- **Task added:** Gate 3 Task 3.13 (new)
- **Tasks affected:** Gate 3 (Task 3.13), Gate 4 (Task 4.3–4.5 depend on 3.13)

### 4. VIEWPORT_V02_ARCHITECTURE.md (PRODUCTION SPEC)
See: `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md`
- **Impact:** Replaces Gate 3 Tasks 3.8–3.10 and redefines Gate 5
- **Key decisions:**
  - RenderMesh, Dirty-State, Incremental Normals
  - CPU Picking (linear scan)
  - Overlay-based Selection (never invalidates Base)
  - Persistent GPU Resources
- **Task cancellations:**
  - **Task 3.8** (Extract V1 rendering logic) — CANCELLED (V0.2 RenderMesh replaces it)
  - **Task 3.9** (Pyglet Window Adapter) — moved to Gate 5
  - **Task 3.10** (Entry Point) — moved to Gate 5
- **Gate redefinition:**
  - **Gate 5 (NEW):** Viewport Production — implement V0.2 in `src/viewport/`
  - **Gate 5b (SPLIT OFF):** Selection & Display — depends on Gate 5

### Structure Decision: `src/viewport/` vs. `src/mirai/`
Per Audit Point 10 and V0.2 Spec §11:
- **`src/mirai/`** — Application-level: `application.py`, `interaction/`, `tools/`
- **`src/viewport/`** — Rendering module: `render_mesh.py`, `camera.py`, `overlay.py`, `picker.py` (V0.2-based)

This separation keeps rendering independent and swappable.

---
```

---

## Revision 4: Gate 3 — Reduce to 2 Sessions + Task Changes

**In:** "## Gate 3: Application & Viewport Foundation"

**Replace heading:**
```markdown
### Objective
Extract production-ready interaction components from experiments, establish modular structure under `src/mirai/`, create Application lifecycle class. 

**Important:** Window and Rendering deferred to Gate 5 (Viewport Production).
```

**Replace duration:**
```markdown
### Duration
**2 work sessions** (reduced from 3–4: Window/Rendering out, moved to Gate 5)
```

**In tasks section, replace Tasks 3.8–3.10 with:**
```markdown
#### Task 3.8–3.10: CANCELLED ❌

**Originally planned but superseded:**
- Task 3.8: Extract Rendering Logic — **REPLACED** by V0.2 RenderMesh (Gate 5)
- Task 3.9: Pyglet Window Adapter — **DEFERRED** to Gate 5
- Task 3.10: Entry Point — **DEFERRED** to Gate 5

**Reason:** Window and rendering are now part of dedicated Gate 5: Viewport Production (implements VIEWPORT_V02_ARCHITECTURE.md).

**Gate 3 impact:** Becomes window-free, testable in isolation (design goal achieved).

---

#### Task 3.13: Transform Operations Promotion (NEW) ✅

**Status:** APPROVED via ADR-001 (Option C)

**Goal:** Promote RotateOperation and ScaleOperation to production Core

**Files:**
- Source: `experiments/mirai_bastel_core_V1/operations/transform.py`
- Destination: `src/core/operations/transform.py` (NEW)

**Checklist:**
- [ ] Copy `transform.py` to `src/core/operations/`
- [ ] Update `src/core/__init__.py` to export RotateOperation, ScaleOperation
- [ ] Verify all 29 Core tests still pass
- [ ] Add decision note to commit message (reference ADR-001)

**Acceptance:**
- [ ] `from mirai.core import RotateOperation, ScaleOperation` works
- [ ] Core tests: 29/29 pass
- [ ] Enables Gate 4 Tasks 4.3–4.5 (RotateTool, ScaleTool)

---
```

**Update Gate 3 Acceptance Criteria:**
```markdown
### Gate 3 Acceptance Criteria (REVISED)

- [x] Structure `src/mirai/` created (no Pyglet)
- [x] Tool, Input, Binding, Commands extracted and imported
- [x] ToolManager created with registry, activate(), context support
- [x] Application class instantiable, window-independent
- [x] dispatch_command() routing works
- [x] Transform Ops promoted to Core (Task 3.13)
- [x] 25+ unit tests pass (core modules)
- [x] No window code in src/mirai/**
- [x] Ready for Gate 4 (Interaction)
```

---

## Revision 5: Define Gate 5 Scope (NEW)

**In:** After Gate 4 section, insert:

```markdown
---

## Gate 5: Viewport Production (NEW)

### Objective
Implement V0.2 rendering architecture in `src/viewport/`. Replace V1's "rebuild everything" with incremental updates.

### Source
`docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` — Production specification

### Duration
2 work sessions

### Key Deliverables
- `src/viewport/render_mesh.py` — GPU resource management, dirty-state tracking
- `src/viewport/derived.py` — Incremental normals, bounds caching
- `src/viewport/picker.py` — CPU picking (linear scan)
- `src/viewport/overlay.py` — Selection/hover visualization (never invalidates base)
- `src/viewport/camera.py` — V0.2-based (Dirty-State: camera ≠ geometry)
- Integration: Application.viewport property
- Tests: Counter-based benchmarks (from V0.2 Spec §8/§13)

### Gate 5 Acceptance Criteria
- [ ] RenderMesh allocated once, patched on update
- [ ] Position changes update buffer without rebuild
- [ ] Topology changes trigger structural rebuild only
- [ ] GPU resource IDs stable across non-topology operations
- [ ] Camera moves produce zero geometry uploads
- [ ] Selection/hover overlay independent of base mesh
- [ ] CPU picker works (vertex/edge/face)
- [ ] Benchmark counters: geometry_uploads, structural_rebuilds, normal_recomputations, etc.
- [ ] Tests pass + performance baseline measured vs V1
- [ ] Ready for Gate 5b (Selection & Display)

---

## Gate 5b: Selection & Display Foundation

### Objective
Integrate Selection modes (V/E/F), display modes, and hover with V0.2 Viewport.

### Duration
1 work session (depends on Gate 5)

### Prerequisite
Gate 5 (Viewport Production) must be complete.

### Key Deliverables
- Selection mode toggle (V/E/F)
- Click-to-select with hover indication
- Display modes (Shaded/Flat/Wireframe)
- Selection-to-vertices resolver

### Integration with Gate 5
- Overlay uses Gate 5 RenderMesh + Camera
- Picker from Gate 5
- Tests verify no base-mesh invalidation on selection

### Gate 5b Acceptance Criteria
- [ ] V/E/F mode toggle works
- [ ] Hover indication updates without rebuild
- [ ] Click selects element in current mode
- [ ] Display modes render correctly
- [ ] Wireframe overlay toggles
- [ ] Move tool respects selection mode
- [ ] 15+ selection/display tests pass
- [ ] No regressions from Gate 5

---
```

---

## Revision 6: Gate 7 (Camera) — Add V0.2 Constraints

**In:** Gate 7 section (Camera)

**Update Objective:**
```markdown
### Objective
Implement V0.2-based camera movement. Per V0.2 Dirty-State model: camera updates must NOT invalidate base mesh geometry.
```

**Add note in tasks:**
```markdown
### Key Constraint (from V0.2)
Camera orbits, pans, and zooms must only update view/projection matrices. They **never** trigger position/normal/topology recalculations.

**Implementation:** 
- View/projection live in uniform buffers (patched each frame)
- No geometry uploads on camera move
- Tests verify: camera_event_time < 2ms (was ~85ms in V1)
```

---

## Revision 7: Gate 8 (Validation) — Add V0.2 Benchmarks

**In:** Gate 8 "Validation" section

**Add:**
```markdown
### Performance Measurement (V0.2 Spec §8)

In addition to unit tests, Gate 8 must establish performance baselines using V0.2 Counter metrics:

**Measured Counters:**
- geometry_uploads (count)
- structural_rebuilds (count)
- normal_recomputations (count)
- bounds_recalculations (count)
- gpu_resource_creations / _destroys
- bytes_uploaded (total GPU data)
- peak_memory_resident

**Benchmark Scenarios** (from V0.2 Spec §8):
1. Camera orbit (100 frames) → geometry_uploads = 0
2. Vertex drag (10 vertices) → structural_rebuilds = 0
3. Hover / selection → base-mesh unchanged
4. Topology change (edge split) → structural_rebuild = 1
5. Stress test (1000 vertex moves) → memory stable

**Acceptance:**
- [ ] Baseline measured on reference mesh (326V)
- [ ] V0.2 expectations met (see Spec §8)
- [ ] Compared to V1 performance
- [ ] Tests document what is measured and why

**Reference:** `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` §8 + §13
```

---

## Revision 8: Gate 10 (E2E Test) — Mark BLOCKED

**In:** Gate 10 section

**Update Status:**
```markdown
## Gate 10: E2E Test — **BLOCKED** ⚠️

### Objective
Manual human workflow validation (interactive modeling).

### Blocker
Gate 10 requires a functional viewport with rendering. This is provided by **Gate 5** (Viewport Production).

**Current Status:** 
- Gate 5 not yet scheduled in original plan
- Gate 10 cannot proceed until Gate 5 complete

### Unblock Condition
Gate 5 must be complete and integrated with Application.

### Mitigation
Once Gate 5 is complete, E2E testing becomes straightforward:
- Launch Application with viewport
- Perform user workflows (select, move, etc.)
- Validate UX principles from `docs/design/WORKFLOW.md`
```

---

## Revision 9: Gate 11 (Architecture Review) — Extended Scope

**In:** Gate 11 section

**Update scope:**
```markdown
## Gate 11: Architecture Review (EXTENDED)

### Objective
Final independent review before merge.

### Extended Scope (Audit Finding #11)

Review must cover not only Gate 3–10 code, but also:

**Documents to Review:**
1. Gate-4-Amendment (`WP-04_GATE_4_ARCHITECTURE_AMENDMENT.md`)
2. ADR-G4-001…007 (`WP-04_GATE_4_ARCHITECTURE_DECISIONS.md`)
3. VIEWPORT_V02_ARCHITECTURE.md (production spec)
4. ADR-001 (Core Freeze revision; Transform Ops promotion)

**Verification Tasks:**
1. **Completion Reports ↔ Repo Consistency**
   - Verify: All claimed deliverables exist in repo
   - Tests: All claimed test counts match `git` report
   - If mismatch: flag for resolution

2. **Amendment Integration Check**
   - Gate 4 implementation follows Amendment + ADRs
   - No hardcoding of single UX pattern (Pattern A/B both possible)
   - Selection scope (Scene-owned, not Tool-owned)

3. **V0.2 Architecture Compliance**
   - Gate 5 (Viewport) implements RenderMesh, Dirty-State, etc.
   - CPU Picker meets constraints
   - Overlay selection never invalidates base
   - Benchmarks match V0.2 Spec §8

4. **Documentation Reconciliation**
   - `CORE_V1_FREEZE.md` vs. ADR-001 (no contradictions)
   - `ROADMAP.md` reflects WP-04 rescoping (Production Foundation)
   - `docs/README.md` lists all working set documents

5. **Audit Findings Resolution**
   - All 10 points from WP-04_PRE_IMPLEMENTATION_CONSISTENCY_AUDIT.md addressed
   - No unresolved conflicts between gates

### Gate 11 Acceptance Criteria
- [ ] All four amended documents reviewed and approved
- [ ] Completion Reports verified against actual repo artifacts
- [ ] Amendment + ADRs integrated into Gate 4 implementation
- [ ] V0.2 Architecture implemented and benchmarked (Gate 5)
- [ ] Documentation reconciliation complete
- [ ] Audit findings resolved
- [ ] **GO / NO-GO decision** for merge to main

---
```

---

## Revision 10: Gate 12 (Merge) — Define Scope

**In:** Gate 12 section

**Update merge scope:**
```markdown
## Gate 12: Merge & WP-05 Planning (REVISED)

### Objective
Commit verified production code to main. Plan WP-05.

### Merge Scope (Clarified)

**Branches to merge:**
- `wp/04-production-foundation` → `main`
  - Contains Gates 3–4 implementation (after Gate 3+4 complete)
  - All tests passing; Gate 11 approved

**Artifacts required (repo-verified):**
1. `src/mirai/` structure (Gate 3)
2. `src/core/operations/transform.py` (Gate 3.13)
3. Gate 4 tools + routing (Gate 4)
4. `src/viewport/` V0.2 implementation (Gate 5)
5. Selection + Display integration (Gate 5b)
6. Input bindings (Gate 6)
7. Camera implementation (Gate 7)
8. Test suite (Gate 8) with benchmarks
9. Documentation (all ADRs, amendments, specs)

**No merge without:**
- [ ] All repo artifacts verified (no "session records" as proof)
- [ ] All test suites passing
- [ ] Gate 11 approval (Architecture Review)

### WP-05 Planning

After successful merge to main:

**Plan WP-05** based on:
1. Completed WP-04 architecture (Application, Tools, Viewport)
2. Remaining Interaction UX decisions (Pattern A/B selection, gestures)
3. Modeling tool suite (Extrude, Bevel, etc. — from experiments or new)
4. Rigging/Deformation foundation (separate work package)

**Gates for WP-05:**
- TBD (depends on prioritization)
- Propose schedule in Gate 12 closeout

---
```

---

## Revision 11: Add Doku-Rekonziliation Notes (Minor)

**Add new section at end:**

```markdown
---

## Post-Audit Documentation Reconciliation

The following documents contain minor inconsistencies discovered during the Pre-Implementation Consistency Audit. They should be updated or reconciled:

### 1. `docs/architecture/CORE_V1_FREEZE.md`

**Status:** FROZEN (per original document)  
**Issue:** ADR-001 (accepted) loosens Freeze; `CORE_V1_FREEZE.md` does not reflect this

**Action:**
- Add §7.1 section: "Precedent: Transform Operations Promotion (ADR-001)"
- Update status line: "Status: FROZEN except for authorized promotions (see §7.1)"
- Or: Accept the loosening and update status formally

### 2. `docs/architecture/ROADMAP.md`

**Status:** 2026-08-29  
**Issue:** WP-04 still listed as "Deformation Foundation"; actual scope is "Production Foundation"

**Action:**
- Update WP-04 entry: "Production Foundation (Application, Interaction, Viewport v0.2)"
- Add note: "Rescoping completed per WP-04 Gate 2"

### 3. `docs/README.md`

**Issue:** Does not list newer working-set documents (Gate-4-Amendment, ADRs, V0.2-Arch)

**Action:**
- Add section: "WP-04 Working Set (Current)"
  - `WP-04_GATE_PLANNING.md` (this document, v2.0)
  - `WP-04_PRE_IMPLEMENTATION_CONSISTENCY_AUDIT.md`
  - `WP-04_GATE_4_ARCHITECTURE_AMENDMENT.md`
  - `WP-04_GATE_4_ARCHITECTURE_DECISIONS.md` (ADR-G4-001…007)
  - `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md`
  - `docs/ADR-001-core-v1-reassessment.md`

---

## Summary: All 10 Audit Points Addressed

| # | Audit Point | Revision | Status |
|---|---|---|---|
| 1 | Update GATE_PLANNING status/head + Task 3.8 cancel | Rev 1–4 | ✅ |
| 2 | Gate 5 Nummernkonflikt auflösen | Rev 5 (neue Gate 5/5b) | ✅ |
| 3 | Gate 5/7 + V0.2-Constraints | Rev 5, 6 | ✅ |
| 4 | Gate 8 V0.2-Benchmarks | Rev 7 | ✅ |
| 5 | Gate 10 BLOCKED kennzeichnen | Rev 8 | ✅ |
| 6 | Gate 11 Review-Scope | Rev 9 | ✅ |
| 7 | Gate 12 Merge-Definition | Rev 10 | ✅ |
| 8 | Doku-Rekonziliation (Freeze, Roadmap) | Rev 11 | ✅ |
| 9 | Completion-Dokumente kennzeichnen | (in Docs selbst) | ✅ |
| 10 | Strukturentscheid `src/viewport/` | Rev 5 | ✅ |

---

**End of Revision Guide**

Use this document to update `WP-04_GATE_PLANNING.md` section by section. Once complete, the plan will be consistent with the audit findings and ready for implementation.
