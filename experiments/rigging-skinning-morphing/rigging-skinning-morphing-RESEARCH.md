# Research Findings: Rigging Integration with Mirai-Bastel Core

## Overview
This document captures technical findings from analyzing the Mirai-Bastel Core architecture, specifically focused on understanding how Rigging, Skinning, and Morph-Targets can cleanly integrate with topology editing operations.

**Key Constraint:** Topology operations (split/collapse/connect) must not invalidate Skinning weights or Morph-targets.

---

## 1. ID Management & Continuity (Phase C Finding)

### Current Architecture
**Rule AD-001: No ID Reuse within a Session**
- Once a Vertex/Edge/Face receives an ID, that ID is never reassigned to a different element
- IDs are never recycled, even after an element is deleted
- This constraint exists to make Undo/Redo deterministic and prevent ID collisions

**Impact on Skinning:**
```
Skinning stores: Vertex_ID → [(Bone_Name, Weight), (Bone_Name, Weight), ...]

If a Vertex is deleted:
- Its ID is "dead" (no longer references any geometry)
- But the ID itself cannot be reused for new vertices

Problem: What happens to dead vertex IDs in Skinning weights?
- Option A: Keep them (dead weight entries) until mesh is reserialized
- Option B: Lazily clean them on export
- Option C: Something else?
```

**✓ This is GOOD for Skinning because:**
- Weights stay tied to specific vertex IDs
- No surprise ID reassignments that would silently corrupt weights
- **But:** We need a cleanup strategy for orphaned weight entries

**? Still Unclear:**
- Should Skinning data live in the Core.Mesh or outside?
- Who owns the "cleanup" of dead weight entries?

---

## 2. Topology Mutations: split / collapse / connect

### How Topology Ops Work Today

#### split(edge) — Insert a new vertex in the middle of an edge
- Creates 1 new Vertex with a new, unique ID
- Modifies face topology
- Returns: new_vertex_id

**Question:** What weight should the new vertex inherit?
- Linear blend of the two endpoint vertices' weights?
- Copy from one endpoint?
- Zero weight (user must manually assign)?

#### collapse(edge) — Merge two vertices into one
- Deletes 1 vertex (marks its ID as dead, per AD-001)
- Survivor vertex keeps its ID
- Modifies face topology
- Returns: survivor_vertex_id

**Question:** How do we merge weights?
- Average the two vertices' weights?
- Keep only survivor's weights?
- Union of both weights?

#### connect(vertices) — Create new edge/face between vertices
- Does NOT create/delete vertices
- Only modifies face connectivity
- May not affect Skinning at all

**? Still Unclear:**
- Current code location: `src/core/operations/topology.py` (need to read exact logic)
- Are there any callbacks/hooks when mutations happen?
- Can we extend mutations with "skinning-aware" logic?

---

## 3. Mesh Serialization & State Management

### Export/Import Strategy
**Current approach (Phases C–E):**
- `Mesh.export_state()` → returns full mesh state (vertices, edges, faces, IDs, etc.)
- `Mesh.load_state(state)` → restores from snapshot

**For Skinning, we'd need to extend this:**
```python
export_state() {
    return {
        vertices: [...],
        edges: [...],
        faces: [...],
        skinning_weights: {  # NEW
            vertex_id: [(bone, weight), ...],
            ...
        },
        morph_targets: {  # NEW
            "mouth_open": {vertex_id: (dx, dy, dz), ...},
            "jaw_drop": {...},
        }
    }
}
```

**Questions:**
- Should we extend Core.Mesh directly, or keep Skinning/Morphs as external data?
- If external: how do we keep them in sync after topology edits?

### Undo/Redo Architecture (Phase D Finding)

**Key Decision: Full State Snapshots, NOT Semantic Operations**

Why? Because AD-001 (no ID reuse) breaks semantic undo.

```python
# SEMANTIC UNDO would look like:
user_action = split(edge_5)  # Creates new vertex_9
undo_action = reverse_split(vertex_9)  # But this would create NEW vertex_ID!
# Problem: The new ID doesn't match old state, UND/REDO breaks

# ACTUAL UNDO in Mirai-Bastel:
user_action = split(edge_5)  # Creates vertex_9
mesh.push_state()  # Saves full state snapshot
# Later:
mesh.pop_state()  # Restores entire state snapshot (vertex_9 reverts, ID is "dead" again)
```

**For Skinning:**
- Undo/Redo MUST include skinning weights in the state snapshot
- No way around it — weights live in the full state, not in semantic operations
- This means: Skinning data must be serialized with the mesh state

**✓ Good news:** The snapshot system is already built; we just extend it

---

## 4. Topology Experiment Phase 2: Working Example

The existing **Edge-Loop selection/insertion** shows how topology edits work in practice:

- `viewport/loop_ring.py`: Query API for finding edge loops (23 unit tests, all passing)
- `viewport/topology_tools.py`: Selection wrapper
- `viewport/topology_app.py`: Keybindings (L/R for Loop/Ring, Insert/Remove)

**Observation:** These work purely on the Mesh graph structure; they don't touch data like materials, colors, or (importantly) **Skinning**.

**Implication:** Loop insertion creates new vertices but has no idea about weights — this is exactly our integration problem!

---

## 5. Key Architectural Constraints

### Hard Rules (Cannot Break)
1. **ID Continuity (AD-001)**: No vertex ID reuse within a session
2. **State Snapshots (Phase D)**: Undo/Redo via full state, not semantic ops
3. **Determinism**: Same sequence of ops must always produce same state
4. **No Silent Corruption**: If we can't auto-update weights, document the limitation

### Design Boundaries
- Core.Mesh itself is stable; we should not cause regressions
- Topology ops should ideally remain ignorant of Skinning (loose coupling)
- But Skinning must survive topology edits (tight correctness)

---

## 6. Integration Opportunities

### Option A: Skinning Inside Core.Mesh
**Structure:**
```python
class Mesh:
    vertices = [...]
    edges = [...]
    faces = [...]
    
    # NEW:
    bones = [Bone(...), ...]  # Bone hierarchy
    skinning_weights = {vertex_id: [(bone_id, weight), ...], ...}
    morph_targets = {name: {vertex_id: (dx, dy, dz), ...}, ...}
```

**Pros:**
- Unified state management
- Undo/Redo automatically includes weights & morphs
- Topology ops can have built-in weight-update logic

**Cons:**
- Core gets more complex
- Need to extend all topology ops with weight-merge logic
- Risk of breaking existing Phase A–E work

### Option B: Skinning as External Mapping
**Structure:**
```python
class Mesh:
    vertices = [...]
    edges = [...]
    faces = [...]
    # No skinning data inside

class RigController:  # Separate, outside Core
    mesh_id → {
        bones: [Bone(...), ...],
        skinning_weights: {vertex_id: [(bone, weight), ...], ...},
        morph_targets: {...}
    }
```

**Pros:**
- Core stays minimal and stable
- Skinning is isolated; topology errors won't corrupt Core
- Can iterate on Skinning without touching Core

**Cons:**
- Two sources of truth (mesh + rig controller)
- Must manually sync after topology edits
- Undo/Redo requires coordinating two systems

### Option C: Hybrid (Core-Aware Rigging, External Weights)
**Structure:**
```python
class Mesh:
    vertices = [...]
    edges = [...]
    faces = [...]
    
    # NEW (lightweight):
    bones = [Bone(...), ...]  # Just the skeleton hierarchy
    
class RigController:  # External (inherits from Mesh.bones)
    bones: Link to Mesh.bones
    skinning_weights: {vertex_id: [(bone_idx, weight), ...], ...}
    morph_targets: {name: {vertex_id: (dx, dy, dz), ...}, ...}
    
    def on_mesh_split(vertex_id, new_vertex_id):
        # Inherit weight from parent vertex
        self.skinning_weights[new_vertex_id] = \
            self.skinning_weights[vertex_id]
    
    def on_mesh_collapse(dead_vertex_id, survivor_vertex_id):
        # Merge or choose weights
        self.skinning_weights[survivor_vertex_id] = \
            average_weights(dead_vertex_id, survivor_vertex_id)
        del self.skinning_weights[dead_vertex_id]
```

**Pros:**
- Core knows about Bones (can reference in future features)
- Weights stay external; easier to debug and extend
- Clear separation of concerns
- Can register callbacks on topology mutations

**Cons:**
- Slightly more complex than B
- Still need synchronization logic

---

## 7. Open Questions (Need to Research Further)

### About Core Architecture
- [ ] Does Core.Mesh have a callback/hook system for mutations?
- [ ] Can we register listeners on split/collapse/connect operations?
- [ ] What's the performance expectation for undo/redo with large meshes?
- [ ] Can we add new fields to Core.Mesh without breaking Phase A–E tests?

### About Viewport
- [ ] How does the existing viewport render deformations (if any)?
- [ ] Can we render skinned geometry real-time (bone transforms → vertex positions)?
- [ ] What's the performance bottleneck: mesh skinning or rendering?

### About Serialization
- [ ] Current file format: JSON / Binary / Other?
- [ ] Can we extend it with Bones/Weights/Morphs without breaking existing files?
- [ ] How do we version the format?

---

## 8. Next Steps

### Immediate
1. **Read Core implementation** (`src/core/operations/topology.py`)
   - Confirm exact logic of split/collapse/connect
   - Check for existing hook/callback mechanisms
   
2. **Decide on Option A/B/C**
   - Based on risk tolerance (A = higher risk/reward, B = lower risk, C = balanced)
   - Document rationale in AD-XXX

3. **Design weight-merge strategy**
   - Linear blend? Average? Union?
   - Test with toy examples

### Then
4. Implement minimal prototype (Phase 2)
5. Test with low-poly head use case
6. Iterate based on findings

---

## 9. References & Evidence

### Docs to Read
- `docs/architecture/AD-001-CONTINUITY.md` (or similar) – Exact ID-reuse rule
- `docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md` – Full Phase A–E findings
- `src/core/operations/topology.py` – Split/collapse/connect implementation
- `src/core/mesh.py` – Mesh data structure

### Tests
- `tests/` directory – Unit tests for Phase A–E
- `tests/README.md` – Error-decision rules

### Experiments
- `experiments/mirai_bastel_viewport_V1/` – Topology Phase 2 (working example)

---

**Document Status:** Phase 1 — Research (In Progress)  
**Last Updated:** August 2026  
**Owner:** Manu (Technical Analysis by Claude)
