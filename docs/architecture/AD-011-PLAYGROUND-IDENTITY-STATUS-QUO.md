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

(Q from `docs/archive/audits_2026-09/Ownershi_Lifecycle_Audit_V1_Integration_Lab_Playground.md` §10, Q-G analog for the
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

---

## Addendum — 2026-10-21: Playground becomes an optional research tool (Manu)

The premise of this decision ("the Playground is the repo's only runnable application") no longer holds: `src/main.py`
is the production application, and the decided Playground results (selection, transform, tweak, connect, knife,
topology/extrude, display modes) have been promoted into it. Manu's statement (2026-10-21, repository slimming
audit): the Playground is **not a primary daily development environment any more**; it stays as an *optional* research
tool for new UX questions and multi-operation workflows, on its older viewport/renderer path.

Decisions and consequences (Manu, 2026-10-21, all implemented in the same change set):
- **Tests.** `playground/tests` is not part of the default `pytest` run (`pytest.ini`) and is no Production gate.
  `tests/` imports nothing from `playground/` (the six `src/`-owned test modules moved to `tests/`;
  `test_playground_transformer.py` moved the other way, which settles item 3 above).
- **Knife is no Playground topic** ("schon fest in Production"). The Playground no longer hosts any Knife
  (families `knife` and `knife_face`, their window code, tests and handoffs are gone; `C` on an empty selection only says
  the Knife is in the app). The frozen Lab engines (B, D, Q5), the golden data and the golden / differential /
  `split_face` equivalence tests moved to `experiments/knife_oracle/`; AGENTS.md §8a lists when to run them. The
  Knife record `knife_face/decision.md` is `docs/research/topology/KNIFE_FACE_DECISIONS.md`. The ATELIER candidate
  "Knife-Familien im Playground zusammenführen (S5)" is void.
- **Gizmo → `src/`** (AD-016 D3): `mirai.viewport.gizmo` (geometry, picking, draw primitives), `Application` (handle
  press / drag / release as an entry point, world frame), `viewport.gl_gizmo_overlay` (drawing), switched on by
  `src/main.py` (`gizmo_enabled`). The Playground imports the shared maths from there and keeps its normal-space
  frames, which are not in the app.
- **Lasso Select → `src/`** next to Box and Paint (`Application`, hold `Q` + LMB drag, `PROVISIONAL`).
- **Articulation (EX-A) stays in the Playground** for now. Deformers / modifiers (bends, twists, lattices …) are a later
  topic (`docs/future_ideas/`).
- The remaining variant families (presentation, selection, transform, tweak, connect, topology) are *candidates* for
  archiving; that is a separate, later step.

## Addendum — 2026-10-24: Playground removed (Manu, consolidation)

The "separate, later step" above is taken: `playground/` is removed together with its tests (Manu's decision,
2026-10-24). Nothing in `src/` or `tests/` imported it; the gizmo's normal-space frames are in the app since the
WP Toolbox Gaps C1 orientation (`K`). Articulation (EX-A) and the shadow-map study are not carried over; the note in
`docs/future_ideas/MODELING.md` names the commit with their last state (`61ebe77`). README, MANUAL and family decisions:
`docs/archive/experiments_2026-10/playground/`.
