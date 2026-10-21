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

## Result: reference PC (Manu, 2026-10-21)

Core 2 Quad Q9550, GeForce 9800 GTX, GL 3.3.0; `gollum_20k`, `--steps 20 --row-seconds 240`, GC on, **n = 20 per row**.
Raw: [`RESULTS_REFERENCE_PC_2026-10-21.md`](RESULTS_REFERENCE_PC_2026-10-21.md). ms, p50 (p95):

| Op | frame `none` 3.14 | frame `all` 3.14 | undo `none` | undo `all` | op + undo `none` → `all` (3.14) | op + undo `all` 3.12 |
|---|---:|---:|---:|---:|---:|---:|
| Extrude 1 face | 2 990 (3 083) | 1 017 (1 039) | 1 795 | 983 | 4 793 → 1 885 | 2 994 |
| Extrude 20 faces | 3 702 (3 767) | 1 586 (1 735) | 1 804 | 1 019 | 5 500 → 2 610 | 4 720 |
| Knife commit | 2 335 (2 448) | 1 526 (1 765) | 2 006 | 1 125 | 4 371 → 2 645 | 4 321 |
| Dissolve 1 edge | 1 930 (2 018) | 766 (928) | 1 926 | 1 245 | 3 829 → 2 063 | 3 279 |
| Delete 1 face | 1 835 (1 942) | 667 (919) | 1 857 | 1 248 | 3 666 → 1 950 | 3 058 |

Reading (agent, `PROVISIONAL`):

1. **One structural sync: 1 249 → 295 ms (4.2x)**, the same factor as in the container. Of the remaining ~295 ms:
   ~140 ms `GLRenderStore` (VertexList creation 72, whole-buffer `update`), ~120 ms Python flattening, the rest the V0
   detection pass. The next cut there is V1 (patch buffers instead of recreating them).
2. **Op + Undo roughly halves** (Delete 3.7 → 2.0 s, Extrude 1 face 4.8 → 1.9 s); p95 stays close to p50. Still far
   from "ohne sichtbare Verzögerung": op frame 0.7-1.6 s, Undo 1.0-1.25 s.
3. **What is left now**, Delete: op frame = history 126 + hover re-pick 153 + sync 345 (+ op 30); Undo ≈ `load_state` ~450
   + H0's after-export ~150 + sync ~300 + re-pick ~150. Extrude 20 and Knife keep both full snapshots (history 690-920 ms,
   not covered by H0). The largest single items: `load_state` (H1), the snapshots (H0 / H1), the whole-buffer upload (V1),
   the `PickCache` rebuild (AD-022 / P). That is stage 2 plus AD-022.
4. **H0 on the reference PC:** the history of Delete / Dissolve drops 434 → ~125 ms (one export and the `after == before`
   comparison gone); the Undo of Delete / Dissolve (1 245 ms) is ~260 ms slower than the Extrude Undo (983 ms, no H0), which
   fits the one export H0 moves there. A run `--stage1 V0,V2,V3` would isolate it; not needed to read the direction.
5. **Python 3.12.10 is much slower for the history**: `export_state` 350 vs 147 ms, `load_state` 1 276 vs 481 ms per call
   (its GC threshold is 700 vs 2 000 under 3.14; same pattern as the container), the viewport sync is the same (~288 ms).
   Op + Undo under 3.12 is 1.2-1.8x the 3.14 value. So a move to 3.12 (e.g. for a pinned NumPy) costs undo/redo time unless
   the GC is tuned (AD-023 G) or the history no longer takes whole snapshots (H1).

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
