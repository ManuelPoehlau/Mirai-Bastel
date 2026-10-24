# Phase 2: RigController Prototype — Experiment-Only Research

**Objective:** Build a functional external RigController and systematically discover through experimentation **which Core capabilities are actually required for Rigging/Skinning to survive topology changes**.

**Constraint:** Zero modifications to `src/core/`. Use only existing public Core APIs. Findings emerge from experiments, not from assumptions.

---

## Core Research Question

**"What information must an external Rig/Skin/Morph system have access to in order to correctly update itself when topology changes occur?"**

Sub-questions:
- Can we detect that topology changed? (How?)
- Can we identify which vertices/edges/faces are new/deleted?
- Can we map old → new vertices to migrate weights?
- Can we preserve morph-target data consistently?
- Where does the Core API fall short?

---

## Critical Principles for Phase 2

### 1. No Pre-filled Hypotheses
- FINDINGS.md starts empty
- Every entry comes from actual experiment results, not assumptions
- Placeholder template only; no "expected" outcomes

### 2. detect_topology_changes() is Observational, Not Prescriptive
```python
# WRONG:
new_vertex → "must be from split()"
deleted_vertex → "must be from collapse()"

# RIGHT:
new_vertex → "vertex created; type unknown. Investigate further."
deleted_vertex → "vertex deleted; reason unknown. Investigate further."
```

### 3. No Geometric Heuristics Without Evidence
- Do NOT assume "closest vertices" are parents
- Do NOT assume "average position" means anything
- First: Exhaust all public Core APIs
- Then: Document what's impossible
- Only then: Consider heuristics (and mark as unreliable)

### 4. collapse() Requires Rigorous Investigation
Critical questions for each collapse():
- Can we determine which vertex dies and which survives?
- How reliable is this determination?
- Can Core APIs tell us this unambiguously?
- If not: Document as Core API gap

### 5. Undo/Redo & Serialization Out of Scope
- Phase 2 explores **external RigController model only**
- Do NOT integrate weights/morphs into Mesh.export_state()
- Do NOT add undo/redo for rig data
- Document as "Open Questions" if relevant

### 6. Goal: Discover, Don't Prescribe
**Wrong mindset:** "Core needs observers, so I'll design for that"
**Right mindset:** "What can the Core API provide? What gaps exist?"

---

## Phase 2 Structure

### 2.1 RigController Foundation (Week 1)

**File:** `experiments/rigging-skinning-morphing/src/rig_controller.py`

```python
class RigController:
    """
    Manages rigging, skinning, and morph-targets externally.
    Uses only public Core Mesh APIs — no listeners, observers, or Core modifications.
    Designed for empirical exploration of topology-rig integration.
    """
    
    def __init__(self, mesh):
        self.mesh = mesh
        self.bones = {}  # {bone_id: Bone(...), ...}
        self.skinning_weights = {}  # {vertex_id: [(bone_id, weight), ...], ...}
        self.morph_targets = {}  # {morph_name: {vertex_id: (dx, dy, dz), ...}, ...}
        
        # For detecting changes
        self.topology_snapshots = []  # List of (iteration, vertex_ids, edge_ids, face_ids)
        self.iteration_counter = 0
    
    def add_bone(self, bone_id, name, parent_id=None):
        self.bones[bone_id] = Bone(bone_id, name, parent_id)
    
    def set_vertex_weight(self, vertex_id, bone_id, weight):
        if vertex_id not in self.skinning_weights:
            self.skinning_weights[vertex_id] = []
        self.skinning_weights[vertex_id].append((bone_id, weight))
    
    def add_morph_target(self, morph_name):
        self.morph_targets[morph_name] = {}
    
    def set_morph_offset(self, morph_name, vertex_id, offset_xyz):
        if morph_name not in self.morph_targets:
            self.add_morph_target(morph_name)
        self.morph_targets[morph_name][vertex_id] = offset_xyz
    
    # ===== OBSERVATION & DETECTION =====
    
    def take_topology_snapshot(self, label=""):
        """
        Record current mesh state for comparison.
        Used to detect changes between operations.
        """
        current_state = {
            "iteration": self.iteration_counter,
            "label": label,
            "vertex_ids": frozenset(v.id for v in self.mesh.vertices),
            "edge_ids": frozenset(e.id for e in self.mesh.edges),
            "face_ids": frozenset(f.id for f in self.mesh.faces),
        }
        self.topology_snapshots.append(current_state)
        self.iteration_counter += 1
        return current_state
    
    def detect_changes_since_last_snapshot(self):
        """
        Compare current mesh to last snapshot.
        Return observed facts, not interpretations.
        
        Returns:
        {
            "new_vertices": [list of vertex IDs],
            "deleted_vertices": [list of vertex IDs],
            "new_edges": [list of edge IDs],
            "deleted_edges": [list of edge IDs],
            "new_faces": [list of face IDs],
            "deleted_faces": [list of face IDs],
        }
        
        NOTE: Presence of new_vertices does NOT imply split().
        Presence of deleted_vertices does NOT imply collapse().
        These are observations, not conclusions.
        """
        if not self.topology_snapshots:
            return {"new_vertices": [], "deleted_vertices": [], 
                    "new_edges": [], "deleted_edges": [],
                    "new_faces": [], "deleted_faces": []}
        
        last = self.topology_snapshots[-1]
        current_v = frozenset(v.id for v in self.mesh.vertices)
        current_e = frozenset(e.id for e in self.mesh.edges)
        current_f = frozenset(f.id for f in self.mesh.faces)
        
        return {
            "new_vertices": list(current_v - last["vertex_ids"]),
            "deleted_vertices": list(last["vertex_ids"] - current_v),
            "new_edges": list(current_e - last["edge_ids"]),
            "deleted_edges": list(last["edge_ids"] - current_e),
            "new_faces": list(current_f - last["face_ids"]),
            "deleted_faces": list(last["face_ids"] - current_f),
        }
    
    def query_vertex(self, vertex_id):
        """
        Investigate a vertex using Core APIs.
        Document what information Core can provide.
        """
        vertex = self.mesh.vertices.get(vertex_id)
        if not vertex:
            return {"status": "not found"}
        
        findings = {
            "vertex_id": vertex_id,
            "position": vertex.position,
            "connected_edges": [],
            "connected_faces": [],
            "edge_details": [],
            "face_details": [],
        }
        
        # Use Core APIs to explore
        # Document: What can we actually learn?
        # (Adjust to match actual Core API)
        # for edge in self.mesh.edges:
        #     if vertex_id in edge.vertices:
        #         findings["connected_edges"].append({
        #             "edge_id": edge.id,
        #             "other_vertex": edge.vertices[1] if edge.vertices[0] == vertex_id else edge.vertices[0],
        #             "edge_data": {...}
        #         })
        
        return findings
    
    def query_edge(self, edge_id):
        """
        Investigate an edge using Core APIs.
        Specifically useful for understanding split/collapse.
        """
        edge = self.mesh.edges.get(edge_id)
        if not edge:
            return {"status": "not found"}
        
        findings = {
            "edge_id": edge_id,
            "vertices": edge.vertices,  # The two endpoints
            "connected_faces": [],
            # More data as Core API reveals
        }
        
        return findings
    
    # ===== TOPOLOGY HANDLING (To be developed empirically) =====
    
    def handle_topology_change(self, changes, context="unknown"):
        """
        Attempt to maintain rig consistency after topology changes.
        Strategy: Investigate before deciding on action.
        
        Args:
            changes: dict from detect_changes_since_last_snapshot()
            context: Optional description of what operation occurred
        
        Returns:
            {
                "actions_taken": [...],
                "unresolved_questions": [...],
                "warnings": [...],
            }
        """
        results = {
            "actions_taken": [],
            "unresolved_questions": [],
            "warnings": [],
        }
        
        # Handle new vertices
        for new_vertex_id in changes["new_vertices"]:
            # Question: Where did this come from?
            # Strategy: Investigate using available Core APIs
            vertex_info = self.query_vertex(new_vertex_id)
            
            # Can we determine parent? Investigate.
            parent_found = self._try_infer_parent_vertex(new_vertex_id, vertex_info)
            
            if parent_found:
                # Action: Inherit weights
                self._inherit_weights(new_vertex_id, parent_found)
                results["actions_taken"].append({
                    "new_vertex": new_vertex_id,
                    "action": "inherit weights",
                    "from_parent": parent_found,
                })
            else:
                # Question: Cannot determine parent
                results["unresolved_questions"].append({
                    "new_vertex": new_vertex_id,
                    "question": "Cannot infer parent vertex. Weights unknown.",
                    "debug_info": vertex_info,
                })
                results["warnings"].append(
                    f"Vertex {new_vertex_id} has no weights assigned"
                )
        
        # Handle deleted vertices
        for dead_vertex_id in changes["deleted_vertices"]:
            self._cleanup_dead_vertex(dead_vertex_id)
            results["actions_taken"].append({
                "dead_vertex": dead_vertex_id,
                "action": "cleanup",
            })
        
        return results
    
    def _try_infer_parent_vertex(self, new_vertex_id, vertex_info):
        """
        Attempt to determine which vertex is the parent of new_vertex_id.
        
        Strategy:
        1. Exhaust all Core APIs first
        2. Document what's learnable
        3. Only if nothing works: mark as unsolvable
        4. Do NOT use geometric heuristics without explicit evidence
        
        Returns:
            parent_vertex_id if confident, None if unknown
        """
        # Placeholder: Implement empirically
        # This is where we'll discover what Core APIs can tell us
        return None
    
    def _inherit_weights(self, new_vertex_id, parent_vertex_id):
        """Copy weights from parent to new vertex."""
        if parent_vertex_id in self.skinning_weights:
            self.skinning_weights[new_vertex_id] = \
                list(self.skinning_weights[parent_vertex_id])
            
            # Same for morphs
            for morph_name in self.morph_targets:
                if parent_vertex_id in self.morph_targets[morph_name]:
                    self.morph_targets[morph_name][new_vertex_id] = \
                        self.morph_targets[morph_name][parent_vertex_id]
    
    def _cleanup_dead_vertex(self, vertex_id):
        """Remove weights/morphs for deleted vertex."""
        if vertex_id in self.skinning_weights:
            del self.skinning_weights[vertex_id]
        
        for morph_name in self.morph_targets:
            if vertex_id in self.morph_targets[morph_name]:
                del self.morph_targets[morph_name][vertex_id]
    
    # ===== DEFORMATION =====
    
    def deform_mesh(self, bone_transforms):
        """Apply rig to mesh, return deformed positions."""
        deformed = {}
        for vertex in self.mesh.vertices:
            if vertex.id in self.skinning_weights:
                deformed[vertex.id] = self._compute_skinned_position(
                    vertex, bone_transforms
                )
            else:
                deformed[vertex.id] = vertex.position
        return deformed
    
    def _compute_skinned_position(self, vertex, bone_transforms):
        """Linear blend skinning."""
        position = (0, 0, 0)
        total_weight = 0
        
        for bone_id, weight in self.skinning_weights[vertex.id]:
            if bone_id in bone_transforms:
                transform = bone_transforms[bone_id]
                transformed = transform.apply(vertex.position)
                position = tuple(p + w*t for p, w, t in 
                               zip(position, [weight]*3, transformed))
                total_weight += weight
        
        if total_weight > 0:
            position = tuple(p / total_weight for p in position)
        
        return position
```

---

### 2.2 Topology Change Analysis & Documentation (Week 1–1.5)

**File:** `experiments/rigging-skinning-morphing/TOPOLOGY_ANALYSIS.md`

Template: For each operation, systematically document **what we observe and learn**, not what we assume.

```markdown
# Topology Analysis: Empirical Findings

## Operation: split(edge_id)

### Execution
1. Create simple test mesh with known edge
2. Record snapshot before operation
3. Perform split()
4. Record snapshot after
5. Compare

### Observed Changes
- New vertices created: [list with IDs]
- Deleted vertices: none
- New edges: [list with IDs]
- Modified faces: [count]

### Questions Investigated

#### Q1: Which edge was split?
- Core provides edge_id parameter ✓
- Can we validate it? [investigate]
- Result: [findings]

#### Q2: What are the edge endpoints?
- Core API: mesh.edges[edge_id].vertices [CHECK ACTUAL API]
- Can we access them? YES/NO
- Result: [what did we learn]

#### Q3: What is the new vertex's position?
- Core API: mesh.vertices[new_id].position [CHECK]
- Is it meaningful? [findings]
- Result: [what did we learn]

#### Q4: Can we infer this is a split() and not another op?
- Observed: 1 new vertex, N new edges
- Inference attempt: "This looks like split()"
- Confidence: HIGH/MEDIUM/LOW
- Result: [findings]

#### Q5: Can we reliably identify the parent vertex?
- Geometric approach: "closest vertex"?
- Topology approach: edge endpoints?
- Both? One?
- Result: [findings]

### Current Understanding
[What can RigController reliably do? What's unclear?]

### Open Questions
[What would we need from Core to answer remaining questions?]

### Next Steps
[What to test next]
```

---

### 2.3 Unit Tests — Research Tests (Week 1)

**File:** `experiments/rigging-skinning-morphing/tests/test_rig_controller.py`

```python
import pytest
from rig_controller import RigController
from src.core import Mesh

class TestTopologyObservation:
    """
    These are RESEARCH TESTS.
    Goal: Document what Core APIs tell us, not just "assert it works"
    """
    
    def test_split_creates_new_vertex(self):
        """
        RESEARCH: When split() occurs, how do we detect it?
        """
        mesh = Mesh()
        rig = RigController(mesh)
        
        # Setup
        edge_id = ...  # Create test edge
        rig.take_topology_snapshot("before_split")
        
        # Execute
        new_vertex_id = mesh.split(edge_id)
        
        # Observe
        changes = rig.detect_changes_since_last_snapshot()
        
        # Analysis (not assertion)
        assert new_vertex_id in changes["new_vertices"]
        print(f"✓ New vertex detected: {new_vertex_id}")
        print(f"✓ All new vertices: {changes['new_vertices']}")
        print(f"  Observation: Can definitively detect vertex creation")
    
    def test_split_query_new_vertex(self):
        """
        RESEARCH: What can we learn about the new vertex?
        """
        mesh = Mesh()
        rig = RigController(mesh)
        edge_id = ...
        
        rig.take_topology_snapshot("before")
        new_vertex_id = mesh.split(edge_id)
        rig.take_topology_snapshot("after")
        
        # Investigate
        vertex_info = rig.query_vertex(new_vertex_id)
        edge_info = rig.query_edge(edge_id)
        
        print(f"\n--- New Vertex Investigation ---")
        print(f"New vertex {new_vertex_id}:")
        print(f"  Position: {vertex_info['position']}")
        print(f"  Connected edges: {vertex_info['connected_edges']}")
        print(f"  Connected faces: {vertex_info['connected_faces']}")
        
        print(f"\nSplit edge {edge_id}:")
        print(f"  Endpoints: {edge_info['vertices']}")
        
        # Document findings
        # What can we conclude? What's unclear?
        # This is research, not a pass/fail
    
    def test_collapse_which_survives(self):
        """
        RESEARCH: After collapse(), which vertex survives?
        Can Core APIs tell us definitively?
        """
        mesh = Mesh()
        rig = RigController(mesh)
        
        # Setup edge with known vertices
        edge_id = ...
        v1, v2 = mesh.edges[edge_id].vertices
        
        # Weights for reference
        rig.set_vertex_weight(v1, "bone_1", 1.0)
        rig.set_vertex_weight(v2, "bone_2", 0.5)
        
        rig.take_topology_snapshot("before_collapse")
        
        # Execute
        survivor_id = mesh.collapse(edge_id)
        
        # Observe
        changes = rig.detect_changes_since_last_snapshot()
        
        print(f"\n--- Collapse Investigation ---")
        print(f"Edge {edge_id} endpoints: {v1}, {v2}")
        print(f"Core returned survivor: {survivor_id}")
        print(f"Observed deleted: {changes['deleted_vertices']}")
        
        # CRITICAL QUESTION:
        # Can we reliably determine which vertex was deleted?
        dead = changes["deleted_vertices"][0] if changes["deleted_vertices"] else None
        
        if dead:
            print(f"✓ Dead vertex: {dead}")
            print(f"✓ Survivor: {survivor_id}")
            print(f"  For weight merge: need to know both IDs unambiguously")
            
            # Investigate: Can Core tell us this?
            # Does mesh.collapse() return survivor reliably?
            assert survivor_id in [v1, v2], "Survivor should be one of the endpoints"
        
        # Document findings
```

---

### 2.4 FINDINGS.md Template (Empty, Waiting for Results)

**File:** `experiments/rigging-skinning-morphing/FINDINGS.md`

```markdown
# Phase 2 Findings: External Rigging on Stable Core

**Status: EXPERIMENTAL — Filled in as experiments progress**

This document records actual findings from Phase 2 experiments.
No hypotheses; only results from systematic investigation.

---

## Finding 1: Vertex Creation Detection

### Experiment
[Description of what test was run]

### Observation
[What actually happened]

### Conclusion
[What we learned]

---

## Finding 2: Collapse Vertex Identification

### Experiment
[...]

### Observation
[...]

### Conclusion
[...]

---

## Finding 3: Parent Vertex Inference

### Experiment
[...]

### Observation
[...]

### Conclusion
[...]

---

## Core API Capabilities

[To be documented as discovered]

---

## Core API Gaps

[To be documented as discovered]

---

## Unanswered Questions (Open for Phase 3+)

[Listed as we discover unknowns]
```

---

## Success Criteria for Phase 2

✅ **Phase 2 is successful if:**
1. RigController prototype is functional (manages bones, weights, morphs)
2. Systematic investigation of 4+ topology operations completed
3. FINDINGS.md filled with actual results (not predictions)
4. Clear documentation of "what Core provides" vs "what's missing"
5. Specific, concrete Core API gaps identified (if any)
6. 37/37 Core tests still passing (zero Core modifications)
7. Research methodology demonstrated: observe → document → conclude

❌ **Fallback if issues:**
- "This operation is impossible to handle externally" → Document why + flag for Core consideration
- "Multiple interpretations possible" → Document ambiguity + propose clarification
- Any Core API unclear → Investigate further before concluding it's missing

---

## Deliverables

```
experiments/rigging-skinning-morphing/
├── src/
│   ├── rig_controller.py         ← Empirical, observation-focused
│   ├── bone.py                   ← Simple hierarchy
│   └── deformation.py            ← Skinning math
├── tests/
│   └── test_rig_controller.py    ← Research tests (not just assertions)
├── TOPOLOGY_ANALYSIS.md          ← Systematic investigation of each op
├── FINDINGS.md                   ← Actual results (fills in during Phase 2)
└── README.md                     ← Updated with Phase 2 methodology & results
```

---

## Timeline

- **Week 1:** RigController foundation + baseline research tests
- **Week 1–1.5:** Systematic investigation of split/collapse/connect
- **Deliverable:** Functional prototype + documented findings

**Key:** Each finding is dated, backed by experiment, and includes questions for follow-up.

---

**Owner:** Manu  
**Constraint:** Zero `src/core/` modifications  
**Principle:** "Observe first, conclude second, decide third"
