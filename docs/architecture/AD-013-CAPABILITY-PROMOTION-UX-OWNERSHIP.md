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
