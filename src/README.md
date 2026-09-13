# Source

Hier entsteht die eigentliche Anwendung.

## Aktueller Stand

Die aktuell implementierte Produktionsstruktur ist:

```text
src/
├── core/      3D-Domain: Scene, Mesh, Selection, Operations, History, Serialization
├── mirai/     Application-Orchestrierung, Interaction/Tools, Kamera, Picking, Display-State
└── viewport/  inkrementelle Renderdaten, Dirty-State, Overlay, Resource-Store, Fassade
```

`src/core/` basiert auf dem abgeschlossenen und eingefrorenen Core-V1-
Milestone. `src/mirai/` und `src/viewport/` sind die implementierte
Production-Foundation für Application/Interaction bzw. Viewport. Der
Viewport-V1-Code bleibt ein isolierter Praxistest unter
`experiments/mirai_bastel_viewport_V1/`.

Nicht vorhanden sind weiterhin ein Production-Fenster/Entry-Point, ein
Production-Draw-Call sowie eine festgelegte Modeling- oder Selection-UX.
Diese Bereiche werden nicht durch leere Ordner oder Vorabarchitektur
vorweggenommen.

## Grundregel

Code wird erst nach einem validierten Experiment oder einer klaren
Architekturentscheidung in `src/` übernommen. Experimente bleiben in
`experiments/` nachvollziehbar erhalten.
