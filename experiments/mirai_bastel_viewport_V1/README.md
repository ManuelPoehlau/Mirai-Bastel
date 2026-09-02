# Mirai-Bastel Viewport V1 - Praxistest

Kein neuer Produktions-Architekturbaustein. Ziel ist, den gefrorenen Core V1
praktisch zu benutzen und daraus Erkenntnisse für spätere Produktionssysteme
zu gewinnen.

Der ursprüngliche Viewport-Test prüft weiterhin die Pipeline

```text
Scene -> Mesh -> Selection -> Operation -> Commit -> History -> Undo/Redo
```

Zusätzlich enthält der Experimentbereich einen **Topology Lab** auf Basis
derselben Viewport-/Picking-/Selection-Infrastruktur.

## Setup

```bash
cd experiments/mirai_bastel_viewport_V1
pip install -r requirements.txt
```

### Normaler V1-Viewport

```bash
python run.py
```

Startet die ursprüngliche Würfel-Testszene.

### Topology Lab

```bash
python run_topology.py
```

Startet eine kontrollierte 3x3-Quad-Grid-Testszene und die experimentellen
Topologie-Werkzeuge.

### All-Tools Playground (experimentell)

```bash
python run_all_tools.py
```

Startet eine Würfel-Testszene, in der Selection, Topology-Werkzeuge und die
modalen Transform-Tools zusammen in **einem** Fenster praktisch ausprobiert
werden können (`viewport/all_tools_app.py`). Reines Test-Tool: keine
Production-UX, kein Gizmo, keine Toolbar.

Die Belegung basiert vollständig auf `build_default_bindings()`; ergänzt
werden im Kontext `topology` ausschließlich **freie** Tasten — bestehende
Hotkeys (S → Split, R → Ring, M → Move, V/E/F, …) bleiben unverändert wirksam:

| Taste | Funktion |
| --- | --- |
| `M` | Move-Tool (modal, WP-02) |
| `Shift+R` | Rotate-Tool (modal, WP-03) |
| `Shift+S` | Scale-Tool (modal, WP-03) |
| `X` / `Y` / `Z` | Achse für die nächste Transform-Interaktion (Toggle: aktive Taste nochmals drücken hebt auf) |
| `S` / `R` | Split Edge / Edge Ring (unverändert) |
| `K` / `C` / `L` | Collapse / Connect / Edge Loop (unverändert) |
| `V/E/F`, `1/2/3` | Selection Modes (unverändert) |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo (unverändert) |
| `Alt+A` / `O` / `W` / `Esc` | Deselect / Display / Wireframe / Cancel (unverändert) |

Achsen-Semantik: Die Transform-Tools besitzen die Achsen-Auswahl bereits als
`begin(axis=…/axes=…)`-Parameter (WP-03); der Playground macht diesen
vorhandenen Parameter über X/Y/Z wählbar, **bevor** eine Interaktion beginnt
(die Achse wird im begin()-Moment fixiert — keine Umschaltung während eines
laufenden Drags, wie bisher). Scale ohne Achse ist uniform (V1_SPEC).
Move ohne Achse bleibt frei entlang der Kamera-Bildebene; mit Achse projiziert
der experimentelle Adapter `AxisConstrainedMoveTool` (all_tools_app.py) das
vorhandene Kamera-Delta auf die Weltachse — die MoveOperation ist unverändert.

## Allgemeine Steuerung

### Selection Modes

- **V / 1**: Vertex Mode
- **E / 2**: Edge Mode
- **F / 3**: Face Mode

Klick auf ein Element toggelt dessen Auswahl. Klick ins Leere löscht die
Auswahl. Hover zeigt das Element, das ein Klick auswählen würde.

### Viewport

- **Linksklick** auf Element: auswählen
- **Links ziehen**: vorhandene Move-Interaktion
- **Rechts ziehen** (Drag): Kamera orbiten
- **Mittelte Taste** (Drag): Pan/Track (neu seit WP-01A)
- **Mausrad**: zoomen
- **Strg+Z / Strg+Y**: Undo / Redo
- **Esc**: laufende Vertex-Verschiebung abbrechen; ein aktiviertes
  Move-Tool deaktivieren (siehe unten)
- **Alt+A**: komplette Auswahl aufheben (zusätzlich zum „Klick ins Leere")
- **O**: Display-Modus wechseln (Shaded → Flat Shaded → Wireframe)
- **W**: Wireframe Overlay AN/AUS

### Modal Move-Tool (WP-02)

**M** aktiviert das modale Move-Tool (Binding austauschbar, z. B. `G` per
`keymap.json`; Command und Tool bleiben davon unberührt):

```text
M
 ↓
Command.Move
 ↓
MoveTool wird aktiviert (Active-Tool über ToolManager)
 ↓
LMB + Drag auf der aktuellen Selection
 ↓
MoveTool.begin / update* (Live-Vorschau)
 ↓
Mouse Release  → MoveTool.commit (genau ein History-Eintrag)
```

- Solange ein Modeling-Tool aktiv ist, **toggelt LMB die Selection nicht**:
  LMB + Drag benutzt die aktuelle Selection (Vertex-, Edge- oder
  Face-Selection wird über `resolve_selection_vertices()` auf betroffene
  Vertices aufgelöst). Klick auf ein bereits selektiertes Element deselektiert
  es deshalb nicht mehr, sondern beginnt die Move-Interaktion.
- **Esc** bricht eine laufende Interaktion ab: Geometrie exakt im Vorzustand,
  kein History-Eintrag, kein stale Tool-State. Ein weiteres Esc deaktiviert
  das Tool zurück in den Tweak-Modus.
- **Commit** passiert beim Loslassen der Maustaste: genau eine Operation bzw.
  genau ein History-Eintrag pro Interaktion (auch mehrere Drags hintereinander,
  solange das Tool aktiv ist); Undo/Redo greifen an dieser Grenze.
- **Navigation bleibt intakt**: RMB-Orbit, MMB-Pan und Mausrad-Zoom
  funktionieren weiter; RMB/MMB canceln eine laufende Interaktion sauber vor
  der Navigation (Geometrie zurück, keine History), das Tool bleibt dabei
  modal aktiv.
- **Ohne `M`** bleibt das gewohnte Tweak-Verhalten unverändert: LMB-Klick
  toggelt die Auswahl, Drag auf der Selection verschiebt, Release commitet,
  danach ist das Tool automatisch beendet.
- Undo/Redo, Selection-Mode-Wechsel (V/E/F) und Alt+A beenden ein aktives
  Tool sauber, bevor sie wirken.

### Modal Transform-Tools (WP-03)

**R** aktiviert das modale Rotate-Tool, **S** das modale Scale-Tool (Bindings
austauschbar, Commands und Tools bleiben davon unberührt). Beide folgen
exakt dem WP-02-Werkzeugvertrag und nutzen die WP-03-Transform-Foundation
(`RotateOperation`/`ScaleOperation` im Experiment-Core-Fork):

```text
R / S
  ↓
Command.Rotate / Command.Scale
  ↓
RotateTool / ScaleTool (Active-Tool über ToolManager)
  ↓
LMB + Drag auf der aktuellen Selection (Live-Vorschau)
  ↓
Mouse Release → Commit (genau ein History-Eintrag)
Esc → Cancel (exakter Vorzustand, kein History-Eintrag)
```

- **Pivot**: Selection Center (Zentroid der betroffenen Vertices), fix
  während der Interaktion.
- **Rotate**: horizontales Ziehen rotiert um die Blickachse der Kamera im
  Begin-Moment (Screen-Plane-Rotation). Der Zielwinkel wird aus der
  kumulierten Pixel-Distanz abgeleitet — das Ergebnis ist unabhängig vom
  Event-Chunking des Fensters.
- **Scale**: Ziehen (rechts/oben vergrößert, links/unten verkleinert)
  skaliert uniform um den Pivot; der Zielfaktor wird auf > 0 begrenzt
  (keine Spiegelung durch die Geste).
- Mehrere Drags hintereinander erzeugen pro Release genau einen
  History-Eintrag; Undo/Redo greifen an dieser Grenze.
- Die Topology-Lab-Bindings S (SplitEdge) und R (EdgeRing) behalten im
  Kontext `topology` Vorrang vor diesen globalen Bindungen.
- Achsen-Auswahl (Weltachse für Rotation, Achsenbeschränkung für Scale) ist
  auf Tool-Ebene über `begin(axis=.../axes=...)` unterstützt; eine
  interaktive Umschaltung per Hotkey/Gizmo ist bewusst noch nicht gebaut.

Die V1-Kamera orbitiert und zoomt weiterhin um das Scene-Zentrum. Die
vertikale Orbit-Richtung folgt der im Praxistest bevorzugten
Modeler-Konvention: Ziehen nach unten dreht das Modell nach unten. Pan
nutzt dieselbe „Grab"-Konvention: Der sichtbare Inhalt folgt der
Mausbewegung (Maus nach oben → Objekt wandert nach oben).

### Display Modes (seit WP-01A)

Der Viewport kennt drei Darstellungs-Modi (`display_state.py`) plus
Wireframe Overlay:

```text
Shaded              Surface mit geglätteter (gemittelter) Normalen-Beleuchtung
Flat Shaded         Surface mit Face-Normalen (harte Kanten)  ← Topology-Check bevorzugt
Wireframe           nur Kanten
Wireframe Overlay   Kanten zusätzlich über der Surface (Shaded/Flat Shaded)
```

Nutzbare Kombinationen: Shaded, Shaded + Wire, Flat Shaded, Flat Shaded +
Wire, Wireframe. **Flat Shaded + Wire** ist der wichtigste praktische
Topology-Prüfmodus (ziehen nach Flat Shaded über `O`, dann `W`).

### Input-Bindings (seit WP-01A)

Tasten- und Maus-Bindings liegen nicht mehr direkt im Window-Code, sondern
in einer Mapping-Schicht (`input_binding.py` + `default_bindings.py`,
`commands.py` enthält die benannten Commands). Aufgelöst wird:

```text
Input (Key/Maus/Wheel + Modifier)
  ↓
Context (global | topology)
  ↓
Binding (Default oder User-Overlay)
  ↓
Command
  ↓
Window-/Tool-Dispatch
```

Bindings sind über eine optionale `keymap.json` im Experiment-Ordner
überschreibbar (User-Overlay; Defaults gelten, solange nicht überschrieben):

```json
{
  "bindings": [
    {
      "context": "global",
      "input": {"kind": "key", "value": "g", "modifiers": []},
      "command": "CycleDisplayMode"
    }
  ]
}
```

Command- und Tool-Code bleiben dadurch frei von konkreten Tasten/Maustasten.
Die Topology-Lab-Commands (S/K/C/L/R) gelten nur im Context `topology`;
globale Bindings (V/E/F, Undo/Redo, Alt+A, O/W, Maus) greifen dort als
Fallback weiter.

## Topology Lab - Phase 1

Die Testszene ist bewusst einfach: ein flaches Quad-Grid mit inneren und
Rand-Edges. Der Cube aus dem ursprünglichen Praxistest bleibt unverändert.

### Werkzeuge

**Split Edge**

- Edge Mode
- genau eine Edge auswählen
- **S** drücken
- die Edge wird über die vorhandene Core-Primitive `split_edge()` geteilt
- die beiden neuen Edges werden ausgewählt

**Collapse**

- **Edge Mode + 1 Edge:** **K** kollabiert die Edge; der verbleibende Vertex
  wird ausgewählt und der Mode wechselt zu Vertex
- **Edge Mode + 2+ Edges:** die ausgewählten gültigen Edges werden experimentell
  nacheinander kollabiert
- **Vertex Mode + 2+ Vertices:** eine zusammenhängende Auswahl wird
  experimentell über vorhandene Verbindungs-Edges schrittweise kollabiert
- Multi-Collapse wurde praktisch in beiden Modi bis zu den topologischen
  Grenzfällen getestet und verhält sich erwartungsgemäß.
- Ein weiterer Collapse kann bei zu wenig verbleibender Geometrie zu
  degenerierten/freischwebenden Edges führen; dies ist als spätere
  Gültigkeitsregel dokumentiert und noch nicht Teil von Phase 1.

**Connect Vertices**

- Vertex Mode
- mindestens zwei Vertices auswählen
- **C** drücken
- bei mehreren Vertices wird experimentell eine deterministische Kette in
  ID-Reihenfolge aufgebaut; bereits vorhandene Verbindungen werden übersprungen
- jede Verbindung nutzt die vorhandene Core-Primitive `connect_vertices()`
- die erzeugten Edges werden ausgewählt und der Selection Mode wechselt zu Edge
- Connect zwischen Vertices ohne gemeinsame Face wird korrekt abgelehnt

**Connect Edges**

- Edge Mode
- mindestens zwei Edges auswählen
- **C** drücken (kontextabhängig: `C` verbindet Vertices im Vertex-Mode und
  Edges im Edge-Mode — seit WP-01A; das frühere `Shift+C` ist entfallen)
- die Operation ist topology-aware und läuft in drei getrennten Phasen
  (Analyze/Validate → Plan → Apply/Commit), siehe
  `docs/research/topology/CONNECT_EDGES_SPEC.md`
- Gruppen und Verbindungen entstehen ausschließlich aus Topologie/Geometrie:
  - gegenüberliegende Kanten einer gemeinsamen Quad-Face werden über ihre
    Mittelpunkte verbunden (`connect_vertices`)
  - kantenbenachbarte Ketten (kollineare Edges um einen regulären
    Innen-Vertex) werden über freie Kanten zwischen den Mittelpunkten
    aufeinanderfolgender Edges verbunden (`add_edge`); die durchlaufenen
    Vertices bleiben erhalten
- vollständig atomic: ungültige/inkompatible Auswahlen ändern das Mesh nicht
  (Analyse ist read-only; der Plan wird vor der Mutation auf einem Clone
  validiert; bei Fehlern wird der exakte Vorher-Zustand wiederhergestellt)
- deterministisch: Selection-Reihenfolge und numerische Edge-IDs haben keinen
  Einfluss auf Gruppierung oder Ergebnis
- genau ein History-Snapshot pro Operation (Undo/Redo über Snapshot-Restore)
- Edge-Ring-Auswahlen erzeugen auf geeigneter Quad-Topologie die zugehörige
  Querverbindungs-Struktur als Ring-Interpretation (noch kein Loop Insert -
  das bleibt eine eigene Höher-Level-Operation)
- Scope aktuell: reguläre kompatible Quad-Topologie. Boundary-/Non-Quad-/
  Mixed-Valence-/Non-Manifold-Fälle werden explizit abgelehnt.

### Phase-1-Ergebnis

Die grundlegenden Werkzeuge wurden praktisch untersucht:

```text
Split Edge          → 1 Edge              ✅
Collapse Edge       → 1 Edge              ✅
Connect Vertices    → 2 Vertices          ✅
Connect Edges       → 2 Edges             ✅

Multi-Selection
Collapse Vertices   → 2+ Vertices         ✅
Collapse Edges      → 2+ Edges             ✅
Connect Vertices    → 3+                  ⚠️ experimentell
Connect Edges       → 3+                  ✅ Ketten & Ringe (Quad-Scope, atomar)
```

Ein konkreter Viewport-Bug bei **Connect Vertices mit 3+ Vertices** wurde
behoben: Die erzeugten `EdgeId`s dürfen nicht in der Vertex-Selection landen;
das Ergebnis wird jetzt explizit als Edge-Selection behandelt.

Die folgenden Punkte bleiben bewusst offen und werden in einem eigenen
nächsten Forschungsblock behandelt:

- **Connect-Edges-Semantik für mehrere Edges**
- Verhalten bei zusammenhängenden und disjunkten Edge-Sets
- Verhalten bei Loops und Rings
- Boundary-/Face-Konstellationen
- Ablehnung ungültiger Auswahlen ohne Teilmutation
- Post-Operation Selection / Mode-Verhalten
- Undo/Redo für Topologie über `load_state()` (separates Core-Thema)

## Topology Lab - Phase 2

Edge-Loop- und Edge-Ring-Erkennung sowie die interaktive Auswahl im Viewport
wurden als Experiment umgesetzt und praktisch verifiziert.

### Erkennung

- `viewport/loop_ring.py` — `edge_loop()` / `edge_ring()`, ausschließlich
  über die bestehende Topologie-Query-API (`face_vertices`, `face_edges`,
  `edge_faces`, `edge_vertices`, `vertex_edges`).
- Bewusst konservativ: Edge Ring läuft nur durch Quad-Faces, Edge Loop nur
  durch Vertices mit Valenz 4 und eindeutigem gegenüberliegendem Kandidaten.
- Boundary-Loop-Fortsetzung ist bewusst nicht implementiert.
- Beide erkennen geschlossene Loops/Ringe explizit (`closed`-Flag), ohne die
  Startkante doppelt aufzunehmen.
- Reine Logik-Tests in `tests/test_loop_ring.py` decken Quad-Grid,
  konservative Abbrüche und geschlossene Loop-/Ring-Fälle ab.

### Interaktive Selection

- **Edge Mode + genau 1 Edge + `L`** → Edge Loop auswählen
- **Edge Mode + genau 1 Edge + `R`** → Edge Ring auswählen
- die bisherige Selection wird durch das erkannte Edge-Set ersetzt
- das Ergebnis wird unmittelbar im Viewport visualisiert
- geschlossene Traversierungen werden in der Caption angezeigt
- die Auswahl selbst verändert keine Mesh-Topologie und benötigt keine
  Änderung am eingefrorenen Core V1

Die praktische Prüfung hat bestätigt, dass die komplette Kette funktioniert:

```text
Edge Picking
    ↓
Loop / Ring Detection
    ↓
Edge Set
    ↓
Viewport Selection
    ↓
visuelles Ergebnis
```

### Bewusst noch offen

- gemischte Quad-/Non-Quad-Topologien über die vorhandene Grenzfallabdeckung
  hinaus
- Boundary-Loop-Fortsetzung
- endgültige Modifier-/Interaktionssemantik
- weiterführende Loop-/Ring-Operationen wie Insert, Cut oder Slide

## Was als Nächstes folgt

```text
Topology Phase 1 → untersucht
        ↓
Topology Phase 2 → Loop/Ring Detection + interaktive Selection
                    praktisch verifiziert
        ↓
Topology Phase 3 → Connect Edges
                    Semantik + Multi-Selection gründlich untersuchen
        ↓
Topology Phase 4 → Loop Insert / Loop Cut
                    Loop Remove / Dissolve
        ↓
Topology Phase 5 → Extrude
        ↓
weitere Topologieoperationen
```

Die langfristige Forschungsrichtung ist in
`experiments/topology/README.md` und
`experiments/topology/TOPOLOGY_EXPERIMENT_PLAN.md` dokumentiert.

Besonders wichtig ist später die Kombination von Topologieänderungen mit
Skinning und Morphing. Animation bleibt zunächst bewusst außen vor.

## Darstellung

Der Test-Viewport verwendet eine minimale Solid-Darstellung der Faces mit
sichtbarem Wireframe und sichtbaren Vertices darüber. Highlight-Farben sind
weiterhin vorläufig und keine endgültige UI-Entscheidung.

## Bewusst außerhalb des aktuellen Scopes

- Object Mode
- endgültiges Modeling-UI
- Universal / All-in-One Mode
- endgültige Selection-Farben / Visual Design
- Soft Selection, Snapping, Ortho-Ansicht
- Transform-Gizmo, interaktive Constraint-Hotkeys (X/Y/Z) während einer
  laufenden Transform-Interaktion (Achsen-Auswahl existiert nur als
  Tool-/Foundation-Parameter, siehe WP-03)
- Loop Insert / Loop Remove / Dissolve
- Extrude
- Produktionscode unter `src/` für Viewport/Modeling

## Struktur

```text
viewport/
  vecmath.py          - reine Vec3-Tupel-Hilfsfunktionen
  camera.py           - OrbitCamera inkl. Picking-Ray/Projektion, Orbit/Zoom/Pan
  picking.py          - Vertex-, Edge- und Face-Picking
  demo_scene.py       - ursprüngliche Würfel-Testszene
  topology_scene.py   - kontrollierte Topology-Testszene
  topology_tools.py  - experimentelle Phase-1- und Selection-Werkzeuge
  loop_ring.py         - Phase-2 Edge-Loop-/Edge-Ring-Erkennung (reine Query)
  commands.py          - benannte User-Commands (Input-unabhängig)
  input_binding.py     - Input→Command-Mapping (pyglet-frei, konfigurierbar)
  default_bindings.py  - Default-Key/Maus-Belegung + keymap.json-Overlay
  display_state.py     - Display-State: Shaded / Flat Shaded / Wireframe + Overlay
  move_tool.py         - MoveTool + resolve_selection_vertices + Tool-Routing (WP-02)
  transform_tool.py    - TransformTool-Basis + RotateTool/ScaleTool + selection_pivot (WP-03)
  tool.py              - Tool-Lifecycle IDLE/ACTIVE/INTERACTING + ToolManager (WP-02)
  app.py              - ursprünglicher V1-Viewport (Display-Modi, Mapping-Dispatch)
  topology_app.py     - Topology-Lab auf Basis von app.py
run.py                - ursprünglicher V1-Einstiegspunkt
run_topology.py       - Topology-Lab-Einstiegspunkt
keymap.json            - optionales User-Overlay für Bindings (wird bei Existenz geladen)
tests/
  test_constraints.py   - Achsen-/Ebenen-Constraints
  test_camera_picking.py - Kamera-/Picking-Logik inkl. Pan
  test_loop_ring.py      - Edge-Loop-/Edge-Ring-Erkennung (Phase 2)
  test_display_state.py  - Display-State und gültige Übergänge (WP-01A)
  test_input_binding.py  - Input-Mapping, Context, keymap.json (WP-01A)
  test_move_tool.py      - MoveTool × MoveOperation (WP-02)
  test_tool_lifecycle.py - Tool-Lifecycle IDLE/ACTIVE/INTERACTING (WP-02)
  test_tool_routing.py   - Command → Tool-Routing (WP-02/WP-03)
  test_tool_integration.py - Window-Integration M→MoveTool→LMB/Commit/Cancel
                           (WP-02-Follow-up, headless)
  test_transform_operations.py - RotateOperation/ScaleOperation: Mathematik,
                            Pivot, Commit/Cancel/Undo (WP-03)
  test_transform_tools.py - RotateTool/ScaleTool: Lifecycle, Gesten, Achsen,
                            Chunking-Unabhängigkeit (WP-03)
  test_transform_integration.py - Window-Integration R/S→Tools→Commit/Cancel
                            (WP-03, headless)
  test_all_tools.py     - All-Tools-Playground: Bindings-Priorität, Achsen-
                            Constraints, Topology-Regression (headless)

```
