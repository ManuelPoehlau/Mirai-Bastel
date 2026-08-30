# AD-005: Rigging & Skinning Integration Architecture

**Status:** DECIDED — Experiment Architecture  
**Date:** August 2026  
**Owner:** Manu (Project Owner)  
**Scope:** Experiment: `rigging-skinning-morphing`  

---

## Problem Statement

How can Rigging, Skinning Weights, and Morph-Targets coexist with topological mesh editing without destroying deformation data, while keeping the production Core stable until the experiment has produced sufficient evidence for a separate architecture decision?

**Use Case:** Low-poly character head (neck, skull, jaw) rigged + skinned + morphed, followed by topology edits such as loop insertion, split, collapse, and Connect Edges.

The experiment must determine not only whether the prototype works, but **what information a dependent deformation system requires from the topology system to remain correct after mutation**.

---

## Decision

### Experiment Architecture: External RigController, No Core Changes

For the current experiment, choose the safe subset of the previously investigated hybrid direction:

- `Core.Mesh` remains unchanged.
- No Core-owned bones are added.
- No topology listeners or observer callbacks are added to the Core.
- `RigController` is entirely experimental code under `experiments/rigging-skinning-morphing/`.
- Rigging, skinning weights, and morph-target data are owned by the external `RigController`.
- The controller uses existing public Core APIs only.
- Synchronization after topology changes is performed explicitly by the experiment, not through Core callbacks.

This is a **prototype/research decision**, not a final production architecture decision.

### Why

The experiment must follow the established Mirai-Bastel experiment pattern:

```text
existing Core API
      ↓
experimental dependent system
      ↓
real topology mutations
      ↓
observe what information is available
      ↓
identify gaps
      ↓
separate architecture decision if Core changes are justified
```

Adding observers or other Core infrastructure before proving that it is required would turn an architectural hypothesis into an implementation prematurely.

---

## Previously Investigated Options

### Option A — Skinning Inside Core

Weights and morph targets become first-class `Mesh` data and topology operations update them directly.

**Advantages:** unified state and potentially simple long-term snapshot/serialization semantics.

**Risks:** strong coupling between topology and deformation, larger Core surface, higher regression and serialization burden.

### Option B — Completely External System

Mesh remains unchanged. An external controller owns bones, weights, and morphs and synchronizes explicitly after mesh edits.

**Advantages:** zero production-Core risk and rapid experimentation.

**Risks:** synchronization and undo/redo coordination must be solved externally.

### Option C — Hybrid Core-Aware Rigging

The earlier proposal combined external weights with minimal Core support such as Core-owned bones and topology listeners.

**Important revision:** Option C is **not being implemented as originally specified**. The experiment now starts with the Core-frozen subset described above. Whether any Core-aware mechanism is eventually justified is an experiment finding, not a preset implementation requirement.

---

## Experiment Architecture

```text
┌──────────────────────────────┐
│          Core.Mesh           │
│                              │
│ vertices / edges / faces     │
│ topology operations          │
│ existing public query APIs   │
└──────────────┬───────────────┘
               │ read-only use
               ▼
┌──────────────────────────────┐
│       RigController          │
│      experiments/ only       │
│                              │
│ bones                        │
│ skinning_weights             │
│ morph_targets                │
│ deformation                  │
│ explicit resynchronization   │
└──────────────────────────────┘
```

The controller may keep its own bone hierarchy. It must not require changes to `Mesh` merely to store or expose that hierarchy.

Suggested data model:

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

These structures are deliberately experimental and may be replaced after validation.

---

## Topology Synchronization Strategy

There is intentionally **no automatic Core callback** in the current phase.

After a topology operation, the experiment explicitly invokes synchronization/recalculation against the updated mesh.

The implementation must investigate what can be reconstructed from the existing Core APIs.

For each mutation, record:

### Vertex creation

Determine:
- which new vertex was created;
- which original topology elements relate to it;
- whether existing APIs provide enough provenance to choose or interpolate weights/morph data.

### Vertex deletion / collapse

Determine:
- which vertex disappeared;
- which vertex survives;
- how weights should be merged;
- how morph offsets should be merged or removed.

### Connect Edges

Connect Edges may not create vertices, but the experiment must verify whether any deformation data still requires synchronization.

### Loop insertion / other operations

Treat these as compositions of lower-level topology mutations only if the actual implementation proves that assumption valid.

---

## Research Rule

Do **not** invent Core hooks solely to make synchronization convenient.

If the existing API is insufficient, record a finding such as:

> "External deformation synchronization requires topology provenance X, which the current public Core API does not expose."

Then document:

- why the information is required;
- which operation needs it;
- whether an external workaround is viable;
- what the smallest possible Core extension might be.

Only after that may a future architecture decision consider a Core change.

---

## Phase 2 — RigController Prototype

**Scope:** experiment code only.

Implement:

1. Bone representation and hierarchy.
2. Skinning weight storage and editing.
3. Morph-target storage and editing.
4. Linear blend skinning/deformation prototype.
5. Explicit topology-resynchronization methods.
6. Focused unit tests.
7. Tests for topology mutation scenarios.

**Must not:**

- modify `src/core/`;
- add Core observers/listeners;
- modify Core topology operations;
- modify production serialization;
- alter the existing Core test suite to accommodate the experiment.

---

## Phase 3 — Viewport Integration

Experimentally:

- render the bone skeleton;
- render the deformed mesh;
- provide simple bone transform controls;
- expose morph weights/controls as needed for validation;
- perform topology edits while rigging/morphing is active.

The existing viewport should be reused where practical rather than creating a second unrelated rendering architecture.

---

## Phase 4 — Validation

Use a low-poly head of approximately 50–100 vertices:

1. Create neck/skull/jaw hierarchy.
2. Assign skinning weights.
3. Create 2–3 morph targets.
4. Deform the mesh.
5. Perform split/loop insertion.
6. Perform collapse where practical.
7. Test Connect Edges.
8. Recalculate/synchronize externally.
9. Verify weights and morphs.
10. Verify deformation still works.
11. Record every missing-information case.

The experiment succeeds only if it produces **evidence**, not merely a visually working demo.

---

## Undo / Redo Consideration

The production Core currently uses state snapshots for topology/history behavior. The experiment must explicitly investigate how external rig state interacts with those snapshots.

Do not extend production history yet.

Instead test/document whether the RigController can:

- snapshot and restore its own state;
- stay aligned with a restored Mesh snapshot;
- detect stale references/data after undo/redo.

Any production integration requirement becomes a later architecture finding.

---

## Transition Criteria

After validation, one of the following outcomes is expected.

### Outcome A — External model is sufficient

Existing Core APIs provide enough information. Rigging can remain external, with integration handled by a higher-level system.

### Outcome B — Small Core API extension is justified

A concrete missing capability is demonstrated. A separate Architecture Decision defines the smallest Core addition and its contracts.

### Outcome C — Current topology API is insufficient for robust deformation preservation

The experiment identifies a deeper requirement that must be solved before production rigging integration.

**No outcome automatically authorizes changes to `src/core/`.**

---

## Relationship to Other Work

### Modeler / Interaction Work

The experiment is independent. It may reveal requirements for future topology-tool contracts, transform systems, or operation provenance, but must not modify those systems opportunistically.

### Topology Experiment

The rigging experiment consumes the existing topology behavior as a black box through public APIs and uses it as the source of mutation cases.

### Future Animation System

Bone transforms, constraints, animation, and evaluation are intentionally outside the current production scope. The experiment may identify future requirements.

---

## Success Criteria

The experiment is successful when:

1. A low-poly head can be rigged, skinned, and morphed in experiment code.
2. Topology mutations can be performed without crashing.
3. The experiment can demonstrate which deformation data survives, can be reconstructed, or is lost.
4. Weight/morph synchronization behavior is tested rather than assumed.
5. The viewport demonstrates deformation before and after topology edits where applicable.
6. Any missing Core capability is documented precisely.
7. No production Core change was required merely to run the experiment.

A successful experiment does **not** mean that the final production rigging architecture has been decided.

---

## Superseded Material

Earlier versions of this document proposed:

- `Mesh.bones`
- `Mesh.topology_listeners`
- `register_topology_listener()`
- automatic callbacks from split/collapse
- automatic weight inheritance through Core notifications

These are **superseded by the current Core-frozen experiment decision** and must not be implemented under the current Phase 2 scope.

---

## Approval

**Decision:** External RigController / Core-frozen experiment  
**Status:** APPROVED FOR EXPERIMENTATION  
**Approved by:** Manu (Project Owner)  
**Date:** August 2026
