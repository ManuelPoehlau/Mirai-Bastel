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
- **Rechts ziehen**: Kamera orbiten
- **Mausrad**: zoomen
- **Strg+Z / Strg+Y**: Undo / Redo
- **Esc**: laufende Vertex-Verschiebung abbrechen

Die V1-Kamera orbitiert und zoomt weiterhin um das Scene-Zentrum. Die
vertikale Orbit-Richtung folgt der im Praxistest bevorzugten
Modeler-Konvention: Ziehen nach unten dreht das Modell nach unten.

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
- **Shift+C** drücken
- jede ausgewählte Edge wird zunächst am Mittelpunkt gesplittet
- die neuen Mittelpunkte werden anschließend experimentell als Kette verbunden
- die erzeugten Verbindungs-Edges werden ausgewählt
- zwei nicht zusammenhängende Edges werden aktuell nicht sinnvoll „verbunden“,
  sondern führen zu einer experimentellen Split-Semantik; dies bleibt als
  offene Modeling-Semantik bestehen und ist nicht als endgültiges Verhalten
  festgelegt.

### Phase-1-Ergebnis

Die vier Phase-1-Primitives wurden praktisch geprüft:

```text
Split Edge          → 1 Edge              ✅
Collapse Edge       → 1 Edge              ✅
Connect Vertices    → 2 Vertices          ✅
Connect Edges       → 2 Edges              ✅

Multi-Selection
Collapse Vertices   → 2+ Vertices         ✅
Collapse Edges      → 2+ Edges             ✅
Connect Vertices    → 3+                  ⚠️ experimentell, Auswahl-State gefixt
Connect Edges       → 3+                  ⚠️ experimentelle Semantik
```

Ein konkreter Viewport-Bug bei **Connect Vertices mit 3+ Vertices** wurde
behoben: Die erzeugten `EdgeId`s dürfen nicht in der Vertex-Selection landen;
das Ergebnis wird jetzt explizit als Edge-Selection behandelt.

Die folgenden Punkte bleiben bewusst offen und werden später erneut bewertet:

- Multi-Connect-Semantik für mehr als zwei Elemente
- Connect Edges bei nicht zusammenhängenden Edges
- Mindesttopologie für Collapse und Vermeidung degenerierter Ergebnisse
- Post-Operation Selection / Mode-Verhalten
- Undo/Redo für Topologie über `load_state()` (separates Core-Thema)

Damit ist **Topology Phase 1 als Experiment abgeschlossen**. Die nächsten
Topologie-Experimente beginnen mit Loop Insert sowie Loop Remove / Dissolve,
gefolgt von Extrude.

Die Multi-Selection-Verhalten waren bewusst experimentell. Nicht nur
technische Fehler, sondern auch die Qualität des Ergebnisses und die daraus
entstehenden Modeling-/Workflow-Fragen wurden beobachtet und dokumentiert.

Die Tool-Schicht liegt bewusst unter `experiments/` und verändert `src/core`
nicht. Sie ist eine interaktive Übersetzung der bereits vorhandenen Core-
Primitives, keine neue Produktions-API.

Die Topologie-Mutationen werden im Experiment derzeit über die öffentliche
`export_state()`/`load_state()`-API als Snapshot-History-Einträge rückgängig
machbar gehalten. Diese History-Anbindung ist momentan **bekannt nicht mit
dem aktuellen eingefrorenen Core synchronisiert**, da `load_state()` im
aktuellen Core V1 noch nicht vorhanden ist. Undo/Redo für Topologie ist daher
vorerst aus dem praktischen Test auszunehmen und wird separat geklärt.

## Topology Lab - Phase 2 (Teilstand)

Reine Erkennung von Edge Loops und Edge Rings, ohne Core-/Mesh-Änderung und
ohne interaktive Anbindung im Viewport:

- `viewport/loop_ring.py` — `edge_loop()` / `edge_ring()`, ausschließlich
  über die bestehende Topologie-Query-API (`face_vertices`, `face_edges`,
  `edge_faces`, `edge_vertices`, `vertex_edges`).
- Bewusst konservativ: Edge Ring läuft nur durch Quad-Faces, Edge Loop nur
  durch Vertices mit Valenz 4 und eindeutigem gegenüberliegendem Kandidaten.
  Boundary-Loop-Fortsetzung ist bewusst nicht implementiert. Beide erkennen
  geschlossene Loops/Ringe explizit (`closed`-Flag) statt die Startkante
  doppelt aufzunehmen.
- Getestet in `tests/test_loop_ring.py` (reine Logik-Tests ohne Fenster/GPU):
  volle Zeile/Spalte im Quad-Grid, konservativer Abbruch an Rand-Valenz und
  an einer Non-Quad-Face, geschlossene Loop-/Ring-Erkennung auf einem
  künstlichen Quad-Rohr.
- **Noch nicht Teil dieses Standes:** interaktive Auswahl im Viewport
  (Klick/Modifier → Loop/Ring-Selection). Details und offene Fragen stehen
  in `experiments/topology/TOPOLOGY_EXPERIMENT_PLAN.md`, Phase 2.

## Was als Nächstes folgt

```text
Topology Phase 1 → abgeschlossen
        ↓
Topology Phase 2 → Erkennung implementiert & getestet,
                    interaktive Selection im Viewport offen
        ↓
Loop Insert
Loop Remove / Dissolve
        ↓
Extrude
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
- interaktive Loop-/Ring-Selection im Viewport (Erkennung selbst ist
  implementiert, siehe "Topology Lab - Phase 2 (Teilstand)")
- Universal / All-in-One Mode
- endgültige Selection-Farben / Visual Design
- Soft Selection, Snapping, Ortho-Ansicht
- Achsen-Constraints / Transform-Gizmo
- Loop Insert / Loop Remove / Dissolve
- Extrude
- Produktionscode unter `src/` für Viewport/Modeling

## Struktur

```text
viewport/
  vecmath.py          - reine Vec3-Tupel-Hilfsfunktionen
  camera.py           - OrbitCamera inkl. Picking-Ray/Projektion
  picking.py          - Vertex-, Edge- und Face-Picking
  demo_scene.py       - ursprüngliche Würfel-Testszene
  topology_scene.py   - kontrollierte Topology-Testszene
  topology_tools.py   - experimentelle Phase-1-Topologie-Werkzeuge
  loop_ring.py         - Phase-2 Edge-Loop-/Edge-Ring-Erkennung (reine Query)
  app.py              - ursprünglicher V1-Viewport
  topology_app.py     - Topology-Lab auf Basis von app.py
run.py                - ursprünglicher V1-Einstiegspunkt
run_topology.py       - Topology-Lab-Einstiegspunkt
tests/
  test_constraints.py   - Achsen-/Ebenen-Constraints
  test_camera_picking.py - Kamera-/Picking-Logik
  test_loop_ring.py      - Edge-Loop-/Edge-Ring-Erkennung (Phase 2)
```
