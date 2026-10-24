# Phase 2: RigController Prototype — Experiment-Only Research

**Objective:** Build a functional external RigController and systematically discover **which Core capabilities are actually required for Rigging/Skinning to survive topology changes**.

**Constraint:** Zero modifications to `src/core/`. Use only existing public Core APIs.

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

## Phase 2 Structure

### 2.1 RigController Foundation (Week 1)

**File:** `experiments/rigging-skinning-morphing/src/rig_controller.py`

```python
class RigController:
    """
    Manages rigging, skinning, and morph-targets independently.
    Uses only public Core Mesh APIs — no listeners, observers, or Core modifications.
    """
    
    def __init__(self, mesh):
        self.mesh = mesh
        self.bones = {}  # {bone_id: Bone(...), ...}
        self.skinning_weights = {}  # {vertex_id: [(bone_id, weight), ...], ...}
        self.morph_targets = {}  # {morph_name: {vertex_id: (dx, dy, dz), ...}, ...}
        
        # Snapshot for detecting changes
        self.last_known_vertex_ids = set(v.id for v in mesh.vertices)
    
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
    
    # Core API: Detect topology changes
    def detect_topology_changes(self):
        """
        Use existing Core APIs to detect what changed.
        Return: {new_vertices: [...], deleted_vertices: [...], modified_connectivity: bool}
        """
        current_vertex_ids = set(v.id for v in self.mesh.vertices)
        
        new_vertices = current_vertex_ids - self.last_known_vertex_ids
        deleted_vertices = self.last_known_vertex_ids - current_vertex_ids
        
        self.last_known_vertex_ids = current_vertex_ids
        
        return {
            "new_vertices": list(new_vertices),
            "deleted_vertices": list(deleted_vertices),
        }
    
    # Research method: What can we learn about a new vertex?
    def analyze_new_vertex(self, vertex_id):
        """
        Given a new vertex ID (from split/other ops), what can we learn from Core APIs?
        
        Document findings:
        - Can we find its connected edges?
        - Can we find what faces it belongs to?
        - Can we infer a parent vertex (for split)?
        - Can we determine position?
        """
        vertex = self.mesh.vertices.get(vertex_id)
        if not vertex:
            return None
        
        findings = {
            "vertex_id": vertex_id,
            "position": vertex.position,
            "connected_edges": [],  # Try via Core API
            "connected_faces": [],  # Try via Core API
            "edge_data": [],  # What info does each edge provide?
        }
        
        # Use Core APIs to explore
        # Example (pseudo-code; adjust to actual Core API):
        # for edge in self.mesh.edges:
        #     if vertex_id in edge.vertices:
        #         findings["connected_edges"].append(edge.id)
        
        return findings
    
    def handle_vertex_deletion(self, vertex_id):
        """
        Vertex was deleted. Clean up local data.
        
        Question: Can we detect WHY it was deleted?
        (collapse vs other operation)
        """
        if vertex_id in self.skinning_weights:
            del self.skinning_weights[vertex_id]
        
        for morph_name in self.morph_targets:
            if vertex_id in self.morph_targets[morph_name]:
                del self.morph_targets[morph_name][vertex_id]
    
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

For each topology operation, systematically document:

#### Template:

```markdown
## Operation: split(edge)

### What Core Tells Us
- **New vertex created:** vertex_id = X
- **New vertex position:** Can we get it? YES/NO
- **Parent vertices (edge endpoints):** Can we find them? YES/NO/HOW?
- **Connected faces:** Can we find them? YES/NO/HOW?

### What RigController Needs to Know
- New vertex's position ✓ (from Core)
- Which vertices were the edge's endpoints (to inherit weights)
- Is this a split or another operation? (Must we infer?)

### What Core API Provides
- vertex.position ✓
- mesh.edges[edge_id].vertices ✓
- mesh.faces_containing_edge(edge_id) — EXISTS? YES/NO

### What's Missing
- No direct API to say "this edge was just split" (must detect via vertex set)
- No direct parent-child relationship tracking
- [Add more findings...]

### RigController Strategy
1. Detect new vertex via set difference
2. Call analyze_new_vertex(new_id) to infer parent
3. If parent found: inherit weights
4. If parent NOT found: log as UNKNOWN, requires manual review

### Conclusion for Phase 2
- ✓ CAN handle split with current APIs (if parent inference works)
- ? UNCLEAR: reliability of parent inference algorithm
```

#### Operations to Analyze:

1. **split(edge_id)** — Creates 1 new vertex in middle of edge
2. **collapse(edge_id)** — Merges 2 vertices, deletes 1
3. **connect(vertex_ids)** — Creates edge/face between vertices (no vertex creation)
4. **loop_insert(edge_loop)** — Inserts edge loop (multiple vertices, Phase 2 Topology work)

---

### 2.3 Unit Tests for RigController (Week 1)

**File:** `experiments/rigging-skinning-morphing/tests/test_rig_controller.py`

```python
import pytest
from rig_controller import RigController
from src.core import Mesh  # Import Core (read-only)

class TestRigController:
    
    def test_basic_initialization(self):
        """RigController initializes with empty rig."""
        mesh = Mesh()
        rig = RigController(mesh)
        assert len(rig.bones) == 0
        assert len(rig.skinning_weights) == 0
    
    def test_add_bone(self):
        """Can add bones to rig."""
        mesh = Mesh()
        rig = RigController(mesh)
        rig.add_bone("bone_1", "Jaw")
        assert "bone_1" in rig.bones
    
    def test_set_vertex_weight(self):
        """Can set skinning weights."""
        mesh = Mesh()
        v1 = mesh.vertices.create()  # Create test vertex
        rig = RigController(mesh)
        rig.add_bone("bone_1", "Jaw")
        rig.set_vertex_weight(v1.id, "bone_1", 1.0)
        assert rig.skinning_weights[v1.id][0] == ("bone_1", 1.0)
    
    def test_detect_topology_changes_empty(self):
        """detect_topology_changes works on unchanged mesh."""
        mesh = Mesh()
        rig = RigController(mesh)
        changes = rig.detect_topology_changes()
        assert len(changes["new_vertices"]) == 0
        assert len(changes["deleted_vertices"]) == 0
    
    def test_detect_new_vertex_after_split(self):
        """
        RESEARCH TEST: Can we detect new vertices after split()?
        """
        mesh = Mesh()
        # Create simple 2-triangle mesh with edge
        edge_id = ...  # Create test edge
        
        # Record baseline
        rig = RigController(mesh)
        
        # Perform split
        new_vertex_id = mesh.split(edge_id)
        
        # Detect change
        changes = rig.detect_topology_changes()
        assert new_vertex_id in changes["new_vertices"]
        
        # RESEARCH: Can we infer parent?
        parent_info = rig.analyze_new_vertex(new_vertex_id)
        print(f"New vertex {new_vertex_id} info: {parent_info}")
        # Document: What can we learn?
    
    def test_detect_deleted_vertex_after_collapse(self):
        """
        RESEARCH TEST: Can we detect deleted vertices after collapse()?
        """
        mesh = Mesh()
        # Create test edge
        edge_id = ...
        v1, v2 = mesh.edges[edge_id].vertices
        
        # Record baseline
        rig = RigController(mesh)
        rig.set_vertex_weight(v1, "bone_1", 1.0)
        
        # Perform collapse
        survivor_id = mesh.collapse(edge_id)
        
        # Detect change
        changes = rig.detect_topology_changes()
        # One vertex should be gone
        assert len(changes["deleted_vertices"]) == 1
        
        # RESEARCH: Which vertex was deleted?
        deleted = changes["deleted_vertices"][0]
        print(f"Deleted vertex: {deleted}")
        # Document findings
```

---

### 2.4 Research Documentation (Week 1.5)

**File:** `experiments/rigging-skinning-morphing/FINDINGS.md`

Template:

```markdown
# Phase 2 Findings: External Rigging on Stable Core

## Summary
After building RigController and testing with topology operations, here's what we learned.

## Finding 1: Vertex Change Detection ✓ WORKS
- Can detect new/deleted vertices via set difference of IDs ✓
- Works for split(), collapse(), and future operations ✓
- **Core API Used:** mesh.vertices (read-only)
- **No Core changes needed** ✓

## Finding 2: Parent Vertex Inference ❓ PARTIAL
- Split creates new vertex between two endpoints
- Can we infer which vertices are the endpoints?
- **Attempt 1:** mesh.edges[edge_id].vertices → YES ✓
- **But:** Only works if we track edge_id; vertex alone gives no hint
- **Workaround:** Assume new vertex is equidistant from closest old vertices
- **Limitation:** Fragile; fails for complex ops like loop insert

## Finding 3: Weight Inheritance Logic
- If we know parent vertex, inherit weight distribution ✓
- If parent unknown, must prompt user or use heuristic (e.g., uniform)
- **Proposed heuristic:** New vertex = average of all nearby vertices
- **Test result:** Works OK for split, risky for complex topology

## Finding 4: Morph Target Consistency
- Dead vertices (collapsed) detected and cleaned up ✓
- New vertices have no morph data (correct behavior) ✓
- **Issue:** If user adds morph AFTER split, morph doesn't apply to new vertex
- **Workaround:** User must re-add morph to include new geometry
- **Better solution:** Would need Core-side tracking of "when was this vertex created"

## Finding 5: Core API Gaps (Potential Future Requirements)

### Gap 1: Topology Operation Context
- **Problem:** After topology changes, we don't know WHAT operation caused it
- **Current workaround:** Infer from vertex changes (split → 1 new, collapse → 1 deleted)
- **Limitation:** Fails for complex ops (e.g., retopology, merging multiple edges)
- **Potential Core feature:** `Mesh.get_last_operation() → {"type": "split", "edge_id": 5, "new_vertex_id": 12}`

### Gap 2: Vertex Parent Tracking
- **Problem:** New vertex has no metadata about its parent
- **Current workaround:** Geometric heuristics (closest vertices)
- **Limitation:** Unreliable for non-uniform topology
- **Potential Core feature:** `vertex.created_from` attribute or `Mesh.get_vertex_lineage(vertex_id)`

### Gap 3: Morph Target Preservation
- **Problem:** New vertices don't inherit morph-target data
- **Current workaround:** User manually re-applies morphs
- **Limitation:** Tedious, error-prone
- **Potential Core feature:** Built-in morph-update-on-topology-change, or at least metadata about vertex creation time

### Gap 4: Change Notification Mechanism
- **Problem:** Must call detect_topology_changes() manually
- **Current workaround:** User calls after each operation
- **Limitation:** Easy to forget, no real-time sync
- **Potential Core feature:** Non-invasive observer pattern (e.g., event registry)

## Conclusions for Production Core Extension

### Definitely Needed (High Priority)
1. **Vertex parent tracking** — Too much guesswork without it

### Very Useful (Medium Priority)
2. **Topology operation context** — Makes RigController logic much cleaner
3. **Automatic morph-update hooks** — Reduces user error

### Nice-to-Have (Low Priority)
4. **Observer pattern** — Could be useful, but workarounds exist

### NOT Needed
- Anything that fundamentally changes the topology API

## Impact on WP 02 (for Later Discussion)
- Current Core is usable for basic rigging workflows (with manual updates)
- Proposed extensions would significantly improve developer experience
- No breaking changes required
```

---

## Success Criteria for Phase 2

✅ **Phase 2 is successful if:**
1. RigController prototype is functional (manages bones, weights, morphs)
2. Can perform split() and collapse() and update rig data appropriately
3. Comprehensive analysis of 4+ topology operations documented
4. Clear list of "Works Great," "Works with Workarounds," and "Core Gap" findings
5. Concrete recommendations for Phase 3 (viewport) and future Core extension
6. 37/37 Core tests still passing (zero Core modifications)

❌ **Fallback if issues:**
- Some topology ops are impossible to handle externally → Document why + propose Core feature
- Weight inference too unreliable → Simplify to "require manual weights for new vertices"
- Morph handling breaks → Document limitation + propose Core feature

---

## Deliverables

```
experiments/rigging-skinning-morphing/
├── src/
│   ├── rig_controller.py         ← Fully functional RigController
│   ├── bone.py                   ← Bone class (simple hierarchy)
│   └── deformation.py            ← Skinning math utilities
├── tests/
│   └── test_rig_controller.py    ← Unit tests for all functionality
├── TOPOLOGY_ANALYSIS.md          ← split/collapse/connect/loop analysis
├── FINDINGS.md                   ← Research conclusions & Core gap analysis
└── README.md                     ← Updated with Phase 2 results
```

---

## Timeline

- **Week 1:** RigController foundation + unit tests
- **Week 1–1.5:** Topology analysis + FINDINGS documentation
- **Deliverable:** Functional prototype + actionable research report

**Next:** Phase 3 (Viewport integration) starts only after Phase 2 findings are documented.

---

**Owner:** Manu  
**Constraint:** Zero `src/core/` modifications  
**Goal:** Discover what Core must provide, not build it yet
