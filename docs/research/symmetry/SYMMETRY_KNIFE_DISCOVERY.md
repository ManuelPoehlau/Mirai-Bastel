# Symmetric Knife — Discovery (AD-SYM-03 slice 6, Type B)

**Status:** Discovery (M5). **No decision, no implementation, no AD status change.** Every recommendation below is marked
as such; the Artist decides Intent, Product Truth, Priority and Promotion (§6).
**Date:** 2026-10-08 · **Repo state:** `main` @ `1aa77c9` (branch `ccr-10ab18a5-f1izvr`)
**Question:** how can the Production Knife (`KnifeTool` + `knife_resolve.resolve_cross_face`) run under symmetry as
**one mirrored intent** — or where can it not — and what is the one way forward?
**Binding inputs (not renegotiated):** [AD-SYM-03](../../architecture/AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md)
(DECIDED; §3 items 1, 2, 4–9, §4 "Knife tie-break equivariance", §7 row 6), [AD-017](../../architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md)
and its addenda in [`AD-017_FINAL_DECISIONS_2026-09-22.md`](../../architecture/AD-017_FINAL_DECISIONS_2026-09-22.md),
the Knife record [`knife_face/decision.md`](../../../playground/experiments/knife_face/decision.md),
[AD-013 addendum H2 + amendment 2026-10-08](../../architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md),
[`SYMMETRY_DESIGN_BRIEF.md`](SYMMETRY_DESIGN_BRIEF.md) (INV-1…13),
[`SYMMETRY_PRODUCTION_OPERATIONS_DISCOVERY.md`](SYMMETRY_PRODUCTION_OPERATIONS_DISCOVERY.md) (cited as **Disc.**, not edited),
[`SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md`](SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md) (R2).
**Probe:** [`experiments/topology/symmetry_knife_probe.py`](../../../experiments/topology/symmetry_knife_probe.py) —
read-only, headless, in-memory, no `pyglet`, no file writes:
`python experiments/topology/symmetry_knife_probe.py` (all sections, fixed seed `20261008`, 500 camera-free fuzz paths
per asset; `--quick` for a smoke run). All numbers below are from one run of that command (§1.3).
**Tests (this container, no `pyglet`), before and after this commit:** `pytest tests --ignore=tests/test_extrude_tool.py`
1964 passed / 14 skipped; `pytest experiments/symmetry_lab/tests` 428 passed / 8 skipped / 1 failed (the pre-existing
`test_app_lab_partners.py::test_lab_overlays_are_drawn_before_the_app_point_overlay`, `pyglet`); `playground/tests` not
collectable without `pyglet`. Nothing in `src/`, `playground/` or `src/main.py` is changed.
**Evidence rule:** §1 holds observations only (code read with `file:line`, probe output, recorded verdicts). Inferences
are marked **[inference]**. §2–§4 are alternatives and proposals and say so.

---

## 0. Before the evidence

### 0.1 M1 — what exists (checked against the code)

The old mirrored Knife exists only in git (`171bb63^`, `lab_knife.py`, pre-B7 per-click model, not restorable); its P1–P3
survive as `experiments/symmetry_lab/tests/test_lab_knife.py`, probe I reproduces (grid tie, `valid`, 4 faces w/o partner).
Reusable and used here: the S1/S2 helpers, `SymmetryIndex` and the C-b report/delta check (`symmetry_coordination.py`),
`Application.knife_render_data`, the Discovery probe's `load` and the coordination probe's `seam_face_and_edges`, the
integrity probe's `camera_for`; the Lab's turquoise partner overlays exist but are vertex-only.

### 0.2 Part C (preview mock) was not built — contract finding

The handoff's Part C (a Lab overlay drawing `app.knife_render_data()` mirrored, three variants on one Lab key) cannot be
built without changing the Lab input contract, so it was skipped (handoff §4.3, §10):

- **AD-013 H2-R1** fixes the Lab context at **exactly three key entries** (Shift+S, M, Shift+B); a fourth key is a
  change of H2 (test T-R1a, `experiments/symmetry_lab/tests/test_app_lab_bindings.py:55`).
- **AD-013 H2-R4 (a)** lists the read-only `Application` state the Lab may use; `knife_render_data`
  (`application.py:887-902`) is not on it. The static scan T-R4a checks methods only, so a property read would not be
  caught by the test — it would still break the rule.

What it would need: a dated H2 amendment adding (1) `knife_render_data` as a read-only item and (2) a fourth Lab key (or
a start option of `run.py` instead of a key), with its own review (H2-R6). Consequence: **Test 2 of the handoff §7 is
not prepared**; Test 1 (Silo) stands on its own (§5). The proposal (§3) puts the mirrored preview into `Application` /
viewport, where no H2 change is needed.

### 0.3 Documents vs. code

No contradiction of substance found between AD-SYM-03 §1, AD-017, `decision.md` and the code. Only line numbers have
moved: `KnifeTool` is begun at `application.py:910` (AD-SYM-03 §1.2 says `:733-741`), `KnifeTool._on_commit` is
`knife.py:617-648` (AD-SYM-03 §1.1 says `:617-643`). The AD-017 addenda that record One Knife S1–S4 / UX2 live in
`AD-017_FINAL_DECISIONS_2026-09-22.md`, not in the AD-017 file itself.

---

## 1. Evidence

### 1.1 Code facts (read at `1aa77c9`)

**Session and commit.**

- `KnifeTool` keeps a virtual path of records, each with a `pid` given at click time (`knife.py:573-586`, pid at
  `:579-580`); planner crossings are records with their **own** pid (`:484-486`). The mesh is untouched until commit;
  `_on_commit` (`:617-648`) calls `resolve_cross_face` on the path without space records, then `check_commit`, then
  pushes one `MeshStateCommand` and selects the cut edges.
- `KnifeTool._on_begin(self, mesh=None, scene=None, selection=None, **_)` (`knife.py:207`) swallows extra `begin`
  params: a `symmetry=` context reaches it today but is ignored.
- `Application._connect_command` starts the session directly (`if ctx is CContext.KNIFE: return self._knife_begin()`,
  `application.py:690-691`); the coordinator lookup `_connect_coordinator` / `_connect_op` serves the selection
  contexts only. A Knife declaration therefore needs its own call path (`_knife_begin`, `:904-921`).
- `CContext.KNIFE` is undeclared (`symmetry_declarations.py:40-48`); the Lab's BLOCK row and MARK warning derive from
  the declarations (`lab_app.py:287-316`, `:721`).

**Resolver (Knife-owned, AD-017 #1).**

- Mutations: only `split_edge` (`knife_resolve.py:517`, `:726`) and `split_face` (`:155`, `:228`, `:231`, `:292`, `:295`,
  `:320`); rollbacks through `export_state` / `load_state` (`:288/308`, `:817/835`, `:851/858/864`, `check_commit :402`).
- Output: `KnifeResolution` (`:425-444`) holds the cut edges and counts. **The pid → vertex mapping is local to
  `resolve()`** (the `resolved` dict, filled by `_run_end_vertex :484-521`); only interior points are reported
  (`interior_vertices`, `:926`, `_record_new_vertices :947-956`). There is **no record of the kept primitive calls**.
- Tie-breaks and order dependence (full list in K9): `select_bridge` (`:184-188`, position lexicographic),
  `close_loop_at_vertex` (`:286-287`), `_tail_corners` (`:942-943`), `_step_from` (`:552`, FaceId order on a tilt tie),
  `_build_loops` (`:772`, FaceId order), `round(·, 9)` in the distance keys (`_TIE_DIGITS`, `:87`) and in the
  repeated-point key (`_merge_repeated_points`, `:991`).
- Intersection points the resolver makes itself are computed in each face's own 2D frame (`FaceFrame`,
  `face_geometry.py:94-111`: origin = first boundary vertex): the split of a crossed cut (`_walk_run :720-726`) and the
  crossing point of a loop (`:700-705`). They carry no pid.
- `Mesh.split_edge` places the new vertex at `a*(1-t) + b*t` (`mesh.py:309`): orientation-dependent for `t ≠ 0.5`
  (AD-SYM-03 §1.2, P3). `mirror_position` is exact negation on E1 planes (AD-SYM-03 §1.2, R4).

**Preview.** `KnifeRenderData` (`knife_preview.py:45-53`) is world positions only (points, segments, crossing dots).

**Pixel / camera rules** (judged for the clicked point only): `EDGE_MARGIN_PX = 9` (`knife.py:317`),
`OWN_POINT_SNAP_PX = 14` (`knife_pick.py:254`), `VERTEX_TOL_PX = 0.5` and occlusion in the planner
(`knife_planner.py:38`, `:72-82`), `ENDPOINT_THRESHOLD = 0.05` in `t` from the click ray (`knife_pick.py:51`).

### 1.2 The methods and the criterion (as run by the probe)

| | Method (probe code only) |
|---|---|
| **K-A** | Mirror the path records (vertex → partner, edge + t → partner edge + `t` or `1−t` by orientation, face + position → partner face + `mirror_position`, crossings as stored), append them after a pen lift, **one** `resolve_cross_face`, then set every mirror vertex of a (pid, mirror pid) pair to `mirror_position(source)`; S1 from the recorded splits |
| K-A0 | K-A without the snap (diagnostic: where P3 recurs) |
| **K-B** | Resolve the source path, then the mirrored path in a **second** call on the same mesh; snap, S1 |
| **K-C** | Resolve the source path alone, then **replay its kept mutations mirrored**: every kept `split_edge` / `split_face` with partner ids and mirrored positions; ids of created elements mapped through the call results (vertices / edges in path order, the two faces of a split by vertex-set inclusion); seam edges are their own partner and are not split again; S1 from the kept splits. The kept-call log comes from wrapping the Mesh *instance* (each `export_state` marks the log, a `load_state` of that state truncates it) — no resolver change |
| **K-D** | K-A with **mirror-aware tie-breaks**: probe copies of `select_bridge`, `close_loop_at_vertex`, `_tail_corners` whose position key is the position on the normal's side and its mirror image on the other side (reference side = the face's side, else the loop's); monkeypatched for the call only |
| **K-E** | K-A, refused whenever the delta check (E-a) fails — the safety net every method keeps (AD-SYM-03 item 5) |

**Equivariance criterion** (handoff §2.3; each part reported separately, never merged; no tolerance):
**E-a** delta check against the session-start mesh clean (no created element without a partner, no complete element
made incomplete, no new dead seam id, no new self-mirrored face) and `symmetry_state` not worse; **E-b** the source-side
faces (all vertices x ≥ 0, one > 0) have exactly the positions of the source path resolved alone on a copy;
**E-c** the multiset of all faces equals its own mirror image (positions through `mirror_position`, winding reversed);
on failure the probe reports the largest distance of a created vertex's mirror position to the nearest vertex
(`conn` = 0: every point has its mirror but the edges differ; `float` < 1e-9; `geom` ≥ 1e-9); **E-d** one history entry,
Undo restores mesh and symmetry definition, Redo the result.

Sessions are always produced by the Production `KnifeTool` click rules (`plan` / `click` / `lift` / `undo_step`);
face points get `distance_px = 100` (the 9 px rule is a pick rule, examined in K6). Camera sessions (K4, K5) click
through `knife_pick` + `snap_own_point` + `space_point` with occlusion on, as `Application._knife_pick` does.
Fixtures: `subd_cube`, `head_basemesh`, `man_with_shoes_basemesh` (partial) with the Lab X definition; `tie_grid`
(x ∈ [−3, 3], y ∈ [0, 3], unit squares: every centred click is an exact tie), `hole_grid` (the same with a symmetric
hole pair), `hexagon_grid` (one face spanning the plane with two non-adjacent seam vertices), `span_grid` (faces
spanning the plane, no seam).

### 1.3 Probe results

Run: `python experiments/topology/symmetry_knife_probe.py` (seed 20261008, 500 camera-free fuzz paths per asset), exit
code 0, 656 s on this container (Linux x86_64, Intel Xeon 2.8 GHz, 4 CPUs, Python 3.13.16; not the reference PC).
Flags in the case tables: `E abcd` = E-a E-b E-c E-d (`+` pass, `-` fail); `snap m/n` = mirror vertices moved / pid
pairs; `dev` = largest mirror deviation of a created vertex (`conn` 0, `float` < 1e-9, `geom` ≥ 1e-9).

**K1 — edge → edge in one +X quad** (`subd_cube` f12, `head_basemesh` f163, `tie_grid` f4).

| asset | t | K-A0 (no snap) | K-A | K-B | K-C | K-D |
|---|---|---|---|---|---|---|
| subd_cube | (0.5, 0.5) | E ++++ | E ++++ snap 0/2 | E ++++ | E ++++ | E ++++ |
| subd_cube | (0.3, 0.6) | **E -+-+** float 1.1e-16 | E ++++ snap **1/2** | E ++++ | E ++++ | E ++++ |
| subd_cube | (0.37, 0.37) | E ++++ | E ++++ snap 0/2 | E ++++ | E ++++ | E ++++ |
| subd_cube | (0.123456789, 0.87654321) | **E -+-+** float 1.1e-16 | E ++++ snap **1/2** | E ++++ | E ++++ | E ++++ |
| head_basemesh | all four | E ++++ | E ++++ snap 0/2 | E ++++ | E ++++ | E ++++ |
| tie_grid | (0.3, 0.6) | **E -+-+** float 2.2e-16 | E ++++ snap **1/2** | E ++++ | E ++++ | E ++++ |
| tie_grid | the other three | E ++++ | E ++++ snap 0/2 | E ++++ | E ++++ | E ++++ |

P3 recurs exactly where a mirrored `t` is `1−t` on an orientation-reversed partner edge and `1−(1−t) ≠ t` in floating
point; the snap must act at **pid → created vertex** of the edge record (`_run_end_vertex`). K-C needs no snap: it places
the mirror vertex at `mirror_position` when it creates it.

**K2 — vertex → vertex chord, vertex → edge point.** All methods E ++++ on all three meshes, except K-A0 on
`head_basemesh` vertex → edge t = 0.3 (float 1.2e-16; K-A with snap 1/2 passes).

**K3 — interior points** (one +X quad each; `TIE` = centred / symmetric clicks).

| mesh | recipe | tie-break that fired (source alone) | K-A | K-B | K-C | K-D | K-E |
|---|---|---|---|---|---|---|---|
| tie_grid | TIE closed shape | `select_bridge` first bridge point by position | **E -+-+ conn** | E -+-+ conn | E ++++ | E ++++ | refused |
| tie_grid | TIE loop at a point | `close_loop_at_vertex` bridge by position | **E -+-+ conn** | E -+-+ conn | E ++++ | E ++++ | refused |
| tie_grid | TIE tail joined to a corner | `_tail_corners` nearest corner by position | **E -+-+ conn** | E -+-+ conn | E ++++ | E ++++ | refused |
| tie_grid | TIE notch / bent cut; every no-tie recipe | — | E ++++ | E ++++ | E ++++ | E ++++ | E ++++ |
| subd_cube | TIE loop at a point | `close_loop_at_vertex` | E ++++ (the flipped key happens to agree) | E ++++ | E ++++ | E ++++ | E ++++ |
| subd_cube, head_basemesh | every other recipe | — | E ++++ | E ++++ | E ++++ | E ++++ | E ++++ |

`conn` = every created point has its mirror but the bridges / corner joins go to the other corner (probe I generalised to
all three tie-break sites). Every +X face with the TIE recipes:

| mesh | recipe | faces | tie fired | K-A pass (E-a+E-c) | K-C pass | K-D pass |
|---|---|---|---|---|---|---|
| subd_cube | closed shape / loop at a point / tail | 12 / 12 / 12 | 0 / **6** / 0 | 12 / **8** / 12 | 12 / 12 / 12 | 12 / 12 / 12 |
| head_basemesh | closed shape / loop at a point / tail | 159 / 162 / 162 | 0 / 0 / 0 | all | all | all |
| tie_grid | closed shape / loop at a point / tail | 9 / 9 / 9 | **9 / 9 / 9** | **0 / 0 / 0** | 9 / 9 / 9 | 9 / 9 / 9 |

Ties are the regular, clean case: none on the irregular head quads, every one on square faces; K-D removes all of them
(no self-symmetric input met).

**K4 — cross-face runs on `head_basemesh`** (camera sessions clicking visible +X targets; (i) = stored crossing records
mirrored, (ii) = the mirrored clicks re-planned with the same camera).

| camera | sessions | (ii) identical to (i) | same edges, other `t` | other elements / breaks | gap breaks (i) / (ii) | K-A (i) E-a+E-c | K-A (ii) E-a+E-c | K-C E-a+E-c |
|---|---|---|---|---|---|---|---|---|
| front (in the plane) | 59 | 1 | 58 | 0 | 133 / 133 | 42 (17 float) | 1 (58 float) | **59** |
| 3/4 (+X) | 60 | 0 | 0 | 60 | 63 / 353 | 50 (10 float) | 0 (60 geom) | **60** |
| side (+X) | 60 | 0 | 0 | 60 | 43 / 374 | 48 (11 float, 1 geom) | 0 (60 geom) | 53 (7 refused, all with a crossing on −X) |

(ii) never reproduces (i) exactly: from the front camera (on the plane) the same edges are crossed but at other `t`
(re-computed from the mirrored ray), from 3/4 and side cameras whole stretches differ (hidden mirror side → 5–9× the gap
breaks). With (ii) not one session is exactly symmetric. (i)'s K-A failures are the resolver-made vertices (K10).
K-C passes every session whose records stay on +X; each of its refusals is a session whose planner crossings reached −X.

**K5 — points in space and gap breaks** (`hole_grid` with a symmetric hole pair, `head_basemesh`; 30 % of the clicks in
empty space).

| mesh | camera | sessions (space points) | gap breaks (i) / (ii) | (ii) skips the same stretches | K-A (i) E-a+E-c | K-A (ii) | K-C E-a+E-c; refused (all with a record on −X) |
|---|---|---|---|---|---|---|---|
| hole_grid | front | 37 (40) | 36 / 37 | 36 | 30 | 12 | 22; 15 |
| hole_grid | 3/4 (+X) | 39 (45) | 50 / 52 | 26 | 34 | 0 | 23; 16 |
| head_basemesh | front | 39 (54) | 64 / 64 | 39 | 28 | 0 | 13; 26 |
| head_basemesh | 3/4 (+X) | 37 (46) | 27 / 168 | 3 | 26 | 0 | 19; 18 |
| head_basemesh | side (+X) | 40 (59) | 23 / 178 | 2 | 32 | 0 | 32; 8 |

(i) skips by construction the same stretches as the source. (ii) does so only from a camera in the plane, and even there
the crossings are not exact. A segment from a point in space far to the side crosses the whole model, so many of these
paths reach −X; K-C refuses exactly those (the remaining K-C sessions all pass).

**K6 — session rules.** (a) The mirror session clicked by the same rules (every camera-free K10 session): same acceptance
per click in **1176 / 1176**, the mirror session's path equals the mirrored records in **1176 / 1176** — the click rules
need no mirror-specific judgement. (b) Pixel rules on the mirror side (head, a face-point click at every +X face centre
that passes the 9 px rule):

| camera | source clicks | mirror visible ≥ 9 px | mirror visible < 9 px | mirror hidden |
|---|---|---|---|---|
| front | 23 | 23 | 0 | 0 |
| 3/4 (+X) | 34 | 8 | 12 | 14 |
| side (+X) | 46 | 0 | 0 | 46 |

A pick rule applied to the mirror point would refuse 76 % (3/4) or 100 % (side) of valid clicks: the mirror must never
be judged by pick rules. (c) After undo, undo, redo the derived mirror path is identical on re-derivation (100 / 100);
the step list is untouched.

**K7 — seam** (`subd_cube`, `head_basemesh`, `tie_grid`; the synthetic rows on `hexagon_grid` / `span_grid`).

| case | K-A | K-B | K-C | K-D | K-E |
|---|---|---|---|---|---|
| a / a′ start or end on a seam vertex | E ++++ | E ++++ | E ++++ | E ++++ | E ++++ |
| g along the seam, then into the face; h seam vertex → side edge | E ++++ | E ++++ | E ++++ | E ++++ | E ++++ |
| b one point on a seam edge (S1) | E ++++ (seam 9/9 live on the cube) | **E -+-+ geom** | E ++++ | E ++++ | E ++++ |
| b2 two points on one seam edge, two chains | E ++++ (seam 10/10 live) | **E -+-+ geom** | E ++++ | E ++++ | E ++++ |
| c path crossing the seam into the other side | **E +-++** (an X: the mirror cut crosses the source cut) | E -+-+ geom | refused (mirror already cut) | E +-++ | E +-++ |
| d drawn symmetric, exact mirror click | cube, grid: E ++++ (merged); head: **E -+-+ float 2.5e-16** | as K-A | refused | as K-A | head: refused |
| d′ mirror click 1e-12 off | **E -+-+ float** (merged by `round(t, 9)`, not exact) | as K-A | refused | as K-A | refused |
| d″ mirror click 1e-6 off | **E +-++** (two almost coincident cuts per side, V +2) | E -+-+ geom | refused | E +-++ | E +-++ |
| e straight chord between two seam points (hexagon) | E ++++ (one shared cut, an undeclared on-plane edge) | E ++++ | refused (self-mirrored face) | E ++++ | E ++++ |
| e′ bent chord seam → inside → seam (hexagon) | E -+++ (new self-mirrored face) | E -+-+ | refused | E -+++ | refused |
| f / f″ through a plane-spanning face, asymmetric | E --++ (on-plane intersection vertex without partner) | E -+-+ | refused | E --++ | refused |
| f′ through it, symmetric | E -+++ (new self-mirrored faces) | E -+++ | refused | E -+++ | refused |

`_merge_repeated_points` key `round(t, 9)` (`knife_resolve.py:991`): in 100 000 random `t`, `1−(1−t) ≠ t` 32 958 times,
the 9-digit keys never differ — a mirror record meets a source record on the same edge only on a seam edge (its own
partner, `t` unchanged) or when the path reaches the other side (c, d). Faces of the three Lab assets with two
non-adjacent seam vertices (where case e could occur): **0**.

**K8 — next to unpaired geometry** (`man_with_shoes_basemesh`, `partial`; +X targets without a partner: vertices 27/442,
edges 108/948, faces 101/463). 300 sessions starting next to unpaired vertices (+100 with an invalid source path).

| method | click-time predictor | predicted, refused at commit | predicted, kept | not predicted, refused | not predicted, kept |
|---|---|---|---|---|---|
| K-A | P1 = a record has no partner | 193 | 0 | 22 | 85 |
| K-A | P2 = P1 or a cut face has no partner | 201 | 0 | 14 | 85 |
| K-C | P1 | 176 | 17 | 8 | 99 |
| K-C | **P2** | **184** | 17 | **0** | 99 |

With K-C, P2 predicts **every** D-strict refusal before Enter; it is conservative (17 of 201 predicted sessions would
have committed cleanly, e.g. when the run touching the unpaired element is dropped). K-A's unpredicted refusals are its
own defects (K10), not unpaired geometry.

**K9 — order / id dependence.** Sites (all `file:line` at `1aa77c9`):

| file:line | site | rule | what the mirror side changes |
|---|---|---|---|
| `knife_resolve.py:184-188` | `select_bridge` | distance tie → boundary-vertex position, then loop-point position, lexicographic | reflection flips the x order |
| `knife_resolve.py:286-287` | `close_loop_at_vertex` | (outside first, distance, loop-point position, boundary position) | reflection flips the x order |
| `knife_resolve.py:942-943` | `CrossFaceResolver._tail_corners` | (distance rounded to 9, corner position) | reflection flips the x order |
| `knife_resolve.py:552, 584` | `KnifeResolver._step_from` | faces in FaceId order; the first wins on a tilt tie | FaceId order |
| `knife_resolve.py:772-778` | `KnifeResolver._build_loops` | first face (FaceId order) holding the probe point | FaceId order |
| `knife_resolve.py:87, 184, 286` | `_TIE_DIGITS = 9` | `round(d, 9)`: near-ties become ties | rounding |
| `knife_resolve.py:991` | `_merge_repeated_points` | key (edge id, `round(t, 9)`) | edge orientation (`t` vs `1−t`) |
| `knife_resolve.py:506-518` | `_run_end_vertex` | `t` within `GEO_EPS` = the same split; `split_edge(piece, u or 1−u)` | edge orientation |
| `knife_resolve.py:954`, `:760` | `_record_new_vertices` / `vertex_at` | position match `< 1e-9` / `<= 1e-12` | float noise |
| `face_geometry.py:94-111` | `FaceFrame` | origin = first boundary vertex, `u` from a fixed axis | boundary start and direction |
| `knife_planner.py:154`, `:164` | `_pick_face_at` / `_face_in_direction` | faces in FaceId order (camera) | FaceId order |
| `knife.py:411` | `KnifeTool._link` | `any()` over shared faces in FaceId order | nothing (`any`) |
| `symmetry_coordination.py:67` | `SymmetryIndex` face lookup | duplicate vertex set → lowest FaceId | FaceId order |

The four ways the mirror side differs from the source, isolated on the source paths of K10 (one-sided resolve; result
compared position-exact with the original, X1 after reflecting back):

| mesh | X1 reflection (positions mirrored, boundaries reversed) | X2 id permutation | X3 boundary start rotated | X4 edge orientation flipped (t → 1−t) |
|---|---|---|---|---|
| subd_cube (300) | 262 identical, 38 float | 300 identical | 287 identical, 13 float | 237 identical, 63 float |
| head_basemesh (300) | 268 identical, 32 float | 300 identical | 292 identical, 8 float | 222 identical, 78 float |
| tie_grid (300) | 239 identical, 26 float, **35 topology** | 300 identical | 296 identical, 4 float | 257 identical, 43 float |

Id order changes nothing (X2: 900 / 900 identical, although `_step_from` met 10 tilt ties decided by FaceId order). What
breaks equivariance is the **reflection** itself (tie-breaks by position → topology, frames → float) and the **edge
orientation** (t → 1−t → float, P3). Tie-break counters over the same paths: `_tail_corners` decided by position 27 / 269
calls, `close_loop_at_vertex` 1 / 52, `select_bridge` 2 / 6 (exact ties), `_step_from` FaceId order 10 / 1652.

**K10 — fuzz** (camera-free, through the Production click rules; 2–8 accepted clicks: vertices, edge points with
t = 0.5 in 30 %, face points centred in 30 %, closes, pen lifts, earlier points, undo; +X faces only). Excluded because
the source path alone is no valid one-sided cut: `subd_cube` 127 / 500 (119 cut nothing, 8 rolled back), `head_basemesh`
102 / 500 (97 / 5), `tie_grid` 95 / 500 (93 / 2). "seam" = a record on a seam vertex or seam edge.

| mesh (n) | method | E-a | E-b | E-c | E-d | all four | refused | exceptions | E-c failures conn / float / geom |
|---|---|---|---|---|---|---|---|---|---|
| subd_cube (373) | K-A | 87.1 % | 100 % | 87.1 % | 100 % | 87.1 % | 0 | 0 | 0 / 48 / 0 |
| | K-B | 64.1 % | 100 % | 64.1 % | 100 % | 64.1 % | 0 | 0 | 31 / 28 / 75 |
| | **K-C** | **100 %** | **100 %** | **100 %** | **100 %** | **100 %** | 0 | 0 | 0 |
| | K-D | 87.1 % | 100 % | 87.1 % | 100 % | 87.1 % | 0 | 0 | 0 / 48 / 0 |
| | K-E | 87.1 % kept | | | | | 48 | 0 | — |
| head_basemesh (398) | K-A | 90.5 % | 100 % | 90.5 % | 100 % | 90.5 % | 0 | 0 | 0 / 38 / 0 |
| | K-B | 82.4 % | 100 % | 82.4 % | 100 % | 82.4 % | 0 | 0 | 8 / 31 / 31 |
| | **K-C** | **100 %** | **100 %** | **100 %** | **100 %** | **100 %** | 0 | 0 | 0 |
| | K-D | 90.5 % | 100 % | 90.5 % | 100 % | 90.5 % | 0 | 0 | 0 / 38 / 0 |
| | K-E | 90.5 % kept | | | | | 38 | 0 | — |
| tie_grid (405) | K-A | 80.7 % | 100 % | 80.7 % | 100 % | 80.7 % | 0 | 0 | **33** / 37 / 8 |
| | K-B | 68.1 % | 100 % | 68.1 % | 100 % | 68.1 % | 0 | 0 | 44 / 28 / 57 |
| | **K-C** | **100 %** | **100 %** | **100 %** | **100 %** | **100 %** | 0 | 0 | 0 |
| | K-D | 90.4 % | 100 % | 90.4 % | 100 % | 90.4 % | 0 | 0 | 0 / 39 / 0 |
| | K-E | 80.7 % kept | | | | | 78 | 0 | — |

Seam stratum (a record on a seam vertex / edge): K-B falls to 40.6 % / 45.9 % / 39.8 % (cube / head / grid), K-A and K-D
stay at their overall level, K-C 100 % (207 / 74 / 123 paths). No exception in any method; no "silent" run (E-a passing
while E-b or E-c fails) anywhere — the delta check catches every non-symmetric one-sided result.

Where K-A / K-D still fail by float or geometry (not by a tie): the created vertices that are no exact mirror after the
snap are **all resolver-made**, none is a pid vertex:

| mesh | runs (K-A) | intersection with a cut of this commit (`split_edge` in `_walk_run`) | crossing point inside a face construction (`split_face`) |
|---|---|---|---|
| subd_cube | 48 | 114 vertices | 14 vertices |
| head_basemesh | 38 | 100 | 8 |
| tie_grid | 45 | 118 | 7 |

Commit time (resolve + snap / replay + S1 + `check_commit`; median / p95 ms, this container):

| mesh | source alone | K-A | K-B | **K-C** | K-D |
|---|---|---|---|---|---|
| subd_cube | 1.12 / 2.21 | 1.86 / 4.56 | 1.96 / 4.55 | **1.51 / 2.81** | 2.17 / 4.37 |
| head_basemesh | 6.54 / 12.38 | 10.69 / 21.60 | 11.11 / 24.17 | **7.54 / 14.79** | 10.72 / 22.05 |
| tie_grid | 1.02 / 2.19 | 1.73 / 4.49 | 1.97 / 4.48 | **1.38 / 2.89** | 1.93 / 4.63 |

The two completeness reports + delta that every coordinator runs come on top (0.4 / 4.2 / 0.4 ms median).

**K11 — preview.** Every `KnifeRenderData` field is a world position: `start_point`, `placed_points`, `path_segments`,
`line_preview`, `target_edge` (= the partner edge exactly, 648 / 648 head edges), `prospective_crossings` (only as the
source camera planned them). Mirroring all fields costs **0.036 / 0.18 / 0.70** ms per frame for 8 / 50 / 200 path points; the
`SymmetryIndex` for the hover partner check costs 1.36 ms once per session (head). The mirror of the source preview
and the preview drawn from mirrored records differ by at most 8.9e-16 (P3 on reversed edges) — invisible, but the
same reason why only a K-C commit matches the mirrored preview exactly.

**K-D with no plane** (the non-symmetric Knife): the golden net (`playground/tests/knife_golden_driver.py`, 345 seeded
sessions + Manu's recorded sequences) is **byte-identical** with the K-D keys installed and `plane=None`, and
`tests/test_knife_parity.py` passes (pytest exit 0). By construction the key is then `tuple(p)`, the original key.

---

## 2. Alternatives

Cost columns: code areas touched, AD amendments, risk, effect on the non-symmetric Knife, what the Artist sees.

### 2.1 Path coordination

| | Evidence (§1.3) | Cost | Assessment |
|---|---|---|---|
| **K-A** mirror records, one resolve, snap by pid | K1/K2 exact only with the snap (K-A0 fails on orientation-reversed edges, P3). K3: every centred tie on the tie grid fails (`conn`), 4 of 12 cube loops. K10 all four: 87.1 / 90.5 / 80.7 % (cube / head / grid); every remaining failure is a tie or a resolver-made vertex. K4 (i) 71–83 %. K7 c: an X, E-b − | Resolver must report pid → created vertex (AD-SYM-03 item 4 already names it) and its seam splits; probe-sized snap; commit ×1.6–1.7 (K10) | **Not used because** it is not equivariant where the resolver decides by itself: on every exact tie (regular quad areas) and on every vertex the resolver computes (intersections with the session's own cuts, loop crossing points), which carry no pid and so cannot be snapped. A path that reaches the other side becomes an X that changes the Artist's own side (E-b) |
| **K-B** two resolve calls | K10 all four: 64.1 / 82.4 / 68.1 %; seam stratum 40.6 / 45.9 / 39.8 %; K7 b, b2, c fail (`geom`) | As K-A | **Not used because** the second call meets the ids the first call killed on shared (seam) elements and drops those runs (K7 b/b2/c, the K10 seam stratum), on top of every K-A defect |
| **K-C** resolve the source, replay its kept mutations mirrored | K10: **100 % of 1176 paths on all four criteria**, seam stratum included; K3 every tie passes; K4/K5 every camera session whose records stay on +X passes, every refusal is a path with a record on −X; K7 refuses c, d, f (the path reaches the other side) and e, e′ (a cut inside a self-mirrored face); K8 with P2: no unpredicted refusal | Resolver reports its **kept primitive calls** (additive field, truncated on dropped-run rollbacks) — an AD-017 addendum; a replay service (~100 lines in the probe) with id mapping by call results and face matching by inclusion; S1 from the kept splits. Commit is the cheapest of all methods (K10). Non-symmetric Knife: unchanged (the log is passive). Risk: the log must cover every primitive the resolver uses (two today); a replay-on-a-copy test guards it (6a) | **Proposed** (§3). Exact by construction: every mirror vertex is created at `mirror_position(source)`; ties and frames are never decided twice, because the mirror side is never resolved. Refuses a path whose kept mutations touch the mirror side or a self-mirrored face (product question F1) |
| **K-D** K-A + mirror-aware tie-break key | K3 every tie passes; K10 all four 87.1 / 90.5 / 90.4 % — the same resolver-vertex failures as K-A remain; with no plane: golden net byte-identical, parity rows pass | Three resolver functions change their key (AD-017 addendum); with no plane the behaviour is byte-identical (golden net, parity rows, §1.3 K-D); a rule is still needed for a tie inside a self-symmetric input (0 cases on the assets) | **Not used because** it removes only the tie defect: the resolver-internal vertices still come out ulps off (same E-c failures as K-A in K10), so it would need a further resolver change (canonical intersection frames) and a snap for vertices without pid — K-C needs neither |
| **K-E** K-A, refused by the delta check | K10 refuses 48 / 38 / 78 of 373 / 398 / 405 paths (13 / 10 / 19 %); K3 tie grid: every centred closed shape, loop and tail refused; no silent run anywhere | None beyond K-A | **Not used as the method because** it refuses exactly the clean, regular, symmetric case (every centred closed shape / loop / tail on the tie grid, K3) and the paths that cross the session's own cuts; the Artist would meet refusals where the mesh is most regular. **Kept as the safety net** under every method (AD-SYM-03 item 5) — in K10 it caught every E-c failure (no "silent" case) |

**[inference]** K-C is not a re-opening of a rejected alternative: it does not search the result for new elements and
pair them (M-d: "nachträgliche Zuordnung"), it carries the creation-time pairing of each kept call (the old Lab Knife's
E17 `intent_pairs` principle, INV-6 "Gegenseite aus der Absicht"); it copies no op logic (M-c); it is Knife-owned and
runs at the Knife's own commit (AD-017 #1, M-e). It does change the *mechanism* AD-SYM-03 §7 row 6 names ("mirror records
before resolution") into "mirror the resolved mutations at the commit" — AD-SYM-03 §4 lists "resolving the source and
constructing its mirror" as an open option, so this is an addendum to §3 item 1 / §7 row 6, not a reversal.

### 2.2 Snap placement

| | Assessment |
|---|---|
| Post-resolve snap by (pid, mirror pid) pairs (K-A) | Fixes P3 for clicked edge points and stored crossings (K1/K2: K-A0 fails, K-A passes). **Not used because** resolver-made vertices have no pid (K10 origin table) |
| Resolver takes explicit mirrored positions (records carry a position instead of `t`) | Makes edge points exact; changes the record format (AD-017) and still leaves intersections computed per frame. **Not used because** it is a larger resolver change for a partial fix |
| **Placement at replay (K-C)** | Every mirror vertex is created and then placed at `mirror_position(source vertex)` inside the replay — X-a (AD-SYM-03 §2.4) applied per created vertex, no pairing step. **Proposed** |

### 2.3 Camera: mirrored records (i) vs. re-planning the mirror from the same camera (ii)

| | Assessment |
|---|---|
| **(i) the stored crossing records, mirrored** | The mirror side gets what the Artist saw: the same edges crossed, the same stretches cut and skipped (K5: by construction). With K-A the crossings are snapped through their own pids; with K-C they are not mirrored as records at all — the resolved cut is. **Proposed** (as part of K-C) |
| (ii) re-plan the mirrored segment from the same camera | **Not used because** it never reproduces (i): from the front camera the same edges at other `t`, from 3/4 and side cameras whole stretches differ with 5–9× the gap breaks (the mirror side is foreshortened or hidden); with (ii) at most 1 of 59 sessions per camera comes out exactly symmetric (K4). It would also make the commit depend on how the mirror side looks from the camera, which the camera-free resolver (AD-017) does not know |

### 2.4 When to refuse: click / hover time vs. commit time

| Refusal | Can it be decided before Enter? | Evidence |
|---|---|---|
| Non-exact plane | At `begin` (session not started), as for the other coordinators | AD-SYM-03 item 6 |
| Target without partner (vertex / edge / face) | **Yes, at hover / click**: one dict lookup per hover in a `SymmetryIndex` built once per session (K11: ~1.4 ms per session on the head) | K8 |
| Cut face without partner (a face the segment cuts has an unpaired vertex) | **Yes, at click**: the faces a camera-free segment cuts are the shared faces of its two points; with a planner segment, the faces of its crossings | K8: predictor P2 = P1 + cut faces |
| Path reaches the other side / cuts a self-mirrored face | Yes at click (a record or crossing on the other side, a shared face that is its own partner) — what happens then is F1 | K7 c, d, e, f |
| Anything else (result not complete) | Only at commit: the delta check stays as the net | AD-SYM-03 item 5 |

**Engineering recommendation (pending F3):** refuse at hover / click what P2 predicts (target without partner, cut face
without partner), marked like the Lab's unpaired vertices (magenta), and keep the delta check at commit as the net.
Commit-only refusal is **not recommended because** the Artist would draw a whole path and lose it at Enter — K8: 184 of
300 sessions next to unpaired geometry. P2 is conservative: it would also refuse 17 sessions that K-C would have
committed (a run touching the unpaired element is dropped anyway).

### 2.5 Session model: a click and its mirror as one step

The mirror is **derived from the path, never stored**: with K-C it does not even exist as records — the preview is the
`mirror_position` image of the source preview (§2.7), the commit replays the source's kept calls. In-session Undo / Redo /
pen lift / close / earlier point stay exactly as they are (K6 (c)); no second step list, no second set of click rules.
The mirror session judged by the same click rules accepts exactly the same clicks and builds exactly the mirrored records
(K6 (a): 1176 / 1176) — no second acceptance pass is needed. The pick rules (9 px margin, 14 px own-point snap, 0.5 px
vertex tolerance, occlusion) must **not** be applied to the mirror: under a 3/4 or side camera they would refuse
76 % / 100 % of valid clicks (K6 (b)). **Not used:** storing mirrored records per click (a second step list) — nothing
needs it; with K-C the commit reads the source path only.

### 2.6 Seam cases (K7) — listed, not decided

| Case | What the methods produce (§1.3 K7) | Options (not decided) |
|---|---|---|
| a / a′ / g / h — a path that starts, ends or runs along the seam (seam vertex, along a seam edge, one end on the seam) | Every method symmetric and complete (E ++++, K-B too) | Nothing to decide |
| b / b2 — one or several edge points on one seam edge | K-A, K-C, K-D: complete, S1 keeps the seam continuous (9/9 resp. 10/10 live on `subd_cube`); K-B fails | S1 is decided (AD-SYM-03 item 8); nothing open |
| c — path crossing the seam into the other side | K-A / K-D: an **X** — the mirror cut crosses the source cut at the seam point; complete and symmetric, but the Artist's side gets a second cut (E-b −); K-C refuses (the source already cut the mirror edge) | refuse · one shared X cut · (cut only to the seam) — **F1** |
| d / d′ / d″ — the Artist draws the mirror himself | Bit-exact mirror click: merged into one cut (K-A); 1e-12 off: merged by the resolver's own `round(t, 9)` key but not exact → refused by the delta check; 1e-6 off: **two almost coincident cuts per side**; K-C refuses (a c-case) | refuse (same rule as c) · merge with a tolerance (touches AR-1) · allow the doubled cut — **F2** |
| e — straight chord between two seam points in one face | Lies in the plane, is its own mirror: K-A merges it into one cut, leaving an on-plane edge that is not declared as seam; K-C refuses. **Unreachable on the Lab assets**: 0 faces with two non-adjacent seam vertices | refuse · one shared cut + add the edge to the seam (a new seam rule) — not asked now |
| e′ / f / f′ / f″ — cuts inside a face that spans the plane | New self-mirrored faces or on-plane intersection vertices without partner: refused by the delta check (K-E) or by K-C | AD-SYM-03 item 9 (refused, engineering interim) — not asked now: no Lab asset has such faces |

### 2.7 Preview (INV-11) and the hidden mirror side

Every field of `KnifeRenderData` is a world position, so the mirror preview is `mirror_position` of each field
(K11: 0.04 / 0.18 / 0.7 ms per frame for 8 / 50 / 200 path points). With K-C the commit is the exact mirror of the source
cut, so this preview cannot disagree with the result — **[inference]** with K-A it could, wherever a tie or a resolver
vertex is decided differently on the two sides. Only the hovered target needs more than geometry: whether it has a partner
(magenta marker, §2.4). The open part is the *feel*: under a 3/4 camera 41 % and under a side camera 100 % of the mirror
points of valid face clicks are hidden (K6 (b)) — whether the mirror shows through, dimmed, or only as points is the
Artist test (§5; variants V-a / V-b / V-c of the handoff, not buildable as a Lab mock, §0.2).

### 2.8 A separate symmetry capability for the Knife (Manu's open consideration)

Reported only, no recommendation for or against splitting capabilities in general.

| | (i) live coordinated Knife (Silo-like) | (ii) one-sided Knife + a later topology-mirroring step (Blender "Symmetrize"-like) | (iii) derived half / virtual mirror (Wings-like) |
|---|---|---|---|
| Knife problems found here that disappear | — (solved by K-C: ties, resolver vertices, P3, camera) | all mirroring problems during the cut: no preview of the mirror needed, no ties, no snap, no camera | all of them; a cut across the seam is impossible by construction (Wings skips the seam face, R2 §3.2) |
| Problems that appear | paths reaching the other side (F1/F2), hidden-side preview (§5) | a new **topology** symmetrize (Re-Symmetrize today moves vertices only, E12/E13): delete one side, duplicate the other mirrored, weld at the seam — the mirror side gets new ids every time (later: weights, morphs, rig); a cut crossing the seam must be cut at the seam then; the Artist works without the mirror in view (INV-11 not met during the cut) | AD-SYM-01 §4 V1 non-goal (X-d); every operation must maintain the seam face itself (R2 §3.2: Wings' per-op seam code); display and export of a half that is not data |
| What the seam must guarantee (AD-SYM-03 §4 assessment) | an exact plane, seam ids kept by S1/S2 | an unambiguous seam saying where to cut and weld; all seam vertices exactly on the plane | a continuous seam line without gaps; seam vertices exactly on the plane |
| Cost | slice 6 as in §3 (resolver report + replay + preview + click refusals) | a new capability, its own AD, a topology mirror op | an architecture change (AD-SYM-01) |

**What the Knife evidence says:** the problems that motivated a separate route (ties, exactness, camera) are solved
inside (i) by K-C for every path that stays on one side (§1.3 K10: E-a…E-d all pass); what remains for (i) are the
paths that reach the other side — and those come back in (ii) at symmetrize time and are excluded by construction in
(iii). Question F5 (§6) carries this to Manu with the costs.

### 2.9 Declaration and gate

- **Form of the `CContext.KNIFE` entry.** The selection coordinators are `(mesh, canonical ids) -> result`; a session
  tool has no selection at `C`. The entry would be the Knife's **commit coordinator**
  `(mesh, path, session_before) -> KnifeResolution` (raising `SymmetryRefusal`), which `Application._knife_begin` passes
  to `KnifeTool.begin(..., symmetry=...)` whenever a definition is set and the context is declared, and which
  `KnifeTool._on_commit` calls instead of `resolve_cross_face`. D-b holds: the entry *is* the implementation.
- **BLOCK row / MARK warning:** both are already derived from the declarations (`block_row`, `e5_warning_text`); the
  entry alone lets `C` start the Knife under BLOCK and removes the orange "Knife läuft einseitig" line. No gate change.
- **Runtime refusals** (non-exact plane at begin, a target without partner at click, F1 at click, the delta check at
  commit) are the contract of a supported operation and apply in MARK as in BLOCK (AD-SYM-03 §2.5).
- **Does any option reopen AD-013 H2?** Only a Lab-side preview or a Lab key (Part C, §0.2). The Production route
  (preview drawn by `Application` / viewport, refusals in the coordinator) does not.

---

## 3. Proposal (engineering recommendation — not a decision)

**Recommendation:** the symmetric Knife resolves the source path unchanged and **replays its kept mutations mirrored**
at the Knife's own commit (**K-C**); the in-session preview is the `mirror_position` image of today's render data; a
target without a partner is refused at hover / click (magenta), the delta check stays as the net at commit; seam rule S1
follows the kept splits; a path whose mutations reach the other side or a self-mirrored face is refused until F1 is
answered; non-exact planes are refused at `begin`.

Why this one (§1.3): it is the only method that passes E-a…E-d on every one-sided fuzz path and camera session, it never
decides a tie or an intersection twice (**[inference]** so the mirrored preview cannot promise something the commit does
not do on the other side, INV-11), it leaves the Artist's side bit-identical to
the one-sided cut (E-b by construction), it is the cheapest commit, and it changes the non-symmetric Knife in nothing
(the resolver only reports what it kept).

**Slice cut for a later Type-A package (Sonnet 5):**

| # | Slice | Content | AD |
|---|---|---|---|
| 6a | Kept-call report | `resolve_cross_face` returns its kept `split_edge` / `split_face` calls (op, arguments, results) and its pid → vertex map in `KnifeResolution`, truncated on every dropped-run rollback; tests: golden net and parity rows unchanged, the report replayed on a copy rebuilds the same mesh | **AD-017 addendum** (Knife-owned, additive) |
| 6b | Symmetric commit | Replay service (id maps from call results, face halves by inclusion, placement at `mirror_position`, S1, delta check, refusals) beside `symmetric_ops`; `KnifeTool.begin(symmetry=...)` and `_on_commit` call it; `Application._knife_begin` passes it; `CContext.KNIFE` declared; tests in the probe's shape (E-a…E-d fuzz, seam rows) and Lab tests (BLOCK row, MARK warning) | **AD-SYM-03 addendum** (§3 item 1 / §7 row 6: "mirror the resolved mutations at the commit"; §3 item 2: the replay service; X-a realised as placement at replay) |
| 6c | Mirrored preview + click refusal | `knife_render_data` gains the mirrored fields (or a mirrored copy) for the viewport tool layers; hover marker / status for a target without partner; Artist test of the preview feel (§5) | none expected (Production UX, provisional) |
| 6d | Seam paths and residue | F1/F2 as answered; residue per F4 | as answered |

**Independent review advisable before the addenda are decided: yes.** K-C changes the mechanism AD-SYM-03 §7 row 6
names and adds a contract (the kept-call report) to the Knife-owned resolver — two ADs at once; a fresh session should
check K-C against M-d / INV-6 and the replay's face matching before anything is built.

---

## 4. Deliberately not decided

- Every product question of §6 (F1–F5), and the preview variant (V-a / V-b / V-c).
- Seam cases e, e′, f (chords in the plane, cuts in plane-spanning faces): stay refused under AD-SYM-03 item 9; asked
  only when an asset has such faces (none of the Lab assets does).
- Whether the resolver's `round(t, 9)` merge of repeated points (`knife_resolve.py:991`) is an acceptable tolerance next
  to AR-1 (it decides case d′); no change proposed.
- Ties inside a self-symmetric input (a loop centred on the plane inside a self-mirrored face): K-D would need a rule;
  K-C does not meet them (refused as item 9). 0 occurrences on the assets.
- Non-exact planes, the derived-half mode (X-d), the capability split (F5 is a question, not a decision).
- Module names, the report's data shape, HUD / status texts, the hover marker's colour, any key.
- AD-SYM-03 and AD-017 stay as they are; no status changes here.

---

## 5. Artist-Test — Vorschau-Gefühl (Silo als Maßstab)

**Test 1 — Silo als Maßstab (ca. 5 Min., jederzeit möglich, braucht nichts aus Mirai).** In Silo ein symmetrisches Mesh
(z. B. einen Kopf) laden, Symmetrie an, Knife/Cut-Werkzeug:

1. Einen Schnitt nur auf einer Seite von Kante zu Kante ziehen, **nicht** in der Kantenmitte. Beobachten: Wann
   erscheint die Gegenseite — schon beim Hover, beim Klick oder erst beim Bestätigen? Punkte, Linie oder beides?
2. Das Mesh so drehen, dass die Gegenseite verdeckt ist (Seitenansicht). Sieht man die gespiegelte Vorschau trotzdem
   (durchscheinend), gedimmt oder gar nicht?
3. Einen Schnitt quer über die Mitte auf die andere Seite ziehen. Was passiert — ein Schnitt, zwei sich kreuzende
   (ein X), oder blockiert Silo?
4. Einen Schnitt genau auf der Mittellinie beginnen oder enden lassen.
5. Einen Punkt mitten in eine Fläche setzen (falls Silo das kann).
6. (Zu F2) Auf der einen Seite schneiden und danach versuchen, auf der anderen Seite „von Hand“ genau dieselbe Linie
   nachzuzeichnen. Legt Silo die beiden zusammen, entstehen zwei fast gleiche Schnitte, oder wird abgelehnt?

Notiere pro Schritt ein, zwei Sätze: was du siehst und wie es sich anfühlt. Die Notizen werden als deine Beobachtung
hier eingetragen:

| Schritt | Beobachtung (Manu) |
|---|---|
| 1 | |
| 2 | |
| 3 | |
| 4 | |
| 5 | |
| 6 | |

**Test 2 — Vorschau-Gefühl im Lab: nicht vorbereitet.** Die Attrappe (drei Darstellungsvarianten V-a verdeckt wie die
eigene Vorschau, V-b immer sichtbar und gedimmt, V-c nur Punkte) braucht eine Ergänzung von AD-013 H2 (eine vierte
Lab-Taste, Lesezugriff auf die Knife-Vorschau), siehe §0.2. Nach Test 1 wird entschieden, ob sich das lohnt oder ob die
Varianten gleich im Slice 6c in der App gezeigt werden.

---

## 6. Entscheidungsvorlage für Manu

Nur Fragen, die Intent, Product Truth oder Priorität sind und die kein weiterer autonomer Test klären kann (M4). Die
Gleichstands-Fälle („Ties“) sind **keine** Frage: mit dem vorgeschlagenen Weg (K-C) spiegelt der Knife sie immer richtig
(INV-5), es bleibt kein sichtbarer Unterschied.

### F1 — Schnitt über die Mitte

**Situation:** Du ziehst mit Symmetrie einen Knife-Schnitt, der über die Mittellinie auf die andere Seite läuft (z. B.
quer über die Nase). Die Gegenseite ist dein eigener Schnitt — gespiegelt würde er sich mit sich selbst kreuzen. Wie
beim Rig: ein Controller, der über die Mitte greift, gehört keiner Seite allein.

| Option | Was du siehst |
|---|---|
| **A** verweigern | Der Klick auf der anderen Seite wird abgelehnt (Statuszeile: über die Mitte geht nur mit Symmetrie aus); du schneidest bis zur Mitte und setzt dort ab |
| **B** ein gemeinsamer Schnitt (X) | Beide Seiten bekommen deinen Schnitt und sein Spiegelbild; sie kreuzen sich auf der Mittellinie — auf deiner Seite entsteht also eine zweite Linie, die du nicht gezogen hast |
| **C** nur bis zur Mitte | Der Teil hinter der Mitte wird verworfen und durch das Spiegelbild deines Teils ersetzt (dein Klick dort zählt nicht) |
| UNKNOWN | — |

**Empfehlung der Planung (Empfehlung, keine Entscheidung):** A für den ersten Stand — billig und umkehrbar; Maya kennt
eine ähnliche Schutzregel (ein Multi-Cut darf mit Symmetrie nicht auf der Mittelkante beginnen, R2 §3.3). B oder C erst,
wenn Test 1 Schritt 3 zeigt, was Silo tut.

**Antwort (Manu):**

### F2 — Selbst symmetrisch gezeichneter Pfad

**Situation:** Du zeichnest den Schnitt auf beiden Seiten selbst, „spiegelbildlich nach Augenmaß“. Die Spiegelung deines
Schnitts fällt dann fast, aber nie genau auf deine eigene Linie (der Abstand liegt im Bereich von Millionstel).

| Option | Was du siehst |
|---|---|
| **A** verweigern (wie F1 A) | Sobald der Pfad die andere Seite erreicht, wird abgelehnt |
| **B** zusammenlegen | Fast gleiche Linien werden zu einer; dafür braucht es eine Fang-Toleranz, die es in der Symmetrie bisher bewusst nicht gibt |
| **C** beide behalten | Auf jeder Seite entstehen zwei fast deckungsgleiche Schnitte (hauchdünne Flächen) |
| UNKNOWN | — |

**Empfehlung der Planung:** A — es ist ein Sonderfall von F1; B würde eine Toleranz-Entscheidung nach sich ziehen.

**Antwort (Manu):**

### F3 — Ziel ohne Spiegelpartner

**Situation:** Neben ungepaarter Geometrie (magenta Punkte, z. B. `man_with_shoes_basemesh`) zeigst du mit dem Knife auf
eine Kante oder Fläche, die keine Gegenseite hat. Schon entschieden (A3 = S): dort wird verweigert. Offen ist nur, **wann**
du es erfährst. Die Probe zeigt: es lässt sich in jedem gemessenen Fall schon beim Zeigen erkennen.

| Option | Was du siehst |
|---|---|
| **A** schon beim Hover/Klick | Das Ziel wird beim Darüberfahren magenta markiert, der Klick abgelehnt; du merkst es sofort |
| **B** erst bei Enter | Du klickst den ganzen Schnitt, beim Bestätigen kommt „nicht spiegelbildlich — nichts geändert“ |
| UNKNOWN | — |

**Empfehlung der Planung:** A (Enter prüft trotzdem weiter, als Sicherheitsnetz).

**Antwort (Manu):**

### F4 — Auswahl nach dem symmetrischen Knife

**Situation:** Nach Enter wählt der Knife heute die geschnittenen Kanten (Edge-Modus). Bei Split und Edge Connect hast du
entschieden: nur die Seite, auf der du gearbeitet hast; beide Seiten nur, wenn du bewusst beide gewählt hattest.

| Option | Was du siehst |
|---|---|
| **A** die Seite, auf der du geklickt hast | Nur deine Schnittkanten sind ausgewählt; Kanten auf der Mittellinie bleiben dabei |
| **B** immer beide Seiten | Deine Kanten und ihre Spiegelkanten |
| **C** wie A, aber beide Seiten, wenn du auf beiden Seiten geklickt hast | nur relevant, wenn F1 = B |
| UNKNOWN | — |

**Empfehlung der Planung:** A (wie Split/Edge Connect); C nur, falls F1 = B.

**Antwort (Manu):**

### F5 — Eigene Knife-Symmetrie oder live koordinierter Knife

**Situation:** Du hattest überlegt, nicht alles in *eine* Symmetrie-Fähigkeit zu zwingen. Für den Knife gibt es drei Wege:

| Option | Was du siehst | Kosten |
|---|---|---|
| **A** live koordiniert (wie Silo) | Du schneidest eine Seite, die Gegenseite erscheint gespiegelt in der Vorschau und wird bei Enter mitgeschnitten | Slice 6a–6d (§3); offen bleiben F1/F2 |
| **B** einseitig schneiden, danach „Symmetrize“ | Beim Schneiden keine Gegenseite; ein eigener Schritt spiegelt danach die Topologie einer Hälfte auf die andere (die Gegenseite wird dabei neu aufgebaut) | neue Fähigkeit, eigene AD; Gegenseite bekommt jedes Mal neue IDs (später wichtig für Gewichte, Morphs, Rig) |
| **C** virtuelle Hälfte (wie Wings) | Du modellierst nur eine Hälfte, die andere ist ein Spiegelbild, das nicht editiert werden kann | Architekturänderung (AD-SYM-01 sagt für V1 „nein“) |
| UNKNOWN | — | — |

**Was die Evidenz sagt (für den Knife, nicht allgemein):** A funktioniert für jeden einseitigen Schnitt exakt (Probe K10,
K4); die Probleme, die einen eigenen Weg nahegelegt hätten, sind damit gelöst. **Empfehlung der Planung:** A für den
Knife; B oder C nur, wenn du sie aus anderen Gründen willst (z. B. für andere Werkzeuge).

**Antwort (Manu):**
