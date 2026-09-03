"""Tests for Living-Mesh Prototype: Mechanical verification only.

These tests verify the TECHNICAL FOUNDATION of the prototype.
They do NOT assert semantic correctness of weight/morph migration strategies.

Test A: Mesh + Rig can be initialized.
Test B: Skin weights can be stored and queried.
Test C: Morph targets can be stored and queried.
Test D: Simple deformation can be executed.
Test E: Topology operation can be executed and inspected.
Test F: BEFORE/AFTER state can be reliably captured.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in path for src.core imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Ensure experiment directory is in path for bone/deformation/rig_controller imports
_EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENT_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENT_DIR))

# Import experiment modules (non-relative, as in existing tests)
from bone import Bone
from deformation import Transform, linear_blend_skinning, blend_morphs
from rig_controller import RigController, TopologySnapshot, TopologyChanges

# Import Core
try:
    from src.core.mesh import Mesh
    from src.core.ids import VertexId, EdgeId, FaceId
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False

# Import prototype modules
from demo_mesh import build_head_mesh, get_skull_vertices, get_jaw_vertices, get_neck_vertices
from inspection import (
    capture_topology, capture_rig, capture_full,
    diff_topology, diff_rig,
    TopologyState, RigState, FullState,
    TopologyDiff, RigDiff,
)
from living_mesh_harness import LivingMeshHarness, create_default_harness

import pytest


# =====================================================================
# Test A: Mesh + Rig Initialization
# =====================================================================

class TestA_MeshRigInitialization:
    """Test A: Mesh + Rig can be initialized."""

    def test_demo_mesh_builds(self):
        """Demo head mesh builds with expected topology."""
        mesh = build_head_mesh()
        assert len(mesh.all_vertex_ids()) == 8, "Expected 8 vertices"
        assert len(mesh.all_edge_ids()) == 12, "Expected 12 edges"
        assert len(mesh.all_face_ids()) == 6, "Expected 6 faces"

    def test_demo_mesh_deterministic(self):
        """Demo mesh is reproducible (same IDs every time)."""
        mesh1 = build_head_mesh()
        mesh2 = build_head_mesh()
        assert sorted(mesh1.all_vertex_ids(), key=int) == sorted(mesh2.all_vertex_ids(), key=int)
        assert sorted(mesh1.all_edge_ids(), key=int) == sorted(mesh2.all_edge_ids(), key=int)
        assert sorted(mesh1.all_face_ids(), key=int) == sorted(mesh2.all_face_ids(), key=int)

    def test_rig_controller_initializes(self):
        """RigController initializes with a mesh."""
        mesh = build_head_mesh()
        rig = RigController(mesh)
        assert rig.bones == {}
        assert rig.skinning_weights == {}
        assert rig.morph_targets == {}

    def test_default_rig_setup(self):
        """Default 3-bone hierarchy can be created."""
        harness = LivingMeshHarness()
        bones = harness.setup_default_rig()
        assert "Neck" in bones
        assert "Skull" in bones
        assert "Jaw" in bones
        assert len(harness.rig.bones) == 3

    def test_default_harness_creation(self):
        """create_default_harness() produces a fully configured harness."""
        harness = create_default_harness()
        assert harness.mesh is not None
        assert len(harness.rig.bones) == 3
        assert len(harness.rig.skinning_weights) > 0
        assert len(harness.rig.morph_targets) == 2


# =====================================================================
# Test B: Skin Weights Storage & Query
# =====================================================================

class TestB_SkinWeights:
    """Test B: Skin weights can be stored and queried."""

    def test_set_and_get_weight(self):
        """Weight can be set and retrieved."""
        harness = create_default_harness()
        vid = get_skull_vertices()[0]
        weights = harness.rig.get_vertex_weights(vid)
        assert len(weights) > 0, "Vertex should have weights after default setup"

    def test_weight_values_correct(self):
        """Default weights have expected values (1.0 for single-bone assignment)."""
        harness = create_default_harness()
        for vid in get_skull_vertices():
            weights = harness.rig.get_vertex_weights(vid)
            assert len(weights) == 1, f"Skull vertex {vid} should have exactly 1 weight"
            assert weights[0][1] == 1.0, f"Skull vertex {vid} weight should be 1.0"

    def test_multiple_weights_per_vertex(self):
        """Multiple bone influences can be assigned to one vertex."""
        harness = create_default_harness()
        bones = harness._get_bone_ids_by_name()
        vid = get_skull_vertices()[0]
        harness.rig.set_vertex_weight(vid, bones["Skull"], 0.7)
        harness.rig.set_vertex_weight(vid, bones["Jaw"], 0.3)
        weights = harness.rig.get_vertex_weights(vid)
        assert len(weights) == 2

    def test_weights_persist_after_query(self):
        """Weights remain stable across multiple queries."""
        harness = create_default_harness()
        vid = get_jaw_vertices()[0]
        w1 = harness.rig.get_vertex_weights(vid)
        w2 = harness.rig.get_vertex_weights(vid)
        assert w1 == w2

    def test_unweighted_vertex_returns_empty(self):
        """Vertex with no weights returns empty list."""
        mesh = build_head_mesh()
        rig = RigController(mesh)
        # Don't set any weights
        assert rig.get_vertex_weights(VertexId(0)) == []


# =====================================================================
# Test C: Morph Targets Storage & Query
# =====================================================================

class TestC_MorphTargets:
    """Test C: Morph targets can be stored and queried."""

    def test_morph_target_creation(self):
        """Morph target can be created."""
        harness = LivingMeshHarness()
        harness.rig.add_morph_target("test_morph")
        assert "test_morph" in harness.rig.morph_targets

    def test_morph_offset_storage(self):
        """Morph offset can be stored and retrieved."""
        harness = LivingMeshHarness()
        harness.rig.add_morph_target("test")
        vid = VertexId(0)
        offset = (0.1, 0.2, 0.3)
        harness.rig.set_morph_offset("test", vid, offset)
        result = harness.rig.get_morph_offset("test", vid)
        assert result == offset

    def test_default_morphs_exist(self):
        """Default harness has smile and jaw_open morphs."""
        harness = create_default_harness()
        assert "smile" in harness.rig.morph_targets
        assert "jaw_open" in harness.rig.morph_targets

    def test_morph_active_state(self):
        """Morph activation state can be set and queried."""
        harness = create_default_harness()
        harness.rig.set_morph_active("smile", 0.5)
        assert harness.rig.active_morphs["smile"] == 0.5

    def test_morph_offset_affects_multiple_vertices(self):
        """Morph offsets can be set for multiple vertices."""
        harness = create_default_harness()
        smile_data = harness.rig.morph_targets["smile"]
        jaw_verts = get_jaw_vertices()
        # At least some jaw vertices should have smile offsets
        affected = [v for v in jaw_verts if v in smile_data]
        assert len(affected) > 0


# =====================================================================
# Test D: Simple Deformation
# =====================================================================

class TestD_Deformation:
    """Test D: Simple deformation can be executed."""

    def test_deform_with_identity_transforms(self):
        """Deformation with identity transforms returns original positions."""
        harness = create_default_harness()
        transforms = {bid: Transform.identity() for bid in harness.rig.bones}
        deformed = harness.deform(transforms)
        # With identity transforms, positions should be unchanged (plus morphs)
        for vid in harness.mesh.all_vertex_ids():
            assert vid in deformed, f"Vertex {vid} missing from deformed output"

    def test_deform_with_translation(self):
        """Deformation with bone translation moves weighted vertices."""
        harness = create_default_harness()
        bones = harness._get_bone_ids_by_name()
        jaw_id = bones["Jaw"]

        # Translate jaw bone by (0, -1, 0)
        transforms = {bid: Transform.identity() for bid in harness.rig.bones}
        transforms[jaw_id] = Transform(translation=(0.0, -1.0, 0.0))

        deformed = harness.deform(transforms)

        # Jaw vertices should move down
        for vid in get_jaw_vertices():
            if harness.mesh.is_valid_vertex(vid):
                orig = harness.mesh.vertex_position(vid)
                def_pos = deformed[vid]
                assert def_pos[1] < orig[1], f"Jaw vertex {vid} should move down"

    def test_deform_with_morphs(self):
        """Deformation with active morphs adds morph offsets."""
        harness = create_default_harness()
        harness.rig.set_morph_active("jaw_open", 1.0)

        transforms = {bid: Transform.identity() for bid in harness.rig.bones}
        deformed = harness.deform(transforms)

        # Jaw vertices should have morph offset applied
        for vid in get_jaw_vertices():
            if harness.mesh.is_valid_vertex(vid):
                orig = harness.mesh.vertex_position(vid)
                def_pos = deformed[vid]
                # jaw_open moves vertices down by 0.2
                assert def_pos[1] < orig[1], f"Jaw vertex {vid} should move down from morph"

    def test_deform_combined_skinning_and_morphs(self):
        """Deformation combines skinning and morphs."""
        harness = create_default_harness()
        bones = harness._get_bone_ids_by_name()
        jaw_id = bones["Jaw"]

        transforms = {bid: Transform.identity() for bid in harness.rig.bones}
        transforms[jaw_id] = Transform(translation=(0.0, -0.5, 0.0))
        harness.rig.set_morph_active("jaw_open", 1.0)

        deformed = harness.deform(transforms)

        # Jaw vertices should move down from BOTH skinning and morphs
        for vid in get_jaw_vertices():
            if harness.mesh.is_valid_vertex(vid):
                orig = harness.mesh.vertex_position(vid)
                def_pos = deformed[vid]
                # Combined: skinning (-0.5) + morph (-0.2) = -0.7
                assert def_pos[1] < orig[1] - 0.5, \
                    f"Jaw vertex {vid} should move down from combined effect"


# =====================================================================
# Test E: Topology Operation + Inspection
# =====================================================================

class TestE_TopologyOperation:
    """Test E: Topology operation can be executed and inspected."""

    def test_split_edge_creates_vertex(self):
        """split_edge() creates exactly one new vertex."""
        harness = create_default_harness()
        before_verts = set(harness.mesh.all_vertex_ids())
        edge_id = sorted(harness.mesh.all_edge_ids(), key=int)[0]
        new_v, new_ea, new_eb = harness.split_edge(edge_id)
        after_verts = set(harness.mesh.all_vertex_ids())
        new_verts = after_verts - before_verts
        assert len(new_verts) == 1
        assert new_v in new_verts

    def test_collapse_edge_removes_vertex(self):
        """collapse_edge() removes exactly one vertex."""
        harness = create_default_harness()
        before_verts = set(harness.mesh.all_vertex_ids())
        edge_id = sorted(harness.mesh.all_edge_ids(), key=int)[0]
        survivor = harness.collapse_edge(edge_id)
        after_verts = set(harness.mesh.all_vertex_ids())
        removed = before_verts - after_verts
        assert len(removed) == 1
        assert survivor in after_verts

    def test_topology_change_detectable_via_snapshots(self):
        """Topology changes are detectable via snapshot comparison."""
        harness = create_default_harness()
        harness.snapshot_topology("before")
        edge_id = sorted(harness.mesh.all_edge_ids(), key=int)[0]
        harness.split_edge(edge_id)
        changes = harness.detect_changes()
        assert len(changes.new_vertices) > 0, "Should detect new vertex"

    def test_inspection_captures_topology(self):
        """Inspection captures topology state."""
        harness = create_default_harness()
        state = harness.capture("test")
        assert len(state.topology.vertex_ids) == 8
        assert len(state.topology.edge_ids) == 12
        assert len(state.topology.face_ids) == 6

    def test_inspection_captures_rig(self):
        """Inspection captures rig state."""
        harness = create_default_harness()
        state = harness.capture("test")
        assert len(state.rig.bones) == 3
        assert len(state.rig.weights) > 0
        assert len(state.rig.morph_targets) == 2


# =====================================================================
# Test F: BEFORE/AFTER State Capture
# =====================================================================

class TestF_BeforeAfterCapture:
    """Test F: BEFORE/AFTER state can be reliably captured."""

    def test_capture_before_state(self):
        """BEFORE state captures complete topology + rig."""
        harness = create_default_harness()
        before = harness.capture("before")
        assert len(before.topology.vertex_ids) == 8
        assert len(before.rig.bones) == 3

    def test_capture_after_state(self):
        """AFTER state reflects topology changes."""
        harness = create_default_harness()
        before = harness.capture("before")
        edge_id = sorted(harness.mesh.all_edge_ids(), key=int)[0]
        harness.split_edge(edge_id)
        after = harness.capture("after")
        assert len(after.topology.vertex_ids) == 9  # 8 + 1 new

    def test_diff_topology_shows_new_vertex(self):
        """Topology diff correctly identifies new vertex."""
        harness = create_default_harness()
        before = harness.capture("before")
        edge_id = sorted(harness.mesh.all_edge_ids(), key=int)[0]
        harness.split_edge(edge_id)
        after = harness.capture("after")
        diff = diff_topology(before.topology, after.topology)
        assert len(diff.new_vertices) == 1

    def test_diff_topology_shows_deleted_vertex(self):
        """Topology diff correctly identifies deleted vertex."""
        harness = create_default_harness()
        before = harness.capture("before")
        edge_id = sorted(harness.mesh.all_edge_ids(), key=int)[0]
        harness.collapse_edge(edge_id)
        after = harness.capture("after")
        diff = diff_topology(before.topology, after.topology)
        assert len(diff.deleted_vertices) == 1

    def test_diff_rig_shows_no_changes_without_rig_mutation(self):
        """Rig diff shows no changes when only topology changes (no rig update)."""
        harness = create_default_harness()
        before = harness.capture("before")
        edge_id = sorted(harness.mesh.all_edge_ids(), key=int)[0]
        harness.split_edge(edge_id)
        after = harness.capture("after")
        diff = diff_rig(before.rig, after.rig)
        # Without explicit rig update, weights/morphs should be unchanged
        assert len(diff.changed_weights) == 0
        assert len(diff.new_weighted_vertices) == 0

    def test_full_before_after_report(self):
        """Full BEFORE → AFTER → DIFF report can be generated."""
        harness = create_default_harness()
        before = harness.capture("initial")
        edge_id = sorted(harness.mesh.all_edge_ids(), key=int)[0]
        harness.split_edge(edge_id)
        after = harness.capture("after_split")
        # Should not raise
        harness.compare_states(before, after)


# =====================================================================
# Run all tests
# =====================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
