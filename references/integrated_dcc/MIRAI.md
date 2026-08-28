# Mirai / N-World

## Rolle als Referenz

Mirai ist die wichtigste **historische Systemreferenz** für das Projekt. Gleichzeitig ist die öffentlich verfügbare technische Dokumentation deutlich schlechter als bei modernen Open-Source-Projekten. Aussagen über konkrete interne Mechanismen müssen deshalb sauber von belegten Informationen und Rekonstruktionen getrennt werden.

## Quellen

- Mirai software overview / history: https://en.wikipedia.org/wiki/Mirai_(software)
- Historical S-Graphics / N-World / Mirai material: https://s-graphics.neocities.org/
- Wings 3D source repository, explicitly describing its Nendo/Mirai inspiration: https://github.com/dgud/wings
- Historical discussion / archived Mirai material: https://blenderartists.org/t/izware-s-mirai-is-back/316000
- Historical Mirai/N-World discussion and archives: https://www.reddit.com/r/lisp/comments/1iqeg1v/back_again_now_for_the_classic_3d_nworld_software/

## Was derzeit relativ gut belegt ist

### Winged-Edge / Topologie

Mirai wird als 3D-Creation-/Editing-Suite beschrieben, deren Modeler eine Winged-Edge-Datenstruktur verwendet. Wings 3D entstand später ausdrücklich unter dem Einfluss von Nendo und Mirai und ist deshalb eine besonders nützliche Open-Source-Referenz für die Modeling-Seite.

### Integriertes System statt reiner Modeler

Historische Beschreibungen ordnen Mirai nicht nur als Polygon-Modeler ein. Mirai entwickelte sich aus der S-Graphics/N-World-Linie und wurde für Character Animation und Game Development eingesetzt. Quellen nennen unter anderem Animation, inverse Kinematics und Motion-Editing-Funktionen.

Ein historischer Erfahrungsbericht beschreibt Mirai als Umgebung, in der Modellierung, 3D-Painting, UV-Arbeit und Animation sehr eng zusammenarbeiten konnten. Solche Erfahrungsberichte sind nützlich als Hinweise auf die Workflow-Philosophie, aber nicht als Beweis für konkrete interne Datenstrukturen.

### Character / Morphing

Mirai ist besonders mit hochwertigem Character Modeling und Morph Targets verbunden. Ein häufig genannter historischer Einsatz ist Bay Raitts Facial Modeling für Gollum in der Herr-der-Ringe-Trilogie.

## Wichtige offene Fragen

Wir sollten derzeit **nicht behaupten**, dass Mirai intern exakt dasselbe Weight-Map-/Attribute-System wie XSI, Modo oder Blender verwendet hat. Dafür fehlen uns belastbare öffentliche technische Quellen.

Gezielt weiter recherchieren:

- Welche Datenstruktur Mirai für UVs verwendete
- Wie Morph Targets intern an Geometrie gebunden waren
- Ob und wie Weight Maps / Deformation Weights als allgemeine Attribute verwendet wurden
- Wie Topologieänderungen auf Morph-/Rigging-/UV-Daten wirkten
- Ob Mirai ein allgemeines Attributkonzept hatte oder mehrere spezialisierte Datensysteme
- Welche Teile aus N-World/S-Graphics übernommen oder neu entwickelt wurden

## Relevanz für Mirai-Bastel

Mirai ist vor allem Referenz für die **Systemidee**:

> Modeling sollte nicht zwangsläufig das erste Stadium einer linearen Pipeline sein, nach dem Geometrie an getrennte UV-, Rigging-, Skinning- und Animationsprogramme weitergereicht wird.

Für Mirai-Bastel bedeutet das nicht, dass alle Systeme sofort gebaut werden müssen. Der Core soll aber möglichst vermeiden, eine spätere integrierte Nutzung von Geometrie, Attributen, Morphs und Deformation grundsätzlich auszuschließen.

## Quellenkritik

Historische Mirai-Informationen sind teilweise nur noch über alte Foren, archivierte Websites, Videos und Erfahrungsberichte verfügbar. Jede konkrete technische Behauptung sollte deshalb nach Möglichkeit durch mehrere unabhängige Quellen oder später durch erhaltene Dokumentation/Software verifiziert werden.
