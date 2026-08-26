"""MeshStateCommand: generischer, snapshot-basierter History-Eintrag für
atomare Topologie-Mutationen (split_edge / collapse_edge / connect_vertices).

Bezug: docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md §17 Phase D.

Warum Snapshot statt semantischer Inverse (wie MoveVerticesCommand)?

AD-001 (ids.py) legt fest, dass eine einmal vergebene ID innerhalb einer
Session NIE wiederverwendet wird - auch nicht nach dem Löschen ihres
Elements. Ein "Undo durch Gegenoperation" (z. B. einen Split rückgängig
machen, indem intern etwas wie collapse_edge aufgerufen wird) würde für
alles, was dabei neu entsteht, zwangsläufig NEUE IDs vergeben - niemals
exakt dieselben, die vor der ursprünglichen Operation existierten. Ein
vollständiger Zustands-Snapshot (Mesh.export_state()/load_state()) ist
deshalb nicht nur die pragmatischste, sondern die einzige Möglichkeit,
exakte ID-Kontinuität über Undo/Redo hinweg zu garantieren.

Bewusst NICHT enthalten (Hardening-Plan §17 Phase D, Absprache im Chat):
- keine automatische Kopplung von split_edge/collapse_edge/connect_vertices
  an die History - Mesh bleibt von History unabhängig (§15 Punkt 5).
- kein neues Operation-Klassengerüst (begin/update/commit) für diese drei
  Mutationen - sie sind atomare Aufrufe, keine interaktiven Abläufe wie
  MoveOperation. Aufrufer bauen dieses Command explizit um ihren
  Mutationsaufruf herum, genau wie ein künftiges Tool das später täte.
- kein allgemeines Undo-Framework über Mesh hinaus.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..mesh import Mesh


@dataclass
class MeshStateCommand:
    """Reversibler History-Eintrag für eine atomare Topologie-Mutation.

    Speichert vollständige Vorher-/Nachher-Snapshots (`mesh.export_state()`)
    statt einer semantischen Differenz - siehe Modul-Docstring für den
    Grund (ID-Kontinuität, AD-001).
    """

    mesh: Mesh
    before_state: dict
    after_state: dict
    description: str = "Topology Edit"

    def undo(self) -> None:
        self.mesh.load_state(self.before_state)

    def redo(self) -> None:
        self.mesh.load_state(self.after_state)
