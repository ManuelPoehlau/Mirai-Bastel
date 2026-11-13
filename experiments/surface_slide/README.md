# Surface Slide — algorithm research prototype

**Status (2026-11-13):** research and validation, **not Production**. Nothing in `src/` imports this folder and no
Production behaviour changed. The question: *which algorithm lets mesh vertices slide across a reference surface so
that they stay on it, stay in the surface region they belong to, and keep a recognisable shape?*

Result and recommendation: [`docs/research/SURFACE_SLIDE_ALGORITHM_RESEARCH_2026-11-13.md`](../../docs/research/SURFACE_SLIDE_ALGORITHM_RESEARCH_2026-11-13.md).
All measured numbers: [`results/SUMMARY.md`](results/SUMMARY.md) (generated).

## What is here

| File | Role |
|---|---|
| `refsurf.py` | `RefSurface`: the immutable triangle snapshot of a gesture (adjacency, barycentric gradients, vertex normals, closest point global / by adjacency descent, flat and Phong evaluation); mirror-symmetric triangulation |
| `geodesic.py` | straightest geodesics for many points at once (edge unfolding, start on a vertex) |
| `algorithms.py` | the candidates behind one interface: `closest_global`, `ray_normal`, `ray_view`, `closest_local`, `tangent_local`, `geodesic_inc`, `geodesic_walk`, `geodesic_abs`, `geodesic_pursuit` (recommended), `geodesic_seeded`, `lerp(...)` |
| `fields.py` | soft-selection weights on arrays (the rule of `mirai.soft_selection.influence`), tangent transport, mirror partners |
| `seam.py` | slide along the symmetry seam (a curve of reference edges) |
| `geometries.py` | sphere, cylinder, capsule, U shape, each with its analytic / exact reference |
| `mirai_io.py` | read-only loader for the Gollum scene (`scenes/Gollum_Head_01.mirai.json`, through `core.serialization`) and the OBJ assets — the only module that imports from `src/` |
| `scenarios.py`, `harness.py`, `metrics.py` | the scenarios, the runner, the measurements |
| `run_all.py`, `studies.py`, `bench.py`, `summarize.py`, `make_figures.py` | produce `results/` |
| `tests/` | regression tests (70): what the report claims, as assertions |

The algorithm modules (`refsurf`, `geodesic`, `algorithms`, `fields`, `seam`) need NumPy only: no `core.Mesh`, no
viewport, no GUI, no mouse. A candidate takes the drag as a world-space vector since the gesture began.

## Run

From the repo root (NumPy is the only requirement; Pillow only for the pictures):

```bash
python -m pytest experiments/surface_slide/tests -q      # 70 tests, under 10 s; not part of the bare `pytest` run
```

```bash
python experiments/surface_slide/run_all.py              # 76 scenarios x candidates -> results/scenarios.json (about 8 min)
```

```bash
python experiments/surface_slide/studies.py              # density, erosion, drift, symmetry, weights, cursor
```

```bash
python experiments/surface_slide/bench.py                # 5k / 20k / 100k vertices and the dense Gollum meshes (about 15 min)
```

```bash
python experiments/surface_slide/summarize.py            # results/*.json -> results/SUMMARY.md
```

`run_all.py --only C D_cage` runs a subset (name prefixes). A scenario name reproduces its numbers: vertex choices and
drag paths are fixed, the only random inputs use fixed seeds.

## Assets used

- `scenes/Gollum_Head_01.mirai.json` — the real Gollum cage (1 670 vertices, quads plus n-gons up to 24 corners,
  declared symmetry plane x = 0 with 69 seam edges, 20 boundary edges).
- `examples/meshes/gollum.obj` — the 21 875-quad ZBrush mesh; `experiments/drag_cost/fixtures/gollum_87k.obj` for
  the benchmark. The two Gollum meshes are different models in different places (cage vertices are 0.24 units from
  the dense mesh on average), so no "cage slides on the dense mesh" test was possible; both were tested sliding
  on themselves.
