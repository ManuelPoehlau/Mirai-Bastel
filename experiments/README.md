# Experiments

Kleine technische Experimente und Praxistests. Experimente dürfen bewusst isoliert, minimal und nicht production-ready sein.

Sie dienen dazu, technische Fragen und Bedienideen praktisch zu prüfen, bevor daraus Produktionscode unter `src/` wird.

## Arbeitsregel für Agenten

Beim Arbeiten in einem Experiment zuerst dessen lokale `README.md` lesen. Sie ist der Einstiegspunkt und verweist auf die übergeordneten Architektur-/Design-Dokumente sowie auf die aktiven Pläne.

Experimentcode und Experimentdokumentation sind **keine automatische Produktionsspezifikation**. Erst eine bewusst getroffene Architekturentscheidung kann eine Erkenntnis in `src/` überführen.

**Nicht zu verwechseln mit `playground/experiments/`:** Dieses Verzeichnis hier ist die
Repository-Ebene — ein Ordner pro eigenständigem Forschungsprogramm (eigene README, eigene Tests,
teils eigener Core-Fork). `playground/experiments/` ist etwas anderes: Varianten-Familien
*innerhalb* des Artist-Playground-Hosts (`<family>/variant_*.py` + `decision.md`), mit eigenem
Verdikt-Mechanismus (KEEP/ITERATE/REJECT). Siehe
[`../docs/design/artist_playground/EXPERIMENT_HOST.md`](../docs/design/artist_playground/EXPERIMENT_HOST.md)
für die Playground-Seite. `playground/` selbst ist die einzige lauffähige Anwendung des Repos und
ist kein Eintrag hier, weil es kein Experiment im Sinne dieses Ordners ist — siehe
[`../playground/README.md`](../playground/README.md).

## Aktuelle Experimente

### `mirai_bastel_core_V1/`

Abgeschlossener und eingefrorener Core-V1-Milestone. Enthält den Referenzstand des Core-Experiments einschließlich Tests und Review-Material.

Aktuelle Architektur:

- [`../docs/architecture/V1_CORE.md`](../docs/architecture/V1_CORE.md)
- [`../docs/architecture/CORE_V1_FREEZE.md`](../docs/architecture/CORE_V1_FREEZE.md)

### `mirai_bastel_viewport_V1/`

Removed — see AD-006 and git history (`git log -- experiments/mirai_bastel_viewport_V1`).

### `mirai_bastel_viewport_V02/`

Abgeschlossenes technisches Architektur-Experiment (Proof, kein Production Viewport): prüft, ob Camera-, Selection-, Material- und Geometry-Änderungen gezielt ohne unnötige Mesh-/GPU-Rebuilds verarbeitet werden können, während Topology-Änderungen strukturelle Rebuilds erlauben. Ergebnis: Hypothese bestätigt (PROVEN); Ergebnisse fließen als Eingabe in die ausstehende Viewport-V0.2-Architekturspezifikation und danach in Gate 5 — Viewport Production.

Lokaler Einstieg: [`mirai_bastel_viewport_V02/README.md`](mirai_bastel_viewport_V02/README.md)

Research-Baseline: [`../docs/viewport/VIEWPORT_V02_RESEARCH.md`](../docs/viewport/VIEWPORT_V02_RESEARCH.md)

### `topology/`

Zentrale Dokumentations- und Planstelle für die Topology-Forschung. Der aktive Topology-Code lebt
heute in `playground/topology_tools/` (1:1-Ports gegen die Production-Core, siehe
`TOPOLOGY_EXPERIMENT_PLAN.md`); `mirai_bastel_viewport_V1/viewport/` enthält die ursprüngliche,
inzwischen portierte Fassung als Referenz.

Lokaler Einstieg: [`topology/README.md`](topology/README.md)

### `rigging-skinning-morphing/`

Research-Experiment zu Rigging, Skinning und Morph-Targets in Kombination mit
Topologie-Editing. Teilt seinen Head-Basemesh (`examples/meshes/head_basemesh.obj`, seit
[AD-007](../docs/architecture/AD-007-SHARED-ASSET-LOADER-OWNERSHIP.md)). Die frühere
V1-Viewport-Abhängigkeit (`run_viewport.py`) wurde per AD-006 (2026-09-17) entfernt —
der Artist Playground deckt diese Rolle ab.

Lokaler Einstieg: [`rigging-skinning-morphing/rigging-skinning-morphing-README.md`](rigging-skinning-morphing/rigging-skinning-morphing-README.md)

### `mirai_bastel_integration_lab/`

Removed — functionality graduated to src/mirai/ (AD-008). See git history.
