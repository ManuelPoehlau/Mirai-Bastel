# Likeness Camera and Reference Camera Matching: Architecture and UX Proposal

**Status:** PROPOSAL. Design only: no production code, Core, scene format, render behaviour, GUI or key binding is
changed, and no key is authorised. All decisions LC-D1 … LC-D10 are open (§11).
**Date:** 2026-11-27.
**State inspected:** `main` @ `df02a00` ("AD-041 slice 3: fill from a selection"), clean tree. The inventory handed
over from the previous session (same commit) was checked against the code; corrections and additions are in §1.2.
**Builds on:** [GUI_Bestandsaufnahme](GUI_Bestandsaufnahme.md) · [GUI_STAGE1_HUD](GUI_STAGE1_HUD.md) ·
[UX_RESEARCH](UX_RESEARCH.md) · [LookDev P2 proposal](LOOKDEV_P2_ARCHITECTURE_UX_PROPOSAL_2026-11-19.md) (room
pattern, rule R-1) · [AD-038](../architecture/AD-038-LOOKDEV-ROOM-M1.md) (background, capture) ·
[VIEWPORT_V02_ARCHITECTURE §4.1](../viewport/VIEWPORT_V02_ARCHITECTURE.md) (camera contract, ortho addendum) ·
[AD-021](../architecture/AD-021-OBJECT-COMPONENT-MODEL.md) (objects, the Reference role) ·
[AD-026](../architecture/AD-026-FACE-CORNER-UVS-AND-TEXTURE.md) (textures beside the scene) ·
[AD-027](../architecture/AD-027-INTERACTION-LAYER-SESSION-SLOT.md) (interaction owner) ·
[AD-033](../architecture/AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md) (units) ·
[CORE_V1_FREEZE §7](../architecture/CORE_V1_FREEZE.md) · [WP_DYNAMIC_ORBIT_FOCUS](../WP_DYNAMIC_ORBIT_FOCUS.md) ·
[REFERENCE_HARDWARE](../architecture/REFERENCE_HARDWARE.md).

**Evidence tags** (as in the GUI Bestandsaufnahme, plus one for arithmetic):

| Tag | Meaning |
|---|---|
| **[V]** | verified in the code or a decided document at `df02a00` (file:line named) |
| **[E]** | arithmetic or estimate, not measured |
| **[H]** | hypothesis or proposal of this document (`PROVISIONAL` until Manu judges it) |
| **[O]** | open, needs Manu's decision (§11) |

Names of new classes, files, panels and labels are `PROVISIONAL`. The word **Reference** already means a 3D object
role in Mirai (`ObjectState.REFERENCE`, AD-021 RF-1 … RF-6) [V `core/scene.py:85`]. To avoid a collision this
document says **likeness camera** and **photo** (German UI: „Kamera“, „Foto“); code names would be `LikenessCamera`
and `backdrop`, never `reference`.

---

## Kurzfassung für Manu (Deutsch)

- **Was es werden soll:** Du legst eine **Kamera** mit einem echten **Objektiv** an (Brennweite in mm, z. B. 85 mm),
  lädst dazu ein **Foto** der Person, schaust **durch die Kamera** und vergleichst dein Modell direkt mit dem Foto.
  Dann modellierst du in dieser Ansicht, bis Form und Perspektive stimmen.
- **Warum das Objektiv wichtig ist:** Der heutige Viewport entspricht ungefähr einem **26-mm-Weitwinkel** an einer
  Kleinbildkamera (bezogen auf die Bildhöhe) [E]. Ein Porträt wird meist mit 50 bis 135 mm fotografiert. Mit dem
  falschen Objektiv sieht ein richtiges Gesicht falsch aus (Nase zu groß, Ohren zu klein) und du korrigierst die
  falsche Stelle. Handy-Selfies auf Armlänge sind deshalb schlechte Vorlagen.
- **Was schon da ist und benutzt wird:** die eine Viewport-Kamera, das Laden von Bildern (PNG/JPG), das Kopieren von
  Bildern neben die Szene, der LookDev-Hintergrund, das Drahtgitter, das Speichern der Ansicht. Nichts davon wird
  neu gebaut.
- **Wichtigste Idee:** Die Viewport-Kamera bekommt **keine neue Mathematik**. Das Objektiv wird in den Bildwinkel
  umgerechnet, den die Kamera schon kennt. Schräg gehaltene oder beschnittene Fotos werden durch Drehen und
  Verschieben des **Fotos** ausgeglichen, nicht der Kamera. Damit bleiben Auswahl, Picking und alle Werkzeuge
  unverändert.
- **Kein neuer Raum:** Die **Kameraansicht** ist ein Ansichts-Zustand wie Ortho, kein Raum wie LookDev. Du kannst sie
  mit LookDev, Morph-Reglern und Pose kombinieren, und alle Modellierwerkzeuge gehen darin (LC-D1).
- **Erster Schritt (M1):** eine Kamera nur für die Sitzung, Brennweite einstellen, durchschauen, Foto hinter dem
  Modell mit Deckkraft, Rahmen in Fotoformat. Noch kein Speichern, keine Taste, keine Core-Änderung.
- **Danach:** Vergleichen (Foto vor dem Modell, Wischen, Umschalten), Brennweite aus dem Foto vorschlagen (M2);
  Speichern mit Rückgängig und Outliner (M3, braucht deine Entscheidung LC-D2); Silhouette und Kontur (M4);
  automatisches Einpassen über Merkpunkte nur, wenn Handarbeit zu langsam ist (M5, LC-D7).
- **Datenschutz:** Fotos echter Menschen sollen nie im öffentlichen Repository landen; sie kommen in einen eigenen
  Ordner neben der Szene, den Git ignoriert (LC-D9), wie heute schon deine eigenen Iris-Fotos.
- **Deine Entscheidungen:** zehn Fragen in §11, jeweils mit Empfehlung. Für den Start von M1 brauche ich nur
  LC-D1, LC-D3, LC-D4 und LC-D5; der Rest kann bis zum Praxistest warten.

---

## 1. Where we are

### 1.1 M1 check: what exists, what was tried, what was rejected

- **Exists:** one camera (`OrbitCamera`), its saved view state, camera snapshots (Eye Lab, LookDev framing), image
  readers, scene-relative image copies, a full-screen background pass in LookDev, a capture of the drawn frame, an
  image-with-handles editor (iris import). Details §1.2.
- **Tried:** nothing on likeness cameras or reference photos. A repository search for likeness, reference image,
  background image, image plane, focal length and scene camera finds only the Rendering Vision's line "Camera, focal
  length and exposure controls" for the LookDev studio [V `RENDERING_VISION.md:68`]. No experiment, no AD.
- **Rejected:** nothing on this topic. Related rejections that bind this proposal: a second window or GL context
  (LookDev P0 §4.1 D, LookDev proposal §2.1); binding a second camera representation (Gate 7,
  `application.py:788–800`).

### 1.2 Inventory check at `df02a00`

The handed-over inventory holds. Corrections and additions found while checking:

| # | Item | Finding | Tag |
|---|---|---|---|
| 1 | `tan(fov/2)` recomputations | Exactly **7**, all inside `camera.py`: `frame_on_bounds` :133, `_half_height` :201, `build_projection_matrix` :275, `screen_to_ray` :306, `project_to_screen` :354, `screen_projector` :389, `pan` :421. None outside the file (grep `fov_degrees` in `src/`: only `view_state.py`) | [V] |
| 2 | Consolidating them is bit-safe | `frame_on_bounds` writes `radians(fov/2)`, the others `radians(fov)/2`. Halving is exact in binary floating point, so both give `round(fov·π/180)/2`; checked for 1,799 values 0.1° … 179.9°: no difference | [V] / [E] |
| 3 | Dolly clamp | In **two** places: `OrbitCamera.dolly` `camera.py:114` and `view_state._apply_camera` `view_state.py:234` | [V] |
| 4 | Saved camera fields | `view.camera` holds target, distance, yaw, pitch, fov, ortho; **near and far are not saved** (`view_state.py:68–75`) | [V] |
| 5 | Plane primitive UVs | **No UVs**: `create_plane` adds faces without UVs (`scene_factory.py:76–91`) and `Mesh.add_face` infers UVs only on a mesh that already has some (`core/mesh.py:1067`) | [V] |
| 6 | Rooms | Paint Room, **Weight Room (AD-041)**, LookDev, plus the Eye Lab window; one room at a time (`open_lookdev` closes the Weight and Paint rooms, `application.py:1312–1335`) | [V] |
| 7 | Menus | A menu bar (`menus.py:236`) and SPACE menu rows for the rooms, all without keys (`menus.py:347–353`) | [V] |
| 8 | Overlay slot under the wire | Extra overlays with `DRAW_UNDER_HIGHLIGHTS` draw before wire, highlights and hover (`viewport.py:1471–1475`) | [V] |
| 9 | Backgrounds | Worklight: only `glClearColor(0.1, 0.1, 0.11)` (`main.py:715`); LookDev: a full-screen triangle before the meshes (`lookdev_pass.py:373`, called `viewport.py:1550`) | [V] |
| 10 | Core reserved slots | `scene_to_dict` writes `morph_targets`, `rig`, `animation` as reserved top-level slots (`serialization.py:213–216`); `rig` was filled in v7, a precedent for a Core scene slot. The reader accepts versions 1–17, writers emit 4–17 (`serialization.py:143–169`, `:224–243`) | [V] |
| 11 | Eye Lab snapshot | Stores target, distance, yaw, pitch, ortho, **not the FOV** (`application.py:1047–1050`). Harmless today (the FOV never changes); it matters once a camera view changes the FOV (§8) | [V] |
| 12 | Scale of the test head | 1 unit = 1 cm is the convention (Q-E6, `eye_object.py:8`), but `Gollum_Head_05` is 1.2 units wide, not at that scale (ATELIER L6, AD-033) | [V] |
| 13 | Private photos | `.gitignore` keeps Manu's own iris and sclera photos out of the public repository (I-9, S-12; `.gitignore:61–64`); other image copies in `scenes/` are tracked (`git ls-files scenes/*_textures`) | [V] |
| 14 | Image readers | PNG: own decoder (`iris_import.decode_png`); everything else through pyglet (`iris_import.read_rgba`, used by `paint/library.read_image_rgba`). No Pillow, no EXIF reader (`requirements.txt`: NumPy only) | [V] |
| 15 | Direct camera reads | About 53 reads of the application camera: 22 in `application.py`, 31 in controllers, GUI and `main.py` (grep `.camera`) | [V] |
| 16 | Free plain keys | Plain `0` and `A` are unbound in the code defaults and in `config/keymap.json`; `F` is reserved for Frame Selected (`WP_DYNAMIC_ORBIT_FOCUS.md:68`); every other plain letter/digit is bound in some context | [V] |
| 17 | Iris landmark editor | An in-panel image view (320 px) with two circle handles; the logic is pure (`gui/iris_import_model.py`: `pick_handle` :117, `drag_handle` :137, `checked`); the draft is UI state and "Importieren" is one Undo step (`gui/eye_panel.py:289–410`) | [V] |
| 18 | Doc drift | `VIEWPORT_V02_ARCHITECTURE.md:134` "camera … not saved" — fixed in this commit (camera saved by `view_state` since 2026-11-07) | [V] |

### 1.3 How other programs do it (from own knowledge, not re-researched)

| Program | Solution | Take for Mirai | Do not take |
|---|---|---|---|
| Blender | Camera object with focal length (mm), sensor width and sensor fit (Auto / Horizontal / Vertical), lens shift; "look through" camera (Numpad 0); "Lock Camera to View"; camera background images (opacity, front / back, fit, offset, rotation, flip); passepartout; fSpy add-on for solving from lines | the lens vocabulary, look-through, lock, background image with fit, passepartout | the full camera property sheet; lens shift as a camera field (see §2.4) |
| Maya | Camera with film back and film gate, overscan, "Look through selected"; image plane attached to a camera | gate + overscan; photo owned by its camera | separate film-gate and resolution-gate concepts |
| 3ds Max | Physical camera (focal length, film width); Camera Match utility with CamPoints (3D points linked to image points, solves the camera); viewport background "match bitmap"; safe frames | the landmark-solve idea for later (M5) | the separate helper objects per point |
| ZBrush | Perspective with a focal angle; no real camera matching | — | — |
| Wings 3D / Silo | No cameras; reference images in ortho views | — | (3D image planes for ortho drawings are a different feature, §4.6) |

---

## 2. The camera model

### 2.1 One truth: `fov_degrees` stays the camera's only lens value [H]

`OrbitCamera` keeps exactly what it has: target, distance, yaw, pitch, vertical `fov_degrees`, near, far, ortho
[V `camera.py:88–105`]. The matrices, CPU picking, GPU picking, `ObjectSpaceCamera`, the shaders' ortho test and the
`screen_projector` bit-identity all read only these fields. A likeness camera's lens (focal length, sensor, fit) is
**authoring data** that is converted into `fov_degrees` when the viewport looks through it. Nothing downstream learns
about millimetres.

This keeps every "must preserve" item intact: no geometry invalidation (only the camera fields change, with a
`camera_revision` bump), the duck-typed contract (`src/viewport` still sees only matrices), the matrix convention and
the symmetric frustum that `screen_to_ray` / `project_to_screen` / `screen_projector` assume.

### 2.2 One place for the lens math [H]

- **Inside the camera:** one private helper `OrbitCamera._tan_half_fov()` replaces the seven recomputations (§1.2
  items 1–2). Every call site keeps its operation order around it, so `project_to_screen` and `screen_projector` stay
  bit-identical by construction and `frame_on_bounds` does not change by one bit (§1.2 item 2). Guarded by
  `tests/test_camera.py`, `test_camera_ortho.py`, `test_picking_equivalence.py`.
- **Outside the camera:** a pure module `src/mirai/viewport/lens.py` (`PROVISIONAL`), stdlib only, beside
  `camera.py`:
  - `effective_sensor(sensor_w, sensor_h, fit, photo_aspect) -> (w, h)`;
  - `view_tan_half_v(sensor, focal, window_aspect, overscan) -> float` and `fov_degrees(...)`;
  - `gate_rect_ndc(photo_aspect, window_aspect, overscan) -> (half_w, half_h)`;
  - `focal_from_fov(...)` for "camera from the current view".
  It never touches the camera; the application writes its result into `camera.fov_degrees`.

### 2.3 Focal length, sensor and fit [H]

Pinhole model, millimetres for focal length and sensor, the photo's pixel aspect `a = width / height`.

1. **Effective sensor** in the photo's aspect, by the fit mode:
   - *Horizontal:* `W = sensor_w`, `H = W / a`.
   - *Vertical:* `H = sensor_h`, `W = H · a`.
   - *Auto* (Blender's default): the photo's longer side takes the sensor's longer side.
   - *Diagonal (35 mm equivalent):* `D = 43.27 mm` (the 36 × 24 mm diagonal), `W = D · a / √(1 + a²)`,
     `H = D / √(1 + a²)`. Phone EXIF gives a "35 mm equivalent" focal length; makers derive it from the diagonal
     ratio [H, to be checked against sample files in M2], so this mode makes a phone photo's EXIF value usable as is.
2. **Gate in the window** (window aspect `a_w`, overscan `o ≥ 1`, default 1.1 so the HUD strip does not cover the
   gate, `PROVISIONAL`):
   - if `a_w ≥ a` (window wider than the photo): `tan_half_v = (H / 2) / f · o`; the gate is
     `half_h_ndc = 1 / o`, `half_w_ndc = (a / a_w) / o`;
   - else: `tan_half_h = (W / 2) / f · o`, `tan_half_v = tan_half_h / a_w`; the gate is `half_w_ndc = 1 / o`,
     `half_h_ndc = (a_w / a) / o`.
3. `fov_degrees = 2 · degrees(atan(tan_half_v))`. A window resize while looking through recomputes it (one revision
   bump; `Viewport.on_camera_changed` already carries the aspect, `viewport.py:1254`).

Reference numbers on a full-frame sensor [E]:

| Focal length | Vertical / horizontal angle | Distance for a 30 cm tall frame (landscape) |
|---|---|---|
| ≈ 26 mm = today's viewport (`fov_degrees` 50) | 50° / ≈ 70° | 32 cm |
| 35 mm | 37.9° / 54.4° | 44 cm |
| 50 mm | 27.0° / 39.6° | 63 cm |
| 85 mm | 16.1° / 23.9° | 106 cm |
| 135 mm | 10.2° / 15.2° | 169 cm |
| 200 mm | 6.9° / 10.3° | 250 cm |

### 2.4 Lens shift, roll and zoom live in the photo, not in the camera [H]

Three pinhole equivalences make camera-math changes unnecessary for matching:

- **Principal-point offset (lens shift, cropped photo)** ≡ the centred camera's image moved in the image plane. So an
  off-centre or cropped photo is matched by an **offset of the photo inside the gate**, exactly.
- **Roll** about the optical axis ≡ rotating the image about the principal point. A tilted photo is matched by
  **rotating the photo**, exactly (LC-D4). The model stays upright on screen; only the photo turns.
- **Focal length at a fixed pose** ≡ scaling the image about the principal point. So photo scale and focal length are
  the same degree of freedom. Rule: **the photo fills the gate (scale 1) and the lens is the variable**; a free photo
  scale exists only in an explicit "beschnittenes Foto" mode, together with the offset.

Counted degrees of freedom: camera pose 5 (eye 3, view direction 2) + focal 1 + photo rotation 1 + photo offset 2 = 9,
the same as a real camera with roll, focal and principal point [E]. Camera roll and lens shift as camera fields stay
possible later (§10 "later") if Manu wants the *model* drawn rolled or a camera to be exported; both would change the
basis or the frustum and so the bit-identity sites.

### 2.5 Free position, near / far and real distances [H]

- **Free position needs no new camera.** Any eye position and view direction (pitch within ±90°) is a set of
  target / distance / yaw / pitch: `target = eye + d · forward` for any `d > 0` [V `camera.py:223–241`]. A likeness
  camera stores eye, direction and a focus distance; looking through writes them into the orbit fields. Orbit, pan and
  Dynamic Orbit Focus then move it like any view.
- **Near / far per likeness camera.** Each likeness camera carries `clip_near` / `clip_far` (defaults 1 / 1000 units,
  `PROVISIONAL`); looking through sets `camera.near` / `camera.far` (fields that matrices and picking already read).
  Depth precision with a 24-bit buffer at 300 units: ≈ 0.005 units for near = 1, ≈ 0.11 units for today's near = 0.05
  [E, `d² / (near · 2²⁴)`]. A likeness camera is always perspective; `U` in the camera view leaves it (§6.3).
- **The interactive camera's 2 m limit.** The dolly clamp (0.5 … 200, two places, §1.2 item 3) and far = 200 limit
  the free view to about 2 m at true scale; a half-figure at 85 mm needs ≈ 2.8 m [E]. Proposal (engineering,
  `PROVISIONAL`): one `MAX_DISTANCE` constant used by both clamp sites, raised to 2000, and far following the distance
  (`far = max(200, 4 · distance)`). Below a distance of 50 nothing changes (far stays 200, so `ortho_back` and every
  existing test result stay as they are); a test pins that.
- **Scale.** Matching is scale-invariant: scaling the model and the camera distance together gives the same picture.
  The focal length is right at any scale; only a distance shown in metres needs the model at 1 unit = 1 cm, which
  `Gollum_Head_05` is not (§1.2 item 12). The panel therefore shows the distance in units, with metres only as
  "bei 1 Einheit = 1 cm".

---

## 3. The camera entity

### 3.1 Interactive camera vs likeness cameras [H]

- **The interactive camera** stays the one `Application.camera` instance bound to the viewport
  [V `application.py:416`, `:799`]. It is "the viewport's eye".
- **Likeness cameras** are records: name, pose, lens, clip, photo and photo fit. There can be several (front, ¾,
  profile).
- **Looking through** copies a record into the interactive camera (with the derived FOV and clip); while the camera is
  not fixed (LC-D3), navigation writes back into the record. This is the Eye Lab snapshot pattern
  (`application.py:1035–1069`), extended by fov / near / far.
- **Rejected alternative:** binding a second `OrbitCamera` instance to the viewport while looking through. About 53
  call sites read the application camera directly (§1.2 item 15); a second instance would split the truth and break
  the Gate 7 rule "no second camera representation" (`application.py:788–793`).

### 3.2 Where saved likeness cameras live: three options

| | A — camera object in the scene | B — Core scene slot `scene.cameras` | C — mirai view state only |
|---|---|---|---|
| Shape | `SceneObject.camera: CameraSpec \| None` on an object with an empty mesh (like `eye: EyeSpec`; empty mesh like `GROUP`) | a list of `CameraSpec` with id and name, top-level beside `rig` | a `view.likeness` section (or a top-level key the app writes, like `view`) |
| Core change | one frozen dataclass + optional field + format v18 by content; contract tests (§7.1) | one dataclass + slot + v18 | none |
| Outliner, rename, hide, group | free (object rows, text field, hide, groups exist) | a new Outliner section (like the bone list) | a list in the panel only |
| Undo, duplicate, delete, copy / paste | free through the existing object commands (`scene_objects.py:178–537`) | new commands in `src/mirai` | none (view state has no History, `view_state.py:11`) |
| Cost in object paths | guards where objects are iterated (picking, OBJ / GoZ export, SubD, symmetry, skin, LookDev, paint, frame bounds, attach / detach, edit-object rule); groups needed about 17 such guards in 6 files [V grep `ObjectState.GROUP`] | none | none |
| Pose and roll | the object transform (rotation + translation) holds a pose with roll naturally | own fields | own fields |
| Older builds | read v18 only after the reader learns it (same as every format step) | same | **drop it silently on save** (verified for `view.lookdev`, `view_state.py:16–18`) |
| Moving it in 3D | object gizmo in mode `4` once a camera glyph is pickable | own handling | — |

**Recommendation [O LC-D2]:** M1 and M2 keep likeness cameras **for the session only** (no persistence, like LookDev
M1 under LD-D12), so the camera's fields are settled by Manu's practical test before anything enters the Core. For
M3, **option A**:
- matched cameras and their photos are document work, so they need Undo and must not vanish silently, which rules out
  C;
- A reuses the Outliner, the object commands, hide and groups (golden rule), where B would rebuild them.

Freeze justification for A (CORE_V1_FREEZE §7):
1. requirement: matched cameras survive save / load, Undo, duplicate and delete;
2. not solvable with the public API: a view section has no History and is dropped by older builds; an ordinary
   empty object with a naming convention would be a hidden contract;
3. smallest extension: one optional field and a format version by content, the pattern of `eye`, `paint` and `look`.

Like a group, a camera object is never the edit object (the Core enforces this for groups, `core/scene.py:1083`).
Opacity, front / back and the compare mode are viewing choices and go to `view.likeness` (no Undo), as the LookDev
studio went to `view.lookdev`.

### 3.3 Undo while looking through (M3) [H]

With the camera not fixed, every finished navigation gesture (end of an orbit or pan drag; consecutive wheel ticks
merged until another command) is one Undo step `ObjectTransformCommand` on the camera object. A fixed camera produces
none. In M1 / M2 (session only) there is no Undo, as for the LookDev studio. The granularity is a feel question for
the M3 test.

---

## 4. Reference photos

### 4.1 Ownership [H]

One photo per likeness camera, one camera per photo (LC-D8): a photo is one pose of one lens. Several photos
(front, ¾, profile) are several cameras. A shared lens across photos from one session ("gleiches Objektiv") is a later
convenience, not a data rule.

### 4.2 Storage beside the scene [H]

- Read with the existing readers (§1.2 item 14), downscaled once to at most 4096 px on the longer side (≈ 48 MiB for
  4096 × 3072 RGBA on a 481 MB card [E]; the paint library's `reduce_rgba` is the precedent).
- **On save (M3):** copied beside the scene with the hashed-name rule of `texture_files.py`, but into a **separate
  folder `<scene stem>_photos/`** that `.gitignore` excludes (`scenes/**/*_photos/`), so photos of real people never
  reach the public repository by accident (LC-D9; precedent I-9 / S-12, `.gitignore:61–64`). The path in the file is
  scene-relative, resolved on load (`texture_files` rules). A missing photo keeps its path and shows a status line.
- **EXIF (M2):** a small stdlib reader for JPEG APP1 (FocalLength, FocalLengthIn35mmFilm, Orientation), in the spirit
  of the own PNG decoder. It only *suggests* the focal length; Manu confirms. The Orientation tag matters: pyglet
  ignores it [H], so phone photos would load sideways without it.

### 4.3 Fit [H]

| Value | Meaning | Default |
|---|---|---|
| Fit mode | Auto / Breite / Höhe / Diagonale (§2.3) | Diagonale with a 35 mm equivalent focal length, else Auto |
| Rotation | the photo about the gate centre (= camera roll, §2.4) | 0° |
| Offset | the photo in the gate, in gate heights (= lens shift) | 0, 0 |
| Scale | only in "beschnittenes Foto" mode (= crop) | 1 |
| Mirror | the photo left / right | off |

Rotation, offset and scale are part of the match and belong to the camera record (document data from M3).

### 4.4 Opacity, in front of or behind the model [H]

- **Behind** (M1): drawn before the meshes with depth test and depth write off; the model is opaque over it. Opacity
  blends the photo with the background colour.
- **In front** (M2): drawn after the meshes, alpha-blended, depth off, **under** wire, highlights, gizmo and HUD, so
  the working overlays stay readable.
- Opacity, placement and on / off are view state (`view.likeness` from M3).

### 4.5 Draw path [H]

- **Screen-space quad in the gate, not a 3D plane.** The photo *is* the camera's image plane, so a quad in normalised
  device coordinates is exact by construction: no depth fighting, no far-plane clipping, no picking, no export, no
  SubD, no Outliner row.
  - A textured plane object was considered and **not recommended**:
    - the plane primitive has no UVs (§1.2 item 5);
    - an object takes part in picking, export, symmetry and the Outliner;
    - it must be re-aligned whenever the camera moves.
- **Behind:** a new optional "backdrop" step in `Viewport._render_meshes` before the meshes, in both shading paths:
  - Worklight: after the clear;
  - LookDev: after `draw_background` (`viewport.py:1550`).
  - The step follows the LookDev background's GL pattern: depth off, state restored (`lookdev_pass.py:373–402`).
- **In front:** an extra overlay with `DRAW_UNDER_HIGHLIGHTS = True` (`viewport.py:1471–1475`), so no new ordering
  mechanism is needed.
- **Texture:** `GLRenderStore.texture(path)` caches by path, mtime and size (`gl_render_store.py:610`); a downscaled
  copy goes up once as a `pyglet` texture, the way the iris import view uploads its draft (`eye_panel.py:306–319`).
- **Boundary:** `src/viewport` receives only a texture, four corners in NDC (rotation and offset already applied),
  an opacity and front / back. All lens and fit math stays in `src/mirai` (`src/viewport` never imports `src/mirai`).
- **Gate and passepartout:** a screen-space overlay that darkens outside the gate and draws its frame. It is drawn
  with the photo step, in both placements.
- **Capture:** `request_capture` draws the meshes without overlays (`viewport.py:1393–1411`); the backdrop is not an
  overlay in "behind" placement, so a LookDev "Bild speichern" in the camera view would include the photo. Proposal:
  the capture skips the backdrop (a flag), so a saved image stays a picture of the model.

### 4.6 Not in this proposal

3D image planes for orthographic front / side drawings (the Wings 3D / Silo use) are a different feature: they belong
to the world, not to a camera. If wanted, they are their own small proposal.

---

## 5. Comparison and matching

### 5.1 Comparison views

| View | What Manu sees | Draw path | New pass? | Stage |
|---|---|---|---|---|
| Foto hinter dem Modell | the model opaque over the photo, photo opacity | backdrop step (§4.5) | no | M1 |
| Drahtgitter über dem Foto | today's wire overlay or display mode WIREFRAME over the photo | existing (`DisplayMode.WIREFRAME`, wire overlay) | no | M1 (free) |
| Foto vor dem Modell | the photo semi-transparent over the shaded model, wire on top | extra overlay under highlights | no | M2 |
| Wischen (split) | photo on one side of a movable vertical line, model on the other | the front quad clipped to the line | no | M2 |
| Umschalten | hold a key: photo at 100 %; release: back | opacity switch | no | M2 |
| Silhouette | the model in one flat unlit colour over the photo | a small program drawing the existing vertex lists (the `EyePass` seam: `vertex_list()`, `uniform_data()`) | small | M4 |
| Kontur | the model's outline as lines over the photo | CPU contour edges (one adjacent face toward the eye, one away) into the line overlay's tool layers, per camera or geometry change | no GPU pass | M4 |
| Differenz | photo minus render | needs the render in a texture (FBO or read-back) | yes, measured first | later |
| Spiegelansicht | model *and* photo mirrored (the painter's check for asymmetry) | a mirrored projection would break the picking parity sites; view-only via capture | yes | later |
| Foto daneben | the photo in its own small window, model unchanged | an ImGui image window (like the iris import view) | no | later, cheap |

The model's own transparency (the Reference ghost path, `alpha < 1`, `gl_render_store.py:1117–1132`) was considered
for "model over photo" and is **not recommended**: ghosts write no depth, so wire and highlights would show through.

### 5.2 Matching: honest staging [H]

1. **Manual alignment (M2).** Look through a camera that is not fixed; orbit, pan and dolly move it (Dynamic Orbit
   Focus applies, so orbiting about the nose works). Two lens gestures (rule 2 of the GUI Bestandsaufnahme:
   "Halten + Maus = Wert"):
   - **dolly zoom:** focal length and distance together, so the head keeps its size on screen and only the
     perspective changes. This is the main likeness lever;
   - **focal length** alone.
   Then the photo fit (rotation, offset for a cropped photo) and "Kamera fixieren". Afterwards Manu models in the
   fixed camera view.
2. **Landmarks (M5, only after LC-D7).**
   - Manu places 2D marks on the photo in the viewport (the point overlay exists) and links each to a vertex
     (hover and pick exist).
   - A NumPy Levenberg–Marquardt solve minimises the reprojection error. The pose is solved with the focal length
     fixed (6 unknowns, 6–8 marks recommended); the focal length is solved too only on ¾ or profile photos.
   - No OpenCV: it is not a dependency, and NumPy is pinned for the reference PC (`requirements.txt`).
   - After the solve, **residual arrows** per mark show where the model differs from the person. That is the
     likeness feedback itself, not only a camera aid.
3. **Not planned:** automatic face-landmark detection (machine learning). It needs new dependencies and sends no
   value the manual marks lack.

Honest limits:
- **Frontal photos:** the face's depth (≈ 10–15 cm) is small against a portrait distance (≈ 1 m), so focal length
  and distance are nearly interchangeable from the front. This is the dolly-zoom ambiguity [E]. A solve would be
  ill-conditioned there and a manual match uncertain, so the focal length should come from EXIF or the photographer.
- **Lens distortion** is not modelled. At 50 mm equivalent and longer it is small; phone wide angles and selfies
  show both strong perspective and distortion, and the edges will not match.
- **The model is not yet the person.** A perfect camera match is impossible while the likeness is wrong. Matching
  should use stable landmarks (eye corners, nose bridge, ear points, chin), not the features being modelled.

### 5.3 Reuse of the iris landmark UI

Reuse the **pattern**, not the widget:
- a pure model (`pick_handle`, `drag_handle`, `checked`);
- a draft that is UI state;
- one Undo step on commit (§1.2 item 17).

The widget itself does not fit: its 320 px in-panel view is too small for face landmarks, and the marks belong in the
viewport over the gate, where the linked vertices are.

---

## 6. UX

### 6.1 Room or viewport mode [H, O LC-D1]

**Recommendation: a viewport state „Kameraansicht“, not a room.**
- Modelling to the photo is the main activity, so every modelling tool must work in it. A room would push Manu out
  for each fix (the argument of LD-D2).
- It touches only the camera and the backdrop, so it combines with LookDev (judge the likeness under portrait light),
  Morph sliders (match an expression photo), pose and SubD.
- **Rule R-1** holds by construction: entering or leaving never touches pose, morph weights, gaze or SubD.
- **Other rooms:**
  - allowed in the Paint and Weight rooms (camera only, no input session);
  - opening the **Eye Lab** leaves the camera view first, because the Eye Lab owns the camera;
  - the LookDev framing buttons (Front / ¾ / Profil, `lookdev_model.py:38`) are disabled in the camera view.

Alternative, recorded and not recommended: an exclusive "Likeness Room". It would forbid the LookDev combination and
duplicate the room frame for no gesture of its own.

### 6.2 Entering and leaving [H]

- **Entry:**
  - "Durchschauen" on a camera row in the panel;
  - a SPACE menu row „Kameraansicht“;
  - later a key (suggestion `0`, §6.5).
- **On entry:** the free view is saved:
  - target, distance, yaw, pitch, FOV, ortho, near, far;
  - the snapped-view and orbit-anchor state, as `restore_camera_state` clears it (`application.py:2749`).

  The camera then takes the likeness camera's pose, lens, clip and perspective.
- **On exit:** the free view comes back exactly. A test pins bit-identity of all eight fields.
- **Save while looking through:** the file's `view.camera` gets the *saved free view*, not the likeness camera's
  (the room precedent: `save_scene_file` writes the restored display, `application.py:2785–2792`).
- **A scene load** leaves the camera view.

### 6.3 Navigation in the camera view [O LC-D3]

Recommendation:
- **not fixed** (while matching): Alt+LMB orbit, Alt+Shift+LMB pan and the wheel move the likeness camera (Manu's
  bindings unchanged);
- **„Kamera fixieren“** (while modelling to the photo): the same navigation leaves the camera view into the free view
  without touching the camera, and `0` (or the panel) returns.
- `U` (ortho) and a Shift snap leave the camera view, because a likeness camera is perspective.

Blender's "Lock Camera to View" splits it the same way.

### 6.4 Panel and HUD [H]

- **A panel „Kamera“** in the right column (like Bone and Auge), with a toggle „Kamera [+]“ in the toggle row
  (`imgui_layer.py:375–410`). Not left: the room panels (LookDev, Paint, Weight) sit left top, and the camera view
  combines with them.
- **About 15 visible controls; the rest under „Mehr“** (the LookDev rule):

| Section | Default view | „Mehr“ |
|---|---|---|
| Kameras | list (name, „Durchschauen“), „Neu aus Ansicht“, rename (text field), delete | — |
| Objektiv | Brennweite (mm, slider + 24 / 35 / 50 / 85 / 105 / 135 / 200), Sensor (Kleinbild-Äquivalent · Vollformat · APS-C · eigene) | Einpassen (Auto / Breite / Höhe / Diagonale), Clip nah / fern, Rand (overscan) |
| Foto | Laden …, Deckkraft, Hinter / Vor dem Modell, Ein / Aus | Drehen, Verschieben, beschnittenes Foto (Skalieren), Spiegeln, EXIF-Vorschlag übernehmen |
| Vergleich | Überblenden · Wischen · Umschalten (M2), Drahtgitter | Silhouette, Kontur (M4) |
| Ansicht | Kamera fixieren, Abstand (Einheiten, „≈ m bei 1 Einheit = 1 cm“) | Rand abdunkeln |

- **HUD:** in the camera view the status strip shows „Kamera ›Front‹ · 85 mm“ and, when fixed, a mark „fixiert“
  (GUI_STAGE1_HUD layer "Warnmarke"). The gate and passepartout are the viewport's own feedback.
- A held slider previews and release commits (the eye and paint pattern).
- Layout and labels stay `PROVISIONAL` until Manu's GUI verdict.

### 6.5 Suggested bindings (suggestions only; `config/keymap.json` unchanged until Manu's „Taste passt“)

| Suggestion | Command | Why / check |
|---|---|---|
| `0` tap | Kameraansicht an / aus (the active camera) | free in code defaults and keymap (§1.2 item 16); Blender's Numpad 0 without numpad (V-2) |
| `0` hold | photo at 100 % while held (Umschalten) | the tap / hold pattern of `N` (`morph_targets.py:168`) |
| hold `A` + mouse left / right | dolly zoom (perspective changes, head size stays) | plain `A` free; `Shift`/`Ctrl`/`Alt`+`A` are taken, so no modifier variant |
| `Alt` + wheel (camera view only) | focal length in steps | `Alt`+wheel is bound only in the brush context the Paint and Weight rooms share (`bindings.py:470–471`); the camera view inside those rooms would need another chord |

No key for the panel or for photo fit: they are occasional.

---

## 7. What stays untouched (gates)

- Camera changes never invalidate geometry (`camera_revision` only).
- `camera_revision` keys `PickCache` and GPU picking: every lens or view change bumps it.
- The duck-typed contract: `src/viewport` sees matrices, a texture and NDC corners, never `src/mirai`.
- The matrix convention and the symmetric frustum (`camera.py:250–287`).
- `project_to_screen` ≡ `screen_projector` bit for bit (`tests/test_camera.py`).
- Manu's navigation bindings (`keymap.json:4–5`), the BindingSet as the input truth.
- The Core freeze (M1–M2 need no Core change; M3 only after LC-D2 and Manu's go) and the additive format pattern.
- The Worklight look: the backdrop step draws nothing while no photo is shown, so `test_gl_face_data_layout.py`,
  `test_gl_shading.py` and `test_gl_texture.py` stay byte-identical.

---

## 8. Risks

| Risk | Why | Mitigation |
|---|---|---|
| Wrong FOV in the free view | the Eye Lab snapshot and `view.camera` writing ignore the camera view; a save could store 85 mm as the free view (§1.2 item 11) | camera view saves and restores all eight fields; save writes the free view; the Eye Lab leaves the camera view first; tests |
| Confusion "where am I looking from" | two kinds of view in one window | HUD line, gate and passepartout always visible in the camera view; `0` toggles |
| Accidental camera moves after a match | navigation moves an unfixed camera | „Kamera fixieren“; Undo per gesture from M3 |
| Large photos on 481 MB VRAM | 24 MP photos | downscale to ≤ 4096 px once; one texture per shown photo only |
| JPEG decode speed and orientation | pyglet on Windows, EXIF orientation ignored [H] | decode once on load (status line); own EXIF orientation in M2; measure on the reference PC |
| Privacy (public repository) | photos of real people beside scenes in `scenes/` | separate ignored `<stem>_photos/` folder (LC-D9); a test checks the `.gitignore` rule exists |
| Model not at true scale | `Gollum_Head_05` is 1.2 units wide | matching is scale-invariant; distances in units, metres only as a hint |
| Depth precision after raising far | far up to 8000 at long distances | likeness cameras set near = 1; interactive far follows the distance, unchanged below 50 |
| HUD covers the gate | strip at the top / bottom | overscan default 1.1; measured in the M1 test |
| Frontal focal ambiguity, lens distortion | physics (§5.2) | EXIF focal length, ≥ 50 mm equivalent photos recommended in the panel hint |
| Object-path ripple of option A | an object without geometry in every loop | the group precedent's guards; a test that a camera object is invisible to every component path (like RF-2) |
| Naming collision "Reference" | existing object role | "likeness camera", "photo", "backdrop" in code and UI |

---

## 9. Test strategy

**Existing tests that guard what must stay:**

| Test | Guards |
|---|---|
| `tests/test_camera.py` | orbit / dolly / frame math, `project_to_screen` ≡ `screen_projector` |
| `test_camera_ortho.py`, `test_camera_orbit_about.py` | ortho depth range, rigid orbit about a point |
| `test_camera_gate5_matrices.py` | the matrix convention |
| `test_camera_gate7_integration.py` | one camera instance bound to the viewport |
| `test_picking_equivalence.py`, `test_picking_cache.py`, `test_gl_gpu_picking.py` | CPU / GPU picking parity, cache keyed on `camera_revision` |
| `test_object_space.py` | the `ObjectSpaceCamera` interface |
| `test_view_state.py` | `view.camera` round trip, a broken section skipped, the Core ignores `view` |
| `test_room_rule.py`, `test_lookdev_room.py` | R-1, a save inside a room writes the restored view |
| `test_application_view_snap.py`, `test_application_orbit_focus.py` | snapped views, Dynamic Orbit Focus |
| `test_viewport_extra_overlays.py` | overlay order |
| `test_gl_face_data_layout.py`, `test_gl_shading.py`, `test_gl_texture.py` | the Worklight byte-identical |
| `test_gui_imgui_window.py` | the GL-state hygiene pattern for a new draw step |

**New tests, by slice:**

- **M1 (headless):**
  - lens table: 50 mm full frame → 26.99° vertical, 85 mm → 16.07°, round trip focal ↔ FOV within 1e-12;
  - every fit mode;
  - gate rectangles for window wider / narrower than the photo;
  - the `_tan_half_fov` refactor leaves every existing camera test result bit-identical;
  - enter / leave restores the eight free-view fields bit-identically;
  - a save in the camera view writes the free view;
  - R-1 in the camera view;
  - the far coupling changes nothing below a distance of 50.
- **M1 (GL, `xvfb-run`, own process):**
  - **self-consistency round trip:** render a test scene through a likeness camera, capture it, load the capture as
    that camera's photo, draw it behind with opacity 1 and the model hidden, capture again. The two images agree
    inside the gate (mean absolute difference below 1/255, threshold `PROVISIONAL`). This proves gate, fit and lens
    together without a human;
  - the backdrop step leaves GL state as found;
  - with no photo the Worklight is byte-identical.
- **M2:**
  - offset ≡ lens shift: a point projected by an asymmetric-frustum reference implementation (test-only) lands on the
    same photo pixel as the symmetric camera plus the photo offset;
  - rotation ≡ roll, the same way;
  - EXIF parser on small synthetic JPEGs written by the test (no third-party photos in the repository);
  - wipe and flip state.
- **M3:**
  - Core contract tests: v18 only by content, round trip, Undo, duplicate, mirror and `replace_scene` carry;
  - a camera object is never the edit object and is invisible to every component path;
  - photo copies go to `<stem>_photos/`, and the `.gitignore` rule exists;
  - an older-format file is the same text.
- **M4:** contour edges of a sphere from known views against an analytic outline; silhouette pass GL hygiene.
- **Reference PC:** one probe row `likeness` in `experiments/drag_cost` (frame time with and without a 4096 px photo,
  behind and in front, 1024 × 768).

---

## 10. Slices

### M1 — „Durch ein Objektiv schauen“ (Discovery, session only, no Core, no format, no key) [H]

- `lens.py` and the `_tan_half_fov` consolidation (bit-identical).
- Session likeness cameras: „Neu aus Ansicht“ (focal length derived from the current FOV), several allowed.
- Kameraansicht enter / leave with the saved free view; save writes the free view; Eye Lab interplay.
- FOV from the gate fit and the window aspect; recomputed on resize.
- Gate and passepartout.
- Photo **behind** the model (PNG / JPEG, downscaled), opacity, on / off, in Worklight and LookDev.
- Clip per camera; the distance clamp coupled to far.
- The minimal panel (Kameras, Objektiv, Foto: Laden / Deckkraft / Ein-Aus).

**Measurable:**
- the headless and GL tests of §9 (M1), including the round trip;
- one probe row on the reference PC;
- **Manu's test (≈ 20–30 min):**
  - load a portrait photo whose focal length he knows;
  - set it, look through, match by navigation;
  - judge whether the perspective now "reads" like the photo, compared with today's 26 mm look;
  - check whether the gate and the HUD are in the way.

**Stop points:**
- the architecture AD (next free number, AD-042 `PROVISIONAL`) before any `src/` change;
- Manu's practical test before M2.

### M2 — „Vergleichen und anpassen“ (session only) [H]

- Photo in front, wipe, hold to flip.
- Photo fit: rotation, offset, cropped mode, mirror.
- EXIF focal length and orientation.
- „Kamera fixieren“.
- The dolly-zoom and focal-length gestures (keys only after „Taste passt“).
- The HUD line.

### M3 — „Speichern“ [H]

- LC-D2 decided (recommended: camera object, `SceneObject.camera`, v18).
- Undo per gesture; Outliner row; duplicate / delete.
- Photo copies to the ignored `<stem>_photos/` folder.
- `view.likeness` for opacity, placement and compare mode.
- A camera glyph (frustum lines) in the viewport and its picking in mode `4`.

**Stop point:** Manu's go for the Core field (as LD-2 had).

### M4 — „Silhouette und Kontur“ [H]

The flat silhouette program and the contour lines (§5.1).

### M5 — „Merkpunkte“ (optional, after LC-D7) [H]

Marks on the photo linked to vertices, the pose solve with a fixed focal length, residual arrows.

### Later (not planned)

- Difference view; mirrored view; photo beside the viewport.
- Lens distortion (one radial term).
- Camera roll and lens shift as camera fields.
- Eyes looking at a likeness camera (gaze target).
- Painting projected from a photo (Paint Room).
- Exporting the camera view at the photo's resolution (LookDev P5 bridge).

### Dependencies

| Slice | Depends on |
|---|---|
| M1 | LC-D1, LC-D3, LC-D4, LC-D5; its AD |
| M2 | Manu's M1 verdict |
| M3 | LC-D2, LC-D9; Manu's go for the Core field |
| M4 | M1 (backdrop); independent of M3 |
| M5 | LC-D7; M2 (fit) |

---

## 11. Entscheidungen für dich [O]

Für den Start von M1 brauche ich **LC-D1, LC-D3, LC-D4, LC-D5**. Die anderen können bis zum Praxistest warten.

| # | Frage | Möglichkeiten | Empfehlung | Art |
|---|---|---|---|---|
| **LC-D1** | Soll die Kameraansicht eine **Ansicht** sein (wie Ortho), die du mit LookDev, Morph und Pose kombinieren kannst, oder ein **eigener Raum** wie LookDev? | Ansicht · eigener Raum | **Ansicht** — du modellierst ja gerade *in* dieser Ansicht, und das Foto unter LookDev-Licht zu prüfen ist besonders wertvoll | Product Truth |
| **LC-D2** | Wo sollen gespeicherte Kameras später wohnen (ab M3)? | **A** Kamera als Objekt in der Szene (steht im Outliner, Rückgängig, Duplizieren, Ausblenden gehen sofort; braucht eine kleine Core-Erweiterung) · **B** eigene Kameraliste in der Szene (Core; Outliner-Bereich und Befehle neu bauen) · **C** nur als Ansicht gespeichert (kein Core, aber kein Rückgängig und kann beim Speichern mit einer älteren Version verloren gehen) | **erst nach dem Praxistest von M2 entscheiden; dann A** | Intent / Promotion |
| **LC-D3** | Was passiert, wenn du in der Kameraansicht mit Alt+Maus navigierst? | bewegt die Kamera mit · verlässt die Kameraansicht | **bewegt die Kamera mit**, und es gibt einen Schalter **„Kamera fixieren“**: dann führt Navigieren in die freie Ansicht, und die Kamera bleibt, wo sie ist | Product Truth |
| **LC-D4** | Ein Foto ist schief gehalten: Soll das **Foto** gedreht werden oder die **Kamera** gekippt (dann steht dein Modell schief am Bildschirm)? | Foto drehen · Kamera kippen | **Foto drehen** — gleiches Ergebnis beim Vergleichen, und Auswahl und Werkzeuge bleiben unberührt | Product Truth |
| **LC-D5** | Brennweite standardmäßig als **Kleinbild-Äquivalent** in mm (das, was Handys und die meisten Angaben liefern), echte Sensorgrößen als Auswahl? | Kleinbild-Äquivalent als Standard · echter Sensor als Standard | **Kleinbild-Äquivalent** | Intent |
| **LC-D6** | Reihenfolge der Vergleiche: zuerst Foto hinter/vor dem Modell mit Deckkraft, Drahtgitter, Wischen und Umschalten (M1/M2); Silhouette und Kontur später (M4)? | so · Silhouette früher | **so** | Priorität |
| **LC-D7** | Automatisches Einpassen über Merkpunkte (du setzt Punkte aufs Foto und auf das Modell, Mirai rechnet die Kamera aus): wann? | gleich nach M2 · nur, wenn das Einpassen von Hand im Praxistest zu langsam oder zu ungenau ist · nie | **nur, wenn Handarbeit nicht reicht** | Priorität |
| **LC-D8** | Ein Foto pro Kamera (Front, ¾ und Profil sind drei Kameras)? | ein Foto pro Kamera · mehrere Fotos pro Kamera | **ein Foto pro Kamera** | Intent |
| **LC-D9** | Fotos echter Menschen sollen **nie** im öffentlichen Repository landen: Kopien in einem eigenen Ordner `<Szene>_photos/`, den Git ignoriert? | ja · Fotos wie andere Bilder behandeln | **ja** | Intent |
| **LC-D10** | Wann soll M1 kommen, verglichen mit den offenen LookDev- und Rig-Themen? | — | deine Wahl | Priorität |
| (Tasten) | Jede Taste (Vorschläge §6.5) erst nach deinem „Taste passt“ im Praxistest | — | — | Product Truth |

Nicht hier entschieden und unverändert: Manus Navigationstasten, D-L9 (Räume ohne Taste), R-1, die LookDev-Entscheidungen
LD-D1 … LD-D16.

---

**Next step:** Manu's answers to LC-D1, LC-D3, LC-D4 and LC-D5, then the architecture AD for M1 (AD-042,
`PROVISIONAL` number). The AD belongs in a **fresh session**: this one carries a long inventory context, and the AD
plus M1 are a self-contained Type C slice. Suggested model: **Claude Opus 5.5, reasoning effort high** (camera
contract and bit-identity discipline, a new draw step in both shading paths); M1's implementation after the AD can run
on Sonnet 5 at high effort.
