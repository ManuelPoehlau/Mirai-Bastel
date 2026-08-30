# Rigging, Skinning & Morph-Targets Experiment

## Overview

This experiment investigates how skeletal rigging, skinning weights, and morph-targets can coexist cleanly with **topological mesh editing** — a capability historically rare outside specialized tools like the original Mirai.

**Core Question:** Can we edit the topology of a rigged, weighted, morphed mesh without destroying the rig, weights, or morph-target integrity?

**Use Case:** Low-poly character head workflow
- Neck, skull, jaw rigged with 3 bones
- Vertices weighted to bones (skinning)
- Facial deformations via morph-targets (mouth open, jaw drop, etc.)
- Then perform topology operations (split/collapse/connect, especially loop insertion)
- Verify: Do weights remain meaningful? Do morphs remain intact? Does the rig still function?

## Important Architectural Boundary

**`src/core/` is frozen for this experiment.**

Phase 2 and all subsequent prototype work must use the existing public Core APIs without modifying `src/core/`. The experiment is intentionally a playground for discovering requirements, not a reason to extend the production Core in advance.

If the experiment demonstrates that a Core capability is genuinely missing, record that as an **experiment finding**. A possible Core change is then evaluated later as a separate architecture decision.

Do **not** introduce observers, topology listeners, Core-owned bones, or other production-Core extensions as part of this experiment unless a later explicit architecture decision approves them.

## Context & Links

### Parent Documentation
- **Project Vision:** [docs/architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md](../../docs/architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md)
  - Living 3D System: Modeling → Deformation → Rigging → Animation
  - This experiment validates a core integration hypothesis

- **Core Hardening Plan:** [docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md](../../docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md)
  - Phase A–E completed; production Core remains deliberately constrained
  - ID-management constraints are relevant to skinning design

- **Topology Experiment:** [experiments/mirai_bastel_viewport_V1/TOPOLOGY_EXPERIMENT_PLAN.md](../mirai_bastel_viewport_V1/TOPOLOGY_EXPERIMENT_PLAN.md)
  - Working topology editing and selection experiments

### System Architecture
- **SOURCE_ARCHITECTURE.md:** How Core.Mesh is structured
- **AD-001 (ID Continuity):** No ID reuse within a session
- **Viewport:** Python + OpenGL

## Independence & Parallel Work

This experiment runs independently from the current Modeler/Interaction work.

- No production-Core dependency is introduced by the experiment
- Experiment code is disposable
- Existing Core and topology tests remain the baseline
- Findings may inform future architecture and work-package decisions
- No experiment result automatically becomes a production implementation

## Current Phase: Phase 2 — RigController Prototype

Phase 1 (research and architecture analysis) is complete. Phase 2 is intentionally **experiment-only**:

1. Implement an external `RigController`
2. Store bones, skinning weights, and morph-targets outside `Core.Mesh`
3. Use existing public Mesh APIs only
4. Implement deformation and topology-resynchronization logic in the experiment
5. Add focused unit tests
6. Record what information is available after topology mutations
7. Record concrete missing Core capabilities instead of patching the Core

The key research question is not merely whether skinning can be implemented, but **what information a dependent deformation system needs in order to remain correct after topology mutation**.

## Files in This Experiment

```
experiments/rigging-skinning-morphing/
├── rigging-skinning-morphing-README.md  ← Local context
├── rigging-skinning-morphing-RESEARCH.md ← Findings and open questions
├── rigging-skinning-morphing-DESIGN.md  ← Architecture options and revised strategy
├── AD-005-RIGGING-INTEGRATION.md        ← Current architecture decision
└── src/                                  ← Working prototypes (Phase 2+)
```

## Topology Research Targets

For each relevant topology mutation, document:

- Which mesh elements are created, deleted, or retained?
- Which IDs remain stable?
- Can the external RigController identify the affected elements using existing APIs?
- How can skinning weights be transferred or merged?
- How can morph data be transferred or interpolated?
- What information is unavailable that would be needed for robust synchronization?

Priority operations:

1. Split / edge-loop insertion
2. Collapse
3. Connect Edges
4. Other topology mutations as useful

## Principles

- **Capture first, discuss second, decide third, implement fourth**
- **Implement little, assume much**
- Never silently change Core architecture
- Experiments discover requirements; they do not grant production architecture changes
- Document missing capabilities before proposing Core modifications
- Keep experiment code pragmatic and disposable
- Only validated architecture is later considered for production extraction

---

**Started:** August 2026  
**Status:** Phase 1 complete → Phase 2 ready  
**Owner:** Manu (with independent parallel experimentation)
