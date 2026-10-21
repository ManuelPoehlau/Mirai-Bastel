# AD-023 stage 2 + AD-022 as one prototype: Delete with Undo / Redo only

> Prototype for the decision "stage 2 of [AD-023](../../docs/architecture/AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md)
> together with [AD-022](../../docs/architecture/AD-022-GPU-PICKING.md)" (AD-023 §6 question 3, §7 stage 2). **Not
> production code, not a decision, not Artist-validated.** Nothing under `src/` is changed: `stage2.py` installs
> stage 1 ([`topology_sync_stage1`](../topology_sync_stage1/README.md), all four switches) and the stage-2 switches
> from the outside. Where the prototype stands in for a **Core change** (the delta apply in `delta.py` reaches into
> `Mesh._vertices / _edges / _faces / _edge_lookup`), it is marked; in production that is a CORE_V1_FREEZE §7
> exception with contract tests (Manu, 2026-10-21: Core changes are a must when they bring a clear gain).
> Basis: stage-1 result on the reference PC ([README](../topology_sync_stage1/README.md), "Result: reference PC"),
> the GPU spike ([README](../gpu_picking_spike/README.md)), review probe P2
> ([AD-022 review](../../docs/archive/viewport_v02/reviews/AD-022_REVIEW_CLAUDE_001.md)).

## Question

Stage 1 halved op + Undo on `gollum_20k` (Delete 3.7 → 2.0 s on the reference PC) and was "viel zu langsam" (Manu,
2026-10-21). Does stage 2 (delta history H1 + patched buffers V1) **together with** GPU picking (AD-022 B2) get one
operation and its Undo to "ohne sichtbare Verzögerung" - before the real rebuild is started? Delete is the smallest
op that exercises all three parts (history, buffers, re-pick); the engineering proxy is a discrete operation incl.
Undo ≤ 100 ms (`PROVISIONAL`, AD-023 header); the success line is Manu's feel.

## What is built

| Switch | Option | What it does |
|---|---|---|
| `H1` | AD-023 H1 | Delete (Entf in vertex, edge, face mode; no symmetry definition) pushes a `DeltaCommand` instead of `MeshStateCommand`'s two whole-mesh snapshots. **Capture mechanism: declared neighbourhood + local diff** - before the unchanged Core op runs, the closure it can touch is read (faces, their edges, those edges' endpoints); after it, whatever of that closure is gone is "removed", every surviving edge with a changed face list is "changed". No full snapshot, no Core hook, no recording proxy; the price is a per-op contract "mutates nothing outside its declared neighbourhood" (true for `Mesh._delete_region` by construction, tested). Undo / Redo re-insert / remove the records. |
| `V1` | AD-023 V1 (+ U) | The viewport patches its buffers from the delta instead of a full topology sync, also on Undo / Redo. **Slot rule:** between two full rebuilds every vertex keeps its buffer index and every face its triangle range and face row; a dead face's triangles become degenerate `(a, a, a)` (no fragment, but `gl_PrimitiveID` and `triangle_faces` stay valid for every live triangle), a dead vertex slot gets a sentinel position. Undo revives the same slots. Index data is patched in place (the AD-018 "patch contract for index data" V1 needs). No spare capacity (nothing grows in a Delete); an element without a slot falls back to the stage-1 full sync, which compacts. Undo learns that the entry was a delta from the command itself (no `HistoryStack` accessor). |
| `GPU` | AD-022 B2-out | Hover and click in **face and vertex mode** pick from an ID render of the `RenderMesh` buffers, drawn **outside** `GLRenderStore` with a second program over the store's public VertexList: face = `gl_PrimitiveID` → `_triangle_face_rows` → FaceId, vertex = `glDrawArrays(GL_POINTS)` with `gl_VertexID` → slot (dead slots clipped). `position` bound with `layout(location = …)` to the store program's location. **Ordering fix** (AD-022 §5): the picker syncs the edit `RenderMesh` first if anything is pending, so a pick right after a Delete or an Undo never reads the old buffers. ID render cached per buffer content / camera / size / occlusion / mode. Edge mode, Box/Paint, Knife, object mode, headless: CPU picker unchanged. |

Configurations of the probe: `none` (today's code), `stage1` (V0,V2,V3,H0 - the previous measurement), `H1,V1`
(stage 1 + stage 2, CPU picker), `all` (stage 1 + H1,V1,GPU).

**Exactness contract (AD-023 §2 H1), as met here:** (1) Delete allocates no IDs, the entry never touches the
counters; (2) the symmetry definition is untouched (a Delete under symmetry takes the old path); (3) boundaries and
`edge.faces` lists are restored as stored; (4) the iteration order of all three containers is restored exactly -
the mesh dicts are in ascending ID order (IDs are only ever appended; `load_state` keeps the snapshot's order), the
capture checks that and the Undo re-inserts by bisection, else it records the positions; (5) Delete validates every
ID before it mutates, so no rollback snapshot is needed; (6) "changed?" is the op's own result.

**Where whole-mesh work is left** (AD-023 §7 abort rule asks for it): the Core op itself scans every edge once
(`_delete_region`'s `keeps_edge`); a vertex Delete's neighbourhood needs `vertex_edges` (an O(E) scan; the Core
has no vertex → edge index, the op does the same scan); the exact-order Undo rebuilds each container that gets
elements back (C-level `list` / `dict.update`, no Python loop); the highlight flags are rebuilt over all vertices
per selection change (unchanged code; the shader no longer reads them). None of these is needed to compute the
touched set of a face / edge Delete. A Core vertex → edge index would remove the first two.

**Not covered:** every other op (Extrude, Knife, Connect, Dissolve: stage-1 path; they create elements, i.e. new
IDs and spare buffer capacity - the hard part of stage 2 still to prototype); symmetric Delete; edge-mode, Box,
Paint and Knife picking on the GPU; H7 surfaces and placed objects beyond the model matrix; the wire overlay
(rebuilt whole per dirty frame when shown, E39), Soft preview and symmetry reports (off in the probe); 87.5k.

## Tests (`tests/`)

- `test_delta_equivalence.py` (headless): randomised Delete sequences in all three modes, five deep, undone to the
  start and redone to the end; after every step `export_state()` **and** the key order of every container and the
  `edge.faces` order equal the whole-snapshot oracle; counters stay forward; selection restore; a non-ascending
  container (recorded positions); symmetry and invalid IDs take the old path / change nothing.
- `test_v1_equivalence.py` (headless): after every step the patched `RenderMesh` holds per element what a fresh one
  built with the original code holds (triangles per face, face rows, positions, normals within 1e-9, adjacency,
  index buffer: live triangles exact, everything else degenerate, `triangle_faces`, highlight flags by slot, the
  stage-1 V0 cache); also two steps without a frame in between, a W move between Deletes, and a Dissolve (full sync,
  compaction) with Undo through the whole stack (the revival falls back).
- `test_gl.py` (GL, `xvfb-run -a`): the same steps draw the same image with `none` and `all`; B2 face and point pass
  equal the spike's B1 per pixel, fresh, after a Delete and after its Undo; a pick right after a Delete and right
  after an Undo (no frame in between) names no dead element and agrees with the CPU picker at the pixel centre.

Mutation checks done once by hand: no order restore (`ORDER_MODE = "append"`) fails 14 delta tests; not writing the
degenerate triangles fails 9 tests (incl. the image); no sync before the pick fails the stale-ID and B2 tests.
Found while building: the ID vertex shader must use the production expression `u_proj * u_view * (u_model * p)`;
`u_proj * u_view * u_model * p` differed from B1 on 2 of 786 432 pixels (llvmpipe).

## Run

```bash
python experiments/topology_stage2_delete/probe_stage2.py      # all four configurations + B2 check, one command
python experiments/topology_stage2_delete/run.py                # the app, all (stage 1 + H1,V1,GPU)
python experiments/topology_stage2_delete/run.py --config stage1
python experiments/topology_stage2_delete/check_b2.py           # the B2 check alone (~1 min)
xvfb-run -a python -m pytest experiments/topology_stage2_delete/tests -q
```

## Result: container, 2026-10-21 [C] (not the reference PC)

Xeon @ 2.80 GHz, Python 3.13.16, **llvmpipe** (the ID render and the draw are software rasterisation here), `gollum_20k`,
defaults (`--steps 20 --row-seconds 120`, GC on), n = 20 per row. Raw: [`RESULTS_CONTAINER_2026-10-21.md`](RESULTS_CONTAINER_2026-10-21.md).
ms, p50 (p95):

| Row | `none` frame / undo | `stage1` frame / undo | `H1,V1` frame / undo | `all` frame / undo / redo |
|---|---:|---:|---:|---:|
| Delete 1 face | 970 / 1 165 | 333 / 1 167 | 103 / 89 | **41 (54) / 32 (49) / 27** |
| Delete 20 faces | 927 / 1 156 | 314 / 1 202 | 102 / 103 | **41 / 46 (68) / 30** |
| Delete 1 vertex | 1 177 / 1 536 | 496 / 1 450 | 161 / 149 | **51 / 53 (85) / 33** |

Where a Delete-1-face frame goes with `all`: Core op 8.6, history (delta capture + push) 3.0, re-pick 17.2 (of which
3.4 the V1 patch, synced before the pick; the rest the ID render on llvmpipe ~10 and the read), viewport sync 2.7,
draw 8.1 (llvmpipe). Undo: delta apply 5.4, re-pick incl. patch 16.0, sync 2.5. B2 check: the face mapping
`gl_PrimitiveID` → face is **exact** on every pixel (two cameras; fresh, after Delete 20 faces, after its Undo), the
point pass too; `position` sits at location 0 in all three programs; agreement with the CPU picker: face 75-85 %
same + the rest half-pixel (0 real differences), vertex 96-98 % (11 neighbouring-vertex differences in 389
non-trivial cursors, none "GPU none").

This container is slower than the one of the stage-1 run (`none` Delete frame 970 here vs 646 there, GC on here vs
off there); compare within this table.

Reading (agent, `PROVISIONAL`):

1. **The two parts need each other.** Stage 2 without GPU picking (`H1,V1`) brings Delete and its Undo from ~1.2 s
   to ~0.1 s; what is left is mostly the CPU `PickCache` rebuild (re-pick 70 ms of the 103 ms frame). GPU picking
   without stage 2 does not help much either (extra run `--config GPU`, n = 10: Delete 1 face frame 273 ms, Undo
   1 082 ms): before the pick reads the buffers they must be synced, and with stage 1's full rebuild that sync is
   ~124 ms of the 141 ms re-pick, while the Undo keeps its whole-mesh `load_state`. Together (`all`) the frame is 41 ms, the Undo 32 ms, and no
   part of it scales with the mesh except the items below.
2. **One contract works:** V1's slot rule (degenerate triangles keep their place) and B2's `gl_PrimitiveID` mapping
   are the same index buffer and the same triangle → face-row map; per pixel the IDs are exact after a patched
   Delete and its Undo (on llvmpipe; the reference driver is what `check_b2.py` is for).
3. **What is still whole-mesh or tail-prone:** the Core op's own edge scan (8-12 ms here, ~25 ms on the reference PC
   per AD-023 §1); vertex Delete's `vertex_edges` scan (no vertex → edge index); the exact-order Undo (Delete 20
   faces / 1 vertex: history 18-20 ms p50, max 106-142 ms - the container rebuild allocates enough objects to start
   a GC pass; Delete 1 face only rebuilds the face dict: 5 ms); the highlight flags over all vertices. Each is a
   candidate for the Core change (vertex → edge index; an order rule) rather than for more viewport work.
4. **Expectation for the reference PC** (estimate, not measured): the Python parts take about 2-3x the container
   (AD-023 §1, stage-1 runs), the GPU parts much less than llvmpipe (ID render ~1-3 ms instead of ~10, draw ~1 ms
   instead of ~8). That puts Delete and its Undo each somewhere around 40-80 ms - near or under the 100 ms proxy,
   but whether that is "ohne sichtbare Verzögerung" is the practical test.

## Result: reference PC (Manu, 2026-10-21)

Core 2 Quad Q9550, GeForce 9800 GTX, GL 3.3, Windows 10, Python 3.14.2; `gollum_20k`, probe defaults (GC on,
n = 20 per row; `none` n = 15-17 within the row budget). Raw: [`RESULTS_REFERENCE_PC_2026-10-21.md`](RESULTS_REFERENCE_PC_2026-10-21.md).
ms, p50 (p95):

| Row | `none` frame / undo | `stage1` frame / undo | `H1,V1` frame / undo | `all` frame / undo / redo | `all` op + undo |
|---|---:|---:|---:|---:|---:|
| Delete 1 face | 1 687 / 1 781 | 667 / 1 116 | 171 / 160 | **35 (37) / 19 (25) / 9** | **54 (60)** |
| Delete 20 faces | 1 709 / 1 891 | 787 / 1 120 | 176 / 193 | **42 (43) / 55 (135) / 15** | **97 (175)** |
| Delete 1 vertex | 1 897 / 2 043 | 774 / 1 349 | 278 / 274 | **54 (56) / 50 (133) / 15** | **104 (184)** |

Where a Delete-1-face frame goes with `all`: Core op 19.0, history 5.1, re-pick 5.6 (of which 3.4 the V1 patch
synced before the pick), viewport sync 2.2, draw 2.0. Its Undo: delta apply 8.7, re-pick 5.6, sync 2.0.
**B2 check on the reference driver:** `gl_PrimitiveID` → face is **exact** on every pixel (two cameras; fresh, after a
patched Delete of 20 faces, after its Undo), the point pass (`gl_VertexID`) too; `position` at location 0 in all three
programs; CPU agreement identical to the container (face: 0 real differences, the rest half-pixel; vertex: 11
neighbouring-vertex differences in 389 non-trivial cursors, no "GPU none"). One pick after a camera change: face
2.8 ms (max 3.5), vertex 5.6 ms (max 24.0, one sample), against 150-190 ms for the CPU `PickCache` rebuild (AD-022 §1).

Reading (agent, `PROVISIONAL`):

1. **Delete and its Undo are 30-90x faster than today and 20-60x faster than stage 1** (p50). Every p50 frame is
   under the 100 ms proxy, Delete 1 face with its Undo even together (54 ms). The container estimate (40-80 ms each)
   was pessimistic: the GPU parts on the 9800 GTX are ~2-6 ms, the Python parts ~2x the container.
2. **Both parts are needed, as in the container:** `H1,V1` alone leaves ~150 ms, almost all of it the CPU
   `PickCache` rebuild (re-pick 140-230 ms). The coupling AD-023 §5 named ("one contract") holds on the reference
   driver: the slot rule with degenerate triangles and B2's `gl_PrimitiveID` mapping give exact IDs.
3. **What is left, in order of size:** (a) the **exact-order Undo** when vertices and edges come back: history
   38-40 ms p50 with p95 120-122 ms (Delete 20 faces, Delete 1 vertex) - the container rebuild of `_vertices` /
   `_edges` plus a GC pass it triggers; Delete 1 face only rebuilds the face dict (8.7 ms). This is the one place where
   the p95 crosses the proxy. (b) the **Core op** itself, 19-25 ms (the edge scan in `_delete_region`; for a vertex
   also `vertex_edges`). (c) everything else is 2-10 ms. Both (a) and (b) are Core questions: an order rule (keep
   ascending ID order without rebuilding, or declare dict order not part of "exact" and make consumers order-free,
   AD-023 §2 H1 point 4) and a vertex → edge index.
4. **Not shown by this prototype:** ops that create elements (Extrude, Knife, Connect: new IDs, spare buffer
   capacity, the Knife resolver's checkpoints), symmetric ops, edge-mode / Box / Knife picking on the GPU, 87.5k.

**Manu, 2026-10-21 (chat, with the raw output; recorded by the agent):** „Die Messungen zeigen deutlich, UNDO und
Delete fühlen sich sehr viel schneller an“.

## Praktischer Test für Manu (ca. 10 Minuten + ein Messlauf)

**Fühlen (das entscheidet):** `python experiments/topology_stage2_delete/run.py` öffnet die normale App mit
gollum_20k (Fenstertitel: „Stufe 2 Delete: stage1+H1,V1,GPU“). Probier dort **nur Delete** (Entf) aus, in allen
drei Modi (`1` Vertex, `2` Edge, `3` Face), einzeln und mit größeren Auswahlen, dazu mehrmals Undo (Strg+Z) und
Redo (Strg+Y) hintereinander. Fahr nach dem Löschen mit der Maus über die Stelle (Hover im Vertex- und Face-Modus
kommt jetzt von der GPU). Zum Vergleich einmal `python experiments/topology_stage2_delete/run.py --config stage1`
(Stufe 1, wie zuletzt). Alles andere (Extrude, Knife, Dissolve, Edge-Hover …) ist in beiden Fenstern Stufe 1 und
gehört nicht zum Test.

**Messen (PowerShell im Repo-Ordner, ein Befehl, ca. 10-15 Minuten, die ganze Ausgabe kopieren):**

`python experiments\topology_stage2_delete\probe_stage2.py`

Er misst nacheinander `none` (heutiger Code), `stage1`, `H1,V1` (Stufe 2 ohne GPU-Picking) und `all`, danach den
B2-Check (ob `gl_PrimitiveID` auf deiner Grafikkarte exakt ist; AD-022 §8). Am Ende steht eine Zusammenfassung.

| Frage | Dein Verdikt |
|---|---|
| Fühlen sich Delete und sein Undo/Redo auf gollum_20k „ohne sichtbare Verzögerung“ an? (ja / besser, aber noch sichtbar / kein Unterschied zu Stufe 1) | **Manu, 2026-10-21:** „Die Messungen zeigen deutlich, UNDO und Delete fühlen sich sehr viel schneller an“ (ob das „ohne sichtbare Verzögerung“ heißt, ist offen) |
| Ist irgendetwas anders als mit `--config stage1` (Aussehen nach Delete/Undo, Hover, Auswahl nach Undo)? | nicht beantwortet |

Wenn „ja“: Stufe 2 + AD-022 sind als Richtung belegt, nächster Schritt ist die Entscheidung über die Richtung
(AD-023 §7) und der Prototyp der schweren Operationen (Extrude, Knife), bevor `src/` umgebaut wird. Wenn „noch
sichtbar“: die Messung zeigt, welcher Teil fehlt.
