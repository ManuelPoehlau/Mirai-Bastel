# Topology Experiments

Dieser Bereich ist die **Dokumentations- und Planstelle für die Topologie-Forschung**.

Der eigentliche experimentelle Code liegt derzeit bewusst unter `experiments/mirai_bastel_viewport_V1/viewport/`. Die Trennung ist absichtlich: Das Viewport-Experiment stellt die interaktive Umgebung bereit, während dieser Ordner die Topology-Forschung als zusammenhängenden Arbeitsbereich dokumentiert.

## Einstieg

- [Topology Experiment Plan](TOPOLOGY_EXPERIMENT_PLAN.md) — **aktiver Single Source of Truth für Richtung, Phasen und Prüfmatrix**
- [Viewport V1 Selection Experiment](../mirai_bastel_viewport_V1/SELECTION_MODES.md) — aktuelle Selection-/Workflow-Erkenntnisse aus dem interaktiven Viewport
- [Selection Future Ideas](../../docs/future_ideas/SELECTION.md) — längerfristige Selection-Ideen, die nicht nur dieses Experiment betreffen
- [Workflow Design](../../docs/design/WORKFLOW.md) — allgemeine Interaktionsprinzipien
- [Core V1 Architecture](../../docs/architecture/V1_CORE.md) — eingefrorene Core-Verträge
- [Core V1 Freeze](../../docs/architecture/CORE_V1_FREEZE.md) — aktueller Freeze-Stand
- [Project Vision](../../docs/architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md) — langfristige Systemrichtung

## Aktueller Status

**Phase 1 — vorhandene Core-Primitives als interaktive Werkzeuge: untersucht; Connect Edges wurde in Phase 3 ausstehend abgeschlossen.**

Getestet wurden unter anderem:

- Split Edge
- Collapse Edge
- Connect Vertices
- Connect Edges
- Mehrfachauswahl für Collapse/Connect-Fälle
- relevante Grenzfälle, soweit die vorhandene Geometrie weitere sinnvolle Operationen zulässt

Dabei wurden praktische Workflow-Fragen entdeckt, insbesondere das Verhalten von Selection und Selection Mode nach einer Topologieoperation. Die frühere experimentelle Implementierung von Connect Edges behandelte größere Multi-Selections nicht als sauber definierte einheitliche Connect-Operation; diese Semantik ist mit Phase 3 (siehe unten) für den regulären Quad-Scope abgeschlossen.

**Phase 2 — Loop/Ring-Erkennung und Selection: abgeschlossen als Experiment.**

Die konservative Erkennung von Edge Loops und Edge Rings wurde als reine Query implementiert und durch Logiktests verifiziert. Anschließend wurde sie interaktiv in das Topology Lab eingebunden und praktisch im Viewport getestet.

Aktuelles experimentelles Verhalten:

- **Edge Mode + genau 1 Edge + `L`** → Auswahl des erkannten Edge Loops
- **Edge Mode + genau 1 Edge + `R`** → Auswahl des erkannten Edge Rings
- die bestehende Auswahl wird durch die erkannte Loop-/Ring-Auswahl ersetzt
- das Ergebnis wird direkt im Viewport visualisiert
- geschlossene Traversierungen werden über den vorhandenen `closed`-Status angezeigt
- die Loop-/Ring-Auswahl verändert keine Mesh-Topologie und benötigt keine Core-Änderung

Damit ist die gesamte Phase-2-Kette praktisch verifiziert:

```text
Edge Picking
    ↓
Loop / Ring Detection
    ↓
Edge Set
    ↓
Viewport Selection
    ↓
visuelles Praxisergebnis
```

Die Detection bleibt bewusst konservativ: Edge Rings laufen nur durch Quad-Faces; Edge Loops benötigen Valenz 4 und einen eindeutigen gegenüberliegenden Kandidaten. Boundary-Loop-Fortsetzung sowie weitergehende gemischte Topologien bleiben offene Forschungsfragen und sind nicht Teil dieses Abschlusses.

**Phase 3 — Connect Edges: Semantik und robuste Multi-Selection: untersucht.**

Connect Edges wurde bewusst vor Loop Insert priorisiert. Die Operation ist eine grundlegende Modeling-Primitive. Die bisherige experimentelle Implementierung (ID-Sortierung → Splits → Verketten) wurde gemäß `docs/research/topology/CONNECT_EDGES_SPEC.md` durch eine topology-aware, atomare Implementierung ersetzt:

- drei klar getrennte Phasen: **Analyze/Validate → Plan → Apply/Commit**
- Gruppierung und Verbindungen basieren ausschließlich auf Topologie/Geometrie:
  - gegenüberliegende Kanten einer Quad-Face → `connect_vertices`
  - kantenbenachbarte Ketten um reguläre Innen-Vertices → freie Kante via neuem Minimalprimitive `Mesh.add_edge` (vom Experiment entdeckte, im Experiment-Core ergänzte Fähigkeit; `split_edge`/`connect_vertices` blieben unverändert)
- vollständig atomic: jeder Validierungs-/Konstruktionsfehler lässt das Mesh exakt unverändert (read-only-Analyse, Plan-Dry-Run auf Clone, Rollback über `load_state`)
- deterministisch: Selection-Reihenfolge und numerische Edge-IDs beeinflussen weder Gruppierung noch Ergebnis
- genau ein History-Snapshot pro Operation

Praktisch verifiziert über `tests/test_connect_edges.py`: 2 kompatible Edges, 3+ Ketten, 4+ zusammenhängende Edges, kompletter Edge Ring, Edge Loop als Input, mehrere disjunkte Gruppen, ungültige Auswahl, mehrere Selection-Reihenfolgen, genau ein History-Snapshot mit Undo/Redo, atomare Fehlerfälle.

Scope: reguläre kompatible Quad-Topologie (Ketten, Ringe). Boundary-, Non-Quad-, Mixed-Valence- und Non-Manifold-Fälle werden explizit abgelehnt und sind damit weiterhin offene Forschungsfragen.

**Noch offen:** Loop Insert als eigene Höher-Level-Operation (Phase 4) - Connect Edges bleibt bewusst davon getrennt.

**Phase 4 — Loop Insert / Loop Remove: geplant.**

Erst nach der Connect-Edges-Untersuchung werden Loop Insert und Loop Remove/Dissolve als höhere Modeling-Operationen erforscht.

Dabei soll insbesondere geprüft werden, welche Teile der vorhandenen Loop-/Ring-Traversierung wiederverwendet werden können und welche eigene Topologie-Mutation notwendig ist. Loop Insert wird nicht einfach mit `Ring Selection + Connect Edges` gleichgesetzt.

**Phase 5 — Extrude: geplant.**

Danach folgt die Untersuchung von Extrude einschließlich neuer Vertices/Edges/Faces, Auswahl der Region, Richtungsfragen und Datenkontinuität.

## Langfristiger Forschungszweck

Unsere Vision ist nicht einfach ein weiterer Modeler. Ein zentraler Forschungsbereich ist die möglichst robuste Verbindung von:

```text
Modellierung
    ↕
Topologieänderung
    ↕
Deformation / Skinning / Morphing
```

Insbesondere soll früh untersucht werden, was passiert, wenn ein bereits deformierbares Mesh nachträglich verändert wird. Die ersten Topology-Experimente laufen deshalb bewusst mit Blick auf spätere Datenkontinuität, obwohl Skinning und Morphing selbst noch nicht implementiert sind.

## Gemeinsame Prüfmatrix

Bei jeder relevanten Topologieänderung sollten nach Möglichkeit dieselben Fragen gestellt werden:

1. **Topologie:** Was entsteht, verschwindet oder ändert sich?
2. **Identität:** Welche IDs bleiben erhalten, welche entstehen neu?
3. **Beziehungen:** Welche alten/neuen Elemente stehen miteinander in Beziehung?
4. **Provenance:** Können wir die Herkunft einer Änderung sinnvoll beschreiben?
5. **History:** Ist die Mutation exakt undo-/redo-fähig?
6. **Skinning:** Wie könnten Bone-Weights erhalten, interpoliert oder zusammengeführt werden?
7. **Morphing:** Wie könnten Morph-Deltas erhalten, interpoliert oder zusammengeführt werden?
8. **Kombinationen:** Funktioniert das Verhalten auch nach mehreren aufeinanderfolgenden Mutationen?
9. **Benutzbarkeit:** Ist die Operation später sinnvoll interaktiv bedienbar?
10. **Workflow:** Was passiert mit Selection und aktivem Selection Mode nach der Operation?

## Beziehung zum Core V1

Der Core V1 ist eingefroren. Topology-Experimente dürfen zeigen, dass eine zukünftige Produktionsfunktion weitere Core-Fähigkeiten benötigt. Das bedeutet nicht automatisch, dass diese Fähigkeit sofort in `src/core` eingebaut wird.

Der bevorzugte Weg bleibt:

```text
Experiment
    ↓
Beobachtung
    ↓
Erkenntnis
    ↓
Architekturentscheidung
    ↓
falls wirklich notwendig: Core-/Production-Erweiterung
```

Nicht jede experimentelle Operation muss jemals Produktionscode werden.

## Dokumentationsregel

Dieser Ordner soll **nicht** zu einer zweiten Sammlung allgemeiner Future Ideas werden. Topology-spezifische Phasen, Tests und Beobachtungen gehören hierher. Allgemeine Selection-, Workflow-, Rigging- oder Morphing-Ideen werden in den zuständigen Dokumenten unter `docs/` gepflegt und hier nur verlinkt.
