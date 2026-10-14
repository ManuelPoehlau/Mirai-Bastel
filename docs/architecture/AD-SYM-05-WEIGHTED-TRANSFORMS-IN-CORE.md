# AD-SYM-05 — Weighted transforms in the Core (symmetric Soft Selection, slice SS1)

**Status:** **PROPOSED** (2026-10-14). Design note before code for the one Core change of symmetric Soft
([AD-SYM-04](AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md) §5.2 SS1, review item R-5; [CORE_V1_FREEZE](CORE_V1_FREEZE.md) §7).
A Core change is a Haltepunkt (Development System §5): **independent review in a fresh session next, then Manu's go
for the code.** Nothing here is built.
**Mode (M5):** Type C (Architecture Gate). Documents only: no change under `src/`, `tests/`, `experiments/` or `playground/`.
**Read at:** `c2bc3e3` (branch `claude/festive-allen-pyajvv`, SS0 committed). Line numbers refer to that commit.
**Basis (binding, only linked):** AD-SYM-04 (Decision record: Q-4 = **P-a**; §4 C-1…C-7 and R-1…R-5; §5.1 D-1…D-5; the
[SS0 note](AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md#implementation-note-2026-10-14-slice-ss0)), [AD-020](AD-020-SOFT-SELECTION-APP-PATH.md)
("Promotion decision", §3 Q2, §8, §13 F3/F4), [AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md) (§2.2, §2.4, §3),
[AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md), [AD-014](AD-014_Core-Change-Basis-Parameter-for-ScaleOperation.md)
(precedent: Core change with a byte-identical old path), `src/core/operation.py` (AD-003 incremental contract).

**Evidence tags** as in AD-SYM-04: **[Code]** read at `c2bc3e3` (file:line), **[Doc]**, **[Probe]** (SS0 or a scratch
computation named in place), **(Reading)** a derivation, `PROVISIONAL` for every agent-set choice.

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
| RQ-1 | The per-vertex weighting lives in the Core loop with today's soft semantics: Move `w·Δ`, Rotate `w·θ`, Scale `1 + w(F − 1)` evaluated absolutely for `w < 1`. **Non-symmetric Soft stays bitwise identical** to the Q2-D ops of today. |
| RQ-2 | **Without weights, every gesture is byte-identical to today** — plain and symmetric Move/Rotate/Scale, incl. both seam checks, the per-side pivot and the refusal texts (AD-SYM-04 R-1, R-4). |
| RQ-3 | **Weights and symmetry in one operation instance** (AD-SYM-02 §3.1): plain step, conjugate step, projected step, each scaled by the vertex's weight; for pair-consistent input the result is an exact mirror (bitwise under E1). |
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
   existing `params["symmetry"]`, the placeholder blend replaced, two accumulated totals. No change to `Mesh`, the
   `Operation` lifecycle, `OperationContext`, `HistoryStack`, `VertexTransformCommand`, any topology operation.
5. **Tests/contract.** §6.
6. **Change only after** the independent review of this note and Manu's go.

---

## 3. R-6 as a design requirement (IN-3)

### 3.1 What the counterexample shows

The SS0 quad `s(+0.5,0,0) → v'(−0.1,1,0) → v(+0.1,1,0) → a(−0.5,0,0)`, X axis, `valid`, four straddling edges, seed `s`
(partner `a`), geodesic. Plain field from `s`: `d(v') = |s − v'| = 1.166`, `d(v) = 1.166 + 0.2 = 1.366`. Union field over
`{s, a}`: `d(v) = |a − v| = 1.166`. [Probe, SS0 `probe_straddling_quad`]

*(Reading, general form.)* Let `M` be the mirror map on vertices and `f_S` the plain field of the seeds `S`. On every
mirror-symmetric edge graph `M` is an automorphism that preserves edge lengths bit for bit (mirrored coordinate
differences only change sign), so `f_{M(S)}(v) = f_S(M v)` and

> **union field `f_U(v) = max(f_S(v), f_S(M v))` — the symmetric weight of a pair is the larger plain weight of its two members.**

That holds with and without straddling edges (it explains why SS0 found the pairs equal on the quad too) and is the
pair-level statement D-1 needs. The SS0 half "equals each side's own field" means `f_S(M v) ≤ f_S(v)` for every own-side
`v`; reflecting a path at a vertex on the plane proves it when every crossing passes through such a vertex, and on the quad
it fails because `s` reaches `v'` across the plane faster than `v`.

**Consequence.** Where `f_S(v) ≠ f_S(M v)`, the plain field itself is not mirror-symmetric, so **any** exactly symmetric
weighting must differ from plain Soft at `v` or at `M v`. "Own side equals plain Soft" and "exact mirror" cannot both hold
on such a mesh; no better field fixes it, only a refusal would.

### 3.2 Options

| | Option | Cost |
|---|---|---|
| **R6-A** | **Pair-level contract, promise dropped.** D-1 = the union field (one weight per pair by construction); "equals the own side's plain field" becomes an observed property of meshes without straddling edges (all current assets with pairs, SS0), pinned as a regression check there, not promised. | On a straddling mesh a few own-side vertices near the plane get a larger weight than plain Soft would give (the quad: `v` from 1.366 to 1.166 distance). Visible in the bands (D-5, SS3). |
| R6-B | Keep the promise, check visibly: refuse geodesic symmetric Soft when the falloff contains a straddling edge. | Refuses `valid` meshes for a property the Artist cannot see; an O(E) check per gesture start and per preview; Euclidean never needs it, so the two metrics behave differently under symmetry. |
| R6-C | Force each pair to the own-side value (`min` instead of `max`). | Undefined when seeds lie on both sides; on the quad `v'`, which `s` reaches directly, would move less than plain Soft moves it — the deviation only moves to the other member. |

**Proposal (`PROVISIONAL`): R6-A.** It is the only option that keeps every guarantee on every mirror-symmetric mesh and refuses
nothing that is `valid`. Binding consequences:

- **R6-1** Every guarantee of SS1 and SS2 (exact mirror, bitwise under E1; seam vertices exactly on the plane; completeness
  unchanged; one Undo step; cancel exact) holds on the straddling quad. The quad becomes a fixture of the SS1 Core
  contract tests (§6 T-8) and of the SS2 gesture tests.
- **R6-2** D-1 is restated at pair level (wording below, to be written into AD-SYM-04 §5.1 when this note is accepted).
- **R6-3** The Core never relies on graph symmetry. It receives weights and categories; **pair consistency is a caller
  precondition** (§4.3), and SS2 builds it by construction.
- **R6-4** The step category of a falloff vertex (plain or conjugate) must not come from "which seed is nearest" (§3.3).

**D-1 at pair level (proposed wording):** *"The symmetric field is the union field over seeds ∪ mirrored seeds (nearest
seed, `min` distance, never a sum). Each mirror pair carries one weight, the larger of its two field values; a seam vertex
carries one weight. On a mirror-symmetric edge graph this equals, for every pair, the larger plain-Soft weight of its two
members. It equals each side's own plain field only where no edge path from a seed crosses the plane between two vertices
off it (every current asset case with pairs, SS0); that is an observation, not a promise."*

### 3.3 Finding: R-6 reaches the step category, not only the weight

The union field also tells which seed is nearest. On the quad `v'` (negative side) is nearest to the explicit seed `s`, and
`v` (positive side) to the mirrored seed `a`. Two pair-consistent ways to give falloff vertices their step:

| | Rule | Quad, Move with `Δ = +x` | Elsewhere |
|---|---|---|---|
| K-near | category of the nearest seed (explicit → plain, mirrored → conjugate) | `v'` moves +x, `v` moves −x: the two cross the plane, the quad folds into a bow tie | Matches "explicit selection wins" for a selection that covers both sides (everything plain). Pair-consistent only on symmetric graphs and with a tie rule. |
| K-side | category by side of the plane relative to the seeds | `v` moves +x, `v'` −x: the quad stretches | Always pair-consistent (partners lie on opposite sides). Undefined when explicit seeds lie on both sides. |

On every mesh without straddling edges and with seeds on one side the two rules agree (the reflection argument, ties
aside). **Not decided here (SS2, O-1 in §8);** recorded because R6-4 forbids K-near alone. *(Reading:)* K-side for seeds on
one side; seeds on both sides need their own rule, possibly an Artist question in SS2 (it is felt behaviour).

---

## 4. Design of the Core change (`PROVISIONAL` in names, binding in rules once reviewed)

### 4.1 Channel

`params["influence"]: Mapping[VertexId, float]`, the key the soft ops use today (AD-020 §3.1 A; the `params` channel of
AD-SYM-02 §2.2). Read by `VertexTransformOperation._on_begin` (`transform.py:223-237`):

- **absent → today:** `_weights = {vid: 1.0}` and nothing else changes (RQ-2);
- **present →** validated before anything is stored: keys exactly the op's vertex set, every value finite and in `(0, 1]`
  (else `ValueError`); `_weights` becomes that map. Stale IDs stay the caller's job (L10, §5.1), as the Core already raises
  for an unknown vertex today.
- `RotateOperation`/`ScaleOperation` with weights need `params["pivot"]` (else `ValueError`): the Core default would be the
  centroid of the *influenced* set (AD-020 E7).

### 4.2 The per-vertex step

The placeholder blend `pos + w·(T(pos) − pos)` (`transform.py:265-269`) is **deleted**: it is not path independent for
Rotate and Scale (AD-020 F7, S1 FINDINGS) and has no caller. Instead each concrete op weights its own parameter, then the
category applies. `w == 1.0` always takes today's arithmetic on the live position, operation for operation (RQ-1/RQ-2).

| Op | plain | conjugate (`mirrored_vertex_ids`) | selected seam (`seam_vertex_ids`) | **falloff seam (new, §4.3)** |
|---|---|---|---|---|
| Move | `pos + w·Δ` | `pos + mirror_vec(w·Δ)` | `pos + proj(Δ)` (today; seeds have `w = 1`) | `pos + proj(w·Δ)`, incremental (projection is linear) |
| Rotate | `R(pos, P, a, w·θ)` incremental | `M(R(M pos, P, a, w·θ))` incremental | today (both checks) | **`proj(R(start, P, a, w·Θ))`, absolute** |
| Scale | `w = 1`: `S(pos, F_step)`; `w < 1`: `S(start, 1 + w(F − 1))` absolute | `M(S(M ·, …))` of the same | today (both checks) | **`proj(S(start, 1 + w(F − 1)))`, absolute** |

`P` the fixed pivot, `a` the fixed axis, `Θ` and `F` the angle and the per-axis factor accumulated since `begin()`, `M` the
mirror (`mirror_point`, `transform.py:141-146`), `proj` the projection onto the plane.

- **Why falloff-seam Rotate is absolute.** Rotating and then projecting depends on how the drag is chunked into steps.
  Scratch computation (plane `x = 0`, pivot `(0.5, 0, 0)`, axis `y`, seam vertex `(0, 0, 1)`, `w = 0.5`, total 90°):
  one step gives `z = 1.061`, two steps `1.222`, sixty steps `1.387`. [Probe, scratch, not committed] The Rotate tool
  explicitly wants chunk independence (`rotate.py:131`, "unabhängig vom Event-Chunking"). Today the problem cannot occur:
  a seam vertex is only rotated about the normal through a pivot on the plane, where the projection removes rounding only.
- **Why the projected result is the symmetric one** *(Reading):* a seam vertex is its own mirror, and
  `proj(M x) = proj(x)`, so `proj(R(p))` equals the projection of the conjugate side's result — the vertex takes the
  average of both sides' intents and stays exactly on the plane (`x − x·1.0 = 0.0` for an axis normal).
- **Exactness of pairs.** For equal weights the partner's step is computed with the same inputs as its source's (today's
  `M ∘ T ∘ M` construction), so a pair stays a bitwise mirror under E1; Scale's absolute path uses the partner's start
  position, which is the exact mirror of its source's.

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
pairing and gets none (AD-SYM-01: correspondence is derived in `mirai`; AD-SYM-02 §3.3: no mirror-result structure); a
violation gives a non-mirrored result, which the completeness oracle of SS2 and of the F-a guard catches. *Rejected:* a Core
check by mirrored positions — it would re-derive correspondence inside the Core.

*Rejected alternative for P-a:* exempt seam vertices by weight (`w < 1`). A non-seed very close to a seed can round to
`w = 1.0`, so the seam rule would depend on a float, and a radius-0 gesture would have to be special-cased.

### 4.4 Accumulated state and the contract deviation (RQ-7)

Only when weights are present:

- **Scale** accumulates `F` per axis and fixes the basis for the gesture (as `SoftScaleOperation` does today,
  `ops.py:185-201`; AD-020 F6/L5). **Rotate** accumulates `Θ` and fixes the axis (no Production tool changes either
  mid-gesture, F6; needed now for the absolute seam path).
- **Order:** validate (basis/axis unchanged, factor finite, seam step check for `seam_vertex_ids`) → accumulate → loop.
  A refusal leaves positions and totals as they were (today's soft test
  `test_scale_basis_change_keeps_the_total_at_its_pre_refusal_value`).
- **Visible deviation:** `core/operation.py` and `transform.py` state that with `params["influence"]`, Scale evaluates
  `w < 1` vertices and Rotate/Scale evaluate falloff-seam vertices **absolutely from the `begin()` snapshot**; everything
  else stays incremental. The snapshot exists already (`_start_positions`, `transform.py:228-230`).
- Without weights nothing is accumulated and nothing is fixed: the plain Core keeps accepting a new basis or axis per update
  (FINDINGS L5/§5.7 untouched).

### 4.5 Not touched

`Mesh`, `Operation`, `OperationContext`, `HistoryStack`, `VertexTransformCommand`, `_on_commit`/`_on_cancel`, the
`description` mechanism, `rotation_keeps_plane`/`scale_keeps_plane`/`pivot_on_plane`, `SEAM_TOLERANCE`, every topology
operation. `supports_symmetry` stays `True` on the three Core ops (C-7 is met by the Core classes).

---

## 5. Migration in the same commit (RQ-6)

### 5.1 `src/mirai/soft_selection/ops.py`

| | Option | Cost |
|---|---|---|
| M-a | Delete the soft op classes; tools build the Core ops with `params["influence"]`. | Smallest code; every importer changes (tools, `__init__`, tests, the Mehlsack bit-identity tests); the op-level symmetry backstop (AD-020 §8.2) loses its home before SS2. |
| **M-b** | **Keep `SoftMove/Rotate/ScaleOperation` as thin subclasses of the Core `MoveOperation`/`RotateOperation`/`ScaleOperation`:** `description`, require `params["influence"]`, filter stale IDs (L10), and — until SS2 — refuse `params["symmetry"]` (`supports_symmetry = False`). **No arithmetic, no copy** (`_scale_about`, the tuple sum and the `_soft_` state go). | One extra thin layer; names, tools, Application and importers unchanged; SS2 then removes exactly the backstop. |

**Proposal (`PROVISIONAL`): M-b.** `scale_formula` and `"power"` leave `src` (only tests use them; S2c kept linear, IN-5);
the S1 record (`experiments/soft_selection/weighted_ops.py`) keeps `"power"`. Tools and `Application` do not change in SS1
(`_soft_show_op_weights` keeps reading `params["influence"]`, `application.py:1953`).

### 5.2 Consumers outside `src/` that the change reaches [Code]

| Consumer | What happens | Done in the SS1 commit |
|---|---|---|
| Mehlsack Lab, `signed_ops.py:92-95` | passes its own `params` — incl. `"influence"` with **negative** weights — into the Core `_on_begin`; the new validation would refuse them | its inner context drops `"influence"` (the Core then sees no weights and never blends: the Lab's own tripwire `test_base_never_blends_one_update_equals_the_closed_form` keeps holding) |
| Mehlsack Lab, `signed_ops.py:48` | imports `SCALE_FORMULAS` from `mirai.soft_selection.ops` | the constant moves into the Lab (signed weights are Lab-only, no promotion, M3) |
| Mehlsack Lab tests | compare against `SoftMoveOperation` bit for bit | unchanged under M-b |
| S1 record `weighted_ops.py` | subclasses the Core ops through private members and overrides `_on_update` wholesale; passes `(0, 1]` weights | run `experiments/soft_selection/tests`; if a private it uses moved, the record gets a dated "superseded by AD-SYM-05" note instead of a repair (`PROVISIONAL`) |
| Playground, Symmetry Lab | reach the Core loop through the tools | no change; suites run (§6) |

### 5.3 AD-020 F3 tripwires (§13, eleven items)

(1) "base never blends" → **flips** into "the Core's weighted step equals the closed form" (and the placeholder test
`test_core_placeholder_blend_is_not_path_independent` goes with the placeholder); (2) `vertex_id=` and kwargs passed →
stays, now inside the Core; (3)/(4) the Scale and Move copies → **gone** (no copies), replaced by the reference oracle (§6
T-3); (5)/(6) base `_on_begin`/`_on_update` reads → stay as Core contract tests; (7) description → stays (M-b);
(8) `supports_symmetry` False → stays on the thin classes until SS2; (9) `pivot` → stays; (10) AST scan "no Core private" →
stays for the thin classes; (11) importability of `VertexTransformOperation` from `mirai` → no longer needed.
CORE_V1_FREEZE §7.1 gets its entry in the SS1 commit; the 2026-10-10 docs-only note there is marked superseded (dated).

---

## 6. Tests (the SS1 gate)

| # | Test | Oracle |
|---|---|---|
| T-1 | No weights → today | Every existing Core transform suite unchanged and green: `tests/test_transform_operations.py`, `test_symmetric_move.py`, `test_symmetric_transform.py`, `test_core.py` (AD-003 incremental) |
| T-2 | All weights `1.0` ≡ no weights | Bitwise, Move/Rotate/Scale, with and without `params["symmetry"]`, with and without a basis |
| T-3 | **Non-symmetric Soft bitwise identical to Q2-D** | A frozen copy of today's `ops.py` as a test-only reference oracle (same platform, so libm cannot differ; golden numbers would): the AD-020 P-D set — 3 ops × 2 metrics × radii {0, the 15 % step, 1.0} × 60 updates, with a tilted basis — positions after every update and the History command's maps |
| T-4 | Weighted semantics | The ported closed-form and path-independence tests of `tests/test_soft_selection_ops.py` against the Core ops |
| T-5 | Refusals before anything moves | Weights outside `(0, 1]`, non-finite, keys ≠ vertex set; weighted Rotate/Scale without pivot; basis or axis change mid-gesture (totals unchanged); `falloff_seam_vertex_ids` without weights or overlapping another category |
| T-6 | Symmetric + weighted exactness | `subd_cube` X and `head_basemesh` X, hand-built pair-consistent weights (no SS2 field code in SS1): after N updates every pair is a bitwise mirror, seam coordinates exactly `0.0`, `symmetry_state` still `valid`, one History entry, Undo/Redo and cancel exact |
| T-7 | P-a | Falloff seam only: Rotate about an axis not parallel to the normal with the pivot off the plane and non-uniform Scale run, stay on the plane, and 1 step vs 60 steps agree to rounding (absolute path). One selected seam vertex added: today's refusals, both checks, unchanged texts (R-4) |
| T-8 | **R-6 fixture** | The SS0 straddling quad with pair-consistent weights: T-6's oracle holds (R6-1) |
| T-9 | Mehlsack | Its tripwire and bit-identity tests green after the `"influence"` strip |

**Suites** (AGENTS §8a, a `src/core` change): `tests` fully; `experiments/symmetry_lab/tests` and `playground/tests`
(both reach the Core loop through the tools); `experiments/soft_selection/tests` and `experiments/mehlsack_lab/tests`
(direct consumers, §5.2) — once each at the end, with `xvfb-run -a`.

---

## 7. Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | Regression in every Move/Rotate/Scale gesture | The no-weights path is the old code path (§4.1); T-1, T-2; the per-vertex cost for `w = 1` is today's (one dict read and one compare already run, `transform.py:265-266`) |
| R-2 | Double weighting | One commit; M-b removes all soft arithmetic; Mehlsack strips the key (§5.2); tripwire (1) flips on purpose |
| R-3 | Contract deviation in the Core | §4.4, written into `operation.py` |
| R-4 | Artist-verdicted `w = 1` behaviour | Seam checks keep their scope (§4.3); the per-side pivot is a tool function, untouched |
| R-5 | Process | This note → fresh-session review → Manu's go → SS1 |
| R-6′ | The absolute Rotate path is new behaviour | Reachable only with `falloff_seam_vertex_ids`, i.e. only after SS2 |

---

## 8. Carried to SS2/SS3 (not decided here)

- **O-1 Step category** of falloff vertices (§3.3): K-side for seeds on one side; a rule for explicit seeds on both
  sides (possibly an Artist question).
- **The field function:** union field or "pair max of the plain field" (§3.1, equal on symmetric graphs, the second needs one
  field instead of one over doubled seeds); one weight per pair by construction; ambiguous vertices inside the falloff.
- **D-2** refusals (seed without partner).
- **D-3, tool side:** classify falloff seam vertices into the new key. With a *selected* seam vertex, the soft path must use
  `symmetric_default_pivot` (`selection_helpers.py:90-115`) like plain symmetric R/S: today the soft branch sets
  `primary_pivot` first and skips it (`tools/transform.py:363-385`), which would turn the per-side fallback (R-4, KEEP)
  into a refusal.
- **Cost:** the pairing dominates the gesture start (SS0 §4) and would repeat on every preview refresh; reuse per mesh
  version versus AR-1/INV-3 is SS2's design question; the reference-PC run of the SS0 probe is still open.
- Lifting I-8 (`application.py:1725-1728`, `:1787-1797`) and the M-b backstop together; bands on both sides (SS3, D-5).

---

## 9. Questions

**Artist:** none for SS1 (no visible change, RQ-8; P-a and R-6 are decided). O-1 may become one in SS2.

**For the independent review (fresh session):** (1) Is §3.1's pair-level statement right, and does R6-A keep every
guarantee? (2) Is a new category (§4.3) the smallest correct form of P-a, or should the checks change instead? (3) Is
the absolute falloff-seam Rotate needed and correctly specified (§4.2)? (4) Is the no-weights path really byte-identical
(§4.1, T-1/T-2)? (5) M-a or M-b? (6) Is any consumer of the Core loop missing from §5.2?

---

## 10. Review

Pending (fresh session, archived unedited under `docs/archive/symmetry_lab/reviews/`).

---

## Kurzfassung für Manu (Deutsch)

**Worum es geht.** Das ist der Bauplan für die eine Core-Änderung der symmetrischen Soft Selection (SS1). Gebaut wird
noch nichts: Erst prüft eine frische Session den Plan unabhängig, dann gibst du das Bauen frei.

**Was sich ändert (für dich unsichtbar).** Die Gewichtung (Soft) zieht in den Core, an dieselbe Stelle, an der heute schon
die Spiegelung sitzt. Soft ohne Symmetrie bleibt bitgenau wie heute, normales W/E/R auch; Soft mit Symmetrie bleibt in der
App bis SS2 abgelehnt. Deine Entscheidung P-a (Mittelpunkte gleiten bei Soft in der Ebene) wird als eigene Punktgruppe
gebaut, damit die heutigen Regeln für *ausgewählte* Mittelpunkte unverändert bleiben. Beim Drehen müssen diese gleitenden
Mittelpunkte vom Startzustand aus gerechnet werden, sonst hinge das Ergebnis davon ab, wie schnell du die Maus bewegst.

**Dein R-6-Punkt als Anforderung.** Auf einem Mesh, bei dem eine Kante die Mitte kreuzt, ohne dass ein Punkt darauf liegt,
kann symmetrisches Soft nicht gleichzeitig exakt spiegeln *und* auf deiner Seite genau wie normales Soft wirken — das schließt
sich dort mathematisch aus. Vorschlag: exakt spiegeln hat Vorrang; nahe der Mitte kann der Einfluss dort etwas weiter reichen
als ohne Symmetrie. Auf keinem heutigen Asset kommt das vor; das kleine Beispiel-Mesh wird Pflichttest. Nebenbefund für SS2:
Welche Seite welche Bewegung bekommt, muss nach der Seite der Mitte gehen, nicht nach dem nächsten Auswahlpunkt — sonst
klappt das Beispiel-Mesh zu einer Schleife. Ob es dazu eine Frage an dich gibt, zeigt SS2.

**Fragen an dich:** keine.
