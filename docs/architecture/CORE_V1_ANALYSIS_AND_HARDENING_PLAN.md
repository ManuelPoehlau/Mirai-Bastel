# Mirai-Bastel Core V1 – Detailanalyse und Hardening-Plan

**Status:** Arbeitsgrundlage vor Produktions-Freeze  
**Scope:** `experiments/mirai_bastel_core_V1` und `src/core`  
**Datum:** 2026-08-26

---

## 1. Zweck dieses Dokuments

Core V1 hat seinen Praxistest bestanden und `src/core` entspricht derzeit der
V1-Implementierung. Bevor der Core jedoch als unveränderliche
Produktionsgrundlage behandelt wird, wird er einmal gezielt gehärtet.

Dabei geht es **nicht** um Core V2 und nicht um das Vorwegnehmen von Rigging,
Skinning, Morphs oder Animation. Ziel ist:

- vorhandene Invarianten explizit zu machen,
- Topologieoperationen gründlicher zu prüfen,
- Identitätskontinuität zu verifizieren,
- Undo/Redo und Serialisierung auf Konsistenz zu prüfen,
- spätere Erweiterbarkeit nicht durch V1-Entscheidungen zu verbauen.

Die V1-Implementierung bleibt als Experiment erhalten und dient als Referenz.
Die Produktionsversion unter `src/core` wird erst nach diesem Hardening-Schritt
als belastbare Basis betrachtet.

---

## 2. Gesamturteil

### Ergebnis

**Kein Rewrite erforderlich.**

Die grundlegenden Architekturentscheidungen sind tragfähig:

1. stabile, typisierte IDs für Vertex/Edge/Face,
2. Mesh-Interna werden über Query-/Mutation-APIs gekapselt,
3. Änderungen laufen über Operations statt über UI-Direktmutationen,
4. History ist vom Mesh entkoppelt,
5. Selection referenziert Elemente über IDs,
6. Scene bildet den übergeordneten Kontext,
7. Serialisierung ist versioniert und erhält ID-Zustände.

Diese Struktur ist insbesondere eine gute Ausgangsbasis für ein späteres
System, in dem Geometrie und darauf bezogene Daten nicht unabhängig
voneinander behandelt werden.

### Aber

Einige Punkte sind für einen Produktions-Freeze noch zu wenig explizit oder
zu schwach abgesichert:

- Topologie-Invarianten,
- genaue Semantik von Split/Collapse/Connect,
- Herkunft bzw. Identitätskontinuität neu erzeugter Elemente,
- Umgang mit abhängigen Daten bei Topologieänderungen,
- langfristige Scene-/Deformationsstruktur,
- Vorwärts-/Rückwärtskompatibilität des Dateiformats.

Diese Punkte sind zunächst **Architektur- und Testthemen**, keine Aufforderung,
jetzt bereits die späteren Systeme zu implementieren.

---

## 3. IDs – tragfähige Grundlage

Der Core verwendet eigene IDs für:

```text
VertexId
EdgeId
FaceId
```

und recycelt IDs innerhalb einer laufenden Session nicht.

Das ist wesentlich besser als eine Identität, die an einen Array-/Listenindex
gebunden ist.

Beispiel:

```text
VertexId(42)
    ↓
Position kann sich ändern
    ↓
Identität bleibt VertexId(42)
```

Dadurch können spätere Systeme prinzipiell Daten an ein konkretes
Geometrieelement binden.

### Bedeutung für die Zukunft

Das ist eine wichtige Voraussetzung für:

- Skin weights,
- Morph-Attribute,
- Vertex Groups,
- andere per-Vertex-Daten,
- spätere Deformationssysteme.

**Bewertung: GRÜN – beibehalten.**

---

## 4. Mesh-Abstraktion – richtige Grenze

Der Mesh-Zustand ist intern organisiert, während andere Systeme über Queries
wie beispielsweise

```text
face_vertices()
face_edges()
edge_faces()
edge_vertices()
vertex_edges()
```

auf die Topologie zugreifen.

Das ist wichtig, weil die interne Repräsentation später geändert werden könnte,
ohne alle Konsumenten umzubauen. Ein möglicher späterer Wechsel der internen
Topologie-Repräsentation (z. B. zu einer Half-Edge-artigen Struktur) muss nicht
heute vorweggenommen werden.

**Bewertung: GRÜN – Architektur beibehalten.**

---

## 5. Topologie-Invarianten – vor Produktions-Freeze härten

Die öffentliche Mutationsebene muss langfristig klare Invarianten garantieren.

Zu prüfen bzw. zu definieren sind insbesondere:

- keine doppelten Vertex-Referenzen innerhalb eines Faces,
- gültige Vertex-/Edge-/Face-Referenzen,
- keine unzulässigen mehrfachen Kantenbeziehungen,
- konsistente Face-/Edge-/Vertex-Adjazenzen,
- keine stale Edge-/Face-Referenzen nach Mutationen,
- klare Regeln für Boundary-Elemente,
- eindeutige Semantik bei degenerierten Fällen.

Die V1-Implementierung verhindert bereits einige ungültige Zustände, aber die
Invarianten sind noch nicht überall gleich streng durchgesetzt.

**Bewertung: GELB – vor Produktions-Freeze testen/härten.**

---

## 6. Split – gute Identitätsrichtung, Herkunft noch offen

Bei einem Edge-Split ist die grundsätzliche Semantik sinnvoll:

```text
alte Edge
    ↓
verschwindet

alte Vertices
    ↓
bleiben erhalten

neuer Vertex
    ↓
neue Identität

neue Edges
    ↓
neue Identitäten
```

Das ist eine gute Grundlage für spätere Datenmigration.

Für einen zukünftigen Remapper wäre jedoch zusätzliche Herkunftsinformation
wertvoll. Konzeptionell könnte eine spätere Operation ausdrücken:

```text
newVertex
    ← entstanden aus
      oldVertexA
      oldVertexB
      Position/Parameter t
```

Ob dies später über Operation-Metadata, einen Änderungsbericht, einen
Herkunftsgraphen oder eine andere Struktur geschieht, ist **noch offen**.

**Bewertung: GRÜN für V1-Semantik, GELB für spätere Remapping-Fähigkeit.**

---

## 7. Collapse – wichtigster Topologie-Prüffall

Beim Edge-Collapse können gleichzeitig verändert werden:

```text
Vertex
Edge
Face
Position
Adjazenz
```

Später möglicherweise zusätzlich:

```text
Skin weights
Morph data
Vertex groups
weitere Attribute
```

Ein typisches V1-Verhalten kann sein:

```text
Vertex A + Vertex B
        ↓
Vertex A überlebt
Vertex B verschwindet
```

Für abhängige Systeme muss irgendwann definiert werden, was mit Daten von B
passiert.

Wichtig: Diese Logik darf **nicht** in die Mesh-Klasse als Skinning-Sonderfall
eingebaut werden. Die Mesh-Operation sollte strukturelle Änderungen und
später ausreichende Änderungsinformationen bereitstellen; spezialisierte
Systeme entscheiden, wie ihre eigenen Daten migriert werden.

**Bewertung: GELB – detailliert testen und Vertrag für Identität/Herkunft
präzisieren.**

---

## 8. Connect – ebenfalls explizit testen

`Connect` verändert Topologie, ohne dass seine Auswirkungen auf abhängige
Daten heute relevant sein müssen.

Vor Produktions-Freeze sollte aber geprüft werden:

- welche IDs erhalten bleiben,
- welche Elemente neu entstehen,
- welche Faces verändert/neu erzeugt werden,
- ob Adjazenz nach der Operation vollständig konsistent ist,
- ob Undo/Redo exakt denselben Zustand wiederherstellt.

**Bewertung: GELB – Hardening-Test erforderlich.**

---

## 9. Operation-Lifecycle – gute Grundlage

Der aktuelle Lebenszyklus ist:

```text
begin()
   ↓
update()*
   ↓
commit()
```

oder:

```text
begin()
   ↓
update()*
   ↓
cancel()
```

Damit können interaktive Werkzeuge viele Zwischenzustände darstellen, ohne
die History mit jedem Mausereignis zu füllen.

Das passt gut zur späteren Trennung:

```text
Input
  ↓
Tool
  ↓
Operation
  ↓
Core
```

**Bewertung: GRÜN – beibehalten.**

---

## 10. MoveOperation – für V1 ausreichend

`MoveOperation` hält Ausgangs-/Endzustände fest und unterstützt Commit,
Cancel, Undo und Redo.

Für die aktuelle V1 ist das angemessen.

Es besteht kein Grund, jetzt bereits einen allgemeinen Transformations-
Framework-Komplex zu bauen.

Spätere Systeme wie Rotate/Scale/Gizmo können auf derselben Operation-Idee
aufbauen.

**Bewertung: GRÜN – keine vorgezogene Erweiterung.**

---

## 11. History – gute Entkopplung

Die History kennt nicht die Details des Meshes. Sie verwaltet lediglich
Commands/Operations mit Undo/Redo-Verhalten.

Das ermöglicht langfristig prinzipiell:

```text
Mesh Operation
Rig Operation
Animation Operation
Material Operation
...
        ↓
     History
```

Eine wichtige Zukunftsanforderung ist jedoch:

> Eine Benutzeraktion, die mehrere abhängige Systeme verändert, muss später
> als eine konsistente Undo-Einheit behandelt werden können.

Beispiel:

```text
Topology Change
    +
Skin Remap
    +
Morph Remap
        ↓
     ein Undo
```

Dafür wird jetzt noch kein Transaction-System implementiert.

**Bewertung: GRÜN für V1, GELB als langfristige Architekturfrage.**

---

## 12. Selection – sauber und unabhängig

Selection referenziert Mesh-Elemente über IDs und kennt die internen
Mesh-Strukturen nicht.

Das ist die richtige Richtung.

Die Trennung zwischen Auswahlzustand und History verhindert außerdem, dass
einfache UI-Auswahlaktionen unnötig den Modeling-Undo-Stack verschmutzen.

Spätere Selection-Arten (Object, Bone, Keyframe usw.) sollen nicht durch
V1 vorschnell vereinheitlicht werden.

**Bewertung: GRÜN.**

---

## 13. Scene – für V1 gut, langfristig bewusst offen

Die Scene bündelt aktuell Mesh, Selection und History und besitzt vorbereitete
Platzhalter für spätere Bereiche wie Morphs, Rig und Animation.

Das ist als V1-Kontext in Ordnung.

Es darf aber nicht automatisch als endgültige Produktionsstruktur interpretiert
werden. Eine spätere Scene könnte beispielsweise eher objekt-/asset-orientiert
werden.

Mögliche zukünftige Struktur:

```text
Scene
 ├── Objects
 │    ├── Geometry
 │    ├── Rig
 │    └── Deformation data
 └── Animation
```

Dies ist eine offene Designfrage.

**Bewertung: GRÜN für V1, GELB für zukünftige Gesamtstruktur.**

---

## 14. Serialisierung – Richtung richtig, V1 bewusst einfach

Positiv:

- Scene wird als Einheit serialisiert,
- Format ist versioniert,
- IDs werden erhalten,
- Allocator-Zustände werden berücksichtigt.

Die aktuelle Versionsbehandlung ist jedoch noch strikt. Eine spätere
Produktionsdatei sollte voraussichtlich ein echtes Migrationskonzept besitzen,
statt alte Versionen einfach abzulehnen.

Noch wichtiger wird die Serialisierung, sobald abhängige Daten existieren:

```text
Mesh
Rig
Skin weights
Morphs
Animation
```

Alle Referenzen müssen dann auf stabile Identitäten und nicht auf zufällige
Container-Indizes zeigen.

**Bewertung: GRÜN für V1, GELB vor dem ersten langlebigen Produktionsformat.**

---

# 15. Zentrale langfristige Architekturidee: Topologie darf Daten nicht blind zerstören

Dies ist eine wichtige Mirai-Leitplanke, die aus der Core-Analyse hervorgeht.

Ein klassisches Problem vieler Modeling-/Skinning-Workflows ist:

```text
Mesh
 ↓
manuelle Skin Weights
 ↓
Topologie ändern
 ↓
Abhängigkeiten passen nicht mehr
```

Das kann bei ungünstigen Topologieänderungen zu beschädigten oder unbrauchbaren
Deformationsergebnissen führen.

Mirai soll langfristig die Möglichkeit bieten, solche abhängigen Daten gezielt
zu erhalten, zu remappen oder zu interpolieren.

Beispiel:

```text
Vertex A                    Vertex B
Weights(A)                  Weights(B)
    \                         /
     \                       /
      └──── neuer Vertex ───┘
                ↓
        interpolierte Weights
```

Bei einem Edge-Split könnte ein zukünftiges System beispielsweise Gewichte
zwischen den Ausgangselementen interpolieren.

Bei einem Collapse könnte es die Daten der zusammengeführten Elemente nach
einer definierten Strategie kombinieren.

### Entscheidender Architekturpunkt

**Mesh darf diese Fachlogik nicht kennen.**

Stattdessen muss der Core langfristig Topologieänderungen so beschreiben können,
dass ein spezialisiertes System daraus seine eigene Migration ableiten kann.

Konzeptionell:

```text
Topology Operation
       ↓
Structural Change Information
       ↓
┌──────┼──────────┐
↓      ↓          ↓
Skin   Morph      other data
```

Ob das später über Change Sets, Operation Metadata, Herkunftsbeziehungen,
Attribute-Systeme oder eine andere Lösung erfolgt, bleibt offen.

**Diese Idee wird ausdrücklich festgehalten, die Implementierung wird vertagt.**

---

# 16. Was NICHT jetzt gebaut wird

Folgende Systeme bleiben außerhalb dieses Hardening-Schritts:

- Skinning
- Bones / Rigging
- Morph Targets
- Deformation Graph
- Weight Remapping
- Attribute-Layer-System
- allgemeines Dependency Graph System
- Animation
- Transform Gizmos
- neue Modeling-Features ohne direkten Hardening-Bedarf

Sie dürfen die Architektur beeinflussen, aber nicht vorzeitig implementiert
werden.

---

# 17. Konkreter Core-Hardening-Plan

## Phase A – Invarianten

Tests und ggf. minimale Validierungsverbesserungen für:

- gültige IDs,
- eindeutige Vertices in Faces,
- konsistente Edges/Faces/Vertices,
- Boundary-Verhalten,
- keine stale Referenzen.

## Phase B – Topologieoperationen

Gezielte Tests für:

```text
split
collapse
connect
```

Jeweils prüfen:

- Vorzustand
- erzeugte IDs
- verschwundene IDs
- erhaltene IDs
- Adjazenz
- Face-/Edge-/Vertex-Konsistenz
- Ergebnisgeometrie

## Phase C – Identitätskontinuität

Explizit testen, dass eine Operation nachvollziehbar macht:

```text
was bleibt?
was stirbt?
was entsteht?
```

Noch ohne allgemeines Herkunftssystem.

## Phase D – History

Für jede relevante Topologieoperation:

```text
operation
 → commit
 → undo
 → Zustand vergleichen
 → redo
 → Zustand vergleichen
```

## Phase E – Serialisierung

Roundtrip-Tests:

```text
Scene
 → save
 → load
 → Zustand vergleichen
```

inklusive IDs und Allocator-Zuständen.

## Phase F – Produktions-Freeze

Erst wenn A–E sauber sind:

```text
Core V1
   ↓
Hardening
   ↓
Produktions-Core-Basis
```

Danach kann der nächste große Schritt die Produktionsarchitektur von Viewport,
Tools und Application konkretisieren.

---

# 18. Entscheidung

Der Core wird **nicht neu geschrieben** und nicht wegen zukünftiger Rigging-/
Skinning-Anforderungen künstlich aufgebläht.

Stattdessen gilt:

> **Stabile Identitäten und nachvollziehbare Topologieänderungen sind eine
> langfristige Architekturvoraussetzung dafür, abhängige geometrische Daten
> später intelligent migrieren zu können.**

Das ist eine Leitplanke für die weitere Entwicklung von Mirai.

Die konkrete Lösung für Skinning-/Morph-Remapping wird erst entworfen, wenn
diese Systeme tatsächlich anstehen.

---

## Status

**Core V1: funktional validiert**  
**Architektur: tragfähig**  
**Produktions-Freeze: nach Core Hardening**  
**Nächster technischer Schritt: Hardening-Tests, keine neuen großen Features**