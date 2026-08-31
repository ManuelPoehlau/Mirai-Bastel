"""Deformation: Skinning and Morph-Target computation utilities.

V1 Implementation: Linear Blend Skinning (LBS) only.
Deferred: Dual-Quaternion Skinning, Advanced Blending Modes.
"""

from __future__ import annotations
from typing import Tuple

Position = Tuple[float, float, float]


class Transform:
    """Minimal rigid transform representation.
    
    V1: 3x3 rotation + 3D translation.
    Deferred: Scale, shear, full 4x4 matrix representation.
    """
    
    def __init__(self, translation: Position = (0, 0, 0), rotation_matrix: list[list[float]] | None = None):
        """Initialize transform.
        
        Args:
            translation: (x, y, z) offset
            rotation_matrix: 3x3 row-major matrix; defaults to identity
        """
        self.translation = translation
        
        if rotation_matrix is None:
            # Identity matrix
            self.rotation = [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ]
        else:
            self.rotation = rotation_matrix
    
    @staticmethod
    def identity() -> Transform:
        """Create identity transform."""
        return Transform()
    
    def apply(self, position: Position) -> Position:
        """Apply transform to a position: p' = R*p + t
        
        Args:
            position: (x, y, z)
        
        Returns:
            Transformed (x, y, z)
        """
        x, y, z = position
        rot = self.rotation
        tx, ty, tz = self.translation
        
        # Matrix-vector multiply: R * p
        x_rot = rot[0][0] * x + rot[0][1] * y + rot[0][2] * z
        y_rot = rot[1][0] * x + rot[1][1] * y + rot[1][2] * z
        z_rot = rot[2][0] * x + rot[2][1] * y + rot[2][2] * z
        
        # Add translation
        return (x_rot + tx, y_rot + ty, z_rot + tz)


def linear_blend_skinning(
    vertex_position: Position,
    bone_weights: list[tuple[int, float]],
    bone_transforms: dict[int, Transform]
) -> Position:
    """Compute Linear Blend Skinning (LBS) for a single vertex.
    
    LBS = sum(weight[i] * Transform[i] * position) / sum(weight[i])
    
    Args:
        vertex_position: Original vertex position (x, y, z)
        bone_weights: List of (bone_id, weight) tuples
        bone_transforms: Dict mapping bone_id → Transform
    
    Returns:
        Deformed vertex position
    
    Note: If no weights or no transforms, returns original position.
    """
    if not bone_weights:
        return vertex_position
    
    deformed = (0.0, 0.0, 0.0)
    total_weight = 0.0
    
    for bone_id, weight in bone_weights:
        if weight == 0.0:
            continue
        
        if bone_id not in bone_transforms:
            # Bone has no transform; skip (bone not in current pose)
            continue
        
        transform = bone_transforms[bone_id]
        transformed = transform.apply(vertex_position)
        
        # Accumulate: deformed += weight * transformed
        deformed = (
            deformed[0] + weight * transformed[0],
            deformed[1] + weight * transformed[1],
            deformed[2] + weight * transformed[2],
        )
        total_weight += weight
    
    if total_weight > 0.0:
        # Normalize by total weight
        deformed = (
            deformed[0] / total_weight,
            deformed[1] / total_weight,
            deformed[2] / total_weight,
        )
    else:
        # No valid weights; return original position
        deformed = vertex_position
    
    return deformed


def apply_morph_offset(
    vertex_position: Position,
    morph_offset: Position | None
) -> Position:
    """Apply morph-target offset to a vertex.
    
    Args:
        vertex_position: Base position
        morph_offset: Offset (dx, dy, dz), or None for no offset
    
    Returns:
        Position + offset (if offset exists)
    """
    if morph_offset is None:
        return vertex_position
    
    return (
        vertex_position[0] + morph_offset[0],
        vertex_position[1] + morph_offset[1],
        vertex_position[2] + morph_offset[2],
    )


def blend_morphs(
    base_position: Position,
    active_morphs: dict[str, float],
    morph_data: dict[str, dict[int, Position]],  # morph_name -> {vertex_id -> offset}
    vertex_id: int
) -> Position:
    """Blend multiple morph-targets by their activations.
    
    Result = base + sum(morph_weight[i] * morph_offset[i])
    
    Args:
        base_position: Starting position
        active_morphs: Dict mapping morph_name → blend_weight (0-1)
        morph_data: Dict mapping morph_name → {vertex_id → offset}
        vertex_id: Which vertex to blend
    
    Returns:
        Blended position
    """
    result = base_position
    
    for morph_name, blend_weight in active_morphs.items():
        if blend_weight == 0.0:
            continue
        
        if morph_name not in morph_data:
            # Morph doesn't have data for this vertex
            continue
        
        if vertex_id not in morph_data[morph_name]:
            # This vertex not affected by this morph
            continue
        
        offset = morph_data[morph_name][vertex_id]
        result = (
            result[0] + blend_weight * offset[0],
            result[1] + blend_weight * offset[1],
            result[2] + blend_weight * offset[2],
        )
    
    return result
