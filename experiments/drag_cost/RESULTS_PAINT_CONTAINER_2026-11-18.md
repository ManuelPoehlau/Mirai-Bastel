# Paint Room Phase 1e — probe results, container (2026-11-18)

**Probe:** `experiments/drag_cost/probe_paint.py` (AD-037 §7, audit 2026-11-18 §8.5). **Machine:** cloud container, Intel
Xeon 2.1 GHz, 4 cores, Python 3.13.18, NumPy 2.2.6 (the pinned version), **llvmpipe** (software GL, LLVM 20.1.2) under
Xvfb — the GL rows are *not* a GPU measurement and say nothing about the 9800 GTX; the CPU rows follow the ×3 rule of
REFERENCE_HARDWARE §4 for an estimate. **Code:** the probe ran on the uncommitted Phase 1 tree (`src/` tree `529b6a14a9`); the commit differs from it only by
a type annotation of `Application._uv_check` (committed `src/` tree `5b4e77b95e`).

Reading [C]: every bar passes in the container. On the reference PC the ×3 estimate puts the 3 % dab + composite at about
12 ms p95 before the frame, and the 10 % dab at ~65 ms (too slow: cap the dab rate there, audit §8.1). Mipmaps per frame
cost ~+6 ms per frame here; "deferred" (the `LiveTexture` default) pays once at the stroke's end. **The reference-PC run
decides P-A / P-B / P-C** — the commands:

```
python experiments/drag_cost/probe_paint.py
python experiments/drag_cost/probe_paint.py --size 1024
```

## 2048² (the ZBrush texture's size)

```
Paint probe (AD-037 Phase 1e) - commit 25154ac2bb, working tree MODIFIED, src/ tree 529b6a14a9
python 3.13.18, numpy 2.2.6, size 2048^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png

P-D texel map build: 609 ms (2,787,212 texels mapped, 48 MiB)  bar <= 2000 ms: PASS
GL: llvmpipe (LLVM 20.1.2, 256 bits) / (4, 5)

P-A dab + composite + frame per dab, 2048^2, ms        p50      p95      max
  radius  1.0 % (~208 texels)
    dab            1.10     1.55     2.04
    composite      0.28     0.57     0.79
    frame          6.12     8.75    31.74
    total          7.57    10.26    33.42
  radius  3.0 % (~1,940 texels)
    dab            2.34     3.29     4.93
    composite      0.51     0.83     0.89
    frame          6.61     8.13    14.76
    total          9.32    11.71    18.02  bar p95 <= 16.7: PASS
  radius  5.0 % (~5,597 texels)
    dab            4.33     5.62    11.40
    composite      0.73     0.99     2.37
    frame          6.16    10.37    18.51
    total         11.40    21.05    24.48  bar p95 <= 33.0: PASS
  radius 10.0 % (~20,505 texels)
    dab           14.18    22.00    22.92
    composite      1.65     2.41     2.63
    frame          6.74     8.42    12.90
    total         22.34    32.49    33.05

P-B mip policy, 3 % stroke, frame ms             p50      p95      max
  frame         12.28    13.64    15.53   stroke-end frame 5.82
  deferred       6.15     7.66     8.27   stroke-end frame 10.67
  none           5.57     7.42     7.67   stroke-end frame 5.94

P-C orbit frame, ms                              p50      p95      max
  file texture      4.94     6.41     7.57
  live texture      5.60     6.91     7.14
  live - file p50 +0.66 ms  bar <= +1 ms: PASS

P-E Modeller frame (file texture) before / after a live texture existed
  same image: PASS;  p50 before 5.32 ms, after 5.37 ms

P-F save of a 4-layer stack
  first save 1091 ms (4 layers + 1 flat, 0.3 MiB)  bar <= 2000 ms: PASS
  second save 0 ms (0 layers, 0 flat)  nothing written: PASS
```

## 1024²

```
Paint probe (AD-037 Phase 1e) - commit 25154ac2bb, working tree MODIFIED, src/ tree 529b6a14a9
python 3.13.18, numpy 2.2.6, size 1024^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png

P-D texel map build: 426 ms (696,802 texels mapped, 12 MiB)  bar <= 2000 ms: PASS
GL: llvmpipe (LLVM 20.1.2, 256 bits) / (4, 5)

P-A dab + composite + frame per dab, 1024^2, ms        p50      p95      max
  radius  1.0 % (~52 texels)
    dab            0.68     0.88     0.97
    composite      0.18     0.32     0.47
    frame          5.84     7.71     9.54
    total          6.90     8.95    10.60
  radius  3.0 % (~484 texels)
    dab            0.95     1.14     1.45
    composite      0.27     0.57     0.60
    frame          5.71     6.84     7.51
    total          6.97     8.04     9.06  bar p95 <= 16.7: PASS
  radius  5.0 % (~1,397 texels)
    dab            1.59     2.09     2.25
    composite      0.33     0.68     0.80
    frame          6.29     7.55     8.78
    total          8.35     9.93    10.89  bar p95 <= 33.0: PASS
  radius 10.0 % (~5,130 texels)
    dab            4.15     5.18     5.55
    composite      0.66     0.91     1.04
    frame          6.75     7.94    10.38
    total         11.75    14.07    15.31

P-B mip policy, 3 % stroke, frame ms             p50      p95      max
  frame          8.46    11.41    12.53   stroke-end frame 6.17
  deferred       6.92     8.47     9.75   stroke-end frame 9.77
  none           6.50     7.55     8.01   stroke-end frame 4.76

P-C orbit frame, ms                              p50      p95      max
  file texture      5.26     6.91     7.14
  live texture      5.99     7.88    13.13
  live - file p50 +0.73 ms  bar <= +1 ms: PASS

P-E Modeller frame (file texture) before / after a live texture existed
  same image: PASS;  p50 before 5.57 ms, after 6.07 ms

P-F save of a 4-layer stack
  first save 309 ms (4 layers + 1 flat, 0.1 MiB)  bar <= 2000 ms: PASS
  second save 1 ms (0 layers, 0 flat)  nothing written: PASS
```

## After the reference-PC fixes (2026-11-18, later; AD-037 §7.1), 2048²

The probe line's `src/` tree is the uncommitted fix; the commit that follows holds it.

```
Paint probe (AD-037 Phase 1e) - commit 94b01b8786, working tree MODIFIED, src/ tree a2214da3e7
python 3.13.18, numpy 2.2.6, size 2048^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png

P-D texel map build: 399 ms (2,787,212 texels mapped, 48 MiB)  bar <= 2000 ms: PASS
GL: llvmpipe (LLVM 20.1.2, 256 bits) / (4, 5)

P-A dab + composite + frame per dab, 2048^2, ms        p50      p95      max
  radius  1.0 % (~208 texels)
    dab            1.06     1.57     3.49
    composite      0.25     0.45     0.51
    frame          6.14     7.69    12.66
    total          7.74     9.78    13.95
  radius  3.0 % (~1,940 texels)
    dab            2.21     3.10     3.21
    composite      0.51     0.75     1.17
    frame          6.41     9.03    13.71
    total          9.34    12.30    16.80  bar p95 <= 16.7: PASS
  radius  5.0 % (~5,597 texels)
    dab            5.11     6.62     7.06
    composite      0.87     1.21     1.25
    frame          6.92     8.87    13.23
    total         13.22    15.98    18.83  bar p95 <= 33.0: PASS
  radius 10.0 % (~20,505 texels)
    dab           15.89    19.37    24.04
    composite      1.80     2.90     4.44
    frame          7.12    10.21    14.94
    total         24.99    34.40    38.78

P-B mip policy, 3 % stroke, frame ms             p50      p95      max
  frame         12.27    13.94    18.31   stroke-end frame 5.78
  deferred       6.33     7.71     8.60   stroke-end frame 11.57
  none           5.36     7.31     9.15   stroke-end frame 6.24

P-C orbit frame, ms                              p50      p95      max
  file texture      5.23     7.15     8.51
  live texture      4.97     7.01     8.34
  live - file p50 -0.26 ms  bar <= +1 ms: PASS

P-E Modeller frame (file texture) before / after a live texture existed
  same image: PASS;  p50 before 4.96 ms, after 4.74 ms

P-F save of a 4-layer stack
  first save 582 ms (4 layers + 1 flat, 0.7 MiB)  bar <= 2000 ms: PASS
    PNG encode (all files)            285 ms in 5 calls (max 70)
      of it: layers                   215 ms in 4 calls (max 57)
    write file                          2 ms in 5 calls (max 1)
    read base                          49 ms in 1 call (max 49)
    flatten (base + composite)        269 ms in 1 call (max 269)
  second save 0 ms (0 layers, 0 flat)  nothing written: PASS
```
