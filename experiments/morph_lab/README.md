# Morph Lab (WP-MORPH-LAB-01)

**Status: Praxistest beantwortet (2026-10-17), Iteration offen.** Gebaut und automatisch getestet (2026-10-16); Manus Antworten
und Verdikte stehen unter „Praxistest“ (`,`/`.` und relatives Ziel umgesetzt, 2026-10-17, noch nicht artist-geprüft; Schieberegler offen).
Discovery-Lab unter `experiments/`. **Seit 2026-10-27 hat Production ein Morph-Ziel pro Mesh** (AD-025 Phase 3,
[§15](../../docs/architecture/AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md#15-editing-view-and-phase-3-implementation-note-2026-10-27)):
Abstände im Basis-Mesh, daneben bearbeitet wie hier (J-5), Gewicht als Ansicht. **Rolle des Labs seitdem:** Discovery für
das, was Production nicht macht (Kiefer-Pose, relativ ↔ absolut, Kosten-HUD) — es ist nicht der Weg, ein Production-Ziel zu
bearbeiten. Ein mit `M` geschicktes Mesh mit Production-Ziel kommt hier als Paar an (Basis = Ruheform, „Ziel 1“ = Ruheform +
Abstände, beide ohne Layer); nichts geht zurück. Die Production-Tasten (`Strg+N`, `Tab`, `N`, `+`/`-`) kollidieren mit
keiner Lab-Taste. Das Lab läuft **auf dem App-Pfad** wie das SubD Lab: alle Modellier-Werkzeuge, Undo, Symmetrie, Soft Selection,
Licht und Shading sind die der App. Die gemischte Form zeichnet der Viewport über den Haken AD-013 H7
(`set_surface_provider`); das Lab ist dessen zweiter Nutzer, geprüft durch die unabhängige Review
[CLAUDE-001](../../docs/archive/morph_lab/reviews/AD-013_H7_MORPH_LAB_REVIEW_CLAUDE_001.md) (ACCEPT WITH CHANGES, Notiz in
[AD-013, „Second user (Morph Lab)“](../../docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#second-user-morph-lab-2026-10-16)).
Das Lab importiert nichts aus `playground/` oder anderen Experimenten (Test: `tests/test_import_boundary.py`).

## Starten

Vom Repo-Root, unter Windows und Linux gleich (nur `pyglet` wird zusätzlich gebraucht):

```
python experiments/morph_lab/run.py                          # head_basemesh (Default)
python experiments/morph_lab/run.py man_with_shoes_basemesh
python experiments/morph_lab/run.py head_basemesh --neu      # von vorn (alte Datei wird .bak)
```

Beim ersten Start pro Asset legt das Lab die Szene `scenes/morph_lab/<asset>.mirai.json` an: die **Basis** (das Asset) und
rechts daneben das **Ziel** (`<asset> · Ziel 1`), eine exakte Kopie mit denselben Punkt-Nummern. Spätere Starts öffnen
diese Datei wieder; `Strg+S` speichert hinein. Der Ordner `scenes/` ist nicht im Git, und das `Leertaste`-Menü der App
zeigt den Unterordner `morph_lab/` nicht.

### Aus `main.py` schicken (Brücke, `PROVISIONAL`)

Im Production-Fenster (`python src/main.py`) schickt die Taste **M** das ausgewählte Objekt ins Morph Lab: in Modus `4` das
eine ausgewählte Objekt (kein oder mehrere: Statuszeile, nichts passiert), sonst das Edit-Objekt. Das Lab öffnet sich in
einem eigenen Fenster, Basis und Ziel stehen sofort (`run.py --von <Datei>`). Das Objekt geht als Mesh-Kopie über
`scenes/morph_lab/von_main/<name>.mirai.json`; die Platzierung des Objekts geht nicht mit (Basis = Identität). Die Lab-Szene
heißt `scenes/morph_lab/<name>.mirai.json` und wird bei jedem Senden neu angelegt (die alte Datei wird einmal `.bak`) — ein
schon gesculptetes Ziel gleichen Namens ist damit weg, außer in der `.bak`. Das Production-Fenster bleibt unverändert (kein
History-Eintrag); abgelehnt, solange W/E/R/T oder das Knife läuft. Code: `src/morph_bridge.py`.

## Was die App macht, was das Lab macht

**Die App** (`src/main.py`): Navigation, Auswahl, W/E/R, Tweak, Soft Selection (`O`), Symmetrie (`Shift+S`), C/Knife,
Extrude, Loops, Delete, Undo/Redo, Objekt-Modus `4`, das bearbeitete Objekt wechseln, Anzeige-Modi, Licht, `Strg+S`.

**Das Lab** ergänzt nur das **Gewicht** und die Anzeige der Mischung: Ist die Basis das bearbeitete Objekt und das
Gewicht über 0 %, zeigt der Viewport statt der Basis die Mischung Basis → Ziel, mit Licht und Flat/Smooth der App.
**Auch beim Arbeiten am Ziel** zeigt die Basis die Mischung beim eingestellten Gewicht (Manu 2026-10-17): mit `Alt+Pfeil hoch/runter`
morpht man, während man das Ziel formt, und jeder Schritt am Ziel ist an der Basis sofort sichtbar. Das Ziel selbst wird wie
es ist gezeichnet. (Viewport-Erweiterung H7-E, siehe unten.)

Das Gewicht ist reine Ansicht: kein Undo-Schritt, wird nicht gespeichert, ändert weder Basis noch Ziel.

## Steuerung (Vorschlag, `PROVISIONAL`)

Umgestellt 2026-10-24 (Manu): `Pfeil`, `Shift+Pfeil`, `←`/`→` kollidierten mit den Look-Zeilen-Tasten der App (AD-024 §8, `LookRow*`, `LookValue*`, `Loop*`); Gewicht jetzt auf `Alt+Pfeil`, Basis/Ziel auf `,`/`.`. 2026-10-27: relativ ↔ absolut von `B` auf `Alt+B` (`B` ist seit 2026-10-25 Border Select der App; bis dahin startete das Lab nicht).

| Taste | Funktion |
|---|---|
| `Alt+Pfeil hoch` / `Alt+Pfeil runter` | Gewicht +10 % / −10 % |
| `Alt+Shift+Pfeil hoch` / `Alt+Shift+Pfeil runter` | Gewicht +1 % / −1 % |
| `Strg+Pfeil hoch` / `Strg+Pfeil runter` | Gewicht 100 % / 0 % |
| `M` | A/B: 0 % ↔ zuletzt eingestelltes Gewicht |
| `Alt+B` | Ziel **relativ ↔ absolut** (`PROVISIONAL`; später eine Checkbox in der UI; seit 2026-10-27 mit `Alt`, weil `B` in der App Border Select ist) |
| `.` (Punkt) | **Ziel bearbeiten** (`PROVISIONAL`, J-2) |
| `,` (Komma) | **Zurück zur Basis** |
| alternativ | `4` · Klick aufs Objekt · `1` (wie die App) |
| alles andere | die App |

| `Alt+Pfeil rechts` / `Alt+Pfeil links` | **Kiefer-Pose** +5° (öffnen) / −5° (schließen) (`PROVISIONAL`, 2026-10-25) |
| `Alt+Shift+Pfeil rechts` / `links` | Kiefer ±1° |
| `J` | Kiefer: 0° ↔ zuletzt eingestellter Winkel |
| `Shift+J` | Kiefer-Scharnier = Mitte der ausgewählten Punkte (Modus `1`); nichts gewählt = automatisch |

`,` / `.` führen genau die App-Geste `4` · Objekt auswählen · `1` aus (kein eigener Pfad, kein Undo-Schritt, mit
den Ablehnungen der App); danach bist du im Komponenten-Modus, in dem du warst (aus `4` in `1`). Bei mehreren Targets wird die
Lösung neu entschieden.

Seit 2026-10-16 (deine Rückmeldung): Ein Klick in `4` **wählt nur aus**, das ausgewählte Objekt ist gelblich getönt;
`Alt+R` schaltet es auf Referenz und zurück (App-Verhalten, AD-021 Q-12 revidiert). Die Lab-Tasten werden beim Start gegen
die App-Tasten geprüft und ausgegeben; solange W/E/R/T oder der Knife läuft, lehnt das Lab sie sichtbar ab.

Oben im Fenster stehen drei HUD-Zeilen: (1) Gewicht, Kosten eines Schritts, Hinweise; (2) **welches Objekt bearbeitet
wird** (Basis oder Ziel 1), der Modus und in `4` die Auswahl; (3) die letzte Meldung der App (in `src/main.py` steht sie nur
in der Konsole) — z. B. warum `1` das bearbeitete Objekt nicht gewechselt hat.

## Kiefer-Pose zusammen mit Morphs (`PROVISIONAL`, Übergang bis zum Rig, 2026-10-25)

Zum Beispiel Gollum: `python experiments/morph_lab/run.py gollum`. Der Kiefer wird **gedreht** und die Morphs liegen
**darunter** — erst die Mischung (Lächeln, Backen, was im Ziel steht), dann die Pose. Ein „Kiefer offen"-Ziel wird
also am ruhenden Kiefer gesculptet und fährt bei jedem Winkel mit.

1. An der Basis (`,`) die Flächen des Unterkiefers auswählen (Modus `3`), `Strg+G` (neue Polygroup), `Strg+Alt+N` →
   Name **`Kiefer`** (auch `Unterkiefer` / `Jaw`; Groß-/Kleinschreibung egal). Die Gruppe wird mit `Strg+S` gespeichert.
2. Optional das **Scharnier** setzen: Punkte am Kiefergelenk auswählen (Modus `1`), `Shift+J`. Ohne Scharnier nimmt das Lab
   die Gruppenmitte in X, die Oberkante in Y und die Rückseite in Z (für einen Kopf, der nach +Z schaut). Achse ist X.
3. `Alt+Pfeil rechts/links` dreht, `J` vergleicht mit 0°. Positive Winkel öffnen einen Kiefer, der nach +Z schaut.
   Außerhalb der Gruppe läuft die Pose über 3 Kantenringe auf 0 aus (Mundwinkel/Wange reißen nicht).

Wie das Gewicht ist die Pose **reine Ansicht** (kein Undo, nicht gespeichert, ändert weder Basis noch Ziel) und
erscheint an der Basis; auch beim Sculpten des Ziels zeigt die Basis Mischung **und** Pose. Auswahl/Picking liegen
wie beim Gewicht auf der Ruhelage. Kosten bei Gollum (87 500 V, Container): erster Schritt einmalig einige Sekunden
(Ersatzfläche), danach ca. 80–150 ms je Schritt — für Tastenschritte, nicht zum Ziehen. Grenzen: nur eine Achse (X), ein
Scharnier, harte Gewichte 1 in der Gruppe; ein echtes Rig mit Gelenk-Gewichten ersetzt das später (AD-005).

## Praxistest für Manu (ca. 20–30 Minuten)

`python experiments/morph_lab/run.py`

1. **Ziel finden.** Das Ziel steht rechts neben dem Kopf, die Kamera zeigt aber nur den Kopf: mit dem **Mausrad ein paar
   Rasten zurück**, bis beide zu sehen sind.
2. **Ziel formen.** `.` (HUD: `Bearbeitet: Ziel 1`; oder `4`, aufs Ziel klicken, `1`). Dann ein Lächeln oder einen offenen Kiefer
   modellieren — mit allem, was die App hat: W/E/R, Tweak (Strg+LMB ziehen), Soft Selection (`O`), Symmetrie (`Shift+S`),
   Undo. Die HUD sagt `Ziel wird bearbeitet`.
3. **Zurück zur Basis** (`,`) und mit `Alt+Pfeil` das
   Gewicht hochfahren. Bei 0 % ist es exakt die Basis, bei 100 % exakt das Ziel; jedes Gewicht sieht gleich aus, egal auf
   welchem Weg du es erreichst. `M` vergleicht 0 % mit dem letzten Gewicht.
4. **Weiterformen und vergleichen.** Am Ziel nachbessern, zurück, wieder schieben. `Strg+Z` springt zum Objekt des
   Schritts zurück (wie in der App).
5. **Speichern.** `Strg+S`, Fenster schließen, neu starten: Basis und Ziel sind wieder da (Gewicht 0 %).
6. **Gegenproben.** (a) In `1` bei 50 % an der Basis arbeiten: Auswahl, Hover und Picking liegen auf der *Ruheform* der
   Basis, nicht auf der sichtbaren Fläche (HUD: `Auswahl/Picking = Basis-Ruhelage`). (b) Ein `C`-Schnitt an Basis oder
   Ziel: die Mischung geht aus (`Morph aus: Topologie …`), `Strg+Z` bringt sie zurück. (c) Optional: in `4` das Ziel
   (Klick) mit `Strg+A` übernehmen — die Mischung verrutscht um den Abstand, das Lab warnt; `Strg+Z`.

**Fragen** (je eine Zeile reicht):

- J-2: Reicht das Wechseln Basis ↔ Ziel über `4` · Klick · `1`, oder braucht es eine eigene Taste? Ist die gelbliche
  Tönung der Auswahl in `4` gut erkennbar? (Eine schnellere Taste wäre eine App-Fähigkeit → eigener Schritt.) Manu: Links Rechts Pfeiltasten um zwischen Basis und Ziel zuwechseln (provisional, später,wenn mehrere Targets existieren, überlegen wir uns eine andere Lösung)
- J-3: Wenn du nach dem Ziel noch die **Basis** änderst: Soll das Ziel die Änderung mitnehmen (relativ) oder seine Form
  behalten (absolut, so ist es gebaut)? Manu: relativ
- J-4: Reichen Pfeiltasten fürs Gewicht, oder brauchst du einen Schieberegler zum Ziehen? Manu: Schieberegler
- J-5: Ziel **daneben** formen (so ist es gebaut) oder **an Ort und Stelle** über einer durchscheinenden Basis? Manu: Daneben
  Und: Soll ein Gewicht ein Undo-Schritt sein bzw. mitgespeichert werden?
- Manu: Nein
- Wie stört es (6a), dass Auswahl und Picking bei Gewicht > 0 % auf der Ruheform liegen? Manu: Hilft eher, da man so sehen kann, wie weit etwas von der Basis abweicht

| Punkt                           | Verdikt (KEEP / ITERATE / REJECT / UNKNOWN) | Notiz |
| ------------------------------- | ------------------------------------------- | ----- |
| Ziel neben der Basis formen (2) | KEEP                                        |       |
| Gewicht über Pfeiltasten (3)    | KEEP                                        |       |
| Vergleichen und Nachbessern (4) | KEEP                                        |       |
| Speichern / neu öffnen (5)      | KEEP                                        |       |

**Antworten J-2…J-5 (Manu, 2026-10-17) und was daraus folgt** — noch nicht umgesetzt, jeder Punkt ist ein eigener Schritt:

| Frage | Antwort | Folge (offen) |
|---|---|---|
| J-2 Wechsel Basis ↔ Ziel | `←` / `→` zum Wechseln (`PROVISIONAL`; bei mehreren Targets später neu entscheiden) | **Umgesetzt 2026-10-17** als Lab-Taste über die App-Geste (kein Eingriff in `src/`); Tönung nicht beanstandet |
| J-3 Basis nachträglich ändern | **relativ**: das Ziel nimmt die Änderung mit | **Umgesetzt 2026-10-17** (siehe „Annahmen“); Bezug nur in der Sitzung, gespeichert wird er erst mit dem Produktionsformat (AD-021 §4.9) |
| J-4 Gewicht | **Schieberegler** (Pfeiltasten reichen nicht) | **Offen, andere Session**; braucht UI im Fenster und Performance beim Ziehen (siehe „Messung“) |
| J-5 Ziel formen | **daneben** (wie gebaut) | keine Änderung |
| Gewicht als Undo-Schritt / gespeichert? | **Nein** | keine Änderung (wie gebaut) |
| 6a Auswahl/Picking auf der Ruhelage | **hilft** (zeigt die Abweichung von der Basis) | keine Änderung; bewusst behalten |

Verdikt gesamt: die vier Punkte oben **KEEP**; ITERATE: `,`/`.` und relatives Ziel sind umgesetzt (noch nicht von Manu geprüft), der Schieberegler steht aus.

## Annahmen (`PROVISIONAL`, in einem Satz korrigierbar)

- Das Ziel ist ein eigenes Objekt neben der Basis (Abstand 1,25 Basisbreiten nach rechts), angelegt nur in der Startszene;
  im laufenden Lab gibt es kein „neues Ziel“.
- Bei 0 % zeigt der Viewport die Basis selbst (keine Ersatzfläche), darüber die Mischung.
- Das Gewicht ist reine Ansicht (kein Undo, nicht gespeichert); Schritte 10 % / 1 %.
- Das Ziel ist **relativ oder absolut**, umschaltbar mit `Alt+B` (Standard relativ; reine Ansicht wie das Gewicht, nicht
  gespeichert). **Absolut:** die Form des Ziels, wie sie ist. **Relativ** (J-3, 2026-10-17): gespeichert ist seine Form, gelesen wird sie als Abstand zur Basis, wie sie war,
  als das Ziel zuletzt geformt wurde. Ändert man danach die Basis, geht das Ziel mit (100 % = Basis jetzt + Abstand). Ändert
  man das Ziel (oder macht es rückgängig), gilt wieder die Basis von jetzt als Bezug. Der Bezug lebt nur in der Sitzung:
  nach `Strg+S` und Neustart ist die geladene Basis der Bezug, Basisänderungen vor dem Speichern sind dann „eingebacken“.
- Basis und Ziel werden über die Namen gefunden, die das Lab schreibt; je Name genau ein Objekt, sonst startet das Lab
  nicht (Hinweis auf `--neu`). `--neu` hebt die alte Datei als `.bak` auf (eine Sicherung).

## Bekannte Grenzen

- Die Kamera rahmt nur das bearbeitete Objekt; das Ziel liegt beim Start außerhalb (Mausrad zurück). Ein „alles rahmen“
  hat die App nicht.
- Während das Ziel bearbeitet wird, liegen Auswahl/Hover/Picking am Ziel selbst (es ist das bearbeitete Objekt); die Basis zeigt
  nur die Mischung. Mit mehreren Targets (später) soll jedes seinen Anteil beitragen — heute gibt es genau eines.
- Bei Gewicht > 0 % liegen Drahtgitter (`Shift+D`), Auswahl, Hover, Soft-Bänder und Picking auf der Ruheform der Basis
  (H7: der Käfig bleibt maßgeblich). Ein W-Zug an der Basis bewegt die sichtbare Fläche nur um (1 − Gewicht) · Weg.
- Im Wireframe-Modus ist die Mischung nicht sichtbar (HUD-Hinweis).
- Topologie-Änderungen an Basis oder Ziel beenden die Mischung, bis sie auf **demselben** Mesh rückgängig gemacht sind;
  dieselbe Änderung an beiden nachzubauen geht nicht (die Punkt-Nummern laufen auseinander, ARCH-02).
- `Strg+A` auf dem verschobenen Ziel brennt den Abstand in die Form (Warnung, `Strg+Z`).
- Morph und SubD lassen sich nicht zusammen zeigen (H7: ein Provider).

## Messung (Container, nicht der Referenz-PC; dort etwa halb so schnell)

GL-Smoke unter Xvfb mit `GLRenderStore`, 2026-10-16. Ein Gewichtsschritt = Neuberechnung + GPU-Patch in `Viewport.sync()`.

| Asset | Ziel weicht ab in | Gewichtsschritt p50 / max | nur Hover (Gewicht > 0) |
|---|---|---|---|
| head_basemesh (326 V) | 15 % der Punkte | 2,9 / 3,5 ms | 1,4 ms |
| head_basemesh | allen Punkten | 9,1 / 9,8 ms | 1,7 ms |
| man_with_shoes_basemesh (928 V) | 15 % der Punkte | 6,3 / 9,9 ms | 5,1 ms |
| man_with_shoes_basemesh | allen Punkten | 24,7 / 27,7 ms | 2,5 ms |

Für Tasten-Schritte reicht das; für stufenloses Ziehen jedes Frame nicht (Viewport-Performance ist ein eigenes Thema).
Die HUD zeigt die Kosten des letzten Schritts auch auf deinem PC.

---

## For agents (English)

**Representation (`PROVISIONAL`, a lab convention, not a morph format).** Base and target are two `SceneObject`s; the
target's Mesh is `Mesh.from_state(base.export_state())`, so equal IDs pair vertices while `morph.topology_signature`
(IDs + edges + faces, sorted) agrees. Production storage belongs on the Mesh (AD-021 §4.9; precedent: the additive
`"symmetry"` key in `export_state`) — built since 2026-10-27 as Core point layers (AD-025). `Scene.morph_targets` stays
`None`. Why not the delta dict of `experiments/rigging-skinning-morphing` (AD-005, `RigController.morph_targets`): the
target must be sculptable with the app's own tools, and an object is what those tools edit; neither is the decided home.
In-place sculpting was not built: lab-held morph data outside the Mesh would drift on Undo, and H2-R4 forbids lab
History entries.

**Evaluation** (`morph.blend`; the target is relative since 2026-10-17: `t` below is `t` itself while base == reference, else `b + (t − r)` with `r` the session-local reference taken when the target was last changed — `morph.py` docstring): `k == 0` → no surface; `k == 100` → `t`; otherwise `b + (k/100)·(t − b)` — exact at both
ends, exact where `b == t`, exactly mirrored (review F-8/R-7; `(1−w)·b + w·t` drifts unchanged regions by an ulp).

**Files:** `morph.py` (GL-free evaluation + `MorphSurfaceProvider`), `lab_scene.py` (start scene file, pairing by name),
`lab_app.py` (context `morph_lab`, keys, HUD text), `lab_app_window.py` (pyglet wiring, `save=`), `run.py` (entry,
`build_app_lab`).

**Review CLAUDE-001 — how each finding is handled:**

| Finding | Where |
|---|---|
| F-1 status feedback loop | `MorphSurfaceProvider._set_message`: post only on a new text, re-read the serial after the own post; `test_morph.py::test_diverged_topology_is_reported_once…`, `test_app_lab.py::test_topology_change_switches_off_with_one_status…` |
| F-2 Ctrl+A on the target | offset warning `MESSAGE_OFFSET` (`OFFSET_WARNING_SHARE`), README; `test_apply_transform_on_the_target_warns_and_undo_restores` |
| F-3 editing the base at k > 0 | no surface at k = 0; HUD hint; practical-test question |
| F-4 note wording | AD-013 H7 "Second user (Morph Lab)" |
| F-5 attach order / load errors | `run.build_app_lab` attaches after the load; `LabSceneError` → exit 1 naming `--neu`; tests |
| F-6 names / folder | `scenes/morph_lab/`; `lab_scene.resolve_pair` exactly one per name; `test_ambiguous_names_refuse_the_start` |
| F-7 switch gesture | README, start-up listing; since 2026-10-16 the app's click in `4` selects only (AD-021 Q-12 revised, `Alt+R` switches Reference), so the gesture is `4` · click · `1`; HUD line 2 names the edited/selected object, line 3 the app's status |
| F-8 numerics | `morph.blend`; `test_morph.py` |
| F-9 cost | HUD timing; table above; signature of the target cached, re-read only after editing it or a new status |
| F-10 serial heuristic | `MorphSurfaceProvider.dirty` property; pinned by `test_a_foreign_status_wakes…` and the Ctrl+A test |
| F-11 Wireframe | HUD hint |
| F-12 Undo crash (latent, `src`) | not reachable from the lab (no `AddObjectCommand`); recorded as AD-021 E-15 |
| F-13 `--neu` | one `.bak`; `test_neu_keeps_one_backup` |
| F-14 / F-15 | this section; "Bekannte Grenzen" |

**Tests:** `pytest experiments/morph_lab/tests -q` (headless with `TraceStore`; the import-boundary test needs pyglet
and runs under `xvfb-run -a` in headless containers). `test_morph.py` (evaluation, provider), `test_app_lab.py` (app
path: start scene, weights, W + symmetry on the target, Undo Q-8, topology refusal, Ctrl+A, save/reopen, `--neu`,
refusals, HUD), `test_run_cli.py`, `test_import_boundary.py`.

**H7-E (2026-10-17):** the base is an object entry while the target is the edit object, so the lab needed the hook for entries.
`Viewport` reads the optional `provider.entry_surfaces` / `entry_moved` (additive, duck-typed; AD-013 "H7-E"); the provider fills
`entry_surfaces = {base_id: surface}` while the target is edited and the weight is above 0. `Alt+B` = `MorphSurfaceProvider.relative`.
Tests: `tests/test_viewport_surface_provider.py` (three H7-E tests), `test_app_lab.py` (base preview, `Alt+B`).

**Left/Right:** `lab_app.MorphAppLab.switch_edit_object` presses `4`, sets `selection.objects`, presses the mode key through `app.key_press` — the app's Q-5 switch, no private call, no History entry.

**Jaw pose (2026-10-25):** `morph.MorphSurfaceProvider.set_jaw_angle` / `set_jaw_pivot`; `jaw_weights` (polygroup
`JAW_REGION_NAMES`, linear falloff over `JAW_FALLOFF_RINGS`), `pose_jaw` (rotation about X, applied after `blend`);
`active` (weight > 0 or angle ≠ 0) replaces the former weight-only gate. `_SignatureCache` keeps `topology_signature`
per mesh and recomputes it only when the `Mesh.watch()` journal reports edges/faces/new or removed vertices (87 500 V:
0.7 s → 0). Keys in `lab_app.LAB_KEYS`; tests: `test_morph.py` (jaw section), `test_app_lab.py` (jaw section).

**Not in scope:** several targets or a runtime "new target" (needs a reviewed host entry; AD-021 E-15 first), a weight
slider, weights as document state, morph + SubD together, topology changes with morphs (ARCH-02), production storage (since 2026-10-27 in Production: AD-025 §15; a sent
Production target becomes the lab's pair in `lab_scene.build_pair_scene`).
