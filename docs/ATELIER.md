# Mirai Atelier — Lagebild für den Artist

> **Status:** Artist-Übersicht (Index) (redaktionell abgeglichen am 2026-10-12; nicht Artist-validiert).
> **Zweck:** Manus Überblick in Artist-Sprache. Diese Seite ist ein **Index**, keine Wahrheit:
> Jede Zeile ist ein kurzer Satz plus Link. Was wirklich gilt, steht im verlinkten Dokument.
> Bei Widerspruch gewinnt immer das verlinkte Dokument, und diese Seite wird korrigiert.

---

## 1. Was Mirai heute kann

### In der Production-App (`python src/main.py [asset]`, Start mit dem Head-Basemesh)

| Bereich | Was geht | Wo es steht |
|---|---|---|
| Navigation | Orbit Alt+LMB, Pan Alt+Shift+LMB, Zoom Mausrad | [ROADMAP, WP-06 B2](architecture/ROADMAP.md) |
| Auswahl | Vertex/Edge/Face über `1`/`2`/`3`; Klick ersetzt, Shift fügt hinzu, Ctrl entfernt, Alt schaltet um | [ROADMAP, WP-06 B2/B5b](architecture/ROADMAP.md) |
| Transform | `W`/`E`/`R` halten und Maus bewegen = Move/Rotate/Scale; `X`/`Y`/`Z` (mit Shift: Ebene) als Achsen-Sperre zum Ein-/Ausschalten | [ROADMAP, WP-06 B3/B4/B4.1](architecture/ROADMAP.md) |
| Anzeige | `D` wechselt Shaded → Flat → Wireframe, `Shift+D` Drahtgitter darüber; Flat schattiert pro Polygon, Smooth ohne Dreiecks-Diagonale (2026-10-15) | [ROADMAP, WP-06 B5a](architecture/ROADMAP.md) · [Intake Log](architecture/WP-06_INTAKE_LOG.md) |
| Licht (`PROVISIONAL`, 2026-10-15) | Key + Fill aus dem Shading Lab, Start „Raitt 2:1“ mit der Kamera; `Strg+D` wechselt Raitt 2:1 → Softbox → Warm/Kalt → Heute, `Strg+Shift+D` Kamera ↔ Welt | [Intake Log](architecture/WP-06_INTAKE_LOG.md) · [Shading Lab README](../experiments/viewport_shading_lab/README.md) |
| Topologie `C` | je nach Auswahl Split, Edge Connect, Vertex Connect; ohne Auswahl startet das Knife | [AD-017](architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md) |
| Knife | Klick schneidet; Punkte in Flächen; Schnitt über mehrere Flächen; Punkte im leeren Raum; `E`/RMB = Stift abheben; Doppelklick schließt; Shift = Kantenmitte; `Enter` übernimmt, `Esc` bricht ab | [Knife-Entscheidungen](../playground/experiments/knife_face/decision.md) |
| Topologie Extrude | Face-Modus (`3`), Fläche(n) wählen (ohne Auswahl: die Fläche unter dem Cursor), `T` halten und Maus ziehen = Extrude, loslassen = fertig, `Esc` bricht ab; nach innen ziehen = Mulde mit Boden; ein Antippen oder Zittern tut nichts. **Praxistest bestanden, KEEP (2026-10-09), noch nicht PROMOTED** | [ROADMAP, WP-06 B9](architecture/ROADMAP.md) |
| Löschen | `Entf` = Delete, Rücktaste = Dissolve (mit Aufräumen), Ctrl+Rücktaste = Dissolve ohne Aufräumen | [WP Delete/Dissolve](WP_DELETE_DISSOLVE_PLAN.md) |
| Soft Selection (**Fähigkeit festgelegt**, Bedienung `PROVISIONAL`, standardmäßig aus) | Weiche Transform-Einflüsse auf Nachbarpunkte; Bedienung, Kurven, Radius und offene Grenzen sind in AD-020 dokumentiert. | [AD-020](architecture/AD-020-SOFT-SELECTION-APP-PATH.md) |
| Undo/Redo | `Ctrl+Z` / `Ctrl+Y` | [ROADMAP, WP-06 B3](architecture/ROADMAP.md) |
| Box / Paint / Tweak (`PROVISIONAL`, 2026-10-15) | LMB ziehen im leeren Raum = Box, auf dem Mesh = Auswahl malen (Shift = dazu, `Esc` verwirft); Ctrl+LMB ziehen = Tweak mit dem zuletzt gedrückten `W`/`E`/`R` | [WP Playground-Werkzeuge](WP_PLAYGROUND_TOOLS_PROMOTION.md) |
| Loop-Werkzeuge (`PROVISIONAL`, 2026-10-15) | Kanten-Modus: `Shift+L` / `Shift+R` = Loop / Ring dazu, `I` = Loop einfügen, `G` halten = Loop gleiten lassen; mit Symmetrie gespiegelt | [WP Playground-Werkzeuge](WP_PLAYGROUND_TOOLS_PROMOTION.md) |
| Szene laden (`PROVISIONAL`, temporär) | `Leertaste` öffnet am Cursor ein Menü mit `cube` und den Registry-Assets (u. a. dem großen `gollum`); Klick auf eine Zeile lädt die Szene, Klick daneben/`Esc`/`Leertaste` schließt. Die Taste ist ein Engineering-Vorschlag, noch kein Verdikt | [ROADMAP, Scene loader](architecture/ROADMAP.md) |
| Szene speichern / laden (`PROVISIONAL`, 2026-10-15) | `Strg+S` speichert die Szene (alle Objekte, Referenzen, Symmetrie) in den Ordner `scenes/` - in die zuletzt geladene/gespeicherte Datei, sonst in eine neue; im `Leertaste`-Menü oben: „Szene speichern“, „Als neue Szene speichern“ und die gespeicherten Szenen („Datei: …“) zum Laden. Auswahl, Undo-Verlauf und Kamera werden nicht gespeichert | [`src/scene_files.py`](../src/scene_files.py), [INPUT_WIRING_MAP §10](../INPUT_WIRING_MAP.md) |
| Zweites Objekt als Referenz (`PROVISIONAL`, M1, noch ohne Verdikt) | Im `Leertaste`-Menü **Shift+Klick** = Eintrag als Referenz *dazu* (gedämpftes Blau, Kamera bleibt); die Referenz leuchtet nie mit auf, man pickt durch sie hindurch; `4` = Objekt-Modus, Klick wählt ein Objekt (gelblich getönt), `Alt+R` schaltet Referenz ↔ normal (seit 2026-10-16, deine Rückmeldung; vorher schaltete der Klick); je ein Undo-Schritt. Seit M2-0: `Alt+D` = alle Referenzen durchscheinend (Ghost) ↔ schattiert; im Wireframe bleiben Referenzen sichtbar. Seit M2-2: in `4` ausgewählte normale Objekte mit `W`/`E`/`R` halten = verschieben/drehen/gleichmäßig skalieren (Objektebene, je ein Undo-Schritt, `Esc` bricht ab; Referenzen gesperrt). Seit M2-3: `Ctrl+A` = Transform übernehmen (in die Form), `Alt+Shift+A` = Transform löschen (Objekt springt zurück). Seit M2-4: in `4` ein normales Objekt auswählen, dann `1`/`2`/`3` = dieses Objekt bearbeiten; Undo springt zum Objekt des Schritts zurück | [AD-021 §6.1/§6.2](architecture/AD-021-OBJECT-COMPONENT-MODEL.md#61-m1-implementation-note-2026-10-15) |

### Nur in Labs und im Playground (Testszenen, nicht Produkt)

| Lab | Was man dort ausprobiert | Start | Doku |
|---|---|---|---|
| Symmetry Lab | Live-Symmetrie mit Transform- und Topologie-Werkzeugen bis einschließlich Slice 7; Symmetrischer Extrude **KEEP** (2026-10-14); Symmetrie kommt in die App (deine Entscheidung 2026-10-14, [AD-SYM-04](architecture/AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md) entschieden). **Seit Slice A1 (2026-10-14) schaltet `Shift+S` die Symmetrie auch in `python src/main.py`**; im Lab ist `Shift+S` jetzt die App-Taste. **Seit Slice A2 (2026-10-14) zeigt die App Ebene und Problem-Punkte** (grün Mitte, magenta ohne Partner, weiß mehrdeutig; keine türkisen Partner); das Lab nutzt diese Anzeige. | `python experiments/symmetry_lab/run.py` | [README](../experiments/symmetry_lab/README.md) · [AD-SYM-03](architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) |
| Subdivision Lab | Wie glatt ist glatt genug, Käfig oder Fläche, Kosten auf dem Referenz-PC. **Seit 2026-10-16 in der App** (wie das Symmetry Lab): alle Werkzeuge, Undo, Licht und Shading sind die der App; `V` wechselt Käfig → glatte Fläche + Käfig → glatte Fläche + Isolinien, `Ctrl+1/2/3` die Stufe, `B` A/B. Das alte Fenster: `run_standalone.py` | `python experiments/subdivision_lab/run.py` | [README](../experiments/subdivision_lab/README.md) |
| Morph Lab | Ein Morph-Ziel neben der Basis mit den Werkzeugen der App formen, mit den Pfeiltasten das Gewicht 0–100 % schieben; die Mischung zeigt der Viewport mit Licht und Shading der App, `Strg+S` speichert (dein „als Nächstes“, 2026-10-16; gebaut 2026-10-16, nichts in `src/`) | `python experiments/morph_lab/run.py` | [README](../experiments/morph_lab/README.md) |
| Mehlsack Lab | Box per Mausrad bauen (mit Tiefe), Loop/Ring ohne Auswahl direkt ziehen oder mit `W`/`E`/`R` halten verschieben, drehen, skalieren (Taille/Bauch, zwei Scale-Formeln per `M`), Einflusskurve mit Bézier-Handles auch unter null, Flächen-Vorschau `P`; seit Slice 3 auch Punkt-/Kanten-/Flächen-Auswahl als Ausgangspunkt derselben Gesten; seit Slice 3b Element-Hover als Standard, Loop/Ring im `L`-Modus, Doppelklick-Loops, Umrechnen (Slices 1–3b verdiktet, 2026-10-13; Slice 3c wartet auf dich) | `python experiments/mehlsack_lab/run.py` | [README](../experiments/mehlsack_lab/README.md) |
| Shading Lab | Licht/Shading für bessere Formwahrnehmung beim Modellieren | `python experiments/viewport_shading_lab/run.py` | [README](../experiments/viewport_shading_lab/README.md) |
| Playground | Varianten-Familien: Selection, Transform, Tweak, Connect, Knife, Knife Face, Topology, Articulation | `python playground/run.py head` | [README](../playground/README.md) |

---

## 2. Wartet auf dich

Sortiert nach Aufwand. Bei jedem Punkt steht, wo die Testschritte liegen.

### B. Praxis-Checks (je etwa 5–10 Minuten)

| # | Was | Testschritte |
|---|---|---|
| B1 | **Delete/Dissolve**: einziger Praxis-Check des Pakets, Verdikt UNKNOWN; DD-3 und DD-4 sind Material für den Check | [WP Delete/Dissolve, „Status“](WP_DELETE_DISSOLVE_PLAN.md) |
| B2d | **Symmetrischer Knife** (Slice 6c): Praxistest **KEEP** (Manu, 2026-10-09). **Weiter offen:** die Wahl zwischen den Spiegel-Varianten V-a / V-b / V-c (V-b bleibt Start, nichts wird entfernt) und F6 (Start des Schnitts im leeren Raum, auf deinen Wunsch offen gelassen) | [Symmetry Lab README, Slice 6c](../experiments/symmetry_lab/README.md#symmetrischer-knife-slice-6c) · [AD-SYM-03 §10.8](architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) |
| B3 | **Licht und Shading in der App** (ca. 10 Minuten, `python src/main.py`): (b) Raitt 2:1 als Start-Licht, `Strg+D` durch die Presets, `Strg+Shift+D` Kamera ↔ Welt beim Orbiten — das sind zugleich F1/F8/F9. (a) Dreiecke und (c) Frame-Zeiten sind beantwortet (2026-10-20, Intake Log). | [Intake Log, Eintrag 2026-10-15](architecture/WP-06_INTAKE_LOG.md) |
| B4 | **Subdivision Lab**: Tests T-SUBD-1 und T-SUBD-2, jetzt in der App (mit `W`/`E`/`R` oder Tweak am Käfig ziehen); dazu: passen die Tasten-Vorschläge `V`, `Ctrl+1/2/3`, `B`, `Shift+V`? | [Subdivision Lab README](../experiments/subdivision_lab/README.md) |
| B5c | **Mehlsack Lab Slice 3c** (deine 3b-Antworten umgesetzt, ca. 5 Minuten): Verdikte (u1) Ring per Shift+Doppelklick auf die Nachbarkante, (u2) weiterer Loop per Shift+Doppelklick, (u3) Punkt-Loop per Doppelklick, (u4) Face-Loop-Teilstück, (u5) `L`-Modus im Flächenmodus | [Mehlsack Lab README, „Slice 3c“](../experiments/mehlsack_lab/README.md#slice-3c-2026-10-13-ringe-punkt-loops-teilstücke) |
| B6 | **Objekte platzieren (AD-021 M2-2)**: in `4` Objekte mit `W`/`E`/`R` verschieben, drehen, skalieren; Referenz gesperrt; Statuszeile als Ebenen-Anzeige (ca. 5 Minuten) | [AD-021, Kurzfassung „M2-2 ist gebaut“](architecture/AD-021-OBJECT-COMPONENT-MODEL.md#kurzfassung-für-manu-deutsch) |
| B7 | **Transform übernehmen / löschen (AD-021 M2-3)**: `Ctrl+A` / `Alt+Shift+A` in `4`, auch auf einem symmetrischen Kopf; Fragen Q-14 (Tasten), Q-15 (Pivot danach), Q-16 (gedrehtes Symmetrie-Objekt) | [AD-021, Kurzfassung „M2-3 ist gebaut“](architecture/AD-021-OBJECT-COMPONENT-MODEL.md#kurzfassung-für-manu-deutsch) |
| B8 | **Bearbeitetes Objekt wechseln (AD-021 M2-4)**: in `4` auswählen, dann `1`/`2`/`3`; Undo springt zum Objekt des Schritts zurück | [AD-021, Kurzfassung „M2-4 ist gebaut“](architecture/AD-021-OBJECT-COMPONENT-MODEL.md#kurzfassung-für-manu-deutsch) |
| B9 | **Playground-Werkzeuge in der App** (Box, Malen, Tweak, Loop-Werkzeuge; ca. 10 Minuten) | [WP Playground-Werkzeuge, „Praxistest“](WP_PLAYGROUND_TOOLS_PROMOTION.md#praxistest-für-manu-ca-10-minuten) |
| B10 | **Morph Lab** (ca. 20–30 Minuten): Ziel formen, Gewicht schieben, speichern; Fragen J-2…J-5 | [Morph Lab README, „Praxistest“](../experiments/morph_lab/README.md#praxistest-für-manu-ca-2030-minuten) |
| B5 | **Mehlsack Lab, offen aus Slice 2a**: (d2) Kurvenfeld ITERATE — Kurvenpunkte hinzufügen/wegnehmen (noch nicht eingeplant); deine Frage „vorher erkennbar, was mitgeht — jetzt besser?“ ist noch unbeantwortet | [Mehlsack Lab README, „Slice 2a“](../experiments/mehlsack_lab/README.md#slice-2a-2026-10-13) |

### C. Lesen und einordnen (ohne Fenster)

| # | Was | Wo |
|---|---|---|
| C1 | **Head-Topologie-Walkthrough**: dein Topologie-Dokument mit den heutigen Werkzeugen durchgespielt (32 von 48 Schritten gingen wie vorhergesagt, 9 wichen ab, 7 waren blockiert); deutscher Tutorial-Entwurf liegt bei | [Walkthrough README](../experiments/head_topology_walkthrough/README.md) |

### D. Entscheidungen

| # | Was | Wo |
|---|---|---|
| D1 | **AD-SYM-03** (wie Symmetrie die Topologie-Werkzeuge koordiniert, statt sie zu blockieren): **entschieden** (Manu, 2026-10-08); die AD-013-H2-Ergänzung (Voraussetzung für Slice 3) ist ebenfalls **entschieden** (2026-10-08); Slice 3a und 3b sind umgesetzt (2026-10-08) | [AD-SYM-03](architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) |
| D1a | **Extrude-Erweiterungen**: Einzel-Face-Verhalten, Edge-/Vertex-Extrude, numerische Eingabe und Durchdringungs-Check sind spätere offene Fragen. | [ROADMAP, WP-06 B9](architecture/ROADMAP.md) |
| D1b | **Soft Selection – offene Arbeit**: symmetrische Gewichtung samt gemeinsamem Core-Umzug und Tests auf höher aufgelösten Meshes; Bedienung und spätere Ideen sind in AD-020 vermerkt. | [AD-020](architecture/AD-020-SOFT-SELECTION-APP-PATH.md) |
| D1c | **Viewport-Performance**: Navigation ist auch mit gollum 87 500 V flüssig (Manu 2026-10-17); langsam sind Hover, Klick, Box/Paint-Auswahl und W-Drag auf dichten Meshes. Slice 1: „gleich, nur schneller“, aber noch weit langsamer als Blender (Manu 2026-10-17). Slice 2 gebaut (Box-Auswahl auf gollum_20k im Container ~35-60x schneller, Hover einmal pro Frame) — dein Praxistest + Referenz-PC-Messung stehen aus. **Architektur (deine Richtung 2026-10-17: GPU-Picking + inkrementelle Topologie, gleich wichtig):** Entwürfe AD-022/AD-023 (PROPOSED), GPU-Spike gebaut — Referenz-PC-Lauf des Spikes liegt vor (2026-10-20); beide Reviews liegen vor (AD-022 und AD-023: ACCEPT WITH CHANGES, [Reviews](archive/viewport_v02/reviews/)); Messungen auf deinem PC sind durch (Zerlegung, GC, NumPy); die AD-Texte sind nach den Reviews überarbeitet (2026-10-20, Abschnitt „Review disposition“); offen: deine Entscheidung (Sperre der Basis-Topologie bei Morph-Targets, UVs/Hard-Edges). Kurzfassung des Architektur-Audits und deine nächsten Schritte: [Audit-Kurzfassung](research/viewport/ARCHITECTURE_AUDIT_2026-10-20.md). Deine Antworten zu AD-023 (2026-10-20: Undo so schnell wie die Operation, Stufe 1 zuerst) sind eingetragen; Stufe 1 ist als Experiment gebaut und auf deinem PC gemessen (Operation samt Undo etwa halbiert, z. B. Delete 3,7 → 2,0 s; noch sichtbar), dein Verdikt (2026-10-21): „trotzdem viel zu langsam“; Core-Änderungen sind bei deutlichem Gewinn ein Muss — nächster Schritt: Entscheidung Stufe 2 + AD-022: [Stufe-1-Experiment](../experiments/topology_sync_stage1/README.md). Vor der Entscheidung: Prototyp Stufe 2 + GPU-Picking **nur für Delete samt Undo** gebaut (2026-10-21) und auf deinem PC gemessen: Delete 1 Face 35 ms, Undo 19 ms (Stufe 1: 667 / 1 116 ms), `gl_PrimitiveID` auf deiner Karte exakt; dein Eindruck: „UNDO und Delete fühlen sich sehr viel schneller an“, im Vergleich mit Blender aber noch eine leichte Verzögerung („20k in Mirai fühlt sich an wie 80k in Blender“, Box-Auswahl mehrerer tausend Faces + Delete + Undo); bei tausenden Faces bleiben Box-Auswahl (noch CPU) und die Arbeit pro Element — offen: die Entscheidung über Stufe 2 + AD-022 und der nächste Schritt: [Stufe-2-Delete-Prototyp](../experiments/topology_stage2_delete/README.md). | [drag_cost README](../experiments/drag_cost/README.md), [GPU-Spike](../experiments/gpu_picking_spike/README.md), [AD-022](architecture/AD-022-GPU-PICKING.md), [AD-023](architecture/AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) |
| D1d | **Objekte (ARCH-01)**: zweites Objekt in der Szene, Zustand *Referenz*, später eigener Transform/Pivot. **Entschieden** (2026-10-15: Go für M0, Q-1–Q-4, Q-9, Q-10 beantwortet). M0 (Core, für dich unsichtbar) ist umgesetzt (2026-10-15); M1 gebaut; Q-5–Q-8, Q-11, Q-12 beantwortet, Q-13 (Pivot) zurückgestellt (2026-10-15). M2-0 (Ghost, Referenz im Wireframe; von dir für gut befunden) und M2-1 (Platzierung intern) gebaut 2026-10-15; M2-2 (Objekte verschieben/drehen/skalieren, Praxistest B6), M2-3 (Transform übernehmen/löschen, B7) und M2-4 (bearbeitetes Objekt wechseln, B8) gebaut 2026-10-15 — **M2 ist gebaut**, deine Praxistests B6–B8 stehen aus. | [AD-021, Kurzfassung](architecture/AD-021-OBJECT-COMPONENT-MODEL.md#kurzfassung-für-manu-deutsch) · [M2-Handoff](architecture/AD-021_M2_CLAUDE_CODE_HANDOFF.md) |
| D2 | **Priorität**: was als Nächstes (siehe Abschnitt 3) | — |

### E. Bewusst geparkt (kein Handlungsbedarf, nur damit es nicht verloren geht)

Flächen mit Loch (Face Holes; vorerst Bridges wie in Blender) ·
Hover-Kreis folgt auf dem Head leicht verzögert · Knife-Kleinigkeiten UX2-k, S4-d, S2-a.
Details: [ROADMAP, WP-06](architecture/ROADMAP.md) und [Knife-Entscheidungen](../playground/experiments/knife_face/decision.md).

---

## 3. Als Nächstes möglich (die Priorität entscheidest du)

| Kandidat | Was es dir bringt | Hängt ab von |
|---|---|---|
| Symmetrie-Spur: Symmetrie in die App, dann symmetrische Soft Selection, gemeinsamer Praxistest | Symmetrie als Teil des Production-Werkzeugflusses nutzbar machen | AD-SYM-04 entschieden (2026-10-14); Re-Symmetrize kommt mit (Weg dahin: Vorschlag §10, erst Review); Slice A1 (Shift+S in der App) und A2 (Ebene und Problem-Punkte in der App) gebaut 2026-10-14, optionale Kurzchecks in AD-SYM-04 (Implementierungsnotizen A1/A2); Kosten-Lauf auf deinem PC vorbereitet (`python experiments/symmetry_lab/probe_drag_cost.py`, Ausgabe in den Chat); Reihenfolge (deine Entscheidung 2026-10-14): erst symmetrische Soft Selection (SS0–SS3), dann Re-Symmetrize (A3, nach der Review von §10); SS0 erledigt (2026-10-14, Messprobe, nichts in `src` geändert: das Soft-Feld ist auf exakt symmetrischen Meshes bitgenau gespiegelt; ein offener Punkt für das Design, siehe AD-SYM-04, Notiz SS0; Kosten-Lauf auf deinem PC: `python experiments/soft_selection/probe_symmetric_field.py --assets head_basemesh man_with_shoes_basemesh --axes X --radii 15`, Ausgabe in den Chat); SS1-Design-Notiz geschrieben (2026-10-14, [AD-SYM-05](architecture/AD-SYM-05-WEIGHTED-TRANSFORMS-IN-CORE.md), dein R-6-Punkt ist dort Anforderung; keine Frage an dich), unabhängige Review angenommen mit Änderungen, eingearbeitet; dein Go für SS1 ist gegeben (2026-10-14); SS1 gebaut (2026-10-14: Gewichtung im Core, für dich nichts sichtbar geändert, [Notiz](architecture/AD-SYM-05-WEIGHTED-TRANSFORMS-IN-CORE.md#implementation-note-2026-10-14-slice-ss1)); SS2 gebaut (2026-10-14: Soft + Symmetrie läuft in der App; deine Antwort zu „beide Seiten / nur Mitte“ ist eingebaut; optionaler Praxistest in der [Kurzfassung von AD-SYM-04](architecture/AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md#kurzfassung-für-manu-deutsch)); SS3 gebaut (2026-10-14: die Bänder zeigen unter Symmetrie beide Seiten; Praxistest und Messbefehl für deinen PC — `python experiments/drag_cost/probe_drag_gl.py --scenarios soft_w soft_w_sym`, Ausgabe in den Chat — in derselben Kurzfassung; dein Lauf vom 2026-10-15: mit Symmetrie am Mann ab 15 % über 8 ms — Viewport-Aufgabe, offene Frage an dich, ob vor J, steht in der Kurzfassung); als Nächstes A3 (nach der Review von §10), dann J; B2d (Knife-Varianten) bleibt offen. |
| Knife-Familien im Playground zusammenführen (S5) | ein Knife statt zwei Varianten auch im Playground | — |
| Hover-/Navigations-Optimierung auf dichten Meshes | flüssigeres Arbeiten auf dichten Meshes | deine Antwort zu D1c; Messung liegt vor |

---

## 4. Wörterbuch

| Begriff | Bedeutung | 3D-Vergleich |
|---|---|---|
| `src/` vs. `experiments/` / `playground/` | Produkt vs. Spielwiese | Hauptszene vs. Testszene |
| Core (`src/core/`) | die Grundlage aller Mesh-Daten, eingefroren | das Basemesh, auf dem alles aufbaut; Änderungen nur mit Beschluss |
| Slice | ein kleiner, einzeln testbarer Arbeitsschritt | ein einzelner Render-Pass |
| PROVISIONAL | eingebaut, aber noch ohne dein Verdikt | Platzhalter-Material |
| KEEP ≠ Promotion | „fühlt sich richtig an“ heißt noch nicht „gehört fest ins Produkt“ | ein guter Testrender ist noch kein finaler Shot |
| PROMOTED | von dir freigegeben, dauerhaft Produktverhalten | Asset aus der Testszene in die Hauptszene übernommen |
| AD (Architecture Decision) | festgeschriebene Bauregel, nur ergänzt, nie still geändert | die Rig-Konventionen eines Projekts |
| Handoff | Arbeitsauftrag an einen Code-Agenten | Shot-Briefing an einen Animator |
| Artist Input Truth | deine Tastenbelegung als Referenz | deine persönliche Hotkey-Datei |
| Discovery / Production | herausfinden, was richtig ist / umsetzen, was entschieden ist | Look-Dev / Produktion |

---

## 5. Pflegeregeln für diese Seite

- Nur Index: ein Satz plus Link, keine Details, keine eigene Wahrheit.
- Ändert ein Paket einen Artist-relevanten Stand (neues Verdikt, neue offene Artist-Frage, neue Fähigkeit in der App),
  wird diese Seite **im selben Commit** aktualisiert (siehe `AGENTS.md`).
- Ein Verdikt gilt erst, wenn es im verlinkten Dokument steht. Steht es nur hier oder nur im Chat, gilt es als offen.
- Erledigte Punkte aus Abschnitt 2 werden gestrichen, nicht abgehakt. Die Geschichte steht in den verlinkten Dokumenten.
- Ziel: höchstens zwei Bildschirmseiten. Wird es länger, wird gekürzt, nicht erweitert.
