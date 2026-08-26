# Viewport V1 — Selection Modes Experiment

## Purpose

This document defines the isolated selection experiment for `experiments/mirai_bastel_viewport_V1/`.

The goal is to test the basic interaction model of a traditional polygon modeler without changing the production Core architecture or moving the experiment into `src/`.

The experiment is deliberately small. It is intended to answer interaction and architectural questions through a working viewport before any production selection system is designed.

## Current baseline

Viewport V1 provides a minimal real-time OpenGL viewport connected to the Core V1 path. The existing experiment validates the basic Scene → Mesh → Selection → Move → Commit → History → Undo/Redo path together with camera interaction.

The viewport now also has a minimal solid/filled representation of polygon faces. Wireframe edges and vertices remain visible on top for the selection experiments.

## Selection modes in this experiment

The current scope is deliberately limited to the three **Sub-Object modes**:

1. **Vertex Mode** — only vertices can be selected.
2. **Edge Mode** — only edges can be selected.
3. **Face Mode** — only faces can be selected.

**Object Mode is intentionally postponed** and will be tested separately after the Sub-Object modes.

Mode switching is available with `V` / `1`, `E` / `2`, and `F` / `3`. Changing mode clears the current selection and hover state.

## Initial selection rule

The first experiment intentionally supports **single selection only**.

A new selection replaces the previous selection:

```text
nothing selected
    ↓
click A
    ↓
A selected
    ↓
click B
    ↓
A deselected
B selected
```

There is deliberately no multi-selection yet.

No Shift/Ctrl modifier behavior, toggle selection, box selection or other multi-selection mechanism is part of this experiment.

## Hover preview

Hover is separate from selection.

When the pointer moves over a selectable component, that component receives a temporary visual highlight indicating what would be selected by a click.

Conceptually:

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
 selection replaces current selection
```

Hover must not modify the actual selection state.

The current implementation uses mode-specific picking:

- Vertex Mode → nearest projected vertex within a small pixel tolerance.
- Edge Mode → nearest projected edge segment within a small pixel tolerance.
- Face Mode → nearest positive ray/triangle intersection; the closest hit wins.

The picking tolerances and algorithms are experimental V1 choices, not production contracts.

## Mode-specific behavior

### Vertex Mode

Only vertices can be selected.

A click on a vertex selects that vertex. Clicking another vertex replaces the current selection.

The existing V1 Move interaction remains available in Vertex Mode: a drag beginning on a selected vertex starts the existing `MoveOperation`.

### Edge Mode

Only edges can be selected.

A click on an edge selects that edge. Clicking another edge replaces the current selection.

Edge selection does not start the Vertex Move operation.

### Face Mode

Only faces can be selected.

A click on a face selects that face. Clicking another face replaces the current selection.

Face selection uses the newly added filled-face representation and ray-based face picking so that overlapping projected faces resolve to the visible/front-most face.

Face selection does not start the Vertex Move operation.

## Selection and visual styling

For this experiment, vertex/edge/face selection colors are intentionally **not** treated as final UI design.

The implementation currently uses neutral geometry colors plus a temporary highlight so that normal, hover and selected states are visually distinguishable.

A later UI/visualization pass can define distinct colors or other styling for vertices, edges and faces.

That future requirement should nevertheless be kept in mind when structuring the implementation so that visual styling is not unnecessarily hard-coded into selection logic.

## Deliberately postponed

The following are outside the current experiment:

- Object Mode
- Multi-selection
- Shift/Ctrl selection modifiers
- Toggle selection
- Box/lasso selection
- Loop/ring selection
- Selection expansion/reduction
- Universal / All-in-One selection mode
- Automatic component-type detection in Universal Mode
- Final selection colors
- Soft Selection
- Advanced selection/picking behavior
- Topology editing operations
- Production `src/` architecture

## Future direction: Universal Mode

A later selection mode may support an all-in-one workflow in which the component under the cursor determines the selection target automatically:

```text
cursor
  ↓
hit test
  ↓
vertex / edge / face / object
  ↓
corresponding selection
```

This is intentionally only a future direction at this point. The current experiment keeps the selection mode explicit so that each component type can be tested independently.

## Experiment philosophy

This work remains inside `experiments/mirai_bastel_viewport_V1/`.

The purpose is to learn from actual interaction before defining the production architecture. The Core V1 analysis and hardening work can continue independently.

The results of this experiment should inform later architectural decisions, but the experiment itself is not considered production code.

## Implementation order

- [x] Add minimal filled-face/solid rendering.
- [x] Add explicit Vertex / Edge / Face mode switching.
- [x] Add mode-specific Vertex / Edge / Face picking.
- [x] Add hover highlighting for the three Sub-Object modes.
- [x] Add single-selection replacement for the three Sub-Object modes.
- [ ] Run and validate the interaction on real hardware.
- [ ] Document practical findings and unexpected behavior.
- [ ] Evaluate Object Mode separately.
- [ ] Only then evaluate multi-selection and the next selection design questions.
