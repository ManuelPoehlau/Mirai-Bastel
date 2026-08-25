# Mirai-Bastel V1 – Spezifikation

## 0. Einordnung: V1 ist nicht das Gesamtsystem

V1 baut bewusst **einen Modeler**. Der Modeler ist aber nur die erste praktische Säule eines wesentlich größeren, langfristig wachsenden Systems.

Das Ziel ist kein „kleiner Blender“, der irgendwann mit immer mehr Funktionen aufgebläht wird. Wir bauen einen eigenständigen Core/Scene-Unterbau, in dem Modeling der erste vollständig nutzbare Bereich ist und später weitere Systeme organisch hinzukommen können.

```text
Gesamtsystem / Scene Core
│
├── Modeling / Mesh              ← V1
├── Selection / Interaction      ← V1
├── Viewport / Camera            ← V1
├── History                      ← V1
│
├── Deformation / Skinning       ← später
├── Morph Targets                ← später
├── Rigging / Skeleton           ← später
├── Animation                    ← später
├── Materials / Shading          ← später
├── Scripting / Extensions       ← später
└── AI-assisted Workflows        ← später
```

Die Versionen V1, V2, V3 usw. sind daher **Meilensteine eines einzigen Systems**, keine voneinander unabhängigen Produkte. Es gibt bewusst keinen Punkt, an dem das Projekt endgültig „fertig“ ist.

### Leitprinzip

> **Implementiere wenig – berücksichtige viel.**
>
> Wir bauen in V1 nur, was wir tatsächlich benötigen. Bekannte zukünftige Anforderungen dürfen aber nicht durch unnötig enge Architekturgrenzen verbaut werden.

Das ist besonders wichtig für die geplante Arbeitsweise mit mehreren Menschen und KI-Systemen: Die langfristige Vision muss aus den technischen Dokumenten jederzeit eindeutig hervorgehen, damit spätere Arbeit nicht unbemerkt auf das falsche Ziel optimiert wird.

---

## 1. V1-Ziel

V1 soll ein kleiner, direkter Polygon-/Subdivision-Modeler werden. Das Bediengefühl soll sich eher wie ein schneller Modeler à la **Mirai / Nendo / Silo / Wings3D** anfühlen als wie eine reduzierte Blender-Oberfläche.

Die historische Inspiration ist dabei vor allem das direkte, kontinuierliche Arbeiten: Hover → Auswahl → Manipulation → Ergebnis sehen → weiterarbeiten.

V1 ist **kein Versuch, Mirai technisch nachzubauen**. Die historischen Systeme dienen als Referenz für Interaktion, Workflow und Architekturideen. Die Implementierung darf und soll moderne Technik nutzen.

---

## 2. Selection Modes

- `1` Vertex
- `2` Edge
- `3` Face
- `4` Object

Soft Selection ist **kein eigener Selection Mode**, sondern ein unabhängiges Verhalten. Eine Vertex-Auswahl mit aktivierter Soft Selection kann dadurch bereits das Verhalten einer erweiterten lokalen Auswahl erreichen, ohne einen zusätzlichen Selection Mode zu benötigen.

---

## 3. Selection

- Hover Highlight
- Single Select
- Multi Select
- Add/Remove Selection
- Soft Selection
- Falloff / Influence Radius
- später: Loop / Ring / Grow / Shrink

Selection ist konzeptionell **eigener Domain-State** und nicht identisch mit Mesh-Mutation. V1 selektiert V/E/F; spätere Systeme werden möglicherweise andere Objekte auswählen können (z. B. Bones, Keyframes oder Morph Channels).

Selektionsänderungen gehören in V1 **nicht zum normalen Modeling-Undo-Stack**. Ein Klick soll keinen Modeling-Undo-Schritt verbrauchen.

---

## 4. Transform

- Translate
- Rotate
- Uniform Scale
- Scale entlang X/Y/Z
- Achsen-Constraints
- Selection Pivot / Center

Transform-Operationen werden nicht dauerhaft an eine bestimmte UI-Geste gekoppelt.

Interaktive Operationen verwenden grundsätzlich einen generischen Lifecycle:

```text
begin()
   ↓
update()   ← beliebig oft während Drag
   ↓
commit()
```

oder bei Abbruch:

```text
begin() → update() → cancel()
```

Dabei gilt:

- `begin()` erfasst den Ausgangszustand.
- `update()` verändert den Live-Zustand, erzeugt aber keine History-Einträge.
- `commit()` erzeugt genau **einen** logischen History-Schritt.
- `cancel()` stellt den Ausgangszustand wieder her und erzeugt keinen History-Schritt.

Dieser Lifecycle darf nicht unnötig Mesh-spezifisch sein. Spätere interaktive Rig-, Pose- oder Animationsoperationen sollen dasselbe Grundprinzip verwenden können.

---

## 5. Interaction

- direkter Tweak-Modus
- kontextabhängige Mausinteraktion
- Modifier-Tasten für schnelle Operationen, soweit sinnvoll
- möglichst wenig UI-Overhead
- Hover als wichtiger Bestandteil der Interaktion

Tweak ist nicht bloß ein weiteres Tool auf einer langen Liste. Das **direkte Manipulationsgefühl** ist ein zentraler Teil der historischen Mirai/Nendo-Inspiration und damit ein wichtiger UX-Schwerpunkt des Projekts.

Die konkreten Tastatur-/Mausbelegungen dürfen während der Entwicklung verändert werden. Entscheidend ist der Interaktionsvertrag, nicht eine frühzeitig eingefrorene Shortcut-Tabelle.

---

## 6. Viewport / Camera

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

Kamera und Navigation sind ein eigenständiger Bestandteil des Viewport-/Scene-Systems und dürfen nicht mit Mesh-Topologie vermischt werden.

---

## 7. Modeling Core

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

Die konkrete Reihenfolge richtet sich nach den tatsächlich benötigten Workflows. Nicht jede hier genannte Funktion muss bereits in der ersten funktionsfähigen V1-Demo vorhanden sein.

### Topologie-Grenze

High-Level-Modeling-Operationen sollen Mesh-Internals nicht beliebig direkt verändern. Topologieänderungen laufen über einen kleinen, kontrollierten Mutation-Layer mit primitiven Operationen wie:

```text
add_vertex()
add_face()
remove_face()
split_edge()
collapse_edge()
connect_vertices()
```

Die genaue Primitive-Liste darf mit den realen Operationen wachsen.

V1 benötigt **keine vollständige Half-Edge-/Winged-Edge-Implementierung**. Wichtig ist zunächst:

- Face-Boundaries sind geordnet.
- Topologie wird über stabile Query-Funktionen abgefragt.
- Interne Container sind kein öffentlicher Vertrag.

Beispielsweise:

```text
face_vertices(face_id)
face_edges(face_id)
edge_faces(edge_id)
vertex_edges(vertex_id)
```

Dadurch kann eine spätere Implementierung intern auf Half-Edge-Navigation umgestellt werden, ohne sämtliche Modeling-Operationen neu schreiben zu müssen.

---

## 8. Stable IDs

Vertices, Edges und Faces erhalten **opake, stabile IDs**.

Für V1 genügt:

- monotoner Counter
- IDs werden während einer Session niemals wiederverwendet
- ID ist kein Speicher-/Array-Index
- Gültigkeit kann geprüft werden
- IDs werden serialisiert

Eine Generational-Slotmap, ECS-Struktur oder eigener Allocator wird **nicht** vorzeitig gebaut. Diese Dinge sind mögliche spätere Implementierungsoptimierungen, keine V1-Anforderungen.

Wichtig ist außerdem die **ID-Kontinuität von Topologieoperationen**. Jede Mutation muss dokumentieren, welche IDs erhalten bleiben, welche ungültig werden und welche neu entstehen. Das schafft bereits in V1 die Grundlage für spätere Systeme wie Skin-Weight- oder Morph-Remapping.

Ein solches Remapping-System selbst ist ausdrücklich **nicht Teil von V1**.

---

## 9. Position und zukünftige Deformation

V1 arbeitet mit einfachen Basis-Vertexpositionen.

Andere Teile des Programms sollen Positionen jedoch nicht unnötig direkt aus internen Datenfeldern lesen/schreiben, sondern über die Mesh-/Domain-API zugreifen.

Damit bleibt konzeptionell Raum für eine spätere Kette wie:

```text
Base Mesh
   ↓
Morph Targets
   ↓
Skin / Deformation
   ↓
Subdivision / Derived Surface
   ↓
Viewport
```

Diese Systeme werden **nicht** in V1 implementiert. V1 darf aber keine Architektur erzwingen, in der die aktuell gespeicherte Vertexposition für alle Zeiten automatisch mit der final angezeigten Position gleichgesetzt wird.

Das ist besonders relevant für das langfristige Ziel eines Workflows wie:

```text
Model → Rig → Deformation testen
       ↓
zurück zum Modeling
       ↓
Mesh weiterbearbeiten
       ↓
Rig / Animation weiterverwenden
```

Wie weit ein späteres System beliebige Topologieänderungen mit bestehenden Morphs und Skin-Weights automatisch erhalten kann, ist ein eigenes technisches Problem und wird nicht durch stabile IDs allein gelöst.

---

## 10. History

History ist konzeptionell ein **generischer Command-/Reversible-Action-Stack**, nicht einfach ein Mesh-Diff-Stack.

V1 wird hauptsächlich Modeling-Commands enthalten. Der History-Vertrag soll jedoch grundsätzlich etwas wie:

```text
undo()
redo()
```

für reversible Aktionen beschreiben, statt eine harte Abhängigkeit auf `MeshOperation` einzubauen.

So kann später grundsätzlich auch eine Rig-, Pose- oder Animationsaktion in dieselbe Core-Architektur integriert werden.

Keine V1-Anforderungen:

- verzweigte History-Bäume
- kollaboratives Merging
- OT/CRDT
- komplexe Cross-Subsystem-Transaktionen

---

## 11. Subdivision

V1 enthält Subdivision / Catmull-Clark als Modeling-/Viewport-Funktion.

Wichtig ist die Trennung:

```text
Control Mesh
     ↓
Derived / Subdivided Surface
     ↓
Viewport
```

Die abgeleitete Oberfläche ersetzt niemals das editierbare Control Mesh.

---

## 12. Scene / Serialization

Auch wenn V1 im Wesentlichen einen Modeler speichert, soll die Dateiarchitektur **nicht so tun, als wäre das Mesh das endgültige Gesamtsystem**.

Konzeptionell:

```json
{
  "version": 1,
  "mesh": { },
  "morph_targets": null,
  "rig": null,
  "animation": null
}
```

Die konkrete Serialisierung darf für V1 einfach bleiben. Keine vorgezogene Migrations-Engine, kein Plugin-Serialisierungsframework.

Die Scene/Core-Struktur soll jedoch von Anfang an Platz für mehrere zukünftige Subsysteme lassen.

---

## 13. Extensibility / Scripting

Langfristig soll das System flexibel, scriptbar, erweiterbar und von Menschen **und KI** weiterentwickelbar sein.

V1 braucht dafür noch kein großes Plugin-System.

Für den Anfang genügen:

- normale Python-Module
- explizite Registrierung
- klare Domain-/Operation-APIs

Nicht V1:

- Plugin-Discovery-System
- Manifest-/Dependency-System
- versioniertes Plugin-ABI
- komplexe Extension-Laufzeit

Wir vermeiden bewusst, eine vermeintlich allgemeine API zu bauen, bevor mehrere reale Extensions gezeigt haben, dass dieselbe Abstraktion tatsächlich gebraucht wird.

---

## 14. AI als zukünftiger Bestandteil

KI ist **kein V1-Feature**, aber ein wichtiger Teil der langfristigen Vision.

Das System soll später so strukturiert und inspizierbar sein, dass unterschiedliche KI-Systeme damit arbeiten können, ohne dass das Projekt seine Unabhängigkeit von einer bestimmten KI verliert.

Dafür sind insbesondere wichtig:

- stabile IDs
- explizite Domain-Objekte
- nachvollziehbare Operationen
- generische History
- Scene-Struktur
- scriptbare APIs
- klare Dokumentation

Die Vision ist kein "AI-Plugin", sondern ein lebendiges System, das parallel von Menschen und verschiedenen KI-Agenten verstanden, erweitert und untersucht werden kann.

Eine konkrete AI-API wird erst entworfen, wenn reale Use Cases dafür vorhanden sind.

---

## 15. Architekturprinzip

Mesh, Selection, Influence, Viewport/Camera und Modeling Tools sollen getrennte Systeme sein.

Zusätzlich gelten für V1 folgende Grenzen:

1. **Keine direkte Abhängigkeit von internen Mesh-Containern.**
2. **Keine Wiederverwendung gelöschter Element-IDs.**
3. **ID-Kontinuität jeder Topologie-Mutation dokumentieren.**
4. **Operation-Lifecycle generisch halten.**
5. **History nicht als Mesh-spezifische Architektur definieren.**
6. **Selection nicht unnötig als Mesh-only-Konzept verankern.**
7. **Scene/Serialization nicht als reines Mesh-Dateiformat konzipieren.**
8. **Bekannte zukünftige Anforderungen berücksichtigen, ohne deren vollständige Systeme vorzeitig zu bauen.**

---

## 16. Nicht Ziel von V1

- vollständige Blender-Alternative
- komplexes Material-/Shader-System
- vollständige Character-Pipeline
- komplette Animation-Suite
- Produktionsrenderer
- vollständiges Rigging
- Skinning / Deformation
- Morph-System
- umfangreiches Plugin-Framework
- AI-API
- Kollaboration
- vorzeitige Performance-Frameworks

**Aber:** Diese Punkte sind nicht aus der Vision gestrichen. Sie gehören zu möglichen späteren Säulen desselben Systems.

---

## 17. V1-Erfolgskriterium

V1 ist nicht dann erfolgreich, wenn möglichst viele Modeling-Tools vorhanden sind.

V1 ist erfolgreich, wenn sich ein einfaches Mesh **direkt, schnell und intuitiv** bearbeiten lässt und der Core gleichzeitig eine saubere Grundlage für das geplante größere System bildet.

Der wichtigste Test ist daher nicht:

> „Wie viele Features haben wir?“

sondern:

> **„Fühlt sich das Modellieren direkt und lebendig an – und können wir darauf aufbauen, ohne den Core später wegzuwerfen?“**

---

## 18. Bezug zur historischen Forschung

Das Projekt ist von Mirai/Nendo/N-World und verwandten historischen Workflows inspiriert, ist aber **keine reine Rekonstruktion**.

Die Recherche soll systematisch herausarbeiten:

- welche Interaktionsparadigmen tatsächlich verwendet wurden
- wie Selection und Mouse Interaction funktionierten
- wie Modeling und Topology organisiert waren
- wie Camera und Viewport arbeiteten
- wie SubD, Morphs, Rigging und Animation zusammenspielten
- welche History-/Editor-Systeme die Flexibilität ermöglichten
- welche Teile davon produktionsspezifische Erweiterungen bei Weta waren
- was heutige Technik besser lösen kann
- welche historische Ideen in modernen Komplettpaketen verloren gegangen sind

Die historische Recherche dient damit nicht nur als Inspiration für einen Modeler, sondern als **Archäologie der Architekturidee hinter dem Gesamtsystem**.

---

## 19. Leitgedanke

> **Der V1-Modeler ist der erste Stein – nicht das ganze Gebäude.**
>
> Wir bauen ihn klein genug, um ihn fertigzustellen, aber wir formen seine Schnittstellen so, dass das Gebäude später weiterwachsen kann.
