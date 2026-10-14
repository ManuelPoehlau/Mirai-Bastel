# AD-SYM-04 — Symmetry in the Production app (`src/main.py`), then symmetric Soft Selection

**Status:** **PROPOSED** (2026-10-14). A decision proposal plus slice plans, nothing more. An independent review in a fresh
session comes first (§9), then Manu decides. Nothing here is decided except what §0 quotes as already decided.
**Mode (M5):** Type C (Architecture Gate), decision preparation. Documents only: no change under `src/` or `experiments/`.
**Work package:** WP-SYM-APP-01 (decision package).
**Read at:** `main` @ `54de6ee`. Line numbers refer to that commit.
**Basis (binding, only linked):** [AD-013](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md) (Addendum H2: H2-R1 … H2-R6, and the
G-2 amendment of 2026-10-08), [AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md),
[AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md), [AD-SYM-03](AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md),
[AD-020](AD-020-SOFT-SELECTION-APP-PATH.md) (§8, "Promotion decision"), [WP-SYM-LAB-03 plan](WP-SYM-LAB-03_REBASE_PLAN.md),
[WP-06 intake log](WP-06_INTAKE_LOG.md) (frozen), [ROADMAP](ROADMAP.md) §7/§14,
[Symmetry Lab README](../../experiments/symmetry_lab/README.md), [REFERENCE_HARDWARE](REFERENCE_HARDWARE.md),
[CORE_V1_FREEZE](CORE_V1_FREEZE.md).

**Evidence tags.** **[Code]** read at `54de6ee` (file:line). **[Doc]** quoted from a repo document. **(Assumption)** not
confirmed by Manu. **(Reading)** an interpretation or derivation, not a measurement. `PROVISIONAL` marks every agent-set choice.

---

## 0. What this document rests on

### 0.1 Decided (as given in the handoff; not re-decided here)

**Artist (Manu, 2026-10-14):**

| # | Decision |
|---|---|
| M-1 | Symmetry must be available in `src/main.py`. |
| M-2 | Symmetric Extrude counts as **KEEP**. *(Recorded in the Lab README, "Slice 7", commit `0f8fb04`; the WP-06 intake log is frozen and gets no entry.)* |
| M-3 | Order: symmetric Soft Selection next, then both into the app together; Playground tools afterwards. |
| M-4 | **Way B:** Symmetry enters the app first; symmetric Soft is built on the app path, not in the Lab. |
| M-5 | Soft Selection is a fixed capability; the weighting moves into the Core only together with symmetric Soft ("Core opened once", Manu 2026-10-11; AD-020 "Promotion decision"). |
| M-6 | Supersedes the decision "Symmetry stays in the Lab" (intake log, 2026-10-02). |

**Engineering (set in the handoff, may be challenged):** this package delivers documents only.

M-1 is the explicit capability-promotion decision AD-013 asks for ("Eine Production-Promotion erfolgt erst durch eine
explizite Entscheidung", § Canonical Product Truth). By AD-013 A5/I7 it promotes **the capability, not the Lab's keys, HUD
or gate UX**. How symmetry is switched and shown in the app is therefore open and `PROVISIONAL` (§3).

### 0.2 Reading of the order (Assumption, for Manu to correct in one sentence)

M-3 and M-4 together are read as: (1) the app gets a way to set and show a symmetry definition (slices A0–A2, §6);
(2) symmetric Soft is built on that app path (slices SS0–SS3, §5); (3) **one** joint Artist practical test of symmetric
Extrude and symmetric Soft in the app (slice J, §7). A1/A2 land before the joint test; Manu may smoke-check them but the
verdict session is the joint one.

### 0.3 Unconfirmed assumptions (marked, not decided)

- **UA-1** — how symmetry is toggled and shown in the app. Options with costs in §3; Manu picks (questions Q-1, Q-2).
- **UA-2** — whether the Lab's E5 gate (MARK/BLOCK, Shift+B) stays Lab-only. This proposal assumes **yes** and gives the
  app fail-closed behaviour by a test instead of a runtime gate (§3.3, question Q-3).
- **UA-3** — Re-Symmetrize (M) and the topological pairing stay Lab research (`lab_topology.py` calls itself "Lab-Experiment,
  keine Capability"). Not part of M-1 unless Manu says so.

---

## 1. Inventory (Task 1)

Facts only, two lines per item.

### 1.1 Already in `src/` and serving symmetry today

| # | Item | Fact |
|---|---|---|
| I-1 | Definition storage | `Mesh.symmetry_definition: SymmetryDefinition \| None` (plane point, unit normal, seam edge ids; `core/mesh.py:74`, `:121`). Part of `export_state()`/`load_state()` (`:1098`, `:1163`), so Undo/Redo restore it (AD-SYM-01). |
| I-2 | Scene change drops it | `init_scene`/`load_scene` replace the mesh and reset history (`application.py:629-680`), so a definition never survives into another scene (AD-SYM-01 condition 3). |
| I-3 | Correspondence and state | `mirai.symmetry`: `vertex_correspondence` (exact positions, no tolerance, whole mesh per call, `symmetry.py:118`), `symmetry_state`, `mirrored_selection`. |
| I-4 | Coordination | `symmetry_coordination` (`SymmetryIndex`, canonical/expand, seam rules S1–S3, completeness/delta) and the coordinators in `symmetric_ops`, `symmetric_knife`, `symmetric_extrude`. |
| I-5 | Declarations (D-b) | `symmetry_declarations`: all four `C` contexts, the three removal commands, `Extrude` (`symmetry_declarations.py:55-93`). Static tables, read at every call, no gate data. |
| I-6 | Transforms | `MoveTool`/`TransformTool` resolve partners and seam vertices from the mesh's definition (`tools/move.py:202-216`, `tools/transform.py:362`, `selection_helpers.resolve_symmetry`); per-side pivot `symmetric_default_pivot` (`selection_helpers.py:90`, Artist B, 2026-10-03). |
| I-7 | Topology in `Application` | `_connect_command` (canonicalise + coordinator, `application.py:874-890`), `_removal_command` (`:913-977`), `_knife_begin` (`:1073-1092`), `_extrude_begin` (`:1928-1954`) all switch on `mesh.symmetry_definition is not None` — no gate needed, "in MARK as in BLOCK". |
| I-8 | Soft + symmetry | Refused visibly at arm (`:1652`) and authoritatively at `begin()` (`:1715`); bands hidden while a definition is set (`:1856`); soft ops raise on `params["symmetry"]` (`soft_selection/ops.py:63-75`). |
| I-9 | Host hooks (H1–H4) | `Viewport.add_overlay`, `Application.apply_mesh_change` (`:2087`), `set_status` (`:2234`), `command_gate` + `refused_contexts` (`:419`, `:2222`, `:897`), `hover_suspended`, `interaction_owner` (`:1522`). All inert by default. |
| I-10 | Knife mirror variants | `V` cycles V-a/V-b/V-c inside a symmetric Knife session, hard-coded, not a binding (`KNIFE_MIRROR_VARIANT_KEY`, `:277`). |
| I-11 | Refusal texts name a Lab key | 17 refusal strings in `src/mirai` end with "Symmetrie ausschalten (Shift+S)" (`symmetric_ops.py:49-65`, `symmetric_extrude.py:65-70`, `symmetric_knife.py:72-113`). Shift+S is bound only in the Lab. |

**Consequence (Reading, from I-5…I-8).** With a definition set, every mutating command `Application` handles today is
either coordinated (W/E/R, `C` in all four contexts, Delete/Dissolve/DissolveNoCleanup, Extrude) or refused (Soft).
No tool runs one-sided; within a coordinated W/E/R, a selected vertex without partner moves alone, as in the Lab (it has
nothing to mirror to, and the topology coordinators refuse such cases, A3 = S). Symmetric Extrude therefore cannot enter
the app alone: the moment the app can set a definition, **all** coordinated tools are live in `src/main.py`. Each has a Lab verdict: per-side pivot W/E/R KEEP (2026-10-03),
Connect 3b checked (residue ITERATE, built and confirmed with Split 4), Delete/Dissolve 3c (seam rule S2 and Face
Dissolve selection KEEP), Split 4 KEEP, Knife 6c KEEP, Extrude 7 KEEP (M-2).

### 1.2 Only in the Lab (`experiments/symmetry_lab/`)

| # | Item | Fact |
|---|---|---|
| L-1 | Keys | Context `symmetry_lab`: Shift+S `SymmetryCycle` ("Artist A2, 2026-09-24"), M `ReSymmetrize`, Shift+B `SymmetryGateMode` (`lab_bindings.py:46-62`). Start-up asserts all three resolve to `None` in GLOBAL and KNIFE, else `LabBindingConflict` (H2-R1, `lab_app.py:361`). |
| L-2 | Definition setup | `lab_symmetry`: E1 plane through the origin, normal exactly X/Y/Z; E3 seam = every edge with both ends at exactly `0.0` on the axis, derived once; E2 one undo step via `apply_mesh_change` (`lab_app.py:_cycle`). |
| L-3 | E1 reader | `current_axis` raises `ValueError` for any definition outside E1 (`lab_symmetry.py:74-87`), so a non-E1 definition written by someone else breaks the Lab. |
| L-4 | E5 gate | `GateMode` BLOCK (default) / MARK; `block_row()` is fail-closed from `NON_OPERATION` + declarations + `supports_symmetry`; `_install_row` is the one gate writer (H2-R6). |
| L-5 | Overlays | Plane outline, seam/unpaired/ambiguous markers, hover/selection partner markers, Re-Symmetrize preview (`lab_overlays.py`, via H1). `ReportCache` defers re-derivation while a transform runs (plan A3). |
| L-6 | HUD | `LabHud` pyglet labels (`lab_app_window.py:64`): asset, vertex count, axis + state, unpaired/ambiguous count, transform state, E5, constraint, status; orange MARK warning; blue preview line. |
| L-7 | Re-Symmetrize | `lab_topology` (topological pairing, "Lab-Experiment, keine Capability") and `lab_resymmetrize` (plan + preview, M/M/Esc). |
| L-8 | Cost probe | `probe_drag_cost.py`: W drag + Lab overlays; reference PC p95 0.40 / 0.86 ms (head / body), hover change p50 17.4 → 9.5 ms on body (intake log 2026-10-03). |
| L-9 | Shared wiring | The Lab builds `Application` with `src_main.GL_TYPES` and `install_handlers` from `src/main.py` (`run.py:60-91`): any overlay type added to `GL_TYPES` reaches the Lab too. |

### 1.3 What `src/main.py` would need

| # | Item | Fact |
|---|---|---|
| N-1 | A definition writer | Nothing in `src/` creates or removes a definition: the coordinators only rewrite the seam of an existing one inside their mutation (`symmetric_ops.py:162-259`, `symmetric_extrude.py:138`, `symmetric_knife.py:568`), `load_state` restores one (`core/mesh.py:1163`). The E1/E3 setup lives in `lab_symmetry` (L-2); `mirai.interaction.commands` has no symmetry command. |
| N-2 | A way to see the state | `src/main.py` has only the console status line ("PROVISIONAL until a HUD exists", `main.py:381-384`); no symmetry overlay, no HUD. |
| N-3 | Governance text | H2-R5 and the G-2 consequence for H2-R5 say no Production host sets a definition; guards T-R5b/T-G3b pin `src/main.py` (§2). |
| N-4 | Nothing for the tools | All coordinators already run in `Application` whenever a definition is set (I-7); no tool-specific work is needed for the app. |

---

## 2. Governance (Task 2): H2-R6, and what the text actually demands

### 2.1 The texts

**H2-R6** (AD-013, Addendum H2, `:674-677`), verbatim:

> **H2-R6 — one writer (governance, not a test, F14).** The gate has one writer: the Symmetry Lab's window wiring. There is
> no list, stack or registry of gates. A second user (another Lab, the Playground) needs its own review of this addendum; it
> does not get to extend the gate silently. Code review enforces this; a test could only assert a type, which proves nothing.

**H2-R6 after G-2** (AD-013, `:1029-1034`), verbatim:

> **H2-R6 — still one writer.** `refused_contexts` is a field of the one `command_gate` value. The Symmetry Lab's window
> wiring stays its only writer (`SymmetryAppLab._install_row`, `lab_app.py:340`). The amendment adds **no second writer and
> no registry**: the D-b declaration mapping is a static Production table of coordinators, read by the one writer to derive
> its row and by `Application` to dispatch coordinated operations. It holds no gate data and nobody installs anything into
> it at runtime. A second gate user still needs its own review.

**H2-R5** (AD-013, `:670-673`), verbatim:

> **H2-R5 — Production is unchanged.** With the defaults (`command_gate is None`, `hover_suspended is False`) behaviour is
> identical; `interaction_owner`, `set_status` and `apply_mesh_change` are additive. `src/main.py` writes no gate data and
> calls neither `apply_mesh_change` nor `set_status` (guard test).

**H2-R5 after G-2** (AD-013, `:1022-1028`), the second half, verbatim:

> **The other half (review S3):** after slice 3, `_connect_command` also changes when a symmetry definition is set
> (canonicalisation, coordinators, runtime refusals). That is Production code, but no Production host sets a definition
> today: `src/main.py` contains no symmetry code. A guard test keeps it so (T-G3b), and T-G3a pins the G-3 boundary from the
> Production side.

### 2.2 Finding

| # | Finding |
|---|---|
| G-1 | **"The gate" in H2-R6 is `command_gate`** (with `hover_suspended`, the "gate data" of H2-R5). A symmetry definition is mesh state (AD-SYM-01), not gate data. The G-2 text already draws this line for the declaration table ("holds no gate data … nobody installs anything into it"). Writing a definition is therefore **not** writing the gate. |
| G-2 | **The app is the base the gate sits on, not a second writer.** `Application` (`src/mirai`) consults the gate at three sites and "calls no experiment code"; `src/main.py` and the Lab are two hosts of separate `Application` instances in separate processes. A `src/main.py` that sets definitions but installs no gate runs with `command_gate is None` — exactly H2-R5's default case. The Lab stays the only writer on its own instance. |
| G-3 | **H2-R6 does not demand an amendment** as long as Production writes no `command_gate`/`hover_suspended`. It would demand its own review only for option F-b (§3.3: Production installs a BLOCK row) — and then because Production *writes the gate*, not because it sets a definition. |
| G-4 | **H2-R5 does demand an amendment.** Its G-2 half states "no Production host sets a definition today … A guard test keeps it so (T-G3b)". M-1 reverses exactly that premise. Moving the writer into `Application` would keep T-G3b green (it scans only `src/main.py`, `tests/test_command_gate_contexts.py:451-519`) while defeating its stated purpose; that would be passing the guard, not keeping the rule. |
| G-5 | **Two related texts become stale, no rule changes:** the H2 "Basis" line ("Symmetry itself is not promoted (`src/main.py` gets no symmetry UX)", `:434-436`) and Alternative D's reason ("promotion is the Artist's decision and was deferred (ROADMAP §7, 2026-10-02)", `:476`). Both are dated history; a dated note suffices. |
| G-6 | **H2-R1 changes only if the app takes Shift+S** (option E-1, §3.1): the Lab's start-up assert would then raise `LabBindingConflict` (L-1). The Lab would drop its own Shift+S entry and use the app's command, so H2-R1's "exactly three entries, all keys" becomes two. With any other app key H2-R1 is untouched. |

### 2.3 Proposed amendment (only what G-4 and G-6 demand)

No new mechanism. To be written into AD-013 as a dated note **after** Manu decides; the wording below is the proposal.

- **H2-R5, G-2 half — replace** "but no Production host sets a definition today: `src/main.py` contains no symmetry code. A
  guard test keeps it so (T-G3b)" **with** (wording for E-1…E-3, where the writer is an `Application` command; under E-4
  `src/main.py` itself sets the definition at start and T-G3b is retired instead of re-labelled): "From 2026-10-14 (Manu,
  AD-SYM-04 M-1) the Production host sets definitions through `Application`'s own symmetry command, recorded in history like any mesh change. `src/main.py` itself still writes
  no gate data and contains no symmetry code; T-G3b keeps guarding `src/main.py` and is re-labelled accordingly. With
  `command_gate is None` an undeclared operation runs as without a definition, and T-G3a keeps pinning that boundary (it
  flips only if Manu chooses F-c, §3.3)."
- **H2-R5, first half — unchanged** if the writer is an `Application` command (recommended, §3.1): `src/main.py` then calls
  neither `apply_mesh_change` nor `set_status` and T-R5b stays as it is. Overlays reach the app as a GL type handed to
  `init_scene` (the `soft_overlay_type` precedent), not through an `add_overlay` call in `src/main.py`.
- **H2-R6 — unchanged.** Add one clarifying sentence only: "Setting a symmetry definition is not writing the gate."
- **H2-R1 — only if the app's key is Shift+S** (E-1, or E-2 on Shift+S): "The Lab context holds exactly two entries (M,
  Shift+B); Shift+S is the app's GLOBAL symmetry command (AD-SYM-04)." T-R1a/T-R1b follow. With any other key H2-R1 is
  unchanged.
- **Dated notes, no rule change:** H2 Basis line and Alternative D (G-5); AD-SYM-02 §4 ("Lab-Verdikt … entscheidet dadurch
  nichts für Production") stays true under UA-2 and gets a pointer only if Manu answers Q-3 with F-c.

### 2.4 The Lab keeps working on the same path — constraints for the slices

- **K-1** The app's definition writer produces E1 definitions only (origin plane, axis normal; L-3), or `current_axis` must
  learn the new form in the same slice.
- **K-2** One home per piece (AD-013 I1): the E1/E3 setup and any overlay moved into `src/` is **moved, not copied** (B6
  precedent); the Lab imports or uses the app's version. Because the Lab passes `src_main.GL_TYPES` (L-9), an app overlay
  type would otherwise draw twice in the Lab.
- **K-3** The app's toggle must notify the viewport (a definition-only change reports nothing today; the Lab marks its
  overlays dirty itself in `_cycle`), so overlays of both hosts re-derive.
- **K-4** The Lab's gate re-derivation (H2-R2: after every forwarded key) already covers a definition changed by an app
  command, because it reads `mesh.symmetry_definition` and never caches it.
- **K-5** `experiments/symmetry_lab/tests` stays green on every slice (AGENTS.md §8a: `Application` changes reach the Lab).

---

## 3. Entry points in the app (Task 3) — `PROVISIONAL`, Artist-facing

Nothing here is decided (AD-013 A5: the Lab's keys and HUD are not promoted with the capability). Each option names its cost.

### 3.1 Create and remove a definition

| | Option | Cost |
|---|---|---|
| **E-1** | **Shift+S as in the Lab**: off → X → Y → Z → off, one Undo step each, plane through the origin (E1), seam derived at exactly 0.0 (E3). An `Application` command; the E1/E3 functions move from `lab_symmetry` to `src/mirai`. | The 17 refusal texts already name Shift+S (I-11) — they become true in the app. H2-R1 amendment + small Lab change (G-6): the Lab drops its Shift+S entry and uses the app's. E3's exact-zero rule means a mesh that is only nearly symmetric comes up `partial` (`man_with_shoes`: 54 vertices without partner), and Re-Symmetrize to repair it stays in the Lab (UA-3). |
| E-2 | **One key, X only** (on/off) | Simplest to learn; Y/Z symmetry not reachable in the app. Same Shift+S/H2-R1 trade-off if the key is Shift+S; with another key the 17 texts must change. |
| E-3 | **Another key with the Lab's cycle** | H2-R1 untouched, no Lab change. Two keys for one meaning across hosts (AD-013 A1, shared language) and the 17 texts must be reworded or made key-neutral. |
| E-4 | **Start option only** (`python src/main.py head_basemesh --symmetry X`) | No key, no binding question; cannot be switched off while working. |

**Recommendation (`PROVISIONAL`): E-1.** It is what Manu already uses in the Lab, the texts already say it, and the Lab gets
simpler (one fewer override). The cost is one H2-R1 sentence.

### 3.2 Show the state

| | Option | Cost |
|---|---|---|
| S-1 | **Status line only**: on toggle `Symmetrie X (valid)` / `Symmetrie X (partial, 54 ohne Partner)` / `Symmetrie aus` | Free (the console status exists). Invisible once scrolled; no hint where unpaired vertices are. |
| **S-2** | **S-1 + plane outline + problem markers** (unpaired magenta, ambiguous white, seam green) — the Lab's plane and state overlays, moved to `src` | One overlay move (K-2) with its plan-A3 deferral; cost on the reference PC already measured in the Lab (L-8). No partner markers. |
| S-3 | **Everything from the Lab** incl. turquoise partner markers for hover and selection | As S-2 plus the partner overlay, which caused the 17.4 ms hover finding on body (fixed to 9.5 ms, L-8). More visual noise; more to move. |
| — | A HUD line in `src/main.py` | Not offered: the app has no HUD yet (N-2); a HUD is its own UX decision. |

**Recommendation (`PROVISIONAL`): S-2.** It answers "is symmetry on, and where is it broken" without new UX.

### 3.3 Fail-closed in the app (UA-2)

E5 KEEP-BLOCK is a Lab verdict (AD-SYM-02 §4 note). Today nothing in the app could run one-sided (§1.1 consequence); the
question is only about tools wired **later** (Loop Insert, Collapse, Tweak, Gizmo …).

| | Option | Cost |
|---|---|---|
| **F-a** | **No runtime gate; a build-time guard instead.** A test in `tests/` runs every command constant through `Application` on a symmetric fixture with a definition set and asserts: completeness unchanged, or nothing changed and a refusal status posted. A newly wired tool fails it until it is declared or refuses. E5 (MARK/BLOCK, Shift+B) stays Lab-only. | No governance change (G-3). Catches only what the test's fixture/selection exercises; a tool reachable only through an unusual selection could slip. |
| F-b | `src/main.py` installs a Production BLOCK row | A second gate writer: H2-R6 review (G-3), H2-R5 rewritten, `NON_OPERATION` must move to `src`. Largest. |
| F-c | G-3: `Application` itself refuses undeclared operations whenever a definition is set | Puts KEEP-BLOCK into Production (needs Manu's promotion of that verdict); the Lab's MARK comparison loses its subject (MARK has nothing to compare with today's declarations anyway, README "E5"); T-G3a flips. |

**Recommendation (`PROVISIONAL`): F-a.** Same protection for every tool that exists or is wired with tests, no second writer.

### 3.4 Artist questions (one per topic)

- **Q-1 (Ein-/Ausschalten):** E-1 (Shift+S wie im Lab: aus → X → Y → Z → aus), E-2 (nur X an/aus) oder anders?
- **Q-2 (Anzeige):** S-1 (nur Statuszeile), S-2 (plus Ebene und Problem-Punkte) oder S-3 (alles aus dem Lab inkl. türkiser Partner)?
- **Q-3 (Werkzeuge, die nicht spiegeln können):** sollen sie in der App unter Symmetrie verweigert werden (wie BLOCK im Lab;
  F-a sichert das beim Bauen ab), und bleibt der MARK/BLOCK-Schalter ein reines Lab-Werkzeug?

---

## 4. Core basis for symmetric Soft (Task 4) — technical basis only

The decision is made (M-5: one Core change, together with symmetric Soft). This section does not re-decide it and stops
before proposing the change.

### 4.1 What symmetric Soft needs, item by item

| # | Need | From the Core? |
|---|---|---|
| C-1 | **Weights and falloff across the mirror plane.** One influence value per vertex, symmetric by construction. | **No.** The influence system is outside the Core (CORE_V1_FREEZE §4, V1_CORE §6); `compute_influence` lives in `src/mirai/soft_selection/influence.py:157` and uses only public `Mesh` queries. Partner ids come from `mirai.symmetry`/`SymmetryIndex`. |
| C-2 | **Geodesic metric across the plane.** | **No.** Multi-source Dijkstra over the edge graph (`influence.py:115`); seeds ∪ mirrored seeds is a caller-side input. |
| C-3 | **Category × weight in one per-vertex step.** A mirrored partner needs the conjugate step *scaled by its weight*; a seam vertex needs the weighted step *then* the projection. | **Yes — this is the need.** The category logic lives in the Core ops (`MoveOperation._transform_position`: reflect/project the delta, `core/operations/move.py`; `_PivotTransformOperation`: conjugate step, projection, plane checks, `core/operations/transform.py:298-366`). The weight logic lives in `src/mirai/soft_selection/ops.py` (`w·Δ`, `w·θ`, `1 + w(F−1)`), which refuses `params["symmetry"]` (`ops.py:63-75`). Neither side does both. Doing both outside the Core means a second copy of the mirror logic per tool (against INV-9/AR-10 and AD-SYM-02 §1 "genau eine Stelle"). The place where both meet is the one loop `VertexTransformOperation._on_update` with its dead `_weights` placeholder (`transform.py:227`, `:261-270`; AD-020 §8.3). |
| C-4 | **Seam vertices with `w < 1`.** | **Partly.** For a fixed axis/basis, the weight does not change whether a step keeps the plane (`_check_seam_step` stays valid). But `_PivotTransformOperation._on_begin` refuses whenever **any** seam vertex is in the op's vertex set and the pivot is off the plane (`transform.py:338-341`). Under Soft the vertex set grows with the radius, so this begin-time scope decides when a soft Rotate/Scale is refused (§5.1 D-3). |
| C-5 | **Scale evaluated absolutely for `w < 1`** (accumulated factor since `begin()` plus the start snapshot, `ops.py:150-215`). | **Yes, if weighting moves in.** It is a visible deviation from the incremental update contract (`core/operation.py:15-25`, AD-020 F9) and would then live in the Core. |
| C-6 | **One basis per gesture** when weights are present (FINDINGS L5). | Contract wording only; the app's tools already fix the basis per gesture (AD-020 §1 F6). |
| C-7 | **`supports_symmetry`** on the weighted operations (AD-SYM-02 §2.3). | Class attribute; today `False` on all soft classes. |

### 4.2 The smallest opening (location, not design)

The per-vertex step of `VertexTransformOperation` (`_on_update`, the `_weights` placeholder) and, for Rotate/Scale, the
begin-time seam scope of `_PivotTransformOperation._on_begin`; plus Scale's absolute path (C-5). **Not touched:** `Mesh`,
the `Operation` lifecycle, `OperationContext` (the `params` channel suffices, AD-SYM-02 §2.2), `HistoryStack`,
`VertexTransformCommand`, every topology operation.

### 4.3 Risk of that opening

- **R-1 Regression surface.** Every Move/Rotate/Scale gesture runs through this loop, symmetric ones included. The AD-014
  argument applies: the `w == 1` path must stay byte-identical; radius-0 bitwise tests exist (AD-020 P-D,
  `tests/test_soft_selection_ops.py`). Suites in reach: `tests/test_transform_operations.py`, `test_symmetric_move.py`,
  `test_symmetric_transform.py`, `test_application_symmetry.py`, `test_soft_selection_*.py`, `test_application_soft_*.py`,
  `experiments/symmetry_lab/tests/test_app_lab_transform.py`, `test_app_lab_soft_selection.py`.
- **R-2 Double weighting.** If the Core weights while `src/mirai/soft_selection/ops.py` still weights, every soft gesture
  is weighted twice. The AD-020 F3 tripwire ("base never blends") guards this today; Core change and soft-op change must go
  in one commit, and the tripwire flips on purpose.
- **R-3 Contract deviation enters the Core** (C-5); `operation.py` requires it to be documented visibly.
- **R-4 Artist-verdicted behaviour at `w == 1`.** The per-side pivot and its fallback (KEEP 2026-10-03) and the seam
  refusal texts must not change for plain symmetric Rotate/Scale.
- **R-5 Process.** CORE_V1_FREEZE §7 (six steps) and a §7.1 entry; a Haltepunkt (Development System §5) — the change gets its
  own review before code.

---

## 5. Symmetric Soft Selection as slices (Task 5)

### 5.1 Design questions

- **D-1 Seam weights.** *Proposal (`PROVISIONAL`):* one field over seeds ∪ mirrored seeds, weight from the nearest seed
  (`min` distance), not a sum; and **one weight per mirror pair**, never two independently computed ones (a pair takes the
  larger of its two field values), so the partner's step is the exact conjugate (INV-6: the other side comes from the
  intent, not from a second search). *(Reading, to be checked by probe SS0:)* on an exactly symmetric mesh, a vertex is
  never nearer to a seed on the other side than to that seed's mirror on its own side (Euclidean: same-side points are
  closer to the mirrored point; geodesic: reflect the part of a path beyond the plane, which is never longer). So the field
  equals each side's own field, mirrored, both members of a pair already agree, and a seam vertex gets the same weight from
  both sides; a sum would double the pull at the middle. A seam vertex then takes the weighted step and is projected onto
  the plane — for Move the same rule as symmetric Move today (KEEP). **No Artist question** (derived from INV-6).
- **D-2 Geodesic distance across the plane.** With D-1 the cross-plane path never wins on an exact mesh, so geodesic needs
  nothing special. On a `partial` mesh (unpaired vertices, e.g. `man_with_shoes` 1e-6 off) the edge graph is no longer
  exactly symmetric and the two members of a pair can get different field values; the one-weight-per-pair rule of D-1 keeps
  them mirrored. *Proposal (`PROVISIONAL`):* a seed without a partner refuses the gesture visibly (A3 = S, "for now"); an
  unpaired vertex inside the falloff takes its side's step with its own weight (it stays unpaired, as under plain W/E/R).
  **No Artist question** (A3 = S exists).
- **D-3 Per-side pivot (Artist B, 2026-10-03) when the falloff reaches the seam.** Rotate/Scale use the centroid of the
  explicit selection, mirrored for the partners; with a seam vertex affected and that centroid off the plane, they fall back
  to the pair midpoint. Under Soft "a seam vertex is affected" depends on the radius, so the pivot would jump when the
  radius grows across the middle. Options: **P-a** keep the own-side pivot; seam vertices reached only by the falloff (`w < 1`) slide in
  the plane (projected; symmetric by construction, because a seam vertex is its own mirror); a seam vertex among the
  *selected* vertices keeps today's fallback (KEEP 2026-10-03, R-4); **P-b** fall back to the pair midpoint as
  today (pivot jumps with the radius); **P-c** refuse visibly. *Engineering lean: P-a* (soft steps are not rigid anyway).
  **Artist question Q-4** (one).
- **D-4 Performance on the reference PC.** Symmetric Soft roughly doubles the moved set and the influence work, and adds a
  correspondence per gesture start and per preview refresh. Known: worst soft row body 15 % euclidean p95 **7.73 ms**
  (bar 8 ms), plain W body 112 V p50 5.29 ms (REFERENCE_HARDWARE §2). *(Reading:)* the symmetric worst rows may cross the
  bar. Gate: the `soft_w` scenario of `experiments/drag_cost/probe_drag_gl.py` gains a symmetric variant (seed off the
  plane, radius steps that cross it); Manu runs it before the joint test. A missed bar is a viewport question (AD-020 §7.3
  rule), not a reason to change the semantics. **No Artist question** (measurement; the mesh-size Intent is already open as
  D1c, WP-VIEW-PERF-01).
- **D-5 Bands.** Today hidden under a definition (I-8). *Proposal:* show both sides (the mirrored field). Practical-test item, no question.

### 5.2 Slices (proposal; built on the app path, M-4)

| # | Slice | Content | Gate / tests |
|---|---|---|---|
| SS0 | Probe (no `src` change) | Headless probe in `experiments/` reading `src` only: D-1 field symmetric bit-for-bit on `subd_cube`, head, body (both metrics, X/Y/Z); how often D-3 occurs per radius step; correspondence + influence cost per gesture start (container). | Report only; stops if D-1's claim fails. |
| SS1 | **The one Core change** (M-5) | Weighting into the Core loop per §4 (design in its own AD/addendum + independent review **before code**, R-5); `src/mirai/soft_selection/ops.py` migrated in the same commit (R-2). Non-symmetric Soft must stay bitwise identical. | Core contract tests; radius-0 identity; the AD-020 suites green; `tests` + Lab tree once. |
| SS2 | Symmetric influence and gesture | D-1 field, per-side step (plain / conjugate / projected), D-2 refusals, D-3 per Manu's answer; `Application` lifts the Soft + symmetry refusal (I-8) only for supported cases; Lab: no row change (soft commands are already `NON_OPERATION`). | One Undo step per gesture; exact mirror (completeness unchanged); cancel exact; MARK and BLOCK alike in the Lab. |
| SS3 | Bands on both sides + probe | D-5; the symmetric `soft_w` probe rows (D-4). | Manu runs the probe on the reference PC. |

### 5.3 Artist question (Soft)

- **Q-4 (Pivot an der Mitte):** Wenn du mit Soft an eine Stelle abseits der Mitte drehst/skalierst und der Einflussbereich
  über die Mitte reicht: sollen die Mittelpunkte in der Ebene mitgleiten (P-a, Drehpunkt bleibt deine Auswahlmitte), soll
  der Drehpunkt auf die Mitte zwischen beiden Seiten springen (P-b, wie heute ohne Soft), oder soll es abgelehnt werden (P-c)?

---

## 6. Bringing symmetric Extrude into the app (Task 6)

The verdict is recorded (M-2, Lab README "Slice 7", commit `0f8fb04`). Nothing Extrude-specific must be built:
`_extrude_begin` already runs the planner whenever a definition is set (I-7). The slices bring the definition into the app.

| # | Slice | Content | Gate / tests |
|---|---|---|---|
| A0 | Decisions (docs) | Manu answers Q-1…Q-3 after the review; the AD-013 note of §2.3 is written; AD-SYM-04 → DECIDED. | No code. |
| A1 | Definition entry | E1/E3 setup **moved** from `lab_symmetry` to `src/mirai` (K-2); an `Application` symmetry command per Q-1 (history-recorded like `apply_mesh_change`, viewport notified, K-3); default binding `PROVISIONAL`; status line per S-1; the F-a guard test (if Q-3 = F-a). Lab uses the moved functions and, under E-1, the app's command (H2-R1 note). | New app tests: toggle = one Undo step, Undo/Redo restore the definition, `load_scene` drops it; a smoke per coordinated tool through `src/main.py`'s `Application` (W/E/R, `C` ×4, Knife, Delete/Dissolve, `T`); T-R5b unchanged, T-G3b re-labelled; `tests` + `experiments/symmetry_lab/tests` + `playground/tests` once (shared `Application` path). |
| A2 | Display | Per Q-2: the Lab's plane/state overlays **moved** to `src` as an `Application`-owned overlay handed in through `GL_TYPES` (soft-band precedent), A3 deferral kept; the Lab drops its copies (no double draw, L-9). | Overlay sync tests ported from the Lab; Lab draw-order test adapted; drag-cost probe re-run on the reference PC (L-8 numbers as the bar). |
| J | Joint Artist test (M-3) | In `python src/main.py`: the Slice 7 steps 1–8 (step 9, MARK, stays Lab-only under UA-2), plus the symmetric Soft test of §5. | Manu's verdict, one session. |

**Practical-test sketch for Extrude in the app** (prepared, not run): `python src/main.py`, symmetry on (per Q-1), `3`,
a face off the middle, hold `T` and drag → both sides; `Ctrl+Z` one step; a face at the middle → one bump, no wall;
extrude the cap again; both sides selected → same result; drag inward → pocket on both sides; `man_with_shoes_basemesh`
(SPACE menu) → a face without partner is refused; symmetry off → `T` one-sided as before.

---

## 7. Combined order (Way B)

A0 → A1 → A2 → SS0 → SS1 → SS2 → SS3 → **J**. Playground tools come after J (M-3). SS0 may run in parallel with A1/A2 (it
reads `src` only). Stop points on the way: SS1 (Core change, own review), any slice that would need a decided AD changed
beyond §2.3.

---

## 8. Not decided here

The answers to Q-1…Q-4. The shape and names of the `Application` symmetry command, the moved functions and the overlay type.
The Core change itself (SS1, own document). Whether E5 ever leaves the Lab (Q-3). Re-Symmetrize in the app (UA-3). The
choice between the Knife mirror variants V-a/V-b/V-c and F6 (still open, AD-SYM-03 §10.9). F-1 of the Extrude (corner at
the seam). Artist Input Truth entries for any symmetry key. Gizmo, Tweak, Loop Insert/Slide, Collapse, Loop/Ring selection
(later packages); the Lab test stage (separate task); Playground UX.

---

## 9. Review

**Review CLAUDE-001 archived (2026-10-14):** [AD-SYM-04_REVIEW_CLAUDE_001](../archive/symmetry_lab/reviews/AD-SYM-04_REVIEW_CLAUDE_001.md) — ACCEPT WITH CHANGES; R-1…R-3 before Manu answers Q-1…Q-4. Answers to its findings: open.

*Original request:* An independent review in a fresh session is to check in particular: G-1…G-6 against the AD-013 text; whether F-a is
"a new governance mechanism" (it is meant as a test only); the D-1 reading; whether §4 stops before a design.

---

## Kurzfassung für Manu (Deutsch)

**Worum es geht.** Du hast entschieden: Symmetrie kommt in die App (`src/main.py`), danach baut man dort die symmetrische
Soft Selection, und beides testest du zusammen. Dieses Dokument bereitet das vor; gebaut wird nichts.

**Die wichtigste Erkenntnis.** Die App kann symmetrisches Arbeiten im Grunde schon: W/E/R, `C` (Split/Connect), Knife,
Delete/Dissolve und Extrude spiegeln alle von selbst, sobald am Mesh eine Symmetrie gesetzt ist. Was fehlt, ist nur das
**Einschalten** und das **Sehen**. Darum kommt der symmetrische Extrude nicht allein in die App, sondern alle gespiegelten
Werkzeuge zusammen — für alle hast du im Lab schon KEEP gesagt.

**Regeln (AD-013).** Die Regel „nur das Lab schreibt das Gate" muss sich nicht ändern: Symmetrie einschalten ist kein
Gate-Schreiben. Ändern muss sich ein Satz, der heute ausdrücklich sagt „die App setzt keine Symmetrie" — das hast du heute
umgedreht. Das Lab läuft weiter auf demselben Weg.

**Deine Fragen (je Thema eine):**
1. **Einschalten:** `Shift+S` wie im Lab (aus → X → Y → Z → aus) — Empfehlung, die Meldungen in der App nennen schon
   `Shift+S` — oder nur X an/aus, oder anders?
2. **Anzeige:** nur Statuszeile, oder zusätzlich Ebene und Problem-Punkte (magenta = ohne Partner) — Empfehlung — oder alles
   aus dem Lab inklusive türkiser Partner-Punkte?
3. **Werkzeuge, die (später) nicht spiegeln können:** in der App verweigern wie BLOCK im Lab (Empfehlung; abgesichert durch
   einen Test beim Bauen), und der MARK/BLOCK-Schalter bleibt reines Lab-Werkzeug?
4. **Soft an der Mitte:** wenn du mit Soft abseits der Mitte drehst/skalierst und der Einfluss über die Mitte reicht —
   sollen die Mittelpunkte in der Ebene mitgleiten (Empfehlung), soll der Drehpunkt auf die Mitte springen (wie heute ohne
   Soft), oder soll es abgelehnt werden?

**Annahmen, die du mit einem Satz korrigieren kannst:** Re-Symmetrize (M) bleibt im Lab. Die Reihenfolge ist: erst
Einschalten und Anzeige in der App, dann die symmetrische Soft Selection (mit der einen Core-Änderung), dann ein gemeinsamer
Praxistest von Extrude und Soft in der App.
