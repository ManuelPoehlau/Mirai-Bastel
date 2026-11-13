# Lookdev GPU probe — Lookdev step 1 (2026-11-13)

**Status:** isolated experiment. **Run on the reference PC on 2026-11-13**
([`RESULTS_REFERENCE_PC_2026-11-13.md`](RESULTS_REFERENCE_PC_2026-11-13.md), `MEASURED [RPC]`); container validation
in [`RESULTS_CONTAINER_2026-11-13.md`](RESULTS_CONTAINER_2026-11-13.md). Main PC: `OPEN`. No change under `src/`,
`tests/`, `config/`; no dependency added.
**Source:** [Lookdev P0 audit](../../docs/research/LOOKDEV_P0_CODEBASE_AUDIT_2026-11-13.md) §5.7 (driver questions),
§6.4 (fill-rate risk), §9 step 1 and §10 (recommendation: probe before the eye lab);
[RENDERING_VISION.md](../../docs/design/RENDERING_VISION.md) §8 ("cubemap reflections: Realistic" — unmeasured until
now) and §9 P1; hardware: [REFERENCE_HARDWARE.md](../../docs/architecture/REFERENCE_HARDWARE.md).

## What it answers

Before the Eye Proof (P1) is built around an environment format, two unknowns:

1. **Does the GeForce 9800 GTX driver handle what P1 needs?** Cube maps in `RGBA16F` and `RGBA8` (and `RGBA32F` for
   reference), explicit mip sampling with `textureLod`, linear / trilinear filtering, and seamless cube filtering
   (`GL_TEXTURE_CUBE_MAP_SEAMLESS`). None of this is used anywhere in Mirai yet (audit §3.4).
2. **What does a frame-filling shaded pass cost?** The Worklight's face-data pass is known only at ≈ 13 % coverage
   (≈ 9.4 ms GPU at 87.5k / 1024×768, `RESULTS_O2_REFERENCE_PC_2026-11-11.md`); a Lookdev close-up fills the frame.

## Result on the reference PC (2026-11-13, MEASURED [RPC]; details and readings in the results file)

- **A, B, C pass in every format.** RGBA8, RGBA16F and RGBA32F cubes store, sample, mip-select and filter exactly;
  the driver reports the requested formats.
- **D fails, but only at corners.** Seamless filtering works across edges. A filter tap beyond both edges of a face
  (a cube corner) comes from one face instead of the mean of three, which leaves seams at the 4², 2² and 1² levels.
  The emulation in `cube_math.seamless_bilinear` reproduces the measured jumps within ~1.5 %. INFERRED from that
  emulation: equalizing the three corner texels per level (`cube_math.equalize_corners`) and not using the 1×1 level
  removes it.
- **T:** one cube lookup over a full 1920×1080 frame costs ≈ 0.1 ms. Seamless filtering is free; RGBA16F is as fast
  as RGBA8.
- **Worklight at a frame-filling close-up (87.5k):** 16.1 ms at 1024×768 and 26.8 ms at 1920×1080 GPU time for the
  pass alone; without face data, 2.9 / 5.0 ms.

## Files

| File | What |
|---|---|
| `probe_gl_caps.py` | The capability probe: own hidden pyglet window and GL context, own programs and offscreen targets; **imports nothing from `src/`**. Checks A–D, timing T, hygiene R (below). |
| `cube_math.py` | GL-free half: the GL cube-face convention, test patterns, expected values, the clamp-to-edge and seamless (two corner rules) emulations, the corner fix-up, verdict rules, PNG writer, source state. NumPy only. |
| `probe_worklight_coverage.py` | Thin wrapper around the **unchanged** `drag_cost/probe_shading_gpu.measure`: same fixture, variants, timer and image check, with the camera dollied in (`--dolly`, default 1.0 / 0.5 / 0.3 ≈ 14 / 62 / 98 % coverage at 1024×768). |
| `RESULTS_TEMPLATE.md` | The results format (evidence labels per cell); copy to `RESULTS_<MACHINE>_<DATE>.md`. |
| `RESULTS_REFERENCE_PC_2026-11-13.md` | The reference-PC run (`MEASURED [RPC]`): GL facts, A–D, the corner diagnosis, fetch cost, Worklight baseline and close-ups, reading for P1, raw output. |
| `RESULTS_CONTAINER_2026-11-13.md` | What the container could validate (`TESTED [C]`), raw output. |
| `tests/` | Headless tests (face convention, patterns, interpretation, argument / import boundaries, the dolly hook) and GL tests (a full small run reaches a verdict everywhere and cleans up; leak and state checks catch what they should). |
| `.gitignore` | ignores `out/` (seam panoramas written by `--images`). |

## Commands — reference PC (PowerShell, repository root, `.venv312`)

Nothing to install: `.venv312` already has `numpy==2.2.6` and `pyglet 2.1.19` (verified 2026-11-13,
`RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md`). The commands call the venv's interpreter by path, so the active
interpreter is not changed.

**First:** NVIDIA control panel → "3D-Einstellungen verwalten" → **Globale Einstellungen** → "Energieverwaltungsmodus"
→ **"Maximale Leistung bevorzugen"** (REFERENCE_HARDWARE §2: at low clocks the same pass costs ≈ 4× the GPU time).
Use the global setting: `.venv312\Scripts\python.exe` is a launcher that starts the base Python 3.12 as a child
process, so a per-program entry for the venv's exe may not apply. Set it back afterwards if wanted.

```powershell
git pull
$py = (Resolve-Path .\.venv312\Scripts\python.exe).Path; & $py --version; & $py -c "import numpy, pyglet; print('numpy', numpy.__version__, 'pyglet', pyglet.version)"
git rev-parse --short=10 HEAD; git rev-parse --short=10 HEAD:src; git status --short
```

```powershell
& $py -m pytest experiments\lookdev_gpu_probe\tests -q
```

```powershell
& $py experiments\lookdev_gpu_probe\probe_gl_caps.py --images experiments\lookdev_gpu_probe\out
```

```powershell
& $py experiments\drag_cost\probe_shading_gpu.py
```

```powershell
& $py experiments\drag_cost\probe_shading_gpu.py --size 1920 1080
```

```powershell
& $py experiments\lookdev_gpu_probe\probe_worklight_coverage.py
```

```powershell
& $py experiments\lookdev_gpu_probe\probe_worklight_coverage.py --size 1920 1080
```

Paste the console output of each (as for the drag-cost probes). Expected duration on the reference PC (estimate, not
measured): capability probe about a minute; each `probe_shading_gpu.py` run under a minute (four 87.5k render meshes
are built); each coverage run three times that. The seam images land in `experiments\lookdev_gpu_probe\out\`
(ignored by git); attach them if they look odd.

What to check in the output before pasting: the `EVIDENCE:` line must say *hardware renderer*; `Source:` names the
commit and `src/` tree; in the two `probe_shading_gpu.py` runs the header line prints the real framebuffer size — if
it is smaller than `1920x1080`, Windows clamped the hidden window to the screen (the capability probe draws into
offscreen targets and is not affected).

## Commands — main PC (when it exists)

The same seven commands, with that PC's interpreter in `$py` (Python 3.12 + the pinned NumPy keeps the comparison
clean; REFERENCE_HARDWARE §4). Record the hardware first (audit §6.3: CPU, RAM, GPU, VRAM, driver version, OS build,
displays with scaling and refresh rate); the probe prints GL strings, limits, all extensions, screens and window scale.

**Known issue for fast GPUs:** `drag_cost/probe_shading_gpu.py` raises
`ValueError: min() iterable argument is empty` *after* measuring when every variant's fastest draw is ≤ 0.5 ms — its
power-management NOTE check (line 257) takes `min()` of an empty generator. The reference PC is not affected (≥ 1.9 ms),
a modern GPU at 1024×768 may be. Not fixed here (outside this lab's footprint); the one-line fix is to give that
`min(...)` a `default=float("inf")`. The coverage wrapper reports the case instead of a traceback. The same NOTE
check also fires falsely whenever the *variants* differ by more than 2.5× (reference PC 2026-11-13: `off` 1.9 ms
against `o2` 11.2 ms, every variant within 2 %). This probe's own rule (`cube_math.timing_unstable`) compares within
each variant instead.

## Commands — container (agent)

```bash
xvfb-run -a python experiments/lookdev_gpu_probe/probe_gl_caps.py --images <scratch folder>
python -m pytest experiments/lookdev_gpu_probe/tests -q        # GL tests skip without pyglet / display
xvfb-run -a python -m pytest experiments/lookdev_gpu_probe/tests -q
```

`probe_shading_gpu.py` and the coverage wrapper hit the known issue above under llvmpipe; the container numbers in
`RESULTS_CONTAINER_2026-11-13.md` came from a scratch runner outside the repository that patches only that one line in
memory.

## How the checks work

Every check samples in a GLSL 330 fragment shader and reads the result back (`glReadPixels`, `GL_FLOAT`) from an
offscreen `RGBA32F` colour renderbuffer; allocation alone never counts. If that target is incomplete, the probe falls
back to an `RGBA8` target (the type the GPU picker uses on the reference PC) with values scaled into [0, 1] and says
so. Sample directions and lods come from an `RGBA32F` buffer texture (a format already passing on the reference PC);
texture units 1 and 2, unit 0 untouched (audit I-5).

| Check | Pattern | Pass rule |
|---|---|---|
| **A** allocation + sampling | full-mip cubes 64² … 512² per format (`RGBA8`, `RGBA16F` from half data, `RGBA16F` from float data, `RGBA32F`); each face has four quadrants with unique values — float formats up to 603 and down to 2⁻¹⁰, which an 8-bit store cannot keep | all 24 quadrant centres (lod 0) come back as stored (`RGBA16F`: within one half-float step, for driver rounding); no GL error. Also prints what the driver reports for the level (`GL_TEXTURE_INTERNAL_FORMAT`, red type and bits), the upload time, the computed size and the free-video-memory drop (NVX / ATI meminfo if exposed). A clamp to 1 is named. |
| **B** explicit mip levels | 64² cube, one marker per level (R) and face (G) | `textureLod` at lod −1, 0 … 6, 7, 8.5 returns exactly the clamped level's marker at 12 directions. G is compared at face centres only: at the 2×2 / 1×1 levels seamless filtering blends the neighbouring face into an off-centre lookup by design. |
| **C** filtering | bilinear: 16² gradient (R = step·column, G = step·row), samples on and between texel centres in fifths of a texel, every face; trilinear: the B cube, lod 0…6 in 0.1 steps | error ≤ 2 % of one texel / level step (+ 8-bit quanta); nearest filtering would show 50 %; trilinear must be monotonic. The printed error shows the hardware's weight precision (8-bit weights: ≤ 0.2 %). |
| **D** seams | 64² cube holding a smooth function of the direction on every level (a stand-in for a prefiltered environment); pairs of lookups 10⁻⁴ either side of all 12 edges at 7 positions, all 7 levels, seamless off and on | on: every edge jump ≤ max(10 % of the clamp seam, the content's own change, 3 quanta). Off is compared with a NumPy emulation of clamp-to-edge bilinear filtering per face (`cube_math.bilinear_clamp`), so the probe knows the seam it should see; a driver that filters seamlessly regardless also passes. "Switch has no effect" is reported as such (→ CPU edge fix-up). `--images` writes lat-long panoramas per format: rows lod 0 / 3 / 5 / 6, left off, right on. |
| **T** timing | full-frame pass (a sphere close-up: reflection directions sweep all faces), 1 `textureLod` per fragment, 128² cube with mips; per format × sharp (lod 0) / rough (lod 4.5) × seamless off / on, plus a pass without fetch; 1024×768 and 1920×1080 `RGBA8` offscreen targets | information only: GL_TIME_ELAPSED p50 / p95 / min / max over 40 rounds after 5, variants interleaved (as `probe_shading_gpu.py`), cost over the no-fetch baseline, ns per pixel; a NOTE if the times spread > 2.5×. |
| **R** hygiene | — | every GL object the probe made is deleted and `glIs*` is false for all of them; the GL state it touches (bindings on units 0–3, program, VAO, buffers, framebuffers, viewport, seamless switch, pixel-store, clamp-read-colour, …) is identical before and after; `glGetError` clean. |

A check that raises is reported as `ERROR` and the others still run. The summary prints raw verdicts; the machine
label belongs in the results file (the probe only says whether the renderer is software).

**Not built (task scope):** shadow maps, depth-texture rendering, MSAA, MRT, screen-space effects, a framebuffer
framework, sRGB textures / framebuffers, the Eye Proof itself. The `RGBA32F` read-back target doubles as a first data
point for float render targets, nothing more.

## Coverage wrapper

`probe_shading_gpu.py` frames the whole fixture (`Application.frame_scene`): the mesh covers 14.3 % of 1024×768 and
10.7 % of 1920×1080 (container; geometry, so the same on every machine). `probe_worklight_coverage.py` calls its
`measure()` unchanged for each `--dolly` factor (camera distance × factor after `frame_scene`; 1.0 is the baseline
view, so the first run doubles as a consistency check against the plain probe) by swapping
`drag_cost.probe_morph_gl.build_app` for the duration of the call. A headless test pins that `measure()` still imports
`build_app` from there. Coverage in the container: 1.0 / 0.5 / 0.3 → 14.3 / 62.2 / 98.3 % at 1024×768,
10.7 / 46.7 / 99.4 % at 1920×1080.

## Evidence labels (results files)

| Label | Meaning |
|---|---|
| **MEASURED [RPC]** | run on the reference PC (Q9550, 9800 GTX, GL 3.3.0, Windows 10, Python 3.12.10, `numpy==2.2.6`, pyglet 2.1.19) |
| **MEASURED [MAIN]** | run on the main PC (not recorded yet) |
| **TESTED [C]** | run only in a container / development environment (here: Mesa llvmpipe, a software rasterizer) |
| **OPEN** | not run, or inconclusive |

A pass under llvmpipe says nothing about the 9800 GTX driver, and llvmpipe's GL_TIME_ELAPSED is not a GPU time (it
is not even monotonic in the pixel count, `RESULTS_CONTAINER_2026-11-13.md`).

## Tests

`python -m pytest experiments/lookdev_gpu_probe/tests -q` (not part of the default `pytest` run; AGENTS.md §8a: run when
this folder changes). 30 headless tests, 3 GL tests (`xvfb-run -a` in a container; skipped without pyglet / display).
Two headless tests pin the reference PC's seam measurements to the emulation.
The GL tests assert only what must hold on any driver — every check reaches a verdict, no leak, state restored — not
that a driver passes A–D: that is a finding for the results file, not a red test.

## Kurzfassung für Manu (Deutsch)

- **Was:** eine kleine Sonde mit eigenem (verstecktem) Fenster, unabhängig von der App. Sie prüft, ob deine
  Grafikkarte Cubemaps (die Umgebung für Spiegelungen im Auge) in den nötigen Formaten wirklich richtig liest — nicht
  nur anlegt —, ob gezielt unschärfere Stufen gelesen werden können (für Rauheit), ob die Filterung stimmt und ob an
  den Würfelkanten Nähte sichtbar sind. Dazu misst sie, was das pro Bild kostet, und misst den heutigen
  Worklight-Shader, wenn das Mesh das ganze Bild füllt (Großaufnahme).
- **Vorher:** NVIDIA-Systemsteuerung → globale Einstellung „Maximale Leistung bevorzugen“.
- **Ausführen:** die sieben PowerShell-Befehle oben (Abschnitt „Commands — reference PC“), Ausgabe hier einfügen. Es
  wird nichts installiert und nichts an der App geändert. Dauer grob 5–10 Minuten.
- **Dein Lauf (2026-11-13):** Cubemaps funktionieren in allen Formaten, nur an den Würfelecken filtert die Karte
  nicht nahtlos (Abhilfe beim Vorberechnen, ohne Laufzeitkosten). Eine Spiegelung kostet ≈ 0,1 ms pro Bild; teuer
  ist das Worklight-Shading in der Großaufnahme (16 / 27 ms). Kurzfassung und Zahlen:
  [`RESULTS_REFERENCE_PC_2026-11-13.md`](RESULTS_REFERENCE_PC_2026-11-13.md).
