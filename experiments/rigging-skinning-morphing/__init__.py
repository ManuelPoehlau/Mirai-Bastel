"""Rigging/Skinning/Morphing Experiment - Core Modules.

V1 Architecture: External RigController (no Core modifications).
"""

from .bone import Bone
from .deformation import Transform, linear_blend_skinning, apply_morph_offset, blend_morphs
from .rig_controller import (
    RigController,
    TopologySnapshot,
    TopologyChanges,
)

__all__ = [
    "Bone",
    "Transform",
    "linear_blend_skinning",
    "apply_morph_offset",
    "blend_morphs",
    "RigController",
    "TopologySnapshot",
    "TopologyChanges",
]
