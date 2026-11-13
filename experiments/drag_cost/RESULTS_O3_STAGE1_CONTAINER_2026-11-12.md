# O3 stage 1 before / after in the container, 2026-11-12 (audit 2026-11-10 §H step 5, first stage)

**Container numbers, not the reference PC** (`docs/architecture/REFERENCE_HARDWARE.md` §4): Intel Xeon @ 2.10 GHz,
4 logical cores, Linux, **Python 3.13.18, NumPy 2.2.6** (installed for this run instead of the container's 2.5.3, D1),
Mesa llvmpipe (software GL: draw times are CPU times, not GPU times), panels on (`imgui-bundle` 1.93.0). Change: O3
stage 1, `RenderMesh`'s derived geometry (positions, face / vertex normals, their adjacency, CPU mirrors, the hand-over
to the store) on slot-indexed NumPy arrays — [AD-032](../../docs/architecture/AD-032-PACKED-ARRAYS-NUMPY.md); report:
[audit addendum "O3 stage 1 in the container"](../../docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md#addendum--o3-stage-1-in-the-container-2026-11-12).

- "before" = `7153fae` (the probe commit: the split also times the array methods, skipped where absent; `src/` as
  `3a96ee3`, the O1 tree `559d88b8e2`), run from a git worktree, "working tree clean";
- "after" = the O3 stage 1 commit, measured on the uncommitted tree before the commit: "`7153faefa1`, working tree
  MODIFIED, src/ tree `ccd5b2a877`" — `git rev-parse <O3 commit>:src` gives the same tree id, so the measured `src/` is
  the committed one.

Order on one host, nothing else running: before 1 → (tests) → after 1 → before 2 → after 2. Each set: split, D3, chain
20k, chain 87.5k, each in its own process. Pair 2 (before 2, after 2) is back to back.

## The pose-step split, `probe_scale_audit.py --only split --assets dense --regions 15`

87.5k fixture, 15 % region = 13,125 weighted vertices, skin only (the audit's §E.3 scenario), 20 steps, p50 ms. Rows
2a–2e are the same parts before and after (before: `DerivedGeometry` dicts; after: `PackedGeometry` arrays); 2f is new
(the moved vertices' slots and positions into the arrays; before O3 that work had no method of its own and is inside
row 2 only).

| wire off | before 1 | before 2 | after 1 | after 2 |
|---|---:|---:|---:|---:|
| step (pointer_motion + update_viewport) | 117.37 | 96.98 | **35.78** | **35.89** |
| 1 skin evaluation | 31.02 | 23.48 | 21.32 | 21.28 |
| 2 `RenderMesh._sync_geometry` | 82.56 | 70.75 | **11.94** | **11.87** |
| 2a neighbourhood | 9.68 | 7.91 | 1.25 | 1.21 |
| 2b face normals | 28.09 | 25.17 | 2.62 | 2.66 |
| 2c vertex normals | 14.19 | 11.28 | 1.64 | 1.62 |
| 2d positions + normals → mirror → store | 17.71 | 14.32 | 2.08 | 2.11 |
| 2e face data → store | 8.22 | 6.99 | 0.71 | 0.71 |
| 2f ids → slots, positions → arrays | – | – | 3.22 | 3.24 |
| step p95 | 209.41 | 144.48 | 51.49 | 44.61 |
| bytes to the store per step | 556,940 | 556,940 | 556,940 | 556,940 |

With the wire on the rows are the same within 1 ms (raw outputs below); the wire costs 0 ms per step since O0.

**Reading.** `_sync_geometry` fell from 71–83 ms to 11.9 ms (≈ 6–7×); every one of its parts fell 7–14×. Its
largest part is now 2f, the per-vertex Python work that stays in stage 1: one `vertex_position` call and one dict
lookup per moved vertex (3.2 ms for 13,125 vertices). The step is now 59–60 % skin evaluation (stage 2's part). Bytes
to the store are unchanged (the same ranges, now float32 arrays instead of lists).

## D3 acceptance probe, `probe_d3_acceptance.py` (87.5k fixture, 15 % jaw region, Morph + Skin, complete frame)

p50 / p95 ms, 60 frames per row; "eval" = `MixSurface._recompute` + `SkinSurface._recompute`, "sync" =
`RenderMesh._sync_geometry` of the shown surface, "tick" = `update_viewport`, "draw" = `on_draw` + `glFinish`
(llvmpipe: the CPU rasterises).

Pair 2 (back to back):

| Row | frame before | frame after | tick before → after | eval p50 | sync p50 | face data → store p50 | draw p50 |
|---|---:|---:|---:|---:|---:|---:|---:|
| pose wire off | 139.04 / 160.63 | **79.52 / 99.36** | 99.69 → 38.30 | 25.05 → 23.48 | 71.20 → **12.25** | 7.23 → 0.74 | 39.40 → 41.02 |
| weight wire off | 169.59 / 192.19 | **107.20 / 118.54** | 120.77 → 58.81 | 42.67 → 41.48 | 72.22 → **12.19** | 7.47 → 0.73 | 48.16 → 48.02 |
| pose wire ON | 163.05 / 186.80 | **99.78 / 106.85** | 106.34 → 41.69 | 28.20 → 26.31 | 74.66 → **12.58** | 7.45 → 0.73 | 56.42 → 57.46 |
| weight wire ON | 190.10 / 233.14 | **125.60 / 139.61** | 126.99 → 60.94 | 44.83 → 42.80 | 75.76 → **12.53** | 7.69 → 0.73 | 60.97 → 62.93 |

Pair 1 (before 1 earlier on the same host, after 1): frame p50 / p95 pose wire off 180.28 / 246.18 → 79.30 / 92.90,
weight wire off 200.24 / 288.18 → 108.32 / 146.87, pose wire ON 190.92 / 257.25 → 99.19 / 116.87, weight wire ON
230.28 / 314.04 → 122.69 / 149.86; sync 79.90–91.24 → 11.87–12.59 ms.

**D3 verdict [C]: OVER** (33.3 ms p95) in every row, before and after. What remains of a frame here: the software draw
(24–47 ms on llvmpipe, the CPU rasterising — not a reference-PC cost), the stage evaluation (23–43 ms: stage 2), the
HUD in weight rows (7 ms, its own package), `_sync_geometry` 12 ms. The tick (everything but the draw) fell from
100–127 to 38–61 ms.

## One-time costs and memory, `probe_scale_audit.py --only chain`

"new RenderMesh" = the time inside `RenderMesh.__init__` of the newly shown surface (the array build and the
triangulation; before: `DerivedGeometry` dicts + flat lists). Process memory = resident set after the row.

| | 87.5k before (1 / 2) | 87.5k after (1 / 2) | 20k before (1 / 2) | 20k after (1 / 2) |
|---|---:|---:|---:|---:|
| load OBJ + scene + first frame | 5,451 / 3,745 ms | **2,736 / 2,931 ms** | 1,082 / 824 ms | **668 / 668 ms** |
| first weight step (builds the mix surface) | 2,489 / 2,171 ms | **1,030 / 1,184 ms** | 576 / 404 ms | **249 / 252 ms** |
| of it: new RenderMesh | 2,411 / 2,101 ms | **960 / 1,107 ms** | 541 / 383 ms | **226 / 229 ms** |
| process memory, change | +230 / +229 MiB | **+180 / +181 MiB** | +57 / +56 MiB | **+43 / +42 MiB** |
| first pose step (builds the skin surface) | 3,286 / 2,700 ms | **1,408 / 1,325 ms** | 502 / 517 ms | **345 / 311 ms** |
| of it: new RenderMesh | 2,963 / 2,377 ms | **1,108 / 1,003 ms** | 409 / 426 ms | **252 / 217 ms** |
| process memory, change | +178 / +180 MiB | **+168 / +169 MiB** | +68 / +66 MiB | **+63 / +62 MiB** |
| process memory after both stages | 974 / 976 MiB | **880 / 881 MiB** | 388 / 385 MiB | **369 / 367 MiB** |
| next weight / pose step, run 1; run 2 (one sample each) | 120 / 126; 116 / 153 ms | 56 / 62; 60 / 65 ms | 33 / 37; 27 / 31 ms | 15 / 16; 16 / 16 ms |

**Reading.** Building a new surface `RenderMesh` at 87.5k fell from 2.1–3.0 s to 1.0–1.1 s, loading from 3.7–5.5 to
2.7–2.9 s; process memory with both stages −95 MiB at 87.5k. What remains of a build is per-face Python work that stage 1
does not touch (triangulation, the slot layout's dicts and lists, edge slots).

## Tests (container)

- `xvfb-run -a python -m pytest tests -q`: **6,928 passed, 1 failed, 8 skipped, 66 subtests passed** (10 min 43 s). The
  failure is `tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring`, the "nicht committen" probe file that fails
  before this change too (audit §I.7); untouched. The 8 skips are the GL modules inside a combined run.
- `xvfb-run -a python -m pytest tests/test_gl_*.py -q` (own process): **165 passed** (2 min 2 s), among them
  `test_gl_face_data_layout.py` (production against the frozen pre-O2 shader, byte-identical).
- `experiments/morph_lab/tests`: **49 passed**; `experiments/drag_cost/tests`: **84 passed**.
- New `tests/test_packed_geometry.py` (16); stricter `test_render_mesh_incremental.py` (patch == rebuild bit-identical)
  and `test_render_mesh_face_data.py` (store == float32 rounding). Six hand mutations, each caught: vertex normals summed
  in another order, Newell wrapping to the wrong corner, the adjacency not written back after a patch, the adjacency
  written in set order, the last upload range dropped, the faces around moved vertices not re-triangulated.
- Pixel cross-check against the pre-O3 tree (scratch script, each tree in its own process): `head_basemesh` and
  `gollum_20k` × Smooth / Flat × perspective / ortho × two views, deformed through the patch path, 640×480, Raitt
  light — **16 of 16 scenes byte-identical** (37,831–48,316 covered pixels per scene).

## Commands for the reference PC (PowerShell, from the repo root)

*Run on 2026-11-13 (Manu): [`RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md`](RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md).*

D1: the runtime there is **Python 3.12.10 with `numpy==2.2.6`** — not the PowerShell default 3.14 (no 2.2.6 wheel, and
newer NumPy does not start on the Q9550). Before and after with the same interpreter. GPU numbers only with the NVIDIA
setting "Maximale Leistung bevorzugen" for `python.exe` ([O2 reference-PC results](RESULTS_O2_REFERENCE_PC_2026-11-11.md),
rounds 2–3). Under 3.12 with `imgui-bundle` the panels are on (the O1 / O2 reference-PC runs under 3.14 had them off).

Once — a virtual environment under Python 3.12 with everything installed (`requirements-dev.txt` includes
`requirements.txt`, i.e. `numpy==2.2.6`); `py -3.12` is the Python launcher, or use the full path of the 3.12
`python.exe`:
```
py -3.12 -m venv .venv312
```
```
$py = (Resolve-Path .\.venv312\Scripts\python.exe).Path; & $py --version; & $py -m pip install -r requirements-dev.txt
```
D1 check — the production import and execution with that NumPy (prints the versions, then the array tests):
```
& $py -c "import sys, numpy; sys.path.insert(0, 'src'); import viewport.render_mesh; print(sys.version); print('numpy', numpy.__version__, numpy.__file__)"
```
```
& $py -m pytest tests\test_packed_geometry.py tests\test_render_mesh_incremental.py tests\test_render_mesh.py tests\test_render_mesh_face_data.py -q
```
GL tests in their own process, then the rest (expect the same skip list as for O1 on Windows):
```
& $py -m pytest (Get-ChildItem tests\test_gl_*.py) -q
```
```
& $py -m pytest tests -q; & $py -m pytest experiments\morph_lab\tests -q
```
After O3 stage 1 — split, D3, chain (one asset per process; each prints the commit):
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
Before O3, from a worktree of the probe commit on the pre-O3 code, **with the same `$py`** (delete it afterwards):
```
git worktree add ..\mirai-pre-o3 7153fae
```
```
Push-Location ..\mirai-pre-o3; & $py experiments\drag_cost\probe_scale_audit.py --only split --assets dense --regions 15; & $py experiments\drag_cost\probe_d3_acceptance.py; & $py experiments\drag_cost\probe_scale_audit.py --only chain --assets examples\meshes\gollum_20k.obj; & $py experiments\drag_cost\probe_scale_audit.py --only chain --assets dense; Pop-Location
```
```
git worktree remove ..\mirai-pre-o3
```
Reference values to compare with (Python 3.14.2, panels off, so not directly): after O1 the D3 pose / weight frame was
307.45 / 375.16 ms p50 with `_sync_geometry` ≈ 221–226 ms
([RESULTS_O1_REFERENCE_PC_2026-11-12.md](RESULTS_O1_REFERENCE_PC_2026-11-12.md)); the kernel probe measured the NumPy
1-ring at 30.7 ms for 13,125 vertices on that PC (2026-11-10).

## Raw outputs

### Split, 87.5k / 15 %, before 1

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree clean
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          117.37  100 %   (p95 209.41)
  1 skin evaluation (LBS + Mesh writes)             31.02   26.4 %
  2 RenderMesh._sync_geometry, total                82.56   70.3 %
  2a  neighbourhood sets                             9.68    8.2 %
  2b  face normals                                  28.09   23.9 %
  2c  vertex normals                                14.19   12.1 %
  2d  positions + normals -> mirror -> store        17.71   15.1 %
  2e  face data -> store (O2: face normals)          8.22    7.0 %
  2f  ids -> slots, positions -> arrays (O3)            -          (no such method in this checkout)
  4 face-data glBufferSubData at draw                0.15    0.1 %
  draw + glFinish                                   45.98
  bytes handed to the store per step               556940  (42 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          110.50  100 %   (p95 183.01)
  1 skin evaluation (LBS + Mesh writes)             25.87   23.4 %
  2 RenderMesh._sync_geometry, total                81.19   73.5 %
  2a  neighbourhood sets                             8.54    7.7 %
  2b  face normals                                  25.98   23.5 %
  2c  vertex normals                                13.13   11.9 %
  2d  positions + normals -> mirror -> store        15.95   14.4 %
  2e  face data -> store (O2: face normals)          7.81    7.1 %
  2f  ids -> slots, positions -> arrays (O3)            -          (no such method in this checkout)
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                1.19    1.1 %
  draw + glFinish                                   64.98
  bytes handed to the store per step               556940  (42 per weighted vertex)
```

### Split, 87.5k / 15 %, after 1

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree MODIFIED, src/ tree ccd5b2a877
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           35.78  100 %   (p95 51.49)
  1 skin evaluation (LBS + Mesh writes)             21.32   59.6 %
  2 RenderMesh._sync_geometry, total                11.94   33.4 %
  2a  neighbourhood sets                             1.25    3.5 %
  2b  face normals                                   2.62    7.3 %
  2c  vertex normals                                 1.64    4.6 %
  2d  positions + normals -> mirror -> store         2.08    5.8 %
  2e  face data -> store (O2: face normals)          0.71    2.0 %
  2f  ids -> slots, positions -> arrays (O3)         3.22    9.0 %
  4 face-data glBufferSubData at draw                0.12    0.3 %
  draw + glFinish                                   37.30
  bytes handed to the store per step               556940  (42 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           37.31  100 %   (p95 57.86)
  1 skin evaluation (LBS + Mesh writes)             21.87   58.6 %
  2 RenderMesh._sync_geometry, total                11.95   32.0 %
  2a  neighbourhood sets                             1.22    3.3 %
  2b  face normals                                   2.59    6.9 %
  2c  vertex normals                                 1.63    4.4 %
  2d  positions + normals -> mirror -> store         2.14    5.7 %
  2e  face data -> store (O2: face normals)          0.74    2.0 %
  2f  ids -> slots, positions -> arrays (O3)         3.26    8.7 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                1.03    2.8 %
  draw + glFinish                                   57.18
  bytes handed to the store per step               556940  (42 per weighted vertex)
```

### Split, 87.5k / 15 %, before 2

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree clean
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           96.98  100 %   (p95 144.48)
  1 skin evaluation (LBS + Mesh writes)             23.48   24.2 %
  2 RenderMesh._sync_geometry, total                70.75   73.0 %
  2a  neighbourhood sets                             7.91    8.2 %
  2b  face normals                                  25.17   26.0 %
  2c  vertex normals                                11.28   11.6 %
  2d  positions + normals -> mirror -> store        14.32   14.8 %
  2e  face data -> store (O2: face normals)          6.99    7.2 %
  2f  ids -> slots, positions -> arrays (O3)            -          (no such method in this checkout)
  4 face-data glBufferSubData at draw                0.13    0.1 %
  draw + glFinish                                   36.31
  bytes handed to the store per step               556940  (42 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          101.22  100 %   (p95 131.35)
  1 skin evaluation (LBS + Mesh writes)             23.27   23.0 %
  2 RenderMesh._sync_geometry, total                74.46   73.6 %
  2a  neighbourhood sets                             7.91    7.8 %
  2b  face normals                                  24.68   24.4 %
  2c  vertex normals                                11.69   11.6 %
  2d  positions + normals -> mirror -> store        15.08   14.9 %
  2e  face data -> store (O2: face normals)          7.60    7.5 %
  2f  ids -> slots, positions -> arrays (O3)            -          (no such method in this checkout)
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                1.08    1.1 %
  draw + glFinish                                   56.77
  bytes handed to the store per step               556940  (42 per weighted vertex)
```

### Split, 87.5k / 15 %, after 2

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree MODIFIED, src/ tree ccd5b2a877
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           35.89  100 %   (p95 44.61)
  1 skin evaluation (LBS + Mesh writes)             21.28   59.3 %
  2 RenderMesh._sync_geometry, total                11.87   33.1 %
  2a  neighbourhood sets                             1.21    3.4 %
  2b  face normals                                   2.66    7.4 %
  2c  vertex normals                                 1.62    4.5 %
  2d  positions + normals -> mirror -> store         2.11    5.9 %
  2e  face data -> store (O2: face normals)          0.71    2.0 %
  2f  ids -> slots, positions -> arrays (O3)         3.24    9.0 %
  4 face-data glBufferSubData at draw                0.12    0.3 %
  draw + glFinish                                   38.16
  bytes handed to the store per step               556940  (42 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           35.52  100 %   (p95 58.69)
  1 skin evaluation (LBS + Mesh writes)             21.27   59.9 %
  2 RenderMesh._sync_geometry, total                11.62   32.7 %
  2a  neighbourhood sets                             1.27    3.6 %
  2b  face normals                                   2.64    7.4 %
  2c  vertex normals                                 1.64    4.6 %
  2d  positions + normals -> mirror -> store         2.05    5.8 %
  2e  face data -> store (O2: face normals)          0.73    2.0 %
  2f  ids -> slots, positions -> arrays (O3)         3.05    8.6 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                1.09    3.1 %
  draw + glFinish                                   54.89
  bytes handed to the store per step               556940  (42 per weighted vertex)
```

### D3, before 1

```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 7153faefa1, working tree clean
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   180.28  p95   246.18  max   307.59 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.17  p95     0.26
    tick (update_viewport)                   p50   127.55  p95   186.65
    on_draw + glFinish                       p50    47.46  p95    65.55
      tick: stage evaluation (mix + skin)    p50    33.69  p95    46.19
      tick: RenderMesh._sync_geometry        p50    91.24  p95   139.20
        of it: face data -> store            p50     8.71  p95    14.73
      draw: viewport render (faces, wire, overlays) p50    28.80  p95    46.53
        of it: face-data upload              p50     0.46  p95     0.97
      draw: gizmo / bones                    p50     0.41  p95     0.64
      draw: HUD                              p50     0.58  p95     0.90
      draw: triad                            p50     0.08  p95     0.13
      draw: panels                           p50     0.90  p95     1.77
      draw: rest (clear, sync, GPU wait)     p50    15.59  p95    20.89
      gpu: vertex-buffer upload              p50     1.08  p95     1.70
      gpu: mesh draw (face data + shaded pass) p50    45.03  p95    63.09
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   200.24  p95   288.18  max   300.54 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.07  p95     0.09
    tick (update_viewport)                   p50   141.14  p95   215.80
    on_draw + glFinish                       p50    55.79  p95    72.86
      tick: stage evaluation (mix + skin)    p50    50.50  p95    75.16
      tick: RenderMesh._sync_geometry        p50    79.90  p95   131.74
        of it: face data -> store            p50     8.43  p95    15.52
      draw: viewport render (faces, wire, overlays) p50    27.51  p95    41.31
        of it: face-data upload              p50     0.44  p95     0.79
      draw: gizmo / bones                    p50     1.85  p95     3.11
      draw: HUD                              p50     8.14  p95    14.82
      draw: triad                            p50     0.08  p95     0.14
      draw: panels                           p50     0.91  p95     1.26
      draw: rest (clear, sync, GPU wait)     p50    15.60  p95    19.83
      gpu: vertex-buffer upload              p50     1.03  p95     1.49
      gpu: mesh draw (face data + shaded pass) p50    53.56  p95    69.21
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   190.92  p95   257.25  max   267.89 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.16  p95     0.22
    tick (update_viewport)                   p50   121.51  p95   181.50
    on_draw + glFinish                       p50    64.63  p95    84.98
      tick: stage evaluation (mix + skin)    p50    31.32  p95    48.08
      tick: RenderMesh._sync_geometry        p50    86.31  p95   127.63
        of it: face data -> store            p50     8.13  p95    13.52
      draw: viewport render (faces, wire, overlays) p50    51.94  p95    75.23
        of it: face-data upload              p50     0.42  p95     0.58
      draw: gizmo / bones                    p50     0.41  p95     0.57
      draw: HUD                              p50     0.50  p95     0.67
      draw: triad                            p50     0.07  p95     0.11
      draw: panels                           p50     0.90  p95     1.34
      draw: rest (clear, sync, GPU wait)     p50    10.10  p95    16.33
      gpu: vertex-buffer upload              p50     0.98  p95     1.99
      gpu: mesh draw (face data + shaded pass) p50    56.34  p95    75.84
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   230.28  p95   314.04  max   338.62 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.07  p95     0.10
    tick (update_viewport)                   p50   155.24  p95   224.57
    on_draw + glFinish                       p50    73.82  p95    94.12
      tick: stage evaluation (mix + skin)    p50    55.71  p95    76.55
      tick: RenderMesh._sync_geometry        p50    89.92  p95   141.55
        of it: face data -> store            p50     8.62  p95    14.89
      draw: viewport render (faces, wire, overlays) p50    55.14  p95    72.27
        of it: face-data upload              p50     0.47  p95     1.12
      draw: gizmo / bones                    p50     1.94  p95     2.84
      draw: HUD                              p50     8.39  p95    12.35
      draw: triad                            p50     0.07  p95     0.14
      draw: panels                           p50     0.89  p95     1.22
      draw: rest (clear, sync, GPU wait)     p50     5.81  p95     8.30
      gpu: vertex-buffer upload              p50     1.06  p95     1.49
      gpu: mesh draw (face data + shaded pass) p50    60.75  p95    77.99
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### D3, after 1

```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 7153faefa1, working tree MODIFIED, src/ tree ccd5b2a877
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50    79.30  p95    92.90  max    98.04 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.14  p95     0.20
    tick (update_viewport)                   p50    38.06  p95    48.19
    on_draw + glFinish                       p50    40.30  p95    47.83
      tick: stage evaluation (mix + skin)    p50    23.20  p95    30.64
      tick: RenderMesh._sync_geometry        p50    11.87  p95    14.86
        of it: face data -> store            p50     0.73  p95     0.95
      draw: viewport render (faces, wire, overlays) p50    23.80  p95    30.75
        of it: face-data upload              p50     0.37  p95     0.46
      draw: gizmo / bones                    p50     0.35  p95     0.53
      draw: HUD                              p50     0.43  p95     0.60
      draw: triad                            p50     0.06  p95     0.09
      draw: panels                           p50     0.78  p95     1.08
      draw: rest (clear, sync, GPU wait)     p50    13.84  p95    16.76
      gpu: vertex-buffer upload              p50     0.79  p95     1.02
      gpu: mesh draw (face data + shaded pass) p50    38.16  p95    45.78
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   108.32  p95   146.87  max   163.56 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.09
    tick (update_viewport)                   p50    57.55  p95    86.45
    on_draw + glFinish                       p50    49.81  p95    67.34
      tick: stage evaluation (mix + skin)    p50    40.85  p95    59.81
      tick: RenderMesh._sync_geometry        p50    12.36  p95    17.71
        of it: face data -> store            p50     0.74  p95     1.05
      draw: viewport render (faces, wire, overlays) p50    24.77  p95    37.20
        of it: face-data upload              p50     0.39  p95     0.81
      draw: gizmo / bones                    p50     1.71  p95     2.72
      draw: HUD                              p50     7.29  p95    11.10
      draw: triad                            p50     0.06  p95     0.12
      draw: panels                           p50     0.82  p95     1.21
      draw: rest (clear, sync, GPU wait)     p50    14.23  p95    18.21
      gpu: vertex-buffer upload              p50     0.88  p95     1.24
      gpu: mesh draw (face data + shaded pass) p50    47.61  p95    65.03
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50    99.19  p95   116.87  max   126.62 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.14  p95     0.17
    tick (update_viewport)                   p50    40.79  p95    54.06
    on_draw + glFinish                       p50    57.39  p95    63.73
      tick: stage evaluation (mix + skin)    p50    25.49  p95    31.91
      tick: RenderMesh._sync_geometry        p50    12.38  p95    17.29
        of it: face data -> store            p50     0.74  p95     0.87
      draw: viewport render (faces, wire, overlays) p50    45.80  p95    51.22
        of it: face-data upload              p50     0.38  p95     0.57
      draw: gizmo / bones                    p50     0.37  p95     0.44
      draw: HUD                              p50     0.45  p95     0.67
      draw: triad                            p50     0.06  p95     0.10
      draw: panels                           p50     0.79  p95     1.13
      draw: rest (clear, sync, GPU wait)     p50     9.19  p95    13.29
      gpu: vertex-buffer upload              p50     0.86  p95     1.12
      gpu: mesh draw (face data + shaded pass) p50    50.91  p95    57.59
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   122.69  p95   149.86  max   190.37 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.08
    tick (update_viewport)                   p50    59.99  p95    75.76
    on_draw + glFinish                       p50    61.14  p95    78.73
      tick: stage evaluation (mix + skin)    p50    42.39  p95    57.06
      tick: RenderMesh._sync_geometry        p50    12.59  p95    17.81
        of it: face data -> store            p50     0.73  p95     1.09
      draw: viewport render (faces, wire, overlays) p50    45.78  p95    59.88
        of it: face-data upload              p50     0.38  p95     0.52
      draw: gizmo / bones                    p50     1.71  p95     2.72
      draw: HUD                              p50     7.25  p95    11.08
      draw: triad                            p50     0.07  p95     0.11
      draw: panels                           p50     0.86  p95     1.07
      draw: rest (clear, sync, GPU wait)     p50     4.88  p95     6.51
      gpu: vertex-buffer upload              p50     0.87  p95     1.54
      gpu: mesh draw (face data + shaded pass) p50    51.88  p95    65.66
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### D3, before 2

```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 7153faefa1, working tree clean
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   139.04  p95   160.63  max   207.38 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.14  p95     0.19
    tick (update_viewport)                   p50    99.69  p95   113.49
    on_draw + glFinish                       p50    39.40  p95    45.24
      tick: stage evaluation (mix + skin)    p50    25.05  p95    34.56
      tick: RenderMesh._sync_geometry        p50    71.20  p95    80.82
        of it: face data -> store            p50     7.23  p95     8.55
      draw: viewport render (faces, wire, overlays) p50    23.77  p95    27.24
        of it: face-data upload              p50     0.38  p95     0.97
      draw: gizmo / bones                    p50     0.35  p95     0.44
      draw: HUD                              p50     0.42  p95     0.57
      draw: triad                            p50     0.06  p95     0.10
      draw: panels                           p50     0.78  p95     1.01
      draw: rest (clear, sync, GPU wait)     p50    13.44  p95    17.98
      gpu: vertex-buffer upload              p50     0.89  p95     1.31
      gpu: mesh draw (face data + shaded pass) p50    37.22  p95    43.04
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   169.59  p95   192.19  max   205.05 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.08
    tick (update_viewport)                   p50   120.77  p95   138.75
    on_draw + glFinish                       p50    48.16  p95    60.46
      tick: stage evaluation (mix + skin)    p50    42.67  p95    56.12
      tick: RenderMesh._sync_geometry        p50    72.22  p95    83.94
        of it: face data -> store            p50     7.47  p95     8.74
      draw: viewport render (faces, wire, overlays) p50    24.12  p95    30.04
        of it: face-data upload              p50     0.39  p95     0.50
      draw: gizmo / bones                    p50     1.70  p95     2.59
      draw: HUD                              p50     7.03  p95    11.53
      draw: triad                            p50     0.06  p95     0.15
      draw: panels                           p50     0.80  p95     1.09
      draw: rest (clear, sync, GPU wait)     p50    14.31  p95    15.89
      gpu: vertex-buffer upload              p50     0.91  p95     1.21
      gpu: mesh draw (face data + shaded pass) p50    46.06  p95    58.62
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   163.05  p95   186.80  max   231.09 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.14  p95     0.21
    tick (update_viewport)                   p50   106.34  p95   128.20
    on_draw + glFinish                       p50    56.42  p95    66.10
      tick: stage evaluation (mix + skin)    p50    28.20  p95    41.59
      tick: RenderMesh._sync_geometry        p50    74.66  p95    87.65
        of it: face data -> store            p50     7.45  p95     9.71
      draw: viewport render (faces, wire, overlays) p50    44.99  p95    56.64
        of it: face-data upload              p50     0.38  p95     0.51
      draw: gizmo / bones                    p50     0.36  p95     0.47
      draw: HUD                              p50     0.44  p95     0.52
      draw: triad                            p50     0.06  p95     0.10
      draw: panels                           p50     0.78  p95     1.10
      draw: rest (clear, sync, GPU wait)     p50     8.76  p95    12.37
      gpu: vertex-buffer upload              p50     0.89  p95     1.06
      gpu: mesh draw (face data + shaded pass) p50    49.48  p95    57.18
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   190.10  p95   233.14  max   296.40 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.10
    tick (update_viewport)                   p50   126.99  p95   173.70
    on_draw + glFinish                       p50    60.97  p95    83.10
      tick: stage evaluation (mix + skin)    p50    44.83  p95    62.05
      tick: RenderMesh._sync_geometry        p50    75.76  p95   120.64
        of it: face data -> store            p50     7.69  p95    12.37
      draw: viewport render (faces, wire, overlays) p50    45.55  p95    68.90
        of it: face-data upload              p50     0.39  p95     0.56
      draw: gizmo / bones                    p50     1.72  p95     2.85
      draw: HUD                              p50     7.05  p95    10.77
      draw: triad                            p50     0.06  p95     0.10
      draw: panels                           p50     0.83  p95     1.01
      draw: rest (clear, sync, GPU wait)     p50     4.88  p95     6.91
      gpu: vertex-buffer upload              p50     0.89  p95     1.06
      gpu: mesh draw (face data + shaded pass) p50    51.79  p95    67.66
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### D3, after 2

```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 7153faefa1, working tree MODIFIED, src/ tree ccd5b2a877
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50    79.52  p95    99.36  max   114.23 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.13  p95     0.20
    tick (update_viewport)                   p50    38.30  p95    52.25
    on_draw + glFinish                       p50    41.02  p95    52.67
      tick: stage evaluation (mix + skin)    p50    23.48  p95    34.10
      tick: RenderMesh._sync_geometry        p50    12.25  p95    16.31
        of it: face data -> store            p50     0.74  p95     1.06
      draw: viewport render (faces, wire, overlays) p50    23.98  p95    36.20
        of it: face-data upload              p50     0.38  p95     0.74
      draw: gizmo / bones                    p50     0.36  p95     0.58
      draw: HUD                              p50     0.44  p95     0.67
      draw: triad                            p50     0.06  p95     0.11
      draw: panels                           p50     0.79  p95     1.08
      draw: rest (clear, sync, GPU wait)     p50    14.56  p95    18.25
      gpu: vertex-buffer upload              p50     0.86  p95     1.19
      gpu: mesh draw (face data + shaded pass) p50    38.84  p95    48.92
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   107.20  p95   118.54  max   151.74 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.07
    tick (update_viewport)                   p50    58.81  p95    66.09
    on_draw + glFinish                       p50    48.02  p95    52.74
      tick: stage evaluation (mix + skin)    p50    41.48  p95    47.65
      tick: RenderMesh._sync_geometry        p50    12.19  p95    14.30
        of it: face data -> store            p50     0.73  p95     0.91
      draw: viewport render (faces, wire, overlays) p50    24.27  p95    27.54
        of it: face-data upload              p50     0.38  p95     0.50
      draw: gizmo / bones                    p50     1.70  p95     2.12
      draw: HUD                              p50     7.27  p95     9.76
      draw: triad                            p50     0.07  p95     0.10
      draw: panels                           p50     0.83  p95     1.13
      draw: rest (clear, sync, GPU wait)     p50    13.29  p95    16.44
      gpu: vertex-buffer upload              p50     0.85  p95     1.08
      gpu: mesh draw (face data + shaded pass) p50    45.93  p95    50.71
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50    99.78  p95   106.85  max   145.22 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.14  p95     0.19
    tick (update_viewport)                   p50    41.69  p95    46.69
    on_draw + glFinish                       p50    57.46  p95    63.63
      tick: stage evaluation (mix + skin)    p50    26.31  p95    30.40
      tick: RenderMesh._sync_geometry        p50    12.58  p95    13.96
        of it: face data -> store            p50     0.73  p95     0.84
      draw: viewport render (faces, wire, overlays) p50    45.67  p95    54.86
        of it: face-data upload              p50     0.38  p95     0.51
      draw: gizmo / bones                    p50     0.38  p95     0.46
      draw: HUD                              p50     0.46  p95     0.60
      draw: triad                            p50     0.06  p95     0.10
      draw: panels                           p50     0.81  p95     1.01
      draw: rest (clear, sync, GPU wait)     p50     8.97  p95    12.88
      gpu: vertex-buffer upload              p50     0.85  p95     1.00
      gpu: mesh draw (face data + shaded pass) p50    51.22  p95    56.41
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   125.60  p95   139.61  max   151.52 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.08
    tick (update_viewport)                   p50    60.94  p95    69.61
    on_draw + glFinish                       p50    62.93  p95    77.41
      tick: stage evaluation (mix + skin)    p50    42.80  p95    50.16
      tick: RenderMesh._sync_geometry        p50    12.53  p95    14.74
        of it: face data -> store            p50     0.73  p95     1.11
      draw: viewport render (faces, wire, overlays) p50    46.88  p95    57.38
        of it: face-data upload              p50     0.40  p95     0.51
      draw: gizmo / bones                    p50     1.75  p95     2.61
      draw: HUD                              p50     7.36  p95    11.10
      draw: triad                            p50     0.07  p95     0.12
      draw: panels                           p50     0.85  p95     1.01
      draw: rest (clear, sync, GPU wait)     p50     4.58  p95     6.87
      gpu: vertex-buffer upload              p50     0.89  p95     1.22
      gpu: mesh draw (face data + shaded pass) p50    51.58  p95    60.13
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### Chain, 87.5k, before 1

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree clean
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                                5451 ms   process     556 MiB (   +436)
  save scene file                                               1282 ms   process     577 MiB (    +21)
    file size 44.4 MiB
  parse scene file (scene_from_json, no viewport)               4224 ms   process     603 MiB (    +26)
  write one target, offsets on 15 % of the points                 88 ms   process     563 MiB (    -40)
  first weight step 0 -> 60 % (builds the mix surface)          2489 ms   process     792 MiB (   +230)
    of it: stage evaluation 35 ms (MixSurface / SkinSurface.update), new RenderMesh 2411 ms
  next weight step (patch) + frame                               120 ms   process     793 MiB (     +1)
    of it: stage evaluation 15 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            120 ms   process     796 MiB (     +2)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     3286 ms   process     974 MiB (   +178)
    of it: stage evaluation 60 ms (MixSurface / SkinSurface.update), new RenderMesh 2963 ms
  next pose step (patch, morph + skin) + frame                   126 ms   process     974 MiB (     +0)
    of it: stage evaluation 24 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### Chain, 87.5k, after 1

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree MODIFIED, src/ tree ccd5b2a877
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                                2736 ms   process     522 MiB (   +402)
  save scene file                                                928 ms   process     544 MiB (    +22)
    file size 44.4 MiB
  parse scene file (scene_from_json, no viewport)               3480 ms   process     570 MiB (    +26)
  write one target, offsets on 15 % of the points                 85 ms   process     530 MiB (    -40)
  first weight step 0 -> 60 % (builds the mix surface)          1030 ms   process     710 MiB (   +180)
    of it: stage evaluation 33 ms (MixSurface / SkinSurface.update), new RenderMesh 960 ms
  next weight step (patch) + frame                                56 ms   process     711 MiB (     +0)
    of it: stage evaluation 15 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            109 ms   process     712 MiB (     +1)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     1408 ms   process     880 MiB (   +168)
    of it: stage evaluation 59 ms (MixSurface / SkinSurface.update), new RenderMesh 1108 ms
  next pose step (patch, morph + skin) + frame                    62 ms   process     880 MiB (     +0)
    of it: stage evaluation 22 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### Chain, 87.5k, before 2

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree clean
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                                3745 ms   process     556 MiB (   +436)
  save scene file                                                972 ms   process     577 MiB (    +21)
    file size 44.4 MiB
  parse scene file (scene_from_json, no viewport)               3940 ms   process     603 MiB (    +27)
  write one target, offsets on 15 % of the points                 89 ms   process     564 MiB (    -40)
  first weight step 0 -> 60 % (builds the mix surface)          2171 ms   process     793 MiB (   +229)
    of it: stage evaluation 34 ms (MixSurface / SkinSurface.update), new RenderMesh 2101 ms
  next weight step (patch) + frame                               116 ms   process     793 MiB (     +1)
    of it: stage evaluation 15 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            110 ms   process     796 MiB (     +3)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     2700 ms   process     976 MiB (   +180)
    of it: stage evaluation 60 ms (MixSurface / SkinSurface.update), new RenderMesh 2377 ms
  next pose step (patch, morph + skin) + frame                   153 ms   process     976 MiB (     +0)
    of it: stage evaluation 38 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### Chain, 87.5k, after 2

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree MODIFIED, src/ tree ccd5b2a877
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                                2931 ms   process     522 MiB (   +402)
  save scene file                                                967 ms   process     542 MiB (    +20)
    file size 44.4 MiB
  parse scene file (scene_from_json, no viewport)               3533 ms   process     569 MiB (    +27)
  write one target, offsets on 15 % of the points                 86 ms   process     529 MiB (    -40)
  first weight step 0 -> 60 % (builds the mix surface)          1184 ms   process     710 MiB (   +181)
    of it: stage evaluation 36 ms (MixSurface / SkinSurface.update), new RenderMesh 1107 ms
  next weight step (patch) + frame                                60 ms   process     710 MiB (     +0)
    of it: stage evaluation 16 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            111 ms   process     712 MiB (     +1)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     1325 ms   process     881 MiB (   +169)
    of it: stage evaluation 58 ms (MixSurface / SkinSurface.update), new RenderMesh 1003 ms
  next pose step (patch, morph + skin) + frame                    65 ms   process     881 MiB (     +0)
    of it: stage evaluation 24 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### Chain, 20k, before 1

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree clean
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                1082 ms   process     258 MiB (   +138)
  save scene file                                                177 ms   process     266 MiB (     +8)
    file size 11.1 MiB
  parse scene file (scene_from_json, no viewport)                762 ms   process     294 MiB (    +28)
  write one target, offsets on 15 % of the points                 20 ms   process     263 MiB (    -32)
  first weight step 0 -> 60 % (builds the mix surface)           576 ms   process     319 MiB (    +57)
    of it: stage evaluation 12 ms (MixSurface / SkinSurface.update), new RenderMesh 541 ms
  next weight step (patch) + frame                                33 ms   process     319 MiB (     +0)
    of it: stage evaluation 3 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             26 ms   process     320 MiB (     +1)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                      502 ms   process     388 MiB (    +68)
    of it: stage evaluation 16 ms (MixSurface / SkinSurface.update), new RenderMesh 409 ms
  next pose step (patch, morph + skin) + frame                    37 ms   process     388 MiB (     +0)
    of it: stage evaluation 6 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### Chain, 20k, after 1

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree MODIFIED, src/ tree ccd5b2a877
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                 668 ms   process     260 MiB (   +140)
  save scene file                                                151 ms   process     266 MiB (     +7)
    file size 11.1 MiB
  parse scene file (scene_from_json, no viewport)                649 ms   process     295 MiB (    +29)
  write one target, offsets on 15 % of the points                 20 ms   process     263 MiB (    -32)
  first weight step 0 -> 60 % (builds the mix surface)           249 ms   process     306 MiB (    +43)
    of it: stage evaluation 9 ms (MixSurface / SkinSurface.update), new RenderMesh 226 ms
  next weight step (patch) + frame                                15 ms   process     307 MiB (     +0)
    of it: stage evaluation 3 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             24 ms   process     307 MiB (     +0)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                      345 ms   process     369 MiB (    +63)
    of it: stage evaluation 15 ms (MixSurface / SkinSurface.update), new RenderMesh 252 ms
  next pose step (patch, morph + skin) + frame                    16 ms   process     369 MiB (     +0)
    of it: stage evaluation 4 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### Chain, 20k, before 2

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree clean
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                 824 ms   process     258 MiB (   +138)
  save scene file                                                134 ms   process     265 MiB (     +7)
    file size 11.1 MiB
  parse scene file (scene_from_json, no viewport)                632 ms   process     295 MiB (    +30)
  write one target, offsets on 15 % of the points                 19 ms   process     263 MiB (    -32)
  first weight step 0 -> 60 % (builds the mix surface)           404 ms   process     318 MiB (    +56)
    of it: stage evaluation 7 ms (MixSurface / SkinSurface.update), new RenderMesh 383 ms
  next weight step (patch) + frame                                27 ms   process     319 MiB (     +0)
    of it: stage evaluation 3 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             25 ms   process     319 MiB (     +0)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                      517 ms   process     385 MiB (    +66)
    of it: stage evaluation 16 ms (MixSurface / SkinSurface.update), new RenderMesh 426 ms
  next pose step (patch, morph + skin) + frame                    31 ms   process     385 MiB (     +0)
    of it: stage evaluation 4 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### Chain, 20k, after 2

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 7153faefa1, working tree MODIFIED, src/ tree ccd5b2a877
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                 668 ms   process     259 MiB (   +139)
  save scene file                                                161 ms   process     266 MiB (     +8)
    file size 11.1 MiB
  parse scene file (scene_from_json, no viewport)                729 ms   process     295 MiB (    +28)
  write one target, offsets on 15 % of the points                 23 ms   process     263 MiB (    -32)
  first weight step 0 -> 60 % (builds the mix surface)           252 ms   process     305 MiB (    +42)
    of it: stage evaluation 7 ms (MixSurface / SkinSurface.update), new RenderMesh 229 ms
  next weight step (patch) + frame                                16 ms   process     305 MiB (     +0)
    of it: stage evaluation 3 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             25 ms   process     305 MiB (     +0)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                      311 ms   process     367 MiB (    +62)
    of it: stage evaluation 15 ms (MixSurface / SkinSurface.update), new RenderMesh 217 ms
  next pose step (patch, morph + skin) + frame                    16 ms   process     367 MiB (     +0)
    of it: stage evaluation 5 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```
