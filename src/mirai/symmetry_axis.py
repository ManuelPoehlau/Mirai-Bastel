"""Achsen-Symmetrie: die Definition, die die App setzt (E1/E3) — reine, GL-freie Funktionen.

AD-SYM-04 Slice A1 (Q-1 = E-1, Manu 2026-10-14): **verschoben, nicht kopiert** aus
`experiments/symmetry_lab/lab_symmetry.py` (K-2, AD-013 I1). Dort lagen sie seit dem
Symmetry Lab Slice 3 (Handoff §2 E1–E3); das Lab importiert sie jetzt von hier. Die
Symmetrie-*Semantik* (Correspondence, State) bleibt in `mirai.symmetry`; hier liegt nur,
wie eine Definition entsteht:

- **E1:** Ebene immer durch den Ursprung des Objekts, Normale exakt eine Achse des Objekts —
  Ursprung und Achsen der Mesh-Koordinaten (Objektraum). AD-021 Q-7 (Manu 2026-10-15): die
  Ebene dreht mit dem Objekt; ohne Platzierung ist das der Welt-Ursprung und eine Weltachse
  (AD-SYM-04, Addendum 2026-10-15). Eine andere Definition liest `current_axis` als Fehler
  (K-1), nie still als eine der Achsen (INV-5).
- **E3:** Die Seam wird einmal beim Wechsel auf eine Ebene abgeleitet — alle Edges, deren
  beide Endpunkte auf der Achse exakt `0.0` haben — und ist danach gespeicherte
  Deklaration (INV-1), keine laufende Positionsprüfung. Keine Toleranz (E4): ein nur fast
  symmetrisches Mesh kommt als `partial` hoch.
- **E2** (ein Zyklus-Schritt = ein Undo-Schritt) liegt beim Aufrufer:
  `SymmetryController.cycle` (Shift+S, `commands.SYMMETRY_CYCLE`) ruft
  `set_symmetry_axis` in seiner Mesh-Transaktion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from core import EdgeId, Mesh, SymmetryDefinition, VertexId

ORIGIN = (0.0, 0.0, 0.0)
AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}
AXIS_NORMALS = {
    "X": (1.0, 0.0, 0.0),
    "Y": (0.0, 1.0, 0.0),
    "Z": (0.0, 0.0, 1.0),
}
#: Shift+S-Reihenfolge (Artist A2 im Lab, Q-1 = E-1 für die App); `None` = Symmetrie aus.
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

    Eine Definition, die nicht aus E1 stammt, setzt niemand (nur `set_symmetry_axis`
    schreibt eine); sie würde als ValueError auffallen statt still als eine der Achsen
    gelesen zu werden (INV-5, AD-SYM-04 K-1).
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
    der Aufrufer ist eine Mesh-Transaktion von `Application` (E2)."""
    mesh.symmetry_definition = definition_for_axis(mesh, axis)


# -- Seam auf Ebene legen (Manu 2026-11-03, Lösung B) ---------------------------------------------
#
# Eine bei Symmetrie aus verschobene Mittel-Naht wird von E3 beim Wiedereinschalten nur lückenhaft
# gefunden (exakt `0.0`, keine Toleranz); dann teilt die Seam das Mesh nicht mehr in zwei Seiten und
# Re-Symmetrize lehnt ab. Der Artist wählt die Naht-Punkte selbst aus — die Auswahl ist die
# Entscheidung, keine Toleranz (E4 bleibt) — und legt sie exakt auf die Ebene. Die Seam wird nur
# ergänzt: jede Edge an einem gewählten Punkt, deren beide Endpunkte danach exakt auf der Ebene
# liegen. Bestehende Seam-Edges bleiben (auch solche, die Topologie-Operationen deklariert haben).


class SeamToPlaneRejected(ValueError):
    """Nicht möglich; `str(exc)` ist der Grund für die Statuszeile."""


@dataclass(frozen=True)
class SeamToPlanePlan:
    axis: str
    #: Vertex → neue Position (nur die, die nicht schon exakt auf der Ebene liegen).
    moves: dict
    #: Seam-Edges, die hinzukommen.
    added_seam_edges: frozenset
    #: Größter Abstand eines bewegten Punkts zur Ebene (Anzeige: war die Auswahl wirklich die Naht?).
    max_distance: float

    @property
    def is_empty(self) -> bool:
        return not self.moves and not self.added_seam_edges


def plan_seam_to_plane(mesh: Mesh, vertex_ids: Iterable[VertexId]) -> SeamToPlanePlan:
    axis = current_axis(mesh)
    if axis is None:
        raise SeamToPlaneRejected("Symmetrie aus")
    selected = {v for v in vertex_ids if mesh.is_valid_vertex(v)}
    if not selected:
        raise SeamToPlaneRejected("keine Auswahl")
    i = AXIS_INDEX[axis]
    moves = {}
    max_distance = 0.0
    for vid in selected:
        position = mesh.vertex_position(vid)
        if position[i] != 0.0:
            after = list(position)
            after[i] = 0.0
            moves[vid] = tuple(after)
            max_distance = max(max_distance, abs(position[i]))

    def on_plane(v: VertexId) -> bool:
        return v in selected or mesh.vertex_position(v)[i] == 0.0

    seam = mesh.symmetry_definition.seam_edges
    added = set()
    for vid in selected:
        for eid in mesh.vertex_edges(vid):
            if eid not in seam and all(on_plane(v) for v in mesh.edge_vertices(eid)):
                added.add(eid)
    return SeamToPlanePlan(axis, moves, frozenset(added), max_distance)


def apply_seam_to_plane(mesh: Mesh, plan: SeamToPlanePlan) -> None:
    """Setzt Positionen und ergänzte Seam — ohne History (der Aufrufer ist eine Mesh-Transaktion)."""
    for vid, position in plan.moves.items():
        mesh.set_vertex_position(vid, position)
    if plan.added_seam_edges:
        d = mesh.symmetry_definition
        mesh.symmetry_definition = SymmetryDefinition(
            d.plane_point, d.plane_normal, d.seam_edges | plan.added_seam_edges
        )
