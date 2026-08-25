# Mirai-Bastel V1 – Spezifikation

## Ziel

V1 soll ein kleiner, direkter Polygon-/Subdivision-Modeler werden. Das Bediengefühl soll sich eher wie ein schneller Modeler à la Silo/Wings3D anfühlen als wie eine reduzierte Blender-Oberfläche.

## Selection Modes

- `1` Vertex
- `2` Edge
- `3` Face
- `4` Object

Soft Selection ist **kein eigener Selection Mode**, sondern ein unabhängiges Verhalten.

## Selection

- Hover Highlight
- Single Select
- Multi Select
- Add/Remove Selection
- Soft Selection
- Falloff / Influence Radius
- später: Loop / Ring / Grow / Shrink

## Transform

- Translate
- Rotate
- Uniform Scale
- Scale entlang X/Y/Z
- Achsen-Constraints
- Selection Pivot / Center

## Interaction

- direkter Tweak-Modus
- kontextabhängige Mausinteraktion
- Modifier-Tasten für schnelle Operationen, soweit sinnvoll
- möglichst wenig UI-Overhead

## Viewport / Camera

- Perspective
- Orthographic
- Front / Back
- Left / Right
- Top / Bottom
- View Snap
- Orbit
- Pan
- Zoom
- Frame Selected / Frame All
- Wireframe / Shaded

## Modeling Core

Geplant bzw. zu untersuchen:

- Extrude
- Inset
- Bevel
- Edge Slide
- Vertex Slide
- Merge / Weld
- Split
- Knife / Cut
- Delete
- Subdivision / Catmull-Clark

## Architekturprinzip

Mesh, Selection, Influence, Viewport/Camera und Modeling Tools sollen getrennte Systeme sein. Transform-Operationen sollen nicht direkt an eine bestimmte UI-Geste gekoppelt sein.

## Nicht Ziel von V1

- vollständige Blender-Alternative
- komplexes Material-/Shader-System
- vollständige Character-Pipeline
- komplette Animation-Suite

Die Architektur soll jedoch spätere Deformation, Morphs, Rigging und Animation ermöglichen, ohne den Mesh-Core neu erfinden zu müssen.
