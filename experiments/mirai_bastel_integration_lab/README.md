# Mirai-Bastel — Integration Lab / Test Studio

**Status:** Laufendes Integration-Harness-Experiment (additiv, isoliert).
**Gültigkeit:** KEIN Production-Viewport, KEIN neuer Modeler, KEIN Gate-5-Baustein.
`src/core` und die bestehenden Experimente wurden NICHT verändert.

Übergeordnete Dokumente:

- Experiment-Index: [`../README.md`](../README.md)
- Viewport V0.2 Experiment: [`../mirai_bastel_viewport_V02/README.md`](../mirai_bastel_viewport_V02/README.md)
- OBJ-Loader + Asset: [`../rigging-skinning-morphing/rigging-skinning-morphing-README.md`](../rigging-skinning-morphing/rigging-skinning-morphing-README.md)
- Core (Domain-Wahrheit): [`../../src/README.md`](../../src/README.md)

Audits / Reviews:

- Architecture Reconciliation Audit — Lab vs. Production (Gate 5/6/7), 2026-09-08, inkl. WP-IL-01 (Re-Base auf Production Camera/Viewport): [`docs/ARCHITECTURE_RECONCILIATION_AUDIT.md`](docs/ARCHITECTURE_RECONCILIATION_AUDIT.md)

---

## 1. Zweck

Wir besitzen mehrere unabhängig entwickelte, teilweise validierte Bausteine:

- `src/core` — Gate-4-Production-Foundation (Mesh/Scene/Selection/History),
- der OBJ Loader aus dem Rigging/Skinning/Morphing-Experiment,
- das Head-Basemesh-Asset,
- den Viewport-V0.2-Incremental-Update-Proof,
- verschiedene Interaction-/Topology-Experimente.

Das Integration Lab bringt diese **erstmals in einer gemeinsamen praktischen
Testumgebung** zusammen. Es ist ein **Integration Harness / Test Studio**,
mit dem sichtbar wird, wie gut die vorhandenen Komponenten zusammenarbeiten
und wo echte Integrationsprobleme liegen.

> **Das Integration Lab verbindet die Experimente – es ersetzt sie nicht.
> `src/core` ist die Domain-Wahrheit. V0.2 ist die Render-/Performance-Schicht.
> Adapter verbinden beide.**

## 2. Architektur

```text
OBJ
 ↓
ObjMeshData                       (OBJ Loader, unverändert wiederverwendet)
 ↓
src/core.Scene / src/core.Mesh    (Domain-Wahrheit; Polygone bleiben Polygone)
 ↓
Core → Render Adapter             (Triangulierung + VertexId↔Render-Index)
 ↓
V0.2 Render Representation        (positions + triangles, adjazent)
 ↓
V0.2 Renderer / Lab-Viewport      (RenderMesh + TraceStore/PygletStore)
```

Zwei bewusst getrennte Mesh-Repräsentationen, die NICHT künstlich
vereinheitlicht werden:

| Schicht | Datei | Rolle |
|---|---|---|
| Domain (src/core) | `src/core/mesh.py` | Wahrheit: polygonbasiert, opake IDs |
| Render (V0.2) | `experiments/mirai_bastel_viewport_V02/mesh.py` | abgeleitet: trianguliert, Listen-Indices |

### Update-Kategorien (aus V0.2 übernommen, bewusst unverändert)

| Änderung | V0.2-Kanal | Effekt |
|---|---|---|
| Camera | `camera` | nur Uniforms |
| Selection | `selection` | nur Highlight-Overlay |
| Material | `material` | nur Material-Uniforms |
| Vertex-Move | `geometry` | Positions-/Normalen-Partial-Updates |
| Topology | `topology` | struktureller Rebuild (im Lab vorbereitet, noch nicht interaktiv) |

## 3. Verantwortlichkeiten

| Baustein | Verantwortung | Bewusst NICHT |
|---|---|---|
| OBJ Loader (`rigging-skinning-morphing/loaders/obj_loader.py`) | OBJ → ObjMeshData, headless, ohne Core/Viewport/pyglet | keine Triangulierung, kein Rendering, kein Core-Wissen |
| `src/core` | Domain-Wahrheit: Topologie, IDs, Positionen, Selection, History | kein Rendering |
| Integration Adapter (`adapters/`) | Übersetzung an den Grenzen (obj→core, core→render, picking) | keine neue System-Architektur |
| V0.2 Renderer (`mirai_bastel_viewport_V02/`) | Render-Darstellung, DirtyState-Kategorien, Resource-Store | bleibt unverändert |

## 4. Dateien / Komponenten

```text
experiments/mirai_bastel_integration_lab/
├── README.md               # dieses Dokument
├── run.py                  # interaktiver Start (Fenster)
├── report.py               # headless Performance-/Status-Probe (TraceStore)
├── _smoke_window.py        # Kurzzeit-Smoke des Fensters (schließt nach 1,5 s)
├── _paths.py               # sys.path-Bootstrap (Lab/Root/Rigging-Ordner)
├── lab_camera.py           # V0.2 OrbitCamera + Projektion/Ray/Deltas + GL-View-Matrix-Fix
├── scene/
│   ├── scene.py            # LabScene + LabObject (unabhängige Core-Scenes)
│   └── scene_objects.py    # Cube + reales Head-Basemesh, build_lab_scene()
├── adapters/
│   ├── obj_to_core.py      # ObjMeshData → src.core (Loader wiederverwendet)
│   ├── triangulate.py      # Polygon-Triangulierung (nur Render-Darstellung)
│   ├── core_to_render.py   # src.core.Mesh → V0.2-Mesh + Index-Map + Binding
│   └── picking.py          # Screen-Space-Vertex-Picking (Core-IDs)
├── integration/
│   └── lab_viewport.py     # pyglet-Fenster (mehrere Objekte, Live-Statistik)
└── tests/                  # headless Integration-Boundary-Tests (33 Stück)
```
## 5. Aktueller Stand

**funktioniert (durch Tests + Report + Fenster-Smoke verifiziert):**

- [x] OBJ Loader wird unverändert wiederverwendet (`OBJ → ObjMeshData`)
- [x] OBJ-Daten werden in `src.core.Scene/Mesh` überführt
- [x] reales Head-Basemesh (`meshes/head_basemesh.obj`) wird geladen
- [x] Cube als kontrolliertes Testobjekt (8 Verts / 6 Quads)
- [x] Core → V0.2 Render Adapter inkl. Triangulierung (Quad → 2 Tris)
- [x] Kategoriebewusster Sync: Camera → nur Uniforms; Selection → nur Overlay;
      Vertex-Move → nur Geometry-Partial-Updates
- [x] Vertex-Move verändert ZUERST `src.core.Mesh`, die Render-Darstellung
      ist davon abgeleitet
- [x] Kamera Orbit + Zoom (+ Pan), Objekt-Auswahl, Vertex-Picking/-Move,
      Live-FPS- und Zähler-Anzeige im Fenster
- [x] 33 headless Boundary-Tests (OBJ→Core, Core→Render, Geometry-Update,
      Scene, Triangulierung, Kamera/Picking, Imports)
- [x] **View-Matrix-Fix (echter Integrationsbefund):** Die V0.2-View-Matrix
      (+forward in Zeile 3) clippte bei der GL-Projektion sämtliche
      Front-Geometrie (schwarzer Viewport). Das Lab überschreibt
      `build_view_matrix` in `lab_camera.py` mit der gluLookAt-Konvention;
      V0.2 bleibt unverändert. Regressions-Tests in
      `tests/test_camera_picking.py`.

**experimentell / vorbereitet, aber noch nicht interaktiv verdrahtet:**

- Topology-Pfad: `CoreRenderBinding.rebuild_from_core()` (struktureller
  Rebuild über `RenderMesh.apply_topology`), test-/reportseitig nutzbar.
- Undo/Redo der Move-Interaktion über `src.core.MoveOperation`
  (Lifecycle + History sind im Core vorhanden; der Lab-Move nutzt für den
  ersten Test bewusst das flache `set_vertex_position`, damit die Kette
  Core→Render minimal bleibt).

**noch nicht integriert (bewusst draußen):**

- Interaction-Lab (Viewport-V1-Tools: Move/Transform/Extrude-Tools,
  Input-Bindings, Topology-Tools) — die V1-Tools hängen am eingefrorenen
  V1-Core (`mirai_bastel_core`); die stabilen, core-unabhängigen Teile
  (Kamera-Picking-Mathematik) wurden in `lab_camera.py`/`picking.py`
  adaptiert. Die Werkzeuge selbst sind ein späterer Schritt.
- Topology-Experiment (Loop/Ring/Connect-Edges) — lauffähig nur im
  V1-Viewport; die Core-Primitives (`connect_vertices`, `remove_vertex`)
  existieren in `src/core`, eine saubere Adapter-Integration ist
  dokumentierter Folgeschritt.

## 6. Erste Zielszene & Interaktion

Beim Start entsteht die Testszene `Cube + Head Basemesh`. Jedes Objekt hält
eine **eigene** `src.core.Scene` (eigene Mesh/Selection/History).

```text
Start
 ↓
Cube + Head laden
 ↓
Objekt auswählen (1/2)
 ↓
Head anzeigen (Auto-Frame)
 ↓
Kamera orbitieren / zoomen  (LMB-Ziehen / Mausrad)
 ↓
Vertex auswählen            (LMB-Klick, Shift+LMB toggelt)
 ↓
Vertex bewegen              (M → +0.35 in Welt-Y)
 ↓
src.core.Mesh wird verändert
 ↓
Render Representation wird aktualisiert (Geometry-Partial-Update)
 ↓
V0.2 Renderer zeigt die Änderung
```

Steuerung:

| Eingabe | Aktion |
|---|---|
| LMB ziehen | Orbit |
| Shift+LMB / MMB ziehen | Pan |
| Mausrad | Zoom |
| LMB-Klick | Vertex auswählen (Shift: toggeln) |
| M | selektierten Vertex bewegen (+Y) |
| 1 / 2 | Objekt auswählen (Cube <-> Head) + Kamera-Frame |
| R | Kamera auf aktives Objekt rahmen |
| S | Report/Statistik in der Konsole |
| Esc / Q | Beenden |
## 7. Performance-Beobachtungen — Head Basemesh (gemessen 2026-07-09)

Head-Basemesh-Kennzahlen (reales Asset, über den OBJ Loader):

| Kennzahl | Wert |
|---|---|
| Vertices | 326 |
| Edges | 648 |
| Faces | 324 (alle Quads) |
| Render-Triangles (nach Adapter-Triangulierung) | 648 |

Gemessene Zeiten des Headless-Reports (`python report.py`, `TraceStore`,
CPU-Buchhaltung, Python 3.14, keine GPU):

| Szenario | Messung | Beobachtung |
|---|---|---|
| Initialer Aufbau (Ableitung + RenderMesh.build) | ~17,9 ms | einmalig pro Objekt |
| 60 Kamera-Orbits | ~1,2 ms gesamt (~0,02 ms/Op) | `mesh_rebuilds = 0`; Ressourcen-IDs stabil |
| 20 Selection-Sets | ~1,4 ms gesamt (~0,07 ms/Op) | nur Overlay; `mesh_rebuilds = 0` |
| 40 Vertex-Moves | ~16,8 ms gesamt (~0,42 ms/Move) | nur Positions-/Normalen-Partial-Updates; `mesh_rebuilds = 0` |

**Einordnung zur ursprünglichen Lag-Frage:** Das Head-Basemesh ist mit
326 Vertices / 648 Render-Triangles ein kleines Mesh. An der Core→Render-
Grenze entsteht durch Kamera-/Selection-Operationen **kein** Mesh-Rebuild —
die V0.2-Kategorien halten die Geometrie unangetastet. Der früher beobachtete
Lag („Head laggt im alten Viewport“) ist damit an dieser Integrationsgrenze
nicht durch die Mesh-Größe erklärbar; er lag voraussichtlich in der
Voll-Rebuild-Strategie des alten Viewports (jedes Event → komplette
Render-Geometrie neu), die V0.2 gezielt vermeidet.

GPU-Frame-Zeiten (echte FPS) lassen sich nur interaktiv messen: Das Fenster
zeigt unten links einen laufenden FPS-Wert; `S` druckt den Report.
Diese Kennzahlen sind maschinenspezifisch und dienen der praktischen
Einordnung, nicht als Benchmark-Suite (bewusst, gemäß Task).

## 8. Tests / Ausführen

```text
python experiments/mirai_bastel_integration_lab/report.py     # headless Probe
python experiments/mirai_bastel_integration_lab/run.py        # interaktives Fenster

# Tests (headless, ohne GPU):
python -m pytest experiments/mirai_bastel_integration_lab/tests -q
```

Testabdeckung der Integrationsgrenzen:

| Grenze | Testdatei |
|---|---|
| OBJ → Core (Loader-Reuse, Zahlen, Positionen, Edges) | `tests/test_obj_to_core.py` |
| Core → Render (Vertices, Faces, Triangulierung, Index-Map) | `tests/test_core_to_render.py` |
| Geometry-Update (Core zuerst, Render abgeleitet, kein Rebuild) | `tests/test_geometry_update.py` |
| Scene (Cube+Head, unabhängige Auswahl, Framing) | `tests/test_scene.py` |
| Triangulierung (konvex/konkav/N-gon/Fallback) | `tests/test_triangulate.py` |
| Kamera/Picking (Projektion, Konsistenz, V0.2-Kompatibilität) | `tests/test_camera_picking.py` |
| Imports der interaktiven Schicht | `tests/test_imports.py` |

## 9. Bekannte Grenzen & Entscheidungen

- **V0.2-View-Matrix-Bug (fund, behoben im Lab):** Die V0.2 `build_view_matrix`
  schreibt +forward in die dritte Zeile (Front-Punkte auf positivem Camera-Z),
  während die V0.2-Projektion Standard-GL ist (clip.w = -view.z). Folge:
  clip.w < 0 für alles vor der Kamera → komplettes Clipping → schwarzer
  Viewport (Ursprung bei yaw=45°/pitch=25°/dist=8: view.z=+8 → clip.w=-8).
  Der V0.2-Demonstrator offenbarte das nie, weil sein Render-Pfad nie live
  ausgeübt wurde. Fix: Override in `lab_camera.LabOrbitCamera` (gluLookAt-
  Konvention), Picking unverändert konsistent (NDC.xy = cam.xy/(cam_z·half)).
  V0.2 selbst bleibt unberührt — Korrektur dort ist eine eigene Entscheidung.
- **pyglet 2.1 Windows-Fenster-Details (Lab-lokal behandelt):** ohne explizite
  `gl.Config` entsteht kein Depth-Puffer (unsichtbare Flächen); Modifier-
  Konstanten liegen in `pyglet.window.key`, nicht `mouse` (V0.2-Demonstrator
  nutzt veraltet `_m.MOD_SHIFT`); transiente `on_resize(height=0)` beim
  Start erfordert einen Aspect-Guard. Alles additiv im Lab gehandhabt.
- **Laufzeit-Nachweis Event-Kette & HUD (Probe 2026-07-09, temporär, außerhalb
  des Repos):** Alle Handler (`on_mouse_press/drag/release/scroll/key_press`)
  werden über pyglets Dispatch-Pfad aufgerufen und verändern den Kamera-State
  nachweislich (Δyaw +0.18, Δpitch +0.12, Distanz 5.20 → 4.68, Pan-Ziel).
  Click-Selection erreicht `_handle_click_selection` und mutiert die Core-
  Selection; `M` erreicht `_move_picked_vertex` und ändert die Position in
  `src.core.Mesh` um +0.35 Y, davon abgeleitet die Render-Daten. HUD:
  `_status.draw()` zeichnet korrekt (~6k Text-Pixel); unsichtbar war der Text
  zuvor nur, weil bei nah herangezoomtem Mesh der aktive Depth-Test die
  Text-Fragmente verwirft (2496 verdrängte Text-Pixel gemessen) — der HUD-Pass
  in `on_draw` deaktiviert den Depth-Test daher bewusst. Headless-Regression:
  Kamera-State-Tests + pyglet-2.x-Modifier-Naht in
  `tests/test_camera_picking.py`.
- **V0.2-Demonstrator-Picking-Lücke:** Die V0.2 `OrbitCamera` bietet KEIN
  `project_to_screen`/`screen_to_ray`, obwohl der V0.2-Demonstrator sie
  aufruft (im V0.2-Experiment nie live ausgeübt). Das Lab ergänzt sie
  additiv in `lab_camera.LabOrbitCamera` (V1-Mathematik) und dokumentiert
  die Lücke — V0.2 bleibt unverändert.
- **Triangulierung:** konservatives Ear-Clipping (einfache Polygone);
  degenerierte Faces fallen deterministisch auf Fan-Triangulierung zurück.
  Kein Polygon-Regularisierungs-Garant, keine UV/Normalen-Bearbeitung.
- **Picking / Selection:** CPU-Projektions-Picking (wie V1/0.2), kein
  GPU-Picking-Buffer. Multi-Selection bleibt bewusst klein (Shift-Toggle).
- **Move ohne History:** Für den minimalen End-to-End-Test wird
  `src.core.Mesh.set_vertex_position` verwendet (fläche, verdrahtbar).
  `MoveOperation`/History-Integration ist dokumentierter Folgeschritt.
- **Topology / Interaction-Lab:** nicht hineingezogen (siehe Abschnitt 5).
- **Gate 5:** wird NICHT vorausgesetzt und nicht berührt.
- **Keine Änderungen an `src/core` oder vorhandenen Experimenten** — das
  Lab ist ausschließlich additiv (Git-Diff prüfbar).

## 10. Implementierungsbericht (Kurzfassung)

Vollständiger Bericht inkl. Commit-Hash: siehe Abschlussmeldung des Tasks.
Kurz: Neu erstellt `experiments/mirai_bastel_integration_lab/` (13 Module,
7 Testdateien). Bestehende Verwendung: OBJ Loader (unverändert), V0.2
`camera`/`render_mesh`/`renderer`/`selection`/`material`/`stats` (unverändert),
`src.core` (nur über öffentliche Query-/Mutations-API). Adapter: `obj_to_core`,
`core_to_render` (+`triangulate`, `picking`), `lab_camera`. Der alte
`viewport_adapter.py` (V1-Core) wird bewusst NICHT importiert — seine Logik
ist in `obj_to_core.py` gegen `src.core` adaptiert.