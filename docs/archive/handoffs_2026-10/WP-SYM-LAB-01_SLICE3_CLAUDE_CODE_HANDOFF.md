# Handoff: WP-SYM-LAB-01 — Slice 3 (Symmetrie an/aus, Vorschau, symmetrisches Move)

**An:** Claude Code
**Modell/Effort:** Opus, effort `high`
**Modus (M5):** Production — Entscheidungen stehen in §2, jetzt wird zuverlässig umgesetzt.
**BUILD darf keine neue Erkenntnis behaupten.** Wenn beim Implementieren etwas
unerwartet anders aussieht als hier beschrieben, nicht still weiterbauen — anhalten
und melden (siehe „Bei Widerspruch" am Ende).

**Stand:** Slice 2 gemergt als `f4ad7d1`, von Manu am 2026-09-24 auf Windows geprüft
(Start, Orbit/Pan/Zoom, Vertex-Klick: alles wie beschrieben).

---

## 1. Referenzdokumente (gelten, nicht neu verhandeln)

- `docs/architecture/WP-SYM-LAB-01_SLICE2_CLAUDE_CODE_HANDOFF.md` — §2 (Rendering/Kamera,
  kein Import aus `playground/`) gilt unverändert weiter.
- `docs/architecture/AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md` — Definition lebt im
  Mesh, nimmt an Undo/Redo teil, **keine** UI-/Tool-Einstellung (AR-7).
- `docs/architecture/AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md` — ein
  History-Eintrag pro symmetrischer Handlung.
- `docs/research/symmetry/SYMMETRY_DESIGN_BRIEF.md` — hier relevant: INV-1 (deklarierte
  Seam), INV-5 (keine stille falsche Symmetrie), INV-7 (eine Handlung, ein Schritt),
  INV-10 (teilweise Symmetrie legitim und **erkennbar**), INV-11 (Vorschau vor dem
  Bestätigen).
- `docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md` — Lab-Bindings sind
  sichtbare Overrides; Gesten-Semantik (A3) bleibt global offen, ist hier Lab-lokal.
- Capability (gemergt, nur benutzen): `src/mirai/symmetry.py`
  (`vertex_correspondence`, `symmetry_state`, `mirrored_selection`),
  `SymmetryDefinition` in `src/core/mesh.py`, `MoveTool` (symmetrisch, sobald
  `mesh.symmetry_definition` gesetzt ist), `MeshStateCommand` in
  `src/core/operations/topology.py`.

## 2. Entscheidungen

### Artist (Manu, 2026-09-24)

- **A1 — Move-Geste:** Q drücken, dann LMB ziehen.
- **A2 — Symmetrie-Taste:** Shift+S schaltet zyklisch **aus → X → Y → Z → aus**.

### Engineering (in diesem Handoff festgelegt)

- **E1 — Ebene durch den Welt-Ursprung**, Punkt `(0.0, 0.0, 0.0)`, Normale exakt
  `(1.0, 0.0, 0.0)` / `(0.0, 1.0, 0.0)` / `(0.0, 0.0, 1.0)` (Einheitsvektoren, Vertrag
  von `SymmetryDefinition`). Kein Mesh-Zentrum, keine freie Ebene.
- **E2 — Jeder Schritt von Shift+S ist genau ein Undo-Schritt**, über das vorhandene
  Muster: `before = mesh.export_state()` → Definition setzen →
  `after = mesh.export_state()` → `scene.history.push(MeshStateCommand(...))`
  (Präzedenz: `playground/topology_ops.py` — **lesen, nicht importieren**). Keine neue
  History-Mechanik.
- **E3 — Seam-Festlegung beim Einschalten:** Die Seam wird **einmal** beim Wechsel auf
  eine Ebene festgelegt als: alle Edges, deren **beide** Endpunkte auf der jeweiligen
  Achse exakt `0.0` haben. Danach ist sie gespeicherte Deklaration (INV-1), keine
  laufende Positionsprüfung. Das ist eine bewusste **Lab-Annahme** — in der README als
  solche benennen, nicht als Capability-Regel.
- **E4 — Keine Toleranz.** Die Capability vergleicht exakt; das bleibt so. Befund
  (verifiziert): `man_with_shoes_basemesh` auf X ergibt `partial` mit **54** Vertices
  ohne Partner, weil sie ca. `1e-6` neben der Spiegelposition liegen (OBJ-Rundung).
  Das Lab macht diese Vertices **sichtbar** (INV-10); es korrigiert sie nicht und
  führt keinen Toleranzwert ein.
- **E5 — Move-Geste ist einmalig (one-shot):** Q scharf schalten → LMB-Drag bewegt →
  Release = Commit **und** entschärft. Für einen weiteren Move erneut Q. (Lab-Wahl zu
  A1; wenn Manu später „bleibt scharf" möchte, ist das eine eigene Änderung.)
- **E6 — Move läuft über `app.tool_manager`** (erster Live-Einsatz): Q →
  `activate(MOVE)` (Pattern A), LMB-Press → `begin_current_interaction({...})`,
  Drag → `update(dx=, dy=, width=, height=)`, Release → `commit()`, Abbruch →
  `cancel()`, danach `deactivate()`. `update()`-Deltas sind **inkrementell**
  (Vertrag in `src/core/operation.py`) — die pyglet-Drag-Deltas passen direkt.

## 3. Ziel dieses Slices

Der Artist schaltet mit Shift+S die Symmetrie durch die Ebenen, sieht Ebene, Seam und
Vertices ohne Partner, sieht beim Auswählen den gespiegelten Partner (Vorschau, INV-11)
und verschiebt mit Q + LMB-Drag einen Vertex symmetrisch. Ein Undo nimmt genau eine
Handlung zurück — Move oder Symmetrie-Schritt.

## 4. Scope

1. **Lab-Bindings** (in `LAB_OVERRIDES`, Lab-Kontext, sichtbar beim Start ausgegeben):

   | Aktion | Input | Command | Herkunft |
   |---|---|---|---|
   | Symmetrie durchschalten | Shift+S | Lab-lokaler String, z. B. `"SymmetryCycle"` | Artist A2 |
   | Move scharf schalten | Q | `Move` | globaler Default (Fallback) |
   | Abbrechen | ESC | `Cancel` | globaler Default (Fallback) |
   | Undo / Redo | Ctrl+Z / Ctrl+Y | `Undo` / `Redo` | globaler Default (Fallback) |

   Der Lab-Command-String wird **im Lab** definiert, nicht in `commands.py`.
   Alle Slice-2-Bindings bleiben unverändert.

2. **Tastatur-Pfad:** Das Fenster überschreibt jetzt `on_key_press` und reicht über
   `mirai.pyglet_input.key_from_pyglet` an den Dispatcher weiter. ESC-Regel:
   - läuft ein Move-Drag → `cancel()` (exakter Vorzustand, kein History-Eintrag);
   - ist Move nur scharf → entschärfen;
   - sonst → Dispatcher meldet „nicht behandelt", das Fenster lässt das
     pyglet-Standardverhalten laufen (Fenster schließt wie bisher).

3. **Symmetrie-Zyklus (E1–E3):** Seam-Ableitung als reine, GL-freie Lab-Funktion.
   Während ein Move-Drag läuft, wird Shift+S ignoriert (die laufende Geste besitzt den
   Input). Nach jedem Schritt: Mesh-VBOs/Overlays neu aufbauen, Status aktualisieren.

4. **Move-Geste (A1, E5, E6):**
   - Q ohne Auswahl → nicht scharf schalten, Statuszeile meldet es (kein Fehler).
   - Q mit Auswahl → scharf; Statuszeile zeigt es.
   - LMB-Press während scharf → Interaktion beginnen mit
     `scene`, `camera`, `vertex_ids = Auswahl` (die Symmetrie liest `MoveTool`
     selbst aus dem Mesh — **nicht** im Lab nachbauen).
   - Drag → `update(...)`, nach jedem Update Mesh-VBO neu aufbauen (voller Rebuild,
     Slice-2-§2.3).
   - Release: Bewegung unter der Klick-Schwelle → `cancel()` (kein History-Eintrag);
     sonst `commit()` (genau ein History-Eintrag). In beiden Fällen entschärfen.
   - Während Move scharf ist, startet nur **LMB ohne Modifier** den Move. Alt+LMB,
     Shift+LMB, MMB und Mausrad navigieren weiter wie in Slice 2 (der Artist kann vor
     dem Ziehen noch die Ansicht drehen). Während eines laufenden Drags werden weitere
     Presses ignoriert (wie Slice 2).

5. **Undo/Redo** über `app.dispatch_command(UNDO/REDO)`; danach Auswahl leeren
   (Vertex-IDs können nach einem Symmetrie-Snapshot nicht mehr gültig sein — gleiches
   Vorgehen wie der Playground), VBOs neu aufbauen. Während eines Drags ignorieren.

6. **Darstellung** (Farben eure Wahl, in der README-Legende dokumentiert):
   - gespiegelter Partner der Auswahl (`mirrored_selection`) — eigene Farbe (INV-11);
   - bei aktiver Symmetrie: Seam-Vertices und Vertices mit `UNPAIRED`/`AMBIGUOUS`
     jeweils eigene Farbe (INV-10);
   - Ebene als Linien-Umriss, auf die Mesh-Bounds bemessen;
   - Statuszeile: Ebene (aus/X/Y/Z), `symmetry_state`, Anzahl ohne Partner,
     Move-Zustand (bereit/scharf/zieht), Auswahl.

## 5. Not in scope

- Rotate/Scale symmetrisch, Mehrfachauswahl, Edge-/Face-Modus.
- Seam von Hand bearbeiten, Ebene mit anderem Punkt als dem Ursprung.
- Jede Toleranz (E4), Re-Symmetrize (INV-12), Ctrl+Shift+Z.
- Achsen-Constraints (X/Y/Z) für Move.
- Änderungen an der Symmetrie-Capability, an `MoveTool` oder an `commands.py`.

## 6. Must NOT change (Diff muss hier leer sein)

- `src/**`, `playground/**`, `tools/**`, `examples/**`, bestehende Tests außerhalb von
  `experiments/symmetry_lab/tests/`.

Erwarteter Diff: nur Dateien unter `experiments/symmetry_lab/` (inkl. README) und
dieses Handoff-Dokument.

## 7. Erwartete Tests (headless, `experiments/symmetry_lab/tests/`)

- **Bindings:** Shift+S → Lab-Command im Lab-Kontext; im `global`-Kontext unverändert;
  Q → `Move`; ESC → `Cancel`; Slice-2-Bindings unverändert.
- **Seam-Ableitung (Charakterisierung):** `subd_cube` X → 8 Seam-Edges, Z → 8;
  `head_basemesh` X → 36.
- **Zyklus:** aus → X → Y → Z → aus mit den erwarteten Normalen; jeder Schritt genau ein
  History-Eintrag; Undo stellt jeweils die vorherige Definition exakt wieder her.
- **States (Charakterisierung):** `head_basemesh` X → `valid`; `subd_cube` Y →
  `partial`; `man_with_shoes_basemesh` X → `partial` mit genau 54 `UNPAIRED`.
- **Move über Dispatcher, ohne Fenster:** Auswahl eines gepaarten Vertex → Q → Press →
  mehrere Drags → Release: Vertex und Partner gespiegelt bewegt, genau ein
  History-Eintrag, ein Undo stellt beide Seiten exakt her.
- **Seam-Vertex:** bleibt nach Move exakt auf der Ebene.
- **Abbruch:** ESC während Drag → exakter Vorzustand, kein History-Eintrag; ESC nur
  scharf → entschärft; ESC im Leerlauf → „nicht behandelt".
- **Randfälle:** Q ohne Auswahl → nicht scharf; Klick unter Schwelle während scharf →
  kein History-Eintrag, entschärft; nach Commit entschärft (E5); Shift+S während Drag →
  ignoriert.
- **Import-Grenze** aus Slice 2 bleibt grün.

## 8. Done-Kriterien

- Neue und bestehende Lab-Tests grün; Produktions-Suite unverändert grün
  (`pytest tests --ignore=tests/test_extrude_tool.py`).
- `git diff --stat` enthält nur Dateien aus §6 „Erwarteter Diff".
- README: Steuerungstabelle ergänzt, Farblegende, Lab-Annahme E3, Befund E4, und eine
  Schritt-für-Schritt-Prüfanleitung für Manu (Windows). **Keine** Artist-Validierung
  behaupten.
- Commit-Message-Vorschlag:
  `WP-SYM-LAB-01 Slice 3: symmetry cycle, mirrored preview, symmetric Move in the Lab`

## 9. Bei Widerspruch

Anhalten und melden, nicht still lösen, insbesondere wenn:

- die Zahlen aus §7 (8/8/36 Seam-Edges, 54 ohne Partner) nicht reproduzierbar sind,
- `MoveTool` den Partner nicht mitbewegt, obwohl die Definition gesetzt ist,
- `ToolManager` sich im Live-Einsatz anders verhält als in §2 E6 beschrieben,
- Undo nach einem Symmetrie-Schritt und einem Move nicht genau je eine Handlung
  zurücknimmt,
- irgendetwas nur über Änderungen an `src/` oder Import aus `playground/` lösbar scheint.
