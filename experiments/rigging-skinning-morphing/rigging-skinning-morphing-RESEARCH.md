# Research Findings: Rigging, Skinning & Morph-Targets

## Purpose

This document records research findings for the hypothesis that a rigged, skinned, morphed mesh should remain topologically editable.

The experiment is deliberately separated from the production Core. Findings may motivate future architecture decisions, but they do not authorize Core changes.

---

## 1. ID Management & Continuity

The project uses the documented rule that element IDs are not reused within a session.

This is favorable for external deformation mappings because a vertex ID remains associated with the same logical vertex identity for the lifetime of that session. When a vertex is deleted, however, external data can contain an orphaned entry and therefore needs explicit cleanup.

Research questions:

- How should orphaned skinning entries be detected?
- Can existing Mesh queries identify live vertex IDs reliably?
- How should morph entries for deleted vertices be cleaned up?

No Core modification is required to investigate these questions.

---

## 2. Topology Mutations

The topology system provides operations such as split, collapse, and Connect Edges. The rigging experiment treats these as existing Core behavior and does not modify their implementation.

### Split / Loop Insertion

A split creates a new vertex. The critical dependency question is:

> What information available through the public API lets an external controller determine how the new vertex relates to existing vertices?

Possible deformation strategies include copying or interpolating source weights and morph offsets. The experiment must measure which strategy is justified rather than assuming one globally.

### Collapse

A collapse removes one vertex while retaining another identity. The experiment must determine appropriate weight and morph merge semantics and clean up data for the deleted ID.

### Connect Edges

Connect Edges can change connectivity without creating or deleting vertices. The experiment must verify whether this leaves skinning/morph data unchanged, as expected, or exposes another dependency.

---

## 3. Undo / Redo and State

The production history model is based on state snapshots rather than semantic inverse operations.

For external rigging data this raises a research question: can RigController state be restored consistently when the Mesh is restored from a snapshot?

The experiment should therefore test:

```text
Mesh state N + Rig state N
        ↓
 topology edit
        ↓
Mesh state N+1 + Rig state N+1
        ↓
 restore Mesh state N
        ↓
Can RigController restore N deterministically?
```

This must be solved experimentally before proposing production integration.

---

## 4. Why the Core Must Remain Frozen

Earlier research proposed a hybrid architecture with Core-owned bones and topology listeners. That proposal was made before applying the project's established experiment discipline consistently.

The current rule is:

> **Do not extend `src/core/` merely because an experiment would be easier with a new hook.**

The topology experiment demonstrates the preferred pattern:

```text
Existing Core
     ↓
External experiment
     ↓
Real operation
     ↓
Observe available information
     ↓
Identify missing capability
     ↓
Architecture decision
```

Therefore the RigController prototype must use existing public Core APIs only.

If the experiment cannot synchronize reliably, that is valuable evidence for a future Core/API proposal.

---

## 5. Current Architecture Hypothesis

The safest hypothesis to test first is:

```text
Core.Mesh
   │
   │ existing public APIs
   ▼
RigController (experiment)
   ├── Bones
   ├── Skinning Weights
   ├── Morph Targets
   └── Deformation
```

No Core listener infrastructure is assumed.

The controller explicitly synchronizes after a topology operation and records what information was required.

---

## 6. Data Dependency Questions

For each mutation, record:

| Dependency | Question |
|---|---|
| Vertex creation | Can source/provenance be identified? |
| Vertex deletion | Can dead IDs be detected and removed? |
| Weight transfer | Copy, interpolation, merge, or user repair? |
| Morph transfer | Same strategy as weights, or different? |
| Bone hierarchy | Can it remain entirely external? |
| Deformation | Can deformed positions be computed without mutating Core data? |
| History | Can external state follow Mesh snapshots? |
| Serialization | What information must eventually persist together? |

These are research questions, not current production requirements.

---

## 7. Validation Targets

The low-poly head scenario should exercise:

1. 50–100 vertices.
2. Neck/skull/jaw bone hierarchy.
3. Skinning weights.
4. 2–3 morph targets.
5. Bone deformation.
6. Morph deformation.
7. Split/loop insertion.
8. Collapse where practical.
9. Connect Edges.
10. External synchronization.
11. Undo/redo interaction at experiment level.

Record both successful and unsuccessful cases.

A failure that precisely identifies missing topology provenance is a successful research result.

---

## 8. Open Questions

### Topology API

- Which public APIs expose enough provenance after split/collapse?
- Does a higher-level operation expose the information needed by dependent systems?
- Are loop insertion operations compositions of identifiable lower-level mutations?

### Deformation Semantics

- What is the correct weight transfer rule for split?
- What is the correct merge rule for collapse?
- How should morph offsets be interpolated?
- Are different topology operations required to use different policies?

### History

- Can external rig state follow Core snapshots deterministically?
- Does the external controller need its own snapshot layer?

### Production Architecture

- Is an external system sufficient long-term?
- If not, what is the smallest Core/API extension actually justified by evidence?
- Should any future dependency mechanism be generic rather than rigging-specific?

---

## 9. Superseded Research Assumptions

The following earlier assumptions are no longer active implementation guidance:

- `Mesh.bones` must be added now.
- `Mesh.topology_listeners` must be added now.
- Split/collapse must call rigging callbacks.
- New vertices should universally inherit a parent vertex's weights.
- Rigging data must immediately be integrated into production Mesh snapshots.

These may become conclusions later, but only after experimental evidence and a separate architecture decision.

---

## 10. Next Steps

### Phase 2 — RigController Prototype

Implement only in `experiments/rigging-skinning-morphing/`:

1. External bone hierarchy.
2. Skinning weight model.
3. Morph-target model.
4. Deformation calculation.
5. Explicit topology synchronization.
6. Unit tests.
7. Mutation-specific experiments.
8. Document findings.

### Phase 3 — Viewport

Add experimental visualization only after the controller model is sufficiently stable.

### Phase 4 — Validation

Run the low-poly head scenario and use the results to decide whether a future production architecture proposal is warranted.

---

**Document Status:** Phase 1 complete → Phase 2 ready  
**Core Policy:** `src/core/` frozen  
**Current Architecture Hypothesis:** External RigController  
**Last Updated:** August 2026
