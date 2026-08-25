# Architektur

## Grundidee

Der Editor wird in klar getrennte Systeme aufgeteilt.

```text
Mesh Core
   │
   ├── Topology / Vertex / Edge / Face
   │
Selection ── Influence / Soft Selection
   │
Viewport / Camera ── Picking / Hover
   │
Modeling Tools ── Transform / Tweak / Modeling Operations
   │
Application / UI
```

## Mesh Core

Der Mesh-Core verwaltet Geometrie und Topologie. Er soll nicht wissen, ob eine Änderung durch Tweak, Transform, Extrude oder ein späteres Deformationssystem ausgelöst wurde.

Stabile Referenzen und saubere Nachbarschaftsbeziehungen sind wichtig für spätere Erweiterungen.

## Selection

Selection beschreibt, welche Elemente ausgewählt sind. Soft Selection erweitert dies um Influence-Gewichte, ohne einen separaten Selection Mode einzuführen.

## Viewport

Der Viewport ist für Kamera, Projektion, Picking, Hover und Darstellung zuständig. Die Kamera ist ein eigenständiger Zustand und wird nicht mit Objekttransformationen vermischt.

## Tools

Tools erhalten Selection/Influence und erzeugen Transformationen oder Topologieänderungen. UI-Gesten sollen nur Eingaben liefern, nicht die eigentliche Modellierungslogik enthalten.

## Langfristige Richtung

Die Datenstrukturen sollen später ein lebendiges Asset ermöglichen:

```text
Model → SubD → Morph → Rig → Pose → Animation
                    ↑
                 weiter modellieren
```

Das ist ein langfristiges Ziel und kein V1-Feature-Set.
