# Topology probe, container, 2026-10-21: before / after the production journal path (AD-023)

Container (Xeon, Python 3.13.16, llvmpipe) - **not the reference PC**. Same command on both trees:
`xvfb-run -a python experiments/drag_cost/probe_navigation_gl.py --scenarios topology --assets examples/meshes/gollum_20k.obj --steps 5 --row-seconds 40`
("after" with `--profile-top 0`). Before = commit 6e4ebd3. ms. Note: after the change the probe's "history" column (wrapped export_state/load_state/push) no longer sees the journal cost; it is inside "op".

## Before (6e4ebd3)

```
[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 1564 ms
  topology extrude 1 face         n=  5  frame p50   1610.32  max   1996.57  (T + 2 moves + release; sync = 3 frames)
    event   494.06 = op     0.94 + history   444.40 + notify   0.01 + hover pick    61.21 [cache   58.41, vertex_faces    0.00]
    sync  1111.97  draw   33.57   next hover frame    13.92   undo frame  1067.92
  topology extrude 20 faces       n=  5  frame p50   2046.28  max   2327.33  (T + 2 moves + release; sync = 3 frames)
    event  1246.87 = op    23.14 + history  1167.96 + notify   0.02 + hover pick    54.74 [cache   51.30, vertex_faces    0.00]
    sync   775.39  draw   30.37   next hover frame    14.28   undo frame   951.82
  topology knife commit, 1 cut    n=  5  frame p50   1397.29  max   1606.02  (2 clicks, line crosses 3 edges; Enter measured)
    event   977.29 = op    87.33 + history   771.42 + notify   0.01 + hover pick   108.58 [cache   53.53, vertex_faces    0.00]
    sync   400.36  draw   15.22   next hover frame    28.96   undo frame  1430.53
  topology dissolve 1 edge        n=  5  frame p50    972.83  max   1273.37
    event   503.77 = op    13.92 + history   376.46 + notify   0.01 + hover pick   120.73 [cache   65.25, vertex_faces    0.00]
    sync   399.84  draw   13.92   next hover frame    30.11   undo frame  1223.86
  topology delete 1 face          n=  5  frame p50    969.51  max   1220.30
    event   521.93 = op    13.79 + history   447.76 + notify   0.01 + hover pick    54.27 [cache   51.19, vertex_faces    0.00]
    sync   489.76  draw   12.38   next hover frame    11.10   undo frame  1219.44
```

## After

```
[gollum_20k] 21875 V / 21875 F / 49218 triangles; load + first frame 901 ms
  topology extrude 1 face         n=  5  frame p50     36.45  max     40.71  (T + 2 moves + release; sync = 3 frames)
    event     3.93 = op     0.63 + history     0.01 + notify   0.01 + hover pick     3.34 [cache    0.07, vertex_faces    0.00]
    sync     5.74  draw   26.71   next hover frame    10.48   undo frame    15.70
  topology extrude 20 faces       n=  5  frame p50     41.44  max     47.45  (T + 2 moves + release; sync = 3 frames)
    event     5.03 = op     1.84 + history     0.04 + notify   0.01 + hover pick     3.00 [cache    0.20, vertex_faces    0.00]
    sync     8.60  draw   27.32   next hover frame    10.86   undo frame    26.29
  topology knife commit, 1 cut    n=  5  frame p50     66.57  max     76.89  (2 clicks, line crosses 3 edges; Enter measured)
    event    47.74 = op     3.57 + history     0.01 + notify   0.00 + hover pick    44.25 [cache    0.11, vertex_faces    0.00]
    sync     2.87  draw   12.13   next hover frame    21.64   undo frame    29.26
  topology dissolve 1 edge        n=  5  frame p50     53.87  max     62.19
    event    37.51 = op     0.33 + history     0.01 + notify   0.00 + hover pick    37.16 [cache    0.05, vertex_faces    0.00]
    sync     2.44  draw   12.62   next hover frame    23.98   undo frame    44.18
  topology delete 1 face          n=  5  frame p50     18.02  max     21.40
    event     2.93 = op     0.22 + history     0.01 + notify   0.00 + hover pick     2.71 [cache    0.05, vertex_faces    0.00]
    sync     2.77  draw   12.26   next hover frame    10.30   undo frame    17.00
```
