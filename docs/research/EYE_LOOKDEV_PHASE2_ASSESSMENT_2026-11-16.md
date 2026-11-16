# Eye LookDev, next phase: assessment of architecture, visual quality, and Viewport vs. Eye Lab

**Status:** Discovery (2026-11-16, English with a German summary): research and architecture assessment, **no decision,
no code change**. Filed after Manu approved the assessment as a document; every implementation phase in §G needs its
own go, and the decisions in §I are Manu's and are not made here.
**Since then (2026-11-16, later):** E-4 is measured and phases 0, 1, 2 and 3 are built - see the
[addendum](#addendum-2026-11-16-later-e-4-measured-phases-0-and-1-built) at the end, which corrects two statements of
§A and §F, and the [phase 3 addendum](#addendum-2026-11-16-latest-phase-3-built).
**Baseline:** branch `claude/relaxed-brown-pf8ybr` @ `dd3c44b`.
**Sources:** [AD-033](../architecture/AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md),
[Lookdev P0 audit](LOOKDEV_P0_CODEBASE_AUDIT_2026-11-13.md),
[eye lab README](../../experiments/lookdev_eye_lab/README.md) and its reference-PC results,
[REFERENCE_HARDWARE](../architecture/REFERENCE_HARDWARE.md), [RENDERING_VISION](../design/RENDERING_VISION.md), and the
code under `src/viewport/eye_*.py`, `src/mirai/eye_*.py`, `src/gui/eye_*.py`, `src/mirai/controllers/morph.py`.

## Context

AD-033 put a parametric eye (refracting cornea, iris image, soft limbus) into the normal Worklight view, and the gaze
followed on 2026-11-16. Three things now block the next step: the iris reads flat and the reflections read like
polished glass; the eye panel is growing into a rendering control surface inside the modelling UI; and the eyes are
missing beside a morph target while it is edited. This document says what exists, what causes each problem, and
in which order to solve them on the one machine there is.

Evidence labels: **[V]** verified in code or by a read-only run today · **[RPC]** measured on the reference PC (results
files in the repo) · **[C]** measured today in this container (not a hardware number) · **[E]** estimate ·
**[P]** proposal or hypothesis.

## Kurzfassung für Manu (Deutsch)

- **Morph-Ziel ohne Augen:** bestätigt. Die Ansicht des Ziels steht neben der Basis, die Augen bleiben bei der Basis.
  Lösung: reine Anzeige-Zwillinge der Augen neben dem Ziel (kein Szenenobjekt, nicht wählbar, nicht gespeichert).
- **Iris flach:** die Tiefe ist geometrisch schon richtig (Iris 3,5 mm hinter der Hornhaut, echte Brechung). Flach
  wirkt sie, weil sie nur gleichmäßig matt beleuchtet wird: kein Relief, kein Lichtfleck durch die Hornhaut, kein
  Schatten vom Rand. Das ist Shader-Arbeit, keine neue Geometrie.
- **Reflexe zu glatt:** die Hornhaut ist eine perfekte Kugel mit überall gleicher Rauheit, das Studio hat zwei saubere
  Rechtecke, und die Lederhaut spiegelt das Studio gar nicht. Größter Gewinn: nasse Lederhaut, leichte
  Unregelmäßigkeit in der Hornhaut-Normalen, dunkles Lid-Band in der Spiegelung.
- **Viewport gegen Eye Lab:** ein Augen-System, zwei Oberflächen. Im Viewport bleiben wenige Regler (Augen an/aus,
  Vorschau, Blick, Pupille, Look-Vorlage). Alles andere geht in ein Eye-Lab-Fenster in derselben App.
- **Leistung:** die Kosten der Augen im echten Kopf sind auf deinem PC noch nicht gemessen (E-4 offen).
- **Deine Entscheidungen:** §I.

---

## A. Current-state assessment

### A.1 Implemented and verified

| Area | State | Evidence |
|---|---|---|
| Eye object | `SceneObject.eye: EyeSpec` (17 fields), format v9, generated shell (3 392 faces), Undo (`ObjectEyeCommand`), duplicate, X / Y mirror copy, component editing refused | [V] `src/core/scene.py`, `src/mirai/eye_object.py`, `controllers/objects.py`; tests in `tests/test_eye_object.py`, `test_application_eye.py` |
| Eye pass | one draw per eye on the store's VertexList, cornea / sclera split per triangle, analytic refraction V2 / V3 to an analytic iris cone, limbus L0–L3 with fast path, radial iris fit, Worklight-matched diffuse | [V] `src/viewport/eye_pass.py`, `eye_shaders.py`, `eye_optics.py`; container tests per AD-033 §11 |
| Reflection | GGX key highlight plus an analytic two-light studio in view space, or key only | [V] `eye_shaders.cornea_reflection` |
| Lab as oracle | `experiments/lookdev_eye_lab/` frozen; production twins compared bit for bit or within 1e-12 | [V] AD-033 §8, `test_oracle_production.py` |
| Gaze | rest / camera / mouse / target, view state, clamped to 50° | [V] `src/mirai/eye_gaze.py` (commit `dd3c44b`) |
| In use | `scenes/Gollum_Head_03.mirai.json`: two eyes, an X mirror pair, L3, image colour source, asymmetry, pupil 0.11, the head mesh with 8 point layers | [V] scene file |

### A.2 Implemented but provisional

- **Cost in the real modelling scene is unmeasured.** AD-033 phase E-4 is open: `experiments/drag_cost/probe_eye_preview.py`
  exists, no results file does [V].
- **Every artist verdict is open** (P1 techniques, V2 vs V3, limbus L0–L3, colour source, asymmetry) [V, eye lab README].
- **Gaze** is one day old and marked `PROVISIONAL`; not saved, pick caches do not follow it [V].
- **Defaults do not match use.** `DEFAULT_EYE` is L0 with a planar procedural iris; the Gollum scene uses L3, overlap
  0.41, asymmetry, image colour [V]. A new eye is not the "good result by default" the viewport should give.
- **The panel "Auge" already holds about 20 controls** (preview, V2 / V3, studio / key, four gaze modes, pad, focus,
  limbus level, colour source, limbal colour, asymmetry, six sliders, image path) [V, `src/gui/eye_panel.py`].

### A.3 Why it looks the way it does (limitations, all [V] in `eye_shaders.py` unless noted)

1. **Flat iris.** The iris is shaded as `albedo × worklight_light(cone normal)`: plain wrapped Lambert on a smooth
   cone. There is no relief, no light concentrated by the cornea, no shadow from the scleral rim. The geometric depth
   is already there and correct: the iris plane sits 0.295 eye units (3.5 mm) behind the corneal apex and every
   fragment traces a refracted ray to it.
2. **Flat, hard pupil.** `ri < u_pupil_radius` is a per-pixel step to a constant near-black. No soft edge, no margin
   darkening, and no anti-aliasing: the window requests no MSAA [V, no sample config in `src/`].
3. **Polished-glass cornea.** The reflection normal is the exact analytic sphere normal, `CORNEA_ROUGHNESS` is the
   constant 0.04 everywhere, and the studio is two clean rectangles on a gradient.
4. **Two competing highlights.** In studio mode the cornea adds a point-light GGX highlight from the Worklight key
   *and* the studio softbox. A point light at roughness 0.04 gives a hot spot of roughly 0.6° [C, from the shader's
   lobe fit `TD_SIGMA_SCALE` / `TD_SIGMA_POWER`, which was fitted for the studio, so approximate here]; real eyes
   reflect area sources.
5. **Dry sclera.** The sclera gets the Worklight's Blinn–Phong only. The studio reflection stops at the limbus, so the
   wet film ends there.
6. **Nothing of the head reaches the eye.** No lid shadow on the eyeball, no dark lid / lash band in the reflection.
   The eye is lit as if it floated free.
7. **Sclera is one colour.** No veins, no colour drift toward the corners.

### A.4 Housekeeping findings

- **The Gollum scene's iris path points into the lab's git-ignored output folder**
  (`experiments\lookdev_eye_lab\out\iris_custom.png`, absolute) [V]. The production scene depends on a file that
  version control does not hold and that the frozen lab owns.
- **AD-033 §7 quotes the cube-map rows (T-C); production draws the analytic studio (T-D), which costs about twice as
  much per pixel in the lab** [RPC]. The nearest lab rows for today's reflection are T-D: L0 1.9 / 4.4 ms, L3 2.9–3.0 /
  6.1–6.5 ms at 1024×768 / 1920×1080 with the eye at about half the frame. Production's sclera is cheaper than the
  lab's, so the true number is somewhere below; only E-4 gives it.
- **`eye_uniforms()` runs for every eye on every drawn frame and costs 0.46 ms each in the container** [C]; half of it
  is `EyeGeometry.angle`, an 80-step bisection evaluated twice. With the documented 2–3× factor for small NumPy calls
  on the Q9550 that is about 1–1.4 ms per eye per frame [E]: more than the GPU cost of a small eye. Caching per
  anatomy removes it.
- **Sliders apply on release** (one Undo step) and show nothing while dragged [V]. Fine for a modelling panel,
  unusable for look development.
- **Manu's iris image is already unrefracted** (the "unrefracted" iris from François et al. 2009, per the archived
  handoff) [V], so today's asset does not have the double-refraction problem of §C.3.

---

## B. Viewport vs. Eye Lab

**Principle.** One eye object, one material record, one pass, one shader library. The two environments differ only in
which values they show and in view state (framing, isolation, quality tier). Nothing is implemented twice.

**Form of the Eye Lab (recommendation).** A dedicated window inside the production app (imgui, AD-030) that drives the
same viewport: it frames one eye, can isolate the eyes with or without the head, raises the quality tier while open and
shows every value with live preview. Not a second GL context, not a second renderer.
- A *room* with its own lighting and background is the later form, once the full Lookdev mode (D-L6) is decided; the
  window grows into it without rework.
- A *standalone experiment* is not recommended: `experiments/lookdev_eye_lab/` is the frozen oracle and AD-033 §8 puts
  new eye work in production. The remaining uncertainty is artistic (does it look right), not technical, and settings
  that default to neutral answer that in the product.

| Feature | Location | Reason | Underlying system |
|---|---|---|---|
| Show / hide all eyes | Viewport | needed while modelling lids and sockets | shared; new view-state flag [P] (per-object Hide exists, with Undo) |
| Add eye, move / rotate / scale, mirror pair | Viewport | object workflow, exists | shared, exists |
| Preview on / off, quality "fast / full" | Viewport, one control | cost control without optics vocabulary | shared `EyeDisplay` view state; tier is new [P] |
| Gaze: mode, pad | Viewport | acting and checking lids against the eye | shared, exists |
| Gaze focus distance | Eye Lab (viewport keeps the default) | rarely changed | shared, exists |
| Pupil size | Viewport | expressive, one slider | shared `EyeSpec.pupil_radius` |
| Look preset (pick one) | Viewport | "good by default" without parameters | shared: a preset is a bundle of `EyeSpec` values [P] |
| Iris tint | Viewport, if Manu wants a colour control there | fast character colour choice | shared; new value [P] |
| Open in Eye Lab | Viewport button | the bridge | — |
| Anatomy: cornea and limbus radius, iris depth, concavity | Eye Lab | changes the shell; rare | shared `EyeSpec` (not in any panel today) |
| Limbus: level, band, strength, normal transition, falloff, overlap, asymmetry, colour source, limbal colour | Eye Lab | optics vocabulary | shared, exists; moves out of the panel "Auge" |
| Refraction V2 / V3, reflection studio / key | Eye Lab | technical comparison | shared view state, exists |
| Iris image import, interactive fit, de-refraction, relief from image | Eye Lab | a one-time authoring job | shared; replaces the JSON sidecar [P] |
| Iris relief, fibre detail, caustic, limbal shadow, pupil edge | Eye Lab | look development | shared; new look values [P] |
| Cornea irregularity, tear film, roughness; sclera wetness, veins | Eye Lab | look development | shared; new look values [P] |
| Lid shadow and lid band in the reflection | Eye Lab | set once per character | shared; new look values [P] |
| Studio lights (position, size, count) | Eye Lab | lighting for look development | shared view state [P]; saved or not is a decision |
| Save look as preset, copy to the other eye | Eye Lab authors, viewport applies | reuse across characters | shared [P] |
| Close-up framing, isolate eyes | Eye Lab | workspace behaviour | view state only [P] |

The compact panel "Auge" ends with about seven controls instead of twenty.

---

## C. Visual improvement roadmap

Ranked by benefit for believable Gollum eyes against cost. Impact and Gollum columns are my judgement from the code and
from your description of the stills; I have not seen the stills, so the ranking of the top four is yours to confirm.

| # | Improvement | Visual impact | Complexity | GPU cost at close-up [E] | Gollum |
|---|---|---|---|---|---|
| 1 | **Wet sclera**: the studio reflection continues over the sclera under a slightly rougher wet coat, one film across the limbus | high | low (reuses `cornea_reflection`) | brings production to about the lab's T-D rows | high |
| 2 | **Cornea / tear-film irregularity**: a small generated, mip-mapped noise texture tilts the *reflection* normal by 0.2–1°; roughness varies 0.03–0.07 with it | high (this is the "organic reflection") | low–medium | +0.1–0.2 ms | high |
| 3 | **Lid in the eye**: a soft lid shadow on the eyeball and a dark lid / lash band in the reflection, both defined in the eye's rest frame so they stay with the head when the gaze moves | high (the eye sits in the head) | low (arithmetic only) | negligible | high |
| 4 | **Iris light**: key light refracted through the cornea, the bright crescent opposite the highlight, a soft shadow under the scleral rim | high (depth and "alive") | medium (analytic, needs twins and parity cases) | +0.05–0.1 ms | high |
| 5 | **Iris relief**: a height channel in the iris texture's alpha, normal from it, applied to the main iris sample only | medium–high | medium | +0.1–0.3 ms | medium–high |
| 6 | **One coherent highlight**: soften or drop the point-light hot spot in studio mode, or tie the softbox to the Worklight key | medium | low | none | medium |
| 7 | **Pupil**: analytic soft edge (also anti-aliases it), darker margin | medium | low | negligible | medium |
| 8 | **Richer studio**: window bars, a bounce card, more sources | medium | low today, but each analytic light costs per pixel; cheap after #11 | per light | medium |
| 9 | **Sclera detail**: veins and colour drift, generated or painted | medium | medium (second texture or generator) | +0.1 ms | medium (bloodshot periphery) |
| 10 | **Iris image workflow** (§C.3) | enabler | medium (tooling, no shader change) | none | depends on the chosen source |
| 11 | **Studio baked to a small cube on the GPU** when it changes | none by itself; halves reflection cost and makes #8 free | medium; rendering into an RGBA16F cube face is untested on this driver | −30 to −50 % of the reflection cost [RPC ratio T-C : T-D] | enabler |
| 12 | Iris height field by ray march (parallax occlusion, 8 steps) | medium, over #4 + #5 small | medium–high | +0.8–1.5 ms | low; full tier only, later |
| — | V3 refraction | none visible (≤ 1.75 px against V2 [RPC]) | exists | +0.3–0.6 ms [RPC] | none |

### C.1 Iris and pupil: findings

- **Geometry vs. analytic shading.** Real geometric depth exists already and is better than parallax mapping, because
  the ray is refracted per pixel. Extra iris geometry cannot be drawn through the analytic cornea at all (the pass has
  no iris mesh). The flatness is a shading gap; #4 and #5 close it.
- **Is an iris normal map enough?** For real time, yes, together with #4. Relief alone makes fibres catch the key;
  the refracted light and the crescent give the bowl its depth. Store *height* rather than a normal: it packs into the
  alpha channel the pass ignores today (no extra texture unit), one image stays the single iris asset, and the
  procedural generator can emit albedo and height that agree.
- **Pupil depth** is perceptual: a soft, slightly darkened margin and correct parallax. A modelled pupil tunnel adds
  little behind a refracting cornea. Pupil shape stays round (Gollum's is); a shape value can come later.
- **Pupil size and the texture.** With a radial fit the image's pupil edge already follows the geometric pupil [V], so
  the iris stretches as a real one does. The procedural iris is rebuilt per anatomy [V].

### C.2 Cornea and reflections: findings

- **Roughness, reflection size and wetness** [C, from the shader's own lobe fit]: roughness 0.03 → 0.4° blur, 0.04 →
  0.6°, 0.06 → 1.0°, 0.08 → 1.5°, 0.10 → 2.1°, 0.15 → 3.5°. The softbox edge is 0.5°. Wet reads below roughly 1.5°;
  above 0.10 the surface starts to read dry. So organic variation must come from the **normal**, not from more
  roughness.
- **Why a small tilt is enough.** A reflection moves by twice the tilt. Tilts of 0.3–1° bend a softbox edge by 0.6–2°
  against its 0.5° sharpness: clearly irregular, still glossy.
- **Texture, not in-shader noise.** A generated 256² two-channel noise texture with mip maps band-limits itself with
  distance. That matters because there is no MSAA: in-shader noise would shimmer while orbiting. It is deterministic
  data, so the NumPy parity discipline holds.
- **Only the reflection normal is perturbed.** Perturbing the refraction would make the iris swim.
- **Per-eye variation.** Both eyes would otherwise show the identical irregularity; the look needs a seed, and a
  mirror copy should flip it.
- **Tear meniscus at the lid margin** needs the lid geometry. It belongs to the head's material work, not to this
  phase.

### C.3 Photographic iris textures and double refraction

A photo taken through a cornea carries four baked effects. Ranked by damage:

1. **Baked highlights** (catchlights that do not move): the worst, and no remap removes them. They need retouching,
   or a cross-polarised source.
2. **Baked lighting** (crescent, lid shadow): doubles with #3 and #4 once those exist.
3. **A baked limbal ring**: doubles with the shader limbus. The existing `colour_source` setting already chooses the
   owner [V].
4. **Baked refraction** (the geometric part). Computed with Mirai's own ray model for a frontal view [C]: the cornea
   magnifies the pupil edge by 1.14 and the outer visible iris by 1.06. Used naively the error would be that size
   again. But **the existing radial fit pins the pupil edge and the iris edge**, and the residual between them is at
   most 1.5 % of the iris radius (0.1 mm). The fit already removes almost all of the geometric double refraction for a
   frontal photo.

Workflow [P], all in the Eye Lab at import, none of it at run time:
- The artist states the source: *frontal photo*, or *flat / unrefracted / painted*.
- Frontal photo: set the two landmarks interactively (replacing the hand-written JSON), optionally bake the exact
  inverse radial remap from `eye_optics.trace` into a corrected copy, and derive a height channel from the image.
- The corrected image is written beside the scene, so the scene no longer points into the lab's output folder.
- An off-axis photo is not radially symmetric and cannot be corrected this way; the tool should say so.

**Photo vs. procedural.** Neither wins by default. A photo brings real pattern but also baked light, a fixed pupil,
unknown rights and no matching height. A procedural iris gives free colour control (Gollum's pale iris), consistent
albedo and height, and no baked light, but today's generator is simple. A photo for albedo with a derived height is
the hybrid. Which direction to invest in is §I.

### C.4 Not recommended now

Transparent shells, screen-space reflections, shadow maps for the eye, subsurface sclera, HDRI loading (a file format
and likely a dependency), tessellation, anything above OpenGL 3.3, V3 as a default.

---

## D. Architecture recommendation

```
Core (document, Undo, file)       SceneObject.eye : EyeSpec   (+ nested look values [P], format v10)
                                  SceneObject.texture         (iris image: albedo, height in alpha [P])
        │ Application.set_eye / set_eye_iris_image (exist) · preview_eye (transient, new [P])
App (view state, not saved)       DisplayState: preview, tier, gaze, eyes visible, lab view
        │ ObjectController.sync_views → EyeDraw per drawn eye (+ morph-view twins, §E)
Viewport                          EyePass: one program family, one shader library, NumPy twins
        ▲                                   ▲
Panel "Auge" (compact)            Eye Lab window (everything, live preview, framing)
```

- **The existing `EyeSpec` and pass support this cleanly.** Both UIs already go through `Application.set_eye` and
  `set_eye_display`; save, load, duplicate, mirror and Undo work on the spec and need nothing new.
- **Change 1: where new look values live.** Recommendation: one nested, optional group inside `EyeSpec` (iris, cornea,
  sclera, lid values), `None` meaning neutral. Files without it stay v9; v10 is written only when a look is set (the
  existing "version by content" rule). This is a Core change and a stop point like Q-E2. A shared look *asset*
  referenced by several eyes is not recommended: it adds a new document entity and cross-object Undo; multi-select
  already writes one change to all selected eyes [V].
- **Change 2: live preview.** A transient per-eye override held by the object controller and used when `EyeDraw` is
  built; the slider previews through it and commits one Undo step on release, as today. No Core change.
- **Change 3: quality tier.** One view-state value ("fast" drops the optional terms). The Eye Lab window sets "full"
  while open. Per-eye level of detail is unnecessary: cost follows covered pixels and the noise fades through its mips.
- **Change 4: presets.** A look preset is a file holding `EyeSpec` values; applying it is one `set_eye` call and one
  Undo step. The viewport lists them, the Eye Lab saves them.
- **Rule for every new shading term:** neutral at amount 0, so the default path and the oracle tests stay
  bit-identical; a NumPy twin in `eye_optics` and a GPU parity case, as today. The frozen lab has no counterpart for
  new terms; the production twins are their reference.
- **Variant discipline.** There are 32 program variants today (refraction × limbus × reflection × fit) [V]. New terms
  should be uniforms plus one tier define, not more defines. First-use compile time on the NVIDIA Cg compiler is
  unmeasured.

---

## E. Morph target editing: eye visibility

**Cause [V].** `MorphController.edit_target` adds a transient view object beside the base, shifted along world +X by
1.25 × the base's width, and makes it the edit object. Eyes are independent scene objects and stay where they are, at
the base. Reproduced headless today: view at x = 2.5, eye entry still at x = 0. In Base and Mix editing nothing is
wrong: the eyes are at the base, rigid, and the lids move against them.

**Options.**

| Option | Verdict |
|---|---|
| Copy the eyes as transient scene objects next to the view | Rejected: they become selectable, appear in the outliner, double the gaze set, and must be filtered from save and mirror pairs |
| Parent eyes to the head and let the view inherit them | Not available: no mesh-to-mesh parenting exists; bone parenting is AD-028, later |
| Merge or reference the eye in the view mesh | Rejected: the eye would enter the morph mesh, exactly the dependency to avoid |
| **Viewport-only twin entries** | **Recommended** |
| Edit the target in place instead of beside the base | Makes the problem disappear for every companion object, but reverses J-5 ("daneben", 2026-10-17): Manu's call, §I |

**Recommended design [P].** While an editing view is open, `ObjectController.sync_views` adds one extra viewport entry
per drawn eye:
- key `("morph_view", eye id)`, the eye's own mesh and `EyeDraw`, model matrix = the eye's drawn matrix translated by
  the view's shift (`MorphController.view_shift`, already computed for the camera pan);
- no scene object, no pick cache, no outliner row, nothing in the file (`document_scene` is untouched), no Undo;
- removed by the same loop that removes stale entries, when the view closes by Tab, Undo or a scene load.

Behaviour:
- **Picking and selection.** The twin cannot be picked or selected; component picking on the view mesh is unchanged.
  Whether real eyes at the base occlude hover on socket vertices today was not checked; the twin should match that
  behaviour, to be verified when built.
- **Gaze.** The twin aims from its own shifted centre, so in camera and mouse mode both sets look at the same point.
- **Symmetry and mirror pairs.** Untouched: twins exist only in the viewport.
- **Morph evaluation.** Eyes are rigid; the twin's position does not depend on any weight. The base beside the view
  keeps its real eyes and shows the mix.
- **Changing geometry.** The eye stays put while lids, sockets and brows move. A lid that cuts into the eyeball shows
  through the depth test, which is useful feedback.
- **Visibility.** A hidden eye has no twin; preview off draws the twin as a plain Worklight object too.
- **Cost.** Two more 3 392-face draws and their eye-pass pixels: negligible against the measured 0.56 ms for a
  43 750-triangle draw [RPC].

Open point for Manu: eyes only, or every companion object (teeth for mouth morphs). The mechanism is identical; the
scene holds no "belongs to this head" relation today (the Gollum eyes have no parent, the group "Eyes" is empty [V]),
so the simple rules are "all visible eyes" or "all visible Normal objects".

---

## F. Performance assessment

**The machine [V, `docs/architecture/REFERENCE_HARDWARE.md`].** Core 2 Quad Q9550 (no SSE4.2 / AVX), 8 GB,
GeForce 9800 GTX / GTX+ with 512 MiB (about 395 MiB free at start), OpenGL 3.3.0 core, GLSL 3.30, Windows 10, screen
1200×1920. Python 3.12.10 with `numpy==2.2.6`. The new PC is unspecified; nothing below assumes it.

**Unknown, not invented:** the driver version; the window size Manu actually works at; the cost of the production eye
pass in a real scene (E-4); shader compile time per variant; whether rendering into an RGBA16F cube face and
`textureGrad` work on this driver (neither is used anywhere yet).

**Measured anchors [RPC], lab, eye at about half the frame, 1024×768 / 1920×1080:**
- cube-map reflection L0 1.2 / 2.9 ms, L3 2.0 / 4.3 ms;
- analytic studio (what production uses) L0 1.9 / 4.4 ms, L3 2.9–3.0 / 6.1–6.5 ms;
- one cube fetch over a full 1920×1080 frame: about 0.1 ms;
- the Worklight pass of an 87.5k head in close-up: 16.1 / 26.8 ms. In a close-up the head's own shading is of the
  same order as the eye or larger; the Gollum head (2 336 vertices) was not measured.

| Proposal | GPU | CPU | Memory | OpenGL 3.3 |
|---|---|---|---|---|
| Cache eye uniforms per anatomy | — | saves about 0.46 ms per eye per frame [C], 1–1.4 ms on the RPC [E] | — | — |
| Morph-view twins | two small draws | one extra `EyeDraw` each | two small vertex buffers | yes |
| Wet sclera (#1) | up to the lab's T-D rows [E from RPC] | — | — | yes |
| Cornea irregularity (#2) | +0.1–0.2 ms at close-up [E] | texture built once | 256² two-channel with mips, under 0.4 MB | yes |
| Lid shadow and band (#3), highlight (#6), pupil (#7) | arithmetic, negligible [E] | — | — | yes (`fwidth` already passes on the RPC) |
| Iris light (#4) | +0.05–0.1 ms [E] | — | — | yes |
| Iris relief (#5) | +0.1–0.3 ms [E], two extra fetches on the main sample | derive height once at import | none (alpha of the same image) | yes |
| Iris texture size | — | — | 512² RGBA with mips 1.4 MB, 1024² 5.6 MB, 2048² 22 MB | yes |
| Studio cube on the GPU (#11) | −30 to −50 % of reflection cost [RPC ratio] | bake only when the studio changes | 128² RGBA16F with mips about 1 MB | cube and 16F verified; render-to-face **unverified** |
| Parallax iris (#12) | +0.8–1.5 ms [E] | — | — | yes; full tier only |

Reading:
- **Texture resolution:** at 1920×1080 with the eye half the frame high, the iris spans roughly 270–300 pixels.
  512² already exceeds the screen; 1024² is the sensible cap.
- **In the modelling view** two eyes cover a few percent of the frame, so all GPU additions together stay well under
  1 ms [E]. There the Python cost per eye is the larger item, which is why the cache comes first.
- **In an Eye Lab close-up** #1–#7 land at roughly 3.5–4.5 ms at 1024×768 and 7–9 ms at 1920×1080 [E]. That is
  acceptable for still and slow look development and is what the "fast" tier and #11 are for. Whether it is
  acceptable is the open budget decision D-L8.
- **Scalability:** the tier, the texture size cap and #11 are the three scaling handles. None requires better
  hardware; a faster machine simply runs "full" everywhere.

---

## G. Implementation phases

One stream at a time; each phase ends green and with a practical test.

| Phase | Content | Size | Depends on |
|---|---|---|---|
| **0** | Manu runs E-4 on the reference PC (probe exists). Agent: cache the eye uniforms; no visual change | S | — |
| **1** | Morph-view eye twins (§E) | S–M | decision I-4 |
| **2** | Split the UI: compact panel "Auge", Eye Lab window with live preview, close-up framing, isolate, quality tier, presets from existing values. No shader change | M | decisions I-1, I-2, I-3 |
| **3** | Reflections: wet sclera, cornea irregularity, lid shadow and lid band, coherent highlight (#1, #2, #3, #6). Needs the nested look values and format v10 | L (Core) | decision I-5; phase 2 |
| **4** | Iris: refracted light and crescent, relief from height, pupil edge (#4, #5, #7) | M–L | phase 3 |
| **5** | Iris import workflow in the Eye Lab, image stored beside the scene (#10) | M | phase 4; decision I-9 |
| **6** | Only if measured or wanted: studio cube (#11) with a richer studio (#8), sclera detail (#9) | M each | phases 0 and 3 results |
| later | Parallax iris, eye on a head bone (AD-028), saved gaze, lighting room, window-wide anti-aliasing | — | separate decisions |

Why this order: phase 1 removes a daily workflow block and is independent of everything else. Phase 2 comes before any
new look value, so that none of them lands in the modelling panel. Reflections come before the iris because they are
your stated first characteristic of the stills and cost less.

---

## H. Acceptance criteria

Test scene for every practical test: `scenes/Gollum_Head_03.mirai.json` on the reference PC, three views: modelling
distance (whole head), three-quarter close-up, frontal close-up. Verdicts are Manu's: KEEP / ITERATE / REJECT.

| Phase | Objective (tests, numbers) | Practical test with the Gollum head |
|---|---|---|
| 0 | E-4 results file in the repo for 1024×768 and 1920×1080; eye uniforms no longer recomputed on an unchanged eye; eye-pass pixels identical before and after | none (no visual change) |
| 1 | While a target is edited: one twin per drawn eye at exactly the view's shift; gone after Tab, Undo and load; saved file identical with and without an open view; pick caches and selection unchanged; no eye in any mesh | Edit a blink and a brow target on Gollum: both eyes sit in the target's sockets, cannot be grabbed, follow the gaze, and the base beside it still shows the mix with its eyes |
| 2 | The compact panel holds only the agreed controls; every value reachable in the Eye Lab; a dragged slider changes the picture every frame and leaves one Undo step; closing the Eye Lab restores camera, isolation and tier; no pixel change at equal values | Set up Gollum's eyes from scratch using only the compact panel plus a preset; then refine in the Eye Lab without touching the modelling panel |
| 3 | All new amounts at 0 → bit-identical to today (oracle and `test_gl_eye_pass` green); GPU parity for every new function; measured cost on the reference PC within the agreed budget; no visible shimmer of the reflection in a recorded orbit | Side by side with your stills, same view: softbox edges irregular but glossy, the film continuous over the limbus, lid band present, "wet, not dirty". Also at modelling distance: no noise, no sparkle |
| 4 | Parity and neutral-at-0 as above; pupil edge smooth at every distance; cost measured | Frontal and three-quarter close-up under a moving key (`L`-drag): the crescent moves opposite the highlight, fibres catch light, the iris reads as a bowl |
| 5 | A frontal photo and a flat image each import without a hand-written file; the scene opens on a fresh clone with its iris; landmark error after fit ≤ 1.5 % of the iris radius in the frontal model | Import one photo and one painted iris; neither shows a doubled limbus or a swimming pupil |
| 6 | Cube and analytic studio agree within a set tolerance; no corner seams at rough levels (the known fix applies); reflection cost lower on the reference PC | Richer studio visible in the reflection with no frame-time penalty |

Two standing gates for every phase: a scene without eyes draws byte-identically and costs the same; and the full
`tests/` and GL suites stay green in the container and on the reference PC.

---

## I. Decisions required from Manu

Artistic or product decisions; none is made here.

1. **Eye Lab form.** A window in the app now, a room later (recommended); or a room from the start; or a standalone
   tool.
2. **What stays in the viewport panel.** Proposal: eyes on / off, preview and quality, gaze mode and pad, pupil, look
   preset, "open in Eye Lab". Should an iris colour control be there too?
3. **Eyes on / off.** View state (not saved, no Undo; recommended) or the existing Hide (an Undo step)?
4. **Morph editing.** Twins for eyes only, or for every companion object such as teeth? Or should the target be
   editable in place, which changes "daneben" (J-5)?
5. **Core change (stop point).** New look values as a nested group in `EyeSpec` with scene format v10?
6. **Default eye.** Should the values you settled on in `Gollum_Head_03` become the default for a new eye and the first
   preset, instead of today's L0?
7. **Existing options.** On 2026-11-14 you kept every limbus option as a setting. Move them all to the Eye Lab as they
   are, or give verdicts now and retire some (V3 in particular: no visible difference measured)?
8. **Highlight.** In studio mode, keep the point-light hot spot from the Worklight key, soften it, or drop it?
9. **Iris direction.** Invest first in a better procedural iris, in the photo workflow, or the hybrid? And may Mirai
   copy the iris image beside the scene on save, so scenes stop pointing into the lab folder?
10. **Fakes.** Are a lid shadow and a lid band set by values on the eye acceptable, or should this wait for real
    shadows in a later Lookdev step?
11. **Reference.** Which stills are the yardstick, and at which three views? They cannot go into the public
    repository, so the comparison stays with you.
12. **Budget (D-L8).** What frame time is acceptable in an Eye Lab close-up on this PC, and may a close-up in the
    normal viewport fall back to the "fast" tier by itself?
13. **Linked eyes.** Is "select both, change once" enough, or do you want left and right to share one look by
    definition? Related: should the gaze target be saved with the scene (open since AD-033 §12)?
14. **Anti-aliasing for the whole window.** Not an eye question; it touches every pass and the 512 MiB card. Raise it
    separately or leave it?

Action, not a decision: run `python experiments\drag_cost\probe_eye_preview.py` and again with `--size 1920 1080`
(NVIDIA "Maximale Leistung bevorzugen", `.venv312`), and send the output.

---

## Addendum 2026-11-16 (later): E-4 measured, phases 0 and 1 built

**Manu, 2026-11-16:** the E-4 output of both probe runs, and "Phase 1 go: morph twins for eyes and teeth" (decision I-4:
twins, for eyes and teeth; the editing view stays beside the base).

**E-4 (MEASURED [RPC]),**
[`RESULTS_EYE_PREVIEW_REFERENCE_PC_2026-11-16.md`](../../experiments/drag_cost/RESULTS_EYE_PREVIEW_REFERENCE_PC_2026-11-16.md):
- **GPU.** The whole frame with two eyes costs 1.3 / 2.1 ms (framed head) and 2.7 / 4.8 ms (close on one eye) at
  1024×768 / 1920×1080, *less* than with the preview off. Limbus level, "key only" and V3 change it by at most 0.4 ms.
  So the modelling view has room for the roadmap's shading terms; the close-up estimates of §F (eye on half the frame)
  are still estimates, because the probe's close view puts the eyes on only 7.5–10 % of the frame.
- **CPU.** The preview added 6–8 ms of wall time per frame for two eyes, about 3.5–4.5 ms of Python per eye.
  **This corrects §A.4 and §F**, which estimated 1–1.4 ms per eye: the direction was right, the size was three times
  larger.

**Phase 0, agent part (built).** The chamber angle is computed once per anatomy and the pass reads the active uniforms
once per draw: 1.80 → 0.90 ms per eye in the container, the same numbers to the shader. The effect on the reference PC
is not measured yet.

**Phase 1 (built),** [AD-033 §14](../architecture/AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md): while a target's editing
view is open, every drawn Normal object other than the base is drawn a second time beside the view, as viewport
entries only. Rule chosen for "eyes and teeth": *every* drawn Normal object, because the scene has no relation that
says which objects belong to a head (`PROVISIONAL`; a separate body would be repeated too). References stay where
they are. Acceptance per §H row 1: met in the container tests; the practical test on the Gollum head is Manu's.

**Still open from §I:** every decision except I-4.

## Addendum 2026-11-16 (later still): phase 2 built

**Manu, 2026-11-16:** I-1 "window in the app", I-2 "proposal as is" (no iris colour in the panel), I-3 "view state".
Phase 2 is built as [AD-033 §16](../architecture/AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md) describes: the compact panel
"Auge", the Eye Lab window with live preview, frontal framing, isolation "eyes + head", the quality tier (carried, no
pixel change yet) and look presets from existing values ("Standard (L0)", plus the ones the artist saves). Acceptance
per §H row 2: the objective part is met in the container tests. The practical test on the Gollum head is Manu's.
Deviation: isolation *without* the head is not built (it needs the edit mesh and its overlays suppressed).
**Practical test (Manu, 2026-11-16): "1-6 Keep".** **I-5 decided (Manu, 2026-11-16): "Core Change erlaubt"** - the
new look values may go into `EyeSpec` as a nested group with scene format v10 (§D change 1; a stop point like Q-E2,
now cleared). **Still open from §I:** I-6, I-7, I-9, I-11, I-13, I-14.

### Phase 3 decisions (Manu, 2026-11-16)

- **I-8 Highlight:** keep the Worklight-key highlight in studio mode, but soften it: a broader highlight shape, less
  excessive peak intensity, no isolated artificial white dot. It must stay visually tied to the studio key light and
  read as a corneal reflection.
- **I-10 Lid shadow and reflected lid band:** allowed as subtle, independently adjustable preview parameters for now.
  The lid-shadow approximation stays separate from the dark lid band in the corneal reflection. Both are optional
  (neutral at 0) and structured so geometry-driven shadows and reflections can later supplement or replace them. Not
  baked into textures, no opaque shader hacks.
- **I-12 Budget:** 60 FPS (16.7 ms) is the target; 30 FPS (33.3 ms) is the minimum acceptable interactive performance
  in the Eye Lab close-up. The new eye effects should add about 4 ms at most; 8 ms is the upper limit, and only if the
  whole view stays at or above 30 FPS. Measured on the reference PC at 1024×768 and 1920×1080: targets to validate,
  not assumed results.
- **Standing rule:** keep the lightweight real-time approach; the existing viewport and modelling interaction are not
  sacrificed for eye-specific effects (the "fast" tier and the default path stay as cheap as today).

## Addendum 2026-11-16 (latest): phase 3 built

Built as [AD-033 §17](../architecture/AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md) describes, on the decisions above (I-5,
I-8, I-10, I-12): roadmap #1 wet sclera, #2 irregularity, #3 lid shadow and lid band, #6 soft key highlight, as
`core.EyeLook` (`EyeSpec.look`, scene format v10), drawn only in the "full" tier. Acceptance per §H row 3:

- **Met in the container (TESTED [C]):** every amount at 0 draws bit-identically (also forced into the new program);
  "fast", an eye without a look and a scene without eyes use the program before phase 3 (its source unchanged for all
  64 variants); GPU parity for every new function; no extra frame-to-frame flicker at modelling distance in a stepped
  orbit (+0.01–0.03 grey levels); the oracle and the existing `test_gl_eye_pass` cases green.
- **Measured on the reference PC (Manu, 2026-11-16, MEASURED [RPC],
  [results](../../experiments/drag_cost/RESULTS_EYE_LOOK_REFERENCE_PC_2026-11-16.md)):** the look's own GPU cost in
  the Eye Lab view +0.92 ms (1024×768) / +2.28 ms (1920×1080), at most +3.36 ms in any measured view - within the I-12
  target of about 4 ms; "fast" unchanged. §F's estimate for #1-#7 at this size (3.5-4.5 / 7-9 ms) was pessimistic. An
  eye filling the frame height is estimated above the 8 ms limit at 1920×1080 [E], not measured. The phase 0 CPU fix
  is measured too: 7.0-7.8 ms less wall time per frame, correcting the open estimate of the first addendum.
- **Practical test (Manu, 2026-11-16): "1-8 Keep"** - all eight points of AD-033 §17 KEEP; the behaviour is
  accepted, the numbers stay `PROVISIONAL`. Phase 3 is done; phase 4 (iris) needs its own go.

Deviations from §C / §D, each with its reason in AD-033 §17: per-eye variation from the object id mixed with a look
seed instead of a mirrored seed; the shadow is the upper lid's only and independent of the key direction; no canthal
tilt; the softened highlight is a softbox-shaped area light at the key (I-8 kept the key highlight, the studio softbox
stays where it is). A built-in preset "Reflexe (Startwerte)" (look values only, `PROVISIONAL`) gives the practical test
a starting point; I-6 stays open. **Still open from §I:** I-6, I-7, I-9, I-11, I-13, I-14.

## Addendum 2026-11-16 (phase 4): the iris built

**Manu, 2026-11-16:** "Phase 4 go" (roadmap #4, #5, #7, the rules of phase 3), then on the two questions asked before
building: "1 go (v11)" (the iris values as their own optional group in the look, scene format v11, v10 files unchanged)
and "2 go" (until the import of phase 5 the relief's height is derived from the iris image's brightness). Built as
[AD-033 §18](../architecture/AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md) describes: `core.EyeIris` (`EyeLook.iris`), drawn
only in the "full" tier. Acceptance per §H row 4:

- **Met in the container (TESTED [C]):** every amount at 0 draws bit-identically (also forced into the new program);
  "fast", every eye without iris values and every scene without eyes use the program of phase 3 (its source unchanged
  for all 128 variants); GPU parity for every new function; the crescent lies opposite the key from either side, the
  rim shadow on the key's side; the pupil edge only changes a ring at the pupil radius (with the pixel footprint, so it
  is smooth at every distance).
- **The physics checked [C]:** the key's path through the cornea against a forward ray trace from a frontal to a grazing
  key. A finding on the way: §C.1's "#4 analytic" needs the cornea's focusing, and that is strongest with the key from
  the side (at 80° the far iris gets over 3 × the unrefracted key's light); with a frontal key it is an even 1.3 ×.
  The first solver (a fixed-point iteration) was wrong at grazing keys; the built one solves in the path's plane.
- **Cost, run 1 on the reference PC (Manu, 2026-11-16, MEASURED [RPC],
  [results](../../experiments/drag_cost/RESULTS_EYE_IRIS_REFERENCE_PC_2026-11-16.md)):** over the I-12 limit - the iris
  +8.3 / +13.4 ms on top of the look in the Eye Lab view, phase 3 + 4 together +9.3 / +15.7 ms (1024×768 /
  1920×1080). §F's estimate for #4 (+0.05–0.1 ms) assumed an analytic term; the built model traces the key's path, per
  pixel. Changed the same day: the path is baked once per eye into a 64² table and read per pixel (AD-033 §18 "Cost");
  run 2 on the reference PC (Manu, same day): the iris +2.8 / +0.5 ms on top of the look in the Eye Lab view, phase 3 +
  4 together at most +3.8 ms in any measured view - within the I-12 target. The practical test is open.

Deviations from §C / §D, each with its reason in AD-033 §18: the height is derived at draw time into the pass's own
texture (no image is written; phase 5 writes a real one); only the key is refracted (fill and ambient as before);
`crescent` may exaggerate up to 2. A built-in preset "Iris (Startwerte)" (iris values only, `PROVISIONAL`) gives the
practical test a starting point. **Still open from §I:** I-6, I-7, I-9, I-11, I-13, I-14.

