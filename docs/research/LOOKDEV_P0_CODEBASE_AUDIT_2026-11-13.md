# Lookdev P0 — Renderer / Lookdev Codebase Audit

**Status:** Discovery / audit — **no decision, no production code changed, no commit.** This is P0 of
[RENDERING_VISION.md §9](../design/RENDERING_VISION.md); it prepares P1 (disposable eye proof) and the decisions in §8.
**Date:** 2026-11-13
**State audited:** `origin/main` @ `8e7da7a` (O3 stage 2 measured on the reference PC). The working branch
`claude/mirai-renderer-lookdev-audit-92e9rl` was at the same commit with a clean tree when the audit began. The local
`main` ref was stale (`3a96ee3`) and was not used.
**Scope:** how the current production viewport could become a character Lookdev workflow without changing the
modelling Worklight, the tools, Morph, Rigging, Skinning or SubD. The pending O4 decision (native kernels, AD-032 §12,
audit D2) is **out of scope** and is not discussed beyond what it means for the frame budget.
**Inputs read first:** [RENDERING_VISION.md](../design/RENDERING_VISION.md),
[RENDERING_TECHNOLOGY_RESEARCH.md](RENDERING_TECHNOLOGY_RESEARCH.md),
[VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md](viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md),
[AD-024](../architecture/AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md),
[AD-032](../architecture/AD-032-PACKED-ARRAYS-NUMPY.md),
[REFERENCE_HARDWARE.md](../architecture/REFERENCE_HARDWARE.md),
[ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md](deformation/ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10.md) including all
addenda up to O3 stage 2 on the reference PC. Further ADs that bear directly on rendering:
[AD-018](../architecture/AD-018-PRODUCTION-DRAW-BINDING.md) (store contract, Worklight, specular, O2 layout),
[AD-021](../architecture/AD-021-OBJECT-COMPONENT-MODEL.md) (object entries, model matrix, Ghost),
[AD-022](../architecture/AD-022-GPU-PICKING.md) (ID buffer), [AD-023](../architecture/AD-023-INCREMENTAL-TOPOLOGY-SYNC-AND-HISTORY.md)
(slot layout), [AD-025 §18](../architecture/AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) /
[AD-028](../architecture/AD-028-SKELETON-AND-SKINNING.md) (evaluated surfaces), [AD-026](../architecture/AD-026-FACE-CORNER-UVS-AND-TEXTURE.md)
(UVs, textures), [AD-030](../architecture/AD-030-GUI-FRAMEWORK.md) (panels), [AD-REGIONS-01](../architecture/AD-REGIONS-01-FACE-REGIONS-STORAGE.md).

**Evidence labels** (every claim carries one):

| Label | Meaning |
|---|---|
| **VERIFIED IN CODE** | Read in the source at `8e7da7a` (or, where named, in the pyglet 2.1.19 source the reference PC runs). |
| **TESTED** | An automated test exercises it. "TESTED [RPC]" = that test passed on the reference PC (165 GL tests, 2026-11-13); "TESTED [C]" = container only. |
| **MEASURED** | A number from a results file in the repository. [RPC] = reference PC, [C] = cloud container (llvmpipe, software GL: draw times there are not GPU times). This audit measured nothing new. |
| **INFERRED** | Reasoned from code, specs or measurements, not checked. |
| **OPEN / UNVERIFIED** | Not answerable from the repository; the smallest test that would answer it is named. |

---

## Kurzfassung für Manu (Deutsch)

- **Urteil:** Lookdev lässt sich auf dem heutigen Viewport aufbauen, ohne Neubau und ohne zweite Geometrie. Alles, was
  der Viewport zeigt (Morph-Mischung, Pose, SubD, andere Objekte), liegt schon als `RenderMesh` mit GPU-Puffern vor.
  Ein Lookdev-Durchgang muss diese Puffer nur **mit einem anderen Shader zeichnen**. Dasselbe machen schon heute das
  GPU-Picking und das Drahtgitter.
- **Was fehlt wirklich:** eine Lookdev-Material-Beschreibung (das heutige Material ist Farbe + Glanz fürs Worklight und
  bleibt so), ein eigenes Lookdev-Licht (das Worklight bleibt ein Arbeitslicht), eine Umgebung für Spiegelungen
  (Cubemap), ein linearer Farbweg (heute rechnet der Shader bewusst ohne Gamma) und ein einstellbarer Hintergrund
  (heute fest im Code).
- **Noch nie auf deinem PC benutzt:** Cubemaps, Fließkomma-Texturen, sRGB, Multisampling, Tiefen-Texturen. Laut
  OpenGL 3.3 sollten sie da sein. Ob der Treiber der 9800 GTX sie brauchbar und schnell kann, zeigt erst ein kleiner
  Test.
- **Größtes Risiko:** Die Grafikkarte ist schon heute beim Schattieren gut beschäftigt. Bei 87,5k und 1024×768 kostet
  ein Bild ≈ 9,4 ms GPU-Zeit, und dabei bedeckt das Mesh nur etwa 13 % des Fensters. Eine Lookdev-Großaufnahme füllt
  das Bild. Wie viel das kostet, ist nicht gemessen; die Sonde dafür gibt es schon (`probe_shading_gpu.py`).
- **Augen-Test (P1):** ein kleines Wegwerf-Lab unter `experiments/` mit einem künstlichen Auge (Sklera, Iris/Pupille,
  Hornhaut), Studio-Umgebung, Key-Licht, Fresnel und Spiegelung je nach Rauheit, dazu eine undurchsichtige Variante
  als Rückfall für deinen PC. Kein Eingriff in Core, Szenenformat, Morph, Rig, SubD oder die App.
- **Nächster Schritt (Empfehlung):** zuerst eine kleine Sonde für GL-Fähigkeiten und Pixelkosten auf deinem PC (und
  auf dem neuen PC, sobald es ihn gibt), dann das Augen-Lab. **Der neue PC steht noch nirgends im Repository.** §6.3
  listet, was ich darüber wissen muss.
- **Deine Entscheidungen:** §8 (D-L1 bis D-L9). Für den Start reichen D-L1, D-L2, D-L4 und D-L5.

---

## 1. Executive summary and verdict

1. **Verdict: extend, do not rebuild.** The production path already separates evaluated geometry (src/mirai stages),
   render-facing geometry (`RenderMesh`) and GPU execution (`GLRenderStore`). It also has two working precedents of
   *another program drawing the store's own VertexList*: the GPU ID picker (`src/viewport/gpu_picker.py`) and the wire
   (`GLLineOverlay.draw_mesh_wire`). A Lookdev presentation needs a **third such consumer**: a read-only shading pass
   over the same `RenderMesh`es. It does not need a new renderer, scene graph or second evaluation path. **VERIFIED IN
   CODE** (§2, §3.1).
2. **The evaluated character is already on the GPU in the right form.** `Viewport.render()` draws
   `surface_render_mesh` (morph mix → pose → SubD via the H7 `SurfaceChain`) instead of the edit mesh, plus
   `object_entries` and their `entry_surface_render_meshes`. After O1–O3, positions flow from the stage tables as
   arrays (`slot_moves()` → `_read_table_moves`) into the same VertexList buffers the Worklight draws. A Lookdev pass that
   draws those `RenderMesh`es shows exactly the evaluated character, and adds **zero** CPU geometry work.
   **VERIFIED IN CODE.**
3. **What is genuinely missing** is not geometry but appearance infrastructure:
   - an Artist material model separate from `ObjectMaterial`;
   - a Lookdev light rig separate from the Worklight;
   - an environment (cubemap + prefiltered mips);
   - a scene-linear colour path (the Worklight is deliberately display-referred: "No gamma", `light_rig.kelvin_to_rgb`
     docstring; AD-026 §7 excludes sRGB);
   - a configurable background (hard-coded `glClearColor(0.1, 0.1, 0.11)` in `src/main.py:715`);
   - normal/roughness maps, per-face material assignment and HDR image input.

   **VERIFIED IN CODE** (absence checked by grep across `src/`, `tests/`, `experiments/`).
4. **The GL 3.3 features Lookdev needs first are untested in Mirai.** Exercised and passing on the 9800 GTX driver: GLSL
   330 programs, a geometry shader, `R32F` / `RG32F` / `RGBA32F` buffer textures, `gl_PrimitiveID`, `dFdx`/`dFdy`,
   mipmapped 2D textures, and an FBO with RGBA8 + DEPTH24 renderbuffers read back by `glReadPixels`. **TESTED [RPC].**
   Never used anywhere in the repository: cube maps (incl. seamless filtering), `textureLod`, half/float *sampled*
   2D/cube textures, float render targets, depth textures, sRGB textures or framebuffers, MSAA, `glBlitFramebuffer`,
   simultaneous MRT writes, GPU-memory queries. **VERIFIED IN CODE (absence).** They are core in GL 3.3, but whether this
   legacy driver runs them correctly and fast is **OPEN**. A small probe answers it (§5.7, §9).
5. **The main performance risk is fragment cost, not geometry.** The Worklight's O2 face-data shading (bilinear quad
   normal, 27 texel fetches per smooth-quad fragment) costs ≈ 9.4 ms GPU per full pass at 87.5k / 1024×768, with the mesh
   on about 13 % of the window. Without face data the same pass costs 1.9 ms. **MEASURED [RPC]**, clocks pinned.
   Lookdev close-ups fill the frame, so fragment work grows with coverage. The amount is **OPEN**: the existing
   `probe_shading_gpu.py`, including `--size 1920 1080`, has commands but no reference-PC result yet.
6. **Recommended seam (for P2, to be confirmed by P1):** a Lookdev pass *outside* `GLRenderStore.draw()`. The pass
   reuses the store's VertexList and face-data bindings through one small, behaviour-free accessor. `Viewport.render()`
   chooses Worklight or Lookdev shading for the meshes it already draws. The Worklight code path stays byte-identical by
   construction, and the existing pixel gates prove it. For **P1**, a disposable lab subclassing `GLRenderStore` (the
   Shading Lab precedent) is enough and touches nothing in `src/`. §4.
7. **Safest next step:** a capability + fill-rate probe on the reference PC (and on the main PC once it is recorded),
   then the P1 eye lab. §10.

---

## 2. Verified current rendering pipeline

### 2.1 Baseline (git)

- `origin/main` = `8e7da7a` "docs(perf): O3 stage 2 on the reference PC – D3 frame 118 / 189 -> 51 / 85 ms". Relevant
  code commits: `f0a90cc` O1 (surfaces as position tables), `58f7052` O2 (face data without per-face vertex copies),
  `47f6fa1` O3 stage 1 (derived geometry on NumPy arrays), `43d0ef3` O3 stage 2 (morph/skin on arrays, array hand-over to
  `RenderMesh`). **VERIFIED IN CODE** (`git log`).
- Runtime on the reference PC: Python 3.12.10, `numpy==2.2.6`, pyglet **2.1.19**, `imgui-bundle` 1.93.0
  ([RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md](../../experiments/drag_cost/RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md)).
  **MEASURED [RPC]** (environment record).

### 2.2 GL context and frame lifecycle

- **Context ownership.** `create_window()` (`src/main.py:420`) creates
  `pyglet.window.Window(width=1024, height=768, resizable=True)` with **no** `Config`. In pyglet 2.1.19 the default
  template asks for GL 3.3, double buffer and 24-bit depth (16-bit fallback), with no multisampling and no sRGB
  framebuffer (`pyglet/window/__init__.py`, the `gl.Config(...)` template list). **VERIFIED IN CODE** (pyglet 2.1.19
  source). There is one context per process. Every GL object (programs, VertexLists, buffer textures, the picker FBO,
  textures, imgui) lives in it. Programs compile lazily on first use (`GLRenderStore.program()`, class-level).
- **Viewport size.** pyglet's `_on_internal_resize` sets `glViewport` to the *framebuffer* size before dispatching
  `on_resize`. Mirai's `on_resize` (`src/main.py:513`) passes the *window* size to `Application.set_viewport_size`
  (`application.py:4215`), which sets the camera aspect and mouse-coordinate units. **VERIFIED IN CODE.** With Windows
  display scaling the two sizes differ. The aspect is the same, but an offscreen Lookdev target must be sized from
  the framebuffer. Whether the main PC uses scaling is **OPEN**.
- **Per tick** (`pyglet.clock.schedule_interval(_tick, 1/60)`, `src/main.py:828-834`): `Application.update_viewport`
  (`application.py:5219`) → `flush_hover`, object highlight sync, region tints, `skin.refresh()`, `morph.refresh()`,
  `viewport.sync()`.
- **Per draw** (`on_draw`, `src/main.py:712-739`), drawing only to the default framebuffer:
  1. `glClearColor(0.1, 0.1, 0.11)` and `window.clear()`.
  2. `viewport.sync()` and `viewport.render()`.
  3. Gizmo, pivot and bones.
  4. Box / lasso band.
  5. HUD, then the triad, then the imgui panels (`#version 330` OpenGL3 backend).
  6. The menu, if one is open.

  **VERIFIED IN CODE.**
- **`Viewport.render()`** (`src/viewport/viewport.py:964`):
  1. Resolves the Worklight once per frame (`light_uniforms()` → `light_rig.resolve(rig, camera)`) and pushes it to every
     drawn store (`set_light_uniforms`).
  2. Draws `drawn`: the surface `RenderMesh` if a provider shows one, else the edit `RenderMesh`, if `show_faces`.
  3. Draws the object entries, opaque first, then the Ghosts (`_entry_draw_order`).
  4. Draws the overlays in a fixed order: under-highlight overlays (Soft shading), wire (`draw_mesh_wire` from the
     buffers when possible), face highlight, edge highlight, tool lines, extra overlays, points.

  **VERIFIED IN CODE.**
- **`GLRenderStore.draw()`** (`gl_render_store.py:955`):
  1. Picks the plain or the textured program.
  2. Sets camera, light, material, flat, region-tint, model and alpha uniforms.
  3. Flushes and binds the face data (`_flush_face_data`) and the vertex buffer textures (`_bind_vertex_textures`).
  4. Enables depth test and back-face culling, plus polygon offset (1, 1) when lines lie on the faces. A Ghost blends
     (`SRC_ALPHA, ONE_MINUS_SRC_ALPHA`) with depth write off.
  5. Calls `vlist.draw(GL_TRIANGLES)`.
  6. Disables depth and cull again and unbinds units 1–7.

  **VERIFIED IN CODE.**

### 2.3 Data flow (after O1–O3)

```
 core.Mesh (edit object, authoritative)        Scene: objects, ObjectMaterial, texture path, rig      [Core, saved]
   │ Mesh.watch() journal                        │
   │                                             ▼
   │                           src/mirai: ObjectController.sync_views → resolved colour/finish/texture
   │                                      (selection tint, Reference blue, Worklight fill_specular)
   ▼
 src/mirai stages (H7 SurfaceChain: morph.provider → skin.provider → subdivision.provider)       [evaluated, view state]
   MixSurface / SkinSurface: SurfacePositions = n×3 float64 table over the base topology (O1, O3 s2)
     journal SurfaceChange: slot chunks, slot_moves(); MovedVertices
   SubdSurfaceProvider: derived mesh from stencils (not on arrays; MAX_DERIVED_FACES = 25,000)
   │  provider.sync(mesh, selection) → moved; provider.surface_mesh; entry_surfaces / entry_moved
   ▼
 Viewport (src/viewport/viewport.py)                                                        [render-facing geometry]
   render_mesh (edit, carries SelectionOverlay) · surface_render_mesh · object_entries · entry_surface_render_meshes
   _cage_render_mesh (never drawn; ID picking under SubD)
   RenderMesh: slot layout (AD-023), triangulation, PackedGeometry (P, VN, FN, ragged adjacency; NumPy, O3 s1)
     table path: position_array()[slot_moves] → packed.P (no per-vertex read, O3 s2)
     float32 mirrors → ResourceStore.update(ranges)
   ▼
 GLRenderStore (one per RenderMesh)                                                           [GPU, shader execution]
   pyglet VertexList (position, normal vec3 f32; uint indices) in the program's shared domain
   buffer textures: face_normals RGBA32F · face_corners RGBA32F · triangle_faces R32F · triangle_uvs RG32F
                    + R32F views of the VertexList's own position / normal buffers (O2)
   uniforms: camera, model, material packet (6 floats), 7 light uniforms, flat / tint / alpha
   2D texture (class-level cache by path, mtime, size)
   ▼
 default framebuffer (RGBA8 + depth 24, no MSAA, no sRGB) ← overlays, gizmo, HUD, triad, imgui draw on top
 GpuPicker: own FBO (3 × RGBA8 + DEPTH24 renderbuffers) drawing the cage RenderMesh's VertexList on demand
```

### 2.4 Components and their actual responsibilities

| Component | Responsibility (as built) | Source | Label |
|---|---|---|---|
| `Viewport` | Facade: owns the `RenderMesh`es (edit, surface, entries, entry surfaces, cage-pick), routes dirty notifications, resolves the Worklight per frame, fixes draw order, hosts overlays. Knows no objects and no `DisplayState`. | `viewport.py` (module docstring; `sync` 851, `render` 964, `_sync_surface` 639, `set_cage_source` 480) | VERIFIED IN CODE |
| `RenderMesh` | Render-facing geometry for one mesh: slot / row / triangle layout, triangulation, hidden / tint state, edge slots, CPU mirrors, `content_revision` / `layout_revision`; reads the mesh and its journal and never writes back. Material and camera are duck-typed bindings. | `render_mesh.py` (`sync` 841, `_sync_geometry` 1239, `_read_table_moves` 1226, `_rebuild_resources` 747, `_sync_material` 1291, `render` 1324) | VERIFIED IN CODE |
| `PackedGeometry` | NumPy arrays on the `RenderMesh` slot layout: positions, vertex / face normals, ragged corner and adjacency pools; 1-ring kernels bit-identical to `derived.py`. Knows no IDs. | `packed_geometry.py:163` (`build` 178, `neighbourhood` 205, `update_face_normals` 211, `update_vertex_normals` 245) | VERIFIED IN CODE; TESTED [RPC] (`test_packed_geometry.py`) |
| `GLRenderStore` | The one drawable group per `RenderMesh` (AD-018 §5: "not a general GPU resource manager"): VertexList assembly / patching, face-data buffer textures, the two programs, the texture cache, draw state, `draw()`. | `gl_render_store.py` | VERIFIED IN CODE |
| `GpuPicker` | Own programs and FBO; draws the store's public VertexList for faces / edges / points IDs; cached by revisions + camera. | `gpu_picker.py` | VERIFIED IN CODE; TESTED [RPC] (`test_gl_gpu_picking.py`, `test_gl_morph_picking.py`) |
| `light_rig` | GL-free Worklight state (`LightRig`), `resolve()` → 7 uniforms, `kelvin_to_rgb`, the Python reference `shade()`, presets. | `light_rig.py` (`LightRig` 47, `kelvin_to_rgb` 205, `resolve` 227, `shade` 262, presets 317–359) | VERIFIED IN CODE; TESTED [RPC] (`test_gl_shading.py`) |
| `material` | GL-free `SurfaceFinish` (specular, glossiness, fill_specular), `Material` (colour, finish, texture path), 6-float packet, `gloss_exponent = 4·64^g`, `specular_term` reference. | `material.py` | VERIFIED IN CODE |
| `DisplayState` | View state: display mode, wire overlay, light preset / edit / space, `surface_finish`, `region_tint`, `show_texture`. | `src/mirai/viewport/display.py` | VERIFIED IN CODE |
| `OrbitCamera` | Orbit / ortho camera, `build_view_matrix`, `build_projection_matrix(aspect)`, fov 50°, near 0.05, far 200. | `src/mirai/viewport/camera.py:89`, projection 264 | VERIFIED IN CODE |
| `view_state` | Saves / loads display, Worklight, finish, camera, SubD and Ghost in an optional `"view"` section of the scene file, outside the Core format, read defensively. | `src/mirai/view_state.py` (added `f76287f`, 2026-11-08) | VERIFIED IN CODE |

### 2.5 Shaders, buffers and texture units in use

**Programs** (all `#version 330 core`): **VERIFIED IN CODE**

| Program | Stages | Used for | Source |
|---|---|---|---|
| plain mesh | VS + FS | Worklight shading of every `RenderMesh` | `VERTEX_SRC`, `FRAGMENT_SRC` (`gl_render_store.py:47`, `112`) |
| textured mesh | VS + **GS** + FS | the same, with barycentrics and per-triangle UVs; attribute locations taken from the plain program | `TEXTURED_*_SRC` (`gl_render_store.py:358–403`) |
| ID picker ×2 | VS + FS | faces / edges / points IDs into the FBO | `gpu_picker.py:45–80` |
| line overlay ×3, point overlay ×2, soft shading ×2 | VS + FS | wire, highlights, tool lines, points, Soft influence | `gl_line_overlay.py`, `gl_point_overlay.py`, `soft_selection/gl_shading.py` |
| imgui | backend | panels (`opengl3_init("#version 330")`) | `src/gui/imgui_layer.py:131` |

There are no uniform buffer objects; every uniform is set per draw through pyglet. **VERIFIED IN CODE.**

**Texture units of the mesh programs** (`gl_render_store.py:410–421`): **VERIFIED IN CODE**

| Unit | Sampler | Content | Format |
|---|---|---|---|
| 0 | — | left free for pyglet (text, HUD) and imgui | — |
| 1 | `u_face_normals` | per face row: Newell normal + corner count | RGBA32F buffer texture |
| 2 | `u_triangle_faces` | per triangle: face row | R32F buffer texture |
| 3 | `u_triangle_uvs` | per triangle: 3 corner UVs (textured program only) | RG32F buffer texture |
| 4 | `u_texture` | the object's image | 2D, mipmapped, trilinear, REPEAT |
| 5 | `u_face_corners` | per face row: vertex slots of 4 corners; region tint rgb, `.w` = 0 (unused) | RGBA32F buffer texture |
| 6 | `u_positions` | view of the VertexList's position buffer (3 texels per vertex) | R32F buffer texture |
| 7 | `u_normals` | view of the VertexList's normal buffer | R32F buffer texture |

The next free unit is 8. GL 3.3 guarantees at least 16 fragment texture image units (spec). The reference driver's
`GL_MAX_TEXTURE_IMAGE_UNITS` is not recorded: **OPEN** (probe). The free `.w` of `face_corners` texel 1 is a per-face
float channel that a later per-face material index could use without changing the layout. **INFERRED** (`_face_corner_values`,
`render_mesh.py:715`); that would be a decision, not something to do silently.

**Buffers.** One pyglet VertexList per store (position vec3 f32, normal vec3 f32, uint index buffer, `GL_TRIANGLES`).
It is allocated through `program.vertex_list_indexed`, so every store's VertexList shares the plain program's vertex
domain; `u_vertex_base = vlist.start` addresses it (`gl_render_store.py:773`). The wire and the picker each own an
`EdgeIndexBuffer` over the same vertex buffer (`glDrawElementsBaseVertex`). **VERIFIED IN CODE.**

### 2.6 How each kind of data reaches the GPU after O1–O3

| Data | Path | Label |
|---|---|---|
| **Positions, edit mesh** | `Viewport.on_vertices_moved` → `RenderMesh.mark_vertices_dirty` → `sync` → `_read_moved` (one `vertex_position` per moved vertex) → `packed.P` | VERIFIED IN CODE |
| **Positions, morph / skin surface** | stage write → `SurfaceChange` slot chunk → `RenderMesh` journal `slot_moves()` → `_table_render` map → `packed.P[slots] = position_array()[moves]` (`_read_table_moves`). The host's moved set only marks geometry dirty. | VERIFIED IN CODE; TESTED [RPC] (`test_stage_arrays.py`, zero per-vertex reads) |
| **Positions, SubD surface** | `SubdSurfaceProvider` derived mesh, `moved` / `surface_topology_changed`; read per vertex (not on arrays) | VERIFIED IN CODE |
| **Normals** | `PackedGeometry.neighbourhood` → face normals (Newell) and vertex normals (sum in FaceId order) on arrays → float32 mirrors | VERIFIED IN CODE; TESTED [RPC] (bit-identity) |
| **To the store** | `_upload_slots` / `_upload_face_normals`: merged ranges as float32 NumPy views → `ResourceStore.update` → `memmove` into pyglet's backing store → pyglet commits inside `vlist.draw()` | VERIFIED IN CODE |
| **Face data** | `face_normals` (only data a deformation writes), `face_corners` and `triangle_faces` (topology / tint only) → `glBufferSubData` over merged dirty ranges at the next draw | VERIFIED IN CODE |
| **UVs** | Mesh face-corner UVs (`Mesh.face_uvs`, `core/mesh.py:879`). Morph / skin tables share the base's UVs (`surface_positions.py:353`); SubD refines them linearly (`catmull_clark.refine_face_uvs`). `triangle_uvs` exists **only** while the bound `Material` has a texture **and** the mesh has UVs (`RenderMesh._uv_wanted`, `render_mesh.py:650`). | VERIFIED IN CODE; TESTED [RPC] (`test_gl_texture.py`) |
| **Material** | resolved by src/mirai → `Material(color, finish, texture).uniform_packet()` (6 floats) → `material_uniforms` (CPU-side "uniform resource") → `read_packet` → `u_base_color`, `u_specular`, `u_spec_exponent`, `u_fill_specular` at draw | VERIFIED IN CODE |
| **Camera / model** | `_camera_uniforms()` (view + proj, 32 floats) per `RenderMesh` on camera dirty; `model_uniforms` per `RenderMesh` | VERIFIED IN CODE |
| **Light** | resolved per frame in `Viewport.render`, set as draw state on each store (no resource, no upload) | VERIFIED IN CODE; TESTED [RPC] (`test_light_change_is_draw_state_only`) |

Bytes to the store per D3 deformation frame (87.5k, 15 % region): **556,940**. **MEASURED [C]** (AD-032 §12; unchanged by
stage 2).

### 2.7 `ObjectMaterial`: representation, update, persistence

- **Data.** `core.scene.ObjectMaterial(base_color, specular, glossiness)`, each in [0, 1], frozen, validated
  (`src/core/scene.py:130`). `SceneObject.material: ObjectMaterial | None`, where `None` means the app's default look.
  **VERIFIED IN CODE.**
- **Meaning lives outside the Core** (AD-024 §2):
  - `gloss_exponent(g) = 4·64^g` (Blinn–Phong exponent 4 … 256);
  - specular is a neutral white highlight scaled by the key's luminance, not energy-normalised, with a non-local viewer;
  - `fill_specular` is a Worklight value, not part of the material (`material.py` docstring, `scene_objects.object_finish`).

  **VERIFIED IN CODE.**
- **What the shader receives is not the material.** `ObjectController.sync_views` (`controllers/objects.py:1011`) sends:
  - **References:** `REFERENCE_BASE_COLOR` with the default finish, whatever their own material is
    (`scene_objects.object_base_color`, `object_finish`);
  - **mode-`4` highlighted objects:** a colour tinted toward yellow (`selected_color`, share 0.45), and **no texture**
    (`_shown_texture`).

  The packet is therefore "the displayed colour". **VERIFIED IN CODE.** Consequence: a Lookdev pass must not derive
  its material from the store's packet (§3.5 I-6).
- **Update.** `Application.set_object_material` / `step_object_material` (keys: `look_controls.MATERIAL_ROWS`, after the
  13 `LIGHT_ROWS` in one arrow-key list), Undo as `ObjectMaterialCommand`. In the viewport this is a uniform update only
  (`material_updates`). **VERIFIED IN CODE;** behaviour pinned by `tests/test_surface_finish.py`,
  `test_gl_shading.py::test_finish_change_is_a_material_update_only` (TESTED [RPC]).
- **Persistence.** `"material": null | {base_color, specular, glossiness}` per object (`serialization._material_to_dict`).
  The file version depends on content (4–8, `serialization.py:66–76`). **VERIFIED IN CODE.**

### 2.8 Textures: loaded, stored, bound, displayed

- **Data.** `SceneObject.texture: str | None`, an image path that is Core data but carries no meaning there
  (`core/scene.py` docstring; file v6+). It comes from OBJ import (`map_Kd` or an image with the same name;
  `Application.import_obj`, `application.py:865`). **One texture per object**, used only as base colour. **VERIFIED IN CODE.**
- **Load / store.** `GLRenderStore.texture(path)` keeps a class-level cache keyed by (path, mtime, size)
  (`gl_render_store.py:563`). `load_texture` → `pyglet.image.load` → `get_texture()`, which uploads with the *unsized*
  internal format `GL_RGBA` (pyglet 2.1.19 `ImageData._get_internalformat`), then `glGenerateMipmap`, trilinear filtering
  and REPEAT (`gl_render_store.py:480`). **VERIFIED IN CODE.** No sRGB internal format and no anisotropic filtering.
  Only formats pyglet's decoders read (8-bit LDR; no `.hdr` / `.exr`). **VERIFIED IN CODE (absence).**
- **Display.** Unit 4. In the textured program the fragment's albedo becomes `texture(u_texture, uv).rgb`, used directly
  as a display value (AD-026 §7: "sRGB-correct display … not in scope"). **VERIFIED IN CODE;** TESTED [RPC]
  (`test_gl_texture.py`, 5 tests: texture shows, UV change, unmapped face, fallback, re-export).
- **Missing for Lookdev:** normal, roughness, specular, detail or mask maps; tangents; several textures per object;
  per-face material assignment; HDR images; texture colour-space metadata. **VERIFIED IN CODE (absence).**

### 2.9 The Worklight: Key / Fill / Ambient

- **State.** `LightRig` (`light_rig.py:47`):
  - space: camera or world;
  - key: azimuth, elevation, intensity, Kelvin, wrap;
  - fill: coupled (diagonally opposite, mirrored elevation) or free, Key:Fill ratio (or off), Kelvin, wrap;
  - ambient: a scalar.

  Presets "Heute", "Raitt 2:1" (app default), "Softbox", "Warm/Kalt". `DisplayState` holds preset, edit and space.
  `Application.set_light` / `step_light`, `L`+mouse drag. No Undo. Saved in the `"view"` section of the scene file
  (`view_state.capture`, since 2026-11-08). **VERIFIED IN CODE.**
- **Uniforms.** `resolve()` gives 7 uniforms: `u_key_dir`, `u_fill_dir` (world space; in camera space rotated by
  `camera.basis()` every frame), `u_key_color`, `u_fill_color` (`kelvin_to_rgb` × intensity, luminance-normalised,
  white-balanced to 6500 K), `u_key_wrap`, `u_fill_wrap`, `u_ambient`. **VERIFIED IN CODE.**
- **Shader** (`FRAGMENT_SRC`):
  `albedo · (ambient + key_color·wrap(N·L_key) + fill_color·wrap(N·L_fill))`, plus Blinn–Phong
  `specular·lum(key)·max(N·H,0)^e`, and the same on the fill with `fill_specular`. V is the camera view axis, a non-local
  viewer. There is no rim light, no shadow, no environment and no Fresnel. Python mirror: `light_rig.shade`. **VERIFIED IN
  CODE;** parity TESTED [RPC] (`test_gl_shading.py::test_shader_highlight_matches_the_reference`,
  `test_heute_reproduces_the_old_single_light`).
- **Artist decisions it carries:**
  - Raitt 2:1 default (2026-10-15);
  - specular / gloss KEEP (2026-10-23);
  - no shadow map and no MatCap *for the Worklight* (2026-09-25 / 26);
  - triangles invisible in Flat and Smooth (2026-10-15, hence the bilinear quad normal).

  These bind the Worklight only.

### 2.10 Camera, background, dimensions, projection

- `OrbitCamera` (`camera.py:89`): perspective fov 50° (vertical), near 0.05, far 200; ortho as a mode of the same camera
  (near = −far/2). `build_projection_matrix(aspect)` with aspect = window width / height. Camera changes reach every
  `RenderMesh` as `mark_camera_dirty`, and each recomputes its own 32 floats. The camera is view state, saved in
  `"view"`. There is no exposure, no physical camera model and no depth of field. **VERIFIED IN CODE.**
- **Background:** hard-coded `glClearColor(0.1, 0.1, 0.11, 1.0)` in `on_draw` (`src/main.py:715`), the only clear colour
  in `src/`. It is not a state value and is not saved. The background slice of the shading research (§4.1b, §7 Slice 3)
  was never built. **VERIFIED IN CODE.**

### 2.11 Shared versus recreated resources; dirty propagation

| Resource | Lifetime | Label |
|---|---|---|
| Plain / textured program | class-level, compiled once per process | VERIFIED IN CODE |
| VertexList | per store; recreated on a full rebuild (`_rebuild_vertex_list`); patched in place otherwise (`_patch_attribute`, memmove); a domain resize re-attaches the R32F views | VERIFIED IN CODE |
| Face-data buffer textures | per store; `glBufferData` on size change, else `glBufferSubData` of merged dirty ranges | VERIFIED IN CODE |
| 2D textures | class-level cache shared by every store showing the same file | VERIFIED IN CODE |
| Surface `RenderMesh` | recreated when the provider's `surface_mesh` *object* changes (first weight / pose step: 3.0–3.1 s at 87.5k **MEASURED [RPC]**); patched otherwise | VERIFIED IN CODE |
| Picker FBO | per picker (per window), recreated on size change; restores `glViewport`, binds framebuffer **0** on exit (`gpu_picker.py:186–245`) | VERIFIED IN CODE |
| Light / flat / tint / alpha | draw state, no resource | VERIFIED IN CODE |

Dirty propagation:

1. Core or app mutation.
2. `Viewport.on_*` (vertices moved, topology, selection, material, camera).
3. `RenderMesh.mark_*` sets the `DirtyState` flags.
4. The next `Viewport.sync()`: edit `RenderMesh`, entries, provider sync + surface `RenderMesh`, cage follow, overlays.
   Topology is taken before geometry, and the journal is the truth (AD-023, AD-032 §11).

**VERIFIED IN CODE.**

### 2.12 Ownership boundaries

| Layer | Owner | What it holds | May a Lookdev system write it? |
|---|---|---|---|
| 1. Core and evaluated scene data | `core.Mesh`, `Scene` (objects, `ObjectMaterial`, texture path, rig); src/mirai stages (`MixSurface`, `SkinSurface`, `SubdSurfaceProvider`, `SurfaceChain`) | topology, rest positions, layers, UVs, regions; evaluated positions as tables / derived mesh; weights / pose as view state | **No.** Read only, through the existing provider / journal contracts. |
| 2. Render-facing geometry | `Viewport`, `RenderMesh`, `PackedGeometry` | slot layout, triangulation, normals, face rows, hidden / tint, UV triangles | **No.** A Lookdev pass consumes it. |
| 3. GPU resources and shader execution | `GLRenderStore`, `GpuPicker`, overlays, imgui backend | VertexLists, buffer textures, programs, FBO, textures, draw state | Adds its **own** programs and environment textures; borrows the store's bindings read-only. |
| 4. Artist-facing material / light / camera state | `DisplayState`, `SceneObject.material` / `.texture`, `OrbitCamera`, `view_state`, `look_controls`, `Application` setters | Worklight rig, finish, show_texture, region tint; object material; camera | Needs a **new, separate** Lookdev state (material, rig, environment, background, exposure). Shares the camera. |

---

## 3. Reuse / extend / missing-capability inventory

### 3.1 Geometry and evaluated surfaces

| Question | Answer | Label |
|---|---|---|
| Can Lookdev consume the same evaluated visible geometry? | **Yes, directly.** The meshes `Viewport.render()` draws (`drawn = surface_render_mesh or render_mesh`, `object_entries`, `entry_surface_render_meshes`) already hold morph + pose + SubD results in their VertexLists. | VERIFIED IN CODE |
| Correct interface after O1 / O3 | **For a GPU pass:** those `RenderMesh`es and their stores (`store.vertex_list()`, face-data bindings, `uniform_data("camera_uniforms" / "model_uniforms")`, `edge_indices`, `content_revision` / `layout_revision`). **For CPU-side consumers** (a later final-render export): the H7 provider's `surface_mesh` with the `Mesh` query API (`vertex_position`, `face_vertices`, `face_uvs`), plus `position_array()` / `table_slots()` on stage tables (`surface_positions.py:397`, `401`). Not `SurfacePositions` internals and not `PackedGeometry` arrays (private to the viewport). | VERIFIED IN CODE |
| Second morph / skin / SubD / topology representation avoidable? | **Yes.** A pass that only draws existing buffers adds no evaluation and no derived data. Anything that needs per-vertex data the `RenderMesh` lacks (tangents, curvature, AO bakes) would add a K2 cost per deformation (shading research §3) and should be avoided or derived in the shader (§3.2). | VERIFIED IN CODE / INFERRED |
| Mechanisms already handling changes | geometry: journal + `mark_vertices_dirty` / `slot_moves`; topology: `_patch_topology` / full rebuild; transforms: `set_model_matrix` → `u_model`; material: `bind_material` + `mark_material_dirty` (uniform only); camera: `mark_camera_dirty`; hidden / tint: `set_hidden` / `set_face_tints`; textures: material texture path → `triangle_uvs` + `set_texture` | VERIFIED IN CODE |
| SubD on the dense character | **Not available above 25,000 derived faces** (`MAX_DERIVED_FACES`, `subdivision/preview.py:75`). `gollum_20k` (21,875 quads) cannot show level 1. D4 accepts this for 100k cages; D5's re-measurement "after O2" is still open. A Gollum close-up therefore shows the cage, with silhouette facets. | VERIFIED IN CODE / OPEN |

### 3.2 Materials and textures

| Need | Today | Classification |
|---|---|---|
| Base colour | `ObjectMaterial.base_color` or texture | **reuse** the value as the Lookdev default colour, *read from the object, not from the packet* |
| Roughness-aware specular | gloss → Blinn–Phong exponent; not energy-normalised; no Fresnel | **missing** in Lookdev. Do **not** reinterpret `glossiness` as roughness or `specular` as F0 (vision §4). A Lookdev material needs its own fields with documented defaults. |
| Fresnel | none | **missing**: shader term only (K0) |
| Environment reflection | none | **missing**: cubemap + `textureLod` (K1) |
| Normal / detail maps | none; no tangents | **missing**. Smallest route: derivative-based tangent frame in the fragment shader (`dFdx`/`dFdy` of position and UV), so no per-vertex tangent buffer and no deformation-time CPU work. `dFdx` is already compiled into every mesh draw and passes on the reference PC. **INFERRED** suitability; image quality unverified. |
| Several textures per object | one path per object, base colour only | **missing**; AD-026 §7 leaves room ("a keyed UV map") |
| Material assignment | per object only (`SceneObject.material`) | **reuse** for P1 (eye parts as separate objects). Per-face assignment is **missing**; candidate later: face regions (AD-REGIONS-01, overlap allowed, so a priority rule would be needed) with an index in `face_corners` texel 1 `.w`. A decision, not a default. |
| Colour space | display-referred; textures used as stored | **missing** for Lookdev: sRGB decode of colour textures, linear shading, exposure, display encode. Shader-side decode / encode avoids touching global GL state. |
| HDR images | not loadable (pyglet decoders) | **missing**: P1 can generate the environment procedurally in NumPy (already a production dependency, `numpy==2.2.6`). A later Radiance `.hdr` reader in NumPy needs no new dependency. **INFERRED.** |

**Smallest extension that allows PBR-inspired materials without a node editor (INFERRED, for P2, after P1):**

- A **separate, flat, named Lookdev material record** (e.g. base colour or texture, roughness, specular level / F0,
  normal-map path + strength, a few eye-specific values such as iris depth and cornea clarity). Names follow glTF /
  OpenPBR meanings (vision §4).
- **Presets** (Sclera, Iris, Cornea, Creature Skin, …) instead of a graph.
- **Resolved by src/mirai per object**, pushed to the viewport as **draw state per entry key**, exactly as the Worklight
  colour / finish is pushed today (`set_object_entry`, `set_edit_base_color`).
- `ObjectMaterial` stays the Worklight look, unchanged. A missing Lookdev material falls back to an explicit default
  that is documented, never computed from `glossiness`.

**Persistence is a decision (D-L7).** AD-024 §1.2 explicitly rejected an ObjectId-keyed side table, because
`replace_scene` hands out new IDs on load. The `"view"` section precedent (`view_state.py`) avoids the Core format, but
it is keyed by app state, not by object.

### 3.3 Lighting and environment

| Question | Answer | Label |
|---|---|---|
| Current Worklight | §2.9: two directional lights with wrap + scalar ambient + Blinn–Phong, camera or world space, Kelvin colour, all draw-state uniforms resolved per frame | VERIFIED IN CODE |
| Reuse without turning the Worklight into scene lighting? | **Reuse the functions, not the state.** `kelvin_to_rgb`, `local_direction`, `frame_for`, `world_direction`, `coupled_fill_angles` are pure and GL-free; a Lookdev rig can call them. The Worklight's `DisplayState.light_*`, `Viewport.light_rig`, `set_light_uniforms` and the 7 Worklight uniform names stay Worklight-only. A Lookdev pass sets its own uniforms in its own program, so `Viewport.render()` pushing the Worklight to every store each frame does not interfere. | VERIFIED IN CODE (functions are pure) / INFERRED (seam) |
| Missing for an independent Lookdev rig | a state object (key, fill, optional rim; intensities in a defined unit; environment rotation / intensity; background; exposure) owned by src/mirai, never written into `DisplayState`'s Worklight fields; its own persistence (decision) | VERIFIED IN CODE (absence) |
| Missing for environment light / reflection | cubemap texture + prefiltered mips (specular); optional 9-coefficient SH (diffuse); an environment source (procedural studio first) | VERIFIED IN CODE (absence) |
| Realistic under GL 3.3 | cube maps, `textureLod`, half-float textures, FBOs with float colour targets and depth textures are all **core in GL 3.3** (spec). None is exercised in Mirai; driver correctness, filtering and speed on the 9800 GTX are **OPEN**. Seamless cube filtering (`GL_TEXTURE_CUBE_MAP_SEAMLESS`, core 3.2) may be emulated or ignored on this GPU generation: **OPEN**; CPU-side edge fix-up of the prefiltered mips is the fallback. | spec fact / OPEN |

### 3.4 Framebuffers, passes and GL features

| Feature | In code | Exercised on the reference PC | Label |
|---|---|---|---|
| GLSL 330 VS + FS | every program | yes (165 GL tests, 2026-11-11 and 2026-11-13) | TESTED [RPC] |
| Geometry shader (GL 3.2 core) | textured program | yes (`test_gl_texture.py`) | TESTED [RPC] |
| Buffer textures R32F / RG32F / RGBA32F + `texelFetch` | face data, UVs, O2 vertex views | yes (`test_gl_face_data_layout.py` byte-identical, `test_gl_texture.py`) | TESTED [RPC] |
| `GL_ARB_texture_buffer_object_rgb32` | — | **absent** on this driver | MEASURED [RPC] |
| `gl_PrimitiveID` in FS, passed through GS | face lookup, picker | yes | TESTED [RPC] |
| `dFdx` / `dFdy` | `screen_flat_n` in every mesh draw | yes (`test_per_triangle_shading_shows_the_diagonal`) | TESTED [RPC] |
| 2D texture + `glGenerateMipmap` + trilinear | `load_texture` | yes | TESTED [RPC] |
| FBO, 3 × RGBA8 colour renderbuffers + DEPTH_COMPONENT24, one draw buffer at a time, `glReadPixels` colour and depth (float) | `GpuPicker` | yes (`test_gl_gpu_picking.py`; spike 2026-10-20) | TESTED [RPC] |
| `GL_TIME_ELAPSED` queries | probes only | yes | MEASURED [RPC] |
| Alpha blending, depth write off (Ghost) | `GLRenderStore.draw` | used in the app (AD-021 Q-11); **no GL test** | VERIFIED IN CODE / UNVERIFIED by test |
| Cube maps, seamless filtering, `textureLod` | — | — | not used; OPEN |
| RGBA16F / RGBA32F *sampled* 2D or cube textures; float render targets | — | — | not used; OPEN |
| Depth textures / shadow samplers | — | — | not used; OPEN |
| sRGB textures / `GL_FRAMEBUFFER_SRGB` | — | — | not used; OPEN |
| MSAA (window or FBO), `glBlitFramebuffer` | — | — | not used; OPEN |
| Simultaneous MRT writes | — (the picker writes one attachment per pass) | — | not used; OPEN |
| GPU-memory queries (`GL_NVX_gpu_memory_info`) | — | — | not used; OPEN |
| Uniform buffer objects, instancing | — | — | not used |

Driver-specific uncertainties that need a test, not speculation, are listed in §5.7.

### 3.5 Invariants an additional render pass can break

Each is **VERIFIED IN CODE** unless marked.

- **I-1 Depth contract with the overlays.** Wire (`draw_mesh_wire` uses `LINE_VERTEX_SRC`'s expression to meet the mesh
  depth with `GL_LEQUAL`), face / edge highlights, tool lines and points all rely on the mesh pass having written depth
  into the *default* framebuffer:
  - with the vertex transform `u_proj · u_view · u_model · position`;
  - with polygon offset (1, 1) whenever lines lie on the faces.

  A Lookdev pass must write identical depth (same transform, same offset rule) or draw into the same depth buffer.
  Otherwise the wire and the selection z-fight or vanish.
- **I-2 Attribute locations.** The textured program, the picker and the wire bind `position` (and `normal`) at
  `GLRenderStore.program()`'s locations via `layout(location = …)`. AD-022 §3 records that the reference driver once
  dropped an unused attribute. Any Lookdev program drawing the VertexList must use the same locations.
- **I-3 Shared vertex domain.** All stores' VertexLists share the plain program's domain. The O2 R32F views are
  re-attached when pyglet's buffer name or size changes (`_bind_vertex_textures`). A foreign program must go through
  that binding, not cache buffer names.
- **I-4 GL state discipline.**
  - `GLRenderStore.draw` leaves depth test and cull disabled, units 1–7 unbound and unit 0 active.
  - `GpuPicker._render` restores the viewport but binds framebuffer **0**, not the previous binding.
  - Picks run from input handlers and the tick, not inside `on_draw` (INFERRED from the call sites).
  - A Lookdev FBO must therefore be bound and unbound entirely inside its own draw call.
- **I-5 Unit 0** belongs to pyglet text, HUD and imgui; units 1–7 to the mesh programs.
- **I-6 The material packet is the displayed colour.** It carries the selection tint, the Reference blue and the
  Worklight finish (§2.7). Lookdev must take its material from the object, not from `store.material()`.
- **I-7 `triangle_uvs` follows the Worklight's texture display.** It exists only while the bound `Material` has a
  texture, and `_shown_texture` withholds the texture for highlighted objects and when `show_texture` is off. A textured
  Lookdev material on a selected object would find no UVs on the GPU. P2 must decouple "UVs on the GPU" from "Worklight
  shows the texture", which is a small `RenderMesh` change and needs its own gate.
- **I-8 Hidden / Isolate** turns triangles degenerate in the shared index buffer, so Lookdev shows the same hidden state
  automatically. Whether Lookdev *should* ignore Hide is a product question (D-L6).
- **I-9 Transparency order.** Ghost entries (`alpha < 1`) draw after the opaque ones with depth write off; the edit object
  has no alpha. A transparent cornea must be an object entry, or get its own ordering rule.
- **I-10 Read-only consumption.** `content_revision` / `layout_revision` are the picker's cache keys. A Lookdev pass must
  never write the store's buffers.
- **I-11 Worklight light is pushed to every store each frame.** Lookdev light must be separate state with separate
  uniforms.
- **I-12 Frame budget.** D3 is not met (pose 50.86 / 53.85 ms, weight 85.10 / 92.37 ms p50 / p95). `on_draw` is 19.6 ms of
  a pose frame, ≈ 12 ms of it waiting for the GPU's mesh draw. **MEASURED [RPC]**, AD-032 §12. Any Lookdev shading adds
  GPU time to exactly that wait. Lookdev during live deformation must be measured, not assumed.
- **Unaffected by construction** (INFERRED from the code paths): GPU picking draws its own ID pass from the cage
  `RenderMesh`; navigation only changes camera uniforms; modelling tools mutate the Core and never read shading state.

### 3.6 Technique classification (cross-check of RENDERING_TECHNOLOGY_RESEARCH)

The shadow-map and MatCap rejections (shading research §2.4) bind the **modelling Worklight** only; they are not reasons
against these techniques in Lookdev.

| Technique | Class | Mirai-specific implication |
|---|---|---|
| GGX / microfacet specular + Schlick Fresnel | **P1** | Shader-only (K0). Compare against the existing Blinn–Phong as a baseline; keep the Python-reference + GL-parity test pattern (`light_rig.shade` ↔ shader). |
| Cubemap environment reflection + prefiltered mips | **P1** | First use of cube maps and `textureLod` in Mirai: needs the probe (§5.7). Prefilter on the CPU (NumPy) once, upload all mips; no FBO rendering needed. |
| Diffuse environment, 9-coefficient SH | **later realtime (P3)** | Cheap in the shader (9 vec3 uniforms); compare with Key+Fill first (research §9 P2). Not needed for the eye proof. |
| Shadow map, one key light, modest PCF | **later realtime (P3)** | Needs a depth texture + extra pass over the same VertexLists: both untested on the 9800 GTX. The ID picker's depth-only face pass is the structural precedent. The extra full-geometry pass hits the I-12 GPU budget at 87.5k. |
| Screen-space / approximate AO | **later realtime, optional** | Needs an offscreen depth (texture) and a full-screen pass: conflicts with the default-framebuffer depth contract (I-1) unless depth is copied or the overlays move. Unjustified before shadows and environment are judged. |
| Realtime skin (wrap / backscatter) | **later realtime, after eyes** | The Worklight's `wrap_light` is reusable math. Thickness data would be new per-vertex data (K2 in deformation), so avoid it initially. |
| Screen-space / multi-pass SSS | **later realtime, optional tier, main PC first** | Needs an HDR offscreen target and blur passes. Fill-rate risk on the legacy GPU (§6.4). |
| Random-walk SSS, path tracing, refraction through layered eyes | **final rendering / external renderer** | P4: an immutable snapshot of the evaluated `surface_mesh` (CPU side), not of the GPU buffers. |
| Directional SH occlusion cache (Wētā / PantaRay style) | **research-only / unjustified** | Cache invalidation under morph / skin is unsolved, and it would be a second derived per-vertex representation. |

---

## 4. Recommended Lookdev architecture boundary and alternatives

### 4.1 Alternatives considered

| # | Seam | Reuses | New responsibility | Assessment |
|---|---|---|---|---|
| **A** | A third program *inside* `GLRenderStore` (like `TEXTURED`: `#define LOOKDEV`), selected by a draw-state switch | VertexList, face data, textures, draw-state pattern | Lookdev program + its uniforms in the store | Least new code. But it puts Lookdev logic into the Worklight's draw method (AD-018 §5: "one group, `draw()` draws exactly that group"; the store is "not a general GPU resource manager"). The Worklight would stay byte-identical only by test, not by construction. **Viable, second choice.** |
| **B** | A Lookdev pass *outside* the store that draws `store.vertex_list()` with its own program, like `GpuPicker` and `draw_mesh_wire`; `Viewport.render()` calls it instead of `rm.render()` for the meshes it already draws | VertexList, face-data bindings, camera / model uniforms, texture cache, draw order, overlays | the pass (programs, environment textures, Lookdev uniforms); one public, behaviour-free store method that binds the face data and vertex views for a foreign program (today private: `_flush_face_data`, `_bind_vertex_textures`, `_set_face_samplers`) | **Recommended for P2.** Worklight code is untouched. The pass is read-only (I-10). It follows two existing, reference-PC-tested precedents. The GLSL helpers (`quad_normal`, `vertex_value`) can be shared as source strings while the Worklight string stays unchanged. |
| **C** | `GLRenderStore` subclass via `Viewport(store_type=…)` | everything | the subclass | **Right for P1** (Shading Lab precedent, `docs/archive/experiments_2026-10/viewport_shading_lab/`; AD-010). **Wrong for production:** `store_type` is per `Viewport`, so a runtime Worklight ↔ Lookdev switch would rebuild every `RenderMesh` (3 s for one 87.5k surface, MEASURED [RPC]) and break "display changes never rebuild". |
| **D** | Second window / context / viewport | — | context sharing, a second upload of all geometry, input routing | Rejected: duplicates GPU geometry and context state on a 481 MB card; the vision does not require it (§3.2). |
| **E** | New render framework / scene graph / generic pass system | — | everything | Rejected: nothing in the code demands it; the existing pieces already separate the layers (§2.12). |
| **F** | Offscreen HDR framebuffer + composite | orthogonal to A / B | FBO, float colour target, depth hand-over to the overlays | Not needed for P1 or the P2 baseline (shader-side tone map + encode into the default framebuffer keeps I-1 intact). Needed later for bloom, screen-space SSS / AO and true HDR exposure; then depth must be shared with the overlays (blit or same FBO): **OPEN** on this driver. |

### 4.2 Recommended boundary, per extension point (INFERRED design; to be validated by P1, decided in an AD before P2)

| Extension point | Reuses | Actually new | Why safer than the alternatives | How it leaves the rest alone |
|---|---|---|---|---|
| **Lookdev pass** (src/viewport, GL) | `RenderMesh` set drawn by `Viewport.render()`; store VertexList; face data; camera / model uniforms; texture cache | programs (Lookdev BRDF, background), environment cube texture, its uniforms | No change in `GLRenderStore.draw()`; mirrors `GpuPicker` / wire | Same vertex transform and polygon-offset rule (I-1); same attribute locations (I-2); read-only (I-10); own GL state, restored (I-4). Overlays, wire, picking and navigation keep their paths. |
| **Store binding accessor** | `_flush_face_data`, `_bind_vertex_textures`, `_set_face_samplers` | a public wrapper "bind face data + vertex views for program P / unbind" | One documented contract instead of a foreign module reaching into privates | The Worklight path calls the same code as today. Gate: `test_gl_face_data_layout.py`, `test_gl_shading.py` and `test_gl_texture.py` byte-identical. |
| **`Viewport` switch** | `render()` draw order, entries, Ghost ordering | a draw-state choice "Worklight / Lookdev" + Lookdev draw state per entry key (material values, as colour / finish are pushed today) | `Viewport` is already the single place that decides what is drawn; no new owner of geometry | Worklight path unchanged when off; D3 measured with Lookdev off to prove "no cost when off". |
| **Lookdev state** (src/mirai) | `OrbitCamera` (shared), `light_rig` functions, `view_state` pattern for defensive persistence | Lookdev rig, environment choice / rotation / intensity, background, exposure, material table; resolved per object and pushed down | Keeps the Artist's intent above the viewport (vision §2); the viewport never learns about objects | Never writes `DisplayState`'s Worklight fields or `ObjectMaterial`. |
| **UV decoupling** (`RenderMesh`) | `triangle_uvs` machinery | allocate UVs when *any* consumer needs them, not only the Worklight texture | Fixes I-7 without touching shading | Small; gated by `test_gl_texture.py` + `test_render_mesh_face_data.py`. |
| **Panel** (src/gui, AD-030) | imgui layer; panels hold no document state | Lookdev panel calling `Application` setters | AD-030 rule; no new input truth | Keys only after Manu approves them (keymap rule, CLAUDE.md). |

---

## 5. P1 Eye / Lookdev proof — proposal

**Form.** A disposable lab, e.g. `experiments/lookdev_eye_lab/` (name `PROVISIONAL`). It has its own pyglet window and
`run.py`, uses `Viewport(store_type=EyeLabStore)` with `EyeLabStore(GLRenderStore)`, and builds its eye parts as object
entries. It imports from `src/`; nothing moves the other way (AGENTS rule). **No change to Core, scene format, Morph,
Rigging, Skinning, SubD, `src/` or `config/keymap.json`.** No `Application`, so no tools, no history and no persistence.
NumPy is used for the environment; no new dependency. Tests live in the lab's own `tests/` (not in `pytest.ini`'s default
run).

### 5.1 Questions and how the lab answers them

| # | Question | How answered |
|---|---|---|
| Q1 | Convincing cornea reflection + Fresnel in the GL 3.3 path? | Techniques T-B / T-C on cornea treatments C2 / C3 (§5.3); Artist verdict at fixed views + orbit |
| Q2 | Environment reflections without modern GL? | Cube map RGBA16F (fallback RGBA8 / RGBM), `textureLod`; the probe (§5.7) on both PCs |
| Q3 | How should roughness affect the reflected environment? | prefiltered mips; compare the roughness → LOD mappings `lod = r·N` and `lod = √r·N`; roughness sweep on the chrome / grey spheres and the sclera |
| Q4 | Existing geometry and texture infrastructure enough? | eye parts as `core.Mesh` → `RenderMesh` → `GLRenderStore`; the iris colour through the existing face-corner UVs + texture path (`Mesh.set_face_uvs`, `Material.texture`) |
| Q5 | Legacy fallback? | C1 opaque (no transparent shell), RGBA8 environment, analytic softbox highlight (T-D) |
| Q6 | What to test on the main PC? | the same lab and probe; higher environment resolutions, float formats, seamless filtering, an MSAA FBO; timing at the main PC's display resolution |

### 5.2 Minimal scene and assets (all generated by the lab; nothing else needed)

- **Eye parts as three object entries:**
  - **Sclera:** sphere, poles turned sideways so no pole fan sits in the iris area.
  - **Iris:** a slightly concave annulus with a pupil hole, set behind the limbus. Planar UVs; a radial iris PNG written
    by the lab (zlib + struct, as `tests/test_obj_uvs.write_png`).
  - **Cornea:** a spherical cap with a smaller radius than the sclera, bulging in front of the iris and meeting the
    sclera at the limbus.
- **Reference spheres:** one chrome (roughness 0, F0 = 1) and one grey diffuse, as research §10 proposes.
- **Environment:** a procedural studio. A neutral backdrop gradient, one large rectangular softbox (key direction), one
  strip light (fill / rim) and a darker floor, in scene-linear values. Built in NumPy, prefiltered per mip on the CPU and
  cached to a file in the lab. There is no Gollum eye asset in the repository: `gollum_20k.obj` is one group without
  `vt` (VERIFIED, grep). A real Gollum eye is D-L2.
- **Background:** neutral grey, either solid or a gradient sampled from a blurred environment mip.

### 5.3 Techniques to compare

| Id | Specular / reflection | Purpose |
|---|---|---|
| T-A | the Worklight's Blinn–Phong as is (baseline, identical to today's look) | reference point |
| T-B | GGX (D) + Smith (G) + Schlick (F), direct key light only | does a microfacet lobe read better on the eye? |
| T-C | T-B + prefiltered cube reflection (`textureLod` by roughness) + Fresnel-weighted environment | the target technique |
| T-D | analytic softbox highlight (a rectangle evaluated in the shader), no cube map | fallback if cube maps fail on the 9800 GTX |

| Id | Cornea treatment |
|---|---|
| C1 | **Opaque fallback:** no cornea mesh; the iris / limbus fragments use the cornea's *analytic sphere normal* for the specular and environment terms |
| C2 | Additive shell: cornea drawn after the opaque parts, depth test on, depth write off, `blend(ONE, ONE)`, output = F·env + direct specular (no refraction, no darkening) |
| C3 | Fresnel-alpha shell: premultiplied `blend(ONE, ONE_MINUS_SRC_ALPHA)`, alpha = F |

Colour path (lab-local): sRGB decode of the iris PNG in the shader, linear shading, exposure, then clamp or Reinhard, then
sRGB encode in the shader. There is **no** global `GL_FRAMEBUFFER_SRGB`, so the HUD and text stay as they are.

### 5.4 Controls (lab-local keys, documented in the lab README; no BindingSet / keymap change)

- **Technique and treatment:** technique T-A…T-D, cornea C1…C3.
- **Light:** key azimuth / elevation / intensity (light-rig vocabulary).
- **Environment:** on / off, yaw, intensity.
- **Material:** exposure; roughness of sclera and cornea; F0 / IOR (cornea 1.376 → F0 ≈ 0.025); roughness → LOD mapping.
- **Environment texture:** resolution 64 / 128 / 256, format RGBA16F / RGBA8, seamless on / off.
- **Camera:** orbit, presets front / ¾ / profile.
- **Output:** screenshot to file; GPU timer read-out.

### 5.5 Expected result and acceptance criteria

**Artist (Manu), verdict KEEP / ITERATE / REJECT per technique and treatment, at the three preset views and while
orbiting:**

1. The cornea shows a crisp, recognisable softbox reflection that sits on the cornea, moves plausibly with the view and
   reads as "wet".
2. Fresnel is visible: the reflection is weaker facing the camera and stronger toward the cornea's edge.
3. Roughness reads: the sclera's reflection is broad and soft, the cornea's sharp.
4. The iris stays readable through the cornea at the front view (no wash-out).
5. No cube seams at rough levels; no distracting highlight flicker while orbiting (aliasing is expected without MSAA:
   record it, do not hide it).
6. C1 alone still reads as a wet eye on the legacy PC.

**Technical (agent, container [C] and reference PC [RPC]):**

- Every variant renders with `glGetError() == 0` and changes the image against T-A.
- Shader BRDF terms match a NumPy / Python reference within float32 tolerance (the `light_rig.shade` parity pattern).
- The roughness sweep blurs monotonically (variance of the chrome sphere's softbox footprint grows with roughness).
- `git diff --stat src tests config` is empty, and the full `tests/test_gl_*.py` run is unchanged.

### 5.6 Measurements

On both PCs, reference PC with "prefer maximum performance" (REFERENCE_HARDWARE §2):

- GL strings, the limits and formats of §5.7;
- GPU time per variant (`GL_TIME_ELAPSED`, p50 / p95 over N frames after warm-up) at 1024×768 and at 1920×1080, with the
  eye covering a fixed share of the frame (e.g. ≈ 50 %);
- CPU time per frame;
- prefilter time (one-off);
- environment texture memory, computed from size × format × mips and, where available, `GL_NVX_gpu_memory_info` before /
  after;
- screenshots at the fixed views.

Results go in `RESULTS_*.md` files in the lab, the repository's convention. For scale (computed, INFERRED): an RGBA16F
cube with mips is ≈ 1.0 MiB at 128² and ≈ 4.2 MiB at 256², small against the 481 MB Windows reports.

### 5.7 Driver questions that need a small test (probe mode of the lab, or a separate script)

1. Report `GL_MAX_TEXTURE_IMAGE_UNITS`, `GL_MAX_TEXTURE_SIZE`, `GL_MAX_CUBE_MAP_TEXTURE_SIZE`, `GL_MAX_SAMPLES`,
   `GL_MAX_COLOR_ATTACHMENTS`, `GL_MAX_DRAW_BUFFERS`, and the presence of `GL_EXT_texture_filter_anisotropic` and
   `GL_NVX_gpu_memory_info`.
2. Create, mipmap and sample an RGBA16F cube map with `textureLod`; check linear filtering and the speed against RGBA8.
3. Does `GL_TEXTURE_CUBE_MAP_SEAMLESS` change the image of a low mip (seam test pattern)?
4. Is an FBO with an RGBA16F colour target complete, and one with a sampled depth texture? (For later passes; not needed
   by T-A…T-D.)
5. Does an sRGB texture decode match the shader-side decode?
6. Is a multisample FBO + `glBlitFramebuffer` resolve available, at what sample counts, and at what cost? (Main PC
   first.)

### 5.8 What counts as failure, and the next alternative

| Failure | Next alternative |
|---|---|
| RGBA16F cube not filterable / slow / wrong | RGBA8 cube with RGBM or clamped LDR; or a 2D lat-long map with explicit LOD |
| Visible seams at rough mips (no seamless) | CPU edge fix-up of each prefiltered mip; fewer, larger mips |
| Cornea shell artefacts (sorting, depth, halos) | C1 opaque |
| Highlight aliasing / flicker | specular anti-aliasing (raise roughness from the normal's screen-space variance); MSAA FBO later (main PC first) |
| GGX no better than Blinn–Phong at eye scale | keep a normalised Blinn–Phong + Fresnel; record the verdict |
| GPU time unacceptable on the reference PC | T-D (analytic softbox) and a lower environment resolution; Lookdev quality tier "legacy" |

### 5.9 Main PC

The same lab, probe and views. Additionally: environment 256–512², RGBA16F / RGBA32F, seamless on / off, an MSAA FBO
(4× / 8×) with resolve, and timing at its native resolution. Its hardware must be recorded first (§6.3).

---

## 6. Hardware compatibility and performance risks

### 6.1 Measured facts (reference PC; source of truth REFERENCE_HARDWARE.md and the linked result files)

| Fact | Value | Label |
|---|---|---|
| GL / renderer | `3.3.0` / `GeForce 9800 GTX/9800 GTX+/PCIe/SSE2` (2026-10-11) | MEASURED [RPC] |
| Graphics memory | Windows reports 481 MB (not a GL measurement) | MEASURED [RPC] (system info) |
| GL test suite | 165 passed, incl. the O2 pixel gate, picking, texture (2026-11-13, Python 3.12.10, pyglet 2.1.19) | TESTED [RPC] |
| Face-data shading pass, full clock | ≈ 11.3 ms GPU with face data vs 1.9 ms without (≈ 9.4 ms for the face-data shading), 87.5k / 1024×768, mesh ≈ 13 % of the window | MEASURED [RPC] (RESULTS_O2_REFERENCE_PC, round 3) |
| GPU power state | the same frame costs ≈ 11 or ≈ 43 ms of GPU time depending on clocks; compare only with "prefer maximum performance" | MEASURED [RPC] |
| D3 frame (87.5k, 15 %, Morph + Skin) | pose 50.86 / 53.85 ms, weight 85.10 / 92.37 ms (p50 / p95); `on_draw` 19.6 ms of a pose frame | MEASURED [RPC] (AD-032 §12) |
| ID render | 1.14 ms (20k) / 10.3 ms (87.5k) GPU | MEASURED [RPC] |
| `GL_ARB_texture_buffer_object_rgb32` | absent | MEASURED [RPC] |
| NumPy | 2.2.6 under Python 3.12.10 only (no x86-64-v2) | MEASURED [RPC] |

### 6.2 Verified code capabilities vs documented-but-untested API capabilities

- Exercised and passing on the 9800 GTX driver: the TESTED [RPC] rows of §3.4.
- Core GL 3.3, never exercised in Mirai: cube maps (+ seamless), `textureLod`, float textures and targets, depth
  textures, sRGB, MSAA, `glBlitFramebuffer`, MRT writes. Status **OPEN** until §5.7 runs. Do **not** treat the vision's
  "Realistic" rows (§8 there) as verified.

### 6.3 Main PC: not recorded anywhere

There is no record of the main PC in the repository. REFERENCE_HARDWARE.md §1 says "Eine Aufrüstung ist geplant, das
Modell ist offen"; the vision and the research say the same. **VERIFIED (grep over `docs/`).** Needed before any dual-PC
claim:

- CPU model, cores and instruction set (x86-64-v2 / v3);
- RAM;
- GPU model, VRAM, driver version;
- `GL_VERSION`, `GL_RENDERER`, `GL_VENDOR`, `GL_SHADING_LANGUAGE_VERSION` and the extension list from the probe;
- OS build;
- display resolution(s), Windows scaling factor and refresh rate;
- Python version, and whether the pinned `numpy==2.2.6` is kept there (REFERENCE_HARDWARE §4 rule).

### 6.4 Risks

| Risk | Why | Label | Mitigation |
|---|---|---|---|
| **Fill rate at close-ups** | The face-data shading already costs ≈ 9.4 ms at ≈ 13 % coverage. A Lookdev close-up covers a multiple of that area, and every extra term (environment fetch, GGX, normal map) is per fragment. The real cost at full-screen coverage is unmeasured. | MEASURED (base) / OPEN (scaling) | Run `probe_shading_gpu.py` incl. `--size 1920 1080` on the RPC. Consider a depth pre-pass to avoid overdraw (the picker's face pass is a precedent). Decide whether Lookdev keeps the bilinear quad normal (D-L6). |
| **Untested GL features** | §3.4 | OPEN | §5.7 probe before building the lab around a format |
| **No anti-aliasing** | No MSAA anywhere; eye highlights alias | VERIFIED IN CODE | specular AA in the shader; MSAA FBO on the main PC first |
| **D3 still over the bar** | Lookdev shading adds to the GPU wait in deformation frames | MEASURED | Judge P1 on still / slow poses; measure D3 with Lookdev off (must be unchanged) and on (informational) |
| **Dense character without SubD** | `MAX_DERIVED_FACES` 25k; silhouettes of a 20k cage show facets in close-ups | VERIFIED IN CODE | Out of P1 scope; D5's re-measurement remains open |
| **pyglet unpinned, internals used** | `requirements-dev.txt` has bare `pyglet`, not in `requirements.txt` although `src/main.py` needs it. The store uses pyglet internals (`shader._uniform_setters`, `domain.buffer_attributes`, `vlist.start`, `domain.vao`, `buffer.commit()`, `index_buffer.set_region`). The reference PC runs 2.1.19. | VERIFIED IN CODE | Report only (no dependency change in this audit); a Lookdev pass adds more of the same coupling, so pinning deserves its own small decision |
| **VRAM** | 481 MB shared by all VertexLists (shared domain), face data and textures | MEASURED (total) / OPEN (use) | Environment ≤ ~4 MiB at 256² (INFERRED); read `GL_NVX_gpu_memory_info` if present |

### 6.5 Reproducible measurement setup for the Eye Proof

- One command per PC, PowerShell under `.venv312` on the reference PC, NVIDIA "prefer maximum performance".
- The lab's `--probe` mode prints the GL strings, limits and format results (§5.7), then renders every variant at the
  preset views and two window sizes for N frames after a warm-up, reporting GPU p50 / p95, CPU p50 and screenshots.
- It records the commit and `src/` tree hash, as the drag-cost probes do.
- Run the pending `python experiments\drag_cost\probe_shading_gpu.py` and `--size 1920 1080` in the same session, so the
  Lookdev numbers can be placed next to the Worklight's own shading cost.

---

## 7. Conflicts, gaps and outdated statements in existing documentation

Reported here only. The vision and research documents are **not** edited (task rule).

| # | Document, place | Statement | Finding | Label |
|---|---|---|---|---|
| 1 | RENDERING_TECHNOLOGY_RESEARCH §2.1; REFERENCE_HARDWARE §2 (navigation 2026-10-11) | "orbit/pan … about 1.2 ms per step and GPU draw about 0.56 ms" | Pre-O2 and on 21,875 V; the navigation probe did not clear depth, so it measured only part of a shaded pass (fixed 2026-11-11). Current figure: ≈ 9.4 ms of face-data shading per full pass at 87.5k / 1024×768 at full clock. REFERENCE_HARDWARE's O2 entry already notes the low orbit values; the research doc does not. | MEASURED |
| 2 | RENDERING_TECHNOLOGY_RESEARCH §2.2; AD-024 §7 ("it is not saved"), §9 Q-L3 ("later") | the Worklight is not stored as scene data | Since 2026-11-08 the Worklight (preset, space, edit), finish, camera and display are saved in the optional `"view"` section of the scene file (`src/mirai/view_state.py`), outside the Core format; still not Undo. AD-024 does not point to it. | VERIFIED IN CODE |
| 3 | RENDERING_VISION §8; RENDERING_TECHNOLOGY_RESEARCH §8 | cube-map reflections "Realistic" / "Yes" on legacy GL 3.3 | Plausible by spec but never exercised in Mirai; no cube map exists in the code. | VERIFIED IN CODE (absence) / OPEN |
| 4 | RENDERING_TECHNOLOGY_RESEARCH §2.2 | "Face-corner UVs and object texture display already exist" | True, but: one texture per object, base colour only, no sRGB handling (AD-026 §7), texture withheld for highlighted objects, UVs on the GPU only while a texture shows (I-7). | VERIFIED IN CODE |
| 5 | RENDERING_VISION §1 / §5.1, research §10 | Gollum eyes first; benchmark scene with blink / jaw morphs | No eye geometry, no UVs and no such morph targets exist in the repository's Gollum assets (`gollum_20k.obj`: 1 group, 0 `vt`; `gollum.obj` byte-identical per REFERENCE_HARDWARE). P1 needs a synthetic eye or an asset from Manu. | VERIFIED |
| 6 | VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH §2.2 (table "Hintergrund") | production clear colour `(0.05, 0.05, 0.08)` | Now `(0.1, 0.1, 0.11)` and still hard-coded; the background slice (§7 Slice 3) was never built. Historical table, not marked as such. | VERIFIED IN CODE |
| 7 | REFERENCE_HARDWARE §2 ("Belegt im Code") | all shaders `#version 330 core` (… `playground/window.py`) | Still true for `src/`; the Playground is archived; the textured program also needs a geometry shader (GL 3.2) and imgui uses `#version 330`. Minor. | VERIFIED IN CODE |
| 8 | RENDERING_VISION §6 "Realtime backend" | candidate infrastructure incl. `material.py` | Reusable as Worklight infrastructure; its packet is the *displayed* colour (selection tint, Reference blue), not an Artist material (I-6). | VERIFIED IN CODE |
| 9 | `requirements.txt` / `requirements-dev.txt` | pyglet unpinned and not listed as a runtime dependency | `src/main.py` and the store need it, and use its internals; the reference PC runs 2.1.19. | VERIFIED IN CODE |
| 10 | ARCHITECTURE_PERFORMANCE_AUDIT_2026-11-10 §C.1 | `MixSurface` / `SkinSurface` hold full `core.Mesh` copies | Superseded by O1 (tables) and O3 (arrays), as the audit's own addenda say. The §C diagram should not be read as current. | VERIFIED IN CODE |
| 11 | RENDERING_VISION §6 "Lookdev Scene Adapter … tracks dirty causes" | implies a new adapter layer | Geometry, transform and material dirtiness are already tracked by `Viewport` / `RenderMesh`. Only Lookdev-own state (environment, rig, Lookdev material, background, exposure) needs new tracking, and that is draw state. | VERIFIED IN CODE / INFERRED |

---

## 8. Explicit decisions required from Manu

**Decided (Manu, chat, 2026-11-13; entered by the agent).** For P1:

| Decision | Choice | Manu's reason |
|---|---|---|
| D-L1 | **Yes:** P1 is a separate experiment | "Keine Änderungen an Mirai Production" |
| D-L2 | **Synthetic** eye, generated by the lab | "Kontrollierte Geometrie, keine Abhängigkeit von vorhandenen Assets" |
| D-L4 | **Procedural studio** environment | "Reproduzierbar, keine HDRI-Dateien oder zusätzlichen Abhängigkeiten" |
| D-L5 | **Deferred** | "Der physische Haupt-PC ist im Repository weiterhin nicht dokumentiert." D-L5 does not block P1: P1 is developed and measured on the reference PC first. |

Deliberately **not** decided yet (Manu: "Es wäre ein Fehler, diese Produktentscheidungen jetzt schon endgültig
festzulegen"):
- **D-L3:** P1 may test a scene-linear colour path inside its own lab; its integration is decided later.
- **D-L6:** stays open. The probe shows a clear technical tendency toward plain interpolated normals
  ([results](../../experiments/lookdev_gpu_probe/RESULTS_REFERENCE_PC_2026-11-13.md) §6).
- **D-L7:** after the Eye Proof.
- **D-L8:** P1 measures the eye first; the large character comes later.
- **D-L9:** keys only after the practical test.

The original questions follow.

Needed for **P1**:

- **D-L1** — Build P1 as a disposable lab under `experiments/` (standalone window, no app integration, no `src/`
  change)? Agent recommendation: yes.
- **D-L2** — Eye asset for P1: a synthetic eye generated by the lab (recommended), or a modelled eye set (sclera / iris /
  cornea as OBJ files) from you?
- **D-L4** — Environment for P1: a procedural studio (recommended; no file formats, no dependency) or a specific HDRI
  (needs an `.hdr` reader, feasible in NumPy without a new dependency)? This answers the vision's gate "fixed studio
  cubemap, HDRI, or both" for P1 only.
- **D-L5** — Main PC: when it exists, record it in REFERENCE_HARDWARE.md (list in §6.3). Until then, P1 results are
  reference-PC only.

Needed **before P2** (after the P1 verdict):

- **D-L3** — Colour pipeline for Lookdev: scene-linear shading with sRGB decode / encode and exposure (recommended for
  Lookdev only; the Worklight stays display-referred and unchanged).
- **D-L6** — What Lookdev is in the product:
  - a display mode of the same viewport (toggle), or a separate workspace;
  - which overlays stay visible (wire, selection, gizmo, HUD);
  - whether tools stay usable in Lookdev;
  - whether Lookdev respects Hide / Isolate;
  - whether it must keep the Worklight's "no visible triangles" bilinear quad shading (expensive per fragment, §6.4) or
    may use plain interpolated normals or the SubD surface.
- **D-L7** — Lookdev material: per object first (recommended) or per face region; where it is stored (a Core field as
  in AD-024, with a format version, or elsewhere). AD-024 rejected ObjectId-keyed side tables because of ID remapping on
  load.
- **D-L8** — Must Lookdev run at the D3 bar while deforming on the reference PC, or is it judged on still / slow poses
  there (with the fluid target on the main PC)? This sets the GPU budget.
- **D-L9** — Keys for Lookdev: only after a practical test, as `config/keymap.json` requires.

---

## 9. Practical next-step sequence after P0

1. **Probe (agent writes, Manu runs on the reference PC; later on the main PC).** GL limits / formats / features of
   §5.7, plus the pending `probe_shading_gpu.py` (1024×768 and 1920×1080). No `src/` change. *Output:* a results file;
   which environment format and fallback P1 starts from.
2. **P1 lab (agent, container first).** Eye parts, environment generation + prefilter, T-A…T-D × C1…C3, Python-reference
   parity tests, screenshots; `src/` diff empty.
3. **P1 runs (Manu).** Reference PC (and main PC if available): `--probe` numbers + practical test with
   KEEP / ITERATE / REJECT per technique.
4. **P1 report and decisions** D-L3, D-L6 … D-L8.
5. **AD for the Lookdev seam (P2)**, covering:
   - pass boundary (§4.2);
   - depth / overlay contract (I-1);
   - attribute-location rule (I-2);
   - Lookdev state ownership and persistence;
   - UV decoupling (I-7);
   - gates.
6. **P2 implementation** behind a draw-state switch. Gates:
   - Worklight pixel gates byte-identical (`test_gl_face_data_layout.py`, `test_gl_shading.py`, `test_gl_texture.py`);
   - full GL suite and picking tests;
   - D3 unchanged with Lookdev off;
   - Lookdev numbers recorded on both PCs.
7. **P3 candidates, only after P2 verdicts:** SH diffuse vs Key + Fill, one shadow map, skin wrap / backscatter.

---

## 10. Recommendation — the safest and most useful next technical step

**Run a small GL capability and fill-rate probe on the reference PC before building the eye lab.** It can be the lab's
`--probe` mode or a standalone script under `experiments/`. Run it together with the already-written
`probe_shading_gpu.py --size 1920 1080`.

Why this first:

- **It is the cheapest step that removes the two unknowns that decide everything after it:**
  - whether the 9800 GTX driver handles what P1 needs (half-float cube maps, `textureLod`, seamless filtering, sRGB) —
    never used in Mirai;
  - how much GPU time a full-frame fragment shader already costs on this card — today only known at ≈ 13 % coverage.
- **It changes nothing in production.**
- **It turns the vision's "Realistic" rows into measurements.**
- **It tells P1 which environment format and which fallback to build around**, instead of discovering a driver limit
  after the lab is written.
- **The same probe, run later on the main PC, fills the hardware record the dual-PC goal needs.**

Not started here, per the task.

---

## Appendix — sources and tests referenced

- Code:
  - `src/main.py` (`create_window` 420, `on_resize` 513, `on_draw` 712, tick 828–834);
  - `src/viewport/viewport.py`, `render_mesh.py`, `packed_geometry.py`, `gl_render_store.py`, `gpu_picker.py`,
    `light_rig.py`, `material.py`, `gl_line_overlay.py`;
  - `src/mirai/application.py` (557, 717–737, 2155, 4215, 5219), `surface_positions.py`, `surface_chain.py`,
    `scene_objects.py`, `controllers/objects.py` (1011, 1058), `view_state.py`, `viewport/display.py`,
    `viewport/camera.py`, `viewport/look_controls.py`, `subdivision/preview.py`;
  - `src/core/scene.py`, `serialization.py`, `mesh.py` (UV API);
  - `src/gui/imgui_layer.py`;
  - pyglet 2.1.19 `window/__init__.py`, `image/__init__.py` (downloaded for reading only, not installed).
- Tests:
  - `tests/test_gl_face_data_layout.py`, `test_gl_shading.py`, `test_gl_texture.py`, `test_gl_gpu_picking.py`,
    `test_gl_morph_picking.py`, `test_gl_line_overlay.py`;
  - `test_packed_geometry.py`, `test_stage_arrays.py`, `test_render_mesh_incremental.py`,
    `test_render_mesh_face_data.py`, `test_surface_finish.py`.
- Results:
  - `experiments/drag_cost/RESULTS_O2_REFERENCE_PC_2026-11-11.md`;
  - `RESULTS_O3_STAGE1_REFERENCE_PC_2026-11-13.md`;
  - `RESULTS_O3_STAGE2_REFERENCE_PC_2026-11-13.md`.
- This audit ran no tests and took no measurements. Container caveat: the session's environment has no pyglet and
  NumPy 2.5.3 instead of the pinned 2.2.6, so a run here would not have been representative anyway.

---

## Addendum — 2026-11-13: §9 step 1 run on the reference PC

The capability and fill-rate probe of §9 step 1 / §10 is
[`experiments/lookdev_gpu_probe/`](../../experiments/lookdev_gpu_probe/README.md). Manu ran it on the reference PC
([`RESULTS_REFERENCE_PC_2026-11-13.md`](../../experiments/lookdev_gpu_probe/RESULTS_REFERENCE_PC_2026-11-13.md)).
**MEASURED [RPC]** unless marked otherwise; the audit body above is unchanged.

- **§5.7 Q1:**
  - `GL_MAX_TEXTURE_IMAGE_UNITS` 32 (combined 96);
  - texture and cube size 8192;
  - `GL_MAX_SAMPLES` 16;
  - 8 colour attachments, 8 draw buffers;
  - `GL_EXT_texture_filter_anisotropic` present (16×);
  - `GL_NVX_gpu_memory_info` present: 512 MiB dedicated.
- **§5.7 Q2:**
  - RGBA16F (and RGBA8, RGBA32F) cubes with mips are stored, sampled, mip-selected (`textureLod`) and filtered
    correctly.
  - RGBA16F filters at RGBA8 speed. One lookup over a full 1920×1080 frame costs ≈ 0.1 ms.
- **§5.7 Q3:** `GL_TEXTURE_CUBE_MAP_SEAMLESS` works across edges but not at cube corners, where a tap comes from one
  face. That leaves seams at the 4², 2² and 1² levels. INFERRED from an emulation fitted to the measurement:
  equalizing the corner texels per level and not using 1×1 removes them. This replaces the fallback "CPU edge fix-up"
  of §5.8 by a corner fix-up.
- **§5.7 Q4:** an RGBA32F colour renderbuffer is complete (the probe's read-back target). Depth textures were not
  tested.
- **§5.7 Q5 and Q6** (sRGB, MSAA): not tested, OPEN.
- **§6.4 fill rate:** the Worklight pass at a frame-filling close-up of the 87.5k fixture costs **16.1 ms (1024×768)
  and 26.8 ms (1920×1080)**, and 2.9 / 5.0 ms without face data. Cost per covered pixel falls with coverage, so the
  13 % figure cannot be extrapolated linearly. This is input for D-L6 and D-L8.
- **§2.2:** pyglet's default context on the reference PC is a **core** profile, as read from the source.

## Addendum — 2026-11-14: §9 step 2, the P1 lab (container)

The Eye Proof lab is [`experiments/lookdev_eye_lab/`](../../experiments/lookdev_eye_lab/README.md), built as §5
proposes (D-L1, D-L2, D-L4; D-L3 / D-L6 … D-L9 stay open, the lab's colour path and normals are lab-local). It draws the
eye parts as production object entries through `Viewport(store_type=EyeLabStore)`; T-A is the unchanged production
draw (pixel-identical, tested), T-B … T-D draw the same VertexList with a lab program. The environment follows
the reference PC's recipe (RGBA16F 128², CPU prefilter in `cube_math`'s face order, corners equalized, chain to 2²,
seamless on). **TESTED [C] only**
([`RESULTS_CONTAINER_2026-11-14.md`](../../experiments/lookdev_eye_lab/RESULTS_CONTAINER_2026-11-14.md)): every variant
renders without GL error, the shader terms match the NumPy reference in float32, the roughness sweep blurs
monotonically, hygiene clean. Every GPU time, the corner-seam fix-up on the 9800 GTX and the Artist verdict are
**OPEN** until §9 step 3 (Manu's run; commands in the lab README). The audit body above is unchanged.

**Reference PC, 2026-11-14 (§9 step 3, probe part; MEASURED [RPC],
[`RESULTS_REFERENCE_PC_2026-11-14.md`](../../experiments/lookdev_eye_lab/RESULTS_REFERENCE_PC_2026-11-14.md)):**

- All six probe checks PASS on the 9800 GTX, including shader / NumPy parity on NVIDIA's Cg compiler.
- **Corner seams:** without the fix-up 0.009 / 0.062 / 0.169 at 4² / 2² / 1². With corners equalized and the chain
  ending at 2², 0 at every level. This replaces the INFERRED fix-up of the 2026-11-13 addendum by a measurement.
- **GPU time per frame,** eye ≈ 50 % of the frame, background included:
  - T-C (target): 1.0–1.3 ms at 1024×768 and 2.4–2.9 ms at 1920×1080;
  - T-A (Worklight, quad normal): 3.6–3.8 ms and 6.9 ms;
  - T-D (analytic softbox): 1.8–2.4× T-C, so it is no performance fallback.
- **CPU prefilter:** 40 s per 128² chain on the Q9550 (cached afterwards).
- **Open:** the Artist verdict (§5.5); D-L3, D-L6 … D-L8 have new input (results file §4) but are not decided.
