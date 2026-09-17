# AD-010 — Playground Supersedes the Lab's Core→Viewport Binding Role

**Status:** DECIDED ✓ (binding authority decided; the port itself is a separate, not-yet-scoped task)
**Date:** 2026-09-17
**Owner:** Manu (Project Owner)
**Scope:** `playground/renderer.py`, `playground/app.py`, `experiments/mirai_bastel_integration_lab/`

---

## Question

Two parallel "Core → production Viewport" bindings exist and neither is marked authoritative:
the Lab's `adapters/core_to_render.py` (`LabPygletStore`, wired to the real `PygletStore` GPU
backend, the only place in the repo that has ever exercised production `src/viewport`'s
incremental-update path on real hardware) and the Playground's `renderer.py` + `app.py` (thin
passthrough, deliberately configured with `store_type=TraceStore` — headless only, own hand-rolled
VBO rebuild on every interaction instead of `PygletStore`'s in-place patching).

(Q-I, `docs/Ownershi_Lifecycle_Audit_V1_Integration_Lab_Playground.md` §10; confirmed by direct
code inspection in this conversation: `playground/app.py` uses `store_type=TraceStore`;
`experiments/mirai_bastel_integration_lab/adapters/core_to_render.py` defines `LabPygletStore(PygletStore)`,
used live by `lab_viewport.py`.)

## Decision

**Playground supersedes the Lab.** Once the Playground's renderer is wired to the real
`PygletStore` GPU backend (adopting the pattern the Lab's `LabPygletStore`/`core_to_render.py`
already proved on real hardware), the Playground itself becomes the live, daily-used exercise of
production `src/viewport`'s real-GL path — which was previously the Lab's one remaining unique
purpose.

Artist's own reasoning: given the Playground has already overtaken the Lab's originally-intended
role everywhere else, it following through on the Lab's one remaining advantage (proven real-GL
binding) "beantwortet die Frage eigentlich sogut wie selbst" — logical, not a hard call.

## What this decision does NOT do

- It does **not** decide whether the Playground is formally "the application" or remains a research
  host — that question is explicitly deferred, to be discussed separately.
- It does **not** execute the port. Wiring `playground/renderer.py` to `PygletStore` instead of
  `TraceStore`, and replacing `window.py`'s full VBO rebuilds with `PygletStore`'s in-place
  patching, is its own implementation task — not scoped here, batched into the end-of-round
  cleanup pass along with AD-006 through AD-009.
- It does **not** retire the Lab today. Retirement follows once the port above is done and
  verified — same pattern as `AD-006` for V1: archived as project memory (code + its 52 passing
  tests + its GL-live-verification findings), not deleted.

## Consequences (not yet executed)

1. **Follow-up implementation task (to be scoped separately):** port `playground/renderer.py` /
   `playground/app.py` from `TraceStore` to `PygletStore`, using the Lab's `LabPygletStore` /
   `core_to_render.py` as the reference implementation to adapt from (per `AGENTS.md` M1 — reuse
   validated work rather than reinvent it) rather than deriving the wiring from scratch.
2. Once ported and verified, `experiments/mirai_bastel_integration_lab/` becomes purely historical
   — mirrors `AD-006`'s V1 pattern exactly.
3. Closes **Q-I** from the Ownership/Lifecycle Audit: the Playground's binding becomes authoritative
   once it adopts what the Lab already proved; the Lab's binding was the correct reference, not a
   competing one to discard.
4. The Lab's *other* content (`adapters/triangulate.py` ear-clipping research, its instrumentation/
   reporting) is not addressed by this decision — may retain standalone research value independent
   of the binding question; left untouched.
5. `docs/design/artist_playground/ARCHITECTURE_MAP.md`'s claim that `src/viewport` is *"the only
   complete renderer in the repository"* (flagged as drift in the Structural Health Audit, row 3)
   becomes accurate only after this port — update that document at execution time, not now.
