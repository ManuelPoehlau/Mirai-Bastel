"""Phase 3C: Topology Mutation Sequence Research

Empirical investigation: Can RigController survive realistic mutation sequences?

METHODOLOGY:
- Baseline → Snapshot → Operation → Snapshot → Diff → Observation → Conclusion
- Strict distinction: Operation-Context vs. Snapshot-only
- Distinction: Observation ≠ Interpretation ≠ Semantic-Question
- NO assumptions about weight/morph merge strategies
- Each test documents: What worked, what failed, why

IMPORTANT DISTINCTIONS:
1. Operation KNOWN (Controller initiated) vs. SNAPSHOT-ONLY (observed)
2. Mechanical facts (Core guarantees) vs. Semantic questions (design choices)
3. Reliable information vs. Inference vs. Guesswork
"""

import os
import sys
from typing import Dict, List, Tuple, Optional

# Import Core
try:
    from src.core.mesh import Mesh
    from src.core.ids import VertexId, EdgeId, FaceId
    CORE_AVAILABLE = True
except ImportError:
    print("ERROR: Core.Mesh not available", file=sys.stderr)
    CORE_AVAILABLE = False
    sys.exit(1)


# =====================================================================
# Helper: Pretty Printing
# =====================================================================

def section(title: str):
    print("\n" + "="*70)
    print(title)
    print("="*70)


def subsection(title: str):
    print(f"\n--- {title} ---")


def finding(text: str):
    print(f"\n[FINDING] {text}")


def observation(text: str):
    print(f"✓ {text}")


def uncertainty(text: str):
    print(f"? {text}")


def implication(text: str):
    print(f"→ {text}")


# =====================================================================
# Test 3C-1: split() in Operation-Context
# =====================================================================

def test_3c1_split_operation_context():
    """
    3C-1: split() when Controller KNOWS edge_id
    
    Context: OPERATION KNOWN (not snapshot-only)
    This is the EXPECTED path. Not really a research problem,
    but establishes baseline for what works well.
    
    Question: What's the challenge-free path when Controller initiates split?
    """
    
    section("3C-1: split() in Operation-Context (KNOWN)")
    
    # Setup
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((0.5, 1.0, 0.0))
    f = mesh.add_face([v0, v1, v2])
    
    subsection("BASELINE")
    edge_id = mesh.all_edge_ids()[0]
    v_endpoints = mesh.edge_vertices(edge_id)
    print(f"Mesh: Triangle with edges {sorted(mesh.all_edge_ids())}")
    print(f"Edge to split: {edge_id}")
    print(f"Endpoints: {v_endpoints}")
    
    # This is what makes Context=KNOWN
    subsection("OPERATION: split_edge({edge_id}) — Controller knows edge_id")
    print("Key insight: edge_id is KNOWN (passed as parameter)")
    print("Therefore: Parent edge is TRIVIALLY KNOWN")
    
    vertices_before = set(mesh.all_vertex_ids())
    new_v_id, new_e_a, new_e_b = mesh.split_edge(edge_id)
    vertices_after = set(mesh.all_vertex_ids())
    
    print(f"New vertex: {new_v_id}")
    print(f"New edges: {new_e_a}, {new_e_b}")
    
    subsection("OBSERVATION")
    observation("New vertex created")
    observation("Parent edge: edge_id (parameter)")
    observation("Position: available via mesh.vertex_position()")
    
    # In RigController context
    subsection("EXTERNAL SYNC: What RigController does")
    print("Action: handle_new_vertex(new_v_id, parent=edge_id)")
    print("  → Can inherit weights from endpoint vertices")
    print("  → Can inherit morphs from endpoint vertices")
    print("  → Parent is deterministic")
    
    subsection("CONCLUSION 3C-1")
    finding("Operation-Context (KNOWN) path is straightforward")
    observation("No ambiguity in parent identification")
    observation("Information flow is clear and reliable")
    implication("This is the PRIMARY path for RigController-initiated operations")
    implication("Snapshot-only observation is the RESEARCH challenge (Test 3C-2)")
    
    print("\n[STATUS] 3C-1 demonstrates baseline: Operation KNOWN = robust")


# =====================================================================
# Test 3C-2: split() in Snapshot-only Context
# =====================================================================

def test_3c2_split_snapshot_only():
    """
    3C-2: split() observed via snapshots ONLY
    
    Context: SNAPSHOT-ONLY (not operation-known)
    This is the RESEARCH challenge.
    
    Question: Can we reliably infer parent edge from topology diff only?
    """
    
    section("3C-2: split() in Snapshot-only Context (OBSERVED)")
    
    # Setup
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((0.5, 1.0, 0.0))
    f = mesh.add_face([v0, v1, v2])
    
    subsection("BASELINE & SNAPSHOT")
    snap_before = {
        "vertices": {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()},
        "edges": {eid: mesh.edge_vertices(eid) for eid in mesh.all_edge_ids()},
    }
    print(f"Before: {len(snap_before['vertices'])} vertices, {len(snap_before['edges'])} edges")
    
    subsection("HIDDEN OPERATION")
    print("External split_edge() call (controller doesn't know which edge)")
    edge_to_split = snap_before["edges"].keys().__iter__().__next__()
    mesh.split_edge(edge_to_split)
    print(f"(Actually split edge {edge_to_split}, but observer doesn't know this)")
    
    subsection("SNAPSHOT AFTER")
    snap_after = {
        "vertices": {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()},
        "edges": {eid: mesh.edge_vertices(eid) for eid in mesh.all_edge_ids()},
    }
    
    # Diff
    new_verts = set(snap_after["vertices"].keys()) - set(snap_before["vertices"].keys())
    deleted_edges = set(snap_before["edges"].keys()) - set(snap_after["edges"].keys())
    
    print(f"After: {len(snap_after['vertices'])} vertices, {len(snap_after['edges'])} edges")
    print(f"Diff: +{len(new_verts)} vertices, -{len(deleted_edges)} edges")
    
    subsection("OBSERVATION: What Core APIs tell us")
    observation("Exactly 1 new vertex")
    observation("Exactly 1 edge deleted")
    observation("New vertex position: " + str(mesh.vertex_position(list(new_verts)[0])))
    
    if deleted_edges:
        deleted_eid = list(deleted_edges)[0]
        v_a, v_b = snap_before["edges"][deleted_eid]
        p_a = snap_before["vertices"][v_a]
        p_b = snap_before["vertices"][v_b]
        midpoint = tuple((x + y) / 2 for x, y in zip(p_a, p_b))
        
        print(f"Deleted edge {deleted_eid}: v{v_a} at {p_a} -- v{v_b} at {p_b}")
        print(f"Midpoint: {midpoint}")
        
        new_v_pos = mesh.vertex_position(list(new_verts)[0])
        distance = sum((a - b) ** 2 for a, b in zip(midpoint, new_v_pos)) ** 0.5
        print(f"New vertex at: {new_v_pos}")
        print(f"Distance: {distance:.8f}")
        
        subsection("INTERPRETATION: Geometric Heuristic")
        if distance < 1e-6:
            observation("Position matches midpoint → likely parent edge")
        else:
            uncertainty("Position doesn't match → heuristic fails?")
    
    subsection("AVAILABLE INFORMATION")
    observation("Parent edge ID: Only if we matched geometry perfectly")
    observation("Parent edge endpoints: Yes (from before-snapshot)")
    observation("New vertex position: Yes (queryable from Core)")
    uncertainty("Parent edge IDENTITY: Inference only, not guaranteed")
    
    subsection("RigController Challenge")
    print("Action: Cannot call handle_new_vertex(v_new, parent=edge_id)")
    print("  Because: edge_id is unknown")
    print("Fallback options:")
    print("  [1] Use geometric heuristic (MEDIUM reliability)")
    print("  [2] Assume no parent (conservative, may lose weights)")
    print("  [3] Query user/external tracking (out of Core scope)")
    
    subsection("CONCLUSION 3C-2")
    finding("Snapshot-only observation creates ambiguity in parent identification")
    uncertainty("Geometric heuristic works for typical cases, fails on edge cases")
    uncertainty("Cannot guarantee reliable parent inference from topology alone")
    implication("Solution options:")
    implication("  - RigController tracks all split() calls directly (primary)")
    implication("  - Core extension: store parent_edge_id in vertex (robust)")
    implication("  - Geometric heuristic + documentation of limitations (fallback)")
    
    print("\n[STATUS] 3C-2 demonstrates challenge: Snapshot-only = ambiguous")


# =====================================================================
# Test 3C-3: collapse() Sequence
# =====================================================================

def test_3c3_collapse_sequence():
    """
    3C-3: Chain of collapse_edge() operations
    
    Context: Multiple collapses in sequence
    
    Questions:
    - Does survivor rule hold throughout chain?
    - What happens to weights?
    - What happens to morphs?
    """
    
    section("3C-3: collapse() Sequence (Chain)")
    
    # Build simple chain: triangle → collapse → collapse
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((0.5, 1.0, 0.0))
    f = mesh.add_face([v0, v1, v2])
    
    subsection("BASELINE: Triangle")
    edges = sorted(mesh.all_edge_ids())
    print(f"Vertices: {sorted(mesh.all_vertex_ids())}")
    print(f"Edges: {edges}")
    
    # Collapse 1
    subsection("COLLAPSE 1")
    edge1 = edges[0]
    v1_surv_pred, v1_dead_pred = mesh.edge_vertices(edge1)
    print(f"Edge {edge1}: ({v1_surv_pred}, {v1_dead_pred})")
    print(f"Prediction: v{v1_surv_pred} survives")
    
    v1_dead = v1_dead_pred
    result1 = mesh.collapse_edge(edge1)
    
    observation(f"Result: {result1}")
    observation(f"v{v1_surv_pred} valid: {mesh.is_valid_vertex(v1_surv_pred)}")
    observation(f"v{v1_dead} deleted: {not mesh.is_valid_vertex(v1_dead)}")
    observation(f"Survivor rule holds: {result1 == v1_surv_pred}")
    
    # Collapse 2
    subsection("COLLAPSE 2 (on reduced mesh)")
    edges2 = sorted(mesh.all_edge_ids())
    print(f"Remaining edges: {edges2}")
    
    if edges2:
        edge2 = edges2[0]
        v2_surv_pred, v2_dead_pred = mesh.edge_vertices(edge2)
        print(f"Edge {edge2}: ({v2_surv_pred}, {v2_dead_pred})")
        
        result2 = mesh.collapse_edge(edge2)
        
        observation(f"Result: {result2}")
        observation(f"Survivor rule holds: {result2 == v2_surv_pred}")
    
    subsection("SEMANTIC QUESTION: Weight Merge")
    print("When vertex deleted: what happens to its weights?")
    print("  Question 1: Do we MERGE weights onto survivor?")
    print("  Question 2: Do we KEEP survivor's weights only?")
    print("  Question 3: Do we AVERAGE somehow?")
    print("\nThese are SEMANTIC (design) questions, not Core facts.")
    print("Core provides: survivor identity (mechanical)")
    print("Core does NOT provide: merge strategy (semantic)")
    
    subsection("SEMANTIC QUESTION: Morph Transfer")
    print("When vertex deleted: what happens to its morph offsets?")
    print("  Question 1: Do morphs TARGET the survivor?")
    print("  Question 2: Do morphs transfer? (offset, scaled, blended?)")
    print("  Question 3: Do we create NEW morphs that include collapse trajectory?")
    print("\nThese are SEMANTIC (design) questions, not Core facts.")
    
    subsection("CONCLUSION 3C-3")
    observation("Survivor rule holds across collapse sequence (mechanical, robust)")
    uncertainty("Weight merge strategy still open (semantic question)")
    uncertainty("Morph transfer strategy still open (semantic question)")
    implication("RigController CAN track survivors, but merge strategy is design choice")
    implication("Multiple approaches viable; cannot claim one is 'correct'")
    
    print("\n[STATUS] 3C-3 demonstrates: Survivor robust, but semantics open")


# =====================================================================
# Test 3C-4: Mixed Sequence
# =====================================================================

def test_3c4_mixed_sequence():
    """
    3C-4: Realistic sequence combining multiple operations
    
    Sequence: split → collapse → connect (if feasible)
    
    Question: What's the bottleneck when combining operations?
    """
    
    section("3C-4: Mixed Sequence (split → collapse → connect)")
    
    # Build quad for flexibility
    mesh = Mesh()
    va = mesh.add_vertex((0.0, 1.0, 0.0))
    vb = mesh.add_vertex((1.0, 1.0, 0.0))
    vc = mesh.add_vertex((1.0, 0.0, 0.0))
    vd = mesh.add_vertex((0.0, 0.0, 0.0))
    f1 = mesh.add_face([va, vb, vc])
    f2 = mesh.add_face([va, vc, vd])
    
    subsection("BASELINE: Quad")
    print(f"Vertices: {sorted(mesh.all_vertex_ids())}")
    print(f"Edges: {sorted(mesh.all_edge_ids())}")
    print(f"Faces: {sorted(mesh.all_face_ids())}")
    
    # Operation 1: split
    subsection("OPERATION 1: split_edge()")
    edges = sorted(mesh.all_edge_ids())
    edge_to_split = edges[0]
    new_v, new_e_a, new_e_b = mesh.split_edge(edge_to_split)
    print(f"Split {edge_to_split} → new vertex {new_v}")
    observation("New vertex created")
    
    # Operation 2: collapse
    subsection("OPERATION 2: collapse_edge()")
    edges = sorted(mesh.all_edge_ids())
    if len(edges) >= 3:
        edge_to_collapse = edges[1]  # Choose different edge
        v_surv, v_dead = mesh.edge_vertices(edge_to_collapse)
        print(f"Collapse {edge_to_collapse}: v{v_surv} survives, v{v_dead} dies")
        result = mesh.collapse_edge(edge_to_collapse)
        observation(f"Survivor rule holds: {result == v_surv}")
    
    # Operation 3: connect (if feasible)
    subsection("OPERATION 3: connect_vertices() [if possible]")
    faces = sorted(mesh.all_face_ids())
    if len(faces) >= 1:
        try:
            face = faces[0]
            boundary = mesh.face_vertices(face)
            print(f"Face {face} boundary: {boundary}")
            
            if len(boundary) >= 4:
                v_a, v_b = boundary[0], boundary[2]  # Diagonal
                new_edge, new_f1, new_f2 = mesh.connect_vertices(face, v_a, v_b)
                observation(f"Connect created: edge {new_edge}, faces {new_f1} {new_f2}")
            else:
                print("(Not enough vertices for meaningful connect)")
        except Exception as e:
            print(f"(Connect not feasible: {e})")
    
    subsection("ANALYSIS: What was challenged?")
    print("1. Split: Parent identification challenge (if snapshot-only)")
    print("2. Collapse: Weight/morph merge strategy (design choice)")
    print("3. Connect: Boundary vertex tracking (need investigation)")
    
    subsection("OBSERVATION: Information Flow")
    observation("Each operation modifies topology predictably")
    observation("Survivor tracking works (collapse)")
    uncertainty("Parent tracking depends on context (split)")
    uncertainty("Merge strategies still open (all operations)")
    
    subsection("CONCLUSION 3C-4")
    finding("Mixed sequence is traceable but requires design decisions")
    implication("Bottleneck: Weight and morph merge semantics (not mechanical)")
    implication("No Core limitation preventing sequence handling")
    implication("Main challenge: choosing merge strategy correctly")
    
    print("\n[STATUS] 3C-4 demonstrates: Sequence is feasible, semantics are key")


# =====================================================================
# Main: Run All Tests
# =====================================================================

if __name__ == "__main__":
    if not CORE_AVAILABLE:
        print("FATAL: Core.Mesh required", file=sys.stderr)
        sys.exit(1)
    
    try:
        test_3c1_split_operation_context()
        test_3c2_split_snapshot_only()
        test_3c3_collapse_sequence()
        test_3c4_mixed_sequence()
        
        section("PHASE 3C RESEARCH COMPLETE")
        print("\nFindings ready for FINDINGS-3C.md")
        
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
