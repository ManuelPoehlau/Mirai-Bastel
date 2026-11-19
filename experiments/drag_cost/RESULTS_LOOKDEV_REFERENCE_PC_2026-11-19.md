# LookDev LD-0 probe — reference PC run (AD-038, 2026-11-19)

Machine: the reference PC (Core 2 Quad Q9550, GeForce 9800 GTX+, GL 3.3.0, Windows 10 19045, Python 3.12.10 in
`.venv312`) — **MEASURED [M-RPC]**. Run by Manu on 2026-11-19 with `experiments/drag_cost/probe_lookdev.py` (defaults:
1024×768 with every extra, then 1920×1080 with the frame rows; 30 rounds after 5).

Command: `python experiments\drag_cost\probe_lookdev.py | Tee-Object -FilePath lookdev_ld0.txt` (PowerShell, repo root).
Source line of both runs: commit `db9fbeafa5`, "working tree MODIFIED", `src/` tree `716ec01d5d`. That tree id equals
`git rev-parse db9fbea:src`: the measured `src/` is the committed one, the modification lay outside `src/`. Whether the
NVIDIA "prefer maximum performance" setting was on is not stated. The tight min / max of most rows suggest a steady
clock.

Scene: `scenes/Gollum_Head_05.mirai.json` as saved — the painted head (2,492 faces; 5,469 triangles on the cage, 22,153
at SubD 1) and two eyes (look, iris and sclera map on); teeth and the older head hidden. `framed` = the head at ¾,
22.8 % of the frame at 1024×768 (17 % at 1920×1080); `close` = the face, front, 80 % (60 %).

## (a) Frame rows, GPU p50 ms (GL_TIME_ELAPSED)

| Surface / view / size | worklight | wl eyes full | ld skin | ld frame | ld no env | ld no map | ld shadow | app render |
|---|---|---|---|---|---|---|---|---|
| cage / framed / 1024×768 | 3.00 | 3.28 | 1.01 | **1.68** | 1.19 | 1.78 | 10.76 | 3.00 |
| cage / close / 1024×768 | 6.59 | 7.37 | 2.93 | **4.59** | 3.15 | 4.48 | 14.28 | 6.60 |
| subd1 / framed / 1024×768 | 5.18 | 5.46 | 1.55 | **2.21** | 1.50 | 2.28 | 11.10 | 5.21 |
| subd1 / close / 1024×768 | 9.72 | 10.53 | 3.58 | **5.26** | 3.55 | 5.09 | 16.72 | 9.76 |
| cage / framed / 1920×1080 | 4.38 | 5.08 | 1.69 | **3.00** | 2.19 | 2.97 | — | 4.39 |
| cage / close / 1920×1080 | 10.95 | 12.17 | 5.33 | **7.96** | 5.35 | 7.80 | — | 10.96 |
| subd1 / framed / 1920×1080 | 7.38 | 8.16 | 2.30 | **3.65** | 2.53 | 3.53 | — | 7.42 |
| subd1 / close / 1920×1080 | 14.80 | 16.04 | 6.18 | **8.85** | 5.85 | 8.60 | — | 14.86 |

GPU min / max stay within about ±0.5 ms of the p50 except in `ld shadow` (7.6–35.7 ms) and a few single maxima.

Derived (COMPUTED from the table, GPU p50 differences, ms):

| Difference | 1024×768: cage framed / close, SubD framed / close | 1920×1080: same order |
|---|---|---|
| studio specular on skin (`ld frame` − `ld no env`) | 0.49 / 1.44 / 0.71 / 1.71 | 0.81 / 2.61 / 1.12 / 3.00 |
| albedo map (`ld frame` − `ld no map`) | −0.10 / +0.11 / −0.07 / +0.17 | +0.03 / +0.16 / +0.12 / +0.25 |
| eyes in "full" + background (`ld frame` − `ld skin`) | 0.67 / 1.66 / 0.66 / 1.68 | 1.31 / 2.63 / 1.35 / 2.67 |
| shadow stand-in (`ld shadow` − `ld frame`) | 9.08 / 9.69 / 8.89 / 11.46 | — |
| LookDev vs Worklight at the same eye tier (`ld frame` − `wl eyes full`) | −1.60 / −2.78 / −3.25 / −5.27 | −2.08 / −4.21 / −4.51 / −7.19 |

CPU p50 (draw + `glFinish`): `ld skin` 2.4–4.9 ms, `ld frame` 7.7–11.9 ms at 1024×768. The step between them is
mostly the eye pass's Python side, as in the Worklight (`wl eyes full` 10.8–18.0 ms).

## (b) UV request, ms wall

| Surface | triangles | request on: first / p50 | first draw after: first / p50 | request off | `_triangle_uvs_flat` p50 |
|---|---|---|---|---|---|
| cage | 5,469 | 15.61 / 15.08 | 3.66 / 1.19 | 0.05 | 12.72 |
| subd1 | 22,153 | 62.90 / 60.94 | 6.72 / 2.36 | 0.06 | 54.91 |

## (c) RGBA16F cube (P3)

- FBO complete for every face and level (42 attachments), `glGetError` 0.
- Chain (6 faces × 7 levels, 128² → 2²): **12.1 ms** GPU with 64 samples, **47.1 ms** with 256. The CPU prefilter of
  the same size took 40 s (REFERENCE_HARDWARE §2).
- Level 0 vs `eye_optics.td_env`: worst relative error 6e-4. `textureLod` read-back: 2e-4.

## (d) Depth texture (P3)

- Depth FBO (2048², DEPTH_COMPONENT24, compare mode) complete; 1,386,320 texels written per pass.
- The PCF lookup darkens 5,189 / 58,170 px (cage framed / close) and 4,077 / 42,541 px (SubD 1), as in the container.

## (compile) first use, wall ms

| Eye variant (V2 L3 studio fit) | cold | as shipped | again |
|---|---|---|---|
| plain | 242.4 | 232.9 | 4.1 |
| look | 600.3 | 783.6 | 203.4 |
| look+iris | 605.4 | 511.1 | 9.6 |
| look+iris+sclera | 567.7 | 556.4 | 10.2 |

- `EyePass.program()` on a fresh pass: 21.0 ms. The same source had been compiled earlier in the process.
- Skin stand-in variants, cold: 36–72 ms each.
- SH9 projection on the CPU: 10.4–13.0 ms.

## Reading (COMPUTED; decisions taken in AD-038 §16.1)

- **LD-D10 is met with a wide margin.** `ld frame` for the framed head at 1024×768 is 1.68 ms (cage) / 2.21 ms (SubD 1),
  5–7 % of the 33.3 ms frame. The worst measured case, the SubD close-up at 1920×1080, is 8.85 ms. M1 ships the full
  skin with the studio specular; no lever is needed.
- **The LookDev stand-in is cheaper than the Worklight** in every view, by 1.6–7.2 ms at the same eye tier. The likely
  cause [H] is the Worklight's face-data path (buffer-texture fetches and the bilinear quad normal per fragment). The
  same gap was measured in P0 (16.1 vs 2.9 ms with / without face data, lookdev_gpu_probe 2026-11-13). Entering
  LookDev therefore does not slow the frame. The Worklight rows are the E16 baseline for "the Modelling Room loses
  nothing".
- **The albedo map is free** (≤ 0.25 ms). **The studio specular** costs 0.5–1.7 ms at 1024×768 and up to 3.0 ms at
  1920×1080: it is the first lever if LD-3 ever needs one.
- **UV request:** a one-time 15 ms (cage) / 61 ms (SubD 1) on room entry, almost all in `_triangle_uvs_flat()` (the
  Python loop the Worklight already runs whenever a texture appears). It is set once on entry with no status line;
  vectorising the loop is a later optimisation, not M1.
- **Cold compile is visible:** 0.24–0.6 s per eye variant on the NVIDIA compiler, and the driver cache does not help
  across processes ("as shipped" is as slow as "cold"). The room's first entry compiles one eye LOOKDEV variant (both
  eyes share it) and one or two skin variants, about 0.7 s [E]. AD-038 §15 Q4 (Manu): compile on entry with a status
  line.
- **P3:** the GPU prefilter of a cube works on this card and is about 3,000× faster than the CPU chain, so the cube
  environment can be rebuilt on demand. Depth textures and PCF work. The shadow stand-in (an unoptimised 2048² depth
  pass every frame + 16 taps) adds 9–11.5 ms and varies a lot. A P3 shadow map should be re-rendered only when the pose,
  the geometry or the key change, at a smaller size first.
- **SH9 projection:** 10–13 ms. It is recomputed only on a studio content change (a preset); intensity and rotation are
  uniforms.

## Output

```
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> python experiments\drag_cost\probe_lookdev.py | Tee-Object -FilePath lookdev_ld0.txt
LookDev LD-0 probe (AD-038 draft, 2026-11-19), 1024x768
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit db9fbeafa5, working tree MODIFIED, src/ tree 716ec01d5d
Scene: scenes/Gollum_Head_05.mirai.json, edit object 'Gollum_backup_noscale1 ZBrush'
  eye    'Auge_Links': 3392 faces, look yes, iris yes, sclera map yes, level L3
  eye    'Auge_Rechts': 3392 faces, look yes, iris yes, sclera map yes, level L3
  edit   'Gollum_backup_noscale1 ZBrush': 2492 faces, UVs yes, albedo paint composite
  hidden in the file (not drawn): 'Gollum', 'tooth', 'tooth01', 'Zahn_1', 'Zahn_2'
SH9 projection of the studio on the CPU (4096 directions, NumPy): 13.0 ms

(compile) first use, compile + link wall ms (cold = a comment no driver cache has seen; warm = the same source again; the LOOKDEV variant will be one more cold compile of this size)
  eye V2 L3 studio fit plain             cold    242.4   as shipped    232.9   again      4.1   fragment 17567 chars
  eye V2 L3 studio fit look              cold    600.3   as shipped    783.6   again    203.4   fragment 24591 chars
  eye V2 L3 studio fit look+iris         cold    605.4   as shipped    511.1   again      9.6   fragment 28394 chars
  eye V2 L3 studio fit look+iris+sclera  cold    567.7   as shipped    556.4   again     10.2   fragment 30338 chars
  EyePass.program() on a fresh pass, the scene eye's full-tier variant: 21.0 ms (pyglet ShaderProgram incl. introspection)

(a) frame rows, 1024x768, 30 rounds after 5; GL_TIME_ELAPSED ms; 'vs wl' = minus `worklight`; CPU = wall ms of the draw + glFinish
  [cage / framed] skin triangles 5469, eye triangles 14976, the meshes cover 22.8 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          3.00     2.94     3.04                8.84
      wl eyes full       3.28     3.22     3.65     +0.28     10.84
      ld skin            1.01     1.00     1.02     -1.99      2.36
      ld frame           1.68     1.65     2.08     -1.32      7.73
      ld no env          1.19     1.15     1.57     -1.81      8.00
      ld no map          1.78     1.60     2.07     -1.22      7.05
      ld shadow         10.76     7.63    13.08     +7.76     24.71
      app render         3.00     2.91     8.28     -0.00      9.21
      (d) the shadow lookup darkens 5189 px (of 786432)
  [cage / close] skin triangles 5469, eye triangles 14976, the meshes cover 80.5 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          6.59     6.53     6.71               12.47
      wl eyes full       7.37     7.30     7.42     +0.78     14.70
      ld skin            2.93     2.92     2.93     -3.66      4.13
      ld frame           4.59     4.57     4.62     -1.99     10.57
      ld no env          3.15     3.13     4.80     -3.43     10.42
      ld no map          4.48     4.46     6.13     -2.10     11.12
      ld shadow         14.28    11.06    35.67     +7.70     28.34
      app render         6.60     6.54     6.65     +0.02     12.91
      (d) the shadow lookup darkens 58170 px (of 786432)
  [subd1 / framed] skin triangles 22153, eye triangles 14976, the meshes cover 22.6 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          5.18     5.09     5.26                9.85
      wl eyes full       5.46     5.37     5.87     +0.28     12.96
      ld skin            1.55     1.54     1.57     -3.63      2.95
      ld frame           2.21     2.19     2.59     -2.96      9.44
      ld no env          1.50     1.48     1.90     -3.68      8.13
      ld no map          2.28     2.07     2.50     -2.90      8.64
      ld shadow         11.10     9.10    13.06     +5.93     25.05
      app render         5.21     5.09     5.32     +0.03     11.59
      (d) the shadow lookup darkens 4077 px (of 786432)
  [subd1 / close] skin triangles 22153, eye triangles 14976, the meshes cover 79.9 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          9.72     9.64     9.80               15.63
      wl eyes full      10.53    10.42    12.31     +0.81     18.01
      ld skin            3.58     3.56     3.60     -6.14      4.94
      ld frame           5.26     5.23     5.29     -4.45     11.92
      ld no env          3.55     3.51     5.20     -6.16     10.61
      ld no map          5.09     5.06     5.13     -4.62     11.73
      ld shadow         16.72    13.40    17.19     +7.00     30.59
      app render         9.76     9.66     9.83     +0.05     16.06
      (d) the shadow lookup darkens 42541 px (of 786432)

  LD-D10 [cage / framed / 1024x768]: `ld frame` 1.68 ms GPU = 5 % of the 33.3 ms frame (30 fps); `worklight` 3.00 ms
  LD-D10 [subd1 / framed / 1024x768]: `ld frame` 2.21 ms GPU = 7 % of the 33.3 ms frame (30 fps); `worklight` 5.18 ms
  (the pass only: the app's overlays, HUD, panels and the CPU side add to the frame; the reference PC decides, LD-D10)
  (d) depth FBO complete, 2048^2 DEPTH_COMPONENT24, compare mode; texels written in the last pass 1386320 of 4194304
  skin stand-in variants, compile + link on first use (cold, ms): colour+env 57.8, map 35.9, map+env 67.4, map+env+shadow 68.2

(b) UV request on the head (Worklight texture hidden, so its UVs are inactive); ms wall
  [cage] 5469 triangles, has UVs True
      request on  (Viewport.sync): first    15.61   p50 of 5 more    15.08
      first draw after (upload):   first     3.66   p50     1.19
      request off (Viewport.sync): first     0.04   p50     0.05
      `_triangle_uvs_flat()` alone p50    12.72
  [subd1] 22153 triangles, has UVs True
      request on  (Viewport.sync): first    62.90   p50 of 5 more    60.94
      first draw after (upload):   first     6.72   p50     2.36
      request off (Viewport.sync): first     0.07   p50     0.06
      `_triangle_uvs_flat()` alone p50    54.91

(c) RGBA16F cube 128^2, mips to 2^2, every face and level through an FBO
  FBO status: complete for every face and level; glGetError 0x0000; program compile + link 67.5 ms
  chain (6 faces x 7 levels; level 0 = 1 sample, others 64 samples):    12.10 ms GPU (median of 5)
  chain (6 faces x 7 levels; level 0 = 1 sample, others 256 samples):    47.12 ms GPU (median of 5)
  level 0 vs eye_optics.td_env at 24 texels: worst relative error 0.0006 (RGBA16F: about 1e-3)
  textureLod at the 6 face centres, lod 0 and 3, vs the read-back centre texels: worst relative error 0.0002 (6x1 RGBA32F target complete)

glGetError at the end: 0x0000

LookDev LD-0 probe (AD-038 draft, 2026-11-19), 1920x1080
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit db9fbeafa5, working tree MODIFIED, src/ tree 716ec01d5d
Scene: scenes/Gollum_Head_05.mirai.json, edit object 'Gollum_backup_noscale1 ZBrush'
  eye    'Auge_Links': 3392 faces, look yes, iris yes, sclera map yes, level L3
  eye    'Auge_Rechts': 3392 faces, look yes, iris yes, sclera map yes, level L3
  edit   'Gollum_backup_noscale1 ZBrush': 2492 faces, UVs yes, albedo paint composite
  hidden in the file (not drawn): 'Gollum', 'tooth', 'tooth01', 'Zahn_1', 'Zahn_2'
SH9 projection of the studio on the CPU (4096 directions, NumPy): 10.4 ms

(a) frame rows, 1920x1080, 30 rounds after 5; GL_TIME_ELAPSED ms; 'vs wl' = minus `worklight`; CPU = wall ms of the draw + glFinish
  [cage / framed] skin triangles 5469, eye triangles 14976, the meshes cover 17.1 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          4.38     4.31     4.42                9.50
      wl eyes full       5.08     4.67     5.22     +0.70     12.09
      ld skin            1.69     1.69     1.69     -2.69      2.76
      ld frame           3.00     2.55     3.10     -1.38      9.02
      ld no env          2.19     1.71     2.29     -2.19      8.10
      ld no map          2.97     2.49     3.04     -1.41      9.13
      app render         4.39     4.33     4.43     +0.01      9.75
  [cage / close] skin triangles 5469, eye triangles 14976, the meshes cover 60.4 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight         10.95    10.87    11.00               16.24
      wl eyes full      12.17    12.11    12.26     +1.22     18.38
      ld skin            5.33     5.33     5.33     -5.62      6.46
      ld frame           7.96     7.92     7.99     -2.99     13.47
      ld no env          5.35     5.31     5.38     -5.60     11.68
      ld no map          7.80     7.76     7.86     -3.16     12.84
      app render        10.96    10.91    11.03     +0.01     16.64
  [subd1 / framed] skin triangles 22153, eye triangles 14976, the meshes cover 16.9 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          7.38     7.27     7.47               13.35
      wl eyes full       8.16     5.17     8.29     +0.78     15.56
      ld skin            2.30     2.28     2.30     -5.09      3.76
      ld frame           3.65     3.16     3.71     -3.74     10.60
      ld no env          2.53     2.06     2.60     -4.85      9.66
      ld no map          3.53     3.03     3.56     -3.86     10.02
      app render         7.42     7.27     7.50     +0.04     13.07
  [subd1 / close] skin triangles 22153, eye triangles 14976, the meshes cover 59.9 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight         14.80    14.70    14.93               20.77
      wl eyes full      16.04    15.92    16.13     +1.24     23.34
      ld skin            6.18     6.05     6.19     -8.62      7.57
      ld frame           8.85     8.70     8.89     -5.95     14.60
      ld no env          5.85     5.81     5.89     -8.95     13.19
      ld no map          8.60     8.56     8.64     -6.20     15.17
      app render        14.86    14.75    14.96     +0.06     21.23
  skin stand-in variants, compile + link on first use (cold, ms): colour+env 59.8, map 35.4, map+env 72.0

glGetError at the end: 0x0000
```
