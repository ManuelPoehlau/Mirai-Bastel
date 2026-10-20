# Architecture audit probes (2026-10-20)

> Discovery probes for the viewport / mesh / workspace audit. They read the repository and change nothing; no GL, no
> window. Results feed the [audit summary](../../docs/research/viewport/ARCHITECTURE_AUDIT_2026-10-20.md) and its two
> detail reports. Not production code, not an architecture decision.

| Probe | Question | Run |
|---|---|---|
| `probe_mesh_cost.py` | What do `vertex_edges` (O(E)), `export_state`, `load_state`, the state comparison and one snapshot (= half an undo step) cost in time and memory on a dense mesh? | `python experiments/architecture_audit_probes/probe_mesh_cost.py [obj ...]` (default: `gollum_20k.obj`, `gollum.obj`) |
| `probe_morph_blend.py` | What does the blend arithmetic `base + sum(w_i * delta_i)` cost for N active morph targets (sparse / dense), in pure Python and with NumPy if importable, and how large are attribute layers (scalar mask, 4-influence weights) as `dict` vs `array`? Blend only: no normals, upload or draw. | `python experiments/architecture_audit_probes/probe_morph_blend.py [V]` |
| `probe_topology_sync_split.py` | Where does one structural viewport rebuild (`RenderMesh._sync_topology`, ~1.26 s on the reference PC at 21.9k V) go: adjacency + normals, index map + triangulation, flatten + GL upload, VertexList creation? Also times `export_state`, `load_state` and `PickCache.refresh`. Wraps functions from the outside around the unchanged `topology` scenario of `drag_cost/probe_navigation_gl.py`; opens a hidden pyglet window (headless: `xvfb-run -a`). | `python experiments/architecture_audit_probes/probe_topology_sync_split.py [--assets examples/meshes/gollum.obj]` |

## Result (container, 2026-10-20; **not** the reference PC)

Xeon @ 2.10 GHz, CPython 3.13, NumPy 2.5.3. Python-heavy code is about 2x slower on the reference PC
([`REFERENCE_HARDWARE.md`](../../docs/architecture/REFERENCE_HARDWARE.md) §2), the GL share more.

- `gollum_20k` (21 875 V): mesh + scene ~38 MB; one `export_state` snapshot ~31 MB (one undo step with before + after ~61 MB);
  `export_state` ~120 ms, `load_state` ~250 ms, `vertex_edges` ~2.5 ms per call. `gollum` (87 500 V): ~152 MB mesh; ~123 MB per
  snapshot (~246 MB per undo step); `export_state` ~600 ms, `load_state` ~2.1 s, `vertex_edges` ~10.7 ms. `HistoryStack` has no limit.
- Morph blend at 21 875 V, ms: pure Python, 15 % support: 1.5 / 14 / 65 for N = 1 / 10 / 50; fully populated: 7.1 / 62 / 373;
  NumPy fully populated: 0.05 / 0.15 / 0.37. Attribute layer for 21 875 V: scalar as `dict` 2.5 MB, as `array('f')` 0.09 MB; skin
  weights with 4 influences as nested dicts 9 MB, copied into every full snapshot.

Open on the reference PC: whether NumPy imports on the Q9550 (SSE4.1, no SSE4.2/AVX) and what these rows cost there
([audit 2](../../docs/research/viewport/ARCHITECTURE_AUDIT_2026-10-20_FUTURE_REQUIREMENTS.md), plan step P0).

Rebuild split (`probe_topology_sync_split.py`, container with Xvfb/llvmpipe, `gollum_20k`, whole `topology` run incl. warm-up and undo
frames; wall clock, nested, so the three children add up to roughly the parent; the per-face triangulation timer inflates its
row slightly): one `_sync_topology` ≈ 539 ms = adjacency + all normals 160 ms (30 %) + index map incl. triangulation 213 ms (39 %,
of which `triangulate_mesh_face` ≈ 193 ms) + flatten and upload 178 ms (33 %: store `update` calls ≈ 31 ms, VertexList creation
≈ 31 ms, the rest ≈ 115 ms is Python flattening of positions, normals, indices and face rows). `export_state` ≈ 147 ms and
`load_state` ≈ 498 ms per call in that run. The container GL is llvmpipe; the GL-dependent rows (`update`, VertexList creation)
are the ones most likely to differ on the reference PC. **Reference-PC run (Manu, third topology run, default GC, depth ~1):** one `_sync_topology`
1 224 ms = adjacency + normals 298 ms (24 %) + index map incl. triangulation 512 ms (42 %; `triangulate_mesh_face` ~449 ms) + flatten and
upload 413 ms (34 %: GL store ~145 ms, Python flattening ~269 ms); `export_state` 145 ms, `load_state` 415 ms
([raw](RESULTS_TOPOLOGY_SYNC_SPLIT_REFERENCE_PC_2026-10-20.md)). The container is ~2x faster on every row, not only on the GL ones.

Options `--gc on|off|freeze` and `--history-depth N` (added after the AD-023 review CLAUDE-001, finding B-1: the cyclic GC may dominate
`export_state` / `load_state`, and the cost grows with the number of live snapshots). Container check (Xeon, Python 3.13, llvmpipe,
`gollum_20k`, history depth 10, `--steps 5 --row-seconds 1`, n = 3): history part of an Extrude 1 face 915 ms with the GC on, 284 ms off,
436 ms frozen; Delete 1 face 868 ms on, 80 ms off, 345 ms frozen. That supports the review's reading in the container; **the reference PC
(Python 3.14) is not measured**, and n = 3 only shows the size of the effect. **Reference-PC run (Manu, 2026-10-20, `--steps 12 --row-seconds 120 --history-depth 20`, all three modes): the median is
independent of the GC (on vs off within ~3 %), the GC adds tail stalls (worst 12.9 s), `freeze` is slower; see the drag_cost README, "GC and history
depth, reference PC", and [the raw output](RESULTS_TOPOLOGY_GC_HISTORY_DEPTH_REFERENCE_PC_2026-10-20.md).** The container result above does not carry
over to the median on the reference PC.

