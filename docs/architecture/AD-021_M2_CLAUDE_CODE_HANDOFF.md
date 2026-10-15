# Handoff: AD-021 — M2 (Platzierung: Objekt-Transform, Pivot, Edit-Objekt wechseln)

**An:** Claude Code
**Modell/Effort:** Opus, effort `high`
**Modus (M5):** Production-Build in Slices. Die Architektur ist entschieden (AD-021 DECIDED, §4.3 L-1…L-5, §4.6, §4.8);
jetzt wird zuverlässig umgesetzt. **BUILD darf keine neue Erkenntnis behaupten.** Sieht beim Bauen etwas anders aus
als hier beschrieben: anhalten und melden („Bei Widerspruch", §9).

**Fortschritt:** M2-0 und M2-1 **gebaut 2026-10-15** (AD-021 §6.2, §6.3; Branch `claude/relaxed-maxwell-2hoj0u`).
M2-2 ist der nächste Slice; seine Gates Q-6 und Q-7 sind beantwortet. M2-2 ruft nach jedem Objekt-Transform und dessen
Undo `Application._placement_changed()` auf.

**Stand:** `main` @ `1c3fd99` (M1 gemergt, Manus Antworten zu Q-11/Q-12). Baseline, gemessen auf dem M1-Stand
(`xvfb-run -a python -m pytest`, mit `libegl1` im Container — ohne EGL werden `tests/test_main_wiring.py` und die
Fenster-Proben übersprungen statt ausgeführt):

| Baum | Ergebnis |
|---|---|
| `tests/` | 3326 passed, 6 skipped, **1 failed** — `tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring`, schlägt auf `main` genauso fehl (eingecheckte Probe vom 2026-10-12, war vorher nur mangels EGL übersprungen). Nicht Teil von M2; nicht anfassen, im Abschlussbericht wieder nennen |
| `playground/tests` | 1241 passed |
| `experiments/symmetry_lab/tests` | 457 passed, 4 skipped |

**Ziel:** Manu kann jedes Objekt in der Szene **platzieren** (verschieben, drehen, gleichmäßig skalieren, um seinen
Pivot), an **jedem** Objekt Punkte/Kanten/Flächen bearbeiten, ohne dass die Platzierung die Form verfälscht, und er
sieht immer, auf welcher Ebene er arbeitet (A-3, A-5). Dazu zuerst die Referenz-Anzeige aus Q-11 (§7.3), weil sie
der offene Schmerzpunkt aus dem M1-Test ist.

---

## 1. Referenzdokumente (gelten, nicht neu verhandeln)

- **[AD-021](AD-021-OBJECT-COMPONENT-MODEL.md)** — vor allem §2 (Platzierungsregel), §4.3 (Transform-Form, **L-1…L-5**),
  §4.4 (Selection, Picking, Drawing), §4.6 (Commands, App-Konsequenzen), §4.7 RF-1…RF-6, §4.8 (Objektraum für Symmetrie
  und Soft), §5.4 „M2", §6 Zeile M2, **§6.1** (was M1 gebaut hat und wie), §7.1–§7.3.
- **M0-Core** (`src/core/scene.py`): `SceneObject.transform: ObjectTransform` (Translation, Rotationsmatrix in Zeilen,
  `scale > 0`, validiert), `pivot` (Objektraum), `ObjectState`. Die Kompositionsformel steht **nicht** im Core
  („M0 speichert nur", E-2).
- **M1-App:** `src/mirai/scene_objects.py`, `Application` (`add_reference`, `_sync_object_views`, `_pick_object`,
  `_select_object_at`, `_switch_object_state`, `_object_mode_refuses`, Mirror-Einträge `(before, after, mesh_step)`),
  `Viewport.set_object_entry`, `picking.pick_object`.
- [AD-012](AD-012-TRANSFORM-SPACE.md) (Constraint-Räume; `space="local"` wird „die Achsen des Objekts", L-5),
  [AD-014](AD-014_Core-Change-Basis-Parameter-for-ScaleOperation.md) (Basis für Achsen-Scale),
  [AD-016](AD-016-TRANSFORM-OWNS-QWE-SINGLE-CURRENT-TOOL.md) (D4: Hold-Key-Gesten W/E/R, WP-06 B3/B4),
  [AD-018](AD-018-PRODUCTION-DRAW-BINDING.md) (deklarierte Ressourcen pro `RenderMesh`; eine Model-Matrix ist „one more
  declared resource", AD-021 §5.4), [AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md),
  [AD-SYM-04](AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md) (E1 „Weltachse", wird durch Q-7 geändert),
  [AD-020](AD-020-SOFT-SELECTION-APP-PATH.md) E3 (Radius aus den Bounds).
- `AGENTS.md` §8a (Teststrategie), `CLAUDE.md` (Doku im selben Commit), `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` §5
  (Haltepunkte).

## 2. Entscheidungen

### Artist (Manu)

| # | Stand | Wirkung in M2 |
|---|---|---|
| Q-1 | Referenz gesperrt | Objekt-Transforms auf einer Referenz werden abgelehnt (RF-4) |
| Q-2 | durch eine Referenz hindurch picken | gilt weiter, auch transformiert |
| Q-3 | Zustandswechsel / Objekt hinzufügen = je ein Undo-Schritt | Objekt-Transform, Pivot, Apply/Clear ebenfalls je ein Schritt (§4.6) |
| Q-4 | nur gleichmäßige Skalierung, `s > 0` | `R` in `4` skaliert gleichmäßig; Achsen-Constraints wirken in `4` nicht auf Scale (Statuszeile) |
| Q-9 | Kamera bleibt beim Hinzufügen | unverändert |
| Q-11 | Blau gut; durchsehen in beide Richtungen nötig | **Slice M2-0** baut den Vorschlag AD-021 §7.3 (RD-1…RD-4), `PROVISIONAL` bis Manus Test |
| Q-12 | Klick in `4` schaltet um — „passt erstmal so" | bleibt |

### Artist — offen, **Gate** für den jeweiligen Slice

Ohne Antwort im Decision Record von AD-021 wird der betroffene Slice **nicht** gebaut (Haltepunkt: Verhalten, das der
Artist spürt). Empfehlungen stehen in AD-021 §7.1.

**Stand 2026-10-15 (Manu):** Q-5, Q-6, Q-7, Q-8 wie empfohlen beantwortet; §7.3 (Q-11) bestätigt; **Q-13 zurückgestellt**
— Pivot verschieben kommt später, bis dahin ist der Pivot der Objekt-Ursprung. M2-3 schrumpft damit auf Apply/Clear
Transform und den Ebenen-Marker; der E-2-Kompensationsfall (Pivot verschieben) wird nicht gebaut, die Formel gilt aber
mit `pivot` aus dem Objekt.

| # | Frage | Gate für | Empfehlung |
|---|---|---|---|
| Q-6 | Wie sieht man, dass ein Objekt transformiert ist? | M2-2 | Statuszeile zuerst |
| Q-7 | Symmetrie-Ebene dreht sich mit dem Objekt (ändert E1) | M2-2 | ja |
| Q-13 | Wie setzt man den Pivot? | M2-3 | `W` + Zusatz-Modifier in `4` verschiebt nur den Pivot |
| Q-5 | Wie wird ein anderes Objekt zum Edit-Objekt? | M2-4 | in `4` wählen, dann `1`/`2`/`3` |
| Q-8 | Springt Undo zum Objekt des Schritts zurück? | M2-4 | ja |

**Q-7 ist kein Detail:** Sobald ein Objekt mit Symmetrie-Definition gedreht werden kann, dreht sich seine Ebene mit
(alles rechnet im Objektraum, §4.8). Ist Q-7 beim Start von M2-2 noch offen, darf M2-2 nur gebaut werden, wenn es
Objekt-Rotation für ein Mesh mit Symmetrie-Definition mit einer Statuszeile ablehnt — melden, nicht still entscheiden.

### Engineering (in diesem Handoff festgelegt, `PROVISIONAL`)

- **E-2 Kompositionsformel.** `world(p) = translation + pivot + s · R · (p − pivot)` mit `p`, `pivot` im Objektraum,
  `R` = `ObjectTransform.rotation` (Zeilen: `R·v` = Zeile·v). Inverse: `p = pivot + Rᵀ · (world − translation − pivot) / s`.
  **Pivot verschieben kompensiert die Translation** (L-2: weder Geometrie noch Weltlage springt): bei neuem Pivot `c'`
  gilt `translation' = translation + (c − c') − s·R·(c − c')`. Weicht der Build davon ab (z. B. Pivot im Weltraum),
  ist das eine Meldung wert, keine stille Änderung.
- **E-6 Ort der Mathematik.** Ein neues Modul `src/mirai/object_space.py` (keine Core-Änderung): `to_world(obj, p)`,
  `to_object(obj, w)`, Richtungen (`R`, `Rᵀ`, ohne Translation), die 4×4-Model-Matrix (spaltenweise wie
  `build_view_matrix`), Bounds in Welt. `ObjectTransform` bleibt im Core reine Daten. Braucht der Build eine Methode am
  Core-Typ, ist das ein **Haltepunkt** (CORE_V1_FREEZE §7).
- **E-7 Objektraum-Kamera.** Alle Komponentenpfade, die heute eine `OrbitCamera` bekommen (Picking, `PickCache`,
  `knife_pick`/`knife_planner`, `MoveTool`/`RotateTool`/`ScaleTool`/Extrude über `screen_delta_to_world`/`basis()`),
  bekommen für das Edit-Objekt einen **Adapter** mit derselben Schnittstelle, der in den Objektraum umrechnet:
  `project_to_screen(p_obj)`, `screen_to_ray` (Ursprung und Richtung im Objektraum), `eye()`, `basis()`,
  `screen_delta_to_world` (liefert ein Objektraum-Delta), `camera_revision` (ändert sich mit Kamera **und** Transform —
  sonst bleibt der Pick-Cache nach einem Objekt-Transform stale). Das ist L-5 „im Tool-Layer, einmal": die Tools und
  Core-Operationen bleiben unverändert. **Erste Arbeit in M2-1:** jede Methode/jedes Attribut auflisten, das die
  Konsumenten an der Kamera lesen (grep), und den Adapter genau darauf bauen. Findet sich ein Konsument, der Weltwerte
  ohne Kamera erzeugt (z. B. feste Weltachsen), gehört er in die Liste unten.
- **E-8 Constraint-Achsen (L-5).** `X`/`Y`/`Z` bleiben **Weltachsen** (AD-012 Default `world`); für einen
  transformierten Edit-Objekt werden die aus `_resolve_space` kommenden Achsen/Ebenen-Normalen mit `Rᵀ` in den
  Objektraum gedreht, bevor die Core-Operation läuft (Scale: als `basis`, AD-014). `space="local"` = Objektachsen = im
  Objektraum die Einheitsachsen — nicht in M2 verdrahten, nur nicht verbauen.
- **E-9 Zeichnen.** Eine Model-Matrix pro `RenderMesh` als deklarierte Uniform (`model_uniforms`, AD-018), im
  Vertex-Shader `u_model`; Normale mit `mat3(u_model)` und `normalize` (gleichmäßige Skalierung, daher kein
  Normal-Matrix-Inverses nötig). Die Overlays des Edit-Objekts (Punkte, Linien, Flächen, Tool-Layer des Knife,
  Soft-Bänder, Symmetrie-Anzeige) bekommen **dieselbe** Matrix — entweder als Uniform oder CPU-seitig beim Aufbau
  der Positionen; der Build wählt eine Form und begründet sie in einem Satz. Identität muss **bitgleich** zum
  heutigen Bild bleiben (Test über die hochgeladenen Daten, nicht über Pixel).
- **E-10 Objekt-Picking in `4`** (`pick_object`): den Weltstrahl je Objekt in dessen Objektraum umrechnen — Ursprung
  mit `to_object`, Richtung mit `Rᵀ·d / s` **ohne** neu zu normieren. Dann ist der Treffer-Parameter `t` derselbe
  Welt-Parameter für jedes Objekt und bleibt objektübergreifend vergleichbar.

## 3. Slices

Jeder Slice: eigener Commit (oder wenige), eigene Tests, Doku im selben Commit, am Ende eine kurze Praxistest-Anleitung
auf Deutsch in AD-021 (Kurzfassung) und `docs/ATELIER.md` §2 B. Reihenfolge verbindlich; ein Slice, dessen Gate offen
ist, wird übersprungen und gemeldet, nicht vorgezogen erfunden.

### M2-0 — Referenz-Anzeige (Q-11, AD-021 §7.3) · kein Gate

- `Alt+D` (neues Command, z. B. `TOGGLE_REFERENCE_GHOST`, `PROVISIONAL`, über `keymap.json` umbelegbar) schaltet
  **alle** Referenzen zwischen *schattiert* und *Ghost*; Statuszeile `References: ghost` / `References: shaded`; kein
  Undo-Schritt, Zustand wie `DisplayState` (Application-weit, überlebt Laden nicht zwingend — wählen und notieren).
- Ghost (RD-1): dasselbe `REFERENCE_BASE_COLOR`, Alpha ≈ 0.3 (`PROVISIONAL`), Blend an, Depth-Test an, **Depth-Write
  aus**, Back-Face-Culling an, gezeichnet **nach** allen opaken Einträgen und nach dem Edit-Mesh, vor Linien/Punkten.
  Shader: ein Alpha-Uniform im bestehenden Programm (Default 1.0 = heutiges Bild).
- RD-3: Referenzen werden auch im Wireframe gezeichnet (heute hängen die Einträge an `show_faces`); nur das Edit-Objekt
  wird Draht. Normale Nicht-Edit-Objekte (Zustand `NORMAL`) folgen weiter dem Display-Modus wie das Edit-Objekt —
  **melden**, falls das im Test seltsam wirkt (es ist eine Ableitung, keine Antwort von Manu).
- RD-4: Picking unverändert.
- Tests (headless): Ghost-Flag erreicht den Store; Zeichenreihenfolge/Flags im `TraceStore` bzw. über ein Fake-Store-
  Protokoll; Wireframe zeichnet Referenz-Einträge; Undo-Stack unberührt. GL-Rauchtest unter xvfb mit zwei Screenshots,
  passend zu Manus zwei Fällen: (1) `gollum` als Szene, `head_basemesh` als Referenz, Ghost an → gollum ist **im** Kopf
  sichtbar; (2) `head_basemesh` als Szene, `gollum` als Referenz, Wireframe → gollum ist im Drahtkopf sichtbar.

### M2-1 — Model-Matrix und Objektraum-Kamera · kein Gate, für Manu unsichtbar

- `object_space.py` (E-2, E-6), Model-Matrix im Draw-Pfad (E-9), Objektraum-Kamera-Adapter (E-7), Constraint-Achsen
  (E-8), Objekt-Picking (E-10), `frame_scene` rahmt die Welt-Bounds des Edit-Objekts.
- **Kein UI**, mit dem man transformieren kann. Getestet wird mit Transforms, die der Test direkt an
  `SceneObject.transform` setzt (plus `_sync_object_views`/Notification).
- Pflicht-Tests:
  - Identität: alle bestehenden Tests unverändert grün; hochgeladene Positionen/Uniforms des Edit-Objekts bitgleich.
  - Mit Transform (z. B. 30° um Y, Translation, `s = 1.5`): Hover/Klick in `1`/`2`/`3` trifft dasselbe Element wie ohne
    Transform an der transformierten Bildschirmstelle; Move entlang Welt-X verschiebt die Weltlage um genau den
    Bildschirm-Delta-Anteil, die Objektraum-Positionen um `Rᵀ·Δ/s`; Rotate/Scale mit Constraint; Extrude; Knife-Klick
    auf eine Kante; Soft-Gewichte gleich denen ohne Transform (Radius in Objekteinheiten, §4.8); Overlays an den
    Weltpositionen.
  - **P-2 als Test** (§4.8): `head_basemesh` mit Symmetrie X, Objekt um 30° gedreht → `symmetry_state` bleibt `valid`,
    Paarungen bitgleich zu ohne Transform, symmetrischer Move bleibt exakt gespiegelt.
  - RF-6 transformiert: eine Referenz vor dem Edit-Objekt blockiert weiter nichts.

### M2-2 — Objekt-Transform in `4` · Gate Q-6, Q-7

- In `4` mit ausgewählten Objekten (`Selection.objects`): `W`/`E`/`R` halten + Maus = Objekt verschieben / drehen um
  den Pivot / gleichmäßig skalieren um den Pivot — dieselben Hold-Key-Gesten wie bei Komponenten (Arm, erste Bewegung
  beginnt, Loslassen committet, `Esc` bricht exakt ab), Constraints `X`/`Y`/`Z` als Weltachsen (Move, Rotate). L-1:
  schreibt nur `transform`, nie das Mesh.
- Abgelehnt mit Statuszeile: Referenzen in der Auswahl (RF-4, Q-1; heutiger Text in `_object_mode_refuses`), keine
  Auswahl, `T`/`C`/`Entf`/`Shift+S` (bleiben Komponentenarbeit). Hover gibt es in `4` weiterhin nicht (M1-Entscheidung);
  ohne Auswahl also keine Hover-Variante.
- Ein Commit = ein Undo-Schritt (`ObjectTransformCommand`: Objekt(e), vorher/nachher `transform` — bei mehreren
  ausgewählten Objekten ein Composite, §4.6), Mirror-Eintrag mit `mesh_step=False`; Undo/Redo zeichnet nur die
  betroffenen Einträge/Matrizen neu und invalidiert den Pick-Cache (Transform ändert die Projektion).
- Q-6 nach Antwort; bei „Statuszeile zuerst": nach jedem Objekt-Commit und beim Wechsel nach `1`/`2`/`3` auf einem
  transformierten Edit-Objekt ein Text wie `Object 'gollum': moved/rotated/scaled (object level)`.
- Q-7 nach Antwort: Wortlaut in AD-SYM-04 (E1) und im Docstring von `src/mirai/symmetry_axis.py` von „Welt-Ursprung /
  Weltachse" auf „Ursprung / Achse des Objekts" ändern (AD-021 §4.8), im selben Commit; die Symmetrie-Anzeige (Ebene)
  folgt dem Transform (E-9).
- Tests: Geste, Abbruch, Undo/Redo, Ablehnungen, mehrere Objekte, Edit-Objekt transformieren und danach Komponenten
  bearbeiten (M2-1 macht das korrekt), Serialisierung des Transforms existiert seit M0 (nur Roundtrip-Stichprobe).

### M2-3 — Pivot, Apply/Clear Transform, Ebenen-Marker · Gate Q-13 (Marker: Q-6)

- Pivot setzen nach Q-13; L-2: verschiebt nie Geometrie und lässt die Weltlage stehen (E-2-Kompensation). Ein
  Undo-Schritt. Den Pivot sichtbar machen (kleines Kreuz/Punkt als Overlay, Look `PROVISIONAL`), solange `4` aktiv ist.
- **Apply Transform** (L-3, Max „Reset XForm"): Mesh-Positionen = Weltpositionen, Transform = Identität, Pivot so, dass
  nichts springt — ein Undo-Schritt als **erster Composite-Command** des Projekts (`MeshStateCommand` + Transform-
  Command, §4.6). **Clear Transform:** Transform = Identität, Mesh bleibt, Objekt springt — ein Undo-Schritt.
  Bindung/Menü: nicht entschieden; Vorschlag als `PROVISIONAL` (z. B. Einträge in einem Objekt-Menü oder Tasten in `4`)
  und im Bericht als Frage an Manu markieren.
- **Achtung Symmetrie:** Apply mit einer Rotation, die die Symmetrie-Achse nicht auf eine Achse abbildet, zerstört die
  exakte Symmetrie im Objektraum (Naht nicht mehr bei 0). `PROVISIONAL`: Apply wird für ein Mesh mit
  Symmetrie-Definition abgelehnt, außer Rotation = Identität oder achsentreu; Statuszeile nennt den Grund. Melden.
- Ebenen-Marker nach Q-6 (L-4).

### M2-4 — Edit-Objekt wechseln · Gate Q-5, Q-8

- Geste nach Q-5 (Empfehlung: Objekt in `4` wählen, dann `1`/`2`/`3`), Reihenfolge §4.4: `objects` lesen,
  `scene.edit_object_id` setzen, Komponenten leeren. Eine Referenz wird nie Edit-Objekt (RF-2) — Ablehnung mit
  Statuszeile. Kein Undo-Schritt (Selection/Scene-Zustand, §2), aber im Mirror-Eintrag.
- Viewport: das neue Edit-Objekt bekommt den Overlay-Eintrag, das alte wird Objekt-Eintrag — ohne Neuaufbau beider
  Meshes, wenn möglich (Einträge tauschen); `_sync_object_views` deckt das Neuzuordnen ab.
- Soft: ein Edit-Objekt-Wechsel ist das vierte Radius-Ereignis (`_soft_refresh_radius`, §4.8); Symmetrie-Report-Cache,
  Pick-Cache, Knife-Zustand und Hover zurücksetzen.
- Q-8 nach Antwort: Undo eines Schritts an einem anderen Objekt macht dieses wieder zum Edit-Objekt (der Mirror-Eintrag
  trägt `edit_object_id` seit M1; `_restore_selection` setzt es bereits — prüfen, dass das mit Q-8 übereinstimmt, und
  den Viewport-Tausch auslösen).
- RF-5 neu lesen: mit Wechsel gibt es mehrere bearbeitbare Objekte; „das Edit-Objekt wird nie Referenz" bleibt.

## 4. Nicht im Umfang

Hierarchie/Parent, Instancing, nicht-gleichmäßige Objekt-Skalierung, Mehr-Objekt-Komponentenbearbeitung (A-4),
Soft über Objektgrenzen, `space="local"` als Constraint-Modus, Speichern/Laden von Szenendateien in der App,
Objekt-Hover in `4`, Objekte löschen/umbenennen, Performance auf gollum (WP-VIEW-PERF-01; messen und nennen ja, optimieren
nein), Playground und Symmetry Lab (beide bleiben bei einem Objekt; das Lab lehnt `4` in BLOCK sichtbar ab).

## 5. Core

**Keine Core-Änderung erwartet.** M0 liefert Objekte, Transform-Daten und Serialisierung; alle Commands sind
App-`Command`s (§4.6). Wird doch eine nötig (z. B. eine Methode an `ObjectTransform`, ein Hook in `HistoryStack`): anhalten,
in AD-021 begründen (CORE_V1_FREEZE §7 Schritte 1–6), Manu fragen.

## 6. Tests

- Während der Arbeit gezielt (AGENTS.md §8a). Neue Tests in `tests/test_application_objects.py` (oder je Slice eine
  Datei `tests/test_object_transform*.py`), Viewport-Teile in `tests/test_viewport_object_entries.py`.
- Vor jedem Push: `xvfb-run -a python -m pytest tests -q`, `… playground/tests -q`, `… experiments/symmetry_lab/tests -q`
  — **`xvfb-run -a python -m pytest`, nicht das nackte `pytest`** (läuft ohne pyglet). Im Container zuerst
  `pip install -r requirements-dev.txt`; fehlt EGL, `apt-get install -y libegl1`, sonst werden Fenster-Tests übersprungen.
- Erwartung: Baseline (oben) plus neue Tests; der eine bekannte Fehlschlag bleibt der einzige.
- Pro sichtbarem Slice ein GL-Rauchtest unter xvfb mit Screenshot im Scratchpad (wie in M1, AD-021 §6.1 „Observed").

## 7. Doku (im selben Commit wie der Code)

AD-021: Decision Record, je Slice eine Umsetzungsnotiz (§6.2 …, Muster §6.1), §7 Fragen aktualisieren, Kurzfassung mit
Praxistest auf Deutsch. AD-SYM-04 + `symmetry_axis.py` (Q-7, in M2-2). AD-012 (Satz: `local` = Objektachsen, verdrahtet
nicht). AD-018 (Model-Matrix als deklarierte Uniform, E-9). `docs/ATELIER.md` (Fähigkeiten-Tabelle, §2 B, D1d),
`ROADMAP.md` ARCH-01, `docs/architecture/README.md`, `WP-06_INTAKE_LOG.md`, `src/main.py`-Docstring, `src/README.md`.

## 8. Abnahme

Je Slice: Tests grün wie oben, Rauchtest-Screenshot, Doku. Danach **Manus Praxistest** (M2-0 und M2-2 sind die beiden,
die er unbedingt sehen muss; M2-1 ist unsichtbar). Kein Agent behauptet Artist-Validierung oder promotet (`PROVISIONAL`
bleibt, bis Manu verdiktet).

## 9. Bei Widerspruch

Anhalten und melden statt still weiterbauen, wenn: ein Gate offen ist; E-2/E-7/E-9 sich als falsch herausstellen (z. B.
ein Konsument liest die Kamera auf einem Weg, den der Adapter nicht abdeckt); eine Core-Änderung nötig wird; ein
bestehender Test geändert werden müsste, der nicht Teil von M1/M2 ist; Picking oder Soft auf einem transformierten Objekt
nicht bitgleich bzw. gleich zu ohne Transform werden; eine Ableitung in diesem Handoff (RD-3 für `NORMAL`-Objekte,
Apply-Ablehnung bei Symmetrie) im Rauchtest falsch wirkt.
