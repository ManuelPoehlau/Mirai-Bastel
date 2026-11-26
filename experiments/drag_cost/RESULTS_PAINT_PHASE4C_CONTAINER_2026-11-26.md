# Paint Room Phase 4c — library probe results, container (2026-11-26)

**Probe:** `experiments/drag_cost/probe_paint_library.py` (AD-037 §14.7) on the 4c working tree (on top of `08e208d`),
rows **P-L** (a 1024² import: open + suggestion, the normalised preview, the grey PNG and its thumbnail written),
**P-M** (the picker's first open with 50 thumbnails: 44 imported 1024² noise alphas + the six built in, a new session's
library, thumbnails from their 64² files + GL textures) and **P-N** (the alpha cache while 60 imported 1024² alphas are
read for painting). Everything in a temporary user folder.
**Machine:** the cloud container (Xeon, Python 3.13.18, NumPy 2.2.6 pinned), GL = llvmpipe (software).

**Reading** (AD-037 §14.7):
- **P-L** ≤ 106 ms worst case (noise) against the 0.5 s gate. Before the grey PNG the noise import was 298 / 322 ms
  (p50 / max; the RGBA file at zlib level 6 alone 280 ms) — about the gate on the reference PC [H: ×2–3]; now 62 ms of
  writing. A 4096² image (clamped to 1024 px; information) 0.6–0.75 s, mostly its decode.
- **P-M** 88 ms total for 50 (thumbnails 23 ms from their small files, GL textures 65 ms on llvmpipe) against 150 ms.
  Before the thumbnail files a 1024² noise alpha's thumbnail cost ~57 ms (its PNG decode): 50 took 2.5 s. In the room
  the textures are also spread over frames (12 ms budget per frame); afterwards a frame only looks them up (0.15 ms).
- **P-N** the cache holds 64.0 MiB at most (48 of 60 alphas; the oldest dropped) — gate met by construction.

## Output (verbatim)

```
Paint library probe (AD-037 Phase 4c) - commit 08e208d0a2, working tree MODIFIED, src/ tree 66a81cd56c
python 3.13.18, numpy 2.2.6

P-L 1024^2 import (open + suggestion, preview, write PNG + thumbnail), ms       gate <= 500 ms
  smooth, RGB              p50   58.9  max   91.9  (open 15, preview 23, write 54; suggested Luminanz)  PASS
  noise, RGB               p50   94.1  max  105.6  (open 16, preview 13, write 62; suggested Luminanz)  PASS
  shape on transparency    p50   84.1  max  107.1  (open 24, preview 3, write 80; suggested Alphakanal)  PASS
  4096^2 (information, clamped to 1024 px): 741 ms

P-M picker first open, 50 thumbnails (44 imported 1024^2 + 6 built in), ms      gate <= 150 ms
  50 items: scan 0.7, thumbnails 22.6, GL textures 64.9, total 88.2  PASS
  afterwards (all 50 cached, the frame's lookups only) 0.15 ms; alpha cache 0.0 MiB (thumbnails do not fill it)

P-N alpha cache: 60 imported 1024^2 alphas read for painting, one after the other      gate <= 64 MiB
  peak 64.0 MiB, now 64.0 MiB (48 alphas held); first read of a 1024^2 alpha p50 42 ms  PASS
```

## Second run, after the starter set was adopted (22 built-in alphas with their thumbnail files)

```
Paint library probe (AD-037 Phase 4c) - commit d89a6255f9, working tree MODIFIED, src/ tree e60c41c415
python 3.13.18, numpy 2.2.6

P-L 1024^2 import (open + suggestion, preview, write PNG + thumbnail), ms       gate <= 500 ms
  smooth, RGB              p50   72.1  max   96.0  (open 11, preview 15, write 45; suggested Luminanz)  PASS
  noise, RGB               p50   96.0  max  107.2  (open 18, preview 16, write 73; suggested Luminanz)  PASS
  shape on transparency    p50   82.3  max   94.8  (open 27, preview 3, write 65; suggested Alphakanal)  PASS
  4096^2 (information, clamped to 1024 px): 641 ms

P-M picker first open, 50 thumbnails (22 imported 1024^2 + 28 built in), ms      gate <= 150 ms
  50 items: scan 1.3, thumbnails 19.7, GL textures 55.4, total 76.4  PASS
  afterwards (all 50 cached, the frame's lookups only) 0.11 ms; alpha cache 0.0 MiB (thumbnails do not fill it)

P-N alpha cache: 60 imported 1024^2 alphas read for painting, one after the other      gate <= 64 MiB
  peak 64.0 MiB, now 64.0 MiB (48 alphas held); first read of a 1024^2 alpha p50 42 ms  PASS
```
