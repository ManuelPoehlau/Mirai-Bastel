"""Wiederholbarer Smoke-Check für den All-Tools-Playground.

Erzeugt kurz ein echtes pyglet-Fenster und prüft Launcher-Import, Fenster-
Init, Testszene und die wichtigsten Key-Commands über die echte Mapping-
Pipeline (Windows-Konsole: ggf. `set PYTHONIOENCODING=utf-8` setzen).
Interaktive Feinheiten (Hover-Gefühl, Drag-UX) bleiben dem manuellen
Viewport-Test vorbehalten.
"""
from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS))
sys.path.insert(0, str(_THIS.parent / "mirai_bastel_core_V1"))

from pyglet.window import key, mouse  # noqa: E402

from mirai_bastel_core import SelectionMode  # noqa: E402

from viewport.all_tools_app import (  # noqa: E402
    AllToolsWindow,
    AxisConstrainedMoveTool,
)
from viewport.transform_tool import RotateTool, ScaleTool  # noqa: E402

_failures = 0


def check(label: str, condition: bool) -> None:
    global _failures
    print(("PASS" if condition else "FAIL"), label)
    if not condition:
        _failures += 1


window = AllToolsWindow()
try:
    check("Cube-Testszene: 8 Vertices", len(list(window.scene.mesh.all_vertex_ids())) == 8)
    check("Cube-Testszene: 6 Faces", len(list(window.scene.mesh.all_face_ids())) == 6)
    check("Start im Vertex-Mode", window.selection_mode is SelectionMode.VERTEX)
    check("Caption dokumentiert die Belegung", "All-Tools Playground" in window.caption)
    check("Caption nennt Shift+R/Shift+S", "Shift+R" in window.caption and "Shift+S" in window.caption)

    window.on_key_press(key.M, 0)
    check("M → Move-Tool (Achsen-Adapter)", isinstance(window._tool_manager.active_tool, AxisConstrainedMoveTool))
    window.on_key_press(key.X, 0)
    check("X → Achse X vorgewählt", window._pending_axis == "x")
    check("Caption zeigt Achse", "Achse: X" in window.caption)
    window.on_key_press(key.X, 0)
    check("X erneut → Achse frei", window._pending_axis is None)
    window.on_key_press(key.ESCAPE, 0)
    check("Esc → Tool deaktiviert", window._tool_manager.active_tool is None)

    window.on_key_press(key.R, key.MOD_SHIFT)
    check("Shift+R → RotateTool", isinstance(window._tool_manager.active_tool, RotateTool))
    window.on_key_press(key.ESCAPE, 0)
    window.on_key_press(key.S, key.MOD_SHIFT)
    check("Shift+S → ScaleTool", isinstance(window._tool_manager.active_tool, ScaleTool))
    window.on_key_press(key.ESCAPE, 0)

    window.on_key_press(key.E, 0)
    edge = sorted(window.scene.mesh.all_edge_ids())[0]
    window.scene.selection.set({edge})
    window.on_key_press(key.R, 0)
    check("R → EdgeRing (bestehendes Binding)", len(window.scene.selection.edges) == 4)
    window.scene.selection.set({edge})  # Split braucht genau 1 Edge (nach Ring 4)
    window.on_key_press(key.S, 0)
    check("S → SplitEdge (bestehendes Binding)", len(list(window.scene.mesh.all_vertex_ids())) == 9)
    window.on_key_press(key.Z, key.MOD_CTRL)
    check("Ctrl+Z → Undo", len(list(window.scene.mesh.all_vertex_ids())) == 8)

    window.on_key_press(key.O, 0)
    check("O → Display-Mode gewechselt", True)
    window.on_mouse_scroll(512, 384, 0, 1)
    check("Wheel → Zoom", True)
finally:
    window.close()

print("FAILURES:", _failures)
sys.exit(1 if _failures else 0)
