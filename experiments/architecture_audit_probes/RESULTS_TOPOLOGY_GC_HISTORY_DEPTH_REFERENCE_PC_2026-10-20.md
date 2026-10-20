# Rohausgabe: Topologie-Operationen mit GC an / aus / eingefroren, History-Tiefe 20 (Manu, 2026-10-20, Referenz-PC)

Unverändert aus dem Chat übernommen. Referenz-PC: Core 2 Quad Q9550, GeForce 9800 GTX, Windows 10, Python 3.14.2,
`GL_VERSION` 3.3.0. Skript: [`probe_topology_sync_split.py`](probe_topology_sync_split.py) mit `--steps 12 --row-seconds 120
--history-depth 20` und `--gc on`, `--gc off`, `--gc freeze`. Je Zeile **n = 12** (der Report der Sonde nennt p50 und max, kein p95).
Vor der Messung liegen 20 echte Undo-Einträge (je zwei Ganz-Mesh-Snapshots) auf dem Stack. Die Zeilen unter „Rebuild split“ sind
verschachtelte Wanduhr-Zeiten über den ganzen Lauf inkl. Warm-up, Pad-Phase und Undo-Frames; der Zeitmesser um
`triangulate_mesh_face` (3,3 Mio. Aufrufe) macht diese Zeile und ihre Eltern etwas zu groß. Auswertung in
[`../drag_cost/README.md`](../drag_cost/README.md) („GC and history depth, reference PC“).

## Lauf 1: `--gc on`

```
PS C:\Users\Manuel\Mirai_Bastel> python experiments/architecture_audit_probes/probe_topology_sync_split.py --steps 12 --row-seconds 120 --history-depth 20 --gc on
... gollum_20k: loading gollum_20k.obj
... gollum_20k: topology
Split probe options: --gc on --history-depth 20 (GC threshold (2000, 10, 0))
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 12 events per row (at least 5, budget 120 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 3475 ms
  topology extrude 1 face         n= 12  frame p50   2770.10  max  12949.79  (T + 2 moves + release; sync = 3 frames)
    event   354.48 = op     0.80 + history   208.07 + notify   0.02 + hover pick   146.08 [cache  138.95, vertex_faces    0.00]
    sync  2383.47  draw   20.67   next hover frame    11.66   undo frame  1606.72
  topology extrude 20 faces       n= 12  frame p50   3330.73  max   4894.06  (T + 2 moves + release; sync = 3 frames)
    event   801.61 = op    66.28 + history   587.77 + notify   0.02 + hover pick   149.58 [cache  142.45, vertex_faces    0.00]
    sync  2410.33  draw   22.41   next hover frame    12.43   undo frame  1650.19
  topology knife commit, 1 cut    n= 12  frame p50   2192.52  max   4140.00  (2 clicks, line crosses 3 edges; Enter measured)
    event   952.84 = op   211.20 + history   470.72 + notify   0.01 + hover pick   248.48 [cache  138.26, vertex_faces    0.00]
    sync  1197.34  draw   10.28   next hover frame    47.55   undo frame  1733.22
  topology dissolve 1 edge        n= 12  frame p50   1684.63  max   2614.25
    event   475.56 = op    29.71 + history   203.84 + notify   0.01 + hover pick   241.18 [cache  138.80, vertex_faces    0.00]
    sync  1196.98  draw   10.70   next hover frame    49.53   undo frame  1700.25
  topology delete 1 face          n= 12  frame p50   1602.22  max   1926.85
    event   377.65 = op    25.41 + history   205.62 + notify   0.01 + hover pick   147.92 [cache  140.63, vertex_faces    0.00]
    sync  1204.45  draw   10.55   next hover frame     9.19   undo frame  1626.03

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                             150   196056.2   1307.04
    DerivedGeometry.full_recompute (adjacency + all normals)            152    45587.9    299.92
    RenderMesh._rebuild_index_mapping (index map + triangulation)       151    85442.0    565.84
      triangulate_mesh_face (all calls)                              3303821    75288.1      0.02
    RenderMesh._rebuild_resources (flatten + upload)                    151    67061.5    444.12
      GLRenderStore.allocate                                           1057     1014.1      0.96
      GLRenderStore.update                                             3669    10659.2      2.91
      GLRenderStore.end_rebuild (VertexList creation)                   151    11613.5     76.91
  Mesh.export_state                                                     226    35798.7    158.40
  Mesh.load_state                                                        72    34882.1    484.47
  PickCache.refresh (only when the signature changed: see calls)        462    18035.3     39.04
```

## Lauf 2: `--gc off`

```
PS C:\Users\Manuel\Mirai_Bastel> python experiments/architecture_audit_probes/probe_topology_sync_split.py --steps 12 --row-seconds 120 --history-depth 20 --gc off
... gollum_20k: loading gollum_20k.obj
... gollum_20k: topology
Split probe options: --gc off --history-depth 20 (GC threshold (2000, 10, 0))
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 12 events per row (at least 5, budget 120 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2746 ms
  topology extrude 1 face         n= 12  frame p50   2907.53  max   3450.39  (T + 2 moves + release; sync = 3 frames)
    event   378.10 = op     0.84 + history   224.15 + notify   0.02 + hover pick   150.06 [cache  142.82, vertex_faces    0.00]
    sync  2507.67  draw   23.63   next hover frame    12.71   undo frame  1673.02
  topology extrude 20 faces       n= 12  frame p50   3283.15  max   3596.45  (T + 2 moves + release; sync = 3 frames)
    event   782.52 = op    64.91 + history   563.92 + notify   0.02 + hover pick   153.10 [cache  145.92, vertex_faces    0.00]
    sync  2480.75  draw   21.44   next hover frame    12.61   undo frame  1679.50
  topology knife commit, 1 cut    n= 12  frame p50   2126.79  max   2256.89  (2 clicks, line crosses 3 edges; Enter measured)
    event   906.27 = op   209.74 + history   446.32 + notify   0.01 + hover pick   249.28 [cache  142.73, vertex_faces    0.00]
    sync  1210.88  draw   10.37   next hover frame    44.41   undo frame  1735.61
  topology dissolve 1 edge        n= 12  frame p50   1695.35  max   1708.96
    event   469.70 = op    29.01 + history   199.68 + notify   0.01 + hover pick   240.74 [cache  141.53, vertex_faces    0.00]
    sync  1214.82  draw    9.84   next hover frame    47.47   undo frame  1710.82
  topology delete 1 face          n= 12  frame p50   1604.24  max   1634.67
    event   376.85 = op    25.19 + history   201.81 + notify   0.01 + hover pick   150.14 [cache  143.93, vertex_faces    0.00]
    sync  1212.17  draw   10.27   next hover frame     9.07   undo frame  1645.16

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                             150   186291.3   1241.94
    DerivedGeometry.full_recompute (adjacency + all normals)            152    45879.3    301.84
    RenderMesh._rebuild_index_mapping (index map + triangulation)       151    76761.2    508.35
      triangulate_mesh_face (all calls)                              3303821    66658.7      0.02
    RenderMesh._rebuild_resources (flatten + upload)                    151    65173.4    431.61
      GLRenderStore.allocate                                           1057     1040.5      0.98
      GLRenderStore.update                                             3669    10530.8      2.87
      GLRenderStore.end_rebuild (VertexList creation)                  151    11303.8     74.86
  Mesh.export_state                                                     226    22155.5     98.03
  Mesh.load_state                                                        72    18998.0    263.86
  PickCache.refresh (only when the signature changed: see calls)        462    18346.0     39.71
```

## Lauf 3: `--gc freeze`

```
PS C:\Users\Manuel\Mirai_Bastel> python experiments/architecture_audit_probes/probe_topology_sync_split.py --steps 12 --row-seconds 120 --history-depth 20 --gc freeze
... gollum_20k: loading gollum_20k.obj
... gollum_20k: topology
Split probe options: --gc freeze --history-depth 20 (GC threshold (2000, 10, 0))
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 12 events per row (at least 5, budget 120 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2615 ms
  topology extrude 1 face         n= 12  frame p50   3041.19  max   3096.82  (T + 2 moves + release; sync = 3 frames)
    event   499.31 = op     0.78 + history   349.31 + notify   0.02 + hover pick   145.63 [cache  139.13, vertex_faces    0.00]
    sync  2526.20  draw   21.60   next hover frame    11.66   undo frame  1928.24
  topology extrude 20 faces       n= 12  frame p50   3872.46  max   4058.03  (T + 2 moves + release; sync = 3 frames)
    event  1323.16 = op    64.55 + history  1108.16 + notify   0.02 + hover pick   150.08 [cache  143.29, vertex_faces    0.00]
    sync  2529.19  draw   20.95   next hover frame    12.28   undo frame  1956.12
  topology knife commit, 1 cut    n= 12  frame p50   2603.33  max   2614.23  (2 clicks, line crosses 3 edges; Enter measured)
    event  1331.53 = op   207.51 + history   873.87 + notify   0.01 + hover pick   252.33 [cache  140.52, vertex_faces    0.00]
    sync  1247.06  draw   10.46   next hover frame    44.69   undo frame  2125.38
  topology dissolve 1 edge        n= 12  frame p50   1910.47  max   2010.79
    event   621.96 = op    28.36 + history   342.43 + notify   0.01 + hover pick   250.40 [cache  141.03, vertex_faces    0.00]
    sync  1272.69  draw   10.23   next hover frame    46.48   undo frame  2117.95
  topology delete 1 face          n= 12  frame p50   1826.16  max   1932.33
    event   546.88 = op    24.84 + history   375.03 + notify   0.01 + hover pick   147.91 [cache  141.22, vertex_faces    0.00]
    sync  1285.65  draw   10.27   next hover frame     8.77   undo frame  2057.36

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                             150   188778.0   1258.52
    DerivedGeometry.full_recompute (adjacency + all normals)            152    46253.0    304.30
    RenderMesh._rebuild_index_mapping (index map + triangulation)       151    77137.1    510.84
      triangulate_mesh_face (all calls)                              3303821    67750.3      0.02
    RenderMesh._rebuild_resources (flatten + upload)                    151    66884.4    442.94
      GLRenderStore.allocate                                           1057     982.2      0.93
      GLRenderStore.update                                             3669    10240.5      2.79
      GLRenderStore.end_rebuild (VertexList creation)                  151    10955.0     72.55
  Mesh.export_state                                                     226    36327.3    160.74
  Mesh.load_state                                                        72    42920.6    596.12
  PickCache.refresh (only when the signature changed: see calls)        462    17916.2     38.78
```
