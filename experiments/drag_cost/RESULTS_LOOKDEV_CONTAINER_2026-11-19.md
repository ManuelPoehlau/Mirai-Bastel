# LookDev LD-0 probe — container run (AD-038 draft, 2026-11-19)

Machine: the cloud container (Xeon @ 2.10 GHz, 4 logical cores; Mesa llvmpipe, GL 4.5 core under `xvfb-run`;
Python 3.13) — **MEASURED [M-C], a function check only.** llvmpipe rasterises on the CPU, so its GL_TIME_ELAPSED values
do not measure the work: several rows report 0.02–0.04 ms for full frames. The `CPU` column (draw + `glFinish`) is the
closer figure there, and it is a software rasteriser's figure. **No budget is judged from this file**; the reference PC
decides ([AD-038 §16](../../docs/architecture/AD-038-LOOKDEV-ROOM-M1.md#16-ld-0-the-probe)).

Command (repo root): `xvfb-run -a -s "-screen 0 1920x1080x24" python experiments/drag_cost/probe_lookdev.py --draws 5`.
Source line: commit `89f61fc6f7`, working tree clean (`src/` unchanged; the probe itself was uncommitted at the time).

## What the run shows (functional, [M-C])

- Every path runs, at both sizes, with `glGetError` 0 at the end.
- The scene as drawn: the painted head (2,492 faces; 5,469 triangles on the cage, 22,153 at SubD 1) and two eyes (look,
  iris and sclera map on); the teeth and the older head are hidden in the file.
- The framed head covers 22.8 % (1024×768) / 17 % (1920×1080) of the frame, the close-up 80 % / 60 %.
- (d) The depth FBO (2048², DEPTH_COMPONENT24, compare mode) is complete. One pass writes 1.39 M of 4.19 M texels.
  The PCF lookup darkens 4–6 k px framed and 43–59 k px in the close-up.
- (c) The RGBA16F cube FBO is complete for all 42 attachments (6 faces × 7 levels). Level 0 matches
  `eye_optics.td_env` within 6e-4 relative, and `textureLod` reads the centre texels back exactly.
- (b) The UV request:
  - activates the UVs on the cage and on the SubD 1 surface (both have UVs);
  - its sync costs about what `_triangle_uvs_flat()` costs;
  - the first draw after the first request is slow on llvmpipe (cause not isolated);
  - taking it back is free.
- (compile) A cold compile of the eye shell is 38–68 ms on Mesa; the same source again takes 6–14 ms (Mesa's cache).
- SH9 projection of the studio on the CPU: 2.4–3.1 ms.

Frames written with `--png` were checked by eye (not committed). The stand-in draws the head with the paint composite
(a flat base colour on this head; the teal / peach areas the Worklight shows are saved region tints, off in LookDev),
the eyes in the full tier, the gradient background and, in `ld shadow`, the key's cast shadow.

## Output

```
LookDev LD-0 probe (AD-038 draft, 2026-11-19), 1024x768
Platform: Linux-6.18.44-fc-v653-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 89f61fc6f7, working tree clean
Scene: scenes/Gollum_Head_05.mirai.json, edit object 'Gollum_backup_noscale1 ZBrush'
  eye    'Auge_Links': 3392 faces, look yes, iris yes, sclera map yes, level L3
  eye    'Auge_Rechts': 3392 faces, look yes, iris yes, sclera map yes, level L3
  edit   'Gollum_backup_noscale1 ZBrush': 2492 faces, UVs yes, albedo paint composite
  hidden in the file (not drawn): 'Gollum', 'tooth', 'tooth01', 'Zahn_1', 'Zahn_2'
SH9 projection of the studio on the CPU (4096 directions, NumPy): 3.1 ms

(compile) first use, compile + link wall ms (cold = a comment no driver cache has seen; warm = the same source again; the LOOKDEV variant will be one more cold compile of this size)
  eye V2 L3 studio fit plain             cold     37.5   as shipped      6.4   again      6.6   fragment 17570 chars
  eye V2 L3 studio fit look              cold     60.8   as shipped      9.0   again     10.5   fragment 24594 chars
  eye V2 L3 studio fit look+iris         cold     60.1   as shipped     10.2   again     10.0   fragment 28397 chars
  eye V2 L3 studio fit look+iris+sclera  cold     68.3   as shipped     13.8   again     10.6   fragment 30341 chars
  EyePass.program() on a fresh pass, the scene eye's full-tier variant: 11.4 ms (pyglet ShaderProgram incl. introspection)

(a) frame rows, 1024x768, 5 rounds after 5; GL_TIME_ELAPSED ms; 'vs wl' = minus `worklight`; CPU = wall ms of the draw + glFinish
  [cage / framed] skin triangles 5469, eye triangles 14976, the meshes cover 22.8 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          1.18     0.36     4.90                9.63
      wl eyes full       1.63     0.29     3.75     +0.46     11.34
      ld skin            0.49     0.39     1.44     -0.69      7.54
      ld frame           0.62     0.02     4.51     -0.56     11.73
      ld no env          0.03     0.02     0.38     -1.15      8.85
      ld no map          0.03     0.02     4.12     -1.15     11.96
      ld shadow         25.71    21.68    30.63    +24.53     27.53
      app render         0.38     0.31     5.88     -0.80      9.51
      (d) the shadow lookup darkens 5238 px (of 786432)
  [cage / close] skin triangles 5469, eye triangles 14976, the meshes cover 80.5 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          0.69     0.64     0.88               20.74
      wl eyes full       0.70     0.54     0.80     +0.02     23.81
      ld skin            0.93     0.76     1.00     +0.25     18.35
      ld frame           0.86     0.72     0.99     +0.18     29.43
      ld no env          0.40     0.36     0.52     -0.29     20.07
      ld no map          0.87     0.69     1.17     +0.19     25.54
      ld shadow         46.57    42.91    47.58    +45.88     48.12
      app render         0.67     0.61     0.69     -0.02     20.70
      (d) the shadow lookup darkens 59132 px (of 786432)
  [subd1 / framed] skin triangles 22153, eye triangles 14976, the meshes cover 22.6 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          0.45     0.42     0.79               13.99
      wl eyes full       0.47     0.39     1.05     +0.02     15.28
      ld skin            0.60     0.53     0.89     +0.14     13.19
      ld frame           0.03     0.02     0.57     -0.42     17.85
      ld no env          0.03     0.02     0.67     -0.42     14.56
      ld no map          0.10     0.02     0.63     -0.35     15.96
      ld shadow         34.30    33.41    38.06    +33.85     36.04
      app render         0.50     0.44     1.35     +0.05     18.34
      (d) the shadow lookup darkens 4131 px (of 786432)
  [subd1 / close] skin triangles 22153, eye triangles 14976, the meshes cover 79.9 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          0.80     0.76     0.89               29.73
      wl eyes full       0.86     0.76     1.44     +0.05     32.13
      ld skin            1.11     0.89     1.31     +0.31     26.70
      ld frame           1.08     1.01     1.55     +0.28     36.80
      ld no env          0.67     0.58     0.86     -0.14     27.10
      ld no map          0.93     0.62     1.10     +0.13     32.23
      ld shadow         58.39    54.49    60.77    +57.59     61.50
      app render         0.99     0.76     1.33     +0.19     29.86
      (d) the shadow lookup darkens 43380 px (of 786432)

  LD-D10 [cage / framed / 1024x768]: `ld frame` 0.62 ms GPU = 2 % of the 33.3 ms frame (30 fps); `worklight` 1.18 ms
  LD-D10 [subd1 / framed / 1024x768]: `ld frame` 0.03 ms GPU = 0 % of the 33.3 ms frame (30 fps); `worklight` 0.45 ms
  (the pass only: the app's overlays, HUD, panels and the CPU side add to the frame; the reference PC decides, LD-D10)
  (d) depth FBO complete, 2048^2 DEPTH_COMPONENT24, compare mode; texels written in the last pass 1386320 of 4194304
  skin stand-in variants, compile + link on first use (cold, ms): colour+env 13.8, map 11.0, map+env 14.3, map+env+shadow 19.5

(b) UV request on the head (Worklight texture hidden, so its UVs are inactive); ms wall
  [cage] 5469 triangles, has UVs True
      request on  (Viewport.sync): first     6.92   p50 of 5 more     4.40
      first draw after (upload):   first   123.70   p50     2.67
      request off (Viewport.sync): first     0.08   p50     0.05
      `_triangle_uvs_flat()` alone p50     3.34
  [subd1] 22153 triangles, has UVs True
      request on  (Viewport.sync): first    19.98   p50 of 5 more    20.33
      first draw after (upload):   first   104.05   p50     7.39
      request off (Viewport.sync): first     0.08   p50     0.07
      `_triangle_uvs_flat()` alone p50    13.44

(c) RGBA16F cube 128^2, mips to 2^2, every face and level through an FBO
  FBO status: complete for every face and level; glGetError 0x0000; program compile + link 17.0 ms
  chain (6 faces x 7 levels; level 0 = 1 sample, others 64 samples):    56.48 ms GPU (median of 5)
  chain (6 faces x 7 levels; level 0 = 1 sample, others 256 samples):   201.26 ms GPU (median of 5)
  level 0 vs eye_optics.td_env at 24 texels: worst relative error 0.0006 (RGBA16F: about 1e-3)
  textureLod at the 6 face centres, lod 0 and 3, vs the read-back centre texels: worst relative error 0.0000 (6x1 RGBA32F target complete)

glGetError at the end: 0x0000

LookDev LD-0 probe (AD-038 draft, 2026-11-19), 1920x1080
Platform: Linux-6.18.44-fc-v653-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 89f61fc6f7, working tree clean
Scene: scenes/Gollum_Head_05.mirai.json, edit object 'Gollum_backup_noscale1 ZBrush'
  eye    'Auge_Links': 3392 faces, look yes, iris yes, sclera map yes, level L3
  eye    'Auge_Rechts': 3392 faces, look yes, iris yes, sclera map yes, level L3
  edit   'Gollum_backup_noscale1 ZBrush': 2492 faces, UVs yes, albedo paint composite
  hidden in the file (not drawn): 'Gollum', 'tooth', 'tooth01', 'Zahn_1', 'Zahn_2'
SH9 projection of the studio on the CPU (4096 directions, NumPy): 2.4 ms

(a) frame rows, 1920x1080, 5 rounds after 5; GL_TIME_ELAPSED ms; 'vs wl' = minus `worklight`; CPU = wall ms of the draw + glFinish
  [cage / framed] skin triangles 5469, eye triangles 14976, the meshes cover 17.1 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          0.39     0.19     3.76               14.00
      wl eyes full       4.79     3.57     7.51     +4.40     18.94
      ld skin            0.43     0.15     0.53     +0.04     11.73
      ld frame           3.79     3.03     4.21     +3.40     21.92
      ld no env          0.02     0.02     0.03     -0.36     15.03
      ld no map          0.03     0.02     0.03     -0.36     18.28
      app render         0.36     0.04     2.29     -0.03     15.31
  [cage / close] skin triangles 5469, eye triangles 14976, the meshes cover 60.4 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          0.58     0.48     1.14               33.42
      wl eyes full       7.83     7.35     9.23     +7.25     39.75
      ld skin            0.67     0.57     0.80     +0.09     31.43
      ld frame           8.12     6.92    10.07     +7.54     49.80
      ld no env          0.41     0.31     0.48     -0.17     31.83
      ld no map          0.50     0.03     1.04     -0.08     45.65
      app render         0.58     0.42     0.63     +0.01     33.56
  [subd1 / framed] skin triangles 22153, eye triangles 14976, the meshes cover 16.9 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          0.29     0.24     0.48               20.27
      wl eyes full       3.96     3.23     4.55     +3.67     20.53
      ld skin            0.42     0.39     0.72     +0.12     18.76
      ld frame           3.54     3.20     3.87     +3.25     24.00
      ld no env          0.03     0.02     1.79     -0.27     17.83
      ld no map          0.03     0.02     0.03     -0.27     21.30
      app render         0.51     0.16     2.40     +0.22     21.46
  [subd1 / close] skin triangles 22153, eye triangles 14976, the meshes cover 59.9 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          0.75     0.67     1.68               43.68
      wl eyes full       8.51     7.48    10.47     +7.76     47.42
      ld skin            1.06     0.76     1.20     +0.31     39.65
      ld frame           8.83     7.84     9.46     +8.08     62.46
      ld no env          0.50     0.16     0.60     -0.25     40.98
      ld no map          0.67     0.44     0.88     -0.07     53.06
      app render         0.77     0.57     0.80     +0.03     46.70
  skin stand-in variants, compile + link on first use (cold, ms): colour+env 16.1, map 15.6, map+env 13.3

glGetError at the end: 0x0000
```
