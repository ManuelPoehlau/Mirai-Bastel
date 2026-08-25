# Research Sources

Dieses Dokument ist der zentrale Index für Quellen, die für Mirai-Bastel besonders wertvoll sind.

**Priorität:** Primärquellen > zeitgenössische technische Quellen > Sekundärquellen.

Bei jeder Quelle versuchen wir zu unterscheiden zwischen **Fakt**, **Beobachtung**, **Interpretation** und **offener Hypothese**.

## 1. Historische Mirai / N-World Quellen

### Symbolics S-Graphics / Nichimen N-World / Izware Mirai Information Site

- URL: https://s-graphics.neocities.org/
- Typ: historische Dokumentations-/Archivseite
- Wert: **sehr hoch**
- Enthält u.a. einen direkten Verweis auf die **N-World 3.0 Online-Dokumentation** und Hinweise zur Entwicklung von S-Graphics über N-World zu Mirai.
- Besonders interessant: Die Seite beschreibt, dass S-Graphics nach der Übernahme durch Nichimen auf Allegro Common Lisp für IRIX und Windows NT portiert wurde.

### N-World 3.0 Online Documentation

- Einstieg: https://s-graphics.neocities.org/
- Typ: **Primär-/zeitgenössische Dokumentation**
- Wert: **Goldquelle – vorrangig sichern und auswerten**
- Ziel der Recherche: tatsächliche Selection-, Modeling-, Camera-, Animation- und UI-Konzepte ermitteln, statt sie aus Erinnerungen zu rekonstruieren.

### Nichimen N-World 3.2 – Internet Archive

- URL: https://archive.org/details/nichimen-n-world-3.2
- Typ: historische Software-Archivierung
- Wert: **sehr hoch**
- Wichtig, weil N-World der direkte Vorgänger von Mirai ist und möglicherweise als praktische Referenz/Experimentierumgebung dienen kann.
- Nicht automatisch als technische Primärquelle interpretieren; die archivierte Software selbst ist jedoch eine wichtige historische Referenz.

### Nichimen Mirai 1.1a – Internet Archive

- URL: https://archive.org/details/nichimen-mirai-1.1a-portable
- Typ: historische Software-Archivierung
- Wert: **sehr hoch**
- Die Existenz archivierter Mirai-Versionen eröffnet die Möglichkeit, das tatsächliche Programmverhalten später direkt zu untersuchen.

## 2. Bay Raitt

### Bay Raitt – Professional Profile

- URL: https://www.linkedin.com/in/bay-raitt-2204161/
- Typ: Primärquelle / persönliche berufliche Beschreibung
- Wert: **sehr hoch**
- Bay Raitt beschreibt Mirai als 3D-Creation-/Editing-Suite in Common Lisp und nennt ausdrücklich die **Winged Edge data structure** sowie die Abstammung von Symbolics S-Geometry.
- Er beschreibt außerdem seine Arbeit an den Gollum-Facial-Morph-Targets.

### Bay Raitt – ArtStation

- URL: https://spiraloid.artstation.com/projects/o693m
- Typ: Primärquelle / persönlicher Projektbericht
- Wert: **sehr hoch**
- Besonders relevant für die spätere Deformations-/Morph-Recherche: Beschreibung der Arbeit an einem umfangreichen kombinatorischen Shape-Netzwerk für Gollum.

## 3. Zeitgenössische Fachpresse

### Game Developer Magazine – Nichimen's Mirai, December 1999

- PDF: https://valvearchive.com/archive/Other%20Files/Publications/The%20Cabal%20%28Ken%20Birdwell%29/The%20Cabal%20%28Valve%27s%20Design%20Process%20For%20Creating%20Half-Life%29/Game%20Developer%20Magazine/GDM_December_1999.pdf
- Typ: zeitgenössischer Fachartikel / Produktreview
- Wert: **sehr hoch**
- Besonders wertvoll: beschreibt Mirai als eine Art **„3D operating system“**, in dem mehrere Editoren dynamisch miteinander verbunden sind; Auswahl und Kontext bestimmen stark, welche Aktionen verfügbar sind.
- Beschreibt außerdem die zentrale Rolle von Left/Middle/Right Mouse, Sequenz und Kontext sowie die bewusst minimale Oberfläche.
- Das ist eine wichtige unabhängige zeitgenössische Quelle für genau das Interaktionsmodell, das uns an Mirai fasziniert.

### Game Developer Magazine – Mirai 1.1, April 2000

- PDF: https://ubm-twvideo01.s3.amazonaws.com/o1/vault/GD_Mag_Archives/GDM_April_2000.pdf
- Typ: zeitgenössischer Fachartikel
- Wert: **hoch**
- Besonders interessant: nennt Verbesserungen bei Camera Manipulation sowie **Magnet Move**, mit dem mehrere Vertices entlang von Normalen mit Falloff bewegt werden können.
- Damit haben wir eine zeitgenössische Quelle für ein Verhalten, das konzeptionell sehr nah an unserer Soft-Selection-Idee liegt.

### GameSpot – Nichimen Introduces New Animation Tool, 2000

- URL: https://www.gamespot.com/articles/nichimen-introduces-new-animation-tool/1100-2451979/
- Typ: zeitgenössische Pressemitteilung / Berichterstattung
- Wert: **hoch**
- Beschreibt Mirai als nächste Generation von N-World und nennt u.a. dynamisch verknüpfte Editoren, Animation, Morphing, skeletal IK und biomechanische Motion Editing Tools.

## 4. Wings3D / Nendo als direkte Nachfahren

### Wings3D User Manual 1.6.1

- PDF: https://www.cs.usfca.edu/~wells/3DCG/Model-Render%20stuff/Wings%20stuff/wings3d_manual1.6.1.pdf
- Typ: zeitgenössische Produktdokumentation
- Wert: **sehr hoch**
- Besonders wichtig, weil das Manual ausdrücklich sagt, dass **Nendo die Inspiration für Wings** war.
- Enthält konkrete Informationen zu Selection, Modeling, Tweak, Navigation und Hotkeys.

### Wings3D offizielle Dokumentation – Hotkeys

- URL: https://www.wings3d.com/documentation/user-manual-table-of-contents/hotkey-assignments/
- Typ: offizielle Dokumentation
- Wert: **hoch**
- Nützlich als moderne, nachvollziehbare Referenz für die aus der Nendo/Mirai-Linie überlieferten direkten Modeling-Interaktionen.

## 5. Historische Community-/Beobachtungsquellen

### Mirai/Nendo Thread – XPForums

- URL: https://www.xpforums.com/threads/the-official-nichimen-mirai-thread-nendo-too.935716/
- Typ: Community / Anwenderbericht
- Wert: **mittel – Hinweise, keine Primärquelle**
- Interessant für konkrete Erinnerungen an Mirai-Workflow, Kontextoperationen und „volume modeling“.
- Aussagen müssen mit Manuals, Videos oder tatsächlicher Software verifiziert werden.

### Working with Edges in Houdini – od|force

- URL: https://forums.odforce.net/topic/1052-working-with-edges-in-houdini/?comment=7050&do=findComment
- Typ: zeitgenössische Community-Diskussion
- Wert: **mittel**
- Ein Nutzer berichtet explizit, dass Mirai Edge Loops als eingebautes Modeling-Konzept verwendete und sie zur Definition von Patch-Grenzen nutzte.
- Sehr interessante Beobachtung, aber nicht als alleinige technische Tatsache behandeln.

## 6. Recherche-Regeln

1. Primärquellen zuerst.
2. Zeitgenössische Quellen höher gewichten als heutige Rückblicke.
3. Community-Beiträge nur als Hinweis verwenden, bis sie bestätigt sind.
4. Videos als direkte **Verhaltensbeobachtung** behandeln, nicht als Beweis für interne Implementierung.
5. Keine technische Architektur aus einem sichtbaren Verhalten ableiten, ohne dies als Hypothese zu kennzeichnen.
6. Wenn eine Quelle besonders wichtig ist, nach Möglichkeit zusätzlich eine lokale/archivierte Kopie bzw. einen stabilen Archivlink sichern.

## 7. Noch zu suchen

- vollständige N-World 3.0 Dokumentation lokal sichern/strukturieren
- Mirai 1.x Handbücher und Online-Hilfe
- Nendo 1.x Dokumentation
- originale Mirai/N-World Demo-Videos
- Bay Raitt Mirai Demos und Interviews
- Martin Krol Mirai/Nendo Demos
- technische Informationen zur Winged-Edge-Implementierung
- historische Common-Lisp-/S-Graphics-Architektur
- Mirai Undo/History/Editor-Linking
- Mirai Morph/Deformation/Animation-Dokumentation
- Weta-Produktionsberichte zu Gollum
