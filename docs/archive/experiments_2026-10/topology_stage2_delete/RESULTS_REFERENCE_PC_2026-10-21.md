# Raw output, reference PC (Manu), 2026-10-21

`python experiments\topology_stage2_delete\probe_stage2.py` in PowerShell (defaults: configurations none, stage1,
H1,V1, all; `--steps 20 --row-seconds 120`, GC on; Python 3.14.2), then `check_b2.py` (run by the probe). Copied
from Manu's message; within the 120 s budget the `none` rows reached n = 15-17. His sentence after the output is
recorded in the README ("Result: reference PC").

```text
===== none =====
configuration: none  (stage-2 switches: -)
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: (3, 3)
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
GC on, threshold (2000, 10, 0)
[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2671 ms
  delete 1 face            n= 17
    delete frame (op as triggered)   p50   1687.02  p95   1890.28  max   1890.28
      op (Core delete)               p50     15.79  p95     16.36  max     16.36
      history                        p50    345.57  p95    426.64  max    426.64
      hover re-pick                  p50    143.14  p95    145.26  max    145.26
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      4.12  p95      4.63  max      4.63
      viewport sync                  p50   1149.87  p95   1298.56  max   1298.56
      draw                           p50     10.52  p95     13.39  max     13.39
    next hover frame                 p50      9.24  p95     10.24  max     10.24
    undo frame                       p50   1781.30  p95   1921.37  max   1921.37
      history                        p50    453.14  p95    598.37  max    598.37
      hover re-pick (incl. sync)     p50    146.75  p95    171.16  max    171.16
      other                          p50      0.16  p95      0.17  max      0.17
      viewport sync                  p50   1158.11  p95   1303.42  max   1303.42
    redo frame                       p50   1722.47  p95   1875.56  max   1875.56
    op + undo                        p50   3427.25  p95   3637.42  max   3637.42
  delete 20 faces          n= 17
    delete frame (op as triggered)   p50   1708.53  p95   1737.78  max   1737.78
      op (Core delete)               p50     17.18  p95     18.13  max     18.13
      history                        p50    349.02  p95    389.70  max    389.70
      hover re-pick                  p50    144.90  p95    146.82  max    146.82
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      0.20  p95      0.24  max      0.24
      viewport sync                  p50   1192.07  p95   1228.64  max   1228.64
      draw                           p50     10.66  p95     14.42  max     14.42
    next hover frame                 p50      9.38  p95     10.68  max     10.68
    undo frame                       p50   1891.05  p95   1914.20  max   1914.20
      history                        p50    460.59  p95    478.08  max    478.08
      hover re-pick (incl. sync)     p50    146.98  p95    149.27  max    149.27
      other                          p50      0.16  p95      0.22  max      0.22
      viewport sync                  p50   1272.77  p95   1291.06  max   1291.06
    redo frame                       p50   1557.77  p95   1752.12  max   1752.12
    op + undo                        p50   3605.67  p95   3641.71  max   3641.71
  delete 1 vertex          n= 15
    delete frame (op as triggered)   p50   1897.36  p95   1998.10  max   1998.10
      op (Core delete)               p50     35.79  p95     36.64  max     36.64
      history                        p50    420.38  p95    487.51  max    487.51
      hover re-pick                  p50    240.36  p95    385.44  max    385.44
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      0.20  p95      0.23  max      0.23
      viewport sync                  p50   1142.66  p95   1377.09  max   1377.09
      draw                           p50     10.07  p95     11.83  max     11.83
    next hover frame                 p50     22.99  p95     24.48  max     24.48
    undo frame                       p50   2042.57  p95   2210.92  max   2210.92
      history                        p50    532.42  p95    712.45  max    712.45
      hover re-pick (incl. sync)     p50    248.02  p95    460.26  max    460.26
      other                          p50      0.16  p95      0.22  max      0.22
      viewport sync                  p50   1226.81  p95   1449.08  max   1449.08
    redo frame                       p50   1923.17  p95   2085.78  max   2085.78
    op + undo                        p50   3830.96  p95   4117.80  max   4117.80
Counters (whole run incl. warm-up):
  stage 1: topology syncs 0 (full buffer rebuilds 0, V2 patch syncs 0); faces re-triangulated 0, reused 0; H0: changed by counts 0, full-compare fallbacks 0, lazy after-exports at Undo 0
  V1:      V1 patch syncs 0, fallbacks to a full sync 0; faces killed 0, revived 0
  GPU:     GPU picks 0 (ID renders 0, 0.0 ms; reads 0.0 ms; syncs before a pick 0); CPU picker used 0x
SUMMARY none | delete 1 face: frame 1687, undo 1781, redo 1722 | delete 20 faces: frame 1709, undo 1891, redo 1558 | delete 1 vertex: frame 1897, undo 2043, redo 1923
===== stage1 =====
configuration: stage1  (stage-2 switches: -)
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: (3, 3)
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
GC on, threshold (2000, 10, 0)
[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2540 ms
  delete 1 face            n= 20
    delete frame (op as triggered)   p50    667.14  p95    840.96  max    841.69
      op (Core delete)               p50     18.43  p95     19.42  max     19.87
      history                        p50    150.45  p95    320.67  max    323.11
      hover re-pick                  p50    149.69  p95    153.38  max    153.50
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      9.28  p95     10.47  max     11.49
      viewport sync                  p50    325.08  p95    335.16  max    343.38
      draw                           p50     10.06  p95     12.17  max     12.75
    next hover frame                 p50     10.80  p95     13.31  max     13.86
    undo frame                       p50   1115.78  p95   1166.01  max   1188.81
      history                        p50    621.69  p95    660.17  max    688.09
      hover re-pick (incl. sync)     p50    149.05  p95    154.33  max    154.34
      other                          p50      0.17  p95      0.21  max      0.21
      viewport sync                  p50    340.75  p95    346.25  max    347.79
    redo frame                       p50    987.69  p95   1077.72  max   1080.72
    op + undo                        p50   1821.29  p95   1978.64  max   1991.26
  delete 20 faces          n= 20
    delete frame (op as triggered)   p50    787.30  p95    837.42  max    855.46
      op (Core delete)               p50     19.59  p95     20.07  max     20.38
      history                        p50    264.02  p95    324.33  max    341.00
      hover re-pick                  p50    151.91  p95    154.05  max    154.57
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      9.31  p95     10.83  max     11.05
      viewport sync                  p50    328.75  p95    334.66  max    335.91
      draw                           p50     10.11  p95     10.86  max     11.56
    next hover frame                 p50     10.63  p95     11.79  max     12.00
    undo frame                       p50   1120.33  p95   1186.06  max   1247.26
      history                        p50    606.40  p95    679.94  max    737.62
      hover re-pick (incl. sync)     p50    149.05  p95    156.01  max    162.76
      other                          p50      0.18  p95      0.27  max      0.35
      viewport sync                  p50    348.30  p95    356.72  max    358.96
    redo frame                       p50   1009.15  p95   1083.81  max   1098.20
    op + undo                        p50   1867.66  p95   1980.16  max   1993.19
  delete 1 vertex          n= 20
    delete frame (op as triggered)   p50    774.41  p95   1016.79  max   1017.12
      op (Core delete)               p50     35.91  p95     37.23  max     37.49
      history                        p50    128.70  p95    384.33  max    386.36
      hover re-pick                  p50    246.44  p95    249.55  max    445.00
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      9.22  p95     10.44  max     10.72
      viewport sync                  p50    334.03  p95    340.57  max    341.82
      draw                           p50      9.77  p95     11.62  max     11.93
    next hover frame                 p50     24.59  p95     25.65  max     25.84
    undo frame                       p50   1349.09  p95   1423.18  max   1516.43
      history                        p50    638.96  p95    809.63  max    910.64
      hover re-pick (incl. sync)     p50    253.00  p95    418.02  max    422.91
      other                          p50      0.17  p95      0.18  max      0.21
      viewport sync                  p50    351.09  p95    355.84  max    363.48
    redo frame                       p50   1208.12  p95   1296.50  max   1318.81
    op + undo                        p50   2177.22  p95   2378.81  max   2393.33
Counters (whole run incl. warm-up):
  stage 1: topology syncs 252 (full buffer rebuilds 253, V2 patch syncs 0); faces re-triangulated 22925, reused 5510400; H0: changed by counts 63, full-compare fallbacks 0, lazy after-exports at Undo 63
  V1:      V1 patch syncs 0, fallbacks to a full sync 0; faces killed 0, revived 0
  GPU:     GPU picks 0 (ID renders 0, 0.0 ms; reads 0.0 ms; syncs before a pick 0); CPU picker used 0x
SUMMARY stage1 | delete 1 face: frame 667, undo 1116, redo 988 | delete 20 faces: frame 787, undo 1120, redo 1009 | delete 1 vertex: frame 774, undo 1349, redo 1208
===== H1,V1 =====
configuration: stage1+H1,V1  (stage-2 switches: H1,V1)
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: (3, 3)
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
GC on, threshold (2000, 10, 0)
[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2523 ms
  delete 1 face            n= 20
    delete frame (op as triggered)   p50    171.08  p95    176.32  max    371.44
      op (Core delete)               p50     14.88  p95     15.55  max     16.05
      history                        p50      5.11  p95      6.52  max      7.00
      hover re-pick                  p50    143.16  p95    149.29  max    236.91
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      0.13  p95      0.15  max      0.16
      viewport sync                  p50      3.91  p95      5.07  max      5.19
      draw                           p50      3.21  p95      5.45  max    109.18
    next hover frame                 p50      8.39  p95      9.41  max     35.01
    undo frame                       p50    159.53  p95    235.99  max    369.81
      history                        p50      9.38  p95     67.13  max     87.41
      hover re-pick (incl. sync)     p50    142.29  p95    151.21  max    295.98
      other                          p50      0.19  p95      0.21  max      0.22
      viewport sync                  p50      3.98  p95      5.23  max      5.47
    redo frame                       p50    150.45  p95    154.56  max    154.70
    op + undo                        p50    330.97  p95    408.53  max    741.25
  delete 20 faces          n= 20
    delete frame (op as triggered)   p50    176.12  p95    178.65  max    181.57
      op (Core delete)               p50     15.92  p95     17.07  max     17.15
      history                        p50      5.79  p95      7.11  max      7.29
      hover re-pick                  p50    140.19  p95    143.16  max    144.25
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      0.14  p95      0.16  max      0.19
      viewport sync                  p50      7.22  p95      8.26  max      8.63
      draw                           p50      6.10  p95      8.49  max      8.52
    next hover frame                 p50      9.10  p95      9.73  max     10.04
    undo frame                       p50    192.64  p95    272.09  max    291.24
      history                        p50     40.21  p95    116.61  max    137.02
      hover re-pick (incl. sync)     p50    141.50  p95    143.37  max    147.69
      other                          p50      0.22  p95      0.28  max      0.29
      viewport sync                  p50      6.76  p95      7.85  max      8.93
    redo frame                       p50    155.18  p95    156.62  max    158.11
    op + undo                        p50    368.97  p95    448.24  max    469.16
  delete 1 vertex          n= 20
    delete frame (op as triggered)   p50    278.05  p95    284.62  max    374.21
      op (Core delete)               p50     25.14  p95     26.45  max     27.08
      history                        p50     14.63  p95     16.35  max     16.55
      hover re-pick                  p50    226.01  p95    232.70  max    323.10
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      0.13  p95      0.14  max      0.24
      viewport sync                  p50      5.63  p95      6.58  max      7.04
      draw                           p50      6.05  p95      6.25  max      6.92
    next hover frame                 p50     24.45  p95     25.12  max     25.84
    undo frame                       p50    274.20  p95    386.46  max    391.94
      history                        p50     38.69  p95     66.35  max     70.26
      hover re-pick (incl. sync)     p50    226.09  p95    314.97  max    317.35
      other                          p50      0.19  p95      0.22  max      0.22
      viewport sync                  p50      4.23  p95      5.31  max      6.37
    redo frame                       p50    231.36  p95    319.36  max    354.75
    op + undo                        p50    552.69  p95    662.27  max    671.97
Counters (whole run incl. warm-up):
  stage 1: topology syncs 0 (full buffer rebuilds 1, V2 patch syncs 0); faces re-triangulated 21875, reused 0; H0: changed by counts 0, full-compare fallbacks 0, lazy after-exports at Undo 0
  V1:      V1 patch syncs 252, fallbacks to a full sync 0; faces killed 1050, revived 1050
  GPU:     GPU picks 0 (ID renders 0, 0.0 ms; reads 0.0 ms; syncs before a pick 0); CPU picker used 0x
SUMMARY stage1+H1,V1 | delete 1 face: frame 171, undo 160, redo 150 | delete 20 faces: frame 176, undo 193, redo 155 | delete 1 vertex: frame 278, undo 274, redo 231
===== all =====
configuration: stage1+H1,V1,GPU  (stage-2 switches: GPU,H1,V1)
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: (3, 3)
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
GC on, threshold (2000, 10, 0)
[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 2541 ms
  delete 1 face            n= 20
    delete frame (op as triggered)   p50     34.63  p95     36.94  max     37.68
      op (Core delete)               p50     18.98  p95     20.00  max     20.83
      history                        p50      5.11  p95      6.51  max      7.28
      hover re-pick                  p50      5.58  p95      7.11  max      8.40
        of which sync before pick    p50      3.42  p95      4.93  max      6.56
      other (selection, status)      p50      0.11  p95      0.16  max      0.18
      viewport sync                  p50      2.22  p95      3.29  max      3.44
      draw                           p50      1.97  p95      2.18  max      2.34
    next hover frame                 p50      1.91  p95      2.26  max      2.34
    undo frame                       p50     18.99  p95     24.58  max     97.00
      history                        p50      8.68  p95     14.33  max     87.26
      hover re-pick (incl. sync)     p50      5.59  p95      7.36  max      7.44
      other                          p50      0.18  p95      0.19  max      0.24
      viewport sync                  p50      2.00  p95      2.65  max      2.67
    redo frame                       p50      9.43  p95     10.52  max     10.78
    op + undo                        p50     53.84  p95     60.26  max    132.03
  delete 20 faces          n= 20
    delete frame (op as triggered)   p50     41.60  p95     43.15  max     43.81
      op (Core delete)               p50     20.00  p95     21.59  max     21.77
      history                        p50      5.41  p95      7.28  max      7.90
      hover re-pick                  p50      9.03  p95      9.87  max     10.05
        of which sync before pick    p50      6.49  p95      7.29  max      7.43
      other (selection, status)      p50      0.12  p95      0.15  max      0.29
      viewport sync                  p50      4.15  p95      5.46  max      6.54
      draw                           p50      1.99  p95      2.35  max      2.44
    next hover frame                 p50      1.95  p95      2.28  max      2.31
    undo frame                       p50     54.96  p95    135.44  max    139.56
      history                        p50     40.24  p95    121.88  max    125.14
      hover re-pick (incl. sync)     p50      8.80  p95      9.86  max     10.08
      other                          p50      0.20  p95      0.23  max      0.24
      viewport sync                  p50      2.73  p95      3.53  max      3.54
    redo frame                       p50     15.47  p95     16.40  max     16.72
    op + undo                        p50     96.52  p95    175.35  max    178.99
  delete 1 vertex          n= 20
    delete frame (op as triggered)   p50     54.27  p95     55.65  max     56.63
      op (Core delete)               p50     24.40  p95     25.48  max     26.56
      history                        p50     13.90  p95     15.57  max     16.09
      hover re-pick                  p50      9.08  p95      9.97  max     10.30
        of which sync before pick    p50      5.73  p95      6.76  max      6.88
      other (selection, status)      p50      0.12  p95      0.13  max      0.15
      viewport sync                  p50      3.82  p95      5.15  max      5.19
      draw                           p50      2.11  p95      2.40  max      2.53
    next hover frame                 p50      6.20  p95      7.35  max      7.38
    undo frame                       p50     50.27  p95    132.84  max    141.05
      history                        p50     38.48  p95    119.91  max    128.01
      hover re-pick (incl. sync)     p50      7.36  p95      8.30  max      8.65
      other                          p50      0.17  p95      0.19  max      0.21
      viewport sync                  p50      2.11  p95      2.89  max      2.96
    redo frame                       p50     15.21  p95     16.32  max     39.74
    op + undo                        p50    104.23  p95    184.25  max    195.17
Counters (whole run incl. warm-up):
  stage 1: topology syncs 0 (full buffer rebuilds 1, V2 patch syncs 0); faces re-triangulated 21875, reused 0; H0: changed by counts 0, full-compare fallbacks 0, lazy after-exports at Undo 0
  V1:      V1 patch syncs 252, fallbacks to a full sync 0; faces killed 1050, revived 1050
  GPU:     GPU picks 378 (ID renders 254, 336.7 ms; reads 362.0 ms; syncs before a pick 252); CPU picker used 0x
SUMMARY stage1+H1,V1,GPU | delete 1 face: frame 35, undo 19, redo 9 | delete 20 faces: frame 42, undo 55, redo 15 | delete 1 vertex: frame 54, undo 50, redo 15
===== AD-022 B2 check =====
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.14.2 (CPython)
GL_VERSION: (3, 3)
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
[gollum_20k] 21875 V / 21875 F, window 1024x768
attribute location of 'position': store program 0 | face ID program 0 | point ID program 0
1. per-pixel B2 vs B1 (Shaded: points depth-tested against the faces)
  front, fresh mesh                  face pixels covered  108034; B2 face == B1 face on 786432/786432 px (differ 0, dead IDs 0); B2 point == B1 point on 786432/786432 px (differ 0)
  back, fresh mesh                   face pixels covered  113735; B2 face == B1 face on 786432/786432 px (differ 0, dead IDs 0); B2 point == B1 point on 786432/786432 px (differ 0)
  front, after Delete 20 faces       face pixels covered  108302; B2 face == B1 face on 786432/786432 px (differ 0, dead IDs 0); B2 point == B1 point on 786432/786432 px (differ 0)
  back, after Delete 20 faces        face pixels covered  113860; B2 face == B1 face on 786432/786432 px (differ 0, dead IDs 0); B2 point == B1 point on 786432/786432 px (differ 0)
  front, after its Undo              face pixels covered  108034; B2 face == B1 face on 786432/786432 px (differ 0, dead IDs 0); B2 point == B1 point on 786432/786432 px (differ 0)
  back, after its Undo               face pixels covered  113735; B2 face == B1 face on 786432/786432 px (differ 0, dead IDs 0); B2 point == B1 point on 786432/786432 px (differ 0)
2./3. agreement with the CPU picker, 300 cursors per camera (integer pixel corners; half-px = the CPU agrees at the pixel centre)
  front face   non-trivial 173: same 130 ( 75.1 %), half-px  43, gpu none  0, cpu none  0, other  0
  front vertex non-trivial 206: same 198 ( 96.1 %), half-px   0, gpu none  0, cpu none  0, other  8
  back  face   non-trivial 162: same 138 ( 85.2 %), half-px  24, gpu none  0, cpu none  0, other  0
  back  vertex non-trivial 183: same 179 ( 97.8 %), half-px   1, gpu none  0, cpu none  0, other  3
4. one pick after a camera change (ID render + read), 20 orbit steps, face / vertex mode
  face   wall p50   2.83 ms, max   3.47 ms; GPU time p50 2.77 ms
  vertex wall p50   5.60 ms, max  23.98 ms; GPU time p50 5.53 ms
B2 RESULT gl_PrimitiveID face mapping EXACT (differing face pixels 0, point pixels 0); position location store/face/point (0, 0, 0); real pick differences vs CPU 11

===== summary (ms, p50) =====
none | delete 1 face: frame 1687, undo 1781, redo 1722 | delete 20 faces: frame 1709, undo 1891, redo 1558 | delete 1 vertex: frame 1897, undo 2043, redo 1923
stage1 | delete 1 face: frame 667, undo 1116, redo 988 | delete 20 faces: frame 787, undo 1120, redo 1009 | delete 1 vertex: frame 774, undo 1349, redo 1208
stage1+H1,V1 | delete 1 face: frame 171, undo 160, redo 150 | delete 20 faces: frame 176, undo 193, redo 155 | delete 1 vertex: frame 278, undo 274, redo 231
stage1+H1,V1,GPU | delete 1 face: frame 35, undo 19, redo 9 | delete 20 faces: frame 42, undo 55, redo 15 | delete 1 vertex: frame 54, undo 50, redo 15
B2 RESULT gl_PrimitiveID face mapping EXACT (differing face pixels 0, point pixels 0); position location store/face/point (0, 0, 0); real pick differences vs CPU 11
```
