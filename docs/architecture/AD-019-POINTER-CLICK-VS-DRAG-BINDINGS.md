# AD-019 — Pointer Click vs. Drag in the Bindings

**Status:** DECIDED (engineering, 2026-09-26) — WP-06 Stage B, Slice B2.

**Basis:** Artist decisions A6 (navigation per Artist Input Truth: Orbit =
Alt+LMB drag, Pan = Alt+Shift+LMB drag, Zoom = wheel) and A7 (selection =
Playground "Modifier" variant, AP-03: LMB replace, Shift add, Ctrl remove,
Alt toggle), Manu 2026-09-26. `INPUT_COMMAND_TOOL_CONTRACT.md` (Input →
Command → Tool, keymap schema), `AD-013` (Truth rules, I4 one binding
authority), `WP-06_STAGE_B_KICKOFF.md` §6.

This is an engineering decision about *how* the interaction layer expresses
the Artist's bindings. It does not decide any UX question and claims no
Artist validation.

---

## 1. Problem

Stage A deliberately kept continuous drags out of the command system:
`src/main.py` read raw pyglet drag deltas and called `OrbitCamera.orbit()`/
`.pan()` directly, and routing drags through `BindingSet` was left as an
open design question.

A6 + A7 now put two meanings on one physical input: **Alt+LMB drag = Orbit**,
**Alt+LMB click = SelectToggle**. `BindingSet` maps exactly one command per
`(context, Input)`, and `Input("mouse", "LEFT", {alt})` is the same object
for both gestures — one binding per Input cannot express this.

## 2. Alternatives

- **(a) New Input kind `drag`; `mouse` means *click*; the gesture is resolved
  after press — CHOSEN.** `drag LEFT {alt} → Orbit` and
  `mouse LEFT {alt} → SelectToggle` are two ordinary bindings. A window-free
  resolver (`mirai.interaction.pointer.PointerGestures`) looks both up at
  press and decides from movement: only one bound → no ambiguity; both bound →
  undecided until movement reaches the threshold (drag, accumulated delta
  replayed) or the button is released below it (click).
- **(b) Hard-code click/drag in `main.py`, as the Playground does** —
  rejected: not exchangeable via `keymap.json`, a second input authority next
  to `BindingSet` (AD-013 I4), and a fat entry point (kickoff §6: thin
  `main.py`).
- **(c) Combined command strings (`"Orbit|SelectToggle"`)** — rejected: hides
  meaning inside a string, breaks the command vocabulary (a command is one
  named user action, contract §1).
- **(d) Symmetry-Lab press resolution (one command per press, click only as a
  special case of that command)** — rejected: cannot express A7's Alt-click
  toggle next to Alt-drag orbit.

## 3. Decision

- Keymap schema: `input.kind` gains `"drag"`. `"mouse"` = click (press +
  release with movement below the threshold); `"drag"` = press + movement ≥
  threshold. `"key"`/`"wheel"` unchanged. `schemaVersion` stays `1` (additive).
- Threshold: **5.0 px, Manhattan** (sum of `|dx| + |dy|`), the same measure as
  the Playground (`playground/selector.py::CLICK_THRESHOLD`).
- Resolution per press (button + modifiers held at press):
  - only `drag` bound → drag starts immediately, no dead zone;
  - only `mouse` bound → click fires on release below threshold, otherwise
    the gesture is discarded (no box select);
  - both bound → undecided until threshold (→ drag, replaying the accumulated
    delta so no motion is lost) or release below threshold (→ click);
  - nothing bound → swallowed.
- The gesture is fixed at press: modifier changes mid-gesture are ignored;
  presses of other buttons while a gesture runs are ignored; only the release
  of the gesture's own button ends it.
- Modifier matching is exact (existing `BindingSet` semantics).
- `Application` executes the resolved commands window-free; `main.py` only
  translates pyglet events.

## 4. Consequences

- Keymap schema gains `drag` (`INPUT_COMMAND_TOOL_CONTRACT.md` §8.1).
- Exact-modifier matching, accepted: unlike the Playground's bitmask
  priority, e.g. Ctrl+Shift+click is unbound and selects nothing.
- A click bound together with a drag waits for release — a click can never
  also start a drag.
- Labs with their own dispatchers (e.g. `experiments/symmetry_lab/
  lab_dispatch.py`) are unaffected; they keep resolving `mouse` Inputs their
  own way.
- AD-013 A3 (press/hold as a global rule) stays **OPEN**; this AD only fixes
  how click vs. drag is expressed in bindings, not any wider gesture
  semantics.
