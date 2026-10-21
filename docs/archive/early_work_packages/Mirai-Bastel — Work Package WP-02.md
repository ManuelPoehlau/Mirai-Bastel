# Mirai-Bastel — Work Package WP-02
## Interaction & Tool Framework

**Status:** Accepted for implementation  
**Date:** 2026-08-30  
**Branch:** `main`

This document defines the bounded implementation package that follows WP-01A. It is based on the actual repository state on `main`, not on earlier chat assumptions.

## 1. Goal

Establish a small, real editor/tool boundary so interactive modeling actions use one consistent lifecycle:

```text
Input
  ↓
Input Mapping / Context
  ↓
Command
  ↓
Tool / Interaction
  ↓
Operation
  ↓
History
  ↓
Core
```

The package must make **Move** the first concrete reference tool without prematurely designing a complete editor framework.

## 2. Why now

WP-01A validated viewport navigation, picking, selection, input mapping, commands, context resolution and the practical `Selection → MoveOperation → History → Undo/Redo` path. The remaining architectural gap is that interactive Move is still implemented as implicit window state rather than as a first-class Tool.

The Core already provides the reusable `Operation` lifecycle (`begin/update/commit/cancel`) and a concrete `MoveOperation`. Therefore WP-02 should connect existing pieces rather than invent a second operation framework.

## 3. Architectural position

### Tool vs Operation

A **Tool** owns temporary editor interaction state:

- activation/deactivation;
- beginning an interaction;
- interpreting pointer/keyboard input;
- transient preview/update state;
- confirmation;
- cancellation.

An **Operation** owns the actual persistent domain mutation and remains independent of UI/input details.

```text
Move Command
    ↓
Move Tool
    ↓
Move Operation
    ↓
Mesh
```

### Selection vs Tool

Selection answers:

> Which elements are selected?

A Tool answers:

> What should be done with the current selection?

Selection is therefore not a Tool and does not become a new generalized interaction framework in this package.

The current direct manipulation UX may remain Tweak-like (`LMB drag` can start Move). The architectural distinction must nevertheless exist internally.

## 4. Scope

### 4.1 Minimal Tool contract

Introduce the smallest useful lifecycle for interactive tools. The exact Python API is an implementation detail, but it must represent these concepts:

```text
activate
begin / start interaction
update*
commit
cancel
deactivate
```

The lifecycle must prevent stale interactive state and make the end of an operation explicit.

### 4.2 Active Tool ownership

Provide a minimal mechanism for tracking the currently active interactive Tool.

At most one interactive modeling Tool is active for the tested viewport context.

The implementation must support returning cleanly to an idle state after commit or cancel.

Do not create a plugin registry, dependency-injection framework, command palette or speculative multi-window tool orchestration.

### 4.3 Command → Tool routing

A command that requires modal interaction must resolve to its Tool rather than embedding the interaction in the Window event handler.

For this package:

```text
Command.Move → MoveTool
```

Commands that are not interactive may continue to use direct actions.

### 4.4 Move reference Tool

MoveTool must use the existing Core MoveOperation rather than implementing a second mutation mechanism.

The current viewport behavior should be preserved where practical:

- selected components are moved;
- drag updates the operation incrementally;
- Esc cancels;
- release/confirmation commits;
- undo/redo operates at the committed operation boundary.

The exact gesture is not an architectural requirement. The existing Tweak-style interaction is a valid UX implementation of the Tool boundary.

### 4.5 Input routing

Physical input remains mapped to Commands. Tools must not contain hard-coded physical key/button bindings.

The existing minimal Context model remains sufficient unless implementation demonstrates a concrete missing use case.

Do not expand Context into a hierarchy or global framework merely for future possibilities.

### 4.6 Selection-to-operation resolution

The current experiment resolves the affected vertex IDs from the current selection. WP-02 may move that responsibility to the appropriate Tool/interaction helper if necessary, but must not redesign Core Selection.

Expected principle:

```text
Selection
   ↓
Tool determines affected domain elements
   ↓
Operation receives domain data
```

Examples already supported by the experiment may include vertex selection directly and edge/face selections through their referenced vertices.

## 5. Explicit non-scope

Do not implement in WP-02:

- Rotate
- Scale
- a complete Transform framework
- Pivot
- Local/Global Transform Space
- transform gizmos
- snapping
- soft selection
- object mode
- Object/Component architecture
- keymap editor
- Preferences system
- plugin system
- command palette
- new renderer architecture
- new topology architecture
- Extrude, Inset, Bevel, Slide or Loop Insert
- Morph, Skin, Rigging or Animation
- speculative Core abstractions

WP-02 is not permission to redesign `src/core/`.

## 6. Dependencies

### Hard

- Core V1 / frozen Core
- Selection
- existing Operation lifecycle
- History
- Viewport V1 interaction/input layer
- existing Command/Input Mapping layer

### Soft

- existing axis-constraint experiment;
- topology experiments;
- picking refinements.

### Parallel / independent

- topology algorithm research and experiments;
- Object/Component architecture research;
- provenance/remapping research;
- materials/renderer research;
- future keymap UI research.

## 7. Core Freeze

`src/core/` remains frozen.

If implementation discovers a missing Core capability:

1. identify the exact requirement;
2. verify whether existing public APIs can satisfy it;
3. document the gap;
4. do not make an opportunistic Core change;
5. treat any required Core extension as a separate architecture decision.

## 8. State model

The minimum externally meaningful state is:

```text
IDLE
  ↓ activate
ACTIVE
  ↓ begin
INTERACTING
  ├── update*
  ├── commit → ACTIVE/IDLE
  └── cancel → ACTIVE/IDLE
```

A committed operation must not leave an active interaction behind.
A cancelled operation must not leave persistent model mutation or a new History entry.

If a Tool is activated but no interaction has started, it must be possible to deactivate it without creating model History.

## 9. History contract

For a successful Move interaction:

```text
begin
update*
commit
```

must result in one logical committed model change and one corresponding History action, according to the existing Core History contract.

For cancellation:

```text
begin
update*
cancel
```

must restore the pre-interaction model state and create no new History action.

Transient pointer movement must never create one History entry per update.

## 10. Tests

Add focused automated tests for the new Tool boundary.

### Tool lifecycle

- activation enters the expected state;
- begin enters interaction state;
- multiple updates are accepted;
- commit exits interaction state;
- cancel exits interaction state;
- deactivation cannot leave stale interactive state.

### Move integration

- MoveTool starts the existing MoveOperation;
- update changes the live model state as expected;
- commit leaves the expected final state;
- cancel restores the exact initial state;
- commit produces exactly the intended History action;
- cancel produces no new History action;
- multiple updates still produce one logical committed action.

### Routing

- `Command.Move` resolves to MoveTool;
- changing the input binding does not require changing MoveTool;
- no Tool contains direct pyglet key/button constants.

### Regression

All existing experiment tests must remain green.
The production Core suite must remain green and `src/core/` must remain unchanged.

## 11. Practical Viewport Test

The real running viewport is mandatory for completion.

### Move / commit

```text
1. Start the normal test viewport.
2. Select a vertex, edge or face as supported by the current experiment.
3. Start the existing Move/Tweak interaction.
4. Drag and observe live movement.
5. Perform several pointer updates.
6. Commit the move.
7. Undo.
8. Verify the exact pre-move state.
9. Redo.
10. Verify the committed move returns.
```

### Move / cancel

```text
1. Select geometry.
2. Start Move.
3. Drag to a clearly different position.
4. Press Esc.
5. Verify the original geometry is restored.
6. Verify no additional History step was created.
```

### Interaction sanity

Verify that after both commit and cancel:

- the viewport remains usable;
- no stale drag state remains;
- selection remains coherent;
- camera navigation still works;
- topology commands still work;
- viewport-only actions still do not create model History.

## 12. Architecture verification

At completion, explicitly inspect the implementation against these contracts:

1. Physical input is translated to Commands by the existing mapping boundary.
2. Commands express intent and are not physical bindings.
3. Tools own temporary interactive state.
4. Operations own persistent model mutation.
5. Operations contain no UI/input dependencies.
6. History is created at commit boundaries, not per pointer update.
7. Selection remains domain state and is not turned into a Tool.
8. Viewport-only actions do not enter model History.
9. Core remains independent of Viewport/UI/Input.
10. No large generic framework was introduced without a demonstrated requirement.

## 13. Expected affected area

Implementation should remain inside the existing experimental Viewport V1 area unless a concrete architecture decision justifies otherwise:

```text
experiments/mirai_bastel_viewport_V1/
```

Likely areas include:

- viewport command/dispatch code;
- Tool/interaction code;
- Move integration;
- focused tests;
- local README/documentation where behavior changes.

Do **not** create a production `src/tools/` or `src/viewport/` hierarchy merely to satisfy this WP. The production source layout remains an explicit future architecture decision.

## 14. Documentation

During implementation, update only authoritative documents whose facts actually change.

Potential updates:

- `docs/architecture/ROADMAP.md` — WP-02 completion status after the package is actually complete;
- `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md` — only if the accepted contract needs clarification based on the implementation;
- `experiments/mirai_bastel_viewport_V1/README.md` — actual user-visible behavior.

Do not duplicate this specification into another permanent architecture document.

## 15. Definition of Done

- [ ] Tool lifecycle exists and is tested.
- [ ] Active Tool state is explicit and cannot remain stale after completion.
- [ ] Command-to-Tool routing exists for Move.
- [ ] MoveTool uses the existing MoveOperation.
- [ ] Selection and Tool responsibilities are distinct.
- [ ] Commit produces the intended persistent change and History boundary.
- [ ] Cancel restores the pre-interaction state without a new History action.
- [ ] Multiple updates do not create multiple History actions.
- [ ] Existing input bindings remain configurable and Tool code is input-independent.
- [ ] Existing topology and viewport behavior remains functional.
- [ ] Automated tests are green.
- [ ] Production Core tests remain green.
- [ ] `src/core/` is unchanged unless a separately approved Core decision is made.
- [ ] Practical viewport commit test passes.
- [ ] Practical viewport cancel test passes.
- [ ] Architecture review confirms the intended boundaries.
- [ ] Relevant documentation is updated.
- [ ] Final Git diff is reviewed for scope creep.
- [ ] Clean commit is created.

## 16. Implementation workflow

Follow this sequence as one bounded work package:

```text
Repository re-check
      ↓
Architecture / spec confirmation
      ↓
Implementation plan
      ↓
Implementation
      ↓
Automated tests
      ↓
Practical viewport verification
      ↓
Architecture / scope review
      ↓
Documentation
      ↓
Git diff review
      ↓
Commit
```

If implementation reveals that a fundamental architecture decision is wrong, stop the implementation at that boundary, document the problem and request/review the alternative rather than silently changing the architecture.
