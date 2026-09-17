# AD-006 — V1 Viewport Retirement

**Status:** DECIDED ✓
**Date:** 2026-09-17
**Owner:** Manu (Project Owner)
**Scope:** `experiments/mirai_bastel_viewport_V1/`, `experiments/rigging-skinning-morphing/run_viewport.py`

---

## Question

Is `experiments/mirai_bastel_viewport_V1/` still needed as an interactive workbench — specifically
by `experiments/rigging-skinning-morphing/run_viewport.py`, which was the last remaining runtime
consumer of the V1 `viewport` package anywhere in the repository?

(Full evidence base: `docs/Ownershi_Lifecycle_Audit_V1_Integration_Lab_Playground.md` §10, Q-A/Q-B.)

## Decision

**REJECT — V1 Viewport wird nicht mehr verwendet.**

The Artist Playground (`playground/`) is sufficient for the rigging experiment's visual-inspection
need (viewing and hand-editing the head basemesh). V1's viewer role is not renewed.

## Consequences (not yet executed — each is its own bounded follow-up)

1. `experiments/rigging-skinning-morphing/run_viewport.py` is now dead code (it was the sole
   remaining external consumer of V1's `viewport` package). Whether it is deleted, archived in
   place, or repointed to the Playground is a separate, small implementation task — not decided by
   this entry.
2. With no external consumer left, `experiments/mirai_bastel_viewport_V1/` becomes **purely
   historical**: reference/archive material only (project memory per `AGENTS.md` M1 / §7), not
   active infrastructure. Its code, tests (184 passed + 21 subtests) and `perf/` evidence are
   **not** deleted — they remain as the documented ancestor of promoted `src/mirai/*` and
   `playground/topology_tools/*` code.
3. `experiments/rigging-skinning-morphing/viewport_adapter.py`'s dependency on the `mirai_bastel_core`
   (Core-V1) fork is **not** resolved by this decision. That fork was kept deliberately ("ein
   Angleich ist eine spätere, bewusste Entscheidung") and remains a separate open question,
   independent of the viewer question.
4. The repo-wide `viewport` package-name collision (D1 in the Structural Health Audit — the cause
   of 46 bare-`pytest` collection errors) is **not** resolved by this decision alone; V1 could still
   be renamed/archived without waiting on this, but doing so is a separate task.
5. Documentation that describes V1 as having "one remaining consumer" (`experiments/README.md`,
   updated 2026-09-17) needs a further update once the retirement is actually executed — this entry
   records the decision, not the implementation.

## What this decision does NOT do

- It does not delete or move any file.
- It does not decide *how* `run_viewport.py` is retired (delete vs. archive vs. repoint).
- It does not decide the Core-V1-fork alignment question.
- It does not rename the `viewport` package.

Each of those remains a small, separately-scoped task per `AGENTS.md` §8.
