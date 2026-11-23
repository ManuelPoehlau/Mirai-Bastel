"""Smooth / Relax stroke (Brush research 2026-11-18 §6–§7, Manu 2026-11-23: O-1 = yes, O-2..O-8 as proposed) -
`PROVISIONAL`.

Headless: one dab of a stroke. The stroke itself (LMB while S / Alt+S is held, the hit under the cursor, spacing,
journal, cursor ring) lives in `controllers.gestures.SmoothGesture`. A dab is the existing Smooth / Relax plan
(`plan_smooth`) at the points of the hit face, with the Soft field around them (radius, curve, metric and flow of the
Soft settings, also while Soft itself is off: brush radius = Soft radius, O-3), applied a small fixed amount from the
*current* state - dabs accumulate (a dial computes from the press state instead). Symmetry: the stroke's one pairing
(`SymmetryPairing`, built at the press), the plan's driver rule writes each partner as its driver's mirror (O-7). The
mask holds points as in every tool; the selection does not limit a stroke (O-6).
"""

from __future__ import annotations

from typing import Iterable, Mapping

from core import Mesh, VertexId

from ..soft_selection import soft_weights
from ..symmetry_coordination import SymmetryPairing
from .smooth import plan_smooth

#: PROVISIONAL (agent-set, Manu's practical test decides): Smooth steps per dab (`plan_smooth` amount; one step moves a
#: point half-way to its neighbours' average at full weight). With the spacing below a point under the stroke's centre
#: line gets about four dabs per pass, about two steps.
DAB_AMOUNT = 0.5

#: PROVISIONAL: dab spacing as a fraction of the brush radius on screen (the Paint Room uses the same rule).
SPACING = 0.25

#: Dabs per pointer event at most (a fast drag fills the rest of its way with the last sample; Paint Room's limit).
MAX_DABS_PER_EVENT = 24

#: The smallest dab spacing in pixels (a tiny radius on screen must not dab per pixel).
MIN_SPACING_PX = 2.0


def dab(
    mesh: Mesh,
    seeds: Iterable[VertexId],
    soft,
    *,
    relax: bool,
    pairing: SymmetryPairing | None = None,
    mask: Mapping[VertexId, float] | None = None,
    amount: float = DAB_AMOUNT,
) -> set[VertexId]:
    """One dab at `seeds` (the hit face's points): their Soft field with `soft` (`SoftSettings`, its `world_radius`),
    `plan_smooth` on it from the current positions, `amount` steps written. Returns the moved points. Raises
    `SmoothRefused` / `SoftSymmetryRefusal` like the held gesture (a seed without a partner, only border or masked
    points): the caller skips that dab."""
    seeds = set(seeds)
    weights = soft_weights(mesh, seeds, soft, None if pairing is None else pairing.correspondence)
    plan = plan_smooth(
        mesh, seeds, relax=relax, weights=weights, mask=mask, index=None if pairing is None else pairing.index
    )
    positions = plan.positions(amount)
    for vid, position in positions.items():
        mesh.set_vertex_position(vid, position)
    return set(positions)
