# References

Gesammelte externe Referenzen für Mirai-Bastel: Modeler, DCC-/3D-Systeme, historische Software, Forschungsprojekte, technische Ansätze, Dokumentationen, Screenshots und eigene Notizen.

Die References sind **Wissens- und Vergleichsmaterial, keine Spezifikation**. Bestehende Lösungen sollen uns helfen, nicht unnötig das Rad neu zu erfinden und gleichzeitig jahrzehntelange Erfahrungswerte aus etablierten Projekten zu berücksichtigen.

## Referenzprinzip

Für interessante Funktionen oder Architekturentscheidungen vergleichen wir nach Möglichkeit mehrere Quellen:

1. **Mirai / Nendo** – historische Bedienphilosophie und Systemideen, soweit rekonstruierbar.
2. **Wings 3D** – besonders wertvoll als Open-Source-Referenz für praktische Polygon-Modeling- und Topologieoperationen.
3. **Andere Open-Source-Modeler und DCC-Systeme** – technische Lösungen, Datenstrukturen und bekannte Randfälle.
4. **Forschung / Experimente / Industrie** – Verfahren aus Deformation, Rigging, UVs, Animation oder prozeduralem Modeling.
5. **Mirai-Bastel** – eigene Anforderungen und Entscheidungen; diese müssen nicht mit einer einzelnen Referenz übereinstimmen.

## Wichtige Regel

Nicht einfach Verhalten kopieren. Bei einer relevanten Funktion fragen wir:

- Wie lösen andere Systeme das Problem?
- Welche Vorteile und bekannten Grenzen hat die jeweilige Lösung?
- Was davon passt zur geplanten Mirai-artigen Bedienung?
- Was muss wegen unseres späteren integrierten Systems anders behandelt werden?

Gerade bei Topologieoperationen ist langfristig wichtig, neben der Mesh-Topologie auch die Auswirkungen auf UVs, Vertex-Attribute, Morph Targets, Rigging und Deformation mitzudenken.

## Modeler

- [Wings 3D](modelers/WINGS3D.md) – Open-Source-Subdivision-Modeler; technische Referenz für Modeling und Topologie.
- [Blender](modelers/BLENDER.md) – moderner Open-Source-DCC; besonders interessant für BMesh, Attribute und die Verbindung von Modeling mit weiteren Geometriedaten.

## Integrierte DCC-Systeme / historische Referenzen

- [Mirai / N-World](integrated_dcc/MIRAI.md) – wichtigste historische Referenz für die angestrebte integrierte Systemphilosophie.
- [Softimage | XSI](integrated_dcc/SOFTIMAGE_XSI.md) – Weight Maps, Operatoren und datengetriebene Deformation.
- [Modo](integrated_dcc/MODO.md) – Vertex Maps, Weight Maps, Morph Maps und persistente Geometriedaten.

## Warum diese Sammlung wichtig ist

Mirai-Bastel soll nicht blind eine einzelne bestehende Software nachbauen. Wir wollen die **Erfahrungen mehrerer Generationen von 3D-Systemen** nutzen:

```text
Mirai / Nendo      ─┐
Wings 3D           ─┤
Softimage / XSI    ─┤
Modo               ─┤──> Erfahrungen / Trade-offs
Blender            ─┤
weitere Systeme    ─┘
                         ↓
                  Mirai-Bastel
```

Dabei interessieren uns nicht nur fertige Features, sondern auch Datenmodelle, gescheiterte Ansätze, Randfälle und die Frage, warum eine Lösung so entworfen wurde.

## Weitere Referenzen

Weitere Einträge werden bei Bedarf ergänzt. Nicht-codebezogene Materialien nur entsprechend den Nutzungsrechten bzw. als Referenz/Link dokumentieren. Bei fremdem Quellcode bevorzugt kleine, gezielt dokumentierte Ausschnitte mit Originalquelle und Lizenzhinweis statt größerer Kopien.
