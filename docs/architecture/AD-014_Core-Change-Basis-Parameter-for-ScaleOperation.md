# AD-014 — ScaleOperation: Optional Basis Parameter (Core Change)

**Status:** Accepted — explicit Core-Freeze exception, authorized by project owner
**Date:** 2026-09-20
**Scope:** `src/core/operations/transform.py::ScaleOperation`

## Problem

`ScaleOperation._transform_position()` applies `factor` as a purely diagonal,
world-axis-aligned multiplier (`f[i] * q[i]`). This is exact only when the
desired scale direction happens to be world-axis-aligned. WP-03C/WP-03D's
Normal-space Scale (single tangent axis and tangent-plane cases) approximate
a directional scale with `factor_i = 1 + (step-1) * |direction_i|` — this
approximation is exact only when `direction` itself is axis-aligned, which
is true for every default-cube face (hence invisible in existing tests) but
false for a face rotated within its own plane. Verified end-to-end on a
30°-rotated single-quad mesh through the real Application → ScaleTool →
ScaleOperation path: the previously "unchanged" tangent_y component visibly
shifts (shears) after a tangent_x-only scale.

Move and Rotate are unaffected — Move projects/subtracts a raw delta vector
(exact for any direction), Rotate uses a single axis vector directly (no
diagonal decomposition involved).

## Why this crosses the Core Freeze

The correct operation — `q' = q + (factor-1) * (component of q along an
arbitrary direction)` — is a rank-1 update, not expressible as three
independent per-world-axis multipliers unless the direction is axis-aligned.
No Tool-layer workaround can fix this; the diagonal-only contract in
`ScaleOperation` itself is the limitation.

Per project owner: the Core Freeze is a safety measure, not an absolute
prohibition — a genuine capability gap like this is a legitimate, explicit
exception, evaluated and authorized case-by-case (this conversation).

## Decision

Add an optional `basis` parameter to `ScaleOperation._transform_position()`:
three orthonormal vectors `(b0, b1, b2)`. `factor` (already a float-or-triple)
is decomposed against this basis instead of implicit world axes:

    q = pos - pivot
    c0, c1, c2 = dot(q,b0), dot(q,b1), dot(q,b2)
    result = pivot + f0*c0*b0 + f1*c1*b1 + f2*c2*b2

`basis=None` (default) preserves today's exact formula — `dot(q, world_x) ==
q[0]` etc., so world-axis-aligned callers are provably unaffected, not just
assumed unaffected (verified: `basis=None` output is bit-identical to the
current diagonal formula for arbitrary test vectors).

## Verified before this decision (not assumed)

- Backward compatibility: `basis=None` byte-identical to current behavior.
- Incremental contract preserved: two `factor=2.0` updates against a fixed
  basis compose identically to one `factor=4.0` update (matches the
  documented "factors multiply across update() calls" contract).
- History/Undo unaffected (operates on positions, not the formula).
- Soft-selection weighting unaffected (applied downstream of
  `_transform_position`, formula-agnostic).
- Correctness: matches the independently-derived rank-1 formula exactly for
  both single-direction and plane-exclude cases, confirmed on the actual
  30°-rotated quad that exposed the bug — tangent_y component now provably
  unchanged (not just "probably", measured before/after).
- Side benefit, not a new risk: mirroring along an arbitrary direction
  (negative factor component) now works the same way world-axis mirroring
  already did — no new code path, same formula.

## Blast radius checked

Only `src/mirai/interaction/tools/scale.py` constructs `factor` today; no
other caller of `ScaleOperation` in `src/` passes anything that would
interact with the new optional parameter. `experiments/` has its own,
separate `ScaleOperation` — untouched, different module.

## Not in scope

- RotateOperation / MoveOperation — already correct, not touched.
- Retroactively "fixing" the WP-03C/WP-03D no-shear tests' weak assertions
  is IN scope for the follow-up WP (see below) — this AD only covers the
  Core primitive itself.