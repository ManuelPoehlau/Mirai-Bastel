# Core API Audit — Phase 2a Findings

**Status:** ✓ COMPLETE (basierend auf Analyse von mesh.py, ids.py)  
**Date:** August 2026  
**Method:** Direct source code inspection, no assumptions  

---

## Summary

This document captures the ACTUAL public API of Mirai-Bastel's Core.Mesh and related classes, extracted directly from source code. This is the foundation for RigController design in Phase 2b.

**Key Finding:** The Core provides comprehensive topology query APIs, but **no built-in mechanism to identify which operation caused a topology change**. All operation context must be inferred from before/after state.

---

## 1. ID System (ids.py)

### Class Hierarchy

```python
class ElementId(int):
    """Opaque handle, inherits from int only for convenience (hashing, serialization)."""
    __repr__() → "VertexId(N)" or "EdgeId(N)" or "FaceId(N)"

class VertexId(ElementId)
class EdgeId(ElementId)  
class FaceId(ElementId)
```

### IdAllocator

**Signature:**
```python
class IdAllocator:
    def __init__(self, id_type: type[ElementId], start: int = 0)
    def allocate(self) -> ElementId
    def peek_next(self) -> int
    def restore_counter(self, value: int) -> None
```

### ID Behavior — CRITICAL

**Finding 1: Monotonic Counter, No Recycling (AD-001)**
- Every `allocate()` returns `id_type(self._next)`, then increments counter
- Counter starts at 0 (or custom start)
- **IDs are NEVER reused**, even after element deletion
- `restore_counter(value)` only moves counter FORWARD (never backwards)

**Finding 2: ID Opacity**
- IDs are ElementId subclasses (inherit from int)
- Safe to use as dictionary keys, hashable
- Safe to serialize as integers
- **Never interpret as array index** (explicitly documented)

**Finding 3: Validity Checking**
- ID validity checked via `mesh.is_valid_vertex(id)` / `edge` / `face`
- No "self-validity" method on ID itself
- Dead IDs (from deleted elements) are still technically "int values" but `is_valid_*()` returns False

**Example:** After 5 vertices created (IDs 0–4), if vertex 2 is deleted:
- `mesh.is_valid_vertex(VertexId(2))` → False
- But VertexId(2) still exists as an int value
- Next `allocate()` returns VertexId(5), NOT VertexId(2)

---

## 2. Mesh Data Structures (mesh.py)

### Internal Representation

```python
class Mesh:
    _vertices: dict[VertexId, _VertexData]     # {id: position}
    _edges: dict[EdgeId, _EdgeData]            # {id: (v0, v1, [faces])}
    _faces: dict[FaceId, _FaceData]            # {id: boundary=[v_ids]}
    _edge_lookup: dict[frozenset[VertexId], EdgeId]  # Unordered pair → edge
```

### Position Storage

**API:**
```python
def vertex_position(self, vertex_id: VertexId) -> Position
    # Returns: tuple[float, float, float]

def set_vertex_position(self, vertex_id: VertexId, position: Position) -> None
    # Sets base position; future systems (Morph/Skin) can override display
```

**Finding:** Position is accessed ONLY through methods, never as raw attribute. This reserves space for deformation chain (Base → Morph → Skin → Subdivision).

---

## 3. Topology Query API (AD-002)

**Key Contract:** These are the ONLY public methods to read topology. No direct access to `_vertices`, `_edges`, `_faces`.

### 3.1 All Elements

```python
def all_vertex_ids(self) -> list[VertexId]
    # Returns all vertex IDs (including unrelated ones)
    # Dead IDs NOT returned (only live vertices in _vertices dict)

def all_edge_ids(self) -> list[EdgeId]
    # Same behavior for edges

def all_face_ids(self) -> list[FaceId]
    # Same behavior for faces
```

**Finding:** These are set-like queries (return all live IDs). Can be used for "before/after" snapshots to detect changes.

### 3.2 From Face

```python
def face_vertices(self, face_id: FaceId) -> list[VertexId]
    # Returns boundary vertices in order
    # Example: triangle face → [v0, v1, v2]
    # Matches the internal _FaceData.boundary order

def face_edges(self, face_id: FaceId) -> list[EdgeId]
    # Returns edges that make up the boundary
    # Computed by walking boundary and looking up edges in _edge_lookup
    # Order: (boundary[0]→boundary[1]), (boundary[1]→boundary[2]), ..., (boundary[-1]→boundary[0])
```

**Finding:** Edges are returned in boundary order. Edge direction (which endpoint is v0 vs v1) is NOT guaranteed; edges are undirected internally.

### 3.3 From Edge

```python
def edge_vertices(self, edge_id: EdgeId) -> tuple[VertexId, VertexId]
    # Returns: (v0, v1)
    # v0 and v1 are stored in _EdgeData, order determined by edge creation
    # NOT guaranteed to match any particular boundary winding order

def edge_faces(self, edge_id: EdgeId) -> list[FaceId]
    # Returns all faces that reference this edge
    # 0 faces: free edge (boundary)
    # 1 face: border edge
    # 2 faces: internal manifold edge
    # >2 faces: non-manifold (V1 allows but doesn't prevent)
```

**Finding:** Edges are undirected; `edge_vertices()` returns (v0, v1) but order is NOT semantic.

### 3.4 From Vertex

```python
def vertex_edges(self, vertex_id: VertexId) -> list[EdgeId]
    # Returns all edges that touch this vertex
    # Implementation: simple scan through all edges
    # (Comment says this could be O(1) via Half-Edge later, but not V1)

# NO METHOD for adjacent vertices or vertex neighbors!
# Must infer from edges manually:
#   edges = mesh.vertex_edges(v)
#   neighbors = {e_other for e in edges for e_other in edge_vertices(e) if e_other != v}
```

**Finding:** NO direct "adjacent vertices" API. Must combine `vertex_edges()` + `edge_vertices()`.

### 3.5 Validity

```python
def is_valid_vertex(self, vertex_id: VertexId) -> bool
    return vertex_id in self._vertices

def is_valid_edge(self, edge_id: EdgeId) -> bool
    return edge_id in self._edges

def is_valid_face(self, face_id: FaceId) -> bool
    return face_id in self._faces
```

**Finding:** Simple membership checks. Dead IDs return False immediately.

---

## 4. Mutation Layer (Topology Operations)

### 4.1 add_vertex()

**Signature:**
```python
def add_vertex(self, position: Position) -> VertexId
```

**Behavior:**
- Creates new vertex at given position
- Returns newly allocated VertexId
- No connectivity yet (isolated vertex)

**ID Contract:** Creates exactly 1 new VertexId.

---

### 4.2 add_face()

**Signature:**
```python
def add_face(self, vertex_ids: list[VertexId]) -> FaceId
```

**Behavior:**
- Takes ordered list of existing vertex IDs (min 3 vertices)
- Creates new face with those vertices as boundary
- For each edge in boundary: if edge exists (via _edge_lookup), reuse it; else create new edge
- Adds this face to edge.faces list

**ID Contract:**
- All vertex IDs remain unchanged
- Edges may be created or reused (no guarantees on which)
- Creates exactly 1 new FaceId
- May create multiple new EdgeIds

**Finding:** Can't predict how many new edges are created without knowing pre-existing topology.

---

### 4.3 remove_face()

**Signature:**
```python
def remove_face(self, face_id: FaceId) -> None
```

**Behavior:**
- Removes face from mesh
- Updates edge.faces lists
- **Edges are NOT deleted** (even if now boundary/free)

**ID Contract:**
- FaceId becomes invalid
- Vertex IDs unchanged
- Edge IDs unchanged (even free edges remain)

**Finding:** Cleaning up orphaned edges is caller's responsibility, not automatic.

---

### 4.4 split_edge() — CRITICAL

**Signature:**
```python
def split_edge(self, edge_id: EdgeId) -> tuple[VertexId, EdgeId, EdgeId]
    # Returns: (new_vertex_id, new_edge_id_a, new_edge_id_b)
```

**Behavior:**
1. Original edge (edge_id) is deleted
2. New vertex created at midpoint: `mid_pos = (p0 + p1) / 2`
3. Two new edges created: `(v0, mid)` and `(mid, v1)`
4. All faces that referenced original edge updated: new vertex inserted in boundary
5. New edges added to those faces' edge.faces lists

**ID Contract:**
- Original EdgeId → invalid
- Both original EndpointVertexIds → remain valid, unchanged position
- Creates exactly 1 new VertexId
- Creates exactly 2 new EdgeIds
- Affected FaceIds → remain valid, boundaries updated

**Position Calculation (IMPORTANT):**
```python
p0 = self.vertex_position(edge.v0)
p1 = self.vertex_position(edge.v1)
mid_pos = tuple((a + b) / 2.0 for a, b in zip(p0, p1))  # Linear interpolation
```

**Finding 1:** New vertex position is ALWAYS the linear midpoint. No caller override.

**Finding 2:** To identify split() after-the-fact:
- 1 new vertex created
- 1 old edge deleted (dead)
- 2 new edges created
- Affected faces' boundaries enlarged by 1

**Finding 3:** To infer parent vertex: new vertex position ≈ midpoint of some edge's endpoints. But WHICH edge? Must check all edges.

---

### 4.5 collapse_edge() — CRITICAL

**Signature:**
```python
def collapse_edge(self, edge_id: EdgeId) -> VertexId
    # Returns: survivor_vertex_id
```

**Behavior:**
1. Original edge (edge_id) is deleted
2. **Survivor = v0** (first endpoint of edge.v0/v1 pair), **removed = v1**
3. Survivor's position updated: `(p0 + p1) / 2`
4. All other edges touching `removed`: redirected to `survivor`
   - If survivor↔other edge already exists, merge face lists
   - If survivor==other (parallel self-edge), delete it
5. All faces updated: `removed` → `survivor` in boundary
6. Deduplication: consecutive duplicate vertices in boundary removed
7. Degenerate faces (<3 unique vertices) deleted
8. Vertex `removed` deleted

**ID Contract:**
- Original EdgeId → invalid
- v0 (survivor) → remains valid, position updated
- v1 (removed) → becomes invalid
- New edges: NONE (only merges existing)
- Affected FaceIds → remain valid, may be removed if degenerate
- Other EdgeIds → may be redirected (ID remains)

**Critical Finding 1: Survivor = v0**
```python
survivor, removed = edge.v0, edge.v1
```

This is FIXED. The first endpoint (v0) always survives.

**Critical Finding 2: Survivor Determination**
```python
def edge_vertices(self, edge_id: EdgeId) -> tuple[VertexId, VertexId]:
    e = self._edges[edge_id]
    return (e.v0, e.v1)
```

So after collapse(), if we know the edge, we can ask Core:
- Before collapse: `v0, v1 = mesh.edge_vertices(edge_id)`
- After collapse: One of them is gone, the other survives

**Critical Finding 3: Detecting collapse() post-hoc**
- 1 vertex deleted
- 1 edge deleted
- Other edges may be merged (face lists combined, IDs unchanged)
- Faces remain (or reduced if degenerate)

**Finding 4:** To know which vertex was deleted:
- Before: `vertices_before = set(mesh.all_vertex_ids())`
- After: `vertices_after = set(mesh.all_vertex_ids())`
- Deleted: `vertices_before - vertices_after` (exactly 1)
- Survivor: The one that wasn't deleted

---

### 4.6 connect_vertices() — CRITICAL for Edge/Face Lifecycle

**Signature:**
```python
def connect_vertices(self, face_id: FaceId, v_a: VertexId, v_b: VertexId) 
    -> tuple[EdgeId, FaceId, FaceId]
    # Returns: (new_edge_id, new_face_id_1, new_face_id_2)
```

**Behavior:**
1. Original face (face_id) is deleted
2. Boundary is split into two loops along the diagonal v_a ↔ v_b
3. New edge created between v_a and v_b (via add_face internal call)
4. Two new faces created from the two loops

**ID Contract:**
- Original FaceId → invalid
- new_edge = existing edge between v_a/v_b (lookup from _edge_lookup)
- Creates exactly 2 new FaceIds
- Vertex IDs unchanged
- Existing edges in original boundary: remain valid, but edge.faces updated

**Edge Creation Detail:**
```python
# Inside add_face(), new edge created via _get_or_create_edge()
new_edge = self._edge_lookup[frozenset((v_a, v_b))]
```

The edge between v_a and v_b is created/reused by add_face().

**Critical Finding 1: connect() creates no NEW vertices**
- 2 vertices provided (must be on boundary)
- Exactly 2 new FaceIds created
- Exactly 1 new EdgeId created (the split edge)

**Critical Finding 2: To detect connect() post-hoc**
- 1 vertex unchanged (v_a and v_b both still there)
- 1 face deleted
- 2 new faces created
- 1 new edge created

**Finding 3:** If v_a and v_b are on boundary and we know the face, connect is deterministic. But after it happens, which two faces are the result? Must check face boundaries (one contains v_a→...→v_b arc, other contains v_b→...→v_a arc).

---

## 5. Serialization

### export_state()

**Signature:**
```python
def export_state(self) -> dict
```

**Returns:**
```python
{
    "vertex_id_counter": int,
    "edge_id_counter": int,
    "face_id_counter": int,
    "vertices": {int(vid): [x, y, z], ...},
    "edges": {int(eid): {"v0": int, "v1": int, "faces": [int, ...]}, ...},
    "faces": {int(fid): [int, int, ...], ...},  # boundary vertex IDs
}
```

**Finding:** Complete state snapshot. Allocator counters included to prevent ID collision on load.

### load_state()

**Signature:**
```python
def load_state(self, state: dict) -> None
```

**Behavior:**
- IN-PLACE replacement of mesh contents
- Restores allocator counters (only forward, never backward)
- Clears all internal containers first

**Finding:** Used for Undo/Redo; entire mesh state snapshot.

### from_state() (classmethod)

**Signature:**
```python
@classmethod
def from_state(cls, state: dict) -> "Mesh"
```

**Behavior:**
- Creates NEW mesh instance
- Loads state into it

**Finding:** Constructor alternative for deserialization.

---

## 6. API Gaps & Limitations — Implications for RigController

### Gap 1: No Operation Context

**Problem:** After topology changes, we can't ask Core "what operation just happened?"

**Evidence:** No API like `get_last_operation()`, `operation_type()`, etc.

**Workaround:** Infer from before/after snapshot:
- 1 vertex created, 1 edge deleted → probably split()
- 1 vertex deleted, 1 edge deleted → probably collapse()
- 1 edge created, 2 faces affected → probably connect()

**Limitation:** Ambiguous in edge cases.

### Gap 2: No Vertex Lineage

**Problem:** After `split()`, we can't ask "which edge was this vertex created from?"

**Evidence:** New vertex has no metadata about its origin.

**Workaround:** Check all edges; if new_vertex ≈ midpoint of edge endpoints, likely parent.

**Limitation:** Geometric heuristic, unreliable.

### Gap 3: No Per-Vertex Topology Cache

**Problem:** `vertex_edges()` scans all edges (O(n) per query).

**Evidence:** Comment in code: "V1: simple scan. Query-API stays stable if replaced by O(1) Half-Edge later."

**Impact:** Repeated calls inefficient, but correct.

### Gap 4: No Automatic Edge Cleanup

**Problem:** `remove_face()` doesn't delete orphaned edges.

**Evidence:** Documented: "Edges that now have 0 faces remain as free edges, not deleted."

**Implication:** Must track manually or live with stale edges.

### Gap 5: No Non-Manifold Warnings

**Problem:** Core allows >2 faces per edge (non-manifold), but doesn't warn.

**Evidence:** Code handles it but doesn't validate.

**Implication:** Skin weights could break on non-manifold geometry (not V1 concern, but future issue).

---

## 7. What RigController CAN Reliably Do

✅ **Detect topology changes** via set difference (all_vertex_ids, all_edge_ids, all_face_ids)

✅ **Query connectivity** via vertex_edges, edge_faces, face_vertices, face_edges

✅ **Get vertex positions** and set them

✅ **Identify which vertex survived collapse()** by checking which one is still valid

✅ **Detect new vertex from split()** by finding vertices not in before-snapshot

✅ **Track which faces changed** by comparing face_vertices() before/after

✅ **Find vertices from faces** via face_vertices()

✅ **Find edges from faces** via face_edges()

---

## 8. What RigController CANNOT Reliably Do (Without Core Extension)

❌ **Identify which edge was split** without checking all edges

❌ **Know which vertex was parent** in split() without geometric inference

❌ **Determine operation type** without ambiguous heuristics

❌ **Get vertex creation context** (which operation created it, when)

❌ **Query edge creation/deletion reasons** (why this edge now exists/gone)

---

## 9. Design Implications for Phase 2b

### Strategy 1: Snapshot-Based Change Detection ✓
- Before each operation: `snapshot = {verts, edges, faces}`
- After operation: compare with current state
- Infer what changed (not which operation)
- **Reliability:** HIGH

### Strategy 2: Geometric Heuristics for Parent Inference ⚠️
- After split(): find new vertex
- Check all edges: if new_vertex ≈ midpoint, that's likely parent
- **Reliability:** MEDIUM (fails if two edges have same midpoint)

### Strategy 3: Brute-Force Comparison for Edge Topology ✓
- Before/after: store all edge properties
- Identify new/deleted/modified edges
- Correlate with vertex changes
- **Reliability:** HIGH

### Strategy 4: Accept Limitations, Document Them ✓
- Some questions can't be answered without Core support
- Flag these in RigController output
- Document workarounds

---

## 10. Next Steps (Phase 2b Design)

1. **Build RigController.take_snapshot()**  
   - Captures all_vertex_ids(), all_edge_ids(), all_face_ids()
   - Stores with label for debugging

2. **Build RigController.detect_changes()**  
   - Compares current state with last snapshot
   - Returns: new_vertices, deleted_vertices, new_edges, deleted_edges, new_faces, deleted_faces

3. **Build RigController.query_vertex_topology(vertex_id)**  
   - Returns: connected edges, connected faces, adjacent vertices (computed)
   - Useful for understanding a vertex's role after topology change

4. **Build RigController.handle_new_vertex(vertex_id)**  
   - Try to infer parent (via geometric heuristic or fail gracefully)
   - Inherit weights if parent found
   - Log as UNKNOWN if not found

5. **Build RigController.handle_deleted_vertex(vertex_id)**  
   - Clean up weights
   - Clean up morphs

6. **For collapse(): Prove survivor detection works**  
   - Before collapse: `v0, v1 = mesh.edge_vertices(edge_id)`
   - After collapse: check which one is still valid
   - Assign dead vertex → parent for weight merge decision

7. **For connect(): Document edge/face creation**  
   - Trace which faces were split
   - Verify new edge is correctly identified

---

## Conclusion

**The Core API is comprehensive for topology QUERIES. It provides everything needed to OBSERVE topology changes. It lacks operation CONTEXT — which operation caused the change, not what changed.**

RigController can work around this via snapshots and inference, but Core extensions (operation logging, vertex parent tracking) would significantly improve reliability.

---

**Document Status:** ✓ COMPLETE  
**Date:** August 2026  
**Ready for:** Phase 2b RigController Design
