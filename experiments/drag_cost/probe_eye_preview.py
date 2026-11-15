"""GPU cost of the eye preview in the Worklight (AD-033 phase E-4, 2026-11-15): the reference head with two eyes.

Usage (from the repo root; opens a hidden pyglet window):
    python experiments/drag_cost/probe_eye_preview.py
    python experiments/drag_cost/probe_eye_preview.py --size 1920 1080 --draws 60

Set the NVIDIA driver to "prefer maximum performance" first (as for `probe_shading_gpu.py`).

The scene: the head base mesh (`head_basemesh`, the edit object) and two eyes from `Application.add_eye` (2.4 units
across, 1 unit = 1 cm) placed at the head's front, `frame_scene` as the app does. Two views: `head` (the framed head,
the eyes small - the modelling case) and `close` (the camera on one eye, the eye about half the frame high). Per
run the whole frame (`Viewport.render`: the head, both eyes, the overlays) is timed with GL_TIME_ELAPSED, the runs in
turn, `--draws` rounds after 5 unmeasured ones:

- `preview off`       the eyes drawn by the Worklight (the floor: what the scene costs without the eye pass);
- `L0` / `L2` / `L3`  the eye pass, studio reflection, V2;
- `L3 key`            L3 with the key highlight only (no studio);
- `L3 V3`             L3 with the two-surface refraction.

Reported: GPU p50 / min / max, the difference to `preview off`, the pixels the eyes cover. Plain ASCII.
"""

from __future__ import annotations

import argparse
import ctypes
import dataclasses
import statistics
import sys
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from drag_cost._paths import ensure_paths  # noqa: E402

ensure_paths()

WARMUP_ROUNDS = 5
DEFAULT_DRAWS = 40
#: (name, preview, level, reflection, refraction)
RUNS = (("preview off", False, 0, "studio", "V2"), ("L0", True, 0, "studio", "V2"), ("L2", True, 2, "studio", "V2"),
        ("L3", True, 3, "studio", "V2"), ("L3 key", True, 3, "key", "V2"), ("L3 V3", True, 3, "studio", "V3"))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--size", nargs=2, type=int, default=(1024, 768), metavar=("W", "H"))
    p.add_argument("--draws", type=int, default=DEFAULT_DRAWS)
    return p


def build_scene(size):
    import math

    import pyglet

    import main as src_main
    from core import ObjectTransform
    from loaders.assets import asset_path
    from mirai.application import Application

    window = pyglet.window.Window(width=size[0], height=size[1], visible=False)
    app = Application()
    app.init_scene("obj", obj_path=asset_path("head_basemesh"), **src_main.GL_TYPES)
    head = app.scene.edit_object.mesh
    points = [head.vertex_position(v) for v in head.all_vertex_ids()]
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    width = hi[0] - lo[0]
    centre_x = 0.5 * (lo[0] + hi[0])
    eye_y = lo[1] + 0.62 * (hi[1] - lo[1])
    eye_z = hi[2] - 0.12 * (hi[2] - lo[2])
    eyes = []
    for side in (-1.0, 1.0):
        eye = app.add_eye()
        eye.transform = ObjectTransform(translation=(centre_x + side * 0.16 * width, eye_y, eye_z),
                                        scale=eye.transform.scale)
        eyes.append(eye)
    app._objects.placement_changed()
    app.selection.objects = set()
    app.frame_scene()
    app.set_viewport_size(*size)
    app.update_viewport(0.0)
    head_view = (app.camera.target, app.camera.distance)
    close_target = tuple(eyes[0].transform.translation)
    close_distance = 2.0 * 2.4 / (2.0 * math.tan(math.radians(app.camera.fov_degrees) / 2.0))
    return window, app, eyes, {"head": head_view, "close": (close_target, close_distance)}


def measure(size, draws: int) -> list[str]:
    from pyglet import gl

    window, app, eyes, views = build_scene(size)
    width, height = window.get_framebuffer_size()
    query = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(query))
    lines = [f"[head_basemesh + 2 eyes] {width}x{height}, {draws} rounds after {WARMUP_ROUNDS}"]
    for view, (target, distance) in views.items():
        app.camera.target, app.camera.distance = target, distance
        app.viewport.on_camera_changed()
        samples = {run[0]: [] for run in RUNS}
        cpu = {run[0]: [] for run in RUNS}
        images = {}
        for round_ in range(WARMUP_ROUNDS + draws):
            for name, preview, level, reflection, refraction in RUNS:
                for eye in eyes:
                    if eye.eye.limbus_level != level:
                        eye.eye = dataclasses.replace(eye.eye, limbus_level=level)
                app.set_eye_display(preview=preview, reflection=reflection, refraction=refraction)
                app._objects.sync_views()
                window.switch_to()
                app.update_viewport(0.0)
                gl.glViewport(0, 0, width, height)
                gl.glClearColor(0.1, 0.1, 0.11, 1.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
                gl.glFinish()
                start = time.perf_counter()
                gl.glBeginQuery(gl.GL_TIME_ELAPSED, query.value)
                app.viewport.render()
                gl.glEndQuery(gl.GL_TIME_ELAPSED)
                gl.glFinish()
                elapsed = (time.perf_counter() - start) * 1000.0
                value = ctypes.c_uint64()
                gl.glGetQueryObjectui64v(query.value, gl.GL_QUERY_RESULT, ctypes.byref(value))
                if round_ >= WARMUP_ROUNDS:
                    samples[name].append(value.value / 1e6)
                    cpu[name].append(elapsed)
                if round_ == WARMUP_ROUNDS + draws - 1:
                    buf = (gl.GLubyte * (width * height * 3))()
                    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
                    gl.glReadPixels(0, 0, width, height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
                    images[name] = bytes(buf)
        changed = sum(1 for i in range(0, len(images["L0"]), 3)
                      if images["L0"][i:i + 3] != images["preview off"][i:i + 3])
        floor = statistics.median(samples["preview off"])
        lines.append(f"  view {view}: the eye pass changes {changed} px ({100.0 * changed / (width * height):.1f} % of "
                     f"the frame)")
        lines.append(f"    {'run':<12} {'GPU p50':>9} {'min':>8} {'max':>8} {'vs off':>8}   {'CPU p50':>8}")
        for name, *_ in RUNS:
            gpu = samples[name]
            lines.append(f"    {name:<12} {statistics.median(gpu):9.2f} {min(gpu):8.2f} {max(gpu):8.2f} "
                         f"{statistics.median(gpu) - floor:+8.2f}   {statistics.median(cpu[name]):8.2f}")
    gl.glDeleteQueries(1, ctypes.byref(query))
    window.close()
    return lines


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    import pyglet

    from drag_cost.probe_d3_acceptance import source_state
    from drag_cost.probe_drag_gl import machine_info

    probe = pyglet.window.Window(width=64, height=64, visible=False)
    info = machine_info(pyglet.gl.gl_info.get_version_string(), pyglet.gl.gl_info.get_renderer())
    probe.close()
    print("Eye preview GPU probe (AD-033 E-4, 2026-11-15): the whole frame, GL_TIME_ELAPSED, ms")
    for line in info:
        print(line)
    print(f"Source: {source_state()}")
    print()
    for line in measure(tuple(args.size), args.draws):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
