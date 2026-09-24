# Handoff: WP-SYM-LAB-01 — Slice 4 (Hover-Ziel für Move + symmetrische Anzeige-Triangulierung)

**An:** Claude Code
**Modell/Effort:** Sonnet, effort `high`
**Modus (M5):** Production — Entscheidungen stehen in §2, jetzt wird zuverlässig umgesetzt.
**BUILD darf keine neue Erkenntnis behaupten.** Wenn beim Implementieren etwas
unerwartet anders aussieht als hier beschrieben, nicht still weiterbauen — anhalten
und melden (siehe „Bei Widerspruch" am Ende).

**Stand:** Slice 3 gemergt als `5c04c5a`, von Manu im Lab benutzt (Screenshot 2026-09-25:
Ebene, Seam, Auswahl + gespiegelter Partner sichtbar).

---

## 1. Referenzdokumente (gelten, nicht neu verhandeln)

- `docs/architecture/WP-SYM-LAB-01_SLICE2_CLAUDE_CODE_HANDOFF.md` §2 — kein Import aus
  `playground/`, Lab besitzt seinen Draw-Pfad.
- `docs/architecture/WP-SYM-LAB-01_SLICE3_CLAUDE_CODE_HANDOFF.md` — alle dortigen
  Entscheidungen (A1/A2, E1–E6) gelten weiter, außer wo §2 hier sie ausdrücklich erweitert.
- Commit `6c50eba` (WP-STAB-04) — Referenz für die Selection-or-Hover-Regel im Playground.
  Lesen, nicht importieren.
- `docs/research/symmetry/SYMMETRY_DESIGN_BRIEF.md` — INV-11 (Vorschau vor dem Bestätigen).
- `docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md` — neue Idee zuerst im
  Experiment, Promotion nur per expliziter Entscheidung.

## 2. Entscheidungen

### Artist (Manu, 2026-09-25)

- **A3 — Hover > Q > LMB-Drag.** Der Artist zeigt auf einen Vertex, drückt Q und zieht mit
  LMB, ohne vorher zu klicken.
- **A4 — Ziel-Regel wie im Playground (WP-STAB-04):** Auswahl nicht leer → die Auswahl
  bewegt sich. Auswahl leer → der Vertex unter dem Cursor (Hover) ist das Ziel. Beides leer
  → Q wird abgelehnt (Statuszeile), nichts wird scharf.

### Engineering (in diesem Handoff festgelegt)

- **E7 — Ziel wird beim Drücken von Q festgelegt** und bleibt bis Commit/Cancel fest.
  Späteres Wegbewegen der Maus vor dem LMB-Press ändert das Ziel nicht.
- **E8 — Hover-Ziel ist temporär und berührt `scene.selection` nicht.** Es wird nur als
  `vertex_ids` an `MoveTool.begin()` übergeben. Nach Commit/Cancel ist die Auswahl genauso
  wie vorher (leer). Abweichung vom Playground, der ein Temp-Target in die Auswahl schreibt
  und wieder entfernt — hier unnötig, weil das Lab `vertex_ids` direkt übergibt.
- **E9 — Hover-Anzeige:** Vertex unter dem Cursor wird hervorgehoben (eigene Farbe), bei
  aktiver Symmetrie zusätzlich sein gespiegelter Partner (INV-11, gleiche Vorschau wie bei
  der Auswahl, über `mirrored_selection`). Hover wird nur im Leerlauf und bei scharfem Move
  aktualisiert, nicht während eines Drags (Kamera oder Move).
- **E10 — Symmetrische Anzeige-Triangulierung, nur im Lab:** Befund (verifiziert): Die
  Production-Fan-Triangulierung (`viewport.derived.triangulate_face`) wählt die
  Quad-Diagonale nach gespeicherter Vertex-Reihenfolge. `subd_cube` X: alle 24 gespiegelten
  Quad-Paare haben asymmetrische Diagonalen; mit „kürzere Diagonale" 0. `head_basemesh` X:
  0 bzw. 0. Das Lab trianguliert deshalb zum Zeichnen:
  - Quads: an der kürzeren Diagonale (Abstände sind spiegelinvariant). Bei exakt gleicher
    Länge: bisheriges Fan-Verhalten.
  - Dreiecke und n-Gons: unverändert `triangulate_face`.
  - Normalen ebenfalls lab-lokal: Heute kommen sie aus `DerivedGeometry`, deren
    Face-Normale das erste Fan-Dreieck ist — das bliebe asymmetrisch. Im Lab: Face-Normale
    nach Newell (unabhängig vom Start-Vertex, spiegeläquivariant), Vertex-Normale =
    normierte Summe der angrenzenden Face-Normalen (gleiches Schema wie `DerivedGeometry`).
  - Grenze, dokumentieren, nicht lösen: Ein Quad, das selbst über die Ebene reicht, kann
    prinzipiell nicht symmetrisch in zwei Dreiecke geteilt werden.
  - Keine Änderung an `src/viewport/derived.py`. Eine Übernahme nach Production ist eine
    spätere, eigene Entscheidung (betrifft Playground, Picking, Normal-Space).

## 3. Ziel dieses Slices

Der Artist sieht, welcher Vertex unter dem Cursor liegt (und bei Symmetrie seinen Partner),
kann ihn per Q + LMB-Drag direkt verschieben, und die Schattierung des Meshes ist bei
symmetrischen Meshes auch symmetrisch.

## 4. Scope

1. Hover: `on_mouse_motion` im Fenster → Dispatcher → `pick_nearest_vertex` (Production).
   Hover-Zustand im Dispatcher (GL-frei, testbar). Overlay nur neu aufbauen, wenn sich der
   Hover-Vertex tatsächlich ändert.
2. Q (A4, E7, E8): `_arm_move` löst das Ziel auf: Auswahl → sonst Hover → sonst ablehnen.
   Das festgelegte Ziel wird beim LMB-Press an `begin_current_interaction` übergeben.
   Statuszeile zeigt, was sich bewegen wird („Auswahl" / „Hover v<id>").
3. Anzeige (E9): Hover-Farbe + Partner-Vorschau; README-Farblegende ergänzen.
4. Triangulierung + Normalen (E10) in `lab_draw_data.py` (oder eigenem Lab-Modul), mit
   Herkunfts-/Abweichungsvermerk im Docstring.

## 5. Not in scope

- Hover für Edges/Faces, Mehrfachauswahl, Rotate/Scale.
- Änderungen an `src/**` (auch nicht an `triangulate_face` oder `DerivedGeometry`).
- Änderungen an der Move-Geste über A3/A4 hinaus (one-shot aus E5 bleibt).

## 6. Must NOT change (Diff muss hier leer sein)

- `src/**`, `playground/**`, `tools/**`, `examples/**`, Tests außerhalb von
  `experiments/symmetry_lab/tests/`.

Erwarteter Diff: nur Dateien unter `experiments/symmetry_lab/` (inkl. README) und dieses
Handoff-Dokument.

## 7. Erwartete Tests (headless)

- Ziel-Regel: Auswahl vorhanden + Hover auf anderem Vertex → Q → Drag bewegt die Auswahl;
  Auswahl leer + Hover → Q → Drag bewegt den Hover-Vertex (und bei Symmetrie seinen
  Partner), ein History-Eintrag, Auswahl danach weiterhin leer; beides leer → Q abgelehnt,
  nicht scharf.
- E7: Nach Q den Hover auf einen anderen Vertex setzen, dann Drag → das beim Q festgelegte
  Ziel bewegt sich.
- Cancel mit Hover-Ziel: ESC während Drag → exakter Vorzustand, Auswahl leer, kein
  History-Eintrag.
- Hover-Update: während eines Kamera- oder Move-Drags ändert sich der Hover nicht.
- Triangulierung (Charakterisierung): `subd_cube` X → 24 gespiegelte Quad-Paare, 0 mit
  asymmetrischer Diagonale; `head_basemesh` X → 0.
- Normalen: Für jedes gepaarte Vertex-Paar ist die Normale des Partners das Spiegelbild
  (Vergleich mit kleiner Float-Toleranz im Test ist hier zulässig — das ist Anzeige, nicht
  die Capability).
- Alle bisherigen Lab-Tests und die Import-Grenze bleiben grün.

## 8. Done-Kriterien

- Lab-Tests grün; Produktions-Suite unverändert grün
  (`pytest tests --ignore=tests/test_extrude_tool.py`).
- `git diff --stat` enthält nur Dateien aus §6 „Erwarteter Diff".
- README: Steuerung (Hover > Q > LMB-Drag), Ziel-Regel, Farblegende, Abschnitt zur
  Anzeige-Triangulierung inkl. Grenze, Prüfanleitung für Manu. Keine Artist-Validierung
  behaupten.
- Commit-Message-Vorschlag: `WP-SYM-LAB-01 Slice 4: hover target for Move, symmetric
  display triangulation`

## 9. Bei Widerspruch

Anhalten und melden, nicht still lösen, insbesondere wenn:

- die Zahlen aus E10/§7 (24 → 0, head 0) nicht reproduzierbar sind,
- sich symmetrische Normalen nur über eine Änderung an `src/` erreichen lassen,
- `MoveTool` mit `vertex_ids`, die nicht der Auswahl entsprechen, anders reagiert als
  erwartet (z. B. Partner nicht mitbewegt),
- irgendetwas nur über Import aus `playground/` lösbar scheint.
