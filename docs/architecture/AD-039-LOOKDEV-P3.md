# AD-039 — LookDev P3: key shadow map, eye shadow, dual lobe, thickness, environment cube, region materials, maps

**Status:** **PROPOSED (2026-11-22, Architecture Gate).** No `src/` change in this AD's session. It needs Manu's
acceptance (with or without changes to §13) before slice S1 starts. The number AD-039 follows AD-038; AD-034 was never
assigned (no file, no reference, no commit in the history). New class, file and panel names stay `PROVISIONAL` until
built.
**Why now:** Manu, 2026-11-21: „LookDev P3 vor LD-3 vorziehen“
([proposal §0.1](../design/LOOKDEV_P2_ARCHITECTURE_UX_PROPOSAL_2026-11-19.md), [AD-038](AD-038-LOOKDEV-ROOM-M1.md)
§13.6). P3 needs its own AD before any `src/` change and fixes the order of the P3 items.
**Basis:** the proposal §0.1, §4.4, §6, §8, §9, §12, §13, §15 and its
[technical appendix](../design/LOOKDEV_P2_TECHNICAL_APPENDIX_2026-11-19.md) §B–§E; AD-038 (all of it, incl. LD-1 §17
and LD-2 §18); the LD-0 reference-PC run
([RESULTS_LOOKDEV_REFERENCE_PC_2026-11-19](../../experiments/drag_cost/RESULTS_LOOKDEV_REFERENCE_PC_2026-11-19.md)); the
LD-1 room run ([RESULTS_LOOKDEV_ROOM_REFERENCE_PC_2026-11-20](../../experiments/drag_cost/RESULTS_LOOKDEV_ROOM_REFERENCE_PC_2026-11-20.md)).
**State inspected:** branch `ccr-bc1a150b-hs0xcj` = `a32a9cf` (LD-2) merged with `c7c5104` (Manu's re-order, from
`claude/festive-feynman-xu6zfg`, fast-forward); `src/` tree `09aa719a72`. Every code statement below was checked at that
state (§1).
**Extends:** AD-038 (the room, the LookDev pass, the eye `LOOKDEV` variant, the linear pipeline, LD-2's `SceneObject.look`
v15), AD-033 / AD-035 (the eye pass and its source discipline), AD-REGIONS-01 (face regions), AD-026 §7 / AD-035
(scene-relative image paths), AD-037 (paint as the albedo source). **Core / format:** none in S1–S5; S6 and S7 each add
one optional Core value and a format version by content (§9, §10; CORE_V1_FREEZE §7).

Evidence tags as in AD-038 §1: **[V]** verified in code at the state above (file:line), **[M-C]** measured in the
container (a function check only), **[M-RPC]** measured on the reference PC, **[P]** decided by this AD if accepted,
**[E]** estimate, **[O]** open for Manu.

---

## Kurzfassung (Deutsch)

- **Was dieses AD festlegt:** die Architektur für alle P3-Teile, als sieben Scheiben in einer Reihenfolge, jede mit
  Dateien, Schnittstellen, Shader-Regeln, GL-Zustand, Budget, Tests und einer Messung auf dem Referenz-PC.
- **Für alle Scheiben gleich (§2):**
  - Jeder Effekt hat eine **feste Einstellung**, ein **eigenes Ein/Aus** im Panel (Block „Effekte“) und seine
    **Feature-Prüfung**, nach Feature, nie nach GPU-Name. Fehlt ein Feature, ist der Effekt aus, und eine Statuszeile
    sagt warum.
  - **Effekt aus = der Shader von vorher, Zeichen für Zeichen.** Dafür gibt es einen neuen Pin über die Haut-Shader und
    die bestehenden Augen-Pins.
  - Der Modelling Room verliert nichts. Ohne LookDev wird nichts davon angelegt oder kompiliert. R-1 und die
    Augen-Pins bleiben. Es gibt keine Tasten.
- **Reihenfolge (mein Vorschlag, §3):**
  1. **S1 Schattenkarte** vom Key, für Haut und Zähne. Sie wird nur bei Pose-, Geometrie- oder Key-Änderung neu
     gerechnet. Der Schlüssel dafür sind die Revisionszähler, die der GPU-Picker schon benutzt.
  2. **S2 Lid-Schatten aus der Geometrie fürs Auge:** Das Auge liest dieselbe Karte. Die Lider des Kopfes werfen den
     Schatten des Keys auf den Augapfel.
  3. **S3 Dual-Lobe-Glanz** auf der Haut.
  4. **S4 Durchscheinen mit Dicke aus der Form:** Die Dicke kommt aus derselben Schattenkarte, ohne Malen.
     - Das korrigiert den Vorschlag: Diese Dicke hängt **nicht** an der Mal-Kanal-Entscheidung (§1.2 C3).
  5. **S5 Cube-Umgebung** mit GPU-Vorfilter. Inhalt ist das analytische Studio der Vorlage, also weiter ohne
     HDRI-Dateien (D-L4).
  6. **S6 Region-Materialien**, nach LD-D8.
  7. **S7 Maps** für Rauheit, Normalen und Durchscheinen, nach der Mal-Kanal-Entscheidung.
  - Gegenüber deinem Vorschlag kommen S2 und S4 dazu und stehen früh, weil sie nur S1 brauchen. Der Cube rückt hinter
    sie, weil er mit dem Studio als Inhalt sichtbar wenig ändert (§8).
- **Core und Format:** keine Änderung in S1 bis S5.
  - S6 bringt `SceneObject.look_regions` (Format v16).
  - S7 bringt `LookMaterial.maps` (die nächste Version).
  - Beide werden nur geschrieben, wenn sie belegt sind.
- **Sonde P3-0 jetzt fertig:** `probe_lookdev.py --p3` misst:
  - den Tiefen-Durchgang allein (512² bis 2048², mit und ohne Augen als Werfer);
  - die Schatten-Abfrage nach Größe und PCF-Taps;
  - die Dicke, den Dual-Lobe und den Cube gegen das analytische Studio;
  - alles zusammen.
  - Im Container läuft sie als Funktionstest (alle FBOs vollständig, keine GL-Fehler, die Ecken-Korrektur des Cubes
    wirkt). Deine Zahlen legen die festen Einstellungen fest (§11).
- **Deine offenen Fragen mit meinem Vorschlag (§13):**
  - **LD-D8:** Regionen des Kopfes, Material je Region am Objekt.
  - **Mal-Kanal:** zuerst importierte Maps als Pfad am Material; gemalte Kanäle später als eigene Paint-Phase.
  - **Schattenkarte:** 1024², 9 Abfragen (3×3 bilinear verglichen), Weichheit aus „Weichheit“ des Keys.
  - **Cube-Inhalt:** das Studio der Vorlage. HDRI nur auf dein Wort.
  - Dazu fünf weitere Fragen.
- **Dein Praxistest von M1 und LD-2 steht noch aus.** Er blockiert dieses AD nicht. Er kann aber die Reihenfolge der
  Scheiben verschieben (§12).

---

## 0. Scope, guardrails, not in scope

### 0.1 In scope [P]

The P3 items of proposal §13 (P3) and §0.1, as slices S1–S7 (§3): the key shadow map; the eye in that shadow (the
"lid shadow from geometry"); dual-lobe specular; backscatter with thickness; the environment cube with a GPU prefilter;
region materials; roughness, normal and translucency maps.

### 0.2 Guardrails (proposal §0.1, AD-038 §9 / §13.6; binding for every slice) [P]

| # | Guardrail | How it is held |
|---|---|---|
| G1 | **P3 ships without LD-3.** Each effect has **one fixed setting**, measured on the reference PC against LD-D10 (≥ 30 fps, framed Gollum head, 1024×768, still or slow poses) | §2.5 budget table; §11 one measurement per slice |
| G2 | Each effect has **its own on/off** in the panel: the manual lever until LD-3 | §2.1 `LookdevEffects`, the panel block „Effekte“ |
| G3 | Each effect brings **the feature check it needs**, by feature, never by GPU name; a missing feature turns the effect off with a status line; LD-3 later takes these checks over, it does not rebuild them | §2.2 `lookdev_features` |
| G4 | **The Modelling Room loses nothing** (LD-D10, E1, E16) | with `shading == "worklight"` no P3 resource, program or state exists (§2.4); E16 re-run per slice (§11) |
| G5 | **The eye pins stay**; the Worklight eye sources are character-identical | §2.3; `PINNED_WORKLIGHT_SOURCES_SHA256` is a hard gate in every slice |
| G6 | **R-1** stays; P3 adds nothing that a room transition writes | the effect switches are view state of the room (§2.1); `tests/test_room_rule.py` unchanged and green |
| G7 | **No keys** (D-L9) | panel controls only |
| G8 | LD-0 (c) and (d) are met on the reference PC: render-to-RGBA16F cube faces, a depth texture with compare mode, PCF (AD-038 §16.1) | the risk left is cost and look, not capability |

### 0.3 Not in scope

- **Painting in a pose or on a morph** — its own AD outside LookDev (P-8 / P-9, proposal §6.2). Nothing here
  depends on it, and nothing here blocks it.
- **LD-3** (the quality manager, Auto / Hoch / Mittel / Entwurf, timing hysteresis). It follows P3 and adapts M1's and
  P3's knobs together (proposal §12.3).
- **P4 / P5:** skin diffusion tiers, MSAA or an HDR target, the render bridge, a render export.
- HDRI files as environment content (D-L4; Q-P3-4).
- Shadows from fill or rim; screen-space effects (SSAO, SSS blur: proposal §9.2 "never in P2–P3").

---

## 1. Code check (what the proposal and AD-038 said, what the code says)

### 1.1 Verified [V] — the facts P3 builds on

| # | Statement | Where |
|---|---|---|
| V1 | The LookDev frame: background first, the edit mesh's drawn surface and every entry with a `LookDraw` through `LookdevPass.draw`, eyes through `EyePass.draw(…, lighting=frame)`; a False return falls back to the Worklight draw | `viewport/viewport.py:1234–1257` |
| V2 | `render()` with a capture request draws the meshes **twice** in one frame (capture, then the normal frame) | `viewport.py:1130–1157` |
| V3 | The frame dict is cached by (studio state, camera basis with "Licht folgt Kamera") | `viewport.py:489–503` |
| V4 | Skin programs are cached by `(ALBEDO_MAP, ENV_SPEC)`; an entry with `alpha < 1` (a Ghost) is not drawn by the pass | `viewport/lookdev_pass.py:79–92`, `:104` |
| V5 | Skin units: UVs 3, albedo 4; the comment reserves 6 for "the P3 shadow map"; unit 0 stays pyglet's | `viewport/lookdev_shaders.py:38–40` |
| V6 | `LD_COMMON_SRC` is included by **both** passes; it holds `ld_diffuse`, `ld_specular` (key / fill / rim in one loop), `ld_studio`, `sh9`, `lookdev_output` | `lookdev_shaders.py:77–157`; appended to the eye's library only with `lookdev` (`viewport/eye_shaders.py:1097–1100`) |
| V7 | The skin body: GGX from the three lights, the studio as environment specular under `ENV_SPEC`, a view-rim backscatter proxy from the key (`(1 − n·v)³ · max(−n·l, 0)`) | `lookdev_shaders.py:209–214` |
| V8 | The skin program's VS is the textured Worklight VS (`u_model` applied, normal by `mat3(u_model)`: uniform scale) | `viewport/gl_render_store.py:358–376`, `lookdev_shaders.py:220–228` |
| V9 | The eye `_without` resolves `#ifdef` blocks of the **body** only; the libraries are concatenated by Python | `eye_shaders.py:1092–1103` |
| V10 | Eye pins: `PINNED_SOURCES_SHA256` (`tests/test_gl_eye_pass.py:1099`), `PINNED_WORKLIGHT_SOURCES_SHA256` over 1,030 sources (`:1137`, test `:1161–1163`), `PINNED_LOOKDEV_SOURCES_SHA256` over 1,024 LOOKDEV sources (`:1491–1495`) | as named |
| V11 | Eye units 1 iris, 2 noise, 3 key table, 4 sclera map; the eye pass already uses **sampler objects** (`glGenSamplers`) | `viewport/eye_pass.py:36–43`, `:296` |
| V12 | An FBO pass inside `on_draw` that saves and restores draw / read framebuffer, viewport, program, VAO and the caps it touches: the phase 4 key table | `eye_pass.py:305–374` |
| V13 | The eye's parametric lid shadow (`u_lid_shadow`, `lid_shadow_weight` in the eye's rest frame) exists only under `LOOK`, in the iris and the sclera branch | `eye_shaders.py:366–369`, `:839–840`, `:913–914` |
| V14 | `RenderMesh.layout_revision` / `content_revision`: +1 on a rebuild, a topology patch, a geometry sync (incl. the posed / morphed / SubD surfaces' table moves) and a Hide / Isolate change; **not** on a region tint or a material change | `viewport/render_mesh.py:356–359`, `:410`, `:542`, `:1178`, `:1266`, `:1273`; tints `:544–561` |
| V15 | The GPU picker caches its FBO render by `(id(rm), content_revision, layout_revision, camera, model, size, occlusion)` and restores the viewport after its FBO pass | `viewport/gpu_picker.py:175`, `:198–250` |
| V16 | `RenderMesh.bounds_min` / `bounds_max` (lazy) and `model_matrix` | `render_mesh.py:258–262`, `:322`, `:841` |
| V17 | Region tints reach the drawn surface by face: `Viewport.set_face_tints` (the **edit mesh only**), the SubD surface through `face_parent` (`surface_face_tints`) | `viewport.py:898–903`, `:845–869`; `mirai/subdivision/preview.py:235–246` |
| V18 | `LookMaterial` is frozen data; `from_dict` takes **exactly** the field names. `EyeLook.iris` is the precedent for an optional sub-object (absent = neutral, older files unchanged) | `core/scene.py:506–555`; `:276–290` |
| V19 | Format by content: v15 only when an object has a look; a `"look"` below v15 refuses the file | `core/serialization.py:159–161`, `:273–279` |
| V20 | `view.lookdev` is read key by key (`raw[name]`); a missing key raises `KeyError`, and that skips the whole section | `mirai/view_state.py:290–343`, `:154–157` |
| V21 | Studio presets carry their content (dome + ≤ 4 softboxes) as `Studio`, hashable, the SH9 cache key; the key light sits on the Portrait softbox (45°, 30°) | `mirai/lookdev_presets.py:23–58`, `viewport/lookdev_optics.py:73–98`, `:163–173` |
| V22 | `Gollum_Head_05`: the painted head's regions are ZBrush polygroups `Group 2` (68 faces), `Group 4` (96), `Group 8` (96); no region is named for the mouth; the teeth and the older head are hidden | `scenes/Gollum_Head_05.mirai.json` (read 2026-11-22) |
| V23 | Detach carries morph targets, weights, UVs and groups into the new object | AD-031 §1 (line 42 there) |

### 1.2 Corrections to the proposal (the AD follows the code)

| # | The proposal | The code / the evidence | Consequence here |
|---|---|---|---|
| C1 | §8.3: render-to-RGBA16F cube faces and `textureGrad` "untested on the 9800 GTX" | LD-0 (c) met: 42 attachments complete, chain 12.1 ms (64 samples), level 0 within 6e-4, `textureLod` exact (AD-038 §16.1) [M-RPC] | S5 uses `textureLod` only; `textureGrad` is not needed |
| C2 | §9.2: a shadow map "needs depth textures, untested" | LD-0 (d) met: depth FBO complete, PCF darkens the expected pixels [M-RPC] | S1's risk is cost and look |
| C3 | §9.2 / §0.1: "translucency / thickness map for backscatter — authoring needed"; backscatter with thickness waits for the paint channel decision | The key's depth map already holds, per texel, the depth where the key light enters the mesh. The fragment's light-space depth minus that is the distance the light travels inside: the established "translucent shadow map" thickness. A second sampler object without compare mode reads the raw depth of the same texture (GL 3.3 core; sampler objects are used already, V11). P3-0 container: it compiles and draws [M-C] | **S4 needs only S1**, no authoring and no paint decision. The thickness **map** stays in S7 and refines it |
| C4 | §4.4: region materials need per-face GPU data "which this proposal does not expose (§9.3)" | There is no §9.3; the reference is §10.3. The region tint path already brings per-face values to the drawn surface, SubD included (V17), but **only for the edit mesh** | S6 reuses the tint path's hand-over and SubD provenance, adds the same for entries, and exposes **one** per-triangle buffer, not the face rows (§8) |
| C5 | §4.4: Gollum has "teeth (4 objects)" as per-object material targets | The four tooth objects are hidden in the file (AD-038 C10); the head's regions are unnamed polygroups (V22) | S6's practical test needs a named mouth region; the teeth are shown for S1's test |
| C6 | §0.1 / AD-038 §16.1: "the unoptimised shadow stand-in adds 9–11.5 ms" | That stand-in rendered the 2048² depth pass **every frame** with the **eyes as casters** (14,976 eye triangles beside 5,469 / 22,153 skin triangles; `probe_lookdev.py` LD-0 `DepthTarget.render`) and 16 fetches. Its split between pass and lookup was never measured | P3-0 (§10.1) measures the pass alone and the lookup alone, skin-only casters. S1's eyes receive and do not cast (§4) |
| C7 | §8.3: a cube "can never be prefiltered on a preset switch" (CPU 40 s) | The GPU prefilter takes 12 ms for 128² (64 samples) [M-RPC]; the lab's CPU corner equalization has a GPU form: a corner texel takes the cube corner's direction, so the three texels meeting there are equal by construction. P3-0 container: corner spread 0.000 at every level with it, up to 1.4 without [M-C] | S5 prefilters on the preset switch, in the frame, with no disk cache (option 1 of §8.3) |
| C8 | §0.1: "the part of LD-3's capability detection that P3 uses (cube FBO completeness, a depth texture with compare mode)" | S4 also needs sampler objects (core 3.3); S7 needs a free unit count (32 fragment units on the reference PC, appendix B1) | §2.2 lists every P3 feature check |

---

## 2. The shared frame for every slice

### 2.1 Effect switches: `LookdevEffects` [P]

- `viewport/lookdev_optics.py` gains `LookdevEffects`: a frozen dataclass of booleans (`shadow`, `eye_shadow`, `dual_lobe`,
  `thickness`, `cube`, `regions`, `maps`). Each field joins with its slice, default **on** once its slice is built.
  `LookdevState.effects` holds it, so the frame dict's cache key (V3) covers it.
- **Dependencies** are resolved in one function, `effective(effects, features)`, with the result shown in the panel:
  - `eye_shadow` and `thickness` need `shadow`;
  - an effect whose feature is missing is off (§2.2).
- **Application:** `set_lookdev_effect(name, on)`. It is view state like the studio: no Undo, refused like the studio
  setters while an interaction owns the input. A switch that needs a program not compiled yet takes the I-10 path
  (AD-038 §17.2): one frame with the status line "LookDev: Shader werden vorbereitet …", then the compile.
- **Panel:** a block „Effekte“ below the studio, one checkbox per built effect. A greyed checkbox carries the reason as
  a tooltip ("braucht Schatten", "Tiefentextur fehlt"). The block replaces nothing that exists.
- **Persistence:** `view.lookdev.effects` (a dict of name → bool).
  - It is read with `raw.get("effects")`: a file from LD-2 has no such key and must keep its studio. Today a missing key
    skips the whole section (V20).
  - An unknown effect name is ignored, and a bad value skips only the `effects` key.
  - An older build drops the key on save (the proposal §5.1 limitation, pinned by the existing test pattern).

### 2.2 Feature checks: `viewport/lookdev_features.py` [P]

- `features(context) -> FeatureReport`, computed once per GL context, the first time an effect needs it (never with
  `shading == "worklight"`). It checks by function, never by `GL_RENDERER`:

| Feature | Check | Needed by |
|---|---|---|
| `depth_texture` | a DEPTH_COMPONENT24 texture with `GL_COMPARE_REF_TO_TEXTURE` attached to an FBO: `glCheckFramebufferStatus == COMPLETE`, `glGetError` 0 | S1, S2, S4 |
| `sampler_objects` | `glGenSamplers` succeeds and `glGetError` stays 0 | S4 |
| `cube_rgba16f` | an RGBA16F cube, every face of every level as an FBO attachment, complete | S5 |
| `texture_units` | `GL_MAX_TEXTURE_IMAGE_UNITS` ≥ the highest unit the variant binds + 1 (§2.4) | S6, S7 |

- A failed check turns that effect off and shows the status line once, for example "LookDev: Schatten aus –
  Tiefentextur nicht verfügbar". It does not retry in the session. The report is a plain value, so LD-3 can read it.
- A test forces each failure through a stub and asserts: effect off, status line, the frame drawn as without the effect.

### 2.3 Shader source discipline [P]

1. **One define per effect** (`SHADOW`, `LD_SHADOW` in the eye, `DUAL_LOBE`, `THICKNESS`, `CUBE_ENV`, `REGIONS`,
   `ROUGHNESS_MAP`, `NORMAL_MAP`, `TRANSLUCENCY_MAP`). **With the effect off, the source is the one before,
   character for character.**
   - Library text that only an effect needs is a separate Python string, appended only when the effect is on
     (`LD_SHADOW_SRC`, `LD_SKIN_SRC`, …). It is never an `#ifdef` inside a library string.
   - Body text is an `#ifdef` block, resolved by `_without` (V9) in **both** bodies: `skin_sources` applies it to
     `SKIN_BODY` as `shell_sources` does to the eye body, so an effect that is off leaves no text behind. The skin's
     new pin (point 3) is taken over `skin_sources` output and holds this.
   - `#if X == n` on a possibly undefined name is never used: GLSL makes an undefined name in `#if` an error. Use one
     define per case (the P3-0 stand-in does so: `DUAL_LOBE_ENV`).
2. **`LD_COMMON_SRC` does not change in P3.** It is in every eye LOOKDEV source (V6), so changing it would move
   `PINNED_LOOKDEV_SOURCES_SHA256`. A skin-only variant of a common function, such as the dual-lobe `ld_specular`, is
   a new function in `LD_SKIN_SRC`. An eye term scaled by the shadow is written in the eye's `LD_SHADOW` body block,
   from the same functions (§5).
3. **Pins:**
   - `PINNED_WORKLIGHT_SOURCES_SHA256`: **unchanged in every slice. This is a hard gate.**
   - `PINNED_LOOKDEV_SOURCES_SHA256` (E4): unchanged. The new eye keyword `ld_shadow` defaults to off, and the pin's
     source space stays the 1,024 sources it was taken over.
   - **New in S1's first commit, before `lookdev_shaders.py` changes:** `PINNED_SKIN_SOURCES_SHA256` over the 4 M1 skin
     variants (`skin_sources` for `ALBEDO_MAP × ENV_SPEC`, attribute locations 0 / 1). This is the C6 / I-0 pattern of
     AD-038: the pin is taken from the old code.
   - **New per eye slice:** a pin over the eye's `LOOKDEV + LD_SHADOW` sources (S2).
4. **Program keys:**
   - The skin cache key becomes the tuple of its defines in a fixed order. A P3 frame draws one or two skin variants,
     because all objects share the effects. With S6 / S7 the key depends on the object (whether it has regions or
     maps).
   - The eye key grows from 9 to 10 values. `ld_shadow` is inserted **before** `sclera`, which stays last, because the
     unchangeable eye tests read `key[-1]` (AD-038 I-1).
5. **Compile:** `Viewport.prepare_lookdev` (`viewport.py:475`) compiles the variants the effects and the drawn objects
   need, behind the status line, as in M1 (AD-038 §9).
6. **NumPy twins:** every new GLSL function gets a twin in `lookdev_optics.py`, with GPU parity in
   `tests/test_gl_lookdev_parity.py` (the E5 pattern): the PCF weight, the thickness transmission, the dual lobe, the
   cube LOD mapping, the region slot pick, the derivative tangent frame.

### 2.4 GL state and resources [P]

- **Units:**

| Unit | Skin pass | Eye pass (LOOKDEV) |
|---|---|---|
| 0 | never (pyglet / imgui, I-5) | never |
| 1–2 | — | iris, noise (V11) |
| 3 | triangle UVs (V5) | key table |
| 4 | albedo (V5) | sclera map |
| 5 | environment cube (S5) | — |
| 6 | key shadow map, compare sampler (S1) | key shadow map (S2) |
| 7 | key shadow map, raw depth through a sampler object (S4) | — |
| 8 | triangle material slots (S6) | — |
| 9–11 | roughness, normal, translucency maps (S7) | — |

  Every pass unbinds what it bound, including sampler objects (`glBindSampler(unit, 0)`), and leaves unit 0 active.

- **Off-screen passes:** the shadow depth pass and the cube prefilter render through their own FBO **inside**
  `_render_lookdev`. They save and restore what `EyePass.iris_table` saves (V12): draw / read framebuffer, viewport,
  program, VAO, and depth / blend / cull / scissor / polygon offset. No FBO stays bound across `on_draw` steps (I-4).
  The frame itself stays the RGBA8 default framebuffer: no float target, no MSAA (P4).
- **Capture (V2):** the shadow map and the cube are cached, so the capture's second mesh draw costs no second depth
  pass or prefilter.
- **`GL_TEXTURE_CUBE_MAP_SEAMLESS`** is global state. It is enabled around the skin draw that samples the cube and
  restored to what it was. Today nothing in `src/` enables it [V: no occurrence in `src/`].
- **Ownership:** the shadow map and the cube belong to `LookdevPass`. They are created on the first LookDev frame with
  the effect on and deleted in `release()`. Nothing is allocated, compiled or computed for `shading == "worklight"`
  (G4).
- **Read only:** the depth pass draws the stores' VertexLists with its own program and writes no store buffer (I-10).
  Hidden faces are degenerate triangles, so they neither cast nor receive (I-8).

### 2.5 Performance budget [P] (LD-D10; the numbers are targets, the reference PC decides)

Baseline [M-RPC]: the LD-1 room frame `Viewport.render()`, framed 1024×768, is 2.42 / 3.28 ms GPU (cage / SubD 1),
wall 11.6 / 12.6 ms (AD-038 §17.4).

| Slice | Per-frame GPU target, framed 1024×768 | Event cost (not per frame) |
|---|---|---|
| S1 shadow lookup | ≤ +1.5 ms | depth pass ≤ 3 ms at SubD 1 (a pose, morph or key change) |
| S2 eye shadow | ≤ +0.5 ms | — |
| S3 dual lobe | ≤ +0.5 ms | — |
| S4 thickness | ≤ +0.5 ms | — |
| S5 cube | ≤ +0.3 ms (expected: cheaper than the analytic studio, appendix B6) | prefilter ≈ 12 ms on a preset switch [M-RPC LD-0 (c)] |
| S6 regions | ≤ +0.3 ms | slot upload on a region or topology change |
| S7 maps | ≤ +0.4 ms per map | — |

- **All P3 effects on:** ≤ 9.5 ms GPU for the framed head at 1024×768 (≤ 29 % of 33.3 ms). The wall frame must stay
  ≤ 33.3 ms in a still pose.
- **During a slow pose or morph drag,** S1 re-renders the map every frame. The frame then holds ≥ 30 fps when the
  depth pass meets its target [E]. LD-D10 judges deformation qualitatively.
- **Levers, in this order,** if a slice misses its target on the reference PC. They are render-only and are LD-3's
  knobs later: a smaller shadow map → fewer PCF fetches → the effect's on/off. The order is applied, not decided anew
  per slice.

### 2.6 What is document data, what is view state [P]

| Kind | P3 items | Where |
|---|---|---|
| View state (no Undo, `view.lookdev`) | effect switches | `view.lookdev.effects` (§2.1) |
| Fixed engineering values (code constants, `PROVISIONAL`) | shadow size / PCF / bias, dual-lobe values, thickness scale, cube size / samples | `lookdev_shaders.py` / `lookdev_optics.py`; LD-3's knobs later |
| Document data (Core, Undo, format by content) | region materials (S6), map paths (S7) | §9, §10 |

---

## 3. The order of the slices [P] (proposal §0.1 asked for it; Manu's proposal: shadow, dual lobe, cube, regions, maps)

| # | Slice | Depends on | Why this place |
|---|---|---|---|
| **S1** | Key shadow map on skin and teeth | the AD; P3-0 on the reference PC (size / PCF) | the named M1 weakness (proposal §9.2, §15 "flat look"), the base of S2 and S4 |
| **S2** | The eye in the key shadow ("lid shadow from geometry") | S1 | the face reads by the eyes under the brow and lids; same map, one eye define |
| **S3** | Dual-lobe specular | — | cheap, no authoring (proposal §0.1 item 2) |
| **S4** | Backscatter with thickness from the key's depth | S1 | no authoring (C3); Gollum's ears and nostrils against a back key |
| **S5** | Environment cube, GPU prefilter, studio content | — | proven (C1, C7); with D-L4 content it mostly corrects rough reflections and prepares arbitrary environments, so its visible gain is smaller now (§7) |
| **S6** | Region materials | **LD-D8** (Q-P3-1) | needs a Core field and Manu's choice |
| **S7** | Roughness, normal, translucency maps | **the paint channel decision** (Q-P3-2) | needs authoring and a Core field |

- **Deviation from Manu's proposed order:** S2 and S4 are added, and both come right after S1 because they reuse its
  map. The cube moves behind them.
- S3 and S5 have no dependency. They can swap with any neighbour if the practical test (§12 point 3) says so.

---

## 4. S1 — the key shadow map

**What [P]:** one 2D depth map from the key light, orthographic, over the bounding sphere of the casters. A PCF lookup
in the skin pass scales the key's diffuse and specular. The fill and rim stay unshadowed. Skin objects and teeth cast
and receive. The eyes neither cast nor receive in S1; they receive in S2.

**Fixed setting (candidate, decided by P3-0 §11.1) [P]:**
- 1024² DEPTH_COMPONENT24, `GL_LINEAR` and compare mode;
- 3 × 3 = 9 fetches, each a hardware 2 × 2 bilinear compare;
- the fetch spacing is scaled by the key's `size` ("Weichheit"): a soft key draws a softer edge. This is PCF with a
  light-size radius, without a blocker search;
- bias: slope-scaled polygon offset in the depth pass (2, 4 as LD-0), plus a normal offset of about one texel in the
  lookup;
- outside the map counts as lit (`CLAMP_TO_BORDER`, border depth 1.0).
- 1024² over a head about 30 cm across gives texels of about 0.3 mm [E], fine enough for the lid's shadow on the
  eyeball (S2).

**When it is re-rendered (the user's requirement: only on a pose, geometry or key change) [P]:**
- The cache key is built each LookDev frame. It costs O(casters) tuple work and no GL call. It holds:
  - for each caster `(id(rm), rm.layout_revision, rm.content_revision, tuple(model))` (V14, V16; the GPU picker's key,
    V15);
  - the key direction in the world;
  - the frustum.
- **A pose step, a morph weight, a SubD surface re-evaluation, a topology edit, Hide / Isolate, a placement change,**
  a studio rotation, the key's azimuth / elevation, or "Licht folgt Kamera" with a camera move each change the key and
  re-render the map.
- **A camera orbit** with the world-fixed studio (LD-D5), a material change, a region tint, the exposure, or a key
  intensity / colour change do **not** re-render it.
- **Frustum:** the union of the casters' world bounds (V16) grown by 15 %. It is recomputed only when the caster set or
  a `layout_revision` changes, not on every pose step, so the shadow does not swim during a drag. A pose that leaves the
  grown sphere clips at the border (lit), which is a named limitation.

**Files and interfaces [P]:**

| Layer | New | Changed |
|---|---|---|
| Viewport | `viewport/lookdev_shadow.py` (`KeyShadow`: texture + FBO, depth program with its own minimal VS (position at the store's location, `u_model`, `u_ld_shadow_vp`) and an empty FS, `key()`, `update(casters, key_dir)`, `bind(unit)`, `release()`); `viewport/lookdev_features.py` | `lookdev_shaders.py` (`LD_SHADOW_SRC`: `u_ld_shadow`, `u_ld_shadow_vp`, `u_ld_shadow_radius`, `ld_key_visibility(p, n)`; `SKIN_BODY` block `#ifdef SHADOW` scaling the key's terms); `lookdev_pass.py` (program key, unit 6, the uniforms); `viewport.py` `_render_lookdev` (shadow update before the background); `lookdev_optics.py` (`LookdevEffects`, `shadow_frustum` twin) |
| App | — | `controllers/lookdev_room.py` (the effects in the studio state), `application.py` (`set_lookdev_effect`), `mirai/view_state.py` (`effects`, read optionally), `lookdev_presets.py` (effects default) |
| GUI | — | `gui/lookdev_model.py`, `gui/lookdev_panel.py` (block „Effekte“) |
| Not touched | | `src/core/`, `serialization.py`, the Worklight programs, `GLRenderStore.draw()`, `eye_shaders.py`, `main.py`, `config/keymap.json` |

- **The key's terms in the skin body:** `ld_diffuse` / `ld_specular` stay as they are (§2.3 point 2). The `SHADOW`
  block subtracts `(1 − vis) ×` the key's own diffuse and specular term, computed with the same `ld_wrap` /
  `direct_specular` calls.
  - This equals scaling the key inside the loop.
  - A parity test against a NumPy twin pins it.
- **Teeth (C5):** they are hidden in `Gollum_Head_05`. S1's practical test shows them, so the lips' shadow on the teeth
  can be judged.

**Tests [P]:** GL tests in `tests/test_gl_lookdev_shadow.py` (new); headless tests in
`tests/test_lookdev_optics.py` (added).

| # | Test | Criterion |
|---|---|---|
| T1-1 | A box over a plane, key from above: the plane under the box is dark, the rest lit | pixel counts in / outside the expected footprint |
| T1-2 | A lit sphere: no self-shadow on its lit half (acne) | ≤ 0.1 % of the lit pixels darkened |
| T1-3 | Re-render only on change: counter `KeyShadow.renders`; a camera orbit and an exposure change → +0; a morph weight, a pose step, a key azimuth, a rotation → +1 each; a capture frame → +0 | counts |
| T1-4 | Effects off = M1: frame pixels identical to the frame before S1; `PINNED_SKIN_SOURCES_SHA256` holds | identical |
| T1-5 | GL state as found after the frame, incl. framebuffer bindings, viewport, units 0–7, sampler bindings | the `snapshot_gl_state` pattern (E14) |
| T1-6 | Feature failure (stub): `depth_texture` false → effect off, status line, M1 frame | as T1-4 |
| T1-7 | `view.lookdev.effects` round trip; an LD-2 file without `effects` keeps its studio; a bad value skips only `effects` | E18 pattern |
| T1-8 | `shadow_frustum` twin: every caster vertex inside the box; stable under a pose step that stays inside the margin | NumPy |

**Gates:** E1, the eye pins incl. the Worklight pin, E15 (picking), `tests/test_room_rule.py`,
`tests/test_gui_imgui_window.py`, `tests/test_gl_lookdev_pass.py`; E16 on the reference PC.

**Measurement:** P3-0 before (§11.1). After the build, `probe_lookdev_room.py` gains:
- `--effects` (a list or `none`);
- rows `lookdev` (effects off), `lookdev +shadow`, and `lookdev +shadow drag` (a morph weight step on the head every
  frame, so the map re-renders);
- `KeyShadow.renders` per row.

---

## 5. S2 — the eye in the key shadow (the lid shadow from geometry)

**What [P]:** the eye's LOOKDEV variant reads S1's map at the shell's world position (`v_world_pos`, the eye VS
already writes it, `eye_shaders.py` `SHELL_VERTEX_SRC`). The key's visibility scales every key term of the eye:
- the key in `lit()` (B1) and in `iris_lit()`, including the phase 4 key table's term (B2);
- the key's GGX highlight (B6);
- the soft key reflection on the cornea and the film (B5).

The head's lids, brow and nose cast this shadow onto the eyeball. Ambient, fill and rim and the studio reflections
stay unshadowed.

- **Define:** `LD_SHADOW`, body blocks nested inside the existing `#ifdef LOOKDEV` blocks, resolved by `_without`
  (V9). The library piece `LD_SHADOW_SRC` (shared with S1, the same text) is appended only when it is on. A global
  `float ld_key_vis` is set once at the start of `main()`.
- **Approximation, named:** the iris is seen through the cornea a few mm behind the shell. The lookup at the shell point
  shifts the shadow's edge on the iris by up to that distance [E]. The probe and the practical test judge whether it
  shows.
- **The parametric lid shadow stays** (V13): `EyeLook.lid_shadow` (the ambient darkening under the lid, in the rest
  frame). With the key shadow on, the key part is no longer faked. Whether the artist then lowers `lid_shadow` is a
  practical-test question (Q-P3-6). This AD changes no eye value.
- **Eyes as casters: no** [P, `PROVISIONAL`]. The eye shell in its own map self-shadows at the corneal bulge and costs
  14,976 triangles in the depth pass (C6). The lids are the head mesh.
- **Files:**
  - `eye_shaders.py`: the `ld_shadow=False` keyword, last among the new ones, and the body blocks;
  - `eye_pass.py`: the key 9 → 10 (before `sclera`), unit 6, the shadow uniforms from the frame dict;
  - `viewport.py`: the eye draw gets the `KeyShadow`.
  - The Worklight path is not touched.
- **Tests** (`tests/test_gl_eye_pass.py`, which **only adds** tests; existing tests and pins untouched):

| # | Test | Criterion |
|---|---|---|
| T2-1 | A blocker plane between key and eye darkens the sclera's key light; without the blocker the eye equals the S1 frame | pixel delta |
| T2-2 | `PINNED_WORKLIGHT_SOURCES_SHA256` and `PINNED_LOOKDEV_SOURCES_SHA256` unchanged; a new pin over the `LOOKDEV + LD_SHADOW` sources | digests |
| T2-3 | Eye shadow off (or `shadow` off) = the eye of the S1 frame, pixel for pixel; E7 (grey card) unchanged with effects off | identical; ≤ 2/255 |
| T2-4 | The draw leaves the GL state clean (the existing "draws and leaves the GL state clean" pattern, LOOKDEV + LD_SHADOW) | state |

- **Measurement:** room probe row `lookdev +shadow +eyes`; target ≤ +0.5 ms (§2.5).

---

## 6. S3 — dual-lobe specular (skin)

**What [P]:** the skin's GGX highlight from the three lights becomes two lobes, at roughness × 0.75 and × 1.3, mixed
0.85 / 0.15. These values are `PROVISIONAL` and follow the common real-time skin default [E]. Each light's size still
widens each lobe (`ld_lobe`). The environment specular follows the P3-0 decision:
- **one** studio evaluation at the base roughness, if `dual env` costs more than its visible gain;
- otherwise **two** evaluations, cheap with S5's cube (`cube dual env`).

- **No Core change.** The values are fixed constants (G1). Per-material dual-lobe values would be `LookMaterial` fields
  later (a version by content), after a practical test asks for them (Q-P3-7).
- **Source (§2.3 point 2):** `LD_SKIN_SRC` gets `ld_specular_dual`, the dual twin of `ld_specular`. `LD_COMMON_SRC`
  and therefore the eye are untouched. The `SKIN_BODY` block `#ifdef DUAL_LOBE` calls it instead.
- **All organic presets** get it while the effect is on, the teeth and the mouth included. A wet preset's low roughness
  keeps a sharp first lobe.
- **Tests:**
  - NumPy twin and GPU parity of `ld_specular_dual`;
  - energy: the mix of the two normalised lobes integrates to the single lobe's albedo within 2 % for r ∈ [0.2, 0.8]
    (headless);
  - effect off = the S1 frame (pixels, skin pin);
  - GL state.
- **Measurement:** room probe row `lookdev +dual`; P3-0 rows `dual direct` / `dual env` decide the environment variant.

---

## 7. S4 — backscatter with thickness from the key's depth (correction C3)

**What [P]:** light from the key that passes through thin parts, such as ears and nostril wings against a back or side
key.

- The skin pass reads S1's map a second time, through a sampler object **without** compare mode on unit 7, at the same
  light-space point.
- `thickness = max(z_fragment − z_map, 0) × depth_range` gives the distance in world units (cm) that the key light
  travels inside the mesh before it reaches this fragment.
- **Transmission:** `exp(−thickness / scale) × max(−n·l_key, 0)`, times `backscatter`, `backscatter_color` and the
  albedo (the material's existing values, V7). The scale is 0.6 cm (`PROVISIONAL`, tuned on Gollum's ears).
- With the effect on, this term **replaces** M1's view-rim proxy. With it off, the proxy is today's.
- **Needs S1** (`thickness` implies `shadow`, §2.1). It uses one extra fetch and no extra pass. Feature:
  `sampler_objects` (§2.2).
- **Limits, named:**
  - The thickness is along the key only, from the map's nearest surface. A fold in front of a thin part reads thick.
  - Outside the map (border) it reads as no light passing.
  - S7's thickness map later multiplies this, for regions the geometry cannot express.
- **Files:** `lookdev_shaders.py` (`THICKNESS` block), `lookdev_shadow.py` (`bind_raw`, the sampler object),
  `lookdev_optics.py` (twin).
- **Tests:**
  - A thin slab and a thick block lit from behind: the slab transmits, the block does not; the numbers match the twin.
  - Effect off = the S3 frame.
  - Sampler binding restored (unit 7 has sampler 0 after the pass).
- **Measurement:** room probe row `lookdev +thick`; P3-0 row `thick 1k x9`.

---

## 8. S5 — the environment cube with a GPU prefilter

**What [P]:**
- **Content:** the studio preset's analytic content (dome + softboxes, `Studio`, V21) rendered into a 128² RGBA16F
  cube in the studio frame. D-L4 holds: "reproduzierbar, keine HDRI-Dateien".
- **Prefilter on the GPU:**
  - GGX importance sampling, 64 samples;
  - level L at roughness L / (levels − 1), down to 2² (the lab's chain, appendix B3);
  - the corner fix of C7 (equal corner texels by construction).
- **When:** on a change of the studio's **content** only, which is the cache key SH9 already uses (`Studio` is hashable,
  V21).
  - Rotation and intensity stay uniforms (`u_ld_env_rot`, `u_ld_env_intensity`).
  - About 12 ms on the reference PC, once per preset switch, inside the frame, with no status line [M-RPC LD-0 (c)].
- **Who reads it:**
  - The skin's environment specular reads it (`CUBE_ENV`), with `textureLod` at the effective roughness, instead of
    evaluating `ld_studio` per pixel.
  - SH9 stays the diffuse environment (proposal §8.1).
  - **The eye stays on the analytic studio in P3.** The cornea's near-mirror reflection needs the softbox's sharp
    edge, which level 0 of a 128² cube softens [E], and the eye pins stay where they are.
  - Skin and eye stay coherent because the cube's content **is** the analytic studio. A test holds level 0 against
    `ld_studio` within 1e-3 relative, as LD-0 (c) measured 6e-4.
- **What it gives now, honestly:**
  - the correct split-sum at medium to high roughness (the analytic lobe is a fit, within 16 % RMS up to r 0.8,
    proposal §8.1);
  - a cheaper environment specular per pixel (the lab's T-D ≈ 2 × T-C, appendix B6);
  - the base for arbitrary environments.
  - It does **not** change what the studio looks like. Its large visible step comes with other content (Q-P3-4).
- **Files:** `viewport/lookdev_cube.py` (new: `EnvCube`, the texture, the FBO, the prefilter program, `update(studio)`,
  `bind(unit)`, `release()`); `lookdev_shaders.py` (prefilter sources, `CUBE_ENV` block); `lookdev_pass.py`;
  `lookdev_features.py` (`cube_rgba16f`).
- **GL:** the FBO pass as in §2.4. `GL_TEXTURE_CUBE_MAP_SEAMLESS` is on only around the skin draw.
- **Tests:**
  - level 0 vs `lookdev_optics.ld_studio`;
  - the corner spread = 0 at every level;
  - the rough levels vs a NumPy GGX prefilter of a few texels (≤ 2 %);
  - `textureLod` read-back (the LD-0 (c) pattern);
  - re-prefilter only on a content change (counter: rotation / intensity +0, preset +1);
  - effect off = the S4 frame;
  - GL state, the seamless flag restored.
- **Measurement:** room probe row `lookdev +cube`, the prefilter's wall time on a preset switch; P3-0 row `cube env`
  and the chain time.

---

## 9. S6 — region materials (after LD-D8)

**Recommended LD-D8 answer [P → O]:** **face regions** (AD-REGIONS-01): a LookDev material per region, on the object.
It is not a separate mouth object.

- **Why regions:**
  - The mouth interior and the wet lip line are part of the head mesh, which is posed, morphed and subdivided.
    Regions are mesh-owned, survive topology edits (inheritance) and go through Undo with the mesh.
  - The SubD surface already carries region values by provenance (V17).
- **Why not a separate object:** Detach carries morphs and weights (V23), so it works today with no code. But the cut
  becomes an open boundary, and **SubD rounds the lip line differently** at a boundary than across it. It is the
  no-code fallback, not the design.

**Design [P]:**

- **Core** (CORE_V1_FREEZE §7: requirement, not solvable with the public API, the smallest extension):
  - `core.RegionLook(region: str, look: LookMaterial)` (frozen);
  - `SceneObject.look_regions: tuple[RegionLook, ...] = ()`. It holds at most 4 entries, and region names are unique
    within it.
  - **Format v16 by content:** `"look_regions"` is written only when non-empty. A v15 scene stays the same text. An
    older build refuses v16, so materials are never silently lost (the v15 rule).
  - A CORE_V1_FREEZE §7.1 entry.
- **Meaning:**
  - The object's `look` (or Neutral) is the base. Each listed region's faces draw that region's material.
  - **Overlap** (AD-REGIONS-01 allows it): the **later** entry wins. The panel shows the list in that order, with "nach
    oben / unten".
  - Keyed by the region's **name**. A rename of a region carries its entry in the same Undo step. A region that no
    longer exists is ignored, and the panel shows "Region fehlt".
- **Undo:** `ObjectLookCommand` grows to cover `look_regions`, one step per change (LD-2's preview / commit, AD-038
  §18.2). The value travels with Duplicate, mirror, Detach and `replace_scene` like `look`.
- **Viewport — the one new GPU interface:**
  - `RenderMesh.set_triangle_material_slots({FaceId: slot})` fills a per-triangle buffer `triangle_material` (R32F
    buffer texture), allocated only on request. This is the AD-038 §4.1 UV-request pattern, so with no regions nothing
    is allocated.
  - `GLRenderStore.bind_triangle_materials(unit)` binds it.
  - Face rows, face corners and the triangle → face map stay private (AD-038 §4.2).
- **Hand-over (C4):**
  - `Viewport.set_face_material_slots(key, slots)` per drawn key, the edit mesh **and** entries;
  - the SubD surface through `face_parent`, generalising `surface_face_tints` to `surface_face_values`
    (`preview.py:235–246`);
  - the posed and morphed surfaces share the FaceIds (AD-038 C11).
- **Shader:** `REGIONS`; `u_region_look[4]` uniform arrays of the `LookDraw` values. The slot comes from a `texelFetch`
  by `gl_PrimitiveID`. Each region may have its own albedo source, colour or the shared map: the same UVs, so one
  sampler.
- **Panel:** in the material block, "Bereich: Ganzes Objekt / <region names>". Regions come from `mesh.face_regions`.
  No new key.
- **Tests:**
  - Core: the contract, v16 by content, round trip, refusal below 16, the same text without regions;
  - app: Undo / Redo, rename carries, a missing region is ignored, Duplicate / mirror / Detach;
  - GL: a two-region plane shows two materials, on the cage and the SubD surface; overlap order;
  - effect off = one material per object;
  - E1 and the Worklight region tint unchanged.
- **Measurement:** room probe row `lookdev +regions` with a named mouth region on the head (the probe names one
  polygroup).

---

## 10. S7 — maps: roughness, normal, translucency (after the paint channel decision)

**Recommended answer to the paint channel decision (proposal §6.1) [P → O]:** **map paths first.** Each map is an
imported image path on `LookMaterial` (ZBrush or external painting), scene-relative and copied into `<scene>_textures/`
on Save As (the AD-026 §7 / AD-035 rule). **Painted channels** (a paint stack per channel in the Paint Room) come later
as their own AD-037 phase, not in P3.

- **Why:**
  - It is the smallest Core change, and it follows a precedent that exists (the sclera map).
  - It matches the ZBrush workflow (normal map export).
  - A painted roughness channel needs a channel-aware Paint Room (which channel a stroke paints, grey vs colour,
    the composite per channel). That is a separate product question.

**Design [P]:**

- **Core:**
  - `core.LookMaps(roughness: str | None, normal: str | None, translucency: str | None, normal_strength: float = 1.0,
    normal_green_down: bool = False)` (frozen);
  - `LookMaterial.maps: LookMaps | None = None`, an optional sub-object (the `EyeLook.iris` precedent, V18): absent =
    none, older looks unchanged.
  - **The next format version by content** (v17 if S6 shipped first, else v16).
- **Shader:**
  - `ROUGHNESS_MAP` multiplies the material roughness (a linear grey value), before the specular AA.
  - `NORMAL_MAP`: tangent space from the screen derivatives of world position and UV, so there is **no per-vertex
    tangent buffer** and no deformation-time CPU cost (proposal §9.2). OpenGL green-up by default, the flag for
    DirectX maps.
    - Limitation: a 2 × 2 pixel quad across a UV seam gets a wrong frame on the seam's pixels [E].
  - `TRANSLUCENCY_MAP` multiplies S4's transmission. Without S4 it scales M1's proxy.
  - Units 9–11, mipmapped, through the shared texture cache (`GLRenderStore.texture(path)`, AD-038 §4.3).
- **Panel:** under "Mehr" in the material block: "Rauheit-Map / Normal-Map / Durchscheinen-Map: Laden … / Entfernen".
  Each is one Undo step, like the sclera map in the Eye Lab.
- **Tests:**
  - Core contract and format;
  - load / replace / remove with Undo;
  - Save As copies;
  - a flat normal map = no change (pixels);
  - a tilted constant normal map turns the highlight (twin);
  - the seam limitation documented by a test image;
  - GL state.
- **Measurement:** room probe row `lookdev +maps` with three 2048² test maps (generated by the probe, not committed).

---

## 11. Measurements on the reference PC (one per slice)

### 11.1 P3-0 — before S1 (written and container-tested in this session)

`experiments/drag_cost/probe_lookdev.py --p3`. It is an extension of the LD-0 probe: the same stand-in skin program,
plus the P3 defines. The default run without `--p3` is LD-0's, unchanged (container check §11.3).

| Section | What it measures | What it decides |
|---|---|---|
| (p3a) depth pass alone | GPU ms at 512² / 1024² / 2048², casters skin only and skin + eyes, cage and SubD 1 | S1's map size and the drag cost (the ≤ 3 ms target); whether eyes may cast (C6) |
| (p3b) cube | the 128² chain with and without the corner fix; corner spread per level | S5's prefilter cost and the corner fix |
| (p3c) `shadow 1k x4 / x9 / x16`, `shadow 2k x9 / x16` | the lookup of a still pose (the map rendered once), vs `ld frame` | S1's PCF fetches and size: **the fixed setting** |
| `drag 1k x9` | the map re-rendered every frame (a slow pose or morph drag) | whether a drag keeps ≥ 30 fps |
| `thick 1k x9` | the thickness fetch on top of the shadow | S4's cost |
| `dual direct`, `dual env` | the second lobe on the lights; also on the environment | S3's environment variant |
| `cube env`, `cube dual env` | the environment specular from the cube instead of `ld_studio` | S5's per-pixel cost (expected cheaper) |
| `p3 all` | 1k × 9 + thickness + dual direct + cube env, and the LD-D10 share | the total P3 budget (§2.5) |

**Command on the reference PC** (NVIDIA "Maximale Leistung bevorzugen", repository root, `.venv312`):

```
python experiments\drag_cost\probe_lookdev.py --p3 | Tee-Object -FilePath lookdev_p3_0.txt
```

- It runs 1024×768 and then 1920×1080, each in its own process, about 3–5 minutes [E].
- The results go into `experiments/drag_cost/RESULTS_LOOKDEV_P3_REFERENCE_PC_<date>.md`.
- The agent fills the AD's table from the text Manu hands over.

### 11.2 After each slice

`probe_lookdev_room.py` gains `--effects <list>` (S1) and one row per built effect: `lookdev` (all off), `lookdev
+<effect>`, `lookdev all P3`, plus `lookdev +shadow drag` (S1). The same three-command run as AD-038 §17.4 then covers
the slice and E16:

```
python experiments\drag_cost\probe_lookdev_room.py | Tee-Object -FilePath lookdev_room_s<N>.txt
python experiments\drag_cost\probe_lookdev.py --no-extras | Tee-Object -FilePath lookdev_ld0_after_s<N>.txt
python experiments\drag_cost\probe_d3_acceptance.py | Tee-Object -FilePath d3_after_s<N>.txt
```

A slice that misses its target (§2.5) takes the levers in their order. It does not ship a slower default.

### 11.3 Container (function check, 2026-11-22) [M-C]

[`RESULTS_LOOKDEV_P3_CONTAINER_2026-11-22.md`](../../experiments/drag_cost/RESULTS_LOOKDEV_P3_CONTAINER_2026-11-22.md)
(llvmpipe; GPU timer values are not meaningful):
- every P3 variant compiles and draws; `glGetError` 0;
- the depth FBOs (512² / 1024² / 2048²) are complete; the raw-depth sampler object reads the compare texture;
- skin-only casters darken 4,979 / 53,307 px (cage framed / close), against LD-0's 5,189 / 58,170 with the eyes as
  casters;
- the cube's corner spread is 0.000 at every level with the fix (up to 1.4 without);
- the LD-0 mode is unchanged.
- `experiments/drag_cost/tests` (headless): 100 passed, the three new P3-0 tests included.

---

## 12. Stop points (Haltepunkte)

1. **This AD** (Manu accepts it, with or without changes to §13). Nothing in `src/` before that.
2. **P3-0 on the reference PC** before S1's fixed setting is committed. S1 can be **built** while the run is pending:
   the constants are one place. But it ships only with the measured setting.
3. **Manu's practical test of M1 + LD-2** is pending (AD-038 §17.5, §18.6).
   - It does not block this AD, nor S1 to S5, which are independent of the material values.
   - **It can shift the priority of the slices**, for example: a flat skin raises S3 / S4; a "the head reads well"
     lowers S5; a mouth that reads wrong raises S6.
   - The agent re-reads its verdicts before each slice and re-orders §3 in the same commit when they say so.
4. **After S1 (+S2):** a practical test (shadow look, softness, the eyes under the lids, the teeth), a reference-PC
   run, and the M1 / LD-2 verdicts if they exist by then.
5. **LD-D8** before S6, **the paint channel decision** before S7. Each needs Manu's word and the CORE_V1_FREEZE §7 entry
   in the slice's commit.
6. **Keys:** none (D-L9).
7. **LD-3** after P3: one AD or AD section with the full knob set (cube size, shadow size, PCF fetches) and the feature
   report of §2.2.

---

## 13. Open questions for Manu, with proposals

| # | Question | Proposal |
|---|---|---|
| **Q-P3-0** | Accept the slice order S1 → S7 (§3), with S2 and S4 added after the shadow map? | yes; the practical test may re-order (§12 point 3) |
| **Q-P3-1 (LD-D8)** | Region materials: face regions with a material per region on the object, or a separate mouth object? | **face regions** (§9): `SceneObject.look_regions`, ≤ 4 per object, later entry wins on overlap, keyed by name; format v16. The separate object stays a no-code fallback |
| **Q-P3-2 (paint channel)** | Roughness / normal / translucency: a map path on the material, or a second paint stack per channel? | **map paths first** (§10), `LookMaterial.maps`, imported images; painted channels later as their own AD-037 phase |
| **Q-P3-3** | Shadow map size and PCF | **1024², 3 × 3 bilinear-compare fetches, softness from the key's „Weichheit“**; P3-0 confirms or moves it (§11.1). 2048² and 4 × 4 become LD-3 knobs |
| **Q-P3-4** | What is in the cube of the studio presets? | **the preset's own analytic studio** (D-L4: reproducible, no HDRI files). If you want real environments, the next step is an `.hdr` (Radiance) import of your own files as a separate small item. That needs your word, because it lifts D-L4 |
| **Q-P3-5** | Eyes cast shadows? | **no** (they receive in S2) |
| **Q-P3-6** | With the key shadow on the eye, keep the parametric lid shadow (`EyeLook.lid_shadow`) as it is? | keep it; judge in S2's practical test whether to lower it per eye in panel „Auge“ (no code change) |
| **Q-P3-7** | Dual-lobe values fixed (× 0.75 / × 1.3, mix 0.85) or per material? | **fixed in P3**; per-material fields only if the practical test asks |
| **Q-P3-8** | Effect switches saved in the scene (`view.lookdev.effects`)? | **yes**, as view state, like the studio |
| **Q-P3-9** | Shadows from fill and rim? | **no** in P3 (one key map); a second map would double S1's cost |

---

## 14. Tests and gates (summary)

| Gate (every slice) | Protects |
|---|---|
| `PINNED_WORKLIGHT_SOURCES_SHA256`, `PINNED_SOURCES_SHA256`, `PINNED_LOOKDEV_SOURCES_SHA256` unchanged | the eye sources (G5) |
| `PINNED_SKIN_SOURCES_SHA256` (new in S1, taken before the change) | the M1 skin with every P3 effect off |
| `tests/test_gl_face_data_layout.py`, `test_gl_shading.py`, `test_gl_texture.py` (E1) | Worklight pixels |
| `tests/test_gl_gpu_picking.py`, `test_gl_morph_picking.py` (E15) | picking ignores LookDev |
| `tests/test_room_rule.py` (E9), `test_lookdev_room.py`, `test_lookdev_persistence.py`, `test_view_state.py` | R-1, the room, LD-2's persistence |
| `tests/test_gl_lookdev_pass.py`, `test_gl_lookdev_parity.py`, `test_gl_eye_pass.py`, `test_gui_imgui_window.py`, `test_gui_lookdev_window.py` | the pass, the twins, the eye, the panel in the real window |
| `experiments/lookdev_eye_lab/tests` | the frozen oracle (the eye's Worklight) |
| E16 on the reference PC | the Modelling Room |

Per slice: its own tests in §4–§10. GL tests run each file in its own process under xvfb (CLAUDE.md "Testing"); the
final runs per AGENTS.md §8a. `src/core` slices (S6, S7) also run `tests/` fully.

---

## 15. Deviations from the proposal (with reasons)

| # | Proposal | This AD | Why |
|---|---|---|---|
| P1 | Order shadow, dual lobe, cube, regions, maps | S1 shadow, **S2 eye shadow**, S3 dual lobe, **S4 thickness**, S5 cube, S6 regions, S7 maps | S2 and S4 reuse S1's map at low cost; the cube's visible gain with D-L4 content is small (§8) |
| P2 | Backscatter with thickness after the paint channel decision | geometric thickness in S4; the map in S7 | C3 |
| P3 | Lid shadows from geometry as a separate item | the eye reads S1's key map (S2) | one map, one define; the lids are already in the head mesh |
| P4 | GPU prefilter or a machine cache | GPU prefilter only, with the corner fix | C1, C7: 12 ms, no cache needed |
| P5 | Region materials "need per-face data" (face data access decided later) | one per-triangle slot buffer via the tint path's hand-over | C4: no face-row exposure |
| P6 | (not stated) | a skin source pin before S1; `LD_COMMON_SRC` frozen in P3 | effects off = M1, character for character; the eye pins stay |
