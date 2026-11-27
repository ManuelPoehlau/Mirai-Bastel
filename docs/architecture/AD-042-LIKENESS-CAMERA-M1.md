# AD-042 — Likeness Camera M1 („Durch ein Objektiv schauen“): lens math, session cameras, the camera view, the backdrop

**Status:** **ACCEPTED (Manu 2026-11-27, chat: „AD-042 build M1“ = accepted as proposed, §2's engineering values
and §16's start values unchanged) — M1 BUILT (2026-11-27)**, implementation note §17. Architecture Gate (Type C).
Was PROPOSED (2026-11-27, docs only, number checked free at `450ebd5`). Still open: Manu's probe run and practical
test (§11.3, §15), Q-LC-1 … Q-LC-3 (§16), every key (§11.4).
**Basis:** [LIKENESS_CAMERA_ARCHITECTURE_UX_PROPOSAL_2026-11-27](../design/LIKENESS_CAMERA_ARCHITECTURE_UX_PROPOSAL_2026-11-27.md)
§2–§7, §9 (M1 tests), §10 (M1), and Manu's decisions **LC-D1, LC-D3, LC-D4, LC-D5** (2026-11-27, chat; entered in its
§0). LC-D2, LC-D6 … LC-D10 and every key stay open; M1 needs none of them.
**State inspected:** `main` @ `450ebd5` ("docs(camera): likeness camera & reference matching proposed") = the working
branch at the same commit, clean tree. `git diff df02a00 450ebd5 -- src tests experiments config .gitignore` is empty:
the code the proposal read is the code checked here. Every code statement this AD relies on was re-checked at
`450ebd5` (§1); where the proposal is wrong or incomplete, §1 says so and the AD follows the code.
**Structural model:** [AD-038](AD-038-LOOKDEV-ROOM-M1.md) (room frame, R-1, background pass, capture).
**Extends:** [VIEWPORT_V02_ARCHITECTURE §4.1](../viewport/VIEWPORT_V02_ARCHITECTURE.md) (camera contract, ortho and
orbit-about addenda; this AD adds a third addendum when built, §3.5, §6),
[WP_DYNAMIC_ORBIT_FOCUS](../WP_DYNAMIC_ORBIT_FOCUS.md), [GUI_STAGE1_HUD](../design/GUI_STAGE1_HUD.md) (one strip
entry). Does **not** touch [CORE_V1_FREEZE](CORE_V1_FREEZE.md): no Core field, no format version, no History in M1.

Evidence tags as in the proposal: **[V]** verified in code at `450ebd5` (file:line), **[M-C]** checked in the container
(arithmetic run, no product code), **[P]** decided by this AD if accepted (engineering, `PROVISIONAL` where marked),
**[E]** estimate, **[O]** open for Manu. New class, file, panel and label names are `PROVISIONAL` until built.

---

## Kurzfassung für Manu (Deutsch)

- **Was dieses AD festlegt:** die verbindliche Bauanleitung für M1 „Durch ein Objektiv schauen“. Nach deiner Freigabe
  kann M1 ohne weitere Designfragen gebaut werden. Es bleibt bei deinen vier Antworten: **Ansicht** (kein Raum),
  **Kamera bewegt sich mit** (plus „Kamera fixieren“), **das Foto** wird gedreht (in M2), **Kleinbild-Äquivalent**.
- **Objektiv:** Eine reine Rechendatei `lens.py` rechnet Brennweite, Sensor und Einpassen in den Bildwinkel um, den
  die eine Viewport-Kamera schon hat. Die Kamera bekommt keine neue Mathematik. Ihre sieben gleichen
  `tan(fov/2)`-Rechnungen werden zu einer Hilfsfunktion zusammengelegt; das Ergebnis bleibt **bitgenau** gleich
  (nachgewiesen in §3.4).
- **Kameras:** nur für die Sitzung (nichts wird gespeichert). „**Neu aus Ansicht**“ legt eine Kamera genau dort an, wo
  du gerade schaust, mit der Brennweite, die das heutige Bild ergibt. Beim Durchschauen springt deshalb nichts, nur der
  Rahmen erscheint.
- **Kameraansicht:** Beim Betreten merkt sich Mirai deine freie Ansicht (acht Kamerawerte plus Einrasten). Beim
  Verlassen kommt sie **bitgenau** zurück. Speichern in der Kameraansicht schreibt die freie Ansicht in die Datei,
  nicht die Kamera. Szene laden verlässt die Kameraansicht.
- **Navigation (LC-D3):** Alt+Maus und Rad bewegen die Kamera mit, Dynamic Orbit Focus inklusive. Ist die Kamera
  **fixiert**, führt dieselbe Bewegung zurück in deine freie Ansicht, und die Kamera bleibt, wo sie ist. „Kamera
  fixieren“ kommt deshalb schon in M1 (der Vorschlag hatte es in M2).
- **Was die Kameraansicht verlässt:** `U` (Ortho), Shift-Einrasten, das Eye Lab, Szene laden. **Gesperrt** in der
  Kameraansicht: die LookDev-Rahmung (Front / ¾ / Profil) und „Auge rahmen“. **Geht** mit ihr: LookDev, Paint Room,
  Weight Room, Morph-Regler, Pose, SubD und alle Modellierwerkzeuge.
- **Foto:** hinter dem Modell, mit Deckkraft, im Worklight und in LookDev. Es wird genau so gezeigt, wie es ist (nicht
  belichtet, nicht getont). Fotos größer als 4096 px werden einmal verkleinert. Ein Knopf „90° drehen“ hilft bei
  Handyfotos, bis M2 die EXIF-Ausrichtung liest. Das Foto wird nirgends hin kopiert und nicht gespeichert.
- **Rahmen:** ein Rahmen im Fotoformat mit abgedunkeltem Rand („Passepartout“). „Bild speichern“ in LookDev zeigt
  weiter nur das Modell, ohne Foto und Rahmen.
- **Weiter weg:** Die freie Kamera darf bis Abstand 2000 statt 200 (für Kameras im echten Maßstab). Unterhalb von
  Abstand 50 ändert sich **nichts** (das prüft ein Test). Ein bestehender Test, der die alte Grenze 200 festschreibt,
  wird dafür angepasst; das ist die einzige erwartete Teständerung.
- **Tests:** Rechentabellen, bitgenaue Rückkehr, Speichern, Navigation, R-1, und ein GL-Rundlauf: Bild durch die
  Kamera aufnehmen, als Foto laden, wieder aufnehmen, beide gleich. Dazu eine Messzeile für deinen PC.
- **Dein Praxistest** (≈ 25 min, §15): Foto mit bekannter Brennweite laden, durchschauen, per Navigation einpassen,
  Perspektive gegen den heutigen 26-mm-Look beurteilen, prüfen, ob Rahmen und Leiste stören.
- **Deine Antwort jetzt:** nur, ob du AD-042 freigibst. Drei kleine Punkte (Rand 1,15; Sprung beim Navigieren mit
  fixierter Kamera; Kameras bleiben nach Szene laden) haben Startwerte und können im Praxistest geklärt werden (§16).

---

## 1. Code check at `450ebd5` (what the proposal said, what the code says)

### 1.1 Verified as the proposal states [V]

| # | Item | Code at `450ebd5` |
|---|---|---|
| C1 | Exactly seven `tan(fov/2)` recomputations, all in `camera.py` | `frame_on_bounds` `camera.py:133` (`math.tan(math.radians(fov_degrees / 2.0))`), `_half_height` :201, `build_projection_matrix` :275, `screen_to_ray` :306, `project_to_screen` :354, `screen_projector` :389, `pan` :421 (all `math.tan(math.radians(self.fov_degrees) / 2.0)`) |
| C2 | The dolly clamp in two places | `OrbitCamera.dolly` `camera.py:114`, `view_state._apply_camera` `view_state.py:234` |
| C3 | `view.camera` holds target, distance, yaw, pitch, fov, ortho; not near / far | `view_state.py:68–75`; `_apply_camera` checks `1 ≤ fov < 180` (`:230`) and calls `restore_camera_state` (`:240`) |
| C4 | `restore_camera_state` clears the snapped view, `_ortho_auto` and the orbit anchor | `application.py:2749–2756` |
| C5 | A save inside a room writes the room's restored display values | `application.py:2784–2792` (LookDev and Paint Room `saved_view` overrides after `view_state.capture`) |
| C6 | Eye Lab snapshot without FOV | `application.py:1046–1049`; close restores it (`:1063–1067`); `open_eye_lab` is refused while LookDev is open (`:1040–1042`); `open_lookdev` closes the Eye Lab (`:1327–1328`) |
| C7 | LookDev background: full-screen triangle, depth off, state restored, colour "as picked" | `lookdev_pass.py:373–402`, `lookdev_shaders.py:938–955`; called `viewport.py:1550` |
| C8 | Worklight background = the clear colour only | `main.py:715` |
| C9 | Under-highlight overlays draw before wire, highlights, points | `viewport.py:1471–1475` |
| C10 | Capture: one extra `_render_meshes()` without overlays, read back, cleared | `viewport.py:1393–1409`, `request_capture` `:1411–1415`; only caller `save_lookdev_image` `application.py:2023` |
| C11 | Aspect reaches the viewport through `on_camera_changed(aspect)` | `viewport.py:1254–1262`, `Application._camera_changed` `application.py:7250–7252`; `set_viewport_size` `:6212–6217` (window resize: `main.py:514–516`) |
| C12 | Image readers: PNG own decoder, everything else pyglet; top row first | `paint/library.read_image_rgba` `library.py:282–290`, `iris_import.read_rgba` `iris_import.py:223–234`, `_rgba_of` `:199–220` |
| C13 | A box downscale helper with a limit argument exists | `paint/library.reduce_rgba(rgba, limit)` `library.py:179–186` (`_box_down`: integer factor `ceil(max/limit)`) |
| C14 | The pyglet upload of an RGBA array (bottom-up rows) | `eye_panel._set_texture` `eye_panel.py:306–319` |
| C15 | The LookDev framing buttons | `lookdev_model.VIEWS` `lookdev_model.py:38`, `frame_lookdev` `application.py:1734–1743`, button `lookdev_panel.py:163` |
| C16 | The toggle row and the right-column panels | `imgui_layer.py:383–410` (toggle buttons), `:424`, `:443`, `:452` (right-column positions) |
| C17 | Rooms in the SPACE menu without keys | `menus.py:347–355` |
| C18 | The file browser for "Laden …" | `gui/file_browser.py` (`request(kind, title, filters, on_pick)`), used by `lookdev_panel.browse_map` `lookdev_panel.py:261–267` |

### 1.2 Corrections and additions (the AD follows the code)

| # | Finding | Consequence in this AD |
|---|---|---|
| K1 | **Raising the dolly ceiling changes one existing assertion.** `tests/test_camera.py:67–72` (`test_dolly_clamps_distance`) asserts `distance <= 200.0` after `dolly(1e6)`. The proposal's "every existing test result stays as they are" (§2.5) is wrong for this test. | The assertion moves to `MAX_DISTANCE`, named in the M1 commit as the one intended test change (§6.3). |
| K2 | **Today the far plane cuts the model at the dolly ceiling.** `far = 200` equals the maximal distance 200, so at full zoom-out the target sits on the far plane and the half of the model behind it is clipped [V arithmetic, `camera.py:96`, `:114`]. | The clip coupling (§6) fixes this as a side effect above distance 50 only. |
| K3 | **`frame_on_bounds` has no upper clamp** (`camera.py:137`: `max(…, 0.5)` only). A large object frames beyond 200 and is clipped by `far = 200` today. | The coupling follows there too (§6.2); the missing clamp stays (no behaviour change below 50). |
| K4 | **`near` / `far` are read only inside `camera.py`** (grep `\.near\b`, `\.far\b`, `ortho_back` in `src/`; `ObjectSpaceCamera` forwards no clip, `object_space.py:144–200`). | The coupling is a camera concern and stays in the camera (§6). |
| K5 | **`GLRenderStore.texture(path)` does not fit the photo.** It loads the *file* through pyglet at full size with `GL_REPEAT` (`gl_render_store.py:480–503`, `:610–624`); the 4096 px cap needs the capped array. | The backdrop uploads its own texture from the array (§7.5). Deviation D1. |
| K6 | **The morph target's editing view moves the camera directly.** `MorphController._pan` writes `camera.target` and calls `on_camera_changed` (`controllers/morph.py:561–567`), on entering (`:534`) and on leaving the view (`:582`); the shift is readable as `services.morph_view_shift` (`services.py:151–158`). The proposal does not mention it. | The camera view treats the shift as a translation of the whole picture (§5.6). |
| K7 | **The orbit gesture keeps virtual angles** (`_orbit_virtual`, `application.py:6636–6655`); Shift during a running orbit re-applies them at once (`set_shift_held`, `:3866–3869`). | Leaving the camera view in the middle of a gesture re-seeds them (§5.2). |
| K8 | **The capture skip cannot be unconditional.** The proposal's own M1 round trip (§9) captures the photo; an unconditional "capture skips the backdrop" would make it capture the clear colour. | `request_capture(callback, *, backdrop=False)` (§7.4). Deviation D3. |
| K9 | **The proposal's round trip is self-consistent, not a lens proof.** Gate, crop and photo quad all use the same gate rectangle, so a wrong gate formula would still pass it. | An independent pinhole check is added (headless §10.2 T-L9, GL §10.3 G2). Deviation D8. |
| K10 | **Free-view depth precision at the new ceiling.** With `near = 0.05`, a distance of 2000 gives ≈ 4.8 units depth step [E, `d² / (near · 2²⁴)`], i.e. z-fighting. | `near` follows the distance too, with the same "no change below 50" (§6.1). |
| K11 | Overscan 1.1 leaves ≈ 35 px above and below a height-limited gate in a 768 px window [E]; the menu bar plus toggle row are ≈ 44 px [E, ImGui default font, `imgui_layer.py:383`], the compact HUD strip at the bottom ≈ 66–84 px [E, `hud.py:682`: `(lines + 1) · 18 + 12`]. | Default 1.15 (≈ 50 px) [P]; Manu's test judges it (§15, Q-LC-1). Deviation D6. |

---

## 2. What this AD builds on, and what it decides

**Artist decisions (Manu, 2026-11-27, proposal §0):**
- **LC-D1 „Ansicht“:** the Kameraansicht is a view state; it combines with LookDev, Morph and Pose; every tool works.
- **LC-D3 „Kamera bewegt sich mit“:** navigation moves the likeness camera; „Kamera fixieren“ makes navigation leave into
  the free view and the camera stays.
- **LC-D4 „Das Foto“:** a tilted photo is matched by rotating the photo (built in M2; M1 keeps the camera roll-free, so
  nothing in M1 can contradict it).
- **LC-D5 „Kleinbild-Äquivalent mm“:** focal length in 35 mm equivalent by default; real sensors as a choice.

**Engineering decisions of this AD (all `PROVISIONAL` until Manu's M1 practical test):**

| # | Item | Value | Where |
|---|---|---|---|
| E1 | Names | `lens.py`, `Lens`, `LikenessCamera`, `LikenessPhoto`, `LikenessSession`, `FreeView`, `Backdrop`, `BackdropPass`; UI „Kamera“, „Kameraansicht“, „Foto“ | §3–§8 |
| E2 | Overscan default | 1.15 (range 1.0 … 1.5), one value for the session | §3.3, K11 |
| E3 | Clip defaults of a new camera | `near = min(1.0, max(0.05, distance / 100))`, `far = max(1000, 8 · distance)` | §6.4 |
| E4 | Photo size cap | 4096 px on the longer side (integer box factor) | §8.1 |
| E5 | Far (and near) coupling | `near = max(0.05, distance / 1000)`, `far = max(200, 4 · distance)`; `MAX_DISTANCE = 2000` | §6 |
| E6 | Backdrop API shape | a frozen `Backdrop` value: gate, passepartout, image + serial, four NDC corners, opacity, placement | §7.1 |
| E7 | Passepartout | black at 50 % outside the gate, a 1 px light-grey gate line | §7.3 |
| E8 | Photo defaults | opacity 1.0, shown | §8 |
| E9 | Focal range | 10 … 600 mm | §3.1 |

---

## 3. The lens math [P]

### 3.1 `src/mirai/viewport/lens.py`

A pure module beside `camera.py`: stdlib only (`math`, `dataclasses`), no import of `camera.py`, `src/viewport`, pyglet
or NumPy. It never touches a camera; the application writes its results into `camera.fov_degrees`.

```python
SENSORS = {   # key -> (label, width mm, height mm, default fit)
    "equiv35":    ("Kleinbild-Äquivalent", 36.0, 24.0, "diagonal"),   # LC-D5 default
    "full_frame": ("Vollformat",           36.0, 24.0, "auto"),
    "aps_c":      ("APS-C",                23.5, 15.6, "auto"),
}                                       # plus "custom": width / height from the Lens itself
FITS = ("auto", "width", "height", "diagonal")
FOCAL_RANGE_MM = (10.0, 600.0)
OVERSCAN_RANGE = (1.0, 1.5)
OVERSCAN_DEFAULT = 1.15

@dataclass(frozen=True)
class Lens:
    focal_mm: float = 50.0
    sensor: str = "equiv35"             # a SENSORS key or "custom"
    sensor_w_mm: float = 36.0
    sensor_h_mm: float = 24.0
    fit: str = "diagonal"

def with_sensor(lens: Lens, key: str) -> Lens                  # a preset's width, height and default fit
def frame_aspect(lens: Lens, photo_size: tuple[int, int] | None) -> float
def effective_sensor(sensor_w_mm, sensor_h_mm, fit, frame_aspect) -> tuple[float, float]
def gate_tan_half(lens: Lens, frame_aspect) -> tuple[float, float]            # (tw, th) of the gate
def view_tan_half_v(lens: Lens, frame_aspect, window_aspect, overscan) -> float
def view_fov_degrees(lens: Lens, frame_aspect, window_aspect, overscan) -> float
def gate_rect_ndc(frame_aspect, window_aspect, overscan) -> tuple[float, float]  # (half_w, half_h)
def focal_from_fov(fov_degrees, lens: Lens, frame_aspect, window_aspect, overscan) -> float
def gate_angles_degrees(lens: Lens, frame_aspect) -> tuple[float, float]       # (horizontal, vertical)
```

Every function raises `ValueError` on a non-finite or non-positive focal length, sensor side or aspect, on
`overscan < 1`, on an unknown fit or sensor key. The setters (§4.3) clamp to `FOCAL_RANGE_MM` and `OVERSCAN_RANGE`;
`lens.py` itself does not clamp (a test can probe any value).

### 3.2 Formulas

Pinhole model; millimetres for focal length `f` and sensor; aspects are width / height.

1. **Frame aspect** `a`: the photo's `w / h` (after the cap and any quarter turn, §8.1); without a photo the sensor's
   `sensor_w_mm / sensor_h_mm` (3 : 2 for the presets).
2. **Effective sensor** `(W, H)` in the frame's aspect, by the fit:
   - `width`: `W = sensor_w`, `H = W / a`;
   - `height`: `H = sensor_h`, `W = H · a`;
   - `auto` (Blender's): `L = max(sensor_w, sensor_h)`; `a ≥ 1`: `W = L`, `H = L / a`; else `H = L`, `W = L · a`;
   - `diagonal`: `D = hypot(sensor_w, sensor_h)` (43.2666 mm for 36 × 24), `W = D · a / sqrt(1 + a²)`,
     `H = D / sqrt(1 + a²)`. For the default `equiv35` a 3 : 2 photo gives exactly 36 × 24, a 2 : 3 portrait 24 × 36,
     a 4 : 3 phone photo 34.61 × 25.96 [M-C]. This makes a phone's "35 mm equivalent" value usable as is
     (proposal §2.3; checked against EXIF samples in M2).
3. **Gate half-angles:** `tw = (W / 2) / f`, `th = (H / 2) / f`.
4. **View** (window aspect `a_w`, overscan `o`):
   - `a_w ≥ a` (window wider than the frame): `tan_half_v = th · o`;
   - `a_w < a`: `tan_half_v = (tw · o) / a_w`.

   Both agree at `a_w = a` (`tw · o / a = th · o`), so a resize across the boundary never jumps.
5. `view_fov_degrees = 2 · degrees(atan(tan_half_v))`.
6. **Gate in NDC** (centred; the frustum stays symmetric):
   - `a_w ≥ a`: `half_h = 1 / o`, `half_w = (a / a_w) / o`;
   - `a_w < a`: `half_w = 1 / o`, `half_h = (a_w / a) / o`.
7. **Inverse** (`focal_from_fov`, used by „Neu aus Ansicht“): `t = tan(radians(fov) / 2)`;
   `a_w ≥ a`: `f = (H / 2) · o / t`; else `f = (W / 2) · o / (t · a_w)`.

**Invariant (the pinhole check, tested §10.2 T-L9):** for a world point at camera coordinates `(x, y, z)` (`z > 0`
along `forward`), its gate-relative position `(ndc_x / half_w, ndc_y / half_h)` equals `(x / (z · tw), y / (z · th))`
in both branches, independent of the window aspect and the overscan. A window resize or an overscan change therefore
never moves the model relative to the gate, and the gate shows exactly what a real camera with that lens records.

Reference values (gate angles, `o = 1`) [M-C]:

| Focal length (KB) | vertical / horizontal angle of a 3 : 2 frame |
|---|---|
| 25.73 mm = today's `fov_degrees` 50 over a 3 : 2 frame | 50.00° / 69.4° |
| 35 mm | 37.85° / 54.43° |
| 50 mm | 26.99° / 39.60° |
| 85 mm | 16.07° / 23.91° |
| 135 mm | 10.16° / 15.19° |
| 200 mm | 6.87° / 10.29° |

### 3.3 Overscan is a view setting, not a lens value

Overscan is the margin the view leaves around the gate. It changes the view's FOV and the gate together and moves
nothing relative to the gate (invariant above). It is therefore one session value (`LikenessSession.overscan`, „Rand“
in the panel's „Mehr“), not a field of `Lens` or of a camera. Default 1.15 (K11).

### 3.4 `OrbitCamera._tan_half_fov()` — one place, bit-identical

```python
def _tan_half_fov(self) -> float:
    """tan(fov/2) of the vertical field of view - the only place it is computed (AD-042 §3.4)."""
    return math.tan(math.radians(self.fov_degrees) / 2.0)
```

The seven sites (C1) call it and keep every operation around it in its order:
- `_half_height`, `build_projection_matrix`, `screen_to_ray`, `project_to_screen`, `screen_projector`, `pan`: the
  expression is **textually the same** as the helper's body, so each result is the same double. `screen_projector`
  still computes `half_h` once outside its closure, `project_to_screen` per call, in the same order as before: the
  `project_to_screen ≡ screen_projector` bit identity (`tests/test_camera.py`) holds by construction.
- `frame_on_bounds` today writes `math.tan(math.radians(fov_degrees / 2.0))`. It becomes `self._tan_half_fov()` and
  the local `fov_degrees` goes. **Bit-identity argument:** CPython's `math.radians(x)` is one rounded multiplication
  `x · (π/180)` (`mathmodule.c`, `math_radians`). `fov / 2.0` is exact for every finite `fov` in the normal range (an
  exponent decrement). Round-to-nearest commutes with scaling by a power of two in the normal range, so
  `radians(fov / 2) = round((fov / 2) · k) = round(fov · k) / 2 = radians(fov) / 2` bit for bit, and `tan` of the same
  double is the same double. Subnormal `fov` values are unreachable (`view_state` admits `1 ≤ fov < 180`; a lens
  gives ≥ 0.4° inside `FOCAL_RANGE_MM` [E]). Checked at `450ebd5`: the 1 799 values 0.1° … 179.9° and 200 000 random
  values in (0.001°, 179.999°): **0 differences** [M-C]. A test pins it (§10.2 T-C1).

`lens.py` does not call the helper (it computes from a lens, not from a camera); the camera's FOV stays its only lens
value (proposal §2.1).

### 3.5 What the camera contract gains (addendum to VIEWPORT_V02 §4.1, written when built)

Only §3.4 (a private helper) and §6 (distance range and clip coupling, one field `clip_follows_distance`). No new
projection, no asymmetric frustum, no roll: the matrices, CPU and GPU picking, `ObjectSpaceCamera`, the ortho test in
the shaders and `screen_projector` read the same fields as today. Every lens or view change bumps `camera_revision`
(PickCache, GPU picking and uniforms key on it).

---

## 4. Session likeness cameras [P]

### 4.1 The record (`src/mirai/likeness.py`)

```python
@dataclass
class LikenessPhoto:
    path: Path                     # where it was read (panel line); nothing is copied or saved in M1
    rgba: np.ndarray               # (h, w, 4) uint8, top row first, capped (§8.1)
    source_size: tuple[int, int]   # (w, h) before the cap (panel line)
    serial: int                    # new on every load and quarter turn: the viewport uploads once per serial

@dataclass
class LikenessCamera:
    name: str                      # „Kamera 1“, „Kamera 2“, ...; renamed in the panel
    target: Vec3                   # the pose in orbit form: target, distance, yaw, pitch
    distance: float
    yaw: float
    pitch: float
    lens: Lens
    clip_near: float
    clip_far: float
    photo: LikenessPhoto | None = None
    fixed: bool = False            # LC-D3 „Kamera fixieren“
```

The pose is stored as **orbit fields**, not as eye / direction / focus distance (proposal §2.5): writing it into the
interactive camera and back is then lossless, and every navigation that works on the free view works on it. M3 maps
it to an object transform (LC-D2) once persistence exists. `fixed` belongs to the camera (a matched camera stays
matched); photo opacity, „Foto ein / aus“, overscan and passepartout are session view values (proposal §4.4) on the
session.

### 4.2 The session (`src/mirai/controllers/likeness.py`, class `LikenessSession`)

Pure state, no GL, no `Application` import (the `LookdevRoom` pattern, `controllers/lookdev_room.py`):
- `cameras: list[LikenessCamera]`, `active: int | None` (the camera the SPACE row looks through: the last one created
  or looked through);
- `view: CameraView | None`: while looking through, `index` and `saved: FreeView` (§5.1);
- `overscan = 1.15`, `photo_opacity = 1.0`, `photo_shown = True`, `passepartout = 0.5`;
- `pending_photo: tuple[int, Path] | None` (the two-step load, §8.1);
- a serial counter for photos.

It has **no interaction session**: the camera view changes no gesture (LC-D1, like LookDev).
The session survives a scene load (it is not document data; Q-LC-3); the camera view does not (§5.5).

### 4.3 Application API (`PROVISIONAL` names; the `open_lookdev` / `set_lookdev_*` shape)

| Method | Effect |
|---|---|
| `likeness` (property) | the session, read by the panel |
| `camera_view_open` (property), `camera_view_text` | §5, §5.7 |
| `likeness_refusal()` | why the camera view cannot be entered now (§5.1), None = it can |
| `new_likeness_camera()` | „Neu aus Ansicht“ (§4.4) |
| `look_through(index)`, `leave_camera_view(status=…)`, `toggle_camera_view()` | §5.1, §5.2; the SPACE row calls the toggle |
| `rename_likeness_camera(index, name)`, `delete_likeness_camera(index)` | rename (≤ 40 characters, empty refused); delete leaves the camera view first when it is the one looked through |
| `set_likeness_lens(index, **changes)` | `focal_mm`, `sensor` (via `with_sensor`), `sensor_w_mm`, `sensor_h_mm`, `fit`; clamped |
| `set_likeness_clip(index, near=…, far=…)` | `0.001 ≤ near < far ≤ 100 000` |
| `set_likeness_fixed(index, on)` | LC-D3 |
| `load_likeness_photo(index, path)`, `turn_likeness_photo(index)`, `remove_likeness_photo(index)` | §8.1 |
| `set_likeness_view(**changes)` | `overscan`, `photo_opacity`, `photo_shown` (clamped) |

A setter that changes the camera looked through re-applies it at once (§5.3). Every setter is view state only: no
History, no Undo, nothing saved (as LookDev M1 under LD-D12). Refusals are status lines.

### 4.4 „Neu aus Ansicht“

1. Pose from the interactive camera: `target − shift` (the morph shift, §5.6; usually zero), `distance`, `yaw`,
   `pitch`.
2. Lens: `Lens()` (equiv35, diagonal) with `focal_mm = focal_from_fov(camera.fov_degrees, lens, a, a_w, overscan)`,
   `a` = the sensor's 3 : 2 (no photo yet), clamped to `FOCAL_RANGE_MM`. Looking through it then reproduces the
   current FOV (within 1e-9° [P], tested), so **nothing jumps**; only the gate appears. Today's view gives ≈ 33.3 mm in a
   1024 × 768 window and ≈ 29.6 mm at 1920 × 1080 (overscan 1.15) [M-C]; 25.7 mm is the gate-filling value
   (`o = 1`, window as wide as the frame).
3. Clip: E3 from the distance (§6.4).
4. Name „Kamera n“ (the lowest unused n); it becomes `active`. Nothing else changes; the view is not entered.
5. From an ortho view: the same, the new camera is perspective; the status line says so
   („Kamera 2 aus der Ansicht (perspektivisch)“).

---

## 5. The camera view state [P]

### 5.1 Entering (`look_through(index)`)

1. **Refused** (status, nothing changed) when: the index does not exist; an interaction session other than `paint` /
   `weight` runs (Knife, Bone chain, …); a paint or weight stroke runs; an object gesture is held (`_gesture`); the
   LookDev room is preparing its shaders. The shape of `lookdev_refusal` (`application.py:1300–1310`).
2. An open **Eye Lab closes first** (`close_eye_lab()`: its camera, isolation and tier come back), because the Eye Lab
   owns the camera (proposal §6.1). The free view saved next is then the view before the lab.
3. **Already looking through another camera:** a switch. The current record is already up to date (§5.4); the saved
   free view stays; continue at step 5. The same camera again: nothing to do (True).
4. **Save the free view** into `FreeView` (frozen): the eight camera fields `target, distance, yaw, pitch, fov_degrees,
   ortho, near, far`, plus `clip_follows_distance` (§6) and the application's `_view_name` and `_ortho_auto` (a
   snapped „Front · Ortho“ comes back as such). **Not** saved: `camera_revision` (it only grows) and the orbit anchor
   (per gesture).
5. **Write the camera:** `target = record.target + shift`, `distance`, `yaw`, `pitch`; `ortho = False`;
   `fov_degrees = view_fov_degrees(record.lens, a, a_w, overscan)` with `a = frame_aspect(lens, photo size)` and
   `a_w = viewport_width / viewport_height`; `near = clip_near`, `far = clip_far`, `clip_follows_distance = False`;
   `camera_revision += 1`.
6. `_view_name = None`, `_ortho_auto = False`, `_orbit_anchor = None`; `view = CameraView(index, saved)`;
   `active = index`.
7. `_camera_changed()`, push the backdrop (§7), `_refresh_hover()`; status „Kameraansicht ›Kamera 1‹ · 85 mm KB“.

Pose, morph weights and current target, gaze and SubD are never touched (R-1 by construction; tested §10.2 T-V8).

### 5.2 Leaving (`leave_camera_view(status=…)`)

1. Write the saved `FreeView` back: the eight fields and `clip_follows_distance` exactly as saved;
   `camera_revision += 1` (never the saved number); `_view_name`, `_ortho_auto` as saved; `_orbit_anchor = None`.
   `restore_camera_state()` is **not** called (it would clear the snapped view, C4); its other two effects
   (`_camera_changed`, `_refresh_hover`) run in step 3.
2. A running orbit gesture (`_orbit_virtual is not None`) continues from the free view: `_orbit_virtual =
   (camera.yaw, camera.pitch)` (K7).
3. `view = None`; push `Backdrop None` (§7.1; frees the photo texture); `_camera_changed()`; `_refresh_hover()`;
   status (default „Kameraansicht verlassen“; `None` = keep the caller's).

The record keeps the pose it had (§5.4). A test pins the bit identity of all restored fields for a free perspective
view with odd values and for a snapped „Front · Ortho“ (§10.2 T-V2).

### 5.3 Re-applying while looking through

A lens change, a photo load / turn / removal, an overscan change or a **window resize** (`set_viewport_size`)
recomputes `fov_degrees` (§3.2) with one `camera_revision` bump, pushes the backdrop (new gate, new corners) and then
runs `_camera_changed()` as today (C11). The pose is not touched, so by the §3.2 invariant the model keeps its place in
the gate (tested §10.2 T-V9). A clip change writes `near` / `far` the same way.

### 5.4 Navigation (LC-D3)

Two small hooks in `Application`, at the existing navigation sites only:

- `_camera_view_route(kind)` **before** the step, `kind` ∈ {`orbit`, `pan`, `dolly`, `snap`, `ortho`}:
  - not in the camera view: nothing;
  - `snap` or `ortho`: leave (status „Kameraansicht verlassen: Ortho und Einrasten gibt es nur in der freien Ansicht“),
    then the step runs on the free view;
  - `orbit` / `pan` / `dolly` and the record is **fixed**: leave (status „Kamera fixiert – freie Ansicht
    (Durchschauen kehrt zurück)“), then the step runs on the free view;
  - otherwise nothing.
- `_camera_view_follow()` **after** the step: in the camera view and not fixed, write the pose back:
  `record.target = camera.target − shift`, `distance`, `yaw`, `pitch` (exact copies; with no morph shift the record
  equals the camera bit for bit).

Sites:

| Site | Route | Follow |
|---|---|---|
| `_navigate` (`application.py:6597–6606`; the pointer orbit and pan, and `_navigate_during_transform`, `:6792`) | `orbit` / `pan` at the start | at the end |
| the wheel zoom (`application.py:6325`) | `dolly` before `camera.dolly` | after it |
| `_apply_orbit_virtual`, the Shift branch (`:6644–6650`; also reached from `set_shift_held`, `:3866`) | `snap` before snapping | — (the view is left) |
| `_toggle_ortho` (`:6782`) | `ortho` at the start | — |

Everything that works on a navigation step works in the camera view unchanged: **Dynamic Orbit Focus** (the anchor is
resolved on the first step against the likeness camera's projection, `application.py:6724–6735`), the pan speed, the
pitch limit ±85°, the dolly clamp, hover coalescing. The rule for a fixed camera is "leave, then the step": the free
view comes back as saved and the gesture continues there; whether that jump feels right is Q-LC-2 (alternative,
recorded: the free view continues from the camera's pose).

### 5.5 Interplay

| Situation | In the camera view | Why |
|---|---|---|
| Scene **save** | `view.camera` gets the saved free view's six fields (after `view_state.capture`, beside the room overrides, C5); nothing of the likeness session is written | proposal §6.2; the file never stores an 85 mm FOV as the free view |
| Scene **load** / reset (`init_scene`) | the camera view is left before the scene is replaced (beside `close_lookdev`, `application.py:754–755`); the session's cameras stay | the new scene frames itself or applies its saved view (`load_scene`, `:2741–2747`) |
| **Eye Lab** open | leaves the camera view first, then opens (`open_eye_lab`) | the Eye Lab owns the camera; its snapshot (C6) then holds the free view's FOV |
| Enter while the **Eye Lab** is open | the Eye Lab closes first (§5.1 step 2) | the LD-D14 pattern |
| **LookDev** open / close | allowed both ways; the camera view stays | LC-D1 |
| LookDev **framing** Front / ¾ / Profil | buttons disabled (tooltip „Kameraansicht: die Kamera ist die Rahmung“); `frame_lookdev` refuses with that status line | proposal §6.1 |
| **„Auge rahmen“** (`frame_eye`, `eye_panel.py:120–123`) | refused with a status line („erst Kameraansicht verlassen“); the Eye Lab calls it after leaving | a framing, like the LookDev buttons |
| **U** (ortho), **Shift snap** | leave, then the command (§5.4) | a likeness camera is perspective |
| Paint Room, Weight Room | allowed in and out; entering the camera view is refused only during a stroke (§5.1) | camera only, no input session |
| Knife, Bone chain | entering refused while their session runs; navigation inside them follows §5.4 | they hold the camera-dependent state of an interaction |
| Morph sliders, pose, SubD, gaze | unchanged (R-1); gaze mode „camera“ looks at the likeness camera, a light that follows the camera follows it | by construction |
| Morph target **editing view** | §5.6 | K6 |
| Window **resize** | §5.3 | C11 |

### 5.6 The morph target's editing view

`MorphController._pan` translates the camera when the editing view opens and back when it closes (K6). A translation
of camera and model together leaves the picture unchanged, so in the camera view the view copy appears where the base
was, against the photo — matching an expression photo works. Rules:
- the shift is not navigation: the record is not written by it; `_camera_view_follow` and „Neu aus Ansicht“ subtract
  the current shift (`services.morph_view_shift`), so the record always holds the pose at the base;
- entering the camera view while an editing view is open adds the shift (§5.1 step 5);
- the saved free view takes the shift too: `MorphController._pan` calls one new services callback
  `services.camera_shifted(shift)` after moving the camera, and the application adds `shift` to `saved.target` while
  looking through. Leaving the camera view inside or after an editing view then gives the free view exactly as
  today's single camera would have it.

### 5.7 What the camera view shows about itself

- `Application.view_text` (`application.py:6616–6621`) returns „Kamera ›Kamera 1‹ · 85 mm“ (plus „ · fixiert“) in the
  camera view, so the status lines and the full HUD strip name it.
- The compact strip lists it as one deviation entry `Kamera`, like SubD (GUI_STAGE1_HUD §7.1: "only deviations"); no
  Warnmarke (the proposal's HUD line was M2; it is one string, and it answers "where am I looking from", risk §14).
- The gate and passepartout are the viewport's own feedback (§7.3).

---

## 6. Clip per camera and the distance / clip coupling [P]

### 6.1 The coupling (free view)

In `camera.py`:

```python
MIN_DISTANCE = 0.5
MAX_DISTANCE = 2000.0                  # was 200 in two places (C2)
NEAR_BASE, FAR_BASE = 0.05, 200.0      # = the field defaults (camera.py:95–96)

def clip_for_distance(distance: float) -> tuple[float, float]:
    """(near, far) the free view keeps at `distance`: today's (0.05, 200) up to distance 50, then proportional."""
    return max(NEAR_BASE, distance / 1000.0), max(FAR_BASE, 4.0 * distance)
```

**No change below distance 50, exactly:** `50 / 1000.0 == 0.05` and `4.0 · 50.0 == 200.0` in binary64 [M-C], and
both expressions are monotone, so every `distance ≤ 50` gives `(0.05, 200.0)` bit for bit — `ortho_back` (= `far / 2`)
and every existing camera result stay as they are. The division by 1000 is written as a division (not `· 0.001`,
which is not exact). Depth step [E, `d² / (near · 2²⁴)`]: distance 50: 0.003 (unchanged); 200: 0.012 (today 0.048,
and today the model is cut by the far plane there, K2); 2000: 0.12 (with `near` fixed it would be 4.8, K10).

### 6.2 Who applies it

- One field `OrbitCamera.clip_follows_distance: bool = field(default=True, compare=False)` and one method
  `follow_clip()`: when the flag is on, `near, far = clip_for_distance(distance)`. No revision bump of its own (the
  callers bump).
- `dolly`: `distance = max(MIN_DISTANCE, min(MAX_DISTANCE, distance · factor))` (the operation order of today's line),
  then `follow_clip()`.
- `frame_on_bounds`: `follow_clip()` after setting the distance (K3: still no upper clamp).
- `view_state._apply_camera`: `max(MIN_DISTANCE, min(MAX_DISTANCE, distance))`, then `camera.follow_clip()`.
- `close_eye_lab`: `follow_clip()` after restoring the distance.
- The constructor keeps its fields (a test camera built at distance 150 keeps `far = 200`,
  `tests/test_camera_ortho.py:28` stays as it is).
- In the camera view the flag is off (§5.1); leaving restores it with the free view (§5.2).

### 6.3 Tests that change, and the ones that must not

- **Changes (intended, named in the commit):** `tests/test_camera.py::test_dolly_clamps_distance` asserts the ceiling
  `MAX_DISTANCE` instead of `200.0` (K1).
- **Must not change:** every other existing test. Before the build commit the implementer greps the tests for a
  distance above 50 reached through `dolly`, `frame_on_bounds` or a view load; a further changed result is a finding to
  report in the implementation note, never a value to update silently.
- **New:** §10.2 T-C2 … T-C4.

### 6.4 Clip per likeness camera

Each record carries `clip_near` / `clip_far`. Looking through writes them as they are (no coupling, flag off).
Defaults for a new camera (E3): `near = min(1.0, max(0.05, distance / 100))`, `far = max(1000.0, 8 · distance)`.
For `Gollum_Head_05` at distance ≈ 6: near 0.06, far 1000; at true scale and 2.8 m (distance 280): near 1.0,
far 2240 [E]. A not-fixed dolly keeps the record's clip: the defaults leave room for an 8× dolly out and a 100× dolly
in, so "the clip cuts my model" needs a deliberate change under „Mehr“ (Clip nah / fern).

---

## 7. The backdrop seam in `src/viewport` [P]

### 7.1 API (`src/viewport/backdrop.py`)

```python
BEHIND, FRONT = "behind", "front"

@dataclass(frozen=True)
class Backdrop:
    gate: tuple[float, float]                       # (half_w, half_h) of the centred gate in NDC, each in (0, 1]
    passepartout: float = 0.5                       # darkening outside the gate (0 = none)
    image: Any = None                               # (h, w, 4) uint8 RGBA, top row first; None = gate only
    image_serial: int = 0                           # a new serial = a new image
    corners: tuple[tuple[float, float], ...] = ()   # the image's 4 NDC corners: top-left, top-right, bottom-right, bottom-left
    opacity: float = 1.0
    placement: str = BEHIND                         # FRONT is drawn from M2 (§7.6)
```

- `Viewport.set_backdrop(backdrop: Backdrop | None)`; `Viewport.backdrop` (read, also headless). `__post_init__`
  validates: four corners when there is an image, `0 ≤ opacity ≤ 1`, `0 ≤ passepartout ≤ 1`, a known placement.
- The boundary holds by construction: `src/viewport` receives a gate, an image, four corners, an opacity and a
  placement — never a lens, a camera record or anything from `src/mirai` (it never imports it, VIEWPORT_V02 §2). All
  lens and fit math stays in `src/mirai` (§3). In M1 the app sends `corners` = the gate rectangle; M2's rotation,
  offset, crop and mirror (LC-D4) are other corners, computed in `lens.py`, with no viewport change.
- The application pushes a new `Backdrop` on every change (enter, switch, re-apply §5.3, photo, opacity, shown /
  hidden) and `None` on leaving. `photo_shown = False` or no photo sends `image = None` (gate only).

### 7.2 Its slot in both shading paths

- **Worklight:** in `Viewport._render_meshes`, the first statement of the Worklight branch (before
  `if self.show_faces:`, `viewport.py:1445`): draw the image when `placement == BEHIND`.
- **LookDev:** in `_render_lookdev`, directly after `passes.draw_background(...)` (`viewport.py:1550`). The photo
  therefore lies on the studio background, not instead of it; with opacity < 1 it blends with it. The AD-040 GPU timer
  wraps `_render_lookdev`, so the room's measured frame includes the photo (honest for its budget).
- Both skip it during a capture unless the capture asks for it (§7.4).
- Drawn **as is**: not exposed, not tone-mapped, not encoded — the LookDev background's rule (AD-038 §8). The Worklight
  framebuffer has no sRGB conversion (no `GL_FRAMEBUFFER_SRGB` in `src/`), so in both paths a photo pixel at opacity 1
  is written with its file value.
- Blending `SRC_ALPHA, ONE_MINUS_SRC_ALPHA` with `alpha = texel.a · opacity`: opacity mixes the photo with whatever lies
  below (the clear colour or the LookDev background) without the viewport knowing that colour. Depth test and depth
  write off: the meshes draw over it as if it were not there.
- `backdrop is None` draws nothing: the Worklight and LookDev frames stay byte-identical (proposal §7).

### 7.3 Gate and passepartout

Drawn in `_render_overlays`, in a fixed slot **after the under-highlight extras and before the wire**:
under-highlight extras (soft shading) → [the front image, M2] → passepartout and gate line → wire → face highlights →
edge highlights → tool lines → other extras → points. The early return of `_render_overlays`
(`viewport.py:1460–1466`) also checks `backdrop is None`.
- Passepartout: the four rectangles outside the gate, black at `passepartout` alpha. It darkens the model and the
  background outside the gate, so the gate reads as "what the camera records" (Blender's passepartout), while the wire,
  selection, hover, points, gizmo, selection box, HUD and panels stay readable on top (the last four are drawn by
  `main.py` after `render()`, `main.py:719–735`).
- Gate line: a 1 px light-grey line loop on the gate rectangle.
- Overlays are never part of a capture (C10), so the gate never is.

### 7.4 The capture

`request_capture(callback, *, backdrop: bool = False)`. The flag is stored with the request and read by the two
slots of §7.2 while `_capturing`. „Bild speichern“ (`save_lookdev_image`) keeps calling it without the flag: a saved
LookDev image shows the model only, never the photo or the gate (proposal §4.5). The round-trip test passes
`backdrop=True` (K8). A second request before the frame replaces the first, flag included (today's rule).

### 7.5 `BackdropPass`: texture and GL-state hygiene (`src/viewport/backdrop_pass.py`)

- Created lazily as `Viewport.backdrop_pass` (the `eye_pass` / `lookdev_pass` pattern, `viewport.py:551–557`,
  `:756–762`); GL objects only on the first draw; `release()` frees them.
- **Geometry:** an empty VAO and `gl_VertexID` (the LookDev background's pattern, `lookdev_shaders.py:938–945`); the
  four corners, the gate and the colours are uniforms. No vertex buffer.
- **Texture:** one `GL_TEXTURE_2D` RGBA8, uploaded from `image` with the rows reversed (bottom-up, as
  `eye_panel._set_texture`), `v = 1` at the top corners; `GL_UNPACK_ALIGNMENT` 1 for the upload and restored;
  mipmapped by binding first and then `glGenerateMipmap`, with `GL_LINEAR` if that fails (the `load_texture` rule,
  `gl_render_store.py:491–499`); `MIN = LINEAR_MIPMAP_LINEAR`, `MAG = LINEAR`, wrap `CLAMP_TO_EDGE`. One texture at a
  time: a new `image_serial` deletes the old one first; the same serial (opacity, shown, corners, a resize) never
  re-uploads; `set_backdrop(None)` deletes it. VRAM ≈ 64 MiB for a 4096 × 3072 photo with mipmaps [E] on a card with
  ≈ 395 MiB free at start (REFERENCE_HARDWARE: 512 MiB, GL 3.3, Core profile); measured in the probe row (§10.4).
- **State:** each draw saves and restores exactly what it sets — depth test, depth write mask, blend enable, blend
  function (RGB and alpha factors), cull face, polygon mode (set to `FILL`: the backdrop must stay filled in any
  display mode), current program, VAO, active texture unit, the texture and the sampler bound on its unit (unit 0;
  sampler set to 0 while drawing). It checks with `gui.imgui_layer.snapshot_gl_state()` plus the texture and sampler
  binding (§10.3 G3).

### 7.6 Front placement (M2) — what the API already allows

`placement = FRONT` is accepted by `Backdrop` in M1 and drawn **nowhere** until M2. M2 adds one branch in the §7.3 slot
(the image under the passepartout, alpha-blended, depth off) and the wipe as a scissor or clip line on the same quad. No
signature changes, no new ordering mechanism (deviation D2 explains why the slot is fixed and not an extra overlay).

---

## 8. Photo loading and the minimal panel [P]

### 8.1 Loading

- `load_likeness_photo(index, path)` from the panel's „Laden …“ (the file browser, C18, filter: images). Two steps, so
  the status line is drawn before a long decode (the LookDev "preparing" pattern): the call stores
  `pending_photo` and shows „Foto wird geladen …“; the next `update_viewport` tick reads it.
- **Read:** `paint.library.read_image_rgba(path)` (PNG through the own decoder, else pyglet: JPEG, BMP, … , C12).
  **Cap:** `paint.library.reduce_rgba(rgba, PHOTO_MAX_PX)` with `PHOTO_MAX_PX = 4096` (an integer box factor
  `ceil(max side / 4096)`: a 6000 × 4000 photo becomes 3000 × 2000; ≤ 4096 stays untouched). Smaller than 16 px on a
  side: refused. `OSError` / `ValueError`: a status line with the reason, nothing changes.
- The record gets a new `LikenessPhoto` (new serial); the status line names the file, the shown size, the source size
  and the time („Foto ›anna.jpg‹: 3000 × 2000 (aus 6000 × 4000), 1,4 s“).
- **„90° drehen“** (`turn_likeness_photo`): the array turned clockwise (`np.rot90(rgba, k=-1)`, contiguous copy), new
  serial; the frame aspect inverts and the camera re-applies (§5.3). It covers phone photos that pyglet loads sideways
  (EXIF orientation is M2, proposal §4.2) and is lossless. It is not the fine photo rotation of LC-D4 (M2).
- „Entfernen“ drops the photo (RAM freed); the gate takes the sensor aspect again.
- **Privacy:** M1 writes no photo anywhere and saves no path; nothing reaches `scenes/` or the repository (LC-D9
  stays open for M3). RAM: one capped array per camera with a photo (≤ 64 MiB each [E]).

### 8.2 The panel „Kamera“ (`src/gui/likeness_panel.py` + pure `src/gui/likeness_model.py`)

Right column (like „Bone“ and „Auge“), toggle „Kamera [+]“ in the toggle row (C16). Pure logic (labels, rows, ranges,
enabled states) in `likeness_model.py`, tested headless; `likeness_panel.py` only draws and calls `Application` (it
holds no state of its own, CLAUDE.md `src/gui/`). Sliders act live (session values, no Undo).

| Section | Shown | Under „Mehr“ |
|---|---|---|
| Kameras | one row per camera: name (double-click renames, the Outliner pattern), „Durchschauen“ / „Verlassen“, „Löschen“; „Neu aus Ansicht“ | — |
| Objektiv | Brennweite (mm, slider 10 … 600 + buttons 24 / 35 / 50 / 85 / 105 / 135 / 200), Sensor (Kleinbild-Äquivalent · Vollformat · APS-C · eigene) | Einpassen (Auto / Breite / Höhe / Diagonale), eigene Breite / Höhe (mm), Clip nah / fern, Rand (1,0 … 1,5) |
| Foto | „Laden …“, Deckkraft, „Foto ein“, file line (name, size) | „90° drehen“, „Entfernen“ |
| Ansicht | „Kamera fixieren“, Abstand („6,2 Einheiten · ≈ 0,06 m bei 1 Einheit = 1 cm“), the gate angles („16,1° × 23,9°“) | — |

About 14 visible controls (the LookDev rule of ≈ 15). The lens and photo rows edit the **active** camera; without a
camera only „Neu aus Ansicht“ is enabled. Hints in the panel: „Fotos ab 50 mm KB vergleichen sich am besten“ (proposal
§5.2), „Nichts wird gespeichert (M1)“.

### 8.3 Menu

One SPACE menu row „Kameraansicht“ / „Kameraansicht verlassen“ beside the rooms (`menus.py:347–355`), shown when at
least one camera exists, calling `toggle_camera_view()`. **No key**; `config/keymap.json` unchanged (proposal §6.5 keys
wait for „Taste passt“).

---

## 9. Files M1 will touch [P]

| File | Change |
|---|---|
| `src/mirai/viewport/lens.py` | new (§3.1–§3.2) |
| `src/mirai/viewport/camera.py` | `_tan_half_fov` (§3.4); `MIN_DISTANCE`, `MAX_DISTANCE`, `clip_for_distance`, `clip_follows_distance`, `follow_clip` (§6) |
| `src/mirai/likeness.py` | new: `LikenessCamera`, `LikenessPhoto`, `FreeView` (§4.1, §5.1) |
| `src/mirai/controllers/likeness.py` | new: `LikenessSession` (§4.2) |
| `src/mirai/controllers/services.py`, `controllers/morph.py` | `camera_shifted(shift)` and its one call in `_pan` (§5.6) |
| `src/mirai/application.py` | the API of §4.3, enter / leave (§5.1–§5.2), the hooks (§5.4), the interplay rows (§5.5), save / init_scene, `set_viewport_size`, `view_text`, the photo tick (§8.1) |
| `src/mirai/view_state.py` | `MIN_DISTANCE` / `MAX_DISTANCE` and `follow_clip` in `_apply_camera` (§6.2) |
| `src/viewport/backdrop.py`, `src/viewport/backdrop_pass.py` | new (§7) |
| `src/viewport/viewport.py` | `set_backdrop`, `backdrop`, `backdrop_pass`, the two slots, the overlay slot, `request_capture(…, backdrop=)` (§7.2–§7.4) |
| `src/gui/likeness_model.py`, `src/gui/likeness_panel.py` | new (§8.2) |
| `src/gui/imgui_layer.py`, `src/gui/menus.py`, `src/gui/lookdev_model.py` / `lookdev_panel.py`, `src/gui/eye_panel.py`, `src/hud.py` | toggle and panel slot; the SPACE row; framing buttons disabled; „Auge rahmen“ disabled; the compact strip entry |
| `src/main.py` | wiring the panel (as for the other panels) |
| `experiments/drag_cost/probe_likeness.py` | new probe (§10.4) |
| tests | §10 |
| docs | VIEWPORT_V02 §4.1 addendum (camera range, clip coupling, `_tan_half_fov`); this AD's implementation note; ATELIER; `docs/README.md` |

Not touched: `src/core/`, the scene format, `config/keymap.json`, `.gitignore`, the shaders of the Worklight, the
LookDev pass and the eye pass.

---

## 10. Tests [P]

All headless tests run in the normal targeted way; the GL tests in their own process
(`xvfb-run -a python -m pytest tests/test_gl_likeness_backdrop.py -q`, CLAUDE.md "GL tests"). Thresholds marked
`PROVISIONAL` may be tightened, not loosened, after the first container run.

### 10.1 Existing tests that guard what must stay (unchanged, run targeted)

`test_camera.py` (except the one assertion of §6.3), `test_camera_ortho.py`, `test_camera_orbit_about.py`,
`test_camera_gate5_matrices.py`, `test_camera_gate7_integration.py`, `test_picking_equivalence.py`,
`test_picking_cache.py`, `test_object_space.py`, `test_view_state.py`, `test_room_rule.py`, `test_lookdev_room.py`,
`test_application_view_snap.py`, `test_application_orbit_focus.py`, `test_viewport_extra_overlays.py`; GL in their own
process: `test_gl_gpu_picking.py`, `test_gl_face_data_layout.py`, `test_gl_shading.py`, `test_gl_texture.py`,
`test_gui_imgui_window.py`, and the LookDev GL pins.

### 10.2 New headless tests

- **`tests/test_lens.py`**
  - T-L1 the table of §3.2 (vertical and horizontal gate angles to 0.01°; 50 mm → 26.99°, 85 mm → 16.07° vertical);
  - T-L2 today's view: `focal_from_fov(50, …, a_w = a, o = 1)` = 25.734 mm ± 1e-3;
  - T-L3 every fit in landscape and portrait; `diagonal` of 3 : 2 is 36 × 24 and of 2 : 3 is 24 × 36 within 1e-12;
  - T-L4 gate rectangles for a window wider, narrower and as wide as the frame; continuity at `a_w = a`;
  - T-L5 round trip focal → FOV → focal within relative 1e-12 over a grid (10 … 600 mm, both branches, `o` 1 … 1.5);
  - T-L6 `ValueError` cases; `with_sensor` presets; `frame_aspect` with and without a photo.
- **`tests/test_camera.py`** (additions)
  - T-C1 `frame_on_bounds` with `_tan_half_fov` equals the old inline formula bit for bit over the 1 799-value grid and
    10 000 random FOVs (the old expression written in the test);
  - T-C2 `clip_for_distance(d) == (0.05, 200.0)` exactly for a grid of `d ≤ 50` and random values; after `dolly`,
    `frame_on_bounds` and `view_state` apply below 50: `near`, `far`, `ortho_back` unchanged;
  - T-C3 above 50 the formula, the ceiling `MAX_DISTANCE`; with `clip_follows_distance = False` nothing follows;
  - T-C4 the constructor keeps its fields.
- **`tests/test_likeness_camera.py`** (application, `TraceStore`, no GL)
  - T-V1 „Neu aus Ansicht“: looking through reproduces the FOV within 1e-9°; the pose equals the camera's; the name;
  - T-V2 enter / leave restores the eight fields, `clip_follows_distance`, `_view_name`, `_ortho_auto` bit for bit,
    from a free perspective view with odd values and from a snapped „Front · Ortho“; `camera_revision` strictly
    increases on both;
  - T-V3 a save in the camera view writes the free view (file read back); nothing of the session in the file;
  - T-V4 a scene load leaves the camera view and keeps the cameras;
  - T-V5 not fixed: an orbit (with and without Dynamic Orbit Focus), a pan and a wheel step move the camera and the
    record equals it bit for bit; fixed: the same steps leave, move the free view, and the record stays bit-identical;
  - T-V6 `U` and a Shift snap leave and then act on the free view; a Shift snap in the middle of an orbit gesture
    continues from the free view's angles;
  - T-V7 Eye Lab: opening it leaves the camera view, entering closes it; `frame_lookdev` and `frame_eye` are refused;
    entering is refused during a held gesture, a Knife session and a paint stroke;
  - T-V8 **R-1:** enter, switch and leave in a pose with a morph mix, gaze on and SubD on: the R-1 snapshot of
    `test_room_rule.py` is bit-identical (the test goes into `test_room_rule.py` beside the room transitions), also
    with LookDev open;
  - T-V9 **pinhole invariant:** for points of a test head, the gate-relative position from `project_to_screen`
    equals `(x / (z · tw), y / (z · th))` within 1e-12, before and after a window resize (wider and narrower than the
    frame) and an overscan change;
  - T-V10 the morph editing view: the camera shifts, the record does not; Tab back gives camera = record; leaving
    inside the editing view and closing it gives the free view today's single camera would have;
  - T-V11 photo: a PNG written by `encode_png` loads through the two-step tick; a 5000 × 100 image is capped to
    2500 × 50; „90° drehen“ swaps the aspect, bumps the serial and re-applies the FOV; an unreadable file changes
    nothing;
  - T-V12 the backdrop pushed to the viewport: gate from `gate_rect_ndc`, corners = the gate in M1, `image = None` when
    hidden, `None` after leaving.
- **`tests/test_gui_likeness_model.py`:** labels, enabled states (no camera, camera view, fixed), the LookDev framing
  rows disabled in the camera view.

### 10.3 New GL tests (`tests/test_gl_likeness_backdrop.py`, own process)

- G1 **round trip** (the proposal's self-consistency test, made exact): window 640 × 480, overscan 1.25, a custom
  sensor 36 × 27 mm with fit `auto` (a 4 : 3 frame), so the gate is exactly 512 × 384 px at (64, 48). Render the test
  scene through a likeness camera, capture (no backdrop), crop the gate → photo; load it as that camera's photo,
  opacity 1, meshes off (`show_faces` off, no entries), capture with `backdrop=True`, crop the gate. Mean absolute
  difference < 1/255 (`PROVISIONAL`; texel centres land on pixel centres, so 0 is expected). A second case with the
  window narrower than the frame (480 × 640). It proves texture orientation, row order, NDC mapping, opacity and the
  capture flag.
- G2 **pinhole in pixels** (K9): a plane object of known height `h` facing the camera at distance `d` (flat colour on
  the clear colour); its measured pixel height over the gate's pixel height equals `h · f / (d · H)` within 1 px. With
  T-V9 this ties lens, gate and the GL matrices together.
- G3 **GL hygiene:** `snapshot_gl_state()` plus the unit-0 texture and sampler binding and the unpack alignment are
  equal before and after the image draw and the gate draw, in the Worklight and in LookDev, and in display mode
  wireframe.
- G4 **nothing left behind:** a frame after `set_backdrop(None)` equals a frame that never had a backdrop, byte for
  byte; with no backdrop the existing Worklight pins hold (`test_gl_face_data_layout.py`, `test_gl_shading.py`,
  `test_gl_texture.py` unchanged).
- G5 **capture default:** `request_capture(cb)` in the camera view with a photo equals the same capture without a
  photo (the saved LookDev image never shows it).
- G6 **LookDev slot:** outside the model a pixel shows the photo (opacity 1) and the mix with the LookDev background
  at opacity 0.5 within 1/255; inside the model the skin, unchanged.
- G7 **passepartout slot:** outside the gate the model is darkened by the passepartout and the wire is not.

### 10.4 The probe row on the reference PC

`experiments/drag_cost/probe_likeness.py` (the `probe_lookdev_room.py` shape: hidden window 1024 × 768,
`scenes/Gollum_Head_05.mirai.json`, 5 unmeasured rounds, `GL_TIME_ELAPSED`, `Viewport.render()` with overlays):

| Row | What |
|---|---|
| `free` | the Worklight frame, no camera view (today's floor) |
| `camera view` | looking through, gate and passepartout, no photo |
| `photo 4096 behind` | a generated 4096 × 3072 photo behind the model, Worklight |
| `lookdev photo 4096 behind` | the same in LookDev (Portrait) |
| `free after` | left again: must equal `free` |
| `photo load` | wall ms of read + cap + upload for a generated 6000 × 4000 PNG (`encode_png`), and for `--photo PATH` (a JPEG of Manu's: the pyglet / WIC decode) |

Targets (`PROVISIONAL`): each camera-view row ≤ its free row + 0.5 ms GPU; `free after` = `free`; `photo load` of a
24 MP JPEG ≤ 3 s. In the container the probe runs as a function check only (`--draws 5`); the reference PC decides.

---

## 11. Stop points

1. **Now:** this AD, PROPOSED. **Manu accepts AD-042** (with or without changes to §2's engineering values or
   §16) before any `src/`, `tests/` or `experiments/` change.
2. **Build M1** in one fresh session (§9–§10), with an implementation note appended here; container results as a
   function check.
3. **Before M2:** Manu runs `probe_likeness.py` on the reference PC and does the practical test (§15). His verdict
   sets the M2 scope (proposal §10 M2).
4. **Keys:** none until a practical test and „Taste passt“ (proposal §6.5, AGENTS.md §7).
5. **M3 persistence:** only after LC-D2, LC-D9 and Manu's go for the Core field (proposal §3.2, CORE_V1_FREEZE §7).

---

## 12. Deviations from the proposal (with reasons)

| # | Proposal | This AD | Reason |
|---|---|---|---|
| D1 | the photo through `GLRenderStore.texture(path)` | an own texture from the capped array | the path cache loads the full file with `GL_REPEAT` (K5) |
| D2 | the front photo as an extra overlay with `DRAW_UNDER_HIGHLIGHTS` | a fixed slot in `_render_overlays` for passepartout, gate and (M2) the front photo | the passepartout must darken the soft-shading extras too, and the backdrop has its own capture rule; extra overlays are host objects the viewport does not own |
| D3 | "the capture skips the backdrop" | `request_capture(…, backdrop=False)` | the round trip needs it in a capture (K8) |
| D4 | „Kamera fixieren“ in M2 | in M1 | LC-D3 is decided and the routing (§5.4) is built in M1 anyway; Manu's test can then model to the photo |
| D5 | "every existing test result stays" | one assertion changes; `near` couples too | K1, K10 |
| D6 | overscan default 1.1 | 1.15 | K11 |
| D7 | the record stores eye, direction, focus distance | orbit fields | lossless, session-only; M3 maps to a transform |
| D8 | the round trip "proves gate, fit and lens" | it proves the pipeline; T-V9 and G2 prove the lens | K9 |
| D9 | the HUD line in M2 | `view_text` and one compact strip entry in M1, no Warnmarke | orientation is a risk from the first test (proposal §8) |
| D10 | (not mentioned) | „90° drehen“ in M1 | phone photos may load sideways until M2's EXIF orientation |
| D11 | (not mentioned) | the morph editing view's shift (§5.6), „Auge rahmen“ disabled, a session survives a load | K6; consistency with the LookDev framing; session, not document |

---

## 13. What M1 deliberately leaves out

- **M2:** the photo in front, wipe, hold to flip; photo fit (fine rotation = LC-D4, offset, cropped mode with scale,
  mirror) as other corners of the same `Backdrop`; EXIF focal length and orientation (a stdlib JPEG APP1 reader); the
  dolly-zoom and focal-length gestures (keys only after „Taste passt“); a Warnmarke „fixiert“ if the strip entry is not
  enough.
- **M3:** persistence (LC-D2, recommended a camera object, Core v18), Undo per gesture, Outliner rows, photo copies to
  an ignored `<stem>_photos/` (LC-D9), `view.likeness`, a camera glyph and its picking.
- **M4 / M5 / later:** silhouette, contour, landmarks, difference and mirror views, distortion, camera roll and lens
  shift as camera fields, gaze at a camera, projection painting, export at photo resolution (proposal §10).
- **Not in M1 at all:** any key, any Core or format change, any file written for a photo.

---

## 14. Risks

| Risk | Mitigation |
|---|---|
| Wrong FOV in the free view after a save, a load or the Eye Lab | §5.1–§5.5: the free view is saved with all fields, the file gets it, the Eye Lab and a load leave first; T-V2 … T-V4, T-V7 |
| "Where am I looking from" | gate, passepartout, `view_text`, the compact strip entry; the toggle in the SPACE menu |
| Accidental camera moves after a match | „Kamera fixieren“ in M1 (D4) |
| The jump when navigating a fixed camera | Q-LC-2; the alternative is recorded (§5.4) |
| Large photos on 512 MiB VRAM, JPEG decode time | the 4096 cap, one texture at a time, the two-step load with a status line; the probe row (§10.4) |
| HUD covers the gate edge | overscan 1.15 and „Rand“ (Q-LC-1); measured in Manu's test |
| The coupling changes a camera result | exact below 50 (§6.1), T-C2, the grep rule (§6.3) |
| A photo of a real person reaches the repository | M1 writes no photo and no path (§8.1) |

---

## 15. Praxistest für Manu nach dem Bau (Deutsch, ca. 25 Minuten)

Vorbereitung: ein Porträtfoto, dessen Brennweite du kennst (am besten ≥ 50 mm Kleinbild-Äquivalent; bei einer
Kamera steht sie in den Bildinfos, bei einem Handy die „35-mm-Brennweite“), und `scenes/Gollum_Head_05.mirai.json`.
Optional zuerst der Messlauf: `python experiments/drag_cost/probe_likeness.py` (und mit `--photo <dein JPEG>`).

1. **Kamera anlegen (2 min).** Szene öffnen, oben „Kamera [+]“, „Neu aus Ansicht“. Erwartet: „Kamera 1“ mit etwa
   29–33 mm. „Durchschauen“: Das Bild springt nicht, nur der Rahmen mit dem abgedunkelten Rand erscheint.
2. **Objektiv (4 min).** Brennweite auf 85 mm: der Kopf wird größer. Mit dem Rad zurückfahren, bis er in den Rahmen
   passt. Vergleiche mit Schritt 1: Nase kleiner, Ohren größer, Gesicht flacher? „Verlassen“: Deine freie Ansicht
   kommt genau so zurück, wie sie war.
3. **Foto (4 min).** „Laden …“, dein Foto wählen. Liegt es quer, „90° drehen“ (unter „Mehr“). Brennweite auf die des
   Fotos. Deckkraft ausprobieren. Der Rahmen hat jetzt das Format des Fotos.
4. **Einpassen (6 min).** In der Kameraansicht mit Alt+Maus drehen, Alt+Shift+Maus verschieben, Rad zoomen: die
   Kamera bewegt sich mit. Tipp: erst auf die Nasenspitze klicken, dann drehen (Dynamic Orbit Focus). Ziel: Augen,
   Nasenwurzel, Ohrpunkte, Kinn liegen auf dem Foto.
5. **Fixieren und modellieren (4 min).** „Kamera fixieren“. Mit W/E/R oder einem Strich etwas am Kopf ändern.
   Dann Alt+Maus: Du bist in deiner freien Ansicht, die Kamera bleibt. „Durchschauen“: genau die eingepasste Ansicht
   wieder. Stört der Sprung beim Navigieren?
6. **Kombinieren (3 min).** In der Kameraansicht LookDev öffnen: Foto unter Porträtlicht. Die Knöpfe Front / ¾ /
   Profil sind grau. „Bild speichern“: das Bild zeigt nur das Modell. Einen Morph-Regler bewegen; Paint Room öffnen
   und schließen.
7. **Verlassen-Wege (1 min).** `U` und Shift beim Drehen verlassen die Kameraansicht; das Eye Lab auch.
8. **Speichern (1 min).** In der Kameraansicht speichern, Szene neu laden: Du bist in deiner freien Ansicht, die
   Kameras sind noch in der Liste (nur bis zum Programmende).
9. **Fenstergröße (1 min).** Fenster schmaler und breiter ziehen: Der Kopf bleibt an derselben Stelle im Rahmen.
10. **Urteil.** Liest die Perspektive jetzt wie das Foto, verglichen mit dem heutigen 26-mm-Look? Stören Rahmen,
    Menüleiste oder Statusleiste (sonst „Rand“ unter „Mehr“ größer)? Was fehlt dir am meisten für M2?

---

## 16. Questions for Manu

**Needed now:** only whether **AD-042 is accepted** (as proposed, or with changes to §2's engineering values).

Three engineering defaults that can wait for the practical test (each is `PROVISIONAL` and cheap to change):

| # | Frage | Startwert | Alternative |
|---|---|---|---|
| Q-LC-1 | Rand um den Rahmen | 1,15 (≈ 50 px bei 768 px Fensterhöhe) | größer, wenn die Leisten den Rahmen verdecken |
| Q-LC-2 | Navigieren mit fixierter Kamera | zurück in die gespeicherte freie Ansicht (Sprung) | die freie Ansicht beginnt an der Kamera-Position |
| Q-LC-3 | Kameras nach „Szene laden“ | bleiben in der Liste (Sitzung) | werden gelöscht |

---

---

## 17. Implementation note — M1 built (2026-11-27)

Built in one session on `claude/magical-hamilton-th1i0c` from `b4eb346`, after Manu's „AD-042 build M1“ (taken as the
acceptance of §11.1, as proposed). Everything in §3 … §8 is built as written except the items in §17.2.

### 17.1 What is where

| AD § | Code |
|---|---|
| §3 lens math | `src/mirai/viewport/lens.py` (stdlib only; `SENSOR_KEYS`, `CUSTOM` added beside `SENSORS`) |
| §3.4, §6 camera | `camera.py`: `_tan_half_fov` (seven sites), `MIN_DISTANCE`, `MAX_DISTANCE = 2000`, `NEAR_BASE`, `FAR_BASE`, `clip_for_distance`, `clip_follows_distance`, `follow_clip` (in `dolly`, `frame_on_bounds`); `view_state._apply_camera` and `close_eye_lab` call `follow_clip`; `view_state.camera_fields` (the six `view.camera` fields of a camera or a saved free view) |
| §4.1, §5.1 records | `src/mirai/likeness.py`: `LikenessPhoto` (+ `size`), `LikenessCamera`, `FreeView` (frozen; `of`, `write`), `default_clip` (E3) |
| §4.2 session | `src/mirai/controllers/likeness.py`: `LikenessSession`, `CameraView` |
| §4.3, §5, §8.1 app | `Application`: the §4.3 API plus `set_active_likeness_camera`; `_camera_view_route` / `_camera_view_follow` at `_navigate`, the wheel zoom, `_apply_orbit_virtual` (Shift branch), `_toggle_ortho`; `_apply_likeness_lens` in `set_viewport_size`; leave in `init_scene` (beside `close_lookdev`), `open_eye_lab`, `shutdown`; `frame_lookdev` / `frame_eye` refused; the save writes the saved free view; `view_text` / `camera_view_text`; the photo tick in `update_viewport` |
| §5.6 morph shift | `MorphController._pan` → `services.camera_shifted(shift)` → `Application._likeness_camera_shifted` |
| §7 backdrop | `src/viewport/backdrop.py` (`Backdrop`, `gate_corners`), `src/viewport/backdrop_pass.py` (`BackdropPass`); `Viewport.set_backdrop` / `backdrop` / `backdrop_pass`, the slots in the Worklight branch and after `draw_background`, the overlay slot after the under-highlight extras, `request_capture(…, backdrop=False)` |
| §8.2, §8.3 GUI | `src/gui/likeness_model.py` (pure), `src/gui/likeness_panel.py`; toggle „Kamera [+]“ and the right-column window in `imgui_layer.py`; the SPACE row in `menus.py`; LookDev framing buttons and „Frontal einrahmen“ / „Einrahmen“ disabled with a tooltip; the compact HUD row `Kamera` (`HudState.camera`) |
| §10.4 probe | `experiments/drag_cost/probe_likeness.py` (+ `tests/test_probe_likeness.py`) |

`src/main.py` needs no wiring: the panels are created by the imgui layer itself (as Bone, Auge, LookDev). Not
touched, as §9 says: `src/core/`, the scene format, `config/keymap.json`, `.gitignore`, the Worklight / LookDev / eye
shaders.

### 17.2 Deviations found while building

| # | AD said | Built | Reason |
|---|---|---|---|
| B1 | §3.2 table: 25.73 mm → 50.00° / **69.4°** | 50.00° / **69.95°** | an arithmetic slip in the table; the formula (and every other row) is right; `tests/test_lens.py` pins 69.95° |
| B2 | §7.3 passepartout "the four rectangles outside the gate" (§7.5: VAO + `gl_VertexID`) | four rectangles, 24 vertices from `gl_VertexID` | as written; a first full-screen triangle with `discard` was replaced the same day (the probe showed the fill) |
| B3 | §4.3 has no "make active" | `set_active_likeness_camera(index)` | a click on a row selects the camera the lens and photo rows edit; the panel holds no state, so it goes through `Application` |
| B4 | §5.1 refusals | plus `PaintRoomController.settle()` first | a finishing paint stroke ends first, as in `open_lookdev`; otherwise the first click after a stroke was refused |
| B5 | §8.1 "the next `update_viewport` tick reads it" | after `LIKENESS_PHOTO_FRAMES = 2` ticks | the LookDev "preparing" pattern: the click happens during a frame's panel draw, so one more frame shows the status line before the decode |
| B6 | §10.3 G3 "equal before and after the image draw and the gate draw, in the Worklight and in LookDev" | the pass's two draws against a deliberately odd state (depth, cull, blend factors, polygon mode `LINE`, a texture and a sampler on unit 0, unit 3 active, unpack 4) + the whole app frame with and without the camera view (Worklight and LookDev) ending in the same state | the Worklight frame itself does not end in its start state (depth test on), so "before / after the whole frame" would test the meshes, not the backdrop |
| B7 | §5.7 the strip entry `Kamera` | the row label `Kamera`, value „›Kamera 1‹ · 85 mm“ (+ „ · fixiert“); the `View` row shows the full `view_text` | the strip's row shape (label · value) |
| B8 | §10.3 G2 "a plane object" | the cube's front face seen frontally (its silhouette is the front face) | the test scene has no plane; measured inside the gate (outside it the passepartout darkens the clear colour) |

### 17.3 Tests (container, 2026-11-27)

- New, headless: `tests/test_lens.py` (29: T-L1 … T-L6 + the §3.2 invariant over random lenses),
  `tests/test_camera.py` (+4: T-C1 over 11 799 FOVs bit for bit, T-C2 … T-C4), `tests/test_likeness_camera.py` (20:
  T-V1 … T-V7, T-V9 … T-V12 plus setters, switch, delete), `tests/test_room_rule.py` (+1: T-V8, with LookDev too),
  `tests/test_gui_likeness_model.py` (5, incl. the compact HUD entry), `experiments/drag_cost/tests/test_probe_likeness.py` (2).
- New, GL in their own process: `tests/test_gl_likeness_backdrop.py` (9: G1 round trip in both window shapes - the
  mean difference inside the gate is **< 1/255**, G2 pinhole within 1 px, G3, G4 byte for byte, G5, G6 within 1/255,
  G7), `tests/test_gui_likeness_panel_window.py` (1: the panel in the real window - new, look through, 85 mm, fix,
  a photo uploaded once, leave).
- The one intended change of an existing test (§6.3, K1): `test_camera.py::test_dolly_clamps_distance` asserts
  `MAX_DISTANCE`. The §6.3 grep found no other test reaching a distance above 50 through `dolly`, `frame_on_bounds` or
  a view load (`test_camera_ortho.py:28` builds one at 150 through the constructor: unchanged). No other existing
  result changed.
- Guards run green (§10.1): 431 headless tests in one targeted run (the §10.1 list plus the new files, HUD, Eye Lab,
  morph twins, main wiring); in their own processes `test_gl_gpu_picking.py` (41), `test_gl_face_data_layout.py`
  (16), `test_gl_shading.py` (19), `test_gl_texture.py` (10), `test_gui_imgui_window.py` (19),
  `test_gl_lookdev_pass.py` (13), `test_gl_line_overlay.py` (8).
- Full `pytest tests` (headless, 12 min): 7 809 passed, 470 skipped, 3 failed → 2 after the fix below. The two left
  (`test_interaction_scenarios.py::test_box_paint_and_lasso_select_and_esc_cancels_a_box` and its purity replay
  `test_interaction_structure.py::test_iv_can_run_is_pure[...]`, "Paint: 6 vertices selected" instead of 5) **fail on
  `b4eb346` too** (checked in a worktree): not caused by M1, not touched. The third was M1's:
  `test_i_application_init_sets_only_non_modal_fields` - `_likeness` is registered in `NON_MODAL_FIELDS` (a view
  configuration without an interaction session, like `_lookdev`); the photo's tick counter lives in the session
  (`pending_frames`), not on `Application`.

### 17.4 Probe, container

[`RESULTS_LIKENESS_CONTAINER_2026-11-27.md`](../../experiments/drag_cost/RESULTS_LIKENESS_CONTAINER_2026-11-27.md):
a function check on llvmpipe. Every row runs; `free after` = `free`; „Neu aus Ansicht“ gives 33.3 mm at 1024 × 768 (as
§4.4 computed). The camera-view rows are over the 0.5 ms target **on the software rasteriser**: the blended
passepartout's fill (isolated: the rectangles alone +4.9 ms, the draw state alone +0.0 ms). The reference PC decides
(§11.3); if it is over there too, the lever is the passepartout's strength under „Mehr“ (0 = off: only the 1 px gate
line is drawn; the value already exists as `LikenessSession.passepartout` / `Backdrop.passepartout`, M1 has no
control for it).

### 17.5 For Manu

Der Praxistest §15 gilt unverändert; vorher bitte einmal `python experiments/drag_cost/probe_likeness.py` (und mit
`--photo <dein JPEG>`) auf dem Referenz-PC. Q-LC-1 … Q-LC-3 (§16) haben ihre Startwerte und warten auf den Test.

**Next step:** Manu's probe run and practical test (§11.3, §15); his verdict sets the M2 scope.
