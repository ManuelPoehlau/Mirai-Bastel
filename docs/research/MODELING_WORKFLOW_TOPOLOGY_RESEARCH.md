# Modeling Workflow & Topology Grammar — Research V1.2

**Status:** Discovery — Recherche, keine Entscheidungen
**Datum:** 2026-09-21 (V1) · 2026-09-21 (V1.1: §15 Local Topology Control — Deep Dive) · 2026-09-26 (V1.2: §16 Topologie-Absicht und zusammengesetzte Operationen)
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

## 16. Topologie-Absicht und zusammengesetzte Operationen — Deep Dive 2

**Ergänzt:** 2026-09-26 (V1.2) · **Modus (M5):** Discovery · **Verhältnis zu V1/V1.1:** baut auf
§6.2 (Fluss-Tätigkeiten), §10 (Mechanik / Operation / Absicht) und §15.0 (drei harte Regeln) auf und
wiederholt sie nicht. Neu ist der Blick auf **bestehende Werkzeuge und Forschungssysteme**, die
Absicht und Mechanik bereits trennen — und auf die Frage, wo sie das *nicht* tun.

> **Leitfrage dieses Abschnitts:**
> Wie könnte klassisches Box-Modeling artist-freundlicher werden, wenn der Artist Topologie-Absicht
> direkt ausdrücken könnte und die Software die wiederkehrende, mechanische Topologiearbeit übernähme?

Wie der Rest des Dokuments: **keine** Architektur, **keine** Tastenbelegung, **keine** Produktentscheidung,
**keine** Implementierungsaufgaben. Was hier „denkbar" heißt, ist genau das — denkbar, nicht empfohlen.

---

### 16.0 History Awareness (M1) und Context Check (M2) für diesen Abschnitt

**Existenzprüfung** (Repository gelesen, Stand `main` @ `d4cf93f`):

| Existiert | Wo | Bedeutung hier |
|---|---|---|
| Fluss-Verben (starten, fortsetzen, umlenken, terminieren, verdichten, umverteilen, herumführen) | §6.2 | Ausgangsvokabular; wird in 16.3 geprüft, nicht neu erfunden. |
| Drei Ebenen Mechanik / Operation / Absicht, Hypothese A vs. B | §10.2–10.3 | Wird in 16.8 gegen die neue Evidenz geprüft. |
| Mathematik der lokalen Kontrolle (Streifen enden nicht, Polbilanz, Dipole, Paritätsregel) | §15.0, §15.3 | Liefert die Begründung, warum manche Absichten sich auf wenige Grundformen reduzieren (16.3). |
| Experiment-Kandidaten E1–E5, L1–L5 | §13, §15.11 | **Keiner davon ist bisher gespielt** (kein Verdikt, kein Verweis in anderen Dokumenten gefunden). 16.9 ergänzt deshalb möglichst *Varianten* bestehender Kandidaten statt neuer Experimente. |
| Connect/Split/Knife-Semantik, kontextuelles C | `docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md`, AD-017 | Mirai hat damit bereits ein kontextsensitives Operationsmuster (Auswahlkontext → Operation). Wird zitiert, nicht neu verhandelt. |
| Interaction-Grammatik (Activation, Termination, Residue, **Composition**) | `docs/design/artist_playground/RESEARCH_MAP.md`, `UX_RESEARCH.md` | Alle *Interaktions*fragen aus 16.5/16.7 gehören dorthin. Hier nur als Fragen markiert. |
| Temporäre Artikulation (EX-A) | `playground/experiments/articulation/` | Relevant für E4 („Biegen und Schauen"): Die Infrastruktur für schnelles Biegen existiert inzwischen im Playground. |
| Topologie-Identität / Provenienz | `ROADMAP.md` ARCH-02 | 16.7 H6 berührt diese Frage und wird dorthin verwiesen, nicht hier beantwortet. |
| Symmetrie-Prinzip „eine Absicht → bekannter Operationskontext" | `README.md`, `docs/research/symmetry/` | Verwandter Gedanke; 16.7 H6. |

**Verworfenes:** Kein Hinweis, dass Absichts- oder Composite-Operationen je geprüft und abgelehnt wurden.
Abgelehnt ist nur die Streifen-Semantik von Connect als alleinige Semantik (Connect Lab, D1-a REJECT) —
das ist eine Mechanik-, keine Absichtsentscheidung.

**Ehrlicher Hinweis zum Dokument selbst:** Der Schluss dieses Dokuments empfiehlt ausdrücklich, *nicht*
weiter zu erweitern, sondern zu spielen. Dieser Abschnitt entsteht trotzdem, weil der Artist die Recherche
ausdrücklich angefragt hat (Priorität ist Artist-Entscheidung). Konsequenz: 16.9 hängt neue Fragen
möglichst an die bereits vorbereiteten Experimente an, statt die Liste zu verlängern.

**Context Check — Annahmen (nur korrigieren, wenn falsch):**

1. Topologie-Operationen im Playground (Stand `d4cf93f`): Split an Parameter t, Collapse, Connect
   pro Face (Wings-artig), Vertex Connect, Knife-Session, Loop Insert, Loop Slide (nur geschlossene
   Loops in regulären Quads), Loop-/Ring-Auswahl (konservativ: Loop nur über Valenz-4-Vertices,
   Ring nur über Quads), Multi-Face-Extrude.
2. **Nicht vorhanden:** Dissolve / Merge Faces (im Code ausdrücklich als fehlendes Primitive vermerkt),
   Kante drehen („spin edge"), Relax / Set-Flow-artige Positionshilfen, SubD-Vorschau, Creases.
3. Diese Liste ist eine **Feststellung**, keine Wunschliste. Ob etwas davon gebraucht wird, ist offen.

---

### 16.1 Methode dieses Abschnitts

Für jedes untersuchte Werkzeug wurden zwei Fragen gestellt, nicht „welches Feature gibt es":

1. **Was muss der Artist beim Benutzen noch denken?**
2. **Welche mechanische Arbeit nimmt die Software ihm ab?**

Die Differenz zwischen beidem ist die *Absicht*, die das Werkzeug bedient.

**Quellenlage (Methodenkritik, ergänzt §3):**
- Hersteller-Handbücher (Autodesk, Blender, SideFX, Maxon) → **FAKT** für *Verhalten*, nicht für Wirkung.
- Fachpublikationen (SIGGRAPH, SGP, Eurographics) → **FAKT** für das, was das jeweilige System tut;
  die Übertragung auf Box-Modeling ist immer **INTERPRETATION**, weil fast alle Retopologie-Systeme sind.
- Händler-/Tipp-Blogs → höchstens **KONSENS**. Beispiel für die Unzuverlässigkeit: Zwei Tipp-Artikel
  desselben Händlers zu ZRemesher geben für die Dichte-Bemalung **entgegengesetzte** Farbkonventionen an
  (einmal „weiß = dichter", einmal „dunkler = dichter"). Solche Details werden hier nicht verwendet.
- Community-Foren → **KONSENS** oder **BEOBACHTUNG**, wertvoll vor allem dort, wo Artists ein Problem
  in eigenen Worten beschreiben.

Nicht geprüft: Modo, Cinema 4D, Silo im Detail (Silo und Wings sind über AD-017 und
`CONNECT_NONQUAD_DISCOVERY.md` bereits abgedeckt). Die Stichprobe ist also **nicht vollständig**.

---

### 16.2 A — Bestehende Ansätze, geordnet nach der Absicht, die sie bedienen

Die Tabelle ist bewusst **nicht nach Programm** geordnet. Sie gruppiert Mechanismen nach der
Absicht dahinter.

#### 16.2.1 „Die Punkte sollen der Form folgen" — Positions-Absicht

| Mechanismus | Was der Artist noch denkt | Was die Software abnimmt | Evidenz |
|---|---|---|---|
| **Maya Edit Edge Flow** — verschiebt gewählte Kanten so, dass sie der Krümmung der Umgebung folgen; Stärke 0 = flach mittig, 1 = volle Krümmungsanpassung; Wert lässt sich danach über den Node nachstellen | *Welcher* Loop; wie stark | Die Neupositionierung jedes Vertex | FAKT (Autodesk-Handbuch). Handbuch warnt: mehr als zwei nicht benachbarte Loops → unvorhersehbare Ergebnisse. |
| **3ds Max Set Flow** (+ „Auto Loop": wählt zu jeder gewählten Kante den Loop mit) | Welche Kanten | Loop-Auswahl *und* Positionierung | FAKT (Autodesk-Handbuch) |
| **3ds Max Flow Connect** — Loop durch einen Ring einfügen **und** sofort an die Form anpassen | Welcher Ring | Einfügen + Nachpositionieren als *ein* Schritt | FAKT. Das ist ein echtes Composite: „Loop Insert → Set Flow". |
| **Relax-Pinsel** (Maya Quad Draw, RetopoFlow) — gleichmäßige Verteilung; Quad Draw sperrt automatisch Rand- oder Innenvertices, je nachdem wo der Pinsel ansetzt | Wo | Gleichmäßiges Verteilen, Randschutz | FAKT (Handbücher) |

**BEOBACHTUNG:** Diese Gruppe ist in den etablierten DCCs **breit und seit Langem** vorhanden.
Keines dieser Werkzeuge ändert die Konnektivität.

**Begriffsfund (FAKT + INTERPRETATION):** „Edge Flow" bedeutet in Mayas Werkzeugname etwas **Geometrisches**
(Krümmungsstetigkeit der Positionen), in der Artist-Sprache (§6) etwas **Topologisches** (Richtung der Loops).
Derselbe Begriff bezeichnet zwei verschiedene Dinge. Das dürfte Gespräche über „Flow" still verunklaren —
auch in diesem Projekt.

#### 16.2.2 „Dieser Loop soll hier enden / abbiegen" — Konnektivitäts-Idiome als Einzelbefehl

| Mechanismus | Was der Artist noch denkt | Was die Software abnimmt | Evidenz |
|---|---|---|---|
| **3ds Max Build End** — baut aus zwei parallelen Loops, die an derselben Kante enden, einen Quad-Abschluss | Welche zwei Loops enden gemeinsam, und wo | Den Umbau der Endstelle in Quads | FAKT. **Vorbedingung laut Handbuch:** funktioniert nur, wenn *genau zwei* parallele Loops auf derselben Seite derselben Innenkante enden. |
| **3ds Max Build Corner** — baut eine Quad-Ecke, damit ein Loop abbiegt | Wo der Loop abbiegen soll | Den Umbau an der Abbiegestelle | FAKT (Handbuch). Community-Bericht: funktioniert im Edit-Poly-Modifier nicht (mehrere Versionen) — BEOBACHTUNG. |
| **3ds Max Distance Connect** — verbindet zwei Endpunkte über die dazwischenliegende Topologie hinweg | Start und Ende | Den Pfad dazwischen | FAKT |
| **MESHmachine (Blender-Addon)** — u. a. „Fluss einer Fase durch Umdrehen der Ecken umlenken", dreieckige Fasenecken in Quad-Ecken umwandeln | Welche Ecke | Den Umbau | FAKT (Herstellerbeschreibung), Hard-Surface-Kontext |

**INTERPRETATION — der wichtigste Einzelfund dieses Abschnitts:** *Build End* ist genau die **Kehre**
aus §15.3 — zwei parallele Reihen, die in Wahrheit ein Streifen sind. Ein Hersteller hat also
„Loop terminieren" als eigenen Befehl gebaut, und die Vorbedingung („genau zwei parallele Loops") ist
nichts anderes als Regel 1 aus §15.0: Ein Quad-Streifen kann nur zusammen mit einem Partner enden.
Die Werkzeugwelt hat die Mathematik unabhängig wiederentdeckt — als Bedienungseinschränkung.

**BEOBACHTUNG zur Auffindbarkeit:** Laut Handbuch erscheinen Build End und Build Corner nur, wenn die
Werkzeugleiste maximiert oder das Panel abgelöst ist. Die einzigen Absichts-Befehle für Konnektivität
im untersuchten Mainstream sind also zugleich die am schwersten auffindbaren.

#### 16.2.3 „Nur hier, nicht überall" — Reichweite begrenzen

| Mechanismus | Was der Artist noch denkt | Was die Software abnimmt | Evidenz |
|---|---|---|---|
| **ZBrush ZModeler: Aktion + Ziel** (Target) — z. B. Edge Delete für einzelne Kanten, Teil-Loops oder ganze Loops; „EdgeLoop Complete" vs. „EdgeLoop Partial" | Komponente, Aktion, Reichweite | Das Finden der betroffenen Elemente | FAKT (Maxon-Dokumentation) |
| **Maskieren/Verstecken als Reichweitenbegrenzung** | Welche Region *nicht* betroffen sein darf | — (Umweg) | BEOBACHTUNG (ZBrushCentral) |

**BEOBACHTUNG, in Artist-Worten:** Ein Nutzer fragt im ZBrush-Forum wörtlich nach der Absicht aus §15.4:
Wie verhindert man, dass „Insert EdgeLoop" durch die ganze Geometrie läuft, *um den Fluss umzulenken*?
Seine eigene Lösung: vorher Polygone löschen, wo der Loop enden soll. Die Antwort: Maskieren/Verstecken,
keine Garantie, dass komplizierte Pfade als Loop erkannt werden, die Eck-Polygone seien das Problem;
Alternativen seien Inset, mehrere Teil-Loops plus Nachnähen, oder ein Schnittpinsel.
→ Die Absicht ist klar formuliert. Das Werkzeug kennt sie nicht. Der Artist baut sie aus Umwegen.

**INTERPRETATION:** ZModelers *Aktion × Ziel* ist das im Mainstream **nächstgelegene Vorbild einer
Grammatik** — Verb (Aktion) und Reichweite (Ziel) sind getrennte, frei kombinierbare Wahlen. Es ist aber
eine Grammatik über **Auswahlreichweite**, nicht über **Flussabsicht**: „EdgeLoop Partial" sagt, *wie viel*
betroffen ist, nicht *wie der Fluss danach verlaufen soll*.

#### 16.2.4 „Der Fluss soll hier entlang" — Striche und Skizzen

| Mechanismus | Artist gibt vor | Software bestimmt | Evidenz |
|---|---|---|---|
| **Maya Quad Draw** — Loop, Kante oder Rand verlängern; automatisches Verschweißen | Richtung durch Ziehen | Neue Faces, Verschweißen | FAKT (Handbuch) |
| **RetopoFlow** — PolyStrips (wichtige Loops als Strich skizzieren, verlängert/überbrückt), Strokes (zwei ungefähr parallele Striche → gleichmäßiges Quad-Raster dazwischen), Contours (Ring um zylindrische Form) | Verlauf, Segmentzahl | Vertexpositionen, Raster, Einrasten auf Oberfläche | FAKT (Herstellerdoku). Selbstbeschreibung: gute Topologie-Praktiken sollen der Normalfall sein. |
| **Takayama et al., SIGGRAPH 2013** — Artist skizziert Patch-Ränder; Flussrichtung folgt den Rändern; Topologie wird über die **Unterteilungszahl je Rand** gesteuert; Singularitäten werden bei Bedarf automatisch eingefügt, **Ort bleibt steuerbar** | WAS (Patch), WO (Ränder), RICHTUNG, ANZAHL | WIE (Innenaufteilung, Polsetzung) | FAKT (Paper). Evaluierung mit professionellen Artists. |
| **Takayama et al., 2014 (Pattern-based N-sided)** — N-seitiger Patch (2 ≤ N ≤ 6) mit vorgegebenen Randzahlen wird garantiert quadrangulierbar gemacht, sofern die Eingabe gültig ist; Standard: minimale Zahl irregulärer Vertices; **andere zulässige Lösungen wählbar** | Randzahlen | Muster, Pole | FAKT |
| **Marcias et al., SIGGRAPH 2015 (Data-driven)** — Quadrangulierungsmuster werden **aus von Artists gebauten Modellen gelernt**; Striche im Patch schlagen eine Flussrichtung vor, das System wählt ein passendes Muster | Patch + gewünschter Fluss | Muster aus einer Datenbank echter Artist-Lösungen | FAKT (Paper), informelle Studie mit drei Artists |
| **Campen & Kobbelt, SIGGRAPH Asia 2014 (Dual Strip Weaving)** — atomare Operation ist ein **ganzer geschlossener Streifen**; beim **Hovern** wird sofort der beste Streifen an der Mausposition gezeigt, ein Klick fixiert ihn; fixierte Streifen schränken die nächsten Vorschläge ein; Farbhinweise zeigen, wo Änderungen die Qualität verbessern würden | Welcher der vorgeschlagenen Streifen | Streifenverlauf, Konsistenz, Vorschläge | FAKT (Paper) |

**FAKT, sinngemäß aus Takayama 2013:** Artists wollen bei Charakter-Meshes ausdrückliche Kontrolle über
Fluss **und** Singularitäten; automatische Verfahren erreichten die Qualität manueller Lösungen (Stand
2013) noch nicht. Das ist eine Forschungsgruppe, die genau die Mitte sucht, nach der Mirai fragt.

**Die Grenze dieser ganzen Gruppe (INTERPRETATION, wichtig):** Alle Einträge sind **Retopologie** —
sie setzen eine *fertige Referenzoberfläche* voraus, auf die neue Topologie einrastet. Beim Box-Modeling
existiert diese Oberfläche nicht; sie entsteht gerade erst (§5.1, §5.8). Die ausgereiftesten
Absichts-Werkzeuge der Branche leben also genau in dem Workflow, den die Mirai-Linie *nicht* als
Grundlinie hat.

#### 16.2.5 „So ungefähr, rechne du" — Führung für Automatik

| Mechanismus | Artist gibt vor | Software bestimmt | Evidenz |
|---|---|---|---|
| **ZRemesher** mit Führungskurven, Kurvenstärke, Dichte-Bemalung, Zielpolygonzahl | Hauptflüsse, Dichteverteilung, Budget | Die gesamte Topologie | FAKT für die Existenz der Parameter (Maxon-Dokumentation). Details der Bedienung nur KONSENS (Händlerblogs, s. 16.1). |
| **Instant Meshes** (bereits §4.5) | Orientierungsstriche | Feld und Mesh | FAKT |

**BEOBACHTUNG:** Hier gibt der Artist WAS, WO, RICHTUNG und DICHTE vor; das WIE ist vollständig
automatisch — aber **global**: Das ganze Mesh wird neu erzeugt, nicht eine Stelle geändert. Mehrere
Tipp-Quellen empfehlen, bei unbefriedigendem Ergebnis einfach eine **alternative Lösung** rechnen zu
lassen (KONSENS) — das Vertrauen beruht also auf Auswahl, nicht auf Vorhersage.

#### 16.2.6 „Die Absicht soll nach dem Schritt weiterleben"

| Mechanismus | Worum es geht | Evidenz |
|---|---|---|
| **Blender „Adjust Last Operation"** — Parameter einer Operation *nach* dem Ausführen nachstellen | Die letzte Absicht bleibt kurz editierbar | FAKT (Blender-Handbuch) |
| **Maya Node-History** (z. B. Edit-Edge-Flow-Wert nachträglich am Node) | Parameter bleibt am Ergebnis hängen | FAKT (Autodesk-Handbuch) |
| **MESHmachine Fuse/Unfuse, Unchamfer, Change Width** — eine *vorhandene* Fase wird **aus der Geometrie wiedererkannt** und lässt sich zurück in eine harte Kante, in eine Rundung oder auf eine andere Breite bringen; der Autor nennt das „re-constructive" | Absicht wird nicht gespeichert, sondern **rekonstruiert** | FAKT (Herstellerdoku). Begründung dort: Fasen seien ohne solche Werkzeuge eine Sackgasse, weil man für Änderungen wieder auf Kanten-/Vertex-Ebene muss. |

**INTERPRETATION:** Es gibt zwei grundverschiedene Wege, eine Absicht über den Schritt hinaus zu
erhalten: **Erinnern** (Parameter/History am Ergebnis) oder **Wiedererkennen** (Muster in der Geometrie
lesen). MESHmachine ist der einzige gefundene Fall des zweiten Wegs im Modeling-Alltag.

#### 16.2.7 Rezepte — Artist-Wissen als wiederverwendbare Operation

| Mechanismus | Worum es geht | Evidenz |
|---|---|---|
| **Houdini Digital Assets** — eigene Node-Netzwerke werden zu wiederverwendbaren Nodes; ausgewählte innere Parameter werden nach außen „promoted" | Rezept = feste Kette + wenige nach außen gegebene Regler | FAKT (SideFX-Doku) |
| **Autocomplete 3D Sculpting** (Peng, Xing, Wei, SIGGRAPH 2018) — zeichnet den Arbeitsablauf still auf, sagt voraus, was der Nutzer als Nächstes tun könnte; Vorschläge annehmen, teilweise annehmen oder ignorieren; vergangene Abläufe auf andere Regionen klonen | Rezepte **aus dem eigenen Verhalten** statt vorab definiert | FAKT (Paper) |
| **Artist-Skripte/Makros** (Maya, Blender-Operatoren, Modo) | aufgezeichnete Befehlsketten | KONSENS, in dieser Session nicht im Detail geprüft |

**INTERPRETATION:** Bei Houdini ist die entscheidende Designfrage eines Rezepts nicht die Kette,
sondern **welche Parameter nach außen gegeben werden**. Die Kette enthält das Wissen des Artists;
die freigegebenen Regler enthalten seine verbleibende Kontrolle.

#### 16.2.8 Forschung: Singularitäten direkt bearbeiten

| System | Kern | Evidenz |
|---|---|---|
| **Peng, Zhang, Kobayashi, Wonka, SIGGRAPH Asia 2011** — Operationen, die Ort, Ausrichtung, Typ und Anzahl irregulärer Vertices ausdrücklich steuern; drei Grundoperationen **bewegen oder drehen ein Polpaar**; ergänzt um Teilen, Verschmelzen, Aufheben und Ausrichten von Polen; umgesetzt **durch Quad-Collapse, Edge-Flip und Edge-Split** | Die Absicht „Pol versetzen" als *eine* Operation, gebaut aus Primitiven | FAKT (Paper), inkl. Analyse, welche Edits möglich und welche unmöglich sind |
| **Peng & Wonka, SGP 2013** — dasselbe für quad-dominante Meshes: irreguläre Vertices *und* irreguläre Faces; Trade-off laut Paper: Pole halten scharfe Merkmale, erzeugen aber stärkere Richtungsabweichungen in glatten Bereichen; Nicht-Quads geben glattere Linien, halten aber keine scharfen Merkmale | Die „Währungsfrage" aus §15.0 als Designraum | FAKT (Paper) |
| **Q-zip** (bereits §15.1) | lokale Singularitäts-Operation | FAKT |

**BEOBACHTUNG (mit Stichproben-Vorbehalt):** „Pol versetzen" existiert in der Forschung seit mindestens
2011 als eigene Operation mit sauberer Zerlegung in Primitive. In den untersuchten DCC-Handbüchern wurde
keine Entsprechung gefunden.

#### 16.2.9 Querschnittsbefund

> **BEOBACHTUNG:** Die etablierten DCCs automatisieren **Position** breit (Set Flow, Edit Edge Flow,
> Relax) und **Konnektivität** nur punktuell (Build End / Build Corner mit engen Vorbedingungen,
> Hard-Surface-Addons). Absichts-Werkzeuge für Konnektivität existieren fast nur in der **Forschung**
> und in der **Retopologie**.

Das ist eine Beobachtung über eine unvollständige Stichprobe, keine Marktanalyse.

---

### 16.3 B — Wiederkehrende Absichten: das kleinste brauchbare Vokabular

#### 16.3.1 Unabhängige Belege je Absicht

| Absicht | Artist-Sprache (§6.2, §15) | Werkzeug-Evidenz (16.2) | Forschung | Hard Surface |
|---|---|---|---|---|
| **Fortsetzen** | Fluss fortsetzen | Quad Draw „Extend Loop", RetopoFlow Strokes | Dual Strip Weaving | — |
| **Beenden** | Loop terminieren | Build End; ZBrush-Forum („nicht durchs ganze Mesh") | Pattern-based (Randzahlen) | Polycount: Stützkanten auf flachen Flächen früh enden lassen |
| **Abbiegen / Umlenken** | Fluss umlenken | Build Corner; MESHmachine „Ecken drehen" | Peng 2011 (Umorientieren) | MESHmachine |
| **Pol versetzen** | Pol verschieben (§15.1) | — (nicht gefunden) | Peng 2011, Q-zip | — |
| **Verdichten (lokal)** | mehr Kontrolle hier | ZModeler Teil-Loops; ZRemesher Dichte-Bemalung | Takayama (Randunterteilung) | — |
| **Ausdünnen / Übergang** | Dichte senken | — | Pattern-based; Chord-Reduktion (§15.5) | früh enden lassen |
| **Verbinden** | Regionen verbinden | Distance Connect, PolyStrips-Brücke, Grid Fill | Pattern-based N-sided | Stützkante über Eckvertices verbinden (Polycount) |
| **Form folgen** | Krümmung erhalten | Set Flow, Edit Edge Flow, Flow Connect | — | — |
| **Verteilen** | Verteilung ist hässlich | Relax (Quad Draw, RetopoFlow) | — | — |
| **Begrenzen** | nur hier | ZModeler-Ziele, Maskieren | — | — |
| **Bewahren** | Silhouette/Kontur halten (§5.3) | Quad Draw Auto-Lock (Rand vs. Innen) | — | Stützkantenbreite steuert Rundung (Polycount) |

**BEOBACHTUNG:** Die meisten Absichten aus §6.2 tauchen **unabhängig** in mindestens zwei der vier
Spalten auf. Die Verben aus der Aufgabenstellung, die *nicht* eigenständig belegt wurden:
**Trennen** (taucht nur als Regionsgrenze auf, z. B. Polygroups) und **Starten** (fällt in der Praxis
mit Fortsetzen oder mit einer neuen Form wie Extrude zusammen).

#### 16.3.2 Die Reduktion — drei Achsen statt einer Liste

**INTERPRETATION:** Das Vokabular zerfällt in drei Arten, die sich in der Evidenz unterschiedlich verhalten:

| Art | Absichten | Ändert … | Typisches Ergebnis |
|---|---|---|---|
| **Konnektivität** | fortsetzen, beenden, abbiegen, Pol versetzen, verdichten, ausdünnen, verbinden | die Topologie | **diskret** — es gibt wenige, abzählbare Lösungen |
| **Position** | Form folgen, verteilen | nur Koordinaten | **kontinuierlich** — stufenlos nachstellbar |
| **Reichweite / Schutz** | begrenzen, bewahren | nichts selbst — beschränkt die anderen | Randbedingung |

#### 16.3.3 Noch kleiner — der Streifen-Kern (HYPOTHESE, mathematisch gestützt)

Aus §15.0 folgt, dass sich die Konnektivitäts-Absichten auf **drei Grundformen am Streifen**
zurückführen lassen könnten:

| Grundform | Bedeutung | Zusammengesetzte Absichten |
|---|---|---|
| **Streifen legen** | einen Quad-Streifen beginnen oder weiterführen | fortsetzen, verbinden |
| **Streifen enden lassen** | Kehre, Nicht-Quad, Rand oder Ring (§15.3 — es gibt keine fünfte Möglichkeit) | beenden, ausdünnen |
| **Streifen abbiegen** | Richtungswechsel an einem Pol | umlenken |

Und dann:
- **lokal verdichten** = Streifen legen + an beiden Enden enden lassen (oder als Ring schließen);
- **Pol versetzen** = Abbiegen an einer Stelle aufheben und an einer anderen einführen (Dipol-Bewegung);
- **beenden** = in reinen Quads **mit einem Partnerstreifen verschmelzen** (Kehre) — genau das, was
  3ds Max' Build End als Vorbedingung verlangt.

**Stützende Evidenz:** Dual Strip Weaving macht den **Streifen** zur atomaren Operation und begründet das
mit geringerem Planungsaufwand für den Nutzer (FAKT). Raitts Loop ist ein **Muskel-Griff** (§6.1) —
ebenfalls ein Streifen, kein einzelnes Element.

**Gegenargument (ernst gemeint):** Die Reduktion ist mathematisch sauber, sagt aber nichts darüber, ob
ein Artist so *denkt*. Möglich ist, dass „Loop beenden" für den Artist eine unteilbare Einheit ist und
„mit Partner verschmelzen" sich fremd anfühlt. Das ist eine Artist-Frage (16.9, T6).

---

### 16.4 C — Zusammengesetzte Operationsmuster

| Absicht | Heutige typische Kette (branchenweit) | Was davon ist Artist-Entscheidung? | Was ist Mechanik? | Existiert irgendwo als *ein* Befehl? |
|---|---|---|---|---|
| Lokal verdichten mit Kehre | Teilschnitt → Eckverbindung an der Kehre → Fünfecke auflösen → Slide → Relax | Start, Ende, Seite der Kehre, Anzahl Reihen | Auflösen der Enden, Nachpositionieren | Teilweise: Build End (nur die Endstelle) |
| Loop abbiegen | Schnitt → Kanten auflösen → Kante drehen, oft mehrfach | Ort der Biegung, Richtung | Umbau um die Biegung | Build Corner |
| Pol versetzen | Kanten schrittweise drehen oder Collapse + Split | Zielort | alle Zwischenschritte | Forschung: Peng 2011 |
| Dichteübergang (3→1, 4→2, 5→3) | Muster von Hand schneiden | Wo der Übergang liegt; bei ungerader Differenz: Dreieck, Ngon oder Zusatzloop | Das Muster selbst | Forschung: Pattern-based N-sided (inkl. Auswahl von Alternativen) |
| Loop einfügen + Form halten | Loop Insert → Set Flow | Welcher Ring | Nachpositionieren | Flow Connect |
| Region neu füllen | Löschen → Füllen → Relax | Region, Randzahlen | Innenaufteilung | Grid Fill (rechteckig), Patches (RetopoFlow) |
| Stützkante (Hard Surface) | Bevel → Eckvertices verbinden → auf flachen Flächen früh enden | Breite (= Rundung), wo enden | Eckverbindungen | Teilweise: MESHmachine |
| Öffnung anlegen (§10.1) | Faces löschen → Rand bereinigen → Ringe anlegen | Lage und Größe | Rand und Ringe | nicht gefunden |

**HYPOTHESE — Kriterium für „mechanisch genug":** Eine Kette eignet sich als *eine* Artist-Aktion, wenn
(1) die Artist-Entscheidungen **wenige und benennbare Größen** sind (Start, Ende, Anzahl, Seite),
(2) der Rest bis auf **wenige abzählbare Alternativen** festliegt, und
(3) das Ergebnis **lokal begrenzt** bleibt.
Build End erfüllt (1)–(3); ZRemesher erfüllt (1), aber nicht (3); „Pol an eine gute Stelle setzen"
erfüllt (1) nicht, weil *gut* eine künstlerische und deformationsabhängige Frage ist.

**Ausdrücklich nicht gefolgert:** dass irgendeine dieser Ketten automatisiert werden sollte.

---

### 16.5 D — Chancen: wo DCCs den Artist weiterhin Mechanik erledigen lassen

1. **Konnektivitäts-Absichten sind Handarbeit.** (16.2.9) Beenden, Abbiegen und Pol versetzen bestehen
   im Alltag aus Ketten von Einzeloperationen. **BEOBACHTUNG.**
2. **Absichts-Werkzeuge gibt es fast nur für Retopologie.** (16.2.4) Für das *gleichzeitige* Formen und
   Topologisieren des Box-Modelings wurde kaum etwas Vergleichbares gefunden. Das ist genau das Gebiet
   der Mirai-Linie. **INTERPRETATION.**
3. **Werkzeuge sind standardmäßig global.** Loop-Werkzeuge laufen ums ganze Modell; „nur hier" braucht
   Umwege (Maskieren, Polygone löschen). **BEOBACHTUNG** (ZBrush-Forum, §15.4).
4. **Der Preis einer Entscheidung ist unsichtbar, bevor sie getroffen ist.** Die Software könnte aus
   §15.0 wissen, ob ein gewünschter Übergang in reinen Quads überhaupt geht (Parität) und was er kostet
   (Polpaar, Dreieck oder Zusatzloop). Der Artist erfährt es heute durch Scheitern — wie in
   `CONNECT_NONQUAD_DISCOVERY.md` F1/F2 beschrieben. **INTERPRETATION.**
5. **Vorschau vor dem Commit ist selten.** Dual Strip Weaving zeigt den Vorschlag beim Hovern, *bevor*
   etwas passiert; die meisten Modeling-Werkzeuge zeigen das Ergebnis erst danach. Knüpft an die
   Hypothese aus §7.3 an (Wert hängt an der Sichtbarkeit der Konsequenz). **BEOBACHTUNG.**
6. **Die Absicht geht nach dem Schritt verloren.** Außer Node-History und MESHmachines Wiedererkennung
   wird nirgends festgehalten, *warum* eine Topologie so aussieht. **BEOBACHTUNG.**

---

### 16.6 E — Grenzen: wo Automatik vermutlich NICHT übernehmen sollte

| Situation | Warum der Artist entscheiden sollte | Evidenz |
|---|---|---|
| **Wo der Pol landet** | Keine belastbare Distanzregel (§15.1); abhängig von Glanz, Krümmung, Deformation | FAKT (Takayama 2013: Artists wollen Kontrolle über Singularitäten) + §15.1 |
| **Pol vs. Dreieck vs. Ngon vs. Zusatzloop** | Das ist die Währungsfrage (§15.0); beide Seiten haben je nach Kontext recht (§15.9) | FAKT (Peng & Wonka 2013: Trade-off Pole ↔ Nicht-Quads) + KONSENS (Polycount) |
| **Deformationsgetriebene Topologie** | Die Software kennt das Gelenkmodell nicht (Raitts Schulter, §5.5) | FAKT (Raitt/Minter) |
| **Mehrdeutige Eingaben** | Mehr als zwei Loops → „unvorhersehbar" steht sogar im Maya-Handbuch | FAKT |
| **Globale Löser** | Ändern mehr als gefragt (ZRemesher, Chord Collapse §15.5) | FAKT / BEOBACHTUNG |
| **Versteckte Vorbedingungen** | Build End nur bei genau zwei Loops; Build Corner mit Modifier-Problem → brüchige Idiome untergraben Vertrauen | FAKT + BEOBACHTUNG |
| **Nicht-Determinismus** | „Anderes Ergebnis rechnen lassen" ersetzt Vorhersagbarkeit durch Ausprobieren | KONSENS |

#### Interaktionskosten — Low-Level vs. Absichts-Ebene

| Kriterium | Low-Level-Kette | Absichts-Operation | Evidenzlage |
|---|---|---|---|
| Kontrolle | vollständig, Schritt für Schritt | auf die freigegebenen Größen beschränkt | INTERPRETATION |
| Vorhersagbarkeit | hoch pro Schritt, niedrig fürs Gesamtergebnis | hoch, *wenn* das Ergebnis in Artist-Begriffen beschreibbar ist | INTERPRETATION |
| Auffindbarkeit | Grundwerkzeuge sichtbar | Idiome oft versteckt (Build End) | BEOBACHTUNG |
| Umkehrbarkeit | Undo pro Schritt, Zwischenzustände oft ungültig | ein Schritt; Nachjustieren möglich (Adjust Last Operation) | FAKT (Blender) / INTERPRETATION |
| Mehrdeutigkeit | Artist löst sie im Kopf | Software muss sie auflösen oder fragen | INTERPRETATION |
| Vertrauen | wächst mit Übung | bricht bei jeder verletzten Vorbedingung | BEOBACHTUNG (Build-Corner-Bericht) |
| Topologiequalität | so gut wie der Artist | so gut wie das Muster — Forschung: Muster aus Artist-Modellen (Marcias) | FAKT / INTERPRETATION |
| Tempo | viele Schritte | wenige | trivial |
| Lernkurve | Werkzeugwissen *und* Topologiewissen | Topologiewissen bleibt nötig, um das Ergebnis zu beurteilen | INTERPRETATION |

> **INTERPRETATION — wo Automatik unverständlicher wird als Handarbeit:**
> Eine Absichts-Operation bleibt verständlich, solange der Artist ihr Ergebnis **vorher** in den Begriffen
> beschreiben kann, in denen er selbst denkt („zwei Reihen enden hier, das Polpaar sitzt an der
> Nasolabialfalte"), und **nachher** sehen kann, *warum* es so gekommen ist. Wo eine dieser beiden
> Bedingungen fehlt, kippt sie vermutlich — unabhängig davon, wie gut das Ergebnis objektiv ist.

---

### 16.7 F — Neue Hypothesen

Alle Punkte sind **HYPOTHESE** oder **OFFENE FRAGE**. Keiner ist eine Empfehlung.

**H1 — Beenden heißt einen Partner wählen.** *(HYPOTHESE, gestützt auf §15.0 und Build End)*
Weil ein Quad-Streifen nur zusammen mit einem Partner enden kann, reduziert sich „diesen Loop hier beenden"
auf zwei Artist-Entscheidungen: **mit welchem Nachbarstreifen** und **wo**. Wenn das stimmt, ist die
Absicht „beenden" kleiner und präziser, als sie klingt.

**H2 — Der Streifen ist die Denkeinheit.** *(HYPOTHESE)*
Artists denken in Streifen/Loops, nicht in Kanten (Raitts Muskel-Griff, Dual Strip Weaving; Polycount-
Hinweis, dass reine Quads vor allem Loop-/Ring-Auswahl nutzbar halten). Mirai hat Loop-/Ring-Erkennung bereits — der Test ist billig (16.9 T2).

**H3 — Der Preis ist wichtiger als die Automatik.** *(HYPOTHESE)*
Den Preis einer Absicht **vor** dem Commit zu zeigen („kostet ein Polpaar" / „geht nur mit Dreieck oder
einem Zusatzloop") könnte mehr Probierschleifen verhindern als das automatische Ausführen selbst.
Das ist die Konsequenz-Sichtbarkeits-Hypothese aus §7.3, übertragen von der Geometrie auf die Topologie.

**H4 — Position darf eine Antwort geben, Konnektivität sollte Alternativen zeigen.** *(HYPOTHESE)*
Positions-Hilfen sind breit etabliert, Konnektivitäts-Hilfen kaum (16.2.9). Mögliche Erklärung:
Positionsergebnisse sind kontinuierlich und nachstellbar, Konnektivitätsergebnisse sind diskrete Varianten.
Auffällig ist, dass die erfolgreichen Konnektivitäts-Systeme **Auswahl** anbieten (Pattern-based: andere
zulässige Lösungen; Dual Strip Weaving: Vorschlag + Klick; ZRemesher: alternative Lösung).

**H5 — Hover-Vorschlag passt zur Mirai-Linie.** *(HYPOTHESE, gehört als Frage ins UX-System)*
Dual Strip Weaving zeigt beim Hovern den besten Streifen. Mirai-Bastel arbeitet ohnehin hover-lastig
(Tweak, Knife-Hover). Ob „Hover zeigt, wo dieser Loop enden würde und was es kostet" zur Interaction
Language passt, ist eine **UX-Frage** → `UX_RESEARCH.md` / Research Map (*Signalling*, *Composition*),
nicht hier zu entscheiden.

**H6 — Absicht als Operationskontext.** *(OFFENE FRAGE, Zuständigkeit ARCH-02)*
Das README formuliert für Symmetrie: eine Modellierabsicht → bekannter Operationskontext → bekannte
Identitätsänderungen. Eine Absichts-Operation („Kehre zwischen Streifen A und B") trägt mehr Bedeutung
als ihre Primitive-Kette (drei Connects, ein Collapse). Ob das für spätere Remapping-Fragen (Weights,
Morphs) nützlich wäre, ist eine Frage für **ARCH-02** — hier nur benannt, keine Architekturaussage.

**H7 — Wiedererkennen statt Erinnern.** *(HYPOTHESE)*
MESHmachine zeigt, dass eine Absicht aus der Geometrie rekonstruierbar sein kann. Topologische Muster
sind ebenfalls lesbar: Eine Kehre ist ein erkennbares Dipol-Muster, ein 3→1-Übergang ein erkennbares
Muster. Absichts-Bearbeitung bräuchte dann nicht zwingend gespeicherte History.

**H8 — Ein Rezept ist eine Kette mit Löchern.** *(HYPOTHESE)*
Ein persönliches Artist-Rezept („Lippe", „Augenhöhle", „Dichteübergang") wäre eine feste Kette plus
wenige offene Größen (Start, Ende, Anzahl, Seite) — genau wie Houdinis promotete Parameter. Das Wissen
steckt in der Kette, die Kontrolle in den Löchern. Die schwierige Frage ist nicht das Aufzeichnen,
sondern **welche Löcher offen bleiben**.

**H9 — Das Wort „Flow" ist doppelt belegt.** *(BEOBACHTUNG → HYPOTHESE)*
Geometrischer Fluss (Positionen folgen der Krümmung) und topologischer Fluss (Richtung der Streifen)
werden im selben Wort geführt. Eine Trennung im Vokabular könnte Gespräche und Experimente in diesem
Projekt schärfer machen — auch ganz ohne Werkzeug.

#### Die ambitionierte Frage: Was würde denkbar, wenn Mirai um Absichten herum gedacht wäre?

Nur Denkräume, ausdrücklich keine Vorschläge:

- **Der Streifen als anfassbares Objekt.** Einen Loop greifen und sein *Ende* an eine andere Stelle ziehen,
  statt Kanten umzubauen.
- **Der Pol als Griff.** Einen Pol ziehen, und die Umgebung baut sich per Dipol-Bewegung nach
  (die Operationen dafür existieren in der Forschung, 16.2.8).
- **Ein „Unruhe-Budget" malen.** Das Gegenstück zur ZRemesher-Dichtebemalung: nicht malen, wo *Dichte*
  hin soll, sondern wo *Unregelmäßigkeit* erlaubt ist (ruhige Zonen, §15.4). Absichten legen ihre Pole
  dann bevorzugt dorthin. In der untersuchten Literatur nicht gefunden.
- **Preisschilder statt Fehlermeldungen.** Statt „Operation nicht möglich" die Liste der Wege, wie es
  ginge — und was jeder kostet.
- **History in Absichtssprache.** Die History zeigt „Kehre an der Wange" statt „Connect ×3, Collapse".
- **Rezepte aus dem eigenen Verhalten.** Wiederkehrende Ketten aus dem Griffzähler (E1) werden
  sichtbar und können benannt werden (Autocomplete-Sculpting-Gedanke, aber für Topologie).
- **Konsequenz in Bewegung.** Absicht auslösen und sofort im gebogenen Zustand sehen (verbindet §8.3,
  E4 und die vorhandene Artikulation).

---

### 16.8 Mirais spezifische Lücke — ist das Ebenenmodell belegt?

Die Aufgabenstellung schlägt vor: **Primitive → Topologie-Operation → Topologie-Absicht → Artist-Workflow**.
§10.3 hatte bereits drei Ebenen (Mechanik / Operation / Absicht).

**Was die Evidenz stützt:**
- **FAKT:** Peng 2011 baut Absichts-Operationen („Polpaar bewegen") ausdrücklich **aus** Primitiven
  (Collapse, Flip, Split). Die Trennung Mechanik ↔ höhere Operation ist dort real und funktioniert.
- **FAKT:** Pattern-based (2014) und Data-driven (2015) arbeiten mit einer **Musterebene** — einer kleinen
  Menge topologischer Muster zwischen Absicht und Mechanik. Die Community kennt dasselbe als
  „Reduktionsmuster" (§15.3).

**Was die Evidenz ergänzt (INTERPRETATION):** Zwischen Operation und Absicht scheint eine eigene Ebene
zu liegen — **Muster / Idiom** (Kehre, 3→1, Quad-Ecke, Build End). Und die Absichtsebene selbst ist
nicht homogen, sondern zerfällt in Konnektivität, Position und Reichweite (16.3.2):

```
Mechanik        split · collapse · connect · (dissolve) · (flip/spin)
    ↓
Operation       Connect · Knife · Loop Insert · Extrude · Slide
    ↓
Muster/Idiom    Kehre · Quad-Ecke · 3→1 · 4→2 · Ring um Merkmal
    ↓
Absicht         Konnektivität (legen / enden / abbiegen) · Position (Form folgen / verteilen)
                · Reichweite (begrenzen / bewahren)
    ↓
Workflow        Volumen → Oberfläche → Prüfen an Silhouette / Kontur / Bewegung (§5)
```

Das ist eine Deutung, **kein Architekturvorschlag**.

**Was zwischen Mirais heutigen Operationen und dem Artist-Denken fehlt (Feststellung, Stand `d4cf93f`):**

- Die Operationsebene ist für **Streifen legen** gut besetzt (Connect pro Face, Knife, Loop Insert).
- Für **Streifen enden lassen** ist sie seit dem Connect-Lab-Verdikt mechanisch möglich (Teilschnitte
  hinterlassen Fünfecke, die weiterbearbeitet werden können), aber es gibt keine Muster-Ebene darüber.
- Für **Streifen abbiegen / Pol versetzen** fehlen die zwei billigsten Mechaniken aus §15.1/§15.2:
  **Kante drehen** und **Dissolve**. (Feststellung, keine Empfehlung.)
- Für **Position** gibt es Loop Slide (nur geschlossene reguläre Loops), keine Form-folgen- oder
  Verteilen-Hilfe.
- **Kopplung, die leicht übersehen wird:** Loop-Auswahl und Loop Slide funktionieren nur über reguläre
  Valenz-4-Topologie. Genau dort, wo der Artist lokal Kontrolle schafft (Teil-Loops mit Polen), enden
  also auch die Loop-Griffe (§15.6 Punkt 5). Wer lokale Kontrolle erzeugt, verliert an dieser Stelle
  heute seine Streifen-Werkzeuge.

---

### 16.9 G — Kandidaten für Artist-Experimente

Wie §13 und §15.11: klein, mit vorhandener Infrastruktur, als **KANDIDAT** markiert. Wo möglich als
**Variante eines bestehenden Kandidaten**, damit die Liste nicht nur wächst.

**T1 — Absichtssatz mit freiem Vokabular** *(Variante von E2)*
- *Frage:* Deckt das kleine Vokabular aus 16.3 Manus eigene Wörter ab? Hypothese A vs. B (§10.2).
- *Aufbau:* Wie E2 — vor drei Topologie-Handlungen je ein Satz, was er will. Zusätzlich hinterher:
  Welche seiner Wörter passen in die Tabelle 16.3.1, welche nicht?
- *Kosten:* keine Codezeile.
- *Mögliche Ergebnisse:* Wörter passen (Vokabular trägt) / Werkzeugnamen dominieren (Hypothese B) /
  ganz andere Wörter (Vokabular ist persönlich, §14 Punkt 2).

**T2 — Strich statt Klick** *(neu, ohne Code)*
- *Frage:* H2 (Streifen als Denkeinheit) und das Gesten-Modell (C der Aufgabenstellung).
- *Aufbau:* Screenshot eines Playground-Meshes (Kopf oder Raster). Manu zeichnet *vor* dem Modellieren
  mit einem beliebigen Malprogramm, wo Fluss hin soll und wo er enden soll. Danach modelliert er es.
  Verglichen wird Zeichnung mit Ergebnis und Anzahl der Operationen.
- *Was es zeigt:* ob die Absicht als Linie/Streifen, als Region oder als Punkt gedacht wird.

**T3 — Preisschild** *(Variante von L2, Wizard-of-Oz)*
- *Frage:* H3, H4.
- *Aufbau:* Die vier vorbereiteten L2-Lösungen (Kehre, Dreieck-Ende, lokaler Ring, durchgehender Loop)
  einmal ohne und einmal **mit Beschriftung des Preises** zeigen („+1 Polpaar", „+1 Dreieck",
  „+1 Loop über 40 Faces"). Die Beschriftung macht ein Agent vorab von Hand — keine Software.
- *Was es zeigt:* ob sichtbarer Preis die Wahl verändert oder beschleunigt.
- *Voraussetzung:* L2-Meshes müssen vorbereitet sein (Agentenarbeit, nicht Artist-Arbeit).

**T4 — Unruhe-Zonen malen** *(neu, Wizard-of-Oz)*
- *Frage:* Ist eine Regions-Absicht (D der Aufgabenstellung) für Manu sinnvoll — in der Umkehrung
  „wo darf Unregelmäßigkeit hin"?
- *Aufbau:* Auf einem Screenshot markiert Manu ruhige Zonen. Ein Agent löst eine Verdichtungsaufgabe von
  Hand so, dass die Pole dort landen. Manu beurteilt nur das Ergebnis: KEEP / ITERATE / REJECT / UNKNOWN.
- *Was es zeigt:* ob „Zonen markieren" als Ausdrucksform überhaupt trägt, bevor irgendetwas gebaut wird.

**T5 — Rezept aus der eigenen Kette** *(Folge von E1, erst danach sinnvoll)*
- *Frage:* H8.
- *Aufbau:* Aus einem E1-Mitschnitt die wiederkehrenden Ketten heraussuchen. Manu entscheidet, welche
  er benennen würde, und welche Größen (Start, Ende, Anzahl …) für ihn offen bleiben müssten.

**T6 — Beenden als Partnerwahl** *(Variante von L3)*
- *Frage:* H1 und das Gegenargument aus 16.3.3.
- *Aufbau:* Wie L3, aber die Aufgabe einmal als „lass den Loop hier enden" und einmal als „lass diesen
  Loop mit jenem Nachbarn verschmelzen" formulieren. Welche Formulierung fühlt sich natürlich an?

**Vorgeschlagene Reihenfolge nach Erkenntnis pro Aufwand:** T1 (= E2) → T2 → T6 (mit L3) → T3 (mit L2)
→ T4 → T5 (nach E1). Die Priorität entscheidet der Artist.

**Bewusst nicht vorgeschlagen:** Experimente, die eine SubD-Vorschau, Dissolve oder Kante-drehen
voraussetzen. Diese existieren nicht, und sie für ein Experiment zu bauen, wäre eine
Prioritätsentscheidung des Artists (vgl. L4).

---

### 16.10 Offene Fragen dieses Abschnitts

| # | Frage | Art |
|---|---|---|
| I-Q1 | Denkt Manu Konnektivitäts-Absichten als Linie (Streifen), als Region oder als Punkt? | Artist-Selbstversuch (T2) |
| I-Q2 | Ist „beenden" für ihn eine Einheit oder „mit Partner verschmelzen"? | Artist-Selbstversuch (T6) |
| I-Q3 | Verändert ein sichtbarer Preis die Topologieentscheidung? | Experiment (T3) |
| I-Q4 | Gibt es in DCCs, die hier nicht geprüft wurden (Modo, Cinema 4D, Plasticity, Houdini-Modeling-Tools), weitere Konnektivitäts-Idiome? | Recherche |
| I-Q5 | Tragen Absichts-Operationen Informationen, die für spätere Remapping-Fragen nützlich sind? | ARCH-02 |
| I-Q6 | Wiedererkennen oder Erinnern — welcher Weg würde Absichten über den Schritt hinaus tragen, und welcher passt zu Undo über Snapshots (AD-001)? | Architektur, erst nach Artist-Evidenz |
| I-Q7 | Wie viele der Muster (Kehre, 3→1, Quad-Ecke) braucht Manu tatsächlich? Wenige oder viele? | Messbar (E1) |

---

### 16.11 Was dieser Abschnitt NICHT beantwortet

- Ob Mirai-Bastel Absichts-Operationen bauen sollte. **Nicht gefolgert.**
- Wie Manu tatsächlich denkt — nur, was die Branche und die Forschung anbieten.
- Wie gut die Forschungssysteme sich im Alltag bewähren. Belegt sind Papers mit kleinen Nutzerstudien,
  keine Produktionserfahrung.
- Ob die Stichprobe der DCCs repräsentativ ist (16.1).
- Irgendeine Interaktions-, Tasten- oder Architekturfrage.

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
| Autodesk 3ds Max Hilfe: *Loops Panel* (Set Flow, Auto Loop, Flow Connect, Distance Connect, Build End, Build Corner) | Software-Dokumentation | hoch (für Verhalten) |
| Autodesk-Forum: *Build Corner does not work* (Edit-Poly-Modifier) | Community | niedrig (BEOBACHTUNG) |
| Autodesk Maya Hilfe: *Edit Edge Flow*, *Quad Draw Tool Options*, *Quad Draw marking menu* | Software-Dokumentation | hoch (für Verhalten) |
| Maxon ZBrush-Dokumentation: ZModeler Edge Actions/Targets; ZRemesher-Funktionsübersicht | Software-Dokumentation | hoch (für Existenz der Funktionen) |
| ZBrushCentral: *ZModeler insert edgeLoop redirect edge flow*; *How to create an edge loop* | Community | niedrig–mittel (Artist-Problembeschreibung) |
| Novedge-Tippartikel zu ZRemesher und ZModeler | Händlerblog, teils widersprüchlich | niedrig (nur KONSENS) |
| RetopoFlow 3/4 — Herstellerbeschreibung (CG Cookie / Orange Turbine) | Herstellerdoku | mittel |
| Blender-Handbuch: *Grid Fill*; *Undo & Redo — Adjust Last Operation* | Software-Dokumentation | hoch (für Verhalten) |
| MACHIN3: *MESHmachine* Dokumentation und Produktbeschreibung | Herstellerdoku | mittel |
| SideFX: *Houdini Digital Assets* (Einführung, Asset-UI/Parameter-Promotion) | Software-Dokumentation | hoch (für Verhalten) |
| Polycount: *Holding edges (bevel) while maintaining quad based geometry* | Community | niedrig–mittel (KONSENS) |
| Takayama, Panozzo, Sorkine-Hornung, Sorkine-Hornung: *Sketch-Based Generation and Editing of Quad Meshes*, SIGGRAPH 2013 | Fachpublikation | hoch |
| Takayama, Panozzo, Sorkine-Hornung: *Pattern-Based Quadrangulation for N-Sided Patches*, SGP 2014 | Fachpublikation | hoch |
| Marcias et al.: *Data-Driven Interactive Quadrangulation*, SIGGRAPH 2015 | Fachpublikation | hoch |
| Campen, Kobbelt: *Dual Strip Weaving*, SIGGRAPH Asia 2014 | Fachpublikation | hoch |
| Peng, Zhang, Kobayashi, Wonka: *Connectivity Editing for Quadrilateral Meshes*, SIGGRAPH Asia 2011 | Fachpublikation | hoch |
| Peng, Wonka: *Connectivity Editing for Quad-Dominant Meshes*, SGP 2013 | Fachpublikation | hoch |
| Peng, Xing, Wei: *Autocomplete 3D Sculpting*, SIGGRAPH 2018 | Fachpublikation | hoch |

---

## Verwandte Dokumente

- `AGENTS.md` — Repository-Regeln
- `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` — M1–M5, Artist-Attention-Filter
- `ROADMAP.md` — Modeling Track, WP-03, ARCH-02
- `CHARACTER_SYSTEMS_RESEARCH.md` — Character-Systems-Research (Rigging, Deformation, Facial-Systeme)
- `docs/design/artist_playground/UX_RESEARCH.md` und Research Map V1 — Interaction Grammar
- `experiments/rigging-skinning-morphing/` — technische Realität der Topologie-Mutation
- `experiments/topology/` — Loop/Ring, Connect Edges
- `docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md` und AD-017 — Connect/Split/Knife-Semantik (§16)
- `docs/design/artist_playground/RESEARCH_MAP.md` — Composition/Signalling als Ziel der UX-Fragen aus §16
- `playground/experiments/articulation/` — temporäre Artikulation (relevant für E4)

---

**Nächster sinnvoller Schritt ist nicht, dieses Dokument zu erweitern.**
Er ist, eines der Experimente aus §13, §15.11 oder §16.9 zu spielen und zu beobachten, was passiert.
Mit V1.2 gilt das umso mehr: Die Recherche beschreibt jetzt Branche, Forschung und Mathematik recht
vollständig — und noch immer nichts über den einen Artist, für den das Werkzeug gebaut wird.
