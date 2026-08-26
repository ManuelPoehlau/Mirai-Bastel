# Architektur

Dieses Dokument beschreibt die aktuelle architektonische Orientierung. Es
ist kein vollständiger Zielbaum der fertigen Anwendung. Konkrete Grenzen
werden anhand realer Experimente und Architekturentscheidungen weiter
präzisiert.

## Aktueller Entwicklungsstand

Der erste Core-V1-Milestone ist abgeschlossen. Sein Produktionspfad liegt
bereits unter `src/core/`; der vollständige V1-Stand bleibt zusätzlich unter
`experiments/mirai_bastel_core_V1/` als nachvollziehbarer Milestone erhalten.

Der anschließende Viewport-V1-Praxistest liegt vollständig unter
`experiments/mirai_bastel_viewport_V1/`. Er ist ein validierter technischer
Prototyp, aber **noch nicht** der Produktions-Viewport.

Die eigentliche `src/`-Gesamtstruktur wird erst nach der Auswertung dieser
Experimente festgelegt. Insbesondere werden `viewport`, `camera`,
`interaction`, `selection`, `modeling`, `tools` und `app` nicht vorschnell
als feste Top-Level-Pakete angelegt.

## Grundidee

Der Editor soll in klar getrennte Systeme aufgeteilt werden.

```text
Mesh / Scene Core
   │
   ├── Topology / Vertex / Edge / Face
   ├── History / Operations
   └── Scene state

Selection / Influence
   │
   └── Auswahlzustand und spätere Soft-Selection-Einflüsse

Viewport / Camera
   │
   ├── Projektion
   ├── Picking / Hover
   └── Darstellung

Interaction / Modeling Tools
   │
   ├── Transform / Tweak
   └── Modeling Operations

Application / UI
```

Diese Darstellung beschreibt Verantwortungsgrenzen, nicht zwingend die
spätere Ordnerstruktur.

## Mesh / Scene Core

Der Mesh-Core verwaltet Geometrie und Topologie. Er soll nicht wissen, ob
eine Änderung durch Tweak, Transform, Extrude oder ein späteres
Deformationssystem ausgelöst wurde.

Stabile Referenzen und saubere Nachbarschaftsbeziehungen sind wichtig für
spätere Erweiterungen.

## Selection

Selection beschreibt, welche Elemente ausgewählt sind. Soft Selection
kann dies um Influence-Gewichte erweitern, ohne einen separaten Selection
Mode zu erzwingen.

Selection soll nicht unnötig an eine bestimmte UI oder ausschließlich an
Mesh-Elemente gekoppelt werden, da spätere Systeme möglicherweise andere
Objekte auswählen (z. B. Bones, Keyframes oder Morph Channels).

## Viewport

Der Viewport ist für Kamera, Projektion, Picking, Hover und Darstellung
zuständig. Die Kamera ist ein eigenständiger Zustand und wird nicht mit
Objekttransformationen vermischt.

Der V1-Praxistest hat diese Trennung praktisch bestätigt: Kamera-/Picking-
Mathematik konnte weitgehend unabhängig von pyglet getestet werden, während
die eigentliche Fenster-/GL-Integration im Experiment blieb.

## Tools / Interaction

Tools erhalten Selection/Influence und erzeugen Transformationen oder
Topologieänderungen. UI-Gesten sollen nur Eingaben liefern, nicht die
Modellierungslogik enthalten.

Interaktive Operationen folgen grundsätzlich dem Lifecycle:

```text
begin()
   ↓
update()*
   ↓
commit()
```

oder:

```text
begin() → update()* → cancel()
```

`commit()` erzeugt genau einen logischen History-Schritt; `cancel()` keinen.

## History

History soll konzeptionell ein generischer reversibler Aktions-/Command-
Stack sein und nicht dauerhaft als Mesh-Diff-Mechanismus definiert werden.
Das erlaubt später grundsätzlich auch Aktionen aus Rigging, Pose oder
Animation.

## Langfristige Richtung

Die Datenstrukturen sollen später ein lebendiges Asset ermöglichen:

```text
Model → SubD → Morph → Rig → Pose → Animation
                    ↑
                 weiter modellieren
```

Das ist ein langfristiges Ziel und kein aktuelles V1-Feature-Set.

## Architekturprinzip

> **Implementiere wenig – berücksichtige viel.**

Bekannte zukünftige Anforderungen sollen durch stabile Grenzen nicht
unnötig erschwert werden. Gleichzeitig werden zukünftige Systeme erst dann
gebaut, wenn reale Anforderungen sie rechtfertigen.

Experimente dienen dabei als Beweis- und Lernstufen. Erst wenn eine Idee
technisch und praktisch ausreichend verstanden ist, wird entschieden, ob
und in welcher Form sie in `src/` übernommen wird.
