# Phase 2: RigController Prototype — Core-First Research Methodology

**Objective:** Build a functional external RigController through systematic investigation of what the Core API actually provides.

**Methodology:** API Audit → Document → Design → Implement → Test

**Constraint:** Zero modifications to `src/core/`. Use only existing public Core APIs.

---

## Phase 2 Structure: Three Sub-Phases

### Phase 2a: Core API Audit (Week 1)

**Goal:** Understand the actual state of public Core APIs before designing RigController.

**Deliverable:** `CORE_API_AUDIT.md` — Comprehensive investigation of Mesh/Vertex/Edge/Face APIs.

#### 2a.1 Investigate Core Mesh Class

**File to examine:** `src/core/mesh.py` (and related files)

```markdown
# Core API Audit: Mesh Class

## Query: Mesh.vertices
- **Actual Type:** [investigate]
- **Access Method:** mesh.vertices or mesh.get_vertices()?
- **Returns:** [list/dict/iterable?]
- **ID Access:** How to get vertex ID? vertex.id or other?
- **Iteration:** Can we iterate all vertices? YES/NO
- **Lookup by ID:** mesh.vertices.get(id)? mesh.get_vertex(id)? Other?

## Query: Mesh.edges
- **Actual Type:** [...]
- **Returns:** [...]
- **Edge Structure:** What does an edge contain?
  - edge.vertices → [v1, v2]?
  - edge.id → unique ID?
  - Anything else?

## Query: Mesh.faces
- [similar investigation]

## Method: split(edge_id)
- **Signature:** def split(self, edge_id: ?) -> ?
- **Parameters:** edge_id type? Other params?
- **Returns:** New vertex ID? Vertex object? Both?
- **Behavior:** 
  - Creates exactly 1 new vertex? YES/NO
  - Position calculated how? (midpoint? caller specifies?)
  - Edge endpoints preserved? Faces updated?
  - IDs: Are new vertex/edge IDs generated sequentially? Random? Other?

## Method: collapse(edge_id)
- **Signature:** def collapse(self, edge_id: ?) -> ?
- **Returns:** Survivor vertex ID? Position preference?
- **Behavior:**
  - Which vertex dies, which survives? Can Core tell us? Or user specifies?
  - New vertex position: midpoint? First endpoint? Last survivor value?
  - Face integrity after collapse?
  - ID behavior: Dead ID truly deleted, or marked "orphaned"?

## Method: connect(vertices)
- **Signature:** def connect(self, ...?) -> ?
- **Parameters:** Exactly how are vertices specified?
- **Returns:** New edge? New face?
- **Behavior:**
  - Does it create edge only, or edge + face?
  - Existing geometry modified or extended?
  - ID generation for new elements?

## Available Query Methods
- List ALL public methods on Mesh
- List ALL public methods on Vertex
- List ALL public methods on Edge
- List ALL public methods on Face
- Document return types for each
```

#### 2a.2 Investigate ID Behavior

```markdown
# ID Behavior Investigation

## Question: Vertex ID Continuity
- After split(), old vertex IDs unchanged? YES/NO
- New vertex ID type: int? string? custom class?
- ID uniqueness: guaranteed within session? YES/NO
- ID reuse: After vertex deleted, can new vertex reuse that ID? YES/NO
- How to prove this? [design test]

## Question: Edge/Face ID Behavior
- Same as vertices? [investigate]

## Question: Topology Snapshot Reliability
- Can we capture all vertex IDs at moment T? YES/NO
- Can we reliably compare two snapshots? YES/NO
- What about transient states during multi-step operations?
```

#### 2a.3 Investigate Topology Query Capabilities

```markdown
# Topology Query Capabilities

## Question: Given a vertex ID, can we find:
- Connected edges? Method: [investigate]
  - mesh.get_edges_for_vertex(v_id)? Other?
  - Returns: edge IDs? Edge objects?
  
- Connected faces? Method: [investigate]

- 1-ring neighbors (adjacent vertices)? Method: [investigate]

## Question: Given an edge ID, can we find:
- Endpoint vertices? Method: edge.vertices? Other?
  - Returns: [v1, v2] reliably ordered? Or unordered?
  
- Connected faces? Method: [investigate]

## Question: Given a face ID, can we find:
- Boundary edges?
- Boundary vertices?
- Winding order?

## Question: After an operation, can we:
- Query which edges changed? NO built-in, must infer from snapshots
- Query operation history? NO built-in
- Determine operation type from before/after state? [test empirically]
```

#### 2a.4 Document Findings

**Output file:** `CORE_API_AUDIT.md`

```markdown
# Core API Audit — Actual Findings

## Mesh Class APIs

### vertices
- Type: [actual]
- Access: mesh.vertices or mesh.get_vertices() or other
- Iteration: [works/doesn't work]
- Lookup: [method to get vertex by ID]
- Example:
  ```python
  for v in mesh.vertices:
      print(v.id, v.position)
  ```

### edges
- [similar structure]

### split(edge_id)
- Signature: [actual]
- Example:
  ```python
  edge = mesh.edges[edge_id]  # or mesh.get_edge()?
  new_v_id = mesh.split(edge_id)
  print(f"New vertex: {new_v_id}")
  print(f"Type: {type(new_v_id)}")
  ```
- Behavior: [actual observed]

### collapse(edge_id)
- Signature: [actual]
- Returns: [what exactly]
- Test:
  ```python
  survivor = mesh.collapse(edge_id)
  print(f"Survivor: {survivor}")
  ```

### connect(...)
- Signature: [actual]
- Parameters: [how exactly to call it]
- Returns: [actual return values]

## Topology Query Capabilities

### Finding 1: Get edges for vertex
- Method: [actual or "NOT AVAILABLE"]
- Example: [or "Not possible with public API"]

### Finding 2: Get adjacent vertices
- Method: [actual or not available]

### Finding 3: Determine operation type from state change
- Method: [findings]
- Example: "After comparing before/after snapshots: [what can we determine for sure]"

## Core API Gaps Identified

### Gap 1: [observed limitation]
- What we need: [...]
- Workaround: [if any]

### Gap 2: [...]

## Verified Capabilities

### ✓ Capability 1: Vertex creation detection
- Method: ID set difference
- Reliability: HIGH/MEDIUM/LOW
- Evidence: [test results]

### ✓ Capability 2: [...]

## Open Questions for RigController Design

1. [Question based on audit findings]
2. [...]
```

---

### Phase 2b: RigController Foundation (Week 1)

**Based on:** Actual Core API findings from Phase 2a

```python
# EXAMPLE (pseudocode, adjust to actual Core API):

class RigController:
    def __init__(self, mesh):
        self.mesh = mesh
        self.bones = {}
        self.skinning_weights = {}
        self.morph_targets = {}
    
    def take_topology_snapshot(self):
        """Snapshot using actual Core API from audit."""
        # Use whatever Core API exists for iterating vertices
        current_v = frozenset(v.id for v in self.mesh.vertices)  # Actual syntax TBD
        return {"vertices": current_v, ...}
    
    def query_vertex_topology(self, vertex_id):
        """Investigate using actual Core API."""
        # If Core provides: mesh.get_edges_for_vertex() → use it
        # If not: "NOT AVAILABLE via public API"
        
        findings = {}
        # Try actual methods discovered in audit
        return findings
```

---

### Phase 2c: Research Tests & Topology Operations (Week 1–1.5)

**File:** `tests/test_core_api_and_rig_controller.py`

```python
import pytest
from rig_controller import RigController
from src.core import Mesh

class TestCoreAPIBehavior:
    """
    First: Verify Core API audit findings.
    Then: Design RigController based on verified API.
    """
    
    def test_split_returns_new_vertex_id(self):
        """Verify split() actual behavior."""
        mesh = Mesh()
        # Setup edge
        edge_id = ...  # Using actual Core API
        
        # Call split
        result = mesh.split(edge_id)
        
        # Verify: What does split() actually return?
        print(f"split() returned: {result} (type: {type(result)})")
        # Document actual behavior
    
    def test_collapse_returns_survivor(self):
        """Verify collapse() actual behavior."""
        # Based on audit findings
        mesh = Mesh()
        survivor = mesh.collapse(edge_id)
        print(f"collapse() returned: {survivor}")
        # Question: Is this the survivor's ID? Object? Something else?
    
    def test_connect_behavior(self):
        """Investigate connect() actual behavior."""
        # Focus on Edge/Face creation and detection
        mesh = Mesh()
        
        before = {
            "edges": frozenset(e.id for e in mesh.edges),
            "faces": frozenset(f.id for f in mesh.faces),
        }
        
        result = mesh.connect(...)  # Using actual signature from audit
        
        after = {
            "edges": frozenset(e.id for e in mesh.edges),
            "faces": frozenset(f.id for f in mesh.faces),
        }
        
        print(f"connect() result: {result}")
        print(f"New edges: {after['edges'] - before['edges']}")
        print(f"New faces: {after['faces'] - before['faces']}")
        
        # Research findings from observation
```

---

## Critical Research Focus: connect()

**Special attention for `connect(vertex_ids, ...)`:**

```python
def test_connect_edge_and_face_creation(self):
    """
    RESEARCH: Does connect() create edge, face, or both?
    Can we definitively identify which elements changed?
    """
    mesh = Mesh()
    
    # Setup
    v1, v2 = [mesh.vertices[i] for i in [0, 1]]
    
    # Before snapshot
    before_edges = set(e.id for e in mesh.edges)
    before_faces = set(f.id for f in mesh.faces)
    
    # Execute connect
    result = mesh.connect(v1, v2)  # Actual signature TBD
    
    # After snapshot
    after_edges = set(e.id for e in mesh.edges)
    after_faces = set(f.id for f in mesh.faces)
    
    # Findings
    new_edges = after_edges - before_edges
    new_faces = after_faces - before_faces
    
    print(f"\nconnect() Investigation:")
    print(f"  Returned: {result} (type: {type(result)})")
    print(f"  New edges: {new_edges}")
    print(f"  New faces: {new_faces}")
    
    # Research question:
    # - Can we reliably map "result" to new elements?
    # - If create both edge AND face: can we identify each?
    # - What if edge already exists? Does connect() handle that?
    
    # Document observations
```

---

## Deliverables

```
experiments/rigging-skinning-morphing/
├── CORE_API_AUDIT.md                 ← Phase 2a: Actual API findings
│                                      (becomes reference for all later work)
├── src/
│   ├── rig_controller.py             ← Phase 2b: Based on audit findings
│   ├── bone.py
│   └── deformation.py
├── tests/
│   └── test_core_api_and_rig_controller.py  ← Phase 2c: Verification + Research
├── TOPOLOGY_ANALYSIS.md              ← Updated with actual Core API methods
├── FINDINGS.md                       ← Empty template, fills during testing
└── README.md                         ← Updated with audit results
```

---

## Timeline

- **Week 1 (Days 1–3):** Phase 2a Core API Audit
  - Read src/core/ files
  - Document actual signatures, returns, behavior
  - Create CORE_API_AUDIT.md reference
  
- **Week 1 (Days 4–5):** Phase 2b RigController Foundation
  - Build on top of verified API findings
  - No guessing; use only what audit confirmed
  
- **Week 1–1.5:** Phase 2c Research Tests & Topology Investigation
  - Verify audit findings with tests
  - Investigate connect() edge/face behavior
  - Fill FINDINGS.md with actual results

---

## Success Criteria

✅ **Phase 2 is successful if:**
1. CORE_API_AUDIT.md is complete and accurate
2. RigController implementation uses only verified API
3. All topology operations (split/collapse/connect) investigated
4. FINDINGS.md filled with actual observations (no predictions)
5. Core API gaps identified with concrete evidence
6. connect() behavior fully understood (edge/face creation, identification)
7. Zero Core modifications
8. 37/37 existing tests passing

---

## Key Principle

**"The audit IS part of the research."**

Understanding what the Core API actually provides is not preliminary work—it's the foundation of the entire experiment. Every finding here shapes RigController design.

---

**Owner:** Manu  
**Constraint:** Zero `src/core/` modifications  
**Starting Point:** Phase 2a — Core API Audit
