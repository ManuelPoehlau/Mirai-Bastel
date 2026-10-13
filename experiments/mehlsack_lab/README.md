# Mehlsack Lab (WP-MEHLSACK-LAB-01, Slice 1 + 2a + 2b + 3: Move, Rotate, Scale, Auswahl)

**Status: Verdikte von Manu für Slice 1, 2a, 2b und 3 liegen vor (alle 2026-10-13)** — siehe die
Verdikt-Tabellen in [Slice 1](#praxistest-für-manu-ca-10-minuten), [Slice 2a](#slice-2a-2026-10-13),
[Slice 2b](#slice-2b-2026-10-13) und [Slice 3](#slice-3-2026-10-13-komponenten-auswahl). Offen aus 2a: (d2) ITERATE (Kurvenpunkte hinzufügen/wegnehmen, nicht eingeplant) und
die Frage „vorher erkennbar, was mitgeht — jetzt besser?“ (unbeantwortet).
Offen aus 3 (neue Wünsche, nicht eingeplant): (s2) ITERATE — Edge Loop per Doppelklick, Teilstück per Shift+Doppelklick;
Face Loop per Shift+Doppelklick (O12); Komponenten-Hover als Standard, Loop/Ring-Hover nur in einem eigenen Modus
(`L` an/aus, O13); Auswahl umrechnen per Shift+`1`/`2`/`3` (O15).
Discovery (Typ B): Das Lab bereitet ein Artist-Verdikt vor, es entscheidet nichts und befördert nichts. KEEP heißt
hier nicht Promotion — nichts verlässt `experiments/`.

Frage des Labs: **Ist „das Mesh ist die Oberfläche“ (Loop/Ring hovern und direkt ziehen, ohne Auswahl) plus eine
Einflusskurve, die unter null gehen darf, eine vielversprechende Richtung?** Slice 1 und 2a können nur **Move**, seit
Slice 2b gibt es auch **Rotate** und **Scale** (zwei Scale-Formeln zum Vergleich). Seit Slice 3 lässt sich alternativ
eine **Auswahl** (Punkte/Kanten/Flächen) treffen, von der dieselben Vorzeichen-Gesten ausgehen; ohne Auswahl bleibt alles
wie bisher.

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
   Seit Slice 2b: `W` / `E` / `R` **halten** über dem gehoverten Loop/Ring = Move / Rotate / Scale mit der Maus,
   loslassen = fertig; `M` schaltet die Scale-Formel (linear ↔ power).
3. **Kurvenfeld** unten links: x = Abstand vom Loop (links 0, rechts der Radius), y = Gewicht. Oberhalb der weißen
   Null-Linie warm getönt, darunter kühl. Seit Slice 2a eine Bézier-Kurve: vier Punkte (weiße Kreise, als Raute nach
   einem Knick) lassen sich frei verschieben, jeder hat zwei Handles (blaue Quadrate); die Enden sind fest (1 am
   Loop, 0 am Radius), ihr einzelnes Handle lässt sich ziehen.
4. **Flächen-Vorschau** (`P`, Slice 2a, standardmäßig aus): die betroffenen Flächen orange (geht mit) oder blau (geht
   entgegen), je kräftiger, desto stärker.
5. **Auswahl** (Slice 3): `1`/`2`/`3` = Punkte/Kanten/Flächen, Klick wählt (Shift/Ctrl/Alt = hinzu/weg/umschalten),
   Shift+L / Shift+R nehmen Loop/Ring der gehoverten Kante dazu. Gewähltes ist kräftig gelb (Production-Stil: Punkte,
   Kanten, gefüllte Flächen). **Mit Auswahl wirkt jede Geste auf die Auswahl** (LMB ziehen über dem Mesh, `W`/`E`/`R`
   halten), die Einfluss-Punkte und die Vorschau gehen von ihr aus; die blasse Hover-Linie zeigt weiter den Loop/Ring
   unter dem Cursor. Klick ins Leere leert die Auswahl — dann wieder direkt hovern und ziehen.

## Steuerung

Die Tabelle ist `LAB_OVERRIDES` in `lab_bindings.py` (wird beim Start gedruckt; ein Test prüft Gleichheit 1:1).
**Alle lab-lokalen Tasten sind ein Vorschlag für dieses Lab, keine Artist-Entscheidung.** `Q` (AD-016) und `C` (AD-017)
sind reserviert und nicht belegt. Seit Slice 2b sind `W` `E` `R` mit ihrer AD-016-Bedeutung belegt (halten = Move /
Rotate / Scale) und Shift+X/Y/Z sind Ebenen (wie die App, B4.1). Seit Slice 3 wirken sie auf die Auswahl, wenn es eine
gibt, sonst auf den gehoverten Loop/Ring (E26); LMB, `1`/`2`/`3`, Shift+L/Shift+R haben ihre Artist-Truth-Bedeutung.

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
| LMB ziehen | Bearbeiten | Auswahl ziehen (Move); ohne Auswahl Loop/Ring unter dem Cursor | lab-lokal; Ziel-Regel Slice 3 E26 (PROVISIONAL) |
| LMB Klick | Bearbeiten | Auswahl ersetzen (Klick ins Leere = Auswahl leeren) | Artist Input Truth |
| Shift+LMB Klick | Bearbeiten | zur Auswahl hinzufügen | Artist Input Truth |
| Ctrl+LMB Klick | Bearbeiten | aus der Auswahl entfernen | Artist Input Truth |
| Alt+LMB Klick | Bearbeiten | Auswahl umschalten (Alt+LMB ziehen = Orbit) | Artist Input Truth |
| LMB im Kurvenfeld ziehen | Bearbeiten | Kurvenpunkt oder Handle ziehen (Handles bleiben in Linie) | lab-lokal (Slice 2a, Vorschlag, keine Artist-Entscheidung) |
| Alt+LMB im Kurvenfeld ziehen | Bearbeiten | Handle allein ziehen = Knick (Punkt wie ohne Alt) | lab-lokal (Slice 2a, Vorschlag, keine Artist-Entscheidung) |
| Doppelklick auf Kurvenpunkt | Bearbeiten | Handles des Punkts wieder weich (automatisch) | lab-lokal (Slice 2a, Vorschlag, keine Artist-Entscheidung) |
| W halten | Bearbeiten | Move der Auswahl, sonst des gehoverten Loops/Rings (loslassen = fertig) | Artist Input Truth (W/E/R); halten wie AD-016; Ziel-Regel Slice 3 E26 (PROVISIONAL) |
| E halten | Bearbeiten | Rotate der Auswahl, sonst des Loops/Rings (waagrecht bewegen) | Artist Input Truth (W/E/R); halten wie AD-016; Ziel-Regel Slice 3 E26 (PROVISIONAL) |
| R halten | Bearbeiten | Scale der Auswahl, sonst des Loops/Rings (rechts/oben = größer) | Artist Input Truth (W/E/R); halten wie AD-016; Ziel-Regel Slice 3 E26 (PROVISIONAL) |
| 1 | Bearbeiten | Auswahlmodus Punkte | Artist Input Truth; leert die Auswahl wie die App |
| 2 | Bearbeiten | Auswahlmodus Kanten | Artist Input Truth; leert die Auswahl wie die App |
| 3 | Bearbeiten | Auswahlmodus Flächen | Artist Input Truth; leert die Auswahl wie die App |
| Shift+L | Bearbeiten | Loop der gehoverten Kante zur Auswahl (Punkt-/Kantenmodus) | Artist Input Truth; hinzufügen = Slice 3 E27 (PROVISIONAL) |
| Shift+R | Bearbeiten | Ring der gehoverten Kante zur Auswahl (Punkt-/Kantenmodus) | Artist Input Truth; hinzufügen = Slice 3 E27 (PROVISIONAL) |
| RMB (während Zug) | Bearbeiten | Zug abbrechen (exakt zurück) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| Tab | Bearbeiten | Loop ↔ Ring (bleibt) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| X | Bearbeiten | Achse X an/aus (bleibt) | Artist Input Truth |
| Y | Bearbeiten | Achse Y an/aus (bleibt) | Artist Input Truth |
| Z | Bearbeiten | Achse Z an/aus (bleibt) | Artist Input Truth |
| Shift+X | Bearbeiten | Ebene YZ (ohne X) an/aus (bleibt) | Artist Input Truth |
| Shift+Y | Bearbeiten | Ebene XZ (ohne Y, z. B. Taille) an/aus (bleibt) | Artist Input Truth |
| Shift+Z | Bearbeiten | Ebene XY (ohne Z) an/aus (bleibt) | Artist Input Truth |
| Shift+Mausrad | Bearbeiten | Einflussradius ±1 Stufe | wie App (AD-020), PROVISIONAL |
| Ctrl+O | Bearbeiten | Metrik geodesic ↔ euclidean | wie App (AD-020), PROVISIONAL |
| Alt+O | Bearbeiten | Einfluss-Punkte an/aus | wie App (AD-020), PROVISIONAL |
| P | Bearbeiten | Flächen-Vorschau an/aus (orange = mit, blau = entgegen) | lab-lokal (Slice 2a, Vorschlag, keine Artist-Entscheidung) |
| N | Bearbeiten | Nachführen an/aus | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| M | Bearbeiten | Scale-Formel linear ↔ power (bleibt; Nachführen) | lab-lokal (Slice 2b, Vorschlag, keine Artist-Entscheidung) |
| K | Bearbeiten | Kurve: Smooth | lab-lokal (Slice 3, Vorschlag, keine Artist-Entscheidung) |
| Shift+K | Bearbeiten | Kurve: Mexican Hat (mit Senke) | lab-lokal (Slice 3, Vorschlag, keine Artist-Entscheidung) |
| Ctrl+Z | Bearbeiten | Undo | Artist Input Truth |
| Ctrl+Y | Bearbeiten | Redo | Artist Input Truth |
| B | Bearbeiten | neue Box (2× B; löscht die History) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| H | beide | Tastenhilfe an/aus | lab-lokal; Artist Truth: H = HUD |
| Esc | beide | Zug/Rückfrage abbrechen, sonst Beenden | lab-lokal; Q bewusst nicht belegt |

Hinweise: Seit Slice 3 sind `1`/`2`/`3` die Auswahlmodi wie in der Artist Input Truth; die Kurven-Presets liegen
deshalb auf `K` / `Shift+K` (vorher `1` / `2` — die Praxistests von Slice 1–2b unten nennen noch die alten Tasten).
`H` ist hier weiter die Tastenhilfe (Artist Truth: HUD-Schalter), das Lab zeigt das HUD immer. LMB trägt im
Bearbeiten-Modus zwei Bindungen (AD-019): unter 5 px Bewegung ein Klick (Auswahl), darüber ein Ziehen. Shift-, Ctrl-, Alt- und
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

## Rotate / Scale mit Vorzeichen-Gewichten (Analyse aus Slice 1 — gebaut in Slice 2b)

*2026-10-13: gebaut in [Slice 2b](#slice-2b-2026-10-13), beide Formeln umschaltbar (`M`). Die Analyse bleibt hier als
Grundlage stehen; die Tabelle unten ist durch einen Test gegen den Code gepinnt.*

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

**Verdikte von Manu (2026-10-13) liegen vor** — siehe [Tabelle unten](#praxistest-für-manu-ca-8-minuten): (a2), (p), (r)
KEEP, (d2) ITERATE; die Frage „vorher erkennbar“ ist unbeantwortet. Setzt Manus zwei ITERATE-Verdikte (a) und (d) und
die Antworten zu O1 und O4 von oben um.
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
  *Korrektur 2026-10-13 (Slice 2b):* Das war nicht harmlos — ein Kurvenpunkt bei −1 ergab `w = −1.0000000000000002`,
  und die Vorzeichen-Ops lehnen `|w| > 1` ab (der Zug hätte im Fenster einen Fehler geworfen; auch Move in 2a). Die
  Auswertung rundet einen solchen Wert jetzt auf ±1 zurück (reiner Rundungsschutz, die Form wird nie beschnitten);
  zwei Regressionstests.
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

| Punkt                              | Verdikt (KEEP / ITERATE / REJECT / UNKNOWN) | Notiz                                     |
| ---------------------------------- | ------------------------------------------- | ----------------------------------------- |
| (a2) Tiefe per Alt+Shift+Mausrad   | KEEP                                        |                                           |
| (d2) Kurvenfeld mit Bézier-Handles | Iterate                                     | Kurvenpunkte hinzufügen/wegnehmen können. |
| (p) Flächen-Vorschau               | KEEP                                        |                                           |
| (r) Rand-Loop um die Ecken         | KEEP                                        |                                           |

Vorher erkennbar, was mitgeht — jetzt besser? Manu:

Hinweis: Alle Tasten sind Vorschläge für dieses Lab, keine Entscheidung. Nächster Schritt nach deinem Verdikt: Slice 2b
(Rotate/Scale, O5) — inzwischen gebaut, siehe unten.

## Slice 2b (2026-10-13)

**Verdikte von Manu (2026-10-13) liegen vor** — siehe [Tabelle unten](#praxistest-für-manu-ca-10-minuten-1): (f), (g),
(h), (i) KEEP; (i) „vorerst“ (generelle UX-Frage, weitere Playground-Tests nötig). Der markierte Loop/Ring lässt sich
jetzt auch **drehen** und **skalieren**, mit
Vorzeichen-Gewichten — für die Aufgabe „Taille mit Bauch daneben“ aus dem Brief und für Manus Antwort zu O5 („Muss man
vergleichen in der Praxis“): beide Scale-Formeln sind gebaut und mit `M` umschaltbar. Nichts davon wird befördert.

### Was gebaut ist

- **Halten über dem Hover:** `W` / `E` / `R` gedrückt halten = Move / Rotate / Scale des Loops/Rings, der beim
  Drücken gehovert war; Maus bewegen = Betrag; loslassen = fertig (ein History-Eintrag); `Esc`/RMB = exakt zurück;
  Antippen ohne Bewegung = nichts. LMB-Ziehen bleibt wie es ist (KEEP (b)).
- **Ebenen:** `Shift+X/Y/Z` (Blender: diese Achse ausgeschlossen; Shift+Y = XZ = nur waagrecht) neben `X/Y/Z`, ein
  gemeinsamer, bleibender Zustand wie in der App (B4.1). Für Move, Rotate und Scale.
- **Rotate:** Winkel `w · θ`; negative Gewichte drehen zurück (S-Kurve). Achse: Blickachse beim Start, mit Achse/Ebene
  die Weltachse (`Y` und `Shift+Y` drehen beide um die Hochachse).
- **Scale:** zwei Formeln für `w ≠ 1`: **linear** `g = 1 + w (F − 1)` (App-Standard, Start) und **power** `g = F ** w`.
  `M` schaltet um (bleibt; gilt ab dem nächsten Zug und per Nachführen für den letzten). Kein Begrenzen von `g`: linear
  mit `w < 0` erreicht `g = 0` bei `F = 1 + 1/|w|` und klappt darüber durch — das HUD zählt während eines linearen
  Scale (und nach dem Nachführen des letzten), wie viele Vertices `g ≤ 0` haben.
- **Nachführen** gilt jetzt auch für Rotate und Scale: Kurve, Radius, Metrik oder Formel ändern rechnet den letzten
  Zug vom Startzustand mit derselben Summe (Winkel bzw. Faktor), Achse und Pivot neu und ersetzt seinen History-Eintrag.
- Vorschau (`P`) und Punkte zeigen weiter die Gewichte, nicht die Richtung (E22).

### Engineering-Annahmen (alle `PROVISIONAL`)

- **E16 Aktivierung:** `E` halten = Rotate, `R` halten = Scale, `W` halten = Move auf dem beim Drücken gehoverten
  Loop/Ring (Ziel eingefroren); Maus = Betrag, loslassen = fertig, `Esc`/RMB = abbrechen, Antippen = nichts.
  AD-016 Halten-über-Hover mit dem Hover-Ziel, Tasten aus der Artist Input Truth.
- **E17 Abbildung:** `RotateTool.RADIANS_PER_PIXEL`, `ScaleTool.SCALE_PER_PIXEL`, `ScaleTool.MIN_SCALE` werden aus den
  Klassen gelesen (keine kopierten Zahlen); Pixel werden wie in den Tools aufsummiert (unabhängig davon, wie das
  Fenster die Bewegung stückelt). Pivot = `primary_pivot(mesh, seeds)`. Rotate-Achse: Blickachse beim `begin()`, sonst
  `_resolve_space(..., for_rotation=True)`. Scale: uniform, sonst die Weltachsen-Maske. Keine Tangentenbasis, kein
  Normal-Raum.
- **E18 Ebenen:** `Shift+X/Y/Z` bleibend (B4.1-Semantik) für Move, Rotate, Scale.
- **E19 Ops:** `SignedSoftRotateOperation` (Winkel `w · θ`, inkrementell) und `SignedSoftScaleOperation` (absolut vom
  Start-Schnappschuss mit dem seit `begin()` aufgelaufenen `F` — die dokumentierte Abweichung vom inkrementellen
  Op-Vertrag, wie in `src`), beide auf den geschützten Core-Hooks wie Slice 1 (Präfix `_mehlsack_`, AST-Scan). Beide
  Formeln, kein Clamp von `g`.
- **E20 Formel:** `M` linear ↔ power, bleibend; Statuszeile zeigt die Formel; HUD-Zähler `g ≤ 0` bei linear.
- **E21 Nachführen** für Rotate und Scale (Summe, Achse/Maske, Pivot, Formel gespeichert).
- **E22** Vorschau und Punkte unverändert.

Zusätzlich vom Agenten gesetzt (beim Bauen nötig geworden, alle `PROVISIONAL`):

- **Wann was gelesen wird:** Das Ziel friert beim Drücken ein; Achse/Ebene, Gewichte (Kurve, Radius, Metrik) und Formel
  werden bei der **ersten Bewegung** gelesen — wie die App beim `begin()` (`Application._transform_step`). Eine
  Achsen-/Formel-Taste während eines laufenden Zugs ändert den Zustand, gilt aber erst ab dem nächsten Zug.
- **Während gehalten:** eine zweite Halte-Taste wird ignoriert; LMB tut nichts; RMB bricht ab; `B` wird ignoriert;
  Undo/Redo während ein Zug läuft wird ignoriert, nur scharf (noch keine Bewegung) wird erst entschärft, dann
  rückgängig gemacht (wie die App). Verliert das Fenster den Fokus, wird ein gehaltener Zug abgebrochen (das Loslassen
  käme nie an). Der Hover ist eingefroren.
- **Move per `W`:** dieselbe Abbildung wie das LMB-Ziehen (Bildebenen-Delta am Anker-Seed, maskiert); der Anker ist das
  erste Ende der gehoverten Kante, nicht `min(vertex_ids)` wie im `MoveTool`.
- **`_resolve_space`** ist eine (mit Unterstrich) modulinterne Funktion in `src/mirai/interaction/tools/transform.py`;
  das Lab ruft sie nur lesend auf, damit die Achsen-/Ebenen-Abbildung nicht von der App abweichen kann.
- **Formel-Wechsel nach einem Rotate/Move** ändert nichts (die Formel gehört nur zu Scale).
- **HUD-Zähler:** zählt Vertices mit `g ≤ 0` auf einer skalierten Achse (`F ≠ 1`); bei power immer 0. Er gilt für den
  laufenden bzw. letzten Scale und verschwindet mit dem nächsten Zug oder Undo/Redo.
- **Nachführen eines Scale** spielt `F` in **einem** Schritt ab; die `w = 1`-Vertices unterscheiden sich dadurch vom
  schrittweisen Zug nur in der Rundung (≤ 1e-12, Test).
- **Kurven-Rundungsschutz** (Korrektur an Slice 2a, siehe R3): Die Kurve rundet Werte knapp jenseits ±1 auf ±1 zurück;
  ohne das warf ein Zug mit einem Kurvenpunkt bei −1 einen Fehler.

### Beobachtungen beim Bauen (keine Bewertung)

Gemessen headless (Container), Box 2 × 3 × 2, `h = 12`, `n = 6`, mittlerer Loop, Radius 50 %, geodesic, Scale mit
`Shift+Y` (nur X/Z). Je Zelle: Vertices mit `g ≤ 0` / umgeklappte Flächen (Normale gegenüber dem Start ≤ 0).
„Tiefe Senke“ = Punkte 0,3 / −1 / −1 / −0,5 mit automatischen Handles.

| Kurve | Formel | F = 0,5 | F = 1,5 | F = 2 | F = 3 | F = 5 |
|---|---|---:|---:|---:|---:|---:|
| Smooth | linear | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Smooth | power | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Mexican Hat | linear | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 48 / 0 |
| Mexican Hat | power | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| tiefe Senke | linear | 0 / 0 | 0 / 0 | 48 / 0 | 96 / 48 | 96 / 144 |
| tiefe Senke | power | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

- **S1 Taille ist sicher, Auswölben nicht:** Beim Einziehen (`F < 1`, die Taille) erreicht keine Formel `g ≤ 0` —
  negative Gewichte werden dort größer (Bauch). Zusammenfallen und Durchklappen gibt es nur beim **Aufweiten** (`F > 1`)
  mit linear und `w < 0`, genau ab `F = 1 + 1/|w|` (Mexican Hat, tiefster Wert −0,35: ab `F ≈ 3,9`).
- **S2 Power wächst in der Taillen-Richtung stark:** `g = F ** w` mit `w < 0` und `F < 1` ist `1 / F^|w|`. Am
  Tool-Minimum `F = 0,01`: `w = −1` → linear 1,99, power **100**; `w = −0,35` → linear 1,35, power 5,0; bei `F = 0,1`:
  1,9 gegen 10 bzw. 1,3 gegen 2,2. Power klappt nie durch, kann aber beim tiefen Einziehen einen sehr großen Bauch machen.
- **S3 Umgeklappte Flächen zählen nicht alles:** Bei Mexican Hat linear `F = 5` haben 48 Vertices `g < 0`, aber keine
  Fläche klappt um — ein ganzer Ring mit `g < 0` auf X und Z wird am Pivot gespiegelt, das ist eine halbe Drehung und
  behält die Orientierung; die Fläche läuft dennoch durch sich selbst. Der HUD-Zähler (`g ≤ 0`) zeigt das, die
  Flächenzählung nicht.
- **S4 Rotate faltet bei großen Winkeln mit jeder Kurve:** um Y, umgeklappte Flächen bei θ = 0,5 / 1 / 2 / 3 rad:
  Smooth 0 / 0 / 48 / 96, Mexican Hat 0 / 0 / 48 / 48, tiefe Senke 0 / 0 / 48 / 48. Das ist Verdrillen, nicht das
  Vorzeichen; mit Senke dreht der Bereich daneben sichtbar zurück (S-Kurve, im Fenster geprüft).
- **S5 Im Fenster** (Xvfb-Screenshots, nicht Referenz-PC): Taille + Bauch mit `Shift+Y`, `R` und Mexican Hat; `M` nach
  dem Zug ändert die Form sofort (Nachführen); lineares Aufweiten bis `F = 5` zeigt im HUD „96 Vertices mit g ≤ 0“;
  `E` mit Senke ergibt die S-Kurve.

### Offene Fragen (nicht im Code entschieden)

- **O9** Soll das Lab `g ≤ 0` bei linear verhindern oder nur anzeigen (jetzt: nur anzeigen; Handoff: beobachten,
  nichts reparieren)? Manu: Erstmal so lassen
- **O10** Power in der Taillen-Richtung (S2): ist ein Bauch von ×5 bis ×100 am Tool-Minimum gewollt? Manu: Bleibt auch erstmal, weitere Tests nötig
- **O11** Pivot, Tangentenbasis, Normal-Raum, Zahleneingabe: bewusst nicht in diesem Slice. Manu: ja, kommt in späteren Slices

### Praxistest für Manu (ca. 10 Minuten)

Start: `python experiments/mehlsack_lab/run.py`, Box mit einigen Loops bauen, `Enter`.

1. **Taille:** Über einen mittleren Loop fahren, `Shift+Y` (nur waagerecht), dann **`R` halten** und die Maus nach innen bewegen — Taille. Loslassen = fertig.
2. **Bauch daneben:** Kurve mit Senke (`2` oder selbst formen), noch einmal `R` am selben Loop — die Ringe daneben wölben sich nach außen.
3. **Formel vergleichen:** `M` schaltet zwischen *linear* und *power*. Mit Nachführen siehst du den Unterschied am letzten Zug sofort. Bei *linear* und starker Senke können Bereiche auf den Mittelpunkt zusammenfallen oder durchklappen (das HUD zählt sie) — bei *power* nicht.
4. **Drehen:** **`E` halten** über einem Loop = verdrehen; mit Senke dreht der Bereich daneben gegen (S-Kurve). `Y` = um die Hochachse.
5. **`W` halten** = Verschieben wie mit der Maustaste — nur zum Vergleich.

Hinweis zu 3: Zusammenfallen/Durchklappen passiert bei *linear* beim **Aufweiten** (Maus nach außen) mit Senke; beim
Einziehen (Taille) nicht. Bei *power* wird dafür der Bauch beim sehr tiefen Einziehen sehr groß (siehe S2).

**Deine Verdikte** (je KEEP / ITERATE / REJECT / UNKNOWN):

| Punkt                                                                   | Verdikt (KEEP / ITERATE / REJECT / UNKNOWN) | Notiz                                                                                                           |
| ----------------------------------------------------------------------- | ------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| (f) Rotate mit Vorzeichen-Gewichten                                     | KEEP                                        |                                                                                                                 |
| (g) Scale mit Vorzeichen-Gewichten (Taille/Bauch)                       | KEEP                                        |                                                                                                                 |
| (h) Formel für negative Gewichte: linear, power oder „beide als Option“ | KEEP                                        | beide erstmal behalten                                                                                          |
| (i) E/R/W halten über dem gehoverten Loop                               | KEEP                                        | vorerst, das ist eine generelle noch nicht 100%ig entschiedene UX Entscheidung (weiter Playground Tests nötig ) |

## Audit für Slices 3–6 (2026-10-13)

Vorab-Audit des Planers (Handoff, nur gelesen), hier **gegen den Code** geprüft. „bestätigt“ = so im Code gefunden,
**fett** = korrigiert oder präzisiert.

| Thema | Gefunden (im Code geprüft) | Im Lab wiederverwenden? |
|---|---|---|
| Auswahl-Modell | bestätigt: `src/core/selection.py` (`Selection`, `SelectionMode`; nicht in der History); App-Commands `Select`/`SelectAdd`/`SelectRemove`/`SelectToggle`/`ClearSelection` (`mirai/interaction/commands.py`). **Die Klick-Regel selbst steckt in `Application.select_at`** (an Fenster/Viewport gebunden, keine freie Funktion) | ja, nur lesend (Slice 3); Klick-Regel im Lab neu formuliert, Command-Namen importiert, Test pinnt sie |
| Komponenten-Picking | bestätigt: `mirai.viewport.picking.pick_component` (+ `PickCache`, `occlusion`); **der Flächen-Pick nimmt die vorderste Fläche und kennt kein `occlusion`** | ja (Slice 3) |
| Klick vs. Ziehen | bestätigt: `mirai.interaction.pointer.CLICK_THRESHOLD_PX = 5.0` (Manhattan-Summe), Resolver `PointerGestures` | Konstante ja; **Resolver-Regel lab-lokal** (`lab_pointer.py`), weil das Lab die gepufferten Bewegungen einzeln nachreicht (`PointerGestures`: eine Summe) — sonst wäre das LMB-Ziehen nicht mehr bitgleich |
| Seeds aus der Auswahl | bestätigt: `mirai.interaction.tools.selection_helpers.resolve_selection_vertices` | ja (Slice 3) |
| Auswahl-Anzeige | **präzisiert:** `src/viewport/overlay.py` `SelectionOverlay` (`point_layers`/`line_layers`/`face_layers`) + `GLPointOverlay`/`GLLineOverlay`/`GLTriangleOverlay`, Layer `selected`, Farbe `(1.0, 0.82, 0.15)`. Die `highlight_flags` des `RenderMesh` liest der Shader nicht mehr (Artist REJECT) | ja (Slice 3, nur lesend) |
| Weltachsen/-ebenen, Screen | bestätigt: X/Y/Z und Shift+X/Y/Z über `_resolve_space`. **Präzisiert:** „Screen“ ist in AD-012 kein eigener Raum (Screen-Space ist dort mit Local/Gimbal auf ARCH-01 verschoben); im Lab heißt „keine Sperre“: Bildebene (Move, wie `MoveTool`) bzw. Blickachse (Rotate, wie `RotateTool`) | schon da |
| Normal-Raum | **korrigiert:** nicht nur für eine Fläche. `selection_normal()` mittelt die Normalen einer Punkt-, Kanten- oder Flächen-Auswahl zu **einer** Richtung (`_resolve_space("normal")`, braucht `derived_geometry`); nur die Tangentenbasis (`normal_x`/`normal_y`) ist auf eine einzelne Fläche beschränkt (WP-03C). Für einen geschlossenen Loop heben sich die Normalen auf → `(0, 0, 0)` (degeneriert). Verschieben **pro Vertex entlang seiner eigenen Normale** („aufblasen“): nirgends als Transform; die Daten gibt es (`derived_geometry.vertex_normals`) | später (Slice 4) |
| Local | bestätigt: bewusst nicht gebaut (AD-012 ARCH-01, braucht Objekt-Rotation) | Slice-4-Frage, siehe Vorschlag unten |
| Gizmo | bestätigt: nur `playground/gizmo.py` (importiert nur `math` und `core.selection` — GL-frei: Modus, Handle-Geometrie, Pick/Hover) + Zeichnen in `playground/window.py`; nichts in `src` | Slice-4-Entscheidung (Import-Grenze) |
| Pinning / Masking | bestätigt: nichts in `src/mirai/soft_selection` oder AD-020 | fehlt wirklich |
| Raster / Achsenanzeige | bestätigt: nichts in `src/viewport`, `src/mirai`, `playground` („grid“ dort nur als Mesh-Asset, `load_grid`); in `experiments/` nur Grid-Meshes in Topologie-Sonden und ein Achsenrahmen für Lichtrichtungen (`viewport_shading_lab/lab_rig.py`, keine Anzeige) | fehlt wirklich |
| Pivot | **präzisiert:** Lab `primary_pivot(seeds)` und App `selection_pivot` sind dieselbe Rechnung (Schwerpunkt, gleiche Summenreihenfolge, `soft_selection/influence.py`); unter Symmetrie hat die App `symmetric_default_pivot`. Eine Pivot-Steuerung gibt es nirgends | fehlt wirklich |

**Vorschlag für Slice 4 (Räume + Gizmo) — nicht gebaut, nicht entschieden:**

- *Räume:* Welt und „Screen“ (= keine Sperre) bleiben. Neu als Kandidaten für Manus „Local“: **(L1) jeder Vertex
  entlang seiner eigenen Normale** (mit Vorzeichen-Gewicht: `w · d · n_v`, Normalen beim Start eingefroren — „aufblasen /
  einschnüren“, eindeutig auch für geschlossene Loops) und **(L2) ein Rahmen der Auswahl/des Loops** (gemittelte Normale
  aus `src`, für geschlossene Loops die Ebenen-Normale des Loops statt des degenerierten Mittels, Tangente entlang des
  Loops). „Local“ im Sinn von Objektachsen ergibt im Lab nichts Neues: die Box ist nie gedreht, Objekt-Achsen = Weltachsen
  (ARCH-01). Empfehlung: Manu nennt, was er mit „Local“ meint; zuerst L1 bauen, weil es die Mehlsack-Geste (Bauch) direkt
  trifft und keine Mehrdeutigkeit hat.
- *Gizmo:* `playground/gizmo.py` ist GL-frei. Drei Wege: (a) als **zweiten** Playground-Import lesend nutzen (wie
  `loop_ring`; Import-Grenzen-Test auf genau zwei Module erweitern), (b) Lab-Kopie (widerspricht „keine Kopien“),
  (c) nach `src` befördern (braucht eigene Doku/AD). Empfehlung für Discovery: (a), als ausdrückliche Grenz-Entscheidung
  vor dem Bau.

## Slice 3 (2026-10-13, Komponenten-Auswahl)

**Verdikte von Manu (2026-10-13) liegen vor** — siehe [Tabelle unten](#praxistest-für-manu-ca-10-minuten-2): (s1), (s3),
(s4) KEEP, (s2) KEEP + ITERATE (Doppelklick-Loop, Teilstück); Antworten zu O12–O16 unter „Offene Fragen“ (O13: Hover soll
standardmäßig Komponenten zeigen, Loop/Ring nur in einem `L`-Modus — ändert den Hover-Weg aus Slice 1, noch nicht
gebaut). Manus Priorität 1 (2026-10-13): Komponenten-Auswahl mit Mehrfachauswahl. Die Auswahl ist eine
**zweite Quelle für die Seeds** derselben Vorzeichen-Gesten; ohne Auswahl bleibt der direkte Hover-Weg exakt wie in
Slice 1–2b (Test: gleiche Ergebnisse bis aufs Bit). Nichts wird befördert.

### Was gebaut ist

- **Auswahl** im Punkt-, Kanten- und Flächenmodus (`1`/`2`/`3`), Klick ersetzt, Shift+Klick fügt hinzu, Ctrl+Klick
  entfernt, Alt+Klick schaltet um; Klick ins Leere leert (nur ohne Modifier). Eine Core-`Selection`, nicht in der
  History.
- **Loop/Ring auswählen:** Shift+L / Shift+R nehmen Loop / Ring der gehoverten Kante **dazu** (Kantenmodus: die Kanten,
  Punktmodus: ihre Vertices), mit dem Rand-Loop um die Ecken (E15). Flächenmodus: abgelehnt (Statuszeile).
- **Ziel-Regel:** mit Auswahl wirkt **jede** Geste auf die Auswahl — LMB ziehen (über dem Mesh gedrückt) und
  `W`/`E`/`R` halten; Einfluss-Punkte, Vorschau (`P`), Kurve, Radius, Metrik, Formel und Nachführen wie bisher, nur von
  den Auswahl-Vertices aus (`w = 1`). Ohne Auswahl: der gehoverte Loop/Ring wie bisher.
- **Anzeige:** Auswahl im Production-Stil (kräftig gelbe Punkte / Kanten / gefüllte Flächen); Einfluss bleibt Punkte und
  Vorschau (warm / blau); die blasse Hover-Linie zeigt weiter den Loop/Ring unter dem Cursor; Achsen-Sperre in Status
  und HUD. Eine HUD-Zeile sagt, worauf die Gesten gerade wirken.
- Kurven-Presets auf `K` (Smooth) / `Shift+K` (Mexican Hat), weil `1`/`2` jetzt Auswahlmodi sind.

### Engineering-Annahmen, so gebaut (alle `PROVISIONAL`, keine Artist-Entscheidung)

- **E23 Auswahl-Modell:** `LabState.selection` ist eine Core-`Selection` (Start: Punktmodus, Core-Default wie die App);
  Picking mit `pick_component` und dem `PickCache` des Labs, Occlusion an wie beim Kanten-Hover.
- **E24 Klick vs. Ziehen:** Schwelle `CLICK_THRESHOLD_PX` aus `mirai.interaction.pointer` (AD-019, nicht kopiert):
  darunter Klick beim Loslassen, darüber Ziehen. Die Bewegungen bis zur Schwelle werden gepuffert und dann **einzeln**
  nachgereicht (`lab_pointer.PointerPress`), damit das LMB-Ziehen bitgleich zu Slice 1–2b bleibt (Test mit Achsen-Sperre).
- **E25 Klick-Semantik = App-Commands:** `Select` ersetzt, ins Leere leert; `SelectAdd`/`SelectRemove`/`SelectToggle`
  ändern nur das getroffene Element, ins Leere nichts (`lab_selection.apply_click`).
- **E26 Ziel-Regel:** Auswahl leer → heutiges Verhalten; Auswahl nicht leer → Seeds =
  `resolve_selection_vertices(mesh, selection, mode)`, `w = 1`, sonst alles wie bisher. Gleiche Regel wie die App
  (`_transform_arm`: erst Auswahl, sonst Hover). *Annahme, nicht Manus Aussage* — Manu testet sie (s3).
- **E27 Loop/Ring auswählen:** fügt hinzu (nicht ersetzen), gleiche Ziele wie der Hover; `Tab` bleibt der Hover-Schalter;
  Shift+R schärft nie das R-Halten (Test).
- **E28 Tasten:** `1`/`2`/`3` = Auswahlmodi (Artist Truth); Presets auf `K` / `Shift+K` (nicht in der Artist Truth, im
  Lab frei; Vorschlag). Tabelle = `LAB_OVERRIDES`, Test erzwingt Gleichheit.
- **E29 Anzeige:** Production-`SelectionOverlay` + `GLPointOverlay`/`GLLineOverlay`/`GLTriangleOverlay`, nur lesend,
  keine neue Palette (Beobachtungen V1–V3).
- **E30 Nachführen:** ein Auswahlwechsel beendet es nicht (ändert keine Geometrie); der letzte Zug behält seine
  eingefrorenen Seeds (Test).
- **E31 Lebenslauf:** Auswahl nur im Bearbeiten-Modus; Undo/Redo behalten sie; `B` (neue Box) leert sie; während eine
  Geste scharf ist oder läuft, werden Auswahl-Klicks ignoriert.

Zusätzlich vom Agenten gesetzt (beim Bauen nötig geworden, alle `PROVISIONAL`):

- **Moduswechsel leert die Auswahl**, auch bei der Taste des aktiven Modus — wie die App (`_set_selection_mode`) und der
  Playground. Der Modus selbst bleibt über eine neue Box erhalten (wie die anderen Einstellungen).
- **Klick-Position:** der Ort des Loslassens (wie die App). „Über dem Mesh gedrückt“ (E26) = eine Kante ist gehovert
  oder unter dem Cursor liegt eine Fläche (`pick_face`). Mit Auswahl und Druck ins Leere bewegt Ziehen nichts.
- **Unentschiedener Druck** (LMB unten, noch unter 5 px): `Esc`, RMB und Fokusverlust verwerfen ihn (kein Klick, kein
  Zug — `Esc` beendet in diesem Moment nicht das Lab); `W`/`E`/`R`, `B` und Auswahl-Tasten werden ignoriert.
- **Auswahl-Tasten** (`1`/`2`/`3`, Shift+L/R) werden wie Klicks ignoriert, solange eine Geste scharf ist oder läuft.
- **Alt+LMB-Orbit** beginnt jetzt wie in der App erst nach 5 px (Alt+Klick = umschalten); vorher sofort. Das gepufferte
  Stück wird nachgeholt.
- **Anker eines Auswahl-Zugs** (Bild → Welt): `min(seeds)` wie `MoveTool`; beim Hover weiter das erste Ende der gehoverten
  Kante. Pivot unverändert `primary_pivot(seeds)`.
- **Während einer Geste auf der Auswahl** zeigt das Lab keine Hover-Linie (wie die App beim Scharfschalten).
- **Shift+L/R** nehmen die gehoverte Kante, unabhängig von `Tab` (Shift+L immer Loop, Shift+R immer Ring). Der
  Playground ersetzt die Auswahl und startet an der ersten gewählten Kante — das Lab fügt hinzu (E27) und braucht keine
  Kante in der Auswahl.
- **HUD-Zeile** „Auswahl (Modus): leer → Gesten wirken auf den gehoverten Loop“ bzw. „n gewählt … → alle Gesten wirken
  auf die Auswahl · Klick ins Leere = zurück zum Hover“.

### Beobachtungen beim Bauen (keine Bewertung)

Im Fenster unter Xvfb durchgespielt und per Screenshot geprüft (nicht Referenz-PC): Klick/Shift/Ctrl/Alt in allen drei
Modi, Shift+L um einen geschlossenen Loop, Flächen auswählen und ziehen, Vorschau `P` mit Auswahl.

- **V1 Gewählte Kanten vs. Hover-Linie:** beide 1 px gelb (Production: gewählt `(1.0, 0.82, 0.15)` deckend, Hover
  `(0.95, 0.90, 0.35)` halbtransparent). Im Screenshot unterscheiden sie sich nur in Sättigung/Helligkeit — ein gewählter
  und ein gehoverter Loop sind schwer auseinanderzuhalten. Die blassgelben Seed-Punkte (Production-Hover-Stil) liegen
  genau auf der Auswahl.
- **V2 Farb-Nachbarschaft:** das Auswahl-Gelb liegt neben den warmen Einflussfarben (Rot/Orange/Rosa) und der orangen
  Vorschau; mit `P` grenzt die gelbe Flächenfüllung direkt an Orange. Im Screenshot unterscheidbar, aber benachbart.
  Laut Handoff gemeldet, keine neue Palette.
- **V3 Gefüllte Flächen:** gewählte Flächen sind deckend gefüllt und verdecken die Vorschau-Tönung dieser Flächen (sie
  sind Seeds, `w = 1`); das Drahtgitter darüber erscheint gestrichelt (gleiche Tiefe; Zeichenreihenfolge wie in der App).
- **V4 Punktmodus:** ein Klick trifft nur nahe an einem Vertex (Production-Pick-Radius); die Hover-Anzeige zeigt aber den
  Loop, nicht den Punkt, den ein Klick treffen würde. Das Lab zeigt keinen Komponenten-Hover (die App schon,
  `Selection.hovered`) — nicht im Auftrag.
- **V5 Klick ohne Bewegung:** mit leerer Auswahl wählt ein Klick auf dem Mesh jetzt etwas aus; danach wirken alle Gesten
  auf diese Auswahl, bis ein Klick ins Leere sie leert. Vor Slice 3 war ein Klick ohne Bewegung ein leerer Zug.
- **V6 Ziehen unter 5 px** bewegt nichts mehr (es wird ein Klick); vorher bewegte es den Loop um diese Pixel.
- **V7 Nachführen nach Auswahlwechsel:** die Punkte/Vorschau zeigen dann die *neue* Auswahl, das Nachführen wirkt aber
  auf den letzten Zug mit den *alten* Seeds (E30) — beides ist gleichzeitig sichtbar.

### Offene Fragen (nicht im Code entschieden)

- **O12** Shift+L/R im Flächenmodus: weder `src` noch `playground` hat eine Flächen-Loop/-Ring-Regel.
  **Manu**: Face Loop (neu)
  Vorgehen: Wechseln in den Face Mode
  Auswahl: Klicken Sie auf eine Fläche, halten Sie **Shift** gedrückt und machen Sie einen Doppelklick auf die benachbarte Fläche in der Richtung, in die der Loop verlaufen soll.

- **O13** Komponenten-Hover (welcher Punkt / welche Kante / Fläche ein Klick trifft) zusätzlich zur Loop-Linie? (V4)
  **Manu**: Hier brauchen wir eine Änderung. Hover sollte Standardmäßig die einzelnen Komponenten highlighten. Hover Loop und Ring nur, wenn wir in den Loop/Ring Modus wechseln(neu). L Taste wechselt in diesen Modus. L verlässt ihn wieder. Dort kann man nur Loops und Rings auswählen bearbeiten, keine einzelne Komponenten. Loop/Ring weiterhin über Tab wechselbar

- **O14** Reicht der Production-Stil, um Auswahl und Hover-Linie zu trennen? (V1, V2 — Teil von s4) **Manu**: Ja

- **O15** Moduswechsel leert die Auswahl (wie die App) — oder soll sie umgerechnet werden (z. B. Kanten → ihre Punkte)?
  **Manu**: Leert (umrechnen über shift+jeweiligen Komponenten Modus Taste 1, 2 oder 3)

- **O16** Shift+L/R: hinzufügen (Lab, E27) oder ersetzen (Playground)?
  **Manu**: Hinzufügen

### Praxistest für Manu (ca. 10 Minuten)

Start im Repo-Ordner: `python experiments/mehlsack_lab/run.py`, Box mit einigen Loops bauen, `Enter`.

1. **Ohne Auswahl wie bisher:** Über einen Loop fahren und mit LMB ziehen, dann `R` halten — alles wie in Slice 2b.
2. **Einzelauswahl:** `1` = Punkte, `2` = Kanten, `3` = Flächen. Klick auf ein Element = Auswahl. `Shift`+Klick = hinzufügen, `Ctrl`+Klick = wegnehmen, `Alt`+Klick = umschalten.
3. **Loop/Ring auswählen:** Im Kantenmodus über eine Kante fahren, `Shift+L` = ganzen Loop dazu, `Shift+R` = Ring dazu.
4. **Auswahl bewegen:** Mit Auswahl wirkt **jede** Geste auf die Auswahl — LMB ziehen, `W`/`E`/`R` halten. Der weiche Einfluss (Punkte, `P`) geht jetzt von der Auswahl aus. Probier eine unregelmäßige Auswahl (z. B. ein paar Flächen auf einer Seite) mit Senke in der Kurve.
5. **Zurück zum direkten Arbeiten:** Klick ins Leere leert die Auswahl — danach wieder Loop hovern und ziehen.
6. **Lesbarkeit:** Kannst du Auswahl (was du gewählt hast), Einfluss (was mitgeht) und Achsen-Sperre auseinanderhalten?

Die Kurven-Presets liegen jetzt auf anderen Tasten (siehe Tastenhilfe `H`). Alle Tasten außer denen aus deiner Input Truth sind Vorschläge.

**Deine Verdikte** (je KEEP / ITERATE / REJECT / UNKNOWN):

| Punkt                                                                                           | Verdikt      | Notiz                                                                                                                                                                                                                                                                                                                                               |
| ----------------------------------------------------------------------------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| (s1) Auswahl per Klick mit Shift/Ctrl/Alt in Punkt-/Kanten-/Flächenmodus                        | KEEP         |                                                                                                                                                                                                                                                                                                                                                     |
| (s2) Loop/Ring per Shift+L / Shift+R auswählen                                                  | KEEP+ITERATE | Optional noch: Wechseln in den Edge Mode<br>    <br>Möglichkeit A (Doppelklick): Doppelklick auf eine Kante.  Wählt automatisch den gesamten Edge Loop aus.<br>    <br>Möglichkeit B (Shift + Doppelklick): Klicken auf eine Kante, dann Shift + Doppelklick  auf eine parallele Kante im selben Loop, um nur ein bestimmtes Teilstück auszuwählen. |
| (s3) Regel „mit Auswahl wirkt alles auf die Auswahl, Klick ins Leere = zurück zum Hover-Ziehen“ | KEEP         |                                                                                                                                                                                                                                                                                                                                                     |
| (s4) Auswahl, Einfluss und Achsen-Sperre unterscheidbar                                         | KEEP         |                                                                                                                                                                                                                                                                                                                                                     |

Hinweis: Die Presets sind `K` = Smooth und `Shift+K` = Mexican Hat (mit Senke).

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
Slice 2b: Rotate/Scale bitgleich zu `SoftRotateOperation` / `SoftScaleOperation` für Gewichte in (0, 1] (Scale mit beiden
Formeln, drei Masken), negative Gewichte (`w · θ`, README-Tabelle linear/power, kein Clamp), N Schritte = 1 Schritt,
Commit/Cancel/Undo/Redo, Nachführen für Rotate/Scale inkl. Formelwechsel, W/E/R halten (scharf, Tippen = nichts, Ziel
eingefroren, Abbildung aus den Tool-Klassen, Stückelung egal, Ebenen, MIN_SCALE, Abbruchwege, Undo), `M`, HUD-Zähler,
Fenster-Pfad (R halten → ein Eintrag, RMB-Abbruch, Fokusverlust), Kurven-Rundungsschutz (Regression).
Slice 3 (`test_selection.py`, `test_selection_gl.py`): Klick ersetzen/hinzu/weg/umschalten je Modus, Klick ins Leere,
Schwelle aus `mirai.interaction.pointer` (Klick darunter, Ziehen ab der Schwelle, gepufferte Schritte einzeln),
`1`/`2`/`3`, Presets auf `K`/`Shift+K` (nicht in der Artist Truth), Shift+L/Shift+R (hinzufügen, Rand-Loop, Punktmodus,
Flächenmodus abgelehnt, Shift+R schärft kein Scale), Ziel-Regel E26 (Seeds = Auswahl-Vertices; W/E/R auf der Auswahl =
gleiche Seeds als Ziel; leere Auswahl = Ergebnisse wie vorher), LMB-Ziehen auf der Auswahl, Nachführen mit
Auswahl-Seeds nach Auswahlwechsel, Undo/Redo behalten / `B` leert, Eingaben ignoriert während einer Geste oder eines
offenen Drucks, HUD-Zeile; Fenster: Klick wählt und zeichnet je Modus, Modifier-Klicks, Ziehen bewegt die Auswahl,
**Ziehen ohne Auswahl bitgleich zum Slice-1–2b-Pfad** (mit Achsen-Sperre), Druck ins Leere zieht nichts, Alt-Klick /
Alt-Orbit, `Esc` verwirft einen offenen Druck, Shift+L/R im Fenster.
