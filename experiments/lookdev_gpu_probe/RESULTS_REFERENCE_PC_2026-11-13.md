# Lookdev GPU probe — reference PC, 2026-11-13

**Run by Manu on 2026-11-13; NVIDIA power management set to "prefer maximum performance" (Manu).** Every number in
this file is **MEASURED [RPC]** unless marked otherwise. **[H]** marks a reading of the numbers, not a measurement.
**INFERRED** marks results from the NumPy emulation in `cube_math.py`. That emulation reproduces this PC's
measurements (§4), but its predictions are not measured here. MAIN stays **OPEN** (no main PC yet). Container
counterpart: [`RESULTS_CONTAINER_2026-11-13.md`](RESULTS_CONTAINER_2026-11-13.md). Format:
[`RESULTS_TEMPLATE.md`](RESULTS_TEMPLATE.md).

## Kurzfassung für Manu (Deutsch)

- **Cubemaps funktionieren auf deiner 9800 GTX.** Getestet sind RGBA8, RGBA16F und RGBA32F von 64² bis 512²: Die
  Werte kommen exakt zurück. Auch gezielt unscharfe Stufen (`textureLod`) und die Filterung stimmen. RGBA16F kostet
  hier nicht mehr als RGBA8.
- **Nähte:** Die Karte filtert über die Würfelkanten hinweg. An den 8 **Würfelecken** nimmt sie aber nur eine Seite
  statt des Mittels der drei. Das stört nur in den kleinsten, sehr unscharfen Stufen und direkt an den Ecken.
  Abhilfe ohne Laufzeitkosten: beim Vorberechnen der Umgebung die drei Ecktexel angleichen und die 1×1-Stufe weglassen.
  In der Nachrechnung ist das Problem damit ganz weg; auf deinem PC bestätigt es das Augen-Lab.
- **Eine Spiegelung nachschlagen ist billig:** ≈ 0,1 ms pro Bild bei 1920×1080.
- **Teuer ist das heutige Worklight-Shading in der Großaufnahme.** Füllt das 87,5k-Mesh das Bild, kostet allein
  dieser Durchgang 16 ms GPU-Zeit (1024×768) bzw. 27 ms (1920×1080). Ohne die Viereck-Normale (die Dreiecke
  unsichtbar macht) wären es 3 bzw. 5 ms. Für Lookdev auf diesem PC heißt das: die Viereck-Normale nicht übernehmen
  (Entscheidung D-L6).
- **Nebenbei beantwortet:** O2 kostet bei vollem Takt gut 4 ms mehr als vorher (7,2 → 11,2 ms bei 1024×768). Die
  RGBA32F-Variante würde davon 3 ms zurückholen, mit pixelgleichem Bild.
- Der Hinweis „NOTE the GPU times vary a lot“ war ein **Fehlalarm** der alten Sonde. Jede Variante blieb innerhalb
  von 2 %; die Takte waren stabil.

## 1. Run record

| Field | Value |
|---|---|
| Machine | reference PC: Core 2 Quad Q9550, GeForce 9800 GTX/9800 GTX+, Windows 10 (19045) |
| Interpreter | `.venv312\Scripts\python.exe`: Python 3.12.10, numpy 2.2.6, pyglet 2.1.19 |
| Commit / `src/` tree | `d61d06d1f4` / `94addddafd` at HEAD = `94addddafd` on disk, so the measured `src/` is the committed one. The working tree was modified only outside `src/` (scene files, `.claude/` settings, untracked venvs / captures). |
| GL | `3.3.0` / `GeForce 9800 GTX/9800 GTX+/PCIe/SSE2` / `NVIDIA Corporation` / GLSL `3.30 NVIDIA via Cg compiler` |
| Context | **core profile**, flags 0. pyglet's default config, as `src/main.py` gets it. The audit inferred this from the pyglet source; it is now measured. |
| `EVIDENCE:` line | hardware renderer |
| Screen | **1200×1920** (portrait). The hidden 1920×1080 window kept its size: it covered 222,592 px, against 222,591 in the container. |
| Driver version | not recorded (the probe cannot read it) |
| Lab tests | `pytest experiments\lookdev_gpu_probe\tests`: **30 passed** (6.3 s), including the 3 GL tests on this driver (full run, leak and state checks) |

## 2. GL facts

| Item | Value |
|---|---|
| GL_MAX_TEXTURE_IMAGE_UNITS / COMBINED | 32 / 96 (the mesh programs use units 1–7) |
| GL_MAX_TEXTURE_SIZE / GL_MAX_CUBE_MAP_TEXTURE_SIZE | 8192 / 8192 |
| GL_MAX_SAMPLES | 16. Probably includes coverage-sampling modes (`GL_NV_framebuffer_multisample_coverage` is present) **[H]**; MSAA itself not tested. |
| GL_MAX_COLOR_ATTACHMENTS / DRAW_BUFFERS | 8 / 8 |
| GL_MAX_TEXTURE_BUFFER_SIZE / RENDERBUFFER_SIZE / VIEWPORT_DIMS | 134,217,728 / 8192 / 8192×8192 |
| GL_MAX_FRAGMENT_UNIFORM_COMPONENTS, LOD bias, anisotropy | 2048, 15.0, **16×** |
| Video memory (`GL_NVX_gpu_memory_info`) | dedicated **512 MiB** (Windows shows 481 MB); 395 MiB available at the start; the evictions counter stayed unchanged during the run |
| Lookdev-relevant extensions present | `EXT_texture_filter_anisotropic`, `NVX_gpu_memory_info`, `ARB_seamless_cube_map`, `ARB_texture_float`, `ARB_half_float_pixel`, `EXT_packed_float` (R11F_G11F_B10F), `EXT_texture_shared_exponent` (RGB9_E5), `EXT_texture_sRGB` + `_decode`, `ARB_framebuffer_sRGB`, `ARB_texture_storage`, `ARB_timer_query`, `ARB_texture_multisample`, `KHR_debug`, `EXT_texture_compression_s3tc` |
| Absent | `ARB_texture_query_lod`, `ARB_texture_cube_map_array`, `ARB_texture_compression_bptc` (no BC6H), `ARB_sample_shading`, `ARB_texture_buffer_object_rgb32` (as known), per-texture seamless switch |
| `RGBA32F` colour renderbuffer (the probe's read-back target) | COMPLETE: rendering into a float target and reading it back works |

## 3. Capability checks

| Check | RGBA8 | RGBA16F (half data) | RGBA16F (float data) | RGBA32F |
|---|---|---|---|---|
| **A** allocation + sampling, 64²–512², full mips | PASS | PASS | PASS | PASS |
| driver-reported level format | RGBA8, UNORM 8 | RGBA16F, FLOAT 16 | RGBA16F, FLOAT 16 | RGBA32F, FLOAT 32 |
| max error over 24 quadrant centres | 2.9·10⁻⁸ | 0 | 0 | 0 |
| **B** `textureLod` at lod −1, 0…6, 7, 8.5 | PASS, 120/120 | PASS, 120/120 | — | PASS, 120/120 |
| **C** bilinear, max error in texel steps | PASS, 0.0017 | PASS, 0.0047 | — | PASS, 0.0016 |
| **C** trilinear, max error in level steps | PASS, 0.0031 | PASS, 0.0031 | — | PASS, 0.0031 |
| **D** seams, seamless on | **FAIL** (corners, §4) | **FAIL** (corners) | — | **FAIL** (corners) |
| **R** objects deleted, state identical, no GL error | PASS (whole run) | | | |

- **Values above 1, down to 2⁻¹⁰, survive in RGBA16F / RGBA32F:** the driver really stores float (A).
- **Float data into RGBA16F:** max error 0. The driver rounds like NumPy. Mesa differed by one half-float step.
- **Weight precision (C):** the errors fit 8-bit bilinear weights and an 8-bit lod fraction (≤ 1/256) **[H]**.
- **RGBA16F bilinear (0.0047 step = 0.0012 absolute at values ≤ 3.75):** this fits a filter result rounded to half
  precision **[H]**. It is harmless for an environment shown in 8 bit.
- **Video-memory drop at 512²:** 6.96 / 13.71 / 25.70 MiB against 8 / 16 / 32 MiB computed (RGBA8 / RGBA16F /
  RGBA32F). The small allocations read noisily (+10 and +19 MiB at 128²: the driver freed other memory at the same
  time), so `GL_NVX_gpu_memory_info` only resolves large allocations.
- **`upload+mips` times include NumPy generating the test pattern:** 250–410 ms at 512², 551 ms once at 256²
  RGBA16F. They are one-off times, not upload speed.

## 4. Seams: the driver blends across edges but not at corners

The measured edge jumps with seamless filtering on:

| Level | Size | Off (= clamp emulation) | On, measured (RGBA8 / RGBA16F / RGBA32F) | Corner texels in the filter footprints |
|---|---|---|---|---|
| 0–3 | 64² … 8² | 0.012 … 0.102 | ≤ 0.0005: continuous | 0 |
| 4 | 4² | 0.208 | 0.0092 / 0.0093 / 0.0091 | 24 |
| 5 | 2² | 0.404 | 0.062 / 0.062 / 0.062 | 72 |
| 6 | 1² | 0.849 | 0.170 / 0.169 / 0.169 | 168 |

- **Seamless off:** the off values match the clamp-to-edge emulation (max error ≤ 0.0007), so the test pattern, the
  face convention and the off path are confirmed on this driver.
- **The residual jumps** appear exactly at the levels where the edge samples' 2×2 footprints reach a corner texel.
- **Emulation of seamless filtering** (`cube_math.seamless_bilinear`, INFERRED, pinned by
  `test_seamless_emulation_matches_both_drivers`):

  | Level | "average" corner rule | "one face" corner rule | Measured, RGBA32F |
  |---|---|---|---|
  | 4 | 0.0001 | 0.0090 | 0.0091 |
  | 5 | 0.0001 | 0.0611 | 0.0620 |
  | 6 | 0.0001 | 0.1699 | 0.1692 |

  - "average": a tap beyond both edges takes the mean of the three texels meeting at the cube corner. That is how I
    read the GL spec; I could not check the spec text here, because the Khronos registry is not reachable from this
    session. Mesa behaves this way.
  - "one face": the tap takes the face's own corner texel. Taking either neighbour's corner texel gives the same
    jumps.

  **Reading:** the 9800 GTX driver blends seamlessly across edges but takes a corner tap from **one** face.
- **Near a corner, the error also reaches the larger levels** (INFERRED: the "one face" emulation, positions
  0.95 / 0.99 along every edge, a test pattern spanning ≈ 0.9):

  | Level | 64² | 32² | 16² | 8² | 4² | 2² | 1² |
  |---|---|---|---|---|---|---|---|
  | Corner error | 0.0009 | 0.0034 | 0.0085 | 0.019 | 0.043 | 0.10 | 0.21 |

  It is limited to lookups within one texel of the 8 corners.
- **CPU fix-up (INFERRED, `test_equalized_corners_make_the_corner_rule_irrelevant_down_to_2x2`):** after
  prefiltering, set the three texels at each of the 8 corners of every level to their mean
  (`cube_math.equalize_corners`, 24 texels per level). The corner rule then no longer matters, and the emulation
  shows no jump at any level down to 2². At 1² every texel is a corner of four cube corners, so that level cannot be
  fixed; leave it unused (`GL_TEXTURE_MAX_LEVEL`).

## 5. Cost of an environment lookup (T)

The cube was 128² with mips. Each pass filled the whole frame (100 % coverage) with one `textureLod` per fragment,
40 rounds after 5. The spread within each variant was ≤ 3 %.

| | 1024×768 | 1920×1080 |
|---|---|---|
| pass without fetch | 0.144 ms | 0.377 ms |
| + one fetch, RGBA8 or RGBA16F, sharp or rough, seamless off or on | **+0.039 ms** | **+0.102 ms** (0.05 ns/px) |
| + one fetch, RGBA32F at the rough lod (trilinear) | +0.078 ms | +0.198 ms |

**Reading:**
- Seamless filtering costs nothing.
- RGBA16F filters at RGBA8 speed. RGBA32F costs twice as much only when two levels are blended.
- One environment lookup over a full 1920×1080 frame is ≈ 0.4 % of what the Worklight pass costs at the same coverage
  (§6). **The lookup is not the budget problem.**

## 6. Worklight: `probe_shading_gpu.py` baseline and close-ups

The fixture was `gollum_87k` (87,500 V / F), Smooth, with GPU p50 ms per face-data layout. `pre-o2` and `o2-rgba`
drew images byte-identical to `o2` in all 8 runs. The plain probe and the coverage wrapper's dolly-1.0 rows agree
within 0.3 %.

| Size | Camera | Coverage | `off` | `pre-o2` | `o2` (production) | `o2-rgba` | `o2` per covered px |
|---|---|---|---|---|---|---|---|
| 1024×768 | framed (plain probe) | 14.3 % | 1.94 | 7.18 | **11.24** | 8.25 | 99.9 ns |
| 1024×768 | dolly 0.5 | 62.2 % | 2.97 | 11.20 | **17.85** | 13.01 | 36.5 ns |
| 1024×768 | dolly 0.3 | 98.3 % | 2.93 | 10.45 | **16.08** | 11.93 | 20.8 ns |
| 1920×1080 | framed (plain probe) | 10.7 % | 2.45 | 9.44 | **14.71** | 10.90 | 66.1 ns |
| 1920×1080 | dolly 0.5 | 46.7 % | 4.14 | 15.87 | **24.98** | 18.42 | 25.8 ns |
| 1920×1080 | dolly 0.3 | 99.1 % | 4.98 | 18.06 | **26.76** | 20.47 | 13.0 ns |

**Reading:**
1. **The Worklight pass alone costs 16.1 ms at a frame-filling close-up at 1024×768 and 26.8 ms at 1920×1080.** That
   is at the 16.7 ms bar, and over it, before anything else is drawn. Without face data (`off`, per-triangle vertex
   normals) the same views cost 2.9 / 5.0 ms. The face-data shading (the bilinear quad normal that keeps the triangles
   invisible) is 13.2 / 21.8 ms of it.
2. **Cost does not scale linearly with coverage.** Extrapolating linearly from the framed view would have predicted
   ≈ 77 ms at full frame (1024×768); the measurement is 16 ms. At the framed view several triangles share a pixel
   (overshading); close up they do not **[H]**. The 62 % view costs more than the 98 % one at 1024×768 (17.9 vs
   16.1 ms): there more of the body is visible in layers, so depth complexity is higher **[H]**.
3. **O2 against pre-O2 at full clock**, the open question of
   [`RESULTS_O2_REFERENCE_PC_2026-11-11.md`](../drag_cost/RESULTS_O2_REFERENCE_PC_2026-11-11.md) round 3: O2 costs
   **+4.0 ms (+56 %)** at the framed 1024×768 view and +8.7 ms (+48 %) at the full-frame 1920×1080 view. The RGBA32F
   fetch variant (`o2-rgba`) would recover **24–27 %** of `o2` at every coverage, with a byte-identical image. Whether
   to adopt it is a separate performance decision, not part of Lookdev.

## 7. Other findings

- **`drag_cost/probe_shading_gpu.py` printed "NOTE the GPU times vary a lot" in all 8 runs. It is a false alarm.**
  Its rule compares the slowest against the fastest *variant*, and `off` / `o2` differ 5.8× by design. Within each
  variant, min and max stay within 2 %, and Manu confirmed maximum performance. My probe had copied the rule (it did
  not fire in T). It now checks the spread within each variant (`cube_math.timing_unstable`). The drag_cost probe is
  unchanged: like its crash on ≤ 0.5 ms times (README), the fix is one line, outside this lab, and awaits an OK.
- **The crash on small GPU times did not occur here,** as expected (the smallest time was 1.91 ms).

## 8. Reading for the Eye Proof (P1)

1. **Environment format: RGBA16F cube, 128² (256² if the cornea wants it; 4 MiB with mips).** Upload as half-float
   data from NumPy, trilinear, seamless on. It is exact, filters like RGBA8 and costs ≈ 0.1 ms per full-frame lookup.
   An RGBA8 / RGBM fallback is not needed for capability reasons on this PC. The compact HDR formats R11F_G11F_B10F
   and RGB9_E5 exist but were not tested; they are not needed at these sizes.
2. **Prefilter on the CPU in GL face order.** The convention in `cube_math.py` is verified on this driver by A and
   by D's off path.
3. **Corners, after prefiltering:**
   - equalize the three corner texels per level (`cube_math.equalize_corners`);
   - stop the mip chain at 2² (`GL_TEXTURE_MAX_LEVEL`);
   - map roughness 1 onto that level.

   P1 should confirm "no seams" on this PC with D's test pattern; the prediction is INFERRED.
4. **Lookup budget:** several lookups per fragment are affordable (specular + diffuse + one for the cornea).
5. **Fill-rate:** the eye lab's own geometry is small, so the 16 / 27 ms above does not limit P1. It limits **P2**:
   on this PC, a Lookdev pass over the 87.5k character must not inherit the face-data quad normal (D-L6). Plain
   interpolated normals cost 2.9 / 5.0 ms at full frame, which leaves room for the Lookdev terms. Judge P1's timing
   with the eye covering about 50 % of the frame, as the audit planned (§5.6).
6. **Still untested and not needed for P1:** MSAA, sRGB textures and framebuffers, depth textures, float render
   targets beyond the RGBA32F read-back.

Decisions D-L1, D-L2, D-L4 and D-L5 from the audit are still needed to start P1. D-L6 now has numbers (point 5).

## 9. Raw output (Manu, pasted; `git status` list summarised in §1)

```
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> $py = (Resolve-Path .\.venv312\Scripts\python.exe).Path; & $py --version; & $py -c "import numpy, pyglet; print('numpy', numpy.__version__, 'pyglet', pyglet.version)"
Python 3.12.10
numpy 2.2.6 pyglet 2.1.19
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> git rev-parse --short=10 HEAD; git rev-parse --short=10 HEAD:src; git status --short
d61d06d1f4
94addddafd
[list omitted: modified scene files and .claude/settings.local.json, untracked venvs, captures, scenes, images - nothing under src/]
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py -m pytest experiments\lookdev_gpu_probe\tests -q
..............................                                                                                                     [100%]
30 passed in 6.25s
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\lookdev_gpu_probe\probe_gl_caps.py --images experiments\lookdev_gpu_probe\out
Lookdev GL capability probe (2026-11-13): cube maps, textureLod, filtering, seams, full-frame fetch cost
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython), numpy 2.2.6, pyglet 2.1.19
Interpreter: C:\Users\Manuel\Mirai_Bastel\.venv312\Scripts\python.exe
Source: commit d61d06d1f4, src/ tree 94addddafd at HEAD / 94addddafd on disk, working tree MODIFIED
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
GL_VENDOR: NVIDIA Corporation
GL_SHADING_LANGUAGE_VERSION: 3.30 NVIDIA via Cg compiler
Context: core profile, flags 0; pyglet default config (as src/main.py)
Window 256x256 (hidden), framebuffer 256x256, scale 1.0, dpi 96; screens: 1200x1920
EVIDENCE: hardware renderer - label the results MEASURED [RPC] or MEASURED [MAIN] by machine.

Limits:
  GL_MAX_TEXTURE_IMAGE_UNITS             32
  GL_MAX_COMBINED_TEXTURE_IMAGE_UNITS    96
  GL_MAX_TEXTURE_SIZE                    8192
  GL_MAX_CUBE_MAP_TEXTURE_SIZE           8192
  GL_MAX_SAMPLES                         16
  GL_MAX_COLOR_ATTACHMENTS               8
  GL_MAX_DRAW_BUFFERS                    8
  GL_MAX_TEXTURE_BUFFER_SIZE             134217728
  GL_MAX_RENDERBUFFER_SIZE               8192
  GL_MAX_VIEWPORT_DIMS                   (8192, 8192)
  GL_MAX_FRAGMENT_UNIFORM_COMPONENTS     2048
  GL_MAX_TEXTURE_LOD_BIAS                15.0
  GL_MAX_TEXTURE_MAX_ANISOTROPY          16.0
Extensions (Lookdev-relevant):
  yes  GL_EXT_texture_filter_anisotropic        anisotropic filtering (iris / skin textures at grazing angles)
  no   GL_ARB_texture_filter_anisotropic        the same, ARB name (core in GL 4.6)
  yes  GL_NVX_gpu_memory_info                   NVIDIA free / total video memory
  no   GL_ATI_meminfo                           AMD free video memory (main PC, if AMD)
  yes  GL_ARB_seamless_cube_map                 seamless cube filtering (core since GL 3.2)
  no   GL_AMD_seamless_cubemap_per_texture      per-texture seamless switch
  no   GL_ARB_seamless_cubemap_per_texture      per-texture seamless switch
  no   GL_ARB_texture_cube_map_array            cube map arrays (GL 4.0)
  yes  GL_ARB_texture_float                     float textures (core since GL 3.0)
  yes  GL_ARB_half_float_pixel                  half-float client data (core since GL 3.0)
  yes  GL_EXT_packed_float                      R11F_G11F_B10F, a compact HDR format
  yes  GL_EXT_texture_shared_exponent           RGB9_E5, a compact HDR format
  yes  GL_EXT_texture_sRGB                      sRGB textures (core since GL 2.1)
  yes  GL_ARB_framebuffer_sRGB                  sRGB framebuffers (core since GL 3.0)
  yes  GL_EXT_texture_sRGB_decode               switchable sRGB decode
  no   GL_ARB_texture_query_lod                 textureQueryLod (GL 4.0)
  yes  GL_ARB_texture_storage                   immutable texture storage (GL 4.2)
  yes  GL_ARB_timer_query                       GL_TIME_ELAPSED (core since GL 3.3)
  no   GL_ARB_texture_buffer_object_rgb32       RGB32F buffer textures (known absent on the reference PC)
  yes  GL_ARB_texture_multisample               multisample textures (core since GL 3.2)
  no   GL_ARB_sample_shading                    per-sample shading (GL 4.0)
  yes  GL_ARB_debug_output                      driver debug messages
  yes  GL_KHR_debug                             driver debug messages (GL 4.3)
  yes  GL_EXT_texture_compression_s3tc          BC1-3 compressed textures
  no   GL_ARB_texture_compression_bptc          BC6H HDR / BC7 compressed textures (GL 4.2)
GPU memory (KiB): dedicated 524288, total available 524288, current available 404304, eviction count 736, evicted 560916
Read-back target: RGBA32F colour renderbuffer: COMPLETE

[A] cube allocation + sampling (full mip chain, textureLod lod 0 at 24 quadrant centres)
  RGBA8:
      64^2  driver: RGBA8, R UNORM 8 bit; GL errors: none; sampled 24/24 exact, max err 2.92e-08; upload+mips 15.1 ms; computed 0.12 MiB, free video memory -0.50 MiB  PASS
     128^2  driver: RGBA8, R UNORM 8 bit; GL errors: none; sampled 24/24 exact, max err 2.92e-08; upload+mips 35.0 ms; computed 0.50 MiB, free video memory -1.48 MiB  PASS
     256^2  driver: RGBA8, R UNORM 8 bit; GL errors: none; sampled 24/24 exact, max err 2.92e-08; upload+mips 107.1 ms; computed 2.00 MiB, free video memory -1.99 MiB  PASS
     512^2  driver: RGBA8, R UNORM 8 bit; GL errors: none; sampled 24/24 exact, max err 2.92e-08; upload+mips 410.6 ms; computed 8.00 MiB, free video memory -6.96 MiB  PASS
  RGBA16F:
      64^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 10.6 ms; computed 0.25 MiB, free video memory -2.00 MiB  PASS
     128^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 23.2 ms; computed 1.00 MiB, free video memory +10.13 MiB  PASS
     256^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 551.0 ms; computed 4.00 MiB, free video memory -3.87 MiB  PASS
     512^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 251.2 ms; computed 16.00 MiB, free video memory -13.71 MiB  PASS
  RGBA16F/float-upload:
      64^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 10.6 ms; computed 0.25 MiB, free video memory -2.00 MiB  PASS
     128^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 21.6 ms; computed 1.00 MiB, free video memory +19.58 MiB  PASS
     256^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 72.7 ms; computed 4.00 MiB, free video memory -3.87 MiB  PASS
     512^2  driver: RGBA16F, R FLOAT 16 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 252.8 ms; computed 16.00 MiB, free video memory -13.71 MiB  PASS
  RGBA32F:
      64^2  driver: RGBA32F, R FLOAT 32 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 11.4 ms; computed 0.50 MiB, free video memory -2.00 MiB  PASS
     128^2  driver: RGBA32F, R FLOAT 32 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 26.5 ms; computed 2.00 MiB, free video memory -0.84 MiB  PASS
     256^2  driver: RGBA32F, R FLOAT 32 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 80.5 ms; computed 8.00 MiB, free video memory -6.86 MiB  PASS
     512^2  driver: RGBA32F, R FLOAT 32 bit; GL errors: none; sampled 24/24 exact, max err 0; upload+mips 277.4 ms; computed 32.00 MiB, free video memory -25.70 MiB  PASS

[B] explicit mip levels / [C] filtering (64^2 marker cube, 16^2 gradient)
  [B] RGBA8    lods -1, 0, 1, 2, 3, 4, 5, 6, 7, 8.5 x 12 directions: 120/120 exact, max err 2.97e-08; GL errors: none  PASS
  [C] RGBA8    trilinear: lod 0..6 in 0.1 steps x 12 directions, max err 0.0031 level step (tolerance 0.0367), monotonic yes  PASS
  [C] RGBA8    bilinear: 1008 samples on a 16^2 gradient (fifths of a texel), max err 0.0017 texel step (tolerance 0.0513; 8-bit weights give <= 0.002); GL errors: none  PASS
  [B] RGBA16F  lods -1, 0, 1, 2, 3, 4, 5, 6, 7, 8.5 x 12 directions: 120/120 exact, max err 0; GL errors: none  PASS
  [C] RGBA16F  trilinear: lod 0..6 in 0.1 steps x 12 directions, max err 0.0031 level step (tolerance 0.0200), monotonic yes  PASS
  [C] RGBA16F  bilinear: 1008 samples on a 16^2 gradient (fifths of a texel), max err 0.0047 texel step (tolerance 0.0200; 8-bit weights give <= 0.002); GL errors: none  PASS
  [B] RGBA32F  lods -1, 0, 1, 2, 3, 4, 5, 6, 7, 8.5 x 12 directions: 120/120 exact, max err 0; GL errors: none  PASS
  [C] RGBA32F  trilinear: lod 0..6 in 0.1 steps x 12 directions, max err 0.0031 level step (tolerance 0.0200), monotonic yes  PASS
  [C] RGBA32F  bilinear: 1008 samples on a 16^2 gradient (fifths of a texel), max err 0.0016 texel step (tolerance 0.0200; 8-bit weights give <= 0.002); GL errors: none  PASS

[D] seams (64^2 smooth cube, every level)
  [D] RGBA8    12 edges x 7 positions, pairs 0.0001 either side of the edge; jump = largest RGB difference across the edge; expected off = clamp-to-edge bilinear per face
      level  size  expected off  jump off   jump on  interior  on <= tol
          0    64       0.01529   0.01529   0.00012   0.00021        yes
          1    32       0.02353   0.02353   0.00002   0.00021        yes
          2    16       0.05098   0.05098   0.00000   0.00000        yes
          3     8       0.10196   0.10196   0.00005   0.00000        yes
          4     4       0.20784   0.20784   0.00917   0.00000        yes
          5     2       0.40392   0.40392   0.06154   0.00000         NO
          6     1       0.85098   0.85098   0.16953   0.00000         NO
      seamless-off values vs the clamp-to-edge emulation: max err 0.00067
      -> FAIL: seams with the switch on (worst: level 6, jump 0.1695 vs step 0.851)
      image: C:\Users\Manuel\Mirai_Bastel\experiments\lookdev_gpu_probe\out\seams_RGBA8.png (rows lod 0, 3, 5, 6 top to bottom; left seamless off, right on)
  [D] RGBA16F  12 edges x 7 positions, pairs 0.0001 either side of the edge; jump = largest RGB difference across the edge; expected off = clamp-to-edge bilinear per face
      level  size  expected off  jump off   jump on  interior  on <= tol
          0    64       0.01216   0.01172   0.00049   0.00049        yes
          1    32       0.02476   0.02490   0.00003   0.00049        yes
          2    16       0.04980   0.04980   0.00000   0.00000        yes
          3     8       0.10156   0.10156   0.00049   0.00000        yes
          4     4       0.20947   0.20947   0.00928   0.00000        yes
          5     2       0.40662   0.40662   0.06201   0.00000         NO
          6     1       0.84906   0.84906   0.16943   0.00000         NO
      seamless-off values vs the clamp-to-edge emulation: max err 0.00065
      -> FAIL: seams with the switch on (worst: level 6, jump 0.1694 vs step 0.8491)
      image: C:\Users\Manuel\Mirai_Bastel\experiments\lookdev_gpu_probe\out\seams_RGBA16F.png (rows lod 0, 3, 5, 6 top to bottom; left seamless off, right on)
  [D] RGBA32F  12 edges x 7 positions, pairs 0.0001 either side of the edge; jump = largest RGB difference across the edge; expected off = clamp-to-edge bilinear per face
      level  size  expected off  jump off   jump on  interior  on <= tol
          0    64       0.01218   0.01218   0.00010   0.00020        yes
          1    32       0.02454   0.02454   0.00000   0.00020        yes
          2    16       0.04981   0.04981   0.00000   0.00000        yes
          3     8       0.10201   0.10201   0.00005   0.00000        yes
          4     4       0.20968   0.20968   0.00910   0.00000        yes
          5     2       0.40670   0.40670   0.06196   0.00000         NO
          6     1       0.84907   0.84907   0.16915   0.00000         NO
      seamless-off values vs the clamp-to-edge emulation: max err 0.00066
      -> FAIL: seams with the switch on (worst: level 6, jump 0.1692 vs step 0.8491)
      image: C:\Users\Manuel\Mirai_Bastel\experiments\lookdev_gpu_probe\out\seams_RGBA32F.png (rows lod 0, 3, 5, 6 top to bottom; left seamless off, right on)

[T] full-frame cube fetch cost (RGBA8 offscreen target)
  cube 128^2 + mips (smooth content), 1 textureLod per fragment, full-frame sphere-reflection directions; 40 rounds after 5, variants interleaved
  1024x768 (786432 px, 100 % covered), GL_TIME_ELAPSED ms; GL errors: none
    variant                                        p50     p95     min     max  - baseline  ns/px
    no fetch (baseline)                          0.144   0.145   0.139   0.149       0.000   0.18
    RGBA8 sharp lod 0 seamless off               0.184   0.184   0.182   0.184       0.039   0.23
    RGBA8 sharp lod 0 seamless on                0.184   0.184   0.182   0.184       0.039   0.23
    RGBA8 rough lod 4.5 seamless off             0.183   0.184   0.177   0.184       0.039   0.23
    RGBA8 rough lod 4.5 seamless on              0.183   0.184   0.182   0.184       0.039   0.23
    RGBA16F sharp lod 0 seamless off             0.184   0.184   0.182   0.185       0.039   0.23
    RGBA16F sharp lod 0 seamless on              0.183   0.184   0.182   0.184       0.039   0.23
    RGBA16F rough lod 4.5 seamless off           0.183   0.184   0.182   0.184       0.039   0.23
    RGBA16F rough lod 4.5 seamless on            0.183   0.184   0.179   0.184       0.039   0.23
    RGBA32F sharp lod 0 seamless off             0.184   0.184   0.182   0.184       0.039   0.23
    RGBA32F sharp lod 0 seamless on              0.183   0.184   0.179   0.184       0.039   0.23
    RGBA32F rough lod 4.5 seamless off           0.222   0.223   0.217   0.223       0.078   0.28
    RGBA32F rough lod 4.5 seamless on            0.222   0.223   0.222   0.223       0.078   0.28
  1920x1080 (2073600 px, 100 % covered), GL_TIME_ELAPSED ms; GL errors: none
    variant                                        p50     p95     min     max  - baseline  ns/px
    no fetch (baseline)                          0.377   0.378   0.377   0.381       0.000   0.18
    RGBA8 sharp lod 0 seamless off               0.480   0.480   0.473   0.481       0.102   0.23
    RGBA8 sharp lod 0 seamless on                0.480   0.480   0.474   0.481       0.102   0.23
    RGBA8 rough lod 4.5 seamless off             0.480   0.481   0.475   0.484       0.103   0.23
    RGBA8 rough lod 4.5 seamless on              0.480   0.480   0.478   0.481       0.102   0.23
    RGBA16F sharp lod 0 seamless off             0.480   0.480   0.478   0.481       0.103   0.23
    RGBA16F sharp lod 0 seamless on              0.480   0.480   0.478   0.481       0.103   0.23
    RGBA16F rough lod 4.5 seamless off           0.480   0.480   0.478   0.481       0.103   0.23
    RGBA16F rough lod 4.5 seamless on            0.480   0.480   0.478   0.481       0.102   0.23
    RGBA32F sharp lod 0 seamless off             0.480   0.480   0.478   0.480       0.102   0.23
    RGBA32F sharp lod 0 seamless on              0.480   0.480   0.478   0.481       0.102   0.23
    RGBA32F rough lod 4.5 seamless off           0.575   0.575   0.570   0.576       0.197   0.28
    RGBA32F rough lod 4.5 seamless on            0.575   0.576   0.573   0.579       0.198   0.28

[R] resources and GL state
  created: 29 texture, 3 buffer, 3 framebuffer, 3 renderbuffer, 1 query, 2 vertex_array, 2 program, 4 shader; still alive after release: none
  GL state after the probe vs before: identical
  glGetError at the end: none
  GPU memory after release (KiB): dedicated 524288, total available 524288, current available 402256, eviction count 736, evicted 560916
  -> PASS

Summary (raw verdicts of this run - label them by machine in the results file):
  A     RGBA8 PASS; RGBA16F PASS; RGBA16F/float-upload PASS; RGBA32F PASS
  B     RGBA8 PASS; RGBA16F PASS; RGBA32F PASS
  C     RGBA8 trilinear PASS; RGBA8 bilinear PASS; RGBA16F trilinear PASS; RGBA16F bilinear PASS; RGBA32F trilinear PASS; RGBA32F bilinear PASS
  D     RGBA8 FAIL; RGBA16F FAIL; RGBA32F FAIL
  T     timing INFO
  R     hygiene PASS

All extensions (237):
  GL_ARB_ES2_compatibility GL_ARB_ES3_compatibility GL_ARB_arrays_of_arrays GL_ARB_base_instance
  GL_ARB_blend_func_extended GL_ARB_clear_buffer_object GL_ARB_color_buffer_float
  GL_ARB_compressed_texture_pixel_storage GL_ARB_conservative_depth GL_ARB_copy_buffer GL_ARB_copy_image
  GL_ARB_debug_output GL_ARB_depth_buffer_float GL_ARB_depth_clamp GL_ARB_depth_texture GL_ARB_draw_buffers
  GL_ARB_draw_elements_base_vertex GL_ARB_draw_instanced GL_ARB_enhanced_layouts GL_ARB_explicit_attrib_location
  GL_ARB_explicit_uniform_location GL_ARB_fragment_coord_conventions GL_ARB_fragment_layer_viewport
  GL_ARB_fragment_program GL_ARB_fragment_program_shadow GL_ARB_fragment_shader GL_ARB_framebuffer_no_attachments
  GL_ARB_framebuffer_object GL_ARB_framebuffer_sRGB GL_ARB_geometry_shader4 GL_ARB_get_program_binary
  GL_ARB_half_float_pixel GL_ARB_half_float_vertex GL_ARB_imaging GL_ARB_instanced_arrays GL_ARB_internalformat_query
  GL_ARB_internalformat_query2 GL_ARB_invalidate_subdata GL_ARB_map_buffer_alignment GL_ARB_map_buffer_range
  GL_ARB_multi_bind GL_ARB_multisample GL_ARB_multitexture GL_ARB_occlusion_query GL_ARB_occlusion_query2
  GL_ARB_pixel_buffer_object GL_ARB_point_parameters GL_ARB_point_sprite GL_ARB_program_interface_query
  GL_ARB_provoking_vertex GL_ARB_robust_buffer_access_behavior GL_ARB_robustness GL_ARB_sampler_objects
  GL_ARB_seamless_cube_map GL_ARB_separate_shader_objects GL_ARB_shader_bit_encoding GL_ARB_shader_objects
  GL_ARB_shader_texture_lod GL_ARB_shading_language_100 GL_ARB_shading_language_420pack
  GL_ARB_shading_language_include GL_ARB_shading_language_packing GL_ARB_shadow GL_ARB_stencil_texturing GL_ARB_sync
  GL_ARB_texture_border_clamp GL_ARB_texture_buffer_object GL_ARB_texture_buffer_range GL_ARB_texture_compression
  GL_ARB_texture_compression_rgtc GL_ARB_texture_cube_map GL_ARB_texture_env_add GL_ARB_texture_env_combine
  GL_ARB_texture_env_crossbar GL_ARB_texture_env_dot3 GL_ARB_texture_float GL_ARB_texture_mirror_clamp_to_edge
  GL_ARB_texture_mirrored_repeat GL_ARB_texture_multisample GL_ARB_texture_non_power_of_two
  GL_ARB_texture_query_levels GL_ARB_texture_rectangle GL_ARB_texture_rg GL_ARB_texture_rgb10_a2ui
  GL_ARB_texture_stencil8 GL_ARB_texture_storage GL_ARB_texture_storage_multisample GL_ARB_texture_swizzle
  GL_ARB_texture_view GL_ARB_timer_query GL_ARB_transpose_matrix GL_ARB_uniform_buffer_object
  GL_ARB_vertex_array_bgra GL_ARB_vertex_array_object GL_ARB_vertex_attrib_binding GL_ARB_vertex_buffer_object
  GL_ARB_vertex_program GL_ARB_vertex_shader GL_ARB_vertex_type_10f_11f_11f_rev GL_ARB_vertex_type_2_10_10_10_rev
  GL_ARB_viewport_array GL_ARB_window_pos GL_ATI_draw_buffers GL_ATI_texture_float GL_ATI_texture_mirror_once
  GL_EXTX_framebuffer_mixed_formats GL_EXT_Cg_shader GL_EXT_abgr GL_EXT_bgra GL_EXT_bindable_uniform
  GL_EXT_blend_color GL_EXT_blend_equation_separate GL_EXT_blend_func_separate GL_EXT_blend_minmax
  GL_EXT_blend_subtract GL_EXT_compiled_vertex_array GL_EXT_depth_bounds_test GL_EXT_direct_state_access
  GL_EXT_draw_buffers2 GL_EXT_draw_instanced GL_EXT_draw_range_elements GL_EXT_fog_coord GL_EXT_framebuffer_blit
  GL_EXT_framebuffer_multisample GL_EXT_framebuffer_multisample_blit_scaled GL_EXT_framebuffer_object
  GL_EXT_framebuffer_sRGB GL_EXT_geometry_shader4 GL_EXT_gpu_program_parameters GL_EXT_gpu_shader4
  GL_EXT_import_sync_object GL_EXT_multi_draw_arrays GL_EXT_packed_depth_stencil GL_EXT_packed_float
  GL_EXT_packed_pixels GL_EXT_pixel_buffer_object GL_EXT_point_parameters GL_EXT_provoking_vertex
  GL_EXT_rescale_normal GL_EXT_secondary_color GL_EXT_separate_shader_objects GL_EXT_separate_specular_color
  GL_EXT_shader_integer_mix GL_EXT_shadow_funcs GL_EXT_stencil_two_side GL_EXT_stencil_wrap GL_EXT_texture3D
  GL_EXT_texture_array GL_EXT_texture_buffer_object GL_EXT_texture_compression_dxt1 GL_EXT_texture_compression_latc
  GL_EXT_texture_compression_rgtc GL_EXT_texture_compression_s3tc GL_EXT_texture_cube_map GL_EXT_texture_edge_clamp
  GL_EXT_texture_env_add GL_EXT_texture_env_combine GL_EXT_texture_env_dot3 GL_EXT_texture_filter_anisotropic
  GL_EXT_texture_integer GL_EXT_texture_lod GL_EXT_texture_lod_bias GL_EXT_texture_mirror_clamp GL_EXT_texture_object
  GL_EXT_texture_sRGB GL_EXT_texture_sRGB_decode GL_EXT_texture_shared_exponent GL_EXT_texture_storage
  GL_EXT_texture_swizzle GL_EXT_timer_query GL_EXT_vertex_array GL_EXT_vertex_array_bgra GL_IBM_rasterpos_clip
  GL_IBM_texture_mirrored_repeat GL_KHR_debug GL_KTX_buffer_region GL_NVX_conditional_render GL_NVX_gpu_memory_info
  GL_NV_ES1_1_compatibility GL_NV_blend_square GL_NV_conditional_render GL_NV_copy_depth_to_color GL_NV_copy_image
  GL_NV_depth_buffer_float GL_NV_depth_clamp GL_NV_explicit_multisample GL_NV_fence GL_NV_float_buffer
  GL_NV_fog_distance GL_NV_fragment_program GL_NV_fragment_program2 GL_NV_fragment_program_option
  GL_NV_framebuffer_multisample_coverage GL_NV_geometry_shader4 GL_NV_gpu_program4 GL_NV_half_float
  GL_NV_light_max_exponent GL_NV_multisample_coverage GL_NV_multisample_filter_hint GL_NV_occlusion_query
  GL_NV_packed_depth_stencil GL_NV_parameter_buffer_object GL_NV_parameter_buffer_object2 GL_NV_path_rendering
  GL_NV_pixel_data_range GL_NV_point_sprite GL_NV_primitive_restart GL_NV_register_combiners
  GL_NV_register_combiners2 GL_NV_shader_buffer_load GL_NV_texgen_reflection GL_NV_texture_barrier
  GL_NV_texture_compression_vtc GL_NV_texture_env_combine4 GL_NV_texture_expand_normal GL_NV_texture_multisample
  GL_NV_texture_rectangle GL_NV_texture_shader GL_NV_texture_shader2 GL_NV_texture_shader3 GL_NV_transform_feedback
  GL_NV_vertex_array_range GL_NV_vertex_array_range2 GL_NV_vertex_buffer_unified_memory GL_NV_vertex_program
  GL_NV_vertex_program1_1 GL_NV_vertex_program2 GL_NV_vertex_program2_option GL_NV_vertex_program3 GL_S3_s3tc
  GL_SGIS_generate_mipmap GL_SGIS_texture_lod GL_SGIX_depth_texture GL_SGIX_shadow GL_SUN_slice_accum
  GL_WIN_swap_hint WGL_EXT_swap_control
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\drag_cost\probe_shading_gpu.py
Shading GPU probe (2026-11-11): one full shaded pass per face-data layout, GL_TIME_ELAPSED, ms
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit d61d06d1f4, working tree MODIFIED, src/ tree 94addddafd

[gollum_87k] 87500 V / 87500 F, 1024x768, Smooth, 112557 px covered, 40 rounds after 5
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            1.94     1.91     1.96              2.63   12401 px differ
  pre-o2         7.18     7.10     7.28              7.92   identical
  o2            11.24    11.11    11.34             12.13   identical
  o2-rgba        8.25     8.17     8.38              9.10   identical
  NOTE the GPU times vary a lot: is the driver set to maximum performance?
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\drag_cost\probe_shading_gpu.py --size 1920 1080
Shading GPU probe (2026-11-11): one full shaded pass per face-data layout, GL_TIME_ELAPSED, ms
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit d61d06d1f4, working tree MODIFIED, src/ tree 94addddafd

[gollum_87k] 87500 V / 87500 F, 1920x1080, Smooth, 222592 px covered, 40 rounds after 5
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            2.45     2.42     2.50              3.22   24700 px differ
  pre-o2         9.44     9.30     9.54             10.27   identical
  o2            14.71    14.58    14.85             15.75   identical
  o2-rgba       10.90    10.81    11.00             11.90   identical
  NOTE the GPU times vary a lot: is the driver set to maximum performance?
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\lookdev_gpu_probe\probe_worklight_coverage.py
Worklight coverage probe (2026-11-13): drag_cost/probe_shading_gpu.measure with the camera dollied in
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit d61d06d1f4, src/ tree 94addddafd at HEAD / 94addddafd on disk, working tree MODIFIED

[gollum_87k] 87500 V / 87500 F, 1024x768, Smooth, 112557 px covered, 40 rounds after 5
  dolly 1: coverage 14.3 % of 1024x768
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            1.94     1.91     1.97              3.15   12401 px differ
  pre-o2         7.18     7.07     7.33              8.53   identical
  o2            11.22    11.10    11.38             12.70   identical
  o2-rgba        8.25     8.18     8.34              9.73   identical
  NOTE the GPU times vary a lot: is the driver set to maximum performance?

[gollum_87k] 87500 V / 87500 F, 1024x768, Smooth, 488895 px covered, 40 rounds after 5
  dolly 0.5: coverage 62.2 % of 1024x768
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            2.97     2.94     3.01              4.20   63427 px differ
  pre-o2        11.20    11.10    11.29             12.51   identical
  o2            17.85    17.59    18.00             19.34   identical
  o2-rgba       13.01    12.84    13.26             14.56   identical
  NOTE the GPU times vary a lot: is the driver set to maximum performance?

[gollum_87k] 87500 V / 87500 F, 1024x768, Smooth, 773169 px covered, 40 rounds after 5
  dolly 0.3: coverage 98.3 % of 1024x768
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            2.93     2.89     2.95              4.13   99366 px differ
  pre-o2        10.45    10.37    10.52             11.81   identical
  o2            16.08    15.91    16.19             17.57   identical
  o2-rgba       11.93    11.84    12.00             13.43   identical
  NOTE the GPU times vary a lot: is the driver set to maximum performance?
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\lookdev_gpu_probe\probe_worklight_coverage.py --size 1920 1080
Worklight coverage probe (2026-11-13): drag_cost/probe_shading_gpu.measure with the camera dollied in
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit d61d06d1f4, src/ tree 94addddafd at HEAD / 94addddafd on disk, working tree MODIFIED

[gollum_87k] 87500 V / 87500 F, 1920x1080, Smooth, 222592 px covered, 40 rounds after 5
  dolly 1: coverage 10.7 % of 1920x1080
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            2.46     2.42     2.50              3.60   24700 px differ
  pre-o2         9.43     9.36     9.51             10.71   identical
  o2            14.74    14.52    14.86             16.21   identical
  o2-rgba       10.90    10.76    11.03             12.44   identical
  NOTE the GPU times vary a lot: is the driver set to maximum performance?

[gollum_87k] 87500 V / 87500 F, 1920x1080, Smooth, 968175 px covered, 40 rounds after 5
  dolly 0.5: coverage 46.7 % of 1920x1080
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            4.14     4.11     4.18              5.25   126067 px differ
  pre-o2        15.87    15.76    15.95             17.06   identical
  o2            24.98    24.79    25.21             26.48   identical
  o2-rgba       18.42    18.23    18.56             19.73   identical
  NOTE the GPU times vary a lot: is the driver set to maximum performance?

[gollum_87k] 87500 V / 87500 F, 1920x1080, Smooth, 2055642 px covered, 40 rounds after 5
  dolly 0.3: coverage 99.1 % of 1920x1080
  variant     GPU p50      min      max   draw+finish p50   image vs o2
  off            4.98     4.94     5.02              6.22   263921 px differ
  pre-o2        18.06    17.94    18.21             19.42   identical
  o2            26.76    26.48    26.89             28.17   identical
  o2-rgba       20.47    20.35    20.60             22.04   identical
  NOTE the GPU times vary a lot: is the driver set to maximum performance?
```
