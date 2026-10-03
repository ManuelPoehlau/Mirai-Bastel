"""Symmetrie-Zyklus und -Befund des Labs — reine, GL-freie Funktionen.

Handoff Slice 3 §2 (E1–E3). Die Symmetrie-*Semantik* (Correspondence,
State, Spiegel-Vorschau) kommt unverändert aus `mirai.symmetry`; hier liegt
nur, was das Lab selbst entscheidet:

- **E1:** Ebene immer durch den Welt-Ursprung, Normale exakt eine Weltachse.
- **E2:** Jeder Zyklus-Schritt ist genau ein Undo-Schritt. Seit WP-SYM-LAB-03
  schreibt ihn `Application.apply_mesh_change` (H3) mit `set_symmetry_axis` als
  `mutate` (`lab_app`); das Lab pusht selbst nichts (H2-R4). Das frühere
  `cycle_symmetry` (eigener `MeshStateCommand`) ging in Slice 5 mit dem alten
  Dispatcher.
- **E3 (Lab-Annahme, keine Capability-Regel):** Die Seam wird einmal beim
  Wechsel auf eine Ebene abgeleitet — alle Edges, deren beide Endpunkte auf
  der Achse exakt `0.0` haben — und ist danach gespeicherte Deklaration
  (INV-1), keine laufende Positionsprüfung.
- **E4:** Keine Toleranz. Vertices knapp neben der Spiegelposition bleiben
  `UNPAIRED` und werden über `SymmetryReport` sichtbar gemacht (INV-10).

`plane_outline_data` (Slice 3) zeichnet die Ebene als Rechteck-Umriss durch den
Ursprung (E1), bemessen auf die Mesh-Bounds der beiden Achsen in der Ebene; seit
WP-SYM-LAB-03 Slice 5 hier statt im gelöschten `lab_draw_data`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Optional

from core import EdgeId, Mesh, SymmetryDefinition, VertexId
from mirai.mesh_geometry import mesh_bounds
from mirai.symmetry import (
    CorrespondenceState,
    SymmetryState,
    VertexCorrespondence,
    symmetry_state,
    vertex_correspondence,
)

ORIGIN = (0.0, 0.0, 0.0)
AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}
AXIS_NORMALS = {
    "X": (1.0, 0.0, 0.0),
    "Y": (0.0, 1.0, 0.0),
    "Z": (0.0, 0.0, 1.0),
}
#: Umriss ragt um diesen Anteil der größten In-Ebene-Ausdehnung über die Bounds.
PLANE_MARGIN = 0.1
#: Shift+S-Reihenfolge (Artist A2); `None` = Symmetrie aus.
SYMMETRY_CYCLE: tuple[Optional[str], ...] = (None, "X", "Y", "Z")


def derive_seam_edges(mesh: Mesh, axis: str) -> frozenset[EdgeId]:
    """E3: alle Edges, deren beide Endpunkte auf `axis` exakt 0.0 liegen."""
    i = AXIS_INDEX[axis]
    return frozenset(
        eid
        for eid in mesh.all_edge_ids()
        if all(mesh.vertex_position(v)[i] == 0.0 for v in mesh.edge_vertices(eid))
    )


def definition_for_axis(mesh: Mesh, axis: Optional[str]) -> Optional[SymmetryDefinition]:
    if axis is None:
        return None
    return SymmetryDefinition(
        plane_point=ORIGIN,
        plane_normal=AXIS_NORMALS[axis],
        seam_edges=derive_seam_edges(mesh, axis),
    )


def current_axis(mesh: Mesh) -> Optional[str]:
    """Achse der gesetzten Definition; `None` = aus.

    Eine Definition, die nicht aus E1 stammt, gibt es im Lab nicht (nur
    `set_symmetry_axis` setzt sie); sie würde als ValueError auffallen statt
    still als eine der Achsen gelesen zu werden (INV-5).
    """
    definition = mesh.symmetry_definition
    if definition is None:
        return None
    for axis, normal in AXIS_NORMALS.items():
        if definition.plane_normal == normal and definition.plane_point == ORIGIN:
            return axis
    raise ValueError(f"Symmetry Definition außerhalb von E1: {definition!r}")


def next_axis(axis: Optional[str]) -> Optional[str]:
    i = SYMMETRY_CYCLE.index(axis)
    return SYMMETRY_CYCLE[(i + 1) % len(SYMMETRY_CYCLE)]


def set_symmetry_axis(mesh: Mesh, axis: Optional[str]) -> None:
    """Setzt die Definition für `axis` (E1, Seam nach E3); `None` = aus. Keine History —
    der Aufrufer ist das `mutate` von `Application.apply_mesh_change` (`lab_app`)."""
    mesh.symmetry_definition = definition_for_axis(mesh, axis)


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
