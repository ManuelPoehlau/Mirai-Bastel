# Design Documentation

This directory contains interaction and workflow principles that guide how Mirai-Bastel should feel and behave. These are design principles, not implementation contracts.

## Documents

- [Workflow Principles](WORKFLOW.md) — direct, low-overhead interaction inspired by Mirai/Nendo/Silo/Wings3D
- [Rendering Vision](RENDERING_VISION.md) — PROPOSAL (2026-11-11): Artist-first character Lookdev, separate from the modelling Worklight; shared material/light intent across realtime and final rendering; Gollum eyes first; staged delivery and decision gates. See the companion [Rendering Technology Research](../research/RENDERING_TECHNOLOGY_RESEARCH.md).
- [LookDev Room P2 — architecture and UX proposal](LOOKDEV_P2_ARCHITECTURE_UX_PROPOSAL_2026-11-19.md) — PROPOSAL (2026-11-19): a LookDev room in the same window for the whole character; one organic material model with presets beside the eye system; the eye pass's LookDev variant in one linear colour pipeline; SH9 diffuse + analytic studio reflections; rule R-1 (rooms never reset pose / morph / gaze / SubD); M1 = Gollum head in a portrait studio; decisions LD-D1 … LD-D16 (**LD-D1 … LD-D14 decided by Manu 2026-11-19**). Measurements, shader notes and the test matrix in the [technical appendix](LOOKDEV_P2_TECHNICAL_APPENDIX_2026-11-19.md)
- [Likeness camera and reference camera matching — architecture and UX proposal](LIKENESS_CAMERA_ARCHITECTURE_UX_PROPOSAL_2026-11-27.md) — PROPOSAL (2026-11-27): likeness cameras with focal length and sensor converted into the one `OrbitCamera`'s FOV (no new camera math; roll, lens shift and crop live in the photo's fit), one photo per camera drawn as a screen-space backdrop behind or in front of the model, comparison views (blend, wire, wipe, flip; silhouette and contour later), manual matching first and landmark solving only if needed, the „Kameraansicht“ as a view state combinable with LookDev; session-only M1 / M2, persistence (recommended: a camera object, Core field) in M3; LC-D1, LC-D3, LC-D4, LC-D5 decided (Manu 2026-11-27, §0), LC-D2, LC-D6 … LC-D10 open; M1 architecture: [AD-042](../architecture/AD-042-LIKENESS-CAMERA-M1.md) (ACCEPTED, M1 and M2 built 2026-11-27)
- [GUI Bestandsaufnahme — Modelling, Morph, Rig](GUI_Bestandsaufnahme.md) — current Production GUI state snapshot (2026-11-03); verified facts `[V]`, UX hypotheses `[H]`, open Manu decisions `[O]`; starting point, not a specification
- [GUI Stage 1 — HUD](GUI_STAGE1_HUD.md) — read-only state display in the Production window (2026-10-23): two layout variants on trial, Stage 2 seams, open questions, Artist test steps; Stufe 1b (A1: status strip, bone name, XYZ triad) and Stufe 1c (A3: the weight view, `9`), 2026-11-03
- Input Map — archived 2026-10-28 ([`archive/input_truth_2026-10/`](../archive/input_truth_2026-10/README.md)); the input truth is the BindingSet with Manu's [`config/keymap.json`](../../config/keymap.json) (AD-013 addendum 2026-10-28)
- [Outliner key proposal](OUTLINER_KEYS_PROPOSAL.md) — (2026-11-07, approved by Manu except Duplicate): keys for hide / group objects reuse the H and G families by mode (AD-021 §6.8)
- [GUI framework spike brief](GUI_FRAMEWORK_SPIKE_BRIEF.md) — task for a fresh session (2026-11-07, Manu): evaluate Dear ImGui with the pyglet backend via an Outliner-panel spike; decision goes into a new AD
- [AD-030 GUI framework decision](../architecture/AD-030-GUI-FRAMEWORK.md) — result of that spike (2026-11-07): Dear ImGui via imgui-bundle, decided yes and implemented in `src/gui/` (2026-11-07)
- [UX Research](UX_RESEARCH.md) — open research / idea space; shared knowledge store of the Three-Role UX system; links back to the current Production GUI baseline
- [Modeling on deformed surfaces](MODELING_ON_DEFORMED_SURFACES.md) — **PROPOSED** long-term product requirement (2026-11-03, pending Manu's review): selecting and topology editing on the visible surface under morphs, posing or both; artist workflows, acceptance criteria, the current baseline (what runs on the rest cage and where that is enforced), Blender/Maya/3ds Max/ZBrush comparison, possible delivery stages; first slice **built 2026-11-03** (§15: hover, picking, Knife and drags on the dialled-in morph mix, base editing); second slice **built 2026-11-17** (§16: hover and picking on the posed surface for setting weights; position and topology stay refused in a pose)

The Artist Playground design documents (architecture map, roadmap, experiment host, research map, host and input
audits, AP-03 and WP-AP-CUT plans) were archived with the Playground on 2026-10-24:
[`archive/experiments_2026-10/artist_playground_design/`](../archive/experiments_2026-10/artist_playground_design/).

## Relationship to other documentation

- Architecture defines system boundaries.
- Design defines desired interaction and UX behavior.
- `docs/future_ideas/` records ideas that are intentionally not yet implemented.
- Experiments test whether a design idea works in practice.

A practical experiment may refine a design principle. Once a principle changes, update this authoritative design document instead of maintaining competing descriptions in experiment notes.
