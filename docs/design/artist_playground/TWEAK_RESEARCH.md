# Tweak — UX Research / Idea Space

**Status:** Open research — no implementation decision
**Area:** Artist Playground
**Date:** 2026-09-12

---

## Purpose

This document is the open idea and research space for **Tweak** as an artist interaction concept.

It is deliberately **not** a production specification and not yet an implementation plan. The goal is to capture ideas, variants, observations and questions before deciding what Tweak should actually become.

The Artist Playground is the place to build and play with these variants. Findings may later become a validated UX decision, but nothing here automatically becomes Production architecture.

---

## Core Idea

Tweak is a **direct manipulation workflow**:

> Hover the component I want to affect, then manipulate it directly — without first making it the global selection.

The cursor identifies the target. The current global Selection is not required as the transform source.

Example:

```text
Selection = A

Cursor → B
Tweak B

→ B changes
→ Selection remains {A}
```

This separation is important. Tweak should not silently replace, add, remove or toggle the global selection merely because a component was manipulated.

---

## Initial Interaction Ideas

### Keyboard-driven Tweak

Hover/highlight a component, then use a transform key while dragging:

```text
Hover → T + Drag  → Move
Hover → R + Drag  → Rotate
Hover → S + Drag  → Scale
```

The exact meaning of `T` is still open. It may represent Tweak/Move, or Move may eventually use another established convention. The experiment should test the interaction before fixing terminology.

### Mouse-driven Tweak

A more direct mouse-first variant:

```text
Hover → LMB + Drag → Move
```

This is intentionally interesting because it competes with the existing meanings of LMB drag. The conflict is part of the UX question, not something to hide prematurely.

Possible future variants could test contextual activation, a dedicated modifier, or another mouse button — but these should remain ideas until the basic interaction has been experienced.

---

## What Tweak Is Not

Tweak should not initially be treated as a replacement for the normal Transform workflow.

The existing workflow remains a baseline:

```text
Select → Move / Rotate / Scale
```

Tweak is an alternative direct-manipulation path:

```text
Hover → Manipulate
```

The two workflows may coexist and may eventually serve different purposes.

---

## Selection Relationship

A central research invariant:

> **Tweak target ≠ necessarily current Selection.**

Example:

```text
A selected
B hovered

T + Drag on B

Expected:
    B moves
    A stays selected
    Selection state is unchanged
```

Multiple selection remains a separate global Selection workflow. Existing Shift-based selection experiments are therefore not part of Tweak itself.

Questions to investigate:

- Should Tweak ever operate on the whole current Selection?
- Should a modifier allow "tweak selected" instead of "tweak under cursor"?
- What should happen when the cursor is over a selected component?
- Should Tweak temporarily expose the target without changing Selection?
- Is a separate visual state needed for **Hovered**, **Selected**, and **Tweak Target**?

---

## Hover / Highlight

Tweak strongly suggests that the component under the cursor should be visually identifiable before the drag begins.

Potential states:

```text
normal
   ↓
hover/highlight
   ↓
active tweak target
   ↓
commit
```

Questions:

- Is hover highlighting necessary for reliable direct manipulation?
- Should the highlight appear only while a Tweak-capable modifier is held?
- Should it exist continuously in the viewport?
- How different should Hover and Selected look?
- Does hover feedback become distracting on dense meshes?
- Does component mode change what can be hovered?

---

## Component Scope

The first useful test can start with vertices, but the concept may generalize:

```text
Vertex  → direct vertex tweak
Edge    → direct edge manipulation?
Face    → direct face manipulation?
```

The existing component picking infrastructure already provides a useful basis for experimentation.

Do not assume that identical behavior is appropriate for all component types.

---

## Transform Semantics

Tweak may reuse existing transform mathematics and Production transform operations internally, while still being a distinct interaction concept.

Important distinction:

```text
Implementation reuse
        ≠
UX / tool identity
```

A Playground prototype may therefore use the existing Move/Rotate/Scale tools as adapters. If Tweak proves valuable, Production can later decide whether it deserves a distinct interaction mode/tool abstraction.

---

## Input Questions

### Keyboard vs Mouse

The first useful comparison is:

| Variant | Interaction |
|---|---|
| Keyboard Tweak | Hover + `T/R/S` + Drag |
| Mouse Tweak | Hover + LMB + Drag |

Research question:

> Which interaction produces the more natural, controllable and low-friction direct manipulation workflow?

### LMB Conflict

Current LMB interactions include selection-related behavior and may also participate in navigation depending on modifiers/state.

A Mouse Tweak using plain LMB therefore raises a fundamental question:

> Can LMB mean both "manipulate the thing under the cursor" and "selection/navigation" without becoming ambiguous?

Possible future answers — **ideas only, not decisions**:

- context-sensitive LMB
- dedicated Tweak modifier
- temporary Tweak mode
- different mouse button
- press/drag timing distinction
- hover state changes the meaning of drag
- explicit tool activation

Do not solve this architecturally before the interaction has been tested.

---

## Possible Extensions / Ideas

These are deliberately uncommitted ideas for later experiments.

### 1. Tweak on different components

- vertex
- edge
- face
- perhaps object/element level later

### 2. Axis constraints

Potential variants:

```text
T + X + Drag
T + Y + Drag
T + Z + Drag
```

or another constraint vocabulary.

### 3. Camera-space vs world-space manipulation

Investigate whether direct Tweak should feel like:

- screen/camera-plane dragging
- world-axis movement
- inferred surface direction
- normal-based movement
- context-dependent behavior

### 4. Depth / distance behavior

For vertex Tweak especially:

- screen-plane movement
- depth locked
- depth inferred from original hit
- depth controlled by a modifier
- distance from camera preserved

### 5. Soft / proportional influence

A future Tweak experiment could ask whether nearby components should follow:

```text
single vertex
      ↓
soft influence
      ↓
local deformation
```

This should remain separate from the basic direct-manipulation question.

### 6. Surface-aware Tweak

Possible future direction:

> Drag a component along the visible surface rather than through a camera plane.

Potentially useful for organic modelling, but requires a separate UX investigation.

### 7. Temporary selection / target display

The hovered Tweak target could receive a transient visual indicator without entering global Selection.

This may provide the visual clarity of selection without the state change.

### 8. Sticky / continuous Tweak

Potential future question:

> After committing one tweak, can the artist immediately move to another component without leaving the mode?

This would shift Tweak from a single gesture toward a continuous modelling mode.

### 9. Modifier changes during drag

Potential future test:

```text
Drag
  ↓
hold modifier
  ↓
change transform constraint/mode
```

Useful only after the basic gesture is proven.

### 10. Tweak as a modelling "brush"

Longer-term idea:

Tweak could evolve from a single-component gesture into a family of direct manipulation behaviors, potentially approaching a lightweight modelling brush without becoming a sculpting system.

This is deliberately speculative.

---

## UX Questions Worth Testing

- Does direct manipulation feel faster than Select → Transform?
- Is hover targeting reliable enough without a click?
- Is the target obvious before movement starts?
- Does T/R/S feel natural for direct manipulation?
- Does LMB-only Tweak feel wonderfully immediate or dangerously ambiguous?
- Is accidental manipulation a problem?
- How often does the artist want to manipulate something without selecting it?
- Does keeping Selection unchanged make workflows clearer?
- Does Tweak reduce repetitive selection operations on dense meshes?
- Does it become annoying when the intended target is difficult to pick?
- How does it behave on the Head Basemesh compared with the Cube?
- Does it remain usable while orbiting/panning/zooming frequently?
- Does muscle memory from other DCCs help or hurt?

---

## Known UX Influences

Tweak is related conceptually to direct-manipulation workflows found in modelling/sculpting applications, especially the idea of manipulating geometry under the cursor without requiring a conventional selection step first.

Specific application behavior should be treated as inspiration to investigate, not as a specification to copy.

---

## Experiment Discipline

For each Tweak experiment:

1. Capture the interaction idea.
2. Build the smallest possible Playground variant.
3. Play with it on Cube and Head.
4. Compare it against the existing Select → Transform workflow.
5. Record what feels good/bad.
6. Decide: **KEEP / ITERATE / REJECT / UNKNOWN**.
7. Only promote a validated finding toward Production later.

Do not turn every successful prototype detail into architecture.

---

## Current Non-Decisions

Nothing below is currently fixed:

- Tweak's final name
- whether T means Move/Tweak
- whether Tweak is a tool, mode, interaction layer, or some combination
- whether Mouse Tweak uses plain LMB
- whether Keyboard and Mouse Tweak should coexist
- whether Tweak affects only one component or can affect a selection
- exact hover appearance
- exact drag/depth semantics
- axis constraint behavior
- soft influence behavior
- Production architecture

---

## Current Working Hypothesis

For Playground research, the most useful first comparison is deliberately small:

```text
A — Keyboard
Hover → T/R/S + Drag

B — Mouse
Hover → LMB + Drag

Both:
    • no prior selection required
    • target comes from the cursor
    • global Selection remains unchanged
    • existing Move/Rotate/Scale machinery may be reused internally
```

This is a **research hypothesis, not a final design**.

---

## Related Documents

- `docs/design/artist_playground/AP-03_PLAN.md` — Selection Lab plan
- `docs/design/artist_playground/ARCHITECTURE_MAP.md` — Playground architecture boundaries
- `docs/design/artist_playground/ROADMAP.md` — broader Playground roadmap
- `AGENTS.md` — repository-wide agent/documentation rules
