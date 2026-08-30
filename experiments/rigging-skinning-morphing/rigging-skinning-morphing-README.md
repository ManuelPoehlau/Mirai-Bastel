# Rigging, Skinning & Morph-Targets Experiment

## Overview

This experiment investigates how skeletal rigging, skinning weights, and morph-targets can coexist cleanly with **topological mesh editing** — a capability historically rare outside specialized tools like the original Mirai.

**Core Question:** Can we edit the topology of a rigged, weighted, morphed mesh without destroying the rig, weights, or morph-target integrity?

**Use Case:** Low-poly character head workflow
- Neck, skull, jaw rigged with 3 bones
- Vertices weighted to bones (skinning)
- Facial deformations via morph-targets (mouth open, jaw drop, etc.)
- Then perform a topology operation (e.g., edge-loop insert in the face)
- Verify: Do weights auto-update? Do morphs stay intact? Does the rig still function?

## Context & Links

### Parent Documentation
- **Project Vision:** [docs/architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md](../../docs/architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md)
  - Living 3D System: Modeling → Deformation → Rigging → Animation
  - This experiment validates a core integration hypothesis

- **Core Hardening Plan:** [docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md](../../docs/architecture/CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md)
  - Phase A–E completed; Phase F (Production Freeze)
  - Key finding: ID-management constraints affect skinning design (see Phase C findings)

- **Topology Experiment (Phase 2):** [experiments/mirai_bastel_viewport_V1/TOPOLOGY_EXPERIMENT_PLAN.md](../mirai_bastel_viewport_V1/TOPOLOGY_EXPERIMENT_PLAN.md)
  - Edge-loop selection, insertion, removal already working
  - This experiment builds on that foundation

### System Architecture
- **SOURCE_ARCHITECTURE.md:** How Core.Mesh is structured
- **AD-001 (ID Continuity):** Why Undo/Redo uses state snapshots, not semantic ops
- **Viewport:** Python + OpenGL (not web-based)

## Independence & Parallel Work

This experiment **runs independently** from WP 02 (Cline's work).

- No blocking dependencies
- Evidence feeds forward into WP 02 design
- Both can progress without coordination
- Experiment code is disposable; only validated learnings move to src/

## Current Phase: Research & Architecture Decision

### What We're Doing Now
1. **RESEARCH.md:** Analyze Core's ID management, topology ops, and serialization
2. **DESIGN.md:** Sketch three architectural options (A: Skinning in Core, B: External Mapping, C: Hybrid)
3. **Architecture Decision (AD-XXX):** Choose one, document rationale

### Files in This Experiment
```
experiments/rigging-skinning-morphing/
├── README.md                           ← You are here
├── RESEARCH.md                         ← Ongoing findings from Core analysis
├── DESIGN.md                           ← Architecture option sketches
├── AD-XXX-RIGGING-CORE-INTEGRATION.md  ← TBD: Chosen decision
└── src/                                ← Working prototypes (Phase 2+)
    ├── bone.py
    ├── skinning.py
    ├── morph_targets.py
    └── deformation_viewport.py
```

## Next Steps

### Immediate
- [ ] Read CORE_V1_ANALYSIS_AND_HARDENING_PLAN.md and extract relevant findings
- [ ] Create RESEARCH.md with summary of ID management, topology ops, serialization
- [ ] Write DESIGN.md with three architectural options

### Then
- [ ] Architecture Decision (choose option A/B/C)
- [ ] Begin Phase 2 prototype (minimal bone/skin/morph code)
- [ ] Implement topology-aware integration test

## Principles (from AGENTS.md)

- **Capture first, discuss second, decide third, implement fourth**
- **Implement little, assume much**
- Never silently change Core architecture; document decisions first
- Documentation is part of the engineering system—not disposable chat notes
- Experiment code is pragmatic and disposable; only extract validated architecture to src/

## Related Experiments
- **Topology Experiment Phase 2:** Edge-loop selection, insertion, removal
- **Viewport (Python + OpenGL):** Real-time mesh visualization

---

**Started:** August 2026  
**Status:** Phase 1 – Research & Architecture Design  
**Owner:** Manu (with Cline's WP 02 separate and independent)
