# Mirai-Bastel Viewport V1 — Review / Erkenntnisse

**Status:** Experiment abgeschlossen als Praxistest; verbleibende Punkte sind bewusst weitere Experimente  
**Pfad:** `experiments/mirai_bastel_viewport_V1/`

## 1. Zweck

Der Viewport V1 war ursprünglich ein kleiner Praxistest, um zu prüfen, ob der Core nicht nur testbar ist, sondern sich über eine echte interaktive Anwendung sinnvoll benutzen lässt.

Er bleibt **Experimentcode** und wird nicht unverändert nach `src/` übernommen.

## 2. Aktueller Umfang

Der Experiment-Viewport enthält inzwischen deutlich mehr als der ursprüngliche reine Vertex-Picking-Test:

- pyglet/OpenGL-Fenster
- perspektivische Orbit-Kamera
- Zoom/Dolly um das Scene-Zentrum
- Picking für Vertex, Edge und Face
- Hover-Feedback
- Vertex-/Edge-/Face-Selection-Modes
- Toggle-Multi-Selection ohne Modifier-Taste, bewusst als Wings-artiges Experiment
- Klick ins Leere löscht die Selection
- Face-Solid-Darstellung plus Wireframe und Vertices
- Sub-Object-Move über die bestehende Core-`MoveOperation`
- Edge-/Face-Selection wird für Move auf die betroffenen Vertex-IDs aufgelöst
- Undo/Redo über den bestehenden History-Mechanismus
- experimentelles Constraint-Modul für Weltachsen/-ebenen

Die aktuelle Dokumentation im Experiment enthält dafür insbesondere `SELECTION_MODES.md` und den Checkpoint `SELECTION_MODES_V1_CHECKPOINT.md`.

## 3. Was praktisch bestätigt wurde

Der grundlegende Core→Viewport-Weg funktioniert als echtes interaktives System:

```text
Scene
  ↓
Mesh
  ↓
Selection
  ↓
Operation
  ↓
Commit
  ↓
History
  ↓
Undo / Redo
  ↓
Viewport
```

Der erste echte Hardware-Lauf hat außerdem bestätigt, dass Rendering, Orbit, Zoom, Picking und Move auf der Zielmaschine funktionieren.

Die Kamera orbitiert und zoomt derzeit immer um das Scene-Zentrum. Die bevorzugte vertikale Orbit-Richtung wurde im Experiment festgelegt: Ziehen nach unten dreht den Würfel nach unten.

Die aktuelle Kamera bleibt absichtlich einfach: Perspektive, begrenzter Pitch und kein Ortho-/Snap-/Frame-/Pan-System.

## 4. Selection-Erkenntnisse

Die ursprüngliche Single-Selection-Annahme wurde im praktischen Experiment bewusst weiterentwickelt.

Aktueller Teststand:

```text
Klick A        → [A]
Klick B        → [A, B]
Klick A        → [B]
Klick ins Leere → []
```

Das funktioniert für Vertex, Edge und Face.

Diese Toggle-Selection ist **noch kein endgültiger Produktionsvertrag**. Sie ist ein bewusst einfacher Interaktionstest, der sich jetzt real ausprobieren lässt.

Ebenfalls noch offen:

- Object Mode
- Visible Only vs. Through/X-Ray
- Box/Lasso/Brush
- Loop/Ring
- Selection Expansion/Reduction
- Universal/All-in-One Mode
- endgültige Selection-Visualisierung
- Modifier-Verhalten

## 5. Sub-Object Move

Der Experimentcode verwendet die vorhandene Core-`MoveOperation` und übersetzt Edge-/Face-Selection lediglich in eine betroffene Vertex-Menge.

Das ist für den Praxistest wertvoll, weil es zeigt, dass der Core nicht wissen muss, **wie** ein Benutzer ein Sub-Object ausgewählt hat.

Die Zuordnung lautet:

```text
Vertex → diese Vertices
Edge   → beide End-Vertices
Face   → alle Boundary-Vertices
```

Bei mehreren Edges/Faces wird die Union der Vertex-IDs gebildet.

Damit ist eine wichtige Trennung sichtbar:

```text
Selection / Interaction
          ↓
    betroffene Elemente
          ↓
     Core Operation
```

## 6. Navigation

Die aktuelle Navigation ist bewusst noch nicht Produktionsdesign.

Bereits als zukünftige Themen festgehalten sind unter anderem:

- freies bzw. alternatives Orbit-Verhalten
- Ortho-Ansichten
- View-Snapping, z. B. Shift-Drag zur nächstgelegenen Standardansicht
- Pan/Track
- Frame Selection / Frame Object
- Orbit around Object / Selection
- Zoom to Object / Selection
- weitere Navigationskonventionen

Die aktuelle V1 bleibt bei Orbit und Zoom um das Scene-Zentrum.

## 7. Constraint-Experiment

`viewport/constraints.py` beschreibt bereits Weltachsen und Weltebenen (`X/Y/Z` sowie `XY/YZ/XZ`).

Das ist derzeit nur eine kleine experimentelle Beschreibung der Constraint-Auswahl. Es ist **kein** fertiges Transform-System und noch nicht als Produktions-API zu verstehen.

## 8. Technische Bewertung des Experimentcodes

Der aktuelle `app.py` ist inzwischen ein nützlicher Interaktionsprototyp, aber weiterhin bewusst monolithisch: Rendering, Geometry-Building, Hover/Picking, Selection-State, Input-Routing und Move-Interaktion liegen weitgehend zusammen.

Das ist für ein Experiment akzeptabel und sogar hilfreich, weil Änderungen schnell ausprobiert werden können.

Für `src/` wäre diese Struktur jedoch nicht unverändert geeignet.

Bewährte Kandidaten für eine spätere Überführung sind:

- Kamera-/View-Mathematik
- Picking-Konzepte
- Rendering-Boundary
- Selection-Feedback als sichtbares Ergebnis des Core-Zustands
- Input→Tool→Operation-Grundidee

Nicht automatisch zu übernehmen sind die konkrete Klassen-/Dateistruktur, Demo-Szene, pyglet-Details und die direkte Vermischung von UI-/Input-/Rendering-Logik.

## 9. Produktionsrelevante Erkenntnisse

Das Experiment liefert jetzt echte Hinweise für die spätere Produktionsarchitektur:

1. **Viewport und Core lassen sich sauber trennen.** Der Core muss weder Fenster noch Renderer kennen.
2. **Selection ist eine Interaktionsgrenze.** Der Benutzer arbeitet mit Vertex/Edge/Face, während eine konkrete Operation daraus ihre benötigten Core-Elemente ableiten kann.
3. **Picking gehört nicht in den Core.** Es ist eine räumliche Viewport-Frage.
4. **Hover ist transient.** Es darf nicht mit persistenter Selection verwechselt werden.
5. **Rendering muss aus dem aktuellen Scene-Zustand ableiten können**, statt eigene autoritative Geometriedaten zu besitzen.
6. **Navigation ist ein eigenständiges UX-Thema.** Die aktuellen Konventionen sind testbar, aber noch nicht endgültig.
7. **Experimentcode darf schneller und pragmatischer sein als Produktionscode.** Genau deshalb bleibt dieser Ordner erhalten.

## 10. Noch nicht als Produktionsentscheidung werten

Folgende Punkte sind bewusst nur Erkenntnisse bzw. offene Fragen:

- endgültige Selection-Semantik
- endgültige Navigation
- Tool-/Interaction-State-Modell
- Renderer-Aufteilung
- Viewport-Rendering-Caches
- Event-/Change-System
- Transform-Constraints
- Object Mode
- Soft Selection / Influence

Sie werden erst aus weiteren praktischen Tests in konkrete Produktionsverträge überführt.

## 11. Nächster Schritt

Der nächste Produktionsschritt wird **nicht aus der Dateistruktur dieses Experiments kopiert**.

Stattdessen werden die bewährten Verhaltensanforderungen extrahiert und mit `SOURCE_ARCHITECTURE.md`, der Projektvision und dem eingefrorenen Core V1 abgeglichen.

Erst daraus wird entschieden, welcher erste echte Baustein unter `src/` den größten Erkenntnisgewinn liefert.
