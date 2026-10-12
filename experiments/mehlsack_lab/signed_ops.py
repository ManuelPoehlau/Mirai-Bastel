"""Signed soft Move on the Core's protected hooks (handoff E4; AD-020 §3 Q2-D pattern).

`SignedSoftMoveOperation` is `mirai.soft_selection.ops.SoftMoveOperation` with one rule
changed: weights may be negative. Each vertex moves by `w · Δ` with `w` in [-1, 1],
`w != 0` (a negative weight moves opposite to the drag). No clamping to positive, no
`abs()`. It cannot subclass `SoftMoveOperation` because that op's `begin()` refuses
`w ∉ (0, 1]`, so it is built on `VertexTransformOperation` exactly the way AD-020 Q2-D
builds the soft ops:

- documented hooks only (`_on_begin` with a vertex view, `_transform_position` with
  `vertex_id=`); no Core private member and no Core private helper — checked by the
  AST scan in `tests/test_signed_ops.py`, same list as `tests/test_soft_selection_ops.py`;
- own state under the `_mehlsack_` prefix;
- the base keeps its `_weights` placeholder at 1.0, so the base loop never blends
  (tripwire test: one update on a `w < 1` vertex equals the closed form);
- one gesture = one History entry (`commit()` of the base, `VertexTransformCommand`).

For weights in (0, 1] the arithmetic is the one of `SoftMoveOperation` (same tuple
operations in the same order) — pinned bit for bit by the tests. Move is linear, so
N steps == 1 step up to float summation.
"""

from __future__ import annotations

import math
from typing import Any

from core import Mesh, OperationContext, VertexId
from core.operations.transform import VertexTransformOperation

Position = tuple[float, float, float]


class VertexView:
    """What the Core `_on_begin` reads from `context.selection`: `.vertices` only."""

    def __init__(self, vertex_ids: set[VertexId]) -> None:
        self.vertices = vertex_ids


class SignedSoftMoveOperation(VertexTransformOperation):
    """update(delta=...): each vertex moves by `w * delta`, `w` in [-1, 1] \\ {0}."""

    description = "Signed Soft Move Vertices"
    supports_symmetry = False

    def _on_begin(self, context: OperationContext) -> None:
        params = context.params
        if "symmetry" in params:
            raise ValueError("Signed soft move does not support symmetry (params['symmetry'] set).")
        influence = params.get("influence")
        if influence is None:
            raise ValueError("SignedSoftMoveOperation needs params['influence'].")
        mesh: Mesh = context.target
        weights: dict[VertexId, float] = {}
        for vid, w in influence.items():
            w = float(w)
            if not (math.isfinite(w) and -1.0 <= w <= 1.0 and w != 0.0):
                raise ValueError(f"Signed weight for {vid!r} must be in [-1, 1] and != 0, got {w!r}.")
            if mesh.is_valid_vertex(vid):  # stale IDs are skipped, not an error (S1 L10)
                weights[vid] = w
        viewed = {vid for vid in context.selection.vertices if mesh.is_valid_vertex(vid)}
        if viewed != set(weights):
            raise ValueError(
                "The selection view must be exactly the influenced vertex set "
                f"({len(viewed)} viewed, {len(weights)} weighted)."
            )
        inner = OperationContext(
            target=mesh, selection=VertexView(set(weights)), history=context.history, params=params,
        )
        super()._on_begin(inner)  # Core snapshot (+ pivot, unused by Move)
        self._mehlsack_weights = weights

    @property
    def weights(self) -> dict[VertexId, float]:
        """The signed influence the gesture runs on (fixed since `begin()`)."""
        return dict(self._mehlsack_weights)

    def _transform_position(
        self, pos: Position, delta: Position, vertex_id: VertexId | None = None, **_: Any
    ) -> Position:
        w = self._mehlsack_weights[vertex_id]
        if w != 1.0:
            delta = (w * delta[0], w * delta[1], w * delta[2])
        # The same tuple sum as `SoftMoveOperation` / `MoveOperation`.
        return (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])
