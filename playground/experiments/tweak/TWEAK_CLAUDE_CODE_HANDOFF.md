# Task: Implement Tweak Experiment (Playground)

**Mode:** Production — the research decision on *what* to build is made. Build
it reliably. Do not introduce new interaction ideas while implementing; if you
notice something that seems better mid-build, stop and flag it as a new
Discovery question instead of silently building your version (see
`MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` §M5, "BUILD darf keine neue Erkenntnis
behaupten").

## Context — read first

1. `docs/design/artist_playground/EXPERIMENT_HOST.md` — Experiment/Variant/
   ExperimentSlot conventions.
2. `playground/experiments/tweak/decision.md` — the full spec for this task.
   This is the authoritative source for what to build; do not deviate from it
   without flagging why.
3. `experiments/mirai_bastel_viewport_V1/viewport/app.py` — existing, working
   prior art for persistent tool-mode + Tweak-fallback semantics. **Reuse or
   adapt this, do not reinvent it.** Specifically:
   - `_activate_tool(tool_cls)` — persistent tool activation
   - `_start_move_interaction()` + `self._tweak_tool` flag — the
     borrowed-vs-persistent-tool fallback logic
   - `_handle_cancel_command()` — differentiated ESC behaviour
4. `playground/experiments/transform/variant_move.py` (and sibling files) —
   the existing pattern for how a Playground Experiment variant is structured.
   Follow this shape for the new Tweak variants.
5. `playground/window.py` — current live wiring: `on_key_press`/
   `on_key_release`/`on_mouse_press`/`on_mouse_drag`/`on_mouse_release`, the
   `_transform_key_down`/`_transform_started` state machine, and
   `_drag_moved`/`CLICK_THRESHOLD` (the existing click-vs-drag disambiguation
   you'll reuse for the Press-vs-Tweak disambiguation in Variant 1).

## Scope

Implement all four Tweak variants described in `playground/experiments/tweak/decision.md`,
plus the shared prerequisite infrastructure. Do **not** run or attempt to
generate a verdict — that decision.md's KEEP/ITERATE/REJECT fields stay empty.
Your job ends at "all four variants are playable," not at "a winner is chosen."

### Shared prerequisite (build once, used by Variants 2 and 4)

A persistent "currently selected transform mode" concept, adapted from the V1
pattern above:

- Press `X`/`R`/`S` toggles a persistent Move/Rotate/Scale mode on/off (not a
  held state) — replacing the current `active_tool = None` on every release.
- The mode must survive across separate drag gestures (i.e. survive commit)
  until explicitly toggled off or replaced by another mode key.

### Variant 1 — Hold Key, self-deciding gesture

- Key-down → key-up **without** drag in between → mode-toggle (see prerequisite
  above).
- Drag occurs between key-down and key-up (same `CLICK_THRESHOLD` mechanism
  already used for click-vs-drag elsewhere in `window.py`) → the gesture
  becomes Tweak instead: target resolution per the Selection-Fallback rule
  below, transform runs until key-release (commit), ESC cancels.
- Leave the "does the mode-toggle still fire if a Tweak happened" question
  **open and observable** — implement whichever behaviour is simplest to wire
  correctly, and note in a code comment which one you picked and why, so it's
  visible during play-testing rather than silently decided.

### Variant 2 — Silo-style (Ctrl + LMB, releasable)

- `Ctrl`+LMB press, `Ctrl` may be released immediately, LMB held through the
  drag → Tweak using the **currently selected persistent mode** (prerequisite
  above). LMB-release = commit. ESC = cancel.

### Variant 3 — Hold X/R/S + click, early-releasable

- `X`/`R`/`S` held **and** LMB pressed → drag starts Tweak with the
  corresponding transform. The `X`/`R`/`S` key may be released mid-drag
  without cancelling — LMB alone continues to govern the interaction.
  LMB-release = commit. ESC = cancel.

### Variant 4 — Hold Ctrl, no click

- `Ctrl` held + drag (no LMB needed) → Tweak using the currently selected
  persistent mode (same prerequisite as Variant 2). `Ctrl`-release = commit.
  ESC = cancel.

### Selection-Fallback rule (identical across all four variants)

- Selection non-empty → Tweak transforms the **whole selection**, regardless
  of where on screen the gesture starts (no hit-test required).
- Selection empty → the gesture's start point requires a hit-test; the hit
  element becomes a temporary target, transforms during the drag, and is
  deselected again on release/commit.

## Acceptance criteria

- All four variants are registered as a new `"tweak"` family
  (`playground/experiments/tweak/variant_*.py` + `__init__.py`, following the
  existing `selection`/`transform`/`presentation` pattern) and wired into
  `window.py`'s per-family slot registry (`app.register_slot(...)`) alongside
  the existing three.
- The existing three families (selection, presentation, transform) are
  unaffected — do not change their behaviour as a side effect.
- The HUD's `Setting:` line reflects the active Tweak variant alongside the
  other families (reuse `PlaygroundHUD.update_setting()`, do not build a
  second HUD mechanism).
- The Selection-Fallback rule is implemented once and shared by all four
  variants — not duplicated four times.
- Headless-testable logic (target resolution, fallback rule, mode
  persistence) has unit tests under `playground/tests/`, following the
  existing test style (see `playground/tests/test_experiment_slot.py`,
  `test_playground_app.py`). GL/window-dependent behaviour (actual key/mouse
  routing in `window.py`) does not need headless tests if the project's
  existing tests don't cover that layer either — match current practice, do
  not invent a new testing standard for this task.
- `python -m unittest discover -s tests` and `pytest playground/tests/`
  (both from repo root, `PYTHONPATH=.`) still pass afterward — no regressions
  in the existing 387/142 tests (the one pre-existing `test_extrude_tool.py`
  import failure is unrelated and pre-dates this task; don't fix it as part of
  this scope unless trivial).

## Explicit constraints

- `src/core/`, `src/viewport/` — never touch (production, frozen).
- `src/mirai/` — read-only for this task; reuse existing tools
  (`MoveTool`/`RotateTool`/`ScaleTool` via `transformer.py`'s
  `create_tool_for_type`) rather than writing new transform math.
- Do not touch `M`/`Q`/`1`/`2`/`3`/`D`/`Z`/`V` key handlers or their existing
  behaviour.
- Do not route the new Tweak keys through `PlaygroundInputMap` as part of this
  task — the existing X/R/S/Ctrl/ESC handling is hardcoded in `window.py`
  today, and unifying that is explicitly a separate, later concern (see
  `docs/design/artist_playground/DEV_HOST_AUDIT.md` §4, "Keymap conflation" —
  don't bundle it in here).
- Playground code (variant classes, wiring) may be quick-and-dirty. Do not
  spend time on production-grade abstraction — this is Discovery-adjacent
  research code, not a production deliverable (see `decision.md`'s Production
  Migration Notes section, which stays empty until a verdict exists).
- Do not fill in, guess, or pre-populate any `decision.md` field (Verdict,
  Pro/Contra, Fühlt sich an, etc.) — those are the Artist's, written after
  playing, not yours.
- Do not choose a "best" variant or default one to being preferred in the UI
  — all four should be equally reachable (e.g. cycled the same way other
  families cycle, or however you find cleanest — flag your choice, don't
  silently bake in a preference).

## Known open question — flag, don't resolve

Whether "Press X (with a Tweak drag in between) still toggles the persistent
mode afterward" is unresolved by design (see Variant 1 above and
`decision.md`'s open questions). Implement one behaviour, comment clearly
which one and why, and leave it visible for observation — this is exactly the
kind of thing Manuel needs to notice while playing, not something to be
decided during implementation.

## When done

Report back: which files were touched, which behaviour you picked for the
open question above and why, and whether anything in `decision.md` turned out
to be ambiguous or infeasible as written (in which case: stop, describe the
problem, do not silently improvise a fix — this is Discovery territory, not
yours to resolve).
