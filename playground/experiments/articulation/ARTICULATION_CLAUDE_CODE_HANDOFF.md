# Task: EX-A — Wire Temporary Articulation into the Playground (H02) + Topology Limits Report (H03)

**Mode:** Production for H02 — the research decision on *what* to build (H01's
scope) is made and already implemented, tested, and committed. Build the
wiring reliably. Do not introduce new interaction ideas while implementing;
if you notice something that seems better mid-build, stop and flag it as a
new Discovery question instead of silently building your version (see
`MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` §M5, "BUILD darf keine neue Erkenntnis
behaupten").

H03 is explicitly Discovery/reporting, not a fix task — see its own section
below.

## Context — read first

1. `docs/design/artist_playground/EXPERIMENT_HOST.md` — Experiment/Variant/
   ExperimentSlot conventions.
2. `docs/research/CHARACTER_SYSTEMS_RESEARCH.md`, Axis 6a — the research
   question behind EX-A: does temporary articulation help the artist detect
   topology problems earlier while modeling?
3. `playground/experiments/articulation/articulation.py` — **already built,
   already tested, do not rewrite.** `ArticulationState` (begin/update/
   restore lifecycle, pivot+falloff rotation, no history, exact restore).
   Read its module docstring — it documents why this does *not* use the
   production `Tool` ABC (no commit semantics — articulation is never
   permanent) and why `linear_blend_skinning` was evaluated and rejected in
   favor of a direct two-state weight blend.
4. `playground/experiments/articulation/demo_cylinder.py` — already built.
   The EX-A test body. Deliberately not the Head Basemesh: the head has 52
   poles (30× valence-3, 22× valence-5 of 326 vertices, measured) where
   several topology tools already refuse to operate — see H03. The cylinder
   has exactly 2 poles (cap centers) and is regular everywhere else.
5. `playground/tests/test_articulation.py` — already built, 12/12 passing.
   Covers the pivot+falloff math, exact restore, and the
   restore→topology-change→articulate-again cycle headlessly. This is your
   regression baseline for the math layer — if you touch `articulation.py`
   or `demo_cylinder.py`, these must still pass unchanged in behavior.
6. `playground/topology_tools/extrude.py` and `playground/topology_tools/
   loop_slide.py` — existing prior art for the exact tool lifecycle pattern
   (`begin()` → snapshot, `update()` → live, `commit()`/`cancel()`) and, more
   importantly here, for how `window.py` currently intercepts
   `on_mouse_drag`/`on_mouse_motion` for an active tool **before** camera
   handling is reached.
7. `playground/window.py` — current live wiring. Specifically:
   - Lines ~669–697: `on_mouse_drag` — active tools consume the drag and
     return `EVENT_HANDLED` before the camera orbit handler (Alt+LMB,
     ~line 710) is reached. **This is the exact mechanism H02 must not
     leave engaged once articulation ends.**
   - Lines ~205–234: the five-family slot registry (`selection`,
     `presentation`, `transform`, `tweak`, `topology`) via
     `app.register_slot(...)`. Articulation becomes a sixth family here.
   - `TAB` (focus family) / `M` (cycle variant within focused family) — the
     existing Host runtime pattern; reuse, don't reinvent.

## Scope — H02

Wire `ArticulationState` into the running Playground so the following loop
is actually playable:

```
REST
  ↓ press+drag (pivot picked at press point, gesture owns the mouse)
BEND            → ArticulationState.begin() + update() per mouse move
  ↓ release
BENT / INSPECTION   → mouse is free again: Orbit / Pan / Zoom / Wireframe
  ↓ second input (key, TBD — pick one, document which)
RESTORE         → ArticulationState.restore(), exact rest pose
  ↓
(artist edits topology via existing K/I/J/E/G tools, as normal)
  ↓
BEND again      → repeat
```

### The one thing that must not happen

The current drag-consumption pattern (context item 7, first bullet) must
**not** carry over into the BENT/INSPECTION state. Once the mouse button that
started the bend is released, camera navigation (Orbit/Pan/Zoom) must work
exactly as it does with nothing active — no special-casing of camera
handlers, no "articulation-aware" branch in the camera code. The simplest
correct shape is probably: articulation only ever holds the mouse *during*
the drag that produces the angle; the moment that drag ends, articulation's
own `on_mouse_drag`/`on_mouse_motion` involvement ends too, and normal event
flow (which already reaches the camera when no tool claims the event)
resumes unmodified.

### Sixth family

Register `articulation` as a sixth Host family (context item 7, second
bullet), one variant to start (matches the Experiment Brief's explicit
"one variant, not two" — a second variant, e.g. estimated-vs-set pivot,
would be a second research variable and is out of scope here). The HUD's
`Setting:` line should reflect it via `PlaygroundHUD.update_setting()` —
reuse, don't build a second HUD mechanism.

### Pivot and axis rule (fixed, not researched here)

Per the Experiment Brief (§4), pivot/axis/radius are a workshop rig, not a
UX decision to explore:

- **Pivot:** the mesh-surface hit point at press (reuse the existing
  `pick_component`/picking path already used by Selection).
- **Axis:** a fixed rule — e.g. screen-right at press time, or the
  cylinder's local circumferential direction, whichever is simpler to wire
  correctly against the current camera. Pick one, document which and why in
  a code comment — this is exactly the kind of fixed-but-arbitrary choice
  the Experiment Brief flags as acceptable for a workshop rig.
- **Radius:** a fixed value or a fixed fraction of mesh bounds. Same
  treatment — pick one, comment why.

Do not make pivot/axis/radius configurable or exposed as a second variant.
That would silently turn this into CE-3 (a second research variable) instead
of EX-A.

## Acceptance criteria (from the original EX-A handoff, H02 portion)

1. EX-A starts reproducibly (`python playground/run.py`, whatever the
   current launch convention is — check `playground/MANUAL.md`).
2. Articulation with pivot + falloff works (already true headlessly — verify
   it survives wiring into the live loop unchanged).
3. Bent state persists after the gesture ends (mouse released, key held down
   is not required).
4. Orbit/Pan/Zoom work in the bent state.
5. Restore returns the exact rest pose (already true headlessly — verify
   this holds through the live loop, including after `update()` was called
   multiple times during the drag).
6. Topology can be changed in the rest state (existing K/I/J/E/G tools,
   unmodified).
7. Articulation works again after a topology change (already covered
   headlessly by `test_articulation.py`; verify live).
8. Existing tests stay green: `pytest playground/tests/` (currently 160
   passing, ignoring `test_input_map.py`/`test_selector.py` only if your
   environment also lacks a display — if you have a real display, those two
   should run too) and `pytest tests/` from repo root (currently 398 passing
   excluding the pre-existing, unrelated `test_extrude_tool.py` import
   failure — do not fix that as part of this scope).
9. No regression in the existing five families' behavior.

## Explicit constraints

- `src/core/`, `src/viewport/` — never touch (production, frozen).
- Do not change the behavior of `selection`, `presentation`, `transform`,
  `tweak`, or `topology` families as a side effect.
- Do not route articulation's input through `PlaygroundInputMap` as part of
  this task — same reasoning as the Tweak handoff: unifying the input
  handling is a separate, later concern (`DEV_HOST_AUDIT.md` §4).
- Do not add bones, skinning weights, morph targets, or anything from
  `experiments/rigging-skinning-morphing/` beyond what `articulation.py`
  already reuses (`Transform`). This stays a two-state (rest / articulated)
  gesture, not a rig.
- Do not push articulation to History. There is no commit — the only two
  states are BENT (transient, in-memory) and RESTORED. If you find yourself
  wanting a `MeshStateCommand` for articulation, stop — that's a sign the
  scope is drifting toward "articulation is a permanent edit," which is a
  different, un-made decision.
- Playground code (wiring, variant class) may be quick-and-dirty, same as
  the rest of the Host — this is Discovery-adjacent research code, not a
  production deliverable.
- Do not decide or hint at a KEEP/ITERATE/REJECT verdict anywhere. That's
  the Artist's, after playing, not yours.

## Scope — H03 (separate, do after H02 works)

**Not a repair task.** Produce a short report, not a fix.

Using the current Head Basemesh (326 vertices, 324 faces, 52 poles: 30×
valence-3, 22× valence-5 — already measured, feel free to re-verify), and/or
the cylinder if it usefully isolates a case, document where the current
topology toolchain hits limits:

- Loop Select / Loop Slide at poles (already known to require valence-4
  throughout the loop — confirm and give a concrete example).
- Connect Edges across mixed vertex valence (kind "v" requires
  `_is_regular_interior_vertex`: valence ≥4, no boundary, all-quad
  neighborhood — confirm and give a concrete example).
- Extrude, Split Edge, Loop Insert, Ring Select — check whether any of these
  have undocumented limits beyond what's in their module docstrings.

For each finding, classify it explicitly as one of:

- **technical bug** — the code doesn't do what its own docstring/contract
  says it should.
- **current limitation** — works as documented, but the documented scope is
  narrow (e.g. "only regular quad topology").
- **unresolved modeling semantics** — there isn't yet an agreed answer for
  what the *correct* behavior even is (e.g. "what should Loop Slide do when
  the loop passes through a valence-5 pole?" is a design question, not a
  bug).

Do not propose or implement a fix for any of these. Do not redesign the
topology toolchain. The report is the deliverable.

## When done

Report back, for H02: which files were touched, which pivot/axis/radius
rule you picked and why, how the drag-release → free-mouse transition was
implemented, and whether anything in `articulation.py`'s existing lifecycle
turned out to be awkward to wire (in which case: describe the problem, don't
silently work around it by changing the module's semantics).

For H03: the classified findings list, nothing else.
