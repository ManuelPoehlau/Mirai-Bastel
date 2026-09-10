# Mirai-Bastel — Artist Playground

**Zweck:** Neutraler Experimentier-Host für Artist-Feedback. Hier werden Interaction-,
Viewport- und Modeling-Fragen als Varianten getestet — bevor etwas als Candidate in die
Production wandert. Der Grundsatz: *Production ist nicht der Ort, wo wir herausfinden, was gut
ist; Production ist der Ort, wo sauber implementiert wird, was sich bewährt hat.*

**Abgrenzung zu Production:** Der Playground ist **kein Production-Code**. Er nutzt Production
über Adapter (🔵 WRAP) und lässt `src/` (insbesondere `src/core/` und `src/viewport/`)
unverändert. Experiment-Erkenntnisse werden dokumentiert und erst nach einer bewussten
Entscheidung zu Production-Kandidaten.

## Status AP-02.5 — Viewport Presentation Lab ✓

**Branch:** `experiment/artist-playground-v1` | **Baseline-Commit:** `b9b7ea6`

WP-AP-02.5 ist abgeschlossen und eingefroren:

- `vbo_builder.py` — Pure VBO-Daten-Builder (headless testbar): `build_face_data`, `build_edge_data`, `build_vertex_data` (🔴 NEW)
- `PlaygroundWindow` — Multi-Pass-Rendering: Phong-Face-Pass (Smooth/Flat via `u_use_flat`), Flat-Color-Overlay-Pass für Edges (`GL_LINES`) und Vertices (`GL_POINTS`) (🟡 ADAPT)
- `PlaygroundApp` — `display_state: DisplayState` + `show_vertices: bool` (🟡 ADAPT)
- `PlaygroundHUD` — 4. Zeile für Display-Mode (🟡 ADAPT)
- `experiments/presentation/` — 6 `PresentationExperiment`-Varianten: Shaded, Flat, Wireframe, Shaded+Wire, Shaded+V, Full (🔴 NEW)
- 27 neue Headless-Tests, alle 71 Playground-Tests + 383 Production-Tests grün

**Darstellungsmodi:**

| Modus | Taste(n) |
|---|---|
| Smooth Shaded | Default |
| Flat Shaded | `D` |
| Wireframe | `D D` |
| +Wireframe-Overlay | `Z` |
| +Vertices | `V` |

**Wiederverwendet (unverändert):** `DisplayState`, `DerivedGeometry.face_normals/vertex_normals`, `triangulate_face()`

**Nächster Schritt:** AP-03 Phase 0 — Playground Controls (Input-Config), dann AP-03 Selection Lab

---

## Status AP-02 — Experiment Host ✓

**Branch:** `experiment/artist-playground-v1`

WP-AP-02 ist implementiert:

- `ExperimentSlot` (`slot.py`) — Container für Experiment-Varianten mit Aktivierung und Decision-Status (🔴 NEW)
- `VariantEntry` + `Decision` — KEEP / ITERATE / REJECT pro Variante (🔴 NEW)
- `generate_decision_md()` / `write_decision_md()` — Git-freundliches Decision-Template (🔴 NEW)
- `PlaygroundApp.set_slot()` + `activate_variant()` — Slot-Integration in den Orchestrator (🔴 NEW)
- `PlaygroundHUD` zeigt Decision-Status an (UNDECIDED wird unterdrückt) (🟡 ADAPT)
- `playground/experiments/` — Dateistruktur für Varianten und `decision.md` (🔴 NEW)
- 18 neue Headless-Tests, alle 383 Production-Tests grün

**Dateistruktur für neue Experimente:**

```
playground/experiments/<experiment_id>/
    variant_a.py    ← erbt von Experiment, überschreibt Hooks
    variant_b.py
    decision.md     ← per slot.write_decision_md() erzeugt
```

## Status AP-01 — Foundation ✓

WP-AP-01 ist abgeschlossen:

- `PlaygroundWindow` — leichtgewichtiges pyglet-Fenster (🔴 NEW)
- `PlaygroundApp` — Orchestrator, wrapped `Application` (🔵 WRAP)
- `PlaygroundRenderer` — Adapter auf den Production Viewport (🔵 WRAP)
- `PlaygroundHUD` — Standalone-HUD (🟡 ADAPT)
- Cube + Head-Basemesh ladbar, Kamera-Input (Orbit/Pan/Zoom) aktiv (🟢 REUSE)

## Startbefehle

```bash
python playground/run.py          # Cube (default)
python playground/run.py cube     # explizit Cube
python playground/run.py head     # Head-Basemesh
python -m playground.run head     # alternativ als Modul
```

**Steuerung:** LMB ziehen = Orbit · MMB/Shift+LMB = Pan · Mausrad = Zoom · `C`/`H` = Szene
wechseln · `D` = Display-Mode · `Z` = Wireframe-Overlay · `V` = Vertices · `Q`/`Esc` = Beenden.

## Hinweis: Kamera/GL-Befund

Der erste Artist-Lauf hatte einen technischen Befund sichtbar gemacht: Im direkten GL-Draw
clippte die Production `OrbitCamera` das Mesh (View-Matrix- vs. OpenGL-Projektions-Konvention,
[Audit §A.1]). **Fix auf Playground-Seite umgesetzt (2026-09-10):** Eine `PlaygroundCamera`
(Playground-GL-Grenze) überschreibt nur `build_view_matrix()` (gluLookAt-Konvention), analog
zum Integration Lab. Picking-/Kamera-Mathematik und Production (`src/`) bleiben unverändert.

- Investigation (Status Production-Kamera weiter offen): [`docs/research/viewport/production_camera_gl_convention.md`](../docs/research/viewport/production_camera_gl_convention.md)
- Autoritativer Detail-Befund (SSOT): Integration-Lab-Reconciliation-Audit **§A.1** —
  [`experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md`](../experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md)

## Siehe auch

- Architecture Map: [`docs/design/artist_playground/ARCHITECTURE_MAP.md`](../docs/design/artist_playground/ARCHITECTURE_MAP.md)
- Roadmap: [`docs/design/artist_playground/ROADMAP.md`](../docs/design/artist_playground/ROADMAP.md)
- Integration Lab (Referenz-Harness): [`experiments/mirai_bastel_integration_lab/README.md`](../experiments/mirai_bastel_integration_lab/README.md)