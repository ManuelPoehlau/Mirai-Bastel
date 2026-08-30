# Design: Rigging, Skinning & Morph-Targets Experiment

## Design Status

**Phase 1 research is complete.** The earlier Option A/B/C comparison remains useful as architectural research, but the experiment implementation is deliberately narrower:

> **Phase 2 uses an external RigController and does not modify `src/core/`.**

This is a research/prototype decision, not the final production rigging architecture.

---

## Problem

Mirai-Bastel aims to support a workflow in which a low-poly mesh can be rigged, skinned, morphed, and then remain topologically editable.

The experiment therefore asks:

> **What representation and dependency information are required for deformation data to remain correct when topology changes?**

The important dependency is:

```text
Topology mutation
       ↓
Mesh structure changes
       ↓
External deformation data may become stale
       ↓
Can the dependency be reconstructed from existing public APIs?
```

---

## Previously Investigated Options

### Option A — Skinning Inside Core.Mesh

Weights and morph targets become first-class Mesh data and topology operations update them directly.

**Pros**
- Unified state
- Potentially straightforward snapshot/serialization integration
- Topology operations can explicitly define deformation behavior

**Cons**
- Strong coupling between topology and deformation
- Larger production Core surface
- Higher regression and testing burden
- Requires deformation semantics for every relevant topology operation

**Current status:** Research option only. Not implemented.

### Option B — Completely External System

Core remains untouched. An external controller owns bones, weights, and morph targets and synchronizes against the mesh after edits.

**Pros**
- Zero Core risk
- Fast experimentation
- Clear separation of topology and deformation

**Cons**
- Synchronization must be solved explicitly
- Undo/redo coordination needs investigation
- External data can become stale if topology provenance is insufficient

**Current status:** This is the **starting architecture for the experiment**.

### Option C — Hybrid / Core-Aware System

The original proposal added lightweight Core facilities such as Core-owned bones and topology listeners while keeping weights external.

**Pros**
- Could support automatic synchronization
- Could provide explicit topology/deformation integration points

**Cons**
- Requires production-Core changes before the need has been proven
- Introduces architecture and maintenance cost
- Risks violating the current Core-freeze experiment strategy

**Current status:** Hypothesis for possible future investigation only. No Core observer/listener implementation is authorized by this experiment.

---

## Current Experiment Architecture

```text
┌──────────────────────────────┐
│          Core.Mesh           │
│                              │
│ vertices / edges / faces     │
│ topology operations          │
│ public query APIs            │
└──────────────┬───────────────┘
               │ read-only
               ▼
┌──────────────────────────────┐
│       RigController           │
│       experiments/ only       │
│                              │
│ bones                        │
│ skinning weights             │
│ morph targets                │
│ deformation                  │
│ explicit synchronization    │
└──────────────────────────────┘
```

The external controller may own its own bone hierarchy. It does not require `Mesh.bones` or any other new Core field.

Suggested prototype data:

```python
skinning_weights = {
    vertex_id: [(bone_id, weight), ...]
}

morph_targets = {
    "mouth_open": {
        vertex_id: (dx, dy, dz),
    }
}
```

The structures are intentionally provisional.

---

## Topology Synchronization

Synchronization is explicit and experiment-owned.

Example workflow:

```text
1. RigController stores state for Mesh
2. User performs topology operation through existing Core API
3. Mesh changes
4. RigController receives/gets the updated Mesh explicitly
5. RigController recalculates or transfers dependent data
6. Tests verify the result
```

Do not add callbacks to Core simply to automate step 4.

The experiment must first establish whether existing APIs provide enough information.

### Split / Loop Insert

Investigate:
- new vertex identity;
- relation to original vertices/edges;
- available topology queries;
- viable weight interpolation/inheritance;
- viable morph interpolation.

### Collapse

Investigate:
- deleted vertex identity;
- surviving vertex identity;
- weight merge semantics;
- morph merge semantics;
- cleanup of external entries.

### Connect Edges

Connect Edges may not create/delete vertices. Verify whether the resulting topology nevertheless requires any external deformation update.

### General Rule

Do not assume that a topological operation's implementation detail is sufficient provenance for a dependent system. Test what the public API actually exposes.

---

## Weight and Morph Semantics

The experiment must not prematurely lock in a universal production rule such as "always copy the parent weight".

Instead test candidate strategies where relevant:

- copy/inherit;
- interpolate between source vertices;
- merge/normalize on collapse;
- explicit user repair when automatic reconstruction is ambiguous.

Record which strategy is appropriate for which operation.

Likewise, morph offsets must be treated as deformation data whose interpolation semantics may differ from skinning weights.

---

## Undo / Redo

The production project uses state snapshots for history. This experiment must investigate how an external RigController interacts with mesh snapshots without changing production history.

Prototype questions:

- Can RigController state be snapshotted independently?
- Can it be restored alongside a restored Mesh state?
- Can stale vertex references be detected?
- Is topology provenance required for deterministic restoration?

Any requirement discovered here is a finding for future architecture work.

---

## Phase 2 — RigController Prototype

Scope:

- experiment code only;
- external bone hierarchy;
- skinning weight storage/editing;
- morph target storage/editing;
- deformation calculation;
- explicit post-topology synchronization;
- focused tests.

Out of scope:

- `src/core/` changes;
- Core observers/listeners;
- production serialization changes;
- production history changes;
- final production rigging API.

---

## Phase 3 — Viewport Integration

Experimentally:

- render bones;
- render deformed geometry;
- provide simple bone controls;
- provide simple morph controls;
- execute topology edits while rigging/morphing is active;
- visualize synchronization failures clearly.

Reuse the existing experimental viewport where practical.

---

## Phase 4 — Validation

Use a simple 50–100 vertex head:

1. Build neck/skull/jaw hierarchy.
2. Assign weights.
3. Create 2–3 morph targets.
4. Deform with bones.
5. Apply loop insertion/split.
6. Apply collapse where practical.
7. Apply Connect Edges.
8. Synchronize externally.
9. Verify weights and morphs.
10. Verify deformation.
11. Record missing-information cases.

The strongest result is not "the demo works" but a clear dependency model explaining why it works or what is missing.

---

## Production Transition Gate

No code moves from this experiment into production automatically.

A later production proposal must answer:

1. What did the experiment prove?
2. Which data must persist with a mesh?
3. Which topology provenance is required?
4. Can the information be supplied by existing Core APIs?
5. If not, what is the smallest Core extension?
6. How would undo/redo and serialization work?
7. What are the performance implications?

Only then should a separate Architecture Decision authorize production changes.

---

## Design Principle

> **Do not build Core infrastructure for a dependency that has not yet been demonstrated.**

The experiment exists to discover that dependency first.

---

**Document Status:** Phase 1 complete; Phase 2 ready  
**Current Strategy:** External RigController / Core frozen  
**Risk to production Core:** None by design  
**Author:** Claude / Manu
