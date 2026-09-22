# Connect — Nicht-Quads, Eck-Verbindungen und Fortsetzen: Discovery

**Status:** Discovery — Research Package (Typ B), keine Entscheidung
**Datum:** 2026-09-21
**Modus (M5):** Discovery
**Gehört zu:** [`CONNECT_EDGES_SPEC.md`](CONNECT_EDGES_SPEC.md) §10 (offene Designfragen) und §11 (Befunde)
**Code-Stand untersucht:** `main` @ `01ea6f9`

> Dieses Dokument untersucht die offene Frage aus der Spec §10 („handling of boundary edges and
> non-quad faces", „behavior on mixed face valences"). Es ändert kein Verhalten, trifft keine
> Produktentscheidung und schlägt kein Werkzeug vor. Es liefert Evidenz und bereitet einen
> Artist-Test vor.

---

## 0. History Awareness (M1)

| Existiert | Wo | Bedeutung hier |
|---|---|---|
| Verhaltensvertrag Connect Edges | `CONNECT_EDGES_SPEC.md` | Nicht-Quads ausdrücklich **offen** (§10) — nicht verworfen. |
| Experimentplan, Phase 3 | `experiments/topology/TOPOLOGY_EXPERIMENT_PLAN.md` | Beschreibt den Scope „nur reguläre Quads". War beim Untersuchungszeitpunkt teilweise veraltet (Taste, „kind v") — im selben Schritt korrigiert. |
| Implementierung | `playground/topology_tools/connect_edges.py` | Streifen-Semantik: nur gegenüberliegende Kanten in Quads. |
| Abhängiger Nutzer | `playground/topology_tools/loop_insert.py` | **Loop Insert ruft `connect_selected_edges()` direkt auf.** Jede Änderung an Connect wirkt auf Loop Insert. |
| Core-Ausnahme `add_edge()` | `docs/architecture/CORE_V1_FREEZE.md` (AP-05) | Begründet mit dem „kind v"-Fall — siehe D6. |
| Connect Vertices | AD-013 (Stand: vertagt) | Grenzt an D5, wird hier nicht entschieden. |
| Topologie-Grundlagen | `docs/research/MODELING_WORKFLOW_TOPOLOGY_RESEARCH.md` §15 | Liefert die Begründung, warum Nicht-Quads beim lokalen Arbeiten zwangsläufig entstehen. |

**Verworfenes:** Kein Hinweis darauf, dass Ngon-Unterstützung oder Eck-Verbindungen jemals
geprüft und abgelehnt wurden. Sie wurden nur aus dem ersten Scope herausgehalten.

---

## 1. Problem

Aus der Praxis (Artist-Beobachtung): Das aktuelle Connect-Tool erlaubt kein vernünftiges
Arbeiten an der Topologie.

Technisch reproduziert und als Charakterisierungstests festgehalten
(`playground/tests/test_topology_connect_edges_characterization.py`, F1–F9):

| # | Befund | Evidenz |
|---|---|---|
| F1 | Ein Teilschnitt, der im Mesh endet, hinterlässt 2 Fünfecke. | Test |
| F2 | Connect verweigert jede Kante an einer Nicht-Quad-Face → nach F1 ist die Stelle blockiert. | Test |
| F3 | Ecke abschneiden (zwei benachbarte Kanten einer Face) → abgelehnt. | Test |
| F4 | Pfad, der abbiegt → abgelehnt. | Test |
| F5 | Zwei Kanten mit einem Quad Abstand → abgelehnt. | Test |
| F6 | Rand → Rand / geschlossener Ring → funktioniert, nur Quads. | Test |
| F7 | „kind v" erzeugt eine freie Kante, die **auf** bestehenden Kanten liegt; keine Face wird geteilt; 4 Fünfecke. | Test |
| F8 | Ablehnungen sind atomar (Mesh und History unverändert). | Test |
| F9 | Die Core-Primitive können Eck-Schnitt und Fünfeck-Auflösung bereits. | Test |
| F10 | Alle 4 Kanten eines Quads → Abbruch mit unverständlicher Meldung („Operationsplan nicht auf gültige Topologie abbildbar: FaceId(5)"). Ursache: zwei sich kreuzende Paare in derselben Face; nach dem ersten Schnitt existiert die geplante Face nicht mehr. | Test |

**Kernzusammenhang (FAKT, siehe Topologie-Research §15.0):** Ein Quad-Streifen kann im Inneren
eines Meshes nicht enden. Jeder Teilschnitt *muss* daher an seinen Enden Nicht-Quads erzeugen.
F1 ist also kein Fehler des Werkzeugs — **F2 macht aus einer mathematischen Notwendigkeit eine
Sackgasse.** Übrig bleibt praktisch nur „ganzer Loop oder nichts", also dasselbe, was Loop Insert
bereits tut.

---

## 2. Referenz: Wie Wings 3D Connect umsetzt

Quelle: Wings-3D-Quellcode (`github.com/dgud/wings`, `src/wings_edge_cmd.erl`,
`src/wings_vertex.erl`, `src/wings_vertex_cmd.erl`) — **FAKT**, direkt aus dem Code gelesen.
Die Spec nennt Wings' Edge Connect ausdrücklich als ursprüngliche Referenz (§9).

**Edge Connect** läuft in vier Schritten:

1. **Vorfilter:** Ausgewählte Kanten, deren angrenzende Faces keine *andere* ausgewählte Kante
   enthalten, werden gar nicht erst geschnitten (sie könnten nie verbunden werden).
2. **Schneiden:** Alle übrigen Kanten werden in der Mitte geteilt.
3. **Verbinden über Vertex Connect, pro Face:** Für jede Face werden die neuen Mittelpunkte auf
   ihrem Rand in Randreihenfolge gesammelt. Zwei Punkte → eine Kante. Mehr als zwei → die Punkte
   werden reihum verbunden (inneres Polygon). Scheitert das, werden die jeweils nächstgelegenen
   Punkte verbunden.
4. **Aufräumen:** Mittelpunkte, die am Ende keine Verbindung bekommen haben, werden wieder entfernt.

Folgerungen (**INTERPRETATION** des Codes):
- Die Face-Größe spielt keine Rolle. Ngons, Dreiecke, Quads werden gleich behandelt.
- Benachbarte Kanten einer Face werden verbunden → Eck-Schnitt mit Dreieck.
- Eine nicht verbindbare Auswahl erzeugt **keinen Fehler**, sondern wirkt einfach nicht.
- Der „kind v"-Fall (zwei Kanten ohne gemeinsame Face) ergibt in Wings **nichts** — beide Kanten
  fallen im Vorfilter heraus.

Außerdem im Code vorhanden (**FAKT**): Varianten „Connect multiple" (mehrere parallele Schnitte,
Anzahl interaktiv) und „Connect + Slide". Über die Tools-Menü-Variante lassen sich Vertex- und
Kanten-Klicks frei mischen (dokumentiert im Wings-Forum; nicht im Code geprüft).

**Vorbehalt:** Wings ist Referenz, nicht Zielarchitektur. Übernommen wird hier nur das Verständnis
der Semantik, kein Code.

---

## 3. Probe: Wings-artige Semantik auf den Mirai-Core-Primitiven

`experiments/topology/connect_per_face_probe.py` bildet Schritt 1–3 aus §2 **nur mit vorhandenen
Core-Funktionen** nach (`split_edge`, `connect_vertices`). Kein Playground-Eingriff, keine
Core-Änderung. Alle Ergebnisse bestehen die Struktur-Invarianten aus `tests/mesh_invariants.py`.

Testfeld: 4×4-Quad-Raster.

| Szenario | aktuelles Tool | Probe (pro Face) | Faces nach Eckenzahl (Probe) |
|---|---|---|---|
| A  Teilschnitt über 1 Quad | ✅ | ✅ 1 Kante | 15×4, 2×5 |
| B  Teilschnitt über 2 Quads | ✅ | ✅ 2 Kanten | 16×4, 2×5 |
| C  Rand → Rand | ✅ | ✅ 4 Kanten | 20×4 |
| D  Ecke abschneiden | ❌ | ✅ 1 Kante | 1×3, 13×4, 3×5 |
| E  „kind v" | ⚠️ freie Kante | — nichts (beide herausgefiltert) | unverändert |
| F  Lücke von 1 Quad | ❌ | — nichts (herausgefiltert) | unverändert |
| G  Pfad knickt um 90° | ❌ | ✅ 2 Kanten | 1×3, 14×4, 3×5 |
| I  alle 4 Kanten eines Quads | ❌ interner Fehler („FaceId(5)") | ✅ inneres Viereck | 4×3, 12×4, 4×5 |
| A2 Teilschnitt fortsetzen | ❌ | ⚠️ siehe unten | 14×4, 4×5 |

**Befund A2 (wichtig):** Selbst mit Wings-artiger Semantik lässt sich ein Schnitt **nicht sauber
am vorhandenen Mittelpunkt fortsetzen**, solange die Auswahl nur aus Kanten besteht. Um
weiterzuschneiden, muss man die halbe Kante auswählen — die wird dann *erneut* geteilt, an der
Viertelposition (y = 1,25 statt 1,5). Der vorhandene Mittelpunkt bleibt ungenutzt.

**INTERPRETATION:** „Weiterschneiden von einem vorhandenen Punkt aus" ist mit einer reinen
Kanten-Auswahl grundsätzlich nicht ausdrückbar. Es braucht einen Vertex als Startpunkt. Das
berührt Connect Vertices (Punkt 3 der Priorisierung) — es ist eine **Kopplung**, keine Entscheidung.

---

## 4. Designraum — die offenen Fragen, geordnet

Jede Frage mit Optionen, Evidenz und Zuständigkeit. „Zuständigkeit" folgt dem Artist-Attention-Filter:
Mechanik entscheidet der Agent anhand von Tests, Produktverhalten entscheidet der Artist.

### D1 — Welche Kanten werden miteinander verbunden?

> **Artist-Verdikt (2026-09-21, Connect Lab):** D1-a (Streifen, Baseline) → **REJECT**.
> D1-b (pro Face, Wings-artig) → **KEEP**. Gespielt auf dem 8×8-Raster, Aufgaben 1–4.
> Aufgabe 1 (Weiterschneiden) hakte erwartungsgemäß in beiden Varianten — bestätigt D5,
> ist kein Urteil über D1. Damit ist „ganze Loop oder nichts" als alleinige Connect-Semantik
> abgelehnt; die Face-Größen-unabhängige Semantik ist die neue Grundlage.

| Option | Beschreibung | Folge |
|---|---|---|
| D1-a (heute) | Nur gegenüberliegende Kanten in Quads, als Kette | Streifen-Schneider |
| D1-b | Pro Face: alle ausgewählten Kanten dieser Face (Wings) | Ecken, Knicke, Ngons möglich |
| D1-c | Pro Face, aber nur Paare gegenüberliegender Kanten, beliebige Face-Größe | Fortsetzung durch Ngons, keine Ecken |

Mechanisch sind alle drei machbar (Probe). **Welche sich richtig anfühlt, ist Product Truth → Artist.**

### D2 — Dürfen Nicht-Quads beteiligt sein?

Mechanisch: ja, keine Core-Änderung nötig (F9, Probe). Die Ablehnung heute ist eine Scope-Grenze
des Werkzeugs, keine technische Notwendigkeit. Folgefrage nur für den Artist: ob es *gewollt* ist,
dass Connect Dreiecke erzeugen kann (D, G, I).

### D3 — Mehr als zwei ausgewählte Kanten in einer Face

Wings bildet ein inneres Polygon (I). Alternativen: Fehler, nur die Paare verbinden, oder ein Kreuz
(„+", vier Quads) — das heutige Tool *plant* genau dieses Kreuz, scheitert aber an der Ausführung (F10).
Welches Ergebnis ein Artist bei „alle vier Kanten ausgewählt" erwartet, ist offen.
**Artist-Frage**, sobald D1-b im Spiel ist.

### D4 — Nicht verbindbare Auswahl: Fehler oder stilles Nichts?

Heute: Fehlermeldung im HUD. Wings: nichts passiert, ohne Meldung. Das ist eine
Signalling-Frage (Research Map, Querschnittseigenschaft) → **Artist**, aber mit geringem Gewicht.

### D5 — Weiterschneiden von einem vorhandenen Punkt

> *Weiterführung 2026-09-21:* aufgegriffen in `docs/architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md`
> (Knife + Connect Vertices über eine gemeinsame Schnitt-Engine).

Mit Kanten-Auswahl allein nicht sauber lösbar (A2). Braucht einen Vertex-Anteil in der Auswahl
oder eine interaktive Variante. **Kopplung an Connect Vertices** — wird bei der Priorisierung von
Punkt 3 relevant.

### D6 — „kind v" und die Core-Ausnahme `add_edge()`

> *Weiterführung 2026-09-21:* als Entscheidungsfrage B4 in AD-017 (PROPOSED).

- **Befund (FAKT, Test F7):** Auf dem Raster, mit dem der Fall abgesichert ist, liegt die erzeugte
  freie Kante genau auf den vorhandenen Kanten und teilt keine Face.
- **Referenz (FAKT, Wings-Code):** Dieselbe Auswahl bewirkt in Wings nichts.
- **Konsequenz:** Die Begründung der Core-Ausnahme `Mesh.add_edge()` (CORE_V1_FREEZE, AP-05) stützt
  sich auf einen Fall, dessen Ergebnis geometrisch nicht sinnvoll erscheint.

Das ist nach `AGENTS.md` §5 **ein dokumentiertes Problem, keine Entscheidung.** Nächster Schritt
wäre ein Architektur-Review mit Alternativen (z. B. `add_edge()` behalten, weil andere künftige
Anwendungsfälle es brauchen könnten; den „kind v"-Zweig aus Connect entfernen; beides). Hier wird
**nichts** davon umgesetzt.

**Offen:** Ob es einen Anwendungsfall gibt, in dem „kind v" auf nicht-planarer Geometrie etwas
Sinnvolles erzeugt. Nicht gefunden, aber auch nicht ausgeschlossen.

### D7 — Loop Insert hängt an Connect

`loop_insert()` = Ring-Erkennung + `connect_selected_edges()`. Jede Semantikänderung an Connect
ändert potenziell Loop Insert. **Mechanische Anforderung (vom Agent prüfbar):** Loop-Insert-Verhalten
bleibt identisch (bestehende Tests `test_topology_loop_insert.py`) oder Loop Insert wird von der
Connect-Semantik entkoppelt. Auf dem Ring-Fall (C) liefern heutiges Tool und Probe dasselbe Ergebnis.

### D8 — Was ist nach Connect ausgewählt? (Residue)

Heute: die neuen Kanten. Das ist die Residue-Frage aus der Research Map. Nur notiert.

---

## 5. Was entschieden werden kann — und von wem

**D1 ist entschieden (siehe §4).** Die Tabelle unten gilt unverändert für D2–D8; D1 dort nur
noch als Referenz.

| Frage | Wer | Grundlage |
|---|---|---|
| Ist Ngon-/Ecken-Connect mit dem Core machbar? | Agent — **beantwortet: ja** | F9, Probe, Invarianten |
| Braucht es dafür eine Core-Änderung? | Agent — **beantwortet: nein** (für D1–D4) | Probe |
| D1 / D2 / D3 / D4 — welches Verhalten | **Artist** | Artist-Test (unten) |
| D5 — Vertex-Anteil | **Artist**, Priorität | koppelt an Punkt 3 |
| D6 — `add_edge()` / „kind v" | Architektur-Review | AGENTS.md §5 |
| D7 — Loop Insert unverändert halten | Agent | bestehende Tests |

Eine Änderung der Connect-*Semantik* im Playground ist keine Architekturgrenze, sondern eine
Werkzeug-Verhaltensfrage — sie gehört nach AD-013 in den Playground, und ihre Richtigkeit ist
Product Truth.

---

## 6. Vorbereiteter Artist-Test (M4) — gebaut, noch nicht gespielt

**Ziel:** In wenigen Minuten erleben, ob sich Wings-artiges Connect (D1-b) richtiger anfühlt als
das heutige Streifen-Connect (D1-a).

**Stand 2026-09-21:** D1-b ist als umschaltbare Playground-Variante gebaut (Lab-Override nach
AD-013 A2). Die Baseline bleibt Standard und unverändert; Loop Insert nutzt weiterhin die Baseline.

- Familie `connect` im Playground: `Tab` bis `connect`, `M` wechselt zwischen
  „Streifen (nur Quads)" und „Pro Face (Wings-artig)". **Keine neue Taste** — `C` bleibt Connect.
- Testkörper: `python playground/run.py grid` (8×8-Quad-Raster) oder `… head`.
- Code: `playground/topology_tools/connect_per_face.py`, `playground/experiments/connect/`
- Tests: `playground/tests/test_connect_lab.py`
- Verdikt-Vorlage: `playground/experiments/connect/decision.md`

Bewusste Festlegungen **nur für den Test** (keine Antworten auf D3/D4):
- Nicht verbindbare Auswahl → dieselbe Fehlermeldung im HUD wie die Baseline. So bleibt das
  Signalling zwischen den Varianten gleich und verfälscht den Vergleich nicht (Research Map §9).
- Bliebe ein Mittelpunkt unverbunden, wird die ganze Operation abgelehnt statt — wie in Wings —
  den Punkt wieder aufzulösen. Dafür fehlt ein Vertex-Dissolve; der Fall tritt nach dem Vorfilter
  praktisch nicht auf.
- Mehr als zwei ausgewählte Kanten in einer Face → inneres Polygon wie in Wings (Szenario I).

**Aufgaben** (auf einem vorbereiteten Quad-Stück, je Variante):

1. Einen Schnitt über zwei Quads machen und dann noch ein Quad weiter verlängern.
2. Eine Ecke abschneiden.
3. Einen Schnitt um eine Ecke herumführen (Knick).
4. Aufgabe L1 aus der Topologie-Research §15.11: in einer markierten Zone mehr Kontrolle schaffen,
   ohne dass Loops die Zone verlassen.

**Beobachten:** Kommt Manu ans Ziel? Wie viele Versuche? Wo entsteht Frust? Welche Ergebnisse
würde er behalten?

**Verdikt je Variante:** KEEP / ITERATE / REJECT / UNKNOWN.
Aufgabe 1 wird in beiden Varianten Reibung zeigen (A2) — das ist erwartet und ein Befund für D5,
kein Urteil über D1.

---

## 7. Was nicht untersucht wurde

- Wie Blender, Maya, Modo oder Mirai selbst Connect bei Ngons behandeln (nur Wings geprüft).
- Wie Attribute (UV, Weights, Morphs) bei Eck-Schnitten mitgeführt werden — Spec §10, später.
- Verhalten auf Non-Manifold-Geometrie.
- Die praktische Lesbarkeit von Ngons im Viewport (Darstellung, Selektion).
