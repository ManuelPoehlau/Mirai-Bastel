# AD-027 — Interaction layer: one session slot, one `can_run`, feature controllers

**Status:** **DECIDED (Manu, 2026-10-29: go with C1–C3; V1, V3, V7 stay as they are).** Proposed the same day as the
Architecture Gate (Type C) stop point; second opinion [DEVCHAT-001](../archive/interaction_layer/reviews/AD-027_REVIEW_DEVCHAT_001.md)
(Development chat): ACCEPT WITH CHANGES, disposition in §12. **M0–M4 implemented (2026-10-30)**; M5–M8 open (§7,
findings of the steps so far in §7.1).
**Mode (M5):** Production (a behaviour-neutral restructuring), in fresh sessions with this AD as the handoff (§7).
**Baseline:** `main` @ `dfd6e5d`. Every code fact, line count and probe result below was read or run there.
**References:** AGENTS.md §5, §7, §7a, §8a · Development System §5 · [SOURCE_ARCHITECTURE](SOURCE_ARCHITECTURE.md) ·
[INPUT_COMMAND_TOOL_CONTRACT](INPUT_COMMAND_TOOL_CONTRACT.md) §5 · [AD-013](AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md)
(H2 command gate, H7 surface provider, addendum 2026-10-28) · [AD-015](AD-015-PLAYGROUND-INPUT-OWNERSHIP-TWEAK-TRANSFORM.md) ·
[AD-016](AD-016-TRANSFORM-OWNS-QWE-SINGLE-CURRENT-TOOL.md) · [AD-017](AD-017-CUT-ENGINE-CONTEXTUAL-C.md) ·
[AD-019](AD-019-POINTER-CLICK-VS-DRAG-BINDINGS.md) · [AD-021](AD-021-OBJECT-COMPONENT-MODEL.md) (L-1) ·
[AD-025](AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md) §4.4, §15, §17.5 · [GUI_STAGE1_HUD](../design/GUI_STAGE1_HUD.md) §3 ·
code: `src/mirai/application.py`, `src/mirai/interaction/`, `src/main.py`, `src/hud.py`, `experiments/morph_lab`.

## Kurzfassung für Manu (Deutsch)

- **Was:** Die App-Steuerung (`Application`, 7 713 Zeilen) wird so umgebaut, dass Pose-Modus, klickbare GUI und
  Morph-Regler andocken, ohne dass diese Datei weiter wächst. Drei Teile: **ein Platz** für die gerade laufende
  Interaktion (Knife, W/E/R halten, Box-Auswahl …); **eine Frage** „darf dieser Befehl jetzt laufen?“, die Tasten,
  Befehle, HUD und später Buttons gleich beantwortet; **Knife, Morph, Objekte, Symmetrie** und die Halte-Gesten
  ziehen in eigene Module.
- **Verhalten:** bleibt gleich, auch in Ecken wie „P halten, dann W, dann Esc“ (§1.1; deine Entscheidung: V1, V3, V7
  bleiben so). Belegt wird das so: Vor dem Umbau werden zehntausende zufällige und geskriptete Eingabefolgen
  aufgezeichnet; nach jedem Umbauschritt müssen sie Schritt für Schritt exakt gleich ablaufen (§6). Danach bleiben
  nur die lesbaren Szenarien als Tests; die Zufallsaufzeichnung wird gelöscht, damit sie spätere gewollte Änderungen
  (Tasten, Phase 6) nicht blockiert.
- **Stand:** entschieden (dein Go, 2026-10-29, mit den drei Änderungen der zweiten Meinung, §12). Der Umbau läuft in
  drei frischen Sessions (§7); die erste (M0–M2: Aufzeichnung, Platz, eine Frage) ist fertig (2026-10-30). Kein
  Abhak-Test: normal weiterarbeiten und melden, wenn sich etwas anders anfühlt (§10).
- **Danach:** AD-025 Phase 6 mit dem Kiefer-Szenario.

## 0. Decisions this AD rests on

- *Artist (Manu, 2026-10-29):* order = docs/status → this gate → AD-025 Phase 6 with the jaw scenario (jaw bone +
  weights, one expression as morph, then a loop inserted at the mouth corner; pose, weights and morph survive, also
  through save/load). **Behaviour stays as it is.**
- *Engineering (handoff):* the target has three parts: (a) one slot for the active modal session with a common
  protocol (key, pointer, cancel, commit, draw/status); (b) one `can_run(command, context) -> refusal | None` used by
  key resolution, `dispatch_command`, the HUD and later the GUI; (c) feature clusters (at least Knife, Morph, Objects,
  Symmetry) move out of `Application` into controllers along existing seams; `Application` stays the orchestrator.
  Reference designs Blender and Maya, adapted, not copied. The justification is the known next users (skeleton pose
  mode, clickable GUI, morph sliders), not neatness; no failure has been observed yet.
- *Assumption (unconfirmed, from the handoff):* the clickable GUI (Mirai UX project) dispatches through the same
  command path. If it does not, only the GUI use of (b) is wasted; (a) and (c) stand on their own.
- *Artist (Manu, 2026-10-29), after the second opinion:* "Go for AD-027 with C1-C3. V1, V3, V7 stay as they are."
  (C1–C3 and the review: §12.)

## 1. Problem (measured at `dfd6e5d`)

| Fact | Value |
|---|---|
| `src/mirai/application.py` | 7 713 lines (2 470 on 2026-10-12); class `Application` 6 981 lines, 332 methods (91 public) |
| Fields set in `Application.__init__` | 128, of which **61 are modal state** (non-default only while an interaction runs) for 16 interactions (§3.1) |
| Checks of four of those states | `_transform_key` 28 sites, `_knife` 21, `_resym_plan` 10, `_drag_select` 7 |
| Refusal logic | `_gate_refuses` (host gate), `_layer_gate_refuses` (AD-025), `_object_mode_refuses` (AD-021), `_hidden_refuses`, plus silent `return False` gates inline in `key_press`, the `pointer_*` handlers and the `_*_arm` functions |
| Method lines by cluster (classified by method name) | gestures (W/E/R, T, G, S, I, Ctrl+B) 1 052 · objects 1 016 · topology commands 644 · scene lifecycle 633 · gizmo / pivot / drag select / lasso / light drag 508 · pointer / hover / views 432 · Knife 390 · mask / hide / regions 378 · keys / dispatch / gates 357 · morph 349 · history / transactions 240 · soft 237 · display / look 121 · symmetry 114 |

What the next users would do to this structure today:

- **Pose mode** would add a mode field plus a branch in `key_press`, `pointer_press/drag/release/motion`, `_cancel`,
  `_update_hover`, `interaction_owner`, and one more `_*_refuses`.
- **A GUI button** has no gated entry: `dispatch_command` lacks most key gates (no host gate, no hidden-geometry gate,
  no session gates). A button could do what the key cannot, e.g. switch the component mode inside a Knife session.
- **A morph slider drag** must own the pointer like a held W: today that is another `_x_key` field and branches in the
  same six entry points (`cursor_wrap_active` is already meant to be reused for it, GUI_STAGE1_HUD §3).

### 1.1 Code facts this AD rests on (probes run headless at `dfd6e5d`)

The precedence among interactions today is **fixed by kind, not by the order they started** — a constraint every
alternative in §4 is measured against.

| # | Sequence | Today | Rule in §3.2 that reproduces it |
|---|---|---|---|
| V1 | hold P (pivot), then W (Move armed), Esc | Esc cancels the pivot placement; Move stays armed | hold claims (stage 2) before the session (stage 3) |
| V2 | W armed, then P | P refused silently | `GestureSession.allows(PivotPlace)` silent |
| V3 | hold P, W armed, LMB click | pivot placed while Move stays armed | hold claims LMB press before the session |
| V4 | hold L and N (either order), move the mouse | the light turns, the weight does not | hold background in fixed rank (Light before Morph weight) |
| V5 | hold L, hold W, move, release W, move | motion drives Move; after the commit motion turns the light again | session (3) before hold background (4) |
| V6 | hold P, then C (Knife), LMB click, Esc | LMB sets a Knife point; Esc ends the Knife, P stays held | the Knife grabs keys and its LMB (stage 1) |
| V7 | hold P, then Alt+M (Re-Symmetrize preview), LMB, Esc | LMB places the pivot under the open preview; Esc closes the preview, P stays held | the preview grabs keys and hover, not the raw LMB press |
| V8 | the tests call `dispatch_command` directly 635 times | 10 calls (7 tests) happen in a state the key path refuses; 9 of them are already refused inside the command (Shift+S, Apply, Delete under a held gesture or a Knife session); 1 sets Wireframe during a Knife session | `can_run` asks the session per **command**: the Knife allows view-state commands (§3.3) |
| V9 | writers of `command_gate` / `hover_suspended` (AD-013 H2) | none in any host since the Symmetry Lab was removed (2026-10-24); only tests | kept as `can_run` stage 2 (open point 5) |

Probe scripts are throwaway (not committed); M0 (§7) turns V1–V7 into scripted golden sequences.

## 2. Reference designs (adapted, not copied)

- **Blender.** A running modal operator sits in the window's handler list and sees events first; its `modal()`
  returns RUNNING_MODAL, PASS_THROUGH, FINISHED or CANCELLED. Every operator has `poll(context)`, and the keymap,
  menus and buttons (greyed out when poll fails) and Python calls all ask the same poll.
- **Maya.** Exactly one current tool context (`MPxContext`) receives press/drag/release; hotkey press/release pairs
  (e.g. hold B + drag for the brush size) are a lighter mechanism than a context.
- **Taken:** one running session that sees events first and can pass them through (`handle(...) -> PASS`); one
  availability check shared by every trigger (`can_run` ≈ poll); held keys as a separate, lighter kind than sessions.
- **Not taken:** Blender's handler list as a general stack (Mirai's precedence is not push order, V1/V4); operator
  properties, redo panel and runtime registration; Maya's per-context tool settings and property sheets.

## 3. Decision

### 3.1 What counts as modal state

- **Session** — an interaction that runs over several events and owns some input while it runs. At most one.
- **Hold key** — a held key that changes what the pointer does: Lasso (Q), Working Pivot (P), Light (L), Morph weight
  (N) — the `commands.HOLD_COMMANDS` that are not gestures. Several may be held; a session may start while one is held
  (V1, V5, V6, V7); each ends with its own key release (the pivot also on Cancel).
- **Not modal** (stays where it is, or moves with its controller as plain state): input tracking (`_cursor`,
  `_press_point`, `_shift/_ctrl/_alt_held`); sticky settings (`_axis_constraint`, `constraint_mode`, `_orientation`,
  `_soft`, `tweak_command`, `gizmo_size_name`, `knife_mirror_variant`, `_working_pivot`, `_morph_ab`); **modes** that
  outlive interactions (`selection.mode` including object mode `4`, the morph target editing view `_target_view`;
  pose mode later) — a mode is read by `can_run`, it owns no input; navigation (`PointerGestures` per AD-019,
  `_orbit_virtual`, `_view_name`, `_ortho_auto`: camera gestures own no keys and coexist with every session, H2-R2);
  the AD-013 H2 host hooks (`command_gate`, `_hover_suspended`); document state.

### 3.2 (a) The slot

`Application.interaction: InteractionSlot`, in `src/mirai/interaction/session.py` (imports nothing from
`mirai.application`). Working shape — final names may change in the implementation, the contract may not:

```python
PASS = ...  # sentinel: "not mine", routing continues

@dataclass(frozen=True)
class Refusal:
    text: str | None                     # None = silent (today's bare `return False`)

class Session(Protocol):
    owner: str | None                    # the AD-013 H2 `interaction_owner` value: "transform" | "knife" | "resymmetrize";
                                         # None for pointer-only sessions (drag select, gizmo press)
    label: str | None                    # what the HUD shows as running ("Move", "Knife", ...)
    def grabs(self, event) -> bool       # decides this event alone, before hold keys and gates
    def allows(self, command: str, ctx) -> Refusal | None   # may `command` run underneath it? (a stage of can_run)
    def handle(self, event) -> bool | PASS                  # key, pointer, modifier, hover and command events
    def cancel(self) -> bool             # Esc, shutdown: exact prior state, no history entry
    def commit(self) -> bool             # its normal end (key / LMB release, Enter, the second Alt+M): <= 1 entry

class HoldKey(Protocol):
    command: str; key: str
    def claims(self, event) -> bool | PASS       # before the session (Pivot: LMB press/drag/release, Cancel, hover)
    def background(self, event) -> bool | PASS   # after the session (Light, Morph weight: motion)
    def release(self) -> bool                    # its key went up (Pivot: a tap toggles, Morph weight: a tap = A/B)

class InteractionSlot:
    session: Session | None
    holds: tuple[HoldKey, ...]           # fixed rank: Pivot, Lasso, Light, Morph weight
    def start(self, session) -> None     # asserts the slot is empty
    def end(self, session) -> None
    def grab(self, event) -> bool | PASS     # stage 1 only (the key path continues with can_run)
    def route(self, event) -> bool | PASS    # stages 1-4 (pointer, modifier, hover, release events)
```

Events are small frozen dataclasses: `KeyPress`, `KeyRelease`, `Press`, `Drag`, `Release`, `Motion`, `Wheel`,
`Modifiers` (Shift/Ctrl/Alt held changed), `Hover` (re-pick at the cursor), `Leave`, `Command`.
**Draw/status:** a session pushes its viewport overlays through the services (§3.4) at its events, as today; what the
window and HUD read (`knife_render_data`, `selection_box`, `selection_lasso`, `gizmo_items()` hidden while a gesture
runs, `pivot_marker_items()`, `cursor_wrap_active`, the HUD's running label) stays public on `Application` and reads
the slot. No new draw timing.

**Routing rule** (`InteractionSlot.route`; the only place precedence lives inside `Application` — a UI hit-test in
front of it, §3.5, is outside this rule):

1. **Grab:** if `session.grabs(event)`, the session alone handles it.
2. **Hold claims** in rank order.
3. **Session** — pointer, modifier and hover events go to `session.handle`. A key press takes the command path:
   resolve through the BindingSet → `can_run` → the command's handler; a handler that concerns the session reaches
   it as `handle(Command(...))` (Cancel; Undo/Redo while a gesture is only armed: disarm, then run; constraint keys;
   `K` before the gesture has begun).
4. **Hold background** in rank order.
5. **Idle** — `Application`'s own behaviour: hover pick, click selection, drag start, gizmo press, zoom.

This reproduces every case in §1.1 (last column). `interaction_owner` becomes `session.owner` or `None` — same values,
same moments, never a camera gesture (H2-R2).

**Inventory** (61 fields leave `Application`):

| Interaction | Today | Becomes | owner | grabs | ends |
|---|---|---|---|---|---|
| hold-key gestures: W/E/R (components), T, G (Loop / Vertex Slide), S / Alt+S, I (faces), Ctrl+B; the gizmo / `Tweak` LMB drag | `_transform_*` (5), `_extrude_*` (3), `_slide_*` (5), `_vslide_*` (3), `_offset`, `_smooth_*` (5), `_constraint_retouched`, `_rotate_press`, `_rotate_virtual`, `_ctrl_snap_ok`, `_soft_gesture`, `_soft_gesture_reference`, `_soft_op_running`, `_soft_gesture_shown` | `GestureSession`, one kind per gesture | `"transform"` | nothing | its key or LMB release (commit), Cancel, a refusal at `begin()` |
| object gesture (W/E/R in `4`) | `_object_gesture` | a `GestureSession` kind (ObjectController) | `"transform"` | nothing | same |
| Knife | 13 `_knife*` fields | `KnifeSession` | `"knife"` | keys (resolved in `knife`), plain / Shift LMB and the KnifeLift button (press, drag, release), motion, hover, Shift held, Soft wheel steps, leave | Enter (commit), Esc (cancel) |
| Re-Symmetrize preview | `_resym_plan` | `ResymPreview` | `"resymmetrize"` | keys, select / region clicks, select / Tweak drags, gizmo press, Soft wheel steps, hover | Alt+M again (commit), Esc |
| Box / Paint / Lasso drag | `_drag_select` | `DragSelect` | None | nothing (it allows only Cancel, display, look, ortho, session switches, SubD) | LMB release (commit), Esc |
| gizmo handle press, before the drag decides | `_gizmo_gesture`, `_gizmo_press_xy`, `_gizmo_constraint_before` | `GizmoPress`; on the first drag step it is replaced by a `GestureSession` that carries the handle | None → `"transform"` | nothing | LMB release (a click sets only the constraint) |
| a refused LMB gesture | `_gesture_refused` | `SwallowedGesture` | None | its select / Tweak / gizmo drag steps | LMB release |
| hold keys | `_lasso_held`; `_pivot_key`, `_pivot_before`, `_pivot_placed`, `_pivot_dragging`, `_pivot_preview`, `_pivot_on_plane`; `_light_drag_key`; `_morph_drag_key`, `_morph_drag_moved`, `_morph_drag_rest` | `LassoHold`, `PivotHold`, `LightHold`, `MorphWeightHold` | — | — | key release (Pivot: also Cancel) |

### 3.3 (b) `can_run`

```python
@dataclass(frozen=True)
class RunContext:
    source: str                 # "key" | "click" | "drag" | "wheel" | "ui" | "api"
    input: Input | None = None
    operands: bool = True       # False: skip stage 5 (the selection-dependent check), for the HUD each frame

def can_run(self, command: str | None, ctx: RunContext) -> Refusal | None: ...
```

**Pure:** no status line, no hover flush, no state change; an unbound input (`None`) is never refused (as today).
**Stages, in today's `key_press` order:**

1. a **grabbing session**: its `allows` alone (Knife, Re-Symmetrize preview);
2. **host gate** — AD-013 H2 `CommandGate` (command identity);
3. **layer / view gate** — AD-025 §4.4 at command level and the §15 editing view (MorphController);
4. **object mode** — AD-021 L-1 (ObjectController), same texts;
5. **hidden geometry** — topology commands next to hidden geometry (operand stage; reads selection and hover);
6. the **running session's `allows`** — a held gesture refuses silently: mode, placement, topology, Pivot / Lasso /
   Light / morph keys, Undo/Redo and `K` once it has begun, the constraint keys under T / G / S / I / Ctrl+B; the drag
   select allows only its list; the gizmo press refuses nothing;
7. **mode policies** — empty today; the place a pose mode adds its rule.

**The rule that keeps behaviour:** `can_run` contains exactly the checks that run today *before the command's first
side effect*. A check that runs after one stays in the command as an outcome: `tweak_command` is set before a second
W/E/R is refused under a held gesture (so the HUD tool changes, as today); the Morph "no target" text; `C: nothing to
do here`; every "nothing selected" text.

**Callers:** `key_press`; `dispatch_command`, which becomes the **gated public entry** (internal calls go to an ungated
`_execute`, as they run after the gate today); the click, drag-start, wheel, gizmo and Tweak paths; the HUD (data only:
`HudState` gains the hinted commands `can_run(..., RunContext("ui", operands=False))` refuses — the look is unchanged,
greying is the UX project's decision); later the GUI.

**Session allow-lists are per command, from any source.** A session that grabs keys resolves them in its own way (the
Knife in the `knife` context, as today); its `allows` says which commands may run underneath it from any source. The
Knife allows its own commands, Cancel, Undo/Redo (routed to its isolated history, AD-017) and view state (display,
look, ortho), so V8's Wireframe-during-Knife call keeps working and no key does anything new.

**Two differences, both visible only with a host gate (no host writes one, V9):** the drag start in mode `4` today
posts the mode text before it consults the host gate (one stage order lets the gate's text win), and
`dispatch_command` consults no host gate today (it will). The trace corpus (§6) runs without a gate;
`tests/test_command_gate*.py` cover neither case. Every other gate `dispatch_command` gains (hidden geometry, the
session stages) changes no test outcome (V8, probed with the hidden-geometry check included).

**Where key and API differ today, both stay, keyed on `ctx.source`:** a hold command arms its gesture on a key but
activates the tool from the API (`dispatch_command(MOVE, context=...)`); Undo from a key posts its status and rebuilds
the view, from the API it does not. Unifying them changes API behaviour and is not part of this gate.

### 3.4 (c) Controllers

Package `src/mirai/controllers/`. Each controller gets an `AppServices` object, never `Application`; `Application`
builds them in `__init__` and keeps its public API as thin delegating properties and methods, so `src/main.py`,
`src/hud.py`, the Morph Lab and every public-API test are untouched.

| Module | Moves out of `Application` | Sits on (existing seam) | Contributes |
|---|---|---|---|
| `knife.py` | the Knife cluster (~390 method lines, 13 fields) | `topology/knife*.py` (`KnifeTool`), `symmetric_knife.py` | `KnifeSession` |
| `morph.py` | target lifecycle, weight, A/B, editing view and its history translation (~349) | `morph_targets.py`, `morph_mix.py`, `surface_chain.py` | `MorphWeightHold`, `can_run` stage 3 (view), the editing view as a mode |
| `objects.py` | add / import / export / delete, mirror pairs, Reference, Apply / Clear, per-object material and texture display (AD-024, AD-026), object views, highlight, cameras, pick caches, edit-object switch, object click (~1 016) | `scene_objects.py`, `object_mirror.py`, `object_space.py` | the object gesture kind, stage 4 |
| `symmetry.py` | Shift+S cycle, Re-Symmetrize, symmetry display, reports cache (~114) | `symmetry*.py`, `resymmetrize.py`, `symmetry_declarations.py` | `ResymPreview` |
| `gestures.py` | the hold-key gestures and their Soft live radius / flow (~1 052) — required because their state is modal | `interaction/tool_manager.py` + `tools/`, `topology/{loop_slide,vertex_slide,smooth,inset,bevel,extrude}.py` | `GestureSession` and its kinds |
| `pointer_tools.py` | Box / Paint / Lasso, gizmo press, Working Pivot, light drag (~508) — required for the same reason | `viewport/box_select.py`, `viewport/gizmo.py`, `pivot.py` | `DragSelect`, `GizmoPress`, `SwallowedGesture`, `PivotHold`, `LassoHold`, `LightHold` |

**`AppServices`** (`controllers/services.py`; the complete list, a controller uses nothing else): read access to
`scene`, `selection`, `history`, `camera`, `display`, `bindings`, `viewport`, `interaction`, the cursor, the press
point, the viewport size, the held modifiers and the edit camera; and `status(text)`, `can_run(...)`,
`selection_snapshot()`, `restore_selection(...)`, `record_selection_history(...)`, `mesh_transaction(...)`,
`invalidate_picks()`, `notify_vertices_moved(ids)`, `notify_topology_changed()`, `notify_selection_changed()`,
`set_hovered(...)`, `refresh_hover()`, `pick(x, y)`, `pick_face(x, y)`, `soft_preview_refresh(...)`,
`set_edit_object(id)`, `follow_edit_object()`. Services that another controller owns (`set_edit_object` →
ObjectController) are forwarded, so controllers never import each other.

**Command table.** `dispatch_command`'s if-chain becomes one `dict[command, handler]` built once in `__init__` from the
controllers and `Application`'s own handlers, asserted one handler per command. It is a static table, not a plugin
system: nothing registers at runtime (AD-013 H2 alternative E stays rejected).

**Stays in `Application`** (the orchestrator): construction and wiring; scene lifecycle (`init_scene`, `load_scene`,
`save_scene_file`, `frame_scene`); the public entry points, now thin (resolve → slot → `can_run` → table); `can_run`;
history, transactions and the selection mirror; hover and picking; navigation and views; display and the Worklight
look; Soft settings and preview; mask / hide / regions; the topology commands (`C`, Delete / Dissolve, Collapse, loops,
selection steps). Expected size **≈ 4 000–4 500 lines** (an estimate, not a target). Moving the last four groups too is
possible later along the same seams, when a user needs it; it is not part of this gate.

What `key_press` looks like afterwards (sketch):

```python
def key_press(self, input: Input) -> bool:
    self.flush_hover()
    grabbed = self.interaction.grab(KeyPress(input))           # Knife, Re-Symmetrize preview
    if grabbed is not PASS:
        return grabbed
    command = self._resolve_key(input)                         # global → subd → morph; I = Inset in face mode
    ctx = RunContext("key", input)
    refusal = self.can_run(command, ctx)
    if refusal is not None:
        return self._refused(refusal)                          # posts the text unless silent; False
    handler = self._handlers.get(command)
    return False if handler is None else handler(command, ctx)
```

### 3.5 How the next users plug in

- **Pose mode** (Phase 6 and later): a SkeletonController with the mode as its state, a stage-7 policy ("in pose mode
  only bone commands"), and bone rotation as a `GestureSession` kind. `Application`: build the controller, one entry
  in the policy tuple, its handlers in the table. No new field, no new branch in an entry point.
- **Morph slider (GUI):** a `SliderDrag` session; Esc restores the value; `cursor_wrap_active` asks the slot. Whether
  its owner is a new `interaction_owner` value stays GUI_STAGE1_HUD §5 Q4 (not decided here).
- **GUI button:** `dispatch_command(cmd)` with the same gates as the key; greyed out when
  `can_run(cmd, RunContext("ui", operands=False))` refuses.
- **UI in front of the slot (C2).** A grabbing session takes every pointer event *that reaches `Application`* (the
  Knife: every plain LMB). A window-level UI hit-test may therefore sit in front of `Application.pointer_*` and so in
  front of `InteractionSlot.route`: a press on a panel goes to the UI, a miss goes on to `Application`. Which presses a
  panel takes while a session runs is **not decided here** (Mirai UX project; GUI_STAGE1_HUD §5 Q4). The slot API
  keeps this open: the slot knows no window and no panel; `Application.pointer_*` stay its only pointer entries; no
  session assumes it sees every pointer event — only every event of a press it took. The one requirement on such a
  UI layer: drags and the release follow their press (capture at press, as `PointerGestures` fixes a gesture at
  press, AD-019), so a session never loses the release of a press it took, and a panel never gets half a viewport
  gesture.

## 4. Alternatives

| | Alternative | Assessment |
|---|---|---|
| 0 | Status quo | **Not used because** every next user adds fields and branches in about six entry points (66 checks of four states today, §1), and the GUI would have no gated entry |
| A | A Blender-style handler stack: the newest session sees events first, push order decides | **Not used because** Mirai's precedence is not push order (V1, V3: a later W loses Esc and LMB to a held P; V4: Light beats Morph weight in either order) — a stack changes behaviour; and it invites nested sessions no current interaction needs |
| B | A strict single slot with hold keys as ordinary sessions | **Not used because** a W pressed under a held L or P would be refused or end the hold (V1, V5, V7) — a behaviour change |
| C | A state machine / statechart framework | **Not used because** it names every combination as a state (16 interactions × 4 hold keys) where a five-stage rule suffices; nothing in the project's history asks for it |
| D | An event bus or plugin registry | **Not used because** AD-013 H2 rejected it (alternative E), INPUT_COMMAND_TOOL_CONTRACT §3 rules out a complex framework without a demonstrated use case, and nothing needs runtime registration |
| E | Split `Application` into mixin files (same object) | **Not used because** the 128 fields and the if-chains stay in one object; a new domain still edits the chains |
| F | Controllers only, no slot and no `can_run` | **Not used because** modal state stays scattered and refusals stay in four functions plus inline gates: parts (a) and (b) are missing |
| **G** | **Slot (one session + ranked hold keys) + one staged `can_run` + controllers behind `AppServices`** | **Chosen** (§3) |

## 5. Effect on decided ADs and documents

| Document | Effect |
|---|---|
| AD-013 H2 | `dispatch_command` uses `can_run` (was: "no gate checks in `dispatch_command`"); G-2's note "a direct `dispatch_command(CONNECT)` is context-gated but not identity-gated" no longer holds — it is both. `interaction_owner` is `session.owner` (values unchanged). The H2 gate sites become `can_run` stage 2. H2-R5 (`src/main.py` writes no gate) and H2-R6 (one writer) unchanged. The note is written into AD-013 in the commit that builds `can_run` (M2). |
| AD-013 H7, addendum 2026-10-28 | unchanged: keys resolve only through the one BindingSet; the Knife session resolves in `knife`, the SubD and morph keys after global, as today |
| AD-015, AD-016 | unchanged: AD-016 D2's one current tool is `tweak_command`, a setting, not the slot; D3 (gizmo entry) and D4 (hold-key hover) keep their mechanics |
| AD-017 | unchanged: the Knife's isolated Undo/Redo holds for every source through `KnifeSession` |
| AD-019 | unchanged: `PointerGestures` stays the click / drag resolver in front of the slot |
| AD-021 L-1 | the mode-4 refusal moves to stage 4, same texts |
| AD-025 §4.4, §15 | the command-level layer gate and the view refusal become stage 3; the operation-level gate (method names, `C` contexts) stays inside the operations |
| INPUT_COMMAND_TOOL_CONTRACT §5 rule 4 | realised: "Tools own temporary interactive/modal state" — the sessions |
| SOURCE_ARCHITECTURE §2, §5 | updated at M8: the Application section describes slot, `can_run` and controllers; §5's open "Command-System und dessen genaue Grenzen" is answered for the app |
| GUI_STAGE1_HUD §3 | its seam "ein öffentlicher Einstieg mit denselben Gates wie die Taste" is the gated `dispatch_command`; Q4 (click ownership) stays open |

**No decided AD changes in substance.** One AD-013 H2 statement changes; it is an API contract, not user-visible
behaviour (V8).

## 6. Equivalence strategy

**E1 — Golden corpus, recorded on the baseline before the first `src/` change (M0).**

- *Driver* `tests/interaction_trace.py`: only public entry points (`key_press/release`,
  `pointer_press/drag/release/motion/scroll/leave`, `set_shift/ctrl/alt_held`, `flush_hover`, `update_viewport`) and
  the public calls hosts use (`load_scene`, `add_primitive`, `mirror_copy`, `create_morph_target`, `set_light` …).
  Never `dispatch_command` (its gating changes on purpose) and no private member.
- *Inputs:* every input bound in `config/keymap.json` or the code defaults, all contexts except `window` (the
  window's own keys). Hold keys are pressed, held over several events and released, as a hand does; clicks and drags
  land on projected vertices, edge midpoints, face centres and empty space; modifiers go down and up; focus loss
  releases them all.
- *Scenes:* cube; subd cube with symmetry; a basemesh with a seam (Knife across faces, Re-Symmetrize); two objects
  and a Reference (mode `4`, a mirror pair); a mesh with two morph targets (editing view); hidden and masked parts.
- *Observation after every event:* the return value; status text and serial; `interaction_owner`; the HUD state
  (`hud.hud_state`); selection (mode, ids, hover); per object the `export_state()` digest, transform, material and
  state; history length and can-undo/redo; the camera; `knife_render_data`, `selection_box/lasso/through`,
  `gizmo_items()`, `pivot_marker_items()`; and the headless viewport's render buffers after `update_viewport(0)`, so a
  lost viewport notification shows as a stale buffer.
- *Deterministic:* fixed seeds, an injected Knife clock, CPU picking. Prototype (2026-10-29): the same seed gives the
  same digests on cube, subd cube and the 928-vertex basemesh; 0.25–0.34 ms per event on the small meshes, 9 ms on
  the basemesh.
- *Stored:* per sequence the seed, the driver's source hash and one 12-hex digest per event
  (`tests/fixtures/interaction_traces/`); scripted sequences store the full observation for a readable diff.
  Default run ≈ 60 000 events on the small meshes and ≈ 3 000 on the basemesh; budget about one minute, measured at
  M0 (the prototype did not yet digest the render buffers).
- *Scripted sequences:* Manu's test points as fixed scenarios — Knife (cut, pen lift, double-click, in-session Undo,
  commit and cancel, symmetric session), W/E/R held with a constraint, Alt orbit, Shift fine and Ctrl snap, Box /
  Paint / Lasso (also through), gizmo click and drag, Working Pivot (place, tap, Esc), the morph view (Tab, W in the
  view, N drag, Undo), Undo/Redo chains, object gestures with a mirror pair, Re-Symmetrize — and V1–V7.
- *Rule:* from M0 to M8 the corpus is never re-recorded to make a step pass. A divergence is a bug of that step. Only
  a bug in the driver itself justifies re-recording, and then from a worktree of the baseline commit.
- *Lifecycle (C1):* the randomised digest corpus is a **migration oracle, not a permanent test**: it encodes every
  binding and every status text, so any intended keymap or behaviour change after the migration (UX project,
  Phase 6) would break it. At M8 the randomised digest fixtures and the random generator are removed. The scripted
  sequences (V1–V7 and the test-point scenarios above) stay as readable regression tests: named steps with explicit
  assertions on the observations that matter to each scenario, so an intended change later edits a readable
  expectation instead of re-recording digests.

**E2 — Differential deep run per step.** The same driver runs in two subprocesses, one on a `git worktree` of
`dfd6e5d`, one on the working tree, with seeds beyond the corpus (≥ 200 000 events on the small meshes and ≥ 20 000
on the basemesh per step, under ten minutes); the first divergence is printed with both observations. A migration
tool only: not committed beyond the driver it shares with E1, and removed with the random generator at M8 (C1).

**E3 — Suites.** Targeted tests while moving a cluster; at the end once: `tests/` fully (baseline: 5 449 passed,
125 skipped, 8 min 50 s), the GL tests in their own process, `experiments/morph_lab/tests`, and the Knife oracle — its
trigger files do not move, it runs anyway because the Knife session wiring does.

**E4 — Test access to private state.** The tests read 507 private `Application` members (58 names; 156 of them Knife
state). They are rewritten in the commit that moves their owner — to the public property where one exists
(`knife_active`), else to the new owner; assertions stay unchanged, so the diff of a test file is accessor paths only.
No compatibility aliases on `Application`.

**E5 — Structure checks (tests).** (i) `Application.__init__` sets no field outside the listed non-modal set (§3.1);
(ii) `controllers/` and `interaction/session.py` import nothing from `mirai.application` and use no underscore member
of `AppServices`; (iii) every command has exactly one handler; (iv) `can_run` is pure — two calls give the same result
and change no observation.

**Not covered by E1/E2:** the GPU picking path (window only; AD-022's own tests), the pyglet adapter (covered by
`tests/test_main_wiring.py`), timing. The routing adds one indirection per event; its cost is measured on Xvfb and
reported (budget: under 5 µs per key or motion event, under 20 µs per frame for the HUD's `can_run` data). No
reference-PC run is needed for a change that adds no work to a hot path; if the measurement exceeds the budget, it is
reported, not guessed.

## 7. Migration order

Each step is one or more commits. After each: E1 equal, E2 equal, the moved cluster's targeted tests green.

**Execution (C3):** in three fresh sessions with this AD as the handoff — **M0–M2**, **M3–M5**, **M6–M8** —
Claude Opus 5.5, effort **high**. Each session starts from the branch state the previous one pushed and reads §3, §6
and its rows below; a session ends with its steps green (E1, E2, targeted tests) and pushed.

| Step | Content | Why here |
|---|---|---|
| M0 | Driver, scripted sequences and the golden corpus, recorded on the baseline; no `src/` change | the oracle must exist before anything moves |
| M1 | `interaction/session.py` (slot, protocol, routing) and `controllers/services.py`; first user: Re-Symmetrize preview + SymmetryController (cycle, display, reports) | the smallest exclusive session proves the grab path |
| M2 | `can_run` with stages 1–7 at every call site; `dispatch_command` gated, internal calls ungated; HUD availability data; the AD-013 H2 note | every later session then plugs into one check |
| M3 | KnifeController + `KnifeSession` | self-contained, the largest block of test accesses |
| M4 | the four hold keys; MorphController (lifecycle, editing view, view policy) | the hold rank (V1, V4) is pinned before the gestures move |
| M5 | `DragSelect`, `GizmoPress`, `SwallowedGesture` | the pointer sessions the gestures hand over to |
| M6 | `GestureSession` and its kinds (Move/Rotate/Scale via `ToolManager`, Extrude, Loop / Vertex Slide, Smooth / Relax, Inset / Bevel), the gizmo / Tweak origin, Soft live radius and flow — **one gesture kind at a time, E1 and E2 after each kind** (C3), not only at the end of the step | the biggest step; everything it touches is in place |
| M7 | ObjectController, including the object gesture kind and the stage-4 policy | the object gesture is a gesture kind |
| M8 | command table; E5 checks; SOURCE_ARCHITECTURE; line counts; E3; then the scripted sequences become the permanent regression tests and the randomised digest fixtures and generator are removed (C1) | closes the DoD |

### 7.1 Findings of the steps so far (implementation, not a new decision)

- **M0.** Corpus as §6 E1: 252 random sequences of 250 events (60 000 on the five small scenes, 3 000 on the
  basemesh), hand-like macros on top of single random events (a gesture key held over moves, Knife sessions, the
  preview, drags, held P / L / N / Q, gizmo drags), 18 scripted sequences (V1–V7, the test points). Deterministic
  across `PYTHONHASHSEED` (the SubD provider's cache had to stay out of the digest). The replay takes **2 min 31 s**
  on the 4-core container, over the "about one minute" budget; E2 per step (230 000 events, both trees) about
  ten minutes on 4 workers. E2 by hand: `git worktree add <dir> dfd6e5d`, copy `tests/interaction_trace.py` into it,
  run `python tests/interaction_trace.py digests <scene> 1000 <count> 250` in both trees and compare the lines;
  `... observe <scene> <seed> 250 <index>` prints the observation at the first differing event.
- **Session protocol:** `exclusive: bool` added - True for a session that grabs input (the Knife, the preview); its
  `allows` alone answers `can_run` (stage 1, "alone" taken literally: the preview's display keys run without the
  host gate, as before).
- **Source-dependent `allows`** where today's behaviour differs by source (allowed by `RunContext`): the preview's
  refusal of a drag is silent, of every other source its hint; a drag selection lets the Soft wheel steps through
  (they never waited for it), keys only Cancel, display, look, ortho, session switches and SubD.
- **Stays in the command** (a precondition, not a gate, or behind a silent gate in today's order): the Working Pivot's
  and the drag selection's mode-`4` texts, `viewport is None`, and `_toggle_orientation`'s own begun check (stage 6
  refuses `K` first, so it is never reached from a key).
- **Cost (M2, measured headless on the 4-core container, Python 3.13):** `can_run` 1.0–1.8 µs per key, a slot grab
  0.3–0.8 µs per event (budget 5 µs: met). The HUD's availability data (`HudState.unavailable`, 34 hinted commands,
  computed while the HUD is visible) costs 30–40 µs per frame - **over the 20 µs budget** (≈ 0.2 % of a 60 Hz
  frame). Not optimised: a batched variant would be a second copy of the stage logic; it is the option if the HUD
  ever shows in a profile.
- **Until their sessions move** (M3, M5, M6) the Knife's, the held gestures' and the drag selection's `allows` are
  `Application` tables (`_KNIFE_ALLOWS`, `_GESTURE_REFUSES`, `_DRAG_SELECT_ALLOWS`) read by `can_run`.
- **M3 (Knife).** `controllers/knife.py`: `KnifeController` (begin / end, the mirror-preview variant and the
  double-click clock as its settings, picking and the tool overlay) and `KnifeSession` (exclusive, owner `"knife"`,
  `allows` = `KNIFE_ALLOWS`); `Application` keeps `knife_active`, `knife_render_data` and `knife_clock` /
  `knife_mirror_variant` as delegating properties. The session grabs keys (resolved in `knife`), its own press
  (plain / Shift LMB, the KnifeLift button) with its drags and release, motion, hover, Shift held, leave, the Soft
  wheel steps, every release after the pointer resolver (the session gate) and Undo/Redo arriving through
  `dispatch_command` (a `Command` event after `can_run`, AD-017's isolated history from every source).
- **Event details the Knife needed (implementation, the contract unchanged):** a press, drag or release a session or
  hold key took never reaches the pointer resolver, so it travels as a *raw* event (`Drag(None, ...)`,
  `Release(..., raw=True)`); after the resolver come the resolved ones. A press's answer means: True = taken (no
  resolver), False = handled (no gizmo press, the resolver still gets it - the preview's answer, which M1 returned as
  True through `route`), `PASS` = idle. `Leave` also stands for "no hover point" (a navigation drag clears the hover,
  a re-pick without a cursor). The slot exposes its stages (`claim`, `handle`, `background`) for the entry points
  that keep a gesture branch between them until M6. `AppServices` gains `pick_cache` (the Knife picks with its own
  occlusion tests on the shared cache) and `toggle_ortho` (the session's own ortho key runs the view command
  `Application` owns); the display / Look command groups moved to `interaction/commands.py`.
- **M4 (hold keys, Morph).** `controllers/pointer_tools.py`: `PointerToolsController` with `PivotHold`,
  `LassoHold`, `LightHold` and the Working Pivot itself (a sticky setting the pivot hold writes);
  `controllers/morph.py`: `MorphController` (lifecycle, current target and weight, A/B, the editing view and its
  history translation, `view_refusal` for `can_run` stage 3) with `MorphWeightHold`; `Application.morph` (the mix
  display) is the controller's. The hold objects live one per app (a second press of a key bound to the same
  command keeps their state, as before) and sit in the slot while held; the pivot also while its LMB placement
  runs past the key release (until that LMB release). Precedence = the slot's rank: the pivot claims press, raw
  drag and release, Cancel and the hover before the session; the light drag, then the Morph weight take the motion
  after it (V4, V5). `key_release` asks the holds in the order it always did (Lasso, Pivot, Morph weight, Light -
  it matters only when two holds share a key value), not in rank order. `AppServices` gains `set_light` (the light
  drag turns the key light; the Worklight stays in `Application`). The editing view's mask / hidden set are dropped
  by `Application` when `close_if_left` reports the closed view.

## 8. Definition of Done (from the handoff) and how each item is checked

| Item | Check |
|---|---|
| No modal state outside the session slot | E5 (i): the field list of `Application.__init__` against §3.1 |
| One `can_run` used by keys, `dispatch_command` and the HUD | grep: no `_*_refuses` left; E5 (iv); tests that call it through each path |
| The named clusters live outside `Application` | `controllers/{knife,morph,objects,symmetry}.py` (plus gestures, pointer tools); E5 (ii) |
| Behaviour equivalence | E1 and E2 equal after every step (in M6 after every gesture kind); E3 green; numbers reported (events, scenes, seeds) |
| Corpus lifecycle (C1) | after M8: the scripted sequences (V1–V7, the test-point scenarios) are readable regression tests in `tests/`; no randomised digest fixture or random generator is left in the repository |
| `SOURCE_ARCHITECTURE.md` reflects the structure | updated at M8 |
| Line counts before / after, model / effort for Phase 6 | in the final report; before (§1): `application.py` 7 713, `main.py` 841, `hud.py` 481, `src/mirai` 30 184 |

## 9. Risks, limits and the points put to the second opinion

**Risks.** A large diff — mitigated by the steps and E1/E2 after each. Exact float equivalence — a step must not
reorder float arithmetic; if that ever proves unavoidable it is reported as a finding, never absorbed by re-recording.
`AppServices` growing into a second `Application` — its member list is fixed in §3.4 and checked by E5 (ii); a new
member needs a reason in the commit.

**Limits.** The accidental orders V1, V3 and V7 (a held P beats a later W or an open preview for LMB and Esc) are
kept, not normalised (Manu, 2026-10-29: "V1, V3, V7 stay as they are"); normalising them would be a behaviour change
and a new decision. The equivalence covers what E1 observes (§6); the GPU picking
path and the pyglet adapter keep their own tests.

**Points put to the Development chat — all decided as chosen (DEVCHAT-001, Manu's go; §12):**

1. Hold keys as a second, ranked list inside the slot (chosen) — or as input state outside the session concept?
2. `dispatch_command` gated (chosen; one AD-013 H2 sentence changes) — or `dispatch_command` ungated and a new gated
   `run_command` for the UI?
3. A `src/mirai/controllers/` package (chosen) — or flat modules next to the existing feature modules?
4. Normalise V1, V3, V7 later (a behaviour change) — or keep them? **Kept** (Manu).
5. AD-013 H2's `CommandGate` and `hover_suspended` have no host writer since 2026-10-24 (V9): keep them as stage 2
   (chosen) — or retire them in a separate decision?
6. The HUD uses `can_run` as data only (chosen) — greying the hints is the UX project's decision.

## 10. Test points for Manu (Deutsch)

Kein Abhak-Test. Normal weiterarbeiten (Knife, W/E/R halten, Box/Lasso, Gizmo, Morph-Ansicht, Undo) und melden, wenn
sich etwas anders anfühlt. Die Gleichheit prüfen die aufgezeichneten Eingabefolgen (§6), nicht du.

## 11. Not in scope

Behaviour, key or binding changes; `config/keymap.json`; any GUI or HUD look; skeleton and skinning; new features;
Core changes; rewriting tool internals (Knife engines, topology operations, SubD, picking); Lab changes beyond keeping
the Morph Lab running.

## 12. Review disposition

Second opinion [DEVCHAT-001](../archive/interaction_layer/reviews/AD-027_REVIEW_DEVCHAT_001.md) (Development chat,
2026-10-29, archived verbatim): **ACCEPT WITH CHANGES**. Manu's go the same day: "Go for AD-027 with C1-C3. V1, V3, V7
stay as they are." The AD is DECIDED with the changes below; nothing beyond them was changed.

| Point | Review | Disposition |
|---|---|---|
| Open points 1–6 (§9) | agrees with the chosen option in each (1: precedence in one place; 2: an ungated public entry is the V8 bug class, GUI and future scripts hit the same gate; 3: keeps interaction code apart from the model modules and makes E5 (ii) checkable; 4: keep V1/V3/V7; 5: retiring `CommandGate` is a separate decision; 6: greying is the UX project's call) | Chosen options stand; §9 marks them decided |
| C1 — corpus lifecycle | the randomised digest corpus is a migration oracle, not a permanent test; after M8 keep the scripted sequences as readable regression tests, remove the randomised digest fixtures; state it in §6 and the DoD | **Adopted:** §6 E1 *Lifecycle*, E2 (removed with the generator), §7 M8, §8 row "Corpus lifecycle" |
| C2 — UI in front of the slot | a grabbing session would swallow clicks on future panels; do not decide panel / viewport pointer ownership; state that a window-level UI hit-test may sit in front of `InteractionSlot.route` and keep the slot API from precluding it | **Adopted:** §3.5 "UI in front of the slot" (the slot knows no window, `Application.pointer_*` stay its only pointer entries, no session assumes it sees every pointer event; the one requirement on a UI layer: drags and the release follow their press); §3.2 routing rule scoped to `Application`. Ownership stays GUI_STAGE1_HUD §5 Q4 |
| C3 — execution | fresh sessions with AD-027 as the handoff, split M0–M2, M3–M5, M6–M8, Opus 5.5 high; in M6 E1/E2 after each gesture kind | **Adopted:** §7 "Execution", M6 row, §8 equivalence row. This replaces the drafting session's suggestion (same session, xhigh) |
