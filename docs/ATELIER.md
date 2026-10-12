# Mirai Atelier — Lagebild für den Artist

> **Status:** Artist-Übersicht (Index) (Claude, 2026-10-12; zuletzt geprüfter Stand: `main` @ `2e91b6d`). Nicht Artist-validiert.
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
| Anzeige | `D` wechselt Shaded → Flat → Wireframe, `Shift+D` Drahtgitter darüber | [ROADMAP, WP-06 B5a](architecture/ROADMAP.md) |
| Topologie `C` | je nach Auswahl Split, Edge Connect, Vertex Connect; ohne Auswahl startet das Knife | [AD-017](architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md) |
| Knife | Klick schneidet; Punkte in Flächen; Schnitt über mehrere Flächen; Punkte im leeren Raum; `E`/RMB = Stift abheben; Doppelklick schließt; Shift = Kantenmitte; `Enter` übernimmt, `Esc` bricht ab | [Knife-Entscheidungen](../playground/experiments/knife_face/decision.md) |
| Topologie Extrude | Face-Modus (`3`), Fläche(n) wählen (ohne Auswahl: die Fläche unter dem Cursor), `T` halten und Maus ziehen = Extrude, loslassen = fertig, `Esc` bricht ab; nach innen ziehen = Mulde mit Boden; ein Antippen oder Zittern tut nichts. **Praxistest bestanden, KEEP (2026-10-09), noch nicht PROMOTED** | [ROADMAP, WP-06 B9](architecture/ROADMAP.md) |
| Löschen | `Entf` = Delete, Rücktaste = Dissolve (mit Aufräumen), Ctrl+Rücktaste = Dissolve ohne Aufräumen | [WP Delete/Dissolve](WP_DELETE_DISSOLVE_PLAN.md) |
| Soft Selection (**feste Fähigkeit** seit 2026-10-11; Tasten und Look `PROVISIONAL`, standardmäßig **aus**) | `O` an/aus; dann ziehen W/E/R die Umgebung der Auswahl weich mit (Standard: geodesic, Kurve Smooth); `Shift`+Mausrad = Radius eine Stufe (2 % bis 200 %); `Shift+O` schaltet die Kurve durch (Smooth, Sphere, Root, Sharp, Linear, Custom), `Ctrl`+Mausrad formt die Custom-Kurve (hoch = runder, runter = spitzer), `Ctrl+O` Metrik; `Alt+O` schaltet die Farbpunkte an/aus; Zustand steht in der Statuszeile. Mit Auswahl zeigt ein Farbpunkt-Band den Einflussbereich (je wärmer, desto stärker; folgt der Auswahl, nicht dem Hover; beim Ziehen wandern die Punkte mit); unter Symmetrie sichtbar abgelehnt. **S2c-Verdikt am 2026-10-11 (Basisgefühl, Rotate/Scale, Tasten, Radius-Stufen, Bänder-Look: KEEP)** | [AD-020](architecture/AD-020-SOFT-SELECTION-APP-PATH.md) |
| Undo/Redo | `Ctrl+Z` / `Ctrl+Y` | [ROADMAP, WP-06 B3](architecture/ROADMAP.md) |
| Szene laden (`PROVISIONAL`, temporär) | `Leertaste` öffnet am Cursor ein Menü mit `cube` und den Registry-Assets (u. a. dem großen `gollum`); Klick auf eine Zeile lädt die Szene, Klick daneben/`Esc`/`Leertaste` schließt. Die Taste ist ein Engineering-Vorschlag, noch kein Verdikt | [ROADMAP, Scene loader](architecture/ROADMAP.md) |

### Nur in Labs und im Playground (Testszenen, nicht Produkt)

| Lab | Was man dort ausprobiert | Start | Doku |
|---|---|---|---|
| Symmetry Lab | Symmetrie an/aus (`Shift+S`), symmetrisches W/E/R, Re-Symmetrize (`M`); die Topologie-Werkzeuge laufen koordiniert auf beiden Seiten als ein Undo-Schritt oder werden sichtbar abgelehnt: Connect, Delete/Dissolve, Split, Knife (V-Varianten, Taste `V`) und Extrude (`T`); nicht Spiegelbares wird abgelehnt statt still falsch ausgeführt. Der Ausbau ist über AD-SYM-03 bis Slice 7 gebaut, der Extrude hat noch kein Verdikt (B2e) | `python experiments/symmetry_lab/run.py` | [README](../experiments/symmetry_lab/README.md) · [AD-SYM-03](architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) |
| Subdivision Lab | Wie glatt ist glatt genug, Käfig oder Fläche, Kosten auf dem Referenz-PC | `python experiments/subdivision_lab/run.py` | [README](../experiments/subdivision_lab/README.md) |
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
| B2e | **Symmetrischer Extrude** (AD-SYM-03 Slice 7, Symmetry Lab, `Shift+S` → `X`, `T` halten): **gebaut 2026-10-09, dein Verdikt steht aus** (KEEP / ITERATE / REJECT / UNKNOWN; Praxistest ca. 10 Minuten). Ecke an der Mitte und Fläche über der Mitte werden vorerst abgelehnt (deine Aussage vom 2026-10-09); Arbeitsregeln (Distanz, Auswahl danach) sind Engineering-Annahmen | [Symmetry Lab README, Slice 7](../experiments/symmetry_lab/README.md) · [AD-SYM-03 §11](architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) |
| B3 | **Shading Lab**: Verdikte F1/F8/F9 | [Shading Lab README](../experiments/viewport_shading_lab/README.md) |
| B4 | **Subdivision Lab**: Tests T-SUBD-1 und T-SUBD-2 | [Subdivision Lab README](../experiments/subdivision_lab/README.md) |

### C. Lesen und einordnen (ohne Fenster)

| # | Was | Wo |
|---|---|---|
| C1 | **Head-Topologie-Walkthrough**: dein Topologie-Dokument mit den heutigen Werkzeugen durchgespielt (32 von 48 Schritten gingen wie vorhergesagt, 9 wichen ab, 7 waren blockiert); deutscher Tutorial-Entwurf liegt bei | [Walkthrough README](../experiments/head_topology_walkthrough/README.md) |

### D. Entscheidungen

| # | Was | Wo |
|---|---|---|
| D1 | **AD-SYM-03** (wie Symmetrie die Topologie-Werkzeuge koordiniert, statt sie zu blockieren): **entschieden** (Manu, 2026-10-08); die AD-013-H2-Ergänzung (Voraussetzung für Slice 3) ist ebenfalls **entschieden** (2026-10-08); Slice 3a und 3b sind umgesetzt (2026-10-08) | [AD-SYM-03](architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) |
| D1a | **Extrude, offene Punkte** (nach KEEP am 2026-10-09): Einzel-Face-Extrude (jede Fläche für sich) und wie man dorthin umschaltet · Edge-/Vertex-Extrude · numerische Eingabe (braucht erst eine allgemeine numerische Eingabe) · Durchdringungs-Check · ob das Halten von `T` und der Hover-Fallback bleiben (bisher Engineering-Vorschläge) | [ROADMAP, WP-06 B9](architecture/ROADMAP.md) |
| D1b | **Soft Selection nach S2c**: **entschieden am 2026-10-11** (dein Verdikt): geodesic ist Standard, Smooth Standardkurve, Radius-Stufen bleiben (jetzt bis 200 %), Bänder-Look bleibt, Bänder abschaltbar. **S2d-Praxistest: KEEP (2026-10-11)** — Kurvenwechsel, `Ctrl`+Mausrad (Richtung, ohne Zoom), Radius bis 200 %, `Alt+O` bestätigt; alles bleibt `PROVISIONAL`. **Promotion entschieden (Manu, 2026-10-11): „Soft Selection wird eine feste Fähigkeit“** — als Fähigkeit, nicht als Bedienung; Tasten (`O`, `Shift`/`Ctrl`+Mausrad, `Shift+O`, `Ctrl+O`, `Alt+O`) und Band-Look bleiben `PROVISIONAL` und Soft bleibt beim Start aus (beides Engineering-Annahmen, von dir nicht bestätigt). Core-Anbindung: **Weg 2** — die Gewichtung zieht erst **zusammen mit der symmetrischen Soft Selection** in den Core (eine Core-Änderung); bis dahin bleibt es wie gebaut. **Offen:** symmetrische Soft Selection (inkl. Core-Umzug) · Tests mit höher aufgelösten Meshes (blockiert durch die Viewport-Performance-Arbeit) · Vorzeichen eines horizontalen Shift-/Ctrl-Mausrads. Als spätere Ideen verschoben: Radius live während des Ziehens ([Future Ideas](future_ideas/TRANSFORM.md)) · kleiner Curve-Shape-Editor, sobald es eine GUI gibt ([Future Ideas](future_ideas/UI_UX.md)) | [AD-020](architecture/AD-020-SOFT-SELECTION-APP-PATH.md) |
| D1c | **Viewport-Performance auf großen Meshes** (WP-VIEW-PERF-01, Discovery): Orbit/Pan/Zoom/Hover ruckeln auf `gollum` (21 875 V); Ursachen gemessen, Fix-Optionen gerankt, nichts umgesetzt. **Offen (deine Intent-Antwort):** welche Meshgröße flüssig bleiben muss (Head/Body oder auch Gollum-Klasse) | [drag_cost README, „Next step“](../experiments/drag_cost/README.md) |
| D2 | **Priorität**: was als Nächstes (siehe Abschnitt 3) | — |

### E. Bewusst geparkt (kein Handlungsbedarf, nur damit es nicht verloren geht)

Flat Shading pro Polygon statt pro Dreieck (B5a.1) · Flächen mit Loch (Face Holes; vorerst Bridges wie in Blender) ·
Hover-Kreis folgt auf dem Head leicht verzögert · Knife-Kleinigkeiten UX2-k, S4-d, S2-a.
Details: [ROADMAP, WP-06](architecture/ROADMAP.md) und [Knife-Entscheidungen](../playground/experiments/knife_face/decision.md).

---

## 3. Als Nächstes möglich (die Priorität entscheidest du)

| Kandidat | Was es dir bringt | Hängt ab von |
|---|---|---|
| Symmetrie-Spur: Extrude bewerten, dann Promotion prüfen | Modellieren mit Symmetrie im echten Werkzeug | Split, Connect, Delete/Dissolve und Knife sind im Lab gebaut und verdiktet (KEEP); offen: dein Verdikt zum symmetrischen Extrude (B2e), die V-Varianten (B2d), danach der Symmetrie-Promotion-Check (eigene Aufträge) |
| Knife-Familien im Playground zusammenführen (S5) | ein Knife statt zwei Varianten auch im Playground | — |
| Hover-/Navigations-Optimierung auf dichten Meshes | flüssigeres Arbeiten auf dichten Meshes | deine Antwort zu D1c; Messung liegt vor |
| Flat Shading pro Polygon (B5a.1) | Flat-Ansicht ohne sichtbare Dreiecke | berührt AD-018 |

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
