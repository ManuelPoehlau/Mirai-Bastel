# AD-009 — Axis/Plane Constraints for Move/Rotate/Scale (Production, incl. XY/XZ/YZ)

**Status:** DECIDED ✓
**Date:** 2026-09-17
**Owner:** Manu (Project Owner)
**Scope:** `src/mirai/interaction/tools/{move,rotate,scale,transform}.py`

---

## Question

`RotateTool`/`ScaleTool` already accept a single-world-axis constraint (`axis="x"/"y"/"z"`);
`MoveTool` does not (verified — no `axis` parameter anywhere in
`src/mirai/interaction/tools/move.py`). V1's `AxisConstrainedMoveTool` was a V1-local experiment,
never promoted. Was leaving Move without axis constraints a deliberate scope decision, or an
unfinished promotion? (`docs/Repository_Wide Structural_Codebase_Health_Audit.md` D7.)

## Decision

**Production. Definitiv, kein Nice-to-have.** Axis constraints for **all three** transform tools —
Move, Rotate, Scale. Scope explicitly widened beyond the original question: **also add the three
plane constraints (XY, XZ, YZ)**, not just the single world axes.

## Current state (verified, for the implementation baseline)

- `RotateTool`/`ScaleTool` already resolve `axis`/`axes` through a shared `_WORLD_AXES` lookup
  (`src/mirai/interaction/tools/transform.py`) — but **only single axes** (`x`/`y`/`z`) are defined
  there today. No plane entries exist yet in production.
- `ScaleTool` already masks per-axis (`axes_mask`, e.g. `(1.0, 1.0, 1.0)` uniform, `(1.0, 0, 0)` for
  a single axis) — the masking *mechanism* already generalizes to planes (`(1.0, 1.0, 0)` for XY),
  it's only the `_WORLD_AXES` lookup table that is currently limited to single axes.
- `MoveTool` has no axis parameter at all today.
- V1 already sketched the full six-way model:
  `experiments/mirai_bastel_viewport_V1/viewport/constraints.py` defines
  `Constraint.{NONE,X,Y,Z,XY,YZ,XZ}` with a hotkey map (`x`/`y`/`z` for axis, `shift+x/y/z` for the
  corresponding plane) — but its own docstring calls it *"Temporäres Welt-Achs-/Ebenensystem …
  bewusst unabhängig von Move/Rotate/Scale"*. It was never wired into any tool; it's a UI-side
  sketch, not implemented math.

## Consequences (not yet executed — batched into the end-of-round cleanup pass)

1. `_WORLD_AXES` (`transform.py`) gets extended from 3 to 6 entries (`x, y, z, xy, yz, xz`), each
   mapping to a mask/direction consistent with how `ScaleTool.axes_mask` already works.
2. `MoveTool` gains an `axis=`/`axes=` parameter and the constrained-drag math, matching the
   existing `Rotate`/`Scale` convention (single axis today; plane as part of this decision).
3. `RotateTool`/`ScaleTool` gain plane-constraint support on top of what they already have.
4. V1's `Constraint` enum/hotkey naming (`constraints.py`) is a **naming reference only** — its
   hotkey map (`shift+x` → XY, etc.) is a reasonable default to reuse, but the enum/module itself is
   not promoted verbatim; it carries no math, only UI vocabulary.
5. Playground key wiring (currently `x/r/s` held = transform, per the Structural Health Audit's
   AI-H2 finding) needs its own extension to actually expose plane input — a separate, small wiring
   task once the tool-level math exists, not decided here.
6. Test coverage: each tool's existing test suite (`test_tool_*`) needs new cases for the three
   plane constraints, mirroring the existing single-axis tests.
7. **Open at implementation time, not a product question:** the precise math of what "plane
   constraint" means for a *drag* (project onto the plane vs. onto the two axes independently) —
   this is an implementation detail resolved during Production, not a Discovery question requiring
   another Artist Verdict, since the direction (three world planes, same convention as the existing
   axis constraints) is already set by this decision.
