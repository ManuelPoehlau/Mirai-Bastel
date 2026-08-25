# Claude Architecture Review 003 — Detailanalyse

**Status:** Archived review. No repository changes were requested by Claude.

## AD-001 — Stable Element IDs

Claude recommends defining IDs as opaque handles rather than raw array positions. `VertexId`, `EdgeId`, and `FaceId` share the conceptual shape `(slot_index, generation)`, but Claude explicitly corrects the previous recommendation: a full generational Slotmap is unnecessarily complex for Python V1.

For V1, the proposed minimal robust solution is a monotonically increasing ID with no index recycling, backed by a Python `dict`. IDs are never reused; validity is checked by membership. A future Slotmap can be introduced only if profiling justifies it.

Important consequences:
- IDs remain stable for existing elements.
- Deleted IDs never silently alias newly created elements.
- `_next_id` must be persisted during serialization.
- `is_valid(id)` should be part of the public scripting/AI-facing API.

**Must decide now:** opaque, never-reused, validity-checkable IDs.
**Must implement now:** yes, but trivially.
**Explicitly not V1:** generational Slotmap recycling, arena allocator, ECS, NumPy struct arrays.

## AD-002 — Topology / Half-Edge / Loop

Claude corrects the earlier recommendation here as well: a real `HalfEdge` class is not required for V1.

What should be fixed now is:
1. Face boundaries are ordered.
2. Code outside the mesh does not access topology containers directly.
3. Adjacency is exposed through stable query functions.

Suggested V1 queries:

```text
mesh.face_vertices(face_id)  -> list[VertexId]
mesh.face_edges(face_id)     -> list[EdgeId]
mesh.edge_faces(edge_id)     -> list[FaceId]
mesh.vertex_edges(vertex_id) -> list[EdgeId]
```

The initial implementation can use ordered vertex lists and simple scans. A future internal Half-Edge implementation can replace those scans without changing callers, provided the query API remains stable.

Half-Edge becomes more valuable for loop/ring selection, bevel, and performance-critical subdivision on larger meshes.

**Must decide now:** ordered boundaries + stable adjacency-query API.
**Must implement now:** no full Half-Edge structure.
**Explicitly not V1:** full Winged-/Half-Edge topology, twin-pointer/radial structures, pre-optimized adjacency caches, non-manifold multi-shell support.

## AD-003 — Interactive Operation Lifecycle

Claude proposes a four-phase contract:

```text
begin()
update()
commit()
cancel()
```

For a Move/Tweak interaction:

1. Selection happens independently and is not part of the main history.
2. `begin()` captures starting positions, computes Soft Selection influence once, and establishes transform context.
3. Repeated `update()` calls directly modify live geometry. No history entry is created.
4. `commit()` creates exactly one history entry and emits the final domain change event.
5. `cancel()` restores the initial snapshot, emits only the necessary redraw/restoration event, and creates no history entry.

`apply()` can conceptually become a convenience wrapper around `begin → update → commit`.

For V1, Claude recommends direct live mesh modification during `update()` rather than a separate preview mesh.

Tweak uses the same lifecycle plus the influence map. Interactive Extrude can create its topology during `begin()` and then move the newly created vertices during `update()`; this raises an important question for our own review: cancellation of a topology-changing operation must restore both geometry and topology safely.

**Must decide now:** lifecycle contract.
**Must implement now:** minimally for Move.
**Explicitly not V1:** asynchronous operation pipelines, OT/CRDT, collaborative state, branching history trees, complex batching heuristics.

## Claude's Summary

| Decision | Contract now | Full implementation now | Main risk if delayed |
|---|---|---|---|
| AD-001 IDs | Yes | Yes, trivial Counter + Dict | Cross-system retrofit |
| AD-002 Topology | Yes: ordered boundary + query API | No full Half-Edge | Wrong domain model |
| AD-003 Lifecycle | Yes | Partially: Move first | Widespread interface break |

## Review note

Claude explicitly corrected two earlier overstatements:
- Generational Slotmap is not necessary for Python V1; the important contract is stable, opaque, never-reused IDs.
- Half-Edge should not be treated as a required V1 primitive; the important contracts are ordered face boundaries and an abstraction boundary around adjacency queries.

These corrections are important and should be considered part of the architectural evidence, not merely implementation detail.
