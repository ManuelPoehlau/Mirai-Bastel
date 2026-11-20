# LookDev room after LD-1 — reference PC run (AD-038 §17.4, 2026-11-20)

Machine: the reference PC (Core 2 Quad Q9550, GeForce 9800 GTX+, GL 3.3.0, Windows 10 19045, Python 3.12.10 in
`.venv312`) — **MEASURED [M-RPC]**. Run by Manu (results handed over 2026-11-20) with the three commands of AD-038
§17.4, in that order:

```
python experiments\drag_cost\probe_lookdev_room.py | Tee-Object -FilePath lookdev_room_ld1.txt
python experiments\drag_cost\probe_lookdev.py --no-extras | Tee-Object -FilePath lookdev_ld0_after_ld1.txt
python experiments\drag_cost\probe_d3_acceptance.py | Tee-Object -FilePath d3_after_ld1.txt
```

Source line of all three: commit `0e2386fbee`, "working tree MODIFIED", `src/` tree `90a2e01a9e`. That tree id equals
`git rev-parse 0e2386f:src`: the measured `src/` is LD-1 as committed. Whether the NVIDIA "prefer maximum performance"
setting was on is not stated; the tight min / max of the LookDev rows suggest a steady clock, and the D3 weight rows
show the usual power-state note.

## Verdict

| Gate | Result |
|---|---|
| **LD-D10** (≥ 30 fps, framed head, 1024×768) | **met.** The room's own frame (`Viewport.render()`, overlays included) costs 2.42 ms GPU on the cage and 3.28 ms at SubD 1 = **7.3 / 9.8 %** of 33.3 ms; wall incl. `glFinish` 11.6 / 12.6 ms |
| LookDev vs Worklight in the app | the room is **cheaper**: −0.56 ms (cage), −1.92 ms (SubD 1) GPU |
| Nothing stays behind | `modelling after` = `modelling` (+0.00 / +0.02 ms) |
| **E16** (Modelling Room unchanged) | **met.** `probe_lookdev.py` `worklight` / `app render`: every one of the 16 values within 0.04 ms (≤ 0.7 %) of LD-0. `probe_d3_acceptance.py`: within noise of O3 stage 2 (table below) |
| Entry | first in the process ≈ 0.15 s in all (open 96 ms, compile 27 ms behind the status line, first frame 29 ms wall); again 1.1 ms + 12 ms. No lever, no change |
| GL errors | `0x0000` in every run |

No render lever (AD-038 §9) is needed. Nothing to change in `src/` from these numbers.

## 1. The room in the app, `probe_lookdev_room.py` (1024×768, framed ¾, 30 rounds after 5)

GPU p50 ms (GL_TIME_ELAPSED of `Viewport.render()`); CPU = wall of the draw + `glFinish`.

| Surface | modelling | **lookdev** | modelling after | lookdev − modelling | share of 33.3 ms | CPU p50 modelling / lookdev / after |
|---|---:|---:|---:|---:|---:|---|
| cage (5,469 tri) | 2.99 | **2.42** | 2.99 | −0.56 | 7.3 % | 10.90 / 11.60 / 7.48 |
| SubD 1 (22,153 tri) | 5.20 | **3.28** | 5.22 | −1.92 | 9.8 % | 10.71 / 12.57 / 10.11 |

- **Against the LD-0 forecast.** `modelling` equals LD-0's `app render` (2.99 / 5.19 ms) — the same frame. `lookdev` is
  0.74 / 1.06 ms above the stand-in `ld frame` (1.68 / 2.22 ms): the room is drawn through `Viewport.render()` with its
  overlays and the production skin pass (paint composite); LD-0 timed the bare stand-in. LD-0 forecast the room
  1.3 / 2.9 ms cheaper than the Worklight; built, it is 0.6 / 1.9 ms cheaper.
- **CPU column.** The wall time includes the GPU wait, and it scatters by up to 3.4 ms between the two Worklight rows of
  the cage (10.90 vs 7.48). With that noise the room's CPU side is the Worklight's or up to ≈ 2 ms more (SubD 1: 12.57
  vs 10.71 / 10.11) [H: the per-object Python of the LookDraws and the eyes' "full" tier]. At 12.6 ms it leaves the
  30 fps frame two thirds free for tick, HUD and panels; the practical test decides the feel.

### Entry (AD-038 §9)

| | open_lookdev | ticks until the first LookDev frame | compiled behind the status line | first LookDev frame |
|---|---:|---|---|---|
| cage, first in the process | 96.4 ms | 1.4 (UV request), 26.7 (compile) ms | 2 programs, 27 ms | GPU 10.28 ms, wall 28.7 ms |
| SubD 1 | 1.1 ms | 0.2 ms | none needed | GPU 3.34 ms, wall 15.0 ms |
| once more (cached) | 1.1 ms | 0.2 ms | none needed | GPU 3.29 ms, wall 11.9 ms |

- **The first entry costs ≈ 0.15 s in all**, the AD's estimate was ≈ 0.7 s [E] (§16.1). The status line shows for a
  frame; the user sees no stall.
- **Compile 27 ms for 2 programs** (the skin variant with the paint map and the eyes' LOOKDEV variant), where LD-0
  measured 0.24–0.6 s per cold eye variant and found no help from the driver cache across processes. [H] The NVIDIA
  disk cache had these exact sources from an earlier run on this PC (the app or a probe), or the LOOKDEV variant
  compiles faster than the V2 eye variants measured in LD-0. Either way the cold case stays behind the status line.
  The app's status line after opening says „(N Shader in X s vorbereitet)“: the first opening after a reboot or a
  driver update shows the cold value without a probe.
- **open_lookdev 96 ms the first time, 1.1 ms after** (container: 0.4 ms first). [H] A first-in-process cost on
  Windows — the room's modules imported and, with a fresh checkout, their `.pyc` written — not the room's own work.
  Not chased: it happens once per process, inside the 0.15 s.
- **UV request:** 1.4 ms — the painted head already holds its triangle UVs in the Worklight (as in the container);
  the LD-0 (b) costs (15 / 61 ms) apply only to a head whose texture is hidden.

## 2. E16 — `probe_lookdev.py --no-extras` after LD-1 against LD-0 (GPU p50 ms)

| Surface / view / size | `worklight` LD-0 → LD-1 | `app render` LD-0 → LD-1 | `ld frame` LD-0 → LD-1 |
|---|---|---|---|
| cage / framed / 1024×768 | 3.00 → 2.98 | 3.00 → 2.99 | 1.68 → 1.68 |
| cage / close / 1024×768 | 6.59 → 6.57 | 6.60 → 6.57 | 4.59 → 4.58 |
| subd1 / framed / 1024×768 | 5.18 → 5.16 | 5.21 → 5.19 | 2.21 → 2.22 |
| subd1 / close / 1024×768 | 9.72 → 9.69 | 9.76 → 9.74 | 5.26 → 5.25 |
| cage / framed / 1920×1080 | 4.38 → 4.38 | 4.39 → 4.38 | 3.00 → 3.01 |
| cage / close / 1920×1080 | 10.95 → 10.92 | 10.96 → 10.92 | 7.96 → 7.95 |
| subd1 / framed / 1920×1080 | 7.38 → 7.37 | 7.42 → 7.41 | 3.65 → 3.64 |
| subd1 / close / 1920×1080 | 14.80 → 14.78 | 14.86 → 14.82 | 8.85 → 8.82 |

Every Worklight value is the same or up to 0.04 ms lower: **the Modelling Room loses nothing** (§9). The stand-in `ld frame`
reproduces within 0.03 ms (LD-0's numbers hold as the reference). SH9 projection 10.4–10.7 ms (LD-0: 10.4–13.0).

## 3. E16 — `probe_d3_acceptance.py` after LD-1 against O3 stage 2 (2026-11-13), p50 / p95 ms

The last reference-PC D3 run is
[`RESULTS_O3_STAGE2_REFERENCE_PC_2026-11-13.md`](RESULTS_O3_STAGE2_REFERENCE_PC_2026-11-13.md) (`src/` tree
`94addddafd`); paint, eye and LookDev commits lie between the two runs.

| Row | frame O3 stage 2 | frame after LD-1 | tick | `_sync_geometry` | stages (eval) | on_draw |
|---|---:|---:|---:|---:|---:|---:|
| pose wire off | 50.86 / 53.85 | 52.60 / 58.44 | 31.11 → 32.49 | 21.51 → 22.96 (p95 23.21 → 27.35) | 8.72 → 8.82 | 19.62 → 19.79 |
| weight wire off | 85.10 / 92.37 | 86.11 / 96.66 | 36.04 → 36.55 | 21.58 → 21.94 | 13.21 → 13.33 | 48.32 → 48.88 |
| pose wire ON | 51.72 / 54.48 | 52.08 / 55.32 | 31.39 → 31.23 | 22.40 → 21.25 | 8.43 → 8.62 | 20.19 → 20.61 |
| weight wire ON | 85.48 / 94.26 | 86.11 / 93.86 | 35.98 → 36.68 | 21.54 → 21.81 | 13.19 → 13.44 | 49.29 → 48.91 |

- **Within noise.** Three rows move by +0.4 to +1.0 ms p50 (≤ 1.2 %). The fourth, `pose wire off`, is +1.7 ms p50 /
  +4.6 ms p95, all of it in `_sync_geometry` on the CPU — while the heavier `pose wire ON` row, which runs the same
  `_sync_geometry` plus the wire, came out 1.2 ms *faster* there. The draw side (`on_draw`, GPU mesh draw 11.4 ms,
  vertex-buffer upload 5.6–5.9 / 34.2–34.6 ms, HUD, gizmo, panels) is unchanged to ±0.6 ms.
- **Code check:** LD-1 touched `RenderMesh` only in the UV request (`set_uvs_requested`, `_uv_wanted`, and one call in
  `_sync_material`, which runs on a material change, not per frame). With LookDev closed `_uvs_requested` is `False`
  and `_uv_wanted()` is today's expression. The per-frame `_sync_geometry` path has no LD-1 change.
- D3 itself stays **OVER** as before (p95 1.7–1.8× / 2.8–2.9× the 33.3 ms bar); that is the deformation pipeline's open item
  (audit 2026-11-10), not LookDev's.

## Raw output (as supplied)

```
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> python experiments\drag_cost\probe_lookdev_room.py | Tee-Object -FilePath lookdev_room_ld1.txt

LookDev room probe (AD-038 LD-1, 2026-11-19), 1024x768, 30 rounds after 5
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit 0e2386fbee, working tree MODIFIED, src/ tree 90a2e01a9e
Scene: Gollum_Head_05.mirai.json, edit object 'Gollum_backup_noscale1 ZBrush', view framed (3/4)

[cage] the head draws 5469 triangles
  entry (first in this process): open_lookdev 96.4 ms; ticks until the first LookDev frame [1.4, 26.7] ms (the first holds the UV request); programs compiled 2 in 27 ms (behind the status line); first LookDev frame GPU 10.28 ms, wall 28.7 ms
  modelling        GPU p50    2.99 ms (min   2.93, max   3.06)    9.0 % of 33.3 ms   CPU p50   10.90 ms
  lookdev          GPU p50    2.42 ms (min   2.35, max   2.48)    7.3 % of 33.3 ms   CPU p50   11.60 ms   vs modelling  -0.56 ms
  modelling after  GPU p50    2.99 ms (min   2.91, max   3.03)    9.0 % of 33.3 ms   CPU p50    7.48 ms   vs modelling  +0.00 ms

[subd1] the head draws 22153 triangles
  entry: open_lookdev 1.1 ms; ticks until the first LookDev frame [0.2] ms (the first holds the UV request); programs compiled 0 in 0 ms (none needed); first LookDev frame GPU 3.34 ms, wall 15.0 ms
  modelling        GPU p50    5.20 ms (min   5.12, max   5.27)   15.6 % of 33.3 ms   CPU p50   10.71 ms
  lookdev          GPU p50    3.28 ms (min   3.21, max   3.50)    9.8 % of 33.3 ms   CPU p50   12.57 ms   vs modelling  -1.92 ms
  modelling after  GPU p50    5.22 ms (min   5.16, max   5.35)   15.7 % of 33.3 ms   CPU p50   10.11 ms   vs modelling  +0.02 ms

Entering once more (programs cached in this process):
  entry again: open_lookdev 1.1 ms; ticks until the first LookDev frame [0.2] ms (the first holds the UV request); programs compiled 0 in 0 ms (none needed); first LookDev frame GPU 3.29 ms, wall 11.9 ms

glGetError at the end: 0x0000
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> python experiments\drag_cost\probe_lookdev.py --no-extras | Tee-Object -FilePath lookdev_ld0_after_ld1.txt
LookDev LD-0 probe (AD-038 draft, 2026-11-19), 1024x768
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit 0e2386fbee, working tree MODIFIED, src/ tree 90a2e01a9e
Scene: scenes/Gollum_Head_05.mirai.json, edit object 'Gollum_backup_noscale1 ZBrush'
  eye    'Auge_Links': 3392 faces, look yes, iris yes, sclera map yes, level L3
  eye    'Auge_Rechts': 3392 faces, look yes, iris yes, sclera map yes, level L3
  edit   'Gollum_backup_noscale1 ZBrush': 2492 faces, UVs yes, albedo paint composite
  hidden in the file (not drawn): 'Gollum', 'tooth', 'tooth01', 'Zahn_1', 'Zahn_2'
SH9 projection of the studio on the CPU (4096 directions, NumPy): 10.7 ms

(a) frame rows, 1024x768, 30 rounds after 5; GL_TIME_ELAPSED ms; 'vs wl' = minus `worklight`; CPU = wall ms of the draw + glFinish
  [cage / framed] skin triangles 5469, eye triangles 14976, the meshes cover 22.8 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          2.98     2.94     3.05                7.71
      wl eyes full       3.31     3.21     3.66     +0.32      9.28
      ld skin            1.01     1.00     1.02     -1.97      2.10
      ld frame           1.68     1.65     2.07     -1.31      7.86
      ld no env          1.34     1.16     1.61     -1.65      7.44
      ld no map          1.96     1.60     2.02     -1.03      8.08
      app render         2.99     2.93     3.03     +0.00      8.97
  [cage / close] skin triangles 5469, eye triangles 14976, the meshes cover 80.5 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          6.57     6.50     6.64               11.43
      wl eyes full       7.37     7.31     9.10     +0.80     13.45
      ld skin            2.93     2.93     2.93     -3.64      4.04
      ld frame           4.58     4.56     4.61     -1.98     11.11
      ld no env          3.16     3.12     4.87     -3.41      9.44
      ld no map          4.48     4.45     6.12     -2.09      9.93
      app render         6.57     6.52     6.62     -0.00     11.47
  [subd1 / framed] skin triangles 22153, eye triangles 14976, the meshes cover 22.6 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          5.16     4.93     5.27                9.39
      wl eyes full       5.48     5.36     5.88     +0.32     12.25
      ld skin            1.55     1.54     1.57     -3.61      2.92
      ld frame           2.22     2.18     2.62     -2.94      8.94
      ld no env          1.50     1.48     1.89     -3.66      8.74
      ld no map          2.09     2.07     2.51     -3.07      8.36
      app render         5.19     5.11     5.27     +0.03     11.50
  [subd1 / close] skin triangles 22153, eye triangles 14976, the meshes cover 79.9 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          9.69     9.59     9.81               15.42
      wl eyes full      10.49    10.39    12.19     +0.80     17.86
      ld skin            3.58     3.56     3.60     -6.11      4.98
      ld frame           5.25     5.21     6.88     -4.44     12.32
      ld no env          3.55     3.53     5.24     -6.14     10.80
      ld no map          5.09     5.06     5.12     -4.60     10.77
      app render         9.74     9.65     9.82     +0.05     14.12

  LD-D10 [cage / framed / 1024x768]: `ld frame` 1.68 ms GPU = 5 % of the 33.3 ms frame (30 fps); `worklight` 2.98 ms
  LD-D10 [subd1 / framed / 1024x768]: `ld frame` 2.22 ms GPU = 7 % of the 33.3 ms frame (30 fps); `worklight` 5.16 ms
  (the pass only: the app's overlays, HUD, panels and the CPU side add to the frame; the reference PC decides, LD-D10)
  skin stand-in variants, compile + link on first use (cold, ms): colour+env 57.2, map 36.5, map+env 82.7

glGetError at the end: 0x0000

LookDev LD-0 probe (AD-038 draft, 2026-11-19), 1920x1080
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit 0e2386fbee, working tree MODIFIED, src/ tree 90a2e01a9e
Scene: scenes/Gollum_Head_05.mirai.json, edit object 'Gollum_backup_noscale1 ZBrush'
  eye    'Auge_Links': 3392 faces, look yes, iris yes, sclera map yes, level L3
  eye    'Auge_Rechts': 3392 faces, look yes, iris yes, sclera map yes, level L3
  edit   'Gollum_backup_noscale1 ZBrush': 2492 faces, UVs yes, albedo paint composite
  hidden in the file (not drawn): 'Gollum', 'tooth', 'tooth01', 'Zahn_1', 'Zahn_2'
SH9 projection of the studio on the CPU (4096 directions, NumPy): 10.4 ms

(a) frame rows, 1920x1080, 30 rounds after 5; GL_TIME_ELAPSED ms; 'vs wl' = minus `worklight`; CPU = wall ms of the draw + glFinish
  [cage / framed] skin triangles 5469, eye triangles 14976, the meshes cover 17.1 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          4.38     4.32     4.44                9.57
      wl eyes full       5.16     4.64     5.26     +0.78     11.48
      ld skin            1.69     1.69     1.69     -2.68      2.85
      ld frame           3.01     2.56     3.08     -1.36      8.98
      ld no env          2.19     1.70     2.25     -2.19      8.38
      ld no map          2.96     2.48     3.03     -1.41      8.65
      app render         4.38     4.34     4.43     +0.01      9.79
  [cage / close] skin triangles 5469, eye triangles 14976, the meshes cover 60.4 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight         10.92    10.85    10.99               15.61
      wl eyes full      12.15    12.10    12.23     +1.23     18.39
      ld skin            5.33     5.33     5.33     -5.59      6.28
      ld frame           7.95     7.91     8.00     -2.97     14.03
      ld no env          5.34     5.31     5.41     -5.59     11.49
      ld no map          7.79     7.74     7.84     -3.13     14.02
      app render        10.92    10.86    11.00     -0.01     17.53
  [subd1 / framed] skin triangles 22153, eye triangles 14976, the meshes cover 16.9 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight          7.37     7.22     7.46               12.31
      wl eyes full       8.12     7.67     8.25     +0.76     14.71
      ld skin            2.29     2.29     2.30     -5.07      3.46
      ld frame           3.64     3.17     3.72     -3.73     10.26
      ld no env          2.53     2.07     2.58     -4.84      8.56
      ld no map          3.51     3.05     3.58     -3.86     10.00
      app render         7.41     7.31     7.51     +0.04     13.40
  [subd1 / close] skin triangles 22153, eye triangles 14976, the meshes cover 59.9 % of the frame
      row             GPU p50      min      max     vs wl   CPU p50
      worklight         14.78    14.70    14.91               20.90
      wl eyes full      16.05    15.90    16.14     +1.28     23.35
      ld skin            6.18     6.04     6.19     -8.60      7.67
      ld frame           8.82     8.67     8.87     -5.95     16.24
      ld no env          5.85     5.79     5.87     -8.93     12.34
      ld no map          8.61     8.56     8.64     -6.17     15.03
      app render        14.82    14.70    14.93     +0.04     22.15
  skin stand-in variants, compile + link on first use (cold, ms): colour+env 55.8, map 34.9, map+env 71.2

glGetError at the end: 0x0000

(.venv312) PS C:\Users\Manuel\Mirai_Bastel> python experiments\drag_cost\probe_d3_acceptance.py | Tee-Object -FilePath d3_after_ld1.txt
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit 0e2386fbee, working tree MODIFIED, src/ tree 90a2e01a9e
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, MixSurface.update, OrientationTriad.draw, RenderMesh._read_moved, RenderMesh._read_table_moves, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, SkinSurface.update, Viewport._sync_edges, Viewport._sync_surface, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50    52.60  p95    58.44  max    62.23 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.27  p95     0.41
    tick (update_viewport)                   p50    32.49  p95    37.25
    on_draw + glFinish                       p50    19.79  p95    21.94
      tick: Viewport._sync_surface (all of it) p50    32.15  p95    36.99
      tick: stage update (candidates + eval) p50     8.95  p95    10.27
      tick: stage evaluation (mix + skin)    p50     8.82  p95    10.14
      tick: RenderMesh._sync_geometry        p50    22.96  p95    27.35
        of it: moved -> slots, positions (2f) p50     0.86  p95     1.10
        of it: face data -> store            p50     1.62  p95     2.02
      draw: viewport render (faces, wire, overlays) p50     3.42  p95     4.64
        of it: face-data upload              p50     0.78  p95     1.15
      draw: gizmo / bones                    p50     0.93  p95     1.23
      draw: HUD                              p50     0.93  p95     1.35
      draw: triad                            p50     0.26  p95     0.58
      draw: panels                           p50     1.55  p95     2.06
      draw: rest (clear, sync, GPU wait)     p50    12.18  p95    13.84
      gpu: vertex-buffer upload              p50     5.60  p95     7.89
      gpu: mesh draw (face data + shaded pass) p50    11.47  p95    16.69
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50    86.11  p95    96.66  max   104.14 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.10  p95     0.14
    tick (update_viewport)                   p50    36.55  p95    45.00
    on_draw + glFinish                       p50    48.88  p95    55.15
      tick: Viewport._sync_surface (all of it) p50    35.83  p95    43.65
      tick: stage update (candidates + eval) p50    13.46  p95    21.64
      tick: stage evaluation (mix + skin)    p50    13.33  p95    21.51
      tick: RenderMesh._sync_geometry        p50    21.94  p95    25.08
        of it: moved -> slots, positions (2f) p50     0.86  p95     0.99
        of it: face data -> store            p50     1.66  p95     2.01
      draw: viewport render (faces, wire, overlays) p50     3.60  p95     4.57
        of it: face-data upload              p50     0.80  p95     1.28
      draw: gizmo / bones                    p50     6.63  p95     7.24
      draw: HUD                              p50    25.10  p95    28.13
      draw: triad                            p50     0.36  p95     0.54
      draw: panels                           p50     1.63  p95     1.90
      draw: rest (clear, sync, GPU wait)     p50    12.31  p95    13.77
      gpu: vertex-buffer upload              p50    34.19  p95    40.35
      gpu: mesh draw (face data + shaded pass) p50    11.47  p95    47.13
    NOTE gpu mesh draw varies 11.27-49.95 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50    52.08  p95    55.32  max    59.34 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.26  p95     0.32
    tick (update_viewport)                   p50    31.23  p95    33.05
    on_draw + glFinish                       p50    20.61  p95    22.14
      tick: Viewport._sync_surface (all of it) p50    30.31  p95    32.10
      tick: stage update (candidates + eval) p50     8.74  p95     9.95
      tick: stage evaluation (mix + skin)    p50     8.62  p95     9.81
      tick: RenderMesh._sync_geometry        p50    21.25  p95    22.85
        of it: moved -> slots, positions (2f) p50     0.84  p95     0.97
        of it: face data -> store            p50     1.58  p95     1.82
      draw: viewport render (faces, wire, overlays) p50     4.04  p95     4.64
        of it: face-data upload              p50     0.81  p95     1.00
      draw: gizmo / bones                    p50     1.08  p95     1.16
      draw: HUD                              p50     1.14  p95     1.29
      draw: triad                            p50     0.46  p95     0.49
      draw: panels                           p50     1.55  p95     1.76
      draw: rest (clear, sync, GPU wait)     p50    12.59  p95    13.66
      gpu: vertex-buffer upload              p50     5.86  p95     7.97
      gpu: mesh draw (face data + shaded pass) p50    11.38  p95    17.64
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50    86.11  p95    93.86  max    95.84 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.09  p95     0.12
    tick (update_viewport)                   p50    36.68  p95    43.82
    on_draw + glFinish                       p50    48.91  p95    51.94
      tick: Viewport._sync_surface (all of it) p50    35.77  p95    42.84
      tick: stage update (candidates + eval) p50    13.55  p95    21.30
      tick: stage evaluation (mix + skin)    p50    13.44  p95    21.15
      tick: RenderMesh._sync_geometry        p50    21.81  p95    23.23
        of it: moved -> slots, positions (2f) p50     0.91  p95     1.08
        of it: face data -> store            p50     1.64  p95     1.82
      draw: viewport render (faces, wire, overlays) p50     3.43  p95     4.31
        of it: face-data upload              p50     0.71  p95     0.97
      draw: gizmo / bones                    p50     6.58  p95     7.19
      draw: HUD                              p50    24.78  p95    26.16
      draw: triad                            p50     0.34  p95     0.51
      draw: panels                           p50     1.54  p95     1.72
      draw: rest (clear, sync, GPU wait)     p50    12.69  p95    13.65
      gpu: vertex-buffer upload              p50    34.63  p95    38.11
      gpu: mesh draw (face data + shaded pass) p50    11.37  p95    46.10
    NOTE gpu mesh draw varies 11.17-48.32 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```
