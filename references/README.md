# References

Gesammelte externe Referenzen für Mirai-Bastel: Modeler, DCC-/3D-Systeme, Forschungsprojekte, technische Ansätze, Dokumentationen, Screenshots und eigene Notizen.

Die References sind **Wissens- und Vergleichsmaterial, keine Spezifikation**. Bestehende Lösungen sollen uns helfen, nicht unnötig das Rad neu zu erfinden und gleichzeitig jahrzehntelange Erfahrungswerte aus etablierten Projekten zu berücksichtigen.

## Referenzprinzip

Für interessante Funktionen oder Architekturentscheidungen vergleichen wir nach Möglichkeit mehrere Quellen:

1. **Mirai / Nendo** – historische Bedienphilosophie und Systemideen, soweit rekonstruierbar.
2. **Wings 3D** – besonders wertvoll als Open-Source-Referenz für praktische Polygon-Modeling- und Topologieoperationen.
3. **Andere Open-Source-Modeler und DCC-Systeme** – technische Lösungen, Datenstrukturen und bekannte Randfälle.
4. **Forschung / Experimente / Industrie** – z. B. Verfahren aus Deformation, Rigging, UVs, Animation oder prozeduralem Modeling.
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

## Weitere Referenzen

Weitere Einträge werden bei Bedarf ergänzt. Nicht-codebezogene Materialien nur entsprechend den Nutzungsrechten bzw. als Referenz/Link dokumentieren.
