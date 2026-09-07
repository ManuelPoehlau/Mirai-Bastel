"""Kurzzeit-Smoke mit Pixel-Check des echten Meshes (nicht nur schwarz).

Öffnet das Fenster, rendert das Head-Basemesh, liest Pixel via glReadPixels
aus dem Default-Framebuffer und prüft, ob Mesh-Sichtbarkeit bestätigt ist.
Schließt danach automatisch.
"""
import sys
from pathlib import Path

import pyglet
from pyglet import gl

_THIS_DIR = Path(__file__).resolve().parent
for _p in (str(_THIS_DIR), str(_THIS_DIR.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from integration.lab_viewport import IntegrationLabWindow
from scene.scene_objects import build_lab_scene


def read_pixels(window):
    """Lese direkt aus dem Default-Framebuffer via glReadPixels."""
    buf = (gl.GLubyte * (window.width * window.height * 3))()
    gl.glReadBuffer(gl.GL_BACK)
    gl.glReadPixels(0, 0, window.width, window.height, gl.GL_RGB,
                    gl.GL_UNSIGNED_BYTE, buf)
    nonzero = 0
    sum_rgb = [0, 0, 0]
    for i in range(0, len(buf), 3):
        r, g, b = buf[i], buf[i + 1], buf[i + 2]
        if r != 0 or g != 0 or b != 0:
            nonzero += 1
            sum_rgb[0] += r; sum_rgb[1] += g; sum_rgb[2] += b
    return nonzero, sum_rgb


def main():
    lab = build_lab_scene()
    window = IntegrationLabWindow(lab)
    window._focus_camera(lab.objects[1].name)
    window._push_camera()

    # Pruefe VBO-Daten
    view = window.active_view()
    has_vlist = view.vlist is not None
    nv = view.vlist.count if has_vlist else 0
    ni = len(view.vlist.indices) if has_vlist else 0
    print(f"vlist: {has_vlist}, verts: {nv}, indices: {ni}")

    # Nimm das Fokus-Objekt (Head) und rendere
    window.set_visible(True)

    def _check_and_close(dt):
        gl.glFinish()
        total = window.width * window.height
        nonzero, sum_rgb = read_pixels(window)
        pct = 100.0 * nonzero / total
        avg = [s // max(nonzero, 1) for s in sum_rgb]
        print(f"glReadPixels: {nonzero}/{total} ({pct:.1f}% non-black), avg RGB: {avg}")
        if nonzero > 0:
            print("PIXEL_CHECK_OK: Head-Basemesh ist sichtbar gerendert")
        else:
            print("PIXEL_CHECK_FAIL: komplett schwarz")
        window.close()
        pyglet.app.exit()

    pyglet.clock.schedule_once(_check_and_close, 0.5)
    pyglet.app.run()
    return 0


if __name__ == '__main__':
    sys.exit(main())