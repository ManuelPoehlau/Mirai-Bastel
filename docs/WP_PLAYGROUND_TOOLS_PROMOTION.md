# Work Package: Playground-Werkzeuge in die App (2026-10-15)

**Status:** Umgesetzt (2026-10-15) — `PROVISIONAL`, Verdikt offen bis zu Manus Praxistest (unten).
**Modus (M5):** Production. Promotion durch Manu (M3), im Chat 2026-10-15: „die Playground-Werkzeuge
in Production einbauen“, Auswahl: Box-Select, Loop-Werkzeuge, Tweak, Paint Select.

## Entscheidungen (Manu, Chat 2026-10-15)

| # | Frage | Antwort |
|---|---|---|
| P-1 | Welche Werkzeuge? | Box-Select, Loop-Werkzeuge (Loop/Ring-Auswahl, Loop Insert, Loop Slide), Tweak (Silo), Paint Select. Articulation nicht. |
| P-2 | Box und Paint teilen sich LMB-Ziehen — wie? | **Startpunkt entscheidet:** Start im leeren Raum = Box, auf dem Mesh = Malen; ohne Taste neu, Shift dazu. Der Wings-Zusatz des Box-Verdikts (Box mit Modifier im Mesh) entfällt. |
| P-3 | Tweak (Silo, Ctrl+LMB) kollidiert mit Ctrl = Entfernen | **Ctrl+LMB, Auswahl weicht:** Ctrl+LMB-Ziehen = Tweak; Ctrl+LMB-Klick bleibt Entfernen; Entfernen per Box/Malen gibt es nicht. **Abgelöst 2026-10-28** (Manu A3): Ctrl+LMB-Ziehen ist entfernt, „Tweak“ heißt jetzt die Halte-Geste W/E/R + Maus — siehe [Nachtrag 2026-10-28](#nachtrag-2026-10-28-achse-einmalig-tweak--halte-geste-gizmo-kleiner-manu). |

Quellen der Verdikte: Box KEEP in [`selection/decision.md`](archive/experiments_2026-10/playground/experiments/selection/decision.md),
Tweak V2 KEEP in [`tweak_decision.md`](archive/experiments_2026-10/playground/experiments/tweak/tweak_decision.md); Paint war dort nur
geplant, Loop-Werkzeuge hatten kein Verdikt (Tasten aus der Artist Input Truth,
`tools/Input_Mapping_Tool/artist_input_truth.json`).

## Engineering-Annahmen (`PROVISIONAL`, korrigierbar in einem Satz)

- **Tweak-Transform** = das zuletzt gedrückte W/E/R (ein Antippen setzt es, Start: Move). Die App hat
  W/E/R als Halte-Tasten (AD-016), keinen persistenten Modus.
- **Tweak-Ziel:** Auswahl (wirkt überall auf dem Bildschirm), sonst das Element unter dem Press-Punkt;
  die Auswahl selbst ändert sich nicht. In Modus `4` bewegt Tweak die ausgewählten Objekte (wie W/E/R).
- **Box:** ein Element zählt, wenn alle seine Ecken im Rechteck liegen (Playground-Regel); bei sichtbaren
  Flächen nur, was man sieht (gleiche Verdeckung wie beim Klick). Box/Malen nicht in Modus `4`.
- **Malen:** Pick-Punkte alle 6 px entlang der Mausbewegung; Esc stellt die Auswahl von vor dem Strich her.
- **Loop-Werkzeuge** nur im Edge-Modus; Ausgangspunkt = ausgewählte Kanten, sonst die gehoverte.
  Shift+L / Shift+R fügen Loop / Ring zur Auswahl hinzu. I = Loop Insert durch den Ring (über dasselbe
  Edge Connect wie `C`, daher unter Symmetrie gespiegelt). G halten = Loop Slide: offene Loop-Stücke und
  mehrere Loops gleiten mit; die Maus folgt der Richtung der Kanten auf dem Bildschirm; unter Symmetrie
  gleitet die Spiegelseite exakt mit, ein Loop *auf* der Spiegelebene wird abgelehnt. Fix 2026-10-29: unter
  Symmetrie stoppt der Slide bei 98 % (ganz bis zur Nachbar-Loop lagen zwei Punkte aufeinander, die Spiegelpaarung
  wurde still mehrdeutig). Im Vertex-Modus ist `G` seit 2026-10-29 Vertex Slide ([WP_INSET_BEVEL_SLIDE.md](WP_INSET_BEVEL_SLIDE.md)).
- Loop Slide in `src` ist neu gebaut (`mirai.topology.loop_slide`); der Playground behält sein
  `LoopSlideTool` (nur geschlossene Loops). Loop/Ring-Erkennung ist verschoben (eine Implementierung).

Code: `src/mirai/application.py` (Box/Paint, Tweak, Loop-Werkzeuge), `src/mirai/viewport/box_select.py`,
`src/mirai/topology/loop_ring.py`, `src/mirai/topology/loop_slide.py`, Gummiband in `src/main.py`.
Tests: `tests/test_application_drag_select_tweak.py`, `tests/test_application_loop_tools.py`,
F-a-Wächter `tests/test_symmetry_fail_closed_guard.py`.

## Praxistest für Manu (ca. 10 Minuten)

Start: `python src/main.py` (Head).

| # | Was tun | Worauf achten | Verdikt |
|---|---|---|---|
| T1 | `1`, im leeren Raum LMB ziehen (über den Kopf), loslassen; dann Shift+Ziehen woanders | Gummiband sichtbar; nur sichtbare Punkte gewählt; Shift fügt hinzu | KEEP |
| T2 | `3`, auf dem Kopf LMB ziehen (malen); mit Shift weitermalen; einmal mitten im Strich `Esc` | Strich wählt Flächen unter dem Cursor; schnelle Bewegung lässt nichts aus; Esc = wie vorher | KEEP |
| T3 | `1`, nichts gewählt: Ctrl+LMB auf einem Punkt ziehen. Dann `E` antippen, Auswahl treffen, Ctrl+Ziehen irgendwo | Tweak verschiebt den Punkt, ein Undo-Schritt; nach `E` dreht Tweak die Auswahl | KEEP |
| T4 | Ctrl+Klick auf einen gewählten Punkt | entfernt ihn weiterhin | KEEP |
| T5 | `2`, Kante hovern, `Shift+L`, dann `Shift+R` | Loop bzw. Ring kommt zur Auswahl | Iterate |
| T6 | `2`, Kante hovern, `I`; dann `G` halten und Maus bewegen, loslassen | neuer Loop, danach gleitet er entlang der Kanten; je ein Undo-Schritt | ITERATE — Hält man I gedrückt, wird der Loop eingefügt und lässt sich direkt sliden |
| T7 | `Shift+S` (Symmetrie X), dann T6 auf einer Seite | Gegenseite macht mit | KEEP |

Die folgenden Antworten von Manu (2026-10-15) sind bestätigt:
- „Ist ‚zuletzt gedrücktes W/E/R‘ für Tweak richtig?“ — **Ja**
- „Soll `Shift+L` die Auswahl ersetzen statt erweitern?“ — **Erweitern**

---

## Nachtrag 2026-10-21: Lasso und Gizmo in die App (Manu)

**Status:** Umgesetzt (2026-10-21) — `PROVISIONAL`, Praxistest unten. Gizmo seit 2026-10-22 erweitert (Mittelkreis, Dial, Shift/Ctrl, Cursor-Wrap; **Keep** Manu, Finetuning später): siehe die beiden Nachträge 2026-10-22 unten — wo sie dem Absatz „Engineering-Annahmen“ widersprechen (Scale-Mitte als Kreuz, Rotate nur dx), gelten sie. Entscheidungen Manu (Chat 2026-10-21): „Gizmo nach `src/` heben“,
„Lasso kommt auch in die Production (Box und Paint sind auch schon dort)“, „Articulation bleibt erstmal im Playground“,
„Knife ist kein Playground-Thema mehr“, Deformer/Modifier (Bends, Twists, Lattices) später
([future_ideas/MODELING.md](future_ideas/MODELING.md)).

**Engineering-Annahmen (`PROVISIONAL`, korrigierbar in einem Satz):**
- **Lasso:** Taste **`Q` halten** + LMB ziehen (Artist Input Truth `selection.lasso_select` ist leer, `Q` war frei; keymap.json kann umbinden).
  Egal wo der Startpunkt liegt (auch auf dem Mesh), ohne Modifier ersetzt, Shift fügt hinzu, `Esc` verwirft. Regel wie Box: ein Element zählt,
  wenn alle seine Ecken im Umriss liegen (gerade Linie vom letzten zum ersten Punkt schließt ihn, gerade-ungerade bei Selbstüberschneidung),
  bei sichtbaren Flächen nur, was man sieht. Weniger als 3 Umrisspunkte: nichts ändert sich. Keine History, nicht in Modus `4`.
- **Gizmo (AD-016 D3):** bei Punkt-/Kanten-/Flächen-Auswahl im Schwerpunkt der Auswahl, Form je Werkzeug (zuletzt gedrücktes `W`/`E`/`R`,
  Start Move): Move = Linien + Pfeil, Rotate = Ringe, Scale = Linien + Würfel + Mitte. Nur Welt-Achsen (Normalenraum gibt es in der App nicht).
  LMB-Klick (ohne Modifier) auf einen Griff setzt nur die Constraint (wie `X`/`Y`/`Z`), Ziehen führt das Werkzeug entlang der Achse aus,
  Loslassen commitet (ein Undo-Schritt), `Esc` bricht ab; ein Treffer hat Vorrang vor dem Auswahl-Klick, ein Fehltreffer läuft wie bisher.
  Scale-Mitte = gleichmäßig, ohne Constraint. Während einer Geste und bei `W`/`E`/`R` gehalten ist das Gizmo ausgeblendet. Nur im Fenster von
  `src/main.py` (`gizmo_enabled`), die Labs bekommen keine unsichtbaren Griffe. Aussehen/Größen wie im Playground.

Code: `src/mirai/viewport/gizmo.py` (Geometrie, Picking, Zeichen-Primitive), `src/mirai/application.py` (Lasso, Gizmo-Geste),
`src/viewport/gl_gizmo_overlay.py`, `src/main.py` (Zeichnen). Tests: `tests/test_application_lasso.py`, `tests/test_viewport_gizmo.py`,
`tests/test_application_gizmo.py`, `tests/test_gl_gizmo_overlay.py`.

### Praxistest für Manu (ca. 5 Minuten)

Start: `python src/main.py` (Head).

| # | Was tun | Worauf achten | Verdikt |
|---|---|---|---|
| L1 | `1`, `Q` halten, im Leeren einen Umriss um mehrere Punkte ziehen (auch quer über den Kopf), loslassen | Umriss sichtbar; nur sichtbare Punkte; `Q` loslassen = wieder Box/Malen | |
| L2 | `3`, `Q` halten, Shift+Umriss woanders; dann einmal `Esc` mitten im Umriss | Shift fügt hinzu; `Esc` verwirft | |
| G1 | Ein paar Punkte wählen, auf eine Gizmo-Achse klicken, dann `X`/`Y`/`Z` drücken | Klick = Constraint, Auswahl bleibt; Taste schaltet dieselbe Constraint | |
| G2 | Auf eine Achse klicken und ziehen, loslassen; `Ctrl+Z` | bewegt nur entlang der Achse, ein Undo-Schritt | |
| G3 | `E` antippen (Ringe), `R` antippen (Scale-Mitte ziehen = gleichmäßig) | Form wechselt mit dem Werkzeug; Mitte skaliert gleichmäßig | |
| G4 | Mittelkreis ziehen bei `W` (frei), `E` (Trackball), `R` (gleichmäßig); bei `E` den äußeren Ring ziehen | Move frei in der Bildebene, Trackball folgt der Mausrichtung, äußerer Ring dreht um die Blickachse | Keep (2026-10-22) |
| G5 | Einen Ring (oder `E` halten / Ctrl+LMB) mit dem Cursor um den Pivot kreisen; mit Shift (fein), mit Ctrl (5°-Raster) | Greifpunkt klebt am Cursor, nahe am Pivot dreht es schneller; Shift/Ctrl wirken ohne Sprung | Keep (2026-10-22) |
| G6 | Beim Ziehen (Move, Rotate, Scale) über den Fensterrand fahren | Zeiger erscheint auf der Gegenseite, die Geometrie springt nicht | Keep (2026-10-22) |

Fragen an dich (nur falls es sich falsch anfühlt): Ist `Q` halten für Lasso richtig? Soll das Gizmo während des Ziehens sichtbar bleiben?

### Nachtrag 2026-10-22: weißer Mittelkreis und Blender-artiges Ring-Drehen (Manu)

**Status:** Umgesetzt, **Keep** (Manu, 2026-10-22; Finetuning später) — `PROVISIONAL` (Faktoren: `RADIANS_PER_PIXEL`, `CENTER_RING_RATIO`, `SCREEN_RING_RATIO`, `GRAZING_COS` in `interaction/dial.py`).
Wunsch Manu: wie in Blender in der Mitte ein weißer Kreis in allen Werkzeugen (ohne Constraint), und Rotate soll sich beim Ziehen natürlich anfühlen.

- **Mittelkreis** (Handle `center`, alle drei Werkzeuge, ersetzt das Scale-Kreuz): Move = freies Verschieben (Kamera-Ebene), Rotate = Trackball,
  Scale = gleichmäßig. Rotate hat zusätzlich den äußeren Ring `screen` (jetzt greifbar): Drehung um die Blickachse.
- **Ring-Drehen = Blenders Dial** (`dial3d_gizmo.cc`, `dial_ghostarc_get_angles`): Cursor bei Press und aktuell werden per Ray auf die Ringebene
  (Pivot, Achse) gelegt, der Winkel dazwischen um die Achse ist die Drehung, volle Umdrehungen werden mitgezählt. Dadurch klebt der Greifpunkt am
  Cursor, die Richtung ist die Tangente am Ring, und je näher der Cursor am Pivot ist, desto mehr Grad pro Pixel. Steht der Ring (fast) kantenparallel
  zur Sicht (|cos| < 0,12 beim Press), gilt für die Geste der Cursor-Versatz entlang der Bildschirm-Tangente / Ring-Radius in Pixeln.
- **Trackball** (`transform_mode_trackball.cc`): Mausversatz seit Start `phi`, Achse `up*phi.x - right*phi.y` der beim Start eingefrorenen Kamera,
  Winkel `|phi| * RADIANS_PER_PIXEL`; absolut ab Start, daher unabhängig vom Event-Chunking. Mit Seam-Vertices (Symmetrie) abgelehnt.
- R-Taste / Tweak ohne Gizmo: in dieser Runde unverändert, seit Runde 2 ebenfalls Dial. Shift / Ctrl: Runde 2.
- Playground: `playground/gizmo.py` nutzt weiter den alten Griffsatz (`pick_handle(free_handles=False)`).
Code: `viewport/gizmo.py`, `interaction/tools/rotate.py` (`begin(gizmo=...)`), `application.py` (`_rotate_gesture_mode`), `viewport/camera.py` (`ray_plane_point`).
Tests: `tests/test_rotate_dial.py`, `tests/test_viewport_gizmo.py`, `tests/test_application_gizmo.py`.

### Nachtrag 2026-10-22 (Runde 2): Dial überall, Shift/Ctrl, Cursor-Wrap (Manu)

**Status:** Umgesetzt, **Keep** (Manu, 2026-10-22; Finetuning später) — `PROVISIONAL` (`PRECISION_GAIN`, `SNAP_STEP`, `SNAP_STEP_PRECISE`, `FALLBACK_MIN_RADIUS_PX`, `MIN_PRESS_RADIUS_PX`, Wrap-Ränder).
- **Dial für jede Rotate-Geste** (Entscheidung Manu: „beide an Dial angleichen“): E-Taste gehalten, Tweak (Ctrl+LMB) und Gizmo-Ring drehen über `interaction/dial.py` (`DialAngle`),
  auch Rotate im Objekt-Modus. Press-Punkt = Cursor beim Arm. Die Drehung ist der Cursor-Winkel um den Pivot (Cursor im Uhrzeigersinn = Drehung im Uhrzeigersinn
  auf dem Bildschirm). Liegt der Press-Punkt näher als 20 px am Pivot oder steht die Ebene kantenparallel zur Sicht, gilt der Tangenten-Fallback (Hebelarm mindestens 100 px
  = ca. 0,57°/px, Press genau auf dem Pivot: Ziehen nach rechts = im Uhrzeigersinn, wie das alte dx-Rotate). Ohne Cursor (Tool direkt benutzt) bleibt das dx-Rotate.
- **Shift = Präzision** (Winkel × 0,2, stetig beim Umschalten; Move/Scale: dx/dy × 0,2; Trackball × 0,2). **Ctrl = Snap** beim Dial: 5°, mit Shift 1°; wirkt sofort beim Drücken.
  Ctrl+LMB-Tweak startet mit gehaltenem Ctrl, deshalb snappt der Tweak erst, nachdem Ctrl einmal losgelassen und neu gedrückt wurde. `Application.set_shift_held` / `set_ctrl_held`, gespeist aus `src/main.py`.
- **Cursor-Wrap** (`mirai/cursor_wrap.py`, `CursorWrapper`): während eines Transforms (`Application.cursor_wrap_active`) springt der Zeiger am Fensterrand auf die Gegenseite
  (`window.set_mouse_position`); das vom Warp ausgelöste Ereignis wird geschluckt. Alle Gesten laufen auf Deltas (der Dial integriert sie zu einem virtuellen Cursor), daher gibt es keinen Sprung.
  Ohne Warp-Unterstützung der Plattform (z. B. Wayland) schaltet sich der Wrap ab. Der Baustein ist für spätere Slider-Drags gedacht (gleiche Bedingung `cursor_wrap_active` bzw. ein eigener Gate).
  **Fix 2026-10-22 (Geometrie sprang beim Wrap):** Pyglets `dx`/`dy` hängen an seiner eigenen letzten Position, und vor dem Warp gequeute Ereignisse tragen noch die alte Randposition.
  `CursorWrapper.filter` rechnet nach einem Warp die Deltas selbst aus den Positionen, verwirft veraltete Ereignisse am alten Rand (40 px, 0,25 s) und löst währenddessen keinen zweiten Warp aus.
Tests: `tests/test_rotate_dial.py`, `tests/test_cursor_wrap.py`.

## Nachtrag 2026-10-28: Achse einmalig, Tweak = Halte-Geste, Gizmo kleiner (Manu)

**Status:** Umgesetzt (2026-10-28) — Discovery, `PROVISIONAL`, Praxistest unten. Ziel (Manu): vergessene
Achsen-Sperren sollen die Hauptgeste (hovern + `W`/`E`/`R` halten + Maus) nicht mehr stören.

**Entscheidungen Manu (2026-10-28):** A1 Achsen-/Ebenen-Constraint (`X`/`Y`/`Z`, `Shift+X/Y/Z`) gilt für **eine** Geste,
dann ist sie weg — zu testen gegen das bisherige „sticky“. A2 Die Halte-Geste (`W`/`E`/`R` halten + Maus) heißt in allen
Texten **Tweak**; Verhalten unverändert. A3 Ctrl+LMB-Ziehen (Tweak, Eintrag in `config/keymap.json` vom 2026-10-15) ist
entfernt; Ctrl+LMB-Klick (Entfernen) bleibt. A4 Gizmo kleiner, Bildschirmgröße beim Zoomen konstant (war schon so),
zuverlässiges Picken mit Geometrie dahinter, Mittelkreis per Hover treffbar. A5 Hover auf dem Griff, der schon die aktive
Constraint ist, muss sichtbar sein.

**Engineering (`PROVISIONAL`, korrigierbar in einem Satz):**
- **One-shot (E1):** Eine Constraint, die vor dem Beginn der Geste gesetzt wird (auch bei gehaltenem, noch nicht bewegtem
  `W`/`E`/`R`), gilt für diese Geste. Der **Commit** räumt sie, `Esc` und ein bloßes Antippen behalten sie. Wird während
  einer laufenden Geste eine Achsentaste gedrückt, gilt sie (wie bisher) erst für die nächste Geste, und der Commit der
  laufenden lässt sie stehen. Eine Geste, die die Achse gar nicht nutzt (Objekt-Scale ist immer gleichmäßig; Extrude,
  Loop Slide, Smooth), räumt sie nicht. Statuszeile beim Commit: „… (constraint X) · free again (one-shot)“.
- **Gizmo-Griff (E2):** Ziehen am Griff gilt nur für diesen Zug (danach frei; `Esc` stellt wieder her, was vor dem Klick
  anstand). Ein Klick ohne Ziehen setzt die One-shot-Constraint wie `X`.
- **Sitzungs-Schalter** (nur für diesen Test, nicht gespeichert, Tasten `PROVISIONAL`): **`F7`** = Constraints one-shot ↔
  sticky (Start: one-shot; sticky = das Verhalten bis heute, auch am Gizmo). **`F8`** = Gizmo-Größe **M → L → S** (Start M).
  HUD-Zeile „Axis“ zeigt die Variante („X · one-shot“, „free · sticky“), die Statuszeile die Größe.
- **Gizmo-Größen (A4):** S / M / L = 0,07 / 0,10 / 0,13 der Kameradistanz (bisher 0,18; M ≈ 55 % der alten Größe, bei
  1080 px Fensterhöhe eine Achse von etwa 115 px). Bleibt beim Zoomen gleich groß auf dem Bildschirm.
- **Picken (E3):** Liegt der Cursor in der Pick-Zone eines Griffs, gewinnt der Griff: kein Mesh-Hover darunter (vorher
  leuchtete das Mesh dahinter mit auf, und es sah aus, als würde der Klick auswählen). Der Mittelkreis ist eine **gefüllte**
  Fläche (Kreis + 4 px, mindestens 10 px Radius): darin gewinnt immer `center`, auch gegen die Achslinien, die durch den Pivot
  laufen. Ringe werden entlang ihrer Segmente gepickt (bei großen Ringen gab es Lücken zwischen den Stützpunkten). AD-022
  (GPU-Picking) und der Tool-Vertrag („space fix ab `begin()`“) sind unberührt.
- **Hover (A5/E5):** Ursache war `draw_items`: der aktive Zustand überdeckte den Hover. Jetzt eigener Zustand „Hover auf
  aktiv“ (Strichbreite 5,5 statt 4, Hover-Farbe). Hover-Farbe = Grundfarbe 45 % Richtung Weiß (vorher ×1,4, auf Rot/Blau
  kaum sichtbar); der weiße Mittelkreis wird beim Hover warm-gelb.
- **Tweak (A2/A3/E4):** Die Halte-Geste heißt „Tweak“: Statuszeile beim Scharfschalten „Move: 3 vertices - Tweak: move the
  mouse, release W to commit“, HUD-Zeile „Tool“ während der Geste „Tweak · Move (running)“. Die Ergebnis-Zeilen („Move
  committed“) bleiben (sie nennen das Ergebnis, nicht die Geste). Die Gizmo-Ziehgeste heißt nicht Tweak. Der interne
  Mechanismus (LMB-Ziehen mit `TWEAK_KEY`, den das Gizmo nutzt) und der Command `Tweak` bleiben; er ist nur ungebunden.
  Ctrl+LMB-Ziehen tut jetzt nichts (kein Klick, keine Auswahländerung).

- **Fix Kugeldrehung (Manu, 2026-10-28: „zuckt nur kurz … bewegt sich dann nicht mehr“):** Mit Symmetrie und einer
  Soft-Zone über der Naht verlangt der Core pro Operation eine feste Drehachse (AD-SYM-05 §4.4); die Kugel (Mittelkreis bei
  Rotate) wechselt die Achse bei jedem Schritt, deshalb scheiterte der zweite Schritt und die Geste fror ein. Jetzt setzt die
  Kugel in diesem Fall bei jedem Schritt die Operation auf den Start zurück und wendet die ganze Drehung als einen Schritt an
  (`RotateTool`, `TransformTool._restart_operation`, derselbe Weg wie der Live-Radius). Naht bleibt auf der Ebene, Paare exakt
  gespiegelt, ein Undo-Schritt, unabhängig davon, wie der Zug in Ereignisse zerfällt (`tests/test_symmetric_soft_selection.py`).
  Kosten: 0,2–0,7 ms pro Schritt auf dem Kopf (Container-CPU, nicht der Referenz-PC). Der Core bleibt unverändert.

Code: `src/mirai/application.py` (`CONSTRAINT_MODES`, `_consume_constraint`, `_session_switch`, `_update_hover`,
`_gizmo_press`/`_cancel`), `src/mirai/viewport/gizmo.py` (`GIZMO_SIZES`, `center_pick_radius_px`, `hover_color`),
`src/mirai/interaction/bindings.py` (F7/F8, Ctrl+LMB-Ziehen entfernt), `src/mirai/pyglet_input.py` (F1–F12), `src/hud.py`,
`config/keymap.json`. Tests: `tests/test_application_transform.py`, `tests/test_application_gizmo.py`,
`tests/test_viewport_gizmo.py`, `tests/test_application_drag_select_tweak.py`, `tests/test_hud.py`.

### Praxistest für Manu (ca. 20–30 Minuten)

Start: `python src/main.py` (Head). Die HUD-Zeile „Axis“ zeigt, welche Variante läuft. `F7` = one-shot ↔ sticky,
`F8` = Gizmo-Größe — beides gilt nur bis zum Schließen.

| # | Was tun | Worauf achten | Verdikt |
|---|---|---|---|
| K1 | **„Achse vergessen“** (one-shot): einen Punkt wählen, `X` drücken, `W` halten und ziehen, loslassen. Dann nochmal mit `W` ziehen | 1. Zug nur entlang X, Statuszeile „… free again (one-shot)“, HUD „free“; 2. Zug frei | |
| K2 | Dasselbe nach `F7` (HUD „sticky“), danach `F7` zurück | sticky: 2. Zug wieder nur entlang X, bis du `X` erneut drückst. Was fühlt sich beim Formen besser an? | |
| K3 | `X` drücken, `W` halten, mit `Esc` abbrechen, nochmal ziehen; außerdem `X`, `W` nur antippen, dann ziehen | `Esc` und Antippen behalten X; erst der fertige Zug räumt es | |
| K4 | **Naht-Fall:** entlang einer Kontur (z. B. Lippenkante) fünf, sechs Punkte nacheinander, jedes Mal `X` + `W` ziehen. Danach dasselbe in sticky | Wie lästig ist das wiederholte `X`? Lieber sticky für solche Serien? | |
| K5 | **Gizmo-Größe:** ein paar Punkte wählen, `F8` mehrmals (M → L → S), dabei zoomen | Welche Größe passt (S / M / L)? Bleibt sie beim Zoomen gleich? | |
| K6 | **Picken mit Mesh dahinter:** Gizmo über dem Gesicht, langsam über Achsen, Ebenen-Winkel und den Mittelkreis fahren, dann klicken und ziehen | Unter einem Griff leuchtet kein Mesh-Element mehr; der Klick trifft den Griff, nie die Auswahl dahinter. Mittelkreis: überall innen treffbar (färbt sich gelb), Ziehen = frei (`W`), Trackball (`E`), gleichmäßig (`R`) | |
| K7 | **Aktive Achse hovern:** `X` drücken (X-Achse dick), dann mit der Maus über die X-Achse fahren; auch bei `E` (Ring) und `R` | Siehst du, dass du sie triffst (noch dicker, heller)? Andere Griffe: heller + dicker | |
| K8 | **Gizmo-Griff ziehen** (one-shot): `X` drücken, dann an der Y-Achse ziehen, loslassen, danach mit `W` ziehen. Auch: an einer Achse klicken ohne zu ziehen, dann `W` ziehen | Zug am Griff nur entlang Y, danach ist alles frei; Klick auf den Griff wirkt wie `X` für einen Zug | |
| K10 | **Kugeldrehung mit Symmetrie + Soft:** `Shift+S` (Symmetrie), `O` (Soft), Radius so groß, dass die Zone über die Mitte reicht, ein paar Punkte neben der Naht wählen, `E` antippen, am Mittelkreis ziehen | dreht durchgehend weiter (kein Zucken/Einfrieren), die Mitte bleibt auf der Ebene, ein `Strg+Z` | |
| K9 | **Ctrl+LMB:** Strg halten und auf dem Mesh ziehen; Strg-Klick auf einen gewählten Punkt | Ziehen tut nichts; Klick entfernt weiter aus der Auswahl. Fehlt dir Ctrl+LMB-Ziehen irgendwo? | |

Meine Lesart (bitte in einem Satz korrigieren, falls falsch): „eine Geste“ = ein fertiger Zug (Commit), nicht schon das
Antippen; `Esc` gibt die Achse zurück; eine Taste mitten im Zug ist für den nächsten Zug gedacht.

