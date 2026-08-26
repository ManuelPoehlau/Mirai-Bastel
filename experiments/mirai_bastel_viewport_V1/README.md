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
cd experiments/mirai_bastel_viewport_v1
pip install -r requirements.txt
python run.py
```

Reines Python + OpenGL (pyglet), gleicher Prozess wie der Core - keine
Bridge, kein Web-/JS-Stack, kein Build-Step (bewusste Entscheidung, siehe
Chat-Absprache vor diesem Milestone).

## Steuerung

- **Linksklick** auf einen Vertex: auswählen
- **Links ziehen** (auf einem gerade selektierten Vertex begonnen): verschieben
- **Rechts ziehen**: Kamera orbiten
- **Mausrad**: zoomen
- **Strg+Z / Strg+Y**: Undo / Redo
- **Esc**: laufende Verschiebung abbrechen (`cancel()`)

## Bewusst außerhalb des Scopes dieses Milestones

- Rotate/Scale (Core hat V1 nur `MoveOperation`)
- Edge-/Face-Selection-Interaktion (nur Vertex-Picking)
- Soft Selection, Snapping, Ortho-Ansicht
- Achsen-Constraints / Transform-Gizmo (Verschiebung ist frei entlang der
  Bildebene der Kamera, siehe `camera.screen_delta_to_world`)
- interaktive Topologie-Edits (split/collapse/connect bleiben testgetrieben
  im Core-Projekt, keine UI dafür)

## Was tatsächlich geprüft wurde (und was nicht)

Diese Sandbox hat kein Display/keine GPU. Zwei unterschiedlich starke
Verifikationsstufen:

1. **`tests/test_camera_picking.py`** - reine Mathe-/Logik-Tests für Kamera,
   Ray-Casting und Vertex-Picking, komplett unabhängig von pyglet. Laufen
   ohne Fenster/GPU, wurden ausgeführt: alle Checks grün.
   `python -m tests.test_camera_picking`

2. **Headless-Smoke-Test unter Xvfb (virtueller Framebuffer)**: das
   komplette `ModelerWindow` wurde tatsächlich instanziiert und alle
   Event-Handler direkt aufgerufen (Picking per simuliertem Klick auf die
   projizierte Position eines echten Vertex, 5x `on_mouse_drag`, `commit()`,
   `Strg+Z`/`Strg+Y`, Orbit, Zoom, mehrere `on_draw()`-Aufrufe) - alle ohne
   Exception, mit korrekten Positions-/History-Assertions. Das deckt die
   komplette Pipeline inklusive echtem OpenGL-Shader-Rendering ab, **aber
   nicht** das reale Timing/Gefühl einer echten Maus in einem echten
   Fenster (z. B. Drag-Geschwindigkeit, Fenstergrößenänderung, tatsächliche
   Bildwiederholrate).

Was das bedeutet: Der Code ist mit hoher Zuversicht lauffähig, aber der
**erste echte Lauf auf deiner Maschine ist trotzdem der eigentliche Test**
- insbesondere das "fühlt sich das wie Benutzen an?", das sich headless
  nicht beurteilen lässt.

## Bekannte Risiken beim ersten echten Lauf

- Die Screen-Space-Pick-Toleranz (`max_pixel_distance=14.0` in
  `picking.py`) ist eine Schätzung - je nach Fenstergröße/DPI evtl.
  nachjustieren.
- Freie Verschiebung entlang der Kamera-Bildebene (kein Gizmo) kann sich
  bei starker Kamera-Neigung ungewohnt anfühlen - das ist eine bewusste
  V1-Vereinfachung, kein Bug.
- pyglet-Fenster-/GL-Verhalten kann je nach Grafiktreiber leicht variieren;
  bei Problemen zuerst `pyglet.version` und die Treiber-OpenGL-Version
  (mind. 3.3 core) prüfen.

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
