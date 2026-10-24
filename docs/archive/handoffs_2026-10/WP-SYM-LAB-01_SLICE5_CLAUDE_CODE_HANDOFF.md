# Handoff: WP-SYM-LAB-01 — Slice 5 (Re-Symmetrize über topologische Paarung)

**An:** Claude Code
**Modell/Effort:** Opus, effort `high`
**Modus (M5):** Production — Entscheidungen stehen in §2, jetzt wird zuverlässig umgesetzt.
**BUILD darf keine neue Erkenntnis behaupten.** Wenn beim Implementieren etwas
unerwartet anders aussieht als hier beschrieben, nicht still weiterbauen — anhalten
und melden (siehe „Bei Widerspruch" am Ende).

**Stand:** Slice 4 gemergt als `7f6431d`, von Manu am 2026-09-25 im Lab geprüft:
Symmetrie-Linie stabil, gepaarte Vertices bewegen sich synchron, ungepaarte (lila)
bewegen sich erwartungsgemäß nicht mit.

---

## 1. Referenzdokumente (gelten, nicht neu verhandeln)

- Handoffs Slice 2–4 von `WP-SYM-LAB-01` — alle Entscheidungen gelten weiter
  (kein Import aus `playground/`, keine Änderung an `src/`, one-shot Move, E1–E10).
- `docs/research/symmetry/SYMMETRY_DESIGN_BRIEF.md` — INV-3 (Korrespondenz ableitbar),
  INV-4 (die Seam ist, was überlebt), INV-5 (nie auf unbekannten Partner spiegeln),
  INV-7 (eine Handlung, ein Schritt), INV-12 (Wiederherstellung bewusst, erkennbare
  Quellseite), §5 Szenario „Wiederherstellung": vorher sichtbar, was sich ändert.
- `docs/architecture/AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md` — Definition inkl. Seam.
- `docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md` — Experiment zuerst;
  Promotion nach `src/` nur per eigener Entscheidung.

## 2. Entscheidungen

### Artist (Manu, 2026-09-25)

- **A5 — Nur exakt gespiegelt gilt als symmetrisch.** Keine Toleranz, auch nicht in
  diesem Slice. (Toleranz bleibt eine spätere Forschungsfrage.)
- **A6 — Quellseite = Seite der Auswahl.**
- **A7 — Taste M:** M öffnet die Vorschau, M erneut führt aus.

### Engineering (in diesem Handoff festgelegt)

- **E11 — Topologische Paarung, nur für Re-Symmetrize.** Partner für Re-Symmetrize
  kommen **nicht** aus Positionen, sondern aus einem Lauf über das Netz, ausgehend von
  der gespeicherten Seam. Symmetrisches Move bleibt bei der exakten
  Positions-Paarung der Capability (`mirai.symmetry`) — **unverändert**.
  Algorithmus (in der Untersuchung prototypisch verifiziert, siehe §7-Zahlen):
  1. Jeder Vertex einer Seam-Edge ist selbst-gepaart.
  2. Für jede Seam-Edge mit genau zwei Faces: diese beiden Faces sind Spiegel-Paar.
  3. Ein Face-Paar mit bekannter gemeinsamer Anker-Edge (a,b) ↔ (a',b') wird
     gleichzeitig umlaufen — im einen Face in Richtung a→b, im anderen in Richtung
     a'→b' — und die Vertices paarweise zugeordnet. Unterschiedliche Face-Längen oder
     ein nicht passender Anker → Konflikt für dieses Paar, nicht weiterlaufen.
  4. Über jede Edge des Face-Paars zum jeweils nächsten Face-Paar weiterlaufen (Breitensuche,
     jedes Paar einmal).
  5. Bekommt ein Vertex zwei verschiedene Partner → Konflikt; dieser Vertex gilt als
     **nicht gepaart** (INV-5).
  Die Paarung ist aus Definition + aktuellem Netz abgeleitet (INV-3), wird nicht
  gespeichert und ist positionsunabhängig.
- **E12 — Seiten topologisch:** Die Faces werden in Zusammenhangskomponenten zerlegt,
  wobei Seam-Edges nicht überquert werden. Genau **zwei** Komponenten sind Voraussetzung;
  sonst wird Re-Symmetrize abgelehnt (Statuszeile nennt den Grund). Ein Vertex gehört zu
  der Seite, deren Faces er berührt; Seam-Vertices gehören zu keiner Seite. Die
  Quellseite ist die Seite des ausgewählten Vertex — dadurch auch dann richtig, wenn der
  Vertex schon über die Ebene gewandert ist.
- **E13 — Was Re-Symmetrize ändert:**
  - Jeder Vertex der **Zielseite** mit topologischem Partner auf der Quellseite wird auf
    `mirror_position(partner)` gesetzt (Capability-Funktion, für die Achsen-Normalen aus
    E1 bitgenau).
  - Jeder Seam-Vertex wird exakt auf die Ebene gelegt (Achsenkomponente = `0.0`).
  - Die Quellseite wird nicht verändert.
  - Zielseiten-Vertices ohne topologischen Partner oder im Konflikt bleiben unverändert
    und werden in der Vorschau sichtbar gemacht.
- **E14 — Ein Undo-Schritt** über `MeshStateCommand` (gleiches Muster wie der
  Symmetrie-Zyklus, Slice 3 E2).
- **E15 — Vorschau-Zustand (A7):**
  - M wird abgelehnt (Statuszeile, kein Zustand), wenn: Symmetrie aus; keine Auswahl;
    ausgewählter Vertex ist Seam-Vertex; Voraussetzung aus E12 verletzt; ein Move ist
    scharf oder läuft.
  - Sonst: Vorschau aktiv. Sichtbar: Vertices, die sich bewegen werden; Seam-Vertices,
    die auf die Ebene gelegt werden (nur die, die nicht schon exakt darauf liegen);
    Zielseiten-Vertices, die mangels Partner unverändert bleiben. Statuszeile: Richtung
    (z. B. „Quelle +X → Ziel −X"), Anzahlen, „M = ausführen, ESC = abbrechen".
  - M erneut → ausführen, Vorschau endet. ESC → Vorschau endet ohne Änderung.
  - Während der Vorschau: Navigation (Orbit/Pan/Zoom) erlaubt; alle anderen Commands
    (Select, Q, Shift+S, Undo/Redo) werden **ignoriert** mit Hinweis in der Statuszeile.
    Hover-Anzeige pausiert.
  - Wenn nichts zu tun ist (alles schon exakt symmetrisch): Vorschau zeigt „0 Änderungen";
    M erneut erzeugt **keinen** History-Eintrag.

## 3. Ziel dieses Slices

Der Artist wählt einen Vertex auf der „guten" Seite, drückt M, sieht, was sich ändern
wird, drückt M erneut — und die andere Seite ist exakt gespiegelt. Lila Vertices werden
dadurch wieder gelb. Ein Undo nimmt das Ganze als einen Schritt zurück.

## 4. Scope

1. **Lab-Modul für E11/E12** (z. B. `lab_topology.py`), rein und GL-frei, mit
   Rückgabe: Partner-Map, Konflikt-Vertices, Seiten-Zuordnung, Anzahl Komponenten.
   Docstring: ausdrücklich **Lab-Experiment**, nicht Capability; Verweis auf dieses
   Handoff und auf INV-3/INV-4.
2. **Re-Symmetrize-Plan** als reine Funktion (Quellseite → Liste der Positionsänderungen
   + unveränderte Zielseiten-Vertices), damit Vorschau und Ausführung dieselbe
   Berechnung benutzen.
3. **Binding** in `LAB_OVERRIDES`: M → Lab-lokaler Command-String (z. B.
   `"ReSymmetrize"`). M ist in den globalen Defaults und in `artist_input_truth.json`
   frei (geprüft).
4. **Dispatcher-Zustand** für die Vorschau (E15), GL-frei und testbar.
5. **Darstellung** der Vorschau (Farben eure Wahl, README-Legende ergänzen).

## 5. Not in scope

- Toleranz jeder Art (A5).
- Topologische Paarung für Move oder für die Anzeige der gelben/lila Vertices — die
  bleiben positionsbasiert und exakt.
- Topologie-Änderungen (kein Löschen/Spiegeln/Schweißen einer Hälfte).
- Promotion nach `src/mirai/symmetry.py`.
- Seam-Bearbeitung, Mehrfachauswahl.

## 6. Must NOT change (Diff muss hier leer sein)

- `src/**`, `playground/**`, `tools/**`, `examples/**`, Tests außerhalb von
  `experiments/symmetry_lab/tests/`.

Erwarteter Diff: nur Dateien unter `experiments/symmetry_lab/` (inkl. README) und
dieses Handoff-Dokument.

## 7. Erwartete Tests (headless)

Charakterisierung (Ebene X, Seam aus Slice 3 E3; Zahlen aus der Untersuchung):

- **Abdeckung/Konflikte:** `subd_cube` 26/26 Vertices topologisch gepaart, 0 Konflikte;
  `head_basemesh` 326/326, 0; `man_with_shoes_basemesh` 928/928, 0.
- **Übereinstimmung:** Wo die Capability einen Vertex als `PAIRED` meldet, ist der
  topologische Partner derselbe (18/18, 290/290, 830/830).
- **Die 54:** Alle 54 `UNPAIRED`-Vertices von `man_with_shoes_basemesh` haben einen
  topologischen Partner.
- **Positionsunabhängig:** Nach Verschieben einiger gepaarter Vertices ist die
  topologische Paarung identisch.
- **Seiten:** jeweils genau 2 Komponenten mit 12/12, 162/162, 463/463 Faces.

Verhalten:

- `man_with_shoes_basemesh`: Re-Symmetrize von **jeder** Seite aus → `symmetry_state`
  `valid`, 0 `UNPAIRED`; genau ein History-Eintrag; ein Undo stellt den Zustand exakt
  wieder her.
- Quellseite bleibt bitgenau unverändert.
- Ausgewählter Vertex vorher über die Ebene verschoben → Quellseite trotzdem seine
  topologische Seite.
- Seam-Vertex vom Plane weg verschoben → danach exakt auf der Ebene.
- Ablehnungen aus E15 (Symmetrie aus, keine Auswahl, Seam-Vertex gewählt, Move scharf).
- Vorschau: M, M → ausgeführt; M, ESC → unverändert, kein History-Eintrag; während der
  Vorschau werden Select/Q/Shift+S/Undo ignoriert; „0 Änderungen" → kein
  History-Eintrag.
- Künstlicher Konflikt (z. B. ein Face auf einer Seite durch ein Dreieck ersetzt oder
  Test-Mesh mit asymmetrischer Topologie) → betroffene Zielseiten-Vertices bleiben
  unverändert und stehen im Plan als „ohne Partner".
- Alle bisherigen Lab-Tests und die Import-Grenze bleiben grün.

## 8. Done-Kriterien

- Lab-Tests grün; Produktions-Suite unverändert grün
  (`pytest tests --ignore=tests/test_extrude_tool.py`).
- `git diff --stat` enthält nur Dateien aus §6 „Erwarteter Diff".
- README: Steuerung (M / M / ESC), Regel für die Quellseite, Farblegende, Abschnitt
  „Topologische Paarung — Lab-Experiment" (was, warum, Grenzen), Prüfanleitung für Manu
  (z. B. `man_with_shoes_basemesh` laden, Symmetrie X, Vertex rechts wählen, M, M →
  lila verschwindet). **Keine** Artist-Validierung behaupten.
- Commit-Message-Vorschlag:
  `WP-SYM-LAB-01 Slice 5: Re-Symmetrize via topological correspondence (lab-local)`

## 9. Bei Widerspruch

Anhalten und melden, nicht still lösen, insbesondere wenn:

- eine der Charakterisierungszahlen aus §7 nicht reproduzierbar ist,
- nach Re-Symmetrize der State nicht `valid` ist (dann ist entweder E13 oder die
  Bitgenauigkeit von `mirror_position` falsch verstanden),
- die Seam eines der Meshes nicht in genau zwei Komponenten teilt,
- sich Re-Symmetrize nur mit Änderungen an `src/` oder Import aus `playground/` lösen
  lässt.
