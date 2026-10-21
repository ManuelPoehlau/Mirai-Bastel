"""GPU vs CPU picking through `Application` (AD-022 B2-out, 2026-10-21).

    python experiments/drag_cost/probe_picking_app.py [--asset examples/meshes/gollum_20k.obj] [--n 15]

Per mode (vertex / edge / face), once with the CPU picker (`app.gpu_picking = False`) and once with the GPU
picker, ms p50 / max:

- `first pick`: the camera orbits (unmeasured), then one `app._pick` at a cursor on the mesh (measured): the cost
  the Artist feels on the first hover after navigating.
- `hover`: `app._pick` at moving cursors, camera unchanged.
- `box 300px`: the Box rule (`elements_in_rect` / `gpu_elements_in_rect`) right after an orbit, a 300 x 300 px
  rectangle around the mesh centre - the selection the gesture would produce.
- `delete + pick`: Delete of one face and the re-pick at the cursor (journal path + pick), then Undo (unmeasured).

Every GPU timing includes `glFinish` so queued GL work is not hidden. Window 1024 x 768, hidden.
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from drag_cost import _paths  # noqa: E402

_paths.ensure_paths()

W, H = 1024, 768


def _ms(fn) -> float:
    from pyglet import gl

    start = time.perf_counter()
    fn()
    gl.glFinish()
    return (time.perf_counter() - start) * 1000.0


def _row(name: str, values: list[float]) -> str:
    return f"  {name:28s} n={len(values):3d}  p50 {statistics.median(values):8.2f}  max {max(values):8.2f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default=str(_paths.REPO_ROOT / "examples" / "meshes" / "gollum_20k.obj"))
    parser.add_argument("--n", type=int, default=15)
    args = parser.parse_args()

    import pyglet

    import main as src_main
    from core import SelectionMode
    from mirai.application import Application
    from mirai.interaction.input import Input
    from mirai.viewport.box_select import elements_in_rect
    from mirai.viewport.gpu_picking import gpu_elements_in_rect

    window = pyglet.window.Window(width=W, height=H, visible=False)
    app = Application()
    app.init_scene("obj", obj_path=Path(args.asset), **src_main.GL_TYPES)
    app.set_viewport_size(W, H)
    app.frame_scene()
    app._camera_changed()
    app.viewport.sync()
    mesh = app.scene.mesh
    print(f"{Path(args.asset).name}: {len(mesh.all_vertex_ids())} V / {len(mesh.all_face_ids())} F, "
          f"{W}x{H}, GL {pyglet.gl.gl_info.get_version()} {pyglet.gl.gl_info.get_renderer()}")

    cx, cy = W / 2.0, H / 2.0

    def orbit(i: int) -> None:
        app.camera.orbit(0.02 if i % 2 == 0 else -0.02, 0.0)
        app._camera_changed()

    for gpu in (False, True):
        app.gpu_picking = gpu
        label = "GPU" if gpu else "CPU"
        print(f"[{label}]")
        for mode in (SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE):
            app.selection.mode = mode
            first, hover, box = [], [], []
            for i in range(args.n + 2):
                orbit(i)
                t = _ms(lambda: app._pick(cx + 0.5, cy + 0.5))
                if i >= 2:
                    first.append(t)
            for i in range(args.n + 2):
                x = cx - 60 + 8 * i
                t = _ms(lambda: app._pick(x + 0.5, cy + 0.5))
                if i >= 2:
                    hover.append(t)
            rect = (cx - 150, cy - 150, cx + 150, cy + 150)
            for i in range(max(3, args.n // 3) + 1):
                orbit(i)
                if gpu:
                    t = _ms(lambda: gpu_elements_in_rect(
                        app.viewport.gpu_picker, app._gpu_pick_mesh(), app._edit_camera, mesh, mode, rect, W, H,
                        cache=app._pick_cache, occlusion=True))
                else:
                    t = _ms(lambda: elements_in_rect(
                        app._edit_camera, mesh, mode, rect, W, H, cache=app._pick_cache, occlusion=True))
                if i >= 1:
                    box.append(t)
            name = mode.name.lower()
            print(_row(f"{name} first pick", first))
            print(_row(f"{name} hover", hover))
            print(_row(f"{name} box 300px", box))

        app.key_press(Input("key", "3"))
        delete = []
        for i in range(args.n):
            face = app._pick(cx + 0.5, cy + 0.5)
            if face is None:
                break
            app.selection.set({face})
            app.viewport.on_selection_changed()

            def op() -> None:
                app.key_press(Input("key", "delete"))
                app._pick(cx + 0.5, cy + 0.5)

            delete.append(_ms(op))
            app.key_press(Input("key", "z", frozenset({"ctrl"})))
            app.viewport.sync()
        print(_row("delete 1 face + re-pick", delete))
    window.close()


if __name__ == "__main__":
    main()
