# Lookdev P1b Corneal Refraction — reference PC, 2026-11-14

**Run by Manu on 2026-11-14** (commit `27fe5f942b`, `src/` tree `94addddafd` = on disk; NVIDIA "Maximale Leistung
bevorzugen" as in the README). Labels: **MEASURED [RPC]** unless marked; **COMPUTED** = the CPU ray model (identical to
the container's numbers, as it must be); **[H]** = a reading. The run used Manu's own iris image
(`out/iris_custom.png`, 512×512 RGBA, sha1 `beff016e0ff3`); it changes the pictures, not the geometry, the ray classes
or (measurably) the timings. **Artist verdict: OPEN** (not given; P1 verdicts also open). Container counterpart:
[`RESULTS_REFRACTION_CONTAINER_2026-11-14.md`](RESULTS_REFRACTION_CONTAINER_2026-11-14.md).

## Kurzfassung für Manu (Deutsch)

- **Alles grün auf deiner 9800 GTX:** Die Brechungs-Shader rechnen auf dem NVIDIA-Compiler wie das Python-Modell; die
  Strahlklasse je Pixel stimmt zu 99,96–100 % (höchstens 4 Randpixel); die undurchsichtige Hornhaut schreibt die
  richtige Tiefe, mischt nicht und ist unabhängig von der Zeichenreihenfolge.
- **V2 kostet praktisch nichts:** gleich viel wie P1s T-C C2 (±0,04 ms) und weniger als P1s C1. **V3 kostet etwas mehr:**
  +0,3–0,4 ms bei 1024×768, +0,5–0,6 ms bei 1920×1080 gegenüber V2 (Front/¾). Sichtbar unterscheiden sich V2 und V3
  um höchstens 1,75 Pixel. T-D bleibt die teuerste Variante (gut doppelt so teuer wie T-C).
- **Zwei Testfehler, beide behoben (nach dem Lauf):** (1) Die P1-Sonde hat eine GL-Einstellung (Pixel-Ausrichtung)
  nicht zurückgestellt — ein alter Fehler in [Q5], der erst mit deiner eigenen Iris sichtbar wurde. (2) Der
  Windows-Decoder hat eine absichtlich kaputte PNG geschluckt; das Lab prüft PNG-Dateien jetzt selbst, auf jedem
  System gleich.

## 1. Run record

| Field | Value |
|---|---|
| Machine | reference PC: Core 2 Quad Q9550 @ 2.83 GHz, GeForce 9800 GTX/9800 GTX+, Windows 10 (19045) |
| Interpreter | `.venv312`: Python 3.12.10, numpy 2.2.6, pyglet 2.1.19 |
| GL | 3.3.0 / NVIDIA / GLSL 3.30 via Cg, core profile; `EVIDENCE:` hardware renderer |
| Iris image | custom, 512×512 8-bit RGBA, sha1 `beff016e0ff3` |
| Lab tests | **2 failed, 111 passed** (211 s) — both failures analysed and fixed in §4 |

## 2. Probe verdicts

| Check | Result | Label |
|---|---|---|
| [M] CPU ray model | identical to the container (magnification 1.136 / 1.135, V2→V3 ≤ 1.75 px, ...) | COMPUTED |
| [P] refraction parity, 8 cases | PASS; ray classes equal everywhere; positions ≤ 9.9·10⁻⁵ units (1.2 µm) | MEASURED [RPC] |
| [K] GPU ray class vs CPU model, 1024×768 | PASS: front 100 % / 99.998 % (V2 / V3, 0 / 4 px differ), ¾ 99.998 % / 100 % (2 / 0), profile 100 % / 99.959 % (0 / 2) | MEASURED [RPC] |
| [D] opaque cornea | PASS: blend off, depth mask on after the frame; depth at the cornea centre 0.969838 = analytic anterior surface (iris behind 0.977146); identical with the iris mesh drawn under it; 0 px differ in reverse draw order | MEASURED [RPC] |
| [V] GL errors, 8 runs × 3 views × 2 sizes | none | MEASURED [RPC] |
| [R] hygiene | PASS | MEASURED [RPC] |

## 3. GPU time per frame (clear + background + eye, eye ≈ 50 %), GL_TIME_ELAPSED p50 ms

30 frames after 5, runs interleaved; p95 within ≈ 3 % of p50 everywhere.

| Run | 1024×768 front | ¾ | profile | 1920×1080 front | ¾ | profile |
|---|---|---|---|---|---|---|
| T-C V1 C2 (= P1's default) | 1.15 | 1.00 | 0.78 | 2.74 | 2.40 | 1.89 |
| T-C V1 C1 | 1.30 | 1.13 | 0.77 | 2.88 | 2.57 | 1.87 |
| **T-C V2** | **1.17** | **1.01** | 0.78 | **2.78** | **2.39** | 1.90 |
| **T-C V3** | **1.60** | **1.33** | 0.83 | **3.39** | **2.85** | 1.95 |
| T-B V2 / V3 | 1.02 / 1.40 | 0.88 / 1.17 | 0.67 / 0.71 | 2.46 / 3.02 | 2.10 / 2.51 | 1.65 / 1.69 |
| T-D V2 / V3 | 1.92 / 2.55 | 1.77 / 2.21 | 1.46 / 1.52 | 4.40 / 5.29 | 4.10 / 4.69 | 3.47 / 3.55 |
| background alone | 0.31 | 0.31 | 0.31 | 0.81 | 0.81 | 0.81 |

P1's T-C C2 timings of the earlier run (1.15 / 1.00 / 0.78 and 2.74 / 2.41 / 1.89 ms) are reproduced within 0.01 ms.

**Readings [H]:**
1. **V2 costs what P1's cornea already cost:** T-C V2 is within ±0.04 ms of T-C V1 C2 at every view and size, and
   below V1 C1 (whose iris fragments ran the analytic-cornea specular). The opaque pass draws the cornea once and skips
   the iris mesh, which pays for the ray march.
2. **V3 adds 0.32–0.43 ms (1024×768) and 0.46–0.61 ms (1920×1080)** over V2 at front / ¾ (≈ 25–37 % / 19–22 % of
   the frame), for the second sphere intersection, refraction and Fresnel term per cornea fragment. In profile, with
   few cornea fragments, the difference is ≤ 0.08 ms.
3. **Image difference V2 → V3** (COMPUTED, §2 of the container file): iris features ≤ 1.75 px, visible only in the
   limbal band. So on this PC V3 costs about a third more cornea time for a sub-2-pixel change; whether that change is
   worth it is the Artist's call (open).
4. **T-D stays the most expensive** (1.6–1.9× T-C with refraction), as in P1.
5. CPU submission 4.4–7.3 ms per frame: lab Python, as in P1 (not a GPU cost).

## 4. The two test failures of this run, and what was fixed

1. **`test_a_small_probe_run_passes_every_check_and_cleans_up` (P1 probe, [R] hygiene FAIL:
   `GL_UNPACK_ALIGNMENT 4 -> 1`).** Cause: P1's [Q5] sRGB check sets the unpack alignment to 1 for its 256×1 upload
   inside `probe_gl_caps.preserved`, which restores bindings but not the pixel-store state. Until now pyglet's lazy
   loading of the procedural iris *after* [Q5] happened to set it back to 4; with the custom iris the image is loaded
   (and checked) when the scene is built, before [Q5], so the old leak showed. Fixed in `probe_eye.srgb` (saves and
   restores the alignment), pinned by `test_srgb_section_leaves_the_unpack_alignment_as_found`. Not a measurement error:
   the timings and every other verdict of the P1 probe were unaffected. TESTED [C]: reproduced with a 512² RGBA custom
   image, then PASS after the fix.
2. **`test_undecodable_custom_iris_falls_back_to_the_procedural_one`.** The test wrote a PNG with a valid header but
   garbage image data. On Linux pyglet's decoder rejects it; on Windows pyglet decodes PNGs through the OS's codec,
   which **accepted** it (so the lab would have shown whatever that codec produced). Fixed in `iris_source.inspect`:
   the lab now checks every PNG itself — chunk CRCs, IHDR, PLTE / IEND, and the image data must inflate to exactly the
   size IHDR implies — so the verdict is the same on every platform; the loader check stays as a second step.
   15 headless tests cover the cases (incl. interlaced and palette images that must pass).

## 5. Raw output (Manu, pasted; test failure tracebacks shortened to their assertion)

```
& $py -m pytest experiments\lookdev_eye_lab\tests -q
FAILED experiments/lookdev_eye_lab/tests/test_gl_eye_lab.py::test_a_small_probe_run_passes_every_check_and_cleans_up
    ([R] GL state after vs before: DIFFERENT: GL_UNPACK_ALIGNMENT: (4,) -> (1,); all other checks PASS;
     iris texture: CUSTOM iris_custom.png - 512x512, 8-bit RGBA, sha1 beff016e0ff3)
FAILED experiments/lookdev_eye_lab/tests/test_gl_refraction.py::test_undecodable_custom_iris_falls_back_to_the_procedural_one
    (assert not True: IrisSource(..., custom=True, note='32x32, 8-bit RGB, sha1 27c428f6879b'))
2 failed, 111 passed in 211.29s (0:03:31)

& $py experiments\lookdev_eye_lab\run_refraction.py --probe
Lookdev P1b corneal refraction probe (2026-11-14): ray model, parity, ray classes, depth / blending, timings, screenshots
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10, numpy 2.2.6, pyglet 2.1.19
Interpreter: C:\Users\Manuel\Mirai_Bastel\.venv312\Scripts\python.exe
Source: commit 27fe5f942b, src/ tree 94addddafd at HEAD / 94addddafd on disk, working tree MODIFIED
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
GL_VENDOR: NVIDIA Corporation
GL_SHADING_LANGUAGE_VERSION: 3.30 NVIDIA via Cg compiler
Context: core profile, flags 0; pyglet default config (as src/main.py)
Window 256x256 (hidden), framebuffer 256x256, scale 1.0, dpi 96; screens: 1200x1920
EVIDENCE: hardware renderer - label the results MEASURED [RPC] or MEASURED [MAIN] by machine.
GPU memory (KiB): dedicated 524288, total available 524288, current available 289856, eviction count 753, evicted 607464

[M] corneal refraction, CPU ray model (cornea_optics.py); 1 unit = 12 mm
  (identical to RESULTS_REFRACTION_CONTAINER_2026-11-14.md section 5, line for line)

iris texture: CUSTOM iris_custom.png - 512x512, 8-bit RGBA, sha1 beff016e0ff3 (the CPU model [M] always uses the procedural image)

[P] refraction GLSL vs cornea_optics (refraction_parity.py, float32 inputs; read-back COMPLETE)
  function          max abs err  failed  compared              tolerance
  refract              1.34e-06       0      1024                  5e-06
  sphere_entry         1.42e-06       0      1024    2e-05 + class equal
  iris_cone_hit        9.93e-05       0      1024 2e-05 + 1e-05|x| + class equal
  limbus_schlick       4.34e-07       0      1024                  2e-06
  trace_hit            3.45e-05       0       993   0.0002 + class equal
  trace_entry           9.4e-05       0       993                 0.0002
  trace_hit             3.4e-05       0       997   0.0002 + class equal
  trace_entry          9.15e-05       0       997                 0.0002
  -> PASS

[K] ray class per pixel, GPU (DEBUG_KIND) vs CPU model, 1024x768, eye ~50 %; pixels where both see the cornea
  front          V2: GPU cornea px 185232, CPU 185512, compared 185232, same class 100.000 % (0 differ)
  front          V3: GPU cornea px 185232, CPU 185512, compared 185232, same class 99.998 % (4 differ)
  three_quarter  V2: GPU cornea px 106616, CPU 106799, compared 106616, same class 99.998 % (2 differ)
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
    T-C V1 C2        1.15     1.15     1.15     1.16     6.42                0  none
    T-C V1 C1        1.30     1.32     1.28     1.33     5.60           167789  none
    T-C V2           1.17     1.18     1.12     1.18     5.44           184610  none
    T-C V3           1.60     1.62     1.56     1.65     5.18           184612  none
    T-B V2           1.02     1.03     1.02     1.03     4.51           351872  none
    T-B V3           1.40     1.41     1.37     1.42     4.60           351880  none
    T-D V2           1.92     1.99     1.91     1.99     5.42           246695  none
    T-D V3           2.55     2.58     2.51     2.58     5.24           246699  none
    background       0.31     0.31     0.31     0.31     1.52           392852  none
    view three_quarter
    run           GPU p50      p95      min      max  CPU p50  px != T-C V1 C2  GL errors
    T-C V1 C2        1.00     1.00     1.00     1.01     6.65                0  none
    T-C V1 C1        1.13     1.15     1.12     1.15     5.13            96622  none
    T-C V2           1.01     1.01     1.00     1.01     5.33           106583  none
    T-C V3           1.33     1.36     1.31     1.37     5.13           106590  none
    T-B V2           0.88     0.88     0.87     0.88     4.52           311782  none
    T-B V3           1.17     1.18     1.14     1.19     4.56           311776  none
    T-D V2           1.77     1.77     1.75     1.78     5.38           168093  none
    T-D V3           2.21     2.25     2.19     2.25     5.33           168100  none
    background       0.31     0.31     0.31     0.31     1.51           395943  none
    view profile
    run           GPU p50      p95      min      max  CPU p50  px != T-C V1 C2  GL errors
    T-C V1 C2        0.78     0.78     0.78     0.78     7.17                0  none
    T-C V1 C1        0.77     0.77     0.77     0.78     5.30             4892  none
    T-C V2           0.78     0.78     0.78     0.79     5.43             4892  none
    T-C V3           0.83     0.83     0.82     0.84     5.24             4892  none
    T-B V2           0.67     0.68     0.67     0.68     4.54           304334  none
    T-B V3           0.71     0.72     0.70     0.72     4.55           304334  none
    T-D V2           1.46     1.48     1.45     1.48     5.40           115496  none
    T-D V3           1.52     1.53     1.51     1.54     5.41           115496  none
    background       0.31     0.31     0.31     0.31     1.52           397622  none
  1920x1080: target COMPLETE
    view front
    run           GPU p50      p95      min      max  CPU p50  px != T-C V1 C2  GL errors
    T-C V1 C2        2.74     2.74     2.74     2.74     7.26                0  none
    T-C V1 C1        2.88     2.89     2.87     2.89     5.78           498045  none
    T-C V2           2.78     2.78     2.77     2.79     5.48           546568  none
    T-C V3           3.39     3.43     3.34     3.44     5.40           546555  none
    T-B V2           2.46     2.46     2.45     2.46     4.62           942845  none
    T-B V3           3.02     3.04     2.98     3.06     4.63           942855  none
    T-D V2           4.40     4.41     4.39     4.54     5.18           699862  none
    T-D V3           5.29     5.33     5.27     5.33     5.56           699845  none
    background       0.81     0.81     0.81     0.81     1.45          1035807  none
    view three_quarter
    run           GPU p50      p95      min      max  CPU p50  px != T-C V1 C2  GL errors
    T-C V1 C2        2.40     2.41     2.40     2.41     6.55                0  none
    T-C V1 C1        2.57     2.58     2.56     2.59     5.74           272373  none
    T-C V2           2.39     2.40     2.39     2.40     5.28           299087  none
    T-C V3           2.85     2.87     2.79     2.88     5.42           299094  none
    T-B V2           2.10     2.10     2.09     2.10     4.44           829138  none
    T-B V3           2.51     2.53     2.48     2.54     4.41           829139  none
    T-D V2           4.10     4.10     4.09     4.11     5.39           451409  none
    T-D V3           4.69     4.72     4.65     4.73     5.47           451420  none
    background       0.81     0.81     0.81     0.81     1.46          1051447  none
    view profile
    run           GPU p50      p95      min      max  CPU p50  px != T-C V1 C2  GL errors
    T-C V1 C2        1.89     1.89     1.88     1.89     7.01                0  none
    T-C V1 C1        1.87     1.88     1.87     1.88     5.49             9442  none
    T-C V2           1.90     1.90     1.89     1.90     4.98             9442  none
    T-C V3           1.95     1.96     1.94     1.96     5.36             9442  none
    T-B V2           1.65     1.65     1.64     1.65     4.65           791881  none
    T-B V3           1.69     1.70     1.68     1.71     4.58           791881  none
    T-D V2           3.47     3.49     3.46     3.49     5.18           291637  none
    T-D V3           3.55     3.56     3.54     3.57     5.43           291637  none
    background       0.81     0.81     0.80     0.81     1.47          1046096  none

Supplementary view steep_75 (yaw 75, 1024x768, eye ~50 %), CPU model px: V1 pupil 0 / iris 0, V2 pupil 0 / iris 17010, V3 pupil 0 / iris 17010

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
