# Phase 3C: Execution Guide & Status

**Status:** ✅ PLAN COMPLETE, ⏳ READY FOR EXECUTION  
**Date:** August 2026  
**Owner:** Manu  

---

## What Phase 3C Delivers

### Primary Goal
Investigate: "Kann der externe RigController eine echte Mutationsequenz konsistent überleben?"

### Deliverables

1. **test_mutation_sequences.py** (500+ lines)
   - 4 focused research tests
   - Operation-Context vs. Snapshot-only distinction
   - Detailed observations (print-based)
   - Clear conclusions per test

2. **FINDINGS-3C.md** (populated after tests)
   - Test results for each case
   - Mechanical findings (robust)
   - Semantic questions (open)
   - Architecture implications
   - Explicit uncertainties

3. **Architecture Evidence**
   - What RigController CAN do robustly
   - What requires design choices
   - What might need Core support
   - Feasibility for Phase 4

---

## Test Execution Instructions

### Prerequisites

```bash
# Verify Core.Mesh is available
cd /path/to/Mirai-Bastel
python -c "from src.core.mesh import Mesh; print('✓ Core available')"
```

### Run Phase 3C Tests

```bash
# Execute all tests (prints detailed output)
python test_mutation_sequences.py

# Capture output to file
python test_mutation_sequences.py > findings_3c_raw.txt

# For pytest integration (if available)
pytest test_mutation_sequences.py -v -s
```

### What to Look For

Tests output detailed observations in this pattern:

```
=== Test Name ===

--- BASELINE ---
[Setup description]

--- OPERATION ---
[What happens]

--- OBSERVATION ---
✓ Fact 1
✓ Fact 2
? Uncertainty 1

--- CONCLUSION ---
[Summary]
[FINDING]
[IMPLICATION]
```

---

## Populating FINDINGS-3C.md

After running tests:

1. **Capture test output**
   ```bash
   python test_mutation_sequences.py > test_output.txt
   ```

2. **Extract findings per test**
   - Copy test output for each 3C-1, 3C-2, 3C-3, 3C-4
   - Paste into FINDINGS-3C.md under corresponding test section
   - Mark [PENDING] → [COMPLETE]

3. **Categorize findings**
   - Mechanical (facts) → Category A
   - Semantic (design) → Category B
   - Limitations (unknowns) → Category C

4. **Add recommendations**
   - Based on observed evidence
   - Don't overstate (distinguish robust vs. open)
   - Document trade-offs

---

## Expected Outcomes (Evidence-Based Predictions)

### Test 3C-1: split() Operation-Context

**Expected:** Straightforward, no research problem

**Actual Evidence:** [PENDING]

**Implication:** Operation-Context is PRIMARY path (baseline)

---

### Test 3C-2: split() Snapshot-only

**Expected:** Geometric heuristic works, with caveats

**Predicted Finding:**
- Midpoint matching successful for test case
- Distance tolerance met (< 1e-6)
- Works but MEDIUM reliability
- Edge cases exist (non-unique midpoints)

**Actual Evidence:** [PENDING]

**Implication:** Heuristic is FALLBACK, not primary

---

### Test 3C-3: collapse() Sequence

**Expected:** Survivor rule holds, semantics open

**Predicted Finding:**
- Survivor deterministic in sequence
- Both collapses succeed
- No mechanical failures
- Weight/morph merge STILL OPEN (design choice)

**Actual Evidence:** [PENDING]

**Implication:** Collapse MECHANICAL is robust, SEMANTIC is design

---

### Test 3C-4: Mixed Sequence

**Expected:** Feasible but complex

**Predicted Finding:**
- Sequence executes without Core errors
- Information is traceable
- Bottleneck: merge strategy (not mechanical)
- Multiple valid approaches

**Actual Evidence:** [PENDING]

**Implication:** Sequence handling is FEASIBLE, design choices matter

---

## Quality Gates (Adherence Check)

### Gate 1: Distinction Maintenance

✅ **Separating Operation-Context from Snapshot-only**
- Test 3C-1 treats KNOWN context
- Test 3C-2 treats SNAPSHOT-only
- Results analyzed separately
- Implications derived differently

✅ **Separating Mechanical from Semantic**
- Survivor = mechanical (Core guarantees)
- Weight merge = semantic (design choice)
- Explicitly labeled in findings
- No confusion

✅ **Separating Observation from Interpretation**
- Facts clearly marked (observations)
- Inferences clearly marked (interpretation)
- Uncertainties explicitly stated

### Gate 2: No Core Modifications

✅ **All tests use ONLY public Core APIs**
- No changes to src/core/
- No new fields added
- parent_edge_id remains optional (Phase 4 decision)
- Proof: review test code for Core usage

### Gate 3: No Premature Claims

✅ **Not claiming production-ready**
- Each finding scoped to Phase 3C
- Limitations documented
- Open questions remain open

✅ **Not finalizing weight/morph strategies**
- Multiple approaches documented
- Trade-offs clear
- No single "correct" answer stated

✅ **Not claiming automatic edge cleanup is solved**
- Separate concern
- Not blocking rigging
- Noted for future

---

## Deliverables Checklist

Before Phase 3C is COMPLETE:

- [ ] test_mutation_sequences.py created ✅
- [ ] All 4 tests runnable (3C-1, 3C-2, 3C-3, 3C-4)
- [ ] FINDINGS-3C.md template created ✅
- [ ] Tests executed successfully
- [ ] Test output captured
- [ ] Findings populated in FINDINGS-3C.md
- [ ] Architecture recommendations documented
- [ ] Uncertainties explicitly listed
- [ ] Quality gates verified
- [ ] Ready for Phase 4 planning

---

## Transition to Phase 4

After Phase 3C complete:

### Phase 4 Decisions (Not Phase 3C)

❌ **NOT deciding in Phase 3C:**
- "Should we add parent_edge_id to Core?" (decide in Phase 4)
- "Which weight merge strategy is correct?" (design choice for later)
- "How to handle morph mutations?" (animation research)
- "Automatic sync architecture?" (Phase 4 architecture)

✅ **Phase 3C provides evidence for Phase 4 to decide:**
- "Geometric heuristic works but has limitations"
- "RigController CAN track mutations if given context"
- "Weight/morph semantics need specification"
- "Sequence handling is feasible"

### Phase 4 Entry Criteria

Phase 4 can start when Phase 3C provides:

1. ✅ Evidence on mutation sequence feasibility
2. ✅ Clear identification of semantic questions
3. ✅ Architectural bottlenecks identified
4. ✅ Core gap analysis (if any)
5. ✅ Trade-offs documented (not hidden)

---

## Timeline

**Phase 3C Execution:**
- Week 1: Test execution + troubleshooting (if needed)
- Week 2: Findings documentation + analysis
- Week 3: Architecture recommendation + Phase 4 prep

**Total:** 2-3 weeks

---

## Documentation Standards for Phase 3C

### For Each Test Finding

Must include:

1. **Observation** (what we saw)
   ```
   ✓ Geometric midpoint match: distance = 1.2e-7
   ✓ Survivor rule holds: v0 survived as predicted
   ? Morph behavior: undefined by Core
   ```

2. **Interpretation** (what we infer)
   ```
   This suggests parent edge was the split source
   BUT: Only valid if no two edges share same midpoint
   ```

3. **Limitation** (what we can't guarantee)
   ```
   Cannot guarantee parent with snapshot-only obs
   Geometric heuristic fails if vertices align
   ```

4. **Implication** (consequence for RigController)
   ```
   Must track split() calls OR accept MEDIUM reliability
   OR require Core extension for robust solution
   ```

---

## Success Criteria for Phase 3C

✅ **Empirical Quality**
- Tests produce clear observations
- No assumptions pre-filled
- Results documented (no [PENDING])
- Uncertainties explicit

✅ **Architectural Value**
- Evidence for next phase decisions
- Trade-offs clear
- Bottlenecks identified
- Feasibility assessed

✅ **Scientific Rigor**
- Distinction: mechanical ≠ semantic ≠ limitation
- Context separated: KNOWN ≠ SNAPSHOT-ONLY
- Observation ≠ interpretation (labeled)
- Facts ≠ opinions (identified)

---

## Known Constraints (Re-emphasizing)

From Review 0dafbad:

1. ✅ **No Core changes** (parent_edge_id only future option)
2. ✅ **Split provenance separated** (Context vs. Snapshot-only)
3. ✅ **Collapse: only survivor robust** (not full pipeline)
4. ✅ **Weight/Morph: still research** (no proven strategy)
5. ✅ **Edge cleanup: separate concern** (not rigging gap)
6. ✅ **Focus: mutation sequences** (realistic scenarios)
7. ✅ **Goal: evidence** (not production code)

---

## Ready to Execute

Phase 3C test infrastructure complete:
- ✅ PHASE-3C-PLAN.md (detailed methodology)
- ✅ test_mutation_sequences.py (ready to run)
- ✅ FINDINGS-3C.md (template for results)
- ✅ PHASE-3C-EXECUTION.md (this document)

**Next Step:** Execute tests → Populate findings → Analyze architecture implications

---

**Status:** ✅ READY FOR EXECUTION  
**Quality:** High (strict guidelines adhered to)  
**Owner:** Manu  
**Date:** August 2026
