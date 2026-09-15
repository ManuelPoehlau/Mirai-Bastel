# Character Systems Research

**Status:** Discovery — externe Research, keine Entscheidungen
**Datum:** 2026-09-15
**Version:** V1 (erste Fassung)

---

## Scope

Dieses Dokument ist das autoritative Zuhause für die **artist-seitige Research zu Character Systems**: Rigging, Controls/Handles, Skinning, Weighting, Deformation, Posing, Morphing/Blendshapes, Correctives, Facial Deformation, prozedurales/automatisches Rigging.

Es sammelt, **was andere Menschen ausprobiert haben**, und wie sie dabei gedacht haben.

### Was dieses Dokument nicht ist

- keine Rigging-Architektur
- keine technische Spezifikation
- keine Entscheidungsliste
- keine Best-Practice-Sammlung
- keine Implementierungsplanung
- keine Empfehlung für Mirai-Bastel

### Abgrenzung zu bestehenden Dokumenten

| Dokument | Verantwortung |
|---|---|
| `docs/design/artist_playground/UX_RESEARCH.md` + Three-Role UX System | Interaction Grammar und Research-Methode |
| `experiments/rigging-skinning-morphing/` (RESEARCH, DESIGN, AD-005, FINDINGS) | technische Experimente, Core-Verhalten, Architekturwissen |
| **dieses Dokument** | externe Research, Konzepte, Observations, mögliche Experimentideen |

Querverweise sind erwünscht. Verantwortungen werden nicht vermischt. Insbesondere: Eine Observation hier ist **nie** eine Antwort auf eine offene Architekturfrage aus AD-005. Sie kann eine Frage *beleuchten*, aber nicht entscheiden.

### Sprache

Dieses Dokument ist auf Deutsch geschrieben, weil es ein Denk- und Diskussionsdokument ist (wie `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md`). Die englischsprachigen Design-/Agent-Dokumente bleiben unberührt. Falls die Repo-Konvention Englisch verlangt, ist das eine Umstellung, keine Umschreibung des Inhalts.

---

## Research Principles

**1. Observation statt Empfehlung.**
Nicht: „X ist besser als Weight Painting."
Sondern: „X verschiebt die Aufgabe von expliziter Weight-Bearbeitung nach …"

**2. Existenz ist keine Validierung.**
Dass Maya, Blender, ein Plugin oder ein SIGGRAPH-Paper etwas so macht, sagt nichts darüber, ob es für Mirai richtig ist. Marktanteil ist kein Argument. Alter ist kein Argument.

**3. Belegt vs. angenommen wird gekennzeichnet.**
Jede Observation trägt ein Evidenzniveau:

- `[Quelle]` — mit Referenz unten belegt
- `[Erfahrungswissen]` — aus allgemeiner Kenntnis formuliert, noch nicht gegenbelegt; vor Weiterverwendung prüfen

**4. Die interessante Frage ist die Unzufriedenheit.**
Wir suchen nicht „die besten Rigging-Tools", sondern Leute, die mit einem etablierten Workflow nicht zurechtkamen und deshalb etwas anderes gebaut haben. Das gelöste Problem ist wertvoller als die Lösung.

**5. Implementierungsentscheidung ≠ UX-Idee.**
Vieles, was nach einem Konzept aussieht, ist nur eine technische Notwendigkeit von damals. Jede Observation fragt deshalb: Was davon ist Technik, was davon ist eine andere Denkweise?

### Observation-Format

```
O-xx — Name
Problem                — was den Autor gestört hat
Konventioneller Weg    — was man vorher tat
Veränderte Annahme     — welche DCC-Selbstverständlichkeit fällt weg
Interaktion            — was der Artist konkret tut
Mentales Modell        — womit der Artist jetzt denkt
Verschobene Verantwortung — was der Artist nicht mehr tut, wer es stattdessen tut
Beobachtbarer Vorteil
Neue Probleme / offene Fragen
Technik oder UX-Idee?
```

---

## Research Map

Bewusst eine Ablage, kein Raster zum Ausfüllen. Leere Bereiche sind normal und bleiben normal.

| Bereich | bisher gesammelt |
|---|---|
| Rig / Controls / Handles | O-04, O-05, O-07, O-08 |
| Skinning / Weights | O-01, O-06, O-09 |
| Deformation | O-02, O-04 |
| Posing | O-03, O-07 |
| Morphs / Shapes | — |
| Correctives | O-05 |
| Facial Systems | — |
| Automatic / Procedural | O-08 |
| Alternative Paradigmen | O-03, O-04 |

Ein System kann in mehreren Bereichen stehen. Das ist kein Fehler, sondern oft der interessante Teil.

---

## Observations

### O-01 — Weight Transfer über Topologiegrenzen (GATOR, copySkinWeights, Data Transfer)

`[Erfahrungswissen]`

**Problem:** Retopo oder Meshänderung nach dem Skinning macht die Gewichtung wertlos.
**Konventioneller Weg:** Gewichte neu malen.
**Veränderte Annahme:** Gewichte gehören nicht diesem konkreten Mesh mit diesen konkreten IDs. Sie sind räumlich definierte Information, die von einem Mesh auf ein anderes übertragen werden kann.
**Interaktion:** Altes und neues Mesh selektieren, Transfer auslösen.
**Mentales Modell:** „Die Gewichtung liegt im Raum, nicht in der Vertexliste."
**Verschobene Verantwortung:** Der Artist wählt die Zuordnungsmethode; die räumliche Suche übernimmt das System.
**Beobachtbarer Vorteil:** Topologiefreiheit nach dem Rigging; Umbauten ohne ID-Verwandtschaft überleben.
**Neue Probleme:** Proximity irrt systematisch an Spalten (Lippen, Achsel, Finger). Das alte Mesh muss aufbewahrt werden. Es ist ein Batch-Vorgang mit einem Vorher und Nachher — kein lebendiger Zustand.
**Technik oder UX-Idee?** Beides. Die Implementierung ist Geometrie-Suche. Die Idee „Rig-Daten sind nicht an Mesh-Identität gebunden" ist ein anderes mentales Modell.

---

### O-02 — Delta Mush / Corrective Smooth

`[Erfahrungswissen]` — Rhythm & Hues, SIGGRAPH 2014 Talk; in Blender als Modifier „Corrective Smooth"

**Problem:** Die letzten 20 % Gewichtungsqualität kosten 80 % der Zeit.
**Konventioneller Weg:** Einzelvertices polieren, bis Kollaps und Zacken verschwinden.
**Veränderte Annahme:** Deformationsqualität muss nicht aus der Gewichtung selbst kommen.
**Interaktion:** Grob zuweisen, Deformer hinzufügen, weiterarbeiten.
**Mentales Modell:** Das deformierte Ergebnis wird geglättet; das im Rest-Zustand gemessene lokale Detail wird wieder aufgesetzt. Der Artist denkt in „Silhouette grob richtig, Detail kommt zurück".
**Verschobene Verantwortung:** Von manueller Weight-Bearbeitung zu einem nachgelagerten Deformationsprozess.
**Beobachtbarer Vorteil:** Grobe Gewichte liefern brauchbare Ergebnisse; die Fehlertoleranz der Gewichtung steigt deutlich.
**Neue Probleme:** Der Artist sieht nicht mehr, *warum* etwas gut aussieht. Kosten pro Frame. Absichtlich scharfe Kanten werden mitgeglättet. Die Vorberechnung hängt an der Rest-Topologie — bei Loop-Insert entsteht dasselbe Problem eine Schicht höher.
**Technik oder UX-Idee?** Die Glättung ist Technik. Die Idee „Qualität nachgelagert erzeugen statt vorne präzise arbeiten" ist eine Haltung, die auch anderswo auftauchen könnte.

---

### O-03 — Posen ohne Rig: Blender Pose Brush

`[Quelle]` — Dobarro, Blender 2.81/2.82

**Problem:** Um Deformation zu *beurteilen*, braucht man normalerweise erst ein fertiges Rig. Bones bauen, binden, gewichten — und erst dann sieht man, ob die Absicht funktioniert.
**Konventioneller Weg:** Rig zuerst, Pose danach.
**Veränderte Annahme:** Die Deformationsstruktur muss nicht vor der Geste existieren und nicht nach ihr weiterleben.
**Interaktion:** Cursor auf den Unterarm, ziehen — der Arm knickt. Der Brush bestimmt den Ursprungspunkt selbst und zeigt ihn als weiße Linie im Cursor an. IK-Segmente entstehen automatisch, Brush-Falloff bestimmt, wie weit die Rotation durch die Kette läuft.
**Mentales Modell:** „Ich fasse die Figur an", nicht „ich bediene einen Controller".
**Verschobene Verantwortung:** Segmentierung und Pivotbestimmung wandern komplett zum System; der Artist liefert nur Ort und Richtung.
**Beobachtbarer Vorteil:** Deformationsabsicht wird testbar, bevor Rig-Daten existieren. Das Ergebnis ist reine Geometrie — topologisch weiter frei bearbeitbar.
**Neue Probleme:** Nicht wiederholbar, nicht animierbar, keine Zeitkonsistenz. Der Ursprungspunkt ist eine Systemschätzung; wenn sie danebenliegt, hat der Artist kein direktes Korrekturmittel außer der Geste selbst.
**Technik oder UX-Idee?** Deutlich UX-Idee. Interessant ist nicht der IK-Solver (klein und bekannt), sondern die Entscheidung, die Struktur **pro Geste** entstehen und wieder verschwinden zu lassen.

---

### O-04 — Ein Weight-System für Punkte, Bones und Cages (Bounded Biharmonic Weights)

`[Quelle]` — Jacobson, Baran, Popović, Sorkine-Hornung, SIGGRAPH 2011

**Problem:** Die Autoren benennen zwei Zumutungen des linearen Blendings ausdrücklich: Man muss entweder Gewichte von Hand malen oder geschlossene Käfige um das Objekt modellieren.
**Konventioneller Weg:** Pro Deformerart ein eigenes System — Joints mit Weight Painting, Cluster mit Falloff, Lattice mit Käfig.
**Veränderte Annahme:** Der Handle-Typ muss nicht bestimmen, welches Deformationssystem läuft. Punkte, Bones und Cages beliebiger Topologie können **gleichzeitig** und **gemischt** dasselbe Objekt steuern.
**Interaktion:** Der Artist setzt den Handle-Typ, der für die jeweilige Teilaufgabe am bequemsten ist — Bones für starre Teile, Cages für großflächige präzise Kontrolle, Punkte für weiche Bereiche.
**Mentales Modell:** „Ich setze Einflusspunkte" statt „ich baue ein Skelett und dazu noch einen Lattice".
**Verschobene Verantwortung:** Die Gewichtsberechnung wandert in eine Optimierung zur Bind-Zeit; der Artist entscheidet nur noch *wo* Einfluss sitzt, nicht *wie stark wo*.
**Beobachtbarer Vorteil:** Die Wahl des Werkzeugs richtet sich nach der Aufgabe, nicht nach der Systemarchitektur. Weight Painting entfällt als Pflichtschritt.
**Neue Probleme:** Die Autoren nennen selbst Raumdiskretisierung und Optimierung als Nachteil. Gewichte entstehen zur Bind-Zeit — was bei Topologieänderung passiert, ist damit noch nicht beantwortet. Und: Wenn der Artist die Gewichte nicht mehr malt, wie korrigiert er eine Stelle, an der die Automatik falsch liegt?
**Technik oder UX-Idee?** Die Gewichtsformel ist Technik. Die Aussage „der Artist soll frei mit der bequemsten Kombination von Handle-Typen arbeiten" ist explizit als UX-Ziel formuliert und ist der interessante Teil.

---

### O-05 — Smart Bones und Smart Bone Dials (Moho / früher Anime Studio)

`[Quelle]`

**Problem:** Ein gebeugter Ellbogen kollabiert. In einem 3D-DCC hieße die Lösung Pose Space Deformation oder Corrective Shape — beides Begriffe, die ein 2D-Animator nicht lernen will.
**Konventioneller Weg:** Driven Keys, PSD-Setups, Corrective-Blendshape-Pipelines mit eigener Terminologie.
**Veränderte Annahme:** Eine Korrektur muss kein eigenes Systemkonzept sein. Sie kann eine aufgezeichnete Aktion sein, die an einem Knochenwinkel hängt.
**Interaktion:** Knochen zum Smart Bone erklären, Aktion anlegen, den Knochen in die problematische Stellung drehen, die Form dort von Hand zurechtziehen. Moho interpoliert zwischen gestrecktem und korrigiertem Zustand.
**Mentales Modell:** „Wenn dieser Knochen so steht, soll es so aussehen." Kein Solver-Begriff, kein Shape-Editor, kein Zwischenobjekt.
**Verschobene Verantwortung:** Die gesamte PSD-Maschinerie verschwindet hinter einer Aufnahmegeste.
**Zweite, separate Beobachtung:** Der **Smart Bone Dial** ist ein Knochen, der an gar nichts gebunden ist und außerhalb der Figur liegt. Er wird nur als Regler benutzt — für Kopfdrehungen, Blinzeln, Gesichtsausdrücke. Technisch ein Bone, funktional ein Slider. Der Systemtyp sagt nichts über die Rolle im Rig.
**Beobachtbarer Vorteil:** Correctives werden für Leute zugänglich, die nie ein PSD-Setup gebaut hätten. Ein einziges Primitiv (Knochen) deckt Deformation *und* Steuerung ab.
**Neue Probleme:** Aus den Anwenderforen: Namenskonventionen sind kritisch (Aktionsname muss exakt zum Knochennamen passen), Winkelbereiche und Richtungen sind fehleranfällig, Verschachtelung wird schnell undurchsichtig. Die Einfachheit der Geste kauft man mit einer unsichtbaren Regel-Ebene.
**Technik oder UX-Idee?** Beides, und beide getrennt interessant: die Korrektur-als-Aufnahme, und der zweckentfremdete Knochen als Regler.

---

### O-06 — Gewichte als Ebenen statt als Zahlenfeld (ngSkinTools)

`[Quelle]` — Maya-Plugin, Viktoras Makauskas

**Problem:** Weight Painting ist destruktiv. Jeder Strich überschreibt den vorherigen Zustand; die *Absicht* hinter einer Gewichtung ist nachträglich nicht mehr auffindbar. Die klassische Gegenmaßnahme ist Influence Locking und Mikromanagement einzelner Werte.
**Konventioneller Weg:** Ein flaches Gewichtsfeld pro Vertex, mühsam gegen Überschreiben gesichert.
**Veränderte Annahme:** Gewichte müssen kein flacher Endzustand sein. Sie können wie in einem Bildbearbeitungsprogramm aus Ebenen mit Masken zusammengesetzt werden, die erst zur Laufzeit kombiniert werden.
**Interaktion:** Wirbelsäule in einer Ebene malen, Arme in einer anderen; das System kombiniert in Echtzeit zum Endgewicht für den Skin Cluster. Eine untere „Sicherheitsebene" mit 100 % garantiert die Normalisierung.
**Mentales Modell:** Photoshop. Ausdrücklich so beworben: schmutzig anfangen, experimentieren, später verfeinern.
**Verschobene Verantwortung:** Das Zusammenrechnen; der Artist arbeitet in Absichtsschichten statt in Endwerten. Influence Locking wurde bewusst weggelassen — mit Ebenen sei es unnötige Komplexität.
**Beobachtbarer Vorteil:** Eine Entscheidung kann rückgängig gemacht werden, ohne die Nachbarentscheidungen zu zerstören. Symmetrie wird pro Ebene aktivierbar, statt als globaler Vorgang.
**Neue Probleme:** Zwei Wahrheiten im selben Dokument — Anwender werden gewarnt, die Maya-Standardwerkzeuge nicht parallel zu benutzen, weil die Ebenen die Änderungen beim nächsten Zugriff überschreiben. Das ist die Kernspannung: Eine Absichtsschicht über einem Endzustand ist nur konsistent, wenn niemand den Endzustand direkt anfasst.
**Technik oder UX-Idee?** UX-Idee mit klarer Architekturfolge. „Der Artist bearbeitet nicht das Ergebnis, sondern die Herkunft des Ergebnisses" ist ein Muster, das weit über Skinning hinausgeht.

---

### O-07 — ZSpheres und Transpose (ZBrush)

`[Erfahrungswissen]`

**Problem:** Skelettaufbau und Bindung sind zwei getrennte Fachdisziplinen, bevor man überhaupt eine Pose sehen kann.
**Konventioneller Weg:** Joints platzieren, orientieren, binden, gewichten.
**Veränderte Annahme:** Dieselbe Primitivkette, die die Struktur beschreibt, kann auch die Geometrie erzeugen bzw. steuern. Und: Posieren kann eine Maskierungsgeste sein statt eine Hierarchieauswahl.
**Interaktion (Transpose):** Bereich maskieren, Linie ziehen, ziehen/drehen. Der „Rig" ist die Maske.
**Mentales Modell:** Die Auswahl *ist* die Einflusszone. Kein persistenter Controller.
**Verschobene Verantwortung:** Keine Bindung, keine Gewichtung — dafür trägt der Artist die volle Verantwortung für die Qualität der Maske.
**Beobachtbarer Vorteil:** Sehr kurzer Weg von „ich will das sehen" zu „ich sehe es".
**Neue Probleme:** Nicht animierbar; Übergangsbereiche sind nur so gut wie die Maskenkante; kein wiederverwendbarer Zustand.
**Status:** Nicht gegenbelegt. Vor Weiterverwendung prüfen.

---

### O-08 — Rig als Geometrie und Graph (Houdini KineFX)

`[Erfahrungswissen]`

**Problem:** Rigging ist eine Einbahnstraße. Ist gebunden, sind Änderungen upstream teuer.
**Konventioneller Weg:** Modell → Rig → gebundener Zustand; danach ist das Mesh weitgehend eingefroren.
**Veränderte Annahme:** Ein Skelett muss kein Sondertyp sein. Es kann Geometrie mit Attributen sein — und damit mit normalen Geometriewerkzeugen bearbeitbar.
**Interaktion:** Rigging findet als Knotenkette statt. Eine Topologieänderung ist ein weiterer Knoten vor dem Deform; danach wird neu ausgewertet.
**Mentales Modell:** „Der Rig ist ein Rezept, kein Zustand."
**Verschobene Verantwortung:** Vom Artist zum Graphen — mit dem Preis, dass der Artist prozedural denken muss.
**Beobachtbarer Vorteil:** Genau die Frage, an der das bestehende Mirai-Experiment hängt (Topologieänderung nach dem Rigging), wird strukturell aufgelöst statt nachträglich repariert.
**Neue Probleme:** Direkte Manipulation geht tendenziell verloren; der prozedurale Mehraufwand ist für ein kleines direktes Modellierwerkzeug erheblich; Gewichte als Attribute brauchen eigene Erzeugungsregeln.
**Status:** Nicht gegenbelegt. Vor Weiterverwendung prüfen.

---

### O-09 — Der „Weight Hammer" als Symptom

`[Quelle]` — Anwenderdiskussion, Maya LT

Kleine Beobachtung aus der Praxis, kein System: Ein Anwender fügt nach dem Rigging Polygone hinzu und kann auf den neuen Vertices keine Gewichte mehr malen. Die verbreitete Antwort ist ein Werkzeug namens „Weight Hammer", das die Gewichte der Nachbarvertices auf die neuen überträgt.

**Warum das hier steht:** Das Problem ist in etablierten DCCs so normal, dass es dafür ein Werkzeug mit eigenem Namen und Icon gibt — und der Standardumgang trotzdem Verwirrung erzeugt. Das ist ein Hinweis darauf, dass „Topologieänderung nach dem Rigging" nicht ein Mirai-Sonderfall ist, sondern ein branchenweiter Dauerschmerz mit lauter Teillösungen.

**Offene Frage:** Wie oft passiert das wirklich, und was tun Artists stattdessen — bearbeiten sie einfach nicht mehr? Das wäre eine Vermeidungshaltung, nicht eine Lösung, und sie wäre in keiner Dokumentation sichtbar.

---

## Research-Faden 1 — Ein Handle-Begriff statt Bone / Cluster / Lattice / Cage

**Forschungsfrage:**

> Muss ein Artist überhaupt wissen, welche technische Deformationsstruktur hinter einem Manipulationspunkt steckt?

Ausdrücklich **nicht** vorausgesetzt, dass „Handle" die richtige Antwort ist. Die Frage ist, welche Antworten reale Systeme geben.

### Wie die bisherigen Observations antworten

| System | Antwort auf die Frage | Wodurch |
|---|---|---|
| Klassisches DCC | **Ja** — der Artist muss es wissen | Joint, Cluster, Lattice, Wire haben je eigene Erzeugung, eigene UI, eigenes Weight-Konzept |
| BBW (O-04) | **Nein** — der Typ ist eine Bequemlichkeitsfrage | ein Gewichtssystem trägt Punkte, Bones und Cages gemischt |
| Pose Brush (O-03) | **Nein** — es gibt gar keine persistente Struktur | Pivot und Segmentierung entstehen pro Geste und verschwinden wieder |
| Smart Bone Dial (O-05) | **Nein, aber verdeckt** — es ist ein Knochen, der kein Knochen ist | Systemtyp und Rolle sind entkoppelt, ohne dass das System das benennt |
| Transpose (O-07) | **Nein** — die Maske ist die Struktur | Auswahl statt Controller |
| KineFX (O-08) | **Ja, aber anders** — der Artist denkt in Daten, nicht in Deformertypen | Skelett ist Geometrie |

### Was in dieser Übersicht auffällt

Die interessante Achse ist möglicherweise gar nicht „ein Typ vs. viele Typen", sondern **wie lange die Struktur lebt**:

```
pro Geste erzeugt und verworfen     →  Pose Brush, Transpose
zur Bind-Zeit erzeugt, dann fest    →  BBW
dauerhaft und vom Artist gepflegt   →  klassisches Rig
bei jeder Auswertung neu erzeugt    →  KineFX
```

Das ist eine Hypothese aus der Gegenüberstellung, keine Erkenntnis. Sie bräuchte mehr Fälle.

### Noch nicht untersucht in diesem Faden

Implicit Skinning (Kontakt und Bulge statt Gewichtspolitur) · Wires (Singh/Fiume 1998, Kurve als Deformer) · Blender Hook-Modifier (beliebiges Objekt wird zum Handle) · Houdini-Handles als vom Knoten entkoppelte Manipulatoren · Cage-basierte IK · Direct Manipulation Blendshapes · Poser-Magnete · Daz JCM · Cascadeur AutoPosing · Spine/Live2D/Rive (2D-Rigging mit ganz anderen Grundannahmen) · Ziva (Deformation als Anatomiesimulation) · automatische Rigger (Pinocchio, Mixamo, RigNet).

---

## Candidate Playground Experiments

Ideen, keine Vorschläge zur Umsetzung. Ob, wann und in welcher Reihenfolge etwas davon gebaut wird, entscheidet Manu. Jedes davon wäre ein isoliertes Artist-Playground-Experiment nach `EXPERIMENT_HOST.md`, kein Rigging-Feature.

**CE-1 — Nur Punkt-Handles**
Head-Basemesh, ausschließlich Punkt-Handles mit Falloff, kein Skelett, keine Hierarchie. Frage: Wie weit trägt ein einziger Handle-Begriff, bevor der Artist etwas vermisst — und was genau vermisst er zuerst?
Berührt: O-04, Forschungsfrage Faden 1.

**CE-2 — Sichtbarer vs. unsichtbarer Einflussbereich**
Derselbe Handle, einmal mit dargestelltem Einflussgebiet, einmal ohne. Frage: Ist der Einfluss überhaupt vorhersagbar, ohne ihn zu sehen? Achtung: Das variiert *Signalling*, was laut Research Map V1 die größte Confounding-Gefahr ist — hier ist Signalling ausnahmsweise die Variable selbst.

**CE-3 — Gestenabgeleiteter Pivot vs. gesetzter Pivot**
Ziehen an einer Stelle des Meshes; einmal bestimmt das System den Drehpunkt (Pose-Brush-artig), einmal setzt ihn der Artist vorher. Frage: Wo genau kippt Bequemlichkeit in Kontrollverlust?
Berührt: O-03.

**CE-4 — Korrektur als Aufnahme**
Element in eine Stellung bringen, Form dort zurechtziehen, System interpoliert. Frage: Ist „wenn es so steht, sieht es so aus" ohne Shape-/PSD-Terminologie verständlich und beherrschbar?
Berührt: O-05.

**CE-5 — Absichtsschicht statt Endzustand**
Ein beliebiger Wert (nicht notwendigerweise Gewichte) wird in zwei Ebenen bearbeitet statt direkt. Frage: Fühlt sich „ich bearbeite die Herkunft des Ergebnisses" freier oder indirekter an?
Berührt: O-06.

**Nicht als Kandidat aufgeführt:** alles, was Topologieänderung unter aktiver Deformation testet. Das ist Gegenstand des bestehenden technischen Experiments (`experiments/rigging-skinning-morphing/`) und gehört nicht als UX-Experiment hierher dupliziert.

---

## Open Questions

1. Ist „wie lange lebt die Deformationsstruktur" tatsächlich die tragende Achse, oder ein Artefakt der bisher gesammelten sechs Fälle?
2. Wenn die Automatik die Gewichte bestimmt (O-04) — wie korrigiert der Artist eine Stelle, an der sie falsch liegt, ohne das ganze Konzept zu verlassen?
3. Gibt es reale Beispiele, in denen die Trennung Modellieren/Rigging vollständig aufgehoben wurde, und nicht nur nachträglich repariert wird?
4. Was machen Artists, die Topologieänderung nach dem Rigging schlicht *vermeiden*? Diese Vermeidungshaltung ist in keiner Dokumentation sichtbar, aber vermutlich der häufigste Umgang.
5. 2D-Rigging (Moho, Spine, Live2D) hat Annahmen, die im 3D-Kontext gar nicht gelten. Welche der dortigen Ideen sind übertragbar, und welche funktionieren nur, weil es 2D ist?
6. Wieviel der bekannten DCC-Rigging-Komplexität existiert für Filmproduktion in großen Teams — und ist für einen einzelnen Artist an einem Kopf-Basemesh schlicht irrelevant?

---

## Sources / References

**Belegt:**

- Bounded Biharmonic Weights — Jacobson, Baran, Popović, Sorkine-Hornung, SIGGRAPH 2011. https://igl.ethz.ch/projects/bbw/ · Paper-PDF: https://igl.ethz.ch/projects/bbw/bounded-biharmonic-weights-siggraph-2011-jacobson-et-al.pdf · CACM-Fassung: https://cacm.acm.org/research/bounded-biharmonic-weights-for-real-time-deformation/
- Blender Pose Brush — Handbuch: https://docs.blender.org/manual/en/latest/sculpt_paint/sculpting/brushes/pose.html · Entwicklerbericht: https://code.blender.org/2020/02/sculpt-mode-features-update/ · Erste Vorstellung: https://www.blendernation.com/2019/12/12/preview-sculpt-mode-pose-brush/ · Dobarro zum Sculpt-Mode allgemein: https://pablodp606.artstation.com/blog/1vEn/new-blender-sculpt-mode-introduction
- Moho Smart Bones — Herstellerbeschreibung: https://moho.lostmarble.com/pages/features · Einordnung als Corrective/PSD-Äquivalent: https://lesterbanks.com/2016/11/working-mohos-smart-bone-actions/ · Smart Bone vs. Smart Bone Dial (Anwenderforum): https://lostmarble.net/forum/viewtopic.php?t=35634
- ngSkinTools — Produktbeschreibung: https://www.ngskintools.com/ · Layer-Konzept: https://www.ngskintools.com/documentation/userguide/quickstart/ · bewusstes Weglassen von Influence Locking: https://www.ngskintools.com/documentation/userguide/faq/ · Praxiserfahrungen inkl. Konflikt mit Maya-Standardwerkzeugen: https://rigmarolestudio.com/ngskintools-skinning-tips/
- Weight Hammer / Polygone nach dem Rigging: https://steamcommunity.com/app/243580/discussions/0/357287935556802103

**Noch nicht gegenbelegt (Erfahrungswissen, vor Weiterverwendung prüfen):**

- GATOR (Softimage), Maya `copySkinWeights`, Blender Data Transfer
- Delta Mush (Rhythm & Hues, SIGGRAPH 2014) / Blender Corrective Smooth
- ZBrush ZSpheres und Transpose / Transpose Master
- Houdini KineFX

---

## Verwandte Dokumente

- `AGENTS.md` — Repository-weite Agenten- und Dokumentationsregeln
- `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` — M1–M5, Discovery/Production, Artist Verdict
- `docs/design/artist_playground/UX_RESEARCH.md` — Interaction Grammar (andere Verantwortung)
- `docs/design/artist_playground/EXPERIMENT_HOST.md` — Experiment/Variant/Slot-Vokabular für spätere Experimente
- `experiments/rigging-skinning-morphing/` — technisches Rigging-Experiment, AD-005, FINDINGS (andere Verantwortung)
