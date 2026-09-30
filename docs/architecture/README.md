# Architecture Documentation

This directory contains the current architectural contracts and accepted direction of Mirai-Bastel.

## Start here

| Document | Role |
|---|---|
| [Project Vision & V1 Principle](PROJECT_VISION_AND_V1_PRINCIPLE.md) | Long-term system vision and the rule: implement little, assume much |
| [Architecture & Development Roadmap](ROADMAP.md) | Current system dependency graph, work packages, architecture gates and development workflow |
| [Input / Command / Tool / Operation Contract](INPUT_COMMAND_TOOL_CONTRACT.md) | Accepted input/tool separation and configurable binding contract for WP-01A |
| [Source Architecture](SOURCE_ARCHITECTURE.md) | Production `src/` boundaries and dependency direction |
| [V1 Core](V1_CORE.md) | Core V1 architecture and contracts |
| [Core V1 Freeze](CORE_V1_FREEZE.md) | Final accepted Core V1 state and freeze boundary |
| [AD-004 — System Vision Reevaluation](AD-004-SYSTEM-VISION-REEVALUATION.md) | Recorded architectural decision about the larger system direction |
| [V1 Specification](../V1_SPEC.md) | Functional and architectural scope of the V1 milestone |

## Architecture decisions

Status wie im jeweiligen Dokumentkopf; dort steht die maßgebliche Angabe. AD-001 bis AD-003 stehen in [V1_CORE.md](V1_CORE.md).

| Decision | Topic | Status (per document) |
|---|---|---|
| [AD-004](AD-004-SYSTEM-VISION-REEVALUATION.md) | System vision re-evaluation | Accepted architectural guidance |
| [AD-005](../../experiments/rigging-skinning-morphing/src/AD-005-RIGGING-INTEGRATION.md) | Rigging integration (lives in the rigging experiment) | see document |
| [AD-006](AD-006-V1-VIEWPORT-RETIREMENT.md) | V1 viewport retirement | DECIDED |
| [AD-007](AD-007-SHARED-ASSET-LOADER-OWNERSHIP.md) | Shared asset & loader ownership | DECIDED |
| [AD-008](AD-008-IMPORT-FRAMING-PRODUCTION.md) | Import, mesh geometry queries, camera framing become production capabilities | DECIDED |
| [AD-009](AD-009-AXIS-PLANE-CONSTRAINTS.md) | Axis/plane constraints for Move/Rotate/Scale | DECIDED |
| [AD-010](AD-010-PLAYGROUND-SUPERSEDES-LAB-BINDING.md) | Playground supersedes the Lab's Core→Viewport binding role | DECIDED |
| [AD-011](AD-011-PLAYGROUND-IDENTITY-STATUS-QUO.md) | Playground identity: status quo | DECIDED |
| [AD-012](AD-012-TRANSFORM-SPACE.md) | Transform space unification | Accepted (amended 2026-09-19) |
| [AD-013](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md) | Capability promotion ≠ UX promotion | DECIDED |
| [AD-014](AD-014_Core-Change-Basis-Parameter-for-ScaleOperation.md) | ScaleOperation optional basis (Core-freeze exception) | Accepted |
| [AD-015](AD-015-PLAYGROUND-INPUT-OWNERSHIP-TWEAK-TRANSFORM.md) | Playground input ownership: Tweak vs. Transform | PARTIAL (superseded by pending audit, per document) |
| [AD-016](AD-016-TRANSFORM-OWNS-QWE-SINGLE-CURRENT-TOOL.md) | Transform owns Q/W/E, one current tool | DECIDED (ownership model) |
| [AD-017](AD-017-CUT-ENGINE-CONTEXTUAL-C.md) | Contextual C (Split/Connect); archived Artist inputs and review sit next to it | IMPLEMENTED (2026-09-22) |
| [AD-018](AD-018-PRODUCTION-DRAW-BINDING.md) | Production draw binding | DECIDED (Option B) |
| [AD-019](AD-019-POINTER-CLICK-VS-DRAG-BINDINGS.md) | Pointer click vs. drag in the bindings | DECIDED (engineering, 2026-09-26) |
| [AD-SYM-01](AD-SYM-01-SYMMETRY-DEFINITION-STORAGE.md) | Symmetry definition storage | DECIDED |
| [AD-SYM-02](AD-SYM-02-SYMMETRIC-OPERATION-HISTORY-CONTRACT.md) | Symmetric operation / history contract | DECIDED |
| [ADR-001](../ADR-001-core-v1-reassessment.md) | Core V1 reassessment | Accepted |

Production entry point and integration: [Stage A](PRODUCTION_ENTRY_POINT_STAGE_A.md), [WP-06 Stage B kickoff](WP-06_STAGE_B_KICKOFF.md).

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
