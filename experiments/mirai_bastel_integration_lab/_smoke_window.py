"""Kurzzeit-Smoke mit Pixel-Check (Cube zuerst, dann Head-Basemesh).

Prüft an der echten GPU-Pipeline, dass beide Objekte sichtbar gerendert
werden. Der Schwellwert (2 % der Pixel) unterscheidet Mesh-Flächen vom
HUD-Text (HUD-Text allein liegt bei ~0,8 % der Pixel — früher Fehlalarm).
Schließt das Fenster danach automatisch.
"""
import sys
from pathlib import Path

import pyglet
from pyglet import gl

_THIS_DIR = Path(__file__).resolve().parent
for _p in (str(_THIS_DIR), str(_THIS_DIR.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from integration.lab_viewport import IntegrationLabWindow  # noqa: E402
from scene.scene_objects import build_lab_scene  # noqa: E402

MESH_THRESHOLD_PCT = 2.0


def _scan(buf):
    nonzero = 0
    sum_rgb = [0, 0, 0]
    for i in range(0, len(buf), 3):
        r, g, b = buf[i], buf[i + 1], buf[i + 2]
        if r != 0 or g != 0 or b != 0:
            nonzero += 1
            sum_rgb[0] += r
            sum_rgb[1] += g
            sum_rgb[2] += b
    return nonzero, sum_rgb


def read_pixels(window):
    """Liest den Default-Framebuffer via glReadPixels (pyglet-2.1-robust).

    glReadBuffer kann je Pixelformat GL_INVALID_OPERATION werfen; dann
    wird der vom Treiber gesetzte Standard-Read-Buffer genutzt. Liefert
    der erste Griff nur schwarze Pixel, wird der andere Buffer probiert.
    """
    w, h = window.width, window.height
    buf = (gl.GLubyte * (w * h * 3))()

    def _grab():
        gl.glReadPixels(0, 0, w, h, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
        return _scan(buf)

    try:
        gl.glReadBuffer(gl.GL_BACK)
    except gl.GLException:
        pass
    nonzero, sum_rgb = _grab()
    if nonzero:
        return nonzero, sum_rgb
    try:
        gl.glReadBuffer(gl.GL_FRONT)
        result = _grab()
        gl.glReadBuffer(gl.GL_BACK)
        return result
    except gl.GLException:
        return nonzero, sum_rgb


def _measure(window):
    gl.glFinish()
    total = max(window.width * window.height, 1)
    nonzero, sum_rgb = read_pixels(window)
    pct = 100.0 * nonzero / total
    avg = [s // max(nonzero, 1) for s in sum_rgb]
    print(f"  non-black: {nonzero}/{total} ({pct:.2f}%), avg RGB: {avg}")
    return pct >= MESH_THRESHOLD_PCT


def main():
    lab = build_lab_scene()
    window = IntegrationLabWindow(lab)
    window.set_visible(True)
    results = {}

    def _step_cube(dt):
        print(f"[Cube] name={lab.objects[0].name!r}")
        results["Cube"] = _measure(window)
        # Auf Head umschalten; ab dem nächsten Frame wird er gerendert.
        window._focus_camera(lab.objects[1].name)
        window._push_camera()
        view = window.active_view()
        ni = len(view.vlist.indices) if view.vlist is not None else 0
        print(f"[Head] name={lab.objects[1].name!r}, vlist={view.vlist is not None}, indices={ni}")

    def _step_head(dt):
        results["Head"] = _measure(window)
        if all(results.values()):
            print("PIXEL_CHECK_OK: Cube und Head sind sichtbar gerendert")
        else:
            print(f"PIXEL_CHECK_FAIL: {results}")
        window.close()
        pyglet.app.exit()

    pyglet.clock.schedule_once(_step_cube, 0.4)
    pyglet.clock.schedule_once(_step_head, 0.9)
    pyglet.app.run()
    return 0 if all(results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())