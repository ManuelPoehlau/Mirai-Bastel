# Work Package: Toolbox-Lücken in Production (2026-10-23)

**An:** Claude Code
**Modell/Effort:** Opus, effort `high` für B1/B2 (Core-Topologie), `medium` für A1/A2/C1/C2
**Status:** A1 und A2 gebaut (2026-10-23, `PROVISIONAL`, Praxistest am Ende von Paket A = jetzt fällig); B1 gebaut (2026-10-23, `PROVISIONAL`, Praxistest B nach B2); C1 … B2 geplant. Reihenfolge und Keys siehe unten; alles Übrige `PROVISIONAL`.
**Modus (M5):** Production, Core-first, **kein Lab** (Blender-bekannte Werkzeuge, AGENTS.md §7a).
Promotion (M3) durch Manu im Chat 2026-10-23: „Werkzeuge, die in Mirai noch in Production müssen“ —
Collapse, Box/Lasso Select Through, Koordinatensystem aus dem Playground, Grow Selection, Loop-Extend,
Next/Previous Loop, Relax/Smooth, Subdivide.
**Grundlage:** [future_ideas/SELECTION.md](future_ideas/SELECTION.md),
[future_ideas/MODELING.md](future_ideas/MODELING.md),
[AD-012](architecture/AD-012-TRANSFORM-SPACE.md), [WP_DELETE_DISSOLVE_PLAN.md](WP_DELETE_DISSOLVE_PLAN.md) (Muster).

## 0. Existenzprüfung (2026-10-23)

| Werkzeug | Stand heute |
|---|---|
| Collapse | Core nur `Mesh.collapse_edge` (`src/core/mesh.py`, journal-fähig, v0 überlebt am Mittelpunkt). `cmd.COLLAPSE` hängt auf `K` im `TOPOLOGY_CONTEXT`, den die App nie auflöst; `dispatch_command` hat keinen Zweig → wirkungslos. Playground: `playground/topology_ops.py::collapse_selected_edge` (alter `MeshStateCommand`-Snapshot), Shift+C. Vertex-/Face-Collapse gibt es nirgends. |
| Select Through | Box/Paint/Lasso existieren (`Application._DragSelect`, `mirai/viewport/box_select.py`, `gpu_picking.py`). Die Verdeckung hängt fest an `display.show_faces` → durch das Mesh wählen geht nur im Wireframe. |
| Koordinatensystem | App: nur World (`mirai/viewport/gizmo.py`, `WORLD_AXES`). `tools/transform.py::_resolve_space` kann `space="normal"` schon, die App reicht es nie durch. Playground: `playground/gizmo.py::gizmo_mode()` (world / normal_full / normal_z_only), Umschalten in `playground/window.py`. |
| Grow/Shrink, Loop-Extend, Next/Prev Loop | Kein Code. Bausteine in `src/mirai/topology/loop_ring.py` (`_loop_step`, `_ring_step`, `edge_loop`, `Traversal`). Shift+L / Shift+R wählen ganze Loops/Ringe. |
| Relax/Smooth | Kein Code (die „smooth“-Treffer sind Shading, SubD und Soft-Kurven). |
| Subdivide | Nur Catmull-Clark-*Vorschau* (`src/mirai/subdivision/`), keine Topologie-Operation; Core hat `split_edge`. |

**„Local Space“:** Der Playground hat **World + Normal**, kein objekt-lokales Space. Object-Local bleibt laut
AD-012 / AD-021 ARCH-01-abhängig und ist hier Nicht-Scope (P-1).

## 1. Entscheidungen

| # | Frage | Antwort |
|---|---|---|
| P-1 | Was ist „Local“? | Normal Space aus dem Playground (pro Auswahl, eine Fläche: voller Tangentenrahmen). Object-Local deferred. `PROVISIONAL` |
| P-2 | Tasten | **Manu 2026-10-23:** Collapse `Shift+C` (das tote `K` im `TOPOLOGY_CONTEXT` entfällt); Loop-Extend `Shift+↑` / `Shift+↓`; Next/Prev Loop `Shift+←` / `Shift+→`; Relax/Smooth zusätzlich „S gedrückt halten + Maus ziehen“; Select Through = nach dem Aufziehen von Box/Lasso **Alt gedrückt halten** (kein Umschalter). `PROVISIONAL`: Grow/Shrink `Ctrl++` / `Ctrl+-` (Haupttastatur und Ziffernblock, Blender „Select More/Less“; `]`/`[` braucht auf deutscher Tastatur AltGr), Orientation-Toggle wie im Playground, Smooth `S` / Relax `Alt+S`. Alle in `GLOBAL`, per `keymap.json` überschreibbar. |
| P-3 | Wofür gilt Select Through? | **Manu 2026-10-23:** Box und Lasso. Paint und der Klick-Pick bleiben sichtbarkeitsbasiert. |
| P-4 | Auswahl nach Collapse | Die Ergebnis-Vertices, Modus wechselt auf Vertex. `PROVISIONAL` (offene Frage aus SELECTION.md „Collapse Edge“) |
| P-5 | Relax/Smooth modal oder One-Shot? | **Beides (Manu 2026-10-23):** Antippen = ein Schritt mit fester Stärke; **S (bzw. Alt+S) gedrückt halten + Maus ziehen** = Stärke live, Loslassen übernimmt, Esc stellt exakt wieder her (Haltetasten-Muster wie G / Loop Slide). |
| P-6 | Subdivide | Erst Simple; „SubD-Stufe anwenden“ ist ein eigener Teil-Slice. `PROVISIONAL` |

## 2. Pakete und Slices

Reihenfolge: **A1 → A2 → B1 → C1 → C2 → B2.** Selektion zuerst: Sie hat das geringste Risiko und liefert
die Auswahl für die späteren Werkzeuge (Loop wählen → Relax). Collapse ist der deutlichste Rückstand, weil
der Command schon existiert, aber tot ist. Subdivide kommt zuletzt: Es ist die größte Core-Fläche, und die
Vorschau deckt den Bedarf vorerst. Jeder Slice ist ein Commit mit Tests und Doku. Pro Paket gibt es einen
gesammelten Praxistest (§3).

### Paket A — Selektion (kein Mesh-Eingriff)

**A1 Topologische Auswahl-Schritte.**
- *Ziel:* Auswahl schrittweise wachsen, schrumpfen und entlang Loops navigieren lassen.
- *Gebaut 2026-10-23* (`src/mirai/topology/selection_steps.py`, `Application._selection_step`,
  Tests `tests/test_selection_steps.py`). Abweichungen von der ersten Planfassung, `PROVISIONAL`:
  - `Shift+↑` verlängert **beide** Enden jedes offenen Loop-Stücks um eine Kante, `Shift+↓` nimmt an
    beiden Enden eine weg (Maya „Grow/Shrink Along Loop“). Ein Ende als „oben“ festzulegen, hätte keine
    sichtbare Regel gehabt.
  - Next/Prev: `Shift+→` wählt die Nachbar-Loop, die auf dem **Bildschirm** rechts liegt; liegen die
    Nachbarn übereinander, gilt oben als rechts.
  - Jedes Stück entscheidet für sich, unter Symmetrie also nicht gespiegelt; das ist ein Punkt für den
    Praxistest.
- *Scope:* neues Modul `src/mirai/topology/selection_steps.py` auf Basis von `loop_ring.py`:
  - **Grow/Shrink** modusabhängig (V über Kanten, E über gemeinsame Vertices, F über Vertex-Nachbarschaft
    wie Blender); Shrink entfernt die Randelemente der Auswahl.
  - **Loop-Extend:** Jede offene Teil-Loop der Kantenauswahl wächst (`Shift+↑`) bzw. schrumpft
    (`Shift+↓`) an beiden Enden um je eine Kante per `_loop_step`. Geschlossene Loops bleiben, wie sie
    sind. An Polen, Nicht-Quads und Rändern ist Schluss (dieselbe Regel wie `edge_loop`).
  - **Next/Prev Loop:** die parallele Loop daneben, per `_ring_step` durch das angrenzende Quad;
    `Shift+→` / `Shift+←` wählen die Seite auf dem Bildschirm. Jedes Stück wandert; ein Stück ohne Quads
    auf dieser Seite bleibt stehen, die Statuszeile sagt es.
    Ergebnis = *ersetzen*, nicht hinzufügen (SELECTION.md: Navigation, nicht Ring-Auswahl).
  - App: Commands in `interaction/commands.py`, Bindings in `bindings.py`, Zweige in `dispatch_command`,
    kein History-Eintrag (eine Auswahländerung wie ein Klick oder Shift+L, `core.selection`).
- *Nicht-Scope:* Soft Selection, ausgeblendete/maskierte Geometrie (gibt es noch nicht).
- *Verträge:* keine Mesh-Mutation. Wie alle Auswahl-Commands nicht gespiegelt; Grow/Shrink und
  Loop-Extend sind rein topologisch, eine symmetrische Auswahl bleibt also symmetrisch.
- *Tests:* `tests/test_selection_steps.py` (Grid, Zylinder, Pol, offener Rand) und App-Verdrahtung analog
  `tests/test_application_loop_tools.py`.

**A2 Select Through (Alt während Box/Lasso).**
- *Gebaut 2026-10-23* (`Application.selection_through`, `_region_occlusion`; Farbe in `src/main.py`).
  Manu 2026-10-23: „bei Box und Lasso nach dem Gummiband-Aufziehen Alt gedrückt halten für Select
  Through“. Das ersetzt den zuerst geplanten Schalter `Alt+Z`.
- *Verhalten:*
  - Ist Alt beim **Loslassen** der Maustaste gehalten, wählt Box bzw. Lasso auch verdeckte Elemente
    (`occlusion = show_faces and not alt`).
  - Solange Alt gehalten ist, sind Gummiband bzw. Umriss blau statt gelb (`PROVISIONAL`).
  - Statuszeile: `Box (through): …` / `Lasso (through): …`.
  - Alt beim *Drücken* bleibt Orbit, dann läuft keine Auswahl.
  - Shift (hinzufügen) lässt sich mit Alt kombinieren.
  - Kein Command, keine Taste, kein Undo-Schritt.
- *Nicht-Scope:* X-Ray-Darstellung (AD-021 verwirft das vorerst), Paint und der Klick-Pick (P-3).
- *Tests:* `tests/test_application_drag_select_tweak.py` (Box: Alt beim Loslassen, Alt vorher
  losgelassen, Paint unberührt), `tests/test_application_lasso.py` (Lasso mit Alt);
  GPU-Pfad mit `tests/test_gl_gpu_picking.py` (xvfb, isoliert).

### Paket B — Topologie-Operationen (Core, Change-Journal)

**B1 Collapse V/E/F.**
- *Gebaut 2026-10-23* (`src/core/operations/collapse.py`, `src/mirai/topology/collapse.py`,
  `Application._collapse_command`, `symmetric_ops.coordinate_collapse`,
  `symmetry_declarations.COLLAPSE_COORDINATORS`; Tests `tests/test_core_collapse.py`,
  `tests/test_application_collapse.py`, Lab `test_app_lab_fail_closed.py`). Präzisierungen, `PROVISIONAL`:
  - Signatur `collapse_elements(mesh, vertex_ids, edge_ids=None)`: die Gruppen entstehen über `edge_ids`
    (E: die gewählten Kanten, F: die Kanten der gewählten Flächen), ohne `edge_ids` über die Kanten zwischen
    zwei gewählten Vertices (V). So bleiben zwei gegenüberliegende Kanten eines Quads zwei Punkte.
  - **Ablehnung statt kaputter Topologie:** Würde eine Fläche einen Vertex doppelt enthalten (eingeschnürt),
    würden zwei Flächen zusammenfallen oder hinge eine Kante an mehr als zwei Flächen, lehnt Collapse vor der
    ersten Mutation ab; die Statuszeile nennt den Grund. Blender lässt das durch; Mirais Invarianten nicht.
  - Unter Symmetrie: Auswahl plus Spiegelbild in einem Schritt; berührt eine Gruppe ihr Spiegelbild (Seam-
    Vertex, Seam-Kante), wird sie ein Punkt **auf** der Ebene. Die Spiegelpunkte werden exakt gesetzt, nicht
    über Rundung gemittelt. Folgeauswahl nur auf der Seite, auf der gewählt war (wie Split).
  - Im Symmetry Lab ist Collapse deklariert und läuft unter BLOCK.
  - Statuszeile `Collapse: N point(s)`; Vertices ohne verbindende Kante: `Collapse: nothing to do …`.
- *Ziel:* Die ausgewählten Elemente fallen in einen Punkt pro zusammenhängender Gruppe.
- *Scope:*
  - Core-Operation `collapse_elements(mesh, vertex_ids) -> list[VertexId]` in `src/core/operations/`.
    Sie bildet zusammenhängende Gruppen der Auswahl (über ausgewählte Kanten) und kollabiert jede auf ihren
    Schwerpunkt, als Kette von `Mesh.collapse_edge` plus abschließender Positionssetzung. Der vorhandene,
    getestete Primitive bleibt so die Grundlage.
  - E- und F-Auswahl werden auf ihre Vertices abgebildet. Bei einer V-Auswahl ohne verbindende Kanten
    entsteht ein Punkt pro Vertex, also keine Änderung, wie bei Blender „Merge at Center“, nur pro Gruppe.
  - App: `cmd.COLLAPSE` wird nach `GLOBAL` auf `Shift+C` verlegt, das `K`-Binding fällt weg. Ausführung über
    `_mesh_transaction` wie `_removal_command`, mit Symmetrie-Koordinator in `symmetry_declarations.py`.
    Danach Auswahl nach P-4.
- *Nicht-Scope:* Dissolve Loop / Collapse Ring (eigenes Folgepaket laut Delete/Dissolve-Plan);
  der Snapshot-Pfad des Playgrounds bleibt unberührt.
- *Verträge:* topologie-sicher (`tests/mesh_invariants.py`), ein `MeshDeltaCommand` pro Aktion, Undo exakt.
- *Tests:* Core-Tests für Edge, Face-Gruppe, Quad-Strip, Randkante und Dreiecks-Degeneration; App- und
  Symmetrie-Verdrahtung; Symmetry-Lab-Tests, weil `application.py` berührt wird.

**B2 Subdivide (Topologie).**
- *Ziel:* echtes Unterteilen als Mesh-Operation.
- *Scope Teil 1 (Simple):* Ausgewählte Faces, ohne Auswahl das ganze Mesh: Kanten mittig teilen
  (`split_edge`), Quads in 4, N-Gons per Fan zum Mittelpunkt. Nachbar-Faces mit geteilten Kanten bleiben
  gültige N-Gons, es entstehen keine T-Junctions. Journal über `record_mesh_change`, dazu eine
  Symmetrie-Deklaration.
- *Scope Teil 2 (optional, P-6):* die aktuelle SubD-Stufe aus `subdivision/catmull_clark.py` (`SubdLevel`)
  als Topologie übernehmen („Apply SubD“).
- *Nicht-Scope:* Unsubdivide, Creases.
- *Tests:* Face- und Vertex-Zählung, Invarianten, Undo, Symmetrie.

### Paket C — Transform-Raum und Glätten

**C1 Transform Orientation World/Normal.**
- *Ziel:* Gizmo und W/E/R wahlweise im Normal-Raum, wie im Playground.
- *Scope:*
  - App-Zustand `transform_space` mit Toggle-Command und HUD-Anzeige, durchgereicht an
    `begin_transform(space=…)`; `_resolve_space` existiert schon.
  - Die Rahmen aus `playground/gizmo.py::gizmo_mode` werden nach `src/mirai/viewport/gizmo.py` übernommen
    (Achsen und Ebenen aus dem aufgelösten Rahmen statt `WORLD_AXES`).
  - AD-012 bekommt eine Implementierungsnotiz „Normal in App“.
- *Nicht-Scope:* Object-Local / Gimbal (ARCH-01), Multi-Face-Tangentenrahmen (TRANSFORM.md, deferred).
- *Tests:* Gizmo-Achsen in beiden Modi; ein Transform-Test mit `space="normal"` über die App.

**C2 Relax / Smooth.**
- *Ziel:* zwei getrennte Formwerkzeuge für ausgewählte Vertices (MODELING.md Priorität 1).
- *Scope:*
  - **Smooth** = Laplace (Nachbarmittel × Stärke).
  - **Relax** = dasselbe Delta, auf die Tangentialebene projiziert: Es verteilt die Vertices gleichmäßiger,
    ohne die Form zu verlieren.
  - Randvertices sind fixiert; unter Symmetrie bleiben die Punkte auf der Ebene darauf.
  - Antippen: One-Shot über `_mesh_transaction(moved_of=…)`, mit Iterationen und Stärke als
    Konstanten (P-5).
  - **Haltetaste (Manu 2026-10-23):** `S` (Smooth) / `Alt+S` (Relax) gedrückt halten und die Maus
    ziehen:
    - Ziehen nach rechts erhöht die Stärke, über die Iterationen hinaus fortlaufend; nach links nimmt
      sie wieder ab, bis 0.
    - Die Positionen werden live aus dem Zustand beim Drücken berechnet.
    - Journal: `begin_change` beim ersten Ziehen, `end_change` plus ein `MeshDeltaCommand` beim
      Loslassen, `rollback_change` bei Esc. Antippen ohne Ziehen ist der One-Shot-Schritt.
    - Gleiche Gates wie G (Loop Slide): nicht unter gehaltenem W/E/R/T, nicht in Modus `4`.
  - Rechnung in `src/core/operations/` als reine Funktion auf Positionen.
- *Nicht-Scope:* Volumenerhalt (Forschungsfrage), Pinsel.
- *Tests:* planares Grid (Relax verändert keine Normalenkomponente), Konvergenz, Rand fix, Undo, Symmetrie.

## 3. Praxistest für Manu (je Paket ca. 10–15 Minuten)

- **A:**
  - Grow/Shrink (`Ctrl++` / `Ctrl+-`) in V/E/F auf dem Kopf.
  - Teil-Loop mit `Shift+↑` verlängern und mit `Shift+↓` kürzen (Stopp am Pol prüfen).
  - Mit `Shift+←/→` über Gesicht und Arm wandern.
  - Box und Lasso über den Kopf ziehen, vor dem Loslassen Alt halten (Band wird blau) → auch die Rückseite ist gewählt; ohne Alt nur die Vorderseite.
- **B:**
  - Collapse (`Shift+C`) auf Kante, Kantenzug und Face-Gruppe, jeweils mit Undo; einmal unter Symmetrie
    (auch eine Kante an der Mitte: der Punkt landet auf der Ebene).
  - Folgeauswahl (P-4): Passt es, dass danach die Punkte im Vertex-Modus gewählt sind, oder willst du im
    Kanten-/Flächen-Modus bleiben, um gleich weiter zu collapsen?
  - Vertex-Modus: zwei benachbarte Punkte wählen → einer; zwei nicht verbundene Punkte → nichts passiert.
  - Subdivide auf einer Face-Insel und auf dem ganzen Mesh.
- **C:**
  - Umschalten World/Normal, an Wange und Nase in beiden Räumen bewegen und drehen.
  - Relax und Smooth auf einem Loop-Bereich, mit SubD-Vorschau an: einmal antippen, einmal halten + ziehen.

## 4. Definition of Done (je Slice)

Gezielte Tests grün (AGENTS.md §8a, GL-Tests isoliert mit `xvfb-run -a`), Symmetry-Lab-Tests bei
Änderungen an `application.py`, `docs/` im selben Commit aktualisiert (dieses Dokument: Status-Zeile und
dated Status-Update; ATELIER §3), und am Ende jedes Pakets steht der Praxistest bereit.
