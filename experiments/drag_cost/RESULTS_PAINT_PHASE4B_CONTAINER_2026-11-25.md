# Paint Room Phase 4b — probe results, container (2026-11-25)

**Probe:** `experiments/drag_cost/probe_paint.py --surfaces cage,subd1` (AD-037 §13.7) on the 4b working tree (on top of
`97d756d`), new rows **P-J** (one spray placement: 20 "Poren" stamps of 20 %, rotation ±180°, size ±30 %, flow ±30 %,
mirror; + composite + frame; the round spray as information) and **P-K** (a 10-s spray stroke: ten crossings of the face
through the stamp queue, 600 frames, then the finishing). P-H and P-I now paint through `stamp.paint` (the room's path).
**Machine:** the cloud container (Xeon, Python 3.13.18, NumPy 2.2.6 pinned), GL = llvmpipe (software: the frame rows
are not comparable to the 9800 GTX).

**Reading** (AD-037 §13.7):
- **P-J** 3 % spray, total p95 12.8 ms (cage) / 24.1 ms (SubD 1, of it 17.7 ms the llvmpipe frame) — gate ≤ 33 ms
  met here; the dab (CPU) p50 / p95 4.2 / 4.8 and 4.6 / 6.8 ms for 40 stamps (20 + their mirror).
- **P-K** 10-s spray stroke: no frame above 50 ms (max 22.1 / 35.3 ms); release → History 9.6 / 11.6 ms.
- **P-H 3 %** must not have become more expensive (AD-037 §12.6): see the A/B below — 4a and 4b are the same. (Its
  SubD 1 total "FAIL" here is the llvmpipe frame, 11–15 ms, as in the 4a container run and in P-A's round dab of the same
  run; the reference PC drew 4–6 ms.)

## A/B: a single placement without randomness, 4a (`4a49d5b`, frozen) against 4b, one process, interleaved

`stamp.paint` against the frozen 4a `evaluate` + `dab` (`tests/paint_stamp_4a_frozen.py`), 40 placements across the face
at 3 %, mirror on, 2048², 30 alternating runs each (1200 placements per row), ms:

```
cage   round  4a: p50 1.553  p95 2.023 ms  (n=1200)
cage   round  4b: p50 1.549  p95 2.005 ms  (n=1200)
cage   poren  4a: p50 1.764  p95 2.467 ms  (n=1200)
cage   poren  4b: p50 1.761  p95 2.544 ms  (n=1200)
subd1  round  4a: p50 1.537  p95 2.290 ms  (n=1200)
subd1  round  4b: p50 1.553  p95 2.260 ms  (n=1200)
subd1  poren  4a: p50 1.725  p95 2.222 ms  (n=1200)
subd1  poren  4b: p50 1.711  p95 2.034 ms  (n=1200)
```

The probe itself, `--no-gl`, run twice each in turn (4a worktree, 4b, 4a, 4b), P-H 3 % dab p50 / p95: cage 2.56 / 3.35,
2.48 / 3.75 (4a) and 2.47 / 3.70, 2.41 / 2.64 (4b); SubD 1 2.66 / 2.84, 2.61 / 2.92 (4a) and 2.75 / 3.08, 3.00 / 3.79 (4b)
— within the spread of P-A in the same runs (its code is untouched: SubD 1 2.83 / 2.75 / 2.54 / 3.03 p50).

## The probe (P-A 3 % for comparison, P-H … P-K verbatim; P-B … P-F omitted, unchanged)

```
Paint probe (AD-037 Phase 1e / 2 / 4a / 4b) - commit 97d756dfb6, working tree MODIFIED, src/ tree 15f9ba5f1e
python 3.13.18, numpy 2.2.6, size 2048^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png, mirrored dab on

GL: llvmpipe (LLVM 20.1.2, 256 bits) / (4, 5)

P-A dab + composite + frame per dab, cage, 2048^2, ms      p50      p95      max
  radius  1.0 % (~409 texels with the mirror)
    dab            1.81     2.64     3.53
    composite      0.37     0.75     2.58
    frame          6.37    11.60    13.47
    total          8.67    13.47    16.32
  radius  3.0 % (~3,854 texels with the mirror)
    dab            2.63     3.27     3.96
    composite      0.83     1.20     1.32
    frame          6.84     9.45    15.15
    total         10.24    13.34    18.15  bar p95 <= 16.7: PASS
P-A dab + composite + frame per dab, subd1, 2048^2, ms      p50      p95      max
  radius  1.0 % (~398 texels with the mirror)
    dab            2.01     2.74     2.89
    composite      0.50     0.86     0.91
    frame         12.04    14.92    17.31
    total         14.49    17.20    20.38
  radius  3.0 % (~3,840 texels with the mirror)
    dab            3.16     3.66     4.09
    composite      0.86     1.28     1.69
    frame         11.29    14.79    19.00
    total         15.43    18.63    22.61  bar p95 <= 16.7: FAIL
P-H alpha placement (Poren, mirror) + composite + frame, cage, 2048^2, ms   p50      p95      max
  radius  3.0 % (~966 texels with the mirror, 0 % wrapped)
    dab            2.86     3.84     5.27
    composite      0.76     1.42     2.56
    frame          6.54     7.88    14.00
    total         10.25    13.28    17.64  bar p95 <= 16.7: PASS
  radius  5.0 % (~2,406 texels with the mirror, 15 % wrapped)
    dab            4.55     7.76     9.16
    composite      1.31     2.21     2.62
    frame          6.53     7.88    17.97
    total         12.76    18.30    24.76  bar p95 <= 33.0: PASS

P-H alpha placement (Poren, mirror) + composite + frame, subd1, 2048^2, ms   p50      p95      max
  radius  3.0 % (~946 texels with the mirror, 0 % wrapped)
    dab            3.04     4.52     6.50
    composite      0.80     1.30     1.33
    frame         11.26    15.48    22.38
    total         15.06    21.39    26.43  bar p95 <= 16.7: FAIL
  radius  5.0 % (~2,518 texels with the mirror, 10 % wrapped)
    dab            5.32     9.30    12.77
    composite      1.47     2.42     2.91
    frame         12.86    17.13    21.04
    total         20.18    24.85    27.81  bar p95 <= 33.0: PASS

P-I 2-s fast stroke, round, 3 %, cage: 114 placements (12.5 % spacing), 120 frames + 1 finishing
  stroke frame ms     10.35    14.79    16.57  bar p95 <= 33: PASS
  release -> History    7.9 ms  bar <= 250: PASS;  finishing frame max 5.3 ms  bar <= 50: PASS

P-I flick (10 frames), round, 3 %, cage: 112 placements (12.5 % spacing), 10 frames + 5 finishing
  stroke frame ms     17.95    31.79    31.79  (info, no bar)
  release -> History  193.6 ms  (info, no bar);  finishing frame max 40.4 ms  bar <= 50: PASS

P-I 2-s fast stroke, Poren, 3 %, cage: 15 placements (100.0 % spacing), 120 frames + 1 finishing
  stroke frame ms      7.06    10.89    12.22  bar p95 <= 33: PASS
  release -> History    7.6 ms  bar <= 250: PASS;  finishing frame max 5.0 ms  bar <= 50: PASS

P-I flick (10 frames), Poren, 3 %, cage: 14 placements (100.0 % spacing), 10 frames + 1 finishing
  stroke frame ms     13.56    16.40    16.40  (info, no bar)
  release -> History   10.8 ms  (info, no bar);  finishing frame max 8.3 ms  bar <= 50: PASS

P-I 2-s fast stroke, round, 3 %, subd1: 110 placements (12.5 % spacing), 120 frames + 1 finishing
  stroke frame ms     15.77    22.56    35.64  bar p95 <= 33: PASS
  release -> History   19.5 ms  bar <= 250: PASS;  finishing frame max 16.7 ms  bar <= 50: PASS

P-I flick (10 frames), round, 3 %, subd1: 109 placements (12.5 % spacing), 10 frames + 6 finishing
  stroke frame ms     23.03    35.45    35.45  (info, no bar)
  release -> History  241.4 ms  (info, no bar);  finishing frame max 47.1 ms  bar <= 50: PASS

P-I 2-s fast stroke, Poren, 3 %, subd1: 14 placements (100.0 % spacing), 120 frames + 1 finishing
  stroke frame ms     11.75    16.34    23.38  bar p95 <= 33: PASS
  release -> History   14.7 ms  bar <= 250: PASS;  finishing frame max 12.1 ms  bar <= 50: PASS

P-I flick (10 frames), Poren, 3 %, subd1: 14 placements (100.0 % spacing), 10 frames + 1 finishing
  stroke frame ms     19.24    28.30    28.30  (info, no bar)
  release -> History   13.8 ms  (info, no bar);  finishing frame max 11.3 ms  bar <= 50: PASS

P-J spray placement (20 stamps, 20 %, jitter, mirror) + composite + frame, cage, 2048^2, 3 %, ms   p50      p95      max
  Poren spray (40 stamps per placement with the mirror)
    dab            4.16     4.80     5.39
    composite      0.69     1.16     1.17
    frame          5.85     8.04    13.32
    total         10.95    12.83    18.83  bar p95 <= 33: PASS
  round spray (40 stamps per placement with the mirror)
    dab            3.68     5.40     5.82
    composite      0.73     1.40     1.65
    frame          6.25     7.93    14.15
    total         10.54    13.98    18.70  (info, no bar)

P-K 10-s spray stroke, Poren spray, 3 %, cage: 280 placements (50 % spacing, 20 stamps each), 600 frames + 1 finishing
  stroke frame ms      8.87    14.39    22.15
  release -> History    9.6 ms;  frames > 50 ms: 0, max 22.1 ms  bar no frame > 50: PASS

P-J spray placement (20 stamps, 20 %, jitter, mirror) + composite + frame, subd1, 2048^2, 3 %, ms   p50      p95      max
  Poren spray (40 stamps per placement with the mirror)
    dab            4.56     6.81    10.58
    composite      0.75     1.45     1.66
    frame         11.88    17.70    25.20
    total         17.36    24.05    30.89  bar p95 <= 33: PASS
  round spray (40 stamps per placement with the mirror)
    dab            4.11     4.65     4.76
    composite      0.78     1.20     1.55
    frame         10.99    15.11    19.71
    total         16.24    20.38    24.55  (info, no bar)

P-K 10-s spray stroke, Poren spray, 3 %, subd1: 273 placements (50 % spacing, 20 stamps each), 600 frames + 1 finishing
  stroke frame ms     14.42    20.47    35.27
  release -> History   11.6 ms;  frames > 50 ms: 0, max 35.3 ms  bar no frame > 50: PASS

```
