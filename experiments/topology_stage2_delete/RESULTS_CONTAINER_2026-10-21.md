# Raw output, container, 2026-10-21 [C]

`probe_stage2.py` with the defaults (configurations none, stage1, H1,V1, all; `--steps 20 --row-seconds 120`, GC on), then `check_b2.py`. Xeon @ 2.80 GHz, Python 3.13.16, llvmpipe: **not the reference PC** (the ID render and the draw are software rasterisation here).

```text
===== none =====
configuration: none  (stage-2 switches: -)
Platform: Linux-6.18.44-fc-v139-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.80GHz (4 logical cores)
Python: 3.13.16 (CPython)
GL_VERSION: (4, 5)
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
GC on, threshold (2000, 10, 10)
[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 1154 ms
  delete 1 face            n= 20
    delete frame (op as triggered)   p50    969.68  p95   1426.71  max   1457.78
      op (Core delete)               p50      8.46  p95     12.02  max     14.57
      history                        p50    367.86  p95    606.54  max    671.51
      hover re-pick                  p50     62.91  p95    251.74  max    288.72
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      1.49  p95      2.28  max      2.49
      viewport sync                  p50    502.18  p95    715.81  max    824.44
      draw                           p50     12.34  p95     17.80  max     18.11
    next hover frame                 p50     11.88  p95     18.48  max     20.45
    undo frame                       p50   1164.51  p95   1492.43  max   1505.32
      history                        p50    519.92  p95    623.08  max    707.25
      hover re-pick (incl. sync)     p50     89.55  p95    296.81  max    306.05
      other                          p50      0.17  p95      0.25  max      0.28
      viewport sync                  p50    512.17  p95    775.58  max    806.43
    redo frame                       p50   1222.52  p95   1591.44  max   1610.91
    op + undo                        p50   2176.51  p95   2740.58  max   2950.22
  delete 20 faces          n= 20
    delete frame (op as triggered)   p50    926.84  p95   1114.48  max   1136.05
      op (Core delete)               p50      8.99  p95     13.46  max     18.52
      history                        p50    333.00  p95    373.40  max    389.10
      hover re-pick                  p50     68.40  p95    279.23  max    295.83
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      0.19  p95      0.21  max      0.22
      viewport sync                  p50    496.12  p95    650.55  max    650.78
      draw                           p50     11.81  p95     16.95  max     17.64
    next hover frame                 p50     11.58  p95     17.98  max     20.40
    undo frame                       p50   1156.22  p95   1441.21  max   1659.55
      history                        p50    519.81  p95    620.58  max    784.69
      hover re-pick (incl. sync)     p50     74.97  p95    279.52  max    355.01
      other                          p50      0.18  p95      0.24  max      0.25
      viewport sync                  p50    524.15  p95    705.87  max    813.15
    redo frame                       p50   1218.31  p95   1454.14  max   1500.87
    op + undo                        p50   2132.97  p95   2486.46  max   2704.22
  delete 1 vertex          n= 20
    delete frame (op as triggered)   p50   1176.58  p95   1422.60  max   1557.88
      op (Core delete)               p50     23.32  p95     30.49  max     36.02
      history                        p50    401.19  p95    539.82  max    545.80
      hover re-pick                  p50    138.46  p95    356.49  max    390.92
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      0.19  p95      0.24  max      0.25
      viewport sync                  p50    536.39  p95    781.96  max    852.21
      draw                           p50     12.47  p95     17.28  max     19.53
    next hover frame                 p50     21.59  p95     32.18  max     32.61
    undo frame                       p50   1536.40  p95   1746.11  max   1753.42
      history                        p50    740.15  p95    915.20  max    992.14
      hover re-pick (incl. sync)     p50    130.38  p95    399.21  max    511.59
      other                          p50      0.17  p95      0.23  max      0.24
      viewport sync                  p50    538.92  p95    789.09  max    802.88
    redo frame                       p50   1516.97  p95   1832.29  max   1885.70
    op + undo                        p50   2710.68  p95   2956.30  max   3303.99
Counters (whole run incl. warm-up):
  stage 1: topology syncs 0 (full buffer rebuilds 0, V2 patch syncs 0); faces re-triangulated 0, reused 0; H0: changed by counts 0, full-compare fallbacks 0, lazy after-exports at Undo 0
  V1:      V1 patch syncs 0, fallbacks to a full sync 0; faces killed 0, revived 0
  GPU:     GPU picks 0 (ID renders 0, 0.0 ms; reads 0.0 ms; syncs before a pick 0); CPU picker used 0x
SUMMARY none | delete 1 face: frame 970, undo 1165, redo 1223 | delete 20 faces: frame 927, undo 1156, redo 1218 | delete 1 vertex: frame 1177, undo 1536, redo 1517
===== stage1 =====
configuration: stage1  (stage-2 switches: -)
Platform: Linux-6.18.44-fc-v139-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.80GHz (4 logical cores)
Python: 3.13.16 (CPython)
GL_VERSION: (4, 5)
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
GC on, threshold (2000, 10, 10)
[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 987 ms
  delete 1 face            n= 20
    delete frame (op as triggered)   p50    332.76  p95    424.32  max    453.36
      op (Core delete)               p50     10.31  p95     13.99  max     14.66
      history                        p50     95.48  p95    131.58  max    157.65
      hover re-pick                  p50     66.56  p95     96.77  max    105.21
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      5.27  p95      8.50  max      8.74
      viewport sync                  p50    132.77  p95    185.32  max    198.52
      draw                           p50     12.49  p95     18.84  max     20.30
    next hover frame                 p50     12.31  p95     21.02  max     24.11
    undo frame                       p50   1166.90  p95   1320.04  max   1344.94
      history                        p50    916.35  p95   1061.50  max   1099.91
      hover re-pick (incl. sync)     p50     67.28  p95    108.74  max    181.25
      other                          p50      0.18  p95      0.21  max      0.25
      viewport sync                  p50    147.75  p95    219.95  max    225.23
    redo frame                       p50    925.06  p95   1033.64  max   1077.33
    op + undo                        p50   1499.93  p95   1732.95  max   1769.26
  delete 20 faces          n= 20
    delete frame (op as triggered)   p50    313.80  p95    375.93  max    402.46
      op (Core delete)               p50     10.67  p95     15.11  max     17.36
      history                        p50     90.08  p95    116.54  max    144.68
      hover re-pick                  p50     68.07  p95     94.36  max     94.72
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      5.05  p95      7.23  max      8.37
      viewport sync                  p50    126.98  p95    163.85  max    172.70
      draw                           p50     12.29  p95     15.29  max     18.18
    next hover frame                 p50     12.92  p95     20.12  max     23.45
    undo frame                       p50   1202.45  p95   1346.46  max   1380.01
      history                        p50    929.92  p95   1025.74  max   1138.92
      hover re-pick (incl. sync)     p50     66.74  p95    111.41  max    117.55
      other                          p50      0.19  p95      0.22  max      0.31
      viewport sync                  p50    153.93  p95    229.38  max    240.99
    redo frame                       p50    918.02  p95   1088.55  max   1121.29
    op + undo                        p50   1506.06  p95   1692.34  max   1714.24
  delete 1 vertex          n= 20
    delete frame (op as triggered)   p50    496.04  p95    791.07  max    845.70
      op (Core delete)               p50     23.05  p95     29.91  max     32.51
      history                        p50     99.33  p95    422.61  max    452.51
      hover re-pick                  p50    137.12  p95    196.48  max    213.41
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      5.89  p95      8.65  max      8.72
      viewport sync                  p50    161.53  p95    221.54  max    222.30
      draw                           p50     14.12  p95     18.22  max     19.65
    next hover frame                 p50     22.51  p95     33.21  max     39.42
    undo frame                       p50   1449.91  p95   1609.23  max   1796.75
      history                        p50   1139.41  p95   1294.90  max   1530.21
      hover re-pick (incl. sync)     p50    132.31  p95    196.88  max    506.17
      other                          p50      0.18  p95      0.24  max      0.25
      viewport sync                  p50    155.78  p95    201.34  max    201.49
    redo frame                       p50   1166.69  p95   1316.91  max   1381.18
    op + undo                        p50   1956.87  p95   2300.43  max   2337.34
Counters (whole run incl. warm-up):
  stage 1: topology syncs 252 (full buffer rebuilds 253, V2 patch syncs 0); faces re-triangulated 22925, reused 5510400; H0: changed by counts 63, full-compare fallbacks 0, lazy after-exports at Undo 63
  V1:      V1 patch syncs 0, fallbacks to a full sync 0; faces killed 0, revived 0
  GPU:     GPU picks 0 (ID renders 0, 0.0 ms; reads 0.0 ms; syncs before a pick 0); CPU picker used 0x
SUMMARY stage1 | delete 1 face: frame 333, undo 1167, redo 925 | delete 20 faces: frame 314, undo 1202, redo 918 | delete 1 vertex: frame 496, undo 1450, redo 1167
===== H1,V1 =====
configuration: stage1+H1,V1  (stage-2 switches: H1,V1)
Platform: Linux-6.18.44-fc-v139-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.80GHz (4 logical cores)
Python: 3.13.16 (CPython)
GL_VERSION: (4, 5)
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
GC on, threshold (2000, 10, 10)
[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 1017 ms
  delete 1 face            n= 20
    delete frame (op as triggered)   p50    102.76  p95    142.42  max    143.33
      op (Core delete)               p50      7.91  p95     11.38  max     12.10
      history                        p50      3.43  p95      4.13  max      4.17
      hover re-pick                  p50     73.20  p95    108.72  max    110.35
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      0.12  p95      0.18  max      0.21
      viewport sync                  p50      3.38  p95      5.59  max      5.71
      draw                           p50     13.49  p95     16.80  max     18.46
    next hover frame                 p50     13.53  p95     22.07  max     23.09
    undo frame                       p50     89.08  p95    130.07  max    134.72
      history                        p50      6.37  p95      9.54  max      9.73
      hover re-pick (incl. sync)     p50     70.07  p95    105.45  max    111.42
      other                          p50      0.18  p95      0.24  max      0.28
      viewport sync                  p50      3.34  p95      5.36  max      6.51
    redo frame                       p50     92.09  p95    134.47  max    152.99
    op + undo                        p50    191.20  p95    268.96  max    272.15
  delete 20 faces          n= 20
    delete frame (op as triggered)   p50    102.39  p95    161.41  max    239.41
      op (Core delete)               p50      8.84  p95     12.19  max     12.52
      history                        p50      3.17  p95      4.47  max      4.53
      hover re-pick                  p50     71.60  p95    119.77  max    202.36
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      0.13  p95      0.17  max      0.17
      viewport sync                  p50      4.77  p95      7.49  max      7.87
      draw                           p50     13.90  p95     17.13  max     18.20
    next hover frame                 p50     12.66  p95     19.35  max     21.52
    undo frame                       p50    103.00  p95    165.24  max    233.57
      history                        p50     20.52  p95     30.62  max    133.31
      hover re-pick (incl. sync)     p50     68.75  p95    107.05  max    116.10
      other                          p50      0.21  p95      0.26  max      0.28
      viewport sync                  p50      4.41  p95      7.07  max      7.20
    redo frame                       p50     90.34  p95    131.91  max    135.83
    op + undo                        p50    231.26  p95    326.65  max    340.39
  delete 1 vertex          n= 20
    delete frame (op as triggered)   p50    161.25  p95    292.11  max    328.28
      op (Core delete)               p50     11.49  p95     18.10  max     18.89
      history                        p50      6.54  p95     10.27  max     12.08
      hover re-pick                  p50    120.97  p95    256.33  max    283.46
        of which sync before pick    p50      0.00  p95      0.00  max      0.00
      other (selection, status)      p50      0.13  p95      0.16  max      0.17
      viewport sync                  p50      4.32  p95      6.59  max      6.90
      draw                           p50     12.82  p95     16.78  max     17.60
    next hover frame                 p50     21.49  p95     26.94  max     30.86
    undo frame                       p50    149.49  p95    265.35  max    324.87
      history                        p50     20.60  p95     26.04  max     27.20
      hover re-pick (incl. sync)     p50    112.15  p95    233.15  max    287.70
      other                          p50      0.16  p95      0.23  max      0.24
      viewport sync                  p50      3.57  p95      5.42  max      5.52
    redo frame                       p50    138.44  p95    240.15  max    272.95
    op + undo                        p50    343.46  p95    463.39  max    479.84
Counters (whole run incl. warm-up):
  stage 1: topology syncs 0 (full buffer rebuilds 1, V2 patch syncs 0); faces re-triangulated 21875, reused 0; H0: changed by counts 0, full-compare fallbacks 0, lazy after-exports at Undo 0
  V1:      V1 patch syncs 252, fallbacks to a full sync 0; faces killed 1050, revived 1050
  GPU:     GPU picks 0 (ID renders 0, 0.0 ms; reads 0.0 ms; syncs before a pick 0); CPU picker used 0x
SUMMARY stage1+H1,V1 | delete 1 face: frame 103, undo 89, redo 92 | delete 20 faces: frame 102, undo 103, redo 90 | delete 1 vertex: frame 161, undo 149, redo 138
===== all =====
configuration: stage1+H1,V1,GPU  (stage-2 switches: GPU,H1,V1)
Platform: Linux-6.18.44-fc-v139-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.80GHz (4 logical cores)
Python: 3.13.16 (CPython)
GL_VERSION: (4, 5)
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
GC on, threshold (2000, 10, 10)
[gollum_20k] 21875 V / 21875 F / 43750 triangles; load + first frame 1026 ms
  delete 1 face            n= 20
    delete frame (op as triggered)   p50     41.26  p95     53.63  max     55.46
      op (Core delete)               p50      8.55  p95     11.35  max     11.47
      history                        p50      3.04  p95      4.42  max      4.97
      hover re-pick                  p50     17.15  p95     21.45  max     21.75
        of which sync before pick    p50      3.38  p95      4.96  max      5.01
      other (selection, status)      p50      0.14  p95      0.28  max      0.57
      viewport sync                  p50      2.72  p95      4.24  max      4.65
      draw                           p50      8.08  p95     12.53  max     14.65
    next hover frame                 p50      7.94  p95     11.39  max     14.17
    undo frame                       p50     32.27  p95     49.17  max     55.40
      history                        p50      5.44  p95      8.58  max     19.46
      hover re-pick (incl. sync)     p50     16.04  p95     23.60  max     26.14
      other                          p50      0.19  p95      0.22  max      0.25
      viewport sync                  p50      2.45  p95      3.76  max      5.93
    redo frame                       p50     26.72  p95     38.02  max     46.29
    op + undo                        p50     74.85  p95    100.88  max    110.86
  delete 20 faces          n= 20
    delete frame (op as triggered)   p50     41.02  p95     53.52  max     58.76
      op (Core delete)               p50      8.58  p95     12.18  max     18.88
      history                        p50      3.23  p95      4.11  max      4.39
      hover re-pick                  p50     17.81  p95     22.56  max     24.58
        of which sync before pick    p50      4.67  p95      5.55  max      7.61
      other (selection, status)      p50      0.12  p95      0.15  max      0.16
      viewport sync                  p50      3.52  p95      5.05  max      6.06
      draw                           p50      7.34  p95     10.20  max     11.39
    next hover frame                 p50      7.59  p95     11.38  max     12.91
    undo frame                       p50     46.37  p95     68.28  max    134.33
      history                        p50     17.82  p95     27.36  max    106.16
      hover re-pick (incl. sync)     p50     17.30  p95     23.96  max     25.90
      other                          p50      0.22  p95      0.31  max      1.16
      viewport sync                  p50      2.82  p95      4.39  max      4.60
    redo frame                       p50     30.31  p95     41.43  max     43.16
    op + undo                        p50     90.20  p95    127.04  max    170.62
  delete 1 vertex          n= 20
    delete frame (op as triggered)   p50     51.27  p95     78.29  max     85.08
      op (Core delete)               p50     12.52  p95     24.52  max     28.11
      history                        p50      6.67  p95     13.56  max     14.60
      hover re-pick                  p50     20.23  p95     30.48  max     30.86
        of which sync before pick    p50      4.56  p95      8.94  max      8.94
      other (selection, status)      p50      0.13  p95      0.16  max      0.20
      viewport sync                  p50      3.58  p95      7.35  max      7.84
      draw                           p50      8.31  p95     13.10  max     14.06
    next hover frame                 p50     11.80  p95     22.04  max     25.11
    undo frame                       p50     52.73  p95     84.51  max    181.75
      history                        p50     19.53  p95     37.51  max    142.63
      hover re-pick (incl. sync)     p50     19.82  p95     30.52  max     31.57
      other                          p50      0.19  p95      0.27  max      0.34
      viewport sync                  p50      2.57  p95      5.23  max      7.93
    redo frame                       p50     32.94  p95     54.46  max     54.50
    op + undo                        p50    114.41  p95    154.90  max    230.58
Counters (whole run incl. warm-up):
  stage 1: topology syncs 0 (full buffer rebuilds 1, V2 patch syncs 0); faces re-triangulated 21875, reused 0; H0: changed by counts 0, full-compare fallbacks 0, lazy after-exports at Undo 0
  V1:      V1 patch syncs 252, fallbacks to a full sync 0; faces killed 1050, revived 1050
  GPU:     GPU picks 378 (ID renders 254, 2278.9 ms; reads 1648.0 ms; syncs before a pick 252); CPU picker used 0x
SUMMARY stage1+H1,V1,GPU | delete 1 face: frame 41, undo 32, redo 27 | delete 20 faces: frame 41, undo 46, redo 30 | delete 1 vertex: frame 51, undo 53, redo 33
===== AD-022 B2 check =====
Platform: Linux-6.18.44-fc-v139-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.80GHz (4 logical cores)
Python: 3.13.16 (CPython)
GL_VERSION: (4, 5)
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
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
  face   wall p50  10.67 ms, max  12.99 ms; GPU time p50 10.64 ms
  vertex wall p50  12.61 ms, max  24.78 ms; GPU time p50 12.61 ms
B2 RESULT gl_PrimitiveID face mapping EXACT (differing face pixels 0, point pixels 0); position location store/face/point (0, 0, 0); real pick differences vs CPU 11

===== summary (ms, p50) =====
none | delete 1 face: frame 970, undo 1165, redo 1223 | delete 20 faces: frame 927, undo 1156, redo 1218 | delete 1 vertex: frame 1177, undo 1536, redo 1517
stage1 | delete 1 face: frame 333, undo 1167, redo 925 | delete 20 faces: frame 314, undo 1202, redo 918 | delete 1 vertex: frame 496, undo 1450, redo 1167
stage1+H1,V1 | delete 1 face: frame 103, undo 89, redo 92 | delete 20 faces: frame 102, undo 103, redo 90 | delete 1 vertex: frame 161, undo 149, redo 138
stage1+H1,V1,GPU | delete 1 face: frame 41, undo 32, redo 27 | delete 20 faces: frame 41, undo 46, redo 30 | delete 1 vertex: frame 51, undo 53, redo 33
B2 RESULT gl_PrimitiveID face mapping EXACT (differing face pixels 0, point pixels 0); position location store/face/point (0, 0, 0); real pick differences vs CPU 11
```

## Extra run: `--config GPU` (stage 1 + GPU picking, no H1 / V1), `--steps 10 --row-seconds 60`, delete 1 face (excerpt)

```text
  delete 1 face            n= 10
    delete frame (op as triggered)   p50    272.57  p95    514.41  max    514.41
      hover re-pick                  p50    140.89  p95    241.49  max    241.49
        of which sync before pick    p50    124.21  p95    201.77  max    201.77
      viewport sync                  p50      2.82  p95      4.43  max      4.43
    undo frame                       p50   1082.45  p95   1143.18  max   1143.18
      hover re-pick (incl. sync)     p50    196.61  p95    231.79  max    231.79
      viewport sync                  p50      2.88  p95      4.04  max      4.04
```
