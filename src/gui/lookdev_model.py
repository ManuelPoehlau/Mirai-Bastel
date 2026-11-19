"""The LookDev panel's logic (AD-038 §7; AD-030: pure logic headless, `lookdev_panel` only draws).

The panel reads the room's state (`state(app)`) and calls `Application` (`set_lookdev_studio_preset`,
`set_lookdev_studio`, `set_lookdev_light`, `set_lookdev_material`, `set_lookdev_material_values`, `frame_lookdev`,
`close_lookdev`); it holds no document state. Everything it changes is session state: not saved, no Undo (M1, LD-D12) -
the status row says "nicht gespeichert". About 15 controls are visible; the rest sits under "Mehr". Labels German, every
layout choice `PROVISIONAL` (proposal §3).
"""

from __future__ import annotations

from dataclasses import dataclass

from mirai.lookdev_material import PRESET_NAMES as MATERIAL_PRESETS
from mirai.lookdev_presets import PRESET_NAMES as STUDIO_PRESETS

#: The window's title and the SPACE menu row (no key, D-L9).
TITLE = "LookDev"
MENU_OPEN = "LookDev öffnen"
MENU_CLOSE = "LookDev schließen"
NOT_SAVED = "Material und Studio: nicht gespeichert (M1)"
EYE_NOTE = "Auge - Werte im Panel „Auge“"
LIGHTS = ("key", "fill", "rim")
LIGHT_LABELS = {"key": "Key", "fill": "Fill", "rim": "Rim"}
TONE_LABELS = {"reinhard": "Neutral", "clamp": "Clamp (Diagnose)"}
#: Front / ¾ / Profil: (yaw, pitch) in degrees after framing the edit object.
VIEWS = {"Front": (0.0, 5.0), "¾": (35.0, 8.0), "Profil": (90.0, 5.0)}


@dataclass(frozen=True)
class LightRow:
    name: str
    label: str
    on: bool
    intensity: float
    azimuth: float
    elevation: float
    kelvin: float
    size: float


@dataclass(frozen=True)
class MaterialRow:
    """The material section: the targets' names and the first target's material (None = no organic target)."""

    targets: tuple[str, ...]
    preset: str | None
    adjusted: bool
    base_color: tuple[float, float, float]
    albedo_source: str
    albedo_label: str
    roughness: float
    specular: float
    wrap: float
    backscatter: float
    backscatter_color: tuple[float, float, float]
    #: a selected eye: its values stay in the panel "Auge"
    eye_selected: bool


@dataclass(frozen=True)
class LookdevPanelState:
    open: bool
    preparing: bool
    studio_preset: str
    rotation: float
    env_intensity: float
    exposure: float
    tone_curve: str
    follow_camera: bool
    background: tuple[tuple[float, float, float], tuple[float, float, float]]
    background_gradient: bool
    lights: tuple[LightRow, ...]
    material: MaterialRow | None
    wire: bool
    eye_preview: bool
    status: str


def _albedo_label(app, obj) -> str:
    if app.paint_display.shows(obj):
        return "Bemalung"
    return "Textur" if obj.texture is not None else "Textur (keine)"


def _material(app) -> MaterialRow | None:
    room = app.lookdev
    targets = app.lookdev_material_targets()
    eye_selected = app.lookdev_eye_selected()
    if not targets:
        return None if not eye_selected else MaterialRow((), None, False, (0.5, 0.5, 0.5), "color", "", 0.0, 0.0,
                                                         0.0, 0.0, (1.0, 1.0, 1.0), True)
    first = targets[0]
    m = room.material(first)
    return MaterialRow(tuple(obj.name for obj in targets), m.preset, m.adjusted, m.base_color, m.albedo_source,
                       _albedo_label(app, first), m.roughness, m.specular, m.wrap, m.backscatter, m.backscatter_color,
                       eye_selected)


def state(app) -> LookdevPanelState:
    room = app.lookdev
    s = room.studio
    lights = tuple(LightRow(name, LIGHT_LABELS[name], light.on, light.intensity, light.azimuth, light.elevation,
                            light.kelvin, light.size) for name, light in zip(LIGHTS, s.lights()))
    return LookdevPanelState(
        open=app.lookdev_open, preparing=bool(room.preparing), studio_preset=s.preset, rotation=s.rotation,
        env_intensity=s.env_intensity, exposure=s.exposure, tone_curve=s.tone_curve, follow_camera=s.follow_camera,
        background=s.background, background_gradient=s.background_gradient, lights=lights,
        material=_material(app) if app.lookdev_open else None, wire=app.display.wireframe_overlay,
        eye_preview=app.display.eye_preview,
        status="Shader werden vorbereitet …" if room.preparing else NOT_SAVED,
    )


def menu_label(app) -> str:
    """The SPACE menu row: LookDev can open on any state (it shows pose, morph and SubD as they are, R-1)."""
    return MENU_CLOSE if app.lookdev_open else MENU_OPEN


def toggle(app) -> bool:
    return app.close_lookdev() if app.lookdev_open else app.open_lookdev()


def preset_label(st: LookdevPanelState) -> str:
    return st.studio_preset


def material_label(row: MaterialRow) -> str:
    if row.preset is None:
        return "-"
    return row.preset + (" (angepasst)" if row.adjusted else "")


def targets_label(row: MaterialRow) -> str:
    if not row.targets:
        return EYE_NOTE
    names = ", ".join(row.targets[:3]) + (f" +{len(row.targets) - 3}" if len(row.targets) > 3 else "")
    return names + (f"  ({EYE_NOTE})" if row.eye_selected else "")


__all__ = ["EYE_NOTE", "LIGHTS", "LIGHT_LABELS", "MATERIAL_PRESETS", "MENU_CLOSE", "MENU_OPEN", "NOT_SAVED",
           "STUDIO_PRESETS", "TITLE", "TONE_LABELS", "VIEWS", "LightRow", "LookdevPanelState", "MaterialRow",
           "material_label", "menu_label", "preset_label", "state", "targets_label", "toggle"]
