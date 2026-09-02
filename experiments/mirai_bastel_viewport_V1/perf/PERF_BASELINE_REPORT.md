# Viewport V1 — Performance Baseline Report

> **Nur Messung.** Keine Optimierung wurde implementiert. Dieser Bericht
> dokumentiert den Befund und trennt Empfehlungen in Quick Win / mittelfristig /
> langfristige Viewport-Architektur.

## Kernergebnis (Bottom Line)

> **Der Viewport laggt bei 324 Quads, weil er bei jeder Mausbewegung die
> komplette Render-Geometrie neu aufbaut** — inklusive eines O(V×F)-Normalen-
> Loops (`_compute_normals`, 45 ms), Neuaufstellung aller Arrays und neuer
> VBOs pro Event. Das ist ein reines **CPU/Python-**Problem, kein GPU-Problem.
>
> Orbit ~85 ms (12 FPS), Zoom ~117 ms, Vertex-Drag ~101 ms bei nur 324 Quads.
> Hotspot: `_compute_normals` = ~76 % der Profilzeit (14.9 Mio.
> `face_vertices()`-Aufrufe in 25 s). Skalierung: quadratisch
> (47 ms → 770 ms → 22,4 s → ≈5 min pro Event bei 20k Quads).
>
> **Schnellster Befund für die Entscheidung:** Kamera-Drag/Zoom darf nicht
> `_rebuild_geometry()` auslösen (nur die Kamera ändert sich) + Normalen über
> eine einmalige Vertex→Faces-Adjazenz linearisieren. Beides ist ein Quick Win
> ohne Architekturänderung — Details in §5.

---

Stand: 2026-09-02 · Machine: Windows (alt, integrierte GPU) · Python 3.12.10 ·
pyglet 2.1.16 · Core V1 (`mirai_bastel_core`) · Asset:
`experiments/rigging-skinning-morphing/meshes/head_basemesh.obj`
(326 V / 648 E / 324 Quad-Faces, geschlossen, 100 % Quads)

## Methodik (Kurzfassung)

- Instrumentation ausschließlich per Monkey-Patching auf Fensterinstanzen
  (`perf/perf_probe.py`). **Keine Änderung** an `viewport/*.py`, Core oder
  Topology.
- Szenario-Messungen am echten pyglet-Fenster (VSync aus) mit direkt
  gelieferten Window-Events (gleiche Technik wie `_smoke_all_tools.py`):
  ein Frame = ein Event + ein `on_draw()`.
- Micro-Benchmarks spiegeln die exakten App-Routinen (`_compute_normals`,
  `_face_triangle_arrays`) headless nach (gleiche O(V×F)-Struktur, gleiche
  `face_vertices()`-Kopien).
- Jeder Wert in Millisekunden; bei großen Meshes Budget-Abbrüche (dann
  n/a bzw. extrapoliert markiert).

Rohdaten und Skripte: `perf/README.md`, `micro_bench_results.txt`,
`scenario_results.txt`, `scaling_results.txt`, `profile_results.txt`.

---

## 1. Performance Baseline (Head, 324 Quads)

Gemessen am echten Fenster (pyglet 2.1.16, VSync aus), 200 Events je
Szenario. „FPS" = 1000/avg (CPU-seitig, da das GPU-Rendering bei dieser
Meshgröße vernachlässigbar ist, siehe §2c).

| Test               | Avg (ms) | p50 | p95 | p99 | Max (ms) | FPS |
| ------------------ | -------: | --: | --: | --: | -------: | --: |
| Idle               |     0.32 | 0.23 | 0.55 | 2.01 |     4.27 | ~3.1 k |
| Orbit              |    85.71 | 63.2 | 229 | 367 |    877   | ~11.7 |
| Pan                |    85.03 | 63.4 | 132 | 457 |   1491   | ~11.8 |
| Zoom               |   117.22 | 65.3 | 408 | 658 |   1225   | ~8.5 |
| Hover (über Mesh)  |    12.78 | 7.1  | 61  | 76  |     83   | ~78   |
| Hover-still        |     7.47 | 6.9  | 8.4 | 17  |     51   | ~134  |
| Vertex Drag        |   100.67 | 54.8 | 265 | 617 |   1052   | ~9.9  |
| Edge Drag          |    72.06 | 58.3 | 146 | 281 |    662   | ~13.9 |
| Face Drag          |    67.09 | 56.4 | 119 | 260 |    388   | ~14.9 |

Wichtige Detailwerte (Komponenten-Anteile der Szenarien):

| Szenario     | `rebuild.geometry` | `rebuild.normals` | Picking | GL-VertexList | on_draw |
| ------------ | ------------------ | ----------------- | ------- | ------------- | ------- |
| Orbit        | 74.7 ms (87 %)     | 52.6 ms (61 %)    | 8.0 ms  | 4.8 ms        | 3.0 ms  |
| Pan          | 71.6 ms (84 %)     | 53.0 ms (62 %)    | 7.5 ms  | 4.5 ms        | 5.8 ms  |
| Zoom         | 100.8 ms (86 %)    | 59.1 ms (50 %)    | 10.4 ms | 8.9 ms        | 5.9 ms  |
| Hover-Move   | 57.0 ms (nur bei 19/200 Hover-Wechseln) | 49.4 ms | 6.7 ms (immer) | 1.2 ms | 0.7 ms |
| Vertex-Drag  | 95.6 ms (95 %)     | 62.4 ms (62 %)    | 6.8 ms  | 5.8 ms        | 4.5 ms  |
| Edge-Drag    | 69.9 ms (97 %)     | 57.2 ms (79 %)    | 21.8 ms | 1.9 ms        | 1.7 ms  |
| Face-Drag    | 65.0 ms (97 %)     | 53.9 ms (80 %)    | 2.1 ms  | 1.7 ms        | 1.7 ms  |

GC-Aktivität während der Szenarien: ~0–10 gen0-Collections je 200-Frame-
Szenario (also grob 1 Collection je 20–25 Frames oder seltener) und praktisch
keine gen1/gen2-Collections. **GC ist kein signifikanter Hotspot.**

Messung ist vollständig automatisiert und reproduzierbar
(`python -m perf.scenario_runner --events 200`), siehe Rohdaten
`scenario_results.txt`.

---

## 2. Hotspot-Analyse (Head, 324 Quads)

### 2a. Picking (pro Aufruf, headless gemessen)

| Operation         | Komplexität | avg (ms) |
| ----------------- | ----------- | -------: |
| `pick_nearest_vertex` | O(V) — alle 326 Vertices projektieren | ~6.9 |
| `pick_nearest_edge`   | O(E) — alle 648 Kanten, Punkt-Segment-Distanz | ~23 |
| `pick_face`           | O(F) — Ray-Triangle pro Face | ~2.1 |

Jeder Mouse-Move (Hover), jeder Orbit-/Pan-/Zoom-/Drag-Schritt und jeder
Selection-Klick ruft Picking auf. Picking läuft NIE geteilt über Frames —
immer ein Voll-Scan des Meshes.

## 2a2. cProfile-Hotspot-Tabelle (mixed orbit+hover+vertex-drag, 25.6 s Profil)

| Rang | Datei:Methode | Aufrufkontext | tottime | cumtime | Anteil (cum) |
| ---: | ------------- | ------------- | ------: | ------: | -----------: |
| 1 | `app.py:_compute_normals` | aus `_rebuild_geometry()` bei jedem Event | 10.0 s | 19.5 s | **~76 %** |
| 1b | `mesh.py:face_vertices()` | Innen-Loop von `_compute_normals` (O(V×F)); **14.88 Mio. Aufrufe** | 8.7 s | 8.7 s | ~34 % |
| 2 | `app.py:_rebuild_geometry` | Gesamt (inkl. Normalen + GL-VertexList) | 0.3 s | 22.8 s | **~89 %** |
| 3 | `picking.py:pick_nearest_vertex` | Hover/press (alle 160 Events) | 0.13 s | 2.54 s | ~10 % |
| 4 | `camera.py:project_to_screen` (+`basis`,`eye`) | in `pick_nearest_vertex`/`screen_delta_to_world` | 0.3+0.2+0.3 | 3.7 s | ~14 % |
| 5 | pyglet `shader.py:vertex_list`-Erzeugung (inkl. `vertexdomain`/`vertexbuffer`) | pro `_rebuild_geometry` erneut angelegte VBOs | ~0.5+0.35 | ~2.4 s | ~9 % |
| 6 | `app.py:_face_triangle_arrays` | Face-Triangulation (O(F), gecachte Normalen) | 0.54 s | 0.91 s | ~4 % |

Zusätzlich zu Zeile 1b: `mesh.py:vertex_position` 0.64 Mio. Aufrufe und
`list.extend` 0.73 Mio. Aufrufe (Array-Neubau pro Rebuild) stützen den
„Python-Allokation pro Rebuild"-Befund (siehe `micro_bench_results.txt`,
>200 KiB Spitzen-Allokation pro Rebuild beim Head). `math.hypot`/`normalize`/
`length` (0.47/0.33/0.38 s) stecken hauptsächlich im Picking-/Camera-Pfad.

**Fazit der Profilierung:** >85 % der CPU-Zeit entfallen auf den einen
Rebuild-Fluss (im Wesentlichen `_compute_normals` mit seinem O(V×F)-Loop),
~10 % auf Picking; Rendering/Upload/draw sind klein.

### 2b. Geometry-Rebuild (`_rebuild_geometry`, headless CPU-Anteil, app-korrigiert)

| Stufe                     | Aufruf | Komplexität | Head (ms) | Anteil |
| ------------------------- | ------ | ----------- | --------: | -----: |
| `_compute_normals`        | pro Rebuild | **O(V×F)** + `face_vertices()`-Kopien | ~45 | **~96 %** |
| `_face_triangle_arrays`   | pro Rebuild (gecachte Normalen) | O(F) | ~1.4 | ~3 % |
| Positions-/Edge-Flattening | pro Rebuild | O(V+E) | ~0.5 | ~1 % |
| `program.vertex_list` ×3-9| pro Rebuild | VBO-Alloc + Upload (nur Fenster) | ~4.5/Eintrag (Fenster) | — |
| **Summe `_rebuild_geometry` CPU** | | | **~47** | |

**Kritisch:** `_rebuild_geometry()` wird **bei jeder Hover-Änderung, bei jedem
Maus-Drag-Schritt (Orbit/Pan/Zoom/Tool) und jedem Selection-Update
vollständig neu ausgeführt** — inklusive Normalen-Rebuild, Triangle-Array-
Neubau und 9× neuer `program.vertex_list` (VBO-Allokation + Upload).

Ablauf bestätigt (app.py):

```text
on_mouse_motion           → _pick()                 (O(V)..O(F))
                            └ hovered != old  → _rebuild_geometry()
on_mouse_drag (orbit/pan) → camera.orbit/pan
                            └ _refresh_hover()      → _pick() + _rebuild_geometry()
on_mouse_scroll (zoom)    → camera.dolly
                            └ _refresh_hover()      → _pick() + _rebuild_geometry()
on_mouse_press (select)   → _pick() + selection.set() + _rebuild_geometry()
on_mouse_drag (tool)      → tool.update()
                            └ _rebuild_geometry()
```

Der frühere Verdacht „rebuilds geometry on every hover/drag (O(V×F))" ist
**bestätigt** — inklusive des O(V×F)-Normalen-Loops pro Rebuild.

### 2c. GPU vs. CPU

- Szenario-Messung am echten Fenster (mit GL-VertexList-Erzeugung und
  Upload) → siehe §1. Dortige `rebuild.geometry`-Zeit ist die Summe aus
  CPU-Arrays + GL-Upload.
- Reine CPU-Zeit von ~47 ms bei 324 Quads (Normals allein 45 ms) liegt
  **weit über** dem, was eine GPU für 324 Quads braucht (Sekundenbruchteil).
  Das schließt GPU-Rendering als primäre Ursache aus; auch der GL-Upload ist
  klein (~1–5 ms/Eintrag, überwiegend Python/ctypes-Konvertierung), wird aber
  bei jedem Rebuild wiederholt (neue VertexList pro Rebuild → neue
  VBO-Allokation).
- Einziger Draw-Pfad: typisch 3–6 kleine `draw()`-Aufrufe pro Frame (Faces,
  Edges, Points, Hover, Selection) — bei 324 Quads vernachlässigbar
  (on_draw ≈ 0.3 ms idle, ≈ 3–6 ms im Drag wegen gleichzeitiger CPU-Last).

---

## 3. Skalierung (~324 / ~1.3k / ~5k / ~20k Quads)

Synthetische geschlossene Quad-Tori (gleiche topologische Klasse, bewusst
ohne realistische Form). Headless gemessene CPU-Zeit pro Rebuild
(app-korrigiert: Normalen einmal, Triangle-Arrays mit gecachten Normalen):

| Quads | normals O(V×F) | triangle-Arrays (O(F)) | CPU-Rebuild gesamt |
| ----: | -------------: | ---------------------: | -----------------: |
|   324 |          45.4  |                   1.4  |            47.0    |
|  1296 |         736.8  |                   7.7  |           770.2    |
|  4970 |       21217    |                  32.3  |         22371      |
| 20022 |      314481    |              (≈130)   |       ≈314600      |

(20k: Normals-Messung exakt aus einem isolierten Einzel-Lauf; Triangle-
Arrays/Flatten linear hochgerechnet, da bei dieser Größe vernachlässigbar
klein gegenüber dem Normalen-Term.)

**Skalierungsverhalten:** Ver-Vierfachung der Faces ⇒ ~15–29× Rebuild-Zeit —
konsistent mit O(V×F) (quadratisch). Der Normalen-Term dominiert ab ~1k Quads
>95 % der Rebuild-Zeit; Triangle-Arrays und Flattening wachsen linear und
sind klein.

Bei 20k Quads würde ein einziger Hover-/Drag-Event den Viewport für
**~5 Minuten** blockieren — der Viewport ist dort vollständig unbedienbar.

### Fenster-Szenario-Skalierung (Orbit/Hover, echtes GL)

| Quads | Orbit Frame (ms) | FPS  | Hover Frame (ms) | FPS  | Rebuild/Event (ms) |
| ----: | ---------------: | ---: | ---------------: | ---: | -----------------: |
|   324 |             62.6 | ~16  |          21.1(*) | ~47  |            ~55–57  |
|  1296 |           1211.5 | ~0.8 |        1005.6(*) | ~1.0 |        ~1134–1226 |
|  4970 |          12818.7 | ~0.1 |       17732.0(*) | ~0.1 |       ~12710–17594 |
| 20022 |            n/a   |  —   |            n/a   |  —   |      ≈314 600 (CPU) |

\* End-to-End-Frame-Zeit über die Maus-Punkte (inkl. Picking); der Rebuild
läuft nur bei Hover-Wechseln, daher kann der Frame-Schnitt bei 324er Größe
niedriger sein als der einzelne Rebuild. Die Spalte „Rebuild/Event" ist die
bei einem Hover-Wechsel tatsächlich gemessene `rebuild.geometry`-Zeit.

(Skalierungsverhältnis Orbit 324→1296: ~19×, 1296→4970: ~11× pro:
korreliert mit der O(V×F)-Normalen-Stufe; 20k wurde wegen der multi-
minütigen Rebuilds bewusst nicht im Fensterszenario ausgeführt.)

---

## 4. Root Cause

Der Viewport V1 baut bei **jedem Kamera-Drag-Event, jedem Hover-Wechsel,
jedem Selection-Update und jedem Tool-Drag-Event die komplette Render-
Geometrie neu auf** — nicht „wenn nötig":

- `on_mouse_drag()` (Orbit/Pan) ruft nach der Kamerabewegung **immer**
  `_refresh_hover()` → `_pick()` **und** `_rebuild_geometry()` auf, obwohl die
  Mesh-Geometrie unverändert ist.
- `on_mouse_scroll()` (Zoom), `on_mouse_press()` (Selection) und der
  Tool-Drag (`on_mouse_drag` Mode "tool") ebenso.
- `_rebuild_geometry()` enthält die O(V×F)-Vertex-Normalen-Mittelung
  `_compute_normals()` (bei 324 Quads **45 ms** = ~96 % der Rebuild-CPU-Zeit,
  ab ~1k Quads >95 %) plus vollständige Neuaufstellung aller Python-Arrays
  und **neuer** `program.vertex_list`-Objekte (VBO-Allokation + Upload).

Damit kostet ein Kamera-/Drag-Event bei 324 Quads ~65–100 ms (8–15 FPS),
obwohl weder Mesh-Geometrie noch Topologie sich ändern. Picking
(O(V/E/F)-Vollscan, 6–22 ms) kommt erschwerend bei jedem Event hinzu.

**Kurz:** Das Problem ist **nicht** das Rendern (GPU), sondern der Python-
Hot-Path „Event → Voll-Picking + Voll-Rebuild inkl. O(V×F)-Normalen" —
und zwar bei **jeder Mausbewegung**, nicht nur bei echten Geometrieänderungen.

---

## 5. Empfehlungen

### Quick Win (klein, ohne Architekturänderung, hohe Wirkung)

1. **Kamera-Drag/Zoom darf NIE `_rebuild_geometry()` auslösen.** Orbit/Pan/Zoom
   ändern nur die Kamera — die vorhandenen VertexLists bleiben unverändert
   gültig. Das entfernt ~70–100 ms pro Event (Orbit 85 ms → praktisch unter
   die Picking-/Draw-Kosten). Hover-Highlight während des Kamera-Drags kann
   über „nur bei geändertem Hover rebuilden" erhalten bleiben.
2. **Picking während Orbit/Pan/Zoom weglassen** (aktuell 6–10 ms/Event).
   Hover-Refresh ist während einer Kamerafahrt nicht nötig (und sowieso
   veraltet, weil die Mausposition gegenüber der Szene springt).
3. **`_compute_normals` linearisieren:** Einmalig (bei Topologieänderung)
   Vertex→Faces-Adjazenz bauen; pro Frame dann O(F+V) statt O(V×F). Das
   allein reduziert den Rebuild bei 324 Quads von ~47 ms auf wenige ms und
   entkräftet die quadratische Skalierung in §3 komplett.
4. **VertexLists wiederverwenden statt pro Rebuild neu erzeugen:** pyglet-
   VertexLists unterstützen Positions-Update (`vertex_list.position = [...]`)
   bzw. können über `ShaderProgram.vertex_list` einmalig angelegt und per
   `resize+update` serviert werden. Das entfernt die wiederholte
   VBO-Allokation/Upload (~1–9 ms/Event) und die 200 KiB Python-Allokationen
   pro Rebuild (tracemalloc: ~203 KiB/Rebuild beim Head).

### Mittelfristige Verbesserung

- **Dirty-Flag-/Versionierungs-Cache für Rendergeometrie:** Geometrie,
  Normalen und Triangle-Arrays nur neu berechnen, wenn Mesh-Positionen oder
  Topologie sich tatsächlich ändern; Rest wird nur neu dargestellt.
- **Selection-/Hover-Overlay von der Basismesh-Geometrie entkoppeln** (eigene,
  winzige VertexLists, die unabhängig von der Hauptgeometrie aktualisiert
  werden) — Hover-/Selektionswechsel kosten dann nicht mehr den vollen Rebuild.
- **Picking-Struktur:** Vertex-/Edge-/Face-Picking über eine einmal gebaute
  Screen-/Space-Struktur (Grid/BVH) oder zumindest über das Cachen der
  Projektionen pro Frame statt O(E)-Neuprojektion bei jedem Event.

### Langfristige Viewport-Architektur

- **View-Layer / Render-Proxy getrennt vom Core-Mesh:** Eine Render-Seite
  mit eigener, versionierter Darstellungsgeometrie, die über Benachrichtigung
  (Dirty-Events) statt über „Rebuild bei jedem Input-Event" aktualisiert wird.
  Damit werden Picking, GPU-Upload und Darstellung sauber vom Inputfluss
  entkoppelt.
- **Persistente GPU-Ressourcen** (einmalige Vertex-/Index-Buffer,
  position-update statt re-create) als Grundlage für spätere größere Meshes,
  Subdivision/Skinning-Anzeige und Deformationsketten (V1-Spec §9: „finale
  Position" kann dann ohne Rebuild über eine Deformation-Query bezogen werden).
- Erst nach dieser Analyse bewusst als Architekturentscheidung zu treffen —
  dieser Bericht **implementiert** noch nichts und soll die Entscheidung
  vorbereiten.

---

## 6. Beantwortete Fragen

1. **Warum laggt der Viewport bereits bei 324 Quads?** Jeder Kamera-/Hover-/
   Drag-Event stößt einen vollständigen Geometry-Rebuild an (inkl. O(V×F)-
   Normalen) plus Voll-Picking: ~45 ms Normalen + ~7 ms Picking + ~5–9 ms GL
   pro Event → ~65–100 ms/Frame (8–15 FPS), obwohl Geometrie und Topologie
   sich gar nicht ändern.

2. **Hauptursache?** Kombination (F), klar dominiert von **B (Geometry
   rebuild)**; Picking (A) ist sekundär; GPU-Upload (C) und Rendering (D)
   sind klein; Python-Allokationen (E) tragen zur Rebuild-Kosten bei, aber
   **GC selbst ist kein Hotspot** (~1 gen0-Collection je 20–25 Frames).

3. **324 → 1.3k → 5k → 20k Quads?** Rebuild-Zeit skaliert quadratisch
   (O(V×F) Normalen): 47 ms → 770 ms → 22,4 s → ≈315 s. Der Viewport wird
   ab ~1k Quads interaktiv unbrauchbar und bei 20k blockiert bereits ein
   einzelner Event für Minuten.

4. **Größter Hotspot?** `ModelerWindow._compute_normals()` (O(V×F)-Loop der
   Vertex-Normalen-Mittelung mit `face_vertices()`-Kopien), aufgerufen aus
   `_rebuild_geometry()` bei jedem Input-Event. Anteil: ~60–80 % der
   Frame-Zeit bei 324 Quads; ab 1k Quads >95 %.

5. **Kleinste sinnvolle Optimierung?** Quick Win 1 (Kamera-Drag ohne
   Rebuild) + Quick Win 3 (lineare Normalen via Adjazenz): beide ändern nur
   wenige Zeilen, keine Viewport-Architektur, und heben Orbit/Pan/Zoom von
   ~10 FPS auf Praxis-FPS bzw. den Rebuild von 47 ms auf wenige ms.

6. **Langfristig architektonisch sinnvoll?** Render-/View-Layer mit
   versionierter Geometrie, Dirty-Flags und persistenten GPU-Buffern,
   getrennt vom Core (Picking/Upload/Draw entkoppelt vom Input-Event-Fluss) —
   das ist die Grundlage für Mesh-Größen jenseits einiger tausend Quads.