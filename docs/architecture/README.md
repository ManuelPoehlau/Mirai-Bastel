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
| [AD-013](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md) | Capability promotion ≠ UX promotion; lab hooks H1/H2/H6 and (2026-10-16) H7, the Viewport's replacement surface for the SubD Lab; (2026-10-28) the BindingSet is the single input truth, Manu's keymap `config/keymap.json` | DECIDED |
| [AD-014](AD-014_Core-Change-Basis-Parameter-for-ScaleOperation.md) | ScaleOperation optional basis (Core-freeze exception) | Accepted |
| [AD-015](AD-015-PLAYGROUND-INPUT-OWNERSHIP-TWEAK-TRANSFORM.md) | Playground input ownership: Tweak vs. Transform | PARTIAL (superseded by pending audit, per document) |
| [AD-016](AD-016-TRANSFORM-OWNS-QWE-SINGLE-CURRENT-TOOL.md) | Transform owns Q/W/E, one current tool | DECIDED (ownership model) |
| [AD-017](AD-017-CUT-ENGINE-CONTEXTUAL-C.md) | Contextual C (Split/Connect); archived Artist inputs and review sit next to it | IMPLEMENTED (2026-09-22) |
| [AD-018](AD-018-PRODUCTION-DRAW-BINDING.md) | Production draw binding | DECIDED (Option B) |
| [AD-019](AD-019-POINTER-CLICK-VS-DRAG-BINDINGS.md) | Pointer click vs. drag in the bindings | DECIDED (engineering, 2026-09-26) |
| [AD-020](AD-020-SOFT-SELECTION-APP-PATH.md) | Soft Selection on the app path for the S2 Artist test (host, Core seam, influence state, visualization, keys, cost probe) | DECIDED (2026-10-10; capability `PROVISIONAL`) |
| [AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) | Object / Component model (ARCH-01): thin Object owning one Mesh, Reference state, object space for symmetry/soft | DECIDED (2026-10-15): reviewed, go for M0; M0, M1, M2-0, M2-0…M2-4 implemented (2026-10-15); Manu's practical tests pending |
| [AD-022](AD-022-GPU-PICKING.md) | GPU ID-buffer picking (WP-VIEW-PERF-02; spike in `experiments/gpu_picking_spike/`) | DECIDED (Manu, 2026-10-29); IMPLEMENTED B2-out (2026-10-21, §11) |
| [AD-023](AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md) | Incremental topology sync and history (delta history, partial viewport rebuild) | DECIDED (Manu, 2026-10-29); IMPLEMENTED (2026-10-21, §9: Core change journal) |
| [AD-024](AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md) | Per-object material (field on `SceneObject`, scene file v4) and Worklight editing in Production (setters, temporary bindings, Undo path) | DECIDED and IMPLEMENTED (2026-10-24) |
| [AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) | Topology identity / provenance (ARCH-02): vertex origin applied inside the Core primitives, mesh-owned point layers journaled per element or per whole layer (morph offsets), edit vs. frame-change rule, fail-closed operation gate; Manu's H1–H5 as parameters | **DECIDED (Manu, 2026-10-29)**; was PROPOSED (2026-10-27), revised after review [CLAUDE-001](../archive/deformation/reviews/AD-025_REVIEW_CLAUDE_001.md) (ACCEPT WITH CHANGES); **IMPLEMENTED (Phase 2, 2026-10-27)**: Core layers, journal, file v5, gate (`mirai/layer_declarations.py`); H1–H5 and C-1 decided by Manu (2026-10-27, all defaults); **IMPLEMENTED (Phase 3, 2026-10-27)**: one morph target in the app, editing view (§15, `mirai/morph_targets.py`); **IMPLEMENTED (Phase 5, 2026-10-27)**: topology edits with targets, Knife origins `split_face(…, origins=…)` (§16); **IMPLEMENTED (Phase 4, 2026-10-27)**: several targets, the additive mix (`mirai/morph_mix.py`), the stage chain morph → SubD (`mirai/surface_chain.py`), packed layer storage (`core/layer_storage.py`) (§17) |
| [AD-026](AD-026-FACE-CORNER-UVS-AND-TEXTURE.md) | Face-corner UVs on the Mesh (journaled, carried by every topology primitive, `"face_uvs"`), a texture per object (`SceneObject.texture`, scene file v6), OBJ import/export of UVs and texture, textured viewport program | DECIDED and IMPLEMENTED (2026-10-29); display `PROVISIONAL`, practical test B24 pending; **addendum 2026-11-16 (Eye LookDev phase 5):** texture paths inside the scene's directory written scene-relative (no new format version, no Core code change), eye iris images copied into `<scene>_textures/` by content hash |
| [AD-027](AD-027-INTERACTION-LAYER-SESSION-SLOT.md) | Interaction layer before skinning and the clickable GUI: one session slot (sessions + ranked hold keys), one staged `can_run` for keys, `dispatch_command`, HUD and GUI, Knife / Morph / Objects / Symmetry / gestures as controllers; behaviour-neutral, proven against a golden input corpus | **DECIDED (Manu, 2026-10-29)** with review [DEVCHAT-001](../archive/interaction_layer/reviews/AD-027_REVIEW_DEVCHAT_001.md) changes C1–C3; **implemented M0–M8 (2026-10-30)** |
| [AD-028](AD-028-SKELETON-AND-SKINNING.md) | Skeleton and skinning (AD-025 Phase 6): rig on `Scene.rig` (bones, rest frames = bind pose), weights as the WEIGHTS point layer (≤ 4 influences, the remainder to the parent bone, the object's share implicit), CPU linear blend skinning as a chain stage morph → skin → SubD, pose as view state, pose mode in the AD-027 structure | **DECIDED (Manu, 2026-11-02)** with review [DEVCHAT-001](../archive/deformation/reviews/AD-028_REVIEW_DEVCHAT_001.md) changes C1–C3; go for the Core change; **IMPLEMENTED (slices 1–4, 2026-11-02/03)**: the weights kind and the rig in the Core (`core/rig.py`, file v7), the skin stage morph → skin → SubD (`mirai/skinning.py`), the write rule (`mirai/skin_weights.py`), the app (`controllers/skeleton.py`: bones, pose mode, weight gestures, the stage-7 policies) and the jaw scenario (§17); open: Manu's practical test and the reference-PC run of `--only-skin` |
| [AD-029](AD-029-ZBRUSH-GOZ-BRIDGE.md) | Mirai ↔ ZBrush 2022.0.8 over GoZ, P1: one object's positions in place when the topology is unchanged (one Undo step, after the artist's confirm), everything else as a new object; `src/interop/goz/` (core + stdlib only), `src/zbrush_bridge.py`, `Application.apply_goz_return` | **IMPLEMENTED (P1, 2026-11-05)**; D1, D11–D13 decided by Manu; open: orientation check and practical test on the reference PC |
| [AD-030](AD-030-GUI-FRAMEWORK.md) | GUI framework for panels (Outliner, Look, Regions, Rig): Dear ImGui via `imgui-bundle` on pyglet; `src/gui/` (bench: `experiments/gui_framework_spike/`) | **DECIDED + IMPLEMENTED Phase 1 (Manu, 2026-11-07)**: `src/gui/`; open: key for the panel, HiDPI, measurement on the reference PC |
| [AD-031](AD-031-ATTACH-DETACH-WELD-BRIDGE.md) | Attach / Detach / Weld / Bridge: combine objects into one mesh (islands), extract faces into a new object, weld selected points to their group centroid, bridge two border loops; never merge targets or regions by name, look must match or be taken over explicitly; `src/mirai` only, no Core change | **DECIDED (Manu, 2026-11-09)**: D1–D9, D11; D10 provisional (threshold reference 0.001 × world bounding-box diagonal); **P1 built (2026-11-10)**: the assembly kernel `mirai/mesh_assembly.py`; **P2 built (2026-11-10)**: Attach (`Application.attach_objects`, `mirai/attach.py`, "Mesh" menu and outliner context menu; O-1, O-2, O-5, O-7, O-13 decided, D4 precise; §15, practical test §16); **P3 built (2026-11-10)**: Detach and Select Linked (`Application.detach_faces` / `select_linked`, `mirai/detach.py`, `mesh_assembly.linked_faces`; "Mesh" > Detach, SPACE > Select Linked; O-8 KEEP and O-14 "SPACE reicht vorerst" decided in the practical test, §17, §18); **P4 built (2026-11-10)**: Weld (`Application.weld_vertices` / `weld_plan`, `mirai/topology/weld.py`, W1–W11; "Mesh" > "Weld…" with the threshold field and preview; W5 changed 2026-11-10: single pairs allowed and reported; §19, practical test §20, D10-v open); **P5 built (2026-11-10)**: Bridge (`Application.bridge_borders` / `bridge_plan`, `mirai/topology/bridge.py`; "Mesh" > "Bridge"; equal counts, O-11 CHANGE decided, not built; no UVs, no region; §21, practical test §22); **P6 built (2026-11-10)**: symmetric Weld / Bridge (P6-a…d; `symmetric_ops` coordinators, declared in `symmetry_declarations` / `layer_declarations`; §23, practical test §24); P7 not implemented (own go); open: §10 |
| [AD-032](AD-032-PACKED-ARRAYS-NUMPY.md) | Packed arrays (NumPy) for the viewport's derived geometry (audit O3, stage 1): positions, face / vertex normals and their adjacency on `RenderMesh`'s slots and rows (`src/viewport/packed_geometry.py`), patched from the journal; normals bit-identical to the Python reference (vertex normals summed in ascending FaceId order); the store takes float32 arrays; `numpy==2.2.6` in `requirements.txt`, NumPy above the Core only. Stage 2 (§11–§12): the morph mix and the skin stage on slot arrays (bit-identical to `evaluate`), the O1 table as n×3 float64 with a slot-chunk journal (`slot_moves()`), the array hand-over to `RenderMesh` (no read per vertex) | **IMPLEMENTED stage 1 (2026-11-12) and stage 2 (2026-11-13)**, agent decisions within Manu's D1; reference PC 2026-11-13 (stage 1): D1 verified (Python 3.12.10 + NumPy 2.2.6), `_sync_geometry` 205 → 35 ms, D3 still over; stage 2 on the reference PC 2026-11-13: stage evaluation 55 / 92 → 9 / 13 ms, D3 frame pose / weight 118 / 189 → 51 / 85 ms p50 — still over the bar, D2's condition (O4) reached |
| [AD-033](AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md) | Eye preview in the Worklight (Lookdev step 1): a parametric eye object (one shell mesh, `SceneObject.eye`, format v9) drawn by an eye pass with the Eye-Lab shading (refraction V2/V3, iris fit, soft limbus L0–L3) in the normal Worklight view; the lab frozen as the oracle | **DECIDED (Manu, 2026-11-15)**: promotion and Core field approved, Q-E3–Q-E5 as proposed, 1 unit = 1 cm; **IMPLEMENTED E-1 … E-3 (2026-11-15)**: `SceneObject.eye` + format v9, `mirai/eye_object.py`, the eye pass (`viewport/eye_pass.py`, `eye_shaders.py`, `eye_optics.py`), panel "Auge", menu entry "eye"; deviations in §11 (analytic studio instead of the cube, the Worklight's own diffuse light, per-triangle split); **§12 (2026-11-16): eye gaze** (camera / mouse / fixed point, view state, `mirai/eye_gaze.py`); **§14 (2026-11-16): view twins** of eyes and teeth beside a morph target's editing view (viewport entries only); **§15: E-4 measured** on the reference PC (`experiments/drag_cost/RESULTS_EYE_PREVIEW_REFERENCE_PC_2026-11-16.md`) and the eye pass's per-frame CPU cost removed; **§16–§18 (2026-11-16): Eye LookDev** phase 2 (panel "Auge" + Eye Lab window), phase 3 (reflections, `EyeLook`, format v10, practical test KEEP), phase 4 (iris: key through the cornea with crescent and rim shadow, relief, pupil edge; `EyeIris`, format v11; reference-PC cost within the I-12 target after the key table; practical test KEEP; I-9 "image beside the scene": yes); **§19 (2026-11-16): phase 5, the iris import** in the Eye Lab (frontal photo with the baked inverse refraction / flat image, landmark circles, height in alpha, copies in `<scene>_textures/`, scene-relative texture paths - AD-026 addendum; no Core change; practical test pending) |
| [AD-035](AD-035-SCLERA-COLOUR-MAP.md) | The sclera's colour map (Eye LookDev M1): an optional RGB image per eye (`EyeSpec.sclera_texture`, format v12) in the limbus-anchored front-disc layout (limbus at ¼ of half the width, rim 130°, clamped), read at the two places the eye shader reads the sclera colour (`SCLERA_MAP` variant, unit 4, own sampler; without a map the program is the one before, pinned), both tiers; loaded / replaced / removed in the Eye Lab (one Undo step each), scene-relative, copied on Save As, untouched by presets; no selection tint on eyes in the Eye Lab (S-4) | **DECIDED (Manu, 2026-11-17)**: S-1 … S-13, Core change + v12 approved; **IMPLEMENTED M1 (2026-11-17, container: TESTED)**; reference-PC cost and practical test pending |
| [AD-036](AD-036-EYES-TEETH-AND-LIDS-ON-THE-RIG.md) | Eyes, teeth and lids on the rig (Architecture Gate after AD-028's bone tool): rigid parts follow a bone through a link on the object (`SceneObject.bone`, format v13, no stored offset: the skin transforms are rest-relative), deforming parts keep weights, every object shows the pose; eyes link to their eye bone, the eye pass's lid frame follows the head; gaze drives the eye bones in a pose (lids follow), at rest only the eyeballs; lids by weights on the eye bone, with the limits of linear blending named | **ACCEPTED (Manu, 2026-11-18)**: "Baue AD-036, Scheiben 1–2; §13 zuerst als Checkliste" (E1–E4 as recommended, agent reading; E5 open); §13 checklist done; **IMPLEMENTED slices 1–2 (2026-11-18, container: TESTED)**; slice 3, reference-PC run and practical test pending |
| [AD-037](AD-037-TEXTURE-PAINT.md) | Texture paint, Phase 1 (foundations), Phase 3 (layers, Multiply, UV transfer) and Phase 2 (the Paint Room: SPACE row, no key; an exclusive session, LMB drag paints on the **shown** surface - SubD when it shows -, world radius, opacity / flow stroke buffer, mirror, seam padding, Pick, one Undo step per stroke, live composite per painted object; batched texel-map build) - Phase 1: UV image painting as the one storage; paint layers on the object (`SceneObject.paint`: `PaintStack` / `PaintLayer`, format v14, no pixels in the Core) above the untouched texture; CPU pixels per object instance (`mirai.paint.store`: tiles, one Undo step per stroke, Esc exact, composite), layer PNGs and a flattened PNG in `<scene>_textures/` on save; the texel → surface map with journal patching (`texel_map`); the read-only UV check (SPACE „UV-Prüfung“, no key); `viewport.live_texture` (tile uploads, mip policies) | **DECIDED (Manu, 2026-11-18)**: P-1, P-2, P-3 (Go, v14), P-4, P-6; **IMPLEMENTED Phase 1 (2026-11-18, container: TESTED)**; P-7 / P-10 / P-13 decided, the P-13 refusals built; reference PC run: P-A/B/C/E pass, P-D / P-F failed and worked on (re-run open); **IMPLEMENTED Phase 2 (2026-11-18, container: TESTED; reference PC: bars met, §10.8e)**; Phase 3 scope and P-12 (Normal + Multiply): Manu 2026-11-19; **IMPLEMENTED Phase 3 (2026-11-19: several layers in the panel, Multiply, merge down, the UV transfer on a GoZ UV change; container: TESTED, reference-PC run open)** |
| [AD-038](AD-038-LOOKDEV-ROOM-M1.md) | LookDev Room M1 (LD-0 / LD-1): a non-exclusive room in the same window (SPACE row, no key) under rule R-1 (room transitions never reset pose, morph, gaze or SubD); `Viewport.shading` and a `LookdevPass` outside `GLRenderStore.draw()` on the evaluated `RenderMesh`es; the smallest interface (a UV request on `RenderMesh`, one triangle-UV binding, one texture binding); the eye pass's `LOOKDEV` variant in one linear colour pipeline (Worklight sources pinned, a new pin over all 1,030); SH9 + the parametric analytic studio; one organic material model with six presets, session only; background as picked; test matrix and stop points; LD-0 probe `experiments/drag_cost/probe_lookdev.py` | **ACCEPTED (Manu, 2026-11-19)**: „AD-038 freigegeben, Fragen 2–4 wie vorgeschlagen, Frage 3 … Neutral“; LD-0 on the reference PC: the framed head 1.7 / 2.2 ms GPU at 1024×768 (5–7 % of 33.3 ms), cheaper than the Worklight; **LD-1 built 2026-11-19** (§17: slices, deviations I-1 … I-15, tests, reference-PC command, practical-test checklist), M1 practical test next |
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
