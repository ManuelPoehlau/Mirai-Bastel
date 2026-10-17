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
| `probe_drag_gl.py` | CLI probe: hidden pyglet window, `GL_TYPES` from `src/main.py`, one entry per scenario in `SCENARIOS` (`plain_w`; `soft_w` = the Soft Selection drag with the band overlay, WP-SOFT-01 S2b; `soft_w_sym` = the same under symmetry X, AD-SYM-04 SS3) |
| `probe_navigation_gl.py` | CLI probe (WP-VIEW-PERF-01): orbit, pan, zoom, first hover after a camera change, hover move, selection click, orbit with wire, the `direct` rows (hover vertex/edge/face, Knife hover, Paint step, Box 60/150/300 px, snap query, cache rebuild, `recompute_bounds`; since Slice 1), the real event loop, plain/soft W - per event + frame on head, body and `gollum_20k.obj` (default; `gollum.obj` = 87.5k via `--assets`); see "Navigation and picking" below |
| `_paths.py` | sys.path bootstrap (pattern copied from `soft_selection/_paths.py`) |
| `tests/` | headless tests: argument handling, statistics, soft variants and report format, import boundary (no pyglet, no window); one end-to-end smoke run of `soft_w`, skipped without a GL context; `test_probe_navigation_args.py` for the navigation probe (arguments, asset paths, row budget, report format, import boundary) |

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

### Scenario `soft_w_sym` (AD-SYM-04 SS3, D-4)

`soft_w` under symmetry X: Shift+S (one Undo step, undone after each row), seed = a paired +X vertex next to the
front-most seam vertex + its paired +X one-ring (off the plane; at every default radius the falloff crosses the middle,
the row label counts the seam vertices it reaches). Same rows; `preview recompute` is the symmetric field with the pairing
reused (what the app does per selection or settings trigger), plus `symmetry report` (what a geometry change adds once,
shared with the symmetry display). Not in the default scenarios. Container result and reading:
[AD-SYM-04, implementation note SS3](../../docs/architecture/AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md#implementation-note-2026-10-14-slice-ss3)
(all rows under the bar in the container, worst body p95 7.35 ms). **Reference PC (2026-10-15): over the bar on the body
from 15 % and on the head at 50 % euclidean** — "Result: `soft_w_sym`, reference PC" below.
`python experiments/drag_cost/probe_drag_gl.py --scenarios soft_w soft_w_sym`.

## Run

From the repo root (Windows command prompt / PowerShell and Linux alike; Linux headless: `xvfb-run -a`):

```
python experiments/drag_cost/probe_drag_gl.py
python experiments/drag_cost/probe_drag_gl.py --assets head_basemesh --sizes 9 36
python experiments/drag_cost/probe_drag_gl.py --moves 400
python experiments/drag_cost/probe_drag_gl.py --scenarios soft_w --metrics geodesic --sizes 15 30
python experiments/drag_cost/probe_drag_gl.py --scenarios soft_w soft_w_sym
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

## Result: `soft_w_sym`, reference PC (Manu, 2026-10-15)

**Reference PC** (Core 2 Quad Q9550, GeForce 9800 GTX, `GL_VERSION` 3.3.0, Windows 10 19045, Python 3.14.2),
`python experiments/drag_cost/probe_drag_gl.py --scenarios soft_w soft_w_sym` at `63bcf65` (AD-SYM-04 SS3), 200 moves per row.
The full output was in the chat; recorded here: `move` p50 / p95 and the once-per-row figures that changed, ms.

| Asset | Metric | Radius | `soft_w` moving V | `soft_w` move | `soft_w_sym` moving V (seam V) | `soft_w_sym` move | verdict |
|---|---|---:|---:|---:|---:|---:|---|
| head | euclidean | 5 % | 9 | 0.95 / 1.23 | 15 (3) | 1.40 / 1.61 | OK |
| head | euclidean | 15 % | 36 | 2.15 / 2.42 | 40 (8) | 2.65 / 4.52 | OK |
| head | euclidean | 30 % | 68 | 3.30 / 3.60 | 77 (11) | 4.50 / 5.79 | OK |
| head | euclidean | 50 % | 151 | 6.57 / 6.96 | 176 (16) | 8.00 / **8.80** | **OVER** |
| head | geodesic | 5 / 15 / 30 / 50 % | 9–109 | ≤ 5.11 / 5.43 | 15–143 | ≤ 6.79 / 7.21 | OK |
| body | euclidean | 5 % | 18 | 1.64 / 1.99 | 37 (5) | 3.31 / 3.74 | OK |
| body | euclidean | 15 % | 76 | 3.85 / 4.23 | 175 (13) | 8.73 / **9.25** | **OVER** |
| body | euclidean | 30 % | 112 | 5.13 / 5.54 | 251 (27) | 11.49 / **12.20** | **OVER** |
| body | euclidean | 50 % | 142 | 6.18 / 6.70 | 342 (34) | 15.25 / **15.89** | **OVER** |
| body | geodesic | 5 % | 10 | 1.29 / 1.65 | 32 (4) | 3.10 / 3.53 | OK |
| body | geodesic | 15 % | 28 | 2.34 / 2.75 | 157 (11) | 8.07 / **8.61** | **OVER** |
| body | geodesic | 30 % | 107 | 4.97 / 5.34 | 235 (23) | 10.88 / **11.50** | **OVER** |
| body | geodesic | 50 % | 135 | 6.05 / 6.55 | 281 (31) | 13.05 / **13.75** | **OVER** |

| Once per row (not gated) | `soft_w` head / body | `soft_w_sym` head / body |
|---|---|---|
| first move | 1.6–8.0 / 2.3–8.8 | 4.5–13.1 / 11.9–27.4 |
| commit frame | 10–12 / 27–30 | 17–21 (one 78.5) / 48–64 |
| selection click | 3.6–4.3 / 11–13 | 5.1–8.8 / 20–24 |
| preview recompute | 0.2–1.1 / 0.3–1.9 | 0.3–2.1 / 0.7–4.1 |
| symmetry report (per geometry change) | — | 5.6–5.7 / 16.9–17.5 |
| settings change | 0.2–1.2 / 0.4–2.0 | 0.5–2.3 / 1.1–4.6 |

Reading (agent, 2026-10-15):

- **The bar is missed by the moved set, not by the bands or the field.** `move` grows with the vertices that move at
  ≈ 0.045 ms per moved vertex on the body in both scenarios (plain 142 V → p95 6.70; symmetric 175 V → 9.25, 342 V → 15.89);
  symmetric Soft moves both sides, so at the same radius it moves 2–2.5× as many vertices. `transform` stays ≤ 1.3 ms; the
  rest is `sync` (`update` + `rest`). On the body the bar sits at ≈ 160 moved vertices, so every symmetric body row from
  15 % on is over; on the head only euclidean 50 % (176 V).
- Container decomposition of `sync` in a symmetric body drag (scratch probe, not committed): the soft bands' overlay sync
  0.05–0.08 ms, the symmetry display's sync 0.16 ms per move (its O(V) `geometry_signature` + the markers; deferred, so no
  re-pairing), the remainder grows with the moved set (derived data and bounds, `store.update` per vertex).
- **Once per gesture:** the symmetry report costs **17 ms** on the body here (it pairs twice, `symmetry_state` re-derives
  the correspondence) and sits in every commit frame (48–64 ms); the first move pays the tool's own pairing (11.9–27.4 ms).
  The selection click (20–24 ms) is the picker (the symmetric seed sits on the chest, the plain one on the hand); the preview
  inside it is ≤ 4.1 ms and does no pairing.
- By AD-020 §7 a missed bar is a viewport question, not a reason to change the semantics. Options (none built, for the
  WP-VIEW-PERF-01 fix slice): **V-1** affected-only bounds (Fix option 6 above) and fewer per-vertex `store.update` calls —
  the per-moved-vertex cost, the only lever for the `move` rows; **V-2** the symmetry display skips `geometry_signature`
  while it defers (−0.16 ms container per move); **V-3** `symmetry_report` pairs once (`symmetry_state` taking the given
  correspondence: ≈ −8 ms per commit frame on the body); **V-4** `begin()` takes the preview's correspondence (≈ −8 ms on
  the first move); Fix options 1–3 above for the click.

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

## Navigation and picking on a high-resolution mesh (WP-VIEW-PERF-01, 2026-10-11)

Discovery, Type B, mode M5: measure and explain, propose fixes; **no change under `src/`**. Question (Manu, reference PC):
with `examples/meshes/gollum.obj` (21 875 V / 21 875 quads) not only soft transforms but Orbit, Pan and Zoom lag
strongly. Where does the time go per input event and per frame?

### Method

`probe_navigation_gl.py` drives the same chain as `probe_drag_gl.py` (`Application` → `Viewport` → `GLRenderStore` + the
`GL_TYPES` overlays of `src/main.py`, hidden 1024×768 window) through the window's public entry points
(`pointer_press` / `pointer_drag` / `pointer_release` / `pointer_scroll` / `pointer_motion` / `key_press`). One sample = one
input event, then the frame `on_draw` would draw (`sync()` + `render()` + `glFinish()`). Instrumentation wraps from the
outside, nothing under `src/` is touched (handoff §10: no hook was needed):

| Column | Meaning |
|---|---|
| `event` | the `Application` handler for the event |
| `pick` | part of `event` inside `pick_component` (`mirai.application` module attribute wrapped) |
| `cache` | part of `pick` inside `PickCache.refresh` (instance attribute wrapped); `rebuilds/event` = refreshes whose signature changed |
| `occl` | part of `pick` inside `vertex_occluded` / `edge_point_occluded` (`mirai.viewport.picking` module attributes); `tests/event` = calls |
| `sync` | `Viewport.sync()` |
| `draw` | `Viewport.render()` + `glFinish()`, CPU wall time |
| `gpu` | `GL_TIME_ELAPSED` query around `Viewport.render()` (GL 3.3 core) - real GPU time on a real GPU, not meaningful on llvmpipe |
| `upload` | bytes pyglet committed to GL buffers during the frame (`BackedBufferObject.commit` wrapped: dirty region) |
| `frame` | `event` + `sync` + `draw` |

Scenarios (handoff E2): `orbit` / `pan` (Alt+LMB / Alt+Shift+LMB drag steps of 4 px), `zoom` (wheel notches in/out with the
cursor resting on the mesh), `first_hover` (a short orbit gesture, unmeasured, then the first plain mouse move), `hover_move`
(plain moves of 3 px across the mesh, camera unchanged), `select_click` (LMB press + release alternating between two
vertices), `orbit_wire` (orbit with the Shift+D wire overlay, H5), `loop` (H3: `src_main.install_handlers` on the window and
`pyglet.app.run(1/60)` + the 1/60 s `update_viewport` tick as `src_main.run`, events injected through
`window.dispatch_event`: orbit drags at 240/s, hover moves at 120/s, wheel notches at 20/s, 2 s each; counts on_draw vs
events and the longest time without a frame), `plain_w` 36 / 112 / 500 V and `soft_w` 15 % / 50 % geodesic (the
scenarios of `probe_drag_gl.py`, reused; their once-per-row extras with 3 instead of 15 repetitions). A cProfile top-N for
orbit, zoom and first hover runs on the last asset. Rows have a time budget (`--row-seconds`, default 8 s; at least
`--min-steps` samples), so `n` is smaller on gollum.

Assets: head and body by registry name, gollum by path (`--assets` takes registry names or `.obj` paths). (2026-10-11 the
21 875 V gollum was not registered; since then `gollum` is registered and points at the 87.5k file, the 21 875 V one is
`gollum_20k.obj` - see "Audit at HEAD" below.)

### Result: container (2026-10-11)

**Container numbers, not the reference PC** (`REFERENCE_HARDWARE.md` §4): Intel Xeon @ 2.80 GHz, 4 logical cores, Python
3.13.16, `GL_RENDERER` llvmpipe (Mesa 25.2.8, GL 4.5 core) - a software rasteriser, so `draw` is CPU rasterisation and
`gpu` is not GPU time. `main` @ `fdef090`, default run (`python experiments/drag_cost/probe_navigation_gl.py`, 2 min). ms
p50 (p95) per event + frame; one frame at 60 Hz = 16.7 ms.

| Scenario | head (326 V) frame | body (928 V) frame | **gollum (21 875 V) frame** | gollum: where it goes |
|---|---:|---:|---:|---|
| orbit step | 0.89 (1.25) | 1.16 (1.97) | **6.85 (8.62)** | event 0.03, sync 0.07, draw 6.76 (llvmpipe), upload 0 |
| pan step | 0.98 (1.43) | 0.99 (1.35) | **6.99 (11.46)** | event 0.05, sync 0.06, draw 6.89, upload 0 |
| zoom notch | 6.04 (8.49) | 9.49 (14.17) | **813 (1535)** | pick 797 = cache rebuild 188 + **occlusion 596 (91 tests)** |
| first hover after a camera change | 5.53 (8.79) | 12.25 (20.93) | **332 (545)** | pick 322 = cache rebuild 178 + occlusion 129 (16 tests) |
| hover move (cache valid) | 1.76 (4.51) | 1.76 (3.91) | **183 (929)** | pick 173 = occlusion 166 (37 tests); scan ~7 |
| selection click | 2.20 (3.81) | 4.88 (6.46) | **233 (327)** | pick 223 = occlusion 217 (30 tests) |
| orbit, wire overlay on | 1.90 (3.34) | 2.18 (3.10) | **19.5 (27.0)** | draw 19.4 (llvmpipe, ~44k lines), sync 0.08, upload 0 |

W drags (`move` = transform + sync, the AD-020 8 ms p95 bar; draw not included):

| Drag | head move p50 / p95 | body | **gollum** | gollum: where it goes |
|---|---:|---:|---:|---|
| plain W 36 V | 1.51 / 2.06 | 2.05 / 2.53 | **10.76 / 16.77** | sync 10.6, of which `store.update` 0.4; rest = `recompute_bounds` over all V |
| plain W 112 V | 2.30 / 3.91 | 2.50 / 4.00 | **13.30 / 24.16** | sync 13.0 (update 0.9) |
| plain W 500 V | - (326 V) | 13.85 / 15.14 | **20.96 / 34.24** | sync 20.1 (update 3.1) |
| soft W 15 % geodesic | 1.04 / 1.86 (30 V) | 1.80 / 2.22 (28 V) | **21.8 / 36.2 (508 V)** | sync 20.5 (update 3.8); commit frame **2045 ms** |
| soft W 50 % geodesic | 2.70 / 3.95 (109 V) | 2.86 / 5.09 (135 V) | **73 / 129 (3339 V)** | sync 67 (update 19, 6888 calls/move); commit frame **2689 ms** |

Event loop (`loop`, real wiring, gollum): orbit 245 events → 118 on_draw in 2 s (59/s), longest time without a frame
**20 ms**; hover 3 events in 4.5 s (**1.5 s each**), 2 frames, longest time without a frame **2.8 s**; zoom 3 notches in
4.4 s (**1.4 s each**), longest time without a frame **1.8 s**. Head and body: ~58 frames/s in all three phases, longest
gap 18-53 ms.

cProfile (gollum, profiler overhead ~3x, so read the shares, not the absolute ms): zoom and first hover are dominated by
`PickCache.refresh` → `OrbitCamera.project_to_screen` per vertex, which recomputes `eye()` and `basis()` (trig, three
normalisations) **for every vertex** (87 600 calls of each for 4 refreshes), and by the occlusion test: `point_occluded`
loops over all 21 875 face bboxes in Python, and `_incident_faces_of_vertex` calls `core.Mesh.vertex_edges`, a linear scan
over all 43 750 edges (`src/core/mesh.py`: "V1: einfacher Scan") - ~4.5 ms per call, about 40 % of one occlusion test.
Orbit: 95 % of the frame is the llvmpipe draw (`draw_subset`); no Python work of note.

Why so many occlusion tests: `pick_nearest_vertex` runs the occlusion test for **every** vertex within 14 px that is closer
than the best visible one found so far, in mesh order. An occluded vertex never lowers that bound, so every hidden vertex
within 14 px of the cursor (the back of the head behind the cursor) costs one full test: 16-91 tests per pick on gollum vs
1-6 on head and body. With ~6.5 ms per test this is the largest single cost.

### Hypotheses (handoff E1)

| # | Hypothesis | Verdict | Evidence (container) |
|---|---|---|---|
| H1 | every zoom notch calls `_refresh_hover` → full `PickCache` rebuild | **Confirmed, and it is the smaller half** | 1.0 rebuild per notch, 188 ms on gollum; the occlusion tests of the same pick cost 596 ms (91 tests) - the notch is 813 ms p50, 1.5 s p95 |
| H2 | plain mouse motion after any camera change rebuilds the pick cache on the first hover | **Confirmed** | `first_hover` 1.0 rebuild/event, 178 ms + 129 ms occlusion = 332 ms p50. **And** every later hover move without a camera change still costs 183 ms p50 / 929 ms p95 (occlusion, not the cache) |
| H3 | `on_draw` runs per input event rather than once per frame | **Rejected as stated** | pyglet 2.1 `app.run(1/60)` dispatches `on_draw` only from the scheduled `_redraw_windows`; `loop` shows 59 on_draw/s with 122-189 orbit events/s. **But** the input work is not frame-bounded either: every hover move and wheel notch does its whole pick inside the event handler, so one event blocks the loop for 0.2-1.5 s on gollum (`loop` hover/zoom: < 1 frame/s). On Windows, mouse moves are coalesced by the OS, wheel notches are queued one by one (a fast scroll = one pick per notch, back to back) |
| H4 | a camera-only frame uploads whole attribute buffers or re-syncs overlays/edges | **Rejected** | upload 0 KB in every orbit/pan/orbit_wire frame; sync 0.03-0.08 ms; wire edges are not rebuilt on a camera change. A hover/selection change uploads 85.5 KB = the whole `highlight_flags` buffer (21 875 floats; the attribute is kept on llvmpipe) and costs ~3 ms `sync` on gollum - a side cost, not the lag |
| H5 | the draw itself is significant on the 9800 GTX | **Rejected (reference PC)** | indexed buffer (`vertex_list_indexed`, not de-indexed - that part is rejected from the code); 43 750 triangles. Reference PC: gollum `gpu` **0.56 ms**, `draw` 1.14 ms per orbit frame; with wire `gpu` 1.15 ms, `draw` 1.95 ms; 0 KB upload. (Container llvmpipe: 6.8 / 19.4 ms CPU raster - not GPU time.) |
| - | **found:** occlusion test cost (O(F) face loop + O(E) `vertex_edges` per hidden candidate) | **New, dominant** | see above; 30-91 tests per pick on gollum |
| - | **found (reference PC only):** `math.hypot` in the nearest-vertex scan costs ~7.5 µs per vertex there (container ~0.1 µs per call) | **New, dominant for hover on the reference PC** | see "Result: reference PC" below: the scan alone is ~165 ms per gollum hover move, ~7 ms on body, ~2.4 ms on head |
| - | **found:** `RenderMesh._sync_geometry` recomputes the bounds over **all** vertices on every W move | **New** | gollum plain W 36 V: sync 10.6 ms, `store.update` 0.4 ms; profiled: `recompute_bounds` ~85 % of `sync`. Nothing in `src/` reads the bounds; `VIEWPORT_V02_ARCHITECTURE.md` §7 already asks for "affected vertices only" |
| - | **found:** the commit frame of a W drag on gollum is 2-2.7 s | **New** | `key_release` → `_refresh_hover` → cache rebuild + occlusion (184 tests in one profiled commit) |

**What this means for "Orbit and Pan lag":** in the container the orbit/pan step itself is cheap on gollum (event 0.03 ms,
no pick, no upload, 59 frames/s in the real loop). The lag the Artist sees is most likely the picking **around** the
gesture: every mouse move before pressing Alt+LMB is a 0.2-1 s pick, the press waits behind the pick that is running, and
the first move after releasing (and after every zoom notch) rebuilds the cache and picks again (0.3 s). The reference-PC
run confirms this (orbit step 1.2 ms on gollum, GPU 0.56 ms; hover 0.25 s p50 / 1.5 s p95, zoom notch 1.7 s; see "Result:
reference PC" below). The pre-run estimate here (0.4-0.6 s per hover, ~2 s per notch) was close for zoom and too high for
the hover median.

### Fix options (ranked by gain / cost; none implemented)

Gains are container estimates for gollum (option 1: reference-PC estimate), to be confirmed by re-running this probe after
a fix; the reference-PC reading per mesh size is under "Result: reference PC" below.

| Rank | Option | Where | Expected gain (gollum, container) | Cost / risk |
|---:|---|---|---|---|
| 1 | **Squared distances instead of `math.hypot`** in the pickers' scans (compare `dx*dx + dy*dy` with `max_px**2`; `sqrt` only for the result if needed). Added after the reference-PC run | `mirai/viewport/picking.py` (`pick_nearest_vertex`, `_point_segment_distance*`) | container: small (hypot is 0.1 µs there). **Reference PC: hover scan ~165 → ~10-20 ms on gollum, ~7 → < 1 ms on body** (estimate from the measured ~7.5 µs per vertex) | trivial; same order and same picks (monotonic); existing picking tests |
| 2 | **Fewer occlusion tests:** test candidates nearest-first and stop at the first visible one (sort the ≤ 14 px candidates by screen distance) instead of testing every closer hidden vertex in mesh order. Same result by construction (the nearest visible vertex) | `mirai/viewport/picking.py` (`pick_nearest_vertex`, same for edges) | 30-91 → ~1-5 tests per pick: hover move 183 → ~15-40 ms, click 233 → ~20-40 ms, zoom 813 → ~200-250 ms | small; identical picks (existing B8 tests + a "hidden vertex closer in mesh order" test) |
| 3 | **Cheaper occlusion test:** vertex → incident-faces map built once per mesh state in `PickCache` (replaces `core.Mesh.vertex_edges`, an O(E) scan) | `picking_cache.py` / `picking.py` | ~40 % off each test (~2.5 of ~6.5 ms) | small; the cache already has the right invalidation points. Changing `vertex_edges` in `src/core` instead is frozen-core work (AD needed) and not recommended for this reason |
| 4 | **Cheaper cache rebuild:** compute eye/basis/aspect once per refresh and project inline, instead of `camera.project_to_screen` per vertex (which recomputes them for every vertex) | `picking_cache.py` (maybe a `camera.projector()` helper) | rebuild 178-188 → ~90 ms (estimate ~2x: the per-vertex `eye`/`basis` calls are ~50 % of the profiled rebuild; same values) | small; numerically identical if the same formula is used |
| 5 | **Coalesce picking to once per frame:** a zoom notch / camera change / motion marks hover stale; the tick picks once at the latest cursor | `application.py` (`pointer_scroll`, `_refresh_hover`, `update_viewport`), `src/main.py` untouched | a burst of N wheel notches costs 1 pick, not N; motion never blocks more than one pick per frame | small-medium; behaviour: hover appears one frame later (Artist-visible? probably not); needs care with the click path, which must stay synchronous |
| 6 | **Lazy / affected-only bounds** in `RenderMesh._sync_geometry` | `src/viewport/render_mesh.py`, `derived.py` | ~9 ms less `sync` per W move on gollum (plain W 36 V: 10.8 → ~2 ms p50; 500 V stays over 8 ms because of the per-vertex `store.update` calls) | small; touches a documented counter (`bounds_recalculations`, `tests/test_render_mesh.py`); `VIEWPORT_V02_ARCHITECTURE.md` §7 already describes this |
| 7 | Face screen-space grid in `PickCache` (bucket face bboxes) so the occlusion test visits only faces under the pixel | `picking_cache.py` / `picking.py` | the O(F) loop per test → O(faces in the cell); with rows 2-4 above, a further ~2x per test | medium (new structure, built per rebuild: adds to the rebuild cost) |
| 8 | Drop the dead `highlight_flags` rebuild (B2b follow-up cleanup) | `render_mesh.py`, `overlay.py`, `gl_render_store.py` | ~3 ms sync + 85 KB upload per hover/selection change | small-medium; part of a documented cleanup, separate decision |
| 9 | World-space spatial index (grid/BVH) for vertices and faces, camera-independent: no rebuild on orbit/zoom at all | new module in `mirai/viewport/` | cache rebuild → 0 per camera change; pick O(cells along the ray) | medium-high; invalidation on every mesh edit; only worth it if 1-5 are not enough |
| 10 | GPU picking (ID buffer + `glReadPixels`, depth = occlusion for free) | Viewport + `mirai` | pick ~O(1) CPU at any mesh size | high: an extra render pass and a Viewport service for `mirai` (architecture change, AD-018 scope); not recommended before 1-5 are measured |
| - | LOD / decimated display mesh | renderer | - | **not recommended** because the draw is not the measured cost (orbit event 0.03 ms, no upload) and H5 is open; it would add a second geometry path for no shown gain |
| - | NumPy vectorisation of projection / occlusion | `mirai/viewport` | large (estimate) | **not recommended now** because it adds a new runtime dependency and a CPU-baseline risk on the Core 2 (no SSE4.2, `REFERENCE_HARDWARE.md` §4: newer instruction sets are a reported conflict); pure-Python 1-5 come first |

Recommended first slice (engineering proposal): 1-4 together (all inside `mirai/viewport` picking, no behaviour
change, no architecture change), then re-run this probe; 5 and 6 as the next slice. See "Result: reference PC" below for
what that is expected to buy per mesh size. Which
mesh size must stay fluid is the Artist's Intent question (handoff §7) - the numbers above are what that answer costs.

### Result: reference PC (Manu, 2026-10-11)

**Reference PC** (`REFERENCE_HARDWARE.md`): Core 2 Quad Q9550 @ 2.83 GHz, Windows 10 (19045), Python 3.14.2,
`GL_VERSION` **3.3.0**, `GL_RENDERER` **GeForce 9800 GTX/9800 GTX+/PCIe/SSE2**; default run, `main` @ `54a7dab`. ms p50
(p95) per event + frame; `gpu` is real GPU time here.

| Scenario | head (326 V) | body (928 V) | **gollum (21 875 V)** | gollum: where it goes |
|---|---:|---:|---:|---|
| orbit step | 0.53 (1.94) | 0.68 (1.09) | **1.19 (3.30)** | event 0.01, sync 0.04, draw 1.14, **gpu 0.56**, upload 0 |
| pan step | 0.55 (1.04) | 0.54 (0.92) | **1.19 (1.56)** | event 0.02, draw 1.14, gpu 0.57 |
| orbit, wire on | 0.82 (1.49) | 0.78 (1.30) | **2.00 (3.01)** | draw 1.95, gpu 1.15 |
| zoom notch | 9.65 (10.74) | **22.44 (24.22)** | **1658 (2368)** | cache rebuild 349 + occlusion 1137 (92 tests, ~12 ms each) + scan |
| first hover after a camera change | 9.25 (10.04) | **26.16 (26.81)** | **737 (814)** | cache 350 + occlusion 206 (17 tests) + scan |
| hover move | 3.67 (4.68) | 8.00 (11.32) | **252 (1529)** | occlusion 79 (21 tests); the rest is the scan |
| selection click | 4.15 (4.58) | 11.92 (13.21) | **571 (576)** | occlusion 400 (31 tests) + scan |

Body rows in bold are over one 60 Hz frame (16.7 ms) on **every** sample (40/40) - the body was not tested for navigation
before; head stays under a frame everywhere.

W drags (`move` p50 / p95, AD-020 bar 8 ms p95): gollum plain W 36 V **20.1 / 20.8** (sync 20.0, `store.update` 1.0 - the
rest is the all-vertex bounds), 112 V 23.4 / 24.2, 500 V 37.9 / 39.4; soft W 15 % geodesic (508 V moving) 40.5 / 65.0,
50 % (3 339 V) 147 / 153; commit frame **3.3-4.2 s**. Body: everything under 8 ms p95 except plain W 500 V (20.5 / 21.5).
Head: all under the bar.

Event loop (real wiring): gollum orbit 434 events, 57 frames/s; hover 3 events in 3.2 s (**1.05 s each**), longest time
without a frame **1.95 s**; zoom 3 notches in 3.4 s (1.13 s each), longest **1.16 s**. A ~90-97 ms gap appears in the
orbit phase of **all three** assets (head included), so it is not mesh-dependent (Windows timer / first frame;
not investigated). Body: zoom 24 ms per notch, 40 frames/s.

**The `math.hypot` finding.** The nearest-vertex scan (`pick_nearest_vertex`: one `dict.get` + one `math.hypot` per
vertex) costs about **7.5 µs per vertex** on the reference PC: head hover pick 2.97 ms - occlusion 0.51 = ~2.4 ms for
326 V; body 7.2 ms with no occlusion for 928 V; gollum ~165 ms for 21 875 V. In the container it is ~0.4 µs per vertex.
The cProfile run names it: `math.hypot` 87 500 calls, 650 ms own time (container: not in the top 8; `timeit` there:
0.1 µs per call). A 20x gap for one builtin is far more than the ~2x the rest of the code shows. Likely cause (reading, not
verified): CPython's `hypot` uses `fma()` for its correction step, and the Core 2 has no FMA instruction, so the Windows
C runtime emulates it in software. Checkable on the reference PC with
`python -c "import math,timeit;print(timeit.timeit('h(3.1,4.2)',globals={'h':math.hypot},number=100000)*10,'us')"`.
Either way the fix is the same and trivial (fix option 1: compare squared distances).

**Scale factor reference PC / container** (same code, same scenarios): ~2x for Python-heavy rows (gollum zoom 2.0x, first
hover 2.2x, click 2.4x, plain W 1.8-1.9x, cache rebuild 1.9x, occlusion test 1.9x), but ~20x for the `hypot` scan (body
hover 4.5x overall). The draw is the other way round: the real GPU is 5-10x faster than llvmpipe.

**Reading (reference PC numbers):**

- **Orbit and pan are fluid on gollum** (1.2 ms per step, GPU 0.56 ms, 57 frames/s in the loop). H5 is rejected; LOD is
  not needed for 44k triangles on the 9800 GTX. The lag Manu feels during navigation is the picking around it: every mouse
  move is a 0.25-1.5 s pick, the first move after an orbit or zoom 0.74 s, and every wheel notch 1.7 s (queued per notch).
- **Body is already over a frame** for zoom (22 ms) and the first hover after a camera change (26 ms) - not "laggy", but
  not free either; head is fine.
- Expected after options 1-4 (estimate from these numbers, to be re-measured): gollum hover move ~250 → ~30-50 ms, click
  ~570 → ~40-60 ms, zoom / first hover ~1.7 s / 0.74 s → ~200-250 ms (the remaining cost is the camera-dependent cache
  rebuild of ~175 ms); body zoom / first hover ~22-26 → ~8-10 ms. So 1-4 make body comfortably fluid and gollum's hover
  usable, but a zoom or the first move after an orbit on gollum would still cost ~0.2 s. Getting **that** under a frame on
  a 20k-vertex mesh needs option 5 (coalescing, so a scroll burst pays once) plus option 9 (camera-independent index) or
  10 (GPU picking) - that is the cost of the Intent answer "gollum must stay fluid".
- W drags on gollum: option 6 (bounds) takes plain W 36 V from 20 to ~2-3 ms per move; soft/large selections stay over
  8 ms because of the per-vertex `store.update` calls (Soft is not the subject of this handoff). The 3-4 s commit frame
  is mostly the hover re-pick after release (options 1-4 cover it).

### Run (reference PC)

From the repo root, Windows (opens no visible window; takes ~5-10 minutes on the reference PC, progress lines `... gollum:
zoom` go to the console while it runs):

```
python experiments/drag_cost/probe_navigation_gl.py
```

Variants: `--assets examples/meshes/gollum.obj` (one asset), `--scenarios orbit pan zoom first_hover` (a subset),
`--row-seconds 4` (shorter), `--profile-top 0` (no profile), `--list`. Linux headless: prefix `xvfb-run -a`.

### Praktischer Test für Manu (Navigation, ca. 10 Minuten)

1. `git pull`
2. `python experiments/drag_cost/probe_navigation_gl.py` — läuft 5–10 Minuten (die Zeilen `... gollum: zoom` zeigen, wo er
   steht). Die ganze Ausgabe (ab `Navigation and picking cost ...`) in den Chat kopieren.
3. Danach entscheidest du, welche Mesh-Größe auf deinem PC flüssig bleiben muss (Kopf, Körper, gollum oder größer) —
   die Tabelle zeigt, was das kostet.

## Audit at HEAD (WP-VIEW-PERF-01, 2026-10-17)

Discovery, no change under `src/`. Question: does the 2026-10-11 picture still hold after AD-021 (objects), Box/Paint
Select, Tweak and the per-polygon shading (FACE_DATA rows), and what do the never-measured paths and future retopology
snapping cost? **Container numbers only** (Xeon @ 2.10 GHz, 4 cores, Python 3.13.16, llvmpipe: `draw` is CPU raster, not
GPU time), `main` @ `45a0bd1`.

**Asset fact.** `5a90685` (2026-10-13) replaced `examples/meshes/gollum.obj` (21 875 V) with an 87 500 V / 87 500 quad
version; the 21 875 V file is back, byte-identical, as `examples/meshes/gollum_20k.obj` (`8897f78`). **Every gollum number
above (2026-10-11, container and reference PC) is `gollum_20k.obj`.** Manu (2026-10-17): the 87.5k mesh was a test of
whether it still navigates fluidly *as a Reference mesh* on the reference PC - **it does** (practical result, no probe
numbers). That matches H5 (the draw is not the bottleneck); everything below is interaction cost, not rendering.

Picking code (`mirai/viewport/picking.py`, `picking_cache.py`) is unchanged since 2026-10-11: none of the fix options
above is built. Like-for-like on `gollum_20k` today vs the 2026-10-11 container table: zoom 457 (813), first hover 175
(332), hover 162 (173), click 118 (233) ms p50, occlusion tests per event 90 / 8 / 37 / 23 (91 / 16 / 37 / 30) - no
regression (the 10-11 run was a 2.8 GHz Xeon; a direction, not a delta). Per-move `store.update` calls grew with the
FACE_DATA rows (plain W, same selections: head 36 V 100 → 179, body 112 V 239 → 372), so the reference-PC margin of the
Soft bar (7.73 ms, 2026-10-11) is unknown until re-measured.

Sizes: `body_L1/L2/L3` = the body after 1/2/3 Catmull-Clark levels of `experiments/subdivision_lab/subd.py` (3 706 /
14 818 / 59 266 V), generated for the run and not committed. Rows marked † come from a scratch probe (same rig as
`probe_navigation_gl.py`, functions called directly; not committed, step 0 of the fix slice adds them here). ms p50 (max).

| Workload | head 326 | body 928 | body_L1 3.7k | body_L2 14.8k | gollum_20k 21.9k | gollum 87.5k |
|---|---:|---:|---:|---:|---:|---:|
| orbit frame (llvmpipe draw) | 0.8 | 0.8 | - | 4.3 | 8.4 | 21.8 |
| cache rebuild † | 2.5 | 4.7 | 17 | 71 | 117 | 469 |
| zoom notch, frame | 3.2 | 5.9 | - | 99 | 457 | 1 869 (p95 3 419) |
| first hover after orbit, frame | 3.1 | 7.4 | - | 129 | 175 | 983 |
| hover vertex mode † | 0.7 | 0.8 | 5.2 | 24 (63) | 182 (936) | 957 (3 846) |
| hover edge mode † | 1.0 | 1.5 | 6.3 | 20 (138) | 79 (461) | 630 (5 914; 277 occl. tests) |
| hover face mode † | 0.1 | 0.1 | 0.4 | 1.5 | 2.0 | 8.1 |
| Knife hover (`knife_pick`) † | 0.4 | 1.5 | 6.1 | 24 | 35 | 158 |
| selection click, frame | 1.5 | 3.1 | - | 61 | 118 | 807 |
| Paint, one 30 px step (5 picks) † | 3.0 | 7.9 | 42 | 180 | 1 940 | 8 314 |
| Box 60 px, vertex † | 2.9 | 11 | 216 | 2 997 | 3 673 | 60 224 |
| Box 300 px, vertex † | 28 | 74 | 1 247 | 17 782 | 43 669 | 705 934 |
| plain W 36 V, `move` p50 / p95 | 1.3 / 1.5 | 1.7 / 2.4 | - | 6.4 / 9.4 | 8.2 / 8.5 | 30 / 35 |
| soft W 15 % geodesic, `move` p50 | 1.0 | 1.3 | - | 14.3 (450 V) | 15.8 (508 V) | 65 (1 897 V) |
| soft drag commit frame | 3.0 | 7.7 | - | 212 | 899 | 5 322 |
| `recompute_bounds` (every W move) † | 0.1 | 0.5 | 1.1 | 4.6 | 6.8 | 35 |
| event loop, hover | 59 fps | 59 fps | - | - | - | 1 event / 3.0 s |

What-if rows † (the candidate fix re-implemented in the scratch probe, compared with the production function):

| What-if | gollum_20k | gollum 87.5k | Same result |
|---|---|---|---|
| W2 vertex hover nearest-first (option 2) | 242 → **9.3** ms (52 → 1.0 tests) | 995 → **40** ms (55 → 1.6 tests) | 11/11 picks on every size |
| W4 eye/basis once per rebuild (option 4) | projection 86 → **15** ms | 455 → **82** ms | ≤ 2e-13 px (the "~2x" estimate above was low) |
| W3 incident faces via `vertex_edges`, per occlusion test (option 3) | 3.0 ms | 17.5 ms | - |
| W1 squared distance (option 1), container | scan 3.1 → 2.4 ms | 18 → 12 ms | identical |
| Ray → surface: BVH (median split, 4 tris/leaf, pure Python) vs `pick_face` with a valid cache | 0.06 vs 2.5 ms; build 648 ms | 0.07 vs 10 ms; build 3.2 s | 40/40 same face (also body, body_L2, body_L3) |

**Confirmed root causes** (beyond 2026-10-11): (a) **Box Select** runs one full O(F + E) occlusion test per element inside
the box (`box_select.elements_in_rect`) - the worst interaction measured, unusable from ~15k V; (b) **Paint** runs one full
`_pick` per 6 px sample; (c) **edge hover** tests up to 277 hidden candidates per pick (mesh order, as for vertices);
(d) the cache rebuild cost is the per-vertex `eye()`/`basis()` (W4: 5.6-7x, not 2x). Face mode, the snap query and the
camera-only frame are cheap per call; their cost is the O(V) rebuild after every camera change.

**Retopology snapping on the current architecture** (ray from the cursor / a vertex's screen position → front face of
the Reference → hit point = `pick_face` + `face_hit_position` with the Reference's own `PickCache`): one query 2 ms on
21.9k, 8 ms on 87.5k with a valid cache; **+107 / 526 ms after every camera change** (rebuild); a drag that snaps k
vertices pays k queries per move (k = 20 on 87.5k ≈ 160 ms). Snapping to the *closest* surface point (not along the view
ray) has no path today. A Reference does not change during retopology, so a camera-independent world BVH built once per
Reference is the one place an index measurably pays (query flat at ~0.07 ms, no rebuild on orbit) -
`VIEWPORT_V02_ARCHITECTURE.md` §4 excludes BVH / GPU ID-buffer for v0.2, so this needs an architecture decision when
retopology becomes a work package; not before.

**Ranking now** (options above, updated by these numbers): Slice 1 = options **2 + 1** (nearest-first for vertex *and*
edge, squared distances), **4** (projection, incl. `ObjectSpaceCamera`), **3** (incident-face map in `PickCache`, per mesh
change not per camera) and **6** (bounds) - all local, no behaviour change. Slice 2 = **Box Select batched visibility**
(screen grid of face bboxes per box; the "simple CPU spatial grid" `VIEWPORT_V02` §4 allows when benchmarks show need)
and option **5** (coalescing; hover one frame later = one Artist check). Then option 8 (dead `highlight_flags`: 3.7 ms +
342 KB per hover change on 87.5k) and batched per-vertex `store.update` for large Soft drags. BVH (retopo) and GPU picking:
architecture decisions, not fix-slice items.

**Benchmark matrix for the fix slices:** sizes head, body, body_L1, body_L2, `gollum_20k` (comparison with the reference
PC history), body_L3 / gollum 87.5k (Reference-mesh role); per size orbit/pan (+ `gpu` on the reference PC), hover vertex /
edge / face, Knife hover, first hover after orbit, zoom notch, click, Box 60/150/300 px, Paint step, plain W 36/112/500,
soft W 15/50 % geodesic, `soft_w_sym` (body), commit frame; retopo: edit mesh head/body over a Reference of 21.9k / 59k /
87.5k - one snap with a valid cache, one after an orbit, 1/20/100 snapped vertices per move.

**Open evidence:** a reference-PC run on gollum 87.5k with numbers (Manu's verdict covers navigation only); reference-PC
Box / Paint / edge / face / Knife rows; the `math.hypot` timeit line above on the reference PC; the `soft_w` margin after
FACE_DATA; Manu's target size for *editing* (ATELIER D1c) - only options 5 and beyond depend on it.

## Result: fix slice 1, container, before → after (WP-VIEW-PERF-01, 2026-10-17)

Production, behaviour-neutral. Built: (1) nearest-first occlusion in `pick_nearest_vertex` / `pick_nearest_edge`
(candidates in range sorted by screen distance, stop at the first visible one; squared distances / screen bboxes in
the scans, exact `hypot` only for the candidates), (2) `PickCache.refresh` projects through
`camera.screen_projector(w, h)` (eye/basis once per refresh; `OrbitCamera` and `ObjectSpaceCamera`; bit-identical to
`project_to_screen`), (3) a vertex → incident-faces map in `PickCache` (`vertex_faces`, rebuilt per mesh state after
`invalidate()`, not per camera) instead of `core.Mesh.vertex_edges` in the occlusion test (`src/core` untouched),
(4) lazy bounds: a W move only invalidates the AABB (`bounds_invalidations`), the O(V) recompute runs on the next read
(`bounds_recalculations`; `VIEWPORT_V02` §4.4 updated). Not built (Slice 2+): Box batched visibility, hover/zoom
coalescing, `highlight_flags`, `store.update` batching.

**Same picks.** `tests/test_picking_equivalence.py` keeps the pre-PERF pickers verbatim and compares: head and body
over a cursor grid plus points on/next to 60 projected vertices, front and back camera, Shaded and Wireframe (body:
~170 hits per camera, occlusion changes the pick on ~70 of them); without a cache; through a placed
`ObjectSpaceCamera`; a seeded `gollum_20k` sample (12/13 cursors hit, occlusion changes 6-8); a hidden vertex and edge
earlier in mesh order than the visible nearest one (now 2 tests instead of a mesh-order sweep); an equal-distance tie
(mesh order kept); Box Select vertex/edge/face on body (and once by hand on `gollum_20k`, 60 px: 440 / 820 / 382
elements, identical). The probe's Box rows select the same counts before and after.

**Container numbers, not the reference PC** (`REFERENCE_HARDWARE.md` §4): Intel Xeon @ 2.80 GHz, 4 cores, Python
3.13.16, llvmpipe (`draw` = CPU raster). Same probe, same container, one after the other: before = `65e30ae` + the step-0
probe (`src/` unchanged), after = this commit. Default run (`python experiments/drag_cost/probe_navigation_gl.py`)
plus `--scenarios direct` (camera framed first) and, for 87.5k, `--assets examples/meshes/gollum.obj --scenarios zoom
first_hover hover_move select_click --profile-top 0`. ms p50 (p95); one 60 Hz frame = 16.7 ms.

| Row (`gollum_20k`, 21 875 V) | before | after | what moved |
|---|---:|---:|---|
| zoom notch, frame | 685 (1 273) | **86 (141)** | occlusion tests 85.5 → 2.0 per notch; cache rebuild 135 → 63 |
| first hover after an orbit, frame | 255 (325) | **86 (122)** | rebuild 130 → 63; tests 15.4 → 1.0 |
| hover move, frame | 211 (836) | **20 (30)** | tests 37.6 → 1.7 |
| selection click, frame | 198 (272) | **25 (28)** | tests 29 → 1.0 |
| orbit / pan step, frame | 8.2 / 8.5 | 7.7 / 8.4 | unchanged (llvmpipe draw; no pick) |
| direct: hover vertex | 83 (882) | **6.7 (19)** | tests 41 → 1.5 |
| direct: hover edge | 69 (397) | **20 (31)** | tests 50 → 1.0 |
| direct: hover face | 3.4 | 3.7 | unchanged (no occlusion test) |
| direct: Knife hover (`knife_pick`) | 58 (925) | **13 (30)** | its vertex + edge picks |
| direct: Paint, one 30 px step (5 picks) | 2 100 | **38** | tests 325 → 7 |
| direct: Box 60 / 150 / 300 px, vertex | 4 075 / 17 398 / 47 370 | **1 429 / 6 920 / 19 901** | same tests (673 / 2 684 / 6 985), each cheaper (map instead of `vertex_edges`) |
| direct: Box 60 / 150 / 300 px, face | 1 189 / 6 269 / 18 552 | 1 183 / 5 957 / 19 276 | unchanged: `point_occluded` per face is Slice 2 |
| direct: snap query, valid cache / after an orbit | 2.3 / 135 | 2.2 / **63** | the rebuild |
| direct: cache rebuild | 137 | **58** | projector |
| plain W 36 / 112 / 500 V, `move` p50 / p95 | 13.8/14.8 · 16.6/18.3 · 22.4/31.6 | **2.8/3.0 · 4.0/6.6** · 11.9/19.8 | no `recompute_bounds` per move (8.6 ms on its own); 500 V stays over 8 ms (`store.update`) |
| soft W 15 % / 50 % geodesic, `move` p50 / p95 | 28.7/40.8 · 93/129 | 12.3/19.1 · 77/122 | bounds; the rest is per-vertex `store.update` |
| soft drag commit frame 15 % / 50 % | 1 734 / 1 375 | **233 / 353** | the re-pick after release |
| event loop, hover (real wiring) | 2.4 events/s, longest gap 819 ms | **19 events/s, 118 ms** | |
| event loop, zoom | 2.0 notches/s, 472 ms each, gap 615 | **9.5/s, 85 ms each, gap 138** | |

Head and body (all rows were under a frame before; selected): body zoom 9.3 → 3.9, first hover 10.7 → 4.5, click 4.6
→ 1.9, Paint step 6.5 → 1.5, plain W 500 V 18.9/21.3 → 9.8/15.4; head zoom 4.9 → 3.0, Paint 2.5 → 0.8. Box face rows
unchanged, Box vertex rows ~1.6-1.8x faster.

`gollum.obj` (87 500 V, Reference-mesh stress case): zoom 2 505 (4 829) → **354 (565)**, first hover 1 086 → **333**,
click 874 → **84**, hover move p95 3 614 → **103** (p50 45 → 72 is not like-for-like: the before row's cursor sat over
an unchanged hover on most moves, `hover changed 6/19` vs `27/40` after, so the after p50 includes the hover's sync +
draw; the rows before it ran a different number of budgeted orbit gestures).

**Reading.** On `gollum_20k` hover, click, Knife hover and Paint are now one or two occlusion tests instead of
16-325; what is left of a pick is the O(F) face loop of that test (~5 ms) and the O(V) scan. The camera-dependent
rebuild halved (not 5x as in the W4 what-if: the projection itself is now small, the unchanged O(F) face bboxes are most of the rebuild in the profile). So after an orbit or
a zoom notch the first pick still costs ~60-85 ms on 21.9k and ~300 ms on 87.5k - that is option 5 (coalescing) plus
a camera-independent index, as predicted. Box Select stays unusable from ~15k V (1.4-20 s): it still runs one full
occlusion test per element (Slice 2: batched visibility). W drags of small selections are under the 8 ms bar on 21.9k
now; large ones are bounded by the per-vertex `store.update` (Slice 2+). Reference-PC numbers decide (Manu's run
below); the `math.hypot` effect (option 1) is invisible here by construction.

### Praktischer Test für Manu (Slice 1, ca. 15 Minuten)

Annahme: Es soll sich **nichts anders anfühlen** - nur schneller. Wenn sich irgendwo eine Auswahl, ein Hover oder ein
Knife-Punkt anders verhält als vorher, ist das ein Fehler (bitte melden, mit Asset und Modus).

1. `git pull`
2. Messung (öffnet kein Fenster, 5-10 Minuten): `python experiments/drag_cost/probe_navigation_gl.py` - die ganze Ausgabe
   (ab `Navigation and picking cost ...`) in den Chat kopieren.
3. Dann die 87.5k-Variante (kurz): `python experiments/drag_cost/probe_navigation_gl.py --assets examples/meshes/gollum.obj --scenarios zoom first_hover hover_move select_click --profile-top 0` - Ausgabe ebenfalls kopieren.
4. Im Fenster: `python src/main.py examples/meshes/gollum_20k.obj` (danach dasselbe kurz mit `examples/meshes/gollum.obj`):
   a. **Hover**: Vertex-, Edge- und Face-Modus, mit der Maus über das Gesicht fahren, auch an der Silhouette - der
      Hover springt auf dieselben Elemente wie vorher, verdeckte Rückseiten-Vertices werden in Shaded nicht gehovert.
   b. **Klick + Zoom**: ein paar Vertices anklicken, dann mit dem Mausrad zoomen und direkt wieder hovern - fühlt es
      sich flüssiger an? (Erwartung Container: Hover/Klick deutlich; Zoom besser, aber noch nicht frei.)
   c. **Box/Paint**: Box-Auswahl über eine kleine Fläche und Paint-Auswahl über das Gesicht - gleiche Auswahl wie
      gewohnt (Box ist auf gollum weiterhin langsam, das ist der nächste Slice).
   d. **Knife**: eine Knife-Linie über Kanten und eine Fläche ziehen - die Punkte rasten an denselben Stellen ein.
5. Verdikt in einem Satz: „fühlt sich gleich an, nur schneller“ - oder was anders ist.

Manu: Fühlt sich gleich an, nur schneller.Im Vergleich zu Blender auf meinem PC aber noch wesentlich langsamer.
Dort lässt sich 20k Gollum sehr flüssig zoomen, Komponenten picken oder Topologie Operationen ausführen. 

## Result: fix slice 2, container, before → after (WP-VIEW-PERF-01, 2026-10-17)

Production, behaviour-neutral except one Artist check (hover may appear one frame later). Built: (1) **Box Select
batched visibility**: `PickCache.face_grid` buckets the cached face screen bboxes into 16 px cells over the
viewport; the occlusion test (`picking._occluded`, behind `point_occluded` / `vertex_occluded` /
`edge_point_occluded`) visits only the faces of its point's cell, and `elements_in_rect` runs all its tests through
one `point_occlusion_test` (eye + projection once). The grid is camera-dependent like the bboxes (the "simple CPU
spatial grid" of `VIEWPORT_V02` §4.6, updated there), built at most once per camera state: at once for a Box, after
`GRID_AFTER_SCANS` = 8 full scans for single tests (hover, click, Knife, Paint), so the first pick after a camera
change does not pay for it. Build cost (container, framed, 1024x768): head 0.6 / body 0.8 / gollum_20k **10.9** /
87.5k 30 ms, i.e. +19 % on top of the 58.6 / 154 ms rebuild, only when a Box or a 9th test needs it.
(2) **Hover coalescing** (option 5): `Application.coalesce_hover` (switched on by `src/main.py run`, off for headless
callers): a plain mouse move or a wheel notch marks the hover stale, the frame tick (`update_viewport` →
`flush_hover`) picks once at the latest cursor; `key_press`, `pointer_press` and `dispatch_command` flush first, so a
key or click that reads the hover sees the current one. Click, Box, Paint samples and the Knife hover are not
coalesced (picked synchronously as before).

**Same results.** `tests/test_picking_equivalence.py` now also keeps `point_occluded` (65e30ae) and
`elements_in_rect` (aa1f10b) verbatim: Box vertex/edge/face on head and body, front and back camera, four boxes
(incl. the whole view and one sticking out of the window), Shaded and Wireframe; a seeded `gollum_20k` 60 px box in
all three modes; every vertex, every third edge midpoint and face centroid of head/body through the grid against the
full scan; the Slice-1 cursor sweeps with the grid built; a hidden vertex behind an occluder whose bbox corner lies in
another cell (a corner-only grid would pick it); grid borders, clamping, faces without a bbox. The probe's Box rows
select the same counts before and after (180 / 860 / 1 900 vertices, 324 / 1 627 / 3 683 edges, 145 / 774 / 1 793
faces on gollum_20k). `tests/test_application_hover_coalescing.py` drives two apps (coalescing / not) with the same
input and compares hover, selection and Knife preview after every tick: moves and zoom bursts in all three modes, a
click and a W arm right after a move (no tick between), Paint and Box, orbit, leaving the window, a Knife session.

**Container numbers, not the reference PC** (`REFERENCE_HARDWARE.md` §4): Intel Xeon @ 2.10 GHz, 4 cores, Python
3.13.16, llvmpipe (`draw` = CPU raster) - another container than Slice 1's (2.80 GHz), so compare within this table
only. Same probe, same container, one after the other, nothing else running: before = `fc97db5` (Slice 1) + this
probe, after = this commit. `python experiments/drag_cost/probe_navigation_gl.py --scenarios zoom first_hover
hover_move select_click direct topology loop --profile-top 0`, then `--scenarios zoom_burst loop` on body /
gollum_20k / 87.5k and the 87.5k subset `--assets examples/meshes/gollum.obj --scenarios zoom first_hover hover_move
select_click loop`. ms p50 (p95); one 60 Hz frame = 16.7 ms.

| Row (`gollum_20k`, 21 875 V) | before | after | what moved |
|---|---:|---:|---|
| Box 60 / 150 / 300 px, vertex | 1 470 / 6 132 / 19 006 | **43 / 134 / 312** | 724 / 2 709 / 6 977 tests, each ~0.05 instead of ~2 ms |
| Box 60 / 150 / 300 px, edge | 2 485 / 11 888 / 35 579 | **93 / 282 / 623** | 1 358 / 5 309 / 13 803 tests |
| Box 60 / 150 / 300 px, face | 1 300 / 5 868 / 17 490 | **64 / 166 / 367** | 634 / 2 599 / 6 825 tests |
| Paint, one 30 px step (5 picks) | 32.6 | **14.2** | the 5 tests go through the grid (built after 8 scans) |
| hover move, frame (event) | 13.6 (6.1) | 14.0 (**3.9**) | occlusion 3.5 → 0.12 ms; the frame is llvmpipe draw + sync |
| selection click, frame (event) | 15.3 (6.6) | 11.5 (**3.1**) | occlusion 3.6 → 0.05 ms |
| direct: hover vertex / edge / Knife hover | 5.1 / 14.1 / 7.1 | 4.8 / 10.2 / 3.4 | what is left is the O(V) / O(E) scan |
| zoom notch, frame | 61.7 (82.9) | 69.6 (107) | unchanged by design: rebuild 44-52 ms + 2.5 tests, no grid for 2-3 tests |
| first hover after an orbit, frame | 68.9 (124) | 67.3 (98) | unchanged by design: rebuild ~48-51 ms + 1 test |
| zoom burst, 4 notches then 1 frame | 238 (331) | **68 (97)** | 4 picks + 4 rebuilds → 1 + 1 (coalescing) |
| event loop, hover (real wiring) | 38 events/s handled, 38 frames/s, longest gap 156 ms | 54/s, 54 frames/s, 121 ms | the pick moved from the events (11.7 ms each) into the tick |
| event loop, zoom | 12.3 notches/s, 12 frames/s, gap 137 | 9.9 notches/s, **17.4 frames/s**, gap 140 | see note |
| cache rebuild (`refresh`) | 45 | 38 | unchanged code; noise |

Event-loop note: the probe's injector fires at most once per loop iteration, so it never delivers a burst; a real
wheel or touchpad queues several events per frame, which is what `zoom_burst` shows. A second after-run of the loop
gave hover 45 frames/s / gap 68 ms and zoom 23 frames/s / gap 110 ms - one 2 s sample per phase, read as a direction.

Head and body (everything was under a frame before; selected): body Box 300 px vertex / edge / face 34.9 / 66.1 /
34.4 → 3.7 / 9.8 / 5.5, Paint 1.3 → 0.6, zoom burst 8.7 → 4.3; head Box 300 px 14 / 31 / 14 → 4.0 / 8.1 / 5.7; zoom,
first hover, hover and click unchanged (< 4 ms).

`gollum.obj` (87 500 V, Reference-mesh stress case): hover move event 26.6 → **11.3** (occlusion 15.5 → 0.15 ms),
click event 25.5 → **10.8**, zoom burst (4 notches) 832 → **249**, zoom notch 259 → 227 and first hover 230 → 239
(the 154-190 ms rebuild, unchanged), loop hover 13 → 17 frames/s; loop zoom 3.6-3.9 → 3.9-4.8 frames/s with the
longest gap 343-367 → 429-557 ms (one 2 s sample each, dominated by the per-frame rebuild; no improvement claimed).

### Topology ops on the current architecture (Slice 2 step 0, measurement only)

`--scenarios topology`: one op as the Artist triggers it (keys + pointer through `Application`), camera framed close
on the front-most vertex, undone after each sample. Container, after = before within noise (no topology code
changed), so one set of numbers (after run), ms p50:

| Op (`gollum_20k`) | frame(s) total | op | history | hover re-pick | viewport sync | undo frame | dominant |
|---|---:|---:|---:|---:|---:|---:|---|
| Extrude 1 face (T, 2 moves, release) | 1 273 | 0.6 | 388 | 51 | 864 (3 syncs) | 956 | sync, then history |
| Extrude 20 faces | 1 834 | 22 | 889 | 49 | 917 (3 syncs) | 1 008 | history ≈ sync |
| Knife commit (1 cut, 3 edges) | 1 188 | 74 | 627 | 99 | 376 | 1 184 | history |
| Dissolve 1 edge (Backspace) | 781 | 11 | 313 | 85 | 361 | 1 000 | sync ≈ history |
| Delete 1 face (Delete) | 792 | 13 | 336 | 50 | 381 | 927 | sync ≈ history |

Body (928 V): every op 26-57 ms (history 6-15, sync 15-32 ms); head 10-25 ms. What the columns are: `history` = the
two whole-mesh `Mesh.export_state()` snapshots of `MeshStateCommand` (before / after, `src/core/operations/
topology.py`: full snapshots by design, AD-001 ID continuity) plus `history.push`; `viewport sync` = `RenderMesh.
_sync_topology` (re-triangulating every face 0.36 s in the profile, all normals 0.23 s, all GPU buffers 0.28 s -
`VIEWPORT_V02` §5.4 "structural rebuild"); `hover re-pick` = the `PickCache` rebuild (~48 ms) plus an O(E) edge scan
where the residue is in Edge mode; undo = `load_state` + the same full rebuild. The operation itself is 1-74 ms.
**Picking is not what makes a topology op slow on 21.9k: it is 5-10 % of it.** (`vertex_faces` is 0 here: the
close-up has no vertex within 14 px of the cursor, so no occlusion test ran.)

### Haltepunkt: what Blender-level fluidity on 20k would need (decision note for Manu + review, 2026-10-17)

Manu's verdict on Slice 1: "Fühlt sich gleich an, nur schneller. Im Vergleich zu Blender auf meinem PC aber noch
wesentlich langsamer. Dort lässt sich 20k Gollum sehr flüssig zoomen, Komponenten picken oder Topologie-Operationen
ausführen." After Slice 2 (container, gollum_20k; reference PC ~2x slower for this Python code, `README` above) the
remaining cost per interaction is one of three things, none of which another local picking fix removes:

| Interaction | container now | what it is | grows with |
|---|---|---|---|
| zoom notch, first hover after orbit/pan | ~60-70 ms per frame | `PickCache.refresh`: project all V + all F bboxes, per camera state | V + F, every camera change |
| hover move, click | ~3-4 ms event | O(V) / O(E) scan + 1 grid test | V, E |
| Box 300 px | 0.3-0.6 s | one grid test per element | elements in the box |
| topology op | 0.8-1.8 s + ~1 s per undo | 2 whole-mesh snapshots + full viewport rebuild | V + F, every op |

Options (cost / risk / what they touch; numbers are container estimates from the measurements above and the
2026-10-17 audit):

1. **Camera-independent world index** (option 9: BVH or uniform grid over triangles in object space, built once per
   mesh state). Face pick / occlusion become ray queries (~0.06 ms measured for a pure-Python BVH query, audit), so
   the per-camera O(F) bbox work disappears; vertex/edge "nearest within 14 px" needs a cone/frustum query over node
   bounds (not built yet, not measured). Cost: build 0.65 s on 21.9k / 3.2 s on 87.5k in pure Python (audit) after
   **every topology op** and a refit after every W drag - unless kept incremental, it moves the cost from zoom to
   editing. Risk: medium (two picking paths until the screen-space one goes; equivalence is testable on the CPU,
   headless). Touches: `VIEWPORT_V02` §1 non-goals ("BVH / Octree / KD-tree") and §4.6 "Do NOT build", §11; also
   serves the retopology snapping case (audit). No AD-018 change.
2. **GPU ID-buffer picking** (option 10: render face / edge / vertex IDs into an offscreen buffer, `glReadPixels` a
   small window under the cursor or the Box rectangle). Per pick one extra draw (the 9800 GTX draws 44k triangles in
   0.56 ms) plus a read-back stall, independent of V in Python; occlusion comes from the depth buffer, so hover after
   zoom and Box would be near frame-free. Cost: a second program and an FBO in `GLRenderStore`, ID encoding, a CPU
   fallback for the headless tests (TraceStore has no GL) - so two pickers. Risk: high - the depth-buffer answer is
   not `DEPTH_TOLERANCE` (silhouette / coplanar cases change: an Artist check, no bit-equivalence), sub-pixel
   elements vanish from a Box, and `gl_PrimitiveID` reliability on the reference driver is open (`REFERENCE_HARDWARE`
   §2; the Flat shading since 2026-10-15 uses it, so Manu's window is evidence). Touches: `VIEWPORT_V02` §1 non-goals
   ("GPU ID-buffer picking / glReadPixels") and §4.6, **AD-018** (the draw binding / `ResourceStore` contract gets a
   pass that is not the mesh draw), `REFERENCE_HARDWARE` §4 (GL 3.3 is enough; driver behaviour is the risk).
3. **Incremental topology sync and history** (new, from the topology rows). The 0.8-1.8 s per op is snapshots +
   full rebuild, not picking: a delta history entry (only the touched elements, plus ID-counter state) instead of two
   `export_state` copies, and an `update_topology` that re-triangulates / re-normals / re-uploads only the touched
   faces (index buffer patch when the count fits, full rebuild otherwise). Expected: ops and undo from ~1 s to tens of
   ms on 21.9k (estimate, not measured). Risk: high for history (ID continuity, AD-001; the symmetric history contract,
   AD-SYM-02; a wrong delta corrupts undo), medium for the viewport (equivalence against the full rebuild is testable
   headless). Touches: `src/core` (`MeshStateCommand` / `HistoryStack` are frozen, `CORE_V1_FREEZE.md`) or a
   `mirai`-level delta command with the core contract unchanged - to be decided; `VIEWPORT_V02` §5.4 ("structural
   rebuild is appropriate") and §4.5 (adjacency rebuilt per topology change); AD-018 only if buffers are patched
   rather than re-created.

Engineering reading (`PROVISIONAL`, not a decision): the three are independent and answer different parts of the
verdict - zoom/first-hover fluidity needs 1 or 2 (the rebuild is camera-dependent by construction), topology-op
fluidity needs 3 whatever picking does. 3 has the largest measured cost (about a second per op and per undo, ~15x a zoom frame), 2 the
largest picking gain at the highest compatibility risk on the reference PC. Evidence that would sharpen the choice:
the reference-PC run of this slice (below), and whether `gl_PrimitiveID` flat shading looks right on Manu's PC. Which
of the three, in what order, and which document clauses change is Manu's decision plus a review (AGENTS.md §5); no
code until then.

### Praktischer Test für Manu (Slice 2, ca. 15 Minuten)

Annahme: Box-Auswahl, Hover, Klick, Paint und Knife wählen **dieselben** Elemente wie bisher - nur schneller; einzige
gewollte Änderung: der Hover nach einer Mausbewegung oder einer Mausrad-Raste kann **einen Frame später** erscheinen
(er wird einmal pro Frame statt pro Ereignis berechnet). Weicht irgendwo eine Auswahl ab, ist das ein Fehler (bitte mit
Asset und Modus melden).

1. `git pull`
2. Messung (öffnet kein Fenster, ~10 Minuten): `python experiments/drag_cost/probe_navigation_gl.py --assets examples/meshes/gollum_20k.obj --scenarios zoom zoom_burst first_hover hover_move select_click direct topology loop --profile-top 0` -
   **bitte die ganze Ausgabe** (ab `Navigation and picking cost ...`) in den Chat kopieren.
3. Kurzvariante 87.5k: `python experiments/drag_cost/probe_navigation_gl.py --assets examples/meshes/gollum.obj --scenarios zoom_burst first_hover hover_move select_click loop --profile-top 0` - Ausgabe ebenfalls kopieren.
4. Im Fenster: `python src/main.py examples/meshes/gollum_20k.obj`
   a. **Box** (LMB-Ziehen im Leeren) in Vertex-, Edge- und Face-Modus (`1`/`2`/`3`), klein und groß, auch über die
      Silhouette - dieselbe Auswahl wie gewohnt, Rückseiten in Shaded nicht mit ausgewählt; sollte jetzt in
      Sekundenbruchteilen statt Sekunden kommen.
   b. **Hover nach Zoom**: Maus ruhig auf dem Gesicht lassen, schnell mehrere Rasten zoomen - der Hover springt danach
      auf das Element unter dem Cursor (ggf. einen Frame später); fühlt sich das Zoomen weniger zäh an?
   c. **Paint** (LMB-Ziehen auf dem Mesh) übers Gesicht - keine Lücken, gleiche Auswahl wie gewohnt.
   d. **Knife** (`C` ohne Auswahl): Linie über Kanten und eine Fläche - die Punkte rasten an denselben Stellen ein.
   e. Einmal Extrude (`T`), Delete und Undo auf gollum_20k: das ist weiterhin langsam (~1 s) - die Messung oben zeigt,
      warum (Snapshots + kompletter Viewport-Neuaufbau, nicht das Picking).
5. Verdikt in einem Satz („gleich, nur schneller“ - oder was anders ist), und zur Architekturfrage oben
   („Haltepunkt“): welche der drei Richtungen (Welt-Index / GPU-Picking / inkrementelle Topologie) dir am wichtigsten
   ist - Zoomen, Picken oder Topologie-Operationen.

## Next step

The reference-PC numbers are in `REFERENCE_HARDWARE.md` §2 and above; the 8 ms bar holds and S2c ran (verdict: AD-020
"S2c verdict"). A larger radius (S2d: up to 200 %) can be measured with `--scenarios soft_w --sizes 100 200`.

Navigation (WP-VIEW-PERF-01): reference-PC run 2026-10-11 (on `gollum_20k.obj`, see the audit above) and the audit at HEAD
2026-10-17 are in; fix slices 1 and 2 are built (container before/after above; Manu's Slice-1 verdict: same, faster,
still far slower than Blender). Next: Manu's reference-PC run and window check ("Praktischer Test ... Slice 2"), then
the architecture decision in "Haltepunkt: what Blender-level fluidity on 20k would need" (world index / GPU picking /
incremental topology sync) - Manu + review, no code before it. Left inside the current architecture: option 8 (dead
`highlight_flags`) and batched `store.update` for large Soft drags.
