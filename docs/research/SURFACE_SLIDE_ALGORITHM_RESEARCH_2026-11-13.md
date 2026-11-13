# Surface Slide — Algorithm Research and Validation (2026-11-13)

**Status:** research result, English, **no Production change and no decision**. The prototype is isolated in
[`experiments/surface_slide/`](../../experiments/surface_slide/README.md); nothing in `src/` imports it.
Every number below is in [`experiments/surface_slide/results/SUMMARY.md`](../../experiments/surface_slide/results/SUMMARY.md)
(generated from the raw JSON next to it) and the claims are pinned by 70 regression tests
(`python -m pytest experiments/surface_slide/tests -q`).

**Markers.** **[M]** measured in this prototype. **[T]** theory or assumption, not measured here.
**[O]** open decision for Manu. `h` is the mean edge length of the reference mesh; "0.1 h" means a tenth of an edge.

---

## 0. Result in one page

**Recommended algorithm: anchored geodesic slide with a speed-limited pursuit** (`geodesic_pursuit[transport]` in
the prototype).

1. At the start of a gesture the surface is captured as an **immutable triangle snapshot**.
2. Every moving vertex owns a **persistent anchor** on it: `(triangle, barycentric coordinates)`. A position is
   only ever *evaluated from* an anchor; nothing is projected back onto the surface, so a vertex cannot leave it or
   switch to a nearby unrelated part of it.
3. The drag is reduced to a tangent vector at the pivot vertex. Each vertex walks that vector — carried to it by a
   tangent transport and scaled by its soft-selection weight — as a **straightest geodesic from its start anchor**
   (the absolute, path-independent target).
4. Each vertex **pursues** its target along the surface at no more than twice the speed of its own drag. Where the
   target moves continuously the vertex *is* the target; where the target tears (it does, on coarse sculpted
   geometry, when the drag turns) the vertex slides after it instead of popping.
5. Under symmetry one half is driven and the other is written as its exact mirror image; seam vertices slide along
   the seam; the snapshot is triangulated mirror-symmetrically.

What the measurements say (details in §5–§11):

| Question | Finding |
|---|---|
| Does a global closest-point query jump on concave shapes? | **Yes, always, in the test.** On the U shape 200 of 200 vertices ended on the opposite wall, each with a deviation of 1e-15 h from "the surface" **[M]**. On the Gollum meshes it jumped between upper and lower lip (12 and 67 region jumps) **[M]**. |
| Do anchored geodesics stay on their region? | 0 wrong-wall vertices, 0 region jumps in all 76 scenarios; deviation from the tracked surface ≤ 7e-14 h; on the developable U the end point matches the exact unrolled answer to 1e-14 h **[M]**. |
| Absolute or incremental drag evaluation? | Neither alone. Incremental variants do not return: a closed loop of 3 edges diameter leaves vertices 0.2–6 h away from their start. The plain absolute geodesic returns exactly but moves single vertices up to 7× (cage) faster than the drag when the drag turns. The pursuit hybrid closes loops exactly and is capped at 2× **[M]**. |
| Is "interpolate between start and fully projected position" valid for soft selection? | No. Blended vertices are off the surface by up to 0.07 h on the sphere, 0.47 h on the U and 2.5 h on the Gollum cage. Scaling the *tangent vector* by the weight keeps every weight on the surface to 1e-15 h, and weight 0 does not move by a single bit **[M]**. |
| Shape preservation? | A fully selected patch moved with the transported vector is distorted 0.1 % on a cylinder (pure projection: 28 %, closest point: 43 %) and 2 % mean on a sphere after 3 edges; distortion grows with (distance / curvature radius)² **[M]**. |
| Is it fast enough? | In the container: capture 19 ms (5k vertices) to 403 ms (100k); an update for 1 000 affected vertices 3–7 ms, for 10 000 22–63 ms (drags up to 10 edges), independent of the mesh size; 830 bytes per reference vertex **[M]**. Not measured on the reference PC. |

Unresolved, stated plainly: the pivot does **not** stay under the cursor where the surface turns away from the view
(§11.3); a flat-facet reference loses volume over repeated gestures on coarse convex shapes unless the reference is
kept or evaluated smoothly (§10); Phong evaluation bulges at creases (§10.2); a slide that reaches a boundary stops
there (§13).

---

## 1. Scope and method

Algorithm research, not a tool. The geometry code knows no camera, mouse, GUI or `core.Mesh`; a candidate receives
the drag as a world-space vector since the gesture began, and all candidates run the same scenarios under the same
conditions (`harness.Scenario`: reference surface, moving vertices with weights, a fixed list of drag vectors per
frame).

Correctness is never judged by a picture and never by the global nearest-surface distance alone. The measurements
that carry the conclusions:

- **Tracked deviation** — distance from the output position to the reference surface, searched by adjacency descent
  *from the anchor the candidate reports*: the surface region it claims to be on.
- **Region check** — on the U shape the wall a vertex is on is known exactly from the unrolled chart; "wrong
  region" counts vertices not on the wall they must stay on.
- **Region jump** (candidate-independent) — consecutive frames whose anchors share no vertex and whose surface
  distance exceeds 3 × the step in space + 2 h: the vertex left its surface part without travelling there.
- **Step ratio** — |movement of a vertex in one frame| / |its own drag in that frame|. A slide never has to move
  faster than the drag; values far above 1 are pops.
- **Exact / analytic references** — the analytic sphere, cylinder and capsule; on the polyhedral U a geodesic is
  exactly a straight line in the unrolled (arc length, y) chart, which gives an exact end point.
- **Edge lengths** of the visible (polygon) edges with a moved end, against the same weights moved freely in space
  (the distortion the falloff alone causes), and separately for edges whose two ends carry weight 1.

---

## 2. Repository findings

What exists and matters for this tool (all read from the current code, 2026-11-13):

| Area | What is there | Consequence for Surface Slide |
|---|---|---|
| `src/core/mesh.py`, `core/operations/transform.py` | `Mesh` with `VertexId`-keyed positions (tuples), change journal (`begin_change` / `end_change`, `MeshDeltaCommand`). Core transform `update()` is incremental; weighted Scale / seam cases already evaluate absolutely from the `begin()` snapshot. Core imports no NumPy. | The slide belongs above the Core. Positions are written through the journal; one gesture = one history entry. |
| `src/mirai/topology/vertex_slide.py`, `loop_slide.py` | The existing slides: *pure planning + position math*, `Application` owns the gesture, "positions are always computed from the press state, so going back to the start restores it exactly"; under symmetry the normal's side is driven and partners are "written as exact mirrors"; the slide stops at 98 % so that two vertices never coincide. | The pattern to follow. It is also the reason this report weights "returns exactly to the start" highly. |
| `src/mirai/symmetry.py`, `symmetry_coordination.py` | Correspondence is derived from positions by **exact float equality**, no tolerance; a vertex on a declared seam edge is `SEAM`. | A mirrored vertex must be the exact mirror image of its partner, or the pairing breaks. Two vertices on one position are `AMBIGUOUS`. |
| `src/mirai/soft_selection/` | `compute_influence` (multi-source Dijkstra over mesh edges, `smooth` = 3t² − 2t³, weights in (0, 1]), `symmetric_influence` (pair-consistent weights, seam / falloff-seam categories, `in_plane_only`). | Reused as is for the weights. The slide needs one thing more from the same Dijkstra: the tree (parents), for the tangent transport. |
| `src/viewport/packed_geometry.py`, `render_mesh.py`, `derived.py` | Slot-indexed NumPy arrays (`P`, `VN`, `FN`, `corners`, `vertex_faces`); `triangulate_face` (fan from the first corner, ear clipping for concave polygons) is "the one place render, overlay, normals and picking take their triangles from". NumPy is pinned (2.2.6, AD-032) and allowed above the Core. | The reference snapshot is the same kind of array structure. Its triangulation is a decision (§9.3): the drawn one is not mirror-symmetric. |
| `src/mirai/surface_positions.py`, `Application._query_mesh` | Tools read the drawn *cage* (the morph mix when a target is dialled in) and write `scene.mesh`. | Which surface is the reference when a mix or pose is shown is an open rule **[O]** (`MODELING_ON_DEFORMED_SURFACES.md` R-6). |
| Spatial queries | No BVH / k-d tree / closest-point structure in `src/` (picking is GPU-based with a cache). | The recommended algorithm needs none. The projection candidates would. |
| Hardware | Reference PC (Core 2 Quad Q9550) runs Python / NumPy about 2× slower than the container (`REFERENCE_HARDWARE.md`). The audit of 2026-11-10 puts a moved vertex at about 0.03 ms through the Core write path. | Per-vertex Python loops are out; the tracer is batched on arrays. |

Assets: the real Gollum cage `scenes/Gollum_Head_01.mirai.json` (1 670 vertices; 1 520 quads, 46 triangles, 52
n-gons up to 24 corners; declared symmetry plane x = 0 with 69 seam edges; every vertex has an exact mirror
partner; 20 boundary edges) and `examples/meshes/gollum.obj` (21 875 quads, ZBrush). **Limitation:** the two are
different models in different places (cage vertices are 0.24 units from the dense mesh on average **[M]**), so
"cage slides on the dense sculpt" could not be tested with real data; both were tested sliding on themselves, and
sliding on a *different* reference was tested on spheres only (`test_points_of_another_mesh_slide_on_the_reference`).

---

## 3. Candidates

All take the absolute drag `d` (world vector since the gesture began); incremental ones difference it themselves.
`p0` start position, `w` weight, `n` a normal.

| Name | Update | Idea |
|---|---|---|
| `closest_global` | absolute | free move `p0 + w d`, then the globally closest surface point |
| `ray_normal` | absolute | free move, then along the start normal (both ways) to the nearest hit; a miss falls back to closest point |
| `ray_view` | absolute | free move, then along the view direction to the first hit ("face project") |
| `closest_local` | absolute target, local search | free move, then closest point by descent over triangle adjacency from the previous anchor |
| `tangent_local` | incremental | step projected into the tangent plane at the current anchor, then closest point by adjacency descent |
| `geodesic_inc` | incremental | step projected at the current anchor, walked as a geodesic from the current anchor |
| `geodesic_walk` | incremental | drag as a 2D vector in the start frame; its *change* is walked in a frame transported with the anchor |
| `geodesic_abs` | absolute | the whole drag as one geodesic from the *start* anchor (exponential map) |
| `geodesic_pursuit` | absolute + limiter | `geodesic_abs` is the target; the vertex pursues it along the surface at ≤ (1 + gain) × drag speed |
| `geodesic_seeded` | absolute | `geodesic_abs` picks the region, adjacency descent to the free-move target |
| `lerp(base)` | — | negative control for soft selection: `p0 + w (base(w = 1) − p0)` |

The geodesic candidates come in two **direction models**: `project` (each vertex takes the drag projected into its
own start tangent plane) and `transport` (the pivot takes its projected drag; every other vertex takes that vector
carried to it by a discrete parallel transport, then scaled by its weight). And two **evaluators**: `flat` (the
point on the triangle) and `phong` (Phong tessellation of the anchor, §10.2).

### 3.1 Advantages and disadvantages

| Candidate | For | Against |
|---|---|---|
| `closest_global` | Simple, stateless, path independent, standard in DCCs. Follows the cursor fairly well. | Jumps to the nearest surface whatever it is **[M]**; pops where the free move crosses the medial axis (step ratio up to 51) **[M]**; needs a spatial index; distorts a fully selected patch most of all candidates (13 % mean / 43 % max on the cylinder) **[M]**. |
| `ray_normal` | Stateless. | Same jumps; rays miss (102 fallbacks on the sphere at large drags) **[M]**; step ratio up to 74 **[M]**. |
| `ray_view` | The vertex is under the cursor by construction. | View dependent; jumps at every silhouette and occlusion (step ratio up to 10⁷); **moves occluded vertices at zero drag** (loop closure 0.76 h on the cage) **[M]**. |
| `closest_local` | No jump to unconnected surface **[M]**; cheap. | Still pops (step ratio 15–50) **[M]**; path dependent whenever the distance has several local minima (path spread 1.3 h on the cage nose) **[M]**; stalls at the bottom of a bend instead of following the surface **[M]**. |
| `tangent_local`, `geodesic_inc` | Continuous (step ratio ≈ 1), cheap per frame. | Drift: a closed drag does not return (0.2–6 h) **[M]**; the result depends on the path. |
| `geodesic_walk` | Continuous, exact on flat walls and across bends, cheapest of the geodesic family; a closed loop ends 2–3× closer to the start than with `geodesic_inc` (1.0 against 2.3 h on the cage, 2.3 against 6.1 h on the dense mesh) **[M]**. | Still path dependent on curved surfaces (path spread 0.04–3.4 h, not better than `geodesic_inc`) **[M]**; needs a snap at zero drag, which is a pop of the size of the drift (step ratio up to 10) **[M]**. |
| `geodesic_abs` | A function of the drag alone: no state, no drift, zero drag = start to the bit **[M]**; exact on developable surfaces **[M]**. | Pops when the drag *turns* on coarse geometry: the straight path flips to the other side of a strongly curved vertex (step ratio up to 7.4 on the cage, 18 under jitter) **[M]**; cost grows with drag distance. |
| `geodesic_pursuit` | Everything of `geodesic_abs` where it is continuous, and bounded speed where it is not (≤ 2.0 everywhere) **[M]**; loops close exactly **[M]**. | Carries state (current anchor); a vertex can lag behind its target when the drag stops right after a tear (10 of 37 vertices in the worst case measured, gone after 7 settle steps) **[M]**; costs one target trace plus a short pursuit trace for lagging vertices. |
| `geodesic_seeded` | Absolute. | Inherits the pops of the local projection (step ratio 44–50) and still made one region jump **[M]**: the hybrid in this direction buys nothing. |

### 3.2 Comparison over all scenarios

All 76 scenarios (53 for the `transport` variants, which need a pivot; 30 for `ray_view`, which needs a view).
Every figure is measured **[M]**; "update" is the mean per update for about 1 000 affected vertices dragged to 10
edges, over the five benchmark meshes.

| Candidate | wrong wall (of 200) | region jumps | largest step ratio | worst loop closure | result depends on the path | off the tracked surface | fallbacks | update, 1 000 vertices |
|---|---|---|---|---|---|---|---|---|
| `closest_global` | **200** | **296** | 51 | 0 | no | 2e-14 h | — | 71 – 349 ms (prototype grid) |
| `ray_normal` | **200** | **254** | 74 | 0 | no | 1e-13 h | 200 | not timed (brute force) |
| `ray_view` | — | **11** | 2e7 | 0.76 h | no | 7e-14 h | 25 | not timed (brute force) |
| `closest_local` | 0 | 0 | 50 | 0.25 h | yes | 2e-14 h | — | 7.0 – 8.3 ms |
| `tangent_local` | 0 | 0 | 1.5 | 6.1 h | yes | 1e-14 h | — | 6.2 – 8.2 ms |
| `geodesic_inc` | 0 | 0 | 1.0 | 6.1 h | yes | 1e-14 h | — | 1.0 – 1.3 ms |
| `geodesic_walk[transport]` | 0 | 0 | 1.0 (10 at the zero snap) | 2.3 h | yes | 6e-14 h | — | 1.1 – 2.2 ms |
| `geodesic_abs[transport]` | 0 | 0 | 7.4 (18 under jitter) | 0 | no | 7e-14 h | — | 3.8 – 5.8 ms |
| **`geodesic_pursuit[transport]`** | **0** | **0** | **2.0** | **0** | only while a vertex lags | 7e-14 h | — | 4.1 – 6.7 ms |
| `geodesic_seeded` | 0 | 1 | 50 | 0 | no | 2e-14 h | — | not timed |

No trace was flagged stuck or over the crossing limit, and no path reached a boundary, in any run.

Why the exponential map tears **[T]**: on a triangle mesh curvature sits in the vertices. Two straight paths that
pass a vertex on different sides are unfolded through different triangle fans and leave it at an angle equal to the
vertex's angle defect; behind the vertex they are `defect × distance` apart. On a dense smooth mesh the defects are
tiny (step ratio p99 1.04 on the 21 875-vertex Gollum **[M]**), on a coarse cage they are not (p99 2.8 **[M]**).
This is intrinsic to any path-independent map built from straight paths on a polyhedron; the incremental variants
trade it for path dependence. The pursuit keeps the absolute answer and limits the speed.

---

## 4. Prototype

```
experiments/surface_slide/
  refsurf.py      RefSurface: immutable snapshot (V, T, face normals, per-edge unit direction and inward
                  perpendicular, barycentric gradients, edge adjacency, vertex -> triangles, angle-weighted vertex
                  normals); closest point (uniform grid, exact) and by adjacency descent; flat / Phong evaluation;
                  mirror-symmetric triangulation
  geodesic.py     batch tracer: all rays advance one triangle per pass (NumPy)
  algorithms.py   the candidates behind  begin(setup) / update(delta) -> positions, anchors, flags
  fields.py       soft weights (array version of mirai.soft_selection.influence), tangent transport, mirror partners
  seam.py         slide along a curve of reference edges (the symmetry seam)
  geometries.py   sphere, cylinder, capsule, U - each with its analytic / exact reference
  mirai_io.py     read-only: Gollum scene through core.serialization, OBJ through examples/loaders
  scenarios.py, harness.py, metrics.py     76 scenarios, runner, measurements
  studies.py, bench.py, summarize.py, make_figures.py
  tests/          70 regression tests
```

**Tracer.** A ray is `(triangle, barycentric position, unit direction in the triangle plane, remaining length)`.
The barycentric velocity is `G[t] · direction` (`G` = gradients of the three barycentric coordinates, precomputed);
the first coordinate to reach zero names the exit edge. Crossing an edge relabels the two shared corners (the
position stays exactly on the edge) and *unfolds* the direction: its component along the edge is kept, its
component perpendicular to the edge now points into the neighbour (Polthier & Schmies 1998, straightest
geodesics). Start on a vertex — the normal case, a mesh vertex sliding over its own snapshot: the direction is
given in the vertex tangent plane; the incident triangle whose corner wedge contains it (seen along the vertex
normal) takes the ray and the direction is lifted onto it along the normal. A ray that reaches a boundary or
barrier edge stops there and is flagged; a ray that makes no progress for 64 crossings, or enters a degenerate
triangle, stops and is flagged. No flag of the second kind occurred in any scenario **[M]**.

**Transport.** One rotation per affected vertex: the product of the minimal rotations (normal → normal) along the
Dijkstra tree from the pivot. Exact on developable surfaces; on curved ones it depends on the tree path by the
enclosed curvature **[T]**. Computed once at `begin`.

**Pursuit.** Per update: trace the targets (absolute); per vertex `budget = (1 + gain) × |change of its tangent
vector|`; a vertex whose target is within its budget takes the target's anchor, any other walks `budget` towards it
(direction = the straight line to the target, projected into the current triangle). Zero drag restores the start
state exactly. `settle(max_step)` lets lagging vertices close in without any drag change.

Debug pictures (illustration only): [`results/img/`](../../experiments/surface_slide/results/img/).

---

## 5. Results per geometry

Aggregated over all scenarios of a group (full tables: `SUMMARY.md` §1; scenario list §2). Columns: largest
deviation from the tracked reference surface; vertices on the wrong region / region jumps; largest step ratio (and
its 99th percentile in the worst run); largest loop-closure error.

### 5.1 Sphere (cube sphere, 1 538 vertices, h = 0.091 R; 16 scenarios)

| Candidate | tracked dev | radial dev to the analytic sphere | step ratio max (p99) | to the analytic geodesic end | flags |
|---|---|---|---|---|---|
| `closest_global` | 4e-15 h | 0.026 h | 11.3 (3.2) | 20.9 h | — |
| `ray_normal` | 4e-15 h | 0.026 h | 66 (21) | 21.8 h | 102 fallbacks |
| `tangent_local`, `geodesic_inc` | 4e-15 h | 0.026 h | 1.0 | 3.6 h | — |
| `geodesic_abs`, `_walk`, `_pursuit` | 4e-15 h | 0.026 h | 1.0 | 0.18 h | — |
| `geodesic_pursuit[transport]+phong` | (0.025 h off the facets) | **0.00016 h** | 1.0 | — | — |

**[M]** All candidates sit on the *faceted* reference to rounding. The radial deviation of 0.026 h is the facet
sag h² / 8R of a vertex that left its own position (§10). The geodesic end point differs from the analytic
great-circle end point by 0.18 h after a drag of 13 edges (1.2 R) and converges with mesh density
(`test_sphere_exponential_map_converges`). The projection candidates end 21 h away from it on the large drags: for a
closed shape a free move through the interior crosses the medial axis and the closest point swings round the
sphere. Behaviour is the same in the three drag directions and at the valence-3 cube corners.

### 5.2 Cylinder and capsule (14 scenarios)

**[M]** Axial drags are exact for every candidate. Circumferential and helical drags separate the direction
models: a fully selected 3-ring patch dragged 3 edges round the barrel keeps its edge lengths to 0.1 % (mean and
max) with `transport`, changes them by 6 % mean / 28 % max with `project`, 13 % / 43 % with `closest_global`. With
`project` a vertex a quarter turn away from the pivot does not move at all (the drag is normal to the surface
there). Across the barrel / cap transition of the capsule the geodesic candidates stay continuous (step ratio ≤
1.07); `ray_normal` needs 8 fallbacks and reaches a step ratio of 17. Radial deviation from the analytic capsule:
flat 0.048 h, Phong 0.008 h (the remainder sits at the transition, where the curvature jumps).

### 5.3 Concave U (16 scenarios) — see §7

### 5.4 Gollum cage (1 670 vertices, h = 0.036; 15 scenarios: cheek, forehead, brow, eye rim, nose side, upper lip, temple; transitions cheek → eye, cheek → ear, forehead → brow, brow → socket, nose → cheek, lip → mouth, temple → eye; three fully selected patches; three closed loops)

| Candidate | tracked dev | region jumps | step ratio max (p99) | loop closure | rigid edges mean / max |
|---|---|---|---|---|---|
| `closest_global` | 2e-14 h | **12** | 47 (13.9) | 0 | 24 % / 99 % |
| `ray_normal` | 1e-13 h | **10** | 72 (13.6) | 0 | 26 % / 172 % |
| `ray_view` | 7e-14 h | **11** | 2e5 (30) | 0.76 h | 19 % / 88 % |
| `closest_local` | 2e-14 h | 0 | 44 (8.8) | 0.26 h | 24 % / 82 % |
| `tangent_local` | 7e-15 h | 0 | 1.5 | 2.2 h | 16 % / 87 % |
| `geodesic_inc` | 7e-15 h | 0 | 1.0 | 2.3 h | 15 % / 78 % |
| `geodesic_walk[transport]` | 6e-14 h | 0 | 1.0 | 1.0 h | 9 % / 63 % |
| `geodesic_abs[transport]` | 7e-14 h | 0 | 7.4 (2.8) | 0 | 9 % / 63 % |
| **`geodesic_pursuit[transport]`** | 7e-14 h | **0** | **2.0** (2.0) | **0** | 9 % / 63 % |

**[M]** The region jumps of the projection candidates are all in `D_cage_lip_down`: upper-lip vertices land on the
lower lip. Elsewhere they do not jump but pop: `closest_global` moves a vertex up to 47× faster than the drag at the
eye rim, 31× at the brow and the nose / cheek crease.

### 5.5 Gollum high resolution (21 875 vertices, h = 0.011; the same 15 scenarios)

| Candidate | tracked dev | region jumps | step ratio max (p99) | loop closure | rigid edges mean / max |
|---|---|---|---|---|---|
| `closest_global` | 1e-14 h | **67** | 51 (11) | 0 | 20 % / 104 % |
| `ray_normal` | 1e-14 h | **27** | 74 (16) | 0 | 15 % / 118 % |
| `closest_local` | 1e-14 h | 0 | 50 (4.1) | 0 | 21 % / 220 % |
| `geodesic_inc` | 1e-14 h | 0 | 1.0 | 6.1 h | 11 % / 63 % |
| `geodesic_walk[transport]` | 1e-14 h | 0 | 1.0 | 2.3 h | 6 % / 108 % |
| `geodesic_abs[transport]` | 1e-14 h | 0 | 4.3 (1.04) | 0 | 6 % / 108 % |
| **`geodesic_pursuit[transport]`** | 1e-14 h | **0** | **1.95** (1.04) | **0** | 6 % / 108 % |

**[M]** On the dense mesh the plain absolute geodesic is already nearly continuous (p99 1.04); the limiter acts on
a handful of vertices at the nose. The 108 % maximum is one edge in the cheek patch dragged 7 edges across the
nasolabial fold; forehead and brow patches: 1.9 % / 13 % and 3.5 % / 42 %.

---

## 6. Edge-length distortion

Three separate effects, measured separately **[M]**:

**(a) The falloff.** For a soft selection the edge-length change is dominated by the weights, not by the
algorithm: the surface slide and a free move in space with the same weights give the same distribution. Sphere
patch (weight bands, drag 2.5 edges): mean |Δl| / l 0.26 for the slide, 0.25 for the free move. Gollum cage, mean over
all 15 scenarios: 0.63 (slide) against 0.71 (free move). A smooth falloff of radius r dragged by d stretches by
up to 1.5 d / r; a drag larger than about r / 1.5 folds triangles in the falloff with *any* method (folded-triangle
counts are the same for slide and free move, `SUMMARY.md` §1). Distribution per scenario: `SUMMARY.md` §3.

**(b) The direction model**, isolated on fully selected patches (every weight 1, edges inside the patch):

| Patch, drag | `transport` | `project` | `geodesic_inc` | `closest_global` |
|---|---|---|---|---|
| Sphere face, 3 edges | 2.0 % / 8.4 % | 3.5 % / 9.9 % | 3.9 % / 9.4 % | 5.2 % / 13.0 % |
| Sphere face, 8 edges | 12.7 % / 35.7 % | 16.2 % / 37.4 % | 21.2 % / 32.0 % | 27.2 % / 51.7 % |
| Cylinder, round the barrel, 3 edges | **0.1 % / 0.1 %** | 6.1 % / 28.5 % | 7.8 % / 32.9 % | 13.2 % / 42.5 % |
| Cylinder, helix, 3.2 edges | 0.2 % / 0.4 % | 4.5 % / 21.2 % | 5.4 % / 24.5 % | 7.5 % / 32.1 % |
| Gollum cage cheek, 2.2 edges | 8.5 % / 18.2 % | 10.3 % / 20.2 % | 6.0 % / 13.6 % | 18.9 % / 66.2 % |
| Gollum cage forehead, 2.2 edges | 3.2 % / 10.2 % | 8.6 % / 17.4 % | 9.5 % / 22.3 % | 17.2 % / 57.5 % |
| Gollum cage brow, 1.7 edges | 15.7 % / 62.8 % | 18.2 % / 65.4 % | 29.0 % / 77.7 % | 34.9 % / 98.9 % |
| Gollum dense forehead, 7 edges | 1.9 % / 13.0 % | 15.8 % / 40.7 % | 13.2 % / 25.6 % | 12.5 % / 46.9 % |

(mean / max of |Δl| / l.) `transport` is an exact isometry on developable surfaces and the best or close to the
best everywhere else.

**(c) Curvature and distance.** Every vertex of a transported patch walks the same length. On a curved surface
that is not a rigid motion: paths that start parallel converge on positive curvature. The distortion grows like
(drag distance / curvature radius)² **[T]**, and the density sweep shows exactly that for a drag of 3 edges: 25.7 %
mean at 98 vertices, 7.5 %, 2.0 %, 0.5 %, 0.12 % at 24 578 vertices **[M]** (`SUMMARY.md` §4). The brow of the cage
(15.7 % after 1.7 edges) is the same effect on a coarse, strongly curved region.

Edge lengths are not enforced anywhere, and should not be: a slide redistributes them legitimately.

---

## 7. Concave-surface failure analysis

Test shape: a deep U — two parallel walls 2.0 high, joined by a half cylinder, extruded 2.0; gap 0.3 (three cells)
and 0.1 (one cell: the gap equals the edge length); bends of 8, 4, 2 and 1 segments (the last two are sharp
creases). The mesh unrolls without distortion, so the wall of every anchor and the exact geodesic end point are
known.

**Into the gap** (wall-A vertices dragged 0.6 at 30°, 60°, 80° off the wall, and along the extrusion with a
component into the gap; 8 scenarios, 200 vertex runs) **[M]**:

| Candidate | wrong wall | region jumps | deviation from "the surface" |
|---|---|---|---|
| `closest_global` | **200 / 200** | 200 | 1e-15 h |
| `ray_normal` | **200 / 200** | 200 | 2e-15 h |
| `closest_local`, `tangent_local` | 0 / 200 | 0 | 1e-15 h |
| all geodesic candidates | 0 / 200 | 0 | 2e-15 h; exact end point to 1e-14 h |

This is the failure the brief describes: the global projection reports a perfect surface deviation while every
vertex has changed wall. The switch happens the moment the free-move target passes the middle of the gap,
regardless of the angle. Picture: `results/img/u_into_gap_60deg.png`.

**Round the bend** (vertices 3 cells above the bend dragged 1.0 straight down) **[M]**: the absolute geodesic,
the walk and the pursuit follow the surface through the bend and up the other wall (exact to 1e-15 h); every
projection candidate and `geodesic_inc` stop at the bottom of the bend, 4–6 edges short — the free target left the
surface and its closest point stays there. Both behaviours are continuous; they are different meanings of "drag
down", and only the first is a slide *along the surface*.

**Sharp creases** (bend of 1 or 2 segments, drag across the crease) **[M]**: no instability in any anchored
candidate; the geodesic end point stays exact (1e-16 h). The hinge unfolding does not care how sharp an edge is.

**Soft patch astride the bend** **[M]**: with `project` every vertex follows the world direction "down" in its own
tangent plane, so vertices on the two walls move in opposite directions along the surface and the patch tears and
folds at the bend (47 folded triangles, edge stretch 388 % at gap = 1 cell). With `transport` the patch moves
round the bend as one piece (2 folded triangles, the same as the free move; max stretch 100 %). `closest_local`
keeps its wall but pops (step ratio 15.6 into the gap): a local projection is not a continuous one.

**On Gollum** the same failure appears wherever two surfaces are close: `D_*_lip_down` (12 jumps on the cage, 67
on the dense mesh for `closest_global`; picture `results/img/D_cage_lip_down.png`). The anchored candidates have 0
region jumps in all 76 scenarios.

Why the anchor works **[T]**: the anchor's triangle can only change by crossing an edge into the adjacent triangle.
Surface parts that are close in space but far along the surface are never adjacent, so there is no operation by
which a vertex could reach them without travelling there.

---

## 8. Stability: incremental against absolute, drift, continuity

Two experiments on five cases (sphere patch, U patch, Gollum cage cheek and nose side, Gollum dense cheek)
**[M]** (`SUMMARY.md` §6):

- **Path spread** — the same final drag (3.5 edges) reached straight, by a dog-leg and by a detour; largest
  difference between the end positions.
- **Jitter** — 300 random steps of about a third of an edge that end at zero drag; closure error and step ratio.

| Candidate | path spread (5 cases) | jitter closure max | jitter step ratio max |
|---|---|---|---|
| `closest_global` | 0 | 0 | 1.9 / 26 / 29 / 28 / 10 |
| `closest_local` | 0 / 0.19 / 0 / 1.34 / 0 h | 0 | 1.9 / 4.8 / 13.5 / 20 / 10 |
| `tangent_local` | 0.16 / 0.03 / 0.26 / 1.84 / 0.11 h | 0.22 / 1.24 / 0.56 / 3.43 / 0.25 h | ≤ 1.4 |
| `geodesic_inc` | 0.16 / 0.03 / 0.22 / 1.96 / 0.09 h | 0.22 / 1.23 / 4.06 / 3.28 / 0.21 h | 1.0 |
| `geodesic_walk[transport]` | 0.16 / 0.04 / 0.67 / 3.43 / 0.34 h | 0 (snap at zero) | 1.05 / 1.0 / 2.1 / 10.3 / 2.3 (the snap) |
| `geodesic_abs[transport]` | 0 | 0 | 1.0 / 1.02 / 2.4 / **17.8** / 1.6 |
| **`geodesic_pursuit[transport]`** | 0 / 0 / 0.03 / 1.43 / 0 h | 0 | 1.0 / 1.02 / 2.0 / **2.0** / 1.6 |

Readings:

- **Incremental evaluation drifts.** Re-projecting the step at the current normal (`tangent_local`,
  `geodesic_inc`) loses the most on a closed drag (up to 4.1 h): the projection changes along the way, so
  increments that cancel in space do not cancel on the surface. Walking in a transported frame removes that error
  source and leaves the curvature enclosed between two paths **[T]**; measured, its path spread is small on the
  sphere and the U (0.16 and 0.04 h) and as large as the others' on the cage (0.67 and 3.4 h). The 0.04 h on the
  developable U comes from vertices that start on the bend, where the first step is lifted from the vertex tangent
  plane onto whichever facet it enters **[T]**.
- **The plain absolute geodesic pops** when the drag direction changes on coarse geometry (17.8× on the cage
  nose).
- **The pursuit** has the absolute result wherever every vertex has caught up — path spread exactly 0 on the
  sphere, the U and the dense Gollum — and a bounded lag otherwise. In the worst case (cage nose, detour path) 10
  of 37 vertices were still behind their target when the drag stopped, the farthest by 1.43 h; 7 `settle` steps of
  a quarter edge brought all of them onto the absolute answer (gap 0) **[M]**.
- **Numerical drift**: none beyond rounding. Running the 300-step jitter twice gives the same bits for every
  candidate. The absolute geodesic gives the same bits for a drag whatever path led to it
  (`test_absolute_geodesic_is_a_function_of_the_drag_alone`), and zero drag returns the start positions exactly.
- **Frame-to-frame discontinuities** are what the step ratio measures; region jumps are listed in §5 and §7.

---

## 9. Symmetry

Cases: sphere, U, and three places on the Gollum cage (nose side, upper lip, forehead) with the seed on the +x
side and a falloff that reaches across the plane (`SUMMARY.md` §7).

### 9.1 Mirrored positions and movement consistency

Two ways to move the other half were compared: **(I)** solve both halves independently with mirrored drags, and
**(M)** solve the driven half and write the other as its mirror image.

**[M]** With a mirror-symmetric triangulation, (I) and (M) agree to 3e-15 – 2e-14 h for the transport candidates
on all five cases, including after a 120-step wiggly drag with the incremental walk — no accumulated asymmetry
beyond rounding. Two things break (I):

- **An asymmetric triangulation.** With the per-face rules (shorter diagonal, ear clipping) 200 of the cage's
  3 318 triangles have no mirror image, and the two independently solved halves end **1.1 h** apart after a
  straight 3-edge drag and up to **3.6 h** after a wiggly one (`geodesic_abs` 2.3 h, `geodesic_walk` 3.6 h).
- **Degenerate paths.** On the sphere a drag exactly along a mesh line runs through vertices; which side of a
  vertex a path passes is a tie the two halves break differently: 0.01 h asymmetry for `geodesic_abs[project]` on
  an otherwise exactly symmetric reference.

(M) is exact by construction (`mirror(mirror(p)) == p` to the bit), costs half, and is what `vertex_slide.py` and
`loop_slide.py` already do. Mirai's correspondence needs exact equality, so (M) is the only option that keeps
every pair a pair.

### 9.2 Do mirrored vertices stay on their reference region?

**[M]** The mirror image of a driven result lies on the *mirror image of the reference*. That is the reference
itself only if the triangulation is symmetric:

| Cage triangulation | triangles without a mirror image | mirrored result off the reference (max) |
|---|---|---|
| per-face rules | 200 / 3 318 | 0.158 h |
| mirrored across the plane | 0 / 3 318 | 5.7e-15 h |

Hence: when a symmetry definition exists, triangulate the driven half and copy that triangulation, mirrored, to
the other half (`refsurf.triangulate(V, faces, partner)`). The triangulation itself matters more than one might
expect, because the cage's quads are not planar **[M]**: the shorter-diagonal rule and the fan from the first
corner (what `viewport.derived.triangulate_face` draws for convex faces) cut 1 524 of 3 318 triangles differently,
and the two surfaces are 0.014 h apart on average, 0.07 h at the 95th percentile and 0.25 h at most; mirroring the
triangulation changes 100 triangles by up to 0.34 h. So the reference a vertex slides on and the surface the
artist sees are the same only if they use the same triangulation **[O]** (`SUMMARY.md` §5, last table).

### 9.3 Seam vertices

**[M]** A seam vertex must stay on the plane. Measured ways to get there:

| Method | off the plane before a snap | off the surface after snapping to the plane |
|---|---|---|
| free drag, then snap | 0.07 – 3.1 h | 0.01 – 1.6 h |
| drag and start normal projected into the plane, geodesic, then snap | 0.02 – 0.41 h | 0.002 – 0.095 h |
| **slide along the seam polyline (`seam.py`)** | exactly 0 | exactly 0 |

A geodesic started in the plane does not stay in it: the seam runs through nothing but vertices, and the tracer
passes a vertex on one side. The seam vertices therefore get their own one-dimensional slide: walk the chain of
seam edges by the component of the tangent vector along it. Every point of the chain is on a reference edge whose
two ends have their plane coordinate exactly on the plane, so the result is on the surface and on the plane by
construction (280 walks on the cage: largest |x| = 0, largest distance to the reference = 0; 5 stopped at an end of
the seam).

### 9.4 Movement across the plane

**[M]** A drag of 6 edges towards the plane, free: 10–24 driven vertices of the three cage cases end on the far
side; their partners cross the other way and the two halves interpenetrate (positions stay exact mirror pairs,
deviation from the surface 3e-15 h). With the seam edges as a **barrier** in the adjacency: none crosses, the
tracer stops them at the seam and flags them — but they stop *exactly on the plane* (10–24 vertices with x = 0),
where they coincide with their partner, which Mirai's correspondence would report as `AMBIGUOUS`. A barrier
therefore needs a back-off (the existing slides stop at 98 % for the same reason) **[O]**.

---

## 10. The reference surface

### 10.1 An immutable snapshot, and what it costs

All candidates slide on a snapshot taken at `begin`; its arrays are read-only (`test_reference_arrays_are_read_only`).
That makes the gesture well defined (the surface does not move under the vertices that slide on it), makes cancel
trivial, and makes the absolute evaluation possible at all.

The cost: a vertex that leaves its own position on a **flat-facet** snapshot of a convex region sinks below the
smooth shape by the facet sag, about h² / 8R **[M]** (sphere: 0.091 h at 98 vertices, 0.010 h at 1 538, 0.002 h at
24 578). One gesture is harmless; **repeated gestures on fresh snapshots accumulate** **[M]** (60 random
gestures, each a soft patch of radius 3 h dragged 1.5 h):

| Sphere, 386 vertices (h = 0.18 R) | mean radius | min radius |
|---|---|---|
| new flat snapshot per gesture | 0.9871 | 0.949 |
| new snapshot per gesture, Phong evaluation | 0.9987 | 0.968 |
| one flat snapshot kept, anchors kept | 0.9953 | 0.991 |
| one snapshot kept, Phong evaluation | 1.0000 | 0.9998 |

(1 538 vertices: 0.9993 / 0.991, 1.0000 / 0.998, 0.9995 / 0.998, 1.0000 / 1.0000.) With a kept reference the loss
is bounded by one facet sag however many gestures follow, because every vertex is always evaluated from the same
surface; with re-snapshotting the mesh erodes like a smoothing filter. On the Gollum cage there is no analytic
shape to compare against; measured against the original flat cage the moved vertices are on average 0.036 h
(at most 0.36 h) away after 60 re-snapshotted gestures, and exactly 0 with a kept flat reference (they are evaluated
from it).

### 10.2 Flat or Phong evaluation

Phong tessellation (Boubekeur & Alexa 2008) evaluates an anchor as the flat point pulled towards the tangent
planes of the triangle's three vertices: `p − α Σ b_k ((p − V_k)·n_k) n_k`. It interpolates the vertices (a vertex
that has not moved keeps its exact position), is continuous across edges, and needs only vertex normals.

**[M]** With α = 0.5 it reproduces the sphere to fourth order: radial deviation 2.3e-3, 1.2e-4, 5.0e-6, 2.4e-7,
1.4e-8 for the five densities, against 3.3e-2 … 5.0e-5 flat. The usual α = 0.75 only halves the flat error (it
overshoots outward); α = 0.5 is the value to use **[M]**, consistent with a quadratic curve through two points
with given tangents **[T]**.

**[M]** The price is paid at creases, where a vertex normal averages two unrelated faces: on the U with a
one-segment bend the Phong point leaves the flat wall by 0.37 h, with two segments 0.22 h, with
eight 0.03 h. On the Gollum cage it is 0.06–0.19 h off the facets in most scenarios and 0.49 h at the eye rim
(n-gon cap, sharp lid edges). Whether that is "the intended surface" or an artefact depends on the region; a
crease-aware normal (do not average across edges above an angle) is the standard fix and was not built **[T]**.

### 10.3 What the reference should be **[O]**

Measured facts above; the choice is an Artist decision:

- **Flat, per gesture** — exactly the existing faceted surface; no surprise at creases; erodes coarse convex
  regions over many gestures.
- **Flat, kept** (captured when the tool is entered or on request, dropped on any topology change) — bounded loss;
  repeated slides are consistent with each other; the artist must understand that the reference is older than the
  mesh.
- **Phong** (either lifetime) — keeps smooth shapes to fourth order; rounds creases unless made crease-aware.
- A reference that is **another object** (retopology over a sculpt) uses the same code path with closest-point
  anchors at `begin`; only tested on spheres (§2).
- With the **SubD preview** on, the artist looks at the limit surface but slides the cage. Not investigated.

---

## 11. Soft selection

### 11.1 Weights **[M]**

Weight bands 1 / 0.5 / 0.25 / 0 by ring around a seed, drag 2.5 edges (`SUMMARY.md` §8):

| Case | `geodesic_pursuit[transport]`: off the surface, w = 0.25 / 0.5 / 1 | travel relative to w = 1 | `lerp(geodesic)`: off the surface, w = 0.25 / 0.5 | `lerp(closest_global)` |
|---|---|---|---|---|
| Sphere | 3e-15 h each | 0.25 / 0.50 exactly | 0.047 / 0.070 h | 0.046 / 0.071 h |
| U near the bend | 3e-16 h | 0.26 / 0.52 | 0.32 / 0.47 h | 0.13 / 0.22 h |
| Gollum cage cheek | 5e-15 h | 0.26 / 0.52 | 1.17 / 0.92 h | 1.14 / 1.25 h |
| Gollum cage brow | 4e-15 h | 0.36 / 0.63 | 1.21 / 0.89 h | **2.53** / 1.58 h |
| Gollum dense cheek | 3e-15 h | 0.25 / 0.50 exactly | 0.13 / 0.20 h | 0.16 / 0.23 h |

- **Every weight is on the surface** with the geodesic candidates, because the weight scales the tangent vector
  and the vertex then walks: there is no interpolated point that could be off it.
- **Weight 0 does not move by one bit** for any candidate.
- **The linear blend is not on the surface** — a chord point, up to 2.5 edges off on the cage. (Travel is measured
  as the straight line between start and end; the *path length* is exactly w × the pivot's. On the brow the path
  bends over the ridge, so the straight-line ratio reads 0.36 instead of 0.25.)
- **Coherence**: with `transport` the travel is the same for all vertices of a band (min = max on sphere and dense
  mesh); with `closest_global` it varies within a band (0.00 – 0.30 for w = 0.25 at the U bend: some vertices do not
  move at all) and it pops (step ratio 7.8 – 15 on the cage).
- **Different weights do not create projection problems** with the anchored candidates: 0 region jumps, step
  ratio 1.0 in all five cases. `lerp(closest_global)` reaches a step ratio of 60.
- **Local distortion** is the falloff's (§6a): edges mean / max 0.32 / 2.42 for the slide on the cage cheek against
  0.30 / 2.62 for the free move.

### 11.2 Scaling to large regions **[M]**

Cost is linear in the affected vertices; see §12 (100, 1 000 and 10 000 affected vertices).

### 11.3 The pivot against the cursor (not solved) **[M]**

The projected tangent vector is shorter than the drag wherever the surface is tilted against the view, so the
pivot lags behind the cursor: on the 18 front-view drags it covers between 0 % (upper lip: "down" on the lip runs
into the mouth, sideways on screen) and 92 % of the drag on screen (`SUMMARY.md` §9). `closest_global` follows
better (9–129 %) and `ray_view` exactly — at the price of §5.

A first attempt at a fix — solve, per frame, for the pivot tangent vector whose geodesic end lies under the cursor
(damped Newton, two unknowns, 8–26 traces of one point per frame) — ends within 10 % of the cursor in 10 of 18
drags and fails in the others (lip, eye socket, silhouette: the surface under the cursor is not reachable by a
continuous path, and the solve stalls or races, once at 112× cursor speed). It shows the mapping can live outside
the algorithm (the core takes a tangent vector, §14.4) but it is **not** a validated solution. Recommended first
version: the same screen-drag-to-world mapping the Move tool uses, projected at the pivot.

---

## 12. Performance

Container (4 × Xeon 2.3 GHz, Python 3.13, NumPy 2.5.3), wall clock, single thread; the reference PC is about 2×
slower for this kind of code (`REFERENCE_HARDWARE.md`) and **was not measured**. Meshes: cube spheres with 5 048,
20 186 and 99 848 vertices, the Gollum mesh with 21 875 vertices and its 87 500-vertex subdivision
(`experiments/drag_cost/fixtures/gollum_87k.obj`). Full tables: `SUMMARY.md` §10.

**Setup (once per reference) [M]**

| Mesh | triangulate | reference arrays | tracer arrays | build peak |
|---|---|---|---|---|
| 5 048 vertices | 4.8 ms | 19 ms | 4.2 MB | 12 MB |
| 20 186 | 11.7 ms | 75 ms | 16.8 MB | 49 MB |
| 21 875 (Gollum) | 15.4 ms | 86 ms | 18.2 MB | 54 MB |
| 87 500 (Gollum) | 53.8 ms | 387 ms | 72.6 MB | 214 MB |
| 99 848 | 61.5 ms | 403 ms | 82.9 MB | 244 MB |

About 4 ms and 830 bytes per 1 000 / per vertex; linear. The closest-point grid the projection candidates need
costs another 5 – 96 ms and 0.3 – 10 MB; the recommended algorithm does not need it.

**Begin (once per gesture) [M]**

| Affected vertices | weights (Dijkstra) | transport frames (Python loop in the prototype) |
|---|---|---|
| ~100 | 0.2 – 0.3 ms | 2.3 – 3.7 ms |
| ~1 000 | 1.2 – 3.5 ms | 21 – 35 ms |
| ~10 000 | 13 – 34 ms | 212 – 275 ms |

**Per update [M]** — a drag simulated in frames of half an edge from zero out to the given distance; mean over the
frames (in brackets: the last, most expensive frame of the 30-edge drag). Ranges are over the five meshes.

| Candidate | affected | drag to 2 h | to 10 h | to 30 h |
|---|---|---|---|---|
| `geodesic_pursuit[transport]` | ~100 | 0.65 – 0.96 ms | 1.4 – 2.1 ms | 3.2 – 4.6 ms (5.5 – 7.7) |
| | ~1 000 | 2.7 – 5.2 ms | 4.1 – 6.7 ms | 8.6 – 15.1 ms (13.7 – 27.6) |
| | ~10 000 | 22 – 37 ms | 37 – 63 ms | 66 – 119 ms (101 – 195) |
| `geodesic_walk[transport]` | ~100 / 1 000 / 10 000 | — | 0.4 – 0.6 / 1.1 – 2.2 / 7.0 – 11.6 ms | same (independent of distance) |
| `closest_local`, `tangent_local` | ~100 / 1 000 / 10 000 | — | 1.0 – 1.9 / 6.2 – 8.3 / 94 – 116 ms | same |
| `closest_global` (prototype grid) | ~100 / 1 000 | 4.9 – 28 / 77 – 355 ms | 4.6 – 20 / 71 – 349 ms | not timed |

Readings **[M]**:

- **The cost does not depend on the mesh size**, only on the affected vertices and the triangles their paths
  cross: 100 affected vertices cost 0.75 ms on the 5k mesh and 0.96 ms on the 100k mesh.
- **It grows with the drag distance** for the absolute evaluation (every update re-traces from the start): 2.2 –
  3.7 µs per vertex at 2 edges, 6.6 – 11.9 µs at 30 edges (10 000 affected). The incremental walk stays at about
  0.7 – 1.2 µs per vertex but drifts (§8).
- **Phong evaluation is free** within the noise (37.5 against 37.5 ms at 10 000 affected on the 100k mesh).
- **The pursuit adds little** over the plain absolute geodesic (0 – 35 %, mostly the bookkeeping).
- **Interactive range.** Up to about 1 000 affected vertices an update is 3 – 7 ms for drags of up to 10 edges —
  inside a frame even at half the speed. At 10 000 affected vertices it is 22 – 63 ms: usable, not smooth. For
  comparison, the audit of 2026-11-10 measured about 0.03 ms per *moved vertex* for the existing write path on the
  reference PC ("16.7 ms buys ≈ 550 – 600 moved vertices"); the slide computation (0.002 – 0.012 ms per vertex here)
  is the smaller part of a frame at every size **[T]** for the comparison across machines.
- **The largest fixed cost is the transport** at `begin` (a Python loop of 3 × 3 products in tree order): 0.2 – 0.3 s
  for 10 000 vertices. It is the first thing to vectorise (§14.7).
- `closest_global` is slow here because the prototype's grid falls back to brute force for targets far from the
  surface; its numbers are an upper bound for a real spatial index, not a verdict.

---

## 13. Known limitations and unresolved problems

1. **Cursor fidelity** (§11.3). Unsolved; the naive solve works in 10 of 18 cases.
2. **Pursuit lag.** A vertex can be behind its target when the drag stops (worst case 1.43 h, 10 of 37 vertices).
   `settle()` removes it in a few steps; who calls it — an idle tick, or the commit — is a host decision **[O]**.
   The pursuit direction is the straight line to the target projected into the current triangle; across a thin
   feature that could point the wrong way. It did not happen in the scenarios; it is not proven impossible **[T]**.
3. **Shape over long drags.** A transported patch is not rigid on curved surfaces: 13 % mean edge change after 8
   edges on the sphere (§6c). A correction (re-deriving the frames from the moved pivot, or a local conformal map
   of the patch) was not investigated.
4. **Boundaries.** A path that reaches a boundary edge stops there (flagged); a boundary vertex dragged outward
   does not move (flagged). Sliding *along* a boundary was not built. No scenario hit a boundary by accident; the
   cage's 20 boundary edges are inside the eye and mouth openings.
5. **Erosion and creases** (§10): flat facets erode over repeated gestures; Phong rounds creases.
6. **Symmetry**: barrier back-off (§9.4) and the triangulation used for drawing against the mirrored one (§9.2)
   are open. Seam ends (5 walks stopped) need a rule.
7. **Non-manifold and inconsistently wound input.** An edge with more than two triangles is treated as a
   boundary; a flipped neighbour is handled by the crossing code but untested (none of the test meshes has one).
8. **Deformed surfaces.** Which surface is the reference while a morph mix or a pose is shown, and how the result
   maps back to rest space, is not addressed (`MODELING_ON_DEFORMED_SURFACES.md` R-6).
9. **Reference PC.** Nothing ran on the Q9550; NumPy here is 2.5.3, the pinned Production version is 2.2.6. The
   code uses only long-standing NumPy functions (`einsum`, `lexsort`, `bincount`, `cross`, fancy indexing) **[T]**.
10. **Gollum as a foreign reference** could not be tested (§2).

---

## 14. Recommendation for Production

### 14.1 Algorithm

`geodesic_pursuit[transport]`, flat evaluation, snapshot per gesture, as the first version; reference lifetime
and Phong evaluation as decided in §10.3 **[O]**.

Why it suits Mirai:

- **Reliability by construction.** The anchor cannot change region without travelling there; there is no
  projection step that could fail and therefore no fallback path to get wrong.
- **It matches the existing slides.** Positions are a function of the press state; returning the drag to zero
  restores the mesh to the bit; cancel is the stored start positions. The speed limit is the only state, and it
  only matters on coarse, strongly curved regions.
- **It reuses what exists.** Weights from `compute_influence` / `symmetric_influence`; mirror partners from
  `SymmetryIndex`; the journal for history; NumPy arrays of the kind `PackedGeometry` already holds. No new
  dependency, no spatial index.
- **It is independent of viewport, GUI and mouse**: input is a vector, output is positions by vertex.

### 14.2 Data structures

| Structure | Content | Size |
|---|---|---|
| `SlideReference` (immutable) | `V (nv, 3)`, `T (nt, 3)`, face normals, per (triangle, edge): unit direction `E`, unit inward perpendicular `Pin`, barycentric gradient `G`; adjacency `nbr`, `nbr_k`; vertex → incident triangles (CSR); vertex normals `VN`; `VertexId` ↔ row maps | 830 bytes per vertex **[M]** |
| Anchor | `tri: int`, `bary: 3 × float64` (sum 1, each ≥ 0); "on vertex v" is `bary` with an exact 1.0 | 32 bytes per moving vertex |
| Gesture state | start anchors and positions, weights, pivot row, transport rotation per vertex (3 × 3, or one angle in a local frame), current anchors (pursuit), `lagging` mask | ~200 bytes per moving vertex |
| Seam | the chain of seam edges as vertex adjacency, one triangle per seam edge | per seam edge |

### 14.3 Rules

- **Reference.** Built from the surface the tool reads, at `begin`, never written. Triangulated mirror-symmetrically
  when the mesh has a symmetry definition. Dropped at commit / cancel (or kept per §10.3). Any topology change
  invalidates it.
- **Symmetry.** Expand the selection as `symmetric_influence` does. Drive the vertices on the normal's side and the
  seam; write each partner as `mirror_position(result)` — exact pairs. Seam vertices slide on the seam polyline
  with the in-plane component of their tangent vector; their plane coordinate is written exactly. Seam edges are
  barriers for non-seam vertices, with a back-off from the plane **[O]**. A seed without a unique partner refuses
  the gesture before anything moves, as today.
- **Soft selection.** Weights at `begin` from the start positions, as today (geodesic metric, pair-consistent
  under symmetry). The weight scales the tangent vector. The pivot is the vertex the gesture was started on (or the
  seed nearest the seeds' centroid); the transport tree is the Dijkstra tree from the pivot — one more output of
  the search that already runs.
- **Mask** (as in `vertex_slide.py`): multiply the weight by `1 − mask`.
- **Failure and fallback.** Never fall back to a global projection. A vertex whose trace is flagged `boundary`
  keeps the point where it stopped; `blocked` keeps its start; `stuck` / `maxiter` (never observed) keeps its last
  valid anchor and is reported. If the reference cannot be built for the whole surface (non-manifold edges inside
  the affected region), refuse the gesture with a status line. Every flag is returned per vertex so the host can
  show it.
- **History.** One gesture = one `MeshDeltaCommand` (journal), like Vertex Slide. Anchors are not stored in
  history; they are derived state of the gesture.

### 14.4 Interface contract (proposal, names provisional)

```python
# src/mirai/surface_slide/  (pure: no viewport, no GUI, no input types; NumPy through the guarded import)

class SlideReference:
    """Immutable triangle snapshot of a surface. Building it never touches the mesh."""
    @classmethod
    def capture(cls, surface, *, mirror_partner: Mapping[VertexId, VertexId] | None = None,
                seam_edges: Iterable[EdgeId] = ()) -> "SlideReference": ...
    # `surface`: anything with the Mesh query API (core.Mesh, SurfacePositions)
    def anchor_at_vertex(self, vertex: VertexId) -> Anchor: ...
    def evaluate(self, anchors, *, smooth: bool = False) -> positions: ...

@dataclass(frozen=True)
class SlidePlan:                       # what one gesture moves; fixed at begin
    driven: tuple[VertexId, ...]       # walk the surface
    weights: Mapping[VertexId, float]  # in [0, 1]; 0 = in the set, never moves
    pivot: VertexId
    seam: frozenset[VertexId]          # driven, slide on the seam curve
    mirrors: Mapping[VertexId, VertexId]   # written as the exact mirror of a driven vertex
    plane: tuple[Position, Position] | None

def plan_surface_slide(mesh, seeds, *, influence=None, mask=None, blocked=frozenset()) -> SlidePlan:
    """Raises SurfaceSlideRefused (the message is the status line)."""

class SurfaceSlide:
    def __init__(self, reference: SlideReference, plan: SlidePlan, *, gain: float = 1.0, smooth: bool = False): ...
    def tangent_of(self, delta: Position) -> tuple[float, float]:
        """The drag projected into the pivot's start tangent plane, in the pivot frame (linear in delta)."""
    def update(self, tangent: tuple[float, float]) -> SlideFrame: ...
    def settle(self, max_step: float) -> SlideFrame: ...
    def start_positions(self) -> dict[VertexId, Position]: ...      # cancel

@dataclass(frozen=True)
class SlideFrame:
    positions: Mapping[VertexId, Position]   # driven and mirrored vertices: write these
    flags: Mapping[VertexId, int]            # BOUNDARY | BLOCKED | STUCK | LAGGING, absent = clean
    lagging: int
```

Contract:

1. `update` is a function of `tangent` and of the previous call only through the speed limit; `update((0, 0))`
   returns the start positions bit for bit and clears all state.
2. Every returned position of a driven vertex is `reference.evaluate(anchor)` for an anchor on the reference; no
   position is ever produced by projection.
3. A vertex moves at most `(1 + gain) × weight × |Δtangent|` per call (flat evaluation).
4. Weight-0 vertices are returned unchanged or not at all.
5. `positions[m] == mirror_position(positions[v])` exactly for every `m -> v` in `plan.mirrors`; seam vertices
   have their plane coordinate exactly on the plane.
6. The reference is not modified by any call. Nothing here reads a camera or a pointer.
7. `Application` owns the gesture (press / drag / release / Esc), maps the pointer to `delta` as the Move tool
   does, writes `positions` through the journal and pushes one history entry at release.

### 14.5 Pseudocode

```
begin(reference, plan):
    for each driven vertex i:
        start[i]  = reference.anchor_at_vertex(i);  current[i] = start[i]
        R[i]      = product of minimal rotations (normal -> normal) along the Dijkstra tree pivot -> i
    t_prev = 0

update(tangent u):                                   # u: 2D, pivot frame
    if u == 0: restore start state; return start positions
    t_p = u.x * e1_pivot + u.y * e2_pivot            # 3D vector in the pivot tangent plane
    for each driven vertex i:                        # (batched on arrays)
        t[i] = weight[i] * project_to_tangent_plane(R[i] * t_p, normal[i])
        if i is a seam vertex:
            target[i] = walk_seam_polyline(i, t[i])
        else:
            target[i] = trace(start[i], direction = t[i] / |t[i]|, length = |t[i]|)
        budget = (1 + gain) * |t[i] - t_prev[i]|
        if |point(target[i]) - point(current[i])| <= budget:
            current[i] = target[i]
        else:
            g = point(target[i]) - point(current[i])
            current[i] = trace(current[i], direction = tangent part of g, length = budget);  mark lagging
    t_prev = t
    positions = { i: evaluate(current[i]) }  +  { m: mirror(positions[v]) for m -> v in mirrors }

trace(anchor, direction d, length L):                # straightest geodesic
    if anchor is a vertex v:
        f = the incident triangle whose corner wedge at v contains d, seen along normal[v]
        d = d lifted onto f along normal[v];  b = corner of v
    loop:
        db   = G[f] . d                               # barycentric velocity
        k, s = first barycentric coordinate to reach 0 and the distance to it
        if s >= L: return (f, b + L * db)
        b += s * db;  b[k] = 0;  L -= s
        g = nbr[f][k]
        if g is none or the edge is a barrier: return (f, b) flagged BOUNDARY
        a, c = d . E[f][k],  -(d . Pin[f][k])        # along the edge, out of f
        d    = a * E[f][k] + c * Pin[g][k']           # same components, perpendicular now into g
        b    = b relabelled to g's corners (the edge's two corners swap, the opposite corner gets 0)
        f    = g
        stop flagged STUCK after 64 crossings without progress or on a degenerate triangle
```

### 14.6 Complexity

| Step | Cost |
|---|---|
| Reference capture | O(T) array work plus one sort of 3T edge keys for the adjacency; measured in §12 |
| Weights | the existing Dijkstra, O(A log A) for A affected vertices |
| Transport | O(A), one rotation product per vertex in tree order |
| Update | O(A × c), c = triangles crossed ≈ drag distance / local edge length × 1.5; one array pass per crossing |
| Pursuit | + O(L × c′) for the L lagging vertices, c′ small (a budget-length step) |
| Memory | reference: about 830 bytes per vertex; gesture: about 200 bytes per affected vertex |

### 14.7 Optimisation opportunities **[T]**

- Capture only the triangles within reach (the affected region grown by the largest expected drag) instead of the
  whole surface; or keep the reference across gestures (§10.3), which removes the capture cost entirely.
- Share arrays with `PackedGeometry` (positions, face normals, corners) instead of rebuilding them.
- Cache the target path of a vertex while the drag direction is unchanged (a straight drag only extends it).
- Transport as one angle per vertex in a local 2D frame instead of a 3 × 3 matrix.
- The setup loops written in Python here (Dijkstra, transport, seam table) are the largest fixed costs; the
  Dijkstra already exists in Production.

---

## 15. Open decisions for Manu **[O]**

1. Reference lifetime and evaluation (§10.3): per gesture or kept; flat or Phong.
2. Direction model: `transport` (the selection moves like a decal — recommended by the measurements) or `project`
   (every vertex follows the screen direction as far as its own tangent plane allows).
3. Crossing the mirror plane: allowed, or stopped at the seam with a back-off (§9.4).
4. Whether the first version ships without cursor-exact pivot tracking (§11.3).
5. When lagging vertices settle (§13.2).
6. Which surface is the reference while a morph mix, a pose or the SubD preview is shown.

## 16. Reproduce

```bash
python -m pytest experiments/surface_slide/tests -q
```

```bash
python experiments/surface_slide/run_all.py && python experiments/surface_slide/studies.py && python experiments/surface_slide/bench.py && python experiments/surface_slide/summarize.py
```

Sources for the methods: K. Polthier, M. Schmies, *Straightest Geodesics on Polyhedral Surfaces* (1998);
T. Boubekeur, M. Alexa, *Phong Tessellation* (SIGGRAPH Asia 2008); C. Ericson, *Real-Time Collision Detection*
§5.1.5 (closest point on a triangle).
