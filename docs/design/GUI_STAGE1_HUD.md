# GUI Stufe 1 — Zustandsanzeige (read-only HUD)

**Status:** IMPLEMENTED 2026-10-23 (Discovery, M5; Look, Texte und beide Layouts `PROVISIONAL`) ·
**Stufe 1b (Phase A1: Statusleiste, Knochenname, XYZ-Achsenkreuz):** IMPLEMENTED 2026-11-03, Praxistest offen (§7) ·
**Stufe 1c (Phase A3: dauerhafte Gewichtsansicht, `9`):** IMPLEMENTED 2026-11-03, Praxistest offen (§8) ·
**Artist-Urteil A vs. B:** durch §7 abgelöst, offen (siehe §4) · **Code:** `src/hud.py`, Verdrahtung `src/main.py`
(`install_handlers(..., hud=, triad=, bone_tag=)`), Tests `tests/test_hud.py`, `tests/test_hud_strip.py`,
`tests/test_gl_hud_marks.py`, `tests/test_main_wiring.py`

**Aktuelle Bestandsaufnahme (2026-11-03):** [GUI_Bestandsaufnahme.md](GUI_Bestandsaufnahme.md) erfasst den heutigen HUD-/Viewport-Bestand sowie die zusätzlichen Morph- und Rig-Zustände. Sie ist ein nicht-normativer Arbeitsstand mit `[V]`/`[H]`/`[O]`, keine neue GUI-Spezifikation.

## 1. Was gebaut ist

- Eine immer sichtbare, rein lesende Zustandsanzeige im Production-Fenster: Modus (1/2/3/4), aktuelles
  Tool (letztes W/E/R; eine laufende Interaktion als „… (running)“, auch Extrude, Loop Slide, Knife),
  Achsen-/Ebenen-Constraint, Symmetrie-Achse, Display-Modus (+ Wire), Soft Selection (an/aus, Radius,
  Kurve), SubD-Vorschau (Ansicht, Stufe, Linien versteckt) und die letzte Statusmeldung.
  „An“-Zustände sind farbig (gelb), Tastenhinweise blau. Später kamen die bedingten Zeilen „Morph“, „Targets“ und
  „Rig“ hinzu; Pose-Modus und Bind-Status waren damit noch nicht als eigener, klar priorisierter Zustand dargestellt
  (**seit Stufe 1b gelöst, §7**).
- Zwei Layout-Varianten: **A `bar`** = Leiste unten (Segmente in einer Zeile, bei schmalem Fenster zwei,
  darunter die Statusmeldung); **B `corner`** = Panel oben links (eine Zeile pro Eintrag, Statusmeldung
  darunter). `H` schaltete **A → B → aus → A**. *(Seit Stufe 1b ersetzt: das Eck-Panel B ist entfallen, es gibt die
  Leiste oben/unten, kompakt/voll, und `H` ist ein reines Ein/Aus — §7.)*
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
- **Gates:** Der öffentliche Einstieg `Application.dispatch_command(...)` ist inzwischen bereits gegatet: Er prüft
  `can_run(command, RunContext("api"))` und leitet erst danach an den Handler weiter. Interne App-Aufrufe nutzen
  `_execute(...)` nach ihrem jeweiligen Gate. Für eine UI-Schaltfläche kann `can_run(command, RunContext("ui", operands=False))`
  die Verfügbarkeit bestimmen (dieser read-only Status steckt in `HudState.unavailable`; seit Stufe 1b dimmt die Leiste die Tastenhinweise
  dieser Befehle, §7); ausgelöst wird anschließend über `dispatch_command(...)`. Der Fenstercode besitzt aktuell weiterhin keinen
  Panel-Hit-Test oder klickbaren GUI-Pfad.
- **Drags (Slider):** AD-027 sieht eine `SliderDrag`-Session mit Esc-Restore vor; `cursor_wrap_active` ist als
  wiederverwendbare Grundlage vorgesehen. Das ist eine Architektur-Naht, noch kein implementierter Morph-Slider.
  Press, Drag und Release müssen zusammen beim Empfänger bleiben. Die offene Ownership-Frage steht in AD-027 §3.5.
- **Toolkit:** Bleibt offen bis zum Stufe-2-Gate. `HudState`/`hud_rows` sind toolkit-frei; nur
  `_Builder`/`_layout_*` sind pyglet und wären auszutauschen.

## 4. Artist-Urteil (Manu) — A (`bar`) vs. B (`corner`)

_Offen. Nach dem Praxistest hier eintragen: welche Variante, was fehlt, was stört (Datum, Wortlaut)._

Seit Stufe 1b (§7) wird nicht mehr Leiste gegen Eck-Panel verglichen, sondern die neue Leiste **oben gegen unten** und
**kompakt gegen voll** (E4 der Bestandsaufnahme). Dein Urteil dazu, hier eingetragen, schließt auch diesen A/B-Punkt.

## 5. Offene Fragen für Stufe 2

1. Welche Variante bleibt (oder beide, umschaltbar)? Danach wird `H` reines Ein/Aus.
2. Welche Einträge fehlen (Auswahl-Anzahl, Edit-Objekt/Objektmodus, Licht-Preset, Soft-Metrik/Flow)?
3. Sollen „An“-Zustände anklickbar werden (Toggle per Klick) — und welche zuerst?
4. Klick-Ownership: Fenster-Ebene (wie die Menüs) oder eigener `interaction_owner` (AD-013 / AD-019)?
5. Braucht die Statuszeile Verlauf, Ausblenden nach Zeit oder Hervorhebung von Ablehnungen?
6. Kontext-Hinweiszeile (Wings-Stil) als eigene Zeile oder in der Bar?
7. Toolkit-Gate: bleiben pyglet-Labels, oder Panels/Slider/Kurveneditor mit ImGui/Qt (REFERENCE_HARDWARE: GL 3.3)?
8. Schriftgröße / HiDPI auf dem alten PC lesbar?

Die aktuelle Bestandsaufnahme und ihre vorläufigen Prioritäten stehen in [GUI_Bestandsaufnahme.md](GUI_Bestandsaufnahme.md); sie ersetzen die offenen Artist-Urteile in diesem Dokument nicht.

## 6. Testschritte für Manu (Praxistest)

> Die Schritte 1 und 5 beschreiben die alte A/B-Erprobung; sie sind durch den Praxistest in §7 ersetzt (die übrigen
> Schritte gelten weiter, nur ist die Leiste jetzt kompakt — `F4` zeigt alles).

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

## 7. Stufe 1b — Phase A1: Statusklarheit und Raumorientierung

**Status:** IMPLEMENTED 2026-11-03 (Discovery, M5; alles `PROVISIONAL`) · Basis `main` @ `b1971ec` · Auftrag:
[GUI_Bestandsaufnahme §7](GUI_Bestandsaufnahme.md) (Review-Hinweis 2026-11-03; A2 Gesten-Feedback und A3 dauerhafte
Gewichtsansicht sind eigene Pakete) · rein lesend: kein Befehl, keine Sperre, keine Geste, kein Core und
`config/keymap.json` sind geändert.

### 7.1 Was gebaut ist

- **Statusleiste** (`src/hud.py`, ersetzt die alte 16-Zeilen-Liste): *Warnmarken* zuerst (rot hinterlegt),
  dann **Modus** als eine Zeile `Vertex Edge Face Object Pose` mit dem aktuellen Modus in Gelb — Pose ist der fünfte
  Eintrag (aus `SkeletonController.pose_mode`, der Auswahlmodus darunter bleibt unberührt) und die Morph-Bearbeitungsansicht
  hängt als Zusatz daran (`Face · target 'Smile'`), dann **Tool bzw. laufende Geste** (im Pose-Modus `Bone · Rotate`,
  laufend `Bone · Rotate (running)`; eine Gewichtsgeste heißt `Set weight`, nicht mehr wie ihr Befehlsname), dann **nur
  Abweichungen vom Standard**: Axis (gesetzt oder sticky), Space (Normal), Pivot (nicht „off“), Sym, Soft, SubD — und
  **aktuelles Morph-Ziel** und **aktueller Knochen** (`'Jaw' · rest/posed`), wenn es sie gibt. *Voll* (`F4`) zeigt
  zusätzlich alles Alte: Display, View, Look, Region, Targets-Liste, Rig-Text, Fixed (und die Standardwerte).
- **Warnmarke „Pose · 6 = rest“**, solange das Edit-Mesh posiert **und** gebunden ist (AD-028 §7.1: dann lehnt
  `can_run` Positions- und Topologiebefehle ab). Die Taste kommt aus den Bindings. Ebenso eine Marke „Keymap invalid“.
- **Gedimmte Tastenhinweise** für Befehle in `HudState.unavailable` (`can_run`, Quelle „ui“, `operands=False`): im
  Pose-Modus sind z. B. `Shift+S` (Symmetrie) und `P` dunkel, im posierten Face-Modus `W/E/R` — die Ablehnung wird
  vorher sichtbar, nicht erst danach.
- **Name am Knochen** (`BoneTag`): der aktuelle Knochen mit Namen am posierten Kopf, im Pose-Modus und in `1`/`2`/`3`,
  solange es ein Rig gibt (nicht in `4`, nicht im Knife) — damit sieht man, auf welchen Knochen `8` schreibt.
- **XYZ-Achsenkreuz** (`OrientationTriad`): die Weltachsen, nur um die Blickrotation der Kamera gedreht (keine
  Perspektive, Zoom und Pan ändern nichts), in den Gizmo-Farben (X rot, Y grün, Z blau), beschriftet, klein in einer
  Ecke, **immer** gezeichnet — auch während Gesten, im Pose-Modus und in den Ortho-Ansichten. Eine Achse, die auf den
  Betrachter zu oder von ihm weg zeigt (z. B. Z in `Front`), ist ein Punkt, ihr Buchstabe steht neben der Mitte; Achsen,
  die vom Betrachter weg zeigen, sind dunkler. Nicht anklickbar (Klicks sind Phase B). Es hält Abstand zur Leiste:
  `Hud.inset_top/inset_bottom` sagen ihm, wie viel Platz sie braucht, auch wenn sie umbricht.

### 7.2 Varianten für den Test (Fenster-Commands im Kontext `window`, nur diese Sitzung, nicht gespeichert, `PROVISIONAL`)

| Taste | Befehl | Wirkung |
|---|---|---|
| `H` | `ToggleHud` | Leiste ein/aus (kein Umschalten A/B mehr) |
| `F3` | `HudPositionToggle` | Leiste unten ↔ oben (Start: unten) |
| `F4` | `HudDetailToggle` | kompakt ↔ voll (Start: kompakt) |
| `F5` | `TriadCornerToggle` | Achsenkreuz unten links ↔ oben rechts (Start: unten links) |
| `F6` | `TriadSizeToggle` | Achsenkreuz M (40 px Achsenlänge) ↔ S (26 px) (Start: M) |

Konfliktcheck: `F3`–`F6` waren in den Code-Defaults (alle Kontexte) und in `config/keymap.json` frei
(`tests/test_hud_strip.py::test_the_new_keys_are_window_commands_and_conflict_with_nothing`, `…_keymap_json_has_no_entry…`);
die Tasten stehen als Hinweis am Ende der Leiste („F4: more · H: HUD“, voll: alle vier). Eine Taste steht erst mit
deinem Wort in `config/keymap.json` (AGENTS.md §7).

### 7.3 Engineering-Entscheidungen und Ergebnisse zu §3 / §5

- **Nähte (§3):** Der Datenpfad bleibt `hud_state` → `hud_rows` → Layout. Neu sind nur lesende Zugriffe:
  `Application.current_bone_name`, `edit_mesh_posed_and_bound`, `current_bone_tag()`, `gesture_label`,
  `morph_editing_target_name` (und die Entsprechung im `MorphController`); `HudRow` trägt Rang (Marke / primär /
  sekundär), „leise“ (Standardwert), die Tastenhinweise einzeln mit Dim-Flag und beim Modus die Auswahl. Der
  Layout-Teil bleibt pyglet-eigen und toolkit-frei trennbar; das Achsenkreuz und die Knochen-Marke sind die ersten
  Viewport-Elemente des Fensters, die **nicht** von `Application` gezeichnet werden und nichts anklicken.
- **Kein Neuaufbau pro Frame:** Das Achsenkreuz (3 Linien, 3 Buchstaben) und die Marke (1 Label, 1 Platte) werden einmal
  angelegt und nur bewegt — und nur, wenn sich Kamera, Fenster, Leiste oder Variante ändern (`moves`). Die Leiste wird wie
  zuvor nur bei geänderter `HudState` / Größe / Variante neu gebaut.
- **Zu §5 offene Fragen:** (1) Leiste unten/oben und kompakt/voll — Test unten; (2) fehlende Einträge: Modus, Pose,
  Bind-Status, Ziel und Knochen sind jetzt da; Auswahl-Anzahl, Licht-Preset, Soft-Metrik bleiben offen; (5) Ablehnungen
  hebt die Statuszeile weiterhin nicht ab (A2); (8) Schrift: unverändert 10 pt, am Referenz-PC prüfen.
- **Bewusst nicht gebaut:** Achslinie und Wert am Cursor (A2), dauerhafte Gewichtsansicht (A3; sie teilt sich heute die
  Soft-Färbung und lebt nur in der Gewichtsgeste, AD-028 §8.4), Klickbares, Treffertest, Panels.

### 7.4 Messung (Container, Xvfb, Software-GL, 1024×768, Kopf im Pose-Modus, posiert und gebunden)

| Was | Wert |
|---|---|
| `hud_state(app)` pro Frame (inkl. `can_run` für ~60 Befehle) | ≈ 0,15 ms |
| `Hud.update` (Snapshot + Vergleich) | ≈ 0,10 ms |
| Leiste zeichnen (fertiger Batch) | kompakt ≈ 0,4 ms, voll ≈ 0,6 ms (alt: 0,7 ms) |
| Leiste neu bauen (nur bei Änderung) | kompakt ≈ 4 ms, voll ≈ 14–20 ms (alt, Leiste unten: ≈ 12 ms) |
| Achsenkreuz: bewegen / zeichnen pro Orbit-Frame | ≈ 0,03 ms / ≈ 0,25 ms |
| Knochen-Marke: `current_bone_tag()` / zeichnen | ≈ 0,01 ms / ≈ 0,25 ms |
| 150 Orbit-Frames: Leiste neu gebaut / Labels erzeugt | 0 / 0 (Achsenkreuz 151× bewegt, Marke 1× Text gesetzt) |
| Orbit-Frame gesamt, alles aus → alles an (Median) | 5,0 ms → 6,0 ms (+1,0 ms in Software-GL) |

Das ist **kein** Ergebnis für den Referenz-PC (`docs/architecture/REFERENCE_HARDWARE.md`): Software-GL hat andere
Kosten, und das Textlayout läuft in Python auf der CPU. Die frühere Angabe „`update()` ≈ 5 µs“ (§2) stammt von vor
`HudState.unavailable`; heute kostet der Snapshot ≈ 0,1 ms.

### 7.5 Praxistest für Manu (Discovery, eine Sitzung, ca. 20–40 Minuten)

**Annahme (bitte mit einem Satz korrigieren):** Phase A1 kommt zuerst (E1 der Bestandsaufnahme ist noch nicht
entschieden; die Review-Notiz schlägt A1 als Einstieg vor, ein Verdikt von dir gibt es nicht). Das hier ist der Test
dazu, keine Checkliste: melde, was Probleme macht (Manu, 2026-10-29).

Start: `python src/main.py` (Kopf). Für die Pose-Schritte ein Rig wie im [AD-028-Praxistest](../architecture/AD-028-SKELETON-AND-SKINNING.md#praxistest-für-manu-nach-dem-bau-deutsch-ca-20-minuten)
(Schritte 1–4: Symmetrie, Gruppe, `P` + `Strg+J`, `7` halten, `5`, `E`).

1. **Modus auf einen Blick.** Leiste unten, kompakt: `1`/`2`/`3`/`4` drücken — der Modus leuchtet in der Zeile
   `Vertex Edge Face Object Pose`. `W` halten (mit Auswahl): „Tweak · Move (running)“. Siehst du Modus und laufende
   Geste, ohne nach unten zu schauen? (Dazu `F3`: Leiste oben.)
2. **Pose als fünfter Modus (E2).** `5`: „Pose“ leuchtet, „Tool“ sagt „Bone · Rotate“, `E` halten: „Bone · Rotate
   (running)“. Fühlt sich Pose neben `1`–`4` richtig an, oder ist es ein anderer Ort (Zusatz, eigene Marke)?
3. **Posiert und gebunden.** Nach dem Drehen: die rote Marke „Pose · 6 = rest“. `1` drücken: `W/E/R` sind gedimmt.
   Merkst du, dass das Mesh posiert ist, **bevor** `W`/`I`/`Strg+J` abgelehnt werden? `6` → die Marke geht.
4. **Welcher Knochen?** Im Pose-Modus und in `1`/`2`/`3` steht der Name am Knochenkopf. Weißt du, auf welchen Knochen
   `8` schreibt? Stört der Name? (In `4` und im Knife ist er weg.)
5. **Morph-Ziel.** `Strg+N`, `Tab`: im Modus steht „· target 'Target 1'“, in der Leiste das Ziel. `Tab` zurück: der Zusatz
   geht.
6. **Achsenkreuz (E8).** Orbit (`Alt`+LMB), in Ortho-Ansichten (`Shift` im Orbit): X rot nach rechts, Y grün nach oben
   in „Front“; Z ist dort ein Punkt mit Buchstabe. Hilft es beim Orbit und in den Ortho-Ansichten, oder stört es?
   Auch beim Halten von `W`/`E`/`R` und im Pose-Modus bleibt es. `F5`: Ecke unten links ↔ oben rechts, `F6`: Größe.
   Welche Ecke, welche Größe, welche Form (Linien mit Buchstaben, Pfeilspitzen, Kugeln)?
7. **Leiste (E4).** `F3` oben/unten, `F4` kompakt/voll: arbeite eine Weile in jeder Lage. Oben oder unten? Kompakt
   genug, oder fehlt in kompakt etwas, das du ständig brauchst (dann sag was)? Deine Wahl schließt auch das alte A/B-Urteil
   (§4). `H` blendet ein/aus.
8. **Tempo.** Orbit und Zoom mit allem an und mit `H` aus: spürbar langsamer? (Messung im Container: +1 ms in
   Software-GL, kein Neuaufbau beim Orbit — aber nur dein PC zeigt es wirklich.)

Trag dein Urteil (Datum, Wortlaut) in §4 ein.

### 7.6 Was noch den Referenz-PC braucht

Alles Gefühlte (Lesbarkeit, Ecke, Größe, Form, oben/unten, kompakt/voll, Schrift bei HiDPI) und die Orbit-/Zoom-Kosten mit
echtem GL (Schritt 8). Im Container geprüft: Zeilen je Zustand, Abweichungs-Filter, Marke, Dimmen, Morph-Zusatz,
Knochen-Marke, Achsenrichtungen aller Standardansichten, Platz zur Leiste in beiden Ecken/Lagen, „nie neu bauen“, Pixel
des echten pyglet-Wegs (`tests/test_gl_hud_marks.py`).

## 8. Stufe 1c — Phase A3: dauerhafte Gewichtsansicht

**Status:** IMPLEMENTED 2026-11-03 (Discovery, M5; Taste, Texte und Look `PROVISIONAL`) · Basis `main` @ `ee19908` ·
Architektur: **W1a, Entscheidung Manu 2026-11-03** — die Ansicht ist ein Anzeige-Besitzer im bestehenden Soft-Routing
(`Application._soft_show`, Flächenfärbung), kein zweiter Kanal, kein Shader-Weg · Regeln:
[AD-028 §8.4/§8.5, Addendum 2026-11-03](../architecture/AD-028-SKELETON-AND-SKINNING.md#addendum-2026-11-03-the-weight-view-gui-phase-a3-w1a),
[AD-020 §5, Notiz 2026-11-03](../architecture/AD-020-SOFT-SELECTION-APP-PATH.md#52-rejected-alternatives) · A2
(Achslinie, Wert am Cursor) ist vorerst übersprungen.

### 8.1 Was gebaut ist

- **`9` = Gewichtsansicht an/aus** (`WeightViewToggle`, Sitzungszustand: nicht gespeichert, kein Undo-Schritt, bleibt
  über ein Laden an). In `1`/`2`/`3` und im Pose-Modus; in `4` wird das Einschalten abgelehnt
  („Weights view: in 1/2/3 or pose mode (5)“).
- **An:** die Flächenfärbung zeigt den Anteil des **aktuellen Knochens** am Edit-Mesh (dieselben Wärmefarben wie die
  Färbung während `7`/`8`), ohne etwas zu schreiben. Die **Soft-Vorschau ruht** solange (keine Bänder, keine
  Soft-Färbung); Soft selbst, Radius und die Gesten bleiben unverändert.
- **Gesten besitzen die Anzeige wie bisher:** ein W/E/R-Zug mit Soft zeigt während des Zugs seine eigenen Gewichte,
  `7`/`8` zeigen den Anteil ihres Strichs; beim Loslassen (oder `Esc`) kommt **die Gewichtsansicht** zurück, nicht die
  Soft-Vorschau.
- **Aus:** die Soft-Vorschau kommt über ihren normalen Refresh zurück.
- **Nichts zu zeigen** — die Ansicht bleibt an, die Färbung ist leer, die Leiste sagt warum: `Weights · — (no rig)`,
  `— (no bone)`, `— (no weights on 'cube')` (Objekt ohne Skin-Layer, ungebunden), `— (object level)` (`4`),
  `— (target view)` (Morph-Bearbeitungsansicht, `Tab`: der Anteil wird nicht auf dem Ziel gezeigt).
- **Leiste:** primärer Eintrag `Weights · Jaw` (mit Taste `9`), nur solange die Ansicht an ist; der Soft-Eintrag sagt
  dann `… · preview hidden (weights view)`.
- **Posiert:** die Flächenfärbung sitzt jetzt auf dem **gezeigten** Mesh (Pose, sonst Morph-Mischung) — siehe 8.2.

### 8.2 Engineering-Entscheidungen und Befunde (`PROVISIONAL`)

- **Taste `9`:** neben `7`/`8`, ohne Modifier (Alt orbitet, Strg rastet während Gesten). Frei in `config/keymap.json`,
  in allen Kontexten der App (global, Knife, SubD, Morph, Fenster) und im Morph Lab
  (`tests/test_weight_view.py::test_the_key_is_free_and_the_command_only_shows`). `config/keymap.json` ist unverändert.
- **Besitzregel an einer Stelle:** `_soft_preview_refresh` zeigt bei eingeschalteter Ansicht den Anteil statt der
  Vorschau. Damit führt jeder bestehende Auslöser (Auswahl, Modus, Einstellungen, Laden, Undo/Redo, Topologie,
  Gestenende, Edit-Objekt über `_hidden_push`) automatisch zum Anteil zurück. Bei ausgeschalteter Ansicht ist der Weg
  unverändert (Stop-Punkt 1 nicht berührt). Hover-Wechsel rechnen bei eingeschalteter Ansicht nichts.
- **Auslöser ohne Soft-Refresh** hatten alle einen bestehenden Haken in `Application`, kein neuer Controller-Vertrag
  (Stop-Punkt 2 nicht berührt): Knochenbefehle (`Alt+J`, neu, löschen; `_run_rig`), Klick im Pose-Modus (`select_at`),
  Laden (nach `SkeletonController.reset`).
- **Neu rechnen nur bei Bedarf:** ein kleiner Cache (`ShareCache`, `controllers/skeleton.py`) je (Mesh, Skin-Layer,
  Knochen) hinter einem `Mesh.watch()` — neu gerechnet wird nur, wenn sich Knochen/Objekt ändern oder das Mesh Layer-
  bzw. Topologie-Änderungen meldet (Gewicht-Commit, Undo/Redo, Topologie, Binden/Lösen, Knochen löschen). Positionen
  allein rechnen nie neu. Die Berechnung `bone_shares` teilt sich die Geste (`_show_share`).
- **Zielansicht (Stop-Punkt 3):** eindeutig — das Bearbeitungsobjekt ist eine ungebundene Kopie ohne Layer
  (AD-025 §15, AD-028 §5.2); die Ansicht zeigt dort nichts und sagt `target view`.
- **Befund: die Färbung blieb in der Pose am Ruhe-Mesh.** Die Annahme des Auftrags („folgt über die bestehende
  Positions-Synchronisation“) traf nicht zu: Zusatz-Overlays synchronisieren am Edit-Mesh (Ruheform); gemessen lagen
  69 von 69 Overlay-Punkten auf Ruhepositionen. Das betraf auch die heutige Färbung während `8` in der Pose
  (AD-028-Praxistest Schritt 5). **Behoben im bestehenden Kanal:** die Flächenfärbung (`GLSoftShadingOverlay`) bekommt
  eine Käfig-Quelle (`set_cage_source`, `Application._shown_cage`: die gezeigte Pose-Fläche, sonst die Morph-Mischung —
  dasselbe Mesh mit denselben IDs, das die Kanten schon zeigen) und liest die Positionen dort; ein Watch auf diese
  Fläche lässt einen Pose-Schritt die Positionen nachziehen. Topologie, Auswahl, Picking und die Soft-**Bänder**
  bleiben am Ruhekäfig (AD-028 §5.2). Das gilt für jede Flächenfärbung, also auch Soft-Vorschau und Gesten.
- **`8` mit eingeschalteter Ansicht:** der Strich der Geste umfasst schon alle Punkte, die den Knochen beim Drücken
  hatten — die Färbung während des Zugs ist darum die volle Ansicht, kein Ausschnitt.

### 8.3 Messung (Container, Python 3.13, Xvfb, ohne GL-Zeichnen; p50 / p95)

| Was | Kopf (326 V, 264 mit Knochen) | Körper (928 V, 240 mit Knochen) |
|---|---|---|
| Anteil neu rechnen (`bone_shares`) | 0,07 / 0,10 ms | 0,09 / 0,11 ms |
| Auslöser mit Neuberechnung + Übergabe an die Färbung | 0,08 / 0,12 ms | 0,10 / 0,11 ms |
| Auslöser ohne Änderung (Auswahl, Soft-Einstellung: Cache) | 0,007 / 0,009 ms | 0,007 / 0,010 ms |
| `Alt+J` als ganzer Tastendruck (Driver, inkl. Frame-Tick) | 1,4 / 3,3 ms | 1,3 / 2,5 ms |
| pro Frame neu: `dirty`-Prüfung der Färbung (nur solange etwas gefärbt ist) | ≈ 50–70 ns | ≈ 50 ns |
| 150 Orbit-Frames mit Ansicht an: Neuberechnungen / Übergaben | 0 / 0 | 0 / 0 |

Zur Einordnung: `gollum` (87 500 V, synthetischer Skin-Layer) 15 % gewichtet 12 / 18 ms, 100 % 95 ms pro Auslöser
(nicht pro Frame; `Mesh.layer_items` sortiert). Kein Ergebnis für den Referenz-PC: echtes GL und das Zeichnen der
Färbung beim Orbit misst nur dein PC (Schritt 7).

### 8.4 Praxistest für Manu (Discovery, eine Sitzung, ca. 20–40 Minuten)

Kein Abhaken: melde, was Probleme macht. Start: `python src/main.py` (Kopf). Rig wie im
[AD-028-Praxistest](../architecture/AD-028-SKELETON-AND-SKINNING.md#praxistest-für-manu-nach-dem-bau-deutsch-ca-20-minuten)
Schritte 1–3 (Symmetrie, Gruppe „Jaw“, `P` + `Strg+J`, `7` halten). Die Taste `9` ist ein Vorschlag; sag „Taste
passt“ oder nenne eine andere.

1. **Gewichtsansicht an.** `1`, dann `9`: der Kiefer färbt sich nach dem Anteil des Knochens, in der Leiste steht
   `Weights · Jaw`. Kannst du einen Mundwinkel prüfen, ohne `8` zu halten? Sind die Farben lesbar (stark rot … schwach
   blau)?
2. **Knochen wechseln.** Mit `P` + `Strg+J` einen zweiten Knochen anlegen (die Färbung wird leer: er hat noch keine
   Gewichte), dann `Alt+J`: springt die Ansicht sofort auf „Jaw“ zurück? Im Pose-Modus (`5`) beide Knochen anklicken:
   springt sie bei jedem Klick richtig mit?
3. **Edit-Objekt wechseln.** `Shift+A` → einen Würfel hinzufügen (er ist danach in `4` gewählt), `1`: der Würfel ist
   das Edit-Objekt, die Färbung ist leer, die Leiste sagt `Weights · — (no weights on 'cube')`. In `4` den Kopf wählen,
   `1`: die Gewichte sind sofort wieder da. Ist klar, dass es auf dem Würfel nichts gibt? (In `4` steht
   `— (object level)`, in der Morph-Bearbeitungsansicht `Tab` steht `— (target view)`.)
4. **Gewicht ändern und zurücknehmen.** Mundwinkel-Punkte wählen, `8` halten + Maus, loslassen: die Ansicht zeigt das
   neue Gewicht. `Strg+Z`, `Strg+Y`: bleibt die Färbung stimmig?
5. **Soft und Ansicht.** `O` (Soft an) bei eingeschalteter Ansicht: die Soft-Bänder fehlen, im Soft-Eintrag steht
   `preview hidden (weights view)`. Ist klar, warum? Einen Punkt wählen, `W` halten und ziehen: während des Zugs die
   Soft-Zone, nach dem Loslassen wieder die Gewichte? `9` aus: kommt die Soft-Vorschau zurück?
6. **Posiert und gebunden.** `5`, Knochen anklicken, `E` halten und den Kiefer öffnen: folgt die Färbung dem
   geöffneten Kiefer (nicht mehr dem geschlossenen)? Auch während `8` in der Pose? (Die Auswahlpunkte bleiben bewusst
   am Ruhe-Mesh.)
7. **Tempo.** Orbit und Zoom mit Ansicht an und aus: spürbar langsamer?

### 8.5 Was noch den Referenz-PC braucht

Alles Gefühlte (Lesbarkeit der Färbung, Taste, ob die ruhende Soft-Vorschau verständlich ist, ob die Färbung auf der
Pose richtig sitzt) und die Orbit-Kosten mit echtem GL (Schritt 7). Im Container geprüft (`tests/test_weight_view.py`):
Anzeige beim Einschalten, Soft-Vorschau unterdrückt und zurück, Soft- und Gewichtsgeste besitzen die Anzeige und geben
an die Ansicht zurück (auch `Esc`), Knochenwechsel (`Alt+J`, Pick, neu, löschen), Edit-Objekt (auch ohne Rig und direkt
über `set_edit_object`), Undo/Redo, Topologie, Binden/Lösen, Laden, Zielansicht, Hover ohne Rechnung, Färbung auf der
Pose und zurück in Ruhe, Leisteneinträge und Taste.

