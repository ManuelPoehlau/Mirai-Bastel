# Viewport V1 — Selection Modes Experiment

## Purpose

This document defines the next isolated experiment for `experiments/mirai_bastel_viewport_V1/`.

The goal is to extend the existing Viewport V1 practical test with the basic interaction model of a traditional polygon modeler, without changing the production Core architecture or moving the experiment into `src/`.

The experiment is deliberately small. It is intended to answer interaction and architectural questions through a working viewport before any production selection system is designed.

## Current baseline

Viewport V1 currently provides a minimal real-time OpenGL viewport connected to the Core V1 path. The existing experiment validates the basic Scene → Mesh → Selection → Move → Commit → History → Undo/Redo path together with camera interaction.

The viewport currently renders the test mesh as wireframe.

## Next step: visual representation

Before implementing all selection modes, the viewport should gain a minimal solid/filled representation of mesh faces.

This is required primarily for useful Face and Object selection feedback. The goal is **not** to build a complete rendering system at this stage.

The intended experimental representation is:

- Wireframe remains available for component visibility.
- Faces can be rendered filled.
- Vertices and edges should remain visually accessible on top of the filled geometry where useful for interaction testing.
- No final selection colors are defined yet.
- Rendering decisions made here are experimental and must not be treated as production architecture.

## Selection modes

The initial selection modes are:

### Vertex Mode

Only vertices can be selected.

A click on a vertex selects that vertex. Clicking another vertex replaces the current selection.

### Edge Mode

Only edges can be selected.

A click on an edge selects that edge. Clicking another edge replaces the current selection.

### Face Mode

Only faces can be selected.

A click on a face selects that face. Filled face rendering is therefore required for useful visual feedback.

### Object Mode

Only complete objects can be selected.

For the current test scene, clicking a visible part of the object should select the complete object. Filled geometry is useful here as well.

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

When the pointer moves over a selectable component, that component should receive a temporary visual highlight indicating what would be selected by a click.

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

## Selection and visual styling

For this experiment, vertex/edge/face selection colors are intentionally **not** specified.

The immediate requirement is only that the following states can be distinguished:

- normal
- hover
- selected

A later UI/visualization pass can define distinct colors or other styling for vertices, edges and faces.

That future requirement should nevertheless be kept in mind when structuring the implementation so that visual styling is not unnecessarily hard-coded into selection logic.

## Deliberately postponed

The following are outside the scope of this experiment:

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
- Advanced hit-testing behavior
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

This is intentionally only a future direction at this point. The first experiment keeps the selection mode explicit so that the behavior of each component type can be tested independently.

## Experiment philosophy

This work remains inside `experiments/mirai_bastel_viewport_V1/`.

The purpose is to learn from actual interaction before defining the production architecture. The Core V1 analysis and hardening work can continue independently.

The results of this experiment should inform later architectural decisions, but the experiment itself is not considered production code.

## Planned order

1. Add minimal filled-face/solid rendering to the viewport.
2. Establish generic hover highlighting.
3. Implement Vertex Mode with single selection.
4. Implement Edge Mode with single selection.
5. Implement Face Mode with single selection.
6. Implement Object Mode with single selection.
7. Test interaction and document findings.
8. Only then evaluate multi-selection and the next selection design questions.
