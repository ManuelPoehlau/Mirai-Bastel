# Artist Playground — Input Ownership Audit

**Status:** Discovery (Type B — observation only, no behavior changes)
**Date:** 2026-09-21
**Scope:** `playground/window.py`, `playground/app.py`, `playground/gizmo.py`
**Relates to:** AD-013 (I3/I4/I5), AD-015 (partial, see addendum)

---

## Purpose

This document is a factual inventory of how interaction ownership currently works in the Playground. It is the evidence base for a future architecture decision. Sections 1–4 are observations from code only. Section 5 is interpretation, clearly labeled.

---

## 1. State Inventory

All fields are on `PlaygroundWindow` unless noted as `app.*` (on `PlaygroundApp`).

### Transform-slot state

| Field | Type | Who writes | Who reads | Handlers |
|-------|------|-----------|-----------|----------|
| `_transform_key_down` | `str \| None` | Q/W/E press (`else` branch); `_clear_transform_state()` → None | on_mouse_drag, on_mouse_motion (guard), on_key_release (commit/exit) | key_press (write), key_release (read+clear), mouse_drag (read), mouse_motion (read) |
| `_transform_mode_on` | `bool` | Q/W/E press (press_mode/press_drag_click first press → True); `_clear_transform_state()` → False | on_mouse_press (gizmo guard), on_mouse_drag, on_mouse_motion, on_mouse_release (press_drag_click commit) | key_press (write), mouse_press (read), mouse_drag (read), mouse_motion (read), mouse_release (read) |
| `_transform_started` | `bool` | `begin_transform()` success in on_mouse_drag/on_mouse_motion → True; `_clear_transform_state()` → False | on_key_press ESC (cancel guard), on_key_release (commit guard), on_mouse_release (press_drag_click commit guard), `_sync_after_transform` | mouse_drag (write+read), mouse_motion (write+read), key_press (read), key_release (read), mouse_release (read) |
| `app.active_tool` | `object \| None` | Q/W/E `else` branch → tool instance; `_clear_transform_state()` → None | on_mouse_press (gizmo guard), on_mouse_drag, on_mouse_motion, on_key_press ESC, on_key_release | key_press (write), all handlers (read) |

**Critical observation:** `app.active_tool` is written **only** in the `else` branch of the Q/W/E dispatch. The V1 and V3 Tweak paths (the `if tv == "v1"` and `elif tv == "v3"` branches) never write `app.active_tool`. The Tweak gesture itself uses a separate `_tweak_tool` field.

### Tweak-family state

| Field | Type | Who writes | Who reads | Handlers |
|-------|------|-----------|-----------|----------|
| `_tweak_v1_key` | `str \| None` | Q/W/E press (V1 branch) → key char; key_release/ESC → None | on_mouse_motion (V1 gesture start), on_key_release (V1 self-deciding) | key_press (write), mouse_motion (read), key_release (read+clear) |
| `_tweak_v1_moved` | `float` | on_mouse_motion V1 branch → incremented; key_press/key_release → 0 | on_key_release (threshold check vs CLICK_THRESHOLD = 5.0 px) | mouse_motion (write), key_press (reset), key_release (read+reset) |
| `_tweak_v3_key` | `str \| None` | Q/W/E press (V3 branch) → key char; key_release/ESC → None | on_mouse_press (V3 LMB arm), on_key_release (V3 key logic) | key_press (write), mouse_press (read), key_release (read+clear) |
| `_tweak_v3_lmb` | `bool` | on_mouse_press V3 branch → True; `_clear_tweak_gesture()` → False | on_mouse_drag (V3 begin), on_mouse_release (V3 commit) | mouse_press (write), mouse_drag (read), mouse_release (read+clear) |
| `_tweak_v3_tool_type` | `str \| None` | on_mouse_press V3 (from `_tweak_v3_key`) → tool type string; `_clear_tweak_gesture()` → None | on_mouse_drag V3 begin | mouse_press (write), mouse_drag (read) |
| `_tweak_v2_armed` | `bool` | on_mouse_press V2+Ctrl branch → True; `_clear_tweak_gesture()` → False | on_mouse_drag V2 begin, on_mouse_release V2 commit | mouse_press (write), mouse_drag (read), mouse_release (read) |
| `_tweak_active` | `bool` | `_tweak_begin()` success → True; `_clear_tweak_gesture()` → False | on_mouse_drag (update guard), on_mouse_motion V1/V4 (update guard), on_mouse_release V2/V3, on_key_press ESC | multiple |
| `_tweak_started` | `bool` | `_tweak_begin()` success → True; `_clear_tweak_gesture()` → False | `_tweak_commit()/_tweak_cancel()` (commit_transform guard), `_sync_after_transform` (_patch_vbo path) | `_tweak_begin` (write), helpers (read) |
| `_tweak_tool` | `object \| None` | `_tweak_begin()` → tool instance; `_clear_tweak_gesture()` → None | on_mouse_drag/motion update, ESC cancel | `_tweak_begin` (write), motion handlers (read) |
| `_tweak_temp_target` | `bool` | `_tweak_begin()` → True when temp pick used; `_tweak_commit/_tweak_cancel` → False | `_tweak_commit/_tweak_cancel` (clear temp selection) | `_tweak_begin` (write), commit/cancel helpers (read+clear) |
| `_tweak_persistent_mode` | `str \| None` | on_key_release V1 tap (no drag) via `toggle_persistent_mode()` → tool type or None | on_mouse_drag V2 begin, on_mouse_motion V4 begin | key_release (write), mouse_drag/motion (read) |
| `_tweak_ctrl_held` | `bool` | Ctrl press → True; Ctrl release → False | on_mouse_press V2 (Ctrl+LMB arm), on_mouse_motion V4 | key_press (write), key_release (write), mouse_press (read), mouse_motion (read) |

### Constraint / space state

| Field | Type | Who writes | Who reads | Handlers |
|-------|------|-----------|-----------|----------|
| `_axis_constraint` | `str \| None` | X/Y/Z press (toggle); Gizmo click → handle name; K press → None | `_tweak_begin()` (axis param), on_mouse_drag/motion begin_transform (axis param), `_draw_gizmo`, Gizmo hit test | key_press (write), mouse_press (write), draw (read) |
| `_transform_space` | `str` | K press → toggles "world"/"normal"; initialized "world" | `_tweak_begin()` (space param), on_mouse_drag/motion begin_transform (space param), `_draw_gizmo`, `gizmo_mode()` | key_press (write), multiple (read) |

**Note:** X/Y/Z constraint toggle is an **independent `if` block** (not in the main elif chain). It always runs on X/Y/Z without Ctrl, even if another branch already handled the key. In practice no other branch claims bare X/Y/Z, so this has no current conflict — but it is structurally implicit.

### Tool / family dispatch state

| Field | Type | Who writes | Who reads | Handlers |
|-------|------|-----------|-----------|----------|
| `app.focused_family` | `str` | Tab press (cycles `app.slots.keys()`) | HUD, on_mouse_press (articulation guard), on_key_press M (which family to cycle) | key_press (read+write), mouse_press (read) |
| `app.select_mode` | `SelectMode` | Set by selection experiment variants activate/deactivate (not directly visible in window.py); `sel.mode` set by 1/2/3 keys | on_mouse_release (`dispatch_click`), selection VBO rebuild | key_press 1/2/3 (write sel.mode), mouse_release (read) |
| `app.select_method` | `SelectMethod` | Shift+M cycling | on_mouse_press/drag/release (BOX guard), on_mouse_release (`dispatch_click`) | key_press Shift+M (write), mouse handlers (read) |

**Note:** `app.focused_family` is NOT consulted by Q/W/E, X/Y/Z, or K. It is only used by Tab (family cycling), M/Shift+M (variant cycling), and the articulation mouse-press guard.

### Other interaction state

| Field | Type | Summary |
|-------|------|---------|
| `_extrude_tool` | `ExtrudeTool \| None` | Created on R press (Face mode); committed on R release (hold) or LMB release (lmb model); cancelled by ESC |
| `_loop_slide_tool` | `LoopSlideTool \| None` | Created on G press (Edge mode); committed on G release; cancelled by ESC |
| `_articulation_state` | `ArticulationState \| None` | Created on LMB press (focused_family == "articulation"); restored by F or ESC |
| `_articulation_dragging` | `bool` | True during LMB drag of articulation gesture |
| `_box_start`, `_box_end` | `tuple \| None` | Set on LMB press (BOX select method, no transform armed); cleared on LMB release |

---

## 2. Entry/Exit Map

### Tweak V1 (TweakV1HoldKey — `tweak_variant = "v1"`)

| Phase | Trigger | State change |
|-------|---------|--------------|
| Arm | Q/W/E press (`tv == "v1"` and `active_tool is None`) | `_tweak_v1_key = key_char`, `_tweak_v1_moved = 0` |
| Gesture start | on_mouse_motion: `_tweak_v1_moved >= CLICK_THRESHOLD` | `_tweak_begin(tool_type)` → `_tweak_active`, `_tweak_started`, `_tweak_tool` |
| Gesture update | on_mouse_motion while `_tweak_started` | `update_transform()`, VBO sync |
| Commit | Q/W/E release: `_tweak_v1_moved >= CLICK_THRESHOLD` | `_tweak_commit()` → `commit_transform()`, `_clear_tweak_gesture()` |
| Tap (no drag) | Q/W/E release: `_tweak_v1_moved < CLICK_THRESHOLD` | `toggle_persistent_mode()` → sets/clears `_tweak_persistent_mode` |
| Cancel (active) | ESC while `_tweak_active` | `_tweak_cancel()` → `cancel_transform()`, `_clear_tweak_gesture()` |
| Cancel (armed) | ESC while `_tweak_v1_key is not None` | `_tweak_v1_key = None`, `_tweak_v1_moved = 0` |

**State exclusively owned during gesture:** `_tweak_v1_key`, `_tweak_v1_moved`, `_tweak_tool`, `_tweak_active`, `_tweak_started`

### Tweak V2 (TweakV2Silo — `tweak_variant = "v2"`)

| Phase | Trigger | State change |
|-------|---------|--------------|
| Arm Ctrl | Ctrl press | `_tweak_ctrl_held = True` |
| Arm LMB | LMB press while `_tweak_ctrl_held` | `_tweak_v2_armed = True` |
| Gesture start | First drag while `_tweak_v2_armed` and `_tweak_persistent_mode is not None` | `_tweak_begin(_tweak_persistent_mode)` |
| Gesture update | Subsequent drag while `_tweak_active and _tweak_started` | `update_transform()` |
| Commit | LMB release when `_tweak_v2_armed or _tweak_active` | `_tweak_commit()` (if active) or `_clear_tweak_gesture()` |
| Ctrl release | Ctrl release when `_tweak_active` | Does NOT cancel (LMB governs) |
| Q/W/E press (V2) | Q/W/E press while V2 active | → **Transform path** (not Tweak): sets `_transform_key_down`, `app.active_tool` |

**Dependency:** `_tweak_persistent_mode` must be set before a V2 gesture can begin. Currently only V1 tap sets it.

### Tweak V3 (TweakV3HoldClick — `tweak_variant = "v3"`)

| Phase | Trigger | State change |
|-------|---------|--------------|
| Arm key | Q/W/E press (`tv == "v3"` and `active_tool is None`) | `_tweak_v3_key = key_char` |
| Arm LMB | LMB press while `_tweak_v3_key is not None` | `_tweak_v3_lmb = True`, `_tweak_v3_tool_type` resolved from key |
| Gesture start | First drag while `_tweak_v3_lmb` | `_tweak_begin(_tweak_v3_tool_type)` |
| Gesture update | Subsequent drag while `_tweak_active and _tweak_started` | `update_transform()` |
| Commit | LMB release when `_tweak_v3_lmb` | `_tweak_commit()` (if active) or `_clear_tweak_gesture()` |
| Key release | Q/W/E release while `_tweak_v3_key == key_char` | `_tweak_v3_key = None`; `_tweak_v3_lmb` and gesture continue until LMB release |
| Cancel (key armed, no LMB) | ESC | `_tweak_v3_key = None`, `_clear_tweak_gesture()` |

### Tweak V4 (TweakV4HoldCtrl — `tweak_variant = "v4"`)

| Phase | Trigger | State change |
|-------|---------|--------------|
| Arm | Ctrl press | `_tweak_ctrl_held = True` |
| Gesture start | on_mouse_motion while `_tweak_ctrl_held` and `_tweak_persistent_mode is not None` | `_tweak_begin(_tweak_persistent_mode)` |
| Gesture update | Subsequent motion while `_tweak_started` | `update_transform()` |
| Commit | Ctrl release while `_tweak_active` | `_tweak_commit()` |
| Q/W/E press (V4) | Q/W/E press while V4 active | → **Transform path**: sets `_transform_key_down`, `app.active_tool` |

**Dependency:** same as V2 — `_tweak_persistent_mode` must be set first.

### Transform — Hold activation (HoldActivationVariant)

| Phase | Trigger | State change |
|-------|---------|--------------|
| Arm | Q/W/E press → `else` branch, `model == "hold"` | `_transform_key_down = key_char`, `app.active_tool = tool` |
| Gesture start | First drag/motion | `begin_transform()` → `_transform_started = True` |
| Gesture update | Subsequent drag/motion | `update_transform()`, VBO sync |
| Commit | Q/W/E release (`_transform_key_down == key_char`) | `commit_transform()`, `_clear_transform_state()` |
| Cancel | ESC while `_transform_started or _transform_mode_on or _transform_key_down` | `cancel_transform()`, `_clear_transform_state()` |

### Transform — Press-Mode activation (PressModeVariant)

| Phase | Trigger | State change |
|-------|---------|--------------|
| Arm (first press) | Q/W/E press → `else` branch, `model == "press_mode"`, `_transform_mode_on == False` | `_transform_mode_on = True`, `_transform_key_down = key_char`, `app.active_tool = tool` |
| Q/W/E release | Key release | `_transform_key_down = None`; `_transform_mode_on` stays True |
| Gesture start | First drag/motion | `begin_transform()` → `_transform_started = True` |
| Commit (second press) | Second Q/W/E press of same key (`_transform_mode_on == True`) | `commit_transform()`, `_clear_transform_state()` |
| Cancel | ESC | `cancel_transform()`, `_clear_transform_state()` |

### Transform — Press-Drag-Click activation (PressDragClickVariant — DEFAULT)

| Phase | Trigger | State change |
|-------|---------|--------------|
| Arm (first press) | Q/W/E press → `else` branch, `model == "press_drag_click"`, `_transform_mode_on == False` | `_transform_mode_on = True`, `_transform_key_down = key_char`, `app.active_tool = tool` |
| Q/W/E release | Key release | `_transform_key_down = None`; `_transform_mode_on` stays True |
| Gesture start | First drag/motion | `begin_transform()` → `_transform_started = True` |
| Commit (LMB release) | LMB release when `_transform_mode_on and _transform_started` | `commit_transform()`, `_clear_transform_state()` |
| Commit (second press) | Second Q/W/E press of same key (`_transform_mode_on == True`) | `commit_transform()`, `_clear_transform_state()` |
| Cancel | ESC | `cancel_transform()`, `_clear_transform_state()` |

### Gizmo

The Gizmo has no interaction state of its own. It always renders when the selection is non-empty. Clicking a handle sets `_axis_constraint` in `on_mouse_press`. It does not start, own, or end an interaction.

| Phase | Trigger | State change |
|-------|---------|--------------|
| Click (set constraint) | LMB press on Gizmo handle (preconditions met — see §4) | `_axis_constraint = hit_handle_name` |

### Extrude, Loop Slide, Articulation, Box Select

These interactions each own their own `_*_tool`/`_*_state` field and have clean enter/exit semantics. They do not share state with the Transform or Tweak families and are not repeated in detail here.

---

## 3. Dispatch Order

### Physical input: Q / W / E (no Shift, no Ctrl)

`on_key_press` structure relevant to Q/W/E:

1. **Early elif chain** (D/Ctrl+Z/Ctrl+Y/I/Shift+R/Shift+C/C/S/R/Shift+D/V/Tab/M/Shift+M/1/2/3/G/Shift+L/Ctrl): Q/W/E are not in this chain. All Q/W/E reach step 2.

2. **Independent `if` block** for X/Y/Z constraint: not applicable to Q/W/E.

3. **Independent `if symbol in (Q, W, E) and not MOD_SHIFT`**: always runs for Q/W/E.
   - Resolves `_key_char` and `_tool_type`.
   - Then evaluates `tv = _active_tweak_variant()`:
     - `if tv == "v1" and app.active_tool is None` → **V1 claims**; transform path skipped
     - `elif tv == "v3" and app.active_tool is None` → **V3 claims**; transform path skipped
     - `else` (V2, V4, or `active_tool is not None`) → **Transform path**:
       - `model == "hold"` → sets `_transform_key_down`, `app.active_tool`
       - `model == "press_mode"/"press_drag_click"` → sets `_transform_mode_on`, `_transform_key_down`, `app.active_tool` (or commits if already in mode)

**Winner determination — code-order and incidental flags:**

| Active tweak variant | Condition | Winner | Reason |
|---------------------|-----------|--------|--------|
| V1 | `active_tool is None` (always true in normal flow) | V1 | V1 path never writes `active_tool`, so the back-off condition is permanently satisfied |
| V3 | `active_tool is None` (always true in normal flow) | V3 | Same reasoning as V1 |
| V2 | N/A (falls to `else`) | Transform | V2 does not claim Q/W/E for Tweak |
| V4 | N/A (falls to `else`) | Transform | V4 does not claim Q/W/E for Tweak |
| None | N/A (falls to `else`) | Transform | No Tweak variant active |
| V1/V3 with external `active_tool` | `active_tool is not None` | Transform | Back-off fires; only achievable by external injection, not normal flow |

**Marked as decided by code order / incidental flags:** V1 and V3 entries. The condition `active_tool is None` is intended as a runtime guard, but it is structurally always true for V1/V3 because neither path sets `active_tool`. There is no explicit rule saying "V1/V3 always own Q/W/E" — the outcome is a side-effect.

### Physical input: X / Y / Z (no Ctrl)

- **Independent `if` block** — always runs for bare X/Y/Z.
- Without Shift: sets `_axis_constraint` to `"x"/"y"/"z"` (toggles off if already set).
- With Shift: sets `_axis_constraint` to `"yz"/"xz"/"xy"` (plane constraints).
- Not gated by any transform/tweak state. Constraint is silently set whether or not anything is active.

### Physical input: K (no modifiers)

- `elif symbol == K and not modifiers` — in the elif chain **after** the Q/W/E block.
- Toggles `_transform_space` between "world" and "normal".
- Resets `_axis_constraint` to None.
- Not gated by transform/tweak state.

### Physical input: LMB (on_mouse_press dispatch order)

1. **Articulation guard** (focused_family == "articulation", vertex hit) → return
2. **Gizmo click** (`active_tool is not None` AND (`_transform_key_down is not None` OR `_transform_mode_on`) AND viewport AND selection non-empty AND vertex_ids) → return on hit; fall through on miss
3. **V2 Ctrl+LMB arm** (V2 active, `_tweak_ctrl_held`) → return
4. **V3 key+LMB arm** (V3 active, `_tweak_v3_key is not None`) → return
5. **BOX select arm** (BOX select_method, no transform armed)
6. `activate()`

### Physical input: mouse drag (on_mouse_drag dispatch order)

1. Articulation drag → return
2. Loop Slide drag → return
3. Extrude drag → return
4. Tweak running gesture (any variant, `_tweak_active and _tweak_started`) → return
5. V2 first drag (armed) → return
6. V3 first drag (armed) → return
7. Transform drag (`_transform_key_down is not None` OR `_transform_mode_on`, AND `active_tool is not None`) → return
8. BOX select rubber-band → return
9. Camera orbit/pan

### Physical input: mouse motion (on_mouse_motion dispatch order)

1. Loop Slide → return
2. Extrude (hold model) → return
3. V1 motion (armed) → return
4. V4 motion (Ctrl held) → return
5. Transform motion (same guard as drag) → return
6. Hover highlighting (no button held)

### Physical input: ESC (on_key_press)

Priority cascade (all `elif`, so first match wins):
1. Articulation restore
2. Loop Slide cancel
3. Extrude cancel
4. Tweak active → `_tweak_cancel()`
5. V1 armed (key down but not started) → clear V1 arm state
6. V3 armed → clear V3 arm state
7. Transform started/mode-on/key-down → cancel/clear
8. Close window

---

## 4. Gizmo Preconditions

The Gizmo click branch in `on_mouse_press` (window.py ~line 839) fires when ALL of:

```python
button == LEFT
and not MOD_ALT
and app.viewport is not None
and not selection.is_empty()
and app.active_tool is not None          # CRITICAL
and (_transform_key_down is not None     # CRITICAL
     or _transform_mode_on)              #
```

If all conditions are met, `pick_gizmo_handle()` is called. If it returns a hit, `_axis_constraint = hit` and the handler returns. If it misses, the handler falls through to V2/V3/BOX/activate.

### Per-variant reachability

| Variant | `active_tool` set by Q/W/E? | `_transform_key_down`/`_mode_on` set? | Gizmo reachable via normal flow? |
|---------|-----------------------------|--------------------------------------|----------------------------------|
| V1 | **Never** (V1 path skips `else`) | Never | **NO** |
| V2 | Yes (V2 → `else` branch) | Yes (hold: key_down; press*: mode_on) | **YES** (after Q/W/E press) |
| V3 | **Never** (V3 path skips `else`) | Never | **NO** |
| V4 | Yes (V4 → `else` branch) | Yes | **YES** |
| None | Yes | Yes | **YES** |

### Can the Gizmo start an interaction on its own?

**No.** The Gizmo click only sets `_axis_constraint`. It does not create a tool, does not call `begin_transform`, and does not set `app.active_tool`. It is a constraint-parameter setter for an already-armed (but not yet started) transform interaction.

### V2 Gizmo — required input sequence

For a Gizmo click to have any effect under V2:
1. Q (or W or E) must be pressed first → Transform path runs → `app.active_tool` set
2. Gizmo handle LMB click → `_axis_constraint` set
3. Mouse drag/motion → `begin_transform(axis=_axis_constraint)` → transform executes with constraint

Whether this sequence produces the correct artist-visible behavior has not been validated. There is no characterization probe for this sequence.

---

## 5. Contradictions with AD-013 and Design Decisions

*(This section is interpretation, not direct observation. It applies the facts above against documented intent.)*

### AD-013 I3 — One interaction authority owns start and end

For V1 and V3: The Tweak paths own start and end of the Tweak gesture cleanly. However, the effect is that no other authority (Transform) can start for Q/W/E while V1/V3 are active. The "one authority" is de-facto V1/V3 permanently, not because of an explicit policy but because the back-off condition is vacuously always satisfied. I3's intent (prevent activation from belonging to authority A and termination to authority B) is nominally satisfied within V1 in isolation, but the broader requirement — that the system supports switching Q/W/E ownership between Tweak and Transform — is not implemented.

### AD-013 I4 — One binding authority at a time

The code attempts to implement I4 via `active_tool is None`. Because V1/V3 never set `active_tool`, this check never transfers ownership to Transform for V1/V3. I4 is not achieved for V1/V3: Q/W/E has a permanent single authority (the Tweak path), but it is permanent by omission, not by policy.

For V2 and V4, I4 is effectively honored. Q/W/E goes to Transform; the Tweak gesture is driven by a different physical input (Ctrl+LMB / Ctrl+motion).

### AD-013 I5 — Binding layers are layered, not forked

The dispatch is a flat if/elif/if structure. There is no layering mechanism. I5 says "the precise mechanism remains an Engineering decision" — so this is not a formal violation, but the current code does not provide a foundation for layering.

### AD-015 stated fix vs actual implementation

AD-015 states: "Tweak (V1/V3) claims Q/W/E only if no transform-owning interaction is already active." The code uses `active_tool is None` as the proxy for "no transform-owning interaction active." But `active_tool` is never set by V1/V3 in normal flow. The check is structurally correct in intent but never fires in practice. See AD-015 Addendum for the formal scope correction.

### Tweak's "SelectMethod-variant" design intent

AD-015 references the 2026-09-13 design decision that Tweak is "usable immediately, no mode switch required." The current implementation over-achieves this: Tweak is not just mode-switch-free, it also blocks Transform from being entered via keyboard. The design intent was "no Tab required before using Tweak," not "Transform is unreachable while V1/V3 are active."

### WP-AP-GIZMO Phase-1 boundary

WP-AP-GIZMO-02 (Gizmo wiring) built the Gizmo under the assumption that `active_tool is not None` would be true when a transform is armed. For V2/V4/no-tweak this holds. For V1/V3 it does not, so the Gizmo click branch is structurally dead for V1/V3 contexts.

**Addendum — 2026-09-21 (AD-016 D3):** This boundary is superseded by an explicit Artist decision. The `active_tool is not None` and `_transform_key_down / _transform_mode_on` preconditions have been removed from the Gizmo click branch. A Gizmo handle click now sets `_axis_constraint` regardless of whether a tool is armed; a subsequent drag executes the current tool along that axis and commits on LMB release. See `docs/architecture/AD-016-TRANSFORM-OWNS-QWE-SINGLE-CURRENT-TOOL.md` D3 for the decision and `playground/tests/test_gizmo.py::TestGizmoWindowDispatch` for test coverage.

---

## 6. Test Coverage

### Covered by characterization tests (`playground/tests/input_characterization.py`)

| Behavior | Probe / Test |
|----------|-------------|
| Q always reaches Transform (D1) | `test_ad016_q_always_reaches_transform` |
| Q sets shared `_current_tool_type` (D2) | `test_ad016_q_sets_shared_current_tool` |
| V1 not in Tweak slot (D5) | `test_ad016_v1_not_in_tweak_slot` |
| V3 not in Tweak slot (D5) | `test_ad016_v3_not_in_tweak_slot` |
| D4 tap sets current tool, no execution | `test_ad016_d4_tap_sets_current_tool_no_execution` |
| D4 hold+drag executes and commits | `test_ad016_d4_hold_drag_executes_and_commits` |
| D4 with selection → no temp target | `test_ad016_d4_with_selection_no_temp_target` |
| D4 with no selection → temp target clears on release | `test_ad016_d4_no_selection_creates_temp_target` |
| D4 ESC clears temp target | `test_ad016_d4_esc_clears_temp_target` |
| V2 reads `_current_tool_type` (D2) | `test_ad016_v2_reads_shared_current_tool` |
| V4 reads `_current_tool_type` (D2) | `test_ad016_v4_reads_shared_current_tool` |
| Gizmo click sets constraint without tool armed (D3) | `TestGizmoWindowDispatch::test_gizmo_click_sets_constraint_without_tool_armed` |
| Gizmo click-only: constraint set, no transform | `TestGizmoWindowDispatch::test_gizmo_click_only_no_transform_on_release` |
| Gizmo drag executes and commits (D3) | `TestGizmoWindowDispatch::test_gizmo_drag_executes_and_commits` |
| Gizmo miss falls through to selection | `TestGizmoWindowDispatch::test_gizmo_miss_falls_through_to_selection` |
| X twice → toggle off | `probe_x_twice` |
| X then Y → replace constraint | `probe_x_then_y` |
| Constraint survives gesture commit | `probe_constraint_survives_commit` |
| Constraint survives gesture cancel | `probe_constraint_survives_cancel` |
| X release does not clear constraint (sticky) | `probe_release_does_nothing` |
| K toggles space world↔normal | `probe_k_toggle_space` |
| K resets axis constraint | `probe_k_clears_axis_constraint` |
| Default transform slot is PressDragClickVariant | `probe_transform_slot_default` |
| Q/W/E/R/S/C/Shift+C/Shift+R key changes (basic) | KEYS / GESTURES tables |

### NOT covered (gaps that remain open)

| Gap | Significance |
|-----|-------------|
| PressModeVariant second-press commit | Not probed |
| HoldActivationVariant key-release commit | Not probed |
| `focused_family` effect on M cycling (non-default families) | Only "selection" family tested |
| Axis constraint + space together in Transform (not Tweak) | Not probed |
| Transform space "normal" + Gizmo normal-frame rendering | Not probed |

---

## Open Questions

### Artist questions (Product Truth / Intent)

1. **Should V1/V3 be able to enter the Transform slot at all?** If Tweak is the only interaction model for V1/V3, the current behavior is correct except that the Gizmo should be treated differently. If V1/V3 should also access persistent Transform, the ownership model needs redesign.
2. **What is the intended relationship between `_tweak_persistent_mode` (set by V1 tap) and V2/V4 begin?** V2 and V4 both depend on this field. Is this intentional shared state, or should V2/V4 have their own mode selection?
3. **For V2: should the Transform path (Q/W/E → active_tool) and the Tweak path (Ctrl+LMB) coexist?** Currently they do — Q/W/E in V2 goes to Transform. Is this the intended behavior?

### Engineering questions

4. **How should `active_tool` signal "transform is armed" for V1/V3?** Options include: setting `active_tool` in the V1/V3 path (but then the Tweak tool and the Transform tool coexist), using a separate ownership flag, or restructuring the dispatch.
5. **Should the Gizmo constraint be settable independently of `active_tool`?** Currently it is gated on `active_tool is not None`. For V1/V3, the Gizmo could alternatively be consulted during `_tweak_begin()` rather than at LMB time.
6. **Is the X/Y/Z constraint toggle independent-`if` structure intentional?** It always fires for bare X/Y/Z, unconditionally. Is this the desired behavior when Extrude or Loop Slide is running?

---

## Addendum 2026-09-23 — WP-STAB-03 Session Gate (implemented)

The structural gap behind engineering question 6 (and the pairwise AD-015/AD-016-style guards) is closed
by one general mechanism in `playground/window.py`. **The gate supersedes per-branch pairwise guards as the
way to keep sessions from interfering; new session types should extend the gate, not add pairwise checks.**

- **`_active_session()`** reads the existing flags (no parallel state machine) and returns the owner:
  `knife` (`_knife_tool`), `articulation` (`_articulation_dragging` only), `loop_slide`, `extrude`,
  `tweak` (`_tweak_active` or `_tweak_v2_armed`), `gizmo` (`_gizmo_drag_armed`),
  `transform` (`_transform_key_down` or `_transform_mode_on`).
- **Keys (`on_key_press`)** — per Artist decision Q4, while a session is live only its own keys and Esc
  pass: Knife Enter / Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z; Articulation F; Tweak Ctrl; Transform X/Y/Z
  (+Shift), K, and the *same* Q/W/E key in the press models (second press = commit). Everything else is
  swallowed — including M and Tab (no variant/focus switch mid-session, B11), 1/2/3, global undo/redo, and
  the display toggles D / Shift+D / V. Key releases are not gated: each release branch already checks its
  own session flag.
- **Esc** is routed to the owning session instead of the first matching flag in the old `elif` chain:
  an armed-but-not-dragged Gizmo or Tweak-V2 no longer falls through to `close()`, and a bent-idle
  Articulation no longer absorbs the Esc meant for a running Transform. Esc still closes the window when
  no session is live.
- **Mouse (`on_mouse_press`/`on_mouse_release`)** — during a session a press is camera navigation
  (MMB, Alt/Shift+LMB/RMB), the session's own gesture (Knife LMB, Extrude-LMB model LMB, Press-Drag-Click
  LMB), or swallowed together with its release (tracked per button in `_gated_buttons`). The Articulation
  press, Gizmo arm, Tweak-V2 arm and Box-select start only run with no session live. A selection click /
  box release never mutates the Selection under a live session. A gizmo handle click during a Transform
  sets the constraint only (the X/Y/Z equivalent, AD-016 D3) and does not arm a second tool.
- **Camera** — orbit/pan pressed during a session always reaches the camera, even though the session drag
  branches (Loop Slide, Extrude, Tweak, Transform) consume every other drag; the release of such a drag
  never commits the session. Zoom (`on_mouse_scroll`) was never gated.
- **Tweak V4** cannot begin inside another session (its motion branch runs before Transform's).
- Tests: `playground/tests/test_session_gate.py` (key matrix over every session × foreign key, repro
  cases, camera during every session, Esc/commit end every session).

**Deliberately unchanged / noted:**
- *Articulation bent-idle* is not a session: it is designed to coexist with other tools (topology
  handlers auto-restore it; the mouse is free for camera after the drag). Only the live bend drag gates.
- *Articulation focus-gating* (B14): with `focused_family == "articulation"` and no session live, LMB
  still always starts a bend and never selects — unchanged, treated as intentional focus-gating. The gate
  only stops it from firing inside another session.
- Q4's strictness also blocks harmless display toggles (D, Shift+D, V) mid-session; relaxing that, and
  per-session modifiers such as Shift-for-midpoint-snapping, is future work.
