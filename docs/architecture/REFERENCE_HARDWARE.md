# Referenz-Hardware — Entwicklungs- und Test-PC

**Status:** Faktenblatt (keine Architekturentscheidung)
**Datum:** 2026-09-30
**Quelle:** Angaben des Artists aus der Windows-Systeminfo. Alles unter „Abgeleitet“ ist Einschätzung, solange nichts gemessen ist.
**Single Source of Truth:** Das ist der einzige Ort, an dem der Test-PC beschrieben wird. Andere Dokumente verlinken hierher. Bei einem Hardwarewechsel wird nur diese Datei geändert (siehe Abschnitt 5).

---

## 1. Das System

| Bereich | Angabe |
|---|---|
| Prozessor | Intel Core 2 Quad Q9550, 2,83 GHz (4 Kerne) |
| Arbeitsspeicher | 8 GB |
| Grafikkarte | NVIDIA GeForce 9800 GTX / 9800 GTX+ (Windows zeigt 481 MB Grafikspeicher) |
| Massenspeicher | SSD Samsung 840 EVO 120 GB (System), HDD 2 TB, HDD 640 GB |
| Betriebssystem | Windows 10, 64-Bit |
| Eingabe | Maus und Tastatur. Keine Stift- oder Toucheingabe verfügbar. |

**Einordnung (Angabe des Artists, 2026-09-30):** Das ist derzeit der **einzige** PC, auf dem getestet wird. Eine Aufrüstung ist geplant, das Modell ist offen. Der neue PC wird in jedem Fall schneller sein als dieser.

Bewusst **nicht** aufgenommen: Gerätename, Geräte-ID und Produkt-ID. Das Repository ist öffentlich, und diese Angaben helfen keiner technischen Entscheidung.

---

## 2. Abgeleitet — Einschätzung, nicht gemessen

**Belegt im Code:** Alle Shader des Projekts verlangen `#version 330 core` (`src/viewport/gl_render_store.py`, `gl_point_overlay.py`, `gl_line_overlay.py`; ebenso `playground/window.py`).

**Einschätzung (soweit bekannt):**

- **Grafik:** Die GeForce 9800 GTX (Baujahr 2008) unterstützt höchstens OpenGL 3.3. Das Projekt sitzt damit genau an der Obergrenze dieses PCs. Alles, was OpenGL 4.x braucht (Compute Shader, Tessellation u. Ä.), ist auf diesem PC nicht testbar. Der Treiber ist vermutlich ein älterer „Legacy“-Zweig.
- **Prozessor:** Der Core 2 Quad Q9550 (Baujahr 2008) hat kein Hyper-Threading und vermutlich SSE4.1, aber weder SSE4.2 noch AVX. Die Leistung pro Kern liegt deutlich unter aktuellen Prozessoren. Vorkompilierte Bibliotheken könnten bei Versionssprüngen neuere CPU-Befehlssätze voraussetzen. Das ist bei Upgrades zu prüfen.
- **Speicher:** Der Referenzkopf (326 Vertices) ist unkritisch. Zuerst an Grenzen stoßen dürften hochauflösende Meshes und große Zusatz-Puffer (Shadow Maps, Extra-Pässe) im knappen Grafikspeicher.
- **Eingabe:** Ohne Stift oder Touch sind druckempfindliche oder gestenbasierte Bedienideen auf diesem PC nicht prüfbar.

**Offen — nur durch Messung zu klären:**

- ~~Die tatsächlichen Strings `GL_VERSION` / `GL_RENDERER` des laufenden Fensters.~~ Gemessen 2026-10-11 (unten): `3.3.0` /
  `GeForce 9800 GTX/9800 GTX+/PCIe/SSE2`.
- Ob Treiber und GPU `gl_PrimitiveID` und Fragment-Ableitungen (`dFdx`/`dFdy`) zuverlässig liefern. Beides gehört zu OpenGL 3.3, das Treiberverhalten ist aber offen (siehe `docs/research/viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md` §6).
- Reale Frame- und Hover-Zeiten in den echten Fenstern (`src/main.py`, Playground) auf diesem PC.
  Messsonde für die Drag-Kosten im GL-Pfad (hidden pyglet-Fenster, gibt auch `GL_VERSION` / `GL_RENDERER` aus):
  `python experiments/drag_cost/probe_drag_gl.py`, Doku und Container-Vorher/Nachher in
  [`experiments/drag_cost/README.md`](../../experiments/drag_cost/README.md) (WP-VIEW-PATCH-01).
  Werte vom Referenz-PC stehen hier erst nach Manus Lauf.
  Navigation, Hover und Klick auf einem hochaufgelösten Mesh (`gollum.obj`, 21 875 V; WP-VIEW-PERF-01):
  `python experiments/drag_cost/probe_navigation_gl.py` — Methode, Container-Zahlen, Hypothesen und Fix-Optionen in
  [`experiments/drag_cost/README.md`](../../experiments/drag_cost/README.md) „Navigation and picking“. Gibt auch die
  GPU-Zeit des Draws (`gpu`, GL-Timer-Query) aus. Werte vom Referenz-PC: unten und im README.

**Gemessen auf dem Referenz-PC (Manu, 2026-10-11)** — Core 2 Quad Q9550, GeForce 9800 GTX, Python 3.14.2,
`python experiments/drag_cost/probe_drag_gl.py` (`plain_w` und `soft_w`, Soft Selection S2b, `main` @ S2b); die ganze
Tabelle steht in [`experiments/drag_cost/README.md`](../../experiments/drag_cost/README.md):

- Alle `move`-Zeilen (Move-Schritt + `Viewport.sync()` pro Mausbewegung) liegen mit p95 ≤ 8 ms unter der 8-ms-Schwelle von AD-020 §7.
  Schlechteste Soft-Zeile: Body, Radius 15 %, euclidean, p95 **7,73 ms**.
- Normales W (ohne Soft), Body, 112 Vertices: p50 **5,29 ms** / p95 **5,77 ms**.
- Einmal pro Geste (nicht in der Schwelle): Commit-Frame Body ~30 ms, Kopf ~11–15 ms; Auswahlklick Body ~13 ms p50
  (vom Picking dominiert, die Soft-Vorschau darin 0,35–1,9 ms).
- Einzelne Maxima bis ~280 ms liegen außerhalb des p95 (nicht untersucht).
- Subjektiv (Manu): „man_with_shoes läuft sehr flüssig.“ Tests mit höher aufgelösten Meshes folgen.

Damit ist die Zeile „Reale Frame- und Hover-Zeiten in den echten Fenstern“ für den Drag-Pfad beantwortet (Hover-Zeiten
außerhalb eines Drags nicht). Die Strings `GL_VERSION` / `GL_RENDERER` kamen nicht mit der Rückmeldung ins Repository und
bleiben unter „Offen“.

**Gemessen auf dem Referenz-PC (Manu, 2026-10-11), Navigation** — Windows 10 (19045), Python 3.14.2, `GL_VERSION` **3.3.0**,
`GL_RENDERER` **GeForce 9800 GTX/9800 GTX+/PCIe/SSE2**; `python experiments/drag_cost/probe_navigation_gl.py` (WP-VIEW-PERF-01),
ganze Tabelle, Hypothesen und Fix-Optionen in [`experiments/drag_cost/README.md`](../../experiments/drag_cost/README.md)
„Navigation and picking“:

- Orbit/Pan sind auch auf `gollum.obj` (21 875 V, 43 750 Dreiecke) flüssig: **1,2 ms** pro Schritt, GPU-Zeit des Draws
  **0,56 ms** (mit Wire 1,15 ms). Der Draw ist auf diesem PC nicht der Engpass.
- Teuer ist das Picking (Hover, Klick, Zoom): gollum Hover **~250 ms** p50 (p95 1,5 s), Klick ~570 ms, erster Hover nach
  einer Kamerabewegung ~740 ms, Zoom-Raste **~1,7 s**. Body: Zoom 22 ms, erster Hover 26 ms (knapp über einem Frame);
  Kopf: alles unter einem Frame.
- Befund nur auf diesem PC: `math.hypot` kostet hier ~7,5 µs pro Aufruf (Container ~0,1 µs), vermutlich weil der Core 2
  kein FMA hat (Lesart, nicht geprüft). Faustregel Referenz-PC / Container für den übrigen Python-Code: ~2x.

Damit sind auch die Hover-Zeiten außerhalb eines Drags gemessen (Produktionspfad `src/main.py`; Playground nicht).

**Vor der Aufrüstung sichern (Empfehlung, Agent):** Die drei Punkte oben einmal auf diesem PC messen und hier eintragen. Nach dem Wechsel sind diese Werte nicht mehr reproduzierbar, und sie sind die einzige Worst-Case-Baseline, die das Projekt hat.

---

## 3. Verhältnis zu vorhandenen Aussagen

- `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` nennt als „Target Platform“ einen Intel i5 der 4. Generation mit 4 GB RAM und als Ziel 30+ FPS auf einem 7 Jahre alten PC. Dieser Test-PC ist älter und beim Prozessor deutlich schwächer als das dort genannte Ziel.
- `experiments/viewport_draw_binding_spike/README.md` vermerkt, dass damals keine repräsentative Hardware verfügbar war. Der PC hier ist die Messbasis für solche Aussagen.
- **Dieses Dokument ändert die Zielplattform nicht.** Ob dieser PC die Untergrenze des Produkts sein soll oder nur das Testgerät ist, entscheidet der Artist (Priorität/Intent).

---

## 4. Regeln für Agenten

- Leistungs- und Render-Aussagen kennzeichnen: gemessen **auf dem Referenz-PC** oder anderswo (z. B. headless unter Xvfb). Headless-Zahlen ersetzen keine Messung hier.
- Ein Feature, das OpenGL über 3.3, Mehrkern-Parallelisierung oder neuere CPU-Befehlssätze braucht, wird als Konflikt mit dem Referenz-PC gemeldet und nicht still eingebaut.
- Nichts hier als gemessen darstellen, was in Abschnitt 2 unter „Einschätzung“ oder „Offen“ steht.

---

## 5. Hardwarewechsel

Bei einer Aufrüstung: die neuen Daten in Abschnitt 1 eintragen und die Werte dieses PCs als Abschnitt „Frühere Referenz (Core 2 Quad Q9550, GeForce 9800 GTX)“ mit Datum **behalten**, samt den Messwerten aus Abschnitt 2. Nur so bleiben spätere Messungen mit dem Worst-Case-Stand vergleichbar. Die offene Frage aus Abschnitt 3 (Untergrenze oder Testgerät) wird dann neu gestellt.
