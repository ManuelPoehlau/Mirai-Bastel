# LookDev: Diffuses Flächenlicht am Terminator (2026-11-24)

**Status:** isoliertes Wegwerf-Experiment (Forschung, keine Production-Spezifikation). **Kein Eingriff in `src/`,
`tests/`, `config/` oder Szenen:** die Varianten werden nur *im eigenen Prozess* in den String des Haut-Fragment-
Shaders gepatcht (`area_glsl.install`); der Augen-Shader und `LD_COMMON_SRC` bleiben unberührt.
**Bewertung und Empfehlung:**
[`docs/research/LOOKDEV_DIFFUSE_AREA_LIGHT_TERMINATOR_ASSESSMENT_2026-11-24.md`](../../docs/research/LOOKDEV_DIFFUSE_AREA_LIGHT_TERMINATOR_ASSESSMENT_2026-11-24.md).
**Container-Lauf:** [`RESULTS_CONTAINER_2026-11-24.md`](RESULTS_CONTAINER_2026-11-24.md) (llvmpipe: Bilder und
Funktionsprüfung, **keine** 9800-GTX-Messung). **Referenz-PC gemessen:** [`RESULTS_REFERENCE_PC_2026-11-24.md`](RESULTS_REFERENCE_PC_2026-11-24.md) (GeForce 9800 GTX, 1024 × 768 und 1920 × 1080).

## Frage

Die „Weichheit“ (`StudioLight.size`) des Key macht heute Glanzlicht und Schattenkante weicher, aber nicht den
diffusen Übergang am Terminator. Lässt sich ein endlich großer Key im diffusen Term billig und ohne die Lecks aus
AD-039 §16.6–16.7 annähern?

## Dateien

| Datei | Was |
|---|---|
| `area_math.py` | NumPy-Modelle: A (Lambert + Wrap, heute), A' (Wrap + Größe, naiv), B (Horizont-Spline), B2 (exakte Kugellicht-Irradianz), C (N Richtungen auf der Kappe), Referenz (4096+ Richtungen); Abbildung Größe → sin σ (`S_MAX`, σ(1) = 40°) |
| `area_glsl.py` | GLSL der Varianten und `patch_fragment` (jede Ersetzung prüft ihren Anker im aktuellen Production-Text); Optionen `excess` (lifted / split / point), `lift` (effective / mid / full), `spec`, `linear`, `repeat` |
| `run_compare.py` | A/B-Bilder durch den echten LookDev-Pass (Gollum_Head_05 SubD 1, Ansichten „face“ und „framed“; Formen-Szene Kugel / Zylinder / Mulde), linear in ein RGBA32F-FBO, Tonkurve in NumPy (Production-Zwilling); REF = Mittel aus 32 harten Key-Richtungen auf der Kappe (echte weiche Schatten) |
| `analyze.py` | Zahlen pro Region (Nase, Mundwinkel, Schattenwange, Augenhöhlen; Kugel, Zylinder, Schale, Rinne) und Ausschnitte |
| `curves.py` | Kurven der Modelle über den Terminator + Fehlertabelle (matplotlib nur für das Bild, keine Repo-Abhängigkeit) |
| `bench.py` | GPU-Zeit der Varianten im echten LookDev-Frame, für den Referenz-PC |
| `tests/` | kopflos: Modelleigenschaften (Punktlicht = Production, Lichtseite unverändert, Größe ≠ Wrap) und dass jeder Patch-Anker in allen Effekt-Kombinationen gefunden wird |
| `out/` | (gitignored) alle Bilder und Zahlen; ausgewählte, verkleinerte Bilder liegen in `docs/research/lookdev_diffuse_area_assets_2026-11-24/` |

## Befehle (Container)

```bash
python -m pytest experiments/lookdev_diffuse_area/tests -q
```

```bash
xvfb-run -a python experiments/lookdev_diffuse_area/run_compare.py --variants A,B,B2,B-split,C16 --ref 32
```

```bash
python experiments/lookdev_diffuse_area/analyze.py experiments/lookdev_diffuse_area/out
```

```bash
xvfb-run -a python experiments/lookdev_diffuse_area/run_compare.py --scene gollum --variants A,B,B-split,A-liftfull,B-liftfull,B-liftmid --out experiments/lookdev_diffuse_area/out_lift
```

```bash
python experiments/lookdev_diffuse_area/curves.py
```

## Befehle (Referenz-PC, PowerShell, Repo-Wurzel, `.venv312`)

Vorher NVIDIA-Systemsteuerung → „3D-Einstellungen verwalten“ → Globale Einstellungen → Energieverwaltungsmodus
„Maximale Leistung bevorzugen“ (REFERENCE_HARDWARE §2).

```powershell
$py = (Resolve-Path .\.venv312\Scripts\python.exe).Path; git rev-parse --short=10 HEAD; git status --short
```

```powershell
& $py experiments\lookdev_diffuse_area\bench.py
```

```powershell
& $py experiments\lookdev_diffuse_area\bench.py --size 1920 1080
```

Die dokumentierten Läufe vom 2026-11-24 stehen in [`RESULTS_REFERENCE_PC_2026-11-24.md`](RESULTS_REFERENCE_PC_2026-11-24.md). Bei Wiederholungen die neue Roh-Ausgabe mit Datum ergänzen. Entscheidend sind die Zeilen `B` gegen `A` und `(Bx16 - Ax16) / 16` je Fläche (cage / subd1) und Ansicht (framed / face).

## Grenzen

- REF ist für Wrap 0 (Neutral) die physikalische Wahrheit eines Kugel-Emitters samt weicher Schatten (bis auf die
  Auflösung der Schattenkarte bei Größe 0 und 32 Richtungen). Für Creature Skin erbt REF die Wrap-Regel von
  Production bei Größe 0 (der „gehobene“ Lookup mit voller Auflösung) - dort ist REF ein Ziel, keine Physik.
- llvmpipe-Zeiten sind keine GPU-Zeiten. Die Bildvergleiche sind davon unabhängig (gleicher Shader-Text, float32).
