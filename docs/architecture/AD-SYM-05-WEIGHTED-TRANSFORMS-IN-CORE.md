# AD-SYM-05 — Weighted transforms in the Core (symmetric Soft Selection, slice SS1)

**Status:** **DECIDED — go for SS1 (Manu, 2026-10-14, in the chat: "Go für SS1")**, after the independent review (2026-10-14). Design note before code for the one Core
change of symmetric Soft ([AD-SYM-04](AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md) §5.2 SS1, review item R-5;
[CORE_V1_FREEZE](CORE_V1_FREEZE.md) §7). Review CLAUDE-001: **ACCEPT WITH CHANGES**, no blocker; every finding is answered
in §10 and worked into the text. A Core change is a Haltepunkt (Development System §5); Manu's go is given, so **SS1 is built per this note** (§4–§6).
Where a section still says "proposed" or "Manu's go", this status wins.
**SS1 is built (2026-10-14, [implementation note](#implementation-note-2026-10-14-slice-ss1)).**
**Mode (M5):** Type C (Architecture Gate). Documents only: no change under `src/`, `tests/`, `experiments/` or `playground/`.
**Read at:** `c2bc3e3` (branch `claude/festive-allen-pyajvv`, SS0 committed). Line numbers refer to that commit.
**Basis (binding, only linked):** AD-SYM-04 (Decision record: Q-4 = **P-a**; §4 C-1…C-7 and R-1…R-5; §5.1 D-1…D-5; the
[SS0 note](AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md#implementation-note-2026-10-14-slice-ss0)), [AD-020](AD-020-SOFT-SELECTION-APP-PATH.md)
("Promotion decision", §3 Q2, §8, §13 F3/F4), [AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md) (§2.2, §2.4, §3),
[AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md), [AD-014](AD-014_Core-Change-Basis-Parameter-for-ScaleOperation.md)
(precedent: Core change with a byte-identical old path), `src/core/operation.py` (AD-003 incremental contract).

**Evidence tags** as in AD-SYM-04: **[Code]** read at `c2bc3e3` (file:line), **[Doc]**, **[Probe]** (SS0, the review's
scratch scripts, or a scratch computation named in place), **(Reading)** a derivation, `PROVISIONAL` for every agent-set
choice.

---

## 0. Inputs (decided, not re-decided here)

| # | Input | Source |
|---|---|---|
| IN-1 | The weighting moves into the Core **once, together with symmetric Soft** ("Core opened once"). | M-5; AD-020 "Promotion decision" (Way 2) |
| IN-2 | **P-a:** seam vertices reached only by the falloff slide in the plane; the pivot stays the own-side selection centre; selected seam vertices keep today's rules (KEEP 2026-10-03). A Core seam-rule change inside SS1. | Q-4 (Manu 2026-10-14) |
| IN-3 | **R-6 is not a stop; it becomes a requirement on the design** (the SS0 counterexample: a `valid` mesh with an edge across the plane and no end point on it). | Manu 2026-10-14 (chat), recorded in AD-SYM-04 Decision record |
| IN-4 | SS0: the union field is mirrored bit for bit on every exactly symmetric asset case; the falloff reaches the seam at ordinary radii (head: half the rows at the default 15 %); the pairing costs more than the influence at gesture start. | SS0 note §1, §3, §4 |
| IN-5 | Scale formula `1 + w(F − 1)` (linear); Soft Rotate/Scale KEEP. | AD-020 S2c verdict, row 6 |

---

## 1. What SS1 must deliver

| # | Requirement |
|---|---|
| RQ-1 | The per-vertex weighting lives in the Core loop with today's soft semantics: Move `w·Δ`, Rotate `w·θ`, Scale `1 + w(F − 1)` evaluated absolutely for `w < 1`. **Non-symmetric Soft stays bitwise identical** to the Q2-D ops of today, **including what they accept** (e.g. a new rotation axis per update). |
| RQ-2 | **Without weights, every gesture is byte-identical to today** — plain and symmetric Move/Rotate/Scale, incl. both seam checks, the per-side pivot and the refusal texts (AD-SYM-04 R-1, R-4). |
| RQ-3 | **Weights and symmetry in one operation instance** (AD-SYM-02 §3, point 1): plain step, conjugate step, projected step, each scaled by the vertex's weight; for pair-consistent input the result is an exact mirror (bitwise under E1). |
| RQ-4 | **P-a:** seam vertices reached only by the falloff take the weighted step, are projected onto the plane and are exempt from **both** seam checks; a selected seam vertex keeps today's rules. |
| RQ-5 | **R-6** (IN-3): no guarantee of SS1 or SS2 may depend on the mesh having a seam loop or no straddling edges (§3). |
| RQ-6 | `src/mirai/soft_selection/ops.py` is migrated **in the same commit** (no double weighting, AD-SYM-04 R-2); the AD-020 F3 tripwires flip on purpose. |
| RQ-7 | Every absolute evaluation is a **visible, documented deviation** from the incremental contract of `core/operation.py:15-25` (R-3). |
| RQ-8 | **SS1 changes no behaviour anyone can see:** the app still refuses Soft + symmetry (AD-SYM-04 I-8) until SS2 lifts it. |

---

## 2. Freeze rule (CORE_V1_FREEZE §7), step by step

1. **Requirement.** Symmetric Soft (M-3/M-5) with P-a (Q-4).
2. **Not solvable without a Core change.** *(a)* The mirror logic of the transform family has exactly one home, the Core
   (`_PivotTransformOperation`, `transform.py:298-366`; `MoveOperation._transform_position`, `move.py:103-110`;
   AD-SYM-02 §1 "genau eine Stelle", INV-9/AR-10). Q2-D soft ops outside the Core would need a second copy of it.
   *(b)* The seam checks that P-a must narrow sit in the Core (`transform.py:338-341`, `:343-346`, `:382-387`,
   `:411-416`). *(c)* M-5 decided Way 2. [Code, Doc]
3. **Problem documented.** AD-SYM-04 §4 (C-1…C-7), the SS0 note, this note.
4. **Smallest extension.** §4: one channel already in use (`params["influence"]`), one new category key inside the
   existing `params["symmetry"]`, the placeholder blend replaced, accumulated totals only where an absolute path needs
   them. **No new public Core API** (§5.1). No change to `Mesh`, the `Operation` lifecycle, `OperationContext`,
   `HistoryStack`, `VertexTransformCommand`, any topology operation.
5. **Tests/contract.** §6.
6. **Change only after** Manu's go (the independent review is done, §10).

---

## 3. R-6 as a design requirement (IN-3)

### 3.1 What the counterexample shows

The SS0 quad `s(+0.5,0,0) → v'(−0.1,1,0) → v(+0.1,1,0) → a(−0.5,0,0)`, X axis, `valid`, four straddling edges, seed `s`
(partner `a`), geodesic. Plain field from `s`: `d(v') = |s − v'| = 1.166`, `d(v) = 1.166 + 0.2 = 1.366`. Union field over
`{s, a}`: `d(v) = |a − v| = 1.166`. [Probe, SS0 `probe_straddling_quad`] The quad is already self-intersecting at rest
(edge `s–v'` crosses `v–a`; review R-5) — it is a test fixture for exactness, not a shape anyone models.

*(Reading, general form, on distances.)* Let `M` be the mirror map on vertices and `d_S` the plain distance field of the
seeds `S`. On every mirror-symmetric edge graph under E1, `M` is an automorphism that preserves edge lengths and point
distances bit for bit (mirrored coordinate differences only change sign), and Dijkstra's value is the minimum over paths of
left-fold float sums, so `d_{M(S)}(v) = d_S(M v)` bit for bit and

> **union distance `d_U(v) = min(d_S(v), d_S(M v))`; the pair weight is `curve(d_U)`, the same value for both members.**

This is stated on distances on purpose: the `smooth` curve is not monotone in floating point (2688 of 200 000 sampled
adjacent-float pairs give `f(t⁺) < f(t)`; the other five curves 0 [Probe, review `ss1_check.py` (b), re-run here]), so the
"larger weight of the pair" form can differ in the last bit where `d_S(v) ≠ d_S(M v)`. It holds with and without
straddling edges (it explains why SS0 found the pairs equal on the quad too). The SS0 half "equals each side's own field"
means `d_S(M v) ≥ d_S(v)` for every own-side `v`; reflecting a path at a vertex on the plane proves it when every crossing
passes through such a vertex, and on the quad it fails because `s` reaches `v'` across the plane faster than `v`.

**Consequence.** Where `d_S(v) ≠ d_S(M v)`, the plain field is not mirror-symmetric, so an exactly symmetric weighting must
differ from plain Soft at `v` **or** at `M v`. *Which* member deviates is a choice: the union field lets the own-side member
`v` deviate; R6-C below keeps the own side exactly plain and lets the mirrored member deviate (where the step is the
conjugate anyway).

### 3.2 Options (an SS2 choice; SS1 is unaffected)

The Core receives weights only (R6-3), so this choice does not change SS1's code. It belongs to SS2's field function.

| | Option | Cost |
|---|---|---|
| R6-A | **Union field** (one weight per pair by construction): "equals the own side's plain field" is an observed property of meshes without straddling edges (all current assets with pairs, SS0), not a promise. | On a straddling mesh a few own-side vertices near the plane get a larger weight than plain Soft (the quad: `v` from distance 1.366 to 1.166). Defined for seeds on both sides and for unpaired vertices (they get a value directly). |
| R6-B | Keep the promise, check visibly: refuse geodesic symmetric Soft when the falloff contains a straddling edge. | Refuses `valid` meshes for a property the Artist cannot see; an O(E) check per gesture start and preview; Euclidean never needs it, so the metrics behave differently under symmetry. |
| R6-C | **Own side exactly plain:** the pair weight is the plain weight of the member on the seeds' side. (Equal to R6-A wherever there are no straddling edges, because there the own-side value is the larger one.) | Undefined when explicit seeds lie on both sides (the same domain where O-1 is open, §3.3); needs a side classification; unpaired vertices on the other side need a rule (D-2). |

*(Reading, `PROVISIONAL` lean for SS2:)* R6-A — it is defined everywhere and needs no side rule. R6-C is a fair alternative
when seeds lie on one side; whether the Artist should feel the difference is one SS2 question together with O-1 (§8), on a
case no current asset shows.

**Binding for SS1:**

- **R6-1** Every SS1 guarantee (exact mirror, bitwise under E1; seam vertices exactly on the plane; completeness unchanged;
  one Undo step; cancel exact) holds on straddling meshes: the SS0 quad **and** a straddling fixture with a seam vertex
  inside the falloff (§6 T-8), so R-6 and P-a are tested together. SS2's gesture tests take the same fixtures.
- **R6-3** The Core never relies on graph symmetry. It receives weights and categories; **pair consistency is a caller
  precondition** (§4.3).

**Moved to SS2:** the D-1 rewording in AD-SYM-04 §5.1 (formerly R6-2) is written with the field function; *draft:* "The
symmetric field gives each mirror pair one distance, the minimum over seeds ∪ mirrored seeds (never a sum), and one weight
from it; a seam vertex carries one weight. That the own side equals its plain field holds only where no edge path from a
seed crosses the plane between two vertices off it (every current asset case with pairs, SS0) — an observation, not a
promise." The former R6-4 (category not from the nearest seed) is **withdrawn** (§3.3).

### 3.3 Finding: R-6 also reaches the step category — open for SS2 (O-1)

The union field also tells which seed is nearest. On the quad `v'` (negative side) is nearest to the explicit seed `s`, and
`v` (positive side) to the mirrored seed `a`. Two pair-consistent ways to give falloff vertices their step, measured with
Move `+x 0.5`, `w = 0.6` [Probe, review `quad_shape.py`, re-run here]:

| | Rule | Quad after the step | Elsewhere |
|---|---|---|---|
| K-near | category of the nearest seed (explicit → plain, mirrored → conjugate) | `v'` +0.2, `v` −0.2: **the crossing disappears** (each vertex moves with the seed it is connected to) | Follows connectivity on straddling meshes; matches "explicit selection wins" for a selection covering both sides. Pair-consistent only on symmetric graphs and **needs a tie rule** (ties `d_S(v) = d_S(M v)` occur whenever the shortest path runs through the seam). |
| K-side | category by side of the plane relative to the seeds | `v` +0.4, `v'` −0.4: the crossing stays and grows | Always pair-consistent without a tie rule (partners lie on opposite sides). Undefined when explicit seeds lie on both sides. |

*Corrected after review R-5:* the first version said the opposite (K-near folds, K-side stretches) because it overlooked
that the quad crosses itself at rest. On every mesh without straddling edges and with seeds on one side the two rules agree
(the reflection argument, ties aside). **Not decided here; O-1 stays fully open for SS2** (§8).

---

## 4. Design of the Core change (`PROVISIONAL` in names, binding in rules once accepted)

### 4.1 Channel

`params["influence"]: Mapping[VertexId, float]`, the key the soft ops use today (AD-020 §3.1 A; the `params` channel of
AD-SYM-02 §2.2). Read by `VertexTransformOperation._on_begin` (`transform.py:223-237`):

- **absent → today:** `_weights = {vid: 1.0}` and nothing else changes (RQ-2);
- **present →** validated before anything is stored: keys exactly the op's vertex set, every value finite and in `(0, 1]`
  (else `ValueError`); `_weights` becomes that map. Stale IDs stay the caller's job (L10): a caller filters its map and
  hands the Core a **new** params dict with the filtered `influence` (§5.1); the Core already raises for an unknown vertex
  today.
- `RotateOperation`/`ScaleOperation` with weights need `params["pivot"]` (else `ValueError`): the Core default would be the
  centroid of the *influenced* set (AD-020 E7).
- With weights, every `seam_vertex_ids` member must carry exactly `1.0` (else `ValueError`): a selected seam vertex is a
  seed, and §4.2 relies on it (review R-7). Cheap, needs no pairing.

### 4.2 The per-vertex step

The placeholder blend `pos + w·(T(pos) − pos)` (`transform.py:265-269`) is **deleted**: it is not path independent for
Rotate and Scale (AD-020 F7, S1 FINDINGS) and has no caller. Instead each concrete op weights its own parameter, then the
category applies. `w == 1.0` always takes today's arithmetic on the live position, operation for operation (RQ-1/RQ-2).

| Op | plain | conjugate (`mirrored_vertex_ids`) | selected seam (`seam_vertex_ids`, `w = 1` checked) | **falloff seam (new, §4.3)** |
|---|---|---|---|---|
| Move | `pos + w·Δ` | `pos + mirror_vec(w·Δ)` | `pos + proj(Δ)` (today) | `pos + proj(w·Δ)`, incremental (projection is linear) |
| Rotate | `R(pos, P, a, w·θ)` incremental | `M(R(M pos, P, a, w·θ))` incremental | today (both checks) | **`proj(R(start, P, a, w·Θ))`, absolute** |
| Scale | `w = 1`: `S(pos, F_step)`; `w < 1`: `S(start, 1 + w(F − 1))` absolute | `M(S(M ·, …))` of the same | today (both checks) | **`proj(S(start, 1 + w(F − 1)))`, absolute, also at `w = 1`** |

`P` the fixed pivot, `a` the axis of the step (fixed only when the absolute Rotate path is in use, §4.4), `Θ` and `F` the
angle and the per-axis factor accumulated since `begin()`, `M` the mirror (`mirror_point`, `transform.py:141-146`), `proj`
the projection onto the plane.

- **Why falloff-seam Rotate is absolute.** Rotating and then projecting depends on how the drag is chunked into steps.
  Scratch computation (plane `x = 0`, pivot `(0.5, 0, 0)`, axis `y`, seam vertex `(0, 0, 1)`, `w = 0.5`, total 90°):
  one step gives `z = 1.061`, two steps `1.222`, sixty steps `1.387`; the absolute form gives 1.061 for any chunking
  [Probe, scratch; reproduced by the review]. The Rotate tool explicitly wants chunk independence (`rotate.py:131`).
  Today the problem cannot occur: a seam vertex is only rotated about the normal through a pivot on the plane, where the
  projection removes rounding only. Falloff-seam Scale is absolute even at `w = 1`, because a rotated basis and the
  projection do not commute.
- **Why the projected result is the symmetric one** *(Reading, confirmed by the review):* for a seam vertex `M p = p`, so
  the conjugate intent is `M(R(p))`, and `proj(R(p))` is the midpoint of `R(p)` and `M(R(p))`; under E1 it lands on
  `x == 0.0` exactly.
- **Exactness of pairs.** For equal weights the partner's step is computed with the same inputs as its source's (today's
  `M ∘ T ∘ M` construction), so a pair stays a bitwise mirror under E1; Scale's absolute path uses the partner's start
  position, which is the exact mirror of its source's. [Probe: review `ss1_check.py` (c) — 60 updates per op, both metrics,
  on the quad, `subd_cube` X, `head_basemesh` X: pairs bitwise mirrored, falloff seam at `x == 0.0`.]

### 4.3 Categories: P-a as a new category, not as an edited check

`params["symmetry"]` gains one key, **`falloff_seam_vertex_ids`** (name `PROVISIONAL`): seam vertices in the op's vertex set
that are not explicit seeds. Rules:

- allowed only with `params["influence"]`; disjoint from `seam_vertex_ids` and `mirrored_vertex_ids` (else `ValueError`
  at `begin()`);
- **the two seam checks keep their scope unchanged:** they apply to `seam_vertex_ids` exactly as today
  (`transform.py:338-346`). P-a is realised by the caller putting falloff-reached seam vertices into the new key, so the
  Core needs no "is it selected?" knowledge and the tool-level arm refusal `_refuse_if_seam_unsafe`
  (`tools/transform.py:398-410`, read from `seam_vertex_ids`) needs no change;
- the categories are **step kinds, not correspondence states**: an unpaired vertex on the mirrored side inside the falloff
  takes the conjugate step with its own weight (D-2), a vertex in no set takes the plain step.

**Caller preconditions, not checked by the Core (R6-3):** the two members of a pair carry the same weight and opposite
categories (or both plain when both are explicit seeds, today's "explicit selection wins", `move.py:35-45`). The Core has no
pairing and gets none (AD-SYM-01: correspondence is derived in `mirai`; AD-SYM-02 §3, point 3: no mirror-result
structure); it already trusts `mirrored_vertex_ids`/`seam_vertex_ids` unchecked today (`move.py:99-100`,
`transform.py:334-335`). A violation gives a non-mirrored result, which the completeness oracle of SS2 and of the F-a guard
catches. *Rejected:* a Core check by mirrored positions — it would re-derive correspondence inside the Core.

*Rejected alternative for P-a:* exempt seam vertices by weight (`w < 1`). A non-seed very close to a seed can round to
`w = 1.0`, so the seam rule would depend on a float, and a radius-0 gesture would have to be special-cased.

### 4.4 Accumulated state and the contract deviation (RQ-7)

- **Scale, with weights:** accumulates `F` per axis and fixes the basis for the gesture — exactly today's `SoftScaleOperation`
  (`ops.py:185-201`; AD-020 F6/L5), so non-symmetric Soft does not change.
- **Rotate, only when `falloff_seam_vertex_ids` is non-empty:** accumulates `Θ`, fixes the axis, and refuses a non-finite
  `angle` before accumulating (one NaN step would poison every later absolute evaluation). Without falloff seam vertices a
  weighted Rotate accepts a new axis per update, as `SoftRotateOperation` does today (`ops.py:138-147`; the existing
  `ROTATE_STEPS`, `tests/test_soft_selection_ops.py:91-92`, change the axis at step 3). *Corrected after review R-1:* the
  first version fixed the axis for every weighted Rotate, which would have changed non-symmetric Soft.
- **Order:** validate (basis/axis unchanged where fixed, factor/angle finite, seam step check for `seam_vertex_ids`) →
  accumulate → loop. A refusal leaves positions and totals as they were.
- **Visible deviation:** `core/operation.py` and `transform.py` state that with `params["influence"]`, Scale evaluates
  `w < 1` vertices and Rotate/Scale evaluate falloff-seam vertices **absolutely from the `begin()` snapshot**; everything
  else stays incremental. The snapshot exists already (`_start_positions`, `transform.py:228-230`).
- Without weights nothing is accumulated and nothing is fixed: the plain Core keeps accepting a new basis or axis per update
  (FINDINGS L5/§5.7 untouched).

### 4.5 Not touched

`Mesh`, `Operation`, `OperationContext`, `HistoryStack`, `VertexTransformCommand`, `_on_commit`/`_on_cancel`, the
`description` mechanism, `rotation_keeps_plane`/`scale_keeps_plane`/`pivot_on_plane`, `SEAM_TOLERANCE`, every topology
operation. `supports_symmetry` stays `True` on the three Core ops (C-7 is met by the Core classes). No public accessor is
added (no `total_factor` on `ScaleOperation`, §5.1).

---

## 5. Migration in the same commit (RQ-6)

### 5.1 `src/mirai/soft_selection/ops.py`

| | Option | Cost |
|---|---|---|
| M-a | Delete the soft op classes; tools build the Core ops with `params["influence"]`. | Smallest code; every importer changes (tools, `__init__`, tests incl. the `type(op) is Soft…Operation` assertions, the Mehlsack bit-identity tests); the op-level symmetry backstop (AD-020 §8.2) loses its home before SS2. |
| **M-b** | **Keep `SoftMove/Rotate/ScaleOperation` as thin subclasses of the Core `MoveOperation`/`RotateOperation`/`ScaleOperation`.** | One extra thin layer; names, tools, Application and importers unchanged; SS2 then removes exactly the backstop. |

**Proposal (`PROVISIONAL`): M-b**, confirmed by the review. What the thin classes hold — and nothing else (review R-3):

- `description` ("Soft Move/Rotate/Scale Vertices");
- `_on_begin`: refuse `params["symmetry"]` until SS2 (`supports_symmetry = False`); require `params["influence"]`; filter
  stale IDs (L10) into **`_soft_weights`** (own `_soft_` attribute, so tripwire (10) keeps holding) and call the Core
  `_on_begin` with a **new** params dict carrying the filtered `influence` and a view of the filtered set (today's
  `ops.py:99-104` forwards the caller's params unchanged, which would trip the Core's key-set check);
- `weights` property → `dict(self._soft_weights)` (read at nine sites in `tests/test_application_soft_selection.py`);
- **no arithmetic and no other state:** `_scale_about`, the tuple sum, `_soft_start`, `_soft_total`, `_soft_basis*`,
  `_weighted_factor`, `scale_formula` and `total_factor` go. The two tests that read `total_factor`
  (`tests/test_soft_selection_ops.py:523-533`, the Mehlsack comparison below) check behaviour instead (positions after the
  refused and the next update) — no Core API is added for them.

`scale_formula` and `"power"` leave `src` (only tests use them; S2c kept linear, IN-5; the Core should not carry a formula
switch). Tools and `Application` do not change in SS1 (`_soft_show_op_weights` keeps reading `params["influence"]`,
`application.py:1953`).

### 5.2 Consumers outside `src/` that the change reaches [Code; review R-2]

| Consumer | What happens | Done in the SS1 commit |
|---|---|---|
| Mehlsack Lab, `signed_ops.py:92-95` | passes its own `params` — incl. `"influence"` with **negative** weights — into the Core `_on_begin`; the new validation would refuse them | its inner context drops `"influence"` (the Core then sees no weights and never blends: the Lab's tripwire `test_base_never_blends_one_update_equals_the_closed_form` keeps holding) |
| Mehlsack Lab, `signed_ops.py:48` | imports `SCALE_FORMULAS` from `mirai.soft_selection.ops` | the constant moves into the Lab (signed weights are Lab-only, no promotion, M3) |
| Mehlsack tests, `test_signed_rotate_scale.py:80`, `:85-98` | Rotate compared with `SoftRotateOperation` (unchanged under M-b); Scale compared bit for bit with `SoftScaleOperation` for `"linear"` **and** `"power"`, reading `total_factor`/`scale_formula` | linear half: compared against the thin `SoftScaleOperation` on positions and commands only; `"power"` half: against the closed form `F ** w` the file already tests (`:142-144`) |
| S1 record `weighted_ops.py:86-92` and `probe_cost.py:50-55` | forwards the caller's `params` with stale IDs in `influence` into the Core `_on_begin` → the new key-set check fires (`test_weighted_ops.py:399-404`) | the same one-line change as Mehlsack: its inner context drops `"influence"`; its arithmetic stays as recorded |
| `tests/test_soft_selection_ops.py` | `"power"` parametrisations (`:146-170`, `:284-298`) | **dropped** with `scale_formula` (named, not "ported"); the rest ported (§6 T-4) |
| Symmetry Lab, Playground, `head_topology_walkthrough/wt.py` | reach the Core loop through the tools, or plain `MoveOperation` without weights | no change; suites run (§6) |

`VertexTransformOperation` stays importable from `core.operations.transform`: Mehlsack (`signed_ops.py:47`) and the S1
record rely on it.

### 5.3 AD-020 F3 tripwires (§13, eleven items)

(1) "base never blends" → **flips** into "the Core's weighted step equals the closed form" (and the placeholder test
`test_core_placeholder_blend_is_not_path_independent` goes with the placeholder); (2) `vertex_id=` and kwargs passed →
stays, now inside the Core; (3)/(4) the Scale and Move copies → **gone** (no copies), replaced by the replay oracle (§6
T-3); (5) "base `_on_begin` reads target/selection.vertices/pivot only" → **restated** as the new Core contract test (it now
also reads and validates `params["influence"]`); (6) base `_on_update` iterates exactly the view → stays; (7) description →
stays (M-b); (8) `supports_symmetry` False → stays on the thin classes until SS2; (9) `pivot` → stays; (10) own attributes
carry the `_soft_` prefix, AST scan "no Core private" → stays, held by §5.1 (`_soft_weights` only); (11) importability of
`VertexTransformOperation` from `core.operations.transform` → no longer needed by `src/mirai`, still relied on by Mehlsack
and the S1 record. CORE_V1_FREEZE §7.1 gets its entry in the SS1 commit; the 2026-10-10 docs-only note there is marked
superseded (dated).

---

## 6. Tests (the SS1 gate)

| # | Test | Oracle |
|---|---|---|
| T-1 | No weights → today | Every existing Core transform suite unchanged and green: `tests/test_transform_operations.py`, `test_symmetric_move.py`, `test_symmetric_transform.py`, `test_core.py` (AD-003 incremental) |
| T-2 | All weights `1.0` ≡ no weights | Bitwise, Move/Rotate/Scale, with and without `params["symmetry"]`, with and without a basis, **with an axis change for Rotate** |
| T-3 | **Non-symmetric Soft bitwise identical to Q2-D** | A **pure replay function** in `tests/` (start positions, weights, pivot, step list → positions after every step, plus the start/end maps): a copy of today's arithmetic (`_scale_about`, `_triple`, the tuple sum, `rotate_around_axis(pos, pivot, axis, angle if w == 1.0 else w * angle)`), **no Core base class**, so it cannot follow the change (review R-4). Run on the AD-020 P-D set **and** the existing `MOVE_STEPS`, `ROTATE_STEPS`, `SCALE_STEPS`, `SCALE_BASIS_STEPS`, radii {0, the 15 % step, 1.0}. Same platform, so libm cannot differ (golden numbers could) |
| T-4 | Weighted semantics | The closed-form and path-independence tests of `tests/test_soft_selection_ops.py` against the Core ops; the `"power"` ones dropped (§5.2); refusal texts of weighted refusals keep the words the ported tests match (`pivot`, `basis`, `weight`, `influenced vertex set`), or the test changes are listed in the SS1 commit |
| T-5 | Refusals before anything moves | Weights outside `(0, 1]`, non-finite, keys ≠ vertex set; weighted Rotate/Scale without pivot; a `seam_vertex_ids` member with `w ≠ 1`; basis change mid-gesture with weights (totals unchanged); with falloff seam vertices: axis change and non-finite angle (Rotate); `falloff_seam_vertex_ids` without weights or overlapping another category |
| T-6 | Symmetric + weighted exactness | `subd_cube` X and `head_basemesh` X, hand-built pair-consistent weights (no SS2 field code in SS1): after N updates every pair is a bitwise mirror, seam coordinates exactly `0.0`, `symmetry_state` still `valid`, one History entry, Undo/Redo and cancel exact |
| T-7 | P-a | Falloff seam only: Rotate about an axis not parallel to the normal with the pivot off the plane and non-uniform Scale in a tilted basis run, stay on the plane, and 1 step vs 60 steps agree to rounding (absolute path). One selected seam vertex added: today's refusals, both checks, unchanged texts (R-4) |
| T-8 | **R-6 fixtures** | T-6's oracle on the SS0 straddling quad **and** on a straddling fixture with a seam vertex inside the falloff (e.g. the quad plus one vertex on the plane connected to `v` and `v'`; review R-11) |
| T-9 | Consumers | Mehlsack tripwire and comparison tests (§5.2), the S1 record's suite and `probe_cost.py` green after the `"influence"` strip |

**Suites** (AGENTS §8a, a `src/core` change): `tests` fully; `experiments/symmetry_lab/tests` and `playground/tests`
(both reach the Core loop through the tools); `experiments/soft_selection/tests` and `experiments/mehlsack_lab/tests`
(direct consumers, §5.2) — once each at the end, with `xvfb-run -a`.

---

## 7. Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | Regression in every Move/Rotate/Scale gesture | The no-weights path is the old code path (§4.1); T-1, T-2. Per-vertex cost: plain gestures pay today's dict read and compare (`transform.py:265-266`); soft gestures under M-b now run through the category tests (two or three `frozenset` lookups per vertex per update) and symmetric gestures gain the new category test — negligible against the 8 ms bar; the `soft_w` drag row (AD-SYM-04 D-4) measures it if needed |
| R-2 | Double weighting | One commit; M-b removes all soft arithmetic; Mehlsack and the S1 record strip the key (§5.2); tripwire (1) flips on purpose |
| R-3 | Contract deviation in the Core | §4.4, written into `operation.py` |
| R-4 | Artist-verdicted `w = 1` behaviour | Seam checks keep their scope (§4.3); the per-side pivot is a tool function, untouched |
| R-5 | Process | This note → review (done, §10) → Manu's go → SS1 |
| R-6′ | The absolute Rotate path is new behaviour | Reachable only with `falloff_seam_vertex_ids`, i.e. only after SS2 |

---

## 8. Carried to SS2/SS3 (not decided here)

- **O-1 Step category** of falloff vertices (§3.3): K-near (follows connectivity, needs a tie rule) or K-side (tie-free,
  undefined for seeds on both sides), and a rule for explicit seeds on both sides. Together with **R6-A vs R6-C** (§3.2):
  possibly one Artist question in SS2, on a case no current asset shows.
- **The field function:** the union field, or the plain field once plus the pair minimum of the two **distances**
  (`curve(min(d_S(v), d_S(M v)))`, equal on symmetric graphs; not the maximum of two weights, §3.1); one weight per pair by
  construction; ambiguous vertices inside the falloff; the D-1 rewording (§3.2 draft). Edge case: the Euclidean
  bounding-box prefilter (`influence.py:100-108`) is per seed set, so the two variants can differ by rounding for a vertex
  at `d ≈ r`; pair consistency of each is not affected.
- **D-2** refusals (seed without partner).
- **D-3, tool side:** classify falloff seam vertices into the new key. With a *selected* seam vertex, the soft path must use
  `symmetric_default_pivot` (`selection_helpers.py:90-115`) like plain symmetric R/S — today the soft branch sets
  `primary_pivot` first and skips it (`tools/transform.py:363-385`), which would turn the per-side fallback (R-4, KEEP) into
  a refusal — **and pass seeds ∪ their partners as the fallback set**, not the influenced set (`tools/transform.py:380`):
  otherwise the fallback pivot moves with the radius (review R-10).
- **Cost:** the pairing dominates the gesture start (SS0 §4) and would repeat on every preview refresh; reuse per mesh
  version versus AR-1/INV-3 is SS2's design question; the reference-PC run of the SS0 probe is still open.
- Lifting I-8 (`application.py:1725-1728`, `:1787-1797`) and the M-b backstop together; bands on both sides (SS3, D-5).
- AD-SYM-04 §5.1 D-3 still describes P-a's exemption as "(`w < 1`)"; aligned with §4.3 (category, not weight) in the SS1
  commit.

---

## 9. Questions

**Artist:** none for SS1 (no visible change, RQ-8; P-a and R-6 are decided). O-1 and R6-A/R6-C may become one question in
SS2.

**To the review (answered in §10):** (1) §3.1 pair level and R6-A; (2) the new category for P-a; (3) the absolute
falloff-seam Rotate; (4) byte identity of the no-weights path; (5) M-a or M-b; (6) missing consumers.

---

## 10. Review

**Independent review:** [AD-SYM-05_REVIEW_CLAUDE_001](../archive/symmetry_lab/reviews/AD-SYM-05_REVIEW_CLAUDE_001.md)
(fresh session, `claude/festive-allen-pyajvv` @ `4550327`, archived unedited). Verdict: **ACCEPT WITH CHANGES**, no
blocker; R-1 and R-2 to be fixed before code. Confirmed without change: §2, §4.1, the §4.2 table (with R-1/R-7), §4.3, §4.4's
deviation note, the Mehlsack strip, §6's suite scope, §7 R-2/R-4/R-5, every cited line number; the six §9 questions are
answered (pair level holds bitwise on distances, the new category is the smallest correct form, the absolute path is needed,
the no-weights path is byte-identical, M-b, the missing consumers). Every finding was re-checked against the code or
re-run before it was taken over (`tests/test_soft_selection_ops.py:91-92`; `test_signed_rotate_scale.py:80-98`;
`weighted_ops.py:84-93` with `test_weighted_ops.py:399-404`; the quad crossings before/after K-near and K-side; the `smooth`
monotonicity count, 2688 of 200 000). Nothing beyond the reviewer's own proposals was decided.

| Finding | Severity | Answer |
|---|---|---|
| R-1 — fixing the axis for every weighted Rotate changes non-symmetric Soft | major | **Fixed, as proposed.** §4.4: `Θ` and the fixed axis only with falloff seam vertices, non-finite angle refused there; RQ-1 names "what they accept"; T-2 with an axis change; T-5 tests the scoped refusal |
| R-2 — §5.2 misses consumers | major | **Fixed.** §5.2: Mehlsack Scale comparison (linear against the thin class, `"power"` against its closed form), the S1 record and `probe_cost.py` get the same `"influence"` strip as Mehlsack, the dropped `"power"` tests named |
| R-3 — M-b's surface unspecified | medium | **Fixed, smallest variant.** §5.1: `_soft_weights` + `weights`, a new filtered params dict, no other state; `total_factor` goes and its two readers test behaviour instead — no Core API added (§2 step 4, §4.5) |
| R-4 — T-3's oracle is not independent | medium | **Fixed, reviewer's form.** T-3 is a pure replay function without a Core base class, on P-D and the existing step lists |
| R-5 — §3.3 inverted | medium | **Fixed.** Table corrected (K-near untangles the quad, K-side keeps the crossing; the quad crosses itself at rest); the trade-off restated (tie rule vs domain); R6-4 withdrawn; O-1 fully open |
| R-6 — §3.1 "Consequence" and R6-C row inaccurate | medium | **Fixed.** The consequence now says *one* member must deviate and which one is a choice; R6-C described as "own side exactly plain" with its real costs; R6-A is a lean for SS2, not binding; R6-1/R6-3 stay binding for SS1, the D-1 rewording moves to SS2 |
| R-7 — weight on `seam_vertex_ids` assumed | minor | **Taken.** §4.1/§4.2: `w ≠ 1` on a selected seam vertex → `ValueError`; T-5 |
| R-8 — bitwise identity holds on distances | minor | **Fixed.** §3.1 stated on distances, pair weight `curve(min distance)`; §8 "pair minimum of the distances" |
| R-9 — tripwire mapping (5), (10), (11) | minor | **Fixed** in §5.3 |
| R-10 — D-3 fallback set for SS2 | minor | **Taken into §8:** seeds ∪ partners, not the influenced set |
| R-11 — the R-6 fixture does not exercise P-a | minor | **Taken.** T-8 adds a straddling fixture with a seam vertex inside the falloff |
| R-12 — texts and references | nit | **Fixed:** T-4 names the matched words; AD-SYM-02 citations now "§3, point 1/3"; the AD-SYM-04 D-3 wording is aligned in the SS1 commit (§8); §7 R-1 states the extra lookups |

A second review is not required by the findings (no blocker; every change is the reviewer's own proposal or a direct
consequence of it). Manu may ask for one.

---

## Implementation note (2026-10-14, slice SS1)

**Built** (one commit, Core + migration, RQ-6), per §4–§6:

- `core/operations/transform.py`, `move.py`: `params["influence"]` read and validated in
  `VertexTransformOperation._on_begin` (§4.1); absent → the old loop, byte-identical. Present → the loop calls a new
  protected hook `_weighted_position(pos, w, vertex_id=…, **kwargs)` per op, implementing the §4.2 table; `w == 1.0`
  delegates to the unweighted `_transform_position`. The placeholder blend is deleted. `falloff_seam_vertex_ids` in
  `params["symmetry"]` (§4.3) with the three begin-time rules (only with weights, disjoint, `seam_vertex_ids` at `w = 1`).
  §4.4 order validate → accumulate → loop in `_PivotTransformOperation._on_update` (`_check_weighted_step`,
  `_accumulate`); Scale accumulates `F` and fixes the basis for every weighted gesture, Rotate accumulates `Θ` and fixes the
  axis only with falloff seam vertices. The deviation is written in `core/operation.py` and the `transform.py` docstring.
- `src/mirai/soft_selection/ops.py` (M-b): a `_SoftBegin` mixin in front of the Core op in each class's MRO — label,
  symmetry backstop, `influence` required, stale-ID filter into `_soft_weights`, `weights`; new params dict with the
  filtered map and a filtered view. No arithmetic, no other state.
- Consumers (§5.2): Mehlsack `signed_ops.py` and the S1 record `weighted_ops.py` hand the Core an inner params dict without
  `"influence"`; `SCALE_FORMULAS` moved into the Lab; the Mehlsack Scale comparison split into linear (against the thin
  class, positions and commands) and `"power"` (against `F ** w`). `probe_cost.py` runs.
- Tests: `tests/test_weighted_transforms.py` (T-2, T-5, T-6, T-7, T-8, tripwire (5) restated as "the Core reads
  `influence`, `pivot`, `symmetry` from params"), `tests/test_soft_selection_replay.py` + `tests/soft_replay.py` (T-3: the
  replay function was run green against the pre-SS1 ops, 42/42, before the Core was touched, then again after),
  `tests/test_soft_selection_ops.py` ported (T-4; flipped tripwire and dropped `"power"` tests named in its docstring).

**Ran** (container, `xvfb-run -a`, once at the end): `tests` 3017 passed, 51 skipped (GL tests without `libEGL` in the
container, plus the existing intentional skips of `test_symmetric_removal.py`), 0 failed; `experiments/symmetry_lab/tests`
454 passed, 4 skipped; `playground/tests` 1241 passed; `experiments/soft_selection/tests` 102 passed;
`experiments/mehlsack_lab/tests` 351 passed. The new gate files: `test_weighted_transforms.py` 76, `test_soft_selection_replay.py`
42, the ported `test_soft_selection_ops.py` 67. The GL rows still need a machine with EGL for a full count.

**Deviations and agent choices (`PROVISIONAL`):**

- The S1 record's suite had its own copy of the placeholder characterization
  (`experiments/soft_selection/tests/test_weighted_ops.py::test_core_placeholder_blend_is_not_path_independent`, it set
  `RotateOperation._weights`); §5.2 named only the `tests/` copy. The placeholder is gone, so the record's test now replays
  the blend formula locally (same evidence, no Core private).
- A weighted Rotate with falloff seam vertices also refuses a zero axis before accumulating (§4.4 lists axis change and
  non-finite angle): otherwise the refusal would come from the loop after `Θ` was already accumulated.
- The thin classes no longer range-check weights of *stale* IDs (they are dropped before the Core validates). Weights of
  valid IDs are refused exactly as before.
- Refusal order when several inputs are wrong: missing `influence` now wins over a missing pivot (the pivot check moved
  into the Core). Texts keep the matched words (`pivot`, `basis`, `weight`, `influenced vertex set`, `symmetry`); the
  pivot and key-set sentences were reworded for the Core.
- `params["influence"] = None` counts as absent (the same `get(...) is None` test the soft ops used).
- Names: `falloff_seam_vertex_ids`, `_weighted_position`, `_SoftBegin` stay `PROVISIONAL`. An op class without
  `_weighted_position` refuses `params["influence"]` at `begin()`.
- `tests/test_soft_selection_ops.py`'s AST scan list of Core privates gained the SS1 names, so tripwire (10) also covers
  the new state.

**Not done (as ordered):** SS2 (field function, O-1, R6-A/R6-C, D-2/D-3 tool side, lifting I-8, removing the backstop),
SS3, any tool, `Application`, binding or Lab gate change.

---

## Kurzfassung für Manu (Deutsch)

**Worum es geht.** Das ist der Bauplan für die eine Core-Änderung der symmetrischen Soft Selection (SS1). Gebaut wird
noch nichts. Die unabhängige Review hat ihn mit Änderungen angenommen; alle Änderungen sind eingearbeitet. **Als Nächstes
brauchst du nur noch zu sagen, ob SS1 gebaut werden soll.**

**Was sich ändert (für dich unsichtbar).** Die Gewichtung (Soft) zieht in den Core, an dieselbe Stelle, an der heute schon
die Spiegelung sitzt. Soft ohne Symmetrie bleibt bitgenau wie heute, normales W/E/R auch; Soft mit Symmetrie bleibt in der
App bis SS2 abgelehnt. Deine Entscheidung P-a (Mittelpunkte gleiten bei Soft in der Ebene) wird als eigene Punktgruppe
gebaut, damit die heutigen Regeln für *ausgewählte* Mittelpunkte unverändert bleiben. Beim Drehen müssen diese gleitenden
Mittelpunkte vom Startzustand aus gerechnet werden, sonst hinge das Ergebnis davon ab, wie schnell du die Maus bewegst.

**Was die Review korrigiert hat.** Der erste Plan hätte beim weichen Drehen ohne Symmetrie einen Achsenwechsel neu
verboten (heutiges Verhalten geändert) — jetzt nur noch, wenn gleitende Mittelpunkte beteiligt sind. Zwei Lab-Stellen, die
sonst rot geworden wären, sind jetzt eingeplant. Und meine Aussage zum Beispiel-Mesh war verdreht: Das Mesh überkreuzt sich
schon vorher, und gerade die Regel „nach dem nächsten Auswahlpunkt" entwirrt es.

**Dein R-6-Punkt.** Für SS1 ändert er nichts am Code (der Core bekommt nur fertige Gewichte); verbindlich ist, dass alles
auch auf solchen Meshes exakt spiegelt — zwei Beispiel-Meshes werden Pflichttests. Offen für SS2, auf einem Fall, den kein
heutiges Asset hat: Soll bei einer Kante, die die Mitte ohne Punkt darauf kreuzt, deine Seite genau wie normales Soft
wirken und die Abweichung auf der gespiegelten Seite liegen — oder umgekehrt? Und welche Seite welche Bewegung bekommt.
Daraus wird in SS2 vielleicht eine Frage an dich.

**Fragen an dich jetzt:** keine — nur das Go für SS1.

**SS1 gebaut (2026-10-14).** Die Gewichtung sitzt jetzt im Core, an derselben Stelle wie die Spiegelung. Für dich ändert
sich nichts Sichtbares: W/E/R ohne Soft sind byte-genau wie vorher, Soft ohne Symmetrie bitgenau wie vorher (das prüft
ein eigener Test gegen eine Kopie der alten Rechnung), Soft mit Symmetrie bleibt in der App abgelehnt bis SS2. Neu und
getestet, aber noch von keinem Werkzeug benutzt: gewichtete Schritte für beide Seiten zugleich, exakt gespiegelt, auch
auf den beiden Sonder-Meshes aus deinem R-6-Punkt; Mittelpunkte, die nur der Falloff erreicht, gleiten in der Ebene und
hängen beim Drehen nicht davon ab, wie schnell du die Maus bewegst. Kleine Abweichungen vom Plan stehen in der
Implementierungsnotiz; keine Frage an dich. Als Nächstes: SS2 (symmetrisches Feld und Geste in der App).
