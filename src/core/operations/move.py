"""MoveOperation: unified onto VertexTransformOperation base.

Bezug: V1_SPEC.md §4, Architecture Decision AD-003.

MoveOperation now inherits from VertexTransformOperation (WP-A),
consolidating with Rotate/Scale to eliminate duplication. The
transformation is pure translation: _transform_position() = pos + delta.
Pivot is never referenced in Move (move is pivot-independent by
construction, not by convention).

Symmetric Move (AD-SYM-02 §2.4, WP-SYM-01 Slice 2): the symmetry context
travels through the existing, generic `OperationContext.params["symmetry"]`
channel (same precedent as `pivot`) - no new field on OperationContext, no
MirrorResult structure. `mirai.interaction.tools.move.MoveTool` resolves it
before `begin()`: which of the affected vertices are mirrored partners
(inferred via `mirai.symmetry.vertex_correspondence()`, not explicitly
selected by the Artist) versus declared Seam vertices among the explicit
selection.

Three vertex categories, one Move interaction (AD-SYM-02 §2.4, Handoff §3.2 -
the open design question this slice resolves, documented here rather than
decided silently per M5):

- Directly selected vertices (plain): the ordinary `delta`.
- Mirrored partner vertices (`mirrored_vertex_ids`, CorrespondenceState.PAIRED,
  not themselves part of the Artist's explicit selection): the delta
  *vector* reflected across the plane normal, `d' = d - 2*(d·n)*n` - this is
  "the mirrored intent", not the same motion as the source side.
- Seam vertices among the selected (`seam_vertex_ids`, CorrespondenceState.SEAM):
  the delta projected onto the plane, `d_proj = d - (d·n)*n`, so a Seam
  vertex can never leave the plane (INV-2) - not even after many
  incremental update() calls, since projection is linear and therefore
  commutes with accumulation.

Resolved-but-not-prescribed edge case (Handoff §3.2): what if the Artist
selects BOTH a vertex and its mirrored partner explicitly? MoveTool never
adds a candidate partner to `mirrored_vertex_ids` if it is already part of
the explicit selection (see `mirrored_selection()` in `mirai.symmetry`) - the
Artist's explicit selection always wins over the inferred mirror preview.
Both vertices are then treated as plain, directly selected vertices and
receive the identical, unmirrored delta. Rationale: for an explicitly,
individually selected vertex, "the Artist's intent" IS to move exactly that
vertex by exactly that delta - inferring a mirrored role for it would
silently override a choice the Artist visibly made. Covered by
`tests/test_symmetric_move.py`.
"""

from __future__ import annotations

from ..ids import VertexId
from ..mesh import Position
from ..operation import OperationContext
from .transform import VertexTransformOperation


def _dot(a: Position, b: Position) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _mirror_vector(v: Position, normal: Position) -> Position:
    """Reflects the vector `v` across the plane through the origin whose
    unit normal is `normal` (AD-SYM-02 §2.4). Point-free on purpose: a
    *displacement* mirrors by its direction alone, `plane_point` never
    enters a vector reflection - only `mirror_position()` in
    `mirai.symmetry` (which mirrors a *position*) needs it."""
    d = _dot(v, normal)
    return (v[0] - 2.0 * d * normal[0], v[1] - 2.0 * d * normal[1], v[2] - 2.0 * d * normal[2])


def _project_onto_plane(v: Position, normal: Position) -> Position:
    """Removes the component of `v` along `normal` (INV-2 Seam constraint)."""
    d = _dot(v, normal)
    return (v[0] - d * normal[0], v[1] - d * normal[1], v[2] - d * normal[2])


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
    supports_symmetry = True

    def _on_begin(self, context: OperationContext) -> None:
        super()._on_begin(context)
        symmetry = context.params.get("symmetry")
        if symmetry is None:
            self._mirrored_vertex_ids: frozenset[VertexId] = frozenset()
            self._seam_vertex_ids: frozenset[VertexId] = frozenset()
            self._plane_normal: Position | None = None
        else:
            self._mirrored_vertex_ids = frozenset(symmetry.get("mirrored_vertex_ids", ()))
            self._seam_vertex_ids = frozenset(symmetry.get("seam_vertex_ids", ()))
            self._plane_normal = symmetry.get("plane_normal")

    def _transform_position(
        self, pos: Position, delta: Position, vertex_id: VertexId | None = None, **_
    ) -> Position:
        if vertex_id in self._seam_vertex_ids:
            delta = _project_onto_plane(delta, self._plane_normal)
        elif vertex_id in self._mirrored_vertex_ids:
            delta = _mirror_vector(delta, self._plane_normal)
        return (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])
