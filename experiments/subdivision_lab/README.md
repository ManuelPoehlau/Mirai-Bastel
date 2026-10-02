# Subdivision-Mini-Lab (WP-SUBD-LAB-01, Slice 1)

**Status: Nicht Artist-validiert.** Gebaut und automatisch getestet; kein Verdikt von Manu liegt vor.
Dieses Lab bereitet vor, es entscheidet nichts: Es macht die Recherche-Tests **T-SUBD-1** (Käfig, Fläche oder beides)
und **T-SUBD-2** (wie glatt ist glatt genug) spielbar und misst, was Subdivision auf dem Referenz-PC kostet.

Forschungs-Lab unter `experiments/` — kein Production-Code, nichts in `src/`, `playground/`, `examples/` oder `tests/`
wurde geändert. Das Lab importiert nichts aus `playground/` oder anderen Experimenten (Test: `tests/test_import_boundary.py`).

## Starten

Vom Repo-Root, unter Windows und Linux gleich (nur `pyglet` wird zusätzlich gebraucht):

```
python experiments/subdivision_lab/run.py                       # head_basemesh (Default)
python experiments/subdivision_lab/run.py subd_cube
python experiments/subdivision_lab/run.py head_basemesh --host "Manu-PC"
```

Gültige Namen: `head_basemesh`, `man_with_shoes_basemesh`, `subd_cube` (Registry `examples/loaders/assets.py`).
Ein unbekannter Name beendet mit Exit-Code 2 und der Liste der gültigen Namen, bevor ein Fenster aufgeht.
`--host` ist das Label, das über jeder Bench-Tabelle (F9) steht — **wo gemessen wurde**.

Beim Start stehen `GL_VERSION` und `GL_RENDERER` in der Konsole und im HUD (offener Punkt in
`docs/architecture/REFERENCE_HARDWARE.md` §2 — das Lab druckt nur, die Datei wird nicht angefasst).

## Was man sieht

Das Control-Mesh ist das einzige maßgebliche Mesh. Die glatte Fläche ist abgeleitet (uniformes Catmull-Clark),
wird nie zurückgeschrieben und hat kein Picking.

| Ansicht | Taste `V` | Inhalt |
|---|---|---|
| **V-CAGE** | Start | Control-Mesh schattiert + Wire — der heutige Stand („Variante A“) |
| **V-BOTH** | 1× `V` | glatte Fläche schattiert + **Käfig-Wire** darüber („Variante B“); `X`: Käfig-Tiefentest an / immer sichtbar |
| **V-ISO** | 2× `V` | glatte Fläche schattiert + **nur Isolinien** (die Control-Kanten, wie sie auf der Fläche liegen), kein Käfig („Variante C“) |

- **Stufe 1 / 2 / 3** mit den Tasten `1` `2` `3` (Level 0 = Inhalt von V-CAGE). Stufen werden beim ersten Bedarf gebaut und gecacht.
  Stufe und Ansicht sind **Ansichts-Zustand** — kein Dokument-Zustand, kein Undo (ob die Stufe ins Dokument gehört, ist
  die offene Architekturfrage OF-3; das Lab beantwortet sie nicht).
- **Limit** `MAX_DERIVED_FACES = 25 000` (provisorisch, vom Agent gesetzt, **keine Messung**): eine Stufe darüber wird mit einer
  HUD-Warnung abgelehnt. `head_basemesh` Stufe 3 = 20 736 Flächen → erlaubt; `man_with_shoes_basemesh` Stufe 3 = 59 264 → abgelehnt, Stufe 2 = 14 816 → erlaubt.
- **Control-Vertex ziehen:** Maus nahe an einen Control-Vertex (Hover-Punkt, 14 px), LMB ziehen → der Vertex wandert in der Bildebene,
  die Fläche folgt live. Pro Drag-Event wird nur aktualisiert, was vom bewegten Vertex abhängt (lokales Update über Stencils,
  kein struktureller Rebuild). In V-CAGE zählen verdeckte Vertices nicht (Occlusion wie in Production); in V-BOTH/V-ISO
  ist **jeder** Control-Vertex greifbar, auch ein von der Fläche verdeckter, weil es kein Flächen-Picking gibt.
  Das ist Lab-Pragmatik, **keine** Antwort auf die offene Frage „wo greift man an“ (D1/D2).
- **`B`** schaltet zum Vergleich auf die Käfig-Ansicht (V-CAGE) um und wieder zurück; die gewählte Ansicht und Stufe bleiben.

## Steuerung

Die Tabelle ist `LAB_OVERRIDES` in `lab_bindings.py` (wird beim Start gedruckt; ein Test prüft Gleichheit 1:1).
Fest durch die Artist Input Truth: Alt+LMB Orbit, Shift+LMB Pan, Mausrad Zoom, `H` HUD, `Esc` Beenden.
**Die lab-lokalen Tasten (`1` `2` `3` `V` `X` `B` `F9`) sind ein Vorschlag für dieses Lab, keine Artist-Entscheidung.**
`Q` `W` `E` `R` (AD-016) und `C` (AD-017) sind reserviert und nicht belegt.

| Eingabe | Funktion | Quelle / Hinweis |
|---|---|---|
| Alt+LMB ziehen | Orbit | Artist Input Truth |
| Shift+LMB ziehen | Pan | Artist Input Truth |
| Mausrad | Zoom | Artist Input Truth |
| RMB ziehen | Orbit | Production-Default wie src/main.py |
| MMB ziehen | Pan | Production-Default wie src/main.py |
| LMB ziehen | Control-Vertex greifen und in der Bildebene ziehen | lab-lokal; Hover = nächster Control-Vertex (14 px) |
| 1 | Stufe 1 | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| 2 | Stufe 2 | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| 3 | Stufe 3 | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| V | Ansicht wechseln (V-CAGE → V-BOTH → V-ISO) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| X | Käfig-Tiefentest an / immer sichtbar (V-BOTH) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| B | A/B-Vergleich mit der Käfig-Ansicht (Umschalter) | lab-lokal; Toggle, nicht Halten (AD-013 A3 offen) |
| F9 | Bench auf diesem PC (Fenster friert ein) | lab-lokal (Vorschlag, keine Artist-Entscheidung) |
| H | HUD an/aus | = application.toggle_hud |
| Esc | Beenden | Q bewusst nicht belegt (Artist Truth: Move) |

## HUD

Ansicht, Stufe, Control V/F, Fläche V/F, Käfig-Tiefentest, **Aufbau/Refresh (letzter)** in ms (Stufe bauen bzw. verstaubte Stufe
neu berechnen), **Drag-Update (letzter)** in ms (kompletter Schritt: Control-Mesh → lokales Update → abgeleitetes Mesh → GPU-Sync →
Linien), **Frame** (gleitender Mittelwert), `GL_VERSION`, `GL_RENDERER`, Host-Label, Warnungen.

## Artist-Testbogen (Manu trägt die Verdikte ein — der Agent nie)

Jede Variante wird mit **KEEP / ITERATE / REJECT / UNKNOWN** beurteilt; UNKNOWN ist eine gültige Antwort.
Jeder Test dauert ein paar Minuten auf `head_basemesh`.

**T-SUBD-1 — Käfig, Fläche oder beides.** Aufgabe: *Eine Wange ein wenig vorziehen.*
Variante A: V-CAGE (heutiger Stand). Variante B: V-BOTH (Käfig über glatter Fläche), einmal Käfig-Tiefentest an, einmal immer sichtbar.
Variante C: V-ISO. Frage pro Variante: *Würde ich so modellieren wollen?*
Zusatzbeobachtung (eine Zeile, kein Verdikt): *Welche Ansicht lasse ich am Ende stehen, und wann wechsle ich?*

| Variante | Verdikt (KEEP / ITERATE / REJECT / UNKNOWN) | Notiz |
|---|---|---|
| A — V-CAGE |  |  |
| B — V-BOTH, Tiefentest an |  |  |
| B — V-BOTH, immer sichtbar |  |  |
| C — V-ISO |  |  |

Zusatzbeobachtung: _(leer)_

**T-SUBD-2 — Wie glatt ist glatt genug.** Gleiche Pose, Stufe 1 / 2 / 3, gleiche Beleuchtung, `B` für den Vergleich mit der Käfig-Ansicht.
Frage pro Stufe: *Stört beim Modellieren noch etwas an der Glätte?* und *Fühlt sich das Ziehen auf meinem PC flüssig genug an?*
(Zwei getrennte Verdikte pro Stufe: Glätte, Ziehen.)

| Stufe | Verdikt Glätte | Verdikt Ziehen | Notiz |
|---|---|---|---|
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |

## Messung

Der Bench druckt `GL_VERSION`/`GL_RENDERER` und eine Markdown-Tabelle; **jede Zahl nennt, wo sie gemessen wurde**
(Host-Label, headless oder sichtbares Fenster). Headless-Zahlen ersetzen keine Messung auf dem Referenz-PC
(`docs/architecture/REFERENCE_HARDWARE.md` §4).

- **Auf dem Referenz-PC (Windows, sichtbares Fenster):** Lab mit `--host "Manu-PC"` starten, `F9` drücken. Das Fenster
  reagiert bis zum Ende nicht (bis zu 30 Läufe je Zeile, Fortschritt in der Konsole); die Tabelle steht danach in der Konsole.
  Pro Zeile gilt ein Zeitbudget (Default 60 s, `--budget` beim `bench.py`; 0 = unbegrenzt): Wer es erreicht, hört vorzeitig auf und
  nennt in der Tabelle sein kleineres n („n von 30 (Budget)“) — sonst würde Stufe 3 auf einem langsamen PC Stunden dauern.
  Oder ohne das Lab-Fenster: `python experiments/subdivision_lab/bench.py --host "Manu-PC" --visible`.
- **Headless (Agent, Xvfb):** `xvfb-run -a python experiments/subdivision_lab/bench.py --host "<Label>"`; `--runs N` ändert die Läufe (Default 30).

| ID | Was |
|---|---|
| M1 | Topologie + Stencils bauen (einmalig pro Stufe, ab Control-Topologie) |
| M2 | abgeleitetes `core.Mesh` bauen + erste `RenderMesh`-Allokation (einmalig pro Stufe) |
| M3 | `apply_full`: alle abgeleiteten Positionen aus den Control-Positionen |
| M4 | `apply_local` für einen Control-Vertex (Valenz 4 und ein Pol, falls vorhanden) |
| M5 | GPU-Sync über `RenderMesh` nach **vollem** Positions-Update (`mark_vertices_dirty(alle)` + `sync()`) |
| M6 | GPU-Sync über `RenderMesh` nach **lokalem** Update |
| M7 | Käfig-/Isolinien-Segmente neu bauen |
| M8 | ein Frame `draw()` + `glFinish` (V-BOTH; V-ISO als M8i, V-CAGE als M8c) |
| M5w / M6w | (Zusatz) die abgeleiteten Positionen ins Lab-`core.Mesh` schreiben, voll / lokal |
| D1 / D2 | (Zusatz) ein kompletter Drag-Schritt / ein Frame direkt danach; 100 simulierte Schritte, mit `benchmark_counters`-Delta und `resource_ids`-Vergleich |

### Referenz-PC (Core 2 Quad Q9550, GeForce 9800 GTX) — **leer, bis Manu (oder ein Agent mit Manus Lauf) misst**

Keine Zahl hier ist gemessen. Beobachtung ≠ Interpretation: erst eintragen, was die Tabelle ausgibt.

| Asset / Stufe | ID | min (ms) | Median (ms) | max (ms) |
|---|---|---:|---:|---:|
|  |  |  |  |  |

`GL_VERSION`: _(leer)_ · `GL_RENDERER`: _(leer)_

### Headless-Messung (Cloud-Sandbox, Agent-Lauf 2026-10-02) — **kein Referenz-PC**

Gemessen unter Xvfb mit Software-GL (llvmpipe, Mesa) auf einer modernen Cloud-CPU; Host-Label `cloud-sandbox (Linux, Xvfb, llvmpipe), kein Referenz-PC`.
Das sagt **nichts** über Q9550 / GeForce 9800 GTX; es zeigt nur Größenordnungen und Verhältnisse. Medianwerte in ms (min/max und n stehen im
vollständigen Lauf darunter); „M4“ und „M6“ für den Vertex mit Valenz 4. ¹ = Zeitbudget (30 s pro Zeile) erreicht, weniger als 30 Läufe
(bzw. 100 Drag-Schritte) — siehe n im vollständigen Lauf.

| Asset / Stufe | M1 | M2 | M3 | M4 | M5 | M6 | M7 | M8 | D1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| head_basemesh / Stufe 1 | 10.4 | 30.8 | 1.0 | 0.02 | 248.0 | 6.9 | 0.4 | 2.0 | 7.9 |
| head_basemesh / Stufe 2 | 76.1 | 185.3 | 6.3 | 0.2 | 4090.9 ¹ | 152.2 | 0.7 | 2.7 | 148.5 |
| head_basemesh / Stufe 3 | 391.9 | 901.7 | 31.7 | 1.3 | 63427.7 ¹ | 2787.5 ¹ | 1.5 | 5.0 | 2844.8 ¹ |
| man_with_shoes_basemesh / Stufe 1 | 33.8 | 123.8 | 3.5 | 0.02 | 2033.0 ¹ | 20.7 | 1.4 | 3.0 | 24.5 |
| man_with_shoes_basemesh / Stufe 2 | 235.3 | 650.7 | 19.3 | 0.2 | 34307.2 ¹ | 446.3 | 2.3 | 5.6 | 432.1 ¹ |
| man_with_shoes_basemesh / Stufe 3 | *abgelehnt (Limit 25 000), nicht gemessen* | | | | | | | | |

**Beobachtung (nicht Interpretation):**

- Der komplette Drag-Schritt (D1) wächst stark mit der Gesamtgröße der Fläche, nicht nur mit der Zahl der betroffenen Vertices:
  `head_basemesh` Stufe 1 / 2 / 3 → 7,9 ms / 148 ms / 2 845 ms (Stufe 3: 11 Schritte); `man_with_shoes_basemesh` Stufe 1 / 2 → 24 ms / 432 ms.
  Betroffene abgeleitete Vertices pro Schritt (Valenz 4, head): 25 / 169 / 841.
- Fast die ganze Schrittzeit ist der GPU-Sync über `RenderMesh` (M6 ≈ D1). `apply_local` (M4), das Schreiben ins Lab-Mesh (M6w) und die
  Linien-Segmente (M7) bleiben dagegen klein (zusammen rund 3 ms bei head Stufe 3).
- `cProfile`, 10 Drag-Schritte, head Stufe 2 (1,80 s gesamt): 1,64 s in `GLRenderStore._patch_attribute` (4 120 Aufrufe), 0,047 s in
  `derived.recompute_bounds`. `_patch_attribute` schreibt bei **jedem** `store.update` den **ganzen** CPU-Puffer des Attributs in die
  VertexList (`target[0:len(data)] = data`). Das Handoff (§5) nannte „ein `store.update` pro bewegtem Vertex + Bounds-Pass über alle
  Vertices“ als Hotspot; die Messung zeigt den Ganzpuffer-Write pro Update als eigentlichen Kostentreiber.
- Voller Update (M5) head Stufe 3: ≈ 63 s pro Sync; Stufe 2: ≈ 4 s.
- `benchmark_counters` über 100 simulierte Drag-Schritte: `structural_rebuilds` und `topology_updates` unverändert (0), `resource_ids`
  unverändert, `glGetError = 0` (head Stufe 1/2; bei den gekürzten Läufen über die jeweils gemessenen Schritte genauso).

Offen (nicht entschieden, **nichts daran geändert**, Handoff-Stoppregel 5): ob und wie der Sync schneller werden soll, und ob dieselbe
Eigenschaft von `_patch_attribute` auch Production-Bewegungen auf großen Meshes betrifft — nicht geprüft.

<details>
<summary>Vollständiger Lauf (min / Median / max, n)</summary>

#### Subdivision-Lab — Messung

- Host-Label: **cloud-sandbox (Linux, Xvfb, llvmpipe), kein Referenz-PC**
- Modus: **headless/unsichtbares Fenster (Xvfb oder EGL)**
- GL_VERSION: `4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.2`
- GL_RENDERER: `llvmpipe (LLVM 20.1.2, 256 bits)`
- Python 3.11.15 auf Linux-6.18.44-fc-v51-x86_64-with-glibc2.39
- Läufe pro Zeile: 30 (Drag: 100 Schritte), Zeitbudget pro Zeile: 30 s; Zeiten in ms (min / Median / max)
- Headless-Zahlen ersetzen keine Messung auf dem Referenz-PC (`docs/architecture/REFERENCE_HARDWARE.md` §4).

### head_basemesh — Stufe 1

| ID | Was | min | Median | max | n |
|---|---|---:|---:|---:|---:|
| M1 | Topologie + Stencils bauen (einmalig pro Stufe, ab Control) | 9.753 | 10.357 | 20.839 | 30 |
| M2 | abgeleitetes core.Mesh + erste RenderMesh-Allokation (einmalig pro Stufe) | 28.423 | 30.840 | 57.563 | 30 |
| M3 | apply_full (alle abgeleiteten Positionen) | 0.971 | 1.011 | 1.550 | 30 |
| M5w | alle abgeleiteten Positionen ins core.Mesh schreiben | 0.161 | 0.170 | 0.344 | 30 |
| M5 | GPU-Sync nach VOLLEM Update (mark_vertices_dirty(alle) + sync()) | 228.788 | 248.042 | 347.962 | 30 |
| M4 | apply_local — Pol (Valenz 5, 31 abgeleitete Vertices betroffen) | 0.025 | 0.026 | 0.098 | 30 |
| M6w | lokale Positionen ins core.Mesh schreiben — Pol | 0.004 | 0.004 | 0.029 | 30 |
| M6 | GPU-Sync nach LOKALEM Update — Pol | 8.432 | 8.919 | 12.475 | 30 |
| M4 | apply_local — Valenz 4 (Valenz 4, 25 abgeleitete Vertices betroffen) | 0.020 | 0.021 | 0.081 | 30 |
| M6w | lokale Positionen ins core.Mesh schreiben — Valenz 4 | 0.003 | 0.003 | 0.022 | 30 |
| M6 | GPU-Sync nach LOKALEM Update — Valenz 4 | 6.824 | 6.945 | 9.042 | 30 |
| M7 | Käfig- + Isolinien-Segmente neu bauen | 0.376 | 0.400 | 0.548 | 30 |
| M8 | ein Frame V-BOTH (draw + glFinish) | 1.682 | 1.982 | 3.000 | 30 |
| M8i | ein Frame V-ISO (draw + glFinish) | 1.625 | 2.148 | 4.168 | 30 |
| M8c | ein Frame V-CAGE (Control-Mesh, draw + glFinish) | 0.973 | 1.405 | 2.776 | 30 |
| D1 | ein kompletter Drag-Schritt (Valenz 4) | 7.428 | 7.944 | 19.202 | 100 |
| D2 | ein Frame direkt nach dem Drag-Schritt (draw + glFinish) | 1.990 | 2.562 | 9.226 | 100 |

- Fläche: 1298 V / 1296 F; Stencil-Einträge: 8102; Control: 326 V / 324 F.
- Drag (100 Schritte) benchmark_counters-Delta: {'structural_rebuilds': 0, 'topology_updates': 0, 'vertex_updates': 2500, 'geometry_uploads': 7400, 'bounds_recalculations': 100}; resource_ids unverändert; glGetError = 0.

### head_basemesh — Stufe 2

| ID | Was | min | Median | max | n |
|---|---|---:|---:|---:|---:|
| M1 | Topologie + Stencils bauen (einmalig pro Stufe, ab Control) | 62.929 | 76.101 | 115.680 | 30 |
| M2 | abgeleitetes core.Mesh + erste RenderMesh-Allokation (einmalig pro Stufe) | 151.700 | 185.255 | 248.781 | 30 |
| M3 | apply_full (alle abgeleiteten Positionen) | 5.982 | 6.324 | 6.801 | 30 |
| M5w | alle abgeleiteten Positionen ins core.Mesh schreiben | 0.855 | 1.037 | 1.235 | 30 |
| M5 | GPU-Sync nach VOLLEM Update (mark_vertices_dirty(alle) + sync()) | 3812.657 | 4090.893 | 4301.448 | 8 von 30 (Budget) |
| M4 | apply_local — Pol (Valenz 5, 205 abgeleitete Vertices betroffen) | 0.234 | 0.238 | 0.439 | 30 |
| M6w | lokale Positionen ins core.Mesh schreiben — Pol | 0.024 | 0.026 | 0.148 | 30 |
| M6 | GPU-Sync nach LOKALEM Update — Pol | 167.059 | 183.146 | 251.603 | 30 |
| M4 | apply_local — Valenz 4 (Valenz 4, 169 abgeleitete Vertices betroffen) | 0.192 | 0.195 | 0.368 | 30 |
| M6w | lokale Positionen ins core.Mesh schreiben — Valenz 4 | 0.020 | 0.024 | 0.145 | 30 |
| M6 | GPU-Sync nach LOKALEM Update — Valenz 4 | 141.178 | 152.161 | 242.965 | 30 |
| M7 | Käfig- + Isolinien-Segmente neu bauen | 0.664 | 0.735 | 1.873 | 30 |
| M8 | ein Frame V-BOTH (draw + glFinish) | 2.025 | 2.713 | 3.397 | 30 |
| M8i | ein Frame V-ISO (draw + glFinish) | 2.393 | 3.091 | 6.690 | 30 |
| M8c | ein Frame V-CAGE (Control-Mesh, draw + glFinish) | 1.000 | 1.152 | 1.864 | 30 |
| D1 | ein kompletter Drag-Schritt (Valenz 4) | 141.073 | 148.481 | 228.999 | 100 |
| D2 | ein Frame direkt nach dem Drag-Schritt (draw + glFinish) | 3.118 | 3.731 | 6.595 | 100 |

- Zeilen mit „n von N (Budget)“ haben das Zeitbudget (30 s pro Zeile) erreicht und vorzeitig aufgehört: weniger Läufe als gefordert, die Spanne ist weniger belastbar.

- Fläche: 5186 V / 5184 F; Stencil-Einträge: 54998; Control: 326 V / 324 F.
- Drag (100 Schritte) benchmark_counters-Delta: {'structural_rebuilds': 0, 'topology_updates': 0, 'vertex_updates': 16900, 'geometry_uploads': 39400, 'bounds_recalculations': 100}; resource_ids unverändert; glGetError = 0.

### head_basemesh — Stufe 3

| ID | Was | min | Median | max | n |
|---|---|---:|---:|---:|---:|
| M1 | Topologie + Stencils bauen (einmalig pro Stufe, ab Control) | 343.882 | 391.939 | 456.024 | 30 |
| M2 | abgeleitetes core.Mesh + erste RenderMesh-Allokation (einmalig pro Stufe) | 812.709 | 901.671 | 1103.665 | 30 |
| M3 | apply_full (alle abgeleiteten Positionen) | 30.563 | 31.678 | 50.900 | 30 |
| M5w | alle abgeleiteten Positionen ins core.Mesh schreiben | 3.118 | 3.527 | 6.558 | 30 |
| M5 | GPU-Sync nach VOLLEM Update (mark_vertices_dirty(alle) + sync()) | 62885.789 | 63427.739 | 63633.498 | 3 von 30 (Budget) |
| M4 | apply_local — Pol (Valenz 5, 1009 abgeleitete Vertices betroffen) | 1.451 | 1.486 | 2.117 | 30 |
| M6w | lokale Positionen ins core.Mesh schreiben — Pol | 0.144 | 0.157 | 0.499 | 30 |
| M6 | GPU-Sync nach LOKALEM Update — Pol | 3202.777 | 3291.724 | 3503.468 | 10 von 30 (Budget) |
| M4 | apply_local — Valenz 4 (Valenz 4, 841 abgeleitete Vertices betroffen) | 1.196 | 1.285 | 2.558 | 30 |
| M6w | lokale Positionen ins core.Mesh schreiben — Valenz 4 | 0.120 | 0.155 | 0.527 | 30 |
| M6 | GPU-Sync nach LOKALEM Update — Valenz 4 | 2662.032 | 2787.542 | 3127.242 | 11 von 30 (Budget) |
| M7 | Käfig- + Isolinien-Segmente neu bauen | 1.464 | 1.525 | 4.721 | 30 |
| M8 | ein Frame V-BOTH (draw + glFinish) | 4.269 | 4.965 | 6.624 | 30 |
| M8i | ein Frame V-ISO (draw + glFinish) | 5.940 | 6.654 | 9.158 | 30 |
| M8c | ein Frame V-CAGE (Control-Mesh, draw + glFinish) | 1.561 | 1.855 | 3.337 | 30 |
| D1 | ein kompletter Drag-Schritt (Valenz 4) | 2763.050 | 2844.800 | 3073.874 | 11 von 100 (Budget) |
| D2 | ein Frame direkt nach dem Drag-Schritt (draw + glFinish) | 6.161 | 6.792 | 8.361 | 11 von 100 (Budget) |

- Zeilen mit „n von N (Budget)“ haben das Zeitbudget (30 s pro Zeile) erreicht und vorzeitig aufgehört: weniger Läufe als gefordert, die Spanne ist weniger belastbar.

- Fläche: 20738 V / 20736 F; Stencil-Einträge: 274166; Control: 326 V / 324 F.
- Drag (11 Schritte) benchmark_counters-Delta: {'structural_rebuilds': 0, 'topology_updates': 0, 'vertex_updates': 9251, 'geometry_uploads': 19822, 'bounds_recalculations': 11}; resource_ids unverändert; glGetError = 0.

### man_with_shoes_basemesh — Stufe 1

| ID | Was | min | Median | max | n |
|---|---|---:|---:|---:|---:|
| M1 | Topologie + Stencils bauen (einmalig pro Stufe, ab Control) | 31.613 | 33.796 | 49.938 | 30 |
| M2 | abgeleitetes core.Mesh + erste RenderMesh-Allokation (einmalig pro Stufe) | 85.399 | 123.803 | 163.889 | 30 |
| M3 | apply_full (alle abgeleiteten Positionen) | 3.127 | 3.481 | 4.614 | 30 |
| M5w | alle abgeleiteten Positionen ins core.Mesh schreiben | 0.515 | 0.590 | 1.114 | 30 |
| M5 | GPU-Sync nach VOLLEM Update (mark_vertices_dirty(alle) + sync()) | 1936.730 | 2032.980 | 2401.360 | 15 von 30 (Budget) |
| M4 | apply_local — Valenz 4 (Valenz 4, 25 abgeleitete Vertices betroffen) | 0.021 | 0.021 | 0.086 | 30 |
| M6w | lokale Positionen ins core.Mesh schreiben — Valenz 4 | 0.003 | 0.003 | 0.026 | 30 |
| M6 | GPU-Sync nach LOKALEM Update — Valenz 4 | 19.836 | 20.745 | 28.196 | 30 |
| M4 | apply_local — Pol (Valenz 5, 31 abgeleitete Vertices betroffen) | 0.026 | 0.026 | 0.105 | 30 |
| M6w | lokale Positionen ins core.Mesh schreiben — Pol | 0.004 | 0.004 | 0.030 | 30 |
| M6 | GPU-Sync nach LOKALEM Update — Pol | 24.426 | 26.092 | 36.475 | 30 |
| M7 | Käfig- + Isolinien-Segmente neu bauen | 1.268 | 1.370 | 2.943 | 30 |
| M8 | ein Frame V-BOTH (draw + glFinish) | 2.105 | 3.039 | 3.858 | 30 |
| M8i | ein Frame V-ISO (draw + glFinish) | 2.581 | 2.910 | 3.624 | 30 |
| M8c | ein Frame V-CAGE (Control-Mesh, draw + glFinish) | 1.788 | 2.146 | 3.312 | 30 |
| D1 | ein kompletter Drag-Schritt (Valenz 4) | 21.914 | 24.455 | 58.598 | 100 |
| D2 | ein Frame direkt nach dem Drag-Schritt (draw + glFinish) | 3.122 | 3.650 | 6.102 | 100 |

- Zeilen mit „n von N (Budget)“ haben das Zeitbudget (30 s pro Zeile) erreicht und vorzeitig aufgehört: weniger Läufe als gefordert, die Spanne ist weniger belastbar.

- Fläche: 3706 V / 3704 F; Stencil-Einträge: 23152; Control: 928 V / 926 F.
- Drag (100 Schritte) benchmark_counters-Delta: {'structural_rebuilds': 0, 'topology_updates': 0, 'vertex_updates': 2500, 'geometry_uploads': 7400, 'bounds_recalculations': 100}; resource_ids unverändert; glGetError = 0.

### man_with_shoes_basemesh — Stufe 2

| ID | Was | min | Median | max | n |
|---|---|---:|---:|---:|---:|
| M1 | Topologie + Stencils bauen (einmalig pro Stufe, ab Control) | 196.641 | 235.343 | 331.649 | 30 |
| M2 | abgeleitetes core.Mesh + erste RenderMesh-Allokation (einmalig pro Stufe) | 527.282 | 650.656 | 894.588 | 30 |
| M3 | apply_full (alle abgeleiteten Positionen) | 18.754 | 19.336 | 22.249 | 30 |
| M5w | alle abgeleiteten Positionen ins core.Mesh schreiben | 2.188 | 2.494 | 3.987 | 30 |
| M5 | GPU-Sync nach VOLLEM Update (mark_vertices_dirty(alle) + sync()) | 33527.556 | 34307.227 | 34925.527 | 3 von 30 (Budget) |
| M4 | apply_local — Valenz 4 (Valenz 4, 169 abgeleitete Vertices betroffen) | 0.198 | 0.204 | 0.508 | 30 |
| M6w | lokale Positionen ins core.Mesh schreiben — Valenz 4 | 0.020 | 0.023 | 0.151 | 30 |
| M6 | GPU-Sync nach LOKALEM Update — Valenz 4 | 396.529 | 446.265 | 586.888 | 30 |
| M4 | apply_local — Pol (Valenz 5, 211 abgeleitete Vertices betroffen) | 0.249 | 0.265 | 0.664 | 30 |
| M6w | lokale Positionen ins core.Mesh schreiben — Pol | 0.025 | 0.027 | 0.187 | 30 |
| M6 | GPU-Sync nach LOKALEM Update — Pol | 498.814 | 545.525 | 708.884 | 30 |
| M7 | Käfig- + Isolinien-Segmente neu bauen | 2.210 | 2.343 | 5.284 | 30 |
| M8 | ein Frame V-BOTH (draw + glFinish) | 4.480 | 5.629 | 9.118 | 30 |
| M8i | ein Frame V-ISO (draw + glFinish) | 4.261 | 5.501 | 8.232 | 30 |
| M8c | ein Frame V-CAGE (Control-Mesh, draw + glFinish) | 1.420 | 1.704 | 3.762 | 30 |
| D1 | ein kompletter Drag-Schritt (Valenz 4) | 401.834 | 432.052 | 551.922 | 67 von 100 (Budget) |
| D2 | ein Frame direkt nach dem Drag-Schritt (draw + glFinish) | 4.955 | 5.656 | 8.100 | 67 von 100 (Budget) |

- Zeilen mit „n von N (Budget)“ haben das Zeitbudget (30 s pro Zeile) erreicht und vorzeitig aufgehört: weniger Läufe als gefordert, die Spanne ist weniger belastbar.

- Fläche: 14818 V / 14816 F; Stencil-Einträge: 157984; Control: 928 V / 926 F.
- Drag (67 Schritte) benchmark_counters-Delta: {'structural_rebuilds': 0, 'topology_updates': 0, 'vertex_updates': 11323, 'geometry_uploads': 26398, 'bounds_recalculations': 67}; resource_ids unverändert; glGetError = 0.

### man_with_shoes_basemesh — Stufe 3

- Stufe 3 abgelehnt (Lab-Limit): 59264 Flächen > 25000 — nicht gemessen.



</details>


## Technik in Kürze

- `subd.py` (GL-frei, reines Python, kein NumPy): Topologie pro Stufe einmal, Positionen über **Stencils** (dünn besetzte Gewichte
  Control-Vertex → abgeleiteter Vertex, über die Stufen komponiert), **Inverse Index** Control-Vertex → betroffene abgeleitete Vertices.
  Regeln: Face-Punkt = Mittel; innere Kante = Mittel(2 Endpunkte, 2 Face-Punkte); Randkante = Mittelpunkt;
  innerer Vertex `(F + 2R + (n−3)P)/n`; Randvertex mit zwei Randkanten `(P_prev + 6P + P_next)/8`; jedes n-Eck → n Vierecke.
  Nicht-Manifold-Eingaben lösen `SubdUnsupportedError` mit deutscher Meldung aus.
- `lab_scene.py`: zwei `RenderMesh` auf dem unveränderten Production-`GLRenderStore` (Control + abgeleitetes Wegwerf-`core.Mesh`,
  gebaut über `mesh_from_positions_and_faces`), eine gemeinsame `OrbitCamera`.
- `lab_lines.py`: Unterklasse von `GLLineOverlay` (Käfig-/Isolinien-Layer, Tiefentest pro Instanz umschaltbar) — Production unberührt.
- Das Lab ändert sein **eigenes** Control-Mesh per `Mesh.set_vertex_position` ohne `Operation`/`History` (Lab-Pragmatik, sagt nichts
  über Production-Move-Semantik).
- Alle Shader bleiben `#version 330 core`; keine Tessellation, kein Compute, keine Threads (Referenz-PC: OpenGL ≤ 3.3).

## Tests

```
xvfb-run -a python -m pytest experiments/subdivision_lab/tests        # Linux headless (Xvfb)
python -m pytest experiments/subdivision_lab/tests                    # Windows / Desktop
```

GL-Tests überspringen sich sauber, wenn kein GL verfügbar ist. Abgedeckt: exakte Werte (Würfel, Rand, n-Ecke), Stencil = direktes
rekursives Catmull-Clark, lokal = voll, Provenienz, nicht unterstützte Eingaben, Limit, Import-Grenze, Steuerungstabelle = README,
CLI, Control-Mesh unverändert, Drag ohne strukturellen Rebuild, Ansichten/A-B/Tiefentest, Bench-Smoke.

## Nicht im Scope (Slice 1)

Creases jeder Art, Limit-Surface-Normalen/Subdivision-Shading (T-SUBD-3), Picking auf der Fläche/Knife-Punkt-Mapping (T-SUBD-4),
Rand-/Eck-Sichttest (T-SUBD-5), Crease vs. Support-Loop (T-SUBD-6), Backing/Refine, partielle Subdivision, Unsubdivide,
Symmetrie-Interaktion, Undo/History, Morph/Skin/Deformation, NumPy/OpenSubdiv/native Bibliotheken/Threads/GPU-Compute,
Optimierung eines langsamen Pfads (messen und berichten), Screenshot-Funktion. Nicht entschieden: Stufe als Dokument-Zustand,
Crease-Speicherung, Tastenbelegung für Production.

## Quellen

Handoff WP-SUBD-LAB-01 Slice 1 (nicht im Repo, WP-Doc-Praxis); Strukturvorbild `experiments/viewport_shading_lab/`;
`docs/architecture/REFERENCE_HARDWARE.md`; `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` §2/§5; AD-013, AD-016, AD-017, AD-018.
Hinweis: Beim Bau dieses Labs lag `docs/research/subdivision/SUBDIVISION_SURFACES_RESEARCH.md` im Repo noch nicht vor;
Regeln, Tests und Maße stammen aus dem Handoff.
