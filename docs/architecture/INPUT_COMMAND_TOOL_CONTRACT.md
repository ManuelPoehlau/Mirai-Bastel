# Mirai-Bastel — Input / Command / Tool / Operation Contract

**Status:** Accepted architectural contract for WP-01A; implementiert und praktisch validiert im Viewport-V1-Experiment (`experiments/mirai_bastel_viewport_V1/`, 2026-08-29)
**Date:** 2026-08-29
**Branch:** `main`

This document defines the basic separation between physical input, user commands, interactive tools and model-changing operations. It is intentionally small and is not a commitment to a large generic input framework.

## 1. Purpose

Mirai-Bastel should support direct, fast modeling interaction while allowing users to configure keyboard and mouse bindings without changing tool or modeling implementation code.

The basic conceptual path is:

```text
Physical Input
      ↓
Input Mapping
      ↓
Command
      ↓
Tool / Action
      ↓
Operation
      ↓
History / Core
```

Not every command requires every layer.

```text
Input
  ↓
Command
  ↓
[optional Tool]
  ↓
[optional Operation]
  ↓
[optional History]
```

## 2. Definitions

### Input

A physical user interaction: key, mouse button, wheel event, modifier combination, or equivalent device event.

Input describes **what happened**, not what that input means in the application.

Examples:

- `M`
- `Ctrl+Z`
- `LMB`
- `MMB drag`
- `Shift+MMB`
- mouse wheel

### Command

A named user action with application meaning.

Examples:

- `Move`
- `Extrude`
- `ConnectEdges`
- `Undo`
- `Redo`
- `Orbit`
- `ToggleWireframe`

A Command is not a hotkey. A hotkey or mouse binding is only one possible way to invoke a Command.

### Tool

An interactive, temporary working state used when a Command requires modal interaction.

A Tool may handle:

- activation;
- interaction/update;
- preview;
- constraints;
- confirmation;
- cancellation.

Example:

```text
Command.Move → MoveTool
```

A Command does not necessarily require a Tool. `Undo` or `ToggleWireframe` may be direct actions.

### Operation

A domain-level change to persistent model data.

Operations must not depend on keyboard, mouse, viewport or UI details. They receive domain-relevant data and perform the corresponding model change.

Example:

```text
MoveTool → MoveOperation → Mesh
```

### History

History records committed model changes according to the existing Core V1 History contract. Interactive preview updates must not accidentally become a separate History entry for every mouse movement.

## 3. Binding and Context

Bindings belong to an input-mapping layer, not to individual Tools.

The conceptual resolution path is:

```text
Input
  ↓
Context
  ↓
Binding
  ↓
Command
```

The implementation should support enough context to distinguish current viewport/editor interactions from global actions, but must not introduce a complex hierarchical context framework without a demonstrated use case.

A binding may be changed without changing the Command, Tool or Operation implementation.

For example:

```text
Default:
M → Move

User-configured:
G → Move
```

Both invoke the same `Move` Command.

The same principle applies to mouse bindings.

## 4. Examples

### Modeling command

```text
M
↓
Input Mapping
↓
Command.Move
↓
MoveTool
↓
MoveOperation
↓
History
```

### Viewport navigation

```text
MMB drag
↓
Input Mapping
↓
Command.Orbit
↓
Viewport / Camera action
```

No Core Operation or History entry is required.

### Display mode

```text
W
↓
Input Mapping
↓
Command.ToggleWireframe
↓
Viewport display action
```

Again, this is not a model edit and does not belong in model History.

## 5. Architectural Rules

1. Physical input must not be hard-coded directly into individual modeling implementations.
2. Bindings map Inputs to Commands.
3. Commands express user intent, not physical input.
4. Tools own temporary interactive/modal state.
5. Operations own persistent model changes.
6. Operations must remain independent of UI/input details.
7. History records committed model changes, not every transient interaction event.
8. Viewport-only actions must not create model History entries.
9. Context handling should remain minimal until real use cases require more.
10. This contract does not require a full Preferences UI; a minimal configurable binding representation/API is sufficient for WP-01A.

## 6. Relationship to the Core Freeze

This contract does not authorize changes to `src/core/`.

If implementation of the input/tool boundary reveals a missing production Core capability, the requirement must be demonstrated and documented first. Any Core change remains an explicit architecture decision under the project's experiment/Core-freeze policy.

## 7. Scope for WP-01A

WP-01A uses this contract to establish:

- basic configurable keyboard bindings;
- basic configurable mouse bindings;
- viewport navigation;
- selection interaction;
- Shaded / Flat Shaded / Wireframe display modes;
- Wireframe Overlay on/off;
- clear user feedback;
- automated mapping/state tests;
- practical viewport verification.

A full keymap editor, plugin system, command palette, sophisticated preferences system and generic framework are explicitly outside this package.
