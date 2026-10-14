"""Symmetrie-Befund und Ebenen-Umriss des Labs — reine, GL-freie Funktionen.

Handoff Slice 3 §2 (E1–E4). Die Symmetrie-*Semantik* (Correspondence, State,
Spiegel-Vorschau) kommt unverändert aus `mirai.symmetry`. Das E1/E3-Setup
(Achsen, Seam-Ableitung, `current_axis`, `next_axis`, `set_symmetry_axis`) und der
Shift+S-Zyklus selbst sind seit AD-SYM-04 Slice A1 (2026-10-14) **verschoben** nach
`mirai.symmetry_axis` bzw. `Application` (`commands.SYMMETRY_CYCLE`); hier bleibt nur,
was das Lab anzeigt:

- **E4:** Keine Toleranz. Vertices knapp neben der Spiegelposition bleiben
  `UNPAIRED` und werden über `SymmetryReport` sichtbar gemacht (INV-10).
- `plane_outline_data` (Slice 3) zeichnet die Ebene als Rechteck-Umriss durch den
  Ursprung (E1), bemessen auf die Mesh-Bounds der beiden Achsen in der Ebene; seit
  WP-SYM-LAB-03 Slice 5 hier statt im gelöschten `lab_draw_data`.

Befund und Umriss ziehen mit AD-SYM-04 Slice A2 (Anzeige S-2) in die App.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Optional

from core import Mesh, VertexId
from mirai.mesh_geometry import mesh_bounds
from mirai.symmetry import (
    CorrespondenceState,
    SymmetryState,
    VertexCorrespondence,
    symmetry_state,
    vertex_correspondence,
)
from mirai.symmetry_axis import AXIS_INDEX, current_axis

#: Umriss ragt um diesen Anteil der größten In-Ebene-Ausdehnung über die Bounds.
PLANE_MARGIN = 0.1


@dataclass(frozen=True)
class SymmetryReport:
    """Was das Lab zur aktuellen Definition anzeigt (Statuszeile + Overlays)."""

    axis: Optional[str]
    state: SymmetryState
    seam: frozenset[VertexId] = frozenset()
    unpaired: frozenset[VertexId] = frozenset()
    ambiguous: frozenset[VertexId] = frozenset()
    #: Die Zuordnung, aus der der Befund stammt (für Partner-Lookups ohne neue
    #: Ableitung, Plan A3); None bei Symmetrie aus. Nicht Teil des Vergleichs.
    correspondence: Optional[Mapping[VertexId, VertexCorrespondence]] = field(
        default=None, compare=False, repr=False
    )


def symmetry_report(mesh: Mesh) -> SymmetryReport:
    axis = current_axis(mesh)
    if axis is None:
        return SymmetryReport(None, SymmetryState.OFF)
    by_state: dict[CorrespondenceState, set[VertexId]] = {s: set() for s in CorrespondenceState}
    correspondence = vertex_correspondence(mesh)
    for vid, corr in correspondence.items():
        by_state[corr.state].add(vid)
    return SymmetryReport(
        axis=axis,
        state=symmetry_state(mesh),
        seam=frozenset(by_state[CorrespondenceState.SEAM]),
        unpaired=frozenset(by_state[CorrespondenceState.UNPAIRED]),
        ambiguous=frozenset(by_state[CorrespondenceState.AMBIGUOUS]),
        correspondence=correspondence,
    )


def plane_outline_data(mesh: Mesh, axis: Optional[str]) -> list[float]:
    """Linien-Positionen (4 Linien à 2 Punkte, flach) des Ebenen-Umrisses; leer, wenn aus."""
    if axis is None:
        return []
    normal_i = AXIS_INDEX[axis]
    u, w = (i for i in range(3) if i != normal_i)
    lo, hi = mesh_bounds(mesh)
    pad = PLANE_MARGIN * max(hi[u] - lo[u], hi[w] - lo[w], 1e-6)
    corners2d = (
        (lo[u] - pad, lo[w] - pad),
        (hi[u] + pad, lo[w] - pad),
        (hi[u] + pad, hi[w] + pad),
        (lo[u] - pad, hi[w] + pad),
    )
    corners = []
    for cu, cw in corners2d:
        p = [0.0, 0.0, 0.0]
        p[u], p[w] = cu, cw
        corners.append(p)
    positions: list[float] = []
    for a, b in zip(corners, corners[1:] + corners[:1]):
        positions.extend(a)
        positions.extend(b)
    return positions
