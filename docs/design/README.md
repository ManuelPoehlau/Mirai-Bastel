# Design Documentation

This directory contains interaction and workflow principles that guide how Mirai-Bastel should feel and behave. These are design principles, not implementation contracts.

## Documents

- [Workflow Principles](WORKFLOW.md) — direct, low-overhead interaction inspired by Mirai/Nendo/Silo/Wings3D

## Artist Playground

- [Artist Playground — Architecture Map](artist_playground/ARCHITECTURE_MAP.md) — building block status analysis: what exists, what is missing, what must not be changed
- [Artist Playground — Roadmap](artist_playground/ROADMAP.md) — WP-AP work package sequence and development model (research-first, Playground → Candidate → Production)

## Relationship to other documentation

- Architecture defines system boundaries.
- Design defines desired interaction and UX behavior.
- `docs/future_ideas/` records ideas that are intentionally not yet implemented.
- Experiments test whether a design idea works in practice.

A practical experiment may refine a design principle. Once a principle changes, update this authoritative design document instead of maintaining competing descriptions in experiment notes.
