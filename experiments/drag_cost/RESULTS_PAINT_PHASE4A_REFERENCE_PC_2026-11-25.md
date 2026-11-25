# Paint Room Phase 4a — probe results, reference PC (Manu, 2026-11-25)

**Probe:** `python experiments/drag_cost/probe_paint.py --surfaces cage,subd1` at `da2af8a` (Manu's working tree
"MODIFIED"; the `src/` tree hash printed below), reference PC (Q9550, GeForce 9800 GTX, OpenGL 3.3, Python 3.12.10,
NumPy 2.2.6). Output verbatim below (pasted by Manu in the session chat, 2026-11-25).

**Reading** (AD-037 §12.5):
- **P-H 3 % FAILED** on both surfaces: total p95 18.2 ms (cage) / 24.3 ms (SubD 1) against 16.7 ms. The dab alone was
  p95 13.2 / 16.7 ms — 1.9–2.2× the round dab of the same run (7.2 / 7.7 ms), which passes with 13.6 / 15.8 ms. Cause:
  the gather of the square's corners (`r √2`) and the wrap on ~20–25 % of the placements of this stroke (main and mirror,
  each with its own shortest-path round). Worked on the same day (AD-037 §12.7); re-run open.
- **P-H 5 % passes** (28.0 / 31.9 ms against 33 ms), tightly.
- **P-I passes** everywhere: the 2-s stroke's frame p95 16.4–21.1 ms (≤ 33), release → History 10.5–13.2 ms (≤ 250),
  finishing frames ≤ 8 ms. The flick (information, no bar) drains in 14–15 finishing frames of ≤ 47 ms: no freeze.
- P-A … P-G unchanged from Phase 2/3 (P-D 1.52–1.61 s, P-F 1.78 s, P-C +0.08 ms, P-E same image).

```
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> python experiments/drag_cost/probe_paint.py --surfaces cage,subd1
Paint probe (AD-037 Phase 1e / 2) - commit da2af8a1f8, working tree MODIFIED, src/ tree 09dd8d3438
python 3.12.10, numpy 2.2.6, size 2048^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png, mirrored dab on

P-G base image (the ZBrush texture the room reads; reference PC 2026-11-18: 6.35 s in P-F)
  Gollum_cbf9c7702d.png: 470,628 bytes, 2048 x 2048, 8 bit, colour type 6, interlace 0, row filters none 0 sub 344 up 706 avg 0 paeth 998
  file read 1 ms, decode 1223 ms (system (998 Average / Paeth rows)), total 1224 ms
  second read (cached) 0.3 ms
  plain re-read of the file 0.6 ms

P-D room enter: paint surface build (texel map + tables), ms        bar <= 2000 ms
  cage    2,234 faces    1611 ms  (2,787,212 texels, 48 MiB)  PASS
         map split 36, map raster 905, map ownership 551, tables 83
  subd1   9,002 faces    1523 ms  (2,787,155 texels, 48 MiB)  PASS
         map split 103, map raster 808, map ownership 439, tables 139
GL: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2 / (3, 3)

P-A dab + composite + frame per dab, cage, 2048^2, ms      p50      p95      max
  radius  1.0 % (~409 texels with the mirror)
    dab            4.07     5.96     9.69
    composite      0.93     1.76     1.88
    frame          3.92     5.70    13.70
    total          9.01    12.55    24.97
  radius  3.0 % (~3,854 texels with the mirror)
    dab            5.75     7.15     7.64
    composite      1.93     2.86     3.42
    frame          4.21     4.81     5.06
    total         11.69    13.60    14.51  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,146 texels with the mirror)
    dab            9.76    11.42    12.62
    composite      3.76     4.39     4.79
    frame          4.66     5.32     5.76
    total         17.99    19.74    21.64  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,863 texels with the mirror)
    dab           29.25    31.93    32.44
    composite      7.73    10.10    10.79
    frame          4.75     6.82     7.09
    total         42.73    46.20    47.40

P-A dab + composite + frame per dab, subd1, 2048^2, ms      p50      p95      max
  radius  1.0 % (~398 texels with the mirror)
    dab            4.23     5.24     6.44
    composite      0.73     1.87     1.92
    frame          5.70     6.36     7.11
    total         10.89    12.57    14.41
  radius  3.0 % (~3,840 texels with the mirror)
    dab            6.28     7.67     8.16
    composite      1.96     2.98     3.00
    frame          5.94     6.58     6.89
    total         14.34    15.77    16.39  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,030 texels with the mirror)
    dab           10.12    11.44    12.34
    composite      3.69     4.61     4.95
    frame          5.67     7.02     7.81
    total         19.94    22.36    23.36  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,889 texels with the mirror)
    dab           30.28    33.46    35.89
    composite      7.83     9.66    10.40
    frame          6.78     8.43     8.58
    total         45.91    49.51    50.61

P-H alpha placement (Poren, mirror) + composite + frame, cage, 2048^2, ms   p50      p95      max
  radius  3.0 % (~982 texels with the mirror, 25 % wrapped)
    dab            8.49    13.24    13.63
    composite      1.55     2.84     2.95
    frame          3.95     4.84     4.92
    total         14.38    18.23    20.62  bar p95 <= 16.7: FAIL
  radius  5.0 % (~2,418 texels with the mirror, 15 % wrapped)
    dab           13.58    22.15    22.79
    composite      3.01     4.18     4.26
    frame          3.86     4.99     5.39
    total         21.34    28.01    29.18  bar p95 <= 33.0: PASS

P-H alpha placement (Poren, mirror) + composite + frame, subd1, 2048^2, ms   p50      p95      max
  radius  3.0 % (~934 texels with the mirror, 20 % wrapped)
    dab            8.90    16.71    16.96
    composite      1.82     2.84     2.90
    frame          5.73     6.60     6.83
    total         16.51    24.27    25.14  bar p95 <= 16.7: FAIL
  radius  5.0 % (~2,530 texels with the mirror, 10 % wrapped)
    dab           13.59    23.44    26.18
    composite      3.04     4.21     4.33
    frame          6.44     7.04     7.28
    total         23.53    31.88    33.62  bar p95 <= 33.0: PASS

P-I 2-s fast stroke, round, 3 %, cage: 114 placements (12.5 % spacing), 120 frames + 1 finishing
  stroke frame ms     14.07    18.80    22.68  bar p95 <= 33: PASS
  release -> History   10.8 ms  bar <= 250: PASS;  finishing frame max 7.0 ms  bar <= 50: PASS

P-I flick (10 frames), round, 3 %, cage: 112 placements (12.5 % spacing), 10 frames + 14 finishing
  stroke frame ms     31.41    36.90    36.90  (info, no bar)
  release -> History  542.5 ms  (info, no bar);  finishing frame max 43.4 ms  bar <= 50: PASS

P-I 2-s fast stroke, Poren, 3 %, cage: 15 placements (100.0 % spacing), 120 frames + 1 finishing
  stroke frame ms      6.25    16.38    18.15  bar p95 <= 33: PASS
  release -> History   10.5 ms  bar <= 250: PASS;  finishing frame max 6.8 ms  bar <= 50: PASS

P-I flick (10 frames), Poren, 3 %, cage: 14 placements (100.0 % spacing), 10 frames + 3 finishing
  stroke frame ms     19.54    24.96    24.96  (info, no bar)
  release -> History  112.8 ms  (info, no bar);  finishing frame max 41.5 ms  bar <= 50: PASS

P-I 2-s fast stroke, round, 3 %, subd1: 110 placements (12.5 % spacing), 120 frames + 1 finishing
  stroke frame ms     16.34    21.06    22.46  bar p95 <= 33: PASS
  release -> History   13.2 ms  bar <= 250: PASS;  finishing frame max 8.0 ms  bar <= 50: PASS

P-I flick (10 frames), round, 3 %, subd1: 109 placements (12.5 % spacing), 10 frames + 15 finishing
  stroke frame ms     32.13    36.71    36.71  (info, no bar)
  release -> History  605.0 ms  (info, no bar);  finishing frame max 46.6 ms  bar <= 50: PASS

P-I 2-s fast stroke, Poren, 3 %, subd1: 14 placements (100.0 % spacing), 120 frames + 1 finishing
  stroke frame ms      8.69    18.77    25.48  bar p95 <= 33: PASS
  release -> History   11.3 ms  bar <= 250: PASS;  finishing frame max 6.2 ms  bar <= 50: PASS

P-I flick (10 frames), Poren, 3 %, subd1: 14 placements (100.0 % spacing), 10 frames + 3 finishing
  stroke frame ms     21.63    27.98    27.98  (info, no bar)
  release -> History  107.7 ms  (info, no bar);  finishing frame max 40.8 ms  bar <= 50: PASS

P-B mip policy, 3 % stroke (cage), frame ms      p50      p95      max
  frame          5.08     5.59     6.61   stroke-end frame 2.71
  deferred       3.94     4.75     6.52   stroke-end frame 3.45
  none           3.75     4.85    36.79   stroke-end frame 2.81

P-C orbit frame, ms                              p50      p95      max
  file texture      3.18     4.02     4.88
  live texture      3.26     3.73     3.74
  live - file p50 +0.08 ms  bar <= +1 ms: PASS

P-E Modeller frame (file texture) before / after a live texture existed
  same image: PASS;  p50 before 3.88 ms, after 3.74 ms

P-F save of a 4-layer stack (base image cache cleared: a cold read, as at the first save of a session)
  first save 1778 ms (4 layers + 1 flat, 0.7 MiB)  bar <= 2000 ms: PASS
    PNG encode (all files)            826 ms in 5 calls (max 173)
      of it: layers                   653 ms in 4 calls (max 167)
    write file                         11 ms in 5 calls (max 2)
    read base                         245 ms in 1 call (max 245)
    flatten (base + composite)        907 ms in 1 call (max 907)
  second save 1 ms (0 layers, 0 flat)  nothing written: PASS
```

## Second run after the optimisation (Manu, 2026-11-25, at `0ff03c8`)

**Reading** (AD-037 §12.7): **every 4a gate passes.** P-H 3 % total p95 **14.05 ms (cage) / 16.01 ms (SubD 1)** against
16.7 ms (was 18.23 / 24.27); its dab p95 7.33 / 7.59 ms is the round dab's of the same run (7.68 / 8.30 ms), 0 % wrapped.
P-H 5 % 24.84 / 28.21 ms (≤ 33; 10–15 % wrapped). P-I: 2-s stroke frame p95 14.8–20.0 ms, release → History 9.7–12.1 ms,
finishing frames ≤ 6.6 ms; flicks (information) drain in ≤ 14 frames of ≤ 44.4 ms. SubD 1 at 3 % is tight for the
alpha (0.7 ms margin) as for the round dab (16.39 ms, 0.3 ms margin). One outlier unrelated to 4a: P-A round 1 % on the
cage, max 293 ms / frame p95 28 ms (a stall of the machine during that row; the same row was 9.0 / 12.6 ms in the first
run and the rows around it are normal).

```
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> python experiments/drag_cost/probe_paint.py --surfaces cage,subd1
Paint probe (AD-037 Phase 1e / 2) - commit 0ff03c8260, working tree MODIFIED, src/ tree b7cecbcb24
python 3.12.10, numpy 2.2.6, size 2048^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png, mirrored dab on

P-G base image (the ZBrush texture the room reads; reference PC 2026-11-18: 6.35 s in P-F)
  Gollum_cbf9c7702d.png: 470,628 bytes, 2048 x 2048, 8 bit, colour type 6, interlace 0, row filters none 0 sub 344 up 706 avg 0 paeth 998
  file read 1 ms, decode 1120 ms (system (998 Average / Paeth rows)), total 1121 ms
  second read (cached) 0.3 ms
  plain re-read of the file 0.9 ms

P-D room enter: paint surface build (texel map + tables), ms        bar <= 2000 ms
  cage    2,234 faces    1681 ms  (2,787,212 texels, 48 MiB)  PASS
         map split 53, map raster 887, map ownership 573, tables 130
  subd1   9,002 faces    1386 ms  (2,787,155 texels, 48 MiB)  PASS
         map split 109, map raster 748, map ownership 364, tables 132
GL: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2 / (3, 3)

P-A dab + composite + frame per dab, cage, 2048^2, ms      p50      p95      max
  radius  1.0 % (~409 texels with the mirror)
    dab            4.13    25.74   293.42
    composite      0.76     1.79     5.39
    frame          4.05    28.06    30.13
    total          9.03    56.19   328.94
  radius  3.0 % (~3,854 texels with the mirror)
    dab            5.72     7.68    10.07
    composite      1.91     3.11     4.06
    frame          4.28     5.11     5.80
    total         11.91    15.72    17.82  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,146 texels with the mirror)
    dab            9.66    11.17    11.79
    composite      3.56     4.46     4.54
    frame          4.74     5.38     5.86
    total         18.06    20.54    21.12  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,863 texels with the mirror)
    dab           29.36    32.48    34.32
    composite      7.95    10.22    10.61
    frame          5.64     6.73     8.67
    total         43.89    47.66    48.55

P-A dab + composite + frame per dab, subd1, 2048^2, ms      p50      p95      max
  radius  1.0 % (~398 texels with the mirror)
    dab            4.18     4.87     5.43
    composite      0.69     1.82     1.90
    frame          5.77     6.34     6.62
    total         10.82    12.03    12.99
  radius  3.0 % (~3,840 texels with the mirror)
    dab            6.46     8.30     8.79
    composite      1.95     2.95     3.25
    frame          6.15     6.64     6.89
    total         14.85    16.39    17.24  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,030 texels with the mirror)
    dab           10.20    11.79    12.52
    composite      3.55     4.31     4.75
    frame          6.62     7.03     7.16
    total         20.31    22.38    23.83  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,889 texels with the mirror)
    dab           30.24    32.92    34.24
    composite      7.81     9.77    10.22
    frame          7.31     8.48     8.71
    total         46.18    49.99    50.21

P-H alpha placement (Poren, mirror) + composite + frame, cage, 2048^2, ms   p50      p95      max
  radius  3.0 % (~966 texels with the mirror, 0 % wrapped)
    dab            6.64     7.33     7.44
    composite      1.49     2.87     3.04
    frame          4.28     4.87     4.96
    total         12.46    14.05    14.59  bar p95 <= 16.7: PASS
  radius  5.0 % (~2,406 texels with the mirror, 15 % wrapped)
    dab           10.71    18.19    19.32
    composite      3.02     4.17     4.43
    frame          4.84     5.19     5.87
    total         19.05    24.84    26.45  bar p95 <= 33.0: PASS

P-H alpha placement (Poren, mirror) + composite + frame, subd1, 2048^2, ms   p50      p95      max
  radius  3.0 % (~946 texels with the mirror, 0 % wrapped)
    dab            6.96     7.59     8.10
    composite      1.87     2.86     2.98
    frame          6.13     6.52     6.70
    total         14.71    16.01    16.68  bar p95 <= 16.7: PASS
  radius  5.0 % (~2,518 texels with the mirror, 10 % wrapped)
    dab           11.17    21.02    21.81
    composite      2.98     4.18     4.22
    frame          6.37     7.02     7.40
    total         21.18    28.21    30.25  bar p95 <= 33.0: PASS

P-I 2-s fast stroke, round, 3 %, cage: 114 placements (12.5 % spacing), 120 frames + 1 finishing
  stroke frame ms     13.53    18.31    21.79  bar p95 <= 33: PASS
  release -> History    9.9 ms  bar <= 250: PASS;  finishing frame max 6.5 ms  bar <= 50: PASS

P-I flick (10 frames), round, 3 %, cage: 112 placements (12.5 % spacing), 10 frames + 13 finishing
  stroke frame ms     29.47    31.54    31.54  (info, no bar)
  release -> History  506.0 ms  (info, no bar);  finishing frame max 42.9 ms  bar <= 50: PASS

P-I 2-s fast stroke, Poren, 3 %, cage: 15 placements (100.0 % spacing), 120 frames + 1 finishing
  stroke frame ms      6.29    14.82    20.96  bar p95 <= 33: PASS
  release -> History    9.7 ms  bar <= 250: PASS;  finishing frame max 6.6 ms  bar <= 50: PASS

P-I flick (10 frames), Poren, 3 %, cage: 14 placements (100.0 % spacing), 10 frames + 2 finishing
  stroke frame ms     17.48    21.99    21.99  (info, no bar)
  release -> History   68.0 ms  (info, no bar);  finishing frame max 39.8 ms  bar <= 50: PASS

P-I 2-s fast stroke, round, 3 %, subd1: 110 placements (12.5 % spacing), 120 frames + 1 finishing
  stroke frame ms     16.14    19.99    23.30  bar p95 <= 33: PASS
  release -> History   12.1 ms  bar <= 250: PASS;  finishing frame max 6.6 ms  bar <= 50: PASS

P-I flick (10 frames), round, 3 %, subd1: 109 placements (12.5 % spacing), 10 frames + 14 finishing
  stroke frame ms     31.02    33.69    33.69  (info, no bar)
  release -> History  564.8 ms  (info, no bar);  finishing frame max 44.4 ms  bar <= 50: PASS

P-I 2-s fast stroke, Poren, 3 %, subd1: 14 placements (100.0 % spacing), 120 frames + 1 finishing
  stroke frame ms      8.68    17.33    23.07  bar p95 <= 33: PASS
  release -> History   10.8 ms  bar <= 250: PASS;  finishing frame max 6.3 ms  bar <= 50: PASS

P-I flick (10 frames), Poren, 3 %, subd1: 14 placements (100.0 % spacing), 10 frames + 2 finishing
  stroke frame ms     21.32    24.77    24.77  (info, no bar)
  release -> History   75.6 ms  (info, no bar);  finishing frame max 38.9 ms  bar <= 50: PASS

P-B mip policy, 3 % stroke (cage), frame ms      p50      p95      max
  frame          4.94     5.92     8.49   stroke-end frame 2.79
  deferred       4.41     4.90     5.92   stroke-end frame 4.32
  none           4.42     4.86     6.40   stroke-end frame 3.72

P-C orbit frame, ms                              p50      p95      max
  file texture      3.12     4.02     4.74
  live texture      3.16     3.73     5.51
  live - file p50 +0.04 ms  bar <= +1 ms: PASS

P-E Modeller frame (file texture) before / after a live texture existed
  same image: PASS;  p50 before 3.71 ms, after 3.70 ms

P-F save of a 4-layer stack (base image cache cleared: a cold read, as at the first save of a session)
  first save 1606 ms (4 layers + 1 flat, 0.7 MiB)  bar <= 2000 ms: PASS
    PNG encode (all files)            771 ms in 5 calls (max 170)
      of it: layers                   601 ms in 4 calls (max 159)
    write file                         11 ms in 5 calls (max 3)
    read base                         222 ms in 1 call (max 222)
    flatten (base + composite)        792 ms in 1 call (max 792)
  second save 1 ms (0 layers, 0 flat)  nothing written: PASS
```
