# Project Vision — V1 Is a Milestone, Not the Architecture Target

## Core principle

> **V1 is a development milestone, not the architectural endpoint.**
>
> **Implement little. Assume much.**

The first practical goal is a small, intuitive, Mirai/Nendo-inspired modelling environment. However, the project itself is intentionally larger than a modeller.

We are building the beginning of an open, flexible, extensible 3D authoring environment whose architecture should allow the same underlying scene/data to evolve continuously across different kinds of work.

The historical Mirai/Weta workflow is inspiration, not a specification. We do not claim to know every detail of the historical implementation. We want to understand which architectural ideas enabled a workflow where modelling, deformation, rigging, morphs and animation could be revisited without destroying the surrounding work.

## Long-term system direction

The eventual system may contain, among other things:

```text
Scene / Core
├── Geometry / Topology
├── Selection
├── Transform / Interaction
├── History
├── Deformation
├── Morph Targets
├── Rig / Skeleton
├── Animation
├── Materials
├── Camera / View
└── Extensions / Scripts
```

And the same core should eventually be accessible through multiple interaction surfaces:

```text
                 Scene Core
                    │
        ┌───────────┼───────────┐
        │           │           │
      Human UI    Scripts       AI
        │           │           │
        └───────────┼───────────┘
                    │
               Core APIs
```

A representative long-term workflow is:

```text
Model
  ↓
Add rough rig
  ↓
Test deformation
  ↓
Notice missing geometry
  ↓
Return to modeling
  ↓
Modify mesh
  ↓
Return to rig / animation
  ↓
Continue
```

The system should remain alive and editable rather than becoming a collection of destructive, isolated stages.

## How V1 architecture must be evaluated

Every architectural decision should be classified into four categories:

### A — Implement now

Required for the first useful modelling prototype.

### B — Architecturally compatible now

Not implemented yet, but V1 must establish a contract or data boundary that does not make known future capabilities unnecessarily difficult.

Examples include:

- morph targets
- rigging
- animation
- deformation
- scripting
- AI interaction
- future topology systems
- non-destructive workflows

### C — Explicitly future

Known or plausible future functionality for which no architectural implementation is currently required.

### D — Do not prematurely generalize

Interesting future capabilities that should remain simple or absent until real use cases justify generalization.

## Important distinction

> **"Not implemented in V1" does not mean "architecturally ignored."**

A future feature may require a new implementation, but it should not unnecessarily require redefining stable core contracts that were already established for V1.

Conversely, future compatibility must not become an excuse to build frameworks prematurely.

The desired balance is:

```text
Small V1 implementation
        +
Stable boundaries for known future needs
        +
No speculative framework-building
        =
A core that can grow naturally
```

## Examples

### Half-Edge topology

V1 does not need a full Half-Edge implementation.

However, topology access should be abstracted so that a later Half-Edge implementation can replace simple V1 scans without forcing operations, interaction code or scripting APIs to be rewritten.

### Morph / Rig / Animation

V1 does not implement these systems.

However, the Mesh, History, Operation and Scene boundaries must not assume that geometry exists only for immediate destructive modelling and can never have persistent deformation or animation relationships.

### AI / Scripting

V1 does not need a complete AI framework or plugin ecosystem.

However, stable element handles and explicit core APIs are important because future scripts and AI agents should be able to inspect and manipulate the same underlying scene through controlled interfaces.

## Architectural rule for future versions

V2, V3, etc. are not promises that the application will eventually be "finished" at some version number.

Versions are development milestones used to introduce capabilities safely.

The long-term project remains intentionally open-ended:

> **The system is meant to remain extensible, alive and capable of evolving.**

A later version may expand the application domain rather than merely add more tools to the original modeller.

## Reminder to the project team

When evaluating a V1 proposal, always ask two questions:

1. **Is this the smallest thing we need today?**
2. **Does this accidentally make something we already know we want tomorrow unnecessarily expensive?**

If the answer to the first is no, simplify.

If the answer to the second is yes, change the boundary before writing production code.
