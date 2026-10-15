# Independent Review — AD-021 "Object / Component Model (ARCH-01)" (PROPOSED)

> **Reviewer:** Claude (fresh context, no prior chat or plan context)
> **Review ID:** CLAUDE-001
> **Target path:** `docs/archive/object_model/reviews/AD-021_REVIEW_CLAUDE_001.md`
> **Repository state reviewed:** `ccr-0fd57631-0t6li6` @ `6a1669c`
> **Subject:** `docs/architecture/AD-021-OBJECT-COMPONENT-MODEL.md` (PROPOSED, 2026-10-15)
> **Type / Mode:** review only · Architecture Gate · no source, test, experiment, Playground file or AD edited
> **Status:** Archived first-pass review — preserved verbatim
>
> This document is intentionally preserved as the original independent review. Do not edit it to
> reflect later decisions. Answers to the findings belong in the AD's §9 "Review".

---

## What was read, what was run

**Read:** `AGENTS.md`, `CLAUDE.md`, AD-021 in full; `src/core/{scene,selection,serialization,history,ids,operation}.py`,
`mesh.py` (header, allocators, `export_state`/`load_state`), `operations/topology.py` (`MeshStateCommand`),
`operations/transform.py` (`VertexTransformCommand`); `src/mirai/application.py` (`init_scene`, `load_scene`,
`frame_scene`, `_set_selection_mode`, `_undo_redo`, `_apply_undo_redo`, `_mesh_transaction`, selection snapshot/restore,
`_prune_ghost_selection`, `_set_hovered`, `_active_selection_contains`, `_soft_refresh_radius`), `scene_factory.py`,
`symmetry_axis.py`, `soft_selection/settings.py`, `interaction/tools/move.py`, `topology/contextual_c.py`;
`src/viewport/{viewport,overlay,gl_render_store}.py`; `playground/app.py` (scene swaps); V1_SPEC §2/§3/§4/§8–§12/§15;
AD-SYM-01 §2–§4, AD-SYM-02 §3, AD-SYM-04 (E1 wording), AD-SYM-05 §3.1, AD-020 E3, AD-012, AD-014 (headline),
CORE_V1_FREEZE §7, CORE_V1_REVIEW §12, ROADMAP ARCH-01, the `6a1669c` doc diff (ATELIER, README, ROADMAP).

**Run:**
- `git diff --stat 63bcf65 6a1669c`: only four doc files changed, so all `src/` line numbers read "at `63bcf65`" are
  valid at `6a1669c`.
- Both scratch probes re-run: P-1 prints the claimed result; P-2 prints exactly "145 of 145", "30 of 145", worst
  `8.881784197001252e-16`, "20 of 36". I wrote a stricter P-1 (full `export_state()` comparison per step): undo/redo
  restore both meshes exactly **except the ID counters, which stay forward** (`vertex_id_counter` 9 vs. 8 after undo) —
  correct AD-001 behaviour, so P-1 holds; the AD could say so.
- F-9 recount (`grep -rn` lines / `grep -rno` occurrences / assignment lines): `src` 59/59/5, `tests` 725/731/13,
  `playground` 292/298/13, `experiments` 275/282/10, Symmetry Lab 196/197/1; per-file split matches the table.
- **Prototype of §5.1/§5.2 in a scratch copy** (not in the repo): `ObjectId`, `SceneObject`, `Scene.objects`,
  `Scene()` creating one object that is `selection.edit_object`, `Scene.mesh` as get/set property, `Selection.objects`
  + `edit_object`, `clear()` clearing `objects`. Baseline (unmodified copy, `xvfb-run -a pytest tests playground/tests
  experiments/symmetry_lab/tests`): 4266 passed, 114 skipped. Prototype: see the result line under Q6.
- A v2 `serialization.py` prototype per §5.3 (with the v1 read branch): exactly two tests fail —
  `test_scene_serialization.py::…::test_reserved_subsystem_slots_present_and_null_in_v1` and
  `test_core.py::test_ad001_serialization_roundtrip` (both assert a `"mesh"` key); the other 27 pass.

---

## Verdict: **ACCEPT WITH CHANGES**

Option B (thin `SceneObject` owning one `Mesh`; placement and role on the Object; edit target in the Selection) is the
right direction, and the AD's central evidence holds: History is already object-agnostic (P-1 reproduced), Core
operations never read `Scene`, the Mesh/Object placement test from AD-SYM-01 is applied consistently, and object-space
computation is the only way to keep E3/E4 exactness (P-2 reproduced). The `Scene.mesh` accessor really is free for the
existing call sites (prototype). But the AD should not go to Manu as is: the freeze step-2 argument rests on a
strawman Option A (R-1), the Selection extension is under-specified in a way that collides with today's mode-key
behaviour and with the Q-5 recommendation (R-2), and three Artist-relevant consequences are hidden in engineering text
(E1 re-interpretation R-6, the Q-4 dependency R-7, Undo switching the edit object R-8). None changes the target
model; R-1 may change the staging (App-first for M1, Core at the first save). All are text-level fixes before the
decision.

---

## Answers to the review questions

### 1. Are the facts (§1) correct?

Checked and correct: F-1 (`scene.py:24-34`); F-2 (`mesh.py:103-105`; the type check is `application.py:2471`, `:2470`
is its comment); F-3 except the line range (`clear()` is `selection.py:67-70`, not 66-69) — `SelectionMode.OBJECT` is
unused in `src/` and `playground/` (only `tests/test_overlay.py:72`); F-4 (`history.py:29-40`, `topology.py:49-53`,
`transform.py:220-226`, `operation.py:73`, no `scene` in `core/operations` or `operation.py`); F-5 (`:616`, `:623`,
`:631-638`, `:2218`, `:2122-2131`, `:2248-2258`); F-6 (`gl_render_store.py:48-49`, `move.py:268`); F-8 (only the two
test files call the serializers; the app never saves); F-10 (`CORE_V1_REVIEW.md:361-371`, `mesh.py:14-17`, AD-018,
SUBDIVISION D8).

Inaccurate or missing, with effect on the conclusion:
- **F-7 drops the word "world".** `symmetry_axis.py:8-9` defines E1 as "Ebene immer durch den **Welt**-Ursprung, Normale
  exakt eine **Welt**achse". §4.8 silently re-defines E1 in object space (R-6). Does not change the choice of object
  space, but changes what Manu is told.
- **F-9 counts lines, labelled "occurrences"**, and `tests/` includes `tests/_archive`. The sentence "there is no site
  that means all meshes" is contradicted by the AD itself (E-4 `frame_scene`) and by the Viewport construction at
  `:631-632`, which under M1 means "what to draw" (R-13). Immaterial to the cost estimate.
- **Missing: mode 4 is unwired, not just unused.** `Selection._active_set()` maps `OBJECT` to a throw-away `set()`
  (`selection.py:42-47`), so `set/add/toggle` are silent no-ops in mode 4; `_active_selection_contains` indexes a
  V/E/F-only dict and raises `KeyError` in mode 4 (`application.py:239-247`); `_MODE_COMMANDS` has no mode-4 entry
  (`:217-221`); `_set_selection_mode` clears the whole selection on every `1/2/3` press (`:801-802`). This feeds R-2.
- **Missing: the Viewport is single-mesh and carries the Selection overlay** (`viewport.py:105-118`); the playground
  builds viewports with `selection=scene.selection` (`playground/app.py:127-204`). Feeds R-5.
- **Missing: scene loads use the `scene.mesh` setter** (`application.py:616/623`, `playground/app.py`, `lab_scene.py:43`).
  Feeds R-4.

### 2. Is the option comparison (§3) fair? Better option? Cost right?

B vs. C vs. D is fair; D's rejection (placement in the Mesh snapshot, lost on swap, mirrors AD-SYM-01's own argument)
is sound, and C is correctly ruled out by V1_SPEC §12 and CORE_V1_REVIEW §12. **Option A is a strawman** (R-1): it is
defined as "no Object concept", so it fails A-2/A-3. An option **A′ — the same thin object table in `src/mirai`,
with `scene.mesh` re-assigned to the edit object's Mesh on an edit-object change** — is not considered. It satisfies
A-1, A-2 and, until a file format exists, A-3/A-5, with zero Core change: the app already swaps `scene.mesh`
(`:616/623`), AD-SYM-01 swap semantics carry the symmetry definition, commands hold their own instances (P-1), and the
app does not persist anything (F-8). A′ is probably still worse than B (a second scene model outside Core, `Scene`
silently stays "exactly one Mesh" — the CORE_V1_REVIEW §12 warning — and it must be replaced at the first save), but
CORE_V1_FREEZE §7 step 2 asks exactly this question and §5's "(2) not solvable without a Core change" is not true as
written.

Cost: the `scene.mesh` figures are right (recount above) and the "0 forced edits" claim is confirmed by the prototype.
The Core-surface estimate for `selection.py` ("two fields") is low: `_active_set()`, `clear()` and `is_empty()`
semantics all change or must be pinned (R-2). Serialization cost "two test files adapt" is confirmed (two tests).

### 3. Do §4's answers cover the questions? Conflicts?

Coverage: all seven ROADMAP questions (§4.1, §4.2, §4.3, §4.4, §4.5, §4.6, §4.9), Reference placement (§4.7, with a
four-way comparison) and computation space (§4.8) are answered. ROADMAP also names **animation** as a driver; object
transform animation (keyable `transform`, `Scene.animation`) is not mentioned — one sentence in §4.9 would close it.

Consistency with DECIDED documents:
- AD-001/AD-003, V1_SPEC §3/§8/§10/§15: consistent. The composite command is not a "Cross-Subsystem-Transaktion"
  in the V1_SPEC §10 sense; fine.
- AD-SYM-01: consistent per object. But AD-SYM-01 §2.1 counted a composite command as "neue Architektur"; AD-021
  introduces the first one (Apply transform) and should say so (R-15).
- AD-SYM-02 §3 point 1: N-2 correctly flags the later amendment.
- AD-SYM-04 E1: **re-interpreted without saying so** (R-6).
- AD-SYM-05 §3.1, AD-020 E3: consistent; the "rename `world_radius`" is right, but an edit-object change becomes a
  fourth radius event (R-12).
- AD-012: consistent (local = object axes). AD-014 is cited but unused although its basis parameter is what makes a
  world-axis scale on a rotated object expressible in object space (R-16).
- V1_SPEC §12 / `serialization.py:5-9` ("erweitert, nicht migriert"): v2 with a one-`if` v1 branch is defensible, but
  it is a migration; V1_SPEC §12's example and the docstring must be updated in M0 (R-15).
- Internal: §4.4 (`clear()` leaves `edit_object`) and §5.1 (`clear()` clears all four sets) together with Q-5
  ("the object selected in mode 4 becomes the edit object when you press `1/2/3`") contradict today's mode-key path,
  which calls `clear()` on that very key press (R-2).

### 4. Are A-4 and A-3 really unblocked?

Mostly yes. N-1 and N-2 hold (verified). Hidden blockers or traps, none fatal:
- **Selection shape:** `edit_object` + bare sets is the one-key case of a keyed map — fine, *if* `clear()`/`is_empty()`
  are pinned to components (R-2); otherwise `contextual_c.py:28` (`is_empty()` → Knife) changes meaning as soon as an
  object is selected.
- **`Scene.mesh` reads `Selection.edit_object`:** the Core accessor depends on transient, unpersisted session state;
  after `scene_from_dict` the edit object is unspecified (R-3). Not a blocker for A-4, but A-4 would turn the accessor
  into a hazard if left undefined.
- **Hover typing:** safe — every hover consumer in `src/` uses `isinstance` per type (`overlay.py:171-181,204,230,245`;
  `application.py:2299-2304`) and `_set_hovered` compares types; nothing tests `isinstance(…, ElementId)`, so E-3 is free.
- **Undo refresh / mirror stack:** object commands must also push mirror entries or the one-mirror-per-push invariant
  (`application.py:2136-2173`, desync fallback = prune only) breaks; pruning must drop dead `ObjectId`s (R-9).
- **Picking, symmetry overlay, soft radius:** covered by L-5 / §5.4 M2 / R-12.
- **Rendering:** a Reference drawn via a second `Viewport` sharing `scene.selection` highlights its own elements whose
  integer IDs equal the edit object's selection/hover (F-2) — RF-2's "structural" argument covers Core ops only (R-5).
- **Per-object transforms (A-3):** unblocked; eyes/jaw need a parent later — additive, and uniform-only scale keeps
  composition a similarity (R-7).

### 5. A-5 handling and the Max "Reset XForm" reasoning

L-1…L-5 are sound and testable; L-2/L-3 are exactly the guarantees a Max user lacks. Gaps: (a) "uniform scale" must be
**positive** — a negative uniform factor is a point reflection (det < 0: winding/normals flip), which is the other
classic Reset-XForm trigger (mirror tool); (b) the strongest Reset-XForm argument is missing: with a hierarchy,
non-uniform parent scale plus a rotated child produces shear that no TRS can represent — similarities compose to
similarities, so uniform-only keeps the later `parent` field additive; (c) uniform-only is **load-bearing for L-5**:
under non-uniform scale a world rotation conjugated into object space (`S⁻¹ R S`) is not a rotation, so
`RotateOperation` (and axis scale via the AD-014 basis) could no longer be fed "unchanged" — Q-4 must tell Manu that
"no" means a Core-operation change, not just a UI change (R-7). The Max description itself ("rotation becomes a
shear, normals skew, the user cannot see which level holds the distortion") is correct in substance.
Naming: "Reset transform" in L-3 will be read by a Max user as Reset XForm, which *bakes* (= the AD's "Apply") — R-10.

### 6. Smallest Core change? Migration realistic?

Smallest that works: yes, given B — no `Mesh`, `Operation`, `OperationContext`, `HistoryStack` or command change is
needed (prototype confirms). It is under-specified in `selection.py` (R-2) and in where `edit_object` lives (R-3).
M0 acceptance "no existing test edited except the two serialization files": **realistic** — see the prototype result:

**Prototype result:** PROTOTYPE_RESULT_PLACEHOLDER

Construction patterns checked: 33 `Scene()` constructions and the 41 `scene.mesh = …` assignment lines (F-9; those
in the three test trees and `src/` all pass through the setter in the prototype), no `scene.selection` re-assignment outside `tests/_archive`, no subclassing/`vars()`/`deepcopy` of `Scene`; tests that use
the app's selection mirror compare snapshots by equality (`test_application_delete_dissolve.py:110-114,369-383`) or
by length, so M1's wider snapshot tuple is also low-risk. M1/M2 have no test budget stated; M1 will touch the mode-4
wiring (`_MODE_COMMANDS`, `_active_selection_contains`) and the 7 test files that inspect the mirror stack only if
their equality assumptions change.

### 7. Artist questions and the German summary

Q-1…Q-3 are the right M1 questions and answerable as phrased. Q-4 needs its consequence (R-7). Hidden Artist decisions
(R-8): "Undo returns to the object a step was made in" (§4.4) means **Undo can switch the edit object** — that is
Artist UX; E-4 (frame edit object vs. all) is Artist UX filed as engineering; the M1 gesture for *adding* an object
(vs. today's "load scene", which replaces) is not asked; and the symmetry plane rotating with the object (R-6).
The German summary restates A-1…A-5 faithfully (only additions: the `gollum.obj` example and "darf nicht verbaut
werden", both faithful). It overstates once: "Das Mesh selbst bleibt unverändert, ebenso Undo und alle Werkzeuge" —
tools gain the world→object input conversion in M2 (L-5; e.g. the anchor at `move.py:268` must be mapped to world first),
and the app's Undo refresh changes (§4.6) (R-11).

---

## Findings

| ID | Sev. | Finding (evidence) | Proposed fix |
|---|---|---|---|
| R-1 | major | Option A is defined so it must fail; an App-only thin object table (A′: objects in `src/mirai`, `scene.mesh` re-assigned on edit-object change) is not compared, so §5 "(2) not solvable without a Core change" (CORE_V1_FREEZE §7 step 2) is not shown. Evidence: `scene.py:26` plain attribute; app already swaps it (`application.py:616,623`); commands hold their instances (P-1); app persists nothing (F-8). | Add A′ to §3 with honest cost (no Core change for M1; second scene model outside Core; `Scene` stays one-Mesh contrary to CORE_V1_REVIEW §12; replaced at first save). Restate step 2 as "solvable short-term in the App, rejected because …" — or choose A′ for M1 and defer M0. |
| R-2 | major | Selection extension under-specified and inconsistent with Q-5: `_active_set()` sends `OBJECT` to a throw-away set (`selection.py:42-47`); §5.1 `clear()` also clears `objects`, but `_set_selection_mode` calls `clear()` on every `1/2/3` press (`application.py:801-802`) — the very press Q-5 uses to promote the selected object; `is_empty()` (`selection.py:72-73`) drives C→Knife (`contextual_c.py:28`) and playground selector logic. | In §5.1: `_active_set` maps `OBJECT`→`objects`; `clear()` = component sets only (separate `clear_objects()` or mode-scoped clear); `is_empty()` stays component-only; state the Q-5 order (read `objects` before clearing). |
| R-3 | medium | `Scene.mesh` (Core) reads `Selection.edit_object` (transient, not serialized, V1_SPEC §3); after `scene_from_dict` the edit object is undefined; a standalone `Selection()` has `None`. | Either keep the edit/active object on `Scene` (persisted, like Blender's active object) or define "first NORMAL object on load" in §5.3 and make the getter fail loudly on `None`. |
| R-4 | medium | The setter keeps other objects: `init_scene`/`load_scene` (`application.py:616,623,670-722`), `playground/app.py:127-204`, `lab_scene.py:43` mean "new scene" but would become "replace the edit object's Mesh"; `load_scene` would keep a Reference whose Add step its history reset drops. F-9's "same meaning" holds for reads only. | List the assignment sites with their intended meaning; M1 routes scene loads through an explicit scene reset, the setter is reserved for "swap this object's Mesh". |
| R-5 | medium | RF-2 ("invisible to every component path… structural") covers Core ops only. A Reference drawn with the existing single-mesh `Viewport` and the shared Selection (`viewport.py:105-118`, playground pattern) highlights elements whose IDs collide with the edit object's (F-2). | Extend RF-2/§5.4 M1: Reference render entries get no Selection (or overlays filter by `edit_object`); add an M1 test. |
| R-6 | medium | §4.8 re-defines E1 from world to object origin/axes (`symmetry_axis.py:8-9` "Welt-Ursprung … Weltachse"; AD-SYM-04 Q-1 = E-1 decided by Manu); F-7 omits "world". Artist-visible: the plane rotates with the object. | Say it explicitly as an amendment of E1 (identical while transform = identity), add one line to the Kurzfassung for confirmation, list AD-SYM-04/`symmetry_axis.py` docstring updates for M2. |
| R-7 | medium | Transform shape lacks `s > 0` (negative uniform scale mirrors, flips winding); uniform-only is load-bearing for L-5 "Core operations unchanged" (`S⁻¹RS` is no rotation; axis scale needs a non-orthogonal basis beyond AD-014); hierarchy/shear argument missing. | Write "uniform scale, s > 0"; add both arguments to §4.3; Q-4 states what "no" costs (Core-op change, new AD). |
| R-8 | medium | Artist decisions hidden in engineering text: Undo switching the edit object (§4.4 `PROVISIONAL`), E-4 framing scope, the M1 gesture for *adding* an object vs. loading. | Move to §7.1 (tagged M1/M2) or name them as explicit assumptions of the M1 practical test. |
| R-9 | minor | Mirror invariant: one mirror entry per `history.push()` (`application.py:2136-2173`); object commands (§4.6) must push one too; undo of "Add object" can leave a dead `ObjectId` in `objects`/`edit_object`. "object commands name their object" is vague. | Rule: every push records a mirror entry incl. `objects`/`edit_object`; pruning drops dead `ObjectId`s; define undo of Add when that object is the edit object. |
| R-10 | minor | "Reset transform" (L-3) collides with Max "Reset XForm", which bakes (= AD's Apply). | Rename "Clear transform"; Kurzfassung: "Transform übernehmen (wie Reset XForm)" vs. "zurücksetzen (Objekt springt)". |
| R-11 | minor | Kurzfassung: "Das Mesh selbst bleibt unverändert, ebenso Undo und alle Werkzeuge" overstates (L-5 input conversion; §4.6 Undo refresh). | "Die Werkzeuge rechnen wie bisher; nur die Eingabe wird umgerechnet." |
| R-12 | minor | Edit-object change is a new soft-radius event (`_soft_refresh_radius`, `application.py:1845-1849`, "the one place"); §4.8 only renames. | Add to §4.8/§5.4. |
| R-13 | minor | F-9 counts lines, not occurrences (tests 725/731, playground 292/298, experiments 275/282), includes `tests/_archive`; "no site means all meshes" contradicted by `:631-632` and E-4. | Relabel; qualify the sentence. |
| R-14 | nit | Line cites: `clear()` is `selection.py:67-70`; type check `:2471`. "Answers AR-12" overclaims — islands inside one Mesh stay open (AD-SYM-01 §4). P-1 should note that ID counters stay forward. | Correct cites; "answers the object-vs-mesh part of AR-12". |
| R-15 | nit | First composite command (AD-SYM-01 §2.1 counted one as new architecture); v2 contradicts `serialization.py:5-9` "erweitert, nicht migriert" and V1_SPEC §12's example. | Acknowledge both; update V1_SPEC §12 and the docstring in M0 (same-commit rule). |
| R-16 | nit | AD-014 cited, never used; ROADMAP's "animation" driver not addressed. | One sentence each in §4.3/L-5 and §4.9. |
