# Eye preview in the Worklight — reference PC run (AD-033 phase E-4, 2026-11-16)

Machine: the reference PC (Core 2 Quad Q9550, GeForce 9800 GTX+, GL 3.3.0, Windows 10 19045, Python 3.12.10 in
`.venv312`) — **MEASURED [RPC]**. Run by Manu on 2026-11-16 with `experiments/drag_cost/probe_eye_preview.py` at
1024×768 and 1920×1080 (40 rounds after 5). Source line of both runs: commit `dd3c44bda1`, "working tree MODIFIED",
`src/` tree `f86c8ac302` (the modification is not identified; whether NVIDIA "prefer maximum performance" was set is
not stated).

Scene: `head_basemesh` (the edit object) and two eyes from `Application.add_eye`. Two views: `head` (the framed head,
the modelling case) and `close` (the camera on one eye). Each row is the **whole frame** (`Viewport.render`: head, both
eyes, overlays). `GPU` = `GL_TIME_ELAPSED`; `CPU` = wall time of `Viewport.render()` plus `glFinish`, so it contains the
wait for the GPU.

## Results (ms, p50)

| View, size | Eye pass pixels | preview off | L0 | L2 | L3 | L3 key | L3 V3 |
|---|---|---|---|---|---|---|---|
| head 1024×768, GPU | 2.3 % | 2.83 | 1.33 | 1.43 | 1.33 | 1.33 | 1.40 |
| head 1024×768, CPU | | 5.90 | 12.93 | 13.60 | 13.66 | 13.15 | 13.20 |
| close 1024×768, GPU | 10.1 % | 5.78 | 2.74 | 3.01 | 2.72 | 2.78 | 2.92 |
| close 1024×768, CPU | | 8.19 | 14.02 | 14.92 | 14.71 | 14.64 | 14.90 |
| head 1920×1080, GPU | 1.7 % | 4.46 | 2.13 | 2.32 | 2.14 | 2.15 | 2.27 |
| head 1920×1080, CPU | | 7.32 | 13.57 | 14.27 | 14.12 | 14.02 | 14.26 |
| close 1920×1080, GPU | 7.5 % | 9.21 | 4.70 | 5.14 | 4.79 | 4.86 | 5.14 |
| close 1920×1080, CPU | | 11.84 | 15.97 | 16.93 | 16.35 | 16.66 | 16.96 |

GPU min / max stay within ±0.1 ms of the p50 in every row but one (L3, head 1920×1080: max 2.31).

## Reading (COMPUTED from the table; no verdict)

- **GPU: the frame is cheaper with the preview on than off**, by 1.4–1.5 ms (head) and 2.8–3.1 ms (close) at 1024×768,
  2.1–2.3 and 4.1–4.5 ms at 1920×1080. "Off" draws the two eye shells with the Worklight's own program; the eye pass
  costs less than that. The same relation was measured in the lab (the same eye in the Worklight 3.6–3.8 ms against
  1.0–1.3 ms, REFERENCE_HARDWARE §2, 2026-11-14). Why the Worklight is that expensive on a 3 392-face shell was not
  investigated.
- **Levels and tiers hardly matter at this coverage.** L0 and L3 are equal within 0.1 ms; L2 is 0.1–0.4 ms above
  them; "key only" saves nothing against the studio; V3 costs 0.07–0.35 ms more than V2. AD-033 §7's requirement "may
  not change the cost of a scene without eyes" is not tested by this probe (it has no run without eyes).
- **CPU: the preview adds 6–8 ms of wall time per frame at 1024×768** (head 5.90 → 12.9–13.7, close 8.19 → 14.0–14.9)
  and 4–7 ms at 1920×1080, although the GPU part of that wall time went *down*. The non-GPU part therefore grows by
  about 7–9 ms for two eyes: **roughly 3.5–4.5 ms of Python per eye and frame**. That is the dominant cost of the eye
  preview on this machine, not the shading.

## Where the CPU time went, and the fix (container, TESTED [C], 2026-11-16)

Profile of `EyePass.draw` in the container (Python 3.12, `numpy==2.2.6`, Mesa llvmpipe; the eye tiny on screen so the
software raster is small): 1.80 ms per eye. Of the Python part (about 1.05 ms), 0.9 ms was `eye_uniforms()`, almost
all of it `EyeGeometry.angle` — an 80-step bisection with NumPy scalars, evaluated twice per eye on every frame — and
0.05 ms was pyglet rebuilding `program.uniforms` once per uniform name.

Changed the same day (`viewport/eye_optics._chamber_angle`, cached per anatomy; `EyePass.draw` reads the active
uniforms once): **1.80 → 0.90 ms per eye in the container, the Python part 1.05 → about 0.15 ms**. The numbers the
shader receives are the same (`tests/test_eye_object.py`, the eye lab's `test_oracle_production.py`, all of
`tests/test_gl_eye_pass.py`).

**Expected on the reference PC (ESTIMATE, to be confirmed by a rerun of the two commands):** the CPU column with the
preview on drops by about 6–7 ms at 1024×768, to roughly the "preview off" value plus 1 ms.

## Open

- A rerun of both commands after the fix (the CPU column).
- A run without eyes in the same scene, to separate the eye pass's own GPU cost from the head's.
- The real Gollum scene (`scenes/Gollum_Head_03.mirai.json`: L3, image colour source, an iris image) instead of the
  probe's default eyes.

## Raw output

```
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> python experiments\drag_cost\probe_eye_preview.py
Eye preview GPU probe (AD-033 E-4, 2026-11-15): the whole frame, GL_TIME_ELAPSED, ms
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit dd3c44bda1, working tree MODIFIED, src/ tree f86c8ac302

[head_basemesh + 2 eyes] 1024x768, 40 rounds after 5
  view head: the eye pass changes 18136 px (2.3 % of the frame)
    run            GPU p50      min      max   vs off    CPU p50
    preview off       2.83     2.76     2.87    +0.00       5.90
    L0                1.33     1.31     1.36    -1.50      12.93
    L2                1.43     1.41     1.47    -1.39      13.60
    L3                1.33     1.31     1.35    -1.50      13.66
    L3 key            1.33     1.31     1.36    -1.50      13.15
    L3 V3             1.40     1.38     1.42    -1.43      13.20
  view close: the eye pass changes 79088 px (10.1 % of the frame)
    run            GPU p50      min      max   vs off    CPU p50
    preview off       5.78     5.69     5.87    +0.00       8.19
    L0                2.74     2.71     2.76    -3.04      14.02
    L2                3.01     2.97     3.07    -2.77      14.92
    L3                2.72     2.70     2.75    -3.06      14.71
    L3 key            2.78     2.75     2.83    -3.00      14.64
    L3 V3             2.92     2.89     2.96    -2.86      14.90
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> python experiments\drag_cost\probe_eye_preview.py --size 1920 1080
Eye preview GPU probe (AD-033 E-4, 2026-11-15): the whole frame, GL_TIME_ELAPSED, ms
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10 (CPython)
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
Source: commit dd3c44bda1, working tree MODIFIED, src/ tree f86c8ac302

[head_basemesh + 2 eyes] 1920x1080, 40 rounds after 5
  view head: the eye pass changes 35871 px (1.7 % of the frame)
    run            GPU p50      min      max   vs off    CPU p50
    preview off       4.46     4.40     4.50    +0.00       7.32
    L0                2.13     2.10     2.16    -2.33      13.57
    L2                2.32     2.29     2.34    -2.14      14.27
    L3                2.14     2.11     2.31    -2.32      14.12
    L3 key            2.15     2.11     2.19    -2.31      14.02
    L3 V3             2.27     2.24     2.29    -2.19      14.26
  view close: the eye pass changes 156393 px (7.5 % of the frame)
    run            GPU p50      min      max   vs off    CPU p50
    preview off       9.21     9.14     9.28    +0.00      11.84
    L0                4.70     4.67     4.74    -4.51      15.97
    L2                5.14     5.07     5.18    -4.07      16.93
    L3                4.79     4.77     4.83    -4.42      16.35
    L3 key            4.86     4.83     4.92    -4.35      16.66
    L3 V3             5.14     5.08     5.19    -4.07      16.96
```
