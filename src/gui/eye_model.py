"""Eye panel, pure logic (AD-033 §6, `PROVISIONAL` layout). No pyglet, no imgui.

The panel reads `state(app)` and calls the same `Application` paths as everything else: `set_eye_display` (view state:
preview, reflection, refraction - no Undo, not saved), `set_eye_gaze` / `set_eye_gaze_angles` (where every eye looks,
`mirai.eye_gaze`, view state as well), `set_eye` (the selected eyes' values, one Undo step per change)
and `set_eye_iris_image`. It holds no document state. With several eyes selected the values shown are the first
eye's; a change goes to all of them (as the material rows do).
"""

from __future__ import annotations

from dataclasses import dataclass

from core import SelectionMode

from mirai.eye_gaze import FOCUS_RANGE, GAZE_MODES, PAD_DEGREES
from viewport.eye_pass import REFLECTIONS, REFRACTIONS

LEVEL_LABELS = ("L0 wie P1b", "L1 Farbband", "L2 + Normalen", "L3 + durchscheinend")
COLOUR_SOURCES = ("shader", "image")
REFLECTION_LABELS = {"studio": "Studio + Key", "key": "nur Key-Glanz"}
#: The panel's sliders: (field, label, min, max, format). Ranges as the eye lab's keys allowed (`PROVISIONAL`).
SLIDERS = (
    ("pupil_radius", "Pupille", 0.08, 0.30, "%.3f"),
    ("band_mm", "Bandbreite mm", 0.25, 4.0, "%.2f"),
    ("strength", "Stärke", 0.0, 1.0, "%.2f"),
    ("normal_mm", "Normalen-Übergang mm", 0.1, 2.0, "%.2f"),
    ("falloff", "Durchscheinen (Abfall)", 0.5, 20.0, "%.2f"),
    ("overlap_mm", "Überlappung rundum mm", 0.0, 1.0, "%.2f"),
)


#: The gaze modes as the panel names them (`mirai.eye_gaze`).
GAZE_LABELS = {"rest": "Eigene Drehung", "camera": "Kamera", "mouse": "Maus", "target": "Fester Punkt"}
assert tuple(GAZE_LABELS) == GAZE_MODES
GAZE_FOCUS_RANGE = FOCUS_RANGE


@dataclass(frozen=True)
class EyePanelState:
    eyes: tuple  # the selected eye objects
    preview: bool
    reflection: str
    refraction: str
    gaze_mode: str = "rest"
    gaze_focus: float = 25.0
    gaze_angles: tuple[float, float] | None = None  # (yaw, pitch) degrees the eyes look at now, None = own rotation
    scene_eyes: int = 0  # how many eyes the gaze turns

    @property
    def gaze_dot(self) -> tuple[float, float] | None:
        """Where the gaze pad shows the current gaze: (x, y) in -1..1 (right, up), clamped to the pad's edge."""
        if self.gaze_angles is None:
            return None
        yaw, pitch = self.gaze_angles
        clamp = lambda v: max(-1.0, min(1.0, v))  # noqa: E731
        return clamp(yaw / PAD_DEGREES[0]), clamp(pitch / PAD_DEGREES[1])

    @property
    def has_eyes(self) -> bool:
        return bool(self.eyes)

    @property
    def spec(self):
        return self.eyes[0].eye if self.eyes else None

    @property
    def header(self) -> str:
        if not self.eyes:
            return "Kein Auge gewählt (Modus 4, Auge anklicken)"
        names = ", ".join(obj.name for obj in self.eyes[:3]) + (" ..." if len(self.eyes) > 3 else "")
        return f"Auge: {names}"

    @property
    def image_text(self) -> str:
        if not self.eyes:
            return ""
        texture = self.eyes[0].texture
        if texture is None:
            return "Iris: berechnet (kein eigenes Bild)"
        name = texture.replace("\\", "/").rsplit("/", 1)[-1]
        spec = self.spec
        fit = "planar" if spec.fit_pupil is None else (
            f"Anpassung {spec.fit_pupil:g} / {spec.fit_limbus:g}" + (", Rand gehalten" if spec.hold_outer_color else ""))
        return f"Iris: {name} ({fit})"


def selected_eyes(app) -> tuple:
    """The selected eyes in mode `4` (a selected group stands for its members), in id order."""
    if app.selection.mode is not SelectionMode.OBJECT:
        return ()
    from mirai.scene_objects import group_leaves  # noqa: PLC0415 - gui reads through the app's own helper

    return tuple(obj for obj in group_leaves(app.scene, app.selection.objects) if obj.eye is not None)


def state(app) -> EyePanelState:
    display = app.display
    gaze = display.eye_gaze
    return EyePanelState(selected_eyes(app), display.eye_preview, display.eye_reflection, display.eye_refraction,
                         gaze.mode, gaze.focus, app.eye_gaze_angles(), len(app._objects.gaze_eyes()))


def set_gaze(app, **changes) -> bool:
    """The gaze mode / focus (view state, no Undo): `Application.set_eye_gaze`."""
    assert set(changes) <= {"mode", "focus"}
    return app.set_eye_gaze(**changes)


def set_gaze_pad(app, x: float, y: float) -> bool:
    """A point on the gaze pad, (x, y) in -1..1 (right, up as seen facing the eyes): the eyes look there (mode
    "target")."""
    x, y = max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y))
    return app.set_eye_gaze_angles(x * PAD_DEGREES[0], y * PAD_DEGREES[1])


def set_value(app, field: str, value) -> bool:
    """One eye value on every selected eye (one Undo step); refused with the reason in the status line."""
    return app.set_eye(**{field: value})


def set_view(app, **changes) -> bool:
    assert set(changes) <= {"preview", "reflection", "refraction"}
    if "reflection" in changes and changes["reflection"] not in REFLECTIONS:
        raise ValueError(changes["reflection"])
    if "refraction" in changes and changes["refraction"] not in REFRACTIONS:
        raise ValueError(changes["refraction"])
    return app.set_eye_display(**changes)
