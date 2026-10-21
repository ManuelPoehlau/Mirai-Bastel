# GPU vs CPU picking through Application, container, 2026-10-21 (AD-022 §11)

Container (Xeon, Python 3.13, **llvmpipe** = software GL; not the reference PC). Command:
`xvfb-run -a python experiments/drag_cost/probe_picking_app.py` (gollum_20k, 1024x768, n = 15, Box n = 5). ms. Every timing includes `glFinish`.

```
gollum_20k.obj: 21875 V / 21875 F, 1024x768, GL (4, 5) llvmpipe (LLVM 20.1.2, 256 bits)
[CPU]
  vertex first pick            n= 15  p50    77.04  max   164.95
  vertex hover                 n= 15  p50     2.71  max    16.60
  vertex box 300px             n=  5  p50  1019.83  max  1094.13
  edge first pick              n= 15  p50    68.42  max    94.27
  edge hover                   n= 15  p50    12.78  max    30.56
  edge box 300px               n=  5  p50  1996.77  max  2166.76
  face first pick              n= 15  p50    47.38  max    74.55
  face hover                   n= 15  p50     2.44  max     2.60
  face box 300px               n=  5  p50  1122.31  max  1336.56
  delete 1 face + re-pick      n= 15  p50     2.79  max     4.23
[GPU]
  vertex first pick            n= 15  p50    15.84  max    26.49
  vertex hover                 n= 15  p50     0.34  max     0.52
  vertex box 300px             n=  5  p50    85.33  max    96.26
  edge first pick              n= 15  p50    21.37  max   123.56
  edge hover                   n= 15  p50     0.51  max     0.84
  edge box 300px               n=  5  p50   113.04  max   190.85
  face first pick              n= 15  p50    11.10  max    14.58
  face hover                   n= 15  p50     0.02  max     0.05
  face box 300px               n=  5  p50   152.39  max   170.00
  delete 1 face + re-pick      n= 15  p50    14.44  max    18.64
```
