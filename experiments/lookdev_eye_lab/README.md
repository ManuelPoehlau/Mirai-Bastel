# Lookdev P1 — Eye Proof lab (2026-11-14)

**Status:** disposable experiment. Container: `TESTED [C]`
([`RESULTS_CONTAINER_2026-11-14.md`](RESULTS_CONTAINER_2026-11-14.md)). **Reference PC: probe run 2026-11-14, six PASS**
([`RESULTS_REFERENCE_PC_2026-11-14.md`](RESULTS_REFERENCE_PC_2026-11-14.md), `MEASURED [RPC]`): no corner seams with
the fix-up, T-C 1.0–1.3 ms / 2.4–2.9 ms per frame at 1024×768 / 1920×1080 with the eye at ~50 %, T-D about twice
that. **Artist verdict: `OPEN`** (the practical test below). Main PC: `OPEN` (D-L5 deferred).
**P1b — Corneal Refraction Lab (2026-11-14):** added on top of P1, P1 unchanged; see [the P1b section](#p1b--corneal-refraction-lab-2026-11-14).
**P1c — soft limbus (2026-11-14):** L0–L3 on top of P1b, P1 / P1b unchanged; see [the P1c section](#p1c--soft-limbus-2026-11-14) (plan: [`PLAN_P1c_LIMBUS_2026-11-14.md`](PLAN_P1c_LIMBUS_2026-11-14.md)).
**Own iris image:** put it at `out/iris_custom.png`; see [Custom iris texture](#custom-iris-texture-outiris_custompng). No change under `src/`, `tests/`, `config/`; no new
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
| `iris_source.py` | which iris image is used: `out/iris_custom.png` if usable, else the procedural one (P1 and P1b) |
| `iris_fit.py`, `suggest_iris_fit.py` | the radial fit of the custom image (`out/iris_custom.json`): validation, remap + GLSL twin, the estimate |
| `parity.py` | shader-vs-NumPy cases (inputs, references, tolerances) for the test and the probe |
| `tests/` | 35 headless tests + 13 GL tests |
| `RESULTS_CONTAINER_2026-11-14.md` | the container validation (`TESTED [C]`) with raw output |
| `RESULTS_REFERENCE_PC_2026-11-14.md` | Manu's probe run on the reference PC (`MEASURED [RPC]`), readings, raw output |
| `RESULTS_TEMPLATE.md` | format for `RESULTS_REFERENCE_PC_<date>.md` incl. the Artist verdict table |
| `.gitignore` | `out/` (iris image, prefilter cache, screenshots, probe images) |

## Custom iris texture (`out/iris_custom.png`)

Added 2026-11-14 (Manu). Used by P1 (`run.py`) and P1b (`run_refraction.py`) alike, and by both probes:

- **If `experiments/lookdev_eye_lab/out/iris_custom.png` exists and loads, it is the iris texture**; otherwise the lab
  falls back to the procedural iris (`out/iris.png`, generated). The choice is made when the window / probe starts.
- **The file is only read**: never written, renamed, copied over or deleted. The procedural iris has its own name, and
  its writer refuses the custom name (tested: bytes and modification time unchanged after both labs ran).
- **Fallback with a reason**: the lab checks the PNG itself (signature, chunk CRCs, header, and the image data must
  inflate to the size the header names — the same verdict on every platform; Windows' own decoder accepted a broken
  file in the 2026-11-14 test run), then the texture loader must decode it. Not a PNG, broken, truncated →
  procedural iris; the reason is in the HUD, on the console and in the probe report.
- **Where you see which one**: the console line at start, the HUD (`iris texture: CUSTOM ... sha1 ...` or
  `procedural`), and the probe reports right after the header (the SHA-1 names the exact image in a results file).
  The probes' CPU ray model (P1b [M]) always uses the procedural iris, so its numbers depend on no file.
- **Replacing the file while the lab runs** shows at the next frame (the loader's cache is keyed by the file's
  modification time). Adding or removing it takes a restart. A replacement the loader cannot decode is not caught at
  that point: P1 then shows a plain grey iris and P1b leaves the cornea out until the file is fixed or the lab
  restarted (the console names the loader's error).

**How the image lies on the eye** (planar mapping, as the procedural iris; checked with marker images): the image square
spans the iris disc of radius 7.18 mm (the iris root); image centre = pupil centre; **top of the file = up, right of
the file = right** in the front view (not mirrored). Measured from the centre as a share of half the image width:

| Share | Radius | What |
|---|---|---|
| 26.8 % | 1.92 mm | pupil edge. P1 shows the image inside it; P1b's refraction shows the dark pupil there whatever the image holds, so paint it black at least to here |
| 78 % | 5.59 mm | the chamber angle: in P1b the iris is not visible beyond it (limbal tissue), magnified on screen by ~1.14 |
| 82 % | 5.88 mm | the visible limbus in P1; beyond it the image is hidden behind the sclera |

Square images work best (non-square ones are stretched onto the disc). The image is treated as sRGB: T-A shows it as
it is, T-B … T-D and P1b decode it to linear light. Alpha is ignored. Any size; it is mipmapped.

### Radial fit (`out/iris_custom.json`, 2026-11-14)

An image whose pupil edge / iris edge are not at the lab's radii (Manu's texture: ≈ 0.22 / ≈ 0.90) gets an optional
sidecar next to it, e.g. `{"pupil": 0.22, "limbus": 0.90}` — where *the image's* pupil edge and iris edge lie, as
shares of half the image width (`iris_fit.py`):

- **Read only**, applies to the custom image only. Exactly the keys `pupil` and `limbus`, numbers,
  `0 < pupil < limbus <= 1`; anything else → ignored, the reason in the HUD / console / probe line
  (`iris_custom.json ignored: …`). **No sidecar → the planar mapping above, unchanged** (the P1 pixel tests and
  V1 = P1 still hold). A valid one shows as `radial fit iris_custom.json: image pupil 0.220 -> 0.268, …`.
- **Remap** (radius only, the angle kept; the standard pupil-dilation remap): lab share `[0, 0.268] → [0, pupil]`,
  `[0.268, target] → [pupil, limbus]`, `[target, 1] → [limbus, outer]`. The image's pupil edge lands on the geometric
  pupil edge in P1 and P1b alike (GL test with a marker image).
- **Where:** P1 bakes it into the iris mesh UVs (`eye_geometry.iris_mesh(uv=…, extra_radii=…)`: one extra ring at the
  target knot so the UV interpolation does not blur the knot); P1b samples through `iris_fit.GLSL_SRC`
  (`#define IRIS_FIT`, NumPy twin `iris_fit.uv`, GPU parity case `refraction_parity.fit_case`, also in the probe's
  [P] when a fit is active). The CPU model (`cornea_optics`, [M]) keeps the procedural iris.
- **Decision (Manu, 2026-11-14): "A+H"** — the image's iris edge lands on the visible limbus 0.819 (`DEFAULT_TARGET`;
  the chamber angle 0.779 stays in `TARGETS` for comparisons), and the optional key **`"hold_outer_color": true`**
  holds the image's iris-edge colour beyond it (absent / false = continue to the image edge, the default). Why the hold:
  P1 has no refraction, so the close-up front view sees the iris through the sclera opening out to ≈ 0.855
  (parallax); without the hold that band shows the image's background (a thin white rim for an image with a white
  outside). With the hold, set `limbus` just inside the background (Manu's texture: `{"pupil": 0.22, "limbus": 0.88,
  "hold_outer_color": true}`). Approved provisionally on a stand-in image with the measured profile; the aesthetic check
  is to be repeated with the real `out/iris_custom.png`.
- `python experiments/lookdev_eye_lab/suggest_iris_fit.py [image.png]` estimates both shares (mean luminance per 1 %
  ring: pupil = first ring > 0.15, iris edge = first ring > 0.85 beyond 0.5; expects a white background) and **prints**
  a suggestion; it writes nothing.

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
"measured coverage" should read about 50 % (the run of 2026-11-14 printed 100 % — a probe bug, fixed since; see the
results file §5).

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
- **Im Container geprüft**, und **auf deinem PC gemessen (2026-11-14):** alles rendert ohne GL-Fehler, die Shader
  rechnen wie die Python-Referenz, keine Würfelnähte mehr, T-C kostet 1–3 ms pro Bild, T-D etwa das Doppelte.
  Ergebnis: [`RESULTS_REFERENCE_PC_2026-11-14.md`](RESULTS_REFERENCE_PC_2026-11-14.md). Offen ist dein Urteil.
- **Dein Lauf:** NVIDIA auf „Maximale Leistung“, dann die vier PowerShell-Befehle oben. Die ersten drei Ausgaben hier
  einfügen und die drei Übersichtsbilder aus `out\probe\` anhängen. Danach im Fenster (`run.py`) je Technik und
  Hornhaut KEEP / ITERATE / REJECT nach den sechs Punkten oben.

---

## P1b — Corneal Refraction Lab (2026-11-14)

**Status:** container-validated (`TESTED [C]`, [`RESULTS_REFRACTION_CONTAINER_2026-11-14.md`](RESULTS_REFRACTION_CONTAINER_2026-11-14.md));
**reference PC 2026-11-14: five PASS** ([`RESULTS_REFRACTION_REFERENCE_PC_2026-11-14.md`](RESULTS_REFRACTION_REFERENCE_PC_2026-11-14.md),
`MEASURED [RPC]`): T-C V2 costs what P1's T-C C2 costs (±0.04 ms), V3 +0.3–0.6 ms more; no Artist verdict (P1's verdicts also stay open). Brief: Manu 2026-11-14 ("Proceed
with P1b"). P1 is the unchanged baseline: P1b only **adds** files and derives from P1's classes; no P1 module, test or
result changed (the P1 tests still pass, and V1 renders P1 pixel for pixel). The later custom iris texture (section
above) touched P1's scene builder only to choose the image; without `out/iris_custom.png` P1 renders as before.

### The three variants

| Id | Ray after the anterior corneal surface |
|---|---|
| **V1** | none: P1 as it is (straight rays to the iris mesh, P1's cornea treatment C1 / C2 / C3) |
| **V2** | one effective refractive surface, air → **n = 1.3375** (keratometric index), then straight to the iris |
| **V3** | two interfaces: air **1.0** → cornea **1.376** (anterior), cornea → aqueous **1.336** (posterior), then to the iris |

V2 / V3 apply to T-B, T-C and T-D (T-A is the production Worklight: it has no refraction and draws P1's T-A).

### Order of work (as asked)

1. **CPU ray model first** (`cornea_optics.py`, `optics_report.py`): geometry, refraction, intersections, and the
   numbers below, before any GLSL.
2. **Geometry:** anterior = P1's cap (r 7.80 mm, rim = the sclera's limbus ring); posterior sphere r 6.60 mm,
   0.55 mm thick at the centre, 0.79 mm at the limbus; the anterior chamber closes where the posterior sphere meets
   P1's iris cone (r 5.59 mm); between that angle and the anterior rim the ray ends in **limbal tissue**, shaded with a
   blend from a dark limbal colour (at the angle) to the sclera (at the rim). V2 uses the same posterior sphere only as
   that boundary, so V2 and V3 hide the same tissue.
3. **Fragment shader** (`refraction_shaders.py`) with GPU-vs-NumPy parity (`refraction_parity.py`).

### What the CPU model measured (COMPUTED, the same on every machine; details in the results file)

- **Front magnification of the pupil:** V2 1.136, V3 1.135 (traced; paraxial 1.144 / 1.143), the virtual pupil
  0.63 mm in front of the real one. At the close-up the pupil's screen area grows by a factor 1.17² (front) and
  1.28–1.30² (¾).
- **V1 → V2/V3 is large:** iris features move 23–52 px (median) at front / ¾, up to 247 px at ¾ (1920×1080).
- **V2 → V3 is small — measured:** iris features ≤ 1.75 px (median 0.1–0.5 px); the visible difference is in the
  limbal band (0.1–0.7 % of the cornea's pixels change between iris and tissue, up to 89 levels there).
- **Side views:** the profile preset (90°, close-up) shows no iris in any variant. Just before it (supplementary 75°
  view) P1 shows none, V2/V3 an iris crescent. Seen from afar, the pupil stays visible to 92.6° off-axis with
  refraction and to 79.6° without.

### The opaque cornea pass

In V2 / V3 the cornea entry is drawn by `RefractionRenderer.draw_cornea`: **depth test on (`GL_LESS`), depth write on,
blending off**, back faces culled, drawn last by the viewport (it is P1's Ghost entry; as an opaque pass the order does
not matter, tested). Per fragment: the view ray meets the analytic anterior sphere (the mesh is the raster footprint),
refracts, and is traced to P1's iris cone, the pupil or the limbal tissue. Colour = (1 − F) · T_inner · L_inside +
reflection, all in linear light, then P1's colour path. F / the reflection use P1's cornea F0 (IOR 1.376) in every
variant, so the reflection equals P1's; only the transmitted part changes. The iris mesh is not drawn in V2 / V3 (every
view of the iris goes through the cornea); tests show that drawing it anyway changes nothing.

This pass also removes P1's C2 / C3 limitation (shells blended in the display-encoded framebuffer): V2 / V3 add the
reflection to the iris in linear light. The reflection therefore looks dimmer than in P1's C2, which over-brightens.

### Approximations and limitations (honest list)

- **Spherical cornea**, both surfaces; real corneas flatten toward the periphery (asphericity Q ≈ −0.25). The
  wide-angle results (iris visible to 115°) depend on that, and there are no lids.
- **No tear film** as a layer (its index ~1.337 ≈ V2's), **no dispersion**.
- **The iris is lit as in P1**, straight from the key: light is not refracted on its way *in*, no caustics, no shadow
  of the limbus on the iris, no inter-reflection.
- **The pupil** is a constant dark colour (P1's); behind it nothing is modelled (lens, retina, red reflex).
- **Limbal tissue** is a lit, opaque blend (dark limbal colour → sclera), not translucent scattering.
- **The iris** is P1's cone (an annulus concave toward the pupil); its depth (3.9 mm behind the apex) is on the deep
  side of real eyes, which makes the refraction effect slightly larger.
- **Reflection** stays P1's: P1's cornea F0 and roughness, Schlick / split sum; the posterior interface reflects
  2·10⁻⁴ (only as a transmission loss, no ghost reflection).
- **Aliasing**: no anti-aliasing (as P1); the refracted iris can shimmer at steep angles.
- **float32**: GPU positions differ from the float64 model by up to ~1 µm at grazing incidence (parity tolerances
  documented in `refraction_parity.py`).

### Files (P1b)

| File | What |
|---|---|
| `cornea_optics.py` | the CPU ray model: geometry, refraction, intersections, traces, magnification, visibility, per-view metrics |
| `optics_report.py` | prints the model's numbers (section [M]); GL-free |
| `refraction_shaders.py` | GLSL: the ray functions (twins of `cornea_optics`), the opaque cornea program, the parity program |
| `refraction_gl.py` | `RefractionState`, `RefractionStore`, `RefractionRenderer`, `build_scene`, the parity pass (all derived from P1's) |
| `refraction_parity.py` | GPU-vs-NumPy cases with tolerances |
| `probe_refraction.py` | the probe: [M] model, [P] parity, [K] ray classes GPU vs CPU, [D] depth / blending / order, [V] timings, sheets, [R] hygiene |
| `run_refraction.py` | interactive window: P1's window and keys + `8` / `9` / `0` = V1 / V2 / V3, `J` = ray-class map; `--probe` |
| `tests/test_cornea_optics.py`, `test_refraction_headless.py`, `test_gl_refraction.py` | 36 + 4 headless, 17 GL (2 for the custom iris) |
| `tests/test_iris_source.py` | 8 headless: choice, fallbacks, the custom file left untouched |
| `tests/test_iris_fit.py` + 8 GL in `test_gl_refraction.py` | 33 headless (sidecar validation, remap, mesh, estimate, PNG filters); GL: fit parity (4), marker image in P1 / P1b with and without sidecar (2), the hold in P1's parallax band (2) |
| `RESULTS_REFRACTION_CONTAINER_2026-11-14.md` | the container validation, the model's numbers, raw output |
| `RESULTS_REFRACTION_REFERENCE_PC_2026-11-14.md` | Manu's run on the reference PC (`MEASURED [RPC]`), readings, the two test fixes |

### Commands — reference PC (PowerShell, repository root, `.venv312`; NVIDIA "Maximale Leistung bevorzugen")

```powershell
git pull
$py = (Resolve-Path .\.venv312\Scripts\python.exe).Path
& $py -m pytest experiments\lookdev_eye_lab\tests -q
```

```powershell
& $py experiments\lookdev_eye_lab\run_refraction.py --probe
```

```powershell
& $py experiments\lookdev_eye_lab\run_refraction.py
```

Paste the output of the first two. Estimate (not measured): tests a few minutes (P1's took 167 s there), the probe
5–10 minutes, most of it the CPU model ([M]) on the Q9550; `--no-optics` skips it (its numbers are the container's
anyway, they do not depend on the machine). Attach `experiments\lookdev_eye_lab\out\refraction\refraction_sheet.png`
(cornea crops: columns T-C V1 C2 = P1 | T-C V2 | T-C V3 | |V3 − V2| × 8; rows front, ¾, profile, steep 75°).
Check: `EVIDENCE: hardware renderer`, five `PASS` lines in the Summary.

In the window: `Z` close-up, `9` / `0` for V2 / V3, `8` back to P1 (V1), `V` for the views, orbit with the left
button; `J` shows which rays reach iris (red), pupil (green) or limbal tissue (blue).

### Kurzfassung für Manu (Deutsch)

- **Drei Varianten:** V1 = P1 ohne Brechung, V2 = eine Ersatzfläche mit n = 1,3375, V3 = zwei Grenzflächen
  (Luft → Hornhaut 1,376 → Kammerwasser 1,336) mit echter Hornhautdicke (0,55 mm Mitte, 0,79 mm am Limbus) und
  Limbus-Übergang.
- **Erst gerechnet, dann gebaut:** Brechung vergrößert die Pupille frontal um 13,6 % und holt sie 0,6 mm nach vorn;
  in der Dreiviertelansicht verschiebt sie die Iris um bis zu 250 Pixel. V2 und V3 unterscheiden sich um höchstens
  1,75 Pixel, sichtbar nur am Limbusrand.
- **Seitenansicht:** im 90°-Profil sieht man in keiner Variante Iris; bei 75° zeigt P1 keine, V2/V3 eine Sichel.
- **Hornhaut jetzt undurchsichtig gezeichnet** (Tiefe schreiben, kein Mischen), alles in linearem Licht: das behebt
  nebenbei die Überhellung der P1-Schalen C2/C3.
- **Dein Lauf:** die drei PowerShell-Befehle oben, Ausgabe einfügen, `refraction_sheet.png` anhängen.

## Eigene Iris-Textur (Kurzfassung für Manu, Deutsch)

- **Datei:** `experiments\lookdev_eye_lab\out\iris_custom.png`. Ist sie da und lesbar, nutzen P1 und P1b sie; sonst
  die berechnete Iris. Die Datei wird nur gelesen, nie verändert.
- **Wo was liegt:** Bildmitte = Pupillenmitte, oben = oben, rechts = rechts (Frontansicht). Pupillenrand bei 26,8 %
  der halben Bildbreite (dort schwarz malen), sichtbarer Limbus bei 82 % (in P1b endet die sichtbare Iris schon bei
  78 %). Quadratisch, sRGB, beliebige Größe.
- **Kontrolle:** Das HUD zeigt `iris texture: CUSTOM …` oder `procedural` (mit Grund, falls deine Datei nicht ging).
  Austauschen während das Fenster läuft wirkt sofort; Hinzufügen oder Entfernen braucht einen Neustart.
- **Radiale Anpassung:** Liegen Pupillen- und Irisrand deines Bilds woanders, daneben `out\iris_custom.json` legen,
  z. B. `{"pupil": 0.22, "limbus": 0.90}` (Anteile der halben Bildbreite). Die Lab-Geometrie bleibt, das Bild wird
  radial passend gezogen. `suggest_iris_fit.py` schlägt die Werte vor, schreibt aber nichts. Deine Wahl „A+H“:
  `{"pupil": 0.22, "limbus": 0.88, "hold_outer_color": true}` — Irisrand auf den Limbus, dahinter die Randfarbe halten
  (ohne den Schlüssel: aus). Das Urteil mit deiner echten Textur steht noch aus.
- **Die JSON legst du selbst an** (das Lab schreibt sie nie; `out\` ist nicht im Repo). PowerShell, Repo-Wurzel:
  `Set-Content -Path experiments\lookdev_eye_lab\out\iris_custom.json -Value '{"pupil": 0.22, "limbus": 0.88, "hold_outer_color": true}'`
  UTF-8 (mit / ohne BOM) und UTF-16 werden gelesen.

## P1c — soft limbus (2026-11-14)

Handoff Task 2, built after Manu's decisions of 2026-11-14 (plan: [`PLAN_P1c_LIMBUS_2026-11-14.md`](PLAN_P1c_LIMBUS_2026-11-14.md)):
cumulative variants, **P1b V2 as the baseline** (V3 selectable), shader only (no geometry change), limbal colour from
a shader setting (default) **or** the iris image's own outer ring (a switch), top / bottom asymmetry as an independent
switch (default off). P1 and P1b code is unchanged; P1c is new files deriving from P1b's classes.

| Level | What it adds (each level includes the ones before) |
|---|---|
| **L0** | nothing — P1b's own code draws (tested and probed: pixel for pixel P1b V2 / V3, every technique, also with the asymmetry switched on) |
| **L1** colour band | one gradient from the limbal colour at the chamber angle (0.29 mm inside the ring) to the sclera albedo `band` (1.0 mm) outside the ring, on P1b's limbal tissue and on the sclera; `strength` scales it. The sclera beyond the band is unchanged (≤ 1 LSB, tested) |
| **L2** normal blend | the shading normal goes from the cornea sphere's to the sclera sphere's across ±0.5 mm around the ring (halfway on the ring), on both passes: the 19.6° kink no longer makes highlights / reflections jump. Refraction and ray classes keep the true surfaces |
| **L3** translucent limbus | the limbal tissue and the sclera band transmit `(1 − t)^falloff` of what lies behind (1 at the chamber angle, 0 at the band edge): the cornea's tissue rays continue (anterior refraction) to the iris; sclera fragments refract into the tissue (n 1.376) and see the iris root |
| asymmetry (switch) | the band starts `0.55 mm · sin²(azimuth)` further over the cornea (visible iris ~11.7 × 10.6 mm): wider at top and bottom; cornea rays that still reach the iris there are covered by tissue (L3: translucent), the cover faded in with the shift (full from ~30° off the horizontal) — fix of 2026-11-14 for a seam left and right that Manu found on the reference PC. Inert at L0 |

Limbal colour: **shader** = a preset (`P1b dark` = P1b's limbal colour, default; `grey-blue`, `grey-brown` as comparison
points) or **image** = the linear mean of the iris image's ring `edge − 0.05 … edge` (edge = the fit's `limbus`, else
0.819); an image that cannot be read falls back to the shader colour with the reason in the HUD. All widths and
the falloff are PROVISIONAL working values (keys below). No Artist verdict.

**Measured in the container** (`TESTED [C]`, llvmpipe — timings there are not GPU times): parity of every limbus
function (max error ≤ 3e-6), L0 = P1b, GL state / resources clean. The probe's [C] section gives edge-continuity
numbers per level (no verdict). Details and raw output:
[`RESULTS_LIMBUS_CONTAINER_2026-11-14.md`](RESULTS_LIMBUS_CONTAINER_2026-11-14.md).

**Reference PC, 2026-11-14** (`MEASURED [RPC]`, [`RESULTS_LIMBUS_REFERENCE_PC_2026-11-14.md`](RESULTS_LIMBUS_REFERENCE_PC_2026-11-14.md)):
186 tests passed, probe four PASS (L0 = P1b pixel for pixel there too). GPU p50, T-C V2 front, 1024×768 / 1920×1080:
L0 1.17 / 2.78 ms, L1 1.28 / 3.04, L2 1.35 / 3.18, **L3 1.89 / 4.17**, asymmetry +0.0. L3's extra cost is mostly the
sclera pass tracing every sclera fragment (it remains in the profile view). Run 1 with Manu's texture without
`iris_custom.json`, run 2 with A+H (no white rim; L3 then 2.10 / 4.56 ms, the fit's remap is sampled up to three times
per L3 fragment). Every Artist verdict is open.

### Controls (P1c window, in addition to P1 / P1b's)

`Q` level L0 → L3 (shift: back) · `O` colour source shader / image · `N` shader colour preset · `A` asymmetry on / off ·
`W` band ±0.25 mm · `D` strength ±0.1 · `,` normal blend ±0.1 mm · `.` translucency falloff ×/÷1.25 (shift = the
other direction). Lab-local; no `config/keymap.json` entry (D-L9). The levels act with V2 / V3 and T-B … T-D.

### Files (P1c)

| File | What |
|---|---|
| `limbus_model.py` | the NumPy reference of every limbus function, the parameters, the image ring colour |
| `limbus_shaders.py` | GLSL: `LIMBUS_LIB_SRC` (twins), the P1c cornea and sclera programs, the parity program |
| `limbus_gl.py` | `LimbusState`, `LimbusStore`, `LimbusRenderer` (L0 → P1b's code), `build_scene`, the parity pass |
| `limbus_parity.py` | GPU-vs-NumPy cases with tolerances |
| `probe_limbus.py` | [P] parity, [I] L0 = P1b, [C] continuity numbers + key sweep, [V] timings, contact sheet, [R] hygiene |
| `run_limbus.py` | the window (P1b's + the keys above); `--probe` |
| `tests/test_limbus_headless.py`, `tests/test_gl_limbus.py` | 9 headless; 19 GL (parity ×5, L0 = P1b ×3 techniques, band per level, asymmetry, no seam left / right ×3 levels, colour source, fallback, GL state, ray-class map / V1, probe run, window) |

### Commands — reference PC (PowerShell, repository root, `.venv312`; NVIDIA "Maximale Leistung bevorzugen")

```powershell
git pull
$py = (Resolve-Path .\.venv312\Scripts\python.exe).Path
& $py -m pytest experiments\lookdev_eye_lab\tests -q
```

```powershell
& $py experiments\lookdev_eye_lab\run_limbus.py --probe
```

```powershell
& $py experiments\lookdev_eye_lab\run_limbus.py
```

Paste the output of the first two; attach `experiments\lookdev_eye_lab\out\limbus\limbus_sheet.png` (limbus crops,
columns L0 | L1 | L2 | L3 | L3 + asymmetry | L3 image colour; rows front / ¾ / profile / steep 75 / ¾ with the key at
−45°, the highlight on the ring). With your `out\iris_custom.png` and
`out\iris_custom.json` = `{"pupil": 0.22, "limbus": 0.88, "hold_outer_color": true}` in place, the probe and the window
use them (the probe names the image and the fit in its header). Check: `EVIDENCE: hardware renderer`, four `PASS`.

### Kurzfassung für Manu (Deutsch)

- **Gebaut:** L0 (= P1b V2, pixelgleich) → L1 Farbband → L2 + Normalen-Übergang → L3 + durchscheinender Limbus;
  Asymmetrie oben/unten als eigener Schalter (aus); Limbusfarbe aus Shader-Einstellung oder aus dem Außenring deiner
  Textur (Taste `O`). P1 und P1b unverändert.
- **Im Fenster:** `run_limbus.py`, `Z` Nahansicht, `Q` Stufe, `A` Asymmetrie, `O` Farbquelle, `N` Farbvorgabe,
  `W` / `D` / `,` / `.` Parameter (Shift = rückwärts). Urteile sind deine.
- **Bitte auf deinem PC:** die drei Befehle oben, Ausgabe der ersten beiden und `limbus_sheet.png` schicken — dann
  stehen die GPU-Zeiten pro Stufe fest.

