"""Production entry point — Stage B, Slices B1, B2 + B2b.

Handoffs: "WP-06 — Slice B1: Head mesh as default scene + camera framing",
"WP-06 — Slice B2: Navigation per Artist Truth + vertex selection,
Modifier variant" and "WP-06 — Slice B2b: Selected vertex as round point +
vertex hover" (2026-09-26), building on Stage A (AD-018 §5/§6, AD-010
Addendum 2026-09-25). Opens a standalone `pyglet` window that shows the
default scene through the real Production draw path:

    Application -> Viewport -> GLRenderStore -> RenderMesh.render(camera)

Scope (binding, see the handoffs):
- Default scene is the head basemesh (`examples/meshes/head_basemesh.obj`),
  loaded through `Application.init_scene("obj", obj_path=...)` and framed
  once via `Application.frame_scene()`. An optional single CLI argument
  overrides this: a path to an `.obj`, or the literal `cube`. A load
  failure prints one line to stderr and falls back to the cube.
- Navigation and vertex selection (B2) go through the bindings:
  pyglet event -> `mirai.pyglet_input` -> `Application.pointer_*` ->
  `BindingSet` + `PointerGestures` (click vs. drag, AD-019). Orbit =
  Alt+LMB drag, Pan = Alt+Shift+LMB drag, Zoom = wheel; LMB click =
  select (Shift add, Ctrl remove, Alt toggle). RMB/MMB are unbound.
- Selected vertices are drawn as small round yellow points by
  `GLPointOverlay` on top of the mesh; the mesh itself is no longer tinted
  (Slice B2b, AD-018 §7 addendum). The vertex under the cursor shows a
  slightly larger, translucent pale-yellow hover point (`PROVISIONAL`):
  `on_mouse_motion`/`on_mouse_leave` -> `Application.pointer_motion`/
  `pointer_leave`.
- No mutation, no tool activation (Move etc. is a later slice).
- No imports from `playground/` (AD-010 Addendum).

This file is intentionally thin: construction and event translation only,
no business logic. All state and execution live in `Application`/`Viewport`
(`src/mirai/application.py`, `src/viewport/viewport.py`), which stay
window-free.

Usage:
    python3 src/main.py                       # head basemesh (default)
    python3 src/main.py cube                   # cube
    python3 src/main.py path/to/mesh.obj       # a different .obj

The window's X button closes it (WP-06 B1, Artist decision A3, 2026-09-26)
— there is no quit hotkey.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent
_ROOT = _SRC.parent
for _p in (str(_SRC), str(_ROOT), str(_ROOT / "examples")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pyglet  # noqa: E402

from mirai.application import Application  # noqa: E402
from mirai.pyglet_input import mouse_from_pyglet, wheel_from_pyglet  # noqa: E402
from viewport.gl_point_overlay import GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402

_DEFAULT_HEAD_OBJ = _ROOT / "examples" / "meshes" / "head_basemesh.obj"


def main() -> None:
    # Window before init_scene(): GLRenderStore needs an active GL context
    # for its first `allocate()` (its shader is compiled lazily "on first
    # use", see `viewport.gl_render_store` module docstring) — pyglet only
    # creates that context together with its first Window.
    window = pyglet.window.Window(
        width=1024, height=768, resizable=True, caption="Mirai — Stage B"
    )

    app = Application()

    arg = sys.argv[1] if len(sys.argv) > 1 else None
    gl_types = {"store_type": GLRenderStore, "point_overlay_type": GLPointOverlay}
    if arg == "cube":
        app.init_scene("cube", **gl_types)
    else:
        obj_path = Path(arg) if arg is not None else _DEFAULT_HEAD_OBJ
        try:
            app.init_scene("obj", obj_path=obj_path, **gl_types)
        except Exception as exc:
            print(f"Failed to load '{obj_path}': {exc}", file=sys.stderr)
            app.init_scene("cube", **gl_types)

    app.frame_scene()

    # Initial size/aspect so the first frame is not distorted (before any
    # resize or camera event has fired).
    app.set_viewport_size(window.width, window.height)

    @window.event
    def on_resize(width: int, height: int):
        app.set_viewport_size(window.width, window.height)
        return pyglet.event.EVENT_HANDLED

    @window.event
    def on_mouse_press(x: int, y: int, button: int, modifiers: int):
        inp = mouse_from_pyglet(button, modifiers)
        if inp is not None:
            app.pointer_press(inp)

    @window.event
    def on_mouse_drag(x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int):
        app.pointer_drag(dx, dy)

    @window.event
    def on_mouse_release(x: int, y: int, button: int, modifiers: int):
        inp = mouse_from_pyglet(button, modifiers)
        if inp is not None:
            app.pointer_release(inp.value, x, y)

    @window.event
    def on_mouse_motion(x: int, y: int, dx: int, dy: int):
        app.pointer_motion(x, y)

    @window.event
    def on_mouse_leave(x: int, y: int):
        app.pointer_leave()

    @window.event
    def on_mouse_scroll(x: int, y: int, scroll_x: float, scroll_y: float):
        inp = wheel_from_pyglet(scroll_y)
        if inp is not None:
            app.pointer_scroll(inp)

    @window.event
    def on_draw():
        from pyglet import gl

        gl.glClearColor(0.05, 0.05, 0.08, 1.0)
        window.clear()
        app.viewport.sync()
        app.viewport.render()

    def _tick(dt: float) -> None:
        # Keeps `viewport.sync()` running once per frame even without a
        # camera event (Stage B hook — no behavior change for this package).
        app.update_viewport(dt)

    pyglet.clock.schedule_interval(_tick, 1 / 60.0)
    pyglet.app.run()


if __name__ == "__main__":
    main()
