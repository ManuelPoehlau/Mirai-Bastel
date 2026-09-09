"""WP-IL-01 Kamera-Bewegungsprobe (echtes Pyglet/OpenGL, auto-close).

Beobachtungsartefakt zu WP-IL-01 ("unter echtem Pyglet/OpenGL beobachten").
Entscheidet empirisch, ob Production-Kamera-Änderungen (eine einzige
LabOrbitCamera, an src.viewport.Viewport.bind_camera gebunden) sichtbar in
den Framebuffer gelangen — und WIE der Redraw geschieht:

  Messung A    : Frame nach dem Start (Cube-Framing)
  orbit (ohne erzwingen) → Messung B : testet Continuous-Redraw
  orbit (mit on_draw-Dispatch) → Messung C : testet gezwungenen Redraw

Auswertung:
  B != A  → Continuous-Redraw funktioniert (Normalfall).
  B == A und C != A → pyglet zeichnet nur on-demand; Kamera-Änderungen ohne
      Event/Dispatch bleiben sichtbar unbewegt (trifft das historische
      Symptom "Kamera wird erkannt, Bild ändert sich nicht").
  C == A → auch der gezwungene Redraw zeigt keine Wirkung (echter Defekt).

    python experiments/mirai_bastel_integration_lab/_camera_motion_probe.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent
for _p in (str(_THIS_DIR), str(_REPO_ROOT), str(_REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pyglet  # noqa: E402
from pyglet import gl  # noqa: E402

from integration.lab_viewport import IntegrationLabWindow  # noqa: E402
from scene.scene_objects import build_lab_scene  # noqa: E402

# Subsampling: jeder 7. Pixel in jeder 7. Reihe reicht als Signatur.
_STRIDE = 7
_VISIBLE_FRACTION = 0.02


def _signature(window):
    """(nonblack_subsampled, hash) des aktuellen Framebuffers."""
    gl.glFinish()
    w, h = window.width, window.height
    buf = (gl.GLubyte * (w * h * 3))()
    gl.glReadPixels(0, 0, w, h, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    nonblack = 0
    acc = 0
    for y in range(0, h, _STRIDE):
        base = y * w
        for x in range(0, w, _STRIDE):
            i = (base + x) * 3
            r, g, b = buf[i], buf[i + 1], buf[i + 2]
            if r or g or b:
                nonblack += 1
                acc = (acc * 131 + r + g * 3 + b * 7) & 0xFFFFFFFF
    return nonblack, acc


def main() -> int:
    lab = build_lab_scene()
    window = IntegrationLabWindow(lab)
    window.set_visible(True)
    results: dict[str, tuple[int, int]] = {}

    def _measure(tag: str) -> None:
        results[tag] = _signature(window)
        print(f"[{tag}] nonblack(sub)={results[tag][0]} signature={results[tag][1]}")

    def _step_a(_dt) -> None:
        _measure("A nach-Start")

    def _step_orbit_no_forced_redraw(_dt) -> None:
        cam = window.camera
        cam.orbit(1.2, 0.35)
        cam.dolly(0.55)
        window._push_camera()
        print(
            f"[orbit] yaw={math.degrees(cam.yaw):.1f}deg "
            f"pitch={math.degrees(cam.pitch):.1f}deg dist={cam.distance:.2f} "
            f"(kein erzwungener Redraw)"
        )

    def _step_b(_dt) -> None:
        _measure("B nach-orbit")

    def _step_orbit_forced(_dt) -> None:
        cam = window.camera
        cam.orbit(0.9, -0.2)
        window._push_camera()
        window.dispatch_event("on_draw")  # Redraw explizit erzwingen

    def _step_c(_dt) -> None:
        _measure("C nach-orbit+forced-draw")
        window.close()
        pyglet.app.exit()

        a, b, c = results["A nach-Start"], results["B nach-orbit"], results["C nach-orbit+forced-draw"]
        total_sub = (window.width // _STRIDE + 1) * (window.height // _STRIDE + 1)
        mesh_visible = min(a[0], c[0]) > total_sub * _VISIBLE_FRACTION
        motion_free = b != a
        motion_forced = c != a
        print(f"[ergebnis] mesh_visible={mesh_visible}  "
              f"continuous_redraw={'JA' if motion_free else 'NEIN'}  "
              f"forced_redraw_effect={'JA' if motion_forced else 'NEIN'}")
        if mesh_visible and motion_forced:
            print("PIXEL_MOTION_OK")
        else:
            print("PIXEL_MOTION_FAIL")

    pyglet.clock.schedule_once(_step_a, 0.5)
    pyglet.clock.schedule_once(_step_orbit_no_forced_redraw, 0.8)
    pyglet.clock.schedule_once(_step_b, 1.2)
    pyglet.clock.schedule_once(_step_orbit_forced, 1.5)
    pyglet.clock.schedule_once(_step_c, 1.9)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
