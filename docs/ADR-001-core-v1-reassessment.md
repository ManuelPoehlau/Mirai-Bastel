# ADR-001 — Core V1 Reassessment

**Status:** Accepted  
**Date:** 2026-09-01

## Context

`src/core` was originally placed under a V1 freeze after the initial foundation work. As Mirai-Bastel transitions from validated experiments toward a Production Application, an absolute freeze increasingly prevents validated functionality from becoming reusable Production functionality.

The project therefore needs a controlled way to extend the Core without turning the WP-04 transition into an unrestricted Core refactor or prematurely designing a Core V2.

## Decision

The absolute **Core V1 freeze is lifted**.

`src/core` may be extended when a concrete Production requirement justifies the extension. Extensions must remain focused on the required domain semantics and must not introduce unrelated refactoring or a premature Core V2.

For WP-04, the following functionality is explicitly considered Core functionality:

- Move
- Rotate
- Scale
- geometric constraint semantics required by these transformations

The Core owns the transformation semantics and resulting operations. It does **not** own user interaction.

Production owns:

- input handling
- keyboard shortcuts / bindings
- commands
- tool activation and lifecycle
- mouse interaction
- UI and other presentation concerns

The intended boundary is therefore:

```text
User Input / UI
      ↓
Production Interaction
      ↓
Production Tool
      ↓
Core Operation / Transform Semantics
      ↓
Core Data
```

## Rationale

Move, Rotate and Scale are fundamental modeling operations and are required for a useful first Production Editor. Their mathematical and geometric semantics should be reusable independently of a particular input mechanism or UI.

Keeping these semantics in Production would make them unnecessarily coupled to the current interaction layer and would encourage duplicated transformation logic for future interfaces such as gizmos, alternative bindings, or other tools.

At the same time, lifting the freeze does **not** justify broad Core restructuring. The existing Core remains the foundation; it is extended deliberately when Production requirements demonstrate the need.

## Consequences

### Positive

- Validated functionality can move from experiments into reusable Production functionality.
- Transformation semantics have a clear architectural home.
- Production input and UI remain decoupled from mathematical Core behavior.
- Future interaction methods can reuse the same Core operations.
- Core evolution can proceed incrementally as the application grows.

### Constraints

- Core changes must remain requirement-driven.
- Unrelated refactoring remains out of scope.
- Core V2 is not being designed by this decision.
- Experiment code remains a Research/Validation layer and is not promoted wholesale into Core or Production.

## Scope of this ADR

This decision establishes the architectural direction for Core evolution and specifically authorizes the WP-04 Transform Foundation work described above.

It does not define the complete future architecture of `src/core` and does not pre-authorize unrelated future Core changes.
