# Work Package: Playground-Werkzeuge in die App (2026-10-15)

**Status:** Umgesetzt (2026-10-15) — `PROVISIONAL`, Verdikt offen bis zu Manus Praxistest (unten).
**Modus (M5):** Production. Promotion durch Manu (M3), im Chat 2026-10-15: „die Playground-Werkzeuge
in Production einbauen“, Auswahl: Box-Select, Loop-Werkzeuge, Tweak, Paint Select.

## Entscheidungen (Manu, Chat 2026-10-15)

| # | Frage | Antwort |
|---|---|---|
| P-1 | Welche Werkzeuge? | Box-Select, Loop-Werkzeuge (Loop/Ring-Auswahl, Loop Insert, Loop Slide), Tweak (Silo), Paint Select. Articulation nicht. |
| P-2 | Box und Paint teilen sich LMB-Ziehen — wie? | **Startpunkt entscheidet:** Start im leeren Raum = Box, auf dem Mesh = Malen; ohne Taste neu, Shift dazu. Der Wings-Zusatz des Box-Verdikts (Box mit Modifier im Mesh) entfällt. |
| P-3 | Tweak (Silo, Ctrl+LMB) kollidiert mit Ctrl = Entfernen | **Ctrl+LMB, Auswahl weicht:** Ctrl+LMB-Ziehen = Tweak; Ctrl+LMB-Klick bleibt Entfernen; Entfernen per Box/Malen gibt es nicht. |

Quellen der Verdikte: Box KEEP in [`selection/decision.md`](../playground/experiments/selection/decision.md),
Tweak V2 KEEP in [`tweak_decision.md`](../playground/experiments/tweak/tweak_decision.md); Paint war dort nur
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
  gleitet die Spiegelseite exakt mit, ein Loop *auf* der Spiegelebene wird abgelehnt.
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

**Status:** Umgesetzt (2026-10-21) — `PROVISIONAL`, Praxistest unten. Entscheidungen Manu (Chat 2026-10-21): „Gizmo nach `src/` heben“,
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

Fragen an dich (nur falls es sich falsch anfühlt): Ist `Q` halten für Lasso richtig? Soll das Gizmo während des Ziehens sichtbar bleiben?

