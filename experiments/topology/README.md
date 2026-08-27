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

**Phase 1 — vorhandene Core-Primitives als interaktive Werkzeuge: abgeschlossen und praktisch verifiziert.**

Getestet wurden unter anderem:

- Split Edge
- Collapse Edge
- Connect Vertices
- Connect Edges
- Mehrfachauswahl für Collapse/Connect-Fälle
- relevante Grenzfälle, soweit die vorhandene Geometrie weitere sinnvolle Operationen zulässt

Dabei wurden auch praktische Workflow-Fragen entdeckt, insbesondere das Verhalten von Selection und Selection Mode nach einer Topologieoperation. Diese Fragen sind bewusst noch nicht als Produktionsvertrag festgelegt.

**Phase 2 — Loop/Ring-Erkennung und Selection: nächster Forschungsbereich.**

Zunächst konservative Erkennung bzw. Auswahl von Edge Loops und Edge Rings. Erst wenn diese Erkennung zuverlässig funktioniert, werden darauf aufbauende Operationen wie Loop Insert/Loop Cut untersucht.

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
