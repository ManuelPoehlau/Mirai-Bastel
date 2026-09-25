"""Production entry point — Stage A (Window + Camera + Rendering).

Handoff: "Minimal First Mirai App, Stage A (Window + Camera + Rendering)"
(AD-018 §5/§6, AD-010 Addendum 2026-09-25). Opens a standalone `pyglet`
window that shows the default scene through the real Production draw path:

    Application -> Viewport -> GLRenderStore -> RenderMesh.render(camera)

Scope (binding, see the handoff):
- Camera navigation only (orbit/pan/zoom) — no mutation, no tool
  activation, no `dispatch_command()` for MOVE/ROTATE/SCALE. Stage B
  (live mutation, e.g. MoveTool) is explicitly deferred to a later
  package and is NOT started here even though the window now exists.
- Cube geometry only (`Application.init_scene()` stays "cube"-only for
  this package; OBJ loading through `Application` is a separate, later
  concern — see AD-018 §5 handoff §4.2).
- No imports from `playground/` (AD-010 Addendum — Playground stays a
  separate, untouched app).

This file is intentionally thin: construction and event wiring only, no
new business logic. All state lives in `Application`/`Viewport`
(`src/mirai/application.py`, `src/viewport/viewport.py`), which stay
window-free.

Camera input (handoff §4.4, deliberate choice, not an oversight): mouse
drag/scroll deltas are read directly from the raw pyglet event arguments
and passed straight to `OrbitCamera.orbit()`/`.pan()`/`.dolly()` — the
proven Playground pattern (`playground/window.py::_camera_navigate`,
technical reference only, no import). `mirai.pyglet_input`'s `Input`
translation is built for discrete key/button events, not continuous
per-frame drag deltas, so it is not used for this specific interaction.
`Application.dispatch_command()` does not handle ORBIT/PAN/ZOOM today
(`src/mirai/interaction/bindings.py`) — routing continuous drag gestures
through the discrete command system is a separate, unresolved design
question, not opened here.

Usage:
    python3 src/main.py

Esc/Q closes the window (existing convention, e.g.
`experiments/ad018_gl_render_store_verification/run_visible.py`).
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent
_ROOT = _SRC.parent
for _p in (str(_SRC), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pyglet  # noqa: E402
from pyglet.window import key as _key, mouse as _mouse  # noqa: E402

from mirai.application import Application  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402


def main() -> None:
    # Window before init_scene(): GLRenderStore needs an active GL context
    # for its first `allocate()` (its shader is compiled lazily "on first
    # use", see `viewport.gl_render_store` module docstring) — pyglet only
    # creates that context together with its first Window.
    window = pyglet.window.Window(
        width=1024, height=768, resizable=True, caption="Mirai — Stage A"
    )

    app = Application()
    app.init_scene(store_type=GLRenderStore)

    def _push_camera_change() -> None:
        aspect = window.width / window.height if window.height else 1.0
        app.viewport.on_camera_changed(aspect)

    # Initial aspect so the first frame is not distorted (before any resize
    # or camera event has fired).
    _push_camera_change()

    @window.event
    def on_resize(width: int, height: int):
        _push_camera_change()
        return pyglet.event.EVENT_HANDLED

    @window.event
    def on_mouse_drag(x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int):
        # Right-drag = orbit, middle-drag = pan — matches the ORBIT/PAN
        # defaults in `mirai.interaction.bindings.build_default_bindings()`.
        # Raw pixel deltas straight to the camera (handoff §4.4), not routed
        # through `Application.dispatch_command()`.
        if buttons & _mouse.RIGHT:
            app.camera.orbit(-dx * 0.005, -dy * 0.005)
            _push_camera_change()
        elif buttons & _mouse.MIDDLE:
            app.camera.pan(dx, dy, window.width, window.height)
            _push_camera_change()

    @window.event
    def on_mouse_scroll(x: int, y: int, scroll_x: float, scroll_y: float):
        app.camera.dolly(0.9 if scroll_y > 0 else 1.1)
        _push_camera_change()

    @window.event
    def on_key_press(symbol: int, modifiers: int):
        if symbol in (_key.ESCAPE, _key.Q):
            window.close()

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
