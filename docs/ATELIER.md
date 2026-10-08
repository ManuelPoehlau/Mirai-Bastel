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
| Löschen | `Entf` = Delete, Rücktaste = Dissolve (mit Aufräumen), Ctrl+Rücktaste = Dissolve ohne Aufräumen | [WP Delete/Dissolve](WP_DELETE_DISSOLVE_PLAN.md) |
| Undo/Redo | `Ctrl+Z` / `Ctrl+Y` | [ROADMAP, WP-06 B3](architecture/ROADMAP.md) |

### Nur in Labs und im Playground (Testszenen, nicht Produkt)

| Lab | Was man dort ausprobiert | Start | Doku |
|---|---|---|---|
| Symmetry Lab | Symmetrie an/aus (`Shift+S`), symmetrisches W/E/R, Re-Symmetrize (`M`); Werkzeuge, die nicht spiegeln, sind blockiert (neue Befehle ohne Spiegel-Unterstützung werden sichtbar abgelehnt). **Neu (Slice 3b): Edge Connect und Vertex Connect (`C`) laufen unter Symmetrie auf beiden Seiten als ein Undo-Schritt** oder werden sichtbar abgelehnt (ungepaarte Auswahl, Ebene nicht achsparallel, Face von beiden Seiten getroffen, Ergebnis nicht spiegelbildlich); Split und Knife bleiben unter BLOCK blockiert. **Neu (Slice 3c): Delete, Dissolve und Dissolve ohne Cleanup (`Entf`, Rücktaste, Ctrl+Rücktaste) laufen unter Symmetrie in allen drei Modi auf beiden Seiten als ein Undo-Schritt**; Delete an der Naht lässt die Naht mit dem Mesh gehen, Dissolve einer Kante direkt auf der Naht wird sichtbar verweigert, Dissolve einer die Naht kreuzenden Kante läuft (zwei Seam-Kanten werden zu einer); das Interim „einseitig“ ist beendet. Mit gesetzter Symmetrie zählt `C` eine Kante plus ihre Spiegelkante als eine Absicht (unter MARK: einseitiger Split der einen Kante) | `python experiments/symmetry_lab/run.py` | [README](../experiments/symmetry_lab/README.md) |
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
| B2a | **AD-SYM-03 Slice 3b, Connect unter Symmetrie** (Symmetry Lab, `Shift+S` → `X`; Edge Connect und Vertex Connect auf `subd_cube`/`head_basemesh`, mit einer Kante an der grünen Seam, neben einem magenta Vertex auf `man_with_shoes_basemesh`). **Praxis-Check am 2026-10-08: alle Schritte wie erwartet.** Auswahl nach Edge Connect: **ITERATE** (Manu) → umgesetzt: die erzeugten Kanten auf der Seite, auf der du gearbeitet hast, bei bewusst beidseitiger Auswahl die erzeugten Kanten beider Seiten (Regel ist eine Engineering-Annahme, in Teil A des Handoffs vom 2026-10-08 geprüft); Vertex Connect lässt die Auswahl unverändert. Nach Split (Slice 4) noch offen | [Symmetry Lab README, Slice 3b](../experiments/symmetry_lab/README.md#symmetrische-topologie-slice-3b-edge-connect-und-vertex-connect) |
| B2b | **AD-SYM-03 Slice 3c, Delete und Dissolve unter Symmetrie** (Symmetry Lab, `Shift+S` → `X`; `head_basemesh`, `man_with_shoes_basemesh`; Schritte im Handoff vom 2026-10-08, Teil B). **Beantwortet am 2026-10-08:** Auswahl nach Face Dissolve **KEEP**; A1 Fall 2 verfeinert: eine Kante direkt auf der Naht auflösen bleibt verweigert, eine Kante, die die Naht kreuzt, wird aufgelöst (zwei Seam-Kanten werden zu einer, Nahtregel S2), Entf auf einer Seam-Kante bleibt erlaubt; eine Warnung über Nahtfolgen ist nur eine mögliche spätere Idee. **Praxis-Check Nahtregel S2 am 2026-10-08 bestanden; Schritt 1 (der grüne Punkt verschwindet, wenn eine die Naht kreuzende Kante aufgelöst wird): KEEP, Schritte 2–4 (Loop über die Naht, Kante zwischen zwei grünen Punkten, Face-Paar an der Naht) wie erwartet.** Keine offene Artist-Frage mehr in B2b. | [Symmetry Lab README, Slice 3c](../experiments/symmetry_lab/README.md#symmetrische-topologie-slice-3c-delete-und-dissolve) |
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
| D2 | **Priorität**: was als Nächstes (siehe Abschnitt 3) | — |

### E. Bewusst geparkt (kein Handlungsbedarf, nur damit es nicht verloren geht)

Flat Shading pro Polygon statt pro Dreieck (B5a.1) · Flächen mit Loch (Face Holes; vorerst Bridges wie in Blender) ·
Hover-Kreis folgt auf dem Head leicht verzögert · Knife-Kleinigkeiten UX2-k, S4-d, S2-a.
Details: [ROADMAP, WP-06](architecture/ROADMAP.md) und [Knife-Entscheidungen](../playground/experiments/knife_face/decision.md).

---

## 3. Als Nächstes möglich (die Priorität entscheidest du)

| Kandidat | Was es dir bringt | Hängt ab von |
|---|---|---|
| Symmetrie für Split/Connect/Knife/Delete/Dissolve im Lab | Modellieren mit Symmetrie ohne Blockaden | D1 und die H2-Ergänzung sind entschieden; Slice 1–2, 3a (Infrastruktur), 3b (Edge/Vertex Connect) und 3c (Delete, Dissolve) erledigt, Praxis-Check der Nahtregel S2 bestanden (KEEP), danach Split (Slice 4, AD-SYM-03 §7) |
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
