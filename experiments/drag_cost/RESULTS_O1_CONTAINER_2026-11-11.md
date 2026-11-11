# O1 before / after in the container, 2026-11-11 (audit 2026-11-10 §H step 4, second half)

**Container numbers, not the reference PC** (`docs/architecture/REFERENCE_HARDWARE.md` §4): Intel Xeon @ 2.10 GHz,
4 logical cores, Linux, Python 3.13.18, Mesa llvmpipe (software GL: draw times are CPU times, not GPU times), panels on
(`imgui-bundle` 1.93.0). Change: O1, the morph mix and the skin stage hold their result as a position table over the
base's topology (`mirai.surface_positions.SurfacePositions`) instead of a `core.Mesh` copy —
[AD-025 §18](../../docs/architecture/AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md#18-addendum-2026-11-11-the-evaluated-surface-as-a-position-table-audit-o1);
report: [audit addendum "O1 in the container"](../../docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md#addendum--o1-in-the-container-2026-11-11).

- "before" = `830f62e` (the probe commit: `probe_scale_audit.py` prints the source state and splits the one-time rows;
  `src/` as `61f6a1a`, the O2 base), run from a git worktree, "working tree clean";
- "after" = the O1 commit, measured on the uncommitted tree before the commit: "`830f62e`, working tree MODIFIED, src/
  tree `559d88b8e2`" — `git rev-parse <O1 commit>:src` gives the same tree id, so the measured `src/` is the
  committed one;
- "array" = a control, not committed: the same O1 change with the table as one `array('d')` of three float64 per slot
  (src/ tree `b2155cfdcc`), for the layout choice in AD-025 §18.

All runs back to back on one host (chain: before, after per asset; D3 pair 1: before, after, array; pair 2 in the reverse
order: after, before, array), nothing else running. Each chain asset in its own process (clean memory totals).

## One-time costs and memory, `probe_scale_audit.py --only chain`

"of it" = the time inside `MixSurface.update` / `SkinSurface.update` (the stage builds its surface on the first call)
and inside `RenderMesh.__init__` (the newly shown surface gets the viewport's derived data — not part of O1). Process
memory = resident set after the row.

| | 87.5k before | 87.5k after | 20k before | 20k after |
|---|---:|---:|---:|---:|
| first weight step 0 → 60 % (builds the mix surface) | 5,765 ms | **2,354 ms** | 1,164 ms | **420 ms** |
| of it: stage evaluation | 3,225 ms | **37 ms** | 751 ms | **7 ms** |
| of it: new RenderMesh | 2,502 ms | 2,280 ms | 399 ms | 395 ms |
| process memory, change | +427 MiB | **+230 MiB** | +102 MiB | **+55 MiB** |
| first pose step (builds the skin surface) | 5,645 ms | **3,003 ms** | 1,403 ms | **468 ms** |
| of it: stage evaluation | 3,650 ms | **92 ms** | 858 ms | **15 ms** |
| of it: new RenderMesh | 1,746 ms | 2,641 ms | 467 ms | 382 ms |
| process memory, change | +417 MiB | **+177 MiB** | +124 MiB | **+66 MiB** |
| process memory after both stages | 1,411 MiB | **974 MiB** | 493 MiB | **384 MiB** |
| load OBJ + scene + first frame | 4,984 ms | 4,478 ms | 851 ms | 1,004 ms |
| next weight step / next pose step (one sample each) | 129 / 130 ms | 117 / 195 ms | 32 / 31 ms | 29 / 31 ms |

**Reading.** Building a stage's surface fell from 3.2–3.7 s to 0.04–0.09 s at 87.5k (≈ 40–100×); the stage's share of
the process memory fell by ≈ 200–240 MiB per stage, 437 MiB with both (−31 % of the process). What remains of a first
step is the new surface `RenderMesh` (1.7–2.6 s, ≈ 190 MiB at 87.5k — audit §C.3), which O1 does not touch: the
audit's "+454–488 MiB and 6–7 s per stage" counted it in. Load, save and parse are unchanged (they never built a stage).
The "next step" rows are single samples (the 195 ms is one frame); the D3 rows below are the statistic.

## D3 acceptance probe, `probe_d3_acceptance.py` (87.5k fixture, 15 % jaw region, Morph + Skin, complete frame)

p50 / p95 ms; "eval" = `MixSurface._recompute` + `SkinSurface._recompute` (incl. the table writes and the journal),
"sync" = `RenderMesh._sync_geometry` of the shown surface, "tick" = `update_viewport`.

Pair 1 (before, after, array):

| Row | frame before | frame after | eval p50 | sync p50 | sync p50, array | tick p50 |
|---|---:|---:|---:|---:|---:|---:|
| pose wire off | 156.25 / 199.36 | **154.08 / 170.71** | 30.66 → **28.03** | 78.73 → 77.89 | 85.69 | 113.64 → 109.54 |
| weight wire off | 197.51 / 243.58 | **178.94 / 212.36** | 55.53 → **45.32** | 80.90 → 77.09 | 89.33 | 144.86 → 129.09 |
| pose wire ON | 183.88 / 235.30 | **172.87 / 221.65** | 32.53 → **29.46** | 82.61 → 80.72 | 89.77 | 118.91 → 113.83 |
| weight wire ON | 215.92 / 276.78 | **205.93 / 264.48** | 56.17 → **48.28** | 81.21 → 79.89 | 91.13 | 146.81 → 136.16 |

Pair 2 (after, before, array — the reverse order):

| Row | frame before | frame after | eval p50 | sync p50 | sync p50, array | tick p50 |
|---|---:|---:|---:|---:|---:|---:|
| pose wire off | 152.64 / 211.27 | **157.28 / 218.65** | 30.38 → **28.54** | 76.56 → 80.15 | 87.16 | 110.85 → 113.03 |
| weight wire off | 196.23 / 233.00 | **184.00 / 226.17** | 56.09 → **46.09** | 80.06 → 77.66 | 86.95 | 144.45 → 129.36 |
| pose wire ON | 194.33 / 253.20 | **184.78 / 261.39** | 34.95 → **31.91** | 89.83 → 84.61 | 90.92 | 132.18 → 121.31 |
| weight wire ON | 211.64 / 245.49 | **203.06 / 252.24** | 56.73 → **49.21** | 83.02 → 81.04 | 89.58 | 145.86 → 137.82 |

Bytes to the GL store per frame: 556,940 in every row (O1 changes no upload).

**Reading.** The stage evaluation of a weight frame fell by 8–10 ms p50 (≈ 15–18 %: the mix and the skin each wrote
13,125 points through a second `Mesh` and its journals), of a pose frame by 2–3 ms (≈ 8 %); the weight frames are
12–19 ms (wire off) and 8–10 ms (wire on) faster at p50 in both pairs, the pose frames are within the noise (−11 to
+5 ms). `_sync_geometry` is unchanged: the surface `RenderMesh` reads the table as fast as it read the `Mesh`.
With the `array('d')` table it is 7–10 ms slower in every row (three float objects and a tuple per read, ≈ 5 reads per
moved vertex) — more than the evaluation gains; hence the tuple table. Every row stays **OVER** the D3 bar (33.3 ms p95)
before and after, as expected for O1 alone: the frame is still the per-vertex Python work in the viewport (normals,
neighbourhood sets, mirrors: ≈ 80 ms) and the stage arithmetic (≈ 28–49 ms) — O3. Frame-to-frame noise in this
container stays large (p95 / p50 ≈ 1.1–1.4; the same row moves by 10 ms between pairs).

## Tests (container)

- `xvfb-run -a python -m pytest tests -q`: **6,912 passed, 1 failed, 8 skipped, 66 subtests passed** (12 min 31 s). The
  failure is `tests/test_scene_menu_local_tmp.py::test_probe_menu_wiring`, the "nicht committen" probe file that fails
  before this change too (audit §B, §I.7); untouched. The 8 skips are the GL modules inside a combined run.
- `xvfb-run -a python -m pytest tests/test_gl_*.py -q` (own process): **165 passed** (2 min 7 s), among them
  `test_gl_face_data_layout.py`, `test_gl_morph_picking.py`, `test_gl_region_tint.py`.
- `experiments/morph_lab/tests`: **49 passed**; `experiments/drag_cost/tests`: **84 passed**.
- New: `tests/test_surface_positions.py` (5); six hand mutations of the view and the stages, each caught (AD-025 §18).

## Commands for the reference PC (PowerShell, from the repo root)

Compare GPU numbers only with the NVIDIA setting "Maximale Leistung bevorzugen" (prefer maximum performance) for
`python.exe` — the clocks otherwise drop while a CPU-bound frame leaves the GPU idle
([O2 reference-PC results](RESULTS_O2_REFERENCE_PC_2026-11-11.md), rounds 2–3). Use the same Python for before and
after (under 3.14 the panels are off: no `imgui-bundle`).

GL tests in their own process (picking on the mix, face-data pixel identity on the 9800 GTX driver):
```
python -m pytest (Get-ChildItem tests\test_gl_*.py) -q
```
After O1 — one-time costs and memory, one asset per process, then the D3 frame (each prints the commit):
```
python experiments\drag_cost\probe_scale_audit.py --only chain --assets examples\meshes\gollum_20k.obj
```
```
python experiments\drag_cost\probe_scale_audit.py --only chain --assets dense
```
```
python experiments\drag_cost\probe_d3_acceptance.py
```
Before O1, from a worktree of the probe commit on the pre-O1 code (delete it afterwards):
```
git worktree add ..\mirai-pre-o1 830f62e
```
```
Push-Location ..\mirai-pre-o1; python experiments\drag_cost\probe_scale_audit.py --only chain --assets examples\meshes\gollum_20k.obj; python experiments\drag_cost\probe_scale_audit.py --only chain --assets dense; python experiments\drag_cost\probe_d3_acceptance.py; Pop-Location
```
```
git worktree remove ..\mirai-pre-o1
```
Reference values to compare with: the first weight / pose step at 87.5k was 9.533 / 11.088 s on 2026-11-10
([RESULTS_SCALE_AUDIT_REFERENCE_PC_2026-11-10.md](RESULTS_SCALE_AUDIT_REFERENCE_PC_2026-11-10.md), before O0 / O2); the
D3 rows after O2 are in [RESULTS_O2_REFERENCE_PC_2026-11-11.md](RESULTS_O2_REFERENCE_PC_2026-11-11.md).

## Raw outputs

### Chain, 87.5k, before
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 830f62e6d3, working tree clean
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                                4984 ms   process     556 MiB (   +436)
  save scene file                                               1130 ms   process     576 MiB (    +20)
    file size 44.4 MiB
  parse scene file (scene_from_json, no viewport)               4127 ms   process     603 MiB (    +27)
  write one target, offsets on 15 % of the points                 86 ms   process     564 MiB (    -40)
  first weight step 0 -> 60 % (builds the mix surface)          5765 ms   process     991 MiB (   +427)
    of it: stage evaluation 3225 ms (MixSurface / SkinSurface.update), new RenderMesh 2502 ms
  next weight step (patch) + frame                               129 ms   process     991 MiB (     +1)
    of it: stage evaluation 20 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            123 ms   process     994 MiB (     +3)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     5645 ms   process    1411 MiB (   +417)
    of it: stage evaluation 3650 ms (MixSurface / SkinSurface.update), new RenderMesh 1746 ms
  next pose step (patch, morph + skin) + frame                   130 ms   process    1411 MiB (     +0)
    of it: stage evaluation 26 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### Chain, 87.5k, after
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 830f62e6d3, working tree MODIFIED, src/ tree 559d88b8e2
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                                4478 ms   process     555 MiB (   +436)
  save scene file                                               1024 ms   process     577 MiB (    +21)
    file size 44.4 MiB
  parse scene file (scene_from_json, no viewport)               3832 ms   process     603 MiB (    +27)
  write one target, offsets on 15 % of the points                 95 ms   process     563 MiB (    -40)
  first weight step 0 -> 60 % (builds the mix surface)          2354 ms   process     793 MiB (   +230)
    of it: stage evaluation 37 ms (MixSurface / SkinSurface.update), new RenderMesh 2280 ms
  next weight step (patch) + frame                               117 ms   process     794 MiB (     +1)
    of it: stage evaluation 14 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                            114 ms   process     796 MiB (     +2)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     3003 ms   process     974 MiB (   +177)
    of it: stage evaluation 92 ms (MixSurface / SkinSurface.update), new RenderMesh 2641 ms
  next pose step (patch, morph + skin) + frame                   195 ms   process     974 MiB (     +0)
    of it: stage evaluation 38 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### Chain, 20k, before
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 830f62e6d3, working tree clean
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                 851 ms   process     258 MiB (   +138)
  save scene file                                                136 ms   process     265 MiB (     +7)
    file size 11.1 MiB
  parse scene file (scene_from_json, no viewport)                662 ms   process     294 MiB (    +29)
  write one target, offsets on 15 % of the points                 33 ms   process     267 MiB (    -27)
  first weight step 0 -> 60 % (builds the mix surface)          1164 ms   process     369 MiB (   +102)
    of it: stage evaluation 751 ms (MixSurface / SkinSurface.update), new RenderMesh 399 ms
  next weight step (patch) + frame                                32 ms   process     369 MiB (     +0)
    of it: stage evaluation 5 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             25 ms   process     369 MiB (     +0)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                     1403 ms   process     493 MiB (   +124)
    of it: stage evaluation 858 ms (MixSurface / SkinSurface.update), new RenderMesh 467 ms
  next pose step (patch, morph + skin) + frame                    31 ms   process     493 MiB (     +0)
    of it: stage evaluation 5 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### Chain, 20k, after
```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Source: commit 830f62e6d3, working tree MODIFIED, src/ tree 559d88b8e2
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                1004 ms   process     259 MiB (   +139)
  save scene file                                                144 ms   process     266 MiB (     +7)
    file size 11.1 MiB
  parse scene file (scene_from_json, no viewport)                671 ms   process     295 MiB (    +29)
  write one target, offsets on 15 % of the points                 20 ms   process     263 MiB (    -32)
  first weight step 0 -> 60 % (builds the mix surface)           420 ms   process     318 MiB (    +55)
    of it: stage evaluation 7 ms (MixSurface / SkinSurface.update), new RenderMesh 395 ms
  next weight step (patch) + frame                                29 ms   process     318 MiB (     +0)
    of it: stage evaluation 3 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  rig + weights on 15 % of the points                             38 ms   process     318 MiB (     +0)
    of it: stage evaluation 0 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  first pose step (builds the skin surface)                      468 ms   process     384 MiB (    +66)
    of it: stage evaluation 15 ms (MixSurface / SkinSurface.update), new RenderMesh 382 ms
  next pose step (patch, morph + skin) + frame                    31 ms   process     384 MiB (     +0)
    of it: stage evaluation 4 ms (MixSurface / SkinSurface.update), new RenderMesh 0 ms
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

### D3 pair 1, before
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 830f62e6d3, working tree clean
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   156.25  p95   199.36  max   219.84 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.15  p95     0.20
    tick (update_viewport)                   p50   113.64  p95   149.37
    on_draw + glFinish                       p50    42.64  p95    51.19
      tick: stage evaluation (mix + skin)    p50    30.66  p95    41.62
      tick: RenderMesh._sync_geometry        p50    78.73  p95   103.61
        of it: face data -> store            p50     8.13  p95    12.05
      draw: viewport render (faces, wire, overlays) p50    25.64  p95    35.24
        of it: face-data upload              p50     0.40  p95     0.53
      draw: gizmo / bones                    p50     0.38  p95     0.50
      draw: HUD                              p50     0.46  p95     0.61
      draw: triad                            p50     0.06  p95     0.12
      draw: panels                           p50     0.82  p95     1.07
      draw: rest (clear, sync, GPU wait)     p50    14.24  p95    18.52
      gpu: vertex-buffer upload              p50     0.92  p95     1.03
      gpu: mesh draw (face data + shaded pass) p50    40.26  p95    49.15
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   197.51  p95   243.58  max   282.68 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.08
    tick (update_viewport)                   p50   144.86  p95   195.95
    on_draw + glFinish                       p50    50.60  p95    67.57
      tick: stage evaluation (mix + skin)    p50    55.53  p95    77.37
      tick: RenderMesh._sync_geometry        p50    80.90  p95   109.28
        of it: face data -> store            p50     8.11  p95    13.23
      draw: viewport render (faces, wire, overlays) p50    25.85  p95    37.87
        of it: face-data upload              p50     0.39  p95     0.61
      draw: gizmo / bones                    p50     1.74  p95     2.79
      draw: HUD                              p50     7.39  p95    11.25
      draw: triad                            p50     0.07  p95     0.13
      draw: panels                           p50     0.88  p95     1.14
      draw: rest (clear, sync, GPU wait)     p50    13.77  p95    20.31
      gpu: vertex-buffer upload              p50     0.91  p95     1.27
      gpu: mesh draw (face data + shaded pass) p50    48.31  p95    65.16
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   183.88  p95   235.30  max   251.37 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.15  p95     0.21
    tick (update_viewport)                   p50   118.91  p95   163.66
    on_draw + glFinish                       p50    62.91  p95    80.00
      tick: stage evaluation (mix + skin)    p50    32.53  p95    45.32
      tick: RenderMesh._sync_geometry        p50    82.61  p95   120.91
        of it: face data -> store            p50     8.44  p95    13.32
      draw: viewport render (faces, wire, overlays) p50    49.16  p95    71.60
        of it: face-data upload              p50     0.40  p95     0.60
      draw: gizmo / bones                    p50     0.38  p95     0.53
      draw: HUD                              p50     0.46  p95     0.78
      draw: triad                            p50     0.07  p95     0.11
      draw: panels                           p50     0.84  p95     1.19
      draw: rest (clear, sync, GPU wait)     p50    10.37  p95    15.64
      gpu: vertex-buffer upload              p50     0.92  p95     1.27
      gpu: mesh draw (face data + shaded pass) p50    55.72  p95    68.48
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   215.92  p95   276.78  max   286.05 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.09
    tick (update_viewport)                   p50   146.81  p95   211.07
    on_draw + glFinish                       p50    63.59  p95    89.83
      tick: stage evaluation (mix + skin)    p50    56.17  p95    87.61
      tick: RenderMesh._sync_geometry        p50    81.21  p95   120.60
        of it: face data -> store            p50     8.23  p95    12.37
      draw: viewport render (faces, wire, overlays) p50    47.38  p95    66.90
        of it: face-data upload              p50     0.38  p95     0.51
      draw: gizmo / bones                    p50     1.78  p95     2.98
      draw: HUD                              p50     7.31  p95    11.47
      draw: triad                            p50     0.07  p95     0.10
      draw: panels                           p50     0.87  p95     1.10
      draw: rest (clear, sync, GPU wait)     p50     4.78  p95     6.99
      gpu: vertex-buffer upload              p50     0.91  p95     1.19
      gpu: mesh draw (face data + shaded pass) p50    54.07  p95    66.19
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### D3 pair 1, after
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 830f62e6d3, working tree MODIFIED, src/ tree 559d88b8e2
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   154.08  p95   170.71  max   216.12 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.15  p95     0.20
    tick (update_viewport)                   p50   109.54  p95   128.10
    on_draw + glFinish                       p50    41.37  p95    54.58
      tick: stage evaluation (mix + skin)    p50    28.03  p95    36.88
      tick: RenderMesh._sync_geometry        p50    77.89  p95    94.13
        of it: face data -> store            p50     7.64  p95    10.64
      draw: viewport render (faces, wire, overlays) p50    24.70  p95    34.07
        of it: face-data upload              p50     0.39  p95     0.55
      draw: gizmo / bones                    p50     0.39  p95     0.57
      draw: HUD                              p50     0.45  p95     0.69
      draw: triad                            p50     0.06  p95     0.11
      draw: panels                           p50     0.80  p95     1.05
      draw: rest (clear, sync, GPU wait)     p50    14.27  p95    18.82
      gpu: vertex-buffer upload              p50     0.91  p95     1.31
      gpu: mesh draw (face data + shaded pass) p50    39.32  p95    52.60
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   178.94  p95   212.36  max   221.73 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.08
    tick (update_viewport)                   p50   129.09  p95   157.81
    on_draw + glFinish                       p50    48.61  p95    59.20
      tick: stage evaluation (mix + skin)    p50    45.32  p95    58.49
      tick: RenderMesh._sync_geometry        p50    77.09  p95   101.30
        of it: face data -> store            p50     7.93  p95    13.57
      draw: viewport render (faces, wire, overlays) p50    24.49  p95    31.41
        of it: face-data upload              p50     0.39  p95     0.55
      draw: gizmo / bones                    p50     1.76  p95     2.70
      draw: HUD                              p50     7.33  p95    11.83
      draw: triad                            p50     0.07  p95     0.10
      draw: panels                           p50     0.87  p95     1.25
      draw: rest (clear, sync, GPU wait)     p50    13.75  p95    17.20
      gpu: vertex-buffer upload              p50     0.94  p95     1.07
      gpu: mesh draw (face data + shaded pass) p50    46.53  p95    57.42
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   172.87  p95   221.65  max   253.73 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.15  p95     0.19
    tick (update_viewport)                   p50   113.83  p95   153.69
    on_draw + glFinish                       p50    58.67  p95    68.84
      tick: stage evaluation (mix + skin)    p50    29.46  p95    41.75
      tick: RenderMesh._sync_geometry        p50    80.72  p95   116.86
        of it: face data -> store            p50     8.01  p95    12.88
      draw: viewport render (faces, wire, overlays) p50    46.42  p95    59.84
        of it: face-data upload              p50     0.41  p95     1.01
      draw: gizmo / bones                    p50     0.38  p95     0.53
      draw: HUD                              p50     0.46  p95     0.63
      draw: triad                            p50     0.06  p95     0.12
      draw: panels                           p50     0.80  p95     1.04
      draw: rest (clear, sync, GPU wait)     p50     9.06  p95    13.92
      gpu: vertex-buffer upload              p50     0.90  p95     1.12
      gpu: mesh draw (face data + shaded pass) p50    52.03  p95    62.00
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   205.93  p95   264.48  max   280.22 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.09
    tick (update_viewport)                   p50   136.16  p95   183.62
    on_draw + glFinish                       p50    66.22  p95    90.89
      tick: stage evaluation (mix + skin)    p50    48.28  p95    67.32
      tick: RenderMesh._sync_geometry        p50    79.89  p95   110.82
        of it: face data -> store            p50     7.97  p95    12.47
      draw: viewport render (faces, wire, overlays) p50    48.51  p95    70.89
        of it: face-data upload              p50     0.41  p95     0.87
      draw: gizmo / bones                    p50     1.80  p95     2.79
      draw: HUD                              p50     7.48  p95    10.80
      draw: triad                            p50     0.07  p95     0.12
      draw: panels                           p50     0.88  p95     1.08
      draw: rest (clear, sync, GPU wait)     p50     5.20  p95     8.20
      gpu: vertex-buffer upload              p50     0.91  p95     1.57
      gpu: mesh draw (face data + shaded pass) p50    54.86  p95    70.33
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### D3 pair 1, array control
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 830f62e6d3, working tree MODIFIED, src/ tree b2155cfdcc
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   162.28  p95   197.29  max   243.45 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.15  p95     0.19
    tick (update_viewport)                   p50   119.86  p95   157.21
    on_draw + glFinish                       p50    40.34  p95    53.15
      tick: stage evaluation (mix + skin)    p50    29.85  p95    44.35
      tick: RenderMesh._sync_geometry        p50    85.69  p95   107.27
        of it: face data -> store            p50     7.55  p95    12.45
      draw: viewport render (faces, wire, overlays) p50    24.38  p95    33.83
        of it: face-data upload              p50     0.41  p95     0.56
      draw: gizmo / bones                    p50     0.38  p95     0.47
      draw: HUD                              p50     0.46  p95     0.62
      draw: triad                            p50     0.06  p95     0.10
      draw: panels                           p50     0.80  p95     1.15
      draw: rest (clear, sync, GPU wait)     p50    13.95  p95    18.69
      gpu: vertex-buffer upload              p50     0.90  p95     1.03
      gpu: mesh draw (face data + shaded pass) p50    38.23  p95    50.80
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   197.71  p95   270.38  max   281.98 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.09
    tick (update_viewport)                   p50   147.17  p95   209.48
    on_draw + glFinish                       p50    50.41  p95    68.06
      tick: stage evaluation (mix + skin)    p50    51.01  p95    71.33
      tick: RenderMesh._sync_geometry        p50    89.33  p95   136.83
        of it: face data -> store            p50     8.10  p95    12.99
      draw: viewport render (faces, wire, overlays) p50    25.16  p95    36.10
        of it: face-data upload              p50     0.42  p95     0.69
      draw: gizmo / bones                    p50     1.75  p95     2.74
      draw: HUD                              p50     7.50  p95    12.08
      draw: triad                            p50     0.07  p95     0.12
      draw: panels                           p50     0.83  p95     1.12
      draw: rest (clear, sync, GPU wait)     p50    14.54  p95    19.07
      gpu: vertex-buffer upload              p50     0.90  p95     1.11
      gpu: mesh draw (face data + shaded pass) p50    48.43  p95    65.69
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   187.34  p95   242.74  max   277.14 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.16  p95     0.21
    tick (update_viewport)                   p50   124.89  p95   180.40
    on_draw + glFinish                       p50    61.18  p95    75.97
      tick: stage evaluation (mix + skin)    p50    30.53  p95    43.00
      tick: RenderMesh._sync_geometry        p50    89.77  p95   128.52
        of it: face data -> store            p50     8.23  p95    13.63
      draw: viewport render (faces, wire, overlays) p50    48.17  p95    66.44
        of it: face-data upload              p50     0.41  p95     0.66
      draw: gizmo / bones                    p50     0.40  p95     0.56
      draw: HUD                              p50     0.47  p95     0.67
      draw: triad                            p50     0.07  p95     0.12
      draw: panels                           p50     0.83  p95     1.16
      draw: rest (clear, sync, GPU wait)     p50     9.97  p95    14.63
      gpu: vertex-buffer upload              p50     0.95  p95     1.64
      gpu: mesh draw (face data + shaded pass) p50    54.22  p95    68.97
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   220.80  p95   273.84  max   315.16 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.08
    tick (update_viewport)                   p50   151.10  p95   185.58
    on_draw + glFinish                       p50    66.13  p95    89.26
      tick: stage evaluation (mix + skin)    p50    51.52  p95    71.15
      tick: RenderMesh._sync_geometry        p50    91.13  p95   124.76
        of it: face data -> store            p50     8.19  p95    13.08
      draw: viewport render (faces, wire, overlays) p50    48.81  p95    69.97
        of it: face-data upload              p50     0.40  p95     0.50
      draw: gizmo / bones                    p50     1.87  p95     2.80
      draw: HUD                              p50     7.94  p95    11.50
      draw: triad                            p50     0.07  p95     0.12
      draw: panels                           p50     0.86  p95     1.11
      draw: rest (clear, sync, GPU wait)     p50     5.08  p95     7.13
      gpu: vertex-buffer upload              p50     0.90  p95     1.05
      gpu: mesh draw (face data + shaded pass) p50    54.39  p95    67.78
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### D3 pair 2, after
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 830f62e6d3, working tree MODIFIED, src/ tree 559d88b8e2
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   157.28  p95   218.65  max   235.49 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.15  p95     0.22
    tick (update_viewport)                   p50   113.03  p95   167.67
    on_draw + glFinish                       p50    42.63  p95    53.12
      tick: stage evaluation (mix + skin)    p50    28.54  p95    41.87
      tick: RenderMesh._sync_geometry        p50    80.15  p95   125.73
        of it: face data -> store            p50     7.80  p95    12.56
      draw: viewport render (faces, wire, overlays) p50    25.34  p95    36.10
        of it: face-data upload              p50     0.41  p95     0.79
      draw: gizmo / bones                    p50     0.39  p95     0.55
      draw: HUD                              p50     0.46  p95     0.69
      draw: triad                            p50     0.07  p95     0.12
      draw: panels                           p50     0.84  p95     1.17
      draw: rest (clear, sync, GPU wait)     p50    14.70  p95    19.16
      gpu: vertex-buffer upload              p50     0.96  p95     2.37
      gpu: mesh draw (face data + shaded pass) p50    39.88  p95    50.83
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   184.00  p95   226.17  max   260.93 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.09
    tick (update_viewport)                   p50   129.36  p95   177.53
    on_draw + glFinish                       p50    51.95  p95    66.73
      tick: stage evaluation (mix + skin)    p50    46.09  p95    61.69
      tick: RenderMesh._sync_geometry        p50    77.66  p95   111.53
        of it: face data -> store            p50     7.93  p95    12.14
      draw: viewport render (faces, wire, overlays) p50    25.52  p95    36.25
        of it: face-data upload              p50     0.43  p95     0.55
      draw: gizmo / bones                    p50     1.70  p95     2.80
      draw: HUD                              p50     7.54  p95    11.65
      draw: triad                            p50     0.07  p95     0.12
      draw: panels                           p50     0.84  p95     1.10
      draw: rest (clear, sync, GPU wait)     p50    14.80  p95    18.95
      gpu: vertex-buffer upload              p50     0.92  p95     1.25
      gpu: mesh draw (face data + shaded pass) p50    49.64  p95    64.24
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   184.78  p95   261.39  max   272.76 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.15  p95     0.23
    tick (update_viewport)                   p50   121.31  p95   188.51
    on_draw + glFinish                       p50    62.63  p95    82.81
      tick: stage evaluation (mix + skin)    p50    31.91  p95    45.81
      tick: RenderMesh._sync_geometry        p50    84.61  p95   137.91
        of it: face data -> store            p50     8.41  p95    14.76
      draw: viewport render (faces, wire, overlays) p50    48.70  p95    74.46
        of it: face-data upload              p50     0.42  p95     0.59
      draw: gizmo / bones                    p50     0.40  p95     0.55
      draw: HUD                              p50     0.48  p95     0.78
      draw: triad                            p50     0.07  p95     0.13
      draw: panels                           p50     0.83  p95     1.17
      draw: rest (clear, sync, GPU wait)     p50     9.74  p95    16.60
      gpu: vertex-buffer upload              p50     0.96  p95     1.37
      gpu: mesh draw (face data + shaded pass) p50    56.04  p95    71.15
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   203.06  p95   252.24  max   332.01 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.08
    tick (update_viewport)                   p50   137.82  p95   181.87
    on_draw + glFinish                       p50    64.22  p95    91.00
      tick: stage evaluation (mix + skin)    p50    49.21  p95    71.35
      tick: RenderMesh._sync_geometry        p50    81.04  p95   110.01
        of it: face data -> store            p50     8.11  p95    12.82
      draw: viewport render (faces, wire, overlays) p50    47.76  p95    71.15
        of it: face-data upload              p50     0.43  p95     0.61
      draw: gizmo / bones                    p50     1.76  p95     2.85
      draw: HUD                              p50     7.83  p95    11.62
      draw: triad                            p50     0.07  p95     0.11
      draw: panels                           p50     0.86  p95     1.09
      draw: rest (clear, sync, GPU wait)     p50     4.94  p95     8.28
      gpu: vertex-buffer upload              p50     0.92  p95     1.09
      gpu: mesh draw (face data + shaded pass) p50    55.25  p95    70.45
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### D3 pair 2, before
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 830f62e6d3, working tree clean
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   152.64  p95   211.27  max   235.23 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.15  p95     0.20
    tick (update_viewport)                   p50   110.85  p95   172.95
    on_draw + glFinish                       p50    41.75  p95    52.96
      tick: stage evaluation (mix + skin)    p50    30.38  p95    45.42
      tick: RenderMesh._sync_geometry        p50    76.56  p95   119.32
        of it: face data -> store            p50     7.71  p95    12.31
      draw: viewport render (faces, wire, overlays) p50    24.22  p95    34.94
        of it: face-data upload              p50     0.41  p95     0.54
      draw: gizmo / bones                    p50     0.38  p95     0.53
      draw: HUD                              p50     0.46  p95     0.65
      draw: triad                            p50     0.06  p95     0.11
      draw: panels                           p50     0.81  p95     1.12
      draw: rest (clear, sync, GPU wait)     p50    14.36  p95    17.27
      gpu: vertex-buffer upload              p50     0.91  p95     1.06
      gpu: mesh draw (face data + shaded pass) p50    39.64  p95    50.38
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   196.23  p95   233.00  max   278.65 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.10
    tick (update_viewport)                   p50   144.45  p95   181.18
    on_draw + glFinish                       p50    51.13  p95    64.40
      tick: stage evaluation (mix + skin)    p50    56.09  p95    67.40
      tick: RenderMesh._sync_geometry        p50    80.06  p95   105.37
        of it: face data -> store            p50     8.18  p95    12.22
      draw: viewport render (faces, wire, overlays) p50    25.12  p95    36.12
        of it: face-data upload              p50     0.42  p95     0.54
      draw: gizmo / bones                    p50     1.74  p95     2.51
      draw: HUD                              p50     7.50  p95    11.40
      draw: triad                            p50     0.07  p95     0.11
      draw: panels                           p50     0.86  p95     1.12
      draw: rest (clear, sync, GPU wait)     p50    14.61  p95    18.46
      gpu: vertex-buffer upload              p50     0.92  p95     1.31
      gpu: mesh draw (face data + shaded pass) p50    48.87  p95    62.13
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   194.33  p95   253.20  max   270.01 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.16  p95     0.21
    tick (update_viewport)                   p50   132.18  p95   185.85
    on_draw + glFinish                       p50    63.53  p95    79.36
      tick: stage evaluation (mix + skin)    p50    34.95  p95    49.66
      tick: RenderMesh._sync_geometry        p50    89.83  p95   134.76
        of it: face data -> store            p50     8.69  p95    15.69
      draw: viewport render (faces, wire, overlays) p50    50.24  p95    69.59
        of it: face-data upload              p50     0.43  p95     0.57
      draw: gizmo / bones                    p50     0.42  p95     0.55
      draw: HUD                              p50     0.52  p95     0.68
      draw: triad                            p50     0.07  p95     0.11
      draw: panels                           p50     0.87  p95     1.14
      draw: rest (clear, sync, GPU wait)     p50    10.60  p95    16.12
      gpu: vertex-buffer upload              p50     0.98  p95     1.23
      gpu: mesh draw (face data + shaded pass) p50    56.05  p95    72.21
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   211.64  p95   245.49  max   259.05 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.09
    tick (update_viewport)                   p50   145.86  p95   175.54
    on_draw + glFinish                       p50    64.21  p95    86.13
      tick: stage evaluation (mix + skin)    p50    56.73  p95    71.02
      tick: RenderMesh._sync_geometry        p50    83.02  p95    98.94
        of it: face data -> store            p50     8.44  p95    11.60
      draw: viewport render (faces, wire, overlays) p50    48.31  p95    66.12
        of it: face-data upload              p50     0.41  p95     0.55
      draw: gizmo / bones                    p50     1.82  p95     2.87
      draw: HUD                              p50     7.60  p95    10.34
      draw: triad                            p50     0.07  p95     0.11
      draw: panels                           p50     0.85  p95     1.03
      draw: rest (clear, sync, GPU wait)     p50     5.04  p95     6.94
      gpu: vertex-buffer upload              p50     0.92  p95     1.16
      gpu: mesh draw (face data + shaded pass) p50    54.13  p95    64.68
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```

### D3 pair 2, array control
```
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit 830f62e6d3, working tree MODIFIED, src/ tree b2155cfdcc
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels on; vertex textures live; face upload subdata
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   164.87  p95   197.65  max   230.17 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.14  p95     0.20
    tick (update_viewport)                   p50   122.22  p95   148.23
    on_draw + glFinish                       p50    42.23  p95    50.70
      tick: stage evaluation (mix + skin)    p50    29.16  p95    42.34
      tick: RenderMesh._sync_geometry        p50    87.16  p95   112.10
        of it: face data -> store            p50     7.68  p95    10.68
      draw: viewport render (faces, wire, overlays) p50    24.69  p95    32.87
        of it: face-data upload              p50     0.41  p95     0.55
      draw: gizmo / bones                    p50     0.36  p95     0.54
      draw: HUD                              p50     0.45  p95     0.72
      draw: triad                            p50     0.06  p95     0.12
      draw: panels                           p50     0.81  p95     1.13
      draw: rest (clear, sync, GPU wait)     p50    14.79  p95    18.23
      gpu: vertex-buffer upload              p50     0.93  p95     1.37
      gpu: mesh draw (face data + shaded pass) p50    40.16  p95    48.46
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   196.34  p95   281.31  max   319.50 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.09
    tick (update_viewport)                   p50   144.13  p95   232.14
    on_draw + glFinish                       p50    49.12  p95    69.32
      tick: stage evaluation (mix + skin)    p50    50.59  p95    78.26
      tick: RenderMesh._sync_geometry        p50    86.95  p95   145.08
        of it: face data -> store            p50     7.72  p95    12.50
      draw: viewport render (faces, wire, overlays) p50    25.03  p95    37.57
        of it: face-data upload              p50     0.39  p95     0.50
      draw: gizmo / bones                    p50     1.71  p95     2.81
      draw: HUD                              p50     7.53  p95    12.16
      draw: triad                            p50     0.07  p95     0.13
      draw: panels                           p50     0.85  p95     1.08
      draw: rest (clear, sync, GPU wait)     p50    13.87  p95    17.36
      gpu: vertex-buffer upload              p50     0.91  p95     1.12
      gpu: mesh draw (face data + shaded pass) p50    46.99  p95    66.84
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   188.08  p95   273.61  max   292.11 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.15  p95     0.20
    tick (update_viewport)                   p50   124.92  p95   195.69
    on_draw + glFinish                       p50    61.41  p95    83.09
      tick: stage evaluation (mix + skin)    p50    30.33  p95    47.31
      tick: RenderMesh._sync_geometry        p50    90.92  p95   143.80
        of it: face data -> store            p50     8.25  p95    13.79
      draw: viewport render (faces, wire, overlays) p50    49.06  p95    69.25
        of it: face-data upload              p50     0.40  p95     0.56
      draw: gizmo / bones                    p50     0.39  p95     0.55
      draw: HUD                              p50     0.46  p95     0.65
      draw: triad                            p50     0.07  p95     0.11
      draw: panels                           p50     0.85  p95     1.17
      draw: rest (clear, sync, GPU wait)     p50     9.72  p95    13.39
      gpu: vertex-buffer upload              p50     0.91  p95     1.13
      gpu: mesh draw (face data + shaded pass) p50    53.79  p95    73.69
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   217.69  p95   295.25  max   331.23 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.06  p95     0.09
    tick (update_viewport)                   p50   150.28  p95   222.95
    on_draw + glFinish                       p50    63.71  p95    90.09
      tick: stage evaluation (mix + skin)    p50    51.45  p95    71.70
      tick: RenderMesh._sync_geometry        p50    89.58  p95   142.04
        of it: face data -> store            p50     8.36  p95    13.68
      draw: viewport render (faces, wire, overlays) p50    47.57  p95    72.23
        of it: face-data upload              p50     0.40  p95     0.55
      draw: gizmo / bones                    p50     1.79  p95     2.93
      draw: HUD                              p50     7.59  p95    11.44
      draw: triad                            p50     0.07  p95     0.14
      draw: panels                           p50     0.87  p95     1.06
      draw: rest (clear, sync, GPU wait)     p50     5.16  p95     8.77
      gpu: vertex-buffer upload              p50     0.92  p95     1.11
      gpu: mesh draw (face data + shaded pass) p50    54.89  p95    73.12
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
```
