# Viewport V1 — Selection Modes Experiment

## Purpose

This document is the **current selection experiment reference** for `experiments/mirai_bastel_viewport_V1/`.

The goal is to test the interaction model of a traditional polygon modeler without changing the production Core architecture or moving the experiment into `src/`.

The experiment is deliberately small. It is intended to answer interaction and workflow questions through a working viewport before a production selection system is designed.

## Current status

Viewport V1 currently provides three explicit Sub-Object modes:

1. **Vertex Mode** — only vertices can be selected.
2. **Edge Mode** — only edges can be selected.
3. **Face Mode** — only faces can be selected.

Mode switching is available with `V` / `1`, `E` / `2`, and `F` / `3`. Changing mode clears the current selection and hover state.

The experiment also has a simple **toggle multi-selection** and Sub-Object Move. These are deliberately experimental workflow choices, not frozen production contracts.

## Selection behavior under test

The current interaction is intentionally simple and Wings-like:

```text
click A        → [A]
click B        → [A, B]
click A        → [B]
click empty    → []
```

Rules:

- clicking an unselected element adds it to the current selection;
- clicking an already selected element removes it;
- clicking another element keeps the existing selection;
- clicking empty space clears the complete selection;
- no modifier key is required.

This behavior applies experimentally to Vertex, Edge and Face modes.

**This is not yet the final Mirai-Bastel selection specification.** The purpose is to test whether the workflow feels right in practice.

## Hover preview

Hover is separate from selection.

When the pointer moves over a selectable component, that component receives a temporary visual highlight indicating what would be selected by a click.

```text
pointer movement
      ↓
   hit test
      ↓
selectable element found?
      ↓
 hover highlight
      ↓
      click
      ↓
 selection changes
```

Hover must not modify persistent selection state.

The current implementation uses mode-specific picking:

- Vertex Mode → nearest projected vertex within a small pixel tolerance.
- Edge Mode → nearest projected edge segment within a small pixel tolerance.
- Face Mode → nearest positive ray/triangle intersection; the closest hit wins.

The picking tolerances and algorithms remain experimental V1 choices.

## Mode-specific behavior

### Vertex Mode

Only vertices can be selected.

The existing V1 Move interaction remains available for selected vertices.

### Edge Mode

Only edges can be selected.

Selected edges can be passed to the Sub-Object Move experiment, which resolves their endpoint vertices.

### Face Mode

Only faces can be selected.

Face selection uses the filled-face representation and ray-based picking so that overlapping projected faces resolve to the visible/front-most face.

## Sub-Object Move

The experiment uses the existing Core `MoveOperation` and resolves the selected Sub-Objects into affected vertices:

```text
Vertex → selected vertices
Edge   → both endpoint vertices
Face   → all boundary vertices
```

For multiple Edges/Faces the affected vertex set is the union, so shared vertices are moved only once.

This is an important architectural observation:

```text
Selection / Interaction
          ↓
    affected elements
          ↓
     Core Operation
```

The Core operation does not need to know how the user arrived at the selection.

## Workflow questions exposed by the experiment

Topology operations can change the selected element type. For example:

```text
Vertex Mode
  ↓
Connect Vertices
  ↓
new Edge exists
```

or:

```text
Edge Mode
  ↓
Collapse Edge
  ↓
Vertex exists / is selected
```

Other operations may behave differently, for example:

```text
Edge Mode
  ↓
Split Edge
  ↓
new Vertex + Edges
```

The useful question is therefore not merely **what does the operation create?**, but:

> **What should remain selected and which interaction mode should remain active after an operation?**

Both behaviors can be useful depending on the next action:

- keeping the newly created element selected makes immediate follow-up operations convenient;
- returning to the originating mode makes repeated operations on the same component type efficient.

This is a workflow/design question, not something that should be hard-coded as a universal rule before practical testing.

The detailed long-term selection/workflow discussion belongs in [`docs/future_ideas/SELECTION.md`](../../docs/future_ideas/SELECTION.md) and the general interaction principles in [`docs/design/WORKFLOW.md`](../../docs/design/WORKFLOW.md). This experiment records only observations and tests specific to the viewport.

## Deliberately postponed / open

- Object Mode
- Visible Only vs. Through/X-Ray
- Box/Lasso/Brush selection
- Loop/Ring selection
- Grow/Shrink and other selection expansion/reduction
- Universal / All-in-One selection mode
- final modifier behavior
- final selection visualization/colors
- Soft Selection / Influence
- advanced picking behavior
- final post-operation selection/mode policy

## Experiment philosophy

This work remains inside `experiments/mirai_bastel_viewport_V1/`.

The purpose is to learn from actual interaction before defining production architecture. Results should inform later architectural and design decisions, but the experiment itself is not considered production code.

## Current verification

The basic Vertex / Edge / Face path has been practically verified:

```text
Hover → Hit-Test → Highlight
Pick  → Selection → Selection-Highlight
```

Toggle multi-selection has been tested in all three Sub-Object modes.

Sub-Object Move has been implemented using the existing Core `MoveOperation` and the topology query API.

Further selection behavior remains an active experiment, especially loop/ring selection, visibility rules and post-operation workflow.
