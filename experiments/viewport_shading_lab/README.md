# Viewport Shading Lab (WP-SHADE-LAB-01)

**Status: Nicht Artist-validiert.**
Stand: Slice 1 — Zwei-Licht-Rig (Key + Fill), gebaut 2026-09-26.

Eigenständiges Forschungsfenster für die Frage, welches Worklight die **Form** beim Modellieren am
besten lesbar macht. Das Lab ist ein Experiment, keine Production-Beleuchtung. Production
(`src/viewport/gl_render_store.py`, `LIGHT_DIR`, `FRAGMENT_SRC`) bleibt unverändert.

Spezifikation und Hintergrund:

- [`VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md`](../../docs/research/viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md)
  — §4.1a (Steuerkonzept des Rigs), §7 (Slice-Plan), §8 (Artist-Fragen F1, F8, F9)
- [AD-018](../../docs/architecture/AD-018-PRODUCTION-DRAW-BINDING.md) — Draw-Binding; Uniforms berühren nie die VertexList
- [AD-010 inkl. Addendum 2026-09-25](../../docs/architecture/AD-010-PLAYGROUND-SUPERSEDES-LAB-BINDING.md) — Playground bleibt unberührt; Vorbild für die Store-Unterklasse
- [AD-013](../../docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md) — Eingaben: gemeinsame Sprache, sichtbare Lab-Abweichungen

## Starten

Vom Repo-Root, unter Windows und Linux gleich:

```
python experiments/viewport_shading_lab/run.py                # Kopf (head_basemesh)
python experiments/viewport_shading_lab/run.py subd_cube      # anderes Mesh aus examples/meshes
```

Ein unbekannter Name bricht mit Exit-Code 2 und der Liste der gültigen Namen ab, bevor ein
Fenster aufgeht. Benötigt nur `pyglet` (wie `src/main.py`).

Belege ohne sichtbares Fenster (Xvfb oder EGL):

```
xvfb-run -a python experiments/viewport_shading_lab/evidence.py            # T1/T2 + PNGs
xvfb-run -a python experiments/viewport_shading_lab/evidence.py --bench 300
python -m pytest experiments/viewport_shading_lab/tests                    # automatische Tests
```

## Steuerung

Diese Tabelle ist 1:1 `LAB_OVERRIDES` in `lab_bindings.py` (wird beim Start ausgegeben;
`tests/test_lab_bindings.py` prüft die Übereinstimmung).

| Eingabe | Aktion | Hinweis |
|---|---|---|
| Alt+LMB ziehen | Orbit | Artist Input Truth |
| Shift+LMB ziehen | Pan | Artist Input Truth |
| Mausrad | Zoom | Artist Input Truth |
| RMB ziehen | Orbit | Production-Default wie src/main.py |
| MMB ziehen | Pan | Production-Default wie src/main.py |
| LMB ziehen | Key-Licht drehen (dx Azimut, dy Höhe) | Lab-Override „Licht ziehen“; ob das UX wird, entscheidet das UX-System |
| ↑ | HUD-Zeile hoch | lab-lokal |
| ↓ | HUD-Zeile runter | lab-lokal |
| ← | Wert kleiner (Shift = fein) | lab-lokal |
| → | Wert größer (Shift = fein) | lab-lokal |
| F1 | Preset „Heute“ | lab-lokal |
| F2 | Preset „Raitt 2:1“ | lab-lokal |
| F3 | Preset „Softbox“ | lab-lokal |
| F4 | Preset „Warm/Kalt“ | lab-lokal |
| B | A/B-Vergleich mit „Heute“ (Umschalter) | lab-lokal; Toggle, nicht Halten (AD-013 A3 offen) |
| H | HUD an/aus | = application.toggle_hud |
| P | Aufnahme (PNG ohne HUD + JSON) | lab-lokal |
| Esc | Beenden | Q bewusst nicht belegt (Artist Truth: Move) |

Verhalten im Detail:

- **B** zeigt „Heute“, ohne das bearbeitete Rig zu verändern. Jede Änderung (Pfeiltasten, LMB ziehen)
  beendet den Vergleich und wirkt auf das bearbeitete Rig, nie auf „Heute“.
- Nach jeder Änderung heißt das Preset „angepasst“.
- **Licht ziehen** dreht den Key im aktuellen Bezugsraum: 0,5° pro Pixel.
- **Aufnahmen** landen in `captures/` (per `.gitignore` nie committet): PNG des Viewports ohne HUD plus
  JSON mit allen Rig-Werten, Preset, A/B-Zustand, Kamera (Yaw/Pitch/Distanz), Mesh, Fenstergröße und Zeit.

### HUD-Zeilen

| Zeile | Bereich | Schritt (fein mit Shift) |
|---|---|---|
| Bezugsraum | Kamera / Welt | Umschalter |
| Key Azimut | −180…180° (läuft rundherum) | 15° (1°) |
| Key Höhe | −90…90° | 5° (1°) |
| Key Stärke | 0…2 | 0,05 (0,01) |
| Key Temperatur | 2500…10000 K | 500 K (100 K) |
| Key Weichheit | 0…1 (Wrap) | 0,1 (0,02) |
| Verhältnis Key:Fill | 1, 1,5, 2, 3, 4, 6, 8, aus | eine Stufe |
| Fill-Kopplung | gekoppelt / frei | Umschalter |
| Fill Azimut / Fill Höhe | wie Key | wie Key |
| Fill Temperatur / Fill Weichheit | wie Key | wie Key |
| Grundhelligkeit | 0…0,6 | 0,05 (0,01) |

- Grau: Fill-Winkel, solange der Fill gekoppelt ist; alle Fill-Zeilen außer dem Verhältnis, solange der Fill aus ist.
- **Summe Licht** = Grundhelligkeit + Key + Fill. Über 1 erscheint eine rote Warnung. Es wird nicht automatisch
  heruntergeregelt; die Grafikkarte schneidet über Weiß einfach ab.
- **Frame** = geglättete Zeit zwischen zwei Bildern in ms.
- Beim Umschalten **gekoppelt → frei** übernimmt der Fill seine aktuelle Richtung (kein Sprung).
- Beim Umschalten des **Bezugsraums** bleiben die Winkel-Zahlen gleich. Das Licht springt also auf dieselben
  Winkel im anderen Bezugsraum.

## Das Rig

Pro Bild rechnet Python aus den Reglern sieben Uniforms (`lab_rig.resolve()`). Der Shader
(`lab_store.FRAGMENT_SRC`) rechnet dann:

```
Licht = Grundhelligkeit + KeyFarbe · wrap(N·L_key, w_key) + FillFarbe · wrap(N·L_fill, w_fill)
wrap(x, w) = max((x + w) / (1 + w), 0)
Farbe = Grundfarbe · Licht        (Selection-Highlight danach wie in Production)
```

- **Richtung:** Azimut/Höhe → `(cos H · sin A, sin H, cos H · cos A)`. Bezugsraum „Welt“ = Weltachsen.
  Bezugsraum „Kamera“ = (rechts, oben, zur Kamera): A 0 / H 0 zeigt vom Objekt zum Betrachter.
- **Fill gekoppelt:** Azimut + 180°, Höhe gespiegelt — diagonal gegenüber und unterhalb (Raitt/Minter).
- **Stärke:** Fill = Key / Verhältnis.
- **Temperatur:** Schwarzkörper-Farbort nach Kim et al. (2002) → lineares Rec.-709-RGB, auf 6500 K
  weißabgeglichen (6500 K ist dadurch exakt neutral) und auf Rec.-709-Luminanz 1 normiert. Die Temperatur
  ändert also nur den Farbton, nie die Helligkeit. Details im Docstring von `lab_rig.kelvin_to_rgb()`.
- **Weichheit:** Wrap-Lighting. 0 = harte Lambert-Grenze wie heute.

Technik: `ShadingLabStore` ist eine Unterklasse des Production-`GLRenderStore`. Sie übernimmt den
Vertex-Shader per Import und alle Buffer-Pfade unverändert. Eigen sind nur der Fragment-Shader und die
Licht-Uniforms in `draw()`. Das Rig ist keine Ressource im `ResourceStore`. Es wird nur beim Zeichnen als
Uniform gesetzt.

## Presets (F1–F4)

Das sind **Startpunkte des Agents, keine Empfehlungen.** Es gibt keine Artist-Entscheidung zu Default-Werten.

| Taste | Name | Bezugsraum | Key (A / H) | Key Stärke | Key K | Key Wrap | Fill | Fill K | Fill Wrap | Grundhelligkeit | Summe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 | **Heute** | Welt | 29,74° / 36,66° (= normalize(0.4, 0.6, 0.7)) | 0,65 | 6500 | 0 | aus | – | – | 0,35 | 1,00 |
| F2 | **Raitt 2:1** | Kamera | −45° / 35° | 0,60 | 6500 | 0 | gekoppelt, 2:1 (0,30) | 6500 | 0 | 0,10 | 1,00 |
| F3 | **Softbox** | Kamera | −45° / 35° | 0,60 | 6500 | 0,5 | gekoppelt, 2:1 (0,30) | 6500 | 0,8 | 0,10 | 1,00 |
| F4 | **Warm/Kalt** | Kamera | −45° / 35° | 0,60 | 4500 | 0 | gekoppelt, 2:1 (0,30) | 8000 | 0 | 0,10 | 1,00 |

- Key-Stärke 0,60 bei F2–F4 folgt aus der Vorgabe „Summe ≈ 1“: 0,10 + 0,60 + 0,60 / 2 = 1.
- F2–F4 wurden gegenüber dem Handoff nicht verändert. Keines ist ausgebrannt (siehe `evidence/`).
- „Heute“ reproduziert die Production-Formel `mix(base·0.35, base, N·L)` = `base · (0.35 + 0.65 · N·L)` (T1).

Die Bilder in `evidence/` stammen aus `evidence.py` (480×360, Software-GL, Kopf, Standardkamera):
`production_glrenderstore.png`, `f1_heute.png`, `f2_raitt_2_1.png`, `f3_softbox.png`, `f4_warm_kalt.png`.

## Was die automatischen Tests beweisen — und was nicht

| Test | Beweist |
|---|---|
| T1 `test_lab_gl.py` | „Heute“ im Lab-Store und der Production-`GLRenderStore` liefern bei gleicher Kamera dasselbe Bild (max. 1 Stufe Rundungsdifferenz von 255). |
| T2 `test_lab_gl.py` | Alle Presets, jeder Regler in beide Richtungen (grob und fein), A/B und Licht ziehen: 124 Aktionen, 80 verschiedene gezeichnete Rigs, **null** Buffer-Uploads. Unverändert bleiben Ressourcen-IDs, VertexList-Identität, alle Upload-/Anlage-Zähler und die Upload-Bytes. Damit ist die K0-Einschätzung der Research gemessen, nicht nur behauptet. |
| T3 `test_lab_gl.py` | Jedes Preset und jeder Regler-Schritt verändert das Bild sichtbar (≥ 100 Pixel um ≥ 2 Stufen). Kein Regler ist also tot. |
| T4 `test_rig_math.py` | Richtungsmathematik: weltfest ist kamera-unabhängig, kamerafest bleibt im Kamerarahmen konstant, die Kopplungsformel stimmt, „Heute“ = `normalize(0.4, 0.6, 0.7)`. |
| T5 `test_rig_math.py` | Temperatur: Luminanz = 1 von 2500 bis 10000 K, 6500 K neutral, warm/kalt in die richtige Richtung. |
| T6 `test_rig_math.py` | Die Python-Referenz `shade()` ist Lambert bei Wrap 0, hellt mit Wrap hinter der Schattengrenze auf, und ein ausgeschalteter Fill trägt nichts bei. |
| T7 `test_lab_gl.py` | Der Lab-Store benutzt nie versehentlich den Production-Shader, auch wenn dieser zuerst kompiliert wurde. |
| T8 `test_lab_gl.py`, `test_import_boundary.py` | `glGetError() == 0` über alle Presets mit HUD. Keine Importe aus `playground/` oder anderen Experimenten. |
| weitere | Das HUD verändert den nächsten Mesh-Frame nicht. Die Aufnahme ist exakt das HUD-lose Bild. Ein unbekannter Mesh-Name ergibt Exit-Code 2. Die Steuerungstabelle ist gleich der README. |

**Was kein Test beweist:** ob irgendeine Einstellung „richtig aussieht“ oder die Form besser lesbar macht.
Das kann nur Manu im Artist-Test entscheiden. Ebenso wenig beweist der Bench etwas über Manus Hardware:
Er läuft hier auf Software-GL (llvmpipe) und ist nur eine relative Angabe.

## Artist-Test (vorbereitet, ca. 10 Minuten)

Start: `python experiments/viewport_shading_lab/run.py` (Kopf).

1. **F1** („Heute“) drücken. Um den Kopf orbiten, besonders nach hinten. So sieht es heute aus.
2. **F2** („Raitt 2:1“) drücken. Genauso orbiten. Mit **B** gegen „Heute“ vergleichen.
   - **F1:** Im HUD „Bezugsraum“ zwischen Kamera und Welt umschalten. Soll der Key der Kamera folgen oder im Raum stehen bleiben?
3. **F8:** „Verhältnis Key:Fill“ und „Weichheit“ verändern (F2 ↔ F3 vergleichen). Welche Grundeinstellung fühlt sich als Worklight richtig an?
4. **F9:** **F4** („Warm/Kalt“) drücken. Hilft es beim Formlesen, oder stört es?
5. Optional: mit LMB ziehen — das Licht wandert über die Oberfläche. Hilft das, Dellen zu finden?

Antwort je Frage: **KEEP / ITERATE / REJECT / UNKNOWN**. Jede Einstellung, die gefällt, mit **P** aufnehmen.

Der Agent trägt nichts als validiert ein. Verdikte schreibt Manu (oder jemand auf seine ausdrückliche
Anweisung) in die Research, §8.

## Offene Fragen / Beobachtungen

Bemerkt, aber bewusst nicht gebaut:

- **Bezugsraum-Umschaltung springt.** Die Winkel-Zahlen bleiben gleich, die Richtung ändert sich. Alternative: beim
  Umschalten die aktuelle Weltrichtung in Winkel des neuen Bezugsraums umrechnen (kein Sprung). Nicht gebaut; eine
  Frage für F1.
- **Warm/Kalt ist kräftig.** 4500 K Key bei Stärke 0,6 wirkt auf dem grauen Ton deutlich orange (`evidence/f4_warm_kalt.png`).
  Die Werte bleiben unverändert. Ob das zu viel ist, beantwortet F9.
- **Farbige Kanäle über 1.** Eine warme Temperatur hebt Rot über den Mittelwert (z. B. 2500 K: R ≈ 2 × Luminanz). Bei hoher Stärke
  kann Rot deshalb abschneiden, obwohl „Summe Licht“ ≤ 1 zeigt. Die Summe misst die Luminanz, nicht einzelne Kanäle.
- **Kein Gamma / kein Linear-Workflow.** Wie Production rechnet der Shader direkt in Anzeigewerten. Wrap und Verhältnisse
  wirken deshalb anders als in einem physikalisch korrekten Renderer. Ein sRGB-Framebuffer wäre eine eigene Entscheidung.
- **Frame-Zeit im HUD** ist der Abstand zwischen zwei Bildern (vsync-begrenzt), keine reine GPU-Zeit.
- **Research §4.1a** sagt „nie pro Frame“ umrechnen; der Handoff (E5) erlaubt die Umrechnung im Kamera-Modus pro Frame.
  Das Lab rechnet das Rig pro Frame um (nur CPU, ein paar Winkelfunktionen). Die Kosten stehen im Bench.
- **pyglet `dispatch_event()` außerhalb der Event-Loop wird nur eingereiht, nicht ausgeführt.** Tests und `evidence.py`
  rufen deshalb die Handler direkt auf. Ein Test, der `dispatch_event` benutzt, prüft sonst still gar nichts.
- **Licht ziehen und Orbit teilen sich die linke Maustaste** (mit/ohne Alt). Ob das im Alltag kollidiert, ist eine UX-Frage (AD-013).

Nächster Schritt: Artist-Verdikte zu F1/F8/F9. Danach entscheidet sich, ob Slice 2 (Screen-Cavity) oder
Slice 3 (Hintergrund) kommt (Research §7).
