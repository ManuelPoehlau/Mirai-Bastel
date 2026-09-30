# Source

Hier entsteht die eigentliche Anwendung.

## Aktueller Stand (2026-09-29)

Die aktuell implementierte Produktionsstruktur ist:

```text
src/
├── core/      3D-Domain: Scene, Mesh, Selection, Operations (Move/Rotate/Scale, Topologie), History, Serialization
├── mirai/     Application-Orchestrierung, Interaction/Tools, Kamera, Picking (inkl. Pick-Cache),
│              Display-State, Topologie-Capabilities (Split/Connect/Knife), Symmetry V1, Scene-Factory
├── viewport/  inkrementelle Renderdaten, Dirty-State, Overlays, Resource-Store, GL-Render-Store, Fassade
└── main.py    Production-Entry-Point: eigenes Fenster (pyglet) auf dem echten Draw-Pfad
```

`src/core/` basiert auf dem abgeschlossenen und eingefrorenen Core-V1-
Milestone. Jede dokumentierte Ausnahme steht in
[`docs/architecture/CORE_V1_FREEZE.md`](../docs/architecture/CORE_V1_FREEZE.md) §7.1.
`src/mirai/` und `src/viewport/` sind die Production-Foundation für
Application/Interaction bzw. Viewport. Der frühere Viewport-V1-Code war ein
ausgemusterter Praxistest ([AD-006](../docs/architecture/AD-006-V1-VIEWPORT-RETIREMENT.md)); seine Rolle als Forschungsfenster übernimmt der Artist Playground (`playground/`).

Ein Production-Fenster (`src/main.py`) und der Production-Draw-Pfad
(`Application → Viewport → GLRenderStore`, AD-018) sind vorhanden
(Stage A, siehe
[`docs/architecture/PRODUCTION_ENTRY_POINT_STAGE_A.md`](../docs/architecture/PRODUCTION_ENTRY_POINT_STAGE_A.md)).
Stage B (WP-06) verdrahtet entschiedene Playground-Ergebnisse Slice für
Slice in dieses Fenster. Welche Capabilities schon drin sind und mit
welchem Verdikt-Stand (`PROMOTED` / `PROVISIONAL`), steht im Intake-Log
in [`docs/architecture/ROADMAP.md`](../docs/architecture/ROADMAP.md) §7
(WP-06) — dort ist die einzige maßgebliche Liste, hier wird sie bewusst
nicht wiederholt.

Nicht vorhanden bzw. bewusst offen sind weiterhin eine festgelegte
Gesamt-UX für Modeling und Selection, ein Application-UI außerhalb des
Viewports sowie alles aus den „Später"-Abschnitten der Roadmap
(Deformation, Rigging, Morph, Animation). Diese Bereiche werden nicht
durch leere Ordner oder Vorabarchitektur vorweggenommen.

Für die Verantwortungsgrenzen der Pakete siehe
[`docs/architecture/SOURCE_ARCHITECTURE.md`](../docs/architecture/SOURCE_ARCHITECTURE.md).

## Grundregel

Code wird erst nach einem validierten Experiment oder einer klaren
Architekturentscheidung in `src/` übernommen. Experimente bleiben in
`experiments/` bzw. im `playground/` nachvollziehbar erhalten. Die
Übernahme selbst ist eine dokumentierte Entscheidung (Promotion Boundary,
`MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` M3), kein stiller Merge.
