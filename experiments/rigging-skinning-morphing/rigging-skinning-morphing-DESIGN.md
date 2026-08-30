# Design: Rigging & Skinning Architecture

## Architectural Decision: Option C (Hybrid)

**Recommendation: Implement Option C (Core-Aware Rigging with External Weights)**

This document presents three architectural options, analyzes trade-offs, and recommends Option C based on risk, scalability, and alignment with the project's "implement little, assume much" principle.

---

## Three Options Analyzed

### Option A: Skinning as First-Class Core Data

**Structure:**
```python
class Mesh:
    vertices = [Vertex(...), ...]
    edges = [Edge(...), ...]
    faces = [Face(...), ...]
    
    # NEW:
    bones = [Bone(...), ...]
    skinning_weights = {
        vertex_id: [(bone_id, weight), ...],
        ...
    }
    morph_targets = {
        "mouth_open": {vertex_id: (dx, dy, dz), ...},
        "jaw_drop": {...},
    }
```

**Integration with Topology:**
```python
def split(edge_id):
    new_vertex = create_new_vertex()
    
    # Topology update
    modify_faces(edge_id, new_vertex)
    
    # NEW: Skinning-aware logic
    parent_vertex = edge.vertices[0]
    new_vertex.skinning_weights = \
        inherit_and_blend_weights(parent_vertex.skinning_weights)
    
    # NEW: Morph-aware logic
    for morph_name in self.morph_targets:
        new_vertex.morph_offsets[morph_name] = \
            interpolate_morph_offset(parent_vertex, edge.vertices[1])
    
    return new_vertex
```

**Pros:**
- ✓ Unified state management (everything in Mesh)
- ✓ Undo/Redo automatically includes weights & morphs
- ✓ Topology ops have built-in deformation logic
- ✓ Theoretically cleaner architecture long-term
- ✓ Real integration point if system grows to animation

**Cons:**
- ✗ **High risk:** Modifying Core.Mesh changes Phase A–E boundary
- ✗ Must extend split/collapse/connect with deformation logic
- ✗ New fields (bones, weights, morphs) increase serialization complexity
- ✗ Testing burden: every topology test now has deformation variants
- ✗ If weight-merge logic is wrong, corrupts saved files
- ✗ Tight coupling: topology bugs affect deformation and vice versa

**Risk Assessment:** 🔴 **HIGH**
- Touches production code (src/core)
- Requires changes to 37 passing tests or new deformation test variants
- Serialization format changes break backward compatibility
- One mistake corrupts rig data

**Timeline:** 3–4 weeks to implement safely

---

### Option B: Skinning as Completely External System

**Structure:**
```python
# Core stays untouched:
class Mesh:
    vertices = [...]
    edges = [...]
    faces = [...]

# Separate system (outside src/core):
class RigController:
    mesh: Mesh
    bones = [Bone(...), ...]
    skinning_weights = {vertex_id: [(bone_id, weight), ...], ...}
    morph_targets = {name: {...}, ...}
    
    def deform_mesh(frame_or_bones_transform):
        """Apply rig to mesh, return deformed positions."""
        for vertex in self.mesh.vertices:
            vertex.deformed_position = \
                compute_skinned_position(vertex, self.bones, 
                                        self.skinning_weights)

# When topology changes, manually sync:
def on_mesh_split(mesh, edge_id, new_vertex_id):
    # RigController must be told about the change
    rig.skinning_weights[new_vertex_id] = ???  # What weight?
    # Problem: we don't know how to update without mesh knowledge!

def on_mesh_collapse(mesh, dead_vertex_id, survivor_vertex_id):
    if dead_vertex_id in rig.skinning_weights:
        del rig.skinning_weights[dead_vertex_id]
    # But survivor's weight: average? keep? User decides?
```

**Pros:**
- ✓ **Zero risk** to Core
- ✓ RigController can be developed/debugged independently
- ✓ Clean separation: topology ops never know about deformation
- ✓ Can iterate fast on skinning without Core regression tests

**Cons:**
- ✗ **Two sources of truth** (Mesh structure + RigController state)
- ✗ **Synchronization burden:** After every topology edit, must manually update weights
- ✗ No built-in strategy: what weight does split() produce? Average? Zero? User decides = bugs
- ✗ Undo/Redo must coordinate Mesh + RigController (complex)
- ✗ Orphaned weight entries (dead vertex IDs) pollute RigController
- ✗ Hard to serialize/load consistently (Mesh and Rig must match)

**Risk Assessment:** 🟡 **MEDIUM (but fragile)**
- Core is safe, but integration is error-prone
- Sync logic is easy to get wrong
- Future maintainers will struggle with state consistency

**Timeline:** 2 weeks, but high rework probability

---

### Option C: Hybrid (Recommended) ⭐

**Structure:**
```python
# Core (minimal extension):
class Mesh:
    vertices = [...]
    edges = [...]
    faces = [...]
    
    # NEW (lightweight):
    bones = [Bone(...), ...]  # Just hierarchy, no animation data
    
    # Callbacks (new infrastructure):
    def on_vertex_created(new_vertex_id, parent_vertex_id, context="split"):
        """Notify subscribers when topology creates a vertex."""
        for listener in self.topology_listeners:
            listener.on_vertex_created(new_vertex_id, parent_vertex_id, context)
    
    def on_vertex_deleted(vertex_id):
        """Notify subscribers before deleting a vertex."""
        for listener in self.topology_listeners:
            listener.on_vertex_deleted(vertex_id)

# Separate system (experiments/ for now):
class RigController:
    mesh: Mesh  # Reference to the Mesh
    bones: Link to mesh.bones  # Shares bone hierarchy
    
    skinning_weights = {vertex_id: [(bone_id, weight), ...], ...}
    morph_targets = {name: {vertex_id: (dx, dy, dz), ...}, ...}
    
    def __init__(self, mesh):
        self.mesh = mesh
        self.bones = mesh.bones  # Same reference
        self.mesh.register_topology_listener(self)
    
    # Implements topology listener interface:
    def on_vertex_created(self, new_vertex_id, parent_vertex_id, context):
        """When split() creates a vertex, inherit parent's weights."""
        if parent_vertex_id in self.skinning_weights:
            # Inherit parent's weight distribution
            self.skinning_weights[new_vertex_id] = \
                self.skinning_weights[parent_vertex_id].copy()
            
            # Same for morph offsets
            for morph_name in self.morph_targets:
                if parent_vertex_id in self.morph_targets[morph_name]:
                    self.morph_targets[morph_name][new_vertex_id] = \
                        self.morph_targets[morph_name][parent_vertex_id]
    
    def on_vertex_deleted(self, vertex_id):
        """When collapse() deletes a vertex, clean up weights."""
        if vertex_id in self.skinning_weights:
            del self.skinning_weights[vertex_id]
        
        for morph_name in self.morph_targets:
            if vertex_id in self.morph_targets[morph_name]:
                del self.morph_targets[morph_name][vertex_id]
```

**Integration Points:**
1. **Core.Mesh gets lightweight extension:**
   - Add `bones: [Bone(...), ...]` field
   - Add `topology_listeners: []` infrastructure
   - Call `on_vertex_created()` / `on_vertex_deleted()` in split/collapse

2. **RigController stays external** (experiments/, later moves to src/)
   - Implements topology listener interface
   - Auto-updates weights on topology changes
   - Handles morph-target consistency

**Pros:**
- ✓ **Low risk to Core:** Only adds callback infrastructure (proven pattern)
- ✓ **Clear coupling:** Mesh knows it's observable, but not what observers do
- ✓ **Auto-sync:** RigController auto-updates on topology changes
- ✓ **Scalable:** Can add more listeners later (animation, constraints, etc.)
- ✓ **Testable:** Topology tests unchanged; rig tests separate
- ✓ **Practical:** Answers the "what weight for new vertex" question
- ✓ **Future-proof:** Bones in Core means animation system can reuse same hierarchy

**Cons:**
- ◐ Slightly more complex than pure Option B (but much safer)
- ◐ Requires Core to know about topology listeners (minor design change)

**Risk Assessment:** 🟢 **LOW**
- Core change is minimal and non-invasive (observer pattern)
- Can be reverted easily if needed
- RigController failures don't affect Mesh integrity
- Backward compatible (old files still load, just without rig)

**Timeline:** 2.5 weeks (1 week Core extension, 1.5 weeks RigController)

---

## Comparison Matrix

| Aspect | Option A | Option B | **Option C** |
|--------|----------|----------|-------------|
| **Risk to Core** | 🔴 High | 🟢 None | 🟢 Low |
| **Implementation Complexity** | High | Medium | Medium |
| **Auto-sync on Topology** | ✓ Built-in | ✗ Manual | ✓ Listener-based |
| **Scalability** | ✓ Unified | ✗ Fragile | ✓ Extensible |
| **Backward Compatibility** | ✗ Format change | ✓ Yes | ✓ Yes |
| **Undo/Redo** | ✓ Unified | ✗ Complex | ✓ Via callbacks |
| **Testing Burden** | Very High | Medium | Low |
| **Time to MVP** | 3–4 weeks | 2 weeks | 2.5 weeks |
| **Ready for Production** | Yes (later) | No (tech debt) | Yes (after validation) |

---

## Design Rationale: Why Option C

### 1. Aligns with "Implement Little, Assume Much"
- Core gets minimal extension (callback framework)
- RigController is pragmatic & disposable initially
- Both can evolve independently

### 2. Risk Management
- Low chance of breaking Phase A–E
- Easy to revert if architecture wrong
- Clear failure modes (listener doesn't update → weights get stale, user sees it)

### 3. Practical for Your Use Case
- Answers: "When I split() a vertex, what weight does it get?" → **Inherit from parent**
- Answers: "When I collapse() two vertices, what happens?" → **Clean up dead ID**
- No guessing; observer pattern handles it

### 4. Scales to Future Requirements
- Bones in Core means animation system later can reference same hierarchy
- Listeners enable: constraints, physics, animation, streaming
- Not just for rigging; pattern works for anything dependent on topology

### 5. Testability
- Mesh tests unchanged (37 tests stay green)
- Rig tests separate (no topology variants needed)
- Can test listener independently

---

## Implementation Strategy for Option C

### Phase 1: Core Extension (Minimal)
**File: `src/core/mesh.py`**
```python
class Mesh:
    def __init__(self):
        # existing
        self.vertices = [...]
        self.edges = [...]
        self.faces = [...]
        
        # NEW:
        self.bones = []
        self.topology_listeners = []
    
    def register_topology_listener(self, listener):
        """Register an object to be notified of topology changes."""
        self.topology_listeners.append(listener)
    
    # In split():
    def split(self, edge_id):
        new_vertex = self.vertices.create_new()
        # ... topology logic ...
        self.notify_vertex_created(new_vertex.id, parent_vertex.id, "split")
        return new_vertex
    
    # In collapse():
    def collapse(self, edge_id):
        dead_vertex, survivor = self.edges[edge_id].vertices
        # ... topology logic ...
        self.notify_vertex_deleted(dead_vertex.id)
        return survivor
    
    def notify_vertex_created(self, new_id, parent_id, context):
        for listener in self.topology_listeners:
            listener.on_vertex_created(new_id, parent_id, context)
    
    def notify_vertex_deleted(self, vertex_id):
        for listener in self.topology_listeners:
            listener.on_vertex_deleted(vertex_id)
```

**Tests:** No new tests needed for Mesh; callback firing is implicit in existing topology tests.

### Phase 2: RigController (Experiment, External)
**File: `experiments/rigging-skinning-morphing/src/rig_controller.py`**
```python
class RigController:
    def __init__(self, mesh):
        self.mesh = mesh
        self.bones = mesh.bones
        self.skinning_weights = {}
        self.morph_targets = {}
        self.mesh.register_topology_listener(self)
    
    def add_bone(self, name, parent=None):
        bone = Bone(name, parent)
        self.bones.append(bone)
        return bone
    
    def set_vertex_weight(self, vertex_id, bone, weight):
        if vertex_id not in self.skinning_weights:
            self.skinning_weights[vertex_id] = []
        self.skinning_weights[vertex_id].append((bone, weight))
    
    # Topology listener implementation:
    def on_vertex_created(self, new_vertex_id, parent_vertex_id, context):
        if parent_vertex_id in self.skinning_weights:
            self.skinning_weights[new_vertex_id] = \
                [(bone, weight) for bone, weight in 
                 self.skinning_weights[parent_vertex_id]]
            # Same for morphs
            ...
    
    def on_vertex_deleted(self, vertex_id):
        self.skinning_weights.pop(vertex_id, None)
        # Clean morphs
        ...
    
    def deform_mesh(self, bone_transforms):
        """Apply rig transforms, return deformed vertex positions."""
        deformed = {}
        for vertex in self.mesh.vertices:
            deformed[vertex.id] = self.compute_skinned_position(
                vertex, self.skinning_weights, self.bones, bone_transforms
            )
        return deformed
```

---

## Phase 3: Viewport Integration

**File: `experiments/rigging-skinning-morphing/src/deformation_viewport.py`**
- Render rigged mesh with bone skeleton visible
- Test morphs with keyboard controls
- Test topology edits (loop insert) + observe weight consistency

---

## Transition Path to Production

1. **Phase 2 validation (experiments/):** Ensure low-poly head use case works
2. **Move to src/core:** Once validated, move RigController to `src/core/rigging/`
3. **Extend tests:** Add rig-aware topology tests to the main test suite
4. **Serialize:** Add rigging data to mesh export format (versioned)
5. **Animation integration:** Wire bone hierarchy to animation system (Phase F+)

---

## Decision Checkpoints

**Approve Option C if:**
- ✓ Core extension (observer pattern) is acceptable risk
- ✓ Inherited weights (for new vertices) is the right default
- ✓ External RigController can be tested independently

**Fallback if issues arise:**
- Core extension proves problematic → Strip bones/listeners, move to Option B
- Weight inheritance strategy wrong → Adjust in RigController, no Core change needed

---

## Next Steps

1. ✓ **RESEARCH.md** — Core architecture analyzed
2. ✓ **DESIGN.md** — Three options presented, Option C recommended
3. → **AD-005-RIGGING-INTEGRATION.md** — Formalize the decision
4. → **Phase 2 (Prototype)** — Implement Option C

---

**Document Status:** Design Phase (Complete)  
**Recommendation:** **Option C (Hybrid) — Proceed to Architecture Decision**  
**Risk Level:** 🟢 LOW  
**Timeline to MVP:** 2.5 weeks  
**Author:** Claude (Technical Architecture Analysis)  
**Approval by:** Manu (Project Owner/PM) — TBD
