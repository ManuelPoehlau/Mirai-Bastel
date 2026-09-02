"""Living-Mesh Prototype: Standalone entry point.

Runs the interactive workbench without viewport.
Demonstrates the full workflow:
  1. Mesh + Rig setup
  2. Inspection (BEFORE)
  3. Deformation (pose + morph)
  4. Topology operation
  5. Inspection (AFTER + DIFF)
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure project root is in path for src.core imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from living_mesh_harness import create_default_harness
from inspection import print_before_after


def main():
    print("=" * 70)
    print("Living-Mesh Prototype — Interactive Workbench")
    print("=" * 70)

    # 1. Setup
    print("\n[1] Setting up mesh + rig + weights + morphs...")
    harness = create_default_harness()
    bones = harness._get_bone_ids_by_name()
    print(f"    Bones: {bones}")
    print(f"    Vertices: {sorted(harness.mesh.all_vertex_ids(), key=int)}")
    print(f"    Weights: {len(harness.rig.skinning_weights)} vertices weighted")
    print(f"    Morphs: {list(harness.rig.morph_targets.keys())}")

    # 2. Inspect BEFORE
    print("\n[2] Capturing BEFORE state...")
    before = harness.capture("initial")

    # 3. Deform
    print("\n[3] Applying deformation (jaw open + morph)...")
    transforms = harness.pose_jaw_open(0.5)
    harness.rig.set_morph_active("jaw_open", 1.0)
    deformed = harness.deform(transforms)
    print(f"    Deformed {len(deformed)} vertices")

    # Show a sample vertex
    jaw_verts = [v for v in harness.mesh.all_vertex_ids() if int(v) in [4, 5]]
    if jaw_verts:
        vid = jaw_verts[0]
        orig = harness.mesh.vertex_position(vid)
        def_pos = deformed[vid]
        print(f"    Example: v{vid} {orig} -> {def_pos}")

    # 4. Topology operation
    print("\n[4] Performing topology operation (split edge)...")
    edge_id = sorted(harness.mesh.all_edge_ids(), key=int)[0]
    print(f"    Splitting edge {edge_id}...")
    new_v, new_ea, new_eb = harness.split_edge(edge_id)
    print(f"    New vertex: {new_v}")
    print(f"    New edges: {new_ea}, {new_eb}")

    # 5. Inspect AFTER + DIFF
    print("\n[5] Capturing AFTER state + DIFF...")
    after = harness.capture("after_split")
    harness.compare_states(before, after)

    # 6. Deform again (after topology change)
    print("\n[6] Deforming again (after topology change)...")
    deformed2 = harness.deform(transforms)
    print(f"    Deformed {len(deformed2)} vertices (including new vertex)")

    # Show new vertex deformation
    if new_v in deformed2:
        print(f"    New vertex {new_v} deformed to: {deformed2[new_v]}")

    print("\n" + "=" * 70)
    print("Living-Mesh Prototype — Complete")
    print("=" * 70)
    print("\nSummary:")
    print(f"  - Mesh: {len(harness.mesh.all_vertex_ids())} vertices, "
          f"{len(harness.mesh.all_edge_ids())} edges, "
          f"{len(harness.mesh.all_face_ids())} faces")
    print(f"  - Rig: {len(harness.rig.bones)} bones, "
          f"{len(harness.rig.skinning_weights)} weighted vertices, "
          f"{len(harness.rig.morph_targets)} morph targets")
    print(f"  - New vertex {new_v} has weights: {harness.rig.get_vertex_weights(new_v)}")
    print(f"  - New vertex {new_v} has morph data: ", end="")
    has_morph = False
    for mname in harness.rig.morph_targets:
        if new_v in harness.rig.morph_targets[mname]:
            print(f"'{mname}' ", end="")
            has_morph = True
    if not has_morph:
        print("(none)", end="")
    print()

    print("\nNote: New vertex has NO inherited weights/morphs.")
    print("      This is the semantic question for Claude to decide.")


if __name__ == "__main__":
    main()
