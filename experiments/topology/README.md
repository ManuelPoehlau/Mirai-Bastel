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

## Erste geplante Experimente

### 1. Extrude

Aus einer bestehenden Face-/Face-Gruppe neue Geometrie erzeugen.

Zu untersuchen:

- Entstehung neuer Vertices, Edges und Faces
- räumliche und topologische Beziehungen
- stabile IDs
- Undo/Redo
- spätere Herkunfts-/Provenance-Informationen
- mögliche Übertragung von Skin Weights und Morph-Daten

### 2. Loop Insert

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

### 3. Loop Remove / Dissolve

Vorhandene Geometrie reduzieren und dabei angrenzende Topologie zusammenführen.

Zu untersuchen:

- welche Elemente verschwinden
- welche IDs erhalten bleiben
- wie abhängige Daten zusammengeführt werden könnten
- ob Informationen über die Herkunft der zusammengeführten Daten benötigt werden

## Danach mögliche Experimente

Je nach Erkenntnissen können später weitere Bereiche hinzukommen, beispielsweise:

- Inset
- Bevel
- Bridge
- Connect
- Dissolve
- Edge/Ring/Loop-Operationen
- Subdivision bzw. gezieltes Hinzufügen von Geometrie
- größere Topologieänderungen
- Retopology-nahe Experimente

Die Reihenfolge ist **nicht festgeschrieben**. Neue Experimente sollen nach ihrem Erkenntniswert ausgewählt werden.

## Beziehung zum Core V1

Der Core V1 ist eingefroren. Bereits vorhandene Core-Operationen wie `split_edge`, `collapse_edge` und `connect_vertices` bilden einen Teil der technischen Grundlage.

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

Damit wird nicht nur getestet, **ob** eine Topologie-Operation funktioniert, sondern auch, ob sie eine brauchbare Grundlage für das spätere Zielsystem bildet.

## Grundsatz

> **Nicht zuerst den perfekten Modeler bauen. Erst herausfinden, welche Kombination aus Topologie, Deformation und Datenkontinuität Mirai-Bastel besonders machen kann.**

Dieses Dokument beschreibt daher bewusst **Richtung und Forschungsfragen**, nicht eine festgelegte Produktionsarchitektur.
