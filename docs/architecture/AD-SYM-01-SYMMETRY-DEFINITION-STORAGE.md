# AD-SYM-01 — Symmetry Definition Storage

**Status:** PROPOSED — Architekturreview ausstehend (Core-Freeze §7)
**Datum:** 2026-09-24
**Modus (M5):** Production-Planung. Keine Implementierung.
**Gehört zu:** WP-SYM-01 (Symmetry V1 Kern)
**Grundlage (unverändert, nur verlinkt):**
- `docs/research/symmetry/SYMMETRY_DESIGN_BRIEF.md` — INV-1, INV-2, INV-3, INV-4, §2 (Begriffe), §4 (Layer)
- `docs/research/symmetry/SYMMETRY_EVOLUTION_RESEARCH.md` — §3.2, §10 (Future-Proofing), AR-1, AR-3, AR-7, AR-12
- `docs/architecture/CORE_V1_FREEZE.md` §7 (Freeze-Regel), §7.1 (Präzedenzfälle)
- AD-001 (stabile, nie wiederverwendete IDs)

**Frage:** Wo lebt die dauerhafte Symmetry Definition (Plane + deklarierte Seam-Element-IDs)?

---

## 1. Bestehender Fakt

Alles in diesem Abschnitt ist im Code auf `main` nachgelesen, nicht angenommen.

**[FAKT·Code] `src/core/scene.py`** hält `mesh`, `selection`, `history` sowie drei
reservierte, in V1 auf `None` stehende Subsystem-Plätze (`morph_targets`, `rig`,
`animation`). Der dokumentierte Vertrag lautet, dass spätere Subsysteme *ergänzt*
statt das Format umgebaut wird.

**[FAKT·Code] `src/core/serialization.py`** schreibt diese reservierten Plätze mit
(`FORMAT_VERSION = 1`). Selection und History sind bewusst nicht persistiert
(transienter Session-Zustand).

**[FAKT·Code] `src/core/mesh.py`** besitzt `export_state()` / `load_state()`.
`load_state()` leert sämtliche internen Container und baut sie vollständig neu auf;
die Allocator-Zähler werden ausschließlich vorwärts gesetzt.

**[FAKT·Code] `src/core/operations/topology.py`** (`MeshStateCommand`) realisiert
Undo/Redo atomarer Topologie-Mutationen als vollständige Vorher-/Nachher-Snapshots
des Mesh — ausdrücklich, weil eine semantische Gegenoperation wegen AD-001 niemals
dieselben IDs zurückgeben könnte.

**[FAKT·Code] AD-001 / `src/core/ids.py`:** IDs werden innerhalb einer Session nie
wiederverwendet. Eine gespeicherte Seam-ID kann daher nie stillschweigend auf ein
*anderes*, später entstandenes Element zeigen. Sie ist entweder gültig oder tot —
nie falsch. Das ist die technische Basis dafür, dass INV-1 (deklarierte Seam über
Identität) in Mirai billig zu haben ist, und dass AR-3 (Seam über Position) nicht
nötig ist.

**[FAKT·Code] `src/mirai/application.py`** ersetzt in `init_scene()` die gesamte
Mesh-Instanz (`self.scene.mesh = create_cube()`). Ein an der Scene hängender
Zustand überlebt diesen Austausch, obwohl sein ID-Raum mit dem alten Mesh
verschwunden ist.

**[FAKT·Code] Core-Freeze §7** verlangt vor jeder Core-Änderung sechs Schritte:
Anforderung benennen → Lösbarkeit mit bestehender API prüfen → Problem dokumentieren
→ kleinste Erweiterung bestimmen → Tests/Vertrag ergänzen → erst dann ändern.
Dieses Dokument leistet Schritt 1–4.

### 1.1 Gemessener Befund (reproduzierbar)

Ein Probe-Lauf gegen den echten Core zeigt die entscheidende Eigenschaft, die die
Wahl des Speicherorts bestimmt:

```text
Quad-Face, Seam deklariert als EdgeId(0)
split_edge(EdgeId(0))  →  EdgeId(0) ungültig, neu: EdgeId(4), EdgeId(5)
  eine Operation, die die Seam mitführt, setzt Definition.seam = {4, 5}
MeshStateCommand.undo()
  → Mesh:       EdgeId(0) wieder gültig, EdgeId(4)/(5) verschwunden
  → Definition: zeigt weiterhin auf {4, 5}  →  beide ungültig
```

**[SCHLUSS]** Sobald eine Operation die Seam mitführt, ist die Definition Teil des
Zustands, den ein Undo zurücknehmen muss. Ein Speicherort *außerhalb* des
Mesh-Snapshots desynchronisiert sich beim ersten Undo einer Topologie-Operation.

**[OFFEN — bewusst nicht durch Annahme geschlossen]** Ob eine V1-Operation die Seam
überhaupt mitführen *muss*, ist heute nicht beweisbar: Extrude existiert in `src/`
nicht (nur ein Testfile `tests/test_extrude_tool.py` gegen einen Experiment-Stand).
Die Research legt es nahe (R1 §3.5: Wings löst beim Extrude angrenzende Faces in die
Naht auf und die entstehende Fläche wird *neue* Naht), aber für Mirais künftiges
Extrude ist es unbewiesen. Deshalb muss der Speicherort den Fall *ermöglichen*,
ohne ihn vorauszusetzen.

---

## 2. Notwendige Erweiterung

Der kleinste Bedarf, der sich aus §1 ergibt — vier Eigenschaften, keine Datenstruktur:

1. **Ein Ort** für genau zwei Dinge: Symmetry Plane und deklarierte Seam-Element-IDs.
   Nichts weiter. Correspondence und Symmetry State werden abgeleitet (INV-3) und
   sind ausdrücklich **kein** zweiter dauerhafter Wahrheitszustand (AR-1).
2. **An den ID-Raum des Mesh gebunden.** Eine Seam-ID ist nur in genau dem Mesh
   sinnvoll, dessen Allocator sie vergeben hat.
3. **Überlebt einen Mesh-Austausch nicht.** Wird das Mesh ersetzt, muss die
   Definition mit verschwinden, statt auf einen toten ID-Raum zu zeigen.
4. **Nimmt an Undo/Redo teil**, solange nicht bewiesen ist, dass keine V1-Operation
   die Seam verändert (§1.1).

Zusätzlich aus der Research, als Randbedingung an die Formulierung:
- **AR-7:** Die Definition muss von *anderen* Systemen abfragbar sein, nicht nur vom
  Edit-Mode-Tool. Sie darf keine UI-/Tool-Einstellung werden.
- **AR-12:** Die Definition braucht einen Geltungsbereich. V1 hat genau einen
  (das Mesh-Objekt); eine spätere Erweiterung auf mehrere Inseln darf dadurch nicht
  ausgeschlossen werden.

### 2.1 Zwei geprüfte Optionen

| | **A — Definition im Mesh** | **B — Definition an der Scene** |
|---|---|---|
| Bedingung 2 (ID-Raum) | erfüllt per Konstruktion | nur per Konvention |
| Bedingung 3 (Mesh-Austausch) | erfüllt per Konstruktion | **verletzt** (§1 `init_scene`) |
| Bedingung 4 (Undo) | erfüllt, sobald die Definition Teil von `export_state()`/`load_state()` ist — `MeshStateCommand` trägt sie dann ohne neue Maschinerie mit | **verletzt** (§1.1); verlangt ein neues, zusammengesetztes Command |
| Passt zum dokumentierten Erweiterungsmuster | nein — Mesh ist als reines Topologie-Domain-Modell dokumentiert | ja — reservierte Subsystem-Plätze |
| Neue Architektur nötig | keine | ja (Composite-Command) |
| Präzedenz in der Research | Wings: `mirror` ist ein Feld der Winged-Edge-Struktur `#we{}` und zeigt auf genau ein Topologie-Element (R1 §3.5) | C4D: Naht als Selection-Tag am Objekt (R1 §3.4) |

**[SCHLUSS]** Option B erkauft die sauberere Schichtung mit genau dem Fehler, den
INV-5 verbietet: eine Definition, die nach einem Undo etwas behauptet, was das Mesh
nicht mehr hergibt. Die Reparatur dafür wäre neue Command-Maschinerie — also mehr
neue Architektur, nicht weniger.

---

## 3. Entscheidung

> **Die Symmetry Definition wird im Mesh gespeichert (Option A) und ist Teil von
> `export_state()` / `load_state()`.**

Mit einer ausdrücklichen Grenze, die den Einwand gegen Option A adressiert:

> **Das Mesh *besitzt* die Symmetrie-Deklaration, aber *kennt* keine Symmetrie-Semantik.**
> Es speichert, serialisiert und trägt sie durch `load_state()` — es spiegelt nicht,
> leitet keine Correspondence ab, berechnet keinen State und prüft keine Invarianten.
> Jede Symmetrie-*Logik* lebt oberhalb des Core-Mesh.

Begründung in einem Satz: Das Mesh ist bereits heute der Eigentümer von
Element-Identität und deren Persistenz — und die Seam *ist* nichts anderes als eine
Menge von Element-Identitäten.

**Folgen, die damit ohne neue Maschinerie erfüllt sind:** INV-1 (deklariert, über
Identität), INV-4 (die Definition überlebt Operationen bzw. wird erkennbar ungültig),
Bedingungen 2–4 aus §2, Vermeidung von AR-1 und AR-3.

**Was diese Entscheidung ausdrücklich nicht behauptet:** dass die Definition dadurch
*gepflegt* wird. Sie wird nur *mitgeführt*. Ob eine Operation die Seam aktualisiert
und wie, ist AD-SYM-02 und WP-SYM-01, nicht dieses Dokument.

### 3.1 Prozess-Status

Dies ist eine Änderung am gefrorenen Core und daher **noch nicht wirksam**. Offen
nach Core-Freeze §7:
- Schritt 5 (Tests/Vertrag ergänzen) — Teil von WP-SYM-01
- Architekturreview. Präzedenz AD-017: ein **unabhängiges** Review vor der
  Umsetzung, archiviert vor der Diskussion (AGENTS.md §6). Erzeuger und Bewerter
  sollen getrennt sein — dieses Dokument ist vom Vorschlagenden geschrieben und
  ersetzt kein Review.

---

## 4. Bewusst NICHT entschieden

- Feld- und Typnamen, konkrete Datenstruktur.
- Ob die Seam als Edge-IDs, Vertex-IDs oder beides deklariert wird. (Die Research
  zeigt beide Wege: Maya Seam-Edge, Wings Naht-*Fläche*.)
- Repräsentation der Plane (Punkt + Normale vs. Achse + Offset vs. anderes).
- Ob `FORMAT_VERSION` erhöht wird oder die Definition als optionaler Schlüssel
  additiv eingeführt wird.
- Ob die positionsbasierte **Vorschlagshilfe** beim Erklären der Symmetrie im Core
  oder darüber lebt. (Evolution §3.2 erlaubt sie ausdrücklich als Vorschlag, nie als
  Definition.)
- Mehrere Definitionen pro Mesh / mehrere Inseln — V1 hat genau eine (Non-Goal,
  Evolution §4). Die Entscheidung schließt eine spätere Erweiterung nicht aus.
- Ob Correspondence jemals gecacht wird. V1: abgeleitet, kein gespeicherter Zustand
  (INV-3, AR-1).
- Ob es je einen Modus mit abgeleiteter Hälfte gibt (Non-Goal V1).

---

## 5. Verhältnis zu AD-SYM-02

Siehe AD-SYM-02 §5. Kurz: **nicht unabhängig.** Diese Entscheidung muss zuerst
fallen, weil sie bestimmt, wie viel AD-SYM-02 überhaupt leisten muss.
