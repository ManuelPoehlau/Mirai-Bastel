# AD-SYM-04 — Symmetry in the Production app (`src/main.py`), then symmetric Soft Selection

**Status:** **DECIDED** (Manu, 2026-10-14): Q-1…Q-4 answered with the recommendations (commit `fa6e017`; Decision record
below). Proposed and revised the same day after the independent review CLAUDE-001 (ACCEPT WITH CHANGES, answered in §9).
The AD-013 amendment of §2.3 is written ([AD-013, Addendum 2026-10-14](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md#addendum-2026-10-14-ad-sym-04--symmetry-in-the-production-app-h2-r5-and-h2-r1-amended-h2-r6-clarified)).
Slice A0 is done with this. **Slice A1 is built (2026-10-14, [implementation note](#implementation-note-2026-10-14-slice-a1)).** Keys, look and texts stay `PROVISIONAL` (AD-013 A5).
**Addition (Manu, 2026-10-14): Re-Symmetrize comes into the app too** (UA-3 corrected). How it gets there touches decided
AD-013 H2 rules, so §10 is a **PROPOSED** extension that needs its own independent review before slice A3 is built.
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

## Decision record (2026-10-14)

Where a section below still reads "proposed", "recommendation" or "assumption", this record wins.

**Artist decisions (Manu, 2026-10-14, answers written into the Kurzfassung, commit `fa6e017`):**

| Q | Decision | Words |
|---|---|---|
| Q-1 | **E-1:** Shift+S cycles off → X → Y → Z → off in the app, one Undo step each, E1 plane, E3 seam (§3.1) | "Ich nehme deine Empfehlung" |
| Q-2 | **S-2:** status line plus plane outline and problem markers (unpaired, ambiguous, seam); no partner markers (§3.2) | "ich nehme deine Empfehlung" |
| Q-3 | **F-a:** tools that cannot mirror are refused in the app, secured by the build-time guard test, no runtime gate; the MARK/BLOCK switch (E5, Shift+B) stays Lab-only (§3.3) — UA-2 is thereby confirmed | "ich nehme deine Empfehlung" |
| Q-4 | **P-a:** under symmetric Soft, seam vertices reached only by the falloff slide in the plane; the pivot stays the own-side selection centre; selected seam vertices keep today's rules (§5.1 D-3). A Core seam-rule change inside SS1 | "Ich nehme deine Empfehlung" |

**Consequences fixed by these answers (no further decision):** H2-R1 changes (Shift+S becomes the app's command; the Lab
keeps M and Shift+B), T-G3b is narrowed (S-2), K-6 applies, AD-SYM-02 §4 needs no pointer (F-c not chosen). All written
into AD-013, Addendum 2026-10-14.

**Re-Symmetrize (Manu, 2026-10-14, in the chat: "Re Symmtrizes kommt mit in die App"):** UA-3 is corrected. Re-Symmetrize
(M / M / Esc, Lab KEEP since 2026-09-25, confirmed on the app path 2026-10-03) and the topological pairing it rests on become
part of the app. This is the explicit promotion decision for that research code (M3). The mechanism is proposed in §10.

**Not answered, still an assumption (Manu did not correct it, which is not a confirmation):** §0.2 (order A1/A2 → SS → one
joint test J; A3 now joins the A-slices, §7).

**Engineering, unchanged by the decision:** the key, the overlay look and every text stay `PROVISIONAL`; no Artist Input
Truth entry is created (AD-013 A5).

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
| I-2 | Scene change drops it | `init_scene` replaces the mesh (`application.py:537`), `load_scene` also resets history (`:629-680`), so a definition never survives into another scene (AD-SYM-01 condition 3). |
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
  flips only if Manu chooses F-c, §3.3)." **Under S-2/S-3 this wording is not enough** (review R-2): the moved overlay is a
  GL type that `src/main.py` must import for `GL_TYPES`, and T-G3b flags every import whose module or name contains
  "symmetry". T-G3b is then **narrowed, not re-labelled**, and the quoted sentence ends instead: "…T-G3b is narrowed to:
  `src/main.py` never assigns `symmetry_definition` and calls no correspondence or coordination function; importing one
  GL overlay type for `GL_TYPES` is allowed." The phrase "contains no symmetry code" is dropped. Renaming the module to
  avoid the word would pass the guard without keeping the rule (G-4) and is not an option. Under S-1 the wording above
  stands.
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
- **K-6** The Lab's gate rows must let the app's symmetry command through (review R-3). As a `mirai.interaction.commands`
  constant dispatched by `Application.key_press`, it is in none of the sets `block_row()` allows (`lab_app.py:306-336`),
  so under BLOCK — the Lab default while symmetry is on — it would get `BLOCK_NOT_ALLOWED_TEXT`: Shift+S could switch
  symmetry on but never cycle it or switch it off. The BLOCK row therefore allows it **by a named entry** (the MARK row
  installs no gate, `ROW_MARK`, so nothing changes there; *corrected 2026-10-14, the first wording said "BLOCK and MARK
  rows"*) in the row (not silently via `NON_OPERATION`, because it changes mesh state); the preview row keeps refusing it (H2-R2). T-FC1
  (which expects every unlisted constant refused) and T-R1a are adjusted in A1. This is a Lab-side change under H2's
  existing rules, no new writer.
- **K-7** The Playground stays out (review R-8). A new constant with a default binding also reaches the Playground's
  resolver (`playground/input_adapter.py:107`), and its `SAFE_COMMANDS` whitelist (`playground/command_handler.py:62-68`)
  drops it, so the Playground cannot set a definition. That is intended: its topology tools mutate outside the
  coordinators and would run one-sided. Adding the command there would make the Playground a second symmetry host and
  needs its own review (the "second user" of H2-R6).

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
| **F-a** | **No runtime gate; a build-time guard instead.** A test in `tests/` binds every command constant to a test GLOBAL key and presses it through `Application` on a symmetric fixture with a definition set. Oracle, with no command list (review R-5): **if the mesh changed, completeness is unchanged**; if the command was handled and refused, a status was posted. Unhandled constants (`return False`, no change) pass trivially. A newly wired one-sided tool fails it until it is declared or refuses. E5 (MARK/BLOCK, Shift+B) stays Lab-only. | No governance change (G-3), no second command list and no import of the Lab's `NON_OPERATION`. Known gaps, stated: it sees only the key path (a host's `dispatch_command(…, context=…)` and `apply_mesh_change` are outside it), and it catches only what the fixture's selection exercises. |
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
| C-3 | **Category × weight in one per-vertex step.** A mirrored partner needs the conjugate step *scaled by its weight*; a seam vertex needs the weighted step *then* the projection. | **Yes — the weighting semantics.** The Core loop already *composes* both: `VertexTransformOperation._on_update` calls `_transform_position` (conjugate step, projection; `MoveOperation`, `_PivotTransformOperation`, `core/operations/transform.py:298-366`) and then blends with `_weights` (`transform.py:227`, `:261-270`). Mirroring is affine, so the blend of a partner's conjugate step is the conjugate of the blended step, and the blend of two on-plane points stays on the plane (review R-7). What is missing is the semantics: the placeholder blends **positions** linearly, while the soft ops of `src/mirai/soft_selection/ops.py` use `w·Δ`, `w·θ` and an absolute `1 + w(F−1)` for Scale, and refuse `params["symmetry"]` (`ops.py:63-75`). Doing this outside the Core would mean a second copy of the mirror logic per tool (INV-9/AR-10, AD-SYM-02 §1 "genau eine Stelle"). So SS1 **replaces the placeholder's blend** with the weighted semantics; it does not have to invent the meeting point (AD-020 §8.3). |
| C-4 | **Seam vertices with `w < 1`.** | **Yes, depending on D-3.** `_PivotTransformOperation` refuses in **two** places whenever any seam vertex is in the op's vertex set: at `begin()` if the pivot is off the plane (`transform.py:338-341`), and on **every step** in `_check_seam_step` — Rotate unless the axis is parallel to the plane normal (`rotation_keeps_plane`, `:160-166`, `:382-387`), Scale unless it is uniform or aligned with the normal (`scale_keeps_plane`, `:169-185`, `:411-416`). Under Soft the vertex set grows with the radius, so both checks start to apply as soon as the falloff reaches the middle (review R-1). The weight itself does not change whether a step keeps the plane, so under P-b/P-c (§5.1 D-3) the checks stay as they are. **Under P-a, seam vertices reached only by the falloff are exempt from both checks** (they are projected instead): that is a change of the Core's seam rule, not only of its weighting, and belongs to SS1's scope and review. |
| C-5 | **Scale evaluated absolutely for `w < 1`** (accumulated factor since `begin()` plus the start snapshot, `ops.py:150-215`). | **Yes, if weighting moves in.** It is a visible deviation from the incremental update contract (`core/operation.py:15-25`, AD-020 F9) and would then live in the Core. |
| C-6 | **One basis per gesture** when weights are present (FINDINGS L5). | Contract wording only; the app's tools already fix the basis per gesture (AD-020 §1 F6). |
| C-7 | **`supports_symmetry`** on the weighted operations (AD-SYM-02 §2.3). | Class attribute; today `False` on all soft classes. |

### 4.2 The smallest opening (location, not design)

The per-vertex step of `VertexTransformOperation` (`_on_update`, the `_weights` placeholder) and, for Rotate/Scale, the
scope of both seam checks of `_PivotTransformOperation` — the begin-time pivot check and the per-step axis/factor check
`_check_seam_step` (C-4; changes only under P-a); plus Scale's absolute path (C-5). **Not touched:** `Mesh`,
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
- **R-4 Artist-verdicted behaviour at `w == 1`.** The per-side pivot and its fallback (KEEP 2026-10-03), both seam checks
  for selected seam vertices, and the seam refusal texts must not change for plain symmetric Rotate/Scale.
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
  both sides; a sum would double the pull at the middle. **Precondition of the geodesic half** (review R-6): every edge path
  across the plane passes through a vertex *on* the plane. An edge that straddles the plane with neither end on it breaks
  the reflection argument (`a'–b` need not be an edge); the one-weight-per-pair rule keeps the result symmetric anyway, but
  "each side's own field" can then fail. SS0 checks a mesh with straddling edges, or records that E3 meshes always have a
  seam loop. A seam vertex then takes the weighted step and is projected onto
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
  radius grows across the middle. A second check applies as well (C-4, review R-1): with a seam vertex in the set, Rotate
  is refused unless its axis is the mirror axis, and Scale unless it is uniform or aligned with it. Options:
  **P-a** keep the own-side pivot; seam vertices reached only by the falloff (`w < 1`) are exempt from **both** checks and
  slide in the plane (projected; exactly symmetric, because a seam vertex is its own mirror and the projections of R(p) and
  mirror(R(p)) coincide); a seam vertex among the *selected* vertices keeps today's rules (KEEP 2026-10-03, R-4). P-a is a
  **Core seam-rule change** inside SS1. **P-b** the pivot jumps to the pair midpoint as today **and** every soft Rotate about
  an axis other than the mirror axis, and every non-uniform soft Scale not along it, is refused once the radius crosses the
  middle — i.e. most soft rotations there. **P-c** refuse visibly whenever the falloff reaches the middle.
  *Engineering lean: P-a* (soft steps are not rigid anyway). **Artist question Q-4** (one).
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

- **Q-4 (Soft an der Mitte):** Wenn du mit Soft an einer Stelle abseits der Mitte drehst/skalierst und der Einflussbereich
  über die Mitte reicht: sollen die Mittelpunkte in der Ebene mitgleiten (P-a, Drehpunkt bleibt deine Auswahlmitte, jede
  Drehachse geht), soll der Drehpunkt auf die Mitte zwischen beiden Seiten springen — dann geht Drehen nur noch um die
  Spiegelachse und Skalieren nur gleichmäßig, alles andere wird abgelehnt (P-b, die heutige Regel ohne Soft) —, oder soll
  es ganz abgelehnt werden (P-c)?

---

## 6. Bringing symmetric Extrude into the app (Task 6)

The verdict is recorded (M-2, Lab README "Slice 7", commit `0f8fb04`). Nothing Extrude-specific must be built:
`_extrude_begin` already runs the planner whenever a definition is set (I-7). The slices bring the definition into the app.

| # | Slice | Content | Gate / tests |
|---|---|---|---|
| A0 | Decisions (docs) | Manu answers Q-1…Q-4 after the review; the AD-013 note of §2.3 is written; AD-SYM-04 → DECIDED. **Done 2026-10-14** (Decision record). | No code. |
| A1 | Definition entry — **built 2026-10-14** ([note](#implementation-note-2026-10-14-slice-a1)) | E1/E3 setup **moved** from `lab_symmetry` to `src/mirai` (K-2); an `Application` symmetry command per Q-1 (history-recorded like `apply_mesh_change`, viewport notified, K-3); default binding `PROVISIONAL`; status line per S-1; the F-a guard test (if Q-3 = F-a). Lab uses the moved functions and, under E-1, the app's command (H2-R1 note). | New app tests: toggle = one Undo step, Undo/Redo restore the definition, `load_scene` drops it; a smoke per coordinated tool through `src/main.py`'s `Application` (W/E/R, `C` ×4, Knife, Delete/Dissolve, `T`); the command's interaction gates (review R-4): ignored while W/E/R/T is armed or running (same gate as `C` and the mode keys, `application.py:1587-1603`, so the partner sets an armed tool resolves at `begin()` cannot change underneath it), ignored inside a Knife session (`_knife_key`, pinned by a test), and Soft armed → toggle → motion refused at `begin()` (`:1715`); Lab: K-6 named row entry, T-FC1 and T-R1a adjusted; T-R5b unchanged, T-G3b re-labelled or narrowed (§2.3); `tests` + `experiments/symmetry_lab/tests` + `playground/tests` once (shared `Application` path). |
| A2 | Display | Per Q-2: the Lab's plane/state overlays **moved** to `src` as an `Application`-owned overlay handed in through `GL_TYPES` (soft-band precedent), A3 deferral kept; the Lab drops its copies (no double draw, L-9). | Overlay sync tests ported from the Lab; Lab draw-order test adapted; drag-cost probe re-run on the reference PC (L-8 numbers as the bar). |
| A3 | Re-Symmetrize (§10) | Only after the §10 review and Manu's decision: topological pairing and plan **moved** to `src/mirai`; the preview as an `Application`-owned interaction (R-a); Lab drops its preview machinery. | See §10.4. |
| J | Joint Artist test (M-3) | In `python src/main.py`: the Slice 7 steps 1–8 (step 9, MARK, stays Lab-only under UA-2), the Re-Symmetrize steps of the Lab README ("Re-Symmetrize (M / M / Esc)", incl. `man_with_shoes_basemesh`), plus the symmetric Soft test of §5. | Manu's verdict, one session. |

**Practical-test sketch for Extrude in the app** (prepared, not run): `python src/main.py`, symmetry on (per Q-1), `3`,
a face off the middle, hold `T` and drag → both sides; `Ctrl+Z` one step; a face at the middle → one bump, no wall;
extrude the cap again; both sides selected → same result; drag inward → pocket on both sides; `man_with_shoes_basemesh`
(SPACE menu) → a face without partner is refused; symmetry off → `T` one-sided as before.

---

## 7. Combined order (Way B)

A0 → A1 → A2 → A3 (after the §10 review) → SS0 → SS1 → SS2 → SS3 → **J**. Playground tools come after J (M-3). SS0 may run in parallel with A1/A2 (it
reads `src` only). Stop points on the way: SS1 (Core change, own review), any slice that would need a decided AD changed
beyond §2.3.

---

## 8. Not decided here

~~The answers to Q-1…Q-4~~ (answered 2026-10-14, Decision record). The shape and names of the `Application` symmetry
command, the moved functions and the overlay type. The Core change itself (SS1, own document). The Re-Symmetrize mechanism
(§10, PROPOSED). The
choice between the Knife mirror variants V-a/V-b/V-c and F6 (still open, AD-SYM-03 §10.9). F-1 of the Extrude (corner at
the seam). Artist Input Truth entries for any symmetry key. Gizmo, Tweak, Loop Insert/Slide, Collapse, Loop/Ring selection
(later packages); the Lab test stage (separate task); Playground UX.

---

## 9. Review

**Independent review:** [AD-SYM-04_REVIEW_CLAUDE_001](../archive/symmetry_lab/reviews/AD-SYM-04_REVIEW_CLAUDE_001.md)
(fresh session, `claude/sweet-ritchie-tfv9xq` @ `2da6d11`, archived unedited). Verdict: **ACCEPT WITH CHANGES**, no
blocker; R-1…R-3 to be fixed before Manu answers Q-1…Q-4. Confirmed without change: the §1.1 consequence, I-1, I-11, G-1…G-6
(with the two additions below), the A5/I7 citation, and that §4 stops before a design. Every finding was re-checked against
the code before it was taken over (`transform.py:160-185`, `:382-416`; `application.py:537`, `:1587-1603`;
`playground/command_handler.py:62-68`). Nothing beyond the reviewer's own proposals was decided.

| Finding | Severity | Answer |
|---|---|---|
| R-1 — Q-4/C-4 omit the per-step seam axis/factor check; P-a is a Core rule change | major | **Fixed, as proposed.** C-4 names both checks; §4.2 adds the step-check scope; D-3 says P-a exempts falloff-reached seam vertices from both checks (a Core seam-rule change in SS1) and that P-b refuses most soft rotations once the radius crosses the middle; Q-4 reworded accordingly (§5.3, Kurzfassung) |
| R-2 — T-G3b cannot just be re-labelled under S-2/S-3 | major | **Fixed, reviewer's wording.** §2.3: under S-2/S-3 T-G3b is narrowed (no `symmetry_definition` assignment, no correspondence/coordination call; one GL overlay import allowed); "contains no symmetry code" dropped; renaming to dodge the guard ruled out (G-4). Under S-1 the original wording stands |
| R-3 — the Lab's BLOCK row would refuse the app's symmetry command | major | **Fixed.** New K-6: BLOCK and MARK rows allow the command by a named entry (not via `NON_OPERATION`), the preview row keeps refusing it; T-FC1 and T-R1a adjusted in A1 |
| R-4 — A1's tests miss the new command's interaction gates | medium | **Taken into A1:** ignored while W/E/R/T is armed or running (same gate as `C`/mode keys), ignored in a Knife session (test), Soft armed → toggle → refused at `begin()` (test). Whether the armed-time refusal posts a status follows the existing gate for `C` and the mode keys, which is silent today; A1 does not change that convention |
| R-5 — F-a's oracle needs a classification and fails on unhandled commands | medium | **Fixed, reviewer's oracle.** "If the mesh changed, completeness is unchanged; if handled and refused, a status was posted" — no command list, no Lab import; the key-path-only limit is stated as a known gap (§3.3) |
| R-6 — the geodesic half of D-1 needs a precondition | minor | **Fixed.** D-1 states it (no edge straddles the plane without a vertex on it); SS0 checks a mesh with straddling edges or records that E3 meshes have a seam loop |
| R-7 — the Core loop already combines category and weight | minor | **Fixed.** C-3 now says the loop composes both and that mirroring is affine; what is missing is the weighting semantics, so SS1 replaces the placeholder's blend |
| R-8 — the Playground is out of reach; say so | minor | **Fixed.** New K-7 |
| R-9 — `init_scene` line reference | nit | **Fixed** (I-2: `:537` and `:629-680`) |

A second review is not required by the findings (no blocker; every change is the reviewer's own proposal or a direct
consequence of it). Manu may ask for one.

---

## 10. Re-Symmetrize in the app (PROPOSED, 2026-10-14)

**Status:** PROPOSED. The decision *that* it comes is Manu's (Decision record); *how* is proposed here and needs an
independent review in a fresh session before A3, because it changes decided AD-013 H2 rules (Development System §5,
Haltepunkt "Änderung an einer entschiedenen Architekturentscheidung").

### 10.1 What exists (facts, read at `f8f77fc`)

| # | Fact |
|---|---|
| RS-1 | `lab_topology.py` (topological pairing E11 and sides E12; breadth-first over face pairs from the seam; conflicts unpaired, `partners` an involution) and `lab_resymmetrize.py` (`plan_resymmetrize`, `set_plan_positions`, `plan_summary`, `resym_preview_data`) are pure, GL-free, and import only `core`, `mirai.symmetry` and `lab_symmetry` (E1 axis). They call themselves "Lab-Experiment, keine Capability". |
| RS-2 | The Lab runs Re-Symmetrize as a **modal preview it owns**: M (one selected vertex) computes the plan once and opens it; M executes through `apply_mesh_change` (one Undo step, empty plan → no step); Esc closes it (`lab_app.py:_open_preview`, `_execute_preview`, `cancel_preview`). |
| RS-3 | The modality is enforced **through the gate**: while the preview is open the Lab installs the preview row (allow-list: display commands only) and `hover_suspended = True`; Esc reaches the Lab at window level (D1); Shift+S/Shift+B are refused by the Lab; any other row asserts (AD-013 H2-R2, N2; tests T-R2c, T-R2e, T-R2g, T-H). |
| RS-4 | `src/main.py` may write no gate data (H2-R5, unchanged by the 2026-10-14 addendum), and a second gate writer needs its own review (H2-R6). The Lab's mechanism therefore cannot be reused by the app as it is. |
| RS-5 | `Application` already owns one modal, key-owning interaction: the Knife session. `key_press` routes every key to `_knife_key` before resolution and gate (`application.py:1562-1563`); `interaction_owner` reports it; Esc/Enter/Undo are handled inside. |
| RS-6 | M is free in GLOBAL and KNIFE (the Lab's start-up assert) and in Artist Input Truth; the Lab binding is "Artist A7 (2026-09-25)". The Playground handles M / Shift+M itself in `on_key_press` (`playground/window.py:2571`, `:2584`), not through the BindingSet, and its `SAFE_COMMANDS` would drop a new command (K-7) — to be verified in A3 by the Playground's own M tests (`playground/tests/test_session_gate.py`, `input_characterization.py`). |

### 10.2 Alternatives for the preview in the app

| | Alternative | Assessment |
|---|---|---|
| **R-a** | **The preview becomes an `Application`-owned interaction**, shaped like the Knife session: `key_press` routes keys to it first (M executes, Esc cancels, display commands and navigation pass, everything else ignored with the existing hint text); `interaction_owner` gets a third value; `Application` pauses hover itself; the plan and its overlay data come from the moved modules. | **Proposed.** One interaction authority owns start and end (I3); no gate writer in Production (H2-R5/H2-R6 untouched); the Lab and the app share one implementation (I1). Cost: a new `Application` section (the Knife precedent) and an H2 amendment that removes the Lab's preview machinery (§10.3). |
| R-b | `src/main.py` (or `Application` on its behalf) installs the Lab's preview row | **Not proposed:** a second gate writer (H2-R6 review), H2-R5 rewritten, and the preview's own rules (N2, D1) would have to live in two hosts. |
| R-c | No preview in the app: M executes at once (one Undo step) | **Not proposed:** changes Artist-verdicted behaviour (M / M / Esc, KEEP); would need Manu's verdict first. |

### 10.3 What R-a changes in AD-013 H2 (proposed wording, to be reviewed)

- **H2-R1:** the Lab context holds **one** entry, Shift+B → `SymmetryGateMode`; M becomes the app's GLOBAL `ReSymmetrize`.
  (Supersedes the "two entries" of the 2026-10-14 addendum for this point.)
- **D1** (Esc closes the preview at window level) **is retired**: Esc reaches `Application`, which ends its own preview
  like a Knife session. T-R2f stays (Esc without a preview still disarms W and ends a Knife session).
- **H2-R2:** the preview leaves the list of the Lab's key-owning interactions; it is an `Application` interaction
  (`interaction_owner` set), so the existing bullet "while `interaction_owner` is not `None`, the Lab executes none of its
  commands and writes neither the gate nor the hover flag" covers it. The preview bullets (Lab opens/ends it, N2, "installing
  another row asserts") are retired with it.
- **Gate table:** the **preview row is removed**. The BLOCK row's named entries (K-6) gain `ReSymmetrize` next to the symmetry
  command (it changes mesh positions); MARK and symmetry-off rows unchanged.
- **H2-R3:** the start-up listing loses the preview row and the D1 line.
- **`hover_suspended`:** keeps its contract; its only external writer (the Lab's preview) goes away. Whether `Application`
  uses the same flag internally or the hook is retired is an A3 implementation choice, recorded in the addendum.
- **Unchanged:** H2-R4, H2-R5, H2-R6, G-2, the Limits of G.

### 10.4 Slice A3 (after review and Manu's decision)

Move (not copy) `lab_topology` and `lab_resymmetrize` into `src/mirai` (the E1 axis dependency comes with A1's moved
setup); `ReSymmetrize` command, default binding M (`PROVISIONAL`); the preview interaction (R-a) with hover pause, the
status line carrying the Lab's blue preview text (the app has no HUD), and the preview overlays moved with A2's overlay;
the Lab drops `_open_preview`/`_execute_preview`/`cancel_preview`, the preview row and D1, and reads the app's preview state
for its HUD line. Tests: the Lab's Re-Symmetrize tests ported to `tests/` against `Application` (rejections, one Undo step,
empty plan, selection kept and restored), the preview fuzz (old T-R2g) and hover test (old T-H) as `Application` tests;
`interaction_owner` covers the preview (old T-R2d extended); Lab: T-R1a/b for one entry, T-FC1 with `ReSymmetrize` named
under BLOCK; Playground: its own M / Shift+M handling unchanged. Cost check: the topological pairing runs once per M; its time on
`gollum.obj` (21 875 V) on the reference PC is unmeasured — A3 measures it in the container and names the reference-PC run.

### 10.5 Artist question

None. The behaviour (M / M / Esc, rejections, colours) is the Lab's KEEP; the only visible difference is that the blue
preview line becomes the status line, because the app has no HUD (`PROVISIONAL`, seen in J).

---

## Implementation note (2026-10-14, slice A1)

Production order (Manu, 2026-10-14: "Slice A1 … umsetzen"), rules AD-013 Addendum 2026-10-14 and K-1…K-7. No
change under `src/core`; no decided rule changed beyond the addendum, so no Haltepunkt was reached. The promotion of the
E1/E3 setup is the one M-1/Q-1 decided (E-1 names it: "the E1/E3 functions move from `lab_symmetry` to `src/mirai`").

**What was built**

| Piece | Where | Note |
|---|---|---|
| E1/E3 setup, **moved** (K-2) | `src/mirai/symmetry_axis.py` | `ORIGIN`, `AXIS_INDEX`, `AXIS_NORMALS`, `SYMMETRY_CYCLE`, `derive_seam_edges`, `definition_for_axis`, `current_axis` (K-1: still raises outside E1), `next_axis`, `set_symmetry_axis`. Removed from `lab_symmetry.py`; every importer (Lab, Lab tests, `experiments/topology` probes) now imports from `mirai.symmetry_axis`. What stays in the Lab is display (`SymmetryReport`, `symmetry_report`, `plane_outline_data`) — slice A2 material. |
| The command | `commands.SYMMETRY_CYCLE = "SymmetryCycle"`, default binding Shift+S in GLOBAL (`PROVISIONAL`) | `Application.dispatch_command` → `_symmetry_cycle`: off → X → Y → Z → off through `_mesh_transaction` (one `MeshStateCommand` `Symmetry <axis>`, selection-mirror entry, so Undo/Redo restore definition and selection). |
| K-3 | `_symmetry_cycle` | The step is reported as a topology change (`moved_of` omitted): pick cache, `viewport.on_topology_changed()`, soft-band refresh (bands are hidden under a definition), hover re-pick — the same notification its Undo already got. Extra overlays re-sync without a host flag; the Lab's `_cycle` and its own `dirty` marking for Shift+S are gone. Cost: one render-mesh rebuild per key press, as for every Undo. |
| Interaction gates (R-4) | `key_press` + `_symmetry_cycle` | Ignored while W/E/R/T is armed or running (same branch as `C`, Delete, Dissolve: silent, `False`); inside a Knife session the session gate ignores it (Shift+S resolves through the KNIFE→GLOBAL fallback, `_knife_key` drops it); `_symmetry_cycle` also returns `False` while `interaction_owner` is set, so the direct `dispatch_command` path cannot slide a definition under a running interaction. |
| Status line (S-1 part of S-2) | `application.symmetry_status_text` | `Symmetrie X (valid)`, `Symmetrie X (partial, 54 ohne Partner)`, `Symmetrie aus` (`… N mehrdeutig` when ambiguous). Text `PROVISIONAL`. |
| Lab (H2-R1, K-6) | `lab_bindings.py`, `lab_app.py` | Context `symmetry_lab` holds two entries (M, Shift+B); the start-up assert covers those two. Shift+S reaches `Application` through `lab_key_press`'s forward path, then `sync_gate` re-derives the row (K-4). BLOCK row: `APP_SYMMETRY_COMMANDS = {SymmetryCycle}` as a named entry; MARK and off rows unchanged; the preview row refuses it with its own text. The start-up listing names the app key. |
| T-G3b narrowed | `tests/test_command_gate_contexts.py` | `src/main.py` never assigns `symmetry_definition` and calls no correspondence / coordination / definition function (the moved writers added to the list); exactly one `…Overlay` import from a `viewport` module is allowed (for A2). Negative controls: assignment, writer and coordination calls, a second overlay import, an overlay import from outside `viewport`. T-R5b unchanged. |
| `src/main.py` | docstring only | No code change: it builds `Application()` and installs no gate; Shift+S reaches the command through `install_handlers` (test). |

**Tests** (named by the A1 row): `tests/test_application_symmetry_cycle.py` — cycle and one Undo step each, Undo/Redo
restore, only the definition changes and the selection stays, the four S-1 texts, `load_scene` drops the definition,
K-3 (extra overlay re-syncs, soft bands follow), the R-4 gates (W/E/R armed and running, T armed and running, Knife
session, direct `dispatch_command`), Soft on → Shift+S → W refused at arm and Soft after the arm refused at `begin()`, one
smoke per coordinated tool (W, E, R, `C` as Split / Edge Connect / Vertex Connect / Knife, Delete, Dissolve,
DissolveNoCleanup, `T`; oracle: one Undo step, the other side changed, AD-SYM-03 delta rule holds, state stays `valid`),
and `src/main.py`'s key handler reaching the command. `tests/test_symmetry_fail_closed_guard.py` — the F-a guard (§3.3):
every command constant × five fixture selections on subd_cube X, oracle "mesh changed ⇒ one Undo step, plane unchanged
unless `SymmetryCycle`, delta rule holds"; a coverage test that the fixtures really exercise the coordinated tools; a
negative control (Delete with its declaration removed runs one-sided and is reported). `tests/test_symmetry_axis.py` —
the E1/E3 tests moved from the Lab. Lab: T-R1a/T-R1b for two entries (plus: a user binding on Shift+S no longer stops the
Lab), T-FC1 with the named entry (allowed under BLOCK and cycling to off, refused under the preview row), the Shift+S
expectations of the cycle/HUD/keys/Knife tests.

**Behaviour change in the Lab (derived, `PROVISIONAL`):** Shift+S while W/E/R is held or a Knife session runs used to be
refused by the Lab with a status line (`Symmetrie (Shift+S) abgelehnt — …`). It is now the app's key and silent there,
like `C` — the convention §9 R-4 fixed for A1. Shift+S under the open preview is still refused visibly (the gate's
`Vorschau aktiv — Befehl ignoriert`). The status text after a step changed from `Shift+S: Symmetrie X` to the app's S-1
text.

**Not in A1:** the plane outline and problem markers in the app (A2); Re-Symmetrize (A3, after the §10 review; M stays a
Lab key). The F-a guard's known gaps stand as stated in §3.3.

**Smoke check for Manu (optional, not a verdict session — the verdict is J):** `python src/main.py`, **Shift+S** →
console `Symmetrie X (valid)`; select a vertex off the middle, hold **W** and move → the mirror vertex follows;
**Ctrl+Z** twice → move and symmetry undone (`Symmetrie aus` is not printed for Undo; the console says `Undo`).
Shift+S three more times → `Symmetrie Y (partial, …)`, `Symmetrie Z …`, `Symmetrie aus`. Nothing is drawn for the
plane yet (A2).

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
   `Shift+S` — oder nur X an/aus, oder anders? Manu: Ich nehme deine Empfehlung
2. **Anzeige:** nur Statuszeile, oder zusätzlich Ebene und Problem-Punkte (magenta = ohne Partner) — Empfehlung — oder alles
   aus dem Lab inklusive türkiser Partner-Punkte? Manu: ich nehme deine Empfehlung
3. **Werkzeuge, die (später) nicht spiegeln können:** in der App verweigern wie BLOCK im Lab (Empfehlung; abgesichert durch
   einen Test beim Bauen), und der MARK/BLOCK-Schalter bleibt reines Lab-Werkzeug? Manu: ich nehme deine Empfehlung
4. **Soft an der Mitte:** wenn du mit Soft abseits der Mitte drehst/skalierst und der Einfluss über die Mitte reicht —
   sollen die Mittelpunkte in der Ebene mitgleiten (Empfehlung; jede Drehachse geht), soll der Drehpunkt auf die Mitte
   springen wie heute ohne Soft (dann geht Drehen nur noch um die Spiegelachse und Skalieren nur gleichmäßig, sonst
   abgelehnt), oder soll es ganz abgelehnt werden? Manu: Ich nehme deine Empfehlung

**Entschieden (2026-10-14):** alle vier wie empfohlen — Shift+S, Ebene + Problem-Punkte, Verweigern ohne Laufzeit-Gate
(MARK/BLOCK bleibt im Lab), Mittelpunkte gleiten bei Soft in der Ebene. Nächster Schritt: Slice A1 (Einschalten in der App).
Die Reihenfolge hast du nicht korrigiert; sie bleibt eine Annahme.

**Slice A1 gebaut (2026-10-14):** `Shift+S` schaltet die Symmetrie jetzt in `python src/main.py` (aus → X → Y → Z → aus, je
ein Undo-Schritt, Meldung in der Konsole, z. B. `Symmetrie X (valid)`). Alle gespiegelten Werkzeuge laufen damit in der
App. Zu sehen ist die Ebene noch nicht (kommt mit A2). Im Lab ist `Shift+S` jetzt die App-Taste; einzige spürbare
Änderung dort: während W/E/R gehalten wird oder der Knife läuft, wird `Shift+S` still ignoriert (wie `C`) statt mit einer
Meldung abgelehnt. Ein optionaler Kurzcheck steht in der Implementierungsnotiz oben; das Verdikt bleibt beim gemeinsamen
Praxistest J.

**Nachtrag (2026-10-14): Re-Symmetrize kommt mit in die App** (deine Aussage). Im Lab ist die Vorschau (M / M / Esc) über die
Lab-Sperre gebaut, die die App nicht schreiben darf. Vorschlag (§10): die Vorschau wird ein eigener Modus der App, wie die
Knife-Session; Taste M wandert vom Lab in die App, das Lab behält nur Shift+B. Weil das entschiedene AD-013-Regeln
ändert, kommt vor dem Bauen eine unabhängige Review; eine Frage an dich gibt es dazu nicht — das Verhalten bleibt wie im
Lab (KEEP), nur die blaue Vorschau-Zeile wird zur Statuszeile.

**Nach der unabhängigen Review (2026-10-14, §9):** Frage 4 war unvollständig und ist oben ergänzt. Außerdem: Die
Lab-Sperre (BLOCK) muss den neuen Symmetrie-Schalter der App durchlassen, sonst ließe sich die Symmetrie im Lab nicht mehr
ausschalten; und mit der Anzeige S-2/S-3 braucht ein Schutztest eine engere Formulierung. Beides ist eingearbeitet, an
deinen Fragen 1–3 ändert es nichts.

**Annahmen, die du mit einem Satz korrigieren kannst:** Re-Symmetrize (M) bleibt im Lab. Die Reihenfolge ist: erst
Einschalten und Anzeige in der App, dann die symmetrische Soft Selection (mit der einen Core-Änderung), dann ein gemeinsamer
Praxistest von Extrude und Soft in der App.
