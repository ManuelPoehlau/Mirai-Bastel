# Modeling Workflow & Topology Grammar — Research V1.1

**Status:** Discovery — Recherche, keine Entscheidungen
**Datum:** 2026-09-21 (V1) · 2026-09-21 (V1.1: §15 Local Topology Control — Deep Dive)
**Modus (M5):** Discovery
**Rolle:** Modeling Workflow Researcher / Artist-Workflow-Analyse
**Vorgesehene Ablage:** `docs/research/MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md`

> Dieses Dokument trifft **keine** Produktentscheidungen, keine Tool-Auswahl, keine
> Hotkey-Aussagen und keine Architekturaussagen. Es sammelt Evidenz und erzeugt Fragen.
> Entscheidungen trifft der Artist, in den dafür zuständigen Dokumenten.

---

## 0. History Awareness (M1) und Context Check (M2)

### 0.1 Existenzprüfung — was es schon gibt

| Bereich | Autoritatives Zuhause | Verhältnis zu diesem Dokument |
|---|---|---|
| Interaction Grammar (Select / Transform / Topology als **UX**-Fragen) | `docs/design/artist_playground/UX_RESEARCH.md`, Research Map V1 | **Nicht hier.** Dieses Dokument liefert dorthin höchstens Fragen, keine UX-Antworten. |
| Tweak als SelectMethod-Variante | Tweak-Design-Entscheidung (Playground) | Wird hier nur als bestehende Designrichtung erwähnt, nicht neu verhandelt. |
| Character Systems (Rigging, Skinning, Deformation, Morph, Facial-Systeme) | `CHARACTER_SYSTEMS_RESEARCH.md` | Abschnitte 8 und 9 hier betrachten Topologie **nur aus Modellierersicht**. Alles, was Rig-, Deformer- oder Morph-*Systeme* betrifft, gehört dorthin. |
| Rigging/Skinning/Morphing (technische Realität) | `experiments/rigging-skinning-morphing/` (AD-005, CORE_API_AUDIT, FINDINGS-3C) | Liefert die technische Grundlage für Abschnitt 8. Wird zitiert, nicht dupliziert. |
| Topologie-Operationen im Core | `experiments/topology/`, Core-API-Audit | Die Operationsliste in Abschnitt 10 beschreibt die Branche, nicht den Mirai-Core-Stand. |
| Input / Bindings / Artist Input Truth | AD-013, `tools/Input_Mapping_Tool/artist_input_truth.json` | Hier bewusst **keine** Tastenaussagen. |
| Reihenfolge der Arbeitspakete | `ROADMAP.md` (Modeling Track, WP-03, ARCH-02) | Dieses Dokument verschiebt nichts in der Roadmap. |

**Ergebnis der Existenzprüfung:** Ein Dokument, das *Modeling-Workflow als Artist-Grammatik*
behandelt, wurde nicht gefunden. Die vorhandenen Dokumente decken drei Nachbargebiete ab
(Interaction Grammar, Character Systems, Topologie-Technik), aber nicht die Frage
„wie denkt ein Modeller, bevor er ein Werkzeug anfasst". Deshalb neues Dokument statt Einbau.

**Verworfenes wurde nicht gefunden.** Es gibt keinen Hinweis darauf, dass ein Modeling-Grammatik-Ansatz
schon einmal geprüft und abgelehnt wurde. Falls doch, gehört dieser Hinweis in die zuständige Decision.

### 0.2 Was in dieser Session **nicht** geprüft werden konnte

Ehrliche Lücke: Zugänglich waren nur `AGENTS.md`, `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md`,
`README.md` und `ROADMAP.md`. Der Wortlaut von `UX_RESEARCH.md`, der Inhalt von
`docs/research/`, die FINDINGS der Topologie-Experimente und die bestehenden Konventionen
für Research-Dokumente konnten **nicht gelesen** werden.

Konsequenz: Formale Konventionen dieses Dokuments sind aus `AGENTS.md` abgeleitet, nicht aus
einem vorhandenen Research-Dokument abgeschaut. Vor dem Commit bitte einmal kurz gegenprüfen.

### 0.3 Context Check — meine Annahmen (nur korrigieren, wenn falsch)

1. `docs/research/` existiert als Ablageort für Research-Dokumente. Falls nicht: dieses Dokument
   neben `CHARACTER_SYSTEMS_RESEARCH.md` legen, nicht ein neues Verzeichnis erfinden.
2. Es existiert noch kein Dokument mit demselben Zweck. Falls doch, wird dieses hier dort
   eingearbeitet statt als zweites Zuhause zu bestehen.
3. Produktionsstand Modeling: vorhanden sind `split` / `collapse` / `connect`, Loop-/Ring-Erkennung
   und -Selektion sowie Connect Edges. Loop Insert/Remove, Extrude, Inset, Bevel, Bridge, Slide,
   Dissolve und Subdivision sind als Produktionsfähigkeiten **nicht** als abgeschlossen angenommen.
4. Facial- und Deformations-Topologie ist derzeit **Forschungshintergrund**, kein Bauziel.
5. Dieses Dokument ist Grundlagenforschung für einen späteren Artist-Selbstversuch, nicht für
   das nächste Arbeitspaket.

---

## 1. Forschungsfrage

> **Welche Operationen, Denkschritte und Interaktionsmuster braucht ein Artist tatsächlich,
> um in seinem bevorzugten Workflow effizient zu modellieren?**

Untergeordnet:

- Welche Operationen sind wirklich fundamental, welche nur workflow-abhängig, welche bloß
  technische Bausteine?
- Welche höheren Absichten tauchen bei Artists wiederholt auf?
- Wo zwingen heutige DCCs den Artist, in Low-Level-Topologie zu denken?
- Was davon ist persönlicher Geschmack, was ist breit tragfähiges Prinzip?

---

## 2. Scope

**Im Scope:** Denkprozess vor der Operation, Edge Flow als aktive Tätigkeit, Pole/Dreiecke/Ngons als
praktische Werkzeuge, deformationsgetriebene Topologie, Facial-Topologie als Vergleich mehrerer
Schulen, Verhältnis von Low-Level-Operationen zu Artist-Absichten, Vorbereitung eines
Artist-Selbstversuchs.

**Nicht im Scope:** Tool-Auswahl für Mirai-Bastel, Hotkeys, HUD, Architektur, Core-Änderungen,
Rig-/Deformer-/Morph-*Systeme* (→ `CHARACTER_SYSTEMS_RESEARCH.md`), UX-Verdikte
(→ Artist Playground), Roadmap-Änderungen.

---

## 3. Methode und Evidenzdisziplin

Untersucht wurden Primärquellen (Artikel der Werkzeugentwickler selbst, Software-Dokumentation,
Fachliteratur zur Subdivision), ergänzt um Community-Material.

### Evidenzstufen

| Stufe | Bedeutung |
|---|---|
| **FAKT** | Dokumentiert in einer nachprüfbaren Quelle (Primärartikel, Handbuch, Fachpublikation). |
| **BEOBACHTUNG** | Aus mehreren Quellen erkennbares Verhalten, ohne einzelne autoritative Festlegung. |
| **KONSENS** | Breit vertretene Community-Meinung. Verbreitung ≠ Beweis. |
| **INTERPRETATION** | Meine Deutung der Befunde. Ausdrücklich nicht die Aussage der Quelle. |
| **HYPOTHESE** | Testbare Vermutung, noch ohne Evidenz. |
| **OFFENE FRAGE** | Bewusst unbeantwortet. |

### Methodenkritik (wichtig)

Die Quellenlage ist stark asymmetrisch. Zu Topologie existiert sehr viel Tutorial- und
SEO-Material, das dieselben Faustregeln wiederholt, ohne sie zu begründen. Ein Teil der
aktuellen Treffer ist erkennbar maschinell erzeugter Fließtext. Solches Material ist hier
höchstens als **KONSENS** eingestuft, nie als FAKT — auch wenn es selbstbewusst formuliert ist.

Zweite Verzerrung: Die am besten dokumentierten Workflows stammen aus der Film- und
Charakterproduktion um 1999–2013. Sie sind nicht automatisch der heutige Normalfall,
und schon gar nicht automatisch der richtige Workflow für einen einzelnen Artist.

---

## 4. Quellen und untersuchte Artists

### 4.1 Bay Raitt / Greg Minter — „Digital Sculpture Techniques" (Nichimen Graphics, 2000)

**Die wichtigste Quelle dieses Dokuments** — und für Mirai-Bastel ein Glücksfall: Sie beschreibt
genau den Workflow, der in Mirai gedacht war, geschrieben vom Produktverantwortlichen
und vom Autor der Mirai-Dokumentation.

- Was dokumentiert ist: Volume Modeling, Derived Surfaces (Kontrollobjekt → geglättete Fläche),
  Modellieren mit Blick auf Smoothing, Modellieren für Animation, Edge Loops.
- Stärke der Evidenz: **hoch**, Primärquelle.
- Übertragbarkeit auf Mirai-Bastel: **hoch** — es ist die Ahnenlinie des Projekts.
- Einschränkung: Stand 2000. Hardware-Aussagen und der Vergleich zu NURBS sind historisch.
  Die *Denkfiguren* sind es nicht.

Biografischer Hintergrund (FAKT): Raitt war Creature Facial Lead für Gollum bei Weta Digital,
war zuvor bei Nichimen am Redesign von Mirai beteiligt und baute für Gollum ein
FACS-basiertes Netz aus rund tausend Shapes. Der Begriff „Edge Loop" wird auf einen Artikel von
Raitt aus dem Jahr 1999 zurückgeführt.

### 4.2 Brian Tindall / Hippydrome — „The Art of Moving Points" (2013)

- Was dokumentiert ist: Facial Articulation als eigenes Handwerk; Arbeit mit
  Point Weight Containers und Deformern; „Three Curve Principle"; eine definierte
  Order of Operation. Der Ansatz ist ausdrücklich software-unabhängig formuliert.
- Stärke der Evidenz: **mittel** — Existenz, Autor und Themen sind belegt, der Buchinhalt
  wurde hier nicht im Detail geprüft (kostenpflichtig).
- Übertragbarkeit: **indirekt.** Tindall denkt vom Endzustand her („wie müssen sich die Punkte
  bewegen"), nicht vom Modellierschritt her.
- Wichtig: Tindalls Kernaussage ist nicht „so sieht richtige Topologie aus", sondern
  „Topologie ist die Voraussetzung dafür, Punkte kontrolliert bewegen zu können".

### 4.3 Wings 3D — Dokumentation und Handbuch

Die Wings-Linie stammt ausdrücklich von Nendo und Mirai ab, ist offen dokumentiert und
damit die am besten nachprüfbare Quelle für die *Interaktionsseite* dieser Tradition.

Dokumentierte Eigenschaften (FAKT):

- Kontextsensitive Menüs: Das Menü hängt vom aktuellen Selektionsmodus ab
  (Vertex / Edge / Face / Body). Jeder Modus hat seinen eigenen Werkzeugsatz.
- **Tweak Mode** als eigene, schnelle Anpassungsart neben dem normalen Werkzeugweg.
- **Magnets** (Soft Selection): Sie wirken nicht auf die Selektion, sondern auf die *Umgebung*
  der Selektion. Zusätzlich gibt es Magnet Masking, um Bereiche gegen den Magneten zu sperren.
- Magnettyp und Achsbeschränkung sind **während** eines Tweak-Vorgangs umschaltbar.
- Werkzeugbestand: Move, Scale, Rotate, Extrude, Bevel, Bridge, Cut, Weld, dazu Sweep,
  Plane Cut, Circularise, Intersect.

Der letzte Punkt ist für uns interessanter als er aussieht: „Magnetart mitten in der Geste
ändern" ist genau die Dimension, die die Research Map als *Composition* führt.

### 4.4 Subdivision-Fachliteratur

- **FAKT:** Die Grenzfläche der Catmull-Clark-Unterteilung ist in regulären Bereichen C²-stetig,
  an Extraordinary Vertices (Valenz ≠ 4) nur C¹ (Peters/Reif). Dort ist das Normalenfeld schwächer,
  was die bekannten Shading-Artefakte erzeugt.
- **FAKT:** Nach einem Unterteilungsschritt besteht das Ergebnis vollständig aus Quads,
  auch wenn die Eingabe Dreiecke enthielt. Ein Dreieck verschwindet also nicht — es hinterlässt
  einen dauerhaften Pol.
- **FAKT:** Es existiert Forschung, die Shading-Artefakte an Extraordinary Points behebt,
  indem nicht nur die Geometrie, sondern auch die Normalen mitunterteilt werden
  („Subdivision Shading"), inklusive Erweiterung auf Semi-Sharp Creases.

Der letzte Punkt ist bemerkenswert: Ein Teil dessen, was Artists als „Topologiefehler" erleben,
ist streng genommen ein *Normalen-/Shading-Problem* und nicht zwingend ein Geometrieproblem.

### 4.5 Instant Field-Aligned Meshes (Jakob, Tarini, Panozzo, Sorkine-Hornung, SIGGRAPH Asia 2015)

- **FAKT:** Das Verfahren optimiert zwei Felder — ein *Orientierungsfeld*, das die Kantenrichtungen
  des Ergebnisses vorgibt, und ein Positionsfeld für die Vertexpositionen. Es läuft schnell genug
  für interaktives Arbeiten. Modo nutzt den Algorithmus für automatische Retopologie.
- **INTERPRETATION:** Hier ist „Edge Flow" erstmals ein **eigenes, manipulierbares Objekt** und
  nicht bloß eine Nebenwirkung von Operationen. Singularitäten des Feldes entsprechen den Polen.
- **Vorsicht:** Das Verfahren ist Retopologie, nicht Modellieren. Es beantwortet nicht, wie ein
  Artist beim Aufbau eines Modells denkt. Es zeigt nur, dass „Fluss" formalisierbar ist.

### 4.6 Community-Material (Polycount und vergleichbare Foren)

Eingestuft als **KONSENS**. Verwendet für wiederkehrende Faustregeln und, wichtiger, für
*Uneinigkeiten* — die sind aufschlussreicher als die Regeln.

---

## 5. Beobachtete Modeling-Patterns

### 5.1 Erst Volumen, dann Oberfläche

**FAKT (Raitt/Minter).** Der Bildhauer legt zuerst schnell das Volumen fest und verfeinert danach
die Oberfläche. Volume Modeling überträgt das: wachsen lassen, extrudieren, Kanten/Flächen/Vertices
eines einfachen Primitivs verschieben. Der Gegenentwurf (NURBS/Patches) definiert zuerst die
Oberfläche und danach das Volumen — laut Artikel die falsche Reihenfolge für einen Bildhauer.

**INTERPRETATION:** Dieser Satz ist für uns kein Tool-Argument, sondern eine Aussage über
*Reihenfolge des Denkens*. Er sagt: Der Artist will früh eine Form haben, die er beurteilen kann.

### 5.2 Das Kontrollobjekt bewusst klein halten

**FAKT (Raitt/Minter).** Typisches Kontrollobjekt: 500–1000 Polygone. Die hohe Auflösung entsteht
abgeleitet, nicht per Hand. Ausdrücklich genannter Grund: Wer mit einem so komplexen Mesh arbeitet,
dass immer nur ein Ausschnitt sichtbar ist, verliert die Spontaneität, die ausdrucksstarke Formen
überhaupt erst möglich macht.

**INTERPRETATION:** Das ist ein *Workflow*-Argument, kein Performance-Argument. Dichte kostet
nicht nur Rechenzeit, sie kostet Überblick und damit künstlerische Entscheidungsfähigkeit.

### 5.3 Drei Bewertungsachsen: Silhouette, Kontur, Bewegung

**FAKT (Raitt/Minter).** Silhouette ist der 2D-Umriss aus einem Blickwinkel; Kontur ist deren
3D-Entsprechung und zeigt sich daran, wie Licht über das Modell fällt; Bewegung ist die Frage,
ob die Form in allen Posen noch stimmt.

**INTERPRETATION:** Das sind drei *Prüffragen*, keine Werkzeuge. Jede Topologieentscheidung wird
an ihnen gemessen. Ein Modeller fragt nicht „ist das saubere Topologie", sondern „hält das die
Silhouette, hält das die Kontur, hält das die Bewegung".

### 5.4 Licht als Modellierwerkzeug

**FAKT (Raitt/Minter).** Der Artikel beschreibt ausdrücklich ein Beleuchtungs-Setup zum Modellieren:
Das kamerafeste Standardlicht („Stirnlampe") verdeckt die Kontur. Empfohlen werden stattdessen
zwei mitbewegte, diagonal gegeneinander gerichtete Lichter, das untere auf 50 % gedimmt.
Ebenfalls festgehalten: Echtzeit-Renderer machen Shading, keine Schatten — das muss man beim
Beurteilen mitdenken.

**INTERPRETATION:** Die Darstellung ist kein Nebenschauplatz, sondern Teil des Werkzeugs.
Das berührt die bereits existierende Presentation-Lab-Arbeit im Playground — dort einordnen,
nicht hier.

### 5.5 Geometrie hinzufügen ist die letzte, nicht die erste Antwort

**FAKT (Raitt/Minter).** Ausdrücklich als häufiger Fehler benannt: Geometrie dort hinzuzufügen,
wo sich etwas nicht richtig verhält. Im gezeigten Beispiel bricht das Modell trotz zusätzlicher
Geometrie beim Animieren, weil die Schulter kein Kugelgelenk wie die Hüfte ist, sondern ein
schwimmendes Gelenk um die Brustmitte — die Geometrie saß an der falschen Stelle. Zusätzlich:
Geometrie, die weder zu Kontur noch zu Silhouette beiträgt, ist verschwendet.

**Das ist die schärfste Aussage der ganzen Recherche**, weil sie der verbreitetsten Faustregel
widerspricht („bei Problemen mehr Loops"). Die Quelle sagt: Erst verstehen, *was* sich bewegt,
dann entscheiden, *wo* Geometrie hingehört.

### 5.6 In der Extrempose prüfen, nicht in der Ruhepose

**FAKT (Raitt/Minter).** Gliedmaßen bis an die Bewegungsgrenze drehen, um Scherungen und
Durchdringungen am Gelenk sichtbar zu machen. Außerdem: Wenn das Skinning gut genug ist, darf
man in einer natürlicheren Pose als der üblichen T-Pose modellieren — das gibt ein besseres
Gefühl für Form, Gewicht und Persönlichkeit.

### 5.7 Formhierarchie primär / sekundär / tertiär

**KONSENS**, quer durch Tutorials und Studio-Beschreibungen: erst Blockout und Proportion,
dann mittlere Formen, dann Details; Details erst, wenn die Silhouette stimmt.
Belegte Primärquelle dafür wurde nicht gefunden — die Idee stammt ursprünglich aus der
Zeichen- und Bildhauerlehre, nicht aus 3D.

### 5.8 Zwei Grundlinien, nicht eine

**BEOBACHTUNG.** Es existieren nebeneinander:

- **Box-/Volume-Modeling:** Topologie entsteht *beim* Formen. Der Artist entscheidet Form und
  Topologie gleichzeitig.
- **Sculpt-first + Retopologie:** Form zuerst ohne Rücksicht auf Topologie, Topologie danach als
  eigener Arbeitsschritt.

Das sind zwei unterschiedliche Denkmodelle, nicht zwei Werkzeugsätze. Wer sculptet, darf die
Topologiefrage verschieben; wer box-modelliert, muss sie ständig beantworten.

---

## 6. Edge Flow und Loop Flow

### 6.1 Begriffe

**FAKT:** Ein Edge Loop ist eine Kette verbundener Kanten über die Oberfläche, meist geschlossen;
ein Edge Ring ist die Querrichtung dazu (eine Seite eines Face Loops).

**FAKT (Raitt/Minter):** Der ursprüngliche Zweck ist **nicht** Sauberkeit. Der Zweck ist,
dass die Kanten des Kontrollobjekts die Muskelstruktur nachbilden, sodass das Auswählen von
Vertices entlang eines Loops sich anfühlt, als bewege man den darunterliegenden Muskel.

**INTERPRETATION:** Ein Loop ist ursprünglich ein **Griff**, kein Qualitätsmerkmal. Die
Verwandlung des Loops von einem Manipulationswerkzeug in ein Bewertungskriterium („gute
Topologie") ist eine spätere Entwicklung der Community — und meiner Einschätzung nach der Punkt,
an dem der Begriff einen Teil seiner Bedeutung verloren hat.

### 6.2 Was Artists mit Fluss tatsächlich tun

**BEOBACHTUNG**, aus der Zusammenschau von Quellen und Praxisbeschreibungen. Wiederkehrende
Tätigkeiten:

| Tätigkeit | Worum es geht |
|---|---|
| Fluss **starten** | An einer Öffnung oder Form eine Richtung etablieren. |
| Fluss **fortsetzen** | Eine bestehende Richtung über eine Formgrenze hinweg weiterführen. |
| Fluss **umlenken** | Die Richtung ändern, ohne die Dichte zu ändern. |
| Fluss **terminieren** | Eine Richtung kontrolliert beenden, statt sie ins Nichts laufen zu lassen. |
| Dichte **erhöhen / senken** | Lokal mehr oder weniger Kontrolle, möglichst ohne globale Folgen. |
| Fluss **umverteilen** | Gleiche Geometrie, bessere Verteilung (Relax, Slide). |
| Fluss **um etwas herumführen** | Öffnungen, Gelenke, Formkanten. |

**INTERPRETATION** (präzisiert in §15.3)**:** Das eigentliche Handwerk liegt beim **Terminieren**, nicht beim Einfügen.
Einen Loop einfügen kann jedes Werkzeug. Ihn *dort enden zu lassen, wo er enden soll,* ohne
den Rest des Modells zu verändern, ist die schwierige Operation — und der Grund, warum Pole
überhaupt gezielt gesetzt werden.

### 6.3 Fluss als eigenes Objekt

**HYPOTHESE.** Der Artist denkt über Fluss als etwas, das *existiert* und eine Richtung hat.
Im Werkzeug existiert er nicht: Er ist eine Nebenwirkung davon, welche Kanten zufällig verbunden
sind. Instant Meshes zeigt, dass ein Orientierungsfeld als explizites Objekt technisch machbar ist.

Das ist ausdrücklich **keine Empfehlung**, so etwas in Mirai-Bastel zu bauen. Es ist der Hinweis,
dass die Lücke zwischen Artist-Denken und Werkzeug-Datenmodell an dieser Stelle real und
benennbar ist.

---

## 7. Pole, Dreiecke und Ngons

### 7.1 Was wirklich belegt ist

- **FAKT:** Ein Pol (Valenz ≠ 4) senkt die Stetigkeit der Grenzfläche von C² auf C¹.
  Das ist der mathematische Kern hinter „Pinching" und Shading-Wellen.
- **FAKT:** Ein Dreieck oder Ngon erzeugt nach der Unterteilung einen dauerhaften Pol. Die
  Unregelmäßigkeit verschwindet nicht, sie ändert nur ihre Form.
- **FAKT:** Ein Teil der sichtbaren Artefakte ist ein Normalenfeld-Problem und durch verbesserte
  Shading-Verfahren behebbar, ohne die Geometrie zu ändern.

### 7.2 Was daraus folgt — und was nicht

Die verbreitete Regel „Quads gut, Tris und Ngons schlecht" ist eine Vereinfachung. Präziser wäre:

> Ein Pol ist dauerhaft. Die Frage ist nicht, ob es ihn gibt, sondern **wo er sitzt**
> und **ob seine Platzierung gewollt war**.

**KONSENS** zur Platzierung, mehrfach und übereinstimmend vertreten:

- Pole gehören in flache, ruhige, wenig deformierte Zonen.
- Ein Pol direkt in einer Hochdeformationszone (Mundwinkel, Gelenkinnenseite) erzeugt zuverlässig
  Artefakte.
- Ngons sind als *Arbeitszustand* verbreitet akzeptiert und als *Endzustand* in deformierenden
  Bereichen verbreitet abgelehnt.

**INTERPRETATION:** „Intentional" heißt praktisch: Der Artist könnte auf Nachfrage sagen,
*welchen Übergang* dieser Pol bedient. Ein Pol, der einfach entstanden ist, ist der
problematische Fall — nicht der Pol an sich.

### 7.3 Der für Mirai-Bastel entscheidende Zusammenhang

**BEOBACHTUNG mit direkter Projektrelevanz:** Fast alle Aussagen über Pole beziehen sich auf
das *Ergebnis nach Unterteilung* oder *nach Deformation*. Ohne eine sichtbare Vorschau von
Subdivision oder Biegung ist die Folge einer Topologieentscheidung für den Artist **unsichtbar**.

**HYPOTHESE:** Der Wert eines Topologiewerkzeugs hängt weniger vom Werkzeug ab als von der
Sichtbarkeit seiner Konsequenz. Das ist eine testbare Aussage — siehe Experiment E3 und E4.

---

## 8. Deformationsgetriebene Topologie

> Leitfrage: **Welche Topologieentscheidungen werden getroffen, weil das Mesh sich BEWEGEN muss —
> nicht, weil es gut AUSSEHEN muss?**

### 8.1 Belegte Aussagen

- **FAKT (Raitt/Minter):** Die Geometrie des Kontrollobjekts muss den vollen Bewegungsumfang
  zulassen. Prüfung erfolgt in Extrempositionen. Zusätzliche Geometrie, die weder Kontur noch
  Silhouette bedient, ist verschwendet.
- **FAKT (Raitt/Minter):** Das Beispiel Schulter zeigt, dass die Frage „wie bewegt sich dieses
  Gelenk wirklich" der Geometriefrage vorausgeht. Falsches Gelenkmodell → Geometrie an der
  falschen Stelle → bricht trotz mehr Geometrie.
- **KONSENS:** Um ein Beugegelenk mehrere Ringe (häufig genannt: mindestens drei), auf der
  Stauchseite enger, auf der Dehnseite weiter.
- **KONSENS:** Dichte dort, wo gestaucht oder gedehnt wird; nicht gleichmäßig über das Modell.

### 8.2 Verbindung zum bestehenden Projektwissen

Die Vision des Projekts nennt genau diese Schleife: modellieren → riggen → Deformation testen →
zurück zum Modellieren → Topologie ändern → weiterarbeiten.

Aus dem Rigging-/Skinning-/Morphing-Experiment ist bereits bekannt (dort dokumentiert, hier nur
referenziert): Mutationssequenzen über `split` / `collapse` / `connect` sind **mechanisch**
überlebbar; offen sind die **semantischen** Fragen (Weight-Merge, Morph-Transfer).

**INTERPRETATION:** Diese Recherche liefert dazu eine Ergänzung aus Artist-Sicht: Die semantische
Frage „welche Gewichte gelten nach einem Collapse" hat eine *Workflow*-Entsprechung, nämlich
„wie oft passiert das überhaupt, und merkt der Artist es rechtzeitig?". Beide Fragen zusammen
gehören in die Phase-4-Entscheidungen des Experiments, nicht hierher.

### 8.3 Offener Punkt

**OFFENE FRAGE:** Die gesamte Literatur beschreibt Topologie *für* Deformation — also einen
Modeller, der antizipiert. Kaum beschrieben ist der Fall, den Mirai-Bastel anstrebt: ein Modeller,
der *währenddessen* biegen kann. Ob sich Topologieentscheidungen dadurch ändern, ist meines
Wissens nicht dokumentiert. Das ist eine echte Forschungslücke und ein starker Kandidat für einen
Artist-Selbstversuch (E4).

---

## 9. Facial Topology

**Abgrenzung:** Hier nur die *Modellierseite*. Facial-Rig-Systeme, FACS, Shape-Netze und
Correctives gehören in `CHARACTER_SYSTEMS_RESEARCH.md`.

### 9.1 Mehrere Schulen, keine kanonische Lösung

**BEOBACHTUNG.** Die untersuchten Quellen zeigen gemeinsame Grundzüge, aber keine einheitliche
Topologie:

- Konzentrische Ringe um Augenöffnung und Mundöffnung als tragende Struktur; alles andere
  schließt daran an. (KONSENS)
- Mindestens zwei Ringe um die Lidöffnung, damit das Lid Volumen hat und schließen kann. (KONSENS)
- Die Nasolabialzone als Übergangsgebiet zwischen zwei Ringsystemen — und damit als typischer
  Ort für bewusst gesetzte Pole. (KONSENS)
- Stilisierte und realistische Gesichter werden unterschiedlich gelöst, mit unterschiedlicher
  Dichte und unterschiedlicher Priorität. (BEOBACHTUNG)

**Ausdrücklich nicht behauptet:** dass eine dieser Varianten richtig ist.

### 9.2 Die Kette Form → Topologie → Deformation → Ausdruck

**FAKT (Raitt/Minter):** Mit gut angelegten Loops lassen sich auch Problemzonen wie die
Mundwinkel in jede Position bringen, ohne Silhouette, Kontur oder Bewegung zu zerstören.

**INTERPRETATION:** Die Kette läuft in der Praxis in **beide** Richtungen. Der gewünschte Ausdruck
bestimmt die nötige Deformation, die bestimmt die Topologie, die begrenzt wiederum, welche
Formen überhaupt erreichbar sind. Ein Modeller, der nur vorwärts denkt, entdeckt seinen Fehler
erst beim Animieren.

### 9.3 Zwei unterschiedliche Denkschulen

- **Raitt:** Der Loop ist ein Muskel-Griff. Man modelliert, indem man Struktur bewegt.
- **Tindall:** Punkte bewegen sich, und die Frage ist, welche Kurven diese Bewegung beschreibt
  (Three Curve Principle, Order of Operation). Topologie ist dem untergeordnet.

**INTERPRETATION:** Das sind nicht zwei Meinungen über dieselbe Frage, sondern zwei
Einstiegspunkte: einer vom Modell her, einer von der Bewegung her. Für Mirai-Bastel ist
interessant, dass beide dieselbe Voraussetzung haben — man muss das Ergebnis der Bewegung
sehen können, während man arbeitet.

---

## 10. Low-Level-Operationen vs. Artist-Intent

### 10.1 Die Gegenüberstellung

| Absicht des Artists | Typische heutige Operationskette | Reibung |
|---|---|---|
| „Hier brauche ich mehr Kontrolle." | Loop Insert → Slide → evtl. Terminierung von Hand | Der Loop läuft weiter, als gewollt. |
| „Dieser Fluss soll hier enden." | Connect / Dissolve / Collapse, mehrere Schritte | Es gibt keine Operation für die Absicht selbst. |
| „Der Fluss soll da langlaufen." | Rotate Edge, Connect, Dissolve, oft mehrfach | Nur indirekt über Einzelkanten erreichbar. |
| „Diese Zone ist zu dicht." | Dissolve / Collapse mit Aufräumen | Nebenwirkungen an den Rändern. |
| „Das soll sich beim Biegen halten." | Ringe einfügen, Abstände anpassen, testen | Test liegt in einem anderen Modus oder Programm. |
| „Die Verteilung ist hässlich." | Relax / Slide / manuelles Nachschieben | Geometrie stimmt, Verteilung nicht. |
| „Hier soll eine Öffnung hin." | Faces löschen, Rand bereinigen, Ringe anlegen | Mehrere unverwandte Schritte für eine Absicht. |

### 10.2 Was das bedeutet — vorsichtig formuliert

**BEOBACHTUNG:** Beschreibungen von Modellierarbeit sind fast durchgängig in Absichten formuliert
(„der Fluss muss um das Auge herum"), während die Werkzeuge in Mechanik formuliert sind
(„Connect Vertices"). Die Übersetzung leistet der Artist im Kopf.

**HYPOTHESE A:** Der Artist denkt in Absichten, und die Werkzeugnamen sind nur Vokabular.
**HYPOTHESE B (Gegenhypothese, ernst gemeint):** Erfahrene Artists denken tatsächlich in
Werkzeugen, weil Gewöhnung das Werkzeug zur Denkeinheit macht. Wer zehn Jahre Loop Cut benutzt,
denkt „Loop Cut", nicht „mehr Kontrolle".

Beide Hypothesen sind plausibel, und **die Recherche kann sie nicht entscheiden**. Sie lassen sich
nur am konkreten Artist messen — das ist der Kern des vorgeschlagenen Selbstversuchs (E1/E2).

**Ausdrücklich nicht gefolgert:** dass Mirai-Bastel höhere Operationen bauen sollte. Die
belastbare Aussage lautet nur: Es gibt eine messbare Differenz zwischen Absichts- und
Werkzeugsprache, und man kann sie messen, bevor man darauf reagiert.

### 10.3 Eine nützliche Unterscheidung

Aus der Recherche lassen sich drei Ebenen trennen:

1. **Mechanik** — was das Mesh tut (split, collapse, connect). Technische Wahrheit, testbar.
2. **Operation** — was der Artist auslöst (Extrude, Bevel, Loop Insert). Werkzeugsprache, gelernt.
3. **Absicht** — was der Artist erreichen will (verdichten, umlenken, terminieren). Artist-Wahrheit.

Heutige DCCs vermischen Ebene 2 und 3 stellenweise (Bevel ist beides) und trennen sie anderswo
strikt (Connect ist reine Mechanik). Diese Unschärfe scheint historisch gewachsen zu sein und
nicht entworfen. **INTERPRETATION**, nicht belegt.

---

## 11. Unterschiede zwischen Workflows

| Workflow | Grundannahme | Stärke | Trade-off | Übertragbar auf Mirai-Bastel? |
|---|---|---|---|---|
| **Volume / Box Modeling** (Mirai-Linie) | Form und Topologie entstehen gemeinsam, Kontrollobjekt bleibt klein | Volle Kontrolle, jederzeit editierbar, Rig-freundlich | Verlangt Topologie-Denken von der ersten Minute an | **Hoch.** Es ist die Ahnenlinie des Projekts. |
| **Sculpt-first + Retopologie** | Form zuerst, Topologie als eigener Schritt | Künstlerische Freiheit, keine frühen Zwänge | Zwei Arbeitswelten, Retopologie als Pflichtarbeit | Mittel. Setzt Sculpting-Infrastruktur voraus, die nicht existiert. |
| **Feldbasierte Auto-Retopologie** | Fluss ist berechenbar, Artist lenkt nur grob | Sehr schnell, formalisierter Flussbegriff | Kein Modellierverfahren; Kontrolle indirekt | Nur als Denkanstoß (Fluss als Objekt). |
| **Lowpoly-first (Games)** | Budget und Ziel-Engine entscheiden mit | Sehr pragmatisch, Dreiecke explizit erlaubt | Deformationsqualität wird bewusst eingetauscht | Teilweise; zeigt, dass „alles Quads" kontextabhängig ist. |

**BEOBACHTUNG:** Die Workflows unterscheiden sich weniger in den Operationen als in dem
**Zeitpunkt**, zu dem die Topologiefrage beantwortet werden muss. Das ist die eigentliche Achse.

**Und der ehrliche Teil:** Welcher davon zu Manu passt, ist eine persönliche Frage. Diese
Recherche kann sie nicht beantworten — sie kann nur die Experimente vorbereiten, die sie
beantworten.

---

## 12. Offene Fragen

| # | Frage | Art |
|---|---|---|
| Q1 | Denkt Manu beim Modellieren in Absichten oder in Werkzeugen? | Artist-Selbstversuch |
| Q2 | Welche Operationsketten wiederholen sich bei ihm tatsächlich? | Messbar |
| Q3 | Ändert sich eine Topologieentscheidung, wenn die Deformation sofort sichtbar ist? | Experiment |
| Q4 | Ändert sich eine Topologieentscheidung, wenn die Subdivision sofort sichtbar ist? | Experiment |
| Q5 | Ist „Terminieren" die eigentlich schwierige Operation, oder täuscht die Literatur? | Experiment |
| Q6 | Wie viel des wahrgenommenen „Topologieproblems" ist in Wahrheit Shading/Darstellung? | Technisch prüfbar |
| Q7 | Wie oft braucht ein Artist im realen Arbeiten einen Ngon als Zwischenzustand? | Messbar |
| Q8 | Ist die Flussrichtung für den Artist ein Objekt oder eine Beschreibung? | Konzeptuell, dann Experiment |
| Q9 | Wo liegt für diesen Artist die Schmerzgrenze bei Werkzeugwechseln pro Absicht? | Messbar |
| Q10 | Welcher Zeitpunkt der Topologieentscheidung passt zu Manus Arbeitsweise (§11)? | Artist Truth |

---

## 13. Kandidaten für Artist-Experimente

Alle Vorschläge sind bewusst klein gehalten und nutzen vorhandene Infrastruktur. Keiner ist
eine Bauempfehlung — es sind Vorschläge für Forschungsfragen, über deren Priorität der Artist
entscheidet.

### E1 — Griffzähler (passives Mitschreiben)

- **Frage:** Q2, Q9. Welche Operationen benutzt Manu wirklich, in welchen Ketten, wie oft?
- **Aufbau:** Der Playground schreibt bei einer realen Modellier-Session mit, welche Operation
  wann ausgelöst wurde. Keine Bewertung, keine Variante, kein Vergleich.
- **Kosten:** sehr gering. Die Research Map führt „Behavioural traces" bereits als billige
  Beobachtungsform.
- **Was es zeigt:** Häufigkeiten, Ketten, tote Werkzeuge, Wechselkosten.
- **Was es nicht zeigt:** *Warum* etwas benutzt wurde. Dafür braucht es E2.
- **Mögliche Ergebnisse:** Es gibt wiederkehrende Ketten (→ Q2 beantwortbar) / es gibt keine
  (→ These von der Absichtssprache geschwächt).

### E2 — Absichtsprotokoll (drei Sätze pro Sitzung)

- **Frage:** Q1, Q5, Q8.
- **Aufbau:** Während einer normalen Session notiert Manu drei Mal *vor* dem Handeln in einem
  Satz, was er erreichen will. Danach wird verglichen, wie viele Operationen diese eine Absicht
  gekostet hat.
- **Kosten:** nahezu null, kein Code.
- **Was es zeigt:** ob Absichten überhaupt in Absichtssprache formulierbar sind oder ob sie
  sofort als Werkzeugnamen herauskommen. Das entscheidet zwischen Hypothese A und B aus §10.2.
- **Fallstrick:** Das Protokollieren selbst beeinflusst das Denken. Deshalb wenige Sätze,
  keine Formulare.

### E3 — Konsequenz sichtbar / unsichtbar

- **Frage:** Q4, Q6.
- **Aufbau:** Dieselbe kleine Modellieraufgabe zweimal — einmal mit sichtbarer geglätteter
  Vorschau, einmal ohne. Beobachtet wird, ob sich die *Entscheidungen* unterscheiden,
  nicht das Ergebnis.
- **Kosten:** gering, wenn eine Glättungsvorschau existiert; sonst hoch. **Voraussetzung prüfen.**
- **Wichtig:** Signalling muss sonst identisch bleiben, sonst ist das Ergebnis nicht deutbar
  (bekannte Falle aus der Research Map).

### E4 — Biegen und Schauen

- **Frage:** Q3, und die Forschungslücke aus §8.3.
- **Aufbau:** Eine einfache Gelenkregion modellieren, biegen, zurück, ändern, wieder biegen.
  Nutzt möglichst das **bestehende** Rigging-/Skinning-Experiment, statt Neues zu bauen.
- **Kosten:** mittel. Rechtfertigt sich dadurch, dass es die Kernvision des Projekts direkt prüft.
- **Was es zeigt:** ob die enge Rückkopplung das Modellierverhalten wirklich ändert — die
  zentrale unbelegte Annahme des ganzen Projekts.
- **Achtung:** Dieses Experiment berührt Weight-Merge-Semantik. Diese Fragen bleiben beim
  Rigging-Experiment, sie werden hier nur ausgelöst, nicht beantwortet.

### E5 — Pole bewusst setzen

- **Frage:** Q5, Q7.
- **Aufbau:** Eine Dichteübergangs-Aufgabe (dichter Bereich trifft groben Bereich) mehrfach
  lösen, jeweils mit bewusster Notiz, wo die Pole landen sollten und wo sie tatsächlich landeten.
- **Kosten:** gering, benötigt nur vorhandene Operationen.
- **Was es zeigt:** ob „Terminieren" praktisch der schwierige Schritt ist und wie viele
  Einzeloperationen eine bewusste Polsetzung heute kostet.

**Vorgeschlagene Reihenfolge nach Erkenntnis pro Aufwand:** E2 → E1 → E5 → E3 → E4.
Die Priorität entscheidet der Artist.

---

## 14. Was wir weiterhin NICHT wissen

1. **Nichts über Manus tatsächlichen Workflow.** Diese Recherche beschreibt andere Leute.
   Jede Übertragung ist eine Vermutung.
2. **Ob die Absichtsebene stabil ist.** Möglicherweise hat jeder Artist eine andere Absichtsliste,
   und eine gemeinsame Grammatik existiert gar nicht.
3. **Ob höhere Operationen sich in der Praxis lohnen.** Kein untersuchtes Werkzeug hat das
   ernsthaft versucht; es gibt keine Evidenz für oder gegen.
4. **Den Inhalt von Tindalls Buch im Detail.** Nur Struktur und Kernbegriffe sind belegt.
5. **Wie Mirai sich tatsächlich angefühlt hat.** Belegt sind Datenstruktur, Derived Surfaces und
   die Arbeitsphilosophie — nicht der Interaktionsrhythmus, um den es dem Projekt eigentlich geht.
6. **Wie viel des Topologieproblems Darstellungsproblem ist.** §4.4 legt nahe, dass der Anteil
   nicht klein ist. Ungeprüft.
7. **Ob die Vorgehensweisen von 2000 heute noch der Normalfall sind.** Die Quellenlage ist
   historisch verzerrt.
8. **Ob der Modus „währenddessen biegen" das Modellieren wirklich ändert.** Das ist die
   zentrale Annahme des Projekts und weiterhin unbelegt.

---

## 15. Local Topology Control — Deep Dive

**Ergänzt:** 2026-09-21 (V1.1) · **Modus:** Discovery · **Verhältnis zu V1:** vertieft §6 und §7,
wiederholt deren Einführung nicht.

> **Leitfrage dieses Abschnitts:**
> Wie fügt ein erfahrener Modeller Kontrolle genau dort ein, wo sie gebraucht wird,
> ohne das ganze Kontrollmesh komplizierter zu machen als nötig?

Der Abschnitt ist nach **Problemen** geordnet, nicht nach Werkzeugen. Er beschreibt, was Artists
tun und was daraus folgt — nicht, was Mirai-Bastel tun sollte.

---

### 15.0 Das Fundament: drei harte Regeln, auf denen alles andere steht

Die Community-Faustregeln („Pole vermeiden", „Loops laufen ums ganze Modell") sind Verkürzungen
von drei mathematischen Tatsachen. Wer diese drei kennt, versteht, *warum* die Techniken
in 15.1–15.7 so aussehen, wie sie aussehen.

**Regel 1 — Ein Quad-Streifen kann im Inneren nicht enden.** — **FAKT**
Verfolgt man in einem reinen Quad-Mesh einen Streifen (Face Loop) von Quad zu gegenüberliegender
Kante, dann endet dieser Streifen auf einem geschlossenen Mesh immer dort, wo er angefangen hat.
Ein Streifen, der an einem Rand beginnt, muss an einem Rand enden; alle anderen sind geschlossen.
(Quadrilateral-Mesh-Literatur: „poly-chords" bzw. „chords".)

Konsequenz: **„Einen Loop terminieren" ist in reinen Quads streng genommen unmöglich.**
Es gibt nur drei Auswege:
- der Streifen **kehrt um** (läuft zurück, woher er kam),
- der Streifen endet an einem **echten Rand** (Öffnung im Mesh),
- ein **Nicht-Quad** (Dreieck oder Ngon) beendet ihn.

Genau das beschreibt die Praxis: Die Standard-Reduktionsmuster der Community arbeiten laut
eigener Beschreibung, indem sie die Loops **zurück in Richtung ihres Ursprungs lenken**.

**Regel 2 — Pole haben ein Vorzeichen, und die Summe ist festgelegt.** — **FAKT**
Jeder Vertex mit Valenz 3 trägt +¼ zur Euler-Charakteristik bei, jeder mit Valenz 5 trägt −¼
(diskreter Poincaré-Hopf-Satz). Für eine geschlossene, kugelartige Form (χ = 2) gilt, solange nur
3er- und 5er-Pole vorkommen: **Anzahl 3er-Pole − Anzahl 5er-Pole = 8.** Ein Würfel ist genau
dieser Minimalfall: acht 3er-Pole, keine 5er.

Konsequenz: Pole sind nicht „vermeidbar". Man kann nur entscheiden, **wie viele zusätzliche**
man setzt und **wo**.

**Regel 3 — Dichteänderung kostet ein Polpaar.** — **FAKT**
In der Meshing-Fachliteratur heißt ein Paar aus einem +¼- und einem −¼-Pol ein **Dipol**.
Dipole zu einem minimal-irregulären Quad-Mesh hinzuzufügen ist dort ausdrücklich der Mechanismus,
um **Größenänderungen des Rasters** zu ermöglichen. Ein Dipol ändert die Gesamtbilanz nicht —
er ist deshalb *lokal* platzierbar.

Die Community kennt dieselbe Tatsache unter dem Namen „E-Pol und N-Pol kommen paarweise"
(E = 5 Kanten, N = 3 Kanten). **KONSENS**, aber hier mathematisch gedeckt.

> **Die zentrale Einsicht dieses Deep Dives (INTERPRETATION, aus Regel 1–3 abgeleitet):**
> Lokale Kontrolle ist nicht umsonst. Sie wird **in Polen bezahlt**.
> Globale Kontrolle wird **in Dichte bezahlt**.
> Das Handwerk besteht darin, zu entscheiden, welche Währung man an welcher Stelle ausgibt —
> und die Pole dorthin zu legen, wo sie am wenigsten kosten.

---

### 15.1 Der Pol als absichtliches Fluss-Werkzeug

#### Was ein Pol tut

- **FAKT:** Ein 5er-Pol entsteht typischerweise beim Extrudieren: Vier Kanten bleiben in der
  Ausgangsfläche, die fünfte führt aus ihr heraus. Eine Extrusion eines Quads erzeugt vier 5er-
  und vier 3er-Pole (dokumentiert in Community-Anleitungen; mit Regel 2 konsistent, da Bilanz 0).
- **KONSENS:** Ein 3er-Pol bündelt drei Flussrichtungen, ein 5er-Pol verteilt auf fünf. Die
  Richtung eines Flusses ändert sich *an* einem Pol — sonst nirgends.
- **INTERPRETATION:** Ein Pol ist die einzige Stelle im Quad-Mesh, an der ein Loop „abbiegen"
  kann, ohne ein Nicht-Quad zu benutzen. Wer einen Loop umlenken will, *muss* also einen Pol
  platzieren oder einen vorhandenen verschieben.

#### Probleme, die ein Pol löst

| Problem | Absicht | Was der Pol tut | Folge |
|---|---|---|---|
| Ein Loop müsste sonst über das ganze Modell laufen | „Nur hier mehr, nicht überall" | Der zusätzliche Streifen kehrt am Pol um (mit Partnerpol) | Dichte bleibt lokal |
| Zwei Flussrichtungen treffen aufeinander (z. B. Ring um Auge trifft Wangenraster) | „Beide Systeme sollen sauber anschließen" | Pol sitzt am Schnittpunkt der Flüsse | Übergang ohne Nicht-Quad |
| Eine Form kommt aus einer Fläche heraus (Nase, Finger, Horn) | „Neue Richtung aus alter Fläche" | 5er-Pol am Fuß der Form | Topologisch unvermeidbar |
| Konvexe Ecke / Spitze | „Hier soll die Form zusammenlaufen" | 3er-Pol | Topologisch unvermeidbar |

**KONSENS (topologyguides):** Pole entstehen dort, wo die großen Flüsse einer Fläche sich
kreuzen — und *wo* sich die Flüsse kreuzen, entscheidet der Modeller. Daraus folgt der Ratschlag,
Pole zu **planen** statt sie nachträglich zu verschieben.

#### Pole verschieben

- **KONSENS (topologyguides):** Wird ein Pol bewegt, muss in Bewegungsrichtung ein Loop verschwinden
  und an der Herkunftsseite einer umgeleitet werden. Ein Pol ist also nicht verschiebbar wie ein
  Vertex — er ist verschiebbar nur durch **Umbau der umliegenden Streifen**.
- **FAKT (Fachliteratur):** Es gibt Forschung zu *lokalen* Operationen, die Singularitäten
  gezielt bewegen, mit kleinem Fußabdruck und unter Erhalt der Euler-Charakteristik
  (z. B. „Q-zip"). Die Mechanik existiert also als eigenständiges Forschungsthema.
- **FAKT (Community, Nendo/Mirai-Umfeld):** Als Wege, Loops und damit Pole zu erzeugen oder zu
  bewegen, werden u. a. Extrusion, Kanten-Drehen („spin edge"), Aufreißen und Schneiden genannt.
- **INTERPRETATION:** Das Drehen einer Kante innerhalb ihrer zwei Quads ändert die Valenz von
  vier Vertices gleichzeitig (zwei verlieren eine Kante, zwei gewinnen eine). Es ist damit die
  kleinstmögliche Bewegung eines Dipols — mechanisch billig, aber für den Artist nicht
  offensichtlich, weil man eine Kante anfasst, um einen Pol zu bewegen.

#### Wann ein Pol schadet

- **FAKT:** C¹ statt C² an der Polstelle (V1 §4.4). Sichtbar als Pinching oder Welle.
- **KONSENS (CG Cookie):** Nach der Unterteilung erzeugt ein 3er-Pol eine Zone *höherer*,
  ein 5er-Pol eine Zone *niedrigerer* Vertexdichte — der Dichteunterschied ist die Ursache des
  Pinchings.
- **KONSENS:** Problematisch vor allem auf gekrümmten Flächen, auf Glanzflächen, direkt an einer
  Formkante und in Hochdeformationszonen. Auf flachen, nicht deformierenden Flächen oft unsichtbar.
- **KONSENS:** Valenz 6 und höher gilt als deutlich riskanter als 3 und 5.

#### Wie weit weg ist „weit genug"? — ehrliche Antwort

**OFFENE FRAGE.** Keine der untersuchten Quellen gibt eine belastbare Distanz an.
**INTERPRETATION:** Da der Stetigkeitsverlust die direkte Umgebung des Pols im *Kontrollmesh*
betrifft, skaliert die sichtbare Störzone mit der **Größe der umgebenden Kontrollflächen**, nicht
mit einer festen Weltdistanz. Ein Pol in grobem Raster stört eine große Fläche, ein Pol in feinem
Raster eine kleine. Das würde erklären, warum Modeller Pole gern *knapp neben* dichte Regionen
legen: dort ist die Störzone klein, aber die Dichte muss nicht bis zum Pol reichen.
Diese Deutung ist plausibel, aber **ungeprüft**.

---

### 15.2 Fluss umlenken

**Problem:** Ein Loop läuft in die falsche Richtung — z. B. quer über eine Wange, statt der
Muskel- oder Formrichtung zu folgen.

| Strategie | Topologie davor → danach | Warum es wirkt | Dichte | SubD-Folge | Trade-off |
|---|---|---|---|---|---|
| **Kante drehen** | Zwei Quads teilen eine Kante → dieselben zwei Quads, Kante verbindet die anderen Ecken | Verschiebt einen Dipol um einen Schritt | unverändert | Pole wandern mit | Wirkt nur sehr lokal; viele Schritte für große Umlenkung |
| **Dissolve + neu verbinden** | Kanten eines Bereichs entfernen (Ngon) → neu schneiden | Region wird frei neu aufgeteilt | frei wählbar | Ngon muss vor SubD aufgelöst sein | Mehrere Schritte, Zwischenzustand ungültig für SubD |
| **Umleiten über Polpaar** | Streifen läuft gerade → Streifen biegt an 3er/5er-Paar ab | Pol ist die einzige Abbiegestelle | unverändert bis leicht erhöht | Zwei neue Singularitäten | Pole müssen gut platziert sein |
| **Neu aufbauen** | Region löschen → neu modellieren | Sauberster Neuanfang | frei | frei | Zeitaufwand, verliert Arbeit |

**BEOBACHTUNG:** In allen Fällen besteht Umlenken aus *Pole bewegen oder erzeugen*. Es gibt keine
Umlenkung ohne Singularität — das folgt direkt aus 15.0.

**FAKT (Raitt/Minter):** Die historische Mirai-Praxis nennt als typische Umbauoperationen u. a.
Dissolve auf Segmenten und Merge Faces. Beides sind Werkzeuge des „erst entfernen, dann neu
verbinden".

---

### 15.3 Loop terminieren

(Präzisiert V1 §6.2: Die dortige Interpretation „Terminieren ist das eigentliche Handwerk"
wird hier genauer: Terminieren im strengen Sinn gibt es in reinen Quads nicht.)

**Problem:** Ein Loop soll vor einer Region enden.

| Strategie | Was passiert | Wo entsteht die Unregelmäßigkeit | Kontext, in dem es gut geht | Kontext, in dem es schlecht geht |
|---|---|---|---|---|
| **Kehre (U-Turn)** | Der Streifen läuft zurück, woher er kam; zwei parallele Reihen sind in Wahrheit *ein* Streifen | Polpaar an der Umkehrstelle | Organische Flächen, deformierende Bereiche, wenn die Kehre in ruhiger Zone liegt | Wenn die Umkehrstelle auf eine Formkante oder einen Glanzbereich fällt |
| **Dreieck am Ende** | Streifen endet an einem Dreieck | Eine Singularität, sehr kompakt | Flache, nicht deformierende Flächen; Kontrollmesh ohne Deformation | Gekrümmte Flächen unter SubD; Deformationszonen (KONSENS) |
| **Ngon am Ende** | Streifen endet an einem Fünf- oder Mehreck | Singularität im Ngon-Zentrum nach SubD | Als *Zwischenzustand* verbreitet akzeptiert | Als Endzustand in Deformationszonen verbreitet abgelehnt |
| **Ende an einer Öffnung** | Streifen läuft in einen echten Rand (Mund, Auge, Nasenloch als Loch im Mesh) | Keine zusätzliche Singularität nötig | Wenn die Öffnung tatsächlich ein offener Rand ist | Wenn das Modell dort geschlossen ist (z. B. modellierter Mundinnenraum) — dann läuft der Streifen weiter |
| **In geschlossenen Ring einbinden** | Der Streifen wird Teil eines Rings um ein Merkmal und schließt sich dort | An den „Ecken" des Rings | Augen, Mund, jede runde Form | Wenn das Merkmal selbst zu klein ist für einen eigenen Ring |

Schematisch, auf Streifen-Ebene (keine echte Mesh-Abbildung):

```
 Reihe A  ───────────────────────────────►   läuft durch
 Reihe B  ─────────────────┐
                           │  Kehre: B und C sind EIN Streifen
 Reihe C  ◄────────────────┘
          dichter Bereich  │  grober Bereich
```

**FAKT-gestützte INTERPRETATION — die Paritätsregel:** Weil ein umkehrender Streifen die
Übergangslinie *zweimal* kreuzt, kann eine Kehre die Zahl der Reihen nur um **zwei** verringern.
Reine Quad-Übergänge wie 3→1, 4→2, 5→3 sind deshalb möglich; 2→1 und 4→1 nicht, ohne ein
Nicht-Quad oder eine Änderung an anderer Stelle.

**BEOBACHTUNG, die diese Deutung stützt:** Die Community-Sammlung von Reduktionsmustern nennt
genau 2→1 und 4→1 als die schwierigsten Fälle und löst sie mit Dreiecken oder Ngons; 3→1, 4→2 und
5→3 werden als Standard-Umlenkungen beschrieben, die alle derselben Grundform folgen. Ein Anwender
beschreibt das Problem ebenfalls: Ungerade Reihenzahlen, die auf gerade treffen, landen am Ende
immer bei einem 2→1-Rest.

**Die Meinungsverschiedenheit (bewahrt):**
- Die eine Seite behandelt das 2→1-Dreieck als tolerierbar, besonders auf flachen, nicht
  deformierenden Flächen und mit der Beobachtung, dass nach der Unterteilung ohnehin alles Quads sind.
- Die andere Seite vermeidet es und nimmt lieber einen zusätzlichen Loop an anderer Stelle in Kauf.
- **Beide haben recht, in unterschiedlichen Kontexten.** Das Dreieck spart Dichte und kostet
  Glätte; der Zusatzloop spart Glätte und kostet Dichte. Es ist dieselbe Währungsfrage wie in 15.0.

---

### 15.4 Lokal verdichten

**Problem:** „Ich brauche hier mehr Kontrolle."

**Zuerst die Frage, die Raitt/Minter stellen würden — FAKT:** Braucht es wirklich mehr Geometrie?
Die Primärquelle nennt das Hinzufügen von Geometrie an falsch verhaltenden Stellen als häufigen
Fehler und Geometrie ohne Beitrag zu Kontur oder Silhouette als verschwendet. Außerdem: Schärfe
entsteht durch **Zusammenrücken vorhandener Kanten** auf dem Kontrollobjekt.

Daraus ergibt sich eine Rangfolge, die in der Praxis **BEOBACHTET** wird (nicht als Regel belegt):

| Stufe | Strategie | Dichte | Pole | Wann |
|---|---|---|---|---|
| 0 | **Vorhandene Vertices verschieben** | unverändert | keine neuen | Wenn die Form falsch ist, nicht die Auflösung |
| 1 | **Vorhandene Kanten zusammenschieben / gleiten** | lokal umverteilt, gesamt gleich | keine neuen | Wenn mehr Schärfe oder Krümmung *hier* und weniger *dort* akzeptabel ist |
| 2 | **Crease statt Geometrie** (s. 15.7) | unverändert | keine neuen | Wenn es um Schärfe geht, nicht um Formkontrolle |
| 3 | **Lokaler geschlossener Ring** (Inset-artig) | nur innen erhöht | Polpaare an den Ringecken | Wenn eine abgegrenzte Region mehr Kontrolle braucht |
| 4 | **Teil-Loop mit Kehre** | im Kehrbereich erhöht | ein Polpaar pro Kehre | Wenn die Verdichtung einen Streifen entlang laufen soll |
| 5 | **Teil-Loop mit Dreieck/Ngon-Ende** | lokal erhöht | eine kompakte Singularität | Statische Flächen, Zwischenzustände |
| 6 | **Durchgehender Loop** | global erhöht | keine neuen | Wenn die Dichte überall ohnehin nützlich ist |

**INTERPRETATION:** Stufe 6 ist das, was Werkzeuge am leichtesten machen (ein Klick),
und genau das, was die Leitfrage vermeiden will. Die Stufen 3–5 sind das, was die Leitfrage
beschreibt — und sie verlangen alle, dass der Artist **einen Ort für Pole wählt**.

**Die Entscheidung „wo beginnt und endet die Verdichtung?"** — **OBSERVATION/KONSENS:** Artists
legen Beginn und Ende dorthin, wo (a) die Form ruhig ist, (b) wenig Deformation stattfindet,
(c) ein Flusssystem ohnehin in ein anderes übergeht. Die dritte Bedingung ist die wichtigste,
weil dort bereits Pole sitzen und ein zusätzlicher Dipol weniger auffällt.

---

### 15.5 Dichte wieder reduzieren / Übergänge

**Problem:** Von einer dichten Zone in eine grobe übergehen, oder eine zu dichte Zone ausdünnen.

- **Reduktionsmuster** (3→1, 4→2, 5→3 als Kehre; 2→1 und 4→1 mit Nicht-Quad) — siehe 15.3.
- **Streifen entfernen:** In der Fachliteratur heißt das Entfernen eines ganzen Quad-Streifens
  „Chord Collapse". **FAKT:** Solche Streifen sind oft nicht lokal, sondern winden sich über die
  Oberfläche; sie zu entfernen vergröbert dann weit mehr als gewollt.
- **Teilstreifen entfernen:** **FAKT:** In der Produktion (EA Frostbite, GDC-Vortrag, in der
  Fachliteratur referenziert) wird eine Variante genutzt, die nur *Teile* eines Streifens entfernt
  — um den Preis von Dreiecken.

**INTERPRETATION:** Das ist exakt dieselbe Situation wie beim Verdichten, nur rückwärts:
**„einen Loop nur hier entfernen"** ist das Spiegelbild von **„einen Loop nur hier hinzufügen"**,
und beide scheitern in reinen Quads an Regel 1. Die industrielle Lösung akzeptiert dafür Dreiecke.

**FAKT (Raitt/Minter):** Mirai erlaubte, die *abgeleitete* Fläche per Dissolve und Merge Faces zu
reduzieren, ohne die Beziehung zum Kontrollobjekt zu zerstören. Das ist eine historische Form von
„Dichte dort senken, wo sie nichts beiträgt" — auf der Ergebnisseite statt auf dem Kontrollmesh.

---

### 15.6 Lokale Kontrolle ohne globale Loop-Ausbreitung — die Synthese

Zusammengeführt aus 15.0–15.5:

1. **Erst prüfen, ob es wirklich an Auflösung fehlt** (FAKT, Raitt/Minter). Oft fehlt es an
   Position oder Verteilung.
2. **Wenn doch:** Jede lokale Verdichtung muss den neuen Streifen entweder **schließen**
   (Ring), **umkehren** (Kehre), **an einen Rand führen** (Öffnung) oder **mit einem Nicht-Quad
   beenden**. Es gibt keine fünfte Möglichkeit. (FAKT-gestützt, Regel 1)
3. **Jede dieser Möglichkeiten erzeugt Singularitäten**, außer dem Randende. (Regel 2/3)
4. **Die eigentliche Entscheidung ist also die Pol-Platzierung**, nicht die Operation. (INTERPRETATION)
5. **Nebenwirkung, die selten erwähnt wird:** Pole beenden auch die *Loop-Selektion*. In den
   üblichen Werkzeugen stoppt Loop-Select an einem Pol; auch die Mirai-Bastel-Topologie-
   Experimente arbeiten bewusst konservativ nur mit Valenz-4-Vertices. Wer einen Pol setzt,
   entscheidet damit auch, **wo künftige Loop-Griffe enden** — und erinnert an Raitts Idee des
   Loops als Muskel-Griff (V1 §6.1). (BEOBACHTUNG + INTERPRETATION)

> **HYPOTHESE (zentral für spätere Experimente):**
> Ein erfahrener Modeller denkt bei lokaler Kontrolle nicht in „Loop Insert", sondern in
> „wo darf die Unruhe hin". Die Operation ist die Folge dieser Entscheidung, nicht ihr Anfang.

---

### 15.7 Kontrollmesh + SubD-Vorschau als Rückkopplungsschleife

#### Belegtes

- **FAKT (Raitt/Minter):** Der Artikel beschreibt die Arbeit ausdrücklich als Zusammenspiel von
  Kontrollobjekt und abgeleiteter Fläche mit Live-Aktualisierung: Eine Fläche am Kontrollobjekt
  skalieren aktualisiert die abgeleitete Fläche sofort. Kleine Topologieänderungen am Kontrollobjekt
  können eine sehr andere hochaufgelöste Fläche ergeben.
- **FAKT (Raitt/Minter):** Als Schlüssel zur Vorhersage des Glättungsergebnisses nennt der Artikel
  den Bezug zwischen den Flächenmitten des Kontrollobjekts und der abgeleiteten Fläche; für eine
  scharfe Kante soll eine Fläche so gelegt werden, dass ihre Mitte auf der gewünschten Kante liegt,
  mit kleinen Flächen drumherum.
  **Einordnung (INTERPRETATION):** Bei Catmull-Clark sind die Flächenmitten die neuen Punkte der
  ersten Unterteilungsstufe; die Grenzfläche geht im Allgemeinen nicht exakt durch sie hindurch.
  Das ist also eine **praktische Vorhersageregel**, keine exakte Eigenschaft — und genau deshalb
  interessant: Artists arbeiten mit Heuristiken, die gut genug vorhersagen.
- **FAKT (Raitt/Minter):** Das Kontrollobjekt soll nie so komplex werden, dass man es nicht mehr
  frei drehen kann.
- **FAKT (DeRose/Kass/Truong, Pixar, SIGGRAPH 1998):** Semi-sharp Creases erlauben einen
  steuerbaren Übergang von scharf zu glatt über einen Schärfewert, statt über zusätzliche
  Geometrie. Entwickelt im Zusammenhang mit Charakteranimation (Geri's Game).

#### Was nur in einer der beiden Ansichten sichtbar ist

| Nur im **Kontrollmesh** gut lesbar | Nur in der **SubD-Vorschau** sichtbar |
|---|---|
| Wo Pole sitzen | Ob ein Pol tatsächlich stört |
| Wie Streifen verlaufen, wo sie umkehren | Pinching, Wellen, Glanzbrüche |
| Ob eine Region zu dicht oder zu grob *aufgeteilt* ist | Ob eine Region zu flach oder zu rund *geformt* ist |
| Wo Loop-Griffe enden werden | Wie weit die Glättung eine Form „wegschmilzt" |
| Ob zwei Flusssysteme logisch anschließen | Ob der Anschluss als Form sichtbar wird |

**INTERPRETATION — Form- vs. Topologieproblem unterscheiden:** Die Tabelle legt eine praktische
Diagnose nahe, die in den Quellen implizit, aber nirgends explizit formuliert ist:
- Ist das Problem in der SubD sichtbar **und** im Kontrollmesh an einer *Position* erkennbar
  → **Formproblem** → verschieben.
- Ist es in der SubD sichtbar, aber im Kontrollmesh an einer *Pol- oder Streifenstelle*
  → **Topologieproblem** → umlenken oder Pol verschieben.
- Ist es nur im Kontrollmesh „unschön", aber in der SubD unsichtbar
  → möglicherweise **gar kein Problem**.

Der dritte Fall ist der interessanteste: Er ist der Punkt, an dem „saubere Topologie" als
ästhetisches Ideal und „funktionierende Topologie" auseinanderlaufen.

#### Wann mehr Dichte das Problem verschlimmert

- **FAKT (Raitt/Minter):** Geometrie am falschen Ort bricht trotzdem (Schulterbeispiel).
- **FAKT (Raitt/Minter):** Zu dichte Kontrollmeshes verlieren die Spontaneität (V1 §5.2).
- **INTERPRETATION:** Mehr Loops um eine Pinch-Stelle schieben den Pol oft nur, statt ihn zu
  entfernen; die Unregelmäßigkeit bleibt (Regel 2), sie wird nur kleiner oder wandert.
- **KONSENS:** Viele Stützkanten nah an einer Form machen die Fläche härter und nehmen dem
  Artist die weichen Übergänge, die er mit wenigen Punkten hätte formen können.

#### Wie wird zwischen den Ansichten gewechselt?

**OFFENE FRAGE.** Belegt ist nur das Prinzip der Live-Aktualisierung. *Wie oft*, *wann* und
*ausgelöst wodurch* erfahrene Modeller zwischen Käfig und Ergebnis wechseln (oder ob sie beides
überlagert sehen), ist in den gefundenen Quellen nicht dokumentiert. Das ist eine reine
Beobachtungsfrage — und damit ein guter Experiment-Kandidat.

---

### 15.8 Zusammenspiel — sechs Szenarien

Jedes Szenario zeigt mehrere Lösungen. Keine ist „die richtige".

#### Szenario 1 — Zusätzlicher Kontrollpunkt an der Wange, ohne Loop durch den ganzen Kopf

| Lösung | Ergebnis | SubD | Trade-off |
|---|---|---|---|
| Vorhandene Punkte verschieben / Kanten zusammenschieben | Keine neue Topologie | unverändert glatt | Reicht nur, wenn die Auflösung eigentlich genügt |
| Lokaler Ring um eine kleine Wangenregion | Dichte nur innen | Polpaare an den Ringecken | Ecken müssen in ruhige Zonen fallen |
| Teil-Loop mit Kehre in Richtung Nasolabialfalte | Verdichtung entlang eines Streifens | Polpaar an der Kehre | Kehre sitzt in einer ohnehin unruhigen Übergangszone — oft gewollt |
| Teil-Loop mit Dreieck-Ende | Minimaler Eingriff | Singularität auf gekrümmter Fläche | Auf der Wange meist sichtbar (KONSENS) |

**INTERPRETATION:** Die Nasolabialzone ist als Ablageort für die Unregelmäßigkeit attraktiv,
weil dort zwei Flusssysteme (Mundring, Wangenraster) ohnehin zusammentreffen.

#### Szenario 2 — Mehr Kontrolle am Auge, Umgebung deutlich gröber

- Ringe um die Augenöffnung sind **geschlossene Streifen** — Verdichtung *innerhalb* der Ringe
  breitet sich per Regel 1 nicht aus. (FAKT-gestützt)
- Die Schwierigkeit liegt beim **Übergang** vom äußersten Ring ins Gesichtsraster. Dort sitzen
  die Pole zwangsläufig. (Regel 2)
- Lösungen: Übergang über Kehren (Reihenzahl in Zweierschritten), über ein Dreieck/Ngon für die
  ungerade Differenz, oder über zusätzliche Ringe, die die Differenz über mehrere Stufen verteilen.
- **KONSENS:** Die Übergangspole werden bevorzugt in Brauen- und Wangenknochenregion gelegt, nicht
  an den Lidrand.

#### Szenario 3 — Ein Loop läuft in die falsche Richtung

Siehe 15.2. Bemerkenswert: Die billigste Lösung (Kante drehen) ist die unintuitivste, weil der
Artist eine *Kante* anfasst, um einen *Fluss* zu ändern. (INTERPRETATION)

#### Szenario 4 — Ein Loop soll vor einer anderen Region enden

Siehe 15.3. Die vier echten Optionen: Kehre, Nicht-Quad, Rand, Ring. Welche gewählt wird, hängt
vom Kontext der Endstelle ab: flach/statisch → Nicht-Quad vertretbar; deformierend → Kehre in
ruhige Zone; Merkmal in der Nähe → Ring; offene Öffnung → Rand.

#### Szenario 5 — Mehr Krümmung unter SubD, aber kein globaler Loop

| Lösung | Was es ändert | Trade-off |
|---|---|---|
| Punkte stärker positionieren (Übertreiben am Käfig) | Krümmung über Position | Käfig sieht „falsch" aus, Ergebnis stimmt |
| Kanten lokal zusammenschieben | Straffere Krümmung dort | Anderswo weicher |
| Semi-sharp Crease | Schärfe ohne Geometrie | Schärfe ≠ Krümmung; nicht jedes Zielformat überträgt Creases; Verhalten unter Deformation separat zu prüfen |
| Teil-Loop mit Kehre | Echte Zusatzkontrolle | Polpaar |

**BEOBACHTUNG:** Die ersten beiden Lösungen sind Raitts Linie (Form durch Position und Abstand),
die dritte ist Pixars Linie (Schärfe als Attribut), die vierte ist die Topologie-Linie.

#### Szenario 6 — Der Pol ist richtig, aber an der falschen Stelle

- Verschieben durch Umbau der umgebenden Streifen (15.1) oder durch Kantendrehung in kleinen Schritten.
- Zielort: flach, wenig Glanz, wenig Deformation, nahe an einem ohnehin vorhandenen Übergang. (KONSENS)
- **INTERPRETATION:** Alternativ die Umgebung des Pols lokal verfeinern, um die Störzone zu
  verkleinern (15.1) — bezahlt mit Dichte statt mit Pol-Bewegung.
- **Deformations-Kontext:** Ein Pol, der statisch unsichtbar ist, kann in Bewegung sichtbar werden,
  wenn er auf einer Biegelinie liegt. Statische SubD-Tauglichkeit und Deformationstauglichkeit sind
  **zwei getrennte Prüfungen**. (KONSENS; vgl. V1 §8)

---

### 15.9 Konkurrierende Strategien — die bewahrten Meinungsverschiedenheiten

| Position A | Position B | Worum es eigentlich geht |
|---|---|---|
| Reine Quads, Nicht-Quads vermeiden | Dreiecke/Ngons dort, wo sie nicht stören | Glätte gegen Dichte |
| Pole planen, nie nachträglich schieben | Iterativ modellieren, Pole wandern lassen | Planungsdisziplin gegen Entdeckungsprozess |
| Schärfe über Stützkanten | Schärfe über Creases | Portabilität/Deformationssicherheit gegen Leichtigkeit |
| Viele lokale Ringe (mehr Pole, weniger Dichte) | Wenige durchgehende Loops (weniger Pole, mehr Dichte) | Die Währungsfrage aus 15.0 |
| Topologie folgt Muskeln (Raitt) | Topologie folgt der gewünschten Punktbewegung (Tindall) | Einstieg von der Form vs. von der Bewegung (V1 §9.3) |

**Historischer Vorbehalt:** Die Mirai-Linie stammt aus einer Zeit, in der Kontrollmeshes klein
bleiben *mussten*. Ob die Vorliebe für minimale Käfige heute noch aus denselben Gründen gilt
(Überblick, Spontaneität) oder nur aus Gewohnheit, ist **OFFEN**. Das Überblicks-Argument
(V1 §5.2) ist jedenfalls nicht hardwareabhängig.

---

### 15.10 Offene Forschungsfragen dieses Deep Dives

| # | Frage |
|---|---|
| L-Q1 | Denkt ein Modeller bei lokaler Kontrolle zuerst an den **Ort der Unruhe** oder an die **Operation**? |
| L-Q2 | Gibt es eine praktisch brauchbare Faustregel für den Abstand eines Pols zu einer empfindlichen Zone, oder hängt es nur von der lokalen Rastergröße ab (15.1)? |
| L-Q3 | Wie oft und wodurch ausgelöst wechseln Modeller zwischen Käfig- und SubD-Ansicht (15.7)? |
| L-Q4 | Ist die Paritätsregel (15.3) Artists bewusst, oder erleben sie sie nur als „2→1 ist nervig"? |
| L-Q5 | Wie viele Einzeloperationen kostet heute eine bewusst platzierte Kehre im Vergleich zu einem durchgehenden Loop? |
| L-Q6 | Wird die Diagnose „Form- vs. Topologieproblem" (15.7) von Artists tatsächlich so getroffen? |
| L-Q7 | Wie verhalten sich Creases unter Deformation im Vergleich zu Stützkanten? (Grenze zu CHARACTER_SYSTEMS_RESEARCH) |
| L-Q8 | Welche Rolle spielt es, dass Pole auch Loop-Selektion begrenzen (15.6/5)? Stört das, oder ist es erwünscht? |

---

### 15.11 Artist-Playground-Kandidaten

Ergänzen, nicht ersetzen, die Experimente E1–E5 aus §13. Alle sind als **KANDIDAT** markiert;
Auswahl und Priorität entscheidet der Artist.

**KANDIDAT L1 — „Wo darf die Unruhe hin?"**
- *Frage:* L-Q1, L-Q5.
- *Aufbau:* Ein vorbereitetes, gleichmäßiges Quad-Stück mit markierter Zielregion. Aufgabe: dort mehr
  Kontrolle schaffen, ohne dass Loops die Region verlassen. Mit den vorhandenen Operationen lösen.
  Mitschreiben: wo die Pole landen, wie viele Schritte, und — vor dem ersten Klick — ein gesprochener
  Satz, *was* Manu vorhat.
- *Was es zeigt:* Ob der erste Gedanke ein Ort oder ein Werkzeug ist; wie teuer lokale Kontrolle
  heute ist.
- *Voraussetzung prüfen:* Welche Topologieoperationen im Playground verfügbar sind.

**KANDIDAT L2 — Vier Lösungen, eine Aufgabe (reines Anschauen)**
- *Frage:* Welche Strategien fühlen sich natürlich an, welche erzwungen?
- *Aufbau:* Dieselbe lokale Verdichtung viermal vorbereitet — Kehre, Dreieck-Ende, lokaler Ring,
  durchgehender Loop — jeweils als Käfig und als SubD. Manu beurteilt nur visuell und in wenigen
  Minuten: KEEP / ITERATE / REJECT / UNKNOWN pro Variante.
- *Kosten:* sehr gering, keine neue Interaktion — nur vorbereitete Meshes.
- *Was es zeigt:* Persönliche Toleranz gegenüber Polen, Dreiecken und Dichte. Trennt Geschmack
  von Technik, bevor irgendein Werkzeug gebaut wird.

**KANDIDAT L3 — Terminieren nach Ansage**
- *Frage:* L-Q4 und „kann ich einen Loop zuverlässig dort enden lassen, wo ich will?"
- *Aufbau:* Ein Loop, eine markierte Stelle, an der er enden soll. Einmal mit gerader, einmal mit
  ungerader Reihendifferenz.
- *Was es zeigt:* Ob die Paritätsregel im Arbeiten spürbar wird und wie Manu sie löst.

**KANDIDAT L4 — Käfig, Ergebnis, oder beides?**
- *Frage:* L-Q3, L-Q6.
- *Aufbau:* Eine kleine Formkorrektur mit SubD-Vorschau. Beobachtet wird nur, *wann* Manu welche
  Ansicht braucht und wie er Form- von Topologieproblemen unterscheidet. Überschneidet sich mit §13
  E3 — dort als Vergleich *mit/ohne* Vorschau, hier als Beobachtung *des Wechsels*. Sinnvoll
  kombinierbar.
- *Voraussetzung:* SubD-Vorschau im Playground. Falls nicht vorhanden, ist das Experiment
  zurückzustellen, nicht dafür eine Vorschau zu bauen, ohne dass der Artist das priorisiert.

**KANDIDAT L5 — Pol verschieben**
- *Frage:* Szenario 6; wie teuer und wie verständlich ist das Bewegen eines Pols?
- *Aufbau:* Ein Pol an einer sichtbar ungünstigen Stelle, Ziel markiert.
- *Was es zeigt:* Ob Manu den Pol als *Objekt* behandeln will (15.6) oder ob das Umbauen der
  Streifen sich natürlich anfühlt.

**Vorgeschlagene Reihenfolge nach Erkenntnis pro Aufwand:** L2 → L1 → L3 → L5 → L4.

---

### 15.12 Was dieser Deep Dive NICHT beantwortet

- Wie *Manu* lokale Kontrolle löst — nur, wie es dokumentiert gelöst wird.
- Eine belastbare Distanzregel für Pole.
- Wie sich Creases unter Deformation verhalten.
- Ob Mirai-Bastel die hier beschriebenen Strategien heute bereits mit vorhandenen Operationen
  ermöglicht. Das ist eine Prüffrage für die Topologie-Experimente (M1), keine Research-Frage.
  *Nachtrag 2026-09-21:* Für Connect geprüft — mit dem aktuellen Werkzeug nicht (nur ganze Loops);
  mit den Core-Primitiven mechanisch ja. Siehe `docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md`.

---

## Quellen

| Quelle | Art | Evidenzstärke |
|---|---|---|
| Bay Raitt, Greg Minter: *Digital Sculpture Techniques*, Nichimen Graphics, 2000 — `theminters.com/misc/articles/derived-surfaces/derived-surfaces.pdf` | Primärartikel der Mirai-Entwicklung | hoch |
| Wikipedia: *Edge loop*, *Bay Raitt*, *Mirai (software)*, *Box modeling* | Enzyklopädisch, mit Belegen | mittel |
| Brian Tindall: *The Art of Moving Points* (2013) — `hippydrome.com`, Verlagsbeschreibung | Fachbuch, Inhalt nicht im Detail geprüft | mittel |
| Wings 3D Handbuch und Dokumentation — `wings3d.com`, Wikibooks-Handbuch | Software-Dokumentation | hoch (für Verhalten) |
| Peters/Reif zur Stetigkeit an Extraordinary Vertices, zitiert in aktueller Fachliteratur (arXiv) | Fachpublikation | hoch |
| *Subdivision Shading … with Semi-Sharp Creases*, MDPI Computers 12(4), 2023 | Fachpublikation | hoch |
| Jakob, Tarini, Panozzo, Sorkine-Hornung: *Instant Field-Aligned Meshes*, SIGGRAPH Asia 2015 — `igl.ethz.ch/projects/instant-meshes/` | Fachpublikation + Referenzimplementierung | hoch |
| Polycount-Diskussionen zu Kopf-, Ellenbogen- und Knietopologie | Community | niedrig (als KONSENS geführt) |
| Diverse Tutorial-/Blogquellen zu Blockout und Formhierarchie | Community, teils maschinell erzeugt | niedrig |
| Daniels, Silva, Shepherd, Cohen: *Quadrilateral Mesh Simplification*, SIGGRAPH Asia 2008 (Poly-Chords schließen sich auf geschlossenen Quad-Meshes) | Fachpublikation | hoch |
| Geuzaine/Remacle: *An Introduction to Mesh Generation* (Index ±¼ für Valenz 3/5, diskreter Poincaré-Hopf) | Lehrbuch | hoch |
| Reberol et al.: *Quasi-structured quadrilateral meshing in Gmsh* (Dipole für Größenänderungen) | Fachpublikation | hoch |
| Knodt: *Single Edge Collapse Quad-Dominant Mesh Reduction*, 2024 (Chords oft nicht lokal; Teil-Chord-Reduktion bei EA mit Dreiecken) | Fachpublikation | hoch |
| *Q-zip: Singularity Editing Primitive for Quad Meshes* (lokale Singularitäts-Operationen) | Fachpublikation | hoch |
| DeRose, Kass, Truong: *Subdivision Surfaces in Character Animation*, SIGGRAPH 1998 (Semi-sharp Creases) | Fachpublikation | hoch |
| topologyguides.com: *Optimal Edge Loop Reduction Flows*, *Moving and Manipulating Edge Poles* | Community-Anleitung | niedrig–mittel |
| CG Cookie: *The Art of Good Topology*; Forum *Optimal Edge Loop Reduction* | Community | niedrig |
| E-/N-Pol-Terminologie (diverse Community-Texte) | Community | niedrig |

---

## Verwandte Dokumente

- `AGENTS.md` — Repository-Regeln
- `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` — M1–M5, Artist-Attention-Filter
- `ROADMAP.md` — Modeling Track, WP-03, ARCH-02
- `CHARACTER_SYSTEMS_RESEARCH.md` — Character-Systems-Research (Rigging, Deformation, Facial-Systeme)
- `docs/design/artist_playground/UX_RESEARCH.md` und Research Map V1 — Interaction Grammar
- `experiments/rigging-skinning-morphing/` — technische Realität der Topologie-Mutation
- `experiments/topology/` — Loop/Ring, Connect Edges

---

**Nächster sinnvoller Schritt ist nicht, dieses Dokument zu erweitern.**
Er ist, eines der Experimente aus §13 zu spielen und zu beobachten, was passiert.
