# Claude Review — Production Viewport / Renderer V02: Current State & Missing Draw Path

> **Reviewer:** Claude (Opus 5.5, claude.ai Project „Mirai Bastel")
> **Review ID:** CLAUDE-001
> **Target path:** `docs/archive/viewport_v02/reviews/VIEWPORT_V02_STATE_REVIEW_CLAUDE_001.md`
> **Repository state reviewed:** `main` @ `ea1fbf3` (2026-09-25)
> **Mode:** Discovery only — no files modified
> **Status:** Archived first-pass review — preserved verbatim
>
> This document is intentionally preserved as the original first substantive review. Do not edit it to reflect later team decisions. Any assessment or response belongs in a separate document/commit.
>
> Subsequent Artist verdict on Q8 (standalone Production app, Playground unchanged) is recorded in `docs/architecture/AD-010-PLAYGROUND-SUPERSEDES-LAB-BINDING.md` (Addendum 2026-09-25), not here.

---

## Original Review

**M1 (Existenzprüfung):** Spec (`docs/viewport/VIEWPORT_V02_ARCHITECTURE.md`), Research-Record, abgeschlossenes Experiment (`experiments/mirai_bastel_viewport_V02/`) und Production-Umsetzung (`src/viewport/`, WP-04 Gate 5/7) existieren. Ein Production-Draw-Pfad existiert nirgends. Verworfen: V1 (AD-006), Integration Lab (Commit `8ef4def`).

### 1. Executive Summary

**Größtenteils geplant — aber es fehlt mehr als nur der letzte Draw-Call.**

Die V02-Planung deckt die *Update-Mechanik* vollständig ab (Dirty-State, Kategorien, Partial-Updates, persistente Buffer, Topology-Rebuild). Das ist implementiert und headless getestet.

Nie entworfen wurde die Schicht dazwischen, das **„Draw Binding"**: wie RenderMesh-Ressourcen zu einem zeichenbaren Shader + Vertex-Buffer + Uniforms werden. Diese Frage wurde dreimal weitergeschoben (Gate 3 → Gate 5 → „künftiges Entry-Point-Gate").

Wichtigster Befund: In **jeder** bisherigen Umgebung (V02-Demonstrator, Integration Lab, Playground, Symmetry Lab) kam das sichtbare Bild aus einem *separaten, parallelen* Draw-Pfad. RenderMesh + Store waren überall nur Buchhaltung. Der Weg „RenderMesh-Daten → Pixel" wurde noch nie gebaut, auch nicht experimentell.

3D-Analogie: Alle Texturen sind sauber gebacken und liegen versioniert im Ordner — aber kein Material-Netzwerk hängt sie ans Objekt, und niemand drückt auf „Render".

Einordnung: keine große Research-Lücke. Nötig sind eine kleine bis mittlere Architekturentscheidung (Draw Binding) plus ein kurzer technischer Spike, danach überwiegend Implementierung.

### 2. Existierende Architektur (belegter Pfad)

```text
Core Mesh/Scene          src/core                              ✅
   │  (Mutation via Tools/Ops)
   ▼
Notifikation             Viewport.on_*()                       ⚠ nur Kamera-Pfad getestet;
   │                                                             Tools rufen on_vertices_moved/
   │                                                             on_topology_changed nirgends auf
   ▼
DirtyState               src/viewport/category.py              ✅
   ▼
RenderMesh.sync()        src/viewport/render_mesh.py           ✅
   ├─ DerivedGeometry    derived.py (Normalen, Bounds)         ✅
   └─ ResourceStore      resource_store.py
        ├─ TraceStore    (Default in Application!)             ✅ in-memory
        └─ PygletStore   (GL, nur Persistenz-Probe)            ⚠ nicht zeichenbar
   ▼
Viewport.render()        viewport.py → `return None`           ❌ No-op
   ▼
Window / Entry Point     —                                     ❌ existiert nicht
```

`Application.init_scene()` baut den Viewport **immer mit `TraceStore`**; es gibt keinen `store_type`-Parameter (`src/mirai/application.py`).

### 3. Bereits entschieden (A)

- **V02-Prinzip, Invarianten, Non-Goals** — „Update only what changed", Kamera invalidiert keine Geometrie, Selection keine Base-Mesh, Topology darf rebuilden (`VIEWPORT_V02_ARCHITECTURE.md` §1–§7).
  - Einschränkung: Die Spec verlangt „proceed only after explicit approval". Kein separater Approval-Eintrag gefunden; Annahme nur implizit über `WP-04_GATE_PLANNING.md` („Decision Documents") und die Gate-5-Umsetzung.
- **Schichtgrenzen** — `src/viewport` kennt `src/mirai` nicht, kein Fenster-Code darin, `Application` window-frei (`WP-04_GATE_5_COMPLETION.md` §2, `SOURCE_ARCHITECTURE.md` §Viewport).
- **Kamera** — eine einzige `OrbitCamera`, duck-typed gebunden (Gate 7); GL-Konvention korrigiert mit Regressionstest (`docs/research/viewport/production_camera_gl_convention.md`, RESOLVED).
- **Session-Entscheidungen aus Gate 5, nur im Completion Report (kein AD):** Selection-Overlay als Highlight-Flag-Buffer (§7.1); Normalen = erstes Fan-Dreieck, ungewichtet gemittelt (§7.2); RenderMesh mutiert den Core nie (§7.3).
- **Ausdrücklich offen:** „Production-Fenster, Entry-Point und konkrete Draw-Call-Integration" (`SOURCE_ARCHITECTURE.md` §5).

### 4. Implementiert (B)

| Komponente | Status |
|---|---|
| `DirtyState`, Kategorien | fertig |
| `DerivedGeometry` (Adjazenz, lokale Normalen, Bounds, Fan-Triangulierung) | fertig |
| `RenderMesh` (Build, Sync-Dispatch, Partial-Uploads, Topology-Rebuild) | fertig |
| `SelectionOverlay` (Flag pro Vertex) | fertig, vereinfacht |
| `TraceStore` | fertig |
| `PygletStore` | nur Persistenz-Probe (siehe unten) |
| `Viewport`-Fassade | fertig, `render()` = No-op |
| `Application` ↔ `Viewport` | nur Kamera gebunden, `update_viewport()` → `sync()` |
| `OrbitCamera` mit GL-Matrizen, `DisplayState`, CPU-Picking | fertig (`src/mirai/viewport/`) |
| pyglet→Input-Translator | vorhanden (`src/mirai/pyglet_input.py`) |
| OBJ-Import | vorhanden (`scene_factory.build_core_scene_from_obj`) |

Warum `PygletStore` nicht zeichenbar ist:
- jede Ressource ist eine eigene `GL_POINTS`-VertexList auf dem Default-Shader;
- Indizes liegen als Floats vor, kein echter Index-Buffer;
- Uniforms sind als Vertex-Attribute abgelegt;
- `nbytes // 12` schneidet Daten ab (Playground: Padding-Workaround `PlaygroundPygletStore`).

### 5. Tatsächlich verifiziert (C)

- 546 Production-Tests grün am 2026-09-25 (`tests/`, ohne das bekannt kaputte `test_extrude_tool.py`); davon 76 direkt Viewport. **Alle gegen `TraceStore`.**
- `PygletStore`: keine automatisierten Tests; einmaliger Xvfb-Live-Check (1 Attribut, 50 Updates, Objekt-ID stabil — Gate 5 §6).
- V02-Experiment: 10/10 + GPU-Check, Verdikt PROVEN — der Demonstrator zeichnete aber über ein *eigenes* indexiertes VBO und patchte es von Hand parallel zum Store (`demonstrator.py::_build_mesh_vbo`, `_apply_vertex_move`).
- Benchmarks: nur Zähler-Invarianten auf dem 8-Vertex-Würfel. Keine Timings auf dem 326V-Head, keine Messung auf Low-End-Hardware. V1-Vergleich nie durchgeführt, V1 inzwischen retired; einzige Baseline sind die historischen Zahlen in `VIEWPORT_V02_RESEARCH.md` §4 (Orbit ~86 ms, Vertex-Drag ~101 ms).
- Kamera-Matrizen live korrekt: Symmetry Lab zeichnet mit der Production-`OrbitCamera` direkt.

### 6. Fehlender Draw-Pfad (nach Abhängigkeit)

1. **Draw-Binding-Entscheidung** — wie werden positions/normals/indices/highlight_flags zu *einem* zeichenbaren Objekt? In pyglet: eigenes `ShaderProgram` + `vertex_list_indexed` mit mehreren Attributen. Widerspricht dem heutigen Store-Vertrag „eine Ressource pro Name"; Uniforms gehören ans Programm, nicht in einen Buffer. Berührt den V02-Ressourcenvertrag → formale Entscheidung nach AGENTS §5.
2. **Store-Wahl nach GL-Kontext** — `Application` muss einen GL-fähigen Store erst *nach* Fenstererzeugung verwenden können.
3. **Fenster + Entry Point** — Ort offen (`SOURCE_ARCHITECTURE` §5). Frame-Loop: `sync()` → Draw; Resize → `on_camera_changed(aspect)`.
4. **Draw-Call** — Programm, Uniforms (view/proj/light), Depth-Test, indexierte Dreiecke.
5. **Kamera-Input** — Input → `camera.orbit()` → `viewport.on_camera_changed()`. Bausteine existieren, Verdrahtung fehlt.

### 7. Offene Architekturfragen

- **Q1 Draw Binding:** Store-Vertrag erweitern (Attributgruppen), GL-Spiegel der CPU-Daten mit Dirty-Ranges, oder `PygletStore` neu fassen?
- **Q2 Buffer-Layout:** indexiert/geteilt (V02) vs. expandiert pro Dreieck (Playground). Flat Shading aus `DisplayState` braucht eins davon oder eine Shader-Lösung.
- **Q3 Kanten/Punkte** für Wireframe/Overlay: weder in RenderMesh noch in der Spec.
- **Q4 Overlay-Darstellung:** Vertex-Flags zeigen Edge-/Face-Selection nicht sauber (Spec §12 offen, Gate 5 vertagt).
- **Q5 Triangulierung/Normalen:** Symmetry Lab zeigt, dass Fan + erstes-Dreieck-Normale bei gespiegelten Quads asymmetrisch ist (lab-lokal via Newell gelöst). Blockiert den ersten Pixel nicht.
- **Q6 Ort von Fenster/Entry-Point**, und ob `init_scene` einen Store-Parameter bekommt.
- **Q7 Wer benachrichtigt den Viewport nach Tool-Operationen?** Laut Gate 5 §0 an UX gekoppelt; für den ersten Pixel nicht nötig.
- **Q8 (Intent/Priorität, Artist):** Verhältnis Playground ↔ Production-App (AD-010 vertagt).

### 8. Research vs. Implementierung

**Research/Entscheidung nötig:** Q1 (Spike + AD); Minimal-Antworten auf Q2, Q3, Q6; Q8 (Artist); Messung auf Head-Mesh und Low-End-PC (autonom möglich, OBJ-Import existiert jetzt — die Blockade aus Gate 5 §7.4 entfällt).

**Entschieden, Implementierung fehlt:** gesamte Dirty-State-/Partial-Update-Logik existiert, wird aber von keinem echten Draw benutzt; Viewport-Notifikation nach Core-Mutation (Muster in Gate 5 §9, Auslöser fehlt); Benchmark-Protokoll (Spec §8/§13).

### 9. Minimale erste Mirai-App

- Production-Entry-Point öffnet ein pyglet-Fenster.
- `Application` + `init_scene` mit Würfel oder Head-OBJ (beides existiert).
- Viewport mit GL-fähigem Store zeichnet **über RenderMesh-Buffer** schattierte Dreiecke (der eigentliche Neubau).
- Resize setzt den Aspect.
- Orbit/Pan/Zoom über bestehende Bindings + `pyglet_input`.
- Abnahme: beim Orbiten bleiben `geometry_uploads = 0` und Resource-IDs stabil — erster *Live*-Beweis des V02-Kamerapfads.
- Optional Stufe B: eine Mutation über das bestehende MoveTool (Prioritätsfrage).
- Nicht dabei: Selection-Darstellung, Tool-UX, Wireframe, Gizmo, Symmetry, HUD.

### 10. Empfohlener nächster Discovery-Schritt

Type-B-Paket **„Draw Binding Spike"**, klein und wegwerfbar unter `experiments/`: eigener Shader + `vertex_list_indexed` aus RenderMesh-Daten; Slice-Updates pro Attribut; Index-Neuaufbau bei Topology; Timings auf `head_basemesh.obj` (Orbit, 1-Vertex, Multi-Vertex) auf dem Low-End-PC. Ergebnis: ein AD zu Q1 mit Minimal-Antworten zu Q2/Q3/Q6 — keine Implementierung.

### Performance / Dirty-State

V02 wurde genau gegen dieses Muster entworfen: V1-Ursache „jedes Event = kompletter Rebuild" (`VIEWPORT_V02_RESEARCH.md` §6). Der Playground reproduziert es teilweise: `_rebuild_vbo()` löscht und erzeugt alle Listen neu (Selection, Topology, Multi-Vertex-Transforms); Nicht-Tweak-Transforms machen pro Update `full_recompute`; selbst der 1-Vertex-Patch scannt alle Faces. WP-STAB-07 (stale `derived`) und WP-STAB-09 (falscher Buffer-Offset) sind genau die Fehlerklasse, die RenderMesh strukturell verhindert. AD-010 hält die Absicht, diese Rebuilds durch In-place-Patching zu ersetzen, bereits fest — nicht umgesetzt.

Gelöst: Zähler-Garantien (headless), inkrementelle Normalen = Vollberechnung, GL-Persistenz für ein Attribut.
Nicht gelöst: sichtbare Flüssigkeit, reale Timings, Multi-Vertex-Uploads (Spec §12 offen), Kosten eines Live-Topology-Rebuilds.

Der beobachtete „Pop" ist im Repo nicht dokumentiert; eine Ursache wäre Vermutung.

### Nebenbeobachtungen (nicht bewertet)

- Gate-3-Report behauptet `src/main.py`; laut Git existierte diese Datei nie.
- Docstring in `src/viewport/derived.py` sagt „flächengewichtet", der Code mittelt ungewichtet (Gate-5-Report korrekt).
- `docs/architecture/ROADMAP.md` §14 veraltet (Gates 3–4 „queued", obwohl 5–7 erledigt). WP-04 Gates 8–12 nie ausgeführt; Gate 10 wegen fehlendem Entry-Point blockiert.
- AD-010 sagt „archivieren, nicht löschen"; das Integration Lab wurde gelöscht und existiert nur noch in der Git-History mit Tombstones.

### Evidence index

`docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` · `docs/viewport/VIEWPORT_V02_RESEARCH.md` · `docs/WP-04_GATE_PLANNING.md` · `docs/WP-04_GATE_5_COMPLETION.md` · `docs/WP-04_GATE_7_COMPLETION_REPORT.md` · `docs/architecture/SOURCE_ARCHITECTURE.md` · `docs/architecture/AD-006-*`, `AD-010-*` · `src/viewport/*` · `src/mirai/application.py` · `experiments/mirai_bastel_viewport_V02/{README.md,demonstrator.py}` · `playground/{window.py,renderer.py,gl_store.py,vbo_builder.py}` · `playground/tests/test_wp_stab_07_*`, `test_wp_stab_09_*` · `experiments/symmetry_lab/README.md` · Commit `8ef4def` (`git show 8ef4def^:experiments/mirai_bastel_integration_lab/adapters/core_to_render.py`)
