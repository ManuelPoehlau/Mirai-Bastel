# WP-AP-CUT — Knife Hover Feedback: Implementation Brief (for Claude Code)

**Status:** Ready for implementation
**Date:** 2026-09-22
**Mode (M5):** Production — the interaction decisions below (kind-based hover dispatch, Variant A vs.
B as a Family, cancel-before-switch) are decided. **BUILD must not claim new knowledge:** if something
unexpected appears while building, stop, record it as an open question, do not silently decide it.
**Authority:** This brief, agreed with Manuel in chat on 2026-09-22. No standalone AD exists yet for
this — if you find yourself making an architectural call not covered below, flag it, don't invent it.
**Related:** AD-017 (`docs/architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md`), `WP-AP-CUT_PLAN.md`
(§1.2 `topology_points.py`, §C4 face-interior knife is explicitly out of scope there too).

---

## 0. Problem statement

Knife (`playground/topology_tools/knife.py`, `knife_pick.py`) is implemented and tested
(`tests/test_ad017_knife*.py`), but has **no visual hover feedback** while active. The cause is
concrete, not vague: `PlaygroundWindow.on_mouse_motion` (`playground/window.py` ~line 1210) has an
early-return Knife branch (~line 1215–1221) that calls `knife_tool.hover(target)` for its internal
state but never touches `sel.hovered` / `_rebuild_hover_vbo()` — so it never reaches the general
Hover-Highlighting block (~line 1282–1289) that every other mode already gets. The code comment at
line 1220 ("visual highlight handled by renderer") is stale/wrong — `renderer.py` is a thin facade
over `viewport.sync()`; the actual draw calls live in `PlaygroundWindow.on_draw` (~line 1930), and
there is no Knife-specific draw path there today. Confirmed by reading the current `main` branch.

## 1. Context — read first

1. `playground/window.py`:
   - `on_mouse_motion` (~1210–1289) — current Knife hover branch and the general hover block it
     currently bypasses.
   - `_rebuild_hover_vbo` (~538–567) and the Hover-Highlight draw pass in `on_draw` (~1976–1998) —
     existing Selection-hover infrastructure, keyed off `sel.hovered` + `sel.mode`.
   - `_active_transform_model` / `_active_tweak_variant` (~703–747) — the existing pattern for
     reading "which variant of this family is active" from a registered `ExperimentSlot`. Follow this
     shape for a new `_active_knife_model()`.
   - The `M` key handler (~1530–1543) — existing precedent for **cancel-before-switch**: switching
     the active Transform variant mid-interaction first cancels the in-progress transform. Do the
     analogous thing for Knife (see §3.4).
   - `on_mouse_press` Knife click branch (~1114–1133) and `on_key_press` Knife entry
     (~1451–1463, `CContext.KNIFE`) — how a Knife session currently starts.
2. `playground/topology_tools/knife.py` — the Knife state machine (`hover()`, `click()`, commit/
   cancel/undo/redo). **Do not change its logic.** `hover()` already returns `{"valid": bool,
   "target": target, "start": ...}` from the same `target` dict this task will also use for drawing —
   reuse the return value, don't recompute validity separately.
3. `playground/topology_tools/knife_pick.py` — `knife_pick()` returns exactly four target kinds:
   `vertex`, `edge` (with `t`), `face` ("on mesh, no target"), `outside`. Reuse `_edge_t_3d`'s
   approach (don't duplicate the math) for computing a free-space point at a given `t` — see §3.2.
4. `playground/vbo_builder.py` — existing ID-keyed VBO builders (`build_selection_vertex_data`,
   `build_selection_edge_data`). None of them accept a raw world position; §3.2 needs one small new
   function here, not a rewrite of the existing ones.
5. `playground/experiments/tweak/` (all four `variant_*.py` + `slot.py`) — the Family/Variant/
   ExperimentSlot convention this task follows: one `Experiment` subclass per variant, registered as
   one `ExperimentSlot` family, switched via the existing generic Tab (focus family) + `M` (cycle
   variant within focused family) mechanism. Reuse this mechanism as-is — do not invent a new
   switching key for Knife.
6. `docs/design/artist_playground/EXPERIMENT_HOST.md` — Experiment/Variant/ExperimentSlot
   conventions, background for point 5.

## 2. Scope

Give Knife the same hover feedback quality every other mode already has, decoupled from
`sel.mode`/`sel.hovered` (so it naturally extends to Face later — see §5), plus two switchable
interaction variants for how the Edge split-point preview behaves.

### 2.1 Shared prerequisite — kind-based Knife hover dispatch (built once, used by both variants)

Replace the Knife branch's early return in `on_mouse_motion` with a small dispatch that:

- Calls `knife_pick()` (as today) and `knife_tool.hover(target)` (as today, unchanged).
- Based on `target["kind"]`, builds hover-highlight geometry **independent of `sel.mode`**:
  - `"vertex"` → reuse `build_selection_vertex_data({vid})` as-is.
  - `"edge"` → reuse `build_selection_edge_data({eid})` as-is for the edge highlight itself, **plus**
    the Variant A/B-specific split-point preview (§3).
  - `"face"` / `"outside"` → no highlight geometry (matches `knife_tool.hover()`'s existing
    `valid: False` treatment of both). Leave the two visually identical for now — do not invent a
    "no valid target" vs "outside" distinction; that's a separate, not-yet-decided UX question.
- Store this in a **separate, Knife-owned state** (e.g. `self._vlist_knife_hover_edge`,
  `self._vlist_knife_preview_point`, or similar — your call on exact naming) — do **not** write to
  `sel.hovered` and do **not** repurpose `_rebuild_hover_vbo()`. Reason: `_rebuild_hover_vbo()`
  chooses GL_POINTS/GL_LINES/GL_TRIANGLES from `sel.mode`, which during a Knife session holds
  whatever mode was active before Knife started (Knife only requires an *empty* selection, not a
  specific mode) — reusing it would either need a mode override with side effects on the real
  Selection display, or silently render the wrong primitive. Draw the new Knife hover VBO(s) using
  the **same** `_overlay_program` and the **same** `_HOVER_COLOR` as the existing hover pass, just as
  its own draw call in `on_draw`, guarded by "Knife session active" instead of `sel.hovered`.
- Rebuild only on change (mirror the existing `if hit != sel.hovered:` guard style at ~1287) — don't
  rebuild VBOs every motion event if the target hasn't changed. For Variant A the preview point
  itself changes continuously along the edge, so that one VBO does rebuild every motion event while
  hovering an edge — that's expected, not a bug to avoid.

### 2.2 New `"knife"` Family with two variants

Register a new family (`playground/experiments/knife/`, `variant_a.py` + `variant_b.py` +
`__init__.py`, `decision.md` via `ExperimentSlot.generate_decision_md()` — same shape as
`playground/experiments/tweak/`). Add `_active_knife_model()` to `window.py` following the
`_active_transform_model()` pattern, reading an `activation` (or similarly named) attribute off the
active variant, e.g. `"live_preview"` / `"press_slide_release"`.

#### Variant A — Live Preview

- While hovering a valid edge target (`kind == "edge"`, per `knife_tool.hover()`'s existing
  validity check — an edge incident to the current `start` vertex is correctly rejected there
  already, reuse that, don't recheck it separately), continuously compute the world position at the
  target's `t` (edge endpoints `p0`/`p1` from `mesh.vertex_position`, same approach as
  `knife_pick._edge_t_3d`, just evaluated as a lerp rather than a closest-point solve since `t` is
  already known) and draw it as a single point, using the point-drawing path already used for vertex
  hover (`GL_POINTS`, `_VERTEX_POINT_SIZE`-style sizing — reuse, don't reinvent).
- Click behaviour is unchanged — `knife_tool.click(target)` already does the right thing
  (`split_edge` at the actual `t` under the cursor). This variant only adds the preview; it does not
  change click semantics.

#### Variant B — Press → Slide → Release

- Mouse-down on a valid edge target starts a slide: preview point appears and follows the mouse
  along the edge (recompute `t` via the existing pick math on each drag event, same as Variant A's
  per-frame computation, just gated by "button held" instead of "hovering").
- Mouse-release while still on a valid target commits: call `knife_tool.click(target)` **at
  release time**, using the target resolved at the release position — not the press position.
- Follow the existing press/drag/release wiring precedent already in `window.py` for
  `press_drag_click` Transform (~1155–1165) for the general shape (state flags, drag-vs-click
  disambiguation reuse via the existing `CLICK_THRESHOLD` mechanism if a plain click without drag
  should still work as a click — confirm this reuse makes sense here or flag if edge cases differ,
  don't silently assume).
- Releasing off any valid target (or with too little movement to count as a real slide, if that
  matters here — flag if unclear) cancels the pending point, no `click()` call, no mutation. This
  mirrors Knife's own "reject" behaviour (`click()` returning `False` is a no-op today) — don't
  invent new rejection UI.

### 2.3 Cancel-before-variant-switch

When `M` is pressed while `focused_family == "knife"` **and** a Knife session is currently active
(`self._knife_tool is not None`), cancel the in-progress Knife session first (same call the Esc
handler already makes: `self._knife_tool.cancel(); self._knife_tool.deactivate(); self._knife_tool =
None`, ~1701–1706) before the slot switches variant — mirroring the existing Transform precedent at
~1536–1541. Do not attempt to translate in-progress state (start vertex, path so far) between
Variant A and B; a clean cancel is the agreed behaviour.

## 3. Explicit constraints

- `src/core/`, `src/viewport/`, `src/mirai/` — do not touch (production, frozen/read-only for this
  task).
- `playground/topology_tools/knife.py` — the state machine's public behaviour (`hover`, `click`,
  `commit`, `cancel`, `undo_step`, `redo_step`) is decided and tested by AD-017. Do not change its
  logic or its return shapes. You may read from it; do not rewrite it.
- `playground/topology_tools/knife_pick.py` — the picking/`t`-resolution math is already correct
  and has a documented history of a subtle bug (see the comment on `_edge_t_3d`'s parameter order).
  Reuse it; do not reimplement the closest-point math from scratch.
- Face hover / cut-into-face — **out of scope for this task.** The `"face"` branch in the dispatch
  (§2.1) should exist as a no-op arm so the dispatch point is ready for it later, but do not build any
  face-interior preview, face highlight geometry, or face-click handling. This mirrors WP-AP-CUT_PLAN
  §C4's existing "out of scope" call on the same question.
- Do not touch the existing `selection`/`transform`/`presentation`/`tweak`/`topology` families'
  behaviour as a side effect.
- Do not fill in, guess, or pre-populate `playground/experiments/knife/decision.md`'s
  Verdict/Pro/Contra fields — those are the Artist's, written after playing.
- Do not choose a "better" variant or default one preferentially in the UI — both should be equally
  reachable via the existing Tab/M mechanism.
- Optics (hover color, preview point size/shape) — use existing constants (`_HOVER_COLOR`,
  `_VERTEX_POINT_SIZE` or equivalent) rather than introducing new ones; Manuel has explicitly said
  visual styling is secondary for this pass.

## 4. Tests

- Headless-testable logic (kind-based dispatch decision, `t`→world-position lerp, cancel-before-
  switch state transitions) gets unit tests under `playground/tests/`, following existing style
  (see `playground/tests/test_ad017_knife_pick.py` for the kind of pure-function test this needs).
- GL/window-routing itself doesn't need headless tests if existing similar code
  (`on_mouse_motion`/`on_mouse_press` wiring) isn't tested that way either — match current practice.
- Run the existing suite (`pytest playground/tests/`, `python -m unittest discover -s tests`, both
  from repo root with `PYTHONPATH=.`) afterward — no regressions, in particular
  `tests/test_ad017_knife*.py` must still pass unchanged since `knife.py`/`knife_pick.py` aren't
  touched.
- Practical verification: run `playground/run.py`, enter Knife (empty selection, `C`), confirm both
  variants show edge hover + a moving/sliding preview point, confirm `Tab`→`M` switches variant and
  cancels an in-progress session cleanly. This practical check is required before calling this done —
  the whole point of this task is visual feedback that can't be confirmed by tests alone.

## 5. When done

Report back: which files were touched/created, what you named the `activation` values and internal
state fields (§2.1/§2.2 deliberately leave naming to you), how you handled the
drag-vs-click-threshold question in Variant B (§2.2), and anything in this brief that turned out
ambiguous or infeasible as written — stop and describe it rather than silently improvising, per M5.
