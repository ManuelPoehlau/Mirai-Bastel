# Rohausgabe: Zerlegung des Viewport-Neuaufbaus auf dem Referenz-PC (Manu, 2026-10-20, dritter Topologie-Lauf)

Unverändert aus dem Chat übernommen. Referenz-PC: Core 2 Quad Q9550, GeForce 9800 GTX, Windows 10, Python 3.14.2,
`GL_VERSION` 3.3.0. Skript: [`probe_topology_sync_split.py`](probe_topology_sync_split.py) in der ersten Fassung
(ohne `--gc` / `--history-depth`, also Standard-GC und History-Tiefe ~1). Je Zeile **n = 3**. Die Zeilen unter „Rebuild split“
sind verschachtelte Wanduhr-Zeiten über den ganzen Lauf (inkl. Warm-up und Undo-Frames); der Zeitmesser um
`triangulate_mesh_face` (940 799 Aufrufe) macht diese Zeile und ihre Eltern etwas zu groß.

```
PS C:\Users\Manuel\Mirai_Bastel> python experiments/architecture_audit_probes/probe_topology_sync_split.py
... gollum_20k: loading gollum_20k.obj
... gollum_20k: topology
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 40 events per row (at least 5, budget 8 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2582 ms
  topology extrude 1 face         n=  3  frame p50   2923.18  max   3209.01  (T + 2 moves + release; sync = 3 frames)
    event   349.76 = op     0.89 + history   205.83 + notify   0.02 + hover pick   141.62 [cache  135.43, vertex_faces    0.00]
    sync  2555.47  draw   21.49   next hover frame    11.90   undo frame  1831.59
  topology extrude 20 faces       n=  3  frame p50   3539.54  max   3592.05  (T + 2 moves + release; sync = 3 frames)
    event  1106.55 = op    64.34 + history   897.71 + notify   0.02 + hover pick   144.48 [cache  137.92, vertex_faces    0.00]
    sync  2429.80  draw   18.84   next hover frame    12.03   undo frame  1791.94
  topology knife commit, 1 cut    n=  3  frame p50   2320.04  max   2354.37  (2 clicks, line crosses 3 edges; Enter measured)
    event  1130.44 = op   201.76 + history   677.97 + notify   0.01 + hover pick   241.82 [cache  136.49, vertex_faces    0.00]
    sync  1178.98  draw   10.62   next hover frame    42.94   undo frame  1885.51
  topology dissolve 1 edge        n=  3  frame p50   1846.02  max   2021.19
    event   650.08 = op    28.55 + history   379.81 + notify   0.01 + hover pick   234.96 [cache  136.29, vertex_faces    0.00]
    sync  1183.64  draw   11.03   next hover frame    48.24   undo frame  1952.43
  topology delete 1 face          n=  3  frame p50   1823.02  max   1950.24
    event   632.66 = op    26.08 + history   464.50 + notify   0.01 + hover pick   147.83 [cache  140.99, vertex_faces    0.00]
    sync  1188.64  draw    9.62   next hover frame     8.41   undo frame  1648.78

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                              42    51391.5   1223.61
    DerivedGeometry.full_recompute (adjacency + all normals)             44    13096.3    297.64
    RenderMesh._rebuild_index_mapping (index map + triangulation)        43    22009.6    511.85
      triangulate_mesh_face (all calls)                              940799    19306.5      0.02
    RenderMesh._rebuild_resources (flatten + upload)                     43    17775.5    413.38
      GLRenderStore.allocate                                            301      267.2      0.89
      GLRenderStore.update                                              959     2806.2      2.93
      GLRenderStore.end_rebuild (VertexList creation)                    43     3151.5     73.29
  Mesh.export_state                                                      51     7406.3    145.22
  Mesh.load_state                                                        18     7478.7    415.48
  PickCache.refresh (only when the signature changed: see calls)        174     5079.3     29.19
```
