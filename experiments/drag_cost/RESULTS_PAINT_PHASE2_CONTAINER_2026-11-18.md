# Paint Room Phase 2 — probe results, container (2026-11-18)

**Probe:** `experiments/drag_cost/probe_paint.py` (AD-037 §7, §10.7) with the Phase 2 dab (hit, footprint, mirror, stroke
buffer) on the cage, SubD level 1 and SubD level 2 of the Gollum head. **Machine:** the cloud container (Xeon 2.1 GHz,
4 cores), Python 3.13.18, NumPy 2.2.6 (the pinned version), GL = llvmpipe (software). Output verbatim below.

**Reading** (AD-037 §10.7): P-D passes on every surface in the container (0.63 / 0.63 / 1.11 s; ×3–3.4 on the reference
PC ≈ 1.9–2.2 s for the cage and SubD 1 — the reference PC decides). The CPU rows of P-A (dab + composite) are 3–4 ms at
3 % and 6–7 ms at 5 % (p50) on every surface, with the mirror. The **frame** rows are llvmpipe rasterizing the surface in
software (6 ms cage, 9–11 ms SubD 1, 22–24 ms SubD 2): they make the SubD 2 rows FAIL here and are not comparable to the
9800 GTX (§7.1: 3–5 ms per frame). SubD 2 is not what the app shows on the head (the preview caps at 25,000 faces → level
1). P-B, P-C, P-E, P-F as in Phase 1 (P-F 0.50 s).

```
Paint probe (AD-037 Phase 1e / 2) - commit be0397f1a8, working tree clean
python 3.13.18, numpy 2.2.6, size 2048^2, 40 dabs per stroke
fixture: Gollum, 2234 faces, texture Gollum_cbf9c7702d.png, mirrored dab on

P-D room enter: paint surface build (texel map + tables), ms        bar <= 2000 ms
  cage    2,234 faces     636 ms  (2,787,212 texels, 48 MiB)  PASS
  subd1   9,002 faces     632 ms  (2,787,155 texels, 48 MiB)  PASS
  subd2  36,008 faces    1112 ms  (2,787,155 texels, 48 MiB)  PASS
GL: llvmpipe (LLVM 20.1.2, 256 bits) / (4, 5)

P-A dab + composite + frame per dab, cage, 2048^2, ms      p50      p95      max
  radius  1.0 % (~409 texels with the mirror)
    dab            2.15     3.11     3.96
    composite      0.43     0.86     1.14
    frame          6.18     7.77    11.24
    total          8.79    10.65    14.22
  radius  3.0 % (~3,854 texels with the mirror)
    dab            2.77     3.48     3.79
    composite      0.86     1.41     1.47
    frame          6.22     7.84    13.06
    total          9.78    12.30    17.49  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,146 texels with the mirror)
    dab            4.81     6.15     6.65
    composite      1.53     2.67     2.71
    frame          6.65    11.66    15.09
    total         13.39    18.90    22.03  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,863 texels with the mirror)
    dab           11.42    14.67    15.53
    composite      2.64     4.30     5.03
    frame          6.42     8.29    11.69
    total         20.51    26.69    27.72

P-A dab + composite + frame per dab, subd1, 2048^2, ms      p50      p95      max
  radius  1.0 % (~398 texels with the mirror)
    dab            1.70     2.44     3.21
    composite      0.32     0.81     0.90
    frame          9.48    13.64    18.04
    total         11.83    16.42    20.52
  radius  3.0 % (~3,840 texels with the mirror)
    dab            2.56     3.19     3.41
    composite      0.70     1.05     1.23
    frame          8.65    10.19    21.50
    total         12.00    13.59    24.39  bar p95 <= 16.7: PASS
  radius  5.0 % (~11,030 texels with the mirror)
    dab            4.26     6.60     8.64
    composite      1.47     2.13     2.20
    frame         10.14    13.25    13.71
    total         16.13    20.13    21.77  bar p95 <= 33.0: PASS
  radius 10.0 % (~40,889 texels with the mirror)
    dab           11.96    17.70    17.95
    composite      2.93     4.78     5.09
    frame         10.90    12.84    18.15
    total         25.72    33.16    33.49

P-A dab + composite + frame per dab, subd2, 2048^2, ms      p50      p95      max
  radius  1.0 % (~384 texels with the mirror)
    dab            2.40     3.27     4.07
    composite      0.42     0.71     0.88
    frame         21.86    27.14    28.55
    total         24.64    31.24    32.29
  radius  3.0 % (~3,851 texels with the mirror)
    dab            3.26     4.41     4.55
    composite      0.89     1.27     1.40
    frame         23.74    29.98    36.62
    total         28.06    34.58    40.56  bar p95 <= 16.7: FAIL
  radius  5.0 % (~10,986 texels with the mirror)
    dab            5.12     6.98    15.59
    composite      1.50     1.83     4.64
    frame         22.94    28.55    29.80
    total         30.26    36.60    44.24  bar p95 <= 33.0: FAIL
  radius 10.0 % (~40,871 texels with the mirror)
    dab           12.57    17.00    21.86
    composite      2.78     4.63     7.25
    frame         22.46    28.71    30.05
    total         37.63    50.12    52.94

P-B mip policy, 3 % stroke (cage), frame ms      p50      p95      max
  frame         12.11    14.39    14.93   stroke-end frame 4.82
  deferred       5.66     6.98     7.05   stroke-end frame 11.66
  none           5.52     6.75     7.01   stroke-end frame 5.55

P-C orbit frame, ms                              p50      p95      max
  file texture      5.03     6.73     7.06
  live texture      4.99     6.56     9.07
  live - file p50 -0.05 ms  bar <= +1 ms: PASS

P-E Modeller frame (file texture) before / after a live texture existed
  same image: PASS;  p50 before 3.94 ms, after 4.17 ms

P-F save of a 4-layer stack
  first save 496 ms (4 layers + 1 flat, 0.7 MiB)  bar <= 2000 ms: PASS
    PNG encode (all files)            233 ms in 5 calls (max 55)
      of it: layers                   178 ms in 4 calls (max 45)
    write file                          2 ms in 5 calls (max 0)
    read base                          43 ms in 1 call (max 43)
    flatten (base + composite)        234 ms in 1 call (max 234)
  second save 0 ms (0 layers, 0 flat)  nothing written: PASS
```
