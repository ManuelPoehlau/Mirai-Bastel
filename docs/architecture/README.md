# Architecture Documentation

This directory contains the current architectural contracts and accepted direction of Mirai-Bastel.

## Start here

| Document | Role |
|---|---|
| [Project Vision & V1 Principle](PROJECT_VISION_AND_V1_PRINCIPLE.md) | Long-term system vision and the rule: implement little, assume much |
| [Architecture & Development Roadmap](ROADMAP.md) | Current system dependency graph, work packages, architecture gates and development workflow |
| [Input / Command / Tool / Operation Contract](INPUT_COMMAND_TOOL_CONTRACT.md) | Accepted input/tool separation and configurable binding contract for WP-01A |
| [Source Architecture](SOURCE_ARCHITECTURE.md) | Production `src/` boundaries and dependency direction |
| [Reference Hardware](REFERENCE_HARDWARE.md) | The developer/test PC (CPU, GPU, RAM, input devices) and what follows from it for performance and rendering questions |
| [V1 Core](V1_CORE.md) | Core V1 architecture and contracts |
| [Core V1 Freeze](CORE_V1_FREEZE.md) | Final accepted Core V1 state and freeze boundary |
| [AD-004 — System Vision Reevaluation](AD-004-SYSTEM-VISION-REEVALUATION.md) | Recorded architectural decision about the larger system direction |
| [V1 Specification](../V1_SPEC.md) | Functional and architectural scope of the V1 milestone |

## Architecture decisions

Status wie im jeweiligen Dokumentkopf; dort steht die maßgebliche Angabe. AD-001 bis AD-003 stehen in [V1_CORE.md](V1_CORE.md).

| Decision | Topic | Status (per document) |
|---|---|---|
| [AD-004](AD-004-SYSTEM-VISION-REEVALUATION.md) | System vision re-evaluation | Accepted architectural guidance |
| [AD-005](AD-005-RIGGING-INTEGRATION.md) | Rigging integration (never implemented; experiment removed 2026-10-24) | SUPERSEDED (2026-10-27) by AD-021 §4.9 + ARCH-02 |
| [AD-006](AD-006-V1-VIEWPORT-RETIREMENT.md) | V1 viewport retirement | DECIDED |
| [AD-007](AD-007-SHARED-ASSET-LOADER-OWNERSHIP.md) | Shared asset & loader ownership | DECIDED |
| [AD-008](AD-008-IMPORT-FRAMING-PRODUCTION.md) | Import, mesh geometry queries, camera framing become production capabilities | DECIDED |
| [AD-009](AD-009-AXIS-PLANE-CONSTRAINTS.md) | Axis/plane constraints for Move/Rotate/Scale | DECIDED |
| [AD-010](AD-010-PLAYGROUND-SUPERSEDES-LAB-BINDING.md) | Playground supersedes the Lab's Core→Viewport binding role | DECIDED |
| [AD-011](AD-011-PLAYGROUND-IDENTITY-STATUS-QUO.md) | Playground identity: status quo | DECIDED |
| [AD-012](AD-012-TRANSFORM-SPACE.md) | Transform space unification | Accepted (amended 2026-09-19) |
| [AD-013](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md) | Capability promotion ≠ UX promotion; lab hooks H1/H2/H6 and (2026-10-16) H7, the Viewport's replacement surface for the SubD Lab | DECIDED |
| [AD-014](AD-014_Core-Change-Basis-Parameter-for-ScaleOperation.md) | ScaleOperation optional basis (Core-freeze exception) | Accepted |
| [AD-015](AD-015-PLAYGROUND-INPUT-OWNERSHIP-TWEAK-TRANSFORM.md) | Playground input ownership: Tweak vs. Transform | PARTIAL (superseded by pending audit, per document) |
| [AD-016](AD-016-TRANSFORM-OWNS-QWE-SINGLE-CURRENT-TOOL.md) | Transform owns Q/W/E, one current tool | DECIDED (ownership model) |
| [AD-017](AD-017-CUT-ENGINE-CONTEXTUAL-C.md) | Contextual C (Split/Connect); archived Artist inputs and review sit next to it | IMPLEMENTED (2026-09-22) |
| [AD-018](AD-018-PRODUCTION-DRAW-BINDING.md) | Production draw binding | DECIDED (Option B) |
| [AD-019](AD-019-POINTER-CLICK-VS-DRAG-BINDINGS.md) | Pointer click vs. drag in the bindings | DECIDED (engineering, 2026-09-26) |
| [AD-020](AD-020-SOFT-SELECTION-APP-PATH.md) | Soft Selection on the app path for the S2 Artist test (host, Core seam, influence state, visualization, keys, cost probe) | DECIDED (2026-10-10; capability `PROVISIONAL`) |
| [AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) | Object / Component model (ARCH-01): thin Object owning one Mesh, Reference state, object space for symmetry/soft | DECIDED (2026-10-15): reviewed, go for M0; M0, M1, M2-0, M2-0…M2-4 implemented (2026-10-15); Manu's practical tests pending |
| [AD-022](AD-022-GPU-PICKING.md) | GPU ID-buffer picking (WP-VIEW-PERF-02; spike in `experiments/gpu_picking_spike/`) | IMPLEMENTED B2-out (2026-10-21, §11) |
| [AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) | Incremental topology sync and history (delta history, partial viewport rebuild) | IMPLEMENTED (2026-10-21, §9: Core change journal) |
| [AD-024](AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md) | Per-object material (field on `SceneObject`, scene file v4) and Worklight editing in Production (setters, temporary bindings, Undo path) | DECIDED and IMPLEMENTED (2026-10-24) |
| [AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) | Topology identity / provenance (ARCH-02): vertex origin applied inside the Core primitives, mesh-owned point layers journaled per element (morph offsets), edit vs. frame-change rule, fail-closed operation gate; Manu's H1–H5 as parameters | PROPOSED (2026-10-27), revised after review [CLAUDE-001](../archive/deformation/reviews/AD-025_REVIEW_CLAUDE_001.md) (ACCEPT WITH CHANGES); awaiting Manu |
| [AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md) | Symmetry definition storage | DECIDED |
| [AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md) | Symmetric operation / history contract | DECIDED |
| [AD-SYM-03](AD-SYM-03-SYMMETRIC-TOPOLOGY-COORDINATION.md) | Symmetric topology coordination (Split/Connect/Delete/Dissolve/Knife/Extrude without `SymmetricX` copies) | DECIDED (2026-10-08) |
| [AD-SYM-04](AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md) | Symmetry in `src/main.py` (entry, display, AD-013 H2 text), Core basis and slices for symmetric Soft Selection | DECIDED (2026-10-14); slices A1, A2 built (2026-10-14) |
| [AD-SYM-05](AD-SYM-05-WEIGHTED-TRANSFORMS-IN-CORE.md) | Weighted transforms in the Core: the one Core change of symmetric Soft Selection (slice SS1), P-a seam category, R-6 at pair level | DECIDED (2026-10-14): reviewed, go for SS1 |
| [AD-REGIONS-01](AD-REGIONS-01-FACE-REGIONS-STORAGE.md) | Face regions (saved regions / polygroups): mesh-owned, journaled, saved as `"face_regions"`; new faces inherit their parents' regions (Slice 3) | DECIDED (2026-10-25); Slices 1–3 built |
| [ADR-001](../ADR-001-core-v1-reassessment.md) | Core V1 reassessment | Accepted |

Production entry point and integration: [Stage A](PRODUCTION_ENTRY_POINT_STAGE_A.md), [WP-06 Stage B kickoff](../archive/handoffs_2026-10/WP-06_STAGE_B_KICKOFF.md).

## Responsibility boundaries

The high-level system is intentionally separated into conceptual responsibilities:

```text
Scene / Mesh Core
    ↓
Topology / domain data / history boundaries

Selection / Influence
    ↓
Editor selection state and future influence behavior

Viewport / Camera
    ↓
Projection / picking / hover / display

Input / Interaction / Modeling Tools
    ↓
Input → Command → Tool → Operation → Core

Application / UI
    ↓
Windowing and presentation
```

These are **responsibility boundaries, not a final `src/` directory tree**. The production source structure is deliberately being derived from the experiments rather than frozen prematurely.

## How to use these documents

`PROJECT_VISION_AND_V1_PRINCIPLE.md` answers **where the system is intended to go**.

`ROADMAP.md` answers **how the current architecture and dependencies translate into development work packages and gates**.

`INPUT_COMMAND_TOOL_CONTRACT.md` answers **how physical input becomes user intent and, where applicable, an interactive tool and model operation**.

`V1_CORE.md` and `CORE_V1_FREEZE.md` answer **what was deliberately established for Core V1**.

`SOURCE_ARCHITECTURE.md` answers **how production code under `src/` is currently bounded**. It is intentionally not a promise of the final application tree.

`V1_SPEC.md` answers **what V1 is meant to accomplish**. It should not be treated as a roadmap for implementing every future subsystem listed in the vision.

Historical reviews and completed working plans are kept in [`../archive/`](../archive/README.md) where possible. They are evidence and project memory, not competing current architecture.

## Architectural rule

> **Implement little. Assume much.**

Known future requirements should influence stable boundaries, but speculative future frameworks should not be built without real use cases.

## Related design and experiments

- Interaction principles: [`../design/README.md`](../design/README.md)
- Deferred ideas: [`../future_ideas/README.md`](../future_ideas/README.md)
- Research: [`../research/README.md`](../research/README.md)
- Experimental prototypes: [`../../experiments/README.md`](../../experiments/README.md)
