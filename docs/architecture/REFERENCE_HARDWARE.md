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

- Die tatsächlichen Strings `GL_VERSION` / `GL_RENDERER` des laufenden Fensters.
- Ob Treiber und GPU `gl_PrimitiveID` und Fragment-Ableitungen (`dFdx`/`dFdy`) zuverlässig liefern. Beides gehört zu OpenGL 3.3, das Treiberverhalten ist aber offen (siehe `docs/research/viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md` §6).
- Reale Frame- und Hover-Zeiten in den echten Fenstern (`src/main.py`, Playground) auf diesem PC.

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
