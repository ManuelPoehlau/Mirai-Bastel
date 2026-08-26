# Mirai-Bastel — Core V1 Review

**Review scope:** `experiments/mirai_bastel_core_V1/`

**Basis:** `docs/V1_SPEC.md`, `docs/architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md`, `docs/architecture/AD-004-SYSTEM-VISION-REEVALUATION.md` and the Core V1 implementation supplied for architecture validation.

**Status:** Review only. No Core code changes are implied by this document.

---

## 1. Purpose of this review

Core V1 is deliberately small. It is **not** supposed to be a complete modeling architecture for the final Mirai-Bastel system.

The project vision is larger: the first practical product is a Modeler, but the Modeler is only one subsystem of a persistent Scene/Core system that may later grow into deformation, rigging, animation, materials, scripting, AI-assisted interaction and other systems.

Therefore this review uses two filters:

1. **Vision / future-boundary filter:** Does V1 accidentally make a known future subsystem difficult or impossible to add without a rewrite?
2. **Overengineering filter:** Is a suspected issue actually an architectural problem, or is it simply a reasonable V1 simplification that can be replaced later behind an existing boundary?

The goal is not to make V1 future-complete. The goal is:

> **Implement little — assume much.**
>
> Build the smallest useful foundation while avoiding assumptions that would unnecessarily lock the future system into a dead end.

---

# 2. Overall assessment

**Verdict: the Core V1 is architecturally on the right track.**

The implementation is substantially closer to the intended long-term architecture than a simple "mini modeler" prototype. In particular, the following decisions are already aligned with the project vision:

- stable opaque IDs rather than array indices as identity;
- topology accessed through a query API rather than exposed containers;
- topology mutations documenting ID continuity;
- generic `begin / update / commit / cancel` operation lifecycle;
- generic Command-based History rather than Mesh-specific history;
- Selection kept as independent domain state;
- Scene used as a system-level container rather than serializing only a Mesh;
- reserved Scene slots for future Morph/Rig/Animation systems;
- serialization deliberately kept small instead of prematurely designing a universal asset/plugin format.

This means **no rewrite is indicated by this review**.

There are a few points that should be clarified or checked before the Core becomes a dependency for larger amounts of functionality. Most are documentation/contract issues rather than architectural changes.

---

# 3. Classification system

Every finding is classified as one of four categories:

| Category | Meaning | Action |
|---|---|---|
| 🟢 KEEP | Correct V1 decision and compatible with the larger system | Leave as-is |
| 🟡 DOCUMENT / CLARIFY | V1 implementation is fine, but the contract should be explicit | Small clarification/test |
| 🟠 FIX NOW | A known future requirement is being structurally blocked | Small architectural change before building on it |
| 🔵 LATER | Valid future concern, but implementing it now would be premature | Record; do not build |

The review deliberately avoids turning 🔵 LATER items into V1 engineering tasks.

---

# 4. Stable IDs

## Verdict: 🟢 KEEP + 🟡 DOCUMENT

The ID strategy is appropriate for V1: IDs are opaque, monotonic and not reused. This is important beyond simple bookkeeping because future deformation systems may need to determine which elements survived a topology mutation.

The most valuable part is not the allocator itself, but the **ID-continuity contract attached to topology mutations**.

For example, `split_edge()` establishes the conceptual relationship:

```text
old edge ID       -> invalid
old endpoint IDs  -> survive
new midpoint      -> new vertex ID
new half edges    -> new edge IDs
face IDs          -> survive
```

This is exactly the information a later Morph/Weight remapping system would need as a starting point.

### Important boundary

Do **not** build generic attribute migration or weight remapping now.

The current architecture only needs to preserve enough information that such a system remains possible later.

### Required discipline

Every future topology mutation must document:

- IDs that survive;
- IDs that become invalid;
- IDs that are newly created;
- any secondary elements whose IDs may disappear as a consequence.

This is an architectural contract, not a V1 feature.

---

# 5. Topology representation

## Verdict: 🟢 KEEP

The decision to use ordered Face boundaries and a query/mutation API instead of immediately implementing a full Half-Edge/Winged-Edge structure is appropriate.

The internal representation can evolve later as long as the public semantic queries remain stable.

The current API already creates that boundary:

```text
face_vertices()
face_edges()
edge_faces()
edge_vertices()
vertex_edges()
```

This is a good example of future-proofing without overengineering.

### Do not do now

Do not introduce:

- a full Half-Edge system;
- ECS/slotmap/arena infrastructure;
- generalized topology frameworks;
- non-manifold topology machinery;
- genus tracking.

Those may become appropriate when real V1/V2 modeling requirements justify them.

---

# 6. Position access and future deformation

## Verdict: 🟡 DOCUMENT / CLARIFY

The use of a position accessor instead of exposing raw vertex storage is exactly the right architectural boundary.

The long-term conceptual chain is approximately:

```text
Base / authored geometry
        ↓
Morph / other deformation
        ↓
Skin / rig deformation
        ↓
Subdivision / derived surface
        ↓
Evaluated / displayed geometry
```

V1 does not implement this chain. It only needs to avoid making direct storage access the public contract.

### Important clarification

Before deformation is actually implemented, the distinction between **base/authored position** and **evaluated/display position** should become explicit.

V1 does not need a complete deformation stack to accomplish this.

The rule is simply:

> Do not let client code become dependent on the internal raw position storage.

---

# 7. Operation lifecycle

## Verdict: 🟢 KEEP

The generic lifecycle

```text
begin → update → commit
              ↘ cancel
```

is one of the strongest parts of the foundation.

It is not inherently a Mesh concept. The same interaction pattern can later be useful for:

- modeling operations;
- bone posing;
- animation/keyframe manipulation;
- other interactive editors.

Using a generic target/context rather than permanently defining the base abstraction around `Mesh` is therefore the correct decision.

### Small contract clarification

The semantics of `update()` should eventually state whether an update receives:

- an incremental delta since the previous update, or
- an absolute state relative to `begin()`.

Either can work. The important thing is that the contract is unambiguous.

No architectural rewrite is required for this.

---

# 8. Move operation

## Verdict: 🟢 KEEP + 🟡 TEST

`MoveOperation` successfully exercises the lifecycle rather than merely declaring it.

The important behavior is:

- `begin()` captures the starting state;
- repeated `update()` calls provide live viewport feedback;
- updates do not create History entries;
- `commit()` creates one logical History action;
- `cancel()` restores the initial state.

This is exactly the interaction model needed for an editor rather than a collection of immediate-mode mesh functions.

### One thing to verify

The meaning of the movement passed to `update()` should be covered by a test so future tools do not accidentally mix absolute and incremental semantics.

This is a contract/test issue, not a reason to redesign the operation system.

---

# 9. History

## Verdict: 🟢 KEEP

History is correctly modeled as a generic reversible command stack rather than as a Mesh-specific diff system.

Conceptually:

```text
Operation
    ↓ commit
Command
    ↓
History
```

The History layer does not need to know whether a command came from:

- modeling;
- rigging;
- animation;
- materials;
- a future script/AI action.

This is exactly the right level of abstraction for V1.

### Do not do now

Do not add:

- branching history trees;
- cross-subsystem transaction graphs;
- collaborative conflict resolution;
- generalized persistence of history.

Those are future concerns.

---

# 10. Selection

## Verdict: 🟢 KEEP

Selection is correctly treated as domain/editor state rather than as part of Mesh mutation history.

The V/E/F selection model is sufficient for V1.

The important architectural property is that the concept is not permanently defined as "MeshSelection" in a way that would prevent future domains such as:

- Bone selection;
- Keyframe selection;
- Morph-channel selection.

No generalized multi-domain Selection Registry should be built now.

---

# 11. Topology mutations: highest-priority technical review area

## Verdict: 🟡 VERIFY CAREFULLY

The mutation layer is the area where future compatibility matters most.

`split_edge()` has a clear continuity contract and is relatively straightforward.

`collapse_edge()` is more complex because it can affect:

- Vertex identity;
- Edge identity;
- Face boundaries;
- neighboring topology;
- potentially degenerate Faces that disappear.

The current implementation documents these consequences, which is good. However, these operations should be tested against their stated contracts before more systems depend on them.

### Required tests

For each topology mutation, tests should verify not only the resulting shape but also the promised identity relationships.

For example:

```text
split_edge:
    old endpoints survive
    old edge dies
    midpoint is new
    face identity survives
```

and for collapse:

```text
survivor ID remains valid
removed vertex ID becomes invalid
affected face IDs follow the documented rules
no stale edge lookup remains
```

This is the most important part of the current Core V1 review.

### Still explicitly NOT required

No Morph/Weight remapping system should be implemented as part of this review.

We only ensure that future remapping is not architecturally precluded.

---

# 12. Scene as the system root

## Verdict: 🟢 KEEP + 🟡 WATCH

The Scene wrapper is an important architectural signal.

V1 should be able to say:

```text
Scene
 ├── modeling / geometry
 ├── selection / editor state
 ├── history
 └── future subsystem slots
```

rather than treating a Mesh file as the entire product model.

The current reserved places for Morph/Rig/Animation are therefore useful.

### Important future boundary

We should avoid allowing the architecture to silently evolve into:

> `Scene = exactly one Mesh`

The final system may eventually need multiple objects, geometry data, rigs, animation data, materials, etc.

However, **do not build a generalized multi-object Scene graph merely to anticipate this.**

The current Scene is sufficient until an actual modeling requirement demands more.

---

# 13. Serialization

## Verdict: 🟢 KEEP

The Scene-envelope format is the right V1 decision:

```json
{
  "version": 1,
  "mesh": { ... },
  "morph_targets": null,
  "rig": null,
  "animation": null
}
```

This establishes the concept that the persistent unit is a Scene, not a raw Mesh.

Selection and History remaining transient is also appropriate for V1.

### Do not do now

No:

- migration framework;
- plugin serialization framework;
- universal schema registry;
- speculative fields for every imaginable future subsystem.

The current reserved blocks are enough.

---

# 14. Core API / interaction boundary

## Verdict: 🟢 KEEP, but do not over-expand yet

A defined API boundary for UI/scripts/AI is consistent with the larger project vision.

However, the boundary should remain **minimal and capability-oriented**.

The goal is not to build an elaborate AI framework or plugin API in V1.

The principle is simply:

```text
UI / future Scripts / future AI
            ↓
       Core boundary
            ↓
       Domain systems
```

This gives future agents and tools a stable place to interact with the application without making them depend on internal implementation details.

### Important distinction

The existence of a Core API is architectural preparation.

A complete scripting system or AI integration is not V1 work.

---

# 15. What the Core V1 should NOT become

This review explicitly rejects turning the current foundation into a giant "future-proof" framework.

Do not add merely because they might someday be useful:

- ECS;
- plugin architecture;
- generalized reflection;
- dependency injection framework;
- complete event bus;
- generalized attribute layers;
- full deformation graph;
- rigging system;
- animation system;
- material system;
- AI framework;
- scripting runtime;
- multi-user collaboration;
- universal asset format;
- complex transaction/history graph.

If a real V1 requirement later exposes the need for one of these, we can introduce it based on an actual use case.

---

# 16. Review result by category

| Area | Result | Decision |
|---|---|---|
| Stable IDs | 🟢 | Keep |
| ID continuity contracts | 🟡 | Keep + enforce/document |
| Basic topology representation | 🟢 | Keep |
| Topology mutations | 🟡 | Verify carefully with tests |
| Position indirection | 🟡 | Keep; clarify base/evaluated semantics later |
| Operation lifecycle | 🟢 | Keep |
| Move operation | 🟢 | Keep; clarify update semantics |
| History | 🟢 | Keep |
| Selection | 🟢 | Keep |
| Scene wrapper | 🟢 | Keep; don't hard-lock to one mesh |
| Serialization | 🟢 | Keep |
| Core/API boundary | 🟢 | Keep minimal |
| Deformation/Rig/Morph | 🔵 | Future |
| Animation | 🔵 | Future |
| Scripting | 🔵 | Future |
| AI integration | 🔵 | Future |
| Half-Edge | 🔵 | Future implementation option |
| ECS/Slotmap/etc. | 🔵 | Future only if justified |

---

# 17. Final conclusion

The current Core V1 should **not** be judged by whether it already resembles the final Mirai-like system.

It should be judged by whether it gives us a small, understandable modeling foundation while avoiding architectural decisions that would make the larger system impossible or unnecessarily expensive to build later.

By that standard, the current implementation passes the review directionally.

The main technical area requiring extra care is **topology mutation + ID continuity**. The main semantic area requiring future clarification is **base vs. evaluated position**. Neither currently justifies a rewrite.

The project should continue with the V1 Modeler implementation while preserving the documented boundaries.

## Guiding rule for future reviews

> **Do not implement the future prematurely. Do prevent the present from accidentally forbidding it.**

And equally important:

> **A future possibility is not automatically a V1 requirement.**

This document is therefore a checkpoint, not a roadmap for implementing every future subsystem.
