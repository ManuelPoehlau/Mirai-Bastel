# Diffuses Flächenlicht – Referenz-PC-Messung, 2026-11-24

**Evidenz:** **MEASURED [M-RPC]** auf Manus GeForce 9800 GTX. Das sind echte GPU-Zeiten aus `GL_TIME_ELAPSED`, nicht die llvmpipe-Zeiten des Container-Laufs.

## Messumgebung

| Feld | Wert |
|---|---|
| Datum | 2026-11-24 |
| Commit | `8347c42619` |
| Working tree | `MODIFIED` (Experiment-Ausgabe); gemessener `src/`-Tree: `c51b82c960` |
| Betriebssystem | Windows 10.0.19045 |
| CPU | Intel Core 2 Quad Q9550 @ 2.83 GHz, 4 logische Kerne |
| GPU | NVIDIA GeForce 9800 GTX / 9800 GTX+ |
| OpenGL | 3.3.0 |
| Python | CPython 3.12.10 |
| Auflösungen | 1024 × 768 und 1920 × 1080 |
| Messung | 20 Runden × 3 Frames je Variante, verschachtelt; nach 5 Warm-up-Frames |
| Key-Größe | 0.5 |
| Effekte | Schatten, Augen-Schatten, Doppel-Glanz, Durchleuchtung, Environment-Cube |
| Ziel | GPU-Zeit je Frame; Referenzbudget 33.3 ms für 30 FPS |

Aufruf:

```powershell
.venv312\Scripts\python.exe experiments\lookdev_diffuse_area\bench.py
python.exe experiments\lookdev_diffuse_area\bench.py --size 1920 1080
```

Der erste Versuch für 1920 × 1080 hatte einen fehlenden Abstand zwischen `bench.py` und `--size`; dieser Aufruf wurde korrigiert und der unten dokumentierte Lauf erfolgreich ausgeführt.

## 1024 × 768

Alle Zeitangaben in ms. `Δ vs A` ist die gemessene Differenz der jeweiligen Variante zur Produktions-Baseline A.

### Cage, framed – 5,469 Dreiecke

| Variante | GPU p50 | GPU min | GPU max | CPU p50 | Δ vs A |
|---|---:|---:|---:|---:|---:|
| A | 4.539 | 4.408 | 4.672 | 13.45 | +0.000 |
| B | 4.696 | 4.566 | 4.785 | 13.58 | +0.157 |
| B2 | 6.188 | 6.050 | 6.339 | 16.46 | +1.649 |
| C8 | 6.459 | 5.049 | 6.857 | 15.02 | +1.920 |
| C16 | 6.638 | 6.548 | 8.003 | 17.16 | +2.099 |
| Ax16 | 5.316 | 5.201 | 5.532 | 14.31 | +0.777 |
| Bx16 | 7.375 | 7.274 | 7.481 | 16.56 | +2.836 |

B-eigener Aufwand aus den 16-fach-Zeilen: `(Bx16 − Ax16) / 16 = 0.129 ms` je Frame (vier Auswertungen pro Pixel: drei Lichter plus Key-Term im Schattenblock). B belegt 14.1 % des 33.3-ms-Budgets.

### Cage, face – 5,469 Dreiecke

| Variante | GPU p50 | GPU min | GPU max | CPU p50 | Δ vs A |
|---|---:|---:|---:|---:|---:|
| A | 11.990 | 11.879 | 12.208 | 21.75 | +0.000 |
| B | 12.388 | 12.206 | 12.511 | 22.54 | +0.398 |
| B2 | 16.192 | 15.971 | 16.363 | 26.66 | +4.202 |
| C8 | 17.673 | 16.625 | 17.958 | 28.92 | +5.683 |
| C16 | 19.788 | 19.637 | 19.923 | 29.54 | +7.798 |
| Ax16 | 16.039 | 15.876 | 16.239 | 25.80 | +4.049 |
| Bx16 | 21.964 | 21.804 | 22.151 | 32.57 | +9.974 |

B-eigener Aufwand: `(Bx16 − Ax16) / 16 = 0.370 ms` je Frame. B belegt 37.2 % des 33.3-ms-Budgets.

### SubD 1, framed – 22,153 Dreiecke

| Variante | GPU p50 | GPU min | GPU max | CPU p50 | Δ vs A |
|---|---:|---:|---:|---:|---:|
| A | 6.695 | 6.508 | 6.846 | 17.37 | +0.000 |
| B | 6.858 | 6.708 | 7.025 | 17.46 | +0.163 |
| B2 | 9.190 | 9.000 | 9.384 | 20.29 | +2.495 |
| C8 | 7.638 | 7.072 | 9.713 | 18.59 | +0.943 |
| C16 | 9.497 | 9.310 | 9.944 | 19.75 | +2.802 |
| Ax16 | 7.423 | 7.318 | 7.579 | 17.92 | +0.727 |
| Bx16 | 10.584 | 10.452 | 10.666 | 21.30 | +3.889 |

B-eigener Aufwand: `(Bx16 − Ax16) / 16 = 0.198 ms` je Frame. B belegt 20.6 % des 33.3-ms-Budgets.

### SubD 1, face – 22,153 Dreiecke

| Variante | GPU p50 | GPU min | GPU max | CPU p50 | Δ vs A |
|---|---:|---:|---:|---:|---:|
| A | 15.258 | 15.008 | 15.568 | 25.56 | +0.000 |
| B | 15.741 | 15.608 | 16.064 | 26.37 | +0.483 |
| B2 | 20.817 | 20.529 | 21.052 | 31.46 | +5.559 |
| C8 | 20.676 | 17.907 | 22.639 | 30.68 | +5.418 |
| C16 | 23.291 | 22.945 | 24.834 | 33.82 | +8.032 |
| Ax16 | 18.558 | 18.376 | 18.856 | 28.59 | +3.299 |
| Bx16 | 25.726 | 25.551 | 25.889 | 35.84 | +10.467 |

B-eigener Aufwand: `(Bx16 − Ax16) / 16 = 0.448 ms` je Frame. B belegt 47.2 % des 33.3-ms-Budgets.

## 1920 × 1080

### Cage, framed – 5,469 Dreiecke

| Variante | GPU p50 | GPU min | GPU max | CPU p50 | Δ vs A |
|---|---:|---:|---:|---:|---:|
| A | 6.602 | 6.521 | 6.746 | 16.73 | +0.000 |
| B | 6.838 | 6.693 | 6.937 | 15.84 | +0.236 |
| B2 | 9.316 | 9.170 | 9.468 | 19.05 | +2.714 |
| C8 | 8.067 | 7.975 | 10.006 | 17.13 | +1.465 |
| C16 | 10.531 | 10.427 | 10.598 | 19.83 | +3.929 |
| Ax16 | 8.327 | 8.209 | 8.417 | 18.47 | +1.725 |
| Bx16 | 11.759 | 11.656 | 11.869 | 22.28 | +5.157 |

B-eigener Aufwand: `(Bx16 − Ax16) / 16 = 0.215 ms` je Frame. B belegt 20.5 % des 33.3-ms-Budgets.

### Cage, face – 5,469 Dreiecke

| Variante | GPU p50 | GPU min | GPU max | CPU p50 | Δ vs A |
|---|---:|---:|---:|---:|---:|
| A | 19.822 | 19.623 | 20.004 | 30.38 | +0.000 |
| B | 20.627 | 20.394 | 20.894 | 30.37 | +0.805 |
| B2 | 27.307 | 27.125 | 27.576 | 37.15 | +7.485 |
| C8 | 30.228 | 27.100 | 30.506 | 40.24 | +10.406 |
| C16 | 36.751 | 34.646 | 39.193 | 46.99 | +16.929 |
| Ax16 | 27.892 | 27.710 | 28.108 | 38.19 | +8.070 |
| Bx16 | 38.428 | 38.266 | 38.707 | 49.00 | +18.606 |

B-eigener Aufwand: `(Bx16 − Ax16) / 16 = 0.659 ms` je Frame. B belegt 61.9 % des 33.3-ms-Budgets.

### SubD 1, framed – 22,153 Dreiecke

| Variante | GPU p50 | GPU min | GPU max | CPU p50 | Δ vs A |
|---|---:|---:|---:|---:|---:|
| A | 9.528 | 9.319 | 9.646 | 19.95 | +0.000 |
| B | 9.853 | 9.673 | 10.219 | 20.37 | +0.325 |
| B2 | 13.455 | 13.289 | 13.676 | 24.37 | +3.928 |
| C8 | 10.978 | 10.264 | 14.485 | 22.48 | +1.450 |
| C16 | 13.658 | 13.563 | 13.784 | 25.31 | +4.130 |
| Ax16 | 10.700 | 10.586 | 10.790 | 20.87 | +1.172 |
| Bx16 | 15.393 | 15.292 | 15.502 | 26.29 | +5.865 |

B-eigener Aufwand: `(Bx16 − Ax16) / 16 = 0.293 ms` je Frame. B belegt 29.6 % des 33.3-ms-Budgets.

### SubD 1, face – 22,153 Dreiecke

| Variante | GPU p50 | GPU min | GPU max | CPU p50 | Δ vs A |
|---|---:|---:|---:|---:|---:|
| A | 23.916 | 23.670 | 24.192 | 34.16 | +0.000 |
| B | 24.753 | 24.433 | 25.047 | 35.30 | +0.837 |
| B2 | 33.179 | 32.836 | 33.517 | 44.12 | +9.263 |
| C8 | 30.116 | 29.913 | 30.329 | 41.13 | +6.200 |
| C16 | 39.026 | 38.731 | 39.247 | 49.11 | +15.110 |
| Ax16 | 31.118 | 30.844 | 31.358 | 41.62 | +7.202 |
| Bx16 | 43.536 | 43.321 | 43.859 | 53.72 | +19.620 |

B-eigener Aufwand: `(Bx16 − Ax16) / 16 = 0.776 ms` je Frame. B belegt 74.3 % des 33.3-ms-Budgets.

## Zusammenfassung und Lesart

| Auflösung | Oberfläche / Ansicht | B eigener Aufwand (x16-Differenz) | B GPU p50 | Anteil 33.3 ms |
|---|---|---:|---:|---:|
| 1024 × 768 | Cage, framed | 0.129 ms | 4.696 ms | 14.1 % |
| 1024 × 768 | Cage, face | 0.370 ms | 12.388 ms | 37.2 % |
| 1024 × 768 | SubD 1, framed | 0.198 ms | 6.858 ms | 20.6 % |
| 1024 × 768 | SubD 1, face | 0.448 ms | 15.741 ms | 47.2 % |
| 1920 × 1080 | Cage, framed | 0.215 ms | 6.838 ms | 20.5 % |
| 1920 × 1080 | Cage, face | 0.659 ms | 20.627 ms | 61.9 % |
| 1920 × 1080 | SubD 1, framed | 0.293 ms | 9.853 ms | 29.6 % |
| 1920 × 1080 | SubD 1, face | 0.776 ms | 24.753 ms | 74.3 % |

- Die Messung bestätigt, dass B auf der tatsächlichen 9800 GTX sehr günstig ist: bei 1024 × 768 liegt sein isolierter Aufwand zwischen 0.129 und 0.448 ms je Frame.
- Die zuvor geschätzten 0.09–0.35 ms für 1024 × 768 lagen in der richtigen Größenordnung, unterschätzten aber besonders die SubD-Gesichts-Nahaufnahme (gemessen 0.448 ms).
- Bei 1920 × 1080 steigt der isolierte Aufwand auf 0.215–0.776 ms. Auch die SubD-Gesichts-Nahaufnahme bleibt mit B bei 24.753 ms GPU p50 unter dem 33.3-ms-Budget; die Reserve ist jedoch geringer.
- B2 und C16 kosten in allen Fällen deutlich mehr. Bei 1920 × 1080 überschreitet C16 in der SubD-Gesichts-Nahaufnahme das 30-FPS-GPU-Budget (39.026 ms); B bleibt darunter.
- Für die Einordnung des reinen B-Aufwands ist die 16-fach-Differenz `(Bx16 − Ax16) / 16` aussagekräftiger als die einzelne Differenz B − A, weil die zusätzliche Arbeit gegenüber dem Frame-Messrauschen verstärkt wird. Beide Werte sind deshalb getrennt dokumentiert.
- `glGetError` am Ende beider Läufe: `0x0000`.

**Fazit:** B ist auf der Referenzhardware performant genug, um als P3-Kandidat weiterverfolgt zu werden. Die Messung ersetzt die frühere reine Schätzung. Sie ist noch keine Freigabe der visuellen Integration; die offenen Schatten-/Wrap-Risiken aus dem Assessment bleiben bestehen.
