# Raw outputs, reference PC (Manu), 2026-10-21

`probe_stage1.py`, `gollum_20k`, `--steps 20 --row-seconds 240`, GC on (default). Runs 1 and 2 in PowerShell
(Python 3.14.2), run 3 in PyCharm (Python 3.12.10, venv `.venv_np312`). Copied from Manu's message; the progress lines and, in runs 2 and 3, the repeated title line are left out.

## Run 1: `--stage1 none` (Python 3.14.2)

```text
AD-023 stage 1 switches: none (baseline: unchanged code)
Split probe options: --gc on --history-depth 0 (GC threshold (2000, 10, 0))
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 20 events per row (at least 5, budget 240 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2662 ms
  topology extrude 1 face         n= 20  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50   2990.00  p95   3083.29  max   3169.27
      op                       p50      0.79  p95      0.93  max      0.97
      history                  p50    280.16  p95    507.01  max    510.77
      hover re-pick            p50    144.70  p95    146.58  max    148.52
      viewport sync            p50   2535.97  p95   2569.41  max   2610.11
    next hover frame           p50     11.80  p95     12.61  max     12.76
    undo frame                 p50   1794.97  p95   1908.32  max   2057.11
    op + undo                  p50   4792.67  p95   4874.37  max   4926.89
  topology extrude 20 faces       n= 20  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50   3701.84  p95   3766.81  max   3804.74
      op                       p50     62.64  p95     70.84  max     74.40
      history                  p50    916.94  p95   1002.60  max   1008.19
      hover re-pick            p50    148.48  p95    154.44  max    163.25
      viewport sync            p50   2557.11  p95   2637.87  max   2711.34
    next hover frame           p50     13.11  p95     14.90  max     16.18
    undo frame                 p50   1803.96  p95   1970.60  max   1974.77
    op + undo                  p50   5499.72  p95   5679.22  max   5775.34
  topology knife commit, 1 cut    n= 20  (2 clicks, line crosses 3 edges; Enter measured)
    frame (op as triggered)    p50   2335.23  p95   2447.68  max   2460.74
      op                       p50    207.31  p95    210.39  max    212.25
      history                  p50    681.52  p95    783.83  max    786.58
      hover re-pick            p50    246.59  p95    249.40  max    251.68
      viewport sync            p50   1195.63  p95   1374.90  max   1386.53
    next hover frame           p50     45.20  p95     46.58  max     46.97
    undo frame                 p50   2006.26  p95   2070.34  max   2110.06
    op + undo                  p50   4370.58  p95   4465.46  max   4509.07
  topology dissolve 1 edge        n= 20
    frame (op as triggered)    p50   1929.77  p95   2017.53  max   2041.79
      op                       p50     29.32  p95     30.06  max     32.37
      history                  p50    434.64  p95    488.95  max    510.67
      hover re-pick            p50    238.46  p95    242.85  max    252.21
      viewport sync            p50   1203.28  p95   1319.96  max   1427.40
    next hover frame           p50     47.42  p95     48.06  max     49.30
    undo frame                 p50   1925.89  p95   2074.32  max   2107.59
    op + undo                  p50   3829.19  p95   3994.35  max   3998.00
  topology delete 1 face          n= 20
    frame (op as triggered)    p50   1835.48  p95   1942.20  max   2052.17
      op                       p50     24.88  p95     25.83  max     26.70
      history                  p50    434.23  p95    471.27  max    473.33
      hover re-pick            p50    147.79  p95    151.12  max    151.44
      viewport sync            p50   1268.16  p95   1404.21  max   1409.57
    next hover frame           p50      8.96  p95     10.30  max     10.35
    undo frame                 p50   1857.28  p95   1917.14  max   1930.93
    op + undo                  p50   3665.95  p95   3859.34  max   3864.76

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                             246   307330.7   1249.31
    DerivedGeometry.full_recompute (adjacency + all normals)            248    73399.3    295.97
    RenderMesh._rebuild_index_mapping (index map + triangulation)       247   131411.9    532.03
      triangulate_mesh_face (all calls)                              5404285   115835.2      0.02
    RenderMesh._rebuild_resources (flatten + upload)                    247   104062.4    421.31
      GLRenderStore.allocate                                           1729     1645.7      0.95
      GLRenderStore.update                                             6025    16497.3      2.74
      GLRenderStore.end_rebuild (VertexList creation)                   247    17663.2     71.51
  Mesh.export_state                                                     306    45657.2    149.21
  Mesh.load_state                                                       120    49054.1    408.78
  PickCache.refresh (only when the signature changed: see calls)        718    29032.4     40.44

Stage-1 counters (whole run incl. warm-up and undo frames): topology syncs 0 (full buffer rebuilds 0, V2 patch syncs 0); faces re-triangulated 0, reused 0; H0: changed by counts 0, full-compare fallbacks 0, lazy after-exports at Undo 0
```

## Run 2: `--stage1 all` (Python 3.14.2)

```text
AD-023 stage 1 switches: H0,V0,V2,V3
Split probe options: --gc on --history-depth 0 (GC threshold (2000, 10, 0))
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 20 events per row (at least 5, budget 240 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2485 ms
  topology extrude 1 face         n= 20  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50   1016.95  p95   1039.20  max   1051.22
      op                       p50      0.78  p95      0.92  max      1.00
      history                  p50    423.91  p95    475.34  max    478.61
      hover re-pick            p50    148.90  p95    152.47  max    167.41
      viewport sync            p50    402.98  p95    411.29  max    418.68
    next hover frame           p50     12.93  p95     14.37  max     14.50
    undo frame                 p50    983.10  p95   1068.57  max   1100.52
    op + undo                  p50   1884.77  p95   2035.04  max   2063.91
  topology extrude 20 faces       n= 20  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50   1585.78  p95   1735.20  max   1752.82
      op                       p50     65.76  p95     66.79  max     68.69
      history                  p50    919.44  p95   1068.30  max   1080.84
      hover re-pick            p50    155.61  p95    159.21  max    159.72
      viewport sync            p50    428.97  p95    439.44  max    451.17
    next hover frame           p50     14.53  p95     16.11  max     16.11
    undo frame                 p50   1019.38  p95   1091.27  max   1125.35
    op + undo                  p50   2609.55  p95   2732.58  max   2744.58
  topology knife commit, 1 cut    n= 20  (2 clicks, line crosses 3 edges; Enter measured)
    frame (op as triggered)    p50   1525.96  p95   1764.76  max   1837.43
      op                       p50    212.18  p95    216.20  max    240.30
      history                  p50    694.26  p95    944.81  max    996.83
      hover re-pick            p50    259.71  p95    263.51  max    264.26
      viewport sync            p50    348.96  p95    354.50  max    375.62
    next hover frame           p50     44.96  p95     47.11  max     47.16
    undo frame                 p50   1124.95  p95   1244.40  max   1315.93
    op + undo                  p50   2644.75  p95   2984.26  max   2991.86
  topology dissolve 1 edge        n= 20
    frame (op as triggered)    p50    765.52  p95    928.40  max    988.53
      op                       p50     37.84  p95     38.78  max     40.54
      history                  p50    124.75  p95    294.84  max    350.34
      hover re-pick            p50    248.31  p95    250.30  max    251.15
      viewport sync            p50    344.16  p95    348.41  max    348.67
    next hover frame           p50     47.53  p95     48.80  max     49.06
    undo frame                 p50   1244.71  p95   1367.15  max   1439.93
    op + undo                  p50   2062.80  p95   2198.25  max   2218.21
  topology delete 1 face          n= 20
    frame (op as triggered)    p50    666.80  p95    919.23  max    932.12
      op                       p50     30.17  p95     32.07  max     32.47
      history                  p50    125.62  p95    383.83  max    389.88
      hover re-pick            p50    153.40  p95    156.13  max    157.91
      viewport sync            p50    345.34  p95    354.53  max    360.87
    next hover frame           p50     10.36  p95     11.65  max     11.71
    undo frame                 p50   1247.91  p95   1315.70  max   1316.79
    op + undo                  p50   1950.42  p95   2067.04  max   2090.26

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                             246    72579.7    295.04
    DerivedGeometry.full_recompute (adjacency + all normals)              1      267.7    267.67
    RenderMesh._rebuild_index_mapping (index map + triangulation)         0        0.0      0.00
      triangulate_mesh_face (all calls)                                   0        0.0      0.00
    RenderMesh._rebuild_resources (flatten + upload)                    201    51951.2    258.46
      GLRenderStore.allocate                                           1407     1080.7      0.77
      GLRenderStore.update                                             9509    13207.0      1.39
      GLRenderStore.end_rebuild (VertexList creation)                   201    14503.0     72.15
  Mesh.export_state                                                     306    44958.7    146.92
  Mesh.load_state                                                       120    57767.8    481.40
  PickCache.refresh (only when the signature changed: see calls)        718    29979.9     41.75

Stage-1 counters (whole run incl. warm-up and undo frames): topology syncs 246 (full buffer rebuilds 201, V2 patch syncs 46); faces re-triangulated 24575, reused 5379710; H0: changed by counts 40, full-compare fallbacks 0, lazy after-exports at Undo 40
```

## Run 3: `--stage1 all` (Python 3.12.10, PyCharm)

```text
AD-023 stage 1 switches: H0,V0,V2,V3
Split probe options: --gc on --history-depth 0 (GC threshold (700, 10, 10))
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 20 events per row (at least 5, budget 240 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 3141 ms
  topology extrude 1 face         n= 20  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50   1395.09  p95   1426.56  max   1438.99
      op                       p50      0.75  p95      0.84  max      0.85
      history                  p50    831.49  p95    865.10  max    868.90
      hover re-pick            p50    152.28  p95    155.62  max    157.75
      viewport sync            p50    394.26  p95    401.70  max    407.62
    next hover frame           p50     12.52  p95     13.38  max     14.30
    undo frame                 p50   1588.13  p95   2006.01  max   2497.29
    op + undo                  p50   2993.78  p95   3400.76  max   3615.97
  topology extrude 20 faces       n= 20  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50   2909.59  p95   3298.47  max   3301.98
      op                       p50     65.94  p95     67.59  max     69.29
      history                  p50   2240.57  p95   2619.03  max   2655.64
      hover re-pick            p50    157.56  p95    180.24  max    217.27
      viewport sync            p50    418.69  p95    435.95  max    439.58
    next hover frame           p50     13.52  p95     14.94  max     16.02
    undo frame                 p50   1764.25  p95   1925.02  max   1925.61
    op + undo                  p50   4719.64  p95   5056.89  max   5133.98
  topology knife commit, 1 cut    n= 20  (2 clicks, line crosses 3 edges; Enter measured)
    frame (op as triggered)    p50   2514.71  p95   2546.59  max   2629.08
      op                       p50    230.07  p95    235.88  max    253.37
      history                  p50   1659.43  p95   1681.14  max   1742.78
      hover re-pick            p50    270.83  p95    277.54  max    278.68
      viewport sync            p50    346.62  p95    353.72  max    366.94
    next hover frame           p50     47.85  p95     48.91  max     50.59
    undo frame                 p50   1792.66  p95   2254.49  max   2259.00
    op + undo                  p50   4320.83  p95   4757.43  max   4805.59
  topology dissolve 1 edge        n= 20
    frame (op as triggered)    p50   1077.51  p95   1365.99  max   1366.23
      op                       p50     46.49  p95     47.77  max     48.03
      history                  p50    414.71  p95    714.07  max    714.60
      hover re-pick            p50    260.80  p95    265.03  max    265.94
      viewport sync            p50    335.95  p95    343.49  max    347.16
    next hover frame           p50     50.66  p95     51.44  max     53.30
    undo frame                 p50   2310.70  p95   2450.31  max   2456.56
    op + undo                  p50   3279.22  p95   3680.90  max   3709.78
  topology delete 1 face          n= 20
    frame (op as triggered)    p50    944.16  p95   1263.06  max   1263.32
      op                       p50     34.24  p95     35.72  max     36.28
      history                  p50    199.45  p95    723.14  max    723.75
      hover re-pick            p50    157.74  p95    574.53  max    582.45
      viewport sync            p50    334.32  p95    342.35  max    357.64
    next hover frame           p50      9.21  p95     10.28  max     10.53
    undo frame                 p50   2248.97  p95   2338.83  max   2368.27
    op + undo                  p50   3057.73  p95   3514.76  max   3517.68

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                             246    70743.6    287.58
    DerivedGeometry.full_recompute (adjacency + all normals)              1      277.0    277.04
    RenderMesh._rebuild_index_mapping (index map + triangulation)         0        0.0      0.00
      triangulate_mesh_face (all calls)                                   0        0.0      0.00
    RenderMesh._rebuild_resources (flatten + upload)                    201    51399.6    255.72
      GLRenderStore.allocate                                           1407      894.3      0.64
      GLRenderStore.update                                             9509    13588.6      1.43
      GLRenderStore.end_rebuild (VertexList creation)                   201    13364.5     66.49
  Mesh.export_state                                                     306   107216.4    350.38
  Mesh.load_state                                                       120   153099.5   1275.83
  PickCache.refresh (only when the signature changed: see calls)        718    31951.3     44.50

Stage-1 counters (whole run incl. warm-up and undo frames): topology syncs 246 (full buffer rebuilds 201, V2 patch syncs 46); faces re-triangulated 24575, reused 5379710; H0: changed by counts 40, full-compare fallbacks 0, lazy after-exports at Undo 40
```
