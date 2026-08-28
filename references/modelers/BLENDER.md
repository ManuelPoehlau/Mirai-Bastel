# Blender

## Rolle als Referenz

Blender ist für Mirai-Bastel vor allem als **modernes, integriertes Geometrie- und Attributsystem** interessant. Es ist nicht nur eine Modeling-Referenz: Mesh-Topologie, UVs, Vertex Groups, Shape Keys, Custom Attributes, Deformation, Geometry Nodes und Animation arbeiten auf bzw. mit gemeinsamen Geometriedaten.

## Primärquellen

- Source Repository: https://github.com/blender/blender
- BMesh source / data model: https://github.com/blender/blender/tree/main/source/blender/bmesh
- BMesh class: https://github.com/blender/blender/blob/main/source/blender/bmesh/bmesh_class.hh
- Blender developer docs – Attributes: https://developer.blender.org/docs/features/objects/attributes/
- Blender Manual – Object Data: https://docs.blender.org/manual/en/latest/modeling/meshes/properties/object_data.html
- Blender Manual – Attribute Domains: https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/attributes_reference.html

## Interessante Erkenntnisse

### BMesh als Edit-/Topologie-Repräsentation

BMesh ist ausdrücklich als Boundary-Representation für fortgeschrittene Editing-Operationen ausgelegt. Die zentrale Struktur kennt Vertices, Edges, Loops und Faces und hält Connectivity-Informationen bereit.

Das ist für Mirai-Bastel interessant, weil unsere Topologieoperationen ebenfalls nicht nur mit flachen Listen arbeiten sollten, sondern Nachbarschaft und lokale Topologie direkt abfragen können.

### Custom Data / Attribute Layers

Blender hängt Daten nicht nur an Vertices. Im aktuellen System gibt es Attribute-Domains wie Point, Edge, Face und Face Corner. UV-Daten sind beispielsweise Corner-Daten. Das erlaubt, Daten dort zu speichern, wo ihre Semantik tatsächlich liegt.

Der BMesh-Code besitzt entsprechende CustomData-Layer für Vertex-, Edge-, Face- und Loop/Corner-Daten.

### Topologieänderung + Daten

Für Mirai-Bastel besonders relevant: Eine Topologieoperation ist langfristig nicht nur eine Änderung von Positionen und Connectivity. Beim Splitten, Mergen oder Löschen von Elementen müssen auch zusätzliche Daten sinnvoll behandelt werden. Blender besitzt dafür ein allgemeines CustomData-/Attribute-System und verarbeitet unter anderem Shape Keys separat.

### Attribute statt fester Spezialfälle

Blenders modernes Attributsystem ist bewusst generisch: Datentyp und Domain sind getrennt von der konkreten Verwendung. Dadurch können dieselben Grundmechanismen für viele unterschiedliche Zwecke verwendet werden.

## Relevanz für Mirai-Bastel

Wir sollten nicht versuchen, Blenders gesamtes Attributsystem nachzubauen. Interessant ist das **Prinzip**:

> Geometrie ist Topologie plus zusätzliche Daten, und diese Daten besitzen eine definierte Domain und Lebenszyklus-/Transfer-Semantik.

Das passt zu unserem langfristigen Ziel eines integrierten Systems wesentlich besser als eine Pipeline, in der UV, Rigging, Morphs und Animation völlig getrennte Asset-Stufen sind.

## Zu untersuchen

- Wie Blender Connect/Bridge/Loop Cut intern organisiert
- Wie BMesh Topologieänderungen und CustomData-Layer propagiert
- Shape-Key-Verhalten bei Topologieänderungen
- Attribute-Interpolation beim Wechsel zwischen Domains
- Welche Teile davon für einen schlanken Mirai-Core sinnvoll wären

## Notiz

Blender ist eine Referenz für moderne Lösungen, aber wegen seines sehr großen Funktionsumfangs **keine Zielarchitektur** für Mirai-Bastel.
