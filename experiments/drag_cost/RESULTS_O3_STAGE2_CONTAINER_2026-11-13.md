# O3 stage 2 before / after in the container, 2026-11-13 (audit 2026-11-10 §H step 5, second stage)

**Container numbers, not the reference PC** (`docs/architecture/REFERENCE_HARDWARE.md` §4): Intel Xeon @ 2.10 GHz,
4 logical cores, Linux, **Python 3.13.18, NumPy 2.2.6** (installed for this run, D1), Mesa llvmpipe (software GL: draw
times are CPU times, not GPU times), panels on (`imgui-bundle` 1.93.0). Change: O3 stage 2 — the morph mix and the skin
stage evaluate on slot arrays, the O1 position table is an n×3 float64 array, its journal records writes as slot chunks,
and the surface `RenderMesh` takes the moved positions as arrays (no read per vertex) —
[AD-032 §11–§12](../../docs/architecture/AD-032-PACKED-ARRAYS-NUMPY.md#11-stage-2--design-2026-11-13); report:
[audit addendum "O3 stage 2 in the container"](../../docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md#addendum--o3-stage-2-in-the-container-2026-11-13).

- "before" = `10beee7` (the probe commit: split / D3 also time the stages' whole update, the surface sync and the array
  hand-over, skipped where absent; `src/` as main `b7bf49c`, tree `8f52936795`), run from a git worktree, "working tree
  clean";
- "after" = the O3 stage 2 commit, measured on the uncommitted tree before the commit: "`5851f35f13`, working tree
  MODIFIED, src/ tree `94addddafd`" — `git rev-parse <stage-2 commit>:src` gives the same tree id, so the measured
  `src/` is the committed one.

Order on one host, nothing else running: before 1 → (implementation, tests) → after 1 → before 2 → after 2. Each set:
split, D3, chain 20k, chain 87.5k, each in its own process. Pair 2 is back to back.

## The pose-step split, `probe_scale_audit.py --only split --assets dense --regions 15`

87.5k fixture, 15 % region = 13,125 weighted vertices, skin only (the input is the edit mesh), 20 steps, p50 ms. Row 1
is `SkinSurface._recompute`, row 5 its whole `update` (candidates + row 1), row 6 `Viewport._sync_surface` (the
stages, the hand-over, the surface `RenderMesh` sync); 2f before = `_read_moved` (one `vertex_position` and one id
lookup per moved vertex), after = `_read_table_moves` (the moved table slots through the slot map, one array copy).

| wire off | before 1 | before 2 | after 1 | after 2 |
|---|---:|---:|---:|---:|
| step (pointer_motion + update_viewport) | 45.38 | 47.95 | **18.19** | **14.38** |
| step p95 | 59.14 | 60.79 | 19.32 | 19.33 |
| 1 skin evaluation (`_recompute`) | 27.35 | 28.56 | **5.12** | **4.03** |
| 5 skin stage update, total | 27.83 | 29.00 | 5.23 | 4.12 |
| 2 `RenderMesh._sync_geometry` | 14.20 | 14.77 | 12.44 | 9.81 |
| 2a / 2b / 2c neighbourhood / face / vertex normals | 1.41 / 3.22 / 1.94 | 1.47 / 3.37 / 2.05 | 1.63 / 3.63 / 2.50 | 1.29 / 2.96 / 1.97 |
| 2d / 2e positions + normals → store / face data → store | 2.36 / 0.82 | 2.33 / 0.81 | 2.90 / 1.05 | 2.30 / 0.83 |
| 2f moved → slots, positions → arrays | 3.96 | 4.28 | **0.59** | **0.48** |
| 6 `Viewport._sync_surface`, total | 45.03 | 47.60 | 17.82 | 14.05 |
| bytes to the store per step | 556,940 | 556,940 | 556,940 | 556,940 |

Wire ON (step p50): 45.07 / 49.96 → 15.84 / 15.28 ms (raw outputs below).

**Reading.** The skin evaluation fell ≈ 6–7× (27–29 → 4–5 ms) and row 2f ≈ 8× (4.0–4.3 → 0.5–0.6 ms); the stage's
bookkeeping outside `_recompute` (row 5 − row 1) is 0.1 ms. The step is now ≈ 68 % `_sync_geometry` — rows 2a–2e,
stage 1's NumPy parts, unchanged by this stage (after 1 ran ≈ 20 % slower across all of them, the host's variation).

## D3 acceptance probe, `probe_d3_acceptance.py` (87.5k fixture, 15 % jaw region, Morph + Skin, complete frame)

p50 / p95 ms, 60 frames per row; "surface" = `Viewport._sync_surface`, "stages" = `MixSurface.update` +
`SkinSurface.update`, "eval" = their `_recompute`, "sync" = `RenderMesh._sync_geometry` of the shown surface, "2f" =
its read of the moved positions, "draw" = `on_draw` + `glFinish` (llvmpipe: the CPU rasterises).

Pair 2 (back to back):

| Row | frame before | frame after | tick before → after | stages | eval | sync | 2f | draw |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pose wire off | 108.99 / 127.66 | **58.53 / 75.72** | 56.03 → **15.03** | 36.20 → 4.07 | 35.64 → 3.97 | 16.43 → 10.45 | 5.08 → 0.49 | 48.70 → 43.12 |
| weight wire off | 132.30 / 165.39 | **71.37 / 85.55** | 76.93 → **18.84** | 59.13 → 6.87 | 55.33 → 6.76 | 15.04 → 10.76 | 4.35 → 0.48 | 54.35 → 51.44 |
| pose wire ON | 119.66 / 151.31 | **86.41 / 106.69** | 52.79 → **17.21** | 32.63 → 4.54 | 32.07 → 4.42 | 15.69 → 12.08 | 4.80 → 0.55 | 66.48 → 68.79 |
| weight wire ON | 157.31 / 189.04 | **103.21 / 133.94** | 83.99 → **22.41** | 63.51 → 8.68 | 59.47 → 8.53 | 16.00 → 13.14 | 4.91 → 0.58 | 70.84 → 78.79 |

Pair 1 (before 1 at the start of the session, after 1 after the test gate): frame p50 / p95 pose wire off 91.58 /
116.95 → 60.20 / 72.31, weight wire off 133.98 / 178.66 → 68.11 / 89.25, pose wire ON 122.51 / 151.97 → 85.25 /
100.46, weight wire ON 153.24 / 204.60 → 84.44 / 106.34; tick 46.99–78.22 → 15.53–17.99 ms; eval 28.77–54.78 →
4.26–6.59 ms.

- The tick (everything but the draw: input handling, both stages, the surface sync, overlays) fell from 47–84 ms to
  **15–22 ms p50** (p95 19–31 ms). Of it, the stages are 4–9 ms, `_sync_geometry` 10–13 ms; the rest of
  `_sync_surface` (provider bookkeeping, journal takes, set copies) fell from ≈ 3 ms to ≈ 0.3 ms.
- Bytes to the store per frame unchanged (556,940). The HUD in weight rows (7.7–10.3 ms) and the software draw
  (llvmpipe: 25–58 ms viewport render) are unchanged — not part of this stage.

**D3 verdict [C]: OVER** in every row, before and after — the frame is ≥ 58 ms because llvmpipe draws on the CPU
(43–79 ms of it). The tick alone would be within the minimum bar here (p95 19–31 ms ≤ 33.3); on the reference PC the
draw is the GPU's and the CPU parts cost ≈ 3× (stage 1 reading), so the verdict there needs the run below.

## One-time costs and memory, `probe_scale_audit.py --only chain`

One sample per row (each asset in its own process); "new RenderMesh" = the time inside `RenderMesh.__init__` of the
newly shown surface. Process memory = resident set after the row.

| | 87.5k before (1 / 2) | 87.5k after (1 / 2) | 20k before (1 / 2) | 20k after (1 / 2) |
|---|---:|---:|---:|---:|
| load OBJ + scene + first frame | 3,626 / 3,437 ms | 3,405 / 3,305 ms | 790 / 797 ms | 843 / 749 ms |
| first weight step (builds the mix surface) | 1,587 / 1,491 ms | 1,273 / 1,288 ms | 275 / 327 ms | 287 / 288 ms |
| of it: stage / new RenderMesh | 49 / 1,489; 45 / 1,398 | 51 / 1,172; 62 / 1,174 | 8 / 242; 12 / 292 | 15 / 250; 12 / 250 |
| next weight step + frame | 79 / 64 ms | **39 / 40 ms** | 26 / 21 ms | **12 / 14 ms** |
| first pose step (builds the skin surface) | 1,598 / 1,634 ms | 1,682 / 1,647 ms | 364 / 393 ms | 439 / 482 ms |
| of it: stage / new RenderMesh | 93 / 1,196; 90 / 1,249 | 114 / 1,270; 82 / 1,328 | 20 / 243; 19 / 290 | 24 / 316; 27 / 343 |
| next pose step + frame | 90 / 68 ms | **52 / 50 ms** | 24 / 21 ms | **14 / 15 ms** |
| process memory after both stages | 884 / 881 MiB | 889 / 890 MiB | 371 / 368 MiB | 373 / 372 MiB |

- Building a stage is unchanged in cost (a table reads every position once, as before; the skin's first build adds
  the posed terms of its weighted points, Python per point: `math.fsum`). The new `RenderMesh` rows scatter both ways
  (single samples); built in isolation, five times each at 20k, a new surface `RenderMesh` takes 208–252 / 211–259 ms
  (mix / skin) before and 211–285 / 218–314 ms after — the same within the host's noise.
- Memory +5–9 MiB at 87.5k: the arrays that replace dicts of tuples are smaller, but the per-slot arrays of both
  stages (the mix's base positions and offsets, the skin's posed terms ≈ 81 B per slot) cover every slot, not only the
  region.

## Tests (the gate)

| Step | Result |
|---|---|
| `xvfb-run -a python -m pytest tests -q` | **6,944 passed**, 1 failed (`test_scene_menu_local_tmp.py`, the pre-existing §I.7 file), 8 skipped (GL modules in the combined run), 66 subtests; 13 min 38 s |
| `xvfb-run -a python -m pytest tests/test_gl_*.py -q` (own process) | **165 passed** (among them `test_gl_face_data_layout.py`, the pixel gate, and the morph-picking GL tests) |
| `experiments/morph_lab/tests` | **49 passed** |
| `experiments/drag_cost/tests` | **85 passed** (one new: row 2f / stage update / surface sync are timed) |

New: `tests/test_stage_arrays.py` (13): the journal against a per-vertex reference through 300 random writes, topology
edits, takes and watches; `slot_moves()` only for pure moves; a chunk resolving to its own vertices after its slot is
reused; first record wins by id; a watch nobody takes stays O(table); `MovedVertices`; signed zeros and `fsum` bit for
bit (what `==` cannot see); the skin mirroring the mix's slots and a `RenderMesh` over it equal to a fresh build through
80 random steps (×4 seeds) with no `vertex_position` / `_read_moved` in pure-move syncs and consistent slot maps; faces
the host never reported still patched; through the app, a pose step and a weight step with zero per-vertex reads.
Unchanged and passing: the oracles `test_morph_multi.py`, `test_skin_stage.py` (bit-identical to `evaluate`),
`test_surface_positions.py` (one assertion re-pointed from `_pos` to `slot_count`), picking / hover on the mix,
`test_render_mesh_incremental.py` (patch == full rebuild).

**Hand mutations** (each applied alone, the five stage / table test files run): caught 13 of 14 — the mix's terms in
descending `LayerId` order, its first term added to 0.0, a freed slot keeping its offsets; the skin's `c` by a running
sum, its weight applied before the translation, posed-set changes not rebuilding the terms, a new vertex on its own
free slot instead of the mix's; the journal's last record by id winning, `slot_moves()` ignoring element records, no
copy-on-write of the slot list; the `RenderMesh` keeping a removed vertex's map entry, not re-triangulating after table
moves, not mapping an added vertex. Not caught (by construction): `slot_moves()` without its mapping check — a mapping
change always records by id in every watch, so the check is a second guard.

## Commands for the reference PC (PowerShell, from the repo root)

*Run on 2026-11-13 (Manu; the "after" commands, compared with the stage-1 run of the same day):
[`RESULTS_O3_STAGE2_REFERENCE_PC_2026-11-13.md`](RESULTS_O3_STAGE2_REFERENCE_PC_2026-11-13.md).*

D1: **Python 3.12.10 with `numpy==2.2.6`** in `.venv312` (as for stage 1; not the PowerShell default 3.14). Before
and after with the same interpreter. GPU numbers only with the NVIDIA setting "Maximale Leistung bevorzugen" for
`python.exe`.
```
$py = (Resolve-Path .\.venv312\Scripts\python.exe).Path; & $py --version; & $py -c "import numpy; print('numpy', numpy.__version__)"
```
The stage-2 tests and the oracles, then the GL tests in their own process, then the rest:
```
& $py -m pytest tests\test_stage_arrays.py tests\test_surface_positions.py tests\test_morph_multi.py tests\test_skin_stage.py tests\test_morph_picking.py tests\test_render_mesh_incremental.py tests\test_packed_geometry.py -q
```
```
& $py -m pytest (Get-ChildItem tests\test_gl_*.py) -q
```
```
& $py -m pytest tests -q; & $py -m pytest experiments\morph_lab\tests -q; & $py -m pytest experiments\drag_cost\tests -q
```
After O3 stage 2 — split, D3, chain (one asset per process; each prints the commit):
```
& $py experiments\drag_cost\probe_scale_audit.py --only split --assets dense --regions 15
```
```
& $py experiments\drag_cost\probe_d3_acceptance.py
```
```
& $py experiments\drag_cost\probe_scale_audit.py --only chain --assets examples\meshes\gollum_20k.obj
```
```
& $py experiments\drag_cost\probe_scale_audit.py --only chain --assets dense
```
Before stage 2, from a worktree of the probe commit on the stage-1 code, **with the same `$py`** (delete it
afterwards):
```
git worktree add ..\mirai-pre-o3s2 10beee7
```
```
Push-Location ..\mirai-pre-o3s2; & $py experiments\drag_cost\probe_scale_audit.py --only split --assets dense --regions 15; & $py experiments\drag_cost\probe_d3_acceptance.py; & $py experiments\drag_cost\probe_scale_audit.py --only chain --assets examples\meshes\gollum_20k.obj; & $py experiments\drag_cost\probe_scale_audit.py --only chain --assets dense; Pop-Location
```
```
git worktree remove ..\mirai-pre-o3s2
```
Reference values (stage 1 on that PC, 2026-11-13): D3 frame p50 / p95 pose 117.77 / 122.87, weight 189.17 / 199.91 ms;
stage evaluation 55.5 / 92.4 ms; `_sync_geometry` 32.8 ms with row 2f 9.50 ms
([RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md](RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md)).

## Raw outputs (pair 2)

### before 2 — split
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 10beee76c6, working tree clean
Platform: Linux-6.18.44-fc-v445-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           47.95  100 %   (p95 60.79)
  1 skin evaluation (LBS + Mesh writes)             28.56   59.6 %
  2 RenderMesh._sync_geometry, total                14.77   30.8 %
  2a  neighbourhood sets                             1.47    3.1 %
  2b  face normals                                   3.37    7.0 %
  2c  vertex normals                                 2.05    4.3 %
  2d  positions + normals -> mirror -> store         2.33    4.9 %
  2e  face data -> store (O2: face normals)          0.81    1.7 %
  2f  moved -> slots, positions -> arrays (O3)       4.28    8.9 %
  4 face-data glBufferSubData at draw                0.14    0.3 %
  5 skin stage update, total (candidates + 1)       29.00   60.5 %
  6 Viewport._sync_surface, total (stages + 2)      47.60   99.3 %
  draw + glFinish                                   37.83
  bytes handed to the store per step               556940  (42 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           49.96  100 %   (p95 63.50)
  1 skin evaluation (LBS + Mesh writes)             30.02   60.1 %
  2 RenderMesh._sync_geometry, total                16.47   33.0 %
  2a  neighbourhood sets                             1.75    3.5 %
  2b  face normals                                   3.70    7.4 %
  2c  vertex normals                                 2.42    4.8 %
  2d  positions + normals -> mirror -> store         2.77    5.6 %
  2e  face data -> store (O2: face normals)          0.94    1.9 %
  2f  moved -> slots, positions -> arrays (O3)       4.85    9.7 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                1.37    2.7 %
  5 skin stage update, total (candidates + 1)       30.60   61.3 %
  6 Viewport._sync_surface, total (stages + 2)      49.54   99.1 %
  draw + glFinish                                   67.17
  bytes handed to the store per step               556940  (42 per weighted vertex)
```

### after 2 — split
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 5851f35f13, working tree MODIFIED, src/ tree 94addddafd
Platform: Linux-6.18.44-fc-v445-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           14.38  100 %   (p95 19.33)
  1 skin evaluation (LBS + Mesh writes)              4.03   28.0 %
  2 RenderMesh._sync_geometry, total                 9.81   68.2 %
  2a  neighbourhood sets                             1.29    8.9 %
  2b  face normals                                   2.96   20.6 %
  2c  vertex normals                                 1.97   13.7 %
  2d  positions + normals -> mirror -> store         2.30   16.0 %
  2e  face data -> store (O2: face normals)          0.83    5.7 %
  2f  moved -> slots, positions -> arrays (O3)       0.48    3.3 %
  4 face-data glBufferSubData at draw                0.14    0.9 %
  5 skin stage update, total (candidates + 1)        4.12   28.6 %
  6 Viewport._sync_surface, total (stages + 2)      14.05   97.7 %
  draw + glFinish                                   39.64
  bytes handed to the store per step               556940  (42 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           15.28  100 %   (p95 19.34)
  1 skin evaluation (LBS + Mesh writes)              4.20   27.5 %
  2 RenderMesh._sync_geometry, total                10.41   68.1 %
  2a  neighbourhood sets                             1.34    8.8 %
  2b  face normals                                   3.25   21.3 %
  2c  vertex normals                                 2.07   13.6 %
  2d  positions + normals -> mirror -> store         2.38   15.6 %
  2e  face data -> store (O2: face normals)          0.88    5.8 %
  2f  moved -> slots, positions -> arrays (O3)       0.50    3.3 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                1.45    9.5 %
  5 skin stage update, total (candidates + 1)        4.29   28.1 %
  6 Viewport._sync_surface, total (stages + 2)      14.91   97.6 %
  draw + glFinish                                   59.89
  bytes handed to the store per step               556940  (42 per weighted vertex)
```

### before 2 — D3
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v445-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 10beee76c6, working tree clean
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, MixSurface.update, OrientationTriad.draw, RenderMesh._read_moved, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, SkinSurface.update, Viewport._sync_edges, Viewport._sync_surface, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   108.99  p95   127.66  max   153.97 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.22  p95     0.36
    tick (update_viewport)                   p50    56.03  p95    71.97
    on_draw + glFinish                       p50    48.70  p95    56.84
      tick: Viewport._sync_surface (all of it) p50    55.89  p95    71.79
      tick: stage update (candidates + eval) p50    36.20  p95    46.70
      tick: stage evaluation (mix + skin)    p50    35.64  p95    46.13
      tick: RenderMesh._sync_geometry        p50    16.43  p95    22.75
        of it: moved -> slots, positions (2f) p50     5.08  p95     8.81
        of it: face data -> store            p50     0.97  p95     1.25
      draw: viewport render (faces, wire, overlays) p50    31.32  p95    36.23
        of it: face-data upload              p50     0.57  p95     0.73
      draw: gizmo / bones                    p50     0.55  p95     0.91
      draw: HUD                              p50     0.58  p95     0.81
      draw: triad                            p50     0.09  p95     0.17
      draw: panels                           p50     1.16  p95     1.45
      draw: rest (clear, sync, GPU wait)     p50    16.06  p95    19.61
      gpu: vertex-buffer upload              p50     1.21  p95     1.61
      gpu: mesh draw (face data + shaded pass) p50    45.52  p95    53.11
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   132.30  p95   165.39  max   198.32 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.09  p95     0.13
    tick (update_viewport)                   p50    76.93  p95   105.23
    on_draw + glFinish                       p50    54.35  p95    74.90
      tick: Viewport._sync_surface (all of it) p50    76.80  p95   105.09
      tick: stage update (candidates + eval) p50    59.13  p95    80.37
      tick: stage evaluation (mix + skin)    p50    55.33  p95    75.18
      tick: RenderMesh._sync_geometry        p50    15.04  p95    20.54
        of it: moved -> slots, positions (2f) p50     4.35  p95     6.35
        of it: face data -> store            p50     0.93  p95     1.20
      draw: viewport render (faces, wire, overlays) p50    27.03  p95    37.39
        of it: face-data upload              p50     0.56  p95     1.09
      draw: gizmo / bones                    p50     1.93  p95     2.73
      draw: HUD                              p50     8.71  p95    12.29
      draw: triad                            p50     0.08  p95     0.16
      draw: panels                           p50     1.07  p95     1.44
      draw: rest (clear, sync, GPU wait)     p50    15.23  p95    19.12
      gpu: vertex-buffer upload              p50     1.21  p95     1.75
      gpu: mesh draw (face data + shaded pass) p50    51.48  p95    71.26
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   119.66  p95   151.31  max   155.17 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.22  p95     0.30
    tick (update_viewport)                   p50    52.79  p95    70.90
    on_draw + glFinish                       p50    66.48  p95    80.26
      tick: Viewport._sync_surface (all of it) p50    52.59  p95    70.72
      tick: stage update (candidates + eval) p50    32.63  p95    45.64
      tick: stage evaluation (mix + skin)    p50    32.07  p95    45.05
      tick: RenderMesh._sync_geometry        p50    15.69  p95    21.00
        of it: moved -> slots, positions (2f) p50     4.80  p95     7.59
        of it: face data -> store            p50     0.89  p95     1.18
      draw: viewport render (faces, wire, overlays) p50    52.67  p95    69.09
        of it: face-data upload              p50     0.52  p95     0.95
      draw: gizmo / bones                    p50     0.54  p95     0.86
      draw: HUD                              p50     0.61  p95     0.94
      draw: triad                            p50     0.09  p95     0.15
      draw: panels                           p50     1.11  p95     1.39
      draw: rest (clear, sync, GPU wait)     p50     9.76  p95    15.37
      gpu: vertex-buffer upload              p50     1.16  p95     1.89
      gpu: mesh draw (face data + shaded pass) p50    57.64  p95    72.19
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   157.31  p95   189.04  max   221.34 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.08  p95     0.11
    tick (update_viewport)                   p50    83.99  p95   109.04
    on_draw + glFinish                       p50    70.84  p95    88.81
      tick: Viewport._sync_surface (all of it) p50    83.86  p95   108.86
      tick: stage update (candidates + eval) p50    63.51  p95    85.17
      tick: stage evaluation (mix + skin)    p50    59.47  p95    79.32
      tick: RenderMesh._sync_geometry        p50    16.00  p95    21.40
        of it: moved -> slots, positions (2f) p50     4.91  p95     8.23
        of it: face data -> store            p50     0.88  p95     1.26
      draw: viewport render (faces, wire, overlays) p50    52.15  p95    66.72
        of it: face-data upload              p50     0.55  p95     0.96
      draw: gizmo / bones                    p50     2.09  p95     2.95
      draw: HUD                              p50     8.69  p95    12.16
      draw: triad                            p50     0.09  p95     0.15
      draw: panels                           p50     1.07  p95     1.40
      draw: rest (clear, sync, GPU wait)     p50     5.86  p95     8.02
      gpu: vertex-buffer upload              p50     1.19  p95     1.57
      gpu: mesh draw (face data + shaded pass) p50    57.36  p95    68.31
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### after 2 — D3
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v445-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 5851f35f13, working tree MODIFIED, src/ tree 94addddafd
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, MixSurface.update, OrientationTriad.draw, RenderMesh._read_moved, RenderMesh._read_table_moves, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, SkinSurface.update, Viewport._sync_edges, Viewport._sync_surface, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50    58.53  p95    75.72  max    80.73 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.19  p95     0.27
    tick (update_viewport)                   p50    15.03  p95    19.40
    on_draw + glFinish                       p50    43.12  p95    55.97
      tick: Viewport._sync_surface (all of it) p50    14.86  p95    19.23
      tick: stage update (candidates + eval) p50     4.07  p95     5.89
      tick: stage evaluation (mix + skin)    p50     3.97  p95     5.77
      tick: RenderMesh._sync_geometry        p50    10.45  p95    13.20
        of it: moved -> slots, positions (2f) p50     0.49  p95     0.66
        of it: face data -> store            p50     0.84  p95     1.20
      draw: viewport render (faces, wire, overlays) p50    25.52  p95    37.39
        of it: face-data upload              p50     0.49  p95     0.65
      draw: gizmo / bones                    p50     0.49  p95     0.70
      draw: HUD                              p50     0.54  p95     0.73
      draw: triad                            p50     0.08  p95     0.14
      draw: panels                           p50     0.93  p95     1.33
      draw: rest (clear, sync, GPU wait)     p50    14.59  p95    18.23
      gpu: vertex-buffer upload              p50     1.13  p95     2.06
      gpu: mesh draw (face data + shaded pass) p50    40.44  p95    52.34
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50    71.37  p95    85.55  max    90.54 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.08  p95     0.13
    tick (update_viewport)                   p50    18.84  p95    24.19
    on_draw + glFinish                       p50    51.44  p95    64.43
      tick: Viewport._sync_surface (all of it) p50    18.72  p95    24.06
      tick: stage update (candidates + eval) p50     6.87  p95    10.20
      tick: stage evaluation (mix + skin)    p50     6.76  p95    10.09
      tick: RenderMesh._sync_geometry        p50    10.76  p95    14.57
        of it: moved -> slots, positions (2f) p50     0.48  p95     0.66
        of it: face data -> store            p50     0.86  p95     1.17
      draw: viewport render (faces, wire, overlays) p50    26.12  p95    33.95
        of it: face-data upload              p50     0.52  p95     1.11
      draw: gizmo / bones                    p50     1.88  p95     2.60
      draw: HUD                              p50     7.74  p95    12.21
      draw: triad                            p50     0.07  p95     0.12
      draw: panels                           p50     0.96  p95     1.25
      draw: rest (clear, sync, GPU wait)     p50    14.99  p95    18.01
      gpu: vertex-buffer upload              p50     1.15  p95     1.67
      gpu: mesh draw (face data + shaded pass) p50    48.83  p95    61.67
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50    86.41  p95   106.69  max   110.17 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.21  p95     0.31
    tick (update_viewport)                   p50    17.21  p95    23.63
    on_draw + glFinish                       p50    68.79  p95    86.44
      tick: Viewport._sync_surface (all of it) p50    17.02  p95    23.33
      tick: stage update (candidates + eval) p50     4.54  p95     6.47
      tick: stage evaluation (mix + skin)    p50     4.42  p95     6.31
      tick: RenderMesh._sync_geometry        p50    12.08  p95    15.94
        of it: moved -> slots, positions (2f) p50     0.55  p95     0.76
        of it: face data -> store            p50     0.96  p95     1.29
      draw: viewport render (faces, wire, overlays) p50    54.40  p95    72.65
        of it: face-data upload              p50     0.53  p95     0.75
      draw: gizmo / bones                    p50     0.57  p95     0.73
      draw: HUD                              p50     0.63  p95     0.85
      draw: triad                            p50     0.10  p95     0.19
      draw: panels                           p50     1.14  p95     1.51
      draw: rest (clear, sync, GPU wait)     p50     8.90  p95    16.70
      gpu: vertex-buffer upload              p50     1.17  p95     1.72
      gpu: mesh draw (face data + shaded pass) p50    60.02  p95    75.64
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   103.21  p95   133.94  max   144.43 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.09  p95     0.14
    tick (update_viewport)                   p50    22.41  p95    30.52
    on_draw + glFinish                       p50    78.79  p95   108.08
      tick: Viewport._sync_surface (all of it) p50    22.25  p95    30.32
      tick: stage update (candidates + eval) p50     8.68  p95    12.01
      tick: stage evaluation (mix + skin)    p50     8.53  p95    11.76
      tick: RenderMesh._sync_geometry        p50    13.14  p95    17.54
        of it: moved -> slots, positions (2f) p50     0.58  p95     0.79
        of it: face data -> store            p50     1.09  p95     1.47
      draw: viewport render (faces, wire, overlays) p50    58.17  p95    82.64
        of it: face-data upload              p50     0.58  p95     1.09
      draw: gizmo / bones                    p50     2.44  p95     3.56
      draw: HUD                              p50    10.25  p95    15.14
      draw: triad                            p50     0.10  p95     0.18
      draw: panels                           p50     1.11  p95     1.85
      draw: rest (clear, sync, GPU wait)     p50     6.26  p95     8.75
      gpu: vertex-buffer upload              p50     1.27  p95     1.92
      gpu: mesh draw (face data + shaded pass) p50    63.81  p95    78.51
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### before 2 — chain 20k
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 10beee76c6, working tree clean
Platform: Linux-6.18.44-fc-v445-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                 797 ms   process     259 MiB (   +139)
  save scene file                                                136 ms   process     266 MiB (     +8)
    file size 11.1 MiB
  parse scene file (scene_from_json, no viewport)                774 ms   process     295 MiB (    +28)
  write one target, offsets on 15 % of the points                 22 ms   process     262 MiB (    -33)
  first weight step 0 -> 60 % (builds the mix surface)           327 ms   process     306 MiB (    +44)
    of it: stage evaluation 12 ms (MixSurface / SkinSurface.update), new RenderMesh 292 ms
  next weight step (patch) + frame                                21 ms   process     307 MiB (     +0)
    of it: stage evaluation 5 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             42 ms   process     307 MiB (     +0)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                      393 ms   process     368 MiB (    +61)
    of it: stage evaluation 19 ms (MixSurface / SkinSurface.update), new RenderMesh 290 ms
  next pose step (patch, morph + skin) + frame                    21 ms   process     368 MiB (     +0)
    of it: stage evaluation 6 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### after 2 — chain 20k
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 5851f35f13, working tree MODIFIED, src/ tree 94addddafd
Platform: Linux-6.18.44-fc-v445-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                 749 ms   process     259 MiB (   +139)
  save scene file                                                185 ms   process     266 MiB (     +8)
    file size 11.1 MiB
  parse scene file (scene_from_json, no viewport)                861 ms   process     295 MiB (    +29)
  write one target, offsets on 15 % of the points                 24 ms   process     263 MiB (    -32)
  first weight step 0 -> 60 % (builds the mix surface)           288 ms   process     307 MiB (    +44)
    of it: stage evaluation 12 ms (MixSurface / SkinSurface.update), new RenderMesh 250 ms
  next weight step (patch) + frame                                14 ms   process     307 MiB (     +0)
    of it: stage evaluation 1 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             27 ms   process     307 MiB (     +0)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                      482 ms   process     372 MiB (    +65)
    of it: stage evaluation 27 ms (MixSurface / SkinSurface.update), new RenderMesh 343 ms
  next pose step (patch, morph + skin) + frame                    15 ms   process     372 MiB (     +0)
    of it: stage evaluation 2 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### before 2 — chain 87.5k
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 10beee76c6, working tree clean
Platform: Linux-6.18.44-fc-v445-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                                3437 ms   process     523 MiB (   +403)
  save scene file                                               1111 ms   process     544 MiB (    +21)
    file size 44.4 MiB
  parse scene file (scene_from_json, no viewport)               4366 ms   process     569 MiB (    +25)
  write one target, offsets on 15 % of the points                 91 ms   process     529 MiB (    -40)
  first weight step 0 -> 60 % (builds the mix surface)          1491 ms   process     710 MiB (   +180)
    of it: stage evaluation 45 ms (MixSurface / SkinSurface.update), new RenderMesh 1398 ms
  next weight step (patch) + frame                                64 ms   process     709 MiB (     -1)
    of it: stage evaluation 18 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            129 ms   process     712 MiB (     +3)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     1634 ms   process     881 MiB (   +169)
    of it: stage evaluation 90 ms (MixSurface / SkinSurface.update), new RenderMesh 1249 ms
  next pose step (patch, morph + skin) + frame                    68 ms   process     881 MiB (     +0)
    of it: stage evaluation 27 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### after 2 — chain 87.5k
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 5851f35f13, working tree MODIFIED, src/ tree 94addddafd
Platform: Linux-6.18.44-fc-v445-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                                3305 ms   process     524 MiB (   +404)
  save scene file                                               1127 ms   process     543 MiB (    +20)
    file size 44.4 MiB
  parse scene file (scene_from_json, no viewport)               4602 ms   process     570 MiB (    +27)
  write one target, offsets on 15 % of the points                125 ms   process     531 MiB (    -40)
  first weight step 0 -> 60 % (builds the mix surface)          1288 ms   process     713 MiB (   +182)
    of it: stage evaluation 62 ms (MixSurface / SkinSurface.update), new RenderMesh 1174 ms
  next weight step (patch) + frame                                40 ms   process     713 MiB (     +0)
    of it: stage evaluation 4 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            178 ms   process     716 MiB (     +3)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     1647 ms   process     890 MiB (   +174)
    of it: stage evaluation 82 ms (MixSurface / SkinSurface.update), new RenderMesh 1328 ms
  next pose step (patch, morph + skin) + frame                    50 ms   process     890 MiB (     +0)
    of it: stage evaluation 7 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```
