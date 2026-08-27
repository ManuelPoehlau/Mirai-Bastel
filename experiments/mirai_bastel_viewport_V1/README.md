# Mirai-Bastel Viewport V1 - Praxistest

Kein neuer Produktions-Architekturbaustein. Ziel ist, den gefrorenen Core V1
praktisch zu benutzen und daraus Erkenntnisse für spätere Produktionssysteme
zu gewinnen.

Der ursprüngliche Viewport-Test prüft weiterhin die Pipeline

```text
Scene -> Mesh -> Selection -> Operation -> Commit -> History -> Undo/Redo
```

Zusätzlich enthält der Experimentbereich jetzt einen **Topology Lab** auf
Basis derselben Viewport-/Picking-/Selection-Infrastruktur.

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
- Multi-Collapse ist bewusst noch keine endgültige Modeling-Semantik

**Connect Vertices**

- Vertex Mode
- mindestens zwei Vertices auswählen
- **C** drücken
- bei mehreren Vertices wird experimentell eine deterministische Kette in
  ID-Reihenfolge aufgebaut; bereits vorhandene Verbindungen werden übersprungen
- jede Verbindung nutzt die vorhandene Core-Primitive `connect_vertices()`
- die erzeugten Edges werden ausgewählt

**Connect Edges**

- Edge Mode
- mindestens zwei Edges auswählen
- **Shift+C** drücken
- jede ausgewählte Edge wird zunächst am Mittelpunkt gesplittet
- die neuen Mittelpunkte werden anschließend experimentell als Kette verbunden
- die erzeugten Verbindungs-Edges werden ausgewählt

Die Multi-Selection-Verhalten sind **bewusst experimentell**. Insbesondere
sind Reihenfolge, Gruppierung, zusammenhängende/nicht zusammenhängende
Auswahl und das Verhalten bei teilweise ungültig werdenden Elementen noch
Gegenstand des Praxistests.

Die Tool-Schicht liegt bewusst unter `experiments/` und verändert `src/core`
nicht. Sie ist eine interaktive Übersetzung der bereits vorhandenen Core-
Primitives, keine neue Produktions-API.

Die Topologie-Mutationen werden im Experiment derzeit über die öffentliche
`export_state()`/`load_state()`-API als Snapshot-History-Einträge rückgängig
machbar gehalten. Diese History-Anbindung ist momentan **bekannt nicht mit
dem aktuellen eingefrorenen Core synchronisiert**, da `load_state()` im
aktuellen Core V1 noch nicht vorhanden ist. Undo/Redo für Topologie ist daher
vorerst aus dem praktischen Test auszunehmen und wird separat geklärt.

## Multi-Selection Testmatrix

Die nächste praktische Teststufe umfasst bewusst mehrere Auswahlgrößen und
Topologie-Situationen:

```text
Collapse
  ├─ 2 Vertices
  ├─ 3+ Vertices
  ├─ 2 Edges
  ├─ 3+ Edges
  └─ zusammenhängend / nicht zusammenhängend

Connect Vertices
  ├─ 2 Vertices
  ├─ 3 Vertices
  ├─ 4+ Vertices
  └─ gültige / ungültige Kombinationen

Connect Edges
  ├─ 2 Edges
  ├─ 3 Edges
  ├─ 4+ Edges
  └─ zusammenhängend / nicht zusammenhängend
```

Nicht nur technische Fehler, sondern auch die **Qualität des Ergebnisses**
und die daraus entstehenden Modeling-/Workflow-Fragen sollen dokumentiert
werden.

## Was als Nächstes folgt

```text
Phase 1 Einzeloperationen       → praktisch grün
        ↓
Phase 1 Multi-Selection         → aktueller Test
        ↓
Grenzfälle / ungültige Fälle
        ↓
Loop Insert
Loop Remove / Dissolve
        ↓
Extrude
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
- Loop-/Ring-Selection
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
  topology_tools.py  - experimentelle Phase-1-Topologie-Werkzeuge
  app.py              - ursprünglicher V1-Viewport
  topology_app.py    - Topology-Lab auf Basis von app.py
run.py                - ursprünglicher V1-Einstiegspunkt
run_topology.py       - Topology-Lab-Einstiegspunkt
```
