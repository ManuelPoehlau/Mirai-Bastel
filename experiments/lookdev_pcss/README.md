# LookDev: Halbschatten des Key abhängig vom Abstand (PCSS), 2026-11-24

**Status:** isoliertes Wegwerf-Experiment, keine Production-Spezifikation. Es gilt für AD-039 §23.6 / Q-S8-3, Manus
Befund „der Übergang von Nase zur Wange links wirkt bei weichem Licht seltsam/unrealistisch“.

**Kein Eingriff in `src/`, `tests/`, `config/` oder Szenen.** Die Varianten werden nur *im eigenen Prozess*
eingesetzt (`pcss_glsl.install`):
- Die beiden Schatten-Abfragen des `SHADOW`-Blocks im Haut-Fragment-Shader werden ersetzt.
- Die Karte bleibt auf Wunsch in voller Auflösung (`lookdev_optics.shadow_resolution`).
- Die Rohtiefe (Einheit 7) wird für jeden Haut-Draw mit Schatten gebunden.

Augen-Shader, `LD_COMMON_SRC` und `LD_SHADOW_SRC` bleiben unberührt.

**Bewertung und Empfehlung:**
[`docs/research/LOOKDEV_PCSS_KEY_SHADOW_ASSESSMENT_2026-11-24.md`](../../docs/research/LOOKDEV_PCSS_KEY_SHADOW_ASSESSMENT_2026-11-24.md).
Der Container-Lauf liefert Bilder und Funktionsprüfung mit llvmpipe, aber **keine** 9800-GTX-Messung.
**Referenz-PC gemessen (2026-11-24):** [`RESULTS_REFERENCE_PC_2026-11-24.md`](RESULTS_REFERENCE_PC_2026-11-24.md).
K16c verfehlt das Budget um das 3- bis 12-Fache, und die Kosten folgen nicht der Zahl der Abfragen. Offen ist der
Diagnose-Lauf `--set diag` (unten).

## Frage

Ein weicher Key (S8 „Weiches Licht“) macht den Terminator weich. Der Schlagschatten hat aber nur den festen
Halbschatten der Karte, etwa 3 Texel der effektiven Auflösung, unabhängig vom Abstand zum Werfer. Lässt sich ein
Halbschatten bauen, der mit dem Abstand Empfänger → Werfer und mit σ wächst? Dafür kommen Blocker-Suche und PCF mit
variablem Radius in Frage. Kontaktschatten sollen scharf bleiben, und die Lecks aus §16.6/§16.7 dürfen nicht
zurückkommen. Was kostet das auf dem Referenz-PC?

## Dateien

| Datei | Was |
|---|---|
| `pcss_glsl.py` | `Pcss`-Variante (Abfragen, Muster, Auflösung, Suchtest, PCF-Vergleich, Lift, …) und `patch_shadow`: Jede Ersetzung prüft ihren Anker im aktuellen Production-Text. `install(area, pcss)` / `uninstall()` |
| `compare.py` | Bilder durch den echten LookDev-Pass, immer mit „Weiches Licht“ an (`--no-area` aus). REF ist das Mittel aus 32 harten Keys über die Lichtscheibe (σ wie S8). Szenen und Ansichten: Gollum „manu“ (Manus Einstellung §23.6), „face“, „framed“ sowie die Formen-Szene. Materialien: Neutral und „Creature Skin*“ (Manus angepasste Werte). Kennzahlen in `metrics.json`, Sheets, Frames. Namen der Varianten in `VARIANTS`; die Empfehlung ist `K16c` |
| `analyze.py` | Kennzahlen pro Region (Nase → Wange, Nasenloch, Mundwinkel, Schattenwange; Formen: Kugel, Schale, Rinne). Dazu `new+`/`new-`: Pixel, die nur in der Variante, nicht in Production, heller oder dunkler als REF sind (Leck oder neuer Fleck) |
| `bench.py` | GPU-Zeit der Varianten im echten LookDev-Frame, für den Referenz-PC |
| `debug_vis.py` | Diagnosebilder: Haut = (vis, vis_wrap, n·l > 0) |
| `zoom.py`, `figures.py` | Ausschnitte; die Abbildungen der Bewertung |
| `tests/` | kopflos: Jeder Anker wird in allen Effekt-Kombinationen mit Schatten gefunden, ohne Schatten ändert sich nichts, `install`/`uninstall` stellen Production wieder her |
| `out*/` | gitignored: Bilder und Zahlen. Ausgewählte Abbildungen liegen in `docs/research/lookdev_pcss_assets_2026-11-24/` |

## Befehle (Container)

```bash
python -m pytest experiments/lookdev_pcss/tests -q
```

```bash
xvfb-run -a python experiments/lookdev_pcss/compare.py --out experiments/lookdev_pcss/out
```

```bash
python experiments/lookdev_pcss/analyze.py experiments/lookdev_pcss/out
```

```bash
xvfb-run -a python experiments/lookdev_pcss/compare.py --scene gollum --views face,manu --materials "Creature Skin*" --variants P,F,K16c --eyes --out experiments/lookdev_pcss/out_eyes
```

```bash
xvfb-run -a python experiments/lookdev_pcss/compare.py --no-area --spec --variants P,F,K16c,K8c/16 --sizes 0.25,0.45,1 --out experiments/lookdev_pcss/out_noarea
```

```bash
xvfb-run -a python experiments/lookdev_pcss/bench.py --rounds 1 --frames 1
```

Der letzte Befehl ist nur eine Funktionsprüfung.

## Befehle (Referenz-PC, PowerShell, Repo-Wurzel, `.venv312`)

Vorher: NVIDIA-Systemsteuerung → „3D-Einstellungen verwalten“ → Globale Einstellungen → Energieverwaltungsmodus
„Maximale Leistung bevorzugen“ (REFERENCE_HARDWARE §2).

```powershell
$py = (Resolve-Path .\.venv312\Scripts\python.exe).Path; git rev-parse --short=10 HEAD; git status --short
```

```powershell
& $py experiments\lookdev_pcss\bench.py
```

```powershell
& $py experiments\lookdev_pcss\bench.py --size 1920 1080
```

Erster Lauf (erledigt, Ergebnis in `RESULTS_REFERENCE_PC_2026-11-24.md`). Er dauert ungefähr 5 bis 10 Minuten je Auflösung: Käfig und SubD 1, „framed“ und „face“, Key-Größe 0.45 und 1,
9 Zeilen. Entscheidend sind die Zeilen `K16c`, `K8c/16` und `K16c/9g` gegen `P`, jeweils je Fläche, Ansicht und
Key-Größe. Das Budget ist AD-039 §2.5: pro Effekt ≤ +0.5 ms bei 1024 × 768.

Diagnose-Lauf (offen; Bewertung §8.3). 13 Zeilen, Key-Größe 0.45, wenige Minuten je Auflösung:

```powershell
& $py experiments\lookdev_pcss\bench.py --set diag --key-sizes 0.45
```

```powershell
& $py experiments\lookdev_pcss\bench.py --set diag --key-sizes 0.45 --size 1920 1080
```

## Grenzen

- REF ist für Neutral die physikalische Wahrheit einer Kugel-Lichtquelle mit echten weichen Schatten, bis auf die
  32 Richtungen und die Karte bei Größe 0. Für Creature Skin* erbt REF die Wrap-Regel von Production bei Größe 0
  (gehobene Abfrage, volle Auflösung). Dort ist REF ein Ziel, keine Physik.
- llvmpipe-Zeiten sind keine GPU-Zeiten. Die Bildvergleiche hängen davon nicht ab (gleicher Shader-Text, float32).
- Ohne „Weiches Licht“ und ohne Glanz kürzt der Compiler `u_ld_light_size` auf ein Element, und pyglet kann das
  Array nicht setzen. Deshalb läuft `--no-area` mit `--spec`. Das ist eine Eigenheit des Experiments, kein
  Production-Fall.
