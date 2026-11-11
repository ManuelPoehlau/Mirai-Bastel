# O0 fixes on the reference PC, 2026-11-11 (audit 2026-11-10 §I.1–§I.3)

Manu's run (Core 2 Quad Q9550, GeForce 9800 GTX, GL 3.3, Windows 10, Python 3.14.2) after the three O0 commits
(`5a739c0` §I.1 picking occlusion, `d1b370a` §I.2 wire from the RenderMesh buffers, `57f3177` §I.3 `highlight_flags`
removed). Raw output as pasted; the commit SHA was not printed by the run, the branch head at the time was `57f3177`.
Report: [`ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md`](../../docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md),
addendum "O0 on the reference PC".

## Comparison [RPC], p50 ms

| Row | 2026-10-21 (AD-022 §11) | 2026-11-10 (audit addendum) | 2026-11-11 (after O0) |
|---|---:|---:|---:|
| `[GPU]` vertex first pick | 6.94 | 167.10 | **11.00** |
| `[GPU]` edge first pick | 8.23 | 164.84 | **12.62** |
| `[GPU]` face first pick | 3.79 | 3.39 | 3.30 |
| `[GPU]` vertex / edge hover | 2.15 / 2.72 | 6.25 / 6.97 (max 52 / 74) | 6.49 / 7.65 (max 10 / 13) |
| `[GPU]` box 300 px vertex / edge / face | 203 / 307 / 405 | 342 / 453 / 434 | 343 / 453 / 432 |
| pose step 20k 15 %, wire off / on | | 96.37 / 181.77 | **93.99 / 95.18** |
| pose step 20k 100 %, wire off / on | | 681.28 / 762.83 | **639.83 / 644.37** |
| pose step 87.5k 15 %, wire off / on | | 399.20 / 728.70 | **391.73 / 398.76** |
| pose step 87.5k 100 %, wire off / on | | 2,815.70 / 3,142.96 | **2,737.65 / 2,742.38** |
| "wire segments" per step (20k 15 % / 87.5k 15 %) | | 80.53 / 329.02 | 0.00 / 0.00 |

Gates of audit §H step 1: the GL tests pass on this driver (39/39, incl. the new wire and picking tests); wire-on rows
equal the wire-off rows (+0.4 % to +1.8 %, the GPU line draw adds 1.7–3 ms to `draw + glFinish`); vertex / edge
first pick is back below one frame (AD-022 §9 abort criterion 1: 16.7 ms) but not at the 2026-10-21 values: 11.0 /
12.6 against 6.9 / 8.2. The hover rows did not change with O0 (6.25 / 6.97 before, 6.49 / 7.65 after); they rose
between 2026-10-21 and 2026-11-10, i.e. with the CPU occlusion rule of the Ngon fix (2026-10-22), not with O0.

## `python -m pytest tests/test_gl_gpu_picking.py tests/test_gl_line_overlay.py -q`

```
.......................................                                                                                            [100%]
=========================================================== warnings summary ============================================================
tests/test_gl_gpu_picking.py::test_the_window_uses_the_gpu_path[compact]
tests/test_gl_gpu_picking.py::test_the_window_uses_the_gpu_path[compact]
tests/test_gl_gpu_picking.py::test_the_window_uses_the_gpu_path[compact]
tests/test_gl_gpu_picking.py::test_the_window_uses_the_gpu_path[compact]
  C:\Users\Manuel\AppData\Local\Programs\Python\Python314\Lib\site-packages\pyglet\libs\win32\com.py:222: DeprecationWarning: 'ctypes._pointer_type_cache' is deprecated and slated for removal in Python 3.19
    _pointer_type_cache[target] = pointer_type

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
39 passed, 4 warnings in 38.61s
```

## `python experiments/drag_cost/probe_picking_app.py`

```
gollum_20k.obj: 21875 V / 21875 F, 1024x768, GL (3, 3) GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
[CPU]
  vertex first pick            n= 15  p50   163.46  max   317.90
  vertex hover                 n= 15  p50    11.26  max    66.75
  vertex box 300px             n=  5  p50  2517.21  max  2530.48
  edge first pick              n= 15  p50   194.77  max   198.73
  edge hover                   n= 15  p50    34.26  max    82.52
  edge box 300px               n=  5  p50  4798.07  max  4882.04
  face first pick              n= 15  p50   147.51  max   149.73
  face hover                   n= 15  p50     6.61  max     8.15
  face box 300px               n=  5  p50  2839.54  max  2848.85
  delete 1 face + re-pick      n= 15  p50     7.67  max     8.63
[GPU]
  vertex first pick            n= 15  p50    11.00  max    14.33
  vertex hover                 n= 15  p50     6.49  max    10.16
  vertex box 300px             n=  5  p50   343.44  max   348.55
  edge first pick              n= 15  p50    12.62  max    15.31
  edge hover                   n= 15  p50     7.65  max    13.24
  edge box 300px               n=  5  p50   452.80  max   468.95
  face first pick              n= 15  p50     3.30  max     6.66
  face hover                   n= 15  p50     0.53  max     0.63
  face box 300px               n=  5  p50   431.64  max   522.89
  delete 1 face + re-pick      n= 15  p50     4.31  max     9.75
```

## `python experiments/drag_cost/probe_scale_audit.py --only split`

```
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_20k] 21875 V, region 15 % = 3281 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           93.99  100 %   (p95 95.29)
  1 skin evaluation (LBS + Mesh writes)             16.07   17.1 %
  2 RenderMesh._sync_geometry, total                75.52   80.3 %
  2a  neighbourhood sets                             4.08    4.3 %
  2b  face normals                                  19.79   21.1 %
  2c  vertex normals                                 9.44   10.0 %
  2d  positions + normals -> mirror -> store        11.21   11.9 %
  2e  face rows (36 floats per face) -> store       25.82   27.5 %
  4 face-data glBufferSubData at draw                1.17    1.2 %
  draw + glFinish                                    4.00
  bytes handed to the store per step               598992  (183 per weighted vertex)
[gollum_20k] 21875 V, region 15 % = 3281 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)           95.18  100 %   (p95 98.26)
  1 skin evaluation (LBS + Mesh writes)             16.62   17.5 %
  2 RenderMesh._sync_geometry, total                76.42   80.3 %
  2a  neighbourhood sets                             4.07    4.3 %
  2b  face normals                                  19.59   20.6 %
  2c  vertex normals                                 9.33    9.8 %
  2d  positions + normals -> mirror -> store        11.34   11.9 %
  2e  face rows (36 floats per face) -> store       26.56   27.9 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                1.09    1.1 %
  draw + glFinish                                    5.71
  bytes handed to the store per step               598992  (183 per weighted vertex)

[gollum_20k] 21875 V, region 100 % = 21875 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          639.83  100 %   (p95 662.75)
  1 skin evaluation (LBS + Mesh writes)            110.14   17.2 %
  2 RenderMesh._sync_geometry, total               514.64   80.4 %
  2a  neighbourhood sets                            27.16    4.2 %
  2b  face normals                                 125.62   19.6 %
  2c  vertex normals                                61.18    9.6 %
  2d  positions + normals -> mirror -> store        69.18   10.8 %
  2e  face rows (36 floats per face) -> store      195.12   30.5 %
  4 face-data glBufferSubData at draw                1.82    0.3 %
  draw + glFinish                                    5.95
  bytes handed to the store per step              3675000  (168 per weighted vertex)
[gollum_20k] 21875 V, region 100 % = 21875 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          644.37  100 %   (p95 657.63)
  1 skin evaluation (LBS + Mesh writes)            112.88   17.5 %
  2 RenderMesh._sync_geometry, total               515.59   80.0 %
  2a  neighbourhood sets                            27.13    4.2 %
  2b  face normals                                 126.79   19.7 %
  2c  vertex normals                                60.72    9.4 %
  2d  positions + normals -> mirror -> store        68.72   10.7 %
  2e  face rows (36 floats per face) -> store      195.08   30.3 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                1.87    0.3 %
  draw + glFinish                                    6.76
  bytes handed to the store per step              3675000  (168 per weighted vertex)

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          391.73  100 %   (p95 421.57)
  1 skin evaluation (LBS + Mesh writes)             67.28   17.2 %
  2 RenderMesh._sync_geometry, total               315.55   80.6 %
  2a  neighbourhood sets                            19.01    4.9 %
  2b  face normals                                  77.66   19.8 %
  2c  vertex normals                                41.63   10.6 %
  2d  positions + normals -> mirror -> store        45.36   11.6 %
  2e  face rows (36 floats per face) -> store      106.39   27.2 %
  4 face-data glBufferSubData at draw                2.04    0.5 %
  draw + glFinish                                   10.18
  bytes handed to the store per step              2304924  (176 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          398.76  100 %   (p95 410.26)
  1 skin evaluation (LBS + Mesh writes)             70.28   17.6 %
  2 RenderMesh._sync_geometry, total               319.65   80.2 %
  2a  neighbourhood sets                            19.27    4.8 %
  2b  face normals                                  79.26   19.9 %
  2c  vertex normals                                41.96   10.5 %
  2d  positions + normals -> mirror -> store        46.01   11.5 %
  2e  face rows (36 floats per face) -> store      107.78   27.0 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                2.01    0.5 %
  draw + glFinish                                   11.94
  bytes handed to the store per step              2304924  (176 per weighted vertex)

[gollum_87k] 87500 V, region 100 % = 87500 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)         2737.65  100 %   (p95 2793.69)
  1 skin evaluation (LBS + Mesh writes)            445.66   16.3 %
  2 RenderMesh._sync_geometry, total              2227.85   81.4 %
  2a  neighbourhood sets                           127.29    4.6 %
  2b  face normals                                 504.85   18.4 %
  2c  vertex normals                                280.30   10.2 %
  2d  positions + normals -> mirror -> store       305.23   11.1 %
  2e  face rows (36 floats per face) -> store      830.99   30.4 %
  4 face-data glBufferSubData at draw                6.34    0.2 %
  draw + glFinish                                   18.59
  bytes handed to the store per step             14700000  (168 per weighted vertex)
[gollum_87k] 87500 V, region 100 % = 87500 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)         2742.38  100 %   (p95 2764.70)
  1 skin evaluation (LBS + Mesh writes)            454.41   16.6 %
  2 RenderMesh._sync_geometry, total              2220.92   81.0 %
  2a  neighbourhood sets                           126.95    4.6 %
  2b  face normals                                 505.62   18.4 %
  2c  vertex normals                                274.51   10.0 %
  2d  positions + normals -> mirror -> store       302.39   11.0 %
  2e  face rows (36 floats per face) -> store      837.90   30.6 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                6.28    0.2 %
  draw + glFinish                                   21.54
  bytes handed to the store per step             14700000  (168 per weighted vertex)
```
