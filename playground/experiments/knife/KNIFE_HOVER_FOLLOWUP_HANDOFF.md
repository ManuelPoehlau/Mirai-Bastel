# WP-AP-CUT — Knife Hover Feedback Follow-up: Edge Locking, Vertex-Kind Release, Start-Vertex Highlight (for Claude Code)

**Status:** Ready for implementation
**Date:** 2026-09-23
**Mode (M5):** Production — the fixes below are decided (Artist play-test findings from commit
`324c2e0`). **BUILD must not claim new knowledge:** if something here turns out ambiguous or
infeasible as written, stop, record it as an open question, do not silently improvise.
**Authority:** This brief, agreed with Manuel in chat on 2026-09-23, following play-testing of
`324c2e0` (the base Knife hover/Variant A/B implementation from
`KNIFE_HOVER_CLAUDE_CODE_HANDOFF.md`).
**Related:** `playground/experiments/knife/KNIFE_HOVER_CLAUDE_CODE_HANDOFF.md` (base task, already
implemented — this brief only covers the three follow-up fixes below, do not redo the base task).
AD-017 (`docs/architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md`).

---

## 0. Context — what changed since the base handoff

`324c2e0` implemented the kind-based Knife hover dispatch and the `knife` Family with Variant A
(Live Preview) and Variant B (Press-Slide-Release), per the base handoff. Manuel play-tested it and
found three related issues, all in `playground/window.py`, all confirmed by reading the current
`main` branch (line numbers below are current, not from the base handoff).

## 1. Findings

### F1 — Variant B loses the grabbed edge when the cursor strays

`on_mouse_drag`'s Variant B branch (~994–1024) and the Variant B release handler (~1214–1231) both
call `knife_pick(camera, mesh, x, y, ...)` **fresh on every event**, from the raw cursor position —
i.e. a full nearest-vertex/nearest-edge/face/outside re-resolution every frame. There is no state
remembering which specific edge was grabbed at mouse-down (only the generic `_knife_hover_last_target`
dict, which is itself overwritten every frame from the fresh pick).

Effect: as soon as the cursor visually leaves the edge's screen-space hit region, the fresh pick
returns a different element (or `face`/`outside`), `hover_result["valid"]` goes `False`, and
`_clear_knife_hover_vbos()` removes the highlight/preview entirely. Compare to Silo, where grabbing
an edge locks it — subsequent cursor movement, however far from the geometry, keeps projecting onto
that edge's line until release.

### F2 — Release silently does nothing when the slide is near an edge endpoint

`knife_pick()` (`playground/topology_tools/knife_pick.py`) already snaps `t` near an edge's ends
(`ENDPOINT_THRESHOLD`) to a `vertex` target instead of an `edge` target — this is correct, existing
behavior. But the Variant B release handler (~1225) only acts when the resolved target is `kind ==
"edge"`:

```python
if target.get("kind") == "edge" and hover_result.get("valid", False):
    accepted = self._knife_tool.click(target)
```

When the release position is close enough to an endpoint that `knife_pick()` returns `kind ==
"vertex"` instead, this condition is `False` and the whole block is skipped — `hover_result["valid"]`
is in fact `True` for vertex targets (`KnifeTool.hover()`'s vertex branch always returns
`valid: True`), so nothing here is being correctly rejected; the cut is just never attempted.
Expected (Manuel, confirmed): release near the threshold should snap to that vertex and connect to
it exactly as a direct vertex click would — same as `KnifeTool.click()` already handles for
`kind == "vertex"` targets (sets `start` on first click, connects `start` → vertex otherwise).

### F3 — Vertex hover draws with the wrong GL primitive; no persistent start-vertex highlight

Two separate problems, same neighborhood:

1. **Wrong primitive.** In the general Knife hover dispatch (`on_mouse_motion`, ~1350–1357), a
   `kind == "vertex"` hover builds a `GL_POINTS` vertex list — but stores it in
   `self._vlist_knife_hover_edge`, the same slot used for the edge-highlight `GL_LINES` list. The
   draw pass in `on_draw` (~2191–2192) always calls
   `self._vlist_knife_hover_edge.draw(gl.GL_LINES)` on that slot regardless of what was actually
   built into it. A single point drawn as `GL_LINES` does not render a visible line — so vertex hover
   during Knife is effectively invisible today, independent of the F1/F2 issues above.
2. **No persistent start-vertex indicator.** `KnifeTool.hover()` already returns the current session
   start (`hover_result["start"]`, see `knife.py` ~73–91) on every call — but `window.py` never reads
   or draws it. Once a first click sets a start vertex, there is currently no visual trace of it once
   the cursor moves away — it's only coincidentally visible if the cursor happens to hover it again.

## 2. Required fixes

### 2.1 Lock the grabbed edge for the duration of a Variant B slide (fixes F1, enables F2)

- On arm (mouse-down, ~950–954), in addition to the existing state, store the grabbed edge id itself,
  e.g. `self._knife_slide_edge_id = eid`.
- In `on_mouse_drag`'s Variant B branch and in the release handler, **stop calling `knife_pick()`**
  while a slide is armed. Instead, project the current cursor ray directly onto the locked edge:
  reuse `knife_pick.py`'s `_edge_t_3d(origin, direction, p0, p1)` (via `camera.screen_to_ray(x, y,
  width, height)` and `mesh.vertex_position(...)` for the locked edge's two endpoints — same inputs
  `knife_pick()` already assembles, just against a fixed edge instead of the nearest one). This
  function already clamps `t` to `[0, 1]`, so the projection is always defined regardless of cursor
  distance from the mesh.
- Apply the **same** `ENDPOINT_THRESHOLD` snap `knife_pick()` uses (import/reuse the constant, don't
  redefine it) to turn the projected `t` into either `{"kind": "edge", "edge_id": locked_eid, "t":
  t}` or `{"kind": "vertex", "vertex_id": va_or_vb}` — this is what makes F2's fix meaningful during
  the slide itself, not just at a single release instant.
- Update the live preview (drag) and the release logic to use this locked-projection target instead
  of a fresh `knife_pick()` result. `KnifeTool.hover()` / `.click()` calls stay exactly as they are —
  only what target dict gets passed to them changes.
- Preview while snapped to an endpoint should visually become a vertex highlight (see §2.3) instead
  of the mid-edge point, so the Artist can see the snap before releasing.

### 2.2 Accept vertex-kind targets on Variant B release (fixes F2)

- Change the release condition (~1225) to accept both kinds:
  ```python
  if target.get("kind") in ("edge", "vertex") and hover_result.get("valid", False):
      accepted = self._knife_tool.click(target)
  ```
- No change needed in `knife.py` — `KnifeTool.click()` already handles `kind == "vertex"` correctly
  (first click sets `start`, subsequent click connects `start` → vertex). This is purely a
  window.py-side gating fix.

### 2.3 Fix vertex-hover rendering + add persistent start-vertex highlight (fixes F3)

- Give the vertex-hover point its own VBO slot, separate from the edge-highlight line slot (don't
  keep overloading `_vlist_knife_hover_edge` for two different primitive types — pick clear, distinct
  names, e.g. `_vlist_knife_hover_vertex` for the hover point vs. keeping
  `_vlist_knife_hover_edge` strictly for `GL_LINES` edge highlights). Draw it with `gl.GL_POINTS`,
  reusing the same point styling already used for ordinary vertex hover (`_VERTEX_POINT_SIZE`,
  `_HOVER_COLOR`) — don't invent new constants.
- Add a **separate, persistent** start-vertex VBO (e.g. `_vlist_knife_start`) that is *not* cleared
  by `_clear_knife_hover_vbos()` (that function's clear-every-motion-frame lifecycle is for ephemeral
  hover state, not this). Rebuild it whenever `hover_result["start"]` changes from what was last
  drawn (track this the same way `_knife_hover_last_target` already tracks the hover target) — i.e.
  after every `click()` that changes `_start`, the next `hover()` call's returned `start` value picks
  it up naturally, no separate signal needed from `knife.py`.
- Style it like a **selected** vertex, not a hovered one — reuse `_SELECTION_COLOR` /
  `_VERTEX_POINT_SIZE` (the same combination already used for `_vlist_sel_verts`), not
  `_HOVER_COLOR`. This is explicitly "for now" (Manuel's words) — a placeholder distinct look, not a
  final design decision.
- Clear this start-vertex VBO wherever `self._knife_tool` is set back to `None` (commit ~1861–1866,
  cancel ~1877–1882, variant-switch cancel ~1707–1715) — same places `_clear_knife_hover_vbos()` is
  already called from, just add the start-VBO cleanup alongside it there (or fold it into
  `_clear_knife_hover_vbos()` itself if you prefer one call site — your call, just make sure all
  three exit paths actually clear it).
- Draw order: draw the persistent start-vertex highlight and the ephemeral hover highlight as
  separate passes in `on_draw`, both still within the existing "Knife Hover" section (~2178 onward) —
  no need to invent a new section.

## 3. Explicit constraints

- Same as the base handoff: `src/core/`, `src/viewport/`, `src/mirai/` untouched;
  `playground/topology_tools/knife.py` and `knife_pick.py` logic untouched (only *read* from, e.g.
  `hover_result["start"]`, `_edge_t_3d`, `ENDPOINT_THRESHOLD` — reuse, don't fork or reimplement).
- Variant A is unaffected by F1/F2 (those are Variant-B-specific, since Variant A never "arms" a
  slide — it re-picks every frame by design, which is correct for Variant A). Do not change Variant
  A's hover behavior. F3's vertex-hover-primitive fix and start-vertex highlight, however, apply to
  **both** variants — they're part of the shared kind-based dispatch (§2.1 of the base handoff), not
  Variant-B-only code.
- Do not touch `experiments/tweak/`, `experiments/transform/`, or any other family as a side effect.
- Colors/sizes: reuse existing constants (`_HOVER_COLOR`, `_SELECTION_COLOR`, `_VERTEX_POINT_SIZE`)
  as specified above — do not introduce new visual constants for this follow-up.

## 4. Tests

- Headless-testable: the locked-edge projection + endpoint-threshold-snap logic (§2.1) should be
  extractable as a small pure function (edge endpoints + ray → target dict) and unit-tested the same
  way `knife_pick()` itself is tested (see `playground/tests/test_ad017_knife_pick.py`) — ideally
  sharing the threshold constant/logic with `knife_pick()` rather than duplicating test coverage for
  two copies of the same rule.
- Run the full existing suite afterward (`pytest playground/tests/`,
  `python -m unittest discover -s tests`, both from repo root with `PYTHONPATH=.`) — no regressions,
  `tests/test_ad017_knife*.py` unchanged and passing.
- Practical verification (required, per the base handoff's same reasoning — this is visual/feel
  feedback that can't be confirmed by unit tests alone): in `playground/run.py`, Variant B — grab an
  edge, drag the cursor far off the mesh, confirm the edge/preview stays locked; slide near an
  endpoint, confirm it visually snaps to the vertex; release there, confirm it connects to that
  vertex. Then confirm plain vertex hover (both variants) now actually shows a highlight, and that a
  session's start vertex stays visibly marked (selected-style) after the cursor moves away, across
  multiple clicks, until commit/cancel.

## 5. When done

Report back: which files were touched, the exact VBO/state field names you used (§2.1/§2.3
deliberately leave naming to you, as before), whether the locked-edge projection ended up sharing
code with `knife_pick()` or duplicating the threshold constant only, and anything here that turned
out ambiguous or infeasible as written.
