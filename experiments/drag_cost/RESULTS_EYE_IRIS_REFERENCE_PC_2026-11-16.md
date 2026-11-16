# Eye LookDev phase 4 (the iris) — reference PC runs (2026-11-16): run 1 over the I-12 budget, run 2 within it

Machine: the reference PC (Core 2 Quad Q9550, GeForce 9800 GTX+, GL 3.3.0, Windows 10 19045, Python 3.12.10 in
`.venv312`) — **MEASURED [RPC]**. Run by Manu on 2026-11-16 with `experiments/drag_cost/probe_eye_preview.py` at
1024×768 and 1920×1080 (40 rounds after 5). Source line of both runs: commit `d400b8494b`, "working tree MODIFIED",
`src/` tree `f5466f8ea0`.

Scene and method as in the [phase 3 run](RESULTS_EYE_LOOK_REFERENCE_PC_2026-11-16.md). New rows: `iris full` /
`iris full key` = the phase 3 starting look plus the starting iris (`eye_presets.IRIS_START`: key through the cornea 1,
crescent 1, rim shadow 0.8, relief 0.5 from the derived height of the procedural iris, pupil edge 0.12 mm, margin 0.4).
`vs look` = the iris's own cost on top of `look full`.

## The iris's own GPU cost (ms, p50, `vs look`) — the build of `d400b84` (the key's path traced per pixel)

| View | 1024×768 iris full | iris full key | 1920×1080 iris full | iris full key |
|---|---|---|---|---|
| head (modelling distance) | +4.29 | +3.28 | +6.41 | +4.92 |
| close | +9.10 | +7.03 | +13.08 | +9.93 |
| **lab** | **+8.34** | +6.61 | **+13.37** | +10.62 |

All new eye effects together in the Eye Lab view (`iris full`, `vs L3`): **+9.26 ms (1024×768), +15.65 ms
(1920×1080)**; the whole frame 11.91 / 19.41 ms GPU, 15.73 / 23.35 ms wall. The phase 3 rows reproduce the phase 3 run
within 0.05 ms.

## Reading (COMPUTED)

- **Over the I-12 limit:** the new effects should add about 4 ms, at most 8 ms. Phase 3 + 4 add 9.3 / 15.7 ms in the
  Eye Lab view. The view itself stays above 30 FPS on the GPU (19.4 ms at 1920×1080), but the 8 ms limit is broken.
- **The cost hardly scales with the iris's area:** at modelling distance (the eyes 1.7 % of the frame) the iris still
  cost +6.4 ms at 1920×1080, half of the close-up's. The per-pixel trace of the key's path (three paths of 6 / 3 secant
  steps with trigonometry, for the crescent's finite difference) ran for every iris pixel, and - through the selects
  of the L3 paths behind the limbus and the sclera band - plausibly for many other eye pixels too.
- **Consequence (built the same day, AD-033 §18 "Cost"):** the path depends only on the iris point and the key's
  direction in the eye's frame, which is one value per eye and frame. The pass now traces it once per eye into a 64²
  RGBA16F table (4096 evaluations instead of ~180 000 pixels) and only when the key in the eye's frame, the anatomy or
  a key value changes; the shader reads one texel per pixel. The relief reuses the main sample's alpha (two extra
  samples instead of three). In the container's software renderer (wall time, relative only) the iris on top of the
  look fell from about +10 ms to about +3 ms in a 600-pixel close-up. **To be measured again on the reference PC.**

## Run 2 (Manu, 2026-11-16): the key table — within the I-12 target

Source line of both runs: commit `ba13deb1b1`, "working tree MODIFIED", `src/` tree `c2cd117ff5` (`fa4e889` + a
string-only change). A run in between still showed `d400b84` and reproduced run 1 within 0.05 ms (not recorded).

| View | 1024×768 iris full `vs look` | `vs L3` (phase 3 + 4) | 1920×1080 iris full `vs look` | `vs L3` |
|---|---|---|---|---|
| head | +0.14 | +0.90 | +0.19 | +1.45 |
| close | +0.29 | +2.17 | +0.45 | +3.80 |
| **lab** | +2.79 | **+3.70** | +0.49 | **+2.77** |

`iris full key`: lab +2.96 / +1.71 ms `vs L3`. Whole frame with the iris in the Eye Lab view: 6.35 / 6.54 ms GPU,
10.14 / 10.29 ms wall (1024×768 / 1920×1080). The phase 3 rows reproduce run 1 within 0.02 ms.

Reading (COMPUTED): the iris on top of the look fell from +8.3 / +13.4 to +2.8 / +0.5 ms in the Eye Lab view;
phase 3 + 4 together are at most **+3.80 ms** in any measured view and size - **within the I-12 target of about 4 ms**,
well under the 8 ms limit, the whole frame far above 60 FPS on the GPU. One reading is not explained: in the lab view
at 1024×768 the iris costs +2.79 ms, at 1920×1080 (twice the pixels) only +0.49; the other views scale as expected. A
table bake in some frames of the smaller run is the likeliest cause (the probe re-sends the eye entries per run); it
does not change the budget verdict.

