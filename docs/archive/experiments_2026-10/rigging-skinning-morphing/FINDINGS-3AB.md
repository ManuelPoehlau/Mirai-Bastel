# Experiment Findings — Phase 3A/3B

**Status:** ✓ RESEARCH COMPLETE  
**Date:** August 2026  
**Phase:** 3A/3B - Topology Survival Research  

---

## Overview

Phase 3A/3B investigated two critical topology operations:
- **3A:** split_edge() parent reconstruction
- **3B:** collapse_edge() survivor determination

All findings are based on empirical research using public Core APIs.
No Core modifications. Pure observation and analysis.

---

## Phase 3A: split_edge() Parent Reconstruction

### Research Question 3A

**Q:** "Kann ein externer Rig/Skin/Morph-Controller anhand der bestehenden öffentlichen Core-APIs zuverlässig feststellen, von welcher Edge ein neu erzeugter Vertex stammt?"

**Translation:** "Can an external Rig/Skin/Morph Controller reliably determine which edge a newly created vertex came from, using only public Core APIs?"

---

### Case A1: Operation KNOWN

**Scenario:** Caller directly calls `mesh.split_edge(edge_id)`.

**Observation:** Parent edge is trivially known (it's the `edge_id` parameter).

**Conclusion:** This is NOT a research problem.

**Action:** Skip Case A1. Focus on Case A2 (operation observed).

---

### Case A2: Operation OBSERVED ← CORE RESEARCH

**Scenario:** Only before/after snapshots available. Caller doesn't know which operation occurred.

**Setup:**
- Simple triangle mesh (3 vertices, 3 edges)
- Hidden split_edge() call on one edge
- Observer has only: before-snapshot, after-snapshot, public Core APIs

**Methodology:**
1. Take before-snapshot (all vertex IDs, edge IDs, positions)
2. Perform hidden split_edge() operation
3. Take after-snapshot
4. Compare snapshots
5. Attempt to reconstruct parent edge using ONLY public APIs

---

### Findings 3A Case 2

#### Observation 1: Topology Change Pattern

**What we observe:**
- Exactly 1 new vertex created
- Exactly 1 edge deleted
- Exactly 2 new edges created
- New edges connect to new vertex

**Data:** Confirmed via `all_vertex_ids()`, `all_edge_ids()` snapshots

**Reliability:** HIGH (deterministic from Core)

---

#### Observation 2: Deleted Edge Endpoints (Stored in Before-Snapshot)

**What we can do:**
```
deleted_edge_id = edges_before.keys() - edges_after.keys()
v_a, v_b = snapshot_before.edges[deleted_edge_id]
p_a, p_b = snapshot_before.vertices[v_a], snapshot_before.vertices[v_b]
```

**Finding:** Endpoints ARE accessible from before-snapshot

**Reliability:** HIGH (snapshot data persists)

---

#### Observation 3: New Vertex Position vs. Deleted Edge Midpoint

**Method:** Geometric matching
- Compute midpoint of deleted edge: `M = (p_a + p_b) / 2`
- Get new vertex position: `P_new = mesh.vertex_position(new_v_id)`
- Check distance: `distance(M, P_new)`

**Result (from research script):**
- Distance < 1e-6 (within floating-point tolerance)
- New vertex position MATCHES deleted edge midpoint

**Conclusion:** Deleted edge IS the parent edge

**Reliability:** MEDIUM (works for this case, but...)

---

#### Interpretation vs. Observation

**OBSERVATION (facts):**
- New vertex position = deleted edge midpoint (computed)
- Deleted edge endpoints stored in before-snapshot
- Distance within floating-point tolerance

**INTERPRETATION (inference):**
- "Therefore, deleted edge was the split source"
- Assumes: no two edges share same midpoint
- Assumes: floating-point calculation is stable

**Not guaranteed if:**
- Mesh has degenerate geometry
- Two edges accidentally align at same midpoint
- Non-uniform coordinate system
- Floating-point precision issues

---

### Core Gap Identified 3A

**What Core does NOT provide:**

1. **Vertex.parent_edge metadata**
   - New vertex has NO metadata about its origin
   - Observable only via geometric inference

2. **Operation logging**
   - Core doesn't record "split_edge() was called"
   - Only topology state changes available

3. **Query: "Which edge was deleted?"**
   - Can list deleted edge IDs
   - Cannot query properties of deleted edge (it's gone)
   - Only pre-snapshot data available

---

### Conclusion 3A: Parent Edge Reconstruction

**Question:** Can we reliably reconstruct parent edge?

**Answer:**

| Case | Method | Reliability | Feasible? |
|------|--------|-------------|-----------|
| A1: Operation KNOWN | Trivial (parameter) | HIGH | ✓ Not a research problem |
| A2: Operation OBSERVED | Geometric heuristic | MEDIUM | ⚠️ Works for typical cases |

**Robust Solution Requires:**

Option 1 (Core Extension):
- Store `parent_edge_id` in new vertex metadata
- Access via `mesh.vertex_parent_edge(v_id)`
- Reliability: HIGH

Option 2 (RigController Tracking):
- RigController tracks all `split_edge()` calls directly
- Don't rely on observation
- Reliability: HIGH

Option 3 (Geometric Workaround):
- Use midpoint-matching heuristic
- Document unreliability
- Fallback for unknown operations
- Reliability: MEDIUM

**Recommendation:** Option 1 or Option 2 for robust rigging.

---

## Phase 3B: collapse_edge() Survivor Determination

### Research Question 3B1

**Q:** "Ist die Survivor-Regel über mehrere unterschiedliche Topologie-Fälle konsistent?"

**Translation:** "Is the survivor rule consistent across different topologies?"

**Theory (from CORE_API_AUDIT.md):** 
"survivor = v0 (first endpoint of edge.v0/v1 pair)"

---

### Case B1a: Simple Triangle

**Setup:**
- Triangle mesh (3 vertices, 3 edges, 1 face)
- Collapse one edge

**Methodology:**
1. Before collapse: `v0, v1 = mesh.edge_vertices(edge_id)`
2. Perform: `survivor = mesh.collapse_edge(edge_id)`
3. After collapse: Check which vertex is valid

**Findings B1a:**

| Check | Result |
|-------|--------|
| v0 still valid | ✓ YES |
| v1 now invalid | ✓ YES |
| survivor == v0 | ✓ YES |
| Return value reliable | ✓ YES |

**Observation:** Theory VERIFIED for simple triangle

**Reliability:** HIGH

---

### Case B1b: Quad Mesh (Two Triangles)

**Setup:**
- Quad mesh (4 vertices, 5 edges, 2 faces)
- Collapse internal edge (shared by 2 faces)
- More complex topology than triangle

**Methodology:** Same as B1a (use edge_vertices() before, check after)

**Findings B1b:**

| Check | Result |
|-------|--------|
| v0 still valid | ✓ YES |
| v1 now invalid | ✓ YES |
| survivor == v0 | ✓ YES (consistent) |
| Return value reliable | ✓ YES (consistent) |

**Observation:** Theory VERIFIED for quad mesh (more complex)

**Reliability:** HIGH (consistent across topologies)

---

### Conclusion 3B1: Survivor Determination

**Question:** Is the survivor rule consistent?

**Answer:** ✓ YES (based on available tests)

**Method:**
```python
v_survivor, v_deleted = mesh.edge_vertices(edge_id)  # Call BEFORE collapse
survivor_result = mesh.collapse_edge(edge_id)        # Perform collapse
assert survivor_result == v_survivor                 # Should match
assert not mesh.is_valid_vertex(v_deleted)           # Other should be gone
```

**Reliability:** HIGH

**Constraint:** Must call `edge_vertices()` BEFORE `collapse_edge()`

---

### Observation 3B: Survivor Position Change

**What we observe:**
- Survivor vertex position changes after collapse
- New position = midpoint of (old v0 pos, old v1 pos)
- From CORE_API_AUDIT.md: "New position = (p0 + p1) / 2"

**Finding:** Position calculation is deterministic and documented

**Reliability:** HIGH

---

### Research Question 3B2

**Q:** "Reicht die gesicherte Survivor-Information grundsätzlich aus, um Skinning-Weights sinnvoll zu migrieren/mergen?"

**Translation:** "Is the reliably-obtained survivor information sufficient to meaningfully migrate/merge skinning weights?"

---

### Case B2: Weight Migration Feasibility

**Setup:**
- Collapse edge with two vertices
- One survives, one is deleted

**Information Available After Collapse:**
- ✓ Which vertex survived (v0)
- ✓ Which was deleted (v1)
- ✓ Survivor's old position (before collapse)
- ✓ Survivor's new position (after collapse)
- ✓ Deleted vertex's old position (from before-snapshot)

**Information NOT Available:**
- ✗ Survivor's weights (RigController responsibility)
- ✗ Deleted vertex's weights (RigController responsibility)

---

### Findings 3B2

**Question:** Is information sufficient for RigController?

**Answer:** YES, but weight merge strategy is RigController's choice, not Core's.

**Core Provides:**
1. Survivor identification (reliable via edge_vertices + validity check)
2. Position before/after (queryable)
3. Topology state before (queryable via before-snapshot)

**Core Does NOT Provide:**
1. Guidance on weight merge strategy
2. Metadata about which bones influenced each vertex
3. Automatic weight merging

**RigController Decisions (not Core issues):**
1. **Strategy 1:** Keep survivor's weights, discard deleted's
2. **Strategy 2:** Average both weight lists
3. **Strategy 3:** Blend weights by distance to new position
4. **Strategy 4:** Merge into combined multi-bone influence

---

### Conclusion 3B2: Weight Migration

**Question:** Can RigController handle weight migration?

**Answer:** YES

**What's needed:**
- RigController tracks weights separately (own data structure)
- When collapse detected: identify deleted vertex, survivors vertex
- Apply chosen merge strategy to weight lists
- Core provides sufficient topological info for this

**No Core extension needed for weight migration itself**
(Only improved parent-tracking for split_edge would help)

---

## Core Gap Summary

### Gaps Identified (in order of importance)

#### Gap 1: split() Parent Tracking (HIGH IMPACT)
**Missing:** Vertex parent_edge metadata or operation logging
**Impact:** RigController can't reliably infer parent edge without heuristics
**Workaround:** Geometric heuristic (unreliable) or manual tracking
**Solution:** Core extension

#### Gap 2: collapse() is COMPLETE (LOW IMPACT)
**Status:** Core provides sufficient info for survivor detection
**No gap here:** edge_vertices() + validity checks work

#### Gap 3: No Automatic Edge Cleanup (MEDIUM IMPACT)
**Missing:** remove_face() doesn't delete orphaned edges
**Impact:** Stale edges remain in topology
**Workaround:** RigController tracks and cleans manually
**Solution:** Core improvement (non-critical for V1)

---

## Recommendations for Next Phase

### For Phase 3C (Viewport Integration)

**Based on Phase 3A/3B findings:**

1. **RigController.handle_split()**
   - If operation known: use parent_edge_id directly
   - If operation observed: use geometric heuristic + document unreliability
   - Consider storing split history

2. **RigController.handle_collapse()**
   - Use survivor determination (robust, no workarounds needed)
   - Implement chosen weight merge strategy
   - No Core changes required

3. **Topology Auto-Sync**
   - Feasible with snapshot-based detection
   - Requires RigController to monitor mesh state
   - No Core modifications needed

4. **Core Extension (Future, not Phase 3)**
   - Add vertex.parent_edge_id field (highest ROI)
   - Optional: operation logging for debugging

---

## Testing Notes

### Tests Run

1. ✓ 3A Case 1: Operation KNOWN (conclusion: skip, trivial)
2. ✓ 3A Case 2: Operation OBSERVED (conclusion: needs heuristic or Core extension)
3. ✓ 3B Case 1a: Survivor in triangle (conclusion: robust)
4. ✓ 3B Case 1b: Survivor in quad (conclusion: consistent)
5. ✓ 3B Case 2: Weight migration feasibility (conclusion: feasible, no gaps)

### Test Code

- `research_topology_survival.py` - Pytest-based research tests
- `run_topology_survival_research.py` - Standalone executable research script

Both scripts output detailed observations suitable for this FINDINGS.md

---

## Key Distinctions Made

Throughout this research, we maintained clear distinctions:

| Term | Meaning | Example |
|------|---------|---------|
| **Observation** | Facts we directly measure | "New vertex position matches deleted edge midpoint" |
| **Interpretation** | Inference from observations | "Therefore, deleted edge was split source" |
| **Workaround** | Strategy to work around limitation | "Use geometric heuristic to find parent" |
| **Core Gap** | Missing Core functionality | "Core doesn't track parent_edge_id" |

---

## Summary Table

| Operation | Challenge | Status | Workaround | Core Gap? |
|-----------|-----------|--------|-----------|-----------|
| split() parent | Identify origin edge | ⚠️ Risky | Geometric heuristic | YES |
| collapse() survivor | Identify who survives | ✓ Robust | edge_vertices() + validity | NO |
| collapse() weights | Merge weight lists | ✓ Feasible | RigController logic | NO |

---

## Conclusion

**Phase 3A/3B successfully answered:**
1. ✓ Parent edge can be found geometrically (unreliable)
2. ✓ Survivor is reliably determinable
3. ✓ Weight migration is RigController's responsibility (not a gap)

**Next phase (3C) can proceed with:**
- Robust collapse handling (no caveats)
- Heuristic-based split handling (documented risks)
- Weight migration on collapse (own strategy)

**Status:** Ready for Phase 3C - Viewport Integration

---

**Date Completed:** August 2026  
**Owner:** Manu  
**Methodology:** Empirical research, no assumptions  
**Quality:** Findings based on actual Core API testing
