"""Bone: Simple hierarchical skeletal structure for rigging.

Minimal implementation: just enough for hierarchy representation.
Animation data (transforms, keyframes) deferred to later phases.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Bone:
    """A single bone in a skeletal hierarchy.
    
    V1 Properties:
    - id: Unique identifier within the rig
    - name: Human-readable name (e.g., "Jaw", "Skull", "Neck")
    - parent: Reference to parent bone (None if root)
    - children: List of child bones
    
    Deferred to Phase 3+:
    - Transform data (position, rotation, scale)
    - Animation keyframes
    - Inverse bind pose
    - Weight painting data
    """
    
    bone_id: int
    name: str
    parent: Optional[Bone] = None
    children: list[Bone] = field(default_factory=list)
    
    def __post_init__(self):
        """Ensure parent-child relationship is consistent."""
        if self.parent is not None and self not in self.parent.children:
            self.parent.children.append(self)
    
    def add_child(self, child: Bone) -> None:
        """Add a child bone to this bone's hierarchy."""
        if child.parent is not None and child in child.parent.children:
            child.parent.children.remove(child)
        child.parent = self
        if child not in self.children:
            self.children.append(child)
    
    def get_root(self) -> Bone:
        """Get the root bone of this hierarchy."""
        if self.parent is None:
            return self
        return self.parent.get_root()
    
    def get_chain_to_root(self) -> list[Bone]:
        """Get chain from this bone up to root (inclusive)."""
        chain = [self]
        current = self.parent
        while current is not None:
            chain.append(current)
            current = current.parent
        return chain
    
    def __repr__(self) -> str:
        parent_name = self.parent.name if self.parent else "None"
        return f"Bone({self.bone_id}, '{self.name}', parent={parent_name})"
