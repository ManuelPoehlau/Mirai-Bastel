# GUI Stufe 1 — Zustandsanzeige (read-only HUD)

**Status:** IMPLEMENTED 2026-10-23 (Discovery, M5; Look, Texte und beide Layouts `PROVISIONAL`) ·
**Artist-Urteil A vs. B:** offen (siehe §4) · **Code:** `src/hud.py`, Verdrahtung `src/main.py`
(`install_handlers(..., hud=)`), Tests `tests/test_hud.py`, `tests/test_main_wiring.py`

## 1. Was gebaut ist

- Eine immer sichtbare, rein lesende Zustandsanzeige im Production-Fenster: Modus (1/2/3/4), aktuelles
  Tool (letztes W/E/R; eine laufende Interaktion als „… (running)“, auch Extrude, Loop Slide, Knife),
  Achsen-/Ebenen-Constraint, Symmetrie-Achse, Display-Modus (+ Wire), Soft Selection (an/aus, Radius,
  Kurve), SubD-Vorschau (Ansicht, Stufe, Linien versteckt) und die letzte Statusmeldung.
  „An“-Zustände sind farbig (gelb), Tastenhinweise blau.
- Zwei Layout-Varianten: **A `bar`** = Leiste unten (Segmente in einer Zeile, bei schmalem Fenster zwei,
  darunter die Statusmeldung); **B `corner`** = Panel oben links (eine Zeile pro Eintrag, Statusmeldung
  darunter). `H` schaltet **A → B → aus → A** (nur solange beide in Erprobung sind; nach dem Urteil wird
  `H` ein reines Ein/Aus).
- Die Konsolen-Ausgabe der Statusmeldung bleibt als Fallback (`main.run`).

## 2. Engineering-Entscheidungen (hier gesetzt)

- **Datenpfad nur lesend:** `hud_state(app)` liest öffentlichen `Application`-Zustand in ein
  unveränderliches `HudState` (keine Änderung an `Application`, kein Accessor nötig). Das HUD besitzt
  keinen App-Zustand und keinen App-Input; Tests prüfen, dass es nichts schreibt.
- **Neuaufbau nur bei Änderung:** `HudState` ist zugleich die Änderungs-Signatur (inkl. `status_serial`,
  damit eine wiederholte gleiche Meldung zählt). Labels werden nur neu gebaut, wenn sich Zustand,
  Fenstergröße oder Layout ändern; Orbit/Zoom ändern nichts davon. Gemessen (Xvfb, Software-GL, Kopf):
  `update()` ≈ 5 µs/Frame, Zeichnen des fertigen Batches ≈ 0,3 ms/Frame, 1 Rebuild über 300 Orbit-Frames.
- **Tastenhinweise aus dem Binding-Layer:** `BindingSet.inputs_for(command, context)` (neu,
  Rückwärts-Auflösung nach denselben Regeln wie `command_for`); kein Hinweis ist hart kodiert, eine
  `keymap.json`-Umbelegung erscheint im HUD.
- **`H`** = Input Truth `application.toggle_hud`, gebunden als Command `ToggleHud` im neuen Kontext
  `window` (`WINDOW_CONTEXT`): Den löst `Application` nie auf, also ist `H` kein App-Command und kein
  Host-`CommandGate` (Symmetry Lab, BLOCK) lehnt es ab. Das Fenster fragt
  `command_for(input, WINDOW_CONTEXT)` (`main.is_hud_key`).
- **pyglet-eigene Primitive** (Labels, Rechtecke, ein Batch), keine neue Abhängigkeit; pyglet wird lazy
  importiert (Muster `scene_menu.py`), der Zustand ist headless testbar.

## 3. Forward-Compat: wo Stufe 2 andocken würde (nur die Nähte, kein Design)

- **Klick-Ziele:** Jede HUD-Zeile ist schon an ihre Commands gebunden (`_HINT_COMMANDS` in `hud.py`), und
  die Layouts kennen ihre Rechtecke. Ein Klick könnte also denselben benannten Command auslösen wie die
  Taste (INPUT_COMMAND_TOOL_CONTRACT: ein Button ist nur ein weiterer Auslöser).
- **Wer den Klick bekommt (AD-013 H2 / AD-019):** Heute entscheidet `Application.pointer_press` →
  `PointerGestures` Klick vs. Drag. Ein HUD-Treffer müsste davor im Fenster abgefangen werden (wie die
  modalen Menüs, aber nicht modal: Treffer = HUD, daneben = App). Offen ist, ob das eine Fenster-Ebene
  bleibt (Variante G wie SPACE/Shift+A) oder ein eigener Owner in `interaction_owner` wird.
- **Gates:** `key_press` schützt viele Commands (W/E/R/T scharf, Drag-Select, Objektmodus);
  `dispatch_command` hat diese Gates nicht alle. Ein Klickpfad braucht einen öffentlichen Einstieg
  „Command aus der UI auslösen, mit denselben Gates wie die Taste“ — das wäre die erste
  `Application`-Änderung von Stufe 2.
- **Drags (Slider):** `cursor_wrap_active` ist schon als wiederverwendbares Gate für Slider-Drags
  vorgesehen; `pointer.active` / `interaction_owner` sagen, wann die UI nichts annehmen darf.
- **Toolkit:** Bleibt offen bis zum Stufe-2-Gate. `HudState`/`hud_rows` sind toolkit-frei; nur
  `_Builder`/`_layout_*` sind pyglet und wären auszutauschen.

## 4. Artist-Urteil (Manu) — A (`bar`) vs. B (`corner`)

_Offen. Nach dem Praxistest hier eintragen: welche Variante, was fehlt, was stört (Datum, Wortlaut)._

## 5. Offene Fragen für Stufe 2

1. Welche Variante bleibt (oder beide, umschaltbar)? Danach wird `H` reines Ein/Aus.
2. Welche Einträge fehlen (Auswahl-Anzahl, Edit-Objekt/Objektmodus, Licht-Preset, Soft-Metrik/Flow)?
3. Sollen „An“-Zustände anklickbar werden (Toggle per Klick) — und welche zuerst?
4. Klick-Ownership: Fenster-Ebene (wie die Menüs) oder eigener `interaction_owner` (AD-013 / AD-019)?
5. Braucht die Statuszeile Verlauf, Ausblenden nach Zeit oder Hervorhebung von Ablehnungen?
6. Kontext-Hinweiszeile (Wings-Stil) als eigene Zeile oder in der Bar?
7. Toolkit-Gate: bleiben pyglet-Labels, oder Panels/Slider/Kurveneditor mit ImGui/Qt (REFERENCE_HARDWARE: GL 3.3)?
8. Schriftgröße / HiDPI auf dem alten PC lesbar?

## 6. Testschritte für Manu (Praxistest)

Start: `python src/main.py` (Kopf) — das HUD ist sofort unten als Leiste sichtbar.

1. **Sichtbar / `H`:** Beim Start ist die Leiste unten da. `H` → Panel oben links (Variante B). `H` → HUD
   aus. `H` → wieder Leiste unten. (Ein/Aus = zweimal bzw. einmal `H`, solange beide Varianten im Test sind.)
2. **Modus, Tool, Constraint:** `1`/`2`/`3`/`4` drücken → „Mode“ zeigt Vertex/Edge/Face/Object sofort.
   `W`, `E`, `R` kurz tippen → „Tool“ zeigt Move/Rotate/Scale. Etwas auswählen und `W` halten → „Move
   (running)“ in Gelb, loslassen → wieder normal. `X`/`Y`/`Z` → „Axis X“ usw. in Gelb, gleiche Taste
   nochmal → „free“; `Shift+X` → „YZ plane“.
3. **Symmetrie, Display, Soft, SubD:** `Shift+S` mehrmals → „Sym“ X → Y → Z → off. `D` → Shaded / Flat
   Shaded / Wireframe, `Shift+D` → „+ Wire“. `O` → „Soft on · 15 % · smooth“, `Shift+Mausrad` ändert die
   Prozent, `Shift+O` die Kurve. `V` → „SubD cage · L2“, nochmal `V` → „isolines“, `Ctrl+1/2/3` → L1/L2/L3;
   in der SubD-Ansicht `Shift+D` → „lines hidden“.
4. **Meldungen im Fenster:** Ohne Auswahl im Face-Modus `T` drücken oder in Modus `4` `C` drücken → die
   Ablehnung steht unten (Leiste) bzw. unter dem Panel — nicht nur in der Konsole. `Ctrl+Z` zweimal →
   auch eine wiederholte gleiche Meldung erscheint.
5. **Varianten vergleichen:** Eine Weile mit Leiste (A) und eine Weile mit Panel (B) arbeiten. Welche fühlt
   sich besser an? Was fehlt? Was stört (verdeckt Mesh, zu klein, zu bunt, zu viel)? → §4 / Chat.
6. **Tempo:** Orbit (Alt+LMB ziehen) und Zoom (Mausrad) mit HUD an und aus vergleichen — fühlt es sich auf
   dem alten PC langsamer an als vorher?
