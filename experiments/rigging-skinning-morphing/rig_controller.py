"""RigController: External rigging, skinning, and morph-target management.

V1 Scope:
- Manages bones, skinning weights, morph-targets independently
- Uses ONLY public Core Mesh APIs (read-only)
- No listeners/observers; topology changes detected via snapshots
- Deformation computed on-demand

Deferred:
- Automatic topology sync (requires Core extension)
- Undo/Redo integration
- Serialization of rig data
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from bone import Bone
from deformation import Transform, linear_blend_skinning, blend_morphs

# Type aliases
VertexId = int
EdgeId = int
FaceId = int
BoneId = int
Position = tuple[float, float, float]


@dataclass
class TopologySnapshot:
    """Captures mesh topology state at a point in time."""
    
    label: str = ""
    vertex_ids: frozenset[VertexId] = field(default_factory=frozenset)
    edge_ids: frozenset[EdgeId] = field(default_factory=frozenset)
    face_ids: frozenset[FaceId] = field(default_factory=frozenset)


@dataclass
class TopologyChanges:
    """Observed topology changes between two snapshots."""
    
    new_vertices: list[VertexId] = field(default_factory=list)
    deleted_vertices: list[VertexId] = field(default_factory=list)
    new_edges: list[EdgeId] = field(default_factory=list)
    deleted_edges: list[EdgeId] = field(default_factory=list)
    new_faces: list[FaceId] = field(default_factory=list)
    deleted_faces: list[FaceId] = field(default_factory=list)


class RigController:
    """External rigging system, fully independent from Core.Mesh.
    
    CORE API CONTRACT (from CORE_API_AUDIT.md):
    - Read-only: all_vertex_ids(), all_edge_ids(), all_face_ids()
    - Read-only: vertex_edges(), edge_vertices(), edge_faces(), face_vertices()
    - Never modify Core mesh directly
    - Topology changes inferred from before/after snapshots
    """
    
    def __init__(self, mesh):
        """Initialize RigController with a Mesh reference.
        
        Args:
            mesh: Mirai-Bastel Core.Mesh instance (read-only)
        """
        self.mesh = mesh
        
        # Bone hierarchy
        self.bones: dict[BoneId, Bone] = {}
        self._next_bone_id = 0
        
        # Skinning weights: vertex_id → [(bone_id, weight), ...]
        self.skinning_weights: dict[VertexId, list[tuple[BoneId, float]]] = {}
        
        # Morph targets: morph_name → {vertex_id → (dx, dy, dz)}
        self.morph_targets: dict[str, dict[VertexId, Position]] = {}
        
        # Active morph blend: morph_name → blend_weight (0-1)
        self.active_morphs: dict[str, float] = {}
        
        # Topology snapshots for change detection
        self.topology_snapshots: list[TopologySnapshot] = []
        self._last_snapshot_index = -1
    
    # =====================================================================
    # Bone Management
    # =====================================================================
    
    def add_bone(self, name: str, parent_id: Optional[BoneId] = None) -> BoneId:
        """Add a bone to the hierarchy.
        
        Args:
            name: Human-readable name (e.g., "Jaw", "Skull")
            parent_id: Parent bone ID, or None for root
        
        Returns:
            New bone ID
        """
        bone_id = self._next_bone_id
        self._next_bone_id += 1
        
        parent_bone = self.bones.get(parent_id) if parent_id is not None else None
        bone = Bone(bone_id=bone_id, name=name, parent=parent_bone)
        
        self.bones[bone_id] = bone
        return bone_id
    
    def get_bone(self, bone_id: BoneId) -> Optional[Bone]:
        """Get bone by ID."""
        return self.bones.get(bone_id)
    
    def get_bone_chain_to_root(self, bone_id: BoneId) -> list[Bone]:
        """Get chain from bone to root (inclusive)."""
        bone = self.bones.get(bone_id)
        if bone is None:
            return []
        return bone.get_chain_to_root()
    
    # =====================================================================
    # Skinning Weights Management
    # =====================================================================
    
    def set_vertex_weight(
        self,
        vertex_id: VertexId,
        bone_id: BoneId,
        weight: float
    ) -> None:
        """Set (or add) weight for a vertex to a bone.
        
        Args:
            vertex_id: Vertex to weight
            bone_id: Bone to weight to
            weight: Weight value (typically 0-1, but not enforced)
        """
        if vertex_id not in self.skinning_weights:
            self.skinning_weights[vertex_id] = []
        
        # Remove existing weight to this bone
        self.skinning_weights[vertex_id] = [
            (bid, w) for bid, w in self.skinning_weights[vertex_id] if bid != bone_id
        ]
        
        # Add new weight
        self.skinning_weights[vertex_id].append((bone_id, weight))
    
    def get_vertex_weights(self, vertex_id: VertexId) -> list[tuple[BoneId, float]]:
        """Get all weights for a vertex."""
        return list(self.skinning_weights.get(vertex_id, []))
    
    def clear_vertex_weights(self, vertex_id: VertexId) -> None:
        """Remove all weights from a vertex."""
        self.skinning_weights.pop(vertex_id, None)
    
    def inherit_weights(
        self,
        source_vertex: VertexId,
        target_vertex: VertexId
    ) -> None:
        """Copy weights from source to target (source's weights remain).
        
        Used when split() creates a new vertex (inherits from parent).
        """
        weights = self.get_vertex_weights(source_vertex)
        for bone_id, weight in weights:
            self.set_vertex_weight(target_vertex, bone_id, weight)
    
    # =====================================================================
    # Morph Target Management
    # =====================================================================
    
    def add_morph_target(self, name: str) -> None:
        """Create a new named morph-target."""
        if name not in self.morph_targets:
            self.morph_targets[name] = {}
    
    def set_morph_offset(
        self,
        morph_name: str,
        vertex_id: VertexId,
        offset: Position
    ) -> None:
        """Set vertex offset for a morph-target.
        
        Args:
            morph_name: Name of morph
            vertex_id: Vertex ID
            offset: (dx, dy, dz) offset
        """
        if morph_name not in self.morph_targets:
            self.add_morph_target(morph_name)
        
        self.morph_targets[morph_name][vertex_id] = offset
    
    def get_morph_offset(
        self,
        morph_name: str,
        vertex_id: VertexId
    ) -> Optional[Position]:
        """Get morph offset for a vertex, or None if not affected."""
        return self.morph_targets.get(morph_name, {}).get(vertex_id)
    
    def set_morph_active(self, morph_name: str, blend_weight: float) -> None:
        """Activate/deactivate a morph target.
        
        Args:
            morph_name: Name of morph
            blend_weight: Blend weight (0 = off, 1 = full, >1 allowed)
        """
        if blend_weight == 0.0:
            self.active_morphs.pop(morph_name, None)
        else:
            self.active_morphs[morph_name] = blend_weight
    
    # =====================================================================
    # Topology Change Detection (Snapshot-based)
    # =====================================================================
    
    def take_topology_snapshot(self, label: str = "") -> TopologySnapshot:
        """Capture current mesh topology state.
        
        Uses Core API: all_vertex_ids(), all_edge_ids(), all_face_ids()
        
        Args:
            label: Optional label for debugging
        
        Returns:
            Snapshot object
        """
        snapshot = TopologySnapshot(
            label=label,
            vertex_ids=frozenset(self.mesh.all_vertex_ids()),
            edge_ids=frozenset(self.mesh.all_edge_ids()),
            face_ids=frozenset(self.mesh.all_face_ids()),
        )
        self.topology_snapshots.append(snapshot)
        self._last_snapshot_index = len(self.topology_snapshots) - 1
        return snapshot
    
    def detect_topology_changes(self) -> TopologyChanges:
        """Compare current mesh state to last snapshot.
        
        Returns:
            TopologyChanges object with new/deleted vertices, edges, faces
        
        NOTE: Observational only. Don't assume operation type from results.
        Example: new_vertices has 1 entry, deleted_edges has 1 entry
                 → MIGHT be split(), but NOT guaranteed.
        """
        if self._last_snapshot_index < 0:
            # No previous snapshot
            return TopologyChanges()
        
        last = self.topology_snapshots[self._last_snapshot_index]
        
        current_vertices = frozenset(self.mesh.all_vertex_ids())
        current_edges = frozenset(self.mesh.all_edge_ids())
        current_faces = frozenset(self.mesh.all_face_ids())
        
        changes = TopologyChanges(
            new_vertices=list(current_vertices - last.vertex_ids),
            deleted_vertices=list(last.vertex_ids - current_vertices),
            new_edges=list(current_edges - last.edge_ids),
            deleted_edges=list(last.edge_ids - current_edges),
            new_faces=list(current_faces - last.face_ids),
            deleted_faces=list(last.face_ids - current_faces),
        )
        
        return changes
    
    # =====================================================================
    # Topology Queries (using Core API)
    # =====================================================================
    
    def query_vertex_topology(self, vertex_id: VertexId) -> dict:
        """Investigate vertex topology using Core APIs.
        
        Returns dict with:
        - connected_edges: list of edge IDs
        - connected_faces: inferred from edges
        - adjacent_vertices: computed from connected edges
        """
        findings = {
            "vertex_id": vertex_id,
            "connected_edges": [],
            "adjacent_vertices": set(),
            "connected_faces": set(),
        }
        
        # Use Core API: vertex_edges()
        edges = self.mesh.vertex_edges(vertex_id)
        findings["connected_edges"] = edges
        
        for edge_id in edges:
            # Use Core API: edge_vertices()
            v0, v1 = self.mesh.edge_vertices(edge_id)
            
            # Track adjacent vertices
            if v0 != vertex_id:
                findings["adjacent_vertices"].add(v0)
            if v1 != vertex_id:
                findings["adjacent_vertices"].add(v1)
            
            # Use Core API: edge_faces()
            faces = self.mesh.edge_faces(edge_id)
            findings["connected_faces"].update(faces)
        
        findings["adjacent_vertices"] = list(findings["adjacent_vertices"])
        findings["connected_faces"] = list(findings["connected_faces"])
        
        return findings
    
    def query_edge_topology(self, edge_id: EdgeId) -> dict:
        """Investigate edge using Core APIs."""
        findings = {
            "edge_id": edge_id,
            "vertices": None,
            "faces": [],
        }
        
        # Use Core API: edge_vertices()
        v0, v1 = self.mesh.edge_vertices(edge_id)
        findings["vertices"] = (v0, v1)
        
        # Use Core API: edge_faces()
        findings["faces"] = self.mesh.edge_faces(edge_id)
        
        return findings
    
    # =====================================================================
    # Topology Event Handling
    # =====================================================================
    
    def handle_vertex_deletion(self, vertex_id: VertexId) -> None:
        """Clean up rig data when a vertex is deleted.
        
        Called after detecting deleted_vertices in topology changes.
        """
        # Remove weights
        self.skinning_weights.pop(vertex_id, None)
        
        # Remove from all morphs
        for morph_name in self.morph_targets:
            self.morph_targets[morph_name].pop(vertex_id, None)
    
    def handle_new_vertex(
        self,
        new_vertex_id: VertexId,
        parent_vertex_id: Optional[VertexId] = None
    ) -> None:
        """Handle new vertex created by topology operation.
        
        Args:
            new_vertex_id: ID of new vertex
            parent_vertex_id: If known, inherit weights from parent
        """
        if parent_vertex_id is not None:
            self.inherit_weights(parent_vertex_id, new_vertex_id)
            
            # Also inherit morph offsets
            for morph_name in self.morph_targets:
                offset = self.get_morph_offset(morph_name, parent_vertex_id)
                if offset is not None:
                    self.set_morph_offset(morph_name, new_vertex_id, offset)
    
    # =====================================================================
    # Deformation Computation
    # =====================================================================
    
    def deform_mesh(
        self,
        bone_transforms: dict[BoneId, Transform]
    ) -> dict[VertexId, Position]:
        """Apply rigging and morphs to mesh vertices.
        
        Args:
            bone_transforms: Dict mapping bone_id → Transform
        
        Returns:
            Dict mapping vertex_id → deformed position
        """
        deformed = {}
        
        for vertex_id in self.mesh.all_vertex_ids():
            # Get base position
            base_pos = self.mesh.vertex_position(vertex_id)
            
            # Apply skinning (if weights exist)
            weights = self.get_vertex_weights(vertex_id)
            if weights:
                skinned_pos = linear_blend_skinning(base_pos, weights, bone_transforms)
            else:
                skinned_pos = base_pos
            
            # Apply active morphs
            morphed_pos = blend_morphs(
                skinned_pos,
                self.active_morphs,
                self.morph_targets,
                vertex_id
            )
            
            deformed[vertex_id] = morphed_pos
        
        return deformed
    
    def get_deformed_position(
        self,
        vertex_id: VertexId,
        bone_transforms: dict[BoneId, Transform]
    ) -> Position:
        """Get deformed position for a single vertex."""
        base_pos = self.mesh.vertex_position(vertex_id)
        
        # Skinning
        weights = self.get_vertex_weights(vertex_id)
        if weights:
            skinned_pos = linear_blend_skinning(base_pos, weights, bone_transforms)
        else:
            skinned_pos = base_pos
        
        # Morphs
        morphed_pos = blend_morphs(
            skinned_pos,
            self.active_morphs,
            self.morph_targets,
            vertex_id
        )
        
        return morphed_pos
