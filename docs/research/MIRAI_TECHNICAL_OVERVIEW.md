# Mirai – Technical Overview (Research)

> **Status:** frühe Recherche  
> **Zweck:** technisches Grundwissen und belastbare Hypothesen sammeln, bevor die Architektur von Mirai-Bastel festgelegt wird.

## 1. Was wir bisher mit hoher Sicherheit wissen

### Mirai ist Teil einer längeren technischen Linie

Die historische Linie wird in mehreren Quellen als ungefähr **Symbolics S-Graphics → Nichimen N-World → Mirai → Nendo → Wings3D** beschrieben. N-World/Mirai stammt aus der Nichimen-Graphics-Linie und wurde in Common Lisp entwickelt. Die Software lief auf SGI/IRIX und später Windows NT. [1][2]

Bay Raitt beschreibt Mirai als 3D-Creation-/Editing-Suite, ursprünglich von Nichimen Graphics, später Winged Edge Technologies und Izware. Er nennt ausdrücklich die **Winged Edge data structure** und die Abstammung von Symbolics S-Geometry. [3]

### Winged Edge ist kein Zufall

Die Modellierungsseite von N-World/Mirai basiert auf einer topologischen Datenstruktur, in der die Beziehungen zwischen Geometrieelementen explizit zugänglich sind. Das passt zu dem direkten Modeling-Workflow, bei dem Nachbarschaften, Kanten und Flächen ständig manipuliert werden.

Wings3D wurde ausdrücklich von Nendo und Mirai inspiriert; bereits die Wings-Dokumentation nennt Nendo als Inspiration. Der Name Wings3D bezieht sich auf die Winged-Edge-Struktur. [4][5]

## 2. Was die historischen Videos nahelegen

Die Videos von Bay Raitt zeigen einen sehr direkten Workflow: Geometrie wird fortlaufend ausgewählt, verschoben, extrudiert und verfeinert, ohne dass der Benutzer ständig zwischen großen Tool-Panels wechseln muss.

Das ist für Mirai-Bastel wichtiger als eine 1:1-Rekonstruktion der alten Oberfläche.

### Arbeits-Hypothese

Der entscheidende Charakter des Workflows lässt sich zunächst als:

**See → Hover → Grab → Modify**

beschreiben.

Das ist eine **Design-Hypothese**, keine Behauptung über die interne Implementierung.

## 3. Mirai, Nendo und Wings3D als Forschungsgruppe

Für Mirai-Bastel sollten wir nicht nur Mirai untersuchen. Nendo und Wings3D sind wertvolle Vergleichspunkte, weil sie aus derselben bzw. einer direkt beeinflussten Modellierungsfamilie stammen und wesentlich besser dokumentiert sind.

Wings3D dokumentiert unter anderem Selection-/Modeling-Tools, Tweak Mode, Magnets/Vector Operations und anpassbare Hotkeys. [5]

Damit können wir drei Ebenen unterscheiden:

1. **Historisch belegt:** Was Mirai/N-World tatsächlich hatte.
2. **Beobachtbar:** Was in Demos sichtbar ist.
3. **Überliefert/weiterentwickelt:** Was Nendo/Wings3D aus dieser Modellierungsphilosophie übernommen haben.

## 4. Warum die Mesh-Datenstruktur zentral ist

Unser aktueller Gemini-Prototyp verwendet eine einfache Repräsentation aus Vertex-Koordinaten und Face-Indexlisten. Das ist für einen ersten Renderer hervorragend geeignet, aber wahrscheinlich nicht die endgültige Struktur für einen interaktiven Modeler.

Für Mirai-Bastel müssen wir insbesondere effizient unterstützen:

- Vertex → angrenzende Edges
- Vertex → angrenzende Faces
- Edge → angrenzende Faces
- Face → Boundary Edges
- Ring-/Loop-Navigation
- lokale Topologieänderungen
- Selection und Soft Selection
- Extrude / Inset / Bevel / Slide
- Subdivision

### Kandidaten

**Winged Edge**

Historisch besonders interessant, weil Mirai diese Struktur laut Bay Raitt selbst verwendete. [3]

**Half Edge**

Moderner und konzeptionell verwandter Ansatz. Sollte als ernsthafter Kandidat untersucht werden, bevor wir den Mesh-Core festlegen.

**Face-Vertex / einfache Indizes**

Sehr einfach und gut für Rendering, aber für häufige topologische Operationen weniger attraktiv.

### Noch keine Entscheidung

Wir sollten **nicht** automatisch Winged Edge implementieren, nur weil Mirai es tat. Erst Vergleich und kleine Experimente durchführen. Das Ziel ist das Verhalten und die Architekturidee, nicht historische Codearchäologie um jeden Preis.

## 5. Warum Common Lisp interessant ist

Common Lisp war nicht nur die Sprache, sondern Teil der technischen Herkunft des Systems. Die S-Graphics/N-World-Linie entstand aus einer Lisp-orientierten Umgebung; die verfügbaren historischen Beschreibungen nennen Common Lisp ausdrücklich als Implementierungssprache. [1][2][3]

Für Mirai-Bastel bedeutet das nicht, dass wir Lisp nachbauen müssen.

Interessant ist vielmehr die Frage, welche Eigenschaften der damaligen Umgebung zum Werkzeug beigetragen haben könnten:

- dynamische Datenstrukturen
- enge Verbindung von Daten und Verhalten
- Erweiterbarkeit / Scripting
- interaktive Entwicklung
- kleine, composable Operationen

Python kann einige dieser Eigenschaften ebenfalls gut abbilden. Wir sollten daher eher die **Systemphilosophie** übertragen als die Sprache.

## 6. Wichtige Architektur-Hypothese für Mirai-Bastel

Der Mesh-Core sollte unabhängig von UI-Gesten sein.

```text
Input
  ↓
Context / Hover / Selection
  ↓
Operation
  ↓
Transform / Topology Change
  ↓
Mesh Core
```

Nicht:

```text
Ctrl + Mouse Drag
  ↓
Direkt irgendwelche Vertices verändern
```

Eine Geste sollte eine Operation auslösen; die Operation soll unabhängig davon funktionieren, ob sie später durch Maus, Shortcut, UI oder Script ausgelöst wird.

## 7. Subdivision

Catmull-Clark und verwandte Subdivision-Verfahren sind ein zentraler Teil des historischen Polygon-/Subdivision-Modeling-Workflows. Für V1 reicht zunächst eine saubere Subdivision-Preview und ein editierbares Control Mesh.

Langfristig ist aber interessanter, wie sich Subdivision, Deformation und weitere Bearbeitung kombinieren lassen.

## 8. Das eigentliche Mirai-Ziel

Die langfristige Vision ist nicht einfach:

> „Ein Modeler mit vielen Mirai-Tools."

Sondern:

> **Ein Mesh bleibt ein lebendiges, editierbares Asset.**

Langfristig soll die Architektur ermöglichen:

```text
Model
  ↓
SubD
  ↓
Morphs
  ↓
Rig / Weights
  ↓
Pose / Animation
  ↓
weiter am Modell arbeiten
```

Ob Mirai intern exakt so arbeitete, ist eine separate Forschungsfrage. Dass diese Art von Workflow ein zentraler Teil unserer heutigen Vision ist, ist dagegen eine bewusste Designentscheidung.

## 9. Forschungsstatus

### Belegt / stark gestützt

- Mirai/N-World-Linie ist mit Symbolics/S-Graphics verbunden.
- N-World/Mirai wurde in Common Lisp entwickelt.
- Winged Edge ist ein zentraler Bestandteil des historischen Modeling-Systems.
- Nendo und Wings3D stehen in direkter Inspirationslinie zu Mirai/N-World.
- Bay Raitt nutzte Mirai intensiv und war an Gollum-/Facial-Morph-Arbeiten beteiligt.

### Beobachtung / noch zu systematisieren

- genaue Modifier-Gesten
- genaue Tweak-Semantik
- genaue Selection-/Hover-Regeln
- genaue Soft-Selection-/Falloff-Implementierung
- genaue Beziehung zwischen Modeling, Morphs, Rigging und Animation
- konkrete UI- und Kamera-Interaktion

### Offene technische Fragen

- Winged Edge vs. Half Edge vs. Hybrid
- Undo/History als Operationen oder Snapshots
- SubD-Datenmodell
- stabile Element-IDs
- Deformation Stack
- Morph Targets bei nachträglicher Topologieänderung
- Rigging/Weights bei Topologieänderung
- Python/OpenGL Architektur
- spätere native Performance-Komponenten, falls Python an Grenzen stößt

## 10. Quellen

**[1] N-World / Mirai Überblick**  
Wikipedia: N-World, historische Entwicklung, Common Lisp, S-Graphics → N-World → Mirai → Nendo → Wings3D.

**[2] Symbolics S-Graphics / Nichimen N-World / Izware Mirai Information Site**  
Historische Dokumentation und Links zu S-Graphics/N-World/Mirai sowie N-World 3.0 Documentation.

**[3] Bay Raitt – Professional Profile**  
Bay Raitt beschreibt Mirai als Common-Lisp-Suite mit Winged-Edge-Datenstruktur und nennt die Abstammung von Symbolics S-Geometry.

**[4] Wings3D User Manual**  
Historisches Wings3D-Handbuch; nennt Nendo ausdrücklich als Inspiration für Wings.

**[5] Wings3D Überblick / Feature-Historie**  
Dokumentation und Sekundärquellen zu Selection, Tweak Mode, Magnets/Vector Operations und der Mirai/Nendo-Inspirationslinie.

## Links

- https://s-graphics.neocities.org/
- https://www.linkedin.com/in/bay-raitt-2204161/
- https://en.wikipedia.org/wiki/N-World
- https://en.wikipedia.org/wiki/Wings_3D
- https://www.cs.usfca.edu/~wells/3DCG/Model-Render%20stuff/Wings%20stuff/wings3d_manual1.6.1.pdf

---

**Hinweis:** Diese Datei ist bewusst ein lebendes Research-Dokument. Aussagen werden ergänzt, korrigiert und mit Primärquellen ersetzt, sobald bessere historische Unterlagen gefunden werden.
