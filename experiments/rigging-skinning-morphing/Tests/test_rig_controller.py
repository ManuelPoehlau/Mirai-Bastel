"""Phase 2c: Unit Tests for RigController Components.

Tests verify that RigController functionality works as designed.
Each test is also a documentation of behavior.

Tests use hypothetical mesh (mock), not actual Core mesh yet.
For actual topology investigation, see test_topology_operations.py
"""

import pytest
from bone import Bone
from deformation import Transform, linear_blend_skinning, blend_morphs
from rig_controller import RigController, TopologySnapshot, TopologyChanges


# =====================================================================
# Fixtures
# =====================================================================

class MockMesh:
    """Mock Core.Mesh for testing (doesn't modify anything)."""
    
    def __init__(self, vertices=None, edges=None, faces=None):
        """Initialize mock with optional element data.
        
        Args:
            vertices: dict[int -> (x, y, z)]
            edges: dict[int -> (v0, v1, [face_ids])]
            faces: dict[int -> [vertex_ids]]
        """
        self._vertices = vertices or {
            0: (0.0, 0.0, 0.0),
            1: (1.0, 0.0, 0.0),
            2: (0.5, 1.0, 0.0),
            3: (0.5, 0.5, 1.0),
        }
        self._edges = edges or {
            0: (0, 1, [0]),
            1: (1, 2, [0]),
            2: (2, 0, [0]),
            3: (0, 3, [1, 2]),
            4: (1, 3, [1]),
            5: (2, 3, [2]),
        }
        self._faces = faces or {
            0: [0, 1, 2],
            1: [0, 1, 3],
            2: [1, 2, 3],
        }
    
    def all_vertex_ids(self):
        return list(self._vertices.keys())
    
    def all_edge_ids(self):
        return list(self._edges.keys())
    
    def all_face_ids(self):
        return list(self._faces.keys())
    
    def vertex_position(self, vertex_id):
        return self._vertices[vertex_id]
    
    def set_vertex_position(self, vertex_id, position):
        self._vertices[vertex_id] = position
    
    def vertex_edges(self, vertex_id):
        """Return all edges touching this vertex."""
        result = []
        for edge_id, (v0, v1, _) in self._edges.items():
            if v0 == vertex_id or v1 == vertex_id:
                result.append(edge_id)
        return result
    
    def edge_vertices(self, edge_id):
        """Return (v0, v1) for edge."""
        v0, v1, _ = self._edges[edge_id]
        return (v0, v1)
    
    def edge_faces(self, edge_id):
        """Return faces touching this edge."""
        _, _, faces = self._edges[edge_id]
        return list(faces)
    
    def face_vertices(self, face_id):
        """Return boundary vertices for face."""
        return list(self._faces[face_id])
    
    def is_valid_vertex(self, vertex_id):
        return vertex_id in self._vertices


@pytest.fixture
def mock_mesh():
    """Simple tetrahedral mesh."""
    return MockMesh()


@pytest.fixture
def rig(mock_mesh):
    """RigController with simple bone hierarchy."""
    controller = RigController(mock_mesh)
    
    # Create hierarchy: Root -> Jaw, Neck
    root_id = controller.add_bone("Root")
    jaw_id = controller.add_bone("Jaw", parent_id=root_id)
    neck_id = controller.add_bone("Neck", parent_id=root_id)
    
    return controller


# =====================================================================
# Bone Management Tests
# =====================================================================

class TestBoneManagement:
    """Test bone hierarchy operations."""
    
    def test_add_bone_root(self, rig):
        """Test adding root bone."""
        bone = rig.get_bone(0)
        assert bone is not None
        assert bone.name == "Root"
        assert bone.parent is None
    
    def test_add_bone_with_parent(self, rig):
        """Test adding bone with parent."""
        jaw = rig.get_bone(1)
        assert jaw is not None
        assert jaw.name == "Jaw"
        assert jaw.parent is not None
        assert jaw.parent.name == "Root"
    
    def test_bone_chain_to_root(self, rig):
        """Test getting chain from bone to root."""
        jaw_id = 1
        chain = rig.get_bone_chain_to_root(jaw_id)
        assert len(chain) == 2
        assert chain[0].name == "Jaw"
        assert chain[1].name == "Root"
    
    def test_multiple_children(self, rig):
        """Test parent with multiple children."""
        root = rig.get_bone(0)
        assert len(root.children) == 2
        child_names = {c.name for c in root.children}
        assert child_names == {"Jaw", "Neck"}


# =====================================================================
# Skinning Weight Tests
# =====================================================================

class TestSkinningWeights:
    """Test weight management and inheritance."""
    
    def test_set_single_weight(self, rig):
        """Test setting weight."""
        rig.set_vertex_weight(vertex_id=0, bone_id=0, weight=1.0)
        weights = rig.get_vertex_weights(0)
        assert len(weights) == 1
        assert weights[0] == (0, 1.0)
    
    def test_multiple_weights_same_vertex(self, rig):
        """Test multiple bones influencing one vertex."""
        rig.set_vertex_weight(0, 0, 0.5)  # Root
        rig.set_vertex_weight(0, 1, 0.5)  # Jaw
        weights = rig.get_vertex_weights(0)
        assert len(weights) == 2
        weights_dict = dict(weights)
        assert weights_dict[0] == 0.5
        assert weights_dict[1] == 0.5
    
    def test_weight_override(self, rig):
        """Test that setting weight twice updates, not appends."""
        rig.set_vertex_weight(0, 0, 1.0)
        rig.set_vertex_weight(0, 0, 0.5)  # Override
        weights = rig.get_vertex_weights(0)
        assert len(weights) == 1
        assert weights[0] == (0, 0.5)
    
    def test_clear_weights(self, rig):
        """Test clearing all weights."""
        rig.set_vertex_weight(0, 0, 0.5)
        rig.set_vertex_weight(0, 1, 0.5)
        rig.clear_vertex_weights(0)
        weights = rig.get_vertex_weights(0)
        assert len(weights) == 0
    
    def test_inherit_weights(self, rig):
        """Test weight inheritance (split operation scenario)."""
        # Setup: vertex 0 has weights
        rig.set_vertex_weight(0, 0, 0.5)
        rig.set_vertex_weight(0, 1, 0.5)
        
        # New vertex 4 inherits from 0
        rig.inherit_weights(source_vertex=0, target_vertex=4)
        
        # Verify: vertex 4 has same weights as vertex 0
        weights_0 = rig.get_vertex_weights(0)
        weights_4 = rig.get_vertex_weights(4)
        assert weights_0 == weights_4
    
    def test_get_weights_nonexistent(self, rig):
        """Test getting weights for vertex with no weights."""
        weights = rig.get_vertex_weights(99)
        assert weights == []


# =====================================================================
# Morph Target Tests
# =====================================================================

class TestMorphTargets:
    """Test morph target creation and blending."""
    
    def test_add_morph_target(self, rig):
        """Test creating morph target."""
        rig.add_morph_target("mouth_open")
        assert "mouth_open" in rig.morph_targets
        assert rig.morph_targets["mouth_open"] == {}
    
    def test_set_morph_offset(self, rig):
        """Test setting morph offset."""
        rig.add_morph_target("jaw_drop")
        offset = (0.0, -0.1, 0.0)
        rig.set_morph_offset("jaw_drop", vertex_id=0, offset=offset)
        
        retrieved = rig.get_morph_offset("jaw_drop", vertex_id=0)
        assert retrieved == offset
    
    def test_get_morph_offset_nonexistent(self, rig):
        """Test getting offset for unaffected vertex."""
        rig.add_morph_target("mouth_open")
        offset = rig.get_morph_offset("mouth_open", vertex_id=99)
        assert offset is None
    
    def test_set_morph_active(self, rig):
        """Test activating morph."""
        rig.add_morph_target("smile")
        rig.set_morph_active("smile", 0.7)
        assert rig.active_morphs["smile"] == 0.7
    
    def test_deactivate_morph(self, rig):
        """Test deactivating morph (weight=0)."""
        rig.add_morph_target("smile")
        rig.set_morph_active("smile", 0.5)
        rig.set_morph_active("smile", 0.0)
        assert "smile" not in rig.active_morphs


# =====================================================================
# Topology Snapshot Tests
# =====================================================================

class TestTopologySnapshots:
    """Test topology observation and change detection."""
    
    def test_take_snapshot(self, rig, mock_mesh):
        """Test snapshot capture."""
        snapshot = rig.take_topology_snapshot("initial")
        assert snapshot.label == "initial"
        assert len(snapshot.vertex_ids) == 4
        assert len(snapshot.edge_ids) == 6
        assert len(snapshot.face_ids) == 3
    
    def test_multiple_snapshots(self, rig):
        """Test storing multiple snapshots."""
        snap1 = rig.take_topology_snapshot("before")
        snap2 = rig.take_topology_snapshot("after")
        
        assert len(rig.topology_snapshots) == 2
        assert rig.topology_snapshots[0].label == "before"
        assert rig.topology_snapshots[1].label == "after"
    
    def test_detect_no_changes(self, rig):
        """Test detecting no changes (no-op)."""
        rig.take_topology_snapshot("before")
        # (No changes to mesh)
        changes = rig.detect_topology_changes()
        
        assert changes.new_vertices == []
        assert changes.deleted_vertices == []
        assert changes.new_edges == []
        assert changes.deleted_edges == []
    
    def test_detect_topology_changes_vertex_addition(self, rig, mock_mesh):
        """Test detecting new vertex (mock only)."""
        rig.take_topology_snapshot("before")
        
        # Simulate mesh adding vertex
        mock_mesh._vertices[99] = (0.5, 0.5, 0.5)
        
        changes = rig.detect_topology_changes()
        assert 99 in changes.new_vertices
    
    def test_detect_topology_changes_vertex_deletion(self, rig, mock_mesh):
        """Test detecting deleted vertex."""
        rig.take_topology_snapshot("before")
        
        # Simulate vertex deletion
        del mock_mesh._vertices[0]
        
        changes = rig.detect_topology_changes()
        assert 0 in changes.deleted_vertices


# =====================================================================
# Topology Query Tests
# =====================================================================

class TestTopologyQueries:
    """Test topology query methods using Core API."""
    
    def test_query_vertex_topology(self, rig):
        """Test querying vertex connectivity."""
        findings = rig.query_vertex_topology(vertex_id=0)
        
        assert findings["vertex_id"] == 0
        assert len(findings["connected_edges"]) > 0
        assert len(findings["adjacent_vertices"]) > 0
    
    def test_query_vertex_adjacent(self, rig):
        """Test that adjacent vertices are correctly computed."""
        # Vertex 0 should connect to 1, 2, 3 (based on MockMesh)
        findings = rig.query_vertex_topology(0)
        adjacent = set(findings["adjacent_vertices"])
        assert 1 in adjacent
        assert 2 in adjacent
        assert 3 in adjacent
    
    def test_query_edge_topology(self, rig):
        """Test querying edge."""
        findings = rig.query_edge_topology(edge_id=0)
        
        assert findings["edge_id"] == 0
        assert findings["vertices"] == (0, 1)
        assert len(findings["faces"]) >= 1


# =====================================================================
# Topology Event Handling Tests
# =====================================================================

class TestTopologyEventHandling:
    """Test event handlers for topology changes."""
    
    def test_handle_vertex_deletion(self, rig):
        """Test cleanup when vertex deleted."""
        # Setup weights and morphs
        rig.set_vertex_weight(0, 0, 0.5)
        rig.add_morph_target("smile")
        rig.set_morph_offset("smile", 0, (0.1, 0.0, 0.0))
        
        # Handle deletion
        rig.handle_vertex_deletion(0)
        
        # Verify cleanup
        assert rig.get_vertex_weights(0) == []
        assert rig.get_morph_offset("smile", 0) is None
    
    def test_handle_new_vertex_no_parent(self, rig):
        """Test handling new vertex without parent."""
        rig.handle_new_vertex(new_vertex_id=99, parent_vertex_id=None)
        # Should not crash; new vertex has no weights/morphs
        assert rig.get_vertex_weights(99) == []
    
    def test_handle_new_vertex_with_parent(self, rig):
        """Test handling new vertex with parent (split scenario)."""
        # Setup parent vertex
        rig.set_vertex_weight(0, 0, 0.5)
        rig.set_vertex_weight(0, 1, 0.5)
        
        rig.add_morph_target("smile")
        rig.set_morph_offset("smile", 0, (0.1, 0.0, 0.0))
        
        # Handle new vertex as child of 0
        rig.handle_new_vertex(new_vertex_id=99, parent_vertex_id=0)
        
        # Verify inheritance
        weights_99 = rig.get_vertex_weights(99)
        assert len(weights_99) == 2
        
        offset_99 = rig.get_morph_offset("smile", 99)
        assert offset_99 == (0.1, 0.0, 0.0)


# =====================================================================
# Deformation Tests
# =====================================================================

class TestDeformation:
    """Test deformation computation (skinning + morphs)."""
    
    def test_deform_no_weights(self, rig, mock_mesh):
        """Test deformation with no weights (should return original)."""
        bone_transforms = {0: Transform()}  # Identity transform
        
        deformed = rig.deform_mesh(bone_transforms)
        
        # Vertex 0 has no weights, should stay at (0, 0, 0)
        assert deformed[0] == mock_mesh.vertex_position(0)
    
    def test_deform_with_skinning(self, rig, mock_mesh):
        """Test deformation with weights and pose."""
        # Setup: vertex 0 influenced by bone 0
        rig.set_vertex_weight(0, 0, 1.0)
        
        # Create transform: translate bone 0 by (1, 0, 0)
        transform = Transform(translation=(1.0, 0.0, 0.0))
        bone_transforms = {0: transform}
        
        deformed = rig.deform_mesh(bone_transforms)
        
        # Vertex 0 at (0, 0, 0) should move to (1, 0, 0)
        assert deformed[0] == (1.0, 0.0, 0.0)
    
    def test_deform_with_morphs(self, rig, mock_mesh):
        """Test deformation with active morphs."""
        rig.add_morph_target("smile")
        rig.set_morph_offset("smile", 0, (0.0, 0.1, 0.0))
        rig.set_morph_active("smile", 1.0)  # Full blend
        
        bone_transforms = {}  # No skinning
        
        deformed = rig.deform_mesh(bone_transforms)
        
        # Vertex 0 at (0, 0, 0) + morph offset (0, 0.1, 0) = (0, 0.1, 0)
        assert deformed[0] == (0.0, 0.1, 0.0)
    
    def test_deform_skinning_and_morphs(self, rig, mock_mesh):
        """Test combined skinning and morphs."""
        rig.set_vertex_weight(0, 0, 1.0)
        
        rig.add_morph_target("smile")
        rig.set_morph_offset("smile", 0, (0.0, 0.1, 0.0))
        rig.set_morph_active("smile", 1.0)
        
        transform = Transform(translation=(1.0, 0.0, 0.0))
        bone_transforms = {0: transform}
        
        deformed = rig.deform_mesh(bone_transforms)
        
        # (0,0,0) -> skin to (1,0,0) -> morph offset (0,0.1,0) = (1, 0.1, 0)
        assert deformed[0] == (1.0, 0.1, 0.0)


# =====================================================================
# Test Summary / Running
# =====================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
