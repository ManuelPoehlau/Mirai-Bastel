# Eye LookDev phase 4 (the iris) — reference PC run 1 (2026-11-16): over the I-12 budget

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
