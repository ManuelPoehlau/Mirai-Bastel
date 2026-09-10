# Integration Lab — Architecture Reconciliation Audit

**Typ:** Audit / Architecture Reconciliation (Review-Artefakt, kein Implementierungsreport)
**Datum:** 2026-09-08
**Branch:** `Integration-Lab-Expriment` · **Head:** `9700c22` (Gate 7)
**Modus:** Reiner Audit — für diesen Bericht wurden keine Code-Dateien geändert und kein Fix vorgenommen.
**Zweck:** Feststellen, welche Teile des Integration Labs nach Gate 5/6/7 weiterhin gültig sind, welche veraltet sind und welche auf den heutigen Production-Code umgestellt werden müssen. Daraus abgeleitet: das kleinste Re-Base-Arbeitspaket (WP-IL-01, siehe §G).

Verwandte Dokumente:

- Lab-README: [`../README.md`](../README.md)
- Gate 5 — Viewport Production V0.2: [`../../../docs/WP-04_GATE_5_COMPLETION.md`](../../../docs/WP-04_GATE_5_COMPLETION.md)
- Gate 6 — Input Config: [`../../../docs/WP-04_GATE_6_COMPLETION_REPORT.md`](../../../docs/WP-04_GATE_6_COMPLETION_REPORT.md)
- Gate 7 — Production Camera Verification: [`../../../docs/WP-04_GATE_7_COMPLETION_REPORT.md`](../../../docs/WP-04_GATE_7_COMPLETION_REPORT.md)
- Viewport-V0.2-Spec: [`../../../docs/viewport/VIEWPORT_V02_ARCHITECTURE.md`](../../../docs/viewport/VIEWPORT_V02_ARCHITECTURE.md)

---

## 0. Methode und Realitäts-Check

- Production-Code wurde gegen den aktuellen Git-Stand gelesen, nicht gegen Gate-Dokumente als alleinige Quelle (AGENTS.md §9).
- Test-Realitäts-Check (ausgeführt, headless):

| Suite | Ergebnis |
|---|---|
| `python -m pytest tests --ignore=tests/test_extrude_tool.py -q` | **383 passed** (deckt den Gate-7-Report) |
| `python -m pytest experiments/mirai_bastel_integration_lab/tests -q` | **42 passed** (README nennt 33 — Doc-Drift, siehe §H) |

- Commit-Chronologie (verifiziert): alle Lab-Commits (`8c53025` … `f0c2f34`, 2026-09-07) liegen **vor** `68b4a1a` (Gate 5), `c0c8770` (Gate 6) und `9700c22` (Gate 7).
- **Kernbefund:** Das Lab importiert **kein einziges Symbol** aus `src.mirai` oder `src.viewport` (Import-Graph geprüft). Es basiert auf dem V0.2-Experiment (`experiments/mirai_bastel_viewport_V02/`), nicht auf der Production. Die Production-Architektur (`Application.camera → Viewport.bind_camera → RenderMesh → camera_uniforms` sowie `Input → BindingSet → Command → dispatch_command`) existiert — das Lab sieht sie schlicht nicht.

---

## A. Current Production Architecture (authoritativ)

Alle Pfade relativ zum Repo-Root. Verifiziert gegen den Code-Stand `9700c22`.

| Bereich | Authoritative Quelle | Fakten |
|---|---|---|
| Core | `src/core/` | `Mesh`, `Scene`, `Selection`, `HistoryStack`, `Operation`, `MoveOperation`, `RotateOperation`, `ScaleOperation`, Serialisierung. Eingefrorene Baseline. |
| Application | `src/mirai/application.py` | Window-frei. Hält `scene/selection/history/camera/display/tool_manager/bindings`. `init_scene()` erstellt den V0.2-Viewport (`Viewport(self.scene.mesh, selection=self.scene.selection)`) und bindet `self.camera` via `bind_camera()` (Gate 7). `dispatch_command()` behandelt nur Tool-Commands + `UNDO`/`REDO`; `SELECT`, `CLEAR_SELECTION`, `SET_*_MODE`, `ORBIT`, `PAN`, `ZOOM` sind definiert, aber **unhandled** (bewusst offen — Interaction-Lab-UX-Entscheidung ausstehend; Gate 5b wurde ersatzlos gestrichen). `update_viewport()` → `viewport.sync()`. |
| Camera | `src/mirai/viewport/camera.py::OrbitCamera` | Die einzige Production-Kamera. State: `target/distance/yaw/pitch/fov/near/far/camera_revision`. API: `orbit/dolly/pan(dx,dy,w,h)/eye/basis/screen_to_ray/project_to_screen/screen_delta_to_world/build_view_matrix/build_projection_matrix(aspect)`. |
| Viewport | `src/viewport/viewport.py::Viewport` | Dünne Fassade: `on_vertices_moved/on_topology_changed/on_selection_changed/on_material_changed/on_camera_changed/sync/render()`. `render()` ist **No-Op** (Draw-Call = zukünftiges Entry-Point-Gate). |
| RenderMesh | `src/viewport/render_mesh.py` | Liest `core.Mesh` direkt (kein separates Render-Mesh), hält `_vertex_index` (VertexId→Flat-Index) und trianguliert selbst. Mutiert Core **nie**; wird per `mark_*_dirty()` informiert. `bind_camera(camera)` duck-typed. `_sync_camera()` schreibt ausschließlich `camera_uniforms`. |
| ResourceStore | `src/viewport/resource_store.py` | `ResourceStore` (ABC) mit `TraceStore` (headless) und `PygletStore` (echtes GL, pyglet ≥ 2.0, in-place Vlist-Patching, GL-live in Gate 5 verifiziert). Stabile `resource_id`s. |
| Selection / Overlay | `src/core/selection.py` + `src/viewport/overlay.py::SelectionOverlay` | Selection ist Core-Zustand; das Overlay leitet `highlight_flags` ab. |
| Picking | `src/mirai/viewport/picking.py` | `pick_nearest_vertex(camera, mesh, sx, sy, w, h, max_pixel_distance=14.0)`, `pick_nearest_edge`, `pick_face` — pyglet-frei, Core-Query-API. |
| Input / Binding | `src/mirai/interaction/input.py`, `bindings.py` | Gate 6: `Input`, `BindingSet` (`command_for`, Unbind via `None`, Context > global, User > Default), `keymap.json` mit `schemaVersion`-Validierung, `KeymapConfigError`, `Application(keymap_path=...)`. |
| Commands / Routing / Tools | `src/mirai/interaction/commands.py`, `routing.py`, `tool_manager.py`, `tools/` | Benannte Command-Strings; `tool_for_command()` → Move/Rotate/Scale-Tools. |
| Mesh → Render | `src/viewport/derived.py` | `triangulate_face()` = **nur Fan-Triangulierung** (dokumentierte Vereinfachung; konkave N-gons sind Non-Goal), `DerivedGeometry` (Normals, Bounds). |
| Window / Entry-Point | — | **Existiert nicht.** Expliziter Non-Goal aller Gates bis Gate 7. |

### A.1 Kritischer dokumentierter Befund: View-Matrix-Konvention (nur dokumentiert, NICHT behoben)

`src/mirai/viewport/camera.py::build_view_matrix` (L.101–113) benutzt exakt die V0.2-Konvention (Zeile 3 = `+forward`, `tz = -dot(eye, forward)`). Die Production-Projektion ist Standard-GL (`m23 = -1` → `clip.w = -view.z`). Kombiniert bedeutet das: Geometrie **vor** der Kamera erhält `view.z > 0` → `clip.w < 0` → **vollständig geclippt** (schwarzer Viewport). Genau diesen Fehler hat das Lab in der V0.2-Kamera empirisch gefunden und in `LabOrbitCamera.build_view_matrix` (gluLookAt-Konvention) korrigiert.

Einordnung:

- Gate-7-Tests prüfen nur numerische Uniform-Inhalte (headless); es existiert **kein GL-Live-Draw durch den Production-Pfad** — der Mismatch ist in Production daher latent, nicht beobachtet.
- Das Lab ist derzeit der einzige Ort, der die Production-Kamera-Mathematik an echter GL verifizieren könnte.
- Keine Fix-Entscheidung in diesem Audit (eine Änderung an der Production-Kamera ist eine eigene Architekturentscheidung). Konsequenz für die Reconciliation: der Lab-View-Matrix-Override ist **load-bearing** — ein naiver Kamera-Tausch ohne Override reproduziert exakt das historische „Mesh unsichtbar/schwarzer Viewport“-Symptom.

---

## B. Integration Lab Inventory

Lab-Pfade relativ zu `experiments/mirai_bastel_integration_lab/`. Stand: 13 Module, 8 Testdateien, 42 Tests.

| Lab-Komponente | Verwendete Implementierung | Production-Gegenstück | Status |
|---|---|---|---|
| `run.py` → `integration/lab_viewport.py::main` | pyglet-Fenster, eigener Shader, eigene `vertex_list_indexed`, HUD, Selftest/Pixel-Messung | — (kein Production-Entry-Point) | bewusst experimentell, behalten |
| `lab_camera.py::LabOrbitCamera` | Basis: V0.2-Experiment-Kamera (`experiments/mirai_bastel_viewport_V02/camera.py`); Ergänzungen (`project_to_screen`, `screen_to_ray`, `screen_delta_to_world`, `pan_px`) aus V1 adaptiert; GL-View-Matrix-Override (gluLookAt) | `src/mirai/viewport/camera.py::OrbitCamera` — hat alle Ergänzungen bereits (identische Mathematik; `pan` ≡ `pan_px`) | veraltet (Basis) + load-bearing Override |
| `adapters/core_to_render.py::CoreRenderBinding` | Baut `V02Mesh` ab; hält V0.2-`RenderMesh` + `SelectionState` + `MaterialState`, Index-Map, `apply_camera/sync` | `src.viewport.Viewport` (Fassade) + `src.viewport.RenderMesh` (Mark-basiert statt Move-basiert) | veraltet / Duplikat |
| `adapters/core_to_render.py::build_render_mesh` + `CoreVertexIndexMap` | Eigenes VertexId↔Render-Index-Mapping; Triangulierung beim Ableiten | `RenderMesh._rebuild_index_mapping()` macht das identisch intern | veraltet (Duplikat) |
| `adapters/picking.py::pick_vertex` | V1-adaptierte Pixel-Distanz-Suche, Threshold 14 px | `src.mirai.viewport.picking.pick_nearest_vertex` — funktional identisch (gleiche Mathematik, gleicher Threshold) | Duplikat von Production-Code |
| `adapters/obj_to_core.py` | Wiederverwendet den Rigging-OBJ-Loader unverändert; überführt nach `src.core.Scene` | — (kein Production-OBJ-Import) | identisch / weiterhin gültig (`frame_camera_on_bounds`, `mesh_bounds` bleiben Harness-Helfer) |
| `adapters/triangulate.py` | Ear-Clipping + deterministischer Fan-Fallback | Production: nur Fan (dokumentierte Vereinfachung) | experimentell, weiterhin sinnvoll (echter Superset — relevant für konkave N-gons) |
| `scene/scene.py`, `scene/scene_objects.py` | `LabScene`/`LabObject`: je Objekt eine eigene `src.core.Scene` (Mesh/Selection/History); Cube + Head-Basemesh | Production `Application` = Einfach-Szene | bewusst experimentell, behalten (Multi-Objekt-Teststudio) |
| Input-Handling in `integration/lab_viewport.py` | Rohe pyglet-Handler (`on_mouse_drag` etc.) → direkte `camera.orbit()/pan_px()/dolly()`-Calls; Klick → `pick_vertex` → Selection-Mutation | Gate 6: `Input → BindingSet.command_for → Command → Application.dispatch_command` | inkompatibel (umgeht Binding-/Command-Ebene komplett) |
| Selection-Buchhaltung im Fenster | Doppelt: `src.core.Selection` + V0.2-`SelectionState` manuell synchronisiert | Production: Core-Selection ist die eine Quelle; Overlay abgeleitet | veraltet |
| GPU-Pfad im Fenster | Dreifach: (1) V0.2-`PygletStore` legt Vlists an — werden nie gezeichnet; (2) fenster-eigene `vlist_indexed` wird gezeichnet; (3) Partial-Updates manuell via `vlist.domain.attrib_name_buffers` | Production-`PygletStore` (in-place Patching, GL-live verifiziert) — aber ohne Draw-Call | inkompatibel / veraltet (Buchhaltungs-Doppelstate) |
| Dualer Kamera-Update-Pfad (Befund Claude, hier verifiziert) | (a) `_push_camera()` → `apply_camera` → `camera_uniforms`-Ressource im Store — wird nie gelesen; (b) `on_draw()` setzt `u_view`/`u_proj` direkt von der Kamera (`lab_viewport.py` L.351–352) | Production: ein kanonischer Pfad `camera → on_camera_changed → mark_camera_dirty → sync → camera_uniforms`; Draw-Feed ist offener Entry-Point-Punkt | veraltet als Muster; Befund bleibt dokumentiert, wird NICHT als Root Cause behandelt |
| Move | `core.set_vertex_position` direkt (ohne History) | `MoveOperation`/`HistoryStack` vorhanden | bewusst experimentell (dokumentierter Folgeschritt) |
| `report.py`, `_smoke_window.py`, `integration/lab_viewport_probe.py`, `_run_debug.log` | Headless-Performance-Probe / Pixel-Smoke / temporärer Event-Probe / Debug-Log | — | Probe + Smoke: behalten; Event-Probe: temporäres Diagnose-Artefakt (in sich als „no longer needed“ dokumentiert); Log: Repo-Hygiene (§H) |
| `tests/` (8 Dateien, 42 Tests) | Grenz-Tests gegen `src.core` + V0.2-Experiment | — | weiterhin gültig, nach Re-Base anzupassen |

Anmerkung zum Dual-Path-Befund: Beide Pfade wurden im Code verifiziert (`u_view`/`u_proj` werden ausschließlich direkt aus der Kamera gesetzt; die `camera_uniforms`-Ressource wird nur gezählt, nie gelesen). Der Befund bleibt eine dokumentierte Beobachtung; ob er nach der Re-Basis noch relevant ist, wird erst dann bewertet (siehe §G, Punkt 6).

---

## C. Reconciliation Matrix

| Bereich | Lab aktuell | Production aktuell | Bewertung | Aktion |
|---|---|---|---|---|
| Application-Orchestrierung | `IntegrationLabWindow` agiert als Orchestrator; `LabScene` = Multi-Objekt-Container | `src.mirai.Application` (window-frei, Einzelszene) | bewusst experimentell, teilweise parallel | Einzelobjekt-Kette künftig über `Application`/`Viewport`-Muster führen; `LabScene` als Harness behalten |
| Camera-State & -Mathematik | `LabOrbitCamera` auf V0.2-Experiment-Basis | `src/mirai/viewport/camera.py::OrbitCamera` | Duplikat — State/API/Mathematik identisch; Production hat alle Picking-Ergänzungen | Auf Production-Kamera umbasen; GL-View-Matrix-Override beibehalten (dokumentierte Grenze, §A.1) |
| Camera-Lifecycle | Dual-Pfad: Store-Uniforms (ungelesen) + direkter Shader-Feed in `on_draw` | Ein kanonischer Pfad bis `camera_uniforms`; Draw-Feed offen (Entry-Point) | veraltetes Muster; nur dokumentiert, nicht als Root Cause | Nach Re-Base: ein Quellpfad; Draw-Feed-Entscheidung im Lab dokumentieren |
| Viewport / RenderMesh | V0.2-Experiment-`RenderMesh` (Move-basiert, mutiert Render-Mesh) | `src/viewport` (Mark-basiert, liest `core.Mesh` direkt) | Duplikat / veraltet | Ersetzen durch `src.viewport.Viewport` |
| ResourceStore | V0.2-Experiment `TraceStore`/`PygletStore` | `src/viewport/resource_store.py` (gehärteter Port desselben Designs) | Duplikat | Production-Store verwenden |
| Core→Render-Grenze | Eigener Adapter + Index-Map + Triangulierung beim Ableiten | In `RenderMesh` integriert (`_vertex_index`, `triangulate_face`) | veraltet | Adapter auf dünne Notifikations-Fassade schrumpfen |
| Triangulierung | Ear-Clipping + Fan-Fallback | Nur Fan (dokumentiert) | experimentell, sinnvoll | Als Experiment behalten; Differenz dokumentieren (nicht productionisieren) |
| OBJ → Core | Loader-Reuse → `src.core` | kein Production-OBJ-Import | weiterhin gültig | Behalten (nicht productionisieren) |
| Picking | `adapters/picking.pick_vertex` | `pick_nearest_vertex` (identische Semantik) | Duplikat von Production-Code | Production-Picker verwenden |
| Selection | Doppel-Buchhaltung Core + V0.2-State | Core-`Selection` + `SelectionOverlay` | veraltet | Einzelbuchhaltung über Core-Selection |
| Material | V0.2 `MaterialState` | nur duck-typed `uniform_packet()` (keine konkrete Klasse) | bewusst experimentell | Behalten (füllt eine Production-Lücke, duck-type-kompatibel) |
| Input | Rohe pyglet-Handler | Gate 6 `Input → BindingSet → Command` | inkompatibel | Eigenes Folgewpaket: pyglet-Events → `BindingSet.command_for` → Commands (pyglet bleibt Event-Quelle) |
| Commands | implizite Aktionen | `commands.py` inkl. `ORBIT/PAN/ZOOM/SELECT/…`; `dispatch_command` behandelt sie nicht | Grenze dokumentiert | Lab nutzt Command-Konstanten; unhandled Commands bleiben Harness-lokal (keine Production-Änderung) |
| Move/History | flaches `set_vertex_position` | `MoveOperation` + History | bewusst experimentell | Später; nicht in WP-IL-01 |
| Pyglet-Fenster / GL / Draw / HUD / Instrumentierung | eigener Harness (Depth-Config, Handler-Registrierung, HUD-Depth-Fix, Pixel-Selftest) | existiert nicht (bewusst) | bewusst experimentell | Behalten — Kern des Experiments |
| Lab-Tests / README | 42 Tests grün; README teils V0.2-bezogen bzw. veraltet | — | Doc-Drift | In WP-IL-01 mitpflegen |

---

## D. Veraltete / doppelte Komponenten (Ersatzkandidaten)

1. **`lab_camera.py` Basis** — V0.2-Experiment-Kamera. Die Production-Kamera ist ein vollständiger Superset (`pan` entspricht `pan_px`; alle Picking-Helfer vorhanden). Nach dem Re-Base bleibt nur der dokumentierte GL-View-Matrix-Override (§A.1).
2. **`adapters/core_to_render.py` Kern** — `build_render_mesh`, `CoreVertexIndexMap`, V0.2-`RenderMesh`-/`SelectionState`-Bindung: seit Gate 5 Production-intern. `CoreRenderBinding` schrumpft zu: `Viewport(mesh, selection=…)` + `bind_camera` + Notifikations-Calls + `sync()`.
3. **`adapters/picking.py`** — Duplikat von `src.mirai.viewport.picking.pick_nearest_vertex`.
4. **V0.2-Import-Block** (`renderer.PygletStore`/`TraceStore`, `material.MaterialState`, `selection.SelectionState`, `mesh.Mesh`, `render_mesh.RenderMesh`) — ersetzen durch `src.viewport`-Entsprechungen; `MaterialState` bleibt als Harness-Klasse.
5. **Doppelte Selection-Buchhaltung** und **dreifacher GPU-State** im Fenster (nie gezeichnete `PygletStore`-Vlists vs. eigene Draw-Vlists).
6. **Dualer Kamera-Pfad** — nach dem Re-Base auf einen kanonischen Pfad konsolidieren; ob der Draw-Feed künftig aus Production-`camera_uniforms` liest, ist eine Lab-Entscheidung, die dann (und nur dann) das Terrain des historischen Symptoms neu bewertet.

---

## E. Bewusst experimentelle Komponenten (bleiben)

- **Pyglet-Fenster, GL-Kontext, echte Draw-Calls, eigener Shader** — Kern des Experiments; Production hat bewusst keinen Entry-Point.
- **Harness-Fixes** (Depth-Buffer-`gl.Config`, `push_handlers`/`_allow_dispatch_event`, HUD ohne Depth-Test, Aspect-Guard bei `on_resize(0)`) — dokumentierte pyglet-2.1/Windows-Erkenntnisse.
- **Instrumentierung** — HUD-Counter, Pixel-Selftest (`run.py --selftest`), `_smoke_window.py`.
- **OBJ-Testdaten + Loader-Reuse**, `LabScene`-Multi-Objekt-Prinzip, `frame_camera_on_bounds`.
- **Ear-Clipping-Triangulierung** als bewusstes Superset-Experiment (nicht productionisieren).
- `report.py` (nach Re-Base gegen den Production-Store).

---

## F. Zielarchitektur des Labs

```text
                     PRODUCTION CODE
                           │
      ┌────────────────────┼─────────────────────────┐
      │                    │                         │
 src.mirai.Application  src.mirai.viewport       src.viewport
 (Orchestrator-Muster,   OrbitCamera (1 Instanz)  Viewport / RenderMesh
  update_viewport→sync)  + picking                ResourceStore / Overlay
      │                    │                         │
      └──── duck-typed bind_camera ──────────────────┘
                           │
                 INTEGRATION LAB (Harness, bleibt)
                           │
        ┌──────────────────┼───────────────────────┐
        │                  │                       │
   Pyglet Window      Test Assets            dünne Lab-Glue
   GL Context         OBJ→src.core           LabScene (n Objekte,
   tatsächlicher      (Loader-Reuse)         je 1 Production-Viewport)
   Draw (eigene       Cube + Head            Input-Adapter:
   Vlists, bis der    ear-clip (Exp.)        pyglet-Event → BindingSet.
   Production-Entry                          command_for → Command
   Point existiert)                          → dispatch_command (bzw.
   HUD / Instrumentierung                    dokumentiert harness-lokal
   Selftest / Pixel-Check                    für noch unhandled Commands)
```

Prinzipien:

- **Eine Kamera-Instanz** pro Kette, via Production-`bind_camera` (Duck-Typ, wie Gate 7).
- **Ein kanonischer Update-Pfad** (Notifikation → `mark_*_dirty` → `sync()` → Store); der Draw-Feed liest aus dieser Quelle statt parallel vom Kamera-Objekt.
- Production-Grenzen werden **dokumentiert, nicht umgangen**: `render()` ist No-Op; `dispatch_command` behandelt Nav-/Selection-Commands nicht; die Production-View-Matrix-Konvention ist (noch) GL-inkompatibel → Lab-Override bleibt, mit Verweis (§A.1).
- Frame-Lifecycle entspricht Production: `on_camera_changed`/`on_*_changed` → `sync()` 1× pro Frame (analog `Application.update_viewport`).

---

## G. Kleinstes notwendiges Arbeitspaket

### WP-IL-01 — „Integration Lab auf Production Camera + Production Viewport re-basen“

**Ziel:** Das Lab benutzt Production-Code dort, wo er existiert; das Experiment-Harness bleibt unangetastet. Keine Production-Änderung, keine Kamera-/Renderer-Neuentwicklung, keine Fix-Versuche am historischen Symptom.

**Scope (erlaubte Dateien):** ausschließlich `experiments/mirai_bastel_integration_lab/**` (Code + README).

1. `lab_camera.py`: `LabOrbitCamera` erbt von `src.mirai.viewport.camera.OrbitCamera` statt V0.2; die Klasse reduziert sich auf den dokumentierten GL-View-Matrix-Override. V0.2-Import entfernt.
2. `adapters/core_to_render.py`: `CoreRenderBinding` wird dünne Fassade über `src.viewport.Viewport` (`Viewport(mesh, selection=obj.scene.selection)`, `bind_camera`, `on_vertices_moved/on_selection_changed/on_topology_changed/on_camera_changed`, `sync()`); Counters/Resource-IDs aus Production-`RenderMesh` für HUD/Report.
3. Import-Wechsel `TraceStore`/`PygletStore` → `src.viewport.resource_store`; `MaterialState` bleibt als Harness-Klasse (duck-type `uniform_packet`).
4. `adapters/picking.py`: ersetzen durch `src.mirai.viewport.picking.pick_nearest_vertex`.
5. Selection: Buchhaltung nur noch über Core-`Selection` (+ `mark_selection_dirty`).
6. Draw-Harness im Fenster: bleibt strukturell bestehen, speist sich aber aus den Production-RenderMesh-Daten (Positions/Normals/Indizes); den Dual-Pfad `camera_uniforms` ↔ Shader-Feed auf einen Quellpfad konsolidieren (Entscheidung im Lab dokumentieren).
7. Input: **nicht** Teil von WP-IL-01 (bleibt bewusst Roh-Pyglet; Umbau auf `BindingSet`/Commands ist ein eigenes Folgewpaket, damit WP-IL-01 klein bleibt).
8. Tests anpassen (Ziel: weiterhin grün), plus ein neuer Regressionstest: „Camera-Op → nur `camera_uniforms`-Update, 0 Geometry-Uploads, stabile Resource-IDs“ über den Production-Pfad.
9. README aktualisieren: Status (Production-basiert), Testanzahl, Abschnitt „Production-Grenzen“ (View-Matrix-Konvention §A.1, `render()` No-Op, unhandled Commands).

**Akzeptanzkriterien:**

- Kein Import aus `experiments.mirai_bastel_viewport_V02` mehr im Lab (grep-prüfbar).
- `pytest experiments/mirai_bastel_integration_lab/tests` grün; `pytest tests --ignore=tests/test_extrude_tool.py` weiterhin 383 grün (Production unberührt).
- `python report.py` (headless): Camera-Orbits → `camera_updates > 0`, `mesh_rebuilds = 0`, IDs stabil.
- `python run.py --selftest` → PASS an echter GL (Mesh + HUD sichtbar) — damit ist der Production-Kamera-Pfad erstmals live erprobt (mit dem dokumentierten Override).

**Explizit out of scope:** Production-Änderungen jeder Art, Kamera-Matrix-Fix, Root-Cause-Analyse des historischen Symptoms, Input/Binding-Umbau, OBJ-Productionisierung, Selection-UX-Entscheidung, Window-Adapter für Production.

---

## H. Sonstige Feststellungen (Repo-Hygiene, ohne Handlung in diesem Audit)

- `viewport/extrude_tool.py` im Repo-Root: 21 Bytes, Inhalt `<longcat_arg_value>` — korrupte Streudatei, nicht Lab-bezogen. Aufräumen ist eine separate Entscheidung.
- `experiments/mirai_bastel_integration_lab/_run_debug.log` ist committed (Debug-Artefakt im Repo).
- Lab-README nennt 33 Tests; real sind es 42 (Doc-Drift).
- `experiments/mirai_bastel_integration_lab/docs/` war vor diesem Audit leer (dieses Dokument füllt sie erstmals).
- `tests/test_extrude_tool.py` hat einen vorbestehenden Importpfad-Fehler (Gate-6-Befund, „stale“ nach der Experiment-Restrukturierung); nicht Teil dieses Audits.

---

## Ergebnis in einem Satz

Das Lab ist nicht „kaputt“, sondern **eine Generation alt**: Production wird nur für `src/core` benutzt; alles darüber (Camera/Viewport/Render/Store/Selection/Picking/Input) ist V0.2-Experiment-Code bzw. Duplikat, das Gate 5/6/7 inzwischen kanonisch in `src/` liefern. Der Dual-Path-Befund ist verifiziert und dokumentiert (nicht als Root Cause behandelt). Zusätzlicher Audit-Befund: Der in V0.2 gefundene GL-View-Matrix-Mismatch existiert unverändert auch in der Production-Kamera und ist dort latent — das Lab-Override ist funktional notwendig, und der Lab-Harness ist die ideale Live-Verifikationsstelle, sobald WP-IL-01 umgesetzt ist.

---

## I. Implementierungsrecord WP-IL-01 (2026-09-08, nachgetragen)

WP-IL-01 (§G) wurde direkt nach diesem Audit umgesetzt. Alle Änderungen
liegen ausschließlich unter `experiments/mirai_bastel_integration_lab/`;
`src/` und andere Experimente sind unberührt (Git-Diff prüfbar).

### Umgesetzt

- **`lab_camera.py`:** `LabOrbitCamera` erbt von
  `src.mirai.viewport.camera.OrbitCamera`; die früheren V1-Adaptionen
  (`project_to_screen`, `screen_to_ray`, `screen_delta_to_world`, `pan_px`,
  `basis`) sind entfernt — alles Production-Standard (`pan` ≡ `pan_px`).
  Einziges Override: `build_view_matrix` (gluLookAt-Konvention, §A.1).
- **`adapters/core_to_render.py`:** `CoreRenderBinding` ist eine dünne
  Fassade über `src.viewport.Viewport` — Camera/Selection/Geometry/
  Material/Topology laufen ausschließlich über die Production-Notifikations-
  API (`on_*_changed` + `sync()`). Kein eigenes Render-Mesh, keine doppelte
  Selection-Buchhaltung, keine V0.2-Importe. Neu: `LabMaterialState`
  (Harness-Material, duck-typed `uniform_packet()`), `LabPygletStore`
  (siehe Befund 2), Lese-API für den Draw-Harness (`positions`,
  `triangle_indices`, `vertex_count`, `triangle_count`).
- **`adapters/picking.py`:** Delegation an
  `mirai.viewport.picking.pick_nearest_vertex` (Duplikat entfernt).
- **`integration/lab_viewport.py`:** Fenster-Harness bleibt strukturell
  (eigener Shader, eigene Draw-Vlists, HUD, Selftest); Kamera-Pan über
  Production-`pan`; Selection einspurig über Core-`Selection` +
  `apply_selection()`; Vertex-Move über `on_vertices_moved`-Pfad mit
  Normalen-Patch über Production-`DerivedGeometry.affected_neighborhood`;
  Draw-Feed liest Matrizen von derselben Kamera-Instanz (kanonischer Pfad,
  keine Zustands-Spaltung — §G Punkt 6 ist damit entschieden).
- **Import-Konvention:** Das Lab importiert den Core konsistent über den
  Production-Importpfad (`core`, `viewport`, `mirai` — wie `src/mirai`
  selbst), nicht mehr über das Namespace-Paket `src.core`. `_paths.py`
  legt dafür `repo-root/src` auf `sys.path`.
- **Neu:** `tests/test_production_rebase.py` (9 Regressionen) und
  `_camera_motion_probe.py` (Kamera-Bewegung am echten GL, auto-close).

### Neue Befunde während der Umsetzung (für Gate 11)

1. **Modul-Identität `src.core` vs. `core`:** `SelectionOverlay` vergleicht
   `selection.mode is SelectionMode.VERTEX` — bei Mischimport (Lab über
   `src.core.*`, Production über `core.*`) sind das zwei verschiedene
   Enum-Klassen, und Selection-Flags bleiben stumm (im Live-Test beobachtet:
   `highlight_flags` durchweg 0.0). Konsequenz: konsequenter
   Production-Importpfad im Lab (siehe oben). Generische Lektion: Grenz-
   übergreifend geteilte Objekte müssen aus EINEM Modulpfad stammen.
2. **`PygletStore` + Default-Shader = vec3-Raster:** `allocate()` rechnet
   `count = nbytes // 12` (position vec3); nicht-3-teilbare Ressourcen
   (camera_uniforms 32 floats, material_uniforms 8, highlight_flags n_verts)
   werden abgeschnitten bzw. laufen beim `update()` über die Kapazität.
   `register_attribute_spec(name, "position", 1)` ist mit dem Default-Shader
   nicht verwendbar — pyglet erwartet für `position` stets `count * 3`
   floats (ValueError „Invalid data size for 'position'. Expected 108, got
   36." im Live-Lauf). `LabPygletStore` richtet die Allokationsgröße auf
   Vielfache von 12 Bytes aus (ceil); ein echter 1-Komponenten-/Multi-
   Attribut-Shader bleibt Production-Entry-Point-Scope.
3. **`RenderMesh._sync_material` ohne Allocate-Fallback:** `_sync_camera`
   prüft `store.has(...)` und allokiert bei Bedarf, `_sync_material` tut
   das nicht — spätes Material-Binding (wie `Viewport.bind_material` es
   vorsieht) wirft mit `PygletStore` einen KeyError. Production betrifft
   es aktuell nicht (kein call-site); der Lab-Store allokiert defensiv
   vor. Gate-11-Kandidat.
4. **Historisches Kamera-Symptom (Status, keine Root-Cause-Erklärung):**
   Nach der Re-Basis sind Kamera-Orbit/Zoom am echten GL **sichtbar**
   (`_camera_motion_probe.py`: Framebuffer-Signatur ändert sich nachweislich,
   Continuous-Redraw bestätigt). Die früheren Dual-Pfade existieren nicht
   mehr; die Frage „war das alte Symptom nach dem Re-Base noch relevant?"
   ist damit praktisch gegenstandslos — die Production-Kamerakette ist im
   Lab live erprobt.

### Akzeptanznachweise (alle erfüllt)

| Kriterium (§G) | Nachweis |
|---|---|
| Kein V0.2-Import im Lab | `test_no_lab_module_imports_v02_experiment` + grep |
| Lab-Suite grün | `pytest experiments/mirai_bastel_integration_lab/tests` → **52 passed** |
| Production unberührt | `pytest tests --ignore=tests/test_extrude_tool.py` → **383 passed** |
| `report.py` headless | 60 Orbits → `camera_updates=62`, `mesh_rebuilds=0`, IDs stabil (Cube + Head) |
| `run.py --selftest` an echter GL | **PASS** (572 762/1 024 000 Pixel non-black; HUD 159 005 Text-Pixel) |
| Beobachtung erweitert | `_smoke_window.py` PASS (Cube 55,9 % / Head 38,4 % non-black); `_camera_motion_probe.py` PASS (Continuous-Redraw + Forced-Redraw wirksam) |

Dokumentation: Lab-README (§2/§3/§4/§5/§7/§8/§9/§10) und
`experiments/README.md` auf den Production-Stand aktualisiert.