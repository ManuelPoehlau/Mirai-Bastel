# Rohausgabe: Topologie-Operationen auf dem Referenz-PC (Manu, 2026-10-20)

Unverändert aus dem Chat übernommen. Referenz-PC: Core 2 Quad Q9550, GeForce 9800 GTX, Windows 10,
Python 3.14.2, `GL_VERSION` 3.3.0. Jede Zeile nur **n = 3** Stichproben (Median; keine p95-Aussage).
`--profile-top 0`, also **ohne** cProfile-Zerlegung. Ausgewertet in der [README](README.md)
(„Result: topology operations, reference PC“).

```
PS C:\Users\Manuel\Mirai_Bastel> python experiments/drag_cost/probe_navigation_gl.py --assets examples/meshes/gollum_20k.obj --scenarios topology --profile-top 0
... gollum_20k: loading gollum_20k.obj
... gollum_20k: topology
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 40 events per row (at least 5, budget 8 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2898 ms
  topology extrude 1 face         n=  3  frame p50   3064.97  max   3127.34  (T + 2 moves + release; sync = 3 frames)
    event   389.40 = op     0.93 + history   244.33 + notify   0.02 + hover pick   144.22 [cache  137.55, vertex_faces    0.00]
    sync  2604.24  draw   18.86   next hover frame    10.43   undo frame  1813.79
  topology extrude 20 faces       n=  3  frame p50   3598.54  max   3634.08  (T + 2 moves + release; sync = 3 frames)
    event  1124.82 = op    63.76 + history   909.72 + notify   0.02 + hover pick   148.07 [cache  141.82, vertex_faces    0.00]
    sync  2455.04  draw   19.50   next hover frame    11.92   undo frame  1730.56
  topology knife commit, 1 cut    n=  3  frame p50   2360.08  max   2398.15  (2 clicks, line crosses 3 edges; Enter measured)
    event   994.27 = op   205.35 + history   524.68 + notify   0.01 + hover pick   245.17 [cache  138.06, vertex_faces    0.00]
    sync  1286.83  draw   12.23   next hover frame    43.82   undo frame  1991.91
  topology dissolve 1 edge        n=  3  frame p50   1951.36  max   2269.73
    event   784.42 = op    31.76 + history   498.40 + notify   0.01 + hover pick   254.11 [cache  146.35, vertex_faces    0.00]
    sync  1273.99  draw     9.74   next hover frame    46.52   undo frame  1876.72
  topology delete 1 face          n=  3  frame p50   1945.21  max   2004.81
    event   639.68 = op    24.45 + history   465.01 + notify   0.01 + hover pick   147.69 [cache  141.53, vertex_faces    0.00]
    sync  1264.78  draw    12.05   next hover frame     8.99   undo frame  1716.54
```
