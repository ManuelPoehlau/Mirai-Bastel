# Phase 3C: Topology Mutation Sequence Research

**Status:** ✓ PLANNED (ready to execute)  
**Date:** August 2026  
**Owner:** Manu  
**Goal:** Investigate if RigController can survive real mutation sequences

---

## Scope & Boundaries (from Review 0dafbad)

### What Phase 3C IS

✅ **Empirical investigation** of consecutive topology mutations  
✅ **Architecture evidence** (not production implementation)  
✅ **External synchronization** under realistic conditions  
✅ **Separating concerns:** Operation-Context vs. Snapshot-only observation  

### What Phase 3C IS NOT

❌ **NOT producing production code** (still research phase)  
❌ **NOT finalizing weight migration semantics** (still open question)  
❌ **NOT solving edge cleanup** (separate topology concern)  
❌ **NOT modifying Core** (parent_edge_id only a future option)  

---

## Central Research Question 3C

**"Kann der externe RigController eine echte Mutationsequenz konsistent überleben?"**

Translation: "Can the external RigController consistently survive a real sequence of mutations?"

---

## Test Scope: Mutation Sequences

### Sequence 1: Basic Pair

```
[Initial Mesh] → split(edge_0) → collapse(edge_new) → [Final Mesh]
```

Questions:
- Can RigController track new vertex from split?
- Can weights/morphs survive split → collapse sequence?
- What information is available at each step?
- What is LOST between mutations?

### Sequence 2: Triangle Subdivision

```
[Triangle] → split(e0) → split(e1) → connect(v_a, v_b) → [Mesh]
```

Questions:
- Multiple new vertices: which are parents?
- Weight distribution across new vertices?
- connect() behavior with split vertices?

### Sequence 3: Collapse Chain

```
[Mesh] → collapse(e0) → collapse(e1) → collapse(e2) → [Simplified]
```

Questions:
- Survivor rule holds across chain?
- Weight accumulation on survivor?
- Morphs survive repeated collapses?

### Sequence 4: Mixed Operations (if time permits)

```
[Quad] → split() → connect() → collapse() → [Final]
```

Realistic scenario combining all operations.

---

## Research Methodology: Per Mutation

For EACH mutation in sequence, investigate:

### 1. BASELINE
- Mesh state (vertices, edges, faces)
- RigController state (weights, morphs, bones)
- Snapshot (topology)

### 2. OPERATION CONTEXT vs. SNAPSHOT-ONLY

#### Context A: OPERATION KNOWN (Controller initiated)
```python
# Controller directly calls operation
edge_id = controller.choose_edge()
new_vertex = mesh.split_edge(edge_id)
# Controller knows: edge_id (parent), edge_id, new_vertex
# → Parent is trivially known
```

**Research:** Not a problem. This is the EXPECTED path.

#### Context B: SNAPSHOT-ONLY (External change)
```python
# Controller only observes before/after
before = snapshot()
# [External: some operation happened]
after = snapshot()
changes = diff(before, after)
# Controller knows ONLY: topology diff
# → Must infer what happened
```

**Research:** Can we reliably infer with available Core APIs?

**CRITICAL:** Must separate these contexts in testing.

### 3. OBSERVATION: What Core Provides

#### For split_edge():
- ✓ New vertex ID (available)
- ✓ New edges IDs (available)
- ✓ Deleted edge endpoints (in before-snapshot)
- ✗ Which edge was split? (inference needed, not guaranteed)

#### For collapse_edge():
- ✓ Survivor ID (deterministic via edge_vertices)
- ✓ Deleted vertex ID (from validity check)
- ✓ New position (queryable)
- ✓ Fully deterministic

#### For connect_vertices():
- ✓ Two faces created
- ✓ One edge created
- ✓ No vertices created/deleted
- ✗ Which face was split? (can infer via boundary)

### 4. EXTERNAL SYNCHRONIZATION

**Question:** What must RigController do to stay synchronized?

#### Split:
```
Observation: 1 new vertex
Action: handle_new_vertex(v_new, parent=?)
  → If parent known: inherit weights/morphs
  → If parent unknown: default behavior
Challenge: Identify parent (operation-context dependent)
```

#### Collapse:
```
Observation: 1 deleted vertex, 1 edge deleted
Action: handle_deleted_vertex(v_dead), merge_weights(v_surv)
  → Survivor: determined via edge_vertices() before
Challenge: Which merge strategy? (research question)
```

#### Connect:
```
Observation: 1 new edge, 2 new faces
Action: handle_faces_split(f_old)
  → No vertices affected
Challenge: Morph targets on boundary vertices? Weights?
```

### 5. WEIGHT BEHAVIOR

**NOT assuming a single "correct" strategy.**

#### Questions:
- What happens to survivor's weights after collapse?
- What happens to deleted vertex's weights?
- Should we MERGE, KEEP, AVERAGE, BLEND?

#### Research Approach:
- Document what's NECESSARY (core constraints)
- Document what's POSSIBLE (options)
- Do NOT claim one strategy is "proven correct"

#### Three strategies to observe:
1. **Strategy A (Conservative):** Keep survivor's weights only
2. **Strategy B (Average):** Combine weight lists somehow
3. **Strategy C (Blend):** Distance-based blending

**Test each, observe consequences, document trade-offs.**

### 6. MORPH BEHAVIOR

**Similar open question as weights.**

#### Questions:
- New vertex (from split): inherit parent's morphs?
- Deleted vertex (from collapse): transfer morphs to survivor?
- Shared morph boundaries (split/connect): what happens?

#### Research Approach:
- Track morph offsets through mutations
- Observe: do morphs make sense after sequence?
- Document: which choices preserve deformation intent?

### 7. REMAINING UNCERTAINTY

**Explicitly document:**
- What we can NOT answer with current Core APIs
- What requires assumptions
- What needs manual specification (weight merge, morph strategy)
- What might need Core extension (parent_edge_id tracking)

---

## Test Cases Structure

### Test Case 3C-1: split() in Operation-Context

```python
def test_3c1_split_operation_context():
    """
    3C-1: split() when Controller knows edge_id
    
    Scenario: Controller initiates split
    Context: Operation KNOWN (not snapshot-only)
    
    Questions:
    - Can we track new vertex → parent edge?
    - Can we inherit weights?
    - Can we inherit morphs?
    - What information is available?
    """
    
    mesh = create_simple_mesh()
    rig = RigController(mesh)
    
    # Setup: vertex with weights and morphs
    edge_id = mesh.all_edge_ids()[0]
    v0, v1 = mesh.edge_vertices(edge_id)
    rig.set_vertex_weight(v0, bone_id=0, weight=0.7)
    rig.add_morph_target("smile")
    rig.set_morph_offset("smile", v0, (0.0, 0.1, 0.0))
    
    # BASELINE
    snap_before = rig.take_snapshot("before_split")
    
    # OPERATION (KNOWN)
    new_v_id, _, _ = mesh.split_edge(edge_id)  # Controller knows edge_id
    
    # OBSERVATION
    snap_after = rig.take_snapshot("after_split")
    changes = rig.detect_changes(snap_before, snap_after)
    
    # FINDINGS
    print(f"\n3C-1: split() in Operation-Context")
    print(f"New vertex: {new_v_id}")
    print(f"Parent edge: {edge_id} (KNOWN to controller)")
    
    # Try to inherit
    rig.handle_new_vertex(new_v_id, parent=v0)  # Or v1, depending on split
    
    # VERIFY
    weights_new = rig.get_vertex_weights(new_v_id)
    morph_new = rig.get_morph_offset("smile", new_v_id)
    
    print(f"Inherited weights: {weights_new}")
    print(f"Inherited morph: {morph_new}")
    
    # CONCLUSION
    # What worked? What didn't? What was uncertain?
```

### Test Case 3C-2: split() in Snapshot-only Context

```python
def test_3c2_split_snapshot_only():
    """
    3C-2: split() observed via snapshots only
    
    Scenario: Only before/after available
    Context: Operation NOT KNOWN (snapshot-only)
    
    Questions:
    - Can we reliably identify parent edge?
    - Geometric heuristic reliability?
    - When does it fail?
    """
    
    # [Hidden operation scenario]
    # Caller can't call split directly
    # Only sees: before → after snapshots
```

### Test Case 3C-3: collapse() Sequence

```python
def test_3c3_collapse_sequence():
    """
    3C-3: Chain of collapses
    
    Scenario: collapse → collapse → collapse
    Context: Does survivor rule hold throughout?
    
    Questions:
    - Survivor consistent in chain?
    - Weight accumulation?
    - Morph preservation?
    """
```

### Test Case 3C-4: Mixed Sequence

```python
def test_3c4_mixed_sequence():
    """
    3C-4: split → collapse → connect
    
    Scenario: Realistic sequence of mutations
    Context: Multiple operations with dependencies
    
    Questions:
    - What's the most challenging aspect?
    - Where does sync fail?
    - What's the bottleneck?
    """
```

---

## Key Distinctions to Maintain

### Distinction 1: Operation Context

| Context | What We Know | Challenge | Example |
|---------|-------------|-----------|---------|
| **KNOWN** | edge_id/face_id directly | None (parent trivial) | `split_edge(edge_id)` → parent is edge_id |
| **SNAPSHOT-ONLY** | Only topology diff | Must infer operation | Before/after → "what happened?" |

**CRITICAL:** Test BOTH. Don't conflate.

### Distinction 2: Information Type

| Type | Reliable | Caveats |
|------|----------|---------|
| **Core-provided** | YES | Only if Core guarantees it |
| **Computed from snapshot** | MEDIUM | Depends on mesh geometry |
| **Inferred/guessed** | MAYBE | Document explicitly |

### Distinction 3: Semantic vs. Mechanical

| Question | Type | Status |
|----------|------|--------|
| "Which vertex survives collapse?" | **Mechanical** | ✓ Core guarantees |
| "How to merge survivor's weights?" | **Semantic** | ? Still open |
| "Should morphs transfer?" | **Semantic** | ? Still open |

**Never claim mechanical answers for semantic questions.**

---

## Documentation Requirements per Test

### For each test, document:

1. **Observation** (facts)
   - What topology changed?
   - What Core APIs say?
   - What snapshots show?

2. **Available Information** (from Core)
   - Which data is reliable?
   - Which requires inference?
   - Which is guesswork?

3. **External Sync** (RigController)
   - What actions taken?
   - What worked?
   - What failed?
   - Why?

4. **Uncertainty** (remaining questions)
   - What couldn't we answer?
   - Why? (Core limitation? Semantic question?)
   - What would help?

5. **Implication** (for architecture)
   - Can sequence be handled robustly?
   - What assumptions needed?
   - What might break?

---

## Success Criteria for Phase 3C

✅ **Test Coverage**
- ✓ split() in both contexts (known + snapshot-only)
- ✓ collapse() sequence
- ✓ connect() behavior
- ✓ Mixed sequence (if feasible)

✅ **Research Quality**
- ✓ Observation/Interpretation clearly separated
- ✓ Core capabilities vs. gaps clearly documented
- ✓ Semantic vs. mechanical questions distinguished
- ✓ No assumptions stated as facts

✅ **Architecture Insights**
- ✓ What CAN be automated (robust)
- ✓ What requires manual specification
- ✓ What needs Core extension (if any)
- ✓ What's still open question

---

## Boundaries (What Phase 3C Does NOT Do)

❌ **NOT implementing production weight merge**
- We observe options, don't finalize one

❌ **NOT claiming collapse is "production-ready"**
- Only survivor-identification is robust
- Rest of collapse pipeline still TBD

❌ **NOT extending Core**
- parent_edge_id remains an option for Phase 4
- Phase 3C uses existing public APIs only

❌ **NOT solving edge cleanup**
- Separate topology issue
- Not critical for rigging

❌ **NOT finalizing morph migration**
- Still a research question
- Multiple valid approaches

---

## Expected Outcomes from Phase 3C

### Outcome A: Architecture Evidence
- "RigController CAN survive split → collapse sequence IF..."
- "REQUIRES: operation context tracking" OR
- "REQUIRES: Core extension" OR
- "REQUIRES: manual weight strategy specification"

### Outcome B: Gaps Identified
- "split() parent tracking needs Core support for robust operation-observed case"
- "Weight merge semantics still open"
- "Morph transfer rules still open"

### Outcome C: Feasibility Assessment
- "Viewport integration viable if... [condition]"
- "Auto-sync viable if... [condition]"
- "Which approach is most promising?"

---

## Timeline

Phase 3C is intensive research, not rushed implementation.

Estimate: 2-3 weeks of empirical testing + documentation

Expected output:
- 5-10 detailed research test cases
- FINDINGS-3C.md with complete analysis
- Architecture recommendation for Phase 4

---

## Next: Detailed Test Implementation

Ready to implement test_mutation_sequences.py based on this plan.

Each test:
- 50-150 lines (detailed, not just assertions)
- Print statements for observations
- Clear conclusion per test
- Distinct: known vs. snapshot-only

---

**Status:** Phase 3C PLAN COMPLETE  
**Next:** Implement test suite per these guidelines  
**Owner:** Manu  
**Quality Gate:** Adhere strictly to boundaries and distinctions
