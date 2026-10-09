# Mirai Atelier — Lagebild für den Artist

> **Status:** Artist-Übersicht (Index) (Claude, 2026-10-07, gelesen auf `main` @ `936bcfb`). Nicht Artist-validiert.
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
| Undo/Redo | `Ctrl+Z` / `Ctrl+Y` | [ROADMAP, WP-06 B3](architecture/ROADMAP.md) |

### Nur in Labs und im Playground (Testszenen, nicht Produkt)

| Lab | Was man dort ausprobiert | Start | Doku |
|---|---|---|---|
| Symmetry Lab | Symmetrie an/aus (`Shift+S`), symmetrisches W/E/R, Re-Symmetrize (`M`); Werkzeuge, die nicht spiegeln, sind blockiert (neue Befehle ohne Spiegel-Unterstützung werden sichtbar abgelehnt). **Neu (Slice 3b): Edge Connect und Vertex Connect (`C`) laufen unter Symmetrie auf beiden Seiten als ein Undo-Schritt** oder werden sichtbar abgelehnt (ungepaarte Auswahl, Ebene nicht achsparallel, Face von beiden Seiten getroffen, Ergebnis nicht spiegelbildlich); Knife bleibt unter BLOCK blockiert. **Neu (Slice 3c): Delete, Dissolve und Dissolve ohne Cleanup (`Entf`, Rücktaste, Ctrl+Rücktaste) laufen unter Symmetrie in allen drei Modi auf beiden Seiten als ein Undo-Schritt**; Delete an der Naht lässt die Naht mit dem Mesh gehen, Dissolve einer Kante direkt auf der Naht wird sichtbar verweigert, Dissolve einer die Naht kreuzenden Kante läuft (zwei Seam-Kanten werden zu einer); das Interim „einseitig“ ist beendet. Mit gesetzter Symmetrie zählt `C` eine Kante plus ihre Spiegelkante als eine Absicht. **Neu (Slice 4): Split (`C` mit einer Kante) teilt die Kante und ihre Spiegelkante zusammen in der Mitte, als ein Undo-Schritt** (eine Seam-Kante einmal, der neue Punkt liegt auf der Naht), oder wird sichtbar abgelehnt; nur der Knife bleibt unter BLOCK blockiert. **Neu (Slice 7): Extrude (`T` halten) extrudiert unter Symmetrie die gewählten Flächen und ihre Spiegelpartner zusammen, als ein Undo-Schritt**; an der Naht wird die neue Deckelkante die neue Naht; eine Fläche mit nur einer Ecke an der Mitte oder eine Fläche über der Mitte wird vorerst sichtbar abgelehnt (deine Aussage vom 2026-10-09). Die Auswahl danach (Deckel auf der Arbeitsseite) ist eine Arbeitsregel, **dein Verdikt steht aus** | `python experiments/symmetry_lab/run.py` | [README](../experiments/symmetry_lab/README.md) |
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
| B2 | **AD-SYM-03, Artist-Tests A1–A3** (Seam-Verbrauch, `C` mit Auswahl auf beiden Seiten, Arbeiten neben ungepaarter Geometrie): **beantwortet** (A1 mit Fall 2 UNKNOWN, später am 2026-10-08 verfeinert, A2 = A, A3 = S „vorerst“; Verdikte in §6) | [AD-SYM-03 §6](architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) |
| B2a | **AD-SYM-03 Slice 3b, Connect unter Symmetrie** (Symmetry Lab, `Shift+S` → `X`; Edge Connect und Vertex Connect auf `subd_cube`/`head_basemesh`, mit einer Kante an der grünen Seam, neben einem magenta Vertex auf `man_with_shoes_basemesh`). **Praxis-Check am 2026-10-08: alle Schritte wie erwartet.** Auswahl nach Edge Connect: **ITERATE** (Manu) → umgesetzt: die erzeugten Kanten auf der Seite, auf der du gearbeitet hast, bei bewusst beidseitiger Auswahl die erzeugten Kanten beider Seiten (Regel ist eine Engineering-Annahme, in Teil A des Handoffs vom 2026-10-08 geprüft); Vertex Connect lässt die Auswahl unverändert. Für Split: siehe B2c | [Symmetry Lab README, Slice 3b](../experiments/symmetry_lab/README.md#symmetrische-topologie-slice-3b-edge-connect-und-vertex-connect) |
| B2b | **AD-SYM-03 Slice 3c, Delete und Dissolve unter Symmetrie** (Symmetry Lab, `Shift+S` → `X`; `head_basemesh`, `man_with_shoes_basemesh`; Schritte im Handoff vom 2026-10-08, Teil B). **Beantwortet am 2026-10-08:** Auswahl nach Face Dissolve **KEEP**; A1 Fall 2 verfeinert: eine Kante direkt auf der Naht auflösen bleibt verweigert, eine Kante, die die Naht kreuzt, wird aufgelöst (zwei Seam-Kanten werden zu einer, Nahtregel S2), Entf auf einer Seam-Kante bleibt erlaubt; eine Warnung über Nahtfolgen ist nur eine mögliche spätere Idee. **Praxis-Check Nahtregel S2 am 2026-10-08 bestanden; Schritt 1 (der grüne Punkt verschwindet, wenn eine die Naht kreuzende Kante aufgelöst wird): KEEP, Schritte 2–4 (Loop über die Naht, Kante zwischen zwei grünen Punkten, Face-Paar an der Naht) wie erwartet.** Keine offene Artist-Frage mehr in B2b. | [Symmetry Lab README, Slice 3c](../experiments/symmetry_lab/README.md#symmetrische-topologie-slice-3c-delete-und-dissolve) |
| B2c | **AD-SYM-03 Slice 4, Split unter Symmetrie** (Symmetry Lab, `Shift+S` → `X`; `head_basemesh`, `man_with_shoes_basemesh`; Schritte im Handoff vom 2026-10-08). **Umgesetzt 2026-10-08. Praxis-Check am 2026-10-08: alle Schritte bestanden, Verdikt KEEP (Manu).** Gefragt waren (a) die Auswahl nach dem Split (nur der neue Vertex deiner Seite, bei beiden Seiten beide) und (b) das Teilen immer genau in der Mitte der Kante für den ersten Stand; Manu antwortete „Alle praktischen Tests bestanden: Keep“ — die Auswahlregel ist damit Artist-bestätigt (KEEP), das Teilen in der Mitte bleibt der erste Stand. Keine offene Artist-Frage mehr in B2c | [Symmetry Lab README, Slice 4](../experiments/symmetry_lab/README.md#symmetrische-topologie-slice-4-split) |
| B2d | **Symmetrischer Knife**: deine Antworten sind eingetragen (2026-10-09: F1 = C „an der Mitte kappen“, nur die Seite, auf der du anfängst, wird geschnitten und gespiegelt, F3 = A, F4 = A; F2 und F5 als Annahmen). Der Silo-Test entfällt (Testversion abgelaufen); das Vorschau-Gefühl hast du in der App mit Slice 6c getestet (siehe Verdikt unten). **Beide Ergänzungen sind angenommen (ACCEPT, Manu 2026-10-09)**; Slice 6a (der Knife schreibt intern mit, was er behält) und Slice 6b (die symmetrische Übernahme beim Enter: kappen, einmal schneiden, gespiegelt wiederholen) sind gebaut. **Neu im Symmetry Lab (Slice 6c, gebaut 2026-10-09): der Knife läuft unter Symmetrie koordiniert, in BLOCK wie in MARK** — er zeigt die Gegenseite mit, den nicht geschnittenen Teil grau, sperrt beim Hover und Klick, was nicht gespiegelt werden kann (magenta, mit Text), und schneidet bei Enter beide Seiten in einem Undo-Schritt. Drei Spiegel-Varianten (V-a/V-b/V-c, Taste **V**, Start V-b), die Farben, die Texte und das Verhalten nach einem abgelehnten Enter sind Engineering-Vorgaben und behalten ihre „vorläufig“-Kennzeichnung. **Verdikt (Manu, 2026-10-09, Praxistest): Slice 6c wie gebaut = KEEP** — du hast „alles Mögliche“ getestet, es funktioniert „überraschend gut“; dabei wurde ein allgemeines (nicht symmetrisches) Knife-Problem gefunden und behoben. Slice 6d ist damit jetzt nicht nötig. **Weiter offen (nicht entschieden):** die Wahl zwischen den Spiegel-Varianten V-a / V-b / V-c (V-b bleibt Start, V-a und V-c bleiben schaltbar, nichts wird entfernt). F6 (wo beginnt der Schnitt, wenn du im leeren Raum anfängst?) bleibt auf deinen Wunsch **offen** („offen lassen (die Idee ist, später bei Start im leeren Raum ein Slice zu starten, ist jetzt aber erstmal irrelevant)“). **Nächster Schritt in der Symmetrie-Spur:** symmetrischer Extrude (Slice 7), danach der Symmetrie-Promotion-Check (eigene Aufträge) | [Symmetry Lab README, Slice 6c + Praxistest](../experiments/symmetry_lab/README.md#praxistest-für-manu-slice-6c-b2d) · [AD-SYM-03 §10.8](architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) · [AD-017 §13](architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md) · [Knife-Discovery §6](research/symmetry/SYMMETRY_KNIFE_DISCOVERY.md#6-entscheidungsvorlage-für-manu) |
| B2e | **Symmetrischer Extrude** (AD-SYM-03 Slice 7, Symmetry Lab, `Shift+S` → `X`, `T` halten; `head_basemesh`, `man_with_shoes_basemesh`). **Gebaut 2026-10-09, dein Verdikt steht aus** (KEEP / ITERATE / REJECT / UNKNOWN). Deine Aussage vom 2026-10-09 ist eingetragen: Ecke an der Mitte und Fläche über der Mitte werden vorerst abgelehnt — ob so ein Fall später einen eigenen Deckelpunkt bekommt, ist nicht entschieden. Arbeitsregeln (Engineering, noch kein Verdikt): Distanz an den Flächen der Arbeitsseite; Auswahl danach = Deckel auf der Seite, auf der du gearbeitet hast. Gefragt: Zug auf beiden Seiten richtig? Mittelkante an der Naht wie erwartet (M)? Auswahl danach gewünscht? **Nächster Schritt:** dein Praxistest (9 Punkte, ca. 10 Minuten) | [Symmetry Lab README, Slice 7 + Praxistest](../experiments/symmetry_lab/README.md), [AD-SYM-03 §11](architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) |
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
| D2 | **Priorität**: was als Nächstes (siehe Abschnitt 3) | — |

### E. Bewusst geparkt (kein Handlungsbedarf, nur damit es nicht verloren geht)

Flat Shading pro Polygon statt pro Dreieck (B5a.1) · Flächen mit Loch (Face Holes; vorerst Bridges wie in Blender) ·
Hover-Kreis folgt auf dem Head leicht verzögert · Knife-Kleinigkeiten UX2-k, S4-d, S2-a.
Details: [ROADMAP, WP-06](architecture/ROADMAP.md) und [Knife-Entscheidungen](../playground/experiments/knife_face/decision.md).

---

## 3. Als Nächstes möglich (die Priorität entscheidest du)

| Kandidat | Was es dir bringt | Hängt ab von |
|---|---|---|
| Symmetrie für Split/Connect/Knife/Delete/Dissolve im Lab | Modellieren mit Symmetrie ohne Blockaden | D1 und die H2-Ergänzung sind entschieden; Slice 1–2, 3a (Infrastruktur), 3b (Edge/Vertex Connect), 3c (Delete, Dissolve) und Slice 4 (Split) erledigt, Praxis-Check der Nahtregel S2 bestanden (KEEP), Praxis-Check Split bestanden (KEEP, B2c), danach Knife (Slice 6; Ergänzungen AD-SYM-03 §10 und AD-017 §13 angenommen, Slice 6a, 6b und 6c gebaut — der Knife läuft im Lab koordiniert, Praxistest B2d: KEEP, Manu 2026-10-09; offen: V-Varianten, F6; als Nächstes symmetrischer Extrude) |
| Symmetrie in die Production-App | Symmetrie im echten Werkzeug | Lab-Ausbau, danach Promotionsprüfung |
| Knife-Familien im Playground zusammenführen (S5) | ein Knife statt zwei Varianten auch im Playground | — |
| Hover-Optimierung auf dem Head | flüssigeres Arbeiten auf dichten Meshes | — |
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
