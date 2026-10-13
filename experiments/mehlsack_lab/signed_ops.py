"""Signed soft Move / Rotate / Scale on the Core's protected hooks (handoff E4, Slice 2b E19;
AD-020 §3 Q2-D pattern).

The three ops are `mirai.soft_selection.ops.SoftMove/Rotate/ScaleOperation` with one rule
changed: weights may be negative, `w` in [-1, 1] and `w != 0`. No clamping to positive, no
`abs()`. They cannot subclass the `src` ops because those refuse `w ∉ (0, 1]` in `begin()`,
so they are built on `VertexTransformOperation` exactly the way AD-020 Q2-D builds the soft
ops:

- documented hooks only (`_on_begin` with a vertex view, `_on_update`, `_transform_position`
  with `vertex_id=`); no Core private member and no Core private helper — checked by the
  AST scan in `tests/test_signed_ops.py`, same list as `tests/test_soft_selection_ops.py`;
- own state under the `_mehlsack_` prefix;
- the base keeps its `_weights` placeholder at 1.0, so the base loop never blends
  (tripwire test: one update on a `w < 1` vertex equals the closed form);
- one gesture = one History entry (`commit()` of the base, `VertexTransformCommand`).

Per-vertex rule:

- Move:   `w · Δ`, incremental (linear, so N steps == 1 step up to float summation).
- Rotate: rotation by `w · θ` around the gesture's axis and pivot, incremental (rotations
          about one axis compose additively, so N steps == 1 step); `w < 0` turns the
          opposite way.
- Scale:  per axis `g = 1 + w (F − 1)` (`params["scale_formula"] = "linear"`, the app's
          default) or `g = F ** w` (`"power"`), with `F` the factor accumulated since
          `begin()`. `w != 1` vertices are evaluated **absolutely from the start snapshot**
          — the linear formula is not multiplicative, so no incremental form is path
          independent. This is the documented deviation from the incremental contract of
          `core/operation.py`, the same one `SoftScaleOperation` makes, visibly. `g` is
          **not clamped**: under linear, `w < 0` reaches `g = 0` at `F = 1 + 1/|w|` (the
          vertices fall onto the pivot) and inverts beyond it (Slice 2b E19, part of what
          Manu compares). The basis is fixed for the whole gesture (AD-020 F6).

`w == 1` vertices take the plain Core arithmetic on the live position. For weights in
(0, 1] all three ops do the arithmetic of the `src` soft ops (same operations, same order)
— pinned bit for bit by the tests. Rotate and Scale need `params["pivot"]` (the caller
passes `primary_pivot(mesh, seeds)`; the Core default would be the centroid of the
influenced set).
"""

from __future__ import annotations

import math
from typing import Any, Iterable

from core import Mesh, OperationContext, VertexId
from core.operations.transform import VertexTransformOperation, rotate_around_axis
from mirai.soft_selection.ops import SCALE_FORMULAS  # ("linear", "power"), E19

Position = tuple[float, float, float]
Basis = tuple[Position, Position, Position]


class VertexView:
    """What the Core `_on_begin` reads from `context.selection`: `.vertices` only."""

    def __init__(self, vertex_ids: set[VertexId]) -> None:
        self.vertices = vertex_ids


class _SignedSoftOperation(VertexTransformOperation):
    """Shared `begin()`: validate the signed influence, filter stale IDs, then let the Core
    base take its snapshot of the influenced vertex set."""

    supports_symmetry = False
    _requires_pivot = False

    def _on_begin(self, context: OperationContext) -> None:
        params = context.params
        name = type(self).__name__
        if "symmetry" in params:
            raise ValueError(f"{name} does not support symmetry (params['symmetry'] set).")
        if self._requires_pivot and params.get("pivot") is None:
            raise ValueError(f"{name} needs params['pivot'] (primary_pivot of the seeds).")
        influence = params.get("influence")
        if influence is None:
            raise ValueError(f"{name} needs params['influence'].")
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
        super()._on_begin(inner)  # Core snapshot + pivot
        self._mehlsack_weights = weights
        self._mehlsack_start: dict[VertexId, Position] = {
            vid: mesh.vertex_position(vid) for vid in weights
        }

    @property
    def weights(self) -> dict[VertexId, float]:
        """The signed influence the gesture runs on (fixed since `begin()`)."""
        return dict(self._mehlsack_weights)


class SignedSoftMoveOperation(_SignedSoftOperation):
    """update(delta=...): each vertex moves by `w * delta`, `w` in [-1, 1] \\ {0}."""

    description = "Signed Soft Move Vertices"

    def _transform_position(
        self, pos: Position, delta: Position, vertex_id: VertexId | None = None, **_: Any
    ) -> Position:
        w = self._mehlsack_weights[vertex_id]
        if w != 1.0:
            delta = (w * delta[0], w * delta[1], w * delta[2])
        # The same tuple sum as `SoftMoveOperation` / `MoveOperation`.
        return (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])


class SignedSoftRotateOperation(_SignedSoftOperation):
    """update(axis=..., angle=...): each vertex rotates by `w * angle` (opposite for `w < 0`)."""

    description = "Signed Soft Rotate Vertices"
    _requires_pivot = True

    def _transform_position(
        self, pos: Position, axis: Position, angle: float, vertex_id: VertexId | None = None, **_: Any
    ) -> Position:
        w = self._mehlsack_weights[vertex_id]
        # The expression of `SoftRotateOperation`.
        return rotate_around_axis(pos, self.pivot, axis, angle if w == 1.0 else w * angle)


class SignedSoftScaleOperation(_SignedSoftOperation):
    """update(factor=..., basis=None): per-axis weighted factor, absolute for `w != 1`
    (module docstring). A different basis on a later update raises before anything moves."""

    description = "Signed Soft Scale Vertices"
    _requires_pivot = True

    def _on_begin(self, context: OperationContext) -> None:
        formula = context.params.get("scale_formula", "linear")
        if formula not in SCALE_FORMULAS:
            raise ValueError(f"scale_formula must be one of {SCALE_FORMULAS}, got {formula!r}.")
        super()._on_begin(context)
        self._mehlsack_formula = formula
        self._mehlsack_total: Position = (1.0, 1.0, 1.0)
        self._mehlsack_basis_set = False
        self._mehlsack_basis: Basis | None = None

    @property
    def scale_formula(self) -> str:
        return self._mehlsack_formula

    @property
    def total_factor(self) -> Position:
        """`F`: the factor accumulated since `begin()`."""
        return self._mehlsack_total

    def weighted_factor(self, w: float) -> Position:
        """`g` per axis for weight `w` at the current `F` (no clamp)."""
        return weighted_factor(w, self._mehlsack_total, self._mehlsack_formula)

    def collapsed_count(self) -> int:
        """`collapsed_count()` of this gesture so far (HUD, E20)."""
        return collapsed_count(self._mehlsack_weights, self._mehlsack_total, self._mehlsack_formula)

    def _on_update(self, factor: "float | Iterable[float]", basis: "Basis | None" = None,
                   **kwargs: Any) -> None:
        # Order as `SoftScaleOperation`: validate, accumulate, then the Core loop.
        f = _triple(factor)
        if self._mehlsack_basis_set and basis != self._mehlsack_basis:
            raise ValueError("SignedSoftScaleOperation needs the same basis for the whole gesture.")
        total = (self._mehlsack_total[0] * f[0], self._mehlsack_total[1] * f[1],
                 self._mehlsack_total[2] * f[2])
        if self._mehlsack_formula == "power" and any(t < 0.0 for t in total):
            raise ValueError("scale_formula 'power' (F ** w) is undefined for negative factors.")
        self._mehlsack_basis_set = True
        self._mehlsack_basis = basis
        self._mehlsack_total = total
        super()._on_update(factor=factor, basis=basis, **kwargs)

    def _transform_position(
        self, pos: Position, factor: "float | Iterable[float]", basis: "Basis | None" = None,
        vertex_id: VertexId | None = None, **_: Any,
    ) -> Position:
        w = self._mehlsack_weights[vertex_id]
        if w == 1.0:
            return _scale_about(self.pivot, pos, _triple(factor), basis)
        return _scale_about(self.pivot, self._mehlsack_start[vertex_id], self.weighted_factor(w), basis)


def weighted_factor(w: float, total: Position, formula: str) -> Position:
    """`g` per axis for weight `w` at the accumulated factor `total` (no clamp)."""
    if formula == "power":
        return tuple(f ** w for f in total)  # type: ignore[return-value]
    return tuple(1.0 + w * (f - 1.0) for f in total)  # type: ignore[return-value]


def collapsed_count(weights: dict, total: Position, formula: str) -> int:
    """Vertices whose `g` is `<= 0` on an axis that scales (`F != 1`): fallen onto the pivot
    plane (`g = 0`) or inverted through it (`g < 0`). Only the linear formula with `w < 0`
    can get there; power stays positive for `F > 0`. Observation aid for the HUD (E20)."""
    count = 0
    for w in weights.values():
        g = weighted_factor(w, total, formula)
        if any(g[i] <= 0.0 for i in range(3) if total[i] != 1.0):
            count += 1
    return count


def _triple(factor: "float | Iterable[float]") -> Position:
    """As `mirai.soft_selection.ops._triple`."""
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
    """Scale `pos` about `pivot` per axis — a copy of `mirai.soft_selection.ops._scale_about`
    (itself the arithmetic of the Core's `ScaleOperation`), pinned by the bit-identity tests
    against `SoftScaleOperation`: if either changes, those tests fail loudly."""
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
