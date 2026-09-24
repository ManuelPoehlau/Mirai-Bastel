# Symmetrie-Korrespondenz nach Topologie-Operationen — Deep Dive

**Status:** Discovery / Research. **Keine** Architekturentscheidung, **keine** Empfehlung für Mirai-Bastel.
**Datum:** 2026-09-24
**Ort (vorgeschlagen):** `docs/research/symmetry/SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md`
**Basis:** [`EDIT_MODE_SYMMETRY_RESEARCH.md`](EDIT_MODE_SYMMETRY_RESEARCH.md) (erster unabhängiger Durchgang, unverändert). Dieses Dokument vertieft genau eine Frage daraus (dort §5, §7 Punkt 3) und wiederholt die Grundlagen nicht.
**Modus (M5):** Discovery

> Unabhängiger Research-Durchgang. Vor längerer Diskussion unverändert archivieren (AGENTS.md §6).

---

## 0. Fragestellung und Kennzeichnung

**Untersucht wird ausschließlich:** Wie erhalten, aktualisieren oder invalidieren DCCs ihre Symmetrie-Korrespondenz, wenn eine Operation die **Topologie** verändert — konkret Extrude, Inset, Bevel, Loop Insert, Knife, Connect, Delete?

Drei Teilfragen:

1. **Neue Partner:** Wie wird für neu entstandene Elemente ein Gegenstück gefunden?
2. **Invalidierung:** Wann wird Symmetrie deaktiviert oder als ungültig markiert?
3. **Inkrementell vs. Neuberechnung:** Wird die Korrespondenz nachgeführt oder neu aufgebaut?

Markierungen wie im Basisdokument: **[FAKT]**, **[FAKT·Code]** (selbst im Quellcode gelesen — hier Blender und Wings 3D), **[ANWENDER]**, **[INTERPRETATION]**, **[SCHLUSS]**, **[OFFEN]**. Quellen in §9 als `[S#]`.

---

## 1. Kurzantwort

**[SCHLUSS] Kein untersuchtes System führt eine Korrespondenz-Tabelle inkrementell durch Topologie-Operationen nach.** In keiner Doku, keinen Release Notes und in keinem der beiden gelesenen Quellcodes fand sich ein Mechanismus der Art „Operation X erzeugt Element n und meldet: Partner ist m". Stattdessen zeigen sich drei andere Strategien:

| Strategie | Idee | Beispiele |
|---|---|---|
| **A — Korrespondenz überflüssig machen** | Die zweite Hälfte existiert nicht als Daten. Es muss nur die **Naht** durch jede Operation getragen werden, nicht die Partner. | Wings Virtual Mirror (Naht-Fläche wird *pro Operation* von Hand gepflegt), Mirror-Modifier/-Generatoren |
| **B — Gespiegelt ausführen, danach neu berechnen** | Symmetrie wird *vor* der Operation auf die Auswahl angewandt, die Operation läuft auf beiden Seiten, danach wird die Korrespondenz aus dem neuen Netz neu bestimmt. | Maya („selection-based"), C4D ab 2023 (Tools einzeln integriert) |
| **C — Bei Bedarf neu berechnen, mit billigem Verfallstest** | Die Korrespondenz ist ein Cache. Ein einfacher Test entscheidet, ob er verworfen wird. | Blender (Zählervergleich Vertices/Edges), ZBrush (Subdivide → zurück auf Weltsymmetrie) |

**Wann Symmetrie abschaltet [SCHLUSS]:** fast überall dann, wenn die **deklarierte Naht** berührt wird (Maya: jede Änderung an Seam-Edges [S1]; Wings: Naht-Fläche verschwindet [Code]; ZBrush: Unterteilung [S6]) — nicht dann, wenn Partner fehlen. Fehlende Partner führen fast überall stattdessen zu **partieller Symmetrie**: Das betroffene Element wird einfach nicht gespiegelt.

**Wie neue Partner gefunden werden [SCHLUSS]:** gar nicht direkt. Neue Elemente bekommen ihren Partner nur, weil die *gespiegelte Ausführung* das Gegenstück gleichzeitig erzeugt hat und die anschließende Neuberechnung beide als symmetrisch erkennt. Ist die Operation nur einseitig gelaufen (Tool nicht symmetrie-fähig, Symmetrie aus, Operation auf der Naht), hat das neue Element **keinen** Partner — und bekommt auch keinen.

---

## 2. Zwei grundverschiedene Ausführungsmodelle

[INTERPRETATION] Bevor man über Korrespondenz-Pflege spricht, muss man trennen, **wie die Operation selbst gespiegelt wird**. Die Quellen zeigen zwei Modelle:

**2a — Gespiegelte Auswahl (Maya, C4D).** Die Symmetrie erweitert die *Auswahl*: Maya beschreibt Symmetrie ausdrücklich als auswahlbasiert — die Gegenkomponenten werden in die Selektion aufgenommen, sodass auswahlbasierte Operationen symmetrisch wirken [S2]. Die Operation (z. B. Extrude) weiß nichts von Symmetrie; sie bekommt einfach eine beidseitige Auswahl. C4D beschreibt ebenfalls eine „virtuelle Selektion", die gespiegelt angezeigt und vom Tool mitverarbeitet wird, aber nicht gespeichert ist [S4].

- Vorteil [INTERPRETATION]: Jedes auswahlbasierte Tool wird „automatisch" symmetrisch.
- Grenze: Tools, die nicht auf einer Auswahl arbeiten, sondern auf **Cursor-Pfaden** (Knife, Multi-Cut, Loop-Insert per Hover, Polygon Pen), brauchen eine eigene gespiegelte Eingabe. Genau diese Tools tauchen in den Einschränkungen und Nutzerberichten auf (§4).

**2b — Gespiegelte Wirkung durch Konstruktion (Wings, Modifier).** Es gibt nur eine Hälfte; jede Operation wirkt nur dort. Symmetrie entsteht durch die Anzeige/Auswertung. Hier muss nicht die Operation gespiegelt werden, sondern die **Naht** muss jede Operation überleben.

---

## 3. DCC-by-DCC

### 3.1 Blender — Cache mit Zählertest (Quellcode gelesen)

Gelesen: `source/blender/editors/mesh/mesh_mirror.cc`, `meshtools.cc`, `editmesh_utils.cc`, `editmesh_extrude.cc` sowie `editmesh_knife.cc`, `editmesh_loopcut.cc`, `editmesh_bevel.cc`, `editmesh_inset.cc` (Branch `main`, gelesen 2026-09-24) [S7].

**Wie Topology-Mirror Partner findet [FAKT·Code]:**
- Startwert pro Vertex = Anzahl anliegender Edges.
- Iterativ: Jeder Vertex addiert die Werte seiner Nachbarn (gewichtet mit der Durchgangsnummer). Das wiederholt sich, **bis die Zahl unterscheidbarer Werte nicht mehr steigt**.
- Danach wird nach Wert sortiert: **genau zwei** Vertices mit gleichem Wert = Partner; **genau einer** = als Mittel-Vertex behandelt (Partner ist er selbst); **drei oder mehr** = kein Partner.
- Position und Achse gehen in die Paarbildung nicht ein.
  - [INTERPRETATION] Das entspricht im Prinzip einer Farbverfeinerung auf dem Graphen (vergleichbar dem Weisfeiler-Lehman-Verfahren). Es erklärt die im Basisdokument zitierten Schwächen: Regelmäßige Netze erzeugen viele gleiche Werte → keine Partner; ein einseitig neu entstandener Vertex bekommt einen eindeutigen Wert → wird rechnerisch als „Mittel-Vertex" eingestuft.

**Wann neu berechnet wird [FAKT·Code]:** `ED_mesh_mirrtopo_recalc_check` verwirft die Tabelle nur, wenn (a) keine existiert, (b) zwischen Edit- und Object-Mode gewechselt wurde, oder (c) sich die **Anzahl der Vertices oder Edges** geändert hat. Dann wird **vollständig** neu berechnet, nicht nachgeführt. Die Tabelle liegt in einer statischen Variable; ein Code-Kommentar vermerkt als TODO, sie im Objekt zu speichern.
- **[HYPOTHESE, testbar]** Eine Operation, die Topologie ändert, **ohne** Vertex- und Edge-Anzahl zu ändern (z. B. Edge Rotate / Flip Edge: gleiche Zahl, andere Verbindungen), würde den Test nicht auslösen, und die alte Tabelle würde weiterverwendet. Nicht praktisch geprüft; ob andere Pfade den Cache ohnehin freigeben, wurde nicht untersucht.

**Positionsmodus [FAKT·Code]:** Beim nicht-topologischen X-Mirror wird für jede Transform-Operation ein KD-Tree über alle Vertices neu gebaut; Partner = nächster Vertex an der gespiegelten Position, sofern innerhalb eines Maximalabstands. Das Ergebnis liegt in einer **temporären** Vertex-Datenschicht und wird nach der Operation verworfen. Es gibt also gar keinen Zustand, der veralten könnte.

**Welche Topologie-Operationen Edit-Mode-Symmetrie kennen [FAKT·Code]:**
- In `editmesh_knife.cc`, `editmesh_loopcut.cc`, `editmesh_bevel.cc`, `editmesh_inset.cc` kommt weder „mirror" noch „symmetr" vor. Knife, Loop Cut, Bevel und Inset laufen demnach **nur einseitig**; das deckt sich mit dem Nutzerbericht im Basisdokument (dort [Q29]).
- Extrude besitzt eine Mirror-Behandlung, aber nur **für den Mirror Modifier mit Clipping**: Offene Rand-Edges, deren beide Vertices innerhalb der Modifier-Toleranz auf der Spiegelebene liegen, werden vom Extrudieren ausgeschlossen. So entsteht keine Innenwand auf der Naht. Der Test ist **positionsbasiert** (Toleranz), nicht topologisch.
- In `editmesh_tools.cc` ist eine Stelle, die die Auswahl symmetrisch erweitern würde, bewusst per `#if 0` deaktiviert (Begründung im Kommentar: führte bei Invert → Hide zu falschem Verhalten).

**[SCHLUSS] Blender:** Symmetrie für Topologie-Operationen läuft praktisch nur über den **Modifier-Weg** (Strategie A). Die Edit-Mode-Korrespondenz ist ein Wegwerf-Cache (Position) bzw. ein Cache mit grobem Verfallstest (Topologie), jeweils mit voller Neuberechnung.

---

### 3.2 Wings 3D — Naht pro Operation von Hand gepflegt (Quellcode gelesen)

Gelesen: `src/wings_extrude_edge.erl`, `wings_vertex_cmd.erl`, `wings_edge_loop.erl`, `wings_edge.erl`, `wings_subdiv.erl`, `wings_face_cmd.erl`, `wings_we.erl` [S8].

Da die Gegenhälfte virtuell ist, gibt es keine Partner zu finden. Stattdessen muss **jede Operation einzeln** sicherstellen, dass die Spiegelfläche (die Naht) intakt bleibt. Der Code zeigt, dass genau das operationsweise passiert [FAKT·Code]:

| Operation | Behandlung der Naht-Fläche |
|---|---|
| **Extrude (Faces)** | Neue Faces, die an die Naht grenzen, werden in die Naht-Fläche aufgelöst; die resultierende Fläche wird neue Naht (Basisdokument §3.5) |
| **Bevel (Edges und Faces)** | Naht wird vor der Operation temporär auf `none` gesetzt und danach wieder eingetragen |
| **Extrude-Edge / Connect-Pfade** | Sonderfall: Liegt ein Teil an der Naht-Fläche, wird dort ein eigener Zweig ausgeführt |
| **Connect (Vertices)** | Die Naht-Fläche wird beim Verbinden **übersprungen**; man kann nicht quer durch sie verbinden |
| **Edge-Loop-Auswahl** | Naht-Kanten gelten als Rand (wie Löcher); Loops enden dort |
| **Tighten** | Nachbarflächen, die die Naht sind, werden nicht einbezogen |
| **Dissolve** | Danach `validate_mirror`: Ist die Naht-Fläche verschwunden, wird Mirror **still** abgeschaltet |
| **Smooth/Subdivide** | Eigener Codepfad für Netze mit Naht; danach Projektion auf die Ebene des Vorher-Zustands |

- [INTERPRETATION] Das ist die einzige gefundene Form echter **inkrementeller Pflege** — aber nicht einer Korrespondenz, sondern eines einzelnen Naht-Elements. Sie ist nicht generisch, sondern **in jede Operation hineingeschrieben**. Jede neue Operation muss die Naht explizit kennen.
- [OFFEN] Knife/Cut in Wings wurde nicht separat gelesen; da die Naht-Fläche versteckt ist, kann vermutlich nicht in sie hineingeschnitten werden.

---

### 3.3 Maya — Gespiegelte Auswahl, Naht als Abschaltbedingung

- [FAKT] Topologische Symmetrie verlangt gleich viele Faces pro Hälfte, eine Edge entlang der Mitte und **keine Faces, die die Mitte überspannen**. Ist das Netz nicht vollständig symmetrisch, greift **partielle** Symmetrie [S1][S2].
- [FAKT] **Jede Änderung an einer Seam-Edge deaktiviert die Symmetrie**; die Doku empfiehlt, eine Seam-Edge zu wählen, die man nicht bearbeiten wird [S1].
- [FAKT] Symmetrie ist auswahlbasiert und bleibt von Tool zu Tool erhalten [S2].
- [FAKT] Multi-Cut (Schneiden, Edge-Loop-Einfügen) kann mit Object-, World- oder topologischer Symmetrie auf beiden Seiten arbeiten [S3][S3b]. Laut Überblicksartikel zu Maya 2016 kam diese Multi-Cut-Unterstützung ab dieser Generation hinzu, ebenso Quad Draw [S3c].
- [ANWENDER] 2017: Mit Symmetrie lässt sich ein Multi-Cut **nicht auf der Symmetrie-Edge beginnen** (gesperrter Cursor); Umweg: auf der Nachbar-Edge starten und zur Naht zurückschneiden [S3d].
  - [INTERPRETATION] Eine **Schutzmaßnahme**: Die Naht wird für die Eingabe gesperrt, damit das Werkzeug sie nicht verändert — konsistent mit der Regel „Naht-Änderung = Symmetrie aus".
- [ANWENDER/Autodesk-Forenmitarbeiter, 2014, Maya LT] Connect bricht die Symmetrie „in manchen Fällen" (bestätigt als Untersuchungsfall); ein Nutzer zeigt, dass ein einzelner horizontaler Multi-Cut-Loop und Target Weld die Symmetrie brechen. Antwort des Mitarbeiters: Die Toolkit-Symmetrie funktioniere nur mit Modeling-Toolkit-Werkzeugen, nicht mit dem älteren Insert-Edge-Loop aus dem Kontextmenü [S5].
  - [INTERPRETATION] Tool-Abdeckung ist eine Eigenschaft jedes einzelnen Werkzeugs, nicht des Systems. Ein Werkzeug außerhalb dieser Abdeckung erzeugt stillschweigend einseitige Topologie, und die Korrespondenz fällt danach auf „partiell".
- [ANWENDER] 2019: Nach „Merge Vertices" mit Toleranz über das ganze Netz wurden bestimmte Faces nicht mehr symmetrisch erkannt; Wiederherstellung nur durch Spiegeln oder Symmetrize [S5b].
- [ANWENDER] 2026: Shift-Extrude (Extrude per Transform-Gizmo) mit World-Symmetrie verschiebt das ganze Modell, statt zu extrudieren — beschrieben als seit Jahren bestehendes Problem; zusätzlich entstehen leicht Null-Längen-Extrudes. Empfehlung eines Nutzers: das Extrude-Kommando statt Shift-Extrude verwenden [S5c].
  - [INTERPRETATION] Genau an der Stelle, wo „Transform" und „Topologie-Operation" in einer Geste verschmelzen, verliert das auswahlbasierte Modell die Kontrolle.
- [OFFEN] Ob Maya nach einer symmetrischen Operation die Korrespondenz komplett neu berechnet oder anders nachführt, ist nicht dokumentiert. Die Formulierungen („partial activates by default", Naht-Änderung = aus) legen eine Neuberechnung ausgehend von der Seam-Edge nahe [INTERPRETATION].

---

### 3.4 Cinema 4D (ab 2023) — Naht-Tag + Neuberechnung, Tools einzeln integriert

- [FAKT] Die Topologie-Symmetrie wird aus einer vom Nutzer gewählten Edge- oder Polygon-Loop bestimmt; der Algorithmus läuft von der Loop senkrecht in beide Richtungen, gleiche Schrittweite = Partner, Position spielt keine Rolle [S4].
- [FAKT] Die Loop wird per **„Update Topology Loops"** in einem Selection-Tag „Symmetry Selection" gespeichert; das Tag ist technisch ein normales Edge-/Polygon-Selection-Tag [S4].
  - [INTERPRETATION] Die gespeicherte Information ist nur die **Naht**, nicht die Partner-Tabelle. Die Partner werden also aus Naht + aktuellem Netz abgeleitet. Nach einer Topologie-Operation bleibt die Naht gültig, solange die Tag-Auswahl die Operation überlebt; die Partner ergeben sich dann neu. [OFFEN] Ob und wie C4D-Modeling-Tools Selection-Tags bei Topologieänderung nachführen, wurde nicht geprüft — davon hängt die Stabilität dieses Ansatzes ab.
  - Der Button-Name „Update Topology Loops" deutet an, dass der Nutzer die Naht **manuell erneuert**, wenn sie nicht mehr stimmt [INTERPRETATION].
- [FAKT] Einschränkungen laut Doku: Layer- und Line-Schnitte sowie einige Polygon-Pen-Funktionen werden bei **Topologie-Symmetrie** nicht unterstützt; Werkzeuge halten die Symmetrie gelegentlich nicht ein, vor allem bei Komponenten **auf der Ebene** (Beispiel Flip Edges auf einer Kante, die die Ebene schneidet) [S4].
- [FAKT] Ein Tool ohne Symmetrie-Unterstützung erkennt man daran, dass die Symmetrie-Einstellungen ausgeblendet sind, solange es aktiv ist [S4].
- [FAKT] Fixes in Release Notes: Magnet-Tool erzeugte mit topologischer Symmetrie problematische Geometrie (2026.1) [S9]; Loop-Selektion im Symmetrie-Modus konnte verborgene Geometrie auf der Gegenseite wählen und „Phantom-Dreiecke" erzeugen (2026.2) [S9b]; Line Cut unzuverlässig beim Schneiden in N-Gons (2026.2) [S9b].
- [ANWENDER, vor 2023] Knife-Schnitte ließen sich nur über das Symmetry-Objekt symmetrisch machen (eine Hälfte löschen, Generator drüber) [S10].
  - [INTERPRETATION] Vor 2023 war C4D für Topologie-Operationen reine Strategie A; ab 2023 kommt Strategie B dazu.

---

### 3.5 Modo — Einseitige Slices als dauerhaftes Anwenderproblem

- [ANWENDER 2009] Beim Arbeiten im Symmetriemodus werden Slices „irgendwann" nicht auf die Gegenseite übertragen; der Symmetry-Fix bewegt manche Punkte nicht; Symmetrie-Modus erlaube kein Hinzufügen neuer Geometrie auf beiden Seiten. Alternative vieler Nutzer: **gespiegelte Instanz** (Strategie A). Ein anderer Nutzer lobt den mit Modo 302 eingeführten „Symmetry Fix" [S11].
- [ANWENDER 2014] Edge Slice im Symmetriemodus wird nicht auf die andere Seite übertragen; Transform schon. Workaround: gespiegelte Instanz [S11b].
- [FAKT, Basisdokument] Modo wendet Operationen auf korrespondierende **Positionen** an; die Topologie-Option hilft, verlangt aber ein weitgehend symmetrisches Modell (dort [Q15]).
- [OFFEN] Aktueller Stand (Modo 16/17) für Loop Slice, Bevel, Edge Extend nicht geprüft.

---

### 3.6 ZBrush — Topologieänderung = zurück auf Weltsymmetrie

- [FAKT] Nach **Subdividieren** fällt ZBrush von Poseable Symmetry auf normale Symmetrie zurück; man aktiviert Poseable Symmetry erneut, was eine Neuberechnung auslöst [S6].
- [FAKT] Anzeige: grüner Pinselradius = Poseable Symmetry aktiv, rot = nicht aktiv [S6].
- [Händler-Tutorial] Nach DynaMesh, Remesh, ZRemesher oder InsertMesh sollte man Poseable Symmetry nicht mehr erwarten; es brauche identische Vertex-Anzahl und -Reihenfolge beidseitig [S6b].
- [ANWENDER 2019] ZModeler „Insert Edge Loop" mit aktiver Symmetrie erzeugt nur einen Loop auf einer Seite (nur ein gespiegelter Punkt erscheint) [S12]. Ein Händler-Tipp von 2026 empfiehlt dagegen Symmetrie + Local Symmetry, damit Loop-Inserts beidseitig konsistent bleiben [S12b] — der aktuelle Stand ist damit **widersprüchlich belegt** [OFFEN].
- [SCHLUSS] ZBrush behandelt Topologieänderung als **harte Invalidierung mit sichtbarem Zustand**, nicht als Nachführung.

---

### 3.7 3ds Max und Houdini (kurz)

- **3ds Max:** [FAKT] Der Symmetry Modifier spiegelt Änderungen, die unterhalb im Stack an der Originalhälfte gemacht werden, live auf die andere Hälfte — inklusive Topologie-Operationen, weil jede Auswertung neu spiegelt [S13]. [ANWENDER, Basisdokument] Live-Symmetrie am vollen Edit-Poly-Netz gilt als Schwäche. → reine Strategie A; keine Korrespondenz-Pflege nötig.
- **Houdini:** [FAKT, Basisdokument] Mirror ist ein Knoten; jede Neuauswertung spiegelt neu. Korrespondenz für Attribute ist ein Knoten mit Plane-, Topology- oder Mapping-Methode. → Neuberechnung bei jedem Cook; eine Nachführung ist nicht nötig, weil nichts zwischen Auswertungen gespeichert wird.

---

## 4. Operations-Matrix

`✓` = belegt symmetrisch, `✗` = belegt nur einseitig / bricht Symmetrie, `(A)` = nur über abgeleitete Hälfte (Modifier/Virtual), `?` = nicht belegt. In Klammern die Quelle.

| Operation | Blender Edit-Mode | Wings | Maya | C4D ≥2023 | Modo | ZBrush |
|---|---|---|---|---|---|---|
| **Extrude** | ✗ ohne Modifier; (A) mit Modifier: Naht-Edges ausgeschlossen [Code] | (A) angrenzende Faces in Naht aufgelöst [Code] | ✓ seit 2015 [Basis Q11]; ✗ Shift-Extrude mit World-Symmetrie [S5c] | ✓ Modeling-Tools unterstützt [S4] | ? | ? |
| **Inset** | ✗ kein Mirror-Code [Code] | (A) ? | ? | ✓ vermutlich, als Modeling-Tool [S4, INTERPRETATION] | ? | ? |
| **Bevel** | ✗ kein Mirror-Code [Code] | (A) Naht temporär aus, danach wieder gesetzt [Code] | ✓ seit 2015 [Basis Q11] | ✓ [S4]; ✗ Grenzfälle auf der Ebene [S4] | ? | ? |
| **Loop Insert** | ✗ kein Mirror-Code [Code] | (A) Loops enden an Naht [Code] | ✓ Multi-Cut [S3]; ✗ altes Insert-Edge-Loop-Tool [S5] | ✓ Loop/Path Cut [S9 indirekt] | ✗ Slices nicht übertragen [S11][S11b] | ✗ ZModeler 2019 [S12] / ✓ laut 2026-Tipp [S12b] |
| **Knife/Cut** | ✗ kein Mirror-Code [Code] | ? | ✓ Multi-Cut [S3b]; Start auf Naht gesperrt [S3d] | ✗ Layer/Line-Schnitt bei Topologie-Symmetrie [S4] | ✗ [S11] | ? |
| **Connect** | ? | (A) Naht wird übersprungen [Code] | ✗ „in manchen Fällen" (2014) [S5] | ? | ? | — |
| **Delete/Dissolve** | ? | (A) Naht weg → Mirror still aus [Code] | ? | ? | ? | ? |
| **Weld/Merge** | ? | ? | ✗ Target Weld (2014) [S5]; Merge-Toleranz [S5b] | ? | ? | — |
| **Subdivide** | ? | (A) Projektion auf alte Ebene [Code] | ? | ? | ? | ✗ fällt auf Weltsymmetrie zurück [S6] |

[SCHLUSS] Das Muster: **auswahlbasierte** Operationen (Extrude, Bevel) sind am frühesten und stabilsten symmetrisch; **cursorbasierte** Operationen (Knife, Loop Insert, Connect über Pfad) und **mergende** Operationen (Weld) sind die häufigsten Bruchstellen.

---

## 5. Wie neue Partner erkannt werden

| System | Mechanismus für neue Elemente | Beleg |
|---|---|---|
| Blender Topology | Volle Neuberechnung beim nächsten Zugriff (wenn V/E-Anzahl sich änderte); Paar nur, wenn Nachbarschafts-Wert genau zweimal vorkommt | [Code] |
| Blender Position | Pro Transform-Operation KD-Tree neu, nächster Vertex innerhalb Maximalabstand | [Code] |
| Wings | Entfällt — kein Partner nötig | [Code] |
| Maya | Nicht dokumentiert; gespiegelte Auswahl erzeugt beide Seiten gleichzeitig | [S2], [OFFEN] |
| C4D Topology | Partner aus gespeicherter Naht-Loop + aktuellem Netz (Schrittweite) | [S4] |
| C4D Planar | Nächster Punkt zur ideal gespiegelten Position, optional mit Toleranzgrenze | [S4] |
| ZBrush Poseable | Explizite Neuberechnung durch Nutzer nach Subdivide | [S6] |

[SCHLUSS] **Keines der Systeme vergibt Partnerschaft zum Entstehungszeitpunkt eines Elements.** Partnerschaft wird immer nachträglich aus dem Netzzustand erschlossen — ob über Position, Nachbarschafts-Wert oder Schrittweite von der Naht.

[INTERPRETATION] Das hat eine praktische Folge: Eine Operation, die auf beiden Seiten **leicht unterschiedliche** Topologie erzeugt (Rundungsunterschiede beim Schnitt, N-Gon-Triangulierung, andere Loop-Terminierung), zerstört die Korrespondenz lokal, obwohl beide Seiten „dieselbe" Operation erhalten haben. Die C4D-Fixes zu Line Cut in N-Gons und „Phantom-Dreiecken" [S9b] passen zu diesem Muster, ohne es zu beweisen.

---

## 6. Wann wird Symmetrie deaktiviert?

| Auslöser | Reaktion | System | Beleg |
|---|---|---|---|
| Seam-Edge wird verändert | Symmetrie **aus** | Maya | [S1] |
| Naht-Fläche verschwindet (Dissolve) | Mirror **still** auf `none` | Wings | [Code] |
| Subdivide nach Poseable-Berechnung | Rückfall auf Weltsymmetrie, **sichtbar** (Farbe) | ZBrush | [S6] |
| Topologie wird asymmetrisch (Faces-Zahl, Nachbarzahl) | **Partielle** Symmetrie; betroffene Elemente ohne Partner | Maya, C4D | [S1][S4] |
| V/E-Anzahl ändert sich | Tabelle verworfen, **still** neu berechnet | Blender Topology | [Code] |
| Tool nicht symmetrie-fähig | Symmetrie-Einstellungen **ausgeblendet** | C4D | [S4] |
| Tool nicht symmetrie-fähig | Tool läuft **still** einseitig | Blender, Maya (alte Tools), Modo | [Code][S5][S11] |
| Cut-Start auf der Naht | Eingabe **gesperrt** | Maya (Multi-Cut) | [S3d] |

[SCHLUSS] Drei Philosophien sind erkennbar:
- **Naht-zentriert:** Die Naht ist das eine Ding, dessen Verletzung alles abschaltet (Maya, Wings). Der Rest darf asymmetrisch werden.
- **Graduell:** Asymmetrie wird lokal toleriert, Symmetrie bleibt „so weit wie möglich" aktiv (Maya partiell, C4D).
- **Hart + sichtbar:** Jede strukturelle Änderung macht die Korrespondenz ungültig, und das wird angezeigt (ZBrush).

Der häufigste reale Fall — ein Werkzeug, das einfach nicht mitspiegelt — wird fast überall **still** behandelt. Einzig C4D macht Nicht-Unterstützung vorab sichtbar.

---

## 7. Inkrementell oder Neuberechnung?

| System | Gespeichert zwischen Operationen | Nach Topologie-Operation |
|---|---|---|
| Blender Position | nichts | pro Operation neu (KD-Tree) |
| Blender Topology | Paar-Tabelle (global, statisch) | voll neu, wenn V/E-Anzahl anders |
| Wings | Naht-Fläche (ID) | **inkrementell gepflegt**, pro Operation handgeschrieben |
| Modifier/Generatoren (Blender, Max, C4D, Houdini) | nur Quellhälfte + Ebene | jede Auswertung spiegelt neu |
| Maya | Seam-Edge | nicht dokumentiert; Naht-Änderung → aus |
| C4D Topology | Naht-Loop im Selection-Tag | Partner neu aus Naht; Naht bei Bedarf manuell erneuern |
| ZBrush Poseable | Tabelle | ungültig bei Subdivide; manuell neu |
| Maya-Plugin polySymmetry / Max Symmetry Tools | Tabelle | [INTERPRETATION] muss neu erzeugt werden; kein Nachführen dokumentiert |

[SCHLUSS] **Inkrementell gepflegt wird, wenn überhaupt, nur die Naht — nie die Partner.** Die Partner werden entweder gar nicht gebraucht (abgeleitete Hälfte) oder komplett neu erschlossen. Die gespeicherte Naht ist der kleinste Zustand, der die Neuberechnung möglich macht.

[INTERPRETATION] Das ist konsistent mit der Aufwandsverteilung: Eine Naht ist eine einzige Loop bzw. Fläche; sie durch Operationen zu tragen, ist lokal. Eine vollständige Partner-Tabelle durch jede Operation zu tragen, würde verlangen, dass **jede** Operation für **jedes** neue Element seinen Partner meldet. Das wäre ein Provenance-/Remapping-System, wie ROADMAP ARCH-02 es als offene Frage beschreibt. Keine der untersuchten DCCs scheint diesen Weg gegangen zu sein — oder er ist zumindest nicht öffentlich dokumentiert.

---

## 8. Offene Fragen

- **Maya intern:** Neuberechnung nach jeder Operation oder etwas anderes? Keine Primärquelle gefunden.
- **C4D Selection-Tags unter Topologie-Operationen:** Werden sie von Extrude/Cut nachgeführt? Davon hängt ab, ob die gespeicherte Naht stabil bleibt.
- **Blender Edge Rotate / Flip:** Bleibt die Topologie-Tabelle veraltet (Hypothese §3.1)? Praktisch testbar.
- **Modo aktuell** (16/17): Stand bei Loop Slice, Bevel, Edge Extend.
- **ZBrush ZModeler:** Widersprüchliche Berichte zu Insert Edge Loop mit Symmetrie.
- **Silo:** Wird in der Community für operationsübergreifende Symmetrie gelobt; kein Mechanismus belegt. Wegen der Nähe zu Mirai-artigen Modelern weiterhin interessant.
- **Mirai / N-World:** Nicht untersucht.
- **Nicht untersucht:** Radiale Symmetrie unter Topologie-Operationen; Symmetrie für abhängige Daten (UV, Weights) nach Topologieänderung — das gehört eher zu ARCH-02 und CHARACTER_SYSTEMS_RESEARCH.

---

## 9. Quellen

Abgerufen 2026-09-23/24.

**Quellcode**
- [S7] Blender, Branch `main`, gelesen 2026-09-24: `source/blender/editors/mesh/mesh_mirror.cc` (`ED_mesh_mirrtopo_recalc_check`, `ED_mesh_mirrtopo_init`), `meshtools.cc` (`ed_mesh_mirror_topo_table_update`, TODO-Kommentar), `editmesh_utils.cc` (`EDBM_verts_mirror_cache_begin_ex`), `editmesh_extrude.cc` (`edbm_extrude_edge_exclude_mirror`), `editmesh_tools.cc` (deaktivierte `EDBM_select_mirrored_extend_all`), `editmesh_knife.cc`, `editmesh_loopcut.cc`, `editmesh_bevel.cc`, `editmesh_inset.cc`. https://github.com/blender/blender
- [S8] Wings 3D, https://github.com/dgud/wings — `src/wings_extrude_edge.erl` (`bevel_edges`, `bevel_faces`, `connect`), `src/wings_vertex_cmd.erl` (`connect`, `connecting_edge`, `tighten_vec`), `src/wings_edge_loop.erl` (`add_mirror_edges`, `mirror_edges`), `src/wings_edge.erl` (Dissolve + `validate_mirror`), `src/wings_subdiv.erl`, `src/wings_face_cmd.erl`, `src/wings_we.erl`.

**Maya**
- [S1] Autodesk Maya 2019 — Edit a mesh with topological symmetry. https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2019/ENU/Maya-Modeling/files/GUID-EC3CCAFA-DBEB-4733-AF50-467B9EE8B65B-htm.html
- [S2] Autodesk Maya 2023/2025 — Symmetrical editing. https://help.autodesk.com/cloudhelp/2023/ENU/Maya-Modeling/files/GUID-68206E61-CFF0-4C83-9254-B761C51FED98.htm · https://help.autodesk.com/cloudhelp/2025/ENU/Maya-Modeling/files/GUID-68206E61-CFF0-4C83-9254-B761C51FED98.htm
- [S3] Autodesk Maya 2020 — Insert an edge loop with the Multi-Cut Tool. https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2020/ENU/Maya-Modeling/files/GUID-145A01AC-1FCD-4229-B40C-F0C2B443EFF9-htm.html
- [S3b] Autodesk Maya Creative — Cut faces with the Multi-Cut Tool. https://help.autodesk.com/view/MAYACRE/ENU/?guid=GUID-12DF0D57-6E5E-48E3-8FBF-F787BA4E5410
- [S3c] Lesterbanks 2016 — Maya's Symmetrical Modeling Improvements. https://lesterbanks.com/2016/04/maya-symmetrical-modeling-improvements/
- [S3d] [ANWENDER] polycount 2017 — Does Maya allow multi-cut on symmetry edge? https://polycount.com/discussion/185447/does-maya-allow-multi-cut-on-symmetry-edge
- [S5] [ANWENDER + Forenmitarbeiter] Steam Community, Maya LT, 2014 — Symmetry-Diskussion. https://steamcommunity.com/app/243580/discussions/0/540743757818904451
- [S5b] [ANWENDER] polycount 2019 — Can't select certain faces or edges in symmetry in Maya. https://polycount.com/discussion/208854/cant-select-certain-faces-or-edges-in-symmetry-in-maya-problem
- [S5c] [ANWENDER] Autodesk Community 2026 — Symmetry, and Extruding. https://forums.autodesk.com/t5/maya-modeling-forum/symmetry-and-extruding/td-p/12175654

**Cinema 4D**
- [S4] Maxon Help 2025 — Symmetry. https://help.maxon.net/c4d/2025/en-us/Content/html/Symmetry.html
- [S9] Maxon Release Notes 2026.1. https://support.maxon.net/hc/en-us/articles/24785504728988-Cinema-4D-2026-1-December-3-2025
- [S9b] Maxon Release Notes 2026.2. https://support.maxon.net/hc/en-us/articles/8658038724124-Cinema-4D-2026-2-0-April-15-2026
- [S10] [ANWENDER] Creative COW — Symmetry for knife cuts. https://creativecow.net/forums/thread/how-can-i-enable-symmetry-for-knife-cuts-selecting-mesh/

**Modo**
- [S11] [ANWENDER] polycount 2009 — Symmetrical Modeling with Mirrored Instances. https://polycount.com/discussion/64844/modo-tip-symmetrical-modeling-with-mirrored-instances
- [S11b] [ANWENDER] polycount 2014 — Modo Symmetry. https://polycount.com/discussion/139466/modo-symmetry

**ZBrush**
- [S6] Maxon ZBrush Docs — Symmetry. https://help.maxon.net/zbr/en-us/Content/html/user-guide/3d-modeling/sculpting/symmetry/symmetry.html
- [S6b] [Händler-Tutorial] Novedge 2026 — Poseable Symmetry. https://novedge.com/blogs/design-news/zbrush-tip-poseable-symmetry-for-symmetric-sculpting-on-posed-models
- [S12] [ANWENDER] ZBrushCentral 2019 — zmodeler insert edge loop symmetry. https://www.zbrushcentral.com/t/zmodeler-insert-edge-loop-symmetry/334423
- [S12b] [Händler-Tutorial] Novedge 2026 — ZModeler Edge Loop Workflow. https://novedge.com/blogs/design-news/zbrush-tip-zmodeler-edge-loop-workflow-for-support-shading-and-animation

**3ds Max**
- [S13] Autodesk 3ds Max 2024 — Symmetry Modifier. https://help.autodesk.com/cloudhelp/2024/ENU/3DSMax-Modifiers/files/GUID-EB0B7B9B-117D-4CC3-A966-A3E007E0C68A.htm
