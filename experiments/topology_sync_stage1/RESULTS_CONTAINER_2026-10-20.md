# Raw outputs, container (not the reference PC), 2026-10-20

`probe_stage1.py` on `gollum_20k`; first three runs `--steps 10 --row-seconds 60 --gc off`, last two `--steps 5 --row-seconds 30` with the GC on (default). Branch `claude/ad023-stage1-experiment`.

## --stage1 none --gc off

```text
AD-023 stage 1 switches: none (baseline: unchanged code)
Split probe options: --gc off --history-depth 0 (GC threshold (2000, 10, 10))
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Linux-6.18.44-fc-v139-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.80GHz (4 logical cores)
Python: 3.13.16 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Run: hidden 1024x768 window; up to 10 events per row (at least 5, budget 60 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 1080 ms
  topology extrude 1 face         n= 10  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50   1047.16  p95   1350.49  max   1350.49
      op                       p50      0.67  p95      0.98  max      0.98
      history                  p50     95.39  p95    332.12  max    332.12
      hover re-pick            p50     57.06  p95     91.97  max     91.97
      viewport sync            p50    831.17  p95    963.22  max    963.22
    next hover frame           p50     13.27  p95     22.71  max     22.71
    undo frame                 p50    589.59  p95    664.00  max    664.00
    op + undo                  p50   1661.64  p95   1925.53  max   1925.53
  topology extrude 20 faces       n= 10  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50   1282.20  p95   1731.41  max   1731.41
      op                       p50     30.65  p95     39.81  max     39.81
      history                  p50    253.26  p95    322.99  max    322.99
      hover re-pick            p50     74.17  p95    117.95  max    117.95
      viewport sync            p50    917.48  p95   1278.72  max   1278.72
    next hover frame           p50     14.52  p95     16.50  max     16.50
    undo frame                 p50    603.37  p95    705.27  max    705.27
    op + undo                  p50   1904.87  p95   2292.64  max   2292.64
  topology knife commit, 1 cut    n= 10  (2 clicks, line crosses 3 edges; Enter measured)
    frame (op as triggered)    p50    912.64  p95   1028.49  max   1028.49
      op                       p50    100.35  p95    106.68  max    106.68
      history                  p50    215.81  p95    241.03  max    241.03
      hover re-pick            p50    127.44  p95    171.85  max    171.85
      viewport sync            p50    462.58  p95    557.88  max    557.88
    next hover frame           p50     31.05  p95     46.19  max     46.19
    undo frame                 p50    714.20  p95    892.40  max    892.40
    op + undo                  p50   1661.74  p95   1792.33  max   1792.33
  topology dissolve 1 edge        n= 10
    frame (op as triggered)    p50    691.40  p95    825.07  max    825.07
      op                       p50     15.69  p95     23.92  max     23.92
      history                  p50     97.08  p95    139.30  max    139.30
      hover re-pick            p50    111.26  p95    150.20  max    150.20
      viewport sync            p50    453.83  p95    537.68  max    537.68
    next hover frame           p50     33.82  p95     52.29  max     52.29
    undo frame                 p50    690.30  p95    883.14  max    883.14
    op + undo                  p50   1418.63  p95   1574.94  max   1574.94
  topology delete 1 face          n= 10
    frame (op as triggered)    p50    645.94  p95    801.32  max    801.32
      op                       p50     14.38  p95     15.12  max     15.12
      history                  p50     86.21  p95     98.82  max     98.82
      hover re-pick            p50     62.00  p95     76.17  max     76.17
      viewport sync            p50    460.24  p95    619.40  max    619.40
    next hover frame           p50     12.37  p95     19.76  max     19.76
    undo frame                 p50    634.94  p95    699.53  max    699.53
    op + undo                  p50   1280.94  p95   1500.85  max   1500.85

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                             126    57140.7    453.50
    DerivedGeometry.full_recompute (adjacency + all normals)            128    16258.0    127.02
    RenderMesh._rebuild_index_mapping (index map + triangulation)       127    19636.4    154.62
      triangulate_mesh_face (all calls)                              2778705    17139.4      0.01
    RenderMesh._rebuild_resources (flatten + upload)                    127    21999.4    173.22
      GLRenderStore.allocate                                            889      308.4      0.35
      GLRenderStore.update                                             3045     4161.7      1.37
      GLRenderStore.end_rebuild (VertexList creation)                   127     3938.1     31.01
  Mesh.export_state                                                     156     6781.9     43.47
  Mesh.load_state                                                        60     6827.0    113.78
  PickCache.refresh (only when the signature changed: see calls)        398     6682.4     16.79

Stage-1 counters (whole run incl. warm-up and undo frames): topology syncs 0 (full buffer rebuilds 0, V2 patch syncs 0); faces re-triangulated 0, reused 0; H0: changed by counts 0, full-compare fallbacks 0, lazy after-exports at Undo 0
```

## --stage1 V0,V2,V3 --gc off

```text
AD-023 stage 1 switches: V0,V2,V3
Split probe options: --gc off --history-depth 0 (GC threshold (2000, 10, 10))
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Linux-6.18.44-fc-v139-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.80GHz (4 logical cores)
Python: 3.13.16 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Run: hidden 1024x768 window; up to 10 events per row (at least 5, budget 60 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 902 ms
  topology extrude 1 face         n= 10  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50    398.71  p95    634.89  max    634.89
      op                       p50      0.72  p95      0.91  max      0.91
      history                  p50    117.74  p95    290.62  max    290.62
      hover re-pick            p50     60.04  p95     99.11  max     99.11
      viewport sync            p50    173.25  p95    218.74  max    218.74
    next hover frame           p50     15.30  p95     21.61  max     21.61
    undo frame                 p50    307.18  p95    324.02  max    324.02
    op + undo                  p50    713.88  p95    958.91  max    958.91
  topology extrude 20 faces       n= 10  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50    525.97  p95    582.49  max    582.49
      op                       p50     26.56  p95     38.97  max     38.97
      history                  p50    233.28  p95    259.88  max    259.88
      hover re-pick            p50     61.54  p95     84.94  max     84.94
      viewport sync            p50    162.97  p95    223.58  max    223.58
    next hover frame           p50     14.66  p95     16.18  max     16.18
    undo frame                 p50    297.99  p95    316.86  max    316.86
    op + undo                  p50    829.13  p95    873.66  max    873.66
  topology knife commit, 1 cut    n= 10  (2 clicks, line crosses 3 edges; Enter measured)
    frame (op as triggered)    p50    588.15  p95    773.83  max    773.83
      op                       p50     92.91  p95    138.85  max    138.85
      history                  p50    217.03  p95    294.62  max    294.62
      hover re-pick            p50    117.57  p95    180.50  max    180.50
      viewport sync            p50    137.10  p95    192.62  max    192.62
    next hover frame           p50     31.13  p95     45.07  max     45.07
    undo frame                 p50    380.58  p95    613.21  max    613.21
    op + undo                  p50    976.98  p95   1387.03  max   1387.03
  topology dissolve 1 edge        n= 10
    frame (op as triggered)    p50    370.84  p95    405.58  max    405.58
      op                       p50     15.65  p95     22.80  max     22.80
      history                  p50     89.60  p95    111.65  max    111.65
      hover re-pick            p50    111.73  p95    141.00  max    141.00
      viewport sync            p50    128.99  p95    153.28  max    153.28
    next hover frame           p50     32.95  p95     50.19  max     50.19
    undo frame                 p50    368.45  p95    389.89  max    389.89
    op + undo                  p50    745.30  p95    792.82  max    792.82
  topology delete 1 face          n= 10
    frame (op as triggered)    p50    323.45  p95    382.89  max    382.89
      op                       p50     14.99  p95     18.41  max     18.41
      history                  p50     90.60  p95    106.37  max    106.37
      hover re-pick            p50     64.06  p95    103.13  max    103.13
      viewport sync            p50    126.25  p95    157.00  max    157.00
    next hover frame           p50     12.44  p95     17.20  max     17.20
    undo frame                 p50    346.68  p95    396.62  max    396.62
    op + undo                  p50    667.24  p95    779.52  max    779.52

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                             126    14314.2    113.60
    DerivedGeometry.full_recompute (adjacency + all normals)              1      115.6    115.64
    RenderMesh._rebuild_index_mapping (index map + triangulation)         0        0.0      0.00
      triangulate_mesh_face (all calls)                                   0        0.0      0.00
    RenderMesh._rebuild_resources (flatten + upload)                    101    10186.0    100.85
      GLRenderStore.allocate                                            707      209.2      0.30
      GLRenderStore.update                                             4769     3339.9      0.70
      GLRenderStore.end_rebuild (VertexList creation)                   101     3149.6     31.18
  Mesh.export_state                                                     156     7022.3     45.01
  Mesh.load_state                                                        60     6837.3    113.96
  PickCache.refresh (only when the signature changed: see calls)        398     6600.7     16.58

Stage-1 counters (whole run incl. warm-up and undo frames): topology syncs 126 (full buffer rebuilds 101, V2 patch syncs 26); faces re-triangulated 23225, reused 2755480; H0: changed by counts 0, full-compare fallbacks 0, lazy after-exports at Undo 0
```

## --stage1 all --gc off

```text
AD-023 stage 1 switches: H0,V0,V2,V3
Split probe options: --gc off --history-depth 0 (GC threshold (2000, 10, 10))
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Linux-6.18.44-fc-v139-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.80GHz (4 logical cores)
Python: 3.13.16 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Run: hidden 1024x768 window; up to 10 events per row (at least 5, budget 60 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 1023 ms
  topology extrude 1 face         n= 10  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50    424.40  p95    497.51  max    497.51
      op                       p50      0.71  p95      0.82  max      0.82
      history                  p50    115.42  p95    209.95  max    209.95
      hover re-pick            p50     65.80  p95    105.12  max    105.12
      viewport sync            p50    167.26  p95    208.02  max    208.02
    next hover frame           p50     15.38  p95     21.95  max     21.95
    undo frame                 p50    328.62  p95    444.57  max    444.57
    op + undo                  p50    768.52  p95    878.05  max    878.05
  topology extrude 20 faces       n= 10  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50    630.56  p95    753.39  max    753.39
      op                       p50     30.06  p95     49.34  max     49.34
      history                  p50    271.84  p95    330.57  max    330.57
      hover re-pick            p50     67.37  p95    105.97  max    105.97
      viewport sync            p50    203.36  p95    264.72  max    264.72
    next hover frame           p50     15.58  p95     23.92  max     23.92
    undo frame                 p50    316.32  p95    441.40  max    441.40
    op + undo                  p50    981.70  p95   1146.83  max   1146.83
  topology knife commit, 1 cut    n= 10  (2 clicks, line crosses 3 edges; Enter measured)
    frame (op as triggered)    p50    569.81  p95    646.40  max    646.40
      op                       p50     91.84  p95    117.38  max    117.38
      history                  p50    205.07  p95    265.67  max    265.67
      hover re-pick            p50    119.00  p95    131.68  max    131.68
      viewport sync            p50    135.32  p95    154.69  max    154.69
    next hover frame           p50     32.58  p95     48.41  max     48.41
    undo frame                 p50    402.49  p95    572.47  max    572.47
    op + undo                  p50   1010.80  p95   1179.61  max   1179.61
  topology dissolve 1 edge        n= 10
    frame (op as triggered)    p50    350.71  p95    461.76  max    461.76
      op                       p50     20.20  p95     32.09  max     32.09
      history                  p50     53.37  p95     74.62  max     74.62
      hover re-pick            p50    111.15  p95    154.54  max    154.54
      viewport sync            p50    138.32  p95    196.78  max    196.78
    next hover frame           p50     34.34  p95     57.57  max     57.57
    undo frame                 p50    420.65  p95    479.49  max    479.49
    op + undo                  p50    783.44  p95    917.34  max    917.34
  topology delete 1 face          n= 10
    frame (op as triggered)    p50    275.13  p95    347.03  max    347.03
      op                       p50     17.40  p95     18.84  max     18.84
      history                  p50     50.42  p95     52.75  max     52.75
      hover re-pick            p50     60.97  p95     97.50  max     97.50
      viewport sync            p50    130.10  p95    179.61  max    179.61
    next hover frame           p50     12.43  p95     14.17  max     14.17
    undo frame                 p50    377.54  p95    481.52  max    481.52
    op + undo                  p50    693.01  p95    762.82  max    762.82

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                             126    15162.5    120.34
    DerivedGeometry.full_recompute (adjacency + all normals)              1      123.8    123.76
    RenderMesh._rebuild_index_mapping (index map + triangulation)         0        0.0      0.00
      triangulate_mesh_face (all calls)                                   0        0.0      0.00
    RenderMesh._rebuild_resources (flatten + upload)                    101    10620.9    105.16
      GLRenderStore.allocate                                            707      239.6      0.34
      GLRenderStore.update                                             4769     3320.8      0.70
      GLRenderStore.end_rebuild (VertexList creation)                   101     3357.8     33.25
  Mesh.export_state                                                     156     6996.0     44.85
  Mesh.load_state                                                        60     7331.2    122.19
  PickCache.refresh (only when the signature changed: see calls)        398     6959.8     17.49

Stage-1 counters (whole run incl. warm-up and undo frames): topology syncs 126 (full buffer rebuilds 101, V2 patch syncs 26); faces re-triangulated 23225, reused 2755480; H0: changed by counts 20, full-compare fallbacks 0, lazy after-exports at Undo 20
```

## --stage1 none (GC on)

```text
AD-023 stage 1 switches: none (baseline: unchanged code)
Split probe options: --gc on --history-depth 0 (GC threshold (2000, 10, 10))
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Linux-6.18.44-fc-v139-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.80GHz (4 logical cores)
Python: 3.13.16 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Run: hidden 1024x768 window; up to 5 events per row (at least 5, budget 30 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 924 ms
  topology extrude 1 face         n=  5  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50   1616.19  p95   1918.08  max   1918.08
      op                       p50      0.79  p95      1.01  max      1.01
      history                  p50    510.68  p95    601.31  max    601.31
      hover re-pick            p50     70.09  p95    223.73  max    223.73
      viewport sync            p50    957.16  p95   1188.05  max   1188.05
    next hover frame           p50     13.94  p95     14.20  max     14.20
    undo frame                 p50    992.75  p95   1204.58  max   1204.58
    op + undo                  p50   2574.97  p95   3122.66  max   3122.66
  topology extrude 20 faces       n=  5  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50   2100.39  p95   2161.11  max   2161.11
      op                       p50     25.28  p95     26.50  max     26.50
      history                  p50   1103.24  p95   1166.10  max   1166.10
      hover re-pick            p50     62.93  p95     68.77  max     68.77
      viewport sync            p50    876.72  p95   1025.06  max   1025.06
    next hover frame           p50     13.69  p95     32.03  max     32.03
    undo frame                 p50    999.04  p95   1018.60  max   1018.60
    op + undo                  p50   3119.00  p95   3134.49  max   3134.49
  topology knife commit, 1 cut    n=  5  (2 clicks, line crosses 3 edges; Enter measured)
    frame (op as triggered)    p50   1627.30  p95   1663.40  max   1663.40
      op                       p50     93.40  p95    104.33  max    104.33
      history                  p50    751.37  p95    769.27  max    769.27
      hover re-pick            p50    114.34  p95    138.69  max    138.69
      viewport sync            p50    622.20  p95    683.84  max    683.84
    next hover frame           p50     31.00  p95     38.75  max     38.75
    undo frame                 p50   1272.53  p95   1309.07  max   1309.07
    op + undo                  p50   2847.83  p95   2935.92  max   2935.92
  topology dissolve 1 edge        n=  5
    frame (op as triggered)    p50   1027.64  p95   1263.87  max   1263.87
      op                       p50     14.76  p95     22.18  max     22.18
      history                  p50    365.37  p95    402.95  max    402.95
      hover re-pick            p50    111.52  p95    383.21  max    383.21
      viewport sync            p50    487.71  p95    757.14  max    757.14
    next hover frame           p50     33.70  p95     43.71  max     43.71
    undo frame                 p50   1192.09  p95   1451.29  max   1451.29
    op + undo                  p50   2244.95  p95   2480.19  max   2480.19
  topology delete 1 face          n=  5
    frame (op as triggered)    p50    947.32  p95   1239.21  max   1239.21
      op                       p50     14.54  p95     15.99  max     15.99
      history                  p50    399.84  p95    423.98  max    423.98
      hover re-pick            p50     66.95  p95     70.37  max     70.37
      viewport sync            p50    456.78  p95    720.15  max    720.15
    next hover frame           p50     11.87  p95     16.17  max     16.17
    undo frame                 p50   1198.48  p95   1403.13  max   1403.13
    op + undo                  p50   2144.76  p95   2474.47  max   2474.47

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                              66    32735.9    496.00
    DerivedGeometry.full_recompute (adjacency + all normals)             68    10892.8    160.19
    RenderMesh._rebuild_index_mapping (index map + triangulation)        67    11679.0    174.31
      triangulate_mesh_face (all calls)                              1465915    10411.2      0.01
    RenderMesh._rebuild_resources (flatten + upload)                     67    10786.9    161.00
      GLRenderStore.allocate                                            469      150.2      0.32
      GLRenderStore.update                                             1555     2150.9      1.38
      GLRenderStore.end_rebuild (VertexList creation)                    67     2021.4     30.17
  Mesh.export_state                                                      81    13601.5    167.92
  Mesh.load_state                                                        30    16881.6    562.72
  PickCache.refresh (only when the signature changed: see calls)        238     4142.2     17.40

Stage-1 counters (whole run incl. warm-up and undo frames): topology syncs 0 (full buffer rebuilds 0, V2 patch syncs 0); faces re-triangulated 0, reused 0; H0: changed by counts 0, full-compare fallbacks 0, lazy after-exports at Undo 0
```

## --stage1 all (GC on)

```text
AD-023 stage 1 switches: H0,V0,V2,V3
Split probe options: --gc on --history-depth 0 (GC threshold (2000, 10, 10))
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Linux-6.18.44-fc-v139-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.80GHz (4 logical cores)
Python: 3.13.16 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Run: hidden 1024x768 window; up to 5 events per row (at least 5, budget 30 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 955 ms
  topology extrude 1 face         n=  5  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50    674.53  p95    880.97  max    880.97
      op                       p50      0.70  p95      0.92  max      0.92
      history                  p50    339.26  p95    427.82  max    427.82
      hover re-pick            p50     74.80  p95    293.91  max    293.91
      viewport sync            p50    156.36  p95    253.28  max    253.28
    next hover frame           p50     13.51  p95     13.77  max     13.77
    undo frame                 p50    739.87  p95    957.10  max    957.10
    op + undo                  p50   1380.25  p95   1620.84  max   1620.84
  topology extrude 20 faces       n=  5  (T + 2 moves + release; sync = 3 frames)
    frame (op as triggered)    p50   1408.09  p95   1571.66  max   1571.66
      op                       p50     26.22  p95     28.39  max     28.39
      history                  p50   1128.80  p95   1285.06  max   1285.06
      hover re-pick            p50     68.45  p95     79.74  max     79.74
      viewport sync            p50    159.80  p95    166.17  max    166.17
    next hover frame           p50     14.40  p95     15.30  max     15.30
    undo frame                 p50    764.85  p95    831.52  max    831.52
    op + undo                  p50   2141.98  p95   2403.18  max   2403.18
  topology knife commit, 1 cut    n=  5  (2 clicks, line crosses 3 edges; Enter measured)
    frame (op as triggered)    p50   1245.10  p95   1287.30  max   1287.30
      op                       p50     86.37  p95     97.29  max     97.29
      history                  p50    886.80  p95    922.91  max    922.91
      hover re-pick            p50    122.48  p95    136.32  max    136.32
      viewport sync            p50    129.24  p95    131.52  max    131.52
    next hover frame           p50     30.62  p95     32.64  max     32.64
    undo frame                 p50    968.37  p95   1206.30  max   1206.30
    op + undo                  p50   2160.39  p95   2280.38  max   2280.38
  topology dissolve 1 edge        n=  5
    frame (op as triggered)    p50    353.04  p95    400.01  max    400.01
      op                       p50     19.15  p95     20.46  max     20.46
      history                  p50     75.02  p95     80.47  max     80.47
      hover re-pick            p50    114.72  p95    145.07  max    145.07
      viewport sync            p50    125.57  p95    148.03  max    148.03
    next hover frame           p50     33.48  p95     52.01  max     52.01
    undo frame                 p50   1246.84  p95   1334.15  max   1334.15
    op + undo                  p50   1601.93  p95   1687.19  max   1687.19
  topology delete 1 face          n=  5
    frame (op as triggered)    p50    608.56  p95    663.48  max    663.48
      op                       p50     17.57  p95     25.35  max     25.35
      history                  p50    379.28  p95    391.10  max    391.10
      hover re-pick            p50     65.13  p95     79.78  max     79.78
      viewport sync            p50    125.87  p95    165.54  max    165.54
    next hover frame           p50     12.39  p95     14.58  max     14.58
    undo frame                 p50    968.95  p95   1383.28  max   1383.28
    op + undo                  p50   1562.00  p95   1687.69  max   1687.69

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                              66     7173.3    108.69
    DerivedGeometry.full_recompute (adjacency + all normals)              1      121.7    121.66
    RenderMesh._rebuild_index_mapping (index map + triangulation)         0        0.0      0.00
      triangulate_mesh_face (all calls)                                   0        0.0      0.00
    RenderMesh._rebuild_resources (flatten + upload)                     51     5228.2    102.51
      GLRenderStore.allocate                                            357      104.5      0.29
      GLRenderStore.update                                             2399     1598.5      0.67
      GLRenderStore.end_rebuild (VertexList creation)                    51     1641.1     32.18
  Mesh.export_state                                                      81    13485.7    166.49
  Mesh.load_state                                                        30    17860.2    595.34
  PickCache.refresh (only when the signature changed: see calls)        238     5069.2     21.30

Stage-1 counters (whole run incl. warm-up and undo frames): topology syncs 66 (full buffer rebuilds 51, V2 patch syncs 16); faces re-triangulated 22550, reused 1443365; H0: changed by counts 10, full-compare fallbacks 0, lazy after-exports at Undo 10
```
