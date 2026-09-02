"""Living-Mesh Harness: Interactive workbench for rigging/skinning/morphing experiments.

Wires together:
  - Demo mesh (reproducible low-poly head)
  - RigController (bones, weights, morphs)
  - Deformation (LBS + morph blending)
  - Topology operations (split/collapse/connect)
  - Inspection (BEFORE → AFTER → DIFF)

This is a WORKBENCH, not the final machine.
It enables practical investigation of rigging behavior across topology changes.

No semantic decisions are baked in:
- Weight merge strategy is NOT decided here.
- Morph transfer semantics are NOT decided here.
- Deformation architecture is NOT finalized here.

The harness provides the hooks; the semantics are decided later.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in path for src.core imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.core.mesh import Mesh
from src.core.ids import VertexId, EdgeId, FaceId

from bone import Bone
from deformation import Transform, linear_blend_skinning, blend_morphs
from rig_controller import RigController, TopologySnapshot, TopologyChanges
from demo_mesh import (
    build_head_mesh,
    get_skull_vertices,
    get_jaw_vertices,
    get_neck_vertices,
)
from inspection import (
    capture_full,
    diff_topology,
    diff_rig,
    format_topology,
    format_rig,
    format_topology_diff,
    format_rig_diff,
    FullState,
    TopologyState,
    RigState,
)


class LivingMeshHarness:
    """Interactive workbench: mesh + rig + deformation + topology + inspection.

    Usage:
        harness = LivingMeshHarness()
        harness.setup_default_rig()
        harness.setup_default_weights()
        harness.setup_default_morphs()

        # Inspect initial state
        harness.inspect("initial")

        # Pose and deform
        harness.pose_jaw_open(0.5)
        deformed = harness.deform()

        # Topology operation
        harness.split_edge(edge_id)

        # Inspect after topology change
        harness.inspect("after_split")
    """

    def __init__(self, mesh: Optional[Mesh] = None):
        """Initialize harness with a mesh (default: demo head mesh).

        Args:
            mesh: Optional custom mesh. If None, uses build_head_mesh().
        """
        self.mesh = mesh if mesh is not None else build_head_mesh()
        self.rig = RigController(self.mesh)
        self._last_state: Optional[FullState] = None

    # =================================================================
    # Default Rig Setup
    # =================================================================

    def setup_default_rig(self) -> dict[str, int]:
        """Set up default 3-bone hierarchy: Neck → Skull → Jaw.

        Returns:
            Dict mapping bone names to bone IDs.
        """
        neck_id = self.rig.add_bone("Neck")       # Root
        skull_id = self.rig.add_bone("Skull", parent_id=neck_id)
        jaw_id = self.rig.add_bone("Jaw", parent_id=skull_id)
        return {"Neck": neck_id, "Skull": skull_id, "Jaw": jaw_id}

    def setup_default_weights(self, bones: Optional[dict[str, int]] = None) -> None:
        """Set up default skin weights by region.

        Skull vertices → Skull bone (1.0)
        Jaw vertices  → Jaw bone (1.0)
        Neck vertices → Neck bone (1.0)

        Args:
            bones: Bone name→ID mapping from setup_default_rig().
                   If None, assumes bones were already added with standard names.
        """
        if bones is None:
            bones = self._get_bone_ids_by_name()

        skull_id = bones.get("Skull", 1)
        jaw_id = bones.get("Jaw", 2)
        neck_id = bones.get("Neck", 0)

        for vid in get_skull_vertices():
            if self.mesh.is_valid_vertex(vid):
                self.rig.set_vertex_weight(vid, skull_id, 1.0)

        for vid in get_jaw_vertices():
            if self.mesh.is_valid_vertex(vid):
                self.rig.set_vertex_weight(vid, jaw_id, 1.0)

        for vid in get_neck_vertices():
            if self.mesh.is_valid_vertex(vid):
                self.rig.set_vertex_weight(vid, neck_id, 1.0)

    def setup_default_morphs(self) -> None:
        """Set up default morph targets: smile, jaw_open.

        Smile: move jaw vertices outward (x direction).
        Jaw Open: move jaw vertices downward (y direction).
        """
        jaw_verts = get_jaw_vertices()

        self.rig.add_morph_target("smile")
        self.rig.add_morph_target("jaw_open")

        for vid in jaw_verts:
            if self.mesh.is_valid_vertex(vid):
                # Smile: slight outward movement
                pos = self.mesh.vertex_position(vid)
                x_dir = 0.1 if pos[0] > 0 else -0.1
                self.rig.set_morph_offset("smile", vid, (x_dir, 0.0, 0.05))

                # Jaw open: downward movement
                self.rig.set_morph_offset("jaw_open", vid, (0.0, -0.2, 0.0))

    def _get_bone_ids_by_name(self) -> dict[str, int]:
        """Get bone IDs indexed by name."""
        return {bone.name: bone_id for bone_id, bone in self.rig.bones.items()}

    # =================================================================
    # Pose & Deform
    # =================================================================

    def pose_bone(self, bone_id: int, translation: tuple[float, float, float] = (0, 0, 0),
                  rotation_matrix: Optional[list[list[float]]] = None) -> dict[int, Transform]:
        """Create a single-bone pose (all other bones identity).

        Args:
            bone_id: Which bone to transform.
            translation: (x, y, z) translation.
            rotation_matrix: Optional 3x3 rotation matrix.

        Returns:
            Dict mapping bone_id → Transform (for use with deform()).
        """
        transforms = {}
        for bid in self.rig.bones:
            if bid == bone_id:
                transforms[bid] = Transform(translation=translation, rotation_matrix=rotation_matrix)
            else:
                transforms[bid] = Transform.identity()
        return transforms

    def pose_jaw_open(self, amount: float = 0.5) -> dict[int, Transform]:
        """Pose: translate jaw bone downward.

        Args:
            amount: Translation amount (0 = closed, 1 = fully open).

        Returns:
            Bone transforms for deformation.
        """
        bones = self._get_bone_ids_by_name()
        jaw_id = bones.get("Jaw")
        if jaw_id is None:
            return {}
        return self.pose_bone(jaw_id, translation=(0.0, -0.3 * amount, 0.0))

    def deform(self, bone_transforms: Optional[dict[int, Transform]] = None) -> dict:
        """Apply deformation (skinning + morphs).

        Args:
            bone_transforms: Dict mapping bone_id → Transform.
                           If None, uses identity transforms.

        Returns:
            Dict mapping vertex_id → deformed position.
        """
        if bone_transforms is None:
            bone_transforms = {bid: Transform.identity() for bid in self.rig.bones}
        return self.rig.deform_mesh(bone_transforms)

    # =================================================================
    # Topology Operations
    # =================================================================

    def split_edge(self, edge_id: EdgeId) -> tuple[VertexId, EdgeId, EdgeId]:
        """Split an edge and return the result.

        NOTE: This does NOT automatically update rig weights/morphs.
        The caller must decide how to handle the new vertex.

        Args:
            edge_id: Edge to split.

        Returns:
            (new_vertex_id, new_edge_a, new_edge_b)
        """
        return self.mesh.split_edge(edge_id)

    def collapse_edge(self, edge_id: EdgeId) -> VertexId:
        """Collapse an edge and return the survivor vertex.

        NOTE: This does NOT automatically update rig weights/morphs.
        The caller must decide how to handle the deleted vertex.

        Args:
            edge_id: Edge to collapse.

        Returns:
            Survivor vertex ID.
        """
        return self.mesh.collapse_edge(edge_id)

    def connect_vertices(self, face_id: FaceId, v_a: VertexId, v_b: VertexId) -> tuple:
        """Connect two vertices in a face.

        Args:
            face_id: Face containing both vertices.
            v_a, v_b: Vertices to connect.

        Returns:
            (new_edge_id, new_face_1_id, new_face_2_id)
        """
        return self.mesh.connect_vertices(face_id, v_a, v_b)

    # =================================================================
    # Inspection
    # =================================================================

    def capture(self, label: str = "") -> FullState:
        """Capture current full state."""
        state = capture_full(self.mesh, self.rig, label)
        self._last_state = state
        return state

    def inspect(self, label: str = "") -> FullState:
        """Capture and print current state."""
        state = self.capture(label)
        print("\n" + "=" * 70)
        print(f"STATE: {label}")
        print("=" * 70)
        print(format_topology(state.topology))
        print(format_rig(state.rig))
        return state

    def compare_states(self, before: FullState, after: FullState) -> None:
        """Print BEFORE → AFTER → DIFF report."""
        from inspection import print_before_after
        print_before_after(before, after)

    def snapshot_topology(self, label: str = "") -> TopologySnapshot:
        """Take a topology snapshot (for change detection)."""
        return self.rig.take_topology_snapshot(label)

    def detect_changes(self) -> TopologyChanges:
        """Detect topology changes since last snapshot."""
        return self.rig.detect_topology_changes()


# =================================================================
# Convenience: Full Setup
# =================================================================

def create_default_harness() -> LivingMeshHarness:
    """Create a fully configured LivingMeshHarness with default rig.

    Returns:
        Harness with:
        - Demo head mesh
        - 3-bone hierarchy (Neck → Skull → Jaw)
        - Default weights (by region)
        - Default morphs (smile, jaw_open)
    """
    harness = LivingMeshHarness()
    harness.setup_default_rig()
    harness.setup_default_weights()
    harness.setup_default_morphs()
    return harness
