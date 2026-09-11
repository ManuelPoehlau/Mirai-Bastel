"""PlaygroundTransformer — Hotkey-to-Transform für AP-04 Phase 1.

Hotkey gedrückt halten (X/R/S) → Tool aktivieren → Drag → Transform.
Losgelassen → Commit. ESC während Drag → Cancel.

Nutzt Production-Tools (MoveTool, RotateTool, ScaleTool) direkt, keine
neue Implementierung. Rein Playground-Adapter.
"""

from __future__ import annotations

from typing import Literal

from playground._paths import ensure_paths

ensure_paths()

from core.selection import SelectionMode  # noqa: E402
from mirai.interaction.tools.move import MoveTool, resolve_selection_vertices  # noqa: E402
from mirai.interaction.tools.rotate import RotateTool  # noqa: E402
from mirai.interaction.tools.scale import ScaleTool  # noqa: E402

ToolType = Literal["move", "rotate", "scale"]


def create_tool_for_type(tool_type: ToolType):
    """Factory: erstelle das passende Production-Tool."""
    if tool_type == "move":
        return MoveTool()
    if tool_type == "rotate":
        return RotateTool()
    if tool_type == "scale":
        return ScaleTool()
    raise ValueError(f"Unknown tool type: {tool_type}")


def begin_transform(
    tool,
    scene,
    camera,
    selection,
) -> bool:
    """Tool aktivieren + begin() aufrufen.

    Konvertiert Face-Selection in Vertex-Selection (alle Vertices der selektierten Faces).
    Gibt True zurück wenn begin erfolgreich war (Selektion nicht leer).
    """
    if selection.is_empty():
        return False

    mesh = scene.mesh
    vertex_ids = resolve_selection_vertices(mesh, selection, selection.mode)

    if not vertex_ids:
        return False

    # Tool muss noch nicht aktiviert sein — wir machen das hier
    if not tool.is_active:
        tool.activate()

    try:
        tool.begin(scene=scene, camera=camera, vertex_ids=vertex_ids)
        return True
    except Exception:
        return False


def update_transform(
    tool,
    dx: float,
    dy: float,
    width: int,
    height: int,
    camera=None,  # camera wird ignoriert — ist bereits in begin() gespeichert
) -> bool:
    """Tool.update() mit Pixel-Deltas aufrufen.

    Camera ist bereits im Tool gespeichert von begin(), wird nicht übergeben.
    True wenn update erfolgreich war.
    """
    if not tool.is_interacting:
        return False

    try:
        tool.update(dx=dx, dy=dy, width=width, height=height)
        return True
    except Exception:
        return False


def commit_transform(tool) -> bool:
    """Tool.commit() aufrufen — genau ein History-Eintrag."""
    if not tool.is_interacting:
        return False

    try:
        tool.commit()
        return True
    except Exception:
        return False


def cancel_transform(tool) -> bool:
    """Tool.cancel() aufrufen — Vorzustand, keine History."""
    if not tool.is_interacting:
        return False

    try:
        tool.cancel()
        return True
    except Exception:
        return False
