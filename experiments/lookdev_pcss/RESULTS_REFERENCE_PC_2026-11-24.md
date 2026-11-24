# PCSS des Key – Referenz-PC-Messung, 2026-11-24

**Evidenz:** **MEASURED [M-RPC]** auf Manus GeForce 9800 GTX: echte GPU-Zeiten aus `GL_TIME_ELAPSED`, nicht die
llvmpipe-Zeiten des Containers. Bewertung:
[LOOKDEV_PCSS_KEY_SHADOW_ASSESSMENT_2026-11-24](../../docs/research/LOOKDEV_PCSS_KEY_SHADOW_ASSESSMENT_2026-11-24.md) §8.

## Messumgebung

| Feld | Wert |
|---|---|
| Datum | 2026-11-24 |
| Commit | `dd9505fba0` |
| Working tree | `MODIFIED` (Experiment-Ausgabe); gemessener `src/`-Tree: `2d2589adb9` |
| Betriebssystem | Windows 10.0.19045 |
| CPU | Intel Core 2 Quad Q9550 @ 2.83 GHz, 4 logische Kerne |
| GPU | GeForce 9800 GTX / 9800 GTX+, OpenGL 3.3.0 |
| Python | CPython 3.12.10 |
| Auflösungen | 1024 × 768 und 1920 × 1080 |
| Messung | 20 Runden × 3 Frames je Variante, verschachtelt, nach 5 Warm-up-Runden; Median |
| Key-Größen | 0.45 und 1 |
| Effekte | Schatten, Augen-Schatten, Doppel-Glanz, Durchleuchtung, Environment-Cube, „Weiches Licht“ |
| Budget | AD-039 §2.5: pro Effekt ≤ +0.5 ms bei 1024 × 768; Frame ≤ 33.3 ms |

Aufruf:

```powershell
& $py experiments\lookdev_pcss\bench.py
& $py experiments\lookdev_pcss\bench.py --size 1920 1080
```

`glGetError` am Ende jeweils `0x0000`. Die vollständige Ausgabe steht in Manus Nachricht vom 2026-11-24; die Tabellen
unten enthalten jede gemessene Median-Zeile.

### 1024 × 768: GPU p50 gegen P (ms; P absolut)

| Fläche / Ansicht / Key-Größe | P | F | K8c/16 | K16c | K24c/16 | K16c/32 | K16c/9g | K16c-nb | K16c-eff |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cage framed 0.45 | 4.55 | +0.03 | +1.75 | +2.33 | +2.84 | +1.47 | +1.84 | +0.81 | +2.15 |
| cage framed 1 | 4.53 | +0.05 | +1.78 | +2.45 | +2.88 | +1.22 | +1.88 | +0.83 | +2.12 |
| cage face 0.45 | 12.25 | +0.03 | +4.83 | +6.10 | +5.93 | +6.57 | +4.70 | +4.89 | +5.65 |
| cage face 1 | 12.25 | +0.00 | +4.87 | +6.10 | +6.05 | +6.27 | +4.83 | +3.81 | +5.70 |
| SubD 1 framed 0.45 | 6.65 | +0.05 | +2.41 | +1.38 | +1.95 | +1.46 | +1.89 | +0.77 | +2.41 |
| SubD 1 framed 1 | 6.65 | +0.04 | +2.45 | +1.39 | +2.08 | +1.22 | +2.13 | +0.81 | +2.36 |
| SubD 1 face 0.45 | 15.33 | +0.05 | +4.65 | +3.03 | +3.18 | +4.82 | +4.04 | +3.20 | +5.25 |
| SubD 1 face 1 | 15.30 | +0.06 | +5.18 | +2.46 | +3.31 | +4.96 | +4.21 | +3.28 | +3.56 |
| **Mittel** | | **+0.04** | **+3.49** | **+3.16** | **+3.53** | **+3.50** | **+3.19** | **+2.30** | **+3.65** |

### 1920 × 1080: GPU p50 gegen P (ms; P absolut)

| Fläche / Ansicht / Key-Größe | P | F | K8c/16 | K16c | K24c/16 | K16c/32 | K16c/9g | K16c-nb | K16c-eff |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cage framed 0.45 | 6.62 | +0.05 | +2.65 | +3.53 | +4.40 | +2.93 | +2.85 | +1.78 | +3.24 |
| cage framed 1 | 6.62 | +0.06 | +2.68 | +3.62 | +4.52 | +3.04 | +2.88 | +1.78 | +3.15 |
| cage face 0.45 | 20.41 | +0.02 | +7.88 | +10.15 | +11.22 | +11.66 | +8.01 | +11.56 | +9.39 |
| cage face 1 | 20.41 | +0.02 | +8.00 | +10.23 | +12.27 | +11.96 | +8.09 | +11.69 | +9.46 |
| SubD 1 framed 0.45 | 9.49 | +0.07 | +3.54 | +1.95 | +2.71 | +1.65 | +3.40 | +1.13 | +3.49 |
| SubD 1 framed 1 | 9.49 | +0.08 | +3.62 | +2.22 | +1.99 | +1.59 | +3.18 | +1.16 | +3.13 |
| SubD 1 face 0.45 | 24.18 | +0.01 | +6.62 | +4.64 | +6.64 | +8.96 | +3.03 | +6.89 | +4.11 |
| SubD 1 face 1 | 24.16 | +0.06 | +2.90 | +4.72 | +6.70 | +9.12 | +3.10 | +6.95 | +4.25 |
| **Mittel** | | **+0.04** | **+4.74** | **+5.13** | **+6.31** | **+6.36** | **+4.32** | **+5.37** | **+5.03** |

## Befund

1. **Das Budget ist deutlich verfehlt.** Die empfohlene Variante K16c kostet bei 1024 × 768 zwischen +1.38 ms
   (SubD 1, framed) und +6.10 ms (Käfig, face), im Mittel +3.16 ms. Erlaubt sind ≤ +0.5 ms, also das 3- bis
   12-Fache. Bei 1920 × 1080 sind es im Mittel +5.13 ms. Der ganze Frame liegt dann bei bis zu 30.6 ms (Käfig, face)
   bzw. 28.9 ms (SubD 1, face), knapp unter 33.3 ms.
2. **Die Kosten folgen nicht der Zahl der Abfragen.**
   - Die Mittel liegen alle bei +3.2 bis +3.5 ms: 8, 16 oder 24 Such-Abfragen; 16 oder 32 PCF-Abfragen; 3 × 3-Gitter.
   - Einzelne Blöcke sind sogar umgekehrt: K8c/16 ist bei SubD 1 teurer als K16c (+2.41 gegen +1.38), und K16c/32
     ist im Käfig-framed-Fall billiger als K16c.
   - Das spricht gegen Texturabfragen als Hauptkosten und für feste Kosten pro Hautpixel: Registerdruck und damit
     geringere Auslastung des ganzen Haut-Shaders, Code-Größe oder Verzweigung [E].
3. **Der Frühabbruch kostet mehr, als er spart.**
   - Ohne ihn (K16c-nb) ist es im Mittel bei 1024 × 768 billiger: +2.30 ms gegen +3.16 ms.
   - Framed sind es +0.77 bis +0.83 ms, das ist die günstigste gemessene Zeile.
   - Bei 1080p im Käfig-face-Fall ist es dagegen teurer.
   - Die Verzweigung divergiert auf der G92 offenbar stark.
4. **Volle Auflösung kostet nichts.** F ist bei +0.00 bis +0.08 ms. Der Tiefen-Pass bei 1024² und der Lookup
   ohne skalierte Karte sind kein Kostenfaktor.
5. **Effektive Auflösung spart nichts** (K16c-eff +3.65 ms) und ist im Bild schlechter.
6. **Ansicht face ist der teure Fall.** Die Haut füllt den Bildschirm, und die Kosten wachsen mit den Hautpixeln.
   Im Käfig ist es teurer als SubD 1 (+6.1 gegen +3.0 ms bei gleicher Fläche): Auf den groben Facetten liegen mehr
   Pixel im Bereich, in dem Blocker gefunden werden.

## Folgerung

K16c wird so **nicht** eingebaut. Nächster Lauf: die Kosten-Diagnose `bench.py --set diag`, in der Bewertung §8.3
beschrieben. Sie trennt Shader-Größe, Suche, PCF, Schleifen-Entrollung und Texture-Cache und misst die schlanke Form
(gleiches Bild).
