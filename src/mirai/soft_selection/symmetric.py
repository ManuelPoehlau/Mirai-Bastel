"""Symmetric Soft Selection: the field and the step categories (AD-SYM-04 SS2, `PROVISIONAL`).

The caller side of the Core's weighted transforms (AD-SYM-05 §4.3, R6-3): the Core gets weights
and categories and trusts that the two members of a mirror pair carry the same weight and
opposite categories. This module is where that precondition is made true.

- **Field (D-1, R6-A).** One distance per mirror pair: the minimum over seeds ∪ mirrored seeds
  (the union field, `METRICS` over seeds ∪ partners) and over both members of the pair, never a
  sum; one weight `curve(distance)` per pair, assigned to both members; a seam vertex carries its
  own one weight. On an exactly mirror-symmetric edge graph the pair minimum changes nothing (the
  union field is already mirrored bit for bit, AD-SYM-05 §3.1); on a `partial` mesh it is what
  keeps the pair consistent (SS0: `man_with_shoes` X geodesic, 11 % of the union pair values
  differ). It takes the minimum of *distances*, never the maximum of two weights: `smooth` is not
  monotone in float. The union (not the seeds' plain field plus a partner lookup) so that an
  unpaired vertex on the mirrored side gets its own value from the mirrored seeds (D-2).
- **Categories (O-1 = K-side, `PROVISIONAL`).** By side of the plane relative to the seeds: a
  falloff vertex on the seeds' side (or on the plane, off the seam) takes the plain step, one on
  the other side the conjugate step — paired or not (D-2: an unpaired vertex takes its side's step
  with its own weight) — a declared seam vertex reached only by the falloff slides in the plane
  (`falloff_seam_vertex_ids`, P-a), a selected seam vertex keeps today's rules (`seam_vertex_ids`,
  weight 1.0). Pair-consistent without a tie rule: partners lie on opposite sides.
- **Refusals (`SoftSymmetryRefusal`, before anything moves).** D-2: a seed without a unique
  partner (unpaired or ambiguous; a seam seed is its own partner). K-side undefined, fail-closed
  until Manu answers (the one Artist question of SS2): seeds on both sides of the plane, or only on
  it (seam vertices do not count as a side).

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
#: O-1 open (Artist question): K-side is undefined for these selections; fail-closed until then.
BOTH_SIDES_TEXT = "Soft + Symmetrie: Auswahl auf beiden Seiten der Ebene (noch nicht festgelegt)"
SEAM_ONLY_TEXT = "Soft + Symmetrie: Auswahl nur auf der Mitte (noch nicht festgelegt)"


@dataclass(frozen=True)
class SymmetricInfluence:
    """The weights and categories one symmetric soft gesture runs on."""

    weights: dict[VertexId, float]
    seeds: frozenset[VertexId]
    #: Partners of the seeds (weight 1.0): the D-3 fallback set is seeds ∪ partners.
    partners: frozenset[VertexId]
    mirrored_vertex_ids: frozenset[VertexId]
    seam_vertex_ids: frozenset[VertexId]
    falloff_seam_vertex_ids: frozenset[VertexId]

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
    `compute_influence`); none left -> empty weights. Raises `SoftSymmetryRefusal` for the
    selections symmetric Soft does not define."""
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
    if len(sides) > 1:
        raise SoftSymmetryRefusal(BOTH_SIDES_TEXT)
    if not sides:
        raise SoftSymmetryRefusal(SEAM_ONLY_TEXT)
    (seed_side,) = sides
    partners = frozenset(corr[s].partner for s in paired)

    # D-1: seeds and their partners carry 1.0; every other pair one weight from its minimum.
    weights: dict[VertexId, float] = {v: 1.0 for v in valid_seeds | partners}
    if radius > 0.0:
        shape = curve_shape(curve, curve_power)
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
        elif _side(mesh.vertex_position(vid), plane_point, plane_normal) == -seed_side:
            mirrored.add(vid)
    return SymmetricInfluence(
        weights=weights,
        seeds=valid_seeds,
        partners=partners,
        mirrored_vertex_ids=frozenset(mirrored),
        seam_vertex_ids=selected_seam,
        falloff_seam_vertex_ids=frozenset(falloff_seam),
    )
