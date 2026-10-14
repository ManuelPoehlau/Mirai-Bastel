"""Soft Move/Rotate/Scale over an influence map (WP-SOFT-01 S2a, AD-020; AD-SYM-05 SS1 M-b).

Since SS1 the weighting lives in the Core loop (`params["influence"]` on `MoveOperation`,
`RotateOperation`, `ScaleOperation`; rules and the documented deviation from the
incremental contract in `core/operations/transform.py`). These classes are thin subclasses
of the Core ops and hold only what the app path needs on top (AD-SYM-05 §5.1):

- the History label (`description`);
- `params["influence"]` is required;
- the stale-ID filter (S1 L10): IDs no longer in the mesh are dropped from the map and from
  the selection view before the Core sees them; the Core gets a *new* params dict with the
  filtered map and checks the rest (weights in (0, 1], keys == vertex set, pivot for
  Rotate/Scale);
- `weights`: the influence the gesture runs on.

Symmetry passes through to the Core (`supports_symmetry` is the Core op's `True`): since
AD-SYM-04 SS2 the caller hands pair-consistent weights and categories
(`soft_selection.symmetric`); the SS1 backstop that refused `params["symmetry"]` is gone with
the I-8 refusal in `Application`.

No arithmetic and no other state here. `Selection` is never written: the Core sees a private
vertex view, not the caller's `Selection`.
"""

from __future__ import annotations

from core import Mesh, MoveOperation, OperationContext, RotateOperation, ScaleOperation, VertexId


class _VertexView:
    """What the Core `_on_begin` reads from `context.selection`: `.vertices` only."""

    def __init__(self, vertex_ids: set[VertexId]) -> None:
        self.vertices = vertex_ids


class _SoftBegin:
    """Shared `begin()` of the three soft ops: filter stale IDs, then the Core op validates
    the weights (and the symmetry categories) and takes its snapshot of the influenced set."""

    def _on_begin(self, context: OperationContext) -> None:
        params = context.params
        influence = params.get("influence")
        if influence is None:
            raise ValueError(f"{type(self).__name__} needs params['influence'].")
        mesh: Mesh = context.target
        weights = {vid: w for vid, w in influence.items() if mesh.is_valid_vertex(vid)}
        viewed = {vid for vid in context.selection.vertices if mesh.is_valid_vertex(vid)}
        inner = OperationContext(
            target=mesh,
            selection=_VertexView(viewed),
            history=context.history,
            params={**params, "influence": weights},
        )
        super()._on_begin(inner)  # type: ignore[misc]  # Core: validate, snapshot, pivot
        self._soft_weights = {vid: float(w) for vid, w in weights.items()}

    @property
    def weights(self) -> dict[VertexId, float]:
        """The influence the gesture runs on (fixed since `begin()`)."""
        return dict(self._soft_weights)


class SoftMoveOperation(_SoftBegin, MoveOperation):
    """update(delta=...): each vertex moves by `w * delta`."""

    description = "Soft Move Vertices"


class SoftRotateOperation(_SoftBegin, RotateOperation):
    """update(axis=..., angle=...): each vertex rotates by `w * angle`."""

    description = "Soft Rotate Vertices"


class SoftScaleOperation(_SoftBegin, ScaleOperation):
    """update(factor=..., basis=None): per-axis `1 + w (F - 1)`, absolute for `w < 1`; the
    basis stays the same for the whole gesture (Core rule with weights)."""

    description = "Soft Scale Vertices"
