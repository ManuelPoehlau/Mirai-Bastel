# AD-011 — Playground Identity: Status Quo (No Formal Promotion to "The Application")

**Status:** DECIDED ✓ (deliberately UNKNOWN-leaning-status-quo, not a promotion — see Decision)
**Date:** 2026-09-17
**Owner:** Manu (Project Owner)
**Scope:** `playground/` (identity/status only — no code or structure changes implied)

---

## Question

Is `playground/` now formally "the application", or does it remain a research host? The answer
would determine whether its input map/camera defaults may keep diverging from production bindings,
whether `tests/test_playground_transformer.py` belongs in `tests/`, and whether the unused
production Input→Command→Tool contract (`src/mirai/interaction/*`) should be reconciled with the
Playground's own ad-hoc key wiring.

(Q from `docs/Ownershi_Lifecycle_Audit_V1_Integration_Lab_Playground.md` §10, Q-G analog for the
Playground itself; raised initially by the artist as: "was wäre App, was wäre Lab/Playground jetzt,
braucht man die App schon, obwohl eh erstmal noch monatelang experimentiert wird?")

## Decision

**Playground bleibt, was er jetzt gerade ist.** No formal promotion to "the application." Explicit
reasoning: the project is still relatively early; nothing today is blocked by the absence of a
formal answer, and several variant families (Tweak, Selection) still carry open verdicts
(`Status: OFFEN — noch nicht gespielt`) that a formal promotion would put unwanted pressure on to
settle prematurely.

This is a genuine decision, not a deferral: the artist chose "keep the current shape" over "build a
separate App now" or "formally declare the Playground done." It is revisited if/when a concrete
need appears (per M4's attention filter — no artist attention spent again on this until something
actually requires it).

## Consequences

1. `playground/` continues to diverge deliberately from production bindings, default camera angle
   and key semantics (as already documented in `PlaygroundCamera`'s docstring and
   `playground/README.md`) — this divergence is not "debt to resolve," it is the Playground doing
   its job.
2. The production Input→Command→Tool contract (`src/mirai/interaction/commands.py`,
   `bindings.py`) remains declared-but-unhandled by any running application (Structural Health
   Audit finding D4) — not resolved by this decision, and not expected to be until a real
   application entry point exists, which this decision explicitly does not create.
3. `tests/test_playground_transformer.py` living inside `tests/` (Structural Health Audit finding
   T3) is left as-is — not reclassified by this decision.
4. AD-006 through AD-010 (V1 retirement, asset/loader ownership, import/framing promotion, axis/
   plane constraints, Playground↔Lab rendering binding) all stand independently of this decision —
   none of them required a Playground identity verdict, and none is affected by it.
5. No documentation needs updating *because of* this decision beyond what Round 1 already did
   (naming the Playground as the repo's only runnable application in `CLAUDE.md`, without implying
   it is formally "production"). That distinction — *is* the running application today vs. *is
   declared* production-stable — is the one this decision deliberately keeps open.
