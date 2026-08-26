# Mirai-Bastel Viewport V1 - Praxistest

Kein neuer Architektur-Baustein. Ziel ist ausschließlich, den bestehenden
Core (`experiments/mirai_bastel_core_V1`) durch eine minimale interaktive
Anwendung praktisch zu benutzen und zu prüfen, ob die Pipeline

```text
Scene -> Mesh -> Selection -> Operation -> Commit -> History -> Undo/Redo
```

sich tatsächlich sinnvoll "anfühlt" - nicht, einen brauchbaren Modeler zu
bauen.

## Setup

```bash
cd experiments/mirai_bastel_viewport_V1
pip install -r requirements.txt
python run.py
```

Reines Python + OpenGL (pyglet), gleicher Prozess wie der Core - keine
Bridge, kein Web-/JS-Stack, kein Build-Step.

## Steuerung

### Selection Modes

- **V / 1**: Vertex Mode
- **E / 2**: Edge Mode
- **F / 3**: Face Mode

In jedem Modus kann zunächst ausschließlich der jeweilige Sub-Object-Typ
selektiert werden. Ein Klick ersetzt die bisherige Auswahl (Single Selection).

Hover zeigt das Element, das ein Klick auswählen würde.

Object Mode ist bewusst noch nicht enthalten.

### Viewport

- **Linksklick** auf Element: auswählen
- **Links ziehen** auf Vertex im Vertex Mode: verschieben
- **Rechts ziehen**: Kamera orbiten
- **Mausrad**: zoomen
- **Strg+Z / Strg+Y**: Undo / Redo
- **Esc**: laufende Vertex-Verschiebung abbrechen

Die V1-Kamera orbitiert und zoomt immer um das Scene-Zentrum. Die vertikale
Orbit-Richtung folgt der im Praxistest bevorzugten Modeler-Konvention:
Ziehen nach unten dreht den Würfel nach unten.

## Darstellung

Der Test-Viewport verwendet eine minimale Solid-Darstellung der Faces mit
sichtbarem Wireframe und sichtbaren Vertices darüber. Das dient ausschließlich
der besseren Visualisierung von Face- und Object-bezogenen Selection-Tests.

Die verwendeten Highlight-Farben sind vorläufig und keine endgültige UI-
Entscheidung.

## Bewusst außerhalb des aktuellen Scopes

- Object Mode
- Multi-Selection / Shift / Ctrl-Auswahl
- Toggle-, Box- und Lasso-Selection
- Loop-/Ring-Selection
- Universal / All-in-One Mode mit automatischer Typ-Erkennung
- endgültige Selection-Farben / Visual Design
- Soft Selection, Snapping, Ortho-Ansicht
- Achsen-Constraints / Transform-Gizmo
- interaktive Topologie-Edits
- Produktionsarchitektur unter `src/`

## Was aktuell automatisiert geprüft wird

`tests/test_camera_picking.py` enthält reine Kamera-/Picking-Checks ohne
Fenster oder GPU. Neben der bestehenden Vertex-Prüfung werden jetzt auch
Edge-Picking und Face-Picking geprüft.

Der vollständige Render-/Input-Pfad in `app.py` muss weiterhin auf echter
Hardware praktisch getestet werden.

## Dokumentation des Selection-Experiments

Siehe `SELECTION_MODES.md` für Scope, bewusst verschobene Fragen und die
geplante weitere Reihenfolge.

## Struktur

```text
viewport/
  vecmath.py     - reine Vec3-Tupel-Hilfsfunktionen, keine Abhängigkeiten
  camera.py      - OrbitCamera inkl. Picking-Ray/Projektion
  picking.py     - Vertex-, Edge- und Face-Picking
  demo_scene.py  - baut eine Würfel-Scene über die Core-Mesh-API
  app.py         - pyglet-Fenster: Rendering + Selection/Input -> Core-Aufrufe
tests/
  test_camera_picking.py - pure Tests für Kamera und Picking
run.py           - Einstiegspunkt
SELECTION_MODES.md - Scope und Ergebnisse des Selection-Mode-Experiments
```
