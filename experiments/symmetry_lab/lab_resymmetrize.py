"""Re-Symmetrize-Plan und -Ausführung — reine, GL-freie Funktionen (Lab).

Handoff WP-SYM-LAB-01 Slice 5, §2 E12–E14. Vorschau und Ausführung benutzen
denselben `ResymPlan` (Handoff §4.2): `plan_resymmetrize` rechnet, der
Dispatcher zeigt den Plan an und `apply_plan` setzt genau diese Positionen.

- **Quellseite (A6, E12):** die topologische Seite (`lab_topology`) des
  ausgewählten Vertex — nicht das Vorzeichen seiner Position. Dadurch auch
  richtig, wenn der Vertex schon über die Ebene gewandert ist.
- **Was sich ändert (E13):** Jeder Zielseiten-Vertex mit topologischem
  Partner auf der Quellseite wird auf `mirror_position(partner)` gesetzt
  (Capability-Funktion; für die Achsen-Normalen aus E1 bitgenau). Jeder
  Seam-Vertex wird exakt auf die Ebene gelegt (Achsenkomponente `0.0`). Die
  Quellseite bleibt unverändert. Zielseiten-Vertices ohne Partner (oder im
  Konflikt) bleiben unverändert und stehen im Plan unter `unmatched`.
- **Keine Toleranz (A5):** „schon symmetrisch" heißt exakt gleich; nur echte
  Positionsänderungen landen im Plan.
- **Ein Undo-Schritt (E14):** `MeshStateCommand` mit Snapshot vorher/nachher
  — gleiches Muster wie `lab_symmetry.cycle_symmetry` (Slice 3 E2). Ein
  leerer Plan erzeugt keinen History-Eintrag.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core import Mesh, Scene, VertexId
from core.operations.topology import MeshStateCommand
from mirai.symmetry import mirror_position

from .lab_symmetry import AXIS_INDEX, current_axis
from .lab_topology import TopologyReport, topology_report

Vec3 = tuple[float, float, float]


class ResymmetrizeRejected(ValueError):
    """Re-Symmetrize ist nicht möglich; `str(exc)` ist der Grund für die Statuszeile."""


@dataclass(frozen=True)
class PositionChange:
    vertex: VertexId
    before: Vec3
    after: Vec3


@dataclass(frozen=True)
class ResymPlan:
    axis: str
    source_side: int
    #: z. B. "+X" / "−X" — nur Anzeige, siehe `_side_labels`.
    source_label: str
    target_label: str
    #: Zielseiten-Vertices → Spiegelposition ihres Partners.
    moves: tuple[PositionChange, ...]
    #: Seam-Vertices → exakt auf die Ebene (nur die, die nicht schon darauf liegen).
    seam_moves: tuple[PositionChange, ...]
    #: Zielseiten-Vertices ohne topologischen Partner (oder im Konflikt) — bleiben.
    unmatched: frozenset[VertexId]

    @property
    def changes(self) -> tuple[PositionChange, ...]:
        return self.moves + self.seam_moves

    @property
    def is_empty(self) -> bool:
        return not self.moves and not self.seam_moves


def _side_labels(mesh: Mesh, report: TopologyReport, axis: str) -> dict[int, str]:
    """„+X"/„−X" je Seite: die Seite mit dem größeren mittleren Achsenwert ist „+".

    Nur Anzeige. Die Seiten selbst sind topologisch (E12); hier wird ihnen
    lediglich ein lesbarer Name gegeben, der auch bei einzelnen über die
    Ebene gewanderten Vertices stabil bleibt.
    """
    i = AXIS_INDEX[axis]
    sums = [0.0, 0.0]
    counts = [0, 0]
    for vid, side in report.sides.vertex_side.items():
        sums[side] += mesh.vertex_position(vid)[i]
        counts[side] += 1
    means = [sums[s] / counts[s] if counts[s] else 0.0 for s in (0, 1)]
    plus = 0 if means[0] >= means[1] else 1
    return {plus: f"+{axis}", 1 - plus: f"−{axis}"}


def plan_resymmetrize(
    mesh: Mesh, source_vertex: VertexId, report: Optional[TopologyReport] = None
) -> ResymPlan:
    """Plan für Re-Symmetrize von der Seite von `source_vertex` aus (A6, E12, E13).

    Wirft `ResymmetrizeRejected`, wenn Symmetrie aus ist, `source_vertex` ein
    Seam-Vertex ist oder keine eindeutige Seite hat, oder die Seam das Mesh
    nicht in genau zwei Komponenten teilt.
    """
    axis = current_axis(mesh)
    if axis is None:
        raise ResymmetrizeRejected("Symmetrie aus")
    report = report if report is not None else topology_report(mesh)
    sides = report.sides
    if sides.component_count != 2:
        raise ResymmetrizeRejected(
            f"Seam teilt das Mesh in {sides.component_count} Teile (nötig: genau 2)"
        )
    if source_vertex in sides.seam_vertices:
        raise ResymmetrizeRejected("Seam-Vertex gewählt — Quellseite unklar")
    source = sides.vertex_side.get(source_vertex)
    if source is None:
        raise ResymmetrizeRejected(f"v{int(source_vertex)} gehört zu keiner Seite")

    definition = mesh.symmetry_definition
    partners = report.pairing.partners
    moves: list[PositionChange] = []
    unmatched: set[VertexId] = set()
    for vid, side in sides.vertex_side.items():
        if side == source:
            continue
        partner = partners.get(vid)
        if partner is None or sides.vertex_side.get(partner) != source:
            unmatched.add(vid)
            continue
        before = mesh.vertex_position(vid)
        after = mirror_position(
            mesh.vertex_position(partner), definition.plane_point, definition.plane_normal
        )
        if after != before:
            moves.append(PositionChange(vid, before, after))

    i = AXIS_INDEX[axis]
    seam_moves: list[PositionChange] = []
    for vid in sides.seam_vertices:
        before = mesh.vertex_position(vid)
        if before[i] != 0.0:
            after = list(before)
            after[i] = 0.0
            seam_moves.append(PositionChange(vid, before, tuple(after)))

    labels = _side_labels(mesh, report, axis)
    return ResymPlan(
        axis=axis,
        source_side=source,
        source_label=labels[source],
        target_label=labels[1 - source],
        moves=tuple(sorted(moves, key=lambda c: int(c.vertex))),
        seam_moves=tuple(sorted(seam_moves, key=lambda c: int(c.vertex))),
        unmatched=frozenset(unmatched),
    )


def apply_plan(scene: Scene, plan: ResymPlan) -> bool:
    """E13/E14: setzt die Positionen des Plans als genau einen History-Eintrag.

    Leerer Plan → nichts, kein History-Eintrag (E15). Rückgabe: ob ein
    History-Eintrag entstanden ist.
    """
    if plan.is_empty:
        return False
    mesh = scene.mesh
    before = mesh.export_state()
    for change in plan.changes:
        mesh.set_vertex_position(change.vertex, change.after)
    after = mesh.export_state()
    scene.history.push(
        MeshStateCommand(
            mesh=mesh,
            before_state=before,
            after_state=after,
            description=f"Re-Symmetrize {plan.source_label} → {plan.target_label}",
        )
    )
    return True


def plan_summary(plan: ResymPlan) -> str:
    """Statuszeilen-Text der Vorschau (E15)."""
    direction = f"Quelle {plan.source_label} → Ziel {plan.target_label}"
    if plan.is_empty:
        counts = "0 Änderungen"
    else:
        counts = f"bewegt {len(plan.moves)}, Seam → Ebene {len(plan.seam_moves)}"
    if plan.unmatched:
        counts += f", ohne Partner bleibt {len(plan.unmatched)}"
    return f"Re-Symmetrize {direction}: {counts} | M = ausführen, ESC = abbrechen"
