# GPU vs CPU picking through Application, reference PC, 2026-10-21 (AD-022 §11)

Manu's run (Core 2 Quad Q9550, GeForce 9800 GTX, GL 3.3, Windows 10, Python 3.14). Raw output as pasted.

`python -m pytest tests\test_gl_gpu_picking.py -q`: **18 passed** (incl. the edge pass: `gl_PrimitiveID` on
`GL_LINES` and `glDrawElementsBaseVertex` work on this driver), 4 DeprecationWarnings from pyglet under Python 3.14.

`python experiments\drag_cost\probe_picking_app.py`:

```
gollum_20k.obj: 21875 V / 21875 F, 1024x768, GL (3, 3) GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
[CPU]
  vertex first pick            n= 15  p50   156.68  max   224.66
  vertex hover                 n= 15  p50    10.11  max    50.30
  vertex box 300px             n=  5  p50  2313.21  max  2324.71
  edge first pick              n= 15  p50   187.02  max   191.47
  edge hover                   n= 15  p50    33.00  max    68.62
  edge box 300px               n=  5  p50  4639.90  max  4657.76
  face first pick              n= 15  p50   143.45  max   145.40
  face hover                   n= 15  p50     7.07  max     8.55
  face box 300px               n=  5  p50  2737.55  max  2909.02
  delete 1 face + re-pick      n= 15  p50     7.19  max     8.64
[GPU]
  vertex first pick            n= 15  p50     6.94  max    10.99
  vertex hover                 n= 15  p50     2.15  max     3.41
  vertex box 300px             n=  5  p50   203.25  max   246.04
  edge first pick              n= 15  p50     8.23  max    12.52
  edge hover                   n= 15  p50     2.72  max     4.17
  edge box 300px               n=  5  p50   306.51  max   389.32
  face first pick              n= 15  p50     3.79  max     7.62
  face hover                   n= 15  p50     0.50  max     0.81
  face box 300px               n=  5  p50   405.33  max   406.07
  delete 1 face + re-pick      n= 15  p50     4.93  max     8.47
```
