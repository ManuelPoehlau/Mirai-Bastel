"""Weighted Move/Rotate/Scale over an influence map (WP-SOFT-01 S1).

The Core ops carry a soft-selection placeholder (`VertexTransformOperation._weights`,
all `1.0`) whose `_on_update` blends *per step* between the current position and the
transformed one: `pos + w * (T(pos) - pos)`. That blend is not path independent for
Rotate (a chord, not an arc: the vertex drifts towards the pivot) nor for Scale
(`(1 + w(f-1))^N != 1 + w(f^N - 1)`), so these subclasses replace `_on_update`
(E8, numbers in FINDINGS). Everything else - snapshot, pivot, commit/cancel, the
History command - is the Core machinery, reached through private members (E10;
the list is in FINDINGS as a dependency to resolve before any promotion).

Per-vertex rule (E6), `w` from `params["influence"]`:

- Move:   `w * delta`, incremental (linear, so N steps == 1 step).
- Rotate: rotation by `w * angle` around the same axis and pivot, incremental
          (rotations about one axis compose additively, so N steps == 1 step).
- Scale:  per basis axis `1 + w * (F - 1)` (`params["scale_formula"] = "linear"`, the
          handoff's working assumption) or `F ** w` (`"power"`, for comparison), with
          `F` the factor accumulated since `begin()`. `w < 1` is evaluated absolutely
          from the start snapshot - the linear formula is not multiplicative, so no
          incremental form is path independent. This is the one place the handoff's
          "internal absolute evaluation" allowance is used.

`w == 1` vertices always take the plain Core arithmetic on the live position, so a
radius-0 gesture (influence == seeds) is bit-identical to the Core op (handoff §5).

Other contracts: the vertex set is the influenced set (stale IDs skipped); the pivot is
`params["pivot"]` and required for Rotate/Scale (E7 - the Core default would be the
centroid of the *influenced* set); `params["symmetry"]` present -> `ValueError` (E9).
`Selection` is never written: the Core sees a private vertex view, not the caller's
`Selection`.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

from core import HistoryStack, Mesh, OperationContext, Selection, SelectionMode, VertexId
from core.operations.move import MoveOperation
from core.operations.transform import RotateOperation, ScaleOperation

from .influence import compute_influence, primary_pivot, seeds_from_selection

Position = tuple[float, float, float]

SCALE_FORMULAS = ("linear", "power")


class _InfluenceView:
    """What the Core `_on_begin` reads from `context.selection`: `.vertices` only."""

    def __init__(self, vertex_ids: set[VertexId]) -> None:
        self.vertices = vertex_ids


class _SoftMixin:
    """Shared `begin()` for the three soft ops: validate, then hand the Core a view
    of the influenced vertex set instead of the caller's selection."""

    _requires_pivot = False

    def _on_begin(self, context: OperationContext) -> None:
        params = context.params
        if "symmetry" in params:
            raise ValueError(
                "Soft Selection with symmetry is out of scope (WP-SOFT-01 E9): "
                "params['symmetry'] must not be set."
            )
        if self._requires_pivot and params.get("pivot") is None:
            raise ValueError(
                f"{type(self).__name__} needs params['pivot'] from the primary selection "
                "(E7); the Core default would be the centroid of the influenced set."
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
            if mesh.is_valid_vertex(vid):
                weights[vid] = w
        inner = OperationContext(
            target=mesh,
            selection=_InfluenceView(set(weights)),
            history=context.history,
            params=params,
        )
        super()._on_begin(inner)  # type: ignore[misc]
        self._weights = weights

    @property
    def weights(self) -> dict[VertexId, float]:
        return dict(self._weights)


class SoftMoveOperation(_SoftMixin, MoveOperation):
    """update(delta=...): each vertex moves by `w * delta`."""

    description = "Soft Move Vertices"
    supports_symmetry = False

    def _on_update(self, delta: Position, **kwargs: Any) -> None:
        for vid in self._vertex_ids:
            w = self._weights[vid]
            step = delta if w == 1.0 else (w * delta[0], w * delta[1], w * delta[2])
            pos = self._mesh.vertex_position(vid)
            self._mesh.set_vertex_position(
                vid, self._transform_position(pos, delta=step, vertex_id=vid)
            )


class SoftRotateOperation(_SoftMixin, RotateOperation):
    """update(axis=..., angle=...): each vertex rotates by `w * angle` (E6)."""

    description = "Soft Rotate Vertices"
    supports_symmetry = False
    _requires_pivot = True

    def _on_update(self, axis: Position, angle: float, **kwargs: Any) -> None:
        for vid in self._vertex_ids:
            w = self._weights[vid]
            pos = self._mesh.vertex_position(vid)
            self._mesh.set_vertex_position(
                vid, self._apply(pos, axis=axis, angle=angle if w == 1.0 else w * angle)
            )


class SoftScaleOperation(_SoftMixin, ScaleOperation):
    """update(factor=..., basis=None): per-axis weighted factor (E6).

    The basis must stay the same for the whole gesture (the absolute evaluation of
    `w < 1` vertices decomposes the start offset in it); a different basis on a later
    update raises `ValueError` before anything moves. The Core op itself accepts a new
    basis per update - see FINDINGS."""

    description = "Soft Scale Vertices"
    supports_symmetry = False
    _requires_pivot = True

    def _on_begin(self, context: OperationContext) -> None:
        formula = context.params.get("scale_formula", "linear")
        if formula not in SCALE_FORMULAS:
            raise ValueError(f"scale_formula must be one of {SCALE_FORMULAS}, got {formula!r}.")
        super()._on_begin(context)
        self._formula = formula
        self._total: Position = (1.0, 1.0, 1.0)
        self._basis_set = False
        self._basis: "tuple[Position, Position, Position] | None" = None

    @property
    def scale_formula(self) -> str:
        return self._formula

    @property
    def total_factor(self) -> Position:
        return self._total

    def _weighted_factor(self, w: float) -> Position:
        if self._formula == "power":
            return tuple(f ** w for f in self._total)  # type: ignore[return-value]
        return tuple(1.0 + w * (f - 1.0) for f in self._total)  # type: ignore[return-value]

    def _on_update(
        self,
        factor: "float | Iterable[float]",
        basis: "tuple[Position, Position, Position] | None" = None,
        **kwargs: Any,
    ) -> None:
        f = _as_triple(factor)
        if self._basis_set and basis != self._basis:
            raise ValueError("SoftScaleOperation needs the same basis for the whole gesture.")
        total = (self._total[0] * f[0], self._total[1] * f[1], self._total[2] * f[2])
        if self._formula == "power" and any(t < 0.0 for t in total):
            raise ValueError("scale_formula 'power' (F ** w) is undefined for negative factors.")
        self._basis_set = True
        self._basis = basis
        self._total = total
        for vid in self._vertex_ids:
            w = self._weights[vid]
            if w == 1.0:
                new = self._apply(self._mesh.vertex_position(vid), factor=factor, basis=basis)
            else:
                # Same Core arithmetic, applied once to the start position.
                new = self._apply(
                    self._start_positions[vid], factor=self._weighted_factor(w), basis=basis
                )
            self._mesh.set_vertex_position(vid, new)


def _as_triple(factor: "float | Iterable[float]") -> Position:
    # Local copy of the Core's private `_as_triple` (keeps the private surface small).
    if isinstance(factor, (int, float)):
        f = float(factor)
        return (f, f, f)
    values = tuple(float(v) for v in factor)
    if len(values) != 3:
        raise ValueError(f"Scale factor expects a float or 3 components, got {values!r}.")
    if not all(math.isfinite(v) for v in values):
        raise ValueError(f"Scale factor must be finite, got {values!r}.")
    return values  # type: ignore[return-value]


def soft_context(
    mesh: Mesh,
    selection: Selection,
    history: HistoryStack,
    radius: float,
    metric: str = "euclidean",
    curve: str = "smooth",
    mode: SelectionMode | None = None,
    **params: Any,
) -> OperationContext:
    """One place for E2/E3/E7: seeds from the selection, influence computed now (from the
    current = start positions), pivot from the seeds. The returned context carries the
    caller's `selection` untouched; the ops never read or write it."""
    seeds = seeds_from_selection(mesh, selection, mode)
    influence = compute_influence(mesh, seeds, radius, metric=metric, curve=curve)
    full = {"influence": influence}
    if seeds:
        full["pivot"] = primary_pivot(mesh, seeds)
    full.update(params)
    return OperationContext(target=mesh, selection=selection, history=history, params=full)
