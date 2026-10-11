# Drag cost with the GL backend (WP-VIEW-PATCH-01)

Probe, Type A (defect fix, Production mode), 2026-10-10. Question: what does one mouse move of a
held-W drag cost in the window's real chain (`Application` → `Viewport` → `GLRenderStore`), not a
`TraceStore` proxy? Origin: AD-020 review F1 found that `GLRenderStore._patch_attribute` re-copied the
whole attribute buffer for every per-vertex update (O((moved + ring) × V) per move). The fix is in
`src/viewport/gl_render_store.py` (slice-only patch); this probe makes the cost measurable on the
reference PC.

- Review and evidence: [`docs/archive/soft_selection/reviews/AD-020_REVIEW_CLAUDE_001.md`](../../docs/archive/soft_selection/reviews/AD-020_REVIEW_CLAUDE_001.md) F1, P-V2 … P-V4
- Contract: [`docs/architecture/AD-018-PRODUCTION-DRAW-BINDING.md`](../../docs/architecture/AD-018-PRODUCTION-DRAW-BINDING.md) (addendum 2026-10-10),
  [`docs/viewport/VIEWPORT_V02_ARCHITECTURE.md`](../../docs/viewport/VIEWPORT_V02_ARCHITECTURE.md) §7
- Reference PC (real window times still "Offen"): [`docs/architecture/REFERENCE_HARDWARE.md`](../../docs/architecture/REFERENCE_HARDWARE.md) §2

> Imports nothing from `playground/` (AD-010 precedent) and nothing from other experiments, guarded by
> `tests/test_probe_args.py`. Reads `src/` (`core`, `mirai`, `viewport`, `main.GL_TYPES`) and
> `examples/loaders` only.

## Contents

| File | What it is |
|---|---|
| `probe_drag_gl.py` | CLI probe: hidden pyglet window, `GL_TYPES` from `src/main.py`, one entry per scenario in `SCENARIOS` (`plain_w`; `soft_w` = the Soft Selection drag with the band overlay, WP-SOFT-01 S2b) |
| `_paths.py` | sys.path bootstrap (pattern copied from `soft_selection/_paths.py`) |
| `tests/` | headless tests: argument handling, statistics, soft variants and report format, import boundary (no pyglet, no window); one end-to-end smoke run of `soft_w`, skipped without a GL context |

## What it measures

Per mouse move, in ms, p50 / p95 / max over `--moves` moves (after `--warmup` unmeasured ones):

| Row | Meaning |
|---|---|
| `transform` | `app.pointer_motion(...)`: the Move step |
| `sync` | `Viewport.sync()` in total (one call per move, as `on_draw`) |
| `update` | the part of `sync` spent inside `GLRenderStore.update` (`calls/move` = how many calls) |
| `rest` | `sync` − `update` (derived data, bounds, overlays) |
| `move` | `transform` + `sync` — the number the 8 ms p95 bar of AD-020 §7 is about |
| `(draw)` | `Viewport.render()` + `glFinish()`; not in `move`. On a software rasteriser this is not GPU time |

Scenario `plain_w`: the selection is the region of N vertices grown (breadth-first over edges) from the
front-most vertex; N = the influenced-vertex counts of
[`experiments/soft_selection/FINDINGS.md`](../soft_selection/FINDINGS.md) §2.2 (head 9 / 36 / 68, body
18 / 76 / 112). The region is set through the `Selection` (112 pick clicks would measure the picker),
then W is armed, `--moves` moves run (direction reverses halfway), W is released, and the drag is undone
so every row starts from the unmodified asset.

### Scenario `soft_w` (WP-SOFT-01 S2b, AD-020 §7.3)

Soft Selection on (switched on through the public entry points: `O`, `Shift`+wheel, `Ctrl+O`, `Shift+O`), the window's
band overlay attached (`GLSoftBandOverlay` is part of `GL_TYPES`). Seed = the front-most vertex (max z) + its one-ring;
radius 5 / 15 / 30 / 50 % of the bounding radius × both metrics (`--sizes` = radius percents, `--metrics` = a subset),
head and body. The same per-move rows as above (the `move` bar applies), plus rows reported once per row, not gated:

| Once-per-row | Meaning |
|---|---|
| `first move` | the first mouse move: `begin()` incl. the influence, and the first push of the op's weights into the overlay |
| `commit frame` | `key_release` (commit) + `sync` (which recomputes the preview) + `render` + `glFinish` |
| `preview recompute` | `compute_influence` + band mapping for the seed, standalone: the work `Application` does per triggering event |
| `settings change` | Shift+O key press + `sync`, end to end (recomputes the preview for the measured selection) |
| `selection click` | `select_at` on the front-most vertex: pick + preview of one vertex, end to end |

`moving V` in the heading is the influenced set of the measured selection (seeds + band points).

## Run

From the repo root (Windows command prompt / PowerShell and Linux alike; Linux headless: `xvfb-run -a`):

```
python experiments/drag_cost/probe_drag_gl.py
python experiments/drag_cost/probe_drag_gl.py --assets head_basemesh --sizes 9 36
python experiments/drag_cost/probe_drag_gl.py --moves 400
python experiments/drag_cost/probe_drag_gl.py --scenarios soft_w --metrics geodesic --sizes 15 30
python experiments/drag_cost/probe_drag_gl.py --list
python -m pytest experiments/drag_cost/tests
```

The output names `GL_VERSION` / `GL_RENDERER` of the window, which closes one of the open items of
`REFERENCE_HARDWARE.md` §2 when run on the reference PC. Plain ASCII, pastes cleanly into the chat.

## Result: container, before → after (2026-10-10)

**Container numbers, not the reference PC** (`REFERENCE_HARDWARE.md` §4): Intel Xeon @ 2.10 GHz, 4
logical cores, Python 3.13.16, `GL_RENDERER` llvmpipe (Mesa 25.2.8, GL 4.5 core), hidden 1024×768 window,
200 moves per row. "Before" = `main` @ `2a5f372` (full-buffer patch), "after" = slice-only patch. ms per
move, p50 / p95.

| Asset | Selection | store.update calls/move | `move` before | `move` after | `update` before | `update` after |
|---|---:|---:|---:|---:|---:|---:|
| head (326 V) | 9 | 32 | 1.49 / 2.11 | 0.39 / 0.57 | 1.17 / 1.66 | 0.07 / 0.12 |
| head | 36 | 100 | 4.06 / 6.32 | 0.74 / 0.92 | 3.50 / 5.56 | 0.20 / 0.27 |
| head | 68 | 176 | 7.10 / 11.62 | 1.10 / 1.50 | 6.25 / 10.46 | 0.35 / 0.51 |
| body (928 V) | 18 | 50 | 5.39 / 6.81 | 0.68 / 0.86 | 4.77 / 6.09 | 0.11 / 0.17 |
| body | 76 | 186 | 18.14 / 24.97 | 1.35 / 1.88 | 17.04 / 23.67 | 0.37 / 0.54 |
| body | 112 | 239 | 24.56 / 36.74 | 1.64 / 2.36 | 23.17 / 34.69 | 0.48 / 0.69 |

Reading:

- Before, `GLRenderStore.update` was 90–95 % of the move and grew with selection size × vertex count;
  after, it is 0.1–0.5 ms and the remaining `sync` cost (`rest`, 0.3–1.0 ms) is derived data, bounds and
  overlays — what the handoff scoped out.
- Every row is under the 8 ms p95 bar after the change; three rows were over before (head 68, body 76,
  body 112).
- The review's P-V4 estimate (body 112 V: p50 28.7 → 1.5 ms) is reproduced (here 24.6 → 1.6 ms).
- `draw` (0.8–1.1 ms p50) is llvmpipe and unchanged by the patch. pyglet marks the whole attribute
  region dirty whenever an attribute is accessed, so the buffer is still uploaded once per frame at draw
  time; the fix removes the per-update Python/ctypes copy, not that single upload.

Reference PC: see "Result: reference PC (2026-10-11)" below.

## Result: `soft_w`, container (2026-10-11)

**Container numbers, not the reference PC** (`REFERENCE_HARDWARE.md` §4): same machine as above (Xeon @ 2.10 GHz, 4
logical cores, Python 3.13.16, llvmpipe, hidden 1024×768 window), 200 moves per row, `main` @ `1ff91bf` + S2b. ms, p50
(and p95 for `move`). Seed = front-most vertex + one-ring (4–5 vertices).

| Asset | Metric | Radius | moving V | `move` p50 / p95 | first move | commit frame | preview recompute | selection click |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| head (326 V) | euclidean | 5 % | 9 | 0.41 / 0.58 | 0.68 | 3.27 | 0.06 | 0.61 |
| head | euclidean | 15 % | 36 | 0.76 / 1.04 | 1.22 | 3.75 | 0.12 | 0.50 |
| head | euclidean | 30 % | 68 | 1.13 / 2.14 | 1.61 | 3.45 | 0.24 | 0.56 |
| head | euclidean | 50 % | 151 | 2.08 / 4.56 | 2.68 | 3.41 | 0.36 | 0.62 |
| head | geodesic | 5 % | 9 | 0.43 / 0.53 | 0.67 | 3.21 | 0.14 | 0.61 |
| head | geodesic | 15 % | 30 | 0.75 / 0.97 | 1.02 | 4.29 | 0.17 | 0.58 |
| head | geodesic | 30 % | 61 | 1.06 / 1.35 | 1.42 | 3.12 | 0.24 | 0.67 |
| head | geodesic | 50 % | 109 | 1.68 / 2.15 | 2.14 | 3.55 | 0.32 | 0.84 |
| body (928 V) | euclidean | 5 % | 18 | 0.77 / 0.95 | 0.97 | 10.95 | 0.13 | 1.77 |
| body | euclidean | 15 % | 76 | 1.36 / 1.76 | 2.36 | 7.23 | 0.32 | 2.58 |
| body | euclidean | 30 % | 112 | 1.68 / 2.72 | 2.18 | 7.50 | 0.31 | 1.89 |
| body | euclidean | 50 % | 142 | 1.99 / 3.01 | 2.57 | 8.78 | 0.33 | 1.84 |
| body | geodesic | 5 % | 10 | 0.65 / 0.83 | 1.20 | 9.03 | 0.38 | 1.98 |
| body | geodesic | 15 % | 28 | 1.03 / 1.33 | 1.48 | 7.20 | 0.39 | 1.99 |
| body | geodesic | 30 % | 107 | 1.63 / 2.13 | 2.46 | 8.92 | 0.76 | 2.97 |
| body | geodesic | 50 % | 135 | 2.12 / 4.03 | 2.91 | 10.56 | 0.58 | 2.30 |

Reading (container only):

- Every row is under the 8 ms p95 bar for `move` (worst: head euclidean 50 %, p95 4.56 ms). The band overlay
  adds position lookups for the band vertices to `sync`'s `rest` and one `set_points` per band; no influence work.
- The preview recompute is 0.06–0.8 ms, so it is not what a selection click costs (that is the pick, 0.5–3 ms).
- The `commit frame` is 3–4 ms (head) and 7–11 ms (body) and includes `render` + `glFinish` on llvmpipe, which is not
  GPU time; it is a once-per-gesture frame and not gated. If it feels like a hitch on the reference PC, split it
  into commit, preview and draw before drawing conclusions.
- This does not claim the reference PC passes; AD-020 §7.3 makes Manu's run the gate before S2c.

## Result: reference PC (Manu, 2026-10-11)

**Reference PC** (`REFERENCE_HARDWARE.md`): Core 2 Quad Q9550, GeForce 9800 GTX, Python 3.14.2, `probe_drag_gl.py` without
arguments (`plain_w` and `soft_w`), after S2b. Recorded from Manu's run; the full per-row table was in the chat and is not
copied here, only the figures that were reported to the repo:

| Figure | Value |
|---|---|
| all `move` rows (p95) | **≤ 8 ms** — the AD-020 §7.3 bar holds |
| worst soft row: body, radius 15 %, euclidean | `move` p95 **7.73 ms** |
| plain W, body, 112 V | `move` p50 **5.29 ms** / p95 **5.77 ms** |
| commit frame (once per gesture, not gated) | body ~30 ms, head ~11–15 ms |
| selection click, body | ~13 ms p50, picking-dominated; preview recompute inside it 0.35–1.9 ms |
| single maxima | up to ~280 ms, outside p95 (not investigated; a GC pause or driver stall is a reading, not a finding) |

Reading: the 8 ms bar holds, with a thin margin on the worst row (7.73 ms): the body, radius 15 %, euclidean soft drag.
The container's worst row was a different one (head euclidean 50 %); the container is llvmpipe, so its ranking was never
expected to carry over (reading, not a finding). Manu's practical result: "man_with_shoes läuft sehr flüssig" (S2c verdict, AD-020). Higher-resolution
meshes are the next test; this probe does not cover them.

S2d (2026-10-11) changed the soft defaults (geodesic metric, Smooth curve) and the radius list (now up to 200 %); the probe
sets its own metric/curve/radius through the public entry points, so its scenario definitions are unchanged. The 150 / 200 %
radii are not in its default size list (5 / 15 / 30 / 50 %); `--sizes 100 200` measures them.

## Praktischer Test für Manu (ca. 5 Minuten)

1. `git pull`
2. `python src/main.py examples/meshes/Man_With_Shoes_basemesh.obj` — eine große Fläche auswählen
   (z. B. halber Oberkörper), W halten und ziehen. Soll sich flüssig anfühlen; Aussehen unverändert.
3. Kopf (`python src/main.py`): kurz W/E/R und Undo — alles wie gewohnt.
4. `python experiments/drag_cost/probe_drag_gl.py` ausführen und die Tabelle in den Chat kopieren
   (ohne Argumente: `plain_w` und `soft_w`; das Ganze dauert etwa eine Minute).

### Soft Selection, S2b (kein Verdikt)

1. `git pull`, `python src/main.py`, `O` an.
2. Vertex an der Wange wählen: farbige Punkte um die Auswahl, je wärmer desto stärker. `Shift`+Mausrad: Bereich
   wächst/schrumpft.
3. `W` ziehen: die Farbpunkte wandern mit; nach dem Loslassen bleiben sie um die Auswahl.
4. `O` aus: keine Farbpunkte mehr.
5. `python experiments/drag_cost/probe_drag_gl.py` ausführen, Tabelle in den Chat kopieren.

Noch kein Verdikt — der Vergleichstest S2c kommt danach, wenn die Zahlen passen.

## Next step

The reference-PC numbers are in `REFERENCE_HARDWARE.md` §2 and above; the 8 ms bar holds and S2c ran (verdict: AD-020
"S2c verdict"). Open: the same probe on higher-resolution meshes; a larger radius (S2d: up to 200 %) can be measured with
`--scenarios soft_w --sizes 100 200`.
