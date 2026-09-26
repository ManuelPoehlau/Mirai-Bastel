"""Production entry point — Stage B, Slice B1 (Head mesh + camera framing).

Handoff: "WP-06 — Slice B1: Head mesh as default scene + camera framing"
(2026-09-26), building on Stage A ("Minimal First Mirai App, Stage A
(Window + Camera + Rendering)", AD-018 §5/§6, AD-010 Addendum 2026-09-25).
Opens a standalone `pyglet` window that shows the default scene through the
real Production draw path:

    Application -> Viewport -> GLRenderStore -> RenderMesh.render(camera)

Scope (binding, see the handoff):
- Camera navigation only (orbit/pan/zoom) — no mutation, no tool
  activation, no `dispatch_command()` for MOVE/ROTATE/SCALE. Live
  mutation (e.g. MoveTool) is explicitly deferred to a later slice and is
  NOT started here even though the window now exists.
- Default scene is now the head basemesh (`examples/meshes/
  head_basemesh.obj`), loaded through `Application.init_scene("obj",
  obj_path=...)` (WP-06 B1, E2/E4) and framed once via
  `Application.frame_scene()` (E3) before the first camera-change push.
  An optional single CLI argument overrides this: a path to an `.obj`, or
  the literal `cube`. A load failure prints one line to stderr and falls
  back to the cube; the window still opens.
- No imports from `playground/` (AD-010 Addendum — Playground stays a
  separate, untouched app).

This file is intentionally thin: construction and event wiring only, no
new business logic. All state lives in `Application`/`Viewport`
(`src/mirai/application.py`, `src/viewport/viewport.py`), which stay
window-free.

Camera input (Stage A handoff §4.4, deliberate choice, not an oversight):
mouse drag/scroll deltas are read directly from the raw pyglet event
arguments and passed straight to `OrbitCamera.orbit()`/`.pan()`/`.dolly()`
— the proven Playground pattern (`playground/window.py::
_camera_navigate`, technical reference only, no import). `mirai.
pyglet_input`'s `Input` translation is built for discrete key/button
events, not continuous per-frame drag deltas, so it is not used for this
specific interaction. `Application.dispatch_command()` does not handle
ORBIT/PAN/ZOOM today (`src/mirai/interaction/bindings.py`) — routing
continuous drag gestures through the discrete command system is a
separate, unresolved design question, not opened here.

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
from pyglet.window import mouse as _mouse  # noqa: E402

from mirai.application import Application  # noqa: E402
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
    if arg == "cube":
        app.init_scene("cube", store_type=GLRenderStore)
    else:
        obj_path = Path(arg) if arg is not None else _DEFAULT_HEAD_OBJ
        try:
            app.init_scene("obj", obj_path=obj_path, store_type=GLRenderStore)
        except Exception as exc:
            print(f"Failed to load '{obj_path}': {exc}", file=sys.stderr)
            app.init_scene("cube", store_type=GLRenderStore)

    app.frame_scene()

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
