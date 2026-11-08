# WP Dynamic Orbit Focus — Last Worked Area

**Status:** gebaut 2026-11-08 (`PROVISIONAL`, Praxistest offen, §8). Plan freigegeben von Manu 2026-11-08 ("Grundsätzlich freigabefähig nach Nachschärfung", dann "umsetzen"); die Produktentscheidungen P1–P9 (§6) sind mit den empfohlenen Defaults umgesetzt und im Praxistest zu bestätigen.


**Origin:** research + architecture audit (plan mode), then implemented in phases (§5).
**Mirai HEAD audited:** `38b34a36c7e0d2aefefb427cc50ad6405fef3a01` ("Objects: Ctrl+C / Ctrl+V copy and paste in mode 4").
**Blender audited:** `blender/blender` main @ `9c4fc4363b03d30e576d76b86420b929f1e18465` (sha via `git ls-remote`; files read from raw.githubusercontent.com at that sha; commit date not retrievable — GitHub API/projects.blender.org were blocked by the session proxy).

## Context

Today Mirai always orbits around `OrbitCamera.target` — effectively the scene/framing centre (V1 decision, `docs/future_ideas/VIEWPORT_NAVIGATION.md:45-54`: "V1 bleibt bewusst beim Scene-Zentrum als Orbit-/Zoom-Zentrum"). The artist has to pan constantly to keep the part they work on under the orbit. Goal: ZBrush-like behaviour — the viewport remembers the **last worked area** (set only by committed work) and orbits around it, without moving the view, until work happens elsewhere. Must stay independent of the Working Pivot, cost nothing per frame, and reuse existing journal/commit infrastructure.

---

## 1. Blender findings

### Files / functions (sha `9c4fc43…`)
| File | Symbol (≈line) | Role |
|---|---|---|
| `editors/space_view3d/view3d_navigate.cc` | `viewops_flag_from_prefs` ~46 | Prefs `USER_ORBIT_SELECTION`, `USER_DEPTH_NAVIGATE`, `USER_ZOOM_TO_MOUSEPOS` → `VIEWOPS_FLAG_*` |
| same | `navigate_pivot_get` ~189–241 | Fallback chain for the pivot |
| same | `ViewOpsData::init_navigation` ~243–407 | Computes `dyn_ofs` **once per gesture**; Auto-Depth re-centres `ofs`/`dist` |
| same | `view3d_orbit_apply_dyn_ofs` ~737, `…_ortho_correction` ~754–815, `viewrotate_apply_dyn_ofs` ~817 | Orbit math around the pivot |
| same | `view3d_orbit_calc_center` ~831–922 | Per-mode centre |
| `view3d_navigate_view_rotate.cc` (not `…_rotate.cc`) | `viewrotate_apply` ~166, `viewrotate_invoke_impl` ~337 | Trackball/turntable/snap all use dyn_ofs; ortho correction switched on |
| `view3d_navigate_view_all.cc` | `view3d_calc_minmax_selected` ~240–392, `viewselected_exec` ~520 | Frame Selected = **bbox midpoint** |
| `view3d_utils.cc` | `ED_view3d_autodist*` ~1122–1211 | Depth-under-cursor pivot + per-gesture cache |
| `makesdna/DNA_view3d_types.h` | `View3D_Runtime::ofs_last_center` ~689, `V3D_RUNTIME_OFS_LAST_CENTER_IS_VALID` ~81 | Stored last centre + validity flag (runtime, per 3D view, not saved) |
| `blenkernel/intern/paint.cc` | `stroke_get_average` ~1676, `stroke_track_location` ~1686 | Sculpt/paint pivot = running average of brush dab positions |
| `blenkernel/BKE_paint_types.hh` ~109–111 | `PaintRuntime::last_stroke_valid / average_stroke_accum / _counter` | Paint-mode "last worked area" |
| `sculpt_paint/paint_stroke.cc` ~953; `sculpt_paint/mesh/sculpt.cc` ~3555 | stroke start collapses sum to mean; each dab tracks location |
| `transform/transform_gizmo_3d.cc` | `calc_pivot_pos` ~2535 (`V3D_AROUND_CENTER_MEDIAN`) | Edit-mode selection median |

### Mechanism (paraphrased, not copied)
1. **Centre per mode** (`view3d_orbit_calc_center`): Object mode → mean of selected objects' bbox centres (one per object); Edit/Pose → median of selected elements via the transform-gizmo code; Sculpt/Paint → average stroke location (always "valid"); text edit → text cursor.
2. **Storage:** `View3D.runtime.ofs_last_center` + validity flag, written on every successful centre calculation at navigation start; never cleared (after deleting the selection Blender keeps orbiting the old spot).
3. **Update vs reuse / fallback chain:** fresh selection centre → (Auto-Depth off) stored last centre → none (orbit `ofs`); with Auto-Depth: depth under cursor (with 0/2/4 px margins, fallback: mouse ray on the view-centre plane), cached across a consecutive trackpad gesture.
4. **Orbit math:** pivot fixed for the whole drag. Each update computes the relative rotation from the gesture-start state and swings the vector *pivot → view centre* by it; `dist` unchanged; computed from the initial state each step (no drift accumulation). The pivot stays fixed on screen, the view centre (`ofs`) moves.
5. **Ortho:** extra correction slides `ofs` along the view axis toward the pivot depth (avoids clip drift); in perspective Blender deliberately does not (would need a `dist` change). Auto-Depth in persp re-centres `ofs` to the closest point on the view axis and sets `dist` (cancel then can't fully restore — an acknowledged XXX).
6. **Sculpt "last worked area"** is exactly the ZBrush idea: stroke positions accumulated during work, read at navigation time.

### Reuse conceptually
- Pivot resolved **once at gesture start**, orbit = rigid rotation of the camera rig about that point (view never jumps).
- A stored "last centre" + validity, separate from the view centre.
- Work-driven centre (paint stroke average) separate from selection-driven centre.
- Ortho: slide the view centre along the view axis to the pivot depth (image-neutral in ortho).
- Frame Selected uses bbox, orbit uses median — two purposes, two estimators.

### Blender-specific — do not replicate
- Depth-buffer readback (Auto-Depth) — GPU sync per gesture; Mirai has CPU picking and no need.
- Selection-driven pivot overriding work (Mirai's requirement is the opposite: navigation follows *work*).
- Negated `ofs` convention, quaternion trackball, `ofs_lock`, camera-view/persp-ensure, NDOF flags.
- Never-invalidated stored centre (Mirai must invalidate on object deletion/scene load).
- **License:** Blender is GPL; we take only the concepts (all are generic 3D-navigation ideas). The Mirai implementation is written independently from Mirai's own `OrbitCamera` yaw/pitch model; no Blender code is copied.

---

## 2. Mirai current state (HEAD `38b34a3`)

### Navigation
- **One camera, world space:** `OrbitCamera` (`src/mirai/viewport/camera.py:88-105`) = `target, distance, yaw, pitch, fov, ortho`. `eye() = target + distance·dir(yaw,pitch)` (`:190`). **Orbit centre == view centre == `target`; there is no separate navigation offset.**
- `orbit()` `:107` (yaw/pitch, pitch clamp ±85°), `dolly()` `:113` (scales distance → zoom always toward target), `pan()` `:374` (moves target in the view plane), `set_view()` `:142` (absolute angles, used by Shift-snap), `frame_on_bounds()` `:117`.
- **Single input choke point:** `Application._navigate` (`src/mirai/application.py:3945`) → `_orbit_step` `:3970` (`camera.orbit` `:3977` or virtual angles → `_apply_orbit_virtual` `:3986` → `set_view` `:3994/:3998`) / `camera.pan` `:3951`; then `_camera_changed` `:4471`. Wheel: `pointer_scroll` → `camera.dolly` `:3684` (x/y dropped in `main.py:677` → no zoom-to-mouse). Alt during a transform: `_navigate_during_transform` `:4020` (reached from `:3628`, `:3713`).
- **Gesture boundary:** `_orbit_virtual` is lazily set on the first snap-orbit step and cleared on release (`:3644`).
- Writers of `camera.target`: `pan`, `frame_on_bounds` (startup `main.py:837`, `load_scene` `:969`), `view_state._apply_camera` (`src/mirai/view_state.py:154-174`, scene file `"view"`), morph edit view `_pan(shift)` (`src/mirai/controllers/morph.py:412-419`, undone in `close_if_left` `:433`).
- `ObjectSpaceCamera` (`src/mirai/object_space.py:120-200`) is a read-only object-space adapter (`target` property `:149`, no setter); component tools use `ObjectController.edit_camera` (`controllers/objects.py:1100`).
- Bindings: Alt+LMB orbit, Alt+Shift+LMB pan, wheel zoom (`interaction/bindings.py:411-424`, `config/keymap.json:4-7`). `F` reserved for `frame_selection`, unbound (`bindings.py:228,343`; E47). No Frame Selected / Frame All command exists.
- Hover / passive motion (`pointer_motion` `:3695-3723`, `flush_hover`, `_refresh_hover`) never touch the camera.

### Working Pivot (must stay untouched)
- `WorkingPivot(object_id, position, enabled)` in `src/mirai/pivot.py:42`, held by `PointerToolsController.working_pivot` (`controllers/pointer_tools.py:507`), object space; `Application.active_pivot` `:4128`; gizmo substitutes it in `_gizmo_pivot` `:4270-4272`.
- Shares **no state** with the camera. Only read-coupling: `place_pivot` uses `camera.target` as depth anchor when it has none (`pivot.py:114`). (Stale doc reference: `pivot.py:16` names `Application._pivot_point_at`, now `PivotPlacement.point_at`, `pointer_tools.py:242`.)

### Selection centres
- `resolve_selection_vertices` / `selection_pivot` (mean) / `symmetric_default_pivot` — `src/mirai/interaction/tools/selection_helpers.py:28-129`, O(selection).
- `_gizmo_pivot` (`application.py:4243-4273`): cached world-space selection mean on `_query_mesh()` (morph mix aware) — but returns the **Working Pivot** when active → must not be reused as-is.
- `_gizmo_object_pivot` `:4275-4295`: mode 4 mean of selected objects' world pivots.
- `mesh_center_and_radius` (`src/mirai/mesh_geometry.py:25-47`): O(V) — only for explicit framing, never per orbit.

### Operation lifecycle & affected-element data
- **Change journal** (`src/core/mesh.py`): `begin_change/end_change/rollback_change` (`:2404-2469`), `MeshDelta` `(before, after)` per vertex/edge/face (`:424-458`); removed vertex = `(pos, None)` → pre-removal position retained. `Mesh.watch()` (`:2564`, `MeshWatch` `:461-489`) = persistent poll-only log (`take()/peek()`), before-records of every touched vertex/edge/face, O(touched); undo/redo replay (`apply_delta`, `set_vertex_position`) is journaled too. Established pattern: 10+ consumers poll at sync time (render_mesh, picking_cache, morph_mix, skinning, hidden, …).
- **Universal commit hook:** `Application._record_selection_history(before, mesh_step, object_meshes)` (`application.py:3352-3369`) runs once after **every** `history.push()` — app paths via `_mesh_transaction` (`:3253-3315`, the "one commit boundary") and all controllers via `AppServices.record_selection_history` (`controllers/services.py:165`): transform `gestures.py:530`, extrude `:664`, slides `:712`, smooth `:885`, inset/bevel `:1017`, knife `controllers/knife.py:507`, delete/dissolve `application.py:1683`, object commands (`mesh_step=False`), skeleton (`mesh_step=False`). Swallowed pushes (morph view translation) return early `:3362`. It receives the **pre-op selection snapshot** and keeps a mirror undo/redo stack 1:1 with `HistoryStack`.
- **Undo/redo:** single path `_apply_undo_redo` (`:3092-3153`) — pops the mirror entry, runs `history.undo/redo`, follows edit-object changes. Core `HistoryStack` (`src/core/history.py`) is frozen and hook-less.
- **Cancel:** `GestureSession.cancel` → `abort()` (`gestures.py:329`), `Operation.cancel()` pushes nothing; rollback restores positions exactly.
- Op results (Split new verts, Extrude `_new_face_ids`, Knife `_path_edges`, …) are selection residue and inconsistent across ops → use the journal instead.
- **Symmetry:** coordinators run one op on the union of both sides (`symmetric_ops.py`, `move.py:54-63`) → journal contains both sides; plain centroid lands on the plane.
- **Soft selection:** the transformed set = whole influenced region (`transform.py:284-295`); seeds = pre-op selection.
- **Morph:** edits in the morph edit view hit the view mesh with real positions, then `TranslatingHistory` (`morph_targets.py:208-226, 283-300`) pushes a layer-only delta on the base. Drawn geometry with a weight > 0 is `MixSurface` (`_query_mesh`, `application.py:3817`).
- **Rig/pose:** pose is view state (no history); bone edits are `RigCommand`; weight edits are layer-only; picking stays on the rest cage (`skinning.py:30-37`).
- **Objects:** one `Mesh` per `SceneObject`, positions object-local (`object_space.to_world`); edit-object switch → `_follow_edit_object` (`application.py:868-886`, also after undo/redo `:3134`).

---

## 3. Gap analysis

| Capability | Blender approach | Mirai current state | Required work |
|---|---|---|---|
| Orbit around arbitrary point without view jump | `dyn_ofs` rotation of `ofs` around pivot, per gesture | Orbit only around `target`; no orbit-about-point | Add pure `OrbitCamera.orbit_about(point, d_yaw, d_pitch)` + `set_view_about(point, yaw, pitch)` |
| Pivot resolved once per gesture | `init_navigation` | Gesture start implicit (`_orbit_virtual` lazy init / release `:3644`) | Resolve anchor on first orbit step, clear at release |
| Stored last centre + validity | `ofs_last_center` + flag, never cleared | None | `OrbitFocus` state (object id + object-space point), invalidated on object deletion/scene load |
| Work-driven centre | Sculpt stroke average | Journal knows every touched element; one commit hook | Mesh watch drained at `_record_selection_history`; centre from changed elements |
| Pre-delete position | n/a (Blender doesn't track) | `MeshWatch` before-records keep removed positions | Read before-record for invalid vertices |
| Distinguish undo/redo | not tracked | no flag in core; single app path `_apply_undo_redo` | Drain watch there with explicit policy |
| Cancel must not move focus | n/a | rollback exact, watch still lists touched keys | Filter "current == before"; drain on commit/undo only |
| Selection centre fallback | median (edit) / bbox-centre mean (object) | `selection_pivot` mean, `_gizmo_pivot` (pivot-contaminated) | Fallback helper on `_query_mesh()` without Working Pivot substitution |
| Ortho handling | ortho correction toward pivot depth | target depth arbitrary in ortho | Slide target along forward to pivot depth in ortho (image-neutral) |
| Zoom centre | `ofs` or zoom-to-mouse | dolly toward `target` | unchanged (product decision P5) |
| Frame Selected | bbox midpoint | none (`F` reserved) | out of scope; separate product decision P6 |
| Soft selection / symmetry | n/a | journal includes falloff region / both sides | Prefer pre-op selection ∩ changed; symmetry side rule (P3) |

---

## 4. Recommended architecture

### 4.1 State ownership
- New module **`src/mirai/orbit_focus.py`** (pure, no pyglet), owned by `Application` (`self._orbit_focus`), next to — never inside — `PointerToolsController.working_pivot`.
  - `OrbitFocus(object_id, position_object_space, source)` frozen dataclass (`source`: `"work" | "undo" | …` for status/tests). Object-space + object id so it follows object placement (same convention as `WorkingPivot`), resolved to world via `object_space.to_world` only at gesture start.
  - `FocusTracker`: holds one `Mesh.watch()` on the edit mesh; `rebind(mesh)` in `_follow_edit_object`, `close()` on scene load.
  - Pure function `focus_point(watch_change, mesh, query_mesh, preferred_vertices) -> Vec3 | None`.
- `OrbitCamera` gains only stateless maths (`orbit_about`, `set_view_about`); it stores **no** focus (keeps `camera.py` free of app state, VIEWPORT_V02 §4.1 contract `eye = target + distance·dir` intact).
- Working Pivot: no reads, no writes, no shared helper path (`_gizmo_pivot` is not used for the fallback because it substitutes the pivot).

### 4.2 Focus calculation (at commit, O(touched)) — revised, see §7.1/§7.2
The first draft ("changed verts ∪ endpoints of changed edges ∪ corners of changed faces, ∩ pre-op selection") was **wrong** for two cases and is replaced:
- Edge records include their `faces` list (`src/core/mesh.py:586-590`), so every edge next to an added/removed face "changes" → Knife/Split/Connect/Bevel would pull whole faces (and Extrude the base ring) into the centre.
- Extrude moves *new* cap vertices; the pre-op selection is the base (`extrude.py:241, 270-273, 293-298`) → pre-op ∩ affected = base, not cap.

Revised algorithm (`focus_point`, pure):
1. `change = watch.take()`; classify every record against the live mesh: **moved** (vertex, position ≠ before), **created** (record None, element exists), **removed** (record set, element gone). Records equal to the current state (rollbacks, cancelled previews, knife `load_state` checkpoints `knife_resolve.py:279`) are dropped. An edge whose only difference is its `faces` list is **not** a change.
2. **Geometric gate:** at least one moved/created/removed vertex, edge or face. `regions`, `symmetry`, `layer_*`, `face_uvs` alone never count (§7.2). Do **not** use `mesh_step` — it is True for region tints and Shift+S symmetry axis.
3. **Affected set in strict tiers** (first non-empty tier wins):
   - T1: moved ∪ created vertices; if empty, removed vertices (positions from the before-record).
   - T2: endpoints of created/removed edges.
   - T3: corners of created/removed faces.
4. **Preferred subset:** T ∩ vertices of the **post-op** selection (the `after` snapshot taken inside `_record_selection_history`); else T ∩ pre-op selection (Delete/Dissolve: removed vertices); else T.
5. Positions: live vertices from `_query_mesh()` (on-screen, morph-mix aware, like `_gizmo_pivot`); removed vertices from the before-record. **Estimator: bbox centre** (P2).
6. Empty / gate failed → focus unchanged.

Per-operation result (verified against code, §7.1): Extrude → cap · Knife/Split/Edge Connect/Inset/Bevel → new vertices · Vertex Connect/Edge Dissolve → T2 · Cap → T3 (hole rim) · Delete → removed positions · Collapse/Slide/Move → moved selection · Soft Move/Smooth → seeds (post-op selection) · Symmetry → working side (post-op residue keeps the working side, `extrude.py:353-354`; move selection = selected side).

### 4.3 Update lifecycle (recommended policy)
| Event | Focus |
|---|---|
| Committed step that passes the geometric gate (`_record_selection_history`, not swallowed) | **update** |
| Whole-mesh rewrites: Apply Transform, Re-Symmetrize, in-place ZBrush return | unchanged (explicit `focus=False` from those call sites, §7.2) |
| Region tint, symmetry axis, hide/show, mask, materials, morph/skin weights, layer add/rename | unchanged (gate) |
| Morph edit-view edit | update (view object id, view space; remapped to base on close, §7.3) |
| Object-mode transform commit (mode 4) | update to moved objects' world pivots mean (`_gizmo_object_pivot` logic) — Phase 4 |
| Cancel / Esc / rollback | unchanged (nothing drained; before≠current filter) |
| Undo / Redo of a mesh step | update to the region the step changed (drain watch in `_apply_undo_redo`) — P4 |
| Orbit / pan / zoom / hover / snap views | **never** |
| Selection change | unchanged (selection ≠ work); used only as fallback — P1 |
| Edit-object switch | focus kept but only used while its object is the edit object; otherwise fallback — P7 |
| Layer-only (weights, morph base translation), pose, bone add | unchanged |
| Object deleted / scene load / `load_scene` | invalidate |
| Object transform (placement) | focus follows automatically (object space) |

Watch bookkeeping: take the watch **before** the `swallowed` early return (`application.py:3362`) and discard it when swallowed; in `_apply_undo_redo` take it **after** `self._morph.after_history()` (`:3143`) — before that the morph view has not followed yet; `_record_selection_history` is not called on undo/redo. Draining happens even with the flag off, so watch memory stays O(one step).

### 4.4 Navigation integration
Revised after the path audit (§7.4). One camera primitive, used by every orbit path:
- `OrbitCamera.set_view_about(anchor, yaw, pitch, ortho=None)`: express `target − anchor` in the current (forward, right, up) basis, set the new yaw/pitch, rebuild in the new basis → rigid rotation about `anchor`; `distance` unchanged; in ortho then slide `target` along `forward` to the anchor's depth (image-neutral). `orbit_about(anchor, d_yaw, d_pitch)` = clamp pitch first, then `set_view_about` with the clamped angles (so rotation and clamp agree).
- Correctness: `eye − target = −distance·forward` is rotated with the frame, so `eye = target + distance·dir` (VIEWPORT_V02 §4.1) stays true; the anchor's camera-frame coordinates are preserved ⇒ same pixel in persp and ortho. The basis comes from `basis()` itself, so the Top/Bottom pole rule (`POLE_EPS`, `camera.py:64-67, 201-203`) is respected automatically. **Verified numerically** on the real `OrbitCamera` (20 000 random steps + snap to Top, persp and ortho): anchor drift 7e-11 px / 3e-11 px, distance unchanged.
- Paths:
  1. **Alt+LMB orbit** (`_execute_drag` `:3936` → `_navigate(snap=True)` → `_orbit_step` `:3979-3984` → `_apply_orbit_virtual` `:3986`): gesture keeps virtual absolute angles. At its first step store `_orbit_anchor` next to `_orbit_virtual`; `_apply_orbit_virtual` calls `set_view_about(anchor, …)` for both the snapped (`:3994`, `ortho=True`) and the free branch (`:3998`).
  2. **Shift toggled mid-orbit** (`set_shift_held` `:1936-1939`) re-runs `_apply_orbit_virtual` → same anchor → snap on/off keeps the anchor's pixel. Note: snapping changes yaw/pitch absolutely, so the target moves on the circle around the anchor; leaving the snap returns to the virtual angles — reversible because each application is a rigid rotation between two absolute orientations.
  3. **Alt-orbit during a transform** (`pointer_drag` `:3626-3628` for gizmo/Tweak, `pointer_motion` `:3711-3713` for armed W/E/R; both → `_navigate_during_transform` `:4020` → `_navigate(snap=False)` → `_orbit_step` free branch `:3975-3977`): there is **no button release** to end it → `_orbit_anchor` is resolved lazily on the first step and cleared when Alt is released (`set_alt_held` `:2296-2307`) and when the gesture ends/cancels. Uses `orbit_about`. The running transform's preview writes are not drained (drain only at commit/undo), so the anchor is the stored focus, not the moving selection. Rotate dial re-projects its pivot per step (`:4023`) — unchanged behaviour, covered by `test_transform_alt_orbit.py`.
  4. **Alt+Shift pan / Alt+Shift during transform** → `camera.pan` unchanged.
  5. **Wheel dolly** `:3684`, **`U` ortho toggle** `_toggle_ortho` `:4010`, **frame_scene** `:888`, **view_state restore** `view_state.py:154-174`, **morph `_pan`** `morph.py:412-419`: unchanged; none of them is inside an orbit gesture, and none reads or writes the focus.
- Clearing `_orbit_anchor`: pointer release (`:3644`, next to `_orbit_virtual = None`), Alt release, scene load, `restore_camera_state` (`:977`).
- Guard: if the anchor projects behind the camera (`project_to_screen` None) → plain `orbit()` (classic).
- Pan unchanged (moves target; focus stays world-fixed). Dolly unchanged (toward target / screen centre) — P5.
- No per-frame or per-step geometry access: one O(1) `to_world` per gesture; fallback selection centre O(selection) once per gesture.

### 4.5 Fallback chain at gesture start
1. Valid `OrbitFocus` whose object is the edit object (mode 1–3) → its world point.
2. Selection centre of the edit object on `_query_mesh()` (mode 4: selected objects' pivots) — computed once per gesture, Working Pivot **not** substituted.
3. `camera.target` → identical to today's behaviour.

### 4.6 Feature flag
`Application.dynamic_orbit_focus: bool` (`PROVISIONAL`, default per P8); no keymap entry, no HUD control until Manu decides.

---

## 5. Implementation roadmap

Each phase is independently testable and committable; docs updated in the same commit (CLAUDE.md).

**Phase 1 — Camera maths (pure).**
Scope: `OrbitCamera.set_view_about`, `orbit_about` (`src/mirai/viewport/camera.py`); one `camera_revision` bump each.
Deps: none. Risk: low — math pre-verified (§7.4); remaining risk is the ortho depth slide interacting with `ortho_back` picking (`ray_origin_toward`).
Tests (`tests/test_camera.py`, `tests/test_camera_ortho.py`): anchor pixel constant (< 1e-6 px) over 10k random steps, persp + ortho; snap to Top/Bottom/Front via `set_view_about`; anchor == target ⇒ bit-compatible with `orbit()`/`set_view()`; distance unchanged; ortho slide leaves `project_to_screen` of arbitrary points unchanged; pitch clamp ±85° with rotation and clamp consistent; `eye = target + distance·dir` invariant.

**Phase 2 — Focus state + calculation (pure).**
Scope: `src/mirai/orbit_focus.py` (`OrbitFocus`, `FocusTracker`, `focus_point`).
Deps: none (uses `Mesh.watch`, `selection_helpers`). Risk: record classification (edge `faces`-only changes must not count); removed vertex moved earlier in the same window → earliest position (acceptable).
Tests (`tests/test_orbit_focus.py`, real ops on small meshes, one test per row of the §7.1 table): single- and multi-face Extrude → **cap** bbox (not base, not midway); long Knife across large quads → created vertices only (no face corners); vertex-to-vertex Knife → T2; Split / Edge Connect / Inset / Bevel → created vertices; Vertex Connect, Edge Dissolve → T2; Cap → T3; Delete vertex/face → pre-delete positions; Collapse; Soft Move & Smooth → seeds; symmetric Move/Extrude → working side; gate: region tint, symmetry axis, layer add, skin weights, hide → None; cancel/rollback and zero-distance extrude → None; O(touched) (spy: no `all_vertex_ids`).

**Phase 3 — App wiring for edit modes (1–3).**
Scope: `src/mirai/application.py`: tracker in `init_scene`/`load_scene`; `rebind` in `_follow_edit_object` (`:868`, after `close_if_left` `:874`, with morph-view → base remap); take-then-gate in `_record_selection_history` (before `:3362`, uses `before` + `after`); undo/redo take after `:3143`; `focus=False` keyword from Apply Transform (`objects.py:1288-1321`), Re-Symmetrize (`controllers/symmetry.py:333`) and in-place ZBrush (`application.py:3226-3248`) via `AppServices.record_selection_history`; anchor in `_orbit_step` / `_apply_orbit_virtual` / `_navigate_during_transform`; clearing per §4.4; feature flag. Morph edit is covered here (no morph-specific code beyond the remap, §7.3).
Deps: 1, 2. Risks: watch noise from swallowed pushes or undo (mitigated by the take order); Rotate dial during Alt-orbit; per-write cost of one more journal log (O(#logs), one extra log next to 10+ existing).
Tests: new `tests/test_application_orbit_focus.py` (pattern of `test_application_working_pivot.py` / `test_application_view_snap.py`): Extrude/Knife/Delete commit moves focus; orbit/pan/zoom/hover/`U` don't; cancel doesn't; region tint / hide / symmetry axis / Apply Transform don't; undo/redo policy; snap orbit: anchor pixel constant while Shift toggles on/off; Alt-orbit during armed Move and during gizmo Tweak orbits about the focus, anchor cleared on Alt release; morph: edit in view → focus on view, Tab back → focus on base shifted like the camera, swallowed (refused) edit → no change, undo in view → policy; Working Pivot / `active_pivot` bit-identical before/after (separation); flag off ⇒ camera bit-identical to today. Regressions: `test_application_view_snap.py`, `test_transform_alt_orbit.py`, `test_application_working_pivot.py`, `test_view_state.py`, morph tests (`pytest tests -k morph -q`).
Acceptance: Manu practice test — work on eye → orbit around eye; edit nose → orbit around nose; view never jumps.

**Phase 4 — Object mode and morph/pose specifics.**
Scope: mode-4 object transform commits set focus (object pivots); pose mode = fallback only.
Deps: 3. Risk: multi-object focus semantics (P7). Tests in the same app test file; `test_weight_view.py` unaffected.

**Phase 5 — Docs.**
`docs/future_ideas/VIEWPORT_NAVIGATION.md` §"Orbit / Zoom Focus" → mark implemented with link; addendum in `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` §4.1 (orbit-about-point, target ≠ orbit pivot during a gesture); AD-012 Working Pivot addendum: "independent of Orbit Focus"; fix stale `pivot.py:16` reference; `docs/README.md` index line. (Can ride along with Phase 3's commit.)

**Not in scope:** Frame Selected (`F`), zoom-to-mouse/focus, HUD indicator, keymap entries, scene-file persistence of focus.

Verification per phase: `pytest tests/test_camera.py tests/test_camera_ortho.py -q`; `pytest tests/test_orbit_focus.py -q`; `xvfb-run -a pytest tests/test_application_orbit_focus.py tests/test_application_view_snap.py tests/test_transform_alt_orbit.py tests/test_application_working_pivot.py tests/test_view_state.py -q`; then a real-app run (`src/main.py`) for the practice test (AGENTS.md §8a scope).

---

## 6. Open product decisions for Manu (with recommended defaults)

| # | Decision | Recommended default | Why |
|---|---|---|---|
| P1 | Does a plain selection change move the focus? | **No** — selection is only the fallback when no work focus exists | Brief: work, not selection, drives navigation; selecting to inspect shouldn't swing the orbit |
| P2 | Estimator for the worked region | **Bbox centre** of affected (preferred) vertices | Robust to uneven vertex density; mean (gizmo) skews toward dense spots |
| P3 | Symmetry: focus on the worked side or on the plane? | **Worked side** (falls out of "post-op selection first", §4.2) | Working on the left eye should orbit the left eye, like ZBrush's stroke point |
| P4 | Undo/Redo update focus? | **Yes**, to the region the step changed | The viewport follows where the mesh visibly changed; no extra state needed |
| P5 | Zoom toward focus instead of screen centre? | **No** (unchanged dolly) for now | Keeps the change small; zoom-to-focus/mouse is a separate navigation decision |
| P6 | Explicit "Frame Selected / set focus" command on reserved `F` | Separate later decision; not part of this work | Needs a keymap decision by Manu (AD-013) |
| P7 | Edit-object switch: keep old object's focus? | **Fall back** to the new edit object's selection/target until work happens there | Orbiting around an object you just left feels wrong |
| P8 | Default on or off | **On**, `PROVISIONAL` flag, confirmed by a practice test | Core of the requested feel; flag allows instant revert |
| P9 | Re-Symmetrize / in-place ZBrush return: update focus? | **No** (whole-mesh rewrite = no localized work area) | A centre of half / the whole mesh is meaningless as an orbit pivot |

Note on P7 vs. the morph view: entering/leaving the morph edit view is technically an edit-object switch, but the focus is **remapped** (view ↔ base, same local position, §7.3) instead of falling back — the artist stays on the same work.

---

## 7. Revision 2026-11-08 — the four follow-up investigations (Manu's review)

### 7.1 Extrude and topology ops: the actually worked area
Journal facts: a `MeshWatch` keeps the first before-record per touched vertex/edge/face (`src/core/mesh.py:461-489, 580-596`); edge records carry `(v0, v1, faces)` (`:586-590`), so a mere neighbour-face change marks an edge as touched-and-different. Rollbacks write old values back (`_apply_records` `:2595-2660`) → compare with the live state.

| Op (code) | What the journal holds | Worked area (tier used) |
|---|---|---|
| Extrude (`topology/extrude.py:241, 261, 270-298, 327-328, 415`) | created cap vertices (copies, moved by the drag); base-ring edges `faces` changed; orig faces removed; multi-face: interior base vertices removed | **cap** = created ∪ moved (T1) ∩ post-op selection (selection remapped to caps) |
| Zero-distance Extrude (`gestures.py:651`) | aborted + rollback, no push | none |
| Symmetric Extrude | both sides created; residue = working side (`extrude.py:353-354`) | working-side cap |
| Knife (`topology/knife.py:726-765`; `split_edge` `mesh.py:1189-1213`, `split_face` `:1478+`) | created crossing/interior vertices; every crossed face removed + recreated (all corners); split-half edges created | created vertices (T1); vertex-to-vertex cut → created edge endpoints (T2); post-op selection = path edges |
| Split / Edge Connect | 1 / n created midpoints; adjacent faces rewritten | created vertices (T1) |
| Vertex Connect (`mesh.py:1438`) | face replaced by two, no vertex created/moved | created edge endpoints (T2) |
| Delete (`topology/delete_dissolve.py:41-69`) | removed faces/edges/vertices; rim edges `faces` changed | removed vertex positions (T1-removed) ∩ pre-op selection; face delete without vertex removal → T2/T3 removed |
| Edge Dissolve | 2 faces removed, 1 merged face created, edge removed; vertices untouched (unless cleanup `mesh.py:1688`) | removed edge endpoints (T2) |
| Face Dissolve | interior edges/vertices removed | removed vertices (T1) |
| Collapse | survivor moved, others removed, 1-ring rewritten | moved ∪ removed (T1) |
| Cap (`topology/border.py:181`) | one face created, edges reused | created face corners (T3) = hole rim |
| Inset (`topology/inset.py:104-121`) / Bevel (`topology/bevel.py:340-355`) | created vertices; bevel re-adds the whole 1-ring of faces | created vertices (T1) |
| Loop/Vertex Slide (`gestures.py:695-701`) | plan vertices moved | moved (T1) |
| Smooth/Relax (`gestures.py:845-886`) | `plan.movable` moved (Soft: falloff set) | moved ∩ post-op selection (seeds) |
| Move/Rotate/Scale (`core/operations/transform.py:229-375`) | `set_vertex_position` on the op's vertex set (Soft: whole influence set; symmetry: + partners); no-op transform → no command (`:362`) | moved ∩ post-op selection (seeds / selected side); a vertex sitting on the Working Pivot doesn't move — harmless |

Conclusion: tiers + "post-op selection first" give the right area for every op without op-specific code; op results (`_new_face_ids`, `_path_edges`, …) need not be read.

### 7.2 Geometric changes vs. hide/show, colours and other state
| Change | Journal fields | push + `_record_selection_history` | Focus |
|---|---|---|---|
| Hide/Isolate/Show (`hidden.py`, `_hidden_push` `application.py:2374`), Mask (`mask.py`) | none | no | — |
| Outliner hide objects (`objects.py:670-676`), materials (`objects.py:1398`), Reference/group/duplicate/paste (`objects.py:920`) | none on edit mesh | yes, `mesh_step=False` | gate: no |
| Region tints (`_region_edit` `application.py:2721-2750`) | `regions` only | yes, **`mesh_step=True`** | gate: no |
| Shift+S symmetry axis (`controllers/symmetry.py:224`) | `symmetry` only | yes, **`mesh_step=True`** | gate: no |
| Seam to plane (`symmetry.py:247`) | positions + symmetry | yes | yes (small real edit) |
| Re-Symmetrize (`symmetry.py:333`) | positions of a whole half | yes | **excluded** (`focus=False`, P9) |
| Morph add/rename/delete (`morph.py:235, 263, 291`), skin weights (`skeleton.py:378-455`) | `layer_meta/whole/values` | yes, `mesh_step=False` | gate: no |
| Morph weights, SubD, display, selection/mode | none | no (`select_group` `objects.py:850` records a mirror entry without push → gate: no) | — |
| Apply Transform (`objects.py:1288-1321`, `scene_objects.py:497-509`) | every vertex (world unchanged) | yes | **excluded** (`focus=False`) |
| ZBrush in place (`application.py:3226-3248`) | positions (often most of the mesh), regions, uvs, layers | yes | **excluded** (P9); texture-only return `mesh_step=False` → gate no |
| Delete objects with edit switch (`objects.py:432`) | none, `scene.mesh` changes | yes, `mesh_step=True` | gate: no; focus of a deleted object invalidated |

Filter = the geometric gate of §4.2 (records, not `mesh_step`) + the explicit `focus=False` keyword on the three whole-mesh rewrites. No new tracking system.

### 7.3 Morph-edit integration point (proven)
- Tab into a target (`controllers/morph.py:350-392`): a real `SceneObject` view with its own id, mesh copy with the base's ids at `b + d` (`morph_targets.py:230-237`), placed beside the base (`view_placement` `:297-308`); `set_edit_object(view)` → `_follow_edit_object` → **the generic watch rebinds to the view mesh**; then the camera pans by the shift (`morph.py:382-385`).
- A committed edit: the gesture writes the view mesh → `history.push` → `TranslatingHistory.translate` (`morph_targets.py:219-226, 265-293`) writes the base layer and pushes a layer-only command; `_rederive` rewrites only bit-different positions (subset of the edited ids). `swallowed` is set **only** on refusal or an empty delta → normal edits **do** reach `_record_selection_history`. The view watch then holds exactly the edited ids → generic §4.2 path gives the right focus in view space.
- Order rules: take the watch before the `swallowed` return (a refused edit's write + undo would otherwise leak into the next step); on undo/redo take it after `self._morph.after_history()` (`application.py:3143`), which re-derives the view via `sync_from_base` (`morph_targets.py:312-331`).
- Leaving (`leave_target` `morph.py:406` → `close_if_left` `:430-434`, called from `_follow_edit_object` `:874`): the view object is removed and the camera pans back. View and base share rotation/scale, so `to_world(view, p) = to_world(base, p) + shift` → remap a focus with `object_id == closed` to the base id, same local position — it moves with the camera pan, the view doesn't jump.
- Mix display (weights > 0, view closed): edits write base rest positions, display is `MixSurface` with the same ids (`morph_mix.py:88-97`) → positions from `_query_mesh()` (`application.py:3817-3827`). In the view `_query_mesh()` is the view mesh itself.
- Known limitation: undo of a target step while the view is closed changes only base `layer_values` → gate: no update (acceptable; P4 applies to geometry steps).
- Rejected alternatives: `translate`'s `moved` (often empty due to bit-exact re-derive), `touched` (local), command `layer_values` keys (this path only).
- **Hook = `Application._record_selection_history` (`:3352`) + `_apply_undo_redo` after `:3143`; focus stored in the current edit object's id/space; remap in `_follow_edit_object` (`:874-876`). No morph-specific code beyond the remap.**

### 7.4 Orbit maths and all navigation paths
- Maths: §4.4; numeric check on the real `OrbitCamera` (20 000 random steps incl. clamp, plus a snap to Top at the pole): anchor drift 6.7e-11 px (persp) / 3.4e-11 px (ortho), `distance` exactly unchanged. Blender's "compute from the gesture-start state" isn't needed for drift; it is still the natural fit for the snap path, which already works from absolute virtual angles.
- Complete inventory of camera writers (grep `orbit(|pan(|dolly(|set_view(|set_ortho(|camera.target =` in `src/`): `_orbit_step` `:3977`, `_apply_orbit_virtual` `:3994/:3998`, `_navigate` pan `:3951`, `pointer_scroll` dolly `:3684`, `_leave_view`/`_toggle_ortho` `set_ortho` `:4006/:4013`, `frame_scene` `:905`, `view_state._apply_camera` `view_state.py:167`, morph `_pan` `morph.py:415`. Only the first two become orbit-about; all others stay as they are (§4.4 items 4–5).
- Snap orbit: Shift down/up mid-gesture via `set_shift_held` `:1936-1939`; same anchor, rigid rotations between absolute orientations → the anchor pixel never moves, also while switching snap ↔ free and persp ↔ ortho (`_ortho_auto`).
- Alt-orbit during transforms: two entry points (`:3626-3628` gizmo/Tweak drag, `:3711-3713` armed W/E/R motion; Smooth/Relax excluded there) → no release event → anchor lifetime bound to Alt held (`set_alt_held`) and to the gesture; the transform keeps reading the camera per step (Move/Scale) or re-projects (Rotate dial) exactly as today.

---

## 8. Umsetzung 2026-11-08 und Praxistest

**Gebaut (Phasen 1–3, 5; Phase 4 vereinfacht):**
- `OrbitCamera.set_view_about` / `orbit_about` (`src/mirai/viewport/camera.py`); Vertrag im Addendum 2026-11-08 von
  [VIEWPORT_V02_ARCHITECTURE §4.1](viewport/VIEWPORT_V02_ARCHITECTURE.md). **Abweichung vom Plan:** der Praxis-Pfad
  Shift-Snap (Persp → Ortho) hätte den Anker springen lassen, weil Ortho- und Persp-Maßstab nur in der Tiefe des
  Targets übereinstimmen; `set_view_about` skaliert beim Wechsel nach Ortho den seitlichen Versatz mit
  `distance / Tiefe`, damit der Anker sein Pixel behält (Test `test_persp_to_ortho_keeps_the_anchor_on_its_pixel`).
- `src/mirai/orbit_focus.py`: `OrbitFocus`, `FocusTracker` (ein `Mesh.watch()` auf dem Edit-Mesh), `worked_area`
  (Stufen §4.2), `focus_point` (bevorzugte Mengen, BBox-Mitte).
- `Application`: Fokus-Update in `_record_selection_history` (Watch vor dem `swallowed`-Rücksprung geleert) und in
  `_apply_undo_redo` (nach `self._morph.after_history()`); `focus=False` für Apply Transform (Fokus bleibt am selben
  Weltpunkt, `set_orbit_focus_world`), Re-Symmetrize und ZBrush-Rückgabe; Watch-Rebind und Morph-View→Basis-Umhängen
  in `_follow_edit_object`; Anker in `_orbit_step` / `_set_view` (alle drei Orbit-Pfade), gelöscht bei Release,
  Alt-Loslassen (ohne gedrückte Taste), jedem Commit/Undo, Scene-Load und `restore_camera_state`; Schalter
  `Application.dynamic_orbit_focus` (Default an, keine Taste, kein HUD).
- **Phase 4 vereinfacht:** in Modus 4 dreht der Orbit um die gewählten Objekte (`_gizmo_object_pivot`, ohne
  Gizmo-Abhängigkeit); ein eigener Objekt-Fokus wird nicht gespeichert, weil ein bewegtes Objekt ohnehin gewählt ist.
  Pose-Modus: nur Fallback (Auswahl / Target).
- Tests: `tests/test_camera_orbit_about.py`, `tests/test_orbit_focus.py`, `tests/test_application_orbit_focus.py`;
  volle Suite `xvfb-run -a python -m pytest tests -q` 2026-11-08: 6270 passed, 150 skipped.

**Praxistest (für Manu, ca. 10 Minuten, `python src/main.py`, Kopf-Mesh):**
1. Am Auge ein paar Vertices verschieben (W), dann Alt+LMB orbiten: dreht ums Auge, das Bild springt beim Start nicht.
2. An der Nase extrudieren (T) oder schneiden (Knife): der nächste Orbit dreht um die Nase (die Cap / den Schnitt).
3. Orbiten, pannen, zoomen, hovern, `U`: der Drehpunkt bleibt die Nase.
4. Eine Transformation mit Esc abbrechen: der Drehpunkt bleibt, wo er war.
5. Region-Farbe setzen, verstecken/zeigen, Symmetrieachse (Shift+S): der Drehpunkt bleibt.
6. Ctrl+Z: der Drehpunkt geht dorthin, wo sich das Mesh durch das Undo geändert hat (P4).
7. Während Alt+LMB-Orbit Shift drücken/loslassen: die Nase bleibt auf ihrem Pixel (Front/Side ortho und zurück).
8. W halten, dann Alt halten und bewegen: dreht um den Fokus; Alt los, W arbeitet weiter.
9. Mit Symmetrie an einem Auge arbeiten: der Drehpunkt liegt am bearbeiteten Auge, nicht auf der Ebene (P3).
10. Working Pivot (P) setzen, dann arbeiten und orbiten: der Pivot bleibt unverändert, der Orbit folgt der Arbeit.
11. Morph-Target bearbeiten (Tab), etwas formen, Tab zurück: der Drehpunkt kommt mit auf die Basis.
12. Modus 4: der Orbit dreht um die gewählten Objekte.

Rückmeldung bitte je Punkt KEEP / ändern; offene Entscheidungen bleiben P5 (Zoom zum Fokus) und P6 (Frame Selected
auf `F`).
