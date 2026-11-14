"""Lookdev P1 - Eye Proof lab (2026-11-14). Disposable experiment; nothing in `src/` changes.

Usage (from the repo root):
    python experiments/lookdev_eye_lab/run.py                 # interactive window (keys: README "Controls", F1)
    python experiments/lookdev_eye_lab/run.py --probe         # measurements + screenshots, plain-ASCII report
    python experiments/lookdev_eye_lab/run.py --technique T-D --cornea C1 --view profile

The window draws the eye through the production `Viewport` with `EyeLabStore` (see `gl_lab.py`), a lab HUD (pyglet
text, texture unit 0) with the state and the last frame's GPU time, and writes screenshots to `out/screenshots/`.
"""

from __future__ import annotations

import argparse
import ctypes
import math
import sys
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from lookdev_eye_lab._paths import CACHE_DIR, OUT_DIR, ensure_paths  # noqa: E402

ensure_paths()

from lookdev_gpu_probe import cube_math as cm  # noqa: E402

from lookdev_eye_lab import lab_state as ls  # noqa: E402

WINDOW_SIZE = (1280, 800)
ORBIT_DEG_PER_PX = 0.4


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Lookdev P1 Eye Proof lab")
    p.add_argument("--probe", action="store_true", help="run the measurement probe instead of the window "
                   "(further options: run.py --probe -- --help)")
    p.add_argument("--technique", choices=ls.TECHNIQUES, default=ls.LabState.technique)
    p.add_argument("--cornea", choices=ls.CORNEAS, default=ls.LabState.cornea)
    p.add_argument("--view", choices=ls.VIEW_ORDER, default=ls.LabState.view)
    p.add_argument("--size", nargs=2, type=int, default=WINDOW_SIZE, metavar=("W", "H"))
    return p


def key_name(symbol: int) -> str:
    from pyglet.window import key

    name = key.symbol_string(symbol)
    return name[1:] if name.startswith("_") and name[1:].isdigit() else name


class LabWindow:
    def __init__(self, args) -> None:
        import pyglet
        from pyglet import gl

        from lookdev_eye_lab import lab_scene

        self.pyglet, self.gl = pyglet, gl
        self.window = pyglet.window.Window(width=args.size[0], height=args.size[1], resizable=True,
                                           caption="Mirai Lookdev P1 - Eye Proof (lab)")
        self.state = ls.LabState(technique=args.technique, cornea=args.cornea, view=args.view)
        width, height = self.window.get_framebuffer_size()
        self.scene = lab_scene.build_scene(self.state, OUT_DIR, CACHE_DIR, width, height)
        print(self.scene.iris_source.describe(), flush=True)
        self.close_up = False
        self.help = False
        self.queries = [ctypes.c_uint(), ctypes.c_uint()]
        for q in self.queries:
            gl.glGenQueries(1, ctypes.byref(q))
        self.frame_index = 0
        self.gpu_ms = float("nan")
        self.label = pyglet.text.Label("", x=10, y=0, multiline=True, width=1200, font_size=10,
                                       color=(230, 230, 230, 255), anchor_y="top")
        w = self.window
        w.on_draw = self.on_draw
        w.on_key_press = self.on_key_press
        w.on_mouse_drag = self.on_mouse_drag
        w.on_mouse_scroll = self.on_mouse_scroll
        w.on_resize = self.on_resize
        w.on_close = self.on_close
        self.message = "F1 help"
        self.shot_pending = False
        self.shots = 0

    # -- events

    def on_resize(self, width, height):
        fw, fh = self.window.get_framebuffer_size()
        self.scene.set_aspect(fw, fh)
        return True  # the lab sets its own viewport

    def on_close(self):
        self.scene.release()
        self.window.close()
        self.pyglet.app.exit()

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        from pyglet.window import mouse

        if buttons & mouse.LEFT:
            self.scene.camera.orbit(math.radians(-dx * ORBIT_DEG_PER_PX), math.radians(-dy * ORBIT_DEG_PER_PX))
            self.scene.viewport.on_camera_changed()

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.scene.camera.dolly(0.9 ** scroll_y)
        self.scene.viewport.on_camera_changed()

    def frame_distance(self) -> float:
        from lookdev_eye_lab import lab_scene

        fw, fh = self.window.get_framebuffer_size()
        return lab_scene.close_up_distance(fw, fh) if self.close_up else lab_scene.OVERVIEW_DISTANCE

    def on_key_press(self, symbol, modifiers):
        from pyglet.window import key

        name = key_name(symbol)
        shift = bool(modifiers & key.MOD_SHIFT)
        if name == "ESCAPE":
            self.on_close()
            return True
        if name == "F1":
            self.help = not self.help
            return True
        if name == "P":
            self.shot_pending = True  # taken in the next on_draw, before the HUD
            return True
        if name == "Z":
            self.close_up = not self.close_up
            self.scene.camera.target = (0.0, 0.0, 0.0)
            self.scene.camera.distance = self.frame_distance()
            self.scene.camera_moved()
            return True
        entry = ls.KEYS.get(name)
        if entry is None:
            return False
        new = entry[1](self.state, shift)
        view_changed = new.view != self.state.view
        for field_name in new.__dataclass_fields__:
            setattr(self.state, field_name, getattr(new, field_name))  # the renderer and stores share this object
        if view_changed:
            self.scene.apply_view(self.state.view)
            self.scene.camera_moved()
        if self.state.technique == "T-C" and self.scene.renderer.env_cube.key is None:
            self.message = "prefiltering the environment (first time: a few seconds, then cached) ..."
        return True

    def screenshot(self) -> None:
        from lookdev_eye_lab import gl_lab

        fw, fh = self.window.get_framebuffer_size()
        image = gl_lab.read_window_rgb(self.gl, fw, fh)
        folder = OUT_DIR / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        self.shots += 1
        path = folder / f"eye_{self.state.view}_{self.state.variant}_{time.strftime('%Y%m%d-%H%M%S')}_{self.shots}.png"
        cm.write_png(path, image / 255.0)
        self.message = f"screenshot: {path}"
        print(self.message, flush=True)

    # -- drawing

    def on_draw(self):
        gl = self.gl
        fw, fh = self.window.get_framebuffer_size()
        current = self.queries[self.frame_index % 2]
        gl.glBeginQuery(gl.GL_TIME_ELAPSED, current.value)
        self.scene.renderer.frame(self.scene.viewport, fw, fh)
        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        previous = self.queries[(self.frame_index + 1) % 2]
        if self.frame_index > 0:
            ready = ctypes.c_int()
            gl.glGetQueryObjectiv(previous.value, gl.GL_QUERY_RESULT_AVAILABLE, ctypes.byref(ready))
            if ready.value:
                value = ctypes.c_uint64()
                gl.glGetQueryObjectui64v(previous.value, gl.GL_QUERY_RESULT, ctypes.byref(value))
                self.gpu_ms = value.value / 1e6
        self.frame_index += 1
        if self.shot_pending:
            self.shot_pending = False
            self.screenshot()
        self.draw_hud(fw, fh)

    def draw_hud(self, fw: int, fh: int) -> None:
        gl = self.gl
        gl.glViewport(0, 0, fw, fh)
        lines = ls.describe(self.state)
        source = getattr(self.scene, "iris_source", None)
        if source is not None:
            lines.append(source.describe())
        lines.append(f"GPU frame {self.gpu_ms:.2f} ms (previous frame, GL_TIME_ELAPSED)   "
                     f"{'close-up' if self.close_up else 'overview'} (Z)   {self.message}")
        if self.help:
            lines.append("")
            lines += [f"{name:>6}  {text}" for name, (text, _fn) in ls.KEYS.items() if text]
            lines += ["     Z  close-up (eye ~50 % of the frame) / overview", "     P  screenshot",
                      "  drag  orbit (left button)   wheel  dolly", "   Esc  quit"]
        self.label.text = "\n".join(lines)
        self.label.y = self.window.height - 8
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        self.label.draw()
        gl.glDisable(gl.GL_BLEND)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--probe" in argv:
        from lookdev_eye_lab import probe_eye

        rest = [a for a in argv if a not in ("--probe", "--")]
        return probe_eye.main(rest)
    args = build_parser().parse_args(argv)
    import pyglet

    LabWindow(args)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
