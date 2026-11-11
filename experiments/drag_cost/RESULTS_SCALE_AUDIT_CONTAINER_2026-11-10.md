# Scale audit, container, 2026-11-10 / 11 - raw probe outputs

Raw outputs behind [`docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md`](../../docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md),
state `5b65c62`. **Container, not the reference PC:** Intel Xeon 2.1 GHz (4 logical cores), Linux, Python 3.13.18,
Mesa llvmpipe (software GL: `draw` and the ID-pass renders are CPU time here, not GPU time). Two container hosts were
used (a restart between 2026-11-10 and 11-11); the same row differed by up to 40 % between them, so read these numbers
as one run each, not as a baseline. `gollum_87k` = `gollum_20k.obj` after one Catmull-Clark step
(`probe_scale_audit.py --make-dense`).

## 1. Pose-step split

`xvfb-run -a python experiments/drag_cost/probe_scale_audit.py --only split` (20k: `--regions 5 15 100 --steps 20`;
87.5k: `--regions 5 15 --steps 12`, then `--regions 100 --steps 6`).

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_20k] 21875 V, region 5 % = 1093 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           10.22  100 %   (p95 18.08)
  1 skin evaluation (LBS + Mesh writes)              1.47   14.4 %
  2 RenderMesh._sync_geometry, total                 8.09   79.1 %
  2a  neighbourhood sets                             0.58    5.7 %
  2b  face normals                                   1.72   16.8 %
  2c  vertex normals                                 0.89    8.8 %
  2d  positions + normals -> mirror -> store         1.41   13.8 %
  2e  face rows (36 floats per face) -> store        2.67   26.1 %
  4 face-data glBufferSubData at draw                0.12    1.1 %
  draw + glFinish                                    8.14
  bytes handed to the store per step               214824  (197 per weighted vertex)
[gollum_20k] 21875 V, region 5 % = 1093 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           47.68  100 %   (p95 67.04)
  1 skin evaluation (LBS + Mesh writes)              1.90    4.0 %
  2 RenderMesh._sync_geometry, total                 9.95   20.9 %
  2a  neighbourhood sets                             0.77    1.6 %
  2b  face normals                                   2.28    4.8 %
  2c  vertex normals                                 1.13    2.4 %
  2d  positions + normals -> mirror -> store         1.49    3.1 %
  2e  face rows (36 floats per face) -> store        3.00    6.3 %
  3 wire segments (whole mesh)                      31.55   66.2 %
  4 face-data glBufferSubData at draw                0.15    0.3 %
  draw + glFinish                                   27.33
  bytes handed to the store per step               214824  (197 per weighted vertex)

[gollum_20k] 21875 V, region 15 % = 3281 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           43.29  100 %   (p95 53.86)
  1 skin evaluation (LBS + Mesh writes)              8.27   19.1 %
  2 RenderMesh._sync_geometry, total                34.27   79.2 %
  2a  neighbourhood sets                             2.29    5.3 %
  2b  face normals                                   7.91   18.3 %
  2c  vertex normals                                 4.07    9.4 %
  2d  positions + normals -> mirror -> store         5.51   12.7 %
  2e  face rows (36 floats per face) -> store       11.30   26.1 %
  4 face-data glBufferSubData at draw                0.26    0.6 %
  draw + glFinish                                    9.85
  bytes handed to the store per step               598992  (183 per weighted vertex)
[gollum_20k] 21875 V, region 15 % = 3281 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           93.74  100 %   (p95 99.69)
  1 skin evaluation (LBS + Mesh writes)              8.04    8.6 %
  2 RenderMesh._sync_geometry, total                38.96   41.6 %
  2a  neighbourhood sets                             2.77    3.0 %
  2b  face normals                                   9.38   10.0 %
  2c  vertex normals                                 4.38    4.7 %
  2d  positions + normals -> mirror -> store         6.63    7.1 %
  2e  face rows (36 floats per face) -> store       13.09   14.0 %
  3 wire segments (whole mesh)                      44.64   47.6 %
  4 face-data glBufferSubData at draw                0.27    0.3 %
  draw + glFinish                                   36.06
  bytes handed to the store per step               598992  (183 per weighted vertex)

[gollum_20k] 21875 V, region 100 % = 21875 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          234.57  100 %   (p95 332.90)
  1 skin evaluation (LBS + Mesh writes)             47.97   20.5 %
  2 RenderMesh._sync_geometry, total               180.72   77.0 %
  2a  neighbourhood sets                            10.33    4.4 %
  2b  face normals                                  44.91   19.1 %
  2c  vertex normals                                21.54    9.2 %
  2d  positions + normals -> mirror -> store        27.77   11.8 %
  2e  face rows (36 floats per face) -> store       55.92   23.8 %
  4 face-data glBufferSubData at draw                0.49    0.2 %
  draw + glFinish                                    9.09
  bytes handed to the store per step              3675000  (168 per weighted vertex)
[gollum_20k] 21875 V, region 100 % = 21875 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          310.10  100 %   (p95 370.10)
  1 skin evaluation (LBS + Mesh writes)             52.76   17.0 %
  2 RenderMesh._sync_geometry, total               204.64   66.0 %
  2a  neighbourhood sets                            13.23    4.3 %
  2b  face normals                                  49.07   15.8 %
  2c  vertex normals                                26.02    8.4 %
  2d  positions + normals -> mirror -> store        32.96   10.6 %
  2e  face rows (36 floats per face) -> store       69.87   22.5 %
  3 wire segments (whole mesh)                      40.66   13.1 %
  4 face-data glBufferSubData at draw                0.62    0.2 %
  draw + glFinish                                   36.19
  bytes handed to the store per step              3675000  (168 per weighted vertex)
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V, region 5 % = 4375 V, wire off, 12 pose steps, p50 ms
  step (pointer_motion + update_viewport)           67.86  100 %   (p95 101.27)
  1 skin evaluation (LBS + Mesh writes)             12.67   18.7 %
  2 RenderMesh._sync_geometry, total                49.26   72.6 %
  2a  neighbourhood sets                             3.93    5.8 %
  2b  face normals                                  11.05   16.3 %
  2c  vertex normals                                 5.59    8.2 %
  2d  positions + normals -> mirror -> store         8.82   13.0 %
  2e  face rows (36 floats per face) -> store       16.91   24.9 %
  4 face-data glBufferSubData at draw                0.30    0.4 %
  draw + glFinish                                   37.40
  bytes handed to the store per step               797556  (182 per weighted vertex)
[gollum_87k] 87500 V, region 5 % = 4375 V, wire ON, 12 pose steps, p50 ms
  step (pointer_motion + update_viewport)          216.42  100 %   (p95 256.91)
  1 skin evaluation (LBS + Mesh writes)             20.20    9.3 %
  2 RenderMesh._sync_geometry, total                41.96   19.4 %
  2a  neighbourhood sets                             3.07    1.4 %
  2b  face normals                                  10.22    4.7 %
  2c  vertex normals                                 5.06    2.3 %
  2d  positions + normals -> mirror -> store         7.09    3.3 %
  2e  face rows (36 floats per face) -> store       13.84    6.4 %
  3 wire segments (whole mesh)                     150.33   69.5 %
  4 face-data glBufferSubData at draw                0.30    0.1 %
  draw + glFinish                                  103.98
  bytes handed to the store per step               797556  (182 per weighted vertex)

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 12 pose steps, p50 ms
  step (pointer_motion + update_viewport)          177.17  100 %   (p95 225.99)
  1 skin evaluation (LBS + Mesh writes)             39.74   22.4 %
  2 RenderMesh._sync_geometry, total               136.03   76.8 %
  2a  neighbourhood sets                            11.37    6.4 %
  2b  face normals                                  35.22   19.9 %
  2c  vertex normals                                18.01   10.2 %
  2d  positions + normals -> mirror -> store        23.56   13.3 %
  2e  face rows (36 floats per face) -> store       45.73   25.8 %
  4 face-data glBufferSubData at draw                0.57    0.3 %
  draw + glFinish                                   36.81
  bytes handed to the store per step              2304924  (176 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 12 pose steps, p50 ms
  step (pointer_motion + update_viewport)          393.11  100 %   (p95 420.74)
  1 skin evaluation (LBS + Mesh writes)             47.98   12.2 %
  2 RenderMesh._sync_geometry, total               162.95   41.5 %
  2a  neighbourhood sets                            11.40    2.9 %
  2b  face normals                                  38.40    9.8 %
  2c  vertex normals                                20.00    5.1 %
  2d  positions + normals -> mirror -> store        27.24    6.9 %
  2e  face rows (36 floats per face) -> store       54.90   14.0 %
  3 wire segments (whole mesh)                     179.33   45.6 %
  4 face-data glBufferSubData at draw                0.59    0.1 %
  draw + glFinish                                  128.55
  bytes handed to the store per step              2304924  (176 per weighted vertex)
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V, region 100 % = 87500 V, wire off, 6 pose steps, p50 ms
  step (pointer_motion + update_viewport)          921.84  100 %   (p95 973.61)
  1 skin evaluation (LBS + Mesh writes)            203.92   22.1 %
  2 RenderMesh._sync_geometry, total               693.82   75.3 %
  2a  neighbourhood sets                            52.83    5.7 %
  2b  face normals                                 175.86   19.1 %
  2c  vertex normals                               100.00   10.8 %
  2d  positions + normals -> mirror -> store        91.23    9.9 %
  2e  face rows (36 floats per face) -> store      209.63   22.7 %
  4 face-data glBufferSubData at draw                2.08    0.2 %
  draw + glFinish                                   28.47
  bytes handed to the store per step             14700000  (168 per weighted vertex)
[gollum_87k] 87500 V, region 100 % = 87500 V, wire ON, 6 pose steps, p50 ms
  step (pointer_motion + update_viewport)         1122.86  100 %   (p95 1244.53)
  1 skin evaluation (LBS + Mesh writes)            180.01   16.0 %
  2 RenderMesh._sync_geometry, total               761.23   67.8 %
  2a  neighbourhood sets                            52.56    4.7 %
  2b  face normals                                 179.42   16.0 %
  2c  vertex normals                               120.24   10.7 %
  2d  positions + normals -> mirror -> store        92.61    8.2 %
  2e  face rows (36 floats per face) -> store      231.13   20.6 %
  3 wire segments (whole mesh)                     152.54   13.6 %
  4 face-data glBufferSubData at draw                2.30    0.2 %
  draw + glFinish                                   92.95
  bytes handed to the store per step             14700000  (168 per weighted vertex)
```

## 2. One-time costs and process memory

`xvfb-run -a python experiments/drag_cost/probe_scale_audit.py --only chain --assets <one asset>` (one asset per
process; the bracket is the change since the previous row).

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                1016 ms   process     260 MiB (   +142)
  save scene file                                                198 ms   process     274 MiB (    +14)
    file size 11.1 MiB
  parse scene file (scene_from_json, no viewport)                739 ms   process     296 MiB (    +21)
  write one target, offsets on 15 % of the points                 31 ms   process     264 MiB (    -32)
  first weight step 0 -> 60 % (builds the mix surface)          1312 ms   process     385 MiB (   +121)
  next weight step (patch) + frame                                54 ms   process     385 MiB (     +0)
  rig + weights on 15 % of the points                             27 ms   process     385 MiB (     +0)
  first pose step (builds the skin surface)                     1741 ms   process     518 MiB (   +133)
  next pose step (patch, morph + skin) + frame                    46 ms   process     518 MiB (     +0)
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                                4532 ms   process     570 MiB (   +452)
  save scene file                                               1134 ms   process     572 MiB (     +2)
    file size 44.4 MiB
  parse scene file (scene_from_json, no viewport)               4011 ms   process     618 MiB (    +46)
  write one target, offsets on 15 % of the points                 88 ms   process     578 MiB (    -40)
  first weight step 0 -> 60 % (builds the mix surface)          6359 ms   process    1066 MiB (   +488)
  next weight step (patch) + frame                               159 ms   process    1069 MiB (     +3)
  rig + weights on 15 % of the points                            118 ms   process    1072 MiB (     +3)
  first pose step (builds the skin surface)                     6206 ms   process    1526 MiB (   +454)
  next pose step (patch, morph + skin) + frame                   157 ms   process    1526 MiB (     +0)
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

## 3. Production code against packed arrays

`python experiments/drag_cost/probe_kernels.py --assets examples/meshes/gollum_20k.obj dense`

```
Kernel probe (2026-11-10): production code vs. packed arrays, CPU side only
Platform: Linux-6.18.44-fc-v378-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
NumPy 2.5.3 (runtime dispatch off: baseline instructions only)
native C: cc -O2 -fPIC -march=core2 -shared -lm, loaded through ctypes

=== gollum_20k.obj: 21875 V, 21875 F ===
production, once: core.Mesh from arrays 204 ms, RenderMesh full build 475 ms, export_state 72 ms, Mesh.from_state 720 ms
packed, once: arrays + adjacency + all normals 25 ms, 3.0 MiB
-- visible: 1-ring normals + buffer data for a moved region, ms per step (CPU side, no upload)
   check: max |production vertex normal - packed| = 1.3e-14; all normals of the mesh: NumPy 9.48 ms, native C 0.442 ms
  region  V moved | production    flat Py      NumPy   native C
     1 %      218 |       1.66       0.57      0.357      0.048
     5 %     1093 |       7.08       2.65      1.287      0.084
    15 %     3281 |      19.00       7.29      3.383      0.178
   100 %    21875 |     151.47      54.98      8.702      0.974
-- skin: linear blend skinning of a weighted region, ms per pose step (evaluation only)
  region        V | production      NumPy   native C   max diff
     5 %     1093 |       2.00      0.453      0.063   0.0e+00
    15 %     3281 |       5.56      0.845      0.054   0.0e+00
   100 %    21875 |      35.72      6.056      0.303   0.0e+00
-- morph: one weight step of one target, ms (evaluation only)
 offsets        V | production      NumPy   native C   max diff
    15 %     3281 |       3.04      0.143      0.024   0.0e+00
   100 %    21875 |      17.75      0.688      0.061   0.0e+00
-- subd: level 1 of this mesh as the cage = 87500 V / 87500 F, 546875 stencil entries; topology + stencil build 0.99 s
                  | production      NumPy   native C   max diff
       apply_full |      82.65     17.701      0.729   3.3e-16

=== gollum_87k.obj: 87500 V, 87500 F ===
production, once: core.Mesh from arrays 1164 ms, RenderMesh full build 3339 ms, export_state 768 ms, Mesh.from_state 3444 ms
packed, once: arrays + adjacency + all normals 152 ms, 12.0 MiB
-- visible: 1-ring normals + buffer data for a moved region, ms per step (CPU side, no upload)
   check: max |production vertex normal - packed| = 3.1e-14; all normals of the mesh: NumPy 53.82 ms, native C 3.654 ms
  region  V moved | production    flat Py      NumPy   native C
     1 %      875 |      10.43       4.15      2.060      0.352
     5 %     4375 |      49.77      15.57      7.591      0.469
    15 %    13125 |     137.46      49.85     19.494      1.081
   100 %    87500 |     798.71     261.60     51.476      4.550
-- skin: linear blend skinning of a weighted region, ms per pose step (evaluation only)
  region        V | production      NumPy   native C   max diff
     5 %     4375 |       5.23      1.048      0.062   0.0e+00
    15 %    13125 |      31.08      3.177      0.202   0.0e+00
   100 %    87500 |     176.48     41.980      1.297   0.0e+00
-- morph: one weight step of one target, ms (evaluation only)
 offsets        V | production      NumPy   native C   max diff
    15 %    13125 |       9.67      0.629      0.058   0.0e+00
   100 %    87500 |      96.05      6.177      0.568   0.0e+00
-- subd: level 1 of this mesh as the cage = 350000 V / 350000 F, 2187500 stencil entries; topology + stencil build 5.19 s
                  | production      NumPy   native C   max diff
       apply_full |     381.04     87.718      4.807   3.3e-16
```

## 4. Navigation, picking, topology, drags (existing probe)

`xvfb-run -a python experiments/drag_cost/probe_navigation_gl.py --assets examples/meshes/gollum_20k.obj <gollum_87k.obj>
--scenarios orbit orbit_wire first_hover hover_move select_click topology plain_w soft_w --row-seconds 6 --profile-top 0`

The `op` column of the topology rows contains the software ID-pass render of the hover re-pick (profile in the audit,
§E.6); it is not Python work.

```
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Linux-6.18.44-fc-v338-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Run: hidden 1024x768 window; up to 40 events per row (at least 5, budget 6 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 49218 triangles; load + first frame 815 ms
  orbit        n= 40  frame p50     7.82  p95    11.38  max    13.80   (0/40 over 16.7 ms)
    event     0.03 (p95     0.05)  pick     0.00  [cache    0.00, 0.0 rebuilds/event; occl     0.00, 0.0 tests/event]
    sync      0.04   draw   7.76  gpu   0.24   upload     0.0 KB/frame
  orbit_wire   n= 40  frame p50    14.88  p95    19.69  max    33.17   (13/40 over 16.7 ms)
    event     0.04 (p95     0.06)  pick     0.00  [cache    0.00, 0.0 rebuilds/event; occl     0.00, 0.0 tests/event]
    sync      0.05   draw  14.78  gpu   0.61   upload     0.0 KB/frame
  first_hover  n= 40  frame p50    82.31  p95   124.68  max   125.90   (40/40 over 16.7 ms)
    event    70.87 (p95   111.71)  pick     0.00  [cache   51.64, 1.0 rebuilds/event; occl     4.32, 2.0 tests/event]
    sync      1.47   draw   9.48  gpu   0.22   upload    96.1 KB/frame
  hover_move   n= 40  frame p50     9.62  p95    12.79  max    28.90   (1/40 over 16.7 ms)
    event     1.10 (p95     3.58)  pick     0.00  [cache    0.00, 0.0 rebuilds/event; occl     0.10, 1.7 tests/event]
    sync      0.92   draw   7.10  gpu   0.22   upload    96.1 KB/frame
    hover changed on 26/40 moves
  select_click n= 40  frame p50    11.12  p95    17.51  max    21.36   (4/40 over 16.7 ms)
    event     1.54 (p95     3.27)  pick     0.00  [cache    0.00, 0.0 rebuilds/event; occl     0.14, 1.0 tests/event]
    sync      1.06   draw   7.90  gpu   0.23   upload    96.1 KB/frame
  topology extrude 1 face         n= 40  frame p50     51.01  max     76.75  (T + 2 moves + release; sync = 3 frames)
    event    15.44 = op    15.43 + history     0.01 + notify   0.01 + hover pick     0.00 [cache    0.00, vertex_faces    0.00]
    sync     4.04  draw   30.59   next hover frame     9.58   undo frame    28.57
  topology extrude 20 faces       n= 40  frame p50     58.40  max     72.06  (T + 2 moves + release; sync = 3 frames)
    event    20.06 = op    20.01 + history     0.04 + notify   0.01 + hover pick     0.00 [cache    0.00, vertex_faces    0.00]
    sync     5.98  draw   31.63   next hover frame     9.73   undo frame    37.58
  topology knife commit, 1 cut    n= 39  frame p50     42.02  max     68.21  (2 clicks, line crosses 3 edges; Enter measured)
    event    30.87 = op    30.85 + history     0.02 + notify   0.00 + hover pick     0.00 [cache    0.11, vertex_faces    0.00]
    sync     1.42  draw   10.15   next hover frame    11.44   undo frame    40.62
  topology dissolve 1 edge        n= 40  frame p50     40.45  max     56.59
    event    29.56 = op    29.55 + history     0.01 + notify   0.00 + hover pick     0.00 [cache    0.06, vertex_faces    0.00]
    sync     0.08  draw    9.85   next hover frame    12.45   undo frame    44.02
  topology delete 1 face          n= 40  frame p50     26.17  max     35.06
    event    16.24 = op    16.23 + history     0.01 + notify   0.00 + hover pick     0.00 [cache    0.00, vertex_faces    0.00]
    sync     1.26  draw    8.80   next hover frame     8.45   undo frame    29.17
  plain_w 36 V  (45 store.update calls/move) OK
    move p50     0.97  p95     1.50  [transform    0.11  sync    0.86 (update    0.18)]  (draw   7.29)
  plain_w 112 V  (56 store.update calls/move) OK
    move p50     2.44  p95     2.83  [transform    0.24  sync    2.17 (update    0.40)]  (draw   9.23)
  plain_w 500 V  (67 store.update calls/move) OVER
    move p50     7.49  p95     8.32  [transform    0.82  sync    6.36 (update    1.06)]  (draw  10.09)
  soft_w r 15 % geodesic: seeds 5 V, moving 508 V  (79 store.update calls/move) OVER
    move p50     5.26  p95     8.21  [transform    0.71  sync    4.49 (update    0.73)]  (draw   8.24)
    once: first move (begin + influence)         p50     29.58
    once: commit frame (release + sync + draw)   p50     45.27
    once: selection click (pick + preview)       p50     22.75
    once: preview recompute (influence + bands)  p50     15.84
    once: settings change (key + sync)           p50     15.20
  soft_w r 50 % geodesic: seeds 5 V, moving 3339 V  (144 store.update calls/move) OVER
    move p50    32.03  p95    45.97  [transform    4.82  sync   27.22 (update    3.38)]  (draw  10.91)
    once: first move (begin + influence)         p50     50.70
    once: commit frame (release + sync + draw)   p50    210.41
    once: selection click (pick + preview)       p50     29.12
    once: preview recompute (influence + bands)  p50     16.54
    once: settings change (key + sync)           p50     17.94

[gollum_87k] 87500 V / 87500 F / 196875 triangles; load + first frame 5634 ms
  orbit        n= 40  frame p50    29.71  p95    37.72  max    45.33   (40/40 over 16.7 ms)
    event     0.05 (p95     0.07)  pick     0.00  [cache    0.00, 0.0 rebuilds/event; occl     0.00, 0.0 tests/event]
    sync      0.06   draw  29.60  gpu   0.70   upload     0.0 KB/frame
  orbit_wire   n= 40  frame p50    61.27  p95    75.09  max    90.21   (40/40 over 16.7 ms)
    event     0.06 (p95     0.08)  pick     0.00  [cache    0.00, 0.0 rebuilds/event; occl     0.00, 0.0 tests/event]
    sync      0.07   draw  61.13  gpu  14.59   upload     0.0 KB/frame
  first_hover  n= 15  frame p50   359.07  p95   474.29  max   474.29   (15/15 over 16.7 ms)
    event   321.28 (p95   432.17)  pick     0.00  [cache  256.31, 1.0 rebuilds/event; occl    19.00, 2.9 tests/event]
    sync      5.65   draw  28.16  gpu   0.76   upload   384.5 KB/frame
  hover_move   n= 40  frame p50    35.27  p95    52.81  max   103.81   (40/40 over 16.7 ms)
    event     2.84 (p95    17.27)  pick     0.00  [cache    0.01, 0.0 rebuilds/event; occl     0.15, 1.9 tests/event]
    sync      3.77   draw  28.17  gpu   0.67   upload   384.5 KB/frame
    hover changed on 31/40 moves
  select_click n= 40  frame p50    32.38  p95    44.26  max    46.64   (40/40 over 16.7 ms)
    event     3.96 (p95     8.81)  pick     0.00  [cache    0.01, 0.0 rebuilds/event; occl     0.82, 6.5 tests/event]
    sync      0.02   draw  27.71  gpu   0.67   upload     0.0 KB/frame
  topology extrude 1 face         n= 17  frame p50    149.49  max    196.98  (T + 2 moves + release; sync = 3 frames)
    event    44.46 = op    44.44 + history     0.01 + notify   0.01 + hover pick     0.00 [cache    0.00, vertex_faces    0.00]
    sync    13.07  draw   90.25   next hover frame    29.59   undo frame    87.61
  topology extrude 20 faces       n= 15  frame p50    151.08  max    187.71  (T + 2 moves + release; sync = 3 frames)
    event    46.84 = op    46.79 + history     0.04 + notify   0.01 + hover pick     0.00 [cache    0.00, vertex_faces    0.00]
    sync    15.41  draw   87.41   next hover frame    35.32   undo frame   132.87
  topology knife commit, 1 cut    n= 12  frame p50    139.02  max    162.01  (2 clicks, line crosses 3 edges; Enter measured)
    event   104.88 = op   104.86 + history     0.02 + notify   0.00 + hover pick     0.00 [cache    0.13, vertex_faces    0.00]
    sync     5.46  draw   29.60   next hover frame    35.09   undo frame   121.06
  topology dissolve 1 edge        n= 15  frame p50    126.32  max    157.25
    event    96.58 = op    96.57 + history     0.01 + notify   0.00 + hover pick     0.00 [cache    0.08, vertex_faces    0.00]
    sync     5.24  draw   30.40   next hover frame    38.27   undo frame   159.95
  topology delete 1 face          n= 21  frame p50     78.43  max     98.47
    event    44.84 = op    44.83 + history     0.01 + notify   0.00 + hover pick     0.00 [cache    0.00, vertex_faces    0.00]
    sync     4.33  draw   25.08   next hover frame    30.43   undo frame    93.24
  plain_w 36 V  (54 store.update calls/move) OK
    move p50     1.34  p95     3.00  [transform    0.17  sync    1.17 (update    0.24)]  (draw  28.35)
  plain_w 112 V  (80 store.update calls/move) OK
    move p50     2.57  p95     3.99  [transform    0.29  sync    2.28 (update    0.43)]  (draw  31.21)
  plain_w 500 V  (120 store.update calls/move) OVER
    move p50     9.16  p95    11.46  [transform    0.99  sync    8.23 (update    1.31)]  (draw  32.72)
  soft_w r 15 % geodesic: seeds 5 V, moving 1921 V  (141 store.update calls/move) OVER
    move p50    23.23  p95    32.83  [transform    3.29  sync   19.94 (update    2.71)]  (draw  30.57)
    once: first move (begin + influence)         p50     72.66
    once: commit frame (release + sync + draw)   p50    195.38
    once: selection click (pick + preview)       p50    100.70
    once: preview recompute (influence + bands)  p50     92.78
    once: settings change (key + sync)           p50     53.32
  soft_w r 50 % geodesic: seeds 5 V, moving 13195 V  (310 store.update calls/move) OVER
    move p50   170.87  p95   237.45  [transform   29.98  sync  139.65 (update   16.03)]  (draw  36.87)
    once: first move (begin + influence)         p50    266.31
    once: commit frame (release + sync + draw)   p50    352.41
    once: selection click (pick + preview)       p50     98.94
    once: preview recompute (influence + bands)  p50    105.25
    once: settings change (key + sync)           p50     86.62
```

## 5. Picking through `Application` (existing probe, after the `_edit_camera` fix)

`xvfb-run -a python experiments/drag_cost/probe_picking_app.py --n 9` and `--n 6 --asset <gollum_87k.obj>`.
Compare `[GPU] vertex / edge first pick` with 15.84 / 21.37 ms in
[`RESULTS_PICKING_APP_CONTAINER_2026-10-21.md`](RESULTS_PICKING_APP_CONTAINER_2026-10-21.md).

```
gollum_20k.obj: 21875 V / 21875 F, 1024x768, GL (4, 5) llvmpipe (LLVM 20.1.2, 256 bits)
[CPU]
  vertex first pick            n=  9  p50    69.59  max   124.31
  vertex hover                 n=  9  p50     3.37  max   149.63
  vertex box 300px             n=  3  p50   996.33  max  1077.03
  edge first pick              n=  9  p50    67.42  max    84.80
  edge hover                   n=  9  p50    12.56  max    35.53
  edge box 300px               n=  3  p50  2100.97  max  2155.41
  face first pick              n=  9  p50    79.54  max    96.73
  face hover                   n=  9  p50     2.70  max     3.01
  face box 300px               n=  3  p50  1248.32  max  1661.45
  delete 1 face + re-pick      n=  9  p50     2.38  max     3.26
[GPU]
  vertex first pick            n=  9  p50    77.27  max    92.88
  vertex hover                 n=  9  p50     1.75  max    28.11
  vertex box 300px             n=  3  p50   139.98  max   177.32
  edge first pick              n=  9  p50   103.78  max   120.13
  edge hover                   n=  9  p50     2.04  max    41.55
  edge box 300px               n=  3  p50   194.47  max   208.96
  face first pick              n=  9  p50    11.49  max    13.33
  face hover                   n=  9  p50     0.02  max     0.02
  face box 300px               n=  3  p50   173.78  max   204.85
  delete 1 face + re-pick      n=  9  p50    16.68  max    19.47
gollum_87k.obj: 87500 V / 87500 F, 1024x768, GL (4, 5) llvmpipe (LLVM 20.1.2, 256 bits)
[CPU]
  vertex first pick            n=  6  p50   348.98  max  1062.09
  vertex hover                 n=  6  p50    11.23  max    11.97
  vertex box 300px             n=  3  p50  7842.06  max  8993.38
  edge first pick              n=  6  p50   439.28  max   545.58
  edge hover                   n=  6  p50    53.65  max    65.52
  edge box 300px               n=  3  p50 13621.98  max 13854.65
  face first pick              n=  6  p50   220.12  max   335.12
  face hover                   n=  6  p50     7.77  max     8.14
  face box 300px               n=  3  p50  6951.00  max  7506.80
  delete 1 face + re-pick      n=  6  p50    13.17  max    13.62
[GPU]
  vertex first pick            n=  6  p50   420.82  max   462.79
  vertex hover                 n=  6  p50     2.87  max     4.63
  vertex box 300px             n=  3  p50   773.62  max   810.86
  edge first pick              n=  6  p50   303.25  max   427.38
  edge hover                   n=  6  p50    13.85  max    61.69
  edge box 300px               n=  3  p50   888.41  max   900.27
  face first pick              n=  6  p50    45.00  max    46.48
  face hover                   n=  6  p50     0.03  max     0.03
  face box 300px               n=  3  p50   597.40  max   607.86
  delete 1 face + re-pick      n=  6  p50    56.94  max    58.87
```

## 6. Symmetry correspondence (scratch timing, not a probe)

`mirai.symmetry.vertex_correspondence(mesh)` with a definition on the plane x = 0, p50 of 3 calls: 928 V
(`Man_With_Shoes_basemesh`) 2.1 ms, 21 875 V 89 ms, 87 500 V 501 ms.
