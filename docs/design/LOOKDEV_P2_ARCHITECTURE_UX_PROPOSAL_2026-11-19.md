# LookDev Room P2: Architecture and UX Proposal

**Status:** PROPOSAL; **decisions LD-D1 … LD-D14 by Manu, 2026-11-19** (§0). Still design and research only: no
production code, Core, scene format, render behaviour or GUI is changed, and no key binding is authorised. LD-D8,
LD-D15 and LD-D16 stay open (§0). Items still marked **[O]** in the body are those open ones or are settled by §0.
**AD-038 drafted 2026-11-19 (PROPOSED):** [AD-038](../architecture/AD-038-LOOKDEV-ROOM-M1.md) is the architecture for LD-0 / LD-1. Where it deviates from this proposal (after a code check at `89f61fc`), its §1.2 and §14 say so and the AD holds.
**Date:** 2026-11-19.
**State inspected:** `origin/main` @ `a3bfcc0` ("AD-037 §11.3: the reference PC's 4.2 s …"), working branch
`claude/busy-brown-svigg5` at the same commit, clean tree. Changes of 2026-11-18/19 on `main` were read (AD-036 slices
1–2, AD-037 Phases 1–3, the Gollum scene `Gollum_Head_05`).
**Builds on:** [RENDERING_VISION](RENDERING_VISION.md) ·
[LOOKDEV_P0_CODEBASE_AUDIT](../research/LOOKDEV_P0_CODEBASE_AUDIT_2026-11-13.md) ·
[RENDERING_TECHNOLOGY_RESEARCH](../research/RENDERING_TECHNOLOGY_RESEARCH.md) ·
[EYE_LOOKDEV_PHASE2_ASSESSMENT](../research/EYE_LOOKDEV_PHASE2_ASSESSMENT_2026-11-16.md) ·
[EYE_LOOKDEV_SCLERA_SURFACE_ASSESSMENT](../research/EYE_LOOKDEV_SCLERA_SURFACE_ASSESSMENT_2026-11-17.md) ·
[AD-024](../architecture/AD-024-OBJECT-MATERIAL-AND-WORKLIGHT-EDITING.md) ·
[AD-026](../architecture/AD-026-FACE-CORNER-UVS-AND-TEXTURE.md) ·
[AD-033](../architecture/AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md) ·
[AD-035](../architecture/AD-035-SCLERA-COLOUR-MAP.md) ·
[AD-036](../architecture/AD-036-EYES-TEETH-AND-LIDS-ON-THE-RIG.md) ·
[AD-037](../architecture/AD-037-TEXTURE-PAINT.md) ·
[MODELING_ON_DEFORMED_SURFACES](MODELING_ON_DEFORMED_SURFACES.md) ·
[REFERENCE_HARDWARE](../architecture/REFERENCE_HARDWARE.md).
**Technical appendix:** [LOOKDEV_P2_TECHNICAL_APPENDIX_2026-11-19.md](LOOKDEV_P2_TECHNICAL_APPENDIX_2026-11-19.md)
holds the measurement tables, the P0 reconciliation in detail, shader and variant notes, the invariant mapping and the
test matrix.
**Refinements by Manu (2026-11-19, two plan reviews):** incorporated throughout. They cover:
- eye reflections vs SH9;
- one linear colour pipeline including the eye pass;
- the persistence order;
- future painting in a pose or on a morph;
- the smallest store interface;
- the focused M1;
- R-1;
- `view.lookdev` compatibility;
- the SubD and Eye Lab boundaries.

**Evidence tags** (as in the P0 audit and AD-036):

| Tag | Meaning |
|---|---|
| **[V]** | verified in the code or a decided document at `a3bfcc0` (file:line or section named) |
| **[M-RPC]** / **[M-C]** | measured on the reference PC / in the container, from a results file in the repository |
| **[P]** | proposal of this document |
| **[E]** | estimate or arithmetic, not measured |
| **[O]** | open, requires Manu's decision (§16) |

Names of new classes, files, panels and presets are `PROVISIONAL`.

---

## 0. Decisions (Manu, 2026-11-19, chat; entered by the agent)

Manu approved LD-D1 … LD-D14 as proposed in §16, with two refinements (verbatim):

| # | Decision | Manu |
|---|---|---|
| LD-D1 | LookDev as a room in the same window | Ja |
| LD-D2 | Modelling tools available in the room | Ja, eingeschränkt im Sinne der Nutzung (refinement below) |
| LD-D3 | No yellow selection tint in the room | Ja |
| LD-D4 | Camera kept, framing buttons | Ja |
| LD-D5 | Studio light oriented to the world | Ja |
| LD-D6 | One organic material system, eyes separate | Ja |
| LD-D7 | Linear colour pipeline in LookDev | Ja |
| LD-D9 | Background colour as picked | Ja |
| LD-D10 | Performance target of at least 30 FPS | Ja, als Ziel und Messkriterium (refinement below) |
| LD-D11 | SH9 + analytic studio reflections | Ja |
| LD-D12 | Persistence only after the M1 practical test | Ja |
| LD-D13 | R-1 as the basic rule for all rooms | Ja |
| LD-D14 | Eye Lab locked while LookDev is open, for now | Ja |

**LD-D2 – Modellieren:** „Der Modelling Room bleibt der primäre Arbeitsraum für alltägliche Modellierarbeit. Im LookDev
bleiben Modellierwerkzeuge verfügbar, werden aber gezielt für gestalterische Korrekturen und Beurteilungen eingesetzt.“

**LD-D10 – Performance:** „Die 30 FPS gelten als Ziel für den gerahmten Gollum-Kopf bei 1024 × 768 und stillstehenden
beziehungsweise langsamen Posen auf deinem Referenzrechner. Die tatsächliche Leistung muss gemessen werden. Der normale
Modelling Room darf durch LookDev keine Performanceeinbußen bekommen.“

**Deliberately left open:**

| # | Decided when |
|---|---|
| LD-D8 (region materials) | before P3 |
| LD-D15 (References and Ghosts) | in the M1 practical test |
| LD-D16 (painting directly under LookDev light) | later, after pose painting |

**What follows:**
- The architecture AD for LD-0 / LD-1 (AD-038, `PROVISIONAL` number) can now be written.
- The stop points stay:
  - the AD before any `src/` change;
  - Manu's go for the LD-2 Core field (`SceneObject.look`, v15) after the M1 verdict;
  - keys only after a practical test (D-L9).
- LD-D2 reads in the design as: the room does not hide or refuse tools. It is not designed or optimised as a modelling
  room, and no modelling-specific UI is added to it.
- LD-D10 reads in the design as: the 30 FPS figure is the LD-0 / LD-1 measurement criterion, and "no loss in the
  Modelling Room" is a gate (E1, E16, §12.4).

---

## Kurzfassung für Manu (Deutsch)

- **Was der LookDev-Raum ist:** eine umschaltbare Konfiguration desselben Fensters, wie der Paint Room. Das ist keine
  zweite App, kein zweiter Renderer und keine zweite Geometrie. Er zeichnet dieselben Puffer, die der Viewport ohnehin
  hat (Morph, Pose, SubD), nur mit einem anderen Shader. Das Worklight bleibt, wie es ist.
- **Was du darin tust:** Du beurteilst den ganzen Kopf im Studio.
  - Studio-Vorlage (Neutral, Portrait, Soft, Dramatisch), Drehung, Helligkeit, Belichtung, Hintergrund.
  - Key, Fill und Rim.
  - Für das gewählte Objekt eine Material-Vorlage (Creature Skin, Wet Skin, Zähne, Mundinneres, Organisch, Neutral)
    mit wenigen Reglern.
  - Morph-Regler, Pose und Blick funktionieren weiter. Ich empfehle, dass auch die Modellier-Werkzeuge im Raum gehen.
- **Regel R-1:** Ein Raumwechsel setzt Pose, Morph-Gewichte, Blick und SubD **nie** zurück und überschreibt sie nicht.
  Gespeichert wird weiter nach den heutigen Regeln: Morph-Gewichte und SubD in der Szene, Pose und Blick nicht.
- **Augen:** Es gibt weiter **ein** Augen-System und **einen** Augen-Durchgang. Er bekommt eine LookDev-Variante.
  - Darin rechnet alles linear und wird nur einmal belichtet, getont und kodiert, genau wie die Haut. Dadurch gibt es
    keine Farbsprünge zwischen Auge und Haut.
  - Die sichtbaren Reflexe bleiben die analytische Softbox. Die diffuse Umgebung (SH9) ersetzt sie nicht.
  - Die Worklight-Varianten bleiben quelltextgleich, gesichert durch den gepinnten SHA-256 in `test_gl_eye_pass.py`.
  - Das eingefrorene Augen-Lab in `experiments/` und das Eye-Lab-Fenster bleiben unverändert.
- **Malen:** LookDev zeigt dieselbe gemalte Zusammensetzung wie der Paint Room, in LookDev-Licht. Malen in Pose oder auf
  einem Morph ist **noch nicht** möglich (P-8). Es gibt Grundlagen dafür: UV-Speicherung, und die Texel-Karte arbeitet
  mit jeder Positionstabelle. Treffer und Pinselabdruck müssen aber erst auf der sichtbaren verformten Fläche gebaut
  werden. §6 trennt, was schon da ist, was fehlt und was LookDev jetzt vorbereitet.
- **Erstes Ergebnis (M1):** der ganze Gollum-Kopf im Portrait-Studio mit Creature Skin, den vorhandenen Augen und
  funktionierendem Morph und Pose.
  - Material und Raum-Einstellungen sind in M1 **nur für die Sitzung**: Wir stimmen die Werte erst im Praxistest ab.
  - Danach kommt **eine** Speicher-Scheibe (LD-2): Material als Core-Feld (Format v15) und die Raum-Einstellungen in
    `view.lookdev`.
  - Achtung: Heutige Versionen **verwerfen** einen unbekannten `view.lookdev`-Abschnitt beim Speichern. Das ist im
    Code geprüft und steht in §10 als Einschränkung.
- **Was später kommt:** Qualitäts-Automatik (LD-3), Cubemap-Umgebung, Schatten, Rauheits- und Normal-Maps, Durchscheinen
  (P3), aufwendigere Haut (P4), ein eigener Final-Render (P5).
- **Entschieden 2026-11-19:** LD-D1 … LD-D14 (mit deinen Präzisierungen zu LD-D2 und LD-D10, §0). Offen: LD-D8 (vor
  P3), LD-D15 (im M1-Praxistest), LD-D16 (nach dem Pose-Painting).

---

## 1. Where we are: baseline and reconciliation

### 1.1 What has changed since the P0 audit (2026-11-13, `8e7da7a`)

| Area | State at `a3bfcc0` | Tag |
|---|---|---|
| Eye | Parametric eye object (`SceneObject.eye: EyeSpec`, v9–v12), production `EyePass` outside `GLRenderStore.draw()`, look / iris / sclera map, gaze, view twins, Eye Lab window, rig link (AD-036) | [V] AD-033 §11–§19, AD-035 §2 |
| Seam "option B" (P0 §4.1) | Proven in production: `EyePass` draws a store's VertexList with its own program, using only public `vertex_list()` / `uniform_data()`, `viewport.py:1019–1027`, `eye_pass.py:457` | [V] |
| Paint | UV-space layers (`SceneObject.paint`, v14), Normal + Multiply, merge, UV transfer, a live composite shown as a `LiveTexture` (`objects.py:1543` `_shown_texture`) | [V] AD-037 §2, §10, §11 |
| Rooms | Paint Room (exclusive session, `paint_room.py`); Eye Lab (`DisplayState.eye_lab` + an imgui window). There is no generic room class | [V] |
| Rig | Pose, skin and rigid parts on bones; every object shows the pose; gaze drives the eye bones in a pose | [V] AD-036 §4.6, §16 |
| Colour | Worklight display-referred (`gl_render_store.py`, no tone map or encode); eye pass mixed (§7.1) | [V] |
| Background | Still `glClearColor(0.1, 0.1, 0.11, 1.0)` hard-coded, `src/main.py:715` | [V] |
| Environment | No cube map anywhere in `src/` (grep `samplerCube` / `TEXTURE_CUBE`: none). The eye uses an analytic studio | [V] |
| UVs on the GPU | Still tied to the Worklight texture: `RenderMesh._uv_wanted`, `render_mesh.py:650` (P0 I-7 open) | [V] |
| Main PC | Still the reference PC (D-L5, 2026-11-14) | [V] REFERENCE_HARDWARE §1 |

### 1.2 What still holds and what does not

- **Still right:**
  - extend, do not rebuild (P0 §1.1);
  - LookDev consumes the evaluated `RenderMesh`es (P0 §3.1);
  - the material and light state is new and separate from `ObjectMaterial` and the Worklight (P0 §3.2, §3.3);
  - a shader-side colour path (P0 §3.2);
  - the invariants I-1 … I-12 (P0 §3.5).
- **Done or overtaken:**
  - P1 (the eye lab) is finished and frozen as the oracle (AD-033 §8);
  - the "store binding accessor" proved unnecessary for the eye (AD-033 §11, deviation 3).
- **Must be revised:**
  - The Vision's P2 ("Production integration") assumed the eye would arrive with LookDev. The eye is already in
    production under the Worklight, so P2 is now about the *rest of the character* and about moving the eye into a
    shared LookDev light and colour context.
  - The Vision's P3 ("lighting, skin and shadows") is too large as one step.
  - The P0 recommendation of a prefiltered cube for the first realtime milestone is overtaken by the measured cost:
    40 s per 128² CPU chain on the Q9550 [M-RPC], and production chose the analytic studio (AD-033 §11, deviation 1).
- **Detail:** appendix §A.

### 1.3 Proposed phase cut (detail §13)

| Stage | Content | Core / format change |
|---|---|---|
| **LD-0** | A small probe on the reference PC | none |
| **M1 = LD-1** | Room + LookDev pass + linear colour pipeline + portrait studio (lights, analytic studio, SH9 diffuse) + eye LookDev variant + Creature Skin and the other presets, assigned per object **for the session only**. **The first demonstration** | none |
| **LD-2** | The persistence slice (`LookMaterial` v15 + `view.lookdev`), the material panel completed, a simple viewport capture | v15 (by content) |
| **LD-3** | Quality manager (capabilities, timing, Auto / override) | none |
| **P3** | Cube environment, key shadow map, roughness / normal / translucency maps, backscatter, region materials | per item |
| **P4** | Optional advanced skin tiers (measured), MSAA / HDR target on a capable PC | — |
| **P5** | Final-render export (immutable snapshot to an external renderer) | — |

---

## 2. Room concept and interaction model

### 2.1 Form: a room in the same window [P]

The Paint Room proves the pattern: a switchable configuration of the same window, entered from the SPACE menu, with
saved and restored display values and its own panel (AD-037 P-2, §10.1, `application.py:1070` / `1104`). LookDev
follows it, with two differences that come from its job:

1. **It is non-exclusive.** The Paint Room owns the input slot (`PaintRoomSession`, `owner="paint"`, exclusive,
   `paint_room.py:96`) because plain LMB paints. LookDev changes no gesture, so it starts no interaction session. The
   normal BindingSet, the tools and the panels stay as they are (AD-013 addendum: the BindingSet stays the input truth).
2. **It is read-only on geometry evaluation.** It never refuses a pose or a morph mix, unlike the Paint Room
   (`paint_room_refusal`, `application.py:1052`, P-8). Evaluating the posed, morphed character is its purpose.

Alternatives, recorded and not recommended:
- a global display toggle (there would be nowhere to keep the room's own view values and panel);
- a second window or GL context (rejected in P0 §4.1 D: duplicates geometry on a 512 MiB card);
- a bridge process.

### 2.2 Entering and leaving [P]

- **Entry:** a SPACE menu row "LookDev öffnen" / "LookDev schließen", the panel's close box. There is **no key**
  (D-L9, CLAUDE.md keymap rule); a key follows only after Manu's "Taste passt".
- **On entry, saved for the exit:** the display values the room changes:
  - display mode → Shaded;
  - wire overlay → off;
  - region tint → off;
  - eye tier → "full".

  This is the mechanism of `PaintRoomController.saved_view` (`paint_room.py:188`). The camera stays where it is.
  Framing buttons are offered, not forced (§3).
- **On exit:** those values come back. Nothing else is touched.
- **While open:**
  - A save writes the *restored* display values into the file's `view.display`, as the Paint Room does
    (`application.py:1732–1736`).
  - A scene load or reset closes the room.
- **Refusals on entry:** another exclusive session is running (Paint stroke, Knife, Bone chain); the Paint Room is
  open (one room at a time, §2.5).

### 2.3 Rule R-1: rooms never reset deformation or view-evaluation state [P]

> **R-1.** Entering, leaving or switching rooms (LookDev, Paint Room, and the Eye Lab window) never silently resets,
> modifies or overwrites **pose, morph weights or current target, gaze, or SubD settings**.
>
> If a target room cannot host the current state yet (today: the Paint Room in a pose or with a morph mix, P-8), the
> switch is **refused with a status line**. It is never "made possible" by resetting the state.

R-1 governs *room transitions only*. It does **not** change how these states are saved. They keep their existing
scene-persistence rules, verified in code:

| State | Saved with the scene? | Where | Tag |
|---|---|---|---|
| Morph weights and each object's current target | yes | `view.morph` (`view_state._capture_morph`, `view_state.py:82`) | [V] |
| SubD view, level, cage depth test, secondary strength, lines | yes | `view.subd` (`view_state.py:72`) | [V] |
| Pose | no: a load starts at rest | AD-028 §6, `skinning.py:587` | [V] |
| Gaze | no: view state | AD-033 §12 | [V] |

Today's rooms already satisfy R-1 by construction:
- the Paint Room saves only `mode`, `wire`, `texture` and `regions` (`application.py:1085–1088`) and refuses instead of
  resetting;
- the Eye Lab saves camera, isolation and tier (`application.py:1010–1027`).

The rule makes this an explicit contract for LookDev and for every later room. A test pins it (§14).

### 2.4 What stays live in the room

| Capability | In LookDev | Why |
|---|---|---|
| Navigation, ortho, framing | yes | the camera is shared (P0 §2.12) |
| Selection (modes 1–4), hover, GPU picking | yes, unchanged | picking draws its own ID pass from the cage `RenderMesh` (`gpu_picker.py`); LookDev changes nothing there [V] |
| Morph sliders, morph-target editing view and its twins | yes | LookDev draws whatever `Viewport.render()` draws (`viewport.py:995`) [V] |
| Pose mode, bone panel, gaze | yes | same |
| Modelling tools (W/E/R, topology, Knife, Soft …) | **yes — decided LD-D2 (§0):** available for targeted design corrections and evaluation; the Modelling Room stays the primary room for everyday modelling | LookDev writes the same depth as the Worklight (§10.2), so overlays and tools behave the same. Forbidding them would push the artist out of the room for every small fix |
| Paint strokes | no: the Paint Room's job | §2.5 |
| Eye placement, `EyeSpec` values via the compact panel "Auge" | yes, existing paths | one eye system (§7) |

The Modelling Room remains the primary space for everyday modelling; LookDev is intended for deliberate look checks and focused corrections where more realistic shading, lighting and (once available) cast shadows add clear artistic value, while its modelling tools remain available without making it a second primary modelling workspace.

### 2.5 Relation to the other rooms and workflows

- **Paint Room ↔ LookDev:** mutually exclusive configurations of the same window.
  - Each panel offers a one-click switch to the other ("Im LookDev ansehen" / "Im Paint Room malen", `PROVISIONAL`).
  - The switch closes one room (restoring its display values) and opens the other. Under R-1 pose, morph, gaze and SubD
    pass through untouched.
  - While P-8 is open, a switch to the Paint Room in a pose is refused with the existing reason.
- **Eye Lab window (AD-033 §16):** not extended or modified by this proposal.
  - The new LookDev lighting of eyes lives only in the production `EyePass`'s LookDev variant (§7).
  - Whether the Eye Lab window may open while LookDev is open, and if so whether it then shows Worklight or LookDev
    light, is **[O] LD-D14**.
  - Until decided, the proposal is the safe default: opening the Eye Lab from inside LookDev is refused with a status
    line ("Eye Lab: erst LookDev schließen", `PROVISIONAL`). Opening LookDev closes an open Eye Lab, as
    `open_paint_room` does today (`application.py:1082`).
- **`experiments/lookdev_eye_lab/`:** stays the frozen oracle (AD-033 §8). It is not touched.
- **Morph workflow:** the morph-target editing view (AD-025 §15) and its view twins (AD-033 §14) draw through the same
  `Viewport.render()` loop, so they appear in LookDev light. Twins of eyes take the eye pass, as today.
- **Rig workflow:** posed surfaces and bone-linked rigid parts (AD-036) are already in the drawn `RenderMesh`es
  (`entry_surface_render_meshes`, model matrices) [V].

### 2.6 Camera, focus, selection, overlays, display

- **Camera:** shared, not saved separately in M1. Framing buttons: Front / ¾ / Profile on the edit object's bounds,
  using `OrbitCamera.frame_on_bounds` (`camera.py:117`), the same call `frame_eye` uses (`application.py:1238`).
  Leaving the room keeps the camera where the artist left it (unlike the Eye Lab, whose close-up is a temporary
  diagnostic view). **[O] LD-D4**.
- **Selection feedback:** in LookDev the yellow material tint (`selected_color`, AD-024 §5) would falsify the look. The
  proposal follows AD-035 S-4 for eyes in the Eye Lab and extends it to all objects in the room: **no tint**; selection
  shows through the existing overlays.
  - In components modes (1/2/3) the face, edge and point highlights draw as today.
  - In object mode the outliner row and the status line name the selection. A thin selection outline is a later
    overlay, not M1. **[O] LD-D3**.
- **Overlays:**
  - wire off on entry (restored on exit), user-toggleable;
  - gizmo, pivot, bones, HUD, triad and the selection box draw as today (`main.py` `on_draw` order);
  - Soft-shading overlays and region tint stay available but start off.
- **Hide / Isolate:** respected automatically. Hidden faces are degenerate in the shared index buffer (P0 I-8), hidden
  objects have no entry.
- **References / Ghosts:** drawn by the Worklight path as today, alpha over the LookDev image. **[O] LD-D15** (the
  alternative is hiding them in the room).
- **SubD:** shown as the artist set it. LookDev adds **no** SubD reduction and the quality manager never changes the
  level (§12). The existing cap `MAX_DERIVED_FACES = 25_000` (`subdivision/preview.py:75`) is a **current limitation**:
  the Gollum head shows SubD level 1 at most (level 2 would be 36,008 faces, AD-037 §10.3) [V].

---

## 3. Artist-facing panel (UX) [P]

One compact window "LookDev", placed left like the Paint Room's and the Eye Lab's (`imgui_layer.py`). Sections:

| Section | Controls (default view) | Collapsed "Mehr" |
|---|---|---|
| **Studio** | Preset (Neutral Inspection · Portrait · Soft · Dramatic) · Drehung (environment and lights about the vertical axis) · Helligkeit (environment intensity) · Belichtung (EV) · Hintergrund (Solid / Verlauf + colour) | tone curve "Neutral / Clamp (Diagnose)" |
| **Licht** | Key / Fill / Rim: on/off, strength, direction (azimuth / elevation), warmth (Kelvin) | softness (highlight size), "Licht folgt Kamera" |
| **Material** (selection) | Preset (Creature Skin · Wet Skin · Zähne · Mundinneres · Organisch · Neutral) · Farbe aus (Textur / Bemalung / Farbe) · Rauheit · Glanz · Weichheit (wrap) | Durchscheinen + Farbe (backscatter) |
| **Ansicht** | Front / ¾ / Profil framing · wire on/off · "Augen: Vorschau" (shortcut to the existing eye display) | — |
| **Status** | one line: "nicht gespeichert" (M1), the active quality (LD-3) | — |

Rules:
- About 15 controls visible. Everything else is collapsed. No node graph, no icon toolbar, no property sheet (the
  GUI Bestandsaufnahme hypothesis "keine Werkzeugleiste mit Icons, keine Eigenschaftsfenster", `[H]`).
- A held slider previews, and release commits (the eye and paint pattern: `preview_eye`, `preview_paint_layer`).
- Light and studio changes are view state (no Undo, AD-024 Q-L1). Material changes are one Undo step each once they
  are document data (LD-2). In M1 they are session state (§5).
- An eye selected in the room shows "Auge — Werte im Panel Auge" in the material section. Eyes are not edited through
  the organic material (§4.3).
- Layout and labels are `PROVISIONAL` until a GUI decision.

---

## 4. Material system [P]

### 4.1 One shading model, a few presets

The Vision lists material types (Creature Skin, Wet Skin, Sclera, Iris, Cornea, Teeth, Mouth Interior, Generic
Organic). The proposal splits them by what they actually are:

- **Organic surface** is one shading model for every non-eye object. Its terms:
  - sRGB-decoded albedo;
  - Lambert diffuse with wrap;
  - GGX / Smith / Schlick specular from the lights;
  - environment diffuse (SH9) and environment specular (the analytic studio);
  - optional backscatter.

  The presets are *value bundles* of this model:

  | Preset | Intent | Roughness | Specular level (F0) | Wrap | Backscatter |
  |---|---|---|---|---|---|
  | Creature Skin | Gollum default: thin, oily, slightly translucent | ≈ 0.50 | ≈ 0.028 (n ≈ 1.4) | medium, warmer in red | low, warm |
  | Wet Skin | lips, lid margins, wet areas | ≈ 0.25 | ≈ 0.028 | medium | low |
  | Zähne | enamel | ≈ 0.30 | ≈ 0.04 | low | low, warm |
  | Mundinneres | gums, tongue, cavity | ≈ 0.30 | ≈ 0.028 | high | medium, red |
  | Organisch | generic | ≈ 0.55 | 0.04 | low | 0 |
  | Neutral (Clay) | grey inspection material; the fallback | 0.6 | 0.04 | 0 | 0 |

  All values are [E] starting points for the M1 practical test.
- **Eye** stays the specialised model with its own pass (`EyeSpec`, AD-033). Sclera, Iris and Cornea are *parts* of
  one eye object, shaded analytically (AD-033 §3 E1). They do not become organic presets. Duplicating them would
  create a second eye system (§7).

### 4.2 Artist-facing properties

| Property | Meaning | Note |
|---|---|---|
| `preset` | name of the bundle the values came from | a label; editing a value keeps the preset name with "angepasst" |
| `base_color` | sRGB-encoded artist colour [0, 1] | decoded to linear in the shader; the value the colour picker shows |
| `albedo_source` | `texture` (the object's shown texture: path or paint composite) · `color` | §5 |
| `roughness` | perceptual roughness [0, 1], α = r² | glTF / OpenPBR meaning |
| `specular` | specular level [0, 1] → F0 = 0.08 · level (0.5 → 0.04) | OpenPBR / Disney "specular" meaning; documented, not a raw F0 field |
| `wrap` | diffuse softness [0, 1] | Worklight vocabulary (`wrap_light`), per-channel tint fixed by the preset |
| `backscatter`, `backscatter_color` | thin-region light from behind [0, 1] | P3 refines with a thickness map |

Reserved for P3 (not in the first schema, §5): `roughness_map`, `normal_map` + `normal_strength`,
`translucency_map`.

### 4.3 Coexistence with `ObjectMaterial` [P]

- `ObjectMaterial` (`base_color`, `specular`, `glossiness`, AD-024) stays the **Worklight material**, unchanged in
  meaning, storage and UI.
- **Nothing is mapped implicitly.** `glossiness` is never read as roughness, `specular` never as F0 (Vision §4).
- **Fallback for an object without a LookDev material:** the preset "Neutral". Its albedo is the shown texture (path or
  paint composite) when the object has UVs and one, otherwise `ObjectMaterial.base_color` read **as a colour value
  only** (an sRGB artist colour, as the Worklight shows it), otherwise `DEFAULT_BASE_COLOR`
  (`gl_render_store.py:405`). This is the P0 recommendation "reuse the value as the default colour, read from the object,
  not from the packet" (P0 §3.2).
- References keep their Worklight look (AD-024 Q-M3) unless LD-D15 decides otherwise.

### 4.4 Per object first, regions later [P]

- **M1 / LD-2: per object.** On Gollum this already covers head, teeth (4 objects) and eyes [V] (`Gollum_Head_05`:
  "Gollum_backup_noscale1 ZBrush" with paint, `tooth`, `tooth01`, `Zahn_1`, `Zahn_2`, two eyes).
- **Later: region materials.** The mouth interior and wet lip line are part of the head mesh, and the scene has no
  separate mouth object [V]. Candidates:
  - face regions (AD-REGIONS-01; overlap is allowed there, so a priority rule is needed) resolved to a per-face
    material index;
  - or a separate mouth-interior object (cheapest, works with per-object).

  Region materials are evaluated separately. They need per-face data on the GPU, which this proposal deliberately does
  **not** expose in P2 (§9.3). **[O] LD-D8**.

---

## 5. Persistence order [P]

The dependency between the room's settings (`view.lookdev`) and the material field is resolved by **one** persistence
slice after the first practical test:

| Stage | Material assignments | Room settings (studio, lights, exposure, background) | File change |
|---|---|---|---|
| **M1 (LD-1)** | session only: held by the app (like `eye_previews`), keyed by ObjectId, dropped on scene load / reset; the panel says "nicht gespeichert" | session only; each session starts from the default preset | **none** |
| **LD-2** | `SceneObject.look: LookMaterial \| None` (Core, frozen, validated, data only; AD-024 / AD-037 precedent, CORE_V1_FREEZE §7.1); written as **v15 only when an object has one** (the existing "version by content" rule, `core/serialization.py`); Undo per change (`ObjectLookCommand`, shaped like `ObjectMaterialCommand`) | `view.lookdev` (preset, edits, lights, exposure, background, quality override); read defensively like every view section | v15 by content |

Why this order:
- **No guessed schema is frozen.** The M1 practical test decides which properties the artist actually uses. Freezing
  them first would mean a v16 migration later.
- **No split.** The Core field and its view-state companion land in one reviewed commit with one set of round-trip
  tests.
- **A session-only side table is acceptable in M1**, because it never reaches a file. AD-024 §1.2 rejected an
  ObjectId-keyed table *for persistence* (IDs are remapped on load). That reason does not apply to transient state.

### 5.1 Compatibility of `view.lookdev`: a verified limitation

- **Load:** `view_state.apply` (`view_state.py:114`) iterates only its known section names (`display`, `light`,
  `surface_finish`, `camera`, `subd`, `symmetry_display`, `reference_ghost`, `morph`). An unknown `lookdev` section is
  **ignored** without error [V].
- **Save:** `save_scene_file` replaces the whole `"view"` dict with `view_state.capture(self)`
  (`application.py:1732`), a fresh dict of the known sections only (`view_state.py:41`). An unknown `lookdev` section
  is therefore **dropped** when a build that does not know it saves the scene again [V].
- **Consequence:** scene files are *not* forward-compatible round-trip for LookDev room settings. A newer scene opened
  and saved in an older build loses its studio, lights, exposure and background. This is acceptable for view state:
  - the Worklight light has the same property;
  - nothing in the document is lost.

  It must be stated in AD-038 and in the practical-test notes.
- **The `LookMaterial` field is different:** an older build refuses a v15 file as an unsupported version (the rule
  every format bump has used since v3, AD-024 §3). So materials are never *silently* lost.
- **Optional mitigation, not proposed for LD-2:** `capture` could carry forward unknown `view` sections it loaded. That
  would be a small change to `view_state` for every future section, and it is its own decision.

---

## 6. Paint Room integration and future painting on posed / morphed geometry

### 6.1 LookDev reads the paint as it is [P]

- The albedo source of a painted object is the **same live composite** the Worklight shows: `PaintDisplay` →
  `LiveTexture`, returned by `_shown_texture` (`objects.py:1543`) [V]. LookDev introduces no second compositor, no
  second texture cache and no second upload. `GLRenderStore.texture()` and the `LiveTexture` upload path are reused.
- LookDev resolves this source **independently of the Worklight's texture toggle and the selection tint**. Today
  `_shown_texture` returns `None` for a highlighted object or with `show_texture` off [V], and that would blank the skin
  of the selected head in LookDev. The resolver for `LookDraw` asks the same `paint_display` / `obj.texture` source
  without those two Worklight conditions.
- **Colour:** paint layers stay 8-bit, display-referred storage (P-16 as decided for the Paint Room). LookDev *decodes*
  that 8-bit value as sRGB to linear in its shader. This settles P-16 for LookDev without changing paint storage:
  - the Worklight and the Paint Room keep showing raw values;
  - LookDev lights them linearly.

  An artist will see that a colour painted in the Worklight reads slightly different under LookDev light. That is the
  intended difference between a work light and a studio, and the M1 practical test checks it (§15).
- **Future channels** go into the same workflow in this order (AD-037 audit "Channels"):
  1. a roughness / specular map (a second paint stack or a map path on `LookMaterial`, decided in P3);
  2. a translucency / thickness map;
  3. normal / detail maps, first imported from ZBrush (a path), later painted.

  Each is an additional UV-space image. No PBR authoring system.

### 6.2 Painting in a pose or on a morph: what exists, what is missing, what LookDev prepares

Manu (2026-11-19): painting while posed and on morphed geometry is planned for the near future. The current refusal is
therefore **not** an architectural assumption of this proposal. The goal is that the artist paints on the posed or
morphed character and sees the result in LookDev at once.

**Verified foundations [V] (useful, but not painting support):**
- **Storage is in UV space** (`SceneObject.paint`, layers as images, AD-037 §2). It does not depend on pose or morph: a
  stroke painted in any state writes the same layer.
- **`TexelMap`** maps every texel to a drawn triangle and barycentric weights. A texel's surface point can be formed
  from *any* position table with the mesh's ids and topology: rest, morph mix or posed surface (module docstring,
  `mirai/paint/texel_map.py:1–6`). A position change does not rebuild the map.
- **`PaintSurface`** evaluates the hit, the footprint and the cursor on the *shown* surface (the cage, or the SubD
  preview's derived mesh with SubD on), and re-reads positions when the mesh reports moved vertices
  (`mirai/paint/surface.py` docstring; AD-037 P-10, §10.3).
- **Picking on the posed surface** exists for weight setting (MODELING_ON_DEFORMED_SURFACES §16).

**Not supported today [V]:**
- The Paint Room **refuses** a posed or morph-mixed edit object: `paint_room_refusal` checks `_query_cage()`
  (`application.py:1052`, `5335`; P-8 open).
- `PaintSurface` is built from the edit mesh or the SubD preview mesh. The morph / skin stage position tables
  (`SurfacePositions`) are **not** wired into it, and its surface-point cache is reset per position change, not per
  pose step.
- Brush radius semantics under stretch, the facing test on posed normals, symmetric painting in a pose (P-9, "mirror in
  rest space") and the cost of re-evaluating surface points per pose change on the reference PC are **unimplemented
  and unmeasured**.

**Required behaviour of the future painting implementation [P]:**
1. The brush **hit and footprint are evaluated on the actually visible, deformed surface**: the morph mix, the posed
   skin and, with SubD on, the SubD surface of the deformed cage. This matches what the artist sees, in LookDev or the
   Worklight.
2. The footprint is **transferred to UV space** through the same `TexelMap` (the texel's surface point from the
   deformed table, the write into the UV layer).
3. **The world radius** is measured on the deformed surface (what the artist sees). Where a pose stretches the skin,
   the painted UV footprint is correspondingly smaller or larger. This is the expected behaviour, to be confirmed in a
   practical test.
4. **Mirror** in rest space across the mesh's plane, then evaluated on the deformed surface (P-9).
5. One stroke = one Undo step, as today. Pose and morph remain view state and are not part of the stroke.

**What the LookDev architecture prepares now [P]:**
- **R-1** (§2.3): switching between LookDev and the Paint Room never resets the pose or morph state the artist wants
  to paint on. Once P-8 lifts, the switch simply passes.
- **No LookDev evaluation of its own** (§9): LookDev shows exactly the surface the painter will hit, the same
  `RenderMesh`es.
- **The live composite as the LookDev albedo** (§6.1): a stroke becomes visible in LookDev light in the next frame, with
  no export or bake step.
- **The room switch keeps the camera.** "Paint here, then look in LookDev" keeps the view.

**What LookDev does not prepare** (it belongs to the painting implementation): wiring the evaluated tables into
`PaintSurface`, radius semantics, the rest-space mirror, cache invalidation per pose change, the probe on the reference
PC, and lifting the `_query_cage` refusal. A later option is *painting inside the LookDev light*, a combined
configuration. It needs P-8 first, and the exclusive paint session would then run with the LookDev shading switch on.
It is listed, not proposed (**[O] LD-D16**).

---

## 7. Eye system integration

This is the central architecture question. Principle: **one eye object, one eye pass, one shader library, two lighting
contexts.** Nothing of the eye is implemented a second time. The eye's quality is not reduced to simplify the
architecture.

### 7.1 What the eye pass is today [V]

- **Routing:** `Viewport.render()` sends an entry with an `EyeDraw` and no entry surface to `EyePass.draw`
  (`viewport.py:1019–1027`). Everything else goes to `RenderMesh.render()`.
- **Inputs:** `store.vertex_list()`, `uniform_data("camera_uniforms" / "model_uniforms")`, the plain program's
  attribute locations and the shared texture cache. No face data, no material packet (`eye_pass.py:457–549`).
- **Light:** the **7 Worklight uniforms** (`values.update(light)`, `eye_pass.py:483`). The diffuse is
  `worklight_light(n)` = ambient + wrapped key and fill (`eye_shaders.py:192`).
- **Visible reflections:** the analytic studio `td_env` (`eye_shaders.py:174`) of softbox, strip and backdrop, built
  from compile-time constants (`studio_frames()`, `eye_optics.py:425`) and evaluated in **view space**. Plus the key's
  GGX or area highlight (`highlight_softness`, AD-033 §17).
- **Colour path, mixed:** albedos and the diffuse are display-referred and written raw. Each reflection term goes
  through `display_add(x) = srgb_encode(x / (1 + x))` (Reinhard, then sRGB, `eye_shaders.py:126`) and is *added* to
  the display value (`eye_shaders.py:821`, `823`, `897`). The output is `vec4(colour, 1.0)` (`eye_shaders.py:907`).
- **Source discipline:** the program is assembled in Python. `shell_sources()` (`eye_shaders.py:1025`) builds a
  `#define` header, and `_without()` (`eye_shaders.py:1044`) removes every `#ifdef` block whose define is off, *as the
  preprocessor would*. `test_gl_eye_pass.py` pins the SHA-256 of all variant sources (`PINNED_SOURCES_SHA256`,
  `test_gl_eye_pass.py:1099`, `test_sources_without_a_map_are_the_ones_before_ad035`).

### 7.2 The LookDev variant of the eye pass [P]

A new define `LOOKDEV` in the same program family (cache key + 1). Its `#ifdef LOOKDEV` blocks replace exactly three
things, and nothing else of the eye's optics:

| Part | Worklight variant (unchanged) | LookDev variant |
|---|---|---|
| Diffuse light | `worklight_light(n)`: Worklight key / fill / ambient | `lookdev_diffuse(n)`: LookDev key / fill / rim (same wrap function) + SH9 environment irradiance (§8.2) |
| Albedos (sclera colour or map, iris image, limbal colour) | raw display values | sRGB-decoded to linear (`srgb_decode`, the inverse of the existing `srgb_encode`) |
| Visible reflections | `td_env` with constant studio, view space; per term `display_add` | the **same `td_env` algorithm**, with the LookDev studio's parameters as uniforms, in character / world space with the studio rotation; terms accumulated **linear**, no per-term `display_add` |
| Output | `colour` written raw | `lookdev_output(colour_linear)`: exposure → tone curve → sRGB encode, **once per pixel**, the same function the skin pass calls |

What stays identical in both: refraction (V2 / V3), the iris analytic geometry, fit, relief, caustic, limbus L0–L3, the
wet film, irregularity, lid shadow and band terms (`EyeLook`, `EyeIris`), the sclera map mapping, gaze (the drawn
matrix) and selection handling.

### 7.3 Two separate guarantees for the Worklight [P]

The Worklight behaviour must not change. Two different properties are protected, each by its own gate:

1. **Source identity (by construction):** with `LOOKDEV` off, `_without(…, "LOOKDEV")` removes every new block, so each
   Worklight variant's source is character for character today's. Gate: `PINNED_SOURCES_SHA256` and
   `test_sources_without_a_map_are_the_ones_before_ad035` stay unchanged. The pinned digest is **not** re-pinned in the
   LookDev change.
2. **Pixel identity (by test):** the existing Worklight-match and "preview off = Worklight draw byte for byte" tests of
   `test_gl_eye_pass.py` (AD-033 §11 "Verified"), the Worklight pixel gates (`test_gl_face_data_layout.py`,
   `test_gl_shading.py`, `test_gl_texture.py`), and the oracle tests against the frozen lab
   (`experiments/lookdev_eye_lab/tests/test_oracle_production.py`) pass unchanged.

Source identity alone does not prove pixel identity: Python-side uniform setting or GL state could still change. Pixel
identity alone does not prove that no variant changed: a variant not covered by a pixel test could. Both are needed.

### 7.4 Coherence between skin and eyes [P]

- **One lighting library.** A GLSL source string `LOOKDEV_LIGHT_LIB` (light uniforms, `lookdev_diffuse`, SH9 evaluation,
  the parametric studio, `srgb_decode`, `lookdev_output`) is included by both the skin program and the eye LookDev
  variant. Each function has a NumPy twin with a GPU parity test, the established pattern (`eye_optics` ↔
  `eye_shaders`).
- **One set of uniforms per frame:** the LookDev state resolves once per frame into one dict, pushed to the LookDev
  pass and the eye pass alike. This is the same pattern as `light_uniforms()` for the Worklight (`viewport.py:327`).
- **Calibration test:** in LookDev, a grey card (Neutral preset, albedo 0.5) on the skin pass and the sclera of an eye
  with the same albedo and roughness, lit by the same key at normal incidence, match within ≤ 2/255. This makes "no
  double tone mapping, no exposure mismatch" a test, not a promise.
- **Wetness and highlight quality are preserved:**
  - the cornea keeps its sharp analytic softbox reflection and the key area highlight;
  - SH9 never replaces a visible reflection (§8.1).

### 7.5 Later (not P2)

- The analytic studio may be replaced by a prefiltered cube for the eye only after a side-by-side Artist verdict on the
  Gollum eyes (the lab measured T-C at about half T-D's per-pixel cost [M-RPC], so the cube may become the cheaper path
  as well).
- Lid shadow and band (`EyeLook`, neutral at 0, "replaceable by geometry later", AD-033 §17 I-10) may be driven by a
  LookDev key shadow map (P3).
- A tear meniscus needs lid geometry (AD-033 §17).

---

## 8. Lighting and environment

### 8.1 Three separate jobs, three separate techniques [P]

| Job | Technique | Stage |
|---|---|---|
| **Diffuse environment illumination** (broad fill, colour of the surroundings on skin and sclera) | **SH9**: 3 bands × RGB = 9 `vec3`, projected on the CPU from the LookDev studio function (NumPy, milliseconds [E]); evaluated per pixel with the normal rotated into the studio frame | M1 |
| **Visible reflections** (cornea, wet sclera, wet lips; the broad sheen on skin) | **The analytic studio** (`td_env`, the lab's T-D: softbox, strip, backdrop; the lobe fitted to the cube prefilter within 16 % RMS at r ≤ 0.8, lab README) made **parametric** (uniforms instead of constants) + the analytic key / fill / rim highlights with area softness | M1 |
| **Arbitrary environments and roughness-correct reflection of them** (HDRI, a room, coloured surroundings) | **A prefiltered cube map** (RGBA16F 128², corner-equalized chain to 2²) | P3 |

SH9 is low-frequency by definition. It cannot hold a softbox's edge and is never used for a visible reflection
(Vision §5.5, research §7). The studio's *direct* lights (key, fill, rim) are analytic and **not** baked into SH9 or a
cube, so moving a light never triggers a projection or a prefilter.

### 8.2 The studio presets [P]

| Preset | Key | Fill | Rim | Environment | Background |
|---|---|---|---|---|---|
| Neutral Inspection | front-high, soft | strong, opposite | off | even grey dome | mid-grey solid |
| Portrait (default) | 45° side, 30° up, soft area | 1:3, opposite low | on, behind-opposite | dark studio, one large softbox | dark gradient |
| Soft Studio | large, front-side | 1:2 | low | bright dome, two softboxes | light grey |
| Dramatic | hard, 70° side | off or 1:8 | strong | near-black | near-black |

- The values are `PROVISIONAL`, tuned in the M1 practical test on Gollum.
- **Light units:** relative intensities; colour from `kelvin_to_rgb` (linear Rec.709, luminance-normalised,
  `light_rig.py:205`), reused as a pure function. The Worklight's `LightRig` state, presets, `DisplayState.light_*` and
  the 7 Worklight uniforms stay Worklight-only (P0 §3.3).
- **Light space:** fixed to the character / world by default, so the studio stays put while the artist orbits around
  the head, as in a photo studio. "Licht folgt Kamera" is an option. This is the opposite of the Worklight's
  camera-space default, which suits modelling. **[O] LD-D5**.
- **Rotation:** one angle turns environment *and* lights together about the vertical axis (a turntable of the studio).
  It is a uniform: no projection, no prefilter.
- **Intensity / exposure:** environment intensity scales SH9 and the studio reflection. Exposure (EV) scales the whole
  linear image before the tone curve.
- **Background:** solid or vertical gradient. The picked colour is shown **as picked** (a display value written after
  the tone curve, not exposed or tone-mapped), so the artist gets the background they chose. **[O] LD-D9**. A blurred
  environment as background is later.

### 8.3 The cube map later: cost and caching [M-RPC] / [P]

- **Measured on the reference PC:**
  - RGBA16F cubes sample correctly and at RGBA8 speed;
  - one lookup over 1920×1080 costs ≈ 0.1 ms;
  - seamless filtering fails at cube corners, fixed by corner equalization and a chain ending at 2²;
  - **CPU prefilter 25 / 40 / 71 s per 64² / 128² / 256² chain** (REFERENCE_HARDWARE §2, 2026-11-13 / 14).
- **Consequence:** a cube can never be prefiltered on a preset switch in the UI thread. Options for P3, in order:
  1. **GPU prefilter** by rendering into the cube faces through an FBO. Unverified on the 9800 GTX: render-to-RGBA16F
     cube face and `textureGrad` are untested (EYE_LOOKDEV_PHASE2_ASSESSMENT §F). It needs the LD-0 probe item (c).
  2. **CPU prefilter once, cached per machine** on disk, keyed by a hash of (environment recipe, size, mapping, code
     version). The first use of a new environment shows a progress status line. Afterwards loading is instant.
  3. Fewer, smaller chains (64²) for rough levels only.
- **Rotation and intensity never re-prefilter** (uniforms). Only a new environment *content* does, and the built-in
  presets are few.

---

## 9. Skin and character shading

### 9.1 M1 skin [P]

- **Albedo:** the painted composite / texture, sRGB-decoded. The detail painted by the artist is never filtered beyond
  trilinear mipmapping.
- **Diffuse:** Lambert with wrap, the wrap slightly larger in red than in green and blue (the classic cheap
  "scatter-colour wrap"). It is local, per pixel, and never blurs across the surface, so sculpted folds stay crisp.
- **Specular:** GGX D + Smith G + Schlick F from key, fill and rim (the eye's existing `ggx_d` / `smith_vis` are the
  template). The environment specular comes from the analytic studio at the skin's roughness.
- **Specular anti-aliasing:** roughness widened from the screen-space variance of the normal (derivatives, `dFdx` /
  `dFdy` pass on the reference PC [V] P0 §3.4). There is no MSAA in the default framebuffer [V].
- **Normals:** the interpolated vertex normals of the shown surface, **not** the Worklight's bilinear quad normal.
  - Measured full-frame close-up: 16.1 ms with face data vs 2.9 ms without at 1024×768 [M-RPC].
  - The P0 probe already showed the technical tendency (D-L6, P0 §8).
  - With SubD level 1 on Gollum (≈ 9k faces) interpolated normals read smooth. On the cage they show the cage, as
    designed.
- **Backscatter:** a low, warm term for light from behind on silhouette-thin regions (ears, nostril wings). In M1
  without thickness information it is limited to the view-aligned rim and `N·L < 0` wrap, at a low default. P3 gives
  it a thickness / translucency map.

### 9.2 Later stages [P]

| Stage | Addition | Why then |
|---|---|---|
| P3 | dual-lobe specular (two roughnesses mixed) | measurable gain on oily skin, cheap |
| P3 | roughness / specular map | needs the paint channel decision (§6.1) |
| P3 | normal / detail maps (ZBrush export first), tangent frame from screen derivatives of position and UV, **no per-vertex tangent buffer** (no deformation-time CPU cost) | needs the map workflow |
| P3 | translucency / thickness map for backscatter | authoring needed |
| P3 | one key **shadow map** + PCF | depth textures are untested on the driver (P0 §3.4, LD-0 (d)); an extra geometry pass costs GPU time |
| P4 | optional diffusion tiers (texture-space or pre-integrated), measured | only if P3 skin is judged insufficient |
| never in P2–P3 | screen-space blur SSS | blurs sculpted detail across depth discontinuities and costs fill rate |

M1 has no cast shadows. The Portrait and Soft presets are tuned to read without them. The Dramatic preset will show the
lack most clearly. This is a known M1 limitation (§15).

---

## 10. Rendering architecture

### 10.1 Data flow [V] / [P]

```
Core  Mesh · SceneObject(material, texture, eye, bone, paint, [look: LD-2])            ── authoritative, saved
  │ Mesh.watch journal
src/mirai  SurfaceChain: morph → skin → SubD (AD-028, H7)        ObjectController.sync_views
  │ evaluated positions / derived mesh                              │ Worklight: colour, finish, texture (packet)
  │                                                                 │ EyeDraw (eyes)
  │                                                                 │ [P] LookDraw: resolved LookDev material + albedo source
Viewport  RenderMesh (edit, surface, entries, entry surfaces) → GLRenderStore (VertexList, face data, textures)
  │                       ▲ read only                                ▲ read only
  │  render():  shading == "worklight" →  RenderMesh.render()  /  EyePass(LIGHTING Worklight)      [V] today
  │             shading == "lookdev"   →  [P] LookdevPass.draw()  /  EyePass(LOOKDEV variant)
  │                                         + [P] background pass
  ▼
default framebuffer RGBA8 + depth24 ← overlays, gizmo, HUD, triad, imgui (unchanged)
```

LookDev reads the `RenderMesh`es that `Viewport.render()` already draws: `surface_render_mesh` or `render_mesh`,
`object_entries`, `entry_surface_render_meshes` (`viewport.py:995–1027`). That is the morph mix, the pose and SubD as
evaluated. It adds **no** geometry evaluation, deformation, SubD or topology work, and never writes a store's buffers
(P0 I-10).

### 10.2 The LookDev pass [P]

- New `src/viewport/lookdev_pass.py` (+ `lookdev_shaders.py`), outside `GLRenderStore.draw()`, built exactly like
  `EyePass`:
  - `vertex_list()`, `uniform_data("camera_uniforms" / "model_uniforms")`;
  - the plain program's attribute locations (`layout(location = …)` from `GLRenderStore.program().attributes`, P0
    I-2);
  - its own programs, compiled lazily and cached by variant key;
  - GL state set explicitly and left as `GLRenderStore.draw` leaves it (depth test and cull off, units unbound, unit 0
    active, program stopped; P0 I-4, `eye_pass.py:521–548`).
- **Program:** VS + GS + FS. The geometry shader provides barycentrics for the per-triangle UV lookup, the pattern of
  the textured Worklight program (`gl_render_store.py`, the `TEXTURED_*` sources), which is exercised on the reference
  PC [V].
- **Depth contract (P0 I-1):** the same vertex transform (`u_proj · u_view · u_model · position`) and the same
  polygon-offset rule (`store.polygon_offset`, set by the viewport per mesh, `viewport.py:775–801`). The wire,
  highlights, tool lines and points therefore meet the LookDev surface exactly as they meet the Worklight's. Tested
  (§14).
- **Texture units:** 1 = triangle UVs (the store's own unit), 4 = albedo (as the Worklight); 2, 3, 5 free for later
  maps. Unit 0 stays pyglet / imgui (P0 I-5).
- **Transparency:** opaque only in P2. Ghost entries keep their Worklight draw order after the opaque ones
  (`_entry_draw_order`, `viewport.py:438`).

### 10.3 The smallest public interface needed [P]

Two needs, two small semantic interfaces. Nothing else is exposed.

1. **"UVs wanted" decoupled from the Worklight texture.** Today `RenderMesh._uv_wanted()` is
   `material.texture is not None and mesh.has_face_uvs()` (`render_mesh.py:650`). The proposal adds one consumer flag
   on `RenderMesh`, for example `set_uvs_requested(bool)`. `_uv_wanted()` becomes "the Worklight material has a texture
   **or** a consumer requested UVs, and the mesh has UVs".
   - The viewport sets the flag for an entry whose `LookDraw` needs an albedo map, and clears it otherwise.
   - With the flag off everywhere, the code path is today's. The gates are `test_gl_texture.py` and
     `test_render_mesh_face_data.py` unchanged.
   - A change of the flag goes through the existing `_sync_uv_resource` / rebuild-on-UV-state-change logic
     (`render_mesh.py:697`, `_patch_topology`). Measure the cost of the first toggle on Gollum in LD-0.
2. **The per-triangle UV lookup for a foreign program.** The `u_triangle_uvs` RG32F buffer texture exists only inside
   the store's private binding methods (`_flush_face_data`, `_bind_vertex_textures`, `_set_face_samplers`,
   `gl_render_store.py:740–819`). The proposal is one public method shaped like
   `bind_triangle_uvs(unit) -> bool` / `unbind_triangle_uvs(unit)`:
   - it flushes and binds that one buffer to a unit the caller chooses;
   - it returns `False` when the mesh has none;
   - the Worklight draw keeps calling its private methods as today.

**Not exposed:** face normals, face corners, triangle→face rows, the R32F vertex views, region tints. A future region or
per-face material (§4.4) or the bilinear quad normal would need some of them. That access is evaluated separately when
such a feature is decided, as P0 already noted for `face_corners .w`.

### 10.4 Viewport switch and draw state [P]

- `Viewport.shading` ∈ {`"worklight"`, `"lookdev"`}. It is draw state, like `eye_preview`. With `"worklight"`,
  `render()` is today's code path.
- `set_object_entry(…, look: LookDraw | None = None)` and the edit mesh's setter carry the resolved material values and
  the albedo source (a path or a `LiveTexture`). This is the pattern of `eye: EyeDraw` (`viewport.py:338`).
  `ObjectController.sync_views` resolves `LookDraw` **from the object** (`look` or the fallback of §4.3), never from the
  packet, which is the displayed Worklight colour (P0 I-6).
- **Background:** with `"lookdev"`, the clear colour or a gradient pass comes from the LookDev state before the meshes
  draw (depth write off). With `"worklight"` the hard-coded `glClearColor(0.1, 0.1, 0.11)` (`main.py:715`) stays.
  Moving it behind a getter that returns the same constant is a refactor proven by the gates.
- **No FBO, no float target in P2.** The pass encodes into the RGBA8 default framebuffer. That keeps the overlay depth
  contract intact (P0 §4.1 F) and avoids untested driver paths. An HDR target (bloom, screen-space effects, MSAA
  resolve) is a later option, best first on a capable PC.

### 10.5 What LookDev must not do [V]-derived rules

- No second scene graph, renderer, geometry evaluation or deformation path.
- No change to `GLRenderStore.draw()`, the Worklight programs, `light_rig` state or `DisplayState`'s Worklight fields.
- No write to any `RenderMesh` or store buffer. No dependency of picking on LookDev.

---

## 11. Colour management [P]

| Step | Worklight (unchanged) | LookDev |
|---|---|---|
| Colour textures, paint composite, picked colours | used as display values | **sRGB → linear in the shader** (`srgb_decode`). sRGB texture formats are untested on the driver (P0 §5.7 Q5), and decoding in the shader leaves global GL state alone |
| Lights | display-referred wrap / Blinn–Phong | linear; `kelvin_to_rgb` is already linear Rec.709 [V] |
| Shading | display-referred | scene-linear |
| Exposure | none | EV, one uniform, before the curve |
| Tone curve | none | one fixed neutral curve (Reinhard on luminance or a short filmic shoulder, chosen in M1 against Gollum); "Clamp" as a diagnostic |
| Encode | none (raw) | linear → sRGB in the shader, once per pixel |
| Background | constant clear colour | the picked display colour, not exposed (LD-D9) |

- There is no OCIO, no ACES pipeline and no colour-space metadata system in P2. Textures are assumed sRGB. Non-colour
  maps in P3 (roughness, normal) are flagged as linear data by their slot, not by a colour-management framework.
- **Expected visible difference:** the same base colour reads differently in the Worklight (display-referred, flat
  modelling light) and in LookDev (linear light, a tone curve). This is intended. The two contexts are not calibrated
  against each other, except the eye-vs-skin calibration *inside* LookDev (§7.4).

---

## 12. Performance and quality adaptation

### 12.1 Facts that set the budget [M-RPC]

All measured on the reference PC (Q9550, 9800 GTX+, 512 MiB, GL 3.3), detail in the appendix §B:

| Measurement | Value |
|---|---|
| Worklight full-frame close-up, 87.5k | 16.1 / 26.8 ms with face data; 2.9 / 5.0 ms without (1024×768 / 1920×1080) |
| Eye preview, head + two eyes | 1.3 / 2.1 ms framed |
| Eye look + iris, worst measured view | +3.8 ms |
| D3 pose frame, 87.5k | ≈ 51 ms; `on_draw` ≈ 19.6 ms of it (AD-032 §12) |

The Gollum head at SubD 1 (≈ 9k faces) is about a tenth of that geometry.

### 12.2 M1 budget [E], to be measured in LD-0

- **Skin pass, Gollum close-up filling the frame:** ≈ 3–6 ms at 1024×768, ≈ 6–12 ms at 1920×1080.
  Reasoning:
  - interpolated normals start from the 2.9 / 5.0 ms class;
  - add texture, GGX × 3 lights, SH9 and the analytic studio specular;
  - the analytic studio costs about 2× a cube lookup per pixel in the lab.
- **Eyes in the LookDev variant:** the existing costs, plus a few ALU operations for decode and SH9.
- **Target, decided LD-D10 (§0):** ≥ 30 fps on the reference PC at 1024×768 with the framed Gollum head, for still or
  slow poses. It is the target **and** the measurement criterion; the real performance is measured (LD-0, LD-1). Live
  deformation is judged qualitatively, as D-L8 left open for the eye.
- **Gate, decided LD-D10:** LookDev causes no performance loss in the normal Modelling Room (§12.4; E1, E16 in the
  appendix).
- **Levers if over budget** (render-only): drop the studio specular on skin, use the "fast" eye tier, render the
  analytic studio cheaper for rough skin (fewer rectangles).

### 12.3 Quality adaptation (LD-3, after M1) [P]

- **Capability detection on room entry, by feature and never by GPU name:**
  - compile the LookDev variants;
  - check that the needed sampler and texture kinds exist;
  - later, cube completeness, depth textures and FBO formats.
  - A missing feature disables its effect and is named in the diagnostic line.
- **Runtime adaptation:** a `GL_TIME_ELAPSED` query around the LookDev pass (already used in the probes) with a
  moving p50 and hysteresis selects Auto = Full / Balanced / Draft.
- **Knobs:** only rendering settings — analytic studio specular on skin, rim and backscatter terms, specular AA, the eye
  tier. Later also cube size, shadow-map size and PCF taps.
- **Never adapted:** mesh resolution, the SubD level, morph or pose accuracy, topology, picking, or artist-authored
  material values. The quality manager is architecturally unable to reach them, because it only produces a set of
  shader defines and uniforms.
- **Manual override:** "Qualität: Auto / Hoch / Mittel / Entwurf", plus a line saying why (for example "Auto: Mittel —
  14 ms > 12 ms Ziel").
- **M1 ships without it:** one fixed full setting, measured on the reference PC in LD-0 and LD-1. This keeps it off the
  M1 critical path.

### 12.4 The Worklight is unaffected [P]

With `shading == "worklight"` no LookDev program is compiled, no LookDev state is resolved, and no UV request is set.
The gates (§14) prove byte-identical pixels, unchanged pinned eye sources and an unchanged D3 frame with LookDev off.

---

## 13. Implementation stages, dependencies and stop points

### LD-0: probe on the reference PC (agent writes, Manu runs; about 15 min) [P]

`experiments/drag_cost/probe_lookdev.py` (`PROVISIONAL`), container first. It measures:
- (a) a stand-in LookDev skin program on the Gollum head (cage and SubD 1) at framed and close-up views,
  1024×768 / 1920×1080;
- (b) the first UV-request toggle on Gollum (the `RenderMesh` UV-state change);
- (c) optional for P3: render-to-RGBA16F-cube-face;
- (d) optional for P3: a sampled depth texture.

Output: `RESULTS_LOOKDEV_REFERENCE_PC_<date>.md`. **No `src/` change.**

### M1 = LD-1: the first demonstration [P]

**Goal:** the complete Gollum head in a controlled portrait studio, with a convincing Creature Skin, the existing eyes
and working morph and pose evaluation.

**Contents:**
- the room frame (§2), R-1 and its test;
- the panel (§3);
- `Viewport.shading`, `LookdevPass`, the background;
- the UV request + `bind_triangle_uvs` (§10.3);
- `LOOKDEV_LIGHT_LIB` with twins;
- the eye `LOOKDEV` variant (§7);
- the four studio presets, analytic studio and SH9 (§8);
- the organic model with all six presets (§4.1), assigned per object for the session only (§5).

**No Core change, no format change, no key.**

**Stop points:**
- the architecture AD (AD-038, `PROVISIONAL` number) before any `src/` change;
- after it, Manu's practical test on `scenes/Gollum_Head_05.mirai.json` (studio presets, skin preset values, eye
  coherence, morph and pose in the room, room switch to the Paint Room and back, R-1).

**Depends on:** LD-0 (a, b).

### LD-2: persistence and the finished material panel [P]

- `SceneObject.look: LookMaterial | None`, format v15 by content, Undo, duplicate / mirror / `replace_scene` carry,
  contract tests (CORE_V1_FREEZE §7.1). The field set is the one M1 confirmed.
- `view.lookdev` with its compatibility note (§5.1).
- **Viewport capture:** "Bild speichern" writes a PNG of the current LookDev view **without overlays**. One extra
  render of the meshes into the back buffer, `glReadPixels`, then the normal frame. It is a screenshot of what the room
  shows at window resolution, and explicitly **not** a render export. An independent render export (its own
  resolution, an immutable scene snapshot, a final-quality backend, EXR) is P5.

**Stop point:** Manu's go for the Core field (as Q-E2 / P-3 were).

### LD-3: quality manager [P]

§12.3. It needs LD-1's timing data.

### P3, P4, P5

- **P3:**
  - cube environment with GPU prefilter or a machine cache (§8.3);
  - a key shadow map (LD-0 d);
  - roughness, translucency and normal maps;
  - dual-lobe specular and backscatter with thickness;
  - region materials (LD-D8);
  - lid shadows from geometry for the eye;
  - painting in a pose (P-8 / P-9) as its own AD, which LookDev already accommodates (§6.2).
- **P4:**
  - optional skin diffusion tiers;
  - MSAA or an HDR target when a capable PC exists (REFERENCE_HARDWARE §5).
- **P5:**
  - the final-render bridge (Vision §6, P4 there): an immutable snapshot of the evaluated `surface_mesh`, the
    materials, the lights and the camera to an external renderer.

### Dependencies

| Item | Depends on |
|---|---|
| LD-1 | LD-0 (a, b) |
| LD-2 | the M1 verdict |
| LD-3 | LD-1 timings |
| P3 cube | LD-0 (c) |
| P3 shadows | LD-0 (d) |
| P3 maps | the paint channel decision (§6.1) |
| Painting in a pose | P-8 / P-9 (outside LookDev) |

---

## 14. Tests and gates (summary; matrix in appendix §D)

**Worklight unchanged**
- `test_gl_face_data_layout.py`, `test_gl_shading.py`, `test_gl_texture.py` byte-identical.
- `PINNED_SOURCES_SHA256` unchanged.
- The eye pass Worklight-match and preview-off tests.
- The lab oracle tests.
- The full GL and picking suites.
- D3 with LookDev off.

**LookDev correctness**
- NumPy twins plus GPU parity for every `LOOKDEV_LIGHT_LIB` function (decode, curve, SH9 evaluation, the parametric
  studio, GGX terms).
- SH9 projection of the studio checked against a numerical integral.
- The eye-vs-skin grey-card calibration (§7.4).

**Depth contract**
- The wire and highlights over the LookDev pass give the same depth buffer as over the Worklight (or the same rendered
  lines), within tolerance.

**R-1**
- Enter, leave and switch rooms in a pose with a morph mix, gaze mode and SubD on: pose, weights, current targets, gaze
  and SubD are bit-identical before and after.
- Scene save inside the room writes the restored display.
- The existing persistence of morph and SubD is unchanged.

**Room**
- Display values restored; a scene load closes the room; refusals; Paint ↔ LookDev switch; Eye Lab refusal (until
  LD-D14).

**GL hygiene**
- Each pass leaves GL state as found (the `test_gui_imgui_window.py` pattern).

**Persistence (LD-2)**
- v15 only by content; a file without looks is the same text.
- Round trip, Undo, duplicate, mirror.
- A `view.lookdev` load with bad values is skipped.
- The compatibility limitation of §5.1 is documented by a test (an older capture drops the section).

**Reference PC**
- `probe_lookdev.py` rows recorded in LD-0, LD-1 and LD-3.

---

## 15. Risks

| Risk | Why | Mitigation |
|---|---|---|
| Fill rate at close-ups | per-pixel cost is unmeasured for a full-frame LookDev skin [E] | LD-0 first; render-only levers (§12.2); LD-3 |
| Flat look without shadows in M1 | no cast shadows until P3 | presets tuned for it; Dramatic named as the weak case; shadow map early in P3 |
| Colour shift Worklight ↔ LookDev | sRGB decode and tone curve vs raw display values | explained in the panel and the practical test; never "corrected" by changing the Worklight |
| Eye variant growth / compile time | 8 defines today; NVIDIA Cg compile time per variant unmeasured (assessment §D) | one extra define; lazy compile; measure first-use compile in LD-0 |
| UV request toggling rebuilds | the UV state change falls back to a rebuild (`_patch_topology`) | set the request on room entry, not per frame; measure in LD-0 (b) |
| SubD cap | Gollum at level 1; level 2 over `MAX_DERIVED_FACES` | documented limitation; LookDev adds none; a cap change is a SubD decision |
| Missing assets | teeth without UVs (they use colour only), no mouth-interior object, scene image files partly not in the repository [V] | per-object colour presets; a mouth object or LD-D8; Manu's local files for the practical test |
| `view.lookdev` dropped by older builds | §5.1 [V] | documented; materials protected by v15 |
| pyglet internals | the pass adds the same coupling as `EyePass` (P0 §6.4) | pinning pyglet stays its own small decision |
| Aliasing | no MSAA | specular AA in M1; MSAA later on a capable PC |
| Future posed painting cost | surface-point cache per pose step unmeasured | the painting AD measures it; LookDev only guarantees R-1 and the live composite |

---

## 16. Decisions for Manu

**Status 2026-11-19:** LD-D1 … LD-D14 decided as proposed (wording and refinements in §0). LD-D8, LD-D15 and
LD-D16 stay open.

Needed **before LD-1**:

| # | Question | Proposal → decision |
|---|---|---|
| **LD-D1** | LookDev as a room in the same window (SPACE menu row, no key), non-exclusive, read-only on geometry? | yes → **Ja** (2026-11-19) |
| **LD-D2** | Modelling tools usable inside the room? | yes → **Ja, eingeschränkt im Sinne der Nutzung** (2026-11-19, §0) |
| **LD-D3** | Selection in the room without the yellow material tint (overlays and the outliner show it)? | yes → **Ja** (2026-11-19) |
| **LD-D4** | Camera: kept on entry and exit, Front / ¾ / Profile framing buttons? | yes → **Ja** (2026-11-19) |
| **LD-D5** | Studio lights fixed to the character / world by default, "follows camera" as an option? | yes → **Ja** (2026-11-19) |
| **LD-D6** | One organic shading model + presets (Creature Skin, Wet Skin, Zähne, Mundinneres, Organisch, Neutral); eyes stay the eye system? | yes → **Ja** (2026-11-19) |
| **LD-D7** | Colour: scene-linear in LookDev only, textures and paint decoded as sRGB (P-16 for LookDev), one neutral tone curve, Worklight unchanged? | yes → **Ja** (2026-11-19) |
| **LD-D9** | Background colour shown exactly as picked (not exposed or tone-mapped)? | yes → **Ja** (2026-11-19) |
| **LD-D10** | Budget: ≥ 30 fps on the reference PC at 1024×768 for still or slow poses with the framed head; deformation judged qualitatively? | yes → **Ja, als Ziel und Messkriterium** (2026-11-19, §0) |
| **LD-D11** | Environment: SH9 diffuse + the parametric analytic studio for visible reflections in M1; the cube in P3? | yes → **Ja** (2026-11-19) |
| **LD-D12** | M1 material and room settings session-only; one persistence slice in LD-2 (Core v15 + `view.lookdev`)? | yes → **Ja** (2026-11-19) |
| **LD-D13** | The R-1 rule as the contract for every room? | yes → **Ja** (2026-11-19) |
| **LD-D14** | Eye Lab window while LookDev is open: refused (default), or allowed and lit by LookDev (a later change to the Eye Lab window)? | refused for now → **Ja** (2026-11-19) |

Needed **later**:

| # | Question | When (Manu, 2026-11-19: deliberately open) |
|---|---|---|
| **LD-D8** | Region materials (mouth interior): face regions with a per-face index, or a separate mouth object? | open — before P3 |
| **LD-D15** | References / Ghosts in the room: Worklight ghost on top (default) or hidden? | open — in the M1 practical test |
| **LD-D16** | Later "paint inside LookDev light" as a combined configuration, after P-8? | open — later, after pose painting |
| **(LD-2 go)** | The Core field `SceneObject.look` and scene format v15 | after the M1 verdict |
| **(keys)** | Any key for the room, only after a practical test | D-L9 |

Not decided here and unchanged:
- D-L8 (budget during deformation) is narrowed by LD-D10;
- P-8 / P-9 (painting in a pose) stay open;
- P-16 for the Paint Room's own storage stays as decided.

---

**Next step:** the architecture AD for LD-0 / LD-1 (AD-038, `PROVISIONAL` number), unblocked by Manu's decisions
LD-D1 … LD-D14 (2026-11-19, §0). It belongs in a **fresh session**: this one carries a long audit context, and the AD plus LD-0 probe
are a self-contained slice. Suggested model: **Claude Opus 5.5, reasoning effort high** (Core-adjacent architecture
with shader-source discipline); the LD-0 probe itself could run at medium effort.
