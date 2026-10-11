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
| `probe_navigation_gl.py` | CLI probe (WP-VIEW-PERF-01): orbit, pan, zoom, first hover after a camera change, hover move, selection click, orbit with wire, the real event loop, plain/soft W - per event + frame on head, body and `gollum.obj`; see "Navigation and picking" below |
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

Assets: head and body by registry name, gollum by path (`--assets` takes registry names or `.obj` paths). gollum is **not**
registered in `examples/loaders/assets.py`: an entry there is a 7-line `ObjAsset(...)` block, not a one-line change, and the
probe does not need it (E3). It is a small follow-up if the SPACE menu should list it.

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
| H5 | the draw itself is significant on the 9800 GTX | **Open (reference PC)** | indexed buffer (`vertex_list_indexed`, not de-indexed - that part is rejected from the code); 43 750 triangles. llvmpipe CPU raster: 6.8 ms mesh, 19.4 ms with wire. The `gpu` column on the reference PC decides; a 2008 GPU draws this triangle count in well under a frame (estimate, not measured) |
| - | **found:** occlusion test cost (O(F) face loop + O(E) `vertex_edges` per hidden candidate) | **New, dominant** | see above; 30-91 tests per pick on gollum |
| - | **found:** `RenderMesh._sync_geometry` recomputes the bounds over **all** vertices on every W move | **New** | gollum plain W 36 V: sync 10.6 ms, `store.update` 0.4 ms; profiled: `recompute_bounds` ~85 % of `sync`. Nothing in `src/` reads the bounds; `VIEWPORT_V02_ARCHITECTURE.md` §7 already asks for "affected vertices only" |
| - | **found:** the commit frame of a W drag on gollum is 2-2.7 s | **New** | `key_release` → `_refresh_hover` → cache rebuild + occlusion (184 tests in one profiled commit) |

**What this means for "Orbit and Pan lag":** in the container the orbit/pan step itself is cheap on gollum (event 0.03 ms,
no pick, no upload, 59 frames/s in the real loop). The lag the Artist sees is most likely the picking **around** the
gesture: every mouse move before pressing Alt+LMB is a 0.2-1 s pick, the press waits behind the pick that is running, and
the first move after releasing (and after every zoom notch) rebuilds the cache and picks again (0.3 s). This is a reading
from container numbers; the reference PC's `orbit` row (`gpu`, `draw`) confirms or rejects it. Rough scale to the
reference PC: body plain W 112 V was 5.29 ms p50 there vs 1.64-2.50 ms in containers (2026-10-10/11), i.e. ~2-3x - so
expect roughly 0.4-0.6 s per hover pick (p95 2-3 s) and ~2 s per zoom notch on gollum (estimate, not measured).

### Fix options (ranked by gain / cost; none implemented)

Gains are container estimates for gollum, to be confirmed by re-running this probe after a fix.

| Rank | Option | Where | Expected gain (gollum, container) | Cost / risk |
|---:|---|---|---|---|
| 1 | **Fewer occlusion tests:** test candidates nearest-first and stop at the first visible one (sort the ≤ 14 px candidates by screen distance) instead of testing every closer hidden vertex in mesh order. Same result by construction (the nearest visible vertex) | `mirai/viewport/picking.py` (`pick_nearest_vertex`, same for edges) | 30-91 → ~1-5 tests per pick: hover move 183 → ~15-40 ms, click 233 → ~20-40 ms, zoom 813 → ~200-250 ms | small; identical picks (existing B8 tests + a "hidden vertex closer in mesh order" test) |
| 2 | **Cheaper occlusion test:** vertex → incident-faces map built once per mesh state in `PickCache` (replaces `core.Mesh.vertex_edges`, an O(E) scan) | `picking_cache.py` / `picking.py` | ~40 % off each test (~2.5 of ~6.5 ms) | small; the cache already has the right invalidation points. Changing `vertex_edges` in `src/core` instead is frozen-core work (AD needed) and not recommended for this reason |
| 3 | **Cheaper cache rebuild:** compute eye/basis/aspect once per refresh and project inline, instead of `camera.project_to_screen` per vertex (which recomputes them for every vertex) | `picking_cache.py` (maybe a `camera.projector()` helper) | rebuild 178-188 → ~90 ms (estimate ~2x: the per-vertex `eye`/`basis` calls are ~50 % of the profiled rebuild; same values) | small; numerically identical if the same formula is used |
| 4 | **Coalesce picking to once per frame:** a zoom notch / camera change / motion marks hover stale; the tick picks once at the latest cursor | `application.py` (`pointer_scroll`, `_refresh_hover`, `update_viewport`), `src/main.py` untouched | a burst of N wheel notches costs 1 pick, not N; motion never blocks more than one pick per frame | small-medium; behaviour: hover appears one frame later (Artist-visible? probably not); needs care with the click path, which must stay synchronous |
| 5 | **Lazy / affected-only bounds** in `RenderMesh._sync_geometry` | `src/viewport/render_mesh.py`, `derived.py` | ~9 ms less `sync` per W move on gollum (plain W 36 V: 10.8 → ~2 ms p50; 500 V stays over 8 ms because of the per-vertex `store.update` calls) | small; touches a documented counter (`bounds_recalculations`, `tests/test_render_mesh.py`); `VIEWPORT_V02_ARCHITECTURE.md` §7 already describes this |
| 6 | Face screen-space grid in `PickCache` (bucket face bboxes) so the occlusion test visits only faces under the pixel | `picking_cache.py` / `picking.py` | the O(F) loop per test → O(faces in the cell); with 1-3 rows above, a further ~2x per test | medium (new structure, built per rebuild: adds to the rebuild cost) |
| 7 | Drop the dead `highlight_flags` rebuild (B2b follow-up cleanup) | `render_mesh.py`, `overlay.py`, `gl_render_store.py` | ~3 ms sync + 85 KB upload per hover/selection change | small-medium; part of a documented cleanup, separate decision |
| 8 | World-space spatial index (grid/BVH) for vertices and faces, camera-independent: no rebuild on orbit/zoom at all | new module in `mirai/viewport/` | cache rebuild → 0 per camera change; pick O(cells along the ray) | medium-high; invalidation on every mesh edit; only worth it if 1-4 are not enough |
| 9 | GPU picking (ID buffer + `glReadPixels`, depth = occlusion for free) | Viewport + `mirai` | pick ~O(1) CPU at any mesh size | high: an extra render pass and a Viewport service for `mirai` (architecture change, AD-018 scope); not recommended before 1-4 are measured |
| - | LOD / decimated display mesh | renderer | - | **not recommended** because the draw is not the measured cost (orbit event 0.03 ms, no upload) and H5 is open; it would add a second geometry path for no shown gain |
| - | NumPy vectorisation of projection / occlusion | `mirai/viewport` | large (estimate) | **not recommended now** because it adds a new runtime dependency and a CPU-baseline risk on the Core 2 (no SSE4.2, `REFERENCE_HARDWARE.md` §4: newer instruction sets are a reported conflict); pure-Python 1-4 come first |

Recommended first slice (engineering proposal): 1 + 2 + 3 together (all inside `mirai/viewport` picking, no behaviour
change, no architecture change), then re-run this probe; 4 and 5 as the next slice if the reference PC still lags. Which
mesh size must stay fluid is the Artist's Intent question (handoff §7) - the numbers above are what that answer costs.

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

## Next step

The reference-PC numbers are in `REFERENCE_HARDWARE.md` §2 and above; the 8 ms bar holds and S2c ran (verdict: AD-020
"S2c verdict"). A larger radius (S2d: up to 200 %) can be measured with `--scenarios soft_w --sizes 100 200`.

Navigation (WP-VIEW-PERF-01): Manu runs `probe_navigation_gl.py` on the reference PC (H5 and the scale factor), then
answers which mesh size must stay fluid; the fix slice (options 1-3 above, then 4-5) follows that answer.
