"""The Weight Room panel's logic (AD-041 §7, slice 2; AD-030: pure logic headless, `weight_panel` only draws).

The panel reads the room's state (`state(app)`) and calls `Application` (`set_weight_brush`, `select_bone`,
`clean_weights_value`, `close_weight_room`, the symmetry and rest / pose keys through `dispatch_command`); it holds no
document state. Labels German, the operation names as in AD-041 (Add / Subtract / Replace / Smooth); every layout choice
`PROVISIONAL`. "Füllen aus Auswahl" (slice 3) and "Gewichte spiegeln" / the L/R pair status (slice 4) join later.
"""

from __future__ import annotations

from dataclasses import dataclass

from mirai.interaction import commands
from mirai.paint.brush import CURVE_ARRAYS, CURVE_LABELS, RADIUS_STEPS_PERCENT
from mirai.skin_weights import CLEAN_THRESHOLD
from mirai.symmetry_axis import current_axis
from mirai.weight_paint import OPERATION_LABELS, OPERATIONS

from . import bone_model as bm

#: The panel's title and the SPACE menu row (W-1: no key).
TITLE = "Weight Room"
MENU_OPEN = "Gewichte malen"
MENU_CLOSE = "Weight Room schließen"
#: The Bone panel's button.
BONE_BUTTON = "Gewichte malen …"
OPERATION_ROWS = tuple((op, OPERATION_LABELS[op]) for op in OPERATIONS)
OPERATION_HINTS = {
    "add": "Aufmalen: der Anteil des Knochens wächst bis 1",
    "subtract": "Wegnehmen: der frei werdende Anteil geht an den Eltern-Knochen (oder ans Objekt)",
    "replace": "Auf einen Wert malen",
    "smooth": "Glätten: zum Mittel der Nachbarn",
}
CURVES = tuple(CURVE_ARRAYS)
#: "Aufräumen"'s threshold range in the panel.
CLEAN_RANGE = (0.001, 0.2)


@dataclass(frozen=True)
class WeightPanelState:
    open: bool
    stroking: bool
    rows: tuple  # bone_model.BoneRow
    current_name: str | None
    blocker: str | None  # why painting is refused now (None = it paints)
    operation: str
    radius_step: int
    flow: float
    opacity: float
    hardness: float
    curve: str
    value: float
    connected: bool
    front_only: bool
    symmetry: str | None  # the edit mesh's symmetry axis, None = off
    posed: bool

    @property
    def radius_label(self) -> str:
        return radius_label(self.radius_step)

    @property
    def can_paint(self) -> bool:
        return self.blocker is None

    @property
    def symmetry_text(self) -> str:
        return "Symmetrie aus" if self.symmetry is None else f"Symmetrie {self.symmetry.upper()}"


def state(app) -> WeightPanelState:
    brush = app.weight_brush
    rig = app.scene.rig
    rows: tuple = ()
    if rig is not None and rig.bones:
        rows = bm.bone_rows(rig, app.current_bone)
    try:
        axis = current_axis(app.scene.mesh)
    except ValueError:
        axis = "?"
    return WeightPanelState(
        open=app.weight_room_open,
        stroking=app.weight_stroking,
        rows=rows,
        current_name=app.current_bone_name,
        blocker=app.weight_paint_blocker,
        operation=brush.operation,
        radius_step=brush.radius_step,
        flow=brush.flow,
        opacity=brush.opacity,
        hardness=brush.hardness,
        curve=brush.curve,
        value=brush.value,
        connected=brush.connected,
        front_only=brush.front_only,
        symmetry=axis,
        posed=app.posed,
    )


def menu_label(app) -> str | None:
    """The SPACE menu row: open / close; None for an eye (it follows its bone by a link, it has no weights)."""
    if app.weight_room_open:
        return MENU_CLOSE
    if app.scene.edit_object.eye is not None:
        return None
    return MENU_OPEN


def toggle(app) -> bool:
    return app.close_weight_room() if app.weight_room_open else app.open_weight_room()


def radius_label(step: int) -> str:
    return f"{RADIUS_STEPS_PERCENT[step]:g} %"


def curve_label(curve: str) -> str:
    return CURVE_LABELS[curve]


def set_operation(app, operation: str) -> bool:
    return app.set_weight_brush(operation=operation)


def choose_bone(app, bone) -> bool:
    return app.select_bone(bone)


def cycle_symmetry(app) -> bool:
    """The symmetry key (`Shift+S`): off -> X -> ... (the edit mesh's definition, one Undo step as the key)."""
    return app.dispatch_command(commands.SYMMETRY_CYCLE)


def toggle_rest(app) -> bool:
    """Rest <-> the last pose (the key `6`; view state)."""
    return app.dispatch_command(commands.POSE_TOGGLE_REST)


def clean(app, threshold: float = CLEAN_THRESHOLD) -> bool:
    return app.clean_weights_value(threshold)


__all__ = ["BONE_BUTTON", "CLEAN_RANGE", "CURVES", "MENU_CLOSE", "MENU_OPEN", "OPERATION_HINTS", "OPERATION_ROWS",
           "TITLE", "WeightPanelState", "choose_bone", "clean", "curve_label", "cycle_symmetry", "menu_label",
           "radius_label", "set_operation", "state", "toggle", "toggle_rest"]
