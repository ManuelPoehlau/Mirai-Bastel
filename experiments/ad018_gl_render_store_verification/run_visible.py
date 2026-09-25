"""Same verification as `run.py`, but with a visible window for Manu's PC
(real-hardware confirmation, same pattern as the draw-binding spike's
`run.py`). Not required for this package to be considered done (AD-018 §5
handoff §8) - optional, real-GPU sanity check.

Usage (no Xvfb, a real display):
    python3 experiments/ad018_gl_render_store_verification/run_visible.py

Orbits the camera automatically for a few seconds, then closes. Esc/Q to
quit early.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT / "examples"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pyglet  # noqa: E402
from pyglet.window import key  # noqa: E402

from core import Selection  # noqa: E402
from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.overlay import SelectionOverlay  # noqa: E402
from viewport.render_mesh import RenderMesh  # noqa: E402

MESH_PATH = _ROOT / "examples" / "meshes" / "head_basemesh.obj"


def main() -> None:
    window = pyglet.window.Window(width=800, height=600, caption="AD-018 GLRenderStore")

    mesh = build_core_scene_from_obj(str(MESH_PATH)).mesh
    selection = Selection()
    overlay = SelectionOverlay(selection)
    rm = RenderMesh(mesh, overlay=overlay, store_type=GLRenderStore)

    camera = OrbitCamera()
    center, radius = mesh_center_and_radius(mesh)
    camera.frame_on_bounds(center, radius)
    rm.bind_camera(camera)
    rm.mark_camera_dirty(aspect=window.width / window.height)
    rm.sync()

    @window.event
    def on_draw():
        from pyglet import gl

        gl.glClearColor(0.05, 0.05, 0.08, 1.0)
        window.clear()
        rm.render(camera)

    @window.event
    def on_key_press(symbol, modifiers):
        if symbol in (key.ESCAPE, key.Q):
            window.close()

    def orbit(dt):
        camera.orbit(0.4 * dt, 0.0)
        rm.mark_camera_dirty(aspect=window.width / window.height)
        rm.sync()

    pyglet.clock.schedule_interval(orbit, 1 / 60.0)
    pyglet.app.run()


if __name__ == "__main__":
    main()
