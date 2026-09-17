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

**Status (aktualisiert 2026-09-17, [AD-006](../docs/architecture/AD-006-V1-VIEWPORT-RETIREMENT.md)):
retiriert — kein aktives Forschungsfeld mehr, kein aktiver Consumer mehr vorgesehen.**

Bis 2026-09-17 hatte V1 noch einen einzigen Laufzeit-Consumer
(`experiments/rigging-skinning-morphing/run_viewport.py`, Betrachten/Von-Hand-Bearbeiten des
Head-Basemesh). Per Artist-Verdikt (AD-006) ist diese Rolle nicht mehr nötig — der Playground
(Taste `H`) deckt sie ab. **Die eigentliche Portierung/Entfernung von `run_viewport.py` ist noch
nicht ausgeführt** — AD-006 hält nur die Entscheidung fest, nicht die Umsetzung.

V1 bleibt als **reine Archiv-/Referenzquelle** erhalten (Projektgedächtnis nach `AGENTS.md` M1):
Ursprungsreferenz für bereits nach `src/mirai/*` promovierten Code (Vecmath, Camera, Picking,
Commands, Bindings, Tool-Lifecycle, Move/Transform-Tools) und für die nach
`playground/topology_tools/` portierten Topology-Primitive. Sein Testbaum ist vollständig grün
(184 Tests + 21 Subtests, headless) und bleibt es auch nach der Retirierung.

Lokaler Einstieg: [`mirai_bastel_viewport_V1/README.md`](mirai_bastel_viewport_V1/README.md)

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
Topologie-Editing. Stellt seinen Head-Basemesh (`examples/meshes/head_basemesh.obj`, geteilt seit
[AD-007](../docs/architecture/AD-007-SHARED-ASSET-LOADER-OWNERSHIP.md)) bisher über einen
minimalen Adapter als normale `Scene`/`Mesh` im **V1-Viewport** dar (All-Tools-Playground,
`python run_viewport.py`) — ohne Viewport-Fork und ohne Core-Änderung. **Diese Abhängigkeit ist seit
[AD-006](../docs/architecture/AD-006-V1-VIEWPORT-RETIREMENT.md) (2026-09-17) zur Portierung
vorgesehen** (V1 ist retiriert); `run_viewport.py` selbst ist noch nicht angepasst.

Lokaler Einstieg: [`rigging-skinning-morphing/rigging-skinning-morphing-README.md`](rigging-skinning-morphing/rigging-skinning-morphing-README.md)

### `mirai_bastel_integration_lab/`

Integration Harness / Test Studio (kein Production-Viewport, kein Modeler).
**Seit WP-IL-01 (2026-09-08) production-basiert:** nutzt die Production-Kamera
(`src/mirai/viewport/camera.py`) und den Production-Viewport
(`src/viewport`, Gate 5/7) über eine dünne Adapter-Fassade; das
V0.2-Experiment wird nicht mehr importiert. Kern: Objekt-Ketten aus
`core.Scene` + je einem Production-`Viewport`, kategoriebewusste Updates
über die Production-Notifikations-API (`on_*_changed` → `sync()`), ein
pyglet/OpenGL-Harness für echten Draw + Instrumentierung und headless
Performance-/Status-Reports. Re-Base-Begründung und -Befunde:
[`mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md`](mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md)

Lokaler Einstieg: [`mirai_bastel_integration_lab/README.md`](mirai_bastel_integration_lab/README.md)
