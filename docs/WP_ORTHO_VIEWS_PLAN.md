# WP Ortho / Views — Ortho/Persp, standard views, pivot symmetry snap

> **Status:** **gebaut 2026-10-28** (`PROVISIONAL`, Praxistest B23 unten offen). Vertrag: [VIEWPORT_V02_ARCHITECTURE §4.1, Addendum Ortho](viewport/VIEWPORT_V02_ARCHITECTURE.md#addendum-2026-10-28-ortho-and-standard-views-wp-ortho--views); V-3: AD-012 Addendum Working Pivot. Der Plan unten ist der Bauauftrag, wie er war. Verwandt: [AD-012, Addendum Working Pivot](architecture/AD-012-TRANSFORM-SPACE.md#addendum-2026-10-28-working-pivot-manu-u-1u-4), [VIEWPORT_V02_ARCHITECTURE §4.1](viewport/VIEWPORT_V02_ARCHITECTURE.md), [future_ideas/VIEWPORT_NAVIGATION.md](future_ideas/VIEWPORT_NAVIGATION.md).

(Working Pivot v1 is done and accepted by Manu 2026-10-28: "Funktioniert alles so, wie es bisher soll"; commit 016c33f
on `claude/vigilant-planck-0p1o4l`.)

## Context

Manu (2026-10-28): "Jetzt zeigt sich aber echter Bedarf nach einer Ortho Persp mit Front/Side/Top/Bottom View, sonst
kann man den Pivot gar nicht genau mittig auf der X Achse setzen (dann geht auch Symmetry nicht so gut)."
The camera is perspective-only by design so far (`src/mirai/viewport/camera.py:1-5`: "Bewusst NICHT enthalten:
Ortho-Modus / Front-Back-Left-Right-Snapping"); view snapping is Manu's recorded idea
(`docs/future_ideas/VIEWPORT_NAVIGATION.md`, "Viewport View Snapping": ZBrush-style Shift during orbit).

Why it fixes the pivot: in an orthographic Side view every view ray runs exactly along X, so the Working Pivot's
"inside" placement (`mirai.pivot.inside_point`, midpoint of entry/exit) on a mirror-symmetric head lands on x = 0
(float rounding, within Core's `SEAM_TOLERANCE`). In perspective the cursor ray is slanted and the midpoint drifts.

**Manu's decisions (chat 2026-10-28, all as recommended) — record them as V-1..V-3 in the docs:**
- **V-1 Snap by Shift during orbit:** start an Alt+LMB orbit, press Shift → the camera snaps to the nearest of
  Front / Back / Left / Right / Top / Bottom while dragging; Shift up → free orbit again. Shift held *before* the
  press stays Pan (Alt+Shift+LMB, Manu's keymap 2026-09-26). No numpad.
- **V-2 Auto ortho:** a snapped view is orthographic; orbiting away returns to perspective (Blender "Auto
  Perspective"). Plus one toggle key Ortho ↔ Persp at any time (`PROVISIONAL` code default).
- **V-3 Pivot symmetry snap:** with symmetry on, a Working Pivot click within ~12 px (screen) of the symmetry plane
  lands exactly on it — every view, also perspective.

## Design

### 1. Camera (`src/mirai/viewport/camera.py`, `OrbitCamera`) — ortho as a mode of the one camera
- New field `ortho: bool = False`. Ortho half-height in world units = `distance * tan(fov/2)` (same apparent size at
  the target when toggling; dolly = ortho zoom, pan speed unchanged).
- Ortho `screen_to_ray`: parallel rays — origin = target-plane point offset along `right/up` by the NDC × half sizes,
  pulled back along `-forward` by a fixed depth (e.g. `far / 2`) so geometry in front of the orbit eye is not cut;
  direction = `forward`. `project_to_screen` / `screen_projector` (keep bit-identical to each other, `tests/test_camera.py`):
  ndc = cam_x / half_w (no division by depth), culling only outside the ortho depth range.
  `build_projection_matrix`: standard ortho matrix with the same near/far as the rays. `screen_delta_to_world`,
  `pan` work unchanged through the ray/plane code (verify).
- `basis()` at |pitch| = 90° (Top / Bottom): today `cross(forward, world_up)` degenerates. Use the analytic
  `right = (cos yaw, 0, -sin yaw)` **only when |cos pitch| < eps**, keep today's code otherwise (bit-identical
  everywhere else). `orbit()` clamp stays ±85° for free orbit; snapped Top/Bottom set ±90° directly.
- `view_snap` helpers (pure): `nearest_standard_view(yaw, pitch) -> (name, yaw, pitch)` (dominant axis of `forward`;
  for Top/Bottom yaw rounded to the nearest 90° so "up" on screen is a world axis).
- `camera_revision` bumps on every ortho/snap change (PickCache, GPU picking and uniforms key on it).

### 2. Every perspective assumption outside the camera (verified grep 2026-10-28; re-grep `\.eye()` before starting)
Principle: one camera helper instead of `eye()` scattered around — e.g. `camera.ray_origin_toward(point)` (persp:
the eye; ortho: `point - forward * depth`) and `camera.view_scale_at(point)` (persp: depth along forward; ortho: the
constant ortho half-height ratio). Add both to `ObjectSpaceCamera` (`src/mirai/object_space.py:120-192`, it exposes an
explicit allow-list and must fail loudly for anything missing).
- `src/mirai/viewport/picking.py:405,416,432` — occlusion casts eye → point (`_occluded`): use the ray origin toward
  the point.
- `src/mirai/viewport/gizmo.py:89` — `gizmo_size` = eye distance × scale: in ortho use the view scale, so the gizmo
  and the pivot marker stay constant on screen and do not explode with the pulled-back eye.
- `src/mirai/topology/knife_pick.py:105-109` (`space_point`: normal = target − eye = forward) — works unchanged as
  long as `eye()` stays the view centre (target + distance·dir); ray origins move to a plane behind the scene instead
  (`picking.py:235` drops hits with t ≤ 1e-9, so origins must be behind all geometry).
- `src/viewport/gpu_picker.py:363-373` (`_pixel_of`): `cw <= 0` never fires in ortho (cw = 1) — add the clip test
  `-cw <= cz <= cw`.
- `Application.frame_scene` (`:2123`) does not call `_camera_changed` itself — the new view/toggle handlers must.
- `src/mirai/topology/knife_planner.py:330` — the cut plane through (eye, A, B): in ortho the plane through A, B and
  the view direction (`n = cross(B − A, forward)`).
- `src/viewport/gl_render_store.py:244-245` (GLSL) — the smooth-quad normal casts a ray from the eye reconstructed
  from `u_view`; in ortho the ray direction is the view forward (`-u_view` row 2), origin the fragment pushed back.
  Needs a uniform/flag for ortho (or derive from `u_proj[11] == 0`).
- `src/mirai/interaction/dial.py` — rays only via `screen_to_ray` / `project_to_screen`: works with parallel rays
  (check the grazing test, `GRAZING_COS`, still makes sense).
- Works unchanged (inventory 2026-10-28): every overlay shader (`u_proj*u_view*pos`), specular (fixed view axis,
  `gl_render_store.py:297`), light-follows-camera (`light_rig.frame_for`, `basis()` only), polygon offsets, GPU
  picking ID/depth reads, `PickCache`/`FaceGrid` (keyed on `camera_revision`), `pick_face`/`face_hits_t`/
  `pick_object`, `dial.py`, `pivot.py`, `screen_delta_to_world`, the transform tools, `render_mesh` uniforms.
- GLSL detail: `FRAGMENT_SRC` needs `uniform mat4 u_proj;` declared (already set on the program, `:665`); ortho =
  `u_proj[3][3] == 1.0`.
- `frame_on_bounds` / `frame_scene` — distance formula also sets the ortho half-height: fine.
- Not in scene files (camera is not saved; check `src/scene_files.py` / `core/serialization.py` before starting).

### 3. Application (`src/mirai/application.py`)
- Orbit gesture (`_navigate` ORBIT via `_execute_drag`, `ORBIT_RADIANS_PER_PX`): keep a *virtual* (yaw, pitch) for the
  running drag. While `_shift_held` (`set_shift_held`, `application.py:3730`) during an ORBIT drag: camera = the
  nearest standard view of the virtual angles, `ortho = True`; Shift up: camera = virtual angles, `ortho` back to
  what it was before the snap (V-2: perspective). A free orbit step from a snapped view leaves ortho (V-2) unless
  the user turned ortho on by hand.
- Toggle command `TOGGLE_ORTHO` (`commands.py`), `PROVISIONAL` code default on a free key (check `config/keymap.json`;
  bare `U` or `J` are free; not numpad), no keymap.json entry. State only, no History, allowed during gestures like
  the display keys.
- Status line: "View: Front (ortho)" etc.; HUD: extend the "Display" row or a new "View" row ("Persp" / "Front · Ortho").
- Rotate dial / Alt-orbit during a transform: snapping only in the pointer ORBIT gesture, not in
  `_navigate_during_transform` (keep scope; note it).

### 4. Pivot symmetry snap (V-3) — `src/mirai/pivot.py` + `Application._pivot_point_at`
- After `place_pivot` resolves a point: if the edit mesh has a symmetry definition (`mesh.symmetry_definition`, plane
  point/normal as used by `resolve_symmetry` / `symmetry_params`) and the screen distance between the point and its
  projection onto the plane is ≤ `PIVOT_PLANE_SNAP_PX` (12, `PROVISIONAL`), return the projection (exactly on the
  plane). Applies after every placement mode (inside, Shift vertex/edge, off-mesh) and to the preview, so a seam
  vertex picked with Shift is exact as well. `PROVISIONAL` threshold; refused/irrelevant without symmetry.
- Status line names it ("on the symmetry plane").

## Tests (AGENTS.md §8a)
- `tests/test_camera.py` / `test_camera_picking.py`: ortho ray ↔ projection round trip, `screen_projector`
  bit-identical to `project_to_screen` in ortho, projection matrix matches `project_to_screen`, Top/Bottom basis
  orthonormal and continuous, perspective results unchanged (existing tests).
- `tests/test_pivot_placement.py`: ortho side view → inside point on x = 0 for the symmetric cube/head; plane snap
  within / outside 12 px; no snap without symmetry.
- New `tests/test_application_view_snap.py`: Alt+LMB orbit + Shift → nearest view + ortho; Shift up → free + persp;
  Alt+Shift pressed before the drag = Pan (unchanged); toggle key; picking (vertex/edge/face, Box/Lasso,
  occlusion) correct in ortho; gizmo size constant in ortho; Working Pivot inside on x = 0 in ortho Right view.
- GL tests in their own process (projection uniforms, GPU picking in ortho).
- Final: `pytest tests -q`, `xvfb-run -a python -m pytest tests/test_gl_*.py -q`, `pytest experiments/morph_lab/tests -q`.

## Docs (same commit)
- `docs/future_ideas/VIEWPORT_NAVIGATION.md`: "Viewport View Snapping" → implemented (`PROVISIONAL`), link.
- Camera contract: addendum to `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` §4.1 "Camera" (its authoritative home):
  ortho mode, the parallel-ray contract every picker and shader relies on, V-1/V-2 in Manu's words.
- `camera.py` module docstring (the "Bewusst NICHT enthalten" list), `bindings.py` docstring, `src/main.py` docstring,
  AD-012 Working Pivot addendum (V-3), `docs/ATELIER.md`: replace the "Als Nächstes" line by a capability line + German practical test (B23).

## Existing tests to extend / keep green
`tests/test_camera.py` (incl. `test_screen_projector_is_bit_identical_to_project_to_screen`),
`tests/test_camera_gate5_matrices.py` (clip-w test :48-58 is perspective-only: add an ortho matrix test),
`tests/test_camera_gate7_integration.py` (ortho toggle = camera-only change), `tests/test_picking_equivalence.py`
(its `_old_point_occluded` reference is eye→point: add an ortho reference), `tests/test_object_space.py`,
`tests/test_camera_picking.py`, `tests/test_picking_cache.py`, `tests/test_gl_shading.py` (smooth quads :158, :297),
`tests/test_viewport_gizmo.py`, `tests/test_knife_cross_face.py`, `tests/test_rotate_dial.py`, GL tests
(`tests/test_gl_*.py`). Knife oracle (`experiments/knife_oracle/tests`) once at the end because `knife_pick.py` /
`knife_planner.py` change (AGENTS.md §8a trigger list).

## Session hint
Fresh session (Manu 2026-10-28: "Vielleicht was für eine frische Session"), Opus, effort high: camera contract + GLSL + pickers + Application gesture, one
coherent Production package; start by re-reading this plan, `camera.py`, `picking.py`, `gizmo.py`, `pivot.py`.

## Result (2026-10-28)

Built as planned; deviations and findings for later agents:
- `view_scale_at` in perspective is the Euclidean eye distance (what `gizmo_size` always used), not the depth along
  `forward`, so the perspective gizmo stays bit-identical.
- The GPU depth oracle's clip test `-w <= z <= w` applies in perspective too (a point nearer than `near` or beyond
  `far` has no depth pixel either); no existing test changed.
- The toggle key is also honoured in a Knife session and in the Re-Symmetrize preview (view state like the orbit).
- The orbit's virtual pitch keeps the ±85° clamp; a free orbit from Top/Bottom therefore starts at ±85°.
- Measured (tests): on a UV sphere seen from the side, the perspective "inside" point drifts ~0.066 off x = 0; the
  ortho one is exactly 0.0 (`tests/test_pivot_placement.py`).

Tests: `tests/test_camera_ortho.py`, `tests/test_application_view_snap.py`, ortho cases in
`tests/test_pivot_placement.py`, `test_picking_equivalence.py`, `test_knife_cross_face.py`, `test_gl_shading.py`,
`test_gl_gpu_picking.py`, `test_hud.py`.

### Praxistest B23 (für Manu, ca. 10–15 Minuten, `python src/main.py`, Kopf-Mesh)

Annahmen, die du mit einem Satz korrigieren kannst: Shift rastet nur während eines laufenden Alt+LMB-Orbits ein
(Shift vor dem Klick bleibt Pan); die eingerastete Ansicht bleibt nach dem Loslassen stehen, bis du wieder frei
orbitest; `U` ist eine vorläufige Taste.

1. **Einrasten:** Alt+LMB orbiten, dabei Shift drücken — die Ansicht springt auf Front/Seite/Oben/…, flach (ortho);
   weiterziehen wechselt zur nächsten Ansicht; Shift los = wieder frei und perspektivisch. HUD-Zeile „View“ zeigt
   z. B. „Right · Ortho“.
2. **Umschalten:** `U` = Ortho ↔ Persp, jederzeit (auch mit gehaltenem `W`). Mit `U` eingeschaltetes Ortho bleibt
   beim freien Orbiten an.
3. **Pivot mittig:** Seitenansicht (Shift beim Orbit), `P` halten, in den Kopf klicken — der Pivot liegt genau auf
   der Mittelebene. Mit `Shift+S` (Symmetrie) auch in einer schrägen Ansicht nahe der Mitte: Statuszeile „on the
   symmetry plane“.
4. **Arbeiten in Ortho:** Auswahl per Klick und Box, Gizmo, Knife (`C`), Smooth-Shading — alles wie gewohnt?
5. **Fragen:** Fühlt sich das Einrasten richtig an (Zeitpunkt, Rückkehr)? Ist `U` die richtige Taste (sonst
   welche — erst dann kommt sie in `config/keymap.json`)? Sind 12 px Ebenen-Snap gut? In der Seitenansicht rastet
   **jeder** Pivot-Klick auf die Ebene, auch Shift auf einen Punkt außerhalb — ist das so richtig?
