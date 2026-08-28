# Connect Edges — Behavior Specification

Status: **Experiment / design contract**  
Purpose: define the intended semantics before replacing the current experimental implementation.

## 1. Purpose

`Connect Edges` is a topology operation that creates new edges between the **midpoints of selected edges**. The operation is inspired by established polygon-modeling workflows, but the behavior below is the Mirai-Bastel design target rather than a claim that another application must behave identically.

The operation must be topology-aware. Selection order or numeric element IDs must never be used as a substitute for topological/geometric relationships.

## 2. Core semantics

Given a valid selection of edges:

1. Determine the topological groups and valid connections represented by the selection.
2. Split the participating source edges as required, creating midpoint vertices.
3. Create the required connecting edges between compatible midpoint vertices.
4. Preserve a valid mesh topology throughout the committed result.
5. The operation is atomic: if validation or construction fails, the mesh remains unchanged.

`Connect Edges` is not the same operation as `Edge Loop`, `Edge Ring`, `Loop Insert`, or `Bridge`. Those operations may use one another internally, but each has its own user-facing semantics.

## 3. Selection cases

### Two compatible edges

Expected result: the two edges are split and their midpoint vertices are connected by one new edge, provided the connection is valid in the surrounding topology.

### Three or more compatible edges

Expected result: all valid connections implied by the topology are created. The implementation must not simply sort edge IDs and connect consecutive entries.

### Edge ring

A ring selected through the Ring tool should be usable as input to Connect Edges. On suitable quad topology this can produce the new cross-cutting edge structure associated with a loop insertion workflow.

The ring must be interpreted through topology, not through the order in which selection IDs happen to be stored.

### Edge loop

A loop selection is valid input only where the selected edges form compatible connect groups. Connect Edges must not silently reinterpret an arbitrary loop selection as a ring or bridge operation.

### Multiple disconnected groups

Disconnected compatible groups should be handled independently where their individual connections are valid. One group must not be connected to another merely because their IDs are adjacent or because they occur next to each other in a collection.

### Invalid / incompatible selection

If no valid connection can be constructed, the operation must fail without modifying the mesh.

Partial success followed by an error is not an acceptable committed result.

## 4. Determinism

The result must be deterministic for the same mesh topology and selection, regardless of:

- selection insertion order;
- Python set iteration order;
- numeric edge-ID ordering;
- viewport selection history.

Topological relationships must be the source of ordering/grouping decisions.

## 5. Atomicity

The current experimental implementation performs splits before all connections have been proven possible. This can leave a partially modified mesh when a later connection fails.

The target behavior is:

```text
selection
  ↓
validate / analyze
  ↓
construct operation plan
  ↓
apply plan
  ↓
commit to history
```

If validation/planning fails:

```text
selection
  ↓
error
  ↓
mesh unchanged
```

## 6. Relationship to other operations

```text
Edge Loop
    = traverse an existing edge-flow

Edge Ring
    = traverse the corresponding cross-flow

Connect Edges
    = create connections between selected edge midpoints

Loop Insert
    = higher-level modeling operation that may use ring detection and
      edge connection, but has its own explicit semantics

Loop Remove / Dissolve
    = remove an existing loop while preserving the intended surrounding
      topology
```

This separation is intentional. `Connect Edges` should remain a reusable topology primitive rather than becoming a universal modeling command.

## 7. Current implementation gap

The current experimental `connect_selected_edges()` implementation effectively does:

```text
selected edges
    ↓
split every edge
    ↓
collect midpoint vertices
    ↓
sort by edge ID
    ↓
connect consecutive midpoints while possible
```

This is useful as a prototype, but it does **not** satisfy this specification because:

- numeric ID order is not topology order;
- multi-edge selections can stop after the first valid connection;
- already-applied splits can remain after a later failure;
- disconnected or differently structured selections are not represented as explicit groups.

The existing behavior is therefore a known experiment, not the final contract.

## 8. Tests required before implementation is considered complete

At minimum:

- two compatible edges;
- three compatible edges;
- multiple edges across a quad grid;
- complete edge ring;
- edge loop;
- multiple disconnected groups;
- invalid/incompatible selection;
- deterministic result with different selection insertion orders;
- failure leaves mesh unchanged.

The viewport should then provide an integration test for the same scenarios using the actual selection and hotkey path.

## 9. Reference basis

The initial semantic reference is **Wings 3D's Edge Connect** concept: connecting the midpoints of selected edges. Other systems are consulted before finalizing details, especially where their topology handling, attribute propagation, deformation data, or integrated workflow differs.

See `references/` for curated external references and the corresponding material under `docs/research/` for detailed investigations.

## 10. Open design questions

The following remain deliberately open until the implementation analysis and reference comparison are complete:

- exact grouping rules for arbitrary multi-edge selections;
- whether every valid group may generate more than one connection;
- handling of boundary edges and non-quad faces;
- behavior on mixed face valences;
- interaction with existing internal/non-manifold topology;
- attribute propagation once UVs, weights, morphs and other data exist in the Core.

These questions should be resolved by tests and explicit design decisions rather than accidental behavior of the current prototype.
