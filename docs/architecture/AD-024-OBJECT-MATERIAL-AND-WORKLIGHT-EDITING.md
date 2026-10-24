# AD-024 — Per-object material and Worklight editing in Production

**Status:** DECIDED and IMPLEMENTED (2026-10-24). Proposed as stop point 1 of the handoff "WP Licht + Material in
Production"; reviewed and approved in the planning chat, Manu's answers to §9 on `main` (2de3bb8). Built: §2–§8;
Core precedent in CORE_V1_FREEZE §7.1 ("Object material").
**Baseline:** `main` @ fb91f5b.
**References:** AD-013 (capability ≠ UX), AD-018 (+ Addendum 2026-10-23, the 6-float material packet), AD-021
(object model, §4.6 object commands), CORE_V1_FREEZE §7 / §7.1 (mirror-pairs precedent, format v3),
`docs/research/viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md` §4.1a, `experiments/viewport_shading_lab/`.

## 0. Decisions this AD rests on

- *Artist (Manu, 2026-10-24):* light and material editing in Production first, GUI later. Material is **per object
  and saved with the scene**. Simple: base colour, specular, glossiness.
- *Engineering (handoff):* the light is the global viewport Worklight, not scene lights; `fill_specular` stays a
  Worklight parameter. References keep their fixed tint (Manu, Q-M3 = yes).
- *Artist (Manu, 2026-10-24, §9):* light changes are no Undo steps; light drag = hold `L` + move the mouse; the
  light is to be saved with the scene **later** (not in this package); base colour as hue/saturation/brightness
  steps; the mirror copy keeps the material; the yellow selection tint on a yellow object is acceptable for now.

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

## 2. Data model (field on `SceneObject`)

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
- As built (smaller than proposed, same effect): `Viewport.set_object_entry(..., finish=)` and
  `set_edit_base_color(color, finish=)` take a per-entry finish, `None` = the viewport's finish
  (`set_surface_finish`, unchanged, now "the default finish"). `DisplayState.surface_finish` stays the Worklight's
  finish: its `fill_specular` goes into every packet, its specular/glossiness are the default look of an object
  without a material. `scene_objects.object_finish` composes the per-object finish; after a global finish change
  `_apply_display` re-sends the objects' own (`set_surface_finish` resets every entry). No caller of the old API
  changed.
- **References** draw as today: `REFERENCE_BASE_COLOR` with the default finish; a stored material is kept but not
  shown (Q-M3 = yes). Material setters skip References (they are locked, as for the mirror pairs) and say so in
  the status line.

## 5. Selection highlight

`selected_color(obj, default)` tints the **resolved** base colour (the object's material colour, else the default)
toward `SELECTED_TINT` by `SELECTED_TINT_SHARE`, as today; specular/glossiness are not tinted. The highlight
signature (`_object_highlight_signature`) gains each object's `material`, so Undo/Redo and every other path that
changes a material redraw through the existing per-frame check. Known weak spot: a yellow-ish custom colour is hard
to tell from "selected" (Q-M4: acceptable for now; the cure would be an outline, out of scope).

## 6. Targets of a material edit

- Mode `4`: the selected objects (References skipped; none left → refusal in the status line).
- Modes `1/2/3`: the edit object (never a Reference).
- Setter API on `Application` (later called by the GUI unchanged): `set_object_material(**changes)` (absolute,
  any of `base_color`, `specular`, `glossiness`) and `step_object_material(row_id, direction, fine)` (each target
  from its own values). Refused while an interaction owns the keys (`interaction_owner`) or a Box/Paint drag runs.
- Material rows (`look_controls.MATERIAL_ROWS`, after the 13 light rows in the one arrow-key list): hue (10° / 2°,
  refused on a colour without saturation), saturation, brightness (HSV of the base colour, Q-M1), specular,
  glossiness (0.05 / 0.01; steps `PROVISIONAL`). The HUD row shows the value of the edit object (`1/2/3`) or the first
  selected non-Reference (`4`).

## 7. Undo/Redo

- **Material:** `ObjectMaterialCommand(changes=[(obj, before, after)], description)` in
  `src/mirai/scene_objects.py`, shaped like `ObjectTransformCommand`; pushed with `history.push` +
  `_record_selection_history(..., mesh_step=False)`. Holds the instance (AD-001), so delete → undo → redo keeps the
  material. **No Core History change** — the extra stop point "History cannot carry scene-data edits" does not
  apply. One key step = one Undo step (`HistoryStack` has no public top/merge, E23; coalescing would need a Core
  change and is not worth it here, `PROVISIONAL`).
- **Light:** **not an Undo step** — the Worklight is view state like the display mode, the camera and the SubD view
  (precedent `_subd_command`; Blender's viewport shading is not in the undo history either), and it is not saved.
  Test point 4 then reads: Undo reverts the material, the light stays (Q-L1 = right).

## 8. Worklight setters (no Core change; **built 2026-10-24**, before the review — independent of §2–§7)

- `DisplayState` holds the edit: `light_edit` (a `LightRig`, None = the preset's values) over `light_preset`; the
  label reads "<preset> angepasst" after an edit, as the Lab. A preset (`Ctrl+D`) replaces the edit;
  `Ctrl+Shift+D` keeps toggling the space, which stays across presets and is not an edit.
- `Application.set_light(**changes)` (any `LightRig` field, clamped to the Lab's ranges) and
  `step_light(param, direction, fine)` with the Lab's steps (azimuth 15°/1°, elevation 5°/1°, intensity 0.05/0.01,
  Kelvin 500/100, wrap 0.1/0.02, ambient 0.05/0.01, ratio over `RATIO_STEPS`, coupling and space as toggles).
- Rows and steps: `src/mirai/viewport/look_controls.py` (a copy of the Lab's rows; parity held by
  `experiments/viewport_shading_lab/tests/test_production_look_parity.py`). A row that does not apply (fill off /
  coupled) is refused with a status line instead of changed invisibly.
- Temporary bindings (`PROVISIONAL`, binding layer, keymap-overridable, commands `LookRow*` / `LookValue*`): `↑`/`↓`
  row, `←`/`→` value, `Ctrl+←`/`Ctrl+→` fine (the Lab's `Shift` is taken by the selection steps `Shift+arrows`).
  Allowed at any time, like the display keys. The HUD row "Look" and the status line show the active row and value.
  The material rows follow in the same list (§6).
- **Morph Lab key conflict (finding, not fixed here — the Morph system is out of scope):** the Morph Lab asserts its
  arrow keys are free in the app bindings (AD-013 H2-R1) and has failed at start since `Shift+↑/↓` became Loop
  grow/shrink (WP Toolbox Gaps A1, 2026-10-23, on `main` before this AD); the plain arrows widen the same conflict.
  Under H2-R1 the Lab moves its keys; that is a Morph Lab change for a separate step.
- **Light drag:** the Lab's plain `LMB` drag is `SelectDrag` (Box/Paint) in Production, every modifier variant of
  `LMB` drag is taken and RMB/MMB are deliberately unbound (AD-013 rule 2) — reported, not remapped. Manu's answer
  (Q-L2): **hold `L` + move the mouse** (command `LightDrag`, global `l` was free; the Topology Lab's own `l` keeps
  priority there, `Shift+L` stays Edge Loop). The Lab's 0.5° per pixel, dx → key azimuth, dy → key elevation; not
  underneath a held W/E/R/T/G; release ends it; no Undo step.

## 9. Artist questions (answered by Manu 2026-10-24)

- Q-L1: Light changes are not Undo steps (view state, like the camera). Right, or should Ctrl+Z undo them too? A: Right
- Q-L2: Light drag: which gesture — e.g. hold a key + move the mouse (like `S`/`G`), or `Ctrl+Alt+LMB` drag? A: Hold L + move mouse 
- Q-L3: Should the light be saved with the scene later (now: not saved, resets to Raitt 2:1)? A: Yes
- Q-M1: Base colour by keys as hue / saturation / brightness steps until the colour picker comes — OK? A: Yes
- Q-M2: Mirror copy takes the source's material — OK? A: Yes
- Q-M3: References keep the fixed blue even when they have their own material — OK? A: Yes
- Q-M4: Selected objects tint toward yellow; on a yellow object that is hard to see — acceptable for now? A: Yes

Still open (for the practical test): are the material steps (hue 10°, the rest 0.05) and the row order (light first,
`↑` from the first row jumps to the material) comfortable; does `L` + mouse turn the light the expected way round.

## Praxistest für Manu (deutsch, ca. 15 Minuten)

Start: `python src/main.py`. Die HUD-Zeile „Look“ (unten bzw. oben links, `H`) zeigt, welcher Wert gerade dran ist.
`↑`/`↓` wählt den Wert, `←`/`→` ändert ihn, `Strg+←`/`Strg+→` fein. Erst kommen die 13 Licht-Werte aus dem Shading
Lab, danach (oder mit `↑` von ganz oben) die 5 Material-Werte. Alle Tasten sind vorläufig, bis die GUI kommt.

1. **Licht:** Richtung (Key Azimut/Höhe, oder `L` halten und die Maus bewegen), Verhältnis Key:Fill, Temperatur,
   Weichheit (Wrap) und Grundhelligkeit ändern. Fühlt es sich an wie im Lab? Dreht `L` + Maus in die erwartete
   Richtung (rechts = Licht nach rechts, hoch = Licht höher)?
2. **Material:** `4`, ein Objekt anklicken, Farbton/Sättigung/Helligkeit, Specular und Glossiness ändern; dann ein
   zweites Objekt anders einstellen. Beide bleiben getrennt. (Ein graues Objekt braucht erst etwas Sättigung, bevor
   der Farbton etwas tut.) In `1`/`2`/`3` wirken die Material-Werte auf das bearbeitete Objekt.
3. **Speichern:** `Strg+S`, Programm neu starten, Szene im `SPACE`-Menü laden — die Materialien sind da. Eine alte
   Szene (vor heute gespeichert) lädt weiter, ihre Objekte im Standard-Grau.
4. **Undo/Redo:** nach einer Material- und einer Licht-Änderung `Strg+Z` — das Material geht zurück, das Licht bleibt
   (Licht ist Ansicht, wie die Kamera); `Strg+Y` stellt das Material wieder her.
5. **Auswahl und Tempo:** in `4` ein eingefärbtes Objekt auswählen — die gelbe Auswahl-Tönung liegt sichtbar auf der
   eigenen Farbe. Orbit/Zoom sind nicht langsamer.

Fragen: Stufen angenehm (Farbton 10°, sonst 0.05)? Reihenfolge Licht → Material so gut, oder Material zuerst?
