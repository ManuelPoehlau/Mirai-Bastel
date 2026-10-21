# WP-04 Core Reassessment — Executive Summary & Decision Record

**Document Type:** Decision Brief  
**For:** Approval to proceed with WP-04 implementation  
**Date:** 2026-09-01  
**Status:** Ready for approval (all analysis complete)

---

## The Question

**Should Core V1 remain frozen, or should we promote Rotate/Scale operations to Core for WP-04?**

Before implementation begins, we re-evaluated whether the Core freeze is still appropriate given WP-04 requirements.

---

## The Analysis

### Three Options Considered

| Option | Choice | Freeze Status |
|--------|--------|---------------|
| **A** | Promote Transform Ops to Core (no documentation) | Freeze violated (unclear precedent) |
| **B** | Keep Transform Ops external (in Production) | Freeze preserved (strictest interpretation) |
| **C** | Promote + document as Freeze-Rule precedent | **Freeze controlled + documented** ← RECOMMENDED |

### Key Findings

| Finding | Evidence |
|---------|----------|
| Core V1 is production-ready | 29/29 tests pass, 5 hardening phases complete |
| WP-04 can be implemented without Core changes | Move/Rotate/Scale all use existing APIs |
| Transform Ops are well-tested | 25+ unit tests from WP-03 validation |
| Promotion satisfies Freeze-Rule §7 | Concrete requirement, minimal, well-tested, isolated |
| Option C is technically optimal | Unified pattern (all transforms from Core), no duplication |
| Risk is low | No new Core APIs/data structures, proven pattern |

---

## Recommendation: OPTION C

### Decision

**Promote RotateOperation and ScaleOperation to `src/core/operations/transform.py`**

### Why

1. **Technically sound:** Uses only existing Operation contract + Mesh APIs (proven by MoveOperation)
2. **Freeze-compliant:** Satisfies CORE_V1_FREEZE.md §7 (concrete requirement, minimal, well-tested)
3. **Architecturally cleaner:** Move/Rotate/Scale follow identical pattern (all from Core)
4. **Long-term benefit:** Enables reuse in future WP (Deformation, Animation)
5. **Risk is low:** 260 lines, isolated, well-tested, no breaking changes

### What Changes

**At Gate 3 (new task 3.13):**
- Copy `experiments/.../transform.py` → `src/core/operations/transform.py`
- Update `src/core/__init__.py` to export RotateOperation, ScaleOperation
- Migrate tests from experiment to `src/tests/test_transform_operations.py`
- Document precedent in CORE_V1_FREEZE.md §7.1

**Total effort:** ~45 minutes (part of Gate 3 anyway)

**At Gate 4:**
- Extract RotateTool/ScaleTool from experiment (simpler: import from Core like MoveTool does)
- No code duplication, cleaner architecture

### Impact on WP-04 Timeline

- **No delay** (promotion happens during Gate 3, same timeline)
- **Cleaner architecture** (unified import pattern)
- **Better tests** (Core + Production tests cover same contract)

---

## The Precedent

**If approved, we establish:**

> "Pattern-filling operations (Operation subclasses using existing Operation contract) may be promoted to Core if well-tested, motivated by concrete requirement, and involve no new Core APIs."

This prevents future erosion of the freeze while enabling necessary, proven extensions.

---

## Explicit Out-of-Scope (Protected)

This does NOT open the door to:
- Topology mutations (already in Core, use MeshStateCommand)
- Architectural features (change-set, provenance, constraints)
- UI/Viewport/Renderer code
- Rigging, Morphing, Animation (future WP)

---

## Approval Checklist (Gate 2)

For approval to proceed with Option C:

- [ ] **Is Option C technically sound?** ✓ YES (uses proven pattern, no new APIs)
- [ ] **Is it Freeze-compliant?** ✓ YES (satisfies §7, with clear precedent)
- [ ] **Is it lower-risk than alternatives?** ✓ YES (unified pattern, no duplication)
- [ ] **Can we document the precedent clearly?** ✓ YES (§7.1 template provided)
- [ ] **Approved to proceed with Option C?** ☐ (awaiting decision)

---

## If Approved: Next Steps

1. **Communicate** this decision to team
2. **Proceed to Gate 3** with updated task plan (3.13 Transform Ops promotion)
3. **Update architecture docs** (CORE_V1_FREEZE.md §7.1, ROADMAP.md)
4. **Execute Gate 3** (includes promotion + tool extraction)
5. **Gate 4** proceeds normally (tools import from Core)

---

## If NOT Approved (Option B)

If Option B is preferred instead (keep external), then:

1. **Task 3.13 skipped** (no Core changes)
2. **Gate 4 modified:** Create `src/mirai/interaction/operations/` with local Rotate/Scale
3. **Gate 4 impact:** ~45 minutes extra (duplicate Operation classes)
4. **Test impact:** Tests scatter between Core + Production layers
5. **Future impact:** Transforms not reusable for future WP

---

## Supporting Documents

**For detailed analysis, see:**

1. **CORE_ARCHITECTURE_REASSESSMENT.md** (12 sections, comprehensive analysis)
   - Current Core API analysis
   - WP-04 requirements mapping
   - Detailed options comparison
   - Risk analysis
   - Long-term vision impact

2. **WP-04_IMPLEMENTATION_IMPACT_OPTION_C.md** (concrete implementation plan)
   - Gate-by-gate changes
   - Task-by-task breakdown
   - File-by-file checklist
   - Alternative (Option B) if needed

3. **Original Documents** (updated references)
   - WP-04_PRODUCTION_FOUNDATION_DISCOVERY_REPORT.md (search + replace "Q1")
   - WP-04_GATE_PLANNING.md (add task 3.13, update task 4.4)
   - WP-04_OPEN_QUESTIONS.md (Q1 is now answered)

---

## One-Paragraph Summary

The Core V1 freeze remains appropriate. WP-04 can be implemented without Core changes, but promoting Rotate/Scale operations to Core is justified under the established Freeze-Rule §7 (pattern-filling, concrete requirement, well-tested, minimal). Option C provides cleaner architecture (unified import pattern), no duplication, and low risk. This establishes a clear precedent for future controlled Core extensions while maintaining freeze discipline.

---

## Decision Record Template

**To be completed upon approval:**

```markdown
# DECISION: WP-04 Core Promotion — Transform Operations

**Decision Date:** [DATE]
**Decided By:** [NAME/ROLE]
**Option Chosen:** C (Promote + Document Precedent)

**Rationale:**
- Freeze-Rule §7 satisfied
- Technical soundness verified
- Risk assessed as low
- Architecture improved (no duplication, unified pattern)

**Implementation:**
- Gate 3 Task 3.13: Copy transform.py, migrate tests, update docs
- Gate 4: Extract tools with simplified imports from Core
- Effort: ~45 minutes (part of existing timeline)

**Documented In:**
- CORE_V1_FREEZE.md §7.1 (precedent)
- ROADMAP.md (WP-04 note)
- Commit message (Gate 3.13)

**Approval:**
- [ ] Architecture team: ___________
- [ ] Project lead: ___________
- [ ] QA/Testing: ___________
```

---

## Timeline Impact

| Phase | Original | With Option C | Impact |
|-------|----------|---------------|--------|
| Gate 2 (Analysis) | Complete | Complete | ✓ SAME |
| Gate 3 (Foundation) | 3–4 sessions | 3–4 sessions | ✓ SAME (3.13 added, duration same) |
| Gate 4 (Interaction) | 2 sessions | 2 sessions | ✓ SAME (simpler imports) |
| Total WP-04 | 13–15 sessions | 13–15 sessions | ✓ NO DELAY |

---

## Recommendation

**✓ APPROVE OPTION C**

Proceed with WP-04 implementation using Option C (Transform Ops promoted to Core with documented precedent).

This maximizes architecture quality, minimizes technical debt, and sets a clear pattern for future controlled Core extensions.

---

**Document End**

**Approval Signature Line**

```
Core Reassessment approved: ________________________  Date: __________

Proceed to Gate 3 with Option C: YES ☐  NO ☐  CLARIFICATIONS NEEDED ☐
```
