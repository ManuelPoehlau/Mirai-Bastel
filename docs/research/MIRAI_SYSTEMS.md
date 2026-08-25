# Mirai / N-World – System Extraction

> **Research status:** active  
> **Method:** Quellen zerlegen und beobachtbare/technische Systeme getrennt erfassen.  
> **Wichtig:** Aussagen werden als `FACT`, `OBSERVED`, `INTERPRETATION` oder `HYPOTHESIS` markiert.

## 0. Current picture

Die bislang zugänglichen Quellen zeigen Mirai nicht als klassischen „Modeler plus separate Animation tools“, sondern als stark integrierte Content-Creation-Umgebung. Eine zeitgenössische Beschreibung bezeichnet Mirai sinngemäß als eine Art „3D operating system“ und betont dynamisch verbundene Editoren, Kontext und Mausinteraktion. [S1]

Die historische S-Graphics/N-World/Mirai-Seite bestätigt die Entwicklungslinie und verweist direkt auf die N-World-3.0-Dokumentation. [S0]

**Arbeits-Hypothese für Mirai-Bastel:** Wir sollten das System als integrierten, zustandsarmen Workflow betrachten, bei dem Auswahl, Kontext, Operation und Darstellung eng zusammenspielen, aber im Code klar getrennt bleiben.

---

# 1. Selection System

## Evidence

### FACT / HIGH CONFIDENCE
N-World/Mirai ist ein polygonaler Modeler; N-World wird als Winged-Edge-3D-Modeler beschrieben. [S2]

### OBSERVED / TO VERIFY
Historische Nutzerberichte beschreiben Mirai als stark kontextgetrieben: Aktionen werden abhängig vom aktuell ausgewählten Element angeboten; die rechte Maustaste öffnet kontextabhängige Operationen. [S3]

### DESIGN DIRECTION
Mirai-Bastel V1:

- Vertex selection
- Edge selection
- Face selection
- Object selection
- Hover highlighting
- Add/remove selection
- Grow/Shrink später
- Loop/Ring-Navigation architektonisch von Anfang an ermöglichen

**Wichtig:** Soft Selection wird nicht als eigener Selection Mode modelliert. Sie ist eine **Influence Layer** über einer normalen Selection.

```text
Selection
    ↓
Influence / Falloff
    ↓
Affected Elements
```

Das entspricht unserer bisherigen Entscheidung, dass ein separater „Mode 3“ nicht nötig ist.

---

# 2. Mouse Interaction / Context

## Evidence

### FACT / HIGH CONFIDENCE
Der zeitgenössische Game Developer-Artikel beschreibt Mirai als stark kontextorientiert und hebt Left/Middle/Right Mouse sowie Sequenz/Kontext der Bedienung hervor. [S1]

### STRONG LEAD
Ein späterer Anwenderbericht beschreibt `right-click → operation` und Modifier wie ALT/CTRL als Wege zu Varianten einer Operation, darunter Magnet Move und unterschiedliche Falloff-Kategorien. [S3]

### DESIGN HYPOTHESIS
Nicht:

```text
Ctrl + Drag = fest verdrahtete Vertex-Funktion
```

sondern:

```text
Mouse gesture
    ↓
Input Context
    ↓
Hovered / Selected Element
    ↓
Operation Resolver
    ↓
Operation
```

Damit können dieselben Operationen später per Maus, Shortcut, Menü oder Script aufgerufen werden.

---

# 3. Modeling System

## Evidence

N-World/Mirai verfügte über polygonales Modeling, Smoothing und Magnet Geometry Editing. [S2]

Mirai 1.1 nennt zusätzliche Modeling-Optionen, verbesserte Camera Manipulation und Magnet Move. [S4]

### Magnet Move

`FACT / CONTEMPORARY SOURCE:` Mirai 1.1 konnte mehrere Vertices entlang ihrer Normalen mit Falloff bewegen. [S4]

Das ist konzeptionell sehr nah an unserem heutigen Soft-Selection-Ziel.

### Modeling Core – planned

V1-Kern:

- Move / Tweak
- Rotate
- Scale uniform
- Scale along axis
- Extrude
- Inset
- Edge Slide
- Face/vertex movement
- basic topology operations
- subdivision preview

Später:

- Bevel
- Bridge
- Connect/Cut
- Loop tools
- Magnet/soft selection variants

---

# 4. Camera / Viewport

## Evidence

Mirai 1.1 nennt ausdrücklich Verbesserungen der Camera Manipulation. [S4]

Wings3D, als direkter Nachfahre der Nendo/Mirai-Linie, dokumentiert Orthographic View, View Along X/Y/Z und direkte Navigation. [S5]

### V1 Design

- Perspective
- Orthographic
- Front
- Back
- Left
- Right
- Top
- Bottom
- View snap
- Orbit
- Pan
- Zoom
- Frame selection/object

Die Kamera soll als eigener Zustand behandelt werden und nicht Teil der Modeling-Operationen sein.

---

# 5. Topology

## FACT / HIGH CONFIDENCE
Bay Raitt beschreibt Mirai ausdrücklich mit einer **Winged Edge data structure**. [S6]

### Implication
Die Topologie ist vermutlich nicht als bloße Liste von Face-Indexlisten gedacht.

Für Mirai-Bastel müssen wir mindestens effiziente Beziehungen unterstützen:

```text
Vertex ↔ Edge
Edge ↔ Face
Face ↔ Boundary
Vertex ↔ Neighbours
```

### Architecture investigation

Vor der finalen Implementierung vergleichen:

1. Winged Edge – historische Nähe
2. Half Edge – moderne, gut erforschte Alternative
3. Hybrid – explizite Topologie + effiziente Render-Repräsentation

**Noch keine Entscheidung.**

---

# 6. Subdivision

N-World/Mirai ist ein Subdivision-/Smoothing-orientierter Modeler. [S2]

### V1

Control Mesh bleibt die editierbare Wahrheit.

```text
Control Mesh
     ↓
Subdivision
     ↓
Display Surface
```

Das Display Mesh darf jederzeit neu berechnet werden.

### Later research

- Catmull-Clark
- extraordinary vertices
- creases
- subdivision boundary rules
- stable vertex/edge/face IDs
- deformation of subdivided surfaces

---

# 7. Animation / Morph / Deformation

Hier wird Mirai besonders interessant.

### FACT / CONTEMPORARY SOURCE
Mirai bezeichnet „Displacement“ als das, was andere Pakete Morphing/Blend Shapes nennen. Displacements konnten für Facial Animation verwendet und mit Slidern verbunden werden. [S1]

Mirai unterstützte außerdem skeletal animation, IK, motion capture und nichtlineare Motion Editing-Workflows. [S1][S4]

Der zeitgenössische Artikel zeigt sogar eine Arbeitsumgebung, in der geglättete Oberfläche, verbundenes Low-Polygon-Modell, slider-gesteuerte Animation, Graphen und Timeline gleichzeitig sichtbar sind. [S1]

### Konsequenz für die Vision

Das bestätigt einen zentralen Teil dessen, was uns an den alten Videos fasziniert:

> Modeling, Deformation und Animation waren nicht gedanklich komplett voneinander getrennte Welten.

**Aber:** Daraus folgt noch nicht, dass Mirai beliebige Topologieänderungen nach bereits erzeugten Morphs/Weights ohne weitere Konsequenzen erlaubte. Das bleibt eine offene Forschungsfrage.

### Long-term architecture hypothesis

```text
Mesh
 ├── Topology
 ├── Geometry
 ├── Subdivision
 ├── Deformations
 │    ├── Morph / Displacement
 │    ├── Skin / Weights
 │    └── Other Deformers
 └── Animation / Evaluation
```

Der Evaluationszustand sollte vom editierbaren Ausgangsmesh unterscheidbar sein.

---

# 8. History / Editor System

### STRONG EVIDENCE
Die zeitgenössische Mirai-Beschreibung betont dynamisch verbundene Editoren und einen integrierten Workflow. [S1]

Mirai unterstützte außerdem Scripting und nichtlineare Motion Editing Workflows; Bewegungs-Layer konnten kombiniert, wieder getrennt und über Scripts erweitert werden. [S1]

### OPEN QUESTION
Wie genau Modeling-Undo/History intern funktionierte, ist noch nicht geklärt.

Mögliche Modelle:

- command history
- reversible topology operations
- snapshots
- hybrid

### DESIGN DIRECTION
Mirai-Bastel sollte Operationen grundsätzlich als **reproduzierbare Aktionen** denken.

```text
Input
  ↓
Operation
  ↓
Change Set
  ↓
Mesh / Scene State
```

Damit bleiben Undo, Redo, Scripting und später Makros grundsätzlich möglich.

---

# 9. Integrated Editors / "3D Operating System"

Dieser Punkt verdient eine eigene spätere Forschungsdatei.

Die zeitgenössische Quelle beschreibt Mirai als System mit mehreren dynamisch verbundenen Editoren. [S1]

Das könnte erklären, warum Mirai in historischen Demos so anders wirkt als klassische Programme mit:

```text
Modeling Mode
Animation Mode
Morph Mode
UV Mode
Paint Mode
```

### Hypothesis
Statt harter „Modes“ könnte Mirai stärker mit **gemeinsamem Scene State + kontextabhängigen Editoren** gearbeitet haben.

Das wäre eine wichtige Leitidee für Mirai-Bastel:

> **Nicht der Benutzer wechselt ständig das Programm-Modul; die Werkzeuge reagieren auf den aktuellen Kontext.**

Noch nicht als Fakt festschreiben.

---

# 10. V1 boundary

V1 konzentriert sich bewusst auf den Kern, der den Mirai/Nendo/Silo/Wings-artigen Modeling-Workflow ausmacht:

- mesh topology
- vertex/edge/face/object selection
- hover
- tweak
- transforms
- axis constraints
- soft selection / influence foundation
- extrusion/basic topology tools
- subdivision preview
- intuitive camera/navigation
- undo/redo foundation

Animation, morphs, rigging und 3D paint bleiben zunächst **Architekturziele**, nicht V1-Features.

---

# Sources

**[S0]** Historical S-Graphics/N-World/Mirai information site – https://s-graphics.neocities.org/  
**[S1]** Game Developer Magazine, December 1999, Mirai product review – https://valvearchive.com/archive/Other%20Files/Publications/The%20Cabal%20%28Ken%20Birdwell%29/The%20Cabal%20%28Valve%27s%20Design%20Process%20For%20Creating%20Half-Life%29/Game%20Developer%20Magazine/GDM_December_1999.pdf  
**[S2]** N-World historical overview / references to N-World 3.0 documentation – https://en.wikipedia.org/wiki/N-World  
**[S3]** XPForums, Nichimen Mirai thread – https://www.xpforums.com/threads/the-official-nichimen-mirai-thread-nendo-too.935716/  
**[S4]** Game Developer Magazine, April 2000, Mirai 1.1 product update – https://media.gdcvault.com/GD_Mag_Archives/GDM_April_2000.pdf  
**[S5]** Wings3D documentation – https://www.wings3d.com/documentation/user-manual-table-of-contents/hotkey-assignments/  
**[S6]** Bay Raitt professional description – https://www.linkedin.com/in/bay-raitt-2204161/

---

## Next research pass

1. Retrieve and preserve the N-World 3.0 online documentation.
2. Extract its actual command/selection/navigation structure section by section.
3. Search specifically for Mirai 1.x manuals/help files and Nendo documentation.
4. Correlate documentation terminology with Bay Raitt/Martin Krol videos.
5. Create separate technical notes for Selection, Modeling, Camera, Topology, SubD, Deformation and History as evidence becomes strong enough.
