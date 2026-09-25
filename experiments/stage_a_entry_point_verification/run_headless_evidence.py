"""Throwaway Xvfb evidence script for the Stage A entry point
(`src/main.py`, handoff "Minimal First Mirai App, Stage A").

Drives the exact same construction `src/main.py::main()` uses
(`Application()` -> window -> `init_scene(store_type=GLRenderStore)`),
orbits the camera for 30 frames, then writes a screenshot and prints the
V02 camera invariant (`geometry_uploads` unchanged while orbiting) — the
practical viewport test named in the handoff's §8, same pattern as
`experiments/ad018_gl_render_store_verification/run.py`.

Not a Production entry point, not committed evidence of Artist validation
(M3/M4) — a technical smoke check only.

Usage:
    xvfb-run -a python3 experiments/stage_a_entry_point_verification/run_headless_evidence.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pyglet  # noqa: E402

from mirai.application import Application  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402

OUT_PATH = Path(__file__).resolve().parent / "stage_a_render.png"


def main() -> None:
    # Window before init_scene(): GLRenderStore needs an active GL context
    # for its first allocate() — see `src/main.py`'s own ordering comment.
    window = pyglet.window.Window(
        width=800, height=600, caption="Mirai Stage A smoke", visible=True
    )

    app = Application()
    app.init_scene(store_type=GLRenderStore)

    def push_camera() -> None:
        app.viewport.on_camera_changed(window.width / window.height)

    push_camera()
    app.viewport.sync()
    app.viewport.render()

    frame_count = [0]

    @window.event
    def on_draw():
        from pyglet import gl

        gl.glClearColor(0.05, 0.05, 0.08, 1.0)
        window.clear()
        app.viewport.sync()
        app.viewport.render()

    # Captured AFTER the first sync()/render(), so camera_uniforms is
    # already allocated - an apples-to-apples comparison with `ids_after`.
    ids_before = app.viewport.resource_ids()

    def tick(dt):
        app.update_viewport(dt)
        app.camera.orbit(0.05, 0.01)
        push_camera()
        frame_count[0] += 1
        if frame_count[0] == 30:
            window.switch_to()
            on_draw()
            from pyglet import gl

            gl.glFinish()
            pyglet.image.get_buffer_manager().get_color_buffer().save(str(OUT_PATH))
            ids_after = app.viewport.resource_ids()
            print("resource_ids before orbit:", ids_before)
            print("resource_ids after 30x orbit:", ids_after)
            print("resource_ids unchanged:", ids_after == ids_before)
            print(
                "geometry_uploads:",
                app.viewport.benchmark_counters.get("geometry_uploads", 0),
            )
            print("screenshot written to", OUT_PATH)
            window.close()

    pyglet.clock.schedule_interval(tick, 1 / 60.0)
    pyglet.app.run()


if __name__ == "__main__":
    main()
