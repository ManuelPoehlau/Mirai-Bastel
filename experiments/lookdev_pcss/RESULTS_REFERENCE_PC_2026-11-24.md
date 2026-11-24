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

## Zweiter Lauf: Kosten-Diagnose (`--set diag`, Commit `9e6d51109a`, gleicher Rechner)

Aufruf:

```powershell
& $py experiments\lookdev_pcss\bench.py --set diag --key-sizes 0.45
& $py experiments\lookdev_pcss\bench.py --set diag --key-sizes 0.45 --size 1920 1080
```

`glGetError` jeweils `0x0000`. Die Bezugszeilen P, K16c und K16c-nb weichen höchstens ±0.1 ms vom ersten Lauf ab,
die Messung ist also reproduzierbar.

### Diagnose 1024 × 768: GPU p50 gegen P (ms; P absolut), Key-Größe 0.45

| Fläche / Ansicht | P | K16c | K16c-nb | K16c-lean | K16c-lean-nb | K8c/8-lean-nb | K16c-nofetch | K16c-nb-nofetch | K16c-search | K16c-pcf | K16c-uall | K16c-unone | K16c-cap12 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cage framed | 4.54 | +2.35 | +0.80 | +1.64 | +1.34 | +1.16 | +2.90 | +1.02 | +0.88 | +1.98 | +2.65 | +1.07 | +2.18 |
| cage face | 12.26 | +6.13 | +4.12 | +4.31 | +4.46 | +2.61 | +7.04 | +5.63 | +1.56 | +4.23 | +5.69 | +5.20 | +5.82 |
| SubD 1 framed | 6.66 | +1.29 | +0.80 | +2.50 | +0.53 | +1.74 | +2.38 | +1.07 | +1.41 | +3.18 | +1.74 | +1.04 | +1.59 |
| SubD 1 face | 15.33 | +3.28 | +3.31 | +6.14 | +4.05 | +3.59 | +7.15 | +4.45 | +2.42 | +6.29 | +3.55 | +4.76 | +3.25 |
| **Mittel** | | **+3.26** | **+2.26** | **+3.65** | **+2.60** | **+2.27** | **+4.87** | **+3.04** | **+1.57** | **+3.92** | **+3.41** | **+3.02** | **+3.21** |

### Diagnose 1920 × 1080: GPU p50 gegen P (ms; P absolut), Key-Größe 0.45

| Fläche / Ansicht | P | K16c | K16c-nb | K16c-lean | K16c-lean-nb | K8c/8-lean-nb | K16c-nofetch | K16c-nb-nofetch | K16c-search | K16c-pcf | K16c-uall | K16c-unone | K16c-cap12 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cage framed | 6.63 | +3.55 | +1.76 | +2.47 | +3.07 | +1.86 | +4.59 | +2.27 | +1.29 | +3.07 | +3.48 | +1.81 | +3.41 |
| cage face | 20.41 | +10.09 | +11.60 | +7.26 | +7.75 | +4.62 | +12.53 | +10.87 | +2.38 | +7.23 | +10.22 | +9.38 | +9.72 |
| SubD 1 framed | 9.51 | +2.06 | +1.12 | +3.67 | +1.13 | +2.63 | +4.09 | +1.69 | +2.05 | +4.82 | +2.66 | +1.15 | +2.04 |
| SubD 1 face | 24.17 | +4.62 | +6.89 | +9.62 | +9.54 | +5.96 | +14.77 | +8.93 | +3.43 | +9.92 | +7.36 | +8.74 | +4.32 |
| **Mittel** | | **+5.08** | **+5.34** | **+5.75** | **+5.37** | **+3.77** | **+8.99** | **+5.94** | **+2.29** | **+6.26** | **+5.93** | **+5.27** | **+4.87** |

### Befund

Ausgewertet nach den vorab festgelegten Regeln der Bewertung §8.3:

1. **`nofetch` ist teurer als K16c,** im Mittel +4.87 gegen +3.26 ms bei 1024 × 768. Ersetzt man jede Abfrage durch
   eine kleine Rechnung (≈ 5 Operationen), steigen die Kosten. Der Haut-Pass ist mit PCSS also **rechengebunden
   (ALU)**, nicht von den Texturabfragen begrenzt. Abfragen sparen hilft nur, wenn die Rechnung pro Abfrage mit
   verschwindet.
2. **Die zwei PCF sind der Hauptteil:**
   - `K16c-pcf` (beide PCF, feste Breite, ohne Suche) kostet +3.92 ms;
   - `K16c-search` (nur die Suche) kostet +1.57 ms.
3. **Texture-Cache ist kein Faktor:** `cap12` liegt bei +3.21, K16c bei +3.26 ms.
4. **Schleifen-Entrollung bringt keine verlässliche Ersparnis:** `uall` +3.41, `unone` +3.02 ms, je nach Block
   verschieden.
5. **Die schlanke Form ist nicht verlässlich billiger.** `lean` liegt bei +3.65 ms, `lean-nb` bei +2.60 ms. Bei
   SubD 1 framed erreicht `lean-nb` +0.53 ms, bei SubD 1 face kostet es +4.05 ms.
6. **Bestwerte je Block bei 1024 × 768:**
   - framed: +0.53 ms (SubD 1, `lean-nb`) und +0.80 ms (Käfig, `nb`);
   - face: +2.61 ms (Käfig, `K8c/8-lean-nb`) und +3.25 ms (SubD 1, `cap12`, praktisch K16c).
7. **Frame-Budget:** Bei 1920 × 1080 reißen `lean`, `lean-nb`, `pcf` und `nofetch` in SubD 1 face die 33.3 ms.

### Folgerung

- Die Schwelle für Weg (a) aus §8.3 ist **nicht erreicht**: Gefordert waren ≤ +0.7 ms framed **und** ≤ +1.5 ms
  face. Die günstigste Form braucht in der Nahansicht +2.6 bis +3.3 ms, das ist das 5- bis 7-Fache des Budgets, und
  K8/8 ist im Bild schwächer.
- Eine Pro-Pixel-PCSS mit Dutzenden Abfragen samt Rechnung passt nicht auf die 9800 GTX, wenn die Haut den Bildschirm
  füllt.
- Ein tragfähiger Weg braucht **wenige Abfragen und wenig Rechnung pro Pixel**. Das ist Weg (b) der Bewertung: die
  Filterarbeit wird in den Karten-Pass verlegt, der nur bei Pose-, Licht- oder Weichheits-Änderung läuft.
