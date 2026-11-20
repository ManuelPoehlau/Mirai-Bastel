# AD-038 — LookDev Room M1 (LD-0 / LD-1): room frame, LookDev pass, linear colour pipeline, eye variant, studio, materials

**Status:** **ACCEPTED (Manu, 2026-11-19)**: „AD-038 freigegeben, Fragen 2–4 wie vorgeschlagen, Frage 3 würde ich
Neutral wählen“ (§15). **LD-0 run on the reference PC (Manu, 2026-11-19)**: LD-D10 met with a wide margin (§16.1).
**LD-1 built 2026-11-19** (branch `claude/sweet-hamilton-pzimll`, implementation note §17). **LD-1 measured on the
reference PC (2026-11-20, §17.4): LD-D10 and E16 met** — the room's frame 2.4 / 3.3 ms GPU (cage / SubD 1, framed
1024×768), cheaper than the Worklight; the Modelling Room unchanged. Next: Manu's M1 practical
test (§13.3, checklist §17.5). Drafted 2026-11-19 as PROPOSED (Architecture Gate). The number
AD-038 stays; new class, file and panel names remain `PROVISIONAL` until built.
**Basis:** [LOOKDEV_P2_ARCHITECTURE_UX_PROPOSAL_2026-11-19](../design/LOOKDEV_P2_ARCHITECTURE_UX_PROPOSAL_2026-11-19.md)
(decisions LD-D1 … LD-D14, Manu 2026-11-19, its §0) and its
[technical appendix](../design/LOOKDEV_P2_TECHNICAL_APPENDIX_2026-11-19.md).
**State inspected:** `main` @ `89f61fc` = the working branch `claude/zen-franklin-6g8u7f` at the same commit, clean tree.
`git diff a3bfcc0 89f61fc -- src tests experiments config` is empty: the code the proposal read is the code checked here.
Every code statement this AD relies on was re-checked at `89f61fc` (§1); where the proposal was wrong or incomplete, §1
says so and the AD follows the code.
**Extends:** [AD-033](AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md) (the eye pass, source discipline),
[AD-026](AD-026-FACE-CORNER-UVS-AND-TEXTURE.md) (triangle UVs, the textured program),
[AD-037](AD-037-TEXTURE-PAINT.md) (the Paint Room as a room, `LiveTexture`),
[AD-024](AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md) (the Worklight material stays as it is),
[AD-018](AD-018-PRODUCTION-DRAW-BINDING.md) (the draw binding). Does **not** touch [CORE_V1_FREEZE](CORE_V1_FREEZE.md):
no Core field, no format version in M1 (LD-D12).

Evidence tags as in the proposal: **[V]** verified in code at `89f61fc` (file:line), **[M-C]** measured in the container
(a function check only), **[M-RPC]** measured on the reference PC, **[P]** decided by this AD if accepted, **[E]**
estimate, **[O]** open for Manu.

---

## Kurzfassung (Deutsch)

- **Was dieses AD festlegt:** die verbindliche Architektur für M1 = LD-1. Der LookDev-Raum ist eine Konfiguration
  desselben Fensters (wie der Paint Room), ohne eigene Interaktions-Sitzung. Er schaltet `Viewport.shading` auf
  `"lookdev"`. Dann zeichnet ein eigener `LookdevPass` – außerhalb von `GLRenderStore.draw()`, gebaut wie der `EyePass` –
  dieselben Puffer, die der Viewport ohnehin hat: Morph, Pose und SubD wie ausgewertet.
- **R-1** gilt als Vertrag für alle Räume: Ein Raumwechsel setzt Pose, Morph-Gewichte, aktuelles Ziel, Blick und
  SubD-Einstellungen nie zurück. Wo ein Raum den Zustand nicht tragen kann, wird mit Statuszeile abgelehnt. Ein Test prüft
  das für LookDev, den Paint Room und das Eye Lab.
- **Kleinste Schnittstelle:** ein UV-Anforderungs-Flag am `RenderMesh` und **eine** öffentliche Bindung für die UVs je
  Dreieck am `GLRenderStore`. Face-Daten bleiben privat.
  - **Abweichung:** Es braucht eine zweite kleine Methode für die Albedo-Textur. Das Hochladen einer `LiveTexture`
    (deine Bemalung) ist heute privat. Das ist keine Face-Daten-Freigabe.
- **Augen:** ein Augen-System, ein Augen-Durchgang, eine neue Variante `LOOKDEV`.
  - Die Worklight-Varianten bleiben quelltextgleich. Der bestehende SHA-256-Pin bleibt, und zusätzlich wird **vor** der
    Änderung ein Pin über *alle* Worklight-Quellen gesetzt. Der alte Pin deckt die Lederhaut-Karten-Varianten nämlich
    gar nicht ab (§1, C6).
  - Pixelgleichheit sichern die bestehenden GL-Tests.
- **Farbe:** In LookDev wird alles linear gerechnet und pro Pixel genau einmal belichtet, getont und kodiert, für Haut
  und Augen mit derselben Funktion. Der Hintergrund wird genau so gezeigt, wie gewählt.
- **Licht:** SH9 für die diffuse Umgebung und das analytische Studio des Auges, parametrisch gemacht, für sichtbare
  Reflexe. Key, Fill und Rim sind fest zur Welt.
- **Material:** ein organisches Modell mit sechs Vorlagen, in M1 nur für die Sitzung (nichts wird gespeichert).
- **Abweichungen vom Vorschlag**, alle begründet in §14:
  - Der Hintergrund wird im Viewport gezeichnet, `main.py` bleibt unberührt.
  - Die Augen-Variante behält die Uniform-Namen des Worklights und bekommt die LookDev-Werte.
  - Das UV-Flag folgt auch den neu gebauten SubD- und Posen-Flächen.
  - Zwei Worklight-Stellen im Augen-Shader fehlten in der Liste des Vorschlags.
- **LD-0-Sonde** `experiments/drag_cost/probe_lookdev.py`: Im Container läuft sie vollständig, aber nur als
  Funktionstest. Die Zahlen deines Referenz-PCs entscheiden (§13, §16).
- **Stand 2026-11-19:** von dir freigegeben, die Sonde lief auf dem Referenz-PC. Der gerahmte Kopf braucht 1,7–2,2 ms
  GPU bei 1024×768, also 5–7 % von 33,3 ms. LookDev ist in jeder Ansicht billiger als das Worklight. Das erste
  Kompilieren einer Augen-Variante dauert bis 0,6 s, deshalb wird beim Betreten mit Statuszeile vorkompiliert (§16.1).
  LD-1 kann beginnen.

---

## 1. Code check at `89f61fc` (what the proposal said, what the code says)

### 1.1 Verified as the proposal states [V]

| Statement | Where |
|---|---|
| The eye pass draws a store's VertexList with its own program, from `vertex_list()` / `uniform_data()` only | `viewport/eye_pass.py:457–549`, routed in `viewport/viewport.py:1019–1025` |
| `Viewport.render()` draws `surface_render_mesh or render_mesh`, then the entries in `_entry_draw_order()` (opaque before ghosts), each through its entry surface when one exists | `viewport.py:995–1027`, `:438–443` |
| The 7 Worklight light uniforms are resolved once per frame and pushed to every store | `viewport.py:327–334`, `:1007–1014`; world-space directions, `viewport/light_rig.py:227–251` |
| UVs on the GPU are tied to the Worklight texture | `viewport/render_mesh.py:650–651` (`_uv_wanted`), resource sync `:697–708`, full-rebuild decision `:919–924` |
| The triangle UVs exist only inside the store's private face-data methods | `viewport/gl_render_store.py:636–642`, `:740–780`, `:810–819`, `:829–838` |
| The textured Worklight program = VS + GS (barycentrics, `gl_PrimitiveID`) + FS; UV by `gl_PrimitiveID * 3`, unmapped below −1e29 | `gl_render_store.py:358–401`, `:309–318`, `:464–477` |
| Hard-coded clear colour | `src/main.py:715` |
| `_shown_texture` returns no texture for a highlighted object or with textures hidden; the paint composite is a `LiveTexture` | `mirai/controllers/objects.py:1543–1554` |
| Eye shader source discipline: `_header` drops undefined defines, `_without` resolves `#ifdef` blocks of the **body** | `viewport/eye_shaders.py:1021–1068` |
| `PINNED_SOURCES_SHA256` and its test | `tests/test_gl_eye_pass.py:1099`, `:1108–1124` |
| Eye texture units 1 iris, 2 noise, 3 key table, 4 sclera map | `eye_pass.py:36–43` |
| Program key of 8 values | `eye_pass.py:220–221` |
| Paint Room saves and restores `mode`, `wire`, `texture`, `regions`; closes an open Eye Lab; refuses a posed or morph-mixed object (P-8) | `mirai/application.py:1070–1124`, `:1052–1068` |
| A save inside the Paint Room writes the restored display | `application.py:1732–1736` |
| A scene reset / load closes the Paint Room | `application.py:732–733` |
| Eye Lab saves camera, isolation, tier | `application.py:1010–1043` |
| `view_state.capture` writes only its known sections (an unknown `view.lookdev` is dropped on save); `apply` reads only known ones | `mirai/view_state.py:41–80`, `:114–125` |
| `kelvin_to_rgb` (linear Rec.709, normalised) | `light_rig.py:205` |
| `OrbitCamera.frame_on_bounds` | `mirai/viewport/camera.py:117` (the proposal's `camera.py` is under `mirai/viewport/`) |
| SubD cap | `mirai/subdivision/preview.py:75` |
| `DisplayState` (eye tier, Eye Lab, texture toggle) | `mirai/viewport/display.py:74–87` (the appendix's `viewport/display.py` is under `mirai/`) |

### 1.2 Corrections and additions (the AD follows the code)

| # | The proposal | The code at `89f61fc` | Consequence here |
|---|---|---|---|
| C1 | "unit 1 = triangle UVs (the store's own unit); 2, 3, 5 free" (§10.2) | The store binds face normals on 1, triangle→face on 2, **triangle UVs on 3**, the texture on 4, face corners on 5, positions / normals on 6 / 7 (`gl_render_store.py:411–421`) | The LookDev pass reads the UVs on unit 3 and the albedo on 4. The unit is the caller's argument of `bind_triangle_uvs` anyway (§4.2) |
| C2 | "the `LiveTexture` upload path is reused" (§6.1) | The upload is the private module function `_upload_live` (`gl_render_store.py:508–548`); only the store's own `draw()` calls it (`:1031–1036`) | A second small public method is needed for the albedo binding (§4.3). It exposes no face data |
| C3 | Set the UV request "for an entry whose `LookDraw` needs an albedo map" (§10.3) | What is drawn is often **another** `RenderMesh`. The SubD / morph / pose surface of the edit object (`viewport.py:670–692`) and every entry surface (`:631–668`) are created anew and get their material only at those hand-over points | The request is held by the viewport per key and applied wherever the material is handed over (§4.1). A flag on the edit `RenderMesh` alone would never reach the SubD surface that draws |
| C4 | The LOOKDEV blocks replace diffuse, albedos, `td_env`, the `display_add` sites and the output (§7.2, appendix C.3) | The body has two more Worklight-specific terms. One is the Worklight's Blinn-Phong "plastic" highlight with the Worklight finish (`eye_shaders.py:878–881`, `:902–904`). The other is the soft key's area frame, taken from the **camera's** axes (`:666–668`). The studio is evaluated in **view space** (`r_view = mat3(u_view) * reflect(…)`, `:650`, `:678`) | Both are LOOKDEV blocks (§5.3, B5 / B6). The LookDev studio is evaluated in the studio frame (world × rotation), so it no longer turns with the camera |
| C5 | "In the LookDev variant the 7 Worklight uniforms are not declared" (appendix C.3) | They are declared in `EYE_LIB_SRC` (`eye_shaders.py:112–119`), which is in every variant and is not passed through `_without` | The LOOKDEV variant keeps those names and receives the LookDev key / fill, with ambient 0 (§5.2). The library stays untouched. The phase 4 iris key table, baked from `light["u_key_dir"]` (`eye_pass.py:493`, `:300–343`), then follows the LookDev key with no code change |
| C6 | "`PINNED_SOURCES_SHA256` … stay unchanged" proves Worklight source identity (§7.3) | The pin hashes the product of 7 arguments with `sclera` **off** (`test_gl_eye_pass.py:1104–1124`). The 256 sclera-map variants, the iris-table program and the parity programs are **not pinned** | LD-1's first commit adds a second pin over the whole Worklight source space, computed at `89f61fc` **before** `eye_shaders.py` changes (§5.4). Value at `89f61fc`: 1,030 sources, SHA-256 `714a683b3ab967518c032312fc8e2327717d7f3d3afa0389bffa40d9b6df9bf0`, same float normalisation as `_source_digest` |
| C7 | A `LOOKDEV_LIGHT_LIB` "included by both" passes (§7.4) | `EYE_LIB_SRC` already defines `srgb_encode`, `ggx_d`, `smith_vis`, `schlick_scalar`, `env_brdf_approx`, `erf_approx`, `box_profile` (`eye_shaders.py:122–172`). Including a library that defines them again is a GLSL redefinition error | The shared library is split into the part the eye lacks and a BRDF part for the skin only. The BRDF part's functions are pinned character for character to the eye's by a test (§5.2) |
| C8 | Background: "the clear colour behind a getter" in `main.py` (appendix F) | `main.py:715` clears before `viewport.render()` | LookDev draws its background as the first step of `render()`; `main.py` is not touched (§8) |
| C9 | "no FBO in P2" (§10.4, appendix C.4) | The eye pass already renders its phase 4 key table (RGBA16F 64²) through an FBO and unbinds it inside its draw (`eye_pass.py:300–343`) | I-4 ("no FBO bound across `on_draw` steps") holds; LookDev adds no FBO in M1 |
| C10 | Gollum head: teeth "(4 objects)" in the practical test scene | In `scenes/Gollum_Head_05.mirai.json` the teeth and the older head object are **hidden**. Drawn: the painted head (2,492 faces; SubD 1 = 22,153 triangles) and two eyes (look, iris and sclera map on). The head's paint composite is a flat base colour; the teal / peach areas seen in the Worklight are **saved region tints**, which the room switches off (proposal §2.2). The head is placed (scale 0.595) [V, probe header] | The M1 practical test should show the teeth (Show) to judge "Zähne". Expect the plain composite on the head in LookDev |
| C11 | (not stated) posed / morphed surfaces carry UVs | `SurfacePositions` reads topology **and UVs** live from the base (`mirai/surface_positions.py:17–19`). The SubD surface refines them (`subdivision/preview.py:372`) | The albedo map works on the posed, morphed and subdivided head with no extra data path |

---

## 2. The room frame and R-1

### 2.1 The room [P]

- **Controller:** `src/mirai/controllers/lookdev_room.py`, class `LookdevRoom` (`PROVISIONAL`). It holds:
  - `open`, `saved_view` (the display values it changed);
  - the session studio state (§6);
  - the session material table (§7).

  It has **no** interaction session: LookDev changes no gesture (LD-D1, LD-D2).
- **Application:** `lookdev_open`, `lookdev_refusal()`, `open_lookdev()`, `close_lookdev(status=…)`, plus setters for
  the studio, lights and material that the panel calls. They follow the `open_paint_room` / `close_paint_room` shape
  (`application.py:1070–1124`).
- **Entry:** one SPACE menu row "LookDev öffnen" / "LookDev schließen" (`gui/menus.py`, beside the Paint Room row at
  `:348`). There is **no key** and no keymap entry (D-L9).
- **On entry, saved for the exit:**
  - `mode` → Shaded;
  - `wireframe_overlay` → off;
  - `region_tint` → off;
  - `eye_tier` → "full".

  The camera, `show_texture`, the light rig and the selection are not touched (LD-D4).
- **Refusals on entry** (status line, nothing changed):
  - an exclusive interaction runs (Knife, Bone chain, a Paint stroke): `interaction.session` with another owner;
  - an object gesture is held.
- **Other rooms:**
  - Opening LookDev **closes** an open Eye Lab (LD-D14, as `open_paint_room` does, `application.py:1082–1083`).
  - Opening LookDev closes an open Paint Room between strokes, restoring the Paint Room's display values first.
  - `open_eye_lab()` is **refused** while LookDev is open ("Eye Lab: erst LookDev schließen", LD-D14).
  - `open_paint_room()` while LookDev is open first checks `paint_room_refusal()`:
    - when it refuses (for example P-8 in a pose), LookDev **stays open** and nothing changes (R-1);
    - otherwise LookDev closes (restoring its values) and the Paint Room opens.
- **While open:**
  - A scene save writes the *restored* `mode`, `wireframe_overlay` and `region_tint` into `view.display`, as the Paint
    Room does (`application.py:1733–1736`). The eye tier is not part of the saved view (`view_state.py:47–80`).
  - `init_scene` (load or reset) closes the room before the scene is replaced (beside `application.py:732–733`).
  - Changing the edit object keeps the room open (it is not bound to one object).
- **Selection feedback:** no yellow tint in the room (LD-D3).
  - For eyes, the existing condition `tinted = oid in highlighted and not (eye_lab and obj.eye is not None)`
    (`objects.py:1410`) becomes "not (a room that judges colour is open and …)": the Eye Lab for eyes, LookDev for every
    object.
  - The skin pass ignores the tint by construction: `LookDraw` is resolved from the object, not from the packet (§3.3).

### 2.2 R-1 — the contract for every room [P] (LD-D13)

> **R-1.** Entering, leaving or switching rooms (LookDev, the Paint Room, the Eye Lab window, and every later room)
> never silently resets, modifies or overwrites **pose, morph weights or the current target, gaze, or SubD settings**.
> If a target room cannot host the current state, the switch is **refused with a status line**. It is never made
> possible by resetting the state. R-1 governs room transitions only. It does not change how these states are saved
> (morph and SubD in `view.morph` / `view.subd`; pose and gaze not saved).

How R-1 is held:

1. **By construction:** a room's open / close code may write only the display fields in its own `saved_view` and its
   own session state. LookDev's are listed in §2.1; the Paint Room's and the Eye Lab's are unchanged.
2. **By test** (`tests/test_room_rule.py`, new, headless): a snapshot of the R-1 state, compared bit for bit before and
   after every transition. The snapshot holds:
   - the pose's bone values;
   - every object's morph weights and current target;
   - the gaze target;
   - the SubD view, level, cage depth test, secondary strength and lines.

   The transitions:
   - enter / leave LookDev;
   - LookDev → Paint Room (refused in a pose: state and room unchanged) and back at rest;
   - Eye Lab → LookDev;
   - Eye Lab refused inside LookDev.

   The test runs in a pose with a morph mix, with gaze on and with SubD on.

---

## 3. `Viewport.shading` and the LookDev pass

### 3.1 The switch [P]

- `Viewport.shading: str`, `"worklight"` (default) or `"lookdev"`. It is draw state, like `eye_display`. It is set only
  by the room through `Application`.
- With `"worklight"`, `render()` runs today's code. The only addition is one string comparison. No LookDev object is
  created, no program compiled, no frame dict resolved, no UV request set (LD-D10 gate).
- With `"lookdev"`, `render()` keeps its loop and order (`viewport.py:1006–1027`). It changes three steps:
  1. **Before** the meshes: the background (§8).
  2. The edit object's drawn mesh and every entry **with a `LookDraw`** go to `LookdevPass.draw(render_mesh, look,
     frame)` instead of `RenderMesh.render()`.
  3. Eye entries go to `EyePass.draw(…, lighting=frame)` with the LOOKDEV variant (§5).

  Entries without a `LookDraw` keep the Worklight draw (References as Ghost or shaded: LD-D15 stays open, so the
  default is today's). Overlays, the gizmo, the HUD and imgui are drawn after `render()` as today (`main.py:713–735`).
- `light_uniforms()` is still pushed to every store each frame (`viewport.py:1007–1014`). Entries drawn by the Worklight
  inside the room need it, and the 7 Worklight uniforms stay Worklight-only (I-11).

### 3.2 `LookdevPass` [P]

- New `src/viewport/lookdev_pass.py`. It is built like `EyePass` (`eye_pass.py:185–586`):
  - inputs `store.vertex_list()`, `uniform_data("camera_uniforms" / "model_uniforms")`;
  - attribute locations from `GLRenderStore.program().attributes` (P0 I-2);
  - its own programs, compiled lazily and cached by the key `(ALBEDO_MAP, ENV_SPEC)`, at most 4 in M1.
- **Program:**
  - VS + GS = the textured Worklight program's **own** vertex and geometry sources (`gl_render_store.TEXTURED_VERTEX_SRC`
    formatted with those locations, `TEXTURED_GEOMETRY_SRC`). This gives the same transform, the same barycentrics and
    the same `gl_PrimitiveID`, which is the depth contract I-1 by construction.
  - FS = `lookdev_shaders.LD_BRDF_SRC + LD_COMMON_SRC + SKIN_BODY` (§5.2).
- **The skin model** (proposal §9.1):
  - the albedo map or colour, sRGB-decoded;
  - interpolated normals, with specular AA from the normal derivatives (taken outside any branch);
  - wrap diffuse, wider in red, from key / fill / rim;
  - GGX / Smith / Schlick specular from the three lights, each light's size widening its α;
  - SH9 irradiance;
  - the parametric studio as environment specular at the effective roughness, with the analytic split-sum term;
  - low warm backscatter;
  - `lookdev_output` once at the end.
- **GL state:** as `EyePass` leaves it (`eye_pass.py:521–549`):
  - during the draw: depth test and write on, blend off, back faces culled, polygon offset (1, 1) when
    `store.polygon_offset`;
  - afterwards: offset, cull and depth test off, the used units unbound, unit 0 active, program stopped.
- **Units:** UVs 3 (C1), albedo 4. 6 stays free for the P3 shadow map; the probe uses it there. Unit 0 is never used
  (I-5).
- **No FBO, no float target, no MSAA** in M1: the pass writes the RGBA8 default framebuffer. It never writes a
  `RenderMesh` or store buffer (I-10).

### 3.3 `LookDraw` and the entries [P]

- `LookDraw` (frozen dataclass, `viewport/lookdev_pass.py`) holds:
  - `base_color` (sRGB artist value), `roughness`, `specular` (level, F0 = 0.08 · level), `wrap_rgb`, `backscatter`,
    `backscatter_color`;
  - `albedo` — a path, a `LiveTexture` or `None`.

  It has no Core type in M1.
- `Viewport.set_object_entry(…, look: LookDraw | None = None)` and `Viewport.set_edit_look(look)` follow the `eye=`
  pattern (`viewport.py:338–388`).
- `ObjectController.sync_views` resolves `LookDraw` while the room is open, **from the object**, never from the packet
  (P0 I-6):
  - the session material (§7), or the Neutral fallback;
  - the albedo source = `paint_display.texture(obj)` when `paint_display.shows(obj)`, else `obj.texture`.

  This is independent of the Worklight's texture toggle and the selection tint (`objects.py:1543–1554` keeps its two
  conditions for the Worklight).
- Closing the room clears every `LookDraw` (`look=None`), so the entries are exactly today's.

---

## 4. The smallest interface

### 4.1 The UV request on `RenderMesh` [P]

- `RenderMesh.set_uvs_requested(bool)` and an `_uvs_requested` attribute. The rule becomes:

  ```python
  def _uv_wanted(self) -> bool:
      return ((getattr(self.material, "texture", None) is not None or self._uvs_requested)
              and self.mesh.has_face_uvs())
  ```

  A change marks the material dirty. The existing `_sync_uv_resource` allocates or frees `triangle_uvs`
  (`render_mesh.py:697–708`): no rebuild, no new code path. With the flag off everywhere the rule is today's
  expression, character for character in effect.
- `_push_texture` (`render_mesh.py:710–713`) is unchanged. A request with no Worklight texture pushes `None`, so the
  Worklight draw of such a mesh stays untextured, because `_textured()` needs a path (`gl_render_store.py:829–838`).
- **Where it is set (C3):** the viewport keeps `_uv_requests: set` of keys (`"edit"` and entry keys), filled from the
  `LookDraw`s that have an albedo source. It applies the request to:
  - the entry's `RenderMesh`;
  - the edit `render_mesh`;
  - every **surface** `RenderMesh` drawn in their place, in the same places that hand the material over: `_follow_entry`
    (`viewport.py:656–668`) and the surface creation in `_sync_surface` (`:683–692`).

  The request is set when the room opens or a `LookDraw` gains or loses an albedo source. It is **not** set per frame.
- **Cost:** LD-0 (b), §16.

### 4.2 The one triangle-UV binding [P]

- `GLRenderStore.bind_triangle_uvs(unit: int) -> bool` and `unbind_triangle_uvs(unit: int)`:
  - flushes **only** the triangle-UV buffer (upload if dirty or resized, the logic of `_flush_face_data` for one
    name) and binds its buffer texture to `unit`;
  - returns `False` when the store has none.
- The Worklight's `draw()` keeps calling its private methods (`_flush_face_data`, `_bind_vertex_textures`,
  `_set_face_samplers`) unchanged.
- **Not exposed:** face normals, face corners, triangle→face rows, the R32F vertex views, region tints. A region or
  per-face material (LD-D8) or a quad normal would need some of these; that access is decided with such a feature.

### 4.3 The albedo binding — a deviation, named [P]

- `GLRenderStore.texture_binding(source) -> tuple[int, int] | None` (classmethod) returns the GL `(target, name)`
  for a texture source the store already knows how to show:
  - a path, through the shared cache `GLRenderStore.texture(path)` (`gl_render_store.py:606–620`, already public and
    used by `EyePass`);
  - a `LiveTexture`, through `_upload_live` when it has pending boxes (`:508–548`).

  The caller binds the unit.
- **Why:** without it the LookDev pass would import a private function of the store, or upload the paint composite a
  second time (proposal §6.1 rules out a second upload). It is texture access the store's `draw()` already has, not
  face data.

---

## 5. The eye `LOOKDEV` variant and the shared linear pipeline

### 5.1 One more define [P]

- `es.shell_sources(…, sclera=False, lookdev=False)`: a new keyword, last.
- `EyePass.program(…, lookdev=False)` puts it in the cache key, which grows from 8 to 9 values.
- `EyePass.draw(render_mesh, draw, light, display, lighting=None)`:
  - `lighting=None` is today's call, unchanged;
  - a LookDev frame dict selects the LOOKDEV program and feeds its values.
- Only drawn variants are compiled. The room typically needs one or two.

### 5.2 Library layout [P]

- `src/viewport/lookdev_shaders.py` (new) holds three GLSL strings:
  - `LD_COMMON_SRC`: the `u_ld_*` uniforms, `srgb_decode`, `sh9`, `ld_studio` (the parametric `td_env`), `ld_diffuse`
    (key / fill / rim wrap + SH9) and `lookdev_output` (exposure → tone curve → `srgb_encode`). It uses `srgb_encode`,
    `erf_approx` and `box_profile` and defines none of them.
  - `LD_BRDF_SRC`: for the skin program only, copies of `srgb_encode`, `ggx_d`, `smith_vis`, `schlick_scalar`,
    `env_brdf_approx`, `erf_approx`, `box_profile`. A test asserts that each of these function definitions is a
    **character-identical** substring of `eye_shaders.EYE_LIB_SRC`, so the two passes share one BRDF and one colour
    encode (C7).
  - `SKIN_BODY`: the skin program's fragment body.
- **The eye's LOOKDEV source:**

  ```
  header(+ LOOKDEV 1) + EYE_LIB_SRC + [LOOK…, IRIS…, SCLERA…] + LD_COMMON_SRC + body
  ```

  `LD_COMMON_SRC` is appended **only** when `lookdev` is on. Without it, the source is today's, through `_header`
  (which drops an undefined define, `eye_shaders.py:1021–1022`) and `_without(body, "LOOKDEV")`.
- **Uniforms (C5):**
  - The LOOKDEV variant keeps `u_key_*` / `u_fill_*` / `u_ambient` and is fed the LookDev key and fill, with
    `u_ambient = 0`.
  - Rim, SH9, the studio, its rotation, exposure, the tone curve and the key's area frame are `u_ld_*`. The prefix keeps
    them disjoint from the Worklight names.
  - `EyePass.draw` already sets only the uniforms a program declares (`eye_pass.py:504–507`).
  - The phase 4 key table follows the LookDev key, because it is baked from `light["u_key_dir"]`
    (`eye_pass.py:493`). A new key direction rebakes it once (its cache key holds the key in the eye's frame,
    `:300–313`). That is a rebake on a studio rotation, never per frame.

### 5.3 The blocks (exactly these sites) [P]

Each is `#ifdef LOOKDEV … #else <today's line> #endif` in `SHELL_FRAGMENT_BODY`:

| # | Site | Worklight (kept) | LOOKDEV |
|---|---|---|---|
| B1 | `lit()` `eye_shaders.py:614` | `albedo * worklight_light(n)` | `srgb_decode(albedo) * ld_diffuse(n_world)` |
| B2 | `iris_lit()` `:629–638`, the ambient term | `vec3(u_ambient)` | `sh9(u_ld_env_rot * n_world)` (key through the table and fill unchanged, now LookDev values); albedo decoded as in B1 |
| B3 | albedo decode | display values | **at B1 / B2 only**: every diffuse albedo passes through `lit` / `iris_lit`. Blends of albedos *before* lighting (the limbal tint, `:761`, `:763`) stay in display space as they were tuned. This is a deliberate, documented simplification, checked by the grey-card test (E7) |
| B4 | `cornea_reflection` `:646–655`, `film_reflection` `:674–682` | `td_env(mat3(u_view) * r, …)` (view-locked studio) | `ld_studio(u_ld_env_rot * r, …)` (studio frame) |
| B5 | `key_reflection` `:664–669`, the soft key's frame | the camera's up / right (`view_t`) | the key's own frame `u_ld_key_up` / `u_ld_key_right` (C4) |
| B6 | the plastic highlight `:878–881`, `:902–904` | Worklight Blinn-Phong with the Worklight finish | GGX `direct_specular` (already in `EYE_LIB_SRC`) from the LookDev key / fill at `u_sclera_roughness`, `u_cornea_f0` (C4) |
| B7 | `display_add(…)` `:821`, `:823`, `:897` | per-term Reinhard + encode, added to display values | the linear term, added linearly |
| B8 | output `:907` | `vec4(colour, 1.0)` | `vec4(lookdev_output(colour), 1.0)` |

Unchanged in both:
- refraction V2 / V3, the iris analytic geometry, the fit, relief, caustic, limbus L0–L3;
- the wet film, irregularity, lid shadow and band;
- the sclera map's mapping, the gaze (the drawn matrix) and the units 1–4 (no new unit).

### 5.4 Worklight guarantees [P]

1. **Source identity.**
   - `PINNED_SOURCES_SHA256` and `test_sources_without_a_map_are_the_ones_before_ad035` stay unchanged and are **not**
     re-pinned.
   - **New** (C6): `PINNED_WORKLIGHT_SOURCES_SHA256 = "714a683b3ab967518c032312fc8e2327717d7f3d3afa0389bffa40d9b6df9bf0"`
     covers every `shell_sources` variant with `lookdev` off (8 arguments, the sclera map included), `parity_sources`
     for both fits and `iris_table_sources`: 1,030 sources, in that order, with the floats normalised as in
     `_source_digest`.
   - It is computed at `89f61fc` and committed in LD-1's **first** commit, before `eye_shaders.py` changes, so the pin
     is taken from the old code.
   - A further new pin covers the LOOKDEV variants (E4).
2. **Pixel identity:** the existing GL tests pass unchanged (§11), notably:
   - `test_preview_off_is_the_worklight_draw` (`test_gl_eye_pass.py:165`);
   - `test_sclera_reads_like_a_worklight_object_of_its_colour` (`:143`);
   - the parity test (`:440`);
   - the Worklight pixel gates;
   - the frozen lab's oracle tests.

### 5.5 One linear pipeline [P] (LD-D7)

- In LookDev every colour texture, paint composite and picked colour is decoded sRGB → linear in the shader. Lights are
  linear (`kelvin_to_rgb`). Shading is linear.
- **Once per pixel**, the skin pass and the eye pass call the same `lookdev_output`:
  1. exposure (2^EV);
  2. the tone curve: M1 default luminance Reinhard (hue-preserving, as in the probe); "Clamp" as a diagnostic. A
     filmic candidate is chosen in the practical test without an architecture change;
  3. `srgb_encode`.
- One frame dict (`lookdev_optics.frame_uniforms(state, camera)`, resolved once per frame) feeds both passes, the
  pattern of `light_uniforms()`.
- **Calibration (E7):** a Neutral grey card (albedo 0.5) on the skin pass and a sclera of the same albedo and roughness,
  lit by the same key at normal incidence, match within ≤ 2/255.
- The Worklight stays display-referred and unchanged. The two contexts are deliberately not calibrated against each
  other (proposal §11).

---

## 6. SH9 and the parametric analytic studio [P] (LD-D5, LD-D11)

- **State** (session, in `LookdevRoom`):
  - preset, rotation (degrees about the vertical), environment intensity, exposure (EV), tone curve;
  - key, fill and rim, each with on, intensity, azimuth, elevation, Kelvin and size;
  - "Licht folgt Kamera";
  - the background (solid or gradient, colours).
- **Presets:** Neutral Inspection · Portrait (default) · Soft Studio · Dramatic, as data in
  `src/mirai/lookdev_presets.py`. Values `PROVISIONAL`, tuned in the M1 practical test.
- **`src/viewport/lookdev_optics.py`** (NumPy, GL-free, the twin of `lookdev_shaders`, the `eye_optics` ↔
  `eye_shaders` pattern) provides:
  - `ld_studio(d, roughness, studio)`: the eye's `td_env` with the studio as parameters. With the eye's constants it
    equals `eye_optics.td_env` (a test);
  - `sh9_project(studio) -> (9, 3)`: 4,096 Fibonacci directions, the cosine bands (π, 2π/3, π/4), divided by π, so a
    Lambert albedo × `sh9(n)` is the diffuse light. LD-0 container: 2.4–3.6 ms [M-C];
  - `sh9_eval`, `srgb_decode` / `srgb_encode`, the tone curves, `lookdev_output`;
  - `frame_uniforms(state, camera)`.
- **When SH9 is recomputed:** only on a studio *content* change (a preset, or an edit of the studio itself), cached
  by that key. The projection costs 10–13 ms on the reference PC (§16.1). Intensity scales it as a uniform
  (`u_ld_env_intensity`), and rotation is a uniform
  (`u_ld_env_rot`, world → studio), applied to the normal and the reflection vector; the lights rotate in Python.
- **Studio space:** fixed to the world. "Licht folgt Kamera" takes the camera's basis, like
  `light_rig.frame_for(SPACE_CAMERA)`.
- **Studio uniforms:** at most 4 rectangles (uniform arrays) + the gradient dome, replacing the eye's compile-time
  constants for the LOOKDEV variant only.
- **What SH9 does not do:** it never makes a visible reflection (cornea, wet film and the skin's sheen use the studio).
  The direct lights are never baked into SH9.

---

## 7. The organic material model and presets — M1 session only [P] (LD-D6, LD-D12)

- **`LookMaterial`:** a frozen, validated dataclass in `src/mirai/lookdev_material.py`, **not** in `src/core/` in M1.
  - Fields: `preset`, `base_color`, `albedo_source` (`texture` | `color`), `roughness` (perceptual, α = r²),
    `specular` (level, F0 = 0.08 · level), `wrap`, `backscatter`, `backscatter_color`.
  - Six presets (proposal §4.1: Creature Skin, Wet Skin, Zähne, Mundinneres, Organisch, Neutral), values `PROVISIONAL`.
- **Session table:** `LookdevRoom.materials: dict[ObjectId, LookMaterial]`.
  - It is dropped on scene load / reset and never written to a file. The panel says "nicht gespeichert".
  - An object deleted in the session loses its row.
  - A duplicate or mirror does **not** carry it in M1, a named limitation that LD-2's Core field removes.
  - The ObjectId-keyed table is acceptable because it is transient: AD-024 §1.2 rejected such a table for
    *persistence*.
- **No Undo** for M1 material and studio changes. They are view / session state; LD-2 makes material changes Undo steps.
- **Fallback** for an object without a row is Neutral. Its albedo is the shown texture or paint composite when the
  object has UVs and one; else `ObjectMaterial.base_color` read as a colour only; else `DEFAULT_BASE_COLOR`
  (`gl_render_store.py:405`). `glossiness` is never read as roughness, nor `specular` as F0 (proposal §4.3).
- **Eyes** are not organic objects. They keep `EyeSpec` and the panel "Auge" (§5).
- **Panel:** `src/gui/lookdev_model.py` (pure, tested headless) + `src/gui/lookdev_panel.py`, one window block in
  `imgui_layer.py` beside the Paint Room's (`:460–470`).
  - About 15 visible controls (proposal §3).
  - A held slider previews, and release commits to the session state.
  - It holds no document state (CLAUDE.md, `src/gui/`).

---

## 8. The background [P] (LD-D9)

- In LookDev, `render()` draws the background as its first step: a full-screen triangle (one empty VAO), depth test and
  depth write off, solid or vertical gradient. The colour is written **as picked**: not exposed, not tone-mapped, not
  encoded.
- In the Worklight, `main.py:715` is untouched (deviation D1, §14).
- The cost is in the LD-0 row `ld frame` (§16).

---

## 9. Performance rules [P] (LD-D10)

- **The Modelling Room loses nothing.** With `shading == "worklight"`, no LookDev program is compiled, no frame dict
  resolved, no UV request set, no SH9 projected.
  - Gate E16: `probe_d3_acceptance.py` and `probe_lookdev.py` (its `worklight` and `app render` rows) within noise of
    their last reference-PC run.
- **Target:** ≥ 30 fps on the reference PC at 1024×768 with the framed Gollum head, still or slow poses.
  - The LD-0 rows `ld frame` give the pass's share. LD-1 measures the room in the app.
  - Deformation is judged qualitatively.
- **Render-only levers** if over budget, in order:
  1. drop the studio specular on skin (`ENV_SPEC` 0, the row `ld no env`);
  2. the "fast" eye tier;
  3. fewer studio rectangles for rough skin.

  The quality manager (LD-3) automates them later. It can never change mesh, SubD, morph, pose, picking or materials.
- **Compile (decided, §15 Q4):** on the reference PC a cold eye-variant compile takes 0.24–0.6 s, and the driver cache
  does not help across processes (§16.1). `open_lookdev` therefore compiles the programs the room will draw first:
  - the eye LOOKDEV variant of the drawn eyes (usually one for both);
  - the skin variants the drawn objects need.

  This happens once per process, before the first LookDev frame, behind the status line "LookDev: Shader werden
  vorbereitet …". Later variants (another object with or without a map) still compile lazily. It is not a per-frame
  cost.

---

## 10. Files LD-1 will touch [P]

| Layer | New | Changed |
|---|---|---|
| Viewport | `src/viewport/lookdev_pass.py` (`LookdevPass`, `LookDraw`), `lookdev_shaders.py`, `lookdev_optics.py` | `viewport.py` (`shading`, `look=` / `set_edit_look`, `_uv_requests` and its hand-over points, the background, the LookDev branch of `render()`); `render_mesh.py` (`set_uvs_requested`, `_uv_wanted`); `gl_render_store.py` (`bind_triangle_uvs` / `unbind_triangle_uvs`, `texture_binding`); `eye_shaders.py` (`lookdev=`, blocks B1–B8 in the body only); `eye_pass.py` (key + 1, `lighting=`) |
| App | `src/mirai/controllers/lookdev_room.py`, `src/mirai/lookdev_material.py`, `src/mirai/lookdev_presets.py` | `application.py` (`open_lookdev` / `close_lookdev` / refusal, setters, the Eye Lab refusal, the Paint Room ↔ LookDev order, close on `init_scene`, the restored display on save); `controllers/objects.py` (`LookDraw` in `sync_views`, no tint in the room) |
| GUI | `src/gui/lookdev_model.py`, `lookdev_panel.py` | `imgui_layer.py` (the window block), `menus.py` (the SPACE row) |
| Tests | see §12 | `tests/test_gl_eye_pass.py`: **only adds** the new pins (E4, C6) and LOOKDEV draw / state tests; existing tests and `PINNED_SOURCES_SHA256` untouched |
| Docs | — | this AD (implementation note), `docs/architecture/README.md`, the proposal's status line, `experiments/drag_cost/README.md` (the LD-1 rows) |
| **Not touched** | | `src/core/`, `core/serialization.py`, `mirai/view_state.py`, `src/main.py`, `config/keymap.json`, `scenes/`, `experiments/lookdev_eye_lab/`, the Eye Lab window, `light_rig` state and presets, `DisplayState`'s Worklight fields, `GLRenderStore.draw()` and the Worklight programs |

---

## 11. Tests that must stay unchanged (gates) [P]

| Gate | What it protects |
|---|---|
| `tests/test_gl_face_data_layout.py`, `tests/test_gl_shading.py`, `tests/test_gl_texture.py` | Worklight pixels, byte for byte (E1) |
| `tests/test_gl_eye_pass.py` — all existing tests incl. `PINNED_SOURCES_SHA256`, `test_preview_off_is_the_worklight_draw`, `test_sclera_reads_like_a_worklight_object_of_its_colour`, the parity and every "draws and leaves the GL state clean" test | eye pass Worklight source and pixels (E2) |
| `experiments/lookdev_eye_lab/tests/test_oracle_production.py` (and the lab's suite) | the frozen oracle (E3); the lab is not touched |
| `tests/test_render_mesh_face_data.py` | the UV resource with the request off everywhere (E12) |
| `tests/test_gl_gpu_picking.py`, `tests/test_gl_morph_picking.py` | picking ignores LookDev (E15) |
| `tests/test_paint_room.py`, `tests/test_eye_lab.py`, `tests/test_view_state.py` | the other rooms and the saved view |
| `tests/test_gui_imgui_window.py` | panels and GL state around imgui |
| `tests/test_main_wiring.py` | `main.py` unchanged in behaviour |

GL tests run in their own process under xvfb (CLAUDE.md "Testing"); scope per AGENTS.md §8a.

---

## 12. New tests for LD-1 [P] (appendix E mapped to files)

| # | Test | File (new unless noted) | Criterion |
|---|---|---|---|
| E4 | Pins: all Worklight sources (C6, from `89f61fc`) and the LOOKDEV variants | `tests/test_gl_eye_pass.py` (added) | digests equal |
| E5 | `lookdev_optics` ↔ `lookdev_shaders`: decode, curves, `sh9`, `ld_studio`, GGX | `tests/test_gl_lookdev_parity.py` | float32 tolerance |
| E5b | `LD_BRDF_SRC` functions are substrings of `EYE_LIB_SRC` | `tests/test_lookdev_shaders.py` | character-identical |
| E6 | SH9 projection vs a numerical integral of the studio; `ld_studio` with the eye's constants = `eye_optics.td_env` | `tests/test_lookdev_optics.py` | ≤ 1 % irradiance; ≤ 1e-6 |
| E7 | Grey card: skin vs sclera in LookDev | `tests/test_gl_lookdev_pass.py` | ≤ 2/255 |
| E8 | Depth contract: wire over the LookDev pass = over the Worklight | `tests/test_gl_lookdev_pass.py` | identical line pixels |
| E9 | R-1 | `tests/test_room_rule.py` | bit-identical state (§2.2) |
| E10 | Display saved / restored; save in the room writes the restored `view.display`; load closes the room | `tests/test_lookdev_room.py` | as the Paint Room tests |
| E11 | Refusals and room order (exclusive session, Eye Lab refused, Paint Room ↔ LookDev incl. P-8) | `tests/test_lookdev_room.py` | status line, no state change |
| E12b | UV request: on → `triangle_uvs` exists, off → today's resources; reaches the SubD and entry surfaces | `tests/test_render_mesh_face_data.py` (added), `tests/test_lookdev_room.py` | resource present / absent |
| E13 | A selected painted head keeps its albedo in LookDev | `tests/test_gl_lookdev_pass.py` | composite drawn |
| E14 | Both passes and the background leave the GL state as found | `tests/test_gl_lookdev_pass.py` | `snapshot_gl_state` pattern |
| E16 | Modelling Room unchanged with LookDev off | `probe_d3_acceptance.py`, `probe_lookdev.py` (reference PC) | within noise |
| — | `lookdev_model` (panel logic) headless | `tests/test_gui_lookdev_model.py` | as `paint_model` tests |

---

## 13. Stop points

1. **Done 2026-11-19:** this AD and the LD-0 probe (container).
2. **Before LD-1 — done 2026-11-19** (AD accepted, reference-PC run §16.1):
   - Manu accepts AD-038, with or without changes to §14 / §15;
   - Manu runs `probe_lookdev.py` on the reference PC (§16). Its `ld frame` rows decide whether M1 ships the full skin
     or starts with a lever.
3. **After LD-1:** Manu's practical test on `scenes/Gollum_Head_05.mirai.json` covers:
   - studio presets, skin preset values, eye ↔ skin coherence;
   - morph and pose in the room;
   - Paint Room ↔ LookDev and R-1;
   - LD-D15 (References / Ghosts).
4. **LD-2** (`SceneObject.look`, format v15, `view.lookdev`): only on Manu's go after the M1 verdict.
5. **Keys:** none until a practical test and "Taste passt" (D-L9).

---

## 14. Deviations from the proposal (with reasons)

| # | Proposal | This AD | Why |
|---|---|---|---|
| D1 | Clear colour behind a getter in `main.py` | Background drawn by the viewport as the first step of `render()` in LookDev; `main.py` untouched | One file fewer; the Worklight path is identical by construction instead of by a proven refactor |
| D2 | Eye LOOKDEV variant without the Worklight uniform names | Names kept, fed with LookDev values; ambient 0 | `EYE_LIB_SRC` declares them in every variant (C5). Editing the library would touch every variant's source. The iris key table follows the LookDev key for free |
| D3 | One library included by both passes | `LD_COMMON_SRC` (both) + `LD_BRDF_SRC` (skin), the latter pinned to the eye's text | GLSL redefinition (C7); the pin keeps "one BRDF, one encode" |
| D4 | UV request set on the entry | Held per key by the viewport, applied at the material hand-over points | The drawn mesh is often a re-created surface (C3) |
| D5 | One accessor for the store | `bind_triangle_uvs` + `texture_binding` | The `LiveTexture` upload is private (C2); not face data |
| D6 | LOOKDEV blocks at five kinds of site | Eight (B1–B8), adding the Worklight plastic highlight and the soft key's camera frame | Both are Worklight-only terms in the body (C4) |
| D7 | Albedos decoded at their three reads | Decoded at the two diffuse entry points `lit` / `iris_lit`; pre-light albedo blends stay as tuned | Every diffuse albedo passes through them; fewer blocks; the visible effect is checked by E7 and the practical test |
| D8 | `PINNED_SOURCES_SHA256` unchanged = Worklight sources unchanged | Plus a pin over all 1,030 Worklight sources, taken before the change | The existing pin does not cover the sclera-map variants (C6) |
| D9 | Teeth as practical-test objects | Noted: hidden in `Gollum_Head_05`; show them for the test | C10 |

---

## 15. Questions for Manu — answered 2026-11-19

Manu: „AD-038 freigegeben, Fragen 2–4 wie vorgeschlagen, Frage 3 würde ich Neutral wählen.“

1. **AD-038:** accepted as it stands, D1–D9 included.
2. **Tone curve:** luminance Reinhard is the M1 default, with "Clamp" as the diagnostic. A filmic shoulder is tried in
   the practical test; changing it needs no architecture change.
3. **Default material on entry:** every object without a session material is **Neutral** until the artist picks a
   preset. Nothing is guessed from object names.
4. **Compile on entry:** yes. The reference PC shows a visible first-use stall, so the room's programs compile on entry
   with a status line (§9).
5. Still open from the proposal and unchanged: LD-D8 (before P3), LD-D15 (in the M1 test), LD-D16 (later).

---

## 16. LD-0: the probe

`experiments/drag_cost/probe_lookdev.py` (+ `tests/test_probe_lookdev.py`, headless). It changes nothing in `src/`. The
UV request and the triangle-UV binding are **stand-ins** built on `RenderMesh` / `GLRenderStore` internals, exactly
the places §4 makes public.

| Item | What it measures |
|---|---|
| (a) | `Gollum_Head_05` as saved (painted head + 2 eyes), cage and SubD 1, framed (¾) and close-up (front, the face filling the frame), 1024×768 and 1920×1080, GL_TIME_ELAPSED. The rows: `worklight` (today's frame without overlays), `wl eyes full`, `ld skin`, `ld frame` (background + stand-in skin + eyes full), `ld no env`, `ld no map`, `ld shadow` (P3: 2048² key depth pass + 16-tap PCF), `app render`. Also the share of the 33.3 ms frame (LD-D10) and the coverage. The stand-in skin is the §3.2 model with the store's own VS + GS |
| (b) | The first UV request on the head (textures hidden, so its UVs are inactive): the `Viewport.sync()` that allocates and fills the UVs, the first draw that uploads them, the request taken back. First cycle and the median, cage and SubD 1 |
| (c) | Render-to-RGBA16F cube faces (128², mips to 2²): completeness of all 42 attachments, the chain's GPU time with 64 / 256 GGX samples, level 0 read back against `eye_optics.td_env`, `textureLod` read back |
| (d) | A 2048² DEPTH_COMPONENT24 texture with compare mode: completeness, texels written, the pixels the PCF lookup darkens (the `ld shadow` row) |
| compile | Eye shell variants (plain, look, look + iris, look + iris + sclera) compiled cold (a comment no driver cache has seen), as shipped, and again; `EyePass.program()` fresh; the skin stand-in's variants on first use |

**Container run** (llvmpipe; a **function check only**, its GPU timer values are not meaningful), 2026-11-19, `89f61fc`:
[`RESULTS_LOOKDEV_CONTAINER_2026-11-19.md`](../../experiments/drag_cost/RESULTS_LOOKDEV_CONTAINER_2026-11-19.md) [M-C]:
- every path runs, with no GL error;
- the depth FBO is complete, and the cube FBO is complete for all 42 attachments;
- the cube's level 0 matches `td_env` within 6e-4 relative (RGBA16F), and `textureLod` reads back exactly;
- the shadow lookup darkens 4–6 k px framed and 43–59 k px close;
- SH9 projection 2.4–3.1 ms;
- the UV request:
  - sync 4.4–6.9 ms (cage, 5,469 triangles) / ≈ 20 ms (SubD 1, 22,153 triangles), almost all of it
    `_triangle_uvs_flat()`, the Python loop that fills the UVs;
  - the first draw after the first request 104–124 ms, later ones 2.7–7.4 ms. This is llvmpipe; the cause of the
    first-cycle cost is not isolated, and the reference PC decides;
  - taking the request back < 0.1 ms;
- cold eye compile 38–68 ms (Mesa).

**Reference PC** (Manu; set NVIDIA "Maximale Leistung bevorzugen" first), from the repository root in `.venv312`:

```
python experiments\drag_cost\probe_lookdev.py | Tee-Object -FilePath lookdev_ld0.txt
```

It runs 1024×768 with every extra, then 1920×1080 with the frame rows, each in its own process (about 2–4 minutes
[E]). The results go into `experiments/drag_cost/RESULTS_LOOKDEV_REFERENCE_PC_<date>.md` from the template
[`RESULTS_LOOKDEV_REFERENCE_PC_TEMPLATE.md`](../../experiments/drag_cost/RESULTS_LOOKDEV_REFERENCE_PC_TEMPLATE.md).

### 16.1 Reference PC (Manu, 2026-11-19) [M-RPC]

[`RESULTS_LOOKDEV_REFERENCE_PC_2026-11-19.md`](../../experiments/drag_cost/RESULTS_LOOKDEV_REFERENCE_PC_2026-11-19.md).
The measured `src/` tree `716ec01d5d` = `db9fbea:src`. GPU p50, ms:

| | 1024×768 framed (cage / SubD 1) | 1024×768 close | 1920×1080 close |
|---|---|---|---|
| `worklight` (today, eyes at the file's tier) | 3.00 / 5.18 | 6.59 / 9.72 | 10.95 / 14.80 |
| `ld frame` (background + skin + eyes full) | **1.68 / 2.21** | 4.59 / 5.26 | 7.96 / 8.85 |
| `ld no env` | 1.19 / 1.50 | 3.15 / 3.55 | 5.35 / 5.85 |

What it decides:
- **LD-D10 met:** the framed head costs 5–7 % of the 33.3 ms frame at 1024×768; the worst case measured is 8.85 ms.
  M1 ships the full skin model, studio specular included. No lever is the default.
- **LookDev is cheaper than the Worklight** in every view, by 1.6–7.2 ms at the same eye tier. The likely cause [H] is
  the Worklight's per-fragment face-data path. Entering the room does not slow the frame. The `worklight` / `app
  render` rows are the E16 baseline.
- **UV request:** a one-time 15 ms (cage) / 61 ms (SubD 1), almost all of it `_triangle_uvs_flat()`. It is set on entry
  with no status line of its own. Vectorising that loop is a later, separate optimisation.
- **Compile:** 0.24–0.6 s per cold eye variant, so the room pre-compiles on entry (§9, §15 Q4).
- **P3:**
  - the GPU prefilter works: a 128² cube chain takes 12 ms (64 samples) against 40 s on the CPU;
  - depth textures and PCF work;
  - the unoptimised shadow stand-in adds 9–11.5 ms. A P3 shadow map renders only on a pose, geometry or key change,
    smaller first.

**What decides what:**

| Row | Decides |
|---|---|
| `ld frame` framed 1024×768 | whether M1 starts with the full skin, or with `ENV_SPEC` 0 (`ld no env`) as the default lever |
| (b) | whether the request can be set on room entry without a status line |
| compile, cold | whether entry pre-compiles (§15 Q4) |
| (c), (d) | P3 only: GPU prefilter vs a machine cache, shadow maps on the 9800 GTX |

---

## 17. Implementation note — LD-1 built (2026-11-19)

Branch `claude/sweet-hamilton-pzimll`, on `main` @ `647d1ac` (`src/` unchanged since `89f61fc`: every file:line of §1
checked against the code before building; no deviation found). **Stop point 3 (§13) is next: Manu's M1 practical test.**

### 17.1 What is built, slice by slice

| # | Commit | What |
|---|---|---|
| 0 | `d27184d` | `PINNED_WORKLIGHT_SOURCES_SHA256` over all 1,030 Worklight eye sources, taken before `eye_shaders.py` changed; value `714a683b…` as §5.4 (C6) |
| 1 | `cd21e61` | §4: `RenderMesh.set_uvs_requested` (+ `uvs_requested`); `Viewport._uv_requests` per key (`EDIT_KEY`, entry keys) handed over at the material hand-over points (new entry, `set_edit_mesh`, the edit object's surface in `_sync_surface`, `_follow_entry`); `GLRenderStore.bind_triangle_uvs` / `unbind_triangle_uvs`, `texture_binding` |
| 2 | `0a1021a` | §5.2 / §6: `lookdev_shaders.py` (`LD_BRDF_SRC`, `LD_COMMON_SRC`, `SKIN_BODY`, `skin_sources`, background), `lookdev_optics.py` (NumPy twins, `Studio`, `EYE_STUDIO`, SH9, `LookdevState`, `frame_uniforms`) |
| 3 | `0dac17b` | §3 / §8: `Viewport.shading` + `set_shading`, `LookdevPass` + `LookDraw` (`lookdev_pass.py`), `set_edit_look`, `set_object_entry(look=)`, the background; `"worklight"` renders today's code (one comparison) |
| 4 | `6708eb5` | §5: the eye's LOOKDEV variant (B1–B8 in the body only), `EyePass.program_key` (9 values), `draw(…, lighting=)`, `variant()`; `prepare_lookdev` helpers in the viewport; E4 pin of the 1,024 LOOKDEV sources |
| 5 | `47406fa` | §2 / §3.3 / §9: `LookdevRoom`, `open_lookdev` / `close_lookdev` / `lookdev_refusal`, room order, Eye Lab refused inside, close on `init_scene`, the restored display on save, LookDraws and no tint in `sync_views`, `AppServices.lookdev`, compile behind the status line; presets as data |
| 6 | `0718967` | §6 / §7 / §15: studio, light and material setters (session only, no Undo), four studios (Portrait default), six materials (Neutral fallback), luminance Reinhard default with Clamp |
| 7 | `fafb59f` | §7: `gui/lookdev_model.py` + `gui/lookdev_panel.py`, the `LookDev` window block in `imgui_layer.py`, the SPACE row „LookDev öffnen / schließen“ (`menus.py`); no key, no keymap entry |
| 8 | `2a4f894` | E7, E8, E13, E14; `probe_lookdev_room.py`; the frame dict cached by (studio, camera basis with „Licht folgt Kamera“) |

Not touched (§10): `src/core/`, `core/serialization.py`, `mirai/view_state.py`, `src/main.py`, `config/keymap.json`,
`scenes/`, `experiments/lookdev_eye_lab/`, the Eye Lab window, `light_rig`, `DisplayState`'s Worklight fields,
`GLRenderStore.draw()` and the Worklight programs. No Core field, no format change, nothing saved.

### 17.2 Where the build differs from the AD text, and why (no architecture decision taken beyond the AD)

| # | AD | Built | Why |
|---|---|---|---|
| I-1 | §5.1 "the cache key grows from 8 to 9 values" (position open) | `lookdev` is value 8 of 9 (index 7), **before** `sclera`, which stays last | the unchangeable eye tests (§11) and `test_gui_imgui_window.py` read `key[-1]` as the sclera flag; appending would have broken 16 of them |
| I-2 | §5.2 `LD_BRDF_SRC` = "copies" of seven functions | cut programmatically from `EYE_LIB_SRC` (`function_src` / `constant_src`); plus `direct_specular` and the constants `PI`, `MIN_DIRECT_ROUGHNESS`, `TD_SIGMA_SCALE`, `TD_SIGMA_POWER` | `ld_specular` and `ld_studio` need them; a cut cannot drift, and E5b still asserts every definition is a substring of `EYE_LIB_SRC` |
| I-3 | §5.3 B6 "GGX `direct_specular` from the LookDev key / fill" | `ld_specular`: `direct_specular` summed over key, fill **and rim**, each light's size widening α — the skin's function | one BRDF for skin and eye; E7 (grey card) is then exact (container: 142/142/142 on both) |
| I-4 | §5.3 B2 "key through the table and fill unchanged" | the same, plus the rim (Lambert) as in `lit` | `iris_lit` falls back to `lit` without a key table; both now see the same three lights |
| I-5 | (not stated) | LOOKDEV without LOOK declares `u_sclera_roughness` (a block in the body's uniforms); fed from `EyeSpec.look.sclera_roughness`, else 0.08 (`DEFAULT_LOOK`) | B6 needs a roughness in every LOOKDEV variant; the uniform existed only under `LOOK` |
| I-6 | (not stated) | the eye's LOOKDEV diffuse is Lambert: `u_key_wrap` / `u_fill_wrap` = 0 in the frame dict, `lit` uses `ld_diffuse(n, 0)` | Neutral has wrap 0; E7 compares like with like. The sclera's own softness is a later eye value, not an organic preset (§7) |
| I-7 | §4.2 "the logic of `_flush_face_data` for one name" | its loop body factored into `_flush_face_buffer(name, fmt, unit)`, called by `_flush_face_data` and `bind_triangle_uvs` | one upload path; the same GL calls in the same order; `draw()` unchanged; §11 texture / shading / face-data gates green |
| I-8 | §4.1 the rule change only | `_sync_material` with **no** material bound also syncs the UV resource | the edit mesh at the default colour has no material; with no request this is today's early return (`_uv_wanted()` False) |
| I-9 | §4.1 key `"edit"` | `EDIT_KEY = ("viewport", "edit")` | entry keys are the host's opaque keys; a tuple cannot clash with a string or an ObjectId |
| I-10 | §9 "before the first LookDev frame, behind the status line" | `open_lookdev` sets the status and `preparing = 2`; the first tick shows one Worklight frame with the status line, the second compiles (`Viewport.prepare_lookdev`) and switches; a viewport without GL switches at once | the status line must be on screen during the stall; the click is handled inside a frame |
| I-11 | §7 material "(selection)" | targets = the selected objects in mode `4` (group leaves), else the edit object; eyes, References, groups left out; a selection of eyes only refuses ("Auge") | an eye keeps `EyeSpec` and its panel (§7); applying silently to the edit object would surprise |
| I-12 | §12 E6 "≤ 1 % irradiance" | the 4,096-direction projection against a dense integral ≤ 1 % (E6); SH9's own band limit against the exact irradiance reported separately: Neutral 1.4 %, Portrait 3.1 %, Soft 2.0 %, Dramatic ≈ 7 % of the environment's largest irradiance (a near-black dome), test bound 8 % | no SH9 meets 1 % against a studio with softboxes; the band limit is a property of SH9 (§6), not of the projection |
| I-13 | (data in slice 6) | `lookdev_presets.py` / `lookdev_material.py` committed with slice 5 | the room needs Portrait and Neutral to open; slice 6 added the setters and their tests |
| I-14 | §7 "a held slider previews, release commits" | preview = commit | M1 has no Undo for these values; a slider of rotation / intensity / exposure changes only uniforms (no SH9 projection) |
| I-15 | (new) | the frame dict is cached in `Viewport.lookdev_frame` | `frame_uniforms` costs ≈ 160 µs of NumPy; resolved again only on a studio change (or a camera move with „Licht folgt Kamera“) |

Observed while testing R-1, **not** caused by a room: `Gollum_Head_05` loads with SubD level 2 and the first
`update_viewport` caps it to 1 (the SubD cap, `preview.py:75`); a morph mix becomes a cage only in that tick. The R-1
test therefore ticks once after building the state, as the app does between two clicks.

### 17.3 Tests (container, 2026-11-19)

GL files each in their own process under xvfb (CLAUDE.md "Testing"):

| Command | Result |
|---|---|
| `xvfb-run -a python -m pytest tests/test_gl_eye_pass.py -q` | 126 passed (incl. both pins, `PINNED_SOURCES_SHA256` untouched) |
| `xvfb-run -a python -m pytest experiments/lookdev_eye_lab/tests -q` | 206 passed (the frozen oracle) |
| `xvfb-run -a python -m pytest tests/test_gl_texture.py tests/test_gl_face_data_layout.py tests/test_gl_shading.py -q` | 45 passed (E1) |
| `xvfb-run -a python -m pytest tests/test_gl_gpu_picking.py tests/test_gl_morph_picking.py -q` | 53 passed (E15) |
| `xvfb-run -a python -m pytest tests/test_gui_imgui_window.py -q` | 18 passed |
| `xvfb-run -a python -m pytest tests/test_gl_lookdev_pass.py -q` | 11 passed (§4 accesses, §3 pass + background, E7, E8, E13, E14) |
| `xvfb-run -a python -m pytest tests/test_gl_lookdev_parity.py -q` | 7 passed (E5) |
| `xvfb-run -a python -m pytest tests/test_gui_lookdev_window.py -q` | 1 passed (the room in the real window) |
| `python -m pytest tests/test_lookdev_shaders.py tests/test_lookdev_optics.py tests/test_lookdev_session.py tests/test_lookdev_room.py tests/test_room_rule.py tests/test_gui_lookdev_model.py tests/test_render_mesh_face_data.py -q` | E5b, E6, E9, E10, E11, E12b, session, panel logic: all passed |
| `xvfb-run -a python -m pytest tests/test_main_wiring.py -q` | **1 skipped** (this container has no EGL; the same before LD-1) — not a pass |

Final tree runs:

| Command | Result |
|---|---|
| `xvfb-run -a python -m pytest tests -q` | 7,826 passed, 8 skipped, 1 failed: `test_scene_menu_local_tmp.py::test_probe_menu_wiring` - **pre-existing**, fails identically on `647d1ac` (before LD-1). `tests/test_interaction_structure.py` (AD-027 E5 (i)) got `_lookdev` in its non-modal field list beside `_paint_room` (the room is a controller, not a session) |
| `xvfb-run -a python -m pytest experiments/morph_lab/tests -q` | 49 passed |
| `xvfb-run -a python -m pytest experiments/drag_cost/tests -q` | 97 passed |

### 17.4 Measurements

Container (llvmpipe, a function check only):
[`RESULTS_LOOKDEV_ROOM_CONTAINER_2026-11-19.md`](../../experiments/drag_cost/RESULTS_LOOKDEV_ROOM_CONTAINER_2026-11-19.md)
— the room opens, 2 programs compile behind the status line (≈ 20 ms on Mesa), nothing compiles in later frames, the
UV request costs nothing on this scene (its paint composite already shows in the Worklight), the Worklight frame after
closing is the one before, no GL error.

**Reference PC** (Manu; NVIDIA „Maximale Leistung bevorzugen“; repository root, `.venv312`), in this order:

```
python experiments\drag_cost\probe_lookdev_room.py | Tee-Object -FilePath lookdev_room_ld1.txt
python experiments\drag_cost\probe_lookdev.py --no-extras | Tee-Object -FilePath lookdev_ld0_after_ld1.txt
python experiments\drag_cost\probe_d3_acceptance.py | Tee-Object -FilePath d3_after_ld1.txt
```

The first gives the room's rows (`modelling` / `lookdev` / `modelling after`, the entry with the cold compile); the
second and third are E16: their `worklight` / `app render` rows and the D3 p95 within noise of the last reference-PC
runs ([LD-0](../../experiments/drag_cost/RESULTS_LOOKDEV_REFERENCE_PC_2026-11-19.md) and the D3 acceptance record).

**Reference PC result (Manu, handed over 2026-11-20) [M-RPC]:**
[`RESULTS_LOOKDEV_ROOM_REFERENCE_PC_2026-11-20.md`](../../experiments/drag_cost/RESULTS_LOOKDEV_ROOM_REFERENCE_PC_2026-11-20.md),
`src/` tree `90a2e01a9e` = `0e2386f:src`.

| `Viewport.render()`, framed, 1024×768, GPU p50 ms | modelling | lookdev | modelling after |
|---|---:|---:|---:|
| cage | 2.99 | **2.42** (7.3 % of 33.3 ms) | 2.99 |
| SubD 1 | 5.20 | **3.28** (9.8 %) | 5.22 |

- **LD-D10 met in the app**, no lever (§9). The room is 0.56 / 1.92 ms cheaper than the Worklight. It costs 0.7 / 1.1 ms
  more than LD-0's stand-in `ld frame`: overlays and the production skin pass. Wall time incl. `glFinish`: 11.6 /
  12.6 ms.
- **Entry:** ≈ 0.15 s the first time in the process — `open_lookdev` 96 ms [H: first imports on Windows], the compile
  of 2 programs 27 ms behind the status line, first frame 29 ms. Again: 1.1 ms + 12 ms.
  - The compile was far below LD-0's cold 0.24–0.6 s per eye variant [H: the NVIDIA disk cache knew these sources].
  - A truly cold entry stays behind the status line; its „(N Shader in X s vorbereitet)“ shows the value in the app.
- **E16 met.**
  - `probe_lookdev.py`: all 16 `worklight` / `app render` values within 0.04 ms of LD-0.
  - `probe_d3_acceptance.py`: within noise of O3 stage 2. Three rows +0.4 … +1.0 ms p50. `pose wire off` +1.7 ms p50,
    all of it in the CPU's `_sync_geometry`, while `pose wire ON` came out 1.2 ms faster there.
  - LD-1 has no change in that per-frame path. The UV request acts in `_sync_material` only.

### 17.5 Checklist for the M1 practical test (`scenes/Gollum_Head_05.mirai.json`)

1. SPACE → „LookDev öffnen“: the status line „LookDev: Shader werden vorbereitet …“ shows for a moment, then the room
   (no visible stall afterwards); SPACE → „LookDev schließen“ brings the display back (mode, wire, regions, eye tier).
2. Studio: the four presets (Neutral Inspection · Portrait · Soft Studio · Dramatic), Drehung, Helligkeit,
   Belichtung, Hintergrund (Solid / Verlauf, colour exactly as picked); „Mehr“: Tonkurve Neutral vs Clamp, „Licht
   folgt Kamera“.
3. Licht: Key / Fill / Rim on/off, Stärke, Richtung, Wärme, Weichheit — the highlights on skin and cornea move together.
4. Material on the head: Creature Skin · Wet Skin · Organisch · Neutral; Textur/Bemalung vs Farbe; Rauheit, Glanz,
   Weichheit, Durchscheinen. The panel says „nicht gespeichert“; a reload forgets it.
5. **Zähne** (C10/D9): show the teeth in the outliner, select them, preset „Zähne“ / „Mundinneres“.
6. Augen: tier „full“ in the room; sclera and skin side by side under the same key (one linear pipeline); cornea
   reflections now show the studio fixed to the world (they no longer turn with the camera).
7. Morph and pose in the room: a morph slider, a pose (jaw), gaze, SubD on/off — the room shows them as they are.
8. Paint Room ↔ LookDev: from the room into the Paint Room at rest (LookDev closes) and back; in a pose the Paint Room
   refuses (P-8) and LookDev stays open; the Eye Lab inside the room is refused („Eye Lab: erst LookDev schließen“).
   R-1: nothing of pose, morph, gaze or SubD changes on any of these switches.
9. Selection: selected objects are not tinted in the room; a selected painted head keeps its paint.
10. LD-D15: References / Ghosts keep the Worklight draw in the room — keep, or give them LookDev too?
11. Save inside the room: the file keeps the display from before the room; nothing of LookDev is in it.

### 17.6 Open for Manu

- LD-D15 (References / Ghosts in the room), LD-D8, LD-D16 — as before (§15.5).
- The preset values (studios, materials) are `PROVISIONAL`: which to retune after the practical test.
  - **Manu, 2026-11-20:** „Die Licht und Materialpresets würde ich tatsächlich erstmal so lassen. Erst mit der
    Möglichkeit, die Werte per Textur/Masken steuern zu können, kann man wahrscheinlich erst richtig einschätzen, wie
    gut die Shader auf einem Gollum Kopf funktionieren? Bisher sieht alles noch nach ‚eingecremter Babypopo‘ aus.“
  - So the M1 values stay unchanged. The skin is judged again once maps steer it (P3 §9.2: roughness / specular,
    normal / detail, translucency).
  - [H, agent] The uniform look has four causes: one roughness and one specular over the whole head; no
    pore- or wrinkle-scale normal detail to break the highlight; no cavity darkening (M1 has no shadows, and SH9 fills
    the creases evenly); the wrap diffuse.
    The first two are exactly the P3 maps; a parameter retune cannot replace them.
  - **Manu, 2026-11-20 (order after M1):** „Regionsmaterialien können noch warten. Material speichern mit Platz für
    Masken. Einen detaillierten Zbrush Gollum habe ich noch nicht, daher denke ich bringen grobe Masken für
    Roughness, Weichheit wahrscheinlich für den Look erstmal mehr als eine Normalmap für Fältchen oder Poren?!“
    - **LD-2** saves the material (`SceneObject.look`, format v15) with a place for masks from the start.
    - The **first masks** are coarse painted UV-space masks for `roughness` (Rauheit) and `wrap` (the material's
      „Weichheit“). They are pulled ahead of the rest of P3.
    - Normal / detail maps wait for a detailed ZBrush sculpt. LD-D8 (region materials) waits as well.
- I-3 / I-4 / I-6 (rim on the eye, Lambert sclera in LookDev) — keep, or give the sclera its own softness later?
- A filmic tone candidate after the Reinhard / Clamp comparison (no architecture change, §15 Q2).
- LD-2 (`SceneObject.look`, format v15, `view.lookdev`) only after the M1 verdict.
