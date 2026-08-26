# Source

Hier entsteht die eigentliche Anwendung.

## Aktueller Stand

`src/core/` enthält den derzeitigen Produktionspfad für den Core. Er basiert
auf dem abgeschlossenen Core-V1-Milestone und entspricht bewusst noch keiner
endgültigen Gesamtarchitektur.

Der interaktive Viewport aus
`experiments/mirai_bastel_viewport_V1/` bleibt vorerst ein isolierter
Praxistest. Seine Erkenntnisse werden verwendet, bevor der eigentliche
Viewport-/Application-Code unter `src/` aufgebaut wird.

## Geplante Bereiche

Die endgültige Aufteilung wird erst festgelegt, wenn die technischen
Grenzen zwischen Core, Viewport, Interaction und Application ausreichend
klar sind. Mögliche spätere Bereiche sind unter anderem:

- core/
- viewport/
- interaction/
- modeling/
- selection/
- tools/
- app/

Diese Liste ist eine Orientierung, keine festgeschriebene Architektur.

## Grundregel

Code wird erst nach einem validierten Experiment oder einer klaren
Architekturentscheidung in `src/` übernommen. Experimente bleiben in
`experiments/` nachvollziehbar erhalten.
