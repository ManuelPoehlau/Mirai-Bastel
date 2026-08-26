# Topology Experiment Plan

Dieser Bereich ist die **Spielwiese für Topologie-Manipulation**.

Hier dürfen interaktive und algorithmische Experimente entstehen, ohne dass daraus automatisch Produktionsarchitektur oder Core-Änderungen werden. Ziel ist, möglichst früh herauszufinden, welche Topologie-Operationen, Datenbeziehungen und Bedienkonzepte Mirai-Bastel für seine langfristige Vision benötigt.

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

## Erste Experimentgruppe: Insert ↔ Remove

Die ersten Experimente konzentrieren sich auf zwei grundlegende und gegensätzliche Fälle.

### 1. Loop Insert

Neue Geometrie wird **innerhalb einer bestehenden Struktur** erzeugt.

```text
A ───────────────── B
          ↓
A ─────── X ─────── B
```

Zu untersuchen:

- Welche Vertices / Edges / Faces entstehen?
- Welche Beziehungen entstehen zwischen alten und neuen Elementen?
- Welche IDs bleiben erhalten?
- Welche IDs sind neu?
- Lässt sich die Herkunft neuer Elemente sinnvoll beschreiben?
- Wie könnte ein späteres Skinning-System Weights für `X` bestimmen?
- Wie könnte ein Morph-System entsprechende Daten behandeln?

Beispielhafte Forschungsfrage:

```text
Weight(X) = ?
MorphDelta(X) = ?
```

Mögliche Strategien wie Interpolation sind **Hypothesen**, keine Architekturvorgaben.

### 2. Loop Remove / Dissolve

Bestehende Geometrie wird reduziert bzw. zusammengeführt.

```text
A ─── X ─── B
      ↓
A ──────── B
```

Zu untersuchen:

- Welche Elemente verschwinden?
- Welche Elemente bleiben erhalten?
- Welche IDs bleiben erhalten?
- Müssen Daten mehrerer Elemente zusammengeführt werden?
- Welche Informationen wären für Skin Weights und Morph-Daten erforderlich?
- Brauchen wir später Herkunfts-/Provenance-Informationen?

**Insert und Remove sollen als zusammengehörige Forschungsgruppe betrachtet werden.** Die genaue Implementierungsreihenfolge ist nicht entscheidend; wichtig ist, dass beide Richtungen untersucht werden.

## Danach: Extrude

Als nächster größerer Topologie-Fall soll **Extrude** untersucht werden.

```text
Face
  ↓
Extrude
  ↓
neue Vertices + Edges + Faces
```

Extrude ist besonders interessant, weil nicht nur einzelne Elemente entstehen, sondern eine zusammenhängende neue Topologie mit räumlicher Bedeutung.

Zu untersuchen sind insbesondere:

- Entstehung und Beziehungen neuer Elemente
- Auswahl der extrudierten Region
- Normal-/Richtungsfragen
- ID- und Herkunftsbeziehungen
- Undo/Redo
- mögliche Übertragung zukünftiger Deformationsdaten

## Weitere mögliche Topologie-Experimente

Nach den ersten drei Bereichen können je nach Erkenntnisgewinn weitere Experimente folgen, beispielsweise:

- Inset
- Bevel
- Bridge
- Connect
- weitere Dissolve-Varianten
- Edge-/Ring-/Loop-Operationen
- Subdivision bzw. gezieltes Hinzufügen von Geometrie
- größere kombinierte Topologieänderungen
- Retopology-nahe Verfahren

Die Liste ist **offen und nicht als starre Feature-Roadmap gedacht**.

## Nicht nur Einzeloperationen testen

Die langfristige Robustheit lässt sich nicht durch eine einzelne erfolgreiche Operation beweisen. Wir müssen unterschiedliche Situationen kombinieren.

Beispielsweise:

```text
Insert
  ↓
Deform
  ↓
Remove
  ↓
Deform
```

oder:

```text
Deform
  ↓
Insert
  ↓
weitere Topologieänderung
  ↓
Deform
```

Später auch:

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

Genau solche Kombinationen sind langfristig interessanter als isolierte Demo-Funktionen.

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

`src/core` V1 ist eingefroren.

Bereits vorhandene Core-Fähigkeiten wie `split_edge`, `collapse_edge` und `connect_vertices` bilden eine technische Grundlage. Neue Experimente dürfen aber zeigen, dass zukünftige Produktionsfunktionen weitere Core-Fähigkeiten benötigen.

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

## Geplante grobe Reihenfolge

```text
┌────────────────────────────────────┐
│  1. Loop Insert                    │
│  2. Loop Remove / Dissolve         │
│                                    │
│  → gemeinsam als Insert/Remove-    │
│    Forschungsgruppe betrachten     │
├────────────────────────────────────┤
│  3. Extrude                        │
├────────────────────────────────────┤
│  4. weitere Topologie-Operationen  │
├────────────────────────────────────┤
│  5. Kombinationen / Edge Cases     │
└────────────────────────────────────┘
```

Diese Reihenfolge ist eine **Orientierung**, keine starre Priorisierung. Alle relevanten Mutationssituationen müssen langfristig untersucht werden.

## Brücke zu Deformation

Sobald die grundlegenden Topologieoperationen funktionieren, sollen sie bewusst mit frühen Deformations-Experimenten verbunden werden:

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
