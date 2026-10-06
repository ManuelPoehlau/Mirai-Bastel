# Context-Sensitive Input Architecture Research V1

**Status:** Discovery / Research — no architecture decision  
**Scope:** Input, bindings, context resolution and context-sensitive modeling interactions  
**Date:** 2026-10-06

## 1. Purpose

Mirai-Bastel is moving toward a direct, hotkey-first modeling workflow. As the number of modeling operations grows, a flat global keymap becomes increasingly difficult to reason about:

- the same physical input may have different meanings in different modes;
- selection/component mode can change the intended command;
- hover state can provide important local context;
- an active tool or interaction can temporarily own input;
- viewport focus and future application rooms may introduce additional context.

This document investigates how those contexts could be represented and resolved **without replacing the existing input architecture prematurely**.

This is a research document. It does **not** define a final implementation and does not constitute an Artist decision.

---

## 2. Current Architectural Shape

The current production interaction path is broadly:

~~~
Physical Input
    ↓
Binding / Context
    ↓
Command
    ↓
Tool / Interaction
    ↓
Operation
    ↓
Core / History
~~~

The important separation is:

- **Input** — what physically happened.
- **Binding** — under which circumstances an input maps to a command.
- **Command** — what the user intends to invoke.
- **Tool / Interaction** — how the command behaves over time.
- **Operation** — the actual mesh/domain mutation.

The existing system already has context-aware binding support. A binding lookup can receive a context and fall back to the global binding set. This means the project does **not** need a new input system merely to support more context.

The research question is therefore narrower:

> How much context should participate in binding resolution, and where should that decision live?

---

## 3. Existing Context Mechanisms

The production application already distinguishes several interaction situations.

### 3.1 Global input

Some commands are naturally global or close to global:

- Undo / Redo
- Escape / cancellation
- application-level navigation
- other commands that should remain available independently of the selected component

These should not become unnecessarily buried under modeling-specific context.

### 3.2 Modeling / topology context

Topology-related commands can use a dedicated context rather than competing with unrelated global bindings.

This is already visible in the existing connection/split/knife handling.

### 3.3 Active interaction context

Some tools temporarily own input while an interaction is active.

The current application explicitly treats states such as Transform and Knife as interaction owners. Knife, for example, has its own handling for commit, cancel, lift and session undo/redo.

This is important because an active tool is not merely another selection mode. It can change the meaning of otherwise ordinary inputs.

### 3.4 Selection/component mode

The Selection state already distinguishes:

- Vertex
- Edge
- Face

It also stores the current selection and hover information.

This creates an obvious potential context dimension:

~~~
same input
    +
Vertex mode → vertex command
Edge mode   → edge command
Face mode   → face command
~~~

This is particularly relevant for topology commands.

### 3.5 Hover / focus

Hover is already separate from persistent selection.

That distinction is valuable:

~~~
Selection = what is selected
Hover     = what the artist is currently pointing at
~~~

A future context resolver could therefore use hover as **interaction context**, without turning hover into selection.

For example:

~~~
Edge selected + hover another edge
~~~

should remain different from:

~~~
Edge selected + no relevant hover target
~~~

---

## 4. The Problem With a Flat Keymap

A flat mapping tends toward:

~~~
Alt+L → Select Loop
Alt+R → Select Ring
C     → ...
W     → Move
E     → Rotate
R     → Scale
...
~~~

This works while the command has one stable meaning.

It becomes less attractive when the same gesture should depend on context.

For example, a future modeling workflow might reasonably want:

~~~
Double-click Edge
    → Edge Loop

Shift + Double-click Edge
    → Edge Ring

Double-click Vertex
    → Vertex-related selection

Double-click Face
    → Face-related selection
~~~

The physical input is not sufficient to determine the command.

The actual decision is closer to:

~~~
Input + Context → Command
~~~

The context can include selection mode, hover target, active tool, application mode and focus.

---

## 5. Context Should Be Treated as a Set of Dimensions

A strict single hierarchy is tempting:

~~~
Global
  ↓
Application
  ↓
Component
  ↓
Hover
  ↓
Tool
~~~

However, these are not always naturally hierarchical.

For example:

- **Edge mode** and **viewport focus** are different dimensions.
- **Hover = Edge** is not necessarily a child of Edge mode.
- **Knife active** may override several otherwise independent contexts.
- A future Sculpt room may change the available commands without changing the component type.

A better research model is therefore a **context snapshot composed of orthogonal dimensions**.

Conceptually:

~~~
ContextSnapshot
├── application / room mode
├── focus / area
├── selection component mode
├── hover target kind
├── active tool / interaction
└── other explicitly relevant state
~~~

Not every binding needs every dimension.

---

## 6. Candidate Context Dimensions

### A. Global

Always available unless an active interaction explicitly captures the input.

Examples:

- Undo
- Redo
- application-level navigation
- emergency cancel

### B. Application / Room

Where the artist currently is.

Examples:

- Model
- Rig / Skin
- Morph
- Animation
- future Paint or other rooms

This should not be implemented merely because these rooms are part of the long-term vision. It is a future context dimension to keep in mind.

### C. Component / Selection Mode

What kind of mesh element is currently being edited.

Examples:

- Vertex
- Edge
- Face

This is particularly relevant for topology commands.

### D. Hover Target

What the pointer is currently over.

Examples:

- nothing
- vertex
- edge
- face
- object
- UI element

Hover is a transient observation, not persistent selection.

### E. Active Tool / Interaction

Whether an interaction currently owns the input.

Examples:

- normal modeling interaction
- Transform
- Knife
- future modal tools

This dimension is potentially stronger than ordinary component context because an active modal interaction may deliberately consume keys until it commits or cancels.

### F. Focus / Area

Where the input is directed.

Examples:

- 3D viewport
- future timeline
- future node editor
- text / numeric field

The viewport is currently the important area. Other areas should not be invented until they exist.

---

## 7. Candidate Resolution Model

A useful abstraction is:

~~~
Input
  +
ContextSnapshot
  ↓
Binding Resolver
  ↓
Command
~~~

The resolver should prefer the **most specific applicable binding** and fall back toward less specific bindings.

Conceptually:

~~~
specific interaction binding
        ↓
tool / component binding
        ↓
application binding
        ↓
global binding
~~~

This is not intended as a mandatory fixed five-level stack.

A binding could instead declare the context dimensions that matter to it.

For example:

~~~
Alt+L
context:
    component = EDGE
→ Select Edge Loop
~~~

while:

~~~
Ctrl+Z
context:
    global
→ Undo
~~~

The important property is:

> A binding only depends on the context that actually gives its input meaning.

---

## 8. Fallback Is Important

Context-specific bindings should not make the global keymap disappear.

For example:

~~~
Ctrl+Z
~~~

should not need separate definitions for:

- Vertex mode
- Edge mode
- Face mode
- Knife
- Transform
- etc.

Instead:

~~~
Try most specific applicable binding
        ↓
not found?
        ↓
try broader binding
        ↓
...
        ↓
global
~~~

This preserves the simplicity of a global keymap while allowing local specialization.

---

## 9. Example: Edge Loop / Ring Selection

The current Mirai workflow already uses explicit commands such as:

- Alt+L → Edge Loop
- Alt+R → Edge Ring

Other DCCs demonstrate additional interaction paths, such as:

- double-click an edge → loop selection
- Shift + double-click an edge → ring selection
- entering a loop/ring selection mode and using hover feedback
- explicit loop/ring commands

These are not necessarily competing features. They can be understood as multiple input routes to the same semantic commands.

For example:

~~~
Alt+L
    +
Edge context
    ↓
Select Edge Loop
~~~

and:

~~~
Double Click
    +
Hover = Edge
    ↓
Select Edge Loop
~~~

Both can resolve to the same command.

Likewise:

~~~
Shift + Double Click
    +
Hover = Edge
    ↓
Select Edge Ring
~~~

This suggests that **selection commands should remain semantic**, while the input layer decides which gesture invokes them.

---

## 10. Why Hover Should Not Be Baked Into Selection

A common architectural mistake would be to make:

~~~
Hover = selected
~~~

or to make hover-specific behavior mutate persistent selection implicitly.

That would blur two different concepts.

Mirai already benefits from keeping:

~~~
Selection → persistent artist state
Hover    → transient interaction observation
~~~

The context resolver can use hover to choose a command without changing that separation.

Example:

~~~
Hover = Edge
Double Click
    ↓
Select Loop
    ↓
Selection changes
~~~

The hover itself remains transient.

---

## 11. Tool Context and Command Semantics

The existing architecture separates commands from tools.

That boundary should be preserved.

The binding system answers:

> Which command does this input invoke here?

The command answers:

> What action should be requested?

The tool answers:

> How does this interaction proceed?

The operation answers:

> What domain/mesh change is performed?

Therefore a context-aware binding system should **not** become a second tool system.

Bad direction:

~~~
hotkey → giant context-specific implementation
~~~

Preferred direction:

~~~
input
  ↓
context resolution
  ↓
semantic command
  ↓
existing tool/operation path
~~~

This keeps the interaction architecture understandable.

---

## 12. What Should Not Be Done Yet

This research does **not** justify:

- replacing the current BindingSet;
- introducing a large generic event framework;
- rebuilding ToolManager;
- moving all input logic out of Application immediately;
- creating a universal context registry for hypothetical future rooms;
- implementing every DCC shortcut;
- making hover-dependent bindings for every tool.

The current architecture already provides enough foundation to investigate this incrementally.

The next useful step should be a **small real use case**, not an input-system rewrite.

---

## 13. Candidate Pilot

A sensible pilot is the Edge Loop / Ring family because it exercises several context dimensions without requiring a new modeling operation.

Candidate inputs:

| Input | Context | Command |
|---|---|---|
| Alt+L | Edge editing | Select Edge Loop |
| Alt+R | Edge editing | Select Edge Ring |
| Double Click | Hover = Edge | Select Edge Loop |
| Shift + Double Click | Hover = Edge | Select Edge Ring |

The pilot should reuse the existing selection and loop/ring commands.

Success would mean that multiple input routes can reach the same semantic command without duplicating the underlying operation.

It would **not** yet mean that a final context architecture has been accepted.

---

## 14. Research Questions

The following questions remain open:

1. Which context dimensions are actually required by Mirai's near-term workflow?
2. Should context matching be exact, partial or declarative?
3. How should conflicting bindings be diagnosed?
4. How should modifier combinations participate in specificity?
5. Should double-click be represented as a first-class input gesture or synthesized before binding resolution?
6. How should hover target type enter the context snapshot?
7. When should an active tool capture an input completely?
8. How should context-sensitive bindings be represented in the Artist Input Truth / input mapping documentation?
9. How should user overrides interact with context-specific bindings?
10. How should the system explain why a particular command won when multiple bindings match?
11. Which parts belong in production code and which parts should first be validated in the Playground?
12. What is the smallest architectural change that enables the pilot without creating speculative infrastructure?

---

## 15. Preliminary Assessment

**Observed:**

The existing architecture already separates physical input, bindings, commands and tool/operation behavior well enough to investigate context-sensitive input.

**Observed:**

The production application already has several explicit interaction contexts, including topology-related handling and active Transform/Knife interaction ownership.

**Gap:**

Context is currently represented only partially. Several decisions about what an input means still live as explicit application-level branches rather than being uniformly resolved from a context model.

**Hypothesis:**

A small context snapshot + binding-resolution layer could reduce those special cases while preserving the existing:

~~~
Input → Command → Tool → Operation
~~~

pipeline.

**Not decided:**

Whether such a resolver is actually necessary, what exact model it should use, and how much of the current Application logic should eventually move behind it.

---

## 16. Next Step

Do not implement a general context system from this document alone.

Instead:

~~~
Research
   ↓
small pilot
   ↓
observe real interaction
   ↓
Artist assessment
   ↓
architecture decision if justified
   ↓
incremental production change
~~~

The Edge Loop / Ring selection case is currently the strongest candidate for that pilot because it combines component context, hover context and multiple input routes while reusing existing semantic commands.

---

## Related Documents

- [Documentation map](../README.md) — documentation map and information hierarchy
- [Design](../design/README.md) — interaction and workflow design principles
- [Architecture](../architecture/README.md) — current architecture and accepted decisions
- [Topology research](topology/README.md) — topology research area
- [Agent Guide](../../AGENTS.md) — repository documentation and collaboration rules

## Related Production Areas

The current implementation relevant to this research is primarily under:

- src/mirai/application.py
- src/mirai/interaction/
- src/core/

These references identify the current implementation area; this research document does not make those files architectural authorities.
