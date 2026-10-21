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

### `architecture_audit_probes/`

Drei lesende Mess-Skripte (Mesh-Kosten und Speicher, Morph-Blend-Arithmetik, Zerlegung des Viewport-Neuaufbaus bei Topologie-Operationen) für das Architektur-Audit 2026-10-20; das dritte öffnet ein verstecktes pyglet-Fenster. Siehe [README](architecture_audit_probes/README.md) und die [Audit-Kurzfassung](../docs/research/viewport/ARCHITECTURE_AUDIT_2026-10-20.md).

### `topology_sync_stage1/`

AD-023 Stufe 1 (V0, V2, V3, H0) als Experiment: von außen eingesetzt, `src/` unverändert, mit Gleichheitstests, einer Messsonde mit p95 und einem Starter für die App. Siehe [README](topology_sync_stage1/README.md).

### `topology_stage2_delete/`

AD-023 Stufe 2 (Delta-History H1, stellenweise gepatchte Buffer V1) zusammen mit AD-022 (GPU-Picking B2-out) als Prototyp, nur für Delete samt Undo/Redo: auf Stufe 1 aufgesetzt, `src/` unverändert, mit Gleichheitstests, einer Messsonde für alle Konfigurationen in einem Befehl, dem B2-Exaktheitscheck (`gl_PrimitiveID`) und einem Starter für die App. Siehe [README](topology_stage2_delete/README.md).

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
`TOPOLOGY_EXPERIMENT_PLAN.md`). Die ursprüngliche Fassung im entfernten `mirai_bastel_viewport_V1/`
ist nur noch Git-Historie (AD-006).

Lokaler Einstieg: [`topology/README.md`](topology/README.md)

### `head_topology_walkthrough/`

Discovery (Typ B): führt die Operationsketten D1 bis D11 des Research-Dokuments
[Character Head Topology — From Box to Deformation-Ready Face](../docs/research/topology/Character%20Head%20Topology%20From%20Box%20to%20Deformation-Ready%20Face.md)
mit den heute vorhandenen Werkzeugen (Playground-Topologie-Tools) aus und protokolliert pro Schritt, ob die Vorhersage des Dokuments hielt
(held / deviated / blocked). Enthält Schrittprotokoll, Findings, Tutorial-Entwurf (DE) und Screenshots (Xvfb-Capture). Nicht Artist-validiert.

Lokaler Einstieg: [`head_topology_walkthrough/README.md`](head_topology_walkthrough/README.md)

### `rigging-skinning-morphing/`

Research-Experiment zu Rigging, Skinning und Morph-Targets in Kombination mit
Topologie-Editing. Teilt seinen Head-Basemesh (`examples/meshes/head_basemesh.obj`, seit
[AD-007](../docs/architecture/AD-007-SHARED-ASSET-LOADER-OWNERSHIP.md)). Die frühere
V1-Viewport-Abhängigkeit (`run_viewport.py`) wurde per AD-006 (2026-09-17) entfernt —
der Artist Playground deckt diese Rolle ab.

Lokaler Einstieg: [`rigging-skinning-morphing/rigging-skinning-morphing-README.md`](rigging-skinning-morphing/rigging-skinning-morphing-README.md)

### `symmetry_lab/`

Symmetry Lab (WP-SYM-LAB-01): eigenständiges Fenster für die Symmetrie-Forschung, mit eigenem
minimalem Draw-Pfad, Production-`OrbitCamera` und Bindings im Lab-Kontext `symmetry_lab`.
Importiert bewusst nicht aus `playground/`. Seit WP-SYM-LAB-03 (abgeschlossen 2026-10-03) läuft das Lab
auf dem Production-Pfad (`src/mirai/application.py`); der eigene Renderer und der alte gespiegelte Knife
sind gelöscht. Danach kamen die symmetrischen Topologie-Werkzeuge (AD-SYM-03, Slices 3a–7: Connect,
Delete/Dissolve, Split, Knife, Extrude). Offene Artist-Verdikte: `docs/ATELIER.md`; Details in der
lokalen README.

Lokaler Einstieg: [`symmetry_lab/README.md`](symmetry_lab/README.md)

### `subdivision_lab/`

Subdivision Lab (WP-SUBD-LAB-01 Slice 1, WP-SUBD-LAB-02): uniformes Catmull-Clark als Stencils (reines Python), Testbogen
T-SUBD-1/T-SUBD-2 und Bench. Seit WP-SUBD-LAB-02 (2026-10-16) läuft es auf dem App-Pfad wie das Symmetry Lab: alle
Werkzeuge, Licht und Shading sind die der App; die glatte Fläche zeichnet der Viewport über den generischen Haken
AD-013 H7 (`set_surface_provider`) statt der Flächen des Käfigs. Subdivision selbst ist nicht in `src/`. Das alte
eigene Fenster: `run_standalone.py`. Nicht Artist-validiert —
[`subdivision_lab/README.md`](subdivision_lab/README.md).

### `morph_lab/`

Morph Lab (WP-MORPH-LAB-01, 2026-10-16): eine Basis, ein Morph-Ziel daneben (eigenes Objekt mit denselben Punkt-Nummern),
Gewicht per Tasten. Läuft auf dem App-Pfad wie das SubD Lab; das Ziel wird mit den Werkzeugen der App geformt, die Mischung
zeichnet der Viewport über AD-013 H7 (zweiter Nutzer, Review CLAUDE-001). Morph ist nicht in `src/`. Nicht Artist-validiert —
[`morph_lab/README.md`](morph_lab/README.md).

### `soft_selection/`

Soft Selection (WP-SOFT-01 S1, headless, Typ B): Influence-Map (euklidisch/geodätisch, smooth/linear) und gewichtete Move/Rotate/Scale als Unterklassen der Core-Ops, Kostenprobe auf Kopf und Ganzkörper; keine Defaults, kein Fenster — [`soft_selection/README.md`](soft_selection/README.md), Ergebnisse in [`soft_selection/FINDINGS.md`](soft_selection/FINDINGS.md).

### `mehlsack_lab/`

Mehlsack Lab (WP-MEHLSACK-LAB-01 Slices 1, 2a, 2b, 3, 3b, 3c, Discovery Typ B): eigenes Fenster; Box per Mausrad bauen
(Höhe, Breite, Tiefe), dann das gehoverte Element (oder im `L`-Modus den Loop/Ring) ohne Auswahl direkt ziehen oder mit
`W`/`E`/`R` halten verschieben, drehen, skalieren (zwei Scale-Formeln). Seit Slice 3 alternativ eine
Punkt-/Kanten-/Flächen-Auswahl (Klick mit Shift/Ctrl/Alt, Shift+L/R, Doppelklick-Loops, Umrechnen per
Shift+`1`/`2`/`3`), von der dieselben Gesten ausgehen; Klick ins Leere = zurück zum Hover. Mitbewegung über die
Soft-Selection-Abstände aus `src` mit einer Bézier-Kurve, die unter null gehen darf (negative Gewichte bewegen
entgegen), optionale Flächen-Vorschau. Importiert aus `playground/` nur `topology_tools.loop_ring`. Verdikte für
Slices 1, 2a, 2b, 3 und 3b liegen vor (Manu, 2026-10-13); Slice 3c ist nicht Artist-validiert —
[`mehlsack_lab/README.md`](mehlsack_lab/README.md).

### `drag_cost/`

Drag-Kosten-Sonde mit dem echten GL-Backend (WP-VIEW-PATCH-01, Typ A): misst pro Mausbewegung eines W-Drags Transform-Schritt, `Viewport.sync()` und `GLRenderStore.update` getrennt (p50/p95) in einem unsichtbaren pyglet-Fenster; ein Szenario pro Funktion (S2b ergänzt den Soft-Drag). Vorher/Nachher des Slice-only-Patches (Container) im README — [`drag_cost/README.md`](drag_cost/README.md).
Zweite Sonde `probe_navigation_gl.py` (WP-VIEW-PERF-01, Discovery): Orbit/Pan/Zoom, Hover, Klick und W-Drags pro
Event + Frame auf Kopf, Körper und `gollum.obj` (21 875 V), mit Picking-Aufteilung, GPU-Timer und cProfile.

### `gpu_picking_spike/`

GPU-ID-Buffer-Picking (WP-VIEW-PERF-02, Discovery-Spike, ändert nichts unter `src/`): Faces/Kanten/Vertices als ID-Farben in einen Offscreen-Framebuffer, Vergleich mit dem Production-CPU-Picker (Übereinstimmung + Kosten). Grundlage für [AD-022](../docs/architecture/AD-022-GPU-PICKING.md) (PROPOSED) — [`gpu_picking_spike/README.md`](gpu_picking_spike/README.md).

### `viewport_shading_lab/`

Viewport Shading Lab (WP-SHADE-LAB-01): eigenständiges Fenster für die Worklight-Forschung. Seit
2026-10-15 ist das Rig in der App; der Lab-Store zeichnet mit dem Production-Shader und liefert nur das Rig. Importiert
nicht aus `playground/` oder anderen Experimenten. Stand Slice 1: Zwei-Licht-Rig (Key + Fill) mit
Presets, A/B-Vergleich gegen „Heute“ und Aufnahme. Jede Rig-Änderung kostet nachweislich null
Buffer-Uploads. Nicht Artist-validiert.

Lokaler Einstieg: [`viewport_shading_lab/README.md`](viewport_shading_lab/README.md)

### `viewport_draw_binding_spike/`

Research-Paket (Typ B) zum Draw-Binding zwischen Production-Viewport und Rendering. Seine Ergebnisse
fließen in [AD-018](../docs/architecture/AD-018-PRODUCTION-DRAW-BINDING.md) (entschieden 2026-09-25); das
Experiment selbst ändert keine Architekturentscheidung.

Lokaler Einstieg: [`viewport_draw_binding_spike/README.md`](viewport_draw_binding_spike/README.md)

### `ad018_gl_render_store_verification/`

Wegwerf-Evidenzskripte für die AD-018-Option-B-Implementierung (`GLRenderStore`). Kein Production-Entry-Point.

Lokaler Einstieg: [`ad018_gl_render_store_verification/README.md`](ad018_gl_render_store_verification/README.md)

### `stage_a_entry_point_verification/`

Headless-Evidenzlauf (`run_headless_evidence.py`, Screenshot) zu Stage A (`src/main.py`). Keine lokale README;
Kontext: [`../docs/architecture/PRODUCTION_ENTRY_POINT_STAGE_A.md`](../docs/architecture/PRODUCTION_ENTRY_POINT_STAGE_A.md).

### `mirai_bastel_integration_lab/`

Removed — functionality graduated to src/mirai/ (AD-008). See git history.
