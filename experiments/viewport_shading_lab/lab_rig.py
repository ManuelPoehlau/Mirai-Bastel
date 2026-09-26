"""Two-light worklight rig (Key + Fill) — GL-free state, math and presets.

Handoff WP-SHADE-LAB-01 Slice 1, E3/E5–E10/E12. Spec source:
`docs/research/viewport/VIEWPORT_SHADING_FORM_PERCEPTION_RESEARCH.md` §4.1a.

- `LightRig` holds every rig parameter (plain data, no GL, no camera).
- `resolve(rig, camera)` turns it into the shader uniforms (world-space unit
  directions, premultiplied colors, wraps, ambient). Called per frame; CPU
  only, a handful of trig calls — no geometry, no buffer upload.
- `shade(normal, uniforms, base_color)` is the pure-Python reference of the
  fragment formula in `lab_store.FRAGMENT_SRC`. The two must stay in sync:
  change one, change the other (`tests/test_rig_math.py` pins `shade()`,
  `tests/test_lab_store_gl.py` pins the shader against the production one).

The rig is deliberately not a `ResourceStore` resource and never goes through
`RenderMesh` (E3): `ShadingLabStore` receives the resolved dict and sets the
uniforms at draw time only.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Optional

Vec3 = tuple[float, float, float]

SPACE_CAMERA = "camera"
SPACE_WORLD = "world"

#: Key:Fill ratio steps (E7); `None` = fill off ("aus").
RATIO_STEPS: tuple[Optional[float], ...] = (1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, None)

KELVIN_MIN = 2500.0
KELVIN_MAX = 10000.0
#: Reference white of the temperature conversion (E8: 6500 K ≈ neutral).
KELVIN_NEUTRAL = 6500.0
WRAP_MIN, WRAP_MAX = 0.0, 1.0
AMBIENT_MIN, AMBIENT_MAX = 0.0, 0.6
ELEVATION_MIN, ELEVATION_MAX = -90.0, 90.0

#: Rec. 709 luminance weights (= Y row of the linear Rec. 709 → XYZ matrix).
REC709_LUMA: Vec3 = (0.2126, 0.7152, 0.0722)


@dataclass(frozen=True)
class LightRig:
    """All Slice-1 rig parameters. Angles in degrees, temperatures in Kelvin."""

    space: str = SPACE_CAMERA
    key_azimuth: float = 0.0
    key_elevation: float = 0.0
    key_intensity: float = 0.65
    key_kelvin: float = KELVIN_NEUTRAL
    key_wrap: float = 0.0
    fill_coupled: bool = True
    #: Only used when `fill_coupled` is False (E6).
    fill_azimuth: float = 180.0
    fill_elevation: float = 0.0
    #: Key:Fill; `None` = fill off.
    fill_ratio: Optional[float] = 2.0
    fill_kelvin: float = KELVIN_NEUTRAL
    fill_wrap: float = 0.0
    ambient: float = 0.35

    def to_dict(self) -> dict:
        return asdict(self)

    def with_(self, **changes) -> "LightRig":
        return replace(self, **changes)

    # -- derived values ------------------------------------------------------

    @property
    def fill_enabled(self) -> bool:
        return self.fill_ratio is not None

    @property
    def fill_intensity(self) -> float:
        """E7: `key_intensity / ratio`; 0 when the fill is off."""
        if self.fill_ratio is None:
            return 0.0
        return self.key_intensity / self.fill_ratio

    def effective_fill_angles(self) -> tuple[float, float]:
        """(azimuth, elevation) of the fill; coupled = diagonally opposite and below (E6)."""
        if self.fill_coupled:
            return coupled_fill_angles(self.key_azimuth, self.key_elevation)
        return self.fill_azimuth, self.fill_elevation

    def exposure_sum(self) -> float:
        """E11: `ambient + key + fill` (colors are luminance-normalized, so the
        intensities are the luminance contributions at N·L = 1)."""
        return self.ambient + self.key_intensity + self.fill_intensity


# -- small vector helpers --------------------------------------------------------------------


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _scale(v, s: float) -> Vec3:
    return (v[0] * s, v[1] * s, v[2] * s)


def _normalize(v) -> Vec3:
    length = math.sqrt(_dot(v, v))
    if length == 0.0:
        return (0.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


# -- direction math (E5, E6) --------------------------------------------------


def wrap_degrees(angle: float) -> float:
    """Maps an angle to (-180, 180]."""
    a = math.fmod(angle, 360.0)
    if a <= -180.0:
        a += 360.0
    elif a > 180.0:
        a -= 360.0
    return a


def coupled_fill_angles(key_azimuth: float, key_elevation: float) -> tuple[float, float]:
    """E6 (Raitt/Minter): `az_fill = az_key + 180°`, `el_fill = −el_key`."""
    return wrap_degrees(key_azimuth + 180.0), -key_elevation


def local_direction(azimuth: float, elevation: float) -> Vec3:
    """E5: `(cos el · sin az, sin el, cos el · cos az)` in a frame (X, Y, Z)."""
    az = math.radians(azimuth)
    el = math.radians(elevation)
    ce = math.cos(el)
    return (ce * math.sin(az), math.sin(el), ce * math.cos(az))


def angles_from_direction(direction: Vec3) -> tuple[float, float]:
    """Inverse of `local_direction` (for expressing a fixed vector as az/el)."""
    x, y, z = _normalize(direction)
    return math.degrees(math.atan2(x, z)), math.degrees(math.asin(max(-1.0, min(1.0, y))))


def frame_for(space: str, camera) -> tuple[Vec3, Vec3, Vec3]:
    """(X, Y, Z) frame: world axes, or (`right`, `up`, `-forward`) of the camera
    so that az 0 / el 0 points from the object toward the viewer (E5).
    `camera` is duck-typed (`basis() -> (forward, right, up)`, `OrbitCamera`)."""
    if space == SPACE_WORLD:
        return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
    if space != SPACE_CAMERA:
        raise ValueError(f"unknown space {space!r}")
    forward, right, up = camera.basis()
    return tuple(right), tuple(up), (-forward[0], -forward[1], -forward[2])


def world_direction(azimuth: float, elevation: float, frame: tuple[Vec3, Vec3, Vec3]) -> Vec3:
    lx, ly, lz = local_direction(azimuth, elevation)
    fx, fy, fz = frame
    return _normalize(tuple(lx * fx[i] + ly * fy[i] + lz * fz[i] for i in range(3)))


# -- temperature (E8) -----------------------------------------------------------


def _planckian_xy(kelvin: float) -> tuple[float, float]:
    """CIE 1931 xy of a black body; cubic-spline fit of Kim et al. (2002),
    "Design of Advanced Color Temperature Control System for HDTV
    Applications", J. Korean Phys. Soc. 41(6), valid 1667–25000 K."""
    t = 1000.0 / kelvin
    if kelvin <= 4000.0:
        x = -0.2661239 * t**3 - 0.2343589 * t**2 + 0.8776956 * t + 0.179910
    else:
        x = -3.0258469 * t**3 + 2.1070379 * t**2 + 0.2226347 * t + 0.240390
    if kelvin <= 2222.0:
        y = -1.1063814 * x**3 - 1.34811020 * x**2 + 2.18555832 * x - 0.20219683
    elif kelvin <= 4000.0:
        y = -0.9549476 * x**3 - 1.37418593 * x**2 + 2.09137015 * x - 0.16748867
    else:
        y = 3.0817580 * x**3 - 5.87338670 * x**2 + 3.75112997 * x - 0.37001483
    return x, y


def _planckian_linear_rec709(kelvin: float) -> Vec3:
    """xy (Y = 1) → XYZ → linear Rec. 709 (sRGB primaries, D65 matrix, IEC 61966-2-1)."""
    x, y = _planckian_xy(kelvin)
    X, Y, Z = x / y, 1.0, (1.0 - x - y) / y
    return (
        3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z,
        -0.9692660 * X + 1.8760108 * Y + 0.0415560 * Z,
        0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z,
    )


_NEUTRAL_RGB = _planckian_linear_rec709(KELVIN_NEUTRAL)


def luminance(rgb: Vec3) -> float:
    return sum(w * c for w, c in zip(REC709_LUMA, rgb))


def kelvin_to_rgb(kelvin: float) -> Vec3:
    """Black-body color for `kelvin`, white-balanced to 6500 K and normalized
    to Rec. 709 luminance 1 (E8: temperature changes hue, never brightness).

    Method: Planckian locus xy after Kim et al. (2002) → linear Rec. 709 →
    per-channel division by the 6500 K result (von-Kries-style white balance,
    so 6500 K is exactly neutral — the raw 6500 K black body is ~4 % magenta
    against the D65 white of Rec. 709, which would break the "Heute" baseline
    identity T1) → divide by Rec. 709 luminance. Values are clamped to
    2500–10000 K. No gamma: the viewport shader works on display values
    directly, like production.
    """
    k = max(KELVIN_MIN, min(KELVIN_MAX, float(kelvin)))
    raw = _planckian_linear_rec709(k)
    balanced = tuple(max(c / n, 0.0) for c, n in zip(raw, _NEUTRAL_RGB))
    lum = luminance(balanced)
    return tuple(c / lum for c in balanced)


# -- resolve (E3) ------------------------------------------------------------------


def resolve(rig: LightRig, camera=None) -> dict:
    """Shader uniforms for `rig`. `camera` is only read in camera space.

    Returns `u_key_dir`/`u_fill_dir` (world-space unit vectors),
    `u_key_color`/`u_fill_color` (normalized RGB × intensity; fill off =
    `(0, 0, 0)`), `u_key_wrap`/`u_fill_wrap` and `u_ambient`.
    """
    frame = frame_for(rig.space, camera)
    key_dir = world_direction(rig.key_azimuth, rig.key_elevation, frame)
    fill_az, fill_el = rig.effective_fill_angles()
    fill_dir = world_direction(fill_az, fill_el, frame)
    key_color = _scale(kelvin_to_rgb(rig.key_kelvin), rig.key_intensity)
    if rig.fill_enabled:
        fill_color = _scale(kelvin_to_rgb(rig.fill_kelvin), rig.fill_intensity)
    else:
        fill_color = (0.0, 0.0, 0.0)
    return {
        "u_key_dir": key_dir,
        "u_key_color": key_color,
        "u_key_wrap": float(rig.key_wrap),
        "u_fill_dir": fill_dir,
        "u_fill_color": fill_color,
        "u_fill_wrap": float(rig.fill_wrap),
        "u_ambient": float(rig.ambient),
    }


# -- reference formula (E4) -------------------------------------------------------------


def wrap_term(ndl: float, w: float) -> float:
    """GLSL `wrap()` in `lab_store.FRAGMENT_SRC`; `w = 0` is plain clamped Lambert."""
    return max((ndl + w) / (1.0 + w), 0.0)


def shade(normal: Vec3, uniforms: dict, base_color: Vec3, highlight: float = 0.0) -> Vec3:
    """Pure-Python mirror of `lab_store.FRAGMENT_SRC` (keep both in sync).

    Returns the unclamped fragment color; GL clamps to [0, 1] on output.
    """
    n = _normalize(normal)
    k = wrap_term(_dot(n, uniforms["u_key_dir"]), uniforms["u_key_wrap"])
    f = wrap_term(_dot(n, uniforms["u_fill_dir"]), uniforms["u_fill_wrap"])
    ambient = uniforms["u_ambient"]
    light = tuple(
        ambient + uniforms["u_key_color"][i] * k + uniforms["u_fill_color"][i] * f
        for i in range(3)
    )
    shaded = tuple(base_color[i] * light[i] for i in range(3))
    h = max(0.0, min(1.0, highlight))
    highlight_color = (1.0, 0.82, 0.15)
    return tuple(shaded[i] * (1.0 - h) + highlight_color[i] * h for i in range(3))


# -- presets (E12) — agent starting points, not artist recommendations -----------------

#: Production `LIGHT_DIR` (0.4, 0.6, 0.7), expressed as az/el (E12 F1).
HEUTE_KEY_AZIMUTH, HEUTE_KEY_ELEVATION = angles_from_direction((0.4, 0.6, 0.7))

PRESET_HEUTE = "Heute"
PRESET_RAITT = "Raitt 2:1"
PRESET_SOFTBOX = "Softbox"
PRESET_WARM_COLD = "Warm/Kalt"

_RAITT = LightRig(
    space=SPACE_CAMERA,
    key_azimuth=-45.0,
    key_elevation=35.0,
    # ambient + key + key/2 = 1  →  key = (1 − 0.10) / 1.5
    key_intensity=0.6,
    key_kelvin=KELVIN_NEUTRAL,
    key_wrap=0.0,
    fill_coupled=True,
    fill_azimuth=135.0,
    fill_elevation=-35.0,
    fill_ratio=2.0,
    fill_kelvin=KELVIN_NEUTRAL,
    fill_wrap=0.0,
    ambient=0.10,
)

PRESETS: dict[str, LightRig] = {
    PRESET_HEUTE: LightRig(
        space=SPACE_WORLD,
        key_azimuth=HEUTE_KEY_AZIMUTH,
        key_elevation=HEUTE_KEY_ELEVATION,
        key_intensity=0.65,
        key_kelvin=KELVIN_NEUTRAL,
        key_wrap=0.0,
        fill_coupled=True,
        fill_ratio=None,
        fill_kelvin=KELVIN_NEUTRAL,
        fill_wrap=0.0,
        ambient=0.35,
    ),
    PRESET_RAITT: _RAITT,
    PRESET_SOFTBOX: _RAITT.with_(key_wrap=0.5, fill_wrap=0.8),
    PRESET_WARM_COLD: _RAITT.with_(key_kelvin=4500.0, fill_kelvin=8000.0),
}

#: F1–F4 in this order (E12).
PRESET_ORDER: tuple[str, ...] = (PRESET_HEUTE, PRESET_RAITT, PRESET_SOFTBOX, PRESET_WARM_COLD)

