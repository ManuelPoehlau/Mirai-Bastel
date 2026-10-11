"""Soft Move/Rotate/Scale over an influence map (WP-SOFT-01 S2a, AD-020 Q2-D).

The weighted operations live in `src/mirai`, on the Core's protected template-method
hooks of `VertexTransformOperation` - no Core change (CORE_V1_FREEZE §1), no Core
*private* state and no private helper (checked by a source scan in
`tests/test_soft_selection_ops.py`). What they rely on is listed in AD-020 §3.3; the
tripwires that pin it are in the same test file:

- the base keeps its `_weights` placeholder at `1.0`, so its per-step blend never runs
  (these ops weight on their own; filling the placeholder in the Core would
  double-weight them - that is the promotion decision of AD-020 §12, not a drive-by);
- the base loop passes the live position and `vertex_id=` and forwards the update
  kwargs unchanged to `_transform_position()`;
- the base `_on_begin` reads `context.target`, `context.selection.vertices` and
  `params["pivot"]` only; its `_on_commit` labels the History entry with `description`.

Per-vertex rule, `w` from `params["influence"]`:

- Move:   `w * delta`, incremental (linear, so N steps == 1 step).
- Rotate: rotation by `w * angle` around the same axis and pivot, incremental
          (rotations about one axis compose additively, so N steps == 1 step).
- Scale:  per basis axis `1 + w * (F - 1)` (`params["scale_formula"] = "linear"`, the
          default and the only one the app uses) or `F ** w` (`"power"`, for the
          comparison suite), with `F` the factor accumulated since `begin()`. `w < 1` is
          evaluated absolutely from the start snapshot - the linear formula is not
          multiplicative, so no incremental form is path independent. This is the one
          place the "absolute evaluation" deviation from the incremental contract of
          `core/operation.py` is used, visibly.

`w == 1` vertices always take the plain Core arithmetic on the live position (the same
operations in the same order), so a radius-0 gesture (influence == seeds) is bit-identical
to the Core op when both get the same explicit pivot.

Other contracts: the vertex set is the influenced set (stale IDs in the map are filtered
before the Core sees them); the pivot is `params["pivot"]` and required for Rotate/Scale
(the Core default would be the centroid of the *influenced* set); `params["symmetry"]`
present (even `None`) -> `ValueError` before anything moves (the combination is refused
visibly by `Application`; this is the backstop). `Selection` is never written: the Core
sees a private vertex view, not the caller's `Selection`.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

from core import Mesh, OperationContext, VertexId
from core.operations.transform import VertexTransformOperation, rotate_around_axis

Position = tuple[float, float, float]
Basis = tuple[Position, Position, Position]

SCALE_FORMULAS = ("linear", "power")


class _VertexView:
    """What the Core `_on_begin` reads from `context.selection`: `.vertices` only."""

    def __init__(self, vertex_ids: set[VertexId]) -> None:
        self.vertices = vertex_ids


class _SoftOperation(VertexTransformOperation):
    """Shared `begin()` of the three soft ops: validate, filter, then let the Core base
    take its snapshot of the influenced vertex set."""

    supports_symmetry = False
    _requires_pivot = False

    def _on_begin(self, context: OperationContext) -> None:
        params = context.params
        if "symmetry" in params:
            raise ValueError(
                "Soft Selection with symmetry is not supported (AD-020 §8): "
                "params['symmetry'] must not be set."
            )
        if self._requires_pivot and params.get("pivot") is None:
            raise ValueError(
                f"{type(self).__name__} needs params['pivot'] from the primary selection; "
                "the Core default would be the centroid of the influenced set."
            )
        influence = params.get("influence")
        if influence is None:
            raise ValueError(f"{type(self).__name__} needs params['influence'].")
        mesh: Mesh = context.target
        weights: dict[VertexId, float] = {}
        for vid, w in influence.items():
            w = float(w)
            if not (0.0 < w <= 1.0):
                raise ValueError(f"Influence weight for {vid!r} must be in (0, 1], got {w!r}.")
            if mesh.is_valid_vertex(vid):  # stale IDs are skipped, not an error (S1 L10)
                weights[vid] = w
        viewed = {vid for vid in context.selection.vertices if mesh.is_valid_vertex(vid)}
        if viewed != set(weights):
            raise ValueError(
                "The selection view must be exactly the influenced vertex set "
                f"({len(viewed)} viewed, {len(weights)} weighted)."
            )
        inner = OperationContext(
            target=mesh,
            selection=_VertexView(set(weights)),
            history=context.history,
            params=params,
        )
        super()._on_begin(inner)  # Core snapshot + pivot
        self._soft_weights = weights
        self._soft_start: dict[VertexId, Position] = {
            vid: mesh.vertex_position(vid) for vid in weights
        }

    @property
    def weights(self) -> dict[VertexId, float]:
        """The influence the gesture runs on (fixed since `begin()`)."""
        return dict(self._soft_weights)


class SoftMoveOperation(_SoftOperation):
    """update(delta=...): each vertex moves by `w * delta`."""

    description = "Soft Move Vertices"

    def _transform_position(
        self, pos: Position, delta: Position, vertex_id: VertexId | None = None, **_: Any
    ) -> Position:
        w = self._soft_weights[vertex_id]
        if w != 1.0:
            delta = (w * delta[0], w * delta[1], w * delta[2])
        # The same tuple sum as `MoveOperation` (radius-0 identity).
        return (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])


class SoftRotateOperation(_SoftOperation):
    """update(axis=..., angle=...): each vertex rotates by `w * angle`."""

    description = "Soft Rotate Vertices"
    _requires_pivot = True

    def _transform_position(
        self,
        pos: Position,
        axis: Position,
        angle: float,
        vertex_id: VertexId | None = None,
        **_: Any,
    ) -> Position:
        w = self._soft_weights[vertex_id]
        return rotate_around_axis(pos, self.pivot, axis, angle if w == 1.0 else w * angle)


class SoftScaleOperation(_SoftOperation):
    """update(factor=..., basis=None): per-axis weighted factor.

    The basis must stay the same for the whole gesture (the absolute evaluation of
    `w < 1` vertices decomposes the start offset in it); a different basis on a later
    update raises `ValueError` before anything moves. The Core op itself accepts a new
    basis per update; no Production tool changes it mid-gesture (AD-020 F6)."""

    description = "Soft Scale Vertices"
    _requires_pivot = True

    def _on_begin(self, context: OperationContext) -> None:
        formula = context.params.get("scale_formula", "linear")
        if formula not in SCALE_FORMULAS:
            raise ValueError(f"scale_formula must be one of {SCALE_FORMULAS}, got {formula!r}.")
        super()._on_begin(context)
        self._soft_formula = formula
        self._soft_total: Position = (1.0, 1.0, 1.0)
        self._soft_basis_set = False
        self._soft_basis: Basis | None = None

    @property
    def scale_formula(self) -> str:
        return self._soft_formula

    @property
    def total_factor(self) -> Position:
        """The factor accumulated since `begin()` (what `w < 1` vertices are evaluated with)."""
        return self._soft_total

    def _weighted_factor(self, w: float) -> Position:
        if self._soft_formula == "power":
            return tuple(f ** w for f in self._soft_total)  # type: ignore[return-value]
        return tuple(1.0 + w * (f - 1.0) for f in self._soft_total)  # type: ignore[return-value]

    def _on_update(
        self,
        factor: "float | Iterable[float]",
        basis: "Basis | None" = None,
        **kwargs: Any,
    ) -> None:
        # Order matters (tested): validate, accumulate, then the Core loop.
        f = _triple(factor)
        if self._soft_basis_set and basis != self._soft_basis:
            raise ValueError("SoftScaleOperation needs the same basis for the whole gesture.")
        total = (self._soft_total[0] * f[0], self._soft_total[1] * f[1], self._soft_total[2] * f[2])
        if self._soft_formula == "power" and any(t < 0.0 for t in total):
            raise ValueError("scale_formula 'power' (F ** w) is undefined for negative factors.")
        self._soft_basis_set = True
        self._soft_basis = basis
        self._soft_total = total
        super()._on_update(factor=factor, basis=basis, **kwargs)

    def _transform_position(
        self,
        pos: Position,
        factor: "float | Iterable[float]",
        basis: "Basis | None" = None,
        vertex_id: VertexId | None = None,
        **_: Any,
    ) -> Position:
        w = self._soft_weights[vertex_id]
        if w == 1.0:
            return _scale_about(self.pivot, pos, _triple(factor), basis)
        # Absolute: the weighted total factor applied once to the start position.
        return _scale_about(self.pivot, self._soft_start[vertex_id], self._weighted_factor(w), basis)


def _triple(factor: "float | Iterable[float]") -> Position:
    if isinstance(factor, (int, float)):
        f = float(factor)
        return (f, f, f)
    values = tuple(float(v) for v in factor)
    if len(values) != 3:
        raise ValueError(f"Scale factor expects a float or 3 components, got {values!r}.")
    if not all(math.isfinite(v) for v in values):
        raise ValueError(f"Scale factor must be finite, got {values!r}.")
    return values  # type: ignore[return-value]


def _scale_about(pivot: Position, pos: Position, f: Position, basis: "Basis | None") -> Position:
    """Scale `pos` about `pivot`, per axis (world axes, or `basis` when given).

    The same operations in the same order as `ScaleOperation._apply`, so that `w == 1`
    vertices are bit-identical to the Core. A copy, pinned by the radius-0 identity test:
    if the Core formula ever changes (AD-014 changed it once), that test fails loudly."""
    q = (pos[0] - pivot[0], pos[1] - pivot[1], pos[2] - pivot[2])
    if basis is None:
        return (pivot[0] + f[0] * q[0], pivot[1] + f[1] * q[1], pivot[2] + f[2] * q[2])
    b0, b1, b2 = basis
    c0 = q[0] * b0[0] + q[1] * b0[1] + q[2] * b0[2]
    c1 = q[0] * b1[0] + q[1] * b1[1] + q[2] * b1[2]
    c2 = q[0] * b2[0] + q[1] * b2[1] + q[2] * b2[2]
    s0, s1, s2 = f[0] * c0, f[1] * c1, f[2] * c2
    scaled = (
        (b0[0] * s0 + b1[0] * s1) + b2[0] * s2,
        (b0[1] * s0 + b1[1] * s1) + b2[1] * s2,
        (b0[2] * s0 + b1[2] * s1) + b2[2] * s2,
    )
    return (pivot[0] + scaled[0], pivot[1] + scaled[1], pivot[2] + scaled[2])
