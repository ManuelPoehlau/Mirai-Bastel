# Gate 5 Implementation Readiness — Viewport Production (V0.2)

**Status:** Ready to implement (depends on Gate 3 complete)  
**Duration:** 2 work sessions  
**Branch:** `wp/04-production-foundation` (shared with Gate 3/4)  
**Source spec:** `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md`

---

## Overview

Gate 5 implements the V0.2 Viewport Architecture: incremental GPU updates, persistent resources, overlay selection, CPU picking.

**Key principle:** "Update only what changed" (replaces V1's "rebuild everything")

**Relationship to original plan:**
- **NEW Gate 5:** Viewport Production (was Task 3.8–3.10, now standalone)
- **Gate 5b (separate):** Selection & Display Integration (depends on Gate 5 complete)

---

## Pre-Implementation Checklist

- [ ] Gate 3 complete (Application, ToolManager, tools framework)
- [ ] Gate 4 complete (Interaction routing, tool lifecycle)
- [ ] `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` reviewed and understood
- [ ] Reference mesh available: `experiments/rigging-skinning-morphing/meshes/head_basemesh.obj` (326V)
- [ ] Pyglet installed and working (for VertexList)
- [ ] Profiling setup ready (for benchmark counter measurement)

---

## Directory Structure (to create)

```
src/viewport/                       # NEW — Pure rendering module (swappable)
├── __init__.py
├── render_mesh.py                  # RenderMesh: GPU resource management + dirty-state
├── derived.py                      # Normals (incremental), Bounds (cached), adjacency
├── overlay.py                      # Selection/Hover overlay (separate geometry)
├── picker.py                       # CPU Picker (vertex/edge/face)
├── camera.py                       # OrbitCamera (V0.2 Dirty-State: camera ≠ geometry)
└── benchmark.py                    # Counter/metric collection (for Gate 8)

tests/                              # NEW test files (viewport-specific)
├── test_render_mesh.py             # 15+ RenderMesh allocation/update tests
├── test_derived_geometry.py        # 10+ incremental normal/bounds tests
├── test_overlay.py                 # 8+ overlay selection/visualization tests
├── test_picker.py                  # 10+ CPU picking tests (v0.2 constraints)
├── test_benchmark_counters.py      # 5+ counter/metric tests
└── test_viewport_integration.py    # 10+ end-to-end viewport tests
```

**Integration point with Application:**
- Application.viewport property (instance of Viewport or similar facade)
- Application can instantiate RenderMesh, query picker, manage overlays

---

## Tasks (Session 1)

### Task 5.1: RenderMesh Core (GPU Resource Management)

**Duration:** ~4 hours

**File:** `src/viewport/render_mesh.py`

**Specification:**

```python
from typing import Set, Dict, Optional, Tuple
import pyglet
from pyglet.gl import *
from mirai.core import Mesh

class RenderMesh:
    """
    Manages persistent GPU geometry + dirty-state tracking.
    
    Core principle: Allocate GPU resources once; patch content on update.
    Never recreate VertexLists for non-topology changes.
    """
    
    def __init__(self, mesh: Mesh):
        """Allocate GPU resources (one-time cost)."""
        self.mesh = mesh
        self.vertex_count = len(mesh.all_vertex_ids())
        self.face_count = len(mesh.all_face_ids())
        
        # Persistent GPU resources (never recreated unless topology changes)
        self.position_vbo: Optional[pyglet.graphics.VertexList] = None
        self.normal_vbo: Optional[pyglet.graphics.VertexList] = None
        self.index_ibo: Optional[pyglet.graphics.VertexList] = None
        
        # Dirty-state tracking
        self.position_revision: int = 0
        self.topology_revision: int = 0
        self.modified_vertices: Set[int] = set()
        
        # Cache
        self.bounds_valid: bool = False
        self.aabb_min: Tuple[float, float, float] = (0, 0, 0)
        self.aabb_max: Tuple[float, float, float] = (0, 0, 0)
        
        # Adjacency (updated on topology changes)
        self.vertex_to_faces: Dict[int, Set[int]] = {}
        
        # Benchmarking
        self.geometry_uploads: int = 0
        self.structural_rebuilds: int = 0
        self.normal_recomputations: int = 0
        self.bounds_recalculations: int = 0
        self.gpu_resource_creations: int = 0
        
        self._initialize()
    
    def _initialize(self) -> None:
        """Initial allocation of GPU resources."""
        # Get initial geometry
        positions = self._get_positions()
        normals = self._compute_normals_full()
        indices = self._get_indices()
        
        # Create persistent VertexLists
        vertex_format = 'v3f/stream'  # 3D position, streaming (will be patched)
        normal_format = 'n3f/stream'  # Normal, streaming
        
        # For simplicity: single VertexList with interleaved data
        # (production might use separate VBOs with explicit buffer management)
        self.position_vbo = pyglet.graphics.vertex_list(
            self.vertex_count,
            ('v3f', positions),
        )
        self.normal_vbo = pyglet.graphics.vertex_list(
            self.vertex_count,
            ('n3f', normals),
        )
        self.index_ibo = pyglet.graphics.vertex_list_indexed(
            self.vertex_count,
            ('B', indices),  # indices as bytes
            ('v3f', positions),
        )
        
        self.gpu_resource_creations += 3
        
        # Build adjacency
        self._build_vertex_to_faces()
        
        # Initial bounds
        self._recalculate_bounds()
    
    def update_positions(self, modified_vertex_ids: Set[int]) -> None:
        """
        Update position buffer for given vertices (incremental patch).
        
        Recomputes only affected normals.
        """
        if not modified_vertex_ids:
            return
        
        # Patch position buffer
        new_positions = self._get_positions_for_vertices(modified_vertex_ids)
        self.position_vbo.vertices = new_positions  # pyglet VertexList update
        
        self.geometry_uploads += 1
        
        # Update affected normals
        affected_faces = set()
        for v_id in modified_vertex_ids:
            if v_id in self.vertex_to_faces:
                affected_faces.update(self.vertex_to_faces[v_id])
        
        if affected_faces:
            self._recompute_normals(affected_faces, modified_vertex_ids)
        
        # Update bounds
        self._recalculate_bounds()
        
        # Track state
        self.position_revision += 1
        self.modified_vertices = modified_vertex_ids
    
    def update_topology(self, new_mesh: Mesh) -> None:
        """
        Structural rebuild (allowed for topology changes).
        
        Reallocates GPU resources if needed.
        """
        self.mesh = new_mesh
        
        # Full rebuild: re-initialize
        self._initialize()
        
        self.structural_rebuilds += 1
        self.topology_revision += 1
        self.modified_vertices.clear()
    
    def render(self, camera) -> None:
        """Issue draw call with current geometry."""
        if not self.position_vbo or not self.index_ibo:
            return
        
        # Set camera matrices (uniforms)
        # ... (Pyglet/OpenGL setup)
        
        # Draw
        self.index_ibo.draw(GL_TRIANGLES)
    
    # Helper methods (internal)
    
    def _get_positions(self) -> tuple:
        """Get all vertex positions from mesh."""
        positions = []
        for v_id in self.mesh.all_vertex_ids():
            pos = self.mesh.vertex_position(v_id)
            positions.extend(pos)
        return tuple(positions)
    
    def _get_positions_for_vertices(self, vertex_ids: Set[int]) -> tuple:
        """Get positions for specific vertices."""
        positions = []
        for v_id in vertex_ids:
            pos = self.mesh.vertex_position(v_id)
            positions.extend(pos)
        return tuple(positions)
    
    def _compute_normals_full(self) -> tuple:
        """Compute normals for all vertices."""
        # Pseudocode: Face-average normals per vertex
        normals = []
        for v_id in self.mesh.all_vertex_ids():
            # Collect faces, average normals
            face_normals = [...]  # compute per face
            avg_normal = ...
            normals.extend(avg_normal)
        return tuple(normals)
    
    def _recompute_normals(self, affected_faces: Set[int], affected_vertices: Set[int]) -> None:
        """
        Recompute normals for affected vertices (incremental).
        
        Only vertices adjacent to affected_faces are updated.
        """
        self.normal_recomputations += 1
        
        # Get affected vertex IDs
        vertices_to_update = set()
        for f_id in affected_faces:
            vertices_to_update.update(self.mesh.face_vertex_ids(f_id))
        
        # Recompute only for these vertices
        new_normals = []
        for v_id in sorted(vertices_to_update):
            # Recompute from affected faces only
            avg_normal = ...
            new_normals.extend(avg_normal)
        
        # Patch normal buffer
        self.normal_vbo.vertices = new_normals
        self.geometry_uploads += 1
    
    def _build_vertex_to_faces(self) -> None:
        """Build adjacency structure: vertex ID → set of face IDs."""
        self.vertex_to_faces = {v: set() for v in self.mesh.all_vertex_ids()}
        for f_id in self.mesh.all_face_ids():
            for v_id in self.mesh.face_vertex_ids(f_id):
                self.vertex_to_faces[v_id].add(f_id)
    
    def _recalculate_bounds(self) -> None:
        """Recalculate AABB from current positions."""
        self.bounds_recalculations += 1
        
        positions = self._get_positions()
        # Compute min/max
        self.aabb_min = min(positions[i::3] for i in range(3))
        self.aabb_max = max(positions[i::3] for i in range(3))
        self.bounds_valid = True
    
    def _get_indices(self) -> tuple:
        """Get face index buffer."""
        indices = []
        for f_id in self.mesh.all_face_ids():
            v_ids = self.mesh.face_vertex_ids(f_id)
            # Convert to triangles if quads
            indices.extend(self._face_to_triangles(v_ids))
        return tuple(indices)
    
    def _face_to_triangles(self, v_ids: list) -> list:
        """Convert quad/polygon to triangles (simple fan triangulation)."""
        if len(v_ids) == 3:
            return v_ids
        elif len(v_ids) == 4:
            return [v_ids[0], v_ids[1], v_ids[2], v_ids[0], v_ids[2], v_ids[3]]
        else:
            raise ValueError(f"Unsupported face: {len(v_ids)} vertices")
    
    # Benchmark accessors
    @property
    def benchmark_counters(self) -> dict:
        """Return all benchmark counters."""
        return {
            'geometry_uploads': self.geometry_uploads,
            'structural_rebuilds': self.structural_rebuilds,
            'normal_recomputations': self.normal_recomputations,
            'bounds_recalculations': self.bounds_recalculations,
            'gpu_resource_creations': self.gpu_resource_creations,
        }
```

**Acceptance:**
- [ ] RenderMesh instantiates without errors
- [ ] Persistent VertexList allocation verified (no recreation on update)
- [ ] 8+ allocation tests pass
- [ ] Dirty-state properties accessible

---

### Task 5.2: Derived Geometry (Incremental Normals + Bounds)

**Duration:** ~3 hours

**File:** `src/viewport/derived.py`

**Specification:**

```python
from typing import Set, Tuple

class DerivedGeometry:
    """
    Manages computed/derived data: normals, bounds, adjacency.
    
    Supports incremental updates.
    """
    
    def __init__(self, mesh, render_mesh):
        self.mesh = mesh
        self.render_mesh = render_mesh
        self.vertex_to_faces = {}  # Built during initialization
        self._build_adjacency()
    
    def recompute_affected_normals(self, affected_face_ids: Set[int]) -> None:
        """
        Recompute normals only for faces in the given set.
        
        Vertices are inferred from these faces.
        """
        # Implementation (similar to RenderMesh._recompute_normals)
        pass
    
    def recalculate_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Calculate AABB from current positions."""
        # Implementation
        pass
    
    def _build_adjacency(self) -> None:
        """Build vertex → faces map."""
        # Implementation
        pass
```

**Acceptance:**
- [ ] Adjacency structure correct
- [ ] Incremental normal recomputation verified
- [ ] Bounds caching works
- [ ] 7+ derived geometry tests pass

---

### Task 5.3: Overlay Selection

**Duration:** ~2 hours

**File:** `src/viewport/overlay.py`

**Specification:**

```python
from typing import Optional, Set
from enum import Enum
import pyglet

class OverlayElement(Enum):
    HOVERED = "hovered"      # Yellow/preview
    SELECTED = "selected"    # Cyan/solid

class SelectionOverlay:
    """
    Separate rendering layer for selection/hover.
    
    Never modifies or depends on base mesh geometry.
    """
    
    def __init__(self):
        self.hovered_element: Optional[Tuple[str, int]] = None  # ('vertex', 0)
        self.selected_elements: Set[Tuple[str, int]] = set()
        self.overlay_vbo: Optional[pyglet.graphics.VertexList] = None
    
    def highlight(self, element_type: str, element_id: int) -> None:
        """Set hover highlight."""
        self.hovered_element = (element_type, element_id)
        self._rebuild_overlay_geometry()
    
    def select(self, element_type: str, element_id: int) -> None:
        """Add to selection."""
        self.selected_elements.add((element_type, element_id))
        self._rebuild_overlay_geometry()
    
    def deselect(self, element_type: str, element_id: int) -> None:
        """Remove from selection."""
        self.selected_elements.discard((element_type, element_id))
        self._rebuild_overlay_geometry()
    
    def clear_selection(self) -> None:
        """Clear all selection."""
        self.selected_elements.clear()
        self._rebuild_overlay_geometry()
    
    def render(self, camera) -> None:
        """Draw overlay on top of base mesh."""
        if not self.overlay_vbo:
            return
        # Render with bright colors (yellow/cyan)
        # ...
    
    def _rebuild_overlay_geometry(self) -> None:
        """
        Rebuild overlay mesh (small, only for selected/hovered).
        
        This does NOT touch base mesh.
        """
        # Build small geometry for selected elements
        # (e.g., spheres at vertices, lines for edges)
        pass
```

**Acceptance:**
- [ ] Overlay instantiates independently
- [ ] Selection/hover state manageable
- [ ] Overlay rebuild verified (base mesh untouched)
- [ ] 6+ overlay tests pass

---

## Tasks (Session 2)

### Task 5.4: CPU Picker (V0.2 Constraints)

**Duration:** ~3 hours

**File:** `src/viewport/picker.py`

**Specification:**

```python
from typing import Optional, Tuple
from enum import Enum
import math

class PickMode(Enum):
    VERTEX = "vertex"
    EDGE = "edge"
    FACE = "face"

class Picker:
    """
    CPU-based picking (linear scan).
    
    Per V0.2 spec: linear scan acceptable for reference mesh (326V).
    Optimizations (spatial grid, GPU ID-buffer) deferred.
    """
    
    def __init__(self, render_mesh, camera, screen_width: int, screen_height: int):
        self.render_mesh = render_mesh
        self.camera = camera
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        self.pick_threshold_pixels = 5.0  # Tolerance
    
    def pick_vertex(self, screen_x: float, screen_y: float) -> Optional[int]:
        """
        Find closest vertex to screen position (within threshold).
        
        Returns vertex ID or None.
        """
        # Project all vertices to screen space
        closest_vertex = None
        closest_distance = self.pick_threshold_pixels
        
        for v_id in self.render_mesh.mesh.all_vertex_ids():
            pos_3d = self.render_mesh.mesh.vertex_position(v_id)
            pos_screen = self.camera.project_to_screen(pos_3d, self.screen_width, self.screen_height)
            
            dx = pos_screen[0] - screen_x
            dy = pos_screen[1] - screen_y
            distance = math.sqrt(dx*dx + dy*dy)
            
            if distance < closest_distance:
                closest_distance = distance
                closest_vertex = v_id
        
        return closest_vertex
    
    def pick_edge(self, screen_x: float, screen_y: float) -> Optional[Tuple[int, int]]:
        """
        Find closest edge to screen position.
        
        Returns (v1_id, v2_id) or None.
        """
        closest_edge = None
        closest_distance = self.pick_threshold_pixels
        
        for e_id in self.render_mesh.mesh.all_edge_ids():
            v1, v2 = self.render_mesh.mesh.edge_vertex_ids(e_id)
            
            p1_3d = self.render_mesh.mesh.vertex_position(v1)
            p2_3d = self.render_mesh.mesh.vertex_position(v2)
            
            p1_screen = self.camera.project_to_screen(p1_3d, self.screen_width, self.screen_height)
            p2_screen = self.camera.project_to_screen(p2_3d, self.screen_width, self.screen_height)
            
            # Distance from point to line segment
            distance = self._point_to_segment_distance(
                (screen_x, screen_y), p1_screen, p2_screen
            )
            
            if distance < closest_distance:
                closest_distance = distance
                closest_edge = (v1, v2)
        
        return closest_edge
    
    def pick_face(self, screen_x: float, screen_y: float) -> Optional[int]:
        """
        Find face under screen position (ray-triangle intersection).
        
        Returns face ID or None.
        """
        # Ray cast from camera through screen point
        ray_origin, ray_direction = self.camera.screen_to_ray(
            screen_x, screen_y, self.screen_width, self.screen_height
        )
        
        closest_face = None
        closest_t = float('inf')
        
        for f_id in self.render_mesh.mesh.all_face_ids():
            # Get face vertices
            v_ids = self.render_mesh.mesh.face_vertex_ids(f_id)
            
            # Triangulate if needed
            for tri in self._face_to_triangles(v_ids):
                p0 = self.render_mesh.mesh.vertex_position(tri[0])
                p1 = self.render_mesh.mesh.vertex_position(tri[1])
                p2 = self.render_mesh.mesh.vertex_position(tri[2])
                
                t = self._ray_triangle_intersection(
                    ray_origin, ray_direction, p0, p1, p2
                )
                
                if t is not None and t < closest_t:
                    closest_t = t
                    closest_face = f_id
        
        return closest_face
    
    # Helper methods
    
    def _point_to_segment_distance(self, p, a, b):
        """Compute distance from point to line segment."""
        # Standard algorithm
        pass
    
    def _ray_triangle_intersection(self, ray_orig, ray_dir, p0, p1, p2):
        """Compute ray-triangle intersection (Möller-Trumbore)."""
        # Standard algorithm
        pass
    
    def _face_to_triangles(self, v_ids):
        """Convert quad/polygon to triangles."""
        # Same as RenderMesh
        pass
```

**Acceptance:**
- [ ] Picker instantiates with render_mesh and camera
- [ ] pick_vertex() returns correct element or None
- [ ] Threshold correctly applied
- [ ] 8+ picker tests pass

---

### Task 5.5: Camera (V0.2 Dirty-State)

**Duration:** ~2 hours

**File:** `src/viewport/camera.py`

**Specification:**

```python
from mirai.core import Scene

class OrbitCamera:
    """
    Orbit camera (Mirai-style interaction).
    
    Per V0.2: Camera updates NEVER invalidate mesh geometry.
    View/projection matrices live in uniforms, not mesh data.
    """
    
    def __init__(self):
        self.center = (0, 0, 0)
        self.distance = 5.0
        self.azimuth = 0.0  # rotation around vertical
        self.elevation = 30.0  # angle from horizontal
        
        self.view_matrix = None
        self.projection_matrix = None
        self.camera_revision = 0  # Track changes (but don't invalidate mesh)
    
    def orbit(self, delta_azimuth: float, delta_elevation: float) -> None:
        """Rotate around target."""
        self.azimuth += delta_azimuth
        self.elevation += delta_elevation
        self.camera_revision += 1
        self._update_matrices()
    
    def pan(self, delta_x: float, delta_y: float) -> None:
        """Move camera target."""
        self.center = (self.center[0] + delta_x, self.center[1], self.center[2] + delta_y)
        self.camera_revision += 1
        self._update_matrices()
    
    def zoom(self, delta_distance: float) -> None:
        """Move closer/farther."""
        self.distance = max(0.1, self.distance + delta_distance)
        self.camera_revision += 1
        self._update_matrices()
    
    def _update_matrices(self) -> None:
        """Recompute view/projection (no geometry invalidation)."""
        # Compute view matrix from orbit parameters
        # Compute projection matrix
        pass
    
    def project_to_screen(self, pos_3d, screen_width, screen_height):
        """Project 3D position to screen coordinates (for picking)."""
        # Apply view and projection matrices
        pass
    
    def screen_to_ray(self, screen_x, screen_y, screen_width, screen_height):
        """Convert screen click to ray in world space (for picking)."""
        # Unproject screen coordinates to ray
        pass
```

**Acceptance:**
- [ ] Orbit/Pan/Zoom update camera_revision
- [ ] View/Projection matrices correctly computed
- [ ] No geometry-related state changes
- [ ] 5+ camera tests pass

---

### Task 5.6: Integration & Benchmarking

**Duration:** ~3 hours

**File:** `src/viewport/benchmark.py` + `tests/test_viewport_integration.py`

**Benchmark scenarios (from V0.2 Spec §8):**

1. **Camera Orbit (100 frames)**
   - Expected: `geometry_uploads == 0`, `normal_recomputations == 0`
   - Measured: `camera_orbit_time < 2ms` per frame

2. **Vertex Position Update (10 vertices)**
   - Expected: `structural_rebuilds == 0`, only `position_buffer_uploads == 1`
   - Measured: `position_update_time < 5ms`

3. **Selection/Hover**
   - Expected: Base mesh unchanged, only overlay state
   - Measured: `geometry_uploads == 0`

4. **Topology Change (edge split)**
   - Expected: `structural_rebuilds == 1`, `topology_revision++`
   - Measured: `topology_update_time < 20ms`

5. **Stress Test (1000 vertex moves)**
   - Expected: Memory stable, no resource leaks
   - Measured: `peak_memory_resident` constant

**Test file:**

```python
import pytest
from src.viewport import RenderMesh, Picker, SelectionOverlay
from tests.fixtures import reference_mesh  # 326V mesh

class TestViewportBenchmarks:
    
    def test_camera_orbit_no_geometry_upload(reference_mesh):
        """Camera orbit must not trigger geometry updates."""
        render_mesh = RenderMesh(reference_mesh)
        initial_uploads = render_mesh.geometry_uploads
        
        # Simulate 100 orbit frames
        camera = OrbitCamera()
        for _ in range(100):
            camera.orbit(1.0, 0.0)
        
        # Verify: no geometry uploads
        assert render_mesh.geometry_uploads == initial_uploads
    
    def test_vertex_move_partial_update(reference_mesh):
        """Single vertex move should update only affected normals."""
        render_mesh = RenderMesh(reference_mesh)
        initial_uploads = render_mesh.geometry_uploads
        initial_recomputations = render_mesh.normal_recomputations
        
        # Move single vertex
        v_id = list(reference_mesh.all_vertex_ids())[0]
        render_mesh.update_positions({v_id})
        
        # Verify: position upload + partial normal recomputation
        assert render_mesh.geometry_uploads > initial_uploads
        assert render_mesh.normal_recomputations > initial_recomputations
        assert render_mesh.structural_rebuilds == 0
    
    def test_selection_no_base_mesh_invalidation(reference_mesh):
        """Selection overlay must not invalidate base mesh."""
        render_mesh = RenderMesh(reference_mesh)
        overlay = SelectionOverlay()
        
        initial_uploads = render_mesh.geometry_uploads
        
        # Select vertex
        v_id = list(reference_mesh.all_vertex_ids())[0]
        overlay.select('vertex', v_id)
        
        # Verify: base mesh untouched
        assert render_mesh.geometry_uploads == initial_uploads
```

**Acceptance:**
- [ ] Benchmark counters collected and accessible
- [ ] 5+ benchmark scenarios pass
- [ ] Performance baselines recorded (camera < 2ms, etc.)
- [ ] Memory stability verified (stress test)

---

## Gate 5 Acceptance Criteria (Final)

### Structural
- [ ] `src/viewport/` directory created (pure rendering module)
- [ ] No window dependencies in src/viewport/
- [ ] No Application/Tools logic in src/viewport/

### RenderMesh
- [ ] Persistent GPU resource allocation verified
- [ ] Position updates patch buffer (no full rebuild)
- [ ] Topology updates trigger structural rebuild only
- [ ] Dirty-state tracking functional
- [ ] 8+ RenderMesh unit tests pass

### Derived Geometry
- [ ] Incremental normal computation for affected vertices only
- [ ] Bounds caching + invalidation working
- [ ] Adjacency (vertex_to_faces) correct
- [ ] 7+ derived geometry tests pass

### Overlay Selection
- [ ] Selection overlay independent of base mesh
- [ ] Selection changes don't trigger base mesh updates
- [ ] 6+ overlay tests pass

### Picker
- [ ] CPU picking (vertex/edge/face) implemented
- [ ] Threshold-based selection working
- [ ] 8+ picker tests pass

### Camera
- [ ] Orbit/Pan/Zoom update view matrices only
- [ ] camera_revision tracked but doesn't invalidate geometry
- [ ] 5+ camera tests pass

### Benchmarking
- [ ] Counters: geometry_uploads, structural_rebuilds, normal_recomputations, etc.
- [ ] 5 benchmark scenarios pass
- [ ] Baselines recorded (camera < 2ms, vertex drag < 5ms, etc.)
- [ ] Memory stability verified

### Integration
- [ ] Application can instantiate and use Viewport
- [ ] RenderMesh ↔ Picker ↔ Overlay all work together
- [ ] 10+ integration tests pass
- [ ] Full workflow: Camera move → Vertex edit → Selection → Overlay

### Testing
- [ ] 60+ total tests pass (all viewport modules)
- [ ] Coverage ≥ 85% for src/viewport/
- [ ] V0.2 Spec §8 measurement criteria satisfied

### Documentation
- [ ] RenderMesh implementation matches V0.2 Spec §3–7
- [ ] Benchmarking clearly documents what is measured
- [ ] Integration points documented

---

## Known Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Pyglet VertexList patching doesn't work as expected** | Update path fails; full rebuild necessary | Verify pyglet behavior early; test patch before full implementation |
| **Normal recomputation not actually incremental** | Performance not improved over V1 | Benchmark normals_recomputations counter; verify affected-face set is small |
| **GPU sync stalls on buffer patch** | Latency spike despite incremental update | Implement double-buffering if stalls measured in Gate 8 benchmarks |
| **Picker too slow on larger meshes** | Interaction latency > threshold | Defer to later gates; Gate 5 accepts linear scan for reference mesh |
| **Adjacency rebuild expensive after topology change** | Topology operations slow | Optimize if measured; accept for Gate 5 (rarity of topology ops) |

---

## Deliverables Summary

**After Gate 5 complete:**

- `src/viewport/` fully implemented (V0.2 Architecture)
- RenderMesh with persistent GPU resources
- Incremental normal/bounds updates
- CPU Picker (vertex/edge/face)
- Selection Overlay (independent of base)
- 60+ tests passing
- Benchmark counters + baselines recorded
- Ready for Gate 5b (Selection & Display Integration)

**Estimated effort:** 2 work sessions (16 hours)

---

## Prerequisites for Gate 5

- [ ] Gate 3 complete (Application, ToolManager, tools)
- [ ] Gate 4 complete (Interaction routing)
- [ ] V0.2 Architecture spec fully understood
- [ ] Reference mesh (326V) available and loaded

---

**Status:** Ready to implement (after Gate 3 & 4 complete). No blockers identified.

---

## Next: Gate 5b (Selection & Display Integration)

After Gate 5 complete, Gate 5b adds:
- V/E/F selection mode toggle
- Click-to-select with current picker
- Display modes (Shaded/Flat/Wireframe)
- Wireframe overlay toggle
- Move tool integration (respects selection mode)

Gate 5b is 1 session and depends entirely on Gate 5 (Viewport).

---

**End of Gate 5 Implementation Readiness**
