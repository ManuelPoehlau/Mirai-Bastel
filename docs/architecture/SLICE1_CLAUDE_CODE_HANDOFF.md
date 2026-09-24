# Handoff: Symmetry V1 — Slice 1 (Definition → Seam → Correspondence → State)

**An:** Claude Code
**Modell/Effort:** Sonnet, effort `high`
**Modus (M5):** Production — Architektur ist entschieden, jetzt wird zuverlässig umgesetzt.
**BUILD darf keine neue Erkenntnis behaupten.** Wenn beim Implementieren etwas
unerwartet anders aussieht als hier beschrieben, nicht still weiterbauen — anhalten
und melden (siehe „Bei Widerspruch" am Ende).

---

## 1. Referenzdokumente (gelten, nicht neu verhandeln)

- `docs/architecture/AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md` — **DECIDED.**
  Definition (Plane + deklarierte Seam-Element-IDs) lebt **im Mesh**, Teil von
  `export_state()`/`load_state()`. Mesh besitzt sie, kennt aber keine
  Symmetrie-Semantik.
- `docs/architecture/AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md` — **DECIDED.**
  Betrifft diesen Slice nur indirekt (keine Operation hier), aber die Grenze
  „Mesh besitzt Daten, Logik lebt oberhalb" gilt genauso für Correspondence/State.
- `docs/research/symmetry/SYMMETRY_DESIGN_BRIEF.md` — INV-1 bis INV-13 sind der
  Vertrag, den dieser Slice für die vier betroffenen Invarianten erfüllen muss:
  **INV-1** (deklarierte Seam), **INV-2** (Seam liegt auf der Plane — hier nur
  prüfbar, nicht erzwingbar, da keine Operation existiert), **INV-3**
  (Correspondence ist ableitbar, kein gespeicherter Zustand), **INV-10**
  (teilweise Symmetrie ist legitim).
- `docs/architecture/CORE_V1_FREEZE.md` §7 — dieser Slice ist eine autorisierte
  Core-Erweiterung nach AD-SYM-01, kein Präzedenzbruch.
- `docs/architecture/ROADMAP.md` §9 (WP-Standard) — dieser Slice ist der erste
  von mehreren innerhalb WP-SYM-01, nicht das ganze WP.

---

## 2. Ziel dieses Slices

Der Artist kann (vorerst nur programmatisch/testbar, noch ohne Viewport-Anzeige)
ein Mesh-Objekt als symmetrisch erklären, eine Seam deklarieren, und für jedes
Element den abgeleiteten Correspondence-Zustand (gepaart / Seam / ungepaart /
mehrdeutig) sowie den aggregierten Symmetry State (gültig / teilweise /
mehrdeutig / verletzt / aus) abfragen. **Keine Mutation, keine Operation, keine
Tool-Integration, kein Viewport.**

## 3. Scope

1. **Symmetry Definition am Mesh** (AD-SYM-01):
   - Plane (Repräsentation: eure Wahl — Punkt+Normale ist der naheliegende
     Default, aber dokumentiert die Entscheidung im Code-Kommentar, wie es der
     Rest von `mesh.py` bei ähnlichen Entscheidungen tut, z. B. `AD-002` bei
     Face-Boundaries)
   - Deklarierte Seam als Menge von Element-IDs (Edge-IDs sind der
     naheliegende Default, siehe R1 §3.8 Maya Seam-Edge; wenn ihr Vertex-IDs
     wählt, begründet das ebenso kurz)
   - `Mesh.export_state()` / `Mesh.load_state()` müssen die Definition
     mitführen. `FORMAT_VERSION` in `serialization.py`: additiver, optionaler
     Schlüssel bevorzugt gegenüber Versionssprung, aber eure Entscheidung —
     dokumentieren, welchen Weg ihr gewählt habt und warum.
   - Eine leere/keine Definition ist der Default-Zustand (Symmetrie „aus").
2. **Correspondence-Ableitung** (INV-3), als reine Funktion(en) **außerhalb**
   von `src/core/mesh.py` — Mesh besitzt die Daten, nicht die Logik
   (AD-SYM-01 §3, die ausdrückliche Grenze). Wo genau dieser Code landet
   (neues Modul unter `src/mirai/` oder ein neues Top-Level-Paket, das
   Application/Viewport gemeinsam nutzen können) ist eure Entscheidung —
   begründet sie kurz im PR/Commit, analog zum bestehenden Muster in
   `scene_factory.py` („liegt in `mirai`, nicht im gefrorenen Core, genau wie
   ein späteres Import-System das täte").
   - Vier Zustände pro Element: **gepaart** (Partner gefunden), **Seam**
     (selbst-gepaart, liegt auf der deklarierten Seam), **ungepaart** (kein
     Partner ableitbar), **mehrdeutig** (mehr als ein Kandidat).
   - Positionsbasiert für diesen Slice ist ausreichend (Design Brief §3:
     Position darf *vorschlagen und bestätigen*, nicht *definieren* — hier
     bestätigt sie tatsächlich, da die Seam bereits über Identität deklariert
     ist, nicht über Position gesucht wird. Kein Widerspruch zu INV-1/AR-3.)
   - Kein Cache, keine gespeicherte Tabelle (AR-1). Bei jedem Aufruf neu
     abgeleitet aus Definition + aktuellem Mesh-Zustand.
3. **Symmetry State** (aggregiert aus der Correspondence-Verteilung):
   `VALID` (alle gepaart oder Seam) / `PARTIAL` (mind. ein ungepaartes
   Element, sonst konsistent) / `AMBIGUOUS` (mind. ein mehrdeutiges Element) /
   `OFF` (keine Definition). `VIOLATED` (Seam-Element liegt nicht auf der
   Plane) ist Teil dieses Slices, **sofern** ihr die Plane-Prüfung ohne
   Toleranz-Diskussion sauber lösen könnt — sonst als `[OFFEN]` markiert
   liegen lassen und im Bericht nennen, nicht selbst entscheiden (Toleranz ist
   laut Evolution-Dokument bewusst nicht V1-Wahrheit).

## 4. Not in scope (nicht anfassen)

- Keine Operation, kein Tool, kein Undo/Redo-Verhalten für die Definition
  selbst (die Definition wird in diesem Slice nie durch eine Operation
  verändert — nur direkt gesetzt, z. B. über eine simple `set_definition()`
  am Mesh, testweise).
- Keine Viewport-Anzeige, kein State-Icon, keine UI.
- Kein Extrude, kein Move symmetrisch, kein Re-Symmetrize.
- Keine Toleranzwerte als Wahrheit einführen (AR-1, Design Brief §7).
- Keine Änderung an `Operation`, `HistoryStack`, `Tool` — AD-SYM-02 wird in
  einem späteren Slice umgesetzt, nicht hier.

## 5. Erwartete Tests

Analog zum bestehenden Muster in `tests/test_core.py` (Architekturvertrags-Tests)
und `tests/test_scene_serialization.py`:

- Definition setzen → `export_state()` → `load_state()` in neues/gleiches
  Mesh → Definition identisch wiederhergestellt.
- **Der Regressionsfall aus AD-SYM-01 §1.1 als expliziter Test:** Seam
  deklarieren, `split_edge()` auf der Seam, Definition zieht nach (falls ihr
  das in diesem Slice schon koppelt — sonst: Definition wird erkennbar
  ungültig, nicht still falsch), dann Undo über `MeshStateCommand` → Definition
  UND Mesh sind wieder exakt im Vorher-Zustand.
- Alle vier Correspondence-Zustände einzeln erzeugbar und erkennbar
  (kleines Testmesh reicht, kein Torso nötig).
- Symmetry State korrekt aggregiert für: leeres Mesh ohne Definition (`OFF`),
  vollständig symmetrisches Testmesh (`VALID`), eines mit einem einseitigen
  Vertex (`PARTIAL`), eines mit mehrdeutiger Nachbarschaft (`AMBIGUOUS`).
- **Bestehende Suite bleibt grün:** `tests/run_core_suite.py` (29 Tests) und
  `tests/test_scene_serialization.py` (8 Tests) laufen unverändert durch.

## 6. Betroffene Dateien (erwartet, nicht abschließend)

- `src/core/mesh.py` — Definition-Speicherung, `export_state`/`load_state`
- `src/core/serialization.py` — Format-Erweiterung
- neues Modul für Correspondence/State (Pfad: eure Entscheidung, siehe §3.2)
- `tests/test_core.py` und/oder neue Testdatei für den neuen Bereich
- `tests/test_scene_serialization.py` — Roundtrip-Ergänzung

## 7. Bekannte Constraints

- `src/core/` ist gefroren (CORE_V1_FREEZE.md) — diese Erweiterung ist durch
  AD-SYM-01 autorisiert, aber bleibt minimal. Keine zusätzlichen Core-Änderungen
  „weil man schon dabei ist".
- IDs sind opak und werden nie wiederverwendet (AD-001) — Correspondence-Code
  darf sie nie als Index interpretieren.
- `Mesh.load_state()` ersetzt In-Place (nicht `from_state()`), weil Scene/
  Selection/Viewport eine Referenz auf die Instanz halten. Die Definition muss
  denselben In-Place-Vertrag einhalten.

## 8. Unresolved / bewusst offen (nicht selbst entscheiden)

- Ob eine künftige Topologie-Operation die Seam aktiv nachführt (Wings-Muster)
  oder ob sie unverändert bleibt und der State degradiert (Maya-Muster) — AD-SYM-02
  §4 hält das ausdrücklich offen. Dieser Slice hat keine Operation, betrifft es
  also nicht direkt, aber baut nichts, das eine der beiden Richtungen vorwegnimmt.
- Repräsentation der Plane und der Seam-IDs — s. o., dokumentieren statt fragen.
- Toleranz für die `VIOLATED`-Prüfung, falls ihr sie umsetzt.

## 9. Definition of Done für diesen Slice

Alle Tests aus §5 grün, bestehende Suite unverändert grün, Definition-Storage
und Correspondence-Ableitung sind über die öffentliche API benutzbar und
dokumentiert (Docstring-Stil wie im Rest von `src/core/`, mit Bezug auf
AD-SYM-01/02). Kein Artist-Test in diesem Slice (E1 braucht Move/Extrude, die
hier nicht existieren) — das ist ein Slice, kein abgeschlossenes WP.

## Bei Widerspruch

Wenn beim Implementieren eine der beiden AD-Entscheidungen nicht wie
beschrieben umsetzbar ist (z. B. weil sich `export_state()`/`load_state()`
anders verhält als in AD-SYM-01 §1 dokumentiert): **anhalten, nicht
umentscheiden.** Das wäre laut M5 eine neue Erkenntnis und geht zurück nach
Discovery — kein stiller Baustellenentscheid.
