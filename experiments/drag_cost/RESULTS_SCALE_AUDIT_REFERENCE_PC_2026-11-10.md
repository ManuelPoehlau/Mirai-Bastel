# Scale audit, reference PC, 2026-11-10 — raw probe outputs

Raw results from Manu's reference-PC runs requested by
[`docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md`](../../docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md)
§J. This is the Windows reference machine, **not** the audit container.

- CPU: Intel Core 2 Quad Q9550 @ 2.83 GHz (4 logical cores)
- GPU: NVIDIA GeForce 9800 GTX / 9800 GTX+; OpenGL 3.3.0
- OS: Windows 10 build 19045
- Python: 3.14.2 for the scale, picking and navigation probes; Python 3.12.10 for the NumPy kernel probe
- NumPy: 2.2.6 under Python 3.12.10; runtime SIMD dispatch disabled for the probe
- Native C: skipped; no `cc`, `gcc` or `clang` on PATH
- Dense asset: `gollum_87k` is `gollum_20k.obj` after one Catmull-Clark step (87,500 vertices / 87,500 quads). It is generated locally and is not committed:
  `python experiments\drag_cost\probe_scale_audit.py --make-dense`

The command transcript does not record the repository commit SHA or working-tree status used for these runs. Do not infer either from the audit's earlier state.

Times are milliseconds. The scale probe reports p50 over 20 pose steps unless stated; the navigation probe reports the statistics shown in its output. Kernel timings are CPU-only and do not include viewport integration, GL upload or drawing.

## 1. Pose-step split and one-time costs

Command:

```powershell
python experiments\drag_cost\probe_scale_audit.py
```

```text
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_20k] 21875 V, region 15 % = 3281 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           96.37  100 %   (p95 127.46)
  1 skin evaluation (LBS + Mesh writes)             16.38   17.0 %
  2 RenderMesh._sync_geometry, total                77.52   80.4 %
  2a  neighbourhood sets                             3.97    4.1 %
  2b  face normals                                  19.87   20.6 %
  2c  vertex normals                                 9.49    9.9 %
  2d  positions + normals -> mirror -> store        11.56   12.0 %
  2e  face rows (36 floats per face) -> store       26.88   27.9 %
  4 face-data glBufferSubData at draw                1.24    1.3 %
  draw + glFinish                                    5.42
  bytes handed to the store per step               598992  (183 per weighted vertex)
[gollum_20k] 21875 V, region 15 % = 3281 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          181.77  100 %   (p95 427.89)
  1 skin evaluation (LBS + Mesh writes)             17.55    9.7 %
  2 RenderMesh._sync_geometry, total                81.74   45.0 %
  2a  neighbourhood sets                             4.31    2.4 %
  2b  face normals                                  20.32   11.2 %
  2c  vertex normals                                 9.68    5.3 %
  2d  positions + normals -> mirror -> store        12.02    6.6 %
  2e  face rows (36 floats per face) -> store       28.77   15.8 %
  3 wire segments (whole mesh)                      80.53   44.3 %
  4 face-data glBufferSubData at draw                1.19    0.7 %
  draw + glFinish                                   34.48
  bytes handed to the store per step               598992  (183 per weighted vertex)

[gollum_20k] 21875 V, region 100 % = 21875 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          681.28  100 %   (p95 1241.53)
  1 skin evaluation (LBS + Mesh writes)            112.82   16.6 %
  2 RenderMesh._sync_geometry, total               553.98   81.3 %
  2a  neighbourhood sets                            28.34    4.2 %
  2b  face normals                                 128.79   18.9 %
  2c  vertex normals                                62.06    9.1 %
  2d  positions + normals -> mirror -> store        70.85   10.4 %
  2e  face rows (36 floats per face) -> store      209.04   30.7 %
  4 face-data glBufferSubData at draw                1.83    0.3 %
  draw + glFinish                                    6.04
  bytes handed to the store per step              3675000  (168 per weighted vertex)
[gollum_20k] 21875 V, region 100 % = 21875 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          762.83  100 %   (p95 969.19)
  1 skin evaluation (LBS + Mesh writes)            111.91   14.7 %
  2 RenderMesh._sync_geometry, total               544.49   71.4 %
  2a  neighbourhood sets                            28.46    3.7 %
  2b  face normals                                 129.83   17.0 %
  2c  vertex normals                                61.19    8.0 %
  2d  positions + normals -> mirror -> store        70.98    9.3 %
  2e  face rows (36 floats per face) -> store      211.97   27.8 %
  3 wire segments (whole mesh)                      83.14   10.9 %
  4 face-data glBufferSubData at draw                1.68    0.2 %
  draw + glFinish                                   34.82
  bytes handed to the store per step              3675000  (168 per weighted vertex)

[gollum_20k] 21875 V / 21875 F, once per session or stage
  load OBJ + scene + first frame                                2746 ms   process     431 MiB (    +47)
  save scene file                                                467 ms   process     274 MiB (   -157)
    file size 11.7 MiB
  parse scene file (scene_from_json, no viewport)                928 ms   process     283 MiB (    +10)
  write one target, offsets on 15 % of the points                405 ms   process     274 MiB (     -9)
  first weight step 0 -> 60 % (builds the mix surface)          2324 ms   process     310 MiB (    +36)
  next weight step (patch) + frame                                94 ms   process     312 MiB (     +1)
  rig + weights on 15 % of the points                            100 ms   process     312 MiB (     +0)
  first pose step (builds the skin surface)                     2536 ms   process     396 MiB (    +84)
  next pose step (patch, morph + skin) + frame                   104 ms   process     398 MiB (     +2)
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          399.20  100 %   (p95 403.87)
  1 skin evaluation (LBS + Mesh writes)             68.43   17.1 %
  2 RenderMesh._sync_geometry, total               321.59   80.6 %
  2a  neighbourhood sets                            18.97    4.8 %
  2b  face normals                                  78.36   19.6 %
  2c  vertex normals                                41.49   10.4 %
  2d  positions + normals -> mirror -> store        45.99   11.5 %
  2e  face rows (36 floats per face) -> store      111.68   28.0 %
  4 face-data glBufferSubData at draw                1.99    0.5 %
  draw + glFinish                                    9.74
  bytes handed to the store per step              2304924  (176 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          728.70  100 %   (p95 1959.87)
  1 skin evaluation (LBS + Mesh writes)             68.51    9.4 %
  2 RenderMesh._sync_geometry, total                323.97   44.5 %
  2a  neighbourhood sets                            18.56    2.5 %
  2b  face normals                                  79.24   10.9 %
  2c  vertex normals                                41.73    5.7 %
  2d  positions + normals -> mirror -> store        46.26    6.3 %
  2e  face rows (36 floats per face) -> store      112.26   15.4 %
  3 wire segments (whole mesh)                     329.02   45.2 %
  4 face-data glBufferSubData at draw                2.04    0.3 %
  draw + glFinish                                  119.48
  bytes handed to the store per step               2304924  (176 per weighted vertex)

[gollum_87k] 87500 V, region 100 % = 87500 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)         2815.70  100 %   (p95 2849.19)
  1 skin evaluation (LBS + Mesh writes)            450.27   16.0 %
  2 RenderMesh._sync_geometry, total              2293.83   81.5 %
  2a  neighbourhood sets                           134.36    4.8 %
  2b  face normals                                 511.49   18.2 %
  2c  vertex normals                               282.91   10.0 %
  2d  positions + normals -> mirror -> store       305.92   10.9 %
  2e  face rows (36 floats per face) -> store      875.54   31.1 %
  4 face-data glBufferSubData at draw                6.56   0.2 %
  draw + glFinish                                   19.13
  bytes handed to the store per step             14700000  (168 per weighted vertex)
[gollum_87k] 87500 V, region 100 % = 87500 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)         3142.96  100 %   (p95 4105.63)
  1 skin evaluation (LBS + Mesh writes)            446.33   14.2 %
  2 RenderMesh._sync_geometry, total               2289.39   72.8 %
  2a  neighbourhood sets                           133.15    4.2 %
  2b  face normals                                 516.32   16.4 %
  2c  vertex normals                               279.73    8.9 %
  2d  positions + normals -> mirror -> store       302.18    9.6 %
  2e  face rows (36 floats per face) -> store      871.02   27.7 %
  3 wire segments (whole mesh)                     344.88   11.0 %
  4 face-data glBufferSubData at draw                6.15    0.2 %
  draw + glFinish                                  133.40
  bytes handed to the store per step             14700000  (168 per weighted vertex)

[gollum_87k] 87500 V / 87500 F, once per session or stage
  load OBJ + scene + first frame                               11665 ms   process    1407 MiB (   +352)
  save scene file                                               1914 ms   process     690 MiB (   -717)
    file size 46.7 MiB
  parse scene file (scene_from_json, no viewport)                3754 ms   process     740 MiB (    +49)
  write one target, offsets on 15 % of the points               1606 ms   process     690 MiB (    -50)
  first weight step 0 -> 60 % (builds the mix surface)          9533 ms   process     909 MiB (   +220)
  next weight step (patch) + frame                               446 ms   process     904 MiB (     -5)
  rig + weights on 15 % of the points                            443 ms   process     912 MiB (     +7)
  first pose step (builds the skin surface)                    11088 ms   process    1261 MiB (   +349)
  next pose step (patch, morph + skin) + frame                   426 ms   process    1263 MiB (     +2)
  SubD preview: refused (SubD aus: schon Stufe 1 hätte mehr als 25000 Flächen)
```

## 2. Picking probe

Command:

```powershell
python experiments\drag_cost\probe_picking_app.py
```

```text
gollum_20k.obj: 21875 V / 21875 F, 1024x768, GL (3, 3) GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
[CPU]
  vertex first pick            n= 15  p50   167.87  max   316.59
  vertex hover                 n= 15  p50    13.33  max   359.23
  vertex box 300px             n=  5  p50  2552.04  max  2564.13
  edge first pick              n= 15  p50   198.26  max   203.79
  edge hover                   n= 15  p50    34.13  max    80.40
  edge box 300px               n=  5  p50  4939.80  max  5012.28
  face first pick              n= 15  p50   147.97  max   153.95
  face hover                   n= 15  p50     7.06  max     8.20
  face box 300px               n=  5  p50  2902.02  max  2922.03
  delete 1 face + re-pick      n= 15  p50     6.81  max     8.88
[GPU]
  vertex first pick            n= 15  p50   167.10  max   173.58
  vertex hover                 n= 15  p50     6.25  max    52.17
  vertex box 300px             n=  5  p50   341.97  max   343.80
  edge first pick              n= 15  p50   164.84  max   186.63
  edge hover                   n= 15  p50     6.97  max    74.21
  edge box 300px               n=  5  p50   453.36  max   539.38
  face first pick              n= 15  p50     3.39  max     7.45
  face hover                 n= 15  p50     0.48  max     0.58
  face box 300px               n=  5  p50   434.02  max   438.98
  delete 1 face + re-pick      n= 15  p50     4.77  max     9.44
```

## 3. NumPy installation and kernel probe

Installation command:

```powershell
py -3.12 -m pip install "numpy<2.3"
```

Installation output:

```text
Collecting numpy<2.3
  Using cached numpy-2.2.6-cp312-cp312-win_amd64.whl.metadata (60 kB)
Using cached numpy-2.2.6-cp312-cp312-win_amd64.whl (12.6 MB)
Installing collected packages: numpy
  WARNING: The scripts f2py.exe and numpy-config.exe are installed in 'C:\Users\Manuel\AppData\Local\Programs\Python\Python312\Scripts' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer, use --no-warn-script-location.
Successfully installed numpy-2.2.6
```

Kernel command:

```powershell
py -3.12 experiments\drag_cost\probe_kernels.py --assets examples\meshes\gollum_20k.obj dense
```

```text
Kernel probe (2026-11-10): production code vs. packed arrays, CPU side only
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
NumPy 2.2.6 (runtime dispatch off: baseline instructions only)
native C skipped: no cc / gcc / clang on PATH

=== gollum_20k.obj: 21875 V, 21875 F ===
production, once: core.Mesh from arrays 680 ms, RenderMesh full build 1461 ms, export_state 415 ms, Mesh.from_state 1768 ms
packed, once: arrays + adjacency + all normals 66 ms, 3.0 MiB
-- visible: 1-ring normals + buffer data for a moved region, ms per step (CPU side, no upload)
   check: max |production vertex normal - packed| = 1.3e-14; all normals of the mesh: NumPy 29.16 ms
  region  V moved | production    flat Py      NumPy   native C
     1 %      218 |       4.90       1.79      0.947          -
     5 %     1093 |      21.68       8.21      2.164          -
    15 %     3281 |      63.09      24.28      7.069          -
    100 %    21875 |     445.25     156.39     29.033          -
-- skin: linear blend skinning of a weighted region, ms per pose step (evaluation only)
  region        V | production      NumPy   native C   max diff
     5 %     1093 |       3.26      0.656          -   0.0e+00
    15 %     3281 |      11.34      2.275          -   0.0e+00
    100 %    21875 |      83.90     20.401          -   0.0e+00
-- morph: one weight step of one target, ms (evaluation only)
  offsets        V | production      NumPy   native C   max diff
    15 %     3281 |       6.22      0.234          -   0.0e+00
    100 %    21875 |      48.04      2.364          -   0.0e+00
-- subd: level 1 of this mesh as the cage = 87500 V / 87500 F, 546875 stencil entries; topology + stencil build 2.31 s
                  | production      NumPy   native C   max diff
       apply_full |     232.69     53.467          -   3.3e-16

=== gollum_87k.obj: 87500 V, 87500 F ===
production, once: core.Mesh from arrays 2816 ms, RenderMesh full build 6515 ms, export_state 1556 ms, Mesh.from_state 7028 ms
packed, once: arrays + adjacency + all normals 307 ms, 12.0 MiB
-- visible: 1-ring normals + buffer data for a moved region, ms per step (CPU side, no upload)
   check: max |production vertex normal - packed| = 3.1e-14; all normals of the mesh: NumPy 129.24 ms
  region  V moved | production    flat Py      NumPy   native C
     1 %      875 |      18.82      10.12      5.968          -
     5 %     4375 |      86.62      36.99     13.004          -
    15 %    13125 |     276.95     105.09     30.711          -
    100 %    87500 |    1950.54     652.77    135.880          -
-- skin: linear blend skinning of a weighted region, ms per pose step (evaluation only)
  region        V | production      NumPy   native C   max diff
     5 %     4375 |      15.65      3.286          -   0.0e+00
    15 %    13125 |      49.48     11.723          -   0.0e+00
    100 %    87500 |     342.73     88.875          -   0.0e+00
-- morph: one weight step of one target, ms (evaluation only)
  offsets        V | production      NumPy   native C   max diff
    15 %    13125 |      29.01      0.891          -   0.0e+00
    100 %    87500 |     201.78     11.774          -   0.0e+00
-- subd: level 1 of this mesh as the cage = 350000 V / 350000 F, 2187500 stencil entries; topology + stencil build 8.97 s
                  | production      NumPy   native C   max diff
       apply_full |     989.34    216.005          -   3.3e-16
```

## 4. Navigation and GL timing

Command:

```powershell
python experiments\drag_cost\probe_navigation_gl.py --assets experiments\drag_cost\_generated\gollum_87k.obj --scenarios orbit orbit_wire plain_w
```

```text
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 40 events per row (at least 5, budget 8 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_87k] 87500 V / 87500 F / 196875 triangles; load + first frame 11882 ms
  orbit        n= 40  frame p50     1.73  p95     2.65  max     5.82   (0/40 over 16.7 ms)
    event     0.03 (p95     0.03)  pick     0.00  [cache    0.00, 0.0 rebuilds/event; occl     0.00, 0.0 tests/event]
    sync      0.04   draw   1.66   gpu   0.76   upload     0.0 KB/frame
  orbit_wire   n= 40  frame p50     6.25  p95     7.11  max    47.56   (1/40 over 16.7 ms)
    event     0.03 (p95     0.06)  pick     0.00  [cache    0.00, 0.0 rebuilds/event; occl     0.00, 0.0 tests/event]
    sync      0.04   draw   6.17   gpu   4.98   upload     0.0 KB/frame
  plain_w 36 V  (42 store.update calls/move) OK
    move p50     2.34  p95     2.67  [transform    0.23  sync    2.09 (update    0.57)]  (draw   6.28)
  plain_w 112 V  (68 store.update calls/move) OK
    move p50     5.23  p95     5.63  [transform    0.46  sync    4.76 (update    1.15)]  (draw   6.23)
  plain_w 500 V  (110 store.update calls/move) OVER
    move p50    17.42  p95    18.22  [transform    1.74  sync   15.71 (update    2.98)]  (draw   6.82)
  profile orbit (20 drag steps + frames):
    total     102.8 ms (incl. GPU wait); top 8 app functions by own time: own ms / cum ms / calls / function
          9.4      11.4       880  errcheck (gl/lib.py:55)
          1.7       2.6      1120  _handle_fromlist (<frozen importlib._bootstrap>:1401)
          1.6       4.7       240  setter_func (graphics/shader.py:571)
          1.3      17.9        20  draw (src/viewport/gl_render_store.py:857)
          0.8       2.2      1120  setter_func (graphics/shader.py:575)
          0.7       1.9       100  basis (src/mirai/viewport/camera.py:231)
          0.7       2.6       100  setter_func (graphics/shader.py:1405)
          0.7       8.6       400  __setitem__ (graphics/shader.py:1405)
  profile zoom (4 notches + frames):
    total    6664.9 ms (incl. GPU wait); top 8 app functions by own time: own ms / cum ms / calls / function
       2457.5    3921.3    350000  _bbox (src/mirai/viewport/picking_cache.py:63)
       1160.2    6002.0         4  refresh (src/mirai/viewport/picking_cache.py:124)
        617.6     617.6   1848449  <method 'get' of 'dict' objects> (~)
        494.3     494.3    350000  project (src/mirai/viewport/camera.py:392)
        397.3     397.3   1750000  <genexpr> (src/mirai/viewport/picking_cache.py:65)
        314.8     314.8    700024  <built-in method builtins.min> (~)
        302.5     464.4         6  _occluded (src/mirai/viewport/picking.py:446)
        292.1     292.1   350010  face_vertices (src/core/mesh.py:961)
  profile first_hover (4 x orbit gesture, then 1 motion + frame; gesture unprofiled):
    total    8869.6 ms (incl. GPU wait); top 8 app functions by own time: own ms / cum ms / calls / function
       2450.3    3907.1    350000  _bbox (src/mirai/viewport/picking_cache.py:63)
       1280.6    1752.4         2  __init__ (src/mirai/viewport/picking_cache.py:332)
       1138.2    5968.6         4  refresh (src/mirai/viewport/picking_cache.py:124)
        726.3     726.3   2201414  <method 'get' of 'dict' objects> (~)
        550.1     2653.1       28  _occluded (src/mirai/viewport/picking.py:446)
        497.8     497.8    350000  project (src/mirai/viewport/camera.py:392)
        412.0     412.0   1050020  <built-in method builtins.min> (~)
        391.1     391.1   1750000  <genexpr> (src/mirai/viewport/picking_cache.py:65)
```

## 5. Readout and limits

### Findings supported by these runs

- **Pose-step split reproduces the audit's central diagnosis on the reference PC.** At 87.5k and a 15 % region, the step is 399.20 ms p50; skin evaluation is 68.43 ms (17.1 %) and `RenderMesh._sync_geometry` is 321.59 ms (80.6 %).
- **The whole-mesh wire rebuild is a separate, large cost.** At 87.5k / 15 %, wire-on adds 329.02 ms to the measured step compared with wire-off. At 20k / 15 %, it adds 85.40 ms. This is consistent with the probe's `wire segments (whole mesh)` row.
- **Whole-mesh deformation is far from interactive in the current path.** At 87.5k, 100 % pose is 2,815.70 ms p50 without wire and 3,142.96 ms with wire.
- **The packed-array NumPy kernels run on the Q9550 under Python 3.12.10.** At 87.5k / 15 %, the CPU-only NumPy timings are 30.711 ms for visible-data preparation, 11.723 ms for skin and 0.891 ms for one target's morph evaluation. These are isolated kernels, not an integrated Mirai frame.
- **The measured numerical outputs match the production reference closely.** Skin and morph max differences are 0.0; normal differences are around 10^-14; SubD stencil evaluation differs by 3.3e-16.
- **Navigation of the 87.5k mesh is fast with wire off in this hidden-window probe.** Orbit is 1.73 ms p50 (GPU timer 0.76 ms); orbit with wire is 6.25 ms p50 (GPU timer 4.98 ms).
- **The picking issue is reproduced in the picking probe.** GPU vertex / edge first-pick p50 is 167.10 / 164.84 ms, while face first-pick is 3.39 ms. The navigation profile also attributes substantial work after zoom/orbit to `PickCache.refresh`, full-vertex projection and bounding-box queries.
- **The dense stage startup cost is significant.** Loading the 87.5k asset and first frame is 11.665 s; first mix construction 9.533 s; first skin-surface construction 11.088 s. The reported process memory reaches 1,407 MiB after load and 1,263 MiB after the next pose step.

### Important boundaries

- The NumPy kernel probe is CPU-only. Its timings do not prove the speed of a complete application frame after integration.
- O2's proposed shader/data-layout change was not implemented or measured here. These runs do not establish its visual equivalence or GPU performance.
- The native C column is absent because no compiler was found on PATH.
- The SubD preview remains refused by the application's 25,000-derived-face guard; the offline kernel probe only measured stencil evaluation.
- Symmetric Soft Selection / symmetric drags on the dense asset were not included.
- The pasted run contains no `pytest` output. It therefore does not establish the main-suite or GL-suite status.
- The application probes used Python 3.14.2; only the NumPy kernel probe used Python 3.12.10. This distinction matters when comparing the runs.
- The code revision SHA and working-tree state were not printed by the commands and are unknown for this record.

For the original audit's first-pass findings and staged recommendation, see its dated addendum:
[`ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md`](../../docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md).
