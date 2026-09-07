"""Headless Pixel-Check: Mesh nach Triangulation/Culling-Fix wirklich sichtbar?

pyglet 2.1-kompatibel: nutzt glReadPixels aus dem Default-Framebuffer.
Fuer Python 3.12 (User-Interpreter). Zeigt das Mesh kurz an und prueft, ob
ueberhaupt nicht-schwarze Pixel gerendert wurden.
"""
import pyglet
from pyglet import gl
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _paths import ensure_paths
ensure_paths()

from integration.lab_viewport import IntegrationLabWindow
from scene.scene_objects import build_lab_scene


def read_pixels(window):
    """Lese direkt aus dem Default-Framebuffer via glReadPixels."""
    buf = (gl.GLubyte * (window.width * window.height * 3))()
    gl.glReadBuffer(gl.GL_BACK)
    gl.glReadPixels(0, 0, window.width, window.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
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
    win = IntegrationLabWindow(lab)
    win._focus_camera(lab.objects[1].name)
    win._push_camera()

    # Pruefe, ob das Mesh wirklich VBO-Daten hat
    view = win.active_view()
    has_vlist = view.vlist is not None
    nv = view.vlist.count if has_vlist else 0
    ni = len(view.vlist.indices) if has_vlist else 0
    print(f"vlist: {has_vlist}, verts: {nv}, indices: {ni}")

    # Render mit sichtbarem Fenster
    win.set_visible(True)
    time.sleep(0.2)
    win.dispatch_event('on_resize', win.width, win.height)

    # Manuelles Render-Flush
    win.on_draw()
    gl.glFlush()
    gl.glFinish()

    # Lese direkt aus dem Default-Framebuffer (0)
    total = win.width * win.height
    nonzero, sum_rgb = read_pixels(win)
    pct = 100.0 * nonzero / total
    avg = [s // max(nonzero, 1) for s in sum_rgb]
    print(f"pyglet {pyglet.version}, glReadPixels: non-black pixels: {nonzero}/{total} ({pct:.1f}%)")
    print(f"  avg RGB: {avg}")

    if nonzero > 0:
        print("PIXEL_CHECK_OK: Mesh ist sichtbar gerendert")
    else:
        print("PIXEL_CHECK_FAIL: komplett schwarz - Mesh nicht sichtbar")
        print(f"  Viewport: {win.width}x{win.height}")
        print(f"  Active object: {lab.active.name}")

    win.close()
    return 0 if nonzero > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
