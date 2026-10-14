# Independent Review — AD-SYM-05 "Weighted transforms in the Core (symmetric Soft, slice SS1)" (PROPOSED)

> **Reviewer:** Claude (claude.ai/code, fresh session, no prior chat or plan context)
> **Review ID:** CLAUDE-001
> **Target path:** `docs/archive/symmetry_lab/reviews/AD-SYM-05_REVIEW_CLAUDE_001.md`
> **Repository state reviewed:** `claude/festive-allen-pyajvv` @ `4550327` (code read there; `git diff c2bc3e3 4550327 -- src tests experiments playground` is empty, so the note's line numbers at `c2bc3e3` apply)
> **Subject:** `docs/architecture/AD-SYM-05-WEIGHTED-TRANSFORMS-IN-CORE.md` (PROPOSED, 2026-10-14)
> **Type / Mode:** Type B (review only) · Architecture Gate (Core change, Haltepunkt) · no source, test, experiment, Playground file or AD edited
> **Status:** Archived first-pass review — preserved verbatim
>
> This document is intentionally preserved as the original independent review. Do not edit it to
> reflect later decisions. Answers to the findings belong in the AD's §10 "Review".

---

## What was read, what was run

**Read (whole or the cited parts):** AGENTS.md (incl. §8a), CLAUDE.md; AD-SYM-05 (whole); AD-SYM-04
(Decision record incl. Q-4 and the R-6 entry, §4, §5.1, §5.2, SS0 note, §9); AD-020 ("Promotion decision", §1
F5–F11, §3.2–§3.3, §8, §13 F3); AD-SYM-02 §2.2–§3; AD-SYM-01 via `src/mirai/symmetry_axis.py` (E1); CORE_V1_FREEZE
§1, §7, §7.1 (incl. the 2026-10-10 docs-only note). Code: `src/core/operations/transform.py`, `move.py`,
`src/core/operation.py:1-80`, `src/mirai/soft_selection/ops.py`, `influence.py`,
`src/mirai/interaction/tools/{transform,move,rotate,selection_helpers}.py` (scale.py by grep only),
`src/mirai/application.py:1720-1955` (soft/symmetry branches), `experiments/mehlsack_lab/signed_ops.py` (whole) and its
tests by grep, `experiments/soft_selection/weighted_ops.py`, `probe_symmetric_field.py` (`straddling_quad`),
`probe_cost.py` (imports), `experiments/head_topology_walkthrough/wt.py:185-215`, `tests/test_soft_selection_ops.py`
(whole), `tests/test_symmetric_transform.py`/`test_symmetric_move.py` (fixtures).

**Consumer grep** (`VertexTransformOperation|MoveOperation|RotateOperation|ScaleOperation|_PivotTransformOperation`,
`"influence"`, `_weights`, `.total_factor`, `.scale_formula`, `.weights`, `SCALE_FORMULAS`, `supports_symmetry`) over
`src tests playground experiments` (without `tests/_archive`). Results in R-2, R-3, Q6.

**Run (headless, `xvfb-run -a`):**
- `pytest tests/test_soft_selection_ops.py tests/test_symmetric_transform.py tests/test_symmetric_move.py tests/test_transform_operations.py -q` → **123 passed, 16 subtests passed** (baseline before SS1).
- `pytest experiments/mehlsack_lab/tests/test_signed_rotate_scale.py experiments/mehlsack_lab/tests/test_signed_ops.py experiments/soft_selection/tests -q` → **180 passed**.
- Two throwaway scripts in the session scratchpad (not committed):
  - `ss1_check.py`: (a) the §4.2 chunking numbers; (b) float monotonicity of every curve in `CURVES`; (c) the §4.2
    table written out as plain functions over `rotate_around_axis`/`mirror_point`/`_project_to_plane`, driven by union
    weights (`compute_influence(seeds ∪ mirrored seeds)`), K-side categories, falloff seam vertices in the new category,
    60 random updates per op, on `straddling_quad`, `subd_cube` X and `head_basemesh` X, both metrics.
  - `quad_shape.py`: segment intersection of the SS0 quad before and after K-near / K-side.

Not run: `playground/tests`, `experiments/symmetry_lab/tests`, the whole `tests` tree (no code changed; the note's own
gate runs them).

---

## Verdict

**ACCEPT WITH CHANGES.** The core of the design is right and small: one channel already in use, one new category key,
the placeholder blend replaced, an absolute path exactly where chunk independence needs it, the seam checks left in their
scope. I re-derived §3.1 at distance level and the §4.2 table on the quad and two assets: every pair stays a bitwise mirror,
every falloff seam vertex lands on `x == 0.0`, and the 1/2/60-step numbers reproduce. The line numbers are all correct.

Two findings must be fixed **before code**, because the gate as written would go red or the stated invariant would be
false: **R-1** (fixing the rotation axis for every weighted Rotate changes non-symmetric Soft and breaks four existing
tests) and **R-2** (§5.2 misses consumers that break under M-b). R-3 and R-4 fix the M-b surface and the T-3 oracle. R-5 and
R-6 correct the R-6 analysis (§3.1, §3.3); they do not change SS1's code, because the Core is weight- and pairing-agnostic,
but R6-4 and the D-1 rewording (R6-2) should not be made binding on that evidence. The rest is minor.

---

## Findings

### R-1 (major) — fixing the axis for every weighted Rotate is a behaviour change of non-symmetric Soft

**Claim (§4.4):** with weights present, Rotate "accumulates `Θ` and fixes the axis"; RQ-1 says non-symmetric Soft stays
bitwise identical; T-1/T-4 say existing suites stay green.

**Evidence.** Today `SoftRotateOperation` accepts a new axis per update (`ops.py:138-147`); only Scale fixes its basis
(`ops.py:193-194`). The existing suite drives Soft Rotate with a changing axis: `ROTATE_STEPS`
(`tests/test_soft_selection_ops.py:91-92`, third step axis `(1,0,0)`) is used in
`test_radius_zero_is_bit_identical_to_core` (`:104`), `test_cancel_restores_exact_start` (`:305`),
`test_commit_one_entry_…` (`:322`) and `test_selection_unchanged_by_the_whole_gesture` (`:372`). Under §4.4 all four raise
at step 3. No tool changes the axis (`rotate.py` passes `self._axis` every update; AD-020 F6), so the app does not see it —
but the op contract does, and T-2 "all weights 1.0 ≡ no weights" would also differ for an axis change. `Θ` is consumed
only by the falloff-seam path (§4.2).

**Change.** Accumulate `Θ` and fix the axis **only when `falloff_seam_vertex_ids` is non-empty** (state it in §4.4, test
the refusal in T-5, keep `ROTATE_STEPS` as is). Scale's basis fixing with weights stays (it is today's SoftScale). While
there: when `Θ` is accumulated, refuse a non-finite `angle` before accumulation (one NaN step would otherwise poison every
later absolute evaluation, unlike the incremental vertices).

### R-2 (major) — §5.2 misses consumers that break under M-b and the new validation

1. **Mehlsack tests are not "unchanged under M-b".** `experiments/mehlsack_lab/tests/test_signed_rotate_scale.py:85-98`
   compares `SignedSoftScaleOperation` bit for bit against `SoftScaleOperation` **with `scale_formula` `"linear"` and
   `"power"`** and reads `op_b.total_factor` and `op_b.scale_formula`; `:80` compares against `SoftRotateOperation`. M-b
   removes `"power"` and (per "the `_soft_` state go") the accumulator that backs `total_factor`. → The `"power"` half needs
   another reference (the closed form `F ** w` it already tests at `:142-144`), the linear half needs the M-b accessors
   (R-3).
2. **The S1 record fails on the new key-set check, not on a moved private.** `weighted_ops.py:86-92` passes the
   caller's `params` (with stale IDs in `influence`) unchanged into the Core `_on_begin`;
   `experiments/soft_selection/tests/test_weighted_ops.py:399-404` puts a stale ID into the map → `ValueError` from the
   new validation (§4.1 "keys exactly the op's vertex set"). `probe_cost.py:50-55` runs on the same classes. A
   "superseded" note leaves a suite red that §6 lists. → Give the S1 record the same one-line change as Mehlsack (inner
   context without `"influence"`), so the record keeps running unchanged in arithmetic, and say so in §5.2.
3. `tests/test_soft_selection_ops.py`: the `"power"` parametrisations (`:149-170`, `:284-298`) go with `scale_formula`;
   T-4 should say which tests are dropped rather than "ported".

### R-3 (medium) — M-b's public surface is not specified

The thin classes must keep: `weights` (read by `tests/test_application_soft_selection.py:182-411`, nine sites),
`total_factor` (`tests/test_soft_selection_ops.py:528-533`, Mehlsack test above), `description`, the symmetry backstop.
But tripwire (10) stays (§5.3) and its scan forbids `_weights` and `_start_positions` in `src/mirai`
(`test_soft_selection_ops.py:541-565`), and §5.1 removes "the `_soft_` state". Also the thin class can no longer forward
`params` unchanged (today `ops.py:99-104`): with stale IDs the Core's key-set check would fire
(`test_stale_ids_*`, `:413`, `:450`).

**Change.** Write into §5.1 what M-b holds and what the Core exposes. Smallest: the thin class keeps its filtered map
(`_soft_weights` → `weights`) and passes a **new** params dict with the filtered `influence`; `total_factor` either becomes
a public read-only property of `ScaleOperation` (a Core API addition → list it in §2 step 4, §4 and T-5) or the two tests
that read it are rewritten. Either way, state it; "no state" and "no Core private" cannot both hold with `weights`.

### R-4 (medium) — the T-3 oracle is not independent of the change

A "frozen copy of today's `ops.py`" subclasses `VertexTransformOperation` and hands `params` with `"influence"` to the
Core `_on_begin` (`ops.py:99-105`), so after SS1 it runs the new validation (stale-ID cases raise) and the new base loop
(if the hook signature or loop changes, the oracle changes with it). It would test the new Core against itself.

**Change.** Make the oracle a pure replay function (start positions, weights, pivot, step list → positions after every
step, plus the start/end maps), a copy of today's arithmetic (`_scale_about`, `_triple`, the tuple sum, the
`angle if w == 1.0 else w * angle` call of the public `rotate_around_axis`), no Core base class. Run it on the AD-020 P-D
set **and** on the existing step lists (`MOVE_STEPS`, `ROTATE_STEPS`, `SCALE_STEPS`, `SCALE_BASIS_STEPS`), radii {0, 15 %
step, 1.0}. Same-platform argument against golden numbers: agreed.

### R-5 (medium) — §3.3's geometry is inverted; R6-4 rests on it

The SS0 quad `s(+0.5,0) → v'(−0.1,1) → v(+0.1,1) → a(−0.5,0)` is **already self-intersecting**: edge `s–v'` crosses edge
`v–a` at `t = 5/6, u = 1/6` (`quad_shape.py`). Move `+x 0.5`, `w = 0.6`:

| | `v'` | `v` | crossing of `s–v'` and `v–a` |
|---|---|---|---|
| start | −0.1 | +0.1 | **yes** |
| K-near (`v'` plain, `v` conjugate) | +0.2 | −0.2 | **none** — the face untangles |
| K-side (`v` plain, `v'` conjugate) | −0.4 | +0.4 | **yes**, larger |

So "K-near folds into a bow tie, K-side stretches" is the wrong way round on this fixture: K-near moves each vertex with
the seed it is connected to. The real trade-off is: K-side is pair-consistent without a tie rule (ties
`d_S(v) = d_S(Mv)` occur whenever the shortest path runs through the seam); K-near follows connectivity on straddling
meshes but needs a tie rule. **Change:** correct the §3.3 table and drop R6-4 as a binding consequence; leave O-1 fully
open for SS2. If Manu should feel it, it is one SS2 question together with O-1 (Artist question, not decided here); no
current asset has straddling edges with pairs (SS0 §2).

### R-6 (medium) — §3.1's "Consequence" and the R6-C row are inaccurate

"'Own side equals plain Soft' and 'exact mirror' cannot both hold on such a mesh" is false for seeds on one side: the rule
**w(pair) := f_S(member on the seeds' side)** keeps the own side exactly plain (`v`: f(1.366), as plain Soft) and the
mirror exact; only the mirrored member `v'` deviates from what plain Soft would do there — and on the mirrored side the
step is the conjugate anyway. That rule is R6-C, but "`min` instead of `max`" mislabels it: on every mesh without
straddling edges the own-side value **is** the max (SS0 §1); it is the min only where R-6 bites. Its real costs: undefined
for seeds on both sides (the same domain where K-side/O-1 is undefined), needs a side classification, and unpaired vertices
on the other side need a rule (D-2) — R6-A's union field gives them a value directly. So R6-A remains defensible, but "the
only option that keeps every guarantee" is not the reason.

**Change.** Fix the sentence and the R6-C row. Since the Core receives weights only (R6-3), the choice does not affect SS1:
keep R6-1 and R6-3 for SS1, move R6-2 (rewriting D-1 in AD-SYM-04 §5.1) to SS2 with the field function (§8 already lists
it).

### R-7 (minor) — the weight on `seam_vertex_ids` is assumed, not enforced

§4.2's selected-seam column is "today (seeds have `w = 1`)". Move's row `pos + proj(Δ)` would silently ignore a `w < 1`
passed for a selected seam vertex; Rotate/Scale are unspecified for it. **Change:** with weights present, `begin()` refuses
(`ValueError`) any `seam_vertex_ids` member whose weight is not exactly `1.0`; add to T-5. Cheap, needs no pairing
(consistent with R6-3), and makes "seeds have `w = 1`" a checked invariant.

### R-8 (minor) — §3.1 states a bitwise identity on weights that holds on distances

`max(f_S(v), f_S(Mv)) == f_U(v)` needs the curve to be monotone **in floating point**; `smooth` (`t·t·(3 − 2t)`,
`influence.py:39-41`) is not: 2688 of 200 000 sampled adjacent-float pairs give `f(t⁺) < f(t)` (`ss1_check.py` (b); the
other five curves 0). Where `d_S(v) ≠ d_S(Mv)` (straddling meshes, seeds on both sides), "pair max of the plain field"
and the union field can then differ in the last bit. What does hold bitwise, for both metrics under E1: **distances**,
`d_U(v) = min(d_S(v), d_S(Mv))` — edge lengths and point distances are mirror-invariant bit for bit, Dijkstra's value is
the minimum over paths of left-fold float sums (independent of heap order, since float addition is monotone) and the
pruning at `r` is a path property too. **Change:** state §3.1 on distances and define the pair weight as
`curve(min distance)` (= the union field); in §8, the "pair max" variant should take the min of the two distances, not
the max of two weights. (Edge case, same finding: the Euclidean bounding-box prefilter, `influence.py:100-108`, is per seed
set, so the two variants can also differ for a vertex at `d ≈ r` by rounding; pair consistency of each variant is not
affected.)

### R-9 (minor) — tripwire mapping (§5.3) needs three corrections

- (5) "base `_on_begin` reads target/selection.vertices/pivot only" does not "stay": after SS1 it also reads and validates
  `params["influence"]`. Restate it as the new Core contract test.
- (10) in AD-020 is "own attribute names carry the `_soft_` prefix → AST scan"; under M-b it depends on R-3.
- (11) is the importability of `VertexTransformOperation` from **`core.operations.transform`** (not "from `mirai`"); it is
  still relied on by `mehlsack_lab/signed_ops.py:47` and `soft_selection/weighted_ops.py`, so it is not "no longer needed",
  only no longer needed by `src/mirai`.

### R-10 (minor) — §8 D-3: name the fallback set for SS2

`symmetric_default_pivot(mesh, selected, affected, symmetry)` falls back to the centroid of `affected`
(`selection_helpers.py:109-114`). In the soft branch, `vertex_ids` is already the influenced set
(`tools/transform.py:380`), so calling it the way the plain branch does (`:384-386`) would put the fallback pivot at the
centroid of the influenced set — radius-dependent — instead of today's pair midpoint (R-4 of AD-SYM-04, KEEP). SS2 must
pass seeds ∪ their partners. Nothing of this is needed in SS1: the app refuses Soft + symmetry
(`application.py:1725-1728`, `:1787-1797`), the tools do not change, and the Core's pivot check is already keyed on
`seam_vertex_ids` only (`transform.py:338-341`).

### R-11 (minor) — the R6-1 fixture does not exercise P-a

`straddling_quad` has no vertex on the plane, so T-8's "seam coordinates exactly `0.0`" is vacuous there. **Change:** add a
second straddling fixture with a seam vertex inside the falloff (e.g. the quad plus one vertex on the plane connected to
`v` and `v'`), so P-a and R-6 are tested together.

### R-12 (nit) — refusal texts and references

- Ported tests match case-sensitively on `"pivot"`, `"basis"`, `"weight"`, `"influenced vertex set"`
  (`test_soft_selection_ops.py:234`, `:278`, `:426`, `:471`, `:529`); the Core's texts are German ("Pivot", "Basis"). Either
  the weighted refusals keep these words or the test changes are listed.
- `_triple` (`ops.py:218-227`) = `_as_triple` (`transform.py:79-95`) + a finiteness check; §4.4 keeps the check for the
  weighted path — correct, keep it.
- RQ-3 cites "AD-SYM-02 §3.1", §4.3 "§3.3": AD-SYM-02 §3 is a numbered list (points 1 and 3).
- AD-SYM-04 §5.1 D-3 still says P-a exempts seam vertices "(`w < 1`)"; §4.3 rightly rejects classification by weight.
  Align D-3's wording when AD-SYM-05 is accepted.
- R-1 in §7 ("per-vertex cost for `w = 1` is today's"): under M-b the soft ops run through
  `_PivotTransformOperation._transform_position`/Move's category tests (two or three extra `frozenset` lookups per vertex
  per update), and every symmetric gesture gains the new category test. Negligible against the 8 ms bar, but not "today's";
  the `soft_w` drag row (AD-SYM-04 D-4) is the measurement if needed.

---

## Answers to §9's six questions

1. **§3.1 / R6-A.** At pair level the statement holds for both metrics on every mirror-symmetric edge graph under E1,
   **bitwise on distances** (R-8 for the weight form). R6-A keeps every guarantee on the quad: `ss1_check.py` (c) — Move,
   Rotate, Scale, 60 updates, both metrics — pairs bitwise mirrored, no vertex unpaired afterwards; the same on
   `subd_cube` X (8/7 falloff seam vertices) and `head_basemesh` X (5/4), falloff seam `x == 0.0` exactly. One Undo and exact
   cancel follow from the unchanged `_on_commit`/`_on_cancel` (§4.5). R6-B is fairly costed; **R6-C is not** (R-6). **§3.3
   is inverted** (R-5).
2. **§4.3.** A new category is the smallest correct form: the checks cannot be narrowed without "is it selected?" knowledge,
   and weight-based exemption is fragile (agreed with the note's argument). R6-3 ("caller precondition, not checked") is
   consistent with today's contract — the Core already trusts `mirrored_vertex_ids`/`seam_vertex_ids` unchecked
   (`move.py:99-100`, `transform.py:334-335`). Add the cheap check of R-7.
3. **§4.2 absolute falloff-seam Rotate/Scale.** Needed: reproduced 1.061 / 1.222 / 1.387 for 1 / 2 / 60 steps; the absolute
   form gives 1.061 for any chunking. Falloff-seam Scale must also be absolute at `w = 1` (rotated basis + projection do not
   commute), which the table does. Order validate → accumulate → loop is right; the axis fix must be scoped (R-1). The
   projection is the symmetric result: for a seam vertex `Mp = p`, so the conjugate intent is `M(R(p))`, and
   `proj(R(p))` is the midpoint of `R(p)` and `M(R(p))`; under E1 it lands on `x == 0.0` exactly.
4. **Byte identity.** Without weights the design is byte-identical, symmetric included (seam checks and per-side pivot
   untouched; `w == 1` paths reuse today's expressions; `1.0 · x == x`). Non-symmetric Soft: `_scale_about` matches
   `ScaleOperation._apply` operation for operation (`_dot` order, `_scale` products, `(x + y) + z`, pivot add); `_triple`
   matches `_as_triple` plus the finiteness refusal; Move's tuple sum and Rotate's `w · angle` match. **Exception: R-1.**
   The T-3 oracle as described is not independent (R-4).
5. **M-a or M-b.** M-b — it keeps names, the `type(op) is Soft…Operation` assertions (`test_application_soft_selection.py`),
   `description` and the backstop until SS2. Moving `scale_formula`/`"power"` out of `src` is right (no app path uses it;
   S2c kept linear; the Core should not carry a formula switch), but R-2 (1) and R-3 must be written in.
6. **Missing consumers.** Yes: the Mehlsack Scale/Rotate comparison test incl. `"power"`, `total_factor`, `scale_formula`;
   the S1 record's stale-ID path and `probe_cost.py`; `weights`/`total_factor` readers in `tests/` (R-2, R-3). Checked and
   unaffected: `experiments/symmetry_lab/lab_app.py` (reads `supports_symmetry` of the Core classes only),
   `experiments/head_topology_walkthrough/wt.py` (plain `MoveOperation`, no weights), `experiments/mirai_bastel_core_V1`
   (own copy), Playground (no direct op construction), `tests/test_application_soft_bands.py` (reads the outer
   `context.params["influence"]`, unchanged under M-b). The §6 suite selection matches AGENTS §8a for a `src/core` change.

**Further checks asked for:**
- **RQ-8** holds once R-1 is scoped: the app refuses Soft + symmetry at arm and begin, the thin classes keep the
  backstop, the soft history descriptions stay, and the remaining differences (refusal texts, `"power"`) are not reachable
  from the app.
- **Tripwire mapping §5.3:** right except (5), (10), (11) (R-9).
- **SS2/SS3 deferrals (§8):** correctly SS2; nothing has to move into SS1 (R-10 names the detail SS2 needs).
- **Line numbers:** all checked citations match (`transform.py:79-95, 141-146, 223-237, 228-230, 265-269, 298-366,
  338-346, 382-387, 411-416`; `move.py:35-45, 103-110`; `operation.py:15-25`; `ops.py:185-201`;
  `tools/transform.py:363-385, 398-410`; `rotate.py:131`; `selection_helpers.py:90-115`; `application.py:1725-1728,
  1787-1797, 1953`; `signed_ops.py:48, 92-95`).

---

## Confirmed without change

- §2 freeze steps 1–4: the mirror logic has one home in the Core; the seam checks to narrow sit there; no change to
  `Mesh`, `Operation`, `OperationContext`, `HistoryStack`, `VertexTransformCommand`, topology ops.
- §4.1 channel and validation (`(0, 1]` and finite equals today's `0.0 < w <= 1.0`; NaN and ∞ fail), pivot required for
  weighted Rotate/Scale (E7).
- §4.2 table (with R-1 and R-7), including pair exactness via `M ∘ T ∘ M` with equal inputs and Scale's absolute path from
  the partner's mirrored start.
- §4.3 disjointness rules; the tool arm refusal `_refuse_if_seam_unsafe` needs no change because it reads
  `seam_vertex_ids` only.
- §4.4 visible deviation note in `operation.py` and `transform.py`; snapshot reuse (`_start_positions`).
- §5.2 Mehlsack strip of `"influence"` (negative weights) and moving `SCALE_FORMULAS` into the Lab.
- §6 suite scope; §7 R-2/R-4/R-5.

---

## Kurzfassung für Manu (Deutsch)

Der Bauplan stimmt im Kern und ist klein genug: Ich habe die Rechnung nachgebaut (Beispiel-Quad, Würfel, Kopf, beide
Distanzarten, Move/Rotate/Scale mit je 60 Schritten). Die Seiten bleiben bitgenau gespiegelt, die Mittelpunkte liegen exakt
auf der Ebene, und dass gleitende Mittelpunkte beim Drehen vom Startzustand aus gerechnet werden müssen, ist richtig. Zwei
Dinge müssen vor dem Bauen korrigiert werden: Erstens würde der Plan beim weichen Drehen ohne Symmetrie einen Achsenwechsel
neu ablehnen — das ändert heutiges Verhalten und macht vier bestehende Tests rot; die Achse darf nur festgelegt werden, wenn
gleitende Mittelpunkte beteiligt sind. Zweitens fehlen in der Liste der betroffenen Stellen ein Mehlsack-Test und der S1-Stand,
die sonst rot würden. Außerdem ist die Begründung beim Beispiel-Quad verdreht: Das Quad überkreuzt sich schon vorher, und
gerade die Regel „nach nächstem Auswahlpunkt" entwirrt es. Für SS1 ist das egal (der Core bekommt nur Gewichte), aber diese
Regel sollte deshalb nicht schon jetzt festgeschrieben werden. Eine mögliche Frage an dich gehört zu SS2: Wenn eine Kante die
Mitte ohne Punkt darauf kreuzt (kommt in keinem heutigen Asset vor), soll dann deine Seite genau wie normales Soft wirken und
die Abweichung auf der gespiegelten Seite liegen — oder umgekehrt? Urteil: annehmen mit Änderungen.
