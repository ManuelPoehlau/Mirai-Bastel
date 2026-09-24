# Handoff: WP-SYM-LAB-01 — Slice 2 (Lab-Fenster: Mesh sehen, navigieren, Vertex auswählen)

**An:** Claude Code
**Modell/Effort:** Opus, effort `high`
**Modus (M5):** Production — Architektur ist entschieden (§2), jetzt wird zuverlässig umgesetzt.
**BUILD darf keine neue Erkenntnis behaupten.** Wenn beim Implementieren etwas
unerwartet anders aussieht als hier beschrieben, nicht still weiterbauen — anhalten
und melden (siehe „Bei Widerspruch" am Ende).

**Namenshinweis:** `WP-SYM-01` = Symmetry-*Capability* (gemergt). `WP-SYM-LAB-01` =
das separate **Symmetry Lab**. Slice 1 (`5e7de54`, gemergt als `5bb1bd8`) lieferte
`src/mirai/pyglet_input.py`.

---

## 1. Referenzdokumente (gelten, nicht neu verhandeln)

- `docs/architecture/WP-SYM-LAB-01_SLICE1_CLAUDE_CODE_HANDOFF.md` — Kontext des
  Binding-Checkpoints (Binding-Schicht braucht für einen zweiten Kontext keine Änderung).
- `docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md` — I4 (eine
  Binding-Autorität pro Kontext), I5/I6 (Kontext-Overrides sichtbar), A3 (Gesten-Semantik
  OFFEN), „Engineering Freedom".
- `docs/architecture/AD-010-PLAYGROUND-SUPERSEDES-LAB-BINDING.md` — Präzedenzfall
  „adaptieren statt cross-importieren" (`playground/gl_store.py` aus `LabPygletStore`)
  und Befund zur GL-Kontext-Reihenfolge.
- `docs/research/viewport/production_camera_gl_convention.md` — Production-
  `OrbitCamera` ist seit `bbeef97` GL-korrekt (gluLookAt-Konvention, Regressionstest
  `tests/test_camera_gate5_matrices.py`).
- `experiments/README.md` — Ein Ordner pro eigenständigem Forschungsprogramm; nicht
  zu verwechseln mit `playground/experiments/`.
- `AGENTS.md` §M3 (Promotion Boundary).

## 2. Entscheidung Rendering/Kamera (Engineering, bestätigt durch Manu 2026-09-24)

Befund:
- Production hat **keinen sichtbaren Draw-Pfad**. `Viewport.render()` ist bewusst ein
  No-op; `PygletStore` führt nur GPU-Ressourcen-Buchhaltung. Alles, was im Playground
  sichtbar ist, entsteht in `playground/window.py` (Shader inline) und
  `playground/vbo_builder.py`. Ein geteilter Renderer ist als künftiges
  „Entry-Point-Gate" vermerkt, nicht beschlossen.
- Die Production-`OrbitCamera` ist GL-korrekt. `PlaygroundCamera` überschreibt die
  View-Matrix nur noch redundant.

Entscheidung:
1. **Das Lab besitzt einen eigenen, minimalen Draw-Pfad.** Benötigte Stücke werden aus
   `playground/` **kopiert/adaptiert, nicht importiert**, mit Herkunftsvermerk im
   Docstring (Datei + Funktion + Commit-Stand). Präzedenz: AD-010, `gl_store.py`.
2. **Keine Extraktion eines geteilten Renderers** in diesem WP. Das würde
   `playground/window.py` anfassen und für genau einen Konsumenten generalisieren.
   Revisions-Trigger: ein **zweites** Nicht-Playground-Fenster braucht denselben
   Draw-Code → dann eigene Entscheidung.
3. **Kein `Viewport`/`PygletStore` im Lab.** Beides zeichnet nichts. Voller VBO-Rebuild
   bei Änderungen ist für das Lab ausreichend.
4. **Kamera = Production-`OrbitCamera` direkt**, keine Subklasse. Startwinkel/Framing
   über `camera.yaw` bzw. `frame_on_bounds()` setzen.
5. **Ort:** `experiments/symmetry_lab/` (eigene README, eigener sys.path-Bootstrap,
   eigene Tests).
6. **Kein Import aus `playground/`** — durch Test abgesichert (§7).

Akzeptierte Kosten: ca. 100–150 Zeilen bewusst duplizierter Draw-/VBO-Code.

## 3. Ziel dieses Slices

Der Artist startet das Symmetry Lab, sieht ein Mesh (shaded + Edges + Vertices),
navigiert mit Orbit/Pan/Zoom und wählt per Klick einen Vertex aus (hervorgehoben).
**Noch keine Symmetrie-Funktion, keine Mutation, kein Move.** Dieser Slice ist die
Grundlage, auf der Slice 3 Symmetrie ein/aus, Plane, Vorschau und Move aufsetzt.

## 4. Scope

1. **Ordner `experiments/symmetry_lab/`** mit:
   - `README.md`: Zweck, Start, Steuerung (Tabelle aus §4.5), Verweis auf dieses Handoff,
     ausdrücklicher Hinweis „importiert nicht aus `playground/`".
   - Einem lab-lokalen sys.path-Bootstrap (Repo-`src/` vor Repo-Root, `examples/` für
     den Asset-Loader). Muster darf `playground/_paths.py` / `playground/run.py`
     („Stufe 0") folgen — **lesen und nachbauen, nicht importieren**.
   - Einem Start-Einstiegspunkt (z. B. `run.py`). Wie gestartet wird (Skript vs. `-m`),
     ist eure Wahl — in der README dokumentieren. Muss auf Windows funktionieren.
   - Modulaufteilung ist eure Wahl. Vorschlag: Bindings/Kontext, Draw (Shader +
     VBO-Daten), Fenster.

2. **Zustand über `mirai.application.Application`** als Container (`scene`,
   `selection`, `camera`, `bindings`). Keine eigene Parallelstruktur.
   Szene laden: `app.scene.mesh = build_core_scene_from_obj(asset_path(name)).mesh`
   (Muster aus `PlaygroundApp.load_asset`), danach
   `app.camera.frame_on_bounds(*mesh_center_and_radius(mesh), margin=...)`.
   Szene/VBOs erst anlegen, **nachdem** das pyglet-Fenster (GL-Kontext) existiert
   (AD-010-Befund).

3. **Asset-Wahl:** Start-Asset per Kommandozeilen-Argument (Registry-Name aus
   `loaders.assets.asset_names()`), Default `subd_cube`. **Kein** In-App-Umschalten
   (keine zusätzlichen Bindings in diesem Slice).

4. **Draw:** Faces shaded (Normalen aus `viewport.derived.DerivedGeometry`,
   Triangulierung via `triangulate_face`), Edges, Vertex-Punkte, selektierter Vertex
   farblich hervorgehoben. Shader und VBO-Datenaufbau adaptiert aus
   `playground/window.py` (`_FACE_*`/`_OVERLAY_*`) bzw. `playground/vbo_builder.py`
   — nur das, was dieser Slice wirklich zeichnet. Kein Flat/Wireframe-Umschalten,
   kein HUD außer optional einer einzeiligen Statusanzeige.

5. **Input-Pfad (der Kern dieses Slices):**
   pyglet-Event → `mirai.pyglet_input` → `app.bindings.command_for(input, SYMMETRY_LAB_CONTEXT)`
   → Lab-Dispatcher.
   - `SYMMETRY_LAB_CONTEXT = "symmetry_lab"` wird **im Lab** definiert, nicht in
     `mirai.interaction`.
   - Lab-Overrides (sichtbar, AD-013 I6) auf dem `BindingSet` im Lab-Kontext, über die
     öffentliche API (`bind`/`set_default` mit `context=`):

     | Aktion | Input | Command | Herkunft |
     |---|---|---|---|
     | Orbit | Alt+LMB (Drag) | `Orbit` | Artist Truth + Playground-Praxis |
     | Pan | MMB (Drag) | `Pan` | globaler Default (Fallback, keine Override nötig) |
     | Pan | Shift+LMB (Drag) | `Pan` | Artist Truth + Playground-Praxis |
     | Zoom | Wheel Up/Down | `Zoom` | globaler Default (Fallback) |
     | Vertex auswählen | LMB (Klick) | `Select` | globaler Default (Fallback) |
     | Orbit auf RMB | RMB | *explizit ungebunden* | Override: eine Primärbindung pro Funktion |

   - **Drag/Klick-Semantik ist Lab-lokal** (AD-013 A3 bleibt offen): Press löst über
     `BindingSet` das Command auf; bei `Orbit`/`Pan` hält das Fenster diesen Zustand bis
     Release und wendet Drag-Deltas auf die Kamera an. `Select` wird bei Release
     ausgeführt, wenn die Bewegung unter einer Lab-lokalen Klick-Schwelle blieb.
   - Der Dispatcher behandelt **nur** die Commands aus der Tabelle. Jedes andere
     aufgelöste Command (z. B. globale Defaults wie `SetFaceMode` auf `f`) ist ein
     No-op — **nicht** einzeln abbinden, **nicht** implementieren.

6. **Auswahl:** nur Vertex-Modus. Klick → `mirai.viewport.picking.pick_nearest_vertex`
   → Auswahl ersetzen; Klick ins Leere → Auswahl leeren. Über `app.scene.selection`.
   Kein Add/Remove/Toggle (Shift+LMB ist Pan, siehe Konflikt-Hinweis §5).

## 5. Not in scope

- Jede Symmetrie-Funktion (ein/aus, Plane, Seam, Vorschau, State-Anzeige) → Slice 3.
- Move/Rotate/Scale, jede Mutation, Undo/Redo.
- Edge-/Face-Modus, Box/Lasso, Add/Remove-Auswahl.
- Neue Commands in `src/mirai/interaction/commands.py` (Lab-eigene Commands kommen,
  wenn nötig, als Lab-lokale Strings — erst ab Slice 3).
- Tastatur-Bindings (dieser Slice kommt ohne aus; ESC zum Schließen ist
  pyglet-Standardverhalten und darf bleiben).
- Geteilter Renderer, `Viewport`/`PygletStore`, Performance-Patching.
- **Konflikt-Hinweis, nicht lösen:** In `artist_input_truth.json` ist Shift+LMB
  sowohl Pan als auch `selection.add`. Das Lab folgt hier der Playground-Praxis (Pan).
  Die Auflösung ist eine Artist-Entscheidung.

## 6. Must NOT change (Diff muss hier leer sein)

- `src/**` komplett (Core frozen; `mirai.interaction`, `pyglet_input`, `Application`,
  `OrbitCamera`, `viewport` — alles nur benutzen).
- `playground/**` komplett (auch nicht die redundante `PlaygroundCamera`, auch nicht
  `vbo_builder.py` „zum Teilen").
- `tools/Input_Mapping_Tool/**`, `artist_input_truth.json`, `INPUT_WIRING_MAP.md`.
- `examples/**` (Assets und Loader nur benutzen).
- Bestehende Tests.

Erwarteter Diff: nur neue Dateien unter `experiments/symmetry_lab/`, ein Eintrag in
`experiments/README.md` (Abschnitt „Aktuelle Experimente") und dieses Handoff-Dokument.

## 7. Erwartete Tests (`experiments/symmetry_lab/tests/`, headless)

- **Import-Grenze:** Nach dem Import aller Lab-Module (Subprozess, analog
  `tests/test_pyglet_input.py::TestInteractionStaysPygletFree`) ist kein Modul mit
  Präfix `playground` in `sys.modules`.
- **Lab-Bindings:** Im Lab-Kontext lösen Alt+LMB → `Orbit`, Shift+LMB → `Pan`,
  MMB → `Pan`, Wheel → `Zoom`, LMB → `Select` auf; RMB → `None`;
  im `global`-Kontext bleiben die Defaults unverändert (RMB → `Orbit`).
- **Dispatcher ohne Fenster:** Die Zuordnung Command → Lab-Aktion (Kamera-Drag-Zustand,
  Select bei Release unter Schwelle, No-op für fremde Commands) ist ohne GL-Kontext
  testbar. Wenn das eure Modulaufteilung nicht zulässt: Aufteilung anpassen, nicht
  den Test weglassen.
- **Auswahl:** Pick auf eine bekannte Vertex-Bildschirmposition ersetzt die Auswahl;
  Pick ins Leere leert sie (mit Production-Kamera + `pick_nearest_vertex`).
- **VBO-Daten:** Face-/Edge-/Vertex-Daten für `subd_cube` haben die erwarteten Längen;
  Highlight-Daten enthalten genau den selektierten Vertex.
- **Szene laden:** Laden per Registry-Name funktioniert für alle drei Assets;
  unbekannter Name → kontrollierter Fehler mit Liste der gültigen Namen.
- Headless-Lösung wie in Slice 1 (`pyglet.options["headless"] = True` vor dem ersten
  `pyglet.window`-Import), dokumentiert im Test-Modul.

## 8. Done-Kriterien

- Neue Tests grün; Produktions-Suite unverändert grün
  (`pytest tests --ignore=tests/test_extrude_tool.py`); `playground/tests` unberührt.
- `git diff --stat` enthält nur die Dateien aus §6 „Erwarteter Diff".
- **Manuelle Prüfung durch Manu** auf dem Windows-Rechner: Lab startet, Mesh sichtbar,
  Orbit/Pan/Zoom wie in der Tabelle, Vertex-Klick markiert. Claude Code beschreibt in
  der README die genauen Startschritte dafür und behauptet **keine** Artist-Validierung.
- Commit-Message-Vorschlag:
  `WP-SYM-LAB-01 Slice 2: Symmetry Lab window — view, navigate, select vertex`

## 9. Bei Widerspruch

Anhalten und melden, nicht still lösen, insbesondere wenn:

- irgendetwas nur durch Import aus `playground/` oder Änderung an `src/` lösbar scheint,
- die Production-`OrbitCamera` im echten GL-Pfad doch falsch clippt (widerspräche
  `bbeef97` und dem Regressionstest),
- eine Binding aus §4.5 über die öffentliche `BindingSet`-API nicht ausdrückbar ist,
- der Asset-Loader oder `build_core_scene_from_obj` sich anders verhält als beschrieben,
- der Slice ohne zusätzliche Tastatur-Bindings nicht bedienbar wäre.
