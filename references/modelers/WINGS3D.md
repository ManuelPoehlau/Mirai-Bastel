# Wings 3D

## Rolle als Referenz

Wings 3D ist für Mirai-Bastel eine wichtige technische Referenz für polygonales Modeling, Topologie-Operationen und die Bedienphilosophie eines schlanken Modelers.

Wings 3D wurde ursprünglich von Nendo und Mirai inspiriert und wird seit 2001 als Open-Source-Projekt weiterentwickelt. Das Projekt verwendet eine Winged-Edge-Datenstruktur für die Nachbarschaftsbeziehungen zwischen Vertices, Edges und Faces.

## Quellen

- Repository: https://github.com/dgud/wings
- Projektseite: https://www.wings3d.com/

## Was wir untersuchen können

- Selection Modes und kontextabhängige Modeling-Operationen
- Edge Loop / Edge Ring Detection und Traversal
- Edge Connect / Vertex Connect
- Loop Cut / Insert und Dissolve
- Topologie-Datenmodell und Nachbarschaftsabfragen
- Undo/Redo und Transaktionsverhalten von Topologieoperationen
- Umgang mit Boundary-, Pole- und Sonderfällen
- UV- und Attributbehandlung bei Topologieänderungen
- Quellcode als technische Referenz für bewährte Lösungen und Randfälle

## Abgrenzung

Wings 3D ist eine Referenz, keine Spezifikation für Mirai-Bastel. Verhalten wird nicht automatisch übernommen. Für jede relevante Funktion wird geprüft:

1. Wie löst Wings das Problem?
2. Wie wurde es in Mirai/Nendo möglicherweise gelöst?
3. Welche Anforderungen ergeben sich aus unserem geplanten integrierten System?
4. Was davon ist für Mirai-Bastel sinnvoll?

Besonders wichtig ist die spätere Trennung zwischen reiner Topologieänderung und der Übertragung zusätzlicher Daten wie UVs, Vertex-Attribute, Morph- und Deformationsdaten.
