# Soft Selection — Findings (WP-SOFT-01 S1)

Date: 2026-10-08. Mode: Discovery (Type B). Baseline `main` @ `02a08c3`.
Rule for this file: **observations are separated from interpretation**; nothing here chooses
a default (metric, curve, scale formula) or claims promotion readiness. Interpretations are
marked *(reading)*, open points end up in §5.

## 1. What exists and what was tested

- `influence.py`, `weighted_ops.py`, `probe_cost.py`, `tests/` (96 tests) — see `README.md`.
- Suite: `python -m pytest experiments/soft_selection/tests` → **96 passed** (Linux container,
  Python 3.13 and Python 3.9). On Windows only the probe was run (reference PC, §2.1), not the suite.
- Production regression: `pytest tests --ignore=tests/test_extrude_tool.py` → **1867 passed**,
  `pytest experiments/symmetry_lab/tests` → **363 passed** (container needed `pytest`, `pyglet`
  and `libegl1` installed to reproduce the baseline; no `src/` file changed).

## 2. Measured numbers (container — not the reference PC)

`python experiments/soft_selection/probe_cost.py` (defaults: 60 steps per gesture, influence
median of 5). Container: Intel Xeon @ 2.10 GHz, 4 logical cores, Python 3.13.16. Per
`docs/architecture/REFERENCE_HARDWARE.md` §4 these are container numbers; the reference PC run
(README, "Praktischer Test") is still outstanding.

```
Asset head_basemesh: 326 vertices, bounding radius 3.3717, seeds 5 (vertex 286 + one-ring), 60 update steps per gesture
  radius          metric     influence_ms  influenced  move_ms  rotate_ms  scale_ms  core_move_ms
    5%   0.1686  euclidean         0.068           9    0.005      0.015     0.013         0.006
    5%   0.1686  geodesic          0.150           9    0.004      0.015     0.019         0.005
   15%   0.5058  euclidean         0.100          36    0.016      0.064     0.077         0.019
   15%   0.5058  geodesic          0.161          30    0.014      0.063     0.049         0.020
   30%   1.0115  euclidean         0.150          68    0.031      0.108     0.103         0.037
   30%   1.0115  geodesic          0.205          61    0.032      0.098     0.095         0.033

Asset man_with_shoes_basemesh: 928 vertices, bounding radius 1.0005, seeds 4 (vertex 121 + one-ring), 60 update steps per gesture
  radius          metric     influence_ms  influenced  move_ms  rotate_ms  scale_ms  core_move_ms
    5%   0.0500  euclidean         0.161          18    0.011      0.031     0.025         0.010
    5%   0.0500  geodesic          0.385          10    0.005      0.017     0.013         0.006
   15%   0.1501  euclidean         0.165          76    0.033      0.126     0.109         0.038
   15%   0.1501  geodesic          0.393          28    0.013      0.043     0.060         0.015
   30%   0.3002  euclidean         0.222         112    0.046      0.172     0.168         0.058
   30%   0.3002  geodesic          0.513         107    0.047      0.168     0.181         0.056
```

Observations:

- N1. Influence is computed once per gesture (at `begin()`), never per update. Worst row:
  geodesic, body mesh, 30 % → ~0.5 ms (spread over 4 runs: 0.46–0.69 ms).
- N2. Per-update cost of the weighted ops is in the same range as the plain Core Move on the same
  vertex set (`core_move_ms`); Rotate/Scale cost ~3–4× Move. All rows ≤ 0.26 ms per update
  across 4 runs. Cost grows with the influenced count, not with the mesh size.
- N3. Run-to-run spread in the container is up to ~2× per cell (4 runs); single cells are not
  meaningful, orders of magnitude are.
- N4. **Geodesic first version** used `Mesh.vertex_edges()` per visited vertex. That query is a
  documented O(E) scan in Core V1 (`src/core/mesh.py`, "V1: einfacher Scan"). Measured then:
  head 30 % 1.6–2.1 ms, body 30 % 7.8–10.6 ms. Building the adjacency once per call from
  `all_edge_ids()`/`edge_vertices()` brought body 30 % to ~0.5 ms. The euclidean metric scans
  all vertices once (O(V), with a seed-bounding-box reject).
- N5. Not measured here: viewport sync, buffer upload, drawing, picking. The Symmetry Lab probe
  showed those dominate a drag on the app path; S1 numbers are only the operation's share.

### 2.1 Reference PC run (Manu, 2026-10-08)

Windows 10 (19045), Intel Core 2 Quad Q9550 @ 2.83 GHz (4 logical cores), Python 3.14.2.

```
Asset head_basemesh: 326 vertices, bounding radius 3.3717, seeds 5 (vertex 286 + one-ring), 60 update steps per gesture
  radius          metric     influence_ms  influenced  move_ms  rotate_ms  scale_ms  core_move_ms
    5%   0.1686  euclidean         0.591           9    0.013      0.058     0.038         0.017
    5%   0.1686  geodesic          0.631           9    0.013      0.055     0.037         0.017
   15%   0.5058  euclidean         2.246          36    0.048      0.216     0.189         0.062
   15%   0.5058  geodesic          1.150          30    0.045      0.177     0.155         0.058
   30%   1.0115  euclidean         4.659          68    0.093      0.431     0.370         0.118
   30%   1.0115  geodesic          1.847          61    0.082      0.359     0.317         0.109

Asset man_with_shoes_basemesh: 928 vertices, bounding radius 1.0005, seeds 4 (vertex 121 + one-ring), 60 update steps per gesture
  radius          metric     influence_ms  influenced  move_ms  rotate_ms  scale_ms  core_move_ms
    5%   0.0500  euclidean         1.131          18    0.025      0.110     0.088         0.032
    5%   0.0500  geodesic          1.472          10    0.015      0.060     0.046         0.019
   15%   0.1501  euclidean         4.289          76    0.110      0.458     0.403         0.130
   15%   0.1501  geodesic          1.980          28    0.039      0.180     0.149         0.049
   30%   0.3002  euclidean         5.476         112    0.156      0.673     0.608         0.195
   30%   0.3002  geodesic          4.385         107    0.141      0.646     0.580         0.181
```

- R1. Per-update cost: at most 0.67 ms (Rotate, body, 30 %). The update columns are about 3–5x the
  container. Weighted Move stays at or below the plain Core Move on the same vertex set, as in the container.
- R2. Influence (once per gesture): at most 5.5 ms (euclidean, body, 30 %). This is 8–35x the container,
  much more than the update columns. On the head, euclidean is *slower* than geodesic at 15/30 %;
  in the container (also under Python 3.14.6) it is the other way round.
- R3. The euclidean time grows linearly with the number of `math.dist` calls in `_euclidean_distances`
  (vertices inside the seed bounding box × seeds, counted in the container on the same assets): head
  55 / 225 / 455 calls → 0.59 / 2.25 / 4.66 ms, body 92 / 404 / 520 → 1.13 / 4.29 / 5.48 ms, i.e.
  ~10 µs per call on the reference PC vs ~0.2 µs in the container. The geodesic column fits the same
  per-call cost (one `math.dist` per edge relaxation) plus the one-off adjacency pass.
  The update path calls no `math.dist`, and its columns scale normally.
- R4. *(reading, unverified)* Candidate cause: the Q9550 has no FMA instructions, and a
  software-emulated `fma()` in the C runtime would make `math.dist` expensive. R6 confirms that
  `math.dist` is unusually slow on this machine; the FMA mechanism itself was not checked.
- R5. *(reading)* Against the Symmetry Lab threshold (whole mouse move p95 ≤ 8 ms, which includes viewport
  work), the operation's share per update is ≤ 0.67 ms on the reference PC. The influence computation is a
  one-off ≤ 5.5 ms at gesture start for these radii. The viewport share of a soft drag is still unmeasured (N5).
- R6. Micro-benchmark, µs per call, values `a = (1, 2, 3)`, `b = (4, 6, 8)`:

  | Machine | `math.dist(a, b)` | `math.sqrt` of the summed squares |
  |---|---|---|
  | Reference PC | 3.22 | 1.08 |
  | Container, Python 3.13 / 3.14 | 0.05 / 0.07 | 0.18 / 0.21 |

  So `math.dist` is ~46x slower on the reference PC, while the hand-written form is ~5x slower,
  in line with the update columns. Open point: at 3.2 µs, `math.dist` explains only about a third
  of the ~10 µs per call fitted in R3. Not examined: whether real coordinates are slower than the
  round benchmark values, and where the rest of the per-call cost goes.
- R7. Consequence in this experiment: `influence.py` now uses `math.sqrt` of the summed squares
  (euclidean compares squared distances and takes one root per vertex). Influenced counts are
  unchanged, the suite passes (96), and container times are unchanged within noise. **The reference-PC
  probe has not been re-run since this change**; the §2.1 table is the `math.dist` version.

## 3. Observations — metrics, curves, scale formulas

### 3.1 Euclidean vs geodesic

- M1. Lip fixture (two sheets 0.1 apart, joined only 4 units away): with `r = 0.5`, euclidean
  reaches the lower sheet (`w ≈ 0.90` directly beneath the seed), geodesic does not
  (`test_lip_euclidean_reaches_the_other_sheet_geodesic_does_not`).
- M2. Same effect on a real asset: on `man_with_shoes_basemesh` the probe's seed (front-most
  vertex, x = −0.73, y = 1.04 — the hand region, by position; not visually verified) at 5 %
  radius: euclidean influences 18 vertices, geodesic 10. The 8 euclidean-only vertices are at
  0.6–0.93 r straight-line but 3.2–4.3 r along edges — presumably a neighbouring finger. At 15 %:
  76 vs 28 (48 euclidean-only, edge distance 1.0–1.54 r).
- M3. On the head (seed = nose-tip region, x = 0) the difference is smaller: 15 % → 36 vs 30,
  30 % → 68 vs 61. The euclidean-only vertices lie at 1.07–1.22 r along edges, i.e. just outside
  — not a topologically far region.
- M4. The edge-graph distance overestimates the surface distance. On a regular quad grid it is
  the Manhattan distance (diagonal neighbour 2 instead of √2·1; `test_geodesic_is_the_edge_path_length`),
  so the geodesic falloff region on a regular grid is a diamond, not a disc. On the head, for
  vertices inside both maps, geodesic/euclidean distance ratio: median 1.10 (15 %), 1.17 (30 %),
  max 1.38. *(reading: the same nominal radius reaches less with `geodesic`; part of that is
  curvature, part is edge-path anisotropy — not separated here.)*
- M5. Seeds from Edge/Face mode are the edge's/face's vertices (E3, `resolve_selection_vertices`).
  Distance is measured to those vertices, not to the edge/face itself; a vertex next to the middle
  of a long selected edge has a larger `d` than its distance to the edge.

### 3.2 Curves

- C1. `smooth` (smoothstep on `t = 1 − d/r`) and `linear` agree at `d = r/2` (both 0.5); `smooth`
  is above `linear` for `d < r/2` and below for `d > r/2`. At `d = r`, `linear` has slope `−1/r`,
  `smooth` slope 0 (the reason given by the articulation precedent `_falloff_weight`).
- C2. Sum of weights over the influenced set (euclidean, 30 %, smooth vs linear): head 34.5837 vs
  34.5842, body 67.1 vs 64.5 (4 %). The curves mostly redistribute weight inside the region
  rather than change its total. *(No visual comparison possible in S1.)*

### 3.3 Scale: `1 + w(F − 1)` (linear) vs `F^w` (power)

Effective per-axis factor `g` for a vertex with weight `w`:

| F | w | linear | power |
|---|---|---|---|
| 2.0 | 0.25 / 0.5 / 0.75 | 1.25 / 1.50 / 1.75 | 1.19 / 1.41 / 1.68 |
| 0.5 | 0.25 / 0.5 / 0.75 | 0.875 / 0.75 / 0.625 | 0.84 / 0.71 / 0.59 |
| 10 | 0.25 / 0.5 / 0.75 | 3.25 / 5.5 / 7.75 | 1.78 / 3.16 / 5.62 |
| 0 | any | `1 − w` | 0 (whole region onto the pivot) |
| −1 | 0.25 / 0.5 / 0.75 | 0.5 / 0 / −0.5 | undefined → `ValueError` |

- S1. Linear: equal *increments* of `F` give equal increments of `g`; power: equal *ratios*. They
  diverge most for large `F` and at `F → 0` (power collapses every influenced vertex onto the
  pivot; linear keeps `1 − w`). With negative `F` (mirror) linear passes through `g = 0` at
  `w = 1/(1 − F)`, i.e. a ring of the influenced region collapses onto the pivot plane.
- S2. The E6 assumption "linear matches common DCC convention" remains **unverified** — no DCC
  was checked in this slice.

### 3.4 The Core placeholder blend (why `_on_update` is replaced)

`VertexTransformOperation._on_update` blends per step: `pos + w·(T(pos) − pos)`. Measured
(`w` = 0.25 / 0.5 / 0.75, total 90° about y, vertex at distance 1 from the pivot; total `F` for
scale):

| | 1 step | 60 steps | soft op (any step count) |
|---|---|---|---|
| Rotate, angle | 18.4° / 45° / 71.6° | 22.5° / 45° / 67.5° | 22.5° / 45° / 67.5° |
| Rotate, distance to pivot | 0.79 / 0.71 / 0.79 | 0.996 / 0.995 / 0.996 | 1 |
| Scale F=2, w=0.5 | 1.5 | 1.4156 | 1.5 (linear) / 1.4142 (power) |
| Scale F=10, w=0.5 | 5.5 | 3.197 | 5.5 (linear) / 3.162 (power) |

- B1. The blend's result depends on how many `update()` calls the drag happened to have (mouse
  event rate). With many small steps it approaches the weighted angle (with a small radius loss)
  and, for Scale, `F^w` — not `1 + w(F − 1)`. *(reading: the "power" formula is the continuous
  limit of the Core placeholder; that is a fact about the placeholder, not an argument for a
  default.)* Characterized by `test_core_placeholder_blend_is_not_path_independent`.

## 4. Observations — lifecycle, exactness, contracts

- L1. **Path independence (E8)**, measured 1 step vs 60 steps on the head (test case: radius 1.0 ≈ 30 %,
  euclidean, smooth, 101 influenced vertices): max deviation Move 2.5e-14, Rotate (constant axis) 9.5e-15, Scale linear
  3.7e-15, Scale power 3.6e-15. Tests assert ≤ 1e-12 (Scale ≤ 1e-11) — float rounding, not
  bit-exact; the Core ops themselves are not bit-exact path independent either.
- L2. How E8 is reached: Move and Rotate stay **incremental** (`w·Δ` is linear; rotations about one
  axis add up). Only Scale with `w < 1` is **evaluated absolutely** from the start snapshot with the
  factor accumulated since `begin()` (the linear formula has no multiplicative incremental form).
  `w == 1` vertices always take the Core's incremental arithmetic.
- L3. **Radius 0 ≡ Core, bit for bit**, for Move, Rotate (incl. changing axes), Scale (world and
  tilted basis): positions and the History command's start/end maps are `==`. Tested with the same
  explicit pivot handed to both; with the Core's *default* pivot the centroid's summation order
  follows set iteration order, which was not examined.
- L4. Rotate with an axis that changes between updates applies `w·θ_k` about `axis_k` per step —
  path dependent, exactly like the Core op. E8 is only claimed for a constant axis.
- L5. Scale needs **one basis for the whole gesture** (absolute evaluation decomposes the start
  offset in it). A different basis on a later `update()` raises `ValueError` before anything moves.
  The Core op accepts a new basis per update; the Production tools always pass the same one.
- L6. **Identity Rotate/Scale are not bit-exact in the Core.** `RotateOperation` with `angle = 0`
  or `ScaleOperation` with `factor = 1` and an explicit pivot changed 44 of 101 head vertices in the
  last bit (`pivot + (p − pivot) ≠ p`), so `commit()` returns a History entry for a visually empty
  gesture (29 of 101 with the default pivot). The soft ops inherit this
  (`test_identity_rotate_scale_round_like_core`). Begin → commit without update, and Move with a
  zero delta, return `None` as required.
- L7. Cancel restores the exact start positions; commit produces exactly one History entry whose
  start/end maps cover exactly the influenced set; undo/redo are exact; mesh invariants hold;
  `Selection` (mode, V/E/F sets, hover) is unchanged by begin → update → commit → undo → redo, in
  all three modes.
- L8. Axis/plane constraints arrive at the operation as already-constrained inputs (masked delta,
  factor triple with 1.0 on locked axes, a basis) — the tools do the constraining. Weighted: a
  locked Move component stays bit-exact (`w·0 = 0`); a locked Scale axis stays within 1e-12 (same
  `pivot + 1·(p − pivot)` rounding as L6).
- L9. Pivot (E7): the Core default pivot would be the centroid of the *influenced* set. Soft
  Rotate/Scale refuse to begin without `params["pivot"]`; `soft_context()` sets it to the seed
  centroid (`primary_pivot`, same arithmetic as `selection_pivot`).
- L10. Influence weights outside `(0, 1]` (incl. NaN) and a missing `params["influence"]` are
  refused at `begin()`; stale IDs in the map are skipped; an empty map is a no-op (`commit()` →
  `None`). `params["symmetry"]` present (even `None`) → `ValueError`, op stays inactive (E9);
  `supports_symmetry = False` on all three soft classes.

### 4.1 Private Core members used (E10 — to resolve before any promotion)

| Member | Where | How |
|---|---|---|
| `VertexTransformOperation._on_begin` (via the Move/Rotate/Scale chain) | `_SoftMixin._on_begin` | called with a **substitute context** whose `selection` is a view of the influenced set; relies on `_on_begin` reading only `target`, `selection.vertices`, `history`, `params` |
| `_on_update` of `VertexTransformOperation` / `_PivotTransformOperation` | all three soft ops | **overridden wholesale**: bypasses the placeholder blend and the seam check (safe only because E9 refuses symmetry) |
| `_weights` | `_SoftMixin` | overwritten after `begin()` with the influence map |
| `_mesh`, `_vertex_ids`, `_pivot` | all | read |
| `_start_positions` | `SoftScaleOperation` | read for the absolute evaluation of `w < 1` |
| `MoveOperation._transform_position` | `SoftMoveOperation` | called per vertex |
| `RotateOperation._apply`, `ScaleOperation._apply` | Rotate/Scale | called per vertex (Core arithmetic → radius-0 bit identity) |
| `core.operations.transform._as_triple` | — | **copied**, not imported |
| `RotateOperation._weights` | `test_core_placeholder_blend_is_not_path_independent` | written in a characterization test only |

Also: `Mesh.vertex_edges()` is avoided for cost reasons (N4), not for privacy.

## 5. Open questions for S2 (not decided here)

1. **Core seam.** Promote by changing the frozen Core (`_weights` blend → weighted parameters,
   possibly absolute Scale evaluation), or keep subclasses outside the Core with a public hook?
   Either needs an Architecture Decision (CORE_V1_FREEZE).
2. **Influence channel.** `params["influence"]` (like `pivot`/`symmetry`) vs a typed field; who
   computes it on the app path (tool `begin()`), and is the transient-at-begin rule (E2) enough
   once the viewport wants to *show* weights?
3. **Defaults** for metric, curve and scale formula: need an artist comparison in a window —
   S1 has only numbers (§3). Includes whether the finger/lip effect (M1/M2) matters in practice
   and whether the geodesic diamond on regular grids (M4) is visible.
4. **Radius**: units (world vs % of bounding radius vs screen), how it is set, and whether it
   lives per tool or globally.
5. **Identity gestures** create History entries in the Core already (L6) — accept, or compare
   with a tolerance in `commit()`?
6. **Basis contract** (L5): make "one basis per gesture" explicit in the Core interface, or keep
   incremental Scale for `w == 1` and absolute only for `w < 1`?
7. **Changing rotation axis** mid-gesture (L4): does any tool do it? If not, should the contract
   say constant axis?
8. **Symmetry combination** (refused here, E9): mirrored influence, seam vertices with `w < 1`.
9. **Cost on the reference PC**: probe run recorded (§2.1). `math.dist` is slow there (R6) and has
   been replaced (R7). Open: a reference-PC re-run after R7 before choosing a metric on cost grounds;
   the viewport share of a soft drag (N5) needs the app path.
10. Is a tolerance-free radius-0 identity (L3) still required once the pivot comes from the tool
    (default-pivot summation order)?

## 6. Not done in this slice

No window, binding, overlay, weight visualization, radius UI, Tweak, normal-direction magnet,
symmetry handling beyond refusal, or default choice. No change under `src/`, `playground/`,
`tests/`.
