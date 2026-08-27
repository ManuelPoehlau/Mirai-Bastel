# Topology Experiments

Dieser Bereich ist die Spielwiese für interaktive und algorithmische Experimente zur **Topologie-Manipulation**.

Er ist bewusst **kein Produktionscode** und erweitert den eingefrorenen Core V1 nicht automatisch. Ziel ist zunächst herauszufinden, welche Topologie-Operationen wir für das spätere System tatsächlich brauchen, wie sie sich sinnvoll bedienen lassen und welche Informationen spätere Systeme wie Skinning, Morph Targets und Deformation benötigen.

## Warum dieser Bereich wichtig ist

Unsere Vision ist nicht einfach ein weiterer 3D-Modeler. Ein zentraler Forschungsbereich ist die möglichst robuste Verbindung von

```text
Modellierung
    ↕
Topologieänderung
    ↕
Deformation / Skinning / Morphing
```

Insbesondere soll untersucht werden, was passiert, wenn ein bereits deformierbares Mesh nachträglich verändert wird. Klassische Systeme können bei solchen Änderungen schnell ihre Gewichts- oder Deformationsdaten verlieren oder unbrauchbar machen. Wir wollen früh herausfinden, welche Daten und Regeln ein Mirai-Bastel-System dafür benötigt.

## Phase 1 – vorhandene Core-Primitives als Werkzeuge

Die erste Implementierungsstufe macht bewusst **keine neue Core-Funktion** auf. Stattdessen werden vorhandene, durch die Core-Hardening-Tests abgesicherte Primitive interaktiv im bestehenden V1-Viewport benutzt:

1. **Split Edge** → `split_edge()`
2. **Collapse Edge** → `collapse_edge()`
3. **Connect Vertices** → `connect_vertices()`
4. **Connect Edges** → experimentelle Kombination aus `split_edge()` + `connect_vertices()`

Die vier Werkzeuge laufen im neuen Topology-Lab mit einer kontrollierten 3x3-Quad-Grid-Testszene.

Ziel dieser Phase ist nicht, bereits ein endgültiges Modeling-UI zu definieren. Wir wollen zunächst beobachten, wie sich die vorhandenen Core-Bausteine als interaktive Topologie-Werkzeuge verhalten.

### Bedienung im Topology Lab

```text
Edge Mode
  S         Split Edge
  K         Collapse Edge
  Shift+C   Connect Edges

Vertex Mode
  C         Connect Vertices
```

Die Tool-Schicht liegt unter `experiments/mirai_bastel_viewport_V1/viewport/` und verändert `src/core` nicht.

## Phase 2 – Loop Insert / Loop Remove

Nach der praktischen Erprobung der Phase-1-Primitives folgen die beiden zusammengehörigen Loop-Forschungsfälle.

### Loop Insert

Zusätzliche Geometrie in einen bestehenden Edge-/Face-Verlauf einfügen.

Beispiel:

```text
A ───────────────── B
          ↓
A ─────── X ─────── B
```

Besonders interessant für Deformation:

```text
Weight(X) = ?
MorphDelta(X) = ?
```

Mögliche Strategien wie Interpolation sollen **experimentell** untersucht und nicht vorab als Architektur festgelegt werden.

### Loop Remove / Dissolve

Vorhandene Geometrie reduzieren und dabei angrenzende Topologie zusammenführen.

Zu untersuchen:

- welche Elemente verschwinden
- welche IDs erhalten bleiben
- wie abhängige Daten zusammengeführt werden könnten
- ob Informationen über die Herkunft der zusammengeführten Daten benötigt werden

Insert und Remove werden als zusammengehörige Forschungsgruppe betrachtet. Die genaue Reihenfolge der Implementierung ist weniger wichtig als die vollständige Untersuchung beider Richtungen.

## Phase 3 – Extrude

Aus einer bestehenden Face-/Face-Gruppe neue Geometrie erzeugen.

Zu untersuchen:

- Entstehung neuer Vertices, Edges und Faces
- räumliche und topologische Beziehungen
- stabile IDs
- Undo/Redo
- spätere Herkunfts-/Provenance-Informationen
- mögliche Übertragung von Skin Weights und Morph-Daten

## Danach mögliche Experimente

Je nach Erkenntnissen können später weitere Bereiche hinzukommen, beispielsweise:

- Inset
- Bevel
- Bridge
- weitere Connect-/Dissolve-Varianten
- Edge-/Ring-/Loop-Operationen
- Subdivision bzw. gezieltes Hinzufügen von Geometrie
- größere kombinierte Topologieänderungen
- Retopology-nahe Verfahren

Die Reihenfolge ist **keine starre Feature-Roadmap**. Neue Experimente sollen nach ihrem Erkenntniswert ausgewählt werden.

## Nicht nur Einzeloperationen testen

Die langfristige Robustheit lässt sich nicht durch eine einzelne erfolgreiche Operation beweisen. Nach den Einzeltests sollen deshalb Kombinationen untersucht werden, zum Beispiel:

```text
Split
  ↓
Connect
  ↓
Collapse
  ↓
Undo / Redo
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

Genau diese Kombinationen sind langfristig interessanter als isolierte Demo-Funktionen.

## Gemeinsame Prüfmatrix

Bei jeder relevanten Topologieänderung sollten wir nach Möglichkeit dieselben Fragen stellen:

1. **Topologie:** Was entsteht, verschwindet oder ändert sich?
2. **Identität:** Welche IDs bleiben erhalten, welche entstehen neu?
3. **Beziehungen:** Welche alten/neuen Elemente stehen miteinander in Beziehung?
4. **Provenance:** Können wir die Herkunft einer Änderung sinnvoll beschreiben?
5. **History:** Ist die Mutation exakt undo-/redo-fähig?
6. **Skinning:** Wie könnten Bone-Weights erhalten, interpoliert oder zusammengeführt werden?
7. **Morphing:** Wie könnten Morph-Deltas erhalten, interpoliert oder zusammengeführt werden?
8. **Kombinationen:** Funktioniert das Verhalten auch nach mehreren aufeinanderfolgenden Mutationen?
9. **Benutzbarkeit:** Ist die Operation später sinnvoll interaktiv bedienbar?

Damit testen wir nicht nur, **ob eine Operation funktioniert**, sondern ob sie eine brauchbare Grundlage für das spätere System bildet.

## Beziehung zum Core V1

Der Core V1 ist eingefroren. Bereits vorhandene Core-Operationen wie `split_edge`, `collapse_edge` und `connect_vertices` bilden die technische Grundlage für Phase 1.

Experimente dürfen zeigen, dass eine zukünftige Produktionsfunktion weitere Core-Fähigkeiten benötigt. Das bedeutet aber nicht automatisch, dass diese Fähigkeit sofort in den Core eingebaut wird.

Der bevorzugte Entwicklungsweg ist:

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

## Deformation als langfristiger Prüfstein

Topologie-Experimente sollen von Anfang an mit Blick auf spätere abhängige Daten betrachtet werden, auch wenn die ersten Implementierungen noch **ohne** Skinning oder Morphing laufen.

Für jede relevante Mutation sollten wir deshalb langfristig fragen:

1. Welche Elemente entstehen?
2. Welche Elemente verschwinden?
3. Welche Elemente ändern ihre Beziehungen?
4. Gibt es eine erkennbare Herkunft der neuen Daten?
5. Welche Informationen müsste ein Skinning-System übernehmen oder interpolieren?
6. Welche Informationen müsste ein Morph-System übernehmen oder interpolieren?
7. Ist die Änderung reversibel und per History exakt wiederherstellbar?

Sobald die grundlegenden Topologieoperationen ausreichend verstanden sind, sollen sie bewusst mit frühen Deformations-Experimenten verbunden werden.

## Grundsatz

> **Nicht zuerst den perfekten Modeler bauen. Erst herausfinden, welche Kombination aus Topologie, Deformation und Datenkontinuität Mirai-Bastel besonders machen kann.**

Dieses Dokument beschreibt daher bewusst **Richtung und Forschungsfragen**, nicht die endgültige Produktionsarchitektur.
