# Connect Edges — Behavior Specification

Status: **Experiment / design contract — implementiert (Scope: reguläre Quad-Topologie)** — practical limits of this scope: see §11  
Purpose: define the intended semantics; the experimental implementation in `experiments/mirai_bastel_viewport_V1/viewport/topology_tools.py` now follows this contract (Analyze → Plan → Apply/Commit, atomic and deterministic). Section 7 documents the superseded pre-implementation state.

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

## 7. Current implementation gap (superseded)

> Status note: this section described the state **before** the topology-aware
> implementation. `connect_selected_edges()` now follows sections 2–5: it
> separates Analyze/Validate, Plan (validated by a dry-run on a clone before
> any mutation) and Apply/Commit (exactly one history snapshot), groups by
> topology only, and is fully atomic. Scope is currently regular compatible
> quad topology; boundary/non-quad/mixed-valence/non-manifold constellations
> are rejected explicitly and remain open (see section 10). The text below is
> kept as project memory of the superseded prototype.

The previous experimental `connect_selected_edges()` implementation effectively did:

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

> 2026-09-21: The non-quad / mixed-valence questions above are being investigated in
> [`CONNECT_NONQUAD_DISCOVERY.md`](CONNECT_NONQUAD_DISCOVERY.md) (Discovery, no decision yet).

## 11. Characterization findings (2026-09-21)

Status: **evidence, not a decision.** Behavior pinned by
`playground/tests/test_topology_connect_edges_characterization.py` (F1–F10).
Code state: `main` @ `01ea6f9`.

Trigger: artist observation that the current Connect tool does not allow reasonable topology work.

| # | Finding |
|---|---|
| F1 | A partial connect that ends inside the mesh leaves 2 pentagons (mathematically unavoidable: a quad strip cannot terminate in the interior of a mesh). |
| F2 | Connect rejects every edge adjacent to a non-quad face — the pentagons from F1 therefore block any follow-up connect at that spot. In practice only "full loop or nothing" remains. |
| F3 | Corner connect (two adjacent edges of one face) is rejected. |
| F4 | A selection path that turns is rejected. |
| F5 | Two edges with one quad in between are rejected (error, not a no-op). |
| F6 | Boundary-to-boundary and closed rings work and produce only quads. |
| F7 | "kind v" creates a free edge that lies geometrically on top of the existing edges (through the shared vertex) and splits no face; 4 pentagons result. See the discovery document, D6 — this bears on the justification of the `Mesh.add_edge()` Core exception (CORE_V1_FREEZE, AP-05). Documented as a problem only; no architecture change made. |
| F8 | All rejections are atomic: mesh and history unchanged. |
| F9 | The Core primitives (`split_edge`, `connect_vertices`) already perform a corner cut and resolve a pentagon. The limits above live in the playground tool layer, not in `src/core`. |
| F10 | Selecting all four edges of one quad: the planned "+" cross fails with an internal message ("Operationsplan nicht auf gültige Topologie abbildbar: FaceId(…)"), because the second pair targets a face that no longer exists after the first split. |

Dependency note: `playground/topology_tools/loop_insert.py` calls `connect_selected_edges()`
directly. Any change to Connect semantics affects Loop Insert.

AD-017 note (2026-09-22): the `C` key no longer dispatches through `connect_selected_edges()`
(strip / baseline semantics). `C` now uses contextual dispatch (`contextual_c.py`): 2+ edges
→ `connect_per_face.py` (per-face / Wings semantics, Artist KEEP decision). Strip semantics are
no longer reachable from `C`. Loop Insert is unchanged and still calls `connect_selected_edges()`.

Reference note: the Wings 3D source (the reference named in §9) implements Edge Connect as
cut → per-face vertex connect → dissolve unconnected midpoints, independent of face size.
Details and a Core-only probe of that semantics: discovery document §2–§3.
