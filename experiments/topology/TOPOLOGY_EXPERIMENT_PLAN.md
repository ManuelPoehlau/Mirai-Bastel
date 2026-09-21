# Topology Experiment Plan

Dieser Bereich ist die **Spielwiese für Topologie-Manipulation**.

Hier dürfen interaktive und algorithmische Experimente entstehen, ohne dass daraus automatisch Produktionsarchitektur oder Core-Änderungen werden. Ziel ist, möglichst früh herauszufinden, welche Topologie-Operationen, Datenbeziehungen und Bedienkonzepte Mirai-Bastel für seine langfristige Vision benötigt.

## Dokumentationsgrenze

Dieses Dokument ist der **Single Source of Truth für den aktiven Topology-Experimentplan**: Phasen, Reihenfolge als Orientierung, gemeinsame Prüfmatrix und aktuell bekannte Topology-spezifische Forschungsfragen.

Allgemeine Selection-/Workflow-Prinzipien werden nicht hier dupliziert:

- [`Selection Experiment`](../mirai_bastel_viewport_V1/SELECTION_MODES.md)
- [`Selection Future Ideas`](../../docs/future_ideas/SELECTION.md)
- [`Workflow Design`](../../docs/design/WORKFLOW.md)

Architekturverträge bleiben unter `docs/architecture/`.

## Forschungsrichtung

Mirai-Bastel soll nicht nur ein weiterer Modeler werden. Ein zentraler Forschungsbereich ist die robuste Verbindung von

```text
Modellierung
    ↕
Topologieänderung
    ↕
Deformation / Skinning / Morphing
```

Insbesondere wollen wir früh untersuchen, was mit Deformationsdaten passiert, wenn ein bereits deformierbares Mesh nachträglich verändert wird.

Das ist bewusst ein **Forschungsziel**, keine bereits festgelegte technische Lösung.

## Phase 1 — vorhandene Core-Primitives als Werkzeuge

**Status: interaktiv untersucht; Connect Edges bleibt als offene Basisoperation bestehen.**

Die erste Stufe hat bewusst keine neue Core-Funktion eingeführt. Vorhandene, durch Core-Hardening-Tests abgesicherte Primitive wurden interaktiv im V1-Viewport benutzt:

1. **Split Edge** → `split_edge()`
2. **Collapse Edge** → `collapse_edge()`
3. **Connect Vertices** → `connect_vertices()`
4. **Connect Edges** → experimentelle Kombination aus `split_edge()` + `connect_vertices()`

Dabei wurde sichtbar, dass insbesondere die Multi-Edge-Semantik von Connect Edges noch nicht ausreichend definiert bzw. umgesetzt ist. Das ist für die weitere Topology-Forschung relevant und wird deshalb jetzt vor höherwertigen Operationen wie Loop Insert untersucht.

Praktische Beobachtungen aus Phase 1:

- einzelne Vertex-/Edge-Connect-Fälle funktionieren wie erwartet;
- Split und Collapse funktionieren in den untersuchten Fällen;
- nicht zulässige Verbindungen ohne gemeinsames Face werden abgelehnt;
- Collapse kann bei sehr kleiner Restgeometrie zu freischwebenden Edges führen; das ist für die Primitive logisch, für ein späteres Modeler-Tool aber eine Workflow-/Validierungsfrage;
- Selection/Mode nach einer Operation ist ein wichtiger eigener Workflow-Aspekt;
- Undo/Redo der Topology-Tools ist derzeit **noch nicht abgeschlossen**, weil der experimentelle Command auf `Mesh.load_state()` angewiesen ist, das im aktuellen Core V1 nicht vorhanden ist.

### Warum Connect Edges jetzt priorisiert wird

Connect Edges gehört zu den grundlegenden Mesh-Editing-Operationen. Bevor höherwertige Modeling-Operationen darauf aufbauen oder ähnliche Topologie-Manipulationen neu implementieren, soll zuerst geklärt werden, welche Semantik eine Edge-Multi-Selection haben soll.

Insbesondere soll untersucht werden:

- Was bedeutet Connect bei genau 2 Edges?
- Was soll bei 3+ ausgewählten Edges passieren?
- Wie verhalten sich zusammenhängende Edge-Sets?
- Wie verhalten sich vollständige Loops und Rings?
- Was passiert bei disjunkten Edges?
- Welche Boundary-/Face-Konstellationen sind gültig?
- Wann soll eine Auswahl abgelehnt werden, statt eine teilweise Mutation auszuführen?
- Welche Selection und welcher Selection Mode sollen nach erfolgreicher Operation entstehen?

Der aktuelle experimentelle Zustand zeigt bereits, dass eine größere Auswahl momentan nicht wie eine einheitliche Connect-Operation behandelt wird: Teile können verbunden werden, während andere ausgewählte Edges lediglich gesplittet werden. Dieses Verhalten ist **nicht als endgültige Modeling-Semantik** festgelegt.

## Phase 2 — Loop / Ring Detection und Selection

**Status: abgeschlossen und praktisch verifiziert.**

Die Phase wurde bewusst in zwei Schritte aufgeteilt: Zuerst wurde die reine Traversierungslogik implementiert und getestet, anschließend wurde sie interaktiv im Topology Lab verdrahtet und im Viewport geprüft.

### Erkennung (Query-Ebene)

`experiments/mirai_bastel_viewport_V1/viewport/loop_ring.py` implementiert `edge_loop()` und `edge_ring()` rein über die bestehende Topologie-Query-API (`face_vertices`, `face_edges`, `edge_faces`, `edge_vertices`, `vertex_edges`), ohne Core- oder Mesh-Änderung.

Die Erkennung ist bewusst konservativ:

- **Edge Ring** läuft nur durch Quad-Faces (Boundary-Länge 4); trifft er auf eine Non-Quad-Face, bricht er auf dieser Seite ab.
- **Edge Loop** läuft nur durch Vertices mit Valenz genau 4 und eindeutigem "gegenüberliegendem" Kandidaten (keine gemeinsame Face mit der eingehenden Kante).
- Boundary-Loop-Fortsetzung ist bewusst **nicht** implementiert, sondern bleibt als offene Folgefrage bestehen.
- Beide erkennen geschlossene Loops/Ringe explizit über ein `closed`-Flag, statt die Startkante doppelt aufzunehmen.

Die Erkennung wurde in `experiments/mirai_bastel_viewport_V1/tests/test_loop_ring.py` ohne Fenster/GPU verifiziert: volle Zeile/Spalte im Quad-Grid, konservativer Abbruch an Rand-Valenz und Non-Quad-Face sowie geschlossene Loop-/Ring-Erkennung auf einem künstlichen Quad-Rohr.

### Interaktive Selection

Die Erkennung ist jetzt im Topology Lab interaktiv angebunden:

```text
Edge Mode + genau 1 Edge
        ↓
L → Edge Loop
R → Edge Ring
        ↓
erkanntes Edge Set
        ↓
Viewport Selection
```

Aktuelles experimentelles Verhalten:

- **`L`** wählt den Edge Loop der aktuell ausgewählten Startkante.
- **`R`** wählt den Edge Ring der aktuell ausgewählten Startkante.
- Voraussetzung ist Edge Mode und genau eine ausgewählte Edge.
- Die bisherige Selection wird durch das erkannte Edge-Set ersetzt.
- Das Ergebnis wird unmittelbar im Viewport visualisiert.
- Geschlossene Traversierungen werden über den `closed`-Status in der Caption angezeigt.
- Die Auswahl selbst verändert keine Mesh-Topologie und benötigt keine Änderung am eingefrorenen Core V1.

Die komplette Kette wurde praktisch getestet und funktioniert:

```text
Edge Picking
    ↓
Loop / Ring Detection
    ↓
Edge Set
    ↓
Viewport Selection
    ↓
visuelles Ergebnis
```

### Bewusst offene Forschungsfragen

Der Abschluss von Phase 2 bedeutet nicht, dass jede denkbare Loop-/Ring-Semantik gelöst ist. Offen bleiben insbesondere:

- Loop-/Ring-Verhalten bei komplexeren gemischten Quad-/Non-Quad-Topologien über die aktuelle Grenzfallabdeckung hinaus;
- Boundary-Loop-Fortsetzung;
- endgültige Modifier-/Interaktionssemantik;
- spätere Loop-/Ring-Operationen wie Insert, Cut und Slide.

Die Detection bleibt damit bewusst ein konservatives Experiment und kein endgültiger Produktionsvertrag.

## Phase 3 — Connect Edges: Semantik und robuste Multi-Selection

**Status: als Enablement-Port implementiert und headless-getestet (2026-09-14). "kind v" / FreeConnect seit AP-05 über `Mesh.add_edge()` umgesetzt. Praktische Grenzen des Quad-Scopes charakterisiert (2026-09-21) — Nicht-Quads, Ecken und Fortsetzen in Discovery, siehe unten.**

### Stand 2026-09-21 — Praxisgrenze und Discovery

Artist-Beobachtung: Mit dem aktuellen Connect ist kein vernünftiges Arbeiten an der Topologie möglich.
Ursache (reproduziert): Jeder Teilschnitt erzeugt zwangsläufig Fünfecke, und Connect verweigert danach jede
Kante an Nicht-Quads; Ecken und Knicke werden abgelehnt. Übrig bleibt praktisch "ganzer Loop oder nichts".

- Befunde F1–F10: [`CONNECT_EDGES_SPEC.md` §11](../../docs/research/topology/CONNECT_EDGES_SPEC.md)
- Charakterisierungstests: `playground/tests/test_topology_connect_edges_characterization.py`
- Discovery (Wings-Semantik, Core-Probe, Designfragen D1–D8, vorbereiteter Artist-Test): [`CONNECT_NONQUAD_DISCOVERY.md`](../../docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md)
- Probe-Skript: `experiments/topology/connect_per_face_probe.py`

Die Abschnitte darunter beschreiben den Stand vom 2026-09-14; abweichende Punkte sind markiert.

Connect Edges wurde als 1:1-Logik-Port aus dem V1-Experiment (`experiments/mirai_bastel_viewport_V1/viewport/topology_tools.py`) gegen Production-`src/core` implementiert, analog zu Split Edge (Enablement-01).

### Implementierter Stand (2026-09-14)

- `playground/topology_tools/connect_edges.py` — `connect_selected_edges(scene, edge_ids)`, 3-Phasen-Plan (Analyze/Validate → Plan/Dry-Run → Apply/Commit), 1 MeshStateCommand
- `playground/window.py` — Taste **J** (Edge-Modus, 2+ Edges selektiert; *seit WP-AP-INPUT-FIX-02: Taste **C***); Selection danach auf neue Verbindungskanten; TopologyToolError → HUD-Anzeige statt Crash
- `playground/tests/test_topology_connect_edges.py` — 7 Headless-Tests: 1 History-Eintrag, neue Vertices/Kante, TopologyToolError bei Einzelauswahl, Undo/Redo, Determinismus (Set-Reihenfolge), "kind v"-Fall → expliziter Error; alle grün

### Bewusst ausgeklammerter Fall: "kind v" / FreeConnect

> *Überholt:* `Mesh.add_edge()` wurde mit AP-05 als Core-Ausnahme ergänzt (CORE_V1_FREEZE) und der "v"-Zweig ist aktiv. Befund F7 (2026-09-21): Das Ergebnis liegt geometrisch auf den bestehenden Kanten und teilt keine Face — als Problem dokumentiert in der Discovery (D6), nicht entschieden. Der folgende Text ist der historische Stand.

V1 nutzt `mesh.add_edge()` für Ketten-Verbindungen über einen gemeinsamen regulären Innen-Vertex ohne gemeinsame Face. Diese Methode existiert **nicht** in `src/core` (nur privates `_get_or_create_edge()`, intern von `add_face()` genutzt, keine öffentliche API für freistehende Edges ohne Face).

`src/core` bleibt unangetastet (Grundregel seit Enablement-01). Praktische Konsequenz: Auf einem Standard-Cube hat jeder Vertex Valenz 3 — `_is_regular_interior_vertex()` verlangt Valenz ≥ 4, also kann der "kind v"-Fall dort ohnehin nie auftreten. Der Fall wird deshalb **explizit abgelehnt** (TopologyToolError mit klarer Meldung), nicht still übergangen oder gecrashed.

Falls `mesh.add_edge()` in `src/core` je hinzugefügt wird (nach einer expliziten Architecture Decision), kann der "v"-Zweig in `_build_adjacency()` und `_execute_plan()` ohne Logik-Änderung nachgerüstet werden.

### Forschungsziel (ursprünglich)

Eine ausgewählte Menge von Edges soll nicht nur technisch mutiert werden, sondern eine klar definierte und reproduzierbare Connect-Operation darstellen.

Zuerst wird das Verhalten ohne neue höherwertige Modeling-Funktion untersucht:

```text
Edge Selection
      ↓
Connect Edges
      ↓
Topologie + Selection
```

### Untersuchungsmatrix

| Fall | Status |
|---|---|
| 2 Edges gegenüberliegend in Quad-Face | ✓ implementiert |
| 3+ zusammenhängende Edges (Kette/Ring) | ✓ implementiert (deterministisch geordnet) |
| kompletter Edge Loop | ✓ funktioniert (Kette oder Ring via Adjacency-Graph) |
| disjunkte Edges ohne gemeinsame Topologie | TopologyToolError (keine Partner-Edge) |
| freie Edges (0 Faces) | TopologyToolError (außerhalb Scope) |
| Boundary Edges (1 Face, Quad) | ✓ zulässig (Rand → Rand funktioniert) |
| benachbarte Kanten einer Face (Ecke) | TopologyToolError — Discovery D1 |
| Pfad mit Knick | TopologyToolError — Discovery D1 |
| alle 4 Kanten eines Quads | interner Abbruch (F10) — Discovery D3 |
| Non-Manifold Edges (>2 Faces) | TopologyToolError (außerhalb Scope) |
| Non-Quad-Faces | TopologyToolError (außerhalb Scope) |
| Kette über gemeinsamen Vertex ohne Face ("kind v") | freie Kante via `add_edge()` — geometrisch fragwürdig (F7), Discovery D6 |
| ungültige Auswahl (< 2 Edges) | TopologyToolError |

### Wichtige Abgrenzung

Connect Edges und Loop Insert werden nicht als dieselbe Operation angenommen.

```text
Connect Edges
    = vorhandene Auswahl gemäß definierter Connect-Semantik verbinden

Loop Insert
    = zusammenhängenden neuen Schnitt durch geeignete Faces/Topologie erzeugen
```

Der aktuelle Test `Edge Ring → Connect Edges` hat diese Abgrenzung praktisch sichtbar gemacht: Eine Ring-Auswahl wird momentan lediglich wie eine normale Multi-Edge-Selection an die bestehende Connect-Logik weitergereicht. Das erzeugt noch kein echtes Loop-Insert-Verhalten.

## Phase 4 — Loop Insert / Loop Remove

**Status: Loop Insert implementiert und headless getestet (AP-05, `playground/topology_tools/loop_insert.py`, Taste I) — wiederverwendet Phase-2-Ring-Erkennung + Phase-3-Connect-Mutation. Loop Remove/Dissolve weiterhin geplant.**

Die beiden zusammengehörigen Fälle werden als nächste große Forschungsgruppe betrachtet.

### Loop Insert

Neue Geometrie wird innerhalb einer bestehenden Struktur erzeugt.

Zu untersuchen:

- ob und wie vorhandene Loop-/Ring-Traversierung wiederverwendet werden kann;
- welche Faces von einem Insert betroffen sind;
- entstehende Vertices / Edges / Faces;
- Beziehungen zwischen alten und neuen Elementen;
- ID-Kontinuität;
- Herkunft/Provenance;
- spätere Skin-Weight-Übertragung;
- spätere Morph-Delta-Übertragung;
- interaktive Positionierung bzw. späteres Loop Slide.

Ein Loop Insert darf nicht einfach als "Ring Selection + Connect Edges" vorausgesetzt werden. Ob vorhandene Primitive sinnvoll zusammengesetzt werden können, soll erst aus den Ergebnissen von Phase 3 abgeleitet werden.

### Loop Remove / Dissolve

Bestehende Geometrie wird reduziert bzw. zusammengeführt.

Zu untersuchen:

- welche Elemente verschwinden;
- welche IDs erhalten bleiben;
- welche Daten mehrerer Elemente später zusammengeführt werden müssten;
- ob Herkunfts-/Provenance-Informationen benötigt werden;
- Abgrenzung zu Collapse.

Für das Modeling-Experiment wird **Remove zunächst als Dissolve** verstanden, nicht als geometrisches Collapse. Die genaue Semantik wird beim Experiment festgelegt.

## Phase 5 — Extrude

**Status: Baseline-Variante implementiert und headless-getestet (2026-09-14). Noch kein Artist-Verdict.**

> **Reihenfolge-Hinweis:** Phase 5 (Extrude) wurde im Rahmen des AP-05-Auftakts **vor** Phase 3 (Connect Edges) und Phase 4 (Loop Insert) implementiert — nicht danach wie ursprünglich geplant. Die Phase-Nummerierung wird bewusst beibehalten (sie beschreibt die konzeptuelle Abhängigkeitsstruktur, nicht die Durchführungsreihenfolge). Extrude wurde vorgezogen, weil es ein eigenständig validierbarer Topologie-Fall ist und für den AP-05-Auftakt als erster Discovery-Schritt dient.

Als nächster größerer Topologie-Fall soll **Extrude** untersucht werden.

```text
Face / Face Group
       ↓
    Extrude
       ↓
neue Vertices + Edges + Faces
```

### Implementierter Stand (Multi-Face-Region, 2026-09-14)

- 1+ Faces auswählen (Face-Modus) → E-Taste → Topologie sofort aufgebaut via Boundary-Edge-Regel
  - Neue Vertices: Union aller Vertices aus allen selektierten Faces (keine Duplikate)
  - Seitenwände nur für Boundary-Edges (Edges mit genau 1 selektierter Nachbar-Face); interne Edges (2 selektierte Faces) bekommen keine Wand
  - Caps: je 1 neue Face pro Original-Face, 1:1 auf neue Vertex-IDs gemappt (keine Verschmelzung)
  - Normale: pro zusammenhängender Komponente (BFS über Adjazenz-Edges), nicht global — entgegengesetzt orientierte Regionen (z.B. linke+rechte Würfelseite) summierten sich sonst zu (0,0,0) und lösten den Z-Fallback aus; jede Komponente bewegt sich entlang ihrer eigenen gemittelten Newell-Normale
  - Distanz-Referenzachse (Drag-Skalar) bleibt global: bei entgegengesetzten Regionen ungenau — bekannte, noch offene Feinheit
- Bei genau 1 Face identisch zum bisherigen Single-Face-Verhalten (echter Refaktor, keine Parallel-Implementierung)
- Hover-Fallback (leere Selection → Hit-Test) bleibt auf 1 Face begrenzt
- LMB-Drag / Motion → Extrusions-Distanz live (entlang Region-Normale)
- LMB-Release / E-Release → Commit (ein MeshStateCommand in der History)
- ESC → Cancel (Mesh-Restore + Multi-Selection-Restore, kein History-Eintrag)
- Undo/Redo funktioniert identisch zu Split Edge
- 12 Headless-Tests (8 Baseline-Regression + 4 Multi-Face), alle grün

Zu untersuchen sind insbesondere:

- Entstehung und Beziehungen neuer Elemente
- Auswahl der extrudierten Region
- Normal-/Richtungsfragen
- ID- und Herkunftsbeziehungen
- History
- spätere Übertragung von Deformationsdaten
- interaktives Verhalten

## Phase 6+ — weitere Topologie-Experimente

Je nach Erkenntnisgewinn können danach folgen:

- Inset
- Bevel
- Bridge
- weitere Connect-/Dissolve-Varianten
- Loop Slide
- Subdivision-nahe Geometrieoperationen
- größere kombinierte Topologieänderungen
- Retopology-nahe Verfahren

Die Liste ist **offen und keine starre Feature-Roadmap**.

## Nicht nur Einzeloperationen testen

Die langfristige Robustheit lässt sich nicht durch eine einzelne erfolgreiche Operation beweisen.

Beispielsweise:

```text
Split
  ↓
Connect
  ↓
Collapse
  ↓
weitere Änderung
```

und später:

```text
Topologie ändern
  ↓
Deform
  ↓
weitere Topologieänderung
  ↓
Deform erneut auswerten
```

Noch später:

```text
Extrude
  ↓
Skin
  ↓
Loop Insert
  ↓
Pose / Deform
  ↓
Loop Remove
  ↓
Morph
  ↓
weitere Topologieänderung
```

Solche Kombinationen sind langfristig interessanter als isolierte Demo-Funktionen.

## Gemeinsame Prüfmatrix

Bei jeder relevanten Topologieänderung sollten nach Möglichkeit dieselben Fragen gestellt werden:

1. **Topologie:** Was entsteht, verschwindet oder ändert sich?
2. **Identität:** Welche IDs bleiben erhalten, welche entstehen neu?
3. **Beziehungen:** Welche alten/neuen Elemente stehen miteinander in Beziehung?
4. **Provenance:** Können wir die Herkunft einer Änderung sinnvoll beschreiben?
5. **History:** Ist die Mutation exakt undo-/redo-fähig?
6. **Skinning:** Wie könnten Bone-Weights erhalten, interpoliert oder zusammengeführt werden?
7. **Morphing:** Wie könnten Morph-Deltas erhalten, interpoliert oder zusammengeführt werden?
8. **Kombinationen:** Funktioniert das Verhalten auch nach mehreren aufeinanderfolgenden Mutationen?
9. **Benutzbarkeit:** Ist die Operation später sinnvoll interaktiv bedienbar?
10. **Workflow:** Was passiert mit Selection und aktivem Selection Mode nach der Operation?

Damit testen wir nicht nur, **ob eine Operation funktioniert**, sondern ob sie eine brauchbare Grundlage für das spätere System bildet.

## Beziehung zum Core V1

Der Core V1 ist eingefroren. Topology-Experimente dürfen zeigen, dass eine zukünftige Produktionsfunktion weitere Core-Fähigkeiten benötigt. Das bedeutet nicht automatisch, dass diese Fähigkeit sofort in `src/core` eingebaut wird.

Der bevorzugte Weg bleibt:

```text
Experiment
    ↓
Beobachtung
    ↓
Erkenntnis
    ↓
Architekturentscheidung
    ↓
falls wirklich notwendig:
Core-/Production-Erweiterung
```

Nicht jede experimentelle Operation muss jemals Produktionscode werden.

## Brücke zu Deformation

Sobald die grundlegenden Topologieoperationen ausreichend verstanden sind, sollen sie bewusst mit frühen Deformations-Experimenten verbunden werden:

```text
Mesh
  ↓
Bones / Skin Weights
  ↓
Deformation
  ↓
Topologie ändern
  ↓
Deformation erneut auswerten
```

Danach:

```text
Topologie
    ↕
Skinning
    ↕
Morph Targets
```

Animation kommt bewusst später. Die Datenkontinuität zwischen Modellierung und Deformation soll jedoch möglichst früh erforscht werden.

## Grundsatz

> **Nicht zuerst den perfekten Modeler bauen. Erst herausfinden, welche Kombination aus Topologie, Deformation und Datenkontinuität Mirai-Bastel besonders machen kann.**

Dieses Dokument beschreibt **Richtung, Experimente und Forschungsfragen**, nicht die endgültige Produktionsarchitektur.
