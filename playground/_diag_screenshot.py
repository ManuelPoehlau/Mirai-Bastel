"""Diagnose-Screenshot: Head-Szene exakt wie run.py head rendern.

Speichert zwei PNGs:
  _diag_cam_eye.png  — Wahrnehmung: Kamera-Position/eye, Bounds, forward/right/up
  _diag_head_view.png — Bildschirmfoto des Fensters (was der User wirklich sieht)

Aufruf:
  python playground/_diag_screenshot.py
"""

import sys

from playground._paths import ensure_paths

ensure_paths()

import math  # noqa: E402

from playground.app import PlaygroundApp  # noqa: E402
from playground.window import PlaygroundWindow  # noqa: E402


def main() -> int:
    app = PlaygroundApp()
    app.load_head()

    cam = app.camera
    print("=== Kamera-Zustand nach load_head() ===")
    print(f"  camera type : {type(cam).__name__}")
    print(f"  target      : {tuple(round(x, 3) for x in cam.target)}")
    print(f"  distance    : {cam.distance:.3f}")
    print(f"  yaw         : {math.degrees(cam.yaw):.1f} deg  ({cam.yaw:.4f} rad)")
    print(f"  pitch       : {math.degrees(cam.pitch):.1f} deg")
    eye = cam.eye()
    print(f"  eye         : {tuple(round(x, 3) for x in eye)}")
    fwd, right, up = cam.basis()
    print(f"  forward     : {tuple(round(x, 3) for x in fwd)}")
    print(f"  right       : {tuple(round(x, 3) for x in right)}")
    print(f"  up          : {tuple(round(x, 3) for x in up)}")
    if eye[2] > 0:
        print("  >> Kamera auf +Z-Seite (Gesicht zeigt +Z) -> sollte GESICHT sehen")
    else:
        print("  >> Kamera auf -Z-Seite -> sieht Hinterkopf")
    print(f"  bounds      : {app.scene.mesh_bounds() if hasattr(app.scene, 'mesh_bounds') else 'n/a'}")
    vr = app.scene.mesh.all_vertex_ids()
    if vr:
        xs = [app.scene.mesh.vertex_position(v)[0] for v in vr]
        ys = [app.scene.mesh.vertex_position(v)[1] for v in vr]
        zs = [app.scene.mesh.vertex_position(v)[2] for v in vr]
        print(f"  mesh bounds : X {min(xs):.3f}..{max(xs):.3f} Y {min(ys):.3f}..{max(ys):.3f} Z {min(zs):.3f}..{max(zs):.3f}")

    # Fenster (sichtbar) bauen und EINEN Frame zeichnen.
    win = PlaygroundWindow(app)
    win.dispatch_event("on_draw")
    import pyglet
    from pyglet.gl import glFinish
    glFinish()

    out = "playground/_diag_head_view.png"
    pyglet.image.get_buffer_manager().get_color_buffer().save(out)
    print(f"\n  Screenshot gespeichert: {out}")
    win.close()
    pyglet.app.exit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())