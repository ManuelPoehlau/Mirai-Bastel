# AD-030 — GUI-Framework für Panels: Dear ImGui (imgui-bundle) auf pyglet

**Status:** PROPOSED (2026-11-07) — Empfehlung **Ja, mit Bedingungen** (§6). Entscheidung liegt bei Manu (§7). Es gibt
keinen Code in `src/`; der Spike liegt in [`experiments/gui_framework_spike/`](../../experiments/gui_framework_spike/README.md)
(Branch `claude/gui-framework-spike`). Auftrag: [GUI_FRAMEWORK_SPIKE_BRIEF](../design/GUI_FRAMEWORK_SPIKE_BRIEF.md).
**Builds on:** [AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) §6.8 (Outliner-Daten und -Commands, unverändert), AD-013 Addendum
2026-10-28 (BindingSet = Eingabe-Wahrheit), [GUI_Bestandsaufnahme](../design/GUI_Bestandsaufnahme.md). Kein `src/core/`-Eingriff.

## Kurzfassung für Manu (Deutsch)

- **Ergebnis:** Dear ImGui trägt. Der Outliner läuft im echten Production-Fenster (Liste mit Gruppen-Einrückung, Klick
  wählt mit Shift/Ctrl/Alt wie im Viewport, Auge blendet über `HideObjects` aus). `src/` blieb unverändert.
- **Alle drei Muss-Kriterien bestanden:** Eingabe-Hoheit (Orbit, Pick, Lasso, W/E/R-Geste, Cursor-Wrap unverändert, 18 Tests),
  GL-Stabilität (keine Zustandslecks in beide Richtungen, gleicher Kontext), Installierbarkeit (Wheels Windows/Linux/macOS).
- **Kosten:** unter xvfb/llvmpipe nicht messbar über dem Rauschen (imgui selbst ca. 0,5 ms CPU je Frame), +26 MB Speicher,
  Start gleich. Die Messung auf deinem PC mit echter GPU steht aus (ein Befehl, §3.3).
- **Bedingungen (§6):** imgui-bundle braucht **Python ≥ 3.10**, das Projekt sagt „3.9+“; auf macOS nur Apple Silicon mit
  macOS 14+ (Intel-Mac nur bis imgui-bundle 1.92.5); ein Einzel-Einblenden-Command und ein öffentlicher
  „Objekt-Auswahl setzen“-Aufruf fehlen (kleine Core-/Application-Änderungen, nur mit deiner Freigabe); eine Taste für
  das Panel gibt es nicht ohne dich.
- **Deine Fragen (§5):** Screenshot [`screenshot_outliner.png`](../../experiments/gui_framework_spike/screenshot_outliner.png)
  im echten Fenster; Optik an die HUD angelehnt (gleiche Hintergrund-/Textfarben). Du entscheidest Optik, Schrift, HiDPI.

## 1. Was gebaut wurde (Spike)

`run.py` komponiert `src/main.py` (`create_window`, `install_handlers`, Szene) und hängt `ImguiLayer` an dasselbe Fenster;
`main.py` ist nicht angefasst. Das Panel liest `Scene`/`Selection` und schickt Commands, es hält nur Ansichtszustand
(eingeklappte Gruppen, Filtertext). Aufteilung nach Brief Punkt 7:

| Teil | Datei | Test |
|---|---|---|
| Zeilen, Einrückung, Klick-Tabelle, Auge-Plan | `outliner_model.py` (rein, ohne pyglet/imgui) | headless |
| Wer bekommt welches Ereignis | `input_gate.py` (rein) | headless |
| Zeichnen, Event-Weitergabe, GL-Sicherung | `imgui_layer.py` (imgui/pyglet lazy) | xvfb |

Rendering: der C++-OpenGL3-Renderer von imgui-bundle auf pyglets Kontext (`opengl3_init("#version 330")`); die Tasten-/Maus-
Weitergabe ist eigener Code (~80 Zeilen). Das mitgelieferte `python_backends/pyglet_backend` taugt nicht: es importiert
PyOpenGL (extra Abhängigkeit), hängt Handler ohne `EVENT_HANDLED`-Rückgabe an und stellt GL-Zustand nur teilweise her.

## 2. Eingabe-Hoheit (Muss 1): bestanden

Regel (`InputGate`): ImGui bekommt die Maus nur über dem Panel-Rechteck des letzten Frames, ein Drag gehört dem Besitzer des
Press (im Viewport begonnen: bleibt bei `Application`, auch über dem Panel; im Panel begonnen: erreicht `Application` nie),
Tasten nur bei aktivem Textfeld (`want_text_input`). Alles andere läuft unverändert durch `install_handlers` in das BindingSet.

| Testfall (Brief) | Ergebnis |
|---|---|
| Klick im Panel wählt kein Viewport-Objekt (`pointer_press/release` kommen nicht an) | ✓ |
| Klick/Drag außerhalb, Alt-Orbit über das Panel hinweg: unverändert bei `Application` | ✓ |
| Taste im Textfeld (`H`, `Ctrl+H`) löst keinen Command aus; Filtertext bekommt sie | ✓ |
| Release einer vor dem Textfeld gedrückten Taste (W) geht durch (kein „hängendes“ W) | ✓ |
| Hover-Pick unter dem Panel unterdrückt (`pointer_leave`), Scroll über dem Panel scrollt die Liste | ✓ |
| W/E/R-Geste folgt der Maus auch über dem Panel; Cursor-Wrap läuft im unveränderten Handler | ✓ (Geste hat Vorrang) |

Gefunden und behoben: ohne den Gesten-Vorrang schluckte das Panel die Bewegung bei gehaltenem W/E/R (Test
`test_move_gesture_follows_the_mouse_over_the_panel`). Tasten: der Layer belegt **keine**; das Umschalten geht über einen
Knopf. Nicht geprüft: IME/Dead Keys, Gamepad, Touch.

## 3. Messwerte

Umgebung: Cloud-Container, Linux, xvfb, Mesa llvmpipe (Software-GL, GL 4.5), Python 3.13, imgui-bundle 1.93.0, pyglet 2.1.19.
Die Absolutwerte gelten **nicht** für den Referenz-PC; aussagekräftig sind die Abstände.

### 3.1 GL (Muss 2): bestanden

Gleicher Kontext (pyglets), keine zweite Fensterbibliothek. `#version 330` läuft unter dem Production-Kontext (4.5 Core-fähig).

| Prüfung | Ergebnis |
|---|---|
| Layer → Production: GL-Zustand (Depth, Blend, Cull, Scissor, Blend-Func, Programm, VAO, Array-Buffer, aktive Textur, Viewport, Depth-Maske, Polygon-Modus) nach `draw()` | unverändert, auch ohne eigene Sicherung (imgui sichert selbst); der Layer sichert trotzdem zusätzlich (`guard_gl`) |
| Production → Layer: Zeichnen mit absichtlich verdrecktem Zustand (Depth an, Cull an, Linienmodus, Scissor 3×3, Depth-Maske aus, Blend aus) | Pixel identisch (0 Bytes Unterschied) |
| ohne GL / ohne Display | Imports lazy; die Panel-Logik-Tests laufen ohne imgui/pyglet; die Fenstertests werden übersprungen. `tests/test_object_outliner.py`, `tests/test_main_wiring.py` unverändert grün |
| `xvfb-run` | läuft |

Nicht geprüft: echte GPU-Treiber (NVIDIA/AMD/Intel, Windows), macOS-Core-Profile (Mesa-Test ≠ Treiber-Test).

### 3.2 Kosten (Kriterium 3), `gollum_20k.obj` + 4 Demo-Objekte, 120 Frames je Fall, Median / p95 ms

| Variante | Idle | Orbit | Start | maxRSS | imgui-CPU je Frame |
|---|---|---|---|---|---|
| ohne imgui | 18,2 / 20,5 | 17,8 / 21,2 | 1,10 s | 268 MB | – |
| imgui, Panel offen | 18,3 / 21,4 | 17,7 / 21,1 | 1,10 s | 294 MB | 0,48 / 0,63 |
| imgui, Panel zu (nur Knopf) | 17,2 / 19,5 | 17,3 / 20,7 | 0,99 s | 294 MB | 0,24 / 0,31 |

Der Unterschied liegt unter dem Rauschen der Software-GL. Zusatz: +26 MB Speicher, Import `imgui_bundle` im Start ohne messbaren
Unterschied. (Ein früherer Lauf zeigte +7 ms; Ursache war die ungleiche Szene — Demo-Objekte nur in der imgui-Variante —, nicht imgui.)

### 3.3 Auf dem Referenz-PC wiederholen
`python experiments/gui_framework_spike/bench.py gollum_20k.obj --variant plain|open|closed` (ohne xvfb), je ein Prozess.

### 3.4 Abhängigkeit (Muss 4): bestanden, mit Bedingungen

| Punkt | Befund |
|---|---|
| Wheels | Windows amd64/arm64, Linux x86_64/aarch64 (manylinux_2_28, musllinux), macOS arm64 (macOS 14+). `pip install` hier ohne Compiler (14,4 MB Wheel, 46 MB installiert) |
| **Python** | **≥ 3.10** (alle Releases ab 1.5.x). Das Projekt sagt „Python 3.9+“ → Mindestversion anheben (3.9 ist EOL) oder Nein |
| **macOS Intel** | nur bis 1.92.5 (`macosx_14_0_x86_64`); 1.92.9+/1.93.0 nur arm64 |
| Lizenz | MIT (imgui-bundle; Dear ImGui MIT). ImGui Test Engine hat eine eigene Lizenz, wird nicht gebraucht |
| Pflege | 31 Releases, letzter 2026-10-21 (1.93.0), davor 2026-08-14, 2026-05-13: aktiv |
| Pinning | genau `imgui-bundle==1.93.0` (neue Versionen ändern die API, 1.92 hat dynamische Fonts); bisher nur in `experiments/gui_framework_spike/requirements.txt`, nicht in `requirements-dev.txt` |

## 4. Befunde an Core / Application (nichts geändert, Brief: Outliner-Commands bleiben)

1. **Einzel-Einblenden fehlt.** `HideObjects` wirkt auf die Auswahl (Auge: erst genau dieses Objekt wählen, dann Command);
   zum Einblenden gibt es nur `ShowAllObjects`, und ein verstecktes Objekt verlässt die Auswahl. Der Spike zeigt dafür *alle*
   Objekte und sagt es in der Panelzeile. Für ein richtiges Auge braucht es einen `ShowObjects`-Command mit Objekt-Argument
   (oder `SetObjectHidden(id, bool)`): kleine Änderung in `ObjectController`, Freigabe nötig.
2. **Kein öffentliches „Objekt-Auswahl setzen“.** Das Panel schreibt `app.selection.objects` (wie die Tests; das Highlight
   zieht `update_viewport` pro Frame nach). Besser: `Application.select_objects(ids)` ohne Pick, mit Gesten-Schutz wie in
   `ObjectController.select_at`. Eine Hide-Aktion über das Auge ändert die Auswahl (Undo stellt `{Objekt}` wieder her).
3. **`install_handlers` hat keinen Overlay-Haken.** `@window.event on_draw` liegt im pyglet-Handler-Stack; der Layer holt ihn
   über das interne `window._event_stack` und umhüllt ihn. Für eine Übernahme gehört ein `overlays=`-Parameter nach `install_handlers`.
4. **pyglet-Falle für Tests:** außerhalb von `pyglet.app.run()` reiht `window.dispatch_event` in eine Queue; ohne
   `dispatch_pending_events()` läuft `on_draw` nie (`run.render_frame`).

## 5. Vergleich und Schätzungen (nicht gebaut)

| Option | Aufwand / Befund |
|---|---|
| **ImGui** | Spike steht: ~500 Zeilen Layer+Gate+Modell+Run (ohne Bench und Tests). Liste, Scroll, Baum, Textfeld, Rechtsklick-Popup sind fertig im Framework (Textfeld und Popup im Spike geprüft). Drag-and-Drop (`begin_drag_drop_source/target`) ist vorhanden, nicht gebaut. |
| Qt/PySide6 | nicht gebaut. Eigener Event-Loop neben pyglet oder pyglet in Qt einbetten: Fenster, Kontext, Eingabe und `Application`-Verdrahtung wären neu. Zusätzlich ~200 MB Abhängigkeit (Schätzung). Zu groß für den Nutzen. |
| Weiter selbst bauen | Schätzung (nicht gebaut), je Baustein auf `hud.py`/`scene_menu.py`: Scroll-Liste mit Clipping ~1–2 Tage, Texteingabe (Cursor, Auswahl, Clipboard, IME, Umlaute) ~3–5 Tage und bleibt lückenhaft, Drag-and-Drop mit Drop-Zielen ~2 Tage, Baum mit Ein-/Ausklappen ~1 Tag; jedes weitere Panel (Look, Regions, Rig) wiederholt das. |

## 6. Entscheidung (Empfehlung): Ja, mit Bedingungen

1. **Python ≥ 3.10** als Mindestversion (CLAUDE.md, `requirements`), oder die Entscheidung kippt auf „nein“.
2. **macOS:** Zielplattform ist Apple Silicon, macOS ≥ 14; Intel-Mac nur mit imgui-bundle ≤ 1.92.5. (Referenz-PC ist
   nach bisherigem Stand Windows; bitte bestätigen.)
3. **Pinning** exakt, Hochziehen nur mit Lauf von `tests` des Spikes/`bench.py`.
4. **Core/Application-Änderungen (§4.1, §4.2, §4.3)** vor der Übernahme, jeweils mit deiner Freigabe.
5. **Keine Taste ohne Manu:** Umschalten des Outliners bekommt eine Taste erst nach deiner Freigabe (`config/keymap.json`);
   bis dahin der Knopf.
6. **Artist-Abnahme** von Optik, Schrift (Latin-1/Umlaute ok, CJK nicht ohne Glyph-Bereich), Skalierung/HiDPI (`font_scale_dpi`
   gesetzt, auf echter HiDPI-Hardware ungeprüft) und Farben nach dem Screenshot.
7. **Messung** auf dem Referenz-PC (§3.3) vor der Übernahme; die hier gemessenen Zahlen kommen aus Software-GL.

## 7. Migrationsplan (nur einordnen, nichts umgesetzt)

| Phase | Inhalt | Bleibt / zieht um |
|---|---|---|
| 0 | Manu entscheidet (Bedingungen §6) | – |
| 1 | `src/gui/`: Layer, Gate, Outliner aus dem Spike (Modell bleibt rein); `install_handlers(..., overlays=...)`; `ShowObjects`, `select_objects`; Requirements | `hud.py`, `scene_menu.py` unverändert |
| 2 | Look-/Regions-/Rig-Panels auf demselben Layer; Namen per Textfeld statt `SET_NAMES`; Drag-Umsortieren, Rechtsklick (Duplizieren) | HUD-Streifen bleibt pyglet (read-only, keine Eingabe) |
| 3 | SPACE-Menü (Szene laden, Speichern, OBJ, ZBrush) → ImGui-Menü/Popup; Add-/Mirror-Menüs ebenso | `scene_menu`-Logik (`scene_entries`, `run_mirror_entry`) bleibt, nur das Zeichnen zieht um |
| – | **Bleibt selbstgebaut:** Rubber-Band/Lasso, Gizmo, Triad, Bone-Tag, Statuszeile (Viewport-Zeichnung, kein Panel); die HUD-Strip-Zeilen solange sie read-only sind |

## 8. Offene Punkte (nicht geprüft)

Windows/macOS-Lauf, echte GPU, HiDPI, Python 3.9 (nicht installierbar), IME, Drag-and-Drop, mehrere Fenster pro Prozess
(`ImguiLayer.close()` ist nötig, imgui-Backend ist prozessglobal).
