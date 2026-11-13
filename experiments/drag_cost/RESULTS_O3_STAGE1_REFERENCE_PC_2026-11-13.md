# O3 stage 1 on the reference PC, 2026-11-13 (audit 2026-11-10 §H step 5, first stage)

Reference PC: Core 2 Quad Q9550, GeForce 9800 GTX, GL 3.3.0, Windows 10 (19045), **Python 3.12.10** in a new venv
`.venv312` with **NumPy 2.2.6** (`numpy-2.2.6-cp312-cp312-win_amd64`, installed from `requirements.txt` through
`requirements-dev.txt`), pytest 9.2.0, pyglet 2.1.19, **`imgui-bundle` 1.93.0 — panels on** (the O1 / O2 runs on this PC
were Python 3.14.2 with panels off). Run supplied by Manu on 2026-11-13. Change: [AD-032](../../docs/architecture/AD-032-PACKED-ARRAYS-NUMPY.md);
container counterpart: [`RESULTS_O3_STAGE1_CONTAINER_2026-11-12.md`](RESULTS_O3_STAGE1_CONTAINER_2026-11-12.md).

- "after" = `40e5ce4` (main after the O3 merge), "working tree MODIFIED, src/ tree `ccd5b2a877`" — the same `src/` tree as
  the O3 commit `47f6fa1` and as the container's "after" runs; the modification lies outside `src/`;
- "before" = `7153fae` (the probe commit, `src/` tree `559d88b8e2` = the O1 code) from a git worktree, "working tree
  clean";
- both with the same interpreter (`.venv312`), after first, then before. Whether NVIDIA "prefer maximum performance" was
  set is not stated; the D3 probe prints its power-management note in the weight rows before and after (GPU rows below
  are therefore p50 only and not compared with the pinned-clock round 3 of O2). The CPU-side rows are not affected.

## D1 — production import and execution on the reference PC: verified

- `import viewport.render_mesh` (which imports `viewport.packed_geometry` and NumPy) under Python 3.12.10 with NumPy
  2.2.6: no error, versions printed.
- Every probe ran the production path (`Application` → `Viewport` → `RenderMesh` → `PackedGeometry` → `GLRenderStore`) on
  the Q9550 without an error.
- The array tests pass on this CPU: `tests/test_packed_geometry.py` (normals **bit-identical** to the pure-Python
  reference, also on `gollum_20k` and after random topology patches), `test_render_mesh_incremental.py` (patch == full
  rebuild, bit-identical), `test_render_mesh.py`, `test_render_mesh_face_data.py` — **64 passed** in 9.4 s.

## Tests

| Step | Result | Duration | Container |
|---|---|---|---|
| O3 tests (4 files, above) | **64 passed** | 9.4 s | 64 passed ✓ |
| GL tests (own process): `pytest tests/test_gl_*.py` | **165 passed** | 7 min 34 s | 165 passed ✓ |
| `pytest tests`, `experiments/morph_lab/tests` | not part of this run | — | 6,928 passed / 1 failed (§I.7) / 8 skipped; 49 passed |

The GL tests include `test_gl_face_data_layout.py`: the production path, now fed from the arrays, draws byte-identical
pixels to the frozen pre-O2 shader on the 9800 GTX driver.

## The pose-step split, `probe_scale_audit.py --only split --assets dense --regions 15`

87.5k fixture, 15 % region = 13,125 weighted vertices, skin only, 20 steps, p50 ms.

| | before, wire off | after, wire off | factor | before, wire ON | after, wire ON |
|---|---:|---:|---:|---:|---:|
| step (pointer_motion + update_viewport) | 267.25 | **96.66** | 2.8× | 269.23 | **93.55** |
| step p95 | 270.94 | 101.00 | | 274.64 | 98.58 |
| 1 skin evaluation | 53.60 | 53.32 | — | 54.50 | 52.24 |
| 2 `RenderMesh._sync_geometry` | 204.80 | **34.60** | 5.9× | 207.08 | **33.21** |
| 2a neighbourhood | 21.98 | 3.44 | 6.4× | 22.01 | 3.33 |
| 2b face normals | 68.01 | 7.81 | 8.7× | 69.05 | 7.95 |
| 2c vertex normals | 35.45 | 4.93 | 7.2× | 36.93 | 4.81 |
| 2d positions + normals → mirror → store | 42.05 | 6.18 | 6.8× | 41.50 | 6.20 |
| 2e face data → store | 22.16 | 1.57 | 14× | 22.87 | 1.59 |
| 2f ids → slots, positions → arrays (new) | — | 9.50 | | — | 8.63 |
| draw + glFinish | 15.68 | 16.01 | | 16.02 | 16.29 |

Per moved vertex, `_sync_geometry` costs 15.6 → **2.6 µs**. The wire costs 0 ms per step (O0).

**Against the container:** every part of the new `_sync_geometry` is ≈ 2.8–3.0× its container value (2e: 2.2×) —
the NumPy parts scale like the Python parts here, not like the kernel probe's 1.6× (30.7 vs 19.5 ms, whole 1-ring in a
few large calls): at 13k elements per call the cost is per-call overhead, not arithmetic. The estimate in the container
addendum ("≈ 25–40 ms [H]") held: 33.2–34.6 ms.

## D3 acceptance probe, `probe_d3_acceptance.py` (87.5k fixture, 15 % jaw region, Morph + Skin, complete frame)

p50 / p95 ms, 60 frames per row.

| Row | frame before | frame after | × bar (p95) after | tick before → after | eval p50 | sync p50 | on_draw p50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| pose wire off | 294.63 / 298.94 | **117.77 / 122.87** | 3.7× | 274.15 → 97.35 | 57.21 → 55.53 | 208.32 → **32.80** | 20.07 → 20.21 |
| weight wire off | 361.96 / 388.13 | **189.17 / 199.91** | 6.0× | 310.06 → 140.05 | 87.39 → 92.37 | 207.18 → **32.22** | 51.89 → 49.31 |
| pose wire ON | 298.40 / 306.09 | **119.07 / 123.87** | 3.7× | 277.59 → 98.13 | 57.84 → 56.39 | 211.44 → **33.04** | 20.45 → 20.87 |
| weight wire ON | 368.01 / 373.38 | **188.21 / 264.47** | 7.9× | 315.09 → 138.93 | 87.44 → 91.10 | 211.38 → **32.06** | 52.60 → 49.56 |

- Face data → store 22.75–23.25 → 1.62–1.66 ms; bytes per frame unchanged (556,940).
- Unchanged by O3 (as expected): the HUD in weight rows (27.8 / 28.3 → 25.6 / 25.0 ms), gizmo / bones in weight rows
  (≈ 6.7 ms), the GPU vertex-buffer upload in weight rows (37.4 → 35.0–35.2 ms GPU timer; 5.6–6.1 ms in pose rows),
  the GPU mesh draw (11.4–11.5 ms p50 before and after; its p95 of 47–51 ms in weight rows is the power-state note).
- The weight-wire-ON row has single frames of 1.8 s (after) and 2.0 s (before) — its p95 after (264 ms, tick p95 202,
  eval p95 131) is those outliers, not the change; the other three rows have p95 within 5–11 ms of p50.

**D3 verdict [RPC]: OVER** in every row — p95 3.7× (pose) to 6–8× (weight) the minimum bar of 33.3 ms (before: 9–12×).

Where an after frame goes (p50):

| | pose, wire off (117.8 ms) | weight, wire off (189.2 ms) |
|---|---:|---:|
| stage evaluation (mix + skin) — O3 stage 2 | 55.5 (47 %) | 92.4 (49 %) |
| `_sync_geometry` (of it 9.5 ms per-vertex read, row 2f) | 32.8 (28 %) | 32.2 (17 %) |
| rest of the tick (input, other syncs) | 9.0 | 15.5 |
| `on_draw` + `glFinish` | 20.2 (17 %): GPU wait ≈ 12 | 49.3 (26 %): HUD 25.6, gizmo / bones 6.7, GPU wait ≈ 12 |

## One-time costs and memory, `probe_scale_audit.py --only chain`

| | 87.5k before | 87.5k after | 20k before | 20k after |
|---|---:|---:|---:|---:|
| load OBJ + scene + first frame | 12,600 ms | **9,761 ms** | 3,159 ms | **2,380 ms** |
| first weight step (builds the mix surface) | 6,376 ms | **3,179 ms** | 1,529 ms | **751 ms** |
| of it: new RenderMesh | 6,233 ms | **3,035 ms** | 1,494 ms | **715 ms** |
| first pose step (builds the skin surface) | 7,130 ms | **3,658 ms** | 1,706 ms | **897 ms** |
| of it: new RenderMesh | 6,630 ms | **3,036 ms** | 1,568 ms | **736 ms** |
| process memory after both stages (working set, first pose row) | 714 MiB | **619 MiB** | 242 MiB | **222 MiB** |
| next weight / pose step + frame (one sample each) | 264 / 287 ms | 74 / 101 ms | 61 / 66 ms | 22 / 26 ms |
| save / parse scene file (no RenderMesh) | 6,719 / 7,582 ms | 6,930 / 7,272 ms | 1,684 / 1,600 ms | 1,667 / 1,546 ms |

A newly shown surface's `RenderMesh` at 87.5k: 6.2–6.6 → 3.0 s (2.1×); the rest of that build is per-face Python
(triangulation, the slot layout's dicts and lists) that stage 1 does not touch.

## Reading

- **O3 stage 1 did on the reference PC what it did in the container:** `_sync_geometry` −83 to −85 % (205–211 → 32–35
  ms), the pose frame −60 % (295 → 118 ms), the weight frame −48 % (362 → 189 ms), a new surface `RenderMesh` −51 to
  −54 % (6.2–6.6 → 3.0 s).
- **D3 is still unmet** (3.7–8× at p95). The pose frame is now half stage evaluation, a quarter `_sync_geometry`, a
  sixth `on_draw`. The weight frame adds the HUD (25.6 ms) and, on the GPU, the vertex-buffer upload (35 ms) — both
  their own packages.
- **D2 is not triggered yet** (it applies after O3, and stage 2 is open). An estimate for planning only **[H]**: stage 2
  with an array hand-over would remove most of the 55–92 ms evaluation (the kernel probe measured LBS at 11.7 ms and one
  morph target at 0.9 ms for this region on this PC) and the 9.5 ms read of row 2f; a pose frame would then be in the
  order of 60–70 ms — still about twice the bar, with ≈ 23–25 ms left in the NumPy part of the sync (overhead-bound, see
  the split) and ≈ 20 ms in `on_draw`. That is the point where D2 (O4, compiled kernels) and the GPU cost of the O2
  shading (≈ 9.4 ms of the ≈ 11.4 ms mesh draw at full clock, O2 addendum) become the deciding items.
- Open from this run: `pytest tests` and `experiments/morph_lab/tests` under Python 3.12 (not part of the supplied
  commands); GPU rows with "prefer maximum performance" confirmed.

## Raw output (as supplied)

```
(.venv) PS C:\Users\Manuel\Mirai_Bastel> py -3.12 -m venv .venv312
(.venv) PS C:\Users\Manuel\Mirai_Bastel> $py = (Resolve-Path .\.venv312\Scripts\python.exe).Path; & $py --version; & $py -m pip install -r requirements-dev.txt
Python 3.12.10
Collecting numpy==2.2.6 (from -r C:\Users\Manuel\Mirai_Bastel\requirements.txt (line 9))
  Using cached numpy-2.2.6-cp312-cp312-win_amd64.whl.metadata (60 kB)
Requirement already satisfied: pytest in c:\users\manuel\mirai_bastel\.venv312\lib\site-packages (from -r requirements-dev.txt (line 4)) (9.2.0)
Requirement already satisfied: pyglet in c:\users\manuel\mirai_bastel\.venv312\lib\site-packages (from -r requirements-dev.txt (line 11)) (2.1.19)
Requirement already satisfied: imgui-bundle==1.93.0 in c:\users\manuel\mirai_bastel\.venv312\lib\site-packages (from -r requirements-dev.txt (line 16)) (1.93.0)
Requirement already satisfied: colorama>=0.4 in c:\users\manuel\mirai_bastel\.venv312\lib\site-packages (from pytest->-r requirements-dev.txt (line 4)) (0.4.6)
Requirement already satisfied: iniconfig>=2 in c:\users\manuel\mirai_bastel\.venv312\lib\site-packages (from pytest->-r requirements-dev.txt (line 4)) (2.3.1)
Requirement already satisfied: packaging>=24 in c:\users\manuel\mirai_bastel\.venv312\lib\site-packages (from pytest->-r requirements-dev.txt (line 4)) (26.3)
Requirement already satisfied: pluggy<2,>=1.6 in c:\users\manuel\mirai_bastel\.venv312\lib\site-packages (from pytest->-r requirements-dev.txt (line 4)) (1.7.0)
Requirement already satisfied: pygments>=2.15 in c:\users\manuel\mirai_bastel\.venv312\lib\site-packages (from pytest->-r requirements-dev.txt (line 4)) (2.21.0)
Using cached numpy-2.2.6-cp312-cp312-win_amd64.whl (12.6 MB)
Installing collected packages: numpy
Successfully installed numpy-2.2.6

[notice] A new release of pip is available: 25.0.1 -> 26.3
[notice] To update, run: C:\Users\Manuel\Mirai_Bastel\.venv312\Scripts\python.exe -m pip install --upgrade pip
(.venv) PS C:\Users\Manuel\Mirai_Bastel> & $py -c "import sys, numpy; sys.path.insert(0, 'src'); import viewport.render_mesh; print(sys.version); print('numpy', numpy.__version__)"
3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]
numpy 2.2.6
(.venv) PS C:\Users\Manuel\Mirai_Bastel> & $py -m pytest tests\test_packed_geometry.py tests\test_render_mesh_incremental.py tests\test_render_mesh.py tests\test_render_mesh_face_data.py -q
................................................................                                                                   [100%]
64 passed in 9.43s
(.venv) PS C:\Users\Manuel\Mirai_Bastel> & $py -m pytest (Get-ChildItem tests\test_gl_*.py) -q
.................................................................................................................................. [ 78%]
...................................                                                                                                [100%]
165 passed in 453.65s (0:07:33)
(.venv) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\drag_cost\probe_scale_audit.py --only split --assets dense --regions 15
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 40e5ce4f64, working tree MODIFIED, src/ tree ccd5b2a877
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           96.66  100 %   (p95 101.00)
  1 skin evaluation (LBS + Mesh writes)             53.32   55.2 %
  2 RenderMesh._sync_geometry, total                34.60   35.8 %
  2a  neighbourhood sets                             3.44    3.6 %
  2b  face normals                                   7.81    8.1 %
  2c  vertex normals                                 4.93    5.1 %
  2d  positions + normals -> mirror -> store         6.18    6.4 %
  2e  face data -> store (O2: face normals)          1.57    1.6 %
  2f  ids -> slots, positions -> arrays (O3)         9.50    9.8 %
  4 face-data glBufferSubData at draw                0.86    0.9 %
  draw + glFinish                                   16.01
  bytes handed to the store per step               556940  (42 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           93.55  100 %   (p95 98.58)
  1 skin evaluation (LBS + Mesh writes)             52.24   55.8 %
  2 RenderMesh._sync_geometry, total                33.21   35.5 %
  2a  neighbourhood sets                             3.33    3.6 %
  2b  face normals                                   7.95    8.5 %
  2c  vertex normals                                 4.81    5.1 %
  2d  positions + normals -> mirror -> store         6.20    6.6 %
  2e  face data -> store (O2: face normals)          1.59    1.7 %
  2f  ids -> slots, positions -> arrays (O3)         8.63    9.2 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                0.81    0.9 %
  draw + glFinish                                   16.29
  bytes handed to the store per step               556940  (42 per weighted vertex)
(.venv) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\drag_cost\probe_d3_acceptance.py
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit 40e5ce4f64, working tree MODIFIED, src/ tree ccd5b2a877
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   117.77  p95   122.87  max   124.33 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.22  p95     0.26
    tick (update_viewport)                   p50    97.35  p95   102.14
    on_draw + glFinish                       p50    20.21  p95    21.92
      tick: stage evaluation (mix + skin)    p50    55.53  p95    58.78
      tick: RenderMesh._sync_geometry        p50    32.80  p95    36.01
        of it: face data -> store            p50     1.64  p95     2.03
      draw: viewport render (faces, wire, overlays) p50     3.73  p95     4.31
        of it: face-data upload              p50     0.87  p95     1.21
      draw: gizmo / bones                    p50     1.03  p95     1.33
      draw: HUD                              p50     1.17  p95     1.45
      draw: triad                            p50     0.33  p95     0.55
      draw: panels                           p50     1.63  p95     1.99
      draw: rest (clear, sync, GPU wait)     p50    12.17  p95    13.80
      gpu: vertex-buffer upload              p50     5.58  p95     7.90
      gpu: mesh draw (face data + shaded pass) p50    11.45  p95    17.63
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   189.17  p95   199.91  max   208.08 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.09  p95     0.11
    tick (update_viewport)                   p50   140.05  p95   147.59
    on_draw + glFinish                       p50    49.31  p95    53.28
      tick: stage evaluation (mix + skin)    p50    92.37  p95    97.28
      tick: RenderMesh._sync_geometry        p50    32.22  p95    36.77
        of it: face data -> store            p50     1.62  p95     2.26
      draw: viewport render (faces, wire, overlays) p50     3.64  p95     4.51
        of it: face-data upload              p50     0.85  p95     1.20
      draw: gizmo / bones                    p50     6.68  p95     7.36
      draw: HUD                              p50    25.58  p95    27.63
      draw: triad                            p50     0.31  p95     0.58
      draw: panels                           p50     1.59  p95     2.00
      draw: rest (clear, sync, GPU wait)     p50    12.31  p95    14.07
      gpu: vertex-buffer upload              p50    35.04  p95    38.59
      gpu: mesh draw (face data + shaded pass) p50    11.46  p95    48.43
    NOTE gpu mesh draw varies 11.32-50.34 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   119.07  p95   123.87  max   125.72 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.21  p95     0.26
    tick (update_viewport)                   p50    98.13  p95   101.91
    on_draw + glFinish                       p50    20.87  p95    23.00
      tick: stage evaluation (mix + skin)    p50    56.39  p95    59.37
      tick: RenderMesh._sync_geometry        p50    33.04  p95    34.77
        of it: face data -> store            p50     1.66  p95     1.93
      draw: viewport render (faces, wire, overlays) p50     4.04  p95     5.05
        of it: face-data upload              p50     0.83  p95     1.27
      draw: gizmo / bones                    p50     1.05  p95     1.28
      draw: HUD                              p50     1.17  p95     1.37
      draw: triad                            p50     0.38  p95     0.59
      draw: panels                           p50     1.65  p95     1.99
      draw: rest (clear, sync, GPU wait)     p50    12.57  p95    13.59
      gpu: vertex-buffer upload              p50     6.12  p95     8.48
      gpu: mesh draw (face data + shaded pass) p50    11.36  p95    17.87
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   188.21  p95   264.47  max  1796.84 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.09  p95     0.12
    tick (update_viewport)                   p50   138.93  p95   202.41
    on_draw + glFinish                       p50    49.56  p95    59.12
      tick: stage evaluation (mix + skin)    p50    91.10  p95   131.45
      tick: RenderMesh._sync_geometry        p50    32.06  p95    38.27
        of it: face data -> store            p50     1.62  p95     2.21
      draw: viewport render (faces, wire, overlays) p50     4.13  p95     4.87
        of it: face-data upload              p50     0.88  p95     1.06
      draw: gizmo / bones                    p50     6.60  p95     7.32
      draw: HUD                              p50    25.04  p95    32.55
      draw: triad                            p50     0.28  p95     0.54
      draw: panels                           p50     1.49  p95     2.06
      draw: rest (clear, sync, GPU wait)     p50    12.75  p95    14.35
      gpu: vertex-buffer upload              p50    35.22  p95    44.20
      gpu: mesh draw (face data + shaded pass) p50    11.37  p95    47.49
    NOTE gpu mesh draw varies 11.16-60.09 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
(.venv) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\drag_cost\probe_scale_audit.py --only chain --assets examples\meshes\gollum_20k.obj
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 40e5ce4f64, working tree MODIFIED, src/ tree ccd5b2a877
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                2380 ms   process     161 MiB (   +112)
  save scene file                                               1667 ms   process     163 MiB (     +1)
    file size 11.7 MiB
  parse scene file (scene_from_json, no viewport)               1546 ms   process     175 MiB (    +13)
  write one target, offsets on 15 % of the points                318 ms   process     164 MiB (    -12)
  first weight step 0 -> 60 % (builds the mix surface)           751 ms   process     207 MiB (    +44)
    of it: stage evaluation 20 ms (MixSurface / SkinSurface.update), new RenderMesh 715 ms
  next weight step (patch) + frame                                22 ms   process     208 MiB (     +1)
    of it: stage evaluation 6 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             92 ms   process     208 MiB (     +0)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                      897 ms   process     222 MiB (    +14)
    of it: stage evaluation 34 ms (MixSurface / SkinSurface.update), new RenderMesh 736 ms
  next pose step (patch, morph + skin) + frame                    26 ms   process     225 MiB (     +2)
    of it: stage evaluation 12 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
(.venv) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\drag_cost\probe_scale_audit.py --only chain --assets dense
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 40e5ce4f64, working tree MODIFIED, src/ tree ccd5b2a877
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                                9761 ms   process     409 MiB (   +360)
  save scene file                                               6930 ms   process     412 MiB (     +3)
    file size 46.7 MiB
  parse scene file (scene_from_json, no viewport)               7272 ms   process     457 MiB (    +45)
  write one target, offsets on 15 % of the points               1301 ms   process     411 MiB (    -46)
  first weight step 0 -> 60 % (builds the mix surface)          3179 ms   process     577 MiB (   +167)
    of it: stage evaluation 104 ms (MixSurface / SkinSurface.update), new RenderMesh 3035 ms
  next weight step (patch) + frame                                74 ms   process     573 MiB (     -4)
    of it: stage evaluation 29 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            401 ms   process     583 MiB (    +10)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     3658 ms   process     619 MiB (    +36)
    of it: stage evaluation 154 ms (MixSurface / SkinSurface.update), new RenderMesh 3036 ms
  next pose step (patch, morph + skin) + frame                   101 ms   process     620 MiB (     +1)
    of it: stage evaluation 55 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
(.venv) PS C:\Users\Manuel\Mirai_Bastel> git worktree add ..\mirai-pre-o3 7153fae
Preparing worktree (detached HEAD 7153fae)
Updating files: 100% (1238/1238), done.
HEAD is now at 7153fae probe(drag_cost): the scale probe times the O3 array parts too, skipped where absent
(.venv) PS C:\Users\Manuel\Mirai_Bastel> Push-Location ..\mirai-pre-o3; & $py experiments\drag_cost\probe_scale_audit.py --only split --assets dense --regions 15; & $py experiments\drag_cost\probe_d3_acceptance.py; & $py experiments\drag_cost\probe_scale_audit.py --only chain --assets examples\meshes\gollum_20k.obj; & $py experiments\drag_cost\probe_scale_audit.py --only chain --assets dense; Pop-Location
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree clean
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          267.25  100 %   (p95 270.94)
  1 skin evaluation (LBS + Mesh writes)             53.60   20.1 %
  2 RenderMesh._sync_geometry, total               204.80   76.6 %
  2a  neighbourhood sets                            21.98    8.2 %
  2b  face normals                                  68.01   25.4 %
  2c  vertex normals                                35.45   13.3 %
  2d  positions + normals -> mirror -> store        42.05   15.7 %
  2e  face data -> store (O2: face normals)         22.16    8.3 %
  2f  ids -> slots, positions -> arrays (O3)            -          (no such method in this checkout)
  4 face-data glBufferSubData at draw                0.87    0.3 %
  draw + glFinish                                   15.68
  bytes handed to the store per step               556940  (42 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          269.23  100 %   (p95 274.64)
  1 skin evaluation (LBS + Mesh writes)             54.50   20.2 %
  2 RenderMesh._sync_geometry, total               207.08   76.9 %
  2a  neighbourhood sets                            22.01    8.2 %
  2b  face normals                                  69.05   25.6 %
  2c  vertex normals                                36.93   13.7 %
  2d  positions + normals -> mirror -> store        41.50   15.4 %
  2e  face data -> store (O2: face normals)         22.87    8.5 %
  2f  ids -> slots, positions -> arrays (O3)            -          (no such method in this checkout)
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                0.67    0.2 %
  draw + glFinish                                   16.02
  bytes handed to the store per step               556940  (42 per weighted vertex)
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit 7153faefa1, working tree clean
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   294.63  p95   298.94  max   300.97 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.21  p95     0.24
    tick (update_viewport)                   p50   274.15  p95   279.33
    on_draw + glFinish                       p50    20.07  p95    21.96
      tick: stage evaluation (mix + skin)    p50    57.21  p95    60.32
      tick: RenderMesh._sync_geometry        p50   208.32  p95   212.03
        of it: face data -> store            p50    22.75  p95    23.71
      draw: viewport render (faces, wire, overlays) p50     3.60  p95     4.24
        of it: face-data upload              p50     0.80  p95     1.11
      draw: gizmo / bones                    p50     1.10  p95     1.30
      draw: HUD                              p50     1.17  p95     1.24
      draw: triad                            p50     0.47  p95     0.50
      draw: panels                           p50     1.62  p95     2.17
      draw: rest (clear, sync, GPU wait)     p50    12.17  p95    13.95
      gpu: vertex-buffer upload              p50     5.92  p95     7.72
      gpu: mesh draw (face data + shaded pass) p50    11.47  p95    17.18
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   361.96  p95   388.13  max   414.52 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.09  p95     0.13
    tick (update_viewport)                   p50   310.06  p95   330.30
    on_draw + glFinish                       p50    51.89  p95    56.66
      tick: stage evaluation (mix + skin)    p50    87.39  p95    98.87
      tick: RenderMesh._sync_geometry        p50   207.18  p95   213.38
        of it: face data -> store            p50    23.23  p95    25.15
      draw: viewport render (faces, wire, overlays) p50     3.62  p95     4.36
        of it: face-data upload              p50     0.80  p95     1.06
      draw: gizmo / bones                    p50     6.75  p95     7.12
      draw: HUD                              p50    27.77  p95    31.65
      draw: triad                            p50     0.29  p95     0.52
      draw: panels                           p50     1.49  p95     1.80
      draw: rest (clear, sync, GPU wait)     p50    12.34  p95    14.00
      gpu: vertex-buffer upload              p50    37.42  p95    41.81
      gpu: mesh draw (face data + shaded pass) p50    11.50  p95    49.05
    NOTE gpu mesh draw varies 11.37-55.65 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   298.40  p95   306.09  max   316.52 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.21  p95     0.24
    tick (update_viewport)                   p50   277.59  p95   286.53
    on_draw + glFinish                       p50    20.45  p95    22.16
      tick: stage evaluation (mix + skin)    p50    57.84  p95    60.05
      tick: RenderMesh._sync_geometry        p50   211.44  p95   218.17
        of it: face data -> store            p50    23.25  p95    25.84
      draw: viewport render (faces, wire, overlays) p50     3.98  p95     4.43
        of it: face-data upload              p50     0.80  p95     0.91
      draw: gizmo / bones                    p50     1.05  p95     1.33
      draw: HUD                              p50     1.04  p95     1.34
      draw: triad                            p50     0.24  p95     0.51
      draw: panels                           p50     1.35  p95     1.85
      draw: rest (clear, sync, GPU wait)     p50    12.61  p95    13.17
      gpu: vertex-buffer upload              p50     6.09  p95     7.77
      gpu: mesh draw (face data + shaded pass) p50    11.38  p95    16.68
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   368.01  p95   373.38  max  2045.69 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.09  p95     0.11
    tick (update_viewport)                   p50   315.09  p95   320.42
    on_draw + glFinish                       p50    52.60  p95    55.38
      tick: stage evaluation (mix + skin)    p50    87.44  p95    90.30
      tick: RenderMesh._sync_geometry        p50   211.38  p95   214.64
        of it: face data -> store            p50    23.23  p95    24.27
      draw: viewport render (faces, wire, overlays) p50     3.96  p95     4.43
        of it: face-data upload              p50     0.81  p95     1.08
      draw: gizmo / bones                    p50     6.69  p95     7.12
      draw: HUD                              p50    28.34  p95    30.55
      draw: triad                            p50     0.27  p95     0.49
      draw: panels                           p50     1.56  p95     1.73
      draw: rest (clear, sync, GPU wait)     p50    12.70  p95    13.68
      gpu: vertex-buffer upload              p50    37.49  p95    41.31
      gpu: mesh draw (face data + shaded pass) p50    11.36  p95    51.21
    NOTE gpu mesh draw varies 11.18-54.41 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree clean
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                3159 ms   process     163 MiB (   +114)
  save scene file                                               1684 ms   process     167 MiB (     +4)
    file size 11.7 MiB
  parse scene file (scene_from_json, no viewport)               1600 ms   process     177 MiB (     +9)
  write one target, offsets on 15 % of the points                319 ms   process     166 MiB (    -11)
  first weight step 0 -> 60 % (builds the mix surface)          1529 ms   process     221 MiB (    +55)
    of it: stage evaluation 20 ms (MixSurface / SkinSurface.update), new RenderMesh 1494 ms
  next weight step (patch) + frame                                61 ms   process     222 MiB (     +1)
    of it: stage evaluation 6 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             92 ms   process     222 MiB (     +0)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     1706 ms   process     242 MiB (    +20)
    of it: stage evaluation 35 ms (MixSurface / SkinSurface.update), new RenderMesh 1568 ms
  next pose step (patch, morph + skin) + frame                    66 ms   process     242 MiB (     +0)
    of it: stage evaluation 13 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree clean
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                               12600 ms   process     446 MiB (   +397)
  save scene file                                               6719 ms   process     451 MiB (     +5)
    file size 46.7 MiB
  parse scene file (scene_from_json, no viewport)               7582 ms   process     494 MiB (    +44)
  write one target, offsets on 15 % of the points               1296 ms   process     449 MiB (    -45)
  first weight step 0 -> 60 % (builds the mix surface)          6376 ms   process     659 MiB (   +210)
    of it: stage evaluation 104 ms (MixSurface / SkinSurface.update), new RenderMesh 6233 ms
  next weight step (patch) + frame                               264 ms   process     658 MiB (     -1)
    of it: stage evaluation 32 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            412 ms   process     666 MiB (     +8)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     7130 ms   process     714 MiB (    +48)
    of it: stage evaluation 157 ms (MixSurface / SkinSurface.update), new RenderMesh 6630 ms
  next pose step (patch, morph + skin) + frame                   287 ms   process     714 MiB (     -0)
    of it: stage evaluation 54 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```
