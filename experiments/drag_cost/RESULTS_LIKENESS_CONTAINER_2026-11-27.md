# Likeness camera probe — container function check (AD-042 M1, 2026-11-27)

`python experiments/drag_cost/probe_likeness.py --draws 5` under `xvfb-run -a`, Mesa **llvmpipe** (software
rasteriser). A **function check only** (AD-042 §10.4): every row runs, the camera view enters and leaves, the photo
loads, caps (6000 × 4000 → 3000 × 2000) and uploads once, `free after` equals `free`. The GPU numbers of a software
rasteriser are fill-rate bound and say nothing about the reference PC; the reference PC decides the targets
(each camera-view row ≤ its free row + 0.5 ms GPU, a 24 MP JPEG ≤ 3 s).

```
Likeness camera probe (AD-042 M1), 1024x768, 5 rounds after 5
Platform: Linux-6.18.44-fc-v880-x86_64-with-glibc2.39
CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 logical cores)
Python: 3.13.18 (CPython)
GL_VERSION: 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.5
GL_RENDERER: llvmpipe (LLVM 20.1.2, 256 bits)
Source: commit b4eb34619b, working tree MODIFIED, src/ tree 03e938344f
Scene: Gollum_Head_05.mirai.json, edit object 'Gollum_backup_noscale1 ZBrush', view framed (3/4)
  free                        GPU p50    0.42 ms (min   0.32, max   1.90)    1.3 % of 33.3 ms   CPU p50   10.08 ms
  (Kamera 1: 33.3 mm KB from the view, overscan 1.15)
  camera view                 GPU p50    4.17 ms (min   3.95, max   7.69)   12.5 % of 33.3 ms   CPU p50   10.30 ms   vs free  +3.75 ms OVER
  photo 4096 behind           GPU p50    5.24 ms (min   4.78, max   5.82)   15.7 % of 33.3 ms   CPU p50   16.01 ms   vs free  +4.82 ms OVER
  lookdev (gate, no photo)    GPU p50    6.04 ms (min   5.44, max   6.67)   18.1 % of 33.3 ms   CPU p50   28.30 ms
  lookdev photo 4096 behind   GPU p50    7.24 ms (min   6.07, max   7.44)   21.7 % of 33.3 ms   CPU p50   32.58 ms   vs lookdev  +1.20 ms
  free after                  GPU p50    0.34 ms (min   0.30, max   0.50)    1.0 % of 33.3 ms   CPU p50   10.09 ms   vs free  -0.08 ms ok
Photo load (wall ms: read + cap in the tick, then the frame that uploads it):
  4096 x 3072 PNG             read    120.8 ms   upload frame   237.6 ms
  6000 x 4000 PNG             read   1440.6 ms   upload frame    62.1 ms   (Foto ›photo_6000.png‹: 3000 × 2000 (aus 6000 × 4000), 1,4 s)
```

Reading (container):
- `camera view` +3.8 ms on llvmpipe is the blended passepartout's fill (four rectangles, ≈ 25 % of the window, the area
  outside the gate): isolated in the same run, the gate's draw state and program alone cost +0.0 ms, the four
  rectangles alone +4.9 ms. A hardware rasteriser fills that in well under 0.1 ms [E]; the reference PC measures it.
- `free after` = `free` (−0.08 ms, noise): the camera view leaves nothing behind (also tested byte for byte,
  `tests/test_gl_likeness_backdrop.py` G4).
- The 6000 × 4000 PNG's 1.4 s are the own PNG decoder plus the box cap on this CPU; a JPEG goes through pyglet
  (WIC on Windows) - `--photo <JPEG>` on the reference PC.

Reference-PC run: open (Manu, before M2; AD-042 §11.3).

## M2 rows (AD-042 §18.8, 2026-11-27)

The same command after M2 (working tree on `aa0506b` + M2, before its commit):

```
  free                        GPU p50    0.53 ms (min   0.32, max  14.06)    1.6 % of 33.3 ms   CPU p50   11.69 ms
  (Kamera 1: 33.3 mm KB from the view, overscan 1.15)
  camera view                 GPU p50    0.09 ms (min   0.08, max   3.15)    0.3 % of 33.3 ms   CPU p50   11.99 ms   vs free  -0.44 ms ok
  photo 4096 behind           GPU p50    0.09 ms (min   0.07, max   0.11)    0.3 % of 33.3 ms   CPU p50   18.45 ms   vs free  -0.44 ms ok
  photo 4096 front            GPU p50    0.09 ms (min   0.08, max   0.12)    0.3 % of 33.3 ms   CPU p50   15.72 ms   vs free  -0.44 ms ok
  photo 4096 wipe             GPU p50    0.07 ms (min   0.05, max   4.68)    0.2 % of 33.3 ms   CPU p50   15.88 ms   vs free  -0.45 ms ok
  photo 4096 front, turned    GPU p50    0.05 ms (min   0.03, max   2.10)    0.1 % of 33.3 ms   CPU p50   17.74 ms   vs free  -0.48 ms ok
  lookdev (gate, no photo)    GPU p50    6.49 ms (min   6.20, max   7.34)   19.5 % of 33.3 ms   CPU p50   28.97 ms
  lookdev photo 4096 behind   GPU p50    6.64 ms (min   6.42, max   6.95)   19.9 % of 33.3 ms   CPU p50   34.30 ms   vs lookdev  +0.15 ms
  free after                  GPU p50    0.40 ms (min   0.30, max   4.91)    1.2 % of 33.3 ms   CPU p50   12.68 ms   vs free  -0.13 ms ok
```

Reading: every row runs (front, wipe, a turned photo), `free after` ≈ `free`. On llvmpipe the GPU timer does not
separate the work this run (the camera-view rows read *below* `free`, where M1's run read +3.8 ms for the same draw):
the software rasteriser's timer queries are not a cost measure, and the CPU column carries its fill time (+4 … +6 ms
with a photo). Nothing here is a verdict; the reference PC decides (AD-042 §18.9).
