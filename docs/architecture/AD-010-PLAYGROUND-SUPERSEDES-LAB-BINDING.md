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

---

## Execution Update — 2026-09-18

**Executed** (commit `8353c56`): the store-swap portion of Consequence #1 —
`playground/app.py`, `playground/window.py`, `playground/run.py`,
`playground/_diag_screenshot.py`, `playground/renderer.py`, new
`playground/gl_store.py` (`PlaygroundPygletStore`, vec3-padded subclass of
`PygletStore`, adapted from `LabPygletStore` rather than cross-imported from
`experiments/` — keeps the Promotion Boundary intact).

Scope actually delivered:
- Live window path (`run.py`, `_diag_screenshot.py`, hotkeys `C`/`H`/`Y`) now
  runs the Viewport's Store on `PlaygroundPygletStore` instead of `TraceStore`.
- Headless default stays `TraceStore` — `load_cube`/`load_head`/`load_cylinder`
  gained a `store_type` parameter instead of a global default change, so the
  existing test suite needed zero edits.
- **New finding, not anticipated in the original Decision text above:** the
  Playground's entry points (`run.py`, `_diag_screenshot.py`) construct the
  scene/Viewport *before* the `pyglet.window.Window` (and its GL context)
  exists — the opposite order from the Lab's `IntegrationLabWindow`. A bare
  store swap would have crashed `PygletStore.allocate()` on missing context.
  Fixed by moving scene load into `PlaygroundWindow.__init__`, after
  `super().__init__()`.

**Verified** (this conversation, via Xvfb — software GL/Mesa-llvmpipe, *not*
real hardware): Viewport genuinely runs on `PlaygroundPygletStore` at
runtime (no silent fallback); real GPU resource allocation succeeds for all
four `RenderMesh` resources plus `camera_uniforms`; **GPU Resource
Persistence holds** — after a vertex move + `sync()`, all pre-existing
resource IDs stay identical (in-place `update()`, not reallocation);
`glGetError() == 0` across `on_draw()`, scene reload, and hotkey-equivalent
scene switching; full `playground/tests/` suite (233 tests) stays green,
including under a real X display. Real-hardware confirmation is still
outstanding — same caveat the Lab's original evidence needed before it
counted as proven.

**Deliberately NOT done** (unchanged from the Decision above — not silently
expanded):
- `window.py`'s ~20 `_rebuild_vbo()` call sites still fully rebuild on every
  interaction. **Note for the next agent:** the Lab's reference
  (`lab_viewport.py::_move_picked_vertex`) only demonstrates in-place
  patching for the single-vertex-move case, on its own hand-built `vlist`
  (`pos_buf.set_region()`/`nrm_buf.set_region()`), bypassing the Production
  `PygletStore.update()` entirely. Selection, hover, and topology changes are
  fully rebuilt in the Lab too — there is no proven reference pattern for
  those. Treat "replace remaining full rebuilds with in-place patching" as
  new engineering per case, not a port, when scoping it.
- Lab retirement (Consequence #2): not started.
- `ARCHITECTURE_MAP.md` (Consequence #5): not updated — the "only complete
  renderer" claim is still arguably contested by the Playground's own
  hand-rolled draw path in `window.py`, independent of which Store backend
  feeds its accounting.

