# Edit-Mode Mirror / Symmetry — DCC-Research

**Status:** Discovery / Research — erster Durchgang. **Keine** Architekturentscheidung, **keine** Empfehlung für Mirai-Bastel.
**Datum:** 2026-09-23
**Ort (vorgeschlagen):** `docs/research/EDIT_MODE_SYMMETRY_RESEARCH.md`
**Modus (M5):** Discovery
**Verwandt:** [`MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md`](MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md) (Modeling-Grammatik, lokale Topologiekontrolle), [`CHARACTER_SYSTEMS_RESEARCH.md`](CHARACTER_SYSTEMS_RESEARCH.md) (Symmetrie bei Weights/Morphs), ROADMAP ARCH-02 (Topology Identity / Provenance).

> Dieses Dokument ist ein **unabhängiger erster Research-Durchgang**. Gemäß AGENTS.md §6 sollte es vor einer längeren Diskussion so archiviert werden, wie es ist. Spätere Bewertungen gehören in ein separates Dokument oder einen klar markierten Nachtrag — nicht in eine Überarbeitung dieses Textes.

---

## 0. Kennzeichnung

Jede substanzielle Aussage trägt eine Markierung:

| Marke | Bedeutung |
|---|---|
| **[FAKT]** | Durch Herstellerdoku, Release Notes, API-Doku, Bug-Tracker-Eintrag der Entwickler oder Quellcode belegt. |
| **[FAKT·Code]** | Selbst im öffentlichen Quellcode nachgelesen (derzeit nur Wings 3D). |
| **[ANWENDER]** | Erfahrungsbericht aus Foren/Community/Bug-Reports von Nutzern. Beschreibt ein beobachtetes Problem, **nicht** die technische Ursache. |
| **[INTERPRETATION]** | Technische Deutung aus den verfügbaren Fakten. Plausibel, aber nicht direkt belegt. |
| **[SCHLUSS]** | Eigene Schlussfolgerung dieses Dokuments über mehrere Quellen hinweg. |
| **[OFFEN]** | Nicht gefunden / nicht belegbar in diesem Durchgang. |

Quellen sind in §10 nummeriert, im Text als `[Q#]`.

---

## 1. Executive Summary

**Die kurze Antwort auf die Leitfrage:** Die heutige Stabilität von Symmetrie-Systemen kommt nach allem, was sich belegen lässt, **nicht** aus besserer numerischer Genauigkeit. In keiner der untersuchten Quellen wurde eine Verbesserung auf Präzision zurückgeführt [OFFEN — aber auffällig]. Stattdessen sind drei andere Ideen erkennbar, die in fast allen reifen Systemen wiederkehren [SCHLUSS]:

1. **Die zweite Hälfte wird gar nicht gespeichert, sondern abgeleitet.** (Blender Mirror Modifier, 3ds Max Symmetry Modifier, Cinema 4D Symmetry-Objekt, Houdini Mirror SOP, Wings 3D Virtual Mirror.) Damit *kann* die Gegenseite nicht driften — es gibt sie nur als Ergebnis.
2. **Die Mittellinie wird zu einem expliziten, gespeicherten Objekt.** Früher war die Naht nur „die Vertices, die zufällig nahe bei x=0 liegen". Heute ist sie in mehreren Systemen etwas, das der Artist *deklariert* und das Programm *festhält*: eine Seam-Edge (Maya), ein Selection Set (Modo), ein gespeichertes „Symmetry Selection"-Tag (C4D), eine versteckte Spiegelfläche (Wings).
3. **Korrespondenz über Topologie statt über Position.** Seit etwa Mitte der 2010er (Maya 2015, später C4D 2023, ZBrush Poseable Symmetry) finden Systeme das Gegenstück über Nachbarschaftsbeziehungen im Netz, nicht über gespiegelte Koordinaten. Das macht Symmetrie robust gegen Drift und sogar gegen Posen — aber empfindlich gegen *topologische* Asymmetrie.

Dazu kommen **Schutzmechanismen**, die verhindern, dass Naht-Vertices die Ebene überhaupt verlassen (Clipping, Clamp, Projektion, Maya „Preserve Seam" mit weicher Übergangszone).

**Was nicht gelöst ist [SCHLUSS]:**

- **Das Toleranz-Dilemma existiert in jedem System weiter.** Jeder Weld/Merge/Matching-Schritt hat einen Schwellenwert: zu klein → Lücken; zu groß → ungewollte Verschmelzung. Die Hersteller dokumentieren beide Richtungen selbst.
- **Topologie-verändernde Operationen *auf* der Mittellinie** sind weiterhin Grenzfälle. Maxon nennt z. B. offen „seltene, undefinierte Fälle" [Q20].
- **Topologische Korrespondenz bricht, sobald die Topologie selbst asymmetrisch wird** — also genau in dem Moment, in dem man sie in einer langen Modeling-Session am meisten bräuchte.
- **Re-Symmetrisieren unter Erhalt von Vertex-Reihenfolge/UVs** ist in manchen Tools weiterhin eine Lücke (Blender-Bugreport: „Worked: never" [Q5]).

**Die wichtigste konzeptionelle Beobachtung [SCHLUSS]:** Die Frage „Wie finde ich das Gegenstück?" ist fast überall durch die Frage „Was ist hier die Source of Truth?" ersetzt worden. Systeme, die diese Frage klar beantworten (eine Hälfte + abgeleitete zweite Hälfte), haben kaum Drift-Probleme, dafür Einschränkungen beim Arbeiten am Ganzen. Systeme, die das ganze Netz als Wahrheit behalten (Edit-Mode-Symmetrie), brauchen Korrespondenz — und damit Toleranzen oder Topologie-Annahmen, die irgendwann versagen.

---

## 2. Historische Entwicklung des Problems

### 2.1 Das ursprüngliche Problem

[INTERPRETATION] Das klassische Problem entsteht, weil zwei Dinge gleichzeitig wahr sein sollen, die im Datenmodell nicht verbunden sind:

- „Diese beiden Vertices sind Spiegelpartner." (Korrespondenz)
- „Dieser Vertex liegt auf der Ebene." (Naht-Invariante)

Wenn beides nur *aus Koordinaten erschlossen* wird, zerstört jede kleine Positionsänderung die Beziehung. Der Artist sieht das als: Gegenstück bewegt sich plötzlich nicht mehr mit, Mittellinie klafft, Near-Doubles an der Naht, manuelle Reparatur mit Weld/Flatten/Neuspiegeln.

Belege, dass genau das der Ausgangszustand war:

- [FAKT] Blenders Handbuch: X-Mirror funktioniert nur, wenn Spiegel-Vertices **exakt** an gespiegelten Positionen liegen; sonst werden sie nicht als gespiegelt erkannt. Das Handbuch nennt die Bedingungen selbst „ziemlich streng" und empfiehlt stattdessen den Mirror Modifier [Q3].
- [FAKT] Wings-3D-Handbuch: Wird die Spiegelfläche während des Modellierens unplan, führt Spiegeln zu „a real mess"; Reparatur = Fläche flatten, neu spiegeln, neu zentrieren [Q14].
- [FAKT] Wings-3D-Handbuch beschreibt den klassischen Kreislauf: Mitte sauber halten, spiegeln, weitermodellieren, Mittel-Loop schneiden, eine Hälfte löschen, erneut spiegeln [Q13].
- [ANWENDER] Houdini-Forum 2006: gespiegelte Hälften reißen beim Subdividieren in der Mitte auf; Lösung: alle Naht-Punkte manuell auf tx=0 setzen, dann Seam-Toleranz erhöhen [Q24].

### 2.2 Grobe Generationen (Rekonstruktion)

[SCHLUSS] Die Datierung ist in diesem Durchgang nur teilweise belegt. Die Reihenfolge der Ideen ist robuster als die Jahreszahlen.

| Generation | Idee | Beispiele (belegt) | Datierung |
|---|---|---|---|
| **G0 — Manuell** | Hälfte modellieren, duplizieren, skalieren −1, welden | Wings-Workflow [Q13], Houdini-Forum 2006 [Q24], Blender 2.4 „Workarounds" (Linked Duplicate gespiegelt) [Q1] | vor/um 2000–2006 |
| **G1 — Abgeleitete Hälfte** | Generator/Modifier erzeugt die zweite Hälfte live, mit Weld-Toleranz | Blender Mirror Modifier (Doku 2.4x) [Q1], Max Symmetry Modifier [Q8], C4D Symmetry-Objekt [Q17], Houdini Mirror SOP [Q24], Wings Virtual Mirror [Q12] | Blender 2.4x-Doku belegt; übrige [OFFEN] |
| **G1b — Naht-Schutz** | Clipping / Clamp / Projektion hält Naht-Vertices auf der Ebene | Blender „Do Clipping" (2.4x) [Q1], C4D „Clamp Points on Axis" [Q18], Wings Mirror-Projektion [Code] | Blender 2.4x belegt |
| **G2 — Positions-Symmetrie am ganzen Netz** | Beide Hälften existieren real; Gegenstück per gespiegelter Position + Toleranz | Blender X-Mirror [Q3], Maya Object/World-Symmetrie [Q10], Modo Symmetry [Q15] | [OFFEN] |
| **G3 — Topologische Korrespondenz** | Gegenstück über Netzstruktur, ausgehend von einer deklarierten Naht | Silo (Mittel-Edge + Taste) [Q27, ANWENDER], Blender Topology Mirror [Q3][Q4], Maya 2015 [Q9][Q11], Modo 9xx [Q15][Q16], ZBrush Poseable Symmetry [Q21], C4D 2023 [Q20] | Maya 2015 belegt (2014); C4D 2023 belegt |
| **G3b — Symmetrie auch für Topologie-Operationen** | Extrude/Bevel usw. werden auf der Gegenseite *ausgeführt*, nicht nur Transforms | Maya 2015 (Extrude/Bevel) [Q11], C4D 2023 (globales System für Modeling-Tools) [Q20] | belegt |
| **G4 — Reparatur-Werkzeuge** | Asymmetrisches Netz wieder symmetrisch machen, mit/ohne Topologie-Erhalt | Blender Symmetrize / Snap to Symmetry [Q6][Q7], Max Symmetry Tools (aus PolyBoost, 2008) [Q22][Q23], ZBrush Mirror & Weld / Smart ReSym [Q21], C4D Symmetrize [Q20] | PolyBoost 4.0 (2008) belegt |

**[SCHLUSS] Richtung der Evolution:** von *impliziter* Symmetrie (Koordinaten stimmen zufällig) → *abgeleiteter* Symmetrie (eine Hälfte ist Quelle) → *deklarierter* Symmetrie (Naht und Korrespondenz sind gespeicherte Daten) → *systemweiter* Symmetrie (ein globaler Modus statt Einzeloptionen pro Tool; bei C4D ausdrücklich so beschrieben [Q20]).

---

## 3. DCC-by-DCC Analyse

### 3.1 Blender

Blender ist das am besten dokumentierte Beispiel, weil es **drei unterschiedliche Modelle gleichzeitig** anbietet und sie in der Doku gegeneinander abgrenzt.

**A) Mirror Modifier — abgeleitete Hälfte**

- [FAKT] Spiegelt entlang lokaler Achsen am Objekt-Origin oder an einem anderen Objekt; kann Vertices an der Ebene innerhalb einer Toleranz verschweißen; kann verhindern, dass Original-Vertices die Ebene durchqueren; spiegelt optional Vertex Groups und UVs [Q1][Q2].
- [FAKT] Heutige Doku: Liegt Geometrie bereits auf beiden Seiten, wird sie an der Ebene geschnitten und nur eine Seite behalten („Bisect") [Q2].
- [FAKT] Clipping: Sobald Vertices innerhalb der Merge-Distanz sind, schnappen sie auf die Ebene und können sie nicht mehr verlassen; zum Lösen muss Clipping ausgeschaltet werden [Q2]. Clipping wirkt nur im Edit Mode, nicht bei Object-Mode-Transforms [Q1].
- [FAKT] Blender-Bugtracker #103175 (3.4, 2022): Mit Clipping aktiv verhalten sich Vertices, als wäre Merge an — auch wenn Merge aus ist. Entwicklerkommentar: Sie sind **nicht wirklich verschmolzen** (Doubles bleiben, sichtbar an harter Kante bei Smooth Shading); sie „kleben" nur, weil das Transform-System den Schwellenwert anwendet. Laut Handbuch sei das erwartetes Verhalten [Q26].
  - [INTERPRETATION] Clipping ist also ein **Transform-Constraint**, kein Datenmodell-Merge. Die Naht wird im *Ergebnis* (Modifier-Output) geschlossen, nicht in der Quelle.
- [FAKT] Reihenfolge im Modifier-Stack zählt: Liegt Subdivision vor Mirror, wirkt die Merge-Grenze nicht in die Subdivision hinein; Lösung laut Tracker: Mirror zuerst [Q25].

*Source of Truth:* die eine gespeicherte Hälfte. *Zweite Hälfte:* nicht gespeichert, bei Auswertung erzeugt. *Naht:* Distanz-Merge im Output + Clipping im Edit Mode.

**B) Edit-Mode Mesh Symmetry (X/Y/Z-Mirror) — Positions-Korrespondenz am ganzen Netz**

- [FAKT] Transformiert man ein Element, wird sein **exaktes** gespiegeltes Gegenstück (im lokalen Raum) mitbewegt [Q3].
- [FAKT] Die Doku nennt die Bedingungen „quite strict" und verweist auf den Mirror Modifier als einfachere Lösung [Q3].
- [ANWENDER] Blender Artists 2019: X-Mirror, Symmetrize, Snap to Symmetry und Modifier helfen nur früh im Prozess oder solange man nur verschiebt — nicht beim Hinzufügen/Entfernen von Geometrie [Q29].
  - [INTERPRETATION] In Blender ist Edit-Mode-Symmetrie historisch primär eine **Transform-Eigenschaft**, keine Eigenschaft von Topologie-Operationen. [OFFEN] Welche Blender-Tools heute Topologie gespiegelt ausführen, wurde hier nicht vollständig geprüft.

**C) Topology Mirror — topologische Korrespondenz**

- [FAKT] Ergänzt X-Mirror: Gegenstücke werden nicht nur über Position, sondern über Beziehungen im Netz bestimmt; funktioniert besser bei detaillierter Geometrie, oft nicht bei Würfel oder UV-Kugel [Q3].
- [FAKT] Diskussion im Blender-Tracker (#81698): Intern wird pro Vertex eine ID aus der umgebenden Topologie berechnet (Anzahl Nachbar-Vertices/-Edges), nicht aus der Position. Paare mit gleicher Umgebung erhalten gleiche IDs; eindeutig nur, wenn kein anderes Paar dieselbe Umgebung hat. Beobachtung im Ticket: Die Kandidatenwahl ignoriert die gewählte Achse praktisch; ein „Partner" kann sogar auf derselben Seite liegen [Q4].
  - [INTERPRETATION] Das ist eine Art **Nachbarschafts-Hashing** (ähnlich einer Graph-Signatur), kein Ausbreiten von einer Naht aus. Daher die Schwäche bei regelmäßigen Formen: Dort haben viele Vertices identische Umgebungen.
- [FAKT] Bugreport #115725 (Blender 4.0.1): Nach leichtem Sculpten erkennt Topology Mirror manche Vertices nicht mehr als Paare, obwohl die Topologie symmetrisch ist; zudem fehlt eine Funktion, die Symmetrie unter Erhalt von Vertex-Reihenfolge und UVs wiederherstellt („wie Mayas Symmetrize"); „Worked: never". Als Duplikat von #81698 geschlossen, Nutzung von Topology Mirror sei „bis zu einem gewissen Grad unklar" [Q5].

**D) Reparatur**

- [FAKT] **Symmetrize**: schneidet das Netz am Pivot, spiegelt eine Seite, verschmilzt die Hälften (falls verbunden), überträgt UVs, Vertex Colors, Weights; Schwellenwert schnappt Vertices auf die Ebene [Q7].
- [FAKT] **Snap to Symmetry**: paart Vertices **über Position** (Suchradius), repositioniert sie; Faktor mischt zwischen beiden Seiten (0,5 = Mittelwert); „Center" setzt Vertices nahe der Ebene exakt auf 0. Ausdrücklich abgegrenzt: Symmetrize löscht eine Hälfte, Snap to Symmetry nicht [Q6].
- [ANWENDER] Blender Artists 2019: Nach R3DS-Wrap auf einen Scan funktioniert weder Symmetrize (merged nicht) noch Snap to Symmetry zufriedenstellend; der Nutzer verweist auf Mayas Symmetrize [Q28].
- [ANWENDER/Drittanbieter] Ein Blender-Add-on erzeugt aus zwei vom Nutzer gewählten korrespondierenden Faces/Edges ein Attribut `symmetry_indices` (Partner-Index pro Vertex, −1 = unbekannt) [Q30].
  - [INTERPRETATION] Das zeigt eine Lücke, die Nutzer mit einer **gespeicherten Korrespondenz-Tabelle** füllen — genau das Modell, das Maya/C4D/Houdini nativ anbieten.

**[SCHLUSS] Blender** hat seine Symmetrie-Robustheit primär über den *Modifier-Weg* (abgeleitete Hälfte + Clipping) erreicht. Die Edit-Mode-Symmetrie am ganzen Netz ist dokumentiert streng und nach Nutzerberichten der schwächere Weg.

---

### 3.2 3ds Max

**A) Symmetry Modifier — abgeleitete Hälfte im Stack**

- [FAKT] Drei Aufgaben in einem: spiegeln, slicen (Teile entfernen), Naht automatisch welden. Änderungen an der Originalhälfte *unterhalb* im Stack erscheinen live auf der anderen Hälfte [Q8].
- [FAKT] Ältere Doku (2016): „Slice Along Mirror" lässt das Gizmo als Schnittebene wirken, sofern es innerhalb des Objekts liegt; ohne Slice ist die Spiegelung ein separates Element. „Weld Seam" verschweißt Vertices entlang der Achse innerhalb Threshold, Default 0,1; Hinweis: zu hoher Threshold verzerrt das Netz [Q8].
- [FAKT] 2022–2024-Doku: zusätzlich Optionen, die eine Hälfte spiegeln, „um saubere Nähte zu erzeugen", und Flip [Q8].
- [ANWENDER] Autodesk-Forum 2021 zu Max 2022: Mit „Slice along mirror" findet offenbar ein internes Verschmelzen vor dem Spiegeln statt, ohne kontrollierbaren Schwellenwert (Nutzer schätzt ~0,01 Einheiten); in 2021 nicht so. Genannt als Problem für kleine Game-Assets; gleichzeitig werden Multi-Axis und Capping des „neuen" Modifiers gelobt [Q9b].
  - [INTERPRETATION] Ein Hinweis, dass der Modifier um 2021/2022 neu implementiert wurde und dabei ein Toleranz-Parameter implizit wurde. [OFFEN] Offizielle Release Notes dazu wurden nicht geprüft.

**B) Symmetry Tools (Graphite / Ribbon, ursprünglich PolyBoost)**

- [FAKT] Werkzeuge, um Modelle symmetrisch zu machen, wenn der Modifier nicht geht — ausdrücklich z. B. bei **Morph Targets**. Man wählt ein symmetrisches Referenzobjekt; Max berechnet mit Toleranz die Symmetrie und kann das Ergebnis auf jedes Modell mit **gleicher Vertex-Anzahl** anwenden. Nach der Berechnung werden alle nicht-symmetrischen Vertices selektiert, *einschließlich der Naht-Vertices*. Funktionen: Spiegeln durch Tausch von Positionen, Kopieren/Einfügen von Vertex-Positionen [Q22].
- [FAKT] Herkunft: PolyBoost 4.0 (2008) führte diese „Symmetry Tools" ein, „great for working with morphtargets" [Q23].
  - [INTERPRETATION] Das ist ein frühes Beispiel für **„einmal berechnete Korrespondenztabelle, danach index-basiert anwenden"**. Die Tabelle wird einmal geometrisch gewonnen und dann über Vertex-Indizes auf andere Formen übertragen.
- [ANWENDER] polycount 2010: Graphite-Mirror-Tools sind „nicht live wie in Maya"; Empfehlung, für Symmetrie zu Silo zu wechseln, dessen Symmetrie „Modeling-Operationen respektiert" [Q27].
- [ANWENDER] polycount 2011: Graphite Symmetry Tools liefern bei nicht völlig symmetrischem Objekt „schiefe" Ergebnisse [Q27b].
- [ANWENDER] Autodesk-Forum 2024: Es gibt kein natives „Symmetrize ohne Änderung der Vertex-Reihenfolge"; die Symmetry Tools verlangen ein bereits symmetrisches Referenznetz; ein Nutzer schreibt stattdessen ein Script mit „topologischer Karte" (Merkmale pro Vertex zählen) [Q9c].

**[SCHLUSS] 3ds Max** setzt fast vollständig auf die **abgeleitete Hälfte im Modifier-Stack**. Live-Symmetrie am ganzen Netz (Edit Poly) war nach Nutzerberichten lange die Schwäche; topologiebasierte Korrespondenz ist in den gefundenen Quellen nicht nativ belegt [OFFEN].

---

### 3.3 Cinema 4D

C4D zeigt die deutlichste **dokumentierte Architekturverschiebung**.

**A) Symmetry-Objekt (Generator) — abgeleitete Hälfte**

- [FAKT] Parameter (SDK): Mirror Plane, Weld Points, Weld Tolerance, „Symmetrical" (ONPLANE), Clamp Points on Axis, Delete Polygons on Axis, Automatically Flip, Flip; inzwischen zusätzlich „Convert to New Symmetry Generator" — das alte Objekt heißt jetzt „Legacy" [Q17].
- [FAKT] Doku (S22): Weld verbindet Punkte an der Spiegelkante (zwei werden einer). Mit „Symmetrical" liegen verschweißte Punkte **exakt** auf der Achse; ohne es landet der Punkt **in der Mitte zwischen den beiden Ausgangspunkten** — was auf der Achse liegen kann oder nicht [Q18].
  - [INTERPRETATION] Hier wird eine subtile Entscheidung sichtbar: **Weld-Ergebnis = Mittelwert** (erhält Form, verschiebt Naht) vs. **Weld-Ergebnis = Projektion auf Ebene** (erhält Naht, verändert Form). Beides sind legitime Antworten auf dasselbe Problem.
- [FAKT] Maxon Release Notes 2025.2 / 2026.1 enthalten weiterhin Fixes rund um das Symmetry-Objekt und den Symmetry-Generator [Q19].

**B) Globales Symmetrie-System (seit Cinema 4D 2023)**

- [FAKT] Seit 2023 gibt es ein **global wirksames** Symmetrie-System; Ziel ist, die bisher pro Tool verteilten Einstellungen (z. B. Sculpt-Brushes) zu zentralisieren. Es wirkt für Mesh-Modeling-Tools, mehrere Spline-Tools, Sculpt und Paint. Tools ohne Unterstützung erkennt man daran, dass die Symmetrieeinstellungen ausgeblendet werden [Q20].
- [FAKT] Es arbeitet sowohl beim **Erzeugen** symmetrischer Objekte mit Modeling-Tools („früher übernahm das das Symmetry-Objekt") als auch beim Bearbeiten bestehender symmetrischer Objekte [Q20].
- [FAKT] Drei Typen: **Planar** (Ebene), **Topology** (über eine vom Nutzer definierte Edge- oder Polygon-Loop), **Radial** [Q20].
- [FAKT] Planar-Toleranz: Ohne „Clamp" wird schlicht der nächstgelegene Punkt zur idealen Spiegelposition als Partner genommen; mit Clamp nur bis zu einer Toleranz. Weicht ein Punkt einer Edge/eines Polygons ab, gilt die ganze Edge/das ganze Polygon als nicht symmetrisch [Q20].
- [FAKT] Topology-Algorithmus (vereinfachte Herstellerbeschreibung): Start an der Loop, Laufen senkrecht zur Topologie in beide Richtungen; Komponenten in gleicher Kantenschritt-Distanz auf der Gegenseite gelten als symmetrisch, **3D-Position spielt keine Rolle**. Funktioniert, solange die Topologie beidseitig gleich ist; Punkte mit abweichender Nachbarzahl werden samt Polygonen als nicht symmetrisch eingestuft [Q20].
- [FAKT] Die Loop wird in einem speziellen **Selection-Tag „Symmetry Selection"** gespeichert; pro Objekt/Insel ist eine eigene Loop nötig [Q20].
- [FAKT] Selektion auf der Gegenseite ist **virtuell**: gespeichert wird nur die manuelle Selektion; „Symmetrize Selection" macht die virtuelle Selektion real [Q20].
- [FAKT] Offen dokumentierte Grenzen: Leistung ab ~100.000 Polygonen; einige Polygon-Pen-Funktionen und Schnitte nicht unterstützt mit Topology-Symmetrie; **Werkzeuge halten die Symmetrie gelegentlich nicht ein, vor allem bei Komponenten auf der Ebene** (Beispiel: Flip Edges auf einer Kante, die die Ebene schneidet) — „seltene, undefinierte Fälle" [Q20].
- [FAKT] Release Notes 2025.3: Fix „Symmetry mode had no effect" bei Set Vertex Weight; 2026.1: Fix „Magnet tool created problematic geometry with topological symmetry", „Brush tool now works properly with symmetry" [Q19].
  - [INTERPRETATION] Das globale System ist ein **laufender Integrationsprozess**: Jedes Werkzeug muss einzeln symmetrie-fähig gemacht werden; die Fehlerliste zeigt, wo die Naht zwischen Tool und System noch offen ist.

**[SCHLUSS] Cinema 4D** ist ein seltenes Beispiel, bei dem ein Hersteller den Wechsel von „Symmetrie als Objekt/Generator" zu „Symmetrie als globaler Modus mit deklarierter Topologie-Naht" **explizit** beschreibt — inklusive Einschränkungen.

---

### 3.4 Modo

- [FAKT] Symmetry ist ein szenenweiter Modus; alle Komponenten-Operationen (Selektion, Deformation) werden gespiegelt. Für beste Ergebnisse soll das Modell perfekt symmetrisch sein, da Modo Operationen grundsätzlich auf **korrespondierende Vertex-Positionen** anwendet [Q15].
- [FAKT] Option **Topology**: topologisches Matching, wenn reguläre Symmetrie versagt; das Modell muss trotzdem „weitgehend symmetrisch" sein; bei asymmetrischen Formen liefert es nicht das erwartete Ergebnis [Q15].
- [FAKT] **Use / Assign Selection Set**: Eine Edge-Loop wird als Mittellinie in einem speziell benannten Selection Set gespeichert, um die topologische Achse zu finden. Wichtige Einschränkung: Das ist **keine lokale Symmetrie**; die Symmetrieebene ist weiterhin immer das Achsenzentrum [Q15].
- [FAKT] Es gibt ein **Symmetrize** zur Reparatur [Q15]; Doku-Tipp für extreme Asymmetrie: halbe Seite löschen und neu spiegeln [Q15b].
- [ANWENDER] polycount 2016: Topologische Symmetrie mit Mesh abseits des Welt-Nullpunkts: Selektion funktioniert, Tools/Transforms nicht; Bevel „kaputt", weil es vom **Item-Center** abhängt — Lösung: Item-Center auf die Geometrie setzen [Q16].
  - [INTERPRETATION] In Modo scheint Topologie-Symmetrie zumindest damals nur die **Korrespondenz** geliefert zu haben, während die **Spiegeloperation** (Transform-Richtung, Pivot) weiterhin an einer geometrischen Ebene hing. Korrespondenz und Spiegelgeometrie sind also zwei getrennte Teile, die zueinander passen müssen.

---

### 3.5 Wings 3D

Wings ist für Mirai-Bastel historisch relevant (Nendo/Mirai-Linie) und das einzige untersuchte System mit öffentlich lesbarem Quellcode. Die Aussagen unten stammen teilweise direkt aus dem Code (Repository `dgud/wings`, Stand Commit vom 2026-09-08).

**Konzept: Virtual Mirror**

- [FAKT] Handbuch: „Create" erzeugt die virtuelle Hälfte **aus einer selektierten Fläche**; man kann an beiden Hälften arbeiten, Änderungen werden gespiegelt. „Break" verwirft die virtuelle Hälfte, „Freeze" macht sie zu echter Geometrie [Q12].
- [FAKT·Code] Das Objekt (`#we{}`, Winged-Edge-Struktur) hat ein Feld `mirror`, das auf **genau eine Fläche** zeigt. `create_mirror/2` versteckt diese Fläche und speichert sie als Spiegelfläche. Die Spiegelfläche ist also ein **reales, aber verstecktes Element der Topologie** — die Naht ist ein Topologie-Objekt.
- [FAKT·Code] `mirror_projection/1`: Die Spiegelebene wird **aus der Spiegelfläche berechnet** (Flächennormale + Zentrum der Flächen-Vertices) und als Projektionsmatrix auf diese Ebene zurückgegeben.
- [FAKT·Code] `wings_drag:mirror_constrain/2`: Bei jedem Drag werden Vertices, die zur Spiegelfläche gehören, durch diese Projektionsmatrix geschickt — sie **können die Ebene nicht verlassen**. Dasselbe gilt im Tweak-Modus (`wings_tweak.erl`, mehrfach `mirror_constrain`).
- [FAKT·Code] `mirror_flatten(OldWe, We)`: Nach Operationen wie Subdivide, Smooth, Flatten projiziert Wings die Vertices der Spiegelfläche auf die Ebene, **die aus dem Zustand *vor* der Operation berechnet wurde**.
  - [INTERPRETATION] Die Ebene wird so gegen „Mitdriften" verankert: Die Operation darf die Ebene nicht verschieben, weil die Referenz der Vorher-Zustand ist.
- [FAKT·Code] Beim Extrudieren von Flächen, die an die Spiegelfläche grenzen, werden neu entstandene Flächen an der Grenze **in die Spiegelfläche aufgelöst** (dissolve) und die neue Fläche wird zur neuen Spiegelfläche (`wings_face_cmd.erl`, ca. Z. 255–266).
  - [INTERPRETATION] Extrude über die Mittellinie erzeugt so **keine inneren Wände** in der Naht — ein direkter, lokaler Umgang mit einem klassischen Stressfall.
- [FAKT·Code] `validate_mirror/1`: Existiert die Spiegelfläche nach einer Operation nicht mehr (z. B. durch Dissolve), wird der Mirror **stillschweigend auf `none` gesetzt**.
  - [INTERPRETATION] Failure Mode: Wird die Naht-Fläche zerstört, verschwindet die Symmetrie, statt einen Fehler zu melden.
- [FAKT·Code] Vertex-Normalen an der Spiegelfläche werden mit den gespiegelten Nachbarnormalen gemittelt, damit die Naht weich schattiert (`wings_we.erl`, `average_normals`).
- [FAKT] Handbuch: Die Spiegelfläche muss **eine einzelne Fläche** sein; Nutzer mit mehreren Flächen an der Mitte bekommen Fehler [Q14b].
- [ANWENDER] Frühe Nutzerwünsche: Bewegungen auf der virtuellen Seite laufen gespiegelt entgegengesetzt; Wunsch nach nicht-gespiegelter Bewegungsrichtung [Q14c].

**[SCHLUSS] Wings** löst Naht-Management nicht über Toleranz, sondern über ein **Topologie-Element (eine Fläche) als Naht-Deklaration** + **harte Projektion** + **explizite Sonderbehandlung einzelner Operationen**. Es gibt keine Weld-Toleranz, weil die zweite Hälfte bis „Freeze" nicht existiert. Der Preis: Die Naht muss eine einzige planare Fläche sein, und sie ist ein Sonderobjekt, das jede Operation respektieren muss.

---

### 3.6 ZBrush

- [FAKT] Standard-Symmetrie spiegelt Aktionen über X/Y/Z in Weltkoordinaten. **Poseable Symmetry** nutzt „SmartResym" und bestimmt Symmetrie über **Topologie statt Weltraum**; Voraussetzung: topologisch symmetrisch über **genau eine** Achse — Kugel oder Würfel (mehrachsig symmetrisch) scheitern. Nutzt keine UVs [Q21].
- [FAKT] Visuelles Feedback: grüner Pinselradius = Poseable Symmetry aktiv, rot = nicht aktiv [Q21].
- [FAKT] Nach **Subdividieren** fällt ZBrush auf normale Symmetrie zurück; Poseable Symmetry muss neu berechnet werden. Bei ~50 % Symmetrie und N-Gons können Edge-Loops die Ursache sein [Q21].
  - [INTERPRETATION] Die Korrespondenz ist eine **berechnete Tabelle**, die bei Topologieänderung ungültig wird — ZBrush macht das sichtbar (Farbe) statt still falsch zu arbeiten.
- [ANWENDER/Händlerblog] Mirror and Weld kopiert eine Seite auf die andere mit WeldDist-Parameter; zerstört eine Pose; Richtung ist fest (negativ → positiv) [Q21b].

**[SCHLUSS] ZBrush** trennt klar: Weltraum-Symmetrie für Sculpt-Standardfall, topologische Tabelle für gepostete Modelle, destruktive Reparatur (Mirror & Weld) als letzter Schritt.

---

### 3.7 Houdini

- [FAKT] **Mirror SOP**: spiegelt Geometrie an einer Ebene (Origin, Direction, Distance); „Keep Original"; **Consolidate Seam** verschmilzt Punkte auf der Ebene, dabei **nur die neu gespiegelten Punkte**; zusätzlich „Only Consolidate Unshared Edges" [Q24b]. HDK-Parameter enthalten `consolidate_tolerance` und eine `redirect_map` [Q24c].
  - [INTERPRETATION] Die `GEO_MirrorRedirectMap` deutet darauf hin, dass der Mirror intern eine **Abbildung Quelle → gespiegeltes Element** mitführt. [OFFEN] Nicht weiter geprüft.
- [FAKT] **Attribute Mirror SOP**: überträgt Attribute (z. B. UVs) von einer Seite auf die andere; Methoden **Plane**, **Topology** und **Use Mapping** (integer Mapping-Attribut pro Element) [Q24d].
- [ANWENDER] Houdini-Forum 2006: Naht reißt beim Subdividieren; manuell auf tx=0 setzen, Toleranz von 0,0001 erhöhen [Q24].
- [ANWENDER] Houdini-Forum 2021 und 2026: Direktes Polygon-Modeling mit Symmetrie gilt als Schwäche; Nutzer vermissen symmetrische Selektion; Verweis auf TopoBuild oder Drittanbieter [Q24e].

**[SCHLUSS] Houdini** behandelt Symmetrie konsequent **prozedural**: Spiegeln ist ein Knoten, Korrespondenz ist ein Attribut/Mapping. Interaktive Edit-Mode-Symmetrie ist kein Schwerpunkt. Interessant ist die **explizite Mapping-Methode** — Korrespondenz als gewöhnliches, speicherbares Datenattribut.

---

### 3.8 Ergänzung: Maya (historisch und technisch relevant)

Maya war nicht auf der Liste, ist aber für topologische Korrespondenz und Naht-Schutz die am klarsten dokumentierte Referenz.

- [FAKT] Maya-2015-Überblick (2014): Symmetrie kann über eine **Mittel-Edge** neu zugewiesen werden, um auch asymmetrisch gewordenen Teilen Symmetrie zurückzugeben; **Extrude und Bevel respektieren Symmetrie** [Q11].
- [FAKT] Topologische Symmetrie: Seam-Edge wählen; Topologie muss beidseitig gleich sein; **Wird eine Seam-Edge verändert, wird Symmetrie deaktiviert**; empfohlen: eine Seam-Edge wählen, die nicht bearbeitet wird [Q10].
- [FAKT] Voraussetzungen: gleiche Anzahl Faces pro Hälfte; eine Edge entlang der Mittellinie; **keine Faces, die die Mittellinie überspannen**. Ist das Netz nicht vollständig topologisch symmetrisch, aktiviert sich **partielle topologische Symmetrie** [Q10b].
- [FAKT] Symmetrie in Maya ist **selektionsbasiert**: Gegenstücke werden in die Selektion aufgenommen; dadurch funktionieren selektionsbasierte Operationen symmetrisch [Q10b].
- [FAKT] `symmetricModelling`-Befehl: `tolerance`, `preserveSeam`, `seamTolerance` („Breite der erzwungenen Naht"), `seamFalloffCurve` (Stärke der Naht innerhalb der Toleranz), `topoSymmetry` [Q10c]. Aktuelle Doku: Naht-Komponenten können sich nicht von der Achse wegbewegen; eine Falloff-Kurve steuert, wie stark Komponenten *nahe* der Naht widerstehen — hohe Naht-Wirkung nahe der Naht, weniger am Rand der Toleranz [Q10d].
  - [INTERPRETATION] Das ist **Naht-Schutz als weiches Feld** statt als binäres Clipping: Nicht nur die Naht-Vertices sind gesperrt, sondern eine Zone um die Naht wird graduell „festgehalten". Das verhindert den typischen Knick direkt neben einer harten Clipping-Linie.
- [FAKT] Pose Editor / Blendshapes: Spiegeln per Object-Achse oder **Topology**, mit Option „Store topological symmetry seam edges" pro Blendshape-Deformer [Q10e].
- [Drittanbieter, FAKT laut Projekt-Wiki] `polySymmetry` (Maya-Plugin): iterativer Algorithmus, der von Nutzer-gewählten symmetrischen Startkomponenten aus die Topologie „nach außen abläuft" und eine **Symmetrie-Tabelle** für Edges, Faces und Vertices erzeugt; nutzbar für Skin Weights, Deformer-Gewichte, Blendshapes — **auch auf deformierten Charakteren ohne Bind-Pose**, weil Positionen keine Rolle spielen [Q31].

---

### 3.9 Ergänzung: Silo

- [ANWENDER] polycount 2007/2010: Symmetrie in Silo wird durch Wahl einer Mittel-Edge + Taste aktiviert; Silos Symmetrie gilt als „wirklich solide" und respektiert Modeling-Operationen [Q27][Q27c].
- [OFFEN] Keine Primärquelle zu Silos Algorithmus gefunden. Wegen der Nähe zu Mirai-artigen direkten Modelern wäre eine gezielte Nachrecherche sinnvoll.

---

## 4. Vergleich der technischen Modelle

[SCHLUSS] Aus den DCCs lassen sich fünf Grundmodelle abstrahieren. Die meisten Programme kombinieren mehrere.

### M-A — Abgeleitete Hälfte (Generator / Modifier / Virtual)

| Frage | Antwort |
|---|---|
| Source of Truth | Eine gespeicherte Hälfte (+ Parameter der Ebene) |
| Zweite Hälfte real? | Nein — nur im ausgewerteten Ergebnis (bis Apply/Freeze/Make Editable) |
| Erzeugung | Spiegelung jeder Auswertung; Weld/Consolidate an der Naht |
| Mittellinie | Weld-Toleranz im Output; zusätzlich Clipping/Clamp/Projektion beim Editieren |
| Korrespondenz | Trivial: Element i ↔ gespiegeltes Element i (per Konstruktion) |
| Rolle der Topologie | Keine für Korrespondenz; Topologie *über* die Naht hinweg kann nicht direkt ausgedrückt werden (wird geslict/gebisectet) |
| Beispiele | Blender Mirror Mod., Max Symmetry Mod., C4D Symmetry-Objekt, Houdini Mirror SOP, Wings Virtual Mirror |

Typische Failure Modes: Naht-Vertices neben der Ebene → Lücke oder ungewollter Merge (Toleranz-Dilemma); Doubles in der Quelle bleiben unsichtbar, bis man anwendet (Blender #103175); Reihenfolge im Stack (Subdivision vor Mirror) [Q25]; kein echtes Arbeiten „am Ganzen" (z. B. Loop quer durch beide Hälften).

### M-B — Positionskorrespondenz am ganzen Netz

| Frage | Antwort |
|---|---|
| Source of Truth | Das ganze Netz; Korrespondenz wird bei Bedarf **aus Positionen erschlossen** |
| Zweite Hälfte real? | Ja |
| Mittellinie | Nicht strukturell garantiert; nur über Toleranz + ggf. Naht-Schutz |
| Korrespondenz | Nächstgelegener Punkt an gespiegelter Position, mit oder ohne Toleranzgrenze |
| Beispiele | Blender X-Mirror, Maya Object/World, Modo (Default), C4D Planar, ZBrush X/Y/Z |

Failure Mode: Drift über die Toleranz hinaus → Gegenstück „verschwindet". C4D macht die Alternative sichtbar: ohne Clamp immer den *nächsten* Punkt nehmen (nie „kein Partner", aber evtl. falscher Partner) vs. mit Clamp (korrekt oder gar nicht) [Q20].

### M-C — Topologische Korrespondenz

| Frage | Antwort |
|---|---|
| Source of Truth | Das ganze Netz + **eine deklarierte Naht** (Edge, Loop, Selection Set) oder eine Nachbarschafts-Signatur |
| Korrespondenz | Graph-Traversierung von der Naht aus (C4D, polySymmetry, vermutlich Maya) **oder** Nachbarschafts-Hashing (Blender Topology Mirror) |
| Rolle der Position | Keine oder nur zur Orientierung (welche Seite ist welche) |
| Stärken | Robust gegen Drift, Posen, Deformation |
| Schwächen | Scheitert bei asymmetrischer Topologie, bei Mehrfachsymmetrie (Kugel/Würfel), bei regelmäßigen Netzen (Hashing); wird durch Topologieänderung ungültig |
| Beispiele | Maya, Modo, C4D Topology, ZBrush Poseable, Blender Topology Mirror, Silo (ANWENDER) |

### M-D — Gespeicherte Korrespondenztabelle

[SCHLUSS] Eine Spezialform von M-B/M-C: Die Korrespondenz wird **einmal** berechnet und dann als **Daten** gespeichert und index-basiert benutzt.

Beispiele: Max Symmetry Tools (für Morph Targets gleicher Vertex-Zahl) [Q22], Houdini Attribute Mirror „Use Mapping" [Q24d], Maya polySymmetry-Tabelle [Q31], Maya „Store topological symmetry seam edges" pro Blendshape [Q10e], C4D „Symmetry Selection"-Tag (speichert die Naht, nicht die ganze Tabelle) [Q20], Blender-Add-on `symmetry_indices` [Q30].

Wichtig: Diese Tabelle ist genau die Art Information, die bei Topologieänderung **ungültig** wird oder **nachgeführt** werden muss — dieselbe Problemklasse wie ROADMAP ARCH-02 (Provenance/Remapping).

### M-E — Naht-Schutz (Prävention)

| Mechanismus | Art | Beispiele |
|---|---|---|
| Clipping | Harter Transform-Constraint, schnappt innerhalb Toleranz, bleibt kleben | Blender Mirror Mod. [Q1][Q2][Q26] |
| Clamp Points on Axis / Symmetrical | Harter Constraint bzw. Weld-Ergebnis auf Achse statt Mittelwert | C4D [Q17][Q18] |
| Projektion auf Ebene bei jedem Drag + Anker am Vorher-Zustand | Harte Projektion, operationsbezogen | Wings (Code) |
| Preserve Seam + Seam Tolerance + Falloff Curve | **Weiche Zone** um die Naht | Maya [Q10c][Q10d] |
| Seam-Edge-Änderung deaktiviert Symmetrie | „Fail loud" statt still falsch | Maya [Q10] |
| Anzeige-Zustand (grün/rot) | Sichtbare Gültigkeit | ZBrush [Q21] |
| Ausgeblendete Symmetrieeinstellungen, wenn Tool nicht unterstützt | Sichtbare Nicht-Unterstützung | C4D [Q20] |

---

## 5. Stressfall-Vergleich

**Lesehinweis:** Nur wenige Zellen sind direkt belegt. Die Tabelle ist deshalb **nach Modell** (M-A/B/C) aufgebaut, mit DCC-Belegen, wo vorhanden. `?` = in diesem Durchgang nicht belegt. Unbelegte Zellen sind absichtlich leer gelassen, statt geraten.

| Stressfall | M-A abgeleitete Hälfte | M-B Positions-Symmetrie | M-C Topologische Symmetrie |
|---|---|---|---|
| **Vertex driftet minimal von der Ebene** | Mit Clipping/Projektion: kann nicht passieren (Blender [Q2], Wings Code). Ohne: Lücke oder Merge je nach Toleranz [Q18] | Gegenstück wird nicht mehr erkannt, wenn außerhalb Toleranz (Blender [Q3]); C4D ohne Clamp: nimmt nächsten Punkt [Q20] | Drift ist egal, Korrespondenz bleibt (C4D [Q20], ZBrush [Q21]) |
| **Vertex über die Ebene gezogen** | Blender Clipping verhindert es [Q1]; Max/Blender: Geometrie jenseits wird geslict/gebisectet [Q2][Q8] | ? | Korrespondenz bleibt; ob die *Spiegeloperation* sinnvoll bleibt: [INTERPRETATION] fraglich (Modo-Bericht zu Pivot [Q16]) |
| **Near-Doubles an der Mittellinie** | Weld-Toleranz entscheidet; Blender Clipping hinterlässt echte Doubles in der Quelle [Q26] | ? | ? |
| **Doppelte / unverschweißte Seam-Vertices** | Im Output durch Weld geschlossen, in der Quelle ggf. nicht [Q26] | Doppelte Vertices können als falsche Partner gewählt werden [INTERPRETATION] | Nicht-manifolde Naht verletzt Voraussetzung (Maya: Edge entlang Mitte, keine überspannenden Faces [Q10b]) |
| **Merge mit Toleranz** | Kerndilemma: zu klein → Lücke, zu groß → Verzerrung/ungewollter Merge (Max [Q8], C4D-Praxis [Q18b]); Max 2022: interner, nicht steuerbarer Merge (ANWENDER [Q9b]) | Snap to Symmetry nutzt Suchradius [Q6] | — |
| **Clipping** | Blender: Clip-Vertices kleben, auch ohne Merge [Q26] | Maya Preserve Seam als weiche Variante [Q10d] | Maya Preserve Seam gilt auch hier [INTERPRETATION] |
| **Extrude über die Mittellinie** | Wings: angrenzende neue Faces werden in die Spiegelfläche aufgelöst (Code) | ? | Maya 2015: Extrude respektiert Symmetrie [Q11] |
| **Knife/Cut über die Mittellinie** | Wings: `validate_mirror` löst Mirror auf, falls Spiegelfläche verschwindet (Code) | Blender: Edit-Mode-Symmetrie für Topologie-Ops laut Nutzern nicht verfügbar [Q29] | C4D: Schnitte teils nicht unterstützt mit Topology-Symmetrie [Q20] |
| **Loop Insert an der Mittellinie** | ? | ? | Maya: Ändern einer Seam-Edge deaktiviert Symmetrie [Q10] |
| **Topologieänderung nur auf einer Seite** | Nicht möglich, solange Mirror aktiv (per Konstruktion) | Unkritisch für Korrespondenz anderer Bereiche [INTERPRETATION] | Maya: partielle Symmetrie [Q10b]; C4D: abweichende Punkte + Polygone gelten als nicht symmetrisch [Q20]; ZBrush: Neuberechnung nötig [Q21] |
| **Lange Session mit vielen Ops** | Stabil, solange Naht-Objekt intakt (Wings) bzw. Toleranz passt | Drift akkumuliert → Snap to Symmetry als Reparatur [Q6] | Korrespondenz erodiert mit jeder asymmetrischen Topologieänderung [INTERPRETATION] |
| **Bereits leicht beschädigtes Mesh** | Reparatur = Hälfte löschen + neu spiegeln (Wings [Q13], Modo [Q15b]) | Blender Snap to Symmetry [Q6]; Max Symmetry Tools selektieren Abweichler [Q22] | Blender #115725: nach Sculpt werden Paare nicht erkannt [Q5]; Maya: Topologie-Symmetrie funktioniert trotz Positionsschaden [Q10b] |
| **Symmetrie wiederherstellen** | Destruktiv: Mirror & Weld (ZBrush [Q21b]), Symmetrize (Blender [Q7]) — Vertex-Reihenfolge nicht garantiert | Nicht-destruktiv per Position: Snap to Symmetry (Faktor, Center) [Q6] | Topologie-erhaltend: Maya Symmetrize (ANWENDER [Q5][Q9c]), Max Symmetry Tools mit Referenz [Q22] |

---

## 6. Welche Probleme wurden tatsächlich gelöst?

[SCHLUSS], jeweils mit dem Mechanismus, der es gelöst hat:

1. **Drift der Gegenseite** — gelöst durch **Nicht-Speichern** der Gegenseite (M-A). Nicht durch Präzision.
2. **Naht-Vertices verlassen die Ebene** — gelöst durch **Constraints** (Clipping, Clamp, Projektion). Blender seit den 2.4x-Handbüchern belegt [Q1]; Wings mit Projektion bei jedem Drag (Code).
3. **Gegenstück verloren bei leichter Positionsabweichung** — gelöst durch **topologische Korrespondenz** (M-C) für Transforms/Selektion und Sculpt, auch in Posen (ZBrush Poseable, C4D Topology, Maya).
4. **Symmetrie für Topologie-Operationen** (nicht nur Transforms) — teilweise gelöst: Maya 2015 (Extrude/Bevel) [Q11], C4D 2023 als globales System [Q20]. [OFFEN] für Blender.
5. **Harter Knick direkt neben geschützter Naht** — adressiert durch **weiche Naht-Zone** (Maya Seam Falloff) [Q10d].
6. **Stilles Fehlverhalten** — teilweise ersetzt durch **sichtbare Gültigkeit**: ZBrush Farbindikator [Q21], Maya deaktiviert Symmetrie bei Naht-Änderung [Q10], C4D blendet Einstellungen aus [Q20].
7. **Symmetrie für abhängige Daten** (Weights, Blendshapes, UVs) — gelöst über **gespeicherte Korrespondenz/Mapping** (M-D): Max Symmetry Tools, Houdini AttribMirror, Maya Pose Editor, polySymmetry.

**Zur Präzisionsfrage explizit:** [OFFEN] In keiner gefundenen Release-Note oder Doku wurde eine Stabilitätsverbesserung auf numerische Genauigkeit (z. B. double statt float) zurückgeführt. Das ist *keine* Widerlegung — nur: Es gibt dafür keinen Beleg, während es für die strukturellen Mechanismen viele Belege gibt.

---

## 7. Welche Probleme existieren weiterhin?

1. **Toleranz-Dilemma.** Alle Weld/Merge/Matching-Schritte brauchen Schwellenwerte; Hersteller dokumentieren selbst beide Fehlerrichtungen [Q8][Q18][Q20]. Max 2022 zeigt, dass Toleranzen bei Neu-Implementierungen sogar zurückkommen können (ANWENDER [Q9b]).
2. **Undefinierte Fälle auf der Ebene.** Operationen auf Elementen, die *auf* der Ebene liegen oder sie schneiden, sind nicht eindeutig spiegelbar (C4D offiziell: Flip Edges [Q20]). [INTERPRETATION] Eine Edge auf der Ebene ist ihr eigenes Gegenstück; eine Operation, die „links" und „rechts" unterscheidet, hat dort keine eindeutige Bedeutung.
3. **Topologische Korrespondenz ist nicht topologie-änderungsfest.** Subdivide (ZBrush), Seam-Änderung (Maya), abweichende Nachbarzahlen (C4D) machen sie ungültig oder partiell [Q10][Q20][Q21].
4. **Mehrdeutigkeit bei regelmäßiger Topologie.** Nachbarschafts-Hashing scheitert an Würfel/Kugel (Blender [Q3][Q4]); ZBrush scheitert bei Mehrachsensymmetrie [Q21].
5. **Korrespondenz ≠ Spiegeloperation.** Korrespondenz kann topologisch sein, die Spiegeloperation braucht trotzdem eine geometrische Ebene/Pivot (Modo-Bericht [Q16], Modo-Doku „keine lokale Symmetrie" [Q15]).
6. **Re-Symmetrisieren mit Erhalt von Vertex-Reihenfolge/UVs** — in Blender und Max laut Nutzern nicht nativ [Q5][Q9c].
7. **Tool-Abdeckung.** Globale Systeme müssen jedes Tool einzeln integrieren; Release Notes zeigen einen andauernden Strom von Symmetrie-Fixes (C4D 2025.3, 2026.1 [Q19]).
8. **Verdeckte Doppelwahrheit bei M-A.** Die Quelle kann Defekte enthalten (Doubles, Vertices knapp neben der Ebene), die erst nach Apply sichtbar werden [Q26]. [INTERPRETATION] Ähnlich der „zwei Wahrheiten"-Spannung, die `CHARACTER_SYSTEMS_RESEARCH.md` bei ngSkinTools beschreibt (O-06).

---

## 8. Konzeptionell besonders interessante Ansätze

Keine Empfehlung — nur Ideen, die für spätere Diskussion auffallen [SCHLUSS]:

1. **Naht als Topologie-Element (Wings).** Die Mittellinie ist eine versteckte Fläche im Netz. Die Ebene wird aus ihr berechnet, Operationen behandeln sie explizit (Extrude löst angrenzende Faces in sie auf). Keine Toleranz nötig. Offene Frage: Was passiert bei nicht-planaren oder nicht-einfachen Nähten?
2. **Ebene gegen den Vorher-Zustand verankern (Wings `mirror_flatten(OldWe, We)`).** Eine Operation darf die Referenzebene nicht mitverschieben. Kleines Detail, aber eine direkte Antwort auf „Drift in langen Sessions".
3. **Weiche Naht-Zone (Maya Preserve Seam + Falloff).** Schutz nicht als Wand, sondern als Gradient.
4. **Naht deklarieren und speichern (C4D „Symmetry Selection"-Tag, Modo Selection Set, Maya Seam-Edge pro Blendshape).** Symmetrie wird zu einem *Objektzustand*, nicht zu einer Laufzeit-Vermutung.
5. **„Fail loud" statt „fail silent" (Maya, ZBrush).** Symmetrie abschalten oder Farbe wechseln, sobald die Voraussetzungen verletzt sind — im Gegensatz zu Wings `validate_mirror` (still auf `none`).
6. **Weld-Ergebnis: Mittelwert vs. Projektion (C4D „Symmetrical").** Eine kleine Option, die eine grundlegende Designfrage sichtbar macht: Soll die Form oder die Naht gewinnen?
7. **Zwei Korrespondenz-Strategien nebeneinander (C4D Planar mit/ohne Clamp).** „Immer einen Partner, evtl. falsch" vs. „nur korrekte Partner, evtl. keinen".
8. **Korrespondenz als Datenattribut (Houdini „Use Mapping", Max Symmetry Tools, polySymmetry).** Macht Symmetrie auf abhängige Daten (Weights, Morphs, UVs) übertragbar und schließt an ARCH-02 an.
9. **Virtuelle Selektion (C4D).** Die gespiegelte Selektion ist ausdrücklich nicht gespeichert, sondern abgeleitet — dieselbe Idee wie M-A, nur für Selektion statt Geometrie.

**Bezug zu vorhandenen Mirai-Bastel-Dokumenten (nur Verweis, keine Ableitung):**
- ROADMAP ARCH-02 (Topology Identity / Provenance / Remapping) behandelt dieselbe Problemklasse wie M-D: Was passiert mit gespeicherter Korrespondenz bei Topologieänderung?
- `docs/research/NWORLD_ARCHAEOLOGY.md` / `MIRAI_SYSTEMS_1999.md`: Wie Mirai selbst Symmetrie handhabte, wurde in diesem Durchgang **nicht** untersucht [OFFEN].

---

## 9. Offene Fragen / Unsicherheiten

**Quellenlücken**

- Genaue Einführungsversionen fehlen für: Blender Topology Mirror, Symmetrize, Snap to Symmetry; Max Symmetry Modifier; C4D Symmetry-Objekt; Wings Virtual Mirror; Modo Topology-Option. Die Generationen-Tabelle (§2.2) ist daher eine Reihenfolge, keine Chronik.
- Mayas topologischer Algorithmus ist nicht offiziell beschrieben; „Traversierung von der Seam-Edge" ist [INTERPRETATION] aus Doku-Voraussetzungen und dem polySymmetry-Plugin.
- Max 2021/2022 Symmetry-Modifier-Neuimplementierung: nur Nutzerbericht, keine offiziellen Release Notes geprüft.
- Silo: nur Community-Aussagen.
- Mirai / N-World / Nendo: Symmetrie-Handhabung nicht untersucht.
- Blender: Welche Topologie-Tools heute Edit-Mode-Symmetrie unterstützen, nicht systematisch geprüft.

**Technische Unsicherheiten**

- Ob Toleranzen heute im Objekt-Maßstab relativ oder absolut sind, wurde nicht geprüft (relevant, weil Max-2022-Nutzer bei kleinen Assets Probleme melden [Q9b]).
- Wie Systeme mit **UV-Nähten entlang der Mittellinie** umgehen (Blender Mirror-Mod. hat UV-Offsets [Q1]), wurde nicht vertieft.
- Wie Korrespondenz bei **mehreren Inseln / mehreren Objekten** aufgebaut wird (C4D: pro Insel eine Loop [Q20]); andere Systeme offen.

**Fragen, die diese Research bewusst *nicht* beantwortet**

Alle „Was sollte Mirai tun?"-Fragen. Beispiele für spätere Discovery, falls priorisiert — nur als Liste, nicht als Plan:

- Ist für den Artist „eine Hälfte ist Quelle" oder „das Ganze ist Quelle" das natürlichere mentale Modell? (Product-Truth-Frage → M4, nicht durch Research entscheidbar.)
- Welche Stressfälle aus §5 sind im tatsächlichen Mirai-Workflow häufig?

---

## 10. Quellen

Offizielle Doku / Release Notes / Entwickler-Tracker = primär. Foren = als [ANWENDER] gekennzeichnet. Abgerufen 2026-09-23.

**Blender**
- [Q1] Blender Wiki (Archiv), Doc 2.4 / 2.6 Manual — Mirror Modifier. https://archive.blender.org/wiki/2015/index.php/Doc:2.4/Manual/Modifiers/Generate/Mirror/ · https://archive.blender.org/wiki/2015/index.php/Doc:2.6/Manual/Modifiers/Generate/Mirror/ · (IT 2.4) https://archive.blender.org/wiki/2015/index.php/Doc:IT/2.4/Manual/Modifiers/Mesh/Mirror/
- [Q2] Blender 5.2 LTS Manual — Mirror Modifier. https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/mirror.html
- [Q3] Blender 2.81 Manual — Mesh Options (X Mirror, Topology Mirror). https://docs.blender.org/manual/en/2.81/modeling/meshes/editing/mesh_options.html · Archiv-Entwurf: https://archive.blender.org/wiki/2015/index.php/User:Terrywallwork/WorkingOn/Topology_Mirror/
- [Q4] Blender Tracker #81698 — Topology Mirror usage. https://developer.blender.org/T81698
- [Q5] Blender Projects #115725 — Topology Mirror erkennt Vertices nicht (4.0.1). https://projects.blender.org/blender/blender/issues/115725
- [Q6] Blender 5.2 LTS Manual — Snap to Symmetry. https://docs.blender.org/manual/en/latest/modeling/meshes/editing/mesh/snap_symmetry.html
- [Q7] Blender 2.79 Manual — Symmetry (Snap to Symmetry, Symmetrize). https://docs.blender.org/manual/ru/2.79/modeling/meshes/editing/basics/symmetry.html
- [Q25] Blender Tracker T53021 — Mirror + Subdivision. https://developer.blender.org/T53021
- [Q26] Blender Projects #103175 — Clipping verhält sich wie Merge (3.4). https://projects.blender.org/blender/blender/issues/103175
- [Q28] [ANWENDER] Blender Artists 2019 — Symmetrize mesh. https://blenderartists.org/t/symmetrize-mesh/1180511
- [Q29] [ANWENDER] Blender Artists 2019 — Full Symmetrical Editing? https://blenderartists.org/t/full-symmetrical-editing/1195488
- [Q30] [Drittanbieter] Mesh Topology Attribute Creator (Gumroad). https://mmemoli.gumroad.com/l/meshTopologyAttributeCreator

**3ds Max**
- [Q8] Autodesk 3ds Max Help — Symmetry Modifier (2016, 2022, 2024). https://knowledge.autodesk.com/support/3ds-max/learn-explore/caas/CloudHelp/cloudhelp/2016/ENU/3DSMax/files/GUID-EB0B7B9B-117D-4CC3-A966-A3E007E0C68A-htm.html · https://help.autodesk.com/view/3DSMAX/2024/ENU/?guid=GUID-EB0B7B9B-117D-4CC3-A966-A3E007E0C68A · https://docs.autodesk.com/3DSMAX/16/ENU/3ds-Max-Help/files/GUID-EB0B7B9B-117D-4CC3-A966-A3E007E0C68A.htm
- [Q9b] [ANWENDER] Autodesk Community 2021 — Symmetry weld threshold in Max 2022. https://forums.autodesk.com/t5/3ds-max-forum/where-is-symmetry-weld-threshold-in-max-2022/td-p/10236877
- [Q9c] [ANWENDER] Autodesk Community 2024 — Symmetrize ohne Vertex-Order-Änderung. https://forums.autodesk.com/t5/3ds-max-modeling-forum/symmetrize-model-without-changing-vertex-order/td-p/12988679
- [Q22] Autodesk 3ds Max 2012 / 2019 Help — Symmetry Tools Dialog. https://download.autodesk.com/us/3dsmax/2012help/files/GUID-BBAA6BD7-6710-402C-A928-B8DA0618FFA-560.htm · https://help.autodesk.com/cloudhelp/2019/ENU/3DSMax-Modeling/files/GUID-BBAA6BD7-6710-402C-A928-B8DA0618FFA8.htm
- [Q23] PolyBoost 4.0 Feature-Liste (2008, Forum-Repost). https://forum.majidonline.com/threads/polyboost-4-0-for-3ds-max-9-2008.88236/
- [Q27] [ANWENDER] polycount 2010 — Mirror Component Selection 3ds Max. https://polycount.com/discussion/74730/mirror-component-selection-3ds-max
- [Q27b] [ANWENDER] polycount 2011 — Symmetry on non-symmetrical mesh (Max). https://polycount.com/discussion/89879/working-with-symmetry-on-non-symmetrical-mesh-3dsmax

**Cinema 4D**
- [Q17] Maxon Python/C++ SDK — Symmetry Object (Legacy). https://developers.maxon.net/docs/py/2026_2_0/cinema_resource/object/osymmetry.html
- [Q18] Maxon Help S22 — Symmetry Object Properties. https://help.maxon.net/c4d/s22/us/html/OSYMMETRY-ID_OBJECTPROPERTIES.html
- [Q18b] [Händler-Tutorial] Novedge — Efficient Symmetrical Modeling in C4D. https://novedge.com/blogs/design-news/cinema-4d-tip-efficient-symmetrical-modeling-in-cinema-4d
- [Q19] Maxon Release Notes 2025.2, 2025.3, 2026.1. https://support.maxon.net/hc/en-us/articles/19590618695708-Cinema-4D-2025-2-0-April-2-2025 · https://support.maxon.net/hc/en-us/articles/20715350693532-Cinema-4D-2025-3-June-18-2025 · https://support.maxon.net/hc/en-us/articles/24785504728988-Cinema-4D-2026-1-December-3-2025
- [Q20] Maxon Help 2025 — Symmetry (globales System, Planar/Topology/Radial, Limitations). https://help.maxon.net/c4d/2025/en-us/Content/html/Symmetry.html

**Modo**
- [Q15] Foundry Learn — Applying Precision / Symmetry. https://learn.foundry.com/modo/content/help/pages/modeling/symmetry.html
- [Q15b] Foundry Learn Modo 901 — Symmetry. https://learn.foundry.com/modo/901/content/help/pages/modeling/symmetry.html
- [Q16] [ANWENDER] polycount 2016 — Modo topological symmetry not working as expected; symmetry based on edge. https://polycount.com/discussion/172529/modo-topological-symmetry-not-working-as-expected · https://polycount.com/discussion/165139/modo-symmetry-based-on-edge-as-center-when-object-is-off-world-center-position

**Wings 3D**
- [Q12] Wings 3D — Menu Tools (Virtual Mirror). https://www.wings3d.com/?page_id=923
- [Q13] Wings 3D — Menu Face (Mirror-Workflow). https://www.wings3d.com/?page_id=953
- [Q14] Wikibooks — Wings 3D User Manual, Face Operations. https://en.wikibooks.org/wiki/Wings_3D/User_Manual/The_Face_Operations_Menu
- [Q14b] [ANWENDER] Wings-Forum — how to make virtual mirror? https://www.tapatalk.com/groups/nendowingsmirai/how-to-make-virtual-mirror-t6975.html
- [Q14c] [ANWENDER] Wings-Forum — thoughts on virtual mirror. https://www.tapatalk.com/groups/nendowingsmirai/thoughts-on-virtual-mirror-t5112.html
- [Code] Wings 3D Quellcode, https://github.com/dgud/wings — `src/wings_we.erl` (`create_mirror`, `mirror_projection`, `mirror_flatten`, `validate_mirror`, `average_normals`), `src/wings_drag.erl` (`mirror_constrain`), `src/wings_tweak.erl`, `src/wings_face_cmd.erl` (Extrude/Subdiv/Smooth), `src/wings_edge.erl` (Dissolve). Gelesen am 2026-09-23.

**ZBrush**
- [Q21] Maxon ZBrush Docs — Symmetry (Poseable Symmetry). https://help.maxon.net/zbr/en-us/Content/html/user-guide/3d-modeling/sculpting/symmetry/symmetry.html
- [Q21b] [Händler-Tutorial] Novedge — Mirror And Weld. https://novedge.com/blogs/design-news/zbrush-tip-mirror-and-weld-accurate-symmetry-and-clean-center-seams

**Houdini**
- [Q24] [ANWENDER] SideFX Forum 2006 — mirror op / merge verts. https://www.sidefx.com/forum/topic/6411/?page=1#post-30381
- [Q24b] SideFX Docs — Mirror geometry node (20.5, JA). https://www.sidefx.com/ja/docs/houdini/nodes/sop/mirror.html
- [Q24c] SideFX HDK — GEO_MirrorParms. https://www.sidefx.com/docs/hdk/class_g_e_o___mirror_parms.html
- [Q24d] SideFX Docs — Attribute Mirror geometry node (20.5, JA). https://www.sidefx.com/ja/docs/houdini/nodes/sop/attribmirror.html
- [Q24e] [ANWENDER] SideFX Forum — Selection Tool Symmetry (2021); Polygons Editing in SOP (2026). https://www.sidefx.com/forum/post/342315/ · https://www.sidefx.com/forum/topic/104063/

**Maya / Silo / Sonstige**
- [Q10] Autodesk Maya 2016 — Activate or deactivate symmetry. https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2016/ENU/Maya/files/GUID-7EC940BA-4B3A-4DB2-AC6B-8CDBA800EC61-htm.html · Maya LT 2015 — Enable topological symmetry: https://knowledge.autodesk.com/support/maya-lt/learn-explore/caas/CloudHelp/cloudhelp/2015/ENU/MayaLT/files/GUID-23F68E7A-10C5-48C6-8838-0436C2EAD075-htm.html
- [Q10b] Autodesk Maya — Symmetrical editing (2023) / Edit a mesh with topological symmetry (2019). https://help.autodesk.com/cloudhelp/2023/ENU/Maya-Modeling/files/GUID-68206E61-CFF0-4C83-9254-B761C51FED98.htm · https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2019/ENU/Maya-Modeling/files/GUID-EC3CCAFA-DBEB-4733-AF50-467B9EE8B65B-htm.html
- [Q10c] Autodesk Maya 2015 Tech Docs — symmetricModelling. https://help.autodesk.com/cloudhelp/2015/CHS/Maya-Tech-Docs/CommandsPython/symmetricModelling.html · PyMel: https://help.autodesk.com/cloudhelp/2015/JPN/Maya-Tech-Docs/PyMel/generated/functions/pymel.core.general/pymel.core.general.symmetricModelling.html
- [Q10d] Autodesk Maya — Select Tool (Seam Tolerance, Falloff). https://help.autodesk.com/cloudhelp/ENU/MayaCRE-Basics/files/GUID-60FD5F79-AC1D-46DE-B66D-2FBE73E15A30.htm
- [Q10e] Autodesk Maya 2025 — Mirror pose interpolators. https://help.autodesk.com/cloudhelp/2025/ENU/Maya-CharacterAnimation/files/GUID-61218D23-D40E-4E6F-8E31-3D2769392740.htm
- [Q11] Lesterbanks 2014 — Overview Maya 2015 Modeling Improvements. https://lesterbanks.com/2014/03/overview-maya-2015-modeling/
- [Q27c] [ANWENDER] polycount — Trouble with Silo 2.0. https://polycount.com/discussion/comment/924406
- [Q31] [Drittanbieter] polySymmetry Wiki (Ryan Porter, 2017). https://github.com/yantor3d/polySymmetry/wiki
- Mudbox (Kontext Topologie-Symmetrie-Definition): https://help.autodesk.com/cloudhelp/2018/ENU/Mudbox/files/GUID-CFBC25BF-D8FB-45F6-B601-892381F5B97F.htm
