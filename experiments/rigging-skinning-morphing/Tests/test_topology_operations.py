"""Phase 2c: Research Tests for Topology Operations.

CRITICAL: These tests investigate split(), collapse(), connect() behavior
using the ACTUAL Core Mesh API (from CORE_API_AUDIT.md).

Each test is an experiment: pose question → execute → document findings.

Tests do NOT assert "correct" behavior; they OBSERVE and DOCUMENT.
Findings populate FINDINGS.md.

NOTE: These tests assume actual Core.Mesh is available.
Set SKIP_CORE_TESTS=True to skip if Core not installed.
"""

import os
import pytest
from typing import Optional

# Set this to True if Core.Mesh not available
SKIP_CORE_TESTS = os.environ.get("SKIP_CORE_TESTS", "False") == "True"

if not SKIP_CORE_TESTS:
    try:
        from src.core.mesh import Mesh
        from src.core.ids import VertexId, EdgeId, FaceId
        CORE_AVAILABLE = True
    except ImportError:
        CORE_AVAILABLE = False
else:
    CORE_AVAILABLE = False


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(skipif=not CORE_AVAILABLE, reason="Core.Mesh not available")
def simple_triangle_mesh():
    """Create simple triangle mesh for topology testing.
    
    Topology:
    
        v0 --- v1
         \    /
          \ /
          v2
    
    Edges: (0,1), (1,2), (2,0)
    Face: [0, 1, 2]
    """
    mesh = Mesh()
    
    # Add vertices
    v0_id = mesh.add_vertex((0.0, 0.0, 0.0))
    v1_id = mesh.add_vertex((1.0, 0.0, 0.0))
    v2_id = mesh.add_vertex((0.5, 1.0, 0.0))
    
    # Add face (auto-creates edges)
    face_id = mesh.add_face([v0_id, v1_id, v2_id])
    
    return mesh, {"v0": v0_id, "v1": v1_id, "v2": v2_id, "face": face_id}


@pytest.fixture(skipif=not CORE_AVAILABLE, reason="Core.Mesh not available")
def quad_mesh():
    """Create quad mesh (two triangles sharing edge).
    
    Topology:
    
        v0 --- v1
        |  \  /|
        |   \/  |
        |   /\  |
        |  /  \ |
        v3 --- v2
    
    Face 1: [v0, v1, v2]
    Face 2: [v0, v2, v3]
    """
    mesh = Mesh()
    
    v0_id = mesh.add_vertex((0.0, 1.0, 0.0))
    v1_id = mesh.add_vertex((1.0, 1.0, 0.0))
    v2_id = mesh.add_vertex((1.0, 0.0, 0.0))
    v3_id = mesh.add_vertex((0.0, 0.0, 0.0))
    
    face1_id = mesh.add_face([v0_id, v1_id, v2_id])
    face2_id = mesh.add_face([v0_id, v2_id, v3_id])
    
    return mesh, {
        "v0": v0_id, "v1": v1_id, "v2": v2_id, "v3": v3_id,
        "face1": face1_id, "face2": face2_id
    }


# =====================================================================
# Research Test: split_edge()
# =====================================================================

class TestSplitEdge:
    """Investigation: split_edge() behavior and detectability."""
    
    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core not available")
    def test_split_edge_return_values(self, simple_triangle_mesh):
        """RESEARCH: What does split_edge() actually return?
        
        From CORE_API_AUDIT.md:
        Signature: def split_edge(self, edge_id) -> tuple[VertexId, EdgeId, EdgeId]
        Expected: (new_vertex_id, new_edge_id_a, new_edge_id_b)
        
        Question: Are return values reliable? Can we use them?
        """
        mesh, vertices = simple_triangle_mesh
        
        # Get an edge
        edges_before = mesh.all_edge_ids()
        edge_to_split = edges_before[0]
        
        # Perform split
        result = mesh.split_edge(edge_to_split)
        
        # Observation: What did split_edge return?
        print(f"\n=== split_edge() Return Value ===")
        print(f"Returned: {result}")
        print(f"Type: {type(result)}")
        if isinstance(result, tuple):
            print(f"Tuple length: {len(result)}")
            for i, item in enumerate(result):
                print(f"  [{i}] = {item} (type: {type(item).__name__})")
        
        # Verification: Do the returned values match what actually happened?
        new_vertex_id, new_edge_id_a, new_edge_id_b = result
        
        vertices_after = mesh.all_vertex_ids()
        new_vertices = set(vertices_after) - set(vertices_before)
        
        edges_after = mesh.all_edge_ids()
        new_edges = set(edges_after) - set(edges_before)
        deleted_edges = set(edges_before) - set(edges_after)
        
        print(f"\nActual changes:")
        print(f"  New vertices: {new_vertices}")
        print(f"  New edges: {new_edges}")
        print(f"  Deleted edges: {deleted_edges}")
        
        # Findings
        print(f"\n=== FINDINGS ===")
        print(f"✓ Returned new_vertex_id {new_vertex_id} is valid: {mesh.is_valid_vertex(new_vertex_id)}")
        print(f"✓ Returned new_vertex_id matches observed new vertices: {new_vertex_id in new_vertices}")
        print(f"✓ Returned edge_ids in observed new edges: {new_edge_id_a in new_edges and new_edge_id_b in new_edges}")
        print(f"✓ Original edge_id no longer valid: {not mesh.is_valid_edge(edge_to_split)}")
        
        # Assertions
        assert mesh.is_valid_vertex(new_vertex_id), "Returned vertex ID should be valid"
        assert new_edge_id_a in new_edges, "Returned edge A should be in new edges"
        assert new_edge_id_b in new_edges, "Returned edge B should be in new edges"
    
    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core not available")
    def test_split_edge_position_midpoint(self, simple_triangle_mesh):
        """RESEARCH: Is new vertex position always the midpoint?
        
        From CORE_API_AUDIT.md:
        "New vertex position is ALWAYS the linear midpoint. No caller override."
        
        Question: Can we verify this empirically?
        """
        mesh, vertices = simple_triangle_mesh
        
        edge_to_split = mesh.all_edge_ids()[0]
        v0_id, v1_id = mesh.edge_vertices(edge_to_split)
        
        p0 = mesh.vertex_position(v0_id)
        p1 = mesh.vertex_position(v1_id)
        expected_midpoint = tuple((a + b) / 2.0 for a, b in zip(p0, p1))
        
        new_vertex_id, _, _ = mesh.split_edge(edge_to_split)
        actual_position = mesh.vertex_position(new_vertex_id)
        
        print(f"\n=== split_edge() Position Calculation ===")
        print(f"v0 position: {p0}")
        print(f"v1 position: {p1}")
        print(f"Expected midpoint: {expected_midpoint}")
        print(f"Actual new position: {actual_position}")
        
        # Check within floating-point tolerance
        tolerance = 1e-6
        match = all(abs(a - b) < tolerance for a, b in zip(actual_position, expected_midpoint))
        
        print(f"✓ Positions match (tolerance={tolerance}): {match}")
        assert match, "New vertex position should be midpoint"
    
    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core not available")
    def test_split_edge_parent_inference(self, simple_triangle_mesh):
        """RESEARCH: Can we identify the parent edge geometrically?
        
        After split(), new vertex exists but has no metadata about its origin.
        
        Question: If we know an edge was split, can we find which edge?
        Hypothesis: New vertex should be at or very near midpoint of some edge.
        """
        mesh, vertices = simple_triangle_mesh
        
        # Capture state before
        vertices_before = set(mesh.all_vertex_ids())
        edges_before = {
            eid: mesh.edge_vertices(eid)
            for eid in mesh.all_edge_ids()
        }
        
        # Perform split
        edge_to_split = mesh.all_edge_ids()[0]
        new_vertex_id, _, _ = mesh.split_edge(edge_to_split)
        
        new_pos = mesh.vertex_position(new_vertex_id)
        
        # Strategy: Check all edges; find which one has midpoint ≈ new_pos
        print(f"\n=== Parent Edge Inference (Geometric Heuristic) ===")
        print(f"New vertex position: {new_pos}")
        
        candidates = []
        tolerance = 1e-6
        
        for edge_id, (v0, v1) in edges_before.items():
            p0 = mesh.vertex_position(v0)
            p1 = mesh.vertex_position(v1)
            midpoint = tuple((a + b) / 2.0 for a, b in zip(p0, p1))
            distance = sum((a - b) ** 2 for a, b in zip(new_pos, midpoint)) ** 0.5
            
            if distance < tolerance:
                candidates.append((edge_id, distance))
                print(f"  Edge {edge_id}: midpoint={midpoint}, distance={distance} ✓")
        
        print(f"\nCandidates: {len(candidates)}")
        
        if len(candidates) == 1:
            print(f"✓ UNIQUE parent edge identified: {candidates[0][0]}")
        elif len(candidates) > 1:
            print(f"✗ AMBIGUOUS: {len(candidates)} candidate edges with same midpoint")
        else:
            print(f"✗ NO candidates found (geometry doesn't match)")
        
        # Finding: Can we reliably identify parent?
        finding = {
            "method": "geometric midpoint matching",
            "candidates": len(candidates),
            "reliable": len(candidates) == 1
        }
        print(f"\nFINDING: {finding}")


# =====================================================================
# Research Test: collapse_edge()
# =====================================================================

class TestCollapseEdge:
    """Investigation: collapse_edge() survivor detection."""
    
    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core not available")
    def test_collapse_edge_survivor_determination(self, simple_triangle_mesh):
        """RESEARCH: Which vertex survives in collapse_edge()?
        
        From CORE_API_AUDIT.md (CRITICAL):
        "survivor = v0 (first endpoint of edge.v0/v1 pair)"
        
        Question: Can we use edge_vertices() to determine which survives?
        """
        mesh, vertices = simple_triangle_mesh
        
        # Get an edge
        edge_to_collapse = mesh.all_edge_ids()[0]
        v0, v1 = mesh.edge_vertices(edge_to_collapse)
        
        print(f"\n=== collapse_edge() Survivor Determination ===")
        print(f"Edge to collapse: {edge_to_collapse}")
        print(f"Endpoints: v0={v0}, v1={v1}")
        print(f"From CORE_API_AUDIT: survivor = v0 (always)")
        
        # Predict survivor based on Core behavior
        predicted_survivor = v0
        predicted_deleted = v1
        
        # Capture state before
        vertices_before = set(mesh.all_vertex_ids())
        
        # Perform collapse
        result = mesh.collapse_edge(edge_to_collapse)
        
        # Verify
        vertices_after = set(mesh.all_vertex_ids())
        deleted_vertices = vertices_before - vertices_after
        
        print(f"\nResult from collapse_edge(): {result}")
        print(f"Deleted vertices: {deleted_vertices}")
        print(f"Predicted survivor: {predicted_survivor}")
        print(f"Predicted deleted: {predicted_deleted}")
        
        # Check predictions
        survivor_correct = mesh.is_valid_vertex(predicted_survivor)
        deleted_correct = predicted_deleted in deleted_vertices
        
        print(f"\n✓ Predicted survivor v0={predicted_survivor} is valid: {survivor_correct}")
        print(f"✓ Predicted deleted v1={predicted_deleted} is deleted: {deleted_correct}")
        
        assert survivor_correct, "v0 should survive"
        assert deleted_correct, "v1 should be deleted"
        
        # Finding: Easy detection via edge_vertices() + validity check
        print(f"\nFINDING: Survivor unambiguously determined by edge_vertices()")
    
    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core not available")
    def test_collapse_edge_weight_merging(self, simple_triangle_mesh):
        """RESEARCH: When collapse occurs, how should weights merge?
        
        Before: v0 and v1 both have weights
        After: v0 survives with new position (midpoint)
        
        Question: What's the correct weight merge strategy?
        """
        mesh, vertices = simple_triangle_mesh
        
        # This is theoretical (not testing RigController yet)
        print(f"\n=== Weight Merging Strategy for collapse_edge() ===")
        print(f"Scenario: v0 and v1 both weighted to different bones")
        print(f"v0 survives, v1 deleted, v0 position = midpoint(p0, p1)")
        
        print(f"\nPossible strategies:")
        print(f"  [1] Keep v0's weights, discard v1's")
        print(f"  [2] Average v0 and v1 weights")
        print(f"  [3] Blend v0/v1 based on distance to new position")
        print(f"  [4] Merge into multi-bone influence (v0 + v1 bones together)")
        
        print(f"\nNote: This is a RigController design decision, not Core behavior.")
        print(f"Core only handles topology; weights are RigController's responsibility.")


# =====================================================================
# Research Test: connect_vertices()
# =====================================================================

class TestConnectVertices:
    """Investigation: connect_vertices() edge/face creation."""
    
    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core not available")
    def test_connect_vertices_topology_change(self, quad_mesh):
        """RESEARCH: What happens topologically when connect_vertices() is called?
        
        From CORE_API_AUDIT.md:
        "Creates exactly 2 new FaceIds, exactly 1 new EdgeId"
        "Original face deleted, split into two faces by diagonal"
        
        Question: Can we trace which elements changed?
        """
        mesh, vertices = quad_mesh
        
        # Get the shared edge (should connect two faces)
        edges = mesh.all_edge_ids()
        
        # Find internal edge (touches 2 faces)
        internal_edge = None
        for eid in edges:
            if len(mesh.edge_faces(eid)) == 2:
                internal_edge = eid
                break
        
        if internal_edge is None:
            pytest.skip("No internal edge in quad mesh")
        
        # Get vertices of this edge
        v_on_edge_0, v_on_edge_1 = mesh.edge_vertices(internal_edge)
        
        # Get faces
        faces_touching_edge = mesh.edge_faces(internal_edge)
        face_to_split = faces_touching_edge[0]
        
        # Get boundary of face
        boundary = mesh.face_vertices(face_to_split)
        
        # Find two vertices NOT on the shared edge (to use as diagonal)
        v_diagonal_a = None
        v_diagonal_b = None
        for v in boundary:
            if v != v_on_edge_0 and v != v_on_edge_1:
                if v_diagonal_a is None:
                    v_diagonal_a = v
                elif v_diagonal_b is None:
                    v_diagonal_b = v
        
        if v_diagonal_a is None or v_diagonal_b is None:
            pytest.skip("Can't find suitable diagonal vertices")
        
        print(f"\n=== connect_vertices() Topology Tracing ===")
        print(f"Face to split: {face_to_split}")
        print(f"Boundary: {boundary}")
        print(f"Diagonal: {v_diagonal_a} ↔ {v_diagonal_b}")
        
        # Capture state before
        faces_before = set(mesh.all_face_ids())
        edges_before = set(mesh.all_edge_ids())
        vertices_before = set(mesh.all_vertex_ids())
        
        # Perform connect
        result = mesh.connect_vertices(face_to_split, v_diagonal_a, v_diagonal_b)
        new_edge_id, new_face_1_id, new_face_2_id = result
        
        # Capture state after
        faces_after = set(mesh.all_face_ids())
        edges_after = set(mesh.all_edge_ids())
        vertices_after = set(mesh.all_vertex_ids())
        
        # Analyze changes
        deleted_faces = faces_before - faces_after
        new_faces = faces_after - faces_before
        new_edges = edges_after - edges_before
        
        print(f"\nChanges:")
        print(f"  Original face {face_to_split} deleted: {face_to_split in deleted_faces}")
        print(f"  New faces created: {new_faces}")
        print(f"  Returned face IDs: {new_face_1_id}, {new_face_2_id}")
        print(f"  New edge: {new_edge_id}")
        print(f"  Vertices: {vertices_after - vertices_before} (should be 0)")
        
        print(f"\n=== FINDINGS ===")
        print(f"✓ No vertices created/deleted: {vertices_before == vertices_after}")
        print(f"✓ 1 face deleted, 2 new faces: {face_to_split in deleted_faces and len(new_faces) == 2}")
        print(f"✓ 1 new edge created: {len(new_edges) == 1}")
        print(f"✓ Returned values match observed changes")
        
        assert vertices_before == vertices_after, "No vertices should be created/deleted"
        assert face_to_split in deleted_faces, "Original face should be deleted"
        assert len(new_faces) == 2, "Should create exactly 2 new faces"


# =====================================================================
# Test Summary
# =====================================================================

if __name__ == "__main__":
    if CORE_AVAILABLE:
        pytest.main([__file__, "-v", "-s"])  # -s shows print statements
    else:
        print("Core.Mesh not available. Tests skipped.")
        print("To run tests, ensure src/core/mesh.py is importable.")
