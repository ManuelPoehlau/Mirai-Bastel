# Design Documentation

This directory contains interaction and workflow principles that guide how Mirai-Bastel should feel and behave. These are design principles, not implementation contracts.

## Documents

- [Workflow Principles](WORKFLOW.md) — direct, low-overhead interaction inspired by Mirai/Nendo/Silo/Wings3D
- [GUI Stage 1 — HUD](GUI_STAGE1_HUD.md) — read-only state display in the Production window (2026-10-23): two layout variants on trial, Stage 2 seams, open questions, Artist test steps
- [Input Map](INPUT_WIRING_MAP.md) — Manu's desired physical input bindings (Artist Input Truth)
- [UX Research](UX_RESEARCH.md) — open research / idea space; shared knowledge store of the Three-Role UX system

The Artist Playground design documents (architecture map, roadmap, experiment host, research map, host and input
audits, AP-03 and WP-AP-CUT plans) were archived with the Playground on 2026-10-24:
[`archive/experiments_2026-10/artist_playground_design/`](../archive/experiments_2026-10/artist_playground_design/).

## Relationship to other documentation

- Architecture defines system boundaries.
- Design defines desired interaction and UX behavior.
- `docs/future_ideas/` records ideas that are intentionally not yet implemented.
- Experiments test whether a design idea works in practice.

A practical experiment may refine a design principle. Once a principle changes, update this authoritative design document instead of maintaining competing descriptions in experiment notes.
