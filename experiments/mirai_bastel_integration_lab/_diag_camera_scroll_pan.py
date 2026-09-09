"""Diagnose-Zusatz: Zoom (Scroll) und Pan über den ECHTEN Handler-Pfad.

Prüft, ob `on_mouse_scroll` (dolly) und `on_mouse_drag` (Pan) über den
nun eingebauten `self.draw(0.0)`-Redraw sichtbar im Framebuffer ankommen.
Vergleicht Framebuffer-Signaturen vor/nach jedem Event.

    python experiments/mirai_bastel_integration_lab/_diag_camera_scroll_pan.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pyglet
from pyglet import gl
from pyglet.window import mouse as _m

_THIS_DIR = Path(__file__).resolve().parent
_REPO = _THIS_DIR.parent.parent
for _p in (str(_THIS_DIR), str(_REPO), str(_REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from integration.lab_viewport import IntegrationLabWindow  # noqa: E402
from scene.scene_objects import build_lab_scene  # noqa: E402

_STRIDE = 9


def _signature(window):
    gl.glFinish()
    w, h = window.width, window.height
    buf = (gl.GLubyte * (w * h * 3))()
    gl.glReadPixels(0, 0, w, h, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    n = 0
    acc = 0
    for y in range(0, h, _STRIDE):
        base = y * w
        for x in range(0, w, _STRIDE):
            i = (base + x) * 3
            r, g, b = buf[i], buf[i + 1], buf[i + 2]
            if r or g or b:
                n += 1
                acc = (acc * 131 + r + g * 3 + b * 7) & 0xFFFFFFFF
    return (n, acc)


def main() -> int:
    lab = build_lab_scene()
    window = IntegrationLabWindow(lab)
    window.set_visible(True)
    res = {}

    def step_a(dt):
        res["A"] = _signature(window)
        d0 = window.camera.distance
        window.on_mouse_scroll(400, 300, 0, 1)
        print(
            f"[zoom] distance {d0:.4f} -> {window.camera.distance:.4f} "
            f"(dolly)"
        )

    def step_b(dt):
        res["B"] = _signature(window)
        t0 = tuple(window.camera.target)
        window.on_mouse_press(400, 300, _m.MIDDLE, 0)
        window._drag_moved = 0.0
        window.on_mouse_drag(400, 300, 30, 0, _m.MIDDLE, 0)
        print(
            f"[pan ] target {tuple(round(t, 3) for t in t0)} -> "
            f"{tuple(round(t, 3) for t in window.camera.target)}"
        )

    def step_c(dt):
        res["C"] = _signature(window)

        def _finish(_d):
            window.close()
            pyglet.app.exit()

        pyglet.clock.schedule_once(_finish, 0.2)

    pyglet.clock.schedule_once(step_a, 0.5)
    pyglet.clock.schedule_once(step_b, 0.9)
    pyglet.clock.schedule_once(step_c, 1.3)
    pyglet.app.run()

    a, b, c = res["A"], res["B"], res["C"]
    print(f"\nA(nach Start)={a}")
    print(f"B(nach Zoom) ={b}   A!=B -> {a != b}")
    print(f"C(nach Pan)  ={c}   B!=C -> {b != c}")
    ok = a != b and b != c
    print(f"ZOOM_PAN_OK: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())