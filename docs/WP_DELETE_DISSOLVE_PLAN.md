# Work Package: WP Delete/Dissolve

**An:** Claude Code
**Modell/Effort:** Opus, effort `high` (nicht Claude Codes Medium-Default — Core-Freeze-Territorium
`src/core/mesh.py` mit ID-Kontinuität-Pflicht und mehreren Topologie-Randfällen wie 2er-Vertices,
face-lose Kanten, Region-Grenzen; dieselbe Klasse Arbeit, bei der im Knife-Strang mehrfach erst
durch sorgfältiges Durchdenken Überraschungen vermieden wurden)
**Status:** Umgesetzt (2026-10-06) — PROVISIONAL, Verdikt UNKNOWN bis zu Manus Praxis-Check (siehe "Status-Update 2026-10-06" am Ende)
**Datum:** 2026-10-06 (final nach Manus Entscheidungen zu Weg, Varianten und Default-Bindung)
**Modus (M5):** Production, Core-first — **kein Lab**. Vorbild: `WP-KNIFE-00`
(`Mesh.split_face` wurde direkt als eigenständiges Core-Paket gebaut, weil seine Form schon klar
war). Begründung für den direkten Weg (Artist-Attention-Filter, Stufe 3 bereits erfüllt): Manu hat
Delete/Dissolve/Cleanup in dieser Form bereits in Blender selbst in der Hand gehabt; die künstlerische
Bewertung hat dort schon stattgefunden. Ein Lab mit Verdikt-Zeremonie entfällt; ein einziger
Praxis-Check am Ende des gesamten Pakets ersetzt die sonst üblichen Per-Slice-Checks.
Core bleibt davon unberührt: Core Freeze, Kontrakttest und `CORE_V1_FREEZE.md`-Eintrag gelten
unabhängig vom gewählten Weg.
**Grundlage:** `Geometrie-Entfernung_als_Modeling-Paradigma_Research_V1.md`,
Gegenstück `Geometrie-Hinzufuegen_als_Modeling-Paradigma_Research_V1.md`

---

## 0. History Awareness (M1) / Context Check (M2)

### 0.1 Existenzprüfung

| Existiert | Wo | Bedeutung für dieses Paket |
| --- | --- | --- |
| `Mesh.collapse_edge` | `src/core/mesh.py` | Zusammenführen — bleibt unberührt, ist nicht Teil dieses Pakets |
| `Mesh.remove_face` | `src/core/mesh.py` | Destruktiv auf Face-Ebene, lässt Kanten bewusst stehen (V1-Entscheidung) — wird hier als Baustein wiederverwendet, nicht ersetzt |
| `Mesh.split_edge`, `connect_vertices`, `split_face` | `src/core/mesh.py` | Hinzufügen-Gegenstück, Vorbild für Docstring-Stil (ID-Kontinuität) |
| Connect/Cut-Lab-Ablauf (AD-017) | `docs/architecture/AD-017*`, `docs/design/artist_playground/WP-AP-CUT_PLAN.md` | Vorbild für diesen Plan: Core-Primitive + Lab-Bindung + Artist-Test + Verdikt vor Promotion |
| Research zu Entfernen/Hinzufügen | `docs/research/Geometrie-Entfernung...md`, `...Hinzufuegen...md` (noch einzupflegen) | Grundlage für §1, §3 dieses Pakets |
| Delete/Dissolve als Primitive | — | **Existiert nicht.** Einziges Entfernen heute ist Collapse. |

**Verworfenes:** nichts — dies ist Neuland.

### 0.2 Bereits getroffene Entscheidungen (Chat, 2026-10-06) — hier nur umgesetzt

1. **Zwei Tasten statt Menü**, wie in 3ds Max: eine Taste destruktiv (Delete, erzeugt ein Loch),
   eine Taste bewahrend (Dissolve, Fläche bleibt geschlossen).
2. **Cleanup ist eine reine Varianten-/Hotkey-Frage, pro Elementebene unterschiedlich geformt**
   (präzisiert 2026-10-06, nach Blender-Vorbild, ersetzt die ursprüngliche "Backspace/Ctrl"-Fassung):
   - **Edge-Dissolve** und **Face-Dissolve** haben je **zwei Varianten**: mit Cleanup (übrig
     bleibende 2er-Vertices werden entfernt) und ohne Cleanup (sie bleiben stehen). Beide Varianten
     sind gleichwertige, eigenständige Operationen — welche davon auf die "einfache" Taste und
     welche auf eine Modifier-Taste gelegt wird, ist **reine Bindungs-Config** (analog
     AD-013/Artist Input Truth), jederzeit umbindbar, nicht Teil der Operation selbst.
   - **Vertex-Dissolve** hat **keine Variante** — es gibt dort nichts zusätzlich aufzuräumen, das
     nicht schon Teil der einen Operation wäre (wie in Blender: die Dissolve-Vertices-Option
     existiert dort nur im Kontext von Edge- und Face-Dissolve, nicht für Vertex-Dissolve selbst).
3. **Face-Region-Löschen:** Wird eine zusammenhängende Face-Region destruktiv entfernt, sollen die
   dadurch face-los gewordenen **inneren** Kanten automatisch mit entfernt werden (nicht die äußeren,
   noch von Nachbar-Faces genutzten Randkanten).
   *Präzisiert 2026-10-06 (Manu, nach der Umsetzung):* Jede Kante, die nach dem Löschen an keiner
   Face mehr hängt, wird entfernt — auch eine frühere Mesh-Randkante. Eine Kante, die noch von einer
   anderen Face gebraucht wird, bleibt. "Eine Kante, die sinnlos in der Luft schwebt, kommt weg."
   Vertices, die dadurch keine Kante mehr haben, gehen mit. Das korrigiert die beiden 2×2-Sätze
   unter §Tests und §Practical viewport test, die eine Nachbar-Face an jeder Außenkante annahmen.
4. **Weg:** Production, Core-first, kein Lab (siehe Kopfzeile). Ein einziger Praxis-Check am Ende
   des gesamten Pakets, keine Per-Slice-Checks. Zeigt sich beim Testen etwas Ungewöhnliches, wird
   das dann gezielt untersucht und behoben (M5: eine dabei auftauchende neue Erkenntnis ist eine
   offene Frage für den jeweiligen Punkt, keine stille Entscheidung im Bauen) — kein Grund, deshalb
   nachträglich doch ein Lab aufzusetzen.
5. **Default-Bindung (final):** Backspace räumt auf (Edge- und Face-Dissolve); Ctrl+Backspace räumt
   nicht auf. Gilt für beide Ebenen gleich.

### 0.3 Context Check — meine Annahmen (nur korrigieren, wenn falsch)

1. "Entf" als destruktive Taste ist ein Platzhalter — die tatsächliche Taste hängt von der
   Pyglet-/Betriebssystem-Zuordnung ab und wird beim Bauen geprüft, nicht hier festgelegt.
2. Reihenfolge: alle drei Elementebenen (Vertex/Edge/Face) **in einem Rutsch**, wie von dir
   gewünscht — nicht nacheinander als separate Pakete.
3. Analog zur Face-Region-Delete-Frage (Punkt 3) nehme ich an, dass Vertex-Delete (destruktiv)
   ebenfalls keine zusätzliche Cleanup-Frage aufwirft: Entfernt man einen Vertex destruktiv, gehen
   alle anliegenden Kanten und Faces zwingend mit (eine Kante kann nicht mit nur einem Endpunkt
   existieren) — das ist Teil der Operation selbst, keine Variante.

---

## Goal

Destruktives Entfernen (Delete) und bewahrendes Entfernen (Dissolve) auf Vertex-, Edge- und
Face-Ebene direkt in der Production-App verfügbar machen — als Gegenstück zu den bestehenden
Hinzufügen-Operationen (Connect, Split, Knife, Extrude) und zur bestehenden Collapse-Operation,
mit der Cleanup-Varianten-Struktur nach §0.2.

## Why now

Mirai hat bei Geometrie-**Hinzufügen** bereits ein breites Werkzeugset (Connect, Split, Knife,
Extrude, Loop Insert), bei Geometrie-**Entfernen** bisher ausschließlich Collapse. Die beiden
Begleit-Research-Dokumente markieren Delete/Dissolve als die am meisten fehlende Operationsfamilie.
Drei Grundsatzfragen sind bereits entschieden (§0.2) — eine weitere Grundsatzdiskussion ist vor
dem Bauen nicht nötig.

## Scope

**Core — neue Primitive** (Docstring-Stil und ID-Kontinuität-Dokumentation wie bei
`collapse_edge`/`remove_face`, analog zum eigenständigen Core-Zuschnitt von `WP-KNIFE-00`):

- `dissolve_vertex(vertex_id)` — **eine** Operation, kein Cleanup-Parameter. Vertex weg, anliegende
  Faces verschmelzen zu einer Face (N-Gon).
- `dissolve_edge(edge_id, cleanup: bool)` — Kante weg, beide anliegenden Faces verschmelzen.
  `cleanup=True` entfernt die beiden Endpunkte, falls sie danach nur noch zwei Kanten haben
  (2er-Vertex); `cleanup=False` lässt sie stehen. **Kein Default** auf Core-Ebene — beide Varianten
  sind gleichrangig, der Default ist eine Bindungs-Entscheidung, keine Core-Entscheidung.
- `dissolve_faces(face_ids, cleanup: bool)` — eine oder mehrere zusammenhängende Faces
  verschmelzen zu einer Face (Innenkanten weg). Für eine einzelne Face ohne Nachbarn in der
  Auswahl: kein Effekt (nichts zu verschmelzen) — sauber behandeln, kein Fehler nötig.
- **Delete-Seite:** `remove_face` existiert bereits (destruktiv, Face-Ebene). Für dieses Paket
  wird geprüft, ob eine schlanke Zusatzfunktion reicht (`remove_face` + "entferne alle danach
  face-losen Kanten/Vertices der betroffenen Region", §0.2 Punkt 3) oder ob Vertex-/Edge-Delete
  eigene Core-Primitive brauchen (Vertex-Delete = 1-Ring entfernen; Edge-Delete = beide
  anliegenden Faces entfernen). Entscheidung fällt beim Bauen, mit demselben Dokumentationsstandard.

**Production (`src/mirai/`), analog zum bestehenden `C`-Kontext-Mechanismus (AD-017):**

- Tasten, Bindung als Artist Input Truth (PROVISIONAL, über Config jederzeit änderbar):
  - **Delete** (destruktiv) — in allen drei Komponentenmodi (Vertex/Edge/Face)
  - **Backspace** = Dissolve mit Cleanup (Edge/Face); bei Vertex die einzige Dissolve-Operation
  - **Ctrl+Backspace** = Dissolve ohne Cleanup (nur Edge/Face; bei Vertex ohne Wirkung, da keine
    Variante existiert)
- Face-Modus deckt sowohl eine einzelne Face als auch eine zusammenhängende Mehrfachauswahl ab.
- Kein separates Lab; Slices werden nacheinander auf `main` gebaut, wie bei `WP-KNIFE-01`.

## Not in scope

- **Dissolve Loop / Collapse Ring** als eigene, loop-bewusste Operation (bräuchte Ring-Erkennung
  wie Loop Insert) — eigenes Folgepaket, in der Research unter §4.4 der Entfernungs-Research skizziert.
- **Region-Entfernen über eine zusammenhängende Face-Auswahl hinaus** (Füllen, Bridging offener
  Ränder) — eigenes Thema.
- **Symmetrie-Verhalten** (z. B. stilles Abschalten der Spiegelung wie bei Wings, wenn die
  Naht-Fläche verschwindet) — eigene Folgefrage, siehe Entfernungs-Research §9.
- **Morph-/Gewichts-Implikationen** (ARCH-02, Rigging-Experiment) — bleiben unberührt.
- **Undo-Modell** — nutzt das bestehende Snapshot-Undo (AD-001), keine neue Mechanik.
- **Feinschliff der Auswahl nach der Operation (Residue)** über einen ersten sinnvollen Standard
  hinaus — das ist Material für den abschließenden Production-Praxis-Check, nicht hier vorab
  festgelegt.

## Dependencies

- Core (`src/core/mesh.py`) — kein offenes Architecture Gate betroffen.
- Bestehende Production-Interaction-Infrastruktur (`src/mirai/interaction/`, Artist-Input-Truth-
  Bindings, analog zum bestehenden `C`-Kontext-Mechanismus aus AD-017).
- Keine Abhängigkeit zu den laufenden Knife-, Symmetry- oder SubD-Strängen; kann parallel laufen.

## Architecture contracts

- Jede neue Core-Methode bekommt einen Docstring-Abschnitt "ID-Kontinuität" im bestehenden Stil:
  welche IDs ungültig werden, welche neu entstehen, welche erhalten bleiben.
- Kein Core-Change ohne Kontrakttest und Eintrag in `CORE_V1_FREEZE.md` §Präzedenzfälle (wie beim
  `split_edge(t)`-Präzedenzfall aus AD-017 B5).
- Die Cleanup-Entscheidung ist **Teil der öffentlichen Signatur** (expliziter Parameter), kein
  stilles Zusatzverhalten.

## Tests

- Je neue Core-Methode: Kontrakttest für ID-Kontinuität, für den Fall "nichts zu tun" (No-op bleibt
  Mesh/History unverändert) und für den jeweiligen Fehlerfall.
- Eigener Testfall exakt für das 2×2-Grid-Beispiel: zwei benachbarte Faces destruktiv entfernen →
  die innere, dadurch face-lose Kante verschwindet mit, die äußeren Randkanten bleiben.
- Production: ein Test pro Tasten-/Modus-Kombination (Delete × Vertex/Edge/Face, Vertex-Dissolve,
  Edge-/Face-Dissolve je beide Varianten), je ein History-Eintrag pro Erfolg, Mesh+History
  unverändert bei Ablehnung/No-op — analog zu den bestehenden `C`-Kontext-Tests aus AD-017/B6.

## Practical viewport test (ein Durchgang am Ende des gesamten Pakets, kein Per-Slice-Check)

- **2×2-Grid:** Delete auf einer einzelnen Face → Loch; alle vier Kanten bleiben erhalten, weil sie
  jeweils noch von einer Nachbar-Face genutzt werden, und bilden zusammen den Lochrand — keine
  verschwindet. Erst wenn zwei benachbarte Faces gemeinsam gelöscht werden, verliert die
  gemeinsame Innenkante beide Faces auf einmal und verschwindet entsprechend §0.2 Punkt 3 mit; die
  äußeren Randkanten der Zweier-Region bleiben weiterhin stehen (haben noch eine Nachbar-Face).
- **Würfel:** Edge-Dissolve in beiden Varianten testen — einmal mit Cleanup (2er-Vertices weg),
  einmal ohne (2er-Vertices bleiben sichtbar stehen). Dasselbe für Face-Dissolve an einer
  Zweier-Region. Vertex-Dissolve separat (keine Variante).
- **Streifen/Loop (z. B. 3×3-Grid):** Edge-Dissolve mit Cleanup auf jeder Kante eines ganzen Loops
  nacheinander → am Ende stehen wieder reine Quads da, kein Rest aus Sechsecken oder losen Punkten.

## Documentation

- Eintrag in `docs/research/topology/README.md` mit Verweis auf beide Research-Dokumente.
- Kurzer Abschluss-Eintrag (KEEP/ITERATE/REJECT/UNKNOWN) nach dem Praxis-Check — im Repo und im
  Projektgedächtnis, analog zu den übrigen WP-Einträgen in der ROADMAP (kein separates `decision.md`
  nötig, da kein Lab existiert).

## Definition of Done

Alle drei Elementebenen sind in der Production-App bedienbar, der einmalige Praxis-Check aus diesem
Dokument ist durchgeführt, und ein Kurzverdikt ist festgehalten.

---

## Status

Alle für den Start nötigen Entscheidungen sind getroffen (§0.2). Das Paket kann an einen
Code-Agenten gehen. Verbleibende technische Details (genaue Core-Signaturen für Vertex-/Edge-Delete,
exakte Pyglet-Tastencodes) werden beim Bauen entschieden, mit demselben Dokumentationsstandard wie
die bestehenden Core-Methoden — nicht hier vorab festgelegt.

---

## Status-Update 2026-10-06 (Umsetzung)

Umgesetzt wie oben beschrieben, Production-first, kein Lab. Der Praxis-Check (Definition of Done) und das
Kurzverdikt stehen aus — das Verdikt ist Manus Urteil, der Agent setzt es nicht.

### Was gebaut wurde

| Ebene | Ort | Inhalt |
| --- | --- | --- |
| Core | `src/core/mesh.py` | `dissolve_vertex(v)`, `dissolve_edges(edge_ids, *, cleanup)`, `dissolve_faces(face_ids, *, cleanup)`, `delete_vertices(ids)`, `delete_edges(ids)`, `delete_faces(ids)`; gemeinsamer, rein lesender Planer (`_region_outline`, `_plan_dissolve`) + ein Apply-Schritt; gemeinsamer Delete-Kern. Docstring je Methode mit ID-Kontinuität. |
| Freeze | `docs/architecture/CORE_V1_FREEZE.md` §7.1 | Präzedenzfall-Eintrag "WP Delete/Dissolve" (Freeze-Regel 1–6) |
| Production | `src/mirai/topology/delete_dissolve.py`, `src/mirai/application.py` (`_removal_command`) | Snapshot → Core → genau ein `MeshStateCommand`; Ablehnung/No-op: Mesh, History, Auswahl unverändert |
| Commands / Bindings | `commands.py` (`Delete`, `Dissolve`, `DissolveNoCleanup`), `bindings.py`, `pyglet_input.py` | Entf / Rücktaste / Ctrl+Rücktaste; Artist Input Truth `topology.delete`, `topology.dissolve`, `topology.dissolve_no_cleanup` (PROVISIONAL) |
| Tests | `tests/test_core_delete_dissolve.py` (43), `tests/test_application_delete_dissolve.py` (46), `tests/test_pyglet_input.py` (+2) | siehe §Tests; alle Suiten grün |
| Assets | `examples/meshes/grid_2x2.obj`, `grid_3x3.obj` | für den Praxis-Check mit `python src/main.py <asset>` |

### Beim Bauen entschieden (Plan: "Entscheidung fällt beim Bauen")

1. **Tasten (§0.3.1):** pyglet `key.DELETE` (Entf) = Delete, `key.BACKSPACE` = Dissolve. macOS: die mit "delete"
   beschriftete Taste liefert `BACKSPACE`, fn+delete liefert `DELETE`.
2. **`dissolve_edges` statt `dissolve_edge`:** atomar über die ganze Auswahl. Grund: Mit Cleanup pro einzelner Edge
   kann die erste Edge den Endpunkt entfernen, an dem die nächste ausgewählte hängt (zwei Edges an einer Würfel-Ecke:
   die zweite verschwände ungewollt). Faces, die über ausgewählte Edges zusammenhängen, verschmelzen als eine Region.
   Für eine einzelne Edge ist es genau die Plan-Operation. `cleanup` ist keyword-only und ohne Default.
3. **Vertex-/Edge-Delete haben eigene Primitive** (`delete_vertices`, `delete_edges`): Core hat keine öffentliche
   Edge-Entfernung, also lässt sich Vertex-/Edge-Delete nicht aus `remove_face` zusammensetzen.
4. **Kanten bei Delete (§0.2.3, präzisiert Manu 2026-10-06):** Jede Edge der entfernten Faces, an der danach keine
   Face mehr hängt, geht mit — innere Kanten wie frühere Mesh-Randkanten —, ebenso jeder Vertex, der dadurch keine
   Edge mehr hat. Edges, die noch an einer verbleibenden Face hängen, bleiben mit ihrer ID als Lochrand stehen.
   Vorher bereits face-lose Edges, die die Operation nicht berührt, bleiben unangetastet. `remove_face` selbst ist
   unverändert (lässt Edges weiterhin stehen). DD-1 ist damit entschieden.
5. **2er-Vertex** = Vertex mit genau zwei Edges. Cleanup-Kandidaten sind die Endpunkte der aufgelösten Edges.
   Lässt sich eine 2er-Kette nicht entfernen (Ersatz-Edge existiert schon, oder eine Face fiele unter 3 Vertices),
   bleibt sie ohne Fehler stehen. `dissolve_vertex` an einem 2er-Vertex ist dieselbe Entfernung (Umkehrung von
   `split_edge`) und lehnt in diesen Fällen ab, weil es den Vertex entfernen *muss*.
6. **Was Dissolve ablehnt** (MeshError, Mesh inkl. ID-Zähler unverändert; App: Statuszeile, keine History):
   - eine Edge mit nur einer Face (Mesh-Rand),
   - eine Region, deren Ergebnis ein Loch hätte oder deren Rand sich in einem Vertex berührt,
   - ein Vertex mit Valenz < 2, ein Bowtie-Vertex oder ein Vertex mit Wire-Edge an einem Fan.
   Bei einer Mehrfachauswahl lehnt eine einzige solche Edge oder ein einziger solcher Vertex die ganze Operation ab.
7. **IDs:** Pro verschmolzener Region entsteht eine neue FaceId. Pro entfernter 2er-Kette entsteht eine neue EdgeId.
   Die Nachbar-Face an der Kette behält ihre FaceId und ihre Boundary verliert den Vertex. Delete erzeugt keine IDs.
8. **Residue (erster Standard, §Not in scope):** Face-Dissolve wählt die verschmolzenen Faces, alles andere leert
   die Auswahl; der Modus bleibt.
9. **Session-Gates:** Wie bei `C` werden die drei Tasten ignoriert, solange W/E/R scharf ist. Während einer
   Knife-Session sind sie ungebunden.

### Agenten-Vorabdurchlauf der drei Szenarien (kein Ersatz für den Praxis-Check)

Echtes `src/main.py`-Fenster (GLRenderStore, Mesa llvmpipe unter Xvfb), Auswahl per Mausklick über das Picking,
Tasten als pyglet-Events. Ergebnis:

- **2×2-Grid** (Stand nach der DD-1-Entscheidung): Delete auf einer Eck-Face ergibt V 9 → 8, E 12 → 10, F 4 → 3 —
  die zwei Mesh-Randkanten und der Eck-Vertex gehen mit, die zwei Kanten zu den Nachbar-Faces bleiben. Zwei
  Nachbar-Faces: V → 6, E → 7, F → 2; keine Kante ohne Face bleibt stehen. Undo stellt alles wieder her.
  (Erster Durchlauf vor der Entscheidung: E 12 → 12 bzw. 11, mit frei schwebenden Randkanten — Anlass für DD-1.)
- **Würfel:** Edge-Dissolve mit Cleanup ergibt V 8 → 6, Faces `[3, 3, 4, 4, 4]` mit geraden Ersatzkanten. Ohne
  Cleanup: V bleibt 8, ein Sechseck, die beiden 2er-Vertices sind sichtbar. Face-Dissolve an einer Zweier-Region
  liefert in beiden Varianten dasselbe Bild. Vertex-Dissolve: ein Sechseck plus drei Quads. Ctrl+Rücktaste im
  Vertex-Modus bewirkt nichts und meldet das in der Statuszeile.
- **3×3-Grid, Loop:** Rücktaste dreimal nacheinander auf den Loop-Kanten. Zwischendurch entsteht ein Fünfeck, am
  Ende sind es 6 reine Quads (V 12, E 17), drei History-Einträge.

### Offene Fragen (M5: neue Erkenntnis = offene Frage, keine stille Entscheidung)

- **DD-1 — Mesh-Randkanten nach Delete. Entschieden (Manu, 2026-10-06):** Randkanten, an denen nach dem Delete keine
  Face mehr hängt, werden entfernt; Kanten, die noch von anderen Faces gebraucht werden, nicht. "Eine Kante, die
  sinnlos in der Luft schwebt, kommt weg." Umgesetzt (Punkt 4, §0.2.3). Folge: Delete des Mittel-Vertex im 2×2-Grid
  entfernt alles, weil keine Kante mehr an einer Face hängt; im 3×3-Grid bleiben die Ring-Kanten zu den Nachbar-Faces.
- **DD-2 — Symmetrie.** Laut Plan ausdrücklich nicht in scope. Delete/Dissolve spiegeln nicht. Das BLOCK-Gate des
  Symmetry Labs (`unsupported_commands`) kennt die drei neuen Commands nicht. Unter Symmetrie wirken sie im Lab
  deshalb einseitig. Gehört in die Symmetrie-Folgefrage (Entfernungs-Research §9); hier nicht angefasst.
- **DD-3 — Vertex-Dissolve und Umbindung.** Wie im Plan hängt die Vertex-Dissolve-Operation am Command "mit
  Cleanup" (`Dissolve`); `DissolveNoCleanup` bewirkt im Vertex-Modus nichts. Werden die beiden Varianten per
  `keymap.json` getauscht, wandert Vertex-Dissolve mit auf Ctrl+Rücktaste. Alternative: Beide Commands lösen im
  Vertex-Modus die eine Vertex-Operation aus.
- **DD-4 — Residue und Mesh-Rand-Edge-Dissolve.** Erste Standards, Material für den Praxis-Check:
  - Auswahl nach der Operation, siehe Punkt 8.
  - Dissolve einer Rand-Edge wird abgelehnt (Blender würde die Face entfernen).
  - Eine Ersatz-Edge, die schon existiert, wird nicht wiederverwendet (konservativ).

### Praxis-Check (Manu, ein Durchgang)

Start: `python src/main.py examples/meshes/grid_2x2.obj`, `python src/main.py cube`,
`python src/main.py examples/meshes/grid_3x3.obj`. Modus mit 1/2/3, Auswahl mit Klick/Shift+Klick, Wireframe-Overlay
mit Shift+D, Undo mit Ctrl+Z. Die drei Szenarien aus §Practical viewport test (2×2-Grid nach §0.2.3 in der
präzisierten Fassung: frei schwebende Randkanten verschwinden mit), dazu DD-3 und DD-4. Danach das Kurzverdikt KEEP/ITERATE/REJECT hier und in `docs/architecture/ROADMAP.md`
eintragen.
