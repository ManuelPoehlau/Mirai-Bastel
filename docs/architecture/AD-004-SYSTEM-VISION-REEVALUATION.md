# AD-004 — Architecture Re-Evaluation in Light of the Long-Term System Vision

**Status:** Accepted architectural guidance  
**Scope:** V1 Core architecture  
**Origin:** External architecture review / team discussion  

## Context

The project must not be treated as "a modeller with some future extension points".

V1 is the first concrete implementation milestone of a larger, persistent 3D authoring system inspired by the workflow philosophy associated with Mirai/Nendo and later production systems.

The long-term system may eventually contain multiple cooperating subsystems:

- Geometry / Topology
- Selection
- Transform / Interaction
- History
- Deformation
- Morph Targets
- Rig / Skeleton
- Animation
- Materials
- Camera / View
- Extensions / Scripts
- AI-facing APIs

The architectural principle is:

> **Implement little. Assume much.**

V1 must remain small, but known future requirements must not be accidentally made expensive by today's contracts.

## Critical long-term consideration: topology changes

A modelling → rigging → deformation → back-to-modelling workflow has a difficult fundamental problem: skin weights and morph deltas can depend on vertex identity while modelling operations may change topology.

Stable IDs alone do **not** solve this problem. They provide the necessary identity continuity on which future remapping strategies can be built.

Therefore V1 should establish identity and mutation-continuity contracts without prematurely implementing a rig/morph remapping framework.

---

## AD-004.1 — Stable Element IDs

### Decision

V1 uses opaque, never-reused element IDs backed by a simple counter + dictionary implementation.

A full generational slotmap is **not** required for Python V1.

The important contract is:

- IDs are opaque handles, not array indices.
- IDs are never reused during a session.
- Validity can be queried.
- `_next_id` is persisted by serialization.
- Mutation operations document which IDs survive, which become invalid, and which are newly created.

### ID continuity contract

For every topology mutation, the operation should explicitly document identity continuity.

Example:

```text
split_edge(edge_id)

existing endpoint VertexIds  → preserved
original EdgeId              → invalid
new midpoint VertexId        → new
new EdgeIds                  → new
```

This is deliberately **not** a generic automatic remapping system.

### Explicitly deferred

- generational slotmap recycling
- arena allocators
- ECS architecture
- automatic per-vertex attribute migration
- automatic skin/morph remapping

---

## AD-004.2 — Topology Representation

### Decision

V1 uses ordered face boundaries plus a stable topology query API.

A full Half-Edge implementation is explicitly **not** required yet.

Clients must not depend on internal containers directly.

The conceptual API is:

```text
face_vertices(face_id)  -> ordered list[VertexId]
face_edges(face_id)     -> ordered list[EdgeId]
edge_faces(edge_id)     -> list[FaceId]
vertex_edges(vertex_id) -> list[EdgeId]
```

The internal implementation may initially use scans. A later Half-Edge implementation should be able to replace those internals without requiring operations, interaction code or scripting APIs to change.

### Important additional boundary

Vertex position must not become a public raw-storage dependency.

Use an accessor such as:

```text
vertex_position(vertex_id)
```

and a controlled mutation path, even though V1 simply returns/stores the base position.

This leaves room for a future distinction between:

```text
base position
    ↓
morph contribution
    ↓
skin/deformation
    ↓
displayed position
```

No deformation stack is implemented in V1.

### Explicitly deferred

- full Half-Edge / Twin structures
- radial cycles
- advanced non-manifold support
- pre-optimized adjacency caches
- generic deformation pipelines

---

## AD-004.3 — Interactive Operation Lifecycle

### Decision

Operations use a generic four-phase lifecycle:

```text
begin(context)
update(...)
commit()
cancel()
```

The operation contract must **not be Mesh-specific**.

The operation receives a broader `OperationContext` containing the relevant scene/domain state rather than hard-coding `mesh: Mesh` into the base interface.

V1 implements this minimally, initially with Move.

### Why

The same interaction pattern is expected to be useful later for:

- mesh transforms
- Tweak
- bone posing
- animation/keyframe manipulation
- other interactive tools

The lifecycle is therefore a Core interaction contract, not merely a modelling feature.

### Explicitly deferred

- asynchronous operation pipelines
- collaborative operation merging
- OT/CRDT
- branching operation graphs
- predictive pipelines

---

## AD-004.4 — History

### Decision

History must be designed around a minimal generic reversible-command contract rather than a `MeshOperation`-specific stack.

Conceptually:

```text
Command
├── undo()
└── redo()
```

A V1 command may represent a mesh operation, while future commands may represent rig, animation or other subsystem changes.

### Important boundary

The history container should not need to know which subsystem produced a command.

### Explicitly deferred

- unified cross-subsystem transaction merging
- branching history trees
- collaborative conflict resolution

---

## AD-004.5 — Selection

### Decision

V1 implements Vertex/Edge/Face selection, but Selection remains conceptually a set of stable IDs belonging to a domain.

The public design should avoid unnecessarily baking "Mesh" into the conceptual Selection contract.

This allows future domains such as:

- bones
- keyframes
- morph channels

without requiring a completely unrelated selection philosophy.

### Explicitly deferred

- generic selection registries
- automatic domain discovery
- universal multi-domain selection systems

---

## AD-004.6 — Deformation / Rig / Morph / Animation

### Decision

These systems are **future scope (C)** for V1.

No implementation or premature framework is required now.

The only V1 architectural consequences are the boundaries already established above:

- stable element identity
- topology mutation continuity
- position access indirection
- generic operation lifecycle
- generic history commands
- scene-level serialization structure

---

## AD-004.7 — Serialization

### Decision

V1 serialization should be scene-oriented rather than treating the mesh as the permanent root of the file format.

Conceptually:

```json
{
  "version": 1,
  "mesh": { },
  "morph_targets": null,
  "rig": null,
  "animation": null
}
```

The exact schema remains intentionally simple.

The important architectural point is that the file represents a **Scene**, with the mesh as one subsystem, even if V1 only populates that subsystem.

### Explicitly deferred

- migration framework
- plugin serialization framework
- generalized asset schema machinery

---

# V1 — The Seven "Do Not Accidentally Assume" Rules

These are the practical architectural guardrails derived from this review:

1. **No direct position storage dependency.** Access geometry through controlled functions so a future deformation layer can be inserted without rewriting clients.
2. **Document ID continuity for every topology mutation.** Do not implement remapping yet; preserve the information needed for future remapping.
3. **History uses a generic reversible-command boundary.** Do not make the history container mesh-specific.
4. **Operations use a generic context.** `begin/update/commit/cancel` must not be typed specifically around Mesh.
5. **Selection remains domain-oriented, not hard-wired conceptually to Mesh.** V1 still only implements V/E/F selection.
6. **Serialization is Scene-oriented.** The mesh is the first populated subsystem, not the permanent root abstraction.
7. **Scene/Core has structural room for future subsystems.** Do not implement them now, but do not architect the scene as if Mesh were the only thing that will ever exist.

## The balance

Every future-facing decision should be evaluated with two questions:

> **Is this the smallest thing we need today?**

and:

> **Does this accidentally make something we already know we want tomorrow unnecessarily expensive?**

If the first answer is no, simplify.

If the second answer is yes, change the boundary before production code depends on it.

This is the concrete application of the project rule:

> **Implement little. Assume much.**

## Conclusion

The review does **not** expand V1 into a rigging, animation, deformation or AI project.

Instead, it identifies a small number of contracts that should be established before the first production implementation so that the Core can grow naturally into the larger system we actually want.

V1 remains intentionally small.

The architecture remains intentionally alive.
