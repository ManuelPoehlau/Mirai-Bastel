"""Temp-Probe: Pixel-Check nach Window-Draw (wird danach gelöscht)."""
from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve().parent
for _p in (str(_THIS), str(_THIS.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pyglet  # noqa: E402

from integration.lab_viewport import IntegrationLabWindow  # noqa: E402
from scene.scene_objects import build_lab_scene  # noqa: E402


def main() -> int:
    lab = build_lab_scene()
    w = IntegrationLabWindow(lab)

    def _capture(_dt):
        try:
            from pyglet.image import get_buffer_manager
            buf = get_buffer_manager().get_color_buffer()
            if hasattr(buf, "get_data"):
                image = buf
            elif hasattr(buf, "get_region"):
                image = buf.get_region(0, 0, buf.width, buf.height).get_image()
            else:  # pragma: no cover
                image = buf.get_image()
            pitch, data = image.get_data()
        except Exception as exc:  # pragma: no cover
            import traceback
            traceback.print_exc()
            print(f"CAPTURE_FAILED {exc!r}")
            w.close()
            return
        n = len(data) // 4
        nonblack = 0
        center_nonblack = 0
        sampled = 0
        # Bildmitte: mittleres Viertel in x und y
        for i in range(0, n, 64):
            r = data[i * 4]
            g = data[i * 4 + 1]
            b = data[i * 4 + 2]
            sampled += 1
            if r > 48 or g > 48 or b > 48:
                nonblack += 1
        print(f"pixels_total={n} sampled={sampled} nonblack_sampled={nonblack} "
              f"frac={nonblack / max(sampled, 1):.4f}")
        print("VERDICT:", "MESH_VISIBLE" if nonblack / max(sampled, 1) > 0.005 else "STILL_BLACK")
        w.close()

    pyglet.clock.schedule_once(_capture, 1.4)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())