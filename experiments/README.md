# Experiments

Kleine technische Experimente und Praxistests. Experimente dürfen bewusst isoliert, minimal und nicht production-ready sein.

Sie dienen dazu, technische Fragen und Bedienideen praktisch zu prüfen, bevor daraus Produktionscode unter `src/` wird.

## Arbeitsregel für Agenten

Beim Arbeiten in einem Experiment zuerst dessen lokale `README.md` lesen. Sie ist der Einstiegspunkt und verweist auf die übergeordneten Architektur-/Design-Dokumente sowie auf die aktiven Pläne.

Experimentcode und Experimentdokumentation sind **keine automatische Produktionsspezifikation**. Erst eine bewusst getroffene Architekturentscheidung kann eine Erkenntnis in `src/` überführen.

## Aktuelle Experimente

### `mirai_bastel_core_V1/`

Abgeschlossener und eingefrorener Core-V1-Milestone. Enthält den Referenzstand des Core-Experiments einschließlich Tests und Review-Material.

Aktuelle Architektur:

- [`../docs/architecture/V1_CORE.md`](../docs/architecture/V1_CORE.md)
- [`../docs/architecture/CORE_V1_FREEZE.md`](../docs/architecture/CORE_V1_FREEZE.md)

### `mirai_bastel_viewport_V1/`

Aktives interaktives Forschungs- und Praxistestfeld für die Verbindung des Core mit einem minimalen OpenGL-Viewport. Der bisherige V1-Praxistest hat insbesondere Scene/Mesh, Selection, Move, Commit, History/Undo/Redo sowie grundlegende Kamera-Interaktion validiert.

Der Viewport-V1-Code ist **kein Produktions-Viewport**. Neue Selection- und Topology-Experimente bleiben hier, bis aus ihnen bewusst Produktionsanforderungen abgeleitet werden.

Lokaler Einstieg: [`mirai_bastel_viewport_V1/README.md`](mirai_bastel_viewport_V1/README.md)

### `topology/`

Zentrale Dokumentations- und Planstelle für die Topology-Forschung. Der experimentelle Topology-Code selbst liegt derzeit im Viewport-Experiment unter `mirai_bastel_viewport_V1/viewport/`.

Lokaler Einstieg: [`topology/README.md`](topology/README.md)

### `rigging-skinning-morphing/`

Research-Experiment zu Rigging, Skinning und Morph-Targets in Kombination mit
Topologie-Editing. Seit dem Viewport-Integrationsschritt stellt es seinen
Head-Basemesh (`meshes/head_basemesh.obj`) über einen minimalen Adapter als
normale `Scene`/`Mesh` im **vorhandenen Viewport V1** dar (All-Tools-Playground,
`python run_viewport.py`) — ohne Viewport-Fork und ohne Core-Änderung.

Lokaler Einstieg: [`rigging-skinning-morphing/rigging-skinning-morphing-README.md`](rigging-skinning-morphing/rigging-skinning-morphing-README.md)
