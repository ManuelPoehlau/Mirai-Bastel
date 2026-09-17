# Mirai-Bastel — Artist Toolbox / Einkaufsliste

**Status:** Working Inventory — noch keine Roadmap  
**Purpose:** Vollständige Bestands- und Wunschliste für die grundlegende Artist-Toolbox  
**Phase:** Discovery / Sorting  
**Datum:** 2026-09-17

---

## 0. Zweck dieses Dokuments

Dieses Dokument beschreibt möglichst breit, welche grundlegenden Fähigkeiten ein Artist in Mirai-Bastel benötigt, wenn er das Programm öffnet und **tatsächlich etwas bauen, untersuchen und verändern möchte**.

Es ist ausdrücklich **keine Roadmap** und keine Architekturentscheidung.

Die Liste soll zunächst:

1. vorhandene Fähigkeiten sichtbar machen,
2. fehlende Grundausstattung identifizieren,
3. unnötige oder nicht mehr relevante Punkte entfernen,
4. neue Anforderungen ergänzen,
5. lose vorhandene Funktionen und Experimente einordnen,
6. anschließend als Grundlage für die Zuordnung zu bestehenden und zukünftigen Work Packages dienen.

### Arbeitsregel

> **Erst Werkzeugkasten definieren. Dann Bestand prüfen. Dann priorisieren. Dann WPs zuordnen.**

Nicht umgekehrt.

Ein Experiment soll möglichst nicht erst während seiner Durchführung ein fehlendes Grundwerkzeug als Sonderlösung bauen müssen.

---

# 1. Status-Legende

Die Markierungen sind bewusst einfach gehalten.

- `[ ]` offen / noch prüfen
- `[x]` vorhanden / ausreichend
- `[~]` teilweise vorhanden / unvollständig
- `[-]` bewusst streichen
- `[?]` unklar / weitere Untersuchung nötig
- `[E]` experimentell / Forschungsgegenstand
- `[D]` doppelt oder verteilt / Ownership klären

**Wichtig:** Ein `[x]` bedeutet zunächst nur „funktioniert grundsätzlich“.  
Es bedeutet **nicht**, dass die aktuelle Implementierung bereits endgültig production-ready ist.

---

# 2. Application / Scene Start

## 2.1 Programmstart

- [x] Programm startet in einen brauchbaren Arbeitszustand
- [ ] Default-Szene
- [x] leere Szene
- [x] neue Szene
- [ ] Szene zurücksetzen
- [ ] zuletzt verwendete Szene öffnen
- [ ] Startobjekt / Startmodell
- [x] definierte Default-Kamera
- [x] definierter Default-Viewport
- [x] verständlicher initialer HUD-Zustand
- [ ] klar erkennbarer aktueller Modus
- [ ] klar erkennbare aktuelle Auswahl

## 2.2 Scene Management

- [x] Objekt erzeugen
- [x] Objekt löschen
- [ ] Objekt duplizieren
- [ ] Objekt umbenennen
- [x] Objekt auswählen
- [x] mehrere Objekte auswählen
- [x] Auswahl aufheben
- [ ] Objekte gruppieren
- [ ] Gruppe auflösen
- [ ] Parent / Child
- [ ] Hierarchie anzeigen
- [ ] Objekt ein-/ausblenden
- [ ] Objekt sperren
- [x] Objekt aktiv setzen
- [ ] aktive Szene / aktives Objekt sichtbar machen

## 2.3 Grundlegende Scene-Struktur

- [x] Scene
- [x] Object
- [x] Mesh
- [ ] Camera
- [~] Light / Lighting
- [x] Material / Appearance
- [ ] Collection / Group
- [ ] Hierarchy
- [ ] Instancing
- [ ] Referenzobjekt / Guide

---

# 3. Primitive Creation

## 3.1 Grundprimitive

- [x] Cube
- [x] Plane
- [x] Sphere
- [x] Cylinder
- [ ] Cone
- [ ] Capsule
- [ ] Torus
- [ ] Circle
- [ ] Line
- [ ] Empty / Null / Locator

## 3.2 Primitive Parameter

- [ ] Größe
- [ ] Breite
- [ ] Höhe
- [ ] Tiefe
- [ ] Radius
- [x] Segmente
- [ ] Auflösung
- [x] Anzahl Rings
- [x] Anzahl Sides
- [~] parametrische Änderung direkt nach Erzeugung
- [~] numerische Eingabe
- [ ] primitive orientation
- [ ] primitive placement

## 3.3 Primitive Workflow

- [ ] Create → immediately transform
- [x] Create → immediately edit
- [ ] primitive als Ausgangsmesh verwenden
- [ ] primitive erneut parametrisieren
- [ ] primitive in normales Mesh umwandeln

---

# 4. Viewport Navigation

## 4.1 Grundnavigation

- [x] Orbit
- [x] Pan
- [x] Zoom
- [ ] Dolly
- [x] kontinuierliche Navigation
- [ ] Navigation während anderer Interaktionen
- [ ] Navigation abbrechen
- [ ] Navigation zurücksetzen

## 4.2 View Framing

- [ ] Frame All
- [x] Frame Selected
- [ ] Frame Object
- [ ] Frame Component Selection
- [ ] Frame Scene
- [ ] Fokuspunkt setzen
- [ ] Fokuspunkt automatisch bestimmen
- [ ] Zoom auf Bounds
- [ ] sinnvolle Default-Framing-Logik

## 4.3 Standard Views

- [x] Front
- [x] Back
- [x] Left
- [x] Right
- [x] Top
- [x] Bottom
- [x] Perspective
- [x] Orthographic
- [ ] View Cube / View Gizmo oder Alternative
- [~] View Orientation sichtbar

## 4.4 Kamera

- [ ] Orbit Camera
- [ ] Pan Camera
- [ ] Zoom Camera
- [ ] Camera Target / Focus
- [ ] Camera Reset
- [ ] Camera State speichern
- [ ] Camera State wiederherstellen
- [ ] Camera Framing
- [ ] sinnvolle Clipping-Distanzen
- [ ] stabile Navigation bei unterschiedlichen Meshgrößen

---

# 5. Selection — Object Level

- [x] Single Select
- [x] Multi Select
- [x] Add
- [x] Subtract
- [ ] Toggle
- [ ] Replace
- [ ] Select All
- [ ] Select None
- [ ] Invert Selection
- [ ] Select Visible
- [ ] Select Hidden
- [ ] Active Object
- [ ] Last Selected
- [x] Selection Highlight
- [ ] Selection Clear
- [ ] Selection Persistence

---

# 6. Selection — Component Level

## 6.1 Component Modes

- [x] Vertex
- [x] Edge
- [x] Face
- [x] Object
- [ ] Element / Island
- [ ] UV / future
- [ ] Bone / Rig / future

## 6.2 Selection Methods

- [x] Click
- [x] Box
- [x] Lasso
- [x] Paint / Brush
- [x] Through / X-Ray Selection
- [x] Visible-only Selection
- [ ] Connected
- [ ] Similar
- [ ] By Material
- [ ] By Normal
- [ ] By Angle
- [ ] By Attribute / future

## 6.3 Topological Selection

- [x] Edge Loop
- [x] Edge Ring
- [ ] Face Loop
- [ ] Face Ring
- [ ] Connected Vertices
- [ ] Connected Edges
- [ ] Connected Faces
- [ ] Boundary
- [ ] Non-Manifold
- [ ] Isolated
- [ ] Island / Connected Component
- [ ] Shortest Path
- [~] Grow Selection
- [~] Shrink Selection
- [ ] Select Similar Topology

## 6.4 Selection Behaviour

- [ ] selection mode independent from transform mode
- [ ] selection does not unexpectedly change active tool
- [x] temporary selection modifiers
- [x] sticky / persistent selection modes
- [x] selection mode visible in HUD
- [ ] selection method visible in HUD
- [ ] predictable modifier behaviour
- [ ] selection cancellation
- [ ] selection preview

---

# 7. Transform Foundation

> **Ein gemeinsames Transform-Konzept statt drei unabhängiger Move/Rotate/Scale-Implementierungen.**

## 7.1 Basic Transform

- [x] Move
- [x] Rotate
- [x] Scale
- [x] Uniform Scale
- [x] Non-Uniform Scale
- [ ] Numeric Transform
- [ ] Relative Transform
- [ ] Absolute Transform
- [ ] Reset Transform

## 7.2 Axis Constraints

- [x] X
- [x] Y
- [x] Z
- [~] XY
- [~] XZ
- [~] YZ
- [~] Screen / View axis
- [~] Normal axis
- [~] Local axis
- [~] World axis

## 7.3 Coordinate Systems

- [x] World
- [x] Local
- [x] View
- [ ] Normal
- [ ] Parent
- [ ] Custom orientation
- [ ] Orientation switching
- [ ] orientation visible in HUD

## 7.4 Pivot

- [x] Object Origin
- [x] Selection Center
- [ ] Median
- [ ] Bounding Box Center
- [ ] Active Element
- [ ] 3D Cursor / equivalent
- [ ] Custom Pivot
- [ ] Pivot placement
- [ ] Pivot orientation
- [ ] Pivot visible

## 7.5 Transform Scope

- [ ] Object
- [ ] Selected Components
- [ ] Individual Origins
- [ ] Median
- [ ] Connected Elements
- [ ] Multiple Objects
- [ ] Hierarchy / Parent
- [ ] Proportional / Soft Transform

## 7.6 Transform Interaction

- [x] click-drag transform
- [ ] axis locking during transform
- [x] modifier keys
- [ ] temporary constraints
- [ ] numeric input during transform
- [x] confirm
- [x] cancel
- [x] preview
- [ ] snapping during transform
- [ ] transform HUD
- [ ] transform feedback
- [ ] transform undo as one coherent operation

---

# 8. Snapping / Alignment

- [ ] Grid Snap
- [ ] Vertex Snap
- [ ] Edge Snap
- [ ] Face Snap
- [ ] Pivot Snap
- [ ] Increment Snap
- [ ] Angle Snap
- [ ] Surface Snap
- [ ] Normal Alignment
- [ ] Grid visibility
- [ ] Grid size
- [ ] Snap toggle
- [ ] temporary Snap modifier
- [ ] Snap settings visible in HUD

---

# 9. Basic Mesh Editing

## 9.1 Creation

- [ ] Add Vertex
- [ ] Add Edge
- [ ] Add Face
- [ ] Fill
- [ ] Create Polygon
- [ ] Create Quad
- [ ] Create Triangle

## 9.2 Deletion

- [ ] Delete Vertex
- [ ] Delete Edge
- [ ] Delete Face
- [ ] Delete Connected
- [x] Dissolve Vertex
- [x] Dissolve Edge
- [ ] Dissolve Face

## 9.3 Basic Topology

- [x] Merge Vertices
- [ ] Weld
- [x] Collapse Edge
- [ ] Collapse Face
- [ ] Split Vertex
- [ ] Split Edge
- [ ] Split Face
- [x] Connect Vertices
- [x] Connect Edges
- [ ] Bridge
- [ ] Fill Boundary
- [ ] Make Planar
- [ ] Flip Face
- [ ] Recalculate / Reverse Normals

---

# 10. Modeling Operations

## 10.1 Core Modeling Toolbox

- [x] Extrude
- [x] Inset
- [x] Bevel
- [x] Loop Insert
- [ ] Loop Cut
- [~] Edge Slide
- [ ] Vertex Slide
- [ ] Face Slide
- [ ] Connect
- [ ] Bridge
- [x] Knife / Cut
- [x] Multi-Cut
- [ ] Offset
- [x] Extrude Along Normal
- [x] Extrude Region
- [x] Extrude Individual
- [ ] Inset Region
- [ ] Inset Individual
- [ ] Bevel Edge
- [ ] Bevel Vertex
- [ ] Bevel Face

## 10.2 Topology Operations

- [ ] Spin / Radial duplication
- [ ] Mirror
- [~] Symmetry
- [ ] Weld
- [ ] Target Weld
- [ ] Merge
- [x] Collapse
- [ ] Subdivide
- [ ] Unsubdivide
- [ ] Triangulate
- [ ] Quadrangulate
- [ ] Retopology helpers
- [ ] Relax
- [ ] Smooth
- [ ] Straighten Edge Loop
- [ ] Circularize
- [ ] Flatten

## 10.3 Future / Advanced Modeling

- [ ] Boolean
- [ ] Shell / Thickness
- [ ] Solidify
- [ ] Shell
- [ ] Array
- [ ] Radial Array
- [ ] Curve-based modeling
- [ ] Surface-based modeling
- [ ] Patch modeling
- [ ] Poly Draw
- [ ] Sculpt-like topology editing
- [ ] Interactive topology drawing

---

# 11. Subdivision / Surface

- [ ] Subdivision Preview
- [ ] Subdivision Levels
- [ ] Interactive subdivision level change
- [ ] Preview vs committed subdivision
- [ ] subdivision-aware selection
- [ ] subdivision-aware display
- [ ] cage display
- [ ] control cage
- [ ] crease
- [ ] vertex crease
- [ ] edge crease
- [ ] subdivision boundary behaviour
- [ ] subdivision topology inspection
- [ ] Catmull-Clark
- [ ] alternative subdivision methods / research

---

# 12. Mesh Information / Topology Infrastructure

## 12.1 Connectivity

- [ ] Vertex → Edges
- [ ] Vertex → Faces
- [ ] Edge → Vertices
- [ ] Edge → Faces
- [ ] Face → Vertices
- [ ] Face → Edges
- [ ] Face adjacency
- [ ] Edge adjacency
- [ ] Vertex adjacency
- [ ] Boundary detection
- [ ] Non-manifold detection
- [ ] Connected components
- [ ] Islands

## 12.2 Geometry Queries

- [ ] Face normal
- [ ] Vertex normal
- [ ] Edge direction
- [ ] Face center
- [ ] Mesh center
- [ ] Mesh bounds
- [ ] Mesh radius
- [ ] Bounding box
- [ ] Bounding sphere
- [ ] Surface area
- [ ] Volume
- [ ] edge length
- [ ] face area
- [ ] centroid
- [ ] geometric center

## 12.3 Topology Traversal

- [ ] Loop traversal
- [ ] Ring traversal
- [ ] Boundary traversal
- [ ] Face traversal
- [ ] Region traversal
- [ ] shortest path
- [ ] connected traversal
- [ ] topological distance

---

# 13. Display / Shading

## 13.1 Basic Display

- [x] Solid
- [x] Wireframe
- [x] Vertex display
- [x] Edge display
- [x] Face display
- [ ] X-Ray
- [ ] Transparent
- [x] Selection overlay
- [ ] Grid
- [ ] Ground / floor
- [x] Background

## 13.2 Shading

- [x] Flat
- [x] Smooth
- [ ] Auto Smooth / equivalent
- [ ] Normal visualization
- [ ] Face orientation
- [ ] Vertex normals
- [ ] Edge normals
- [ ] Crease visualization

## 13.3 Presentation

- [x] Default material
- [ ] Material preview
- [ ] Lighting preview
- [ ] Studio lighting
- [ ] Environment lighting
- [ ] Shadows
- [ ] Ambient occlusion
- [ ] silhouette-friendly view
- [ ] topology-friendly view

---

# 14. Overlays / Artist Feedback

- [x] Selection highlight
- [x] Active component highlight
- [ ] Transform gizmo
- [ ] Pivot
- [x] Axis indicators
- [ ] Grid
- [ ] World axis
- [ ] Normals
- [x] Wire overlay
- [x] Vertex overlay
- [x] Edge overlay
- [x] Face overlay
- [ ] Bounding box
- [ ] measurements
- [ ] object labels
- [ ] component IDs / debug
- [ ] topology diagnostics

---

# 15. Context HUD / Interaction Feedback

## 15.1 Current State

- [ ] current tool
- [x] current selection mode
- [x] current selection method
- [x] current transform
- [ ] current coordinate system
- [ ] current pivot
- [ ] current constraint
- [ ] snapping state
- [ ] display mode
- [ ] active object

## 15.2 Contextual Help

- [ ] available actions
- [ ] current shortcuts
- [ ] modifier keys
- [ ] confirm key
- [ ] cancel key
- [ ] temporary modes
- [ ] contextual tool information
- [ ] interaction hints

## 15.3 Feedback

- [x] operation preview
- [x] operation result
- [x] selection feedback
- [ ] constraint feedback
- [ ] invalid operation feedback
- [ ] progress / long-operation feedback
- [ ] undo feedback
- [ ] clear state after cancellation

---

# 16. Interaction Model

- [x] tool activation
- [x] temporary tool activation
- [ ] modal operation
- [ ] non-modal operation
- [x] click-drag operation
- [x] keyboard-driven operation
- [x] modifier-driven operation
- [x] operation confirmation
- [x] operation cancellation
- [ ] repeat last operation
- [ ] repeat operation
- [ ] interactive preview
- [ ] operation state reset
- [ ] no stale modal state
- [ ] predictable keyboard precedence
- [ ] navigation remains available where appropriate

---

# 17. Undo / Redo / History

- [x] Undo
- [x] Redo
- [?] operation-level undo
- [?] transform as one undo
- [ ] topology operation as one undo
- [ ] selection history / optional
- [ ] history stack
- [ ] history inspection
- [ ] history awareness
- [ ] clear history
- [ ] branching behaviour defined
- [ ] redo invalidation after new operation
- [ ] safe cancellation without history pollution

---

# 18. Object / Component Organization

- [ ] object naming
- [ ] object visibility
- [ ] object lock
- [ ] object hierarchy
- [ ] parent
- [ ] child
- [ ] collection
- [ ] layer
- [ ] active object
- [ ] isolate object
- [ ] local view
- [ ] hide selected
- [ ] hide unselected
- [ ] unhide all
- [ ] freeze object
- [ ] reference object
- [ ] guide object

---

# 19. Materials / Appearance — Basic

- [x] default material
- [ ] material assignment
- [x] material color
- [x] viewport color
- [ ] material slots
- [ ] assign material to faces
- [ ] remove material assignment
- [ ] material visibility
- [ ] basic texture support
- [ ] basic image texture support
- [ ] UV-independent viewport appearance
- [ ] future shader/material system

---

# 20. UV / Texture — Basic Infrastructure

- [ ] UV coordinates
- [ ] UV display
- [ ] UV selection
- [ ] UV seams
- [ ] unwrap
- [ ] planar projection
- [ ] box projection
- [ ] cylindrical projection
- [ ] UV editing
- [ ] UV transform
- [ ] texture preview

**Note:** Nicht zwingend Teil der ersten Modellierungsbasis, aber als vollständiger Artist-Werkzeugkasten sichtbar halten.

---

# 21. Import / Export / Assets

## 21.1 Scene Files

- [x] Save
- [ ] Save As
- [x] Open
- [x] New
- [ ] Recent Files
- [ ] Autosave
- [ ] Recovery
- [ ] version information
- [ ] scene compatibility

## 21.2 Mesh Import

- [x] OBJ Import
- [ ] OBJ Export
- [ ] STL Import
- [ ] STL Export
- [ ] FBX / future
- [ ] glTF / future
- [ ] other formats / future

## 21.3 Asset Handling

- [ ] asset path handling
- [ ] relative paths
- [ ] absolute paths
- [ ] asset discovery
- [ ] asset references
- [ ] missing asset handling
- [ ] asset browser / future
- [ ] external references / future
- [ ] reusable model assets

---

# 22. Measurement / Precision

- [ ] numeric input
- [ ] dimensions
- [ ] distance measurement
- [ ] angle measurement
- [ ] coordinates
- [ ] object dimensions
- [ ] grid units
- [ ] unit system
- [ ] snapping increments
- [ ] transform precision
- [ ] input validation

---

# 23. Modeling Helpers

- [ ] Mirror
- [ ] Symmetry
- [ ] Array
- [ ] Duplicate Along Axis
- [ ] Align
- [ ] Distribute
- [ ] Center
- [ ] Match Position
- [ ] Match Rotation
- [ ] Match Scale
- [ ] Flatten
- [ ] Straighten
- [ ] Relax
- [ ] Circularize
- [ ] Make Planar

---

# 24. Diagnostics / Mesh Health

- [ ] non-manifold detection
- [ ] isolated vertices
- [ ] duplicate vertices
- [ ] duplicate faces
- [ ] zero-area faces
- [ ] degenerate edges
- [ ] flipped normals
- [ ] open boundaries
- [ ] disconnected components
- [ ] invalid topology
- [ ] mesh statistics
- [ ] vertex count
- [ ] edge count
- [ ] face count
- [ ] triangle count
- [ ] polygon count
- [ ] topology visualization
- [ ] repair helpers

---

# 25. Character / Deformation Foundations

Nicht als sofortige Feature-Roadmap verstehen. Diese Punkte dienen dazu, den späteren Charakter-/Deformationsbereich sichtbar zu halten.

## 25.1 Transforms

- [ ] reusable transform representation
- [ ] transform hierarchy
- [ ] local transform
- [ ] world transform
- [ ] parent transform
- [ ] transform composition

## 25.2 Deformation

- [ ] deformable mesh
- [ ] vertex weights
- [ ] skinning
- [ ] basic joint influence
- [ ] deformation preview
- [ ] weight visualization
- [ ] weight editing
- [ ] mirror weights

## 25.3 Morphing

- [ ] morph target
- [ ] blendshape
- [ ] morph value
- [ ] multiple morphs
- [ ] morph editing
- [ ] morph visualization

## 25.4 Rigging

- [ ] joint / bone
- [ ] hierarchy
- [ ] control
- [ ] handle
- [ ] posing
- [ ] constraints
- [ ] IK / future
- [ ] FK
- [ ] deformation preview

---

# 26. Animation — Basic Visibility

Nicht zwingend Teil der ersten Modellierungsbasis.

- [ ] timeline
- [ ] play
- [ ] stop
- [ ] frame navigation
- [ ] keyframe
- [ ] interpolation
- [ ] animation curves
- [ ] pose
- [ ] animation preview
- [ ] animation import/export

---

# 27. Performance / Robustness

- [x] responsive viewport
- [x] stable navigation
- [?] stable selection
- [?] stable transform
- [ ] large mesh handling
- [ ] large selection handling
- [ ] predictable redraw
- [ ] no unnecessary rebuilds
- [ ] incremental rendering
- [ ] resource lifecycle
- [ ] clean application shutdown
- [ ] recoverable errors
- [ ] useful diagnostics
- [ ] headless testability

---

# 28. Keyboard / Mouse Workflow

## 28.1 Basic

- [ ] consistent shortcut scheme
- [~] configurable shortcuts
- [x] modifier keys
- [x] temporary modes
- [x] tool hotkeys
- [ ] selection hotkeys
- [ ] view hotkeys
- [?] transform hotkeys
- [x] display hotkeys

## 28.2 Mouse

- [x] left-click selection
- [x] right-click / context
- [ ] middle mouse navigation
- [x] wheel zoom
- [x] drag operations
- [x] modifier-click selection
- [ ] context-sensitive mouse behaviour

## 28.3 Artist Flow

- [ ] minimal modal friction
- [x] easy cancel
- [x] easy undo
- [ ] predictable focus
- [?] keyboard-first operation
- [ ] temporary tools
- [ ] repeat operation
- [ ] operation discoverability

---

# 29. Context / Mode Management

- [x] current mode
- [x] current tool
- [x] current selection
- [?] current transform
- [x] current display
- [ ] current object
- [x] current component
- [ ] temporary state
- [ ] modal state
- [ ] state reset
- [ ] state persistence
- [ ] state visible in HUD
- [ ] no conflicting active authorities

---

# 30. Viewport ↔ Core Boundary

Nicht als konkrete Architekturentscheidung, sondern als benötigte Fähigkeit sichtbar halten:

- [ ] Core mesh sichtbar machen
- [ ] Core scene sichtbar machen
- [ ] Core selection sichtbar machen
- [ ] Core changes reflected in viewport
- [ ] viewport selection reflected where required
- [ ] topology changes reflected immediately
- [ ] transform changes reflected immediately
- [ ] display changes reflected immediately
- [ ] efficient derived render data
- [ ] predictable synchronization
- [ ] no duplicate authoritative state

---

# 31. Experiment / Research Support

Der Playground ist selbst ein Werkzeug.

- [x] experiment host
- [x] experiment slots
- [x] independent variant families
- [x] switch variants
- [x] multiple families active simultaneously
- [x] focus one research question
- [x] settings remain variable
- [ ] observation capture
- [ ] experiment notes
- [?] decision state
- [?] KEEP
- [?] REJECT
- [?] ITERATE
- [?] UNDECIDED
- [ ] candidate promotion
- [~] restart with selected variant
- [ ] compare variants
- [ ] temporary experiments without production commitment
- [ ] easy experiment reset

---

# 32. Research Areas / Dinge, die bewusst noch offen bleiben können

Diese Punkte gehören auf die große Karte, müssen aber nicht sofort Bestandteil der Grundausstattung werden.

- [?] Proportional Editing
- [x] Soft Selection
- [ ] Sculpting
- [ ] Dynamic Topology
- [ ] advanced retopology
- [ ] procedural modeling
- [ ] node-based modeling
- [ ] modifiers
- [ ] non-destructive modeling
- [ ] construction history
- [ ] procedural deformation
- [ ] advanced symmetry
- [ ] advanced snapping
- [ ] surface modeling
- [ ] curves
- [ ] NURBS
- [ ] subdivision modeling variants
- [ ] sculpt / box-model hybrid workflows
- [ ] advanced character controls
- [ ] facial morph workflow
- [ ] animation systems
- [ ] simulation
- [ ] rendering
- [ ] compositing
- [ ] scripting
- [ ] plugins
- [ ] external tool integration

---

# 33. Artist Experience

## 33.1 Orientierung

- [x] Ich sehe sofort, was ausgewählt ist.
- [x] Ich sehe sofort, was ich gerade tun kann.
- [x] Ich sehe sofort, welcher Modus aktiv ist.
- [ ] Ich sehe wichtige temporäre Zustände.
- [ ] Ich weiß, wie ich eine Operation abbreche.
- [ ] Ich weiß, wie ich sie bestätige.
- [ ] Ich kann schnell rückgängig machen.

## 33.2 Discoverability

- [ ] Kontext-HUD
- [ ] Tooltips
- [ ] Shortcut-Hinweise
- [ ] contextual help
- [ ] sichtbare aktive Constraints
- [ ] sichtbare aktive Selection Mode
- [ ] sichtbarer Transform Mode

## 33.3 Flow

- [ ] wenige unnötige Dialoge
- [ ] wenige unnötige Moduswechsel
- [ ] direkte Manipulation
- [ ] schnelle Wiederholung
- [ ] temporäre Werkzeuge
- [ ] konsistentes Verhalten
- [ ] kein überraschender State
- [ ] Undo als Sicherheitsnetz

---

# 34. „Ich öffne das Programm und möchte etwas bauen“

Minimaler Realitätscheck.

Wenn Mirai-Bastel geöffnet wird und ein Artist einfach anfangen möchte:

### Orientierung

- [x] Ich sehe ein Modell oder kann eines erzeugen.
- [x] Ich kann die Kamera bewegen.
- [x] Ich kann das Objekt fokussieren.
- [x] Ich kann zwischen Standardansichten wechseln.

### Auswahl

- [x] Ich kann Objekt auswählen.
- [x] Ich kann Vertex auswählen.
- [x] Ich kann Edge auswählen.
- [x] Ich kann Face auswählen.
- [x] Ich kann mehrere Elemente auswählen.

### Veränderung

- [x] Ich kann verschieben.
- [x] Ich kann rotieren.
- [x] Ich kann skalieren.
- [x] Ich kann auf X/Y/Z beschränken.
- [ ] Ich kann numerisch arbeiten.

### Modellieren

- [x] Ich kann Geometrie hinzufügen.
- [x] Ich kann Geometrie löschen.
- [x] Ich kann extrudieren.
- [ ] Ich kann insetten.
- [x] Ich kann Kanten verbinden.
- [x] Ich kann Loops erzeugen.
- [x] Ich kann Kanten verschieben.
- [x] Ich kann verschweißen.
- [ ] Ich kann Flächen füllen.

### Kontrollieren

- [x] Ich kann Wireframe sehen.
- [x] Ich kann Vertices/Edges/Faces sehen.
- [ ] Ich kann Normals kontrollieren.
- [ ] Ich kann X-Ray verwenden.
- [x] Ich kann die Darstellung ändern.

### Sicherheit

- [x] Undo
- [x] Redo
- [x] Cancel

### Daten

- [x] Ich kann mein Ergebnis speichern.
- [x] Ich kann es wieder öffnen.
- [x] Ich kann ein vorhandenes Mesh importieren.

---

# 35. Was ist wirklich „Grundausstattung“?

Diese Kategorie **noch nicht ausfüllen**.

Sie wird erst nach Durchgang durch die gesamte Liste definiert.

Mögliche spätere Kategorien:

- **Essential** — ohne das ist das Programm für den vorgesehenen Zweck kaum benutzbar
- **Basic** — gehört in die normale Werkzeugausstattung
- **Useful** — sinnvoll, aber nicht zwingend
- **Advanced** — später
- **Research** — erst experimentieren
- **Future** — bewusst außerhalb des aktuellen Horizonts
- **Not needed** — bewusst nicht Teil von Mirai-Bastel

---

# 36. Loose Ends — vorhandene Dinge, die später einsortiert werden müssen

Hier werden zunächst nur Dinge gesammelt. Noch keine Entscheidung treffen.

- [ ] Transform aus Rigging Research
- [ ] `frame_camera_on_bounds`
- [ ] Mesh bounds utilities
- [ ] Mesh center / radius
- [ ] OBJ parser
- [ ] OBJ → Core Scene
- [ ] Head basemesh / asset handling
- [ ] Integration-Lab framing helpers
- [ ] Integration-Lab scene helpers
- [ ] Playground topology tools
- [ ] Playground selection variants
- [ ] Playground transform variants
- [ ] Playground presentation variants
- [ ] existing camera variants
- [ ] Core → Viewport binding variants
- [ ] existing picking infrastructure
- [ ] existing selection state
- [ ] existing transform operations
- [ ] existing history
- [ ] existing display state
- [ ] existing render infrastructure
- [ ] existing HUD infrastructure
- [ ] existing experiment host
- [ ] existing primitive builders
- [ ] existing topology algorithms
- [ ] existing deformation utilities
- [ ] existing rigging viewer
- [ ] other loose capabilities discovered during inventory

---

# 37. Not Yet — bewusst nicht entscheiden

Die folgenden Fragen werden **nicht in diesem Dokument beantwortet**:

- Welche konkrete Architektur bekommt eine Fähigkeit?
- Welches Modul wird Eigentümer?
- Wird etwas aus einem Experiment nach `src/` verschoben?
- Welche Variante gewinnt?
- Welche Interaktion wird Standard?
- Welche Hotkeys werden endgültig verwendet?
- Welche Technologie wird verwendet?
- Welches WP implementiert welchen Punkt?
- Welche Features werden zuerst gebaut?
- Was wird Production und was bleibt Experiment?

Diese Fragen kommen **nach** dem Werkzeugkasten-Inventar.

---

# 38. Nächster Arbeitsprozess

## Phase 1 — Artist Review

Der Artist geht die Liste durch.

Für jeden Punkt:

- abhaken
- streichen
- umformulieren
- ergänzen
- kommentieren
- als unbekannt markieren

Noch keine WP-Zuordnung.

## Phase 2 — Bestandsaufnahme

Die bereinigte Liste wird gegen den aktuellen Repository-Zustand gehalten:

- `src/`
- `playground/`
- `experiments/`
- `tests/`
- vorhandene Dokumentation

Dabei wird sichtbar:

> **Was haben wir bereits? Wo liegt es? Und wie vollständig ist es?**

## Phase 3 — Konsolidierung

Lose vorhandene Fähigkeiten werden den Werkzeugkasten-Kategorien zugeordnet.

Dabei können sich natürliche technische Gruppen ergeben.

## Phase 4 — Priorisierung

Erst jetzt wird bestimmt:

- Was ist Grundausstattung?
- Was fehlt dringend?
- Was kann warten?
- Was gehört in Research?
- Was ist bereits ausreichend vorhanden?

## Phase 5 — WP-Zuordnung

Erst danach werden die Punkte bestehenden oder neuen Work Packages zugeordnet.

Dabei soll möglichst die **bestehende Roadmap erhalten bleiben**, statt sie vorschnell neu zu erfinden.

---

# 39. Grundgedanke

> **Der Playground ist die Werkstatt für unbekannte Werkzeuge.  
> Die Toolbox ist die Grundausstattung der Werkstatt.  
> Die Roadmap baut die Werkstatt aus.**

Ein Experiment sollte möglichst mit vorhandenen Werkzeugen arbeiten können.

Wenn ein Experiment ständig erst fehlende Grundfunktionen bauen muss, ist das möglicherweise kein Problem des Experiments, sondern ein Hinweis darauf, dass ein Stück **Grundausstattung** fehlt.

---

**Arbeitsstatus:** Offen für Artist Review  
**Keine WP-Zuordnung vorgenommen.**  
**Keine Architekturentscheidungen vorgenommen.**