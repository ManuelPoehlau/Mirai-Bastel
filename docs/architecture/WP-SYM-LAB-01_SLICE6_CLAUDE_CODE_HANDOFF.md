# Handoff: WP-SYM-LAB-01 — Slice 6 (Gespiegelter Knife, headless Engine)

**An:** Claude Code
**Modell/Effort:** Opus, effort `high`
**Modus (M5):** Experiment-Build — Entscheidungen stehen in §2, jetzt wird zuverlässig umgesetzt.
**BUILD darf keine neue Erkenntnis behaupten.** Wenn beim Implementieren etwas
unerwartet anders aussieht als hier beschrieben, nicht still weiterbauen — anhalten
und melden (siehe „Bei Widerspruch" am Ende).

**Stand:** `main` @ `1825b44` (Slice 5 KEEP, 2026-09-25). Baseline: Lab-Tests +
`playground/tests/test_ad017_knife.py` + `test_ad017_knife_pick.py` → 192 passed.

**Schnitt:** Slice 6 ist **nur die headless Engine** plus Charakterisierung. Fenster,
Edge-Hover, Pfad-Vorschau und Tastenbindung folgen in Slice 7. Slice 6 ist deshalb
nicht vom Artist spielbar — das ist gewollt: Erst muss belegt sein, dass ein
gespiegelter Schnitt die Symmetrie überhaupt überlebt.

---

## 1. Referenzdokumente (gelten, nicht neu verhandeln)

- Handoffs Slice 2–5 von `WP-SYM-LAB-01` — alle Entscheidungen gelten weiter
  (kein Import aus `playground/`, keine Änderung an `src/`, E1–E15, A1–A7).
- `docs/architecture/AD-017_FINAL_DECISIONS_2026-09-22.md` §6–§8 — Knife-Interaktionsmodell
  und Session-History (Klick = nächster Schnitt, Undo = letzter Schnitt, Cancel = alles
  verwerfen, Commit = ein History-Eintrag).
- `docs/architecture/AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md` §2.1 — eine
  symmetrische Operation ist eine Operation-Instanz, nicht zwei.
- `docs/research/symmetry/SYMMETRY_DESIGN_BRIEF.md` — INV-4 (die Seam ist, was überlebt),
  INV-5 (nie auf unbekannten Partner spiegeln), INV-6 (Gegenseite aus der Absicht),
  INV-7 (eine Handlung, ein Schritt); Zeile **Knife** in der Operations-Tabelle.
- `docs/research/symmetry/SYMMETRY_EVOLUTION_RESEARCH.md` §5 E4, §8.2, §12 („Connect oder
  Knife?").
- `docs/research/symmetry/SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md` §3.2 (Wings: Naht pro
  Operation pflegen), §5 (kein DCC vergibt Partnerschaft zum Entstehungszeitpunkt).

## 2. Entscheidungen

### Artist (Manu, 2026-09-25)

- **A8 — Pfad-Fall ist Knife, nicht Connect** (beantwortet Evolution §12 „Priorität").
  Taste **C** startet Knife im Lab, **Klick ins Leere** committet. *Umsetzung der Taste
  erst in Slice 7*; hier nur festgehalten.
- **A9 — Operationskontext ist die primäre Korrespondenz.** Knife weiß, was es gerade
  getan hat; daraus wird das Spiegelziel bestimmt. Position und Topologie sind
  **unabhängige Validierung**, keine Quelle. Ausdrücklich **keine** Architekturentscheidung
  über die künftige Capability — nur die Regel dieses Experiments.
- **A10 — Knife nur bei `valid`.** Ist Symmetrie an und der Zustand nicht `valid`, wird die
  Session gar nicht erst begonnen. Knife bei `partial` ist eine offene Frage für später.
- **A11 — Validierung schlägt fehl → Schritt ablehnen und zurückrollen, mit Meldung.**

### Engineering (in diesem Handoff festgelegt)

- **E16 — Lab-Kopie statt Import.** `playground/topology_tools/knife.py` und
  `connect_in_shared_face` aus `playground/topology_tools/topology_points.py` werden als
  `experiments/symmetry_lab/lab_knife.py` kopiert und adaptiert, mit Herkunftsvermerk im
  Docstring (Präzedenz AD-010, wie die Draw-Stücke). Die Klasse erbt weiter von
  `mirai.interaction.tool.Tool`. `knife_pick.py` wird erst in Slice 7 gebraucht. Das
  Playground-Original bleibt unverändert.

- **E17 — Partner-Auflösung (A9).** Die Session führt eine Absichts-Paarung
  `intent_pairs: dict[VertexId, VertexId]` (Involution; selbst-gepaart erlaubt), die Teil
  jedes Session-Schritts ist (Undo/Redo stellen sie mit wieder her). `partner(v)`:
  1. `v` in `intent_pairs` → dieser Partner (in der Session erzeugt — Operationskontext).
  2. sonst `v` ist Endpunkt einer gültigen deklarierten Seam-Edge → `v` selbst.
  3. sonst Capability-Korrespondenz (`mirai.symmetry.vertex_correspondence`) ist `PAIRED`
     → deren Partner. (Bestehende Geometrie: Knife hat sie nicht erzeugt, also gibt es
     keinen Operationskontext. Bei `valid` (A10) ist diese Paarung vollständig und exakt.)
  4. sonst nicht auflösbar → Schritt abgelehnt.

  `partner_edge(e)` = die Edge zwischen `partner(a)` und `partner(b)`; existiert keine →
  abgelehnt. `partner_edge(e) == e` genau dann, wenn `e` eine Seam-Edge ist.

- **E18 — Ein Klick = ein Schritt mit beiden Seiten** (alles innerhalb **eines**
  `_push_step`):
  - **Vertex-Klick ohne Start:** Start = `v`. `partner(v)` muss auflösbar sein.
  - **Edge-Klick** (Split bei `t`):
    - Quelle: `split_edge(e, t)` → neuer Vertex `n`.
    - Ist `e` Seam-Edge: **kein** Spiegel-Split. `n` ist selbst-gepaart. Die Seam-Deklaration
      wird im selben Schritt nachgeführt: die tote `e` raus, die beiden neuen Halb-Edges
      rein (neue `SymmetryDefinition` mit gleicher Ebene). Die Achsenkomponente von `n`
      muss exakt `0.0` sein; sonst → Validierung schlägt fehl (E19).
    - Sonst: `split_edge(partner_edge(e), 0.5)` → `n'`, danach
      `set_vertex_position(n', mirror_position(pos(n)))`. **Nicht** über gespiegeltes `t`
      (Befund P3, §7). `intent_pairs[n] = n'`, `intent_pairs[n'] = n`.
  - **Connect** (nach Vertex- oder Edge-Klick mit Start): Quelle wie heute über
    `connect_in_shared_face`, aber die Lab-Kopie gibt zusätzlich die benutzte Face zurück.
    Spiegel-Connect `partner(start) → partner(ziel)` in **der** Face, deren Vertex-Menge das
    Partnerbild der Quell-Face ist (nicht „niedrigste FaceId"). Keine solche Face → abgelehnt.
  - **Selbstgespiegelt:** Ist `{partner(start), partner(ziel)} == {start, ziel}`, entsteht
    die Verbindung genau einmal (kein Spiegel-Connect).
  - **Seam-Sehne:** Sind Start **und** Ziel Seam-Vertices, wird der Schritt abgelehnt
    (Meldung „Schnitt entlang der Seam nicht unterstützt"). Grund: Die Spiegel-Face würde
    dieselbe Vertex-Verbindung ein zweites Mal verlangen. Vorbild: Maya sperrt die Seam für
    Multi-Cut. Artist-Semantik dazu ist offen (§5).
  - Scheitert irgendein Teil → Rollback des ganzen Schritts über den gerade gepushten
    Snapshot (bestehendes Knife-Muster), Meldung, `click()` → `False`.

- **E19 — Validierung nach jedem Schritt (A9/A11).** Nach der Mutation beider Seiten,
  noch im selben `click()`:
  - **Position:** Für jedes Paar `x ↔ y` in `intent_pairs` mit `x ≠ y` meldet die
    Capability `PAIRED` mit Partner `y`; jeder selbst-gepaarte `x` ist `SEAM`.
  - **Topologie:** `lab_topology.topological_pairing(mesh).partners` bildet jedes Paar
    aus `intent_pairs` identisch ab.
  - **Gesamt:** `symmetry_state == VALID`, genau 2 Seiten (`component_count == 2`),
    0 Konflikte.

  Schlägt eine Prüfung fehl → Schritt zurückrollen (Mesh, Start, Pfad, `intent_pairs`
  bitgenau wie vorher), Meldung nennt die gescheiterte Prüfung (`Position` / `Topologie` /
  `Seam`/`Seiten`). Das Prüfergebnis ist als Datenobjekt abrufbar (für Tests und später
  die Statuszeile), nicht nur als Print.

- **E20 — Gate beim Session-Beginn (A10).** Symmetrie aus → Knife läuft ungespiegelt wie
  im Playground (keine Validierung). Symmetrie an und nicht (`valid` **und** 2 Seiten) →
  `begin` abgelehnt, keine Session, Meldung.

- **E21 — History unverändert.** In-Session-Undo/Redo wie im Playground (ganze Snapshots,
  jetzt inkl. `intent_pairs` und Seam-Definition). Commit → genau ein `MeshStateCommand`
  (enthält die nachgeführte Seam, weil `symmetry_definition` Teil von `export_state()`
  ist). Cancel → Zustand vor der Session, kein Eintrag. Unverändert → kein Eintrag.

- **E22 — Kein Auswahl-Residue im Lab.** Das Lab hat keinen Edge-Modus; Knife berührt
  `scene.selection` nicht. (AD-017-Residue bleibt Playground-Verhalten; ob das Lab eins
  braucht, zeigt Slice 7.)

## 3. Ziel dieses Slices

Headless belegen: Eine Knife-Session auf `subd_cube` und `head_basemesh` (Symmetrie X)
schneidet beidseitig, jeder Schritt bleibt `valid`, die Seam überlebt Schnitte durch
sie, und die Absichts-Paarung wird von Position **und** Topologie bestätigt — oder der
Schritt wird ehrlich abgelehnt.

## 4. Scope

1. `lab_knife.py` (E16–E22), rein und GL-frei. Docstring: **Lab-Experiment**, keine
   Capability; Verweis auf dieses Handoff, AD-017, AD-SYM-02, INV-4/5/6.
2. Validierung (E19) als reine Funktion, damit Tests und Slice 7 dieselbe Prüfung benutzen.
3. Charakterisierungstests der drei Befunde aus der Untersuchung (§7).
4. README: neuer Abschnitt „Gespiegelter Knife — Lab-Experiment (Slice 6, headless)":
   was, warum (A9), Seam-Nachführung, Grenzen, Befunde P1–P3. **Keine** Steuerung,
   **keine** Artist-Validierung behaupten.
5. `docs/research/symmetry/SYMMETRY_EVOLUTION_RESEARCH.md` §12, Punkt „Priorität":
   ergänzen „Artist-Entscheidung 2026-09-25: Knife (A8, WP-SYM-LAB-01 Slice 6)". Sonst
   nichts an dem Dokument.

## 5. Not in scope

- Fenster, Rendering, Edge-Hover/-Picking, Pfad-Vorschau, Bindings (Slice 7).
- Face-Cut (AD-017 §6 offen), Preview-UX (AD-017 §9 offen).
- Knife bei `partial`/`violated`/`ambiguous` (A10).
- Reparatur oder Änderung von `lab_topology.py` — Befund P2 wird nur charakterisiert.
- Toleranz jeder Art (A5).
- Seam-Sehnen-Semantik, Schnitte, die den Spiegelpfad ansteuern (§7, nur beobachten).
- Promotion nach `src/`, Änderungen am Playground-Knife, RigController-Anbindung.

## 6. Must NOT change (Diff muss hier leer sein)

- `src/**`, `playground/**`, `tools/**`, `examples/**`, Tests außerhalb von
  `experiments/symmetry_lab/tests/`, `experiments/symmetry_lab/lab_topology.py`.

Erwarteter Diff: neue/geänderte Dateien unter `experiments/symmetry_lab/` (inkl. README),
die eine Zeile in `SYMMETRY_EVOLUTION_RESEARCH.md` §12 und dieses Handoff-Dokument.

## 7. Erwartete Tests (headless)

**Charakterisierung** (Ebene X, Seam aus E3; Zahlen aus der Untersuchung, Wegwerf-Probe
gegen `1825b44`):

| Befund | `subd_cube` | `head_basemesh` |
|---|---|---|
| Baseline | `valid`, topo 26/26, Seiten 12/12 | `valid`, topo 326/326, Seiten 162/162 |
| **P1** Seam-Edge roh splitten (ohne Nachführung), t=0.37 | Vertex x = 0.0; `partial`; Seam 7/8 gültig; **1 Seite** | x = 0.0; `partial`; Seam 35/36; **1 Seite** |
| **P2** einseitiger Schnitt split(0.3) + split(0.6) + connect in einer +X-Quad | topo **0/28**, 28 Konflikte, 40 Face-Paar-Konflikte | topo **0/328**, 328 Konflikte, 644 Face-Paar-Konflikte |
| **P3** gespiegelter Schnitt über `1−t` (Kanten hier umgekehrt orientiert) | ein Spiegelpunkt 1.1e-16 daneben → `partial`, topo 30/30 | exakt → `valid` |
| **P3′** Spiegelpunkt über `mirror_position` (E18) | `valid`, topo 30/30, Seiten 13/13 | — |

Gegenprobe zu P2 (deckt sich mit Slice-5-README): einseitiger `split_edge` allein →
topo 326/327; einseitiger `connect_vertices` allein → Positionszustand `valid` bei
asymmetrischer Topologie. Die P2-Ursache ist **nicht** untersucht — Test hält den Befund
fest; eine Erklärung darf in die README, nur wenn sie ohne Code-Änderung an
`lab_topology.py` belegt ist.

**Verhalten (E16–E22):**

- Gespiegelter Schnitt Edge→Edge in einer +X-Quad (`subd_cube`, `head_basemesh`) → `valid`,
  topo 30/30 bzw. 330/330, Seiten 13/13 bzw. 163/163; alle Paare aus `intent_pairs` von
  Position und Topologie bestätigt.
- Session mit ≥3 Schritten bleibt nach jedem Schritt `valid`; Commit → genau ein
  History-Eintrag; Undo → `export_state()` bitgleich zum Vorher-Zustand; Redo → bitgleich
  zum Nachher-Zustand.
- In-Session-Undo nimmt beide Seiten eines Schritts zurück (inkl. `intent_pairs`);
  In-Session-Redo stellt beide wieder her.
- Cancel → bitgleich zum Zustand vor der Session, kein Eintrag.
- **Seam-Punkt:** Schnitt von einem +X-Edge-Punkt auf eine Seam-Edge → neuer Vertex
  selbst-gepaart, Achsenkomponente exakt 0.0; Seam-Definition enthält die zwei Halb-Edges
  und nicht mehr die tote Edge; 2 Seiten; `valid`. Undo stellt die alte Seam-Definition
  wieder her.
- **Über die Mitte:** Start auf Seam-Vertex, Schnitt in beide Richtungen → beide Seiten
  gespiegelt, `valid`.
- **Selbstgespiegelt / Spiegelpfad ansteuern:** Nach Schnitt `a → m` (m auf der Seam)
  Klick auf `a'` (existiert bereits als Spiegelpunkt) → Verhalten festhalten (erwartet:
  abgelehnt, weil die Verbindung schon existiert; Meldung nennt das). Kein Crash, kein
  doppelter Edge. Nur beobachten, keine Sonderlogik erfinden.
- **Seam-Sehne:** Seam-Edge splitten (m), dann Start `s1`, Klick `s2` (beide Seam-Vertices
  derselben Face, nicht benachbart) → abgelehnt, Mesh unverändert.
- **Gate (E20):** `man_with_shoes_basemesh` X (`partial`) → `begin` abgelehnt; `subd_cube` Y
  → abgelehnt; Symmetrie aus → Knife läuft ungespiegelt (Teilmenge der Playground-Knife-Tests
  als Portierung).
- **Rollback (A11):** Platzierung künstlich auf `1−t` umstellen (Monkeypatch in `subd_cube`,
  Befund P3) → Validierung `Position` scheitert, Schritt zurückgerollt, Mesh + Start + Pfad +
  `intent_pairs` bitgleich wie vorher, Meldung nennt `Position`.
- Alle bisherigen Lab-Tests und die Import-Grenze bleiben grün.

## 8. Done-Kriterien

- Lab-Tests grün; Produktions-Suite unverändert grün
  (`pytest tests --ignore=tests/test_extrude_tool.py`); Playground-Knife-Tests unverändert grün.
- `git diff --stat` enthält nur Dateien aus §6 „Erwarteter Diff".
- README-Abschnitt wie §4.4; Befundtabelle P1–P3 übernommen.
- Commit-Message-Vorschlag:
  `WP-SYM-LAB-01 Slice 6: mirrored Knife engine, intent correspondence + validation (lab-local, headless)`

## 9. Bei Widerspruch

Anhalten und melden, nicht still lösen, insbesondere wenn:

- eine Charakterisierungszahl aus §7 nicht reproduzierbar ist,
- ein gespiegelter Schnitt mit Platzierung über `mirror_position` **nicht** `valid` ist,
- die Seam-Nachführung nur mit einer Änderung an `src/` möglich wäre
  (`SymmetryDefinition` ist frozen — eine neue Instanz setzen ist erlaubt, eine
  Klassenänderung nicht),
- Position und Topologie für einen Schritt **unterschiedlich** urteilen (eine bestätigt,
  die andere nicht) — das ist ein Befund, kein Bug: festhalten und melden,
- sich irgendetwas nur mit Import aus `playground/` lösen lässt.

---

## Ausblick Slice 7 (nicht Teil dieses Handoffs)

Binding **C** → Lab-Command `Knife` (C ist im Lab-Kontext frei; global nur im
Topology-Kontext an `Connect` gebunden). Edge-Hover/-Picking über `mirai.viewport.picking`
(Lab-Kopie von `knife_pick`), Pfad + gespiegelter Pfad sichtbar während des Zeichnens,
abgelehnte Spiegelziele vor dem Klick erkennbar (Design Brief, Zeile Knife),
Klick auf `outside` → Commit, ESC → Cancel, Validierungs-Meldungen in der Statuszeile,
manuelle Prüfanleitung für Manu.
