# Rohausgabe: GPU-Picking-Spike auf dem Referenz-PC (Manu, 2026-10-20)

Unverändert aus dem Chat übernommen (Manus Lauf des „Praktischen Tests“ in
[`README.md`](README.md)). Referenz-PC: Core 2 Quad Q9550, GeForce 9800 GTX, Windows 10, Python 3.14.2,
`GL_VERSION` 3.3.0. Die ausgewertete Fassung steht in der README („Result: reference PC“).
„cpu“-Zahlen in den `box`-Zeilen sind Elementanzahlen, die `cost`-Zeilen sind ms p50.

## Lauf 1: `probe_gpu_picking.py` (head_basemesh, man_with_shoes_basemesh, gollum_20k; 300 Cursor, 15 Stichproben)

```
python experiments/gpu_picking_spike/probe_gpu_picking.py
... head_basemesh
... man_with_shoes_basemesh
... gollum_20k
GPU ID-buffer picking vs CPU picker (spike, WP-VIEW-PERF-02), ms p50
Platform: Windows-10-10.0.19045-SP0
CPU: Intel64 Family 6 Model 23 Stepping 10, GenuineIntel (4 logical cores)
Python: 3.14.2
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window, 300 cursors per camera (front, back), 15 samples per cost row

[head_basemesh] 326 V / 648 E / 324 F
  agree vertex       shaded n= 600  same  596 ( 99.3%)  half-px   0  real   4 [gpu none 2, cpu none 0, other 2]
      e.g. front (447,381): cpu VertexId(292) gpu VertexId(293)
      e.g. back (408,343): cpu VertexId(208) gpu None
      e.g. back (392,350): cpu VertexId(208) gpu VertexId(158)
  agree vertex+depth shaded n= 600  same  596 ( 99.3%)  half-px   0  real   4 [gpu none 2, cpu none 0, other 2]
      e.g. front (447,381): cpu VertexId(292) gpu VertexId(293)
      e.g. back (408,343): cpu VertexId(208) gpu None
      e.g. back (392,350): cpu VertexId(208) gpu VertexId(158)
  agree edge         shaded n= 600  same  592 ( 98.7%)  half-px   0  real   8 [gpu none 1, cpu none 0, other 7]
      e.g. front (736,233): cpu EdgeId(382) gpu EdgeId(620)
      e.g. front (671,175): cpu EdgeId(380) gpu EdgeId(615)
      e.g. back (578,365): cpu EdgeId(18) gpu EdgeId(227)
  agree face         shaded n= 600  same  586 ( 97.7%)  half-px  13  real   1 [gpu none 0, cpu none 1, other 0]
      e.g. back (506,157): cpu None gpu FaceId(164)
  agree vertex       wire   n= 600  same  600 (100.0%)  half-px   0  real   0 [gpu none 0, cpu none 0, other 0]
  agree vertex+depth wire   n= 600  same  600 (100.0%)  half-px   0  real   0 [gpu none 0, cpu none 0, other 0]
  agree edge         wire   n= 600  same  600 (100.0%)  half-px   0  real   0 [gpu none 0, cpu none 0, other 0]
  box front  60 px vertex cpu     6 | ids     6 -   0 +   0 | depth     6 -   0 +   0
  box front  60 px edge   cpu     5 | ids     5 -   0 +   0 | depth     5 -   0 +   0
  box front  60 px face   cpu     1 | ids     1 -   0 +   0 | depth     1 -   0 +   0
  box front 150 px vertex cpu    64 | ids    62 -   2 +   0 | depth    62 -   2 +   0
  box front 150 px edge   cpu   104 | ids   112 -   0 +   8 | depth   102 -   2 +   0
  box front 150 px face   cpu    43 | ids    50 -   0 +   7 | depth    43 -   0 +   0
  box front 300 px vertex cpu   142 | ids   140 -   2 +   0 | depth   140 -   2 +   0
  box front 300 px edge   cpu   255 | ids   270 -   2 +  17 | depth   251 -   4 +   0
  box front 300 px face   cpu   118 | ids   140 -   1 +  23 | depth   117 -   1 +   0
  box back   60 px vertex cpu     4 | ids     4 -   0 +   0 | depth     4 -   0 +   0
  box back   60 px edge   cpu     3 | ids     3 -   0 +   0 | depth     3 -   0 +   0
  box back   60 px face   cpu     0 | ids     0 -   0 +   0 | depth     0 -   0 +   0
  box back  150 px vertex cpu    41 | ids    40 -   1 +   0 | depth    40 -   1 +   0
  box back  150 px edge   cpu    61 | ids    66 -   1 +   6 | depth    60 -   1 +   0
  box back  150 px face   cpu    21 | ids    26 -   0 +   5 | depth    21 -   0 +   0
  box back  300 px vertex cpu    94 | ids    91 -   4 +   1 | depth    91 -   4 +   1
  box back  300 px edge   cpu   170 | ids   182 -   5 +  17 | depth   163 -   7 +   0
  box back  300 px face   cpu    76 | ids    86 -   1 +  11 | depth    76 -   1 +   1
  cost build (per mesh state)             cpu      -     gpu    261.77
  cost render (per camera state), wall    cpu      -     gpu      5.62
  cost render, GL timer (GPU time)        cpu      -     gpu      1.16
  cost vertex: pick after an orbit        cpu      2.62  gpu      3.06
  cost vertex: hover pick, valid state    cpu      0.21  gpu      0.85
  cost vertex+depth: pick after an orbit  cpu      2.52  gpu      6.27
  cost vertex+depth: hover pick, valid state cpu      0.21  gpu      3.10
  cost edge: pick after an orbit          cpu      2.98  gpu      2.25
  cost edge: hover pick, valid state      cpu      0.82  gpu      0.84
  cost face: pick after an orbit          cpu      2.48  gpu      3.61
  cost face: hover pick, valid state      cpu      0.32  gpu      0.87
  cost box 300 px vertex, valid state     cpu     18.92  gpu      6.96
  cost box 300 px vertex, depth variant   cpu     18.92  gpu      3.52

[man_with_shoes_basemesh] 928 V / 1852 E / 926 F
  agree vertex       shaded n= 600  same  596 ( 99.3%)  half-px   0  real   4 [gpu none 0, cpu none 0, other 4]
      e.g. front (625,521): cpu VertexId(500) gpu VertexId(502)
      e.g. front (725,381): cpu VertexId(635) gpu VertexId(637)
      e.g. back (458,492): cpu VertexId(491) gpu VertexId(444)
  agree vertex+depth shaded n= 600  same  596 ( 99.3%)  half-px   0  real   4 [gpu none 0, cpu none 0, other 4]
      e.g. front (625,521): cpu VertexId(500) gpu VertexId(502)
      e.g. front (725,381): cpu VertexId(635) gpu VertexId(637)
      e.g. back (458,492): cpu VertexId(491) gpu VertexId(444)
  agree edge         shaded n= 600  same  597 ( 99.5%)  half-px   0  real   3 [gpu none 0, cpu none 0, other 3]
      e.g. front (454,325): cpu EdgeId(802) gpu EdgeId(803)
      e.g. back (418,453): cpu EdgeId(1320) gpu EdgeId(1323)
      e.g. back (542,591): cpu EdgeId(532) gpu EdgeId(879)
  agree face         shaded n= 600  same  587 ( 97.8%)  half-px   9  real   4 [gpu none 0, cpu none 1, other 3]
      e.g. front (423,501): cpu FaceId(160) gpu FaceId(159)
      e.g. front (725,370): cpu FaceId(580) gpu FaceId(581)
      e.g. back (558,463): cpu FaceId(12) gpu FaceId(285)
  agree vertex       wire   n= 600  same  600 (100.0%)  half-px   0  real   0 [gpu none 0, cpu none 0, other 0]
  agree vertex+depth wire   n= 600  same  600 (100.0%)  half-px   0  real   0 [gpu none 0, cpu none 0, other 0]
  agree edge         wire   n= 600  same  600 (100.0%)  half-px   0  real   0 [gpu none 0, cpu none 0, other 0]
  box front  60 px vertex cpu    11 | ids    11 -   0 +   0 | depth    11 -   0 +   0
  box front  60 px edge   cpu    14 | ids    15 -   0 +   1 | depth    14 -   0 +   0
  box front  60 px face   cpu     3 | ids     4 -   0 +   1 | depth     3 -   0 +   0
  box front 150 px vertex cpu    48 | ids    48 -   0 +   0 | depth    48 -   0 +   0
  box front 150 px edge   cpu    79 | ids    88 -   1 +  10 | depth    79 -   0 +   0
  box front 150 px face   cpu    31 | ids    37 -   0 +   6 | depth    31 -   0 +   0
  box front 300 px vertex cpu   175 | ids   175 -   1 +   1 | depth   175 -   1 +   1
  box front 300 px edge   cpu   298 | ids   325 -   6 +  33 | depth   292 -   6 +   0
  box front 300 px face   cpu   124 | ids   159 -   3 +  38 | depth   123 -   2 +   1
  box back   60 px vertex cpu    12 | ids    11 -   1 +   0 | depth    11 -   1 +   0
  box back   60 px edge   cpu    14 | ids    14 -   1 +   1 | depth    14 -   0 +   0
  box back   60 px face   cpu     4 | ids     4 -   1 +   1 | depth     4 -   0 +   0
  box back  150 px vertex cpu    55 | ids    54 -   1 +   0 | depth    54 -   1 +   0
  box back  150 px edge   cpu    91 | ids    92 -   2 +   3 | depth    91 -   0 +   0
  box back  150 px face   cpu    38 | ids    44 -   2 +   8 | depth    38 -   0 +   0
  box back  300 px vertex cpu   229 | ids   228 -   2 +   1 | depth   228 -   2 +   1
  box back  300 px edge   cpu   396 | ids   415 -   9 +  28 | depth   396 -   3 +   3
  box back  300 px face   cpu   169 | ids   211 -   6 +  48 | depth   169 -   2 +   2
  cost build (per mesh state)             cpu      -     gpu     48.64
  cost render (per camera state), wall    cpu      -     gpu      0.90
  cost render, GL timer (GPU time)        cpu      -     gpu      0.67
  cost vertex: pick after an orbit        cpu      6.61  gpu      1.64
  cost vertex: hover pick, valid state    cpu      0.39  gpu      0.51
  cost vertex+depth: pick after an orbit  cpu      6.53  gpu      2.33
  cost vertex+depth: hover pick, valid state cpu      0.52  gpu      0.78
  cost edge: pick after an orbit          cpu      7.97  gpu      1.81
  cost edge: hover pick, valid state      cpu      1.45  gpu      0.49
  cost face: pick after an orbit          cpu      6.09  gpu      1.46
  cost face: hover pick, valid state      cpu      0.29  gpu      0.23
  cost box 300 px vertex, valid state     cpu     17.70  gpu      6.42
  cost box 300 px vertex, depth variant   cpu     17.70  gpu      3.84

[gollum_20k] 21875 V / 43750 E / 21875 F
  agree vertex       shaded n= 600  same  586 ( 97.7%)  half-px   0  real  14 [gpu none 0, cpu none 0, other 14]
      e.g. front (653,463): cpu VertexId(20907) gpu VertexId(20910)
      e.g. front (477,272): cpu VertexId(16795) gpu VertexId(16794)
      e.g. front (371,587): cpu VertexId(5235) gpu VertexId(5238)
  agree vertex+depth shaded n= 600  same  592 ( 98.7%)  half-px   0  real   8 [gpu none 0, cpu none 0, other 8]
      e.g. front (653,463): cpu VertexId(20907) gpu VertexId(20910)
      e.g. front (371,587): cpu VertexId(5235) gpu VertexId(5238)
      e.g. front (693,366): cpu VertexId(14760) gpu VertexId(14761)
  agree edge         shaded n= 600  same  578 ( 96.3%)  half-px   1  real  21 [gpu none 0, cpu none 0, other 21]
      e.g. front (644,428): cpu EdgeId(41442) gpu EdgeId(41459)
      e.g. front (350,530): cpu EdgeId(10858) gpu EdgeId(11898)
      e.g. front (583,584): cpu EdgeId(33788) gpu EdgeId(33801)
  agree face         shaded n= 600  same  520 ( 86.7%)  half-px  79  real   1 [gpu none 0, cpu none 0, other 1]
      e.g. back (328,391): cpu FaceId(15849) gpu FaceId(15848)
  agree vertex       wire   n= 600  same  582 ( 97.0%)  half-px   3  real  15 [gpu none 0, cpu none 0, other 15]
      e.g. front (428,390): cpu VertexId(8759) gpu VertexId(13114)
      e.g. front (546,348): cpu VertexId(18508) gpu VertexId(18509)
      e.g. front (477,272): cpu VertexId(16795) gpu VertexId(16794)
  agree vertex+depth wire   n= 600  same  600 (100.0%)  half-px   0  real   0 [gpu none 0, cpu none 0, other 0]
  agree edge         wire   n= 600  same  554 ( 92.3%)  half-px  10  real  36 [gpu none 0, cpu none 0, other 36]
      e.g. front (644,428): cpu EdgeId(41442) gpu EdgeId(41459)
      e.g. front (583,584): cpu EdgeId(33788) gpu EdgeId(33790)
      e.g. front (626,392): cpu EdgeId(30814) gpu EdgeId(30822)
  box front  60 px vertex cpu   169 | ids   160 -   9 +   0 | depth   169 -   0 +   0
  box front  60 px edge   cpu   299 | ids   270 -  29 +   0 | depth   299 -   0 +   0
  box front  60 px face   cpu   131 | ids   129 -   2 +   0 | depth   131 -   0 +   0
  box front 150 px vertex cpu  2018 | ids  1950 -  94 +  26 | depth  2047 -  17 +  46
  box front 150 px edge   cpu  3880 | ids  3377 - 567 +  64 | depth  3938 -  31 +  89
  box front 150 px face   cpu  1863 | ids  1814 -  87 +  38 | depth  1907 -  15 +  59
  box front 300 px vertex cpu  6350 | ids  6232 - 220 + 102 | depth  6457 -  48 + 155
  box front 300 px edge   cpu 12455 | ids 11315 -1349 + 209 | depth 12737 -  91 + 373
  box front 300 px face   cpu  6099 | ids  6006 - 262 + 169 | depth  6294 -  37 + 232
  box back   60 px vertex cpu    30 | ids    30 -   0 +   0 | depth    30 -   0 +   0
  box back   60 px edge   cpu    44 | ids    44 -   0 +   0 | depth    44 -   0 +   0
  box back   60 px face   cpu    16 | ids    16 -   0 +   0 | depth    16 -   0 +   0
  box back  150 px vertex cpu   987 | ids   950 -  60 +  23 | depth  1012 -   9 +  34
  box back  150 px edge   cpu  1857 | ids  1564 - 340 +  47 | depth  1921 -  16 +  80
  box back  150 px face   cpu   879 | ids   863 -  54 +  38 | depth   913 -   8 +  42
  box back  300 px vertex cpu  4464 | ids  4351 - 201 +  88 | depth  4581 -  29 + 146
  box back  300 px edge   cpu  8714 | ids  7677 -1220 + 183 | depth  9027 -  75 + 388
  box back  300 px face   cpu  4256 | ids  4149 - 230 + 123 | depth  4468 -  32 + 244
  cost build (per mesh state)             cpu      -     gpu    794.85
  cost render (per camera state), wall    cpu      -     gpu      1.43
  cost render, GL timer (GPU time)        cpu      -     gpu      1.14
  cost vertex: pick after an orbit        cpu    160.85  gpu      3.29
  cost vertex: hover pick, valid state    cpu     18.63  gpu      1.65
  cost vertex+depth: pick after an orbit  cpu    162.49  gpu      4.49
  cost vertex+depth: hover pick, valid state cpu     20.18  gpu      2.33
  cost edge: pick after an orbit          cpu    187.66  gpu      3.75
  cost edge: hover pick, valid state      cpu     43.39  gpu      1.96
  cost face: pick after an orbit          cpu    150.21  gpu      2.40
  cost face: hover pick, valid state      cpu      8.02  gpu      0.71
  cost box 300 px vertex, valid state     cpu   2384.48  gpu     89.06
  cost box 300 px vertex, depth variant   cpu   2384.48  gpu     85.38
```
## Lauf 2: `probe_gpu_picking.py --assets examples/meshes/gollum.obj --cursors 150 --repeats 8` (87 500 V)

```
PS C:\Users\Manuel\Mirai_Bastel> python experiments/gpu_picking_spike/probe_gpu_picking.py --assets examples/meshes/gollum.obj --cursors 150 --repeats 8
... gollum
GPU ID-buffer picking vs CPU picker (spike, WP-VIEW-PERF-02), ms p50
Platform: Windows-10-10.0.19045-SP0
CPU: Intel64 Family 6 Model 23 Stepping 10, GenuineIntel (4 logical cores)
Python: 3.14.2
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Run: hidden 1024x768 window, 150 cursors per camera (front, back), 8 samples per cost row

[gollum] 87500 V / 175000 E / 87500 F
  agree vertex       shaded n= 300  same  272 ( 90.7%)  half-px   3  real  25 [gpu none 0, cpu none 0, other 25]
      e.g. front (644,428): cpu VertexId(20934) gpu VertexId(83769)
      e.g. front (583,584): cpu VertexId(72315) gpu VertexId(72322)
      e.g. front (713,250): cpu VertexId(67360) gpu VertexId(67372)
  agree vertex+depth shaded n= 300  same  290 ( 96.7%)  half-px   0  real  10 [gpu none 0, cpu none 0, other 10]
      e.g. front (644,428): cpu VertexId(20934) gpu VertexId(83769)
      e.g. front (632,421): cpu VertexId(84397) gpu VertexId(84389)
      e.g. front (583,584): cpu VertexId(72315) gpu VertexId(72322)
  agree edge         shaded n= 300  same  267 ( 89.0%)  half-px   3  real  30 [gpu none 0, cpu none 0, other 30]
      e.g. front (556,613): cpu EdgeId(125748) gpu EdgeId(125753)
      e.g. front (644,428): cpu EdgeId(164695) gpu EdgeId(164774)
      e.g. front (632,421): cpu EdgeId(166364) gpu EdgeId(166381)
  agree face         shaded n= 300  same  236 ( 78.7%)  half-px  64  real   0 [gpu none 0, cpu none 0, other 0]
  agree vertex       wire   n= 300  same  259 ( 86.3%)  half-px   9  real  32 [gpu none 0, cpu none 0, other 32]
      e.g. front (632,421): cpu VertexId(84389) gpu VertexId(84397)
      e.g. front (350,530): cpu VertexId(6279) gpu VertexId(39407)
      e.g. front (571,424): cpu VertexId(85772) gpu VertexId(84165)
  agree vertex+depth wire   n= 300  same  295 ( 98.3%)  half-px   0  real   5 [gpu none 0, cpu none 0, other 5]
      e.g. back (646,430): cpu VertexId(39287) gpu VertexId(5170)
      e.g. back (470,431): cpu VertexId(58596) gpu VertexId(25649)
      e.g. back (419,490): cpu VertexId(74695) gpu VertexId(74696)
  agree edge         wire   n= 300  same  236 ( 78.7%)  half-px   8  real  56 [gpu none 0, cpu none 0, other 56]
      e.g. front (398,454): cpu EdgeId(74785) gpu EdgeId(74782)
      e.g. front (556,613): cpu EdgeId(125748) gpu EdgeId(125753)
      e.g. front (380,491): cpu EdgeId(63505) gpu EdgeId(5201)
  box front  60 px vertex cpu   659 | ids   577 -  82 +   0 | depth   659 -   0 +   0
  box front  60 px edge   cpu  1241 | ids   993 - 248 +   0 | depth  1240 -   1 +   0
  box front  60 px face   cpu   583 | ids   546 -  37 +   0 | depth   583 -   0 +   0
  box front 150 px vertex cpu  8005 | ids  6579 -1501 +  75 | depth  8151 -  59 + 205
  box front 150 px edge   cpu 15692 | ids  9975 -5812 +  95 | depth 16069 - 106 + 483
  box front 150 px face   cpu  7686 | ids  6436 -1295 +  45 | depth  7889 -  61 + 264
  box front 300 px vertex cpu 25118 | ids 21709 -3656 + 247 | depth 25709 - 151 + 742
  box front 300 px edge   cpu 49720 | ids 33693 -16337 + 310 | depth 51130 - 303 +1713
  box front 300 px face   cpu 24604 | ids 21163 -3582 + 141 | depth 25395 - 152 + 943
  box back   60 px vertex cpu   111 | ids   111 -   0 +   0 | depth   111 -   0 +   0
  box back   60 px edge   cpu   190 | ids   187 -   3 +   0 | depth   190 -   0 +   0
  box back   60 px face   cpu    81 | ids    81 -   0 +   0 | depth    81 -   0 +   0
  box back  150 px vertex cpu  3889 | ids  3169 - 765 +  45 | depth  4043 -  32 + 186
  box back  150 px edge   cpu  7565 | ids  5011 -2598 +  44 | depth  7922 -  54 + 411
  box back  150 px face   cpu  3687 | ids  2985 - 738 +  36 | depth  3861 -  28 + 202
  box back  300 px vertex cpu 17573 | ids 14618 -3171 + 216 | depth 18231 - 116 + 774
  box back  300 px edge   cpu 34721 | ids 22698 -12274 + 251 | depth 36304 - 211 +1794
  box back  300 px face   cpu 17157 | ids 14004 -3268 + 115 | depth 18068 -  89 +1000
  cost build (per mesh state)             cpu      -     gpu   3086.92
  cost render (per camera state), wall    cpu      -     gpu     10.78
  cost render, GL timer (GPU time)        cpu      -     gpu     10.33
  cost vertex: pick after an orbit        cpu    661.92  gpu     13.96
  cost vertex: hover pick, valid state    cpu     85.21  gpu      3.34
  cost vertex+depth: pick after an orbit  cpu    653.87  gpu     15.43
  cost vertex+depth: hover pick, valid state cpu     80.19  gpu      4.60
  cost edge: pick after an orbit          cpu    774.54  gpu     15.46
  cost edge: hover pick, valid state      cpu    197.36  gpu      4.09
  cost face: pick after an orbit          cpu    618.67  gpu     11.79
  cost face: hover pick, valid state      cpu     35.22  gpu      0.65
  cost box 300 px vertex, valid state     cpu  14522.31  gpu    294.59
  cost box 300 px vertex, depth variant   cpu  14522.31  gpu    332.24
```
