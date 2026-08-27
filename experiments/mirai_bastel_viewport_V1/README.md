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

Startet eine kontrollierte 3x3-Quad-Grid-Testszene und die erste Gruppe
interaktiver Topologie-Werkzeuge.

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

**Collapse Edge**

- Edge Mode
- genau eine Edge auswählen
- **K** drücken
- die Edge wird über `collapse_edge()` kollabiert

**Connect Vertices**

- Vertex Mode
- genau zwei Vertices einer gemeinsamen Face auswählen
- **C** drücken
- die vorhandene `connect_vertices()`-Primitive wird verwendet

**Connect Edges**

- Edge Mode
- genau zwei Edges einer gemeinsamen Face auswählen
- **Shift+C** drücken
- experimentell werden beide Edges zunächst gesplittet und die beiden neuen
  Mittelpunkte anschließend über `connect_vertices()` verbunden

Die Tool-Schicht liegt bewusst unter `experiments/` und verändert `src/core`
nicht. Sie ist eine interaktive Übersetzung der bereits vorhandenen Core-
Primitives, keine neue Produktions-API.

Die Topologie-Mutationen werden im Experiment über die öffentliche
`export_state()`/`load_state()`-API als Snapshot-History-Einträge rückgängig
machbar gehalten. Das ist bewusst lokal zum Experiment; der gefrorene Core
wird dadurch nicht erweitert.

## Was als Nächstes folgt

Phase 1 soll zunächst praktisch getestet werden:

```text
Split Edge
Collapse Edge
Connect Vertices
Connect Edges
        ↓
Kombinationen + Undo/Redo
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
  topology_tools.py   - experimentelle Phase-1-Topologie-Werkzeuge
  app.py              - ursprünglicher V1-Viewport
  topology_app.py     - Topology-Lab auf Basis von app.py
run.py                - ursprünglicher V1-Einstiegspunkt
run_topology.py       - Topology-Lab-Einstiegspunkt
```
