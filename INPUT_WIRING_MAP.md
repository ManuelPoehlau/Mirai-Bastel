# Mirai-Bastel — Artist Playground Input Map

**Purpose:** Artist-defined desired physical input bindings  
**Status:** Draft / Artist Input Decision  
**Date:** 2026-09-18

> Fill in the **Desired Input** column.
>
> Do not change the Interaction Behavior column here.
> The existing interaction behavior is preserved during the Input Wiring pass.
>
> Examples:
> - `X`
> - `M`
> - `Alt + LMB`
> - `Ctrl + LMB`
> - `Shift + X`
> - `Mouse Wheel`
> - `X + LMB Drag`
>
> If you don't want to decide something yet, write `TBD`.

---

## 1. Navigation

| Function                | Current Input  | Desired Input | Interaction Behavior  | Notes |
| ----------------------- | -------------- | ------------- | --------------------- | ----- |
| Orbit                   | Alt + LMB drag | keep          | Modifier + mouse drag |       |
| Pan                     | MMB drag       | keep          | Mouse drag            |       |
| Zoom                    | Mouse Wheel    | keep          | Wheel                 |       |
| Frame / Focus Selection | TBD            |               |                       |       |
| Reset / Home View       | TBD            |               |                       |       |

---

## 2. Selection Mode

| Function              | Current Input | Desired Input | Interaction Behavior | Notes |
| --------------------- | ------------- | ------------- | -------------------- | ----- |
| Vertex Selection Mode | `1`           | keep          | Press                |       |
| Edge Selection Mode   | `2`           | keep          | Press                |       |
| Face Selection Mode   | `3`           | keep          | Press                |       |

---

## 3. Selection Behavior

| Function                  | Current Input          | Desired Input | Interaction Behavior | Notes |
| ------------------------- | ---------------------- | ------------- | -------------------- | ----- |
| Replace Selection         | `M` variant            | keep          | Experiment variant   |       |
| Toggle Selection          | `M` variant            | keep          | Experiment variant   |       |
| Modifier Selection        | `M` variant            | keep          | Experiment variant   |       |
| Box Select                | `Q` variant            |               | Experiment variant   |       |
| Lasso Select              | `Q` variant            |               | Experiment variant   |       |
| Paint Select              | `Q` variant            |               | Experiment variant   |       |
| Face Picking              | Current picking        |               | Click                |       |
| Hover / Preview Selection | Current implementation |               | Mouse hover          |       |
| Add to Selection          | TBD                    |               |                      |       |
| Remove from Selection     | TBD                    |               |                      |       |
| Clear Selection           | TBD                    |               |                      |       |
| Select All                | TBD                    |               |                      |       |
| Invert Selection          | TBD                    |               |                      |       |

---

## 4. Transform — Move / Rotate / Scale

| Function | Current Input | Desired Input | Interaction Behavior | Notes |
| -------- | ------------- | ------------- | -------------------- | ----- |
| Move     | `X`           | W             | Existing variant     |       |
| Rotate   | `R`           | E             | Existing variant     |       |
| Scale    | `S`           | R             | Existing variant     |       |

### Transform Constraints

| Function | Current Input | Desired Input | Interaction Behavior | Notes |
|---|---|---|---|---|
| Move X Axis | `Shift + X` / current | | Modifier / constraint | |
| Move Y Axis | `Shift + Y` / current | | Modifier / constraint | |
| Move Z Axis | `Shift + Z` / current | | Modifier / constraint | |
| Move XY Plane | TBD | | Constraint | |
| Move XZ Plane | TBD | | Constraint | |
| Move YZ Plane | TBD | | Constraint | |
| Rotate X Axis | TBD | | Constraint | |
| Rotate Y Axis | TBD | | Constraint | |
| Rotate Z Axis | TBD | | Constraint | |
| Rotate XY Plane | TBD | | Constraint | |
| Rotate XZ Plane | TBD | | Constraint | |
| Rotate YZ Plane | TBD | | Constraint | |
| Scale X Axis | TBD | | Constraint | |
| Scale Y Axis | TBD | | Constraint | |
| Scale Z Axis | TBD | | Constraint | |
| Scale XY Plane | TBD | | Constraint | |
| Scale XZ Plane | TBD | | Constraint | |
| Scale YZ Plane | TBD | | Constraint | |

---

## 5. Transform Interaction Variants

> These are **not** being redesigned in the Input Wiring pass.
> This section documents the existing interaction variants so their physical
> inputs can be kept separate from the action itself.

| Function / Variant | Current Input | Desired Input | Interaction Behavior | Notes |
|---|---|---|---|---|
| Transform — Hold Key | X / R / S | | Hold-to-activate | |
| Transform — Press Mode | X / R / S | | Press-to-toggle | |
| Transform — Press-Drag-Click | X / R / S + LMB | | Press / drag / click | |
| Tweak — Hold Key | X / R / S | | Existing Tweak variant | |
| Tweak — Silo | Ctrl + LMB | | Existing Tweak variant | |
| Tweak — Hold Click | X / R / S + LMB | | Existing Tweak variant | |
| Tweak — Hold Ctrl | Ctrl + mouse motion | | Existing Tweak variant | |

---

## 6. Topology

| Function | Current Input | Desired Input | Interaction Behavior | Notes |
|---|---|---|---|---|
| Extrude | TBD / current | | | |
| Connect Edges | TBD / current | | | |
| Loop Select | TBD / current | | | |
| Ring Select | TBD / current | | | |
| Loop Insert | TBD / current | | | |
| Loop Slide | TBD / current | | | |
| Edge / Topology Select | TBD / current | | | |
| Topology Operation Restore / Cancel | `F` / current | | | |
| Restore Articulation | `F` / current | | | |
| Cancel Current Operation | `ESC` | | | |
| Undo | `Ctrl + Z` / current | | | |
| Redo | `Ctrl + Y` / current | | | |

---

## 7. Display / Presentation

| Function | Current Input | Desired Input | Interaction Behavior | Notes |
|---|---|---|---|---|
| Toggle Wireframe | `Z` | | Toggle | |
| Toggle Vertex Display | `V` | | Toggle | |
| Shading / Presentation Variant 1 | Current | | Variant | |
| Shading / Presentation Variant 2 | Current | | Variant | |
| Shading / Presentation Variant 3 | Current | | Variant | |
| Shading / Presentation Variant 4 | Current | | Variant | |
| Shading / Presentation Variant 5 | Current | | Variant | |
| Shading / Presentation Variant 6 | Current | | Variant | |

---

## 8. Modeling / Component Operations

| Function | Current Input | Desired Input | Interaction Behavior | Notes |
|---|---|---|---|---|
| Vertex Move | Move | | Transform | |
| Edge Move | Move | | Transform | |
| Face Move | Move | | Transform | |
| Vertex Rotate | Rotate | | Transform | |
| Edge Rotate | Rotate | | Transform | |
| Face Rotate | Rotate | | Transform | |
| Vertex Scale | Scale | | Transform | |
| Edge Scale | Scale | | Transform | |
| Face Scale | Scale | | Transform | |
| Delete Component | TBD | | | |
| Duplicate Component | TBD | | | |
| Merge / Weld | TBD | | | |

---

## 9. Experiment / Playground Controls

| Function | Current Input | Desired Input | Interaction Behavior | Notes |
|---|---|---|---|---|
| Cycle Selection Variant | `Q` / current | | Cycle | |
| Cycle Selection Mode / Strategy | `M` / current | | Cycle | |
| Cycle Transform Variant | Current | | Cycle | |
| Cycle Presentation Variant | Current | | Cycle | |
| Keep Current Variant | TBD | | Experiment decision | |
| Iterate Current Variant | TBD | | Experiment decision | |
| Reject Current Variant | TBD | | Experiment decision | |
| Reset Experiment Variant | TBD | | | |

---

## 10. General / Application

| Function | Current Input | Desired Input | Interaction Behavior | Notes |
|---|---|---|---|---|
| Cancel | `ESC` | | Immediate cancel | |
| Confirm / Commit | `ENTER` / current | | Commit | |
| Save | TBD | | | |
| Load | TBD | | | |
| Quit | `Q` / current | | | |
| Toggle HUD | TBD | | | |
| Toggle Debug Information | TBD | | | |

---

# 11. Free Artist Notes

Use this space for ideas that don't fit the tables above.

```text
-
-
-
-
-