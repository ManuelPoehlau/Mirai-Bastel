"""Soft Move/Rotate/Scale over an influence map (WP-SOFT-01 S2a, AD-020; AD-SYM-05 SS1 M-b).

Since SS1 the weighting lives in the Core loop (`params["influence"]` on `MoveOperation`,
`RotateOperation`, `ScaleOperation`; rules and the documented deviation from the
incremental contract in `core/operations/transform.py`). These classes are thin subclasses
of the Core ops and hold only what the app path needs on top (AD-SYM-05 §5.1):

- the History label (`description`);
- the symmetry backstop: `params["symmetry"]` present (even `None`) -> `ValueError` before
  anything moves (`Application` refuses the combination visibly, AD-SYM-04 I-8); it stays
  until SS2 lifts both;
- `params["influence"]` is required;
- the stale-ID filter (S1 L10): IDs no longer in the mesh are dropped from the map and from
  the selection view before the Core sees them; the Core gets a *new* params dict with the
  filtered map and checks the rest (weights in (0, 1], keys == vertex set, pivot for
  Rotate/Scale);
- `weights`: the influence the gesture runs on.

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
    """Shared `begin()` of the three soft ops: refuse symmetry, filter stale IDs, then the
    Core op validates the weights and takes its snapshot of the influenced vertex set."""

    supports_symmetry = False

    def _on_begin(self, context: OperationContext) -> None:
        params = context.params
        if "symmetry" in params:
            raise ValueError(
                "Soft Selection with symmetry is not supported yet (AD-020 §8, until "
                "AD-SYM-04 SS2): params['symmetry'] must not be set."
            )
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
