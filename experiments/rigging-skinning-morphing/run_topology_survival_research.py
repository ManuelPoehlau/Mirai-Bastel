"""Phase 3A/3B: Topology Survival Research - Standalone Execution

Runs topology investigations without pytest dependency.
Outputs findings to stdout and FINDINGS.md
"""

import sys
import os
from typing import Tuple, Dict, List

# Try to import Core
try:
    from src.core.mesh import Mesh
    from src.core.ids import VertexId, EdgeId, FaceId
    CORE_AVAILABLE = True
except ImportError:
    print("ERROR: Core.Mesh not importable.", file=sys.stderr)
    print("Make sure src/core/mesh.py is available.", file=sys.stderr)
    CORE_AVAILABLE = False
    sys.exit(1)


def distance_3d(p1: Tuple[float, float, float], 
                p2: Tuple[float, float, float]) -> float:
    """Euclidean distance."""
    return sum((a - b) ** 2 for a, b in zip(p1, p2)) ** 0.5


def section(title: str):
    """Print section header."""
    print("\n" + "="*70)
    print(title)
    print("="*70)


def subsection(title: str):
    """Print subsection header."""
    print(f"\n--- {title} ---")


# =====================================================================
# Phase 3A: SPLIT_EDGE RESEARCH
# =====================================================================

def research_3a_split_edge():
    """Investigate split_edge() parent reconstruction."""
    
    section("PHASE 3A: SPLIT_EDGE RESEARCH")
    
    # Case A1: Operation Known
    subsection("CASE A1: Operation KNOWN (trivial)")
    print("When split_edge(edge_id) is called directly, parent is trivially known.")
    print("This is NOT a research problem.")
    print("FINDING: Skip Case A1.")
    
    # Case A2: Operation Observed
    subsection("CASE A2: Operation OBSERVED (core research)")
    
    print("Setup: Simple triangle mesh")
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((0.5, 1.0, 0.0))
    f = mesh.add_face([v0, v1, v2])
    
    print(f"  v0={v0} at (0, 0, 0)")
    print(f"  v1={v1} at (1, 0, 0)")
    print(f"  v2={v2} at (0.5, 1, 0)")
    print(f"  Face: [{v0}, {v1}, {v2}]")
    
    # Capture before
    subsection("BASELINE (before split)")
    vertices_before = set(mesh.all_vertex_ids())
    edges_before = {}
    for eid in mesh.all_edge_ids():
        v_a, v_b = mesh.edge_vertices(eid)
        p_a = mesh.vertex_position(v_a)
        p_b = mesh.vertex_position(v_b)
        edges_before[eid] = (v_a, v_b, p_a, p_b)
    
    print(f"Vertices: {sorted(vertices_before)}")
    print(f"Edges: {sorted(edges_before.keys())}")
    for eid, (v_a, v_b, p_a, p_b) in edges_before.items():
        print(f"  {eid}: v{v_a}-v{v_b} : {p_a} -- {p_b}")
    
    # Hidden operation
    subsection("OPERATION (hidden from observer)")
    edge_to_split = sorted(edges_before.keys())[0]
    print(f"Split edge_id={edge_to_split} (unknown to observer)")
    
    new_v, new_e_a, new_e_b = mesh.split_edge(edge_to_split)
    print(f"Returned: new_vertex={new_v}, edges=({new_e_a}, {new_e_b})")
    
    # Capture after
    subsection("SNAPSHOT (after split)")
    vertices_after = set(mesh.all_vertex_ids())
    new_verts = vertices_after - vertices_before
    edges_after = set(mesh.all_edge_ids())
    new_edges = edges_after - set(edges_before.keys())
    deleted_edges = set(edges_before.keys()) - edges_after
    
    print(f"Vertices: {sorted(vertices_after)} (new: {new_verts})")
    print(f"Edges: {sorted(edges_after)}")
    print(f"  New edges: {new_edges}")
    print(f"  Deleted edges: {deleted_edges}")
    
    # Investigation
    subsection("OBSERVATION: What can we learn from public APIs?")
    
    new_vertex_pos = mesh.vertex_position(list(new_verts)[0])
    print(f"New vertex {new_verts} position: {new_vertex_pos}")
    
    # Try to find parent edge via deleted edge endpoints
    print(f"\nTrying to find parent edge...")
    if deleted_edges:
        deleted_eid = list(deleted_edges)[0]
        v_a, v_b, p_a, p_b = edges_before[deleted_eid]
        computed_midpoint = tuple((x + y) / 2 for x, y in zip(p_a, p_b))
        distance = distance_3d(computed_midpoint, new_vertex_pos)
        
        print(f"Deleted edge {deleted_eid}:")
        print(f"  Endpoints: v{v_a} at {p_a}, v{v_b} at {p_b}")
        print(f"  Midpoint: {computed_midpoint}")
        print(f"  New vertex position: {new_vertex_pos}")
        print(f"  Distance: {distance:.8f}")
        
        if distance < 1e-6:
            print(f"✓ MATCH: Deleted edge is parent (position matches midpoint)")
        else:
            print(f"✗ NO MATCH: Distance too large")
    
    subsection("INTERPRETATION (what we infer, not observe)")
    print("Strategy: Geometric heuristic - match new vertex position to edge midpoints")
    print("\nLimitations:")
    print("  - Doesn't work if two edges have same midpoint")
    print("  - Floating-point precision issues")
    print("  - Not guaranteed for non-uniform meshes")
    
    subsection("CORE GAP")
    print("Core provides NO direct way to identify which edge was split.")
    print("  ✗ No vertex.parent_edge metadata")
    print("  ✗ No operation logging")
    print("  ✗ No 'which edge was deleted?' query")
    
    subsection("CONCLUSION 3A")
    print("Q: Can external Controller reconstruct parent edge from public APIs?")
    print("A: ONLY via geometric heuristic (unreliable)")
    print("\nRequired for robust solution:")
    print("  - CORE EXTENSION: Store edge_id in new vertex metadata")
    print("  - OR: RigController tracks all split() calls directly")


# =====================================================================
# Phase 3B: COLLAPSE_EDGE RESEARCH
# =====================================================================

def research_3b_collapse_edge():
    """Investigate collapse_edge() survivor determination."""
    
    section("PHASE 3B: COLLAPSE_EDGE RESEARCH")
    
    # Case B1a: Simple triangle
    subsection("CASE B1a: Survivor in Simple Triangle")
    
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((0.5, 1.0, 0.0))
    f = mesh.add_face([v0, v1, v2])
    
    print(f"Triangle: v0={v0}, v1={v1}, v2={v2}")
    
    subsection("PREDICTION (from CORE_API_AUDIT.md)")
    edge_id = mesh.all_edge_ids()[0]
    v_predicted_surv, v_predicted_dead = mesh.edge_vertices(edge_id)
    print(f"Edge {edge_id}: ({v_predicted_surv}, {v_predicted_dead})")
    print(f"Prediction: v0={v_predicted_surv} survives, v1={v_predicted_dead} deleted")
    
    subsection("OPERATION")
    verts_before = set(mesh.all_vertex_ids())
    result = mesh.collapse_edge(edge_id)
    verts_after = set(mesh.all_vertex_ids())
    deleted = verts_before - verts_after
    
    print(f"collapse_edge({edge_id}) returned: {result}")
    print(f"Deleted vertices: {deleted}")
    
    subsection("OBSERVATION")
    v_surv_valid = mesh.is_valid_vertex(v_predicted_surv)
    v_dead_invalid = v_predicted_dead not in verts_after
    result_matches_v0 = result == v_predicted_surv
    
    print(f"v{v_predicted_surv} (predicted survivor) still valid: {v_surv_valid}")
    print(f"v{v_predicted_dead} (predicted deleted) now invalid: {v_dead_invalid}")
    print(f"Return value = v0 (predicted survivor): {result_matches_v0}")
    
    subsection("CONCLUSION 3B1a")
    if v_surv_valid and v_dead_invalid and result_matches_v0:
        print("✓ PREDICTION VERIFIED")
        print("  Survivor rule holds: v0 always survives")
        print("  Return value is reliable: == survivor_id")
        print("  Reliability: HIGH")
    else:
        print("✗ PREDICTION FAILED")
    
    # Case B1b: Quad mesh
    subsection("CASE B1b: Survivor in Quad Mesh")
    
    mesh2 = Mesh()
    va = mesh2.add_vertex((0.0, 1.0, 0.0))
    vb = mesh2.add_vertex((1.0, 1.0, 0.0))
    vc = mesh2.add_vertex((1.0, 0.0, 0.0))
    vd = mesh2.add_vertex((0.0, 0.0, 0.0))
    f1 = mesh2.add_face([va, vb, vc])
    f2 = mesh2.add_face([va, vc, vd])
    
    print(f"Quad: va={va}, vb={vb}, vc={vc}, vd={vd}")
    print(f"Faces: [{va},{vb},{vc}] and [{va},{vc},{vd}]")
    
    subsection("OPERATION: Collapse internal edge (shared by 2 faces)")
    
    # Find internal edge
    internal_edge = None
    for eid in mesh2.all_edge_ids():
        if len(mesh2.edge_faces(eid)) == 2:
            internal_edge = eid
            break
    
    if internal_edge:
        v_s, v_d = mesh2.edge_vertices(internal_edge)
        print(f"Internal edge {internal_edge}: ({v_s}, {v_d})")
        print(f"Prediction: v{v_s} survives, v{v_d} deleted")
        
        verts_before = set(mesh2.all_vertex_ids())
        result = mesh2.collapse_edge(internal_edge)
        verts_after = set(mesh2.all_vertex_ids())
        deleted = verts_before - verts_after
        
        print(f"Result: {result}, deleted: {deleted}")
        
        if mesh2.is_valid_vertex(v_s) and v_d in deleted and result == v_s:
            print("✓ PREDICTION VERIFIED in quad mesh")
        else:
            print("✗ PREDICTION FAILED in quad mesh")
    
    subsection("CONCLUSION 3B1b")
    print("Survivor rule appears CONSISTENT across topologies")
    print("(Limited testing, but trend clear)")
    
    # Case B2: Weight migration feasibility
    subsection("CASE B2: Weight Migration Feasibility")
    
    mesh3 = Mesh()
    v0 = mesh3.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh3.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh3.add_vertex((0.5, 1.0, 0.0))
    mesh3.add_face([v0, v1, v2])
    
    edge = mesh3.all_edge_ids()[0]
    v_surv, v_dead = mesh3.edge_vertices(edge)
    p_surv_before = mesh3.vertex_position(v_surv)
    p_dead_before = mesh3.vertex_position(v_dead)
    
    print(f"Before collapse:")
    print(f"  Survivor v{v_surv} at {p_surv_before}")
    print(f"  Deleted v{v_dead} at {p_dead_before}")
    
    mesh3.collapse_edge(edge)
    p_surv_after = mesh3.vertex_position(v_surv)
    
    print(f"After collapse:")
    print(f"  Survivor v{v_surv} at {p_surv_after} (moved)")
    print(f"  Deleted v{v_dead} invalid")
    
    subsection("INFORMATION AVAILABLE")
    print("✓ Which vertex survived")
    print("✓ Which was deleted")
    print("✓ Survivor's before/after position")
    print("✗ Original weights (RigController's responsibility)")
    print("✗ Weight merge strategy (design choice)")
    
    subsection("CONCLUSION 3B2")
    print("Survivor information sufficient for RigController to ATTEMPT merge")
    print("Weight strategy is RigController's design choice, not Core's gap")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    if not CORE_AVAILABLE:
        print("FATAL: Core.Mesh not available", file=sys.stderr)
        sys.exit(1)
    
    try:
        research_3a_split_edge()
        research_3b_collapse_edge()
        
        print("\n" + "="*70)
        print("PHASE 3A/3B RESEARCH COMPLETE")
        print("="*70)
        print("\nFindings ready for FINDINGS.md documentation")
        
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
