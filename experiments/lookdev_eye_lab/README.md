# Lookdev P1 — Eye Proof lab (2026-11-14)

**Status:** disposable experiment, **validated in the container** (`TESTED [C]`,
[`RESULTS_CONTAINER_2026-11-14.md`](RESULTS_CONTAINER_2026-11-14.md)); **ready for Manu's run on the reference PC**
(everything `[RPC]` is `OPEN`). Main PC: `OPEN` (D-L5 deferred). No change under `src/`, `tests/`, `config/`; no new
dependency; no keymap entry.
**Source:** [Lookdev P0 audit](../../docs/research/LOOKDEV_P0_CODEBASE_AUDIT_2026-11-13.md) §5 (P1 proposal), §8
(decisions) and its 2026-11-13 addendum; the probe's reading for P1:
[`lookdev_gpu_probe/RESULTS_REFERENCE_PC_2026-11-13.md`](../lookdev_gpu_probe/RESULTS_REFERENCE_PC_2026-11-13.md) §8.

## Decisions this lab works under

| Decision | State | What the lab does |
|---|---|---|
| D-L1 separate experiment | decided (Manu 2026-11-13) | own window, imports from `src/`, nothing moves the other way |
| D-L2 synthetic eye | decided | sclera / iris + pupil / cornea generated as `core.Mesh` (`eye_geometry.py`) |
| D-L4 procedural studio | decided | backdrop + softbox + strip light in NumPy (`studio_env.py`), no HDRI |
| D-L5 main PC | deferred | reference PC only |
| D-L3 colour path | **open** | scene-linear **inside the lab only** (shader-side sRGB decode / encode, exposure, clamp or Reinhard) |
| D-L6 product form, quad normal | **open** | the lab uses plain interpolated vertex normals (the probe's tendency, RESULTS_REFERENCE_PC §6); nothing decided |
| D-L7 material storage | **open** | lab-local `SurfaceMaterial` per part (`lab_state.py`), not stored anywhere |
| D-L8 budget | **open** | eye only, ~50 % of the frame; the large character is not measured here |
| D-L9 keys | **open** | lab-local keys below; no BindingSet, no `config/keymap.json` |

## What it answers (audit §5.1)

| # | Question | Where |
|---|---|---|
| Q1 | Cornea reflection + Fresnel in the GL 3.3 path? | T-B / T-C / T-D on C2 / C3 (and C1), Artist verdict at the three views + orbit |
| Q2 | Environment reflections without modern GL? | RGBA16F cube 128², half-float upload, CPU prefilter, `textureLod`; RGBM8 fallback; probe [E], [S] |
| Q3 | Roughness → reflection? | prefiltered mips per mapping (`lod = r·N` / `lod = √r·N`, key `L`); chrome sweep (key `G`, probe [W]) |
| Q4 | Existing geometry + texture infrastructure enough? | the parts are production object entries (`Viewport(store_type=EyeLabStore)`); the iris image goes through `Mesh.set_face_uvs` → `RenderMesh` triangle UVs → the store's texture (AD-026) |
| Q5 | Legacy fallback? | C1 (opaque, no shell), RGBM8 cube, T-D (no cube map) |
| Q6 | Main PC? | the same commands (D-L5) |

## The seam under test

The lab is built the way the audit recommends for P2 (§4.2), so P1 also tests the seam:

- `Viewport(store_type=EyeLabStore)` with `EyeLabStore(GLRenderStore)` (`gl_lab.py`). The store keeps every production
  mechanism (VertexList assembly, face data, triangle UVs, texture cache) and only replaces `draw()`.
- **T-A** calls `GLRenderStore.draw` unchanged. A test pins that T-A is pixel-identical to a store without the lab
  (`test_t_a_is_the_production_draw_pixel_for_pixel`).
- **T-B … T-D** draw the **same VertexList** with a lab program on the production attribute locations — a third
  consumer of the store's buffers after the GPU picker and the wire. The textured variant reuses production's
  `TEXTURED_VERTEX_SRC` / `TEXTURED_GEOMETRY_SRC` as they are.
- Draw order is the viewport's own (AD-021 RD-1): grey sphere (edit mesh), sclera, iris, chrome, then the cornea as
  a Ghost entry (alpha < 1) — last, as the shells need, and in T-A it shows as the production Ghost.

## Scene (all generated; units: 1 = 12 mm, the sclera radius)

| Part | Shape |
|---|---|
| sclera | sphere r 1, polar axis +Z, **open at the limbus** (the front cap is removed, so there is no pole fan in the iris area at all — the audit's "poles sideways" aimed at that; the back pole is out of view) |
| cornea | spherical cap r 0.65 (7.8 mm), rim = the sclera's limbus ring (r 0.49, same vertices' positions), apex 1.095 |
| iris | slightly concave annulus (pupil edge 0.03 behind the root), root just inside the sclera wall; pupil tube 0.06 deep with a black floor; planar UVs; procedural iris PNG written to `out/iris.png` |
| chrome / grey | reference spheres r 0.6 at x = ∓2.3 (chrome F0 1, grey albedo 0.18 / F0 0.04 / r 0.5) |

**Studio** (scene-linear, neutral): backdrop (floor 0.035, horizon 0.12, zenith 0.20), key softbox at az 35° / el 25°,
36° × 26°, radiance 8, strip light at az −115° / el 10°, 8° × 64°, radiance 4. The rectangles are Gaussian-edged boxes
in angular coordinates — the same function T-D evaluates in the shader.

**Cube (RESULTS_REFERENCE_PC §8 recipe):** RGBA16F, 128² (64 / 256 by key), half-float data rounded by NumPy, CPU
prefilter in GL face order (`lookdev_gpu_probe/cube_math.py`, not re-derived), GGX importance sampling with N = V = R
(Karis split sum), each mip prefiltered for the roughness its mapping assigns to it, **corners equalized per level**
(`cube_math.equalize_corners`), chain ending at **2²** (`GL_TEXTURE_MAX_LEVEL`; roughness 1 → 2²), trilinear,
**seamless on** (key `M`). Cached in `out/cache/` (ignored by git); prefilter ≈ 6 s per 128² chain in the container.

## Techniques and cornea treatments (audit §5.3)

| Id | Specular / reflection |
|---|---|
| T-A | the Worklight's Blinn–Phong, production program unchanged (display-referred, face-data normals) |
| T-B | GGX D + height-correlated Smith + Schlick, key light only |
| T-C | T-B + prefiltered cube (`textureLod` by roughness) × Karis' analytic split-sum term (Fresnel-weighted environment) |
| T-D | T-B + analytic softbox / strip / backdrop in the shader (no cube map); lobe width `0.8 · α^0.675`, fitted to the cube prefilter (≤ 16 % relative RMS at r ≤ 0.8) |

| Id | Cornea |
|---|---|
| C1 | no cornea mesh; iris fragments intersect the analytic cornea sphere and add its specular / environment there (iris diffuse × (1 − F)) |
| C2 | cornea shell drawn last, depth test on, depth write off, `blend(ONE, ONE)`, output = environment specular + direct specular |
| C3 | the same with premultiplied `blend(ONE, ONE_MINUS_SRC_ALPHA)`, alpha = Schlick F(N·V) |
| T-A + C2 / C3 | the cornea as the production Ghost (alpha 0.25): what the app can show today |

Diffuse is the same in T-B … T-D (key Lambert + a sky / ground ambient taken from the studio), so the techniques differ
only in their specular. The iris has no highlight of its own; the wet reflection over it is the cornea's.

**Colour path (lab-local, D-L3 open):** sRGB decode of the iris image in the shader, linear shading, exposure `2^EV`,
clamp or Reinhard per channel, sRGB encode in the shader; no `GL_FRAMEBUFFER_SRGB`, so a HUD stays as it is.

**Known limits (record them, do not hide them):**
- C2 / C3 blend in the 8-bit **display-encoded** framebuffer, not in linear light (no float target, no sRGB framebuffer
  in P1): the added reflection is somewhat brighter than a linear add would be. C1 adds in linear light.
- No anti-aliasing (no MSAA, no specular AA): highlight flicker while orbiting is expected — note it.
- RGBM8 interpolates RGBM values trilinearly (the usual compromise); RGBA16F is the reference format.
- T-D's Gaussian has no GGX tail: wide lobes come out tighter than T-C's (probe [W]).
- The background "env" is the analytic studio blurred (the same for all techniques), not a cube mip.

## Files

| File | What |
|---|---|
| `run.py` | entry point: interactive window, or `--probe` |
| `probe_eye.py` | probe mode: header, [E] environment, [S] seams, [Q5] sRGB, [P] parity, [V] variant timings, [W] roughness sweep, screenshots, [R] hygiene |
| `gl_lab.py` | `EyeLabStore`, `EyeLabRenderer` (programs, cube, background), `EnvCube`, offscreen `Target`, `ParityPass` |
| `shaders.py` | GLSL: `LIB_SRC` (every term, twin of `eye_math.py`), surface / background / parity programs |
| `eye_math.py` | NumPy reference of every shading term, colour path, T-D softbox, C1 sphere, framing |
| `studio_env.py` | procedural studio, CPU prefilter, cache, RGBM, footprint spread |
| `eye_geometry.py` | the eye and reference spheres as `core.Mesh`, the iris image |
| `lab_scene.py` | the scene on the production `Viewport`, camera presets, close-up framing |
| `lab_state.py` | every control as plain data, materials, the lab-local key table, HUD text |
| `parity.py` | shader-vs-NumPy cases (inputs, references, tolerances) for the test and the probe |
| `tests/` | 35 headless tests + 13 GL tests |
| `RESULTS_CONTAINER_2026-11-14.md` | the container validation (`TESTED [C]`) with raw output |
| `RESULTS_TEMPLATE.md` | format for `RESULTS_REFERENCE_PC_<date>.md` incl. the Artist verdict table |
| `.gitignore` | `out/` (iris image, prefilter cache, screenshots, probe images) |

## Controls (lab-local; `F1` shows them in the window)

| Key | Action |
|---|---|
| `1` `2` `3` `4` | technique T-A / T-B / T-C / T-D |
| `5` `6` `7` | cornea C1 / C2 / C3 |
| `←` `→` / `↑` `↓` | key azimuth ∓15° / elevation ±10° |
| `K` (`Shift+K`) | key intensity ×1.25 (÷1.25) |
| `E` | environment on / off |
| `Y` (`Shift+Y`) | environment yaw +15° (−15°) |
| `U` (`Shift+U`) | environment intensity ×1.25 (÷1.25) |
| `X` (`Shift+X`) | exposure +0.5 EV (−0.5) |
| `S` (`Shift+S`) | sclera roughness +0.05 (−0.05) |
| `C` (`Shift+C`) | cornea roughness +0.01 (−0.01) |
| `I` (`Shift+I`) | cornea IOR +0.02 (−0.02) → F0 |
| `G` (`Shift+G`) | chrome roughness 0 / .1 / .25 / .5 / .75 / 1 |
| `L` | roughness → LOD mapping linear / sqrt (each has its own prefiltered chain) |
| `R` | cube resolution 64 / 128 / 256 |
| `F` | cube format RGBA16F / RGBM8 |
| `M` | seamless cube filtering on / off |
| `T` | tonemap clamp / Reinhard |
| `B` | background solid / environment |
| `H` | reference spheres on / off |
| `V` | camera preset front / ¾ / profile |
| `Z` | close-up (eye ≈ 50 % of the frame) / overview |
| left drag, wheel | orbit, dolly |
| `P` | screenshot to `out/screenshots/` (without the HUD) |
| `Esc` | quit |

The HUD shows the state and the previous frame's GPU time (`GL_TIME_ELAPSED`). The first switch to T-C (or a new
resolution / mapping) prefilters for a few seconds once; after that the chain comes from `out/cache/`.

## Commands — reference PC (PowerShell, repository root, `.venv312`)

Nothing to install: `.venv312` has `numpy==2.2.6` and `pyglet 2.1.19` (verified 2026-11-13). The commands call the
venv's interpreter by path.

**First:** NVIDIA control panel → "3D-Einstellungen verwalten" → **Globale Einstellungen** → "Energieverwaltungsmodus"
→ **"Maximale Leistung bevorzugen"** (REFERENCE_HARDWARE §2; the global setting, because `.venv312\Scripts\python.exe`
starts the base Python as a child process).

```powershell
git pull
$py = (Resolve-Path .\.venv312\Scripts\python.exe).Path; & $py --version; & $py -c "import numpy, pyglet; print('numpy', numpy.__version__, 'pyglet', pyglet.version)"
git rev-parse --short=10 HEAD; git rev-parse --short=10 HEAD:src; git status --short
```

```powershell
& $py -m pytest experiments\lookdev_eye_lab\tests -q
```

```powershell
& $py experiments\lookdev_eye_lab\run.py --probe
```

```powershell
& $py experiments\lookdev_eye_lab\run.py
```

Paste the console output of the first three. Expected duration (estimate, not measured): tests under a minute; the
probe 3–6 minutes, most of it the CPU prefilter of six chains (64 / 128 / 256 × two mappings) plus the two sweep
studios on the Q9550. The probe's screenshots land in `experiments\lookdev_eye_lab\out\probe\` (`sheet_front.png`,
`sheet_three_quarter.png`, `sheet_profile.png`: rows T-A … T-D, columns C1 … C3); attach the three sheets.

What to check before pasting: the `EVIDENCE:` line says *hardware renderer*; `Source:` names the commit and `src/`
tree; the Summary lists six `PASS` lines (a `FAIL` is a finding, not a broken run — paste it as it is).

**The practical test (Manu, interactive window).** Start with `Z` (close-up), then for each technique (`1`–`4`) and
cornea (`5`–`7`) at front / ¾ / profile (`V`) and while orbiting (left drag), a verdict **KEEP / ITERATE / REJECT** on
(audit §5.5):

1. the cornea shows a crisp, recognisable softbox reflection that sits on the cornea, moves plausibly and reads "wet";
2. Fresnel is visible: weaker facing the camera, stronger toward the cornea's edge;
3. roughness reads: the sclera's reflection broad and soft, the cornea's sharp (`S`, `C`; the chrome sweep `G` with `H`);
4. the iris stays readable through the cornea at the front view;
5. no cube seams at rough levels (`G` up to 1 on the chrome sphere, `M` toggles seamless), no distracting flicker while
   orbiting (aliasing is expected: note how bad);
6. C1 alone still reads as a wet eye.

Also worth one look each: `L` (which mapping reads more natural on the chrome sweep), `F` (RGBM8 vs RGBA16F), `T`
(clamp vs Reinhard), `B`. Screenshots with `P` for anything worth discussing. The table to fill is in
[`RESULTS_TEMPLATE.md`](RESULTS_TEMPLATE.md).

## Commands — container (agent)

```bash
python -m pytest experiments/lookdev_eye_lab/tests -q                 # GL tests skip without pyglet / display
xvfb-run -a python -m pytest experiments/lookdev_eye_lab/tests -q
xvfb-run -a python experiments/lookdev_eye_lab/run.py --probe --images <scratch folder>
```

The container has no pyglet in its system Python; the runs used a scratch venv outside the repository with the
reference PC's versions (`uv venv -p python3.12` + `numpy==2.2.6 pyglet==2.1.19 pytest`).

## Evidence labels (results files)

| Label | Meaning |
|---|---|
| **MEASURED [RPC]** | run on the reference PC (Q9550, 9800 GTX, GL 3.3.0, Windows 10, Python 3.12.10, `numpy==2.2.6`, pyglet 2.1.19) |
| **MEASURED [MAIN]** | run on the main PC (not recorded yet, D-L5) |
| **TESTED [C]** | run only in the container (Mesa llvmpipe, a software rasterizer: its `GL_TIME_ELAPSED` is not a GPU time) |
| **OPEN** | not run, or inconclusive |

## Tests

`python -m pytest experiments/lookdev_eye_lab/tests -q` — not part of the default `pytest` run (AGENTS.md §8a: run when
this folder changes). Headless (35): the NumPy reference (GGX normalisation, Fresnel / split-sum limits, LOD mappings,
erf, T-D vs the prefilter), the studio and its chain (face order, corners, monotonic footprint, cache, RGBM), the
geometry (orientation, shared limbus ring, no poke-through, UVs, iris image), keys and the `src/` / keymap boundary.
GL (13): every `LIB_SRC` function against NumPy (11 cases), a small probe run that must report six `PASS`, and T-A
pixel-identical to the production draw.

## Kurzfassung für Manu (Deutsch)

- **Was:** ein Wegwerf-Lab mit eigenem Fenster. Ein künstliches Auge (Lederhaut, Iris mit Pupille, Hornhaut) und zwei
  Referenzkugeln (Chrom, Grau) in einem berechneten Studio (Softbox, Streiflicht, Hintergrund). Vier Techniken
  (T-A heute, T-B GGX nur Key, T-C mit Cubemap-Spiegelung, T-D Softbox analytisch ohne Cubemap) und drei
  Hornhaut-Varianten (C1 undurchsichtig, C2 additive Schale, C3 Fresnel-Schale).
- **Gebaut wie für später gedacht:** Das Auge sind normale Objekte im Produktions-Viewport; das Lab ersetzt nur das
  Zeichnen. T-A ist pixelgleich mit heute. Nichts in `src/` ist geändert.
- **Im Container geprüft:** Alles rendert ohne GL-Fehler, die Shader rechnen wie die Python-Referenz, die Rauheit macht
  die Spiegelung gleichmäßig breiter, keine Nähte. Zeiten aus dem Container sind keine GPU-Zeiten.
- **Dein Lauf:** NVIDIA auf „Maximale Leistung“, dann die vier PowerShell-Befehle oben. Die ersten drei Ausgaben hier
  einfügen und die drei Übersichtsbilder aus `out\probe\` anhängen. Danach im Fenster (`run.py`) je Technik und
  Hornhaut KEEP / ITERATE / REJECT nach den sechs Punkten oben.
