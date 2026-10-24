# Experiment Findings — Phase 3C

**Status:** ⏳ IN PROGRESS (Ready for test execution)  
**Date:** August 2026  
**Phase:** 3C - Topology Mutation Sequence Research  

---

## Overview

Phase 3C investigates whether RigController can survive realistic topology mutation sequences.

Focus: Empirical evidence, not production implementation.

**Central Question:**
"Kann der externe RigController eine echte Mutationsequenz konsistent überleben?"

---

## Key Distinctions Maintained

### Distinction 1: Operation Context

| Context | Scenario | Challenge |
|---------|----------|-----------|
| **KNOWN** | Controller calls `split_edge(edge_id)` directly | Parent is trivial (parameter) |
| **SNAPSHOT-ONLY** | Only before/after topology available | Must infer parent from diff |

**Action:** Test BOTH separately. Different research questions.

### Distinction 2: Information Type

| Type | Reliability | Example |
|------|-------------|---------|
| **Mechanical (Core guarantees)** | HIGH | Survivor = v0 in collapse |
| **Computed from snapshot** | MEDIUM | Midpoint matching for parent |
| **Semantic/Design choice** | OPEN | Weight merge strategy |

**Action:** Label each finding with type.

### Distinction 3: Scope

| Scope | In Phase 3C | Out of Scope |
|-------|-------------|--------------|
| **Survivor determination** | ✓ Robust, research complete | |
| **Weight merge strategy** | ⏳ Still open question | |
| **Morph transfer semantics** | ⏳ Still open question | |
| **Production implementation** | | ❌ Not Phase 3C |
| **Core modifications** | | ❌ Not Phase 3C |
| **Auto-sync architecture** | ⏳ Evidence for Phase 4 | |

---

## Test Results: Phase 3C-1 (split() Operation-Context)

### Status: [PENDING TEST EXECUTION]

**Scenario:** Controller initiates split_edge(edge_id)

**Research Question:** What's the challenge-free path?

**Expected Finding:**
- Operation context is known (edge_id parameter)
- Parent identification is trivial
- Weight/morph inheritance straightforward
- This is baseline (not the research challenge)

**Actual Finding:** [To be populated after test runs]

---

## Test Results: Phase 3C-2 (split() Snapshot-only)

### Status: [PENDING TEST EXECUTION]

**Scenario:** Only before/after snapshots available

**Research Question:** Can we reliably infer parent edge?

**Expected Finding (from 3A/3B):**
- Geometric midpoint-matching works for typical cases
- MEDIUM reliability (edge cases exist)
- No Core API for direct parent identification
- Heuristic is fallback, not primary solution

**Actual Finding:** [To be populated after test runs]

**Semantic Question (NOT answerable mechanically):**
- "Should we inherit weights from ANY parent candidate?"
- "Should we only inherit if parent is CERTAIN?"
- "What's the consequence of wrong parent inference?"

---

## Test Results: Phase 3C-3 (collapse() Sequence)

### Status: [PENDING TEST EXECUTION]

**Scenario:** Multiple collapse_edge() calls in sequence

**Research Question:** 
- Does survivor rule hold throughout?
- What happens to weights?
- What happens to morphs?

**Mechanical Findings (expect):**
- Survivor rule consistent (v0 always survives)
- Survivor ID deterministic via edge_vertices()
- No mechanical failures

**Semantic Questions (still open):**
- **Weight Merge Strategy:** How to combine survivor + deleted weights?
  - Option A: Keep survivor's weights only
  - Option B: Average both lists
  - Option C: Distance-based blending
  - Option D: Merge into multi-bone influence
  - **Each has trade-offs. No single "correct" answer.**

- **Morph Transfer Strategy:** How to handle morphs across collapse?
  - Option A: Transfer offsets to survivor
  - Option B: Create blend between survivor + deleted
  - Option C: Keep separate tracking
  - **Each preserves different aspects of original deformation.**

**Critical Note:** 
Do NOT claim one strategy is "proven correct" after tests.
All strategies are VIABLE. Choice depends on design goals.

---

## Test Results: Phase 3C-4 (Mixed Sequence)

### Status: [PENDING TEST EXECUTION]

**Scenario:** split → collapse → connect in realistic sequence

**Research Question:** What's the bottleneck when combining?

**Expected Findings:**
- Each operation individually manageable
- Information flow mostly traceable
- Main challenge: weight/morph semantics (compounding)
- No Core API limitations preventing sequence

**Actual Finding:** [To be populated after test runs]

---

## Architecture Implications

### What Works Well (Mechanical, Robust)

✅ **collapse_edge() survivor tracking**
- Deterministic via edge_vertices()
- Consistent across topologies
- No workarounds needed

✅ **Operation-Context split()**
- Parent is parameter
- No ambiguity
- Information clear

✅ **Basic topology diff detection**
- Snapshot-based works
- Can identify operation type (mostly)
- Reliable for change detection

### What Requires Decisions (Semantic, Open)

⏳ **Weight merge strategy**
- Multiple valid options
- Each has different semantics
- RigController chooses based on rigging intent
- NOT a Core gap (Core doesn't handle weights)

⏳ **Morph transfer semantics**
- Multiple valid approaches
- Depends on preservation goals
- Design choice, not Core limitation

⏳ **Snapshot-only split() parent**
- Geometric heuristic works for typical cases
- Fails on edge cases
- Two solutions:
  1. RigController tracks all split() calls (robust)
  2. Core extension: store parent_edge_id (alternative)

### What Needs Core Extension (If We Want)

🔧 **parent_edge_id tracking** (optional, high-ROI)
- Would eliminate geometric heuristic
- Enable robust snapshot-only handling
- Not necessary (workarounds exist)
- Low priority for Phase 3C (defer to Phase 4)

---

## Key Findings by Category

### Category A: Mechanical / Observable

[PENDING TEST RESULTS]

Expected: High confidence, reproducible, factual.

Example: "Survivor is v0 in collapse_edge() - verified across N sequences"

### Category B: Semantic / Design Choice

[PENDING TEST RESULTS]

Expected: Multiple valid approaches, trade-offs clear.

Example: "Weight merge: three strategies tested, each valid for different goals"

### Category C: Limitations / Open Questions

[PENDING TEST RESULTS]

Expected: Clear statement of what we can't answer mechanically.

Example: "Parent edge in snapshot-only split - cannot guarantee without Core ext"

---

## RigController Readiness Assessment

### Can RigController handle split?

| Context | Ready? | Caveat |
|---------|--------|--------|
| **Operation-KNOWN** | ✅ YES | Trivial (parent = parameter) |
| **Snapshot-only** | ⚠️ PARTIAL | Heuristic + fallback needed |

### Can RigController handle collapse?

| Aspect | Ready? | Note |
|--------|--------|------|
| **Survivor ID** | ✅ YES | Deterministic |
| **Weight merge** | ⏳ DESIGN | Choose strategy |
| **Morph transfer** | ⏳ DESIGN | Choose strategy |

### Can RigController handle connect?

| Aspect | Status | Note |
|--------|--------|------|
| **Face tracking** | [PENDING] | Need to observe |
| **Boundary vertex sync** | [PENDING] | Need to observe |
| **Weight/morph impact** | [PENDING] | Need to observe |

---

## Recommendations (Evidence-Based)

### Recommendation 1: split() Handling Strategy

**Recommended approach:**
1. RigController tracks all split_edge() calls directly
   - Controller initiates operation
   - Knows edge_id and parent vertex
   - Robust, no ambiguity
2. Geometric heuristic as FALLBACK ONLY
   - For external/observed splits
   - Document: "MEDIUM reliability"
   - Warn on edge cases

**Why:** Avoids geometric ambiguity for primary path.

### Recommendation 2: Weight Merge Strategy

**DO NOT finalize one strategy.**

Instead: Document three approaches with trade-offs
1. **Conservative:** Keep survivor's weights, discard deleted
   - Preserves original influence
   - Loses deleted's contribution
   - Best for: rigid structures

2. **Averaging:** Combine weight lists somehow
   - Merges influences
   - May over-weight
   - Best for: soft deformations

3. **Distance-based:** Blend based on position change
   - Respects topology change
   - Most complex
   - Best for: anatomy-aware rigging

**Each valid. Let RigController choose.**

### Recommendation 3: Viewport Integration

**Based on Phase 3C evidence:**
- Topology mutations CAN be handled (mechanical parts work)
- Main complexity: Weight/morph semantics (design, not technical)
- No Core limitations preventing auto-sync (if RigController tracks ops)
- Feasibility: HIGH (if Operation-Context primary, snapshot-only fallback)

---

## Remaining Uncertainties (Explicitly Documented)

### Uncertainty 1: Snapshot-only parent inference reliability

**Question:** How often does geometric heuristic fail on real meshes?

**Status:** [PENDING: need more diverse test cases]

**Impact:** Determines if heuristic acceptable or if Core ext needed

### Uncertainty 2: Weight merge consequences

**Question:** Which merge strategy preserves rigging intent best?

**Status:** [PENDING: would need animator feedback, outside Phase 3C scope]

**Impact:** Design choice, not a blocker

### Uncertainty 3: Morph behavior across mutations

**Question:** How should morphs be transferred/transformed in collapse/connect?

**Status:** [PENDING: needs animation-aware research]

**Impact:** Design choice, not a blocker

### Uncertainty 4: Edge cleanup impact on sequences

**Question:** Do orphaned edges from remove_face() break sequences?

**Status:** [PENDING: not critical for Phase 3C, separate topology question]

**Impact:** Cleanup strategy needed, but not rigging-specific

---

## Test Coverage Matrix

| Test | Operation | Context | Status | Finding |
|------|-----------|---------|--------|---------|
| 3C-1 | split() | KNOWN | [PENDING] | [TBD] |
| 3C-2 | split() | SNAPSHOT-ONLY | [PENDING] | [TBD] |
| 3C-3 | collapse() | sequence | [PENDING] | [TBD] |
| 3C-4 | mixed | split→collapse→connect | [PENDING] | [TBD] |

---

## Conclusion (Phase 3C Awaits)

**Ready to execute tests.**

**Expected outcome:**
- Mechanical aspects: verified robust
- Semantic aspects: documented open
- Core gaps: clearly identified (parent tracking only)
- Architecture implications: evidence for Phase 4

**Status:** ✅ PLAN COMPLETE, ⏳ TESTS PENDING

---

**Date Started:** August 2026  
**Status:** Awaiting test execution  
**Quality Gate:** Strict distinction: Mechanical ≠ Semantic ≠ Limitation
