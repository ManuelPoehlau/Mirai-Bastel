# Mirai-Bastel — Integration Lab / Test Studio

**Status:** Production-basiert seit WP-IL-01 (2026-09-08). Das Lab nutzt die
Production-Kamera (`src/mirai/viewport/camera.py::OrbitCamera` via
`bind_camera`) und den Production-Viewport (`src/viewport.Viewport` →
RenderMesh/ResourceStore/SelectionOverlay, Gate 5/7) — das V0.2-Experiment
wird nicht mehr importiert.
**Gültigkeit:** KEIN Production-Viewport, KEIN neuer Modeler. `src/` und die
bestehenden Experimente wurden NICHT verändert.
**Audit/Reconciliation:** [`docs/ARCHITECTURE_RECONCILIATION_AUDIT.md`](docs/ARCHITECTURE_RECONCILIATION_AUDIT.md)

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

> **Das Integration Lab benutzt Production-Code, wo er existiert — und bleibt
> selbst Harness für alles, was Production bewusst noch nicht hat
> (Fenster, GL-Kontext, echter Draw, Instrumentierung).**

## 2. Architektur (seit WP-IL-01)

```text
OBJ
 ↓
ObjMeshData                        (OBJ Loader, unverändert wiederverwendet)
 ↓
core.Scene / core.Mesh             (Domain-Wahrheit; Polygone bleiben Polygone;
                                    Production-Importpfad `core`, wie src/mirai)
 ↓
CoreRenderBinding (Adapter)        (dünne Fassade: Viewport + Notifikationen)
 ↓
src.viewport.Viewport              (RenderMesh + ResourceStore + Overlay,
                                    Gate 5/7: mark_*_dirty → sync → Store)
 ↓
Lab-Harness                        (pyglet-Fenster, GL-Kontext, eigener Draw,
                                    Kamera-Matrizen von derselben Kamera-Instanz)
```

Eine Kamera-Instanz pro Objekt-Kette (`LabOrbitCamera` = Production-`OrbitCamera`
+ dokumentiertes GL-View-Matrix-Override, Audit §A.1), gebunden über
`Viewport.bind_camera()` — exakt der Gate-7-Vertrag. Keine zweite
Mesh-Repräsentation mehr: `src.viewport.RenderMesh` liest die Core-Mesh
direkt (`_vertex_index`, Fan-Triangulierung via `viewport.derived`).

### Update-Kategorien (Production `src/viewport`, unverändert)

| Änderung | Kanal | Effekt |
|---|---|---|
| Camera | `camera` | nur `camera_uniforms` |
| Selection | `selection` | nur `highlight_flags` (Overlay) |
| Material | `material` | nur `material_uniforms` |
| Vertex-Move | `geometry` | Positions-/Normalen-Partial-Updates |
| Topology | `topology` | struktureller Rebuild (im Lab vorbereitet, nicht interaktiv) |

## 3. Verantwortlichkeiten

| Baustein | Verantwortung | Bewusst NICHT |
|---|---|---|
| OBJ Loader (`rigging-skinning-morphing/loaders/obj_loader.py`) | OBJ → ObjMeshData, headless, ohne Core/Viewport/pyglet | keine Triangulierung, kein Rendering, kein Core-Wissen |
| `src/core` (Import als `core`) | Domain-Wahrheit: Topologie, IDs, Positionen, Selection, History | kein Rendering |
| Integration Adapter (`adapters/`) | Dünne Fassade + Übersetzung an den Grenzen (obj→core, core→Production-Viewport, picking) | keine neue System-Architektur, keine Render-Kopie |
| `src/viewport` (Production, Gate 5/7) | Render-Darstellung, DirtyState-Kategorien, Resource-Store, Overlay | kein Fenster, kein Draw-Call (`Viewport.render()` ist No-Op) |
| Lab-Harness (`integration/`) | pyglet-Fenster, GL-Kontext, eigener Draw, HUD/Instrumentierung, Beobachtungs-Proben | keine Production-Architektur |

## 4. Dateien / Komponenten

```text
experiments/mirai_bastel_integration_lab/
├── README.md               # dieses Dokument
├── run.py                  # interaktiver Start (Fenster)
├── report.py               # headless Performance-/Status-Probe (TraceStore)
├── _smoke_window.py        # Kurzzeit-Smoke des Fensters (schließt nach 1,5 s)
├── _camera_motion_probe.py # Kamera-Bewegungsprobe am echten GL (auto-close)
├── _paths.py               # sys.path-Bootstrap (Lab/Root/Repo-src/Rigging)
├── lab_camera.py           # Production-OrbitCamera + GL-View-Matrix-Override
├── scene/
│   ├── scene.py            # LabScene + LabObject (unabhängige Core-Scenes)
│   └── scene_objects.py    # Cube + reales Head-Basemesh, build_lab_scene()
├── adapters/
│   ├── obj_to_core.py      # ObjMeshData → core (Loader wiederverwendet)
│   ├── triangulate.py      # Ear-Clipping-Experiment (bewusst außerhalb des
│   │                       #  Production-Fan-Pfads; Superset für konkave N-gons)
│   ├── core_to_render.py   # dünne Fassade: core.Mesh + Selection → src.viewport.Viewport
│   │                       #   + LabPygletStore (vec3-Ausrichtung) + LabMaterialState
│   └── picking.py          # Delegation an src.mirai.viewport.picking
├── integration/
│   └── lab_viewport.py     # pyglet-Fenster (mehrere Objekte, Live-Statistik)
├── docs/
│   └── ARCHITECTURE_RECONCILIATION_AUDIT.md  # Audit + WP-IL-01
└── tests/                  # headless Integration-Boundary-Tests (52 Stück)
```
## 5. Aktueller Stand (nach WP-IL-01, 2026-09-08)

**funktioniert (durch Tests + Report + echte-GL-Proben verifiziert):**

- [x] Production-Kamera als einzige Kamera: `LabOrbitCamera` IST eine
      `src.mirai.viewport.camera.OrbitCamera`, gebunden über
      `Viewport.bind_camera()` (Gate-7-Vertrag, Objekt-Identität getestet)
- [x] Production-Viewport als einzige Render-Schicht:
      `CoreRenderBinding` = dünne Fassade über `src.viewport.Viewport`
      (`on_vertices_moved`/`on_selection_changed`/`on_topology_changed`/
      `on_camera_changed` + `sync()`); keine V0.2-Importe mehr (grep-Test)
- [x] OBJ Loader unverändert wiederverwendet (`OBJ → ObjMeshData → core`)
- [x] reales Head-Basemesh + Cube als kontrolliertes Vergleichsobjekt
- [x] Kategoriebewusster Sync über den Production-Pfad: Camera → nur
      `camera_uniforms`; Selection → nur Overlay; Vertex-Move → nur
      Geometry-Partial-Updates (Regressionstests in
      `tests/test_production_rebase.py`)
- [x] Vertex-Move verändert ZUERST `core.Mesh`, Render folgt per Notifikation
- [x] Kamera Orbit + Zoom (+ Pan über Production-`pan`), Objekt-Auswahl,
      Vertex-Picking (Production-`pick_nearest_vertex`) und -Move,
      Live-FPS-/Zähler-Anzeige im Fenster
- [x] 52 headless Boundary-Tests (OBJ→Core, Core→Production-Render,
      Geometry-Update, Scene, Triangulierung, Kamera/Picking, Imports,
      Production-Re-Base-Regressionen)
- [x] **View-Matrix-Override (weiterhin load-bearing):** Die Production-View-
      Matrix (+forward in Zeile 3) clippte im Lab-Harness sämtliche Front-
      Geometrie (schwarzer Viewport). `LabOrbitCamera.build_view_matrix`
      überschreibt mit gluLookAt-Konvention; Picking/Uniforms lesen dieselbe
      Instanz. Fix in Production ist eine eigene Architekturentscheidung
      (Audit §A.1). Regressions-Tests in `tests/test_camera_picking.py`.
- [x] **Live-Verifikation am echten GL (WP-IL-01):** `run.py --selftest`
      PASS (Mesh + HUD sichtbar), `_smoke_window.py` PASS (Cube **und** Head
      sichtbar), `_camera_motion_probe.py` PASS (Kamera-Orbit/Zoom ändern das
      Framebuffer-Bild sichtbar — Continuous-Redraw bestätigt).

**experimentell / vorbereitet, aber noch nicht interaktiv verdrahtet:**

- Topology-Pfad: `CoreRenderBinding.rebuild_from_core()` (struktureller
  Rebuild über `on_topology_changed`), test-/reportseitig nutzbar.
- Undo/Redo der Move-Interaktion über `core.MoveOperation`/History (der
  Lab-Move nutzt für den minimalen End-to-End-Test bewusst das flache
  `set_vertex_position`).

**noch nicht integriert (bewusst draußen):**

- Input/Binding: Die pyglet-Handler mappen weiterhin direkt auf
  Kamera-/Selection-Aktionen. Der Anschluss an das Gate-6-System
  (`Input → BindingSet.command_for → Command → dispatch_command`) ist ein
  eigenes Folgewpaket (Audit §G, Punkt 7) — pyglet bleibt Event-Quelle.
- Selection-UX-Entscheidung (Interaction Lab) — `dispatch_command`
  behandelt `SELECT`/Nav-Commands Production-seitig bewusst noch nicht.

## 6. Erste Zielszene & Interaktion

Beim Start entsteht die Testszene `Cube + Head Basemesh`. Jedes Objekt hält
eine **eigene** `core.Scene` (eigene Mesh/Selection/History).

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
core.Mesh wird verändert
 ↓
on_vertices_moved → sync()   (Geometry-Partial-Update im Production-Store)
 ↓
Lab-Harness zeichnet die Änderung
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
## 7. Performance-Beobachtungen — Head Basemesh (neu gemessen 2026-09-08, WP-IL-01)

Head-Basemesh-Kennzahlen (reales Asset, über den OBJ Loader):

| Kennzahl | Wert |
|---|---|
| Vertices | 326 |
| Edges | 648 |
| Faces | 324 (alle Quads) |
| Render-Triangles (Production-Fan) | 648 |

Gemessene Zeiten des Headless-Reports (`python report.py`, Production-
`TraceStore`, CPU-Buchhaltung, Python 3.14, keine GPU):

| Szenario | Messung | Beobachtung |
|---|---|---|
| Initialer Aufbau (Viewport/RenderMesh.build) | ~12,9 ms | einmalig pro Objekt |
| 60 Kamera-Orbits | ~1,5 ms gesamt (~0,03 ms/Op) | `camera_updates = 62`; `mesh_rebuilds = 0`; IDs stabil |
| 20 Selection-Sets | ~1,3 ms gesamt (~0,06 ms/Op) | nur Overlay; `mesh_rebuilds = 0` |
| 40 Vertex-Moves | ~21,0 ms gesamt (~0,52 ms/Move) | `vertex_updates = 40`; nur Positions-/Normalen-Partial-Updates; `mesh_rebuilds = 0` |

Historische Messungen vom 2026-07-09 (alte V0.2-Experiment-Verkabelung,
vor WP-IL-01): Aufbau ~17,9 ms / 60 Orbits ~1,2 ms / 20 Selections ~1,4 ms /
40 Moves ~16,8 ms — gleiche Größenordnung, Production-Pfad ist im selben
Performance-Enveloppe.

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
python experiments/mirai_bastel_integration_lab/report.py              # headless Probe
python experiments/mirai_bastel_integration_lab/run.py                 # interaktives Fenster
python experiments/mirai_bastel_integration_lab/run.py --selftest      # GL-Pixel-Selbsttest
python experiments/mirai_bastel_integration_lab/_smoke_window.py       # GL-Smoke Cube+Head
python experiments/mirai_bastel_integration_lab/_camera_motion_probe.py # Kamera-Bewegung am GL

# Tests (headless, ohne GPU):
python -m pytest experiments/mirai_bastel_integration_lab/tests -q     # 52 Tests
```

Testabdeckung der Integrationsgrenzen:

| Grenze | Testdatei |
|---|---|
| OBJ → Core (Loader-Reuse, Zahlen, Positionen, Edges) | `tests/test_obj_to_core.py` |
| Core → Production-Render (Vertices, Faces, Fan-Triangulierung, Index-Map) | `tests/test_core_to_render.py` |
| Geometry-Update (Core zuerst, Notifikation, kein Rebuild) | `tests/test_geometry_update.py` |
| Scene (Cube+Head, unabhängige Auswahl, Framing) | `tests/test_scene.py` |
| Triangulierung (konvex/konkav/N-gon/Fallback, Lab-Experiment) | `tests/test_triangulate.py` |
| Kamera/Picking (Projektion, Konsistenz, Production-Basis, View-Matrix) | `tests/test_camera_picking.py` |
| Imports der interaktiven Schicht | `tests/test_imports.py` |
| HUD-Vertrag | `tests/test_hud.py` |
| **Production-Re-Base-Regressionen (WP-IL-01)** | `tests/test_production_rebase.py` |

## 9. Bekannte Grenzen & Entscheidungen (Stand WP-IL-01)

- **Production-View-Matrix-Konvention (load-bearing Lab-Override):** Die
  Production `build_view_matrix` (`src/mirai/viewport/camera.py`) schreibt
  +forward in die dritte Zeile (Front-Punkte auf positivem Camera-Z), während
  die Production-Projektion Standard-GL ist (clip.w = -view.z). Folge:
  clip.w < 0 für alles vor der Kamera → komplettes Clipping → schwarzer
  Viewport. Der Gate-5-GL-Live-Check berührte diese Kombination nie (nur
  headless Uniform-Tests, nur positions-ähnliche Ressourcen). Das Lab
  überschreibt `build_view_matrix` in `LabOrbitCamera` (gluLookAt-Konvention);
  Picking/Uniforms lesen dieselbe Instanz. **Eine Korrektur in der Production
  ist eine eigene Architekturentscheidung** (Audit §A.1; Gate-11-Kandidat).
- **`RenderMesh._sync_material` ohne Allocate-Fallback (Production-Grenze):**
  Bindet man einen Material-State NACH dem Konstruktions-Build (so wie
  `Viewport.bind_material` es vorsieht), geht `_sync_material` von einer
  existierenden Ressource aus — mit `PygletStore` würde `update()` einen
  KeyError werfen (`_sync_camera` hat diesen Guard, `_sync_material` nicht).
  Der Lab-Store allokiert defensiv vor; Production betrifft es aktuell
  nicht (kein call-site), dokumentiert für Gate 11.
- **`PygletStore` + Default-Shader = vec3-Raster:** Ressourcen, deren Float-
  Anzahl nicht durch 3 teilbar ist (camera_uniforms = 32, material_uniforms
  = 8, highlight_flags = n_verts), passen nicht in die
  `count = nbytes // 12`-Allokation; `register_attribute_spec(..., 1)` ist
  mit dem Default-Shader nicht verwendbar (pyglet erwartet für `position`
  stets `count * 3` floats — Live-Befund WP-IL-01). `LabPygletStore`
  richtet die Allokationsgröße auf Vielfache von 12 Bytes aus (ceil);
  `update()`/Buchhaltung bleiben unverändert Production. Ein echter
  Multi-Attribut-/1-Komponenten-Shader bleibt Production-Entry-Point-Scope.
- **pyglet 2.1 Windows-Fenster-Details (Lab-lokal behandelt):** ohne explizite
  `gl.Config` entsteht kein Depth-Puffer (unsichtbare Flächen); Modifier-
  Konstanten liegen in `pyglet.window.key`, nicht `mouse`; transiente
  `on_resize(height=0)` beim Start erfordert einen Aspect-Guard. Alles
  additiv im Lab gehandhabt.
- **Laufzeit-Nachweis Event-Kette & HUD (Probe 2026-07-09):** Alle Handler
  (`on_mouse_press/drag/release/scroll/key_press`) werden über pyglets
  Dispatch-Pfad aufgerufen und verändern den Kamera-State nachweislich.
  Click-Selection erreicht `_handle_click_selection` und mutiert die Core-
  Selection; `M` erreicht `_move_picked_vertex`. HUD: der HUD-Pass in
  `on_draw` deaktiviert den Depth-Test bewusst (sonst verdeckt nahes Mesh
  den Text). Headless-Regression: Kamera-State-Tests + pyglet-2.x-Modifier-
  Naht in `tests/test_camera_picking.py`; neue Live-Probe:
  `_camera_motion_probe.py` (2026-09-08: Continuous-Redraw bestätigt,
  Kamera-Änderungen erreichen das Framebuffer-Bild).
- **Triangulierung:** Production-Fan (`viewport.derived.triangulate_face`)
  ist maßgeblich im Render-Pfad; das Lab-Experiment `adapters/triangulate.py`
  (Ear-Clipping + Fan-Fallback, Superset für konkave N-gons) bleibt bewusst
  außerhalb — Productionisieren wäre eine eigene Entscheidung.
- **Picking / Selection:** Production-`pick_nearest_vertex` (CPU, Pixel-
  Distanz, Threshold 14 px), Selection ausschließlich Core-Buchhaltung.
  Multi-Selection bleibt bewusst klein (Shift-Toggle).
- **Move ohne History:** Für den minimalen End-to-End-Test wird
  `core.Mesh.set_vertex_position` verwendet (flächig, verdrahtbar über
  `on_vertices_moved`). `MoveOperation`/History-Integration ist
  dokumentierter Folgeschritt.
- **Input/Binding:** bewusst noch nicht am Gate-6-System (siehe §5) —
  eigenes Folgewpaket.
- **Gate 5/6/7 Production:** wird benutzt (Camera/Viewport/Store/Overlay/
  Picking), nicht geändert. Git-Diff prüfbar: alle WP-IL-01-Änderungen
  liegen unter `experiments/mirai_bastel_integration_lab/`.

## 10. Implementierungshistorie

**Ursprünglicher Aufbau (2026-09-07, vor WP-IL-01):** Neu erstellt
`experiments/mirai_bastel_integration_lab/` (13 Module, 7 Testdateien).
Bestehende Verwendung: OBJ Loader (unverändert), V0.2-Experiment
`camera`/`render_mesh`/`renderer`/`selection`/`material`/`stats`,
`src.core` (nur über öffentliche Query-/Mutations-API). Adapter:
`obj_to_core`, `core_to_render` (+`triangulate`, `picking`), `lab_camera`.
Der alte `viewport_adapter.py` (V1-Core) wurde bewusst NICHT importiert —
seine Logik ist in `obj_to_core.py` adaptiert.

**WP-IL-01 (2026-09-08):** Re-Base auf Production Camera + Production
Viewport (dieses Dokument, §2–§5 und §9). Details, Befunde und
Akzeptanznachweise: [`docs/ARCHITECTURE_RECONCILIATION_AUDIT.md`](docs/ARCHITECTURE_RECONCILIATION_AUDIT.md)
(§A.1 View-Matrix-Konvention, §G WP-IL-01, §I Implementierungsrecord).