# Experiments

Kleine technische Experimente und Praxistests. Experimente dürfen bewusst isoliert, minimal und nicht production-ready sein.
Die Production-App (`src/main.py`) ist das Produkt; ein Lab gibt es nur für eine konkrete, offene Frage (AGENTS.md §7a).

## Arbeitsregel für Agenten

Beim Arbeiten in einem Experiment zuerst dessen lokale `README.md` lesen. Experimentcode und Experimentdokumentation sind
**keine automatische Produktionsspezifikation**. Erst eine bewusst getroffene Architekturentscheidung kann eine Erkenntnis
in `src/` überführen. Welche Tests wann laufen: AGENTS.md §8a.

## Aktiv

| Ordner | Zweck | Tests |
|---|---|---|
| [`morph_lab/`](morph_lab/README.md) | Morph-Ziel neben der Basis formen, Gewicht mischen (WP-MORPH-LAB-01). Seit 2026-10-27 hat die App selbst ein Ziel pro Mesh (AD-025 Phase 3); das Lab bleibt für Kiefer-Pose, relativ ↔ absolut und Neues, die App schickt mit `M` eine Kopie (`src/morph_bridge.py`). Nicht Artist-validiert | Standardlauf |
| [`mehlsack_lab/`](mehlsack_lab/README.md) | Box per Mausrad, Loop/Ring direkt ziehen, signierte Einflusskurve (WP-MEHLSACK-LAB-01). Geparkt (Manu, 2026-10-29): Code bleibt, kein offener Test in ATELIER | nur gezielt |
| [`goz_probe/`](goz_probe/README.md) | E1: GoZ-Handshake ZBrush 2022.0.8 ↔ Python (Registrierung als GoZ-App, Rückmeldung, Achsen, Reihenfolge) für die [ZBrush-Brücke](../docs/future_ideas/ZBRUSH_BRIDGE_AUDIT.md). Am 2026-11-05 auf dem Referenz-PC gelaufen: Handshake funktioniert (Ergebnis README §11); Grundlage für P1 | nur gezielt |
| [`drag_cost/`](drag_cost/README.md) | GL-Kostensonden für W-Drag, Navigation, Hover und Picking (WP-VIEW-PATCH-01, WP-VIEW-PERF-01); Messwerkzeug für die offene Viewport-Performance | nur gezielt |
| [`lookdev_gpu_probe/`](lookdev_gpu_probe/README.md) | Lookdev Schritt 1 (2026-11-13): GL-Fähigkeiten für den Augen-Test (Cubemaps RGBA16F / RGBA8, `textureLod`, Filterung, Nähte an den Würfelkanten) und Pixelkosten einer bildfüllenden Großaufnahme (Worklight über `drag_cost/probe_shading_gpu.py`), vor P1 aus dem [Lookdev-P0-Audit](../docs/research/LOOKDEV_P0_CODEBASE_AUDIT_2026-11-13.md) §10. Eigenes Fenster, importiert nichts aus `src/`. Auf dem Referenz-PC gelaufen (2026-11-13): Cubemaps ok, Nähte nur an den Würfelecken, Worklight-Großaufnahme 16 / 27 ms ([Ergebnis](lookdev_gpu_probe/RESULTS_REFERENCE_PC_2026-11-13.md)) | nur gezielt |
| [`lookdev_eye_lab/`](lookdev_eye_lab/README.md) | Lookdev P1, Augen-Test (2026-11-14): künstliches Auge (Lederhaut, Iris mit Pupille, Hornhaut) und Referenzkugeln im berechneten Studio; Techniken T-A (Worklight heute) bis T-D und Hornhaut C1–C3 aus dem [Lookdev-P0-Audit](../docs/research/LOOKDEV_P0_CODEBASE_AUDIT_2026-11-13.md) §5. Zeichnet über den Produktions-`Viewport` mit `EyeLabStore(GLRenderStore)`; kein Eingriff in `src/`. Referenz-PC (2026-11-14): sechsmal PASS, keine Würfelnähte, T-C 1–3 ms pro Bild ([Ergebnis](lookdev_eye_lab/RESULTS_REFERENCE_PC_2026-11-14.md)); Artist-Urteil offen | nur gezielt |
| [`surface_slide/`](surface_slide/README.md) | Surface Slide, Algorithmus-Forschung (2026-11-13): Kandidaten für das Gleiten von Vertices auf einer Referenzfläche (Closest Point, Ray, lokale Projektion, Geodäten inkrementell / absolut / mit Tempolimit) auf Kugel, Zylinder, U-Form und beiden Gollum-Meshes, mit Symmetrie und Soft Selection; nur NumPy, kein Fenster, liest `src/` nur zum Laden der Gollum-Szene. Kein Production-Code; Ergebnis und Empfehlung: [SURFACE_SLIDE_ALGORITHM_RESEARCH_2026-11-13.md](../docs/research/SURFACE_SLIDE_ALGORITHM_RESEARCH_2026-11-13.md); Production-Readiness-Audit mit Proben (`audit_2026-11-14/`): [SURFACE_SLIDE_PRODUCTION_READINESS_AUDIT_2026-11-14.md](../docs/research/SURFACE_SLIDE_PRODUCTION_READINESS_AUDIT_2026-11-14.md) | nur gezielt |
| [`gui_framework_spike/`](gui_framework_spike/README.md) | nur noch das Messskript `bench.py` (Frame-Zeit, Speicher, GL-Zustand mit/ohne Panel); der Spike ist seit 2026-11-07 nach `src/gui/` übernommen ([AD-030](../docs/architecture/AD-030-GUI-FRAMEWORK.md)) | nur gezielt |

## Regressionsschutz

| Ordner | Zweck | Tests |
|---|---|---|
| [`knife_oracle/`](knife_oracle/README.md) | Eingefrorene Knife-Face-Lab-Engines; hält den Production-Knife und `Mesh.split_face` fest | Trigger-Liste, AGENTS.md §8a |

## Entfernt am 2026-10-24 (Konsolidierung, Manus Entscheidung)

Der letzte Stand liegt in Commit `61ebe77` (`git show 61ebe77:<pfad>`, `git checkout 61ebe77 -- <pfad>`).
READMEs, Findings und Ergebnisse liegen in [`docs/archive/experiments_2026-10/`](../docs/archive/experiments_2026-10/).

| Pfad | Warum entfernt | Ersatz / Verbleib |
|---|---|---|
| `playground/` | optionales Werkzeug seit AD-011-Addendum; entschiedene Ergebnisse in `src/` | Articulation (EX-A) und Schattenkarte: Notiz in `docs/future_ideas/MODELING.md` |
| `experiments/symmetry_lab/` | Symmetrie komplett in der App (AD-SYM-04 A1–A3) | `src/mirai/symmetry*`, Tests `tests/test_application_symmetric_tools.py` |
| `experiments/subdivision_lab/` | SubD in der App (KEEP 2026-10-23) | `src/mirai/subdivision/` |
| `experiments/viewport_shading_lab/` | Rig in der App, Werte editierbar (AD-024) | `src/viewport/light_rig.py` |
| `experiments/soft_selection/` | übernommen (AD-020) | `src/mirai/soft_selection/` |
| `experiments/gpu_picking_spike/` | übernommen (AD-022) | `src/viewport/gpu_picker.py` |
| `experiments/topology_sync_stage1/`, `topology_stage2_delete/` | abgelöst durch AD-023 §9 | Change Journal in `src/core` |
| `experiments/viewport_draw_binding_spike/`, `ad018_gl_render_store_verification/` | Ergebnis in AD-018 | `src/viewport/gl_render_store.py` |
| `experiments/stage_a_entry_point_verification/` | Evidenz zu Stage A | `src/main.py` |
| `experiments/architecture_audit_probes/` | einmaliges Audit 2026-10-20 | `docs/research/viewport/ARCHITECTURE_AUDIT_2026-10-20.md` |
| `experiments/mirai_bastel_viewport_V02/` | PROVEN, übernommen | `src/viewport/` |
| `experiments/mirai_bastel_core_V1/` | eingefrorener Core-Fork, nur vom Rigging-Experiment genutzt | `src/core` |
| `experiments/rigging-skinning-morphing/` | nur vom Playground genutzt | Forschung im Archiv; AD-005 in `docs/architecture/` |
| `experiments/head_topology_walkthrough/` | lief nur auf dem Playground | Findings, Tutorial-Entwurf, Screenshots im Archiv |
| `experiments/topology/` | Discovery-Probes, teils schon defekt | `src/mirai/topology/`; README und Plan im Archiv |

Früher entfernt: `mirai_bastel_viewport_V1/` (AD-006), `mirai_bastel_integration_lab/` (AD-008) — siehe Git-Historie.
