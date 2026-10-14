"""Achsen-Symmetrie: die Definition, die die App setzt (E1/E3) — reine, GL-freie Funktionen.

AD-SYM-04 Slice A1 (Q-1 = E-1, Manu 2026-10-14): **verschoben, nicht kopiert** aus
`experiments/symmetry_lab/lab_symmetry.py` (K-2, AD-013 I1). Dort lagen sie seit dem
Symmetry Lab Slice 3 (Handoff §2 E1–E3); das Lab importiert sie jetzt von hier. Die
Symmetrie-*Semantik* (Correspondence, State) bleibt in `mirai.symmetry`; hier liegt nur,
wie eine Definition entsteht:

- **E1:** Ebene immer durch den Welt-Ursprung, Normale exakt eine Weltachse. Eine andere
  Definition liest `current_axis` als Fehler (K-1), nie still als eine der Achsen (INV-5).
- **E3:** Die Seam wird einmal beim Wechsel auf eine Ebene abgeleitet — alle Edges, deren
  beide Endpunkte auf der Achse exakt `0.0` haben — und ist danach gespeicherte
  Deklaration (INV-1), keine laufende Positionsprüfung. Keine Toleranz (E4): ein nur fast
  symmetrisches Mesh kommt als `partial` hoch.
- **E2** (ein Zyklus-Schritt = ein Undo-Schritt) liegt beim Aufrufer:
  `Application._symmetry_cycle` (Shift+S, `commands.SYMMETRY_CYCLE`) ruft
  `set_symmetry_axis` in seiner Mesh-Transaktion.
"""

from __future__ import annotations

from typing import Optional

from core import EdgeId, Mesh, SymmetryDefinition

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
