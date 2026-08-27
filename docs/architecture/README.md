# Architecture Documentation

This directory contains the current architectural contracts and accepted direction of Mirai-Bastel.

## Start here

| Document | Role |
|---|---|
| [Project Vision & V1 Principle](PROJECT_VISION_AND_V1_PRINCIPLE.md) | Long-term system vision and the rule: implement little, assume much |
| [Source Architecture](SOURCE_ARCHITECTURE.md) | Production `src/` boundaries and dependency direction |
| [V1 Core](V1_CORE.md) | Core V1 architecture and contracts |
| [Core V1 Freeze](CORE_V1_FREEZE.md) | Final accepted Core V1 state and freeze boundary |
| [AD-004 — System Vision Reevaluation](AD-004-SYSTEM-VISION-REEVALUATION.md) | Recorded architectural decision about the larger system direction |
| [V1 Specification](../V1_SPEC.md) | Functional and architectural scope of the V1 milestone |

## How to use these documents

`PROJECT_VISION_AND_V1_PRINCIPLE.md` answers **where the system is intended to go**.

`V1_CORE.md` and `CORE_V1_FREEZE.md` answer **what was deliberately established for Core V1**.

`SOURCE_ARCHITECTURE.md` answers **how production code under `src/` is currently bounded**. It is intentionally not a promise of the final application tree.

`V1_SPEC.md` answers **what V1 is meant to accomplish**. It should not be treated as a roadmap for implementing every future subsystem listed in the vision.

Historical reviews and completed working plans are kept in [`../archive/`](../archive/README.md). They are evidence and project memory, not competing current architecture.

## Architectural rule

> **Implement little. Assume much.**

Known future requirements should influence stable boundaries, but speculative future frameworks should not be built without real use cases.
