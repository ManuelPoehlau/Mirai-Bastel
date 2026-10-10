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
| `probe_drag_gl.py` | CLI probe: hidden pyglet window, `GL_TYPES` from `src/main.py`, one function per scenario (`SCENARIOS`; S2b adds a soft drag as another entry) |
| `_paths.py` | sys.path bootstrap (pattern copied from `soft_selection/_paths.py`) |
| `tests/` | headless tests: argument handling, statistics, import boundary (no pyglet, no window) |

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

## Run

From the repo root (Windows command prompt / PowerShell and Linux alike; Linux headless: `xvfb-run -a`):

```
python experiments/drag_cost/probe_drag_gl.py
python experiments/drag_cost/probe_drag_gl.py --assets head_basemesh --sizes 9 36
python experiments/drag_cost/probe_drag_gl.py --moves 400
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

Reference PC: not measured yet — see "Praktischer Test für Manu".

## Praktischer Test für Manu (ca. 5 Minuten)

1. `git pull`
2. `python src/main.py examples/meshes/Man_With_Shoes_basemesh.obj` — eine große Fläche auswählen
   (z. B. halber Oberkörper), W halten und ziehen. Soll sich flüssig anfühlen; Aussehen unverändert.
3. Kopf (`python src/main.py`): kurz W/E/R und Undo — alles wie gewohnt.
4. `python experiments/drag_cost/probe_drag_gl.py` ausführen und die Tabelle in den Chat kopieren.

## Next step

Numbers from the reference PC go into the table above and into `REFERENCE_HARDWARE.md` §2. S2b extends
the probe with a soft-drag scenario (one more entry in `SCENARIOS`).
