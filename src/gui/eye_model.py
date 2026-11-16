"""Eye panel and Eye Lab window, pure logic (AD-033 §6; Eye LookDev phase 2, `PROVISIONAL` layout). No pyglet, no
imgui.

Phase 2 (Manu 2026-11-16, I-1..I-3) splits the UI: the compact panel "Auge" keeps eyes on / off, preview and quality,
gaze mode and pad, pupil, look preset and "open in Eye Lab"; every other value is in the Eye Lab window
(`EYE_LAB_SLIDERS`, limbus, refraction, reflection, gaze focus, iris image, saving presets). Both read `state(app)` and
call the same `Application` paths: `set_eye_display` / `set_eyes_shown` / `set_eye_isolate` (view state - no Undo,
not saved), `set_eye_gaze` / `set_eye_gaze_angles` (`mirai.eye_gaze`, view state as well), `preview_eye` while a
slider is held and `set_eye` on its release (one Undo step per change), `apply_eye_preset` and `set_eye_iris_image`.
Neither holds document state. With several eyes selected the values shown are the first eye's; a change goes to all of
them (as the material rows do).

Eye LookDev phase 3: the Eye Lab's section "Reflexe" sets the look values (`LOOK_SLIDERS`, fields "look.<name>" that
`mirai.eye_object.with_changes` merges into each eye's own look); they draw only in the quality "voll".
Eye LookDev phase 4: the section "Iris" sets the iris values (`IRIS_SLIDERS`, fields "look.iris.<name>"), the relief's
height source and "Iris zurücksetzen"; they draw only in the quality "voll" as well.
"""

from __future__ import annotations

from dataclasses import dataclass

from core import SelectionMode

from mirai.eye_gaze import FOCUS_RANGE, GAZE_MODES, PAD_DEGREES
from mirai.eye_object import LOOK_PREFIX, look_value
from viewport.eye_pass import REFLECTIONS, REFRACTIONS, TIERS

LEVEL_LABELS = ("L0 wie P1b", "L1 Farbband", "L2 + Normalen", "L3 + durchscheinend")
COLOUR_SOURCES = ("shader", "image")
REFLECTION_LABELS = {"studio": "Studio + Key", "key": "nur Key-Glanz"}
#: The compact panel's one eye value (I-2): (field, label, min, max, format).
PANEL_SLIDERS = (("pupil_radius", "Pupille", 0.08, 0.30, "%.3f"),)
#: The Eye Lab's anatomy (shapes the shell; never in a panel before phase 2). Ranges `PROVISIONAL`; `EyeSpec` refuses an
#: invalid combination (status line) and the last valid preview stays.
ANATOMY_SLIDERS = (
    ("cornea_radius", "Hornhaut-Radius", 0.52, 0.90, "%.3f"),
    ("limbus_radius", "Limbus-Radius", 0.40, 0.60, "%.3f"),
    ("iris_root_z", "Iris-Tiefe (z)", 0.70, 0.86, "%.3f"),
    ("iris_concavity", "Iris-Wölbung", 0.0, 0.10, "%.3f"),
)
#: The Eye Lab's limbus sliders. Ranges as the eye lab's keys allowed (`PROVISIONAL`).
SLIDERS = (
    ("band_mm", "Bandbreite mm", 0.25, 4.0, "%.2f"),
    ("strength", "Stärke", 0.0, 1.0, "%.2f"),
    ("normal_mm", "Normalen-Übergang mm", 0.1, 2.0, "%.2f"),
    ("falloff", "Durchscheinen (Abfall)", 0.5, 20.0, "%.2f"),
    ("overlap_mm", "Überlappung rundum mm", 0.0, 1.0, "%.2f"),
)

#: Phase 3, the Eye Lab's "Reflexe" (`core.EyeLook`; I-8, I-10). Amounts first (neutral at 0), then what shapes them.
#: Ranges `PROVISIONAL`; `EyeLook` refuses an invalid value (status line).
LOOK_SLIDERS = (
    ("look.wet_sclera", "Nasse Lederhaut", 0.0, 1.0, "%.2f"),
    ("look.irregularity_deg", "Unregelmäßigkeit (Grad)", 0.0, 2.0, "%.2f"),
    ("look.highlight_softness", "Key-Glanz weich", 0.0, 1.0, "%.2f"),
    ("look.lid_shadow", "Lidschatten", 0.0, 1.0, "%.2f"),
    ("look.lid_band", "Lid in der Spiegelung", 0.0, 1.0, "%.2f"),
    ("look.sclera_roughness", "Lederhaut-Rauheit (nass)", 0.03, 0.25, "%.3f"),
    ("look.irregularity_mm", "Unregelmäßigkeit Größe mm", 0.4, 4.0, "%.2f"),
    ("look.lid_shadow_mm", "Lidschatten Breite mm", 0.5, 6.0, "%.2f"),
    ("look.lid_upper", "Oberlid-Kante (Höhe)", 0.0, 0.8, "%.3f"),
    ("look.lid_lower", "Unterlid-Kante (Höhe)", -0.8, 0.0, "%.3f"),
)
LOOK_HINT = "Reflexe zeichnen nur in Qualität 'voll' (das Eye Lab stellt sie beim Öffnen ein)."
#: Phase 4, the Eye Lab's "Iris" (`core.EyeIris`; roadmap #4, #5, #7). Amounts first (neutral at 0), then what shapes
#: them. Ranges `PROVISIONAL`; `EyeIris` refuses an invalid value (status line).
IRIS_SLIDERS = (
    ("look.iris.light", "Key durch die Hornhaut", 0.0, 1.0, "%.2f"),
    ("look.iris.crescent", "Halbmond (1 = berechnet)", 0.0, 2.0, "%.2f"),
    ("look.iris.rim_shadow", "Schatten am Skleralrand", 0.0, 1.0, "%.2f"),
    ("look.iris.relief", "Relief", 0.0, 1.0, "%.2f"),
    ("look.iris.pupil_edge_mm", "Pupillenrand weich mm", 0.0, 0.5, "%.3f"),
    ("look.iris.pupil_margin", "Pupillensaum dunkel", 0.0, 1.0, "%.2f"),
    ("look.iris.rim_shadow_mm", "Randschatten Breite mm", 0.05, 2.0, "%.2f"),
    ("look.iris.relief_mm", "Relief Tiefe mm", 0.02, 0.5, "%.3f"),
)
#: The relief's height source (`EyeIris.relief_source`) as the lab names it.
RELIEF_SOURCE_LABELS = {"luminance": "Höhe aus Helligkeit", "alpha": "Höhe aus Alpha"}
IRIS_HINT = "Iris zeichnet nur in Qualität 'voll'. Den Key mit L-Ziehen bewegen: der Halbmond wandert gegenüber."


def value(spec, field: str):
    """A control's current value: an `EyeSpec` field, or a look value ("look.<name>"; the starting look's while the eye
    has none)."""
    if field.startswith(LOOK_PREFIX):
        return look_value(spec, field[len(LOOK_PREFIX):])
    return getattr(spec, field)


def new_pattern(app) -> bool:
    """Another irregularity pattern for the selected eyes (the look's seed + 1; one Undo step)."""
    eyes = selected_eyes(app)
    if not eyes:
        return False
    return app.set_eye(**{LOOK_PREFIX + "seed": (look_value(eyes[0].eye, "seed") + 1) % (2 ** 31)})


def reset_look(app) -> bool:
    """The selected eyes without a look (neutral, as before phase 3); one Undo step."""
    return app.set_eye(look=None)


def reset_iris(app) -> bool:
    """The selected eyes without iris values (neutral, as before phase 4; the reflections stay); one Undo step."""
    return app.set_eye(**{LOOK_PREFIX + "iris": None})


#: The gaze modes as the panel names them (`mirai.eye_gaze`).
GAZE_LABELS = {"rest": "Eigene Drehung", "camera": "Kamera", "mouse": "Maus", "target": "Fester Punkt"}
assert tuple(GAZE_LABELS) == GAZE_MODES
GAZE_FOCUS_RANGE = FOCUS_RANGE


TIER_LABELS = {"fast": "schnell", "full": "voll"}
assert tuple(TIER_LABELS) == TIERS


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
    tier: str = "fast"
    eyes_shown: bool = True
    isolate: bool = False
    lab_open: bool = False

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
                         gaze.mode, gaze.focus, app.eye_gaze_angles(), len(app._objects.gaze_eyes()),
                         display.eye_tier, display.eyes_shown, display.eye_isolate, app.eye_lab_open)


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


def preview_value(app, field: str, value) -> bool:
    """While a slider is held: the selected eyes drawn with this value (no Undo, nothing saved)."""
    return app.preview_eye(**{field: value})


def end_preview(app) -> bool:
    """A slider let go without a change: back to the eyes' own values."""
    return app.preview_eye()


def preset_names(app) -> list[str]:
    return [preset.name for preset in app.eye_presets()]


def set_view(app, **changes) -> bool:
    assert set(changes) <= {"preview", "reflection", "refraction", "tier"}
    if "reflection" in changes and changes["reflection"] not in REFLECTIONS:
        raise ValueError(changes["reflection"])
    if "refraction" in changes and changes["refraction"] not in REFRACTIONS:
        raise ValueError(changes["refraction"])
    return app.set_eye_display(**changes)
