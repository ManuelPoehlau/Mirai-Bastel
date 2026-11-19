# LookDev room probe — container (function check), 2026-11-19

`experiments/drag_cost/probe_lookdev_room.py --draws 10` on llvmpipe (Mesa 25.2.8), 1024×768, after LD-1 (AD-038).
**A function check only:** llvmpipe rasterises on the CPU, so its GL_TIME_ELAPSED values and the CPU columns are not
meaningful for LD-D10 — the reference PC decides (command in AD-038 §17.4). What this run shows:

- the room opens on `Gollum_Head_05` as saved, the programs compile behind the status line (2 programs: the skin
  variant with the paint composite and the eyes' LOOKDEV variant, about 20 ms on Mesa) one frame after the click,
  and no program is compiled in a LookDev frame afterwards;
- the UV request costs nothing on this scene: the head already shows its paint composite in the Worklight (textures
  on), so its triangle UVs are live (the first tick 0.1 ms); the LD-0 (b) numbers apply when textures are hidden;
- `modelling after` (the room closed again) is the Worklight frame of before: nothing stays behind;
- no GL error.

```
LookDev room probe (AD-038 LD-1, 2026-11-19), 1024x768, 10 rounds after 5
Platform: Linux-6.18.44-fc-v653-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.4
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit fafb59f7ce, working tree MODIFIED, src/ tree d9a7a65fa0
Scene: Gollum_Head_05.mirai.json, edit object 'Gollum_backup_noscale1 ZBrush', view framed (3/4)

[cage] the head draws 5469 triangles
  entry (first in this process): open_lookdev 0.4 ms; ticks until the first LookDev frame [0.1, 20.3] ms (the first holds the UV request); programs compiled 2 in 20 ms (behind the status line); first LookDev frame GPU 9.08 ms, wall 25.9 ms
  modelling        GPU p50    0.51 ms (min   0.28, max   4.43)    1.5 % of 33.3 ms   CPU p50    9.96 ms
  lookdev          GPU p50    0.03 ms (min   0.02, max   2.04)    0.1 % of 33.3 ms   CPU p50   13.78 ms   vs modelling  -0.48 ms
  modelling after  GPU p50    0.39 ms (min   0.33, max   4.06)    1.2 % of 33.3 ms   CPU p50   10.94 ms   vs modelling  -0.11 ms

[subd1] the head draws 22153 triangles
  entry: open_lookdev 0.5 ms; ticks until the first LookDev frame [0.1] ms (the first holds the UV request); programs compiled 0 in 0 ms (none needed); first LookDev frame GPU 12.99 ms, wall 39.1 ms
  modelling        GPU p50    0.61 ms (min   0.40, max   4.73)    1.8 % of 33.3 ms   CPU p50   19.47 ms
  lookdev          GPU p50    0.45 ms (min   0.02, max   1.49)    1.3 % of 33.3 ms   CPU p50   25.67 ms   vs modelling  -0.17 ms
  modelling after  GPU p50    0.50 ms (min   0.42, max   0.93)    1.5 % of 33.3 ms   CPU p50   17.35 ms   vs modelling  -0.11 ms

Entering once more (programs cached in this process):
  entry again: open_lookdev 0.3 ms; ticks until the first LookDev frame [0.1] ms (the first holds the UV request); programs compiled 0 in 0 ms (none needed); first LookDev frame GPU 5.95 ms, wall 26.5 ms

glGetError at the end: 0x0000
```
