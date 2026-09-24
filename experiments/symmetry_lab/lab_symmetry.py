"""Symmetrie-Zyklus und -Befund des Labs — reine, GL-freie Funktionen.

Handoff Slice 3 §2 (E1–E3). Die Symmetrie-*Semantik* (Correspondence,
State, Spiegel-Vorschau) kommt unverändert aus `mirai.symmetry`; hier liegt
nur, was das Lab selbst entscheidet:

- **E1:** Ebene immer durch den Welt-Ursprung, Normale exakt eine Weltachse.
- **E2:** Jeder Zyklus-Schritt ist genau ein Undo-Schritt — Snapshot-Muster
  `export_state()` → Definition setzen → `export_state()` →
  `MeshStateCommand`, nachgebaut (nicht importiert) nach
  `playground/topology_ops.py::split_selected_edge`, Stand `f4ad7d1`.
- **E3 (Lab-Annahme, keine Capability-Regel):** Die Seam wird einmal beim
  Wechsel auf eine Ebene abgeleitet — alle Edges, deren beide Endpunkte auf
  der Achse exakt `0.0` haben — und ist danach gespeicherte Deklaration
  (INV-1), keine laufende Positionsprüfung.
- **E4:** Keine Toleranz. Vertices knapp neben der Spiegelposition bleiben
  `UNPAIRED` und werden über `SymmetryReport` sichtbar gemacht (INV-10).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core import EdgeId, Mesh, Scene, SymmetryDefinition, VertexId
from core.operations.topology import MeshStateCommand
from mirai.symmetry import CorrespondenceState, SymmetryState, symmetry_state, vertex_correspondence

ORIGIN = (0.0, 0.0, 0.0)
AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}
AXIS_NORMALS = {
    "X": (1.0, 0.0, 0.0),
    "Y": (0.0, 1.0, 0.0),
    "Z": (0.0, 0.0, 1.0),
}
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
    `cycle_symmetry` setzt sie); sie würde als ValueError auffallen statt
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


def cycle_symmetry(scene: Scene) -> Optional[str]:
    """Schaltet einen Schritt weiter (aus → X → Y → Z → aus), genau ein History-Eintrag."""
    mesh = scene.mesh
    axis = next_axis(current_axis(mesh))
    before = mesh.export_state()
    mesh.symmetry_definition = definition_for_axis(mesh, axis)
    after = mesh.export_state()
    scene.history.push(
        MeshStateCommand(
            mesh=mesh,
            before_state=before,
            after_state=after,
            description=f"Symmetry {axis or 'off'}",
        )
    )
    return axis


@dataclass(frozen=True)
class SymmetryReport:
    """Was das Lab zur aktuellen Definition anzeigt (Statuszeile + Overlays)."""

    axis: Optional[str]
    state: SymmetryState
    seam: frozenset[VertexId] = frozenset()
    unpaired: frozenset[VertexId] = frozenset()
    ambiguous: frozenset[VertexId] = frozenset()


def symmetry_report(mesh: Mesh) -> SymmetryReport:
    axis = current_axis(mesh)
    if axis is None:
        return SymmetryReport(None, SymmetryState.OFF)
    by_state: dict[CorrespondenceState, set[VertexId]] = {s: set() for s in CorrespondenceState}
    for vid, corr in vertex_correspondence(mesh).items():
        by_state[corr.state].add(vid)
    return SymmetryReport(
        axis=axis,
        state=symmetry_state(mesh),
        seam=frozenset(by_state[CorrespondenceState.SEAM]),
        unpaired=frozenset(by_state[CorrespondenceState.UNPAIRED]),
        ambiguous=frozenset(by_state[CorrespondenceState.AMBIGUOUS]),
    )
