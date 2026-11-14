"""Lab state of the Eye Proof: every control of audit §5.4 as plain data, the part materials, the camera presets and
the lab-local key table (GL-free; no BindingSet, no `config/keymap.json` entry - D-L9: keys only after the practical
test).

Values marked PROVISIONAL are agent-set starting points for Manu's practical test, not decisions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import numpy as np

from . import eye_math as em
from . import studio_env as se

TECHNIQUES = ("T-A", "T-B", "T-C", "T-D")
CORNEAS = ("C1", "C2", "C3")
ENV_SIZES = (64, 128, 256)
ENV_FORMATS = ("RGBA16F", "RGBM8")
BACKGROUNDS = ("solid", "env")
VIEWS = {"front": (0.0, 0.0), "three_quarter": (35.0, 8.0), "profile": (90.0, 0.0)}
VIEW_ORDER = ("front", "three_quarter", "profile")
#: Every (technique, cornea) the probe times and screenshots; T-A has no cornea treatment of its own (C1 = no cornea,
#: C2 = the production Ghost shell, the closest thing the app can show today).
VARIANTS = (("T-A", "C1"), ("T-A", "C2"),
            *((t, c) for t in TECHNIQUES[1:] for c in CORNEAS))

SOLID_BACKGROUND = (0.06, 0.06, 0.06)  # scene-linear; PROVISIONAL
BACKGROUND_BLUR = 0.6  # roughness of the "env" background; PROVISIONAL
CORNEA_GHOST_ALPHA = 0.25  # T-A + C2 / C3: the production Ghost of the cornea entry


@dataclass(frozen=True)
class SurfaceMaterial:
    """Scene-linear Lookdev material of one part (lab-local; D-L7 decides the product's)."""

    albedo: tuple[float, float, float]
    f0: tuple[float, float, float]
    roughness: float
    spec_weight: float = 1.0


@dataclass
class LabState:
    technique: str = "T-C"
    cornea: str = "C2"
    key_azimuth: float = 35.0  # = the softbox: the direct highlight sits inside its reflection
    key_elevation: float = 25.0
    key_intensity: float = 3.0  # irradiance at normal incidence; PROVISIONAL
    env_on: bool = True
    env_yaw: float = 0.0
    env_intensity: float = 1.0
    exposure_ev: float = 0.0
    sclera_roughness: float = 0.30  # PROVISIONAL
    cornea_roughness: float = 0.04  # PROVISIONAL
    cornea_ior: float = 1.376
    chrome_roughness: float = 0.0
    lod_mapping: int = 0  # eye_math.LOD_MAPPINGS
    env_size: int = 128
    env_format: str = "RGBA16F"
    seamless: bool = True
    tonemap: int = 1  # eye_math.TONEMAPS: Reinhard
    background: str = "solid"
    show_references: bool = True
    view: str = "front"
    env: se.StudioEnv = field(default_factory=lambda: se.DEFAULT_ENV)

    def copy(self, **changes) -> "LabState":
        return replace(self, **changes)

    @property
    def variant(self) -> str:
        return f"{self.technique}_{self.cornea}"

    @property
    def exposure(self) -> float:
        return 2.0 ** self.exposure_ev

    @property
    def cornea_f0(self) -> float:
        return em.f0_from_ior(self.cornea_ior)

    def key_direction(self) -> np.ndarray:
        return se.local_direction(self.key_azimuth, self.key_elevation)

    def key_irradiance(self) -> tuple[float, float, float]:
        return (self.key_intensity,) * 3

    def env_scale(self) -> float:
        return self.env_intensity if self.env_on else 0.0

    def env_rotation(self) -> np.ndarray:
        """World -> environment space: the studio turned by `env_yaw` about +Y (a light at az a appears at a + yaw)."""
        a = math.radians(-self.env_yaw)
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])

    def material(self, part: str) -> SurfaceMaterial:
        f0c = (self.cornea_f0,) * 3
        return {
            "sclera": SurfaceMaterial(tuple(em.srgb_decode((0.86, 0.83, 0.79))), (0.025,) * 3, self.sclera_roughness),
            # The iris itself has no highlight: the wet reflection over it is the cornea's (C1 / C2 / C3).
            "iris": SurfaceMaterial((0.5, 0.5, 0.5), (0.04,) * 3, 0.5, spec_weight=0.0),
            "cornea": SurfaceMaterial((0.0, 0.0, 0.0), f0c, self.cornea_roughness),
            "chrome": SurfaceMaterial((0.0, 0.0, 0.0), (1.0, 1.0, 1.0), self.chrome_roughness),
            "grey": SurfaceMaterial((0.18, 0.18, 0.18), (0.04,) * 3, 0.5),
        }[part]


#: T-A colours (display-referred, as the production material takes them).
WORKLIGHT_COLOURS = {"sclera": (0.86, 0.83, 0.79), "iris": (0.6, 0.6, 0.6), "cornea": (0.85, 0.88, 0.92),
                     "chrome": (0.80, 0.80, 0.82), "grey": tuple(float(v) for v in em.srgb_encode((0.18,) * 3))}


def cycle(values, current, step: int = 1):
    values = tuple(values)
    return values[(values.index(current) + step) % len(values)]


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


#: Lab-local keys (README "Controls"); name -> (help, action(state, shift) -> LabState | None).
KEYS: dict[str, tuple[str, object]] = {}


def _key(name: str, text: str):
    def register(fn):
        KEYS[name] = (text, fn)
        return fn
    return register


for _i, _t in enumerate(TECHNIQUES):
    _key(str(_i + 1), f"technique {_t}")(lambda s, shift, t=_t: s.copy(technique=t))
for _i, _c in enumerate(CORNEAS):
    _key(str(_i + 5), f"cornea {_c}")(lambda s, shift, c=_c: s.copy(cornea=c))
_key("LEFT", "key azimuth -15 / +15 (RIGHT)")(lambda s, shift: s.copy(key_azimuth=s.key_azimuth - 15.0))
_key("RIGHT", "")(lambda s, shift: s.copy(key_azimuth=s.key_azimuth + 15.0))
_key("UP", "key elevation +10 / -10 (DOWN)")(lambda s, shift: s.copy(key_elevation=clamp(s.key_elevation + 10, -80, 80)))
_key("DOWN", "")(lambda s, shift: s.copy(key_elevation=clamp(s.key_elevation - 10, -80, 80)))
_key("K", "key intensity x1.25 (shift: /1.25)")(
    lambda s, shift: s.copy(key_intensity=s.key_intensity / 1.25 if shift else s.key_intensity * 1.25))
_key("E", "environment on / off")(lambda s, shift: s.copy(env_on=not s.env_on))
_key("Y", "environment yaw +15 (shift: -15)")(lambda s, shift: s.copy(env_yaw=s.env_yaw + (-15.0 if shift else 15.0)))
_key("U", "environment intensity x1.25 (shift: /1.25)")(
    lambda s, shift: s.copy(env_intensity=s.env_intensity / 1.25 if shift else s.env_intensity * 1.25))
_key("X", "exposure +0.5 EV (shift: -0.5)")(lambda s, shift: s.copy(exposure_ev=s.exposure_ev + (-0.5 if shift else 0.5)))
_key("S", "sclera roughness +0.05 (shift: -0.05)")(
    lambda s, shift: s.copy(sclera_roughness=round(clamp(s.sclera_roughness + (-0.05 if shift else 0.05), 0, 1), 3)))
_key("C", "cornea roughness +0.01 (shift: -0.01)")(
    lambda s, shift: s.copy(cornea_roughness=round(clamp(s.cornea_roughness + (-0.01 if shift else 0.01), 0, 1), 3)))
_key("I", "cornea IOR +0.02 (shift: -0.02) -> F0")(
    lambda s, shift: s.copy(cornea_ior=round(clamp(s.cornea_ior + (-0.02 if shift else 0.02), 1.0, 2.0), 3)))
_key("G", "chrome roughness sweep 0 / .1 / .25 / .5 / .75 / 1 (shift: back)")(
    lambda s, shift: s.copy(chrome_roughness=cycle((0.0, 0.1, 0.25, 0.5, 0.75, 1.0), s.chrome_roughness,
                                                   -1 if shift else 1)))
_key("L", "roughness -> LOD mapping linear / sqrt")(lambda s, shift: s.copy(lod_mapping=1 - s.lod_mapping))
_key("R", "environment resolution 64 / 128 / 256")(lambda s, shift: s.copy(env_size=cycle(ENV_SIZES, s.env_size)))
_key("F", "environment format RGBA16F / RGBM8")(lambda s, shift: s.copy(env_format=cycle(ENV_FORMATS, s.env_format)))
_key("M", "seamless cube filtering on / off")(lambda s, shift: s.copy(seamless=not s.seamless))
_key("T", "tonemap clamp / Reinhard")(lambda s, shift: s.copy(tonemap=1 - s.tonemap))
_key("B", "background solid / environment")(lambda s, shift: s.copy(background=cycle(BACKGROUNDS, s.background)))
_key("H", "reference spheres on / off")(lambda s, shift: s.copy(show_references=not s.show_references))
_key("V", "camera preset front / 3/4 / profile")(lambda s, shift: s.copy(view=cycle(VIEW_ORDER, s.view)))


def describe(state: LabState) -> list[str]:
    """HUD lines."""
    return [
        f"{state.technique} {state.cornea}   view {state.view}   exposure {state.exposure_ev:+.1f} EV   "
        f"tonemap {em.TONEMAPS[state.tonemap]}   background {state.background}",
        f"key az {state.key_azimuth:.0f} el {state.key_elevation:.0f} E {state.key_intensity:.2f}   "
        f"env {'on' if state.env_on else 'OFF'} yaw {state.env_yaw:.0f} x{state.env_intensity:.2f}",
        f"roughness sclera {state.sclera_roughness:.2f} cornea {state.cornea_roughness:.2f} chrome "
        f"{state.chrome_roughness:.2f}   cornea IOR {state.cornea_ior:.3f} (F0 {state.cornea_f0:.4f})",
        f"cube {state.env_size}^2 {state.env_format} seamless {'on' if state.seamless else 'off'}   "
        f"LOD {em.LOD_MAPPINGS[state.lod_mapping]}",
    ]
