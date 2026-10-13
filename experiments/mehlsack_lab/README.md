# Mehlsack Lab (WP-MEHLSACK-LAB-01, Slice 1: Move)

**Status: Nicht Artist-validiert.** Gebaut und automatisch getestet; kein Verdikt von Manu liegt vor.
Discovery (Typ B): Das Lab bereitet ein Artist-Verdikt vor, es entscheidet nichts und befördert nichts.

Frage des Labs: **Ist „das Mesh ist die Oberfläche“ (Loop/Ring hovern und direkt ziehen, ohne Auswahl) plus eine
Einflusskurve, die unter null gehen darf, eine vielversprechende Richtung?** Slice 1 kann nur **Move**.

Forschungs-Lab unter `experiments/` — nichts in `src/`, `playground/`, `tests/` oder `examples/` wurde geändert.
`src` wird nur gelesen; aus `playground/` wird genau ein Modul importiert (`playground.topology_tools.loop_ring`,
Loop/Ring-Regeln unverändert). Nichts importiert das Lab (Test: `tests/test_import_boundary.py`).

## Starten

Vom Repo-Root, unter Windows und Linux gleich (nur `pyglet` wird zusätzlich gebraucht):

```
python experiments/mehlsack_lab/run.py
```

Beim Start stehen die Tastentabelle, `GL_VERSION` und `GL_RENDERER` in der Konsole.

## Was man sieht

1. **Box bauen** (Start): eine Box, schattiert mit Drahtgitter. Das Mausrad baut sie (Höhe, Breite, Loops, Unterteilung
   rundum); die Statuszeile zeigt Höhe, Breite, `h`, `n` und V/E/F. Die Kamera zoomt nur heraus, wenn die Box aus dem Bild
   wächst. `Enter` übernimmt die Box — auch ohne Unterteilung (dann ist es ein Würfel).
2. **Bearbeiten:** Über eine Kante fahren → ihr **Loop** (oder mit `Tab` ihr **Ring**) leuchtet auf (blasse Hover-Linie),
   seine Vertices sind blasse gelbe Punkte (`w = 1`), die farbigen Punkte zeigen, **was mitgehen wird**:
   warm (rot/orange/rosa) = geht mit, **blau = geht entgegen**. Mit LMB ziehen = verschieben in der Bildebene.
3. **Kurvenfeld** unten links: x = Abstand vom Loop (links 0, rechts der Radius), y = Gewicht. Oberhalb der weißen
   Null-Linie warm getönt, darunter kühl. Vier Punkte lassen sich senkrecht ziehen; die Enden sind fest (1 am Loop,
   0 am Radius).

## Steuerung

Die Tabelle ist `LAB_OVERRIDES` in `lab_bindings.py` (wird beim Start gedruckt; ein Test prüft Gleichheit 1:1).
**Alle lab-lokalen Tasten sind ein Vorschlag für dieses Lab, keine Artist-Entscheidung.** `Q` `W` `E` `R` (AD-016) und
`C` (AD-017) sind reserviert und nicht belegt. Shift+X/Y/Z (Ebenen) gibt es hier nicht.

| Eingabe | Phase | Funktion | Quelle / Hinweis |
|---|---|---|---|
| Alt+LMB ziehen | beide | Orbit | Artist Input Truth |
| Alt+Shift+LMB ziehen | beide | Pan | Artist Input Truth |
| RMB ziehen | beide | Orbit | Production-Default wie src/main.py |
| MMB ziehen | beide | Pan | Production-Default wie src/main.py |
| Mausrad | Bearbeiten | Zoom | Artist Input Truth |
| Mausrad | Box | Höhe ±1 Schritt | lab-lokal (Brief); Mausrad zoomt hier nicht |
| Alt+Mausrad | Box | Breite (= Tiefe) ±1 Schritt | lab-lokal (Brief) |
| Shift+Mausrad | Box | horizontale Loops ±1 | lab-lokal (Brief) |
| Ctrl+Mausrad | Box | Unterteilung rundum ±1 | lab-lokal (Brief) |
| Enter | Box | Box übernehmen → Bearbeiten | lab-lokal (Brief) |
| LMB ziehen | Bearbeiten | Loop/Ring unter dem Cursor direkt ziehen (Move) | lab-lokal; ohne Auswahl |
| LMB im Kurvenfeld ziehen | Bearbeiten | nächsten Kurvenpunkt senkrecht ziehen | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| RMB (während Zug) | Bearbeiten | Zug abbrechen (exakt zurück) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| Tab | Bearbeiten | Loop ↔ Ring (bleibt) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| X | Bearbeiten | Achse X an/aus (bleibt) | Artist Input Truth |
| Y | Bearbeiten | Achse Y an/aus (bleibt) | Artist Input Truth |
| Z | Bearbeiten | Achse Z an/aus (bleibt) | Artist Input Truth |
| Shift+Mausrad | Bearbeiten | Einflussradius ±1 Stufe | wie App (AD-020), PROVISIONAL |
| Ctrl+O | Bearbeiten | Metrik geodesic ↔ euclidean | wie App (AD-020), PROVISIONAL |
| Alt+O | Bearbeiten | Einfluss-Punkte an/aus | wie App (AD-020), PROVISIONAL |
| N | Bearbeiten | Nachführen an/aus | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| 1 | Bearbeiten | Kurve: Smooth | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| 2 | Bearbeiten | Kurve: Mexican Hat (mit Senke) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| Ctrl+Z | Bearbeiten | Undo | Artist Input Truth |
| Ctrl+Y | Bearbeiten | Redo | Artist Input Truth |
| B | Bearbeiten | neue Box (2× B; löscht die History) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| H | beide | Tastenhilfe an/aus | lab-lokal; Artist Truth: H = HUD |
| Esc | beide | Zug/Rückfrage abbrechen, sonst Beenden | lab-lokal; Q bewusst nicht belegt |

Hinweise: In der Artist Input Truth sind `1`/`2` die Auswahlmodi und `H` der HUD-Schalter — dieses Lab hat keine
Auswahl und zeigt das HUD immer, deshalb sind die Tasten hier anders belegt (Handoff §4). Shift-, Ctrl- und Alt+Mausrad:
Manche Windows-Treiber melden das als horizontales Scrollen; dann liest das Lab `scroll_x` (Regel aus `src/main.py`,
Richtung auf dem Referenz-PC unbestätigt).

## Praxistest für Manu (ca. 10 Minuten)

Start im Repo-Ordner: `python experiments/mehlsack_lab/run.py`

1. **Box bauen:** Mausrad = Höhe, Alt+Mausrad = Breite, Shift+Mausrad = horizontale Loops, Ctrl+Mausrad = Unterteilung rundum. Das Drahtgitter folgt sofort. Mit `Enter` in den Bearbeiten-Modus. (Einmal neu starten und direkt `Enter` drücken, ohne Unterteilung — muss auch gehen.)
2. **Loop finden:** Über eine horizontale Kante fahren. Der ganze Loop leuchtet auf, farbige Punkte zeigen, was mitgehen wird. `Tab` schaltet auf Ring um und zurück.
3. **Ziehen:** Einen mittleren Loop mit gedrückter linker Maustaste nach oben ziehen (mit `Y` nur senkrecht). Der Sack wird oben gestaucht, unten gestreckt. `Shift+Mausrad` ändert den Einflussradius.
4. **Negativ:** Im Kurvenfeld unten links einen mittleren Punkt unter die Null-Linie ziehen (oder `2` für das Preset mit Senke). Blaue Punkte = diese Bereiche bewegen sich **entgegen** der Zugrichtung. Noch einmal ziehen.
5. **Nachführen:** Direkt nach einem Zug die Kurve oder den Radius ändern — der letzte Zug passt sich live an. `N` schaltet das aus; vergleichen.
6. **Asymmetrisch:** Einen Loop schräg oder einen Ring an einer Seite ziehen.
7. `Ctrl+Z` / `Ctrl+Y` zwischendurch.

**Deine Verdikte** (je KEEP / ITERATE / REJECT / UNKNOWN):
- (a) Box per Mausrad bauen
- (b) Loop/Ring per Hover finden und direkt ziehen (ohne Auswahl)
- (c) Negative Gewichte als Werkzeug
- (d) Kurvenfeld (Bedienung, Lesbarkeit)
- (e) Nachführen der letzten Geste
- Frage: Konntest du **vor** dem Ziehen erkennen, was mitgeht?

Hinweise: Im Box-Modus zoomt das Mausrad nicht (es gehört der Box). Taille/Bauch geht in diesem Schritt noch nicht — dafür braucht es Scale (nächster Schritt). Alle Tasten sind Vorschläge für dieses Lab, keine Entscheidung.

| Punkt | Verdikt (KEEP / ITERATE / REJECT / UNKNOWN) | Notiz |
|---|---|---|
| (a) Box per Mausrad |  |  |
| (b) Loop/Ring hovern und direkt ziehen |  |  |
| (c) Negative Gewichte |  |  |
| (d) Kurvenfeld |  |  |
| (e) Nachführen |  |  |

Vor dem Ziehen erkennbar, was mitgeht? _(leer)_

## Engineering-Annahmen (nicht Artist-entschieden)

Aus dem Handoff (E1–E9, A1–A4), so gebaut:

- **E1 Host:** eigenes Fenster nach dem Muster des Subdivision Labs (`src/viewport`-Draw-Pfad, `src` nur gelesen) —
  kein App-Pfad-Lab (AD-013 H2-R6), nicht im Playground (Artist 2026-10-08).
- **E3 Loop/Ring:** `playground.topology_tools.loop_ring` wird gelesen, nicht kopiert und nicht verschoben.
- **E4 Vorzeichen-Gewichte:** `w ∈ [−1, 1]`, Seeds (alle Vertices der Loop-/Ring-Kanten) `w = 1`, Bewegung `w · Δ`,
  `w == 0` nicht im Op-Set, kein Clamp, kein `abs()`. `SignedSoftMoveOperation` (`signed_ops.py`) sitzt wie AD-020 Q2-D
  auf den geschützten Hooks von `VertexTransformOperation`; eigener Zustand mit Präfix `_mehlsack_`; eine Geste = ein
  History-Eintrag. Für Gewichte in (0, 1] bitgleich mit `SoftMoveOperation` (Test).
- **E5 Kurve:** x = d/r, y = w; Enden (0, 1) und (1, 0) fest; vier Punkte bei x = 0,2 / 0,4 / 0,6 / 0,8, nur senkrecht;
  PCHIP (Fritsch–Carlson) ohne Überschwingen. Presets: `1` Smooth (`CURVES["smooth"]` an den Punkten abgetastet),
  `2` Mexican Hat (0,70 / 0,10 / −0,35 / −0,30). Alles `PROVISIONAL`.
- **E6 Einfluss:** Abstände unverändert aus `mirai.soft_selection.METRICS`, `w = Kurve(d/r)`, Standard geodesic;
  Radiusstufen und Start 15 % wie AD-020 E5 (Prozent des Bounding-Radius der Box beim `Enter`).
- **E7 Nachführen:** (a) Vorschau — jede Kurven-/Radius-/Metrik-Änderung rechnet die Hover-Punkte sofort neu.
  (b) Nachführen (`N`, Start: an) — nach einem Zug wertet eine solche Änderung den **letzten Zug** neu aus
  (`Start + w' · Δ_gesamt`) und **ersetzt** seinen History-Eintrag; endet mit dem nächsten Zug, Undo/Redo, `N` oder
  einer neuen Box. Mit `N` aus behält ein Zug seine Gewichte aus `begin()`.
- **E8 Punkte:** positive Gewichte warm, negative blau, `w == 0` nicht gezeichnet (siehe offener Punkt O1).
- **E9 Box:** Seitenwände `n × h` Quads pro Seite, Deckel `n × n`, nur Quads, geschlossen, Außen-Normalen; Loops = `h − 1`;
  Ecken der Deckel haben Valenz 3, Loops auf der Kante oben/unten stoppen dort (Regel von `loop_ring.py`).
  Grenzen `h, n ∈ [1, 32]`; Höhe/Breite in Schritten von 0,25 zwischen 0,25 und 8 (Start 2 × 2 × 2).
- **A1–A4** wie im Handoff angenommen (Kurvenfeld nur im Lab; Breite = Tiefe; Ctrl+Rad = Unterteilung rundum;
  beide Lesarten von „sofort“ gebaut).

Zusätzlich vom Agenten gesetzt (beim Bauen nötig geworden, alle `PROVISIONAL`):

- **Topologie-Index** (`targets.TopologyIndex`): `loop_ring` ruft `Mesh.vertex_edges()` auf, im Core V1 ein O(E)-Scan
  (ein 128-Kanten-Loop auf der 32 × 32-Box ≈ 1,5 Mio. Kantenprüfungen pro Hover). Das Lab gibt `loop_ring` stattdessen
  ein Objekt mit denselben fünf Abfragen aus Tabellen, die beim `Enter` einmal über die öffentliche Core-API gebaut
  werden (die Topologie ändert sich im Bearbeiten-Modus nie). Gleiche Listen, gleiche Reihenfolge; ein Test vergleicht
  jeden Loop und Ring mit der Traversierung auf dem Core-Mesh. Die Regeln bleiben die von `loop_ring`.
- **Hover über dem Kurvenfeld:** Der letzte Mesh-Hover bleibt stehen, damit man beim Kurvenziehen die Punkte sieht.
- **Kurve während eines Zugs:** ändert nur die Vorschau; der laufende Zug behält seine Gewichte (AD-020 E3).
- **`N` beendet das Nachführen** des letzten Zugs (er bleibt so, wie er ist); wieder an schaltet es erst für den
  nächsten Zug ein.
- **Nachführen über die öffentliche History-API:** `undo()` (exakter Startzustand) → neue Gewichte dort messen →
  bei gleichen Gewichten `redo()`, sonst ein neuer Ein-Schritt-Zug, dessen `push()` den alten Eintrag verwirft. Kein
  Zugriff auf private Member der `HistoryStack`.
- **Anker des Zugs:** das erste Ende der gehoverten Kante (ein Seed); Bildebenen-Delta wie `MoveTool._on_update`.
- **Kamera im Box-Modus:** zoomt nur heraus, wenn die Box aus dem gerahmten Bereich wächst, damit Größenänderungen
  sichtbar bleiben. Die Box steht mittig im Ursprung.
- **HUD-Hintergrund:** dunkel, halbtransparent — graue Schrift war über der hellen Box-Oberseite unlesbar.

## Rotate / Scale mit Vorzeichen-Gewichten (nur Analyse, kein Code — bereitet Slice 2 vor)

**Rotate:** Winkel `w · θ` um dieselbe Achse und denselben Pivot. Negative Gewichte drehen entgegen; Rotationen um eine
Achse addieren sich, also bleibt die Geste pfadunabhängig wie heute. Keine Singularität. Ein Vertex mit `w < 0` weit vom
Pivot läuft einen langen Bogen (`Abstand · |w| · θ`) — bei großem Radius kann das gegenläufige Verdrehen („S-Kurve“)
stärker wirken als erwartet.

**Scale (linear, wie die App):** Faktor `g = 1 + w (F − 1)`. Für `w < 0` ist `g = 1 − |w| (F − 1)`: beim Vergrößern
(`F > 1`) schrumpft der Bereich, beim Verkleinern (`F < 1`) wächst er — genau „Taille mit Bauch daneben“. Bei
`F = 1 + 1/|w|` wird `g = 0`: die Vertices fallen auf den Pivot; darüber wird `g < 0`, sie stülpen durch den Pivot
hindurch nach außen um.

| w | F = 0,5 | F = 1,5 | F = 2 | F = 3 | F = 5 | g = 0 bei F = |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0,5 | 1,5 | 2 | 3 | 5 | — |
| 0,5 | 0,75 | 1,25 | 1,5 | 2 | 3 | — |
| −0,25 | 1,125 | 0,875 | 0,75 | 0,5 | **0** | 5 |
| −0,5 | 1,25 | 0,75 | 0,5 | **0** | −1 | 3 |
| −1 | 1,5 | 0,5 | **0** | −1 | −3 | 2 |

Zum Vergleich die Potenzformel der App-Vergleichssuite (`F ** w`): für `F > 0` immer positiv (`w = −1`, `F = 2` → 0,5),
also kein Zusammenfallen und kein Umstülpen, aber nicht linear. Welche Formel für negative Gewichte trägt, ist eine
Frage für Slice 2 (nach Manus Verdikt).

## Messung (Container, **kein Referenz-PC**)

`python experiments/mehlsack_lab/bench.py --host "<Label>"` (Referenz-PC zusätzlich `--visible`). Jede Zahl nennt, wo sie
gemessen wurde. Agent-Lauf 2026-10-12, `cloud container (Linux, Xvfb, llvmpipe), kein Referenz-PC`, Box h = n = 32
(V 6146 / E 12 288 / F 6144), Loop auf halber Höhe (128 Kanten), Fenster 1280 × 800 unsichtbar, 10 Läufe,
Median / Max in ms:

| Radius | hover pick | hover pick (cold) | hover change | Einfluss-Vertices | drag step | drag sync | nachführen |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 15 % | 9.07 / 13.45 | 37.12 / 58.06 | 5.40 / 10.38 | 896 | 0.64 / 1.19 | 28.41 / 56.67 | 1.93 / 2.87 |
| 50 % | 8.98 / 11.18 | 37.46 / 52.82 | 8.96 / 10.14 | 2944 | 2.04 / 2.57 | 44.33 / 53.44 | 6.31 / 7.63 |
| 200 % | 10.04 / 15.05 | 39.74 / 59.59 | 17.19 / 26.32 | 6146 | 4.60 / 6.92 | 71.02 / 105.20 | 14.86 / 22.81 |

- *hover pick* = `pick_nearest_edge` (Production, `PickCache` + Occlusion) bei unveränderter Kamera; *cold* = direkt
  nach einer Positionsänderung (Cache-Neuaufbau). *hover change* = Loop + Vorzeichen-Einfluss einer neu gehoverten Kante.
  *drag step* = der Event-Handler (Op-Update + Dirty-Markierung). *drag sync* = der nächste Frame (`RenderMesh.sync()`,
  Overlays, Zeichnen, `glFinish`). *nachführen* = eine Kurvenänderung, Abstände aus dem Cache.
- Aufteilung von *drag sync* (Median, gleiche Box): `RenderMesh.sync()` 10 / 25 / 50 ms (15 / 50 / 200 %), Drahtgitter- und
  Punkte-Overlay neu 7 ms, Zeichnen + `glFinish` ohne Änderungen 10–14 ms (Software-GL).
- **Beobachtung, keine Interpretation:** Im Container liegen auf der 32 × 32-Box der Drag-Schritt (0,6–4,6 ms) und
  Nachführen bis 50 % (Median 1,9 / 6,3 ms) unter 8 ms; Hover-Pick (~9 ms), Hover-Wechsel ab 50 %, Nachführen bei 200 %
  und der Frame nach einem Drag-Schritt (28–71 ms) liegen darüber. Der größte Posten ist `RenderMesh.sync()` (ein
  `store.update` pro bewegtem Vertex und Bounds über alle Vertices — bekannter Hotspot, im Subdivision Lab gemessen, hier
  nicht angefasst). Der Referenz-PC entscheidet.
- **Box-Modus:** ein Mausrad-Schritt baut Mesh und `RenderMesh` neu (Topologie-Änderung). Bei 31 → 32 × 32 dauert das im
  Container ~320 ms inkl. Frame (Mesh allein 42 ms), `Enter` ~180 ms — bei hohen Unterteilungen hakt das Rad spürbar.
- Zum Vergleich die 12 × 6-Box (V 362 / E 720 / F 360), gleicher Lauf, Median in ms bei 15 / 50 / 200 %: hover pick
  0,47 / 0,46 / 0,50 · cold 2,1 · hover change 0,39 / 0,57 / 0,89 · drag step 0,07 / 0,16 / 0,26 · drag sync
  4,1 / 4,9 / 6,1 · nachführen 0,26 / 0,49 / 0,83.

## Ergebnisse und offene Punkte

Was im Fenster läuft (unter Xvfb durchgespielt, Screenshot-geprüft; nicht auf dem Referenz-PC): Box per Mausrad,
`Enter`, Hover mit Loop/Ring-Linie, Seeds und Vorzeichen-Punkten, LMB-Zug mit X/Y/Z, Abbruch mit Esc/RMB, Kurvenfeld
mit Nachführen, Presets, Undo/Redo, neue Box, Tastenhilfe. Was nur headless getestet ist: die Rechenregeln (Box,
Loop/Ring, Kurve, Einfluss, Op, Nachführen, Zustandsmaschine) — dort exakt, siehe Tests.

Beobachtungen beim Bauen (keine Bewertung — das ist Manus Teil):

- **B1 Falten:** Negative Gewichte lassen Flächen früher umklappen. 16 × 6-Box (Zeilenabstand 0,125), Loop auf halber
  Höhe senkrecht gezogen, Radius 50 %, Anzahl umgeklappter Flächen bei Δ = 0,1 / 0,2 / 0,3 / 0,5 / 0,8:
  Smooth 0 / 0 / 0 / 24 / 96 · Mexican Hat 0 / 0 / 48 / 72 / 96 · tiefe Senke (0,3 / −1 / −1 / −0,5) 0 / 24 / 72 / 96 / 120
  (geodesic und euclidean gleich). Grund: Ein Ring mit `w < 0` läuft dem Seed entgegen, der Seed überholt ihn.
- **B2 Smooth-Preset ≠ Smooth:** vier Punkte tragen Smoothstep nur bis 0,0098 genau; die PCHIP-Enden haben die Steigung
  −0,16 statt 0, die Einflussgrenze ist also nicht mehr glatt (C¹) wie in der App.
- **B3 Vorschau zeigt Gewichte, nicht Bewegung:** die Punkte färben nach `w`, nicht nach der späteren Richtung; wie gut
  man „was geht entgegen“ vor dem Zug liest, ist Manus Frage.

Offene Fragen (nicht im Code entschieden):

- **O1 Farben:** Die App-Bänder laufen innerhalb der *positiven* Gewichte von warm nach kalt (rot, orange, türkis, blau).
  Damit „blau = entgegen“ eindeutig ist, behält das Lab die zwei warmen App-Farben und ersetzt die kühlen schwachen
  Bänder durch zwei Rosatöne (lab-lokal). Ob die App-Farben selbst so bleiben, ist nicht Teil dieses Labs.
- **O2 Leistung** auf dichten Boxen (siehe Messung): erst der Referenz-PC zeigt, ob 32 × 32 flüssig genug ist.
- **O3 Pan im Subdivision Lab** ist noch Shift+LMB, die Artist Input Truth sagt seit 2026-09-26 Alt+Shift+LMB; dieses
  Lab folgt der Truth. Nicht hier geändert.
- **O4** Ob Loops an den Deckelecken weiterlaufen sollen (Valenz 3), ist eine `loop_ring`-Regel und bewusst unverändert.
- **O5** Scale/Rotate mit Vorzeichen-Gewichten: Formelwahl für `w < 0` (siehe Analyse oben) — Slice 2.

Nächster Schritt: Manus Praxistest (oben). Danach Slice 2 (Scale/Rotate) nur nach Verdikt.

## Tests

```
xvfb-run -a python -m pytest experiments/mehlsack_lab/tests -q     # Linux headless
python -m pytest experiments/mehlsack_lab/tests -q                 # Windows / mit Display
```

Nicht in `pytest.ini` (`testpaths`) — Aufruf per Pfad. GL-Tests überspringen sauber ohne GL.
Box (Zählung, Quads, geschlossen, Außen-Normalen, Mesh-Invarianten), Loop/Ring auf der Box (inkl. Index = Core-Traversierung),
Kurve (Enden, kein Überschwingen, Smooth-Toleranz 0,01, Negativ), Einfluss (bitgleich zu `compute_influence` mit Smooth),
Op (bitgleich zu `SoftMoveOperation` für (0, 1], `w · Δ`, N = 1 Schritt, Commit/Cancel/Undo/Redo, AST-Scan),
Nachführen, Zustandsmaschine, Tastentabelle = README, Import-Grenze, GL-Smoke- und Event-Pfad, Bench-Lauf.
