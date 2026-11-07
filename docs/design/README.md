# Design Documentation

This directory contains interaction and workflow principles that guide how Mirai-Bastel should feel and behave. These are design principles, not implementation contracts.

## Documents

- [Workflow Principles](WORKFLOW.md) — direct, low-overhead interaction inspired by Mirai/Nendo/Silo/Wings3D
- [GUI Bestandsaufnahme — Modelling, Morph, Rig](GUI_Bestandsaufnahme.md) — current Production GUI state snapshot (2026-11-03); verified facts `[V]`, UX hypotheses `[H]`, open Manu decisions `[O]`; starting point, not a specification
- [GUI Stage 1 — HUD](GUI_STAGE1_HUD.md) — read-only state display in the Production window (2026-10-23): two layout variants on trial, Stage 2 seams, open questions, Artist test steps; Stufe 1b (A1: status strip, bone name, XYZ triad) and Stufe 1c (A3: the weight view, `9`), 2026-11-03
- Input Map — archived 2026-10-28 ([`archive/input_truth_2026-10/`](../archive/input_truth_2026-10/README.md)); the input truth is the BindingSet with Manu's [`config/keymap.json`](../../config/keymap.json) (AD-013 addendum 2026-10-28)
- [Outliner key proposal](OUTLINER_KEYS_PROPOSAL.md) — (2026-11-07, approved by Manu except Duplicate): keys for hide / group objects reuse the H and G families by mode (AD-021 §6.8)
- [UX Research](UX_RESEARCH.md) — open research / idea space; shared knowledge store of the Three-Role UX system; links back to the current Production GUI baseline
- [Modeling on deformed surfaces](MODELING_ON_DEFORMED_SURFACES.md) — **PROPOSED** long-term product requirement (2026-11-03, pending Manu's review): selecting and topology editing on the visible surface under morphs, posing or both; artist workflows, acceptance criteria, the current baseline (what runs on the rest cage and where that is enforced), Blender/Maya/3ds Max/ZBrush comparison, possible delivery stages; first slice **built 2026-11-03** (§15: hover, picking, Knife and drags on the dialled-in morph mix, base editing)

The Artist Playground design documents (architecture map, roadmap, experiment host, research map, host and input
audits, AP-03 and WP-AP-CUT plans) were archived with the Playground on 2026-10-24:
[`archive/experiments_2026-10/artist_playground_design/`](../archive/experiments_2026-10/artist_playground_design/).

## Relationship to other documentation

- Architecture defines system boundaries.
- Design defines desired interaction and UX behavior.
- `docs/future_ideas/` records ideas that are intentionally not yet implemented.
- Experiments test whether a design idea works in practice.

A practical experiment may refine a design principle. Once a principle changes, update this authoritative design document instead of maintaining competing descriptions in experiment notes.
