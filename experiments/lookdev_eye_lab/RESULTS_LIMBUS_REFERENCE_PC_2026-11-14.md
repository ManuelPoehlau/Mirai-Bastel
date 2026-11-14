# P1c soft limbus — reference PC run (2026-11-14)

Machine: the reference PC (Q9550, GeForce 9800 GTX+, GL 3.3, Windows 10) — **MEASURED [RPC]**. Run by Manu on
2026-11-14 (`run_limbus.py --probe`, defaults: 30 frames after 5, 1024×768 and 1920×1080, front / 3/4 / profile).
Tests on the same machine: **186 passed** (334 s). Probe: **four PASS** (P parity, I L0 = P1b, V no GL error,
R hygiene). **No Artist verdict here**: L0–L3, the colour source and the asymmetry stay Manu's to judge.

## What was measured

- **Image:** Manu's own `out/iris_custom.png` (512² RGBA, sha1 `beff016e0ff3`), **without** `out/iris_custom.json`
  (the header names no radial fit), i.e. the planar mapping, not the chosen "A+H" (`{"pupil": 0.22, "limbus": 0.88,
  "hold_outer_color": true}`). The A+H look check with the real texture is still open.
- **Source:** the probe header says commit `6c012fc0ca` (not on the remote: a local commit on the reference PC; the
  probe's output format is the one of `0a8737f`) and "working tree MODIFIED" (not identified).
- **Lighting / camera:** identical for every run (key az 35 el 25 E 3, environment on, exposure 0 EV, Reinhard);
  close-up distance per frame size.

## GPU time per level (GPU p50, ms; T-C unless named; MEASURED [RPC])

| View, size | L0 (= P1b V2) | L1 | L2 | L3 | L3 asym | V3 L0 → L3 | T-B L0 → L3 | T-D L0 → L3 |
|---|---|---|---|---|---|---|---|---|
| front 1024×768 | 1.17 | 1.28 | 1.35 | 1.89 | 1.90 | 1.60 → 1.89 | 1.02 → 1.72 | 1.92 → 2.87 |
| 3/4 1024×768 | 1.01 | 1.11 | 1.17 | 1.66 | 1.66 | 1.33 → 1.62 | 0.88 → 1.51 | 1.77 → 2.57 |
| profile 1024×768 | 0.78 | 0.87 | 0.92 | 1.25 | 1.25 | 0.82 → 1.24 | 0.67 → 1.14 | 1.46 → 1.99 |
| front 1920×1080 | 2.78 | 3.04 | 3.18 | 4.17 | 4.19 | 3.40 → 4.40 | 2.46 → 3.83 | 4.40 → 6.13 |
| 3/4 1920×1080 | 2.39 | 2.63 | 2.77 | 3.70 | 3.71 | 2.85 → 3.78 | 2.10 → 3.39 | 4.10 → 5.64 |
| profile 1920×1080 | 1.90 | 2.11 | 2.23 | 2.98 | 2.98 | 1.95 → 2.96 | 1.65 → 2.73 | 3.48 → 4.67 |

Reading (COMPUTED from the table, no verdict):
- **L1** adds ~0.1 ms (1024×768) / ~0.25 ms (1920×1080), **L2** a further ~0.06 / ~0.14 ms, the **asymmetry** nothing
  measurable (≤ 0.02 ms).
- **L3** is the expensive step: +0.5 / +1.0 ms over L2 with T-C (front), +0.7 / +1.4 ms over L0 with T-B, +0.95 /
  +1.7 ms with T-D. At 1920×1080 T-C V2 L3 costs 4.17 ms vs 2.78 ms for P1b V2 (+50 %).
- **Where L3's cost comes from:** it stays at +0.33 / +0.75 ms in the **profile** view, where hardly any cornea is
  seen — so most of it is the P1c sclera pass, which traces the refracted ray for *every* sclera fragment (the band
  is only ~1 mm wide; outside it the result is multiplied by 0). Tracing only inside the band is an obvious, untested
  optimisation (see "Open").
- V3: L3 costs the same as V2 L3 (1.89 / 4.40 ms vs 1.89 / 4.17 ms, front); V3's L0 is already dearer (1.60 vs 1.17 ms), so its L0 → L3 step looks smaller (+0.29 / +1.0 ms).

## Continuity across the ring ([C], 1024×768, T-C V2, Manu's texture; numbers, no verdict)

| View | L0 | L1 | L2 | L3 | L3 asym | L3 image colour |
|---|---|---|---|---|---|---|
| front | 51.7 / 87.3 @ −0.17 | 44.9 / 101.6 @ −0.17 | 28.0 / 99.3 @ −0.17 | 17.5 / 27.2 @ −0.17 | 16.0 / 23.9 @ −0.72 | 17.8 / 26.9 @ −0.25 |
| 3/4 | 76.2 / 113.2 @ −0.02 | 43.1 / 78.3 @ −0.77 | 42.3 / 71.6 @ −0.77 | 40.5 / 71.6 @ −0.90 | 39.2 / 71.6 @ −1.05 | 43.2 / 71.6 @ −0.82 |
| steep 75 | 71.1 / 110.3 @ −0.02 | 43.4 / 59.0 @ −0.17 | 43.4 / 58.8 @ −0.22 | 45.1 / 58.8 @ −0.22 | 35.9 / 55.7 @ −0.57 | 45.1 / 63.2 @ −0.22 |

(median / p95 of the largest luminance step per radial line, 0..255; @ = where that step sits, mm from the ring,
− = cornea side; chamber angle at −0.29 mm. Profile: no line fully visible.)

- **3/4 and steep:** L0's sharpest step sits **on the ring** (@ −0.02 mm, the seam / bright rim, p95 110–113). From L1
  on it is gone from there: the sharpest step moves 0.2–1 mm into the iris (the texture's own detail, ~40–45).
- **Front:** the sharpest step is the edge where the visible iris meets the limbal tissue (@ −0.17 mm). With this light
  iris and the default dark limbal colour ("P1b dark"), L1 / L2 make that edge's p95 *higher* than L0 (101.6 / 99.3
  vs 87.3); L3 (transmission 1 at the chamber angle) brings it to 27. The container's stand-in did not show the L1
  rise (its outer iris is darker).
- **Key sweep (3/4, p95 per azimuth −60 … +60):** L0 102–117, L1 70–79, L2 62–84, L3 62–75.

## Run 2 — the same texture with A+H (MEASURED [RPC], 2026-11-14)

Manu created `out\iris_custom.json` = `{"pupil": 0.22, "limbus": 0.88, "hold_outer_color": true}` and ran the probe
again. Header: `iris texture: CUSTOM iris_custom.png - 512x512, 8-bit RGBA, sha1 beff016e0ff3; radial fit
iris_custom.json: image pupil 0.220 -> 0.268, image iris edge 0.880 -> 0.819 (limbus), outer colour held`. Same source
line (`6c012fc0ca`, working tree MODIFIED). Four PASS again: parity, **L0 = P1b pixel for pixel with the same fit**,
no GL error, hygiene. Contact sheet (`out\limbus\limbus_sheet.png`): no white rim at the iris edge in any view.

GPU p50 (ms), T-C unless named, run 2 (run 1 without the sidecar in brackets):

| View, size | L0 | L1 | L2 | L3 | L3 asym | V3 L0 → L3 | T-B L0 → L3 | T-D L0 → L3 |
|---|---|---|---|---|---|---|---|---|
| front 1024×768 | 1.21 (1.17) | 1.32 | 1.39 | **2.10 (1.89)** | 2.10 | 1.68 → 2.05 | 1.06 → 1.86 | 1.96 → 3.04 |
| 3/4 1024×768 | 1.03 (1.01) | 1.13 | 1.19 | 1.82 (1.66) | 1.82 | 1.38 → 1.75 | 0.90 → 1.62 | 1.79 → 2.70 |
| profile 1024×768 | 0.78 (0.78) | 0.87 | 0.93 | 1.34 (1.25) | 1.34 | 0.83 → 1.33 | 0.68 → 1.21 | 1.47 → 2.06 |
| front 1920×1080 | 2.88 (2.78) | 3.14 | 3.28 | **4.56 (4.17)** | 4.58 | 3.53 → 4.76 | 2.56 → 4.13 | 4.49 → 6.47 |
| 3/4 1920×1080 | 2.45 (2.39) | 2.69 | 2.83 | 4.03 (3.70) | 4.04 | 2.94 → 4.08 | 2.15 → 3.64 | 4.15 → 5.92 |
| profile 1920×1080 | 1.90 (1.90) | 2.11 | 2.24 | 3.19 (2.98) | 3.19 | 1.96 → 3.17 | 1.65 → 2.90 | 3.49 → 4.83 |

- The fit's remap costs little where it is evaluated once per fragment (L0 +0.04 / +0.10 ms, front) and more in L3,
  which samples the iris image up to three times per fragment through it (+0.2 / +0.4 ms over run 1). **T-C V2 L3 at
  1920×1080: 4.56 ms vs 2.88 ms for L0 (+58 %).** The asymmetry still costs nothing measurable.

[C] (1024×768, T-C V2; median / p95 @ position, mm):

| View | L0 | L1 | L2 | L3 | L3 asym | L3 image colour |
|---|---|---|---|---|---|---|
| front | 53.5 / 85.3 @ −0.17 | 45.2 / 104.7 @ −0.17 | 26.0 / 101.6 @ −0.17 | 17.3 / 29.1 @ −0.30 | 16.2 / 27.2 @ −1.00 | 18.9 / 27.9 @ −0.30 |
| 3/4 | 76.5 / 118.1 @ −0.02 | 40.5 / 72.0 @ −0.87 | 40.0 / 61.4 @ −0.80 | 36.0 / 61.4 @ −0.87 | 33.2 / 60.3 @ −1.07 | 38.9 / 61.4 @ −0.72 |
| steep 75 | 66.0 / 110.4 @ −0.02 | 42.1 / 60.3 @ −0.27 | 42.1 / 59.4 @ −0.27 | 42.1 / 59.4 @ −0.27 | 37.3 / 48.6 @ −0.37 | 42.1 / 59.4 @ −0.17 |

Key sweep (3/4, p95, azimuth −60 … +60): L0 101–120, L1 65–87, L2 56–81, L3 56–65. The pattern of run 1 holds:
L0's sharpest step is on the ring; from L1 on it is not; in the front view L1 / L2 sharpen the iris-to-tissue edge
with the dark default colour (p95 ~102–105 vs 85), L3 softens it (29).

## Finding after run 2: a seam with the asymmetry on (fixed 2026-11-14)

Manu: "es gibt noch ein Problem bei Asymmetry on. Sieht man vor allem gut bei L1 und L2, bei L3 wirds teilweise
kaschiert, aber dennoch sichtbar, dort ist links und rechts, mittig auf dem Limbusrand ein Seam zu sehen".

Cause (verified in the container, TESTED [C]): `iris_cover` covered every cornea ray between the chamber angle and
the visible iris edge as soon as the shift was > 0 — and the shift `A sin²(azimuth)` is 0 only on the exact horizontal.
So the asymmetry changed that band all round except on a one-pixel line left and right: |on − off| along an arc at
−0.22 mm was 0 at 0° and ~50 at ±0.25° (L1 / L2; ~6 in L3, where the tissue is translucent there). Fix: the cover is
faded in with the shift (`smooth(shift / (0.25 A))`, full from ~30° off the horizontal; top / bottom unchanged), in
both twins. After the fix: |on − off| ≤ 2 within 3° of the horizontal, no jump along the arc; new tests (headless
continuity, GL ×3 levels) fail on the old shader and pass on the new one. **The asymmetry's look left / right changes
with this fix** (its effect now fades out toward the horizontal instead of covering the band there); the reference-PC
runs above were made before it.

## Follow-up: overlap all round (2026-11-14, built; not yet run on the reference PC)

Manu after the seam fix: "Dadurch das es in die Cornea hineinragt, bekommt man diesen schönen weichen Übergang,
allerdings wirkt es etwas komisch, dass der Effekt nur oben und unten richtig wirkt und an den Seiten nicht so, und
dort der Übergang dann hart bleibt, was an den Seiten etwas unnatürlich/künstlich wirkt". Built as an independent
setting **overlap all round** (0 / 0.15 / 0.3 / 0.5 mm, default 0, key `-`; first `/`, which a German layout cannot reach); the asymmetry adds on top of it.
Container (TESTED [C], stand-in image + A+H): four PASS; [C] front, L2 → L2 + overlap 0.3 mm: 43.4 / 66.9 → 13.9 / 22.7
(the iris-to-tissue edge softened all round), with the asymmetry 9.6 / 16.3; no jump along the ring (GL tests).

## Open

- **Artist verdicts** (Manu): L0–L3, colour source shader / image (and which preset), asymmetry on / off and the
  overlap all round (both to be looked at with the seam fix and the new overlap).
- **A+H with the real texture:** measured in run 2 (no white rim); Manu's look verdict on it is open.
- **L3 cost** (technical, an agent's job if wanted): trace the sclera's refracted ray only inside the band (texture
  sampled outside the branch as now); expected to remove most of the profile-view +0.33 / +0.75 ms (run 2: +0.56 / +1.29 ms); to be measured.

## Raw output (as pasted by Manu, 2026-11-14)

```
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py -m pytest experiments\lookdev_eye_lab\tests -q
186 passed in 334.21s (0:05:34)
(.venv312) PS C:\Users\Manuel\Mirai_Bastel> & $py experiments\lookdev_eye_lab\run_limbus.py --probe
Lookdev P1c soft limbus probe (2026-11-14): parity, L0 identity, continuity, timings, contact sheet
Platform: Windows-10-10.0.19045-SP0
CPU: Intel(R) Core(TM)2 Quad CPU    Q9550  @ 2.83GHz (4 logical cores)
Python: 3.12.10, numpy 2.2.6, pyglet 2.1.19
Source: commit 6c012fc0ca, src/ tree 94addddafd at HEAD / 94addddafd on disk, working tree MODIFIED
GL_VERSION: 3.3.0
GL_RENDERER: GeForce 9800 GTX/9800 GTX+/PCIe/SSE2
GL_VENDOR: NVIDIA Corporation
GL_SHADING_LANGUAGE_VERSION: 3.30 NVIDIA via Cg compiler
EVIDENCE: hardware renderer - label the results MEASURED [RPC] or MEASURED [MAIN] by machine.
GPU memory (KiB): dedicated 524288, total available 524288, current available 296424, eviction count 753, evicted 607464

iris texture: CUSTOM iris_custom.png - 512x512, 8-bit RGBA, sha1 beff016e0ff3
Lighting / camera for every run: key az 35 el 25 E 3, environment on yaw 0 x1, exposure +0 EV, tonemap 1; close-up distance per frame size
limbus L0 (P1b as is)   colour shader 'P1b dark'   asymmetry off (0.55 mm)
band 1.00 mm   strength 1.00   normal blend +-0.50 mm   translucency falloff 4.00

[P] limbus GLSL vs limbus_model (limbus_parity.py, float32 inputs; read-back COMPLETE)
  function          max abs err  failed  compared    tolerance
  coords               3.33e-06       0      1024        5e-06
  weights              2.29e-07       0      1024        2e-05
  normal_blend         1.46e-07       0      1024        5e-06
  sclera_through       7.72e-07       0      1024       0.0002
  tint                 7.45e-08       0      1024        5e-06
  -> PASS

[I] L0 against P1b (480x360, every technique T-B ... T-D, V2 and V3, every view)
  differing: none  -> PASS

[V] (GPU p50 / p95 / min / max / CPU p50 ms, GL errors none in every run) - condensed into the table above;
    1024x768 front T-C V2 L0 1.17 1.18 1.16 6.28 5.34 (one slow frame) ... T-D V2 L3 at 1920x1080 front 6.13 6.16 6.11 6.16 6.40

[R] resources and GL state
  still alive after release: none
  GL state after vs before: identical
  glGetError at the end: none
  -> PASS

Summary (raw verdicts - label them by machine in the results file):
  PASS  P limbus parity
  PASS  I L0 = P1b pixel for pixel
  PASS  V every run renders without GL error
  PASS  R hygiene
```

The [C] section and every [V] row are reproduced in the two tables above (values copied unchanged from the pasted
output; the full paste is in the session of 2026-11-14).
