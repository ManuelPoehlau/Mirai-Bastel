# Phase 2b: RigController Foundation

**Status:** ✓ COMPLETE  
**Date:** August 2026  
**Base:** CORE_API_AUDIT.md findings  

---

## Overview

RigController is an **external rigging, skinning, and morph-target system** that:
- Operates **independently** from Core.Mesh
- Uses **ONLY read-only public Core APIs** (no observers, no modifications)
- Detects topology changes via **snapshot comparison**
- Manages **bones, weights, morphs** as separate data structures
- Computes **deformation on-demand** (no persistent mesh state)

**Key Design:** RigController does NOT modify the mesh. It queries the mesh, stores its own rig data, and computes deformed positions when needed.

---

## V1 Scope (What's Implemented)

### ✓ Bones
- Hierarchical bone structure (parent-child relationships)
- Simple named bones (e.g., "Jaw", "Skull", "Neck")
- Query: Get bone, get chain to root

### ✓ Skinning (Linear Blend Skinning)
- Per-vertex weight list: [(bone_id, weight), ...]
- Set/get/clear weights
- Weight inheritance when new vertices created
- Deformation via LBS formula: `sum(w[i] * T[i] * position) / sum(w[i])`

### ✓ Morph Targets
- Named morph targets (e.g., "mouth_open", "jaw_drop")
- Per-morph, per-vertex offsets: (dx, dy, dz)
- Active morph blending (blend_weight per morph)
- Result = base_position + sum(morph_weight[i] * offset[i])

### ✓ Topology Change Detection
- Snapshot-based observation (before/after state)
- Detects: new_vertices, deleted_vertices, new_edges, deleted_edges, new_faces, deleted_faces
- **Observational only:** No operation-type inference (ambiguous without Core context)

### ✓ Topology Queries (Core API)
- `query_vertex_topology()` → connected edges, adjacent vertices, connected faces
- `query_edge_topology()` → endpoint vertices, connected faces
- All using public Core APIs: `vertex_edges()`, `edge_vertices()`, `edge_faces()`

### ✓ Deformation Computation
- `deform_mesh()` → apply all vertices (skinning + morphs)
- `get_deformed_position()` → single vertex
- Uses `bone_transforms: dict[BoneId, Transform]` (caller provides poses)

---

## Deferred (Phase 3+)

- ❌ Animation/Pose data (keyframes, timeline)
- ❌ Inverse bind pose calculation
- ❌ Serialization of rig data
- ❌ Undo/Redo integration
- ❌ Viewport integration
- ❌ Weight painting UI
- ❌ Dual-Quaternion Skinning
- ❌ Advanced blend modes (add, multiply, overlay)

---

## Module Structure

### bone.py
```python
class Bone:
    bone_id: int
    name: str
    parent: Optional[Bone]
    children: list[Bone]
    
    # Methods
    add_child()
    get_root()
    get_chain_to_root()
```

Minimal bone hierarchy. Deferred: transforms, IK, constraints.

### deformation.py
```python
class Transform:
    translation: Position
    rotation_matrix: list[list[float]]
    apply(position) -> Position
    
def linear_blend_skinning(...) -> Position
def apply_morph_offset(...) -> Position
def blend_morphs(...) -> Position
```

Math utilities for LBS and morph blending.

### rig_controller.py
```python
class RigController:
    # Bones
    add_bone(name, parent_id) -> BoneId
    get_bone(bone_id) -> Bone
    
    # Weights
    set_vertex_weight(vertex_id, bone_id, weight)
    get_vertex_weights(vertex_id) -> [(bone_id, weight), ...]
    inherit_weights(source, target)
    
    # Morphs
    add_morph_target(name)
    set_morph_offset(morph_name, vertex_id, offset)
    set_morph_active(morph_name, blend_weight)
    
    # Topology
    take_topology_snapshot(label) -> TopologySnapshot
    detect_topology_changes() -> TopologyChanges
    query_vertex_topology(vertex_id) -> dict
    query_edge_topology(edge_id) -> dict
    
    # Events
    handle_vertex_deletion(vertex_id)
    handle_new_vertex(vertex_id, parent_id=None)
    
    # Deformation
    deform_mesh(bone_transforms) -> dict[vertex_id, position]
    get_deformed_position(vertex_id, bone_transforms) -> position
```

Central controller managing all rig aspects.

---

## Core API Usage (from CORE_API_AUDIT.md)

**Read-Only Queries Used:**
- `mesh.all_vertex_ids()` → list[VertexId]
- `mesh.all_edge_ids()` → list[EdgeId]
- `mesh.all_face_ids()` → list[FaceId]
- `mesh.vertex_position(vertex_id)` → Position
- `mesh.vertex_edges(vertex_id)` → list[EdgeId]
- `mesh.edge_vertices(edge_id)` → (VertexId, VertexId)
- `mesh.edge_faces(edge_id)` → list[FaceId]
- `mesh.is_valid_vertex(vertex_id)` → bool

**Never Used:**
- ❌ Mesh modification APIs (split, collapse, connect, add_vertex, etc.)
- ❌ Listeners/Observers (not in V1 Core anyway)
- ❌ Direct access to internal `_vertices`, `_edges`, `_faces`

---

## Design Decisions (from Phase 1 Research)

### Decision 1: External, Not Integrated
**Rationale:** Follows Topology Experiment pattern. No Core modifications. Allows research without blocking other work.

### Decision 2: Snapshot-Based Change Detection
**Rationale:** Core doesn't provide operation context. Snapshots are reliable and observable.

**Trade-off:** Can't distinguish split() from collapse() post-hoc without geometric heuristics. Document as limitation.

### Decision 3: No Automatic Sync
**Rationale:** Automatic sync would require observers or Core extension. Phase 2 avoids this.

**Implication:** Caller must explicitly handle topology changes via `detect_topology_changes()` + event handlers.

### Decision 4: On-Demand Deformation
**Rationale:** Don't store deformed mesh. Caller provides poses (bone_transforms). Compute deformations on-demand.

**Benefit:** Lightweight, supports multiple deformations for same mesh (e.g., different poses, morphs).

---

## Usage Example (Pseudocode)

```python
from rig_controller import RigController
from deformation import Transform

# Create rig
rig = RigController(mesh)

# Build bone hierarchy
skull_id = rig.add_bone("Skull")
jaw_id = rig.add_bone("Jaw", parent_id=skull_id)
neck_id = rig.add_bone("Neck", parent_id=skull_id)

# Weight some vertices
for vertex_id in range(10):
    rig.set_vertex_weight(vertex_id, skull_id, 0.5)
    rig.set_vertex_weight(vertex_id, jaw_id, 0.5)

# Create morph target
rig.add_morph_target("mouth_open")
rig.set_morph_offset("mouth_open", vertex_5, (0.0, 0.1, 0.0))
rig.set_morph_offset("mouth_open", vertex_6, (0.0, 0.1, 0.0))

# Snapshot before topology operation
rig.take_topology_snapshot("before_split")

# [Caller performs topology operation on mesh...]
# mesh.split_edge(some_edge)

# Detect changes
changes = rig.detect_topology_changes()
if changes.new_vertices:
    new_v = changes.new_vertices[0]
    # Try to inherit from existing vertex (heuristic)
    rig.handle_new_vertex(new_v, parent_vertex_id=vertex_5)

# Pose bones
bone_transforms = {
    skull_id: Transform(translation=(0, 0, 0)),
    jaw_id: Transform(translation=(0, -0.05, 0)),
    neck_id: Transform(translation=(0, 0, 0)),
}

# Activate morph
rig.set_morph_active("mouth_open", 0.5)

# Compute deformation
deformed = rig.deform_mesh(bone_transforms)
# deformed = {vertex_0: (x0, y0, z0), vertex_1: (x1, y1, z1), ...}

# Apply to mesh (caller's responsibility)
for vid, pos in deformed.items():
    mesh.set_vertex_position(vid, pos)  # Display only; doesn't persist rig
```

---

## Phase 2b → Phase 2c Transition

**What Phase 2b provides:**
- ✓ Functional RigController
- ✓ Bones, weights, morphs working
- ✓ Topology change detection
- ✓ Core API query patterns established

**What Phase 2c does:**
- Tests to verify each component
- Systematic topology operation investigation
- Document findings (split, collapse, connect behavior)
- Identify remaining Core API questions
- Fill FINDINGS.md

---

## Testing Strategy (Phase 2c)

1. **Unit Tests:** Each RigController method
   - add_bone, set_weight, add_morph, etc.

2. **Integration Tests:** Topology operations
   - Setup rig
   - Perform split/collapse/connect
   - Verify change detection
   - Verify weight/morph handling

3. **Research Tests:** Deep topology investigation
   - "Can we identify parent vertex after split()?" (geometric heuristic test)
   - "Can we determine which vertex survived collapse()?" (query via edge_vertices)
   - "Can we trace which faces were split by connect()?" (boundary comparison)

---

## Known Limitations (Document for Phase 2c FINDINGS)

1. **No Parent Tracking for split():**
   - New vertex has no metadata about which edge it came from
   - Workaround: Geometric heuristic (check which edge midpoint matches new position)
   - Limitation: Fails if two edges share same midpoint

2. **No Operation Logging:**
   - After topology change, can't ask "was this split or collapse?"
   - Workaround: Track changes yourself via snapshots
   - Limitation: Ambiguous in edge cases

3. **No Automatic Edge Cleanup:**
   - `remove_face()` leaves orphaned edges
   - Limitation: Stale edges may exist

4. **Vertex Edges is O(n):**
   - `vertex_edges()` scans all edges
   - Not a limitation (still works), just slow for large meshes

---

## Next: Phase 2c

Ready to test and investigate topology operations systematically.

**Date:** August 2026  
**Owner:** Manu  
**Status:** ✓ Implementation Complete → Testing Phase
