# Paint Room Phase 4a — probe results, container (2026-11-25)

**Probe:** `experiments/drag_cost/probe_paint.py --surfaces cage,subd1` (AD-037 §12.5) at commit `a84ce85` (working tree
clean), new rows **P-H** (one alpha placement, "Poren" with the mirror, + composite + frame) and **P-I** (a 2-s fast
stroke and a 0.17-s flick through the stamp queue, then the finishing frames and the History step). **Machine:** the cloud
container (Xeon, Python 3.13.18, NumPy 2.2.6 pinned), GL = llvmpipe (software). Output verbatim below (P-A for
comparison in the same run; P-B … P-F omitted, unchanged).

**Reading** (AD-037 §12.5):
- The **frame** rows are llvmpipe rasterizing in software (5.5–7 ms cage, 10–15 ms SubD 1); they make the SubD 1 3 % rows
  FAIL here for the round dab (P-A, accepted on the reference PC with a 4–6 ms frame, §10.8e) and the alpha alike — not
  comparable to the 9800 GTX.
- **CPU part (dab + composite), 3 %, p95:** alpha 6.4 ms cage / 7.8 ms SubD 1 against the round dab's 4.2 / 4.9 ms in the
  same run (×1.5–1.6); at 5 %: 11.2 / 12.7 against 8.0 / 7.9 ms. 20–25 % of the alpha placements on this stroke wrapped.
- **P-I 2-s stroke:** every frame p95 ≤ 21 ms (with llvmpipe), release → History 8–17 ms, finishing frames ≤ 14 ms — the
  queue keeps up and nothing is left at the release. **The flick** (information, no bar): the round tip on SubD 1 leaves
  ~300 ms of work, drained in 7 finishing frames of ≤ 48 ms (no freeze); the alpha (100 % spacing) leaves nothing.
- Release → History includes `seam_pad` and the commit. (This run still printed bar verdicts on the flick rows; the probe
  now prints them as information.)

```
Paint probe (AD-037 Phase 1e / 2) - commit a84ce8568b, working tree clean
python 3.13.18, numpy 2.2.6, size 2048^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png, mirrored dab on

GL: llvmpipe (LLVM 20.1.2, 256 bits) / (4, 5)

P-A dab + composite + frame per dab, cage, 2048^2, ms      p50      p95      max
  radius  1.0 % (~409 texels with the mirror)
    dab            1.58     2.46     4.50
    composite      0.37     0.66     0.74
    frame          5.67     7.09    11.78
    total          7.81    10.40    14.39
  radius  3.0 % (~3,854 texels with the mirror)
    dab            2.38     3.07     3.44
    composite      0.75     1.13     1.18
    frame          5.51     7.03    13.81
    total          8.69    10.57    16.74  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,146 texels with the mirror)
    dab            4.28     5.59     7.30
    composite      1.55     2.38     2.86
    frame          6.08     9.17    12.53
    total         11.84    16.22    19.55  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,863 texels with the mirror)
    dab           11.73    16.75    18.73
    composite      2.88     4.67     6.73
    frame          6.72     8.91    12.45
    total         21.59    30.12    31.42

P-A dab + composite + frame per dab, subd1, 2048^2, ms      p50      p95      max
  radius  1.0 % (~398 texels with the mirror)
    dab            1.76     2.40     3.46
    composite      0.31     1.19     1.39
    frame          9.91    13.90    16.02
    total         12.10    17.21    18.72
  radius  3.0 % (~3,840 texels with the mirror)
    dab            2.72     3.35     3.72
    composite      0.76     1.53     1.72
    frame          9.66    13.14    16.78
    total         13.24    17.92    20.00  bar p95 <= 16.7: FAIL
  radius  5.0 % (~11,030 texels with the mirror)
    dab            4.59     5.62     6.35
    composite      1.49     2.24     2.66
    frame         10.49    13.95    17.16
    total         16.79    20.57    23.33  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,889 texels with the mirror)
    dab           12.41    14.87    16.66
    composite      3.05     4.07     4.91
    frame         11.41    14.30    16.59
    total         26.30    32.66    38.16

P-H alpha placement (Poren, mirror) + composite + frame, cage, 2048^2, ms   p50      p95      max
  radius  3.0 % (~982 texels with the mirror, 25 % wrapped)
    dab            3.40     5.14     6.66
    composite      0.73     1.28     1.42
    frame          5.74     7.28    12.46
    total         10.37    14.67    16.10  bar p95 <= 16.7: PASS
  radius  5.0 % (~2,418 texels with the mirror, 15 % wrapped)
    dab            5.83     8.60    13.00
    composite      1.32     2.57     3.37
    frame          6.65     9.09    14.27
    total         14.37    18.43    23.43  bar p95 <= 33.0: PASS

P-H alpha placement (Poren, mirror) + composite + frame, subd1, 2048^2, ms   p50      p95      max
  radius  3.0 % (~934 texels with the mirror, 20 % wrapped)
    dab            3.73     6.42     8.16
    composite      0.77     1.37     1.99
    frame         11.33    14.74    22.65
    total         15.71    20.78    28.64  bar p95 <= 16.7: FAIL
  radius  5.0 % (~2,530 texels with the mirror, 10 % wrapped)
    dab            5.54    10.48    13.07
    composite      1.48     2.17     2.60
    frame         11.77    14.60    22.86
    total         19.53    24.85    30.95  bar p95 <= 33.0: PASS

P-I 2-s fast stroke, round, 3 %, cage: 114 placements (12.5 % spacing), 120 frames + 1 finishing
  stroke frame ms      9.52    12.75    15.13  bar p95 <= 33: PASS
  release -> History    8.4 ms  bar <= 250: PASS;  finishing frame max 5.3 ms  bar <= 50: PASS

P-I flick (10 frames), round, 3 %, cage: 112 placements (12.5 % spacing), 10 frames + 5 finishing
  stroke frame ms     18.83    30.68    30.68  bar p95 <= 33: PASS
  release -> History  186.3 ms  bar <= 250: PASS;  finishing frame max 39.9 ms  bar <= 50: PASS

P-I 2-s fast stroke, Poren, 3 %, cage: 15 placements (100.0 % spacing), 120 frames + 1 finishing
  stroke frame ms      6.47    10.79    15.32  bar p95 <= 33: PASS
  release -> History    7.7 ms  bar <= 250: PASS;  finishing frame max 5.3 ms  bar <= 50: PASS

P-I flick (10 frames), Poren, 3 %, cage: 14 placements (100.0 % spacing), 10 frames + 1 finishing
  stroke frame ms     15.84    21.41    21.41  bar p95 <= 33: PASS
  release -> History    7.8 ms  bar <= 250: PASS;  finishing frame max 5.5 ms  bar <= 50: PASS

P-I 2-s fast stroke, round, 3 %, subd1: 110 placements (12.5 % spacing), 120 frames + 1 finishing
  stroke frame ms     15.08    20.71    25.45  bar p95 <= 33: PASS
  release -> History   12.7 ms  bar <= 250: PASS;  finishing frame max 10.2 ms  bar <= 50: PASS

P-I flick (10 frames), round, 3 %, subd1: 109 placements (12.5 % spacing), 10 frames + 7 finishing
  stroke frame ms     24.36    40.16    40.16  bar p95 <= 33: FAIL
  release -> History  299.0 ms  bar <= 250: FAIL;  finishing frame max 47.5 ms  bar <= 50: PASS

P-I 2-s fast stroke, Poren, 3 %, subd1: 14 placements (100.0 % spacing), 120 frames + 1 finishing
  stroke frame ms     13.18    17.71    27.09  bar p95 <= 33: PASS
  release -> History   17.0 ms  bar <= 250: PASS;  finishing frame max 14.0 ms  bar <= 50: PASS

P-I flick (10 frames), Poren, 3 %, subd1: 14 placements (100.0 % spacing), 10 frames + 1 finishing
  stroke frame ms     20.95    27.55    27.55  bar p95 <= 33: PASS
  release -> History   13.5 ms  bar <= 250: PASS;  finishing frame max 10.7 ms  bar <= 50: PASS

```

## After the optimisation (AD-037 §12.7, same day, container)

```
Paint probe (AD-037 Phase 1e / 2) - commit da2af8a1f8, working tree MODIFIED, src/ tree 6e8a701fbe
python 3.13.18, numpy 2.2.6, size 2048^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png, mirrored dab on

P-A dab + composite + frame per dab, cage, 2048^2, ms      p50      p95      max
  radius  1.0 % (~409 texels with the mirror)
    dab            1.47     2.20     2.50
    composite      0.30     0.61     0.80
    frame          5.08     6.69    10.92
    total          7.04     9.23    13.13
  radius  3.0 % (~3,854 texels with the mirror)
    dab            2.31     2.86     3.57
    composite      0.78     1.23     1.27
    frame          5.46     7.24    12.10
    total          8.65    10.54    15.15  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,146 texels with the mirror)
    dab            4.03     4.83     5.17
    composite      1.29     1.73     1.77
    frame          5.58     6.99    10.99
    total         10.95    12.77    16.58  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,863 texels with the mirror)
    dab           10.66    14.18    15.38
    composite      2.53     3.61     5.13
    frame          5.64     7.08    11.31
    total         19.48    25.30    27.66

P-A dab + composite + frame per dab, subd1, 2048^2, ms      p50      p95      max
  radius  1.0 % (~398 texels with the mirror)
    dab            1.61     2.14     2.57
    composite      0.31     0.72     0.80
    frame          9.29    11.73    14.01
    total         11.31    13.97    16.80
  radius  3.0 % (~3,840 texels with the mirror)
    dab            2.68     3.58     4.55
    composite      0.82     1.64     1.80
    frame         10.08    12.54    14.47
    total         13.66    17.11    17.87  bar p95 <= 16.7: FAIL
  radius  5.0 % (~11,030 texels with the mirror)
    dab            4.27     5.51     6.40
    composite      1.32     1.89     2.26
    frame         10.14    14.21    19.18
    total         15.58    21.79    24.75  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,889 texels with the mirror)
    dab           11.53    13.50    14.24
    composite      2.74     3.48     3.73
    frame          9.97    12.37    14.93
    total         24.15    28.29    30.08

P-H alpha placement (Poren, mirror) + composite + frame, cage, 2048^2, ms   p50      p95      max
  radius  3.0 % (~966 texels with the mirror, 0 % wrapped)
    dab            2.39     3.00     3.40
    composite      0.62     1.09     1.16
    frame          5.34     6.23    13.91
    total          8.44     9.40    17.31  bar p95 <= 16.7: PASS
  radius  5.0 % (~2,406 texels with the mirror, 15 % wrapped)
    dab            4.24     6.43     7.32
    composite      1.11     1.60     1.81
    frame          5.23     6.60    11.08
    total         10.98    13.53    15.74  bar p95 <= 33.0: PASS

P-H alpha placement (Poren, mirror) + composite + frame, subd1, 2048^2, ms   p50      p95      max
  radius  3.0 % (~946 texels with the mirror, 0 % wrapped)
    dab            2.54     3.23     4.09
    composite      0.65     1.02     1.11
    frame          8.54    10.90    14.85
    total         11.73    15.18    19.31  bar p95 <= 16.7: PASS
  radius  5.0 % (~2,518 texels with the mirror, 10 % wrapped)
    dab            3.89     7.85     9.62
    composite      1.14     1.62     1.82
    frame          9.23    11.09    13.44
    total         14.68    18.11    20.71  bar p95 <= 33.0: PASS

P-I 2-s fast stroke, round, 3 %, cage: 114 placements (12.5 % spacing), 120 frames + 1 finishing
  stroke frame ms      8.96    12.01    15.95  bar p95 <= 33: PASS
  release -> History    9.3 ms  bar <= 250: PASS;  finishing frame max 4.7 ms  bar <= 50: PASS

P-I flick (10 frames), round, 3 %, cage: 112 placements (12.5 % spacing), 10 frames + 5 finishing
  stroke frame ms     17.04    18.85    18.85  (info, no bar)
  release -> History  193.7 ms  (info, no bar);  finishing frame max 41.4 ms  bar <= 50: PASS

P-I 2-s fast stroke, Poren, 3 %, cage: 15 placements (100.0 % spacing), 120 frames + 1 finishing
  stroke frame ms      6.04     9.23    11.48  bar p95 <= 33: PASS
  release -> History    7.4 ms  bar <= 250: PASS;  finishing frame max 4.9 ms  bar <= 50: PASS

P-I flick (10 frames), Poren, 3 %, cage: 14 placements (100.0 % spacing), 10 frames + 1 finishing
  stroke frame ms     11.52    14.80    14.80  (info, no bar)
  release -> History    7.2 ms  (info, no bar);  finishing frame max 4.7 ms  bar <= 50: PASS

P-I 2-s fast stroke, round, 3 %, subd1: 110 placements (12.5 % spacing), 120 frames + 1 finishing
  stroke frame ms     11.83    13.96    19.85  bar p95 <= 33: PASS
  release -> History   10.4 ms  bar <= 250: PASS;  finishing frame max 7.9 ms  bar <= 50: PASS

P-I flick (10 frames), round, 3 %, subd1: 109 placements (12.5 % spacing), 10 frames + 4 finishing
  stroke frame ms     20.40    21.92    21.92  (info, no bar)
  release -> History  162.1 ms  (info, no bar);  finishing frame max 41.4 ms  bar <= 50: PASS

P-I 2-s fast stroke, Poren, 3 %, subd1: 14 placements (100.0 % spacing), 120 frames + 1 finishing
  stroke frame ms     10.71    13.46    18.83  bar p95 <= 33: PASS
  release -> History   11.2 ms  bar <= 250: PASS;  finishing frame max 8.8 ms  bar <= 50: PASS

P-I flick (10 frames), Poren, 3 %, subd1: 14 placements (100.0 % spacing), 10 frames + 1 finishing
  stroke frame ms     16.44    19.20    19.20  (info, no bar)
  release -> History   10.1 ms  (info, no bar);  finishing frame max 7.7 ms  bar <= 50: PASS

```
