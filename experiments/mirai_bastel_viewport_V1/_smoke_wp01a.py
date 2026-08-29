"""Temporärer Smoke-Test für WP-01A — wird NICHT committet.

Erzeugt kurz ein echtes pyglet-Fenster und prüft die Command-/
Mapping-Pipeline sowie Pan-/Zoom-/Selection-Verhalten. Interaktive
Feinheiten (Hover-Gefühl, allgemeine UI) bleiben dem manuellen
Viewport-Test vorbehalten.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS))
sys.path.insert(0, str(_THIS.parent / "mirai_bastel_core_V1"))

from pyglet.window import key, mouse  # noqa: E402

from viewport.app import ModelerWindow  # noqa: E402
from viewport.display_state import DisplayMode  # noqa: E402

_failures = 0


def check(label: str, condition: bool) -> None:
    global _failures
    print(("PASS" if condition else "FAIL"), label)
    if not condition:
        _failures += 1


window = ModelerWindow()
try:
    # --- Key-Commands über das Mapping --------------------------------
    window.on_key_press(key.F, 0)
    check("F → Face-Mode (Command über Mapping)", window.selection_mode.name == "FACE")
    window.on_key_press(key.V, 0)
    check("V → Vertex-Mode", window.selection_mode.name == "VERTEX")
    window.on_key_press(key.O, 0)
    check("O → Flat Shaded", window.display_state.mode is DisplayMode.FLAT_SHADED)
    window.on_key_press(key.O, 0)
    check("O → Wireframe", window.display_state.mode is DisplayMode.WIREFRAME)
    window.on_key_press(key.O, 0)
    check("O → Shaded", window.display_state.mode is DisplayMode.SHADED)
    window.on_key_press(key.W, 0)
    check("W → Wireframe Overlay AN", window.display_state.wireframe_overlay is True)
    window.on_key_press(key.W, 0)
    check("W → Wireframe Overlay AUS", window.display_state.wireframe_overlay is False)

    # --- Mouse-Bindings (Pan/Select/Zoom) ------------------------------
    window.on_mouse_press(512, 384, mouse.MIDDLE, 0)
    check("MMB → Pan-Drag aktiv", window._drag_mode == "pan")
    before = window.camera.target
    window.on_mouse_drag(562, 384, 50, 0, mouse.MIDDLE, 0)
    check("Pan-Drag verändert das Kamera-Ziel", before != window.camera.target)

    distance_before = window.camera.distance
    window.on_mouse_scroll(512, 384, 0, 1)
    check("Scroll UP → Zoom (Dolly)", window.camera.distance < distance_before)

    window.on_key_press(key.F, 0)
    picked = window._pick(window.width // 2, window.height // 2)
    check("Face-Pick trifft eine Cube-Face", picked is not None)
    if picked is not None:
        window.on_mouse_press(window.width // 2, window.height // 2, mouse.LEFT, 0)
        check("LMB → Face wird selektiert", len(window.scene.selection.faces) == 1)

    # --- History-Zugriff über Mapping ------------------------------------
    window.on_key_press(key.Z, key.MOD_CTRL)
    check("Ctrl+Z → Undo (ohne Einträge kein Crash)", True)

finally:
    window.close()

print("FAILURES:", _failures)
sys.exit(1 if _failures else 0)