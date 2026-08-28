# Modo

## Rolle als Referenz

Modo ist für Mirai-Bastel besonders interessant, weil es ein starkes Modeling-System mit einem sehr flexiblen **Vertex-Map-/Weight-Map-Konzept** verbindet. Dadurch können zusätzliche Daten direkt als Werkzeug- oder Deformationssteuerung dienen.

## Quellen

- Foundry Modo SDK/User Guide – Working with Vertex Maps: https://modosdk.foundry.com/modo/14.1/content/help/pages/uving/working_with_vmaps.html
- Foundry Modo – Procedural Vertex Maps: https://modosdk.foundry.com/modo/14.1/content/help/pages/uving/procedural_vmaps.html
- Foundry Modo – Vertex Map Weight Tool: https://modosdk.foundry.com/modo/content/help/pages/uving/weight_tool.html

## Interessante Erkenntnisse

### Vertex Maps als allgemeine Geometriedaten

Modo beschreibt Vertex Maps als Möglichkeit, vertex-spezifische Informationen im Modell zu speichern. Neben Weight Maps existieren u. a. UV Maps, Morph Maps, Farbwerte, Normaldaten und Auswahl-/Pick Maps.

Das ist für unsere Architekturfrage sehr interessant: Viele scheinbar unterschiedliche Systeme können auf einem gemeinsamen Konzept von **benannten, typisierten Geometriedaten** aufbauen.

### Weight Maps

Weight Maps speichern Gewichtswerte und können unter anderem Tool-Effekte über Falloffs steuern, Deformer beeinflussen, Subdivision Creases kontrollieren oder als Masken für andere Systeme dienen.

### Morph Maps

Modo unterscheidet relative und absolute Morph Maps. Besonders interessant ist die dokumentierte Aussage, dass Topologieänderungen auf die zugehörigen Morph Maps angewendet werden können. Das ist ein konkretes Beispiel dafür, dass Topologieoperationen und zusätzliche Geometriedaten nicht völlig unabhängig voneinander behandelt werden können.

### Auswahl als Daten

Pick Maps bzw. Edge Pick Maps zeigen noch einen weiteren interessanten Ansatz: Eine Auswahl kann als benannter Datensatz erhalten bleiben und später wieder verwendet werden, statt nur ein flüchtiger UI-Zustand zu sein.

## Relevanz für Mirai-Bastel

Modo liefert mehrere Ideen, die wir langfristig getrennt betrachten sollten:

1. Benannte Geometrie-Attribute
2. Unterschiedliche Datentypen auf ähnlicher Infrastruktur
3. Weight/Mask-Daten als Eingabe für Werkzeuge und Deformer
4. Morph-Daten als Teil des Modells
5. Persistente Selection Sets

Das passt gut zu einem System, in dem Modeling, UV, Morphing und Deformation nicht zwingend als lineare Pipeline behandelt werden.

## Zu untersuchen

- Wie Modo Vertex Maps intern unterscheidet und speichert
- Wie Topologieänderungen Morph Maps übertragen
- Selection/Pick Maps als persistente Daten
- Weight Maps als Tool-/Falloff-Daten
- Welche minimale Variante davon in Mirai-Bastel sinnvoll wäre

## Abgrenzung

Modo ist keine Zielarchitektur. Wir übernehmen nur Konzepte, die zu einem schlanken Core passen.
