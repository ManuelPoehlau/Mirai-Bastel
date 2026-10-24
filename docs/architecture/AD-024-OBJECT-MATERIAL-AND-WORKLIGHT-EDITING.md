# AD-024 — Per-object material and Worklight editing in Production

**Status:** PROPOSED (2026-10-24), stop point 1 of the handoff "WP Licht + Material in Production"; waiting for
the second opinion before any change in `src/core/`.
**Baseline:** `main` @ fb91f5b.
**References:** AD-013 (capability ≠ UX), AD-018 (+ Addendum 2026-10-23, the 6-float material packet), AD-021
(object model, §4.6 object commands), CORE_V1_FREEZE §7 / §7.1 (mirror-pairs precedent, format v3),
`docs/research/viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md` §4.1a, `experiments/viewport_shading_lab/`.

## 0. Decisions this AD rests on

- *Artist (Manu, 2026-10-24):* light and material editing in Production first, GUI later. Material is **per object
  and saved with the scene**. Simple: base colour, specular, glossiness.
- *Engineering (handoff, unconfirmed by Manu):* the light is the global viewport Worklight, not scene lights;
  `fill_specular` stays a Worklight parameter; References keep their fixed tint.

## 1. Requirement and freeze rule (CORE_V1_FREEZE §7)

1. **Requirement:** each object carries base colour, specular and glossiness; the values survive Undo/Redo,
   save/load, object delete/undo and the scene reset; v3 files keep loading.
2. **Existing public API is not enough.** `SceneObject` has `__slots__` (no ad-hoc attribute), and the file format
   is `core.serialization`. A side table in `src/mirai` keyed by `ObjectId` would need its own block in the file
   outside the Core format, an ID remap on every load (`replace_scene` hands out new IDs) and its own coupling to
   add/delete/undo — the object's data stored in two places. Same reason the mirror pairs went into the Core
   (OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.1). Rejected.
3. **Smallest extension, data only (as M0 and the mirror pairs):** §2 and §3. No change to `Mesh`, `Operation`,
   `HistoryStack`, `ObjectTransform`, `Selection`.

## 2. Data model (recommended: field on `SceneObject`)

`src/core/scene.py`:

```python
@dataclass(frozen=True)
class ObjectMaterial:
    base_color: Vec3   # each channel finite, in [0, 1]
    specular: float    # [0, 1]
    glossiness: float  # [0, 1]  (exponent mapping stays in viewport.material.gloss_exponent)
```

- `SceneObject.material: ObjectMaterial | None = None` (one more slot and keyword argument).
  **`None` = "app default look"**: the object follows `gl_render_store.DEFAULT_BASE_COLOR` and
  `material.DEFAULT_FINISH`, so retuning a default still reaches every untouched object and v3 files need no
  invented values. The Core holds no default numbers; `src/mirai` resolves `None` → defaults.
- Invalid values are refused with `ValueError` (like `ObjectTransform`); the setters in `src/mirai` clamp first,
  so a key step never raises.
- Not in the Core: the exponent mapping, the fill highlight, the selection tint, the Reference look.

**Alternative, not taken now — material table** (`Scene.materials: {MaterialId: Material}`,
`SceneObject.material_id`): buys sharing one material across objects, a library, and later textures referenced
by id. Costs a new ID space and allocator, orphan/usage rules, Undo for table entries, referential integrity in
the file. Nothing in scope needs sharing. Moving to it later is mechanical: each distinct `ObjectMaterial`
becomes a table entry and the field becomes an id (one more format version).

## 3. Scene file v4

- `_object_to_dict` writes `"material": null | {"base_color": [r, g, b], "specular": s, "glossiness": g}`;
  `FORMAT_VERSION = 4`; only v4 is written.
- Read: v4 as above (missing key = `null`); v3 and v2 load as v4 with `material = None`; v1 as today. An invalid
  material makes the file invalid (`ValueError`), like an invalid mirror pair.
- An older app refuses a v4 file ("unsupported version") — forward compatibility is not promised (as for v3).
- `replace_scene` copies `material`. "Mirror copy" copies the source's material (Blender's duplicate keeps the
  material); a new primitive / asset gets `None`. `morph_bridge` / Morph Lab read through the Core and are
  unaffected (their objects stay `None`).
- Tests to adapt: the three assertions pinning version 3 (`test_scene_objects.py`, `test_scene_files.py`,
  `test_mirror_pairs.py`) — same pattern as the v3 bump.

## 4. Render path (uniform update only, AD-018)

- The 6-float packet `[r, g, b, specular, glossiness, fill_specular]` stays. Per entry it is composed from the
  object's resolved material and the Worklight's `fill_specular`. A material change is `bind_material` +
  `mark_material_dirty` (one `material_updates`), never geometry/index/face data.
- `Viewport` loses the one global finish for all entries: `set_object_entry(..., finish=)` and
  `set_edit_material(color, finish)` (replaces `set_edit_base_color`); the global finish setter shrinks to
  `fill_specular`. `DisplayState.surface_finish` becomes `DisplayState.fill_specular`.
- **References** draw as today: `REFERENCE_BASE_COLOR` with the default finish; a stored material is kept but not
  shown (handoff; Artist question Q-M3). Material setters skip References (they are locked, as for the mirror
  pairs) and say so in the status line.

## 5. Selection highlight

`selected_color(obj, default)` tints the **resolved** base colour (the object's material colour, else the default)
toward `SELECTED_TINT` by `SELECTED_TINT_SHARE`, as today; specular/glossiness are not tinted. The highlight
signature (`_object_highlight_signature`) gains each object's `material`, so Undo/Redo and every other path that
changes a material redraw through the existing per-frame check. Known weak spot: a yellow-ish custom colour is hard
to tell from "selected" (Artist question Q-M4; the cure would be an outline, out of scope).

## 6. Targets of a material edit

- Mode `4`: the selected objects (References skipped; none left → refusal in the status line).
- Modes `1/2/3`: the edit object (never a Reference).
- Setter API on `Application` (later called by the GUI unchanged): `set_object_material(**changes)` (absolute,
  any of `base_color`, `specular`, `glossiness`) and `step_object_material(param, direction, fine)`. Refused while
  an interaction owns the keys (`interaction_owner`), as SubD.

## 7. Undo/Redo

- **Material:** `ObjectMaterialCommand(changes=[(obj, before, after)], description)` in
  `src/mirai/scene_objects.py`, shaped like `ObjectTransformCommand`; pushed with `history.push` +
  `_record_selection_history(..., mesh_step=False)`. Holds the instance (AD-001), so delete → undo → redo keeps the
  material. **No Core History change** — the extra stop point "History cannot carry scene-data edits" does not
  apply. One key step = one Undo step (`HistoryStack` has no public top/merge, E23; coalescing would need a Core
  change and is not worth it here, `PROVISIONAL`).
- **Light:** **not an Undo step** — the Worklight is view state like the display mode, the camera and the SubD view
  (precedent `_subd_command`; Blender's viewport shading is not in the undo history either), and it is not saved.
  Test point 4 then reads: Undo reverts the material, the light stays (Artist question Q-L1).

## 8. Worklight setters (no Core change; built before the review — independent of §2–§7)

- `DisplayState` holds the edited rig: `light_rig` (a `LightRig`), `light_preset` (name or "angepasst" after an
  edit, as the Lab). A preset (`Ctrl+D`) replaces the rig; `Ctrl+Shift+D` keeps toggling the space.
- `Application.set_light(**changes)` (any `LightRig` field, clamped to the Lab's ranges) and
  `step_light(param, direction, fine)` with the Lab's steps (azimuth 15°/1°, elevation 5°/1°, intensity 0.05/0.01,
  Kelvin 500/100, wrap 0.1/0.02, ambient 0.05/0.01, ratio over `RATIO_STEPS`, coupling and space as toggles).
- Temporary bindings (`PROVISIONAL`, binding layer, keymap-overridable): a "Look" parameter list (light rows, later
  the material rows) — `↑`/`↓` row, `←`/`→` value, `Ctrl+←`/`Ctrl+→` fine (the Lab's `Shift` is taken by the
  selection steps `Shift+arrows`). The HUD and status line show the active row and value.
- **Light drag is not bound: stop point.** The Lab's plain `LMB` drag is `SelectDrag` (Box/Paint) in Production;
  every modifier variant of `LMB` drag is taken (Alt = Orbit, Alt+Shift = Pan, Shift = add, Ctrl = Tweak), RMB/MMB
  are deliberately unbound (AD-013 rule 2). Not remapped; options for Manu in Q-L2.

## 9. Open Artist questions (max 10 lines)

- Q-L1: Light changes are not Undo steps (view state, like the camera). Right, or should Ctrl+Z undo them too? A: Right
- Q-L2: Light drag: which gesture — e.g. hold a key + move the mouse (like `S`/`G`), or `Ctrl+Alt+LMB` drag? A: Hold L + move mouse 
- Q-L3: Should the light be saved with the scene later (now: not saved, resets to Raitt 2:1)? A: Yes
- Q-M1: Base colour by keys as hue / saturation / brightness steps until the colour picker comes — OK? A: Yes
- Q-M2: Mirror copy takes the source's material — OK? A: Yes
- Q-M3: References keep the fixed blue even when they have their own material — OK? A: Yes
- Q-M4: Selected objects tint toward yellow; on a yellow object that is hard to see — acceptable for now? A: Yes
