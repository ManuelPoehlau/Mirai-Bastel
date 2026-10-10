# Independent Review — AD-020 "Soft Selection on the Production App Path" (PROPOSED)

> **Reviewer:** Claude (claude.ai/code, fresh session, no prior chat or plan context)
> **Review ID:** CLAUDE-001
> **Target path:** `docs/archive/soft_selection/reviews/AD-020_REVIEW_CLAUDE_001.md`
> **Repository state reviewed:** `main` @ `0f079bd` (merge of PR #33). Its tree equals `f0ad85d`, the
> commit the handoff names. Apart from the AD itself, its index line and the FINDINGS §5 pointers, it
> equals `f65d223`, the commit the AD was read at.
> **Subject:** `docs/architecture/AD-020-SOFT-SELECTION-APP-PATH.md` (PROPOSED, 2026-10-10)
> **Type / Mode:** Type B (independent review of a Type C architecture gate) · M5 review only · no source,
> test, binding, AD, FINDINGS or other doc edited
> **Status:** Archived first-pass review — preserved verbatim; answers belong in AD-020 §13
>
> This document is intentionally preserved as the original independent review. Do not edit it to
> reflect later decisions.

Evidence tags as in the AD: **VERIFIED (code)** = read at `0f079bd`, file:line; **VERIFIED (probe X)** =
a throwaway review probe, code and output in the appendix; **UNVERIFIED** = not checked here. Readings are
marked *(reading)*. Every number in this review is a **container number** (Linux, Intel Xeon @ 2.10 GHz,
4 logical cores, Python 3.13.16, Xvfb with Mesa llvmpipe; REFERENCE_HARDWARE.md §4). None of them is a
reference-PC result.

---

## What was read, what was run

**Read in full:** AD-020 incl. Appendices A and B. `experiments/soft_selection/` `FINDINGS.md`,
`README.md`, `influence.py`, `weighted_ops.py`, `probe_cost.py`, `tests/test_weighted_ops.py`,
`tests/_fixtures.py`. `CORE_V1_FREEZE.md` (all, incl. every §7.1 entry). `AD-014`. `AD-016`. `V1_CORE.md`
§6 and §13. `src/core/operation.py`, `operations/transform.py`, `operations/move.py`,
`operations/__init__.py`, `core/__init__.py`. `src/mirai/interaction/tools/*.py` (`transform.py`: the
`_resolve_space` normal branches and `TransformTool`), `tool_manager.py`, `bindings.py`, `commands.py`.
`src/mirai/pyglet_input.py`. `src/mirai/mesh_geometry.py:25-60`. `src/viewport/viewport.py`.
`experiments/symmetry_lab/lab_bindings.py`. `tools/Input_Mapping_Tool/artist_input_truth.json`.
`REFERENCE_HARDWARE.md`. The format precedent `AD-SYM-03_REVIEW_CLAUDE_001.md`.

**Read in part:**
- AD-013: Decision, Default Lifecycle, Capability Promotion, Shared Artist Language, Context Overrides,
  Artist Input Truth rules 1–7, A3–A5, I1–I8, addendum 2026-09-26, Addendum H2 (Problem through Review),
  Amendment G-2 incl. the implementation notes 3a, 3b, 3c, 4 and 7.
- AD-018 §7 (E15–E18, hotfix, B5a/B5b extensions). AD-019 §1–§2. AD-SYM-02 §1.
- `src/mirai/application.py`: `__init__`, `init_scene`, `frame_scene`, `dispatch_command`,
  `_set_selection_mode`, `_knife_key`, `KNIFE_MIRROR_VARIANT_KEY`, `interaction_owner`, `key_press`,
  `key_release`, `_transform_arm`, `_constrain`, `_transform_step`, `_active_transform_vertex_ids`,
  `_transform_end`, `_cancel`, `_undo_redo`, `_apply_undo_redo`, `apply_mesh_change`, `_set_status`,
  `_gate_refuses`.
- `src/mirai/interaction/input.py:203-219` (`command_for`). `src/main.py:60-215`.
- `src/viewport/overlay.py:60-97`, `gl_point_overlay.py:100-224`, `gl_render_store.py:55-260`,
  `render_mesh.py:60-90` and `:240-330`, `derived.py:280-307`.
- `experiments/symmetry_lab/lab_app.py`: `NON_OPERATION`, `TRANSFORM_OPERATIONS`, `block_row`,
  `assert_lab_keys_free`, `sync_gate`, `run_command`, `_cycle`, `lab_key_press`, `e5_warning_text`.
  `probe_drag_cost.py` (docstring and setup). `tests/test_app_lab_fail_closed.py:1-240`.
  `tests/_app_lab_support.py` (helpers).
- `WP-SYM-LAB-03_REBASE_PLAN.md` § A3 (`:397-465`). ROADMAP §7 line 495 (B5a).
- `tests/test_display_modes.py:325-335`, `tests/test_input_binding.py:107-113`.
- pyglet 2.1.16 source, as installed in the container: `window/win32/__init__.py:885-943`,
  `graphics/vertexdomain.py:95-106`, `graphics/vertexbuffer.py:270-325`.

**Not read:** AD-SYM-02 §2.2–§5; AD-019 beyond §2; V1_SPEC beyond the mode keys (`docs/V1_SPEC.md:53`);
`gl_line_overlay.py`, `gl_triangle_overlay.py`, `lab_overlays.py` beyond the class list; the remaining
Lab tests; the Playground. The AD's re-run at `eaf43a3` and its no-EGL count (2232 passed, 41 skipped) were
not repeated (**UNVERIFIED**).

**Run:**

- Setup: `pip install -r requirements-dev.txt` (pytest 9.1.1, pyglet 2.1.16), `apt-get install libegl1`.
- **Environment trap:** in this container the bare `pytest` on `PATH` is a uv-tool install without
  pyglet. It reports `tests` 2232 passed, 14 skipped and the Lab 452 passed, 9 skipped, with "pyglet not
  installed" skips. With `python -m pytest`, the interpreter that has pyglet:

  | Suite | Command | Result | AD §0.1 |
  |---|---|---|---|
  | Production | `xvfb-run -a python -m pytest tests` | **2320 passed, 6 skipped** (68 subtests) | 2320 / 6 ✓ |
  | Symmetry Lab | `xvfb-run -a python -m pytest experiments/symmetry_lab/tests` | **466 passed, 4 skipped** | 466 / 4 ✓ |
  | Soft Selection S1 | `python -m pytest experiments/soft_selection/tests` | **96 passed** | 96 ✓ |

- Review probes, throwaway, in the session scratchpad (none committed). Code and output are in the
  appendix:
  - **P-D**: AD Appendix A rebuilt (`d_ops.py`). D is compared with the S1 ops and with the Core ops, and
    its private-member use is scanned.
  - **P-D2**: D's edge cases.
  - **P-D3**: the S1 op suite run against D, with the AD's "one helper change".
  - **P-V**: AD Appendix B rebuilt (TraceStore).
  - **P-V2**: the same drag with the window's GL backend (`GLRenderStore` and the GL overlays in a
    hidden pyglet window).
  - **P-V3**: a `cProfile` of P-V and P-V2.
  - **P-V4**: P-V2 with a slice-only `GLRenderStore.update` (a monkeypatch, not a repo change).
  - **P-B**: the cost of a 4-band `GLPointOverlay` that is stale every frame.
  - **P-A**: when sticky transform settings are read, at arm or at the first motion.
  - **P-K**: the brief's key probe, run on a `git archive` export of `0f079bd`. It adds placeholder
    commands and default bindings for O, Up, Down, Shift+O and Ctrl+O, then runs the Lab suite without
    and with them in `NON_OPERATION`, plus the Production suite once.

---

## Verdict

**ACCEPT WITH CHANGES. Two blockers (F1, F2).**

The structure of the recommendation is right, and most of it holds up under checking:

- in the app, off by default (A);
- no Core change for S2, using the D subclasses;
- the tool computes the influence at `begin()`;
- banded points through `add_overlay`;
- a measurement gate before the practical test.

Every code fact I checked in §0.2 and §1 is correct or only imprecise (table below). P-D reproduces
exactly: 12/12 and 6/6 bitwise equal, and D uses no Core private state. The `NON_OPERATION` claim about
the Lab tests holds with and without the addition.

Two things are not ready:

- **F1 (BLOCKER), Q6:** the viewport-cost proxy and the proposed S2 probe both use `TraceStore`. They
  cannot see the dominant per-move cost of the real window. `GLRenderStore.update` re-copies the
  **whole** attribute buffer for every single moved vertex, which is O(moved × V) per move. On the body at
  30 % the step + sync is p50 **30.7 ms** with the GL store, against **2.1 ms** with TraceStore (P-V/P-V2,
  container). The 8–15 ms reading for the reference PC, and the German summary for Manu, are therefore
  too low by an order of magnitude *(reading)*. A ~5-line slice-only patch brings the row to p50 1.5 ms
  (P-V4). This is pre-existing Production behaviour, not caused by Soft Selection.
- **F2 (BLOCKER), E3:** the visible Soft + Symmetry refusal sits only at arm, but the soft settings are
  read at `begin()`, the first motion. The AD also allows the soft keys while W is held. So
  **W → O → move** reaches `begin()` with soft on under symmetry. The AD's own precedent shows the timing:
  X pressed after arm applies to that gesture (P-A). The result would be either an uncaught `ValueError`
  out of `pointer_motion`, or a silent one-sided soft gesture. Both are against E3 / INV-8.

| Q | Verdict | One line |
|---|---|---|
| Q1 Host | **agree with changes** | A is the right host; §2.3 overstates the 2026-10-08 statement as "the" AD-013 decision (F5); `NON_OPERATION` needs a table change, not only a note (F6); B is rejected against an influence hook, not the cheaper settings-only data hook (F8) |
| Q2 Core seam | **agree with changes** | D is the right S2 choice and verified bitwise, but "documented extension points" is overstated and its hidden dependencies are only partly named (F3); the promotion deferral has no owner, trigger or criteria (F4); D changes S1's stale-ID contract (F10) |
| Q3 Influence/state | **agree with changes** | Tool at `begin()`, `params["influence"]` and sticky state in `Application` are sound; the E3 refusal must move to where the settings are read (F2); one source for the world radius and an update contract for the overlay are missing (F9) |
| Q4 Visualization | **agree with changes** | Banded points via `add_overlay` are fine; split headless band data from the GL sink, reword the rejection of c, and consider face bands and bands-at-arm (F11) |
| Q5 Keys | **agree with changes** | Free in every context today (verified), but O was vacated on purpose by an Artist Truth change (B5a, "D statt O") and two Production tests pin it unbound (F7); five commands, not four; Ctrl+O vs. "Open" (F12) |
| Q6 Cost | **disagree as written** | Bar (whole move p95 ≤ 8 ms) and gate placement agreed; the proxy, the extrapolation and the probe design miss the dominant cost (F1) |

---

## Answers to the review questions

### R1 — Q2-D, the central new claim

**D is a real difference in kind from C for private *state*, and only a difference in degree for
coupling.**

- **What D does not do.** D reads and writes no Core private attribute and calls no Core private helper.
  The P-D AST scan of the rebuilt classes finds none of `_weights`, `_start_positions`, `_vertex_ids`,
  `_pivot`, `_mesh`, `_apply`, `_as_triple` (**VERIFIED, P-D §4**). C uses nine such rows (FINDINGS §4.1),
  including a wholesale `_on_update` override that bypasses the seam check.
- **What D still is.** D is inheritance coupling to the protected template-method hooks (`_on_begin`,
  `_on_update`, `_transform_position`) of a class the Core does not export.
  - `VertexTransformOperation` is in neither `core.__all__` nor `core.operations.__all__`
    (**VERIFIED, P-D §4**; `src/core/__init__.py:22-43`, `src/core/operations/__init__.py:5`).
  - Its own docstring says concrete transforms implement **"ausschließlich `_transform_position()`"**
    (`src/core/operations/transform.py:214-218`). D also overrides `_on_begin` and, for Scale,
    `_on_update`.
  - The super-call extension of those two hooks has precedent only inside the Core: `MoveOperation`
    (`move.py:91-101`) and `_PivotTransformOperation` (`transform.py:325-346`).
  - So "documented extension points" is true for `_transform_position` and the four `_on_*` hooks of
    `Operation` (`operation.py:82-85`). For extending `VertexTransformOperation._on_begin`/`_on_update`
    from outside it is a Core-internal precedent, not a documented contract (F3).

**Every hidden dependency D has** (the "named" column says whether AD §3.3 lists it):

| # | D relies on … | Evidence | Named in AD? |
|---|---|---|---|
| 1 | the base keeps `_weights` at `1.0`, so it never blends | `transform.py:227`, `:265-269` | yes |
| 2 | the base loop passes `vertex_id=` and forwards the update kwargs unchanged | `transform.py:264` | yes |
| 3 | a copy of `ScaleOperation._apply` and `_as_triple` (bit identity needs the same operation order) | `transform.py:79-95`, `:418-435` | yes |
| 4 | a copy of Move's tuple sum (`move.py:110`) for radius-0 bit identity | §3.1 mentions it; §3.3 says "one copied formula (Scale)" | partly |
| 5 | the base `_on_begin` reads only `context.target`, `context.selection.vertices` and `params.get("pivot")`, and snapshots before D's own snapshot | `transform.py:223-237` | no |
| 6 | the base `_on_update` iterates exactly `_vertex_ids` (the selection view = influence keys), passes the *live* position positionally, and writes the return value back unblended; DScale's `w < 1` path ignores that `pos` | `transform.py:261-270` | no |
| 7 | the base `_on_commit` compares end and start with `==` and labels the History entry with `self.description`; D must set `description`, or History reads "Transform Vertices" | `transform.py:221`, `:272-283` | no |
| 8 | `Operation.supports_symmetry` defaults to `False`, and D does not inherit from `_PivotTransformOperation` | `operation.py:88` | yes (§8.2) |
| 9 | the `pivot` property returns the `float()`-converted `params["pivot"]` | `transform.py:234-235`, `:252-255` | no |
| 10 | D's own underscore attributes (`_influence`, `_start`, `_total`, `_basis`, `_formula`, `_requires_pivot`) do not collide with future base attributes | P-D §4 | no |
| 11 | `VertexTransformOperation` stays importable from `core.operations.transform` | not exported (above) | as "module-public" |

**Edge cases** (all **VERIFIED, P-D2**, on the D rebuilt from Appendix A plus the refusals of §4.2):

- **Stale ID** in map and view: `KeyError` from the base `_on_begin` (`mesh.py:141`), not the S1 skip
  (L10) and not a `ValueError`. Stale ID in the map only: the key-set check refuses with `ValueError`.
  Unreachable on the app path, because the tool computes the map from valid seeds just before `begin()`.
  It does change S1's contract (F10).
- **Empty** map and view: Move begins, `commit()` returns `None`, nothing is pushed to History. Empty map
  for Rotate without a pivot: `ValueError` (pivot).
- **Missing map**, a weight of 1.5, NaN, view ≠ keys, `params["symmetry"]` present (even `None`): each a
  `ValueError` before anything moves. `supports_symmetry` is `False` on all three.
- **`commit()`**: Move with a zero delta → `None`, History untouched. Rotate with angle 0 → an entry, as
  in the Core (L6).
- **Cancel** is exact for all three ops, with no History entry.
- **Basis mismatch mid-gesture:** refused before anything moves, and the total stays at the
  pre-refusal value. Continuing with the right basis gives the same mesh as a run without the refused
  step. A malformed factor is refused before accumulation. This holds only if the elided body of
  `DScale._on_update` keeps the order "validate → accumulate → base loop" (Appendix A shows it as a
  comment only).
- **`space="normal"`:** unreachable from `Application`. `_CONSTRAINT_SPACES` maps only x/y/z/xy/xz/yz
  (`application.py:129-136`), and `application.py` contains no `"normal"`. Inside the tools the normal
  space gives one direction, axis or basis per gesture, fixed at `begin()` (`move.py:157-181`,
  `scale.py:106-137`). D receives the same kwargs shape, and DScale's one-basis check holds. The normal
  is derived from `scene.selection` (`move.py:172-178`, `scale.py:113-117`), which under E1 stays the
  seeds, so it is consistent.

### R2 — Deferring the Core change (Q2-A)

**Sound under CORE_V1_FREEZE §1 and §7, with one wording caveat and one gap.**

- **Why it holds.** §1 asks for "eine konkrete neue Anforderung, die zeigt, dass der bestehende
  V1-Vertrag nicht ausreicht". P-D shows the existing contract is enough for S2, bit for bit.
- **Wording caveat.** §7 step 2 says "mit den bestehenden **öffentlichen** APIs lösbar". D uses protected
  hooks of an unexported class. The honest claim is therefore "solvable without a Core change", which is
  what §1 needs, not "with public APIs" (F3).
- **The `_weights` placeholder is not a requirement.** Nothing in `src` sets it, and no test in `tests/`
  touches it (grep: only `transform.py:25`, `:227`, `:265`, plus the S1 experiment). A semantic defect in
  dead code has no consumer, so it does not satisfy §1.
- **It is a hazard, though.**
  - Three places present the placeholder as *the* seam: `transform.py:24-26`, AD-014 ("Soft-selection
    weighting unaffected (applied downstream of `_transform_position` …)") and CORE_V1_FREEZE §7.1
    (2026-09-24, "analogous to the existing `self._weights` soft-selection placeholder").
  - Under D, filling it would silently double-weight D (dependency 1).
  - *(reading)* That argues for a tripwire test in S2a, not for a Core change now.
- **"The promotion AD decides A vs D" has no owner, trigger, criteria or default.** As written it is a
  deferral, not a plan (F4).

### R3 — Q1-A governance

- **The 2026-10-08 statement is necessary but not sufficient as worded.**
  - AD-013 § Default Lifecycle: "Production/Core promotion requires an **explicit** Artist/Product
    decision".
  - The 2026-10-08 statement exists in the repo only as AD-020's second-hand quote. I found no primary
    record in ROADMAP, ATELIER or FINDINGS (grep).
  - Its wording ("validation in the Production viewport, not the Playground") is also met by an
    app-path Lab. The Symmetry Lab runs the same `Application` and `Viewport`.
  - AD-013's own precedent treats "behind a flag in `src/main.py`" as a promotion that needs the
    Artist's decision: H2 Alternative D, "Not used: promotion is the Artist's decision … I7"
    (`AD-013:476`).
  - The AD's decision list already asks Manu "Host: im Programm, aus per Default (A) — ja / anders?".
    That answer *is* the explicit decision. §2.3 should say so instead of calling the 2026-10-08
    statement "the explicit decision AD-013 asks for" (F5).
  - Precedent that this is allowed with such a decision: WP Delete/Dissolve went straight into the
    Production app on Artist decisions (CORE_V1_FREEZE §7.1, 2026-10-06).
- **`NON_OPERATION`: change the table, dated; a loose note is not enough.**
  - G-2 says "It contains **exactly**" (`AD-013:933`), and its "Not decided here" list keeps the
    classification of new commands open ("Whether `EdgeLoop`/`EdgeRing` count as non-operations (they
    fail closed until decided)").
  - So adding commands is a decision that changes a normative table.
  - It lifts no Limit of G and adds no writer (H2-R6), so it needs no second H2 review. It does need the
    table row itself changed in a dated amendment note decided with AD-020, so that "exactly" stays true
    (F6).
- **The rejection of Q1-B is partly unfair.**
  - The AD rejects B against an *influence* hook ("a host-computed influence cannot follow the hover
    target"). The cheaper G-style alternative is a **settings-only data field** that a second Lab writes
    and the tool reads at `begin()`, computing the influence itself. That one follows the hover target.
  - It still needs the soft ops in `src`, a second Lab and an AD-013 addendum review. So A stays cheaper
    and the conclusion holds, but the table should carry this row with the right reason (F8).

### R4 — Symmetry Lab effect

- **The AD's claim holds (VERIFIED, P-K).** With five placeholder commands bound in GLOBAL (O, Up, Down,
  Shift+O, Ctrl+O), the Lab suite gives:
  - without the `NON_OPERATION` addition: **476 passed, 4 skipped** — the 466 baseline plus 10 new
    T-FC1 parametrisations, five "refused visibly under BLOCK" and five "silent without symmetry", all
    green;
  - with the addition: **466 passed, 4 skipped**.
  - No Lab test needed an edit. T-R1a/T-R1b (the start-up assert) also pass: none of the inputs is
    Shift+S, M or Shift+B.
- **The "soft cannot be switched off under BLOCK" trap is real but escapable (VERIFIED, P-A §3).**
  - Without the addition, O under BLOCK is refused with the generic `BLOCK_NOT_ALLOWED_TEXT`
    ("Befehl nicht koordiniert"), which misleads for a setting.
  - Shift+B (MARK, gate `None`) lets O through. So does Shift+S cycling to off (`lab_app.py:587-601`),
    at the cost of an undo step.
  - The real reason for the addition is classification: a soft setting is state for the next gesture,
    like the constraint group. It is not the trap (F6).
- **The arm-time refusal (§8.1) is reachable and visible in MARK and BLOCK.**
  - Under BLOCK, W passes the gate: the Lab reads `supports_symmetry` from the *Core* classes
    (`lab_app.py:90-94`, `:312`), so Move is allowed (P-A §2 arms W under BLOCK).
  - Under MARK the gate is `None`.
  - **But it is bypassable (F2):** P-A shows a constraint pressed after arm applies to the armed
    gesture, and §6.1 allows the soft keys while W is held.
  - The MARK HUD would not warn about a resulting one-sided soft gesture either: `e5_warning_text` keys
    on `TRANSFORM_OPERATIONS`, i.e. the Core classes (`lab_app.py:735-737`).

### R5 — Q3 on the app path

- **The influenced set reaches `on_vertices_moved` and `_cancel`:** yes, provided the soft branch makes
  `MoveTool.moves` or `TransformTool.vertex_ids` return the influence keys. Both paths read
  `_active_transform_vertex_ids()` (`application.py:1603`, `:1606-1612`, `:1759-1762`). Commit needs no
  notification, since the positions were reported during the steps. **VERIFIED (code).**
- **The Move anchor stays a seed:** yes, if the soft branch keeps today's order. The anchor is taken
  from the passed `vertex_ids` (`move.py:125`) *before* `_vertex_ids` is replaced by the affected set
  (`move.py:211`). Seeds always carry `w = 1.0` (`influence.py`, `compute_influence`), so the anchor moves
  by the full delta and the screen→world mapping is the plain Move's. **VERIFIED (code).**
- **Tools are re-instantiated per activation:** yes (`tool_manager.py:75`). **VERIFIED (code).**
- **Preview and `begin()` influence cannot diverge:** true for the function, and the positions only
  change on notifying paths. Four caveats:
  - the world radius needs one source; "once per mesh state (on toggle and after topology changes)"
    ignores that gestures change the bounds too (F9);
  - the overlay needs a stated update contract: who pushes the weights, `dirty`, and no recomputation
    during a gesture (F9);
  - the preview can be one frame stale, because the overlay syncs in `viewport.sync()` while `begin()`
    runs in `pointer_motion` *(reading, cosmetic)*;
  - hover-armed gestures have no preview by design.
- **"Sticky like X/Y/Z" vs E2:** consistent, because settings are not influence and the influence is
  still computed at `begin()`. **But X/Y/Z timing means a change after arm and before the first motion
  applies to the armed gesture** (P-A §1, §2). That is what breaks §8.1 (F2).
- **Positions changing without a Viewport notification:** none new on the soft path. One pre-existing
  path: an exception inside an op's update loop (e.g. a malformed basis) leaves the already-moved
  vertices unreported, because `_transform_step` has no handler around `tool_manager.update`
  (`application.py:1599-1603`).

### R6 — Q4

- **The `add_overlay` + `GLPointOverlay` subclass wiring is consistent** with the H1 contract
  (`viewport.py:52-59`, `:162-166`) and with "Viewport stays passive": the Viewport only calls
  `sync`/`draw`.
  - For *Production* code, AD-018 §7 E16 is the closer precedent: "data is headless", and the GL class is
    a sink. The Symmetry Lab merges data and GL in one experiment class.
  - S2a would be easier to test if the band computation (weights → band → positions) were a headless
    object, with the GL subclass only as its sink (F11).
- **Rejecting the per-vertex colour attribute: right for S2, but the reasoning over-reaches.**
  - The engineering reasons hold: a layout and shader change on a pipeline slated for removal, and a
    driver that drops the attribute (`gl_render_store.py:213-219`).
  - The Artist REJECT was about selection, and the AD then asks Manu in S2c whether a tint reads
    differently for influence. He cannot judge that without seeing one.
  - A missed middle alternative: face bands through `GLTriangleOverlay`/`FlatColorLayers` (the B5b
    face-highlight precedent, AD-018 §7). That gives a surface read with no `RenderMesh` change (F11).
- **"No hover preview" is plausible on cost.**
  - The cited ~9.5 ms is the hover change on the body *with* symmetry and Lab overlays. The plan says it
    is mostly the app's own pick (`WP-SYM-LAB-03_REBASE_PLAN.md:458-466`).
  - A hover preview would add up to 2.2 ms of influence per hover change on the reference PC
    (FINDINGS R10).
  - A cheaper middle path is missed: compute and show the bands **at arm** for a hover-armed target, once
    per W press (F11).

### R7 — Q5 keys

| Input | GLOBAL | KNIFE (falls back to GLOBAL, `input.py:212`) | TOPOLOGY | Hard-coded in `Application` | Symmetry Lab (+ start-up assert) | Artist Input Truth | Adapter map |
|---|---|---|---|---|---|---|---|
| O | free | free; in a session `_knife_key` returns `False` (`:1016-1033`) | free | none | free; assert passes (P-K) | no entry — **but vacated on purpose: B5a "D statt O"** (F7) | `pyglet_input.py:57` |
| Up / Down | free | free | free | none | free | no entry | `:65` |
| Shift+O | free | free | free | none | free | no entry | modifiers `:87-98` |
| Ctrl+O | free | free | free | none | free | no entry; `application.load` intentionally unbound (rule 4) | as above |
| Ctrl+Shift+O | free | free | free | none | free | no entry | as above |

**VERIFIED (code, P-K):**

- GLOBAL `bindings.py:107-184`; KNIFE `:154-158`; TOPOLOGY `:180-182`.
- The only hard-coded key is V (`application.py:250`, `:1022-1024`).
- Lab: `lab_bindings.py:46-62`.
- Truth: all 77 entries listed.
- The Playground binds neither O nor the arrow keys (grep of `playground/`).
- P-K's Production run shows that two tests pin O as unbound: `test_display_modes.py:328-334` and
  `test_input_binding.py:107-113`, the latter commented "WP-06 B5a (E42): Artist Input Truth — D statt O".
  They are the only Production failures: 2318 passed, 2 failed (F7).

**Windows/pyglet:**

- Auto-repeat is suppressed on Win32: `on_key_press` is not dispatched for a repeat
  (`win32/__init__.py:916-943`). So Up/Down give one radius step per press, and holding does not step.
  **VERIFIED** in pyglet 2.1.16 source. The pyglet version on the reference PC is **UNVERIFIED** (the
  repo pins none).
- Ctrl and Shift come from `GetKeyState` and are mapped to `ctrl`/`shift` by the adapter; Caps/Num Lock
  are ignored (`pyglet_input.py:87-98`). **VERIFIED.**
- Arrows also emit `on_text_motion`, which `src/main.py` does not handle — harmless.
- Ctrl+Shift+O against the Windows input-language hotkey (Ctrl+Shift or Alt+Shift, when several layouts
  are installed): **UNVERIFIED**.
- O and the arrows sit in the same place on a German QWERTZ layout. **VERIFIED** (layout fact).

### R8 — Q6 cost

- **Is P-V a valid proxy? The idea is valid; the store is not.**
  - The viewport share does depend only on the moved set (and V), not on the weights.
  - With `TraceStore` the proxy omits the dominant term of the real window: `GLRenderStore.update` →
    `_patch_attribute` writes the **full** CPU buffer into the VertexList on every per-vertex update
    (`gl_render_store.py:166-183`, `:199-219`; `target[0:len(data)] = data` with `data = buf`).
  - On the body at 30 % that is 232 calls per move (112 positions + 120 normals) × 2784 floats.
  - `cProfile`: 2.84 s of 3.36 s for 100 moves in `_patch_attribute` (P-V3).

  | Row (container) | P-V TraceStore p50 / p95 | P-V2 GLRenderStore p50 / p95 | P-V4 slice-only p50 / p95 |
  |---|---|---|---|
  | head 5 %, 9 moved | 0.40 / 0.43 | 1.51 / 1.85 | 0.36 / 0.57 |
  | head 30 %, 68 moved | 0.74 / 1.00 | 7.80 / 16.03 | 1.73 / 1.95 |
  | body 5 %, 18 moved | 0.52 / 0.64 | 5.95 / 12.36 | 0.65 / 1.02 |
  | body 30 %, 112 moved | 2.07 / 2.24 | **30.66 / 58.95** | 1.53 / 2.26 |

  (Edges hidden; step + sync, ms; full tables in the appendix. P-V4's "today" column was a separate run
  and agrees with P-V2 within noise.)
- **The 3–5× extrapolation is defensible only for pure-Python work**, which is where FINDINGS R1 got it.
  It is moot here because the dominant term is missing.
  - *(reading, not measured)* Applied to P-V2 it would put the body 30 % row at roughly 90–150 ms per
    move on the reference PC.
  - Even body 5 %, an ordinary 18-vertex drag that exists today, would be at 18–30 ms.
- **The bar (whole move p95 ≤ 8 ms, stricter than A3) is right**: it is about half a 60-Hz frame and
  includes the app's own sync.
- **The gate placement (before S2c) is right.** But the probe must use the GL store. A hidden pyglet
  window works headless here, as the `tests/test_gl_*.py` files and P-V2 show. A decision on the store
  fix must come before S2c, otherwise S2c judges Soft Selection through a viewport defect.
- **The missed cheaper mitigation** is the slice-only patch (P-V4): write `data` at `offset` instead of
  the whole `buf`. Body 30 %: p50 28.7 → 1.5 ms, and the GPU copy equals the CPU copy.
- **Costs the probe will not see:**
  - the band layers' vertex-list rebuild on every draw: 0.19–0.23 ms p50 for 9–112 points in 4 bands
    (P-B, llvmpipe);
  - `GLLineOverlay`'s full rebuild with edges shown;
  - the GPU upload and draw on the 9800 GTX;
  - the one-off `mesh_center_and_radius` (named by the AD).

### R9 — Scope and brief

- **Quietly decided?** Mostly no, and the AD flags most choices.
  - The radius unit is a "test setting". Fine, but say that S2 then cannot answer the *unit* part of
    FINDINGS §5.4, only the steps (F13).
  - Band look and preview scope are PROVISIONAL and engineering, and flagged.
  - "Global sticky" scope for the settings is decided as engineering and flagged (§4.3).
  - Symmetry is kept to contact points.
- **Missing alternatives or rejected-alternative lines:**
  - Q1: the settings-only data hook B′ (F8).
  - Q4: face bands; bands at arm (F11).
  - Q5: Alt+O (F12).
  - Q6: a GL-inclusive probe (F1).
- **FINDINGS §5 pointers only point.** `git show f0ad85d -- experiments/soft_selection/FINDINGS.md` adds
  one intro paragraph ("The questions themselves stay recorded here unchanged") and ten "→ AD-020 §x"
  suffixes. No question is answered there.
- **DoD file set:** `git show --stat f0ad85d` touches exactly the AD, the index line and FINDINGS.
  **VERIFIED.**

### R10 — Facts

See "Code facts checked" below: 31 rows — 26 correct, 5 imprecise, none wrong. The imprecise ones that
matter are row 19 (AD F15, which hides F1) and row 20 (AD F16, which hides F7). The text that hides F2 is
not a §1 fact but §6.1's "while … held" (F13).

---

## Findings

Severity: **BLOCKER** = change before DECIDED; **SHOULD** = resolve in the text, or answer, before
DECIDED; **NIT** = wording or slice detail.

### F1 — The cost proxy and the S2 probe miss the dominant per-move cost of the real window (BLOCKER)

**Claim (§7.2, §7.3, Kurzfassung):** P-V approximates the viewport share of a soft drag. Per move it
costs at most ~2.5 ms (edges off) or ~2.9 ms (edges on) in the container, which the AD reads as about
8–15 ms on the reference PC. The cost is "mostly in **existing** per-move viewport work" (§7.2), and a
missed bar is "a viewport question (e.g. bounds or edge segments per move)" (§7.3). The S2 probe is to be
built "like `experiments/symmetry_lab/probe_drag_cost.py`", which uses `TraceStore`.

**Evidence:**

- `GLRenderStore.update` calls `_patch_attribute(group, name, buf)` with the full buffer
  (`gl_render_store.py:178-183`). `_patch_attribute` writes `target[0:len(data)] = data`
  (`:211-219`), i.e. the whole attribute, once per per-vertex "partial" update. `RenderMesh._sync_geometry`
  issues one such update per moved vertex and per 1-ring normal (`render_mesh.py:294-314`). The cost is
  O((moved + ring) × V) per move.
- **P-V2:** p50 / p95 per move with the GL store vs. TraceStore: head 30 % 7.8 / 16.0 vs. 0.7 / 1.0 ms;
  body 30 % 30.7 / 59.0 vs. 2.1 / 2.2 ms.
- **P-V3:** `_patch_attribute` takes 2.84 of 3.36 s for 100 moves; `_transform_step` takes 0.035 s.
- The draw itself (`render()`, llvmpipe) is p95 0.4–2.8 ms. The cost sits in `sync()`, in Python and
  ctypes copying, not in the driver.
- The P-V TraceStore numbers reproduce the AD's table (same moved counts, same order of magnitude).
- **The defect is pre-existing.** Any W drag in today's window pays it: an 18-vertex drag on the body is
  p50 6 ms in the container.
- REFERENCE_HARDWARE §2 lists real window frame times as "Offen".
- WP-SYM-LAB-03 A3 measured with TraceStore, so its "remaining sync" numbers never included this.

**Why it matters:**

- The gate the AD puts before Manu's practical test would measure the wrong thing and could pass while
  the window lags by tens of milliseconds *(reading)*.
- S2c's verdict on Soft Selection would then be confounded by a viewport defect.
- The German summary tells Manu "möglicherweise über der 8-ms-Schwelle". That understates the expected
  cost by about an order of magnitude *(reading)*.

**Proposed change:**

1. **§7.2:** name the `_patch_attribute` O(moved × V) term, with the P-V2/P-V3 evidence. Replace the
   8–15 ms reading. Drop "bounds or edge segments" as the likely fix: with the GL store they are small
   next to the patch.
2. **§7.3:** the S2 probe drives the window's GL backend (`GL_TYPES` from `src/main.py`) in a hidden
   pyglet window, as `tests/test_gl_*.py` do, and reports `GLRenderStore.update` separately. A TraceStore
   variant may stay as a CPU reference.
3. **§7.3 and §12:** a decision on the store fix becomes a precondition of S2c. The fix is a
   `src/viewport` change in AD-018's scope, independent of Soft Selection. P-V4 shows the size: a
   slice-only patch, p50 28.7 → 1.5 ms on body 30 %, GPU copy == CPU copy. It belongs in its own small
   slice with a GL test.
4. Report the defect to Manu as a Production item in its own right: it already affects today's large W
   drags.
5. Correct the Kurzfassung.

### F2 — The visible Soft + Symmetry refusal can be bypassed: settings are read at `begin()`, the refusal sits at arm (BLOCKER)

**Claim (§8.1, §6.1, §4.3):**

- "W/E/R with soft on while `mesh.symmetry_definition is not None` → refused visibly at the key press".
- The soft keys are "allowed while W/E/R/T is held (state only, applies from the next gesture)".
- The settings are "read once per gesture at `begin()`".

**Evidence:**

- `begin()` runs at the first motion, not at the key press (`application.py:1580-1598`).
- **P-A §1 and §2:** X pressed after W is armed and before the first motion sets that gesture's
  `transform_space` to `x`. This holds in `Application` and in the Lab under BLOCK, where X is
  `NON_OPERATION`. The soft settings would follow the same rule.
- So W (soft off, arm passes) → O (soft on) → motion reaches `begin()` with soft on under symmetry. It
  does so in MARK always, and in BLOCK if the soft commands are in `NON_OPERATION`, as §2.1 proposes.
- What happens next depends on the S2a code:
  - **Case 1** — the tool hands the soft op `params["symmetry"]`. The op raises `ValueError` (§8.2).
    `_transform_step` catches only `SeamConstraintError` (`:1591`), so the exception leaves
    `pointer_motion`, with W still armed and the tool active. What pyglet then does is **UNVERIFIED**.
  - **Case 2** — the tool does not hand it over. The soft gesture runs one-sided under symmetry. Under
    MARK the HUD shows no warning, because `e5_warning_text` reads the Core classes
    (`lab_app.py:735-737`).
- Both cases violate E3 ("refused visibly, fail-closed") and INV-8.

**Proposed change:**

1. §8.1 makes the **authoritative** refusal at `begin()`, where the settings are read. Reuse the F3 path
   (`application.py:1591-1598`: status line, `_transform_end`, no history, mesh unchanged): either check
   `soft and mesh.symmetry_definition is not None` in `_transform_step` just before
   `begin_current_interaction`, or have the soft op raise a dedicated refusal error that `_transform_step`
   catches like `SeamConstraintError`.
2. Keep the arm-time check as early feedback only.
3. Alternatively, snapshot the soft settings at arm. That is a different stickiness rule from X/Y/Z,
   which would need saying.
4. Add to §10 S2a: "W armed, then O, then motion, with a definition set → refused visibly, no history,
   mesh unchanged, in MARK and BLOCK".

### F3 — "Documented extension points" overstates D; most hidden dependencies are not named (SHOULD)

**Claim (§3.1, §3.3, F8, F10):** D uses "the documented extension points only" and depends on three
things (the inert `_weights`, `vertex_id=`, the Scale copy).

**Evidence:** R1 above.

- `VertexTransformOperation` is not exported.
- Its docstring limits subclasses to `_transform_position` (`transform.py:214-218`).
- Of eleven dependencies, four are named (row 8 only in §8.2), two partly (rows 4 and 11), and five not
  at all (rows 5, 6, 7, 9, 10).

**Why it matters:**

- D would be the first `src/mirai` class that subclasses a Core `Operation` (F10 states that none does
  today; **VERIFIED**, grep).
- The protected hooks then become a de-facto external contract of the frozen Core, with no record in
  CORE_V1_FREEZE.
- A later Core edit (e.g. "just fill `_weights`") would silently double-weight D.

**Proposed change:**

1. Call D "protected-hook subclassing (template method) of an unexported Core base class". Keep the
   accurate part: no private state and no private helper is used.
2. List rows 1–11 in §3.3.
3. In §10 S2a, pin rows 1, 5, 6 and 7 with tests in `tests/` (not the experiment), so that any Core
   change trips them:
   - "the base never blends": one `update` on a `w < 1` vertex equals the closed form;
   - `description`;
   - the radius-0 identity (already planned).
4. When S2a lands, add a dated, docs-only line to CORE_V1_FREEZE §7.1: no Core change, but
   `src/mirai/soft_selection` consumes these hooks.
5. Reword §7 step 2 accordingly ("without a Core change", not "public API").

### F4 — "The promotion AD decides A vs D" has no owner, trigger or criteria (SHOULD)

**Claim (§3.4, §10, §12):** after the S2 verdict, its own AD decides A vs keeping D and the fate of
`_weights`.

**Evidence:** no owner, no trigger beyond "after the verdict", no criteria, and no default if nobody
acts. Meanwhile D becomes Production code in `src/mirai`. The placeholder is dead and untested in
`tests/` (R2).

**Proposed change:**

- **Owner:** the WP-SOFT-01 slice after S2c.
- **Trigger:** S2c KEEP, or a second consumer named by V1_CORE §6 (Tweak), or symmetric soft
  (FINDINGS §5.8).
- **Criteria:**
  - symmetric soft needs the shared loop (§8.3), which argues for A;
  - a second consumer argues for A or a public hook;
  - otherwise keep D.
- **Default if undecided:** D stays PROVISIONAL and the capability stays off by default.
- Add the tripwire of F3, so the placeholder cannot be revived unnoticed meanwhile.

### F5 — §2.3 calls the 2026-10-08 statement "the explicit decision AD-013 asks for" (SHOULD)

**Evidence:** R3.

- No primary record of the 2026-10-08 statement exists in the repo.
- Its wording also fits an app-path Lab.
- AD-013 H2 Alternative D treats `src/main.py` behind a flag as a promotion that needs the Artist's
  decision (`AD-013:476`).

**Proposed change:**

1. §0.3: quote the 2026-10-08 statement with its source (date, wording, where it was given).
2. §2.3: say that Manu's answer to Q1 is the explicit AD-013 decision. Spell out what it covers: "Soft
   Selection may run in `src/main.py` for S2, off by default, with PROVISIONAL keys and look, as an
   unvalidated capability; no promotion".
3. Log it in ROADMAP §7 intake when decided.

### F6 — `NON_OPERATION`: change the G-2 table, and give the right reason (SHOULD)

**Claim (§2.1, §8.4):** "a dated note in AD-013's G-2 amendment". Without the addition "soft could not
be switched off while symmetry is on".

**Evidence:**

- G-2 says "contains exactly" (`AD-013:933`) and leaves new classifications open.
- P-K: the Lab tests need no edit either way.
- P-A §3: without the addition O is refused under BLOCK with "Befehl nicht koordiniert", which is
  escapable via Shift+B or Shift+S.

**Proposed change:**

1. The note **changes the table**: a new group "soft settings" with the five commands and gate path
   `key_press`. It is dated and decided with AD-020. No second H2 review is needed (no Limit of G
   lifted, no writer added).
2. State the reason as classification (state for the next gesture, like the constraints), and describe
   the BLOCK behaviour without the addition as a nuisance, not a trap.
3. Note the interaction with F2: membership opens the bypass under BLOCK unless the refusal moves to
   `begin()`.

### F7 — O was vacated on purpose; two Production tests pin it unbound (SHOULD)

**Claim (§6.1):** "O — Free in GLOBAL, KNIFE, TOPOLOGY, Symmetry Lab; no Artist Truth entry uses O."

**Evidence:**

- ROADMAP §7 line 495 (B5a): "`Shift+D` toggles the wire overlay (Artist Input Truth; the old default
  `O` is gone)".
- `tests/test_input_binding.py:107-113` ("WP-06 B5a (E42): Artist Input Truth — D statt O",
  `assertIsNone(... _key("o"))`) and `tests/test_display_modes.py:328-334` both pin O unbound.
- P-K: these are the only two Production failures with the proposed bindings (2318 passed, 2 failed).

**Why it matters:**

- The statement is true today, but it omits that O had a display meaning the Artist moved to D.
- S2a would have to weaken two tests whose stated purpose is that Truth change.
- Manu may still reach for O expecting the wireframe toggle *(reading)*.

**Proposed change:**

1. Name the history in §6.1.
2. Ask Manu explicitly, in the decision list: "O for Soft, although O was the old display key?".
3. If yes, the S2a handoff rewrites both tests to "O is not a display key" rather than deleting the
   assertion.

### F8 — Q1-B is rejected against an influence hook, not against the cheaper settings-only data hook (SHOULD)

**Claim (§2.1 row B):** B needs "a data hook 'influence for the next gesture', or an operation factory",
and "a host-computed influence cannot follow the hover target".

**Evidence:** R3. A G-style read-only *settings* field (e.g. `app.soft_settings`, default `None`, written
only by a second Lab, read at `begin()` by the tool, which computes the influence from its own target)
follows the hover target. It needs no callback and no operation factory.

**Proposed change:** add row **B′** (A's `src` code, no default bindings, settings written by a second
app-path Lab through one data field). Reject it with the real reason: it adds a second Lab, an AD-013
addendum and an H2-R6-style review to reach the same gesture. A's off-by-default keys do the same job
more cheaply, and the Artist asked for the Production viewport. The conclusion A stays.

### F9 — One source for the world radius, and an update contract for the overlay (SHOULD)

**Claim (§4.3, §4.4, §5.1):**

- The radius is a fraction of the bounding radius. `mesh_center_and_radius` should run "once per mesh
  state (e.g. on toggle and after topology changes)".
- Preview and `begin()` "both agree", because nothing moves between them without a notification (§4.4).

**Evidence:**

- Gestures, Undo and Redo change the bounds too, so "once per mesh state" and "after topology changes"
  disagree.
- If the preview and the tool read the radius at different times, they can disagree. If both read a
  cached value, the meaning of "15 %" drifts silently.
- The H1 contract calls `o.sync(mesh, selection)` only on notifications or when `o.dirty` is set
  (`viewport.py:249-257`). Nobody is named as pushing the weights or setting `dirty` on a settings change.

**Proposed change:**

1. `SoftSettings` holds the radius in **world units**. They are computed when soft is switched on, when
   a step changes, and on scene load, and are read by both preview and tool. The status line already
   shows both (`15 % (0.51)`).
2. §5.1: `Application` pushes the weights (selection preview, or the op's weights at `begin()`) into the
   overlay and sets `dirty`; the overlay never computes influence itself.
3. Add an S2a test: preview weights == op weights at `begin()`.

### F10 — D changes S1's stale-ID contract (L10); the S1 suite does not port "with one helper change" (SHOULD)

**Claim (§3.3, D row):** "the S1 suite ports with one helper change". §4.2 cites S1 L10 for the
refusals.

**Evidence (P-D3):** the S1 op suite on D with the AD's helper change gives 56 passed, **3 failed**: all
three `test_stale_ids_in_influence_skipped[…]`. They fail with `KeyError` from the base `_on_begin`
(P-D2), where S1 skips stale IDs (L10).

**Proposed change:** pick one.

- D filters stale IDs before the key-set check and hands the base a view of the valid keys (L10 kept).
- D refuses stale IDs with a `ValueError` before `super()._on_begin` (L10 changed, and stated so).

The app path never produces stale IDs, so either is fine. The text should say which.

### F11 — Q4: separate headless data from the GL sink; reword the rejection of c; two missed alternatives (NIT)

- §5.1: a headless band object (weights → bands → positions, testable without GL, the E16 precedent),
  with the `GLPointOverlay` subclass as its sink through the `soft_overlay_type` pass-through.
- §5.2 c: reject it for its cost (layout, shader, a pipeline slated for removal, driver behaviour), and
  do not cite the selection REJECT as covering influence.
- Missed alternative: face bands via `GLTriangleOverlay`/`FlatColorLayers`, depth-tested like the B5b
  face highlight. No `RenderMesh` change. Ambiguous where a face spans bands.
- Missed alternative for hover-armed gestures: show the bands at arm (once per key press, ≤ 2.2 ms on
  the reference PC by FINDINGS R10) instead of per hover change.

### F12 — Q5 details (NIT)

- §6.1 says "Four new command constants … four defaults" for five inputs. Up and Down need two commands
  (`SoftRadiusUp`/`SoftRadiusDown`). A binding carries the meaning, so a rebind through `keymap.json`
  must not have to know a direction (AD-013 I2; `INPUT_COMMAND_TOOL_CONTRACT`). P-K used five.
- Ctrl+O is the near-universal "Open". The Truth keeps `application.load` intentionally unbound (rule 4),
  so there is no conflict today. Alternative: Alt+O. Blender 2.7x put proportional "connected only" on
  it (recalled, **UNVERIFIED**). It would share whatever Windows does with Alt+letter in a menu-less
  window with today's Alt+A (**UNVERIFIED**).
- Holding Up/Down does not repeat (R7). Say "one step per press".
- The rejection of V has a stronger reason than "two meanings". A GLOBAL V binding would *break* the
  symmetric Knife's variant key. `_knife_key` reads V only when `command is None`
  (`application.py:1022-1024`), and the KNIFE context falls back to GLOBAL (`input.py:212`).

### F13 — Smaller corrections (NIT)

- P-D covered the linear Scale formula only. This review checked `"power"` too: bitwise equal to S1
  (P-D2).
- §3.3 "one copied formula (Scale)": Move's tuple sum is a second, trivial copy (row 4).
- F5 "`MoveTool` likewise": `MoveTool` hands the op no `pivot`, only `"symmetry"` when a definition is
  set (`move.py:192-208`).
- §6.1 says the soft keys work "while W/E/R/T is held (state only, applies from the next gesture)", and
  §4.3 says a change "during a running gesture … applies from the next gesture". F2's precedent
  (`_constrain`, `application.py:1548-1553`) says that only for a *running* gesture. A gesture that is
  armed but has not begun takes the new value (P-A). "Held" in §6.1 covers both, and that is the gap F2
  exploits.
- §0.1: add a one-line environment note. In some containers the bare `pytest` lacks pyglet; use
  `python -m pytest` (this review).
- §4.3: say that S2 cannot answer the unit part of FINDINGS §5.4, only the steps, because only one unit
  is offered.

---

## Code facts checked

| # | AD claim (section) | Result |
|---|---|---|
| 1 | `_transform_arm` `application.py:1507-1543`, `resolve_selection_vertices` at `:1518` (F1) | correct (function ends `:1542`) |
| 2 | `_transform_space = self._axis_constraint` `:1581`; payload `scene`/`camera`/`vertex_ids`/`space` `:1584-1590` (F1) | correct |
| 3 | `on_vertices_moved(self._active_transform_vertex_ids())` `:1603`; `:1606-1612`; `_cancel` notifies the same set `:1759-1762` (F1) | correct |
| 4 | Sticky `_axis_constraint` `:418-422`; `_constrain` `:1548-1556`, "new value applies from the next gesture" (F2) | correct (for a *running* gesture; §6.1's "while … held" stretches it to an armed gesture, which takes the new value: P-A, F2, F13) |
| 5 | `SeamConstraintError` refusal path `:1591-1598` (F3) | correct |
| 6 | `tool = tool_class()` per activation `tool_manager.py:74-76` (F4) | correct |
| 7 | `TransformTool._on_begin` view + `params` `tools/transform.py:348-379`; "`MoveTool` likewise" `tools/move.py:190-221` (F5) | imprecise — `MoveTool` passes no `pivot` |
| 8 | Move anchor `min(vertex_ids)` before partners `tools/move.py:125` (F5) | correct (`_vertex_ids` replaced at `:211`) |
| 9 | Rotate axis fixed `tools/rotate.py:101-116`, passed `:133`; Scale basis `tools/scale.py:119`, `:175`, `:179` (F6) | correct |
| 10 | Base loop + placeholder blend `transform.py:261-270`; weights `1.0` `:227`; nothing in the Core sets them (F7) | correct (grep: no setter in `src`, no test in `tests/`) |
| 11 | `Operation` hooks `operation.py:82-85`, `:128-145`; subclasses implement only `_transform_position` `transform.py:214-218`, `:289-295` (F8) | imprecise — cited correctly, but the text says "ausschließlich", which D exceeds (F3) |
| 12 | `MoveOperation._on_begin` super-call `move.py:91-101`; `pivot`/`vertex_ids` `transform.py:252-259`; `rotate_around_axis` `:98-118`; `VertexTransformCommand` `:187-208` in `core.__all__`; `ScaleOperation._apply` `:418-435` (F8) | correct |
| 13 | Incremental contract and the "explicitly documented deviation" clause `operation.py:15-25` (F9) | correct |
| 14 | No `src/mirai` module touches a Core private or subclasses a Core `Operation`; imports at `application.py:44`, `tools/rotate.py:38`, `tools/selection_helpers.py:12` (F10) | correct (grep). `VertexTransformOperation` "module-public": imprecise — exported by neither `__all__` |
| 15 | CORE_V1_FREEZE §4 lists "Soft Selection / Influence-System" (F11) | correct (`:274`) |
| 16 | H1 contract `viewport.py:52-59`, `add_overlay` `:162-166`, `sync` `:244-257`, draw `:319-320`; `GLPointOverlay` class attributes `gl_point_overlay.py:125-134`, depth off `:211` (F12) | correct |
| 17 | `set_tool_overlay` replaces all tool layers `viewport.py:170-183` (F13) | correct |
| 18 | `highlight_flags` slot `render_mesh.py:74`; shader no longer reads it `gl_render_store.py:63-93`; hotfix `:213-219` (F14) | correct |
| 19 | `_sync_geometry` `render_mesh.py:277-314` with "partial uploads per moved vertex"; bounds `derived.py:305-307`; edges `viewport.py:275-281` (F15) | imprecise **with consequence** — partial at the `RenderMesh` level, but each one re-copies the whole attribute in `GLRenderStore` (`:166-183`, `:199-219`; F1) |
| 20 | GLOBAL/KNIFE/TOPOLOGY bindings `bindings.py:107-182`; V `application.py:250`, `:1022-1024`; Lab keys `lab_bindings.py:46-62`; Truth reservations; Q unbound `AD-013:391` (F16) | imprecise — all correct, but O's B5a history and the two tests pinning it are missing (F7) |
| 21 | Adapter key map `pyglet_input.py:54-69`; scroll without modifiers `main.py:207-211`, `pyglet_input.py:142-153` (F17) | correct |
| 22 | BLOCK fail-closed `lab_app.py:125`, `:132-170`, `:293`; "exactly" `AD-013:933`; Lab tests parametrise over all constants `test_app_lab_fail_closed.py:82-85`, `:184-218`, "need no edit" (F18) | correct (T-FC1 at `:183-221`; "no edit" VERIFIED, P-K) |
| 23 | `git diff eaf43a3..f65d223 -- src/core` and `02a08c3..f65d223 -- src/core src/mirai/interaction/tools` empty (§0.2) | correct |
| 24 | Only additive EXTRUDE branches in `key_press`, `key_release`, `_transform_arm`, `_transform_step`, `_cancel`; `_transform_end` only resets Extrude state (§0.2) | correct (AST diff: the only removed lines are three `if` → `elif`) |
| 25 | `_TRANSFORM_COMMANDS` `:110-115`; `interaction_owner` `:1403-1414`; constraints ignored during Extrude `:1450-1454`; `T` `bindings.py:129`; Knife symmetry layers `overlay.py:74-96`; draw order `viewport.py:83-96` (§0.2) | correct |
| 26 | Knife session takes keys first `application.py:1443-1444` (§6.1) | correct |
| 27 | Wheel = Zoom `bindings.py:171-172`; Knife Shift tracking `main.py:146-156`; 1/2/3 clear the selection `application.py:608-621` (§6.2) | correct |
| 28 | `supports_symmetry` default `operation.py:88`; `_PivotTransformOperation` `transform.py:298-366`; Move tuple sum `move.py:110` (§8, §3.1) | correct |
| 29 | Radius as a fraction of the bounding radius `probe_cost.py:142-148`; `math.dist` per vertex `mesh_geometry.py:44-46` (§4.3) | correct |
| 30 | `init_scene` pass-through pattern `application.py:493-555`; `GL_TYPES` `main.py:118-124`; thin entry point `main.py:72-80`; "`Application` calls no experiment code" `AD-013:500` (§5.1, §2.1) | correct |
| 31 | A3: per-move p95 0.40 / 0.86 ms, remaining sync p95 1.04 / 1.44 ms; body hover change ~9.5 ms (§7.1, §5.1); baseline 2320/6, 466/4, 96 (§0.1) | correct (plan `:436-441`, `:458`); counts reproduced with `python -m pytest` |

Totals: 26 correct, 5 imprecise (rows 7, 11, 14, 19, 20), 0 wrong.

---

## Appendix — review probes

Throwaway, kept in the session scratchpad, not committed. They were run from the repo root at `0f079bd` with `python` (the interpreter that has pyglet), and the GL probes under `xvfb-run -a`. All numbers are **container numbers** (REFERENCE_HARDWARE.md §4). `_setup.py`, which every probe imports first:

```python
import sys
from pathlib import Path
REPO = Path("/home/user/Mirai-Bastel")
HERE = Path(__file__).resolve().parent
for p in (HERE, REPO / "src", REPO, REPO / "examples", REPO / "experiments"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
if str(REPO / "tests") not in sys.path:
    sys.path.append(str(REPO / "tests"))
```

### P-D — alternative D rebuilt (`d_ops.py`, from AD-020 Appendix A plus the refusals of §4.2)

Appendix A elides the body of `DScale._on_update` (`...`). The order used here follows its comment ("one basis per gesture (L5); accumulate the total factor; then the Core loop"), with the factor validated first.

```python
"""Review probe (CLAUDE-001 of AD-020): alternative D rebuilt from AD-020 Appendix A + §4.2.

Only public Core names are imported; the classes override the protected hooks
`_on_begin` / `_on_update` / `_transform_position` of VertexTransformOperation
with super-calls. ScaleOperation._apply and _as_triple are COPIED (as the AD says).
"""
from __future__ import annotations

import math

from core.operations.transform import VertexTransformOperation, rotate_around_axis


def triple(factor):
    # copy of core.operations.transform._as_triple (no finiteness check, like the Core)
    if isinstance(factor, (int, float)):
        f = float(factor)
        return (f, f, f)
    values = tuple(float(v) for v in factor)
    if len(values) != 3:
        raise ValueError(f"factor needs 3 components, got {values!r}")
    return values


def scale_apply(pivot, pos, f, basis):
    # copy of ScaleOperation._apply (transform.py:418-435), same operation order
    q = (pos[0] - pivot[0], pos[1] - pivot[1], pos[2] - pivot[2])
    if basis is None:
        s = (f[0] * q[0], f[1] * q[1], f[2] * q[2])
        return (pivot[0] + s[0], pivot[1] + s[1], pivot[2] + s[2])
    b0, b1, b2 = basis
    dot = lambda a, b: a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    sc = lambda a, s: (a[0] * s, a[1] * s, a[2] * s)
    add = lambda a, b: (a[0] + b[0], a[1] + b[1], a[2] + b[2])
    c0, c1, c2 = dot(q, b0), dot(q, b1), dot(q, b2)
    scaled = add(add(sc(b0, f[0] * c0), sc(b1, f[1] * c1)), sc(b2, f[2] * c2))
    return add(pivot, scaled)


class _DSoft(VertexTransformOperation):
    _requires_pivot = False

    def _on_begin(self, context):
        params = context.params
        if "symmetry" in params:
            raise ValueError("soft: params['symmetry'] must not be set (E9 / AD-020 §8.2)")
        if self._requires_pivot and params.get("pivot") is None:
            raise ValueError(f"{type(self).__name__} needs params['pivot'] (E7)")
        if params.get("influence") is None:
            raise ValueError(f"{type(self).__name__} needs params['influence']")
        influence = {}
        for vid, w in params["influence"].items():
            w = float(w)
            if not (0.0 < w <= 1.0):
                raise ValueError(f"influence weight for {vid!r} must be in (0, 1], got {w!r}")
            influence[vid] = w
        if set(influence) != set(context.selection.vertices):
            raise ValueError("soft: selection view != influence keys")
        super()._on_begin(context)  # Core snapshot, pivot
        self._influence = influence
        self._start = {vid: context.target.vertex_position(vid) for vid in influence}


class DMove(_DSoft):
    description = "Soft Move Vertices"

    def _transform_position(self, pos, delta, vertex_id=None, **_):
        w = self._influence[vertex_id]
        if w != 1.0:
            delta = (w * delta[0], w * delta[1], w * delta[2])
        return (pos[0] + delta[0], pos[1] + delta[1], pos[2] + delta[2])  # = core move.py:110


class DRotate(_DSoft):
    description = "Soft Rotate Vertices"
    _requires_pivot = True

    def _transform_position(self, pos, axis, angle, vertex_id=None, **_):
        w = self._influence[vertex_id]
        return rotate_around_axis(pos, self.pivot, axis, angle if w == 1.0 else w * angle)


class DScale(_DSoft):
    description = "Soft Scale Vertices"
    _requires_pivot = True

    def _on_begin(self, context):
        formula = context.params.get("scale_formula", "linear")
        if formula not in ("linear", "power"):
            raise ValueError(f"scale_formula {formula!r}")
        super()._on_begin(context)
        self._formula = formula
        self._total = (1.0, 1.0, 1.0)
        self._basis_set = False
        self._basis = None

    def _on_update(self, factor, basis=None, **kw):
        f = triple(factor)                                   # malformed factor raises here
        if self._basis_set and basis != self._basis:         # L5, before anything moves
            raise ValueError("DScale needs the same basis for the whole gesture")
        total = (self._total[0] * f[0], self._total[1] * f[1], self._total[2] * f[2])
        if self._formula == "power" and any(t < 0.0 for t in total):
            raise ValueError("power formula undefined for negative factors")
        self._basis_set, self._basis, self._total = True, basis, total
        super()._on_update(factor=factor, basis=basis, **kw)  # the Core loop

    def _transform_position(self, pos, factor, basis=None, vertex_id=None, **_):
        w = self._influence[vertex_id]
        if w == 1.0:
            return scale_apply(self.pivot, pos, triple(factor), basis)
        if self._formula == "power":
            g = tuple(t ** w for t in self._total)
        else:
            g = tuple(1.0 + w * (t - 1.0) for t in self._total)
        return scale_apply(self.pivot, self._start[vertex_id], g, basis)
```

### P-D — D vs. S1, D vs. Core at radius 0, path independence, private-member scan (`probe_pd.py`)

```python
"""Review probe P-D (CLAUDE-001 of AD-020): D vs S1 ops, D vs Core at radius 0, path independence,
private-member scan, edge cases. Container only."""
import _setup  # noqa: F401
import ast, inspect, math, random

from core import HistoryStack, MoveOperation, OperationContext, RotateOperation, ScaleOperation, VertexId
from core.operations.transform import VertexTransformOperation
from soft_selection.influence import compute_influence, primary_pivot
from soft_selection.weighted_ops import (SoftMoveOperation, SoftRotateOperation, SoftScaleOperation,
                                         _InfluenceView)
from soft_selection.tests._fixtures import head

import d_ops
from d_ops import DMove, DRotate, DScale

def positions(m):
    return {v: m.vertex_position(v) for v in m.all_vertex_ids()}

def case(radius, metric):
    mesh = head()
    first = mesh.all_vertex_ids()[100]
    seeds = {first}
    for eid in mesh.vertex_edges(first):
        seeds.update(mesh.edge_vertices(eid))
    inf = compute_influence(mesh, seeds, radius, metric=metric, curve="smooth")
    return mesh, seeds, inf, primary_pivot(mesh, seeds)

def ctx(mesh, inf, pivot, **extra):
    return OperationContext(target=mesh, selection=_InfluenceView(set(inf)), history=HistoryStack(),
                            params={"influence": inf, "pivot": pivot, **extra})

c, s = math.cos(0.4), math.sin(0.4)
TILT = ((c, s, 0.0), (-s * 0.6, c * 0.6, 0.8), (s * 0.8, -c * 0.8, 0.6))   # orthonormal
AXIS = (0.3, 1.0, -0.2)

def steps(kind, rng, n=60):
    if kind == "move":
        return [{"delta": tuple(rng.uniform(-0.02, 0.02) for _ in range(3))} for _ in range(n)]
    if kind == "rotate":
        return [{"axis": AXIS, "angle": rng.uniform(-0.03, 0.03)} for _ in range(n)]
    return [{"factor": tuple(rng.uniform(0.98, 1.025) for _ in range(3)), "basis": TILT} for _ in range(n)]

def run(op, st):
    op.begin()
    for k in st:
        op.update(**k)
    return op.commit()

PAIRS = {"move": (DMove, SoftMoveOperation, MoveOperation),
         "rotate": (DRotate, SoftRotateOperation, RotateOperation),
         "scale": (DScale, SoftScaleOperation, ScaleOperation)}

print("== 1. D vs S1 ops (60 updates; positions + History start/end maps) ==")
ok1 = 0
for kind, (D, S1, _) in PAIRS.items():
    for metric in ("euclidean", "geodesic"):
        for radius in (0.0, 1.0):
            st = steps(kind, random.Random(7))
            ma, seeds, inf, piv = case(radius, metric)
            mb = head()
            ca = run(D(ctx(ma, inf, piv)), st)
            cb = run(S1(ctx(mb, inf, piv)), st)
            same = (positions(ma) == positions(mb) and ca.start_positions == cb.start_positions
                    and ca.end_positions == cb.end_positions)
            ok1 += same
            print(f"  {kind:6s} {metric:9s} r={radius:3.1f} influenced={len(inf):3d} bitwise_equal={same}")
print(f"  -> {ok1}/12 bitwise equal")

print("== 2. D vs Core at radius 0, same explicit pivot ==")
ok2 = 0
for kind, (D, _, Core) in PAIRS.items():
    for metric in ("euclidean", "geodesic"):
        st = steps(kind, random.Random(11))
        ma, seeds, inf, piv = case(0.0, metric)
        assert inf == {v: 1.0 for v in seeds}
        mb = head()
        ca = run(D(ctx(ma, inf, piv)), st)
        cb = run(Core(OperationContext(target=mb, selection=_InfluenceView(set(seeds)),
                                       history=HistoryStack(), params={"pivot": piv})), st)
        same = (positions(ma) == positions(mb) and ca.start_positions == cb.start_positions
                and ca.end_positions == cb.end_positions)
        ok2 += same
        print(f"  {kind:6s} {metric:9s} bitwise_equal={same}")
print(f"  -> {ok2}/6 bitwise equal")

print("== 3. Path independence, 1 step vs 60 steps (r=1.0, euclidean, smooth) ==")
for kind in ("move", "rotate", "scale"):
    D = PAIRS[kind][0]
    ma, seeds, inf, piv = case(1.0, "euclidean")
    mb = head()
    n = 60
    if kind == "move":
        tot = (0.3, -0.12, 0.05); one = [{"delta": tot}]; many = [{"delta": tuple(t / n for t in tot)}] * n
    elif kind == "rotate":
        one = [{"axis": AXIS, "angle": 0.9}]; many = [{"axis": AXIS, "angle": 0.9 / n}] * n
    else:
        tot = (1.7, 0.8, 1.3); one = [{"factor": tot, "basis": TILT}]
        many = [{"factor": tuple(f ** (1.0 / n) for f in tot), "basis": TILT}] * n
    run(D(ctx(ma, inf, piv)), one); run(D(ctx(mb, inf, piv)), many)
    a, b = positions(ma), positions(mb)
    dev = max(max(abs(x - y) for x, y in zip(a[v], b[v])) for v in a)
    print(f"  {kind:6s} max deviation {dev:.2e}")

print("== 4. Underscore attribute accesses in the D classes (AST) ==")
src = inspect.getsource(d_ops)
names = sorted({n.attr for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Attribute) and n.attr.startswith("_")})
defs = sorted({n.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name.startswith("_")})
probe = VertexTransformOperation.__new__(VertexTransformOperation)
core_state = {"_weights", "_start_positions", "_vertex_ids", "_pivot", "_mesh", "_apply", "_active",
              "_selection_center", "_as_triple"}
core_hooks = {a for a in dir(VertexTransformOperation) if a.startswith("_") and not a.startswith("__")}
print("  attribute reads/writes:", names)
print("  -> of these, Core private STATE/helpers:", sorted(set(names) & core_state) or "none")
print("  methods defined with a leading underscore:", defs)
print("  -> overriding Core hooks:", sorted(set(defs) & core_hooks))
print("  -> own attrs that a future Core change could collide with:", sorted(set(names) - core_hooks - core_state))
print("  VertexTransformOperation in core.__all__:", "VertexTransformOperation" in __import__("core").__all__,
      "| in core.operations.__all__:", "VertexTransformOperation" in __import__("core.operations", fromlist=["x"]).__all__)
```

Output:

```text
== 1. D vs S1 ops (60 updates; positions + History start/end maps) ==
  move   euclidean r=0.0 influenced=  5 bitwise_equal=True
  move   euclidean r=1.0 influenced=101 bitwise_equal=True
  move   geodesic  r=0.0 influenced=  5 bitwise_equal=True
  move   geodesic  r=1.0 influenced= 75 bitwise_equal=True
  rotate euclidean r=0.0 influenced=  5 bitwise_equal=True
  rotate euclidean r=1.0 influenced=101 bitwise_equal=True
  rotate geodesic  r=0.0 influenced=  5 bitwise_equal=True
  rotate geodesic  r=1.0 influenced= 75 bitwise_equal=True
  scale  euclidean r=0.0 influenced=  5 bitwise_equal=True
  scale  euclidean r=1.0 influenced=101 bitwise_equal=True
  scale  geodesic  r=0.0 influenced=  5 bitwise_equal=True
  scale  geodesic  r=1.0 influenced= 75 bitwise_equal=True
  -> 12/12 bitwise equal
== 2. D vs Core at radius 0, same explicit pivot ==
  move   euclidean bitwise_equal=True
  move   geodesic  bitwise_equal=True
  rotate euclidean bitwise_equal=True
  rotate geodesic  bitwise_equal=True
  scale  euclidean bitwise_equal=True
  scale  geodesic  bitwise_equal=True
  -> 6/6 bitwise equal
== 3. Path independence, 1 step vs 60 steps (r=1.0, euclidean, smooth) ==
  move   max deviation 2.49e-14
  rotate max deviation 9.55e-15
  scale  max deviation 2.22e-15
== 4. Underscore attribute accesses in the D classes (AST) ==
  attribute reads/writes: ['__name__', '_basis', '_basis_set', '_formula', '_influence', '_on_begin', '_on_update', '_requires_pivot', '_start', '_total']
  -> of these, Core private STATE/helpers: none
  methods defined with a leading underscore: ['_on_begin', '_on_update', '_transform_position']
  -> overriding Core hooks: ['_on_begin', '_on_update', '_transform_position']
  -> own attrs that a future Core change could collide with: ['__name__', '_basis', '_basis_set', '_formula', '_influence', '_requires_pivot', '_start', '_total']
  VertexTransformOperation in core.__all__: False | in core.operations.__all__: False
```

### P-D2 — D edge cases (`probe_pd_edges.py`)

```python
"""Review probe P-D2: D edge cases (R1)."""
import _setup  # noqa: F401
import math
from core import HistoryStack, OperationContext, VertexId
from soft_selection.influence import compute_influence, primary_pivot
from soft_selection.weighted_ops import _InfluenceView, SoftScaleOperation
from soft_selection.tests._fixtures import head
from d_ops import DMove, DRotate, DScale

def positions(m): return {v: m.vertex_position(v) for v in m.all_vertex_ids()}
def case(radius=1.0):
    mesh = head(); first = mesh.all_vertex_ids()[100]; seeds = {first}
    for eid in mesh.vertex_edges(first): seeds.update(mesh.edge_vertices(eid))
    inf = compute_influence(mesh, seeds, radius); return mesh, seeds, inf, primary_pivot(mesh, seeds)
def ctx(mesh, inf, piv, view=None, h=None, **extra):
    p = {"influence": inf, **({"pivot": piv} if piv is not None else {}), **extra}
    return OperationContext(target=mesh, selection=_InfluenceView(set(inf) if view is None else view),
                            history=h or HistoryStack(), params=p)
def attempt(label, fn):
    try:
        r = fn(); print(f"  {label}: ok -> {r}")
    except Exception as e:
        print(f"  {label}: {type(e).__name__}: {str(e)[:90]}")

mesh, seeds, inf, piv = case()
stale = VertexId(10**6)
print("== stale / empty / missing ==")
attempt("stale id in map AND view (S1 skips it, L10)", lambda: DMove(ctx(head(), {**inf, stale: 0.5}, piv)).begin())
attempt("stale id in map only", lambda: DMove(ctx(head(), {**inf, stale: 0.5}, piv, view=set(inf))).begin())
def empty():
    h = HistoryStack(); op = DMove(ctx(head(), {}, None, h=h)); op.begin(); op.update(delta=(1, 0, 0))
    return ("commit", op.commit(), "history", len(h))
attempt("empty influence + empty view, Move", empty)
attempt("empty influence, Rotate without pivot", lambda: DRotate(ctx(head(), {}, None)).begin())
attempt("missing map", lambda: DMove(OperationContext(target=head(), selection=_InfluenceView(set()), history=HistoryStack())).begin())
attempt("weight 1.5", lambda: DMove(ctx(head(), {**inf, next(iter(inf)): 1.5}, piv)).begin())
attempt("weight NaN", lambda: DMove(ctx(head(), {**inf, next(iter(inf)): math.nan}, piv)).begin())
attempt("view != keys (seeds only)", lambda: DMove(ctx(head(), inf, piv, view=set(seeds))).begin())
attempt("symmetry=None present", lambda: DScale(ctx(head(), inf, piv, symmetry=None)).begin())
print("  supports_symmetry:", DMove.supports_symmetry, DRotate.supports_symmetry, DScale.supports_symmetry)

print("== commit None / cancel exactness ==")
m = head(); h = HistoryStack(); op = DMove(ctx(m, inf, piv, h=h)); op.begin(); op.update(delta=(0.0, 0.0, 0.0))
print("  Move zero delta -> commit", op.commit(), "history", len(h))
for cls, kw in ((DMove, {"delta": (0.1, 0.2, -0.1)}), (DRotate, {"axis": (0, 1, 0), "angle": 0.7}),
                (DScale, {"factor": (1.3, 0.8, 1.1)})):
    m = head(); start = positions(m); h = HistoryStack(); op = cls(ctx(m, inf, piv, h=h)); op.begin()
    for _ in range(5): op.update(**kw)
    op.cancel(); print(f"  {cls.__name__} cancel exact: {positions(m) == start}, history {len(h)}")
m = head(); op = DRotate(ctx(m, inf, piv)); op.begin(); op.update(axis=(0, 1, 0), angle=0.0)
print("  Rotate angle 0 commit (L6 identity, like Core):", op.commit() is not None)

print("== basis mismatch mid-gesture: is the accumulated total consistent afterwards? ==")
TILT = ((math.cos(.5), math.sin(.5), 0.0), (-math.sin(.5), math.cos(.5), 0.0), (0.0, 0.0, 1.0))
ma = head(); mb = head()
a = DScale(ctx(ma, inf, piv)); a.begin(); a.update(factor=(1.2, 1, 1), basis=TILT)
before = positions(ma)
try:
    a.update(factor=(1.5, 1, 1), basis=None)
except ValueError as e:
    print("  refused:", e, "| mesh unchanged:", positions(ma) == before, "| total", a._total)
a.update(factor=(1.1, 1, 1), basis=TILT); a.commit()
b = DScale(ctx(mb, inf, piv)); b.begin(); b.update(factor=(1.2, 1, 1), basis=TILT); b.update(factor=(1.1, 1, 1), basis=TILT); b.commit()
print("  after refusal + continue == run without the refused step:", positions(ma) == positions(mb))
m = head(); s0 = positions(m); op = DScale(ctx(m, inf, piv)); op.begin()
try: op.update(factor=(1.2, 1.0))
except ValueError as e: print("  malformed factor refused before anything moves:", positions(m) == s0, "| total", op._total)
op.cancel()

print("== power formula (not covered by the AD's P-D) ==")
ma, mb = head(), head()
a = DScale(ctx(ma, inf, piv, scale_formula="power")); b = SoftScaleOperation(ctx(mb, inf, piv, scale_formula="power"))
for op in (a, b):
    op.begin(); [op.update(factor=(1.01, 0.99, 1.02), basis=TILT) for _ in range(30)]; op.commit()
print("  D power == S1 power bitwise:", positions(ma) == positions(mb))
```

Output:

```text
== stale / empty / missing ==
  stale id in map AND view (S1 skips it, L10): KeyError: VertexId(1000000)
  stale id in map only: ValueError: soft: selection view != influence keys
  empty influence + empty view, Move: ok -> ('commit', None, 'history', 0)
  empty influence, Rotate without pivot: ValueError: DRotate needs params['pivot'] (E7)
  missing map: ValueError: DMove needs params['influence']
  weight 1.5: ValueError: influence weight for VertexId(100) must be in (0, 1], got 1.5
  weight NaN: ValueError: influence weight for VertexId(100) must be in (0, 1], got nan
  view != keys (seeds only): ValueError: soft: selection view != influence keys
  symmetry=None present: ValueError: soft: params['symmetry'] must not be set (E9 / AD-020 §8.2)
  supports_symmetry: False False False
== commit None / cancel exactness ==
  Move zero delta -> commit None history 0
  DMove cancel exact: True, history 0
  DRotate cancel exact: True, history 0
  DScale cancel exact: True, history 0
  Rotate angle 0 commit (L6 identity, like Core): True
== basis mismatch mid-gesture: is the accumulated total consistent afterwards? ==
  refused: DScale needs the same basis for the whole gesture | mesh unchanged: True | total (1.2, 1.0, 1.0)
  after refusal + continue == run without the refused step: True
  malformed factor refused before anything moves: True | total (1.0, 1.0, 1.0)
== power formula (not covered by the AD's P-D) ==
  D power == S1 power bitwise: True
```

### P-D3 — the S1 op suite run against D (`make_s1port.py`)

```python
# P-D3: copy the S1 op suite, point it at the D classes, apply the AD's "one helper change"
# (soft_context hands the op a view of the influenced set). Run: python -m pytest s1port -q
src = open("/home/user/Mirai-Bastel/experiments/soft_selection/tests/test_weighted_ops.py").read()
src = src.replace("""from soft_selection.weighted_ops import (
    SoftMoveOperation,
    SoftRotateOperation,
    SoftScaleOperation,
    _InfluenceView,
    soft_context,
)""", """from soft_selection.weighted_ops import _InfluenceView, soft_context as _s1_soft_context
from d_ops import DMove as SoftMoveOperation, DRotate as SoftRotateOperation, DScale as SoftScaleOperation


def soft_context(*a, **k):
    # the AD's 'one helper change': hand the op a view of the influenced set
    c = _s1_soft_context(*a, **k)
    return OperationContext(target=c.target, selection=_InfluenceView(set(c.params["influence"])),
                            history=c.history, params=c.params)""")
src = src.replace("from ._fixtures import grid, head", "from soft_selection.tests._fixtures import grid, head")
open("s1port/test_weighted_ops_on_d.py", "w").write(src)
# s1port/conftest.py: puts the probe directory on sys.path and imports _setup
```

Output of `python -m pytest s1port -q` (paths shortened):

```text
FAILED s1port/test_weighted_ops_on_d.py::test_stale_ids_in_influence_skipped[DMove]
FAILED s1port/test_weighted_ops_on_d.py::test_stale_ids_in_influence_skipped[DRotate]
FAILED s1port/test_weighted_ops_on_d.py::test_stale_ids_in_influence_skipped[DScale]
3 failed, 56 passed in 0.49s
```

### P-V / P-V2 — AD-020 Appendix B rebuilt, with a GL variant (`probe_pv.py`)

`python probe_pv.py` (TraceStore, as in the AD) and `xvfb-run -a python probe_pv.py --gl` (`GL_TYPES` from `src/main.py` in a hidden pyglet window). The two runs were sequential, with no other load on the machine.

```python
"""Review probe P-V (CLAUDE-001 of AD-020): AD-020 Appendix B rebuilt, plus a GL variant.

  python probe_pv.py            # TraceStore, as in the AD (CPU side, no upload, no draw)
  python probe_pv.py --gl       # GLRenderStore + GL overlays in a hidden pyglet window (Xvfb/llvmpipe);
                                #   sync() then includes the real GLRenderStore.update -> _patch_attribute
Per asset x radius x metric: plain W drag of exactly the influenced set, 200 moves, sync per move.
"""
import _setup  # noqa: F401
import argparse, math, statistics, sys, time

from loaders.assets import asset_path
from core import SelectionMode
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.mesh_geometry import mesh_center_and_radius
from soft_selection.influence import compute_influence
from soft_selection.probe_cost import pick_seeds

W = Input("key", "w")
ap = argparse.ArgumentParser(); ap.add_argument("--gl", action="store_true"); ap.add_argument("--moves", type=int, default=200)
ap.add_argument("--assets", nargs="+", default=["head_basemesh", "man_with_shoes_basemesh"])
args = ap.parse_args()

gl_kwargs, win = {}, None
if args.gl:
    import pyglet
    win = pyglet.window.Window(width=1280, height=800, visible=False)
    sys.path.insert(0, "/home/user/Mirai-Bastel/src")
    from main import GL_TYPES
    gl_kwargs = dict(GL_TYPES)

def stats(xs):
    o = sorted(xs); return statistics.median(o), o[max(0, math.ceil(0.95 * len(o)) - 1)], o[-1]

print(f"P-V {'GL (GLRenderStore, Xvfb/llvmpipe)' if args.gl else 'TraceStore'}; container, NOT the reference PC")
print(f"{'asset':24s} {'r':>4s} {'metric':9s} {'moved':>5s} | edges hidden: step+sync p50/p95 | edges shown: step+sync p50/p95"
      + (" | render p95 (llvmpipe)" if args.gl else ""))
for asset in args.assets:
    for frac in (0.05, 0.15, 0.30):
        for metric in ("euclidean", "geodesic"):
            row = []
            for edges in (False, True):
                app = Application()
                app.init_scene("obj", obj_path=asset_path(asset), **gl_kwargs)
                app.frame_scene(); app.set_viewport_size(1280, 800)
                if edges:
                    app.viewport.set_display(True, True, False)
                mesh = app.scene.mesh
                _, br = mesh_center_and_radius(mesh)
                _, seeds = pick_seeds(mesh)
                inf = compute_influence(mesh, seeds, frac * br, metric=metric, curve="smooth")
                app.selection.mode = SelectionMode.VERTEX
                app.selection.vertices = set(inf)
                app.viewport.on_selection_changed(); app.viewport.sync()
                if args.gl: app.viewport.render()
                assert app.key_press(W)
                tot, rend = [], []
                for i in range(args.moves):
                    sx = 3.0 if i < args.moves // 2 else -3.0
                    t0 = time.perf_counter()
                    app.pointer_motion(640, 400, sx, sx / 3.0)
                    app.viewport.sync()
                    t1 = time.perf_counter()
                    if args.gl:
                        app.viewport.render(); r1 = time.perf_counter(); rend.append((r1 - t1) * 1e3)
                    if i: tot.append((t1 - t0) * 1e3)
                app.key_release(W)
                row.append((len(inf), stats(tot), stats(rend) if rend else None))
            (n, a, ra), (_, b, rb) = row
            extra = f" | {ra[1]:5.2f} / {rb[1]:5.2f}" if args.gl else ""
            print(f"{asset:24s} {int(frac*100):3d}% {metric:9s} {n:5d} | {a[0]:6.2f} / {a[1]:6.2f}"
                  f"                     | {b[0]:6.2f} / {b[1]:6.2f}{extra}")
```

Output, TraceStore:

```text
P-V TraceStore; container, NOT the reference PC
asset                       r metric    moved | edges hidden: step+sync p50/p95 | edges shown: step+sync p50/p95
head_basemesh              5% euclidean     9 |   0.40 /   0.43                     |   0.41 /   0.72
head_basemesh              5% geodesic      9 |   0.27 /   0.44                     |   0.46 /   0.75
head_basemesh             15% euclidean    36 |   0.53 /   0.83                     |   0.71 /   1.11
head_basemesh             15% geodesic     30 |   0.46 /   0.61                     |   0.73 /   1.21
head_basemesh             30% euclidean    68 |   0.74 /   1.00                     |   0.90 /   1.05
head_basemesh             30% geodesic     61 |   0.75 /   1.29                     |   0.89 /   1.56
man_with_shoes_basemesh    5% euclidean    18 |   0.52 /   0.64                     |   1.02 /   1.73
man_with_shoes_basemesh    5% geodesic     10 |   0.44 /   0.71                     |   0.94 /   1.59
man_with_shoes_basemesh   15% euclidean    76 |   0.96 /   1.61                     |   1.45 /   2.12
man_with_shoes_basemesh   15% geodesic     28 |   0.68 /   0.92                     |   1.13 /   1.22
man_with_shoes_basemesh   30% euclidean   112 |   2.07 /   2.24                     |   1.75 /   2.22
man_with_shoes_basemesh   30% geodesic    107 |   1.19 /   1.41                     |   1.76 /   2.14
```

Output, GL store:

```text
P-V GL (GLRenderStore, Xvfb/llvmpipe); container, NOT the reference PC
asset                       r metric    moved | edges hidden: step+sync p50/p95 | edges shown: step+sync p50/p95 | render p95 (llvmpipe)
head_basemesh              5% euclidean     9 |   1.51 /   1.85                     |   1.86 /   3.60 |  0.48 /  1.49
head_basemesh              5% geodesic      9 |   1.55 /   2.10                     |   1.90 /   3.74 |  0.42 /  1.31
head_basemesh             15% euclidean    36 |   4.87 /  10.38                     |   9.46 /  11.36 |  0.89 /  1.62
head_basemesh             15% geodesic     30 |   5.73 /   8.95                     |  10.12 /  10.61 |  0.78 /  1.79
head_basemesh             30% euclidean    68 |   7.80 /  16.03                     |   8.84 /  16.81 |  0.82 /  1.61
head_basemesh             30% geodesic     61 |   8.61 /  14.64                     |   7.31 /  14.95 |  0.80 /  1.49
man_with_shoes_basemesh    5% euclidean    18 |   5.95 /  12.36                     |   7.25 /  13.45 |  0.95 /  2.48
man_with_shoes_basemesh    5% geodesic     10 |   3.51 /   3.89                     |   4.65 /   5.81 |  0.53 /  1.82
man_with_shoes_basemesh   15% euclidean    76 |  20.90 /  38.00                     |  23.90 /  42.61 |  0.97 /  2.78
man_with_shoes_basemesh   15% geodesic     28 |  10.44 /  13.55                     |  11.71 /  22.28 |  0.76 /  2.63
man_with_shoes_basemesh   30% euclidean   112 |  30.66 /  58.95                     |  29.82 /  61.16 |  1.03 /  2.66
man_with_shoes_basemesh   30% geodesic    107 |  27.96 /  49.24                     |  28.20 /  35.67 |  1.00 /  1.90
```

### P-V3 — where the time goes (`probe_pv_profile.py`)

```python
"""Review probe P-V3: cProfile of 100 W-drag moves (body, 30 %, euclidean, 112 moved), GL store vs TraceStore."""
import _setup  # noqa: F401
import cProfile, pstats, sys, io
import pyglet
from loaders.assets import asset_path
from core import SelectionMode
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.mesh_geometry import mesh_center_and_radius
from soft_selection.influence import compute_influence
from soft_selection.probe_cost import pick_seeds
sys.path.insert(0, "/home/user/Mirai-Bastel/src")
from main import GL_TYPES

win = pyglet.window.Window(width=1280, height=800, visible=False)
for label, kw in (("TraceStore", {}), ("GLRenderStore", dict(GL_TYPES))):
    app = Application(); app.init_scene("obj", obj_path=asset_path("man_with_shoes_basemesh"), **kw)
    app.frame_scene(); app.set_viewport_size(1280, 800)
    mesh = app.scene.mesh; _, br = mesh_center_and_radius(mesh); _, seeds = pick_seeds(mesh)
    inf = compute_influence(mesh, seeds, 0.3 * br)
    app.selection.mode = SelectionMode.VERTEX; app.selection.vertices = set(inf)
    app.viewport.on_selection_changed(); app.viewport.sync()
    app.key_press(Input("key", "w")); app.pointer_motion(640, 400, 3, 1); app.viewport.sync()
    pr = cProfile.Profile(); pr.enable()
    for i in range(100):
        app.pointer_motion(640, 400, 3, 1); app.viewport.sync()
    pr.disable()
    s = io.StringIO(); st = pstats.Stats(pr, stream=s); st.sort_stats("cumulative").print_stats(14)
    print(f"===== {label}: {len(inf)} moved, 100 moves =====")
    print("\n".join(l for l in s.getvalue().splitlines() if l.strip())[:3200])
    app.key_release(Input("key", "w"))
```

Output (cumulative-time listing, filtered to the relevant rows):

```text
===== TraceStore: 112 moved, 100 moves =====
         679601 function calls in 0.332 seconds
      100    0.000    0.000    0.305    0.003 /home/user/Mirai-Bastel/src/viewport/viewport.py:244(sync)
      100    0.028    0.000    0.294    0.003 /home/user/Mirai-Bastel/src/viewport/render_mesh.py:277(_sync_geometry)
    23200    0.040    0.000    0.067    0.000 /home/user/Mirai-Bastel/src/viewport/resource_store.py:167(update)
      100    0.000    0.000    0.027    0.000 /home/user/Mirai-Bastel/src/mirai/application.py:1558(_transform_step)
===== GLRenderStore: 112 moved, 100 moves =====
         866601 function calls in 3.358 seconds
      100    0.000    0.000    3.323    0.033 /home/user/Mirai-Bastel/src/viewport/viewport.py:244(sync)
      100    0.048    0.000    3.299    0.033 /home/user/Mirai-Bastel/src/viewport/render_mesh.py:277(_sync_geometry)
    23200    0.074    0.000    3.018    0.000 /home/user/Mirai-Bastel/src/viewport/gl_render_store.py:166(update)
    23200    2.839    0.000    2.888    0.000 /home/user/Mirai-Bastel/src/viewport/gl_render_store.py:199(_patch_attribute)
      100    0.001    0.000    0.035    0.000 /home/user/Mirai-Bastel/src/mirai/application.py:1558(_transform_step)
```

### P-V4 — slice-only `GLRenderStore.update` (`probe_pv_slice.py`; a monkeypatch, not a repo change)

```python
"""Review probe P-V4: GLRenderStore patched to write only the changed slice (scratch monkeypatch,
not a repo change). Measures body/head rows again and checks GPU-side data == CPU copy."""
import _setup  # noqa: F401
import math, statistics, sys, time
import pyglet
from loaders.assets import asset_path
from core import SelectionMode
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.mesh_geometry import mesh_center_and_radius
from soft_selection.influence import compute_influence
from soft_selection.probe_cost import pick_seeds
sys.path.insert(0, "/home/user/Mirai-Bastel/src")
from main import GL_TYPES
from viewport.gl_render_store import GLRenderStore

ORIG_UPDATE = GLRenderStore.update

def sliced_update(self, name, offset, data, nbytes):
    res = self._ensure(name)
    buf = self._cpu.setdefault(name, [])
    needed = offset + len(data)
    if len(buf) < needed:
        buf.extend([0.0] * (needed - len(buf)))
    buf[offset:offset + len(data)] = data
    res.updates += 1; res.bytes_uploaded += nbytes
    self.stats.add_upload(nbytes); self.stats.snapshot_resource(res)
    group = self._group_of(name)
    if group is None or group in self._rebuild_active:
        return
    vlist = self._vertex_lists.get(group)
    if vlist is None:
        return
    attributes, index_name = self._groups[group]
    if name == index_name:
        return
    target = getattr(vlist, attributes[name][0], None)
    if target is None:
        return
    target[offset:offset + len(data)] = data          # only the changed floats

win = pyglet.window.Window(width=1280, height=800, visible=False)

def run(asset, frac, patched, moves=200):
    GLRenderStore.update = sliced_update if patched else ORIG_UPDATE
    app = Application(); app.init_scene("obj", obj_path=asset_path(asset), **GL_TYPES)
    app.frame_scene(); app.set_viewport_size(1280, 800)
    mesh = app.scene.mesh; _, br = mesh_center_and_radius(mesh); _, seeds = pick_seeds(mesh)
    inf = compute_influence(mesh, seeds, frac * br)
    app.selection.mode = SelectionMode.VERTEX; app.selection.vertices = set(inf)
    app.viewport.on_selection_changed(); app.viewport.sync(); app.viewport.render()
    app.key_press(Input("key", "w")); xs = []
    for i in range(moves):
        sx = 3.0 if i < moves // 2 else -3.0
        t0 = time.perf_counter(); app.pointer_motion(640, 400, sx, sx / 3); app.viewport.sync()
        if i: xs.append((time.perf_counter() - t0) * 1e3)
        app.viewport.render()
    app.key_release(Input("key", "w"))
    store = app.viewport.render_mesh.store
    vl = store._vertex_lists["mesh"]
    gpu_pos = list(vl.position)[:len(store._cpu["positions"])]
    exact = all(abs(a - b) < 1e-6 for a, b in zip(gpu_pos, store._cpu["positions"]))
    o = sorted(xs)
    return len(inf), statistics.median(o), o[math.ceil(0.95 * len(o)) - 1], exact

print("P-V4 container (Xvfb/llvmpipe), NOT the reference PC; step+sync per move, ms; edges hidden")
for asset in ("head_basemesh", "man_with_shoes_basemesh"):
    for frac in (0.05, 0.30):
        n, a50, a95, _ = run(asset, frac, False)
        _, b50, b95, ok = run(asset, frac, True)
        print(f"  {asset:24s} {int(frac*100):2d}% moved {n:3d}: today p50 {a50:6.2f} p95 {a95:6.2f} | "
              f"slice-only p50 {b50:5.2f} p95 {b95:5.2f} | GPU copy == CPU copy: {ok}")
```

Output:

```text
P-V4 container (Xvfb/llvmpipe), NOT the reference PC; step+sync per move, ms; edges hidden
  head_basemesh             5% moved   9: today p50   1.67 p95   2.53 | slice-only p50  0.36 p95  0.57 | GPU copy == CPU copy: True
  head_basemesh            30% moved  68: today p50  10.49 p95  16.06 | slice-only p50  1.73 p95  1.95 | GPU copy == CPU copy: True
  man_with_shoes_basemesh   5% moved  18: today p50   6.37 p95  12.76 | slice-only p50  0.65 p95  1.02 | GPU copy == CPU copy: True
  man_with_shoes_basemesh  30% moved 112: today p50  28.72 p95  52.69 | slice-only p50  1.53 p95  2.26 | GPU copy == CPU copy: True
```

### P-B — a 4-band `GLPointOverlay`, stale every frame (`probe_bands.py`)

```python
"""Review probe P-B: cost of a 4-band GLPointOverlay subclass (H1 pattern) when every band is stale
each frame (positions follow the drag). Container, Xvfb/llvmpipe; times only the Python-side
vertex-list rebuild inside draw(), via the class's own rebuild counter + perf_counter."""
import _setup  # noqa: F401
import math, random, statistics, sys, time
import pyglet
sys.path.insert(0, "/home/user/Mirai-Bastel/src")
from viewport.gl_point_overlay import GLPointOverlay

win = pyglet.window.Window(width=640, height=480, visible=False)
BANDS = ("b0", "b1", "b2", "b3")
class Bands(GLPointOverlay):
    LAYERS = BANDS
    LAYER_STYLES = {b: ((1.0, 0.2 * i, 0.0, 1.0), 6.0) for i, b in enumerate(BANDS)}
ov = Bands()
eye = tuple(1.0 if i % 5 == 0 else 0.0 for i in range(16))
cam = eye + eye
rng = random.Random(1)
for n in (9, 68, 112):
    pts = [[(rng.random(), rng.random(), rng.random()) for _ in range(n // 4 + 1)] for _ in BANDS]
    xs = []
    for frame in range(200):
        for b, layer in zip(BANDS, pts):
            ov.set_points(b, [(x + frame * 1e-3, y, z) for x, y, z in layer])
        t0 = time.perf_counter(); ov.draw(cam); xs.append((time.perf_counter() - t0) * 1e3)
    o = sorted(xs[1:])
    print(f"  {n:3d} points in 4 bands: draw incl. 4 vertex-list rebuilds p50 {statistics.median(o):.3f} ms, "
          f"p95 {o[math.ceil(.95*len(o))-1]:.3f} ms (llvmpipe; container)")
```

Output:

```text
    9 points in 4 bands: draw incl. 4 vertex-list rebuilds p50 0.190 ms, p95 0.348 ms (llvmpipe; container)
   68 points in 4 bands: draw incl. 4 vertex-list rebuilds p50 0.222 ms, p95 0.331 ms (llvmpipe; container)
  112 points in 4 bands: draw incl. 4 vertex-list rebuilds p50 0.229 ms, p95 0.338 ms (llvmpipe; container)
```

### P-A — are sticky settings read at arm or at the first motion? (`probe_arm.py`)

```python
"""Review probe P-A (CLAUDE-001 of AD-020): when are sticky transform settings read - at arm or at
the first motion? Uses the X constraint, the precedent AD-020 §4.3/§6.1 copies for the soft settings.
Run from a repo root; with --copy the scratch copy with the placeholder Soft bindings is used."""
import sys
root = sys.argv[1] if len(sys.argv) > 1 else "/home/user/Mirai-Bastel"
for p in (root + "/src", root, root + "/examples", root + "/experiments"):
    sys.path.insert(0, p)
from mirai.application import Application
from mirai.interaction.input import Input
from core import SelectionMode
from symmetry_lab.run import build_app_lab
from symmetry_lab.lab_app import lab_key_press, BLOCK_NOT_ALLOWED_TEXT

W, X, SHIFT_S, SHIFT_B, O = (Input("key", "w"), Input("key", "x"), Input("key", "s", frozenset({"shift"})),
                             Input("key", "b", frozenset({"shift"})), Input("key", "o"))

print("== 1. src/main.py path (Application, cube): W arm -> X -> first motion ==")
app = Application(); app.init_scene("cube"); app.frame_scene(); app.set_viewport_size(800, 600)
app.selection.mode = SelectionMode.VERTEX; app.selection.vertices = {app.scene.mesh.all_vertex_ids()[0]}
print("  W armed:", app.key_press(W), "| axis_constraint at arm:", app.axis_constraint)
print("  X while armed (not begun):", app.key_press(X), "| interaction_owner:", app.interaction_owner)
app.pointer_motion(400, 300, 5, 0)
print("  first motion -> transform_space of THIS gesture:", app.transform_space)
app.key_release(W)

print("== 2. Symmetry Lab, symmetry X, BLOCK: W arm -> X -> first motion ==")
app, lab = build_app_lab("subd_cube", 800, 600)
lab_key_press(app, lab, SHIFT_S)
print("  lab axis:", lab.axis, "| gate mode:", lab.gate_mode.value)
v = app.scene.mesh.all_vertex_ids()[0]
app.selection.mode = SelectionMode.VERTEX; app.selection.vertices = {v}
print("  W armed (BLOCK lets Move through):", lab_key_press(app, lab, W))
print("  X while armed (NON_OPERATION):", lab_key_press(app, lab, X), "| status:", app.status_message)
app.pointer_motion(400, 300, 5, 0)
print("  first motion -> transform_space:", app.transform_space, "| begun:", app.transform_interacting)
lab_key_press(app, lab, X)  # toggle back off
app.key_release(W)

if "--copy" in sys.argv:
    print("== 3. scratch copy with placeholder O binding: O under BLOCK / MARK (not in NON_OPERATION) ==")
    app, lab = build_app_lab("subd_cube", 800, 600)
    lab_key_press(app, lab, SHIFT_S)
    r = lab_key_press(app, lab, O)
    print("  BLOCK: O ->", r, "| status:", app.status_message, "| == BLOCK text:", app.status_message == BLOCK_NOT_ALLOWED_TEXT)
    lab_key_press(app, lab, SHIFT_B)
    s = app.status_serial
    r = lab_key_press(app, lab, O)
    print("  after Shift+B (MARK): gate", app.command_gate, "| O reaches Application:", app.status_serial == s,
          "(no handler in the probe, so False)", r)
```

Output at `0f079bd`:

```text
== 1. src/main.py path (Application, cube): W arm -> X -> first motion ==
  W armed: True | axis_constraint at arm: None
  X while armed (not begun): True | interaction_owner: transform
  first motion -> transform_space of THIS gesture: x
== 2. Symmetry Lab, symmetry X, BLOCK: W arm -> X -> first motion ==
  lab axis: X | gate mode: BLOCK
  W armed (BLOCK lets Move through): True
  X while armed (NON_OPERATION): True | status: Constraint: X
  first motion -> transform_space: x | begun: True
```

Output of section 3, run on the P-K copy without the `NON_OPERATION` addition (`python probe_arm.py <copy> --copy`):

```text
== 3. scratch copy with placeholder O binding: O under BLOCK / MARK (not in NON_OPERATION) ==
  BLOCK: O -> False | status: Symmetrie aktiv — Befehl nicht koordiniert (BLOCK: nicht gestartet) | == BLOCK text: True
  after Shift+B (MARK): gate None | O reaches Application: True (no handler in the probe, so False) False
```

### P-K — placeholder Soft commands and bindings (the brief's key probe)

A `git archive 0f079bd` export, patched as follows. Five commands, not four: Up and Down need two (F12). The `lab_app.py` hunk applies to run 2 only.

```diff
--- a/src/mirai/interaction/commands.py
+++ b/src/mirai/interaction/commands.py
@@ -106,4 +106,10 @@
 EXTRUDE = "Extrude"
 
 # --- Articulation (EX-A / H02) -----------------------------------------------
-ARTICULATION_RESTORE = "ArticulationRestore"
\ No newline at end of file
+ARTICULATION_RESTORE = "ArticulationRestore"
+# --- REVIEW PROBE (CLAUDE-001 of AD-020): placeholder Soft Selection commands -----
+SOFT_TOGGLE = "SoftToggle"
+SOFT_RADIUS_UP = "SoftRadiusUp"
+SOFT_RADIUS_DOWN = "SoftRadiusDown"
+SOFT_CURVE = "SoftCurve"
+SOFT_METRIC = "SoftMetric"
--- a/src/mirai/interaction/bindings.py
+++ b/src/mirai/interaction/bindings.py
@@ -146,6 +146,12 @@
     bs.set_default(_key("delete"), cmd.DELETE)
     bs.set_default(_key("backspace"), cmd.DISSOLVE)
     bs.set_default(_key("backspace", "ctrl"), cmd.DISSOLVE_NO_CLEANUP)
+    # REVIEW PROBE: AD-020 §6.1 proposal
+    bs.set_default(_key("o"), cmd.SOFT_TOGGLE)
+    bs.set_default(_key("up"), cmd.SOFT_RADIUS_UP)
+    bs.set_default(_key("down"), cmd.SOFT_RADIUS_DOWN)
+    bs.set_default(_key("o", "shift"), cmd.SOFT_CURVE)
+    bs.set_default(_key("o", "ctrl"), cmd.SOFT_METRIC)
 
     # --- Knife session (WP-06 B7, AD-017; context "knife") ------------------
     # Artist Input Truth `topology.knife_commit` (Enter); Ctrl+Shift+Z is the
--- a/experiments/symmetry_lab/lab_app.py
+++ b/experiments/symmetry_lab/lab_app.py (run 2 only)
@@ -166,6 +166,12 @@
         cmd.ZOOM,
         cmd.KNIFE_COMMIT,
         cmd.KNIFE_LIFT,
+        # REVIEW PROBE: soft settings (AD-020 §2.1)
+        cmd.SOFT_TOGGLE,
+        cmd.SOFT_RADIUS_UP,
+        cmd.SOFT_RADIUS_DOWN,
+        cmd.SOFT_CURVE,
+        cmd.SOFT_METRIC,
     }
 )
 
```

Results (`xvfb-run -a python -m pytest …` in the copy):

```text
run 1  experiments/symmetry_lab/tests, bindings, NON_OPERATION unchanged : 476 passed, 4 skipped
       (baseline 466 + 10 new T-FC1 parametrisations: 5 x refused-under-BLOCK, 5 x silent-without-symmetry)
run 2  experiments/symmetry_lab/tests, bindings + NON_OPERATION addition : 466 passed, 4 skipped
run 3  tests (Production), bindings                                      : 2 failed, 2318 passed, 6 skipped, 68 subtests passed
       FAILED tests/test_display_modes.py::test_bare_d_cycles_and_o_is_unbound
       FAILED tests/test_input_binding.py::DefaultBindingsTests::test_display_keys
       (both assert command_for(key 'o') is None; the second is commented
        'WP-06 B5a (E42): Artist Input Truth - D statt O')
```

---

## Kurzfassung für Manu (Deutsch)

**Verdikt: ACCEPT WITH CHANGES, zwei Blocker.** Die Richtung stimmt: Soft Selection im normalen Programm, standardmäßig aus; kein Eingriff in den Core; Punkte in Farbbändern; eine Messung vor deinem Praxistest. Die Core-Lösung D habe ich nachgebaut: Sie rechnet bitgleich wie das Experiment und bei Radius 0 wie der Core.

1. **Blocker Messung:** Die Messung im AD lässt den teuersten Teil des echten Fensters weg. Der Grafikpuffer wird bei jedem bewegten Vertex komplett neu kopiert. Im Container kostet eine Mausbewegung am Körper (112 Vertices) damit ~31 ms statt ~2 ms, auf deinem PC vermutlich deutlich mehr (geschätzt, nicht gemessen). Das betrifft heute schon jeden größeren W-Drag. Ein kleiner Viewport-Fix (nur die geänderten Werte schreiben) bringt es im Container auf ~1,5 ms. Er gehört vor den Praxistest, und die Messung muss mit dem echten Grafikteil laufen.
2. **Blocker Symmetrie:** Die Ablehnung „Soft + Symmetrie“ greift nur beim Drücken von W. Mit W drücken, dann O, dann Maus bewegen umgeht man sie. Sie muss beim Start der Geste greifen.
3. **Taste O:** Sie ist heute frei, aber O war früher die Anzeige-Taste und wurde mit deiner Entscheidung „D statt O“ bewusst freigemacht. Zwei Tests halten das fest.

**Was du entscheidest:**

- (a) Darf Soft Selection für S2 ins normale Programm, standardmäßig aus, mit vorläufigen Tasten? Ja oder nein. Das ist die ausdrückliche Entscheidung, die AD-013 verlangt.
- (b) O trotzdem, oder eine andere Taste?
- (c) Den Viewport-Fix als eigenen kleinen Schritt vor dem S2-Praxistest? Ja oder nein.
