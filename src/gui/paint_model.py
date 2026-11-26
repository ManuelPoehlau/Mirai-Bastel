"""The Paint Room panel's logic (AD-037 §8 Phase 2; AD-030: pure logic headless, `paint_panel` only draws).

The panel reads the room's state (`state(app)`) and calls `Application` (`set_paint_brush`, `set_paint_resolution`,
`close_paint_room`, the paint layer calls of Phase 3); it holds no document state. Labels German, every layout choice `PROVISIONAL` (audit §9.2: a compact
text strip in the room only, P-17).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.scene import PAINT_BLEND_MODES
from mirai.paint.brush import CURVE_ARRAYS, CURVE_LABELS, RADIUS_STEPS_PERCENT, TOOL_LABELS, TOOLS, BrushSettings
from mirai.paint.dynamics import (
    EMITTER_LABELS,
    EMITTERS,
    ORIENTATION_LABELS,
    ORIENTATIONS,
    SCATTER_MAX,
    SIZE_JITTER_MAX,
    SPACING_MAX,
    SPACING_MIN,
    SPRAY_MAX,
    SPRAY_SIZE_MAX,
    SPRAY_SIZE_MIN,
)
from mirai.paint.layers import BLEND_LABELS, MAX_LAYERS

#: The panel's title and the SPACE menu row (no key until Manu's "Taste passt").
TITLE = "Paint Room"
MENU_OPEN = "Paint Room öffnen"
MENU_CLOSE = "Paint Room schließen"
CURVES = tuple(CURVE_ARRAYS)
BLENDS = PAINT_BLEND_MODES
#: The layer list's text before the first stroke (Phase 3).
NO_LAYERS = "Noch keine Bemalung - der erste Strich legt „Ebene 1“ an"
#: The spacing slider's range in percent of the stamp diameter (P-18).
SPACING_PERCENT = (SPACING_MIN * 100.0, SPACING_MAX * 100.0)
#: Phase 4b (AD-037 §13): the brush's collapsed sections (proposal §7 area 4) - key, title; "spray" only with the spray
#: emitter - and the ranges of their sliders (percent / radii / stamps).
SECTIONS = (("stroke", "Strich"), ("scatter", "Streuung"), ("spray", "Spray"))
ORIENTATION_ROWS = tuple((o, ORIENTATION_LABELS[o]) for o in ORIENTATIONS)
EMITTER_ROWS = tuple((e, EMITTER_LABELS[e]) for e in EMITTERS)
SIZE_JITTER_PERCENT = SIZE_JITTER_MAX * 100.0
SCATTER_RADII = SCATTER_MAX
SPRAY_DENSITY_RANGE = (1, SPRAY_MAX)
SPRAY_SIZE_PERCENT = (SPRAY_SIZE_MIN * 100.0, SPRAY_SIZE_MAX * 100.0)


def _radii(value: float) -> str:
    return f"{value:.1f}".replace(".", ",") + " r"


def stroke_summary(brush: BrushSettings) -> str:
    """The "Strich" section's line while it is closed: spacing, orientation (alpha tip) and angle, emitter."""
    dyn = brush.dynamics
    parts = [f"Abstand {dyn.spacing * 100:.0f} %"]
    if not brush.tip.round:
        parts.append(ORIENTATION_LABELS[dyn.orientation] + (f" {dyn.angle:+.0f}°" if dyn.angle else ""))
    parts.append(EMITTER_LABELS[dyn.emitter])
    return ", ".join(parts)


def scatter_summary(brush: BrushSettings) -> str:
    """The "Streuung" section's line: the jitter and scatter values that are on, else "aus"."""
    dyn = brush.dynamics
    parts = []
    if dyn.jitter_rotation and not brush.tip.round:
        parts.append(f"Drehung ±{dyn.jitter_rotation:.0f}°")
    if dyn.jitter_size:
        parts.append(f"Größe ±{dyn.jitter_size * 100:.0f} %")
    if dyn.jitter_flow:
        parts.append(f"Fluss ±{dyn.jitter_flow * 100:.0f} %")
    if dyn.scatter_across:
        parts.append(f"quer {_radii(dyn.scatter_across)}")
    if dyn.scatter_along:
        parts.append(f"längs {_radii(dyn.scatter_along)}")
    return ", ".join(parts) if parts else "aus"


def spray_summary(brush: BrushSettings) -> str:
    """The "Spray" section's line: density, stamp size, intensity."""
    dyn = brush.dynamics
    return (f"{dyn.spray_density} Stempel, Größe {dyn.spray_size * 100:.0f} %, "
            f"Intensität {dyn.spray_intensity * 100:.0f} %")


def sections(brush: BrushSettings) -> tuple[tuple[str, str, str], ...]:
    """The brush's sections shown now as (key, title, summary): "Spray" only with the spray emitter."""
    summaries = {"stroke": stroke_summary, "scatter": scatter_summary, "spray": spray_summary}
    return tuple((key, title, summaries[key](brush)) for key, title in SECTIONS
                 if key != "spray" or brush.dynamics.spray)


def section_label(title: str, summary: str, open_: bool, key: str) -> str:
    """The header's label: closed it carries the one-line summary (proposal §7 area 4); the ID stays the key's."""
    return f"{title}###{key}" if open_ else f"{title}   {summary}###{key}"


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
    #: the tip's label (Phase 4c: the picker chooses the alpha, `gui.brush_picker_model`)
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
        tip_label=app.paint_brush.tip.label(),
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


__all__ = ["BLENDS", "CURVES", "MENU_CLOSE", "MENU_OPEN", "NO_LAYERS", "SECTIONS", "TITLE", "TOOLS", "LayerRow",
           "PaintPanelState", "menu_label", "scatter_summary", "section_label", "sections", "spray_summary", "state",
           "stroke_summary", "toggle"]
