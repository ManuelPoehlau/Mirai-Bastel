# Symmetry Lab (WP-SYM-LAB-01 … 03)

Forschungsfenster für die Symmetrie-Arbeit — **auf dem Production-Pfad**. **Stand
2026-10-03: WP-SYM-LAB-03 abgeschlossen.** Das Lab baut genau den Pfad von
`src/main.py` (`Application` → Viewport V02 → `GLRenderStore`, dieselben
Fenster-Handler über `create_window`/`install_handlers`/`run`) und ergänzt nur die
Symmetrie: drei Lab-Tasten, eine Gate-Zeile, Overlays und eine HUD-Zeile. Navigation,
Auswahl, Hover, W/E/R, Constraints, Anzeige-Modi, V/E/F, kontextuelles C, Knife und
Undo/Redo sind **die der App**. Eigener Renderer, eigener Dispatcher und der
gespiegelte Knife des alten Labs sind in Slice 5 gelöscht (Abschnitt „Historie" unten).

Symmetrie ist **nicht** nach Production übernommen (zurückgestellt, `docs/architecture/ROADMAP.md`
§7, Eintrag 2026-10-02); `src/main.py` kennt kein Experiment. Vertrag zwischen Lab und App:
[AD-013, Addendum H2](../../docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-03-wp-sym-lab-03-h2--experiment-input-hook-in-application).
Plan und Abschluss: [WP-SYM-LAB-03 Rebase-Plan](../../docs/architecture/WP-SYM-LAB-03_REBASE_PLAN.md)
(§5, A2-Tabelle).

> **Importiert nicht aus `playground/`** (Präzedenz AD-010), abgesichert durch
> `tests/test_import_boundary.py`.

## Start

Vom Repo-Root aus (Windows-Eingabeaufforderung/PowerShell und Linux identisch):

```
python experiments/symmetry_lab/run.py                          # subd_cube (Default)
python experiments/symmetry_lab/run.py head_basemesh
python experiments/symmetry_lab/run.py man_with_shoes_basemesh
python experiments/symmetry_lab/run.py --help
```

Gültige Namen sind die Registry-Namen aus `examples/loaders/assets.py` (`asset_names()`).
Ein unbekannter Name bricht **vor** dem Öffnen des Fensters mit der Liste der gültigen Namen
ab (Exit-Code 2). Voraussetzung wie bei `src/main.py`: `pyglet` ist installiert. Beim Start
listet die Konsole die drei Lab-Tasten, die Gate-Tabelle (AD-013 H2-R1/R3) und die
kontextuelle Bedeutung von Esc (`Cancel (Esc): closes the Re-Symmetrize preview while it is
open`). Liegt eine der drei Tasten in der App schon auf einem Command (global oder im
Knife-Kontext), bricht der Start mit `LabBindingConflict` ab, statt sie still zu überdecken.
Schließen: Fenster-X (Esc ist wie in der App nur Abbrechen).

## Steuerung

**Alles außer den drei Lab-Tasten ist die Bedienung von `src/main.py`** (Docstring dort):
Orbit = Alt+LMB ziehen, Pan = Alt+Shift+LMB ziehen, Zoom = Mausrad; LMB-Klick wählt
(Shift hinzufügen, Ctrl entfernen, Alt umschalten), Klick ins Leere leert; RMB/MMB
ungebunden. **W / E / R halten** + Maus bewegen = Move / Rotate / Scale (Ziel: die Auswahl,
sonst der Vertex unter dem Cursor; fix ab dem Tastendruck), loslassen übernimmt, Antippen
tut nichts; **X / Y / Z** (Shift+X/Y/Z = Ebene) als Constraint-Umschalter. **1 / 2 / 3** =
Vertex/Edge/Face, **D** / **Shift+D** = Anzeige-Modus / Draht-Overlay, **C** = kontextuelles
C (Split/Connect bzw. Knife bei leerer Auswahl), **Ctrl+Z / Ctrl+Y** = Undo/Redo (stellt die
Auswahl wieder her), **Esc** = Abbrechen.

| Taste | Lab-Command | Was passiert |
|---|---|---|
| Shift+S | `SymmetryCycle` | Symmetrie aus → X → Y → Z → aus, genau ein Undo-Schritt (über `Application.apply_mesh_change`); Ctrl+Z/Ctrl+Y gehen die Schritte zurück/vor. Abgelehnt (Statuszeile), solange W/E/R scharf ist oder läuft, eine Knife-Session aktiv ist oder die Re-Symmetrize-Vorschau offen ist |
| M | `ReSymmetrize` | öffnet die Re-Symmetrize-Vorschau; M bei offener Vorschau führt aus (ein Undo-Schritt), Esc schließt sie — siehe „Re-Symmetrize" unten |
| Shift+B | `SymmetryGateMode` | E5-Modus **BLOCK (Default)** ↔ MARK, Statuszeile `E5-Modus: <BLOCK\|MARK>`. Nur Lab-Zustand — kein Mesh, keine History, kein Undo-Schritt. Auch bei Symmetrie aus erlaubt (gilt ab dem nächsten Shift+S). Abgelehnt wie Shift+S |

Die drei Commands sind Lab-lokal (`lab_bindings.py`), nicht in `mirai.interaction.commands`,
und liegen im Kontext `symmetry_lab`; alles andere fällt auf die Bindungen der App zurück.

## Symmetrie unter W/E/R (Pivot pro Seite)

Symmetrisches W/E/R kommt ohne Lab-Code aus `src` (`MoveTool`/`TransformTool` lesen die
Definition im Mesh): der Partner führt die gespiegelte Absicht aus, ein Seam-Vertex gleitet
in der Ebene, X/Y/Z-Constraints gelten auch für W. **Pivot pro Seite** (Artist-Entscheidung B,
KEEP 2026-10-03): ohne expliziten Pivot dreht/skaliert die Auswahl um die Mitte der *eigenen*
Auswahl, die Gegenseite um den gespiegelten Punkt; ein einzelner Vertex dreht/skaliert also
um sich selbst. Rückfall auf die Mitte über Auswahl ∪ Partner, wenn ein Seam-Vertex betroffen
ist und die eigene Mitte nicht auf der Ebene liegt. Ein Seam-Vertex bleibt exakt auf der
Ebene, oder die Aktion wird vor der ersten Bewegung abgelehnt (`Rotate: refused — …`).

## E5: BLOCK (Default) und MARK

Experiment E5 / INV-8, **Artist-Verdikt KEEP-BLOCK** (Manu, 2026-10-03, in AD-SYM-02 §4
festgehalten): ein Tool, das unter Symmetrie nicht spiegelt, wird verweigert, statt
einseitig zu laufen. Auf dem App-Pfad spiegeln seit Slice 3b Edge und Vertex Connect (kontextuelles C, Koordinatoren), seit 3c Delete und Dissolve, seit Slice 4 Split und seit Slice 6c der Knife (Abschnitt „Symmetrischer Knife, Slice 6c“ unten). Als „nicht unterstützt" zählt C (keine Operation, keine
Erklärung) und jedes Transform-Command, dessen Operation `supports_symmetry` nicht erklärt —
gelesen am Klassenattribut, keine Tool-Liste. Heute erklären es W/E/R und alle vier C-Kontexte
sind deklariert; E5 hat also mit den echten Deklarationen nichts mehr zu verweigern oder zu
markieren (der Mechanismus bleibt und ist mit einem undeklarierten Kontext getestet).
MARK bleibt über Shift+B zum Vergleich erreichbar.

**Fail-closed (seit AD-SYM-03 Slice 3a, AD-013 H2-Amendment vom 2026-10-08).** Die BLOCK-Zeile ist
keine Sperrliste mehr, sondern eine Allow-List: durch geht, was in `NON_OPERATION` steht (Anzeige,
Auswahl samt Klicks und Alt+A, Modi 1/2/3, Undo/Redo, Esc, Constraints, Navigation), was als
Koordinator **deklariert** ist (`src/mirai/symmetry_declarations.py`, seit 3b Edge und Vertex Connect, seit 3c Delete,
Dissolve und DissolveNoCleanup, seit Slice 4 Split) und die Transforms mit `supports_symmetry`. Alles andere — auch ein
künftig verdrahtetes Werkzeug, das niemand eingetragen hat — wird sichtbar abgelehnt
(`Symmetrie aktiv — Befehl nicht koordiniert (BLOCK: nicht gestartet)`), nie still einseitig. Ist
ein C-Kontext deklariert, geht `C` durch, und jeder nicht deklarierte Kontext
(von Split, Edge Connect, Vertex Connect, Knife; seit Slice 6c keiner mehr) wird mit seinem Namen abgelehnt (`refused_contexts`, vom
Gate in `Application` nach der einen Kontext-Auflösung geprüft); solange keiner deklariert ist, wird
`C` wie bisher per Identität abgelehnt. Die Zeile ändert sich nur mit dem Lab-Zustand, nie pro
Tastendruck. Die Start-Liste zeigt jede Zeile mit `refused`, `allowed` und `refused_contexts`
sowie `NON_OPERATION` und die aktuellen Deklarationen.

**Kein Interim mehr (seit Slice 3c).** Die Übergangsmenge `INTERIM_ONE_SIDED` (Delete, Dissolve und
DissolveNoCleanup liefen unter Symmetrie + BLOCK einseitig, Manu, 2026-10-06) ist entfernt; die drei Befehle sind
deklariert und laufen koordiniert (Abschnitt „Slice 3c“ unten). Ohne Deklaration würde BLOCK sie wie jeden anderen
nicht koordinierten Befehl sichtbar ablehnen.

**MARK-Folge der Kanonisierung.** Sobald eine Symmetrie gesetzt ist, zählt `C` ein Spiegelpaar
einmal (Verdikt A2 = A): eine Kante plus ihre Spiegelkante ist eine Absicht. Bis Slice 3c lief das
unter MARK als einseitiger Split der Kante auf der Seite der Ebenennormalen (früher: „Keine
verbindbaren Kanten"); **seit Slice 4 endet diese Folge**: das Paar ist ein Split-Kontext und läuft
koordiniert (genau zwei neue Vertices, kein doppeltes Teilen), unter MARK wie unter BLOCK. Ein Vertex
plus sein Spiegelvertex ergibt weiter `C: nothing to do here`. Die Knife-Warnzeile steht nur, solange der
Kontext Knife keinen Koordinator hat (seit Slice 6c hat er einen).

| Zustand | C | W/E/R | HUD |
|---|---|---|---|
| Symmetrie aus (Modus egal) | wie in der App | wie in der App | kein `E5:` |
| Symmetrie an, **BLOCK** (Default) | Extrude (`T` halten) läuft seit Slice 7 koordiniert (Abschnitt unten); Split/Edge Connect/Vertex Connect laufen koordiniert (eine Undo-Stufe) oder werden mit ihrem Text abgelehnt (Entf/Rücktaste/Ctrl+Rücktaste ebenso, siehe Slice 3c); der Knife (leere Auswahl) startet seit Slice 6c eine koordinierte Session (Abschnitt unten); ein undeklarierter Kontext würde mit `Symmetrie aktiv — <Name> spiegelt nicht (BLOCK: <Name> nicht gestartet)` abgelehnt, ohne jede Deklaration wäre es `… C spiegelt nicht …` | laufen; ein nicht spiegelndes wird mit `Symmetrie aktiv — <Name> spiegelt nicht (BLOCK: <Name> nicht gestartet)` abgelehnt | `E5: BLOCK` |
| Symmetrie an, **MARK** | Split, Edge/Vertex Connect, Delete/Dissolve, der Knife und Extrude laufen koordiniert (mit denselben Ablehnungen wie BLOCK); ein undeklarierter Kontext läuft einseitig | laufen; ein nicht spiegelndes läuft mit Warnzeile | `E5: MARK`; **orange Warnzeile** darüber, solange etwas einseitig läuft |

Die orange Warnzeile (nur MARK): `Knife läuft einseitig — Symmetrie aktiv`, solange eine
Knife-Session unter Symmetrie läuft **und der Knife-Kontext undeklariert ist** (seit Slice 6c nie mit den echten Deklarationen); `Symmetrie aktiv — Extrude spiegelt nicht (läuft einseitig)`, solange Extrude (`T` gehalten) läuft **und undeklariert ist** (seit Slice 7 nie mit den echten Deklarationen); `Symmetrie aktiv — <Name> spiegelt nicht (läuft
einseitig)`, solange ein nicht spiegelnder Transform scharf ist oder läuft (heute nur über
einen Test erreichbar). Das Lab schreibt dafür keine Statusmeldung (AD-013 H2-R2). Ein
sofortiges C unter MARK behält die Statuszeile der App; seine Degradation zeigen die
Zustands-Marker (Vertex ohne Partner, magenta; HUD `partial`). Esc (Cancel) lehnt das
Gate außerhalb der Vorschau nie ab.

## Symmetrische Topologie, Slice 3b: Edge Connect und Vertex Connect

AD-SYM-03 Slice 3b (2026-10-08). **Praxis-Check durch Manu am 2026-10-08: alle Schritte wie erwartet; Auswahl nach Edge Connect: ITERATE (umgesetzt, s. u.)** (B2a in `docs/ATELIER.md`). Mit gesetzter
Symmetrie führt `C` mit einer Edge-Connect- oder Vertex-Connect-Auswahl **eine** koordinierte Operation auf beiden
Seiten aus (Auswahl plus Partner, ein Aufruf der unveränderten `apply_*`-Funktion, ein Undo-Schritt) oder lehnt
sichtbar ab und ändert nichts. Das gilt in **MARK wie in BLOCK**: die Ablehnungen gehören zum Vertrag einer
unterstützten Operation, sie sind keine Gate-Zeile (AD-013 H2-Amendment, „Runtime refusals are not G-3“). Ohne
Symmetrie läuft `C` unverändert.

- **Was koordiniert läuft:** Edge Connect (zwei oder mehr Kanten) und Vertex Connect (zwei oder mehr Vertices).
  Ein Spiegelpaar in der Auswahl zählt einmal (A2 = A). Liegt eine Seam-Kante in der Auswahl und wird geteilt, ersetzen
  ihre zwei Hälften sie in der Seam (Regel S1); Undo stellt die alte Seam wieder her. Knife
  ist nicht Teil davon (Slice 6); Split siehe Slice 4, Delete und Dissolve siehe Slice 3c.
- **Ablehnungen** (Statuszeile, kein History-Eintrag, Mesh und Auswahl unverändert; Reihenfolge wie geprüft):
  | Fall | Text |
  |---|---|
  | Ebene nicht achsparallel durch den Ursprung | `Symmetrie: Ebene nicht achsparallel durch den Ursprung — Operation nicht koordinierbar; Symmetrie ausschalten (Shift+S)` |
  | ausgewählte Kante/Vertex ohne Spiegelpartner | `Symmetrie: Auswahl enthält Elemente ohne Spiegelpartner — an einer Stelle mit Partner arbeiten oder Symmetrie ausschalten (Shift+S)` |
  | eine Face würde von Auswahl und Spiegelbild getroffen (Face über der Ebene) | `Symmetrie: eine Face würde von beiden Seiten getroffen (Auswahl und Spiegelbild) — Auswahl verkleinern oder Symmetrie ausschalten (Shift+S)` |
  | Ergebnis hätte ein Element ohne Partner (D-strict, A3 = S „vorerst“) | `Symmetrie: Ergebnis wäre nicht spiegelbildlich (neue Elemente ohne Partner) — nichts geändert; an einer Stelle mit Partner arbeiten oder Symmetrie ausschalten (Shift+S)` |

  Auf `man_with_shoes_basemesh` (`partial`) arbeitet man fern der magenta Vertices symmetrisch; direkt daneben (die
  neue Face enthielte einen ungepaarten Vertex) kommt der letzte Text.
- **Auswahl nach dem Connect (Artist-Verdikt ITERATE, Manu, 2026-10-08):** Edge Connect wählt die erzeugten Kanten auf
  der Seite, auf der du gearbeitet hast; hattest du bewusst beide Seiten gewählt (Kanten links, ihre Spiegelpartner
  rechts), die erzeugten Kanten beider Seiten, damit du mit beiden weiterarbeiten kannst (z. B. Skalieren in X).
  Regel (Engineering-Annahme, von Manu nicht bestätigt): maßgeblich ist die **live** Auswahl vor der Kanonisierung;
  liegt sie nur auf der Ebene (Seam-Kanten), gilt die Seite der Normalen (+X). Erzeugte Kanten auf der Ebene (ihr
  eigenes Spiegelbild) bleiben ausgewählt. Beide Seiten werden immer geschnitten, nur die Auswahl folgt der Seite.
  Undo stellt die vorherige Auswahl wieder her; eine abgelehnte Taste lässt sie unberührt. Vertex Connect lässt die
  Auswahl unverändert (AD-017). Für Split (Slice 4) gilt dieselbe Regel als Engineering-Annahme, siehe Slice 4.
- **Erfolgstexte** wie bisher: `Connect Edges`, `Vertex Connect` (kein Treffer: `Vertex Connect: nothing connectable`,
  kein History-Eintrag).
- **Headless nachgemessen** (nicht Praxis): `tests/test_symmetric_ops.py` und
  `experiments/symmetry_lab/tests/test_app_lab_symmetric_connect.py`; zusätzlich ein Durchlauf aller Kantenpaare und Vertexpaare jeder +X-Face von `subd_cube` und `head_basemesh`
  (je Erfolg: Befund sauber, eine Undo-Stufe, Undo stellt das Mesh her; keine Ausnahme). Zahlen:
  [AD-SYM-03 §7, Implementation note 3b](../../docs/architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md).

## Symmetrische Topologie, Slice 3c: Delete und Dissolve

AD-SYM-03 Slice 3c (2026-10-08). **Artist-Verdikte (2026-10-08):** Auswahl nach Face Dissolve **KEEP**; A1 Fall 2 verfeinert
(unten); Praxis-Check zur Nahtregel S2 bestanden, der verschwindende grüne Punkt **KEEP** (B2b in `docs/ATELIER.md`). Mit gesetzter
Symmetrie führen **Entf** (Delete), **Rücktaste** (Dissolve) und **Ctrl+Rücktaste** (Dissolve ohne Cleanup) in jedem
Komponenten-Modus (Vertex, Edge, Face) **eine** koordinierte Operation auf beiden Seiten aus (Auswahl plus Partner, ein
Aufruf der unveränderten Core-Operation, ein Undo-Schritt) oder lehnen sichtbar ab und ändern nichts. Das gilt in
**MARK wie in BLOCK**. Ohne Symmetrie laufen sie einseitig wie früher. Das Interim `INTERIM_ONE_SIDED` ist entfernt.

- **Ablehnungen** (Statuszeile, kein History-Eintrag, Mesh, Seam und Auswahl unverändert): dieselben vier Texte wie bei
  Connect (Ebene nicht achsparallel; Element ohne Spiegelpartner; Face von beiden Seiten getroffen im Vertex-/Edge-Modus;
  Ergebnis nicht spiegelbildlich, D-strict, u. a. neben ungepaarter Geometrie) und ein neuer:

  | Fall | Text |
  |---|---|
  | Dissolve (alle Varianten) einer Kante **direkt auf der Naht** (beide Enden auf ihr), eines Seam-Vertex oder eines Face-Paars über der Naht, das eine Face über der Ebene erzeugen oder eine Seam-Kante verbrauchen würde | `Symmetrie: Auflösen an der Seam wird noch nicht unterstützt (Seam-Kante oder -Vertex würde aufgelöst) — nichts geändert; abseits der Seam arbeiten oder Symmetrie ausschalten (Shift+S)` |

  Die bestehenden Texte „nichts ausgewählt“ und „kein Variant im Vertex-Modus“ (Ctrl+Rücktaste) bleiben.
- **Naht bei Delete (A1 Fall 1 = M, Manu):** Die Naht verschwindet nur, wo die angrenzenden Faces weg sind. Seam-Kanten,
  die nach dem Löschen nicht mehr existieren, werden in derselben Transaktion aus der Definition gestrichen; der HUD
  bleibt `valid`, Undo stellt die alte Naht wieder her. Gilt in allen drei Modi, also auch, wenn du eine Seam-Kante oder
  einen Seam-Vertex selbst löschst (Annahme über Fall 1 hinaus, von Manu nicht bestätigt); wäre das Ergebnis danach
  unvollständig, lehnt die Delta-Prüfung ab.
- **Naht bei Dissolve (A1 Fall 2 verfeinert, Manu 2026-10-08):** Eine Kante **direkt auf der Naht** aufzulösen bleibt
  verweigert (Text oben), weil eine Face ohne Naht übrig bliebe. Eine Kante, die die Naht **kreuzt** (ein Ende auf ihr),
  wird aufgelöst: die Naht verschwindet nicht, die zwei Seam-Kanten am aufgeräumten Seam-Vertex werden zu **einer**
  (Nahtregel S2, Engineering, im Praxis-Check KEEP; in derselben Transaktion, der grüne Punkt verschwindet, der HUD bleibt `valid`, Undo
  stellt Mesh, Naht und Auswahl wieder her). Gilt auch für einen Loop über die Naht (Kanten auf beiden Seiten
  ausgewählt, auch mehrere Naht-Übergänge). **Ctrl+Rücktaste** (ohne Cleanup) lässt die Naht unverändert. Jede andere
  verbrauchte Seam-Kante und jede neue Face über der Ebene bleibt verweigert. **Entf** auf einer Seam-Kante bleibt
  erlaubt („man macht bewusst ein Loch“). Eine Warnung über die Folgen beim Entfernen von Naht-Elementen ist eine
  mögliche spätere Idee, **nicht entschieden**.
- **Auswahl danach:** Delete und Vertex-/Edge-Dissolve leeren die Auswahl (der Modus bleibt, wie bisher). Face Dissolve
  wählt die verschmolzenen Faces auf der Seite, auf der die Auswahl lag, bei bewusst beidseitiger Auswahl beider Seiten
  (derselbe Helfer wie bei Edge Connect; **KEEP**, Manu 2026-10-08).
- **Headless nachgemessen** (nicht Praxis): `tests/test_symmetric_removal.py`,
  `experiments/symmetry_lab/tests/test_app_lab_symmetric_removal.py`; Zahlen und die Durchläufe aller Elemente der Assets:
  [AD-SYM-03 §7, Implementation note 3c](../../docs/architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md).

## Symmetrische Topologie, Slice 4: Split

AD-SYM-03 Slice 4 (2026-10-08). **Praxis-Check durch Manu am 2026-10-08: alle Schritte bestanden, KEEP** (B2c in `docs/ATELIER.md`). Mit gesetzter Symmetrie
führt `C` mit **einer** gewählten Kante (Kontext Split) **eine** koordinierte Operation aus: die Kante und ihre
Spiegelkante werden zusammen geteilt (ein Undo-Schritt), oder `C` lehnt sichtbar ab und ändert nichts. Das gilt in
**MARK wie in BLOCK**. Ohne Symmetrie teilt `C` unverändert die eine Kante. Seit diesem Slice war **nur der Knife**
(leere Auswahl) unter BLOCK noch abgelehnt (`Symmetrie aktiv — Knife spiegelt nicht (BLOCK: Knife nicht gestartet)`;
seit Slice 6c ist er deklariert); die BLOCK-Zeile und der Text leiten sich aus den Deklarationen ab (nichts von Hand eingetragen).

- **Was geteilt wird:** immer in der Mitte der Kante (t = 0,5; auf einer achsparallelen Ebene durch den Ursprung sind die
  Mittelpunkte der Spiegelkanten exakt gespiegelt). Kein Snap (der gehört zum Knife, Slice 6).
- **Spiegelpaar gewählt (A2 = A):** Kante plus ihre Spiegelkante zählt als eine Absicht — genau **zwei** neue Vertices, kein
  doppeltes Teilen.
- **Seam-Kante:** sie ist ihr eigener Partner und wird **einmal** geteilt; der neue Vertex liegt exakt auf der Ebene und
  ist ein Seam-Vertex (Regel S1: die zwei Hälften ersetzen die Kante in der Naht), die Naht bleibt durchgehend, der HUD
  bleibt `valid`; Undo stellt die alte Naht wieder her.
- **Ablehnungen:** dieselben Texte und dieselbe Reihenfolge wie bei Connect (Ebene nicht achsparallel; Kante ohne
  Spiegelpartner; Face von beiden Seiten getroffen, z. B. eine Kante in einer Face über der Ebene; Ergebnis nicht
  spiegelbildlich, D-strict). Kein History-Eintrag, Mesh, Naht und Auswahl bleiben unverändert. Auf
  `man_with_shoes_basemesh` wird eine Kante an einem magentafarbenen Vertex abgelehnt, fern davon läuft Split symmetrisch.
- **Auswahl danach (Engineering-Regel, im Praxis-Check KEEP, Manu 2026-10-08):** Vertex-Modus, die
  neuen Vertices auf der Seite, auf der die **live** Auswahl lag (derselbe Helfer wie bei Edge Connect): eine Kante auf
  einer Seite → nur der neue Vertex dieser Seite; bewusst beide Seiten gewählt → beide neuen Vertices; nur Elemente auf
  der Ebene (Seam-Kante) → der neue Vertex liegt auf der Ebene und bleibt ausgewählt. Ohne Symmetrie wie bisher ein
  Vertex. Undo stellt die vorherige Auswahl wieder her; eine abgelehnte Taste lässt sie unberührt.
- **Headless nachgemessen** (nicht Praxis): `tests/test_symmetric_split.py`,
  `experiments/symmetry_lab/tests/test_app_lab_symmetric_split.py`; ein Durchlauf aller Kanten von `subd_cube` (X, Z),
  `head_basemesh` (X) und `man_with_shoes_basemesh`: [AD-SYM-03 §7, Implementation note 4](../../docs/architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md).

## Re-Symmetrize (M / M / Esc)

Spiegelt die Seite der Auswahl exakt auf die andere Seite; die Partner kommen aus der
topologischen Paarung ab der Seam (Abschnitt unten). KEEP seit Slice 5 des alten Labs
(2026-09-25), auf dem App-Pfad bestätigt (Gemeinsame Prüf-Session, Punkt 1).

- **M ohne Vorschau:** Quelle ist genau ein ausgewählter Vertex. Abgelehnt (nur
  Statuszeile) mit `Re-Symmetrize: Symmetrie aus`, `… keine Auswahl`, `… genau einen Vertex
  auswählen`, `… Seam-Vertex gewählt — Quellseite unklar`, `… Seam teilt das Mesh in N Teile
  (nötig: genau 2)` und `Re-Symmetrize (M) abgelehnt — Transform läuft` bzw. `— Knife-Session
  läuft`. Sonst wird der Plan **einmal** gerechnet und die Vorschau öffnet: Overlay (blau /
  hellgrün / hellrot), blaue Zeile über der HUD-Zeile (`Re-Symmetrize Quelle +X → Ziel −X:
  bewegt 27, Seam → Ebene 0 | M = ausführen, ESC = abbrechen`), Hover ausgeblendet.
- **M bei offener Vorschau:** setzt genau die Positionen des Plans (ein Undo-Schritt, die
  Auswahl bleibt; Ctrl+Z stellt Mesh und Auswahl wieder her). Leerer Plan: `Re-Symmetrize: 0
  Änderungen — kein Schritt`, kein History-Eintrag.
- **Esc bei offener Vorschau:** schließt ohne Änderung (`Re-Symmetrize abgebrochen`).
- **Während die Vorschau offen ist:** Navigation und **D** / **Shift+D** gehen; jedes andere
  Command, jeder Auswahl-Klick sowie Shift+S und Shift+B → `Vorschau aktiv — Befehl
  ignoriert`. Kein Hover, auch nicht nach dem Zoom; nach M oder Esc kommt er zurück.
  Fenster schließen beendet die Vorschau.

## Overlays und Farblegende

Über `Viewport.add_overlay` (Lab-Klassen in `lab_overlays.py`; `src` kennt weder die Layer
noch die Farben). Auswahl und Hover sind die der App (gelb, 8 px, Hover blass gelb).

| Overlay | Farbe | Inhalt |
|---|---|---|
| Ebenen-Umriss | hellblau, Linien (mit Depth-Test) | Symmetrie-Ebene durch den Ursprung, Bounds + 10 % |
| Seam | grün, Punkt | Seam-Vertex (Endpunkt einer deklarierten Seam-Edge) |
| ohne Partner | magenta, Punkt | `UNPAIRED` (INV-10) |
| mehrdeutig | weiß, Punkt | `AMBIGUOUS` |
| Partner des Hover | türkis, Punkt (8 px) | gespiegelter Partner des Vertex unter dem Cursor, ohne auszuwählen |
| Partner der Auswahl | türkis, Punkt (8 px) | gespiegelte Partner der ausgewählten Vertices |
| Vorschau: bewegt | blau, Punkt (8 px) + Linie | Zielseiten-Vertex, der auf die Spiegelposition seines Partners gesetzt wird; Linie zur neuen Position |
| Vorschau: Seam → Ebene | hellgrün, Punkt (8 px) + Linie | Seam-Vertex, der exakt auf die Ebene gelegt wird |
| Vorschau: ohne Partner | hellrot, Punkt (8 px) | Zielseiten-Vertex ohne topologischen Partner — bleibt |
| blaue Textzeile | — | Re-Symmetrize-Vorschau offen: Richtung, Anzahlen, Tasten |
| orange Textzeile | — | E5 MARK: etwas läuft unter Symmetrie einseitig |

Die Partner kommen aus `mirai.symmetry.mirrored_selection` (keine eigene Paarung) und gibt es
**nur im Vertex-Modus**. Ein Seam-Vertex ist sein eigener Partner und ein Vertex ohne Partner
hat keinen — beide bekommen keinen türkisen Punkt; sind beide Seiten eines Paars ausgewählt,
wird keiner als Partner gezeigt.

**Zeichenreihenfolge:** Ebene → Vorschau-Linien → Zustands-Marker → Vorschau-Punkte →
Hover-Partner → Auswahl-Partner, alles vor den Punkten der App — Hover und Auswahl (gelb)
liegen obenauf. Punkte und Vorschau-Linien ohne Depth-Test. Die Vorschau-Linien liegen unter
den Zustands-Markern (altes Lab: darüber; Artist-Verdikt KEEP, 2026-10-03).

**Neu berechnet** wird nur, was sich geändert hat: Ebene und Zustands-Marker nur bei
geänderter Geometrie oder Definition, die Partner bei Auswahl- bzw. Hover-Wechsel. Während
eines laufenden W/E/R bleiben Befund, Ebene und Partner-IDs die vom Drag-Start, nur die Marker
wandern mit; der erste Frame nach dem Commit leitet alles neu ab (Plan A3).

## HUD

Eine Zeile unten links (bricht an der Fensterbreite um), nur aus öffentlichem App-Zustand:
`Asset | Vertex-Anzahl | Symmetrie: <X|Y|Z|aus> (<Zustand>) | ohne Partner: N[, mehrdeutig: M] |
<Move|Rotate|Scale>: scharf|bewegt (Auswahl | Hover v<id>) bzw. Transform: bereit |
E5: <BLOCK|MARK> | Constraint: <X|XY-Ebene> | letzte Statusmeldung`. „ohne Partner" und „E5"
nur bei aktiver Symmetrie, „Constraint" nur, wenn eine gesetzt ist. „Hover v<id>" steht, wenn
die Auswahl leer war und der Hover-Vertex das Ziel ist. Darüber, falls aktiv, die orange
E5-Warnzeile und die blaue Vorschau-Zeile. Die Statusmeldungen stehen außerdem wie in
`src/main.py` in der Konsole.

## Symmetrischer Knife, Slice 6c

AD-SYM-03 Slice 6c (2026-10-09; **Look, Texte, Varianten-Taste und das Verhalten nach einem abgelehnten Enter sind
Engineering-Vorgaben und bleiben „vorläufig“; Slice 6c wie gebaut: KEEP, Manu 2026-10-09**, B2d in `docs/ATELIER.md`). `CContext.KNIFE` ist deklariert
(`mirai.symmetry_declarations`, der Koordinator ist `mirai.symmetric_knife.coordinate_knife`): mit gesetzter Symmetrie
startet `C` mit leerer Auswahl eine **koordinierte** Knife-Session, **in BLOCK wie in MARK** (die BLOCK-Zeile nennt keinen
Kontext mehr, es gibt keine einseitige Warnzeile; beides leitet sich aus den Deklarationen ab, nichts Neues im Lab,
**keine vierte Lab-Taste**, die Allow-List der BLOCK-Zeile ist unverändert). Ohne Symmetrie ist der Knife der alte.

- **Was du siehst.** Die Seite, auf der du den Schnitt beginnst (erster Mesh-Punkt, nicht der Punkt im Leeren: F6 bleibt
  offen), ist die Arbeitsseite. Die Spiegelung deiner Punkte, Pfadsegmente, des Startpunkts, der Hover-Linie und der
  Kreuzungen erscheint auf der Gegenseite — sie wird aus **derselben Kappung** berechnet, die Enter benutzt, die
  Vorschau zeigt also nie etwas anderes als der Commit. Der Teil deines Pfads, der **nicht geschnitten wird** (Punkte und
  Segmente auf der anderen Seite, eine zweite Kette dort), ist **neutral grau**. Ein Hover-Ziel auf der Gegenseite mit
  Partner wird nicht abgelehnt, sondern grau (gekappt) gezeigt.
- **Drei Spiegel-Varianten, im Knife mit `V` durchschalten** (provisorisch; V war im Knife-Kontext und global frei und ist
  keine der drei Lab-Tasten; außerhalb einer symmetrischen Session tut `V` nichts): **V-a** wie die eigene Vorschau
  (Pfadlinien mit Tiefentest, Hover obenauf, Punkte durch das Mesh), **V-b** (Default) Spiegelseite immer sichtbar
  und gedimmt, **V-c** nur Punkte, keine Linien. Die Statuszeile nennt die aktive Variante (`Spiegelvorschau V-b …, Taste V
  wechselt V-a / V-b / V-c` beim Start und beim Wechsel, `[Spiegel V-b]` hinter jeder Knife-Meldung). Die Variante bleibt
  über Sessions erhalten, bis die App neu startet.
- **Sperre beim Hover und Klick (F3 = A).** Ein Ziel ohne Spiegelpartner, ein Schnitt durch eine Fläche ohne Partner, ein
  Schnitt, der innerhalb einer Fläche über die Mitte läuft (kein Punkt auf der Mitte zum Kappen), ein Schnitt in einer
  Fläche, die auf oder über der Mitte liegt, oder auf der Gegenseite der Arbeitsseite werden **in Sperrfarbe (magenta:
  Punkt, Kante, Linie vom Start)** gezeigt, die Statuszeile sagt warum (einmal, nicht bei jeder Mausbewegung), und der
  Klick wird **nicht gesetzt**. Texte: `Symmetrie: Dieser Punkt hat keinen Spiegelpartner — …`, `Symmetrie: Der Schnitt
  läuft durch eine Fläche ohne Spiegelpartner — …`, `Symmetrie: Der Schnitt kreuzt die Mitte innerhalb einer Fläche …`,
  `Symmetrie: Der Schnitt liegt in einer Fläche auf oder über der Mitte …`; jeweils mit dem Weg raus (anderswo schneiden
  oder Symmetrie mit Shift+S aus). Es ist der vordere Teil des Commits (`SymmetricKnifeView.refusal`), nichts anderes;
  was erst das Schneiden zeigt (Kollision, Spiegelung nicht eindeutig, Vollständigkeitsdelta) lehnt weiter Enter ab.
  Eine Doppelklick-Schließung, die so abgelehnt würde, schließt nicht, sondern hebt nur den Stift (`… not closed: …`).
- **Beginn.** Eine Ebene, die nicht achsparallel durch den Ursprung liegt, startet keine Session
  (`Symmetrie: Ebene nicht achsparallel durch den Ursprung — …`).
- **Enter.** Ein History-Eintrag für beide Seiten; Ctrl+Z nimmt beide Seiten und die Naht zurück, Ctrl+Y stellt sie wieder
  her; ausgewählt sind nur die Schnittkanten **deiner** Seite (F4 = A, Edge-Modus). Ein abgelehnter Enter beendet die
  Session wie bisher mit der Statuszeile `Knife: result taken back (…), nothing committed` und dem Mesh wie am Anfang —
  ob die Session lieber offen bleiben soll, ist deine Frage im Praxistest.
- **Kosten.** Die Session baut einen `SymmetryIndex` beim Start (das Mesh ändert sich währenddessen nicht); Hover und
  Klick lösen nichts auf und bauen keinen Index neu. Zahlen: AD-SYM-03 §10.8, „Slice 6c as built“.

### Praxistest für Manu (Slice 6c; B2d)

*Verdikt (Stand 2026-10-09): **Slice 6c wie gebaut: KEEP** (Manu, 2026-10-09). Du hast „alles Mögliche“ getestet; es funktioniert „überraschend gut“. Dabei wurde ein allgemeines (nicht symmetrisches) Knife-Problem gefunden und behoben. Slice 6d ist jetzt nicht nötig. **Offen, nicht entschieden:** die Wahl zwischen V-a / V-b / V-c (V-b bleibt Start, V-a und V-c bleiben schaltbar) und F6 („für jetzt irrelevant“). Als Nächstes in der Symmetrie-Spur: symmetrischer Extrude (Slice 7). Look, Texte und Varianten-Defaults behalten ihre „vorläufig“-Kennzeichnung; die Schritte unten sind der historische Testablauf.*

Ca. 10 Minuten. Pro Punkt **KEEP / ITERATE / REJECT / UNKNOWN** und ein Satz, wenn etwas nicht passt. Jeder Schritt ist am
gebauten Stand headless durchgespielt (Lab-Pfad, `head_basemesh` und `man_with_shoes_basemesh`, Vorder- und Seitenansicht);
das Aussehen am Bildschirm kann nur du beurteilen.

**Vorbereitung:** `git pull`, dann `python experiments/symmetry_lab/run.py head_basemesh`. **Shift+S** → `X`. Der E5-Modus
bleibt auf **BLOCK** — der Knife ist dort jetzt freigeschaltet. **1**, Auswahl leeren, **C** → Knife. Die Statuszeile nennt
die Spiegelvorschau und die Taste **V**.

1. **Vorschau der Gegenseite.** Auf einer Seite drei, vier Punkte setzen (Kante, Punkt in einer Fläche, über zwei Flächen).
   Die Gegenseite zeigt die Spiegelung mit (blau-violett). Kamera so drehen, dass die Gegenseite mal sichtbar, mal verdeckt ist.
   Mit **V** durchschalten: **V-a** (wie die eigene Vorschau, verdeckt), **V-b** (immer sichtbar, gedimmt; Start), **V-c** (nur
   Punkte). Die Statuszeile nennt die aktive Variante. → Welche fühlt sich am ehesten wie Silo an? Verdikt pro Variante.
2. **Schnitt über die Mitte.** Einen Schnitt quer über die Nase auf die andere Seite ziehen (die Mitte kreuzt der Schnitt an
   der Naht; Statuszeile `cut across 1 crossing(s)`). Der Teil hinter der Mitte erscheint **grau** („wird nicht
   geschnitten“), die Spiegelung deiner Hälfte ersetzt ihn. **Enter.** → Ergebnis: Schnitt bis zur Mitte plus Spiegelbild,
   durchgehend, HUD `valid`. Ist die graue Darstellung verständlich?
3. **Aus der Seitenansicht.** Kamera auf die Seite, ein Schnitt über mehrere Flächen und ein Klick ins Leere. → Wird das, was
   verdeckt über die andere Seite läuft, nachvollziehbar gekappt? (Die Statuszeile nennt verdeckte Kreuzungen: `hidden
   crossing(s) not cut`.)
4. **Zwei Schnitte.** Auf einer Seite schneiden, **E** (Stift abheben), auf der anderen Seite weiterschneiden. → Nur die Seite,
   auf der du angefangen hast, wird geschnitten, die zweite Kette erscheint grau, das Spiegelbild entsteht. **Enter.**
5. **Auswahl danach.** Nach Enter: nur die Schnittkanten deiner Seite ausgewählt (Edge-Modus)?
6. **Undo.** **Ctrl+Z** nimmt beide Seiten in einem Schritt zurück, **Ctrl+Y** stellt beide wieder her.
7. **Sperre beim Hover.** `python experiments/symmetry_lab/run.py man_with_shoes_basemesh`, **Shift+S** → `X`, Knife. Über eine
   Stelle ohne Spiegelpartner hovern (die ungepaarten Vertices liegen auf der −X-Seite; der Lab-Marker zeigt sie magenta).
   → Markierung in Sperrfarbe (magenta: Punkt, ggf. Kante und Linie vom Start), die Statuszeile sagt warum, ein Klick wird nicht
   gesetzt. Ist das früh und klar genug?
8. **Abgelehnter Enter (falls er dir begegnet).** Mit F3 = A ist das selten (die meisten Fälle sind schon beim Hover gesperrt).
   Die Session endet, das Mesh ist wie vorher, die Statuszeile sagt warum. → Passt das, oder soll die Session offen bleiben,
   damit du den letzten Schritt zurücknehmen kannst?
9. **Optional F6.** Einen Schnitt im leeren Raum beginnen. Wenn du dabei eine Meinung zu F6 bekommst, notiere sie; sonst bleibt
   F6 offen.

Praxistest und Fragen: `docs/ATELIER.md` B2d. Tests: `tests/test_symmetric_knife_preview.py`,
`test_app_lab_symmetric_knife.py` (BLOCK / MARK), und die Lab-Tests, die vorher den Knife-Verweis oder die
Warnzeile festhielten, laufen jetzt mit `undeclare_knife` (der abgeleitete Mechanismus bleibt getestet).

## Symmetrischer Extrude, Slice 7

*Engineering-Vorgaben (PROVISIONAL), dein Verdikt steht aus — AD-SYM-03 §11.* Mit gesetzter Symmetrie (`Shift+S`) extrudiert `T` halten die gewählten
Flächen **und ihre Spiegelpartner als eine Absicht**, als **ein** Undo-Schritt, in BLOCK wie in MARK (die Deklaration `EXTRUDE_COORDINATORS` in
`mirai.symmetry_declarations` ist der Schalter; BLOCK-Zeile und MARK-Warnung folgen ihr). Ohne Symmetrie läuft `T` unverändert einseitig wie in B9.

- **Gespiegelt, exakt:** die Deckel der Gegenseite liegen bit-genau auf dem Spiegelbild (kein Toleranzwert); Punkte auf der Mitte bleiben exakt auf ihr.
- **Distanz:** gemessen an den Flächen der **Arbeitsseite** (bei beiden Seiten gewählt: die Seite mit mehr gewählten Flächen, Gleichstand → Seite der
  Ebenennormalen). „Nach außen ziehen" heißt auf beiden Seiten außen; das Ergebnis ist dasselbe Spiegelbild, auf welcher Seite du arbeitest.
- **Naht (A1 Fall 3 = M, dein Verdikt):** liegt eine Fläche mit einer Kante an der Naht, entsteht eine zusammenhängende Beule über die Mitte, **ohne Wand in der Mitte**;
  die neue **Deckelkante ist die neue Naht**, samt den beiden Wandkanten an ihren Enden, die ebenfalls in der Mitte liegen (Regel S3, im selben Undo-Schritt, Undo bringt die alte Naht zurück). Die gewählten Deckel lassen sich sofort wieder extrudieren, beliebig oft.
- **Auswahl danach (Engineering-Vorgabe, kein Verdikt):** die neuen Deckel auf der Seite/den Seiten, auf denen du gearbeitet hast.
- **Ablehnungen** (Statuszeile, nichts verändert, kein Undo-Eintrag; in BLOCK und MARK dieselben):

| Grund | Text (Beginn) |
|---|---|
| Ebene nicht achsparallel durch den Ursprung | `Symmetrie: Ebene nicht achsparallel durch den Ursprung — Operation nicht koordinierbar; …` |
| Fläche ohne Spiegelpartner | `Symmetrie: Auswahl enthält Elemente ohne Spiegelpartner — …` |
| Fläche über der Mitte (**deine Aussage vom 2026-10-09: vorerst ablehnen**) | `Symmetrie: Eine Fläche liegt über der Mitte (ihr eigenes Spiegelbild) — Extrude wird dort noch nicht unterstützt, nichts geändert; …` |
| Berührung der Mitte nur an einer Ecke (**dieselbe Aussage**) | `Symmetrie: Die Auswahl berührt die Mitte nur an einer Ecke — Extrude wird dort noch nicht unterstützt, nichts geändert; …` |
| Ergebnis nicht spiegelbildlich (Netz beim Loslassen, Gegenprobe) | `Symmetrie: Ergebnis wäre nicht spiegelbildlich (neue Elemente ohne Partner) — nichts geändert; …` |

Auf `subd_cube` und `head_basemesh` gibt es weder eine Fläche, die die Mitte nur mit einer Ecke berührt, noch eine Fläche über der Mitte: die beiden Ablehnungen
sind dort nicht zu sehen (getestet an synthetischen Netzen, AD-SYM-03 §11.5 F-2).

### Praxistest für Manu (Slice 7)

> **Praxistest — symmetrischer Extrude im Lab (ca. 10 Minuten).** `git pull`, dann `python experiments/symmetry_lab/run.py` (Kopf-Asset).
>
> 1. `Shift+S` (Symmetrie an), `3` (Face-Modus). Eine Fläche **abseits der Mittellinie** wählen, `T` halten, nach außen ziehen → beide Seiten wachsen gleich. Loslassen. `Ctrl+Z` → beide Seiten weg, **ein** Schritt.
> 2. Dasselbe auf der **anderen** Seite → das Ergebnis ist das Spiegelbild, „nach außen ziehen" heißt auf beiden Seiten außen.
> 3. Eine Fläche **direkt an der Mittellinie** (Nasenrücken, Stirnmitte) → `T` → eine zusammenhängende Beule über die Mitte, **keine Wand in der Mitte**. Den gewählten neuen Deckel gleich noch einmal (und ein drittes Mal) mit `T` extrudieren: geht, die Naht-Punkte bleiben grün. Danach einen Punkt der **neuen** Mittelkante mit `W` verschieben: er bleibt auf der Mittellinie, beide Seiten bewegen sich gleich.
> 4. *(Geändert nach deiner Aussage vom 2026-10-09: Ecke an der Mitte wird vorerst abgelehnt.)* Auf dem Kopf gibt es keine Fläche, die die Mittellinie nur mit einer Ecke berührt — dieser Punkt ist mit den mitgelieferten Netzen nicht auszuprobieren. Die Ablehnung („berührt die Mitte nur an einer Ecke", nichts verändert) ist an einem synthetischen Netz getestet.
> 5. **Beide Seiten** wählen (Shift+Klick auf Fläche und Gegenfläche) → `T` → gleiches Verhalten wie bei einer Seite.
> 6. Nach **innen** ziehen → Mulde mit Boden, auf beiden Seiten.
> 7. Nach dem Extrudieren: Welche Flächen sind markiert? Erwartet: die neuen Deckel auf **der Seite, auf der du gearbeitet hast** (Arbeitsregel, noch nicht dein Verdikt).
> 8. `python experiments/symmetry_lab/run.py man_with_shoes_basemesh`, `Shift+S` → `X`: eine Fläche **ohne Spiegelpartner** (die ungepaarten Punkte sind magenta) → `T` → verständliche Ablehnung, nichts verändert.
> 9. `Shift+B` (MARK) → gleiches Verhalten (Extrude ist jetzt unterstützt, keine orange Warnzeile). `Shift+S` aus → `T` wirkt wie vorher einseitig.
>
> **Dein Verdikt (KEEP / ITERATE / REJECT / UNKNOWN):** Fühlt sich der Zug auf beiden Seiten richtig an? Ist die Mittelkante bei Punkt 3 so, wie du sie erwartest (M)? Ist die Auswahl danach so gewünscht?

Tests: `tests/test_symmetric_extrude.py`, `test_app_lab_symmetric_extrude.py`.

## Was das Lab nicht macht

- **Kein eigener gespiegelter Knife.** Der Knife ist der der App; unter Symmetrie spiegelt ihn seit Slice 6c der
  Koordinator der App (Abschnitt „Symmetrischer Knife, Slice 6c“). Der gespiegelte Knife des alten
  Labs (Slice 6/7) ist nicht übernommen; seine Befunde bleiben als Forschung (Historie, und
  `tests/test_lab_knife.py` für P1–P3).
- **Keine Partner im Edge-/Face-Modus.**
- **`subd_cube` schattiert unter X asymmetrisch** — die App trianguliert Quads nach der
  Vertex-Reihenfolge; die lab-eigene „kürzere Diagonale" (E10) ist mit Q1 = (a) entfallen
  (Manu, 2026-10-03; Frage kommt bei einer Promotion wieder). `head_basemesh` ist nicht
  betroffen. Befund: `tests/test_display_characterization.py`.

## Symmetrie im Lab

- **Ebene (E1):** immer durch den Welt-Ursprung `(0, 0, 0)`, Normale exakt `(1,0,0)`, `(0,1,0)`
  oder `(0,0,1)`. Kein Mesh-Zentrum, keine freie Ebene.
- **Speicherort:** die Definition lebt im Mesh (`mesh.symmetry_definition`, AD-SYM-01), nicht im
  Lab; das Lab liest sie bei jedem Zugriff neu (AD-013 H2-R2). Jeder Shift+S-Schritt ist genau
  ein Undo-Schritt (E2), geschrieben von `Application.apply_mesh_change` (H3).
- **Lab-Annahme E3 (keine Capability-Regel):** Beim Wechsel auf eine Ebene wird die Seam
  **einmal** festgelegt als alle Edges, deren beide Endpunkte auf der Achse exakt `0.0` haben.
  Danach ist sie gespeicherte Deklaration (INV-1) und wird nicht laufend neu geprüft. Verlässt
  ein Seam-Vertex später die Ebene, zeigt die Capability das als `violated`.
- **Befund E4 (keine Toleranz):** `man_with_shoes_basemesh` auf X ergibt `partial` mit genau
  **54** Vertices ohne Partner — sie liegen ca. `1e-6` neben der Spiegelposition
  (OBJ-Rundung). Das Lab markiert sie magenta, korrigiert sie aber nicht und führt keinen
  Toleranzwert ein.
- **W/E/R:** ob und wie gespiegelt wird, entscheiden `MoveTool`/`TransformTool` selbst aus der
  Definition im Mesh (oben).
- **Re-Symmetrize:** benutzt **nicht** die Positions-Paarung der Capability, sondern die
  topologische Paarung des Labs (nächster Abschnitt). W/E/R und die Markierungen
  (grün/magenta/weiß/türkis) bleiben positionsbasiert und exakt.

Charakterisierung der heutigen Assets (Tests in `tests/test_lab_symmetry.py`,
`tests/test_app_lab_cycle.py`):

| Asset | X | Y | Z |
|---|---|---|---|
| `subd_cube` | 8 Seam-Edges, `valid` | 0 Seam-Edges, `partial` (26 ohne Partner) | 8 Seam-Edges, `valid` |
| `head_basemesh` | 36 Seam-Edges, `valid` | `partial` | `partial` |
| `man_with_shoes_basemesh` | 44 Seam-Edges, `partial`, 54 ohne Partner | `partial` | `partial` |

## Topologische Paarung — Lab-Experiment (Slice 5, E11/E12)

`lab_topology.py`. **Lab-Experiment, keine Capability** — nicht in `mirai.symmetry`, keine
Änderung an `src/`; eine Übernahme wäre eine eigene Entscheidung (AD-013).

**Was:** Partner und Seiten werden aus dem Netz abgeleitet, ausgehend von der gespeicherten Seam
— nicht aus Positionen:

1. Jeder Vertex einer Seam-Edge ist selbst-gepaart.
2. Die beiden Faces an einer Seam-Edge (genau zwei) sind ein Spiegel-Paar.
3. Ein Face-Paar wird ab seiner gemeinsamen Anker-Edge gleichzeitig umlaufen (im einen Face
   a→b, im anderen a'→b'); die Vertices werden paarweise zugeordnet. Andere Face-Länge oder ein
   Anker, der keine Kante des Face ist → Konflikt für dieses Face-Paar, dort geht es nicht weiter.
4. Über jede Edge des Face-Paars zum nächsten Face-Paar (Breitensuche, jedes Paar einmal).
5. Ein Vertex mit zwei verschiedenen Partnern ist im Konflikt und gilt als nicht gepaart
   (INV-5). **Lab-Auslegung:** Auch ein Vertex, dessen Partner im Konflikt ist, gilt als nicht
   gepaart — sonst könnten zwei Vertices denselben Partner haben und Re-Symmetrize legte beide
   auf dieselbe Position. Die Partner-Map ist dadurch immer eine Involution.

Seiten (E12): Faces werden in Zusammenhangskomponenten zerlegt, ohne Seam-Edges zu überqueren.
Genau zwei Komponenten sind Voraussetzung für Re-Symmetrize. Ein Vertex gehört zur Seite der
Faces, die er berührt; Seam-Vertices gehören zu keiner Seite.

**Warum:** Die Positions-Paarung findet ohne Toleranz (A5) keinen Partner für Vertices, die
`1e-6` neben ihrer Spiegelposition liegen (Befund E4) — genau die Vertices, die Re-Symmetrize
reparieren soll. Die Seam ist das, was Verformung überlebt (INV-4), und von ihr aus ist die
Paarung jederzeit neu ableitbar (INV-3): nicht gespeichert, bei jedem Aufruf neu berechnet,
positionsunabhängig.

**Charakterisierung** (Ebene X, Seam aus E3; `tests/test_lab_topology.py`):

| Asset | topologisch gepaart | Konflikte | stimmt mit Capability-`PAIRED` überein | Faces je Seite |
|---|---|---|---|---|
| `subd_cube` | 26/26 | 0 | 18/18 | 12 / 12 |
| `head_basemesh` | 326/326 | 0 | 290/290 | 162 / 162 |
| `man_with_shoes_basemesh` | 928/928 | 0 | 830/830 | 463 / 463 |

Alle 54 `UNPAIRED`-Vertices von `man_with_shoes_basemesh` haben einen topologischen Partner
(27 Paare); Re-Symmetrize von jeder Seite aus ergibt `valid` mit 0 ohne Partner.

**Grenzen:**

- Braucht eine Seam mit mindestens einer Edge, die genau zwei Faces hat. Ohne Seam (z. B.
  `subd_cube` auf Y: 0 Seam-Edges → eine Komponente) wird Re-Symmetrize abgelehnt.
- Faces, die über keine Kette von Face-Paaren von der Seam aus erreichbar sind (z. B. eine
  zweite, nicht an die Seam angebundene Mesh-Insel), bleiben ungepaart.
- Asymmetrische Topologie wird nicht „repariert": Ein Face-Paar mit unterschiedlicher Länge
  (z. B. nach `split_edge` auf einer Seite) wird übersprungen; ein Vertex ohne Gegenstück bleibt
  ohne Partner und wird bei Re-Symmetrize nicht bewegt (hellrot in der Vorschau). Die übrigen
  Vertices dieser Faces werden meist über benachbarte Face-Paare trotzdem gepaart.
- Die Seam selbst wird nicht geprüft: sie ist gespeicherte Deklaration (E3). Liegt sie nicht
  zwischen zwei gespiegelten Hälften, ist auch die Paarung falsch — das Lab kann das nicht
  erkennen, nur (über die Komponentenzahl) eine Seam, die das Mesh nicht in zwei Teile teilt.

## Aufbau

```
pyglet-Event → Handler aus src/main.py (install_handlers) ─┬→ Application (alles der App)
               Lab-on_key_press (lab_key_press) ───────────┘   Lab-Taste → SymmetryAppLab
Application → Viewport V02 → GLRenderStore; Lab-Overlays über Viewport.add_overlay (H1)
```

| Datei | Inhalt | GL nötig |
|---|---|---|
| `run.py` | Einstieg: Asset prüfen, Start-Liste, `src/main.py`-Fenster + Lab bauen (`build_lab`, fensterlos `build_app_lab`), Event-Loop | – |
| `lab_app.py` | Lab-Kontext (drei Tasten, Start-Prüfung), Gate-Tabelle, Start-Liste, `lab_key_press`, Shift+S, Re-Symmetrize-Vorschau (M/M/Esc), E5-Modus (Shift+B, `block_row` fail-closed aus `NON_OPERATION`, Deklarationen und `supports_symmetry`), Befund-Cache, HUD-Zeile `hud_text`, E5-Warnzeile, Vorschau-Zeile | nein |
| `lab_overlays.py` | Ebenen-Umriss, Zustands-, Vorschau- und Partner-Marker, Vorschau-Linien als Unterklassen von `FlatColorLayers`/`GLPointOverlay`; Änderungs-Signatur, Aufschub während eines Transforms | erst beim Zeichnen |
| `lab_app_window.py` | pyglet: Handler aus `src/main.py` + Lab-`on_key_press`/`on_draw` darüber, HUD-, Warn- und Vorschau-Label | ja |
| `lab_bindings.py` | `SYMMETRY_LAB_CONTEXT`, die drei Lab-Commands, `LAB_OVERRIDES` (einzige Quelle der Lab-Tasten) | nein |
| `lab_symmetry.py` | Ebene (E1), Seam-Ableitung (E3), `set_symmetry_axis`, Befund `SymmetryReport`, Ebenen-Umriss `plane_outline_data` | nein |
| `lab_topology.py` | Topologische Paarung (E11) und Seiten (E12) — Lab-Experiment | nein |
| `lab_resymmetrize.py` | Re-Symmetrize-Plan (E12/E13), `set_plan_positions`, Vorschau-Text und -Daten | nein |
| `lab_scene.py` | Asset-Namen prüfen; `load_asset_into` (ohne Viewport, nur für die Forschungs-Tests) | nein |
| `probe_drag_cost.py` | Drag-Kosten-Probe (Plan A3), baut über `run.build_app_lab` | nein |
| `_paths.py` | sys.path-Bootstrap (`src/` vor Repo-Root, `examples/`, `experiments/`) | nein |

Erlaubte `Application`-Zugriffe: nur die öffentliche Liste aus AD-013 H2-R4 — für **jedes**
Lab-Modul geprüft (statisch T-R4a, zur Laufzeit T-R4b, `tests/test_app_lab_boundary.py`). Das
Lab pusht nie selbst in die History.

## Tests

```
python -m pytest experiments/symmetry_lab/tests
```

Headless (TraceStore, kein Fenster); Tests, die `pyglet.window` brauchen, setzen auf Linux ohne
Display `pyglet.options["headless"] = True` (`tests/_pyglet_headless.py`). Änderungen an
`src/mirai/application.py` oder `src/viewport/` sollen diese Tests mitlaufen lassen (CLAUDE.md).

- App-Pfad: `test_app_lab_*.py` (AD-013 H2 T-R1–T-R4, Zyklus, Overlays, Partner, HUD,
  W/E/R unter Symmetrie, Hover-Ziel, Re-Symmetrize, Vorschau inkl. Fuzz, E5, fail-closed BLOCK-Zeile in `test_app_lab_fail_closed.py`), `test_run.py`
  (Fenster-Smoke-Test), `test_probe_drag_cost.py`.
- Forschung, rein: `test_lab_topology.py`, `test_lab_resymmetrize.py`, `test_lab_symmetry.py`,
  `test_lab_scene.py`, `test_lab_knife.py` (P1–P3), `test_display_characterization.py` (E10/Q1).
- `test_import_boundary.py`: genau diese Lab-Module, keines aus `playground/`.

Welche Tests des alten Labs in Slice 5 gelöscht wurden und was sie ersetzt: Plan, A2-Tabelle.

## Drag-Kosten-Probe (Plan A3)

Ohne Fenster, Windows und Linux gleich, Ausgabe zum Einfügen in den Chat:

```
python experiments/symmetry_lab/probe_drag_cost.py
```

Baut App + Lab wie `run.py` (ohne Fenster), Symmetrie X, wählt per Klick 6 gepaarte Vertices,
zieht W über 200 Mausbewegungen und misst je Bewegung Transform-Schritt + Lab-Overlays
(p50/p95/max; Schwelle p95 ≤ 8 ms) auf `head_basemesh` und `man_with_shoes_basemesh`, dazu den
Commit-Frame und Hover-Wechsel. Optionen: `--moves N`, `--assets <Name …>`. Zahlen (Container
und Referenz-PC): [Plan A3](../../docs/architecture/WP-SYM-LAB-03_REBASE_PLAN.md#review-amendments-2026-10-03).

## Historie (bis 2026-10-03)

*Stand 2026-10-03, WP-SYM-LAB-03 Slice 5.* Die Abschnitte unten sind **inhaltlich unverändert**
übernommen — Projektgedächtnis, keine Anleitung mehr. Jeder trägt in der Zeile darunter sein
Verdikt. Befehle und Dateien darin beziehen sich auf den damaligen Stand: `run.py` war bis
Slice 5 das **alte** Lab (eigener Renderer, eigener Dispatcher, gelöscht), `run_app.py` der
App-Pfad (heute `run.py`). Die Handoffs der Slices:
[Slice 2](../../docs/architecture/WP-SYM-LAB-01_SLICE2_CLAUDE_CODE_HANDOFF.md) (Rendering/Kamera, §2),
[Slice 3](../../docs/architecture/WP-SYM-LAB-01_SLICE3_CLAUDE_CODE_HANDOFF.md) (Symmetrie + Move, Entscheidungen A1/A2, E1–E6 in §2),
[Slice 4](../../docs/architecture/WP-SYM-LAB-01_SLICE4_CLAUDE_CODE_HANDOFF.md) (Hover-Ziel für Move, symmetrische Anzeige-Triangulierung, Entscheidungen A3/A4, E7–E10 in §2),
[Slice 5](../../docs/architecture/WP-SYM-LAB-01_SLICE5_CLAUDE_CODE_HANDOFF.md) (Re-Symmetrize über topologische Paarung, Entscheidungen A5–A7, E11–E15 in §2),
[Slice 6](../../docs/architecture/WP-SYM-LAB-01_SLICE6_CLAUDE_CODE_HANDOFF.md) (gespiegelter Knife, headless Engine, Entscheidungen A8–A11, E16–E22 in §2),
[Slice 7](../../docs/architecture/WP-SYM-LAB-01_SLICE7_CLAUDE_CODE_HANDOFF.md) (gespiegelter Knife im Fenster, Entscheidungen A12/A13, E23–E30 in §2).

### Gemeinsame Prüf-Session nach Slice 4 (Manu, Windows) — geprüft 2026-10-03

*Verdikt (Stand 2026-10-03): 1 S3–S5-Smoke **KEEP** · 2 Pivot **B** entschieden, nachgeprüft **KEEP** · 3 E5 **KEEP-BLOCK** (seit Slice 5 Default) · 4 Q1 **(a)** · 5 Zeichenreihenfolge **KEEP** (Manu, 2026-10-03).*

**Artist-Verdikte (Manu, 2026-10-03):** 1 KEEP · 2 Pivot → B (siehe Punkt 2) ·
3 **KEEP-BLOCK** · 4 **(a)** · 5 KEEP. Zu 2 danach: Pivot **B** (pro Seite) entschieden, gebaut und im Fenster geprüft: **KEEP**. Plan §4.2/§4.3 (WP-SYM-LAB-03): eine Sitzung, ≈10 Minuten, altes
und neues Lab **nebeneinander**. Für die KEEP-Punkte ist das keine neue Entscheidung — nur „dasselbe
wie vorher?", was kein Test beweisen kann. Offen entschieden werden S2 und E5; Q1 ist eine
Prioritätsfrage. Bedienung im neuen Lab wie in der App (W/E/R **halten** + Maus, Pan
Alt+Shift+LMB, Shift+Klick = hinzufügen, Esc schließt das Fenster nie).

Zwei Konsolen im Repo-Ordner:

```
python experiments/symmetry_lab/run.py head_basemesh        # alt
python experiments/symmetry_lab/run_app.py head_basemesh    # neu (App-Pfad)
```

**1. S3–S5 KEEP-Smoke auf dem neuen Host** (nur `run_app.py`, Vergleich mit dem alten Fenster):
**Shift+S** viermal → aus → X → Y → Z → aus, Umriss und Marker wie im alten Lab; **Ctrl+Z** /
**Ctrl+Y** gehen die Schritte zurück/vor. Auf X einen Vertex seitlich am Kopf anklicken (türkiser
Partner), **W halten** + Maus → beide bewegen sich spiegelbildlich, loslassen = ein Undo-Schritt;
dasselbe mit **E** und **R**. Dann `man_with_shoes_basemesh`, Shift+S, Vertex rechts wählen,
**M** (blaue Vorschau) / **M** (ausführen, `valid`) / Ctrl+Z, und **M** / **Esc** (nichts geändert).
Schritte im Detail: [„Manuelle Prüfung Re-Symmetrize auf dem App-Pfad"](#manuelle-prüfung-re-symmetrize-auf-dem-app-pfad-manu-windows--offen-noch-nicht-geprüft).
Verdikt 1: **KEEP** (Manu, 2026-10-03).

**2. S2 — symmetrisches Rotate/Scale (offen seit 2026-10-03)**, Schritte wie [„Manuelle Prüfung S2"](#manuelle-prüfung-s2-manu-windows--offen-noch-nicht-geprüft),
im neuen Lab: `head_basemesh`, Shift+S → X, Vertex seitlich anklicken; **E halten**, dann mit
**X**, **Y**, **Z** (Constraint, Toggle) erneut — dreht der Partner richtig mit (X gleicher Sinn,
Y/Z Gegensinn)? **R halten** — ist die Paarmitte der Pivot, den du erwartest? Grünen Seam-Vertex
wählen, E mit Y/Z/frei → abgelehnt (`Rotate: refused — …`), mit X erlaubt. **Neu klickbar:** beide
Vertices eines Paars mit Shift+Klick wählen → starre Rotation (Schritt 5 der S2-Liste).
Verdikt 2: **Pivot B entschieden, Nachprüfung KEEP** (Manu, 2026-10-03). Rückfrage war, wo der Pivot liegt: bis dahin der Zentroid über Auswahl ∪ Partner (Paarmitte auf der Ebene). Entscheidung **B — Pivot pro Seite**: ohne explizites `pivot` der Zentroid der *eigenen* Auswahl, die Operation spiegelt ihn für die Partner; Rückfall auf Auswahl ∪ Partner, wenn ein Seam-Vertex betroffen ist und der eigene Zentroid nicht auf der Ebene liegt (`selection_helpers.symmetric_default_pivot`). Die Paarmitte (A) bleibt als Idee für ein Pivot-System (freie/temporäre Pivots, später). **Nachprüfung (KEEP, Manu, 2026-10-03):** `run_app.py head_basemesh`, Shift+S → X, eine Augen- oder Ohrschleife auf **einer** Seite wählen (Shift+Klick), **E** und **R** halten: dreht/skaliert die Schleife um ihre eigene Mitte und die Gegenseite gespiegelt? Ein einzelner Vertex bewegt sich mit E/R nicht mehr (dreht um sich selbst). Verdikt: **KEEP** (Manu, 2026-10-03).

**3. E5 mit C — MARK vs. BLOCK** (die Frage aus [„Manuelle Prüfung E5"](#manuelle-prüfung-e5-manu-windows--keep-block-2026-10-03-siehe-ad-sym-02-4),
jetzt mit dem echten nicht spiegelnden Tool C). `run_app.py subd_cube`, **Shift+S** → X; die
HUD-Zeile zeigt `E5: MARK`.
- **MARK:** *(Stand der Prüfung, 2026-10-03; seit Slice 4 teilt Split beide Seiten, HUD bleibt `valid`)* **2** (Edge-Modus), eine Edge auf **einer** Seite anklicken, **C** → Split: nur diese
  Seite bekommt einen Vertex, er ist **magenta** (ohne Partner), HUD `partial`, Statuszeile `Split`.
  **Ctrl+Z**. Dann **1**, Auswahl leeren (Klick ins Leere), **C** → Knife-Session: über der
  HUD-Zeile steht orange `Knife läuft einseitig — Symmetrie aktiv`; zwei gegenüberliegende
  Vertices einer Face auf einer Seite anklicken, **Enter** → einseitiger Schnitt, die orange Zeile ist weg; Ctrl+Z.
- **Shift+B** → `E5-Modus: BLOCK`, HUD `E5: BLOCK`. Dieselbe Edge, **C** → nichts passiert,
  Statuszeile `Symmetrie aktiv — C spiegelt nicht (BLOCK: C nicht gestartet)`; mit leerer Auswahl
  ebenso (kein Knife). **W/E/R** laufen in beiden Modi symmetrisch.
- Frage: Womit würdest du im Alltag lieber arbeiten — C verweigert (BLOCK) oder läuft einseitig mit
  Markierung (MARK)? Hast du im MARK die orange Zeile und den magenta Vertex überhaupt bemerkt?

Verdikt 3: **KEEP-BLOCK** (Manu, 2026-10-03) — ein nicht spiegelndes Tool soll unter Symmetrie verweigert werden, nicht einseitig laufen. Nachgetragen in AD-SYM-02 §4. Folge fürs Lab: BLOCK wird Default (Slice 5).

**4. Q1 — Schattierung von `subd_cube` unter X** (Plan §6): beide Fenster mit `subd_cube`
(`run.py subd_cube` / `run_app.py subd_cube`), Shift+S → X, orbiten und linke/rechte Seite
vergleichen. Das alte Lab schattiert symmetrisch (E10, kürzere Diagonale), das neue mit der
Production-Triangulierung asymmetrisch; `head_basemesh` ist in beiden gleich. (a) im Lab vorerst
hinnehmen (Empfehlung des Agenten) oder (b) „kürzere Diagonale" als eigenes kleines Paket für
Production? Verdikt 4: **(a)** im Lab vorerst hinnehmen (Manu, 2026-10-03).

**5. Zeichenreihenfolge seit Slice 3:** bei offener Re-Symmetrize-Vorschau
(`man_with_shoes_basemesh`, Schritt 1) liegen die Vorschau-Linien jetzt **unter** den
Symmetrie-Markern (altes Lab: darüber). Stört das, oder ist es egal (die Linien sind dort
meist ~1e-6 lang)? Verdikt 5: **KEEP** (Manu, 2026-10-03).

### Manuelle Prüfung Re-Symmetrize auf dem App-Pfad (Manu, Windows) — offen, noch nicht geprüft

*Verdikt (Stand 2026-10-03): **KEEP** über die Gemeinsame Prüf-Session, Punkt 1 (Manu, 2026-10-03); Verhalten wie „Manuelle Prüfung Slice 5" (KEEP 2026-09-25).*

Aus „Manuelle Prüfung Slice 5" (KEEP 2026-09-25) für `run_app.py` umgeschrieben; erwartet wird
**dasselbe Verhalten wie dort**. Anders nur, was die App vorgibt: Auswahl gelb statt rot, Move ist
**W halten + Maus bewegen** (statt Q), Pan Alt+Shift+LMB, MMB ungebunden, Esc schließt das Fenster
nie.

1. `python experiments/symmetry_lab/run_app.py man_with_shoes_basemesh` starten. Die Konsole
   listet `key:m -> ReSymmetrize`, die Gate-Zeile `Re-Symmetrize-Vorschau offen (Slice 3)` und die
   Zeile `Cancel (Esc): closes the Re-Symmetrize preview while it is open`.
2. **Shift+S** → HUD `Symmetrie: X (partial) | ohne Partner: 54`; die 54 Vertices sind magenta.
3. Einen Vertex auf der **rechten** Körperseite **anklicken** (gelb).
4. **M** → über der HUD-Zeile erscheint die blaue Zeile, z. B.
   `Re-Symmetrize Quelle +X → Ziel −X: bewegt 27, Seam → Ebene 0 | M = ausführen, ESC = abbrechen`.
   Die 27 Vertices der anderen Seite sind **blau** markiert (Linien ~`1e-6` lang, unsichtbar).
5. Während die Vorschau offen ist: Alt+LMB-Ziehen, Alt+Shift+LMB-Ziehen und Mausrad navigieren;
   **D** wechselt den Anzeige-Modus. **W** (halten + bewegen), **Shift+S**, **Ctrl+Z**,
   **Ctrl+Y**, **C**, **1/2/3** und ein LMB-Klick tun nichts; HUD/Konsole melden
   `Vorschau aktiv — Befehl ignoriert`. Kein gelber Hover, auch nicht nach dem Mausrad.
   Zusätzlich (neu, AD-013 F1): mitten im Alt+LMB-Ziehen **Ctrl+Z** → ebenfalls ignoriert.
6. **M** erneut → `Symmetrie: X (valid) | ohne Partner: 0`, `Re-Symmetrize ausgeführt: 27
   Änderungen`; die blaue Zeile verschwindet, der Hover ist wieder da, die Auswahl bleibt.
   Die ehemals magenta Vertices zeigen beim Hover/bei Auswahl einen türkisen Partner.
7. **Ctrl+Z** → wieder `partial`, 54 magenta (ein Schritt), die Auswahl ist wieder der Vertex aus
   Schritt 3. **Ctrl+Y** → wieder `valid`.
8. Abbrechen: Vertex wählen, **M**, dann **Esc** → Vorschau verschwindet, nichts geändert, kein
   Undo-Schritt (`Re-Symmetrize abgebrochen`); das Fenster bleibt offen.
9. Dasselbe mit einem Vertex auf der **linken** Seite (vorher Ctrl+Z) → Richtung in der blauen
   Zeile umgekehrt, Ergebnis ebenfalls `valid`.
10. `head_basemesh` (schon symmetrisch), Shift+S, Vertex wählen, **M** → `0 Änderungen`; **M** →
    `Re-Symmetrize: 0 Änderungen — kein Schritt`, Ctrl+Z nimmt dann das Shift+S zurück.
11. Quellseite folgt der Topologie: `head_basemesh` neu starten, **ohne** Symmetrie einen Vertex
    seitlich am Kopf wählen, mit **W** halten + Maus **über die Mittelebene hinaus** ziehen, W
    loslassen. **Shift+S** (→ X; Vertex und alter Partner magenta, die Auswahl bleibt) und **M** →
    Quelle ist die **ursprüngliche** Seite, blau ist der alte Partner. **M** → der Partner springt
    spiegelbildlich mit, `Symmetrie: X (valid)`.
12. Ablehnungen (Statuszeile, keine Vorschau): **M** ohne Auswahl; **M** bei Symmetrie aus; **M**
    mit einem grünen Seam-Vertex als Auswahl; **M** mit zwei ausgewählten Vertices (Shift+Klick);
    **M** bei Symmetrie **Y** auf `subd_cube`; **W** halten und dabei **M** (Transform läuft).

### Start

*Verdikt (Stand 2026-10-03): Referenz: Start des alten Labs (`run.py` bis Slice 5, gelöscht). Heute: Abschnitt „Start" oben.*

Vom Repo-Root aus (Windows-Eingabeaufforderung/PowerShell und Linux identisch):

```
python experiments/symmetry_lab/run.py                          # subd_cube (Default)
python experiments/symmetry_lab/run.py head_basemesh
python experiments/symmetry_lab/run.py man_with_shoes_basemesh
```

Gültige Namen sind die Registry-Namen aus `examples/loaders/assets.py` (`asset_names()`).
Ein unbekannter Name bricht **vor** dem Öffnen des Fensters mit der Liste der gültigen Namen ab
(Exit-Code 2). Voraussetzung wie beim Playground: `pyglet` ist installiert
(`python -m pip install pyglet`). Beim Start listet die Konsole die aktiven Lab-Overrides.
Schließen: ESC (wenn kein Move scharf ist oder läuft, keine Vorschau offen und keine
Knife-Session aktiv ist) oder Fenster-X.

### Move-Bedienung wie die App (2026-09-27) — offen, noch nicht geprüft

*Verdikt (Stand 2026-10-03): **Superseded, nie verdiktet** (Plan §4.2): das Lab nutzt seit WP-SYM-LAB-03 das W der App selbst (WP-06 B3, `PROMOTED`); es gibt nichts Lab-Eigenes mehr zu beurteilen.*

**Artist-Entscheidung (Manu, 2026-09-27):** Das Lab bekommt dieselbe Move-Bedienung wie die
Production-App (WP-06 B3): **W** statt Q, und AD-016 hold-key-hover statt „Q scharf, dann
LMB ziehen". Ersetzt die Slice-3-Geste (KEEP 2026-09-25); Ziel-Regel (Slice 4 A4/E7/E8) und
symmetrisches Verhalten bleiben unverändert. Q ist im Lab jetzt ungebunden. Die Konsole listet
beim Start keine `key:q`/`key:w`-Overrides (W fällt auf den globalen Default `Move` zurück).

1. `python experiments/symmetry_lab/run.py`, **Shift+S** (→ X), einen gepaarten Vertex anklicken.
2. **W gedrückt halten und die Maus bewegen** (keine Maustaste) → Vertex und Partner folgen
   live, spiegelbildlich (`Move: bewegt`). **W loslassen** → `Move übernommen`, ein
   Undo-Schritt.
3. **W antippen** ohne Mausbewegung → `Move: nur angetippt — nichts bewegt`, kein Undo-Schritt.
4. W halten, bewegen, **ESC** → zurück auf den Ausgangszustand, kein Undo-Schritt.
5. Ohne Auswahl über einem Vertex schweben, W halten, bewegen → der gehoverte Vertex bewegt sich.
6. Während W gehalten wird: Alt+LMB orbitet weiter; danach bewegt die Maus wieder den Vertex.
7. **Ctrl+Z** / **Ctrl+Y** → Move zurück / wieder.

Verdikt (KEEP / ITERATE / REJECT / UNKNOWN): steht aus.

### Manuelle Prüfung S2 (Manu, Windows) — KEEP 2026-10-03 (Pivot B)

*Verdikt (Stand 2026-10-03): **KEEP** mit Pivot pro Seite (B) (Manu, 2026-10-03; Gemeinsame Prüf-Session, Punkt 2).*

**Artist-Verdikt: steht aus.** WP-SYM-LAB-02 S2. Rotate/Scale wirken unter Symmetrie wie Move
(AD-SYM-02 §2.4, entschieden): der Partner führt die *gespiegelte Absicht* aus — bei Rotation um die
Ebenennormale im selben Sinn, um eine Achse in der Ebene im Gegensinn; bei Scale je Achse gespiegelt.
Der **Pivot** (Kandidat, Verdikt offen) ist der Mittelpunkt über Auswahl ∪ Partner, ein einzelner
Vertex dreht/skaliert also um die Paarmitte auf der Ebene. *Überholt 2026-10-03:* Artist-Entscheidung
**B — Pivot pro Seite** (Mitte der eigenen Auswahl, die Gegenseite um den gespiegelten Punkt; Rückfall
auf die Paarmitte, wenn ein Seam-Vertex dabei ist). Ein einzelner Vertex dreht/skaliert damit um sich
selbst. Die Paarmitte bleibt als Idee für ein späteres Pivot-System (freie/temporäre Pivots). Die
Schritte unten beschreiben noch das alte Verhalten; die Nachprüfung steht in der „Gemeinsamen
Prüf-Session“, Punkt 2. Neu im Lab: die Constraint-Tasten
**X / Y / Z** (Shift+X/Y/Z = Ebene) als Toggle wie in der App; sie gelten ab der nächsten Geste und
nur für E/R (W bleibt unverändert). Die Statuszeile zeigt `Constraint: X`.
Seam-Vertices (grün) bleiben exakt auf der Ebene oder die Aktion wird **vor der ersten Bewegung**
mit Meldung abgelehnt (`Rotate: abgelehnt — …`): Rotate nur um X (= Ebenennormale bei Symmetrie X);
Y, Z und „frei" (Bildachse) werden abgelehnt. Scale ist mit uniform und jedem Weltachsen-Constraint
erlaubt. Ein einzelner Seam-Vertex ist sein eigener Pivot (nichts zu bewegen: `keine Änderung`).

1. `python experiments/symmetry_lab/run.py head_basemesh`, **Shift+S** → X. Einen Vertex an der
   Seite des Kopfes anklicken.
2. **E halten**, Maus bewegen: Vertex und Partner drehen gemeinsam um ihre Mitte (Bildachse).
   Dann nacheinander **X**, **Y**, **Z** (Constraint) und jeweils neu E halten: beobachten, in
   welche Richtung der Partner dreht (X: gleicher Sinn, Y/Z: Gegensinn). Ein Undo-Schritt je Geste.
3. **R halten**: das Paar rückt auseinander/zusammen. Frage: fühlt sich ein einzelner Vertex wie
   ein Paar an, und ist die Paarmitte der Pivot, den du erwartest?
4. Einen grünen Seam-Vertex wählen, **E halten** mit X / Y / Z-Constraint (und frei): Y, Z und
   frei werden mit Meldung abgelehnt, X läuft (bewegt aber den einzelnen Seam-Vertex nicht).
   Ist die Ablehnung für jetzt akzeptabel?
5. Beide Vertices eines Paares explizit wählen (Auswahl ersetzt im Lab, daher nur über Tests/Aufruf
   mit Mehrfachauswahl abgedeckt) — starre Rotation, wie bei Move. Im Lab selbst nicht klickbar.

Verdikt (KEEP / ITERATE / REJECT / UNKNOWN): steht aus.

### Manuelle Prüfung E5 (Manu, Windows) — KEEP-BLOCK 2026-10-03, siehe AD-SYM-02 §4

*Verdikt (Stand 2026-10-03): **KEEP-BLOCK** (Manu, 2026-10-03, auf dem App-Pfad mit C geprüft); BLOCK ist seit Slice 5 der Default.*

**Artist-Verdikt: steht aus.** WP-SYM-LAB-02 S1, Experiment E5 / INV-8 (AD-SYM-02 §4). Bei aktiver
Symmetrie verhält sich ein Tool, dessen Operation `supports_symmetry = False` hat (heute Rotate und
Scale), je nach Lab-Modus so — **entschieden ist nichts**, das Lab macht beide Varianten vergleichbar:

- **MARK** (Default): das Tool läuft einseitig wie in der App; die Statuszeile meldet
  `Symmetrie aktiv — <Tool> spiegelt nicht (läuft einseitig)`; der Partner bewegt sich nicht und
  seine Markierung ist währenddessen ausgeblendet. Ein Undo-Schritt.
- **BLOCK**: das Tool wird nicht scharf, die Statuszeile nennt den Grund; kein History-Eintrag.

Die Statuszeile zeigt bei aktiver Symmetrie den Modus (`E5: MARK` / `E5: BLOCK`). Shift+B schaltet
nur diesen Lab-Zustand um, nie Mesh, History oder Undo/Redo. Das Gate liest das Klassenattribut
`supports_symmetry` der Operation (keine Tool-Liste); Move (W) und Knife (C) sind in beiden Modi
unverändert. Ohne Symmetrie verhalten sich E/R wie in der Production-App.

1. `python experiments/symmetry_lab/run.py head_basemesh`, **Shift+S** → X.
2. Einen Vertex an der Seite des Kopfes anklicken. **W halten**, Maus bewegen: Vertex und Partner
   bewegen sich spiegelbildlich (Referenz: so fühlt sich „unterstützt" an).
3. Denselben Vertex: **E halten**, Maus bewegen (MARK): nur dein Vertex dreht sich; Statuszeile
   lesen. Loslassen, **Ctrl+Z**. Dasselbe mit **R**.
4. **Shift+B** (BLOCK). **E halten**, Maus bewegen: nichts passiert, die Statuszeile nennt den
   Grund. Dasselbe mit **R**.
5. Frage: Womit würdest du im Alltag lieber arbeiten — Tool verweigert (BLOCK) oder läuft
   einseitig mit Warnung (MARK)? Hast du die Statuszeile im MARK überhaupt bemerkt?

**Seit S2 (2026-10-03):** Rotate/Scale sind symmetrisch (siehe „Manuelle Prüfung S2"). Der
S1-Behelfs-Pivot (Ursprung) ist entfernt; das Gate findet unter W/E/R/C kein nicht unterstützendes
Tool mehr, der Code bleibt, weil das E5-Verdikt noch offen ist. Die Schritte 3–4 oben gelten damit
nur noch mit einem (in Tests simulierten) nicht unterstützenden Tool.

**Seit WP-SYM-LAB-03 Slice 4 (2026-10-03):** auf dem App-Pfad prüfbar mit C als nicht spiegelndem
Tool — [„Gemeinsame Prüf-Session nach Slice 4"](#gemeinsame-prüf-session-nach-slice-4-manu-windows--offen), Punkt 3.

Verdikt: **KEEP-BLOCK** (Manu, 2026-10-03, auf dem App-Pfad mit C geprüft — siehe „Gemeinsame Prüf-Session nach Slice 4“, Punkt 3).

### Manuelle Prüfung Slice 7 (Manu, Windows) — historisch, nie verdiktet; bezieht sich auf den gelöschten alten Lab-Pfad (WP-SYM-LAB-03 S5)

*Verdikt (Stand 2026-10-03): **Moot, nie verdiktet** (Plan §4.2): der gespiegelte Knife wird nicht auf den App-Pfad übernommen (Kopie vor B7) und ist in Slice 5 gelöscht. Die Befunde E23–E30 bleiben als Forschung für einen künftigen symmetrischen One Knife.*

**Artist-Verdikt: steht aus.** Baut auf Slice 3–5 auf; hier nur, was neu ist. Die Konsole listet
beim Start zusätzlich `key:c -> Knife`.

1. `python experiments/symmetry_lab/run.py head_basemesh`, **Shift+S** → `Symmetrie: X (valid)`,
   dann **C** → Statuszeile zeigt `Knife: aktiv (kein Start)` und `Knife gestartet`. Die gelbe
   Vertex-Hover-Markierung aus Slice 4 ist ab jetzt durch die Knife-Markierung ersetzt.
2. Maus über eine Kante seitlich am Kopf bewegen (nicht auf der Mittellinie) → **großer gelber
   Punkt** auf der Kante (dort, wo geschnitten würde), **türkiser Punkt** an der gespiegelten
   Stelle auf der anderen Seite. Nahe an einem Kantenende rastet der Punkt auf den Vertex ein
   (wie im Playground).
3. **Klicken** → der Punkt wird real, auf beiden Seiten entsteht ein neuer Vertex. Der Startpunkt
   ist jetzt **violett**, sein Spiegelpartner türkis; Statuszeile `Knife: aktiv (Start v<id>)`,
   `Knife: Schritt angenommen`.
4. Maus über eine zweite Kante **derselben Face** bewegen (gelb + türkis), klicken → die
   Verbindung entsteht auf beiden Seiten; der Startpunkt wandert an das neue Ende. Weitere Klicks
   setzen den Schnitt fort.
5. Maus auf eine Kante **auf der Mittellinie** (zwischen zwei grünen Seam-Vertices) bewegen →
   gelber Punkt **ohne** türkisen Spiegelpunkt: der Schnittpunkt liegt auf der Seam und ist sein
   eigenes Spiegelbild (Sonderfall, kein Fehler). Klicken geht.
6. Nicht auflösbar vor dem Klick: einen **grünen Seam-Vertex als Start** anklicken (neue Session
   oder nach Schritt 5), dann die Maus auf einen **anderen grünen Seam-Vertex** oder eine
   **andere Seam-Kante** bewegen → der Punkt wird **magenta**, kein türkiser Punkt, die
   Statuszeile nennt `Ziel: Schnitt entlang der Seam nicht unterstützt`. Ein Klick dort wird
   abgelehnt, am Mesh ändert sich nichts.
   Der Fall aus Slice 6 („Beobachtet, nicht entschieden": nach einem Schnitt `a → m` mit `m` auf der
   Seam den Spiegelpunkt `a'` anklicken) zeigt sich **anders**: `a'` hat einen eindeutigen Partner
   (`a`), die Vorschau zeigt ihn deshalb gelb + türkis; erst der Klick wird mit
   `Verbindung … existiert bereits` abgelehnt. **Erste offene Frage an dich:** stört das den Fluss,
   oder ist es erwartbar?
7. **Klick auf den freien Hintergrund** (neben dem Kopf) → `Knife committet`, die Session endet,
   die Knife-Zeile verschwindet aus der Statuszeile. **Ctrl+Z** nimmt den ganzen Schnitt in einem
   Schritt zurück, **Ctrl+Y** stellt ihn wieder her. Ohne vorherigen Schnitt (nur C, dann
   Hintergrund) → `Knife — keine Schnitte`, kein Undo-Schritt.
8. Schritte 1–4 wiederholen und statt Schritt 7 **ESC** drücken → `Knife abgebrochen`, das Mesh ist
   wie vor dem C, kein Undo-Schritt; das Fenster bleibt offen.
9. **Frage A12:** Während einer Session auf eine **Fläche** klicken (auf dem Mesh, aber weder
   Vertex noch Kante in Reichweite) → es passiert nichts, die Session läuft weiter. Fühlt sich
   dieses „No-op" richtig an, oder hättest du erwartet, dass auch das committet?
10. Während der Session: Alt+LMB / Shift+LMB / MMB / Mausrad navigieren weiter. **Shift+S**, **W**,
    **M**, **Ctrl+Z**, **Ctrl+Y** tun nichts, die Statuszeile meldet
    `Knife aktiv — Befehl ignoriert`. **Enter** ist im Lab nicht belegt (A13) — falls du beim
    Testen Enter zum Bestätigen vermisst, bitte notieren.
11. Ablehnungen beim Start (Statuszeile, keine Session): **C** bei `man_with_shoes_basemesh` mit
    Symmetrie X (`partial`); **C** bei `subd_cube` mit Symmetrie Y; **W** gedrückt halten (Move
    scharf) und dann **C**; **M** (Re-Symmetrize-Vorschau offen) und dann **C**. Ohne Symmetrie startet **C** einen
    ungespiegelten Knife (`Knife: aktiv (kein Start, ungespiegelt)`), ohne türkise Punkte.

### Manuelle Prüfung Slice 3 (Manu, Windows) — KEEP (2026-09-25)

*Verdikt (Stand 2026-10-03): **KEEP** (Manu, 2026-09-25); auf dem App-Pfad bestätigt (Gemeinsame Prüf-Session, Punkt 1).*

*Historisch (2026-09-27): geprüft mit **Q** + LMB-Ziehen. Seit 2026-09-27 ist Move **W halten +
Maus bewegen** — siehe „Move-Bedienung wie die App" oben.*

**Artist-Verdikt (Manu, 2026-09-25): KEEP.** Aussage: „Läuft bisher alles wie geplant."
Prüfschritte, wie geprüft:

1. Terminal öffnen, in den Repo-Ordner wechseln (`cd <pfad>\Mirai-Bastel`).
2. `python experiments/symmetry_lab/run.py head_basemesh` starten. Die Konsole listet jetzt
   zusätzlich `key:Shift+s -> SymmetryCycle`. Statuszeile unten links:
   `Symmetrie: aus (off) | Move: bereit | Auswahl: —`.
3. **Shift+S** drücken → hellblauer Rechteck-Umriss in der Ebene x = 0 um den Kopf, grüne
   Punkte auf der Mittellinie (Seam). Statuszeile: `Symmetrie: X (valid) | ohne Partner: 0`.
4. Weiter **Shift+S** → `Y (partial)`, dann `Z (partial)`: Umriss liegt jeweils in der anderen
   Ebene, alle Vertices werden magenta (ohne Partner — der Kopf ist dort nicht symmetrisch).
   Noch einmal **Shift+S** → `aus`, Umriss und Markierungen verschwinden. Wieder auf **X**
   schalten.
5. LMB-Klick auf einen Vertex seitlich am Kopf → Vertex rot, der gespiegelte Partner auf der
   anderen Seite türkis (Vorschau, noch nichts bewegt).
6. **Q** drücken → Statuszeile `Move: scharf`. Optional vorher noch mit Alt+LMB die Ansicht
   drehen — das geht, solange Move scharf ist. Dann **LMB gedrückt halten und ziehen** →
   Vertex und Partner bewegen sich spiegelbildlich (`Move: zieht`). Loslassen →
   `Move übernommen`, `Move: bereit`.
7. **Ctrl+Z** → beide Seiten springen exakt zurück, Auswahl ist leer. **Ctrl+Z** noch einmal →
   Symmetrie ist wieder `aus` (nimmt das letzte Shift+S aus Punkt 4 zurück). **Ctrl+Y** →
   wieder `X`.
8. Abbrechen: Vertex wählen, **Q**, ziehen und **während des Ziehens ESC** → Vertex springt
   zurück, kein Undo-Schritt entsteht. **Q** und dann **ESC** (ohne Ziehen) → nur entschärft,
   Fenster bleibt offen. ESC im Leerlauf schließt wie bisher das Fenster.
9. Seam: einen grünen Vertex wählen, **Q**, ziehen → er gleitet nur entlang der Mittelebene.
10. **Q ohne Auswahl** → Statuszeile meldet `Move: keine Auswahl`, nichts wird scharf. (Slice 4:
    diese Regel gilt so nur noch, wenn der Cursor dabei auch über keinem Vertex steht — siehe
    Ziel-Regel unten.)
11. `python experiments/symmetry_lab/run.py man_with_shoes_basemesh`, **Shift+S** →
    `Symmetrie: X (partial) | ohne Partner: 54`; die 54 Vertices sind magenta markiert (siehe
    Befund E4 unten).

### Manuelle Prüfung Slice 5 (Manu, Windows) — KEEP (2026-09-25)

*Verdikt (Stand 2026-10-03): **KEEP** (Manu, 2026-09-25); auf dem App-Pfad bestätigt (Gemeinsame Prüf-Session, Punkt 1).*

*Historisch (2026-09-27): geprüft mit **Q** + LMB-Ziehen. Seit 2026-09-27 ist Move **W halten +
Maus bewegen** — siehe „Move-Bedienung wie die App" oben.*

**Artist-Verdikt (Manu, 2026-09-25): KEEP.** Aussage: Solange die Vertices exakt auf der
Symmetrie-Linie liegen, funktioniert Re-Symmetrize reibungslos. Liegt ein Vertex nicht exakt in
der Mitte, funktioniert Symmetrie weiterhin, Re-Symmetrize aber erwartungsgemäß nicht — so wie der
aktuelle Stand sein soll.

*Einordnung (Agent, nicht Teil des Verdikts):* Nachgestellt am Code. Rutscht ein Seam-Vertex erst
**nach** dem Einschalten von der Ebene, legt Re-Symmetrize ihn wieder exakt darauf (`valid`).
Liegt ein Mittel-Vertex schon **beim Einschalten** nicht exakt auf `0.0`, entsteht durch E3 eine
Lücke in der Seam, das Mesh zerfällt nicht in zwei Teile und Re-Symmetrize wird mit
„Seam teilt das Mesh in 1 Teile (nötig: genau 2)" abgelehnt. Folgefrage für spätere Versionen:
`docs/research/symmetry/SYMMETRY_EVOLUTION_RESEARCH.md` §12.

Baut auf Slice 3/4 auf; hier nur, was neu ist.

1. `python experiments/symmetry_lab/run.py man_with_shoes_basemesh` starten. Die Konsole listet
   zusätzlich `key:m -> ReSymmetrize`.
2. **Shift+S** → `Symmetrie: X (partial) | ohne Partner: 54`; die 54 Vertices sind magenta.
3. Einen Vertex auf der **rechten** Körperseite **anklicken** (rot).
4. **M** drücken → Vorschau: über der Statuszeile erscheint eine blaue Zeile, z. B.
   `Re-Symmetrize Quelle +X → Ziel −X: bewegt 27, Seam → Ebene 0 | M = ausführen, ESC = abbrechen`
   (welches Vorzeichen „rechts" ist, hängt von der Ansicht ab). Die 27 Vertices der anderen
   Seite, die sich bewegen werden, sind **blau** markiert. Die Linien von der aktuellen zur neuen
   Position sind hier nur ~`1e-6` lang und deshalb nicht zu sehen.
5. Während die Vorschau offen ist: Alt+LMB / Shift+LMB / MMB / Mausrad navigieren weiter.
   **Q**, **Shift+S**, **Ctrl+Z**, **Ctrl+Y** und ein LMB-Klick tun nichts; die Statuszeile
   meldet `Vorschau aktiv — Befehl ignoriert`. Die gelbe Hover-Markierung ist ausgeblendet.
6. **M** erneut → `Symmetrie: X (valid) | ohne Partner: 0`, `Re-Symmetrize ausgeführt: 27
   Änderungen`. Alle magenta Markierungen sind verschwunden; die ehemals magenta Vertices
   zeigen beim Hover/bei Auswahl jetzt einen türkisen Partner.
7. **Ctrl+Z** → wieder `partial`, 54 magenta (ein Schritt). **Ctrl+Y** → wieder `valid`.
8. Abbrechen: Vertex wählen, **M**, dann **ESC** → Vorschau verschwindet, nichts geändert,
   kein Undo-Schritt; das Fenster bleibt offen.
9. Dasselbe mit einem Vertex auf der **linken** Seite wiederholen (vorher Ctrl+Z) → Richtung in
   der Vorschau-Zeile ist umgekehrt, Ergebnis ebenfalls `valid`.
10. Mit `head_basemesh` (schon exakt symmetrisch), Symmetrie X, Vertex wählen, **M** → Vorschau
    zeigt `0 Änderungen`; **M** → `0 Änderungen — kein Schritt`, Ctrl+Z nimmt dann das
    Shift+S zurück, nicht Re-Symmetrize.
11. Quellseite folgt der Topologie, nicht der Position: `head_basemesh` neu starten und
    **ohne** Symmetrie einen Vertex seitlich am Kopf wählen, mit **Q** + LMB-Ziehen **über die
    Mittelebene hinaus** auf die andere Seite ziehen (ohne Symmetrie bewegt sich nur dieser
    eine Vertex). Dann **Shift+S** (→ X; der Vertex und sein alter Partner sind jetzt magenta,
    die Auswahl bleibt) und **M** → die Vorschau nennt als Quelle die **ursprüngliche** Seite
    des Vertex, und blau markiert ist sein alter Partner. **M** → der Partner springt
    spiegelbildlich ebenfalls über die Ebene, `Symmetrie: X (valid)`.
12. Ablehnungen (Statuszeile, keine Vorschau): **M** ohne Auswahl; **M** bei Symmetrie aus;
    **M** mit einem grünen Seam-Vertex als Auswahl; **M** bei Symmetrie **Y** auf `subd_cube`
    (Seam teilt das Mesh nicht in zwei Teile); **Q** und dann **M** (Move scharf).

### Manuelle Prüfung Slice 4 (Manu, Windows) — KEEP (2026-09-25)

*Verdikt (Stand 2026-10-03): **KEEP** (Manu, 2026-09-25). Schritt 10 (symmetrische Schattierung, E10) gilt auf dem App-Pfad nicht mehr: Q1 = (a) (Manu, 2026-10-03).*

*Historisch (2026-09-27): geprüft mit **Q** + LMB-Ziehen. Seit 2026-09-27 ist Move **W halten +
Maus bewegen** — siehe „Move-Bedienung wie die App" oben.*

**Artist-Verdikt (Manu, 2026-09-25): KEEP.** Aussage: „Läuft bisher alles wie geplant."
Baut auf Slice 3 auf; hier nur, was neu ist.

1. `python experiments/symmetry_lab/run.py head_basemesh` starten, Symmetrie mit **Shift+S**
   auf `X` schalten (siehe Slice 3, Schritt 3).
2. Maus **ohne zu klicken** über einen Vertex seitlich am Kopf bewegen → der Vertex wird
   **gelb** (Hover), der gespiegelte Partner auf der anderen Seite **türkis** — ohne dass
   irgendetwas ausgewählt wurde (Statuszeile `Auswahl: —` bleibt).
3. Maus über einen anderen Vertex bewegen → die gelbe/türkise Markierung folgt dem Cursor.
4. Bei einem Vertex **Q** drücken (ohne vorher zu klicken) → Statuszeile
   `Move: scharf (Hover v<id>)`. Dann **LMB gedrückt halten und ziehen** → derselbe Vertex
   (und bei Symmetrie sein Partner) bewegt sich, obwohl nie geklickt wurde. Loslassen →
   `Move übernommen`; **Auswahl bleibt danach leer** (E8) — nur der Hover war das Ziel.
5. Vor dem LMB-Press die Maus testweise woandershin bewegen (Hover ändert sich sichtbar),
   **dann erst** ziehen → es bewegt sich weiterhin der bei Q anvisierte Vertex, nicht der,
   über dem die Maus jetzt steht (E7 — Ziel steht seit dem Q-Druck fest).
6. Einen Vertex **anklicken** (Auswahl, rot) und dann die Maus über einen **anderen** Vertex
   bewegen (der wird gelb) → **Q**, ziehen → es bewegt sich die **Auswahl** (rot), nicht der
   Hover-Vertex; Statuszeile zeigt `Move: scharf (Auswahl)`.
7. Auswahl leeren (Klick ins Leere), Maus **über keinen Vertex** bewegen (z. B. Hintergrund),
   **Q** drücken → Statuszeile meldet, dass nichts zu bewegen ist; nichts wird scharf.
8. Wie Slice 3, Schritt 8 (Abbrechen mit ESC während des Ziehens): mit einem Hover-Ziel statt
   einer Auswahl wiederholen → der Vertex springt exakt zurück, kein Undo-Schritt, Auswahl
   bleibt leer.
9. Kamera drehen (Alt+LMB) oder einen Move ziehen, währenddessen auf einen anderen Vertex
   zeigen → die gelbe Hover-Markierung ändert sich währenddessen **nicht**; erst nach dem
   Loslassen springt sie auf den Vertex unter dem jetzt aktuellen Cursor.
10. Mit `subd_cube` oder `head_basemesh` vergleichen, ob die Schattierung bei aktiver
    X-Symmetrie links/rechts gleich aussieht (Anzeige-Triangulierung, E10) — insbesondere bei
    `subd_cube`, wo die alte Fan-Triangulierung sichtbar asymmetrisch schattierte.

### Manuelle Prüfung Slice 2 — von Manu am 2026-09-24 geprüft

*Verdikt (Stand 2026-10-03): Geprüft (Manu, 2026-09-24).*

Start, Orbit/Pan/Zoom, Vertex-Klick wie beschrieben (laut Slice-3-Handoff). Zur Referenz:

1. Terminal öffnen, in den Repo-Ordner wechseln (`cd <pfad>\Mirai-Bastel`).
2. `python experiments/symmetry_lab/run.py` starten → Fenster „Mirai-Bastel — Symmetry Lab
   [subd_cube]" mit blau-grauem Mesh, dunklen Edges, orangen Vertex-Punkten, Statuszeile unten
   links.
3. Alt+LMB ziehen → Orbit. Shift+LMB ziehen und MMB ziehen → Pan. Mausrad → Zoom.
   RMB ziehen → **nichts** (bewusst ungebunden).
4. LMB-Klick auf einen Vertex → Vertex wird rot und größer, Statuszeile zeigt `Auswahl: v<id>`.
   Klick auf einen anderen Vertex ersetzt die Auswahl. Klick ins Leere leert sie.
5. Dasselbe mit `head_basemesh` und `man_with_shoes_basemesh` wiederholen.

### Steuerung

*Verdikt (Stand 2026-10-03): Referenz: Steuerung des alten Labs (eigener Dispatcher, gelöscht in Slice 5). Heute: Abschnitt „Steuerung" oben.*

| Aktion | Input | Command | Herkunft |
|---|---|---|---|
| Orbit | Alt+LMB (Drag) | `Orbit` | Lab-Override — Artist Truth + Playground-Praxis |
| Pan | MMB (Drag) | `Pan` | Lab-Override — preserve lab MMB pan after WP-06 B2 global change |
| Pan | Shift+LMB (Drag) | `Pan` | Lab-Override — Artist Truth + Playground-Praxis |
| Zoom | Wheel Up/Down | `Zoom` | globaler Default (Fallback) |
| Vertex auswählen | LMB (Klick) | `Select` | globaler Default (Fallback) |
| — | RMB | *explizit ungebunden* | Lab-Override — eine Primärbindung pro Funktion |
| Symmetrie durchschalten (aus → X → Y → Z → aus) | Shift+S | `SymmetryCycle` (Lab-lokal) | Lab-Override — Artist A2 |
| Move scharf schalten (Ziel: Auswahl, sonst Hover) | W (gedrückt halten) | `Move` | Artist Manu 2026-09-27 (wie App, WP-06 B3), globaler Default (Fallback) |
| Move bewegen / übernehmen | Mausbewegung bei gehaltenem W (keine Maustaste) / W loslassen | — (AD-016 hold-key-hover, `MoveTool`) | Artist Manu 2026-09-27 |
| Rotate / Scale scharf schalten (Ziel wie Move) | E / R (gedrückt halten), Maus bewegen, loslassen übernimmt | `Rotate` / `Scale` | globaler Default (Fallback), AD-016 hold-key-hover — WP-SYM-LAB-02 S1 |
| Constraint für Rotate/Scale (Toggle, ab nächster Geste) | X / Y / Z, Shift+X/Y/Z (Ebene) | `ConstrainAxis*` / `ConstrainPlane*` | globaler Default (Fallback), WP-SYM-LAB-02 S2 |
| E5-Modus MARK ↔ BLOCK (nur Lab-Zustand) | Shift+B | `SymmetryGateMode` (Lab-lokal) | Lab-Override — Artist E5 test |
| Re-Symmetrize: Vorschau öffnen / ausführen | M / M erneut | `ReSymmetrize` (Lab-lokal) | Lab-Override — Artist A7 |
| Knife starten | C | `Knife` (Lab-lokal) | Lab-Override — Artist A8, E23 |
| Knife: schneiden (Vertex oder Kante unter dem Cursor) | LMB ohne Modifier (Klick, während Knife aktiv) | — (Lab-Geste, `LabKnifeTool.click`) | Artist A8, E25/E29 |
| Knife: committen | LMB-Klick auf den Hintergrund (außerhalb des Mesh) | — (Lab-Geste, `LabKnifeTool.commit`) | Artist A8/A12, E25 |
| Abbrechen (Move, Re-Symmetrize-Vorschau, Knife-Session) | ESC | `Cancel` | globaler Default (Fallback) |
| Undo / Redo | Ctrl+Z / Ctrl+Y | `Undo` / `Redo` | globaler Default (Fallback) |

`SymmetryCycle`, `ReSymmetrize` und `Knife` sind im Lab definiert (`lab_bindings.py`), nicht in
`mirai.interaction.commands`. C ist seit WP-06 B6 global an `Connect` gebunden; im
`symmetry_lab`-Kontext gewinnt der Lab-Override C → `Knife` (E23). Enter ist nicht belegt (A13; `mirai.pyglet_input`
übersetzt Enter gar nicht in ein `Input`).
Andere global gebundene Commands (z. B. `f` → `SetFaceMode`) lösen zwar auf, sind im Lab aber
No-ops und gelten als „nicht behandelt". Die Mausbewegung selbst (`on_mouse_motion`, ohne
gedrückte Taste) ist kein Command — sie treibt nur das Hover-Ziel (siehe unten).

**Drag/Klick-Semantik der Maus (Lab-lokal):** Der Press bestimmt das Command;
Orbit/Pan laufen bis zum Release derselben Maustaste, auch wenn währenddessen Modifier
losgelassen werden. Select wird beim Release ausgeführt, wenn die Maus weniger als 5 px
(Manhattan-Summe, wie Playground) bewegt wurde; sonst passiert nichts (kein Box-Select).

**Move (seit 2026-09-27 wie die App: W, AD-016 hold-key-hover) — Ziel-Regel (Slice 4, Artist
A3/A4):** Der Artist zeigt auf einen Vertex, hält **W** und bewegt die Maus (ohne Maustaste),
ohne vorher zu klicken. Welcher Vertex sich bewegt, entscheidet beim W-Druck (wie im
Playground, WP-STAB-04):

1. Auswahl nicht leer → die Auswahl bewegt sich (unverändert seit Slice 3).
2. Auswahl leer, aber ein Vertex liegt unter dem Cursor (Hover) → **dieser** Vertex bewegt
   sich, ohne dass er zuvor ausgewählt werden musste. `scene.selection` bleibt dabei leer
   (E8) — nach Commit/Cancel ist die Auswahl genau wie vorher.
3. Beides leer → W wird abgelehnt (Statuszeile: „Move: keine Auswahl, kein Hover"), nichts
   wird scharf.

Das Ziel wird beim W-Druck **einmal** festgelegt (E7) und bleibt bis Commit/Cancel fest. Die
erste Mausbewegung bei gehaltenem W startet den Move (keine Schwelle), jede weitere bewegt live
weiter. **W loslassen** → `commit()` (genau ein Undo-Schritt); **W nur antippen** (keine
Bewegung dazwischen) → nichts passiert, kein Undo-Schritt. Danach ist Move entschärft — für den
nächsten Move erneut W. Die Statuszeile zeigt während Move scharf/bewegt, was sich bewegen wird
(„Auswahl" bzw. „Hover v<id>"). Solange W gehalten wird, navigieren Alt+LMB, Shift+LMB, MMB und
Wheel weiter (während einer Kamerageste bewegt sich der Vertex nicht); ein Klick wählt nichts
aus. Während eines laufenden Moves werden Shift+S, W, Ctrl+Z/Ctrl+Y ignoriert; nur ESC bricht ab
(und das Loslassen von W übernimmt). Q ist im Lab ungebunden.

**Hover (Slice 4, E9):** Der Vertex unter dem Cursor wird laufend hervorgehoben (gelb), bei
aktiver Symmetrie zusätzlich sein gespiegelter Partner (türkis, wie bei der Auswahl). Der
Hover aktualisiert sich nur im Leerlauf — während eines Kamera-Drags und solange W gehalten wird,
bleibt er unverändert (wie App, WP-06 B3 E24). Liegt der Hover auf einem Move-Ziel, wird er beim
W-Druck ausgeblendet; nach Commit/Cancel/Undo/Redo wird er an der letzten Cursorposition neu
bestimmt. Der Hover ist reine Anzeige; er berührt `scene.selection` nicht.

**Re-Symmetrize (Slice 5, Artist A6/A7, E12–E15):**

- **Quellseite = Seite der Auswahl (A6).** Genau ein Vertex muss ausgewählt sein. Seine Seite
  ist **topologisch** bestimmt (Seiten = die zwei Face-Komponenten links und rechts der Seam,
  siehe unten), nicht über das Vorzeichen seiner Position — ein Vertex, der schon über die Ebene
  gewandert ist, zählt weiterhin zu seiner ursprünglichen Seite. Die Anzeige „+X"/„−X" benennt
  die Seite mit dem größeren bzw. kleineren mittleren Achsenwert ihrer Vertices.
- **M** öffnet die Vorschau (nichts wird geändert). Abgelehnt — nur Statuszeile, keine
  Vorschau — wenn: ein Move scharf ist oder läuft; Symmetrie aus; keine Auswahl; ein
  Seam-Vertex ausgewählt ist; die Seam das Mesh nicht in genau zwei Teile teilt.
- Die Vorschau zeigt: Zielseiten-Vertices, die sich bewegen werden (blau, mit Linie zur neuen
  Position); Seam-Vertices, die auf die Ebene gelegt werden (hellgrün, mit Linie — nur die, die
  nicht schon exakt darauf liegen); Zielseiten-Vertices ohne Partner, die unverändert bleiben
  (hellrot). Eine eigene Zeile über der Statuszeile nennt Richtung, Anzahlen und
  „M = ausführen, ESC = abbrechen".
- **M** erneut → ausführen: jeder Zielseiten-Vertex mit topologischem Partner auf der
  Quellseite wird exakt auf dessen Spiegelposition gesetzt (`mirai.symmetry.mirror_position`),
  jeder Seam-Vertex exakt auf die Ebene (Achsenkomponente `0.0`); die Quellseite bleibt
  unverändert. Genau ein Undo-Schritt (`MeshStateCommand`). Gibt es nichts zu tun
  („0 Änderungen" — alles schon exakt symmetrisch, A5), entsteht **kein** History-Eintrag.
- **ESC** → Vorschau endet ohne Änderung, kein History-Eintrag.
- Während der Vorschau: Orbit/Pan/Zoom erlaubt; Select, W, Shift+S, Ctrl+Z/Ctrl+Y werden
  ignoriert (Hinweis in der Statuszeile); der Hover ist pausiert (ausgeblendet) und kehrt mit
  der nächsten Mausbewegung nach der Vorschau zurück. So kann sich das Mesh zwischen Vorschau
  und Ausführung nicht ändern — ausgeführt wird genau der angezeigte Plan.
- Die Auswahl bleibt nach der Ausführung erhalten (keine Topologie-Änderung, IDs bleiben gültig).

**Knife (Slice 7):** siehe Abschnitt „Gespiegelter Knife im Fenster (Slice 7)" unten.

**ESC-Regel:** Re-Symmetrize-Vorschau offen → Vorschau schließen; Knife-Session aktiv → Session
abbrechen, Mesh wie vor C, kein History-Eintrag; Move läuft → Abbruch auf
den exakten Vorzustand, kein History-Eintrag; Move nur scharf → entschärfen; sonst nicht
behandelt → pyglet-Standard (Fenster schließt).

**Undo/Redo** leeren danach die Auswahl (wie Playground — ein Snapshot-Load kann Vertex-IDs
ungültig machen) und entschärfen einen scharfen Move.

### Farblegende

*Verdikt (Stand 2026-10-03): Referenz: Farblegende des alten Renderers (gelöscht in Slice 5). Heute: „Overlays und Farblegende" oben.*

| Farbe | Bedeutung |
|---|---|
| blau-grau (shaded) | Faces |
| dunkelgrau | Edges |
| orange, klein | Vertex |
| rot, groß | ausgewählter Vertex |
| türkis, groß | gespiegelter Partner der Auswahl (`mirrored_selection`, Vorschau — INV-11) |
| grün, mittel | Seam-Vertex (Endpunkt einer deklarierten Seam-Edge) — nur bei aktiver Symmetrie |
| magenta, mittel | Vertex ohne Partner (`UNPAIRED`) — nur bei aktiver Symmetrie (INV-10) |
| weiß, mittel | Vertex mit mehrdeutigem Partner (`AMBIGUOUS`) — nur bei aktiver Symmetrie |
| gelb, mittel | Hover-Vertex — Vertex unter dem Cursor (Slice 4, E9) |
| hellblau, Linien | Umriss der Symmetrie-Ebene, auf die Mesh-Bounds + 10 % bemessen |
| blau, groß + Linie | Re-Symmetrize-Vorschau: Zielseiten-Vertex wird bewegt; Linie zur neuen Position (Slice 5) |
| hellgrün, groß + Linie | Re-Symmetrize-Vorschau: Seam-Vertex wird auf die Ebene gelegt; Linie zur neuen Position |
| hellrot, groß | Re-Symmetrize-Vorschau: Zielseiten-Vertex ohne topologischen Partner — bleibt unverändert |
| blaue Textzeile über der Statuszeile | Re-Symmetrize-Vorschau aktiv: Richtung, Anzahlen, Tasten |
| violett, groß | Knife: Start-Vertex der laufenden Session (Slice 7, E30) |
| türkis, groß (Knife) | Knife: Spiegelpartner des Starts bzw. Spiegelpunkt des Hover-Ziels — gespiegelte Vorschau wie überall |
| gelb, groß | Knife: Hover-Ziel, klickbar — Vertex oder der Punkt auf der Kante, an dem geschnitten würde |
| magenta, groß | Knife: Hover-Ziel, **nicht** klickbar (kein Spiegelpartner, Seam-Sehne, Kante am Start); Grund in der Statuszeile |

Punkte werden ohne Depth-Test gezeichnet (wie Slice 2): Rückseiten-Markierungen sind sichtbar.
Zeichenreihenfolge: Symmetrie-Markierungen (Seam/ohne Partner/mehrdeutig) → Re-Symmetrize-Vorschau
→ Hover + dessen gespiegelter Partner → Knife-Marker (Hover-Ziel, darüber Start) → Auswahl + deren
gespiegelter Partner zuletzt (überdeckt alles andere). Der Knife-Start liegt über dem Hover-Ziel,
weil der Cursor nach einem Klick genau auf dem neuen Start steht.
Magenta groß (Knife, nicht klickbar) und magenta mittel (Vertex ohne Partner) teilen die Farbe mit
Absicht: beides heißt „hier gibt es keine eindeutige Gegenseite".
Die Statuszeile bricht an der Fensterbreite um (Slice 7): mit Knife-Zeile und Ablehnungsgrund wird
sie breiter als das Fenster, und der Grund steht am Ende.
Der gespiegelte Partner des Hover-Vertex nutzt dieselbe Farbe wie der gespiegelte Partner der
Auswahl (türkis) — es ist dieselbe Vorschau-Mechanik (`mirrored_selection`), nur auf den
Hover statt auf `scene.selection` angewandt.

### Gespiegelter Knife — Lab-Experiment (Slice 6, headless)

*Verdikt (Stand 2026-10-03): Forschung, headless, **nie Artist-geprüft**. Die Engine (`lab_knife.py`) ist in Slice 5 gelöscht; Baseline und P1–P3 stehen weiter in `tests/test_lab_knife.py`. Grundlage für einen künftigen symmetrischen One Knife.*

*Historisch (2026-10-03, WP-SYM-LAB-03):* Die gespiegelte Knife-Engine (Slice 6/7) wird beim Umbau auf den Production-Pfad **nicht** übernommen. Sie kopiert das Modell vor B7 (inkrementell, ein echter Schnitt pro Klick), Production arbeitet dagegen mit dem virtuellen Pfad (WP-KNIFE-01 S2–S4). Die Befunde E23–E30 und P1–P3 bleiben als Grundlage für einen symmetrischen One Knife erhalten ([Rebase-Plan](../../docs/architecture/WP-SYM-LAB-03_REBASE_PLAN.md)).

`lab_knife.py`. **Lab-Experiment, keine Capability** — keine Änderung an `src/` oder am
Playground-Knife. Nur die Engine: kein Fenster, kein Edge-Hover, keine Pfad-Vorschau, keine
Taste (alles Slice 7). **Nicht vom Artist geprüft** — belegt ist nur das headless Verhalten
unten. Die Engine ist eine Kopie (Stand Slice 6) von `playground/topology_tools/knife.py` (seit WP-06 B7 liegt der
Knife unter `src/mirai/topology/knife.py`) und
`connect_in_shared_face` (Herkunftsvermerk im Docstring, Präzedenz AD-010, E16) und läuft nach
dem gleichen Session-Modell (AD-017 §6–§8): Klick = nächster Schnitt, In-Session-Undo/Redo =
letzter Schnitt, Cancel = alles verwerfen, Commit = genau ein `MeshStateCommand`. Kein
Auswahl-Residue: der Knife fasst `scene.selection` nicht an (E22).

**Was:** Ist Symmetrie an, erzeugt jeder Klick beide Seiten in *einem* Session-Schritt
(AD-SYM-02 §2.1, INV-7):

- **Edge-Klick:** Quelle `split_edge(e, t)` → `n`. Auf der Spiegel-Edge `split_edge(e', 0.5)` →
  `n'`, danach `n'` exakt auf `mirror_position(pos(n))` — **nicht** über ein gespiegeltes `t`
  (Befund P3). `n ↔ n'` wird als Absichts-Paar gemerkt.
- **Connect:** Quelle wie im Playground (niedrigste gemeinsame Face). Gespiegelt wird in **der**
  Face, deren Vertex-Menge das Partnerbild der Quell-Face ist — nicht in „irgendeiner" Face.
  Ist die Verbindung ihr eigenes Spiegelbild, entsteht sie genau einmal.
- **Seam-Edge-Klick:** kein Spiegel-Split; `n` ist selbst-gepaart und liegt exakt auf der Ebene
  (Achsenkomponente `0.0`). Die **Seam wird im selben Schritt nachgeführt**: neue
  `SymmetryDefinition` mit gleicher Ebene, die tote Edge raus, die zwei Halb-Edges rein. Ohne
  das zerfällt die Seam (Befund P1). Weil die Definition Teil von `export_state()` ist, nehmen
  In-Session-Undo und der Commit-Eintrag die Seam-Änderung automatisch mit.
- **Abgelehnt:** Start und Ziel beide auf der Seam („Schnitt entlang der Seam nicht
  unterstützt" — die Spiegel-Face würde dieselbe Verbindung ein zweites Mal verlangen; Vorbild
  Maya sperrt die Seam für Multi-Cut; Artist-Semantik offen), ein Ziel ohne auflösbaren
  Spiegelpartner (INV-5), eine fehlende Spiegel-Edge/-Face, eine schon existierende Verbindung.

**Warum so (A9):** Das Spiegelziel kommt aus dem **Operationskontext**, nicht aus Positionen
oder Topologie. Reihenfolge (E17): (1) Vertex in dieser Session erzeugt → sein Absichts-Partner
(`intent_pairs`, INV-6 „Gegenseite aus der Absicht"); (2) Endpunkt einer gültigen Seam-Edge →
er selbst (INV-4); (3) bestehende Geometrie → Capability-Korrespondenz `PAIRED` (bei `valid`
vollständig und exakt); (4) sonst abgelehnt. Position und Topologie sind danach **unabhängige
Validierung** jedes Schritts (E19, `validate_step`, als Datenobjekt `KnifeValidation`
abrufbar):

- **Position:** jedes Absichts-Paar `x ↔ y` ist in der Capability `PAIRED` mit Partner `y`,
  jeder selbst-gepaarte Vertex ist `SEAM`;
- **Topologie:** `lab_topology.topological_pairing` bildet jedes Absichts-Paar identisch ab;
- **Seam/Seiten:** `symmetry_state == valid`, genau 2 Seiten, 0 Konflikte.

Scheitert eine Prüfung, wird der ganze Schritt zurückgerollt (Mesh, Start, Pfad,
`intent_pairs`), die Meldung nennt die Prüfung (A11). Das ist die Regel dieses Experiments,
keine Architekturentscheidung über eine künftige Capability.

**Gate (A10, E20):** Symmetrie aus → Knife läuft ungespiegelt wie im Playground, ohne
Validierung. Symmetrie an und nicht (`valid` und 2 Seiten) → `begin` wird abgelehnt
(`KnifeRejected`), keine Session — z. B. `man_with_shoes_basemesh` X (`partial`) und
`subd_cube` Y (keine Seam, 1 Seite).

**Befunde** (Ebene X, Seam aus E3; `tests/test_lab_knife.py`). Die „+X-Quad" ist die niedrigste
FaceId unter den Quads mit allen Vertices auf +X (`subd_cube` f12, `head_basemesh` f163);
geschnitten wird zwischen den Edges (v0, v1) bei t=0.3 und (v2, v3) bei t=0.6:

| Befund | `subd_cube` | `head_basemesh` |
|---|---|---|
| Baseline | `valid`, topo 26/26, Seiten 12/12 | `valid`, topo 326/326, Seiten 162/162 |
| **P1** Seam-Edge roh splitten (ohne Nachführung), t=0.37 | Vertex x = 0.0; `partial`; Seam 7/8 gültig; **1 Seite** | x = 0.0; `partial`; Seam 35/36; **1 Seite** |
| **P2** einseitiger Schnitt split(0.3) + split(0.6) + connect in einer +X-Quad | topo **0/28**, 28 Konflikte, 40 Face-Paar-Konflikte | topo **0/328**, 328 Konflikte, 644 Face-Paar-Konflikte |
| **P3** gespiegelter Schnitt über `1−t` (Kanten hier umgekehrt orientiert) | ein Spiegelpunkt 1.1e-16 daneben → `partial`, topo 30/30 | exakt → `valid` |
| **P3′** Spiegelpunkt über `mirror_position` (E18) | `valid`, topo 30/30, Seiten 13/13 | — |
| Engine: gespiegelter Schnitt Edge→Edge | `valid`, topo 30/30, Seiten 13/13 | `valid`, topo 330/330, Seiten 163/163 |

- **P1** ist der Grund für die Seam-Nachführung: die gesplittete Seam-Edge ist tot, die Seam
  hat eine Lücke, die Seiten laufen ineinander.
- **P2** — Gegenprobe (deckt sich mit Slice 5): einseitiger `split_edge` allein → topo 326/327
  (`head_basemesh`); einseitiger `connect_vertices` allein → Positionszustand `valid` bei
  asymmetrischer Topologie. Die *Ursache* des Totalausfalls ist nicht untersucht.
  **Beobachtung** (Probe mit einem Spion auf `lab_topology._walk`, ohne Code-Änderung): beide
  Hälften der geschnittenen Quad sind wieder 4-Ecke, gleich lang wie die ungeschnittene
  Spiegel-Quad, und die Breitensuche akzeptiert beide als Face-Paar mit ihr. Von diesen
  falschen Paaren läuft sie weiter (die Spiegel-Quad wird in 21 bzw. 320 Face-Paaren
  besucht), bis selbst alle Seam-Vertices im Konflikt sind (8/8, 36/36; im Test festgehalten:
  4-Ecke und Seam-Vertices im Konflikt). Der gespiegelte Knife vermeidet P2, weil beide Seiten
  im selben Schritt geschnitten werden; `lab_topology.py` bleibt unverändert.
- **P3:** Die Spiegel-Edges der +X-Quad sind in beiden Assets umgekehrt orientiert, also
  `1−t`. Auf `subd_cube` liegt ein so gesetzter Punkt eine Rundungsstufe neben der
  Spiegelposition; ohne Toleranz (A5) ist er dann `UNPAIRED`. Deshalb setzt die Engine den
  Punkt mit `mirror_position`. Wird die Platzierung künstlich auf `1−t` zurückgestellt
  (Monkeypatch im Test), lehnt die Validierung `Position` ab und rollt zurück; die Topologie
  bestätigt das Paar in diesem Fall trotzdem — die beiden Prüfungen können also
  unterschiedlich urteilen, genau dafür sind beide da.

**Slice 7:** jetzt im Fenster spielbar, siehe nächster Abschnitt. Die Engine selbst ist
unverändert.

**Beobachtet, nicht entschieden:** Nach einem Schnitt `a → m` (m auf der Seam) ist der
Klick auf den bestehenden Spiegelpunkt `a'` abgelehnt, weil `m–a'` schon existiert
(„Verbindung existiert bereits"); kein doppelter Edge, keine Sonderlogik.

**Grenzen:**

- Nur bei `valid` mit 2 Seiten; Knife bei `partial` ist offen (A10).
- Keine Face-Cuts (AD-017 §6 offen), keine Vorschau, keine Artist-Semantik für Seam-Sehnen.
- Undo/Cancel/Rollback stellen Vertices, Edges, Faces und Symmetrie-Definition bitgleich her,
  die ID-Zähler in `export_state()` aber nicht: `load_state` setzt sie nur vorwärts
  (AD-001, eine vergebene ID wird nie wieder ausgegeben). Redo ist auch in den Zählern
  bitgleich. Gleiche Ausnahme wie in den Playground-Knife-Tests.

### Gespiegelter Knife im Fenster (Slice 7)

*Verdikt (Stand 2026-10-03): **Moot, nie verdiktet** (Plan §4.2); Fenster, Picking und Vorschau des gespiegelten Knife sind in Slice 5 gelöscht. Befunde E23–E30 bleiben als Forschung.*

**Nicht vom Artist geprüft** — Prüfanleitung oben („Manuelle Prüfung Slice 7"). Die Engine aus
Slice 6 (`lab_knife.py`) ist unverändert; Slice 7 ruft sie nur auf (`begin`, `click`, `commit`,
`cancel`) und liest sie an (`start`, `intent_pairs`, `partner()`, `last_message`,
`last_validation`).

**Ablauf (A8, E24/E25/E29):**

- **C** startet eine Session. Abgelehnt (nur Statuszeile) bei scharfem oder laufendem Move, bei
  offener Re-Symmetrize-Vorschau (deren Hinweis), wenn schon eine Session läuft, und wenn `begin`
  ablehnt (Symmetrie an, aber nicht `valid` mit 2 Seiten — Meldung aus Slice 6, E20). Symmetrie
  aus → ungespiegelter Knife wie im Playground.
- **LMB-Klick** (unter 5 px Bewegung, wie Select) löst das Ziel unter dem Cursor mit
  `lab_knife_pick.knife_pick` auf (Lab-Kopie der Playground-Version, E27):
  - Vertex oder Kante → `knife.click` (Schnitt beider Seiten in einem Schritt, Slice 6).
    Angenommen → `Knife: Schritt angenommen`. Abgelehnt → die Meldung aus `knife.last_message`;
    ist die Validierung (E19) dieses Klicks gescheitert, steht dort, welche Prüfung (A11).
  - **Hintergrund** (außerhalb des Mesh) → Commit: ein History-Eintrag, oder keiner, wenn nichts
    geschnitten wurde (`Knife — keine Schnitte`). Die Session endet.
  - **Fläche** (auf dem Mesh, kein Vertex/keine Kante in Reichweite) → nichts (A12, Annahme, beim
    Test zu klären).
- **ESC** → `knife.cancel()`: Mesh und Symmetrie-Definition wie vor C (ID-Zähler ausgenommen,
  siehe Slice 6), kein History-Eintrag.
- Während der Session: Orbit/Pan/Zoom erlaubt; jedes andere Command wird mit
  `Knife aktiv — Befehl ignoriert` ignoriert, auch Ctrl+Z/Ctrl+Y (In-Session-Undo ist in Slice 7
  nicht an Tasten gebunden). Kein Enter-Commit (A13).

**Vorschau vor dem Klick (E26/E28, `lab_knife_preview.py`):** Bei jeder Mausbewegung bestimmt
`knife_hover_preview` ohne Mutation, was ein Klick erzeugen würde:

- **Quellpunkt:** der Vertex, bzw. auf einer Kante der Punkt bei `t` mit derselben Arithmetik wie
  `split_edge`.
- **Spiegelpunkt:** dieselbe Auflösung wie der echte Klick (E17/E18), mit den Methoden der Engine
  selbst (`partner`, `_seam_vertices`, `_is_seam_edge`, `edge_between`) — kein zweiter
  Algorithmus. Vertex → Position seines Partners; Kante auf der Seam → kein Spiegelpunkt (eigener
  Partner); sonst Partner-Kante über die Partner der Endpunkte → `mirror_position(Quellpunkt)`.
- **Nicht klickbar** (magenta, Grund in der Statuszeile): kein Spiegelpartner, keine Spiegel-Kante,
  Kante ist ihr eigenes Spiegelbild ohne Seam-Kante zu sein, Seam-Sehne (Start und Ziel auf der
  Seam), oder `knife.hover` lehnt das Ziel ab (Kante am Start-Vertex). Die Texte sind wortgleich
  mit den Ablehnungen des echten Klicks.

**Belegt (headless, `tests/test_lab_knife_window.py`):**

- Vorschau == echter Klick, bitgenau: für **jede** Kante von `subd_cube` und jede 7. Kante von
  `head_basemesh` als erster Klick (Quellpunkt, Spiegelpunkt bzw. Seam-Selbstpaarung) und für alle
  Vertices/Kanten der Faces um einen gesetzten Start als zweiter Klick.
- Was die Vorschau „nicht klickbar" nennt, lehnt der Klick immer ab.
- **Grenze (bewusst, E28 deckt nur Spiegel-Auflösbarkeit und Seam-Sehne ab):** Umgekehrt kann ein
  gelb angezeigtes Ziel beim Klick noch abgelehnt werden — in der Charakterisierung um einen Start
  (je Asset 20 Vertex-/Kanten-Ziele, davon 10 angenommen, 4 vorab magenta): der Start-Vertex selbst (`Ziel ist der Start-Vertex`) und
  seine schon verbundenen Nachbarn (`Verbindung … existiert bereits`), je 2+2+2 Fälle. Ebenso
  nicht vorab geprüft: keine gemeinsame Face, keine Spiegel-Face, gescheiterte Validierung (E19).
  Das sind Gründe des Klicks, nicht der Spiegelung; der Spiegelpunkt, den die Vorschau zeigt,
  stimmt in allen geprüften Fällen mit dem Ergebnis überein. Der Slice-6-Befund „`a'` nach
  `a → m`" gehört genau hierher (gelb, dann `existiert bereits`).
- Ein im Test erzwungener Validierungsfehler (Slice-6-Monkeypatch `1−t`) erscheint mit
  `Validierung gescheitert: Position (…)` in der Statuszeile.
- Der GL-Pfad (Renderer, Fenster, Statuszeile) wurde für diesen Slice einmal headless über EGL
  gezeichnet und die Bilder angesehen (Start violett, Hover gelb + türkis, Seam-Sehne magenta,
  umbrechende Statuszeile) — kein automatischer Test, keine Artist-Aussage.

### Anzeige-Triangulierung (Slice 4, E10)

*Verdikt (Stand 2026-10-03): **KEEP** (Slice 4, 2026-09-25); in Slice 5 gelöscht nach Q1 = (a) (Manu, 2026-10-03). Der Befund zur Production-Triangulierung steht in `tests/test_display_characterization.py`.*

Nur im Lab, keine Änderung an `src/viewport/derived.py` — reine Anzeige-Entscheidung, keine
Capability-Regel.

**Befund (verifiziert):** Die Production-Fan-Triangulierung
(`viewport.derived.triangulate_face`) wählt die Quad-Diagonale nach der gespeicherten
Vertex-Reihenfolge (immer die Diagonale zwischen dem ersten und dritten Boundary-Vertex).
Bei einem gespiegelten Quad-Paar ist diese Diagonale im Allgemeinen nicht die gespiegelte
Diagonale der anderen Seite:

| Asset (Achse) | gespiegelte Quad-Paare | davon mit asymmetrischer Fan-Diagonale | mit „kürzere Diagonale" |
|---|---|---|---|
| `subd_cube` (X) | 24 | 24 | 0 |
| `head_basemesh` (X) | 324 | 0 | 0 |

(`head_basemesh` war mit der Fan-Diagonale bereits symmetrisch — kein Unterschied zur
kürzeren Diagonale. Charakterisierung in `tests/test_draw_data.py`.)

**Lab-Entscheidung:** Beim Zeichnen (`lab_draw_data.face_data`, nicht bei Move/Picking/Core)
trianguliert das Lab abweichend von `viewport.derived.triangulate_face`:

- **Quads:** an der kürzeren der beiden Diagonalen — Kantenlängen sind unter Spiegelung
  invariant, das ist deshalb spiegelinvariant. Bei exakt gleicher Länge: bisheriges
  Fan-Verhalten (Diagonale zwischen erstem und drittem Vertex).
- **Dreiecke und n-Gons:** unverändert `triangulate_face`.
- **Normalen:** ebenfalls lab-lokal. `viewport.derived.DerivedGeometry` nimmt als
  Face-Normale das erste Dreieck der Fan-Triangulierung — vom Start-Vertex abhängig und
  deshalb bei gespiegelten Quads asymmetrisch. Das Lab berechnet die Face-Normale stattdessen
  nach **Newell** (ordnungsunabhängig vom Start-Vertex der Boundary, spiegeläquivariant) und
  die Vertex-Normale als normierte Summe der Normalen der angrenzenden Faces — gleiches
  Schema wie `DerivedGeometry`, nur mit den Newell-Face-Normalen. Für jedes Vertex-Paar mit
  Correspondence-Zustand `PAIRED` ist die Normale des einen Vertex exakt das Spiegelbild der
  Normale seines Partners (Test in `tests/test_draw_data.py`, kleine Float-Toleranz zulässig
  — das ist Anzeige, nicht die Capability).
- **Grenze, dokumentiert, nicht gelöst:** Ein Quad, das selbst über die Symmetrie-Ebene
  reicht (seine vier Vertices liegen nicht symmetrisch zueinander), kann prinzipiell nicht
  symmetrisch in zwei Dreiecke geteilt werden — die kürzere Diagonale ist dafür kein
  Ersatz, sie hilft nur bei Quads, deren gespiegeltes Gegenstück eine eigene Face ist.
- Übernahme dieser Triangulierung/Normalen-Wahl nach Production (Playground, Picking,
  Normal-Space) ist eine spätere, eigene Entscheidung — dieser Slice ändert dafür nichts an
  `src/`.

### Aufbau

*Verdikt (Stand 2026-10-03): Referenz: Aufbau des alten Labs (gelöscht in Slice 5). Heute: Abschnitt „Aufbau" oben.*

```
pyglet-Event → mirai.pyglet_input → app.bindings.command_for(input, "symmetry_lab") → LabDispatcher
```

| Datei | Inhalt | GL nötig |
|---|---|---|
| `run.py` | Einstieg: Argument prüfen, `Application` + Lab-Bindings, Fenster, Event-Loop | – |
| `_paths.py` | sys.path-Bootstrap (`src/` vor Repo-Root, `examples/`, `experiments/`) | nein |
| `lab_bindings.py` | `SYMMETRY_LAB_CONTEXT`, `LAB_OVERRIDES` (einzige Quelle der Overrides) | nein |
| `lab_scene.py` | Asset per Registry-Name laden, Auswahl leeren, Kamera rahmen | nein |
| `lab_dispatch.py` | Command → Kamera-Geste / Vertex-Pick / Hover / Symmetrie-Zyklus / Move (Ziel-Regel) / Re-Symmetrize-Vorschau / Knife-Session (Slice 7) / Undo | nein |
| `lab_symmetry.py` | Ebene (E1), Seam-Ableitung (E3), Zyklus als `MeshStateCommand` (E2), Befund | nein |
| `lab_topology.py` | Topologische Paarung (E11) und Seiten (E12) — Lab-Experiment | nein |
| `lab_resymmetrize.py` | Re-Symmetrize-Plan (E12/E13), Ausführung als `MeshStateCommand` (E14), Vorschau-Text | nein |
| `lab_knife.py` | Gespiegelter Knife (E16–E22), Validierung `validate_step` (E19) — Engine, seit Slice 7 über `lab_dispatch` im Fenster | nein |
| `lab_knife_pick.py` | Cursor → Knife-Ziel (Vertex/Kante mit `t`/Fläche/außerhalb), Lab-Kopie aus dem Playground (E27) | nein |
| `lab_knife_preview.py` | Dry-Run eines Hover-Ziels: Quellpunkt, Spiegelpunkt, klickbar oder Grund (E28) | nein |
| `lab_status.py` | Text der Statuszeile (inkl. Move-Ziel-Label und Knife-Zeile) und der Vorschau-Zeile | nein |
| `lab_draw_data.py` | VBO-Daten (Faces/Edges/Vertices/Highlight/Ebenen-Umriss/Re-Symmetrize-Vorschau/Knife-Marker); lab-lokale Triangulierung + Normalen (E10) | nein |
| `lab_render.py` | Shader + Vertex-Lists, Draw-Reihenfolge | ja |
| `lab_window.py` | pyglet-Fenster: Events übersetzen (inkl. `on_mouse_motion` → Hover), zeichnen, Statuszeile | ja |

Zustand ausschließlich über `mirai.application.Application` (`scene`, `scene.selection`,
`camera`, `bindings`, `tool_manager`, `history`) plus der reinen Hover-Anzeige im Dispatcher
(`hover_vertex`, berührt `scene.selection` nicht — E8) und dem Plan einer offenen
Re-Symmetrize-Vorschau (`resym_plan`) und der laufenden Knife-Session (`knife`) samt ihrem
Hover-Dry-Run (`knife_hover`). Move läuft über `app.tool_manager`
(Pattern A: `activate` → `begin_current_interaction` → `update`* → `commit`/`cancel` →
`deactivate`). Kamera ist die Production-`OrbitCamera` direkt. Kein `Viewport`, kein
`PygletStore`; bei Änderungen werden die Vertex-Lists komplett neu gebaut.

### Tests

*Verdikt (Stand 2026-10-03): Referenz: Tests des alten Labs. Heute: Abschnitt „Tests" oben; was gelöscht wurde: Plan, A2-Tabelle.*

```
python -m pytest experiments/symmetry_lab/tests
```

Headless: GL-freie Module werden direkt getestet. Tests, die `pyglet.window` brauchen
(Import-Grenze, Input-Pfad mit echten pyglet-Konstanten), setzen auf Linux ohne Display
`pyglet.options["headless"] = True` — Details und die Abweichung von Slice 1 in
`tests/_pyglet_headless.py`. Symmetrie-Zyklus, Move und Re-Symmetrize laufen headless über den
Dispatcher (`tests/test_lab_symmetry.py`, `tests/test_lab_move.py`,
`tests/test_lab_resymmetrize.py`); die topologische Paarung ist in `tests/test_lab_topology.py`
charakterisiert, der gespiegelte Knife (Befunde P1–P3 und Engine) in `tests/test_lab_knife.py`,
der Knife im Fenster (Dispatcher, Picking, Vorschau vs. Klick, Marker-Daten, Statuszeile) in
`tests/test_lab_knife_window.py`.

### Beobachtungen aus Slice 2 (nicht gelöst, zur Einordnung)

*Verdikt (Stand 2026-10-03): Referenz: Beobachtungen am alten Renderer (Slice 2); mit dem Renderer erledigt. Picking ist auf dem App-Pfad verdeckungsabhängig (B8), Shift+LMB wählt dort hinzu (B2).*

- **Verdeckte Edges bei `subd_cube`:** Ein Teil der Edges wird von den Faces verdeckt. Ursache:
  stark nicht-planare Quads (Fan-Triangulierung) gegen den Depth-Test. Das Playground zeigt mit
  Wireframe-Overlay exakt dasselbe Bild — übernommenes Verhalten, kein Lab-Fehler. Bei
  `head_basemesh`/`man_with_shoes_basemesh` nicht auffällig.
- **Picking und Vertex-Punkte sind verdeckungsfrei** (wie Playground/`pick_nearest_vertex`):
  Rückseiten-Vertices sind sichtbar und anklickbar.
- **Shift+LMB-Konflikt:** In `artist_input_truth.json` ist Shift+LMB sowohl Pan als auch
  `selection.add`. Das Lab folgt der Playground-Praxis (Pan); die Auflösung ist eine
  Artist-Entscheidung.
- **Lab-Kontext nicht per `keymap.json` konfigurierbar:** `BindingSet.from_dict` akzeptiert nur
  die Kontexte `global`/`topology` (`_VALID_CONTEXTS` in `mirai.interaction.input`). Für dieses
  Slice egal; relevant, falls Lab-Bindings später extern überschreibbar sein sollen.
