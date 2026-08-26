# Mirai-Bastel Core V1 — Produktions-Freeze

**Status:** FROZEN  
**Datum:** 2026-08-27  
**Grundlage:** Hardening-Phasen A–E + Gesamtarchitektur-Review

## 1. Entscheidung

`src/core/` wird nach Abschluss des Hardening- und Architektur-Reviews als **Core V1 eingefroren**.

Freeze bedeutet nicht, dass der Core niemals wieder geändert werden darf. Es bedeutet:

> Eine Änderung an `src/core/` benötigt ab jetzt eine konkrete neue Anforderung, die zeigt, dass der bestehende V1-Vertrag nicht ausreicht.

Zukünftige Systeme werden nicht vorsorglich in den Core eingebaut.

## 2. Was vor dem Freeze validiert wurde

### Phase A — Invarianten

- gültige Vertex-/Edge-/Face-Referenzen
- keine doppelten Vertices in Face-Boundaries
- bidirektionale Edge↔Face-Adjazenz
- keine Self-Loops
- maximal zwei Faces pro Edge für die V1-Manifold-Annahme
- keine stale Edge-Endpunkte nach Collapse

### Phase B — Topologie

`split_edge`, `collapse_edge` und `connect_vertices` wurden in relevanten Boundary-/Interior-/Fan-/Merge-Szenarien geprüft.

### Phase C — Identitätskontinuität

Für jede Topologieoperation wurden die vollständigen Mengen von Vertex-, Edge- und Face-IDs vor und nach der Mutation verglichen. Damit ist nicht nur die Existenz einzelner IDs, sondern auch nachvollziehbar, welche Elemente bleiben, verschwinden oder neu entstehen.

Der Core liefert dafür bewusst noch kein allgemeines Change-Set-/Provenance-System. Die vollständigen Diffs sind über die öffentliche Query-API extern rekonstruierbar.

### Phase D — Undo / Redo

Topologieänderungen können über `MeshStateCommand` mit Vorher-/Nachher-Snapshots exakt rückgängig gemacht und wiederhergestellt werden.

`Mesh.load_state()` stellt den Zustand in-place wieder her. Der ID-Allocator bleibt dabei monoton; Undo darf keine bereits verwendete ID erneut verfügbar machen.

Die Topologie-Mutationen bleiben bewusst History-unabhängig. Ein Aufrufer entscheidet explizit, wann eine atomare Mutation als History-Command erfasst wird.

### Phase E — Serialisierung

Scene-/Mesh-Zustände wurden nach echten Topologie-Mutationssequenzen per Dict und JSON roundtripped.

Geprüft wurden unter anderem:

- vollständige Topologiebeziehungen
- exakte Allocator-Zählerstände
- Kollisionsfreiheit für Vertex/Edge/Face-IDs nach dem Laden
- bewusster Ausschluss von Selection und History aus der Persistenz
- reservierte V1-Subsystem-Plätze für Morph Targets, Rig und Animation
- Versionsprüfung
- leere Scene

**Gesamtergebnis:** 37/37 unittest-Tests + 11 Architekturvertrags-Blöcke, PASS.

## 3. Architekturabgleich mit der langfristigen Vision

Die langfristige Vision ist kein größerer Modellierer um seiner selbst willen, sondern ein lebendes, erweiterbares 3D-System, in dem Modellierung, Deformation, Rigging, Morphs und Animation auf einer gemeinsamen Scene weiterarbeiten können.

Der V1-Core verbaut diese Richtung nicht:

- stabile opaque IDs schaffen eine Grundlage für spätere Referenzen
- kontrollierte Topologie-Queries verhindern, dass spätere Systeme von konkreten Containern abhängen müssen
- History und Serialization sind eigenständige Core-Verantwortlichkeiten
- UI, Viewport und Renderer sind nicht Teil des Core
- zukünftige Deformations-/Morph-/Rig-Systeme sind nicht vorweggenommen

Wichtig: **Stable IDs allein lösen noch kein Skin-/Morph-Remapping.** Bei zukünftigen Topologieänderungen wird voraussichtlich ein zusätzliches Change-/Provenance-/Remapping-Konzept benötigt. Dieses gehört in eine spätere, durch konkrete Anforderungen motivierte Phase.

Damit bleibt insbesondere der gewünschte langfristige Workflow möglich:

```text
Model
  ↓
Rig / Deformation testen
  ↓
fehlende Geometrie erkennen
  ↓
Mesh weiter bearbeiten
  ↓
Deformation / Animation weiterverwenden
```

Der V1-Core muss diesen Workflow noch nicht vollständig implementieren; er darf ihn aber nicht durch falsche V1-Annahmen unnötig verhindern.

## 4. Bewusst NICHT Teil des Freeze

Folgende Systeme werden nicht nachträglich in Core V1 hineingezogen:

- Half-Edge-/Winged-Edge-Neuimplementierung
- generisches Change-Set-System
- Herkunfts-/Provenance-Metadaten
- Skin-Weight-Remapping
- Morph Targets
- Rigging / Bones
- Animation
- Soft Selection / Influence-System
- vollständiges Extension-/Plugin-System
- AI-Integration
- Renderer
- UI / Viewport

Diese Punkte bleiben zukünftige Architektur- und Implementierungsaufgaben.

## 5. Konsequenz für `src/`

`src/core/` ist ab diesem Punkt **Referenz- und Vertragsbasis** für die nächsten Produktionsschichten.

Neue Produktionssysteme sollen den Core konsumieren, nicht ihn für jede neue UI-/Viewport-/Tool-Anforderung umbauen.

Grundrichtung:

```text
UI ──────────┐
             │
Tools ───────┼──► Core (FROZEN V1)
             │
Viewport ────┘
```

Die konkrete Produktionsstruktur außerhalb des Core wird erst aus den inzwischen gewachsenen Experimenten und echten Anforderungen abgeleitet.

## 6. Beziehung zu den Experimenten

Die Experimente bleiben bewusst erhalten. Sie sind Erkenntnis- und Validierungsräume, keine automatisch zu übernehmenden Produktionsmodule.

Insbesondere der Viewport-V1-Praxistest hat die Core→Viewport-Schnittstelle praktisch validiert, ist aber weiterhin ein Experiment.

## 7. Freeze-Regel für die Zukunft

Vor einer Änderung am gefrorenen Core gilt:

1. konkrete neue Anforderung benennen
2. prüfen, ob sie mit den bestehenden öffentlichen APIs lösbar ist
3. falls nicht: Architekturproblem dokumentieren
4. kleinste notwendige Core-Erweiterung bestimmen
5. Tests/Vertrag ergänzen
6. Änderung erst dann durchführen

Damit bleibt V1 klein, stabil und verständlich, ohne die Weiterentwicklung des Gesamtsystems zu blockieren.
