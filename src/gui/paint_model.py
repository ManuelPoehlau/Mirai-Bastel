"""The Paint Room panel's logic (AD-037 §8 Phase 2; AD-030: pure logic headless, `paint_panel` only draws).

The panel reads the room's state (`state(app)`) and calls `Application` (`set_paint_brush`, `set_paint_resolution`,
`close_paint_room`, the paint layer calls of Phase 3); it holds no document state. Labels German, every layout choice `PROVISIONAL` (audit §9.2: a compact
text strip in the room only, P-17).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.scene import PAINT_BLEND_MODES
from mirai.paint.alpha import TEST_ALPHAS, alpha_name
from mirai.paint.brush import CURVE_ARRAYS, CURVE_LABELS, RADIUS_STEPS_PERCENT, TOOL_LABELS, TOOLS, BrushSettings
from mirai.paint.dynamics import SPACING_MAX, SPACING_MIN
from mirai.paint.layers import BLEND_LABELS, MAX_LAYERS

#: The panel's title and the SPACE menu row (no key until Manu's "Taste passt").
TITLE = "Paint Room"
MENU_OPEN = "Paint Room öffnen"
MENU_CLOSE = "Paint Room schließen"
CURVES = tuple(CURVE_ARRAYS)
BLENDS = PAINT_BLEND_MODES
#: The layer list's text before the first stroke (Phase 3).
NO_LAYERS = "Noch keine Bemalung - der erste Strich legt „Ebene 1“ an"
#: Phase 4a (AD-037 §12): the tip chooser - the round tip and the generated test alphas (no library before 4c).
TIPS: tuple[tuple[str | None, str], ...] = ((None, alpha_name(None)),) + tuple((i, alpha_name(i)) for i in TEST_ALPHAS)
#: The spacing slider's range in percent of the stamp diameter (P-18).
SPACING_PERCENT = (SPACING_MIN * 100.0, SPACING_MAX * 100.0)


@dataclass(frozen=True)
class LayerRow:
    """One row of the layer list (top first in `PaintPanelState.layers`)."""

    name: str
    visible: bool
    opacity: float
    blend: str
    active: bool
    label: str


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
    #: the layers top first (empty before the first stroke), and what the layer buttons may do now
    layers: tuple[LayerRow, ...] = ()
    can_add: bool = False
    can_delete: bool = False
    can_up: bool = False
    can_down: bool = False
    can_merge: bool = False
    #: the tip chooser's rows (alpha id or None, label) and the chosen one's label
    tips: tuple[tuple[str | None, str], ...] = TIPS
    tip_label: str = "Rund"


def _plane(app) -> str | None:
    definition = app.scene.mesh.symmetry_definition
    if definition is None:
        return None
    n = definition.plane_normal
    axis = max(range(3), key=lambda i: abs(n[i]))
    return "XYZ"[axis]


def layer_label(name: str, opacity: float, blend: str) -> str:
    extra = [f"{round(opacity * 100)} %"] if opacity < 1.0 else []
    if blend != "normal":
        extra.append(BLEND_LABELS[blend])
    return name + (f"  ({', '.join(extra)})" if extra else "")


def _layers(app, obj) -> tuple[tuple[LayerRow, ...], dict]:
    stack = obj.paint
    if stack is None or not app.paint_room_open:
        return (), {}
    active = app.paint_active_layer
    rows = tuple(LayerRow(layer.name, layer.visible, layer.opacity, layer.blend, layer.name == active,
                          layer_label(layer.name, layer.opacity, layer.blend)) for layer in reversed(stack.layers))
    names = [layer.name for layer in stack.layers]
    i = names.index(active)
    below = stack.layers[i - 1] if i > 0 else None
    me = stack.layers[i]
    flags = dict(can_add=len(names) < MAX_LAYERS, can_delete=len(names) > 1, can_up=i < len(names) - 1,
                 can_down=i > 0, can_merge=below is not None and below.blend == me.blend and below.visible and me.visible)
    return rows, flags


def state(app) -> PaintPanelState:
    open_ = app.paint_room_open
    obj = app.scene.edit_object
    header = f"{obj.name}" if open_ else "geschlossen"
    rows, flags = _layers(app, obj)
    stroking = app.paint_stroking
    if stroking:
        flags = {}
    return PaintPanelState(
        open=open_,
        header=header,
        brush=app.paint_brush,
        resolution=app.paint_resolution,
        resolutions=tuple(app.paint_resolutions),
        resolution_fixed=obj.paint is not None,
        mirror_plane=_plane(app),
        surface=app.paint_surface_text if open_ else "",
        stroking=stroking,
        layers=rows,
        tip_label=alpha_name(app.paint_brush.tip.alpha),
        **flags,
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


def blend_label(blend: str) -> str:
    return BLEND_LABELS[blend]


__all__ = ["BLENDS", "CURVES", "MENU_CLOSE", "MENU_OPEN", "NO_LAYERS", "TITLE", "TOOLS", "LayerRow", "PaintPanelState",
           "menu_label", "state", "toggle"]
