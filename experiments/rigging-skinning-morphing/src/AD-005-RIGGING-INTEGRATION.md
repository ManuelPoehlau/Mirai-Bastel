# AD-005: Rigging & Skinning Integration Architecture

**Status:** DECIDED ✓  
**Date:** August 2026  
**Owner:** Manu (Project Owner)  
**Architect:** Claude  
**Scope:** Experiment: rigging-skinning-morphing  

---

## Problem Statement

How must Rigging, Skinning Weights, and Morph-Targets be represented in the Mirai-Bastel system such that:

1. They survive topological mesh editing (split/collapse/connect)
2. Topology operations can meaningfully auto-update deformation data (not just destroy it)
3. Core.Mesh remains stable (Phase A–E regression-free)
4. The system can later scale to animation & constraint systems

**Use Case:** Low-poly character head model (neck, skull, jaw rigged + skinned + morphs), then edit topology (e.g., loop insert) without losing rig integrity.

---

## Decision: Option C — Hybrid (Core-Aware Rigging with External Weights)

### Chosen Architecture

**Core.Mesh (Minimal Extension):**
- Add `bones: [Bone(...), ...]` — Bone hierarchy
- Add `topology_listeners: []` — Observer pattern infrastructure
- Modify split/collapse/connect to call `on_vertex_created()` / `on_vertex_deleted()` callbacks

**RigController (External, experiments/rigging-skinning-morphing/):**
- Inherits reference to `mesh.bones` (same hierarchy)
- Owns `skinning_weights: {vertex_id: [(bone_id, weight), ...], ...}`
- Owns `morph_targets: {name: {vertex_id: (dx, dy, dz), ...}, ...}`
- Implements topology listener interface
- Auto-updates weights/morphs when topology changes (split → inherit parent weight, collapse → clean up dead ID)

### Why Option C (Not A or B)

| Criterion | Option A | Option B | **Option C** |
|-----------|----------|----------|-------------|
| Risk to Phase A–E | 🔴 High | 🟢 None | 🟢 Low |
| Auto-sync | ✓ Built-in | ✗ Manual | ✓ Listener-based |
| Scalability | ✓ Unified | ✗ Fragile | ✓ Extensible |
| Testability | ✗ Complex | ◐ Medium | ✓ Clean |
| Time to MVP | 3–4 weeks | 2 weeks | 2.5 weeks |

**Rationale:**
- **Option A** (Skinning in Core): Highest potential for unified design long-term, but risks Core regression and is too ambitious for an experiment running in parallel to WP 02
- **Option B** (External Only): Safe but creates two sources of truth; sync bugs likely; no built-in strategy for weight inheritance
- **Option C** (Hybrid): Balances safety + practicality. Core gets minimal, non-invasive extension (observer pattern — proven design). RigController handles deformation logic independently. Clear auto-sync strategy (inherit weights on vertex creation, clean on deletion). Scales to future systems.

---

## Architecture

### 1. Core.Mesh Extension

**Minimal changes to `src/core/mesh.py`:**

```python
class Mesh:
    def __init__(self):
        # Existing
        self.vertices = [...]
        self.edges = [...]
        self.faces = [...]
        
        # NEW (lightweight):
        self.bones = []                    # Bone hierarchy (see Bone class below)
        self.topology_listeners = []       # Observer pattern
    
    def register_topology_listener(self, listener):
        """Register an object to be notified of topology mutations."""
        self.topology_listeners.append(listener)
    
    def split(self, edge_id):
        parent_vertex = ... # one end of edge
        new_vertex = self.vertices.create_new()
        # ... topology mutation logic (unchanged) ...
        self._notify_vertex_created(new_vertex.id, parent_vertex.id, "split")
        return new_vertex
    
    def collapse(self, edge_id):
        dead_vertex, survivor = self.edges[edge_id].vertices
        # ... topology mutation logic (unchanged) ...
        self._notify_vertex_deleted(dead_vertex.id)
        return survivor
    
    def connect(self, vertices):
        # ... (unchanged; doesn't create/delete vertices) ...
        pass
    
    def _notify_vertex_created(self, new_id, parent_id, context):
        for listener in self.topology_listeners:
            listener.on_vertex_created(new_id, parent_id, context)
    
    def _notify_vertex_deleted(self, vertex_id):
        for listener in self.topology_listeners:
            listener.on_vertex_deleted(vertex_id)


class Bone:
    """Simple bone hierarchy node."""
    def __init__(self, name, parent=None):
        self.id = unique_id()
        self.name = name
        self.parent = parent  # Reference to parent Bone or None
        self.children = []
        if parent:
            parent.children.append(self)
    
    # Future: transform data (position, rotation, scale) added in animation phase
```

**Impact on Phase A–E:**
- No changes to existing topology logic (split/collapse/connect remain functionally identical)
- Callback notifications are **non-blocking** (if no listeners, no overhead)
- Serialization: `bones` field is optional in old files (backward compatible)
- Tests: All 37 Phase A–E tests remain unchanged

### 2. RigController (External)

**Location:** `experiments/rigging-skinning-morphing/src/rig_controller.py` (initially)

```python
class RigController:
    """Manages rigging, skinning, and morph-targets for a Mesh."""
    
    def __init__(self, mesh):
        self.mesh = mesh
        self.bones = mesh.bones  # Shared reference to bone hierarchy
        self.skinning_weights = {}  # vertex_id → [(bone_id, weight), ...]
        self.morph_targets = {}     # morph_name → {vertex_id: (dx, dy, dz), ...}
        
        # Register as topology listener
        self.mesh.register_topology_listener(self)
    
    # Builder methods:
    def add_bone(self, name, parent_bone=None):
        bone = Bone(name, parent_bone)
        self.bones.append(bone)
        return bone
    
    def set_vertex_weight(self, vertex_id, bone, weight):
        """Add/update weight for a vertex to a bone."""
        if vertex_id not in self.skinning_weights:
            self.skinning_weights[vertex_id] = []
        
        # Remove existing weight to this bone
        self.skinning_weights[vertex_id] = [
            (b, w) for b, w in self.skinning_weights[vertex_id] if b != bone
        ]
        # Add new weight
        self.skinning_weights[vertex_id].append((bone, weight))
    
    def add_morph_target(self, name):
        """Create a new named morph-target."""
        self.morph_targets[name] = {}
    
    def set_morph_offset(self, morph_name, vertex_id, offset_xyz):
        """Set vertex offset for a morph-target."""
        if morph_name not in self.morph_targets:
            self.add_morph_target(morph_name)
        self.morph_targets[morph_name][vertex_id] = offset_xyz
    
    # Topology listener interface:
    def on_vertex_created(self, new_vertex_id, parent_vertex_id, context="split"):
        """Inherit weights and morph offsets from parent vertex."""
        
        # Inherit skinning weights
        if parent_vertex_id in self.skinning_weights:
            self.skinning_weights[new_vertex_id] = \
                list(self.skinning_weights[parent_vertex_id])  # Shallow copy
        
        # Inherit morph offsets
        for morph_name in self.morph_targets:
            if parent_vertex_id in self.morph_targets[morph_name]:
                self.morph_targets[morph_name][new_vertex_id] = \
                    self.morph_targets[morph_name][parent_vertex_id]
    
    def on_vertex_deleted(self, vertex_id):
        """Clean up orphaned weights and morph offsets."""
        
        if vertex_id in self.skinning_weights:
            del self.skinning_weights[vertex_id]
        
        for morph_name in self.morph_targets:
            if vertex_id in self.morph_targets[morph_name]:
                del self.morph_targets[morph_name][vertex_id]
    
    # Deformation compute:
    def deform_mesh(self, bone_transforms):
        """
        Apply rig to mesh vertices.
        
        Args:
            bone_transforms: {bone_id: Transform(...), ...}
        
        Returns:
            {vertex_id: (x, y, z) deformed position, ...}
        """
        deformed_positions = {}
        for vertex in self.mesh.vertices:
            if vertex.id in self.skinning_weights:
                deformed_positions[vertex.id] = \
                    self._compute_skinned_vertex(vertex, bone_transforms)
            else:
                # Vertex not skinned, use original position
                deformed_positions[vertex.id] = vertex.position
        return deformed_positions
    
    def _compute_skinned_vertex(self, vertex, bone_transforms):
        """Compute skinned position via linear blend skinning."""
        position = (0, 0, 0)
        total_weight = 0
        
        for bone, weight in self.skinning_weights[vertex.id]:
            if bone.id in bone_transforms:
                transform = bone_transforms[bone.id]
                # Transform vertex by this bone
                transformed = transform.apply(vertex.position)
                # Accumulate weighted
                position = tuple(p + w*t for p, w, t in 
                               zip(position, [weight]*3, transformed))
                total_weight += weight
        
        # Normalize by total weight
        if total_weight > 0:
            position = tuple(p / total_weight for p in position)
        
        # Apply active morphs (additive)
        # (Future: morph blending would go here)
        
        return position
    
    # Serialization:
    def export_state(self):
        """Export rig data (can be saved alongside mesh)."""
        return {
            "bones": [bone.to_dict() for bone in self.bones],
            "skinning_weights": self.skinning_weights,
            "morph_targets": self.morph_targets,
        }
    
    def load_state(self, state):
        """Load rig data from export."""
        self.bones = [Bone.from_dict(b) for b in state["bones"]]
        self.skinning_weights = state["skinning_weights"]
        self.morph_targets = state["morph_targets"]
```

---

## Constraints & Guarantees

### What This Architecture Guarantees
1. ✓ **Topology safety**: split/collapse/connect never corrupt rig data (weights auto-sync)
2. ✓ **Clear ownership**: Weights live in RigController, topology in Mesh (separation of concerns)
3. ✓ **Deterministic**: Same topology sequence + same rig → same deformed result
4. ✓ **Undo/Redo**: Can be implemented via mesh state snapshots (RigController auto-syncs on load)
5. ✓ **Backward compatible**: Existing meshes load fine (no rig = no RigController)

### Constraints We Accept
1. **Weight inheritance strategy is fixed**: New vertices inherit parent weight distribution
   - Alternative: User could manually adjust, but default is sensible
2. **Morph-targets must exist before topology edit**: We can't retroactively apply morphs to newly created vertices
   - Solution: Add morphs first, then edit topology
3. **No cross-vertex morphs**: Each morph-target is a per-vertex offset (no shape-blending libraries)
   - Acceptable for initial experiment; can extend later

---

## Implementation Plan

### Phase 1: Core Extension (Week 1)
**Minimal, non-invasive:**
1. Add `bones: []` field to Mesh
2. Add `topology_listeners: []` infrastructure
3. Call `_notify_vertex_created/deleted()` in split/collapse
4. No test changes (observers are invisible to existing tests)
5. Merge to `main` branch

**Risk:** 🟢 Very Low (observer pattern is standard)

### Phase 2: RigController Prototype (Week 1.5)
**In experiments/ only:**
1. Implement RigController class with topology listener
2. Test manually: create mesh → add rig → split vertex → verify weight inheritance
3. Create unit tests for RigController (separate from topology tests)
4. No Mesh tests modified

**Risk:** 🟢 Very Low (isolated experiment code)

### Phase 3: Viewport Integration (Week 1–1.5)
**In experiments/viewport:**
1. Extend existing viewport to render bone skeleton
2. Add keyboard control for bone transforms
3. Render deformed mesh (via RigController.deform_mesh)
4. Test topology edit + observe rig still works

**Risk:** 🟢 Very Low (display layer only)

### Phase 4: Validation & Iteration (Week 2–2.5)
**Low-poly head use case:**
1. Model simple head mesh
2. Rig + skin (3 bones, weights)
3. Add morphs (mouth open, jaw drop)
4. Perform loop insert → verify weights persist
5. Document findings in RESEARCH.md

**Risk:** 🟡 Low (may need weight-merge strategy adjustment, but RigController-only change)

---

## Transition Path (After Validation)

**If experiment is successful:**
1. Move RigController from `experiments/` → `src/core/rigging/`
2. Add rig-aware tests to main suite (coordinated with Phase A–E tests)
3. Extend mesh serialization to include bones/weights/morphs (versioned format)
4. Wire bone hierarchy to future animation system

**If issues arise:**
- Rig strategy wrong → Adjust RigController, no Core change
- Listener pattern problematic → Remove Core extension, keep RigController external (fallback to Option B)
- Performance problem → Optimize listener callbacks or cache

---

## Relationships to Other Work

### WP 02 (Cline's Concurrent Work)
- **Independence:** Rigging experiment runs fully independent
- **Evidence:** RigController design patterns can inform WP 02 architecture
- **No Blocking:** WP 02 may choose different approach; both valid

### Topology Experiment Phase 2
- **Dependency:** Uses existing split/collapse/connect
- **Enhancement:** Adds listener notification (non-invasive)
- **Test Compatibility:** Phase 2 tests remain unchanged

### Future Animation System (Phase F+)
- **Compatibility:** Bone hierarchy in Core.Mesh can be reused
- **Extensibility:** Listener pattern scales to animation, constraints, etc.

---

## Success Criteria

✅ **Decision will be considered successful if:**
1. Low-poly head model can be rigged, weighted, morphed
2. Topology edit (loop insert) executes without crashing
3. Weights remain plausible after topology edit (no NaNs, negative weights, or orphaned data)
4. Deformation in viewport is visually correct
5. Phase A–E tests still pass (37/37 green)
6. Code is documented and decision is recorded for next PM/engineer

❌ **Fallback decision if:**
1. Core extension (observers) causes Phase A–E regression → Strip Core change, move to Option B
2. Weight inheritance strategy is wrong → Adjust RigController, iterate
3. Performance unacceptable → Optimize listener callbacks

---

## References

- **RESEARCH.md** — Technical findings from Core analysis
- **DESIGN.md** — Full option comparison and trade-off analysis
- **CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md** — Phase A–E requirements
- **AD-001** — ID Continuity constraint (relevant to weight management)
- **Topology Experiment Phase 2** — Working example of mesh topology

---

## Approval & Sign-Off

**Technical Decision:** ✓ DECIDED (Hybrid Option C)  
**Recommendation:** Proceed to Phase 1 (Core Extension) in Week 1

**Approved by:**
- Project Owner: **Manu** — TBD
- Architect: **Claude** — ✓ Recommended

**Date Decided:** August 2026

---

**Next Document:** Phase 2 implementation plan (after Core extension merged)
