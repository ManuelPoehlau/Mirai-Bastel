# Addendum: Multi-Bend Articulation Sessions + Topology Lock (H02)

> **SUPERSEDED 2026-09-17.** Multi-Bend was implemented, then reverted.
> H02 ships as Single-Bend. This document is kept for project memory only —
> Multi-Bend is parked as future research. Do not implement from this spec.

**Mode:** Production — the semantics below are a made decision (see the
chat discussion this addendum formalizes), not open research. Build it
reliably. Do not introduce new interaction ideas while implementing; if you
notice something that seems better mid-build, stop and flag it as a new
Discovery question instead of silently building your version (see
`MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md` §M5, "BUILD darf keine neue Erkenntnis
behaupten").

**Relationship to the original handoff:** this addendum extends
`ARTICULATION_CLAUDE_CODE_HANDOFF.md`, which is already implemented and
committed (base H02 wiring: single-gesture bend, restore via `F`/ESC, camera
free after drag-release). Read that document first — this one only covers
what changes on top of it. Do not re-read it as "still to build."

**Two separate concerns, kept separate on purpose (see §6 below and the
Acceptance Criteria table):** multi-bend sessions, and locking topology
edits out of the BENT state. They touch adjacent code but are independent
decisions with independent tests. Do not merge them into one code path
"because it's convenient" — if you find yourself tempted to, that's a sign
to stop and flag it rather than silently combine them.

## Context — read first

1. `playground/experiments/articulation/articulation.py` — the current,
   already-tested `ArticulationState`. Read its module docstring and the
   `begin()`/`update()`/`restore()` implementations before touching anything.
2. `playground/tests/test_articulation.py` — existing headless tests,
   currently 12/12 passing. In particular `test_update_is_relative_to_rest_
   not_cumulative` already proves the property this addendum depends on:
   `update()` recomputes fully from `_rest_positions` on every call, never
   incrementally. This is why the multi-bend semantics below need almost no
   new logic in `ArticulationState` itself.
3. `playground/window.py` — current H02 wiring:
   - `on_mouse_press`: the `articulation` family branch. Currently, **every**
     press restores any existing `ArticulationState` and constructs a brand
     new instance with a fresh `begin()`. This is the exact pattern that
     needs to change (§2 below).
   - `on_key_press`: `F` and `ESCAPE` handlers, both call
     `self._articulation_state.restore()` — unchanged by this addendum.
   - `K`/`I`/`J`/`E` handlers (Split Edge, Loop Insert, Connect Edges,
     Extrude) — currently unconditional, no articulation awareness. §5 below.

## 1. Session vs. Gesture — the semantics

Formalized from the chat discussion. This is the authoritative statement;
implement exactly this, do not reinterpret:

- An **Articulation Session** has exactly one immutable `_rest_positions`
  snapshot, captured once at session start (`begin()`).
- Within one session, any number of **Bend Gestures** are allowed. A gesture
  is one press→drag→release cycle.
- A new gesture may change `pivot`/`axis`/`radius`, but must **never**
  trigger a new rest snapshot.
- `update()` keeps calculating every gesture absolutely from
  `_rest_positions` — already true today, do not change this.
- Gesture B completely **replaces** gesture A's visible pose. Deformation is
  never cumulative across gestures within a session.
- `F` / `ESC` ends the session and restores the exact original REST state —
  unchanged from the existing behavior.
- `begin()` must still refuse a second call while a session is active (the
  existing `ArticulationError("begin() called twice — restore() first.")`
  guard stays exactly as is — do not weaken or remove it).
- There must be **no visible `restore()`** between two bend gestures in the
  same session — no flash back to rest, no VBO rebuild showing rest pose,
  between gesture A ending and gesture B starting.

```text
REST (immutable rest snapshot)
  ↓ BEND
BENT A
  ↓ new BEND (same session, new pivot/axis/radius)
BENT B
  ↓ new BEND (same session)
BENT C
  ↓ F / ESC
REST
```

## 2. `retarget()` — the new API

Add exactly one method to `ArticulationState` in `articulation.py`:

```python
def retarget(self, pivot: tuple, axis: tuple, radius: float) -> None:
    """Start a new gesture within the SAME session — no re-snapshot.

    Must only be called while a session is active (after begin(), before
    restore()). Does not touch `_rest_positions`. The next update() call
    computes the new gesture's pose fully from the existing rest snapshot,
    exactly as any update() call already does.
    """
    if not self._bent:
        raise ArticulationError("retarget() requires an active session — begin() first.")
    self.pivot, self.axis, self.radius = pivot, axis, radius
```

This is the only change to `articulation.py`. Do not touch `begin()`,
`update()`, or `restore()` — their existing behavior already provides
everything the session semantics need (see context item 2 above).

### Why no other change is needed

`update()` already writes every vertex in `_rest_positions` unconditionally
on each call — vertices outside the new gesture's falloff radius are
explicitly reset to `rest` (see the `if weight <= 0.0: new_pos = rest`
branch). So calling `retarget()` followed by `update()` naturally clears
whatever the previous gesture bent, without any explicit "undo gesture A"
step. This is a property of the existing math, not something you need to
add.

## 3. `window.py` wiring change

Replace the current `on_mouse_press` articulation branch's unconditional
restore-then-recreate pattern with:

```text
Press, articulation family focused, no active session
  (self._articulation_state is None or not self._articulation_state.is_bent)
    → pick pivot as today
    → create ArticulationState(mesh, pivot, axis, radius)
    → begin()
    → session starts

Press, articulation family focused, session already active
  (self._articulation_state is not None and self._articulation_state.is_bent)
    → pick new pivot as today
    → self._articulation_state.retarget(pivot, axis, radius)
    → NO begin(), NO restore()
    → same session continues, new gesture starts
```

`axis` is computed the same way it already is today (from drag direction —
see the existing `on_mouse_drag` comment block deriving axis from
`total_dx`/`total_dy`). `radius` may be recomputed the same way as the
initial press (`_mesh_bounding_radius(mesh)`) — it's cheap and the mesh
hasn't topologically changed within a session (see §5).

Do not add a VBO rebuild or HUD update between the old gesture ending and
the new one starting beyond what already happens naturally via `update()`'s
own rebuild calls during the drag — an explicit "reset to rest for one
frame" step would reintroduce the visible flash this addendum removes.

## 4. Acceptance criteria

**Multi-bend session (this addendum's primary scope):**

- Two consecutive bend gestures in one session, second gesture bends a
  *different* region: after the second gesture, the first region is back at
  rest, the second region is bent — verify headlessly (positions, no window
  needed).
- Two consecutive gestures, same pivot, same angle: `_rest_positions` is
  never re-captured (assert `_rest_positions` dict identity or content is
  unchanged between gestures — this is the direct test of "no new snapshot").
- Three or more gestures, then `restore()`: result is bit-identical to the
  original rest snapshot, regardless of how many gestures occurred — extend
  the existing `test_restore_is_exact` pattern.
- `retarget()` called before `begin()` (no active session) raises
  `ArticulationError`.
- `retarget()` called after `restore()` (session ended) raises
  `ArticulationError`.
- Live/manual verification only (no headless equivalent — flag if you find
  one): pressing to start a second gesture does not produce a visible
  one-frame snap to rest before the new bend appears.

**Topology lock (§5, separate concern — list its own criteria there).**

**Regression:** all 160 existing Playground tests and 398 existing
production tests (excluding the pre-existing, unrelated
`test_extrude_tool.py` import failure) still pass unchanged.

## 5. Topology lock — Option 2: Automatic Restore

**Separate concern from §1–4 above.** This is the fix for the earlier,
separately-diagnosed bug: today, `K`/`I`/`J`/`E` run unconditionally, even
while an articulation session is active — and since operations like Split
Edge / Loop Insert / Connect Edges (kind "v") create *new* vertex IDs via
`mesh.split_edge()`, those new vertices have no entry in `_rest_positions`
and cannot be restored correctly. See the chat discussion for the full
diagnosis; this section is the fix, not a re-diagnosis.

**Chosen behavior: automatic restore, not blocking.** If `K`/`I`/`J`/`E` is
pressed while `self._articulation_state is not None and
self._articulation_state.is_bent`, the handler must first call
`self._articulation_state.restore()` (ending the session, mesh returns to
exact rest) and clear `self._articulation_state = None`, **then** proceed
with the topology operation exactly as it already does today on the
now-rest mesh. Do not silently ignore the keypress and do not show an error
— the topology operation still happens, just after an implicit restore.

This mirrors the existing pattern already used for the `Y`/`H`/`C` scene-
load handlers (which already null out `_articulation_state` on scene
change) — reuse that shape rather than inventing a new one.

### Topology lock acceptance criteria

- Start a session, bend, press `K` (Split Edge) with a valid edge selection:
  mesh must be at exact rest positions (all vertices from the pre-bend
  snapshot) at the moment the split executes, and the split's new midpoint
  vertex must be computed from rest geometry, not bent geometry. Verify
  headlessly: begin a session, update(), then call the same restore-then-
  split sequence the handler will use, assert midpoint equals the rest-space
  midpoint.
- Same for `I` (Loop Insert) and `J` (Connect Edges, kind "v" path — the one
  that creates new vertices via `split_edge`).
- `E` (Extrude): starting an extrude while a session is active must also
  trigger the automatic restore first, for the same reason (extrude direction
  is computed from current — otherwise bent — face geometry).
- After the automatic restore + topology op, `self._articulation_state` is
  `None` — a fresh press is required to start a new session, exactly as
  after a manual `F`/ESC restore.
- HUD action text should make the implicit restore visible (e.g. "Articulation
  restored (topology edit)" or similar) rather than silently swallowing it —
  match the existing HUD phrasing style used elsewhere in `window.py`, your
  call on exact wording.

### Explicit non-goal for this addendum

Do not implement Option 1 (block/ignore the key) anywhere, even as a
fallback or a commented-out alternative. Option 2 is the decision.

## 6. Do not conflate the two changes

Multi-bend sessions (§1–4) and the topology lock (§5) are independent:

- Multi-bend sessions work identically whether or not the topology lock
  exists — a session with three gestures and no topology edits is fully
  testable without §5 ever running.
- The topology lock works identically whether the session had one gesture
  or five — it doesn't care how many `retarget()` calls happened, only that
  `is_bent` is true when the key is pressed.

Keep them as separate commits if practical, and definitely as separate test
functions/files — do not write a single test that exercises both at once as
your only coverage for either.

## Explicit constraints (unchanged from the original handoff)

- `src/core/`, `src/viewport/`, `src/mirai/` — never touch.
- Do not change the behavior of `selection`, `presentation`, `transform`,
  `tweak`, or `topology` families as a side effect.
- No `MeshStateCommand`, no history push for articulation itself — still
  true, `retarget()` doesn't change this.
- Do not add a second articulation variant or make pivot/axis/radius
  externally configurable beyond what §3 describes — still a workshop rig,
  not a UX surface.
- Do not decide or hint at a KEEP/ITERATE/REJECT verdict anywhere.

## When done

Report back: whether `retarget()`'s guard conditions needed any adjustment,
how the "no visible restore flash" requirement was verified (headless proof
is impossible for this one — describe what you actually observed live),
which HUD text you chose for the automatic-restore case, and whether the
`E` (Extrude) automatic-restore interacted awkwardly with Extrude's own
hold-to-drag lifecycle (flag, don't silently work around).
