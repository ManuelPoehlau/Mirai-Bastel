"""MoveOperation: unified onto VertexTransformOperation base.

Bezug: V1_SPEC.md §4, Architecture Decision AD-003.

MoveOperation now inherits from VertexTransformOperation (WP-A),
consolidating with Rotate/Scale to eliminate duplication. The
transformation is pure translation: _transform_position() = pos + delta.
Pivot is never referenced in Move (move is pivot-independent by
construction, not by convention).
"""

from __future__ import annotations

from ..mesh import Position
from .transform import VertexTransformOperation


class MoveOperation(VertexTransformOperation):
    """Moves selected vertices by a delta passed to update().

    Inherits from VertexTransformOperation to share snapshot/commit/cancel
    machinery. Soft-selection falloff simplified to weight 1.0 per vertex
    for V1 (soft selection is independent behavior, not a mode) — structure
    holds the place for a future influence-map system without changing
    the lifecycle.

    Move is pivot-independent: _transform_position ignores self._pivot.
    """

    description = "Move Vertices"

    def _transform_position(self, pos: Position, delta: Position, **_) -> Position:
        return (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])
