# Mirai Rendering — Product Vision & Design Direction

**Status:** PROPOSAL — product direction and research synthesis, not an accepted Architecture Decision (ADR)  
**Date:** 2026-11-11  
**Artist requirements recorded:** Manu, 2026-11-11  
**Related research:** [Rendering Technology Research](../research/RENDERING_TECHNOLOGY_RESEARCH.md)  
**Current implementation references:** [AD-024](../architecture/AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md), [Reference Hardware](../architecture/REFERENCE_HARDWARE.md), [Viewport Shading Research](../research/viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md)

---

## 1. Product intent

Mirai should let an Artist judge and develop the appearance of a character under convincing light without having to become a rendering engineer.

The primary example is Gollum: the face must read as a believable, living surface. The eyes should have depth, wetness and convincing reflections; skin should respond plausibly to light; facial folds and expression must remain legible; shadows and contact between forms should ground the character in its environment.

The goal is not to reproduce every feature of a large commercial renderer. It is to create a focused, coherent character Lookdev workflow whose technical complexity stays mostly below the Artist-facing surface.

### User requirements (Manu, 2026-11-11)

- Support both the legacy reference PC and a more capable main PC.
- Detect capabilities and adapt quality automatically, while preserving manual control.
- Support interactive Lookdev and a route to high-quality final images.
- Prioritise eyes, reflections and facial expression first.
- The final visual goal includes believable lighting, shading, cast/contact shadows, reflections, skin and eyes.
- Prefer a focused Artist workflow over a large collection of low-level renderer settings.

The main PC model and its exact CPU, GPU, VRAM, driver and graphics API capabilities are not yet recorded. See [Reference Hardware](../architecture/REFERENCE_HARDWARE.md); that file remains the hardware source of truth.

## 2. Core product principle

> **Mirai owns the Artist's intent and scene description. A renderer consumes that intent and turns it into an image.**

The renderer must not become the owner of mesh topology, morph state, rigging, skinning, SubD state, undo/redo or scene-editing operations.

Mirai's evaluated production result remains authoritative. A Lookdev renderer must display the visible evaluated form, not silently calculate a second version of the character.

This is the most important protection against a split-brain application where the model looks different in modelling, Morph, Rigging and Lookdev.

## 3. Two visual contexts, not one overloaded viewport

### 3.1 Modelling Worklight

The existing Worklight exists to make form and topology readable during modelling. It is deliberately lightweight and has its own Artist decisions.

Current foundation:
- Production viewport in **src/viewport/**.
- **GLRenderStore** with GLSL 330 core shaders.
- Key / Fill / Ambient Worklight and camera/world light space.
- Per-object base colour, specular and glossiness.
- UV texture display.
- Viewport overlays, wire, selection, hover and GPU picking.

The existing Worklight is not a rendering system. In the earlier Viewport Shading Research, shadow maps were rejected specifically for the modelling Worklight, and MatCap was rejected for that Worklight. Those decisions must not be broadened into a rejection of shadows or image-based lighting in a separate Lookdev / Rendering context.

Do not rewrite or quietly expand AD-024 to turn the Worklight into a scene-lighting system.

### 3.2 Lookdev Studio

A distinct visual context should provide a simple virtual character studio:

- Neutral, adjustable background.
- A few repeatable lighting setups: portrait, soft studio, dramatic key/rim, neutral inspection.
- Environment image / HDRI lighting where supported.
- Artist-controlled key, fill and optional rim lights.
- Camera, focal length and exposure controls.
- Material presets and a small set of meaningful controls.
- Live display of current Morph and Rigging results.
- A final-render action using the same scene and material intent.

The Lookdev context may reuse the existing viewport window, camera, mesh draw infrastructure, overlays and GPU context. It should not require a second application window or a second model-editing system.

## 4. Artist-facing material system

Start with a compact, named material vocabulary, not a general-purpose node editor.

Possible presets:
- Creature Skin
- Wet Skin
- Sclera
- Iris
- Cornea
- Teeth
- Mouth Interior
- Generic Organic
- Hard Surface

The Artist should primarily adjust visually meaningful properties: colour, roughness, reflection strength, normal/detail influence, translucency/subsurface amount where available, and material-specific controls such as iris contrast or cornea clarity.

The renderer may use more sophisticated parameters internally. Raw BRDF coefficients, sampling controls, ray depths, shader implementation switches and hundreds of technical settings belong in a separate diagnostic/advanced layer, not the default Artist workflow.

### Material semantics and compatibility

A future material specification should use familiar, documented meanings and map to more than one rendering backend. Khronos glTF metallic-roughness, OpenPBR and MaterialX are useful references for the vocabulary and interchange boundary; they are not a requirement to adopt a large node-graph system immediately.

The current **core.ObjectMaterial** is intentionally much simpler: base colour, specular and glossiness, persisted per object. Do not silently reinterpret those legacy values as PBR roughness / IOR / metallic values. Any future extension needs explicit defaults, migration rules and compatibility tests.

## 5. Visual priorities and feasible technique families

The technology assessment and sources live in [Rendering Technology Research](../research/RENDERING_TECHNOLOGY_RESEARCH.md). The following is the proposed order for Mirai, not a claim that the effects already exist.

### 5.1 Eyes — first visual target

Treat the eye as a small layered character asset, not a single coloured sphere.

Logical components:
1. Sclera with a slightly warm/off-white colour and controlled roughness.
2. Iris with radial detail and a clearly defined pupil.
3. Cornea with a curved surface and strong, smooth specular reflection.
4. Eyelids, lid margins and tear line with their own geometry/material transitions.
5. Optional moisture layer or tear-film treatment if it proves visually valuable and robust.

Realtime baseline:
- Separate geometry/material assignments where the asset supports them.
- Fresnel-aware specular response.
- Environment reflection from a cubemap or equivalent prefiltered environment.
- Direct light highlights.
- A robust opaque / low-transparency fallback for the legacy GPU.

Do not require physically correct multi-layer refraction or multiple transparent eye shells for the first working result. The characteristic cornea highlight and the iris depth are the first success criteria.

Final render:
- Allow physically correct dielectric interfaces, refraction and higher-quality sampling when the selected backend supports them.

### 5.2 Reflections

A useful character renderer needs more than a single Blinn–Phong highlight.

Proposed progression:
- Direct specular highlight from real scene lights.
- Image-based specular reflection from a studio environment.
- Prefiltered environment levels so rough surfaces blur reflections and smooth corneas retain sharp highlights.
- A consistent Fresnel / microfacet model as the common semantic target.

A low-order Spherical Harmonics representation is suitable for broad diffuse irradiance; it is not a replacement for sharp reflections. Keep diffuse environment lighting and specular environment reflection as separate parts of the design.

### 5.3 Skin and organic surfaces

Skin realism is a combination of several signals, not a single “skin shader” switch:

- Base colour with spatial variation.
- Roughness variation.
- Fine and medium-scale normal/detail maps.
- Controlled specular response.
- Soft diffuse falloff and subtle backlighting.
- Subsurface scattering at a level appropriate to the backend.
- Good lighting, colour management and well-authored geometry.

Realtime baseline should begin with a restrained diffuse/wrap or back-light approximation and good roughness/specular response. A cheap approximation must not blur away the sculpted detail.

More advanced real-time SSS (screen-space blur, thickness-aware or multi-pass approximations) is optional and should be measured. A high-quality offline backend can use physically based volume scattering / random walk where appropriate.

### 5.4 Light, shading and shadows

Proposed Lookdev lighting:
- Key and Fill are the first controllable lights, extending the already familiar Worklight vocabulary.
- Optional Rim / Back light as a separate control.
- Environment illumination for broad fill and reflections.
- A small number of intentional, reproducible studio rigs.

Proposed shadow progression:
1. No cast shadows in the earliest eye-only shader experiment.
2. One shadow-casting key light with a conservative shadow map.
3. Percentage-closer filtering (PCF) or another measured filter for softer edges.
4. Additional lights / higher-quality shadowing only on hardware where they earn their cost.

Contact shadows, directional occlusion and cast shadows solve different problems. Screen-space AO can help contact/readability but must not be presented as full global illumination. Shadow maps belong to the future Lookdev context even though they were rejected for the lightweight modelling Worklight.

### 5.5 Environment lighting and Spherical Harmonics

Spherical Harmonics (SH) are a compact representation of directional data on a sphere. They are not a renderer and do not themselves create reflections, cast shadows or full global illumination.

For Mirai, distinguish:
- **Environment SH:** a few coefficients approximate low-frequency diffuse environment irradiance. Three bands / nine coefficients per colour channel are a practical candidate for diffuse lighting.
- **Directional visibility / SH occlusion:** coefficients describe which directions are blocked at a surface point. Combining this with incoming environment light gives direction-aware ambient occlusion and better diffuse environment response.
- **Specular environment reflection:** needs a separate environment-reflection solution such as a cubemap / prefiltered cubemap; low-order SH cannot preserve sharp eye highlights.

Recommendation:
- Keep low-order diffuse SH as a candidate for the realtime Lookdev baseline if an environment-lighting test demonstrates value.
- Do not implement a Wētā/PantaRay-scale per-point directional-occlusion cache in the first renderer milestone. Its expensive precomputation, cache storage and invalidation for changing/deforming characters are disproportionate until an actual quality/performance need is measured.

## 6. Proposed architecture boundary

This is a conceptual boundary to validate against current code before implementation. Names are responsibilities, not instructions to create these exact classes.

**Production Core / evaluated scene**
- Owns mesh, topology, object transforms, morphs, rigging, skinning and SubD state.
- Supplies the final visible/evaluated geometry and stable object/material identity.

**Lookdev Scene Adapter**
- Reads the evaluated result and Lookdev view state.
- Converts it to render-facing data without writing back into Core.
- Tracks dirty causes: geometry/deformation, object transform, material, texture, light, environment and camera.
- Uses the existing surface-provider / cage-source / RenderMesh pathways where they fit; audit before creating parallel infrastructure.

**Realtime backend**
- First candidate is a measured extension of the existing OpenGL 3.3 Production viewport path, not a brand-new engine by default.
- Existing **Viewport**, **RenderMesh**, **GLRenderStore**, **light_rig.py**, **material.py** and texture display are candidate infrastructure.
- Add Lookdev-specific passes and materials only behind explicit boundaries so Worklight and modelling overlays remain stable.

**Material and lighting semantics**
- One compact scene/material description with explicit units, colour spaces and parameter meanings.
- Backend-specific implementations may approximate the same intent differently.
- A feature-support report makes differences visible rather than silently pretending both backends are identical.

**Final Render Job**
- Takes an immutable snapshot of the evaluated scene, materials, textures, lights, environment, camera and render settings.
- Does not modify the working scene or history.
- Can first export to an external renderer process.
- Reports progress, completion, errors and output paths back to Mirai.

**Output**
- Final image formats should include a high-dynamic-range option such as OpenEXR when the export pipeline is ready.
- Colour transforms should be explicit and reproducible.
- Multi-channel AOVs (for example beauty, depth, normal, object/material IDs) are a later useful addition, not a P0 requirement.

## 7. Automatic quality without taking control away from the Artist

Capability detection and performance adaptation are separate:

**Capability detection** determines which features are actually available: OpenGL/GLSL version, extensions, shader compilation, texture limits, framebuffer formats, depth formats and memory allocation results.

**Runtime adaptation** observes actual frame cost and memory pressure. It may reduce internal render resolution, shadow-map resolution, optional filtering or secondary effects.

The Quality Manager must never reduce:
- Mesh or sculpt resolution.
- Morph weights or deformation accuracy.
- Topology precision.
- Selection / picking correctness.
- Artist-authored material values.

Proposed controls:
- Auto (default on first run).
- Draft / Interactive / High Lookdev.
- Manual override per effect where useful.
- A diagnostic readout of the active tier and why a feature is unavailable.

Do not select a tier from a GPU name alone. Do not promise a frame rate before measuring on both actual machines. The main PC must be added to the hardware factsheet before the dual-PC target can be verified.

## 8. What is realistic — and what should not be promised

| Capability | Legacy GL 3.3 class | Better main PC | Proposed treatment |
|---|---|---|---|
| Diffuse + direct specular lighting | Realistic | Easy | Early |
| PBR-inspired microfacet / Fresnel response | Realistic with careful shader scope | Easy | Early, subset |
| Cubemap environment reflections | Realistic | Easy | Early |
| Diffuse SH environment lighting | Realistic candidate | Easy | Early experiment |
| One shadow map + modest filtering | Plausible, must measure memory and cost | Easy | Later realtime slice |
| Directional SH occlusion cache | Technically possible but precompute/cache cost unknown | More plausible | Research only until justified |
| Approximate skin translucency / backscatter | Plausible, carefully limited | Easier | After eyes |
| Multi-pass / screen-space SSS | Possible but budget-sensitive | Plausible | Optional quality tier |
| Physically based random-walk SSS | Not a sensible interactive legacy target | Offline plausible | Final backend |
| Multi-bounce path tracing / complex refraction | Not a realtime legacy target | Offline plausible | External final backend first |
| Spectral path tracing | Out of scope for Mirai realtime | Possible through external renderer | Do not implement in Mirai core |

“Possible” does not mean “already benchmarked”. Actual feasibility depends on mesh size, render resolution, shader implementation, driver and the specific reference hardware.

## 9. Staged delivery

### P0 — Current-state and hardware audit
- Map the actual viewport draw path and its ownership boundaries.
- Confirm the existing shader/context and measured reference-PC capabilities.
- Record the main PC hardware and runtime capabilities.
- Measure existing draw cost and memory with a reproducible test scene.
- Decide the smallest safe extension seam.
- No production renderer implementation yet.

### P1 — Disposable eye / lookdev proof
- A standalone test scene with sclera, iris, pupil and cornea.
- One controllable key light, neutral background and environment reflection.
- Compare simple specular, Fresnel and cubemap approaches.
- Include an opaque fallback.
- Run on both PCs and document image quality, frame timing and memory.
- No changes to Core, morph, rigging, scene format or production viewport.

### P2 — Production integration
- Consume the already evaluated visible geometry.
- Reuse existing viewport infrastructure where validated.
- Add a separate Lookdev state and preserve the modelling Worklight.
- Keep selection, overlays, GPU picking, camera navigation and modelling tools working.
- Add capability-based quality tiers and a manual override.
- Regression and performance gates before promotion.

### P3 — Lighting, skin and shadows
- Add controlled studio lights, diffuse environment, SH if proven useful.
- Add shadow mapping and filtering behind quality controls.
- Expand the material vocabulary and skin approximation.
- Evaluate eye transmission separately from the stable legacy fallback.

### P4 — Final render bridge
- Compare at least two external renderers with the same representative Gollum scene.
- Validate material mapping and colour management.
- Export an immutable evaluated scene snapshot.
- Choose an external backend based on reproducibility, quality, reliability, compatibility and maintenance — not feature count alone.

### P5 — Reconsider custom offline rendering only with evidence
A custom offline renderer is justified only if the external route has a concrete, recurring limitation that Mirai cannot reasonably solve at the interchange boundary. Do not start by building a universal path tracer.

## 10. Non-goals

- Replacing the existing modelling Worklight.
- Replacing the production viewport wholesale.
- A universal V-Ray / Arnold / Blender feature clone.
- A general node graph before a small semantic material model proves insufficient.
- A duplicate mesh, morph or skinning evaluation path.
- Implementing global illumination, spectral transport or complex SSS from scratch as an initial milestone.
- Copying code from GPL renderers into Mirai. Study, benchmark or invoke such applications externally unless licensing is explicitly reviewed.

## 11. Decision gates

The following remain open until evidence exists:
- Exact OpenGL capability and hardware details of the main PC.
- Whether the existing GLRenderStore is the right long-term realtime backend or only a transitional backend.
- The minimum PBR material vocabulary and migration strategy from ObjectMaterial.
- Whether the first environment source is a fixed studio cubemap, HDRI, or both.
- Whether SH environment lighting materially improves Gollum compared with a small multi-light setup.
- Shadow-map resolution/filter budgets on the legacy PC.
- The most useful external final renderer.
- The scene interchange representation and colour-management contract.

**Promotion rule:** This document is a design proposal. It does not authorise code changes, new Core ownership, a scene-format change or a new key binding. A technical audit and a measured prototype must precede an Architecture Decision and production implementation.
