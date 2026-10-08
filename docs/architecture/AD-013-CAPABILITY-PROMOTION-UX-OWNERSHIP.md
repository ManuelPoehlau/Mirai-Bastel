# AD-013 — Capability Promotion ≠ UX Promotion / Artist Input Ownership

**Status:** DECIDED ✓
**Date:** 2026-09-20
**Owner:** Manu (Project Owner)
**Scope:** Playground, Production/Core, future Labs, Artist Input Truth, capability promotion, input/interaction ownership

---

## Question

How are newly developed capabilities, their input bindings, interaction/gesture semantics, and eventual Production UX related?

In particular:

- Does promoting a capability also promote its binding or UX?
- Should a new, not-yet-validated capability be implemented directly in Production?
- How can Playground and future Labs share a common Artist language while still experimenting with deliberate deviations?

## Decision

Mirai separates **capability ownership** from **input, interaction, gesture, and UX ownership**.

> **Capability promotion is not UX promotion.**

Promoting a capability from Playground/experiment into Production/Core means only that the **capability itself becomes a shared production capability**.

It does **not** automatically promote:

- keyboard or mouse bindings,
- gesture semantics,
- press/hold behavior,
- activation/termination behavior,
- interaction model,
- contextual UX,
- HUD presentation,
- or any other Playground/Lab-specific UX decision.

A capability may therefore be Production-ready while its interaction model remains experimental.

---

## Default Lifecycle for New Capabilities

A **new, not-yet-validated capability is an experiment by default**.

Therefore:

> **New / unvalidated capability → Playground / Experiment first.**

An AI agent must not infer Production promotion merely from a request such as:

> "We need a Bevel tool."

The default interpretation is that the new capability should first be implemented and explored in the Playground/appropriate experimental Lab, where the Artist can evaluate its behavior and interaction.

Production/Core promotion requires an **explicit Artist/Product decision**, unless an existing documented Product/Architecture decision already specifies that the capability is Production-owned.

This rule exists so that the Artist does not have to repeat the same instruction for every new capability.

### Existing validated capabilities

If a capability already exists as a validated, documented Production/Core capability, it must be **reused rather than rebuilt experimentally**.

For example:

- an existing validated Move capability remains a shared Production capability;
- a new Bevel capability starts as an experiment unless explicitly promoted otherwise.

This is a lifecycle rule, not a requirement to duplicate implementation.

---

## Capability Promotion Does Not Promote Binding

When an experimental capability is promoted:

```
Playground / Experiment
        ↓
capability validated
        ↓
capability promoted to Core/Production
```

only the capability crosses the boundary.

It does **not** imply:

```
binding → Production
gesture → Production
activation → Production
UX → Production
```

Those remain separate decisions.

This applies to future modeling, rigging, skinning, morphing, animation, and other capabilities.

---

## Shared Artist Language

Mirai has a common Artist input language by default.

The current Artist Input Truth records the intended/common input vocabulary independently from implementation state.

Current documented transform bindings are:

```
transform.move    = Q
transform.rotate  = W
transform.scale   = E
```

The semantic IDs remain stable even if runtime implementation names change.

Artist Input Truth describes **Artist intent**. It must not be rewritten merely because the current code happens to differ.

---

## Context Overrides

Playground and future Labs may deliberately deviate from the common Artist language while experimenting.

A deviation is an **override**, not a mutation of the shared Artist language.

Conceptually:

```
                ARTIST INPUT TRUTH
                       │
                       ▼
                 COMMON BASELINE
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     Playground      Model Lab    Rig Lab
      override       override     override
```

The exact engineering mechanism for implementing this layering is deliberately not decided here.

The important invariant is:

> **Baseline ≠ override ≠ accidental implementation state.**

A successful experiment may later produce a new Artist decision, but that promotion requires an explicit decision.

---

## Artist Input Truth

Artist Input Truth is the authoritative representation of Artist input intent, subject to these rules:

1. Each function has a stable semantic ID, e.g. `transform.move`.
2. A function has one intended primary binding.
3. Multiple functions sharing a physical input remain possible, but the conflict must be explicitly visible.
4. An empty binding means **intentionally unbound**. If the project later needs to distinguish this from "not yet decided", that distinction may be introduced explicitly.
5. Artist Input Truth is not rewritten merely to match implementation.
6. Implementation follows Artist Input Truth unless an explicit override or unresolved discrepancy exists.
7. Changes to Artist Input Truth are Artist/Product decisions, not implementation-driven corrections.

---

## Artist Decisions

### A1 — Shared Artist language

**DECIDED: YES**

Mirai should have a common Artist input language across contexts by default.

### A2 — Contextual deviation

**DECIDED: YES**

Playground and Labs may deliberately deviate from the common language while experimenting. Such deviations are overrides and must not silently redefine the common Artist language.

### A3 — Press/Hold as global rule

**OPEN**

It has not yet been decided whether press/hold/gesture semantics should be global Mirai behavior or remain contextual/research-specific.

No architecture should prematurely force this decision.

*2026-09-27 (WP-06 B3): resolved for Transform only — answered by AD-016 (hold-key-hover, WP-AP-04 KEEP); still open for everything else. See the 2026-09-26 addendum below.*

### A4 — Artist Input Truth as authority

**DECIDED: YES**

Artist Input Truth is the authoritative representation of Artist input intent according to the rules in this document.

### A5 — Capability promotion promotes binding

**DECIDED: NO**

Promoting a capability does **not** promote its binding, interaction model, gesture semantics, or UX.

---

## Architecture Invariants

### I1 — One authoritative capability home

A production capability has one authoritative implementation in the production/core layer.

Labs do not fork the capability implementation merely to experiment with its interaction.

### I2 — Capabilities are input-independent

A capability must not depend on the physical input that invoked it.

Input, constraints, spaces, targets, and interaction context are provided externally.

### I3 — One interaction authority owns start and end

Activation and termination of an interaction belong to the same interaction authority.

### I4 — One binding authority at a time

At any point, exactly one authority determines what a physical input means within the active interaction context.

### I5 — Binding layers are layered, not forked

Context-specific bindings should override or extend a baseline rather than silently creating unrelated copies of the same Artist language.

The precise mechanism remains an Engineering decision.

### I6 — Overrides remain visible

An experimental deviation must remain identifiable as an override.

An experiment must not silently mutate the shared Artist language.

### I7 — Capability promotion and UX promotion are independent

Promoting a capability to Production does not promote its binding, interaction, gesture semantics, or UX.

### I8 — Artist intent and implementation state are separate

The current code is evidence of implementation state. It is not automatically evidence of Artist intent.

---

## Activation and Termination

Activation and termination belong to the same interaction authority.

The architecture must not split:

```
START → authority A
END   → authority B
```

without an explicit, well-defined contract.

This prevents binding, activation, and release semantics from becoming mismatched.

---

## Gesture Semantics Remain Open

This decision does not establish a global rule for:

- press,
- hold,
- release,
- drag,
- modifier timing,
- or other gesture semantics.

These remain valid Playground/Lab research topics until the Artist has enough evidence to decide.

A successful experiment does not automatically become a global UX rule.

---

## Engineering Freedom

This AD intentionally does not prescribe:

- class structure,
- event architecture,
- dispatcher implementation,
- exact BindingSet implementation,
- whether Playground should use ToolManager,
- exact command-routing implementation,
- the final mechanism for shared baseline + context overrides,
- or a universal gesture system.

Engineering may choose the simplest implementation that satisfies the invariants.

The project should not build a larger mechanism merely because a future Lab might eventually need it.

---

## Sequencing Principle

The immediate goal is not to solve every future Lab input problem.

The project should:

1. preserve one clear binding/interaction authority;
2. preserve shared capability reuse;
3. keep Artist Input Truth separate from implementation state;
4. allow contextual experimentation;
5. introduce shared baseline mechanisms only when evidence requires them.

The existence of a future Lab is not by itself sufficient reason to build its complete input architecture today.

---

## Relationship to AD-011

AD-011 remains historical documentation of the Playground's deliberate independence from Production UX.

This AD makes the distinction explicit:

> **Capability sharing concerns implementation reuse. Playground/Lab independence concerns interaction and UX.**

These are compatible and are not to be conflated.

---

## Consequences

### Positive

- New capabilities have a predictable experiment-first lifecycle.
- Manu does not need to repeat "test this in Playground first" for every new capability.
- Production capabilities can be reused without inheriting experimental UX.
- Playground/Lab experimentation cannot silently redefine Artist input truth.
- AI agents have an explicit rule against assuming capability promotion implies input promotion.
- Artist intent remains distinguishable from implementation state.

### Costs

- Capability promotion and UX promotion must be tracked separately.
- Some interaction decisions remain deliberately unresolved.
- Context overrides require explicit representation.
- A Production capability may temporarily have experimental/context-specific UX.

These costs are accepted because premature UX coupling has already demonstrated architectural risk.

---

## Non-Goals

This AD does not:

- define the final Mirai keymap;
- decide press vs. hold;
- define final Production UX;
- define a universal gesture system;
- require every Lab to use identical controls;
- require every Playground behavior to become Production behavior;
- require a new binding framework;
- or require immediate refactoring of existing infrastructure.

---

## Canonical Product Truth

> **Das Verschieben einer Capability nach Production bedeutet ausschließlich die Übernahme der Fähigkeit selbst. Binding, Interaction, Gesten und UX bleiben zunächst beim Playground bzw. jeweiligen Lab und werden erst durch eine spätere bewusste UX-Entscheidung nach Production übernommen.**

And:

> **Neue, noch nicht validierte Capabilities werden standardmäßig zuerst im Playground bzw. im entsprechenden Experiment untersucht. Eine Production-Promotion erfolgt erst durch eine explizite Entscheidung oder einen bereits dokumentierten Product-/Architecture-Entscheid.**

These rules are canonical for future architecture decisions, implementation tasks, AI-agent prompts, and code reviews.

---

## Addendum (2026-09-26, WP-06 Stage B, Slice B1)

Manu decided a new Artist Input Truth for transform bindings (recorded in
`tools/Input_Mapping_Tool/artist_input_truth.json`):

```
transform.move    = W   (was Q)
transform.rotate  = E   (was W)
transform.scale   = R   (was E)
topology.extrude  = T   (was R; implementation follows in a later slice)
```

`Q` is no longer bound. `application.quit` stays unbound (binding `""`);
the window is closed via the window's X button only.

Per this AD's own rules (§ Artist Input Truth, rule 6/7), this is an Artist
Input Truth change — implementation follows it, not the other way round.
As of this addendum, that implementation has **not** yet happened
everywhere, and both discrepancies are intentionally recorded rather than
silently left inconsistent:

- Production `src/mirai/interaction/bindings.py::build_default_bindings()`
  still returns q/w/e. Aligning it with this addendum is WP-06 Slice B3
  (Move + Undo/Redo), not this slice (B1).
- Playground (AD-016, `playground/`) still uses Q/W/E for Transform. This
  is an **open, recorded discrepancy** between Playground and the new
  Artist Input Truth — not in WP-06's scope, and no decision about closing
  it has been made here.

WP-06 Slice B2 (2026-09-26): Manu changed `navigation.pan` from Shift+LMB to
Alt+Shift+LMB (drag); this resolves the recorded Truth conflict Shift+LMB
(pan vs. `selection.add`). Alt+LMB now carries drag = orbit and click =
`selection.toggle` — an intended, noted overlap resolved by AD-019.

WP-06 Slice B3 (2026-09-27): production `build_default_bindings()` now follows
this addendum (GLOBAL `w` → Move, `e` → Rotate, `r` → Scale; `q` unbound), and
the production Move mechanism is the Transform Lab's AD-016-decided
hold-key-hover model (WP-AP-04 KEEP), not a Symmetry-Lab-style separate drag.
Artist decision (Manu, 2026-09-27): the Symmetry Lab takes over the same
controls — W and hold-key-hover, no lab key override — replacing its own
Slice-3 arm-then-LMB-drag gesture (Q, KEEP 2026-09-25). The Playground
runtime (AD-016 itself) still uses Q/W/E for its own hotkeys — unchanged, still
an open discrepancy. A3 (press vs. hold as a general input-ownership question)
is answered for Transform by AD-016 and is resolved for that scope only; it stays
open for everything else.

## Addendum (2026-10-03, WP-SYM-LAB-03 H2 — experiment input hook in `Application`)

**Status:** DECIDED ✓ (2026-10-03). Revised twice after independent reviews, both archived
unedited and answered in § Review below:
[CLAUDE-001](../archive/symmetry_lab/reviews/AD-013_H2_ADDENDUM_REVIEW_CLAUDE_001.md) (first draft,
hook F → replaced by the reviewer's data-only command gate **G**) and
[CLAUDE-002](../archive/symmetry_lab/reviews/AD-013_H2_ADDENDUM_REVIEW_CLAUDE_002.md) (revision with
deviations D1–D3; ACCEPT WITH CHANGES, no blockers; N1–N3 answered by adopting the reviewer's own
changes). Implementation follows the plan's Slice 1 and Slice 3.
**Basis:** Artist decision (Manu, 2026-10-03): the Symmetry Lab must use the Production tools
instead of its own renderer and input layer; Symmetry itself is not promoted (`src/main.py`
gets no symmetry UX). Plan: `WP-SYM-LAB-03_REBASE_PLAN.md`, hook H2.

### Problem

The Symmetry Lab (`experiments/symmetry_lab/`) is to run on the Production input path:
pyglet event → `mirai.pyglet_input` → `Application` (`src/mirai/application.py`). Today
`Application` is the only interaction authority on that path. It resolves bindings in the
GLOBAL context only (plus `knife` during a Knife session, `key_press`, `application.py:993`),
recognises click vs. drag itself (`PointerGestures`, AD-019; clicks executed in
`_execute_click`, `:1440`) and drives hover or the armed transform from
`pointer_motion` (`:1345`). Nothing outside it can take part.

The Lab needs three things that `Application` cannot provide without symmetry knowledge:

1. **Own commands:** Shift+S (symmetry cycle), M (Re-Symmetrize), Shift+B (E5 gate mode).
   These are bound in the Lab context `symmetry_lab`, are free in GLOBAL, and stay out of
   `mirai.interaction.commands`.
2. **Pre-empting app commands under symmetry:** refusing C (contextual C / Knife run one-sided
   under symmetry, INV-8 in AD-SYM-02 §2.3), and refusing W/E/R/C in the E5 BLOCK mode
   (an open Artist question, AD-SYM-02 §4).
3. **A modal Lab interaction:** the Re-Symmetrize preview. While it is open, navigation keeps
   working, but select clicks, W/E/R, C, Shift+S and Undo/Redo are ignored with a hint, and
   the hover pauses (Slice 5 KEEP, 2026-09-25).

Without a defined entry point the only option is what the Lab does today: a second input
layer (`LabDispatcher`) that re-implements gestures, arming, hover and undo. That has
already drifted from `Application` (W ignores constraints, Undo clears instead of restoring
the selection). It also breaks I1 in spirit ("Labs do not fork the capability implementation
merely to experiment with its interaction"). The invariants at stake are I3 (one interaction
authority owns start and end), I4 (one binding authority at a time), I6 (overrides remain
visible) and the Activation and Termination rule above.

### Alternatives

| | Alternative | Assessment |
|---|---|---|
| 0 | Keep the Lab's own dispatcher (status quo) | Not used: it is the drift source; every app input fix needs a Lab copy |
| A | Subclass `Application` in the Lab and override `key_press`, `_execute_click`, `pointer_motion` | Not used: couples the experiment to private methods, so an `Application` refactor would change Lab behaviour without any signal. It is a fork of the interaction authority in disguise (I1, I3) |
| B | A facade in front of `Application` at window level | Not used for pointers: blocking a select click but not an Alt+LMB orbit needs the click-vs-drag decision `PointerGestures` makes inside `Application`, so a facade would re-implement it. Workable for keys only — G uses exactly that part for the Lab's own keys |
| C | `Application` resolves an "active context" and hands unknown commands to the Lab (fallback only) | Not used: adds commands but cannot pre-empt any. Needs 2 and 3 are not covered |
| D | Promote the symmetry UX into `src/main.py` behind a flag | Not used: promotion is the Artist's decision and was deferred (ROADMAP §7, 2026-10-02); I7 |
| E | A general extension/plugin system (command registry, event bus, overlay providers) | Not used: § Engineering Freedom and § Sequencing Principle above; INPUT_COMMAND_TOOL_CONTRACT §3 ("no complex hierarchical context framework without a demonstrated use case") |
| F | One optional hook object (callback), consulted first at three call sites (`key_press`, `_execute_click`, `pointer_motion`) — the first draft of this addendum | **Not used** (below) |
| **G** | **Data-only command gate in `Application` + Lab keys at window level** (review CLAUDE-001, F9) | **Chosen** (below), with the additions both reviews ask for and the deviations D1–D3 |

**F is not used because** (review F1, F3, F4, F9):

1. Its precedence relative to `Application`'s own gates exists only as the branch order
   "hook first", so the rules had to restate `Application`'s gating — and the first draft
   restated it wrongly: it made the hook back off during camera gestures, during which
   `Application` gates no keys, so Undo and W ran under the open preview (F1, verified by the
   reviewer's probe P1). G places the check *after* `Application`'s own routing, so precedence
   is `Application`'s by construction.
2. Its `pointer_motion` call site cannot pause hover: zoom and refreshes re-pick hover on paths
   the hook never sees (F3, probe P2).
3. A callback that receives raw events can do anything with them, so I1 and I3 were held only by
   rules (R2, R4) that are hard to test and whose key predicate was undefined (F4, the AD-015
   failure mode). G's `Application`-side contract is two lookups and one flag, tested as data.

F would cover cases G cannot (see § Limits of G); none of them is a stated need, and needing
one later is a new review of this addendum (H2-R6).

### Decision

H2 is a **command gate**, not a callback. `Application` calls no experiment code. It gets
these additions, all inert by default (working names; the Python shape stays open):

| Addition | What | Where it acts |
|---|---|---|
| `command_gate` (default `None`) | One value holding `refused: dict[command, status text]` (block-list), `allowed: frozenset[command] \| None` (allow-list, `None` = no allow-list) and `not_allowed_text`. A command is refused if it is in `refused` (its text) or if `allowed` is set and does not contain it (`not_allowed_text`). Replaced as a whole on every Lab state change, never mutated in place | `key_press`: right after `command = self.bindings.command_for(input)` (`application.py:999`), i.e. after the Knife routing (`:997-998`) and before every branch. `_execute_click` (`:1440`): before `select_at`, for the click command. A refused event posts the text through `Application`'s own status (`status_serial` + 1) and returns `False`. An unbound input (`command is None`) is never refused |
| `hover_suspended: bool` (default `False`, initialised through its backing field because `viewport` is `None` until `init_scene()`) | Setting it `True` clears `selection.hovered` (viewport notified); while it is set, `_update_hover` (`:1388`) only keeps hover cleared; setting it `False` re-picks at the last cursor (`_refresh_hover`) | `_update_hover`, which every hover path goes through: motion, zoom (`:1340`), the refresh after Undo/Redo, commit, cancel and `apply_mesh_change` |
| `interaction_owner` (read-only) | `"transform"` while a transform is armed or running (`transform_command is not None`), `"knife"` while a Knife session runs (`knife_active`), else `None`. Camera gestures are **not** owners | Read by the Lab (H2-R2) |
| `set_status(message)` (plan hook H4) | Public alias of `_set_status` (`:1278`), same `status_serial`; the internal name and its call sites stay | The Lab's own refusals and messages |
| `apply_mesh_change(description, mutate)` (plan hook H3; review CLAUDE-002 N1) | The one entry for a mesh change produced outside `Application`. `mutate: Callable[[], set[VertexId] \| None]` performs the change through core operations and returns the moved vertex IDs (positions only) or `None` (topology changed). `Application`, in order: (1) raises if `interaction_owner` is not `None` (D3, before any change); (2) snapshots the selection and `mesh.export_state()`; (3) calls `mutate()` — if it raises, the mesh is restored from the snapshot (`load_state`) and the exception propagates, so no half change survives; (4) if `export_state()` is unchanged, records nothing and returns `False` ("0 changes = no entry"); else (5) pushes one `MeshStateCommand(description)`, (6) records the selection-mirror entry, (7) invalidates the pick cache, (8) notifies the viewport (`on_vertices_moved(moved)` or `on_topology_changed()`), (9) re-picks hover, and returns `True`. The selection snapshot format stays private | Re-Symmetrize, the symmetry cycle |

There are deliberately **no** gate checks in `key_release` (a refused press arms nothing, so
its release is already a no-op, `:1036`), `pointer_press`/`pointer_drag`/`pointer_scroll`
(navigation is never gated), `pointer_motion` (hover is handled by the flag; a transform step
can only run for a transform the gate let `Application` arm), `pointer_leave`,
`set_shift_held`, or `dispatch_command` (the Lab may not call it, H2-R4; `Application`'s
internal calls happen after the gate).

**Lab side (experiment code, window level).** The Lab's own keys are resolved before
`Application` sees the event, through the one `BindingSet`. The step is a pyglet-free function
`lab_key_press(app, lab, input) -> bool`, so it is testable headless like `Application`
(review CLAUDE-002 N4):

```text
key press:   cmd = app.bindings.command_for(input, "symmetry_lab")   # GLOBAL fallback
             cmd is a Lab command:
                 app.interaction_owner is set     -> refused visibly            (H2-R2)
                 preview open and cmd != M        -> refused visibly            (H2-R2, N2)
                 otherwise                        -> the Lab runs it
             preview open and cmd == Cancel       -> the Lab closes the preview  (D1)
             otherwise                            -> app.key_press(input), then the Lab
                                                     re-derives its symmetry state (H2-R2)
key release, pointer events                       -> Application, unchanged
pyglet on_key_press                               -> always EVENT_HANDLED, as src/main.py:168-170
```

The Lab writes `command_gate` and `hover_suspended` only on its own state changes, from one
static table (printed at start-up, H2-R3). **The preview row dominates:** while the preview is
open no other row is installed, whatever the symmetry or E5 state (review CLAUDE-002 N2).

| Lab state | `command_gate` | `hover_suspended` |
|---|---|---|
| symmetry off | `None` | `False` |
| symmetry on, Slice 1 (before E5) | refused: `Connect` → `Symmetrie aktiv — C spiegelt nicht` | `False` |
| symmetry on, E5 MARK (Slice 4) | `None` (one-sided C allowed, HUD marks it) | `False` |
| symmetry on, E5 BLOCK (Slice 4) | refused: `Connect` and every transform command E5 counts as unsupported (`supports_symmetry`) | `False` |
| Re-Symmetrize preview open (Slice 3) | allowed: display commands only (`CycleDisplayMode`, `ToggleWireframeOverlay`, `SetShaded`, `SetFlatShaded`, `SetWireframe`); `not_allowed_text` = `Vorschau aktiv — Befehl ignoriert` | `True` |

Every other command, including any app command added in future, is refused during the preview
by default (F7). Navigation needs no entry: drags and the wheel are never gated.

**Precondition:** H3 (`apply_mesh_change`) and H4 (`set_status`) land with or before the gate
(Slice 1). Without H4 the Lab's own refusals could not be visible (F10); without H3 a Lab
mutation desynchronises Undo (F2).

### Deviations from G as proposed

G as proposed in review CLAUDE-001 F9, plus the review's own change requests (F2 commit entry,
F4 `interaction_owner`, F6/F15 exact Lab context with start-up assert, F7 allow-list, F8
start-up listing, F10 status setter), is adopted. This revision differs from it here
(all three reviewed in CLAUDE-002: D1 and D2 sound, D3 sound in intent and moved before the
mutation, N1):

- **D1 — Esc closes the preview at window level.** G routes only Lab-context commands to the
  Lab, so Esc (GLOBAL `Cancel`) would reach `Application`, be refused by the preview allow-list,
  and the preview could not be closed by Esc (S5 KEEP: M / M / Esc). Esc cannot get a Lab-context
  entry: it is bound in GLOBAL (start-up assert, F15), and a permanent Lab Esc would shadow
  `Application`'s Cancel for armed transforms. So the window step takes the resolved `Cancel`,
  and only while the preview is open. This is safe: while the preview is open,
  `interaction_owner` is `None` (H2-R2), so `Application`'s `_cancel` would be a no-op
  ("idle → nothing", `:1145-1149`); nothing `Application` owns is ended or stolen. Meaning still
  comes from the one `BindingSet` (I4). Test T-R2e.
- **D2 — the start-up assert also covers the KNIFE context.** The Lab step runs before the Knife
  routing, so a Lab key would shadow a future KNIFE binding as well as a GLOBAL one (F15 names
  GLOBAL only). Stricter than proposed.
- **D3 — `apply_mesh_change` raises while `interaction_owner` is set, before anything
  changes.** F2 names the entry; the guard makes H2-R2 ("no Lab mutation during an
  `Application` interaction") fail loudly in code instead of holding only by rule. CLAUDE-002 N1
  showed that the first form (`record_mesh_change`, called after the Lab had mutated) fired after
  the damage; `Application` now runs the mutation itself, after the check.

Because of D1 (D2 and D3 only tighten), this revision got a second independent review
(CLAUDE-002) before DECIDED.

### Limits of G

G refuses by command identity only. It does not cover: refusals that depend on more than the
command (click position, part of the selection, mirror side); refusing input inside a Knife
session (the check sits after the Knife routing); a Lab reaction that must run *instead of* an
`Application` command with the original event (D1 is the one exception, and only for an idle
`Application`). None is a stated need. Any of them reopens this addendum (H2-R6).

*Note 2026-10-08:* AD-SYM-03 (DECIDED) states the first such need: refusing `C` by its resolved
context. An amendment that lifts exactly that item is **DECIDED** (Manu, 2026-10-08); see
§ Addendum (2026-10-08) below. That item ("part of the selection", for `C` by its resolved context) is no
longer a Limit; everything else in this section stands unchanged.

### Rules

- **H2-R1 — one binding authority (I4, I5, I6).** The Lab resolves its keys only through
  `app.bindings`, the one `BindingSet`, with its context `symmetry_lab` and GLOBAL fallback, and
  creates no second resolver. The Lab context holds **exactly three entries, all keys:**
  Shift+S → `SymmetryCycle`, M → `ReSymmetrize`, Shift+B → `SymmetryGateMode`. There are no
  pointer entries: `Application` resolves pointer input without a context (`application.py:266`,
  `pointer.py:94-95`), so pointer overrides are impossible under H2 (the current Lab's `C`,
  Alt+LMB, Shift+LMB, RMB and MMB entries are dropped, F6). At start-up the Lab asserts that each
  of the three inputs resolves to `None` in GLOBAL and in KNIFE (user and default layers) and
  fails loudly otherwise (F15, D2). The three entries are printed at start-up. The only app
  command the Lab interprets is `Cancel`, and only while the preview is open (D1).
- **H2-R2 — start and end stay with their owner (I3, AD-015 runtime-state rule).**
  *Key-owning interactions* are: `Application`'s armed or running transform and its Knife
  session (exactly `app.interaction_owner is not None`), and the Lab's Re-Symmetrize preview.
  **Camera gestures (orbit, pan, zoom) own no keys:** `Application` does not gate keys during
  them (`application.py:993-1029`), and the command gate applies during them as at any other
  time (F1). Consequences:
  - The Lab opens the preview only while `interaction_owner` is `None`, and only the Lab ends it
    (M executes, Esc cancels, closing the window ends it). While it is open, the gate allows only
    display commands, so `Application` cannot start a key-owning interaction; the two never
    overlap.
  - **While the preview is open, the Lab executes no Lab command except M (execute); Shift+S and
    Shift+B are refused visibly (`set_status`), and the gate stays on the preview row until the
    preview ends.** Installing any other row while the preview is open is a programming error
    and asserts. This premise carries D1: if the preview row could be replaced, W could arm under
    the open preview and Esc would close the preview instead of cancelling the Move (review
    CLAUDE-002 N2, reproduced by probe).
  - While `interaction_owner` is not `None`, the Lab executes none of its commands (refused
    visibly) and writes neither the gate nor the hover flag nor history. The gate is therefore
    constant for the whole lifetime of an `Application` interaction: it can stop `Application`
    from *starting* something, but never ends, alters or steals what runs.
  - Outside the preview the gate refuses only commands that start an interaction or change the
    mesh (Connect; transform commands in BLOCK). It never refuses `Cancel`.
  - Lab mesh changes go through `apply_mesh_change` only (D3 enforces the timing).
  - The Lab's symmetry state is read from `mesh.symmetry_definition` (part of
    `export_state()`, so `Application`'s Undo/Redo restores it), never cached. After every key
    event forwarded to `Application` the Lab re-derives it and re-installs the matching gate row
    if it changed. Otherwise Ctrl+Z over a symmetry cycle would leave a stale row, e.g. symmetry
    back on with C no longer refused (INV-8). It installs a row only while `interaction_owner`
    is `None` and the preview is closed. That loses no change: a running transform ignores
    Undo/Redo (E23), an armed-only one is disarmed before Undo runs (`:1023-1029`, so the owner
    is `None` afterwards), a Knife session undoes in its isolated history (AD-017,
    `dispatch_command` `:454-457`), and the preview row refuses Undo/Redo.
- **H2-R3 — refusals are visible and listed (I6).** Every refused event posts a status message
  (`status_serial` + 1, also for a repeated identical text): `Application` does it for the gate,
  the Lab through `set_status` (H4) for its own commands. Nothing is swallowed silently. The
  gate table per Lab state (above) is printed at start-up next to the three binding entries,
  because a refusal deviates from the Artist language like a rebinding does (F8).
  The listing also prints D1's contextual meaning: `Cancel (Esc): closes the Re-Symmetrize
  preview while it is open` (CLAUDE-002 N8).
  **Return contract (F13, N4):** refused input returns `False` ("the model did not change"), like
  `Application`'s own gates (`:1011-1012`, `:1017-1018`); a Lab command that ran returns `True`,
  a refused Lab command `False`; Esc that closes the preview (D1) returns `True`; allowed
  commands return what `Application` returns today. The pyglet handler around `lab_key_press`
  returns `EVENT_HANDLED` in every branch, as `src/main.py:168-170` does, so pyglet's default
  handler never closes the window on Esc.
- **H2-R4 — no capability fork; public allow-list (I1, F5).** Lab code may use only:
  (a) read-only state — `selection`, `scene`/mesh (written only inside a `mutate` passed to
  `apply_mesh_change`, through core operations), `camera`, `display`, `history.can_undo()`/
  `can_redo()`, `interaction_owner`, `transform_command`, `knife_active`, `status_message`/
  `status_serial`, and `bindings` (read, plus `set_default` for its own context at start-up);
  (b) the gate data — `command_gate`, `hover_suspended`; (c) `set_status` (H4);
  (d) `apply_mesh_change` (H3); (e) the public event entry points (`key_press`, `key_release`,
  `pointer_*`), called only from the window adapter with the original event; plus the Viewport
  overlay hook H1;
  (f) one-time setup before the event loop, as `src/main.py` does it: `init_scene`,
  `frame_scene`, `set_viewport_size` (clarification 2026-10-03, Slice 1b; only in the Lab's
  entry `run_app.py`, checked by T-R4a). **Not allowed:** `dispatch_command`, `select_at`, any member with a leading
  underscore, `history.push`, and importing `PointerGestures`, `ToolManager` or `pick_component`
  for app semantics. No own gesture recognition, transform arming, picking for app semantics or
  undo bookkeeping.
  *Note 2026-10-03 (WP-SYM-LAB-03 Slice 5): `run_app.py` is renamed to `run.py`; (f) now names `run.py`.*
- **H2-R5 — Production is unchanged.** With the defaults (`command_gate is None`,
  `hover_suspended is False`) behaviour is identical; `interaction_owner`, `set_status` and
  `apply_mesh_change` are additive. `src/main.py` writes no gate data and calls neither
  `apply_mesh_change` nor `set_status` (guard test).
- **H2-R6 — one writer (governance, not a test, F14).** The gate has one writer: the Symmetry
  Lab's window wiring. There is no list, stack or registry of gates. A second user (another Lab,
  the Playground) needs its own review of this addendum; it does not get to extend the gate
  silently. Code review enforces this; a test could only assert a type, which proves nothing.

### Required tests

Headless, through `Application`'s public entry points, fixture as in
`tests/test_application_pointer.py:34-40`; sequences from review CLAUDE-001 Q4 and the appendix
probes, with the CLAUDE-002 corrections (N3, N5–N7). Lab-side tests drive the pyglet-free
`lab_key_press` (N4). `src` tests go to `tests/`, Lab tests to `experiments/symmetry_lab/tests/`.

| ID | Rule | Test |
|---|---|---|
| T-R1a | R1, N7 | The Lab context contains exactly {key Shift+S, key M, key Shift+B} and no pointer entry; after Lab start-up GLOBAL and KNIFE resolve every input exactly as `build_default_bindings()` does |
| T-R1b | R1, F15, D2 | Each of the three resolves to `None` in GLOBAL and KNIFE; with a user GLOBAL binding on Shift+S the Lab start-up raises |
| T-R1c | R1 | The Lab holds `app.bindings` by identity; building the Lab creates no further `BindingSet` (counter on `BindingSet.__init__`) |
| T-R1d | R1, R3, F8 | The start-up listing returns every Lab entry and every gate-table row |
| T-R2a | R2 | Arm W, press M → returns `False`, status posted, `transform_command == MOVE`; release W commits one history entry |
| T-R2b | R2, N5 | Symmetry **off** (the Slice 1 row refuses C): C with empty selection starts a Knife session; Shift+S → refused, `knife_active` stays `True`; then E → pen lifted (`knife_render_data.start_point is None`) |
| T-R2c | R2, **F1** | Preview open → Alt+LMB press, drag 10 px (`pointer.active`) → Ctrl+Z returns `False`, history unchanged, status posted; W → `transform_command is None` |
| T-R2d | R2, F4 | `interaction_owner` is non-`None` in every state where `Application`'s own gates apply (armed, running, Knife) and `None` idle and during an orbit/pan |
| T-R2e | R2, D1, N2 | Preview open; W, E, R, C, Ctrl+Z, 1/2/3, X, Alt+A, a select click → all refused, `interaction_owner` stays `None`; Shift+S and Shift+B → refused, `command_gate` unchanged (still the preview row); Esc → returns `True`, closes the preview, no history entry, gate and hover flag back to the row of the current symmetry state |
| T-R2f | D1, **N3** | **No preview**, through `lab_key_press`: arm W (selection or hover), Esc → `transform_command is None`, status `Move disarmed`; symmetry off, C with empty selection, Esc → `knife_active is False`. A Lab that intercepted Cancel unconditionally fails this test |
| T-R2g | D1, R2 | Seeded fuzz (probe D1a of CLAUDE-002, fixed seeds): random key/click/drag/wheel/motion sequences under the open preview → after every event `interaction_owner is None`, no active tool, hover `None`, selection, history and mesh unchanged |
| T-R2h | R2 | Symmetry on (C refused) → Shift+S cycles to off and back on … → Ctrl+Z over a cycle step → the gate row matches `mesh.symmetry_definition` after each Undo/Redo |
| T-R3 | R3 | Parametrised over (Lab state × refused command, key and click): return `False`, `status_serial` + 1, `status_message` equals the row's text; twice the same refusal → two increments |
| T-H | F3, N5 | Face mode set *before* the preview opens (3 is refused under it); preview open → hover `None`; motion over a vertex → still `None`; one wheel step (probe P2) → still `None`; preview closed → hover re-picked at the cursor |
| T-R4a | R4 | Static: AST scan of the Lab modules for underscore attributes on `Application` objects, `dispatch_command`, `select_at`, `history.push`, and imports of `PointerGestures`, `ToolManager`, `pick_component` |
| T-R4b | R4, F5, N6 | The Lab suite runs with `Application.dispatch_command` and `select_at` patched to raise when their **immediate** caller (`sys._getframe(1)`) is a Lab module; `key_press` calling `dispatch_command` with a Lab frame further up the stack is legitimate |
| T-R4c | R4, **F2**, N1 | Probe P3 through the Lab path: select A → W-move → select B → Shift+S (Lab commit via `apply_mesh_change`) → Ctrl+Z → selection is {B}; Ctrl+Z again → {A}. A `mutate` that changes nothing → returns `False`, no history entry |
| T-R4d | F2 | After a Lab mesh change, hover and a click pick the *new* vertex positions (pick cache invalidated) without any camera change |
| T-R4e | D3, N1, N5 | `apply_mesh_change` raises while a transform is armed and while a Knife session runs, without calling `mutate`; mesh `export_state()`, history and mirror stacks unchanged. A `mutate` that raises midway → mesh restored to the snapshot, no history entry, exception propagates |
| T-R5a | R5 | `Application()` has `command_gate is None`, `hover_suspended is False` |
| T-R5b | R5 | AST guard: `src/main.py` never assigns `command_gate`/`hover_suspended` and never calls `apply_mesh_change`/`set_status` |
| T-R5c | R5 | **Pass-through run:** every `tests/test_application_*` re-run with an *inert but active* gate installed on each new `Application` (`allowed` = every command constant in `mirai.interaction.commands`, N7; `refused` = {an unused sentinel command}) → identical results; negative control: an empty allow-list must make tests fail (CLAUDE-002: 412 passed vs. 303 failed on its emulation). Proves the check code path changes nothing, not only the `None` case |

R6 has no test (governance, F14).

### Consequences

- **Positive:** the Lab runs on the same gestures, arming, constraints, hover, picking and undo
  as the app; for app input, drift becomes impossible by construction. Lab mesh changes keep
  Undo's selection mirror and the pick cache correct because `Application` itself takes the
  snapshots and records them in `apply_mesh_change` (T-R4c, T-R4d); that the Lab uses it is a
  rule plus tests (R4, T-R4a), not construction.
  Precedence between the gate and `Application`'s own gates is `Application`'s branch order,
  not a second layer. Lab behaviour is testable headless through `Application`'s entry points.
- **Costs:** two lookups and one flag check in `Application`'s input path, four small public
  additions, and one window-level step in the Lab. An `Application` change can break Lab tests;
  that is intended, as the signal the drift lacked. Pointer overrides in the Lab are impossible:
  MMB pan and the Lab's other mouse entries disappear (a visible change, plan §4.3).
- **Key repeat:** suppressed by the pyglet adapter for `Application` and the Lab alike (pyglet
  2.1.16 dispatches no `on_key_press` for auto-repeat on Win32, Cocoa or X11, review F11). The
  repo pins no pyglet version; if one is pinned later, an adapter test follows.
- **Focus loss (F12):** W held + Alt-Tab leaves the transform armed (pre-existing,
  `on_deactivate` resets only Shift, `src/main.py:180-185`). Under H2 the Lab then refuses its
  commands until W is pressed and released again. Not fixed here (outside H2). The preview is
  Lab state: it survives focus loss and ends with the Lab window, which resets the gate;
  `Application.shutdown` needs no knowledge of it.

### Not decided here

The Python shape (dataclass or plain attributes) and final names; whether the Playground could
use such a gate (H2-R6); any gesture semantics (A3 stays open); any Artist Input Truth (the Lab
keys stay Lab overrides); anything in § Limits of G.

### Review

**First independent review:**
[AD-013_H2_ADDENDUM_REVIEW_CLAUDE_001.md](../archive/symmetry_lab/reviews/AD-013_H2_ADDENDUM_REVIEW_CLAUDE_001.md)
(fresh session, `main` @ `bafae30`, archived unedited). Verdict: ACCEPT WITH CHANGES, blockers
F1 and F2. Outcome: hook F replaced by the reviewer's proposal G (F9) with the requested
additions; deviations D1–D3 above.

| Finding | Severity | Answer |
|---|---|---|
| F1 — R2 lets app commands through during navigation inside the preview | BLOCKER | **Fixed in the revised text.** H2-R2 defines key-owning interactions; camera gestures own none. The gate sits in `key_press` after resolution and applies during camera gestures, so Ctrl+Z/W mid-orbit are refused under the preview. Test T-R2c |
| F2 — Lab mutations desync the selection mirror and the pick cache | BLOCKER | **Fixed in the revised text.** An external-commit entry (plan H3) is part of the Decision and a Slice 1 precondition; H2-R4 forbids `history.push` from Lab code; D3 guards the timing. The "drift impossible by construction" claim is narrowed in § Consequences. Tests T-R4c (probe P3), T-R4d. *CLAUDE-002 N1 found the first form (`record_mesh_change`) unusable without a private format; now `apply_mesh_change`, see below* |
| F3 — consuming `pointer_motion` does not pause hover | SHOULD | **Fixed.** The `pointer_motion` call site is dropped; `hover_suspended` is honoured in `_update_hover`, so motion, zoom and refreshes all respect it; `Application` keeps updating `_cursor`. Test T-H (probe P2). Replacing hover picking with Lab semantics stays out of scope (not a need) |
| F4 — R2's back-off condition undefined | SHOULD | **Fixed.** Read-only `interaction_owner` (`None` / `"transform"` / `"knife"`), the single predicate in H2-R2. Test T-R2d |
| F5 — R4 permits public calls that start or alter app interactions | SHOULD | **Fixed.** H2-R4 is an allow-list; `dispatch_command`, `select_at` and `history.push` are excluded. Tests T-R4a (static), T-R4b (patched) |
| F6 — the existing Lab context is incompatible; R1 does not fix the entry set | SHOULD | **Fixed.** H2-R1 fixes the set to three key entries and states that pointer overrides are impossible; the current `C` and mouse entries are dropped in the new host (the old `run.py` is unchanged until Slice 5). MMB pan loss recorded as a visible change (plan §4.3). Test T-R1a |
| F7 — the preview gate is a block-list with gaps | SHOULD | **Fixed.** The preview row is an allow-list (display commands only); every other command, including future ones, is refused by default. The open question whether a selection change invalidates the preview becomes moot: selection changes are refused. Test T-R2e, T-R3. *CLAUDE-002 N2: the Lab's own Shift+S/Shift+B were not covered; now refused during the preview (H2-R2)* |
| F8 — refusals must be listed like bindings | SHOULD | **Fixed.** The gate table per Lab state is printed at start-up (H2-R3). Test T-R1d |
| F9 — a smaller, data-only mechanism (G) | SHOULD (Q2) | **Adopted**, with deviations D1–D3 (§ Deviations from G). "F is not used because …" is recorded under § Alternatives. G's own limits are recorded in § Limits of G |
| F10 — R3 depends on a status setter that does not exist yet | NIT | **Fixed.** H4 is a named precondition in the Decision and moves from Slice 2 to Slice 1 in the plan |
| F11 — the key-repeat cost is probably moot | NIT | **Fixed.** The cost line is replaced (§ Consequences, "Key repeat"). No adapter test: no pyglet version is pinned |
| F12 — focus loss | NIT | **Fixed in the text** (§ Consequences, "Focus loss"): the stuck-armed case is described and the preview's lifetime is tied to the Lab window. **Not fixed in code:** the stuck-armed transform is pre-existing `src/main.py` behaviour outside H2 |
| F13 — return-value contract | NIT | **Fixed.** H2-R3 states it. Test T-R3 |
| F14 — R4 and R6 are only partly testable | NIT | **Fixed.** The claim "each is testable" is removed; R4 is tested statically and behaviourally, R6 is stated as governance |
| F15 — the Lab context silently shadows user GLOBAL bindings | NIT | **Fixed.** Start-up assert in H2-R1, extended to the KNIFE context (D2). Test T-R1b |

Review Q3 (call sites): followed — no hook on `key_release`, `pointer_press`/`drag`,
`pointer_scroll`, `pointer_leave`, `set_shift_held`; the motion site is replaced by the flag;
`dispatch_command`/`select_at` are off-limits (H2-R4). Q4 (tests): taken over as
§ Required tests, adapted to G (the pass-through run uses an inert-but-active gate instead of a
hook returning `False`). Q5 (`src/main.py`, line references): no change needed; the guard test
is T-R5b.

**Second independent review:**
[AD-013_H2_ADDENDUM_REVIEW_CLAUDE_002.md](../archive/symmetry_lab/reviews/AD-013_H2_ADDENDUM_REVIEW_CLAUDE_002.md)
(fresh session, `claude/intelligent-ride-irx6ku` @ `366042f`, archived unedited). Verdict:
ACCEPT WITH CHANGES, **no blockers**. D1 sound (probes: owner `None` over 40 × 400 random events
under the preview; idle Cancel a no-op in 11 059 reached states), D2 sound, D3 sound in intent but
too late (N1). I1, I4, I6 upheld; I3 upheld given N2. F2 and the Lab-key half of F7 only claimed
a fix. The reviewer's probes emulate G on the real `Application`; they are evidence for the
placement, not for the future code. Every change below is the reviewer's own proposed change;
nothing new was decided beyond them except T-R2h and the symmetry-state rule (from the
reviewer's "outside H2" observation) and the restore-on-raise in `apply_mesh_change` (the same
"no half change" goal as N1).

| Finding | Severity | Answer |
|---|---|---|
| N1 — `record_mesh_change` unusable without breaking H2-R4; D3 fires after the damage | SHOULD | **Fixed in the text, reviewer's main proposal.** Replaced by `apply_mesh_change(description, mutate)`: `Application` checks the owner first (D3 before any change), takes both snapshots itself (the selection format stays private), runs `mutate`, restores the mesh if `mutate` raises, records nothing if nothing changed, else pushes, mirrors, invalidates the pick cache, notifies the viewport and re-picks hover. H2-R4(a) now says where the Lab may write the mesh (inside `mutate`, through core operations). Tests T-R4c, T-R4e |
| N2 — Lab commands during the preview unspecified; D1 depends on them | SHOULD | **Fixed in the text, as proposed.** H2-R2: while the preview is open the Lab runs only M (execute); Shift+S and Shift+B are refused visibly; the preview row dominates every other row and stays until the preview ends; installing another row meanwhile asserts. The window-step pseudo-code shows the branch. Test T-R2e (Shift+S/Shift+B, gate unchanged) |
| N3 — D1 has no negative-path test | SHOULD | **Fixed.** New T-R2f: without a preview, Esc through `lab_key_press` still disarms an armed Move and ends a Knife session. The fuzz D1a is adopted as T-R2g |
| N4 — the window step's contract is not written down | NIT | **Fixed.** `lab_key_press(app, lab, input) -> bool` is pyglet-free; Esc that closes the preview returns `True`; the pyglet handler returns `EVENT_HANDLED` in every branch (§ Decision, H2-R3). The pyglet close-on-Esc behaviour stays UNVERIFIED (taken from the `src/main.py:168-170` comment) |
| N5 — test preconditions | NIT | **Fixed.** T-R2b runs with symmetry off; T-H sets Face mode before the preview; T-R4e covers a Knife session and asserts the mesh unchanged |
| N6 — T-R4b caller check | NIT | **Fixed.** Immediate caller only (`sys._getframe(1)`) |
| N7 — T-R1a / T-R5c robustness | NIT | **Fixed.** T-R1a also asserts GLOBAL and KNIFE equal `build_default_bindings()` after Lab start-up; T-R5c uses the all-constants allow-list plus the empty-allow-list negative control |
| N8 — I6 listing of D1 | NIT | **Fixed.** The start-up listing prints `Cancel (Esc): closes the Re-Symmetrize preview while it is open` (H2-R3) |
| Outside H2 — Lab state vs. `Application`'s Undo (UNVERIFIED in the review) | observation | **Answered in H2-R2**, because it decides which gate row is installed: the symmetry definition is mesh state (`mesh.export_state()` includes it, `src/core/mesh.py:623`), so Undo restores it; the Lab never caches the symmetry state and re-derives it (and the gate row) after every forwarded key event. Test T-R2h. Whether the current Lab code caches it is a Slice 1 implementation check (plan) |
| Q5 implementation notes (`set_status` as an alias, `hover_suspended` backing field) | note | **Taken over** in the Decision table |

With N1–N3 answered, the addendum is DECIDED (status above).

## Addendum (2026-10-08, AD-SYM-03 slice 3 — H2 amendment G-2: context-keyed refusal for `C`, fail-closed BLOCK row)

**Status:** **DECIDED ✓** (Manu, 2026-10-08, option A: accepted as revised). Proposed 2026-10-08 and
revised the same day after the independent review
[CLAUDE-001](../archive/symmetry_lab/reviews/AD-013_H2_AMENDMENT_REVIEW_CLAUDE_001.md) (fresh session,
`claude/funny-curie-vhvi6a` @ `42aa4ea`, archived unedited; ACCEPT WITH CHANGES, no blockers; answers in
§ Review below). The decision includes the canonicalisation rule of review S1 (§ Proposal 1) with its
MARK consequence, which was shown to Manu with the decision. No second review was asked for. Code
follows in AD-SYM-03 slice 3; until it lands, nothing in `src` or the Lab has changed.
*Update 2026-10-08:* slice 3 is cut in two. **Slice 3a landed the gate side and the Lab side of this
amendment** (§ Implementation note 2026-10-08 at the end of this addendum); the sentence "nothing in `src`
or the Lab has changed" is obsolete from that date. Slice 3b (the coordinators) follows.
**Basis:** [AD-SYM-03](AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) (DECIDED, Manu, 2026-10-08) §2.5,
§3 item 7, §5 (row "AD-013 H2"), §7 slice 3. The direction is decided there: declaration per resolved
operation (D-b), a fail-closed BLOCK row, and a context-keyed refusal for `C` with G-2 as the proposed
route. This amendment only states how H2 changes to carry that. H2-R6 requires it, because it lifts a
Limit of G.
**Read at:** `main` @ `b1cedee`; line numbers below refer to that commit.
**Engineering assumption (not confirmed by Manu):** the Lab-side change (the BLOCK row and the MARK
warning derived from the declarations) is described here and implemented in slice 3, not by this
amendment. No code changes with this text.

### Problem

G refuses by command identity only (§ Limits of G), but `C` is one command with four operations
(Split, Edge Connect, Vertex Connect, Knife; `resolve_c_context`, `contextual_c.py:18`). "Support
Connect before Knife" (AD-SYM-03) therefore needs a refusal that depends on part of the selection,
which G cannot express, so slice 3 of AD-SYM-03 is blocked on this amendment.

A second change uses G's existing mechanism and lifts no Limit, but it changes the H2 gate table: the
BLOCK row is a block-list today (`block_row`, `experiments/symmetry_lab/lab_app.py:202-207`). A mutating
command nobody adds to it runs one-sided under BLOCK (INV-8). AD-SYM-03 §2.5 turns it into an allow-list.

### Verification (code facts this amendment rests on, read at `b1cedee`)

| # | Question | Finding | Result |
|---|---|---|---|
| a | Do `_execute_click` and `key_press` consult the same gate? | `key_press` (`application.py:1145`) routes a Knife session first (`:1151-1152`), resolves GLOBAL (`:1153`), then calls `_gate_refuses(command)` (`:1154`) before every branch. `_execute_click` (`:1702`) calls `_gate_refuses(click.command)` (`:1704`) for `_SELECT_COMMANDS` (`:80-85`: `Select`, `SelectAdd`, `SelectRemove`, `SelectToggle`) before `select_at` (`:1706`). Both use the one `_gate_refuses` (`:1524-1534`), which reads the one `command_gate` (`:335`). During a Knife session a click never reaches `_execute_click` (`:1584-1589`). **Precision:** `ClearSelection` is not a click command. It is a key (Alt+A, `bindings.py:127`), gated in `key_press` (`:1154`), and `Application` has no branch for it yet, so it falls through to `return False` (`:1185`). AD-SYM-03 §2.5 groups it with the click commands; the gate path it takes is the same | **Confirmed** (same gate); grouping in AD-SYM-03 §2.5 imprecise, no consequence for G-2 |
| b | Does `_connect_command` call `resolve_c_context` exactly once? | One call (`:565`); every branch tests that one value (`:567` SPLIT, `:580` EDGE_CONNECT, `:597` VERTEX_CONNECT, `:614` KNIFE → `_knife_begin` `:615`, NONE `:617-620`). No other call in `src/` or `experiments/symmetry_lab/` (the only other occurrence is a docstring, `:1502`). `_connect_command` has one caller, `dispatch_command` (`:527-528`), and `dispatch_command(CONNECT)` has one caller, `key_press` (`:1170-1175`), reached after the gate (`:1154`) and after the armed-transform check (`:1173-1174`). No test, Lab or Playground module calls `dispatch_command` with `Connect` (grep) | **Confirmed** |
| c | Does `sync_gate` skip while a Knife session owns the keys? What does that mean for a row installed for a Knife-starting `C`? | `sync_gate` returns early while `interaction_owner is not None` (`lab_app.py:331`); `interaction_owner` is `"knife"` during a session (`application.py:1119-1120`). `lab_key_press` forwards to `Application` and only then calls `sync_gate` (`lab_app.py:507-508`). So a row installed *per key press* for a `C` that starts a Knife session (G-4) stays installed for the whole session and is re-derived only by the forwarded key that ends it (Enter/Esc, through `lab_key_press`). **Precision:** during the session that stale row changes no behaviour, because `Application` consults no gate inside a Knife session (keys `:1151-1152`, clicks `:1584-1589`). The cost is H2-R3: for the session's duration the installed gate is not the row the start-up listing names for the Lab state. Under G-2 rows change only with Lab state, so nothing is stale | **Confirmed** as AD-SYM-03 §2.5 states it, with the precision above |
| d | Which mutating commands declared in `commands.py` does `Application` not handle yet? | `SplitEdge` (`commands.py:97`), `Collapse` (`:98`), `LoopInsert` (`:101`), `LoopSlide` (`:102`), `Extrude` (`:103`), `ArticulationRestore` (`:106`). `key_press` has no branch for them (`application.py:1153-1185`), and `tool_for_command` maps only `Move`/`Rotate`/`Scale` (`routing.py:25-29`). Of these, `Collapse` (K) and `Extrude` (Alt+E) are bound only in `TOPOLOGY_CONTEXT` (`bindings.py:168,172`), which `Application` never resolves; the other four are unbound. Unhandled but **not** mutating: `EdgeLoop` (`:99`), `EdgeRing` (`:100`), `ClearSelection` (`:51`). Today a user keymap that binds one of the six in GLOBAL gets a silent `False` (`:1185`), not a mutation | **Six**, as AD-SYM-03 §1.4/§2.5 list them |

No finding contradicts AD-SYM-03 §2.5. The precision under (a) is recorded and changes nothing in the
proposal.

### Alternatives

| | Alternative | Assessment |
|---|---|---|
| G-1 | Refuse `C` (by identity) until all four contexts are supported | **Not used because** it blocks the stated intent, "support Connect before Knife" (AD-SYM-03 §2.5) |
| **G-2** | **A data-only field on `CommandGate` (`refused_contexts: Mapping[CContext, str]`), checked by `Application` in `_connect_command` right after its one `resolve_c_context`** | **Proposed** (§ Proposal) |
| G-3 | `Application` itself refuses unsupported contexts whenever a symmetry definition is set | **Not used because** it writes the Lab verdict KEEP-BLOCK into Production behaviour without a promotion (M3; AD-SYM-02 §4 note "dieses Dokument entscheidet dadurch nichts für Production") and removes the Lab's MARK comparison (AD-SYM-03 §2.5) |
| G-4 | The Lab resolves the context itself (`resolve_c_context` on `app.selection`, read-only) just before it forwards `C`, and installs the matching row | **Not used because** (AD-SYM-03 §2.5, review CLAUDE-001 of AD-SYM-03): it resolves the context twice and is correct only by event timing; it turns a gate row from a function of Lab state into one installed per key press (H2-R2/R3); and a row installed for a Knife-starting `C` stays installed for the session (verification c). **New evidence (2026-10-08):** after the A2 verdict (A, AD-SYM-03 §6), `_connect_command` canonicalises a two-sided selection to one side *before* its resolution. The Lab would have to repeat that canonicalisation to predict the context, which is app semantics in Lab code (H2-R4) and a capability fork (I1). G-4's one advantage, no `src` change, saves little, because slice 3 changes `_connect_command` anyway |
| G-5 | The Lab keeps G as it is and rewrites the identity `refused` set per key press (refuse `Connect` exactly when the next `C` would resolve to an unsupported context) | **Not used because** it is G-4 in another shape: deciding whether to refuse `Connect` needs the same prediction of the context, with the same two resolutions, timing dependence and per-press rows |
| G-6 | `Application` exposes the resolved context as a public read-only property (e.g. `c_context`), and the Lab reads it before forwarding `C` | **Not used because** it still decides before the press, from a second evaluation; it adds public surface whose only purpose is prediction; and it keeps the per-press row of G-4 |
| G-7 | A predicate or callback on the gate (`refuse_if(context) -> str \| None`) | **Not used because** H2 rejected callbacks (§ Alternatives, "F is not used because", items 1–3), and "`Application` calls no experiment code" is a constraint of this amendment |
| G-8 | Split `C` into context-specific commands (e.g. reuse `SplitEdge`) and refuse those by identity | **Not used because** it changes the Artist language (`topology.connect` is one contextual `C`, AD-017) and needs rebinding, which a Lab may not do (H2-R1: exactly three Lab entries) |
| G-9 | Generalise G-2 to `(command, context)` keys, e.g. removal command × component mode | **Not used now:** no stated need. AD-SYM-03 declares removal per command (§ Proposal, "Removal"). Naming it keeps it visible; adopting it would be its own amendment (H2-R6) |

### Proposal (G-2 and the fail-closed BLOCK row)

**1. `refused_contexts` (`src`, data only).** `CommandGate` (`application.py:248`) gets one more field,
inert by default (working name; the Python shape stays open, as in H2):

| Addition | What | Where it acts |
|---|---|---|
| `refused_contexts: Mapping[CContext, str]` (default empty) | Resolved `C` context → status text. Immutable like `refused` (`MappingProxyType`, `:262-264`), so rows compare with `==` as `sync_gate` does today (`lab_app.py:335`). `CContext` is the public enum in `mirai.topology.contextual_c`. `CContext.NONE` is not an operation and may not be listed (construction raises): `Application`'s own text `C: nothing to do here` (`:619`) stays | In `_connect_command`, **right after its one `resolve_c_context`** (`:565`) and before any branch: if `command_gate` is set and lists `ctx`, post the text through `_set_status` (`status_serial` + 1) and return `False`. No branch runs: no mesh change, no history entry, no Knife session, no selection change |

- **One resolution.** `_connect_command` keeps exactly one `resolve_c_context` (verification b). After
  slice 3 the check keys on the value the branch uses. "Right after `resolve_c_context`" means after
  that one call, not after a second, gate-only evaluation.
- **Canonicalisation (review S1; proposed in this revision, follows A2 = A as recorded).** Whenever a
  symmetry definition is set, `_connect_command` canonicalises the selection to one side (A2 = A,
  AD-SYM-03 §6) **for every context, declared or not**, and resolves that canonical selection in its one
  call. Only "canonicalise always" keeps one resolution. "Canonicalise only for declared contexts" would
  need the canonical context to know whether it is declared and then a second, literal resolution for
  the undeclared case, with the G-2 key changing meaning between the two branches. Why this is not
  G-3: the A2 verdict says what `C` *means* under symmetry ("one edge plus its mirror edge is one
  intent"). It is not a support policy, it refuses nothing, and it does not depend on the gate or the
  E5 mode. Consequence in MARK (review probe P5, `subd_cube`, X, mirror edge pair `{0, 10}`): before
  slice 4 the pair is read as one edge and runs as a one-sided Split of that edge (Split is not yet
  declared), where today it reports `Keine verbindbaren Kanten …`. Under BLOCK the same press is
  refused with the Split text. Confirmed by Manu with the decision on this amendment (2026-10-08).
- **Canonicalisation works on a value (review S4).** It builds a temporary selection (or id sets) for
  the resolver and the coordinator and never writes `app.selection` before the check. A refused `C`
  therefore leaves `selection` (mode and every id set) unchanged, the two-sided case included. Only a
  branch that runs may write the selection, as its residue (AD-017), as today.
- **Mirror pairing is still the context item (review P1).** Through canonicalisation the effective
  refusal can depend on whether two selected elements are mirror partners (P5: literal `EDGE_CONNECT`,
  canonical `SPLIT`). The key is still the context `Application` resolves, and the gate data is keyed
  on `CContext` only. This is part of the lifted "part of the selection" item, not the "mirror side"
  Limit.
- **Order with the identity gate.** The identity check in `key_press` (`:1154`) runs first. A row that
  refuses `Connect` by identity, or whose allow-list lacks it, never reaches `_connect_command`.
  `refused_contexts` therefore matters only in a row that lets `Connect` through. Then the armed-transform
  check (`:1173-1174`) applies, and only then the context check. The check cannot act inside a Knife
  session (keys never reach `_connect_command` there, `:1151-1152`) or while W/E/R is armed.
- **No callback.** `Application` reads one mapping and calls no host code. The gate table stays a
  static, printable function of Lab state (H2-R2/R3): a row lists its refused contexts the way it lists
  its refused commands.
- **A third gate site (review N1).** H2 § Decision names two gate sites (`key_press`,
  `_execute_click`) and puts none in `dispatch_command`. This amendment **adds a third site**, below
  `dispatch_command`, in `_connect_command`; the H2 call-site list is to be read with it. A direct
  `dispatch_command(CONNECT)` is therefore context-gated but not identity-gated. Today nothing calls that
  except `key_press` after the gate (verification b; the review found only private test calls of
  `_connect_command`, `tests/test_topology_transaction_seam.py`), and the Lab may not call it (H2-R4),
  so the asymmetry is theoretical.

**2. Fail-closed Lab BLOCK row (experiment code; implemented in slice 3).** While symmetry is on and
the E5 mode is BLOCK, the Lab installs one row **derived** at each derivation from the declarations, as
`block_row()` does today (`lab_app.py:202`):

```text
allowed  = NON_OPERATION
         ∪ { operation commands with a coordinator declaration (D-b) }          # e.g. Delete, Dissolve, DissolveNoCleanup
         ∪ { Connect }  if at least one C operation context is declared
         ∪ { transform commands whose Operation declares supports_symmetry }   # Move/Rotate/Scale today
refused  = { transform: block_text(label) } for each transform without supports_symmetry  # as block_row() today
         ∪ { Connect: block_text("C") }  if no C operation context is declared             # today's behaviour
refused_contexts = { ctx: block_text(display name) } for ctx in {SPLIT, EDGE_CONNECT, VERTEX_CONNECT, KNIFE}
                                                    without a declaration
not_allowed_text = a generic BLOCK text (e.g. "Symmetrie aktiv — Befehl nicht koordiniert (BLOCK: nicht gestartet)")
```

**Texts (review N4).** The generic `not_allowed_text` is the contract for every command outside
`allowed`. There is no second list of "known operation commands": named texts come only from sources
that already exist, the transform labels (`TRANSFORM_OPERATIONS`, `lab_app.py:81-85`) and `C`. The
context texts use display names (`Split`, `Edge Connect`, `Vertex Connect`, `Knife`), one small
Lab-side table keyed by `CContext`, never the enum names.

`NON_OPERATION` is one Lab-side constant, printed at start-up. It contains exactly:

| Group | Commands | Gate path |
|---|---|---|
| display | `CycleDisplayMode`, `ToggleWireframeOverlay`, `SetShaded`, `SetFlatShaded`, `SetWireframe` | `key_press` |
| selection | `Select`, `SelectAdd`, `SelectRemove`, `SelectToggle` (click commands), `ClearSelection` (key, unhandled today) | `_execute_click` `:1704` / `key_press` `:1154` |
| mode | `SetVertexMode`, `SetEdgeMode`, `SetFaceMode` | `key_press` |
| history | `Undo`, `Redo` | `key_press` |
| cancel | `Cancel` | `key_press` (H2-R2: never refused) |
| constraints | `ConstrainAxisX`, `ConstrainAxisY`, `ConstrainAxisZ`, `ConstrainPlaneXY`, `ConstrainPlaneXZ`, `ConstrainPlaneYZ` | `key_press` |
| navigation, Knife session (review N2) | `Orbit`, `Pan`, `Zoom`, `KnifeCommit`, `KnifeLift` | `key_press`, only through a user GLOBAL key binding |

With the default keymap the last group never reaches the gate: drags and the wheel are never gated
(§ Decision above), and `KnifeCommit`/`KnifeLift` are bound only in the KNIFE context, where no gate
applies. A user GLOBAL key binding can still route them through `key_press` (`command_for` accepts it),
where `Application` returns `False` for them anyway. Listing them keeps such a key silent instead of
reporting "not coordinated" (review probe P4); it cannot start anything. The three Lab commands need no
entry (handled before `Application`, `lab_app.py:503-504`). **Deliberately not listed:**
`EdgeLoop`, `EdgeRing`. They are unhandled Topology-Lab selection commands, and whether a loop
selection should mirror under symmetry is itself a symmetry question. If they are wired, BLOCK refuses
them visibly until someone decides.

An omission from `NON_OPERATION` or from the declarations is **refused visibly**
(`not_allowed_text`, `status_serial` + 1). It never runs silently one-sided (INV-8). The six unwired
mutating commands (verification d) are refused under BLOCK from the day they are wired until a
coordinator declares them. Named refusal texts stay where the operation is known (`refused` is checked
before `allowed`, `CommandGate.refusal`, `:267-273`). The other rows are unchanged: symmetry off → `None`;
MARK → `None`; preview → the display-only allow-list, which still dominates (H2-R2, N2).

*Illustration, not a plan:* if slice 3 declares Edge Connect, Vertex Connect and the three removal
commands, then under BLOCK `C` with two edges runs coordinated. `C` with one edge is refused with the
Split text until slice 4, and `C` with an empty selection is refused with the Knife text until slice 6.
No Knife session starts, and the row does not change across the press.

**Removal.** D-b keys removal "by removal mode" (AD-SYM-03 §2.5). This amendment carries removal
declarations **per command** (`Delete`, `Dissolve`, `DissolveNoCleanup`), which G already expresses.
Assumption: slice 3 coordinates each declared removal command in every component mode. If a removal
command can be coordinated in only some component modes, that is a mode-keyed refusal. This amendment
does not lift it (G-9). Either that command stays undeclared, and so is refused in every mode under
BLOCK, or H2 is reopened.

**3. Runtime refusals are not G-3** (AD-SYM-03 §2.5, taken over). A coordinator that refuses a seam case,
the both-sides face case (AD-SYM-03 §3 item 9), a non-exact plane or a D-strict delta acts in
`Application` whenever a symmetry definition is set, in MARK as in BLOCK. That is not G-3. Such a refusal
is part of the contract of a **supported** operation ("mirrors correctly or recognisably not at all",
INV-5). G-3 would apply KEEP-BLOCK, the policy for **unsupported** operations, in Production. The gate
(G and G-2) remains the only place that policy acts, and only the Lab writes it. Consequence after slice
3: MARK runs declared operations coordinated, including their runtime refusals, and only undeclared ones
one-sided. That is the same as transforms today, which mirror whenever a definition is set.

*Operational criterion (review N6):* a runtime refusal is decided by the coordinator of a **declared**
operation, from that operation's input (selection, seam, delta). It never reads the gate or the E5
mode, and an undeclared operation never reaches a coordinator. **One accepted exception:** the
non-exact-plane refusal (AD-SYM-03 §3 item 6) depends on the definition, not on the input, so for such
a definition it refuses every declared topology operation, in MARK too. It is unreachable today (Lab
planes are axis planes through the origin; no host produces another plane) and recorded as an
asymmetry in AD-SYM-03 §4. Canonicalisation (§ Proposal 1) is no refusal and follows the A2 verdict,
not a support policy.

**4. The MARK warning comes from the same declarations.** `e5_warning_text`
(`lab_app.py:582-603`; today a running Knife session and undeclared transforms) is derived from the
same declaration mapping as the BLOCK row. Example: the Knife line appears only while `KNIFE` has no
declaration. There is no second list. An immediate undeclared operation (e.g. Split before slice 4) is
no running interaction and keeps having no warning line; its degradation shows in the state markers,
as the docstring of `e5_warning_text` says today.

### Consequences for H2-R1 … H2-R6

- **H2-R1 — unchanged.** No new Lab binding, no new context, no rebinding of `C`.
- **H2-R2 — one bullet replaced (review S2), the rest holds.** The context check can only stop `C`
  from *starting* an operation. It runs before any branch and never inside an `Application`
  interaction (verification b, c). The gate stays constant while `interaction_owner` is set: rows still
  change only on Lab state changes, never per key press. **Replaced bullet.** H2-R2's "Outside the
  preview the gate refuses only commands that start an interaction or change the mesh (Connect;
  transform commands in BLOCK). It never refuses `Cancel`." now reads: "Outside the preview the gate
  refuses commands that start an interaction or change the mesh; under BLOCK it additionally refuses
  every command outside `NON_OPERATION` and the declarations (fail-closed), mutating or not, and `C` by
  its resolved context. It never refuses `Cancel`." `Cancel` stays allowed (it is in `NON_OPERATION`;
  `refused_contexts` cannot name a command).
- **H2-R3 — extended.** A context refusal is visible like any refusal: status text, `status_serial` + 1
  (also for a repeated identical text), return `False`. The start-up listing prints each row's
  `refused_contexts` next to its `refused` and `allowed` sets, and prints the `NON_OPERATION` constant.
- **H2-R4 — extended by two read-only items, and one prohibition.** The Lab may (g) import the
  `CContext` enum as a key and (h) read the D-b declaration mapping (a static `src/mirai` table, not an
  `Application` member). The Lab may **not** call `resolve_c_context` or the canonicalisation functions
  of `mirai.symmetry_coordination` (`canonical_vertices`, `canonical_edges`, `canonical_faces`,
  `symmetry_coordination.py:108-118`; review N3). Either would be G-4 under another name. T-R4a's
  static scan covers both.
- **H2-R5 — Production unchanged.** With the defaults (`command_gate is None`, or a gate with empty
  `refused_contexts`) `_connect_command` behaves identically: the check is one `None` test, or one empty
  lookup. `src/main.py` writes no gate data (T-R5b, unchanged). Needed guard tests: T-R5a and T-R5c
  extended (below). **The other half (review S3):** after slice 3, `_connect_command` also changes when
  a symmetry definition is set (canonicalisation, coordinators, runtime refusals). That is Production
  code, but no Production host sets a definition today: `src/main.py` contains no symmetry code. A guard
  test keeps it so (T-G3b), and T-G3a pins the G-3 boundary from the Production side.
- **H2-R6 — still one writer.** `refused_contexts` is a field of the one `command_gate` value. The
  Symmetry Lab's window wiring stays its only writer (`SymmetryAppLab._install_row`,
  `lab_app.py:340`). The amendment adds **no second writer and no registry**: the D-b declaration
  mapping is a static Production table of coordinators, read by the one writer to derive its row and by
  `Application` to dispatch coordinated operations. It holds no gate data and nobody installs anything
  into it at runtime. A second gate user still needs its own review.

### Required tests (named, not written)

Headless, through `Application`'s public entry points, fixture as in
`tests/test_application_pointer.py:34-40`. `src` tests go to `tests/` (not named `test_application_*`,
because T-R5c re-runs that set); Lab tests go to `experiments/symmetry_lab/tests/` and drive
`lab_key_press`.

| ID | Rule | Test |
|---|---|---|
| T-G2a | G-2, R3, S4 | Parametrised over the four operation contexts × (listed / not listed): `C` via `key_press` with a selection that resolves to the context. Listed → returns `False`, `status_serial` + 1, `status_message` = the row text, `mesh.export_state()` and history unchanged, `selection` mode and every id set unchanged, `knife_active is False` for KNIFE. Not listed → identical to a run without a gate. Twice the same refusal → two increments. After slice 3 also with a definition set and a two-sided selection (mirror pair): refused → `selection` still holds both sides |
| T-G2b | G-2, S1 | `resolve_c_context` patched with a counter: exactly one call per `C` press, whether listed, unlisted or refused, and (after slice 3) with a definition set for declared and undeclared contexts alike, i.e. on the canonicalisation path |
| T-G2c | order | `Connect` in `refused` and its context listed → the identity text wins, counter 0; `Connect` outside `allowed` → `not_allowed_text`, counter 0; W armed + `C` → `False` from the armed check, no context status |
| T-G2d | NONE | Constructing a gate that lists `CContext.NONE` raises. One vertex selected, every operation context listed → `C: nothing to do here` |
| T-G2e | R2 | During a Knife session (started without a gate), a gate that lists every context changes nothing: Enter, Esc, E, Ctrl+Z and clicks behave as without it |
| T-G2f | R5 | `CommandGate()` has empty `refused_contexts`; two gates from equal data are `==`; the mapping is read-only |
| T-R5a+ | R5 | As T-R5a (`Application()` has `command_gate is None`), plus: with a default `CommandGate()` installed, `C` on each of the five contexts gives the same return value, status, mesh and history as with no gate |
| T-R5c+ | R5, N5 | The inert-but-active gate of `tests/_inert_gate_plugin.py` also gets `refused_contexts = {}` → identical results, and the plugin counts context-check consultations as it counts `_gate_refuses` today, so the run proves the context path executed. New negative control: every operation context listed → the contextual-`C` and Knife tests fail |
| T-G3a | G-3 boundary, S3 | `command_gate is None`, a definition set (exact X plane): `C` on each **undeclared** context (after slice 3: Split, Knife) with a one-sided selection behaves as with no definition (same return value, same one-sided mesh result, no refusal status). A two-sided mirror-pair selection follows the canonicalisation rule (§ Proposal 1, probe P5) |
| T-G3b | R5, S3 | AST guard like T-R5b: `src/main.py` never assigns `symmetry_definition` and calls no `mirai.symmetry` / `mirai.symmetry_coordination` function |
| T-FC1 | fail-closed | Lab, symmetry on, BLOCK: for every command constant in `mirai.interaction.commands` that is in neither `NON_OPERATION` nor the declarations nor the Lab commands, bound by a test user binding in GLOBAL → `lab_key_press` returns `False`, status posted, mesh and history unchanged (covers the six commands of verification d) |
| T-FC2 | fail-closed | Lab, symmetry on, BLOCK: each `NON_OPERATION` command (four click commands, Alt+A, 1/2/3, Ctrl+Z/Y, Esc disarming W, X/Y/Z and Shift+X/Y/Z, D/Shift+D) behaves as with symmetry off |
| T-FC3 | D-b | Declarations patched (add or remove a context or removal command) → `block_row()` changes accordingly and compares with `==`; the row is a function of the declarations and the transform `supports_symmetry` flags only |
| T-FC4 | G-2 via Lab | Symmetry on, BLOCK: `C` on a declared context runs; on an undeclared one it is refused with its named text; empty selection → refused, `knife_active is False`. `app.command_gate` is the same object before and after each press (no per-press row) |
| T-FC5 | MARK | Declarations patched: the Knife warning line appears iff KNIFE is undeclared; MARK row stays `None` |
| T-R1d+ | R3 | The start-up listing contains every row's `refused_contexts` and the `NON_OPERATION` constant |
| T-R2h+ | R2 | As T-R2h; after each Undo/Redo the installed row, including `refused_contexts`, equals the row derived for the restored definition |
| T-R4a+ | R4, N3 | The AST scan also fails on any call of `resolve_c_context` or `canonical_vertices`/`canonical_edges`/`canonical_faces` in Lab modules; importing `CContext` is allowed |

### Consequences

- **Positive:** `C` can be supported context by context, starting with Connect, with no callback and no
  second resolution. Under BLOCK an operation without a coordinator is refused visibly; it can no
  longer run silently one-sided. BLOCK row, MARK warning and coordinators share one source (the
  declarations).
- **Costs:** one field and one lookup in `src` (`CommandGate`, `_connect_command`); a `NON_OPERATION`
  hand list in the Lab (its omissions fail visibly, which is the property that matters, AD-SYM-03
  §2.5); the generic BLOCK text for commands that are neither listed nor named.
- **Behaviour change in the Lab (slice 3, BLOCK only):** a GLOBAL user binding on one of the six unwired
  mutating commands, or on `EdgeLoop`/`EdgeRing`, now posts a refusal instead of returning a silent
  `False` (navigation and Knife-session commands bound that way stay silent, review N2). The end of the
  accepted interim (Delete/Dissolve one-sided under BLOCK) is owner check O1 in AD-SYM-03 §4, not decided
  here.
- **Behaviour change in MARK (slice 3, canonicalisation, review S1):** a two-sided mirror-pair selection
  is one intent for `C` whenever a definition is set, also for a context without a coordinator; before
  slice 4 a mirror edge pair runs as a one-sided Split of one edge (§ Proposal 1).

### Not decided here

The Python shape and the final names (`refused_contexts`, `NON_OPERATION`, texts). Whether
`EdgeLoop`/`EdgeRing` count as non-operations (they fail closed until decided). Mode-keyed removal refusals (G-9). Everything else in
§ Limits of G (click position, mirror side for other commands, refusals inside a Knife session,
"instead of" reactions) stays a Limit. Nothing here promotes symmetry or KEEP-BLOCK to Production (M3).

### Review

**Independent review:**
[AD-013_H2_AMENDMENT_REVIEW_CLAUDE_001.md](../archive/symmetry_lab/reviews/AD-013_H2_AMENDMENT_REVIEW_CLAUDE_001.md)
(fresh session, `claude/funny-curie-vhvi6a` @ `42aa4ea`, archived unedited). Verdict: **ACCEPT WITH
CHANGES, no blockers.** Every file:line claim of § Verification re-checked and correct. G-2 and the
fail-closed row were emulated on the real `Application` and Lab (probes P1–P5); the probes are evidence
for placement and wiring, not for the future code. G-2 lifts exactly the context item; `NON_OPERATION`
covers every command `Application` handles today, and nothing listed is wrong. The reviewer named S1,
S2 and the S3/S4 tests as the changes before DECIDED; all are taken over below. Nothing beyond the
reviewer's own proposals was decided, except where the table says so. The archived H2 reviews
CLAUDE-001/002 are not touched.

| Finding | Severity | Answer |
|---|---|---|
| S1 — the A2/MARK canonicalisation question decides whether "one resolution" (T-G2b) holds and touches the G-3 boundary | SHOULD | **Decided in the text, reviewer's recommendation.** Canonicalise always when a definition is set, for declared and undeclared contexts (§ Proposal 1); one resolution holds; why it is not G-3 is stated in § Proposal 1 and item 3; the MARK consequence is listed under § Consequences. Removed from § Not decided here. **Confirmed by Manu with the decision (2026-10-08, option A)**; the MARK consequence was shown to him with it |
| S2 — the H2-R2 bullet "refuses only commands that start an interaction or change the mesh" contradicts the fail-closed row | SHOULD | **Fixed, reviewer's wording.** § Consequences for H2-R1 … H2-R6 now replaces that bullet instead of saying "holds" |
| S3 — no test for the G-3 boundary from the Production side | SHOULD | **Fixed.** New T-G3a (no gate + definition: undeclared contexts unchanged) and T-G3b (AST guard: `src/main.py` sets no definition and calls no symmetry code); H2-R5 consequence extended |
| S4 — "no selection change" on refusal claimed, not tested | SHOULD | **Fixed.** § Proposal 1: canonicalisation works on a value, never on `app.selection` before the check; T-G2a asserts mode and id sets unchanged, including the two-sided case |
| N1 — a third gate site | NIT | **Fixed.** § Proposal 1 names it as an addition to H2's call-site list |
| N2 — "never reach the gate" holds only for the default keymap | NIT | **Fixed, as proposed.** `Orbit`/`Pan`/`Zoom`/`KnifeCommit`/`KnifeLift` are in `NON_OPERATION`; only `EdgeLoop`/`EdgeRing` stay deliberately unlisted |
| N3 — `canonical_*` would reopen G-4 under another name | NIT | **Fixed.** H2-R4 prohibition and T-R4a+ cover `canonical_vertices`/`canonical_edges`/`canonical_faces` |
| N4 — "known operation commands" is an undefined second list; context texts need display names | NIT | **Fixed.** The generic text is the contract; named texts only from existing sources (transform labels, `C`); a display-name table for the four contexts (§ Proposal 2, "Texts") |
| N5 — T-R5c+ should count context-check consultations | NIT | **Fixed** in T-R5c+ |
| N6 — operational form of "runtime refusals are not G-3"; the non-exact plane | NIT | **Fixed.** Item 3 has the operational criterion and names the non-exact plane as the one accepted definition-wide refusal, with the AD-SYM-03 §4 pointer |
| P1 — mirror pairing via canonicalisation is part of the context item | NIT | **Fixed.** One bullet in § Proposal 1 |

A second review is not required by the findings (no blocker, and every change is the reviewer's own
proposal); Manu did not ask for one.

**Decision note (2026-10-08).** Manu decided option A: the amendment as revised above, including the
canonicalisation rule (S1) and its MARK consequence. Alternatives offered and not chosen: B (canonicalise
under MARK only for declared contexts; needs two resolutions, a revision and a second review), C (a
second review first), UNKNOWN.

### Implementation note (2026-10-08, AD-SYM-03 slice 3a)

Slice 3a implemented § Proposal 1 and 2 and the listed tests; no coordinator exists yet. Nothing here
changes the decision; what the code made concrete or had to add is listed so the text and the code agree.

- **Landed (`src`).** `CommandGate.refused_contexts` (`MappingProxyType`, `==`-comparable, construction
  raises for `CContext.NONE`) and `CommandGate.context_refusal`; `Application._connect_command` with exactly
  one `resolve_c_context`, canonicalisation on a temporary value whenever a definition is set
  (`_canonical_c_selection`, never written to `app.selection`), and the check right after the call
  (`_context_refuses`: post the text through `_set_status`, return `False`, no branch runs). The static
  declaration tables are `src/mirai/symmetry_declarations.py` (`C_CONTEXT_COORDINATORS`,
  `REMOVAL_COORDINATORS`, read through `declared_c_contexts()` and `declared_removal_commands()`); both are
  empty in 3a. The module imports only the `CContext` enum, so `symmetry_coordination` keeps depending on
  `core` and `mirai.symmetry` only. `src/main.py` and `src/core` are untouched (T-G3b guards the former).
- **H2 call-site list, read with the third site.** The gate is consulted in `key_press`, in
  `_execute_click` and in `_connect_command` (§ Proposal 1, "A third gate site"). A direct
  `dispatch_command(CONNECT)` is context-gated but not identity-gated; nothing outside `key_press` calls it.
- **Landed (Lab).** `NON_OPERATION` exactly as in the table above (`EdgeLoop`/`EdgeRing` deliberately not
  listed), `CONTEXT_NAMES` (display names), `BLOCK_NOT_ALLOWED_TEXT`, `block_row()` derived from the
  declarations as in § Proposal 2, `e5_warning_text` reading the same declarations (Knife line only while
  `KNIFE` is undeclared), and a start-up listing that prints each row's `refused`, `allowed` and
  `refused_contexts` (one rule per line), `NON_OPERATION`, `INTERIM_ONE_SIDED` and the current
  declarations. `sync_gate` and the single-writer rule are unchanged; no per-press row. With no
  declaration, `Connect` is refused by identity with `block_text("C")` as before; the four
  `refused_contexts` are part of the row regardless, so the row is the same function of the declarations
  before and after slice 3b.
- **Deviation from the allow-list formula of § Proposal 2 (engineering, set in the slice 3a handoff, not an
  Artist decision; assumption: acceptable because it keeps today's behaviour).** With zero declarations a
  pure fail-closed allow-list would refuse `Delete`, `Dissolve` and `DissolveNoCleanup` under BLOCK and so
  end the accepted interim (Manu, 2026-10-06) silently. `allowed` therefore also contains the named
  constant `INTERIM_ONE_SIDED = {Delete, Dissolve, DissolveNoCleanup}` (printed at start-up, "accepted
  interim, Manu 2026-10-06; removed in slice 3b"). It is neither a declaration nor an omission. **Slice 3b
  deletes it**, together with the interim.
- **Test IDs.** `tests/test_command_gate_contexts.py`: T-G2a, T-G2b, T-G2c, T-G2d, T-G2e, T-G2f, T-R5a+,
  T-G3a, T-G3b. `tests/test_command_gate.py` and `tests/_inert_gate_plugin.py`: T-R5c+ (the inert gate
  carries `refused_contexts = {}` and the plugin counts `_context_refuses` consultations; negative control
  mode `contexts` lists every operation context and makes the contextual-`C` and Knife tests fail).
  `experiments/symmetry_lab/tests/test_app_lab_fail_closed.py`: T-FC1 to T-FC5, T-R1d+, T-R2h+, and a
  test for the interim; `test_app_lab_boundary.py`: T-R4a+. Declarations are patched where a declared
  context is needed, because the real mapping is empty. T-FC1 covers the six unwired commands of
  verification (d), `EdgeLoop`/`EdgeRing` and `Connect`.
- **Observed, not decided.** Canonicalisation applies to vertex pairs too (A2: "1 vertex pair → no C
  meaning"): a vertex and its mirror vertex, in Vertex mode with a definition set, now give
  `C: nothing to do here` in MARK, where `C` used to resolve to Vertex Connect between the two (on
  the head: nothing connectable, A2 observation 2). The
  amendment's MARK consequence names the edge pair (probe P5); the vertex pair follows from the same rule
  and from A2 as recorded.

