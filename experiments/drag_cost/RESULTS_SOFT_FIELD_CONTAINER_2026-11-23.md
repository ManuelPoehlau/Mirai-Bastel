# Soft field and Smooth-stroke dab - container, 2026-11-23

Probe: `python experiments/drag_cost/probe_soft_field.py --repeats 5` (before) / `--repeats 9` (after), cloud container
(Python 3.13.18, NumPy as installed there - not the pinned reference-PC set). Container figures only; the reference-PC
estimate is x3 (2026-11-10 audit). Context: [Brush research](../../docs/research/BRUSH_SYSTEM_FEASIBILITY_AND_ARCHITECTURE_RESEARCH_2026-11-18.md)
§4.1 / §8.4, built as [AD-020 "Smooth / Relax stroke"](../../docs/architecture/AD-020-SOFT-SELECTION-APP-PATH.md#smooth--relax-stroke-2026-11-23-provisional).

**Before** (`f8c771f32b`, clean): the geodesic field built a whole-mesh neighbour map on every call.
**After** (phase 1 + 2 working tree): neighbours from the indexed `Mesh.vertex_edges`, per visited point; the dab row
exists only after phase 2. The before-p95 outliers (68 / 233-266 ms) are GC pauses inside 5 repeats; read p50.

Field = `compute_influence` geodesic / smooth from one seed (front-most vertex). Dab = `smooth_stroke.dab` (field around
the face's points, `plan_smooth`, positions at 0.5 steps, writes in an open journal), no symmetry.

| Mesh | Radius | Weighted V | Field before p50 | Field after p50 | Dab after p50 / p95 |
|---|---:|---:|---:|---:|---:|
| gollum_20k (21,875 V) | 3 % | 11 | 9.49 ms | 0.02 ms | 0.14 / 0.23 ms |
| | 5 % | 35 | 9.15 ms | 0.06 ms | 0.37 / 0.42 ms |
| | 10 % | 236 | 9.15 ms | 0.46 ms | 1.77 / 1.96 ms |
| | 15 % | 449 | 9.81 ms | 0.86 ms | 2.99 / 3.12 ms |
| | 25 % | 1,000 | 11.03 ms | 2.02 ms | 6.55 / 7.00 ms |
| gollum_87k (87,500 V) | 3 % | 39 | 45.44 ms | 0.07 ms | 0.38 / 0.53 ms |
| | 5 % | 136 | 43.41 ms | 0.26 ms | 1.11 / 1.22 ms |
| | 10 % | 967 | 43.74 ms | 2.11 ms | 7.00 / 10.86 ms |
| | 15 % | 1,819 | 46.63 ms | 3.98 ms | 11.97 / 12.45 ms |
| | 25 % | 4,037 | 51.36 ms | 10.69 ms | 29.24 / 36.12 ms |

Symmetry setup (once per press or stroke, definition at x = 0; the fixtures are not mirror-paired, so a full pass):
`vertex_correspondence` 46-110 ms (20k), 192-240 ms (87.5k); `SymmetryIndex` 95-162 ms (20k), 646-1005 ms (87.5k).
Since phase 1 a Smooth / Relax / Inflate / Pinch press pays this once (before: the field's correspondence plus the plan's
own index, i.e. twice).

**Reading.** The bars (research §7): <= 16.7 ms p95 per dab at 5 % on 20k and <= 33 ms on 87.5k on the reference PC.
Container x3: 1.3 ms and 3.7 ms - far inside. At 87.5k / 25 % a dab is ~29 ms (container), ~90 ms estimated on the
reference PC: a large radius on the dense mesh dabs slowly (the stroke caps the dabs per event, it does not drop the
way). Not measured here: the per-dab surface pick after a write (GPU ID pass re-render or the CPU pick-cache patch)
and the viewport sync - the reference-PC run in the app answers both (ATELIER B17).
