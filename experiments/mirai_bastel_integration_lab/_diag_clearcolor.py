"""Minimaler Present-Pfad-Test: nur Clear-Color-Wechsel, kein Mesh/Kamera/HUD.

Ziel: ausschliessen, dass unser eigener Viewport-Code die Ursache ist.
Wenn auch dieser Farbwechsel nicht sichtbar wird, liegt das Problem im
pyglet/WGL/DWM-Present-Pfad selbst — unabhaengig von unserem Code.

Ablauf (je 0.5 s):
  schwarz -> weiss -> rot -> gruen -> blau -> schwarz -> ...
  (laeuft bis Esc/Fenster-X)

Aufruf:
    python experiments/mirai_bastel_integration_lab/_diag_clearcolor.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pyglet
from pyglet import gl

_THIS_DIR = Path(__file__).resolve().parent
_REPO = _THIS_DIR.parent.parent
for _p in (str(_THIS_DIR), str(_REPO), str(_REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_COLORS = [
    (0.0, 0.0, 0.0, 1.0),   # schwarz
    (1.0, 1.0, 1.0, 1.0),   # weiss
    (1.0, 0.0, 0.0, 1.0),   # rot
    (0.0, 1.0, 0.0, 1.0),   # gruen
    (0.0, 0.0, 1.0, 1.0),   # blau
]
_NAMES = ["schwarz", "weiss", "rot", "gruen", "blau"]
_INTERVAL = 0.5  # Sekunden pro Farbe


class _ClearWindow(pyglet.window.Window):
    def __init__(self):
        super().__init__(
            640, 480,
            caption="ClearColor-Diagnose (Esc=Ende)",
            resizable=False,
            vsync=True,           # Variante A: vsync=True (Standard)
        )
        self._color_index = 0
        self._frame = 0
        # Farbe alle _INTERVAL Sekunden wechseln
        pyglet.clock.schedule_interval(self._next_color, _INTERVAL)
        print(f"[diag] start — Fenster offen, Farbe wechselt alle {_INTERVAL}s")
        print(f"[diag] Variante A: vsync=True, keine WGL-Overrides")
        print(f"[diag] Aktuelle Farbe: {_NAMES[self._color_index]}")

    def _next_color(self, dt):
        self._color_index = (self._color_index + 1) % len(_COLORS)
        print(f"[diag] -> {_NAMES[self._color_index]}", flush=True)

    def on_draw(self):
        self._frame += 1
        r, g, b, a = _COLORS[self._color_index]
        gl.glClearColor(r, g, b, a)
        self.clear()
        return pyglet.event.EVENT_HANDLED

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.ESCAPE:
            self.close()
        return pyglet.event.EVENT_HANDLED


def main():
    win = _ClearWindow()
    win.set_visible(True)
    pyglet.app.run()
    print(f"[diag] beendet nach {win._frame} Frames")


if __name__ == "__main__":
    main()
