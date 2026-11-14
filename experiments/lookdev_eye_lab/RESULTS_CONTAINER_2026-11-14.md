# Lookdev P1 Eye Proof — container results, 2026-11-14 (TESTED [C] only)

**What this is:** the agent's validation run in the cloud container. **Not** the reference PC and not the main PC:
every RPC / MAIN cell is **OPEN**. Mesa **llvmpipe** is a CPU rasterizer: a PASS here shows the lab works and that a
spec-conformant implementation passes its checks; it says nothing about the GeForce 9800 GTX driver, and its
`GL_TIME_ELAPSED` values are **not GPU times** (they are in the raw output only to show the timing path works).
**Format:** [RESULTS_TEMPLATE.md](RESULTS_TEMPLATE.md). **Commands:** [README.md](README.md). **Reference-PC run:**
[RESULTS_REFERENCE_PC_2026-11-14.md](RESULTS_REFERENCE_PC_2026-11-14.md) (the OPEN RPC cells below are answered there,
except the Artist verdict).

## 1. Run record

| Field | Value |
|---|---|
| Machine | container (TESTED [C]); Intel Xeon @ 2.10 GHz, 4 logical cores, Linux 6.18 |
| Python, numpy, pyglet | 3.12.3, **2.2.6**, **2.1.19** (the reference PC's versions) in a scratch venv outside the repository; no repository dependency changed |
| Commit / `src/` tree | `11b767d659` / `94addddafd`, working tree clean for tracked files (the lab folder was untracked during the runs) |
| GL | `4.5 (Core Profile) Mesa 25.2.8` / `llvmpipe (LLVM 20.1.2, 256 bits)`, core profile, Xvfb |
| `EVIDENCE:` line | SOFTWARE RENDERER |
| Lab tests | `xvfb-run -a … pytest experiments/lookdev_eye_lab/tests`: **48 passed** (23 s); without a display: 35 passed, 13 skipped |
| Probe tests (unchanged, imported by the lab) | `pytest experiments/lookdev_gpu_probe/tests` under Xvfb: 33 passed |
| `git diff --stat src tests config` | empty |

## 2. Outcome

| Item | RPC | MAIN | C |
|---|---|---|---|
| [E] cube upload 64 / 128 / 256 × RGBA16F / RGBM8 | OPEN | OPEN | TESTED [C]: no GL error; driver reports `RGBA16F FLOAT 16` / `RGBA8 UNORM 8`; computed 0.25 / 1.00 / 4.00 MiB (RGBA16F, chain to 2²) |
| [E] CPU prefilter per chain | OPEN | OPEN | TESTED [C]: 4.2 s (64²), 6.3–6.4 s (128²), 13–14 s (256²) per mapping, single NumPy process; cached afterwards |
| [S] seams of the lab chain (to 2², corners equalized), seamless on | OPEN | OPEN | TESTED [C]: PASS — but llvmpipe takes the *mean* at corners, so the raw chain is seamless here too (0.00008 at every level). Only the RPC can show the fix-up working against the "one face" rule |
| [Q5] `GL_SRGB8_ALPHA8` decode vs exact | OPEN | OPEN | TESTED [C]: PASS, max error 1.2·10⁻³ (code 218); the shader-side decode of RGBA8 is exact to 1.4·10⁻⁷ |
| [P] parity, 11 `LIB_SRC` functions vs NumPy | OPEN | OPEN | TESTED [C]: PASS, every function ≤ 0.27 × its tolerance (abs. errors 8·10⁻⁸ … 7·10⁻⁵ on values up to ~10) |
| [V] 11 variants × 3 views × 2 sizes: GL errors | OPEN | OPEN | TESTED [C]: none |
| [V] image differs from T-A C1 | OPEN | OPEN | TESTED [C]: every variant; T-A C2 (Ghost cornea) by 1–26 % of the frame depending on the view, T-B … T-D on 99–100 % of the eye's pixels (other colour path) |
| [V] framing | OPEN | OPEN | TESTED [C]: the sclera disc covers 49.8–50.0 % of the frame at both sizes and all views (geometry, so the same on every machine) |
| [V] GPU time per variant | **OPEN** | OPEN | not meaningful (llvmpipe) |
| [W] roughness sweep, chrome sphere | OPEN | OPEN | TESTED [C]: monotonic in T-C (499 → 9507 px²) and T-D (498 → 5887 px²) over r 0 … 1; T-D grows less at r ≥ 0.5 (no GGX tail, as fitted) |
| [R] hygiene | OPEN | OPEN | TESTED [C]: PASS — every lab and probe GL object deleted, GL state identical, `glGetError` clean |
| T-A = production draw | OPEN | OPEN | TESTED [C]: pixel-identical (`test_t_a_is_the_production_draw_pixel_for_pixel`) |
| Interactive window: every key (with and without Shift), orbit, dolly, screenshot | OPEN | OPEN | TESTED [C] headless (scripted events under Xvfb): no GL error, screenshot written without the HUD |
| Artist verdict (KEEP / ITERATE / REJECT) | **OPEN** | OPEN | — (agent's look at the contact sheets: the softbox reads as a rectangle catchlight on the cornea in T-C / T-D, Fresnel darkens the limbus edge in C3; not a verdict) |

## 3. What the container run validates, and what it cannot

- **Validated [C]:** the seam under test (production `Viewport` + `EyeLabStore`, the same VertexList drawn by a lab
  program, T-A unchanged); the iris through the production UV / texture path (Q4); the GLSL terms equal their NumPy
  twins in float32; the prefilter and the cube upload in GL face order; the roughness sweep's monotonic blur; the
  framing; resource and state discipline; the colour path's sRGB decode is exact.
- **Needs the reference PC:** every GPU time; whether the corner fix-up removes the 9800 GTX's corner seams (its
  driver takes a corner tap from one face, RESULTS_REFERENCE_PC §4 — llvmpipe does not, so [S] cannot fail here);
  parity on NVIDIA's compiler; `GL_SRGB8_ALPHA8` on that driver; NVX memory figures; the CPU prefilter time on the
  Q9550; the Artist verdict.
- One finding for the RPC run to confirm: the probe's own [S] check compares the lab chain with the raw one, so the
  RPC output will show both the residual corner jumps (raw, expected ≈ 0.009 / 0.062 / 0.17 at 4² / 2² / 1²) and the
  equalized chain.

## 4. Raw output (`xvfb-run -a python experiments/lookdev_eye_lab/run.py --probe`)

```
Lookdev P1 Eye Proof probe (2026-11-14): environment, seams, sRGB, parity, variant timings, roughness sweep, screenshots
Platform: Linux-6.18.44-fc-v470-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.12.3, numpy 2.2.6, pyglet 2.1.19
Interpreter: <scratch>/venv312/bin/python
Source: commit 11b767d659, src/ tree 94addddafd, working tree clean
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
GL_VENDOR: Mesa
GL_SHADING_LANGUAGE_VERSION: 4.50
Context: core profile, flags 0; pyglet default config (as src/main.py)
Window 256x256 (hidden), framebuffer 256x256, scale 1.0, dpi 96; screens: 1280x1024
EVIDENCE: SOFTWARE RENDERER - TESTED [C] at best; GL_TIME_ELAPSED here is not a GPU time.
Limits: TEXTURE_IMAGE_UNITS 32, COMBINED_TEXTURE_IMAGE_UNITS 192, TEXTURE_SIZE 16384, CUBE_MAP_TEXTURE_SIZE 16384, SAMPLES 4, COLOR_ATTACHMENTS 8, DRAW_BUFFERS 8, TEXTURE_BUFFER_SIZE 134217728, RENDERBUFFER_SIZE 16384, VIEWPORT_DIMS (16384, 16384), FRAGMENT_UNIFORM_COMPONENTS 16384, TEXTURE_LOD_BIAS 16.0, TEXTURE_MAX_ANISOTROPY 16.0
Extensions: GL_EXT_texture_filter_anisotropic, GL_ARB_texture_filter_anisotropic, GL_NVX_gpu_memory_info, GL_ATI_meminfo, GL_ARB_seamless_cube_map, GL_AMD_seamless_cubemap_per_texture, GL_ARB_seamless_cubemap_per_texture, GL_ARB_texture_cube_map_array, GL_ARB_texture_float, GL_ARB_half_float_pixel, GL_EXT_packed_float, GL_EXT_texture_shared_exponent, GL_EXT_texture_sRGB, GL_ARB_framebuffer_sRGB, GL_EXT_texture_sRGB_decode, GL_ARB_texture_query_lod, GL_ARB_texture_storage, GL_ARB_timer_query, GL_ARB_texture_buffer_object_rgb32, GL_ARB_texture_multisample, GL_ARB_sample_shading, GL_ARB_debug_output, GL_KHR_debug, GL_EXT_texture_compression_s3tc, GL_ARB_texture_compression_bptc
GPU memory (KiB): dedicated 315693616, total available 332167392, current available 0, eviction count 32767, evicted -1412258944, texture free (ATI) 0

[E] environment: CPU prefilter (fresh, not from the cache) and upload; chain ends at 2^2, corners equalized
  studio 8554b77177bd: softbox az 35.0 el 25.0, 36 x 26 deg, radiance 8.0; strip radiance 4.0
  ambient (cosine-weighted mean radiance) sky 0.5083, ground 0.0467
  size mapping prefilter s samples per level                        roughness per level
    64  linear        4.23 [1, 512, 2048, 2048, 2048, 2048]         [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    64    sqrt        4.33 [1, 512, 2048, 2048, 2048, 2048]         [0.0, 0.04, 0.16, 0.36, 0.64, 1.0]
   128  linear        6.73 [1, 128, 512, 2048, 2048, 2048, 2048]    [0.0, 0.167, 0.333, 0.5, 0.667, 0.833, 1.0]
   128    sqrt        6.66 [1, 128, 512, 2048, 2048, 2048, 2048]    [0.0, 0.028, 0.111, 0.25, 0.444, 0.694, 1.0]
   256  linear       13.12 [1, 64, 128, 512, 2048, 2048, 2048, 2048] [0.0, 0.143, 0.286, 0.429, 0.571, 0.714, 0.857, 1.0]
   256    sqrt       13.70 [1, 64, 128, 512, 2048, 2048, 2048, 2048] [0.0, 0.02, 0.082, 0.184, 0.327, 0.51, 0.735, 1.0]
  size   format upload ms   computed   NVX drop  driver, errors
    64  RGBA16F       2.2   0.25 MiB   0.00 MiB  RGBA16F, R FLOAT 16 bit, no GL error
    64    RGBM8       1.7   0.12 MiB   0.00 MiB  RGBA8, R UNORM 8 bit, no GL error
   128  RGBA16F       2.6   1.00 MiB   0.00 MiB  RGBA16F, R FLOAT 16 bit, no GL error
   128    RGBM8       3.3   0.50 MiB   0.00 MiB  RGBA8, R UNORM 8 bit, no GL error
   256  RGBA16F      10.0   4.00 MiB   0.00 MiB  RGBA16F, R FLOAT 16 bit, no GL error
   256    RGBM8      15.7   2.00 MiB   0.00 MiB  RGBA8, R UNORM 8 bit, no GL error

[S] seams, seamless on: check D's smooth 64^2 pattern, RGBA16F; jump = largest RGB step across the 12 edges
  level  size  raw chain (to 1^2)  lab chain (to 2^2, equalized)  tolerance
      0    64             0.00008                        0.00008    0.00122
      1    32             0.00008                        0.00008    0.00248
      2    16             0.00008                        0.00008    0.00498
      3     8             0.00008                        0.00008    0.01016
      4     4             0.00008                        0.00008    0.02095
      5     2             0.00008                        0.00000    0.00034
      6     1             0.00008         (not in the lab chain)
  -> PASS: no seam at any level of the lab chain

[Q5] sRGB decode, 256 codes (read-back target RGBA32F COMPLETE)
  GL_SRGB8_ALPHA8 vs the exact sRGB curve: max error 1.19e-03 (at code 218); shader-side decode of RGBA8 vs exact: 1.35e-07; GL errors: none
  -> PASS (threshold 2/255: hardware decode may use an 8-bit table)

[P] shader vs NumPy reference (parity.py, float32 inputs; read-back RGBA32F COMPLETE)
  function            max abs err  err / tol  failed  compared
  srgb_decode               4e-07      0.022       0       512
  srgb_encode            1.62e-07      0.016       0       512
  tonemap                8.03e-08      0.093       0       512
  ggx_vis_schlick        1.69e-06      0.002       0       512
  direct_specular        8.45e-06      0.007       0       512
  env_brdf_approx        1.38e-07      0.002       0       512
  lod_erf_box_lobe       4.16e-07      0.055       0       512
  env_radiance           6.58e-05      0.268       0       512
  td_env                 4.47e-05      0.149       0       512
  cornea_hit             5.81e-06      0.252       0       512
  display                2.03e-07      0.010       0       512
  -> PASS

[V] variants: frame = clear + background + viewport.render(); eye only, sclera disc ~ 50% of the frame; 30 frames after 5, variants interleaved; GPU = GL_TIME_ELAPSED, CPU = submission (frame call without glFinish)
  1024x768: target COMPLETE, camera distance 2.532 (predicted coverage 50.0%)
    view front: measured coverage (T-A C1, non-clear pixels) 50.0%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           0.19     2.17     0.09     4.39     1.39            0 (0%)  none
    T-A C2           0.18     0.58     0.02    12.52     1.92      185214 (24%)  none
    T-B C1           0.10     2.94     0.05     6.45     1.95      390181 (99%)  none
    T-B C2           0.10     2.66     0.04    10.02     2.52      390239 (99%)  none
    T-B C3           0.10     1.70     0.06     9.86     2.51      390239 (99%)  none
    T-C C1           0.21     0.31     0.07    14.55     2.15     392623 (100%)  none
    T-C C2           0.21     2.56     0.06    15.74     2.69     392620 (100%)  none
    T-C C3           0.21     0.60     0.05    15.83     2.76     392620 (100%)  none
    T-D C1           0.22     3.19     0.06    15.18     2.03     392603 (100%)  none
    T-D C2           0.21     0.34     0.05    16.72     2.68     392606 (100%)  none
    T-D C3           0.23     6.20     0.05    19.49     2.58     392606 (100%)  none
    background       0.07     0.13     0.06     3.36     0.54     786432 (100%)  none
    view three_quarter: measured coverage (T-A C1, non-clear pixels) 49.9%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           0.21     3.80     0.01     4.00     1.32            0 (0%)  none
    T-A C2           0.20     0.48     0.09    13.57     1.93      106614 (14%)  none
    T-B C1           0.14     3.62     0.05     9.45     2.11     391395 (100%)  none
    T-B C2           0.11     4.30     0.05    13.92     2.45     391432 (100%)  none
    T-B C3           0.16     4.44     0.05    11.37     2.46     391346 (100%)  none
    T-C C1           0.25     2.96     0.05    11.28     2.10     392360 (100%)  none
    T-C C2           0.24     1.47     0.05    16.51     2.57     392363 (100%)  none
    T-C C3           0.24     2.16     0.06    13.15     2.58     392363 (100%)  none
    T-D C1           0.21     0.30     0.06    12.21     2.04     392352 (100%)  none
    T-D C2           0.22    11.32     0.07    19.18     2.74     392355 (100%)  none
    T-D C3           0.22     1.91     0.06    15.86     2.58     392355 (100%)  none
    background       0.08     0.11     0.06     2.14     0.50     786432 (100%)  none
    view profile: measured coverage (T-A C1, non-clear pixels) 49.9%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           0.25     3.64     0.02     4.52     1.24            0 (0%)  none
    T-A C2           0.21     3.04     0.02    12.93     1.58         4892 (1%)  none
    T-B C1           0.17     3.88     0.07     8.46     1.95     392730 (100%)  none
    T-B C2           0.16     4.21     0.06     9.67     2.28     392730 (100%)  none
    T-B C3           0.09     2.48     0.04     9.94     2.36     392730 (100%)  none
    T-C C1           0.24     4.26     0.06    11.97     1.86     392730 (100%)  none
    T-C C2           0.21     2.17     0.08    12.58     2.42     392730 (100%)  none
    T-C C3           0.24     3.61     0.06    10.60     2.42     392730 (100%)  none
    T-D C1           0.26     3.25     0.05     9.43     1.99     392730 (100%)  none
    T-D C2           0.23     3.72     0.05     9.60     2.76     392730 (100%)  none
    T-D C3           0.24     5.70     0.06    12.61     2.43     392730 (100%)  none
    background       0.08     0.82     0.05     2.39     0.51     786432 (100%)  none

  1920x1080: target COMPLETE, camera distance 2.229 (predicted coverage 50.0%)
    view front: measured coverage (T-A C1, non-clear pixels) 50.0%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           0.30     0.49     0.01     2.32     1.76            0 (0%)  none
    T-A C2           0.28     1.28     0.11    35.16     2.54      548285 (26%)  none
    T-B C1           0.09     0.23     0.04    22.28     3.03     1028088 (99%)  none
    T-B C2           0.08     0.28     0.04    26.74     3.39     1028239 (99%)  none
    T-B C3           0.08     4.50     0.06    26.22     3.18     1028239 (99%)  none
    T-C C1           0.10     0.92     0.06    32.59     2.42    1035129 (100%)  none
    T-C C2           0.21     0.39     0.05    29.29     3.19    1035126 (100%)  none
    T-C C3           0.10     0.40     0.04    29.79     3.22    1035126 (100%)  none
    T-D C1           0.09     1.54     0.05    30.14     2.62    1035086 (100%)  none
    T-D C2           0.07     0.41     0.05    34.63     3.42    1035095 (100%)  none
    T-D C3           0.11     1.09     0.06    34.26     3.42    1035095 (100%)  none
    background       0.07     3.91     0.05     8.78     0.76    2073600 (100%)  none
    view three_quarter: measured coverage (T-A C1, non-clear pixels) 49.8%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           0.27     0.39     0.01     6.32     1.64            0 (0%)  none
    T-A C2           0.28     0.39     0.03    26.86     2.10      299121 (14%)  none
    T-B C1           0.07     1.59     0.05    20.67     2.49    1030049 (100%)  none
    T-B C2           0.07     0.14     0.05    19.49     2.97    1030135 (100%)  none
    T-B C3           0.07     0.24     0.05    17.36     2.84    1029912 (100%)  none
    T-C C1           0.20     6.03     0.05    29.52     2.60    1032560 (100%)  none
    T-C C2           0.29     6.54     0.06    29.40     3.31    1032550 (100%)  none
    T-C C3           0.09     0.37     0.06    29.91     3.47    1032550 (100%)  none
    T-D C1           0.11     1.31     0.05    24.99     2.87    1032538 (100%)  none
    T-D C2           0.13     0.44     0.06    26.24     3.83    1032532 (100%)  none
    T-D C3           0.09     0.34     0.05    27.96     3.06    1032532 (100%)  none
    background       0.08     3.86     0.05     8.45     0.69    2073600 (100%)  none
    view profile: measured coverage (T-A C1, non-clear pixels) 50.0%
    variant       GPU p50      p95      min      max  CPU p50      px != T-A C1  GL errors (px: eye only; T-A: frame)
    T-A C1           0.28     0.54     0.07     0.69     1.86            0 (0%)  none
    T-A C2           0.28     0.39     0.17    17.99     2.12         9442 (0%)  none
    T-B C1           0.07     0.24     0.05    14.49     2.62    1036654 (100%)  none
    T-B C2           0.08     1.73     0.05    17.02     2.76    1036654 (100%)  none
    T-B C3           0.08     0.47     0.05    12.93     2.48    1036654 (100%)  none
    T-C C1           0.09     0.51     0.06    22.82     2.24    1036654 (100%)  none
    T-C C2           0.22     2.64     0.05    20.69     2.82    1036654 (100%)  none
    T-C C3           0.09     0.36     0.05    22.24     2.89    1036654 (100%)  none
    T-D C1           0.08     0.35     0.04    26.07     2.80    1036654 (100%)  none
    T-D C2           0.11     0.67     0.05    23.50     3.33    1036654 (100%)  none
    T-D C3           0.27     1.32     0.05    23.79     3.27    1036654 (100%)  none
    background       0.09     2.10     0.06     5.98     0.71    2073600 (100%)  none

Screenshots: /home/user/Mirai-Bastel/experiments/lookdev_eye_lab/out/probe - eye_<view>_<technique>_<cornea>.png at 1024x768; sheet_<view>.png at half size: rows T-A..T-D, columns C1..C3 (T-A has C1 = no cornea, C2 = the production Ghost; its C3 cell is blank)

[W] roughness sweep: chrome sphere (F0 1), key light off, front view 512^2. Footprint = the softbox's own reflection: linear luminance of a softbox-only studio minus a backdrop-only one (Reinhard inverted); spread = its luminance-weighted variance in px^2
  T-C: r 0: 499, r 0.1: 574, r 0.25: 1088, r 0.5: 3186, r 0.75: 5656, r 1: 9507  -> monotonic
  T-D: r 0: 498, r 0.1: 517, r 0.25: 775, r 0.5: 2085, r 0.75: 4142, r 1: 5887  -> monotonic
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
