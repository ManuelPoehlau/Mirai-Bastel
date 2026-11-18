# Paint Room Phase 1e — probe results, reference PC (2026-11-18)

**Probe:** `experiments/drag_cost/probe_paint.py` (AD-037 §7). **Run by:** Manu, 2026-11-18, on the reference PC (Core 2
Quad Q9550, GeForce 9800 GTX, GL 3.3; REFERENCE_HARDWARE §1), Python 3.12.10, NumPy 2.2.6. **Code:** `src/` tree
`5b4e77b95e` = the committed AD-037 Phase 1 (`254486a`). Output verbatim below.

**Reading** (AD-037 §7.1): P-A, P-B, P-C, P-E pass; P-D failed at 2048² (2,061 ms against 2 s) and P-F failed at both
sizes (7.4 / 9.4 s against 2 s, nearly independent of the image size). Both were worked on the same day (P-D −35 % in the
container, P-F −45 % in the container plus a split of its parts in the probe); **a re-run on the reference PC is open**.

## 2048²

```
Paint probe (AD-037 Phase 1e) - commit 2572dd1096, working tree MODIFIED, src/ tree 5b4e77b95e
python 3.12.10, numpy 2.2.6, size 2048^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png

P-D texel map build: 2061 ms (2,787,212 texels mapped, 48 MiB)  bar <= 2000 ms: FAIL
GL: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2 / (3, 3)

P-A dab + composite + frame per dab, 2048^2, ms        p50      p95      max
  radius  1.0 % (~208 texels)
    dab            2.04     3.05     3.43
    composite      0.66     1.33     1.56
    frame          3.06     4.14     4.81
    total          6.09     7.22     7.95
  radius  3.0 % (~1,940 texels)
    dab            5.28     6.68     7.21
    composite      1.32     1.46     1.68
    frame          4.18     4.48     5.05
    total         10.49    11.97    13.13  bar p95 <= 16.7: PASS
  radius  5.0 % (~5,597 texels)
    dab           14.06    14.94    15.31
    composite      2.06     2.29     2.52
    frame          4.48     4.86     5.29
    total         20.12    21.56    22.59  bar p95 <= 33.0: PASS
  radius 10.0 % (~20,505 texels)
    dab           49.85    63.78   374.02
    composite      3.88     4.73     5.37
    frame          4.91     5.67   329.29
    total         58.93    72.53   432.76

P-B mip policy, 3 % stroke, frame ms             p50      p95      max
  frame          4.72     5.31     7.75   stroke-end frame 3.50
  deferred       4.03     4.71     6.28   stroke-end frame 3.56
  none           4.12     5.94    34.66   stroke-end frame 3.18

P-C orbit frame, ms                              p50      p95      max
  file texture      3.38     3.89     5.30
  live texture      3.18     3.79     4.18
  live - file p50 -0.21 ms  bar <= +1 ms: PASS

P-E Modeller frame (file texture) before / after a live texture existed
  same image: PASS;  p50 before 3.63 ms, after 3.80 ms

P-F save of a 4-layer stack
  first save 9370 ms (4 layers + 1 flat, 0.3 MiB)  bar <= 2000 ms: FAIL
  second save 1 ms (0 layers, 0 flat)  nothing written: PASS
```

## 1024²

```
Paint probe (AD-037 Phase 1e) - commit 2572dd1096, working tree MODIFIED, src/ tree 5b4e77b95e
python 3.12.10, numpy 2.2.6, size 1024^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png

P-D texel map build: 1418 ms (696,802 texels mapped, 12 MiB)  bar <= 2000 ms: PASS
GL: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2 / (3, 3)

P-A dab + composite + frame per dab, 1024^2, ms        p50      p95      max
  radius  1.0 % (~52 texels)
    dab            1.13     1.67     1.71
    composite      0.36     0.66     0.67
    frame          3.20     4.19     4.25
    total          4.92     6.20     6.32
  radius  3.0 % (~484 texels)
    dab            2.01     2.53     2.59
    composite      0.65     1.41     1.51
    frame          3.85     4.40     4.88
    total          6.53     7.70     8.77  bar p95 <= 16.7: PASS
  radius  5.0 % (~1,397 texels)
    dab            3.67     4.49     4.69
    composite      0.75     1.46     2.16
    frame          3.59     4.72     4.99
    total          8.49    10.15    10.42  bar p95 <= 33.0: PASS
  radius 10.0 % (~5,130 texels)
    dab           12.05    14.10    15.02
    composite      1.69     2.07     2.12
    frame          4.41     4.73     5.00
    total         17.56    20.06    21.28

P-B mip policy, 3 % stroke, frame ms             p50      p95      max
  frame          4.20     4.49     5.65   stroke-end frame 3.61
  deferred       3.87     4.17     4.44   stroke-end frame 3.05
  none           3.81     4.40     4.77   stroke-end frame 3.61

P-C orbit frame, ms                              p50      p95      max
  file texture      2.99     3.87     4.42
  live texture      3.19     3.66     4.15
  live - file p50 +0.20 ms  bar <= +1 ms: PASS

P-E Modeller frame (file texture) before / after a live texture existed
  same image: PASS;  p50 before 3.73 ms, after 3.73 ms

P-F save of a 4-layer stack
  first save 7388 ms (4 layers + 1 flat, 0.1 MiB)  bar <= 2000 ms: FAIL
  second save 1 ms (0 layers, 0 flat)  nothing written: PASS
```
