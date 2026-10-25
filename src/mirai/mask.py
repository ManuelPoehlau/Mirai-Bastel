"""Mask Geometry: vertices protected from transforms (docs/future_ideas/MODELING.md, Priorität 1).

A mask is a per-vertex protection in (0, 1]; absent = 0 = editable. It is *not* a selection and not
mesh data: the selection, the topology and History never see it, and Undo does not revert it. It is
consulted once when a gesture begins (Move / Rotate / Scale, plain and Soft, Smooth / Relax):

- `m >= 1` (fully masked): the vertex never moves. As a seed it is dropped before the influence is
  computed, so a masked seed neither moves nor spreads Soft influence.
- `0 < m < 1`: a Soft influence weight `w` becomes `w * (1 - m)`. A seed that is not fully masked
  keeps its weight 1.0 (the Core requires exactly 1.0 for selected seam seeds).

Under a symmetry definition the effective mask of a mirror pair is the larger of the two members
(`effective_mask`), so the pair-consistency the Core's weighted transforms rely on holds even if only
one side was masked.

Stale IDs (deleted vertices) are dropped by `VertexMask.prune`; new vertices start unmasked.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Mapping

from core import Mesh, VertexId

from .soft_selection.symmetric import SymmetricInfluence
from .symmetry import CorrespondenceState, vertex_correspondence

#: Mask value at which a vertex is fully protected.
FULL = 1.0

MaskValues = Mapping[VertexId, float]


class VertexMask:
    """The artist's mask: `{vertex: value in (0, 1]}`. Empty = nothing masked."""

    def __init__(self) -> None:
        self._values: dict[VertexId, float] = {}

    def __bool__(self) -> bool:
        return bool(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def value(self, vertex: VertexId) -> float:
        return self._values.get(vertex, 0.0)

    def values(self) -> dict[VertexId, float]:
        return dict(self._values)

    def full(self) -> frozenset[VertexId]:
        """The fully masked vertices."""
        return frozenset(v for v, m in self._values.items() if m >= FULL)

    def set(self, vertices: Iterable[VertexId], value: float = FULL) -> None:
        value = float(value)
        if not 0.0 <= value <= 1.0:  # NaN fails as well
            raise ValueError(f"mask value must be in [0, 1], got {value!r}.")
        for v in vertices:
            if value > 0.0:
                self._values[v] = value
            else:
                self._values.pop(v, None)

    def clear(self) -> None:
        self._values.clear()

    def invert(self, mesh: Mesh) -> None:
        """`m -> 1 - m` on every vertex of `mesh` (editable becomes protected and back)."""
        inverted: dict[VertexId, float] = {}
        for v in mesh.all_vertex_ids():
            m = 1.0 - self._values.get(v, 0.0)
            if m > 0.0:
                inverted[v] = m
        self._values = inverted

    def prune(self, mesh: Mesh) -> None:
        self._values = {v: m for v, m in self._values.items() if mesh.is_valid_vertex(v)}


def effective_mask(mesh: Mesh, mask: VertexMask) -> dict[VertexId, float]:
    """What a gesture runs on: the mask without stale IDs, and under a symmetry definition the pair
    maximum, so both members of a mirror pair are protected alike."""
    values = {v: m for v, m in mask.values().items() if mesh.is_valid_vertex(v)}
    if not values or mesh.symmetry_definition is None:
        return values
    correspondence = vertex_correspondence(mesh)
    for v, m in list(values.items()):
        c = correspondence.get(v)
        if c is not None and c.state is CorrespondenceState.PAIRED and c.partner is not None:
            if m > values.get(c.partner, 0.0):
                values[c.partner] = m
    return values


def unblocked(vertices: Iterable[VertexId], mask: MaskValues | None) -> set[VertexId]:
    """`vertices` without the fully masked ones."""
    if not mask:
        return set(vertices)
    return {v for v in vertices if mask.get(v, 0.0) < FULL}


def mask_weights(
    weights: Mapping[VertexId, float], seeds: Iterable[VertexId], mask: MaskValues | None
) -> dict[VertexId, float]:
    """Soft weights under the mask: seeds keep their weight, every other `w -> w * (1 - m)`; weights
    that reach 0 are dropped (the Core wants weights in (0, 1])."""
    if not mask:
        return dict(weights)
    seed_set = set(seeds)
    result: dict[VertexId, float] = {}
    for v, w in weights.items():
        if v not in seed_set:
            w = w * (1.0 - mask.get(v, 0.0))
        if w > 0.0:
            result[v] = w
    return result


def mask_symmetric_influence(field: SymmetricInfluence, mask: MaskValues | None) -> SymmetricInfluence:
    """The symmetric field under the mask: seeds and their partners keep 1.0, the falloff is scaled,
    and the step categories shrink to the vertices that still carry a weight."""
    if not mask:
        return field
    weights = mask_weights(weights=field.weights, seeds=field.seeds | field.partners, mask=mask)
    keep = weights.keys()
    return replace(
        field,
        weights=weights,
        mirrored_vertex_ids=field.mirrored_vertex_ids & keep,
        seam_vertex_ids=field.seam_vertex_ids & keep,
        falloff_seam_vertex_ids=field.falloff_seam_vertex_ids & keep,
    )
