# Viewport V0.2 Experiment — Incremental-Update-Architektur-Proof

**Status:** Experiment abgeschlossen — Hypothese bestätigt (PROVEN), GPU-Persistenz zusätzlich live verifiziert
**Gültigkeit:** Nur Experimentcode. Kein Production Viewport. `src/` und `experiments/mirai_bastel_viewport_V1/` wurden nicht verändert.

Übergeordnete Dokumente:

- Research-Baseline: [`../../docs/viewport/VIEWPORT_V02_RESEARCH.md`](../../docs/viewport/VIEWPORT_V02_RESEARCH.md)
- Experiment-Index: [`../README.md`](../README.md)

---

## 1. Research Question

Kann ein Viewport Camera-, Selection-, Material- und Geometry-Änderungen **gezielt** verarbeiten — ohne unnötige vollständige Mesh-/GPU-Rebuilds — während Topology Changes ausdrücklich strukturelle Aktualisierung erlauben?

Das ist die praktische Gegenprobe zur V1-Diagnose („jedes Event rebuildet die komplette Render-Geometrie“, siehe Research-Dokument, Abschnitte 4–8).

## 2. Hypothesis

Update-Kategorien (`camera`, `geometry`, `selection`, `material`, `topology`) können über Dirty-State getrennt werden, sodass:

| Kategorie | EXPECTED |
|---|---|
| Camera | nur Render-State/Uniforms; kein Mesh-Rebuild, kein Geometry-Upload, keine GPU-Resource-Recreation |
| Selection | nur Overlay-Ressource; kein Base-Geometry-Rebuild |
| Material | nur Material-Ressource; keine Geometry-Invalidierung |
| Geometry (Vertex-Move) | Partial-Update der betroffenen Ressourcen + Derived-Data-Update (Normale, Bounds); Topology bleibt unverändert |
| Topology | struktureller Rebuild erlaubt und sichtbar (neue Ressourcen-IDs) |

Zusätzlich: GPU-Ressourcen-Identität muss nachvollziehbar sein — Ressourcen-Ersetzung muss als solche sichtbar werden, nicht als „gleicher Counter, neuer Buffer“.

## 3. Architecture

Implementiert als kleine, eigenständige Komponenten unter `experiments/mirai_bastel_viewport_V02/`:

```text
category.py    DirtyState: je Kategorie Flag + Revisionszähler, modified_vertices-Set
mesh.py        Mesh (Positionen, Quad-Faces), move_vertex, Adjacency, Grid-Generator
derived.py     DerivedData: Face-/Vertex-Normalen, Bounds, affected_neighborhood
camera.py      OrbitCamera: orbit/pan/zoom, View-/Projektionsmatrizen
selection.py   SelectionState: Vertex-Set -> Highlight-Flags
material.py    MaterialState: Base-Color -> Uniform-Paket
renderer.py    ResourceStore-Vertrag + zwei Backends:
                 TraceStore  — deterministisch, In-Prozess, monotone Ressourcen-IDs (Tests)
                 PygletStore — gleicher Vertrag für den Live-Demonstrator
render_mesh.py RenderMesh: besitzt Mesh + DerivedData + Stats + DirtyState + Store;
               sync() verarbeitet Dirty-Kategorien in fester Reihenfolge
run_tests.py   Test-Suite (10 Tests + optionaler Live-GPU-Check)
demonstrator.py Interaktives pyglet-Fenster mit Live-Instrumentierung
```

Der zentrale Update-Flow (`render_mesh.py::sync`):

```text
sync()
  ├─ dirty.topology  -> _sync_topology:  full_recompute + Ressourcen-Neuaufbau (neue IDs)
  ├─ dirty.geometry  -> _sync_geometry:  affected_neighborhood -> lokale Normalen,
  │                      bounds recalc, Positions-/Normalen-Partial-Uploads
  ├─ dirty.selection -> _sync_selection: nur highlight_flags-Ressource
  ├─ dirty.material  -> _sync_material:  nur material_uniforms-Ressource
  └─ dirty.camera    -> _sync_camera:    nur camera_uniforms-Ressource
```

Ressourcen-Vertrag (`ResourceStore`): `allocate(name, nbytes)` erzeugt eine Ressource mit stabiler Identität; `update(name, offset, data, nbytes)` schreibt **in dieselbe Ressource** (Partial-Update). Die Backends zählen `gpu_resource_creations`, `gpu_resource_destroys` und `uploaded_bytes` explizit.

## 4. Update Categories

| Kategorie | darf verändern | darf NICHT verändern |
|---|---|---|
| camera | `camera_uniforms` | Mesh, positions/normals/indices, highlight_flags, material_uniforms |
| selection | `highlight_flags` | alle Base-Mesh-Ressourcen, Derived Data |
| material | `material_uniforms` | alle Geometry-/Topology-Ressourcen |
| geometry | `positions` (partial), `normals` (partial), Face-/Vertex-Normalen, Bounds | Topologie, Adjacency, Indizes, Ressourcen-Identität |
| topology | alles strukturelle: neue Ressourcen für positions/normals/indices/highlight_flags, Adjacency-Rebuild | — (hier ist Rebuild erlaubt und gefordert) |

## 5. Instrumentation

Gezählt werden (Task-Liste vollständig abgedeckt):

`camera_updates`, `selection_updates`, `material_updates`, `vertex_updates`, `topology_updates`, `structural_rebuilds`, `mesh_rebuilds`, `geometry_uploads`, `partial_updates`, `bounds_recalculations`, `gpu_resource_creations`, `gpu_resource_destroys` — plus `uploaded_bytes` pro Ressource und einfaches CPU-Timing (`stats.start/stop`, diagnostisch).

False-Positive-Schutz gegen „Counter nur passend interpretieren“:

1. **Ressourcen-IDs sind global monoton** (Zähler im Prozess, nie zurückgesetzt, nie wiederverwendet). Jede Recreation erzeugt eine sichtbar neue Nummer; ein „versteckter“ Rebuild würde als ID-Sprung auffallen.
2. **Whitebox-Audit** (siehe unten) legt vorab fest, welche Kategorie welche Ressource verändern darf.
3. Tests prüfen **Inhalte**, nicht nur Counter: Puffer-Bytes, Normalen-Werte, Bounds-Grenzen, Flag-Zustände.
4. Der optionale `--gpu`-Test verifiziert die Persistenz-Annahme **live gegen pyglet**: `VertexList`-Objektidentität bleibt über `set_attribute_data` (in-place `set_region`/`glBufferSubData`) erhalten.

### Whitebox-Audit (ist so implementiert)

```text
GPU-Ressourcen (6, initial):
  positions, normals, indices      — Base-Geometry (Triangulation der Quads)
  highlight_flags                  — Selection-Overlay (f' pro Vertex)
  material_uniforms                — Material-Paket
  camera_uniforms                  — View+Projektions-Matrizen

Kategorie -> Ressourcenzugriff:
  Camera    -> camera_uniforms only
  Selection -> highlight_flags only
  Material  -> material_uniforms only
  Geometry  -> positions (partial, nur verschobene Vertices)
            -> normals   (partial, nur betroffene Nachbarschaft)
            -> Derived Data (Face-/Vertex-Normalen, Bounds) — CPU-seitig
  Topology  -> kompletter Neuaufbau aller strukturgebenden Ressourcen (neue IDs)
```

Hinweis zur Begrifflichkeit: `TraceStore`/`PygletStore` modellieren die Ressourcen-Identität (ID, Creation, Destroy, Bytes) deterministisch in Python; der Demonstrator schreibt echte Positions-/Normalen-Daten über pyglets `VertexList.set_attribute_data` in die bestehenden VBOs. Das Experiment erhebt keinen Anspruch auf ein allgemeines GPU-Resource-Management (bewusster Non-Goal, siehe Research-Dokument Abschnitt 25).

## 6. Tests

Ausführung (beide Modi verifiziert funktionieren):

```bash
cd experiments/mirai_bastel_viewport_V02
python run_tests.py --verbose          # Kern-Suite, headless, ohne GPU
python run_tests.py --gpu --verbose    # + Live-GPU-Persist-Check (pyglet-Fenster 32x32, unsichtbar)
python demonstrator.py                 # interaktiver Demonstrator
```

Die Kern-Suite läuft headless (kein Fenster nötig); nur `--gpu` und der Demonstrator benötigen pyglet/OpenGL.

| # | Test | Prüfkern |
|---|---|---|
| 1 | Initial Build | 6 Ressourcen angelegt (IDs 1–6) |
| 2 | Camera | Orbit/Pan/Zoom × mehrere Schritte: `mesh_rebuilds == structural_rebuilds == geometry_uploads == 0`, IDs stabil |
| 3 | Selection | Flags korrekt gesetzt, `mesh_rebuilds == structural_rebuilds == 0` |
| 4 | Material | Nur `material_uniforms` verändert; Positions-Ressource unangetastet |
| 5 | Vertex Position | `vertex_updates > 0`, `topology_updates == 0`, `structural_rebuilds == 0`, `partial_updates > 0`, `geometry_uploads > 0`, `bounds_recalculations > 0`, Positions-Bytes korrekt, Normalen aktualisiert |
| 6 | Topology | `topology_updates > 0`, `structural_rebuilds > 0`, `mesh_rebuilds > 0`, neue Ressourcen-IDs |
| 7 | Resource Persistence | Camera+Selection+Material+Geometry gemischt: 0 Creations, 0 Destroys, IDs identisch, Upload-Bytes nachweisbar gewachsen |
| 8 | Stress | 33×33-Grid (1089 Vertices), 780 Moves in 5 Syncs: keine Leaks, keine Hidden Rebuilds, IDs stabil, Pufferlänge intakt |
| 9 | Interleaving | Alle vier Kategorien im selben `sync()`: alle Counter > 0, kein Structural Rebuild, Inhalte (Flags/Uniforms/Position) korrekt |
| 10 | Bounds / Visual Correctness | Bounds decken verschobene Vertices exakt ab; Vertex-Normale am verschobenen Vertex nicht mehr planar |
| GPU | Live-Persist-Check | pyglet `VertexList`-Identität stabil über Partial-Update; Position-/Color-Buffer vorhanden |

Demonstrator-Steuerung: LMB ziehen = Orbit · Shift+LMB/MMB = Pan · Mausrad = Zoom · LMB-Klick = Vertex picken (CPU) · M = Vertex anheben · K = Materialfarbe · T = Topology vergrößern · R = Reset · Esc/Q = Ende. Live im Fenster: alle Zähler + aktuelle Ressourcen-IDs.

## 7. Expected Results

Siehe Hypothesis-Tabelle in Abschnitt 2. Konkret pro Test: 2/3/4 ohne jegliche Rebuild-/Upload-Zähler; 5 mit Partial-Updates + Bounds + Normalen ohne Topology; 6 mit sichtbarem ID-Wechsel; 7/8 ohne Creations/Destroys; 9 ohne Counter-Korruption und ohne Structural Rebuild.

## 8. Actual Results (OBSERVED)

`python run_tests.py --verbose` (und identisch im `-m`-Paketmodus): **10/10 PASS**, `--gpu`-Check ebenfalls PASS (pyglet 2.1.16, Python 3.14, Windows). Beobachtete Werte:

| # | OBSERVED |
|---|---|
| 1 | Ressourcen: `positions=1, normals=2, indices=3, highlight_flags=4, material_uniforms=5, camera_uniforms=6` |
| 2 | 9 Camera-Updates, IDs stabil (6), 0 Uploads |
| 3 | Flags `{0,6,12}` korrekt; IDs stabil |
| 4 | Nur `material_uniforms` geändert |
| 5 | `vertex_updates=1, partial_updates=8` (1 Positions-Patch + 7 Normalen-Patches der Nachbarschaft), `geometry_uploads=8`, `bounds_recalc=1` |
| 6 | Neue IDs `37–42` (monotone Zähler — beweist Neuanlage statt Wiederverwendung); `structural_rebuilds=1, mesh_rebuilds=1` |
| 7 | 0 Creations, 0 Destroys, IDs identisch, `uploaded delta=844 B` |
| 8 | `vertices=1089, updates=780, partials=4625`, IDs stabil, Pufferlänge korrekt |
| 9 | Interleave-Deltas: alle vier Kategorie-Counter > 0, `structural_rebuilds=0`, `mesh_rebuilds=0`, `partial_updates=11` (1 Position + 7 Normalen + 1 Selection + 1 Material + 1 Camera), Inhalte verifiziert |
| 10 | Bounds `(-1,0,0)..(4,4,3)` decken beide Moves ab; Normalen korrekt nicht-planar |
| GPU | `VertexList`-Objekt identisch vor/nach `set_attribute_data`; `position`- und `color`-Buffer vorhanden |

Interaktiver Demonstrator (Live-GPU): Canvas zeichnet, IDs bleiben über Camera/Selection/Material/Vertex-Interaktion stabil; `mesh_rebuilds=1`/`structural_rebuilds=1` stammen ausschließlich aus dem initialen Aufbau; ein Interleave-Frame erzeugte `partial_updates=11`.

**Abweichungen von EXPECTED:** keine. Kein Test musste interpretiert werden; keine Hypothese musste abgeschwächt werden.

## 9. Known Limitations

- **Simulation vs. echter GPU-Treiber:** Die Creation-/Destroy-/ID-Buchhaltung läuft in Python (`TraceStore`/`PygletStore`). Echte Treiber-Buffer-Identität wurde nur für den pyglet-Pfad (`set_attribute_data` → in-place VBO-Update) live verifiziert, nicht für jeden Einzelfall instrumentiert.
- **Selection-Overlay:** Punktbasiertes GL_POINTS-Highlight (Flags + separates Overlay-VList). Kein Production-Selection-System (bewusst).
- **Normaldefinition:** einfache flächengewichtete Mittel-Normale mit `vertex_to_faces`-Nachbarschaft. Andere Normaldefinitionen können die minimale betroffene Nachbarschaft verändern (Research-Dokument Abschnitt 16).
- **Meshgrößen:** bis 33×33 getestet; Skalierungsverhalten auf Head-Basemesh/ größere Netze ist Gegenstand eines Folgeschritts (Benchmark gegen V1, Research-Dokument Abschnitt 27).
- **Timing:** diagnostisch (`stats.start/stop`), keine Performance-Acceptance-Criteria — bewusst, gemäß Task-Vorgabe.
- **Einzel-Thread/Single-Window:** keine Aussagen über Multithreading oder mehrere Viewports.

## 10. Verdict

**PROVEN** (mit einer Grenze: GPU-Persistenz ist live nur für den pyglet-Partial-Update-Pfad verifiziert).

Die gestellte Hypothese hat sich reproduzierbar bestätigt: Camera-, Selection-, Material- und Geometry-Updates laufen ohne Mesh-/Structural-Rebuilds und ohne GPU-Resource-Recreation ab; Topology-Änderungen erzeugen sichtbar neue Ressourcen-Identitäten; Interleaving wird korrekt verarbeitet; unter Stress treten keine Leaks oder Hidden Full Rebuilds auf.

**Empfehlung für den nächsten Schritt:**

1. Diese Ergebnisse als Eingabe für die ausstehende `VIEWPORT_V02_ARCHITECTURE.md` verwenden (Research-Dokument, Abschnitt 28) — insbesondere: Ressourcen-Vertrag mit monotonen IDs und „update statt recreate“ als harte Invariante übernehmen.
2. Anschließend Gate 5 — Viewport Production: Übertragung der validierten Muster (DirtyState-Kategorien, `affected_neighborhood`, Partial-Uploads) in `src/` — nicht durch Kopieren des Experimentcodes.
3. Benchmark-Abgleich gegen V1 unter identischen Szenarien/Hardware (Research-Dokument Abschnitt 22/27), bevor Performance-Ziele verbindlich werden.
