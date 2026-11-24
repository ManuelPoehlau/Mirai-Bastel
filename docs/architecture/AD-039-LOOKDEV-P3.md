# AD-039 — LookDev P3: key shadow map, eye shadow, dual lobe, thickness, environment cube, region materials, maps

**Status:** **ACCEPTED (2026-11-22, Manu):** „AD-039 freigegeben, Reihenfolge S1–S7 und Q-P3-0, Q-P3-3, Q-P3-5,
Q-P3-8, Q-P3-9 wie vorgeschlagen.“ LD-D8 and the paint channel (Q-P3-1, Q-P3-2) stay open until before S6 / S7;
Q-P3-4, Q-P3-6 and Q-P3-7 belong to S2, S3 and S5 and are judged there. Proposed 2026-11-22 (Architecture Gate). The
number AD-039 follows AD-038; AD-034 was never assigned (no file, no reference, no commit in the history). New class,
file and panel names stay `PROVISIONAL` until built. **S1 built 2026-11-22** (§16): the reference-PC run (E16, the
shadow's drag cost) and Manu's practical test (§16.5) are open. **S2 built 2026-11-22** (§17: the eyes in the key's
shadow, „Augen-Schatten“; eye shadow off = S1 by pin and pixels): its reference-PC row and practical test (§17.4–§17.5)
are open. **S3 built 2026-11-23** (§18: dual-lobe specular on the lights, „Doppel-Glanz“; dual lobe off = S1 / S2 by
pins; the §6 energy claim corrected, §18.2): its reference-PC row and practical test (§18.4–§18.5) are open. **S4 built
2026-11-23** (§19: the key's light through thin parts, „Durchleuchtung“; thickness off = S3 by pins; the scale in world
units, the unit question open, §19.2 S4-1): its reference-PC row and practical test (§19.4–§19.5) are open. **S7 built
2026-11-24, ahead of S5 / S6** (§20; Manu on Q-P3-2: „Map-Pfade“, and „S7 jetzt vorziehen“): roughness, normal and
translucency maps as image paths on the material (`core.LookMaps`, `LookMaterial.maps`, format **v16**; S6 takes v17);
no map = S4 by pins; its reference-PC row and practical test (§20.4–§20.5) are open. **S5 built 2026-11-24** (§21: the
studio's environment cube, „Umgebungs-Cube“: the analytic studio prefiltered on the GPU, read back and uploaded - the
reference PC's FBO-cube defect - on unit 8; cube off = S7 by pins; with the dual lobe two lookups; the eye stays
analytic): its reference-PC rows and practical test (§21.4–§21.5) are open. S6 next, after LD-D8.
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
     HDRI-Dateien (D-L4). **Gebaut 2026-11-24** (§21).
  6. **S6 Region-Materialien**, nach LD-D8.
  7. **S7 Maps** für Rauheit, Normalen und Durchscheinen, nach der Mal-Kanal-Entscheidung. **Gebaut 2026-11-24, vor S5
     und S6 vorgezogen** (dein „Map-Pfade“ und „S7 jetzt vorziehen“, §20).
  - Gegenüber deinem Vorschlag kommen S2 und S4 dazu und stehen früh, weil sie nur S1 brauchen. Der Cube rückt hinter
    sie, weil er mit dem Studio als Inhalt sichtbar wenig ändert (§8).
- **Core und Format:** keine Änderung in S1 bis S5.
  - S6 bringt `SceneObject.look_regions` (Format v16).
  - S7 bringt `LookMaterial.maps` (die nächste Version; gebaut als v16, S6 wird damit v17).
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
| V16 | The bounds are `RenderMesh.derived.bounds_min` / `bounds_max` (`DerivedView`, lazy over `PackedGeometry.bounds`; corrected at S1, 2026-11-22: there is no `RenderMesh.bounds_min`) and `model_matrix` | `render_mesh.py:253–263` (`DerivedView`), `:398–402` (`derived`), `packed_geometry.py:301`; `render_mesh.py:322`, `:841` |
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
| C9 | (S1 code check, 2026-11-22) §2.4: unit 5 is "the Worklight's face corners", 6 / 7 free for the shadow map and its raw depth | The Worklight draw also binds the VertexList's position / normal buffers as buffer textures on **6 and 7** (O2, `gl_render_store.py` `_POSITIONS_UNIT` / `_NORMALS_UNIT`) and unbinds all of its face-data units after its draw (`_unbind_face_data`, `:872–880`) | No clash at a skin draw: the shadow map binds 6 only around the skin draw and unbinds it; T1-5 checks units 0–7 (2D, buffer, sampler) after a frame with Worklight-free entries and an eye |
| C10 | (S1 code check) §2.1: `set_lookdev_effect` "refused like the studio setters while an interaction owns the input" | The studio setters (`set_lookdev_studio`, `set_lookdev_light`, `set_lookdev_studio_preset`) refuse nothing while an interaction runs; the panel only gets the mouse over itself (`input_gate`) | `set_lookdev_effect` follows the code: like the studio setters, no refusal |

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
     unchangeable eye tests read `key[-1]` (AD-038 I-1). **As built (S2-1, §17.2):** only an LD_SHADOW program's key
     has the 10th value; every other program keeps the 9-value key (an unchangeable test asserts `len(k) == 9`).
5. **Compile:** `Viewport.prepare_lookdev` (`viewport.py:522` at S2; the AD had `:475`) compiles the variants the effects and the drawn objects
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
| 5 | — (the Worklight's face corners; kept free, see below) | — |
| 6 | key shadow map, compare sampler (S1) | key shadow map (S2) |
| 7 | key shadow map, raw depth through a sampler object (S4) | — |
| 8 | environment cube (S5) | — |
| 9–11 | roughness, normal, translucency maps (S7) | — |
| 12 | triangle material slots (S6) | — |

  Every pass unbinds what it bound, including sampler objects (`glBindSampler(unit, 0)`), and leaves unit 0 active.
  **No unit carries two texture targets at a draw.** P3-0 run 2 [M-RPC]: the stand-in's cube on unit 5, where the
  stand-in UV binding (`_flush_face_data`) had bound the face corners as a buffer texture, failed every draw with
  `GL_OUT_OF_MEMORY` while 270 MiB were free. Run 3 (cube on 8) failed the same way, so the
  clash was **not** the cause. The cause of the cube rows' failure is open (run 4, `--p3-cube-check`, §11.1). The rule
  stays: the production `bind_triangle_uvs` binds unit 3 only, and the cube stays on 8.

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
| S1 shadow lookup | ≤ +2 ms (P3-0 run 2: +1.1 / +1.8 ms) | depth pass ≤ 3 ms at SubD 1 (a pose, morph or key change) |
| S2 eye shadow | ≤ +0.5 ms | — |
| S3 dual lobe | ≤ +0.5 ms | — |
| S4 thickness | ≤ +0.5 ms | — |
| S5 cube | ≤ +0.3 ms (P3-0 run 5: −0.4 / −0.6 ms, cheaper than the analytic studio) | prefilter 12 ms + CPU copy 17–24 ms on a preset switch [M-RPC] |
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

- **Re-ordered 2026-11-24 (Manu: „S7 jetzt vorziehen“, with Q-P3-2 „Map-Pfade“):** S7 is built before S5 and S6. It
  depends on neither; only the format number moves (S7 = v16, S6 = v17). S5 and S6 keep their order after it.
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
  (V9). (As built, §17.2 S2-2: three sites without a LOOKDEV block take a standalone `#ifdef LD_SHADOW` block.) The library piece `LD_SHADOW_SRC` (shared with S1, the same text) is appended only when it is on. A global
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
  - `eye_pass.py`: the key 9 → 10 (before `sclera`), unit 6, the shadow uniforms from the frame dict (as built:
    from `KeyShadow.uniforms()`, §17.2 S2-3);
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
- **Built 2026-11-23 (§18).** The energy test above does not hold for these values above r ≈ 0.4: the mix reflects up to
  a third more than the single lobe at r = 0.8, while staying ≤ 1. The test was replaced, and the numbers are recorded
  (§18.2, S3-1).

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
- **Built 2026-11-23 (§19).** The scale is 0.05 world units, not 0.6: `Gollum_Head_05` is not at 1 unit = 1 cm (§19.2,
  S4-1, open for Manu). The probe row is `lookdev +shadow +thick`.

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
- **Built 2026-11-24 (§21).** As §11.1 run 4 / 5 changed it: the prefilter renders into a scratch cube, the chain is
  read back and uploaded into the cube the skin samples, and a preset switch waits one frame behind the status line
  „LookDev: Umgebung wird vorbereitet …“. With the dual lobe the reflection takes two lookups (run 5). Level 0 holds
  within one RGBA16F step, not 1e-3 (§21.2 S5-2).

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

**Decided 2026-11-24 (Manu, Q-P3-2): „Map-Pfade“** - the recommendation below; built in §20.

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

**Reference PC, run 1 (Manu, 2026-11-22) [M-RPC]:**
[`RESULTS_LOOKDEV_P3_REFERENCE_PC_2026-11-22.md`](../../experiments/drag_cost/RESULTS_LOOKDEV_P3_REFERENCE_PC_2026-11-22.md).
- **Aborted after (p3a):** `GL_OUT_OF_MEMORY` at the first frame rows, in both processes. The failing row is unknown,
  because the probe printed sections only at their end. The probe now prints each line at once, shows the free VRAM
  (`GL_NVX_gpu_memory_info`), drops a failing row and continues, and creates only the maps the chosen rows need.
- **(p3a) the depth pass alone is about 1 ms** (0.7–1.2 ms p50) at 512² to 2048², with or without the eyes, cage and
  SubD 1. This is far under S1's 3 ms target. LD-0's 9–11.5 ms were not the pass (C6).
- **Run 2 (Manu, 2026-11-22) [M-RPC]:** complete except the cube rows (`cube env`, `cube dual env`, `p3 all`): they
  failed with `GL_OUT_OF_MEMORY` at every draw while 270 MiB VRAM were free. The cause is a stand-in unit clash (§2.4),
  not memory; the probe's cube moved to unit 8. GPU ms over `ld frame`, framed 1024×768 unless named:

| Row | cage | SubD 1 | close, SubD 1 |
|---|---:|---:|---:|
| depth pass alone, 1024², skin (absolute) | 0.51 | 0.49 | — |
| `shadow 1k x4` | +0.76 | +1.04 | +1.76 |
| `shadow 1k x9` | +1.11 | +1.78 | +2.76 |
| `shadow 1k x16` | +1.17 | +1.94 | +3.08 |
| `shadow 2k x9` | +1.09 | +1.81 | +2.78 |
| `drag 1k x9` (map every frame) | +7.35 | +9.86 | +10.75 |
| `thick 1k x9` | +0.50 | +0.85 | +1.35 |
| `dual direct` | +0.21 | +0.06 | +0.16 |
| `dual env` | +0.91 | +1.35 | +2.52 |

  What it decides:
  - **S1's fixed setting: 1024², 3 × 3 fetches (Q-P3-3 as proposed).** The lookup does not depend on the map size
    (1k = 2k), so 2048² only costs memory (16 MiB instead of 4). The framed head with the shadow takes 2.8 / 4.0 ms
    GPU, 8 / 12 % of 33.3 ms. S1's lookup target in §2.5 becomes ≤ +2 ms (SubD 1 measured +1.78 ms).
  - **The drag is the open cost.** Re-rendering the map every frame costs 7–10 ms more than the lookup, although the
    pass alone takes 0.5 ms [H: the driver waits when the depth texture is written and then sampled in the same frame].
    The frame stays at 9–12 ms GPU and 24–26 ms wall, under 33.3 ms, but tight. S1 measures it in production
    (`lookdev +shadow drag`) and, if it holds, tries in this order: render the map first in the frame with a flush
    before the background; then two maps used alternately (ping-pong).
  - **S3: the second lobe on the lights only** (+0.06–0.29 ms). On the analytic studio a second lobe costs +0.9–4 ms,
    so the environment keeps one lobe until S5's cube is measured (`cube dual env`).
  - **S4 is cheap:** `thick 1k x9` costs less than the shadow row alone (+0.50 against +1.11), a compiler difference
    between the two variants [H]. S4's production row decides.
  - **Run 3 (cube rows only, cube on unit 8):** failed again with 277–311 MiB free. The unit hypothesis is withdrawn.
    The GPU prefilter works (12.1 ms); sampling the cube in the skin stand-in fails. **S5 stays blocked on this until
    run 4** (`--p3 --p3-cube-check --size 1024 768`) shows which part fails. If the cube cannot be sampled in the skin
    pass on this card, S5 falls back to the analytic studio and moves behind S6 / S7, and the rest of P3 is unaffected.
  - **Run 4 (`--p3-cube-check`):** a cube **rendered** through an FBO samples once and then fails every later draw; a
    cube **uploaded** from the CPU always works (RGBA16F with mips, level 0 only, RGBA8). Seamless filtering, `textureLod`,
    the program, the albedo map and the eyes are not the cause [H: a driver defect with FBO-rendered float cubes on this
    card]. **S5's design changes accordingly [P]:** prefilter on the GPU (12 ms), then read the chain back and upload
    it into the sampled cube once per studio content change (container ≈ 2 ms for 128²; the reference PC measures it).
    This is a workaround for an observed defect, so it is gated: S5 keeps a test that a rendered-then-copied cube
    samples over many frames.
  - **Run 5 — P3-0 complete.** Case M (rendered, then read back and uploaded) draws 5 of 5 frames; case L (rendered
    only) fails in its first. The copy costs 17–24 ms wall once per studio content change, after the 12 ms prefilter.
    Together that is a one-frame hitch on a preset switch; S5 shows the status line of §2.1 for it. On the copy:
    - `cube env` is **cheaper** than the analytic studio: −0.4 / −0.6 ms framed (cage / SubD 1), −1.3 / −1.5 ms
      close at 1024×768, −2.6 ms close at 1920×1080. S5's target in §2.5 holds with a margin.
    - `cube dual env` (two lobes on the cube) still costs less than one analytic lobe. S3 uses the second lobe on the
      environment too once S5 is in; before S5 the lights only (run 2).
    - **`p3 all`** (shadow 1k × 9 + thickness + dual lobe + cube) is **1.69 / 2.29 ms GPU framed at 1024×768, 5 / 7 % of
      33.3 ms**: about what the room costs today without any P3 effect. The total budget of §2.5 (≤ 9.5 ms) holds with a
      wide margin. The open cost is the shadow drag (run 2).
    - Order: the cube's saving pays for S1–S4's cost. The order of §3 stays, because the budget is not tight. If S1's
      production drag cost is a problem, S5 can come right after S1.

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
   in the slice's commit. *S7: given 2026-11-24 („Map-Pfade“), the entry is in S7's commit (§20).*
6. **Keys:** none (D-L9).
7. **LD-3** after P3: one AD or AD section with the full knob set (cube size, shadow size, PCF fetches) and the feature
   report of §2.2.

---

## 13. Open questions for Manu, with proposals

| # | Question | Proposal |
|---|---|---|
| **Q-P3-0** | Accept the slice order S1 → S7 (§3), with S2 and S4 added after the shadow map? | yes; the practical test may re-order (§12 point 3) |
| **Q-P3-1 (LD-D8)** | Region materials: face regions with a material per region on the object, or a separate mouth object? | **face regions** (§9): `SceneObject.look_regions`, ≤ 4 per object, later entry wins on overlap, keyed by name; format v16. The separate object stays a no-code fallback |
| **Q-P3-2 (paint channel)** | Roughness / normal / translucency: a map path on the material, or a second paint stack per channel? | **map paths first** (§10), `LookMaterial.maps`, imported images; painted channels later as their own AD-037 phase. **Decided 2026-11-24 (Manu): „Map-Pfade“; built §20** |
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

---

## 16. Implementation note — S1 built (2026-11-22)

**Kurzfassung (Deutsch):** Die Schattenkarte vom Key ist gebaut (Haut und Zähne werfen und empfangen, Augen weder noch).
Sie wird nur bei Pose-, Form- oder Key-Änderung neu gerechnet. Panel-Block „Effekte“ mit „Schatten“; die Einstellung
wird mit der Szene gespeichert. Schatten aus ist M1, Zeichen für Zeichen (neuer Haut-Pin) und Pixel für Pixel (alter
gegen neuen Code am Gollum-Kopf geprüft). Die Kosten des Ziehens misst erst dein PC; die zwei Gegenmittel aus P3-0
(Flush, zwei Karten) sind gebaut und abschaltbar, die Sonde misst alle drei Varianten in einem Lauf.

### 16.1 What is built

| Layer | Built |
|---|---|
| Pin | `PINNED_SKIN_SOURCES_SHA256` over the 4 M1 skin variants (12 sources), taken in its own commit before `lookdev_shaders.py` changed (`ae19de5`); `tests/test_lookdev_shaders.py` |
| Effects | `lookdev_optics.LookdevEffects(shadow=True)`, `LookdevState.effects` (the frame cache key covers it), `effective` / `effect_reasons` (dependencies, missing features; the panel's reasons); `Application.set_lookdev_effect(name, on)`, `lookdev_effect_reasons()`; a studio preset switch keeps the effects |
| Features | `viewport/lookdev_features.py`: `FeatureReport(depth_texture)`, `probe()` once per context (held by `LookdevPass.features`), `CHECKS` (a test stubs one); a missing feature turns the effect off and queues one status line „LookDev: Schatten aus – Tiefentextur nicht verfügbar“, shown by the app (`_lookdev_feature_status`), not retried |
| Shaders | `LD_SHADOW_SRC` (`u_ld_shadow`, `u_ld_shadow_vp`, `u_ld_shadow_radius`, `u_ld_shadow_offset`, `ld_key_visibility(p, n)`), appended only with `SHADOW`; the `SKIN_BODY` block `#ifdef SHADOW` subtracts (1 − vis) × the key's own `ld_wrap` / `direct_specular` term; `skin_sources(..., shadow=False)` resolves the block with `eye_shaders._without` when off; `SHADOW_DEPTH_*` (the depth pass's own minimal program). `LD_COMMON_SRC` unchanged |
| Map | `viewport/lookdev_shadow.py` `KeyShadow`: 1024² DEPTH_COMPONENT24, `GL_LINEAR` + compare `LEQUAL`, `CLAMP_TO_BORDER` (border 1.0), polygon offset (2, 4); the cache key per frame (per caster `(id, layout_revision, content_revision, model)`, key direction, frustum); the frustum (`lookdev_optics.shadow_frustum`, +15 %) only on a caster-set / layout / placement change; full GL save / restore; `renders`; options `flush` and `maps=2` (§16.4) |
| Pass | `LookdevPass`: program key `(ALBEDO_MAP, ENV_SPEC, SHADOW)`, owns `KeyShadow` (`key_shadow()`, deleted in `release()`), binds the map on unit 6 for the draw and unbinds it |
| Viewport | `_render_lookdev`: the casters (the edit surface and every entry with a `LookDraw`, Ghosts and eyes excluded) and `KeyShadow.update` before the background; `set_lookdev_effects` / `lookdev_effects(wanted)` / `lookdev_features` / `take_lookdev_notices`; `_lookdev_programs` / `prepare_lookdev` compile the variants of the wanted effects |
| App | the I-10 path for a switch that compiles (the frame before stays in LookDev for those frames, `_apply_lookdev` leaves it; then `prepare_lookdev` and the switch); `view.lookdev.effects` (written always, read with `raw.get`, unknown names ignored, a bad value keeps the current effects and never skips the studio) |
| GUI | panel block „Effekte“ under „Studio“: one checkbox per built effect, greyed with its reason as tooltip (`lookdev_model.EffectRow`) |
| Probe | `probe_lookdev_room.py --effects <list>|none`; rows `lookdev` (effects off), `lookdev +shadow`, `lookdev +shadow drag` (+ `flush`, `pingpong`), `KeyShadow.renders` per row; the drag steps a probe morph target on the edit object each frame (in memory only) |

Not touched: `src/core/`, `serialization.py`, the Worklight programs, `GLRenderStore.draw()`, `eye_shaders.py`,
`eye_pass.py`, `main.py`, `config/keymap.json` (no keys). R-1 unchanged (`tests/test_room_rule.py`).

### 16.2 Where the build differs from §2 / §4, and why

| # | AD | Built | Why |
|---|---|---|---|
| S1-1 | §4 uniforms `u_ld_shadow`, `u_ld_shadow_vp`, `u_ld_shadow_radius` | plus `u_ld_shadow_offset` (the normal offset in world units = 1.5 texels of the effective map) and `u_ld_shadow_scale` (the rendered part of the map, §16.6); `ld_key_visibility(p, n, l)` is split into `ld_shadow_coord` and `ld_shadow_pcf` (the parity test reads the latter) | the offset needs the map's texel size in the world, which depends on the frustum and the softness |
| S1-2 | §4 "the fetch spacing is scaled by the key's `size`" | **revised 2026-11-22 (§16.6):** the fetches stay one texel apart; the key's size sets the map's **effective resolution** (`shadow_resolution`: 1024 / (1 + 5 × size), at least 96 texels; Portrait 0.10 → 683, 0.26 → 445, Soft Studio 0.35 → 372, 1.0 → 171), rendered into that corner of the 1024² map | spreading 9 fetches up to 9 texels apart dipped under curved skin and drew stepped copies of the edge (Manu's practical test) |
| S1-3 | §4 bias "polygon offset (2, 4) plus a normal offset of about one texel" | plus a constant compare bias of 0.0005 of the map's depth (2 r) and a **receiver-plane bias** per fetch (the depth slope from the screen derivatives of the map point, clamped at 10); the normal offset (1.5 texels of the effective map) is the normal **projected off the key** (sideways only); the key's **wrap excess** looks the map up at the point lifted 4 offsets out along the normal (a second 3 × 3 lookup) | T1-2 (no acne, also with a soft key at a grazing 20°); the lifted wrap lookup keeps a convex surface's wrap past the terminator while a crease's cast shadow stays dark (§16.6, §16.7) |
| S1-4 | §4 frustum "recomputed only when the caster set or a layout_revision changes" | also on a placement change (a caster's model matrix) | a moved object must stay inside its map; a placement is not a pose step, so a drag does not swim |
| S1-5 | §2.1 "refused like the studio setters while an interaction owns the input" | no refusal (C10) | the studio setters refuse nothing in the code |
| S1-6 | (not stated) | pyglet 2.1 has no setter for `sampler2DShadow`: `lookdev_shadow.register_shadow_sampler_uniform` reuses the `sampler2D` entry | the `_register_sampler_buffer_uniform` pattern |
| S1-7 | §2.1 "a switch that needs a program not compiled yet takes the I-10 path: one frame with the status line" | while it prepares, the room keeps drawing the **previous** LookDev state (not the Worklight, as on entering); other studio changes made meanwhile wait for the compile | a switch inside the room must not flash the Worklight |
| S1-8 | §11.1 "if it holds, try the flush, then two maps" | both built as `KeyShadow` options, off by default; the room probe measures plain / flush / ping-pong in one run | the container cannot measure the reference PC's driver; Manu's run decides, then the default is set in one place |

### 16.3 Tests (container, llvmpipe, 2026-11-22)

New tests:

| # | Test | Where |
|---|---|---|
| T1-1 | a box over a plane: the footprint (CPU ray cast through the key) is dark (> 99 % of its pixels darker by > 40/255, black with no fill / environment), the rest of the plane unchanged (> 99.9 % within 1/255), the box's lit top without acne | `tests/test_gl_lookdev_shadow.py` |
| T1-2 | a lit sphere, key at 60° and 20°, hard and soft (size 0 / 0.3 / 1.0): ≤ 0.1 % of the pixels with n·l > 0.1 darkened; the penumbra widens with the size while a dark core stays; §16.7: a cast shadow under a 15° key with a wide wrap is black (99th percentile ≤ 2/255; fails on `af4fe14` with 17), the wrap past a sphere's terminator is kept (median ≥ 95 %) | same |
| T1-3 | `KeyShadow.renders`: viewport level (camera orbit, exposure / key intensity / colour / size, a capture frame +0; key azimuth, rotation, a caster vertex +1 each; the frustum unchanged by a geometry step) and in the app on the head (a morph weight, a jaw pose step, the key azimuth, the rotation +1 each, once; orbit, exposure, key intensity / size, capture +0; the frustum unchanged by morph and pose; „Licht folgt Kamera“ + orbit +1) | same |
| T1-4 | `PINNED_SKIN_SOURCES_SHA256` holds with the shadow off; no `KeyShadow`, no probe; the frame equals one drawn with a program from the M1 call; with nothing between key and surface the shadow changes no pixel. One-off: old (`ae19de5`) vs new code on Gollum, pixel-identical (§16.4) | `tests/test_lookdev_shaders.py`, `tests/test_gl_lookdev_shadow.py` |
| T1-5 | a frame that renders the map (with an eye, scissor on, a foreign polygon offset) leaves draw / read framebuffer, viewport, program, VAO, caps, depth mask / function, polygon offset, units 0–7 (2D, buffer, sampler) as found | `tests/test_gl_lookdev_shadow.py` |
| T1-6 | `depth_texture` stubbed false: the frame equals the M1 frame, no map, the status line once, not retried; in the app the status line appears and the panel row is greyed „Tiefentextur fehlt“ | same |
| T1-7 | `view.lookdev.effects` round trip; an LD-2 file without `effects` keeps its studio and the current effects; 5 bad values keep the effects and never skip the studio; an unknown name is ignored | `tests/test_lookdev_persistence.py` |
| T1-8 | `shadow_frustum`: every caster vertex (model matrices, teeth) inside the map for 26 key directions; a jaw-like pose inside the margin stays inside; the light side is depth 0 | `tests/test_lookdev_optics.py` |
| parity | `ld_shadow_pcf` (GPU, a random 64² map, the full map and half of it rendered, 4,096 points with random receiver slopes incl. border and depth range) vs `pcf_visibility` (max ≤ 0.02, mean ≤ 0.003; the twin clamps the reference to [0, 1] as a fixed-point depth texture does); the `SHADOW` block vs `ld_key_shadowed` in full shadow and full light (≤ 2.5/255) | `tests/test_gl_lookdev_shadow.py`, twins headless in `tests/test_lookdev_optics.py` |
| app / panel | `set_lookdev_effect` (view state, no Undo, a preset keeps the effects, unknown name refused); a switch that compiles keeps the previous LookDev frame; the panel block | `tests/test_lookdev_room.py`, `tests/test_gui_lookdev_model.py` |
| probe | `probe_lookdev_room.py --effects` arguments | `experiments/drag_cost/tests/test_probe_lookdev_room.py` |

Runs (GL files each in their own process under xvfb):

| Command | Result |
|---|---|
| `xvfb-run -a python -m pytest tests/test_gl_lookdev_shadow.py -q` | 12 passed; 16 after §16.6; 18 after §16.7 |
| `xvfb-run -a python -m pytest tests/test_gl_eye_pass.py -q` | 126 passed (all three eye pins incl. the Worklight pin unchanged) |
| `xvfb-run -a python -m pytest tests/test_gl_face_data_layout.py` / `test_gl_shading.py` / `test_gl_texture.py` (E1) | 16 / 19 / 10 passed |
| `xvfb-run -a python -m pytest tests/test_gl_gpu_picking.py` / `test_gl_morph_picking.py` (E15) | 37 / 16 passed |
| `xvfb-run -a python -m pytest tests/test_gl_lookdev_pass.py` / `test_gl_lookdev_parity.py` | 13 / 7 passed (with the shadow on by default) |
| `xvfb-run -a python -m pytest tests/test_gui_imgui_window.py` / `test_gui_lookdev_window.py` | 18 / 1 passed (the panel with „Effekte“ in the real window) |
| `xvfb-run -a python -m pytest tests -q` | 7,920 passed, 8 skipped, 1 failed: `test_scene_menu_local_tmp.py::test_probe_menu_wiring` - **pre-existing**, fails identically at `ae19de5` (before S1; AD-038 §17.3) |
| `xvfb-run -a python -m pytest experiments/morph_lab/tests -q` | 49 passed |
| `xvfb-run -a python -m pytest experiments/drag_cost/tests -q` | 103 passed |
| `xvfb-run -a python -m pytest experiments/lookdev_eye_lab/tests -q` | 206 passed (the frozen oracle) |

Not run: `experiments/knife_oracle/tests` (no Knife or topology code touched).

### 16.4 Measurement

Container (llvmpipe, a function check only; its GPU ms are a CPU rasteriser's and say nothing about the reference PC):
`python experiments/drag_cost/probe_lookdev_room.py --draws 3` ran all rows with `glGetError` 0; `KeyShadow.renders`
is 0 in the still rows (`lookdev`, `lookdev +shadow`) and one per frame in the three drag rows (8 of 8). One-off
check: the Gollum head (cage and SubD 1, Portrait, framed, eyes in) rendered with the code before S1 (`ae19de5`) and
with S1 and the shadow off is **pixel-identical**; with the shadow on 1,065 / 443 px change (the nose, the ear).

**Reference PC (E16 and S1, open):** NVIDIA "Maximale Leistung bevorzugen", repository root, `.venv312`:

```
python experiments\drag_cost\probe_lookdev_room.py | Tee-Object -FilePath lookdev_room_s1.txt
python experiments\drag_cost\probe_lookdev.py --no-extras | Tee-Object -FilePath lookdev_ld0_after_s1.txt
python experiments\drag_cost\probe_d3_acceptance.py | Tee-Object -FilePath d3_after_s1.txt
```

What the run decides:
- `lookdev +shadow` against `lookdev`: S1's lookup target ≤ +2 ms (§2.5; P3-0: +1.1 / +1.8 ms).
- `lookdev +shadow drag` against `lookdev +shadow`: the open drag cost of P3-0 (+7–10 ms in the stand-in although the
  pass took 0.5 ms). If the production drag shows it too, `drag flush` and `drag pingpong` say which remedy helps; the
  better one becomes `KeyShadow`'s default (one line), in the order flush → ping-pong. If neither helps, the drag still
  holds ≥ 30 fps when the row stays under 33.3 ms wall; otherwise the levers of §2.5 apply.
- `modelling` / `modelling after`, `probe_lookdev.py --no-extras` and `probe_d3_acceptance.py`: E16, within noise of
  the last runs (the Modelling Room loses nothing).

### 16.5 Practical test S1 (`scenes/Gollum_Head_05.mirai.json`, about 15 minutes)

Open LookDev (SPACE row „LookDev öffnen“), view „¾“.
1. **Schatten an / aus:** in „Effekte“ „Schatten“ aus- und einschalten. Erwartet: unter Nase, Brauen, Ohr und Kinn liegt
   mit „Schatten“ der Schatten des Key; aus = genau das Bild von vorher. Wirkt der Schatten zu hart, zu weich, zu
   dunkel, schwimmt oder flackert er?
2. **Weichheit:** „Mehr“ einschalten, dann im Block „Licht“ in der Zeile **Key** „Weichheit“ von 0 bis 1 (nicht die
   „Weichheit“ im Material). Erwartet (nach §16.6): die Schattenkante wird gleichmäßig weicher, ohne Flecken und ohne
   gestufte Kanten; feine Schatten (Lidfalten) verblassen bei sehr weichem Key. Der Glanz wird breiter.
3. **Die vier Studio-Vorlagen:** Neutral Inspection, Portrait, Soft Studio, Dramatic. Erwartet: der Schatten folgt dem
   Key jeder Vorlage, „Schatten“ bleibt beim Wechsel wie eingestellt. Passt er in jeder Vorlage, besonders in Dramatic
   (Key von der Seite)?
4. **Pose und Morph ziehen:** einen Morph-Regler langsam ziehen und eine Pose (Kiefer) drehen. Erwartet: der Schatten
   geht mit, ohne zu springen; das Ziehen bleibt flüssig. Wie fühlt es sich an gegenüber Schatten aus?
5. **Zähne einblenden:** „tooth“, „tooth01“, „Zahn_1“, „Zahn_2“ im Outliner einblenden, Mund öffnen (Morph / Pose).
   Erwartet: Lippen werfen Schatten auf die Zähne, die Zähne auf die Mundhöhle; die Augen werfen keinen Schatten und
   liegen noch nicht im Schatten der Lider (das ist S2).
6. **Bild speichern** mit Schatten: das PNG zeigt den Schatten wie der Viewport.

Assumptions to correct in one sentence: the key's „Weichheit“ also softens the shadow (S1-2); the shadow is on by
default; teeth are hidden in the file and shown only for this test.

### 16.6 Revision after Manu's first look (2026-11-22): „Weichheit wirkt noch sehr unsauber“

Manu's screenshot (Dramatic, Creature Skin, the key's „Weichheit“ 0.26): blotchy dark patches across cheek, temple and
the nasolabial fold. Reproduced in the container on `Gollum_Head_05` (cage and SubD 1). Two causes, both in the S1
lookup, not in the driver:

1. **The spread fetches.** S1-2 spread the 3 × 3 fetches up to (1 + 8 × size) texels apart. On curved skin a fetch that
   far from the centre compares the receiver's depth against the surface itself several texels away: self-shadow
   blotches. Beyond 2 texels the fetches' 2 × 2 footprints also leave gaps, so the edge shows as three stepped copies.
2. **The terminator.** The organic presets' wrap diffuse lights past n·l = 0, where the map holds the mesh's own
   facets; on the cage that cuts the wrapped light along triangle edges.

Fixed with the established techniques, without more fetches:
- **Softness = effective resolution:** the fetches stay one texel apart (a contiguous bilinear-compare ramp), and a soft
  key renders the map into a smaller corner of the 1024² texture (`lookdev_optics.shadow_resolution`); the rest of the
  texture is cleared to 1.0 (lit). The penumbra widens smoothly; small shadows fade at high softness as under a large
  light. A softness change that changes the resolution re-renders the map once (`KeyShadow.key`).
- **Receiver-plane depth bias** (Isidoro, GDC 2006): each fetch compares the depth of the receiver's own plane at that
  fetch, the slope taken from the screen derivatives of the map point.
- **Terminator fade:** the map's answer is weighted by smoothstep(0, 0.3, n·l), so near the terminator the shading
  model's falloff decides, not the facets. Tried and rejected: a normal offset growing toward grazing light (×4 and ×10
  of 1.5 texels) – it leaked light in streaks into real cast shadows (the nasolabial fold).

(The terminator fade described here was replaced in §16.7.) Result (container, Dramatic, Creature Skin, framed): SubD 1 clean at 0 / 0.26 / 1.0 (hard, soft, very soft); on the
cage a few thin lines remain along the coarse facets at the neck and the inner eye corner – the cage's own polygons,
which SubD smooths. Pixel cost: unchanged 9 fetches plus two screen derivatives; a soft key's depth pass is cheaper
(fewer texels). Tests: T1-2 with soft keys, a penumbra test, the parity with slopes and a half-rendered map (§16.3).

### 16.7 Revision 2 (2026-11-22): „in der Nase und um die Mundwinkel entstehen sehr helle Ränder um die Schatten herum“

Manu's screenshot: Dramatic, Creature Skin, key „Weichheit“ 0.03, the face from the front. Reproduced; a CPU ray cast
against the drawn SubD surface sorted the cause out (`probe`-style script in the session, not committed):
- The rims are **not** a bias leak: with every bias at 0 they stay, and no pixel gets brighter than without the shadow.
- The rim pixels lie in real cast shadows (175 of 175 occluded, the occluder a median 17 texels ≈ 7 mm away: the far
  wall of the nostril, the lip at the mouth corner), mostly at n·l < 0.3.
- §16.6's terminator fade lifted the map's answer there for the key's **whole** term - its Lambert part, its wrap and
  its highlight (strong at grazing light through Fresnel). Creature Skin's wide wrap made the rim bright.

Fix: the fade is gone. The key's Lambert part and highlight take the map's answer as it is. Only the **wrap's excess**
past Lambert (the light the organic presets carry past the terminator) looks the map up at a point lifted
`SHADOW_WRAP_LIFT` = 4 normal offsets (≈ 6 texels) out along the normal: on a convex surface that point leaves the
surface's own shadow just past the terminator (the cage-facet problem §16.6 solved with the fade), in a crease it stays
in the far wall's shadow. The normal offset is also projected off the key (sideways only), so a surface facing the key
right behind an occluder's edge is not moved toward the light. Cost: a second 3 × 3 lookup (18 compare fetches per
pixel; P3-0 measured 9 → 16 fetches at +0.06–0.3 ms on the reference PC) - the room probe's `lookdev +shadow` row
measures it. Result: nostrils and mouth corners without rims; the nose now also shadows the cheek's wrap (the fade had
cancelled that cast shadow); the cage at softness 0.26 as clean as with the fade, the neck calmer.

Tests: `test_a_cast_shadow_at_a_grazing_key_keeps_the_wrap_and_the_highlight_dark` (fails on `af4fe14`),
`test_the_wrap_past_a_convex_terminator_is_not_cut`, the twins (`shadow_coords(..., key_dir, lift)`,
`ld_key_shadowed(..., wrap_visibility)`).

---

## 17. Implementation note — S2 built (2026-11-22)

**Kurzfassung (Deutsch):** Die Augen liegen jetzt im Schatten des Key: Lider, Brauen und Nase des Kopfes werfen ihn auf
den Augapfel, aus derselben Schattenkarte wie S1 (die Augen werfen weiter keinen). Der Schatten skaliert jedes
Key-Licht des Auges – Lambert der Sklera und Iris (samt Key-Tabelle), GGX-Glanz, Key-Spiegelung auf Hornhaut und Film,
Punkt und weich; Umgebung, Fill, Rim und Studio-Spiegelung bleiben. Neuer Schalter „Augen-Schatten“ im Block „Effekte“
(Standard an, braucht „Schatten“), mit der Szene gespeichert; eine S1-Datei behält ihre Einstellungen. Augen-Schatten
oder Schatten aus = das S1-Auge, Zeichen für Zeichen (Pins) und Pixel für Pixel (alter gegen neuen Code am Gollum-Kopf,
12 Bilder). `EyeLook.lid_shadow` bleibt (Q-P3-6, dein Praxistest). Die Kosten misst erst dein PC (Zeile
`lookdev +shadow +eyes`).

### 17.1 What is built

| Layer | Built |
|---|---|
| Effects | `LookdevEffects.eye_shadow` (default on), `EFFECT_NEEDS = {"eye_shadow": "shadow"}` (the panel's reason „braucht Schatten“), `EFFECT_LABEL` „Augen-Schatten“; `view.lookdev.effects` reads it optionally (S1's reader already replaces only the names present: an S1 file without `eye_shadow` keeps the current eye shadow) |
| Shaders | `eye_shaders.shell_sources(..., lookdev=False, ld_shadow=False)`: `ld_shadow` the last keyword, forced off without `lookdev`; define `LD_SHADOW`; `lookdev_shaders.LD_SHADOW_SRC` (the skin's string, unchanged) appended after `LD_COMMON_SRC` only with it; the body blocks resolved by `_without(body, "LD_SHADOW")` before `LOOKDEV`. `LD_COMMON_SRC` unchanged |
| Body blocks (9) | the global `float ld_key_vis` (in the LOOKDEV uniform block); `ld_key_vis = ld_key_visibility(v_world_pos, to_world(normalize(p)), u_ld_light_dir[0])` once in `main()` right after the shell point `p` (uniform control flow, before any branch); B1 `lit()` minus (1 − vis) × the key's Lambert term; `ld_specular_vis` (the three GGX lobes, the key's times vis) at both B6 sites; B2 `iris_lit` `u_key_color * (ld_key_vis * k)` (the key table's term); B5 `cornea_reflection`'s key and `key_reflection`'s point and soft (area) key times vis |
| Pass | `EyePass.program_key(..., ld_shadow=False)` / `program(...)` / `draw(..., shadow=None)`: a rendered `KeyShadow` with `lighting` draws the LOOKDEV + LD_SHADOW program, its `uniforms()` set, the map bound on `SHADOW_UNIT` = 6 (`lookdev_shaders.SHADOW_UNIT`) for the draw; after it `glBindSampler(6, 0)` and the texture unbound; `register_shadow_sampler_uniform()` before the first such compile |
| Viewport | `_casts_key_shadow` (a LookDraw, not a Ghost: S1's caster rule, now one place); `_render_lookdev` hands the `KeyShadow` to the eye draw when `shadow` and `eye_shadow` are in force **and** something casts; `_lookdev_programs` adds the same flag to every eye variant, so `prepare_lookdev` compiles the LD_SHADOW eye program behind the status line (I-10) and `lookdev_prepare_needed` sees a switch. The Worklight path is untouched |
| Twins | `lookdev_optics.eye_key_dimmed(values, vis)` (the blocks as a frame dict: the eye with visibility vis = the eye without the blocks under a key of vis × its colour); `eye_sclera_shadowed` (the plain sclera: `lit` + GGX with the key scaled) |
| GUI | `lookdev_model.EFFECT_LABELS` / `EFFECT_HINTS`: the row „Augen-Schatten“ (greyed „braucht Schatten“ with the shadow off) |
| Probe | `probe_lookdev_room.py`: `EFFECT_ROWS`; the row `lookdev +shadow` now has the eye shadow **off** (skin and teeth only, as S1 measured it) and `lookdev +shadow +eyes` switches both on (S2's cost = the difference) |

Not touched: `src/core/`, `serialization.py`, `LD_COMMON_SRC`, `LD_SHADOW_SRC`, the Worklight eye sources and the eye's
Worklight draw, `GLRenderStore.draw()`, `KeyShadow`, `main.py`, `config/keymap.json` (no keys), `EyeLook` and every eye
value (Q-P3-6). R-1 unchanged.

**Code check (§5's references, before the build):** `SHELL_VERTEX_SRC` writes `v_world_pos` [V]; V9 (`_without` on the
body only, `eye_shaders.py:1099–1102` at `c1b7732`), V10 (the three pins at `test_gl_eye_pass.py:1099`, `:1137`, `:1491`),
V11 (eye units 1–4, `eye_pass.py:37–43`; the sampler objects at `:295`, not `:296`), V12 (`iris_table`, `:305–374`), V13
(`lid_shadow_weight` at `eye_shaders.py:366–369`, `:840`, `:914`) held; the three eye pins were green before the first
change. §2.3 point 5's `viewport.py:475` for `prepare_lookdev` was stale (`:513` at `c1b7732`, `:522` now) - corrected
there.

### 17.2 Where the build differs from §2 / §5, and why

| # | AD | Built | Why |
|---|---|---|---|
| S2-1 | §2.3 point 4 / §5: "the eye key grows from 9 to 10 values" | an **LD_SHADOW** program's key has 10 values (`True` at index 8, `sclera` stays `key[-1]`, `lookdev` stays `key[7]`); every other program keeps the 9-value key of before | the unchangeable `test_lookdev_programs_draw_and_leave_the_gl_state_clean` asserts `len(k) == 9` for its LOOKDEV programs (an eye with no caster); "effect off = before" now holds for the key as for the sources |
| S2-2 | §5 "body blocks nested inside the existing `#ifdef LOOKDEV` blocks" | six blocks are nested so; three are standalone `#ifdef LD_SHADOW` blocks (the `ld_key_vis` lookup in `main()`, `cornea_reflection`'s key, `key_reflection`'s point key) | those sites have no LOOKDEV block, and a new one would leave `#ifdef LOOKDEV … #endif` text behind with `ld_shadow` off (the LOOKDEV pin). `LD_SHADOW` implies `LOOKDEV` (`shell_sources` forces it), so the standalone blocks are equivalent |
| S2-3 | §5 "the shadow uniforms from the frame dict" | from `KeyShadow.uniforms()`, as the skin pass takes them | the frame dict holds the studio; the map's matrix, scale and offset belong to the map (S1) |
| S2-4 | §5 "the lookup at the shell's world position with its normal" | the normal is the eyeball sphere's radial direction `to_world(normalize(p))`, also on the cornea | the shell VS writes no normal (and is pinned); the normal only steers the sideways offset (1.5 texels), the eyes do not cast, so there is no self-shadow to bias against |
| S2-5 | (not stated) | no caster in the frame (an eye alone) → the eye draws the LOOKDEV program without LD_SHADOW | the map would be empty; the fetches would cost for nothing |

**The approximation, named (§5):** the iris and the limbal tissue seen through the cornea take the visibility of the
shell point in front of them; they lie a few mm behind it, so a lid shadow's edge on the iris can sit up to that
distance off. The practical test judges whether it shows.

### 17.3 Tests (container, llvmpipe, 2026-11-22)

New tests (`tests/test_gl_eye_pass.py` only adds; no existing test or pin changed):

| # | Test |
|---|---|
| T2-1 + parity | `test_a_blocker_between_key_and_eye_darkens_every_key_term` (plain eye; a look with wet film, soft key and the iris key table; a look with the point key): a plate between key and eye → the eye equals the eye under a key of intensity 0 (`eye_key_dimmed(…, 0)`; max 0/255 in the run, bound 2), the key's light gone (99th percentile of the drop > 40/255); a plate whose edge crosses the eye leaves every pixel between the two (±2) with both ends present; without a blocker (a floor casts, not on the eye) the eye equals the eye-shadow-off frame **pixel for pixel**, and that frame drew no 10-value program |
| twin | `test_the_twin_lights_the_plain_sclera_in_full_light_and_full_shadow`: `eye_sclera_shadowed` (CPU sphere normals, the frame dict) against the GPU on the sclera's pixels at visibility 1 and 0 (99th percentile ≤ 3/255, mean < 1) |
| T2-2 | `test_ld_shadow_sources_are_pinned_and_the_old_ones_unchanged`: the Worklight pin (1,030) and the LOOKDEV pin (1,024, also with `ld_shadow=False`) unchanged; new `PINNED_LD_SHADOW_SOURCES_SHA256` over the 1,024 LOOKDEV + LD_SHADOW sources; `LD_SHADOW_SRC` appended once after `LD_COMMON_SRC`; `ld_shadow` without `lookdev` = the Worklight source; the lookup once, before the cornea branch |
| T2-3 | `test_eye_shadow_or_shadow_off_is_the_s1_eye`: with a blocker, `eye_shadow` off and `shadow` off each draw the eye of the S1 frame (no map handed to the eye, 9-value keys only); E7 (grey card, `test_gl_lookdev_pass.py`) unchanged |
| T2-4 | `test_ld_shadow_programs_draw_and_leave_the_gl_state_clean` (plain, soft look): a still frame and one that re-renders the map leave units 0–7 (2D, buffer, **sampler**), framebuffers, program, caps, depth function as found; `glGetError` 0 |
| I-10 | `test_prepare_lookdev_compiles_the_eye_variant_the_effects_need`: `prepare_lookdev` compiles the LD_SHADOW eye program before the frame, the frame compiles nothing; eye shadow off → the 9-value program is prepared; no caster → no shadow program |
| headless | `test_lookdev_optics.py` (the dependency, the reasons), `test_lookdev_persistence.py` (`test_an_s1_file_without_eye_shadow_keeps_its_settings`; the round trip writes both names), `test_lookdev_room.py` (the switch is view state, no Undo, „braucht Schatten“), `test_gui_lookdev_model.py` (the row, greyed with its reason), `experiments/drag_cost/tests/test_probe_lookdev_room.py` (the row `lookdev +shadow +eyes`) |

**Gollum, old against new (one-off, not committed):** `Gollum_Head_05`, cage and SubD 1, Portrait and Dramatic, the
framed ¾ view, the face from the front and a close-up of each eye (1024 × 768, wire and points off): the S1 code
(`c1b7732`) and the S2 code with `eye_shadow` off are **pixel-identical** in all 12 frames. With the eye shadow on,
554–20,753 px change per frame, every one darker (no pixel brighter by more than 2/255).

**The picture, checked with a CPU ray test** (as §16.7; script in the session, not committed): for the eyes' pixels
facing the key (n·l > 0.15) a ray toward the key against the drawn SubD 1 head (19,692 triangles):
- **No light leaks:** of the pixels the GPU leaves lit, 99.5–99.7 % are unoccluded on the CPU.
- **The lid's shadow is geometric:** of the pixels the GPU darkens, 9–38 % are occluded on the CPU; of the rest,
  83–100 % are blocked within 3 texels sideways (Portrait texel 2.9 × 10⁻³ world units = 3 % of the eye's radius at the
  effective 683², Dramatic 2.2 × 10⁻³ at 890²): the penumbra of the 3 × 3 fetches plus the normal offset.
- **What it looks like:** with Portrait (key 45° / 30°) and Dramatic (70° / 20°) the lids cast a **narrow** band on the
  eyeball - a contact shadow along the upper lid, widening toward the outer corner, and the lower lid's rim; the CPU
  agrees that only about 1 % of the key-facing eyeball is occluded at these key heights. A higher key widens it.
- **Named:** in Portrait from the front, the lower inner sclera of one eye darkens faintly beyond the geometric
  penumbra (≤ 8/255, mostly ≤ 3/255; up to 6 % of the darkened samples lie > 6 texels from an occluder), with a faint
  texel staircase only visible amplified × 8. No acne on the cornea: the cornea's pixels change only at the lid margin,
  the highlight is unchanged where the key is unoccluded. Flicker needs the drag and the reference PC: the lookup is in
  world space and the map re-renders only on a change (S1), so an orbit cannot move it.

Runs (GL files each in their own process under xvfb):

| Command | Result |
|---|---|
| `xvfb-run -a python -m pytest tests/test_gl_eye_pass.py -q` | 135 passed (126 before + 9 new; all pins incl. the Worklight pin unchanged) |
| `… tests/test_gl_lookdev_shadow.py` / `test_gl_lookdev_pass.py` / `test_gl_lookdev_parity.py` | 18 / 13 / 7 passed |
| `… tests/test_gl_face_data_layout.py` / `test_gl_shading.py` / `test_gl_texture.py` (E1) | 16 / 19 / 10 passed |
| `… tests/test_gl_gpu_picking.py` / `test_gl_morph_picking.py` (E15) | 37 / 16 passed |
| `… tests/test_gui_imgui_window.py` / `test_gui_lookdev_window.py` | 18 / 1 passed |
| `xvfb-run -a python -m pytest tests -q` | 7,938 passed, 8 skipped, 1 failed: `test_scene_menu_local_tmp.py::test_probe_menu_wiring` - **pre-existing** (fails identically before S1, §16.3) |
| `xvfb-run -a python -m pytest experiments/morph_lab/tests -q` | 49 passed |
| `xvfb-run -a python -m pytest experiments/drag_cost/tests -q` | 104 passed |
| `xvfb-run -a python -m pytest experiments/lookdev_eye_lab/tests -q` | 206 passed (the frozen oracle) |

Not run: `experiments/knife_oracle/tests` (no Knife or topology code touched).

### 17.4 Measurement

Container (llvmpipe, a function check only): `python experiments/drag_cost/probe_lookdev_room.py --draws 3` ran every
row (`lookdev`, `lookdev +shadow`, `lookdev +shadow +eyes`, the three drag rows) with `glGetError` 0; `KeyShadow.renders`
0 in the still rows, 8 of 8 in the drag rows; the cage entry compiled 2 programs behind the status line (the skin and
the LD_SHADOW eye). Its ms are a CPU rasteriser's (one still row read 24 ms at SubD 1 in this run, the next 0.9 ms) and
say nothing about the reference PC.

**Reference PC (E16, S1's open drag decision and S2):** NVIDIA "Maximale Leistung bevorzugen", repository root,
`.venv312`:

```
python experiments\drag_cost\probe_lookdev_room.py | Tee-Object -FilePath lookdev_room_s2.txt
python experiments\drag_cost\probe_lookdev.py --no-extras | Tee-Object -FilePath lookdev_ld0_after_s2.txt
python experiments\drag_cost\probe_d3_acceptance.py | Tee-Object -FilePath d3_after_s2.txt
```

What the run decides:
- `lookdev +shadow +eyes` against `lookdev +shadow`: S2's target ≤ +0.5 ms (§2.5). Missed → the levers of §2.5.
- Everything S1's run decides (§16.4): `lookdev +shadow` against `lookdev` (≤ +2 ms; the row is skin and teeth only,
  as S1 built it), the drag rows (plain / flush / ping-pong, the default in `KeyShadow`), E16 (`modelling` /
  `modelling after`, `probe_lookdev.py --no-extras`, `probe_d3_acceptance.py` within noise of the last runs).
- If S1's run is done already, only the first command is new for S2; the other two confirm E16 after S2.

### 17.5 Practical test S2 (`scenes/Gollum_Head_05.mirai.json`, about 15 minutes; together with S1's §16.5)

Open LookDev, SubD 1, view „¾“ and front; zoom close to one eye for points 1–4.
1. **Lid-Schatten in Portrait und Dramatic:** Erwartet: Oberlid (und am äußeren Winkel breiter) und der Rand des
   Unterlids legen einen schmalen Schatten auf den Augapfel; die Iris unter dem Lidrand wird mit dunkel. Bei diesen
   Key-Höhen (30° / 20°) ist der Schatten schmal – das ist die Geometrie (CPU-Strahltest, §17.3). Liest er sich als
   Kontaktschatten oder als Rand / Linie? Zu hart, zu weich, zu dunkel?
2. **Blickrichtung ändern** (Panel „Auge“, das Blick-Feld: links / rechts / oben / unten): Erwartet: der Schatten bleibt am Lid, er
   wandert nicht mit der Iris; die Iris taucht beim Blick nach oben in den Lidschatten. Sieht die Iris-Kante im Schatten
   versetzt aus (die benannte Näherung: der Schatten wird an der Hornhaut-Oberfläche gelesen, die Iris liegt dahinter)?
3. **Key drehen:** in „Licht“ den Key in Höhe (z. B. 30° → 60°) und Richtung drehen. Erwartet: höherer Key → breiterer
   Oberlid-Schatten; Brauen und Nase werfen ihn auf das ferne Auge, wenn der Key von der Seite kommt. Springt oder
   flackert er beim Drehen, besonders auf der Hornhaut?
4. **„Weichheit“ des Key** (0 → 1, „Mehr“, Zeile **Key**): Erwartet: die Kante auf dem Auge wird mit der auf der Haut
   gleich weich; bei sehr weichem Key verblasst der schmale Lidschatten fast ganz (wie feine Falten in S1).
5. **„Augen-Schatten“ an / aus** (Block „Effekte“): aus = genau das Auge von vorher; „Schatten“ aus → „Augen-Schatten“
   wird grau („braucht Schatten“). Wird der Augen-Schatten nach dem Speichern und Laden so wiederhergestellt?
6. **`EyeLook.lid_shadow` (Q-P3-6):** im Panel „Auge“ die Lid-Abdunklung vergleichen (aktueller Wert, dann 0). Wirkt sie
   mit dem echten Lidschatten jetzt zu stark (doppelt dunkel unter dem Lid)? Wenn ja: welcher Wert fühlt sich richtig an?
   Eine Code-Änderung folgt nur auf dein Wort.
7. **Front, Portrait, nah am Auge zur Nase hin:** eine sehr schwache Abdunklung der unteren inneren Sklera über den
   geometrischen Halbschatten hinaus (≤ 8/255, §17.3). Siehst du sie, und stört sie?

Assumptions to correct in one sentence: the eye shadow is on by default; it needs the skin shadow; the eyes still cast
no shadow (Q-P3-5); `EyeLook.lid_shadow` is unchanged.

---

## 18. Implementation note — S3 built (2026-11-23)

**Kurzfassung (Deutsch):** Der Glanz der Haut aus den drei Lichtern (Key, Fill, Rim) besteht jetzt aus zwei Anteilen:
85 % bei Rauheit × 0,75 (eine schärfere Spitze) und 15 % bei × 1,3 (ein weicher Saum), mit deinen freigegebenen Werten
(Q-P3-7, fest). Die Studio-Spiegelung bleibt einfach, bis der Cube kommt (P3-0 Lauf 2: ein zweiter Anteil auf dem
analytischen Studio kostet +0,9 bis +4 ms). Neuer Schalter „Doppel-Glanz“ im Block „Effekte“ (Standard an, braucht
nichts), mit der Szene gespeichert; eine S2-Datei behält ihre Einstellungen. Doppel-Glanz aus = S1/S2, Zeichen für
Zeichen (Pins). Die Augen bleiben unverändert. **Abweichung:** Die AD versprach „gleiche Energie wie ein Lobe, ±2 %“.
Das stimmt mit diesen Werten nur bis Rauheit 0,4; darüber reflektiert der Doppel-Glanz mehr (bei Creature Skin 0,5 etwa
+3 bis +6 %, bei Neutral 0,6 etwa +8 bis +10 %), weil der schärfere Hauptanteil weniger durch Selbstabschattung verliert.
Er erzeugt keine Energie (≤ 1). Am Gollum-Kopf werden die Glanzlichter dadurch sichtbar heller (bis +24 bis +36/255 im
Spitzenwert). Dein Praxistest entscheidet, ob das so bleibt (§18.5).

### 18.1 What is built

| Layer | Built |
|---|---|
| Effects | `LookdevEffects.dual_lobe` (default on, the third field), no `EFFECT_FEATURE` and no `EFFECT_NEEDS` entry (it needs neither a feature nor another effect), `EFFECT_LABEL` „Doppel-Glanz“; `view.lookdev.effects` reads it optionally (S1's reader: an S2 file without `dual_lobe` keeps the current switch) |
| Shaders | `lookdev_shaders.DUAL_LOBE_SCALES = (0.75, 1.3)`, `DUAL_LOBE_MIX = 0.85` (`PROVISIONAL`, Q-P3-7 fixed); `LD_DUAL_LOBE_SRC` (`ld_direct_dual`: `mix(broad, sharp, 0.85)`, each lobe `direct_specular` at `ld_lobe(roughness × scale, size)`; `ld_specular_dual`: the three lights), appended after `LD_COMMON_SRC` only with the effect; `SKIN_EFFECTS = ("SHADOW", "DUAL_LOBE")`; `skin_sources(..., shadow=False, dual_lobe=False)` resolves every effect that is off with `_without` |
| Body blocks (2) | `#ifdef DUAL_LOBE … #else … #endif` around the `colour` line (`ld_specular_dual` / `ld_specular`) and, nested inside the `SHADOW` block, around the key's subtracted term (`ld_direct_dual` / `direct_specular`), so the key's shadow takes away exactly the highlight it drew. The `#else` parts are the S1 text, character for character. `ENV_SPEC` is untouched: the studio's reflection keeps one lobe |
| Pass | `LookdevPass.program(albedo_map, env_spec, shadow=False, dual_lobe=False)`: the key is 4 values `(ALBEDO_MAP, ENV_SPEC, SHADOW, DUAL_LOBE)` (§2.3 point 4's fixed order); `draw(..., shadow=None, dual_lobe=False)` |
| Viewport | `_lookdev_programs` adds `effects.dual_lobe` to every skin variant (so `prepare_lookdev` compiles it behind the status line and `lookdev_prepare_needed` sees a switch); `_render_lookdev` hands it to every skin draw. Eyes and Worklight untouched |
| Twins | `lookdev_optics.ld_direct_dual`, `ld_specular_dual`; `ld_key_shadowed(..., dual=False)` for the `SHADOW` block with `DUAL_LOBE` |
| GUI | `lookdev_model.EFFECT_LABELS` / `EFFECT_HINTS`: the row „Doppel-Glanz“ |
| Probe | `probe_lookdev_room.py`: `EFFECT_ROWS["dual_lobe"] = ("lookdev +dual", ("dual_lobe",))`, the dual lobe alone against `lookdev` (every effect off) |

Not touched: `src/core/`, `serialization.py`, `LD_COMMON_SRC` (the eye's LOOKDEV pin), `LD_SHADOW_SRC`, `eye_shaders.py`,
`eye_pass.py`, `KeyShadow`, `main.py`, `config/keymap.json` (no keys), `LookMaterial` (no per-material values, Q-P3-7).

### 18.2 Where the build differs from §2 / §6, and why

| # | AD | Built | Why |
|---|---|---|---|
| S3-1 | §6 test "the mix of the two normalised lobes integrates to the single lobe's albedo within 2 % for r ∈ [0.2, 0.8]" | `test_the_dual_lobe_keeps_energy`: each lobe's NDF is normalised (∫ D cos θ dω = 1 within 2 %); the mix's directional albedo (F0 = 1) is ≤ 1 and ≥ the single lobe's (− 0.01); within 5 % of it for r ≤ 0.4 | the claim is false for the accepted values. Measured (F0 = 1, light size 0, the single lobe's albedo → the mix's): see the table below. Single-scatter GGX loses energy to Smith masking as the roughness grows; the mix's main lobe is sharper (× 0.75), so it loses less. The mix stays energy-conserving; against the single lobe it is brighter |
| S3-2 | §6 "`LD_SKIN_SRC` gets `ld_specular_dual`" | a separate string `LD_DUAL_LOBE_SRC`, appended only with the effect | there is no `LD_SKIN_SRC`; the code's pattern is one library string per effect (`LD_SHADOW_SRC`, §2.3 point 2), and an appended string keeps every effect-off source pinned |
| S3-3 | §6 (not stated) | the `SHADOW` block subtracts the key's **dual** highlight when both are on | otherwise the key's shadow would leave the difference between the two highlights behind in the shadow (light where the key is blocked) |
| S3-4 | §14 / E7 (grey card skin = sclera, `test_gl_lookdev_pass.py`) | E7 runs with every P3 effect off (it set none before and so ran with the defaults, the shadow on) | E7 checks that both passes share the M1 BRDF; the dual lobe is the skin's own (the eye keeps one lobe), so with it on the two differ on purpose |

The energy, measured (`_directional_albedo`, 600 × 600 directions; cos θ_v = 1 / 0.7 / 0.35):

| r | single → dual, cos θ_v = 1 | 0.7 | 0.35 |
|---|---|---|---|
| 0.2 | 0.999 → 0.999 (+0.1 %) | +0.1 % | −0.6 % |
| 0.4 | 0.968 → 0.977 (+1.0 %) | +1.8 % | +4.6 % |
| 0.5 | 0.916 → 0.944 (+3.1 %) | +4.9 % | +5.9 % |
| 0.6 | 0.825 → 0.892 (+8.2 %) | +10.0 % | +6.3 % |
| 0.8 | 0.555 → 0.747 (+34.5 %) | +26.1 % | +11.5 % |

The presets: Wet Skin 0.25, Zähne and Mundinneres 0.3 (≤ 2 %), Creature Skin 0.5, Organisch 0.55, Neutral 0.6. A light's
size widens both lobes (`ld_lobe`), which moves a soft key's effective roughness up the table. If the practical test
finds the highlights too strong, the options are: lower `DUAL_LOBE_MIX`'s sharp share, or normalise the mix to the single
lobe's albedo (a fitted factor per roughness, a code constant). Either is a one-place change and Manu's call.

### 18.3 Tests (container, llvmpipe, 2026-11-23)

| # | Test |
|---|---|
| sources | `test_lookdev_shaders.py`: `test_the_dual_lobe_off_keeps_m1_and_s1_sources` (the M1 pin unchanged; new `PINNED_S1_SKIN_SOURCES_SHA256` over the 4 S1 variants, taken from `f8c771f` before the change: `shadow=True` and `shadow=True, dual_lobe=False` both equal it); `test_the_dual_lobe_variant_calls_the_dual_twins_for_the_lights_and_the_shadowed_key` (define and library once, the library after `LD_COMMON_SRC`, the key's shadowed term dual, the studio one lobe, nothing dual left with the effect off) |
| twins | `test_lookdev_optics.py`: `test_ld_specular_dual_is_the_mix_of_two_widened_lobes` (the mix per light, the sum, `ld_key_shadowed(..., dual=True)` at visibility 1 and 0); `test_the_dual_lobe_keeps_energy` (S3-1, r = 0.2 / 0.4 / 0.6 / 0.8) |
| GPU parity | `test_gl_lookdev_parity.py::test_dual_lobe`: `ld_direct_dual` (random light sizes) and `ld_specular_dual` against the twins, 2,048 inputs, within 10⁻³ relative |
| block | `test_gl_lookdev_shadow.py::test_the_shadow_block_matches_ld_key_shadowed[True]`: the plane in full shadow and in the light equals `lookdev_output(ld_key_shadowed(..., dual=True))` (≤ 2.5/255); `[False]` is S1's test with the dual lobe off |
| off = S1 | `test_the_dual_lobe_off_draws_s1_and_on_changes_the_highlight`: with the shadow on and the dual lobe off, the program built by S1's call (`skin_sources(…, shadow)`) draws the same pixels; on a glossy sphere the dual lobe changes > 50 px |
| GL state | the defaults now include the dual lobe, so S1's `test_a_frame_that_renders_the_map_leaves_the_gl_state_as_found` and S2's state tests run with it on |
| headless | `test_lookdev_persistence.py` (`test_an_s2_file_without_dual_lobe_keeps_its_settings`; the round trip writes three names), `test_lookdev_room.py` (view state, no Undo, no reason), `test_gui_lookdev_model.py` (the row, available with the shadow off), `experiments/drag_cost/tests/test_probe_lookdev_room.py` (`lookdev +dual`) |

**Gollum (one-off, not committed):** `Gollum_Head_05`, 1024 × 768, the framed ¾ view and the face, cage and SubD 1,
shadow and eye shadow on; dual lobe on against off:

| Preset, material | changed > 2/255 (framed / face) | brighter / darker (face, SubD 1) | max (face, cage / SubD 1) |
|---|---|---|---|
| Portrait, Neutral (0.6) | 435–579 / 3,037–3,417 px | 3,024 / 13 | +25 / +26, −5 / −3 |
| Portrait, Creature Skin (0.5) | 322–430 / 1,856–1,987 px | 1,849 / 0 | +21 / +23, −3 / −3 |
| Dramatic, Creature Skin | 1,378–1,566 / 11,227–11,472 px | 10,012 / 187 | +36 / +34, −5 / −5 |

The change sits in the highlights (bridge of the nose, cheekbones, brow, lips); the eyes are unchanged. The few darker
pixels are the broader lobe's lower peak where a highlight was already at its edge. Not done this time: an S2-code
against S3-code (dual off) pixel comparison on the head, as §17.3 did; the source pins (M1, S1) and the GL test cover it.

Runs (GL files each in their own process under xvfb):

| Command | Result |
|---|---|
| `xvfb-run -a python -m pytest tests/test_lookdev_shaders.py tests/test_lookdev_optics.py -q` | 29 passed |
| `… tests/test_gl_lookdev_shadow.py` / `test_gl_lookdev_pass.py` / `test_gl_lookdev_parity.py` | 20 / 13 / 8 passed |
| `… tests/test_gl_eye_pass.py` | 135 passed (unchanged; the eye pins green) |
| `xvfb-run -a python -m pytest tests -k "lookdev or look or view_state or main_wiring" -q` | 408 passed |
| `xvfb-run -a python -m pytest experiments/drag_cost/tests -q` | 105 passed |

### 18.4 Measurement

Container (llvmpipe, a function check only): `probe_lookdev_room.py --effects dual_lobe --draws 5 --surfaces cage`
ran `lookdev` and `lookdev +dual` with `glGetError` 0; the entry compiled 2 programs behind the status line. Its ms say
nothing about the reference PC.

**Reference PC (S3, together with S1's and S2's open run):** NVIDIA "Maximale Leistung bevorzugen", repository root,
`.venv312`:

```
python experiments\drag_cost\probe_lookdev_room.py | Tee-Object -FilePath lookdev_room_s3.txt
```

It measures every built row in one run (`lookdev`, `lookdev +shadow`, `lookdev +shadow +eyes`, `lookdev +dual`, the
drag rows). What it decides for S3: `lookdev +dual` against `lookdev` ≤ +0.5 ms (§2.5; P3-0 run 2's stand-in measured
+0.06 to +0.29 ms). E16 and S1's / S2's decisions as §17.4 (the other two commands there).

### 18.5 Practical test S3 (`scenes/Gollum_Head_05.mirai.json`, about 10 minutes; with S1 / S2's if still open)

Open LookDev, SubD 1, view „¾“, then the face from the front.
1. **„Doppel-Glanz“ an / aus** (Block „Effekte“), mit Portrait und Material Creature Skin, dann Neutral: Erwartet: an =
   die Glanzlichter auf Nasenrücken, Wangenknochen, Stirn und Lippen haben einen helleren, schärferen Kern und einen
   weichen Saum; aus = genau das Bild von vorher. Wirkt die Haut lebendiger oder eher feucht / speckig?
2. **Dramatic:** derselbe Vergleich; hier ändert sich am meisten. Sind die Glanzlichter zu hell? Wenn ja, sag, ob die
   Spitze schwächer (weniger scharfer Anteil) oder der Glanz insgesamt gedämpft werden soll (§18.2: auf die Helligkeit
   eines Lobes normiert).
3. **„Weichheit“ des Key** (0 → 1): Erwartet: beide Anteile werden weicher, der Kern bleibt etwas schärfer als ohne
   Doppel-Glanz.
4. **Zähne, Mundinneres, Wet Skin:** Erwartet: kaum Unterschied (niedrige Rauheit), der Glanz bleibt scharf.
5. **Speichern und Laden:** der Schalter kommt so zurück, wie er war.

Assumptions to correct in one sentence: the dual lobe is on by default; it needs nothing; the studio's reflection keeps
one lobe until S5; the values are fixed (not per material).

---

## 19. Implementation note — S4 built (2026-11-23)

**Kurzfassung (Deutsch):** Der Key scheint jetzt durch dünne Stellen: Die Haut liest die Schattenkarte des Key ein
zweites Mal als rohe Tiefe und weiß damit, wie weit das Licht im Mesh bis zu diesem Punkt gelaufen ist. Der Anteil, der
durchkommt, ist `exp(−Dicke / 0,05)`, mal Backscatter, Backscatter-Farbe, Albedo und Key-Farbe des Materials, nur auf
der vom Key abgewandten Seite. Ein dünnes Ohr oder ein Nasenflügel vor einem Key von hinten leuchtet, der dicke Kopf
nicht. Der Rand-Schimmer aus M1 (der Ersatz ohne Dicke) fällt dafür weg, wie die AD es vorsah; auf der Schattenseite
des Kopfes wird es dadurch etwas weniger rosa. Neuer Schalter „Durchleuchtung“ (Standard an, braucht „Schatten“ und
Sampler-Objekte). Durchleuchtung aus = S3, Zeichen für Zeichen. **Einheit:** Die AD rechnete mit „0,6 cm“ und 1
Einheit = 1 cm (AD-033). `Gollum_Head_05` ist aber 1,2 Einheiten breit (ein Kopf von etwa 15 cm). Der Wert ist deshalb
in Welteinheiten gesetzt: 0,05, also 0,6 cm bei dieser Kopfgröße. Eine Szene im 1-cm-Maßstab bräuchte etwa 0,6.
Offene Frage an dich (§19.2, S4-1).

### 19.1 What is built

| Layer | Built |
|---|---|
| Effects | `LookdevEffects.thickness` (default on, the fourth field); `EFFECT_FEATURE["thickness"] = "sampler_objects"`, `EFFECT_NEEDS["thickness"] = "shadow"` (reasons „Sampler-Objekte fehlen“ / „braucht Schatten“); `EFFECT_LABEL` „Durchleuchtung“; `view.lookdev.effects` reads it optionally (an S3 file keeps its settings) |
| Features | `lookdev_features.FeatureReport.sampler_objects`, `_sampler_objects()` (`glGenSamplers` gives a name, a parameter set, deleted, `glGetError` 0); status line „LookDev: Durchleuchtung aus – Sampler-Objekte nicht verfügbar“ |
| Shaders | `lookdev_shaders.SHADOW_RAW_UNIT = 7`, `THICKNESS_SCALE = 0.05` (`PROVISIONAL`, world units); `LD_THICKNESS_SRC` (`u_ld_shadow_depth`, `u_ld_shadow_range`; `ld_key_thickness(p, n, l)`: at `ld_shadow_coord`'s map point, `max(z − stored, 0) × range`, −1 outside the map; `ld_key_transmission`: `exp(−t / scale)`, 0 outside), appended after `LD_SHADOW_SRC` only with the effect; `SKIN_EFFECTS = (SHADOW, DUAL_LOBE, THICKNESS)`; `skin_sources(..., thickness=False)` refuses `thickness` without `shadow` |
| Body block (1) | `#ifdef THICKNESS … #else … #endif` around the backscatter's `back`: `ld_key_transmission(v_world_pos, n, l_key) × max(−n·l_key, 0)` in place of M1's `(1 − n·v)³ × max(−n·l_key, 0)`; the `#else` part is M1's line |
| Map | `KeyShadow.bind_raw(unit)` / `unbind_raw(unit)`: the current map on unit 7 through a sampler object (GL_LINEAR, CLAMP_TO_EDGE, compare mode NONE; created on first use, deleted in `release()`); `uniforms()` adds `u_ld_shadow_depth = 7` and `u_ld_shadow_range = 2 × the frustum radius` (the map's depth [0, 1] spans the orthographic box's 2 r) |
| Pass | program key 5 values `(ALBEDO_MAP, ENV_SPEC, SHADOW, DUAL_LOBE, THICKNESS)`, `THICKNESS` only with `SHADOW`; `draw(..., thickness=False)` binds the raw map on unit 7 with the shadow on 6 and unbinds texture and sampler after the draw; a frame whose map is not ready draws without both |
| Viewport | `_lookdev_programs` adds `effects.thickness` to the skin key (so `prepare_lookdev` compiles it behind the status line); `_render_lookdev` hands it to every skin draw. Eyes untouched |
| Twins | `lookdev_optics.bilinear_depth` (a raw GL_LINEAR / CLAMP_TO_EDGE fetch), `key_transmission(depth, sp, range, scale)`, `ld_backscatter(albedo, n, v, values, backscatter, colour, transmission=None)` (the proxy without `transmission`) |
| GUI | `lookdev_model`: the row „Durchleuchtung“ with its hint |
| Probe | `probe_lookdev_room.py`: `EFFECT_ROWS["thickness"] = ("lookdev +shadow +thick", ("shadow", "thickness"))` against `lookdev +shadow` |

Not touched: `src/core/`, `serialization.py`, `LD_COMMON_SRC`, `LD_SHADOW_SRC`, the depth pass and its program,
`eye_shaders.py`, `eye_pass.py`, `main.py`, `config/keymap.json`, `LookMaterial` (the backscatter values are the
materials' own, V7).

### 19.2 Where the build differs from §2 / §7, and why

| # | AD | Built | Why |
|---|---|---|---|
| S4-1 | §7 "the scale is 0.6 cm" | `THICKNESS_SCALE = 0.05` world units | the AD assumed 1 unit = 1 cm (AD-033 Q-E6). `Gollum_Head_05` does not follow it: its head's bounding radius is 0.60 units (1.2 across; the eyes ≈ 0.1 radius, §17.3), about 12 cm per unit for a ~15 cm head. 0.05 is 0.6 cm at that head's size. **[O] for Manu:** which unit should LookDev assume - the scene as it is (this value), or the 1 cm convention (then 0.6, and Gollum should be scaled up)? A per-material value would be a `LookMaterial` field (a format version) and is not built |
| S4-2 | §7 "a sampler object without compare mode" | GL_LINEAR, CLAMP_TO_EDGE | the P3-0 stand-in used GL_NEAREST; a linear raw fetch gives a smooth thickness across the map's texels at the same cost (one fetch). CLAMP_TO_EDGE because outside the map is masked in the shader (the texture's own border depth 1.0 would read as "no path" = full light) |
| S4-3 | §7 "outside the map it reads as no light passing" | built so (`inside` mask) | as the AD; named here because the border's depth alone would give the opposite |
| S4-4 | (not stated) | the GL test's boxes are built from six separate quads (`_flat_box`) | `_box` shares its 8 corners, so its vertex normals bend toward the corners and the face-on transmission read 0.45 instead of 0.67: a test-geometry effect, not the shader (found while building, §19.3) |

**What changes in the picture (Gollum, key from behind at 160° / 15°, Creature Skin, SubD 1):** with the thickness on,
21,000–34,000 px change by more than 2/255 (scale 0.02 / 0.05 / 0.1), between +24 and −26/255. The plus is the
light through thin parts (ears, the neck's open rim); the minus is M1's view-rim proxy that no longer glows on the thick
head's shadowed side. With Creature Skin's backscatter 0.15 the ears' gain is subtle; Mundinneres has 0.3, Neutral
and Organisch have none (the effect does nothing there).

**Limits, named (§7):** the thickness is along the key only, from the map's nearest surface - a fold in front of a thin
part reads thick, and an ear behind the head (relative to the key) gets the head's thickness plus the air between.
Outside the map no light passes.

### 19.3 Tests (container, llvmpipe, 2026-11-23)

| # | Test |
|---|---|
| sources | `test_lookdev_shaders.py`: `test_the_thickness_off_keeps_the_m1_s1_and_s3_sources` (new `PINNED_S3_SKIN_SOURCES_SHA256` over the 4 `shadow + dual_lobe` variants, taken from `eadb291` before the change; M1 and S1 pins unchanged); `test_the_thickness_variant_replaces_the_rim_proxy_and_needs_the_shadow` (define and library once, after `LD_SHADOW_SRC`; refused without the shadow; nothing left with it off) |
| twins | `test_lookdev_optics.py`: `test_bilinear_depth_reads_texel_centres_and_blends_between_them`, `test_key_transmission_falls_with_the_path_inside_the_mesh` (exp(−t/s), in front = 1, outside = 0, the rendered part), `test_ld_backscatter_proxy_and_transmission`; the dependency and feature reasons in `test_effects_default_on_and_dependencies_and_features` |
| GPU parity | `test_gl_lookdev_shadow.py::test_ld_key_transmission_matches_key_transmission[1.0 / 0.5]`: a smooth 64² map as the compare texture, read raw on unit 7 through `KeyShadow`'s sampler object (the production binding), 4,096 points against the twin (max ≤ 0.03, mean ≤ 0.003; values strictly between 0 and 1 prove the compare mode is off; outside = 0) |
| T4-1 | `test_the_thickness_lets_a_thin_slab_through_and_not_a_thick_block`: the key straight behind a 0.02 slab and a 0.8 block - the slab's face equals `lookdev_output(ld_backscatter(…, exp(−0.02 / scale)))`, the block's 0 (≤ 2.5/255); with the thickness off both show the proxy (0 face-on) |
| T4-2 | `test_the_thickness_off_draws_s3_and_binds_nothing_on_unit_7`: the program built by S3's call draws the same pixels; the key in front changes nothing; unit 7 has neither texture nor sampler after the frame |
| T4-3 | `test_without_sampler_objects_the_thickness_is_off_with_a_status_line`: the stub - the frame equals the thickness-off frame, the shadow stays, the status line once |
| GL state | S1's `test_a_frame_that_renders_the_map_leaves_the_gl_state_as_found` now runs with the thickness on (its state snapshot covers units 0–7 with the sampler binding) |
| headless | persistence (`test_an_s3_file_without_thickness_keeps_its_settings`; the round trip writes four names), room (reasons), panel model (the row, greyed „braucht Schatten“), `test_probe_lookdev_room.py` (`lookdev +shadow +thick`) |

Runs (GL files each in their own process under xvfb):

| Command | Result |
|---|---|
| `xvfb-run -a python -m pytest tests/test_gl_lookdev_shadow.py -q` | 25 passed |
| `… tests/test_gl_lookdev_pass.py` / `test_gl_lookdev_parity.py` / `test_gl_eye_pass.py` | 13 / 8 / 135 passed |
| `xvfb-run -a python -m pytest tests -k "lookdev or look or view_state or main_wiring" -q` | 419 passed |
| `xvfb-run -a python -m pytest tests -q` (at `e2b2ba4`, S3 + S4) | 7,960 passed, 8 skipped, 1 failed: `test_scene_menu_local_tmp.py::test_probe_menu_wiring` - **pre-existing** (fails identically before S1, §16.3) |

### 19.4 Measurement

Container (llvmpipe, a function check only): `probe_lookdev_room.py --effects shadow,thickness --draws 3 --surfaces
cage` ran `lookdev`, `lookdev +shadow`, `lookdev +shadow +thick` and the drag rows with `glGetError` 0.

**Reference PC (S4, with S1–S3's open run):** the same single command as §18.4 (`probe_lookdev_room.py`, every built row).
What it decides for S4: `lookdev +shadow +thick` against `lookdev +shadow` ≤ +0.5 ms (§2.5; P3-0's `thick 1k x9`
measured +0.50 against +1.11 for the shadow alone).

### 19.5 Practical test S4 (`scenes/Gollum_Head_05.mirai.json`, about 10 minutes)

Open LookDev, SubD 1, material **Creature Skin** (or **Mundinneres** for a stronger effect), view „¾“ and from the side.
1. **Key von hinten:** in „Licht“ den Key auf Richtung ~160° und Höhe ~15° drehen. Erwartet: die Ohren (und der
   Halsrand) leuchten warm durch, der Kopf selbst nicht. Zu stark, zu schwach, falsche Stelle?
2. **„Durchleuchtung“ an / aus:** aus = das Bild von vorher. Erwartet: an verschwindet der schwache rosa Rand-Schimmer
   auf der Schattenseite des Kopfes (der Ersatz aus M1); fehlt er dir?
3. **Nasenflügel:** Key seitlich-hinten (z. B. 120°, 0°), Blick auf die Nase von vorn: leuchten die Nasenflügel durch?
4. **Key drehen und „Weichheit“:** flackert oder springt das Durchscheinen? (Die Karte wird nur bei einer Änderung neu
   gerechnet.)
5. **Die Einheit (S4-1):** wirkt die Dicke, durch die Licht kommt, für Gollums Kopfgröße plausibel?

Assumptions to correct in one sentence: the thickness is on by default; it needs the shadow; it only changes materials
with a backscatter; the value is in this scene's world units (0.05).

---

## 20. Implementation note — S7 built (2026-11-24)

**Decision:** Manu, 2026-11-24, on Q-P3-2: „Map-Pfade“ (the recommendation of §10), and on the order: „S7 jetzt
vorziehen“ (before S5 / S6; S7 takes v16, S6 v17). This is the paint channel decision and the go for the Core field
(§12 point 5); the CORE_V1_FREEZE §7.1 entry is in this commit.

**Kurzfassung (Deutsch):** Ein LookDev-Material kann jetzt drei Bild-Maps tragen, als Pfad am Material (ZBrush oder
extern gemalt), in den UVs des Objekts: **Rauheit** (grau, mal der Rauheit des Materials; weiß = unverändert),
**Normal** (Tangentenraum, OpenGL „Grün oben“; „Grün unten (DirectX)“ und „Normal-Stärke“ 0–2 im Panel) und
**Durchscheinen** (grau, mal dem Durchscheinen: mit „Durchleuchtung“ die Dicke aus S4, ohne sie M1s Rand-Schimmer).
Laden / Entfernen im Panel unter „Mehr“ im Block Material, je ein Undo-Schritt; eine Vorlage behält die Maps,
„Zurücksetzen“ entfernt sie mit dem Material. Beim Speichern werden die Bilder nach `<Szene>_textures/` kopiert und
relativ gespeichert (Szenenformat **v16**, nur mit Maps; sonst bleibt die Datei wie vorher). Neuer Effekt-Schalter
„Maps“ (Standard an). Ohne Map = S4, Zeichen für Zeichen. Die Normal-Map braucht keinen Tangenten-Puffer: der Rahmen
kommt aus den Bildschirm-Ableitungen von Position und UV, je Dreieck. Bilder: PNG, JPEG, BMP bis 4096².

### 20.1 What is built

| Layer | Built |
|---|---|
| Core | `core.LookMaps(roughness, normal, translucency, normal_strength=1.0, normal_green_down=False)` (frozen; each map a non-empty path or None, at least one; strength in [0, 2]); `LookMaterial.maps: LookMaps \| None = None` (absent in the dict = none, the `EyeLook.iris` pattern); `LOOK_MAP_FIELDS`, `LOOK_NORMAL_STRENGTH_MAX`; `serialization.LOOK_MAPS_FORMAT_VERSION = 16` by content, reads 2–16, a `"maps"` key below 16 refuses the file; CORE_V1_FREEZE §7.1 entry |
| App | `mirai/look_maps.py` (the size policy from the file header: PNG / JPEG / BMP up to `MAX_SIZE` 4096, a hint above 2048; `drawable`, `status_text`); `lookdev_material.with_map`, `keep_maps`, `MAP_VALUES` through `with_values` (never „angepasst“); `Application.set_lookdev_map(kind, path)` (one Undo step on the material targets, refused with the reason; a target without a look gets Neutral with the map; a target without UVs keeps it, the status line says it is not drawn); `set_lookdev_material` keeps the maps; `set_lookdev_material_values(normal_strength=…, normal_green_down=…)`; load resolves the paths against the scene, save copies them into `<stem>_textures/` (`_copy_look_maps`, the AD-035 S-10 rule: content name, never overwrites, never deletes, a missing image keeps its path) and writes them scene-relative; `LookdevRoom.look_draw` hands the drawable maps on an object with UVs |
| Effects / features | `LookdevEffects.maps` (default on, the fifth field), `EFFECT_FEATURE["maps"] = "texture_units"`; `FeatureReport.texture_units` (`GL_MAX_TEXTURE_IMAGE_UNITS` ≥ 12), status line „LookDev: Maps aus – zu wenige Textureinheiten“; the check runs only when a drawn LookDraw has a map (`Viewport._lookdev_maps`) |
| Shaders | `MAP_UNITS` 9 / 10 / 11, `SKIN_MAPS`, `NORMAL_MAP_ZERO = 128/255`; defines `ROUGHNESS_MAP`, `NORMAL_MAP`, `TRANSLUCENCY_MAP`, and `LD_MAP_UV` with any of them; `LD_NORMAL_MAP_SRC` (`ld_normal_tangent`, `ld_cotangent_frame`, `ld_normal_mapped`) appended only with the normal map; `skin_sources(..., roughness_map, normal_map, translucency_map)` |
| Body blocks | `LD_MAP_UV`: the triangle UVs (declared under `#ifndef ALBEDO_MAP` when the albedo has not) read in uniform control flow, `map_on` 0 on a triangle without UVs; `NORMAL_MAP`: `n_geo = n`, then `n` tilted (only where `map_on`); `ROUGHNESS_MAP`: `alpha = u_roughness × map` before the specular AA; `TRANSLUCENCY_MAP`: `back ×= map`; inside `SHADOW` and `THICKNESS`, a nested `NORMAL_MAP` block gives the key map's lookups `n_geo` (the `#else` lines are S4's) |
| Pass | `LookDraw` gains `roughness_map`, `normal_map`, `translucency_map`, `normal_strength`, `normal_green_down`, `map_paths()`, `needs_uvs`, `map_uniforms()`; `LookdevPass.program_key` = S4's 5 values, plus the three map flags only when a map is drawn; `draw(..., maps=False)` binds the triangle UVs even without an albedo map, each loadable map through `GLRenderStore.texture` (mipmapped, repeating) on its unit, unbinds them after the draw |
| Viewport | the UV request follows `LookDraw.needs_uvs`; `_lookdev_programs` adds the map flags for a mesh with UVs (so `prepare_lookdev` compiles them behind the status line); `_render_lookdev` hands `effects.maps` to every skin draw. Eyes untouched |
| Twins | `lookdev_optics.normal_map_tangent`, `cotangent_frame`, `ld_normal_mapped`, `map_roughness` |
| GUI | `lookdev_model`: the effect row „Maps“, `MapRow`s, `load_map`; `lookdev_panel.draw_maps` under „Mehr“ in the material block: per map its file (or why it is not drawn), „Laden …“ (the file browser), „Entfernen“; for the normal map „Normal-Stärke“ (held = preview, release = one step) and „Grün unten (DirectX)“ |
| Probe | `probe_lookdev_room.py`: `EFFECT_ROWS["maps"] = ("lookdev +maps", ("maps",))` against `lookdev`, with three generated 2048² maps (`probe_map_images`; a temporary folder, set in memory) |

Not touched: `LD_COMMON_SRC`, `LD_SHADOW_SRC`, `LD_THICKNESS_SRC`, the depth pass, `eye_shaders.py`, `eye_pass.py`,
`main.py`, `config/keymap.json`, `Mesh`, `ObjectMaterial`, the presets' values.

### 20.2 Where the build differs from §2 / §10, and why

| # | AD | Built | Why |
|---|---|---|---|
| S7-1 | §10 "a 2 × 2 pixel quad across a UV seam gets a wrong frame on the seam's pixels [E]" | no seam error; the frame is constant per triangle | a fragment quad never spans two triangles (GL rasterises quads per primitive, helper pixels extrapolate), so the derivatives of position and UV are the triangle's own. The limit is the other way round: the tangent is per triangle (orthogonalised against the smooth normal), so on a coarse mesh with a strong map a faint facet line can show along a triangle edge where the UV's direction turns. The seam test image is replaced by the GPU parity of the frame and the half-UV plane (§20.3) |
| S7-2 | §2.3 one define per effect | plus `LD_MAP_UV` | the three maps share one UV read; a fourth define keeps "an effect off leaves no text" true for each map |
| S7-3 | §2.3 point 4 the key "depends on the object (whether it has maps)" | 5 values without a map, 8 with one | the S2-1 pattern: every key and test before S7 stays as it was |
| S7-4 | (not stated) | with a normal map the shadow's and the thickness's lookups use the geometric normal | the mapped normal's detail would move the shadow's normal offset and receiver-plane slope per texel (blotches, §16.6); lighting (n·l, the highlight, the backscatter's n·l) uses the mapped normal |
| S7-5 | (not stated) | 128 / 255 is a map's zero (`texel × 255 / 128 − 1`) | 8-bit has no exact 0.5: a flat map (128, 128, 255) must not tilt (`a flat normal map = no change`). Maps that treat 127 as zero tilt by 0.8 % |
| S7-6 | §10 "Panel: … under „Mehr“" | under „Mehr“ in the material block, with the normal map's two values | as the AD; the strength and the DirectX flag are only shown with a normal map |
| S7-7 | (not stated) | PNG / JPEG / BMP up to 4096², a hint above 2048 (`PROVISIONAL`) | the sclera map's header reader (no decoder); ZBrush exports BMP / PNG. 16-bit and TIFF / TGA are refused with the reason. 4096² with mips is 85 MiB per map on a 512 MiB card - the hint says so |
| S7-8 | (not stated) | a preset keeps the maps; „Zurücksetzen“ removes them with the look | a preset carries no maps (like an eye preset keeps its images); reset = no LookDev material at all |
| S7-9 | (not stated) | the texture-unit check runs only when a drawn material has a map | S1's gate "every effect off: nothing probed" (`test_the_shadow_off_draws_m1_and_creates_nothing`) must hold with the maps switch on and no map |
| S7-10 | §2.3 point 5 (compile behind the status line) | a map assigned while the room is open compiles its variant in the next frame (≈ 50 ms on llvmpipe, no status line) | the same as an albedo-source switch today: `prepare_lookdev` covers the room's entry and the effect switches, not material edits. The variant is cached for the session; a scene opened with maps compiles them on entry |

### 20.3 Tests (container, llvmpipe, 2026-11-24)

| # | Test |
|---|---|
| Core | `tests/test_look_maps_format.py` (12): value rules, defaults, exact keys, `"maps": null` refused, v16 round trip on the JSON text, without maps the v15 text again, "maps" below 16 and 17 refused, invalid groups refuse the file, several objects; the five "first unknown version" assertions now say 17 |
| App | `tests/test_look_maps.py` (11): load / replace / remove with Undo / Redo, refusals with the reason, a preset keeps the maps and reset drops them, the normal values preview and commit (not „angepasst“), `with_map` / `with_values` rules, the LookDraw carries only drawable maps and only with UVs, the panel rows, save copies (one copy for one image, relative, the material points at the copy, nothing deleted), load resolves, saved again = no second copy, without maps v15 again, a missing map keeps its path, Duplicate carries them |
| sources | `test_lookdev_shaders.py`: new `PINNED_S4_SKIN_SOURCES_SHA256` (the 4 `shadow + dual_lobe + thickness` variants, taken from `50c69cd` before the change) holds with no map; M1 / S1 / S3 pins unchanged; each map's define and only its text, the UV declared once per albedo case, `n_geo` in the key lookups only with the normal map |
| twins | `test_lookdev_optics.py`: the flat map does not tilt, strength and green, the cotangent frame follows the UV (mirrored UV flips it, degenerate keeps `n`), the roughness map; the `maps` effect and its feature |
| GL | `tests/test_gl_lookdev_maps.py` (9): a flat normal map and white grey maps change no pixel (≤ 1/255), the effect off = no maps; a tilted constant normal map lights the plane as the twin (≤ 2/255), DirectX flips it, strength 0.5 between, 0 = none; a grey roughness map = the material's roughness × 128/255; the translucency map scales the backscatter; a face without UVs reads no map (half-UV plane), no UVs = 5-value keys; units 3 and 9–11 unbound after the frame; `texture_units` stubbed false = the no-map frame with the status line; the check passes on llvmpipe; GPU parity of `ld_cotangent_frame` / `ld_normal_tangent` against the twin over 1,024 random frames (max < 2e-4) |
| headless | effect lists in persistence / room / panel tests gain `maps`; `test_probe_lookdev_room.py` (`lookdev +maps`, the probe's images) |

Runs (GL files each in their own process under xvfb):

| Command | Result |
|---|---|
| `xvfb-run -a python -m pytest tests/test_gl_lookdev_maps.py -q` | 9 passed |
| `… tests/test_gl_lookdev_shadow.py` / `test_gl_lookdev_pass.py` / `test_gl_lookdev_parity.py` / `test_gl_eye_pass.py` | 25 / 13 / 8 / 135 passed |
| `… test_gl_face_data_layout.py` / `test_gl_shading.py` / `test_gl_texture.py` (E1) / `test_gl_gpu_picking.py` / `test_gl_morph_picking.py` (E15) | 16 / 19 / 10 / 37 / 16 passed |
| `… test_gui_imgui_window.py` / `test_gui_lookdev_window.py` (new: the map rows under „Mehr“) | 18 / 2 passed |
| `python -m pytest experiments/lookdev_eye_lab/tests` / `experiments/drag_cost/tests` | 206 / 107 passed |
| `xvfb-run -a python -m pytest tests -q` (a Core slice, §14) | see the follow-up note below |

**Sight check (container):** `Gollum_Head_05`, SubD 1, Creature Skin, the probe's 1024² bump normal map: 18,968 px
change, the bumps follow the UVs smoothly over the whole head, no black (NaN) pixel.

### 20.4 Measurement

Container (llvmpipe, a function check only): `probe_lookdev_room.py --effects maps --draws 3 --surfaces cage` set the
three 2048² probe maps on the head, ran `lookdev` and `lookdev +maps`, `glGetError` 0.

**Reference PC (S7, with S1–S4's open run):** the same single command as §18.4 (`probe_lookdev_room.py`, every built
row). What it decides for S7: `lookdev +maps` against `lookdev` ≤ +1.2 ms for the three maps (§2.5: ≤ +0.4 ms per
map); above it, the levers of §2.5 (a smaller map is the artist's; the effect's on/off).

### 20.5 Practical test S7 (`scenes/Gollum_Head_05.mirai.json`, about 15 minutes)

You need a normal map of Gollum's head in its UVs (ZBrush: *Normal Map* from the subdivided sculpt to the lowest level,
"Tangent", "Flip G" off, export as PNG / BMP), optionally a roughness or cavity map (grey).
Open LookDev, select the head, material **Creature Skin**, view „¾“, SubD 1.
1. **Normal-Map laden:** Material → „Mehr“ → Normal-Map „Laden …“. Erwartet: Poren / Falten aus ZBrush erscheinen im
   Licht, die Silhouette bleibt (es ist nur Shading). Sieht es eingedrückt statt erhaben aus → „Grün unten (DirectX)“.
2. **„Normal-Stärke“** 0 / 1 / 2: 0 = ohne Map, 1 = wie exportiert. Passt 1?
3. **Key drehen:** wandern die Details mit dem Licht, ohne Flecken im Schatten (der Schatten nimmt die Geometrie, nicht
   die Map)? Siehst du feine Kanten entlang der Dreiecke (S7-1)?
4. **Rauheit-Map** (falls vorhanden): dunkle Stellen glänzen schärfer, weiße bleiben beim Material-Wert.
5. **Speichern unter …** in einen neuen Ordner, neu laden: die Maps sind da und liegen in `<Szene>_textures/`.
6. **Effekt „Maps“ aus / an:** aus = das Bild ohne Maps.

Assumptions to correct in one sentence: maps are images in the object's UVs, not painted in Mirai (painted channels
are a later AD-037 phase); OpenGL green-up by default; a preset keeps the maps; at most 4096², PNG / JPEG / BMP.

---

## 21. Implementation note — S5 built (2026-11-24)

**Kurzfassung (Deutsch):** Die Spiegelung des Studios auf der Haut kommt jetzt aus einem vorgefilterten Umgebungs-Cube
statt aus der analytischen Näherung pro Pixel. Der Inhalt des Cubes **ist** das analytische Studio der Vorlage (keine
HDRI-Dateien, D-L4; Q-P3-4 wie vorgeschlagen): Level 0 ist das scharfe Studio, die rauen Level sind daraus mit GGX
gefiltert (64 Proben, Ecken-Korrektur). Er wird nur neu berechnet, wenn sich der **Inhalt** des Studios ändert (eine
Vorlage); Drehen, Intensität, Belichtung und die Lichter kosten nichts. Wegen des Treiberfehlers deiner Karte (§11.1
Lauf 4/5) wird der Cube auf der GPU gefiltert, zurückgelesen und neu hochgeladen; die Haut liest nur die Kopie. Ein
Vorlagenwechsel zeigt dafür einen Frame lang „LookDev: Umgebung wird vorbereitet …“. Mit „Doppel-Glanz“ liest die
Spiegelung jetzt auch zwei Anteile (P3-0 Lauf 5: billiger als ein analytischer). Die Augen bleiben beim analytischen
Studio. Neuer Schalter „Umgebungs-Cube“ (Standard an, braucht ein Cube-Ziel). Cube aus = S7, Zeichen für Zeichen.
**Sichtbar ändert sich wenig** (wie §8 sagt): am Gollum-Kopf nur einzelne Pixel an der Silhouette (≤ 7/255); auf einer
glänzenden Kugel im Mittel < 1/255, höchstens 20/255 bei Dramatic und Rauheit 0,25. Der Gewinn ist die richtige
Filterung bei mittlerer bis hoher Rauheit, weniger GPU-Zeit pro Pixel und die Grundlage für andere Umgebungen.

### 21.1 What is built

| Layer | Built |
|---|---|
| Effects / features | `LookdevEffects.cube` (default on; the fifth field, before `maps`, in the AD's slice order - persistence is by name); `EFFECT_FEATURE["cube"] = "cube_rgba16f"`, `EFFECT_LABEL` „Umgebungs-Cube“; `lookdev_features._cube_rgba16f` (the production size and levels, every face of every level attached in turn: complete, `glGetError` 0), status line „LookDev: Umgebungs-Cube aus – Cube-Ziel nicht verfügbar“ |
| Shaders | `CUBE_UNIT = 8`, `CUBE_SIZE = 128`, `CUBE_LEVELS = 7` (128² … 2²), `CUBE_SAMPLES = 64` (`PROVISIONAL`); `LD_CUBE_SRC` (`u_ld_env_cube`, `ld_env_cube(r, roughness)`: `u_ld_env_intensity × textureLod(cube, u_ld_env_rot × r, clamp(roughness) × 6)`), appended last only with the effect; `CUBE_PREFILTER_SRC` + `cube_prefilter_sources()` (the full-screen triangle; `LD_BRDF_SRC + LD_COMMON_SRC`, so the content is `ld_studio` itself; level 0 one sample, the rest GGX importance sampling, Hammersley, N = V = R, N·L-weighted; the corner fix); `skin_sources(..., cube_env)` refuses it without `env_spec` |
| Body block (1) | inside `ENV_SPEC`: `#ifdef CUBE_ENV` - `ld_env_cube` at `rough`, with a nested `DUAL_LOBE` the mix of two lookups at `rough × 1.3` / `× 0.75` (0.15 / 0.85, the lights' values) - `#else` the analytic line, character for character |
| Cube | `viewport/lookdev_cube.py`: `EnvCube.update(studio)` (prefilter only when `holds(studio)` is false: the `Studio` content, the SH9 key; renders every face of every level into a scratch RGBA16F cube through its own FBO, reads the chain back with `glGetTexImage` and uploads it into a fresh cube, deletes the scratch cube and the FBO; saves / restores FBOs, viewport, program, VAO, caps, depth mask, the active unit and unit 8's cube); `prefilters`, `last_ms`, `bind` / `unbind`, `read_back(level)` (test hook), `release()` |
| Pass | `LookdevPass.env_cube()` (created on first use, released in `release()`); `program_key(..., cube_env)`: 9 values with the cube (S4's 5, the three map flags, `CUBE_ENV`), else 5 or 8 as before; `draw(..., cube=None)` binds the cube on unit 8 and enables `GL_TEXTURE_CUBE_MAP_SEAMLESS` only around the draw (restored to what it was) |
| Viewport | `set_lookdev_effects(effects, studio=None)`: the studio content the next frame's cube shows; `_lookdev_programs` adds the cube flag; `lookdev_prepare_needed` is also true when a cube program is drawn and the cube does not hold the wanted content (`lookdev_cube_needed`), `prepare_lookdev` prefilters it; `_render_lookdev` brings the cube up to date before the background when a skin LookDraw is drawn and hands it to every skin draw. Eyes untouched |
| App | `_set_lookdev_studio_state` (every studio change: a preset, a setter, a loaded `view.lookdev`): with the room open and a prefilter due it takes the I-10 path - the frame before stays, status „LookDev: Umgebung wird vorbereitet …“, then `_prepare_lookdev_step` prefilters and switches („… (Umgebung in x s vorbereitet)“); rotation, intensity, exposure and the lights never wait |
| Twins | `lookdev_optics.cube_face_direction`, `cube_texel_directions` (with the corner fix), `radical_inverse`, `cube_level_roughness`, `cube_lod`, `prefilter_ggx` |
| GUI | `lookdev_model`: the effect row „Umgebungs-Cube“ with its hint; the „Doppel-Glanz“ hint says the reflection takes two lobes with the cube |
| Probe | `probe_lookdev_room.py`: `EFFECT_ROWS["cube"] = ("lookdev +cube", ("cube",))` against `lookdev`; `cube_rows`: per studio preset the build's wall ms (`EnvCube.last_ms`) and the frame after the preparation |

Not touched: `src/core/`, `serialization.py`, `LD_COMMON_SRC` (the eye's LOOKDEV pin), the other P3 library strings,
`eye_shaders.py`, `eye_pass.py`, `KeyShadow`, `main.py`, `config/keymap.json` (no keys), SH9 (the diffuse environment).

### 21.2 Where the build differs from §2 / §8, and why

| # | AD | Built | Why |
|---|---|---|---|
| S5-1 | §8 "prefilter … inside the frame, with no status line" | GPU prefilter, then read back and upload; a preset switch behind the status line of §2.1 | §11.1 run 4 / 5 (the reference PC's defect with sampling an FBO-rendered float cube; the copy costs 17–24 ms there). Applied on every card: checks are by function, never by GPU name (§2.2); `test_the_copied_cube_samples_over_many_frames` is the gate |
| S5-2 | §8 test "level 0 vs `ld_studio` within 1e-3 relative" | within one RGBA16F step (2⁻¹⁰) + 2e-4 | 1e-3 is the format's own limit: a half float's step is 9.8e-4 relative just above a power of two, and Mesa rounds the store toward zero. llvmpipe: 1.14e-3 at values just above 1.0 (≈ 1.15 steps), everywhere else below 1e-3; LD-0 (c) on the reference PC 6e-4 |
| S5-3 | §6 / §11.1 run 5 "S3 uses the second lobe on the environment too once S5 is in" | built: with `DUAL_LOBE` and `CUBE_ENV` two lookups; the analytic studio keeps one lobe | as run 5 decided (`cube dual env` cheaper than one analytic lobe) |
| S5-4 | §2.3 point 4 (the key's defines in a fixed order) | 9 values only with the cube (`key + maps + (True,)`), 5 / 8 as before without it | the S2-1 / S7-3 pattern: every key and test before S5 stays as it was |
| S5-5 | §8 "When: on a change of the studio's content" | also only when a skin LookDraw is drawn | an eyes-only or Reference-only frame needs no cube; the gate "every effect off: nothing created" holds |
| S5-6 | §8 "`update(studio)` … about 12 ms … inside the frame" | the frame builds it only if the room did not (a viewport without the app, a test); the app prefilters in `prepare_lookdev` | the I-10 path of §2.1 is the app's; the frame keeps a correct fallback |

**What changes in the picture** (container, llvmpipe): a glossy sphere (`GLOSSY`-like, F0 0.08) per preset and roughness
0.25 / 0.45 / 0.7 against the analytic studio - mean 0.4–0.8/255 over the lit pixels, p99 1–8/255, max 2–20/255 (the
largest at Dramatic, r 0.25: the softbox's edge, sharper in the cube's level 1 than in the analytic fit's widened
edge). `Gollum_Head_05`, SubD 1, Creature Skin, all other effects on, framed ¾ at 1024 × 768: Portrait 6 px > 2/255
(max 3), Dramatic 7 px (max 7), Soft Studio 0 px - all at the silhouette, where the Fresnel term lifts the reflection.
The eyes are unchanged.

### 21.3 Tests (container, llvmpipe, 2026-11-24)

| # | Test |
|---|---|
| sources | `test_lookdev_shaders.py`: new `PINNED_S7_SKIN_SOURCES_SHA256` (the 4 variants with every effect before S5 and all three maps, taken from `eb4c817` before the change); `test_the_cube_off_keeps_the_m1_to_s7_sources` (every pin with `cube_env=False`); `test_the_cube_variant_reads_the_cube_instead_of_the_analytic_studio` (define and library once, the library last, `ld_env_cube` in its block, twice with the dual lobe, refused without `ENV_SPEC`, nothing left with it off, `LD_COMMON_SRC` without a cube); `test_the_prefilter_program_is_the_studio_library_and_the_prefilter` |
| twins | `test_lookdev_optics.py`: the GL cube table and the corner fix (the three faces of a corner share its direction), `radical_inverse` / `cube_lod`, `prefilter_ggx` (one sample = the studio, a constant studio stays constant, a rough level is smoother); the `cube` effect, its feature and reason |
| GL (`tests/test_gl_lookdev_cube.py`, 13) | level 0 vs `ld_studio` (S5-2); the corner spread 0 at all 7 levels; levels 1–6 vs `prefilter_ggx` at 24 texels each (≤ 2 %; measured ≤ 9.6e-4); `ld_env_cube` at texel centres and the level's roughness = the texel × intensity with the studio turned 33° (the `textureLod` read-back); prefiltered only on a content change (rotation, intensity, exposure, a light, the camera +0, a preset +1, back +1, the capture's second draw +0); 30 frames of the copied cube identical, no GL error; cube off = the program of S7's call, pixel for pixel, nothing on unit 8, on stays close; the dual lobe reads it twice (9-value key, the picture changes); seamless and unit 8 as found (off and on before the frame); `prepare_lookdev` prefilters the wanted studio and the frame before keeps the old content; `cube_rgba16f` stubbed false = the cube-off frame, no cube, the status line once; the check passes on llvmpipe; in the app a preset switch waits one frame with „LookDev: Umgebung wird vorbereitet …“, then prefilters once, rotation / a light do not wait, the effect off compiles behind the status line and a preset switch then waits for nothing |
| updated | the effect lists in persistence / room / panel / probe tests gain `cube`; tests that compare against a program or twin before S5 (`test_gl_lookdev_shadow.py`: `OFF`, the S1 / S3 / S4 comparisons; `test_gl_lookdev_maps.py`: `MAPS_ONLY`) switch the cube off, as S3-4 did for E7. **Pre-existing, fixed here:** `test_lookdev_room.py::test_set_lookdev_effect_is_view_state_and_a_preset_keeps_the_effects` failed since S7 (its reasons dict lacked `maps`) |

Runs (GL files each in their own process under xvfb):

| Command | Result |
|---|---|
| `xvfb-run -a python -m pytest tests/test_gl_lookdev_cube.py -q` | 13 passed |
| `… tests/test_gl_lookdev_shadow.py` / `test_gl_lookdev_pass.py` / `test_gl_lookdev_parity.py` / `test_gl_lookdev_maps.py` | 25 / 13 / 8 / 9 passed |
| `… tests/test_gl_eye_pass.py` | 135 passed (unchanged; the eye pins green) |
| `python -m pytest tests/test_lookdev_shaders.py tests/test_lookdev_optics.py tests/test_lookdev_persistence.py tests/test_lookdev_room.py tests/test_gui_lookdev_model.py experiments/drag_cost/tests/test_probe_lookdev_room.py -q` | all passed |
| `… test_gl_face_data_layout.py` / `test_gl_shading.py` / `test_gl_texture.py` (E1) / `test_gl_gpu_picking.py` / `test_gl_morph_picking.py` (E15) | 16 / 19 / 10 / 41 / 16 passed |
| `… test_gui_imgui_window.py` / `test_gui_lookdev_window.py` | 18 / 2 passed (the maps window test now accepts the 9-value key with the cube) |
| `xvfb-run -a python -m pytest tests -k "lookdev or look or view_state or main_wiring" -q` | 492 passed |
| `python -m pytest experiments/drag_cost/tests` / `xvfb-run -a … experiments/lookdev_eye_lab/tests` | 107 / 206 passed |

Not run: the full `tests/` (S5 touches no `src/core/`, §14).

### 21.4 Measurement

Container (llvmpipe, a function check only): `probe_lookdev_room.py --effects cube --draws 3 --surfaces cage` ran
`lookdev`, `lookdev +cube` and the four `cube prefilter` rows (each `prefilters +1`, the build 49–65 ms wall on
llvmpipe) with `glGetError` 0.

**Reference PC (S5, with S1–S4's and S7's open run):** the same single command as §18.4 (`probe_lookdev_room.py`, every
built row). What it decides for S5:
- `lookdev +cube` against `lookdev` ≤ +0.3 ms (§2.5; P3-0 run 5 measured −0.4 / −0.6 ms, cheaper);
- `cube prefilter` ≤ about 40 ms wall per preset switch (run 5: 12 ms prefilter + 17–24 ms copy) - one frame's hitch
  behind the status line. Above it, the lever is the cube's size (a constant; LD-3's knob later).

### 21.5 Practical test S5 (`scenes/Gollum_Head_05.mirai.json`, about 5 minutes)

Open LookDev, SubD 1, material **Creature Skin**, then **Wet Skin**, view „¾“.
1. **„Umgebungs-Cube“ an / aus** (Block „Effekte“): Erwartet: kaum ein Unterschied, höchstens an der Silhouette und in
   den Glanzlichtern der Studio-Lichtflächen. Fällt dir etwas auf, das schlechter wirkt?
2. **Vorlage wechseln** (Portrait → Dramatic → Soft Studio): Erwartet: ein Frame mit „LookDev: Umgebung wird vorbereitet
   …“, dann das neue Studio; kein spürbares Stocken über diesen einen Frame hinaus.
3. **Studio drehen, Intensität, Lichter:** Erwartet: flüssig, keine Statuszeile (der Cube wird nicht neu gerechnet).
4. **Wet Skin, „Doppel-Glanz“ an / aus:** die Spiegelung der Lichtflächen hat mit Doppel-Glanz einen weicheren Saum.

Assumptions to correct in one sentence: the cube is on by default; its content is the preset's analytic studio (no
HDRI, Q-P3-4: an `.hdr` import of your own files is a separate item on your word); the eyes keep the analytic studio;
the size is fixed (128², LD-3's knob later).
