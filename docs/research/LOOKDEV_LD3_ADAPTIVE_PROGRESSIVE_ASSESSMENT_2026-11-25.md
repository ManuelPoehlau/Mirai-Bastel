# LD-3 extension: adaptive quality during interaction and progressive refinement when idle — assessment

**Status:** ASSESSMENT (2026-11-25, English with a German summary; research, no decision, no code change). Asked by
Manu before LD-3 starts: should the quality manager (LD-3) also lower quality during interaction and refine the image
when the artist pauses, as Blender and Marmoset Toolbag do?
**State inspected:** `main` @ `1e5d751` (P3 S9 „Weicher Schatten“ built). No `src/`, `tests/`, Core or scene-format
change in this document.
**Basis:** [proposal §12.3 / §13 LD-3](../design/LOOKDEV_P2_ARCHITECTURE_UX_PROPOSAL_2026-11-19.md),
[AD-038](../architecture/AD-038-LOOKDEV-ROOM-M1.md), [AD-039](../architecture/AD-039-LOOKDEV-P3.md) (§2, §11, §16–§24),
[RENDERING_VISION §7](../design/RENDERING_VISION.md), the reference-PC results in `experiments/drag_cost/` and
`experiments/lookdev_pcss/`, [REFERENCE_HARDWARE](../architecture/REFERENCE_HARDWARE.md).

Evidence tags as in AD-038: **[V]** verified in code at `1e5d751` (file:line), **[M-RPC]** measured on the reference PC,
**[D]** official product documentation (how it was read: §3; URLs: §11), **[E]** estimate, **[P]** proposal, **[O]** open
for Manu.

---

## Kurzfassung (Deutsch)

- **Empfehlung:** Ja, aber als **Teil der LD-3-Architektur**, gebaut in **zwei Scheiben**:
  - **LD-3a:** Quality Manager mit einem neuen **Aktivitätszustand** (Interaktiv → Beruhigen → Ruhe).
    - In Ruhe werden teure Effekte **zeitverzögert eingeschaltet**, ohne Akkumulation.
    - „Weicher Schatten“ (S9) wird damit „nur in Ruhe“ möglich: beim Arbeiten flüssig, beim Hinschauen das gute Bild.
  - **LD-3b:** **echte progressive Verfeinerung**. Mehrere leicht verschobene Frames werden gemittelt:
    - Kantenglättung (heute hat der LookDev-Raum **gar keine**);
    - rauschfreie weiche Schatten.
    - Ist das Bild fertig, zeigt der Viewport nur noch das gespeicherte Bild und rechnet nichts mehr.
- **Was andere tun [D]:**
  - **Blender EEVEE** mittelt im Viewport eine einstellbare Zahl von Samples (Kantenglättung, weiche Schatten) und hört
    dann auf. Jede Änderung startet neu.
  - **Cycles** rechnet progressiv und entrauscht ab einem Start-Sample.
  - **Marmoset** mittelt im Raytracing- und Hybrid-Modus Frames. „Adaptive“ passt die Samples pro Frame an eine
    Ziel-Bildrate an. „Draft“ rendert in halber Auflösung ohne teure Effekte.
  - **Gazebo/OGRE** hat feste Qualitätseinstellungen, zum Beispiel die Schattenkartengröße. Eine Ruhe-Verfeinerung ist
    dort nicht dokumentiert.
- **Für Mirai relevant:**
  - Qualität abhängig von der Interaktion;
  - verzögertes Einschalten teurer Effekte;
  - Akkumulation mit Jitter (Kamera-Subpixel, Schatten-Abtastmuster, optional die Key-Position).
- **Nicht relevant, zu aufwendig:**
  - temporale Reprojektion: braucht Bewegungsvektoren, und Mirai-Figuren verformen sich;
  - Entrauschen: Mirai hat kein Rauschen, das sich zu entrauschen lohnt;
  - Auflösungsskalierung: Mirai ist CPU-gebunden, nicht GPU-gebunden.
- **Wichtigster Baustein, jetzt vorzusehen:** eine **Frame-Signatur**. Das ist ein Schlüssel aus allem, was das Bild
  bestimmt: Kamera, Mesh-Revisionen, Studio, Effekte, Materialien, Augen, Mal-Textur, Qualitätsstufe.
  - Sie erkennt „Ruhe“ und macht alte Akkumulationen ungültig, für alle Quellen einheitlich: Maus, Slider, Morph, Pose,
    später Animation.
  - Sie verwendet das Muster wieder, das die Schattenkarte (`KeyShadow.key`) und der GPU-Picker schon benutzen.
- **Referenz-PC:**
  - Alles nötige ist OpenGL 3.3 Core.
  - Speicher: ca. 12 MiB bei 1024×768, ca. 32 MiB bei 1080p für die Akkumulation, dazu +12 MiB für eine
    2048²-Schattenkarte. Frei sind 240–310 MiB.
  - Das Risiko ist der bekannte Treiberfehler mit FBO-gerenderten Float-Texturen. Er ist beim Cube gemessen; 2D bei
    64² funktioniert im Augen-Pass. Vor LD-3b braucht es deshalb eine Sonde.
- **Bedienung:**
  - Block „Qualität“ mit „Qualität: Auto / Hoch / Mittel / Entwurf“, das ist die Qualität beim Arbeiten;
  - Schalter „In Ruhe verfeinern“, Standard aus;
  - „Ruhe-Qualität: Hoch / Maximal“;
  - eine Statuszeile mit Fortschritt („Verfeinern 24/64“, „Fertig“).
  - „Bild speichern“ nimmt das fertig verfeinerte Bild.

---

## 1. The question, and what "refinement" can mean

Manu's idea, in three states:
- **Interactive:** responsive while orbiting, posing, morphing or dragging a slider.
- **Settling:** quiet for a short, configurable time.
- **Idle / Refine:** more time per image, better shadows and sampling, optional accumulation, stop once converged.

The state is optional and artist-toggleable. Below 30 fps is acceptable in Refine; 30 fps stays the target for
interactive work (Manu, 2026-11-24, for S9: „du kannst auch zu Gunsten besserer Qualität unter 30 Fps in Kauf nehmen“;
2026-11-25: the same, restricted to the idle image).

Five techniques are easily confused. This document keeps them apart:

| # | Technique | What it is | Needs |
|---|---|---|---|
| T1 | **Adaptive quality during interaction** | a cheaper configuration while something moves; full when still | a notion of "moving", configurations |
| T2 | **Progressive sampling / frame accumulation** | the same still image rendered N times with a varying sample (sub-pixel offset, filter rotation, light position), averaged | an accumulation buffer, a jitter sequence, a reset rule |
| T3 | **Temporal accumulation / reprojection** | accumulation *while moving*: last frames warped to the new view by motion vectors, rejected where they disagree | velocity buffers, history rejection, ghosting control |
| T4 | **Denoising** | a filter that turns a noisy low-sample image into a plausible clean one | a noisy estimator (path tracing, stochastic shadows), auxiliary buffers, a denoiser |
| T5 | **Delayed activation** | expensive single-frame effects switched on only after the motion stops | T1's notion of "still", precompiled variants |

---

## 2. Code check: what exists, what is only proposed

### 2.1 Implemented [V], and reusable

| Mechanism | Where | Reuse for |
|---|---|---|
| Effect switches as a frozen value (9 effects incl. `area_diffuse`, `soft_shadow`); dependency + feature resolution | `lookdev_optics.py:77` `LookdevEffects`, `EFFECT_FEATURE`, `effective()` | the quality configurations are *masks over these switches*, not a second switch set |
| Feature report, by function, once per context | `lookdev_features.py` `FeatureReport` ("a plain value, so LD-3 can read it later") | LD-3's capability layer, unchanged |
| Precompile behind a status line (I-10 path) | `application.py:1396` `set_lookdev_effect` → `lookdev_prepare_needed()` → `room.preparing` | precompiling all configuration variants on entry |
| Shadow-map cache by revision key | `lookdev_shadow.py:102` `KeyShadow.key` (`layout_revision`, `content_revision`, model, key dir, resolution) | the frame signature's geometry part; "re-render only on change" is already the pattern |
| Frame-dict cache by state + camera | `viewport.py:636` `lookdev_frame` | the signature's studio part |
| Environment cube rebuilt only on studio change | `lookdev_cube.py` `EnvCube.update` | idle "high" cube as a second cache entry |
| Camera matrices from one place | `lookdev_pass.py:271` and `eye_pass.py:500/527`: both read `store.uniform_data("camera_uniforms")` | sub-pixel jitter on the CPU side: **no shader source change, no pin moves** |
| Capture of the meshes without overlays | `viewport.py:1288–1300` `request_capture` / `read_back_buffer` | "Bild speichern" from the converged image |
| Interaction signals | `application.py:1185` `lookdev_refusal`: `interaction.session`, `_paint_room.stroking`, `_gesture` | early "activity" hints (the signature remains the truth, §5.2) |
| Frame tick with `dt` | `main.py:824` `_tick` → `Application.update_viewport(dt)` (`application.py:6818`) | the settling timer |
| GPU timing in the probes | `experiments/drag_cost/probe_lookdev_room.py` (`GL_TIME_ELAPSED`) | the pattern for LD-3's timer; **`src/` has no timer query yet** (grep: no `GL_TIME_ELAPSED` in `src/`) |

### 2.2 Facts that shape the design [V]

- **The app redraws continuously.** `main.run` calls `pyglet.app.run()` with pyglet's default `interval=1/60`
  (`main.py:834–835`; pyglet 2.1 `EventLoop.run`): every tick calls `on_draw` → `viewport.sync()` + `viewport.render()`
  + gizmo, HUD, triad, ImGui. A still LookDev image is re-rendered at full cost 60 times a second today. "Stop work once
  converged" is a *saving* over today, not only a quality feature.
- **No anti-aliasing in LookDev.** The window is created without multisampling (`main.py:420–426`); AD-038 §9 fixes
  "no FBO, no float target, no MSAA in M1". Silhouette edges, the lids, eyelash-like geometry and specular highlights
  alias. Accumulation with sub-pixel jitter is the cheapest route to anti-aliasing on this hardware.
- **The frame is LDR RGBA8**, written straight into the default framebuffer (AD-038 §9). An HDR target is P4.
- **Overlays are drawn after `viewport.render()`** (`main.py:712–741`). A composite inside the LookDev render step
  leaves gizmo, HUD, triad, ImGui and menus live and untouched.
- **The S9 soft shadow uses fixed 16-tap Vogel spirals** (AD-039 §24.1). Its error against the 32-key area reference is
  a mean of 1.83 / 255. The PCSS assessment's *reference* is itself an accumulation: 32 hard keys over the light's disc.

### 2.3 Only proposed, not built

LD-3 as a whole: the timer, the moving p50, the hysteresis, Auto / Hoch / Mittel / Entwurf, the status readout
(proposal §12.3); RENDERING_VISION §7's runtime adaptation; my 2026-11-25 chat proposal "interaction quality" (F1–F9,
unanswered).

### 2.4 Measured costs that decide the budgets [M-RPC]

| Item | Cost (1024×768, framed / close-up) | Source |
|---|---|---|
| LookDev frame, no P3 | 1.7 / 2.2 ms GPU (cage / SubD 1, framed) | LD-0, AD-038 §16.1 |
| "p3 all" (shadow 1k 3×3, thickness, dual lobe, cube) | 1.7 / 2.3 ms GPU framed | P3-0 run 5 |
| Room wall time | 11.6 / 12.6 ms (mostly CPU) | LD-1 room run |
| Key depth pass alone | 0.5–1.2 ms, 512² to 2048² | P3-0 runs 1–2 |
| Shadow map re-rendered every frame during a drag | +7 to +10 ms GPU, 24–33 ms wall | P3-0 run 2; the cause is open |
| S9 soft shadow (K16c) | +1.4 to +6.1 ms (mean +3.2); 1080p mean +5.1 | `lookdev_pcss/RESULTS_REFERENCE_PC_2026-11-24` |
| S9 cost structure | ALU-bound; the two PCFs +3.9, the search +1.6; 8/16/24 taps cost about the same | the same, diag run |
| S8 area diffuse | +0.13 to +0.45 ms | AD-039 §23.4 |
| Cube prefilter + CPU copy (128², 64 samples) | 12 ms GPU + 17–24 ms CPU, per studio change | P3-0 run 5 |
| Cold compile of a variant | 0.24–0.6 s each (NVIDIA) | LD-0 |
| VRAM free during LookDev rows | 242–311 of 512 MiB | P3-0 runs 2–4 |

**Reading:** a still LookDev frame is cheap on the GPU. The configurations differ by 2–4 ms without S9 and by up to
6–7 ms with it. The real interactive cost is the drag (shadow re-render) and the CPU, which no shader setting reaches.
That is why the quality *budget* belongs to the idle image, and why the interactive configuration matters mainly in
drags and close-ups.

---

## 3. How other applications do it

How the pages were read: `docs.blender.org`, `docs.marmoset.co`, `gazebosim.org` and `ogrecave.github.io` were not
reachable by direct fetch from this container (DNS blocked by the network policy). The statements below come from
search-engine extracts of those **official pages** (URLs in §11). Exact wording should be checked on the live pages
before a claim is quoted elsewhere.

### 3.1 Blender EEVEE

- **T2, accumulation [D]:** the viewport and the render accumulate samples. "Viewport Samples: the number of samples to
  use in the 3D Viewport"; 0 = "the viewport will be resampled continuously". Anti-aliasing is temporal AA over these
  samples ("TAA is sample based so the more samples the more aliasing is reduced").
- **Stop when converged [D]:** when nothing changes the viewport stops at the sample count. Bug reports #65821 / #80871
  describe the failure case: in Walk/Fly the operator re-tags the view every tick, so sampling restarts endlessly.
  - **Lesson for Mirai:** whatever counts as "a change" must be exact, or the image never settles.
- **Soft shadows by accumulation [D]:**
  - Legacy EEVEE (≤ 4.1): "Rays" per light and "Steps" per ray, and "Jittered Shadows: enable jittered shadows on the
    viewport" (always on in the final render).
  - EEVEE Next (4.2+): light jitter "has a high performance cost, since the shadow map cannot be cached" and must be
    re-rendered every sample; it is "not visible by default in the viewport".
  - This is the same trade our `KeyShadow` cache faces (§5.6).
- **T3 [D]:** "Temporal Reprojection: reduces noise while moving the viewport or during animation playback. Can leave
  some ghosting." Reprojection is optional and comes with ghosting.
- **T1:** EEVEE has no separate "interactive tier". The image simply restarts accumulating on every change, so a moving
  view shows the first, un-accumulated sample.

### 3.2 Blender Cycles

- **T2:** "Viewport (Max) Samples", 0 = indefinite; progressive by nature [D].
- **T4:** "Denoise" for the viewport with a "Start Sample" after which denoising begins; OpenImageDenoise default,
  OptiX optional [D].
- **T1 by resolution:** "Pixel Size" renders the viewport at a lower resolution [D]. An older manual describes a "start
  resolution … progressively increase it to the full viewport size" [D, 2.82]; a 2023 change reworked the resolution
  divider during navigation (PR #105581).
- The blue-noise sampling pattern is tuned "to get better quality in the first sample … where the render keeps
  restarting" [D]. The first frame after a change is what the artist sees while working.

### 3.3 Marmoset Toolbag (4 / 5)

- **T2 [D]:** in the Ray Tracing and Hybrid viewport, "Samples" "progressively improves viewport preview quality by
  accumulating frames over time".
- **T1 + T2 combined, "Adaptive" [D]:** it "automatically adjusts the number of accumulated samples per frame while
  trying to maintain the target frame rate. When disabled, only 1 sample is accumulated per frame."
  - The adaptation is not quality *down* but *samples per frame up* while the frame rate allows.
- **T1, Draft Quality [D]:** a viewport mode that "renders at half of the camera's resolution and disables ray-traced
  features, raster screen space effects, and camera post effects". Full Quality renders everything.
- **T4 [D]:** the ray-traced viewport has denoising settings (details not in the extracts). "Upscaling Mode" renders at
  a reduced resolution and upscales with AI.
- **Raster anti-aliasing [D, API reference]:** modes "None" / "4x Temporal".

### 3.4 Gazebo (gz-sim, ogre2) / OGRE

- **Fixed configuration, not adaptive [D]:**
  - shadow texture size per light type, set through the MinimalScene GUI plugin: 512 … 16384, default 2K, "may be a
    lower value, like 8K on less powerful machines". The docs advise one directional light so VRAM does not grow;
  - a configurable anti-aliasing option in MinimalScene;
  - global illumination methods (VCT, CI VCT) that "require hardware that uses OpenGL4", CI VCT only with Vulkan.
- **Not documented** in the pages found: interaction-dependent quality, idle refinement, frame accumulation, render on
  demand. Absence in the extracts is not proof of absence. Gazebo's job (simulation, sensors, a steady frame rate) has
  no "inspect a still frame" moment.
- **Lesson for Mirai:** this is the model Mirai follows today, through the P3 fixed settings and the effect switches.

### 3.5 Summary: who uses what

| | T1 interaction quality | T2 accumulation | T3 reprojection | T4 denoise | T5 delayed activation |
|---|---|---|---|---|---|
| EEVEE | implicit (restart) | **yes**, stops at N | optional, ghosting | no (Next: for ray-traced effects) | jittered shadows viewport opt-in |
| Cycles | pixel size / start resolution | **yes** | no | **yes**, from a start sample | — |
| Toolbag | Draft mode, Adaptive | **yes** (RT / hybrid) | temporal AA (raster) | **yes** (RT) | ray tracing on / off |
| Gazebo / OGRE | — | — | — | — | — (fixed settings) |
| **Mirai: relevant?** | **yes** (drag cost) | **yes** (AA, shadows) | **no** | **no** | **yes** (S9, map size, cube) |

**Why T3 and T4 are out for Mirai:**
- **T3 needs a velocity buffer per pixel.** For a deforming character that means skinned, morphed and SubD positions of
  the previous frame, a second vertex stream through every store, plus history rejection and ghosting control. That is
  a renderer project, and a 9800 GTX shows its ghosting artefacts more than its benefit.
- **T4 only pays where the per-frame estimator is noisy.** Mirai's raster shading is deterministic. The only stochastic
  part T2 would introduce (rotated shadow taps) converges in 16–64 frames without a denoiser, and a quality denoiser
  (OIDN, OptiX) is not available on GL 3.3 at interactive cost.

**Why resolution scaling (Cycles pixel size, Toolbag Draft) is not needed now:** the LookDev frame is 2–9 ms GPU against
a 33 ms frame. The room is CPU-bound (11.6–12.6 ms wall), and half resolution saves GPU only.

---

## 4. Which P3 effects suit which technique

| Effect | T5 delayed activation (single frame) | T2 accumulation (jitter) | Comment |
|---|---|---|---|
| **AA** (none today) | — | **yes: sub-pixel camera jitter** | the largest visible gain; CPU-side projection offset, no shader change (§2.1) |
| S1 key shadow, 3×3 PCF | 2048² map (+16 MiB, pass ≈ 1 ms once) | **yes: rotate / offset the 3×3 per frame** | smoother penumbra, fewer steps at a grazing key |
| S2 eye shadow | — | camera jitter only | a tap rotation needs an eye source change (eye pins): not in the first step |
| S3 dual lobe | — | indirect (AA of highlights) | analytic |
| S4 thickness | 2048² map helps | marginal | one raw-depth fetch |
| S5 cube | 256 samples / 256² cube on settle (event: prefilter + copy ≈ 70–100 ms [E]) | — | an event cost in Refine, never per frame |
| S6 regions, S7 maps | — | indirect (AA of normal-map aliasing) | artist data; never altered (guardrail) |
| S8 area diffuse | — | — | analytic, already exact for the disc |
| **S9 soft shadow** | **on only in Refine** | **yes: rotate both 16-tap spirals per frame → 16·N taps** | the clearest T5 + T2 case (§5.6) |
| Eye tier | `full` already in the room | — | — |

---

## 5. Proposed architecture [P]

### 5.1 One new value: the frame signature

`Viewport.lookdev_signature() -> tuple` is everything the LookDev image depends on, built from values the draw already
reads:
- the camera's view and projection matrices (`camera_uniforms`) and the framebuffer size;
- per drawn `RenderMesh`: `id`, `layout_revision`, `content_revision`, the model matrix (the `KeyShadow.key` tuple);
- `LookdevState` (studio, effects; frozen dataclasses) and the frame dict's key;
- per drawn object its `LookDraw` (frozen), its region slots and its map paths;
- the eye entries' gaze, display and eye-display state;
- the live paint texture's revision (AD-037);
- the resolved quality configuration and the feature report.

It is O(objects), no GL. **Two jobs, one value:**
1. **Activity:** the signature changed this tick → Interactive. It is unchanged for the settling time → Refine.
2. **Invalidation:** any change resets the accumulation (§5.8).

**Why change-driven and not input-driven:** input events miss changes that do not come from the mouse (a ZBrush
re-import poll at `main.py:961`, a later animation clock, a scripted change). They also flag inputs that change nothing
(hovering a panel). The signature covers every source with one rule. The interaction signals of §2.1 only *add* an early
"active" (a held gesture counts as active even on a tick where nothing moved), so a slow drag does not flicker into
Settling.

### 5.2 The activity state

```
          signature changed / gesture held
   ┌──────────────────────────────────────────────┐
   ▼                                              │
Interactive ──quiet──► Settling ──t ≥ wait──► Refine(n) ──n = N──► Converged
   ▲                       │                     │                    │
   └───────────────────────┴─────── change ──────┴────────────────────┘
```

- **Interactive:** the interactive configuration (§5.4), one fresh frame per tick, no accumulation.
- **Settling:** still the interactive configuration. The wait is 0.3 s by default, configurable 0.1–2 s [P].
- **Refine(n):** the idle configuration. Each tick renders one jittered sample and accumulates it (LD-3b). In LD-3a,
  without accumulation, it renders the idle configuration directly.
- **Converged:** no LookDev draw. `viewport.render()` composites the stored image (one textured quad); overlays stay
  live.
- **Refinement off** (the default): the states still exist, but both configurations are the chosen tier. The room
  behaves exactly as today, which the pixel and pin gates prove (§7.1).

### 5.3 Two budgets

| State | Budget | Who decides |
|---|---|---|
| Interactive | **≤ 33.3 ms per frame** (LD-D10); Auto picks the interactive tier from the GPU p50 of the last ~30 interactive frames, with hysteresis | LD-3 timer (GPU time only: the CPU part is not reachable by shaders, §2.4) |
| Refine | **no frame-rate target.** A per-frame **ceiling** (≤ 50 ms [P], so a click or slider move answers within one refine frame) and a **convergence time** (N samples, about 1–3 s) | the idle configuration and N; the ceiling only cuts samples per frame, never quality |

**The latency rule:** an input during Refine waits at most for the refine frame already in flight. The next frame is
interactive. This is why the ceiling exists, and why a refine frame renders one sample, not a batch.

### 5.4 Configurations (masks over `LookdevEffects`, plus resolution knobs)

The effect switches stay the artist's **"allowed"** set (P3 G2). A configuration can only turn an allowed effect off or
raise a resolution. It never turns on an effect the artist switched off, and regions and maps are never touched.

| | Entwurf | Mittel (= today's fixed P3) | Hoch | Maximal (idle only) |
|---|---|---|---|---|
| Shadow | off | 1024², 3×3 | 1024², 3×3 | 2048², 3×3 rotated (T2) |
| Eye shadow, thickness, dual lobe | off | on | on | on |
| Cube | on (cheaper than off, P3-0 run 5) | 128² / 64 | 128² / 64 | 256 samples (event on settle) |
| S8 area diffuse | off | as switched | as switched | as switched |
| S9 soft shadow | off | off | on | on, spirals rotated (T2) |
| AA (T2) | — | — | — | sub-pixel jitter |
| Samples N (LD-3b) | 1 | 1 | 16 | 64 |

- **Interactive tier:** Auto / Hoch / Mittel / Entwurf (the LD-3 control).
- **Idle tier:** Hoch / Maximal. It is used only when „In Ruhe verfeinern“ is on.
- **During a drag:** the interactive tier also freezes the shadow map, or renders it every second frame (my F2). This is
  the measured +7–10 ms.

### 5.5 What accumulation needs (LD-3b, new infrastructure)

1. **Accumulation target:** an RGBA16F 2D texture at framebuffer size in its own FBO, plus an RGBA8 copy of the last
   interactive frame for the crossfade (§5.7).
2. **Feed without redirecting the renderer:** the LookDev step still draws into the back buffer as today. After the
   meshes (before the overlays), `glBlitFramebuffer` / `glCopyTexSubImage2D` copies the frame into a texture, and one
   full-screen pass adds it: `acc = mix(acc, frame, 1/(n+1))`. A composite quad then draws `acc` back.
   - No render target change for the passes, no new store path, no change to picking.
   - Provision: the module takes "a frame texture" as input, so a P4 HDR target can feed it later without a redesign.
3. **Jitter sequence:** a Halton(2,3) sub-pixel offset per sample, added to the projection matrix on the CPU in the one
   place both passes read (`camera_uniforms`), for the LookDev frame only.
   - Picking reads its own camera state at pick time and is never jittered.
4. **Filter rotation:** one uniform per frame for the S1 PCF and the S9 spirals, behind a new define (`ACCUM_JITTER`) in
   the P3 discipline. Off = the earlier source, character for character; every pin stays.
5. **Stop:** at n = N the step only composites. A change resets n = 0.
6. **Capture:** „Bild speichern“ reads the composited converged image. If refinement is running, it waits for
   convergence, with the status line „Bild wird verfeinert …“. [O] F-R5.

### 5.6 S9 in the idle image: two ways

- **(i) PCSS idle-only (T5) with rotated spirals (T2).**
  - Per-frame cost as measured: +1.4 to +6.1 ms, irrelevant in Refine.
  - With 16·N effective taps the residual noise and banding of the fixed spiral go. The method's systematic error
    against the area reference (mean 1.83 / 255) stays.
- **(ii) Jittered key (T2, EEVEE's method).**
  - Each refine sample moves the key to a point on its disc. The map is re-rendered (≈ 1 ms pass, plus the open drag
    stall of +7–10 ms) and looked up hard (3×3).
  - The mean over N samples *is* the 32-key reference of the PCSS assessment. It converges to the correct penumbra,
    contact hardening and terminator, with no PCSS approximation.
  - Cost per sample ≈ 10–12 ms on the reference PC [E from the drag rows], fine in Refine.
  - It needs no shader change at all (the map changes, not the lookup), and it gives the eye's shadow the same quality
    without touching the eye pins.
- **Recommendation:**
  - (i) in LD-3a: it is already built.
  - (ii) as LD-3b's shadow mode, after a reference-PC row compares both against the 32-key reference. (ii) is likely
    the better image at a cost only Refine can pay.

### 5.7 No disruptive jump

The idle configuration differs from the interactive one: S9 appears, the shadow sharpens. To avoid the jump:
- The display crossfades: `shown = mix(last_interactive, acc, min(1, n / F))`, with F = 6–8 frames (≈ 0.1–0.25 s).
- `acc` itself holds only idle samples, so the converged image has no bias from the interactive frame.
- Without LD-3b, LD-3a has a single switch at the end of Settling. That is acceptable for the first slice: EEVEE shows
  the same pop when its jittered samples begin.

### 5.8 Stale frames: the invalidation rule

- **The rule:** the accumulation is valid only for the signature it was started with. Any difference resets it, in the
  same tick, before drawing.
- **Window size:** a resize also reallocates the target.
- **Program set:** a recompile (I-10 path) is in the signature through the configuration, so it resets too.
- **The real risk is an input missing from the signature.** The artist would then look at an old image. Three guards:
  1. **Completeness test:** each input of `_render_lookdev` is mutated in turn, and the signature must change (a
     table-driven test that grows with every new effect, like the pin tests).
  2. **Build rule:** the signature is built next to the draw from the same objects, never from a separate dirty-flag
     list.
  3. **Diagnostics:** a debug toggle compares the converged image against one fresh frame of the same configuration
     after convergence (the T2 mean of a jittered set equals the unjittered frame within AA tolerance away from edges).

### 5.9 Animation and continuous deformation

- A playing animation, a running morph or pose drag, an animated eye gaze or a live paint stroke changes the signature
  every tick. The room stays Interactive: no refinement, no accumulation, and no ghosting by construction.
- When playback stops, the room settles and refines the held frame. This is EEVEE's behaviour without its Walk/Fly bug:
  the bug was a signature (tagging) that changed without the image changing.
- Mirai has no playback yet. The rule above means a future animation system needs nothing new from LD-3, as long as
  its evaluated state reaches the `RenderMesh` revisions, which it must anyway for drawing.

### 5.10 OpenGL 3.3 and the GeForce 9800 GTX

- **Feature level:** core 3.3 covers it all: FBOs, RGBA16F 2D textures, `glBlitFramebuffer`, timer queries
  (`GL_TIME_ELAPSED`, already used in every probe on this card), blending.
- **Feature checks:** they join `lookdev_features` by function: `accum_rgba16f` (attach, complete, render, sample twice
  in two frames and compare).
- **Main risk:** the reference PC samples an *FBO-rendered RGBA16F cube* once and then fails with `GL_OUT_OF_MEMORY`
  (P3-0 runs 3–5). A 2D RGBA16F FBO target at 64² works in the eye pass every frame (`eye_pass.py` key table, AD-038
  C9), but a screen-sized target is unmeasured.
  - The LD-3b probe must render-and-sample a 1024×768 and a 1920×1080 RGBA16F target over hundreds of frames.
  - Fallback if it fails: RGBA8 accumulation with ping-pong and `1/(n+1)` blending in 8 bits, worse for N > 16
    (quantisation), or a CPU-side copy as the cube uses (too slow at screen size).
- **Memory:**

| Item | 1024×768 | 1920×1080 |
|---|---:|---:|
| accumulation RGBA16F | 6.0 MiB | 15.8 MiB |
| frame copy RGBA8 + last interactive RGBA8 | 6.0 MiB | 15.8 MiB |
| 2048² shadow (instead of 1024²) | +12 MiB | +12 MiB |
| 256-sample cube (size unchanged) | 0 | 0 |
| **total** | ≈ 24 MiB | ≈ 44 MiB |

  Free during LookDev: 242–311 MiB [M-RPC], so there is margin. It must still be measured with
  `GL_NVX_gpu_memory_info` as P3-0 did.
- **Per-frame overhead of accumulating:** a copy, one full-screen blend and one composite, ≈ 0.3–0.8 ms at 1024×768 on
  this card [E]. To be measured.
- **Converged cost:** one composite, ≈ 0.2 ms [E], instead of today's 2–9 ms per still frame.
- **Timer queries:** read one or two frames late (a small ring of query objects), never synchronously. A blocking read
  would add the GPU frame to the CPU frame.

### 5.11 The pyglet loop

- **No change to `main.run`.** The 60 Hz redraw stays.
  - Refine renders one sample per tick, Converged composites per tick.
  - The settling timer runs on `update_viewport(dt)`.
  - The state machine lives in the LookDev room (`Application` side), the accumulation in `Viewport` / `LookdevPass`.
- **What changes in practice:** with vsync on (pyglet's default), a 20–30 ms refine frame drops the whole window,
  overlays included, to 30 or 20 fps while refining. That is acceptable for 1–3 s, and it is why the ceiling exists.
- **A move to render-on-demand** (`interval=None` + invalidation) would save more power but touches every overlay,
  ImGui animations and hover. It is **not** recommended for LD-3.

---

## 6. Answers to the seven questions

1. **Part of LD-3 or a later stage?**
   - Part of LD-3's architecture: the activity state, the signature, and the two configurations and budgets.
   - Built as **LD-3a** (manager, timer, tiers, activity state, delayed activation) and **LD-3b** (accumulation). LD-3b
     follows a reference-PC probe and Manu's verdict on LD-3a.
   - Folding the activity state in later would mean redesigning the manager's inputs. Building accumulation now would
     put an unmeasured float-FBO risk on LD-3's critical path.
2. **Smallest implementation with a real benefit:** LD-3a with the idle tier "Hoch".
   - S9 soft shadow only after settling.
   - The shadow map frozen during drags.
   - The interactive tier from Auto.
   - The image is better when looking, the drag is responsive, and the converged frame cost is still today's, because
     there is no accumulation yet.
3. **Reuse:**
   - `LookdevEffects` / `effective()` / `FeatureReport`;
   - the I-10 precompile path;
   - the `KeyShadow` / `EnvCube` / `lookdev_frame` cache keys;
   - `camera_uniforms` as the single jitter point;
   - the capture path;
   - the probe rows and the timer pattern of `probe_lookdev_room.py`;
   - the interaction signals of `lookdev_refusal`;
   - `update_viewport(dt)`.
4. **New for real accumulation:**
   - the accumulation target and its feature check;
   - the copy / blend / composite passes;
   - the Halton jitter on the projection;
   - the `ACCUM_JITTER` define for PCF / S9 rotation (with pins);
   - the crossfade;
   - "converged = composite only";
   - optionally the jittered-key shadow mode.
5. **Risks on the reference PC:**
   - the float-FBO defect at screen size (probe first);
   - the shadow re-render stall (+7–10 ms) for the jittered-key mode;
   - vsync quantisation while refining;
   - the cube's CPU copy (≈ 70–100 ms [E]) at the moment of settling, which needs to be deferred one frame after the
     first refine sample, behind the crossfade;
   - VRAM ≈ 24–44 MiB of 240–310 free.
6. **Controls:** see §8.
7. **Tests and measurements:** see §7.

---

## 7. Tests and reference-PC measurements

### 7.1 Gates (container, headless and xvfb)

- **State machine,** headless with a fake clock: Interactive → Settling → Refine → Converged. A change in any state
  returns to Interactive in the same tick, a held gesture keeps it Interactive, and the wait is configurable.
- **Signature completeness:** a table of every `_render_lookdev` input, each mutated, and the signature must change.
  Unchanged inputs (hover over a panel, a status line) must not change it.
- **Refinement off = today:** the frame is pixel-identical to `1e5d751`. `PINNED_WORKLIGHT_SOURCES_SHA256`,
  `PINNED_LOOKDEV_SOURCES_SHA256` and the skin pins are unchanged, and with `ACCUM_JITTER` off the source is character
  for character the same.
- **Guardrail:** the configuration type holds only render fields. A structural test asserts that it cannot reach mesh,
  SubD, morph, pose, picking or `LookMaterial` values (appendix E20).
- **GL (llvmpipe):**
  - the accumulation of N jittered frames equals the mean of N separately rendered frames (tolerance);
  - converged → zero skin-pass draws per tick (a counter, as `KeyShadow.renders`);
  - a camera nudge resets within one tick;
  - the GL state is restored (no FBO bound across `on_draw` steps, I-4; units unbound);
  - the capture returns the converged image.
- **E16:** the Modelling Room is unchanged, as in every P3 slice.

### 7.2 Reference PC (one probe, extended `probe_lookdev_room.py`)

| Row | Decides |
|---|---|
| interactive tiers (Entwurf / Mittel / Hoch), framed / close, 1024 / 1080 | Auto's thresholds |
| drag with the map frozen vs every frame vs every 2nd | F2 |
| refine frame per idle tier (with S9, with 2048², with jittered key) | the ceiling and N |
| accumulation copy + blend + composite | the overhead (§5.10) |
| **`accum_rgba16f` stability: 600 frames render-then-sample at 1024×768 and 1920×1080** | whether LD-3b is possible as designed |
| time to converge (N = 16 / 64) and converged per-tick GPU | the UX promise |
| VRAM free before / during / after (`GL_NVX_gpu_memory_info`) | memory |
| input latency: an orbit step during a refine frame | the ceiling |
| image: jittered key vs S9 idle vs 32-key reference (`lookdev_pcss/compare.py`) | §5.6 (i) vs (ii) |

---

## 8. Artist-facing controls [P]

Panel block „Qualität“ (LookDev room, below „Effekte“). No keys (D-L9).

| Control | Values | Default |
|---|---|---|
| Qualität (beim Arbeiten) | Auto / Hoch / Mittel / Entwurf | Auto |
| In Ruhe verfeinern | on / off | **off** (Manu: an option, not a forced change) |
| Ruhe-Qualität | Hoch / Maximal (Maximal = LD-3b) | Hoch |
| Wartezeit | 0.1–2 s | 0.3 s |

- **Status line:**
  - „Interaktiv – Mittel (Auto: 14 ms > 12 ms)“;
  - „Verfeinern 24/64“;
  - „Fertig – 64 Samples, 1.6 s“.
  - A small progress tick in the viewport corner while refining.
- **„Bild speichern“** takes the converged image. During refinement it waits, with a status line.
- **Effect switches keep their meaning:** „allowed“. A tooltip on S9 says „aktiv in: Hoch, Maximal“.
- **Storage:** an app setting per machine, not `view.lookdev`. Quality is a property of the PC, not of the scene (F7).

---

## 9. Implement now vs provide for now

| Now (LD-3a) | Provision now, build in LD-3b |
|---|---|
| the frame signature + its completeness test | the accumulation module's interface: "frame texture in, composite out", so the P4 HDR target can feed it |
| the activity state machine and the settling timer | the `ACCUM_JITTER` define slot in the define order (after `SOFT_SHADOW`) |
| interactive / idle configurations as masks; Auto via the GPU timer ring | the `accum_rgba16f` feature name in `FeatureReport` |
| S9 idle-only; the map frozen in drags; precompiling every configuration's variants on entry | the camera-uniform jitter hook (one function, identity in LD-3a) |
| the panel block, status line, app setting | the capture hook "wait for converged" (no-op in LD-3a) |
| refinement off = today, proven by pixels and pins | the probe rows of §7.2 |

---

## 10. Recommended LD-3 scope, and the changes to LD-3's architecture

### 10.1 Changes against proposal §12.3

1. **Add an activity state** (Interactive / Settling / Refine / Converged), driven by a **frame signature** and not by
   input events. §12.3 had only a moving p50 over all frames.
2. **Split the budget:** the 33.3 ms target with Auto applies to the interactive configuration only. The idle
   configuration has a convergence budget and a per-frame ceiling, never a frame-rate target. In §12.3 one Auto served
   both.
3. **Hysteresis only between interactive tiers.** In the still state there is no automatic downgrade, which was §12.3's
   risk of silently changing the image the artist judges.
4. **Configurations are masks over the effect switches** and the existing knobs. No second switch set; regions and maps
   are never touched.
5. **Precompile all variants of both configurations on room entry** (I-10 path). A tier change must not cost a 0.3–0.6 s
   compile.
6. **"Bild speichern" uses the idle configuration** (converged when LD-3b exists).
7. **Storage as a machine setting.**
8. **Accumulation (LD-3b)** as its own slice after the `accum_rgba16f` probe; T3 (reprojection) and T4 (denoising) are
   excluded explicitly.

### 10.2 Order

- **LD-3a:** AD → build → reference-PC run (§7.2 rows without accumulation) → Manu's practical test.
- **LD-3b probe:** the `accum_rgba16f` stability and overhead rows, plus the jittered-key image comparison, in
  `experiments/`, no `src/`.
- **LD-3b:** only on a passing probe and Manu's go.

### 10.3 Open questions for Manu [O]

- **F-R1:** extend LD-3 as in §10.1 (activity state, two budgets, LD-3a / LD-3b)?
- **F-R2:** „In Ruhe verfeinern“ default off (as asked) — or on once your practical test likes it?
- **F-R3:** S9 in the idle image: (i) PCSS idle-only now, (ii) the jittered key as LD-3b's candidate (§5.6)?
- **F-R4:** the waiting time 0.3 s default and a crossfade of about 0.2 s — or an immediate switch?
- **F-R5:** „Bild speichern“ waits for the converged image?
- The open chat questions F1–F9 (2026-11-25) are largely answered by this design:
  - F1 → §5.2;
  - F3 → §5.4;
  - F5 → §10.1 point 5;
  - F6 → point 6;
  - F7 → point 7.
- F2 (drag shadow: freeze or half rate) stays open for the probe.

---

## 11. Sources

Official documentation, read through search-engine extracts (direct fetch blocked in this container, §3):

- Blender Manual — EEVEE Sampling (latest / 4.4):
  <https://docs.blender.org/manual/en/latest/render/eevee/render_settings/sampling.html>,
  <https://docs.blender.org/manual/en/4.4/render/eevee/render_settings/sampling.html>
- Blender Manual — EEVEE Light Settings (latest, jittered shadows / resolution limit):
  <https://docs.blender.org/manual/en/latest/render/eevee/light_settings.html>
- Blender Manual — EEVEE Shadows (4.1): <https://docs.blender.org/manual/en/4.1/render/eevee/render_settings/shadows.html>
- Blender Manual — Cycles Sampling (latest): <https://docs.blender.org/manual/en/latest/render/cycles/render_settings/sampling.html>
- Blender Manual — Cycles Performance (latest / 3.6 / 2.82 de):
  <https://docs.blender.org/manual/en/latest/render/cycles/render_settings/performance.html>,
  <https://docs.blender.org/manual/en/3.6/render/cycles/render_settings/performance.html>,
  <https://docs.blender.org/manual/de/2.82/render/cycles/render_settings/performance.html>
- Blender issues on viewport sampling restarts: <https://projects.blender.org/blender/blender/issues/65821>,
  <https://projects.blender.org/blender/blender/issues/80871>; resolution divider change:
  <https://projects.blender.org/blender/blender/pulls/105581>
- Marmoset Toolbag Documentation — Render Window: <https://docs.marmoset.co/docs/render-object/>; Viewports:
  <https://docs.marmoset.co/docs/viewports/>; mset API reference (AA modes): <https://www.marmoset.co/python/reference3.html>
- Gazebo Sim — Shadow Texture Size: <https://gazebosim.org/api/sim/9/shadow_texture_size.html>; Global Illumination:
  <https://gazebosim.org/api/sim/9/global_illumination.html>; Gazebo GUI MinimalScene:
  <https://gazebosim.org/api/gui/10/classplugins_1_1MinimalScene.html>
- OGRE Manual — Shadows: <https://ogrecave.github.io/ogre/api/13/_shadows.html>
