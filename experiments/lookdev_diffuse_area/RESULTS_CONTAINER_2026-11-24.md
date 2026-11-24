# Diffuses Flächenlicht - Container-Lauf, 2026-11-24

**Evidenz:** **TESTED [C]** = Container, Software-Renderer (llvmpipe). Die *Bilder* und Bildvergleiche sind gültig
(derselbe Shader-Text wie auf jeder GPU, float32, gleiche Szene); die *Zeiten* sind keine GPU-Zeiten und sagen nichts
über die GeForce 9800 GTX. Referenz-PC: **OPEN** (Befehle: [README.md](README.md)).

## Lauf

| Feld | Wert |
|---|---|
| Maschine, Datum | Container (Claude-Code-Sitzung), 2026-11-24 |
| Commit | `8f605ef1ce` (main; `src/` unverändert, die Experiment-Dateien noch nicht eingecheckt - die Quelle meldet „clean“, weil sie nur verfolgte Dateien prüft) |
| Python, numpy, pyglet | 3.13.18, 2.2.6, 2.1.19 |
| GL | 4.5 Core, Mesa 25.2.8, `llvmpipe (LLVM 20.1.2, 256 bits)` - **SOFTWARE RENDERER** |
| Szene | `scenes/Gollum_Head_05.mirai.json` (nur gelesen), SubD 1 (22 153 Dreiecke), Augen ausgeblendet, Käfiglinien nicht gezeichnet (nur im Prozess); Formen-Szene erzeugt (Kugel r 1, Zylinder r 0.7, Platte mit Schale 0.41 tief und Rinne 0.26 tief) |
| Licht | Studio „Dramatic“, Key Azimut 70° / Elevation 20°, Rim aus, Fill-Größe 0; Belichtung 0, Reinhard; Effekte Schatten + Doppel-Glanz; Material Neutral (Wrap 0) und Creature Skin (Wrap 0.3 × (1, 0.65, 0.5)), Albedo „Farbe“ |
| Vergleich | diffus allein (Glanz × 0), linear erfasst, Tonkurve in NumPy (`lookdev_optics.lookdev_output`); REF = 32 harte Key-Richtungen auf der Kappe (Vogel-Spirale), Key-Farbe × 2 / (1 + cos σ), gemittelt |
| Abbildung | sin σ = Größe × sin 40° (σ = 0 / 9.2 / 18.7 / 40.0° bei 0 / 0.25 / 0.5 / 1) |

Laufzeit: der ganze Vergleich (2 Szenen, 3 Ansichten, 2 Materialien, 4 Größen, 5 Varianten + 3 Beauty + REF) ≈ 100 s.

## Modelle gegen die dichte Referenz (`curves.py`, max / RMS über n·l ∈ [−1, 1])

| Größe | σ | Wrap | A (heute) | A' Wrap+Größe | **B** Spline | B2 exakt | C8 | C16 | Kugel heller (B) |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 | 9.2° | 0 | 0.034 / 0.006 | 0.121 / 0.058 | **0.006 / 0.0015** | 0.000 | 0.009 / 0.004 | 0.003 / 0.001 | +0.9 % |
| 0.5 | 18.7° | 0 | 0.070 / 0.017 | 0.191 / 0.103 | **0.010 / 0.004** | 0.000 | 0.019 / 0.009 | 0.007 / 0.003 | +3.4 % |
| 1 | 40.0° | 0 | 0.158 / 0.056 | 0.241 / 0.156 | **0.003 / 0.002** | 0.000 | 0.041 / 0.022 | 0.015 / 0.008 | +13.8 % |
| 1 | 40.0° | 0.3 | 0.117 / 0.041 | 0.223 / 0.155 | **0.013 / 0.006** | 0.011 / 0.005 | 0.033 / 0.020 | 0.011 / 0.007 | +13.8 % |

## Formen (Neutral; MAE in 1/255 gegen REF; „neu+“ = Anteil Pixel > 8/255 heller als REF, die es in A nicht sind)

| Größe | Variante | Kugel | Zylinder | Schale MAE / neu+ | Rinne MAE / neu+ / p99 heller |
|---|---|---|---|---|---|
| 0.5 | A | 4.9 | 2.5 | 6.2 / – | 6.6 / – / 17 |
| 0.5 | B | 3.3 | 0.5 | 7.2 / 6.5 % | 5.2 / 5.0 % / 23 |
| 0.5 | C16 | 3.1 | 0.4 | 7.0 / 5.4 % | 5.4 / 4.0 % / 21 |
| 0.5 | B-split | 3.2 | 0.5 | 6.2 / 0.8 % | 5.5 / 0.5 % / 18 |
| 1 | A | 11.4 | 9.7 | 13.6 / – | 12.5 / – / 18 |
| 1 | B | 4.6 | 0.8 | 8.1 / 11.3 % | 5.1 / 6.5 % / 40 |
| 1 | C16 | 4.9 | 1.3 | 7.9 / 11.0 % | 5.2 / 7.2 % / 40 |
| 1 | B-split | 4.7 | 1.1 | 9.2 / 0.4 % | 5.6 / 2.7 % / 19 |

Die Kugel-Fehler aller Varianten (auch A) kommen zum Teil vom Silhouettenrand der REF-Bilder (Schattenkarte der
einzelnen Richtungen); der Zylinder ist sauber. Der Schlagschatten der Schalenkante ist in REF viel weicher als in
jeder Variante: das ist die Schattenkarte (Halbschatten über die effektive Auflösung), nicht der diffuse Term.

## Gollum, Ansicht „face“ (MAE in 1/255 gegen REF; neu+ wie oben; p99 = 99. Perzentil „heller als REF“)

Neutral (Wrap 0, REF = Physik):

| Größe | Variante | Schattenwange | Nase MAE / neu+ / p99 | Mundwinkel l MAE / neu+ | Augenhöhle l |
|---|---|---|---|---|---|
| 0.5 | A | 5.4 | 2.2 / – / 12 | 0.7 / – | 8.9 |
| 0.5 | **B** | 3.2 | 3.6 / 16.8 % / 20 | 0.7 / 2.2 % | 4.4 |
| 0.5 | B2 | 2.4 | 2.9 / 13.1 % / 19 | 0.4 / 1.6 % | 3.5 |
| 0.5 | C16 | 2.4 | 3.1 / 13.5 % / 19 | 0.5 / 1.8 % | 3.7 |
| 0.5 | B-split | 4.9 | 1.4 / 0.1 % / 13 | 0.1 / 0 | 3.8 |
| 0.5 | B-liftmid | 2.6 | 1.9 / 4.3 % / 19 | 0.3 / 0.1 % | 4.3 |
| 1 | A | 19.9 | 10.8 / – / 13 | 8.0 / – | 18.8 |
| 1 | **B** | 2.7 | 5.1 / 16.2 % / 30 | 2.4 / 6.8 % | 4.3 |
| 1 | B2 | 2.5 | 5.0 / 15.5 % / 30 | 2.3 / 6.3 % | 4.1 |
| 1 | C16 | 2.8 | 5.1 / 15.6 % / 30 | 2.5 / 6.3 % | 4.6 |
| 1 | B-split | 14.3 | 5.7 / 0.8 % / 16 | 4.0 / 0 | 4.7 |
| 1 | B-liftmid | 4.4 | 4.3 / 6.7 % / 22 | 2.1 / 0.4 % | 4.2 |
| 1 | B-liftfull | 9.6 | 4.8 / 2.0 % / 17 | 3.2 / 0 | 4.2 |

Creature Skin (Wrap 0.3; REF erbt Productions Wrap-Regel bei Größe 0 - „liftfull“ trifft REF dort teils per
Konstruktion):

| Größe | Variante | Schattenwange | Nase MAE / neu+ / p99 | Mundwinkel l MAE / neu+ | Augenhöhle l |
|---|---|---|---|---|---|
| 0.25 | A | 5.8 | 3.0 / – / **34** | 0.5 / – | 3.8 |
| 0.25 | B | 6.0 | 2.9 / 0.2 % / 34 | 0.2 / 0.2 % | 3.5 |
| 0.25 | A-liftfull | 3.0 | 1.0 / 0.1 % / 9 | 0.4 / 0 | 3.0 |
| 0.5 | A | 7.9 | 8.2 / – / **40** | 3.1 / – | 5.5 |
| 0.5 | B | 7.5 | 8.3 / 3.0 % / 41 | 2.5 / 3.5 % | 4.0 |
| 0.5 | B-split | 7.6 | 7.6 / 0.3 % / 40 | 1.8 / 0 | 3.7 |
| 1 | A | 13.7 | 7.7 / – / 33 | 13.2 / – | 11.0 |
| 1 | B | 2.9 | 6.2 / 12.5 % / 37 | 3.5 / 8.5 % | 4.4 |
| 1 | B-split | 10.4 | 5.2 / 2.6 % / 34 | 7.9 / 0.2 % | 4.7 |
| 1 | B-liftmid | 6.2 | 5.1 / 3.4 % / 29 | 4.0 / 0.3 % | 4.4 |

Die fett gesetzten p99-Werte von **A** sind der vorhandene Befund (Assessment §6.3): mit Wrap glüht die Innenwand des
linken Nasenlochs ab Größe 0.25, weil der gehobene Lookup (AD-039 §16.7) mit der effektiven Texelgröße wächst.

Bilder (verkleinert): [`docs/research/lookdev_diffuse_area_assets_2026-11-24/`](../../docs/research/lookdev_diffuse_area_assets_2026-11-24/).
B-liftmid zeigt bei 0.5 / 1 streifige Flecken auf der Wange neben der Nase (Bild `gollum_nose_creatureskin_liftmid.png`):
der §16.6-Fehler kommt zurück, sobald der Lift kleiner als die effektive Texelgröße verlangt wird.

## Bench (`bench.py --rounds 3 --frames 2`, 1024 × 768) - nur Funktionsprüfung

Alle Varianten kompilieren unter GL 3.3 core, zeichnen und lassen keinen GL-Fehler zurück (`glGetError` 0). Die
GL_TIME_ELAPSED-Werte von llvmpipe streuen um ganze Millisekunden (A selbst: min 0.06, max 7.4 ms) und messen die CPU;
sie sind hier **nicht** ausgewertet. Die Abschätzung für die 9800 GTX steht im Assessment §5.
