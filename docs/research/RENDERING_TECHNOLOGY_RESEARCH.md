# Rendering Technology Research — Character Lookdev, Lighting and Final Images

**Status:** Research synthesis — no implementation decision  
**Date:** 2026-11-11  
**Scope:** Realistic character presentation for Mirai, with Gollum as the first reference asset  
**Product requirements:** [Rendering Vision](../design/RENDERING_VISION.md)  
**Existing baseline:** [Reference Hardware](../architecture/REFERENCE_HARDWARE.md), [AD-024](../architecture/AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md), [Viewport Shading Research](viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md)

This document separates repository facts, externally sourced facts, interpretations and unknowns. It is a research map, not an instruction to implement every technique listed.

---

## 1. Research questions

The target is the most believable image of an organic character that Mirai can reasonably produce:

- How does light wrap around and reveal the face?
- How do direct light, diffuse environment light and cast/contact shadows interact?
- How should reflections respond to roughness and viewing angle?
- How can Gollum's eyes look wet, deep and alive?
- How can skin retain sculpted detail while exhibiting a subtle sense of subsurface light?
- Which parts should be interactive on old hardware and which should be reserved for final rendering?
- Which established standards, renderers and open-source tools can Mirai reuse or use as benchmarks?

The objective is not maximum feature count. It is a predictable visual system with an Artist-facing vocabulary that hides low-level renderer complexity.

## 2. Existing Mirai baseline — verified in the repository

### 2.1 Hardware facts

The current reference machine is documented in [REFERENCE_HARDWARE.md](../architecture/REFERENCE_HARDWARE.md):

| Component | Recorded value |
|---|---|
| CPU | Intel Core 2 Quad Q9550, 2.83 GHz, 4 cores |
| RAM | 8 GB |
| GPU | NVIDIA GeForce 9800 GTX / GTX+ |
| Reported VRAM | 481 MB |
| OS | Windows 10, 64-bit |
| Measured GL version | 3.3.0 |
| Measured renderer string | GeForce 9800 GTX/9800 GTX+/PCIe/SSE2 |

The production shaders use GLSL 330 core. This is already running on the reference machine. Do not redesign the baseline around OpenGL 2.1 just because the GPU is old; the measured runtime is OpenGL 3.3.

The main PC is not yet described in the hardware factsheet. Its actual API, driver, VRAM and CPU must be captured before dual-machine claims are verified.

Existing viewport measurements in the hardware document are useful but must not be mistaken for a realistic shading benchmark: orbit/pan on the 21,875-vertex Gollum mesh measured about 1.2 ms per step and GPU draw about 0.56 ms (wire about 1.15 ms). Picking, by contrast, was much slower. These numbers describe the current viewport path, not new shadowing, reflections, SSS or final rendering.

### 2.2 Existing renderer and materials

Verified source locations:
- **src/viewport/gl_render_store.py** — existing GLSL 330 draw path and shader variants.
- **src/viewport/render_mesh.py** — render-mesh and buffer ownership.
- **src/viewport/viewport.py** — thin viewport façade combining render mesh, camera binding and overlays.
- **src/viewport/light_rig.py** — current Key / Fill Worklight and its parameter model.
- **src/viewport/material.py** — current viewport material packet and specular function.
- **src/mirai/viewport/look_controls.py** — current Worklight / object material control rows.
- **src/mirai/viewport/display.py** — display state.

Current material behaviour:
- Per-object base colour, specular and glossiness.
- Current specular is Blinn–Phong, not a full physically based BRDF.
- Specular and glossiness are deliberately independent artist controls; the highlight is not energy-normalised.
- Current material packet also carries the Fill specular contribution.
- Face-corner UVs and object texture display already exist (AD-026).

Current lighting behaviour:
- Key and Fill are real directional lights in the Worklight rig, with camera/world space options, colour temperature, intensity and wrap controls.
- The Worklight is global viewport state; AD-024 says it is not scene lighting, not stored as scene data and not in Undo history.
- The current Worklight is designed for modelling form readability, not final image rendering.

**Important boundary:** the older research decision rejecting Shadow Maps applies to the modelling Worklight. It does not reject shadow maps for a separate Lookdev / Rendering mode. Keep those product contexts separate.

### 2.3 Existing architecture that should be reused or assessed first

The viewport already has a meaningful separation:
- **Viewport** is the integration façade.
- **RenderMesh / GLRenderStore** own rendering buffers and GL draws.
- Mirai-side surface providers can supply evaluated display surfaces (including SubD and deformed surface paths).
- The cage-source path lets the viewport display/pick against a shown evaluated cage without writing back into Core.
- Selection, hover, wire, face and tool overlays are separated from the base surface draw.
- Per-object material binding is already supported.

These are valuable seams. The first renderer audit should establish how the existing evaluated surface and object materials can be consumed. A new renderer should not reimplement morph, skinning, SubD, selection or picking.

### 2.4 Current design constraints

[AD-024](../architecture/AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md) deliberately keeps a small **ObjectMaterial** data model: base colour, specular and glossiness. A future PBR model must not reinterpret those values silently.

The existing Worklight is a view/artist aid. A Lookdev Studio needs its own scene-level light, environment, camera and background state. This is a future design problem, not something to smuggle into AD-024.

## 3. Findings already established in this conversation

These are synthesis notes from the research and design discussion on 2026-11-11; they are not evidence of implemented functionality.

1. Mirai's desired direction is a focused Artist-first renderer, not a clone of V-Ray / Arnold / Cycles with hundreds of low-level controls.
2. The preferred high-level split is interactive Lookdev plus a high-quality final-render path.
3. Both hardware classes are targets; the old PC requires a deliberately conservative baseline and the new main PC should unlock higher quality automatically. Main-PC specs remain unknown.
4. The same material and light intent should feed both paths, but identical parameters do not guarantee pixel-identical results; each backend may approximate differently.
5. The renderer should consume the current evaluated visible surface and must not own geometry, topology, morphs, skinning, history or selection.
6. The first visual proof should focus on Gollum's eyes: sclera, iris, pupil, cornea, reflections and eyelid/tear-line transitions.
7. A separate, small Artist-facing material vocabulary and a few repeatable studio light rigs are preferable to an unrestricted shader graph at the start.
8. A high-quality external renderer is the sensible first final-render route. A custom offline renderer is not justified without evidence that an external backend creates a concrete limitation.
9. Spherical Harmonics are a compact lighting/visibility representation, not a renderer or a universal replacement for reflection and shadow calculations.

## 4. Studio reference: Wētā FX

### 4.1 Manuka and Gazebo — two uses, a coherent look

Wētā's public material describes [Manuka](https://www.wetafx.co.nz/research-and-tech/technology/manuka) as its physically based production renderer. The American Cinematographer's 2023 Avatar: The Way of Water article reports that Manuka was developed to work with Gazebo; lighting authored in Gazebo could transfer to Manuka with very similar appearance because the two shared reflectance models based on real-world lighting.

This is the strongest workflow lesson for Mirai:

- Fast and final render paths can be different implementations.
- Their material semantics and light intent should be aligned deliberately.
- The Artist should not have to rebuild the look from scratch for final output.
- Approximation differences should be expected and measured, not hidden.

Sources:
- [Wētā FX — Manuka](https://www.wetafx.co.nz/research-and-tech/technology/manuka)
- [The American Society of Cinematographers — Total Immersion for Avatar: The Way of Water](https://theasc.com/article/avatar-the-way-of-water/)
- [fxguide — Manuka: Weta Digital's new renderer](https://www.fxguide.com/fxfeatured/manuka-weta-digitals-new-renderer/)

This is a workflow reference, not a prescription to reproduce Wētā's internal software or production infrastructure.

### 4.2 Spherical Harmonics and directional occlusion

Wētā describes Spherical Harmonics as a data representation of light interaction with surfaces. Its official page says the system stores information about individual light contributions and directional occlusion and that it is important to its hair and eye work.

The detailed 2013 fxguide explanation makes several distinctions especially relevant to Mirai:

- SH represents a directional function over a sphere, somewhat like a spherical frequency representation.
- Incoming environment illumination can be represented with SH coefficients.
- Directional visibility / occlusion at a point can also be represented with SH coefficients.
- Combining incoming light and directional visibility gives a direction-aware diffuse lighting result.
- The SH data can be cached and reused; it is not a cached final image.
- Low-order SH contains broad diffuse information, not sharp high-frequency environment details.

For diffuse irradiance under distant environment illumination, Ramamoorthi and Hanrahan showed that the first nine coefficients (three bands) provide a very compact approximation with about 1% average error for their diffuse-irradiance problem. This statement must not be misread as “nine coefficients accurately reproduce all reflections and all lighting”.

Wētā's larger system is much more than evaluating nine numbers in a shader. Its historical PantaRay approach precomputed directional occlusion using large-scale GPU ray tracing, then stored SH visibility data for reuse. The expensive part is producing and maintaining the cache; the later combination is comparatively cheap.

**Mirai assessment:**
- A small SH environment probe for diffuse lighting is realistic to prototype on the GL 3.3 baseline.
- A per-surface-point directional-occlusion cache is a separate, ambitious research item.
- A deforming face creates cache invalidation questions: morphs, jaw/face rigging, topology edits and changing nearby geometry can invalidate visibility.
- SH is not the solution for sharp specular eye reflections; use a separate specular environment representation.

Sources:
- [Wētā FX — Spherical Harmonics](https://www.wetafx.co.nz/research-and-tech/technology/spherical-harmonics)
- [fxguide — The science of spherical harmonics at Weta Digital](https://www.fxguide.com/fxfeatured/the-science-of-spherical-harmonics-at-weta-digital/) (Mike Seymour, 2013)
- [Ramamoorthi & Hanrahan — An Efficient Representation for Irradiance Environment Maps](https://graphics.stanford.edu/papers/envmap/) (SIGGRAPH 2001)
- [NVIDIA Research — PantaRay: Fast Ray-traced Occlusion Caching of Massive Scenes](https://research.nvidia.com/publication/2010-07_pantaray-fast-ray-traced-occlusion-caching-massive-scenes)

## 5. Rendering technique map

### 5.1 Direct illumination and physically based surface response

A practical realtime foundation is a limited microfacet PBR model:
- Diffuse response for non-metal surfaces.
- Fresnel response for view-angle-dependent reflection.
- GGX microfacet specular distribution.
- A visibility / geometry term and energy-conscious combination.
- Roughness controls highlight width and environment reflection blur.
- Normal maps add medium/fine surface detail without forcing all detail into geometry.

This is substantially more coherent than extending the current independent Blinn–Phong specular and glossiness values indefinitely. It is not necessary to implement every PBR lobe or arbitrary material graph.

References:
- [Khronos — Physically Based Rendering in glTF](https://www.khronos.org/gltf/pbr/)
- [Google Filament — real-time PBR implementation](https://github.com/google/filament)
- [MaterialX PBR Specification 1.39](https://github.com/AcademySoftwareFoundation/MaterialX/blob/main/documents/Specification/MaterialX.PBRSpec.md)

### 5.2 Environment lighting and reflections

Use separate strategies for diffuse and specular environment response:

**Diffuse environment**
- Low-order SH is a good candidate for broad diffuse irradiance.
- A simple multi-light rig remains valuable for explicit artist control and debugging.
- Compare SH with the existing Key + Fill setup; do not assume it is automatically better.

**Specular environment**
- Use a cubemap or equivalent environment texture for directional reflection.
- Pre-filtered mip levels (or another roughness-aware prefilter) allow rough materials to blur the reflected environment.
- A small BRDF lookup / approximation can be considered if it measurably improves the result.
- Cornea needs a clean, high-quality highlight; it should not inherit the blur of low-order diffuse SH.

Legacy feasibility: cubemap sampling and ordinary texture-based techniques fit the current OpenGL 3.3 baseline in principle. Actual VRAM use, filtering quality and speed must be measured at the intended viewport resolution.

### 5.3 Eyes

The eye should be modelled and shaded as separate optical/geometry layers where the character asset supports it:
- Sclera: subtle off-white tint, non-perfectly smooth response.
- Iris: dedicated texture and geometry depth where available.
- Pupil: distinct dark region and correct shape.
- Cornea: curved dielectric surface with strong Fresnel reflection.
- Eyelid margin / tearline: important wet/dry boundary and contact transition.
- Optional tear film: later experiment only if it earns its complexity.

Realtime priority:
1. Correct geometry and layering.
2. A stable environment reflection / specular highlight.
3. Iris detail and pupil readability.
4. Robust depth sorting and an opaque fallback.
5. Only then evaluate transparent shells, refraction and extra passes.

Do not start by requiring physically correct refraction through several transparent layers on the 9800 GTX.

### 5.4 Skin and subsurface scattering

Skin appearance depends on colour, roughness, normal detail, specular response, light size/direction and subsurface transport.

Three useful levels:

| Level | Method | Use |
|---|---|---|
| 1 | Diffuse + roughness/specular + detail maps | First useful realtime skin |
| 2 | Wrap diffuse / backscatter / thickness-aware approximation | Realtime Lookdev quality tier |
| 3 | Screen-space or multi-pass SSS approximation | Optional; must be measured for artifacts and cost |
| 4 | Physically based volumetric / random-walk SSS | High-quality offline final rendering |

Blender's Principled BSDF documentation is a useful comparison: it distinguishes the Christensen–Burley approximation from Random Walk, and documents a skin-oriented Random Walk mode. It also notes that true volumetric random walk works best on closed meshes; holes and overlapping faces can cause problems. This is relevant to character asset preparation, not just renderer implementation.

Sources:
- [Blender Manual — Principled BSDF](https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/principled.html)
- [OpenPBR Surface specification and reference implementation](https://github.com/AcademySoftwareFoundation/OpenPBR)

### 5.5 Shadows and occlusion

Keep these techniques distinct:

- **Cast shadows:** light blocked by another object; commonly shadow maps in realtime and ray tracing in offline rendering.
- **Contact shadow / local occlusion:** local darkening around contact, cavities and folds; screen-space AO or other approximations can assist.
- **Directional environment occlusion:** visibility varies by incoming direction; SH occlusion is one possible representation.
- **Global illumination:** indirect light bouncing between surfaces; not equivalent to AO.

A single key-light shadow map with modest PCF filtering is a plausible later realtime experiment on GL 3.3. Its costs include an extra depth pass, a depth texture, filtering and possible bias/acne issues. Start with one shadow-casting light; do not immediately add cascades or many shadow-casting area lights.

The old Worklight shadow-map rejection was a scope decision for modelling form readability, not a technical finding that shadow maps cannot work on the legacy GPU.

### 5.6 Color management and image pipeline

Realistic light requires a consistent linear-light calculation and an intentional display transform. Otherwise materials and lighting may look different due to uncontrolled gamma / display conversion rather than shader quality.

Useful open standards/tools:
- [OpenColorIO](https://github.com/AcademySoftwareFoundation/OpenColorIO) — colour management framework designed for VFX and animation, with ACES compatibility and use across applications.
- [OpenEXR](https://github.com/AcademySoftwareFoundation/openexr) — high-dynamic-range, scene-linear image format widely used in film/VFX; supports floating-point pixels and multi-part / multi-channel images.
- [OpenImageIO](https://github.com/AcademySoftwareFoundation/OpenImageIO) — robust image/texture I/O, image cache and filtered texture lookups for VFX applications.

These are pipeline components, not renderers. They are candidates for later image I/O / texture / colour-management work; do not bundle all three into the first eye prototype.

## 6. External software and open-source references

The categories below distinguish “learn from”, “benchmark against”, and “reuse / integrate”. A project being open source does not automatically make it a good in-process dependency for Mirai.

| Project | What it offers | Mirai value | Limitation / caution |
|---|---|---|---|
| **Wētā Manuka + Gazebo** | Production final renderer + interactive rendering workflow; shared reflectance models | Workflow benchmark for Lookdev-to-final consistency | Proprietary studio systems; not a reusable package |
| **Blender Cycles** | Mature offline path tracer; Principled BSDF; skin SSS modes | Best practical visual benchmark and likely first external final-render candidate | Heavy application/export boundary; GPL code must not be copied into Mirai |
| **appleseed** | Open-source physically based GI renderer; standalone CLI, C++/Python APIs, OSL, SSS, OCIO | Strong candidate for a controlled external-backend evaluation | Releases/builds and CPU instruction compatibility need verification; current release list includes beta releases |
| **Mitsuba 3** | Research-oriented retargetable renderer; scalar CPU, LLVM and CUDA variants; RGB/spectral transport | Excellent technical reference for light transport, materials and controlled experiments | Research system with advanced build/runtime requirements; not an Artist-facing drop-in |
| **pbrt-v4** | Modern reference renderer/book; spectral, volumetric and GPU rendering | Excellent source of algorithms and explanations | Educational/reference renderer, not a packaged Artist workflow or easy plugin |
| **Google Filament** | Modern realtime PBR, Cook–Torrance, IBL, shadows, approximate translucency | High-quality code and architecture benchmark | Desktop OpenGL backend requires 4.1+, above the legacy PC's measured GL 3.3; not the shared baseline |
| **MaterialX / OpenPBR** | Open material graph and surface-shading standards | Vocabulary, material semantics, future interchange target | Too broad as a first Mirai node system; implement only a measured subset |
| **glTF PBR** | Compact, widely used material model and asset interchange | Good initial parameter vocabulary and export bridge | Does not define Mirai's full character SSS / eye model |
| **OpenColorIO** | VFX colour management and transforms | Later shared colour pipeline | Not needed for the first shader proof |
| **OpenImageIO** | Image / texture reading, caching and filtering | Later texture pipeline if current code needs it | C++ dependency/build footprint and old CPU support need testing |
| **OpenEXR** | HDR scene-linear image storage | Strong final-output format | Image format/library only, not rendering |

### 6.1 Candidate roles

**Blender Cycles — visual reference first.** Render the same Gollum eye/head setup in Cycles using a Principled material, environment, key/fill lighting and a skin SSS option. Capture what the image actually gains from each feature. If the export path is reliable, invoke Blender as a separate process for final images. Avoid copying GPL implementation code into Mirai.

**appleseed — evaluate as an external backend.** Its project describes it as an open-source physically based GI renderer for animation and VFX, with standalone applications, Python/C++ APIs and MIT licensing. Its feature documentation includes SSS, OSL, OCIO, AOVs and image tools. Do not make it the default until a current Windows build, scene import/export, texture path, performance and CPU ISA compatibility have been tested on the intended final-render PC.

**Mitsuba 3 — technical experiments.** The official documentation describes it as a research-oriented forward/inverse light-transport system. Its scalar RGB variant offers a CPU path; LLVM and CUDA variants bring optional modern acceleration requirements. Use for controlled comparisons or technical learning, not as the first user-facing integration.

**pbrt-v4 — reference implementation.** Use its book, user guide and source to understand physically based sampling, materials, reflection, volumes and spectral rendering. It is not the first candidate for a turnkey Artist workflow.

**Filament — realtime reference, not legacy dependency.** It demonstrates a comprehensive modern realtime PBR feature set. But the desktop OpenGL backend requires 4.1+, so it cannot serve as the same backend on the 9800 GTX. It may be worth measuring on the new PC only if a separate modern backend is ever justified; that would increase maintenance and preview consistency costs.

### 6.2 Material standards

- **glTF metallic-roughness:** compact, portable baseline for base colour, metalness, roughness and normal maps; extensions add clearcoat, transmission and other features.
- **OpenPBR:** broader surface model intended for VFX and feature animation; standard hosted by the Academy Software Foundation, with a MaterialX reference implementation.
- **MaterialX:** node-graph interchange and standardized shading semantics, including OpenPBR and other familiar surface models.

Recommendation: take names, parameter meaning and interoperability lessons from these standards. Do not introduce a large general-purpose graph editor until a small named-material system proves insufficient.

## 7. Spherical Harmonics — precise scope

SH is a basis representation for functions on a sphere. It can encode incoming illumination, directional visibility, or other direction-dependent data. It is not a lighting algorithm by itself.

For diffuse irradiance, three bands (nine coefficients per colour channel) are often sufficient because diffuse convolution suppresses high-frequency lighting detail. That result does not hold for mirror-like or sharp specular reflection.

For Wētā's directional occlusion, the expensive process samples visibility from many directions at many points, encodes it in SH and caches it. This is an asset/scene preparation pipeline, not a cheap calculation that simply appears because a shader uses nine coefficients.

Potential Mirai uses, in order:
1. SH environment probe for broad diffuse lighting — a small, testable feature.
2. SH visibility at a small number of static sample points — exploratory.
3. Dense per-surface-point SH visibility cache — defer until a measured need exists and deformation/cache invalidation is understood.

For eyes, retain a separate specular environment map / reflection path.

## 8. What is realistic for Mirai?

| Feature | Legacy interactive GL 3.3 | Main-PC interactive | External final render |
|---|---|---|---|
| Direct diffuse/specular | Yes | Yes | Yes |
| Microfacet / Fresnel subset | Yes, conservative shader | Yes | Yes |
| Environment cubemap reflection | Yes, measure texture cost | Yes | Yes |
| Diffuse SH environment | Likely practical; test | Yes | Optional |
| One shadow map + PCF | Plausible; benchmark memory and frame cost | Yes | Not necessary |
| Approximate skin wrap/backscatter | Plausible | Yes | Optional |
| Multi-pass screen-space SSS | Budget-dependent | More plausible | Better alternatives available |
| Random-walk volumetric SSS | Not a reasonable legacy realtime target | Not assumed realtime | Yes, renderer-dependent |
| Multi-bounce path tracing / complex refraction | No practical target | Dedicated modern GPU may help, not guaranteed | Primary use case |
| Spectral light transport | No | No reason to place in viewport | Available in specialist offline renderers |

“Not a target” is not the same as mathematically impossible. It means the cost/complexity does not fit Mirai's shared old-hardware interactive baseline.

## 9. Open research and validation list

### P0 — Must establish before design is frozen
- [ ] Record main PC CPU, GPU, VRAM, OS, driver and supported GL/Vulkan versions.
- [ ] Capture runtime GL/GLSL/extensions on both PCs.
- [ ] Audit exact viewport lifecycle, GL context ownership, shader compilation and render passes.
- [ ] Confirm the data path for the currently displayed morph + skinned + SubD surface.
- [ ] Measure old-PC baseline frame time, texture memory and buffer memory with a realistic head scene.
- [ ] Identify image/texture file formats already supported and current gamma/colour-space assumptions.

### P1 — Eye/lookdev proof
- [ ] Compare eye geometry: iris placement, cornea curvature, eyelid/tearline construction.
- [ ] Compare Blinn–Phong versus Fresnel/microfacet highlights on the same eye.
- [ ] Compare direct light highlight versus environment cubemap reflection.
- [ ] Measure one transparent cornea layer against an opaque fallback on the legacy GPU.
- [ ] Establish the smallest useful environment resolution and mip chain.
- [ ] Artist review: can the eye read as wet/deep while orbiting and changing expression?

### P2 — Lighting and shadows
- [ ] Compare two-light Key/Fill with an environment-lit studio.
- [ ] Compare SH diffuse irradiance with the current Worklight and a small multi-light rig.
- [ ] Establish shadow-map resolution, depth format, bias and PCF tap budget on the legacy GPU.
- [ ] Test contact shading / AO without halos, dirty creases or loss of sculpted detail.
- [ ] Determine which lights cast shadows and which are purely fill/reflection sources.

### P3 — Skin
- [ ] Compare diffuse/wrap, backscatter and screen-space SSS approximations.
- [ ] Determine whether useful thickness information can be authored or derived for Gollum.
- [ ] Compare against Cycles skin Random Walk and Christensen–Burley output.
- [ ] Test the effects of open boundaries, eye/mouth cavities and overlapping surfaces on offline SSS.

### P4 — Final renderer / interoperability
- [ ] Build one identical Gollum head scene in Cycles and appleseed.
- [ ] Also test Mitsuba or pbrt only for a specific research question, not as an undirected comparison.
- [ ] Test export of evaluated geometry, transforms, UVs, textures, materials, lights, camera and environment.
- [ ] Define colour-space / display-transform handoff and EXR output.
- [ ] Compare backend material differences and document expected Lookdev-to-final deviations.
- [ ] Check current Windows builds, runtime dependencies, CPU instruction requirements and license obligations for the selected versions.

### P5 — Only if justified
- [ ] Determine whether directional SH visibility caching is useful for a deforming head.
- [ ] Investigate cache density, data size, invalidation and reuse across poses.
- [ ] Evaluate OpenColorIO, OpenImageIO and OpenEXR integration where a concrete file/pipeline requirement exists.
- [ ] Consider a custom offline renderer only after a documented limitation of external backends.

## 10. Recommended benchmark scene

Create one small, version-controlled Lookdev test scene rather than comparing renderers on unrelated assets.

It should contain:
- Gollum head with representative eye geometry, eyelids, mouth cavity, nose folds and skin detail.
- A neutral gray sphere and a chrome sphere as lighting/reflection references.
- A small colour chart / neutral card.
- A fixed camera plus a turntable camera.
- One studio environment and one directional key light.
- A key/fill comparison rig.
- Morph states: neutral, blink / eye closure, jaw open, one expressive face target.
- A fixed viewport resolution and a fixed final output resolution.

Capture:
- Beauty image.
- Diffuse-only, specular-only and normal diagnostic views if supported.
- Shadow / occlusion diagnostic.
- Frame time, GPU memory, RAM and render time.
- Current GPU/driver/API identifiers.
- Exact material/light values and asset revision.

This scene is the common visual oracle for legacy realtime, main-PC realtime and external final rendering.

## 11. Source register

Links were reviewed on 2026-11-11 unless a publication date is stated. Product capability and current project status should be rechecked when selecting a specific version.

### Film / VFX studios
- [Wētā FX — Spherical Harmonics](https://www.wetafx.co.nz/research-and-tech/technology/spherical-harmonics) — official explanation of its SH lighting representation, directional occlusion and importance for hair/eyes.
- [Wētā FX — Manuka](https://www.wetafx.co.nz/research-and-tech/technology/manuka) — official overview of its physically based production renderer.
- [Wētā FX — Physically Based Shading](https://www.wetafx.co.nz/research-and-tech/technology/physically-based-shading) — studio shading principles.
- [American Cinematographer — Total Immersion for Avatar: The Way of Water](https://theasc.com/article/avatar-the-way-of-water/) — 2023 account of Gazebo/Manuka collaboration and transfer of lighting through shared reflectance models.
- [fxguide — The science of spherical harmonics at Weta Digital](https://www.fxguide.com/fxfeatured/the-science-of-spherical-harmonics-at-weta-digital/) — Mike Seymour, 2013; detailed SH / PantaRay historical explanation.
- [fxguide — Manuka: Weta Digital's new renderer](https://www.fxguide.com/fxfeatured/manuka-weta-digitals-new-renderer/) — 2014; development context for Gazebo/Manuka compatibility.

### Papers / foundational techniques
- [Ramamoorthi & Hanrahan — An Efficient Representation for Irradiance Environment Maps](https://graphics.stanford.edu/papers/envmap/) — SIGGRAPH 2001; low-order SH for diffuse irradiance.
- [NVIDIA Research — PantaRay: Fast Ray-traced Occlusion Caching of Massive Scenes](https://research.nvidia.com/publication/2010-07_pantaray-fast-ray-traced-occlusion-caching-massive-scenes) — directional occlusion cache and GPU ray tracing.
- [Fascione et al. — Manuka: A Batch-Shading Architecture for Spectral Path Tracing in Movie Production](https://doi.org/10.1145/3182161) — 2018 production renderer architecture paper.
- [Physically Based Rendering, 4th edition](https://www.pbrt.org/) — theory and implementation reference, with modern spectral / volumetric / GPU topics.

### Realtime / material standards
- [Google Filament repository](https://github.com/google/filament) — real-time PBR implementation; desktop GL 4.1+ backend requirement is incompatible with the reference PC's measured GL 3.3.
- [Khronos glTF PBR](https://www.khronos.org/gltf/pbr/) — compact PBR material semantics and extensions.
- [OpenPBR](https://github.com/AcademySoftwareFoundation/OpenPBR) — ASWF surface-shading standard and reference implementation.
- [MaterialX](https://github.com/AcademySoftwareFoundation/MaterialX) — node-graph material interchange and PBR specification.
- [OpenSubdiv](https://github.com/PixarAnimationStudios/OpenSubdiv) — adjacent reference for efficient subdivision surface evaluation; not a renderer replacement.

### External renderers
- [Blender Cycles — Principled BSDF manual](https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/principled.html) — reference for layered materials and skin SSS methods.
- [appleseed repository](https://github.com/appleseedhq/appleseed) — MIT-licensed physically based GI renderer for animation/VFX, with standalone and API options.
- [appleseed feature documentation](https://appleseed.readthedocs.io/en/latest/features/features.html) — SSS, OSL, OCIO, AOV and performance overview.
- [Mitsuba 3 documentation](https://mitsuba.readthedocs.io/en/latest/) — research-oriented renderer and current build/runtime requirements.
- [pbrt-v4 resources](https://www.pbrt.org/resources) — source, user guide and book links.

### Image / colour pipeline
- [OpenColorIO](https://github.com/AcademySoftwareFoundation/OpenColorIO) — colour management for VFX/animation with ACES compatibility.
- [OpenImageIO](https://github.com/AcademySoftwareFoundation/OpenImageIO) — VFX image and texture input/output, cache and filtering.
- [OpenEXR](https://github.com/AcademySoftwareFoundation/openexr) — scene-linear HDR image format and multi-channel image storage.

---

## 12. Reading order

1. Wētā SH official page, then the fxguide SH article — understand data representation versus the costly cache pipeline.
2. American Cinematographer / Manuka sources — understand the interactive-to-final workflow and shared reflectance models.
3. glTF PBR and OpenPBR — define a compact, portable material vocabulary.
4. Filament — study a modern realtime PBR implementation, while respecting its desktop GL 4.1 requirement.
5. Blender Cycles — visual benchmark for layered materials and skin.
6. appleseed / Mitsuba / pbrt — evaluate only against a concrete final-render or research question.

**Research conclusion:** Mirai can reasonably target convincing character Lookdev on the old GL 3.3 PC by carefully choosing direct lighting, a compact PBR subset, environment reflections and measured shadowing. A higher-end offline renderer should initially supply true path tracing and advanced SSS. The key is to share material/light intent and the evaluated scene, not to force both backends to use the same rendering algorithm.
