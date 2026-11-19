# LookDev Room P2: Technical Appendix

**Status:** PROPOSAL (decisions LD-D1 … LD-D14 by Manu, 2026-11-19, in the main proposal's §0), a companion to
[LOOKDEV_P2_ARCHITECTURE_UX_PROPOSAL_2026-11-19.md](LOOKDEV_P2_ARCHITECTURE_UX_PROPOSAL_2026-11-19.md). It is
documentation only, at `origin/main` @ `a3bfcc0`, and uses the same evidence tags: [V] verified, [M-RPC] / [M-C]
measured, [P] proposal, [E] estimate, [O] open for Manu.

---

## A. Reconciliation with the Rendering Vision and the P0 audit

| Source | Statement / recommendation | State at `a3bfcc0` | Consequence for P2 |
|---|---|---|---|
| Vision §3.1 | Worklight is not a rendering system; AD-024 not to be expanded | holds [V] | LookDev is separate state and a separate pass (proposal §10) |
| Vision §3.2 | LookDev may reuse window, camera, mesh draw, overlays, GL context | holds; the Paint Room proves the same-window room [V] | room form (proposal §2) |
| Vision §5.1 | eyes first, cubemap reflection in the realtime baseline | eyes done in production with an **analytic** studio (AD-033 §11, deviation 1: no prefilter at start-up) | analytic studio kept for visible reflections; cube in P3 (§8) |
| Vision §5.5 | SH for diffuse, never for sharp reflections | holds | SH9 for diffuse only (proposal §8.1) |
| Vision §9 P1 | disposable eye proof | done, frozen as the oracle (AD-033 §8) | the lab is not touched |
| Vision §9 P2 | production integration incl. eyes, quality tiers, gates | eye integration already happened under the Worklight; quality tiers not needed for M1 | P2 re-cut into LD-0 … LD-3 (proposal §13) |
| Vision §9 P3 | lights, SH, shadows, skin, eye transmission together | too large for one step | split: lights + SH + skin basics in M1; shadows, maps, cube in P3 |
| P0 §1.6 / §4.2 | pass outside `GLRenderStore.draw()`, one public binding accessor | the pass pattern is proven by `EyePass`; the eye needed **no** accessor (AD-033 §11) | LookDev needs only the UV lookup: one semantic accessor (proposal §10.3); face data stays private |
| P0 §3.2 | separate flat Artist material record, presets, resolved per object | holds | `LookMaterial` (proposal §4), persisted in LD-2 |
| P0 §3.2 / D-L7 | persistence is a decision; ObjectId side tables rejected (AD-024 §1.2) | AD-033, AD-035, AD-036 and AD-037 all chose Core fields with version-by-content | Core field v15 in LD-2; a session-only table in M1 (not persisted) |
| P0 §3.5 I-7 | UVs on the GPU only with the Worklight texture | still open (`render_mesh.py:650`) [V] | the UV request flag (proposal §10.3) |
| P0 §2.10 | background hard-coded | still `main.py:715` [V] | LookDev background from state; Worklight constant unchanged |
| P0 §5.7 / addenda | cube RGBA16F works; corner seams fixed; CPU prefilter 25 / 40 / 71 s | measured [M-RPC] | cube deferred; GPU prefilter probe (LD-0 c) |
| P0 §8 D-L3 | linear colour path for LookDev only | the eye built a *mixed* path; never decided for the whole character | one linear pipeline incl. the eye's LookDev variant (proposal §7, §11) |
| P0 §8 D-L6 | display mode or workspace; overlays; tools; Hide; quad normal | Eye: "im Worklight-Modus"; the rest open | room, tools usable, Hide respected, interpolated normals (proposal §2, §9); → LD-D1 / LD-D2 decided 2026-11-19 |
| P0 §8 D-L8 | deformation budget | open | LD-D10 narrows it (still / slow poses ≥ 30 fps); → decided 2026-11-19 as target and measurement criterion |
| P0 §6.3 / D-L5 | main PC unknown → reference PC is the main PC | holds (REFERENCE_HARDWARE §1) | every budget is the 9800 GTX's |
| P0 §3.1 | SubD unavailable above 25,000 derived faces | holds; Gollum at level 1 (AD-037 §10.3) | documented limitation; LookDev adds no reduction |
| P0 §7 #11 | a "LookDev Scene Adapter" layer is not needed | holds | `ObjectController.sync_views` resolves `LookDraw` as it resolves `EyeDraw` |

---

## B. Measurements used

All from results files in the repository. Nothing new was measured for this proposal.

| # | Measurement | Value | Source |
|---|---|---|---|
| B1 | GL context | 3.3.0 core, NVIDIA Cg compiler, 32 fragment texture units, cube / 2D up to 8192², aniso 16×, `GL_MAX_SAMPLES` 16, 512 MiB (≈ 395 MiB free at start) | [M-RPC] `experiments/lookdev_gpu_probe/RESULTS_REFERENCE_PC_2026-11-13.md` |
| B2 | Cube RGBA8 / 16F / 32F with mips, `textureLod`, filtering | correct; 16F as fast as RGBA8; one lookup over 1920×1080 ≈ 0.1 ms | same |
| B3 | Seamless cube filtering | edges yes, corners no; fixed by corner equalization + chain to 2² (0 at every level) | [M-RPC] `experiments/lookdev_eye_lab/RESULTS_REFERENCE_PC_2026-11-14.md` |
| B4 | CPU prefilter per chain | 25 s (64²), 40 s (128²), 71 s (256²) | [M-RPC] REFERENCE_HARDWARE §2 |
| B5 | Worklight pass, 87.5k, full-frame close-up | 16.1 / 26.8 ms with face data, 2.9 / 5.0 ms without (1024×768 / 1920×1080); framed D3 view 11.2 / 14.7 ms | [M-RPC] lookdev_gpu_probe 2026-11-13 |
| B6 | Lab eye, ≈ 50 % of frame | T-C (cube) 1.0–1.3 / 2.4–2.9 ms; T-D (analytic) ≈ 2× T-C; Worklight on the same eye 3.6–3.8 / 6.9 ms | [M-RPC] eye lab 2026-11-14 |
| B7 | Production eye preview, head + 2 eyes | framed 1.3 / 2.1 ms; close-up 2.7 / 4.8 ms; less than preview off | [M-RPC] `experiments/drag_cost/RESULTS_EYE_PREVIEW_REFERENCE_PC_2026-11-16.md` |
| B8 | Eye look (phase 3) | +0.92 / +2.28 ms Eye Lab view; ≤ +3.36 ms worst view | [M-RPC] `RESULTS_EYE_LOOK_REFERENCE_PC_2026-11-16.md`, AD-033 §17 |
| B9 | Eye look + iris (phases 3 + 4) | ≤ +3.8 ms in every measured view (run 2) | [M-RPC] AD-033 §18 |
| B10 | D3 frame, 87.5k, morph + skin | pose 50.86 / 53.85 ms p50 / p95; `on_draw` ≈ 19.6 ms of a pose frame | [M-RPC] AD-032 §12 |
| B11 | Sclera map cost | **not measured** on the reference PC | AD-035 §6 |
| B12 | Paint Room bars on the shown surfaces | P-A … P-G pass (fourth run) | [M-RPC] AD-037 §10.8e |
| B13 | Gollum head sizes | cage 2,234 / 2,492 faces with UVs; SubD level 1 ≈ 9,002 faces; level 2 36,008 (over the cap) | [V] `scenes/Gollum_Head_05.mirai.json`, AD-037 §10.3 |

**Not measured, needed:**
- the LookDev skin pass at full coverage (LD-0 a);
- the first UV-request toggle on Gollum (LD-0 b);
- render-to-RGBA16F cube face (LD-0 c);
- a sampled depth texture (LD-0 d);
- first-use compile time of an eye variant on the Cg compiler;
- sRGB texture decode and MSAA on this driver (P0 §5.7 Q5 / Q6; not needed by the proposal).

---

## C. Shader and variant considerations

### C.1 `LOOKDEV_LIGHT_LIB` (GLSL source string, shared by the skin pass and the eye LookDev variant) [P]

```glsl
// uniforms: resolved once per frame by the LookDev state (one dict for both passes)
uniform vec3  u_ld_key_dir, u_ld_key_color;  uniform float u_ld_key_wrap, u_ld_key_size;
uniform vec3  u_ld_fill_dir, u_ld_fill_color; uniform float u_ld_fill_wrap;
uniform vec3  u_ld_rim_dir, u_ld_rim_color;
uniform vec3  u_ld_sh[9];                 // SH9 irradiance, linear RGB, already convolved with the cosine lobe
uniform mat3  u_ld_env_rot;               // world -> studio frame (studio rotation)
uniform float u_ld_env_intensity, u_ld_exposure;   // exposure as a linear factor 2^EV
// studio rectangles as uniform arrays (count fixed per preset family), replacing the eye's compile-time constants

vec3  srgb_decode(vec3 c);                // exact inverse of the existing srgb_encode
vec3  sh9_irradiance(vec3 n_world);       // evaluated with n rotated by u_ld_env_rot
vec3  studio_radiance(vec3 d_world, float roughness);   // td_env's algorithm, parametric
vec3  lookdev_diffuse(vec3 n, vec3 wrap_rgb);           // key/fill/rim wrap + sh9
vec3  lookdev_output(vec3 linear_rgb);    // exposure -> tone curve -> srgb_encode; called once per pixel
```

- Names are `PROVISIONAL`. The `u_ld_` prefix keeps them disjoint from the 7 Worklight uniforms that `Viewport.render()`
  pushes to every store each frame (P0 I-11).
- Each function gets a NumPy twin in a GL-free module (pattern: `viewport/eye_optics.py` ↔ `eye_shaders.py`) and a GPU
  parity case.
- **SH9:** the CPU projects `studio_radiance(d, 1.0)` (or the unblurred studio) over a fixed direction set, then
  convolves with the clamped cosine (Ramamoorthi–Hanrahan constants). It costs milliseconds for some thousands of
  directions [E]. Recomputed only when the studio *content* or its intensity changes; rotation is applied to the normal.
- **Tone curve candidates** (chosen in M1 against Gollum):
  - luminance Reinhard (`L/(1+L)`, hue-preserving);
  - a short filmic shoulder with a linear toe.

  Not per-channel Reinhard on skin, because it desaturates highlights toward white. Note that the eye's current
  `display_add` uses per-channel Reinhard on reflections only. In the LookDev variant that disappears into the single
  `lookdev_output`.

### C.2 The skin program [P]

- **VS:** `gl_Position = u_proj * u_view * u_model * vec4(position, 1)`, identical to the Worklight's (P0 I-1).
  `v_world_pos` and `v_normal` as in `TEXTURED_*`.
- **GS:** a pass-through with barycentrics and `gl_PrimitiveID = gl_PrimitiveIDIn`. The UV is
  `texelFetch(u_triangle_uvs, gl_PrimitiveID * 3 + i)`, as the textured Worklight program reads it; a value below
  −1e29 means unmapped (`gl_render_store.py` textured source).
- **FS:**
  1. albedo from the colour or the map (decoded);
  2. N from the interpolated normal, plus specular AA;
  3. `lookdev_diffuse` × albedo;
  4. GGX × lights;
  5. `studio_radiance(reflect, roughness)` × the split-sum Fresnel term (the lab's analytic term is in
     `shaders.LIB_SRC`, already ported for the eye);
  6. backscatter;
  7. `lookdev_output`.
- **Variants** (defines, compiled lazily): `ALBEDO_MAP` 0/1, `ENV_SPEC` 0/1 (a quality knob), later `NORMAL_MAP`,
  `SHADOW`. M1 uses at most 4 programs.
- **Specular AA:** `α'² = clamp(α² + k · (|dFdx(N)|² + |dFdy(N)|²), 0, 1)` with `k` ≈ 0.25–1 (Kaplanyan / Tokuyoshi
  style). It needs only derivatives, which pass on the reference PC.

### C.3 The eye pass `LOOKDEV` variant [P]

- **Program key:** today 8 values (`VARIANT`, `LIMBUS_LEVEL`, `REFLECTION`, `IRIS_FIT`, `DEBUG_KIND`, `LOOK`, `IRIS`,
  `SCLERA_MAP`; `eye_pass.py:220`, `eye_shaders.py:1025–1041`). `LOOKDEV` makes 9.
- **Lazy compilation:** only variants that are drawn are compiled. The LookDev room usually needs two (left / right eyes
  usually share one): `(V2, Lx, studio, fit, LOOK, IRIS, SCLERA_MAP?, LOOKDEV)`.
- **Blocks:** the `#ifdef LOOKDEV` blocks sit only where §7.2 of the proposal names:
  - the diffuse call;
  - the three albedo reads (sclera colour / map, limbal tissue at the cornea entry, iris image);
  - `td_env` → `studio_radiance`;
  - the `display_add` sites (`eye_shaders.py:821`, `823`, `897`) → linear accumulation;
  - the final write (`:907`) → `lookdev_output`.
- **Source gate:** `_without(body, "LOOKDEV")` removes them for every Worklight variant, so the digest
  `PINNED_SOURCES_SHA256` (`tests/test_gl_eye_pass.py:1099`) stays the same. A **new** pinned digest is added for the
  LookDev variants.
- **Uniform discipline:** in the LookDev variant the 7 Worklight uniforms are not declared. `values.update(light)`
  (`eye_pass.py:483`) is fed the LookDev dict instead. The pass reads the active uniforms per program, AD-033 §15.
- **Units:** the eye uses 1 iris, 2 noise, 3 key table, 4 sclera map (`eye_pass.py:37–43`). SH9 and the studio are
  uniforms, so no new unit is needed. The P3 cube would take unit 5.

### C.4 GL state and resources [V] / [P]

| Rule | Source | LookDev pass |
|---|---|---|
| depth test on, depth write on, blend off, back faces culled, polygon offset (1, 1) when `store.polygon_offset` | `eye_pass.py:521–529`, `gl_render_store.py:1053` | same |
| afterwards: offset, cull and depth test off, used units unbound, unit 0 active, program stopped | `eye_pass.py:531–548` | same |
| no FBO bound across `on_draw` steps | P0 I-4 | no FBO in P2; the LD-2 capture binds nothing (back buffer + `glReadPixels`) |
| unit 0 = pyglet / imgui | P0 I-5 | untouched |
| no write to store buffers | P0 I-10 | read only |

---

## D. Invariants I-1 … I-12 (P0 §3.5) mapped to the proposal

| # | Invariant | How the proposal keeps it |
|---|---|---|
| I-1 | overlay depth contract | same transform and polygon-offset rule; depth test (D below) |
| I-2 | attribute locations | taken from `GLRenderStore.program().attributes`, as `EyePass` does |
| I-3 | shared vertex domain | the pass uses `vertex_list()` per draw and never caches buffer names |
| I-4 | GL state discipline | C.4 |
| I-5 | unit 0 | C.3, C.4 |
| I-6 | the packet is the displayed colour | `LookDraw` resolved from the object (proposal §10.4) |
| I-7 | UVs follow the Worklight texture | the UV request flag (proposal §10.3) |
| I-8 | Hide / Isolate via degenerate triangles | respected automatically |
| I-9 | transparency order | opaque only; Ghosts keep the Worklight order |
| I-10 | read-only consumption | no buffer writes; revisions untouched |
| I-11 | Worklight light pushed to every store | `u_ld_` uniforms, a separate dict |
| I-12 | frame budget | LD-0 / LD-1 measurements; D3 with LookDev off unchanged |

---

## E. Test matrix

| # | Test | Kind | Stage | Pass criterion |
|---|---|---|---|---|
| E1 | Worklight pixel gates `test_gl_face_data_layout.py`, `test_gl_shading.py`, `test_gl_texture.py` | GL | LD-1 | unchanged, byte-identical |
| E2 | `test_gl_eye_pass.py`: `PINNED_SOURCES_SHA256`, Worklight match, preview off = Worklight | GL | LD-1 | unchanged |
| E3 | Lab oracle `experiments/lookdev_eye_lab/tests/test_oracle_production.py` | headless | LD-1 | unchanged |
| E4 | New pinned digest of the eye `LOOKDEV` variants | headless | LD-1 | pinned |
| E5 | `LOOKDEV_LIGHT_LIB` twins: decode, curve, SH9 evaluation, studio radiance, GGX | GL parity | LD-1 | float32 tolerance |
| E6 | SH9 projection vs numerical integral of the studio | headless | LD-1 | ≤ 1 % irradiance error [P] |
| E7 | Grey-card calibration skin pass vs eye sclera in LookDev | GL | LD-1 | ≤ 2/255 |
| E8 | Depth contract: wire over the LookDev pass vs over the Worklight | GL | LD-1 | identical line pixels (or depth within 1 ulp) |
| E9 | R-1: enter / leave / switch rooms in a pose with morph mix, gaze mode, SubD on | headless | LD-1 | pose, weights, current targets, gaze, SubD bit-identical |
| E10 | Room display restore; save inside the room writes the restored `view.display` | headless | LD-1 | as the Paint Room tests |
| E11 | Refusals: Paint Room open, exclusive session, Eye Lab (LD-D14) | headless | LD-1 | status line, no state change |
| E12 | UV request flag off everywhere = today (`test_render_mesh_face_data.py`, `test_gl_texture.py`) | headless + GL | LD-1 | unchanged |
| E13 | Selected painted head keeps its albedo in LookDev (I-7 / `_shown_texture` conditions) | GL | LD-1 | albedo drawn |
| E14 | Each pass leaves GL state as found | GL | LD-1 | the `test_gui_imgui_window.py` pattern |
| E15 | Picking unchanged in the room (`test_gl_gpu_picking.py`, `test_gl_morph_picking.py` under LookDev) | GL | LD-1 | same IDs |
| E16 | D3 with LookDev off: the Modelling Room unchanged (LD-D10, decided 2026-11-19) | probe | LD-1 | within noise of the last reference run |
| E17 | `LookMaterial` contract tests: validation, v15 by content, a file without looks is the same text, round trip, Undo, duplicate, mirror, `replace_scene` | headless | LD-2 | as `test_paint_format.py` |
| E18 | `view.lookdev` defensive load (bad values skipped) and the documented drop by a capture without the section | headless | LD-2 | skipped list; limitation pinned |
| E19 | Viewport capture writes the LookDev view without overlays | GL | LD-2 | PNG equals a render without overlays |
| E20 | Quality manager never changes mesh, SubD, morph, picking or materials | headless | LD-3 | structurally: it outputs only defines / uniforms |

---

## F. Expected touch list for LD-1 (for the AD; nothing is changed now)

| Layer | Expected files |
|---|---|
| Viewport | new `src/viewport/lookdev_pass.py`, `lookdev_shaders.py`, `lookdev_optics.py` (NumPy twins); `viewport.py` (shading switch, `look=` entries, background); `render_mesh.py` (UV request flag); `gl_render_store.py` (`bind_triangle_uvs` / `unbind_triangle_uvs`); `eye_shaders.py` / `eye_pass.py` (`LOOKDEV` blocks) |
| App | `src/mirai/controllers/lookdev_room.py` (`PROVISIONAL`: room frame, saved display, session-only materials); `controllers/objects.py` (`LookDraw` in `sync_views`); `application.py` (`open_lookdev` / `close_lookdev`, setters); `viewport/display.py` (shading value) |
| GUI | `src/gui/lookdev_model.py` + `lookdev_panel.py`; `imgui_layer.py` (window block); `menus.py` (SPACE row) |
| Main | `src/main.py` (clear colour behind a getter, Worklight constant unchanged) |
| Not touched in LD-1 | `src/core/`, `core/serialization.py`, `view_state.py`, `config/keymap.json`, `experiments/lookdev_eye_lab/` |
