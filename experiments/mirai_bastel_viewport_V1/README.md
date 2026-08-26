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

- **Linksklick** auf einen Vertex: auswählen
- **Links ziehen** (auf einem gerade selektierten Vertex begonnen): verschieben
- **Rechts ziehen**: Kamera orbiten
- **Mausrad**: zoomen
- **Strg+Z / Strg+Y**: Undo / Redo
- **Esc**: laufende Verschiebung abbrechen (`cancel()`)

Die V1-Kamera orbitiert und zoomt immer um das Scene-Zentrum. Die vertikale
Orbit-Richtung folgt der im Praxistest bevorzugten Modeler-Konvention:
Ziehen nach unten dreht den Würfel nach unten. Objekt-/Selection-Fokus ist
bewusst noch nicht Bestandteil dieses Milestones.

## Bewusst außerhalb des Scopes dieses Milestones

- Rotate/Scale (Core hat V1 nur `MoveOperation`)
- Edge-/Face-Selection-Interaktion (nur Vertex-Picking)
- Soft Selection, Snapping, Ortho-Ansicht
- Achsen-Constraints / Transform-Gizmo (Verschiebung ist frei entlang der
  Bildebene der Kamera, siehe `camera.screen_delta_to_world`)
- interaktive Topologie-Edits (split/collapse/connect bleiben testgetrieben
  im Core-Projekt, keine UI dafür)
- Orbit around Object/Selection und Zoom to Object/Selection

## Was tatsächlich geprüft wurde

### 1. Automatisierte Logik-Tests

`tests/test_camera_picking.py` enthält reine Mathe-/Logik-Tests für Kamera,
Ray-Casting und Vertex-Picking. Sie laufen unabhängig von pyglet und GPU;
die vorhandenen Checks wurden erfolgreich ausgeführt.

### 2. Headless-Integrationstest unter Xvfb

Unter einem virtuellen Xvfb-Framebuffer wurde das vollständige
`ModelerWindow` instanziiert. Die Event-Handler wurden direkt durchgespielt:
Vertex anhand seiner projizierten Bildschirmposition gepickt, fünfmal
gedraggt, committed, Strg+Z/Strg+Y, Orbit und Zoom ausgeführt sowie mehrere
`on_draw()`-Aufrufe mit OpenGL-Shader durchgeführt. Positions- und
History-Zustände wurden per Assertions geprüft.

Dieser Test verifiziert den Integrationspfad unter einer virtuellen
Grafikumgebung. Er beweist jedoch **nicht**, dass der Renderpfad auf einer
konkreten echten GPU korrekt sichtbar ist oder dass sich die Interaktion mit
einer echten Maus angenehm anfühlt.

### 3. Echter Hardware-/Praxistest

Der erste Lauf auf echter Hardware wurde anschließend praktisch getestet.
Dabei wurde zunächst ein schwarzes Fenster festgestellt, obwohl der
Headless-Test erfolgreich war. Ursache war eine fehlende explizite Bindung
des eigenen `ShaderProgram` vor dem Setzen der Uniforms und dem Zeichnen.
Das wurde in `app.py` korrigiert; danach war der Würfel sichtbar.

Anschließend wurden auf echter Hardware erfolgreich geprüft:

- sichtbare Würfel-Darstellung
- Vertex-Picking
- Vertex-Move per Drag
- Kamera-Orbit
- Zoom
- Undo / Redo
- tatsächliches Bediengefühl der Mausinteraktion

Der verwendete Praxistest lief mit:

- pyglet 2.1.16
- OpenGL 3.3
- NVIDIA GeForce 9800 GTX/9800 GTX+

### Ergebnis

Der Core kann über den minimalen Viewport interaktiv benutzt werden. Die
Pipeline `Scene -> Mesh -> Selection -> Operation -> Commit -> History ->
Undo/Redo` funktioniert im praktischen Test. Die grundlegende V1-
Viewport-Navigation ist für diesen Milestone ausreichend.

Nicht geprüft bzw. bewusst nicht Teil dieses Milestones sind unter anderem
andere Hardware-/Treiberkombinationen, langfristige Performance und eine
abschließende Bewertung eines späteren vollständigen Navigationssystems.

## Bekannte bzw. bewusste V1-Einschränkungen

- Die Screen-Space-Pick-Toleranz (`max_pixel_distance=14.0` in
  `picking.py`) ist eine V1-Schätzung und kann je nach Fenstergröße/DPI
  später angepasst werden.
- Freie Verschiebung entlang der Kamera-Bildebene (kein Gizmo) kann sich bei
  starker Kamera-Neigung ungewohnt anfühlen - das ist eine bewusste V1-
  Vereinfachung.
- Der vertikale Orbit ist aktuell auf ±85° begrenzt. Ein späterer freier
  Kugelorbit kann bei der grundsätzlichen Navigationsüberarbeitung erneut
  bewertet werden.
- pyglet-Fenster-/GL-Verhalten kann je nach Grafiktreiber variieren.

## Struktur

```text
viewport/
  vecmath.py     - reine Vec3-Tupel-Hilfsfunktionen, keine Abhängigkeiten
  camera.py      - OrbitCamera inkl. Picking-Ray/Projektion (kein pyglet)
  picking.py     - nächster Vertex zu einer Bildschirmposition
  demo_scene.py  - baut eine Würfel-Scene über die Core-Mesh-API
  app.py         - pyglet-Fenster: Rendering + Eingabe -> Core-Aufrufe
tests/
  test_camera_picking.py - pure Tests für camera.py/picking.py
run.py           - Einstiegspunkt
```
