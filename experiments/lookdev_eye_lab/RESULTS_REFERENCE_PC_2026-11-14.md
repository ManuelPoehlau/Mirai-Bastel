# Lookdev P1 Eye Proof — reference PC, 2026-11-14

**Run by Manu on 2026-11-14, NVIDIA "Maximale Leistung bevorzugen" (README step).** Every number here is
**MEASURED [RPC]** unless marked otherwise; **[H]** marks a reading of the numbers, **INFERRED** a conclusion not
measured. The **Artist verdict is OPEN**: this run is the probe and the screenshots; the practical test in the window
(README "The practical test") is still to come. Container counterpart:
[`RESULTS_CONTAINER_2026-11-14.md`](RESULTS_CONTAINER_2026-11-14.md). Format: [`RESULTS_TEMPLATE.md`](RESULTS_TEMPLATE.md).

## Kurzfassung für Manu (Deutsch)

- **Alles läuft auf deiner 9800 GTX:** alle 11 Varianten in drei Ansichten und zwei Größen ohne GL-Fehler; die
  Shader rechnen auf dem NVIDIA-Compiler wie die Python-Referenz; die Rauheit verbreitert die Spiegelung gleichmäßig;
  keine Ressourcen bleiben liegen. Sechsmal PASS.
- **Die Würfelnähte sind weg.** Ohne Korrektur springt der Wert an den Würfelecken um 0,009 / 0,062 / 0,169 (Stufen
  4² / 2² / 1²), genau wie vorhergesagt. Mit angeglichenen Ecktexeln und Kette bis 2² ist der Sprung 0. Das war die
  offene Vorhersage von gestern; jetzt ist es gemessen.
- **Das Auge ist billig.** Bei ~50 % Bildfläche kostet ein ganzes Bild mit T-C (Cubemap-Spiegelung) 1,0–1,3 ms bei
  1024×768 und 2,4–2,9 ms bei 1920×1080, Hintergrund eingerechnet. Das heutige Worklight (T-A) kostet für dasselbe
  Auge 2,5–3,6-mal so viel (3,8 / 6,9 ms), wegen der Viereck-Normale.
- **T-D ist keine Spar-Variante:** die analytisch berechnete Softbox kostet rund doppelt so viel wie die Cubemap
  (2,5–2,8 / 5,5–5,9 ms). Da Cubemaps bei dir funktionieren, hat T-D nur noch als Look eine Rolle, falls er dir
  besser gefällt.
- **Langsam ist nur das einmalige Vorberechnen** der Umgebung auf dem Q9550: 40 s für 128², 71 s für 256². Die Sonde
  hat alles in den Cache geschrieben; im Fenster lädt es jetzt sofort.
- **Ein Fehler der Sonde (behoben):** „measured coverage 100 %“ war falsch. Die Sonde kannte die Hintergrundfarbe als
  feste Zahl, dein Treiber rundet sie anders. Die Zeiten und PASS-Ergebnisse betrifft das nicht.
- **Als Nächstes:** dein Urteil im Fenster (`run.py`, `Z` für die Großaufnahme), KEEP / ITERATE / REJECT je Technik
  und Hornhaut.

## 1. Run record

| Field | Value |
|---|---|
| Machine | reference PC: Core 2 Quad Q9550 @ 2.83 GHz, GeForce 9800 GTX/9800 GTX+, Windows 10 (19045) |
| Interpreter | `.venv312\Scripts\python.exe`: Python 3.12.10, numpy 2.2.6, pyglet 2.1.19 |
| Commit / `src/` tree | `4a5fd77bed` (main after PR #67) / `94addddafd` at HEAD = on disk; the working tree was modified outside `src/` only. The lab files at `4a5fd77` are identical to `3a1b7af` (the lab commit) |
| GL | `3.3.0` / `GeForce 9800 GTX/9800 GTX+/PCIe/SSE2` / `NVIDIA Corporation` / GLSL `3.30 NVIDIA via Cg compiler`; core profile |
| `EVIDENCE:` line | hardware renderer |
| Video memory | NVX: 512 MiB dedicated, 360 MiB (368,580 KiB) available at the start |
| Lab tests | `pytest experiments\lookdev_eye_lab\tests`: **48 passed** in 167 s (most of it the CPU prefilter in the headless tests) |
| Frames | offscreen RGBA8 + DEPTH24 targets of exactly 1024×768 and 1920×1080 (the screen is 1200×1920, so a window could not have held 1920×1080) |

## 2. Probe verdicts

| Check | Result | Label |
|---|---|---|
| [E] cube upload 64 / 128 / 256 × RGBA16F / RGBM8 | no GL error; driver reports `RGBA16F FLOAT 16` / `RGBA8 UNORM 8`; upload 9–20 ms (64², 128²), 39 ms (256² RGBA16F), 62 ms (256² RGBM8) | MEASURED [RPC] |
| [E] memory | computed 0.25 / 1.00 / 4.00 MiB (RGBA16F chain to 2²); NVX drop 0.50 / 0.01 / 2.99 MiB — as in the probe run of 2026-11-13, NVX resolves only large allocations | MEASURED [RPC] |
| [E] CPU prefilter per chain | **25 s (64²), 40 s (128²), 71 s (256²)** per mapping; ≈ 6× the container | MEASURED [RPC] |
| [S] seams, seamless on | raw chain (to 1², not equalized): 0.0093 / 0.0620 / 0.1694 at 4² / 2² / 1² — the "one face" corner rule of RESULTS 2026-11-13 §4 again. **Lab chain (to 2², corners equalized): 0.00000 at 4² and 2²**, ≤ 0.0005 at every level → **PASS** | MEASURED [RPC] |
| [Q5] `GL_SRGB8_ALPHA8` decode | PASS; max error vs the exact curve **3.75·10⁻³ at code 251** (≈ 1 step of 8 bits; container 1.2·10⁻³); the shader-side decode of RGBA8 is exact (2.8·10⁻⁸) | MEASURED [RPC] |
| [P] parity, 11 functions on NVIDIA's Cg compiler | PASS; worst `env_radiance` at 0.73 × its tolerance (2.1·10⁻⁴ abs.), all others ≤ 0.26 × | MEASURED [RPC] |
| [V] GL errors, 11 variants × 3 views × 2 sizes | none | MEASURED [RPC] |
| [V] image differs from T-A | every variant (T-A C2 vs C1: 24 / 14 / 1 % of the frame at 1024×768, 26 / 14 / 0.5 % at 1920×1080) | MEASURED [RPC] |
| [V] coverage | printed **100 %: wrong, a probe bug** (§5); the framing is geometry, 49.8–50.0 % in the container at the same commit | INFERRED (from [C]) |
| [W] roughness sweep, chrome sphere | monotonic: T-C 499 → 9505 px², T-D 498 → 5887 px² (r 0 … 1); equal to the container within 0.1 % | MEASURED [RPC] |
| [R] hygiene | PASS: every object deleted, GL state identical, no GL error | MEASURED [RPC] |
| Screenshots | the three contact sheets (front, ¾, profile) look the same as the container's **[H]** (compared by eye, not byte by byte) | MEASURED [RPC] |
| Artist verdict | — | **OPEN** |

## 3. GPU time per frame, eye ≈ 50 % of the frame (clear + background + eye), GL_TIME_ELAPSED p50 ms

30 frames after 5, variants interleaved. p95 stayed within 1 % of p50 for every variant except one T-A C2 row; the
clocks were stable.

| Variant | 1024×768 front | ¾ | profile | 1920×1080 front | ¾ | profile |
|---|---|---|---|---|---|---|
| T-A C1 (Worklight) | 3.83 | 3.59 | 2.72 | 6.91 | 6.93 | 5.65 |
| T-A C2 (+ Ghost cornea) | 6.01 | 5.05 | 2.83 | 11.01 | 9.45 | 5.82 |
| T-B C1 / C2 / C3 | 0.95 / 0.93 / 0.94 | 0.84 / 0.83 / 0.84 | 0.66 / 0.67 / 0.67 | 2.26 / 2.25 / 2.29 | 2.03 / 2.00 / 2.02 | 1.62 / 1.64 / 1.64 |
| T-C C1 / C2 / C3 | 1.30 / 1.15 / 1.16 | 1.14 / 1.00 / 1.01 | 0.77 / 0.78 / 0.78 | 2.88 / 2.74 / 2.76 | 2.57 / 2.41 / 2.42 | 1.87 / 1.89 / 1.89 |
| T-D C1 / C2 / C3 | 2.81 / 2.50 / 2.75 | 2.42 / 2.15 / 2.34 | 1.44 / 1.48 / 1.49 | 5.85 / 5.53 / 5.83 | 5.19 / 4.82 / 5.05 | 3.43 / 3.48 / 3.50 |
| background alone | 0.31 | 0.31 | 0.31 | 0.81 | 0.81 | 0.81 |

CPU p50 of the submission: T-A 3.0–3.4 ms, T-B … T-D 4.6–7.3 ms.

**Readings [H]:**
1. **The target technique is cheap at eye scale.** T-C costs 0.11–0.35 ms (1024×768) and 0.25–0.62 ms (1920×1080)
   more than T-B, consistent with one or two cube lookups per fragment (probe 2026-11-13 §5: ≈ 0.1 ms per full-frame
   lookup at 1920×1080). The eye's own shading in T-C C2, background subtracted, is 0.5–0.8 ms at 1024×768 and
   1.1–1.9 ms at 1920×1080.
2. **The Worklight is the expensive one, as on the character:** T-A C1 costs 2.5–3.6× T-C C2 for the same eye. That is
   the face-data quad normal (RESULTS 2026-11-13 §6); the lab's techniques use plain interpolated normals. Input for
   D-L6.
3. **The production Ghost cornea is not free:** T-A C2 adds 2.2 ms (1024×768) and 4.1 ms (1920×1080) at the front
   view, because the Ghost draws the cornea through the same face-data program; the lab's shells add nothing
   measurable over C1.
4. **T-D is not a performance fallback:** 1.8–2.4× the GPU time of T-C. Each environment evaluation computes two
   rectangles (4 `atan`, 8 `erf` with `exp`) instead of one texture lookup. On a GPU where cube maps work, which this
   one does, T-D only matters if its look is preferred. INFERRED: a GPU without working cube maps would also be too
   slow for T-D.
5. **C1 vs C2 / C3:** C1 is slightly dearer in T-C / T-D (a second specular evaluation for every iris fragment)
   and the same in T-B; the shells cost nothing beyond their few cornea fragments.
6. **The background pass costs 0.31 / 0.81 ms**, about twice a fetch-free full-frame pass of the probe
   (0.144 / 0.377 ms). The likely reason [H] is that the shader's ternary also evaluates the analytic studio in "solid"
   mode. It is the same in every lab variant, so the comparison holds; it is not optimised, so that these numbers stay
   tied to the measured code.
7. **CPU:** the lab's submission is 1.5–4 ms dearer than T-A. That is lab Python (uniforms rebuilt and introspected
   per draw for five parts), not GPU work, and says nothing about a P2 pass that sets its state once per frame.

## 4. Reading for the decisions (input only; nothing decided here)

- **Q2 / §5.8 environment:** RGBA16F 128² cube, CPU-prefiltered, corners equalized, chain to 2², seamless on, works
  on the 9800 GTX with no seam and costs ≈ 0.2–0.6 ms at eye scale. Neither the RGBM8 fallback nor T-D is needed
  for capability on this PC. 256² costs 4 MiB and 71 s of one-off prefilter (cached).
- **D-L3 colour path:** shader-side sRGB decode is exact and cost nothing measurable; the hardware `SRGB8_ALPHA8`
  decode is ≈ 1 step of 8 bits off near white. Either works for an 8-bit iris image.
- **D-L6:** at eye scale, Lookdev with plain normals costs about a third of the Worklight with the quad normal; with
  RESULTS 2026-11-13 §6 (character, full frame: 26.8 vs 5.0 ms) this points the same way.
- **D-L8:** the eye at 50 % of a 1920×1080 frame costs ≤ 2.9 ms in T-C, frame included. The character in Lookdev is
  not measured (P1 scope).
- **Prefilter time:** 40 s per 128² chain on the Q9550 is fine for a cached studio and too slow for an environment the
  Artist edits live. INFERRED: a P2 with editable environments would prefilter on the GPU or at a lower sample
  budget; not needed for P1.

## 5. Probe bug found in this run, fixed after it

`probe_eye.py` counted coverage against the cleared colour hard-coded as RGB (26, 26, 28). The 9800 GTX stores
`glClearColor(0.1, 0.1, 0.11)` differently from Mesa, so every pixel counted as "eye": "measured coverage 100.0 %"
and, for the lab variants, "px != T-A C1" over the whole frame. Neither the timings nor any verdict depend on it:
T-A rows compare the whole frame anyway, and every lab variant differs from T-A. Fixed on 2026-11-14: the probe now
reads the cleared colour from an empty frame, and `test_a_small_probe_run_passes_every_check_and_cleans_up` checks
that coverage lies between 30 and 70 %. Container after the fix: 49.8–50.0 % at every view and size.

## 6. Raw output (Manu, pasted; the version / `git status` lines were not included)

```
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py -m pytest experiments\lookdev_eye_lab\tests -q
................................................                                                                   [100%]
48 passed in 166.91s (0:02:46)
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\lookdev_eye_lab\run.py --probe
Lookdev P1 Eye Proof probe (2026-11-14): environment, seams, sRGB, parity, variant timings, roughness sweep, screenshots
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10, numpy 2.2.6, pyglet 2.1.19
Interpreter: C:\Users\Manuel\Mirai_Bastel\.venv312\Scripts\python.exe
Source: commit 4a5fd77bed, src/ tree 94addddafd at HEAD / 94addddafd on disk, working tree MODIFIED
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
GL_VENDOR: NVIDIA Corporation
GL_SHADING_LANGUAGE_VERSION: 3.30 NVIDIA via Cg compiler
Context: core profile, flags 0; pyglet default config (as src/main.py)
Window 256x256 (hidden), framebuffer 256x256, scale 1.0, dpi 96; screens: 1200x1920
EVIDENCE: hardware renderer - label the results MEASURED [RPC] or MEASURED [MAIN] by machine.
Limits: TEXTURE_IMAGE_UNITS 32, COMBINED_TEXTURE_IMAGE_UNITS 96, TEXTURE_SIZE 8192, CUBE_MAP_TEXTURE_SIZE 8192, SAMPLES 16, COLOR_ATTACHMENTS 8, DRAW_BUFFERS 8, TEXTURE_BUFFER_SIZE 134217728, RENDERBUFFER_SIZE 8192, VIEWPORT_DIMS (8192, 8192), FRAGMENT_UNIFORM_COMPONENTS 2048, TEXTURE_LOD_BIAS 15.0, TEXTURE_MAX_ANISOTROPY 16.0
Extensions: GL_EXT_texture_filter_anisotropic, GL_NVX_gpu_memory_info, GL_ARB_seamless_cube_map, GL_ARB_texture_float, GL_ARB_half_float_pixel, GL_EXT_packed_float, GL_EXT_texture_shared_exponent, GL_EXT_texture_sRGB, GL_ARB_framebuffer_sRGB, GL_EXT_texture_sRGB_decode, GL_ARB_texture_storage, GL_ARB_timer_query, GL_ARB_texture_multisample, GL_ARB_debug_output, GL_KHR_debug, GL_EXT_texture_compression_s3tc
GPU memory (KiB): dedicated 524288, total available 524288, current available 368580, eviction count 753, evicted 607464

[E] environment: CPU prefilter (fresh, not from the cache) and upload; chain ends at 2^2, corners equalized
  studio 8554b77177bd: softbox az 35.0 el 25.0, 36 x 26 deg, radiance 8.0; strip radiance 4.0
  ambient (cosine-weighted mean radiance) sky 0.5083, ground 0.0467
  size mapping prefilter s samples per level                        roughness per level
    64  linear       25.47 [1, 512, 2048, 2048, 2048, 2048]         [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    64    sqrt       25.82 [1, 512, 2048, 2048, 2048, 2048]         [0.0, 0.04, 0.16, 0.36, 0.64, 1.0]
   128  linear       40.00 [1, 128, 512, 2048, 2048, 2048, 2048]    [0.0, 0.167, 0.333, 0.5, 0.667, 0.833, 1.0]
   128    sqrt       39.83 [1, 128, 512, 2048, 2048, 2048, 2048]    [0.0, 0.028, 0.111, 0.25, 0.444, 0.694, 1.0]
   256  linear       71.21 [1, 64, 128, 512, 2048, 2048, 2048, 2048] [0.0, 0.143, 0.286, 0.429, 0.571, 0.714, 0.857, 1.0]
   256    sqrt       71.24 [1, 64, 128, 512, 2048, 2048, 2048, 2048] [0.0, 0.02, 0.082, 0.184, 0.327, 0.51, 0.735, 1.0]
  size   format upload ms   computed   NVX drop  driver, errors
    64  RGBA16F      14.0   0.25 MiB   0.50 MiB  RGBA16F, R FLOAT 16 bit, no GL error
    64    RGBM8       8.8   0.12 MiB   0.50 MiB  RGBA8, R UNORM 8 bit, no GL error
   128  RGBA16F      16.2   1.00 MiB   0.01 MiB  RGBA16F, R FLOAT 16 bit, no GL error
   128    RGBM8      19.9   0.50 MiB   0.01 MiB  RGBA8, R UNORM 8 bit, no GL error
   256  RGBA16F      39.3   4.00 MiB   2.99 MiB  RGBA16F, R FLOAT 16 bit, no GL error
   256    RGBM8      61.9   2.00 MiB  -0.49 MiB  RGBA8, R UNORM 8 bit, no GL error

[S] seams, seamless on: check D's smooth 64^2 pattern, RGBA16F; jump = largest RGB step across the 12 edges
  level  size  raw chain (to 1^2)  lab chain (to 2^2, equalized)  tolerance
      0    64             0.00049                        0.00049    0.00195
      1    32             0.00003                        0.00003    0.00248
      2    16             0.00000                        0.00000    0.00498
      3     8             0.00049                        0.00049    0.01016
      4     4             0.00928                        0.00000    0.02095
      5     2             0.06201                        0.00000    0.00001
      6     1             0.16943         (not in the lab chain)
  -> PASS: no seam at any level of the lab chain

[Q5] sRGB decode, 256 codes (read-back target RGBA32F COMPLETE)
  GL_SRGB8_ALPHA8 vs the exact sRGB curve: max error 3.75e-03 (at code 251); shader-side decode of RGBA8 vs exact: 2.80e-08; GL errors: none
  -> PASS (threshold 2/255: hardware decode may use an 8-bit table)

[P] shader vs NumPy reference (parity.py, float32 inputs; read-back RGBA32F COMPLETE)
  function            max abs err  err / tol  failed  compared
  srgb_decode            3.16e-07      0.021       0       512
  srgb_encode            2.39e-07      0.012       0       512
  tonemap                9.48e-08      0.106       0       512
  ggx_vis_schlick        1.69e-06      0.004       0       512
  direct_specular        8.23e-06      0.012       0       512
  env_brdf_approx        1.58e-07      0.003       0       512
  lod_erf_box_lobe       7.06e-07      0.104       0       512
  env_radiance           0.000206      0.725       0       512
  td_env                 0.000262      0.147       0       512
  cornea_hit             5.81e-06      0.257       0       512
  display                2.58e-07      0.012       0       512
  -> PASS

[V] variants: frame = clear + background + viewport.render(); eye only, sclera disc ~ 50% of the frame; 30 frames after 5, variants interleaved; GPU = GL_TIME_ELAPSED, CPU = submission (frame call without glFinish)
  1024x768: target COMPLETE, camera distance 2.532 (predicted coverage 50.0%)
    view front: measured coverage (T-A C1, non-clear pixels) 100.0%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           3.83     3.86     3.76     3.87     2.99            0 (0%)  none
    T-A C2           6.01     6.07     5.94     9.70     4.74      185232 (24%)  none
    T-B C1           0.95     0.95     0.95     0.98     5.11     783734 (100%)  none
    T-B C2           0.93     0.93     0.93     0.95     5.86     783805 (100%)  none
    T-B C3           0.94     0.95     0.94     0.96     5.89     783805 (100%)  none
    T-C C1           1.30     1.32     1.29     1.33     5.52     786188 (100%)  none
    T-C C2           1.15     1.16     1.15     1.18     7.09     786198 (100%)  none
    T-C C3           1.16     1.17     1.16     1.18     6.97     786198 (100%)  none
    T-D C1           2.81     2.83     2.79     2.84     5.66     786170 (100%)  none
    T-D C2           2.50     2.51     2.48     2.53     7.14     786182 (100%)  none
    T-D C3           2.75     2.78     2.72     2.78     6.75     786182 (100%)  none
    background       0.31     0.31     0.31     0.31     1.41     786432 (100%)  none
    view three_quarter: measured coverage (T-A C1, non-clear pixels) 100.0%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           3.59     3.61     3.54     3.64     3.28            0 (0%)  none
    T-A C2           5.05     5.09     4.99     5.10     4.77      106616 (14%)  none
    T-B C1           0.84     0.84     0.84     0.85     5.01     785283 (100%)  none
    T-B C2           0.83     0.83     0.83     0.83     5.63     785309 (100%)  none
    T-B C3           0.84     0.84     0.83     0.84     5.80     785225 (100%)  none
    T-C C1           1.14     1.14     1.12     1.15     5.48     786247 (100%)  none
    T-C C2           1.00     1.01     1.00     1.01     6.99     786238 (100%)  none
    T-C C3           1.01     1.01     1.01     1.01     6.06     786238 (100%)  none
    T-D C1           2.42     2.45     2.40     2.49     5.70     786234 (100%)  none
    T-D C2           2.15     2.17     2.13     2.17     7.14     786222 (100%)  none
    T-D C3           2.34     2.37     2.30     2.37     7.06     786222 (100%)  none
    background       0.31     0.31     0.31     0.31     1.44     786432 (100%)  none
    view profile: measured coverage (T-A C1, non-clear pixels) 100.0%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           2.72     2.74     2.68     2.75     3.39            0 (0%)  none
    T-A C2           2.83     2.86     2.78     2.87     4.81         4892 (1%)  none
    T-B C1           0.66     0.66     0.66     0.67     4.88     786432 (100%)  none
    T-B C2           0.67     0.68     0.67     0.68     5.21     786432 (100%)  none
    T-B C3           0.67     0.67     0.67     0.68     5.86     786432 (100%)  none
    T-C C1           0.77     0.77     0.77     0.78     4.84     786432 (100%)  none
    T-C C2           0.78     0.78     0.78     0.78     6.65     786432 (100%)  none
    T-C C3           0.78     0.78     0.78     0.79     6.30     786432 (100%)  none
    T-D C1           1.44     1.44     1.43     1.44     5.54     786432 (100%)  none
    T-D C2           1.48     1.48     1.47     1.48     6.38     786432 (100%)  none
    T-D C3           1.49     1.50     1.48     1.50     6.65     786432 (100%)  none
    background       0.31     0.31     0.31     0.31     1.49     786432 (100%)  none

  1920x1080: target COMPLETE, camera distance 2.229 (predicted coverage 50.0%)
    view front: measured coverage (T-A C1, non-clear pixels) 100.0%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           6.91     6.95     6.86     6.97     3.43            0 (0%)  none
    T-A C2          11.01    11.09    10.94    11.10     4.35      548344 (26%)  none
    T-B C1           2.26     2.27     2.26     2.27     4.55    2065878 (100%)  none
    T-B C2           2.25     2.25     2.24     2.26     5.44    2066111 (100%)  none
    T-B C3           2.29     2.29     2.28     2.29     5.78    2066111 (100%)  none
    T-C C1           2.88     2.89     2.87     2.89     5.18    2072941 (100%)  none
    T-C C2           2.74     2.74     2.73     2.75     6.65    2072931 (100%)  none
    T-C C3           2.76     2.77     2.76     2.77     6.70    2072931 (100%)  none
    T-D C1           5.85     5.89     5.82     5.89     5.72    2072878 (100%)  none
    T-D C2           5.53     5.55     5.52     5.56     7.15    2072873 (100%)  none
    T-D C3           5.83     5.86     5.80     5.86     7.16    2072873 (100%)  none
    background       0.81     0.81     0.80     0.81     1.50    2073600 (100%)  none
    view three_quarter: measured coverage (T-A C1, non-clear pixels) 100.0%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           6.93     6.97     6.86     6.98     3.31            0 (0%)  none
    T-A C2           9.45     9.50     9.36     9.51     4.84      299124 (14%)  none
    T-B C1           2.03     2.04     2.03     2.04     5.10    2070601 (100%)  none
    T-B C2           2.00     2.01     2.00     2.01     5.83    2070659 (100%)  none
    T-B C3           2.02     2.02     2.01     2.03     5.76    2070442 (100%)  none
    T-C C1           2.57     2.59     2.56     2.59     5.20    2073080 (100%)  none
    T-C C2           2.41     2.41     2.40     2.41     6.57    2073061 (100%)  none
    T-C C3           2.42     2.42     2.41     2.42     7.03    2073061 (100%)  none
    T-D C1           5.19     5.23     5.15     5.24     5.85    2073060 (100%)  none
    T-D C2           4.82     4.83     4.80     4.84     7.30    2073017 (100%)  none
    T-D C3           5.05     5.07     5.02     5.07     6.88    2073017 (100%)  none
    background       0.81     0.81     0.80     0.81     1.47    2073600 (100%)  none
    view profile: measured coverage (T-A C1, non-clear pixels) 100.0%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           5.65     5.68     5.60     5.69     3.42            0 (0%)  none
    T-A C2           5.82     5.86     5.77     5.87     4.84         9442 (0%)  none
    T-B C1           1.62     1.62     1.62     1.62     4.64    2073600 (100%)  none
    T-B C2           1.64     1.64     1.64     1.64     5.85    2073600 (100%)  none
    T-B C3           1.64     1.64     1.63     1.64     5.85    2073600 (100%)  none
    T-C C1           1.87     1.88     1.87     1.88     5.60    2073600 (100%)  none
    T-C C2           1.89     1.89     1.88     1.89     6.81    2073600 (100%)  none
    T-C C3           1.89     1.89     1.89     1.90     7.06    2073600 (100%)  none
    T-D C1           3.43     3.43     3.42     3.43     5.68    2073600 (100%)  none
    T-D C2           3.48     3.48     3.48     3.48     7.16    2073600 (100%)  none
    T-D C3           3.50     3.50     3.49     3.51     6.87    2073600 (100%)  none
    background       0.81     0.81     0.81     0.81     1.49    2073600 (100%)  none

Screenshots: C:\Users\Manuel\Mirai_Bastel\experiments\lookdev_eye_lab\out\probe - eye_<view>_<technique>_<cornea>.png at 1024x768; sheet_<view>.png at half size: rows T-A..T-D, columns C1..C3 (T-A has C1 = no cornea, C2 = the production Ghost; its C3 cell is blank)

[W] roughness sweep: chrome sphere (F0 1), key light off, front view 512^2. Footprint = the softbox's own reflection: linear luminance of a softbox-only studio minus a backdrop-only one (Reinhard inverted); spread = its luminance-weighted variance in px^2
  T-C: r 0: 499, r 0.1: 574, r 0.25: 1088, r 0.5: 3185, r 0.75: 5657, r 1: 9505  -> monotonic
  T-D: r 0: 498, r 0.1: 517, r 0.25: 775, r 0.5: 2085, r 0.75: 4141, r 1: 5887  -> monotonic
  -> PASS

[R] resources and GL state
  lab objects: 19 texture, 1 buffer, 3 framebuffer, 6 renderbuffer, 1 query, 1 vertex_array; probe objects: 6 texture, 5 buffer, 3 framebuffer, 3 renderbuffer, 3 vertex_array, 1 program, 2 shader
  still alive after release: none
  GL state after vs before: identical
  glGetError at the end: none
  -> PASS

Summary (raw verdicts - label them by machine in the results file):
  PASS  S seams (lab chain)
  PASS  Q5 sRGB texture decode
  PASS  P parity
  PASS  V every variant renders without GL error and differs from T-A
  PASS  W roughness sweep monotonic
  PASS  R hygiene
```
