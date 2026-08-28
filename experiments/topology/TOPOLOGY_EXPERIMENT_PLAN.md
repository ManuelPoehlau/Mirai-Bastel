# Topology Experiment Plan

Dieser Bereich ist die **Spielwiese für Topologie-Manipulation**.

Hier dürfen interaktive und algorithmische Experimente entstehen, ohne dass daraus automatisch Produktionsarchitektur oder Core-Änderungen werden. Ziel ist, möglichst früh herauszufinden, welche Topologie-Operationen, Datenbeziehungen und Bedienkonzepte Mirai-Bastel für seine langfristige Vision benötigt.

## Dokumentationsgrenze

Dieses Dokument ist der **Single Source of Truth für den aktiven Topology-Experimentplan**: Phasen, Reihenfolge als Orientierung, gemeinsame Prüfmatrix und aktuell bekannte Topology-spezifische Forschungsfragen.

Allgemeine Selection-/Workflow-Prinzipien werden nicht hier dupliziert:

- [`Selection Experiment`](../mirai_bastel_viewport_V1/SELECTION_MODES.md)
- [`Selection Future Ideas`](../../docs/future_ideas/SELECTION.md)
- [`Workflow Design`](../../docs/design/WORKFLOW.md)

Architekturverträge bleiben unter `docs/architecture/`.

## Forschungsrichtung

Mirai-Bastel soll nicht nur ein weiterer Modeler werden. Ein zentraler Forschungsbereich ist die robuste Verbindung von

```text
Modellierung
    ↕
Topologieänderung
    ↕
Deformation / Skinning / Morphing
```

Insbesondere wollen wir früh untersuchen, was mit Deformationsdaten passiert, wenn ein bereits deformierbares Mesh nachträglich verändert wird.

Das ist bewusst ein **Forschungsziel**, keine bereits festgelegte technische Lösung.

## Phase 1 — vorhandene Core-Primitives als Werkzeuge

**Status: abgeschlossen und praktisch verifiziert.**

Die erste Stufe hat bewusst keine neue Core-Funktion eingeführt. Vorhandene, durch Core-Hardening-Tests abgesicherte Primitive wurden interaktiv im V1-Viewport benutzt:

1. **Split Edge** → `split_edge()`
2. **Collapse Edge** → `collapse_edge()`
3. **Connect Vertices** → `connect_vertices()`
4. **Connect Edges** → experimentelle Kombination aus `split_edge()` + `connect_vertices()`

Zusätzlich wurden Mehrfachauswahl-Fälle für Collapse/Connect untersucht.

Praktische Beobachtungen:

- einzelne Vertex-/Edge-Connect-Fälle funktionieren wie erwartet;
- Split und Collapse funktionieren in den untersuchten Fällen;
- nicht zulässige Verbindungen ohne gemeinsames Face werden abgelehnt;
- Collapse kann bei sehr kleiner Restgeometrie zu freischwebenden Edges führen; das ist für die Primitive logisch, für ein späteres Modeler-Tool aber eine Workflow-/Validierungsfrage;
- Selection/Mode nach einer Operation ist ein wichtiger eigener Workflow-Aspekt;
- Undo/Redo der Topology-Tools ist derzeit **noch nicht abgeschlossen**, weil der experimentelle Command auf `Mesh.load_state()` angewiesen ist, das im aktuellen Core V1 nicht vorhanden ist. Das wird als eigener späterer Punkt behandelt und nicht als erledigte Funktion angenommen.

## Phase 2 — Loop / Ring Detection und Selection

**Status: abgeschlossen und praktisch verifiziert.**

Die Phase wurde bewusst in zwei Schritte aufgeteilt: Zuerst wurde die reine Traversierungslogik implementiert und getestet, anschließend wurde sie interaktiv im Topology Lab verdrahtet und im Viewport geprüft.

### Erkennung (Query-Ebene)

`experiments/mirai_bastel_viewport_V1/viewport/loop_ring.py` implementiert `edge_loop()` und `edge_ring()` rein über die bestehende Topologie-Query-API (`face_vertices`, `face_edges`, `edge_faces`, `edge_vertices`, `vertex_edges`), ohne Core- oder Mesh-Änderung.

Die Erkennung ist bewusst konservativ:

- **Edge Ring** läuft nur durch Quad-Faces (Boundary-Länge 4); trifft er auf eine Non-Quad-Face, bricht er auf dieser Seite ab.
- **Edge Loop** läuft nur durch Vertices mit Valenz genau 4 und eindeutigem "gegenüberliegendem" Kandidaten (keine gemeinsame Face mit der eingehenden Kante).
- Boundary-Loop-Fortsetzung ist bewusst **nicht** implementiert, sondern bleibt als offene Folgefrage bestehen.
- Beide erkennen geschlossene Loops/Ringe explizit über ein `closed`-Flag, statt die Startkante doppelt aufzunehmen.

Die Erkennung wurde in `experiments/mirai_bastel_viewport_V1/tests/test_loop_ring.py` ohne Fenster/GPU verifiziert: volle Zeile/Spalte im Quad-Grid, konservativer Abbruch an Rand-Valenz und Non-Quad-Face sowie geschlossene Loop-/Ring-Erkennung auf einem künstlichen Quad-Rohr.

### Interaktive Selection

Die Erkennung ist jetzt im Topology Lab interaktiv angebunden:

```text
Edge Mode + genau 1 Edge
        ↓
L → Edge Loop
R → Edge Ring
        ↓
erkanntes Edge Set
        ↓
Viewport Selection
```

Aktuelles experimentelles Verhalten:

- **`L`** wählt den Edge Loop der aktuell ausgewählten Startkante.
- **`R`** wählt den Edge Ring der aktuell ausgewählten Startkante.
- Voraussetzung ist Edge Mode und genau eine ausgewählte Edge.
- Die bisherige Selection wird durch das erkannte Edge-Set ersetzt.
- Das Ergebnis wird unmittelbar im Viewport visualisiert.
- Geschlossene Traversierungen werden über den `closed`-Status in der Caption angezeigt.
- Die Auswahl selbst verändert keine Mesh-Topologie und benötigt keine Änderung am eingefrorenen Core V1.

Die komplette Kette wurde praktisch getestet und funktioniert:

```text
Edge Picking
    ↓
Loop / Ring Detection
    ↓
Edge Set
    ↓
Viewport Selection
    ↓
visuelles Ergebnis
```

### Bewusst offene Forschungsfragen

Der Abschluss von Phase 2 bedeutet nicht, dass jede denkbare Loop-/Ring-Semantik gelöst ist. Offen bleiben insbesondere:

- Loop-/Ring-Verhalten bei komplexeren gemischten Quad-/Non-Quad-Topologien über die aktuelle Grenzfallabdeckung hinaus;
- Boundary-Loop-Fortsetzung;
- endgültige Modifier-/Interaktionssemantik;
- spätere Loop-/Ring-Operationen wie Insert, Cut und Slide.

Die Detection bleibt damit bewusst ein konservatives Experiment und kein endgültiger Produktionsvertrag.

## Phase 3 — Loop Insert / Loop Remove

Die beiden zusammengehörigen Fälle werden als nächste große Forschungsgruppe betrachtet.

### Loop Insert

Neue Geometrie wird innerhalb einer bestehenden Struktur erzeugt.

Zu untersuchen:

- entstehende Vertices / Edges / Faces
- Beziehungen zwischen alten und neuen Elementen
- ID-Kontinuität
- Herkunft/Provenance
- spätere Skin-Weight-Übertragung
- spätere Morph-Delta-Übertragung

### Loop Remove / Dissolve

Bestehende Geometrie wird reduziert bzw. zusammengeführt.

Zu untersuchen:

- welche Elemente verschwinden
- welche IDs erhalten bleiben
- welche Daten mehrerer Elemente später zusammengeführt werden müssten
- ob Herkunfts-/Provenance-Informationen benötigt werden

Insert und Remove werden gemeinsam bewertet; die genaue Reihenfolge ist weniger wichtig als die vollständige Untersuchung beider Richtungen.

## Phase 4 — Extrude

Als nächster größerer Topologie-Fall soll **Extrude** untersucht werden.

```text
Face / Face Group
       ↓
    Extrude
       ↓
neue Vertices + Edges + Faces
```

Zu untersuchen sind insbesondere:

- Entstehung und Beziehungen neuer Elemente
- Auswahl der extrudierten Region
- Normal-/Richtungsfragen
- ID- und Herkunftsbeziehungen
- History
- spätere Übertragung von Deformationsdaten
- interaktives Verhalten

## Phase 5+ — weitere Topologie-Experimente

Je nach Erkenntnisgewinn können danach folgen:

- Inset
- Bevel
- Bridge
- weitere Connect-/Dissolve-Varianten
- Loop Slide
- Subdivision-nahe Geometrieoperationen
- größere kombinierte Topologieänderungen
- Retopology-nahe Verfahren

Die Liste ist **offen und keine starre Feature-Roadmap**.

## Nicht nur Einzeloperationen testen

Die langfristige Robustheit lässt sich nicht durch eine einzelne erfolgreiche Operation beweisen.

Beispielsweise:

```text
Split
  ↓
Connect
  ↓
Collapse
  ↓
weitere Änderung
```

und später:

```text
Topologie ändern
  ↓
Deform
  ↓
weitere Topologieänderung
  ↓
Deform erneut auswerten
```

Noch später:

```text
Extrude
  ↓
Skin
  ↓
Loop Insert
  ↓
Pose / Deform
  ↓
Loop Remove
  ↓
Morph
  ↓
weitere Topologieänderung
```

Solche Kombinationen sind langfristig interessanter als isolierte Demo-Funktionen.

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

Damit testen wir nicht nur, **ob eine Operation funktioniert**, sondern ob sie eine brauchbare Grundlage für das spätere System bildet.

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
falls wirklich notwendig:
Core-/Production-Erweiterung
```

Nicht jede experimentelle Operation muss jemals Produktionscode werden.

## Brücke zu Deformation

Sobald die grundlegenden Topologieoperationen ausreichend verstanden sind, sollen sie bewusst mit frühen Deformations-Experimenten verbunden werden:

```text
Mesh
  ↓
Bones / Skin Weights
  ↓
Deformation
  ↓
Topologie ändern
  ↓
Deformation erneut auswerten
```

Danach:

```text
Topologie
    ↕
Skinning
    ↕
Morph Targets
```

Animation kommt bewusst später. Die Datenkontinuität zwischen Modellierung und Deformation soll jedoch möglichst früh erforscht werden.

## Grundsatz

> **Nicht zuerst den perfekten Modeler bauen. Erst herausfinden, welche Kombination aus Topologie, Deformation und Datenkontinuität Mirai-Bastel besonders machen kann.**

Dieses Dokument beschreibt **Richtung, Experimente und Forschungsfragen**, nicht die endgültige Produktionsarchitektur.
