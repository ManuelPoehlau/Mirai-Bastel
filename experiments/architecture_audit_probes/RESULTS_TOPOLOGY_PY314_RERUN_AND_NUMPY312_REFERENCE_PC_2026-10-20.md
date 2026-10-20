# Rohausgabe: weiterer Topologie-Lauf (Python 3.14.2) und NumPy-Test unter Python 3.12 (Manu, 2026-10-20, Referenz-PC)

Unverändert aus dem Chat übernommen, mit einer Ausnahme: die ersten Zeilen des Topologie-Laufs (Aufruf, `... loading`, `Split probe options`)
fehlen in Manus Einfügung. Aus dem Header „Python: 3.14.2“ und aus `Mesh.export_state` = 186 Aufrufen (die Läufe mit `--history-depth 20`
haben 226, also 40 mehr = 20 Pad-Einträge × 2 Snapshots) lese ich: **Python 3.14.2 (nicht 3.12!), Standard-GC, History-Tiefe 0**, `--steps 12
--row-seconds 120` (n = 12). Manu wollte den Lauf unter Python 3.12 machen, `python` in PowerShell ist aber 3.14.2 (`python --version`
in derselben Sitzung: 3.14.2). Ein Lauf unter 3.12.10 (der PyCharm-Interpreter) steht damit **weiter aus**.

## NumPy unter Python 3.12 (venv `.venv_np312` mit `py -3.12`)

```
PS C:\Users\Manuel\Mirai_Bastel> python --version
Python 3.14.2
PS C:\Users\Manuel\Mirai_Bastel> py -3.12 -m venv .venv_np312
PS C:\Users\Manuel\Mirai_Bastel> .venv_np312\Scripts\pip install "numpy<2.3"
Collecting numpy<2.3
  Downloading numpy-2.2.6-cp312-cp312-win_amd64.whl.metadata (60 kB)
Downloading numpy-2.2.6-cp312-cp312-win_amd64.whl (12.6 MB)
Installing collected packages: numpy
Successfully installed numpy-2.2.6
PS C:\Users\Manuel\Mirai_Bastel> .venv_np312\Scripts\python -c "import numpy; print(numpy.__version__)"
2.2.6
```

Nur der Import wurde getestet, keine Rechenzeit. (Die Download-Fortschrittsbalken und der pip-Hinweis sind hier gekürzt.)

## Topologie-Lauf (Python 3.14.2, Standard-GC, Tiefe 0, n = 12)

```
Navigation and picking cost with the GL backend (WP-VIEW-PERF-01), ms per event + frame
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window; up to 12 events per row (at least 5, budget 120 s); frame = event + sync + draw; one frame at 60 Hz = 16.7 ms

[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2925 ms
  topology extrude 1 face         n= 12  frame p50   3042.79  max   3400.68  (T + 2 moves + release; sync = 3 frames)
    event   520.53 = op     0.80 + history   370.80 + notify   0.02 + hover pick   145.79 [cache  139.53, vertex_faces    0.00]
    sync  2485.92  draw   21.23   next hover frame    11.95   undo frame  1803.96
  topology extrude 20 faces       n= 12  frame p50   3754.68  max   3840.03  (T + 2 moves + release; sync = 3 frames)
    event  1090.05 = op    64.03 + history   875.01 + notify   0.02 + hover pick   149.31 [cache  142.23, vertex_faces    0.00]
    sync  2591.25  draw   21.15   next hover frame    12.99   undo frame  1843.51
  topology knife commit, 1 cut    n= 12  frame p50   2381.47  max   2471.81  (2 clicks, line crosses 3 edges; Enter measured)
    event  1138.78 = op   207.21 + history   689.14 + notify   0.01 + hover pick   247.42 [cache  138.34, vertex_faces    0.00]
    sync  1211.89  draw   10.67   next hover frame    46.60   undo frame  2032.22
  topology dissolve 1 edge        n= 12  frame p50   1914.13  max   2176.00
    event   664.87 = op    29.18 + history   388.83 + notify   0.01 + hover pick   240.66 [cache  138.65, vertex_faces    0.00]
    sync  1238.25  draw   10.30   next hover frame    49.10   undo frame  1995.18
  topology delete 1 face          n= 12  frame p50   1857.26  max   2032.19
    event   643.29 = op    25.24 + history   472.60 + notify   0.01 + hover pick   145.47 [cache  138.59, vertex_faces    0.00]
    sync  1212.28  draw    9.67   next hover frame     9.39   undo frame  1866.47

Rebuild split (wall clock, nested; calls over the whole run incl. warm-up and undo frames)
  function                                                            calls   total ms    avg ms
  RenderMesh._sync_topology                                             150   189136.2   1260.91
    DerivedGeometry.full_recompute (adjacency + all normals)            152    47536.3    312.74
    RenderMesh._rebuild_index_mapping (index map + triangulation)       151    78089.9    517.15
      triangulate_mesh_face (all calls)                              3303821    68534.1      0.02
    RenderMesh._rebuild_resources (flatten + upload)                    151    65240.9    432.06
      GLRenderStore.allocate                                           1057      985.6      0.93
      GLRenderStore.update                                             3641    10206.8      2.80
      GLRenderStore.end_rebuild (VertexList creation)                  151    10955.3     72.55
  Mesh.export_state                                                     186    29514.0    158.68
  Mesh.load_state                                                        72    29167.1    405.10
  PickCache.refresh (only when the signature changed: see calls)        462    17828.0     38.59
```
