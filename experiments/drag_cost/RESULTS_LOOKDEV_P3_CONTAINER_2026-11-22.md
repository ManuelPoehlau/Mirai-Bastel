# LookDev P3-0 probe — container run (function check only), 2026-11-22

`experiments/drag_cost/probe_lookdev.py --p3` ([AD-039](../../docs/architecture/AD-039-LOOKDEV-P3.md) §11.1), llvmpipe
under xvfb. **A function check, not a measurement:** llvmpipe's `GL_TIME_ELAPSED` values are not meaningful (they
jump between rows that differ by one define; the wall times are the CPU rasteriser). The reference PC decides
(AD-039 §11.1).

Command: `xvfb-run -a python experiments/drag_cost/probe_lookdev.py --p3 --size 1024 768 --draws 3`, exit 0.

What the run shows:
- every P3 stand-in variant compiles and draws (`SHADOW_GRID` 2 / 3 / 4, `THICKNESS`, `DUAL_LOBE`, `DUAL_LOBE_ENV`,
  `CUBE_ENV`), `glGetError` 0 at the end;
- the depth FBOs at 512² / 1024² / 2048² are complete; the second sampler object without compare mode reads the raw
  depth of the same texture (`thick` rows);
- the shadow lookup darkens 4,979 / 53,307 px (cage framed / close) and 3,850 / 39,662 px (SubD 1) with **skin-only
  casters** — LD-0's run with the eyes as casters darkened 5,189 / 58,170 and 4,077 / 42,541 px;
- the GPU prefilter with the **corner fix** (a corner texel takes the cube corner's direction) leaves the three texels
  at every cube corner equal at every level (spread 0.000); without it the spread reaches 1.4 at the small levels —
  the GPU form of the lab's CPU corner equalization works;
- `p3 all` (shadow 1k × 9 + thickness + dual lobe direct + cube env) draws a few hundred pixels brighter than `ld
  frame` (thickness, second lobe) and as many darker as the shadow alone.
- The LD-0 mode is unchanged (a separate `--size 1024 768 --draws 1 --surfaces cage --views framed --skip compile,uv`
  run: same rows, `ld shadow` darkens 5,238 px, cube level 0 vs `td_env` 6e-4, `textureLod` exact).

Raw output:

```
LookDev P3-0 probe (AD-039, 2026-11-22), 1024x768
Platform: Linux-6.18.44-fc-v726-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.30GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit c7c5104571, working tree MODIFIED, src/ tree 09aa719a72
Scene: scenes/Gollum_Head_05.mirai.json, edit object 'Gollum_backup_noscale1 ZBrush'
  eye    'Auge_Links': 3392 faces, look yes, iris yes, sclera map yes, level L3
  eye    'Auge_Rechts': 3392 faces, look yes, iris yes, sclera map yes, level L3
  edit   'Gollum_backup_noscale1 ZBrush': 2492 faces, UVs yes, albedo paint composite
  hidden in the file (not drawn): 'Gollum', 'tooth', 'tooth01', 'Zahn_1', 'Zahn_2'
SH9 projection of the studio on the CPU (4096 directions, NumPy): 2.2 ms

(p3) depth pass alone (re-rendered only on a pose / geometry / key change; a drag pays it per frame), GL_TIME_ELAPSED ms, 3 rounds after 5
      surface     map casters        GPU p50      min      max
      cage        512 skin              0.97     0.97     1.00
      cage        512 skin + eyes       2.16     1.97     2.23
      cage       1024 skin              1.78     1.58     1.78
      cage       1024 skin + eyes       3.23     3.21     3.65
      cage       2048 skin              5.02     4.77     5.22
      cage       2048 skin + eyes       5.96     5.94     6.39
      subd1       512 skin              2.51     2.36     2.73
      subd1       512 skin + eyes       3.65     3.28     3.70
      subd1      1024 skin              3.82     3.80     3.89
      subd1      1024 skin + eyes       4.86     4.79     5.68
      subd1      2048 skin              7.15     5.26     8.43
      subd1      2048 skin + eyes       9.24     8.53    10.02

(p3) environment cube 128^2 RGBA16F, mips to 2^2, the analytic studio prefiltered on the GPU (64 samples): 45.42 ms with the corner fix, 247.84 ms without
      corner spread per level (largest relative difference of the 3 texels at a cube corner), without / with the fix: L0 0.002/0.000, L1 0.083/0.000, L2 0.683/0.000, L3 0.483/0.000, L4 0.959/0.000, L5 1.412/0.000, L6 1.355/0.000

(p3) frame rows, 1024x768, 3 rounds after 5; GL_TIME_ELAPSED ms; 'vs ld' = minus `ld frame` (the effect's own cost); shadow rows read a map rendered once (a still pose), `drag` renders it every frame; casters: skin only (the eyes receive, AD-039 S1)
  [cage / framed]
      row             GPU p50      min      max     vs ld   CPU p50
      ld frame           0.03     0.02     6.66               10.65
      shadow 1k x4      10.75    10.48    10.83    +10.72     11.59
      shadow 1k x9      11.01    10.64    11.37    +10.99     12.09
      shadow 1k x16     11.85    11.62    13.51    +11.82     12.73
      shadow 2k x9       0.03     0.03     0.67     +0.01     11.81
      shadow 2k x16      0.03     0.03     0.03     +0.00     12.42
      drag 1k x9        14.05    12.88    15.38    +14.02     15.39
      thick 1k x9       11.81    11.49    12.20    +11.78     12.85
      dual direct        0.03     0.02     0.14     +0.01     10.33
      dual env           0.02     0.02     0.57     -0.00     12.23
      cube env           8.98     8.66     9.20     +8.96      9.90
      cube dual env     10.90    10.00    10.91    +10.87     11.44
      p3 all            10.64    10.47    14.13    +10.61     11.53
      shadow 1k x4: 4979 px darker, 0 px brighter than `ld frame` (of 786432)
      p3 all: 5269 px darker, 251 px brighter than `ld frame` (of 786432)
  [cage / close]
      row             GPU p50      min      max     vs ld   CPU p50
      ld frame           0.69     0.67     0.71               23.60
      shadow 1k x4      26.05    24.28    26.68    +25.36     26.95
      shadow 1k x9      27.56    26.74    28.78    +26.86     28.38
      shadow 1k x16     29.55    29.09    32.69    +28.85     30.41
      shadow 2k x9       0.86     0.85     1.01     +0.17     28.95
      shadow 2k x16      1.08     0.99     1.28     +0.39     32.46
      drag 1k x9        29.60    29.14    31.84    +28.91     31.02
      thick 1k x9       28.41    27.09    30.70    +27.71     29.34
      dual direct        0.86     0.69     0.90     +0.16     25.22
      dual env           0.96     0.95     0.97     +0.27     29.61
      cube env          21.64    21.33    21.84    +20.95     22.48
      cube dual env     25.98    25.95    26.54    +25.29     26.78
      p3 all            27.46    25.28    29.30    +26.77     28.36
      shadow 1k x4: 53307 px darker, 0 px brighter than `ld frame` (of 786432)
      p3 all: 53626 px darker, 528 px brighter than `ld frame` (of 786432)
  [subd1 / framed]
      row             GPU p50      min      max     vs ld   CPU p50
      ld frame           0.02     0.01     0.54               14.05
      shadow 1k x4      14.49    13.83    15.98    +14.47     15.36
      shadow 1k x9      15.18    14.59    15.35    +15.16     16.06
      shadow 1k x16     16.70    16.19    16.76    +16.68     17.58
      shadow 2k x9       0.02     0.02     0.03     +0.01     18.66
      shadow 2k x16      0.03     0.02     0.06     +0.01     19.99
      drag 1k x9        20.05    19.60    20.11    +20.03     21.26
      thick 1k x9       15.65    15.64    15.82    +15.64     16.53
      dual direct        0.44     0.02     4.73     +0.42     15.80
      dual env           0.03     0.02     0.07     +0.01     18.38
      cube env          15.22    14.40    15.25    +15.20     16.07
      cube dual env     14.70    14.52    14.78    +14.68     15.45
      p3 all            14.98    14.29    15.10    +14.96     15.79
      shadow 1k x4: 3850 px darker, 0 px brighter than `ld frame` (of 786432)
      p3 all: 4046 px darker, 254 px brighter than `ld frame` (of 786432)
  [subd1 / close]
      row             GPU p50      min      max     vs ld   CPU p50
      ld frame           0.94     0.93     1.02               31.75
      shadow 1k x4      31.49    31.38    31.83    +30.55     32.37
      shadow 1k x9      33.48    33.35    34.59    +32.54     34.39
      shadow 1k x16     39.11    37.34    44.30    +38.16     39.99
      shadow 2k x9       1.15     1.04     4.55     +0.21     40.31
      shadow 2k x16      1.62     1.30     1.94     +0.67     43.30
      drag 1k x9        42.09    40.63    42.31    +41.14     43.46
      thick 1k x9       37.25    36.60    38.14    +36.31     38.40
      dual direct        1.11     0.97     1.34     +0.17     35.40
      dual env           1.55     1.17     1.74     +0.61     39.87
      cube env          28.86    28.08    30.67    +27.92     29.89
      cube dual env     32.51    31.69    33.10    +31.56     33.37
      p3 all            35.79    35.18    36.45    +34.84     36.89
      shadow 1k x4: 39662 px darker, 0 px brighter than `ld frame` (of 786432)
      p3 all: 39132 px darker, 812 px brighter than `ld frame` (of 786432)
  depth FBOs: 1024^2 complete, 2048^2 complete; the raw-depth sampler object for `thick`

  LD-D10 [cage / framed / 1024x768]: `p3 all` 10.64 ms GPU = 32 % of the 33.3 ms frame; `ld frame` 0.03 ms
  LD-D10 [subd1 / framed / 1024x768]: `p3 all` 14.98 ms GPU = 45 % of the 33.3 ms frame; `ld frame` 0.02 ms
  (stand-ins: the production effects follow AD-039; the reference PC decides each slice's fixed setting)

glGetError at the end: 0x0000
```
