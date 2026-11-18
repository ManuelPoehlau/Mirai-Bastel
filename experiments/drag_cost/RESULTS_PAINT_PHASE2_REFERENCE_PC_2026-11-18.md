# Paint Room Phase 2 — probe results, reference PC (2026-11-18)

**Probe:** `experiments/drag_cost/probe_paint.py` (AD-037 §10.7) with the Phase 2 dab on the cage, SubD 1 and SubD 2.
**Run by:** Manu, 2026-11-18, on the reference PC (Core 2 Quad Q9550, GeForce 9800 GTX, GL 3.3; REFERENCE_HARDWARE §1),
Python 3.12.10, NumPy 2.2.6. **Code:** commit `e349c8749b` (the probe prints the commit of the clone it runs in), src/ tree
`e4c5d8613c` = the Phase 2 state before the fixes of AD-037 §10.8a/b. Output verbatim below.

**Reading** (AD-037 §10.8b):
- **P-D** cage 1.90 s PASS, SubD 1 2.26 s FAIL, SubD 2 3.44 s FAIL: 3.0-3.6× the container (0.63 / 0.63 / 1.11 s).
  Worked on the same day (texels grouped by slot from the build, no sort: container 0.35 / 0.44 / 0.74 s) - re-run open.
- **P-A** passes on the cage and SubD 1 at 3 % and 5 % (total p95 13.3 / 15.7 ms at 3 %); SubD 2 fails at 3 % on the frame
  (10.5 ms: 72k triangles on the 9800 GTX) - SubD 2 is not what the head shows (the preview's 25,000-face cap → level 1).
  The dab itself 5.8-6.6 ms at 3 %, 9.6-10.8 ms at 5 % p50 (container × 2.1).
- **P-B** "frame" 4.41 / "deferred" 4.27 ms p50: the mip policy "frame" (§10.8a) costs 0.14 ms a frame.
- **P-C, P-E** pass. **P-F** 7.8 s FAIL: **6.35 s of it is "read base"** - reading the 2048² ZBrush texture (the container:
  0.04 s), the same cost that made the first dab wait ~7 s; the file writes are 12 ms (no per-file write cost). The probe now
  splits that read (P-G: file read, decode, which decoder, the PNG's row filters); the decoded image is cached per session.

```
Paint probe (AD-037 Phase 1e / 2) - commit e349c8749b, working tree MODIFIED, src/ tree e4c5d8613c
python 3.12.10, numpy 2.2.6, size 2048^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png, mirrored dab on

P-D room enter: paint surface build (texel map + tables), ms        bar <= 2000 ms
  cage    2,234 faces    1901 ms  (2,787,212 texels, 48 MiB)  PASS
  subd1   9,002 faces    2259 ms  (2,787,155 texels, 48 MiB)  FAIL
  subd2  36,008 faces    3435 ms  (2,787,155 texels, 48 MiB)  FAIL
GL: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2 / (3, 3)

P-A dab + composite + frame per dab, cage, 2048^2, ms      p50      p95      max
  radius  1.0 % (~409 texels with the mirror)
    dab            3.85     5.02     6.83
    composite      0.71     1.69     1.74
    frame          4.04     4.62     5.05
    total          8.69    10.46    10.66
  radius  3.0 % (~3,854 texels with the mirror)
    dab            5.75     7.33     8.22
    composite      1.89     2.85     2.95
    frame          4.05     4.72     4.82
    total         11.59    13.32    13.96  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,146 texels with the mirror)
    dab            9.61    11.42    12.53
    composite      3.88     4.39     5.01
    frame          4.47     5.32     6.32
    total         17.78    21.21    21.69  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,863 texels with the mirror)
    dab           30.17    32.89    34.03
    composite      7.67     9.73    10.23
    frame          5.56     7.05     7.07
    total         43.29    47.99    48.06

P-A dab + composite + frame per dab, subd1, 2048^2, ms      p50      p95      max
  radius  1.0 % (~398 texels with the mirror)
    dab            4.59    28.33   111.98
    composite      0.70     1.92     2.14
    frame          5.75    12.18    52.06
    total         11.06    58.68   118.82
  radius  3.0 % (~3,840 texels with the mirror)
    dab            6.29     7.70     8.04
    composite      1.94     2.84     2.91
    frame          6.04     6.53     6.59
    total         14.29    15.72    16.17  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,030 texels with the mirror)
    dab           10.07    11.82    11.90
    composite      3.74     4.42     4.49
    frame          6.25     7.12     7.29
    total         20.32    22.85    23.14  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,889 texels with the mirror)
    dab           31.19    34.45    35.13
    composite      7.97     9.85    10.29
    frame          6.94     8.44     8.78
    total         46.93    49.44    49.55

P-A dab + composite + frame per dab, subd2, 2048^2, ms      p50      p95      max
  radius  1.0 % (~384 texels with the mirror)
    dab            4.42     5.23     5.60
    composite      0.75     1.95     2.23
    frame         10.58    11.16    11.53
    total         16.09    17.51    17.60
  radius  3.0 % (~3,851 texels with the mirror)
    dab            6.60     7.97     8.32
    composite      1.97     2.87     2.95
    frame         10.52    11.54    11.66
    total         19.36    21.17    21.31  bar p95 <= 16.7: FAIL
  radius  5.0 % (~10,986 texels with the mirror)
    dab           10.79    12.27    12.88
    composite      3.68     4.48     4.53
    frame         11.24    11.95    12.51
    total         26.01    28.08    29.12  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,871 texels with the mirror)
    dab           29.74    33.54    34.36
    composite      7.74     9.80    10.00
    frame         12.11    13.69    36.21
    total         49.98    54.68    72.32

P-B mip policy, 3 % stroke (cage), frame ms      p50      p95      max
  frame          4.41     5.37     6.80   stroke-end frame 2.73
  deferred       4.27     4.84     5.09   stroke-end frame 4.03
  none           3.84     4.84     5.41   stroke-end frame 3.08

P-C orbit frame, ms                              p50      p95      max
  file texture      3.03     3.90     4.54
  live texture      2.96     3.65     4.56
  live - file p50 -0.07 ms  bar <= +1 ms: PASS

P-E Modeller frame (file texture) before / after a live texture existed
  same image: PASS;  p50 before 3.29 ms, after 3.75 ms

P-F save of a 4-layer stack
  first save 7788 ms (4 layers + 1 flat, 0.7 MiB)  bar <= 2000 ms: FAIL
    PNG encode (all files)            824 ms in 5 calls (max 175)
      of it: layers                   650 ms in 4 calls (max 175)
    write file                         12 ms in 5 calls (max 3)
    read base                        6350 ms in 1 call (max 6350)
    flatten (base + composite)       6919 ms in 1 call (max 6919)
  second save 1 ms (0 layers, 0 flat)  nothing written: PASS
```

## Second run (Manu, 2026-11-18, `--no-gl`, src/ tree `721b7fe088`: after §10.8b)

**Reading** (AD-037 §10.8c): **P-G finds the 6.5 s**: Manu's local `Gollum_cbf9c7702d.png` is not the repo's file (470,628
bytes, RGBA, rows filtered Sub 344 / Up 706 / **Paeth 998**; the repo's: 423,554 bytes, RGB, unfiltered) and the own
decoder reconstructs Paeth rows byte by byte in Python - the file read itself is 1 ms. Fixed: such a PNG goes to the
system decoder first (pyglet: WIC on Windows). P-D: cage 1.65 s PASS, SubD 1 2.02 s FAIL (by 22 ms), SubD 2 3.51 s; the
probe now splits P-D into the map's parts and the tables. P-A (CPU rows) passes everywhere at 3 % and 5 %.

```
Paint probe (AD-037 Phase 1e / 2) - commit c77f1696c2, working tree MODIFIED, src/ tree 721b7fe088
python 3.12.10, numpy 2.2.6, size 2048^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png, mirrored dab on

P-G base image (the ZBrush texture the room reads; reference PC 2026-11-18: 6.35 s in P-F)
  Gollum_cbf9c7702d.png: 470,628 bytes, 2048 x 2048, 8 bit, colour type 6, interlace 0, row filters none 0 sub 344 up 706 avg 0 paeth 998
  file read 1 ms, decode 6510 ms (own), total 6511 ms
  second read (cached) 0.2 ms
  plain re-read of the file 0.7 ms

P-D room enter: paint surface build (texel map + tables), ms        bar <= 2000 ms
  cage    2,234 faces    1650 ms  (2,787,212 texels, 48 MiB)  PASS
  subd1   9,002 faces    2022 ms  (2,787,155 texels, 48 MiB)  FAIL
  subd2  36,008 faces    3514 ms  (2,787,155 texels, 48 MiB)  FAIL

P-A dab + composite + frame per dab, cage, 2048^2, ms      p50      p95      max
  radius  1.0 % (~409 texels with the mirror)
    dab            3.76     4.66     6.16
    composite      0.63     1.56     1.79
    total          4.55     5.78     6.71
  radius  3.0 % (~3,854 texels with the mirror)
    dab            5.52     6.95     7.62
    composite      1.77     2.66     2.77
    total          7.38     9.01     9.24  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,146 texels with the mirror)
    dab            9.41    11.17    12.17
    composite      3.63     4.29     4.55
    total         12.87    15.22    16.04  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,863 texels with the mirror)
    dab           30.40    33.12    33.49
    composite      7.41     9.84    11.02
    total         38.56    41.68    41.84

P-A dab + composite + frame per dab, subd1, 2048^2, ms      p50      p95      max
  radius  1.0 % (~398 texels with the mirror)
    dab            4.00     5.00     5.61
    composite      0.71     1.73     1.87
    total          5.02     6.23     6.41
  radius  3.0 % (~3,840 texels with the mirror)
    dab            6.11     7.67     7.88
    composite      1.84     2.69     3.06
    total          8.04     9.48     9.89  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,030 texels with the mirror)
    dab            9.91    11.50    12.14
    composite      3.44     4.26     4.52
    total         13.55    15.07    16.01  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,889 texels with the mirror)
    dab           30.59    33.86    34.74
    composite      7.49     9.47     9.59
    total         38.95    41.87    42.30

P-A dab + composite + frame per dab, subd2, 2048^2, ms      p50      p95      max
  radius  1.0 % (~384 texels with the mirror)
    dab            4.23     5.32     5.40
    composite      0.70     1.74     2.16
    total          5.13     6.19     6.48
  radius  3.0 % (~3,851 texels with the mirror)
    dab            6.70     8.23     8.79
    composite      1.94     2.76     3.51
    total          8.97    10.25    10.38  bar p95 <= 16.7: PASS
  radius  5.0 % (~10,986 texels with the mirror)
    dab           10.81    12.21    14.63
    composite      3.59     4.24     4.92
    total         14.42    16.01    19.55  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,871 texels with the mirror)
    dab           32.84    37.15    40.03
    composite      7.72     9.67    28.77
    total         41.08    46.87    62.98

P-F save of a 4-layer stack (base image cache cleared: a cold read, as at the first save of a session)
  first save 8058 ms (4 layers + 1 flat, 0.7 MiB)  bar <= 2000 ms: FAIL
    PNG encode (all files)            825 ms in 5 calls (max 176)
      of it: layers                   650 ms in 4 calls (max 166)
    write file                         12 ms in 5 calls (max 3)
    read base                        6607 ms in 1 call (max 6607)
    flatten (base + composite)       7189 ms in 1 call (max 7189)
  second save 1 ms (0 layers, 0 flat)  nothing written: PASS
```
