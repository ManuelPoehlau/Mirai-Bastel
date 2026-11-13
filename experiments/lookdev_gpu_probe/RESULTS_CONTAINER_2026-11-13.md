# Lookdev GPU probe — container results, 2026-11-13 (TESTED [C] only)

**What this is:** the agent's validation run in the cloud container. **Not** the reference PC and not the main PC:
every RPC / MAIN cell below is **OPEN**. Mesa **llvmpipe** is a CPU rasterizer. A PASS here shows that the probe works
and that a spec-conformant implementation passes it. It says nothing about the GeForce 9800 GTX driver, and its
GL_TIME_ELAPSED values are not GPU times (§5).
**Format:** [RESULTS_TEMPLATE.md](RESULTS_TEMPLATE.md). **Commands:** [README.md](README.md).

## 1. Run record

| Field | Value |
|---|---|
| Machine | container (TESTED [C]) |
| Date | 2026-11-13 (agent) |
| Commit / `src/` tree | `a37ca9df33` / `94addddafd` (= `git rev-parse a37ca9d:src`), working tree clean for tracked files; the lab folder was untracked during the runs |
| Python, numpy, pyglet | 3.12.3, **2.2.6**, **2.1.19**: the reference PC's NumPy and pyglet, in a scratch venv outside the repository (`uv venv -p python3.12` + `numpy==2.2.6 pyglet==2.1.19 pytest`); no repository dependency changed |
| OS, CPU | Linux 6.18 (glibc 2.39), Intel Xeon @ 2.10 GHz, 4 logical cores |
| GL | `4.5 (Core Profile) Mesa 25.2.8` / `llvmpipe (LLVM 20.1.2, 256 bits)` / Mesa / GLSL 4.50; core profile; Xvfb |
| `EVIDENCE:` line | SOFTWARE RENDERER |

## 2. Outcome

| Item | RPC | MAIN | C |
|---|---|---|---|
| A allocation + sampling 64²–512²: RGBA8 / RGBA16F (half) / RGBA16F (float data) / RGBA32F | OPEN | OPEN | TESTED [C]: PASS ×4; driver reports `RGBA8 UNORM 8`, `RGBA16F FLOAT 16`, `RGBA32F FLOAT 32` |
| B `textureLod` explicit levels (lod −1 … 8.5) | OPEN | OPEN | TESTED [C]: PASS ×3 (120/120 exact) |
| C bilinear (fifths of a texel) | OPEN | OPEN | TESTED [C]: PASS ×3, error 0.0000 texel step |
| C trilinear (lod in 0.1 steps) | OPEN | OPEN | TESTED [C]: PASS ×3, error 0.0000 level step, monotonic |
| D seams | OPEN | OPEN | TESTED [C]: PASS ×3. On: jump ≤ 0.0001 at every level. Off: the predicted clamp seams (0.012 at 64² … 0.85 at 1×1), matching the clamp-to-edge emulation to 6·10⁻⁸ (float) / 0.0024 (RGBA8) |
| D panoramas | OPEN | OPEN | TESTED [C]: looked at. Off shows the face borders at lod 3 / 5 / 6; on is smooth |
| R hygiene: objects deleted, `glIs*` false, state identical, `glGetError` clean | OPEN | OPEN | TESTED [C]: PASS (29 textures, 3 buffers, 3 FBOs, 3 renderbuffers, 1 query, 2 VAOs, 2 programs, 4 shaders made and released) |
| Read-back target `RGBA32F` colour renderbuffer | OPEN | OPEN | TESTED [C]: COMPLETE |
| T full-frame fetch cost | OPEN | OPEN | TESTED [C]: runs, no GL error; **values not GPU times** (§5) |
| `drag_cost/probe_shading_gpu.py`, 1024×768 and 1920×1080 | OPEN | OPEN | TESTED [C]: crashes unmodified (§4); via a scratch runner: all images `identical` |
| `probe_worklight_coverage.py`, both sizes | OPEN | OPEN | TESTED [C]: coverage 14.3 / 62.2 / 98.3 % (1024×768), 10.7 / 46.7 / 99.4 % (1920×1080); images `identical` at every dolly |
| Lab tests: 27 headless + 3 GL (`xvfb-run`) | OPEN | OPEN | TESTED [C]: 30 passed; without pyglet: 27 passed, 3 skipped |

The limits and extensions are llvmpipe's own (GL 4.5, all relevant extensions present). They are recorded in the raw
output only to show that the queries work. They are no indication of the 9800 GTX's values.

## 3. What the container run validates, and what it cannot

- **Validated [C]:**
  - The probe's plumbing: it builds the cubes in GL face order and reads values back through a GLSL 330 `textureLod`
    pass.
  - The expected values and tolerances: a conformant implementation passes A–D with large margins.
  - The seam test is discriminating: off shows the seams that GL's non-seamless rule predicts, and on removes them.
  - The resource and state discipline.
  - The coverage wrapper reaches a frame-filling close-up without touching the drag_cost probe's image check.
- **Not validated, needs the reference PC:**
  - Whether the 9800 GTX driver stores `RGBA16F` / `RGBA32F` cubes as float, filters them, honours
    `GL_TEXTURE_CUBE_MAP_SEAMLESS`, and selects mips correctly.
  - Every GPU time (T, the Worklight baseline, the close-up coverage runs).
  - Video-memory figures (`GL_NVX_gpu_memory_info`).
  - Whether a hidden 1920×1080 window keeps that size on the reference PC's screen.
- One small driver difference seen here: Mesa converts float client data to `RGBA16F` with a result one half-float
  step away from NumPy's rounding (max error 0.000244 at 0.4). It is within tolerance. If the Eye Proof wants
  reproducible environment bytes, it should upload half-float data it rounded itself (`numpy.float16`), which is the
  `RGBA16F` (half) path of check A.

## 4. Finding: `drag_cost/probe_shading_gpu.py` crashes when every GPU time is small

Run unmodified here, the probe measures and then raises in its power-management NOTE check (line 257):

```
  File "experiments/drag_cost/probe_shading_gpu.py", line 257, in measure
    if max(max(v) for v in samples.values()) > 2.5 * min(min(v) for v in samples.values() if min(v) > 0.5) \
ValueError: min() iterable argument is empty
```

It happens when no variant's fastest draw exceeds 0.5 ms. The reference PC is not affected: its face-data pass costs
≥ 1.9 ms. A fast main-PC GPU at 1024×768 may be affected, and so is llvmpipe. Not fixed here, because it is outside
this lab's footprint. The fix is one line, `min(..., default=float("inf"))`, and needs Manu's OK.

The container numbers below therefore come from a scratch runner outside the repository. It executes the unchanged
module source with only that expression replaced in memory (`assert src.count(bad) == 1` before the replacement).
The measurement code is untouched. `probe_worklight_coverage.py` turns the same case into a message instead of a
traceback.

## 5. Numbers (TESTED [C] — llvmpipe; for plumbing, not for decisions)

**The llvmpipe timer is not a GPU timer.** In T (§6.1), the no-fetch pass costs 0.120 ms at 1024×768 and 0.106 ms
at 1920×1080, which is less for 2.6× the pixels. In the Worklight runs, GL_TIME_ELAPSED falls from 1.73 to 0.95 ms
(`o2`) while coverage rises from 14 % to 98 %. The probe's own `draw+finish` column (CPU wall time of the software
rasterizer) rises from 35.7 to 43.4 ms at 1024×768 and from 39.2 to 71.8 ms at 1920×1080. None of these values
transfers to a GPU.

Worklight, `probe_shading_gpu.py` view (dolly 1.0), GPU p50 / `draw+finish` p50 ms, all images as required:

| Size | Covered | `off` | `pre-o2` | `o2` | `o2-rgba` |
|---|---|---|---|---|---|
| 1024×768 | 112,557 px (14.3 %) | 0.73 / 28.9 | 1.41 / 32.7 | 1.77 / 35.5 | 1.64 / 34.3 |
| 1920×1080 | 222,591 px (10.7 %) | 0.40 / 28.5 | 0.76 / 36.0 | 0.87 / 36.8 | 0.82 / 38.1 |

The framed view covers only 10.7 % of 1920×1080 (it frames by height). At that size the existing probe measures
about 2× the covered pixels of 1024×768, not a close-up, which is why the coverage wrapper exists.

## 6. Raw output

### 6.1 `probe_gl_caps.py --images <scratch>`

```
Lookdev GL capability probe (2026-11-13): cube maps, textureLod, filtering, seams, full-frame fetch cost
Platform: Linux-6.18.44-fc-v445-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.12.3 (CPython), numpy 2.2.6, pyglet 2.1.19
Interpreter: <scratch>/venv312/bin/python
Source: commit a37ca9df33, src/ tree 94addddafd at HEAD / 94addddafd on disk, working tree MODIFIED
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
GL_VENDOR: Mesa
GL_SHADING_LANGUAGE_VERSION: 4.50
Context: core profile, flags 0; pyglet default config (as src/main.py)
Window 256x256 (hidden), framebuffer 256x256, scale 1.0, dpi 96; screens: 1280x1024
EVIDENCE: SOFTWARE RENDERER - these results are TESTED [C] at best and say nothing about the 9800 GTX driver; its GL_TIME_ELAPSED is not a GPU time.

Limits:
  GL_MAX_TEXTURE_IMAGE_UNITS             32
  GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS    192
  GL_MAX_TEXTURE_SIZE                    16384
  GL_MAX_CUBE_MAP_TEXTURE_SIZE           16384
  GL_MAX_SAMPLES                         4
  GL_MAX_COLOR_ATTACHMENTS               8
  GL_MAX_DRAW_BUFFERS                    8
  GL_MAX_TEXTURE_BUFFER_SIZE             134217728
  GL_MAX_RENDERBUFFER_SIZE               16384
  GL_MAX_VIEWPORT_DIMS                   (16384, 16384)
  GL_MAX_FRAGMENT_UNIFORM_COMPONENTS     16384
  GL_MAX_TEXTURE_LOD_BIAS                16.0
  GL_MAX_TEXTURE_MAX_ANISOTROPY          16.0
Extensions (Lookdev-relevant):
  yes  GL_EXT_texture_filter_anisotropic        anisotropic filtering (iris / skin textures at grazing angles)
  yes  GL_ARB_texture_filter_anisotropic        the same, ARB name (core in GL 4.6)
  yes  GL_NVX_gpu_memory_info                   NVIDIA free / total video memory
  yes  GL_ATI_meminfo                           AMD free video memory (main PC, if AMD)
  yes  GL_ARB_seamless_cube_map                 seamless cube filtering (core since GL 3.2)
  yes  GL_AMD_seamless_cubemap_per_texture      per-texture seamless switch
  yes  GL_ARB_seamless_cubemap_per_texture      per-texture seamless switch
  yes  GL_ARB_texture_cube_map_array            cube map arrays (GL 4.0)
  yes  GL_ARB_texture_float                     float textures (core since GL 3.0)
  yes  GL_ARB_half_float_pixel                  half-float client data (core since GL 3.0)
  yes  GL_EXT_packed_float                      R11F_G11F_B10F, a compact HDR format
  yes  GL_EXT_texture_shared_exponent           RGB9_E5, a compact HDR format
  yes  GL_EXT_texture_sRGB                      sRGB textures (core since GL 2.1)
  yes  GL_ARB_framebuffer_sRGB                  sRGB framebuffers (core since GL 3.0)
  yes  GL_EXT_texture_sRGB_decode               switchable sRGB decode
  yes  GL_ARB_texture_query_lod                 textureQueryLod (GL 4.0)
  yes  GL_ARB_texture_storage                   immutable texture storage (GL 4.2)
  yes  GL_ARB_timer_query                       GL_TIME_ELAPSED (core since GL 3.3)
  yes  GL_ARB_texture_buffer_object_rgb32       RGB32F buffer textures (known absent on the reference PC)
  yes  GL_ARB_texture_multisample               multisample textures (core since GL 3.2)
  yes  GL_ARB_sample_shading                    per-sample shading (GL 4.0)
  yes  GL_ARB_debug_output                      driver debug messages
  yes  GL_KHR_debug                             driver debug messages (GL 4.3)
  yes  GL_EXT_texture_compression_s3tc          BC1-3 compressed textures
  yes  GL_ARB_texture_compression_bptc          BC6H HDR / BC7 compressed textures (GL 4.2)
GPU memory (KiB): dedicated 55318160, total available 71790236, current available 0, eviction count 32765, evicted -480181552, texture free (ATI) 0
Read-back target: RGBA32F colour renderbuffer: COMPLETE

[A] cube allocation + sampling (full mip chain, textureLod lod 0 at 24 quadrant centres)
  RGBA8:
      64^2  driver: RGBA8, R UNORM 8 bit; GL errors: none; sampled 24/24 exact, max err 7.36e-08; upload+mips 5.4 ms; computed 0.12 MiB, free video memory +0.00 MiB  PASS
     128^2  driver: RGBA8, R UNORM 8 bit; GL errors: none; sampled 24/24 exact, max err 7.36e-08; upload+mips 13.6 ms; computed 0.50 MiB, free video memory +0.00 MiB  PASS
     256^2  driver: RGBA8, R UNORM 8 bit; GL errors: none; sampled 24/24 exact, max err 7.36e-08; upload+mips 43.5 ms; computed 2.00 MiB, free video memory +0.00 MiB  PASS
     512^2  driver: RGBA8, R UNORM 8 bit; GL errors: none; sampled 24/24 exact, max err 7.36e-08; upload+mips 155.1 ms; computed 8.00 MiB, free video memory +0.00 MiB  PASS
  RGBA16F:
      64^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 2.9 ms; computed 0.25 MiB, free video memory +0.00 MiB  PASS
     128^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 7.1 ms; computed 1.00 MiB, free video memory +0.00 MiB  PASS
     256^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 30.0 ms; computed 4.00 MiB, free video memory +0.00 MiB  PASS
     512^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 82.4 ms; computed 16.00 MiB, free video memory +0.00 MiB  PASS
  RGBA16F/float-upload:
      64^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0.000244; upload+mips 1.4 ms; computed 0.25 MiB, free video memory +0.00 MiB  PASS
     128^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0.000244; upload+mips 3.9 ms; computed 1.00 MiB, free video memory +0.00 MiB  PASS
     256^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0.000244; upload+mips 16.8 ms; computed 4.00 MiB, free video memory +0.00 MiB  PASS
     512^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0.000244; upload+mips 82.7 ms; computed 16.00 MiB, free video memory +0.00 MiB  PASS
  RGBA32F:
      64^2  driver: RGBA32F, R FLOAT 32 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 1.8 ms; computed 0.50 MiB, free video memory +0.00 MiB  PASS
     128^2  driver: RGBA32F, R FLOAT 32 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 4.8 ms; computed 2.00 MiB, free video memory +0.00 MiB  PASS
     256^2  driver: RGBA32F, R FLOAT 32 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 14.2 ms; computed 8.00 MiB, free video memory +0.00 MiB  PASS
     512^2  driver: RGBA32F, R FLOAT 32 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 105.4 ms; computed 32.00 MiB, free video memory +0.00 MiB  PASS

[B] explicit mip levels / [C] filtering (64^2 marker cube, 16^2 gradient)
  [B] RGBA8    lods -1, 0, 1, 2, 3, 4, 5, 6, 7, 8.5 x 12 directions: 120/120 exact, max err 7.25e-08; GL errors: none  PASS
  [C] RGBA8    trilinear: lod 0..6 in 0.1 steps x 12 directions, max err 0.0000 level step (tolerance 0.0367), monotonic yes  PASS
  [C] RGBA8    bilinear: 1008 samples on a 16^2 gradient (fifths of a texel), max err 0.0000 texel step (tolerance 0.0513; 8-bit weights give <= 0.002); GL errors: none  PASS
  [B] RGBA16F  lods -1, 0, 1, 2, 3, 4, 5, 6, 7, 8.5 x 12 directions: 120/120 exact, max err 9.54e-07; GL errors: none  PASS
  [C] RGBA16F  trilinear: lod 0..6 in 0.1 steps x 12 directions, max err 0.0000 level step (tolerance 0.0200), monotonic yes  PASS
  [C] RGBA16F  bilinear: 1008 samples on a 16^2 gradient (fifths of a texel), max err 0.0000 texel step (tolerance 0.0200; 8-bit weights give <= 0.002); GL errors: none  PASS
  [B] RGBA32F  lods -1, 0, 1, 2, 3, 4, 5, 6, 7, 8.5 x 12 directions: 120/120 exact, max err 9.54e-07; GL errors: none  PASS
  [C] RGBA32F  trilinear: lod 0..6 in 0.1 steps x 12 directions, max err 0.0000 level step (tolerance 0.0200), monotonic yes  PASS
  [C] RGBA32F  bilinear: 1008 samples on a 16^2 gradient (fifths of a texel), max err 0.0000 texel step (tolerance 0.0200; 8-bit weights give <= 0.002); GL errors: none  PASS

[D] seams (64^2 smooth cube, every level)
  [D] RGBA8    12 edges x 7 positions, pairs 0.0001 either side of the edge; jump = largest RGB difference across the edge; expected off = clamp-to-edge bilinear per face
      level  size  expected off  jump off   jump on  interior  on <= tol
          0    64       0.01529   0.01569   0.00010   0.00018        yes
          1    32       0.02353   0.02353   0.00008   0.00016        yes
          2    16       0.05098   0.05098   0.00008   0.00016        yes
          3     8       0.10196   0.10196   0.00008   0.00016        yes
          4     4       0.20784   0.20784   0.00008   0.00015        yes
          5     2       0.40392   0.40392   0.00008   0.00008        yes
          6     1       0.85098   0.85098   0.00008   0.00008        yes
      seamless-off values vs the clamp-to-edge emulation: max err 0.0024
      -> PASS: seamless on: continuous at every level; off: the predicted clamp seams (the switch works)
      image: <scratch>/img_final/seams_RGBA8.png (rows lod 0, 3, 5, 6 top to bottom; left seamless off, right on)
  [D] RGBA16F  12 edges x 7 positions, pairs 0.0001 either side of the edge; jump = largest RGB difference across the edge; expected off = clamp-to-edge bilinear per face
      level  size  expected off  jump off   jump on  interior  on <= tol
          0    64       0.01216   0.01216   0.00008   0.00016        yes
          1    32       0.02476   0.02476   0.00008   0.00016        yes
          2    16       0.04980   0.04980   0.00008   0.00016        yes
          3     8       0.10156   0.10156   0.00008   0.00016        yes
          4     4       0.20947   0.20947   0.00008   0.00015        yes
          5     2       0.40662   0.40662   0.00008   0.00008        yes
          6     1       0.84906   0.84906   0.00008   0.00008        yes
      seamless-off values vs the clamp-to-edge emulation: max err 6e-08
      -> PASS: seamless on: continuous at every level; off: the predicted clamp seams (the switch works)
      image: <scratch>/img_final/seams_RGBA16F.png (rows lod 0, 3, 5, 6 top to bottom; left seamless off, right on)
  [D] RGBA32F  12 edges x 7 positions, pairs 0.0001 either side of the edge; jump = largest RGB difference across the edge; expected off = clamp-to-edge bilinear per face
      level  size  expected off  jump off   jump on  interior  on <= tol
          0    64       0.01218   0.01218   0.00008   0.00016        yes
          1    32       0.02454   0.02454   0.00008   0.00016        yes
          2    16       0.04981   0.04981   0.00008   0.00016        yes
          3     8       0.10201   0.10201   0.00008   0.00016        yes
          4     4       0.20968   0.20968   0.00008   0.00015        yes
          5     2       0.40670   0.40670   0.00008   0.00008        yes
          6     1       0.84907   0.84907   0.00008   0.00008        yes
      seamless-off values vs the clamp-to-edge emulation: max err 6.3e-08
      -> PASS: seamless on: continuous at every level; off: the predicted clamp seams (the switch works)
      image: <scratch>/img_final/seams_RGBA32F.png (rows lod 0, 3, 5, 6 top to bottom; left seamless off, right on)

[T] full-frame cube fetch cost (RGBA8 offscreen target)
  cube 128^2 + mips (smooth content), 1 textureLod per fragment, full-frame sphere-reflection directions; 40 rounds after 5, variants interleaved
  1024x768 (786432 px, 100 % covered), GL_TIME_ELAPSED ms; GL errors: none
    variant                                        p50     p95     min     max  - baseline  ns/px
    no fetch (baseline)                          0.120   0.164   0.078   2.337       0.000   0.15
    RGBA8 sharp lod 0 seamless off               0.177   0.429   0.123   4.733       0.057   0.22
    RGBA8 sharp lod 0 seamless on                0.190   0.239   0.132   0.300       0.070   0.24
    RGBA8 rough lod 4.5 seamless off             0.269   0.400   0.186   0.946       0.149   0.34
    RGBA8 rough lod 4.5 seamless on              0.316   0.392   0.240   0.824       0.196   0.40
    RGBA16F sharp lod 0 seamless off             0.221   1.558   0.147   2.943       0.101   0.28
    RGBA16F sharp lod 0 seamless on              0.222   0.292   0.156   8.957       0.102   0.28
    RGBA16F rough lod 4.5 seamless off           0.344   0.464   0.267   7.058       0.224   0.44
    RGBA16F rough lod 4.5 seamless on            0.371   0.448   0.255   0.985       0.251   0.47
    RGBA32F sharp lod 0 seamless off             0.199   0.263   0.131   0.383       0.079   0.25
    RGBA32F sharp lod 0 seamless on              0.209   0.270   0.134   0.471       0.089   0.27
    RGBA32F rough lod 4.5 seamless off           0.317   0.437   0.198   1.984       0.197   0.40
    RGBA32F rough lod 4.5 seamless on            0.327   0.424   0.234   0.479       0.207   0.42
  1920x1080 (2073600 px, 100 % covered), GL_TIME_ELAPSED ms; GL errors: none
    variant                                        p50     p95     min     max  - baseline  ns/px
    no fetch (baseline)                          0.106   0.784   0.076   3.020       0.000   0.05
    RGBA8 sharp lod 0 seamless off               0.160   0.232   0.120   1.321       0.054   0.08
    RGBA8 sharp lod 0 seamless on                0.175   0.257   0.125   1.850       0.069   0.08
    RGBA8 rough lod 4.5 seamless off             0.244   0.329   0.192   6.258       0.138   0.12
    RGBA8 rough lod 4.5 seamless on              0.275   0.479   0.176   0.722       0.169   0.13
    RGBA16F sharp lod 0 seamless off             0.182   0.259   0.114   1.113       0.076   0.09
    RGBA16F sharp lod 0 seamless on              0.190   0.256   0.142   2.883       0.084   0.09
    RGBA16F rough lod 4.5 seamless off           0.315   0.599   0.243   8.368       0.209   0.15
    RGBA16F rough lod 4.5 seamless on            0.332   0.521   0.239  27.671       0.226   0.16
    RGBA32F sharp lod 0 seamless off             0.169   0.223   0.116   1.220       0.063   0.08
    RGBA32F sharp lod 0 seamless on              0.187   0.292   0.123   3.780       0.081   0.09
    RGBA32F rough lod 4.5 seamless off           0.275   0.376   0.211   4.106       0.169   0.13
    RGBA32F rough lod 4.5 seamless on            0.282   0.380   0.190   2.128       0.176   0.14

[R] resources and GL state
  created: 29 texture, 3 buffer, 3 framebuffer, 3 renderbuffer, 1 query, 2 vertex_array, 2 program, 4 shader; still alive after release: none
  GL state after the probe vs before: identical
  glGetError at the end: none
  GPU memory after release (KiB): dedicated 55318160, total available 71790236, current available 0, eviction count 32765, evicted -480181552, texture free (ATI) 0
  -> PASS

Summary (raw verdicts of this run - label them by machine in the results file):
  A     RGBA8 PASS; RGBA16F PASS; RGBA16F/float-upload PASS; RGBA32F PASS
  B     RGBA8 PASS; RGBA16F PASS; RGBA32F PASS
  C     RGBA8 trilinear PASS; RGBA8 bilinear PASS; RGBA16F trilinear PASS; RGBA16F bilinear PASS; RGBA32F trilinear PASS; RGBA32F bilinear PASS
  D     RGBA8 PASS; RGBA16F PASS; RGBA32F PASS
  T     timing INFO
  R     hygiene PASS

All extensions (229):
  GL_3DFX_texture_compression_FXT1 GL_AMD_conservative_depth GL_AMD_draw_buffers_blend GL_AMD_gpu_shader_int64
  GL_AMD_multi_draw_indirect GL_AMD_pinned_memory GL_AMD_query_buffer_object GL_AMD_seamless_cubemap_per_texture
  GL_AMD_shader_stencil_export GL_AMD_shader_trinary_minmax GL_AMD_texture_texture4 GL_AMD_vertex_shader_layer
  GL_AMD_vertex_shader_viewport_index GL_ANGLE_texture_compression_dxt3 GL_ANGLE_texture_compression_dxt5
  GL_ARB_ES2_compatibility GL_ARB_ES3_1_compatibility GL_ARB_ES3_2_compatibility GL_ARB_ES3_compatibility
  GL_ARB_arrays_of_arrays GL_ARB_base_instance GL_ARB_blend_func_extended GL_ARB_buffer_storage
  GL_ARB_clear_buffer_object GL_ARB_clear_texture GL_ARB_clip_control GL_ARB_compressed_texture_pixel_storage
  GL_ARB_compute_shader GL_ARB_conditional_render_inverted GL_ARB_conservative_depth GL_ARB_copy_buffer
  GL_ARB_copy_image GL_ARB_cull_distance GL_ARB_debug_output GL_ARB_depth_buffer_float GL_ARB_depth_clamp
  GL_ARB_derivative_control GL_ARB_direct_state_access GL_ARB_draw_buffers GL_ARB_draw_buffers_blend
  GL_ARB_draw_elements_base_vertex GL_ARB_draw_indirect GL_ARB_draw_instanced GL_ARB_enhanced_layouts
  GL_ARB_explicit_attrib_location GL_ARB_explicit_uniform_location GL_ARB_fragment_coord_conventions
  GL_ARB_fragment_layer_viewport GL_ARB_fragment_shader GL_ARB_framebuffer_no_attachments GL_ARB_framebuffer_object
  GL_ARB_framebuffer_sRGB GL_ARB_get_program_binary GL_ARB_get_texture_sub_image GL_ARB_gl_spirv GL_ARB_gpu_shader5
  GL_ARB_gpu_shader_fp64 GL_ARB_gpu_shader_int64 GL_ARB_half_float_pixel GL_ARB_half_float_vertex
  GL_ARB_indirect_parameters GL_ARB_instanced_arrays GL_ARB_internalformat_query GL_ARB_internalformat_query2
  GL_ARB_invalidate_subdata GL_ARB_map_buffer_alignment GL_ARB_map_buffer_range GL_ARB_multi_bind
  GL_ARB_multi_draw_indirect GL_ARB_occlusion_query2 GL_ARB_parallel_shader_compile GL_ARB_pipeline_statistics_query
  GL_ARB_pixel_buffer_object GL_ARB_point_sprite GL_ARB_polygon_offset_clamp GL_ARB_post_depth_coverage
  GL_ARB_program_interface_query GL_ARB_provoking_vertex GL_ARB_query_buffer_object
  GL_ARB_robust_buffer_access_behavior GL_ARB_robustness GL_ARB_sample_shading GL_ARB_sampler_objects
  GL_ARB_seamless_cube_map GL_ARB_seamless_cubemap_per_texture GL_ARB_separate_shader_objects
  GL_ARB_shader_atomic_counter_ops GL_ARB_shader_atomic_counters GL_ARB_shader_ballot GL_ARB_shader_bit_encoding
  GL_ARB_shader_clock GL_ARB_shader_draw_parameters GL_ARB_shader_group_vote GL_ARB_shader_image_load_store
  GL_ARB_shader_image_size GL_ARB_shader_objects GL_ARB_shader_precision GL_ARB_shader_stencil_export
  GL_ARB_shader_storage_buffer_object GL_ARB_shader_subroutine GL_ARB_shader_texture_image_samples
  GL_ARB_shader_texture_lod GL_ARB_shader_viewport_layer_array GL_ARB_shading_language_420pack
  GL_ARB_shading_language_include GL_ARB_shading_language_packing GL_ARB_spirv_extensions GL_ARB_stencil_texturing
  GL_ARB_sync GL_ARB_tessellation_shader GL_ARB_texture_barrier GL_ARB_texture_border_clamp
  GL_ARB_texture_buffer_object GL_ARB_texture_buffer_object_rgb32 GL_ARB_texture_buffer_range
  GL_ARB_texture_compression_bptc GL_ARB_texture_compression_rgtc GL_ARB_texture_cube_map_array
  GL_ARB_texture_filter_anisotropic GL_ARB_texture_filter_minmax GL_ARB_texture_float GL_ARB_texture_gather
  GL_ARB_texture_mirror_clamp_to_edge GL_ARB_texture_multisample GL_ARB_texture_non_power_of_two
  GL_ARB_texture_query_levels GL_ARB_texture_query_lod GL_ARB_texture_rectangle GL_ARB_texture_rg
  GL_ARB_texture_rgb10_a2ui GL_ARB_texture_stencil8 GL_ARB_texture_storage GL_ARB_texture_storage_multisample
  GL_ARB_texture_swizzle GL_ARB_texture_view GL_ARB_timer_query GL_ARB_transform_feedback2 GL_ARB_transform_feedback3
  GL_ARB_transform_feedback_instanced GL_ARB_transform_feedback_overflow_query GL_ARB_uniform_buffer_object
  GL_ARB_vertex_array_bgra GL_ARB_vertex_array_object GL_ARB_vertex_attrib_64bit GL_ARB_vertex_attrib_binding
  GL_ARB_vertex_buffer_object GL_ARB_vertex_shader GL_ARB_vertex_type_10f_11f_11f_rev
  GL_ARB_vertex_type_2_10_10_10_rev GL_ARB_viewport_array GL_ARM_shader_framebuffer_fetch_depth_stencil
  GL_ATI_blend_equation_separate GL_ATI_meminfo GL_ATI_texture_float GL_ATI_texture_mirror_once
  GL_EXT_EGL_image_storage GL_EXT_EGL_image_storage_compression GL_EXT_EGL_sync GL_EXT_abgr
  GL_EXT_blend_equation_separate GL_EXT_debug_label GL_EXT_draw_buffers2 GL_EXT_draw_instanced
  GL_EXT_framebuffer_blit GL_EXT_framebuffer_multisample GL_EXT_framebuffer_multisample_blit_scaled
  GL_EXT_framebuffer_object GL_EXT_framebuffer_sRGB GL_EXT_memory_object GL_EXT_memory_object_fd
  GL_EXT_packed_depth_stencil GL_EXT_packed_float GL_EXT_pixel_buffer_object GL_EXT_polygon_offset_clamp
  GL_EXT_provoking_vertex GL_EXT_shader_clock GL_EXT_shader_framebuffer_fetch
  GL_EXT_shader_framebuffer_fetch_non_coherent GL_EXT_shader_image_load_formatted GL_EXT_shader_integer_mix
  GL_EXT_texture_array GL_EXT_texture_compression_dxt1 GL_EXT_texture_compression_rgtc
  GL_EXT_texture_compression_s3tc GL_EXT_texture_filter_anisotropic GL_EXT_texture_filter_minmax
  GL_EXT_texture_integer GL_EXT_texture_mirror_clamp GL_EXT_texture_sRGB GL_EXT_texture_sRGB_R8
  GL_EXT_texture_sRGB_RG8 GL_EXT_texture_sRGB_decode GL_EXT_texture_shadow_lod GL_EXT_texture_shared_exponent
  GL_EXT_texture_snorm GL_EXT_texture_storage GL_EXT_texture_swizzle GL_EXT_timer_query GL_EXT_transform_feedback
  GL_EXT_vertex_array_bgra GL_EXT_vertex_attrib_64bit GL_IBM_multimode_draw_arrays
  GL_INTEL_shader_atomic_float_minmax GL_KHR_blend_equation_advanced GL_KHR_blend_equation_advanced_coherent
  GL_KHR_context_flush_control GL_KHR_debug GL_KHR_no_error GL_KHR_parallel_shader_compile
  GL_KHR_robust_buffer_access_behavior GL_KHR_robustness GL_KHR_texture_compression_astc_ldr
  GL_KHR_texture_compression_astc_sliced_3d GL_MESA_framebuffer_flip_y GL_MESA_pack_invert
  GL_MESA_shader_integer_functions GL_MESA_texture_signed_rgba GL_NVX_gpu_memory_info
  GL_NV_alpha_to_coverage_dither_control GL_NV_conditional_render GL_NV_copy_image GL_NV_depth_clamp
  GL_NV_packed_depth_stencil GL_NV_shader_atomic_float GL_NV_texture_barrier GL_OES_EGL_image GL_OVR_multiview
  GL_OVR_multiview2 GL_S3_s3tc
```

### 6.2 `probe_shading_gpu.py` (scratch runner, one line patched in memory, see §4), 1024x768 and `--size 1920 1080`

```
Shading GPU probe (2026-11-11): one full shaded pass per face-data layout, GL_TIME_ELAPSED, ms
Platform: Linux-6.18.44-fc-v445-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.12.3 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit a37ca9df33, working tree clean

[gollum_87k] 87500 V / 87500 F, 1024x768, Smooth, 112557 px covered, 40 rounds after 5
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            0.73     0.17     4.63             28.87   12502 px differ
  pre-o2         1.41     0.34     7.52             32.73   identical
  o2             1.77     0.38     7.01             35.48   identical
  o2-rgba        1.64     0.36     8.59             34.26   identical

[gollum_87k] 87500 V / 87500 F, 1920x1080, Smooth, 222591 px covered, 40 rounds after 5
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            0.40     0.00     7.08             28.49   24297 px differ
  pre-o2         0.76     0.31     6.14             35.97   identical
  o2             0.87     0.05     8.96             36.78   identical
  o2-rgba        0.82     0.56     3.47             38.10   identical
```

### 6.3 `probe_worklight_coverage.py` (same scratch runner), 1024x768 and `--size 1920 1080`

```
Worklight coverage probe (2026-11-13): drag_cost/probe_shading_gpu.measure with the camera dollied in
Platform: Linux-6.18.44-fc-v445-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.12.3 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit a37ca9df33, src/ tree 94addddafd, working tree clean

[gollum_87k] 87500 V / 87500 F, 1024x768, Smooth, 112557 px covered, 40 rounds after 5
  dolly 1: coverage 14.3 % of 1024x768
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            0.85     0.18     7.20             28.11   12502 px differ
  pre-o2         1.38     0.35     6.87             32.86   identical
  o2             1.73     0.38     8.37             35.71   identical
  o2-rgba        1.68     0.39    10.74             33.93   identical

[gollum_87k] 87500 V / 87500 F, 1024x768, Smooth, 488895 px covered, 40 rounds after 5
  dolly 0.5: coverage 62.2 % of 1024x768
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            0.20     0.09     4.15             31.30   63388 px differ
  pre-o2         0.34     0.18     5.89             41.98   identical
  o2             0.40     0.24     3.00             45.63   identical
  o2-rgba        0.48     0.24     2.41             44.71   identical

[gollum_87k] 87500 V / 87500 F, 1024x768, Smooth, 773031 px covered, 40 rounds after 5
  dolly 0.3: coverage 98.3 % of 1024x768
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            0.42     0.28     3.90             28.33   98953 px differ
  pre-o2         0.82     0.65     2.12             40.49   identical
  o2             0.95     0.68     1.89             43.40   identical
  o2-rgba        0.92     0.70     1.74             42.05   identical

[gollum_87k] 87500 V / 87500 F, 1920x1080, Smooth, 222591 px covered, 40 rounds after 5
  dolly 1: coverage 10.7 % of 1920x1080
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            0.35     0.06     3.78             27.77   24297 px differ
  pre-o2         0.70     0.20     5.22             36.39   identical
  o2             0.83     0.71     7.14             39.20   identical
  o2-rgba        0.74     0.02     2.98             36.99   identical

[gollum_87k] 87500 V / 87500 F, 1920x1080, Smooth, 968176 px covered, 40 rounds after 5
  dolly 0.5: coverage 46.7 % of 1920x1080
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            0.16     0.01     1.42             35.26   125925 px differ
  pre-o2         0.37     0.10     1.53             51.71   identical
  o2             0.43     0.07     9.55             57.65   identical
  o2-rgba        0.42     0.13     1.42             54.06   identical

[gollum_87k] 87500 V / 87500 F, 1920x1080, Smooth, 2060603 px covered, 40 rounds after 5
  dolly 0.3: coverage 99.4 % of 1920x1080
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            0.23     0.16     1.97             40.36   264944 px differ
  pre-o2         0.51     0.32     5.72             62.01   identical
  o2             0.60     0.43     1.22             71.81   identical
  o2-rgba        0.57     0.43     4.10             68.12   identical
```
