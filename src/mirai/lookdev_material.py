"""The organic LookDev material (AD-038 §7) - M1: session only, never saved, not in `src/core/` (LD-D12).

`LookMaterial` is one value bundle of the one organic shading model (`viewport.lookdev_pass`, proposal §4): an sRGB
artist colour, where the albedo comes from (`texture`: the object's shown texture or paint composite; `color`: the
colour), perceptual roughness (alpha = r²), the specular *level* (F0 = 0.08 x level; 0.5 -> 0.04), the diffuse wrap
(softness; the preset fixes its per-channel tint) and the backscatter with its colour.

Six presets (`PRESETS`, values `PROVISIONAL`, tuned in the M1 practical test). An object without a session row is drawn
**Neutral** (Manu 2026-11-19, AD-038 §15 Q3): nothing is guessed from object names. Its albedo is then the shown texture
or paint composite when it has UVs and one, else `ObjectMaterial.base_color` read as a colour only, else the Worklight's
`DEFAULT_BASE_COLOR`; `glossiness` is never read as roughness, nor `specular` as F0 (proposal §4.3).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

ALBEDO_SOURCES = ("texture", "color")


@dataclass(frozen=True)
class LookMaterial:
    preset: str
    base_color: tuple[float, float, float]
    albedo_source: str = "texture"
    roughness: float = 0.6
    specular: float = 0.5
    wrap: float = 0.0
    wrap_tint: tuple[float, float, float] = (1.0, 1.0, 1.0)
    backscatter: float = 0.0
    backscatter_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    #: True once a value was changed after the preset was picked ("angepasst", proposal §4.2)
    adjusted: bool = False

    def __post_init__(self) -> None:
        if self.albedo_source not in ALBEDO_SOURCES:
            raise ValueError(f"albedo_source: {ALBEDO_SOURCES}")
        for name in ("roughness", "specular", "wrap", "backscatter"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name}: needs 0 <= value <= 1, got {value}")
        for name in ("base_color", "wrap_tint", "backscatter_color"):
            colour = getattr(self, name)
            if len(colour) != 3 or not all(0.0 <= c <= 1.0 for c in colour):
                raise ValueError(f"{name}: three values in 0 .. 1")

    @property
    def f0(self) -> float:
        return 0.08 * self.specular

    def wrap_rgb(self) -> tuple[float, float, float]:
        return tuple(self.wrap * t for t in self.wrap_tint)

    def with_(self, **changes) -> "LookMaterial":
        """A copy with `changes`; a value change marks it "angepasst" (the preset name stays)."""
        values = {k: v for k, v in changes.items() if k not in ("preset", "adjusted")}
        adjusted = self.adjusted or any(getattr(self, k) != v for k, v in values.items())
        return dataclasses.replace(self, **changes, adjusted=changes.get("adjusted", adjusted))


NEUTRAL = "Neutral"
#: The six presets (proposal §4.1; `PROVISIONAL`). Creature Skin is the Gollum candidate; Neutral the fallback (clay).
PRESETS: dict[str, LookMaterial] = {
    "Creature Skin": LookMaterial("Creature Skin", (0.62, 0.52, 0.44), "texture", roughness=0.5, specular=0.35,
                                  wrap=0.3, wrap_tint=(1.0, 0.65, 0.5), backscatter=0.15,
                                  backscatter_color=(1.0, 0.45, 0.3)),
    "Wet Skin": LookMaterial("Wet Skin", (0.62, 0.45, 0.42), "texture", roughness=0.25, specular=0.35, wrap=0.3,
                             wrap_tint=(1.0, 0.65, 0.5), backscatter=0.1, backscatter_color=(1.0, 0.45, 0.3)),
    "Zähne": LookMaterial("Zähne", (0.85, 0.80, 0.68), "color", roughness=0.3, specular=0.5, wrap=0.1,
                          wrap_tint=(1.0, 0.9, 0.8), backscatter=0.1, backscatter_color=(1.0, 0.8, 0.6)),
    "Mundinneres": LookMaterial("Mundinneres", (0.55, 0.22, 0.22), "texture", roughness=0.3, specular=0.35, wrap=0.5,
                                wrap_tint=(1.0, 0.5, 0.45), backscatter=0.3, backscatter_color=(1.0, 0.3, 0.25)),
    "Organisch": LookMaterial("Organisch", (0.6, 0.55, 0.5), "texture", roughness=0.55, specular=0.5, wrap=0.1),
    NEUTRAL: LookMaterial(NEUTRAL, (0.5, 0.5, 0.5), "texture", roughness=0.6, specular=0.5),
}
PRESET_NAMES = tuple(PRESETS)


def preset(name: str) -> LookMaterial:
    try:
        return PRESETS[name]
    except KeyError:
        raise ValueError(f"LookDev material: no preset {name!r} ({', '.join(PRESET_NAMES)})") from None


def fallback(base_color: tuple[float, float, float] | None, default: tuple[float, float, float]) -> LookMaterial:
    """Neutral for an object without a session row: its `ObjectMaterial.base_color` as the colour (else `default`)."""
    colour = tuple(float(c) for c in (base_color if base_color is not None else default))
    return dataclasses.replace(PRESETS[NEUTRAL], base_color=colour)
