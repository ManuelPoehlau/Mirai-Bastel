# Lookdev P1b Corneal Refraction — container results, 2026-11-14

**What this is:** the agent's validation in the cloud container (Mesa llvmpipe, a CPU rasterizer). Labels:
**COMPUTED** = the CPU ray model (`cornea_optics.py`, deterministic NumPy: the same numbers on every machine; the
reference PC prints them again in section [M]); **TESTED [C]** = a GL check that passed in the container; **OPEN** = not
answerable here. Every GPU time in the raw output below is llvmpipe's and **not a GPU time**: the reference PC's
timings are **OPEN**. No Artist verdict (P1 verdicts stay open, Manu 2026-11-14). Commands: README "P1b".

## Kurzfassung für Manu (Deutsch)

- **Lichtbrechung ist ein großer Effekt, V2 gegen V3 ein kleiner — gemessen, nicht angenommen.** Ohne Brechung (V1)
  gegen mit (V2/V3): Iris-Details verschieben sich in der Großaufnahme um 23–52 Pixel (Median), bis 247 Pixel in der
  Dreiviertelansicht; die Pupille wirkt 13,5 % größer (Ferne) bzw. 17–30 % (Großaufnahme) und 0,6 mm näher.
  V2 gegen V3: Iris-Details 0,1–0,5 Pixel (Median), höchstens 1,75 Pixel. Sichtbar wird der Unterschied nur am
  Limbusrand (0,1–0,7 % der Hornhautpixel wechseln dort zwischen Iris und Limbusgewebe).
- **Seitenansicht:** Im Profil-Preset (90°, Großaufnahme) ist in keiner Variante Iris zu sehen. Kurz davor (75°) zeigt
  P1 gar keine Iris mehr, mit Brechung erscheint sie als Sichel durch die Hornhautwölbung. Aus der Ferne bleibt die
  Pupille mit Brechung bis 92,6° sichtbar, ohne bis 79,6° — so verhält es sich auch beim echten Auge.
- **Technisch geprüft (Container):** GPU rechnet wie das Python-Modell (Strahlklasse je Pixel 100 % gleich, bis auf
  2 Randpixel im Profil); V1 ist pixelgleich mit P1; die undurchsichtige Hornhaut schreibt Tiefe, mischt nicht und ist
  unabhängig von der Zeichenreihenfolge.
- **Offen:** die Zeiten auf deinem PC und dein Urteil.

## 1. Run record

| Field | Value |
|---|---|
| Machine | container: Intel Xeon @ 2.10 GHz, 4 logical cores, Linux 6.18; Mesa 25.2.8 llvmpipe, GL 4.5 core, Xvfb |
| Python, numpy, pyglet | 3.12.3, 2.2.6, 2.1.19 (the reference PC's versions) in a scratch venv outside the repository |
| Commit | `122fa740b7` + the untracked P1b files; `src/` tree `94addddafd` (unchanged) |
| P1 files | unchanged (`git diff` over the lab's existing files empty); P1b adds files only |
| Lab tests | see §4 |

## 2. CPU ray model (COMPUTED; section [M], 1 unit = 12 mm)

**Geometry.** Anterior surface = P1's cornea cap (r 7.80 mm), posterior sphere r 6.60 mm; central thickness 0.550 mm,
growing to 0.699 mm at r 4.8 mm, 0.762 mm at the chamber angle (r 5.59 mm) and 0.789 mm at the limbus (r 5.88 mm).
The chamber closes where the posterior sphere meets P1's iris cone (r 5.59 mm); between there and the anterior rim the
ray ends in limbal tissue. Pupil r 1.92 mm, 3.90 mm behind the apex (P1's geometry; a real anterior chamber is
~3.0–3.6 mm deep to the iris, so this eye is slightly deep).

**Front view, the virtual pupil.**

| Variant | Magnification paraxial / traced | Apparent depth behind the apex, paraxial / traced | Pupil visible off-axis to | Iris visible to |
|---|---|---|---|---|
| V1 | 1.000 / 1.000 | 3.896 / 3.896 mm | 79.6° | 84.6° |
| V2 (n 1.3375) | 1.144 / 1.136 | 3.333 / 3.270 mm | 92.6° | 115.5° |
| V3 (1.0 → 1.376 → 1.336) | 1.143 / 1.135 | 3.326 / 3.265 mm | 92.7° | 115.5° |

Traced = the pupil edge's virtual image triangulated from two on-axis cameras; the 0.7 % gap to paraxial is spherical
aberration at the pupil edge (r 1.92 mm of a 7.8 mm surface). The magnification matches the human entrance pupil
(~1.13, Gullstrand). "Visible to" includes occlusion by the sclera but no lids; 115° for the iris is an artefact of the
spherical, lid-less cornea, the pupil's 92.6° is in the range reported for real eyes.

**Per view, eye ≈ 50 % of the frame** (feature px = how far an iris point moves on screen, pixels where both variants
see iris; class changed = pixels whose ray ends in a different class; albedo = the iris image the rays see, no light):

| Size | View | V1→V2 feature px median / p95 / max | pupil scale, shift | V2→V3 feature px median / p95 / max | V2→V3 class changed | V2→V3 albedo diff p95 / max (8-bit) |
|---|---|---|---|---|---|---|
| 1024×768 | front | 22.6 / 24.9 / 24.9 | 1.17, 0 px | 0.12 / 0.83 / 0.99 | 1220 px (0.66 %) | 3 / 88 |
| 1024×768 | ¾ | 29.3 / 104 / 124 | 1.28, 23.6 px | 0.27 / 0.52 / 0.86 | 133 px (0.12 %) | 4 / 85 |
| 1024×768 | profile | no iris in any variant | — | 0.01 / 0.20 / 0.24 | 38 px | 0 / 39 |
| 1920×1080 | front | 42.4 / 46.8 / 46.9 | 1.18, 0 px | 0.21 / 1.48 / 1.75 | 3740 px (0.68 %) | 3 / 89 |
| 1920×1080 | ¾ | 52.0 / 198 / 247 | 1.30, 42.9 px | 0.49 / 0.91 / 1.45 | 333 px (0.11 %) | 4 / 85 |
| 1920×1080 | profile | no iris in any variant | — | 0.01 / 0.10 / 0.14 | 18 px | 0 / 5 |

**Reading.**
1. Refraction itself (V1 → V2/V3) is a large, view-dependent effect: the iris is magnified and pulled toward the viewer,
   and at ¾ it shifts and stretches by up to ~250 px at 1920×1080. It is not subtle even at the front view.
2. V2 vs V3 (one effective surface vs two interfaces): iris features differ by ≤ 1.75 px; the visible difference sits in
   the limbal band, where V2 and V3 send the rays near the chamber angle into tissue at slightly different radii
   (V3's ray bends more inside the cornea). On-axis the two virtual pupils differ by 0.002 mm in radius and 0.005 mm in
   depth. **[H]** That the difference is this small is a consequence of this geometry (a thin, nearly concentric
   cornea); a thicker or more aspheric cornea would differ more.
3. The profile preset sees only the cornea's edge at close-up distance (no iris in any variant); just before profile
   (supplementary 75° view: V1 no iris, V2/V3 an iris crescent of 17,010 px at 1024×768) is where refraction changes
   what is visible at all.

## 3. GL checks (TESTED [C])

| Check | Result |
|---|---|
| [P] parity, 8 cases (refract, sphere entry, iris cone, limbus weight / Schlick, full trace V2 / V3 hit + entry) | PASS; ray classes equal in every compared row; positions ≤ 1·10⁻⁴ units (1.2 µm) — float32 cancellation at grazing incidence, documented tolerances |
| [K] GPU ray class per pixel vs the CPU model (1024×768, three views, V2 / V3) | PASS; 100 % equal at front and ¾ (185,232 / 106,616 px), 99.96 % in profile (2 border px of 4,856) |
| V1 = P1 pixel for pixel (T-A, T-B, T-D × C1 / C2 / C3, front and ¾; T-A with V3) | PASS (test) |
| [D] opaque cornea pass | PASS: after the frame blend off and depth mask on; depth at the cornea centre 0.969838 = analytic anterior surface (iris behind: 0.977146); identical image with the iris mesh drawn under it; identical image with the parts drawn in reverse order (0 px) |
| Front-view magnification in the GPU image | PASS (test): pupil pixel area ratio V2 / straight in [1.10, 1.25] |
| [V] 8 runs × 3 views × 2 sizes, GL errors | none |
| [R] hygiene | PASS |
| GPU time per run | **OPEN** (llvmpipe) |

## 4. Tests

`xvfb-run -a python -m pytest experiments/lookdev_eye_lab/tests -q`: **103 passed** (P1's 48 unchanged + 55 P1b:
36 ray model, 4 headless state / keys, 15 GL). Without a display: 75 passed, 28 skipped (the GL tests).

## 5. Raw output (`xvfb-run -a python experiments/lookdev_eye_lab/run_refraction.py --probe`)

```
Lookdev P1b corneal refraction probe (2026-11-14): ray model, parity, ray classes, depth / blending, timings, screenshots
Platform: Linux-6.18.44-fc-v470-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.12.3, numpy 2.2.6, pyglet 2.1.19
Interpreter: <scratch>/venv312/bin/python
Source: commit 122fa740b7, src/ tree 94addddafd, working tree clean
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
GL_VENDOR: Mesa
GL_SHADING_LANGUAGE_VERSION: 4.50
Context: core profile, flags 0; pyglet default config (as src/main.py)
Window 256x256 (hidden), framebuffer 256x256, scale 1.0, dpi 96; screens: 1280x1024
EVIDENCE: SOFTWARE RENDERER - TESTED [C] at best; GL_TIME_ELAPSED here is not a GPU time.
Limits: TEXTURE_IMAGE_UNITS 32, COMBINED_TEXTURE_IMAGE_UNITS 192, TEXTURE_SIZE 16384, CUBE_MAP_TEXTURE_SIZE 16384, SAMPLES 4, COLOR_ATTACHMENTS 8, DRAW_BUFFERS 8, TEXTURE_BUFFER_SIZE 134217728, RENDERBUFFER_SIZE 16384, VIEWPORT_DIMS (16384, 16384), FRAGMENT_UNIFORM_COMPONENTS 16384, TEXTURE_LOD_BIAS 16.0, TEXTURE_MAX_ANISOTROPY 16.0
Extensions: GL_EXT_texture_filter_anisotropic, GL_ARB_texture_filter_anisotropic, GL_NVX_gpu_memory_info, GL_ATI_meminfo, GL_ARB_seamless_cube_map, GL_AMD_seamless_cubemap_per_texture, GL_ARB_seamless_cubemap_per_texture, GL_ARB_texture_cube_map_array, GL_ARB_texture_float, GL_ARB_half_float_pixel, GL_EXT_packed_float, GL_EXT_texture_shared_exponent, GL_EXT_texture_sRGB, GL_ARB_framebuffer_sRGB, GL_EXT_texture_sRGB_decode, GL_ARB_texture_query_lod, GL_ARB_texture_storage, GL_ARB_timer_query, GL_ARB_texture_buffer_object_rgb32, GL_ARB_texture_multisample, GL_ARB_sample_shading, GL_ARB_debug_output, GL_KHR_debug, GL_EXT_texture_compression_s3tc, GL_ARB_texture_compression_bptc
GPU memory (KiB): dedicated 220111872, total available 236585648, current available 0, eviction count 32764, evicted 1326272544, texture free (ATI) 0

[M] corneal refraction, CPU ray model (cornea_optics.py); 1 unit = 12 mm
  indices: air 1.0, cornea 1.376, aqueous 1.336, V2 effective 1.3375
  anterior r 7.80 mm, posterior r 6.60 mm, apex z 1.0946; chamber angle at r 5.59 mm, z 0.7910; limbus r 5.88 mm
  thickness along the anterior normal (mm): r 0.0: 0.550, r 2.4: 0.584, r 4.8: 0.699, r 5.6: 0.762, r 5.9: 0.789
  pupil: r 1.92 mm, 3.896 mm behind the apex
  variant paraxial mag paraxial depth mm traced mag traced depth mm pupil visible to iris visible to
  V1            1.0000             3.896     1.0000           3.896           79.6 d          84.6 d
  V2            1.1442             3.333     1.1361           3.270           92.6 d         115.5 d
  V3            1.1430             3.326     1.1353           3.265           92.7 d         115.5 d
  (traced = virtual pupil edge triangulated from two on-axis cameras; visible to = largest angle off the eye's axis, sclera occlusion included, no lids)
  1024x768, eye ~50 % of the frame (camera distance 2.532):
    view           pair   feature px med    p95    max pupil scale pupil shift px class changed px albedo diff mean  p95  max  >2/255
    front          cornea 185512 px: V1 pupil 17572 / limbus 0, V2 pupil 24136 / limbus 7752, V3 pupil 24128 / limbus 6540
                   V1-V2           22.64  24.88  24.93       1.172           0.00            14316            25.88   69  156  84.32%
                   V2-V3            0.12   0.83   0.99       1.000           0.00             1220             0.82    3   88   5.25%
                   V1-V3           22.93  25.14  25.19       1.172           0.00            13096            26.13   70  156  84.36%
    three_quarter  cornea 106799 px: V1 pupil 10130 / limbus 3540, V2 pupil 16574 / limbus 172, V3 pupil 16537 / limbus 100
                   V1-V2           29.29 104.49 124.42       1.279          23.58            11740            47.17  121  165  87.84%
                   V2-V3            0.27   0.52   0.86       0.999           0.18              133             1.31    4   85  14.70%
                   V1-V3           29.72 104.08 123.96       1.278          23.76            11701            47.31  121  165  87.92%
    profile        cornea 4886 px: V1 pupil 0 / limbus 4886, V2 pupil 0 / limbus 4398, V3 pupil 0 / limbus 4436
                   V1-V2             nan    nan    nan         nan            nan              488             1.63    0  134   2.99%
                   V2-V3            0.01   0.20   0.24         nan            nan               38             0.15    0   39   1.64%
                   V1-V3             nan    nan    nan         nan            nan              450             1.49    0  135   2.74%
  1920x1080, eye ~50 % of the frame (camera distance 2.229):
    view           pair   feature px med    p95    max pupil scale pupil shift px class changed px albedo diff mean  p95  max  >2/255
    front          cornea 549240 px: V1 pupil 50704 / limbus 0, V2 pupil 70688 / limbus 24236, V3 pupil 70624 / limbus 20560
                   V1-V2           42.39  46.84  46.92       1.181           0.00            44220            27.02   73  160  83.41%
                   V2-V3            0.21   1.48   1.75       1.000           0.00             3740             0.83    3   89   5.31%
                   V1-V3           42.94  47.36  47.45       1.180           0.00            40480            27.28   74  160  83.46%
    three_quarter  cornea 299646 px: V1 pupil 27251 / limbus 18670, V2 pupil 46372 / limbus 289, V3 pupil 46278 / limbus 150
                   V1-V2           52.04 197.77 246.98       1.304          42.87            43280            50.12  122  164  88.52%
                   V2-V3            0.49   0.91   1.45       0.999           0.34              333             1.39    4   85  16.65%
                   V1-V3           52.82 196.81 245.32       1.303          43.21            43269            50.26  122  164  88.66%
    profile        cornea 9406 px: V1 pupil 0 / limbus 9406, V2 pupil 0 / limbus 9256, V3 pupil 0 / limbus 9274
                   V1-V2             nan    nan    nan         nan            nan              150             0.02    0   42   0.09%
                   V2-V3            0.01   0.10   0.14         nan            nan               18             0.00    0    5   0.02%
                   V1-V3             nan    nan    nan         nan            nan              132             0.02    0   37   0.09%
  feature px = how far an iris point moves on screen between the two variants (pixels where both see iris); class changed = pixels whose ray ends in a different class (iris / pupil / limbus); albedo diff = the iris image the rays see, 8-bit levels, no lighting

[P] refraction GLSL vs cornea_optics (refraction_parity.py, float32 inputs; read-back COMPLETE)
  function          max abs err  failed  compared              tolerance
  refract               2.3e-06       0      1024                  5e-06
  sphere_entry         2.92e-06       0      1024    2e-05 + class equal
  iris_cone_hit        0.000223       0      1024 2e-05 + 1e-05|x| + class equal
  limbus_schlick       3.84e-07       0      1024                  2e-06
  trace_hit            2.68e-05       0       993   0.0002 + class equal
  trace_entry          6.33e-05       0       993                 0.0002
  trace_hit            3.53e-05       0       997   0.0002 + class equal
  trace_entry          9.56e-05       0       997                 0.0002
  -> PASS

[K] ray class per pixel, GPU (DEBUG_KIND) vs CPU model, 1024x768, eye ~50 %; pixels where both see the cornea
  front          V2: GPU cornea px 185232, CPU 185512, compared 185232, same class 100.000 % (0 differ)
  front          V3: GPU cornea px 185232, CPU 185512, compared 185232, same class 100.000 % (0 differ)
  three_quarter  V2: GPU cornea px 106616, CPU 106799, compared 106616, same class 100.000 % (0 differ)
  three_quarter  V3: GPU cornea px 106616, CPU 106799, compared 106616, same class 100.000 % (0 differ)
  profile        V2: GPU cornea px 4892, CPU 4886, compared 4856, same class 100.000 % (0 differ)
  profile        V3: GPU cornea px 4892, CPU 4886, compared 4856, same class 99.959 % (2 differ)
  -> PASS (threshold 99.9 %: border pixels may fall either way in float32)

[D] the opaque cornea pass (T-C V2, 3/4 view)
  after the frame: GL_BLEND off, depth write mask on (expected off / on)
  depth at the cornea centre pixel (197, 446): 0.969838; analytic anterior surface 0.969838; the iris straight behind 0.977146; the refracted iris point 0.975881
  iris mesh drawn under the cornea: image identical (0 px differ)
  parts drawn in reverse order (cornea first): 0 px differ (0.0000 % of the frame; ties along the shared limbus ring)
  -> PASS

[V] GPU time per frame (clear + background + eye), eye ~50 % of the frame, 30 frames after 5, runs interleaved; ms
  1024x768: target COMPLETE
    view front
    run           GPU p50      p95      min      max  CPU p50  px != T-C V1 C2  GL errors
    T-C V1 C2        0.18     0.32     0.06     3.37     3.24                0  none
    T-C V1 C1        0.23     0.30     0.06    15.13     2.58           175941  none
    T-C V2           0.22     2.15     0.06    13.56     2.33           175154  none
    T-C V3           0.22     2.24     0.06    14.00     2.27           175152  none
    T-B V2           0.11     3.08     0.05     9.93     2.15           355855  none
    T-B V3           0.09     2.86     0.06     9.96     2.12           355853  none
    T-D V2           0.21     4.45     0.06    16.43     2.34           239672  none
    T-D V3           0.20     0.49     0.06    12.43     2.42           239686  none
    background       0.08     0.11     0.05     1.85     0.61           392854  none
    view three_quarter
    run           GPU p50      p95      min      max  CPU p50  px != T-C V1 C2  GL errors
    T-C V1 C2        0.23     0.37     0.06     1.93     3.14                0  none
    T-C V1 C1        0.22     4.04     0.06    13.86     2.55           101617  none
    T-C V2           0.20     0.41     0.05    12.89     2.26           103529  none
    T-C V3           0.24     2.22     0.07    13.47     2.23           103567  none
    T-B V2           0.13     1.61     0.05    10.24     2.13           309701  none
    T-B V3           0.13     1.73     0.06     9.66     2.22           309698  none
    T-D V2           0.24     2.32     0.06    14.33     2.38           166389  none
    T-D V3           0.17     0.34     0.05    13.60     2.43           166411  none
    background       0.07     0.55     0.05     2.87     0.60           395945  none
    view profile
    run           GPU p50      p95      min      max  CPU p50  px != T-C V1 C2  GL errors
    T-C V1 C2        0.23     1.65     0.08     3.75     2.76                0  none
    T-C V1 C1        0.24     2.04     0.07    10.10     2.32             4892  none
    T-C V2           0.24     4.11     0.05     9.89     1.93             4892  none
    T-C V3           0.25     4.01     0.07     9.47     2.09             4892  none
    T-B V2           0.11     2.93     0.06     5.93     2.01           303807  none
    T-B V3           0.17     3.41     0.07     4.73     1.91           303807  none
    T-D V2           0.24     3.83     0.06     8.21     1.93           114750  none
    T-D V3           0.25     2.65     0.06     9.92     2.23           114750  none
    background       0.08     0.30     0.05     3.03     0.58           397622  none
  1920x1080: target COMPLETE
    view front
    run           GPU p50      p95      min      max  CPU p50  px != T-C V1 C2  GL errors
    T-C V1 C2        0.15     0.40     0.05     0.50     3.52                0  none
    T-C V1 C1        0.31     0.53     0.05    32.54     2.70           522043  none
    T-C V2           0.27     9.91     0.05    33.00     2.70           520042  none
    T-C V3           0.31     0.75     0.05    32.86     2.56           520005  none
    T-B V2           0.07     0.22     0.04    20.97     2.18           954833  none
    T-B V3           0.09     0.47     0.04    24.15     2.33           954825  none
    T-D V2           0.26     0.42     0.05    27.30     2.47           680778  none
    T-D V3           0.28     0.37     0.07    27.26     2.51           680748  none
    background       0.08     2.89     0.05     5.55     0.74          1035808  none
    view three_quarter
    run           GPU p50      p95      min      max  CPU p50  px != T-C V1 C2  GL errors
    T-C V1 C2        0.11     0.35     0.05     0.37     2.93                0  none
    T-C V1 C1        0.10     0.64     0.06    21.80     2.52           285577  none
    T-C V2           0.18     0.37     0.05    28.68     2.27           291333  none
    T-C V3           0.25     0.38     0.04    27.24     2.48           291382  none
    T-B V2           0.07     0.75     0.05    14.11     2.14           823381  none
    T-B V3           0.08     2.24     0.05    17.23     2.05           823385  none
    T-D V2           0.11     1.54     0.05    26.47     2.21           447605  none
    T-D V3           0.10     0.54     0.05    24.27     2.27           447622  none
    background       0.07     1.52     0.05     5.91     0.67          1051457  none
    view profile
    run           GPU p50      p95      min      max  CPU p50  px != T-C V1 C2  GL errors
    T-C V1 C2        0.12     0.38     0.06     1.21     3.34                0  none
    T-C V1 C1        0.09     0.35     0.06    17.07     2.79             9442  none
    T-C V2           0.21     0.38     0.05    20.39     2.22             9442  none
    T-C V3           0.24     0.33     0.06    20.59     2.10             9442  none
    T-B V2           0.08     0.22     0.05    10.37     2.04           791002  none
    T-B V3           0.08     0.20     0.05    11.48     2.18           791002  none
    T-D V2           0.27     0.41     0.06    17.50     2.36           288988  none
    T-D V3           0.10     0.37     0.05    17.55     2.47           288988  none
    background       0.07     2.58     0.05     5.26     0.69          1046096  none

Supplementary view steep_75 (yaw 75, 1024x768, eye ~50 %), CPU model px: V1 pupil 0 / iris 0, V2 pupil 0 / iris 17010, V3 pupil 0 / iris 17010
Screenshots: /home/user/Mirai-Bastel/experiments/lookdev_eye_lab/out/refraction - refraction_<view>_<run>.png (1024x768); refraction_sheet_<view>.png and refraction_sheet.png: cornea crops 560^2, columns T-C V1 C2 (P1) | T-C V2 | T-C V3 | |V3 - V2| x 8, rows front / 3/4 / profile / steep 75 (supplementary)

[R] resources and GL state
  lab objects: 1 texture, 1 buffer, 5 framebuffer, 10 renderbuffer, 1 query, 1 vertex_array; probe objects: 1 texture, 2 buffer, 1 framebuffer, 1 renderbuffer, 1 query, 1 vertex_array
  still alive after release: none
  GL state after vs before: identical
  glGetError at the end: none
  -> PASS

Summary (raw verdicts - label them by machine in the results file):
  PASS  P refraction parity
  PASS  K GPU ray classes = CPU model
  PASS  D opaque cornea: depth, blending, order
  PASS  V every run renders without GL error
  PASS  R hygiene
```
