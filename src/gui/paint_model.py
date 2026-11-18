"""The Paint Room panel's logic (AD-037 §8 Phase 2; AD-030: pure logic headless, `paint_panel` only draws).

The panel reads the room's state (`state(app)`) and calls `Application` (`set_paint_brush`, `set_paint_resolution`,
`close_paint_room`); it holds no document state. Labels German, every layout choice `PROVISIONAL` (audit §9.2: a compact
text strip in the room only, P-17).
"""

from __future__ import annotations

from dataclasses import dataclass

from mirai.paint.brush import CURVE_ARRAYS, CURVE_LABELS, RADIUS_STEPS_PERCENT, TOOL_LABELS, TOOLS, BrushSettings

#: The panel's title and the SPACE menu row (no key until Manu's "Taste passt").
TITLE = "Paint Room"
MENU_OPEN = "Paint Room öffnen"
MENU_CLOSE = "Paint Room schließen"
CURVES = tuple(CURVE_ARRAYS)


@dataclass(frozen=True)
class PaintPanelState:
    open: bool
    header: str
    brush: BrushSettings
    resolution: int
    resolutions: tuple[int, ...]
    resolution_fixed: bool
    mirror_plane: str | None
    surface: str
    stroking: bool


def _plane(app) -> str | None:
    definition = app.scene.mesh.symmetry_definition
    if definition is None:
        return None
    n = definition.plane_normal
    axis = max(range(3), key=lambda i: abs(n[i]))
    return "XYZ"[axis]


def state(app) -> PaintPanelState:
    open_ = app.paint_room_open
    obj = app.scene.edit_object
    header = f"{obj.name}" if open_ else "geschlossen"
    return PaintPanelState(
        open=open_,
        header=header,
        brush=app.paint_brush,
        resolution=app.paint_resolution,
        resolutions=tuple(app.paint_resolutions),
        resolution_fixed=obj.paint is not None,
        mirror_plane=_plane(app),
        surface=app.paint_surface_text if open_ else "",
        stroking=app.paint_stroking,
    )


def menu_label(app) -> str | None:
    """The SPACE menu row: open / close, or None when the edit object cannot be painted at all (no UVs, an eye)."""
    if app.paint_room_open:
        return MENU_CLOSE
    obj = app.scene.edit_object
    if obj.eye is not None or not obj.mesh.has_face_uvs():
        return None
    return MENU_OPEN


def toggle(app) -> bool:
    return app.close_paint_room() if app.paint_room_open else app.open_paint_room()


def radius_index(brush: BrushSettings) -> int:
    return brush.radius_step


def radius_label(step: int) -> str:
    return f"{RADIUS_STEPS_PERCENT[step]:g} %"


def tool_label(tool: str) -> str:
    return TOOL_LABELS[tool]


def curve_label(curve: str) -> str:
    return CURVE_LABELS[curve]


__all__ = ["CURVES", "MENU_CLOSE", "MENU_OPEN", "TITLE", "TOOLS", "PaintPanelState", "menu_label", "state", "toggle"]
