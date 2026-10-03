# Independent Review — AD-013 Addendum "H2 — experiment input hook in `Application`"

> **Reviewer:** Claude (Opus 5.5, claude.ai, fresh session, no prior chat or plan context)
> **Review ID:** CLAUDE-001
> **Target path:** `docs/archive/symmetry_lab/reviews/AD-013_H2_ADDENDUM_REVIEW_CLAUDE_001.md`
> **Repository state reviewed:** `main` @ `bafae30` (2026-10-03)
> **Subject:** `docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md`, addendum dated 2026-10-03 (lines 425–536)
> **Type / Mode:** Type B (review only) · Discovery · no source, plan or addendum edited
> **Status:** Archived first-pass review — preserved verbatim
>
> This document is intentionally preserved as the original independent review. Do not edit it to
> reflect later decisions. Answers to the findings belong in the addendum's "Review" section.

---

## What was read, what was run

Read: AD-013 (whole file), `INPUT_COMMAND_TOOL_CONTRACT.md` (§3, §5, §8), AD-015, AD-016,
`src/mirai/application.py` (whole input path, Knife session, selection mirror stack),
`src/mirai/interaction/pointer.py`, `src/mirai/interaction/bindings.py`,
`src/mirai/interaction/input.py` (`BindingSet`), `src/mirai/pyglet_input.py`, `src/main.py`,
`AGENTS.md`, `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md`.

Also read, as repository evidence for the Lab side (not a plan):
`experiments/symmetry_lab/lab_bindings.py` (the current Lab context) and
`experiments/symmetry_lab/lab_resymmetrize.py:153-173` (how Re-Symmetrize writes history).
**Not read:** `WP-SYM-LAB-03_REBASE_PLAN.md` (as instructed), AD-SYM-01, AD-SYM-02,
`lab_dispatch.py` beyond a grep for preview keys.

Run:

- Baseline at `bafae30`: `pytest tests` → 1531 passed, 7 skipped, 1 collection error
  (`tests/test_extrude_tool.py`: `ModuleNotFoundError: mirai_bastel_core`, unrelated to H2, environment).
  `tests/test_application*.py` alone: 412 passed, headless, ~7 s.
- Four throwaway probes against the current `Application` (no hook exists yet). They were run and
  deleted; the code is in the appendix so every "VERIFIED (probe)" claim below can be reproduced.
- pyglet 2.1.16 wheel source, for the key-repeat question (the repo pins no pyglet version).

Every claim not checked in code or by a probe is marked **UNVERIFIED**.

---

## Verdict

**ACCEPT WITH CHANGES — two blockers must be resolved before the addendum can move to DECIDED.**

The direction is right: one interaction authority (`Application`) instead of a second Lab
dispatcher, the rejected alternatives are mostly well argued (B's click-vs-drag argument is correct,
see pointer.py:8-13 and bindings.py:143-144), and the three call-site line references are current.

But as written, the rules do not deliver need 3 (the modal preview) and do not keep Undo correct once
the Lab mutates the mesh:

- **F1 (blocker):** H2-R2 makes the hook back off during *any* Application pointer gesture. Navigation
  is explicitly allowed during the preview, and `Application.key_press` has no gate during pointer
  gestures — so Ctrl+Z, W/E/R and 1/2/3 pressed mid-orbit run under the open preview.
- **F2 (blocker):** Lab mutations (Re-Symmetrize pushes history directly) bypass `Application`'s
  selection mirror stack and pick cache. H2-R4 forbids the private calls that would fix this, and no
  public API is named. The "undo as the app, drift impossible by construction" consequence is not
  true for Lab commands.

I also think a smaller, data-only mechanism meets all three stated needs with fewer rules (F9).

---

## Q1 — Do H2-R1..R6 uphold I1, I3, I4, I6?

| Invariant | Rule(s) | Assessment |
|---|---|---|
| **I1** one capability home | R4 | Upheld for gestures, arming, constraints, hover, picking. **Weak**: (a) R4 allows any public call, including ones that start or alter app interactions (F5); (b) Lab-owned mutations cannot reach Application's undo bookkeeping without private access (F2), so the Lab will need its own undo patch-ups — the exact drift the addendum cites as motivation. |
| **I3** one authority owns start and end | R2 | Upheld for transform and Knife (the hook never sees Knife clicks, application.py:1321-1329, and is told to leave armed/running transforms alone). **Broken** for the hook-owned preview by the pointer-gesture clause (F1). Back-off predicate not named (F4). |
| **I4** one binding authority | R1 (+ R2 for precedence) | Meaning comes from one `BindingSet` (`app.bindings`, application.py:259) — upheld. But there are now two *gate* layers in series (hook refusals, then Application's session gates at :1011-1028) whose precedence is defined only by branch order — AD-016 Problem 4 names exactly this failure mode. R2 states half of the precedence; F1 shows the half it states is wrong for navigation. Silent shadowing of user GLOBAL bindings is possible (F15). |
| **I6** overrides visible | R1 ("listed at start-up"), R3 | Binding entries visible. **Weak**: refusals (W/E/R/C refused in BLOCK, C refused under symmetry) deviate from the Artist language but are visible only when triggered, not listed (F8). The existing Lab context contains entries that become inert or harmful under H2 and would still be printed at start-up (F6). |

R5 and R6 are governance rules for I7 and I5 respectively; R5 is sound (F10/Q5), R6 is not testable (F14).

---

## Findings

### F1 — BLOCKER — R2 lets app commands through during navigation inside the preview

**Rule:** R2: "An interaction `Application` starts (armed or running transform, Knife session,
**pointer gesture**) is never ended, altered or stolen by the hook. While one runs, the hook consumes
nothing except its own commands."
**Need 3:** "While [the preview] is open, navigation keeps working, but select clicks, W/E/R, C,
Shift+S and Undo/Redo are ignored."

**Evidence:** `key_press` (application.py:993-1029) never checks `self.pointer.active`. Keys are fully
live during an orbit/pan gesture. VERIFIED (probe P1): with an Alt+LMB orbit past the threshold,
`key_press(Ctrl+Z)` returns True and undoes; `key_press(W)` returns True and arms Move.

**Breaking sequence:** M (preview opens) → Alt+LMB press, drag 10 px (orbit, `pointer.active` True)
→ Ctrl+Z. R2 obliges the hook to pass Ctrl+Z through → `Application._undo_redo` runs → the mesh
changes under the open preview. Variant: … → W during the orbit → Move arms → release LMB, move the
mouse → `pointer_motion`: preview wants hover paused, but R2 now forbids consuming (armed transform)
→ a Move runs with the preview open.

**Change:** Remove "pointer gesture" from R2's list. Define precedence explicitly:
"Keys and clicks are gated by the owner of the running *key-owning* interaction. Key-owning
interactions are: armed/running transform and Knife session (Application), the preview (hook).
Camera gestures own no keys (Application does not gate keys during them, application.py:993-1029)."
Add the sequence above as a required test (Q4, R2-c).

### F2 — BLOCKER — Lab mutations desync Undo's selection mirror and the pick cache

**Evidence:**
- Application keeps a selection mirror stack paired 1:1 with *its own* `history.push()` calls
  (application.py:299-317, :1183-1218, :1240-1248). The comment says those are "currently the only callers".
- The Lab's Re-Symmetrize pushes `scene.history` directly (lab_resymmetrize.py:166-172).
- `_record_selection_history` (:1240) and `_pick_cache` / `_notify_topology_changed` (:244, :553) are
  private; R4 forbids private members. No public "external mutation happened" entry exists.
- VERIFIED (probe P3): select A → W-move → select B → external `history.push` → Ctrl+Z. History undoes
  the external step, but the mirror pops the *Move's* entry and restores selection `{A}` instead of `{B}`.
  The fallback at :1196-1198 only covers an *empty* mirror stack, not a mis-paired one.
- Pick cache: every mutation must invalidate it explicitly (comment :237-243). After a Lab mutation it
  stays stale until the next camera change → hover/click pick old positions. UNVERIFIED by probe
  (follows from the code comment and `_transform_step` :1123).

**Why it matters for H2:** the addendum's Consequences claim the Lab runs on the same undo as the app
and drift becomes "impossible by construction". It is still possible exactly where the addendum cites
drift today ("Undo clears instead of restoring the selection", UNVERIFIED as a Lab claim).

**Change:** The addendum must name one public Application entry for externally produced history
entries, e.g. `app.commit_external(command, description)` that pushes, records the mirror entry,
invalidates the pick cache and notifies the viewport — or must forbid the hook from pushing history at
all (and then say where Re-Symmetrize commits). Add the probe P3 sequence as a required test.

### F3 — SHOULD — Pausing hover by consuming `pointer_motion` does not pause hover

**Evidence:**
- `_refresh_hover` is called from paths the hook never sees; the relevant one during a preview is zoom:
  `pointer_scroll` → `_refresh_hover` (:1340, :1364-1377). VERIFIED (probe P2): with hover cleared,
  one wheel step brings it back with no motion event.
- If the hook is consulted before `self._cursor = (x, y)` (:1353) — the table says only "before hover
  update or transform step" — `_cursor` goes stale while the hook consumes motion, and the zoom re-pick
  then uses an old position. If it is consulted after :1353, the zoom leak remains.
- The motion site also carries risk: a hook that consumes motion while a transform is armed freezes
  the transform (R2 forbids it, but only by rule).

**Change:** Drop the `pointer_motion` call site. Give Application one public flag,
e.g. `hover_suspended: bool`, checked in `_update_hover` (:1388) so every hover path (motion, zoom,
refresh after undo) honours it, and clear `selection.hovered` when it is set. Application keeps
owning hover (I3). If the Lab needs the cursor for its own overlay, it can read it after the event
from the window — that is observation, not pre-emption. Not covered by this: a Lab that wants to
*replace* hover picking with its own semantics (not a stated need).

### F4 — SHOULD — R2's back-off condition is not defined; AD-015 failed exactly here

**Evidence:** AD-015 Addendum: the Tweak back-off read `app.active_tool`, which the competing path
never set, so the condition was "vacuously always true". AD-015 Costs: "Both sides must agree on what
'active' means." Application's state is spread over `transform_command` (:968), `knife_active` (:615),
`pointer.active` (pointer.py:79-81), and private `_knife_gesture` (:332).

**Change:** Name the predicate in R2. Better: Application exposes one read-only property
(e.g. `interaction_owner -> None | "transform" | "knife"`) and a test asserts it is non-None in every
state where Application's own gates (:1011, :1017, :1023, :997) apply.

### F5 — SHOULD — R4 permits public calls that start or alter app interactions

**Evidence:** VERIFIED (probe P4): `app.dispatch_command(commands.MOVE)` returns True and activates a
ToolManager tool, but `transform_command` stays None, so neither Esc (`_cancel` :1148) nor a key
release (:1036) ends it — an interaction started by the hook that only the hook could end, with no
contract (I3, § Activation and Termination). `dispatch_command(UNDO)` and `select_at` (:1446) are
public too and bypass every gate. The current Lab already calls `dispatch_command` and its own
`select_at` (lab_dispatch.py:377, :555, :670 — grep only).

**Change:** Turn R4 into an allow-list: read-only properties, the status setter (H4), the external
commit entry from F2, and nothing that dispatches app commands. Test: run the Lab test suite with
`Application.dispatch_command` and `select_at` patched to raise when called from the hook module.

### F6 — SHOULD — The existing Lab context is incompatible with H2; R1 does not fix the entry set

**Evidence** (`lab_bindings.py:67-108`, run.py prints them at start-up, run.py:62-63):
- `C → KNIFE` in `symmetry_lab`. The hook resolves its own context first (input.py:212), so C becomes a
  *Lab* command and the hook never sees `CONNECT` — need 2 ("refusing C") cannot work while this
  entry exists.
- `mouse Alt+LMB → ORBIT`, `mouse Shift+LMB → PAN`, `mouse RIGHT → None`, `mouse MIDDLE → PAN`.
  `PointerGestures` is built with `context=None` (application.py:266, pointer.py:94-95), so Application
  never resolves pointer input in the Lab context. Under H2 these entries are inert, yet would still be
  listed at start-up as active overrides (I6 inverted: a visible override that does not apply). MMB pan
  silently disappears from the Lab (GLOBAL leaves MMB unbound, bindings.py:139).

**Change:** R1 should state the exact entry set (Shift+S, M, Shift+B, keys only) and that pointer
overrides are not possible under H2. Test: the Lab context contains exactly those three key entries.

### F7 — SHOULD — The preview gate is a block-list with gaps; make it an allow-list

**Evidence:** Need 3 lists what is ignored (select clicks, W/E/R, C, Shift+S, Undo/Redo). Not listed and
therefore passed to Application: 1/2/3 (clear selection and hover, :477-479), X/Y/Z and Shift+X/Y/Z
(sticky constraint, :1093-1101), D/Shift+D (display — harmless), Shift+B (gate mode, a Lab command).
Whether a selection change invalidates the Re-Symmetrize preview is UNVERIFIED.

**Change:** Define the preview as an allow-list: camera navigation (pointer, wheel), display commands,
and the preview's own keys (M, Esc). Everything else that resolves to a command is refused visibly.
Any future app command is then refused by default instead of leaking.

### F8 — SHOULD — Refusals are overrides and must be listed like bindings (I6)

**Evidence:** In BLOCK mode W no longer means Move. That deviates from the Artist language just like a
rebinding. R1 lists only context entries; R3 makes refusals visible only when they fire.

**Change:** The hook (or the F9 table) exposes its refusal rules as data, and the start-up listing prints
them next to the binding entries ("BLOCK: Move, Rotate, Scale, Connect refused").

### F9 — SHOULD (Q2) — A smaller, data-only mechanism meets all three needs

Proposal "G" — no callback inside Application:

1. `Application.refusals: dict[str, str]` — app command → status text. Checked in `key_press` right
   after `command = self.bindings.command_for(input)` (:999), and in `_execute_click` (:1440) for click
   commands. Application posts the text through its own `_set_status`.
2. `Application.hover_suspended: bool` (F3).
3. Lab commands at window level: `cmd = app.bindings.command_for(inp, "symmetry_lab")`; if `cmd` is a
   Lab command the Lab handles it (refusing it visibly while `app.interaction_owner` is set, F4),
   otherwise `app.key_press(inp)`. Same `BindingSet` (I4). The addendum already concedes that a
   window-level step "is workable for keys only" — keys are all this step handles.

The Lab writes one dict and one bool when its state changes (symmetry on/off, BLOCK on/off, preview
open/closed).

What G gets for free: precedence is Application's (the check sits after Knife routing at :997 and
applies during camera gestures, so F1 cannot occur); R3 holds by construction; F8 holds by
printing the dict; R2/R4/R6 shrink to "one writer of the table"; tests read data, not hook
behaviour.

What G does **not** cover: refusals that depend on more than the command identity (click position,
part of the selection, which side of the mirror plane); refusing input *inside* a Knife session; any
Lab reaction that must run *instead of* an Application command with the original event. None of
these is a stated need today. F2 is needed with either mechanism.

### F10 — NIT — R3 depends on a status setter that does not exist yet

**Evidence:** `_set_status` is private (:1278-1280). Writing `app.status_message` directly skips
`status_serial`, so the console loop (main.py:234-236) misses a repeated identical message.
**Change:** Name H4 as a precondition in the addendum's Decision, not only in the plan.

### F11 — NIT — The key-repeat cost is probably moot, and not hook-specific

**Evidence:** pyglet 2.1.16 does not dispatch `on_key_press` for auto-repeat on Win32
(`window/win32/__init__.py:942`, `if not repeat`), Cocoa (`pyglet_view.py:218`, `isARepeat`) or X11
(`window/xlib/__init__.py:1222`, plus the repeat heuristic above it). The repo pins no pyglet version
(UNVERIFIED which version runs on the Artist's machine). If repeats did arrive, Application itself would
misbehave first: X/Y/Z toggle on every press (:1099).
**Change:** Replace the cost line with "key repeat is handled (suppressed) by the pyglet adapter for
Application and hook alike", or add an adapter test if a version is pinned.

### F12 — NIT — Focus loss

**Evidence:** `on_deactivate` resets only Shift (main.py:180-185). W held + Alt-Tab → the release never
arrives → the transform stays armed (pre-existing). Under H2, R2 then refuses all Lab commands until W
is pressed and released again. A preview survives focus loss (acceptable; hook-owned).
`Application.shutdown` ends a Knife session (:1496-1500) but knows nothing about the preview.
**Change:** Mention the stuck-armed case in the addendum; state that the preview's lifetime ends with
the Lab window.

### F13 — NIT — Return-value contract for consumed events

Application's own gates return False for ignored input (:1011-1012, :1017-1018). Say whether a hook
refusal returns False ("nothing happened") and a hook-executed command True. Tests assert return
values throughout `tests/test_application_*`.

### F14 — NIT — R4 and R6 are only partly testable

R4 is testable statically (see Q4) and behaviourally only through F5's patching. R6 is a governance
rule; a test can assert the attribute is not a list, which proves nothing. Say so in the addendum
instead of "each is testable".

### F15 — NIT — Lab context silently shadows user GLOBAL bindings

`"symmetry_lab"` is not in `_VALID_CONTEXTS` (input.py:60), so keymap.json cannot address it, and the
own-context lookup (input.py:212) wins over any user GLOBAL entry for Shift+S, M or Shift+B.
**Change:** At start-up, assert each Lab input resolves to None in GLOBAL (user and default layers) and
fail loudly otherwise. VERIFIED that all three are free in the defaults (bindings.py:96-147).

---

## Q3 — Call sites

| Entry point | H2 | Assessment |
|---|---|---|
| `key_press` (:993) | hook first, before Knife routing | Needed. Before-Knife placement is harmless only because R2 forbids consuming app commands in a Knife session; during a session the hook resolves `e` as Rotate (GLOBAL) while Application resolves it as KnifeLift (KNIFE ctx, bindings.py:131) — R2 must be checked first (test R2-b). |
| `key_release` (:1031) | none | Correct. A refused W press leaves `_transform_key` None, so the release is a no-op (:1036). No Lab command has release semantics. |
| `_execute_click` (:1440) | hook | Correct and sufficient: select is click-only (bindings.py:140-143), nothing is bound to a bare LMB drag, over-threshold releases yield no click (pointer.py:131-134). Knife clicks never reach it (:1321-1329). |
| `pointer_press` / `pointer_drag` | none | Correct for need 3 (navigation allowed). Consequence: no pointer overrides possible (F6). |
| `pointer_motion` (:1345) | hook | Superfluous and insufficient — replace with a hover flag (F3). |
| `pointer_scroll` (:1332) | none | Correct for navigation, but leaks hover (F3). |
| `pointer_leave`, `set_shift_held` | none | Fine (`set_shift_held` only drives the Knife hover, :834). |
| `dispatch_command`, `select_at` | none | Public bypasses of every gate; must be off-limits to the hook (F5). |
| key repeat | — | See F11. |
| focus loss | — | See F12. |

---

## Q4 — Tests per rule (headless, through `Application`'s public entry points)

Fixture as in `tests/test_application_pointer.py:34-40` (`init_scene("cube")`, viewport size), plus a
minimal test hook implementing the three methods.

- **R1:** (a) Lab context has exactly {key Shift+S, key M, key Shift+B}; (b) each resolves to None in
  GLOBAL; (c) the hook holds `app.bindings` by identity and constructing the Lab creates no further
  `BindingSet` (patch `BindingSet.__init__` with a counter); (d) the start-up listing function returns
  every entry and every refusal rule (F8).
- **R2:** (a) arm W, press M → refused with status, `transform_command == MOVE`, release W commits one
  history entry; (b) start a Knife session (C with empty selection), press Shift+S → refused,
  `knife_active` True, then E → pen lifted (`knife_render_data.start_point is None`); (c) **F1 sequence**:
  preview open, Alt+LMB drag 10 px, Ctrl+Z → history unchanged; W → `transform_command is None`.
  Under the current R2 wording (c) fails by design.
- **R3:** for every (Lab state × refused command) pair: `status_serial` increments and
  `status_message` is non-empty after the event. Parametrised.
- **R4:** static: AST-scan the hook module for attribute access with a leading underscore on
  Application objects, and for imports of `PointerGestures`, `ToolManager`, `pick_component`.
  Behavioural: F5's patching. F2's probe sequence P3 with the Lab's commit path.
- **R5:** (a) `Application().input_hook is None`; (b) AST/grep guard that `src/main.py` never assigns
  it; (c) **pass-through run**: re-run every `tests/test_application_*` with a hook installed whose
  methods always return False — proves "False = proceeds exactly as without a hook" directly, not only
  for the None case.
- **R6:** not meaningfully testable (F14).

---

## Q5 — `src/main.py` with the hook `None`; line references

Line references checked at `bafae30`: `key_press` `application.py:993` ✓, Knife routing at :997-998 ✓,
`_execute_click` `:1440` ✓, `pointer_motion` `:1345` ✓. None are stale.

Risk to `src/main.py` with `None`: low. main.py calls only the public entry points
(main.py:160-215) and ignores their return values; it never touches `_execute_click` directly.
Three `if self.input_hook is not None and …` guards are inert when the attribute is None. The only
placement risk is behavioural and applies to the Lab, not to main.py: where the motion check sits
relative to `self._cursor = (x, y)` (:1353), see F3. R5's guard test plus the pass-through run (Q4, R5-c)
cover the rest.
Baseline for "existing suites unchanged": 1531 passed / 7 skipped / 1 unrelated collection error;
`tests/test_application*.py` 412 passed.

---

## Appendix — probe code (run against `bafae30`, then deleted)

Placed temporarily as `tests/_tmp_h2_probe_test.py`; all four passed.

```python
import tests._bootstrap  # noqa: F401
from core.operations.topology import MeshStateCommand
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.interaction import commands
from mirai.viewport.picking import pick_nearest_vertex

W, H = 800, 600
def key(v, *m): return Input("key", v, frozenset(m))
def mouse(v, *m): return Input("mouse", v, frozenset(m))

def mk():
    app = Application(); app.init_scene("cube"); app.frame_scene(); app.set_viewport_size(W, H); return app

def targets(app):
    out = []
    for vid in sorted(app.scene.mesh.all_vertex_ids()):
        sx, sy = app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), W, H)
        if pick_nearest_vertex(app.camera, app.scene.mesh, sx, sy, W, H, occlusion=True) == vid:
            out.append((vid, sx, sy))
    return out

def click(app, x, y, *m):
    app.pointer_press(mouse("LEFT", *m), x, y); return app.pointer_release("LEFT", x, y)

def test_P1_keys_stay_live_during_an_orbit_gesture():
    app = mk()
    (a, ax, ay), *_ = targets(app)
    click(app, ax, ay)
    app.key_press(key("w")); app.pointer_motion(ax + 5, ay + 5, 5, 5); app.key_release(key("w"))
    assert app.history.can_undo()
    app.pointer_press(mouse("LEFT", "alt"), ax, ay)
    app.pointer_drag(10, 0, ax + 10, ay)
    assert app.pointer.active
    assert app.key_press(key("z", "ctrl")) is True      # Undo runs mid-orbit
    assert not app.history.can_undo()
    assert app.key_press(key("w")) is True              # Move arms mid-orbit
    assert app.transform_command == commands.MOVE

def test_P2_zoom_brings_hover_back_without_any_motion_event():
    app = mk()
    app.key_press(key("3"))                       # Face mode: the face under the centre survives a zoom step
    app.pointer_motion(W / 2, H / 2)
    assert app.selection.hovered is not None
    app._set_hovered(None)            # stands in for "hover paused": the hook ate the motion
    app.pointer_scroll(Input("wheel", "UP"))
    assert app.selection.hovered is not None

def test_P3_history_push_outside_application_desyncs_the_selection_mirror():
    app = mk()
    (a, ax, ay), (b, bx, by), *_ = targets(app)
    click(app, ax, ay)
    app.key_press(key("w")); app.pointer_motion(ax + 5, ay + 5, 5, 5); app.key_release(key("w"))
    click(app, bx, by)
    assert app.selection.vertices == {b}
    mesh = app.scene.mesh
    before = mesh.export_state()
    mesh.set_vertex_position(b, tuple(c + 0.1 for c in mesh.vertex_position(b)))
    app.scene.history.push(MeshStateCommand(mesh=mesh, before_state=before,
                                            after_state=mesh.export_state(), description="lab"))
    app.key_press(key("z", "ctrl"))  # undoes the Lab push ...
    assert app.selection.vertices == {a}   # ... but restores the Move's 'before' selection, not {b}

def test_P4_tool_command_via_dispatch_command_activates_a_tool_application_does_not_track():
    app = mk()
    assert app.dispatch_command(commands.MOVE) is True
    assert app.tool_manager.active_tool is not None
    assert app.transform_command is None   # no _transform_key: no key_release / Esc path ends it
    assert app.key_press(key("ESCAPE")) is False
    assert app.tool_manager.active_tool is not None
```
