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
| T1 | `1`, im leeren Raum LMB ziehen (über den Kopf), loslassen; dann Shift+Ziehen woanders | Gummiband sichtbar; nur sichtbare Punkte gewählt; Shift fügt hinzu | |
| T2 | `3`, auf dem Kopf LMB ziehen (malen); mit Shift weitermalen; einmal mitten im Strich `Esc` | Strich wählt Flächen unter dem Cursor; schnelle Bewegung lässt nichts aus; Esc = wie vorher | |
| T3 | `1`, nichts gewählt: Ctrl+LMB auf einem Punkt ziehen. Dann `E` antippen, Auswahl treffen, Ctrl+Ziehen irgendwo | Tweak verschiebt den Punkt, ein Undo-Schritt; nach `E` dreht Tweak die Auswahl | |
| T4 | Ctrl+Klick auf einen gewählten Punkt | entfernt ihn weiterhin | |
| T5 | `2`, Kante hovern, `Shift+L`, dann `Shift+R` | Loop bzw. Ring kommt zur Auswahl | |
| T6 | `2`, Kante hovern, `I`; dann `G` halten und Maus bewegen, loslassen | neuer Loop, danach gleitet er entlang der Kanten; je ein Undo-Schritt | |
| T7 | `Shift+S` (Symmetrie X), dann T6 auf einer Seite | Gegenseite macht mit | |

Offene Fragen an dich (nur falls es sich falsch anfühlt): Ist „zuletzt gedrücktes W/E/R“ für Tweak richtig?
Soll `Shift+L` die Auswahl ersetzen statt erweitern?
