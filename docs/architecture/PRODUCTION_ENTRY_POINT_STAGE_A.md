# Production Entry Point — Stage A (Window + Camera + Rendering)

**Status:** DONE ✓ — 2026-09-25.

**Basis:** AD-018 §5/§6 (Option B decision + implementation — `RenderMesh`
layout contract, `GLRenderStore`), AD-010 Addendum 2026-09-25 (standalone
Production app, separate from Playground — KEEP). Handoff: "Minimal First
Mirai App, Stage A (Window + Camera + Rendering)" — a Type A implementation
package, not a redecision of either.

Doc placement: a new, plainly-named file rather than forcing this into a
"Gate N" shape (`docs/WP-04_GATE_PLANNING.md` claims Gates 8–12 are
pre-planned but they are not actually defined) or appending to
`SOURCE_ARCHITECTURE.md` (this is a completion record for one bounded
package, not a change to the source-tree map itself).

---

## 1. What this package did

Assembled already-existing, already-verified pieces (`Application`,
`Viewport`, `GLRenderStore`, `OrbitCamera`) into a running window. No new
architecture, no new draw path — AD-018 already decided and built the draw
store; this package closes the one real gap left (`Viewport.render()` was
still a no-op) and wires a thin entry point around it.

**Scope: Stage A only — camera + rendering, no mutation, no tool wiring**
(explicit Artist scope decision, 2026-09-25). Live mutation (MoveTool etc.,
"Stage B") is deferred to a later package and was deliberately not started
here, even though the window now exists and it would be easy to add.

## 2. Changes

### `src/viewport/viewport.py` — `Viewport.render()` fixed

Was a hardcoded `return None` (never updated when `RenderMesh.render(camera)`
was added in AD-018). Now delegates:

```python
def render(self) -> None:
    if self.render_mesh.camera is None:
        return None
    self.render_mesh.render(self.render_mesh.camera)
```

No new parameter — `RenderMesh` already stores the bound camera from
`bind_camera()`, so the facade stays a clean no-arg call (matching `sync()`).
The `camera is None` guard keeps `test_render_is_safe_noop_without_gl_backend`
(pre-existing) and unbound-camera callers safe.

### `src/mirai/application.py` — `Application.init_scene(store_type=...)`

Additive parameter, default unchanged (`TraceStore`):

```python
def init_scene(
    self,
    geometry_type: str = "cube",
    store_type: type[ResourceStore] = TraceStore,
) -> None: ...
```

Passed straight through to `Viewport(...)`. Every existing call site
(`init_scene()`, `init_scene("cube")`) is unaffected — confirmed by the full
existing `ApplicationSceneTests`/`ApplicationDispatchTests` suite staying
green, plus new tests asserting the default store type and that a passed
`store_type` reaches `render_mesh.store`.

`geometry_type` stays `"cube"`-only, as scoped — no OBJ loading wired into
`Application.init_scene()` here (`AD-018`'s verification scripts already
prove OBJ works at the `RenderMesh` level, just not through `Application`
yet; that gap is left named, not closed).

### `src/main.py` — new entry point

Resolves Q6 for Stage A. Chosen path: `src/main.py`, per the handoff's
suggested default (`README.md` "Current status" already described this as
the intended location, and it reads naturally as "the production app" next
to `src/core/`, `src/mirai/`, `src/viewport/`).

Thin by design — construction and event wiring only:

- Opens a `pyglet.window.Window` **before** `Application.init_scene(store_type=GLRenderStore)`.
  This ordering is load-bearing, not stylistic: `GLRenderStore` compiles its
  shader lazily "on first use" (see its module docstring), and that first
  use happens inside `init_scene()`'s camera binding. pyglet's GL context is
  created together with its first `Window` — building `Application` and
  calling `init_scene(store_type=GLRenderStore)` before any window exists
  raised `GLException: Invalid operation` on `glBindVertexArray` in this
  environment. Caught during the practical viewport test (§5 below), fixed
  by reordering; not a change to `GLRenderStore`/`RenderMesh`/AD-018 itself.
- `on_resize` → `viewport.on_camera_changed(aspect)`.
- `on_mouse_drag`: right-drag → `camera.orbit(...)`, middle-drag →
  `camera.pan(...)`, both from raw pixel deltas — the proven Playground
  pattern (`playground/window.py::_camera_navigate`, read as a technical
  reference only, no import, per AD-010). Matches the `ORBIT`/`PAN` mouse
  defaults in `mirai.interaction.bindings.build_default_bindings()` (RIGHT /
  MIDDLE). Deliberately NOT routed through `Application.dispatch_command()`
  — it does not handle `ORBIT`/`PAN`/`ZOOM` today, and wiring continuous
  drag gestures through the discrete command/`BindingSet` system is a
  separate, unresolved design question this package does not open.
- `on_mouse_scroll` → `camera.dolly(...)` directly, same reasoning.
- `mirai.pyglet_input`'s `Input` translation was deliberately NOT used here
  — it is built for discrete key/button events, not continuous per-frame
  drag deltas; adding that layer for this one interaction would not fit.
  This was a deliberate choice, not an oversight.
- `on_draw`: clear → `viewport.sync()` → `viewport.render()`.
- `pyglet.clock.schedule_interval(...)` calls `app.update_viewport(dt)` once
  per frame, independent of camera events — keeps the door open for a
  future Stage B without changing this package.
- Esc/Q closes the window (existing repo convention, e.g.
  `experiments/ad018_gl_render_store_verification/run_visible.py`).

No new business logic in this file — every call is into
`Application`/`Viewport`/`OrbitCamera`, all of which stay as documented.

## 3. Not in scope (unchanged from the handoff)

- No mutation, no tool activation, no `dispatch_command()` for
  MOVE/ROTATE/SCALE (Stage B — explicitly deferred).
- Q7 (tool → viewport notification wiring) — stays open.
- OBJ loading through `Application.init_scene()` — cube only.
- Selection visualization, wireframe/display-mode switching, gizmo, HUD —
  untouched.
- No edits to `AD-018-PRODUCTION-DRAW-BINDING.md` §1–§5 (append-only
  elsewhere, not touched at all by this package).
- No imports from or edits to `playground/`.
- `BindingSet`/`dispatch_command` still do not handle `ORBIT`/`PAN`/`ZOOM`
  — not resolved here.

## 4. Architecture contracts — confirmed intact

- `src/viewport` still does not import from `src.mirai` (checked: only
  stdlib + `core` imports in `viewport.py`/`render_mesh.py`).
- `Application` stays window-free in its own module — all window/event
  handler code lives in `src/main.py`.
- No change to `RenderMesh`, `ResourceStore`, `GLRenderStore`, or the
  AD-018 contract itself — `Viewport.render()`'s fix only changes what the
  facade method's body does, not any of those classes.

## 5. Tests

Baseline (this package's starting point, re-verified before changing
anything, not assumed from AD-018's own completion record):

```
$ python3 -m pytest tests/ -q --ignore=tests/test_extrude_tool.py
560 passed
$ xvfb-run -a python3 -m pytest playground/tests -q
843 passed
```

After:

```
$ python3 -m pytest tests/ -q --ignore=tests/test_extrude_tool.py
567 passed
$ xvfb-run -a python3 -m pytest playground/tests -q
843 passed
```

567 − 560 = 7 new tests, all headless/GL-optional:

- `tests/test_viewport_facade.py` — 2 new tests: `Viewport.render()` is a
  no-op when no camera is bound (`camera is None` guard) and delegates to
  `render_mesh.render(bound_camera)` when one is (spy on `render_mesh.render`,
  no real GL context needed for this one).
- `tests/test_application.py` — 3 new tests: `init_scene()`'s default store
  type is `TraceStore` (unaffected default), a passed `store_type` reaches
  `render_mesh.store`, and the camera binding (`render_mesh.camera is
  app.camera`) still holds with a non-default store type.
- `tests/test_main_entry_point.py` (new file) — 2 tests, real GL context via
  the same `gl_window` fixture pattern as `tests/test_gl_render_store.py`
  (skips cleanly without one): `Application` + `init_scene(store_type=
  GLRenderStore)` + `viewport.render()` produces a non-background
  framebuffer through the real Production path (not `RenderMesh` directly —
  that path is already covered by `test_gl_render_store.py`), and the V02
  camera invariant (`geometry_uploads` stays 0, `resource_ids()` unchanged
  across 20 orbit steps) holds through `Application`/`Viewport`.

`playground/tests` (843) — zero edits, zero regressions, confirmed via
`xvfb-run -a python3 -m pytest playground/tests -q` before and after.

**Environment note:** this sandbox had neither `pyglet` nor `pytest`
installed, and `pyglet`'s headless EGL backend needed `libegl-mesa0`/
`libgl1-mesa-dev` (both installed via `apt-get`, plus `pyglet`/`pytest` via
`pip`) before any GL-backed test or the entry point itself could run. Once
installed, real GL context creation worked even without `xvfb-run` (EGL
headless), and both with and without it gave identical results — reported
for transparency, not because it changes what passed.

## 6. Practical viewport test (handoff §8)

`experiments/stage_a_entry_point_verification/run_headless_evidence.py`
(throwaway, not a Production entry point) drives the exact same
construction `src/main.py::main()` uses — window first, then
`Application()` + `init_scene(store_type=GLRenderStore)` — orbits the camera
for 30 frames under Xvfb, and writes a screenshot:

```
$ xvfb-run -a python3 experiments/stage_a_entry_point_verification/run_headless_evidence.py
resource_ids before orbit: {'positions': 1, 'normals': 2, 'indices': 3, 'highlight_flags': 4, 'camera_uniforms': 5}
resource_ids after 30x orbit: {'positions': 1, 'normals': 2, 'indices': 3, 'highlight_flags': 4, 'camera_uniforms': 5}
resource_ids unchanged: True
geometry_uploads: 0
screenshot written to .../stage_a_entry_point_verification/stage_a_render.png
```

The screenshot (kept out of git — see §8 below, described here instead)
shows the default cube, shaded (directional light, smooth normals), in the
same style as AD-018's `head_mesh_render.png`, confirming the draw is real
GL through the real `Application` → `Viewport` → `GLRenderStore` path, not a
parallel path or a bypass of the facade.

`src/main.py` itself was also run directly under Xvfb for 5 seconds
(`timeout 5 xvfb-run -a python3 src/main.py`) with no window-creation or
draw errors before the timeout killed it — `pyglet.app.run()` blocks
forever by design, so this is the expected termination, not a failure.

## 7. Findings

- **Window-before-`init_scene(store_type=GLRenderStore)` ordering is
  load-bearing**, not a style choice (see §2 above) — caught live during
  this package's own practical viewport test, not assumed from AD-018's
  scripts (which already created the window first, but that ordering
  constraint was not stated anywhere before now). Documented in
  `src/main.py`'s own comment so a future edit does not silently reorder it.
- **`OrbitCamera` has no separate "zoom" method** — the handoff's §1.10/§4.4
  wording ("mouse wheel zoom method") refers to the existing `dolly()`
  (Playground's own convention, `playground/window.py::on_mouse_scroll`);
  no new camera method was needed or added.
- **No changes were needed to `TraceStore`, `GLRenderStore`, `RenderMesh`,
  or any `core/` file.** The entire package touches exactly the files this
  doc's §2 lists, plus the throwaway evidence script and this record.

## 8. `git diff --stat` scope check

Touched: `src/viewport/viewport.py` (the fix), `src/mirai/application.py`
(the additive parameter), `src/main.py` (new entry point),
`tests/test_viewport_facade.py`, `tests/test_application.py`,
`tests/test_main_entry_point.py` (new file), `README.md` ("Current status"),
this completion record, and a new throwaway evidence directory
(`experiments/stage_a_entry_point_verification/`, script only — see below).
Nothing outside this list, no edits to `playground/`, no edits to any other
`experiments/` directory, no edits to `AD-018-PRODUCTION-DRAW-BINDING.md`.

The evidence screenshot (`experiments/stage_a_entry_point_verification/
stage_a_render.png`, ~28 KB) was generated locally but is **not committed**
— kept out of git per handoff §8 ("do NOT commit large binary screenshots
into `src/`; fine to keep the screenshot out of git and just describe it").
It is not under `src/` in any case; it was left out of the commit entirely
to keep the diff text-only, and is described in §6 above instead.

## 9. Definition of Done — status

- [x] `src/main.py` opens a window showing the default cube via the real
      Production draw path
- [x] Orbit (right-drag), pan (middle-drag), zoom (wheel) all wired to the
      real `OrbitCamera` methods (not exercised by an automated GUI test —
      no display/input-injection harness in this environment; verified by
      code inspection against `playground/window.py`'s proven pattern and
      by the practical viewport test driving the same camera calls
      programmatically)
- [x] Resize updates aspect correctly (`on_resize` → `on_camera_changed(aspect)`,
      same call `_push_camera_change()` uses elsewhere — no distortion path)
- [x] `Viewport.render()` fixed to delegate to `RenderMesh.render()`,
      covered by 2 new tests
- [x] `Application.init_scene(store_type=...)` added, additive, existing
      call sites/tests unaffected (confirmed, not assumed)
- [x] Live camera invariant demonstrated through the real entry-point
      construction path (`geometry_uploads` == 0, `resource_ids()`
      unchanged across 20 orbit steps) — §6 above
- [x] No mutation, no tool activation, no `playground/` imports or edits
- [x] Full existing test suite: 100% green, exact before/after numbers
      reported (560→567 in `tests/`, 843→843 in `playground/tests`)
- [x] `README.md` "Current status" updated
- [x] Completion record written (this document)
- [x] `git diff --stat` reviewed and reported (§8 above)
