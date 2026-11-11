# O2 on the reference PC, 2026-11-11 (audit 2026-11-10 §H step 4)

Manu's run (Core 2 Quad Q9550, GeForce 9800 GTX, GL 3.3.0, Windows 10, Python 3.14.2 **without `imgui-bundle`**, so the
D3 rows draw no panels) after O2 (`58f7052`, docs `b143946`). Raw output as pasted below. Container counterpart:
[`RESULTS_O2_CONTAINER_2026-11-11.md`](RESULTS_O2_CONTAINER_2026-11-11.md); decision record:
[AD-018 addendum 2026-11-11](../../docs/architecture/AD-018-PRODUCTION-DRAW-BINDING.md); report: audit addendum
"O2 on the reference PC".

The D3 probe on the O2 code came in a second paste (section "D3 after O2" below, at `b8f5a43` with the `on_draw`
split; "working tree MODIFIED" there is the local state of that checkout, not a code change of this branch).

## Results [RPC]

| | before O2 | after O2 |
|---|---:|---:|
| GL tests in their own process (incl. `test_gl_face_data_layout.py`, the pixel identity to the pre-O2 path) | 165 passed (container) | **165 passed** on this driver |
| pose-step split, 87.5k, 15 %, wire off: step p50 (p95) | 391.73 (421.57), after O0 | **299.17 (330.93)** |
| the same, wire ON | 398.76 (410.26) | **294.02 (298.86)** |
| of it: face data → store, wire off | 106.39 (27.2 %) | **22.34 (7.5 %)** |
| of it: face normals / vertex normals / positions + normals / neighbourhood | 77.66 / 41.63 / 45.36 / 19.01 | 75.19 / 40.13 / 46.65 / 19.14 |
| skin evaluation | 67.28 | 66.76 |
| face-data `glBufferSubData` at draw | 2.04 | 1.00 |
| draw + `glFinish` of that step, wire off / on | 10.18 / 11.94 | 5.57 / 10.84 |
| bytes per step | 2,304,924 | **556,940** |
| orbit 87.5k (navigation probe): frame p50 / p95, GPU timer | 1.73 / 2.65, **0.76** (2026-11-10) | 4.08 / 6.06, **2.76** |
| orbit with wire: frame p50, GPU timer | 6.25, 4.98 (2026-11-10, before O0's wire) | 6.32, 4.71 |
| D3 frame, pose / weight, wire off, p50 (p95) | 426.37 (433.35) / 506.38 (516.11) | **352.98 (360.14) / 431.05 (440.80)** |
| D3 frame, pose / weight, wire ON, p50 (p95) | 441.46 (445.55) / 514.13 (521.93) | **366.33 (451.47) / 424.99 (444.58)** |

**Reading.**

1. **Pixel identity holds on the 9800 GTX driver.** `tests/test_gl_face_data_layout.py` (16 scenes, production path
   against the frozen pre-O2 shader, byte-identical required) is among the 165 passing GL tests.
2. **The deformation step is 23–26 % faster** (92–105 ms per step at 87.5k / 15 %): the face-data part fell from 106 to
   22 ms (×4.8) and its bytes by 89 %; every other part is unchanged within ±3 %, as it should be. The remaining step is
   per-vertex Python work O2 does not touch (skin 67, face normals 75, positions + normals 47, vertex normals 40,
   neighbourhood 19 ms) — O1 / O3.
3. **The shaded pass costs about 2 ms more GPU time** at 87.5k in this 1024×768 window: GPU timer 0.76 → 2.76 ms, orbit
   frame 1.73 → 4.08 ms p50 (0 of 40 frames over 16.7 ms). This is the price of the dependent texel fetches (a
   Smooth-quad fragment: 27 fetches, 24 of them single `R32F`, instead of 10 `RGBA32F`), which llvmpipe did not show.
   During a deformation the draw got cheaper (10.18 → 5.57 ms) because 89 % fewer face bytes go through the driver.
   The 2026-11-10 value predates O0, but O0 changed nothing in the shaded pass (the removed `highlight_flags` buffer was
   not read by the shader). Assessment: acceptable now — the CPU part of a deformation step (≈ 300 ms) is about 100 times
   the shaded pass's GPU time; the GPU time scales with covered pixels, so a full-screen window pays more. If it ever limits a frame, the cheapest
   lever would have been three times fewer fetches through `RGB32F` buffer textures — **this driver does not offer
   `GL_ARB_texture_buffer_object_rgb32`** (`False 3.3.0`, second paste).
4. **D3 [RPC]: 73–89 ms p50 faster per frame, still 10–13× over the bar.** The tick (evaluation + sync) fell by
   about 89 ms (pose: 390.98 → 302.42; `_sync_geometry` 313.48 → 224.66, of it face data 107.58 → 22.34), but
   `on_draw` **rose** by about 15 ms (pose 34.90 → 50.11, weight 64.27 → 79.67). Its split after O2 (pose, wire off):
   viewport render 3.59 ms CPU, gizmo / bones 0.99, HUD 1.13, triad 0.42 — and 44.18 ms "rest", i.e. waiting in
   `glFinish` for the GPU. So a D3 frame keeps the GPU busy ≈ 44 ms after O2 against ≈ 28 ms before (on_draw minus its
   CPU parts), although the split probe's draw got faster (10.18 → 5.57 ms) and an orbit costs only +2 ms. **Unexplained;
   diagnosis below.** The hypothesis: the vertex buffers are updated every frame (pyglet re-uploads the whole vertex
   list's positions and normals, ≈ 2.4 MB at 87.5k) while they are attached to the new buffer textures, and this driver
   synchronises or copies for that.
5. **HUD during the weight drag [RPC]: 24.5 ms per frame** (pose drag: 1.1 ms), the gizmo / bones 6.9 ms (pose: 1.0) —
   the weight read-out changes every frame. Size-independent, outside O2; a small fix of its own.

## Diagnosis of the GPU wait (commands, PowerShell, after `git pull`)

The D3 probe now times every `GLRenderStore.draw` on the GPU (GL_TIME_ELAPSED: the vertex-buffer upload, then the draw)
and can swap the buffer textures (`--vertex-textures`): `live` = production; `copy` = the same fetches from a one-time
copy of the vertex buffers that the per-frame updates do not touch (the image goes stale, the timing stays valid);
`off` = no face data (the old per-triangle shading, no buffer textures). Pose rows only, about 1.5 minutes each:
```
python experiments\drag_cost\probe_d3_acceptance.py --interactions pose --vertex-textures live
python experiments\drag_cost\probe_d3_acceptance.py --interactions pose --vertex-textures copy
python experiments\drag_cost\probe_d3_acceptance.py --interactions pose --vertex-textures off
```
Reading: if `copy` brings the GPU wait back to about the `off` level, the cost is the overlap of updates and buffer
textures (fix: let the shader read a separate copy that the store updates itself, or update the attribute buffers
differently); if `copy` stays at the `live` level, it is the fetches themselves.

## Raw output (Manu, pasted)

```
PS C:\Users\Manuel\Mirai_Bastel> python -m pytest (Get-ChildItem tests\test_gl_*.py) -q
.................................................................................................................................. [ 78%]
...................................                                                                                                [100%]
=========================================================== warnings summary ============================================================
tests/test_gl_attach.py: 4 warnings
tests/test_gl_hud_marks.py: 87 warnings
  C:\Users\Manuel\AppData\Local\Programs\Python\Python314\Lib\site-packages\pyglet\libs\win32\com.py:222: DeprecationWarning: 'ctypes._pointer_type_cache' is deprecated and slated for removal in Python 3.19
    _pointer_type_cache[target] = pointer_type

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
165 passed, 91 warnings in 492.58s (0:08:12)
PS C:\Users\Manuel\Mirai_Bastel> git worktree add ..\mirai-pre-o2 23faef5
Preparing worktree (detached HEAD 23faef5)
Updating files: 100% (1228/1228), done.
HEAD is now at 23faef5 probe(drag_cost): D3 acceptance probe - complete frame, jaw region, Morph + Skin
PS C:\Users\Manuel\Mirai_Bastel> Push-Location ..\mirai-pre-o2; python experiments\drag_cost\probe_d3_acceptance.py; Pop-Location
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit 23faef5642, working tree clean
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

Panels aus: imgui-bundle fehlt (pip install -r requirements-dev.txt)
[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels off
  timed: GLRenderStore._flush_face_data, MixSurface._recompute, RenderMesh._sync_geometry, RenderMesh._upload_rows, SkinSurface._recompute, Viewport._sync_edges

  pose   wire off  frame  p50   426.37  p95   433.35  max   442.54 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.25  p95     0.28
    tick (update_viewport)                   p50   390.98  p95   397.02
    on_draw + glFinish                       p50    34.90  p95    37.23
      stage evaluation (mix + skin)          p50    68.47  p95    69.65
      RenderMesh._sync_geometry (all meshes) p50   313.48  p95   319.17
        of it: face data -> store            p50   107.58  p95   110.04
        face-data upload at draw             p50     1.98  p95     2.42
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)

  weight wire off  frame  p50   506.38  p95   516.11  max   650.77 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.10  p95     0.12
    tick (update_viewport)                   p50   442.22  p95   449.32
    on_draw + glFinish                       p50    64.27  p95    69.82
      stage evaluation (mix + skin)          p50   110.80  p95   112.09
      RenderMesh._sync_geometry (all meshes) p50   315.31  p95   321.57
        of it: face data -> store            p50   109.27  p95   113.74
        face-data upload at draw             p50     2.00  p95     2.35
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)

  pose   wire ON   frame  p50   441.46  p95   445.55  max   469.52 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.26  p95     0.31
    tick (update_viewport)                   p50   403.83  p95   407.53
    on_draw + glFinish                       p50    37.31  p95    39.45
      stage evaluation (mix + skin)          p50    68.99  p95    69.87
      RenderMesh._sync_geometry (all meshes) p50   325.92  p95   329.25
        of it: face data -> store            p50   114.09  p95   116.35
        face-data upload at draw             p50     2.01  p95     2.38
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)

  weight wire ON   frame  p50   514.13  p95   521.93  max  1548.93 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.10  p95     0.13
    tick (update_viewport)                   p50   447.86  p95   453.98
    on_draw + glFinish                       p50    66.08  p95    69.82
      stage evaluation (mix + skin)          p50   110.83  p95   112.37
      RenderMesh._sync_geometry (all meshes) p50   320.45  p95   324.17
        of it: face data -> store            p50   110.91  p95   113.40
        face-data upload at draw             p50     1.98  p95     2.24
    bytes to the GL store per frame            2304924  (vertex 335580, face data 1969344; 176 per region vertex)
PS C:\Users\Manuel\Mirai_Bastel> git worktree remove ..\mirai-pre-o2
PS C:\Users\Manuel\Mirai_Bastel> python experiments\drag_cost\probe_scale_audit.py --only split --assets dense --regions 15
Scale audit probe (2026-11-10): pose-step split and one-time stage costs
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2

[gollum_87k] 87500 V, region 15 % = 13125 V, wire off, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          299.17  100 %   (p95 330.93)
  1 skin evaluation (LBS + Mesh writes)             66.76   22.3 %
  2 RenderMesh._sync_geometry, total               221.39   74.0 %
  2a  neighbourhood sets                            19.14    6.4 %
  2b  face normals                                  75.19   25.1 %
  2c  vertex normals                                40.13   13.4 %
  2d  positions + normals -> mirror -> store        46.65   15.6 %
  2e  face data -> store (O2: face normals)         22.34    7.5 %
  4 face-data glBufferSubData at draw                1.00    0.3 %
  draw + glFinish                                    5.57
  bytes handed to the store per step               556940  (42 per weighted vertex)
[gollum_87k] 87500 V, region 15 % = 13125 V, wire ON, 20 pose steps, p50 ms
  step (pointer_motion + update_viewport)          294.02  100 %   (p95 298.86)
  1 skin evaluation (LBS + Mesh writes)             67.87   23.1 %
  2 RenderMesh._sync_geometry, total               216.92   73.8 %
  2a  neighbourhood sets                            18.80    6.4 %
  2b  face normals                                  74.74   25.4 %
  2c  vertex normals                                39.61   13.5 %
  2d  positions + normals -> mirror -> store        45.88   15.6 %
  2e  face data -> store (O2: face normals)         21.79    7.4 %
  3 wire segments (whole mesh)                       0.00    0.0 %
  4 face-data glBufferSubData at draw                0.90    0.3 %
  draw + glFinish                                   10.84
  bytes handed to the store per step               556940  (42 per weighted vertex)
PS C:\Users\Manuel\Mirai_Bastel> python experiments\drag_cost\probe_navigation_gl.py --assets experiments\drag_cost\fixtures\gollum_87k.obj --scenarios orbit orbit_wire
... gollum_87k: loading gollum_87k.obj
... gollum_87k: orbit
... gollum_87k: orbit_wire
... gollum_87k: profile
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 40 events per row (at least 5, budget 8 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_87k] 87500 V / 87500 F / 196875 triangles; load + first frame 10802 ms
  orbit        n= 40  frame p50     4.08  p95     6.06  max    12.28   (0/40 over 16.7 ms)
    event     0.03 (p95     0.05)  pick     0.00  [cache    0.00, 0.0 rebuilds/event; occl     0.00, 0.0 tests/event]
    sync      0.04   draw   4.01  gpu   2.76   upload     0.0 KB/frame
  orbit_wire   n= 40  frame p50     6.32  p95     7.30  max    16.98   (1/40 over 16.7 ms)
    event     0.03 (p95     0.05)  pick     0.00  [cache    0.00, 0.0 rebuilds/event; occl     0.00, 0.0 tests/event]
    sync      0.05   draw   6.23  gpu   4.71   upload     0.0 KB/frame
  profile orbit (20 drag steps + frames):
    total     104.1 ms (incl. GPU wait); top 8 app functions by own time: own ms / cum ms / calls / function
         11.9      14.8      1220  errcheck (gl/lib.py:55)
          2.3       3.4      1480  _handle_fromlist (<frozen importlib._bootstrap>:1401)
          2.0       5.7       320  setter_func (graphics/shader.py:571)
          1.3      23.4        20  draw (src/viewport/gl_render_store.py:924)
          1.0       3.9        20  _unbind_face_data (src/viewport/gl_render_store.py:752)
          0.9       2.7        20  _flush_face_data (src/viewport/gl_render_store.py:673)
          0.8       9.9       480  __setitem__ (graphics/shader.py:1405)
          0.7       1.9        20  _bind_vertex_textures (src/viewport/gl_render_store.py:715)
  profile zoom (4 notches + frames):
    total     140.3 ms (incl. GPU wait); top 8 app functions by own time: own ms / cum ms / calls / function
         30.3      32.9         8  _read (src/viewport/gpu_picker.py:254)
         20.3      20.3      2683  <built-in method math.hypot> (~)
          8.8     113.0         4  gpu_pick_component (src/mirai/viewport/gpu_picking.py:49)
          7.8       9.0       548  errcheck (gl/lib.py:55)
          4.5       4.5      2683  project (src/mirai/viewport/camera.py:392)
          4.5      27.3        94  point_occluded_by (src/mirai/viewport/picking.py:414)
          3.9      13.0       397  triangulate_face (src/viewport/derived.py:105)
          3.3       4.7      2683  vertex_of_slot (src/viewport/render_mesh.py:352)
  profile first_hover (4 x orbit gesture, then 1 motion + frame; gesture unprofiled):
    total     179.5 ms (incl. GPU wait); top 8 app functions by own time: own ms / cum ms / calls / function
         39.0      41.9         8  _read (src/viewport/gpu_picker.py:254)
         21.0      21.0      2768  <built-in method math.hypot> (~)
          9.2     154.9         4  gpu_pick_component (src/mirai/viewport/gpu_picking.py:49)
          8.4      52.4       188  point_occluded_by (src/mirai/viewport/picking.py:414)
          7.6       8.9       548  errcheck (gl/lib.py:55)
          7.3      25.6       740  triangulate_face (src/viewport/derived.py:105)
          5.2       5.9       740  _newell (src/viewport/derived.py:76)
          5.1       5.6      1442  _ray_triangle_intersection (src/mirai/viewport/picking.py:212)
```

## D3 after O2 and the extension check (Manu, second paste)

```
PS C:\Users\Manuel\Mirai_Bastel> python experiments\drag_cost\probe_d3_acceptance.py
D3 acceptance probe (2026-11-11): complete frame, jaw region, Morph + Skin active
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit b8f5a43a37, working tree MODIFIED
Run: hidden 1024x768 window, 60 frames per row after 6 unmeasured; bar (D3): p95 <= 33.3 ms minimum, <= 16.7 ms preferred

Panels aus: imgui-bundle fehlt (pip install -r requirements-dev.txt)
[gollum_87k] 87500 V / 87500 F; region 15 %: 13125 V weighted, 13125 V in the morph target at 60 %; panels off
  timed: Application.bone_items, Application.gizmo_items, Application.pivot_marker_items, GLRenderStore._flush_face_data, Hud.draw, Hud.update, ImguiLayer.draw, MixSurface._recompute, OrientationTriad.draw, RenderMesh._sync_geometry, RenderMesh._upload_face_normals, SkinSurface._recompute, Viewport._sync_edges, Viewport.render, main.draw_gizmo

  pose   wire off  frame  p50   352.98  p95   360.14  max   377.06 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.24  p95     0.27
    tick (update_viewport)                   p50   302.42  p95   308.89
    on_draw + glFinish                       p50    50.11  p95    52.09
      tick: stage evaluation (mix + skin)    p50    68.74  p95    70.22
      tick: RenderMesh._sync_geometry        p50   224.66  p95   229.40
        of it: face data -> store            p50    22.34  p95    23.44
      draw: viewport render (faces, wire, overlays) p50     3.59  p95     4.03
        of it: face-data upload              p50     0.86  p95     1.06
      draw: gizmo / bones                    p50     0.99  p95     1.28
      draw: HUD                              p50     1.13  p95     1.25
      draw: triad                            p50     0.42  p95     0.61
      draw: rest (clear, sync, GPU wait)     p50    44.18  p95    46.22
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire off  frame  p50   431.05  p95   440.80  max  1488.27 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.10  p95     0.12
    tick (update_viewport)                   p50   351.49  p95   356.93
    on_draw + glFinish                       p50    79.67  p95    84.51
      tick: stage evaluation (mix + skin)    p50   110.15  p95   112.53
      tick: RenderMesh._sync_geometry        p50   225.46  p95   227.57
        of it: face data -> store            p50    22.81  p95    23.51
      draw: viewport render (faces, wire, overlays) p50     3.60  p95     4.29
        of it: face-data upload              p50     0.86  p95     1.01
      draw: gizmo / bones                    p50     6.87  p95     7.41
      draw: HUD                              p50    24.51  p95    31.26
      draw: triad                            p50     0.45  p95     0.56
      draw: rest (clear, sync, GPU wait)     p50    44.05  p95    47.10
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  pose   wire ON   frame  p50   366.33  p95   451.47  max   933.38 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.25  p95     0.31
    tick (update_viewport)                   p50   313.54  p95   343.78
    on_draw + glFinish                       p50    52.90  p95    81.77
      tick: stage evaluation (mix + skin)    p50    70.57  p95    77.70
      tick: RenderMesh._sync_geometry        p50   232.82  p95   263.95
        of it: face data -> store            p50    23.37  p95    25.42
      draw: viewport render (faces, wire, overlays) p50     4.10  p95     5.06
        of it: face-data upload              p50     0.85  p95     1.16
      draw: gizmo / bones                    p50     1.13  p95     1.30
      draw: HUD                              p50     1.17  p95     1.45
      draw: triad                            p50     0.46  p95     0.57
      draw: rest (clear, sync, GPU wait)     p50    45.99  p95    73.71
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)

  weight wire ON   frame  p50   424.99  p95   444.58  max   462.30 ms   [OVER 33.3]
    input (pointer_motion)                   p50     0.10  p95     0.12
    tick (update_viewport)                   p50   357.43  p95   368.83
    on_draw + glFinish                       p50    66.41  p95    85.51
      tick: stage evaluation (mix + skin)    p50   111.45  p95   116.31
      tick: RenderMesh._sync_geometry        p50   229.45  p95   237.01
        of it: face data -> store            p50    23.06  p95    24.94
      draw: viewport render (faces, wire, overlays) p50     4.07  p95     4.74
        of it: face-data upload              p50     0.86  p95     1.08
      draw: gizmo / bones                    p50     6.85  p95     7.48
      draw: HUD                              p50    24.63  p95    26.12
      draw: triad                            p50     0.48  p95     0.62
      draw: rest (clear, sync, GPU wait)     p50    29.13  p95    48.64
    bytes to the GL store per frame             556940  (vertex 335580, face data 221360; 42 per region vertex)
PS C:\Users\Manuel\Mirai_Bastel> python -c "import pyglet; w = pyglet.window.Window(visible=False); from pyglet.gl import gl_info; print(gl_info.have_extension('GL_ARB_texture_buffer_object_rgb32'), gl_info.get_version_string())"
False 3.3.0
```

