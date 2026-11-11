# Benchmark fixtures (`experiments/drag_cost`)

Test fixtures for the performance probes - **not production example assets** (those live in `examples/meshes/`).
Committed per Manu's decision D5 (2026-11-11,
[`ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md`](../../../docs/research/deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md)
"Decisions") so dense measurements are reproducible on every machine.

## `gollum_87k.obj`

| | |
|---|---|
| Content | 87 500 vertices, 87 500 quads; plain OBJ (`v` and `f` lines only, no normals / UVs), LF line endings |
| sha256 | `ea05e77f0dbfdc76da310e2407af000889b23e7307c4970e53aab6f54e4c51cf` (4 935 750 bytes) |
| Source | `examples/meshes/gollum_20k.obj` (21 875 V / 21 875 F; sha256 `45bb298ebdaeb2271bc9e77e69c319b10f40d95e03e9a500c0941073af066553`, git blob `1efa482`) |
| Method | one Catmull-Clark step of the production evaluator: `mirai.subdivision.catmull_clark.SubdSurface(mesh).level(1)`, positions from `apply_full`, faces from `level.faces`; coordinates written as `%.6f` (`probe_scale_audit.make_dense`) |
| Generated | 2026-11-10 for the scale audit; committed 2026-11-11. Evaluator at the time: `src/mirai/subdivision/catmull_clark.py` as of `1fb9d80` |
| Used by | `probe_scale_audit.py` (`--assets dense`, default), `probe_kernels.py` (`dense`), `probe_navigation_gl.py --assets experiments/drag_cost/fixtures/gollum_87k.obj` |

Regenerating it is deterministic (same bytes on Linux in the container, two runs, and on the reference PC under
Windows 10 / Python 3.14.2, Manu 2026-11-11: `--verify-dense` "identical", same sha256; `newline="\n"` on every
platform). Check on any machine:

```
python experiments/drag_cost/probe_scale_audit.py --verify-dense
```

"DIFFERENT" means the evaluator or the source mesh changed since the fixture was written: the fixture stays as the
benchmark reference until a decision replaces it (then `--make-dense`, a new sha256 here and a note in the results
that compare across the change). `.gitattributes` keeps git from converting its line endings on Windows checkouts.
