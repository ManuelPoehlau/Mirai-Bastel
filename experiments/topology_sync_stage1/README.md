# AD-023 stage 1 as an experiment (V0 + V2 + V3 + H0)

> Prototype of stage 1 of [AD-023](../../docs/architecture/AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) §7 after Manu's
> answers of 2026-10-20 (AD-023 §6: Undo as fast as the operation; stage 1 first). **Not production code, not a decision,
> not Artist-validated.** Nothing under `src/` is changed: `stage1.py` replaces a few methods of `RenderMesh` and
> `Application` from the outside. No Core change (CORE_V1_FREEZE untouched).
> Basis: [drag_cost README](../drag_cost/README.md) (topology rows on the reference PC), the split probe in
> [`architecture_audit_probes/`](../architecture_audit_probes/README.md), [REFERENCE_HARDWARE](../../docs/architecture/REFERENCE_HARDWARE.md).

## What is built

| Switch | AD-023 | What it does |
|---|---|---|
| `V3` | V3 | Flattening of positions / normals / indices without the per-rebuild sort, one comprehension per buffer. |
| `V0` | V0 | Per-face cache of boundary + triangles and per-vertex positions of the last topology sync: only new faces, faces with a changed boundary and faces with a moved vertex are re-triangulated and get a new normal; vertex normals and adjacency only around them; face-data rows reused. W-drag moves between two syncs are recorded (`_sync_geometry` wrapper), because a W drag does not re-triangulate (AD-023 V0 "cache key"). Buffers are still rebuilt whole. |
| `V2` | V2 (+ U side effect) | If vertex list, face list, every boundary and every triangulation are unchanged since the last sync, the topology sync only patches the moved vertices (the `_sync_geometry` path) instead of recreating the buffers: Extrude's release rebuild becomes a patch, and so does the Undo / Redo of a positions-only step. Above 2 000 moved vertices it rebuilds whole (`PROVISIONAL`). Needs `V0`. |
| `H0` | H0 | `Application._mesh_transaction` (Delete, Dissolve, Connect, Split, `apply_mesh_change`) pushes a command without the after-snapshot; "changed?" from the element counts, with today's full comparison as the fallback when the counts are equal (exact). The after-state is exported at the first Undo, so **Undo pays that export**. Extrude and Knife build their own commands and are not covered. |

`all` = `V0,V2,V3,H0`; `none` = today's code.

Equivalence (`tests/`): after every step (initial build, Delete, Dissolve, a positions-only change, Extrude T + moves +
release, rotated boundaries with unchanged IDs, each with Undo / Redo) the patched `RenderMesh` holds what a fresh one
built with the original code holds (index map, triangles, face rows, adjacency, all buffers; normals within 1e-9,
because a vertex normal sums over a `set` whose order can differ), for five switch combinations; Undo / Redo restore the
exact `export_state()`. `test_gl_image.py` draws the same steps with `none` and `all` through `GLRenderStore` and compares
the pixels (llvmpipe). Mutation checks done once by hand: dropping the W-drag record, the face-row invalidation, the
"boundary changed" flag or the V2 position patch each makes at least one test fail.

## Run

```bash
python experiments/topology_sync_stage1/probe_stage1.py --stage1 none --steps 20 --row-seconds 240   # baseline
python experiments/topology_sync_stage1/probe_stage1.py --stage1 all  --steps 20 --row-seconds 240
python experiments/topology_sync_stage1/probe_stage1.py --stage1 V0,V2,V3 --steps 20 --row-seconds 240  # without H0
python experiments/topology_sync_stage1/run.py [asset] [--stage1 none|all|V0,V2,V3]                    # the app
xvfb-run -a python -m pytest experiments/topology_sync_stage1/tests -q                                   # headless
```

The probe prints p50 / p95 / max per column (the drag_cost report prints p50 and max; p95 equals max below n = 20), the
split table of the split probe and the stage-1 counters. Options `--gc`, `--history-depth`, `--assets` are passed on.

## Result: container, 2026-10-20 [C] (not the reference PC)

Xeon @ 2.80 GHz, Python 3.13.16, llvmpipe; `gollum_20k`, `--gc off` (the container's GC distorts the history column, which
the reference PC does not show at the median), `--steps 10`, n = 10 per row. ms, p50 (p95):

| Op | frame `none` | frame `V0,V2,V3` | frame `all` | undo `none` | undo `V0,V2,V3` | undo `all` | op + undo `none` → `all` |
|---|---:|---:|---:|---:|---:|---:|---:|
| Extrude 1 face | 1 047 (1 350) | 399 (635) | 424 (498) | 590 | 307 | 329 | 1 662 → 769 |
| Extrude 20 faces | 1 282 (1 731) | 526 (582) | 631 (753) | 603 | 298 | 316 | 1 905 → 982 |
| Knife commit | 913 (1 028) | 588 (774) | 570 (646) | 714 | 381 | 402 | 1 662 → 1 011 |
| Dissolve 1 edge | 691 (825) | 371 (406) | 351 (462) | 690 | 368 | 421 | 1 419 → 783 |
| Delete 1 face | 646 (801) | 323 (383) | 275 (347) | 635 | 347 | 378 | 1 281 → 693 |

One structural sync: 454 → 114 ms (4x). Of the remaining ~110 ms per full sync, ~65 ms are `GLRenderStore` (`update`
~31, VertexList creation ~32: the whole-buffer copy and the pyglet VertexList, i.e. what V1 would patch) and ~40 ms the
Python flattening; the V0 detection pass over all faces is a few ms. Extrude now rebuilds once per gesture (the release is
a V2 patch: 101 full rebuilds and 26 patch syncs over the run). H0 shifts one `export_state` from the op into the Undo: the
op frame of Delete / Dissolve drops by ~40-50 ms, the Undo rises by ~30-50 ms, op + Undo is unchanged within noise. The
memory side (one snapshot per entry instead of two until it is undone, ~31 MB less per step at 21.9k [C]) is not measured
here. Raw outputs, also two runs with the GC on: [`RESULTS_CONTAINER_2026-10-20.md`](RESULTS_CONTAINER_2026-10-20.md).

Reading (agent, `PROVISIONAL`, a hypothesis for the reference PC): at about 2x the container (REFERENCE_HARDWARE §2,
drag_cost "Correction") stage 1 would bring a Delete from ~1.6 s to roughly 0.6-0.8 s and its Undo from ~1.6 s to roughly
0.7-0.8 s; still a visible delay. What remains per op: the history snapshots (Knife and Extrude 20 keep both), the hover
re-pick (`PickCache` rebuild, AD-022), the whole-buffer upload (V1); per Undo: `load_state` (H1) + the upload. That is
stage 2 of AD-023 §7 plus AD-022; whether it is needed is Manu's feel test below and the reference-PC run.

## Result: reference PC

Not run yet (see below).

## Praktischer Test für Manu (ca. 15 Minuten + 3 Messläufe)

**Fühlen (das entscheidet):** `python experiments/topology_sync_stage1/run.py` öffnet die normale App mit gollum_20k und
Stufe 1 (Fenstertitel: „AD-023 Stufe 1: H0,V0,V2,V3“). Mach dort, was du sonst machst: Extrude (`T`), Knife (`C`),
Connect, Delete, Dissolve, mehrmals Undo/Redo, auch nach einem W-Move. Zum Vergleich einmal
`python experiments/topology_sync_stage1/run.py --stage1 none` (heutiger Code, gleiche App).

**Messen (PowerShell im Repo-Ordner, je ca. 5-10 Minuten, jeweils die ganze Ausgabe kopieren):**

1. `python experiments\topology_sync_stage1\probe_stage1.py --stage1 none --steps 20 --row-seconds 240`
2. `python experiments\topology_sync_stage1\probe_stage1.py --stage1 all --steps 20 --row-seconds 240`
3. Unter Python 3.12.10 (dein PyCharm-Interpreter, z. B. die venv `.venv_np312`): einmal `.venv_np312\Scripts\pip install pyglet`,
   dann `.venv_np312\Scripts\python experiments\topology_sync_stage1\probe_stage1.py --stage1 all --steps 20 --row-seconds 240`.

| Frage | Dein Verdikt |
|---|---|
| Fühlen sich Operation und Undo auf gollum_20k mit Stufe 1 „ohne sichtbare Verzögerung“ an? (ja / besser, aber noch sichtbar / kein Unterschied) | |
| Ist irgendetwas anders als mit `--stage1 none` (Aussehen, Auswahl, Undo-Ergebnis)? | |

Wenn „ja“: Stufe 2 (Core-Änderung) ist nicht nötig (AD-023 §7). Wenn „besser, aber noch sichtbar“: nächster Schritt ist
die Entscheidung über Stufe 2 und AD-022.
