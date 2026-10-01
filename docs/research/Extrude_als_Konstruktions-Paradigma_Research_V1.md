# Extrude als Konstruktions-Paradigma — Research V1

Sep 30, 2026 · @Manu

## 0. History Awareness (M1), Context Check (M2), Modus

**Modus (M5):** Discovery, Typ-B-Research. Keine Implementierung, kein Code, keine Architecture Decision, keine Empfehlung „Mirai soll X bauen“. Ablageort-Vorschlag im Repo: `docs/research/topology/` oder `docs/research/` (Entscheidung bei Manu).

**Evidenzstufen** wie in `docs/research/README.md` und `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md`: **FAKT** (Quelle), **BEOBACHTUNG** (Code/Test/Tutorial direkt gesehen), **KONSENS** (Community, nicht einzeln geprüft), **INTERPRETATION** (Schluss), **HYPOTHESE** (unbelegt).

### 0.1 Existenzprüfung — Repository `main` @ `9e1a093` (2026-09-30)

| Existiert | Wo | Bedeutung für diese Research |
| --- | --- | --- |
| Extrude-Tool (Playground) | `playground/topology_tools/extrude.py` | Region-Extrude zusammenhängender Faces, Drag nur entlang Normale, Lifecycle begin → update → commit/cancel, **ein** Snapshot-History-Schritt, neue Faces nach Commit ausgewählt. Das ist bereits eine Mini-Session (Topologie bei Begin, Position beim Drag). |
| Extrude-Verdikte | Projektgedächtnis (kein Repo-Dokument gefunden) | Mulde mit Boden reicht; Einzel-Extrude pro Face wird gebraucht (Umschaltung offen); Tippen ohne Bewegung bewirkt nichts (Schwellenwert). Edge/Vertex-Extrude später; Zahleneingabe braucht zuerst eine allgemeine numerische Eingabe. Werden hier **nicht** neu verhandelt. |
| Erinnern vs. Wiedererkennen, Rezepte | `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §16.2.6, §16.2.7, H7, H8, E1, T5 | Blender Adjust Last Operation, Maya Node-History, MESHmachine, Houdini Digital Assets, Autocomplete-Sculpting sind dort schon belegt. Dieses Dokument vertieft **H8 („Rezept = Kette mit Löchern“) für Extrude** und wiederholt §16 nicht. |
| Operationen als reproduzierbare Aktionen | `docs/research/MIRAI_SYSTEMS.md` (Design Direction) | Input → Operation → Change Set → State; Makros „grundsätzlich möglich“. Ausgangsthese, nicht geprüft. |
| Undo über Snapshots | AD-001, `MeshStateCommand`, AD-SYM-02 | Keine ID-Wiederverwendung. Undo = vollständiger Vorher/Nachher-Zustand. **Konsequenz hier:** Jedes Neu-Abspielen einer Topologie-Operation erzeugt neue IDs. |
| Session-Muster | AD-017 FINAL, Knife-/Q5-Lab | In-Session-Undo = letzter Schnitt, Esc = Session verwerfen, Commit = ein History-Schritt. Präzedenz für jede „Extrude-Session“. |
| Provenienz | ROADMAP ARCH-02 (offen), AD-017 B5, `KNIFE_CROSS_FACE_DISCOVERY.md` §7, Rigging-Experiment FINDINGS-3C | Operationskontext ist der verlässliche Weg (`split_edge(t)`); Snapshot-Heuristik nur Fallback. |
| Symmetrie als eine Absicht | README, AD-SYM-02 | „Eine Absicht → bekannter Operationskontext“. Symmetry Lab: Operationskontext primär, Position/Topologie als unabhängige Prüfung. |
| Temporäre Artikulation (EX-A) | `playground/experiments/articulation/` | Biegen mit Pivot + Falloff, ohne History, exakt rücksetzbar. Relevant für Fall B (Ellbogenwinkel). |
| Composition / Residue | `docs/design/artist_playground/RESEARCH_MAP.md` | „Select face → Extrude → Move → Extrude again“ steht dort schon als Spielsequenz. Jede Session-Frage gehört in dieses UX-System. |
| Wunschliste | `Artist Toolbox - Einkaufsliste.md` | „repeat last operation“, „construction history“, „schnelle Wiederholung“ — unbewertet. |

**Verworfenes:** Keine Konstruktions-History, kein Makro-System und kein Repeat wurde bisher geprüft oder abgelehnt. Die Kernfrage berührt keinen verworfenen Ansatz.

**Evidenz-Konsequenz:** Kein validiertes System wird ersetzt. Das bestehende Extrude-Tool und das laufende Extrude-Work-Package bleiben unberührt.

### 0.2 Context Check — meine Annahmen (nur korrigieren, wenn falsch)

1. Die frühere Extrude-UX-Vergleichsrunde (Wings, Blender, Max, Maya, Modo, Cinema 4D) liegt nicht als Datei im Repo. Dieses Dokument ergänzt sie, es ersetzt sie nicht.
2. Das Playground-Extrude kann heute kein Scale/Rotate in derselben Geste, keinen Einzel-Extrude, keine Zahleneingabe, kein Repeat.
3. `src/` enthält kein Extrude. Im Code gibt es kein Konzept „Kette“ oder „Konstruktion“.
4. Mirai hat noch kein Dissolve (laut §16.0 des Workflow-Dokuments).

## 1. Executive Summary

Die wichtigste Erkenntnis: **Die meisten „nachträglich ändern“-Wünsche beim Extrudieren von Gliedmaßen sind Form-Änderungen, keine Topologie-Änderungen — und Form-Änderungen haben das berüchtigte Referenzproblem gar nicht.** Das ist eine HYPOTHESE, aber sie ordnet den ganzen Design Space.

1. **Extrude ist fast nie allein.** In realen Workflows ist Extrude die erste Hälfte einer Geste: Extrude, dann Position, oft Skalierung oder Rotation. Mehrere DCCs haben das in ein Werkzeug gepackt: Maya (Translate/Rotate/Scale/Taper/Twist/Divisions im Extrude-Node), LightWave Multishift (Inset + Shift, Rechtsklick = nächster Schritt), Wings-Plugin Sweep (Extrude + Drehen + Skalieren in einer Geste). **FAKT.** Die „Extrude-Session“ ist historisch etabliert; offen ist ihr Umfang, nicht ihre Existenz.
2. **Zwei historische Linien.** (a) Rezept ist die Wahrheit: XSI, 3ds Max, Maya, Modo MeshOps, Houdini. (b) Mesh ist die Wahrheit, plus Undo und Wiederholen: Wings (direkter Nachfahre der Mirai-Linie), LightWave Modeler, SketchUp, Plasticity. **FAKT/KONSENS.**
3. **Linie (a) hat überall dasselbe Problem.** Spätere Operationen zeigen auf Komponenten per Index; ändert sich frühere Topologie, treffen sie die falschen Elemente. Belegt bei 3ds Max (Topology-Dependence-Warnung), Houdini (Forum-Fall mit exakt einer Extrude-Kette), Blender (Designnotizen zum Tweak-Modifier), Maya (Metadaten-Indizes). In CAD heißt das „Persistent Naming Problem“ (Kripac 1997; FreeCAD erst 1.0). **FAKT.**
4. **Die Antworten der Praxis:** Einfrieren (XSI Immediate Mode, Max Collapse, Maya Delete History) als Gewohnheit, oder Rollen-Referenzen: Houdini Front/Side-Gruppen, Modo „Select by Previous Operation“, Blender Extrude-Mesh-Node mit Top/Side-Ausgängen. **FAKT.**
5. **Mirai hat die billigste Rollen-Referenz schon:** Nach dem Extrude sind die neuen Top-Faces ausgewählt. „Die aktuelle Auswahl“ *ist* damit „das Ergebnis des vorigen Schritts“. Wiederholen auf der aktuellen Auswahl (Wings Repeat) ergibt automatisch eine rollenbasierte Kette. **INTERPRETATION.** Folge: Residue-Design (was nach einer Operation ausgewählt ist) ist zugleich das Referenzsystem jeder Automatisierung.
6. **Eine Extrude→Move→Rotate-Kette ist strukturell eine Kette lokaler Rahmen — wie eine FK-Kette.** Ellbogenwinkel oder Oberarmlänge später ändern heißt einen Rahmen drehen/strecken, nicht Topologie neu abspielen. **HYPOTHESE.** Möglicherweise löst das bestehende Artikulations-Experiment (EX-A) Fall B schon ohne jede gespeicherte Kette.
7. **Mirais Core spricht für „Mesh ist die Wahrheit, Kette ist Annotation“.** Snapshot-Undo, AD-001 (neue IDs bei jedem Neu-Abspielen) und Direct-Modeling-Ethos passen dazu. „Rezept ist die Wahrheit“ (Option D) hätte ARCH-02 vollständig zur Voraussetzung und kehrt das History-Modell um. **INTERPRETATION.**
8. **Wiederholen ist billig und bewährt** (Wings Repeat/Repeat Args/Repeat Drag, SketchUp-Doppelklick, Max „Apply and Continue“). Aufzeichnen und Parametrisieren sind möglich, wenn Schritte über Rollen und lokale Rahmen statt über IDs und Weltkoordinaten verknüpft sind. **INTERPRETATION.**

**Design Space (§12):** A Simple Extrude + Repeat · B Extrude-Session · C Leichte Konstruktionsketten (Mesh ist Wahrheit) · D Volle Construction History · E Hybrid. Keine Empfehlung.

**Billigste nächste Erkenntnis (§14):** E1-Variante „Extrude-Ketten-Mitschnitt“ (passiv) und ein 10-Minuten-Selbstversuch mit der vorhandenen Artikulation (X4a). Beide kosten fast nichts und entscheiden, ob Option C überhaupt einen Anwendungsfall hat.

**Invariante aus der Aufgabe:** Mirai darf nie still eine andere Topologie erzeugen. In der Unterscheidung dieses Dokuments heißt das: Form-Edits ändern Topologie per Definition nicht; jeder topologie-ändernde Edit muss seinen Konflikt zeigen, bevor er gilt.

## 2. Reale Artist-Workflows

Dieselbe Absicht „einen Arm bauen“ wird in mindestens drei verschiedenen Operationsketten ausgeführt. Ein Konstruktionssystem, das nur eine davon abbildet, deckt die anderen nicht ab. **BEOBACHTUNG** (Tutorials).

**Methodenkritik:** Manus eigene Ketten sind noch nicht gemessen (E1 ist ungespielt). Die Tabellen unten sind Rekonstruktionen aus Tutorials und Handbüchern, also **INTERPRETATION**, bis E1 sie bestätigt oder widerlegt.

### 2.1 Drei Schulen für Gliedmaßen

- **Schule S — Segment-Extrude.** Pro Abschnitt ein eigener Extrude: Oberarm, vor dem Ellbogen, Ellbogen, nach dem Ellbogen, vor dem Handgelenk, Handgelenk, Hand. Dann die Handfront teilen, vier Finger extrudieren, Daumen seitlich herausziehen und in Position drehen ([SimplyMaya-Forum, 2002](https://simplymaya.com/forum/showthread.php?p=8277)).
- **Schule L — Lang-Extrude plus Schnitte.** Ein langer Extrude vom Schulter-Face bis zum Handgelenk, dann mit dem Knife Querschnitte setzen und Punkte formen. Hand: Extrude aus dem Handgelenk, mit Knife unterteilen, vier Polygone als Finger extrudieren, Fingergelenke mit zwei Schnitten, Finger am Ende in eine entspannte Haltung biegen ([highend3d-Tutorial](https://highend3d.com/maya/tutorials/modeling/polygon/c/subdivision-modeling-of-a-human/page/2)).
- **Schule P — Primitive statt Extrude.** Hand oder Bein aus einem Zylinder blocken, Divisions setzen, Ellbogen biegen, Pivot setzen, dann per Bridge an den Körper hängen; am Ende „mirror and delete history“ ([Kursbeschreibung, Udemy](https://www.udemy.com/course/realistic-character-modeling-for-game-in-maya-and-zbrush/)).

**INTERPRETATION:** Schule S ist eine reine Extrude-Kette. Schule L hat Topologie-Operationen *mitten* in der Kette (genau die Fälle D und E aus §8) — nicht als Ausnahme, sondern als Methode. Schule P ersetzt die Kette durch ein parametrisches Primitive plus Biegen. Das Biegen am Ende (L und P) ist Posing als Modellierschritt.

### 2.2 Workflow-Tabelle

| # | Aufgabe | Start-Auswahl | Typische Kette | Bedeutsame Artist-Entscheidungen | Mechanische Wiederholung | Wo Richtungswechsel nötig ist |
| --- | --- | --- | --- | --- | --- | --- |
| W1 | Gliedmaße aus Torso (S) | 1 Schulter-Face (oder 2×2) | (E → M → S → R) × n | Länge, Richtung, Querschnitt je Segment | Extrude neu aufrufen, Pivot/Achse neu setzen, Ergebnis neu greifen | an jedem Gelenk |
| W2 | Gliedmaße (L) | 1 Face | E lang → Knife/Loop × n → Punkte verschieben | Gesamtlänge, Lage der Schnitte, Form | Schnitte in ähnlichem Abstand | Lage jedes Schnitts |
| W3 | Finger / Zehen | n Faces an der Handfront | Einzel-Extrude → M → S, dreimal je Finger | Länge je Finger, Spreizung, Daumen gesondert | **dieselbe Kette pro Finger** | Daumen, Längenunterschiede |
| W4 | Hand / Fuß | Handgelenk-Face | E → S (ungleichmäßig) → E; Fuß: E nach vorn → flach skalieren → E Zehen | Proportion des Blocks | wenig | Fußspitze, Ballen |
| W5 | Mechanisches Teil verlängern | Deckfläche | E exakt → Inset (E mit Distanz 0 + S) → E | **exakte Maße** | Inset/Extrude-Paare | kaum, eher Zahlen |
| W6 | Architektonischer Vorsprung (Sims, Gesims) | viele Faces | Inset → E nach außen/innen | Tiefe, Breite | **gleiche Distanz auf vielen Faces** | selten |
| W7 | Röhre, Ast, Tentakel | End-Face | (E → M → R → S) × n, Zweig = neue Kette aus Seiten-Face | Krümmung, Verjüngung | Schritte mit gleichem Winkel/Faktor | Verzweigungen |
| W8 | Gestufte / verjüngte Form | Deckfläche | (E → S) × n oder (Inset → E) × n | Stufenhöhe, Faktor | **fast alles** | kaum |
| W9 | Proportions-Blocking | wenige Faces | wenige E, viel Verschieben | Proportionen | wenig | ständig: Proportionen werden oft geändert |
| W10 | Wiederholte Strukturen (Rippen, Zähne, Knöpfe) | viele Einzel-Faces | dieselbe Mikro-Kette | Muster, Größe | **identische Kette auf vielen Stellen** | selten |
| W11 | Flächen durch wiederholten Edge-Extrude (Ohr, Saum, Rand) | Randkanten | (Edge-E → M) × n | Verlauf des Randes | Aufruf pro Streifen | laufend |

E = Extrude, M = Move, S = Scale, R = Rotate. W11 setzt Edge-Extrude voraus, den Mirai noch nicht hat.

### 2.3 Was daraus folgt

- **Artist-Entscheidungen** sind: wo es losgeht (Auswahl), wie weit und wohin, welcher Querschnitt, welche Gelenkwinkel, wie viele Segmente, welche Faces einzeln. **INTERPRETATION.**
- **Mechanik** ist: Werkzeug neu aufrufen, neu greifen, Constraint/Pivot neu setzen, das Ergebnis neu auswählen, identische Ketten auf Fingern oder Zähnen wiederholen. **INTERPRETATION.**
- In W1, W3, W7, W8, W10 dominiert die Mechanik. In W2 und W5 sind Topologie-Operationen eingewoben. In W9 dominieren **nachträgliche Änderungen** — dort wären die Fälle A und B aus §8 am häufigsten. **HYPOTHESE.**
- Proportionsänderungen im Blocking werden in der Praxis meist direkt gemacht: Vertex-Gruppen auswählen und verschieben oder skalieren, oft mit Soft Selection. Nicht durch Rückkehr in eine History. **KONSENS**, nicht einzeln geprüft.

## 3. Wiederkehrende Extrude-Muster

Die Muster zerfallen in drei Klassen, und nur eine davon ist ein Kandidat für echte Automatisierung: **Wiederholung mit gleichen Parametern.** Wiederholung mit wechselnden Parametern braucht eher eine flüssige Session; bedeutsame Einzelentscheidungen bleiben manuell. **INTERPRETATION.**

### 3.1 Musterkatalog

| Muster | Typischer Einsatz | Entscheidungsgehalt | Mechanikgehalt | Wiederverwendbar? | Wo es das als *ein* Werkzeug gibt |
| --- | --- | --- | --- | --- | --- |
| E → M (entlang Normale) | Grundgeste | 1 Wert (Distanz) | gering | trivial | fast überall; Mirai-Playground heute |
| E → M → S | Stufe, Verjüngung, Finger | 2 Werte | mittel | ja, wenn Werte gleich bleiben | Maya Extrude-Node (Scale), LightWave Multishift (Shift + Inset) |
| E → M → R | Gelenk, Biegung | Achse + Winkel; **Pivot ist die schwere Frage** | mittel | nur bei gleichem Winkel (Locken) | Maya Extrude-Node (Rotate), Wings Sweep |
| E mit Distanz 0 → S (= Inset) | Detail-Vorstufe | 1 Wert | gering | ja | Max/Blender Inset, Modo Bevel |
| (E → S) × n | Stufen, Treppen, Pyramiden | insgesamt 1–2 Werte | **hoch** | **ja** | Maya Divisions + Taper |
| (E → M → R) × n, gleiche Werte | Tentakel, Locke, Schwanz | 2–3 Werte | **hoch** | **ja** | Maya Extrude entlang Kurve (Taper, Twist), Wings Sweep + Repeat Drag |
| (E → M → R) × n, wechselnde Werte | Arm, Bein | je Gelenk neu | mittel | eher nein | — |
| E → Knife × n → M | Schule L | Lage der Schnitte | mittel | selten | — |
| Einzel-E → M → S auf n Faces | Finger, Stacheln | wenige Werte, oft je Face leicht anders | **hoch** | teilweise | Maya „Keep Faces Together“ aus, Blender „Individual“ |

### 3.2 Drei Klassen

1. **Wiederholung mit gleichen Parametern** (Stufen, Locken, Rippen, Sims auf vielen Faces). Eine Entscheidung, viele Ausführungen. Vorbilder: Wings „Repeat Drag“, SketchUp Doppelklick, Max „Apply and Continue“ (§4). **Kandidat für Automatisierung.**
2. **Wiederholung mit wechselnden Parametern** (Arm, Bein, Finger unterschiedlicher Länge). Die Struktur wiederholt sich, die Werte nicht. Hier hilft eine Session, die das Neu-Aufrufen und Neu-Greifen spart, mehr als ein Makro. **INTERPRETATION.**
3. **Bedeutsame Einzelentscheidungen** (erster Extrude einer Gliedmaße, Lage eines Gelenks, Proportionen). **Bleiben manuell.**

### 3.3 Kann der Artist eine Sequenz selbst zur „Konstruktion“ machen?

Ja — in der Geschichte der DCCs gibt es das seit Jahrzehnten, aber fast immer als *Skript*, nicht als Modellierkonzept. 3ds Max: Text aus dem Macro Recorder auf eine Werkzeugleiste ziehen erzeugt einen Button, der die aufgezeichnete Abfolge ausführt. Maya: Befehle aus der Script-Editor-History als Shelf-Button speichern. XSI: Befehle als Script Command auf eigene Toolbars. **FAKT** (§4, Quellen).

**Das Problem dieser Aufzeichnungen:** Sie halten fest, *was* getan wurde, oft mit konkreten Komponenten, nicht *worauf es sich bezog*. XSI warnt ausdrücklich, dass eine im Immediate Mode abgespielte Befehls-History andere Ergebnisse liefern kann. **FAKT.** Dass Recorder konkrete Komponentennamen oder Indizes festschreiben, ist **KONSENS**, hier nicht an Primärquellen geprüft. Die Brücke zu einem brauchbaren Artist-Rezept sind Rollen-Referenzen (§7) und lokale Rahmen (§8) — Details in §9.

## 4. Historischer DCC-Vergleich

Jedes untersuchte System hat eine klare Haltung zur Frage „ist das Rezept oder das Mesh die Wahrheit?“ — und jedes Rezept-System hat einen Notausgang zum Einfrieren eingebaut. Alle Aussagen sind mit Primärdoku belegt, wo nicht anders markiert; Links in der Quellenliste am Ende.

### 4.1 Softimage / XSI — Operator Stack mit Absichts-Regionen

- **Philosophie:** Jede Modifikation ist ein Operator im Stack; die Ausgabe eines Operators ist die Eingabe des nächsten; man kann jederzeit zurückgehen, ändern oder löschen. **FAKT.**
- **Besonderheit:** Der Stack ist in vier Regionen geteilt — Modeling, Shape Modeling, Animation, Secondary Shape Modeling. Der Artist wählt vor der Operation einen Construction Mode und ordnet sie so nach seiner Absicht ein; falsch einsortierte Operatoren lassen sich verschieben. **FAKT.**
- **Notausgang:** Freeze entfernt den Stack. **Immediate Mode** friert nach jeder Operation ein; begründet wird das mit kleineren, schneller aktualisierenden Szenen, gerade beim Verschieben von Punkten und Extrudieren. Im Immediate Mode öffnet jede Operation ihren Property Editor mit OK/Cancel — also eine Mini-Session. **FAKT.**
- **Warnung der Doku:** Wer Befehle aus der History abspielen will, soll Immediate Mode nicht nutzen, weil Parameteränderungen im offenen Editor nicht geloggt werden und das Abspielen dann anders ausgeht. **FAKT.**
- **Cluster:** Laut einem Softimage-Entwickler (Mailingliste 2011) führen Topologie-Operatoren bestehende Cluster automatisch nach, wenn Komponenten hinzukommen oder wegfallen. **FAKT** (Entwickleraussage, nicht Handbuch).
- **Lehre:** Die Regionen sind das einzige gefundene History-Modell, das Modellieren, Shapes und Animation *nach Absicht* trennt — nah an Mirais Vision „model → rig → back to modeling“. Immediate Mode ist eine bewusst wählbare Grenze zwischen „editierbar“ und „eingefroren“. **INTERPRETATION.**
- **Nicht kopieren:** Den Artist den Stack verwalten lassen (Reihenfolge, Region, Freeze-Zeitpunkt) als Normalfall.

### 4.2 3ds Max — Modifier Stack, Edit Poly und Topologie-Abhängigkeit

- **Philosophie:** Modifier Stack; Editable Poly (direkt) vs. Edit Poly Modifier (im Stack). **FAKT.**
- **Das Kernproblem, offiziell benannt:** „Topology-dependent modifiers“ arbeiten auf expliziten Vertex- oder Face-Nummern. Ändert man weiter unten im Stack die Topologie, verfälscht man ihre Ergebnisse; eine Warnung meldet das. **FAKT** (Glossar).
- **Praxis:** Community-Rat, Edit-Poly-Modifier so früh wie möglich zu kollabieren, weil spätere Modifier weiter auf „Vertex 1“ zeigen, der inzwischen woanders liegt. **KONSENS** (Polycount).
- **Live bis Commit:** Im Edit Poly Modifier bleibt die aktuelle Operation über ihren Caddy offen, bis man sie mit Commit bestätigt oder abbricht. **FAKT.**
- **Apply and Continue:** Im Extrude-Caddy wendet dieser Knopf die Einstellungen an und behält sie für die Vorschau auf die nächste Auswahl. **FAKT.**
- **Press/Release-Shortcuts:** Eine Taste halten überlagert kurz die laufende Operation mit einer anderen; beim Loslassen geht es zurück. **FAKT.** (= Composition im Sinne der Research Map.)
- **User Tools:** Text aus dem Macro Recorder auf eine Toolbar ziehen erzeugt einen Button für die aufgezeichnete Abfolge. **FAKT.**
- **Lehre:** Warnen statt still falsch rechnen ist besser als nichts — aber die Warnung kommt nach dem Schaden. „Apply and Continue“ ist Wiederholung ohne History.
- **Nicht kopieren:** Gestapelte Edit-Poly-Modifier, die per Index adressieren.

### 4.3 Maya — Dependency Graph als lineare Construction History

- **Philosophie:** Upstream vom Mesh-Node kann eine einzelne lineare Kette von DG-Nodes existieren; jeder Node reicht sein Mesh weiter. Vertex-Tweaks verkomplizieren das. **FAKT** (SDK-Doku).
- **Extrude als parametrisierte Geste:** `polyExtrudeFacet` trägt u. a. translate, rotate, scale, localTranslate, divisions, taper, twist, thickness, offset, keepFacesTogether, inputCurve und einen worldSpace-Schalter. **FAKT.** Ein Node ist also schon „Extrude → Move → Rotate → Scale“ in einem.
- **Notausgang:** Delete History bzw. Delete Non-Deformer History (von Autodesk selbst als Gegenstück zu XSIs Freeze beschrieben). **FAKT.** Kursbeschreibungen zeigen „delete history“ als Routine-Schritt. **BEOBACHTUNG.**
- **Indizes und Topologie:** Metadaten-Indizes ändern sich durch die History nicht; ändert sich die Topologie, kann die Zuordnung zum ursprünglichen Element verloren gehen. **FAKT.**
- **User Tools:** Befehle aus der Script-Editor-History als Shelf-Button speichern. **FAKT.**
- **Lehre:** Transform-Parameter im Extrude-Node sind bewährt. Gleichzeitig zeigt der Node mit Dutzenden Flags (Schwerkraft, Magnet, Zufall …), wie ein Werkzeug zum „God Tool“ wächst.
- **Nicht kopieren:** Komponenten-Eingaben per Index.

### 4.4 Modo — Tool Pipe und MeshOps

- **Philosophie (zweigleisig):** Direct Modeling ist laut Doku „destruktiv“ — man kann frühere Operationen nicht ändern und spätere behalten. Seit 10.1 gibt es zusätzlich einen prozeduralen Stack aus Mesh Operations, Tool Operations (direkte Werkzeuge verpackt) und Selection Operations. **FAKT.**
- **Tool Pipe:** Werkzeuge lassen sich mit Falloffs und Sub-Tools (z. B. Symmetrie) kombinieren. **FAKT.** Das ist ein vom Artist zusammengesetztes Werkzeug ohne Skript.
- **Referenzen:** Selection Ops enthalten „Select by Index“ (Standard), „Select by Previous Operation“ (Quell-Operation + benannter Ausgang, etwa „Front“) und „Assign Selection Set“, das über spätere Mesh-Edits erhalten bleibt. **FAKT.**
- **Fragilität:** Ein offizieller Bug (Modo 11–13): Nach dem Duplizieren zeigt „Select by Previous Operation“ weiter auf die Operation des Originals. **FAKT.**
- **Lehre:** Benannte Rollen-Ausgänge („Front“) sind genau die Referenz, die Ketten robust macht.
- **Nicht kopieren:** Zwei parallele Modellierwelten (direkt vs. prozedural), zwischen denen der Artist wählen und umdenken muss.

### 4.5 LightWave Modeler — Werkzeug bleibt live, Rechtsklick = nächster Schritt

- **Philosophie:** Werkzeugzentriert und ohne Construction History. **KONSENS**, in dieser Session nicht an Primärdoku geprüft.
- **Bevel:** Ziehen formt die Fase; die Operation wird wirksam, wenn man das Werkzeug abwählt oder ein anderes nimmt; Klick in einen leeren Bereich bricht ab. **FAKT.**
- **Multishift:** Inset und Shift in einem Werkzeug; Linksziehen bewegt, **Rechtsklick erzeugt einen neuen Shift**; wählbarer Shift entlang gemittelter statt lokaler Normale. **FAKT.**
- **Extrude:** Anzahl „Sides“ für segmentierte Formen. **FAKT.**
- **Lehre:** Eine mehrstufige Session ohne jede History ist seit Jahrzehnten ein funktionierendes Muster.

### 4.6 Blender — Adjust Last Operation, Modifier, Geometry Nodes

- **Adjust Last Operation:** bereits in `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §16.2.6 belegt; nicht wiederholt.
- **Extrude Mesh Node:** hat die Ausgänge **Top** und **Side** als Boolean-Felder, dazu dokumentierte Regeln, wie Attribute auf neue Elemente übertragen werden (Mittelwert, Kopie). „Individual“ extrudiert jedes Face einzeln. **FAKT.**
- **Tweak-Modifier (Designnotiz):** Die Entwickler beschreiben das Picking-Problem offen: indexbasiert bricht bei geänderter Topologie, ID-basiert bricht, wenn vorherige Modifier Anzahl oder Reihenfolge ihrer Duplikate ändern; vorgeschlagen werden Kombinationen. **FAKT.**
- **Lehre:** Rollen-Ausgänge plus explizite Propagationsregeln sind das saubere Vorbild für „was wird aus Daten auf neuen Elementen“.

### 4.7 Houdini — Graph, Gruppen als Rollen

- **PolyExtrude:** kann Front-, Back- und Side-Gruppen ausgeben, damit spätere Nodes gezielt nur diese Polygone treffen. **FAKT.**
- **Der Fall aus der Aufgabe, real:** Ein Nutzer baut eine Kette aus PolyExtrudes an einer Röhre. Weil der zweite Extrude per Prim-Nummer wählt, trifft er nach Ändern der Spaltenzahl oben nicht mehr das End-Face. Ein SideFX-Mitarbeiter rät: Front-Gruppe ausgeben und im nächsten Extrude verwenden. **FAKT** (Forum 2017).
- **Der Gegenpreis:** Ein anderer Nutzer merkt an, dass Gruppen für einfache Operationen überflüssig seien; Polygone direkt auswählen und Zahlen eintippen sei schneller. **BEOBACHTUNG** (Forum 2025). Das ist der Kern-Trade-off dieses Dokuments in einem Satz.
- Digital Assets (promotete Parameter): siehe §16.2.7 im Workflow-Dokument.

### 4.8 Wings 3D — der Mirai-Nachfahre wählt Wiederholen statt History

- **Philosophie:** Im Edit-Menü stehen an History-Funktionen nur Undo/Redo und Repeat. **FAKT.** Wings stammt über Nendo aus der Mirai-Linie (Repo: `ARCHAEOLOGY_FINDINGS_001.md`).
- **Drei Stufen des Wiederholens:** Repeat (letzter Befehl), Repeat Args (letzte Argumente), Repeat Drag (Befehl *und* Ziehbetrag — ein Extrude um drei Einheiten wird um drei Einheiten wiederholt). Das Menü zeigt, ob der Befehl im aktuellen Auswahlmodus wiederholbar ist; ohne Auswahl ist nichts wiederholbar. **FAKT.**
- **Sweep (Optigon-Plugin):** Ziehen extrudiert, Linksziehen dreht um eine gewählte Achse, Ctrl+Rechtsziehen skaliert, Rechtsziehen dreht um die Normale — alles in einer Geste; D und Shift+D wiederholen Sweep. **FAKT** (Forum 2012, Nutzerbeschreibung).
- **Lehre:** Die direkte Mirai-Nachfolge hat „Mesh ist Wahrheit + Wiederholen“ gewählt. Wiederholen wirkt auf die **aktuelle Auswahl** — und nach einem Extrude ist das das Ergebnis. **INTERPRETATION.** (Wie Mirai selbst History löste, ist offen: `MIRAI_SYSTEMS_1999.md` §10.)

### 4.9 SketchUp — Doppelklick wiederholt die Distanz

- Push/Pull: Nach einem ersten Zug wiederholt ein Doppelklick auf eine andere Fläche dieselbe Distanz; Ctrl lässt eine neue Startfläche stehen (mehrstufige Gebäude). **KONSENS** (Forum, mit Zitaten aus dem User’s Guide 2006). Ein Entwickler-Beitrag beschreibt Richtungsfehler beim Doppelklick, die später behoben wurden. **BEOBACHTUNG.**
- **Lehre:** Wiederholen ohne Menü, direkt am Ziel. Fehler in der *Richtung* einer Wiederholung sind real.

### 4.10 Plasticity — moderne Absage an die History

- NURBS-Modeler „CAD for artists“; der Entwickler nennt parametrische Features wegen des Artist-Fokus eine geringere Priorität, ein Modifier-System ist geplant. **FAKT** (Fachpresse 2023, Entwickleraussage).
- **Lehre:** Auch 2023 wählt ein Artist-Werkzeug bewusst direktes Modellieren statt History.

### 4.11 CAD — das Persistent Naming Problem

- History-basierte parametrische Systeme scheitern beim Neuberechnen oft, wenn sich Topologie ändert; das Problem heißt „persistent“ oder „topological naming“. Grundlagen: Kripac 1997, Capoyleas/Chen/Hoffmann 1996, Agbodan/Marcheix/Pierra 2000–2003. **FAKT.**
- FreeCAD: Das Problem betrifft alle CAD-Systeme; andere Systeme mildern es mit Heuristiken. Der neue Naming-Algorithmus (erstmals stabil in 1.0) repariert teils automatisch, schlägt teils eine Lösung vor und zeigt sonst wenigstens die Ursache. **FAKT.**
- **Lehre:** „Automatisch reparieren → vorschlagen → Ursache zeigen“ ist eine gestufte Fehlerkultur, die Mirais Invariante („nie still anders“) konkret macht.

### 4.12 Forschung — Ketten sichtbar machen und übertragen

| Arbeit | Was sie zeigt | Bezug |
| --- | --- | --- |
| MeshFlow (Denning, Kerr, Pellacini 2011) | Mesh-Konstruktion umfasst Zehntausende Einzeloperationen über Stunden; wiederholte Operationen lassen sich hierarchisch clustern | Eine rohe Operationsliste ist keine Oberfläche; Wiederholungen sind erkennbar (→ E1) |
| MeshGit (Denning, Pellacini 2013) | Mesh-Edit-Distanz, Korrespondenz zwischen zwei Mesh-Versionen, Konflikterkennung beim Mergen | Korrespondenz ohne gespeicherte History ist möglich (→ §7) |
| MeshHisto (Salvati et al. 2015) | Editier-Historien auf andere Mesh-Teile mit abweichender Topologie übertragen, Sequenzen mit mehreren hundert Edits | „Rezept auf andere Auswahl anwenden“ ist auf Forschungsniveau gelöst (→ §9) |
| 3DFlow (Denning, Tibaldo, Pellacini 2015) | Zusammenfassung von Workflows nur aus Mesh-Snapshots | Mirai speichert ohnehin Snapshots |

Autocomplete 3D Sculpting: siehe Workflow-Dokument §16.2.7.

## 5. Construction History im Vergleich

Die Systeme unterscheiden sich weniger in Features als in einer Frage: **Wie lange bleibt eine Entscheidung veränderbar, und wer ist die Quelle der Wahrheit?** Daraus ergeben sich fünf Philosophien. **INTERPRETATION** auf Basis der FAKTEN in §4.

| Philosophie | Quelle der Wahrheit | Editierfenster | Referenzmodell | Typischer Fehler | Beobachtete Artist-Gewohnheit | Vertreter |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Rezept ist Wahrheit | Operator-/Node-Kette | unbegrenzt | Index, bei Profis Rollen/Gruppen | still falsches Ziel nach Topologieänderung | früh einfrieren, kollabieren, History löschen | XSI, Max-Stack, Maya, Modo MeshOps, Houdini |
| 2. Mesh ist Wahrheit, letzter Schritt weich | Mesh | bis Commit / bis zur nächsten Operation | implizit (aktuelle Auswahl) | keiner — Fenster schließt sich einfach | — | Blender Adjust Last Op, Max Edit Poly Caddy, XSI Immediate OK/Cancel, LightWave Bevel |
| 3. Mesh ist Wahrheit, Wiederholen | Mesh | keins | aktuelle Auswahl | falsche Richtung bei Wiederholung | Doppelklick, D/Shift+D | Wings, SketchUp, Max Apply and Continue |
| 4. Mesh ist Wahrheit, Absicht rekonstruieren | Mesh | beliebig, soweit erkennbar | Muster in der Geometrie | Muster nicht erkannt | — | MESHmachine (Workflow-Dokument H7) |
| 5. Aufgezeichnete Befehle als Werkzeug | Mesh | keins (neue Anwendung) | konkrete Komponenten oder aktuelle Auswahl | Abspielen trifft Falsches | Buttons für eigene Abläufe | Max Macro Recorder, Maya Shelf, XSI Toolbar |

### 5.1 Der Notausgang ist kein Zufall

Jedes Rezept-System hat ein Einfrieren eingebaut, und Artists nutzen es routinemäßig. XSI begründet Immediate Mode mit kleineren, schnelleren Szenen; Max-Nutzer raten zum frühen Kollabieren; Maya-Kurse lehren „delete history“ als festen Schritt. **FAKT/KONSENS.**

**INTERPRETATION:** Beim Hände-Modellieren von Charakteren verliert das Rezept seinen Wert schnell — nach wenigen Schritten will niemand mehr zum dritten Extrude zurück — während seine Kosten (Auswertung, Brüchigkeit) wachsen. Der Notausgang ist die Antwort der Praxis auf dieses Missverhältnis.

**Gegenbefund:** Prozedurale Nutzer (Houdini, Modo MeshOps) ziehen großen Nutzen aus langlebigen Rezepten — dort, wo Variation und Wiederverwendung das Ziel sind (Umgebungen, Hard Surface, Assets in Serie). Die Frage ist also nicht „History gut oder schlecht“, sondern **für welche Art Arbeit**. Mirai zielt auf direktes Charakter-Modellieren. **INTERPRETATION.**

### 5.2 Zwei Ideen, die über die Grenze hinweg interessant sind

1. **Maya: History als Parametergedächtnis.** Der Extrude-Node merkt sich Translate/Rotate/Scale der Geste. Das ist nützlich, auch wenn nie jemand die Kette neu abspielt — als Grundlage für „Wiederholen“ und „Nachjustieren“.
2. **XSI: History nach Absicht geordnet.** Modeling vs. Shape vs. Animation als Regionen. Für Mirais Vision (Topologie ändern, nachdem Rig und Morphs existieren) ist das der einzige gefundene Präzedenzfall, der die Absichts-Ebenen im Datenmodell trennt. Gehört als Frage zu ARCH-01/ARCH-02 und `CHARACTER_SYSTEMS_RESEARCH.md`, nicht hierher. **INTERPRETATION.**

## 6. Operation Stack vs. Graph

Für die Szenarien dieser Aufgabe braucht Mirai vermutlich **keinen Graphen** — höchstens einen **Wald kurzer Ketten**, deren Anker ein Baum bilden (Körper → Arm → Hand → Finger). **HYPOTHESE.**

### 6.1 Das Problem des linearen Stacks

Ein Körper mit zwei Armen, zwei Beinen und Hals hat fünf Ketten, die räumlich unabhängig sind, im Stack aber zeitlich hintereinander liegen. Ändert man den ersten Extrude des linken Arms, muss alles danach neu berechnet werden — auch der rechte Arm. **FAKT** für XSI, Max, Maya (lineare Kette), Modo (Liste).

**INTERPRETATION:** Mit Index-Referenzen koppelt ein linearer Stack unabhängige Ketten zusätzlich über die **globale Nummerierung**: Ein Loop im linken Arm verschiebt Indizes, und der rechte Arm trifft die falschen Faces (genau das Houdini-Forum-Muster aus §4.7). Mit stabilen IDs (Mirai, AD-001) und Rollen-Referenzen entfällt diese Kopplung. Damit entfällt der Hauptgrund, einen Graphen zu wollen.

### 6.2 Was ein Graph kostet

Houdini zeigt die volle Kraft: explizite Abhängigkeiten, Verzweigen, Zusammenführen. Der Preis: Der Artist baut den Graphen selbst. MeshFlow zählt für ein Charakter-Mesh Zehntausende Einzeloperationen über Stunden. **FAKT.** Ein Graph daraus ist keine Oberfläche, sondern ein Datenbankauszug. **INTERPRETATION.**

### 6.3 Kleinere Modelle

| Modell | Struktur | Was editierbar bleibt | Wo es endet |
| --- | --- | --- | --- |
| Normale Operationen + Fenster für die letzte | keine | nur die letzte Operation | bei der nächsten Operation |
| Temporäre Session (wie Knife) | Liste innerhalb der Session | alle Schritte bis Commit | beim Commit |
| Wald kurzer Ketten | je Kette eine Liste, an eine Region verankert | Formparameter der Kette nach Commit | wenn eine Kette eine andere berührt |
| Baum verankerter Ketten | Kette an Rolle einer anderen Kette verankert (Finger an Hand-Top) | Formparameter entlang des Baums | bei Brücke/Weld zwischen Ästen |
| Voller Graph | DAG | alles | nie (bis zur Unlesbarkeit) |

**Beobachtung zur Form:** Ein Baum verankerter Ketten hat dieselbe Struktur wie eine Skelett-Hierarchie (Oberarm → Unterarm → Hand → Finger). **INTERPRETATION.** Das verbindet diese Frage mit Rigging (§8.2) und ist für Mirais Vision kein Zufall.

### 6.4 Wo ein Graph unvermeidlich wäre

- Eine Operation hängt von **zwei** Ketten ab: Bridge zwischen zwei Fingern, Weld zwischen Arm und Körper-Detail.
- Eine Operation hängt von einer **geometrischen Abfrage** anderer Teile ab (Snap auf eine Fläche).

In beiden Fällen gibt es zwei ehrliche Antworten: Dort friert die Kette ein (Grenze der Editierbarkeit), oder die Abhängigkeit wird explizit. Welche Antwort Artists erwarten, ist eine Artist-Frage (§13, EXT-Q8).

## 7. Das topologische Referenzproblem

**Antwort auf die Kernfrage (HYPOTHESE):** Mirai kann nützliche editierbare Ketten ohne großes prozedurales System anbieten, wenn drei Bedingungen gelten: (1) Schritte verweisen über **Rollen** („Top von Schritt k“), nicht über IDs oder Indizes; (2) nachträglich editierbar sind nur **Formparameter**; (3) jeder topologie-ändernde Eingriff macht seinen Konflikt sichtbar, statt ihn zu raten. Das schwierigste Teilproblem ist dann nicht die Referenz, sondern die **manuelle Arbeit zwischen den Schritten**.

### 7.1 Ansätze im Vergleich

| Ansatz | Stabil gegenüber | Bricht bei | Kosten | Fehlerbild | Wer nutzt es |
| --- | --- | --- | --- | --- | --- |
| Index / Nummer | nichts außer identischer Vorgeschichte | jeder Topologieänderung davor | minimal | **still falsches Ziel** | Max Edit Mesh/Poly, Maya-Komponenten, Houdini Prim-Nummer, Modo „by Index“ |
| Persistente ID | Änderungen an anderer Stelle | Neu-Abspielen erzeugt neue Elemente mit neuen IDs | gering (Mirai hat es) | Referenz ins Leere | Mirai (AD-001), Blender-Tweak-Idee „ID-based“ |
| Rolle / Operationsergebnis | Parameteränderungen, die Anzahlen ändern (Divisions) | wenn nur ein *Teil* einer Rolle gemeint ist; wenn die Rolle gespalten oder gelöscht wird | gering, pro Operation definiert | Konflikt erkennbar | Houdini Front/Side, Modo „by Previous Operation“, Blender Top/Side, **Mirai: neue Faces nach Commit ausgewählt** |
| Selection Set, nachgeführt | Topologieänderungen, wenn jede Operation mitführt | Operationen ohne Propagationsregel | **jede** Operation braucht Regeln | Set wird unvollständig | Modo „Assign Selection Set“, XSI-Cluster |
| Topologische Korrespondenz / Matching | vieles | Mehrdeutigkeit | hoch, heuristisch | falsches Match möglich | CAD Persistent Naming, MeshGit |
| Geometrische Abfrage (Position, Normale, Box) | Topologieänderung | **Formänderung** | mittel | trifft nach Verlängern andere Elemente | Houdini/Modo Regel-Selektionen |
| Hybrid | kombiniert | selten | höher | Widersprüche sichtbar | Mirai Symmetry Lab: Operationskontext primär, Position/Topologie als unabhängige Prüfung |

**Warnung zur geometrischen Abfrage:** Sie widerspricht Fall A direkt. Wer den Oberarm verlängert, verschiebt Positionen — eine Positionsabfrage findet danach andere Elemente. Als Primärreferenz für editierbare Ketten ungeeignet, als Validierung brauchbar. **INTERPRETATION.**

### 7.2 Die Mirai-spezifische Pointe: AD-001

Mirai vergibt IDs nie zweimal. **FAKT** (AD-001). Daraus folgt zweierlei:

- **Neu-Abspielen einer Topologie-Operation** erzeugt neue Elemente mit neuen IDs. Alles, was sich die alten IDs gemerkt hat (manuelle Tweaks, spätere Schritte), zeigt ins Leere. IDs taugen also nicht als Referenz *über ein Neu-Abspielen hinweg*. **INTERPRETATION.**
- **Form-Edits spielen keine Topologie neu ab.** Wer nur Distanz, Winkel, Skalierung oder Pivot ändert, verschiebt dieselben Vertices; alle IDs bleiben. Für diese Klasse ist Mirais ID-System schon genau richtig. **INTERPRETATION.**

Das ist der Grund für die Zweiteilung in §8: **Klasse i = Form-Edit** (Topologie unverändert, IDs stabil, kein Naming-Problem) und **Klasse ii = Topologie-Edit** (Naming-Problem im vollen Sinn).

### 7.3 Das eigentliche Problem: Arbeit zwischen den Schritten

Box-Modeling ist „formen, während man baut“: Zwischen zwei Extrudes werden Vertices verschoben. **KONSENS.** Maya speichert solche Vertex-Tweaks nicht automatisch als eigenen Node; ein Toolbox-Hersteller beschreibt unerwartetes Verhalten beim Zurücksetzen der History, wenn diese Edits fehlen. **FAKT** (GS Toolbox Doku).

**Folge für Mirai (INTERPRETATION):** Eine Kette, die manuelle Tweaks ignoriert, verliert Artist-Arbeit. Eine Kette, die sie einbezieht, muss sie (a) per ID an Vertices binden — funktioniert, solange Topologie unverändert ist — und (b) im **lokalen Rahmen** des jeweiligen Schritts speichern, damit sie bei einer Winkeländerung mitfahren. Beides ist in Klasse i lösbar, in Klasse ii nicht ohne Provenienz.

### 7.4 Anschluss an ARCH-02

Für Klasse ii braucht jede Operation, die neue Vertices erzeugt, eine Aussage „aus wem“. Der Projektstand hat dafür schon Bausteine: `split_edge(t)` im Operationskontext (AD-017 B5), die Provenienz-Haken des Cross-Face-Knife (Gruppierung pro Absicht, `(edge_id, t)`, Eltern-Face, Blickrichtung) und FINDINGS-3C (Operationskontext HIGH, Snapshot-Heuristik MEDIUM). **FAKT** (Repo). Diese Research liefert ARCH-02 einen weiteren Anwendungsfall, keine neue Anforderung: **„Rolle eines Operationsergebnisses“ als Teil des Operationskontexts.**

## 8. Editierbare History — Fälle A bis H

Drei der acht Fälle (A, B, C) sind robust lösbar, weil sich keine Topologie ändert. D, E und F sind **teilweise** lösbar: Formparameter können weiter wirken, Topologieparameter nicht. G und H sind im Mirai-Maßstab nicht robust lösbar, ohne gegen die Invariante „nie still andere Topologie“ zu verstoßen. **INTERPRETATION.**

**Szenario:** Torso → Schulter-Face wählen → Extrude 1 → Move → Rotate → Extrude 2 → Move → Rotate → … → Extrude Hand.

**Begriffe:** *Formparameter* = Distanz, Winkel, Skalierung, Pivot. *Topologieparameter* = Auswahl/Region, einzeln vs. zusammen, Divisions, Anzahl Schritte.

### 8.1 Übersicht

| Fall | Was der Artist tut | Klasse | Topologie ändert sich? | Robust möglich? | Voraussetzung | Konflikt zeigen? |
| --- | --- | --- | --- | --- | --- | --- |
| A | Distanz von Extrude 1 erhöhen | i | nein | **ja** | spätere Schritte im lokalen Rahmen gespeichert | nein |
| B | Winkel von Rotate 1 ändern | i | nein | **ja** | wie A + gespeicherter Pivot | nein |
| C | Extrude am Ende anhängen | i für frühere Edits | nein (früher) | **ja** | neuer Schritt verweist auf Rolle „Top des vorigen“ | nein |
| D | Loop Insert mitten in der Kette | ii | ja | teilweise | Provenienz neuer Vertices (`split_edge(t)`) | ja, für Topologieparameter |
| E | Knife in der Kette | ii | ja | teilweise | wie D, plus Face-Innenkoordinaten | ja; zwingend, wenn eine Rolle gespalten wird |
| F | Kanten eines früheren Schritts auflösen | ii | ja | teilweise | Rolle unberührt? | ja, wenn eine Rolle betroffen ist |
| G | Region eines späteren Schritts ändern | ii | ja | nein (ehrlich: neu ausführen) | Rollen-Referenzen für alles danach | **ja, immer** |
| H | Topologie eines früheren Schritts grundlegend ändern | ii | ja | nein | Persistent Naming (CAD-Niveau) | **ja, immer** |

### 8.2 A und B — eine Extrude-Kette ist eine FK-Kette

**Fall A (längerer Oberarm).** Erwartung: Unterarm und Hand wandern mit. Das klappt nur, wenn die späteren Schritte **relativ zum Top-Face des vorigen Schritts** gespeichert sind. Sind sie in Weltkoordinaten gespeichert („2 Einheiten nach +X“), bleibt der Unterarm stehen und der Oberarm wächst in ihn hinein. Maya führt beides als Parameter (translate vs. localTranslate, worldSpace-Schalter). **FAKT.** Die Mehrdeutigkeit ist also real und wird dort dem Artist überlassen.

**Fall B (anderer Ellbogenwinkel).** Wie A, plus: Um welchen Punkt wurde gedreht? Face-Mitte, eine Kante (Scharnier), ein frei gesetzter Pivot? Der gespeicherte Pivot muss im lokalen Rahmen liegen. Die Seiten-Faces zwischen Oberarm-Top und Unterarm-Basis werden dabei gestaucht oder gedehnt — **genau wie bei einem Gelenk im Rig.**

**Die Pointe (HYPOTHESE):** Jeder Extrude-Schritt definiert einen lokalen Rahmen (Face-Mitte + Normale + Tangente). Die Kette dieser Rahmen ist strukturell ein Skelett, und A und B sind Forward Kinematics. Mirais Transform-Tangentenbasis (AD-012/AD-014) und die Normal-Space-Arbeit liefern die Rahmendefinition schon teilweise. **INTERPRETATION.**

**Alternative ohne gespeicherte Kette:** Die temporäre Artikulation (EX-A) biegt heute schon mit Pivot + Falloff, ohne History, exakt rücksetzbar. **FAKT** (Repo). Tutorials biegen Finger am Ende „in eine entspannte Haltung“ — Posing als Modellierschritt. **BEOBACHTUNG.** Wenn ein Ellbogenwinkel auch so änderbar ist, braucht Fall B gar keine History. **HYPOTHESE** — billig testbar (§14, X4a).

### 8.3 C — Anhängen ist harmlos

Anhängen macht nichts Früheres ungültig. Frühere Schritte bleiben editierbar, wenn der neue Schritt auf „Top des vorigen Schritts“ verweist. Ändert man danach Distanz 1, wandert auch der neue Schritt mit. **INTERPRETATION.**

### 8.4 D, E, F — Topologie mitten in der Kette

**D (Loop Insert im Unterarm).** Der Loop teilt Seiten-Faces von Schritt 5. Der Hand-Extrude verweist auf das Top-Face von Schritt 6 — unberührt. Die neuen Loop-Vertices gehören aber zu keinem Rahmen. Mit `split_edge(t)` im Operationskontext weiß man, dass jeder zwischen einem Vertex aus Rahmen k und einem aus Rahmen k+1 liegt, bei Anteil t. Dann folgt er Form-Edits **interpoliert** — das ist Skinning mit zwei Knochen. Das Rigging-Experiment bewertet genau diesen Weg (split im Operationskontext) als HIGH. **FAKT** (FINDINGS-3C). Konzeptuell ist das dann aber Deformation, nicht mehr „Neu-Abspielen“. **INTERPRETATION.**

Was **nicht** mehr geht: Divisions von Schritt 5 nachträglich ändern. Der manuelle Loop und die Divisions würden kollidieren. → Topologieparameter gesperrt, Formparameter offen: **„teilweise editierbar“.**

**E (Knife).** Knife-Punkte auf Kanten sind wie D (`(edge_id, t)`). Punkte im Face-Inneren (Face Cut, Q5) brauchen Innenkoordinaten relativ zu den Face-Ecken — einer der Provenienz-Haken in `KNIFE_CROSS_FACE_DISCOVERY.md` §7. **Harte Grenze:** Schneidet der Knife durch ein Face, auf das ein späterer Schritt als Rolle verweist, wird aus einem Top-Face zwei. Der spätere Schritt ist dann mehrdeutig. Hier darf nichts geraten werden → **ungültig**, Konflikt anzeigen.

**F (Kanten auflösen).** Aufgelöste Kanten, die nur „produziert“ und nicht „referenziert“ sind (Seitenkanten), stören spätere Schritte nicht. Vertices überleben ein Kanten-Auflösen meist; Rahmenzugehörigkeit hängt an Vertices, also bleiben Form-Edits möglich. Verschmilzt ein Auflösen aber ein Top-Face mit Seiten, ist die Rolle zerstört → **ungültig** für alles, was sie nutzt. Hinweis: Mirai hat noch kein Dissolve.

### 8.5 G und H — die Absicht selbst hat sich geändert

**G (späterer Schritt soll auf zwei Faces statt einem wirken).** Alles ab diesem Schritt entsteht neu. Rollen-Referenzen tragen die Kette weiter („Top von Schritt k“ sind jetzt zwei Faces), aber alle manuellen Tweaks danach hängen an IDs, die es nicht mehr gibt. Houdini kann das, weil dort nichts manuell dazwischenliegt. **INTERPRETATION.** Ehrliche Optionen: neu ausführen mit Konfliktliste, oder Abzweig (Alt bleibt, Neu entsteht daneben).

**H (Extrude 1 einzeln statt Region, oder Divisions 1 → 4).** Alles danach wird neu ausgewertet. Rollen überleben, Indizes und manuelle Tweaks nicht. Das ist das CAD-Problem, das FreeCAD erst in Version 1.0 mit Heuristiken mildert. **FAKT.** Robustes nicht-destruktives Verhalten würde Mirais Invariante nur einhalten, wenn jede unsichere Zuordnung gezeigt wird. **INTERPRETATION:** Kein Problem in Mirai-Größe.

### 8.6 Der Satz, der alles ordnet

> Form-Edits bewegen dieselben Vertices; Topologie-Edits erzeugen neue. Das erste ist ein Rig-Problem, das zweite ein Naming-Problem.

**INTERPRETATION.** Diese Unterscheidung ist in keiner der untersuchten DCCs ein sichtbares Konzept für den Artist — dort ist beides „History“.

## 9. Artist-kontrollierte Automatisierung

„Der Artist erzeugt die Automatisierung“ ist in drei Stufen denkbar, und jede Stufe verlangt genau eine neue Zutat: **Wiederholen** braucht die letzte Operation samt Parametern; **Aufzeichnen** braucht Rollen-Referenzen; **Parametrisieren** braucht die Entscheidung, welche Löcher offen bleiben (H8). **INTERPRETATION.** Die Begriffe unten sind Arbeitsnamen, keine Terminologie-Entscheidung.

### 9.1 Begriffsraum

| Arbeitsname | Was es ist | Was gespeichert wird | Vorbild |
| --- | --- | --- | --- |
| Repeat | letzte Operation erneut auf aktueller Auswahl, neue Geste | Operationstyp | Wings Ctrl+D |
| Repeat Args | letzte Operation mit denselben Einstellungen | + Einstellungen | Wings D |
| Repeat Drag | letzte Operation inklusive Geste (Distanz, Winkel) | + Gestenwerte | Wings Shift+D, SketchUp Doppelklick, Max Apply and Continue |
| Kette | Folge von Operationen, verknüpft über Rollen | Schritte + Rollen | Houdini Front-Gruppe, Modo „by Previous Operation“ |
| Konstruktion | Kette, deren Formparameter nach Commit editierbar bleiben | + lokale Rahmen, Tweaks | Maya Extrude-Node (teilweise) |
| Rezept / Makro | gespeicherte Kette, anwendbar auf andere Auswahl | Kette ohne Ort | Max Macro Recorder, Maya Shelf |
| User Tool | Rezept mit Namen, Hotkey und freigegebenen Reglern | + Löcher | Houdini Digital Asset, Modo Tool Pipe/Presets |

### 9.2 Die Antworten auf die Fragen der Aufgabe

- **Kann der Artist eine Kette speichern?** Ja, wenn jeder Schritt „auf das Ergebnis des vorigen“ verweist statt auf IDs. **Mirai-Vorteil:** Das Playground-Extrude wählt nach dem Commit die neuen Faces aus. **BEOBACHTUNG** (Code). Wer Operationen auf „der aktuellen Auswahl“ aufzeichnet, erhält deshalb automatisch eine rollenbasierte Kette — solange jede Operation ihr Ergebnis ausgewählt hinterlässt. **INTERPRETATION.** Das macht das Residue-Design (Research Map: „was überlebt eine Operation?“) buchstäblich zum Referenzsystem jeder Automatisierung.
- **Kann man Parameter freigeben?** Ja; die schwierige Frage ist welche (H8). Eine prüfbare Heuristik: Parameter, die der Artist zwischen Wiederholungen geändert hat, sind Löcher; konstante werden eingebacken. **HYPOTHESE**, testbar mit E1-Daten.
- **Kann man eine Kette wiederholen?** Ja, trivial mit Rollen.
- **Auf eine andere kompatible Auswahl anwenden?** Kompatibel heißt: Der erste Schritt akzeptiert den Auswahltyp, und jede Rolle liefert eine gültige Eingabe. Extrude funktioniert auf jedem Face; quad-gebundene Operationen (Ring, Loop) nicht überall. MeshHisto zeigt, dass Übertragen auf abweichende Topologie auf Forschungsniveau geht. **FAKT.** Entscheidend: **Relative** Parameter (Winkel zur Normale, Skalierungsfaktor) übertragen sich sinnvoll, **absolute** (Weltverschiebung) nicht. Ob Distanz absolut oder relativ zur Face-Größe sein soll (Finger an kleiner und großer Hand), ist eine Artist-Frage.
- **Einzelne Schritte editieren?** Nur auf der Stufe „Konstruktion“. Auf der Stufe „Rezept“ ändert ein Edit die Vorlage, nicht die schon angewendeten Instanzen.
- **Sollen Vorlagen-Änderungen angewendete Instanzen verändern?** Houdini-Assets tun genau das. Für handmodellierte Teile wäre das der Schritt ins Prozedurale. **INTERPRETATION:** eher nicht — aber Artist-Frage.
- **Backen?** Im Modell „Mesh ist Wahrheit“ trivial: Annotation weg, Mesh bleibt. Im Modell „Rezept ist Wahrheit“ heißt Backen Kollabieren.
- **Auseinanderbrechen?** Eine Kette bei Schritt k teilen: Der zweite Teil verankert sich an der Rolle von Schritt k, als wäre sie Startauswahl.
- **Kompatibilität verloren?** Explizite Zustände statt stiller Reparatur (§11).

### 9.3 Wer stößt die Automatisierung an?

Autocomplete-Sculpting schlägt Wiederholungen aus dem eigenen Verhalten vor (Workflow-Dokument §16.2.7). **FAKT.** Für Mirai gilt der Artist-in-the-Loop-Grundsatz: Ein Vorschlag darf erscheinen, entscheiden muss der Artist. **INTERPRETATION.**

Die billigste Form, die den Grundsatz erfüllt: **nachträgliches Befördern.** Der Artist arbeitet normal, bemerkt die Wiederholung selbst und macht „die letzten N Schritte“ zur benannten Kette — wie Max-Nutzer Text aus dem Macro Recorder auf eine Toolbar ziehen. Kein Aufnahme-Knopf vorher, kein Automatismus. **HYPOTHESE.**

## 10. Extrude-Session-UX

Alle fünf Session-Formen aus der Aufgabe existieren in echten DCCs; keine ist die „richtige“. Die Entscheidung gehört ins UX-System (Three-Role, Research Map: Dimension *Composition*), nicht in dieses Dokument. Hier nur: Belege, Konsequenzen, Risiken. **Keine Tastenbelegung, keine Entscheidung.**

### 10.1 Die fünf Formen mit Vorbildern

| Form | Was sie ist | Vorbild | Belegstufe |
| --- | --- | --- | --- |
| 1. Atomare Topologie-Operation | Extrude erzeugt Geometrie; Move/Scale/Rotate sind danach eigene Operationen | Max Editable Poly, klassische Menübefehle | KONSENS |
| 2. Transformations-Session | eine Geste enthält Extrude + Move + Scale + Rotate | Maya Extrude-Manipulator und Node-Parameter; Wings Sweep; LightWave Multishift | FAKT |
| 3. Mehrstufige Konstruktions-Session | mehrere Extrude-Schritte in einer Session, ein Commit | LightWave Multishift (Rechtsklick = neuer Shift); Max „Apply and Continue“; Mirai Knife (Klicks sammeln, Enter) | FAKT |
| 4. Übergang in andere Operationen | die laufende Operation wird kurz überlagert | Max Press/Release-Shortcuts | FAKT |
| 5. Kontextabhängig | je nach Auswahl/Situation eine andere Form | Mirais kontextuelles C (AD-017) als Denkmuster | INTERPRETATION |

### 10.2 Konsequenzen, die jede Variante beantworten muss

- **Commit-Granularität.** Ein Undo-Schritt pro Session (Knife-Präzedenz: in der Session nimmt Undo den letzten Schritt, nach dem Commit die ganze Session) oder einer pro Schritt? Mirai hat für den Knife genau diese Frage schon beantwortet. **FAKT** (AD-017 FINAL, Artist-Entscheidung 2026-09-29). Übertragbarkeit auf Extrude ist offen.
- **Cancel.** Esc verwirft die ganze Session (Knife) oder nur den letzten Schritt?
- **Wer besitzt Q/W/E in der Session?** AD-016 gibt Transform die Hoheit über Q/W/E. Eine Session, in der Q/W/E auf das neue Top wirken, ohne sie zu verlassen, müsste diese Hoheit teilen oder nutzen. Bekannte Tastenkonflikte zwischen Familien existieren schon (`playground-input-konflikte`). **FAKT** (Repo).
- **Pivot für Rotation.** Face-Mitte, Kante als Scharnier (Max „Hinge from Edge“), frei gewählte Achse (Wings Sweep fragt danach). Das ist eine **künstlerische** Frage, weil es bestimmt, wie ein Ellbogen „knickt“.
- **Richtung bei Region-Extrude.** Gemittelte Normale vs. Normale je Face — LightWave bietet beides an. **FAKT.** Verknüpft mit Manus Verdikt „Einzel-Extrude pro Face wird gebraucht“.
- **Tippen ohne Bewegung.** Manus Verdikt (Tippen bewirkt nichts, mit Schwellenwert) gilt für den *Start*. Was ein Tippen *innerhalb* einer Session bedeutet (nächster Schritt?), ist eine neue Frage — nicht aus dem Verdikt ableitbar.
- **Zahleneingabe.** Mechanische Teile (W5) brauchen Zahlen; Mirai hat noch keine allgemeine numerische Eingabe. Repeat Drag umgeht das teilweise: Der Wert kommt aus der letzten Geste, nicht aus einer Tastatur. **INTERPRETATION.**
- **Symmetrie.** Eine Session auf einer Seite erzeugt eine Absicht mit zwei Seiten (AD-SYM-02). Muss mitgedacht, nicht jetzt gelöst werden.

### 10.3 Das God-Tool-Risiko

Mayas Extrude-Node trägt neben Translate/Rotate/Scale auch Schwerkraft, Magnet, Anziehung und Zufall. **FAKT.** Wings Sweep packt vier Transformationen auf Maustasten-Kombinationen. **FAKT.** Beides zeigt, wie ein Werkzeug, das „alles während des Extrudierens“ kann, zur Parameterwand oder zum Griffrätsel wird.

**Gegenmittel, die schon im Projekt liegen (INTERPRETATION):** Die Session *nutzt* die bestehende Transform-Familie, statt eigene Transformationen mitzubringen — so wie der Knife die bestehende Split/Connect-Infrastruktur nutzt statt einer „Cut Engine“ (Manus Haltung zu AD-017).

### 10.4 Die Session-Grenze ist die natürliche Editierbarkeits-Grenze

Max Edit Poly hält die aktuelle Operation bis zum Commit live; XSI Immediate Mode öffnet OK/Cancel pro Operation. **FAKT.** **HYPOTHESE:** Wenn Mirai eine Session bekommt, ist „alles bis Commit editierbar, danach normales Mesh“ der kleinste kohärente Vertrag (= Option B). Alles, was nach dem Commit editierbar bleiben soll, ist schon Option C.

## 11. Fehler- und Invalidierungsfälle

Vier Zustände reichen, um jede Kette ehrlich zu beschreiben — und Mirai kann Invalidierung über den **Operationskontext erkennen**, statt sie durch Nachrechnen zu erraten. Erkannt heißt: zeigen, nicht reparieren. **INTERPRETATION.**

### 11.1 Zustände

| Zustand | Bedeutung | Was geht | Was nicht | Wie man hineinkommt |
| --- | --- | --- | --- | --- |
| Editierbar | Topologie seit der Kette unverändert, nichts Manuelles hängt an Ergebnis-IDs | Form- und Topologieparameter | — | praktisch nur innerhalb einer Session |
| Form-editierbar (= „teilweise“) | Topologie wurde verändert, aber jeder Vertex hat eine Rahmenzugehörigkeit (direkt oder über Provenienz) | Formparameter (Distanz, Winkel, Skalierung, Pivot) | Topologieparameter | Commit; Loop Insert, Knife auf Kanten, Kanten auflösen ohne Rollen-Treffer |
| Eingefroren | Annotation entfernt, normales Mesh | alles, was ein Mesh kann | Ketten-Edits | Backen durch den Artist (automatisch? → EXT-Q8) |
| Ungültig | eine referenzierte Rolle ist gespalten, gelöscht oder verschmolzen, oder ein Rahmen ist entartet | alle Schritte **vor** dem Bruch | die betroffenen Schritte und alles danach | Knife durch ein Top-Face, Top löschen, Bridge/Weld mit anderer Kette |

### 11.2 Wie Profi-Werkzeuge mit der Grenze umgehen

| Werkzeug | Mechanismus | Zeitpunkt | Bewertung (INTERPRETATION) |
| --- | --- | --- | --- |
| 3ds Max | Topology-Dependence-Warnung | nach der Änderung | ehrlich, aber zu spät |
| XSI | Freeze, Immediate Mode | vorher, pauschal | Artist wählt die Grenze selbst |
| Maya | Delete (Non-Deformer) History | pauschal, durch Artist | Gewohnheit statt Konzept |
| Houdini | Rollen-Gruppen | konstruktiv vermieden | robust, verlangt Disziplin im Aufbau |
| Modo | „by Previous Operation“ | — | offizieller Bug: Referenz zeigt nach Duplizieren still aufs Original |
| Blender (Tweak-Designnotiz) | Daten ohne gültigen Index ignorieren oder Modifier abschalten | beim Auswerten | Abschalten ist ehrlich, Ignorieren nicht |
| FreeCAD 1.0 | reparieren → vorschlagen → Ursache zeigen | beim Neuberechnen | gestuft, transparent |

### 11.3 Fehlerkatalog

| # | Auslöser | Was bricht | Erkennbar? | Ehrliche Reaktion |
| --- | --- | --- | --- | --- |
| F1 | Knife schneidet durch ein referenziertes Top-Face | späterer Schritt wird mehrdeutig (ein Top → zwei Faces) | ja, Operationskontext kennt das Eltern-Face | **ungültig** ab diesem Schritt, Konflikt zeigen |
| F2 | Top-Face gelöscht oder aufgelöst | Eingabe fehlt | ja | **ungültig** |
| F3 | Bridge oder Weld mit einer anderen Kette | Eingabe gehört zwei Ketten | ja | Grenze der Kette; einfrieren oder explizite Abhängigkeit (EXT-Q8) |
| F4 | Divisions ändern, während ein späterer Schritt nur einen Teil einer Rolle nutzt | Index innerhalb der Rolle | ja | Topologieparameter gesperrt |
| F5 | Neu-Abspielen entfernt Vertices, an denen manuelle Tweaks hängen | Artist-Arbeit | ja (IDs fehlen) | nie still verwerfen; betroffene Tweaks auflisten |
| F6 | Rahmen entartet (Face mit Fläche null) | Normale undefiniert | ja, messbar | **ungültig** statt Ersatzrichtung |
| F7 | Form-Edit lässt den Arm in den Torso dringen | nichts Technisches, aber die Form | messbar | nur zeigen; die Durchdringungsprüfung ist bei Extrude ohnehin offen |
| F8 | Kette auf einer Seite, Symmetrie-Korrespondenz geht verloren | Gegenseite | ja (Symmetrie-Zustand) | wie Symmetrie-Zustand „partial“ behandeln |
| F9 | Undo stellt das Mesh zurück, die Annotation nicht | alles | vermeidbar | Annotation gehört in denselben History-Schritt wie das Mesh (EXT-Q14) |
| F10 | Topologie-Replay erzeugt neue IDs (AD-001) | alles ID-Gebundene außerhalb der Kette: Selection Sets, Symmetrie-Korrespondenz, später Weights und Morphs | ja | Form-Edits bevorzugen; bei Topologie-Replay Liste der betroffenen Abhängigkeiten |

**Konkreter Fund zu F6 (BEOBACHTUNG, Code):** `_compute_face_normal` in `playground/topology_tools/extrude.py` gibt für ein entartetes Face still `(0, 0, 1)` zurück. In einer einzelnen Live-Geste sieht der Artist das Ergebnis sofort, dort ist es unkritisch. In einem Neu-Abspielen wäre es genau ein „still anderes Ergebnis“. Das ist eine Beobachtung für eine mögliche Kette, **keine** Änderungsforderung an das heutige Tool.

### 11.4 Die Invariante, operationalisiert

> Mirai darf nie still eine andere Topologie erzeugen, nur weil sich eine frühere Operation geändert hat.

- **Form-Edit:** ändert Topologie per Definition nicht → darf live laufen.
- **Topologie-Edit an einer Kette:** vor dem Commit den Unterschied zeigen (MeshGit belegt, dass sichtbare Diffs zwischen Mesh-Versionen machbar sind) plus die Liste betroffener Tweaks und Abhängigkeiten.
- **Nie:** Ersatzrichtung, stilles „nächstbestes Element“, stilles Weglassen.
- **FreeCADs erste Stufe (automatisch reparieren)** passt nur dort, wo die reparierte Topologie nachweislich identisch ist. Sonst bleiben für Mirai nur „vorschlagen“ und „Ursache zeigen“. **INTERPRETATION.**

## 12. Design Space — Optionen A bis E

Die Optionen unterscheiden sich vor allem darin, **wie lange eine Entscheidung veränderbar bleibt** und **was die Quelle der Wahrheit ist**. A und B kommen ohne neue Datenstruktur neben dem Mesh aus; C braucht eine; D kehrt das Undo-Modell um. Keine Empfehlung — die Wahl hängt an Ergebnissen, die noch nicht existieren (§14). **INTERPRETATION.**

### Option A — Simple Extrude + manuelle Operationen (+ Wiederholen)

- **Ermöglicht:** identische Wiederholung (W3, W6, W8, W10) über Repeat / Repeat Args / Repeat Drag auf der aktuellen Auswahl.
- **Vorteile:** schnellstes und vorhersagbarstes Modell; Linie Wings/Nendo/Mirai; passt direkt zu Snapshot-Undo; kaum neue Architektur („letzte Operation + Parameter + Gestenwerte“ als Datensatz).
- **Nachteile:** Nach dem Commit ist nichts mehr änderbar; variierende Ketten (Arm, Finger unterschiedlicher Länge) bleiben Handarbeit; Wiederholung kann in die falsche Richtung gehen (SketchUp-Erfahrung).
- **Komplexität:** gering. **Risiko:** gering — solange Residue stimmt (Ergebnis bleibt ausgewählt).
- **Offen:** Reicht Wiederholen für Manus mechanische Fälle? (X2)

### Option B — Extrude-Sessions

- **Ermöglicht:** Extrude → Move → Scale → Rotate → nächster Schritt ohne Neuaufruf; ein Undo-Schritt pro Session; alles bis zum Commit editierbar.
- **Vorteile:** spart die Mechanik aus §2.3; Session-Muster existiert schon (Knife); nutzt die vorhandene Transform-Familie.
- **Nachteile:** Modalität; Tastenhoheit (AD-016) muss geklärt werden; Lernaufwand.
- **Komplexität:** mittel. **Risiko:** God Tool, Residue-Verwirrung, Konflikte mit Tweak-Input.
- **Offen:** Ist Composition familienspezifisch? Wo endet die Session? (X3)

### Option C — Leichte Konstruktionsketten (Mesh ist Wahrheit)

- **Definition:** Eine Kette ist eine Annotation am Mesh: Schritte, Rollen-Referenzen, lokale Rahmen, Formparameter, manuelle Tweaks als lokale Offsets. Nach dem Commit sind Formparameter editierbar; Topologie-Eingriffe führen in „form-editierbar“ oder „ungültig“ (§11); Backen = Annotation löschen.
- **Ermöglicht:** Fälle A, B, C; Wiederholen und Rezepte (H8) auf derselben Grundlage.
- **Vorteile:** Topologie kann per Konstruktion nie still anders werden; AD-001 wird zum Vorteil (Form-Edits halten alle IDs).
- **Nachteile:** neuer Datentyp neben dem Mesh; „teilweise editierbar“ ist schwer zu vermitteln; veraltete Annotationen.
- **Komplexität:** mittel bis hoch — Rahmenmathematik, Speicherung, Undo-Einbindung, Invalidierungserkennung, Symmetrie.
- **Risiko:** Erwartung wächst Richtung volle History. Außerdem binden dann zwei Systeme Vertices an Rahmen — Ketten und später Rig-Knochen. Das kann Doppelarbeit werden oder eine gemeinsame Grundlage (EXT-Q17).
- **Offen:** Wird es überhaupt gebraucht? (X1, X4a) Welche Rahmendefinition? Welches ARCH-02-Minimum?

### Option D — Volle Construction History (Rezept ist Wahrheit)

- **Ermöglicht:** alles bleibt editierbar; prozedurale Wiederverwendung und Variation.
- **Vorteile:** maximale Nachträglichkeit; bekannt aus XSI, Maya, Houdini.
- **Nachteile:** Persistent Naming vollständig lösen; Neuberechnungskosten auf der Referenz-Hardware; Umkehr des Undo-Modells (Snapshot → Neuberechnung); Konflikt mit AD-001 bei jedem Replay; die Branche zeigt die Gewohnheit, genau das wieder einzufrieren.
- **Komplexität:** sehr hoch. **Risiko:** still falsche Ergebnisse (Branchenbefund, §4); großes System gegen die Small-System-Philosophie.
- **Offen:** bräuchte ARCH-01, ARCH-02 und eine Performance-Studie. Derzeit außerhalb jeder Planung.

### Option E — Hybrid

- **Form:** A als Grundverhalten, B für die Geste, C nur auf ausdrückliche Artist-Entscheidung („das ist eine Konstruktion“), D nie im Modeling-Alltag.
- **Vorteile:** schnell per Default; editierbar nur dort, wo es gewollt ist. Das ist XSIs Immediate Mode umgedreht: Standard eingefroren, Editierbarkeit als Opt-in.
- **Nachteile:** zwei Denkmodelle — genau die Modo-Warnung (direkt vs. prozedural).
- **Komplexität:** Summe aus B und C, aber begrenzt auf markierte Stellen.
- **Risiko:** Opt-in wird nie benutzt (Aufwand verpufft) oder immer (C durch die Hintertür).
- **Offen:** wird Opt-in genutzt? Erst nach X1 und X4a sinnvoll zu fragen.

### Zwei Querwege

- **W — Wiedererkennen statt Erinnern (H7).** Keine Speicherung: Die Kette wird aus der Geometrie erkannt (eine Folge von Ringen entlang einer Röhre) und die Rahmen daraus abgeleitet. Vorteil: keine Invalidierung, funktioniert auch bei importierten Meshes. Nachteil: Erkennung unsicher, besonders bei Schule L.
- **P — Posing statt History.** Formänderungen der Klasse i über Artikulation oder Transform mit Falloff (EX-A; Influence/Falloff als geplantes gemeinsames Subsystem laut `MIRAI_SYSTEMS_1999.md`). Vorteil: existiert teilweise, keine neue Datenstruktur. Nachteil: keine exakte Rückkehr zu „genau 30° statt 45°“; Verlängern ist kein Biegen.

### Vergleich gegen Mirais Prinzipien (INTERPRETATION)

| Kriterium | A | B | C | D | E |
| --- | --- | --- | --- | --- | --- |
| Artist-Kontrolle | hoch | hoch | hoch | mittel | hoch |
| Vorhersagbarkeit | hoch | hoch | mittel bis hoch | niedrig (Branchenbefund) | hoch |
| Transparenz | hoch | mittel | hängt an der Zustandsanzeige | niedrig | mittel |
| Tempo beim direkten Modellieren | hoch | hoch | hoch | mittel | hoch |
| Kleines System | sehr klein | klein | mittel | groß | mittel |
| Wiederverwendbarkeit | mittel (Repeat) | niedrig | hoch | sehr hoch | hoch |
| Ehrliches Scheitern | nichts kann brechen | hoch (Esc) | hängt an §11 | historisch niedrig | mittel bis hoch |
| Lab-tauglich | ja | ja | ja, eingeschränkt | nein | stückweise |

### Was jede Option vom Projekt verlangt

| Option | Braucht vorher |
| --- | --- |
| A | Residue-Regel „Ergebnis bleibt ausgewählt“ (existiert für Extrude) |
| B | UX-System (Composition, Tastenhoheit AD-016), Knife-Session als Vorlage |
| C | Rahmendefinition, ARCH-02-Minimum für Klasse ii, Undo-Einbindung |
| D | ARCH-01, ARCH-02 vollständig, Performance-Studie |
| E | alles von B und C, plus ein Opt-in-Konzept |

## 13. Offene Research-Fragen

Siebzehn Fragen: zehn brauchen Manus Urteil (Artist oder Produkt), vier sind technisch (Architektur oder agent-entscheidbar), zwei sind reine Messung, eine gehört ins UX-System. Die Art bestimmt nach dem Artist-Attention-Filter (M4), wer gefragt wird.

| # | Frage | Art | Wie beantworten |
| --- | --- | --- | --- |
| EXT-Q1 | Welche Extrude-Ketten nutzt Manu wirklich — identisch wiederholt oder mit wechselnden Werten? | messbar | X1 |
| EXT-Q2 | Wie oft will Manu nach dem Commit zurück, und ist es dann Form (i) oder Topologie (ii)? | messbar + Artist | X1, Selbstbeobachtung |
| EXT-Q3 | Modelliert Manu eher nach Schule S, L oder P — oder je nach Aufgabe? | Artist | X1 |
| EXT-Q4 | Sollen spätere Schritte relativ zum vorigen Top gespeichert sein oder in Weltkoordinaten (Erwartung bei Fall A)? | Artist (M4) | X4b |
| EXT-Q5 | Um welchen Pivot dreht ein Gelenk in der Kette: Face-Mitte, Kante als Scharnier, frei gesetzt? | Artist (M4) | X3 |
| EXT-Q6 | Sollen manuelle Vertex-Tweaks zwischen den Schritten Teil der Kette sein? | Artist | X4b |
| EXT-Q7 | Ist „anderer Ellbogenwinkel“ ein History-Edit oder Posing? | Artist | X4a |
| EXT-Q8 | Wo endet eine Session oder Kette: Commit, Berührung einer anderen Kette, jeder Topologie-Eingriff? Und friert sie dann automatisch ein? | Artist + UX-System | X3 |
| EXT-Q9 | Undo in der Session: letzter Schritt (Knife-Präzedenz) oder ganze Session? | Artist | X3 |
| EXT-Q10 | Welche Löcher bleiben offen (H8)? Distanz absolut oder relativ zur Face-Größe? | Artist + Daten | X1 → X6 |
| EXT-Q11 | Dürfen Änderungen an einem Rezept bereits angewendete Instanzen verändern? | Produktentscheidung | nach X6 |
| EXT-Q12 | Wie wird der Zustand (editierbar, form-editierbar, eingefroren, ungültig) sichtbar, ohne HUD-Last? | UX-System | X5 |
| EXT-Q13 | Reicht als Provenienz-Minimum: Rolle + `(edge_id, t)` + Face-Innenkoordinaten? | Architektur (ARCH-02) | Research |
| EXT-Q14 | Gehört die Ketten-Annotation in denselben History-Schritt wie das Mesh? | agent-entscheidbar, später | Implementierung |
| EXT-Q15 | Reicht der Vertrag „eine Absicht mit zwei Seiten“ (AD-SYM-02) für symmetrische Ketten? | Architektur | Research |
| EXT-Q16 | Was kostet Neuberechnung auf der Referenz-Hardware (Form billig, Topologie teuer)? | messbar | Benchmark, erst bei Option C |
| EXT-Q17 | Sind Rahmen-Ketten (Option C) und künftige Rig-Knochen dasselbe System? | Architektur, strategisch | `CHARACTER_SYSTEMS_RESEARCH.md`, ARCH-01 |

**Bewusst keine Artist-Frage:** EXT-Q14. Das entscheidet ein Agent, sobald es gebaut wird — die Antwort folgt aus F9 in §11.

## 14. Empfohlene Lab-Experimente

Sechs Kandidaten; vier davon kosten fast nichts, und **keiner baut Konstruktions-History**. Wo möglich sind es Varianten schon vorbereiteter Experimente (E1, T5, EX-A), wie es das Workflow-Dokument empfiehlt. Reihenfolge nach Erkenntnis pro Aufwand; die Priorität entscheidet Manu.

### X1 — Extrude-Ketten-Mitschnitt (Variante von E1)

- **Frage:** EXT-Q1, Q2, Q3, Q10.
- **Aufbau:** Der Playground schreibt bei echten Modellier-Sessions mit: Operation, Auswahlgröße, Gestenwerte (Distanz, Winkel, Faktor), Zeitpunkt. Zusätzlich ein Marker, wenn eine Region später erneut bearbeitet wird (dieselben Vertex-IDs nach einer Pause). Keine Oberfläche, keine Bewertung.
- **Kosten:** gering (ein Logger). **Artist-Zeit:** keine zusätzliche.
- **Zeigt:** identische vs. variierende Ketten; wie oft Manu zurückkehrt; welche Schule.
- **Zeigt nicht:** warum (dafür E2).
- **Konsequenz:** viele identische Ketten → X2 lohnt; häufige Rückkehr mit Formänderung → X4b lohnt; kaum Rückkehr → Option C ruht.

### X4a — Biegen statt Zurückgehen (Selbstversuch, kein Bau)

- **Frage:** EXT-Q7.
- **Aufbau:** Manu baut im Playground einen Arm (Schule S, vier bis fünf Extrudes) und committet. Danach versucht er, Ellbogenwinkel und Oberarmlänge mit dem Vorhandenen zu ändern: der Artikulation (Pivot + Falloff; sie ist bewusst nur temporär, zeigt also das *Gefühl*) und Rotate/Move auf der Vertex-Auswahl von Unterarm und Hand.
- **Kosten:** kein Bau. **Artist-Zeit:** etwa 10 Minuten.
- **Zeigt:** ob Fall B als Posing-Aufgabe empfunden wird und was fehlt (dauerhaftes Biegen? Pivot-Wahl?).
- **Verdikt:** KEEP / ITERATE / REJECT / UNKNOWN für „Posing statt History“.
- **Konsequenz:** „reicht fast“ → Querweg P statt Option C; „ich will den Parameter zurück“ → X4b interessant.

### X2 — Repeat-Lab

- **Frage:** Trägt Option A die mechanischen Fälle?
- **Aufbau:** drei Varianten im Playground-Variantensystem, jeweils auf der aktuellen Auswahl: Repeat (neue Geste), Repeat Args, Repeat Drag. Optional ein SketchUp-artiger Doppelklick auf ein Face. Aufgaben: Stufensäule (W8), fünf gleich lange Finger (W3), Nietenring (W10).
- **Voraussetzung:** Extrude merkt sich die letzten Gestenwerte. Der Einzel-Extrude aus dem laufenden Work Package hilft bei den Fingern.
- **Kosten:** klein. **Artist-Zeit:** etwa 15 Minuten.
- **Zeigt:** welche Wiederhol-Stufe sich natürlich anfühlt; ob Richtungsfehler auftreten.
- **Zeigt nicht:** variierende Ketten.

### X3 — Session-Lab (im UX-System)

- **Frage:** EXT-Q5, Q8, Q9; ist Composition familienspezifisch (Research-Map-Hypothese)?
- **Aufbau:** Variante a = heute (Extrude, danach Transform separat). Variante b = Session: Während des Extrude wirken die vorhandenen Transform-Werkzeuge auf das neue Top, ohne die Session zu verlassen; ein weiterer Extrude-Schritt geht in derselben Session; Commit und Cancel wie beim Knife. Variante c = LightWave-artig: eine Maustaste löst den nächsten Schritt aus. Aufgaben: Arm aus Torso (W1), Tentakel mit Verjüngung (W7).
- **Zuständig:** Playground Spec / UX Researcher; Tastenfragen dort (AD-016).
- **Kosten:** mittel. **Artist-Zeit:** etwa 20 Minuten.
- **Zeigt:** ob eine Session Mechanik spart, ohne Modalitätsverwirrung.

### X4b — Rahmen-Kette nachträglich ändern (nur wenn X1 oder X4a es nahelegen)

- **Frage:** EXT-Q4, Q6.
- **Aufbau:** nur im Lab: Eine Session zeichnet die Rahmen auf; nach dem Commit lassen sich Distanz und Winkel eines Schritts per Regler ändern. Topologie-Operationen sind in diesem Mesh gesperrt — ein reiner Klasse-i-Test.
- **Kosten:** mittel bis hoch. Kein Core-Eingriff.

### X5 — Zustands-Probe (Papier)

- **Frage:** EXT-Q12.
- **Aufbau:** statische Mockups der vier Zustände. Versteht Manu sie auf einen Blick? Nur nach X4b.

### X6 — Rezept aus der eigenen Kette (= T5, auf Extrude zugeschnitten)

- **Frage:** EXT-Q10, Q11.
- **Aufbau:** Aus dem X1-Mitschnitt die wiederkehrenden Ketten zeigen; Manu benennt sie und markiert, welche Größen für ihn offen bleiben müssen. Gespräch, kein Bau.

### Reihenfolge und Grenzen

1. X1 (läuft passiv im Hintergrund) parallel zu X4a.
2. X2.
3. X3.
4. Entscheidungspunkt G1 (§15).
5. Nur falls G1 es rechtfertigt: X4b → X5 → X6.

**Bewusst nicht vorgeschlagen:** alles, was Persistent Naming, ein Graph-UI, eine Rezept-Bibliothek oder das Neu-Abspielen von Topologie voraussetzt.

## 15. Research-Roadmap

Drei Spuren und zwei Entscheidungspunkte bei Manu; nichts davon blockiert das laufende Extrude-Work-Package. Das Diagramm ist bewusst als Text gesetzt, damit es beim Export nach Markdown ins Repo erhalten bleibt.

```text
SPUR 1 — SOFORT IM LAB (Discovery, kein Core-Eingriff)

  X1 Ketten-Mitschnitt (passiv) ─────┐
                                     ├──▶ G1  Manu: Kommt „nach Commit ändern“ vor?
  X4a Biegen statt Zurückgehen ─────┘          Wenn ja: Form oder Topologie?
                                               │
  X2 Repeat-Lab ──┐                             ├─ kaum            → A (+B) weiter, C ruht
                  ├──▶ G2  Verdikte             ├─ Form, Biegen reicht → Querweg P statt C
  X3 Session-Lab ─┘    KEEP/ITERATE/            ├─ Form, Parameter gewollt → X4b → X5 → X6
                       REJECT/UNKNOWN           └─ Topologie        → zurück in Research,
                         │                                        D bleibt außen vor
                         ▼
                 erst dann Production-Planung (M5-Wechsel),
                 Promotion nur durch Manu (M3)

SPUR 2 — TIEFERE ARCHITEKTUR-RESEARCH (Anwendungsfall für ARCH-02, kein neues Gate)

  Rolle als Teil des Operationskontexts · Rahmenzugehörigkeit neuer Vertices
  über (edge_id, t) und Face-Innenkoordinaten · Annotation + Undo · symmetrische
  Ketten · Rahmen-Kette vs. Rig-Knochen (ARCH-01, CHARACTER_SYSTEMS_RESEARCH)

SPUR 3 — AUSSERHALB VON PRODUCTION, BIS VALIDIERT

  Option C · Option D · Opt-in aus Option E · Rezept-Bibliothek
  jedes Neu-Abspielen von Topologie · jeder Graph
```

### 15.1 Die Spuren im Einzelnen

| Spur | Inhalt | Voraussetzung | Wer entscheidet |
| --- | --- | --- | --- |
| 1 — sofort im Lab | X1, X4a, X2, X3 | nichts außer dem Playground; X2 braucht gemerkte Gestenwerte | Priorität: Manu; Umsetzung: Claude Code (Typ A für X1/X2, UX-System für X3) |
| 2 — Architektur-Research | EXT-Q13, Q15, Q17 als Anwendungsfall in ARCH-02 einbringen | offener Stand von ARCH-02 | Typ-C-Gate, Richtung durch Manu |
| 3 — außerhalb von Production | Option C, D, E-Opt-in, Rezept-Bibliothek, Topologie-Replay, Graph | positive Ergebnisse aus Spur 1 und ein entschiedenes ARCH-02 | Promotion ausschließlich Manu (M3) |

### 15.2 Hinweis an das laufende Extrude-Work-Package

Diese Research fordert vom WP nichts („BUILD darf keine neue Erkenntnis behaupten“). Drei **Beobachtungen**, über die Manu entscheidet:

1. Das Tool kennt seine neuen Faces schon (`new_face_ids`) und wählt sie nach dem Commit aus. Genau das ist die Rollen-Referenz, auf der jede spätere Automatisierung aufbauen würde. Bleibt dieses Residue so, bleiben alle Optionen offen.
2. Die Gestenwerte der letzten Operation (Distanz; später Winkel, Faktor) als Daten festzuhalten, ist die einzige Voraussetzung für X2 und Option A.
3. Die stille Ersatznormale `(0, 0, 1)` bei entarteten Faces (§11, F6) ist für die Live-Geste unkritisch und nur für künftiges Neu-Abspielen relevant.

### 15.3 Modell-Empfehlung für Handoffs (nach Manus Regel)

| Schritt | Typ | Modell + Effort |
| --- | --- | --- |
| X1 Logger, X2 Repeat-Varianten | A (klar abgegrenzt) | Sonnet 5, high |
| X3 Session-Lab | UX-System, Varianten-Bau | Sonnet 5, high (Spezifikation vorher im UX-System) |
| ARCH-02-Anwendungsfall (Spur 2) | C | Opus 5.5, high bis xhigh |
| Nachtrag dieses Dokuments ins Repo | sehr klein, mechanisch | Sonnet 5, medium |

## Was dieses Dokument nicht beantwortet

- Keine Tastenbelegung, keine Terminologie, keine Architecture Decision, kein Work Package.
- Keine Semantik für Edge- und Vertex-Extrude und kein Design für die numerische Eingabe.
- Nicht geprüft: Silo und Cinema 4D im Detail, die History-Architektur des Original-Mirai (`MIRAI_SYSTEMS_1999.md` §10 bleibt offen), LightWaves Verzicht auf Construction History (nur KONSENS).
- Manus eigene Ketten sind nicht gemessen; alle Workflow-Aussagen in §2 und §3 sind Rekonstruktionen bis X1.
- Quellenhinweis: Die Herstellerseiten und Foren wurden am 2026-09-30 über die Websuche gelesen (Seitenauszüge, nicht jede Seite vollständig geöffnet). Vor einer Architekturentscheidung, die sich auf eine einzelne Quelle stützt, diese Seite vollständig prüfen.

## Quellen

Zugriff jeweils 2026-09-30.

**Softimage / XSI**

- [Operator Stack](https://download.autodesk.com/global/docs/softimage2014/en_us/files/basic_mod_OperatorStack.htm) · [Immediate Mode](https://download.autodesk.com/global/docs/softimage2014/en_us/files/basic_mod_ImmediateMode.htm) · [FreezeModeling](https://download.autodesk.com/global/docs/softimage2014/en_us/sdkguide/si_cmds/FreezeModeling.html) · [About ICE Modeling](https://download.autodesk.com/global/docs/softimage2014/en_us/files/GUID-C4A23B19-A390-4062-9698-3BC631D6BCA9.htm) · [Custom Toolbars](https://download.autodesk.com/global/docs/softimage2014/en_us/files/toolbars_shelves_CustomToolbars.htm)
- [xsi\_list: ICE Modelling (Luc-Eric Rousseau, 2011)](https://groups.google.com/g/xsi_list/c/Rz1M3332xT0)

**Maya**

- [polyExtrudeFacet](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/Commands/polyExtrudeFacet.html) · [Construction History and Tweaks (SDK)](https://help.autodesk.com/cloudhelp/2017/ENU/Maya-SDK/files/Polygon_API_Construction_History_and_Tweaks.htm) · [Softimage-Maya Bridge: Operator Stack vs. DG](https://help.autodesk.com/cloudhelp/2016/ENU/Maya/files/GUID-72C44120-DF03-4917-AF1B-26672E84CE59.htm) · [Metadata](https://help.autodesk.com/cloudhelp/2016/ENU/Maya/files/GUID-52A836EE-9A09-4B50-8C44-1A6941EAE9D7.htm) · [Scripts auf dem Shelf speichern](https://download.autodesk.com/us/maya/2010help/files/Saving_scripts_to_the_Shelf_Beyond_the_Lesson.htm)
- [GS Toolbox: Store Edits and Undo Edit](https://gs-toolbox.readthedocs.io/en/latest/store-edits-and-undo-edit.html)

**3ds Max**

- [Glossar: Topology-Dependent Modifier](https://download.autodesk.com/us/3DSmax/2012help/files/GUID-BBC25115-E5C2-4E81-BF39-0CE1BC72707-3569.htm) · [Edit Poly Mode Rollout](https://help.autodesk.com/cloudhelp/2017/ENU/3DSMax/files/GUID-34663E40-9485-4270-9FDA-7939DFA80B69.htm) · [Edit Poly Modifier (Press/Release-Shortcuts)](https://download.autodesk.com/us/3DSmax/2012help/files/GUID-1230619A-8CB3-4411-B07D-C133716F61F-401.htm) · [Extrude-Caddy: Apply and Continue](https://download.autodesk.com/us/3dsmax/2012help/files/GUID-120012A8-90FC-460F-9287-5FB4545B1EA-620.htm) · [Macro Recorder](https://help.autodesk.com/cloudhelp/2015/ENU/3DSMax/files/GUID-7F0698EB-236E-48EF-96B3-4DF011DF86B0.htm)
- [Polycount-Diskussion zum Kollabieren von Edit Poly](https://polycount.com/discussion/comment/2472705/)

**Modo**

- [Modeling Techniques](https://learn.foundry.com/modo/Content/help/pages/modeling/modelling_types.html) · [Procedural Preset Browser (Tool Pipe)](https://learn.foundry.com/modo/Content/help/pages/modeling/procedural_preset_browser.html) · [Procedural Geometry (SDK)](https://learn.foundry.com/modo/developers/latest/sdk/pages/tutorials/Procedural%20Geometry.html) · [Procedural Selection](https://learn.foundry.com/modo/Content/help/pages/modeling/procedural_selection.html) · [Bug ID 392981](https://supportsandbox.foundry.com/hc/en-us/articles/32696444768530-ID-392981-Select-by-Previous-MeshOp-does-not-update-indices-when-duplicated)

**LightWave**

- [Multishift](https://docs.lightwave3d.com/lw2024/multishift-tool.html) · [Bevel](https://docs.lightwave3d.com/lw2024/bevel-tool.html) · [Extrude](https://docs.lightwave3d.com/lw2024/extrude.html)

**Blender**

- [Extrude Mesh Node](https://docs.blender.org/manual/en/dev/modeling/geometry_nodes/mesh/operations/extrude_mesh.html) · [Designnotiz Tweak Modifier](https://wiki.blender.jp/Dev:Source/Modifiers/Stack/TweakModifier)

**Houdini**

- [PolyExtrude (Doku)](https://www.sidefx.com/ja/docs/houdini/nodes/sop/polyextrude.html) · [Forum 2017: Extrude-Kette per Prim-Nummer](https://www.sidefx.com/forum/topic/49686/) · [Forum 2025: Gruppen vs. direkt auswählen](https://www.sidefx.com/forum/topic/104031/)

**Wings 3D**

- [Edit-Menü (Repeat, Repeat Args, Repeat Drag)](https://www.wings3d.com/?p=329) · [Hotkeys](https://wings3d.com/?p=265) · [Forum: Joys of Sweep](https://www.wings3d.com/forum/showthread.php?pid=8815)

**SketchUp**

- [Push/Pull-Wiederholung per Doppelklick](https://forums.sketchup.com/t/how-do-i-duplicate-push-pull-w-o-entering-distances-repeatedly/21259) · [SketchUcation mit Zitaten aus dem User’s Guide 2006](https://community.sketchucation.com/post/991659) · [Push/Pull-Algorithmus, Entwicklerbeitrag](https://forums.sketchup.com/t/push-pull-algorithm/175645?page=2)

**Plasticity**

- [CG Channel 2023](https://www.cgchannel.com/2023/04/check-out-promising-new-nurbs-modeller-plasticity)

**CAD / Persistent Naming**

- [FreeCAD Wiki: Topological naming problem](https://wiki.freecad.org/Topological_naming_problem/en) · [Kripac 1997](<https://doi.org/10.1016/S0010-4485(96)00040-1>) · [Capoyleas, Chen, Hoffmann 1996](<https://doi.org/10.1016/0010-4485(95)00014-3>) · [Agbodan et al. 2003](https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf)

**Forschung**

- [MeshFlow (2011)](https://history.siggraph.org/learning/meshflow-interactive-visualization-of-mesh-construction-sequences-by-denning-kerr-and-pellacini/) · [MeshGit (2013)](https://history.siggraph.org/?p=108309) · [MeshHisto (2015)](https://history.siggraph.org/?p=210393) · [3DFlow (2015)](https://history.siggraph.org/?p=112781)

**Workflows**

- [SimplyMaya-Forum 2002](https://simplymaya.com/forum/showthread.php?p=8277) · [highend3d: Subdivision Modeling of a Human](https://highend3d.com/maya/tutorials/modeling/polygon/c/subdivision-modeling-of-a-human/page/2) · [Udemy-Kursbeschreibung](https://www.udemy.com/course/realistic-character-modeling-for-game-in-maya-and-zbrush/)

## Verwandte Dokumente (Repo)

- `docs/research/MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` — §16 (Erinnern/Wiedererkennen, Rezepte, H7, H8), E1, T5
- `docs/research/CHARACTER_SYSTEMS_RESEARCH.md` — Rahmen-Kette vs. Rig (EXT-Q17)
- `docs/research/symmetry/` — Korrespondenz unter Topologie-Operationen; AD-SYM-01, AD-SYM-02
- `docs/research/topology/KNIFE_CROSS_FACE_DISCOVERY.md` §7 — Provenienz-Haken
- `docs/architecture/AD-017-*` — Session-Modell des Knife; `AD-016` — Q/W/E-Hoheit; `AD-012`/`AD-014` — Transform Space
- `docs/architecture/ROADMAP.md` — ARCH-01, ARCH-02
- `docs/design/artist_playground/RESEARCH_MAP.md`, `UX_RESEARCH.md` — Composition, Residue
- `docs/research/MIRAI_SYSTEMS.md`, `MIRAI_SYSTEMS_1999.md` — Operationen als reproduzierbare Aktionen, offene History-Frage
- `playground/topology_tools/extrude.py`, `playground/experiments/articulation/`
- `experiments/rigging-skinning-morphing/` — FINDINGS-3C
