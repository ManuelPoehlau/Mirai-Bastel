# O3 stage 2 on the reference PC, 2026-11-13 (audit 2026-11-10 §H step 5, second stage)

Reference PC: Core 2 Quad Q9550, GeForce 9800 GTX, GL 3.3.0, Windows 10 (19045), **Python 3.12.10** in `.venv312` with
**NumPy 2.2.6**, `imgui-bundle` installed (panels on). Run supplied by Manu on 2026-11-13. Change:
[AD-032 §11–§12](../../docs/architecture/AD-032-PACKED-ARRAYS-NUMPY.md#11-stage-2--design-2026-11-13); container
counterpart: [`RESULTS_O3_STAGE2_CONTAINER_2026-11-13.md`](RESULTS_O3_STAGE2_CONTAINER_2026-11-13.md).

- "after" = `43d0ef3` (the stage-2 commit), "working tree MODIFIED, src/ tree `94addddafd`" — the committed `src/` tree
  (`git rev-parse 43d0ef3:src`) and the one measured in the container; the modification lies outside `src/`;
- "before" = **the stage-1 run on this PC the same day** ([`RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md`](RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md),
  "after" column: `40e5ce4`, `src/` tree `ccd5b2a877`, the same `.venv312`). The worktree commands for a before run of
  `10beee7` were not part of this run. Between `ccd5b2a877` and the stage-2 base `8f52936795` only
  `viewport/packed_geometry.py` changed (`b7bf49c`: the NumPy version message before the import, not on a timed
  path), so the stage-1 "after" is the stage-2 "before" up to run-to-run variation. Whether NVIDIA "prefer maximum
  performance" was set is not stated (the weight rows print the power-management note, as before); CPU rows are not
  affected.

## Tests

| Step | Result | Duration | Container |
|---|---|---|---|
| stage-2 tests and the oracles (7 files: `test_stage_arrays`, `test_surface_positions`, `test_morph_multi`, `test_skin_stage`, `test_morph_picking`, `test_render_mesh_incremental`, `test_packed_geometry`) | **140 passed** | 17.4 s | 140 ✓ |
| GL tests (own process): `pytest tests\test_gl_*.py` | **165 passed** | 7 min 14 s | 165 ✓ |
| `pytest tests` | **6,944 passed**, 1 failed, 8 skipped, 66 subtests | 37 min 42 s | the same ✓ |
| `experiments/morph_lab/tests` | **49 passed** | 14.8 s | 49 ✓ |
| `experiments/drag_cost/tests` | **85 passed** | 11.2 s | 85 ✓ |

- The GL tests include `test_gl_face_data_layout.py` (the O2 pixel gate) and the morph-picking GL tests: the arrays
  draw and pick as before on the 9800 GTX driver.
- The one failure is `tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring`, `assert None == 'transform'` at line
  145 — the same assertion that fails in the container (the pre-existing local probe file, audit §I.7), not this change.
- **First complete `pytest tests` under Python 3.12 on this PC** (open since stage 1): the run has the container's counts
  exactly (the O1 run under Python 3.14 without `imgui-bundle` had 6,555 passed / 183 skipped), and the O1 failure
  `test_hud_strip.py::test_the_triad_ignores_zoom_and_pan_and_perspective` passes since `6e48e36`.
  `experiments/morph_lab/tests` under 3.12: 49 passed (also open since stage 1).

## The pose-step split, `probe_scale_audit.py --only split --assets dense --regions 15`

87.5k fixture, 15 % region = 13,125 weighted vertices, skin only, 20 steps, p50 ms. Before = stage 1 on this PC.

| | stage 1, wire off | **stage 2, wire off** | factor | stage 1, wire ON | stage 2, wire ON | × container (after 2) |
|---|---:|---:|---:|---:|---:|---:|
| step (pointer_motion + update_viewport) | 96.66 | **31.34** | 3.1× | 93.55 | **31.40** | 2.2× |
| step p95 | 101.00 | 34.39 | | 98.58 | 37.84 | |
| 1 skin evaluation (`_recompute`) | 53.32 | **7.88** | 6.8× | 52.24 | 7.85 | 2.0× |
| 5 skin stage update, total | — | 7.97 | | — | 7.96 | 1.9× |
| 2 `RenderMesh._sync_geometry` | 34.60 | **22.89** | 1.5× | 33.21 | 22.91 | 2.3× |
| 2a neighbourhood | 3.44 | 3.15 | | 3.33 | 3.21 | 2.4× |
| 2b face normals | 7.81 | 6.56 | | 7.95 | 6.42 | 2.2× |
| 2c vertex normals | 4.93 | 4.71 | | 4.81 | 4.81 | 2.4× |
| 2d positions + normals → store | 6.18 | 5.60 | | 6.20 | 5.59 | 2.4× |
| 2e face data → store | 1.57 | 1.56 | | 1.59 | 1.56 | 1.9× |
| 2f moved → slots, positions → arrays | 9.50 | **0.84** | 11× | 8.63 | 0.84 | 1.8× |
| 6 `Viewport._sync_surface`, total | — | 31.00 | | — | 31.01 | 2.2× |
| draw + glFinish | 16.01 | 15.26 | | 16.29 | 15.73 | |
| bytes to the store per step | 556,940 | 556,940 | | 556,940 | 556,940 | |

The skin evaluation fell 6.8× (53.3 → 7.9 ms) and row 2f 11× (9.5 → 0.84 ms); rows 2a–2e (stage 1's kernels) are
unchanged. The new parts cost ≈ 2× their container time here — less than the ≈ 3× of stage 1's parts (fewer, larger
NumPy calls per frame in the stages). The step is now 73 % `_sync_geometry` (stage 1's NumPy work), 25 % skin.

## D3 acceptance probe, `probe_d3_acceptance.py` (87.5k fixture, 15 % jaw region, Morph + Skin, complete frame)

p50 / p95 ms, 60 frames per row. Before = stage 1 on this PC.

| Row | frame stage 1 | **frame stage 2** | × bar (p95) | tick | stages (eval) | sync (2f) | on_draw |
|---|---:|---:|---:|---:|---:|---:|---:|
| pose wire off | 117.77 / 122.87 | **50.86 / 53.85** | 1.6× | 97.35 → **31.11** | 55.53 → **8.72** | 32.80 → 21.51 (0.86) | 20.21 → 19.62 |
| weight wire off | 189.17 / 199.91 | **85.10 / 92.37** | 2.8× | 140.05 → **36.04** | 92.37 → **13.21** | 32.22 → 21.58 (0.84) | 49.31 → 48.32 |
| pose wire ON | 119.07 / 123.87 | **51.72 / 54.48** | 1.6× | 98.13 → **31.39** | 56.39 → **8.43** | 33.04 → 22.40 (0.84) | 20.87 → 20.19 |
| weight wire ON | 188.21 / 264.47 | **85.48 / 94.26** | 2.8× | 138.93 → **35.98** | 91.10 → **13.19** | 32.06 → 21.54 (0.84) | 49.56 → 49.29 |

- **D3 verdict [RPC]: OVER** in every row — p95 1.6× (pose) and 2.8× (weight) the minimum bar of 33.3 ms (stage 1:
  3.7× / 6.0–7.9×). The pose-row max of 80.88 ms (wire ON) is one frame; p95 is 54.48.
- The rest of the tick (tick − stages − sync) fell from 9.0 / 15.5 ms to 0.9 / 1.3 ms (pose / weight): the per-vertex
  sets, copies and journal merges outside the evaluation are gone too.
- Unchanged, as expected: `on_draw` (pose 19.6–20.2 ms; weight 48.3–49.3 ms with the HUD 24.7–24.9 ms and gizmo /
  bones 6.6–6.7 ms), the GPU mesh draw (11.4 ms p50; p95 47–48 ms in weight rows: the power-state note), the GPU
  vertex-buffer upload (5.8–5.9 ms in pose rows, 34.2–34.6 ms in weight rows).
- The [H] estimate of the container results (pose ≈ 55–60 ms, weight ≈ 95 ms) was slightly pessimistic: 50.9 / 85.1 ms
  p50, because the new parts scale ≈ 2× here, not 3×.

Where a stage-2 frame goes (p50):

| | pose, wire off (50.86 ms) | weight, wire off (85.10 ms) |
|---|---:|---:|
| `_sync_geometry` (stage 1's NumPy kernels; 2f 0.86) | 21.51 (42 %) | 21.58 (25 %) |
| stage evaluation (mix + skin) | 8.72 (17 %) | 13.21 (16 %) |
| rest of the tick | 0.9 | 1.3 |
| `on_draw` + `glFinish` | 19.62 (39 %): GPU wait ≈ 12, viewport 3.4, panels 1.5, gizmo 1.1, HUD 1.0 | 48.32 (57 %): HUD 24.9, gizmo / bones 6.7, GPU wait ≈ 12, viewport 3.3, panels 1.6 |
| on the GPU timer | mesh draw 11.4, vertex-buffer upload 5.8 | mesh draw 11.5, vertex-buffer upload 34.2 |

## One-time costs and memory, `probe_scale_audit.py --only chain`

| | 87.5k stage 1 | **87.5k stage 2** | 20k stage 1 | **20k stage 2** |
|---|---:|---:|---:|---:|
| load OBJ + scene + first frame | 9,761 ms | 9,715 ms | 2,380 ms | 2,419 ms |
| first weight step (builds the mix surface) | 3,179 ms | 3,271 ms | 751 ms | 798 ms |
| of it: new RenderMesh | 3,035 ms | 3,111 ms | 715 ms | 754 ms |
| first pose step (builds the skin surface) | 3,658 ms | 3,767 ms | 897 ms | 932 ms |
| of it: new RenderMesh | 3,036 ms | 3,133 ms | 736 ms | 768 ms |
| of it: stage evaluation (weight / pose row) | — | 119 / 158 ms | — | 28 / 35 ms |
| next weight / pose step + frame (one sample each) | 74 / 101 ms | **32 / 42 ms** | 22 / 26 ms | **13 / 14 ms** |
| process memory after both stages (first pose row) | 619 MiB | 630 MiB | 222 MiB | 229 MiB |

- **A new surface `RenderMesh` is 2.5–5 % slower** (87.5k: +76 / +97 ms; 20k: +39 / +32 ms) — consistently in all four
  rows, so not run-to-run noise alone. Cause, measured in the container afterwards: the full build needs every
  position as a Python tuple for the triangulation (`triangulate_face`); the tuple table handed out its stored tuples
  (7 ms for 87.5k), the array table creates them (`table_slots` + gather + `tolist` + tuples: 35 ms). A one-time cost
  per newly shown surface (≈ 3 % of its 3.1 s); a column-wise variant (`rows.T.tolist()` + `zip`) measured 24 ms, i.e.
  it would recover about a third — not applied in this run (the measured tree stays the committed one).
- Memory +7 to +11 MiB (the per-slot arrays of both stages cover every slot; container +5 to +9 MiB).

## Reading

- **Stage 2 did on the reference PC what it did in the container, a little better:** the stage evaluation −84 to
  −86 % (55.5 / 92.4 → 8.7 / 13.2 ms), row 2f −91 % (9.5 → 0.84 ms), the D3 tick −68 / −74 % (97 / 140 → 31 / 36 ms),
  the D3 frame −57 / −55 % (pose 117.8 → 50.9 ms, weight 189.2 → 85.1 ms p50).
- **O3 is complete for the D3 scenario** (stage 1 + stage 2; the SubD stencils are a separate package, and SubD is off
  at this density per D4), **and D3 is still unmet**: p95 53.9 ms (pose) and 92.4 ms (weight) against 33.3 ms. That is
  the condition of **D2** ("O4 only if O3 leaves the D3 bar unmet on the reference PC").
- **What is left, by package:**
  - pose frame: `_sync_geometry` 21.5 ms (NumPy, ≈ 80 calls per frame on 13k elements: per-call overhead), the stages
    8.7 ms, `on_draw` 19.6 ms (≈ 12 ms of it waiting for the GPU's 11.4 ms mesh draw);
  - weight frame: additionally the HUD (24.9 ms), gizmo / bones (6.7 ms) and on the GPU a whole-buffer vertex upload
    (34.2 ms vs 5.8 ms in pose rows for the same 556,940 bytes per frame).
- **For the decision [H]** (container ratios of `probe_kernels.py`, audit §E.5: native C 1.1 ms for the 15 % 1-ring
  data, 0.2 ms LBS, 0.06 ms morph against NumPy 19.5 / 3.2 / 0.63 ms; the Q9550 ratio for native code is unmeasured):
  O4 for the sync and the stages could take ≈ 25–28 ms off the 30 ms they cost now, leaving a pose frame of
  ≈ 23–28 ms — under the 33.3 ms minimum, not the 16.7 ms preferred (`on_draw` alone is ≈ 20 ms). The weight frame
  would stay over without the HUD package (≈ 25 ms) and, once the CPU is that fast, the GPU vertex-buffer upload
  (34 ms on the GPU). O4 is a tooling decision (a compiled kernel built for and shipped to Windows; no compiler is
  known on this PC) and Manu's to take.

## Raw output (as supplied; the pytest progress lines and the failing test's body shortened, marked `[...]`)

```
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> $py = (Resolve-Path .\.venv312\Scripts\python.exe).Path; & $py --version; & $py -c "import numpy; print('numpy', numpy.__version__)"
Python 3.12.10
numpy 2.2.6
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py -m pytest tests\test_stage_arrays.py tests\test_surface_positions.py tests\test_morph_multi.py tests\test_skin_stage.py tests\test_morph_picking.py tests\test_render_mesh_incremental.py tests\test_packed_geometry.py -q
.................................................................................................................................. [ 92%]
..........                                                                                                                         [100%]
140 passed in 17.39s
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py -m pytest (Get-ChildItem tests\test_gl_*.py) -q
.................................................................................................................................. [ 78%]
...................................                                                                                                [100%]
165 passed in 434.08s (0:07:14)
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py -m pytest tests -q; & $py -m pytest experiments\morph_lab\tests -q; & $py -m pytest experiments\drag_cost\tests -q
[... progress dots 1 %-72 % omitted; one F at 61 % (the failure below), skips (s) at 14 % ...]
[cost] subd_cube: n=97 median commit symmetric 6.06 ms, one-sided 3.04 ms (x1.99); p95 11.14 / 6.25 ms
.
[cost] head_basemesh: n=94 median commit symmetric 20.07 ms, one-sided 3.41 ms (x5.89); p95 33.56 / 10.01 ms
.
[cost] tie_grid: n=90 median commit symmetric 4.65 ms, one-sided 2.06 ms (x2.25); p95 7.86 / 5.04 ms
............................
[cost] head_basemesh hover (pick + plan + overlay): median/p95 plain 2.46/9.85 ms, symmetric 2.80/10.13 ms (x1.14); Intel64 Family 6 Model 23 Stepping 10, GenuineIntel, python 3.12.10, Windows 10
............................... [ 74%]
[... progress dots 74 %-100 % omitted; skips (s) at 76 %, subtests (u) at 78-79 % and 94 % ...]
=============================================================== FAILURES ================================================================
________________________________________________________ test_probe_menu_wiring _________________________________________________________

    def test_probe_menu_wiring():
        LOADED.clear()
    [... test body omitted up to the failing step ...]
        # 5) Kein Menü, solange eine Geste läuft (W gehalten).
        window, app = build(SceneMenu(scene_entries(), load=fake_load))
        h = window.handlers
        h["on_key_press"](key.W, 0)
>       assert app.interaction_owner == "transform"
E       AssertionError: assert None == 'transform'
E        +  where None = <mirai.application.Application object at 0x0000021BB20AE630>.interaction_owner

tests\test_scene_menu_local_tmp.py:145: AssertionError
======================================================== short test summary info ========================================================
FAILED tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring - AssertionError: assert None == 'transform'
1 failed, 6944 passed, 8 skipped, 66 subtests passed in 2261.52s (0:37:41)
.................................................                                                                  [100%]
49 passed in 14.80s
.....................................................................................                              [100%]
85 passed in 11.20s
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\drag_cost\probe_scale_audit.py --only split --assets dense --regions 15
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 43d0ef3585, working tree MODIFIED, src/ tree 94addddafd
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           31.34  100 %   (p95 34.39)
  1 skin evaluation (LBS + Mesh writes)              7.88   25.1 %
  2 RenderMesh._sync_geometry, total                22.89   73.0 %
  2a  neighbourhood sets                             3.15   10.1 %
  2b  face normals                                   6.56   20.9 %
  2c  vertex normals                                 4.71   15.0 %
  2d  positions + normals -> mirror -> store         5.60   17.9 %
  2e  face data -> store (O2: face normals)          1.56    5.0 %
  2f  moved -> slots, positions -> arrays (O3)       0.84    2.7 %
  4 face-data glBufferSubData at draw                0.65    2.1 %
  5 skin stage update, total (candidates + 1)        7.97   25.4 %
  6 Viewport._sync_surface, total (stages + 2)      31.00   98.9 %
  draw + glFinish                                   15.26
  bytes handed to the store per step               556940  (42 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           31.40  100 %   (p95 37.84)
  1 skin evaluation (LBS + Mesh writes)              7.85   25.0 %
  2 RenderMesh._sync_geometry, total                22.91   73.0 %
  2a  neighbourhood sets                             3.21   10.2 %
  2b  face normals                                   6.42   20.4 %
  2c  vertex normals                                 4.81   15.3 %
  2d  positions + normals -> mirror -> store         5.59   17.8 %
  2e  face data -> store (O2: face normals)          1.56    5.0 %
  2f  moved -> slots, positions -> arrays (O3)       0.84    2.7 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                0.62    2.0 %
  5 skin stage update, total (candidates + 1)        7.96   25.3 %
  6 Viewport._sync_surface, total (stages + 2)      31.01   98.8 %
  draw + glFinish                                   15.73
  bytes handed to the store per step               556940  (42 per weighted vertex)
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\drag_cost\probe_d3_acceptance.py
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit 43d0ef3585, working tree MODIFIED, src/ tree 94addddafd
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, MixSurface.update, OrientationTriad.draw, RenderMesh._read_moved, RenderMesh._read_table_moves, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, SkinSurface.update, Viewport._sync_edges, Viewport._sync_surface, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50    50.86  p95    53.85  max    57.85 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.21  p95     0.26
    tick (update_viewport)                   p50    31.11  p95    33.33
    on_draw + glFinish                       p50    19.62  p95    21.30
      tick: Viewport._sync_surface (all of it) p50    30.96  p95    33.19
      tick: stage update (candidates + eval) p50     8.84  p95    10.03
      tick: stage evaluation (mix + skin)    p50     8.72  p95     9.91
      tick: RenderMesh._sync_geometry        p50    21.51  p95    23.21
        of it: moved -> slots, positions (2f) p50     0.86  p95     1.04
        of it: face data -> store            p50     1.59  p95     2.04
      draw: viewport render (faces, wire, overlays) p50     3.39  p95     3.99
        of it: face-data upload              p50     0.78  p95     1.13
      draw: gizmo / bones                    p50     1.07  p95     1.34
      draw: HUD                              p50     1.01  p95     1.25
      draw: triad                            p50     0.39  p95     0.50
      draw: panels                           p50     1.51  p95     1.68
      draw: rest (clear, sync, GPU wait)     p50    12.10  p95    13.82
      gpu: vertex-buffer upload              p50     5.78  p95     7.47
      gpu: mesh draw (face data + shaded pass) p50    11.44  p95    16.90
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50    85.10  p95    92.37  max    95.98 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.09  p95     0.11
    tick (update_viewport)                   p50    36.04  p95    44.07
    on_draw + glFinish                       p50    48.32  p95    51.70
      tick: Viewport._sync_surface (all of it) p50    35.91  p95    43.94
      tick: stage update (candidates + eval) p50    13.34  p95    21.80
      tick: stage evaluation (mix + skin)    p50    13.21  p95    21.66
      tick: RenderMesh._sync_geometry        p50    21.58  p95    22.92
        of it: moved -> slots, positions (2f) p50     0.84  p95     0.92
        of it: face data -> store            p50     1.63  p95     2.08
      draw: viewport render (faces, wire, overlays) p50     3.26  p95     3.98
        of it: face-data upload              p50     0.75  p95     0.96
      draw: gizmo / bones                    p50     6.67  p95     7.14
      draw: HUD                              p50    24.93  p95    26.47
      draw: triad                            p50     0.46  p95     0.60
      draw: panels                           p50     1.56  p95     1.74
      draw: rest (clear, sync, GPU wait)     p50    12.26  p95    14.04
      gpu: vertex-buffer upload              p50    34.16  p95    37.34
      gpu: mesh draw (face data + shaded pass) p50    11.46  p95    47.56
    NOTE gpu mesh draw varies 11.27-49.04 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50    51.72  p95    54.48  max    80.88 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.21  p95     0.28
    tick (update_viewport)                   p50    31.39  p95    33.40
    on_draw + glFinish                       p50    20.19  p95    21.91
      tick: Viewport._sync_surface (all of it) p50    31.20  p95    33.24
      tick: stage update (candidates + eval) p50     8.55  p95     9.73
      tick: stage evaluation (mix + skin)    p50     8.43  p95     9.61
      tick: RenderMesh._sync_geometry        p50    22.40  p95    23.84
        of it: moved -> slots, positions (2f) p50     0.84  p95     0.99
        of it: face data -> store            p50     1.64  p95     1.96
      draw: viewport render (faces, wire, overlays) p50     3.99  p95     4.33
        of it: face-data upload              p50     0.78  p95     1.00
      draw: gizmo / bones                    p50     1.09  p95     1.31
      draw: HUD                              p50     1.09  p95     1.29
      draw: triad                            p50     0.27  p95     0.49
      draw: panels                           p50     1.36  p95     1.68
      draw: rest (clear, sync, GPU wait)     p50    12.55  p95    13.80
      gpu: vertex-buffer upload              p50     5.93  p95     7.66
      gpu: mesh draw (face data + shaded pass) p50    11.36  p95    17.11
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50    85.48  p95    94.26  max    95.71 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.09  p95     0.11
    tick (update_viewport)                   p50    35.98  p95    43.82
    on_draw + glFinish                       p50    49.29  p95    51.63
      tick: Viewport._sync_surface (all of it) p50    35.83  p95    43.68
      tick: stage update (candidates + eval) p50    13.32  p95    21.16
      tick: stage evaluation (mix + skin)    p50    13.19  p95    21.02
      tick: RenderMesh._sync_geometry        p50    21.54  p95    23.08
        of it: moved -> slots, positions (2f) p50     0.84  p95     0.98
        of it: face data -> store            p50     1.63  p95     1.93
      draw: viewport render (faces, wire, overlays) p50     3.72  p95     4.54
        of it: face-data upload              p50     0.77  p95     1.06
      draw: gizmo / bones                    p50     6.61  p95     6.99
      draw: HUD                              p50    24.71  p95    26.46
      draw: triad                            p50     0.47  p95     0.50
      draw: panels                           p50     1.55  p95     1.76
      draw: rest (clear, sync, GPU wait)     p50    12.64  p95    14.41
      gpu: vertex-buffer upload              p50    34.61  p95    37.47
      gpu: mesh draw (face data + shaded pass) p50    11.36  p95    46.74
    NOTE gpu mesh draw varies 11.14-48.11 ms between frames: GPU clock changes (power management) likely; compare runs with the driver set to maximum performance
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\drag_cost\probe_scale_audit.py --only chain --assets examples\meshes\gollum_20k.obj
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 43d0ef3585, working tree MODIFIED, src/ tree 94addddafd
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                2419 ms   process     162 MiB (   +113)
  save scene file                                               1750 ms   process     164 MiB (     +2)
    file size 11.7 MiB
  parse scene file (scene_from_json, no viewport)               1566 ms   process     174 MiB (    +10)
  write one target, offsets on 15 % of the points                319 ms   process     165 MiB (    -10)
  first weight step 0 -> 60 % (builds the mix surface)           798 ms   process     210 MiB (    +45)
    of it: stage evaluation 28 ms (MixSurface / SkinSurface.update), new RenderMesh 754 ms
  next weight step (patch) + frame                                13 ms   process     211 MiB (     +1)
    of it: stage evaluation 2 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            102 ms   process     211 MiB (     +0)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                      932 ms   process     229 MiB (    +18)
    of it: stage evaluation 35 ms (MixSurface / SkinSurface.update), new RenderMesh 768 ms
  next pose step (patch, morph + skin) + frame                    14 ms   process     231 MiB (     +2)
    of it: stage evaluation 4 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\drag_cost\probe_scale_audit.py --only chain --assets dense
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 43d0ef3585, working tree MODIFIED, src/ tree 94addddafd
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                                9715 ms   process     411 MiB (   +362)
  save scene file                                               6773 ms   process     415 MiB (     +4)
    file size 46.7 MiB
  parse scene file (scene_from_json, no viewport)               7570 ms   process     461 MiB (    +46)
  write one target, offsets on 15 % of the points               1389 ms   process     414 MiB (    -47)
  first weight step 0 -> 60 % (builds the mix surface)          3271 ms   process     581 MiB (   +167)
    of it: stage evaluation 119 ms (MixSurface / SkinSurface.update), new RenderMesh 3111 ms
  next weight step (patch) + frame                                32 ms   process     580 MiB (     -1)
    of it: stage evaluation 5 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            401 ms   process     585 MiB (     +6)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     3767 ms   process     630 MiB (    +45)
    of it: stage evaluation 158 ms (MixSurface / SkinSurface.update), new RenderMesh 3133 ms
  next pose step (patch, morph + skin) + frame                    42 ms   process     633 MiB (     +3)
    of it: stage evaluation 13 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
(.venv312) PS C:\Users\Manuel\Mirai_Bastel>
```
