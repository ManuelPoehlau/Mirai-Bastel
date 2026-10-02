# Subdivision Surfaces (SubD) — Research V1

**Status:** Discovery — Recherche, keine Entscheidungen
**Datum:** 2026-10-02
**Modus (M5):** Discovery, Typ-B-Research
**Ablage:** `docs/research/subdivision/` (Einstieg: [`README.md`](README.md))
**Priorität:** Artist-Entscheidung Manu 2026-10-02 — SubD ist der nächste sinnvolle Schritt nach den Research-Dokumenten zu Geometrie-Entfernung und Geometrie-Hinzufügen.

> Dieses Dokument trifft **keine** Produktentscheidung, schlägt keine Architektur vor, legt keine
> Hotkeys fest und sagt nicht „Mirai soll X bauen". Es beschreibt den Raum, sammelt Evidenz und
> bereitet Artist-Tests vor. Entscheidungen trifft der Artist in den dafür zuständigen Dokumenten.

**Bereits entschieden und hier nicht neu verhandelt:** Das Control Mesh ist autoritativ. Die abgeleitete
(unterteilte) Oberfläche ersetzt es nie (`docs/V1_SPEC.md` §11, `docs/architecture/V1_CORE.md` §10).

**Evidenzstufen** wie in `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §3 und `Extrude_als_Konstruktions-Paradigma_Research_V1.md`:

| Stufe | Bedeutung |
|---|---|
| **FAKT** | In einer nachprüfbaren Quelle belegt (Handbuch, Paper, Quellcode). |
| **BEOBACHTUNG** | Selbst gesehen: Code gelesen, Messung gemacht, Verhalten geprüft. Bei Messungen steht immer, *wo* gemessen wurde. |
| **KONSENS** | Breit vertretene Community-Aussage, nicht einzeln geprüft. Verbreitung ≠ Beweis. |
| **INTERPRETATION** | Eigene Deutung der Befunde. Nicht die Aussage der Quelle. |
| **HYPOTHESE** | Testbare Vermutung ohne Evidenz. |
| **OFFEN** | Bewusst unbeantwortet. |

*Hinweis:* `docs/research/README.md` nennt noch die englischen Stufen FACT/OBSERVED/INTERPRETATION/HYPOTHESIS.
Die deutschen Stufen oben sind die, die die jüngeren deutschsprachigen Research-Dokumente benutzen (inkl. KONSENS).

---

## 0. History Awareness (M1) und Context Check (M2)

**Ergebnis in zwei Zeilen:**
Es gibt **keinen** SubD-Code im Repository und hat nie welchen gegeben — der in `V1_CORE.md` §10 erwähnte
„simple Catmull-Clark prototype" wurde nie committet. Vorhanden sind verstreute Evidenz (Mirai, Modeling-Workflow,
Symmetry, Face Holes, Shading), ein leerer README-Stub hier und mehrere Experimente, die ausdrücklich auf eine SubD-Vorschau warten.

### 0.1 Existenzprüfung — Repository `main` @ `4631c33`

| Existiert | Wo | Bedeutung für diese Research |
|---|---|---|
| Entscheidung „Control Mesh autoritativ" | `V1_SPEC.md` §11, `V1_CORE.md` §10, `MIRAI_SYSTEMS.md` §6 | Fest. Alles hier baut darauf auf. |
| Offene Architekturfrage „Caching derived geometry" | `V1_CORE.md` §19 Frage 8 | Wird in §4.6 und §7.3 berührt, nicht beantwortet. |
| Satz „current prototype contains a simple Catmull-Clark implementation" | `V1_CORE.md` §10 | **Veraltet / nie zutreffend im Repo.** Siehe 0.2. |
| Mirai als SubD-Modeler, Volume Modeling, Derived Surface | `MIRAI_SYSTEMS.md` §6, `MIRAI_SYSTEMS_1999.md` §4/§7, `RESEARCH_LOG.md`, `ARCHAEOLOGY_FINDINGS_001.md` §5 | Historische Grundlage für §2. |
| SubD-Literatur, Pole, Kontrollmesh+Vorschau-Schleife | `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §4.4, §7, §15.7, §15.8 (Szenario 5), §15.10 (L-Q3, L-Q7) | Wird **nicht** wiederholt, nur verlinkt und vertieft. |
| Experimente, die auf SubD-Vorschau warten | dieselbe Datei: Kandidat **L4**, Kandidat **L2**, §13 **E3**, Hinweis bei §16 („bewusst nicht vorgeschlagen") | Dort steht: Vorschau nicht ohne Artist-Priorisierung bauen. Die Priorisierung betrifft jetzt die **Research**; ob gebaut wird, ist weiterhin Artist-Entscheidung. |
| Subdivision Shading bewusst zurückgestellt | `VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md` §5, §9 | Gehört hierher (§6.3). |
| Inkrementelles Update-Modell, Topologie-Rebuild | `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` §1, §5.2, §5.4, §12 | Rahmen für §4/§5. Ziel < 15 ms Interaktionslatenz. |
| `DerivedGeometry` (Normalen, Adjazenz, Ear Clipping) | `src/viewport/derived.py` | Reines Python, keine NumPy-Abhängigkeit. |
| NumPy nicht verpflichtend | `docs/viewport/VIEWPORT_V02_RESEARCH.md` §19 | Relevant für §4.4/§5. |
| Referenz-Hardware | `docs/architecture/REFERENCE_HARDWARE.md` | OpenGL 3.3 ist die Obergrenze. Kein Compute, keine Tessellation. |
| Deformationskette Base → Morph → Skin → Subdivision | `src/core/mesh.py` Header, `CORE_API_AUDIT.md` | Reihenfolge ist als Raumhalter dokumentiert, nicht implementiert. |
| SubD × Symmetrie | `symmetry/EDIT_MODE_SYMMETRY_RESEARCH.md` (Q24, Q25, `mirror_flatten`), `SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md` (Subdivide-Zeile) | Für §7.2. |
| SubD × Löcher | `topology/FACE_HOLES_DISCOVERY.md` (Zeilen zu „Subdivision (future)") | Holed Faces sind für SubD nicht definiert. |
| Wunschliste | `docs/project planning/… Artist Toolbox - Einkaufsliste.md` §11 (alles `[ ]`), §10.2 (Subdivide/Unsubdivide/Smooth `[ ]`), §13.2 (Smooth Shading `[x]`, Crease visualization `[ ]`) | Unbewertet. Wird hier nicht geändert. |
| Testmeshes | `examples/meshes/SubD_Cube.obj` (26 V / 24 Quads), `head_basemesh.obj` (326 V / 324 Quads), `Man_With_Shoes_basemesh.obj` (928 V / 926 Quads) | Alle reine Quad-Meshes. Für Messungen in §5 benutzt. |
| Taste `C` | AD-017 (kontextuelles C für Split/Connect/Knife) | In Silo ist `C` laut aktuellem Quick-Start **Subdivide** (§8). Nur eine Beobachtung für spätere Binding-Fragen, keine Entscheidung. |

**Verworfenes:** Zu SubD wurde nichts verworfen. Kein validiertes System wird ersetzt.

### 0.2 Der verschwundene Catmull-Clark-Prototyp

- **BEOBACHTUNG (Git):** `git log -S "catmull" -i --all` findet nur Doku-Commits. Kein Python-Commit enthielt je
  Catmull-Clark-Code (Suche auch nach `edge_point`, `face_point`, `def …subdiv`: nur Knife-Code mit „face points").
- **BEOBACHTUNG (Git):** Der Satz entstand in `242262c` („docs: add V1 core architecture draft") am 2026-08-25 —
  am selben Tag wie der Initial Commit `3b64143`.
- **INTERPRETATION:** Der Prototyp lag vermutlich außerhalb des Repos (früher Chat- oder lokaler Prototyp) und wurde
  nie eingecheckt. Er ist nicht „entfernt" oder „archiviert", sondern im Repo nie vorhanden gewesen.
- **Konsequenz:** `V1_CORE.md` §10 beschreibt einen falschen Stand. Korrekturvorschlag in §12.

### 0.3 Context Check — meine Annahmen (nur korrigieren, wenn falsch)

1. Die beiden Research-Dokumente zu **Geometrie-Entfernung** und **Geometrie-Hinzufügen** sind noch nicht im Repo
   (`main` @ `4631c33`, Suche nach Dateiname und Inhalt leer). Ihre §10 konnte ich **nicht lesen**. Die Themen daraus,
   die der Kickoff nennt (Dissolve vs. Delete unter SubD, Hinzufügen verändert die SubD-Form, Crease vs. Support Loops,
   Silo „Refine Control Mesh"), behandle ich hier aus eigener Recherche. Sobald die Dokumente committet sind, gehört ein
   Abgleich dazu (offene Frage OF-11).
2. Der Kickoff nennt als Intent-Variante „Editing the derived surface (Mirai original)". **Dafür habe ich weder im Repo
   noch in neuen Quellen einen Beleg gefunden.** Belegt ist für Mirai das Gegenteil: Ein Kontrollvolumen steuert eine
   abgeleitete Fläche und aktualisiert sie live (§2.1). Ich behandle „auf der abgeleiteten Fläche arbeiten" deshalb als
   Variante, die es in anderen DCCs gibt (Maya Modus 3, Blender „On Cage", Silo „Refine"), aber **nicht** als belegtes
   Mirai-Verhalten. Falls Manu eine konkrete Quelle oder Erinnerung dazu hat, ändert das §2.
3. Mirai-Bastel-Symmetrie arbeitet auf einem vollständigen Mesh mit beiden Hälften und deklarierten Seam-Edges
   (`SymmetryDefinition` in `src/core/mesh.py`), nicht mit einer virtuellen Spiegelhälfte. §7.2 baut darauf auf.

### 0.4 Begriffe, die leicht verwechselt werden

| Begriff | Was es ist | Im Projekt |
|---|---|---|
| **Smooth Shading** | Vertex-Normalen gemittelt, Geometrie unverändert | existiert (`[x] Smooth` in Toolbox §13.2) |
| **Subdivision Surface (SubD)** | Neue, feinere Geometrie nach Regeln aus dem Control Mesh abgeleitet | existiert nicht |
| **Subdivision Shading** | Normalen mitunterteilen bzw. aus der Grenzfläche nehmen | existiert nicht (§6.3) |
| **Smooth / Relax** (Glätten) | Vertices verschieben, Topologie gleich | existiert nicht (Toolbox §10.2 `[ ] Smooth`) |
| **Wings „Smooth"** | **Destruktive** Catmull-Clark-Unterteilung | — |

Für Artists, die von Wings kommen, heißt „Smooth" also etwas anderes als in Blender oder Maya. Für Bedienung und
Doku ist das eine Stolperfalle (INTERPRETATION).

---

## 1. Forschungsfrage und Scope

**Frage:** Was bedeutet „Subdivision" in einem Modeler der Mirai/Silo/Wings-Linie — für den Artist, als Verfahren,
technisch auf alter Hardware, in der Darstellung und im Zusammenspiel mit den Systemen, die es schon gibt?

**Im Scope:** Die sieben Fragen des Kickoffs (Intent, Algorithmen, Implementierungslandschaft, Performance,
Viewport, Systemwechselwirkungen, DCC-Vergleich).

**Nicht im Scope:** Implementierung, Core-Änderungen, Renderer-Architektur, Sculpting/Multires,
Entscheidung über die Speicherung von Creases.

**Methode:** Repository-Dokumente und -Code gelesen; Wings-3D-Quellcode gelesen (`dgud/wings`, `src/wings_proxy.erl`,
`wings_subdiv.erl`, `wings_cc.erl`, `wings_view.erl`, `wings_hotkey.erl`, `wings_pref.erl`, gelesen 2026-10-02);
Hersteller-Dokumentation (Silo, Blender, Maya, 3ds Max, Modo, OpenSubdiv); eine kleine Wegwerf-Messung in
einer Sandbox (§5, kein Repo-Code).

---

## 2. Artist Intent — was „SubD" im Modeler bedeuten kann (Frage 1)

### 2.1 Was für Mirai belegt ist

- **FAKT (zeitgenössisch, 1999):** Mirai war polygon-/subdivision-basiert, nicht NURBS-basiert. „Volume Modeling":
  ein niedrig aufgelöstes Kontrollvolumen, daraus eine höher aufgelöste geglättete **Derived Surface**; Änderungen am
  Kontrollvolumen aktualisieren die abgeleitete Fläche. (`MIRAI_SYSTEMS_1999.md` §4, §7, Quelle [3] dort.)
- **FAKT (zeitgenössisch, 1999):** Das Kontrollvolumen konnte mehrere Detailstufen erzeugen, die Face-Anzahl blieb unter
  Oberflächendeformation stabil, und es konnte wie ein Lattice-Deformer für Posen und Morph Targets wirken (ebd. §7).
- **FAKT (Raitt/Minter 2000):** Live-Aktualisierung (Fläche am Kontrollobjekt skalieren → abgeleitete Fläche ändert sich sofort);
  Flächenmitten als Vorhersageheuristik; Kontrollobjekt nie so komplex, dass man es nicht mehr frei drehen kann
  (`MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §15.7).
- **OFFEN:** Ob man in Mirai direkt auf der abgeleiteten Fläche selektieren/editieren konnte, wie Stufen umgeschaltet
  wurden und welche Kantenregeln galten. `MIRAI_SYSTEMS_1999.md` „Still open" nennt Algorithmus und Extraordinary-Vertex-Behandlung
  ausdrücklich als unbekannt.

### 2.2 Die Intent-Modelle, die es in der Praxis gibt

Fünf unterscheidbare Modelle. Sie schließen sich **nicht** aus; die meisten DCCs kombinieren zwei oder drei.

| # | Modell | Was der Artist tut | Wo die Wahrheit liegt | Beispiele (Belege in §8) |
|---|---|---|---|---|
| **A** | **Vorschau-Schalter** | Schaltet die geglättete Ansicht an/aus, um zu prüfen | Control Mesh | Maya `1`/`2`/`3`, Wings Shift+Tab (alle Objekte) |
| **B** | **Am Käfig arbeiten, Fläche live sehen** | Editiert das grobe Mesh, sieht dauerhaft das Ergebnis | Control Mesh | Mirai Volume Modeling, Silo (Standard), Wings Proxy Mode, 3ds Max NURMS + Show Cage, Maya Modus 2 |
| **C** | **Auf der Fläche greifen, Käfig wird bewegt** | Klickt/zieht scheinbar auf der glatten Fläche; das Werkzeug wirkt auf die zugehörigen Kontrollelemente | Control Mesh | Maya Modus 3 (Änderungen werden auf das Original zurückgespielt), Silo mit ausgeblendetem Käfig, Blender „On Cage" |
| **D** | **Backen / Verfeinern** | Macht die abgeleitete Fläche zum neuen Control Mesh | **neues** Control Mesh | Silo Refine (Shift+C), Wings Smooth, Maya „Convert Smooth Mesh Preview to Polygons", Modo Subdivide |
| **E** | **Teil-Unterteilung** | Unterteilt nur ausgewählte Bereiche | je nach Tool | Silo Partial Subdivide, Wings Smooth auf Face-Auswahl |

**INTERPRETATION — was die Entscheidung „Control Mesh autoritativ" schon festlegt und was nicht:**
- A, B und C sind mit ihr voll verträglich. In allen drei bleibt das Control Mesh die einzige editierbare Wahrheit;
  C ist „nur" eine andere Art, Kontrollelemente zu *treffen*.
- D ist verträglich, aber in einem anderen Sinn: Die abgeleitete Fläche wird nicht editiert, sie *wird* zum Control Mesh.
  Das ist eine Topologie-Operation (wie Extrude) mit neuen IDs und Provenienz-Fragen (ARCH-02).
- E ist im SubD-Sinn eigentlich D auf einem Teilbereich (destruktiv), oder — bei Silo — eine Unterteilung, deren Grenze
  selbst Regeln braucht. Es ist das am wenigsten verbreitete Modell.
- Die Kickoff-Formulierung „editing the derived surface" passt am ehesten zu **C** (scheinbar auf der Fläche, technisch am Käfig)
  oder zu **D** (backen, dann weiterarbeiten). Beides ist hier abgedeckt; die Research-Richtung ist dadurch **nicht blockiert**.
  Deshalb keine Vorab-Frage an Manu.

### 2.3 Was Stufen (Levels) für den Artist bedeuten

- **FAKT:** Eine Catmull-Clark-Stufe macht aus jedem Quad vier (Blender-Handbuch; Guerrilla CG; Modo). Viele DCCs trennen
  Viewport-Stufe und Render-Stufe (Blender „Levels Viewport/Render", 3ds Max „Iterations" in Display- und Render-Gruppe).
- **FAKT:** Bedienung der Stufe ist sehr unterschiedlich: Silo `C`/`V` (mehrfach drücken = mehr/weniger Stufen),
  Maya Page Up/Page Down, Blender Ctrl+1…, Max Zahlenfeld, Wings Proxy fest eine Stufe (mit OpenCL bis 5, §8).
- **INTERPRETATION:** Für Formarbeit braucht es nur eine Stufe, die „glatt genug" aussieht. Wie hoch sie sein muss, hängt
  von Monitor, Abstand und Mesh-Dichte ab. Ob Manu überhaupt Stufen wechseln will oder eine feste „sieht glatt aus"-Stufe
  genügt, ist eine Artist-Frage (OF-2, Test T-SUBD-2).

### 2.4 Was die bestehende Research schon über den Wechsel Käfig ↔ Fläche weiß

Siehe `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §15.7: Tabelle „nur im Kontrollmesh lesbar / nur in der SubD sichtbar",
Diagnose Form- vs. Topologieproblem, offene Frage **L-Q3** („Wie oft und wodurch ausgelöst wechseln Modeller?").
Diese Research fügt die Werkzeugseite hinzu (§6, §8), beantwortet L-Q3 aber nicht — das bleibt eine Beobachtungsfrage.

---

## 3. Der Algorithmenraum (Frage 2)

### 3.1 Catmull-Clark in einem Schritt

**FAKT (Catmull & Clark 1978; Standardliteratur):** Eine Stufe erzeugt drei Arten neuer Punkte:

| Neuer Punkt | Regel (innen, glatt) | Analogie für Artists |
|---|---|---|
| **Face Point** | Mittelwert aller Vertices der Fläche | ein neuer Punkt in der Mitte jeder Fläche |
| **Edge Point** | Mittelwert aus den zwei Endpunkten und den zwei angrenzenden Face Points | ein Punkt auf jeder Kante, leicht zur Wölbung hin gezogen |
| **Vertex Point** (alter Vertex, verschoben) | `(F + 2R + (n−3)·P) / n` — F: Mittel der angrenzenden Face Points, R: Mittel der Kantenmitten, P: alte Position, n: Valenz | der alte Punkt rutscht in Richtung seiner Nachbarschaft — deshalb „schrumpft" eine SubD-Form gegenüber dem Käfig |

Dann wird jede Fläche mit `n` Ecken in `n` Quads zerlegt (Ecke → Edge Point → Face Point → Edge Point).

**Folgen, die für Artists sichtbar sind (FAKT, Standardliteratur; teils schon in `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §4.4/§7):**
- Nach einem Schritt besteht alles aus Quads, auch aus Dreiecken und N-Gons.
- Jede Nicht-Quad-Fläche erzeugt in ihrer Mitte einen Pol (Valenz = Eckenzahl). Ein Dreieck wird zu drei Quads mit einem
  Valenz-3-Pol, ein Fünfeck zu fünf Quads mit einem Valenz-5-Pol.
- Die Anzahl der Pole ändert sich nach Stufe 1 nicht mehr. Höhere Stufen machen sie nur kleiner.
- Reguläre Bereiche (Valenz 4) ergeben im Grenzwert bikubische B-Spline-Flächen (C²); an Polen nur C¹.

### 3.2 Ränder (offene Kanten)

- **FAKT (Standardliteratur):** Randkanten werden wie Kurven unterteilt: Edge Point = Kantenmitte; Rand-Vertex =
  `(P_vorher + 6·P + P_nachher) / 8`. Dadurch bleibt der Rand eine glatte Kurve und schrumpft weniger als die Fläche.
- **FAKT (3ds Max OpenSubdiv-Modifier; Modo):** Für Ränder gibt es Varianten: „Kanten scharf" oder „Kanten und
  Zwei-Kanten-Ecken scharf". Modo bietet „Smooth All / Crease All / Crease Edges". OpenSubdiv nennt diese Wahl
  „Boundary Interpolation" (Sdc::Options).
- **INTERPRETATION:** Ob die Ecke eines offenen Randes (z. B. die Ecke eines Planes) fest bleibt oder sich rundet, ist
  eine sichtbare Formfrage, keine Implementierungsdetail-Frage. Das ist ein Kandidat für ein Artist-Urteil, sobald es
  spielbar ist (OF-4).
- **Bezug Löcher:** `FACE_HOLES_DISCOVERY.md` stellt fest, dass Faces mit Löchern für Subdivision nicht definiert sind
  und vorher überbrückt werden müssten. Ein echtes Loch (gelöschte Faces) ist dagegen ein normaler Rand mit Randregeln.

### 3.3 N-Gons, Dreiecke, Pole

- **FAKT (OpenSubdiv-Doku):** Bei Quad-Schemata wie Catmull-Clark werden Nicht-Quad-Flächen als Satz quadratischer
  „Sub-Faces" parametrisiert. Das deckt sich mit 3.1: Ab Stufe 1 gibt es nur Quads.
- **FAKT:** Modo bietet neben Catmull-Clark einen eigenen Algorithmus („SDS"), der leicht andere Ergebnisse liefert; Pixar-
  Catmull-Clark verzerrt laut Modo-Doku UVs weniger und erlaubt Edge Creasing.
- **INTERPRETATION:** „Welche Variante von Catmull-Clark?" ist keine akademische Frage. Silo selbst warnt, dass sich
  SubD zwischen Programmen unterscheidet und nicht direkt übertragen lässt (§8). Austauschbarkeit mit anderen Tools
  (OBJ-Export, späteres Rendern woanders) spricht für die verbreitete Pixar/OpenSubdiv-Variante — sobald das Projekt
  Export braucht. Das ist eine Beobachtung, keine Empfehlung.

### 3.4 Creases (scharfe und halbscharfe Kanten)

| Art | Wirkung | Belege |
|---|---|---|
| **Unendlich scharf** | Kante wird wie ein Rand behandelt: Kurvenregel entlang der Kante. Vertex mit 2 scharfen Kanten → Crease-Regel, ≥ 3 → Ecke (bleibt stehen). | Standardliteratur; Wings respektiert „Hard Edges" im Proxy (BEOBACHTUNG Code: `wings_cc.erl` zählt harte Kanten pro Vertex, gedeckelt bei 3) |
| **Halbscharf (semi-sharp)** | Schärfewert `s`: In den ersten Stufen gelten scharfe Regeln, pro Stufe wird `s` um 1 kleiner, danach glatt. Gebrochene Werte mischen. | DeRose/Kass/Truong 1998 (schon in `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §15.7); OpenSubdiv `Sdc::Crease` |
| **Chaikin-Variante** | Schärfe wird entlang einer Kantenkette interpoliert; bessere Übergänge bei unterschiedlichen Gewichten | 3ds Max OpenSubdiv-Modifier; OpenSubdiv „creasing method" |
| **Vertex Crease** | Einzelner Vertex bleibt (teil-)spitz | Blender, OpenSubdiv (Toolbox §11 listet „vertex crease") |

- **FAKT (Silo-Doku):** Creases lassen sich nicht in andere Programme exportieren, außer man verfeinert (Refine) das Mesh.
- **FAKT (OpenSubdiv 3.1 Release Notes):** Halbscharfe Features verlangen bei adaptiver Auswertung eine Isolationstiefe,
  die so hoch ist wie die größte Schärfe — das macht sie teuer.
- **KONSENS:** Support Loops (zusätzliche Kantenringe nah an einer Kante) sind die verbreitete Alternative zu Creases;
  sie übertragen sich in jedes Format, kosten aber Geometrie und machen die Fläche nah an der Kante härter
  (`MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §15.7 „Wann mehr Dichte das Problem verschlimmert", §15.8 Szenario 5).
- **INTERPRETATION — die eigentliche Artist-Frage:** Crease ist „Schärfe als Attribut" (Pixar-Linie), Support Loop ist
  „Schärfe durch Topologie" (Raitt-Linie). Ob Manu Schärfe als Kanteneigenschaft oder als Geometrie denken will, ist eine
  Intent-Frage (OF-5). Wie Creases gespeichert würden, ist ausdrücklich nicht Teil dieser Research.

### 3.5 Grenzfläche (Limit Surface) vs. Stufen

- **FAKT (Standardliteratur):** Unendlich oft unterteilt konvergiert Catmull-Clark gegen eine Grenzfläche. Für jeden Vertex
  lässt sich die Grenzposition direkt aus seiner Nachbarschaft berechnen (Limit-Maske, Halstead/Kass/DeRose 1993; für einen
  inneren Vertex mit Valenz n: `(n²·P + 4·ΣE + ΣF) / (n·(n+5))`, E = Kantennachbarn, F = Diagonalnachbarn). Stam (1998)
  zeigt die exakte Auswertung an beliebigen Parameterwerten.
- **FAKT (Blender-Handbuch):** „Use Limit Surface" setzt Vertices auf die Grenzfläche, mit einstellbarer Genauigkeit.
- **INTERPRETATION für Artists:** Stufe 2 und Grenzfläche sehen sich ähnlich, aber nicht gleich: Die Stufe ist ein
  Zwischenschritt, die Grenzfläche ist „die wahre Form". Für einen Modeler zählt vor allem, dass die Vorschau sich
  vorhersagbar verhält. Grenzpositionen und Grenznormalen sind billig und deshalb für Darstellung (§6.3) und Picking (§6.4)
  interessanter als für die Geometrie selbst.

### 3.6 Nur zum Kontrast: Loop, Doo-Sabin, Bilinear

| Schema | Eingabe | Eigenschaft | Relevanz |
|---|---|---|---|
| **Loop** (1987) | Dreiecke | C² regulär bei Valenz 6 | Triangle-Meshes; in Quad-Modelern selten. OpenSubdiv unterstützt es. |
| **Doo-Sabin** (1978) | beliebig | Dual-Schema, quadratisch, C¹ | historisch; in heutigen Modeling-DCCs praktisch nicht verbreitet (KONSENS) |
| **Bilinear** | beliebig | Unterteilen ohne Glätten | OpenSubdiv „Bilinear"; entspricht Blenders altem „Simple"-Modus und Modos „Flat" |

**INTERPRETATION:** Für die Mirai/Silo/Wings-Linie ist Catmull-Clark gesetzt (alle drei nutzen quad-basierte
Unterteilung; Wings' Code nennt die Catmull-Clark-Arbeit von Patney et al. als Inspiration). Die Alternativen sind
Abgrenzung, keine Kandidaten.

---

## 4. Implementierungslandschaft (Frage 3)

### 4.1 OpenSubdiv

- **FAKT (OpenSubdiv-Doku):** Schichten: `Sdc` (Regeln, Creasing), `Vtr`/`Far` (Topologie-Verfeinerung, Stencil- und
  Patch-Tabellen), `Osd` (Auswertung auf CPU/GPU, Zeichnen mit Hardware-Tessellation). Uniforme und feature-adaptive
  Unterteilung werden unterstützt. Auswerter: CPU (single), TBB, OpenMP, CUDA, OpenCL, GL Compute, GL Transform Feedback,
  DX11, Metal.
- **FAKT (Blender-Commits 2015):** Der Transform-Feedback-Shader von OpenSubdiv deklariert `#version 410`, braucht also
  OpenGL 4.1; der Compute-Auswerter braucht OpenGL 4.3 (oder 4.2 + Erweiterung).
- **INTERPRETATION mit Bezug zur Referenz-Hardware:** Alle GPU-Pfade von OpenSubdiv liegen über OpenGL 3.3. Auf dem
  Referenz-PC kommen nur die CPU-Auswerter in Frage. Laut `REFERENCE_HARDWARE.md` §4 wäre jeder GPU-Pfad als Konflikt zu melden.
- **BEOBACHTUNG (PyPI, 2026-10-02):** Es gibt keine gepflegten Python-Bindings für OpenSubdiv auf PyPI. Das Paket
  `pyOpenSubdiv` (0.0.3, 2022) ist trotz Name eine reine Python-Catmull-Clark-Implementierung, keine Bindung. Ob die
  USD-Python-Bindings Teile von OpenSubdiv nutzbar machen, wurde **nicht** geprüft (OFFEN).
- **INTERPRETATION:** OpenSubdiv aus Python zu nutzen hieße, eine eigene native Bindung zu bauen oder zu übernehmen.
  Das wäre die erste kompilierte Abhängigkeit des Projekts, mit allen Fragen zu CPU-Befehlssätzen auf dem Q9550
  (`REFERENCE_HARDWARE.md` §2). Der Gewinn wäre Korrektheit bei Creases/Rändern und Austauschbarkeit mit anderen Tools.
- **OFFEN:** Lizenz von OpenSubdiv in dieser Session nicht geprüft.

### 4.2 Eigene CPU-Implementierung

- **BEOBACHTUNG:** Das Projekt ist reines Python mit pyglet, ohne NumPy in `src/` (`VIEWPORT_V02_RESEARCH.md` §19:
  NumPy nur dort, wo ein Benchmark echten Nutzen zeigt).
- **BEOBACHTUNG (Sandbox):** Eine naive Catmull-Clark-Stufe ist in reinem Python etwa 80 Zeilen. Zahlen in §5.
- **INTERPRETATION:** Uniformes Catmull-Clark mit glatten Regeln und einfachen Rändern ist gut verstanden und klein.
  Aufwendig sind Creases (besonders halbscharf), Grenzauswertung und Kantenfälle (nicht-manifold, Löcher, entartete Faces).
  Genau dort liegen Fehlerquellen, die OpenSubdiv bereits abdeckt — und die das Projekt erst brauchen würde, wenn Creases
  gewollt sind.

### 4.3 Uniform vs. feature-adaptiv

- **FAKT (Nießner, Loop, Meyer, DeRose 2012; OpenSubdiv):** Feature-adaptive Unterteilung verfeinert nur um irreguläre
  Stellen herum und zeichnet reguläre Bereiche als bikubische Patches über Hardware-Tessellation.
- **INTERPRETATION:** Hardware-Tessellation braucht OpenGL 4.0. Auf dem Referenz-PC bleibt nur **uniforme** Unterteilung
  (jede Stufe überall). Adaptiv wäre erst nach einem Hardwarewechsel ein Thema.

### 4.4 Stencils: Topologie einmal, Positionen oft

- **FAKT (OpenSubdiv-Doku):** Nach der Topologie-Verfeinerung erzeugt man eine `StencilTable`: Für jeden neuen Punkt eine
  Liste „Kontrollvertex × Gewicht". Positionen werden danach nur noch durch Anwenden dieser Tabelle berechnet; die
  Tabelle bleibt gültig, solange sich die Topologie (und die Crease-Werte) nicht ändert.
- **Analogie für Artists:** Die Stencil-Tabelle ist wie ein Skin-Weight-Setup: Jeder neue Punkt „hängt" mit festen Gewichten
  an ein paar Kontrollpunkten. Bewegt man Kontrollpunkte, folgt die Fläche ohne Neuberechnung des Aufbaus.
- **INTERPRETATION:** Das trennt die beiden Update-Arten sauber, die `VIEWPORT_V02_ARCHITECTURE.md` schon kennt:
  Positionsänderung (§5.2) = Tabelle anwenden; Topologieänderung (§5.4) = Tabelle neu bauen. Die Idee ist
  bibliotheksunabhängig und auch in reinem Python umsetzbar (§5 misst sie).

### 4.5 Inkrementell: nur neu rechnen, was sich ändert — wie Wings es macht

**BEOBACHTUNG (Wings-3D-Quellcode, `wings_proxy.erl`, `wings_subdiv.erl`):**
1. **Änderungserkennung:** `proxy_needs_update` vergleicht Kantentabelle, harte Kanten, Materialien, ID-Zähler und
   Spiegelzustand mit dem vorigen Stand. Gleich → nur Positionen neu (`inc_smooth`), sonst volle Neuberechnung.
   Das ist dieselbe Trennung wie in 4.4, ohne Stencil-Begriff.
2. **Während des Ziehens („split proxy"):** Die Faces um die bewegten Vertices werden bestimmt und **einmal um einen Ring
   erweitert**; für die Berechnung kommt **noch eine äußere Lage** dazu, damit die Unterteilung an der Grenze stimmt.
   Der Rest wird als statische Display-Liste einmal gezeichnet und während des Ziehens nicht angefasst. Spiegel-Faces und
   Löcher werden ausgenommen.
3. **Darstellung:** Getrennte Deckkraft für „stehende" und „bewegte" Proxies (`proxy_static_opacity`, `proxy_moving_opacity`).
4. **Stufen:** Standard ist **eine** Stufe auf der CPU. Höhere Stufen (bis 5) nur über OpenCL, mit Rückfall auf die CPU-Stufe,
   wenn der Speicher nicht reicht.

**INTERPRETATION:** Wings beweist im Alltag eines Modelers der Mirai-Linie genau das Muster „statisch + dynamischer
Bereich", das das Viewport-V02-Prinzip „update only what changed" für SubD bedeuten würde. Die Locality-Messung in §5
zeigt, warum es trägt.

### 4.6 Caching der abgeleiteten Geometrie (V1_CORE Frage 8)

**INTERPRETATION — es gibt drei verschiedene Dinge, die man cachen könnte, mit verschiedener Lebensdauer:**

| Was | Gültig bis | Kosten bei Neuberechnung |
|---|---|---|
| Verfeinerte **Topologie** (Faces der Stufe L, Eltern-Zuordnung) + Stencils | Topologie-, Crease- oder Stufenänderung | hoch (§5) |
| Verfeinerte **Positionen** und Normalen | jede Positionsänderung | mittel, lokal begrenzbar |
| **GPU-Puffer** | wie Positionen, aber Upload-gebunden | Upload-Größe |

Ob irgendetwas davon in History oder Datei landet, ist eine Architekturfrage. Aus Sicht dieser Research spricht nichts dafür,
abgeleitete Daten zu speichern: Sie sind jederzeit aus Control Mesh + Stufe (+ ggf. Creases) reproduzierbar (§7.3).

---

## 5. Performance auf der Referenz-Hardware (Frage 4)

### 5.1 Was gemessen wurde — und wo

**BEOBACHTUNG (Sandbox-Messung 2026-10-02, NICHT der Referenz-PC):** Python 3.12, ein CPU-Kern einer Cloud-Xeon @ 2,8 GHz.
Naive reine-Python-Implementierung, nur Positionen (keine Normalen, kein GPU-Upload). Das Wegwerf-Skript ist nicht Teil
des Repos.

**Volle Neuberechnung (Topologie + Positionen):**

| Mesh | Stufe | Quads | Vertices | Zeit |
|---|---|---|---|---|
| `head_basemesh` (324 Quads) | 1 | 1 296 | 1 298 | 11 ms |
| | 2 | 5 184 | 5 186 | 40 ms |
| | 3 | 20 736 | 20 738 | 180 ms |
| `Man_With_Shoes_basemesh` (926 Quads) | 1 | 3 704 | 3 706 | 31 ms |
| | 2 | 14 816 | 14 818 | 161 ms |
| | 3 | 59 264 | 59 266 | 488 ms |

**Stencil-Variante (Tabelle einmal bauen, dann nur anwenden):**

| Mesh | Stufe | Stencil-Einträge | Tabelle bauen | Alle Positionen anwenden | Neue Vertices, die von **einem** Kontrollvertex abhängen |
|---|---|---|---|---|---|
| head | 1 | 8 102 | 8 ms | 4 ms | 31 (2,4 %) |
| head | 2 | 54 998 | 65 ms | 28 ms | 205 (4,0 %) |
| head | 3 | 274 166 | 386 ms | 122 ms | 1 009 (4,9 %) |
| Man | 2 | 157 984 | 197 ms | 82 ms | 169 (1,1 %) |

### 5.2 Was daraus folgt — vorsichtig

- **BEOBACHTUNG:** Die Kosten wachsen pro Stufe etwa um Faktor 4 (wie die Face-Anzahl).
- **BEOBACHTUNG:** In reinem Python ist „alle Stencils anwenden" nicht dramatisch schneller als „alles neu rechnen"
  (head L2: 28 ms vs. 40 ms). Der eigentliche Gewinn liegt in der **Lokalität**: Ein bewegter Kontrollvertex beeinflusst
  bei Stufe 2 nur 1–4 % der neuen Vertices.
- **EINSCHÄTZUNG, nicht gemessen:** Ein Core 2 Quad Q9550 ist pro Kern deutlich langsamer als die Sandbox-CPU; ein Faktor
  2–4 ist plausibel, aber unbelegt. Damit lägen auf dem Referenz-PC schon **head Stufe 1 voll neu** (~20–45 ms) und erst recht
  Stufe 2 (~80–160 ms) über dem Ziel < 15 ms aus `VIEWPORT_V02_ARCHITECTURE.md` §1.
- **INTERPRETATION — was inkrementell sein *muss*, was nicht:**

| Ereignis | Häufigkeit | Muss inkrementell sein? |
|---|---|---|
| Vertex ziehen / Tweak / Transform-Drag | jeder Frame | **ja** — lokal (Wings-Muster, §4.5) |
| Kamera, Hover, Selektion | jeder Frame | **ja** — darf die SubD gar nicht anfassen (V02 §5.1/§5.3) |
| Topologie-Operation (Knife, Connect, Extrude-Commit) | einmal pro Aktion | nein — einmaliger Rebuild ist V02 §5.4 ohnehin |
| Undo/Redo | einmal pro Aktion | nein — aber Undo von Topologie = Rebuild (§7.3) |
| Stufe wechseln | selten | nein |
| Vorschau an/aus | selten | nein, wenn die Daten gecacht bleiben |

- **INTERPRETATION zur GPU:** Stufe 3 von `Man_With_Shoes` sind ~119 000 Dreiecke. Das ist für eine GeForce 9800 GTX kein
  Zeichenproblem. Engpass ist auf diesem PC die **Python-Arbeit pro Event**, wie in der Shading-Research schon festgestellt
  („Python-Arbeit pro Event > Extra-Pässe > Shader-Mathematik"). Der Upload kompletter Positions- und Normalpuffer bei
  Stufe 3 (~20 000 Vertices × 24 Byte ≈ 0,5 MB) ist zu messen, nicht zu schätzen.
- **OFFEN, nur durch Messung auf dem Referenz-PC:** reale Zeiten für Stufe 1–2 inkl. Normalen und Upload; ob NumPy für
  das Anwenden der Stencils dort einen echten Unterschied macht (das wäre ein Benchmark im Sinne von V02-Research §19).

### 5.3 Realistisches Budget — Einschätzung

**EINSCHÄTZUNG, nicht gemessen:** Mit reinem Python und lokalem Update scheint auf dem Referenz-PC eine **interaktive Stufe 1–2**
für Meshes in der Größe der Beispielmeshes erreichbar; Stufe 3 eher nur als ruhende Ansicht. Das ist eine Hypothese für
eine Messung (H-PERF-1), keine Zusage.

---

## 6. Viewport (Frage 5)

### 6.1 Käfig über der Fläche zeichnen

**FAKT, nach Tool:**
- **Wings:** Kantendarstellung im Proxy wählbar: nur Käfig / einige Kanten / alle Kanten (`proxy_shaded_edge_style`,
  BEOBACHTUNG Code).
- **3ds Max:** „Show Cage" zeigt den unveränderten Käfig in zwei Farben; „Isoline Display" zeigt statt aller neuen Kanten
  nur die Linien, die den Original-Kanten entsprechen, für weniger Unruhe.
- **Blender (ältere Doku):** Option, die Drahtgitter-Anzeige auf die ursprünglichen Käfigkanten zu beschränken, weil der
  Edit-Modus sonst mit Linien überladen ist, die es „nicht wirklich gibt".
- **Maya:** „Display Subdivisions" schaltet die Unterteilungskanten auf der Vorschau an/aus.

**INTERPRETATION:** Drei Darstellungen sind üblich: (a) Käfig als Drahtgitter + glatte Fläche schattiert, (b) Isolinien
(Originalkanten *auf* der Fläche), (c) alle Unterteilungskanten. (b) setzt voraus, dass man weiß, welche neuen Kanten aus
welcher alten Kante stammen — bei Catmull-Clark ist das exakt bekannt (jede alte Kante zerfällt in zwei Halbkanten).

### 6.2 Verdeckung: der Käfig verschwindet in der Fläche

- **FAKT (Blender-Doku, ältere Version):** Ohne „Edit Cage" liegen manche Käfig-Vertices unter der unterteilten Fläche begraben.
- **INTERPRETATION:** Bei konvexen Formen liegt der Käfig außen, bei konkaven Stellen *innerhalb* der Fläche. Ein normaler
  Tiefentest versteckt dann Käfigteile. Das trifft genau die X-Ray-/Hidden-Line-Techniken aus
  `VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md` §4.5 (E2 „Kanten/Vertices ohne Tiefentest", E3 „verdeckte Kanten gedimmt").
  SubD macht diese Techniken vom Komfort- zum Pflichtthema.

### 6.3 Normalen und Subdivision Shading

- **BEOBACHTUNG (Repo):** `DerivedGeometry` berechnet Vertex-Normalen flächengewichtet aus den Faces (`src/viewport/derived.py`).
  Auf einem unterteilten Mesh ergibt das eine Annäherung, die an Polen leichte Unruhe zeigen kann.
- **FAKT (Literatur):** Grenznormalen lassen sich wie Grenzpositionen über Tangenten-Masken direkt aus der Nachbarschaft
  berechnen (OpenSubdiv `limit masks`). „Subdivision Shading" (Alexa & Boubekeur 2008; Erweiterung auf Semi-Sharp Creases,
  MDPI Computers 2023 — beide schon in `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §4.4/§16 Quellen) unterteilt die Normalen
  mit und glättet so Shading-Artefakte an Polen ohne mehr Geometrie.
- **INTERPRETATION:** Es gibt drei Normalen-Strategien mit steigender Treue: Flächen-gemittelt (vorhanden), Grenznormalen,
  Subdivision Shading. Für Formwahrnehmung ist das relevant, weil ein Teil der „Topologiefehler", die Artists sehen,
  Normalenartefakte sind (`MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §7.1). Was davon nötig ist, entscheidet ein visueller Vergleich,
  nicht Recherche (T-SUBD-3).
- **Bezug Shading-Lab:** Zebra (B6) und Cavity (B3) aus der Shading-Research würden auf einer SubD-Fläche genau die
  Unterschiede zwischen diesen Normalen-Strategien sichtbar machen.

### 6.4 Picking: auf dem Käfig oder auf der Fläche?

**FAKT, nach Tool:**
- **Silo:** Ist der Käfig ausgeblendet, sieht es so aus, als wähle man Faces der inneren Fläche; tatsächlich wird die
  zugehörige Face des äußeren Meshes gewählt.
- **Maya:** Im Modus „Cage + Smooth" ist einstellbar, ob man auf dem Käfig, auf der Fläche oder auf beiden auswählt. Im
  Modus „Smooth Mesh" wählt und editiert man direkt auf der Vorschau; Änderungen werden auf das Original-Mesh zurückgespielt;
  der Manipulator erscheint dabei an der Position der Komponente **am Original**.
- **Blender:** „On Cage" passt den Edit-Käfig an das Modifier-Ergebnis an (Käfig-Vertices erscheinen auf der Fläche).
  **BEOBACHTUNG (Anwenderforum):** Nutzer berichten, dass das Knife-Werkzeug dann „woanders" schneidet und man nicht editiert,
  was man sieht; Vertices verschieben gehe, Knife nicht zuverlässig.

**INTERPRETATION — was technisch einfach und was schwer ist:**
- **Faces:** Bei Catmull-Clark gehört jedes neue Quad zu genau einer Eltern-Face. Ein Treffer auf der Fläche lässt sich
  exakt einer Kontroll-Face zuordnen. Einfach.
- **Vertices:** Jeder Kontrollvertex hat genau einen Nachfolger (den verschobenen Vertex Point) bzw. eine Grenzposition.
  Hover/Pick auf dieser Position ist exakt zuordenbar. Einfach.
- **Kanten:** Jede Kontrollkante hat zwei Halbkanten-Nachfolger (die Isolinie aus 6.1). Zuordenbar.
- **Positionen auf einer Face** (Knife-Klickpunkt, „face points" aus WP-KNIFE-01 S3): Ein Klickpunkt auf der glatten Fläche
  hat **keinen** eindeutigen Ort auf der flachen Kontroll-Face — die beiden Flächen liegen räumlich woanders. Man kann über die
  Parametrisierung der Unterfläche zurückrechnen, aber das Ergebnis ist eine *Abbildung*, nicht derselbe Punkt. Genau hier
  entsteht die Blender-Verwirrung.
- **Manipulator-Ort:** Maya zeigt bewusst den Ort am Original. Ein Gizmo „auf der Fläche" würde dort stehen, wo sich der
  Kontrollpunkt gar nicht befindet.

**INTERPRETATION:** Picking auf der Fläche ist für Vertex/Edge/Face gut lösbar; für Positions-Werkzeuge (Knife-Punkte,
Snapping auf Flächen) entsteht eine echte Bedeutungsfrage: Meint der Artist den Punkt, den er auf der glatten Form sieht,
oder einen Punkt am Käfig? Das ist Product Truth (OF-7, T-SUBD-4).

### 6.5 Einordnung in das Viewport-V02-Update-Modell

**INTERPRETATION:** `VIEWPORT_V02_ARCHITECTURE.md` §6 kennt Update-Kategorien (Kamera, Position, Selektion, Topologie).
SubD bringt zwei neue Auslöser dazu, die heute keine Kategorie haben: **Stufe geändert** und — falls es Creases gibt —
**Schärfe geändert**. Beide verhalten sich wie eine Topologieänderung der abgeleiteten Daten, obwohl sich das Control Mesh
topologisch nicht ändert. Das ist eine Beobachtung für spätere Architekturarbeit, keine Festlegung.

---

## 7. Zusammenspiel mit bestehenden Systemen (Frage 6)

### 7.1 Topologie-Operationen (Knife, Connect, Extrude, Löschen, Dissolve)

| Operation | Wirkung auf die SubD-Form | Evidenz |
|---|---|---|
| **Connect / Split / Edge Loop einfügen** | Neue Kante nah an einer bestehenden → die Fläche wird dort straffer, Rundung „schmilzt" weniger weg (Support-Loop-Effekt) | KONSENS; `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §15.7/§15.8 |
| **Knife über eine Fläche** | Wie oben, plus möglicher Pol, wo der Schnitt in einer Face endet (Dreieck/N-Gon → Pol, §3.1) | FAKT (Pol-Regel) |
| **Extrude** | Erzeugt eine neue Kantenreihe an der Basis; Basis wird unter SubD schärfer, je näher die neue Reihe an der alten liegt | KONSENS |
| **Faces löschen** | Erzeugt einen Rand → Randregeln (§3.2), der Rand zieht sich als Kurve | FAKT (Randregel) |
| **Dissolve (Kante entfernen, Faces verschmelzen)** | Erzeugt ein N-Gon → unter SubD ein Pol in seiner Mitte; die Form bleibt geschlossen | FAKT (§3.1) |
| **Face mit Loch** | Für SubD nicht definiert, müsste überbrückt werden | `FACE_HOLES_DISCOVERY.md` |

- **INTERPRETATION — der Kern für Artists:** „Geometrie hinzufügen" ist unter SubD nie neutral. Jede zusätzliche Kante
  verändert die Form, auch wenn sie genau in der alten Fläche liegt. Ohne Vorschau ist diese Formänderung unsichtbar —
  das ist die Hypothese aus `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §7.3 („Der Wert eines Topologiewerkzeugs hängt von der
  Sichtbarkeit seiner Konsequenz ab").
- **Silo „Refine Control Mesh"** (Modell D) ist ebenfalls eine Topologie-Operation: Danach gilt das bisherige Control Mesh
  nicht mehr; laut Silo-Doku kann man nach Änderungen nur per Undo zurück.
- **Provenienz (ARCH-02):** Refine/Bake erzeugt aus *jeder* Kontroll-Face mehrere neue Faces mit exakt bekannter Herkunft
  (Eltern-Face, Eltern-Kante, Eltern-Vertex). Das ist der seltene Fall einer Topologie-Operation mit vollständiger,
  regelhafter Provenienz (INTERPRETATION).

### 7.2 Symmetry Lab und Naht

- **FAKT (Symmetry-Research):** Andere DCCs haben mit SubD und Spiegelung Nahtprobleme: Houdini (gespiegelte Hälften reißen
  beim Unterteilen auf, Naht-Punkte müssen exakt auf die Ebene), Blender (Reihenfolge im Modifier-Stack: Mirror vor
  Subdivision), Wings (`mirror_flatten` projiziert nach Smooth/Subdivide die Naht-Vertices auf die Ebene aus dem Vorher-Zustand),
  ZBrush (nach Subdivide Rückfall auf Weltsymmetrie).
- **INTERPRETATION für Mirai-Bastel:** Die meisten dieser Probleme entstehen bei einer *virtuellen* Spiegelhälfte. Mirai-Bastel
  hat beide Hälften als echte Geometrie (Context Check 0.3). Dann ist die SubD eines symmetrischen Meshes automatisch
  symmetrisch und ohne Lücke — **solange** Topologie und Positionen symmetrisch sind. Was bleibt:
  - Naht-Vertices minimal neben der Ebene erzeugen in der SubD eine sichtbare Delle oder Rippe entlang der Mitte.
    SubD macht solche Ungenauigkeiten deutlicher sichtbar als das grobe Mesh (HYPOTHESE, mit `subd_cube`/`head_basemesh`
    prüfbar).
  - Die Symmetry-Lab-Erfahrung, dass Fan-Triangulierung sichtbar asymmetrisch schattiert (`experiments/symmetry_lab/README.md`),
    gilt für unterteilte Flächen genauso; mit nur Quads ab Stufe 1 und konsistenter Diagonale wird es eher besser.
  - Refine/Bake (Modell D) erzeugt neue Elemente auf beiden Seiten. Die Korrespondenz müsste mitgeführt oder neu bestimmt
    werden (Symmetry-Research: topologische Korrespondenz ist nicht topologie-änderungsfest).

### 7.3 History / Undo

- **BEOBACHTUNG (Repo):** Undo arbeitet mit vollständigen Vorher/Nachher-Zuständen des Meshes (`MeshStateCommand`,
  `export_state()`/`load_state()`; die `SymmetryDefinition` reist schon mit).
- **INTERPRETATION:**
  - Abgeleitete Geometrie muss nicht in die History; sie ist aus dem Zustand reproduzierbar. Das passt zu „Control Mesh autoritativ".
  - Versteckte Kosten: Jedes Undo/Redo einer Topologie-Operation löst einen kompletten SubD-Rebuild aus (§5). Bei Stufe 2–3 auf
    dem Referenz-PC kann Undo dadurch spürbar zögern (HYPOTHESE, messbar).
  - Falls es Creases gibt, sind sie Teil des Control-Mesh-Zustands (sie verändern die Form) und müssten mit Undo zurückgehen.
    Wie sie gespeichert werden, ist bewusst nicht Teil dieser Research.
  - Ist die **Stufe** Dokumentzustand (mit Undo) oder Ansichtszustand (wie Kamera, ohne Undo)? Unterschiedlich gelöst:
    Blender speichert Stufen im Modifier (Datei), Maya im Shape-Node, Silo per Objekt-Befehl. OFFEN (OF-3).

### 7.4 Deformationskette (Morph, Skin)

- **BEOBACHTUNG (Repo):** `src/core/mesh.py` hält Raum für Base → Morph → Skin → Subdivision — SubD **zuletzt**.
- **FAKT (Mirai 1999):** Das Kontrollvolumen wirkte wie ein Lattice-Deformer für Posen und Morph Targets, die Face-Anzahl blieb
  unter Deformation stabil.
- **KONSENS:** Produktionsübliche Reihenfolge ist „Käfig deformieren, dann unterteilen". Gewichte und Morphs leben dann nur auf
  den wenigen Kontrollvertices.
- **INTERPRETATION:** Die dokumentierte Reihenfolge, Mirai und die Produktionspraxis zeigen in dieselbe Richtung. Konsequenz:
  Jeder Frame einer Animation oder Morph-Slider-Bewegung ist für die SubD ein „alle Positionen geändert"-Ereignis — nicht
  lokal. Das ist ein anderes Lastprofil als Modellieren (dort lokal, §5) und spricht für Stencils (§4.4) statt lokaler
  Ausschnitte. Für die heutige Research nur ein Hinweis, Morph/Skin sind später.
- **Offene Verbindung:** `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` L-Q7 (Creases unter Deformation vs. Stützkanten) gehört an die
  Grenze zu `CHARACTER_SYSTEMS_RESEARCH.md` und bleibt dort offen.

### 7.5 Stable IDs

**INTERPRETATION:** Solange die abgeleitete Fläche nie editiert wird (Modelle A, B, C), brauchen ihre Elemente **keine**
stabilen IDs. Sie sind Wegwerfdaten, adressiert über „Eltern-Element + Position im Schema". Erst Modell D (Refine) macht aus
abgeleiteten Elementen echte — dann gelten alle ID- und Provenienzregeln des Core.

---

## 8. DCC-Vergleich (Frage 7)

| Tool | Ein/Aus und Stufen | Käfig-Anzeige | Wo wird editiert | Creases | Backen / Teilweise |
|---|---|---|---|---|---|
| **Mirai** (1999) | OFFEN | Kontrollvolumen + Derived Surface gleichzeitig (Abbildungsbeschreibung) | am Kontrollvolumen, Fläche live (FAKT); direkt auf der Fläche: **kein Beleg** | OFFEN | mehrere LOD aus dem Kontrollvolumen (FAKT) |
| **Silo** | `C` Subdivide / `V` Unsubdivide, mehrfach = Stufen (FAKT) | Käfig als Drahtgitter, ausblendbar (FAKT) | am Käfig; mit ausgeblendetem Käfig *scheinbar* auf der Fläche (FAKT) | Crease Edges; nicht exportierbar ohne Refine (FAKT) | Refine Control Mesh Shift+C (FAKT); Partial Subdivide (FAKT) |
| **Wings 3D** | Tab = Workmode (flach/glatt schattiert); Shift+Tab = Quick Smoothed Preview für alle Objekte; „Toggle Proxy Mode" für Auswahl (BEOBACHTUNG Code) | Kantenstil Käfig / einige / alle; Deckkraft stehend/bewegt (BEOBACHTUNG Code) | am Käfig, Proxy live (BEOBACHTUNG Code) | Hard Edges wirken als scharfe Kanten (BEOBACHTUNG Code) | „Smooth" = destruktive Catmull-Clark (FAKT); auf Face-Auswahl möglich (KONSENS) |
| **Blender** | Modifier; Viewport- und Render-Stufe; Ctrl+1… (FAKT) | „Optimal Display"/Isolinien (ältere Doku, FAKT) | am Käfig; „On Cage" zeigt Käfig auf der Fläche (FAKT) — Knife-Verwirrung (BEOBACHTUNG Forum) | gewichtete Edge-/Vertex-Creases (FAKT) | Modifier anwenden (KONSENS); Multires für Editieren der feinen Fläche (FAKT) |
| **Maya** | `1`/`2`/`3`, Page Up/Down (FAKT) | Modus 2: Käfig + Fläche; Modus 3: nur Fläche (FAKT) | Modus 2: wählbar Käfig/Fläche/beide; Modus 3: auf der Fläche, zurückgespielt aufs Original, Manipulator am Original (FAKT) | Crease-Werkzeug, OpenSubdiv-CC-Methode (FAKT/KONSENS) | Convert Smooth Mesh Preview to Polygons (FAKT) |
| **3ds Max** | NURMS in Editable Poly, Iterations Display/Render; MeshSmooth/TurboSmooth/OpenSubdiv-Modifier (FAKT/KONSENS) | Show Cage (zweifarbig), Isoline Display (FAKT) | am Käfig (FAKT) | OpenSubdiv-Modifier: Crease-Methode Normal/Chaikin, Randoptionen (FAKT) | Modifier kollabieren (KONSENS) |
| **Modo** | Tab-Umschaltung (KONSENS) | OFFEN | am Käfig (KONSENS) | Edge Creasing mit Pixar-CC (FAKT) | Subdivide-Befehl mit SDS / Catmull-Clark / Flat; UnSubdivide (FAKT) |
| **Nendo** | OFFEN | OFFEN | OFFEN | OFFEN | OFFEN |

**BEOBACHTUNG über alle Tools:**
- Kein untersuchtes Tool editiert die abgeleitete Fläche als eigene Wahrheit, ohne sie vorher zu backen. Selbst Maya Modus 3
  spielt Änderungen auf das Original zurück.
- „Am Käfig arbeiten, Fläche live sehen" (Modell B) ist der gemeinsame Kern aller Modeler der Mirai/Silo/Wings-Linie.
- Die schnellen Modeler (Silo, Wings) haben **eine** Taste für die Vorschau; die großen Pakete verteilen die Bedienung auf
  Modifier, Attribute und mehrere Tasten.
- **Tasten-Notiz:** Silo nutzt `C` für Subdivide; Mirai-Bastel nutzt `C` kontextuell für Split/Connect/Knife (AD-017).
  Wings nutzt Tab für Schattierung. Nur festgehalten, nicht bewertet.

---

## 9. Synthese — die Achsen des Entscheidungsraums

Keine Empfehlung. Das sind die Achsen, auf denen später entschieden werden müsste, mit dem Typ der Entscheidung.

| Achse | Optionen (aus §2–§8) | Wer entscheidet |
|---|---|---|
| **D1 Intent-Modell** | A Vorschau / B Käfig + live / C auf Fläche greifen / D Backen / E Teilweise — kombinierbar | Artist (Intent, Product Truth) |
| **D2 Wo wird gegriffen** | nur Käfig / Käfig oder Fläche / beide | Artist (Product Truth), nach Test |
| **D3 Schärfe** | keine / harte Kanten / halbscharf / nur Support Loops | Artist (Intent); Speicherung: Architektur |
| **D4 Randverhalten** | glatt / Kanten scharf / Kanten + Ecken scharf | Artist (Product Truth), visuell |
| **D5 Auswertung** | eigene Python-Implementierung / OpenSubdiv nativ / später GPU | Architektur, gebunden an Referenz-Hardware |
| **D6 Update-Körnung** | voll / Stencils / lokal (Wings-Muster) / Kombination | Agent-Domäne (Messung) |
| **D7 Darstellung** | Käfig-Drahtgitter / Isolinien / alle Kanten; Normalen-Strategie | Artist (visuell) + Agent (Kosten) |
| **D8 Stufe als Zustand** | Dokument / Ansicht / pro Objekt / global | Architektur (berührt ARCH-01) |

---

## 10. Offene Fragen

| # | Frage | Art |
|---|---|---|
| OF-1 | Gibt es eine Quelle für „Mirai editierte die abgeleitete Fläche direkt"? | Recherche / Manu-Erinnerung |
| OF-2 | Will Manu Stufen wechseln, oder genügt eine feste Stufe, die glatt aussieht? | Product Truth → T-SUBD-2 |
| OF-3 | Ist die Stufe Dokument- oder Ansichtszustand? | Architektur |
| OF-4 | Rundet sich eine offene Ecke, oder bleibt sie stehen? | Product Truth, visuell |
| OF-5 | Schärfe als Kanteneigenschaft (Crease) oder als Geometrie (Support Loops)? | Intent |
| OF-6 | Reale Zeiten auf dem Referenz-PC für Stufe 1–2 inkl. Normalen und Upload | Messung (Agent) |
| OF-7 | Meinen Positions-Werkzeuge (Knife-Punkt, Snapping) auf der glatten Fläche den sichtbaren Punkt oder einen Käfigpunkt? | Product Truth → T-SUBD-4 |
| OF-8 | Welche Normalen-Strategie braucht Formwahrnehmung wirklich? | Product Truth, visuell → T-SUBD-3 |
| OF-9 | Lizenz und Python-Anbindung von OpenSubdiv; USD-Python-Pfad | Recherche (Agent) |
| OF-10 | Wie sichtbar sind Naht-Ungenauigkeiten unter SubD auf den Symmetry-Testmeshes? | Messung/Probe (Agent) |
| OF-11 | Abgleich mit §10 der Research-Dokumente Geometrie-Entfernung / Geometrie-Hinzufügen, sobald sie im Repo sind | Recherche (Agent) |
| L-Q3, L-Q7 | aus `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` — weiterhin offen | — |

---

## 11. Vorbereitete Artist-Tests (nicht jetzt fragen)

*Lab: [`experiments/subdivision_lab/`](../../../experiments/subdivision_lab/README.md) (WP-SUBD-LAB-01 Slice 1) macht T-SUBD-1 und T-SUBD-2 spielbar. Stand: gebaut, nicht Artist-validiert.*

Alle Tests setzen eine spielbare SubD-Vorschau voraus. **Ob dafür ein Lab gebaut wird, ist eine Prioritätsentscheidung des
Artists** — dieselbe Bedingung wie bei `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` Kandidat L4. Jede Variante wird mit
KEEP / ITERATE / REJECT / UNKNOWN bewertet; Dauer je wenige Minuten.

| Test | Frage | Aufbau | Bezug |
|---|---|---|---|
| **T-SUBD-1 — Käfig, Fläche oder beides** | D1/D2, L-Q3 | `head_basemesh` mit Stufe 2; drei Ansichten umschaltbar: nur Käfig / Käfig-Drahtgitter + Fläche / nur Fläche mit Isolinien. Eine kleine Formkorrektur an der Wange. Beobachtet wird, welche Ansicht Manu stehen lässt. | kombiniert L4 und E3 |
| **T-SUBD-2 — Wie glatt ist glatt genug** | OF-2 | Dieselbe Pose bei Stufe 1, 2, 3 nebeneinander, gleiche Beleuchtung. Frage: Ab welcher Stufe stört nichts mehr beim Modellieren? | Budget §5.3 |
| **T-SUBD-3 — Normalen** | OF-8 | Stufe 1 mit (a) heutigen Flächen-Normalen, (b) Grenznormalen. Zebra/Cavity optional. Auf einen Pol im Gesicht zoomen. | §6.3, Shading-Lab |
| **T-SUBD-4 — Wo landet der Knife-Punkt** | OF-7 | Fläche ohne Käfig. Ein Knife-Klick; Variante (a) Punkt am Käfig unter der Klickstelle, (b) Punkt so gewählt, dass die neue Kante auf der Fläche durch die Klickstelle läuft. | §6.4, Blender-Befund |
| **T-SUBD-5 — Rand und Ecke** | OF-4 | Ein offenes Plane und ein offener Zylinder in den drei Randvarianten. | §3.2 |
| **T-SUBD-6 — Schärfe** | OF-5 | Eine Kante dreimal: Support Loop nah, Support Loop weit, harte Kante. Danach dieselbe Form einmal verbiegen. | §3.4, L-Q7 |

**Bewusst nicht als Frage gestellt:** Algorithmus- und Bibliothekswahl, Update-Strategie, Caching. Das ist Agent- bzw.
Architekturdomäne.

---

## 12. Doku-Pflege, die aus dieser Research folgt

- `docs/architecture/V1_CORE.md` §10: Der Satz über den Prototyp beschreibt einen Stand, den es im Repository nie gab.
  Vorschlag (englisch, wie die Datei):
  *„No Catmull-Clark implementation exists in the repository. An early prototype referred to by an earlier draft of this
  section was never committed (see `docs/research/subdivision/SUBDIVISION_SURFACES_RESEARCH.md` §0.2). Current SubD research:
  `docs/research/subdivision/`."*
  Das ist eine Faktenkorrektur, keine Architekturänderung.
- `docs/research/subdivision/README.md`: vom Stub zum Einstieg dieses Bereichs.
- `docs/research/README.md`: Eintrag „Subdivision" ergänzen.
- **Nicht** geändert: Artist-Toolbox §11 (Status bleibt `[ ]`), `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` (wird nur verlinkt),
  Roadmap (keine neue Priorität ohne Artist).

---

## 13. Quellen

**Repository (gelesen auf `main` @ `4631c33`):** siehe Tabelle §0.1.

**Quellcode:**
- Wings 3D, https://github.com/dgud/wings — `src/wings_proxy.erl` (`proxy_needs_update`, `split_proxy`, `update_dynamic`),
  `src/wings_subdiv.erl` (`smooth`, `inc_smooth`), `src/wings_cc.erl` (OpenCL-Proxy, harte Kanten), `src/wings_view.erl`,
  `src/wings_hotkey.erl`, `src/wings_pref.erl`, `src/wings_pref_dlg.erl`. Gelesen 2026-10-02.

**Hersteller-Dokumentation:**
- Nevercenter Silo — Subdivision Surfaces Tutorial: https://nevercenter.com/silo3d/Tutorials/Subdivision_Surfaces/Subdivision_Surfaces.html
- Nevercenter Silo — Quick Start Guide: https://nevercenter.com/silo/support/manual/quickstart/
- Blender Manual — Subdivision Surface Modifier: https://www.blender.org/manual/en/modeling/modifiers/generate/subdivision_surface.html
- Blender Wiki (2.6) — Subsurf Modifier, Edit Cage: https://wiki.blender.jp/Doc:2.6/Manual/Modifiers/Generate/Subsurf
- Blender-Commits zu OpenSubdiv/GPU-Subdivision (GL-Versionen, eigene Compute-Shader): https://projects.blender.org/archive/blender-archive/commits/commit/5c682a901b2ae9acf656f19e5f9b470d957d71cc/intern/opensubdiv
- Autodesk Maya — Smooth Mesh Preview: https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Modeling/files/GUID-FF35F773-1FC0-4EBA-A64C-6199375F489A.htm
  und https://help.autodesk.com/cloudhelp/2019/ENU/Maya-Modeling/files/GUID-BF4C21CB-C149-449F-925D-5456B1D96EB7.htm
- Autodesk 3ds Max — Subdivision Surface Rollout (NURMS, Show Cage, Isoline): https://help.autodesk.com/cloudhelp/2016/ENU/3DSMax/files/GUID-642809FB-1C98-4960-8689-24B8108F3B10.htm
- Autodesk 3ds Max — OpenSubdiv Modifier: https://help.autodesk.com/cloudhelp/2015/ENU/3DSMax/files/GUID-AC9DDAB2-52E4-482A-B245-F5C30CC45544.htm
- Foundry Modo — Subdivide: https://learn.foundry.com/modo/content/help/pages/modeling/edit_geometry/subdivide.html
- OpenSubdiv — Osd Overview: https://graphics.pixar.com/opensubdiv/docs/osd_overview.html ;
  Sdc Overview: https://graphics.pixar.com/opensubdiv/docs_3x_alpha/sdc_overview.html ;
  Release 3.1: https://graphics.pixar.com/opensubdiv/docs/release_31.html ;
  `Sdc::Crease`: https://graphics.pixar.com/opensubdiv/docs/doxy_html/a01312.html

**Fachliteratur (Standardreferenzen, Inhalt in dieser Session nicht neu nachgelesen):**
- E. Catmull, J. Clark: *Recursively generated B-spline surfaces on arbitrary topological meshes*, CAD 10(6), 1978.
- D. Doo, M. Sabin: *Behaviour of recursive division surfaces near extraordinary points*, CAD 10(6), 1978.
- C. Loop: *Smooth Subdivision Surfaces Based on Triangles*, MS Thesis, University of Utah, 1987.
- M. Halstead, M. Kass, T. DeRose: *Efficient, Fair Interpolation using Catmull-Clark Surfaces*, SIGGRAPH 1993.
- J. Stam: *Exact Evaluation of Catmull-Clark Subdivision Surfaces at Arbitrary Parameter Values*, SIGGRAPH 1998.
- T. DeRose, M. Kass, T. Truong: *Subdivision Surfaces in Character Animation*, SIGGRAPH 1998.
- M. Alexa, T. Boubekeur: *Subdivision Shading*, ACM TOG 27(5), SIGGRAPH Asia 2008.
- M. Nießner, C. Loop, M. Meyer, T. DeRose: *Feature-Adaptive GPU Rendering of Catmull-Clark Subdivision Surfaces*, ACM TOG 31(1), 2012.
- Peters/Reif (Stetigkeit an Extraordinary Vertices) und *Subdivision Shading … with Semi-Sharp Creases* (MDPI Computers 12(4), 2023):
  siehe Quellen in `MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md`.

**Anwender / Community (KONSENS bzw. BEOBACHTUNG):**
- Wings-Forum, Quick Smoothed Preview: https://www.wings3d.com/forum/showthread.php?tid=1411
- Wings-Forum, OpenCL-Proxy: https://wings3d.com/forum/printthread.php?tid=1521
- Steam-Community, Blender Knife mit „Adjust edit cage": https://steamcommunity.com/app/365670/discussions/0/3183345000082533639
- Guerrilla CG, Subdivision Surfaces: https://vimeo.com/2450612

**Paketindex:**
- PyPI `pyOpenSubdiv` 0.0.3 (reine Python-Catmull-Clark, keine Bindung), geprüft 2026-10-02.
