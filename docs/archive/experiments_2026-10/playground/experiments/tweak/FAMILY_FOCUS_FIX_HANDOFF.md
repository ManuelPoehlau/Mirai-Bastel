# Fix: Decouple Family Focus from Interaction Keys

**Mode:** Production — this is a correction to a specific, diagnosed wiring bug,
not new research. Do not introduce new interaction ideas while fixing this.

## Context — read first

1. `playground/window.py` — current state, specifically:
   - Lines ~166-208: per-family slot registration in `PlaygroundWindow.__init__`
   - Line ~830 (`elif symbol == _key.M:`): the `M`-cycling handler
   - Line ~906-907: `X`/`R`/`S` press handling, `activate_variant("transform", ...)`
     call
   - Lines ~553, 562: `activate_variant("tweak", ...)` calls inside
     `on_mouse_press` (V2/V3 Tweak arming)
2. `playground/app.py` — `PlaygroundApp.activate_variant()`,
   `register_slot()`, `_slots` registry, `_active_experiment`.

## The bug, precisely

`M` cycles variants within `self.app.active_experiment.id` — whichever family
that currently is. Which family that *is* gets set as a side effect of
interaction keys:

- `X`/`R`/`S` press → unconditionally calls
  `app.activate_variant("transform", slot.active_index)`, making `"transform"`
  reachable via `M`.
- Nothing equivalent exists for `"tweak"` — the two `activate_variant("tweak", ...)`
  calls in `on_mouse_press` only fire once the active Tweak variant is already
  `"v2"`/`"v3"`, which itself requires `"tweak"` to already be the focused
  family. Unreachable from a resting state. **Tweak Variants 2–4 are correctly
  implemented and tested but unplayable in the live window.**

This isn't just a missing call to add for `"tweak"` — the underlying design is
wrong. Coupling "which family M cycles" to specific interaction keys doesn't
scale: every new family would need its own key to become reachable, and X/R/S
are interaction triggers (Move/Rotate/Scale/Tweak), not family selectors.

## The fix — decouple family focus from interaction

### 1. New, independent focus state

Add `self.focused_family: str` to `PlaygroundApp` (or `PlaygroundWindow`, your
call on which is the better fit given existing state ownership) — completely
separate from `active_tool`/`active_experiment`'s interaction-triggered
mutations. Default: `"selection"`.

### 2. Dedicated family-switch key: `Tab`

`Tab` cycles `focused_family` through `app.slots.keys()`, in whatever order
the dict currently holds them (insertion order is fine — no need to hardcode
a sequence). This must generalize to however many families are registered,
not assume exactly four.

### 3. `M` cycles the focused family only

Rewrite the `M` handler to read `app.focused_family` instead of
`app.active_experiment.id`. Everything else about `M`'s behavior (the
`transform`-specific state-reset branch, `_update_hud()`) stays as-is, just
re-pointed at the new focus variable.

### 4. Remove the side-effect wiring

- Remove the `activate_variant("transform", slot.active_index)` call from the
  `X`/`R`/`S` handler (line ~906-907). Pressing X/R/S must arm/trigger the
  transform tool as it already does — it must **not** also change which
  family `M` cycles.
- Remove the two `activate_variant("tweak", ...)` calls from `on_mouse_press`
  (lines ~553, 562) for the same reason. Tweak-arming logic stays; the
  family-focus side effect goes.
- After this, `activate_variant(family_id, index)` should only ever be called
  from the `M` handler (to actually switch a variant) and from
  `PlaygroundWindow.__init__` (initial state). No interaction key should call
  it merely to shift focus.

### 5. HUD

If `PlaygroundHUD` displays which family is currently focused (check
`update_setting()` / the `Setting:` line), make sure it reads
`app.focused_family`, not `app.active_experiment.id`, so the display matches
what `M` will actually do.

## Acceptance criteria

- Pressing `Tab` repeatedly cycles through all currently-registered families
  (`selection` → `presentation` → `transform` → `tweak` → back to
  `selection`, in whatever order `app.slots` holds them) without touching any
  active tool, transform state, or Tweak-arming state.
- Pressing `M` cycles variants **within whatever family `Tab` last selected**
  — verify explicitly that this reaches **all four** Tweak variants (not just
  V1), and still correctly cycles Selection/Presentation/Transform as before.
- Pressing `X`/`R`/`S`/`Ctrl` still triggers the correct
  Move/Rotate/Scale/Tweak interaction exactly as before this fix — verify
  against `playground/tests/test_tweak.py`'s existing 22 tests, none of which
  should need behavioral changes (only the family-focus side effect is being
  removed, not the interaction logic itself).
- No hardcoded assumption of "four families" or their names anywhere in the
  new `Tab`-cycling code — it must iterate `app.slots` however many entries
  it has. This is explicitly to support registering more families later
  without touching this code again.
- Existing test suites still pass: `python -m unittest discover -s tests` and
  `pytest playground/tests/` (both `PYTHONPATH=.` from repo root). Add new
  headless tests for `Tab`-cycling and for `M` correctly reaching all four
  Tweak variants — this specific regression (only V1 reachable) should have a
  test that would have caught it.

## Explicit constraints

- Don't touch `src/core/`, `src/viewport/`, `src/mirai/`.
- Don't change what X/R/S/Ctrl actually *do* interactively — only remove
  their family-focus side effect.
- Don't design a full "experiment loader/registry UI" — Manuel has flagged
  that as a real future need once the number of families grows, but that's
  explicitly out of scope for this fix. The only requirement from that future
  direction is: don't hardcode family names or a fixed count anywhere in the
  `Tab` logic, so a loader can add entries to `app.slots` later without this
  code needing to change.
- Don't touch `tweak_decision.md` or any other decision file.

## When done

Report: which key handlers changed, confirmation that all four Tweak variants
are now reachable via `Tab` + `M` (not just asserted — actually trace it), and
whether anything about the existing `_active_experiment`/`active_experiment`
property is now redundant or should be deprecated as a followup (flag it,
don't remove it silently if other code still depends on it — check
`test_playground_app.py`'s `active_experiment`-related tests before touching
that property).
