# Rohausgabe: `topology` mit `--profile-top 15` auf dem Referenz-PC (Manu, 2026-10-20, zweiter Lauf)

Unverändert aus dem Chat übernommen. Referenz-PC: Core 2 Quad Q9550, GeForce 9800 GTX, Windows 10, Python 3.14.2,
`GL_VERSION` 3.3.0. Zweiter Lauf des Szenarios `topology` (erster Lauf: [`RESULTS_TOPOLOGY_REFERENCE_PC_2026-10-20.md`](RESULTS_TOPOLOGY_REFERENCE_PC_2026-10-20.md)),
je Zeile wieder **n = 3**. **Wichtig:** `--profile-top` profiliert in `probe_navigation_gl.py` nur `orbit`, `zoom` und
`first_hover` (`run_profiles`), **nicht** das Szenario `topology`. Die Profile unten sind also CPU-Picker-Profile (mit
cProfile-Aufschlag), keine Zerlegung des Viewport-Neuaufbaus. Die Zerlegung liefert
[`experiments/architecture_audit_probes/probe_topology_sync_split.py`](../architecture_audit_probes/probe_topology_sync_split.py).

```
PS C:\Users\Manuel\Mirai_Bastel> python experiments/drag_cost/probe_navigation_gl.py --assets examples/meshes/gollum_20k.obj --scenarios topology --profile-top 15
... gollum_20k: loading gollum_20k.obj
... gollum_20k: topology
... gollum_20k: profile
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 40 events per row (at least 5, budget 8 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2574 ms
  topology extrude 1 face         n=  3  frame p50   2859.69  max   3129.59  (T + 2 moves + release; sync = 3 frames)
    event   356.78 = op     0.90 + history   210.05 + notify   0.02 + hover pick   146.51 [cache  140.15, vertex_faces    0.00]
    sync  2486.12  draw   32.13   next hover frame    11.67   undo frame  1794.81
  topology extrude 20 faces       n=  3  frame p50   3459.19  max   3477.86  (T + 2 moves + release; sync = 3 frames)
    event  1097.19 = op    63.70 + history   886.80 + notify   0.02 + hover pick   147.69 [cache  141.53, vertex_faces    0.00]
    sync  2344.28  draw   18.28   next hover frame    12.28   undo frame  1777.25
  topology knife commit, 1 cut    n=  3  frame p50   2467.60  max   2468.14  (2 clicks, line crosses 3 edges; Enter measured)
    event  1194.38 = op   211.54 + history   738.75 + notify   0.01 + hover pick   255.03 [cache  148.10, vertex_faces    0.00]
    sync  1262.19  draw    9.86   next hover frame    48.40   undo frame  2343.83
  topology dissolve 1 edge        n=  3  frame p50   1966.40  max   2131.57
    event   716.56 = op    31.91 + history   426.77 + notify   0.01 + hover pick   257.25 [cache  142.96, vertex_faces    0.00]
    sync  1240.43  draw    9.41   next hover frame    91.98   undo frame  2068.80
  topology delete 1 face          n=  3  frame p50   1899.22  max   2001.11
    event   685.25 = op    25.75 + history   505.45 + notify   0.01 + hover pick   149.61 [cache  141.68, vertex_faces    0.00]
    sync  1250.46  draw   28.41   next hover frame    13.38   undo frame  1937.32
  profile orbit (20 drag steps + frames):
    total     176.8 ms (incl. GPU wait); top 15 app functions by own time: own ms / cum ms / calls / function
         12.6      14.7       760  errcheck (gl/lib.py:55)
          1.8      21.8        20  draw (src/viewport/gl_render_store.py:627)
          1.7       2.7       920  _handle_fromlist (<frozen importlib._bootstrap>:1401)
          1.4       4.1       160  setter_func (graphics/shader.py:571)
          0.9       2.6        20  _flush_face_data (src/viewport/gl_render_store.py:442)
          0.8       2.7       100  setter_func (graphics/shader.py:575)
          0.8       9.4       320  __setitem__ (graphics/shader.py:1405)
          0.7       1.8        60  setter_func (graphics/shader.py:567)
          0.6       0.7        20  on_camera_changed (src/viewport/viewport.py:581)
          0.6       2.4        20  _unbind_face_data (src/viewport/gl_render_store.py:483)
          0.6       0.6       920  <built-in method builtins.hasattr> (~)
          0.5      27.9        20  render (src/viewport/viewport.py:645)
          0.5       1.3        40  kelvin_to_rgb (src/viewport/light_rig.py:205)
          0.4       3.2        20  resolve (src/viewport/light_rig.py:227)
          0.4       1.7        60  basis (src/mirai/viewport/camera.py:111)
  profile zoom (4 notches + frames):
    total    2173.3 ms (incl. GPU wait); top 15 app functions by own time: own ms / cum ms / calls / function
        892.1    1540.9         4  refresh (src/mirai/viewport/picking_cache.py:80)
        261.5     261.5    718476  <method 'get' of 'dict' objects> (~)
        200.2     490.8        27  _occluded (src/mirai/viewport/picking.py:375)
        132.0     132.0     87500  project (src/mirai/viewport/camera.py:216)
        112.5     173.1         1  __init__ (src/mirai/viewport/picking_cache.py:166)
        100.3     100.3    437500  <genexpr> (src/mirai/viewport/picking_cache.py:109)
         96.2      96.2    218762  <built-in method builtins.min> (~)
         82.9      82.9    218792  <built-in method builtins.max> (~)
         75.2      75.2     87611  face_vertices (src/core/mesh.py:157)
         54.3    2131.6         4  pick_nearest_vertex (src/mirai/viewport/picking.py:72)
         33.1      33.1     88614  vertex_position (src/core/mesh.py:140)
         22.6      22.6     87506  <built-in method math.floor> (~)
         18.3      18.3        28  all_face_ids (src/core/mesh.py:190)
         14.0      14.0     36638  <method 'append' of 'list' objects> (~)
          7.5       9.8         4  build_highlight_flags (src/viewport/overlay.py:119)
  profile first_hover (4 x orbit gesture, then 1 motion + frame; gesture unprofiled):
    total    1803.5 ms (incl. GPU wait); top 15 app functions by own time: own ms / cum ms / calls / function
        924.9    1586.2         4  refresh (src/mirai/viewport/picking_cache.py:80)
        195.7     195.7    525060  <method 'get' of 'dict' objects> (~)
        132.7     132.7     87500  project (src/mirai/viewport/camera.py:216)
        107.7     107.7    437500  <genexpr> (src/mirai/viewport/picking_cache.py:109)
         85.2      85.2    175008  <built-in method builtins.min> (~)
         75.5      75.5     87522  face_vertices (src/core/mesh.py:157)
         69.6      69.6    175036  <built-in method builtins.max> (~)
         63.1      98.1         4  _occluded (src/mirai/viewport/picking.py:375)
         56.9    1775.3         4  pick_nearest_vertex (src/mirai/viewport/picking.py:72)
         33.8      33.8     87728  vertex_position (src/core/mesh.py:140)
         13.4      13.4        12  all_vertex_ids (src/core/mesh.py:184)
          9.3       9.3         8  all_face_ids (src/core/mesh.py:190)
          8.2      11.4         4  build_highlight_flags (src/viewport/overlay.py:119)
          5.5       5.5       710  <built-in method math.hypot> (~)
          3.3       4.1       216  errcheck (gl/lib.py:55)
```
