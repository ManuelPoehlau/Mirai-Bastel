# Mehlsack Lab (WP-MEHLSACK-LAB-01, Slice 1 + 2a: Move)

**Status: Slice 1 Verdikte von Manu (2026-10-13) liegen vor; Slice 2a nicht Artist-validiert.** Slice 2a ist gebaut
und automatisch getestet (siehe [Slice 2a](#slice-2a-2026-10-13)); sein Praxistest steht aus.
Discovery (Typ B): Das Lab bereitet ein Artist-Verdikt vor, es entscheidet nichts und befördert nichts. KEEP heißt
hier nicht Promotion — nichts verlässt `experiments/`.

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

1. **Box bauen** (Start): eine Box, schattiert mit Drahtgitter. Das Mausrad baut sie (Höhe, Breite, Tiefe, Loops,
   Unterteilung rundum); die Statuszeile zeigt Höhe, Breite, Tiefe, `h`, `n` und V/E/F. Die Kamera zoomt nur heraus, wenn die Box aus dem Bild
   wächst. `Enter` übernimmt die Box — auch ohne Unterteilung (dann ist es ein Würfel).
2. **Bearbeiten:** Über eine Kante fahren → ihr **Loop** (oder mit `Tab` ihr **Ring**) leuchtet auf (blasse Hover-Linie),
   seine Vertices sind blasse gelbe Punkte (`w = 1`), die farbigen Punkte zeigen, **was mitgehen wird**:
   warm (rot/orange/rosa) = geht mit, **blau = geht entgegen**. Mit LMB ziehen = verschieben in der Bildebene.
   Eine Kante am oberen oder unteren Rand gibt den ganzen Rand-Loop rund um die Box (Slice 2a).
3. **Kurvenfeld** unten links: x = Abstand vom Loop (links 0, rechts der Radius), y = Gewicht. Oberhalb der weißen
   Null-Linie warm getönt, darunter kühl. Seit Slice 2a eine Bézier-Kurve: vier Punkte (weiße Kreise, als Raute nach
   einem Knick) lassen sich frei verschieben, jeder hat zwei Handles (blaue Quadrate); die Enden sind fest (1 am
   Loop, 0 am Radius), ihr einzelnes Handle lässt sich ziehen.
4. **Flächen-Vorschau** (`P`, Slice 2a, standardmäßig aus): die betroffenen Flächen orange (geht mit) oder blau (geht
   entgegen), je kräftiger, desto stärker.

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
| Alt+Mausrad | Box | Breite ±1 Schritt | lab-lokal (Brief) |
| Alt+Shift+Mausrad | Box | Tiefe ±1 Schritt | lab-lokal (Slice 2a, Annahme A5) |
| Shift+Mausrad | Box | horizontale Loops ±1 | lab-lokal (Brief) |
| Ctrl+Mausrad | Box | Unterteilung rundum ±1 | lab-lokal (Brief) |
| Enter | Box | Box übernehmen → Bearbeiten | lab-lokal (Brief) |
| LMB ziehen | Bearbeiten | Loop/Ring unter dem Cursor direkt ziehen (Move) | lab-lokal; ohne Auswahl |
| LMB im Kurvenfeld ziehen | Bearbeiten | Kurvenpunkt oder Handle ziehen (Handles bleiben in Linie) | lab-lokal (Slice 2a, Vorschlag, keine Artist-Entscheidung) |
| Alt+LMB im Kurvenfeld ziehen | Bearbeiten | Handle allein ziehen = Knick (Punkt wie ohne Alt) | lab-lokal (Slice 2a, Vorschlag, keine Artist-Entscheidung) |
| Doppelklick auf Kurvenpunkt | Bearbeiten | Handles des Punkts wieder weich (automatisch) | lab-lokal (Slice 2a, Vorschlag, keine Artist-Entscheidung) |
| RMB (während Zug) | Bearbeiten | Zug abbrechen (exakt zurück) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| Tab | Bearbeiten | Loop ↔ Ring (bleibt) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| X | Bearbeiten | Achse X an/aus (bleibt) | Artist Input Truth |
| Y | Bearbeiten | Achse Y an/aus (bleibt) | Artist Input Truth |
| Z | Bearbeiten | Achse Z an/aus (bleibt) | Artist Input Truth |
| Shift+Mausrad | Bearbeiten | Einflussradius ±1 Stufe | wie App (AD-020), PROVISIONAL |
| Ctrl+O | Bearbeiten | Metrik geodesic ↔ euclidean | wie App (AD-020), PROVISIONAL |
| Alt+O | Bearbeiten | Einfluss-Punkte an/aus | wie App (AD-020), PROVISIONAL |
| P | Bearbeiten | Flächen-Vorschau an/aus (orange = mit, blau = entgegen) | lab-lokal (Slice 2a, Vorschlag, keine Artist-Entscheidung) |
| N | Bearbeiten | Nachführen an/aus | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| 1 | Bearbeiten | Kurve: Smooth | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| 2 | Bearbeiten | Kurve: Mexican Hat (mit Senke) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| Ctrl+Z | Bearbeiten | Undo | Artist Input Truth |
| Ctrl+Y | Bearbeiten | Redo | Artist Input Truth |
| B | Bearbeiten | neue Box (2× B; löscht die History) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| H | beide | Tastenhilfe an/aus | lab-lokal; Artist Truth: H = HUD |
| Esc | beide | Zug/Rückfrage abbrechen, sonst Beenden | lab-lokal; Q bewusst nicht belegt |

Hinweise: In der Artist Input Truth sind `1`/`2` die Auswahlmodi und `H` der HUD-Schalter — dieses Lab hat keine
Auswahl und zeigt das HUD immer, deshalb sind die Tasten hier anders belegt (Handoff §4). Shift-, Ctrl-, Alt- und
Alt+Shift+Mausrad: Manche Windows-Treiber melden das als horizontales Scrollen; dann liest das Lab `scroll_x` (Regel aus
`src/main.py`, Richtung auf dem Referenz-PC unbestätigt). Im Kurvenfeld orbitet Alt+LMB nicht (Slice 2a: Alt+Ziehen an
einem Handle = Knick); Alt+Shift+LMB pannt dort weiter.

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

| Punkt                                  | Verdikt (KEEP / ITERATE / REJECT / UNKNOWN) | Notiz                              |
| -------------------------------------- | ------------------------------------------- | ---------------------------------- |
| (a) Box per Mausrad                    | Iterate                                     | Alt+Scroll für Tiefe hinzufügen    |
| (b) Loop/Ring hovern und direkt ziehen | KEEP                                        |                                    |
| (c) Negative Gewichte                  | KEEP                                        |                                    |
| (d) Kurvenfeld                         | Iterate                                     | Kurven über Bezier Handles formbar |
| (e) Nachführen                         | KEEP                                        |                                    |

Vor dem Ziehen erkennbar, was mitgeht? Manu: Wird sich mit dem optionalem Preview Modus evtl. besser erkennen lassen. Muss getestet werden.

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

Manus Antworten auf die offenen Fragen:

- **O1**: Optionaler Preview Modus (Screenshot aus C4D): The soft selection is displayed with an orange preview, which makes it much easier to select correctly. The Strength parameter is symbolized by the saturation of the orange color. This preview can be switched on and off here.[[2026-1_soft_selection_02_.jpg]]

- **O2**: Läuft soweit ok. Es werden eh noch noch Viewport Perfomance Verbesserungen später
  nötig sein (gollum mesh). Nicht Frage dieses Labs

- **O3**: Artist Truth

- **O4**: Ja, macht in diesem Experiment Sinn

- **O5**: Muss man vergleichen in der Praxis


## Slice 2a (2026-10-13)

**Nicht Artist-validiert.** Setzt Manus zwei ITERATE-Verdikte (a) und (d) und die Antworten zu O1 und O4 von oben um.
Move bleibt die einzige Transform; Rotate/Scale kommt in Slice 2b (eigener Auftrag, danach).

### Was sich geändert hat

- **Tiefe (a):** Breite und Tiefe sind getrennt. Alt+Mausrad = Breite (x), **Alt+Shift+Mausrad = Tiefe** (z); ein
  gemeinsames `n` für beide. Start weiterhin 2 × 2 × 2, Statuszeile zeigt Höhe, Breite, Tiefe.
- **Bézier-Kurve (d):** Das Kurvenfeld ist eine stückweise kubische Bézier-Kurve durch sechs Punkte (statt PCHIP).
  Punkte frei in x (zwischen den Nachbarn) und y; Handles ziehen; Alt+Ziehen an einem Handle = Knick; Doppelklick auf
  einen Punkt = wieder weich. Preset `1` Smooth ist jetzt **exakt** Smoothstep (Beobachtung B2 aus Slice 1 ist weg:
  Endsteigung 0 statt −0,16), `2` Mexican Hat hat die Slice-1-Werte mit weichen Handles und waagrechten Enden.
- **Flächen-Vorschau (O1):** `P` schaltet eine Flächentönung ein: orange = geht mit, blau = geht entgegen, Deckkraft
  ∝ `|w|`, Seeds am stärksten, `w = 0` durchsichtig. Standardmäßig aus; die Punkte (Alt+O) bleiben wie sie sind.
- **Rand-Loop (O4):** Eine Kante am oberen oder unteren Rand gibt den **geschlossenen** Loop rund um die Box
  (`4n` Kanten, über die Ecken). Alle anderen Loops und Ringe bleiben `loop_ring`; senkrechte Eckkanten enden weiter an
  den Ecken.

### Annahmen (Manu korrigiert nur, wenn falsch)

- **A5** (a): Breite und Tiefe unabhängig. **Alt+Mausrad bleibt Breite, Alt+Shift+Mausrad = Tiefe.** (Falls „Alt+Scroll
  für Tiefe“ Alt+Mausrad = Tiefe meinte: zwei Tabellenzeilen tauschen.)
- **A6** (a): ein `n` für Breite und Tiefe.
- **A7** O4 gelesen als „ja, Rand-Loops sollen in diesem Lab um die Box-Ecken weiterlaufen“.
- **A8** O1: negative Gewichte bekommen dasselbe in Blau (die Lab-Regel „blau = entgegen“); nur das Prinzip von C4D
  (Sättigung = Stärke), nicht dessen Look. Der Screenshot `[[2026-1_soft_selection_02_.jpg]]` ist ein Obsidian-Embed und
  **nicht im Repo**; gebaut nach Manus Text.
- **A9** Vorschau standardmäßig aus („optional“); die Punkte (Alt+O) bleiben wie sie sind.

### Engineering-Annahmen (alle `PROVISIONAL`)

- **E10 Tiefe:** `BoxParams.depth` (gleiche Schritte und Grenzen wie die Breite). Kamera-Regel unverändert.
- **E11 Bézier:** x = d/r, y = w; Enden (0, 1) und (1, 0) fest, ihr Handle ziehbar (Endsteigung). Vier innere Punkte:
  x echt zwischen den Nachbarn (Mindestabstand 0,02), y ∈ [−1, 1], je ein Ein- und Aus-Handle. **Garantien durch
  Konstruktion:** alle Kontrollpunkte y ∈ [−1, 1] (konvexe Hülle ⇒ Kurve in [−1, 1], kein Clamp der Ausgabe); in jedem
  Segment sind die Kontroll-x nicht fallend (⇒ x(t) monoton ⇒ die Kurve ist eine Funktion von x). Auswertung: x(t) = x
  pro Segment mit Newton im Bisektions-Intervall (keine Tabelle). Handle-Züge werden in ihre Box geklemmt (x zwischen
  eigenem Punkt und dem anderen Handle des Segments, y in [−1, 1]).
- **E12 Handle-Modi:** Standard *in Linie* (Ein- und Aus-Handle kollinear; das andere Handle dreht mit, behält seine
  Länge und wird zum Punkt hin gekürzt, wenn es sonst seine Box verließe). Alt+Ziehen = Knick für diesen Punkt;
  Doppelklick = wieder in Linie mit automatischer Länge. Pick: nächstes Element in 12 px, Handles vor Punkten.
  Punkte hinzufügen/entfernen: nicht in diesem Slice (offene Frage).
- **E13 Presets:** Smooth = ein Segment (0, 1) → (1, 0) mit Handles (1/3, 1) und (2/3, 0) (x(t) = t, y = smooth(1 − x)),
  per de Casteljau bei x = 0,2 / 0,4 / 0,6 / 0,8 geteilt — vier Punkte, gleiche Kurve. Mexican Hat = 0,70 / 0,10 /
  −0,35 / −0,30 mit automatischen Handles, waagrechte Enden.
- **E14 Vorschau:** lab-lokales Dreieck-Overlay (`lab_preview.GLInfluencePreviewOverlay`, Unterklasse des
  Production-`GLTriangleOverlay` mit eigenem Shader für eine Farbe pro Vertex) über den Flächen mit mindestens einem
  Vertex `w ≠ 0`; Farbe pro Ecke, über die Fläche interpoliert. Tiefentest wie das B5b-Flächen-Highlight (`GL_LEQUAL`
  auf den per Polygon-Offset zurückgesetzten Flächen). **Keine Änderung an `src/viewport`, `RenderMesh` oder dessen
  Shader** (AD-020 §5.1 c bleibt für die App abgelehnt). Neu gebaut bei Hover-Wechsel, Kurven-/Radius-/Metrik-Änderung,
  während des Zugs (mit den Gewichten der Geste) und nach dem Nachführen.
- **E15 Rand-Loop:** `box.rim_vertex_cycles` / `box_rims` nennen die zwei Ränder (Übergang Deckel/Wand); `TargetFinder`
  bekommt sie beim `Enter` und gibt für eine Rand-Kante im Loop-Modus den geschlossenen Rand-Loop (gehoverte Kante
  zuerst). Eine ausdrückliche Lab-Ausnahme vor `loop_ring`; `loop_ring.py` und die `TopologyIndex`-Gleichheit sind
  unverändert, ein Test prüft, dass alle anderen Loops und alle Ringe genau `loop_ring` sind.

Zusätzlich vom Agenten gesetzt (beim Bauen nötig geworden, alle `PROVISIONAL`):

- **„Automatische Länge“** gelesen als automatische Handles: Reichweite 1/3 des Nachbarsegments in x, Steigung nach
  Fritsch–Carlson (0 an einem Hoch-/Tiefpunkt). Mit x linear in t ist das genau das PCHIP-Segment aus Slice 1 — diese
  Handles schießen nie über ihre Punkte hinaus. Endpunkte: waagrechtes Handle.
- **Punkt verschieben:** die Handles wandern mit; ein Handle, das [−1, 1] verlässt, wird zum Punkt hin gekürzt; überlappen
  sich die zwei Handles eines Segments in x, werden beide im gleichen Verhältnis gekürzt (Regel üblicher
  Animationskurven-Editoren).
- **Ziehen im Kurvenfeld:** mit Greif-Versatz (ein Klick ohne Bewegung ändert nichts — so bleibt der Doppelklick
  sauber); jeder Zugschritt wird auf die Kurve vom Drücken angewendet, ein gekürztes Handle wächst also zurück, wenn
  der Cursor zurückgeht. Ein Klick in leere Fläche des Kurvenfelds greift nichts (Slice 1 griff den nächsten Punkt
  irgendwo). Ein Doppelklick auf ein Handle setzt dessen Punkt zurück (so lässt sich auch ein Punkt mit eingeklapptem
  Handle wieder weich machen).
- **Alt+LMB im Kurvenfeld** orbitet nicht mehr (dort gehört Alt dem Knick, E12); auf einem Punkt verschiebt Alt+Ziehen
  ihn wie ohne Alt.
- **Kurvenfeld** 320 × 190 px (Slice 1: 260 × 160), damit Handles greifbar sind.
- **Nur Handle-Modus geändert** (Knick ohne Formänderung): kein Nachführen, nur die Anzeige.
- **Vorschau:** ohne Tiefen-Schreiben gezeichnet (durchscheinend; überlappende Vorschauflächen verdecken sich nicht),
  vor Drahtgitter, Loop-Linie und Punkten. Deckkraft höchstens 0,85 (Seeds), damit die Schattierung sichtbar bleibt.
- **Bench:** `BOX` hat jetzt `depth=1.5` — dieselbe Box wie bei der Slice-1-Messung.

### Beobachtungen beim Bauen (keine Bewertung)

- **R1 Vorzeichenwechsel in einer Fläche:** Die Farben werden pro Ecke interpoliert. Liegt in einer Fläche eine Ecke im
  Orangen und eine im Blauen, mischt sich das über die Fläche; eine exakte Null-Linie innerhalb der Fläche gibt es nicht.
- **R2 Blau auf blaugrau:** Die Production-Schattierung der Box ist bläulich-grau; die blaue Vorschau hebt sich im
  Screenshot (Xvfb, Mexican Hat, Radius 75 %) schwächer ab als die orange. Ob das reicht, ist Manus Frage.
- **R3 Rundung:** Mathematisch bleibt die Kurve in [−1, 1]; die Gleitkomma-Auswertung kann ±1 um wenige ulp
  überschreiten (Fuzz-Test, 2000 zufällige Züge: höchstens 4,4·10⁻¹⁶). Es gibt bewusst keinen Clamp.
- **R4 Eingeklapptes Handle:** Liegt ein Punkt bei y = ±1, kann das gegenüberliegende Handle beim Drehen auf Länge 0
  gekürzt werden (es würde sonst die Box verlassen). Doppelklick holt es zurück.
- **R5 Vorschau-Kosten** nicht gemessen (O2: nicht Frage dieses Labs). Mit `P` an wird die Tönung bei jedem Zugschritt
  neu gebaut.

### Offene Fragen (nicht im Code entschieden)

- **O6** Kurvenpunkte hinzufügen/entfernen (nicht in diesem Slice).
- **O7** Ob die Vorschau linear in `|w|` (Deckkraft) gut liest oder eine andere Abbildung braucht — erst nach Manus Test.
- **O8** Ob „in Linie“ die Länge des anderen Handles in Kurvenkoordinaten (so gebaut) oder auf dem Bildschirm halten soll.

### Praxistest für Manu (ca. 8 Minuten)

Start: `python experiments/mehlsack_lab/run.py`

1. **Tiefe:** Mausrad = Höhe, Alt+Mausrad = Breite, **Alt+Shift+Mausrad = Tiefe**. Eine flache, breite Box bauen. `Enter`.
2. **Rand-Loop:** Über eine Kante am oberen Rand fahren — der Loop läuft jetzt ganz um die Box herum. Hochziehen.
3. **Bézier-Kurve:** Im Kurvenfeld an den Anfassern (Handles) ziehen. Mit Alt an einem Handle ziehen = Knick. Doppelklick auf einen Punkt = wieder weich. Punkte lassen sich jetzt auch seitlich verschieben. `1` = Smooth, `2` = Senke.
4. **Vorschau:** `P` schaltet die Flächen-Vorschau ein: Orange = geht mit, Blau = geht entgegen, je kräftiger, desto stärker. Über verschiedene Loops fahren, Kurve und Radius ändern — erkennst du **vor** dem Ziehen, was passiert?
5. Ziehen, dann mit Nachführen die Kurve nachformen (wie bisher).

**Deine Verdikte** (je KEEP / ITERATE / REJECT / UNKNOWN):

| Punkt | Verdikt (KEEP / ITERATE / REJECT / UNKNOWN) | Notiz |
|---|---|---|
| (a2) Tiefe per Alt+Shift+Mausrad | | |
| (d2) Kurvenfeld mit Bézier-Handles | | |
| (p) Flächen-Vorschau | | |
| (r) Rand-Loop um die Ecken | | |

Vorher erkennbar, was mitgeht — jetzt besser? Manu:

Hinweis: Alle Tasten sind Vorschläge für dieses Lab, keine Entscheidung. Nächster Schritt nach deinem Verdikt: Slice 2b
(Rotate/Scale, O5).

## Tests

```
xvfb-run -a python -m pytest experiments/mehlsack_lab/tests -q     # Linux headless
python -m pytest experiments/mehlsack_lab/tests -q                 # Windows / mit Display
```

Nicht in `pytest.ini` (`testpaths`) — Aufruf per Pfad. GL-Tests überspringen sauber ohne GL.
Box (Zählung, Quads, geschlossen, Außen-Normalen, Mesh-Invarianten, Breite ≠ Tiefe, Ränder), Loop/Ring auf der Box
(inkl. Index = Core-Traversierung; Rand-Loop geschlossen mit `4n` Kanten, alle anderen Loops/Ringe = `loop_ring`),
Bézier-Kurve (Smooth = `3t² − 2t³` auf 10 001 Stellen bis 1e-9, Endsteigung 0, Seed-Fuzz mit 2000 Zügen: in [−1, 1] und
eindeutig, Klemmen, in Linie / Knick, Doppelklick), Einfluss (bitgleich zu `compute_influence` mit Smooth-Lambda; mit
dem Smooth-Preset selbst bis 1e-12), Op (bitgleich zu `SoftMoveOperation` für (0, 1], `w · Δ`, N = 1 Schritt,
Commit/Cancel/Undo/Redo, AST-Scan), Nachführen, Vorschau-Farbdaten (Vorzeichen → Farbton, `|w|` → Stärke, `w = 0` →
Alpha 0), Zustandsmaschine (inkl. Alt+Shift+Rad und Fallback), Tastentabelle = README, Import-Grenze, GL-Smoke- und
Event-Pfad (Handles, Knick, Doppelklick, Rand-Loop-Hover, `P` an zeichnet / `P` aus = gleiches Bild), Bench-Lauf.
