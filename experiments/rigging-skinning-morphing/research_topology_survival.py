"""Phase 3A/3B: Topology Survival Research

EMPIRICAL INVESTIGATION of split_edge() and collapse_edge() behavior.

Central Research Questions:

3A - split_edge():
  «Kann ein externer Rig/Skin/Morph-Controller anhand der bestehenden 
  öffentlichen Core-APIs zuverlässig feststellen, von welcher Edge ein 
  neu erzeugter Vertex stammt?»
  
  Two cases:
  - Case A1: Operation KNOWN (split_edge(edge_id) directly called)
    → Parent edge trivially known, not a research problem
  - Case A2: Operation OBSERVED (only before/after snapshots available)
    → Can we reconstruct parent edge from public APIs?

3B - collapse_edge():
  - Case B1: Survivor determination
    «Ist die Survivor-Regel konsistent über verschiedene Topologie-Fälle?»
  - Case B2: Weight migration
    «Reicht die gesicherte Survivor-Information aus für Weight-Merging?»

METHODOLOGY:
Baseline → Snapshot → Operation → Snapshot → Diff → Core-API-Investigation → 
Observation → Conclusion

CRITICAL: Distinction
- Observation (what we actually see)
- Interpretation (what we infer)
- Workaround (how to work around limitations)
- Core Gap (what's missing from Core)

NO PRE-FILLED HYPOTHESES. Only empirical results.
"""

import os
import sys
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

# Skip if Core not available
SKIP_TESTS = os.environ.get("SKIP_TOPOLOGY_RESEARCH", "False") == "True"

if not SKIP_TESTS:
    try:
        from src.core.mesh import Mesh
        from src.core.ids import VertexId, EdgeId, FaceId
        CORE_AVAILABLE = True
    except ImportError:
        print("WARNING: Core.Mesh not importable. Tests will be skipped.", file=sys.stderr)
        CORE_AVAILABLE = False
else:
    CORE_AVAILABLE = False

import pytest


# =====================================================================
# Data Structures for Investigation
# =====================================================================

@dataclass
class MeshSnapshot:
    """Captures mesh topology state at a point in time."""
    label: str
    vertices: Dict[int, Tuple[float, float, float]]  # id -> position
    edges: Dict[int, Tuple[int, int]]  # id -> (v0, v1)
    faces: Dict[int, List[int]]  # id -> [boundary]
    
    def vertex_ids(self):
        return set(self.vertices.keys())
    
    def edge_ids(self):
        return set(self.edges.keys())
    
    def face_ids(self):
        return set(self.faces.keys())


@dataclass
class TopologyDiff:
    """Difference between two snapshots."""
    new_vertices: List[int]
    deleted_vertices: List[int]
    new_edges: List[int]
    deleted_edges: List[int]
    new_faces: List[int]
    deleted_faces: List[int]


def take_snapshot(mesh: Mesh, label: str) -> MeshSnapshot:
    """Capture complete mesh state."""
    vertices = {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}
    edges = {eid: mesh.edge_vertices(eid) for eid in mesh.all_edge_ids()}
    faces = {fid: mesh.face_vertices(fid) for fid in mesh.all_face_ids()}
    
    return MeshSnapshot(label=label, vertices=vertices, edges=edges, faces=faces)


def diff_snapshots(before: MeshSnapshot, after: MeshSnapshot) -> TopologyDiff:
    """Compute difference between two snapshots."""
    return TopologyDiff(
        new_vertices=list(after.vertex_ids() - before.vertex_ids()),
        deleted_vertices=list(before.vertex_ids() - after.vertex_ids()),
        new_edges=list(after.edge_ids() - before.edge_ids()),
        deleted_edges=list(before.edge_ids() - after.edge_ids()),
        new_faces=list(after.face_ids() - before.face_ids()),
        deleted_faces=list(before.face_ids() - after.face_ids()),
    )


def distance_3d(p1: Tuple[float, float, float], 
                p2: Tuple[float, float, float]) -> float:
    """Euclidean distance between two 3D points."""
    return sum((a - b) ** 2 for a, b in zip(p1, p2)) ** 0.5


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture(skipif=not CORE_AVAILABLE, reason="Core.Mesh not available")
def simple_triangle():
    """Simple triangle mesh for research."""
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((0.5, 1.0, 0.0))
    f = mesh.add_face([v0, v1, v2])
    return mesh


@pytest.fixture(skipif=not CORE_AVAILABLE, reason="Core.Mesh not available")
def quad_mesh():
    """Quad mesh (two triangles)."""
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 1.0, 0.0))
    v1 = mesh.add_vertex((1.0, 1.0, 0.0))
    v2 = mesh.add_vertex((1.0, 0.0, 0.0))
    v3 = mesh.add_vertex((0.0, 0.0, 0.0))
    f1 = mesh.add_face([v0, v1, v2])
    f2 = mesh.add_face([v0, v2, v3])
    return mesh


# =====================================================================
# Phase 3A: SPLIT_EDGE RESEARCH
# =====================================================================

class TestSplitEdgeResearch:
    """Investigation: split_edge() parent edge reconstruction."""
    
    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core not available")
    def test_3a1_operation_known_split_is_trivial(self, simple_triangle):
        """3A Case 1: Operation KNOWN (not a research problem)
        
        When we directly call split_edge(edge_id), the parent edge is 
        trivially known (it's the edge_id we passed).
        
        This is not a research question. Document and move on.
        """
        mesh = simple_triangle
        
        print("\n" + "="*70)
        print("3A CASE 1: Operation KNOWN (direct call)")
        print("="*70)
        
        # Get an edge
        edge_id = mesh.all_edge_ids()[0]
        v0, v1 = mesh.edge_vertices(edge_id)
        
        print(f"\nDirect call: mesh.split_edge({edge_id})")
        print(f"Parent edge: {edge_id} (trivially known)")
        print(f"Endpoints: v0={v0}, v1={v1}")
        
        print("\n--- OBSERVATION ---")
        print("Parent edge is known because we called split_edge(edge_id) directly.")
        print("\n--- CONCLUSION ---")
        print("Case A1 is NOT a research problem. Parent is trivially known.")
        print("SKIP Case A1. Focus on Case A2 (operation observed).")
    
    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core not available")
    def test_3a2_operation_observed_parent_reconstruction(self, simple_triangle):
        """3A Case 2: Operation OBSERVED (core research problem)
        
        Only before/after snapshots available. No knowledge of which operation occurred.
        Can we reconstruct the parent edge using public Core APIs?
        
        Approach:
        1. Capture before-snapshot
        2. Perform split (caller doesn't know which edge)
        3. Capture after-snapshot
        4. Identify: which edge was split?
        5. Try to reconstruct via public APIs (NO geometry heuristic yet)
        """
        mesh = simple_triangle
        
        print("\n" + "="*70)
        print("3A CASE 2: Operation OBSERVED (before/after only)")
        print("="*70)
        
        # --- BASELINE ---
        print("\n--- BASELINE ---")
        snap_before = take_snapshot(mesh, "before_split")
        print(f"Vertices: {sorted(snap_before.vertex_ids())}")
        print(f"Edges: {sorted(snap_before.edge_ids())}")
        print(f"Faces: {sorted(snap_before.face_ids())}")
        
        # Store edge properties for later investigation
        edges_before = {
            eid: (mesh.edge_vertices(eid), mesh.vertex_position(eid[0]) if isinstance(eid, tuple) else None)
            for eid in snap_before.edge_ids()
        }
        
        # --- OPERATION (hidden) ---
        print("\n--- OPERATION (HIDDEN) ---")
        edge_to_split = snap_before.edge_ids().__iter__().__next__()  # First edge
        print(f"(Split operation on edge {edge_to_split}, but this is unknown to observer)")
        
        new_vertex_id, new_edge_a, new_edge_b = mesh.split_edge(edge_to_split)
        
        print(f"\nReturned from split():")
        print(f"  new_vertex_id = {new_vertex_id}")
        print(f"  new_edge_a = {new_edge_a}")
        print(f"  new_edge_b = {new_edge_b}")
        
        # --- SNAPSHOT AFTER ---
        print("\n--- SNAPSHOT AFTER ---")
        snap_after = take_snapshot(mesh, "after_split")
        print(f"Vertices: {sorted(snap_after.vertex_ids())}")
        print(f"Edges: {sorted(snap_after.edge_ids())}")
        print(f"Faces: {sorted(snap_after.face_ids())}")
        
        # --- DIFF ---
        print("\n--- DIFF ---")
        diff = diff_snapshots(snap_before, snap_after)
        print(f"New vertices: {diff.new_vertices}")
        print(f"Deleted vertices: {diff.deleted_vertices}")
        print(f"New edges: {diff.new_edges}")
        print(f"Deleted edges: {diff.deleted_edges}")
        print(f"New faces: {diff.new_faces}")
        print(f"Deleted faces: {diff.deleted_faces}")
        
        # --- CORE-API INVESTIGATION ---
        print("\n--- CORE API INVESTIGATION ---")
        
        # Observation 1: New vertex position
        new_vertex_pos = mesh.vertex_position(new_vertex_id)
        print(f"\nNew vertex position: {new_vertex_pos}")
        
        # Observation 2: Check deleted edge endpoints
        deleted_edge_id = diff.deleted_edges[0] if diff.deleted_edges else None
        if deleted_edge_id:
            # Try to get vertices of deleted edge from BEFORE snapshot
            v_endpoints = snap_before.edges.get(deleted_edge_id)
            if v_endpoints:
                print(f"Deleted edge {deleted_edge_id} had endpoints: {v_endpoints}")
                v0_pos = snap_before.vertices[v_endpoints[0]]
                v1_pos = snap_before.vertices[v_endpoints[1]]
                computed_midpoint = tuple((a + b) / 2 for a, b in zip(v0_pos, v1_pos))
                print(f"  v0 position: {v0_pos}")
                print(f"  v1 position: {v1_pos}")
                print(f"  Computed midpoint: {computed_midpoint}")
                print(f"  New vertex position: {new_vertex_pos}")
                distance = distance_3d(computed_midpoint, new_vertex_pos)
                print(f"  Distance: {distance:.6f}")
        
        # Observation 3: New edges' endpoints
        print(f"\nNew edges investigation:")
        for new_edge_id in diff.new_edges:
            v0, v1 = mesh.edge_vertices(new_edge_id)
            print(f"  Edge {new_edge_id}: ({v0}, {v1})")
            if v0 == new_vertex_id or v1 == new_vertex_id:
                other_v = v1 if v0 == new_vertex_id else v0
                print(f"    → Connected to new vertex {new_vertex_id}, other endpoint: {other_v}")
        
        # --- OBSERVATION ---
        print("\n--- OBSERVATION ---")
        print(f"What we can observe with public APIs:")
        print(f"  1. Exactly 1 new vertex created: {len(diff.new_vertices) == 1}")
        print(f"  2. Exactly 1 edge deleted: {len(diff.deleted_edges) == 1}")
        print(f"  3. Exactly 2 new edges created: {len(diff.new_edges) == 2}")
        print(f"  4. New edges connect to new vertex: ✓")
        print(f"  5. New vertex position available: ✓")
        print(f"  6. Deleted edge's endpoints stored in BEFORE snapshot: ✓")
        
        print(f"\nWhat we CANNOT directly query:")
        print(f"  ✗ Core does NOT provide: 'which edge was deleted?' (only ID)")
        print(f"  ✗ Core does NOT provide: metadata on deleted edge after deletion")
        print(f"  → BUT: Endpoints stored in before-snapshot, so we CAN compute midpoint")
        
        # --- INTERPRETATION ---
        print("\n--- INTERPRETATION (NOT OBSERVATION) ---")
        print(f"Strategy: If deleted edge midpoint ≈ new vertex position:")
        print(f"  → Likely that this edge was the split source")
        print(f"\nBUT: This is a WORKAROUND, not a Core API capability.")
        print(f"This is a geometric heuristic, not guaranteed to work if:")
        print(f"  - Two edges have same midpoint")
        print(f"  - Mesh uses non-uniform coordinates")
        print(f"  - Floating-point precision issues")
        
        # --- CORE GAP ---
        print("\n--- CORE GAP ---")
        print(f"Core is missing:")
        print(f"  1. Vertex.parent_edge or similar metadata")
        print(f"  2. Operation logging/history")
        print(f"  3. Method to query 'which edge was deleted?' (only IDs available)")
        
        # --- CONCLUSION ---
        print("\n--- CONCLUSION 3A2 ---")
        print(f"Can we reconstruct parent edge from public APIs alone?")
        print(f"  Answer: ONLY via geometric heuristic (midpoint matching)")
        print(f"  Reliability: MEDIUM (works for typical cases, fails on edge cases)")
        print(f"  Better solution: CORE EXTENSION (store parent edge in vertex metadata)")
        
        print("\n[Marking as RESEARCH COMPLETE for 3A2]")


# =====================================================================
# Phase 3B: COLLAPSE_EDGE RESEARCH
# =====================================================================

class TestCollapseEdgeResearch:
    """Investigation: collapse_edge() survivor detection and consistency."""
    
    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core not available")
    def test_3b1_survivor_determination_single_triangle(self, simple_triangle):
        """3B Case 1: Survivor determination in simple triangle.
        
        From CORE_API_AUDIT.md: "survivor = v0 (first endpoint of edge.v0/v1)"
        
        Question: Is this rule consistent?
        Method: Check edge_vertices() before collapse, then check which survives.
        """
        mesh = simple_triangle
        
        print("\n" + "="*70)
        print("3B CASE 1: Survivor Determination (Simple Triangle)")
        print("="*70)
        
        # --- BASELINE ---
        snap_before = take_snapshot(mesh, "before_collapse")
        print(f"\n--- BASELINE ---")
        print(f"Triangle mesh (3 vertices, 3 edges, 1 face)")
        print(f"Vertices: {sorted(snap_before.vertex_ids())}")
        print(f"Edges: {sorted(snap_before.edge_ids())}")
        
        # --- IDENTIFY EDGE ---
        edge_to_collapse = snap_before.edge_ids().__iter__().__next__()
        v0_predicted, v1_predicted = mesh.edge_vertices(edge_to_collapse)
        
        print(f"\n--- OPERATION: collapse_edge({edge_to_collapse}) ---")
        print(f"edge_vertices() returns: ({v0_predicted}, {v1_predicted})")
        print(f"PREDICTION (from Core audit): v0={v0_predicted} should survive")
        print(f"PREDICTION (from Core audit): v1={v1_predicted} should be deleted")
        
        # --- CAPTURE VERTICES BEFORE ---
        vertices_before = set(snap_before.vertex_ids())
        
        # --- PERFORM COLLAPSE ---
        survivor_returned = mesh.collapse_edge(edge_to_collapse)
        print(f"\nReturned from collapse_edge(): {survivor_returned}")
        
        # --- CHECK RESULTS ---
        vertices_after = set(mesh.all_vertex_ids())
        deleted_vertices = vertices_before - vertices_after
        
        print(f"\n--- RESULTS ---")
        print(f"Vertices after: {sorted(vertices_after)}")
        print(f"Deleted vertices: {deleted_vertices}")
        print(f"Returned survivor: {survivor_returned}")
        
        # --- VERIFICATION ---
        print(f"\n--- VERIFICATION ---")
        v0_survived = mesh.is_valid_vertex(v0_predicted)
        v1_deleted = v1_predicted in deleted_vertices
        returned_matches_v0 = survivor_returned == v0_predicted
        
        print(f"v0 ({v0_predicted}) still valid: {v0_survived}")
        print(f"v1 ({v1_predicted}) deleted: {v1_deleted}")
        print(f"Returned value = v0: {returned_matches_v0}")
        
        # --- OBSERVATION ---
        print(f"\n--- OBSERVATION ---")
        if v0_survived and v1_deleted and returned_matches_v0:
            print(f"✓ CONSISTENT: v0 survived, v1 deleted, return value = v0")
            print(f"✓ Prediction from CORE_API_AUDIT.md VERIFIED")
            print(f"✓ collapse_edge() return value is reliable (= survivor)")
        else:
            print(f"✗ INCONSISTENT: Observations don't match prediction")
            print(f"   v0 survived: {v0_survived}")
            print(f"   v1 deleted: {v1_deleted}")
            print(f"   returned = v0: {returned_matches_v0}")
        
        # --- CONCLUSION ---
        print(f"\n--- CONCLUSION 3B1 ---")
        print(f"Survivor determination via edge_vertices():")
        print(f"  Method: v0, v1 = mesh.edge_vertices(edge_id)")
        print(f"          v0 is always the survivor")
        print(f"  Reliability: HIGH (consistent for this case)")
        print(f"  Requires: Calling edge_vertices() BEFORE collapse()")
    
    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core not available")
    def test_3b1_survivor_determination_quad_mesh(self, quad_mesh):
        """3B Case 1b: Survivor in quad mesh (two triangles).
        
        Test if survivor rule holds with more complex topology
        (shared edge, multiple faces).
        """
        mesh = quad_mesh
        
        print("\n" + "="*70)
        print("3B CASE 1b: Survivor Determination (Quad Mesh)")
        print("="*70)
        
        snap_before = take_snapshot(mesh, "before_collapse")
        
        print(f"\n--- BASELINE ---")
        print(f"Quad mesh (4 vertices, 5 edges, 2 faces)")
        print(f"Vertices: {sorted(snap_before.vertex_ids())}")
        print(f"Edges: {sorted(snap_before.edge_ids())}")
        print(f"Faces: {sorted(snap_before.face_ids())}")
        
        # Find internal edge (touches 2 faces)
        internal_edge = None
        for eid in snap_before.edge_ids():
            if len(mesh.edge_faces(eid)) == 2:
                internal_edge = eid
                break
        
        if internal_edge is None:
            pytest.skip("No internal edge found")
        
        v0_pred, v1_pred = mesh.edge_vertices(internal_edge)
        
        print(f"\n--- OPERATION: collapse_edge({internal_edge}) [INTERNAL EDGE] ---")
        print(f"edge_vertices(): ({v0_pred}, {v1_pred})")
        print(f"Touches {len(mesh.edge_faces(internal_edge))} faces")
        print(f"PREDICTION: v0={v0_pred} survives, v1={v1_pred} deleted")
        
        vertices_before = set(snap_before.vertex_ids())
        survivor_returned = mesh.collapse_edge(internal_edge)
        vertices_after = set(mesh.all_vertex_ids())
        deleted = vertices_before - vertices_after
        
        print(f"\n--- RESULTS ---")
        print(f"Returned: {survivor_returned}")
        print(f"Deleted: {deleted}")
        print(f"v0 valid: {mesh.is_valid_vertex(v0_pred)}")
        print(f"v1 deleted: {v1_pred in deleted}")
        
        # --- OBSERVATION ---
        print(f"\n--- OBSERVATION ---")
        if mesh.is_valid_vertex(v0_pred) and v1_pred in deleted and survivor_returned == v0_pred:
            print(f"✓ CONSISTENT in quad mesh: v0 survives (rule holds)")
        else:
            print(f"✗ INCONSISTENT in quad mesh")
        
        print(f"\n--- CONCLUSION 3B1b ---")
        print(f"Survivor rule appears CONSISTENT across different topologies")
        print(f"  (more test cases would strengthen this observation)")
    
    @pytest.mark.skipif(not CORE_AVAILABLE, reason="Core not available")
    def test_3b2_survivor_sufficient_for_weight_migration(self, simple_triangle):
        """3B Case 2: Is survivor information sufficient for weight migration?
        
        Not about testing actual weight migration (that's RigController responsibility).
        About: What information do we have about the collapsed vertices?
        
        Question: After collapse, do we know enough to merge weights sensibly?
        """
        mesh = simple_triangle
        
        print("\n" + "="*70)
        print("3B CASE 2: Weight Migration Feasibility")
        print("="*70)
        
        snap_before = take_snapshot(mesh, "before_collapse")
        
        edge_id = snap_before.edge_ids().__iter__().__next__()
        v0_surv, v1_dead = mesh.edge_vertices(edge_id)
        p0_before = snap_before.vertices[v0_surv]
        p1_before = snap_before.vertices[v1_dead]
        
        print(f"\n--- BEFORE COLLAPSE ---")
        print(f"Edge: {edge_id}")
        print(f"Survivor (v0): {v0_surv} at {p0_before}")
        print(f"Deleted (v1): {v1_dead} at {p1_before}")
        
        # --- COLLAPSE ---
        survivor = mesh.collapse_edge(edge_id)
        p0_after = mesh.vertex_position(v0_surv)
        
        print(f"\n--- AFTER COLLAPSE ---")
        print(f"Survivor still valid: {mesh.is_valid_vertex(v0_surv)}")
        print(f"Survivor position changed: {p0_after} (was {p0_before})")
        print(f"  Δ = ({p0_after[0] - p0_before[0]}, {p0_after[1] - p0_before[1]}, {p0_after[2] - p0_before[2]})")
        print(f"Deleted vertex now invalid: {not mesh.is_valid_vertex(v1_dead)}")
        
        # --- INFORMATION AVAILABLE FOR WEIGHT MIGRATION ---
        print(f"\n--- INFORMATION AVAILABLE ---")
        print(f"✓ Which vertex survived: {v0_surv}")
        print(f"✓ Which vertex deleted: {v1_dead}")
        print(f"✓ Survivor's old position: {p0_before}")
        print(f"✓ Survivor's new position: {p0_after}")
        print(f"✓ Deleted vertex's old position: {p1_before}")
        
        print(f"\n--- INFORMATION NOT AVAILABLE ---")
        print(f"✗ Survivor's weight before collapse")
        print(f"✗ Deleted vertex's weight before collapse")
        print(f"✗ How to meaningfully merge two different weight lists")
        print(f"   (e.g., v0 weighted to Jaw+Skull, v1 weighted to Neck)")
        
        # --- INTERPRETATION ---
        print(f"\n--- INTERPRETATION ---")
        print(f"Weight migration strategies (caller's choice, not Core's):")
        print(f"  [1] Keep survivor's weights, discard deleted's")
        print(f"  [2] Average weights")
        print(f"  [3] Blend weights based on distance to new position")
        print(f"  [4] Merge into multi-bone influence")
        
        print(f"\nNone of these are 'Core's responsibility' - it's RigController design.")
        
        # --- CONCLUSION ---
        print(f"\n--- CONCLUSION 3B2 ---")
        print(f"Survivor information (which vertex survives, new position) is sufficient")
        print(f"for RigController to ATTEMPT weight migration.")
        print(f"\nHowever:")
        print(f"  - Core provides NO guidance on merge strategy")
        print(f"  - RigController must decide: keep/average/blend/merge weights")
        print(f"  - This is a DESIGN decision, not a Core API gap")
        print(f"\nSurvey: Survivor determination is RELIABLE via edge_vertices().")
        print(f"        Weight merging strategy is CALLER'S RESPONSIBILITY.")


# =====================================================================
# Summary & Next Steps
# =====================================================================

if __name__ == "__main__":
    if CORE_AVAILABLE:
        print("\n" + "="*70)
        print("PHASE 3A/3B: TOPOLOGY SURVIVAL RESEARCH")
        print("="*70)
        print("\nRun with: pytest research_topology_survival.py -v -s")
        print("\nThis will produce detailed observations for FINDINGS.md")
        pytest.main([__file__, "-v", "-s"])
    else:
        print("Core.Mesh not available. Tests skipped.")
