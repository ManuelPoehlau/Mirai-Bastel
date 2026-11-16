# Eye LookDev phase 3 (the reflections) — reference PC run (2026-11-16)

Machine: the reference PC (Core 2 Quad Q9550, GeForce 9800 GTX+, GL 3.3.0, Windows 10 19045, Python 3.12.10 in
`.venv312`) — **MEASURED [RPC]**. Run by Manu on 2026-11-16 with `experiments/drag_cost/probe_eye_preview.py` at
1024×768 and 1920×1080 (40 rounds after 5). Source line of both runs: commit `ae2ffc2777`, "working tree MODIFIED",
`src/` tree `80b3e7661d` (the modification is not identified, as in the E-4 run).

Scene and method as in the [E-4 run](RESULTS_EYE_PREVIEW_REFERENCE_PC_2026-11-16.md): `head_basemesh` and two eyes from
`Application.add_eye`, each row the **whole frame** (`Viewport.render`), `GPU` = `GL_TIME_ELAPSED`, `CPU` = wall time
of `Viewport.render()` plus `glFinish` (it contains the wait for the GPU). New since phase 3: the view `lab` (the Eye
Lab's own frontal close-up, `Application.frame_eye(frontal=True)`; the eye about half the frame high, computed from the
probe's camera: 367 px of 768 / 516 px of 1080) and the rows `look fast` / `look full` / `look full key` (L3 with the
starting look `eye_presets.LOOK_START`: wet sclera 0.7, irregularity 0.5°, soft key highlight 0.6, lid shadow 0.3, lid
band 0.7). `vs L3` = the look's own cost.

## The look's own GPU cost (ms, p50, `vs L3`)

| View | Eye pass pixels (1024×768 / 1920×1080) | 1024×768 look full | look full key | 1920×1080 look full | look full key |
|---|---|---|---|---|---|
| head (modelling distance) | 2.3 % / 1.7 % | +0.75 | +0.41 | +1.25 | +0.69 |
| close (one eye, half the frame high) | 10.1 % / 7.5 % | +1.89 | +1.03 | +3.36 | +1.84 |
| **lab** (the Eye Lab's framing) | 11.7 % / 8.7 % | **+0.92** | +0.28 | **+2.28** | +1.17 |

Whole frame with the look (`look full`), GPU p50 / wall p50: head 2.08 / 6.84 and 3.39 / 8.38; close 4.61 / 9.57 and
8.15 / 12.18; lab 3.57 / 8.58 and 6.04 / 9.88 ms (1024×768 and 1920×1080).

`look fast` equals `L3` within 0.01 ms in all six view / size combinations.

## Reading (COMPUTED from the tables; the verdict on I-12 is Manu's)

- **I-12 budget** (Manu 2026-11-16: the new effects about 4 ms, 8 ms at most; 60 FPS target, 30 FPS minimum): the
  look's own cost is **+0.92 / +2.28 ms in the Eye Lab view** and at most **+3.36 ms** (close view, 1920×1080), so
  **every measured view is within the 4 ms target**. The whole render stays at or below 12.2 ms of wall time (about
  82 FPS for the render alone; the app's full frame - panels, input, sync - is not part of this probe).
- **Standing rule** ("fast" and the default path as cheap as before): met - `look fast` = `L3`.
- **Where the cost is:** "key only" saves about half of the look's cost (lab: +0.28 instead of +0.92, +1.17 instead
  of +2.28 ms): the analytic studio, now evaluated on the sclera as well, is the larger part.
- **Assessment §F estimate** for #1-#7 with the eye at about half the frame: 3.5-4.5 / 7-9 ms. Measured for #1, #2, #3,
  #6 in the comparable `lab` view: 0.9 / 2.3 ms - well below.
- **Non-GPU wall time** of the look (wall minus GPU, against L3): +0.3 to +1.0 ms for two eyes, with one row at -0.2;
  CPU and GPU overlap, so this is approximate.
- **The phase 0 CPU fix, now measured:** with the preview on, the wall time per frame fell by 7.0-7.8 ms against the E-4
  run (L0: head 12.93 → 5.16, close 14.02 → 6.65 at 1024×768; head 13.57 → 6.11, close 15.97 → 8.19 at 1920×1080). The
  estimate was "about 6-7 ms, to roughly preview off + 1 ms"; measured, preview on is now 1.6-3.4 ms *below* preview off
  in wall time. Both runs carry an unidentified "working tree MODIFIED".
- Single spikes (max 6.25 / 7.39 in `look full`, head; 4.05 / 4.59 in `L3 key`, head) stand alone, as in the E-4 run.

## Estimate beyond the measured views [E]

The look's cost grows with the pixels the eyes cover. Zoomed so that one eye fills the frame height (twice the `lab`
diameter, about four times its pixels), it would be roughly 3.7 ms at 1024×768 and 9 ms at 1920×1080 frontally, more
at a three-quarter angle (scaled from `close`: about 7.6 / 13 ms). At 1920×1080 that would exceed the 8 ms limit. Not
measured; the probe has no such view. Levers if it matters: the reflection "key only" (measured: about half), the
studio cube (roadmap #11).

## Open

- The real Gollum scene (`scenes/Gollum_Head_03.mirai.json`) instead of the probe's default eyes (open since E-4).
- A frame-filling macro view, only if the artist works that close.

## Raw output

```
Eye preview GPU probe (AD-033 E-4, 2026-11-15; phase 3 look rows 2026-11-16): the whole frame, GL_TIME_ELAPSED, ms
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit ae2ffc2777, working tree MODIFIED, src/ tree 80b3e7661d

[head_basemesh + 2 eyes] 1024x768, 40 rounds after 5
  view head: the eye pass changes 18136 px (2.3 % of the frame)
    run              GPU p50      min      max   vs off    vs L3    CPU p50
    preview off         2.81     2.77     2.87    +0.00    +1.48       6.72
    L0                  1.34     1.30     1.37    -1.47    +0.01       5.16
    L2                  1.44     1.42     1.48    -1.37    +0.11       5.83
    L3                  1.33     1.30     1.36    -1.48    +0.00       5.77
    L3 key              1.33     1.31     4.05    -1.49    -0.01       5.49
    L3 V3               1.41     1.38     1.45    -1.41    +0.07       5.47
    look fast           1.33     1.31     1.36    -1.48    -0.00       5.76
    look full           2.08     2.04     6.25    -0.73    +0.75       6.84
    look full key       1.74     1.72     1.80    -1.07    +0.41       6.54
  view close: the eye pass changes 79088 px (10.1 % of the frame)
    run              GPU p50      min      max   vs off    vs L3    CPU p50
    preview off         5.78     5.70     5.83    +0.00    +3.06       9.57
    L0                  2.74     2.71     2.79    -3.04    +0.02       6.65
    L2                  3.02     2.98     3.07    -2.76    +0.30       7.07
    L3                  2.72     2.70     2.75    -3.06    +0.00       6.92
    L3 key              2.78     2.76     2.83    -3.00    +0.06       7.09
    L3 V3               2.92     2.89     2.96    -2.86    +0.20       7.09
    look fast           2.72     2.70     3.16    -3.06    +0.00       7.01
    look full           4.61     4.57     4.64    -1.17    +1.89       9.57
    look full key       3.75     3.71     3.79    -2.03    +1.03       8.68
  view lab: the eye pass changes 91697 px (11.7 % of the frame)
    run              GPU p50      min      max   vs off    vs L3    CPU p50
    preview off         4.69     4.62     4.75    +0.00    +2.04       8.43
    L0                  2.33     2.30     2.37    -2.36    -0.32       6.38
    L2                  2.55     2.50     2.58    -2.14    -0.10       6.83
    L3                  2.65     2.56     2.72    -2.04    +0.00       6.95
    L3 key              2.29     2.26     2.32    -2.40    -0.36       6.60
    L3 V3               2.47     2.43     2.52    -2.22    -0.18       6.92
    look fast           2.64     2.54     2.71    -2.05    -0.01       6.94
    look full           3.57     3.52     3.61    -1.13    +0.92       8.58
    look full key       2.93     2.89     3.06    -1.76    +0.28       8.03
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> python experiments\drag_cost\probe_eye_preview.py --size 1920 1080
Eye preview GPU probe (AD-033 E-4, 2026-11-15; phase 3 look rows 2026-11-16): the whole frame, GL_TIME_ELAPSED, ms
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit ae2ffc2777, working tree MODIFIED, src/ tree 80b3e7661d

[head_basemesh + 2 eyes] 1920x1080, 40 rounds after 5
  view head: the eye pass changes 35871 px (1.7 % of the frame)
    run              GPU p50      min      max   vs off    vs L3    CPU p50
    preview off         4.44     4.36     4.53    +0.00    +2.29       7.93
    L0                  2.13     2.09     2.16    -2.31    -0.02       6.11
    L2                  2.32     2.28     2.37    -2.12    +0.17       6.51
    L3                  2.14     2.12     2.37    -2.29    +0.00       6.42
    L3 key              2.15     2.12     4.59    -2.28    +0.01       6.05
    L3 V3               2.27     2.23     2.30    -2.17    +0.12       6.37
    look fast           2.14     2.11     2.18    -2.29    +0.00       6.25
    look full           3.39     3.36     7.39    -1.05    +1.25       8.38
    look full key       2.83     2.80     2.89    -1.61    +0.69       7.64
  view close: the eye pass changes 156393 px (7.5 % of the frame)
    run              GPU p50      min      max   vs off    vs L3    CPU p50
    preview off         9.17     9.08     9.27    +0.00    +4.38      11.60
    L0                  4.71     4.67     4.76    -4.46    -0.08       8.19
    L2                  5.14     5.10     5.17    -4.03    +0.35       8.12
    L3                  4.79     4.76     4.83    -4.38    +0.00       8.99
    L3 key              4.85     4.80     4.89    -4.32    +0.06       8.50
    L3 V3               5.13     5.08     5.17    -4.04    +0.34       8.74
    look fast           4.79     4.76     4.82    -4.38    -0.00       8.29
    look full           8.15     8.09     8.21    -1.02    +3.36      12.18
    look full key       6.63     6.59     6.72    -2.54    +1.84      10.34
  view lab: the eye pass changes 181050 px (8.7 % of the frame)
    run              GPU p50      min      max   vs off    vs L3    CPU p50
    preview off         7.58     7.52     7.66    +0.00    +3.82       9.96
    L0                  3.92     3.87     3.95    -3.67    +0.16       6.68
    L2                  4.30     4.24     4.36    -3.29    +0.54       7.60
    L3                  3.76     3.74     3.78    -3.82    +0.00       6.62
    L3 key              3.89     3.80     3.93    -3.69    +0.13       7.06
    L3 V3               4.07     4.04     4.17    -3.52    +0.31       7.32
    look fast           3.76     3.73     3.78    -3.82    -0.00       6.60
    look full           6.04     6.00     6.08    -1.54    +2.28       9.88
    look full key       4.93     4.91     4.97    -2.65    +1.17       8.60
```
