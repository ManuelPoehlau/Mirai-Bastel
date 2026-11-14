# P1c soft limbus — container validation (2026-11-14)

Evidence: **TESTED [C]** (container, Mesa llvmpipe software renderer). GL_TIME_ELAPSED under llvmpipe is **not a GPU
time**: the [V] numbers below only show that every run renders without GL error. GPU cost per level: reference PC
(README "P1c", commands there). No Artist verdict here.

## Tests

- `xvfb-run -a python -m pytest experiments/lookdev_eye_lab/tests -q`: **186 passed** = 121 before this session
  + 32 radial fit (26 headless + 6 GL) + 9 `hold_outer_color` (7 headless + 2 GL) + 24 P1c (8 headless + 16 GL).
- Without a display: 132 passed, 54 skipped (the GL tests).

## What the probe shows (both runs: four PASS)

- **[P]** every limbus function matches its NumPy twin (max error 2.8e-6; `sclera_u` uses `atan2` because GLSL `acos`
  was off by 7.6e-5 near the ring in float32 — found by the parity test, fixed in both twins).
- **[I]** L0 renders P1b V2 / V3 pixel for pixel (T-B / T-C / T-D, front / 3/4 / profile) — with the procedural iris
  and with a custom image + the A+H sidecar (`{"pupil": 0.22, "limbus": 0.88, "hold_outer_color": true}`).
- **[C]** (numbers, no verdict): in the 3/4 and steep views L0's largest step across the ring sits *on* the ring
  (@ −0.02 mm, the seam / bright rim, ~72 of 255); from L1 on it is ~18 and moves inward. In the front view the largest
  step in L0 … L2 sits at −0.17 mm, the edge where the visible iris meets the limbal tissue; L3 (translucent tissue)
  lowers it from ~42–45 to ~16. Profile: no radial line is fully visible (n 0).
- **[R]** GL state and resources as found.

The custom-image run used a **stand-in** (the procedural iris moved to the profile measured on Manu's texture: pupil
0.22, iris edge 0.90, white outside) in a scratch folder — not Manu's file, and not the lab's `out/`.

## Raw output — procedural iris (`--draws 5 --sizes 1024x768`)

```
Lookdev P1c soft limbus probe (2026-11-14): parity, L0 identity, continuity, timings, contact sheet
Platform: Linux-6.18.44-fc-v470-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.12.3, numpy 2.2.6, pyglet 2.1.19
Interpreter: <scratch>/venv312/bin/python
Source: commit 38e2fcd2d4, src/ tree 94addddafd at HEAD / 94addddafd on disk, working tree MODIFIED
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
GL_VENDOR: Mesa
GL_SHADING_LANGUAGE_VERSION: 4.50
Context: core profile, flags 0; pyglet default config (as src/main.py)
Window 256x256 (hidden), framebuffer 256x256, scale 1.0, dpi 96; screens: 1280x1024
EVIDENCE: SOFTWARE RENDERER - TESTED [C] at best; GL_TIME_ELAPSED here is not a GPU time.
Limits: TEXTURE_IMAGE_UNITS 32, COMBINED_TEXTURE_IMAGE_UNITS 192, TEXTURE_SIZE 16384, CUBE_MAP_TEXTURE_SIZE 16384, SAMPLES 4, COLOR_ATTACHMENTS 8, DRAW_BUFFERS 8, TEXTURE_BUFFER_SIZE 134217728, RENDERBUFFER_SIZE 16384, VIEWPORT_DIMS (16384, 16384), FRAGMENT_UNIFORM_COMPONENTS 16384, TEXTURE_LOD_BIAS 16.0, TEXTURE_MAX_ANISOTROPY 16.0
Extensions: GL_EXT_texture_filter_anisotropic, GL_ARB_texture_filter_anisotropic, GL_NVX_gpu_memory_info, GL_ATI_meminfo, GL_ARB_seamless_cube_map, GL_AMD_seamless_cubemap_per_texture, GL_ARB_seamless_cubemap_per_texture, GL_ARB_texture_cube_map_array, GL_ARB_texture_float, GL_ARB_half_float_pixel, GL_EXT_packed_float, GL_EXT_texture_shared_exponent, GL_EXT_texture_sRGB, GL_ARB_framebuffer_sRGB, GL_EXT_texture_sRGB_decode, GL_ARB_texture_query_lod, GL_ARB_texture_storage, GL_ARB_timer_query, GL_ARB_texture_buffer_object_rgb32, GL_ARB_texture_multisample, GL_ARB_sample_shading, GL_ARB_debug_output, GL_KHR_debug, GL_EXT_texture_compression_s3tc, GL_ARB_texture_compression_bptc
GPU memory (KiB): dedicated 582214592, total available 598688368, current available 0, eviction count 32766, evicted -709867680, texture free (ATI) 0

iris texture: procedural iris.png - 512x512 generated
Lighting / camera for every run: key az 35 el 25 E 3, environment on yaw 0 x1, exposure +0 EV, tonemap 1; close-up distance per frame size
limbus L0 (P1b as is)   colour shader 'P1b dark'   asymmetry off (0.55 mm)
band 1.00 mm   strength 1.00   normal blend +-0.50 mm   translucency falloff 4.00

[P] limbus GLSL vs limbus_model (limbus_parity.py, float32 inputs; read-back COMPLETE)
  function          max abs err  failed  compared    tolerance
  coords               2.82e-06       0      1024        5e-06
  weights              2.83e-07       0      1024        2e-05
  normal_blend         1.09e-07       0      1024        5e-06
  sclera_through       4.18e-07       0      1024       0.0002
  tint                 9.35e-08       0      1024        5e-06
  -> PASS

[I] L0 against P1b (480x360, every technique T-B ... T-D, V2 and V3, every view)
  differing: none  -> PASS

[C] continuity across the ring (1024x768, eye ~50 %, T-C V2): largest luminance step (0..255) between samples 0.05 mm apart within +-1.5 mm, per radial line; median / p95 over the lines, @ = median position of that step in mm from the ring (- = cornea side; the chamber angle is at -0.29); n = lines fully facing the camera (0: none, e.g. profile). Numbers only - no verdict.
  view                                L0                    L1                    L2                    L3               L3 asym             L3 imgcol
  front            45.5/ 77.7 @-0.17 n64 34.6/ 70.7 @-0.17 n64 34.0/ 56.0 @-0.17 n64 15.7/ 22.1 @-0.17 n64 11.1/ 17.1 @-0.17 n64 12.9/ 19.0 @+0.00 n64
  three_quarter    74.4/ 98.1 @-0.02 n34 18.0/ 33.1 @-0.12 n34 18.8/ 33.2 @-0.12 n34 17.7/ 32.8 @-0.72 n34 16.9/ 30.2 @-0.97 n34 18.8/ 35.3 @-0.50 n34
  profile           nan/  nan @ +nan n0   nan/  nan @ +nan n0   nan/  nan @ +nan n0   nan/  nan @ +nan n0   nan/  nan @ +nan n0   nan/  nan @ +nan n0 
  steep_75         72.3/ 86.0 @-0.02 n19 17.9/ 28.1 @-0.27 n19 18.3/ 29.3 @-0.27 n19 17.4/ 25.0 @-0.42 n19 17.7/ 21.4 @-0.42 n19 17.5/ 25.8 @-0.22 n19
  key sweep, 3/4 view: per azimuth the p95 step (T-C V2)
  azimuth                       L0              L1              L2              L3
  -60                         93.1            62.5            58.9            40.3
  -45                         92.5            58.3            64.9            44.0
  -30                         95.6            50.7            54.5            38.6
  -15                         96.8            45.1            47.7            36.6
  0                           97.8            46.4            41.3            35.0
  15                          98.5            56.5            39.9            34.1
  30                          98.0            34.1            34.8            32.5
  45                          99.9            51.2            31.1            30.2
  60                         101.7            36.2            32.5            32.1

[V] GPU time per frame (clear + background + eye), eye ~50 % of the frame, 5 frames after 5, runs interleaved; ms
  1024x768: target COMPLETE
    view front
    run                     GPU p50      p95      min      max  CPU p50  GL errors
    T-C V2 L0                  0.24     0.27     0.11     0.28     2.53  none
    T-C V2 L1                  0.18     0.26     0.06     0.27     2.06  none
    T-C V2 L2                  0.20     2.08     0.08     2.54     2.06  none
    T-C V2 L3                  0.34     0.40     0.06     0.41     2.33  none
    T-C V2 L3 asym             0.26     0.28     0.08     0.28     2.67  none
    T-C V3 L0                  0.12     0.22     0.07     0.23     2.50  none
    T-C V3 L3                  0.32     2.73     0.07     3.32     2.65  none
    T-B V2 L0                  0.19     2.52     0.08     2.79     2.43  none
    T-B V2 L3                  0.25     2.32     0.08     2.77     2.66  none
    T-D V2 L0                  0.09     0.21     0.08     0.23     2.59  none
    T-D V2 L3                  0.30     0.33     0.07     0.33     2.80  none
    view three_quarter
    run                     GPU p50      p95      min      max  CPU p50  GL errors
    T-C V2 L0                  0.12     0.26     0.07     0.27     1.92  none
    T-C V2 L1                  0.21     0.26     0.17     0.26     2.15  none
    T-C V2 L2                  0.24     0.31     0.06     0.33     2.23  none
    T-C V2 L3                  0.08     0.28     0.06     0.30     1.84  none
    T-C V2 L3 asym             0.27     0.28     0.09     0.29     2.38  none
    T-C V3 L0                  0.20     0.23     0.07     0.24     1.82  none
    T-C V3 L3                  0.28     0.32     0.22     0.32     2.02  none
    T-B V2 L0                  0.09     0.94     0.05     1.15     1.87  none
    T-B V2 L3                  0.23     0.26     0.07     0.26     1.89  none
    T-D V2 L0                  0.21     2.23     0.16     2.73     1.97  none
    T-D V2 L3                  0.27     0.33     0.10     0.33     2.29  none
    view profile
    run                     GPU p50      p95      min      max  CPU p50  GL errors
    T-C V2 L0                  0.07     1.25     0.07     1.51     1.69  none
    T-C V2 L1                  0.08     2.96     0.06     3.48     1.77  none
    T-C V2 L2                  0.25     0.38     0.06     0.41     2.06  none
    T-C V2 L3                  0.37     2.86     0.07     3.04     1.88  none
    T-C V2 L3 asym             0.30     0.37     0.05     0.38     1.94  none
    T-C V3 L0                  0.26     0.52     0.20     0.55     1.86  none
    T-C V3 L3                  0.32     0.38     0.05     0.38     1.91  none
    T-B V2 L0                  0.18     2.67     0.07     2.96     1.85  none
    T-B V2 L3                  0.24     2.18     0.08     2.66     1.84  none
    T-D V2 L0                  0.10     0.23     0.05     0.23     1.65  none
    T-D V2 L3                  0.25     0.33     0.15     0.34     1.76  none

Screenshots: <scratch>/probe_proc - limbus_<view>_<run>.png (1024x768); limbus_sheet.png: limbus crops 400^2, columns T-C V2 L0 | T-C V2 L1 | T-C V2 L2 | T-C V2 L3 | T-C V2 L3 asym | T-C V2 L3 imgcol; rows front / three_quarter / profile / steep_75 / three_quarter_key-45

[R] resources and GL state
  lab objects: 1 texture, 1 buffer, 4 framebuffer, 8 renderbuffer, 1 query, 1 vertex_array 1 texture, 1 buffer, 1 vertex_array; probe objects: 1 texture, 2 buffer, 1 framebuffer, 1 renderbuffer, 1 query, 1 vertex_array
  still alive after release: none
  GL state after vs before: identical
  glGetError at the end: none
  -> PASS

Summary (raw verdicts - label them by machine in the results file):
  PASS  P limbus parity
  PASS  I L0 = P1b pixel for pixel
  PASS  V every run renders without GL error
  PASS  R hygiene
```

## Raw output — stand-in image + A+H sidecar, header and [P] / [I] / [C]

```
iris texture: CUSTOM iris_custom.png - 512x512, 8-bit RGB, sha1 619bf9e7b784; radial fit iris_custom.json: image pupil 0.220 -> 0.268, image iris edge 0.880 -> 0.819 (limbus), outer colour held
Lighting / camera for every run: key az 35 el 25 E 3, environment on yaw 0 x1, exposure +0 EV, tonemap 1; close-up distance per frame size
limbus L0 (P1b as is)   colour shader 'P1b dark'   asymmetry off (0.55 mm)
band 1.00 mm   strength 1.00   normal blend +-0.50 mm   translucency falloff 4.00

[P] limbus GLSL vs limbus_model (limbus_parity.py, float32 inputs; read-back COMPLETE)
  function          max abs err  failed  compared    tolerance
  coords               2.82e-06       0      1024        5e-06
  weights              2.83e-07       0      1024        2e-05
  normal_blend         1.09e-07       0      1024        5e-06
  sclera_through       4.18e-07       0      1024       0.0002
  tint                 9.35e-08       0      1024        5e-06
  -> PASS

[I] L0 against P1b (480x360, every technique T-B ... T-D, V2 and V3, every view)
  differing: none  -> PASS

[C] continuity across the ring (1024x768, eye ~50 %, T-C V2): largest luminance step (0..255) between samples 0.05 mm apart within +-1.5 mm, per radial line; median / p95 over the lines, @ = median position of that step in mm from the ring (- = cornea side; the chamber angle is at -0.29); n = lines fully facing the camera (0: none, e.g. profile). Numbers only - no verdict.
  view                                L0                    L1                    L2                    L3               L3 asym             L3 imgcol
  front            42.1/ 66.4 @-0.17 n64 45.2/ 72.6 @-0.17 n64 43.4/ 66.9 @-0.17 n64 15.7/ 22.5 @-0.17 n64 11.0/ 15.3 @-0.17 n64 12.4/ 18.3 @+0.03 n64
  three_quarter    72.4/ 92.8 @-0.02 n34 18.3/ 40.4 @-0.22 n34 18.6/ 35.9 @-0.37 n34 18.3/ 32.8 @-0.50 n34 16.3/ 28.8 @-0.87 n34 17.7/ 35.2 @-0.50 n34
  profile           nan/  nan @ +nan n0   nan/  nan @ +nan n0   nan/  nan @ +nan n0   nan/  nan @ +nan n0   nan/  nan @ +nan n0   nan/  nan @ +nan n0 
  steep_75         71.3/ 87.6 @-0.02 n19 18.4/ 28.3 @-0.22 n19 18.4/ 29.2 @-0.12 n19 18.1/ 25.2 @-0.27 n19 18.4/ 20.3 @-0.42 n19 18.3/ 26.4 @-0.22 n19
  key sweep, 3/4 view: per azimuth the p95 step (T-C V2)
  azimuth                       L0              L1              L2              L3
  -60                         84.3            64.3            64.3            39.9
  -45                         83.0            60.1            70.6            42.3
  -30                         81.8            52.5            60.6            38.7
  -15                         83.5            48.5            53.5            36.2
  0                           88.4            44.8            48.0            35.7
  15                          97.0            54.1            42.1            34.7
  30                          92.6            40.6            37.3            31.6
  45                          95.6            54.7            34.9            29.4
  60                         100.2            39.4            33.9            27.5
```
