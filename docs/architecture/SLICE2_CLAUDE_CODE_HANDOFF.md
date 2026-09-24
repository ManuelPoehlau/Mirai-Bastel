# Handoff: Symmetry V1 — Slice 2 (Symmetrische Auswahl-Vorschau + symmetrisches Move)

**An:** Claude Code
**Modell/Effort:** Sonnet, effort `xhigh` (empfohlen statt `high` — mehrere
zusammenwirkende Vertex-Kategorien mit unterschiedlicher Transform-Mechanik in
einer einzigen Operation ist fehleranfälliger als Slice 1's reiner Datenlayer;
lieber jetzt gründlicher als eine subtile Spiegel-Mathematik durchrutschen
lassen).
**Modus (M5):** Production. AD-SYM-02 ist DECIDED, dieser Slice setzt ihren
noch offenen Umsetzungsteil um.
**Weiterhin headless/testbar, kein Fenster:** `../../src/mirai/application.py` ist
bewusst window-frei; laut `../WP-04_GATE_PLANNING.md` ist Gate 5b (Selection
& Display) *DROPPED* und Gate 10 (E2E) *BLOCKED* — es gibt aktuell kein
Production-Fenster. Dieser Slice bleibt deshalb wie Slice 1 vollständig durch
automatisierte Tests verifiziert, nicht durch Anschauen. Das ist kein Mangel
dieses Slices, sondern der aktuelle Projektstand.

---

## 1. Referenzdokumente (gelten, nicht neu verhandeln)

- `AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md` — DECIDED,
  umgesetzt (Slice 1): `Mesh.symmetry_definition`.
- `AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md` —
  DECIDED. Relevant hier vor allem §2.3 (Unterstützungsgrad-Aussage, noch
  nicht umgesetzt) und §2.4 (Gegenseite = gespiegelte Absicht, nicht
  nachträgliche Zuordnung — inkl. der als „Beobachtung, keine Entscheidung"
  markierten Notiz zu `VertexTransformOperation._on_update()`).
- `../research/symmetry/SYMMETRY_DESIGN_BRIEF.md` — INV-2 (Seam bleibt auf
  der Plane), INV-6, INV-7, INV-9, INV-11 (Gegenseite sichtbar *vor*
  Bestätigen — hier: berechenbar, s.o. zum Fenster).
- `../../src/mirai/symmetry.py` (Slice 1) — `vertex_correspondence()`,
  `mirror_position()`, `CorrespondenceState`. Wird hier konsumiert, nicht
  verändert, außer eine kleine, klar benannte Ergänzung ist unvermeidbar.
- `CORE_V1_FREEZE.md` §7 — auch dieser Slice ändert
  gefrorenen Core-Code (`operation.py`, evtl. `transform.py`) und braucht
  denselben Eintrag wie AD-SYM-01 in §7.1.

## 2. Ziel dieses Slices

Zwei zusammengehörige Stücke, beide headless testbar:

1. **Symmetrische Auswahl-Vorschau** (Daten, keine Anzeige): Zu einer
   aktuellen Selektion lässt sich — wenn Symmetrie aktiv ist — die Menge der
   gespiegelten Partner-Vertices ableiten, über die bestehende
   `vertex_correspondence()` aus Slice 1.
2. **Symmetrisches Move**: Bewegt man selektierte Vertices, bewegt sich ihre
   Gegenseite gespiegelt mit — als **eine** Artist-Absicht, **ein**
   Undo-Schritt (AD-SYM-02 §2.4).

## 3. Scope

### 3.1 Unterstützungsgrad-Aussage (AD-SYM-02 §2.3)

Der Operation-Vertrag (`../../src/core/operation.py`) bekommt eine Aussage, ob eine
Operation vor `begin()` symmetrisch wirken kann. Präzedenzfall im selben
Modul: `description` ist heute schon ein Klassenattribut, das den Lifecycle
nicht berührt — dieselbe Form hier. Konkrete Ausprägung (Boolean reicht laut
AD-SYM-02 §4 für diesen Slice; eine abgestufte Aussage ist E5-Stoff, nicht
hier) ist eure Wahl, dokumentiert im Code wie bei Slice 1 üblich.

### 3.2 Symmetrisches Move

Betroffene Stellen (nicht vorgeschrieben, aber das sind die Kandidaten):
`../../src/core/operations/transform.py` (`VertexTransformOperation`,
`MoveOperation`) und `../../src/mirai/interaction/tools/move.py` (`MoveTool`).

Die eigentliche Design-Frage, die AD-SYM-02 §2.4 bewusst offen gelassen hat:
**Drei Vertex-Kategorien** brauchen unterschiedliche Mechanik innerhalb
derselben Move-Interaktion, wenn Symmetrie aktiv ist:

- **Direkt selektierte Vertices** (nicht auf der Seam): bekommen das normale
  `delta`.
- **Gespiegelte Partner** (per `vertex_correspondence()` gefunden, PAIRED,
  selbst nicht in der ursprünglichen Selektion): bekommen das an der Plane
  **gespiegelte** Delta — Reflexion des Delta-*Vektors* an der Normalen
  (`d' = d - 2*(d·n)*n`), nicht dieselbe Bewegung wie die Quellseite. `n` ist
  `definition.plane_normal`.
- **Seam-Vertices** unter den selektierten (CorrespondenceState.SEAM): dürfen
  die Plane nicht verlassen (INV-2). Ihre Bewegung muss auf die Plane
  projiziert werden (`d_proj = d - (d·n)*n`), sonst bricht die Naht bei der
  ersten Move-Interaktion.

Ob das über einen neuen, per-Vertex unterschiedlichen Transform-Pfad in
`_on_update()` gelöst wird (analog zum bestehenden `self._weights`-Platzhalter
für Soft-Selection, der schon eine Pro-Vertex-Differenzierung vorsieht) oder
anders — eure Entscheidung, dokumentiert.

**Randfall, der einen Test braucht, keine Vorentscheidung:** Was passiert,
wenn ein Partner-Vertex vom Artist *auch* explizit selektiert wurde (beide
Seiten von Hand ausgewählt)? Doppelte/widersprüchliche Bewegung ist zu
vermeiden — wie genau, ist eure Wahl, aber es darf nicht still falsch
gerechnet werden.

### 3.3 Auswahl-Vorschau als Funktion

Eine reine Funktion (Vorschlag, kein Zwang zum Namen) etwa
`mirrored_selection(mesh, selection) -> set[VertexId]` in `mirai.symmetry`,
die für eine gegebene Selektion die Menge der gespiegelten Partner-IDs
liefert (leer, wenn Symmetrie aus ist). Kein Cache (AR-1, wie Slice 1).

## 4. Not in scope

- Rotate/Scale symmetrisch — nur Move, der kleinste Fall zuerst.
- Extrude, Loop Insert, jede Topologie-Operation.
- Irgendein UI-Toggle für Symmetrie an/aus — Definition wird weiterhin
  direkt am Mesh gesetzt (`mesh.symmetry_definition = ...`), wie in Slice 1
  getestet.
- Fenster, Rendering, tatsächliche visuelle Vorschau — s.o.
- Eine abgestufte Unterstützungsgrad-Aussage (nur ja/nein für diesen Slice).

## 5. Erwartete Tests

- Move mit aktiver Symmetrie: Quellseite bewegt sich um `delta`, Partnerseite
  um das gespiegelte Delta, **ein** History-Eintrag, **ein** Undo macht
  beide Seiten rückgängig.
- Cancel während einer symmetrischen Move-Interaktion: kein Commit, exakter
  Ausgangszustand auf beiden Seiten (bestehender AD-003-Vertrag, hier für den
  symmetrischen Fall geprüft, nicht neu erfunden).
- Move eines Seam-Vertex: Ergebnis bleibt exakt auf der Plane (Distanz 0,
  analog zur exakten Prüfung aus Slice 1 — keine Toleranz einführen).
- Move ohne aktive Symmetrie (`symmetry_definition is None`): Verhalten
  exakt wie vor diesem Slice — bestehende `test_transform_operations.py`
  bleiben unverändert grün.
- Der Randfall aus §3.2 (Partner zusätzlich selbst selektiert) mit
  mindestens einem Test.
- **Bestehende Suite bleibt grün:** `run_core_suite.py`, alle
  `../../tests/test_transform_operations.py`, `../../tests/test_symmetry.py`.

## 6. Betroffene Dateien (erwartet, nicht abschließend)

- `../../src/core/operation.py` — Unterstützungsgrad-Aussage
- `../../src/core/operations/transform.py` — Mirror-/Seam-Mechanik in
  `VertexTransformOperation`/`MoveOperation`
- `../../src/mirai/interaction/tools/move.py` — löst Partner-Vertices auf, bevor
  die Operation beginnt (analog zu `resolve_selection_vertices()`)
- `../../src/mirai/symmetry.py` — `mirrored_selection()` oder Äquivalent
- `../../tests/test_symmetry.py` und/oder neue Testdatei
- `CORE_V1_FREEZE.md` §7.1 — neuer Eintrag, gleiches Muster
  wie AD-SYM-01

## 7. Bekannte Constraints

- `Operation.update()` ist inkrementell (AD-003) — die Spiegel-/Projektions-
  Mechanik muss das bei mehreren `update()`-Aufrufen in Folge respektieren,
  nicht nur beim ersten.
- `plane_normal` ist laut `SymmetryDefinition`-Vertrag (Slice 1) ein
  Einheitsvektor, vom Aufrufer garantiert, nicht hier normalisiert.
- Kein neuer Cache für Correspondence — jede Ableitung geht über die
  bestehende `vertex_correspondence()`.

## 8. Unresolved / bewusst offen

- Genauer Mechanismus für die Pro-Vertex-Differenzierung in `_on_update()`
  (§3.2) — dokumentieren statt fragen, wie in Slice 1.
- Verhalten bei doppelt-selektiertem Partner (§3.2 Randfall) — testen und
  dokumentieren, nicht diskutieren.
- Rotate/Scale symmetrisch bleiben für einen späteren Slice offen.

## 9. Definition of Done

Alle Tests aus §5 grün, bestehende Suite unverändert grün,
Unterstützungsgrad-Aussage und symmetrisches Move über die öffentliche API
nutzbar und dokumentiert, CORE_V1_FREEZE.md §7.1 ergänzt. Kein Artist-Test in
diesem Slice — E1 bleibt bis zum Fenster (WP-04) ungespielt, dieser Slice
macht es nur technisch bereit.

## Bei Widerspruch

Wie bei Slice 1: Wenn eine der beiden AD-Entscheidungen beim Implementieren
nicht wie beschrieben trägt, anhalten und melden statt still umzuentscheiden.
