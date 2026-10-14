"""Symmetric Soft Selection: the field and the step categories (AD-SYM-04 SS2, `PROVISIONAL`).

The caller side of the Core's weighted transforms (AD-SYM-05 §4.3, R6-3): the Core gets weights
and categories and trusts that the two members of a mirror pair carry the same weight and
opposite categories (or both plain where the explicit selection wins). This module is where that
precondition is made true.

- **Field (D-1, R6-A).** One distance per mirror pair: the minimum over seeds ∪ mirrored seeds
  (the union field, `METRICS` over seeds ∪ partners) and over both members of the pair, never a
  sum; one weight `curve(distance)` per pair, assigned to both members; a seam vertex carries its
  own one weight. On an exactly mirror-symmetric edge graph the pair minimum changes nothing (the
  union field is already mirrored bit for bit, AD-SYM-05 §3.1); on a `partial` mesh it is what
  keeps the pair consistent (SS0: `man_with_shoes` X geodesic, 11 % of the union pair values
  differ). It takes the minimum of *distances*, never the maximum of two weights: `smooth` is not
  monotone in float. The union (not the seeds' plain field plus a partner lookup) so that an
  unpaired vertex on the mirrored side gets its own value from the mirrored seeds (D-2).
- **Categories (O-1).** A declared seam vertex reached only by the falloff slides in the plane
  (`falloff_seam_vertex_ids`, P-a), a selected seam vertex keeps today's rules (`seam_vertex_ids`,
  weight 1.0), the seeds' own partners take the conjugate step. Every other falloff vertex, by the
  selection (Manu, 2026-10-14, AD-SYM-04 Decision record):
  - *seeds on one side* — **K-side**: the seeds' side (and off-seam vertices exactly on the plane)
    plain, the other side conjugate, paired or not (D-2: an unpaired vertex takes its side's step
    with its own weight). Pair-consistent without a tie rule.
  - *seeds on both sides* — **"the explicit selection wins"**, as plain W/E/R today
    (`mirrored_selection`): only partners of seeds whose partner is not selected are added; a
    falloff vertex takes the step of its nearest source (**K-near**: an explicit seed → plain, an
    added partner → conjugate), a tie goes to the explicit seed (plain). Pairs whose nearest
    sources are both explicit move alike, as two explicitly selected partners do today.
  - *seeds only on the seam* (seam vertices are no side) — **in the plane**: the side is
    irrelevant because every allowed step commutes with the mirror (Rotate/Scale keep today's
    seam rules through `seam_vertex_ids`: pivot on the plane, axis along the normal, scale keeping
    the plane); Move must keep its delta parallel to the plane, which the caller does
    (`in_plane_only`, `MoveTool`). The categories then use the positive side, which no step can
    tell from the other.
- **Refusal (`SoftSymmetryRefusal`, before anything moves).** D-2: a seed without a unique
  partner (unpaired or ambiguous; a seam seed is its own partner).

No cache (AR-1/INV-3, as `mirai.symmetry`): the correspondence is derived once per call, i.e.
once per gesture start; a caller that already holds it for the current geometry may hand it in.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from core import Mesh, VertexId

from ..symmetry import CorrespondenceState, VertexCorrespondence, vertex_correspondence
from .influence import METRICS, checked_radius, curve_shape


class SoftSymmetryRefusal(ValueError):
    """Symmetric Soft cannot run for this selection; raised before anything moves (texts
    `PROVISIONAL`). `Application` shows it like a seam refusal."""


#: D-2 (AD-SYM-04 §5.1): a seed without a partner refuses the gesture.
NO_PARTNER_TEXT = "Soft + Symmetrie: {count} gewählte Vertices ohne Spiegelpartner"


@dataclass(frozen=True)
class SymmetricInfluence:
    """The weights and categories one symmetric soft gesture runs on."""

    weights: dict[VertexId, float]
    seeds: frozenset[VertexId]
    #: Partners the selection adds (weight 1.0; a selected partner is a seed): the D-3 fallback
    #: set is seeds ∪ partners.
    partners: frozenset[VertexId]
    mirrored_vertex_ids: frozenset[VertexId]
    seam_vertex_ids: frozenset[VertexId]
    falloff_seam_vertex_ids: frozenset[VertexId]
    #: Seeds only on the seam: a Move must keep its delta parallel to the plane.
    in_plane_only: bool = False

    def symmetry_params(self, mesh: Mesh) -> dict[str, Any]:
        """`params["symmetry"]` for the Core op (the shape `resolve_symmetry` builds, plus the
        fourth category)."""
        definition = mesh.symmetry_definition
        return {
            "plane_normal": definition.plane_normal,
            "plane_point": definition.plane_point,
            "mirrored_vertex_ids": set(self.mirrored_vertex_ids),
            "seam_vertex_ids": set(self.seam_vertex_ids),
            "falloff_seam_vertex_ids": set(self.falloff_seam_vertex_ids),
        }


def _side(position, plane_point, plane_normal) -> int:
    distance = sum((p - o) * n for p, o, n in zip(position, plane_point, plane_normal))
    return (distance > 0.0) - (distance < 0.0)


def symmetric_influence(
    mesh: Mesh,
    seeds: Iterable[VertexId],
    radius: float,
    metric: str = "euclidean",
    curve: str = "smooth",
    curve_power: float = 1.0,
    correspondence: Mapping[VertexId, VertexCorrespondence] | None = None,
) -> SymmetricInfluence:
    """Weights and categories for symmetric Soft from the explicit seeds (module docstring).

    Needs a symmetry definition on `mesh`. Seeds the mesh no longer knows are skipped (as in
    `compute_influence`); none left -> empty weights. Raises `SoftSymmetryRefusal` for a seed
    without a partner (D-2)."""
    radius = checked_radius(metric, curve, radius)
    definition = mesh.symmetry_definition
    if definition is None:
        raise ValueError("symmetric_influence() needs a symmetry definition.")
    plane_point, plane_normal = definition.plane_point, definition.plane_normal
    valid_seeds = frozenset(s for s in seeds if mesh.is_valid_vertex(s))
    if not valid_seeds:
        return SymmetricInfluence({}, valid_seeds, frozenset(), frozenset(), frozenset(), frozenset())
    corr = vertex_correspondence(mesh) if correspondence is None else correspondence

    def state(vid: VertexId) -> CorrespondenceState | None:
        c = corr.get(vid)
        return None if c is None else c.state

    selected_seam = frozenset(s for s in valid_seeds if state(s) is CorrespondenceState.SEAM)
    paired = valid_seeds - selected_seam
    no_partner = [s for s in paired if state(s) is not CorrespondenceState.PAIRED]
    if no_partner:
        raise SoftSymmetryRefusal(NO_PARTNER_TEXT.format(count=len(no_partner)))
    sides = {_side(mesh.vertex_position(s), plane_point, plane_normal) for s in paired} - {0}
    both_sides = len(sides) > 1
    in_plane_only = not sides
    # Seam only: any side will do (module docstring); one side: K-side; both: K-near below.
    seed_side = 1 if len(sides) != 1 else next(iter(sides))
    # The explicit selection wins: a selected partner is a seed, not a partner.
    partners = frozenset(corr[s].partner for s in paired) - valid_seeds

    # D-1: seeds and their partners carry 1.0; every other pair one weight from its minimum.
    weights: dict[VertexId, float] = {v: 1.0 for v in valid_seeds | partners}
    from_seeds: dict[VertexId, float] = {}
    from_partners: dict[VertexId, float] = {}
    if radius > 0.0:
        shape = curve_shape(curve, curve_power)
        if both_sides:
            # K-near needs to know which source is nearest: the union as two fields.
            from_seeds = METRICS[metric](mesh, set(valid_seeds), radius)
            from_partners = METRICS[metric](mesh, set(partners), radius) if partners else {}
            distances = dict(from_seeds)
            for vid, d in from_partners.items():
                if d < distances.get(vid, math.inf):
                    distances[vid] = d
        else:
            distances = METRICS[metric](mesh, set(valid_seeds | partners), radius)
        for vid, d in distances.items():
            if vid in weights:
                continue  # a seed, a partner, or the second member of a pair already done
            c = corr.get(vid)
            partner = c.partner if c is not None and c.state is CorrespondenceState.PAIRED else None
            if partner is not None:
                d = min(d, distances.get(partner, math.inf))
            w = shape(1.0 - d / radius)
            if w > 0.0:
                weights[vid] = w
                if partner is not None:
                    weights[partner] = w

    mirrored: set[VertexId] = set()
    falloff_seam: set[VertexId] = set()
    for vid in weights:
        if vid in valid_seeds:
            continue  # plain, or a selected seam vertex (today's rules)
        if vid in partners:
            mirrored.add(vid)  # the seeds' own partners: as `mirrored_selection` today
        elif state(vid) is CorrespondenceState.SEAM:
            falloff_seam.add(vid)
        elif both_sides:
            if from_partners.get(vid, math.inf) < from_seeds.get(vid, math.inf):
                mirrored.add(vid)  # nearest source an added partner; a tie stays plain
        elif _side(mesh.vertex_position(vid), plane_point, plane_normal) == -seed_side:
            mirrored.add(vid)
    return SymmetricInfluence(
        weights=weights,
        seeds=valid_seeds,
        partners=partners,
        mirrored_vertex_ids=frozenset(mirrored),
        seam_vertex_ids=selected_seam,
        falloff_seam_vertex_ids=frozenset(falloff_seam),
        in_plane_only=in_plane_only,
    )
