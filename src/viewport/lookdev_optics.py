"""NumPy twins of `lookdev_shaders` (AD-038 §6) and the LookDev frame dict - GL-free, the `eye_optics` <-> `eye_shaders`
pattern (parity: `tests/test_gl_lookdev_parity.py`, `tests/test_lookdev_optics.py`).

- `Studio`: the parametric analytic studio (dome + at most 4 soft rectangles), the eye's `td_env` with its constants as
  values. `EYE_STUDIO` is the eye's own; `ld_studio(d, r, EYE_STUDIO) == eye_optics.td_env(d, r)`.
- `sh9_project(studio)`: SH9 irradiance / pi over 4,096 Fibonacci directions - so a Lambert albedo times `sh9_eval(n)`
  is the diffuse light. Cached by the studio's *content* (`project_cached`); intensity and rotation are uniforms.
- `srgb_decode` / `srgb_encode`, the tone curves, `lookdev_output` (exposure -> tone -> encode).
- `ld_diffuse` / `ld_specular`: the three lights (key, fill, rim) as the shader evaluates them.
- `frame_uniforms(state, camera)`: one dict per frame for the skin pass and the eye's LOOKDEV variant, the pattern of
  `Viewport.light_uniforms()`. `state` is a `LookdevState` (the session studio, `mirai.lookdev_presets`).

World frame as `light_rig` (Y up, the model faces +Z, azimuth from +Z toward +X). The studio's frame turns by
`rotation` degrees about Y; with "Licht folgt Kamera" it is the camera's (`right`, `up`, `-forward`), as
`light_rig.frame_for(SPACE_CAMERA)`. Lights and rectangles are given in that frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import eye_optics as eo
from .light_rig import kelvin_to_rgb
from .lookdev_shaders import MAX_STUDIO, TONE_CURVES

LUMA = np.array([0.2126, 0.7152, 0.0722])
SH_DIRECTIONS = 4096
LIGHT_NAMES = ("key", "fill", "rim")


# -- colour ------------------------------------------------------------------------------------------------------------

def srgb_decode(c) -> np.ndarray:
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb_encode(c) -> np.ndarray:
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1.0 / 2.4) - 0.055)


def tone(c, curve: str = "reinhard") -> np.ndarray:
    """The tone curve on linear rgb (..., 3): luminance Reinhard (hue-preserving; the M1 default) or a clamp."""
    c = np.asarray(c, dtype=np.float64)
    if curve == "clamp":
        return np.clip(c, 0.0, 1.0)
    return c / (1.0 + np.sum(c * LUMA, axis=-1, keepdims=True))


def lookdev_output(c, exposure: float = 1.0, curve: str = "reinhard") -> np.ndarray:
    """Linear rgb -> the display value: exposure (a factor, 2^EV), the tone curve, sRGB encode - once per pixel."""
    return srgb_encode(tone(np.maximum(np.asarray(c, dtype=np.float64), 0.0) * exposure, curve))


# -- the parametric studio ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Softbox:
    """One studio rectangle: azimuth / elevation of its centre and half width / height (degrees, studio frame), its
    linear radiance."""

    azimuth: float
    elevation: float
    half_width: float
    half_height: float
    radiance: tuple[float, float, float]


@dataclass(frozen=True)
class Studio:
    """The studio's content: the dome (zenith, horizon, floor, linear) and its rectangles. Hashable: the SH9 cache key."""

    zenith: tuple[float, float, float]
    horizon: tuple[float, float, float]
    floor: tuple[float, float, float]
    softboxes: tuple[Softbox, ...] = ()
    horizon_width: float = eo.STUDIO_HORIZON_WIDTH
    edge_sigma: float = eo.STUDIO_EDGE_SIGMA

    def __post_init__(self) -> None:
        if len(self.softboxes) > MAX_STUDIO:
            raise ValueError(f"at most {MAX_STUDIO} studio rectangles")

    def frames(self) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, tuple[float, float], tuple]]:
        """(centre, right, up, (half width, half height) in radians, radiance) per rectangle, as
        `eye_optics.studio_frames`."""
        out = []
        for box in self.softboxes:
            c = eo.local_direction(box.azimuth, box.elevation)
            right = np.cross(np.array([0.0, 1.0, 0.0]), c)
            right /= np.linalg.norm(right)
            out.append((c, right, np.cross(c, right), (math.radians(box.half_width), math.radians(box.half_height)),
                        tuple(box.radiance)))
        return out


#: The eye's studio (`eye_optics` constants) as a `Studio`.
EYE_STUDIO = Studio(tuple(eo.STUDIO_ZENITH), tuple(eo.STUDIO_HORIZON), tuple(eo.STUDIO_FLOOR),
                    tuple(Softbox(az, el, hw, hh, tuple(rad)) for az, el, hw, hh, rad in eo.STUDIO_LIGHTS))


def ld_studio(d, roughness: float, studio: Studio) -> np.ndarray:
    """Linear radiance (..., 3) of `studio` toward unit directions `d` (studio frame), as a lobe of `roughness` sees it
    (GLSL `ld_studio`)."""
    d = np.asarray(d, dtype=np.float64)
    lobe = eo.TD_SIGMA_SCALE * (roughness * roughness) ** eo.TD_SIGMA_POWER
    sigma = math.sqrt(studio.edge_sigma ** 2 + lobe ** 2)
    width = math.sqrt(studio.horizon_width ** 2 + lobe ** 2)
    y = d[..., 1]
    zenith, horizon, floor = (np.asarray(c, dtype=np.float64) for c in (studio.zenith, studio.horizon, studio.floor))
    sky = horizon + (zenith - horizon) * np.clip(y, 0, 1)[..., None]
    t = np.clip((y + width) / (2.0 * width), 0.0, 1.0)
    out = floor + (sky - floor) * (t * t * (3.0 - 2.0 * t))[..., None]
    for c, right, up, (hw, hh), radiance in studio.frames():
        dc = np.sum(d * c, axis=-1)
        x = np.arctan2(np.sum(d * right, axis=-1), dc + 1e-12)
        yy = np.arctan2(np.sum(d * up, axis=-1), dc + 1e-12)
        s = np.clip(dc / 0.25, 0.0, 1.0)
        w = eo._box(x, hw, sigma) * eo._box(yy, hh, sigma) * (s * s * (3.0 - 2.0 * s))
        out = out + w[..., None] * np.asarray(radiance, dtype=np.float64)
    return out


# -- SH9 ---------------------------------------------------------------------------------------------------------------

SH_BAND = np.array([math.pi] + [2.0 * math.pi / 3.0] * 3 + [math.pi / 4.0] * 5)


def sh9_basis(d) -> np.ndarray:
    """The 9 real SH basis functions at unit directions `d` (..., 3) -> (..., 9), in the order `sh9()` reads."""
    d = np.asarray(d, dtype=np.float64)
    x, y, z = d[..., 0], d[..., 1], d[..., 2]
    return np.stack([np.full_like(x, 0.282095), 0.488603 * y, 0.488603 * z, 0.488603 * x, 1.092548 * x * y,
                     1.092548 * y * z, 0.315392 * (3.0 * z * z - 1.0), 1.092548 * x * z,
                     0.546274 * (x * x - y * y)], axis=-1)


def fibonacci_directions(count: int) -> np.ndarray:
    i = np.arange(count) + 0.5
    z = 1.0 - 2.0 * i / count
    r = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    phi = math.pi * (3.0 - math.sqrt(5.0)) * i
    return np.stack([r * np.cos(phi), r * np.sin(phi), z], axis=-1)


def sh9_project(studio: Studio, count: int = SH_DIRECTIONS) -> np.ndarray:
    """SH9 irradiance / pi of the studio (its sharp radiance, roughness 0): projected over `count` Fibonacci
    directions, convolved with the clamped cosine (pi, 2pi/3, pi/4), divided by pi. (9, 3)."""
    d = fibonacci_directions(count)
    coeffs = sh9_basis(d).T @ ld_studio(d, 0.0, studio) * (4.0 * math.pi / count)
    return coeffs * SH_BAND[:, None] / math.pi


def sh9_eval(sh, n) -> np.ndarray:
    """GLSL `sh9(n)`: (..., 3) at unit normals `n` (studio frame)."""
    return sh9_basis(n) @ np.asarray(sh, dtype=np.float64)


_SH_CACHE: dict = {}


def project_cached(studio: Studio) -> np.ndarray:
    """`sh9_project` once per studio content (a preset or an edit of the studio itself, AD-038 §6)."""
    sh = _SH_CACHE.get(studio)
    if sh is None:
        if len(_SH_CACHE) > 16:
            _SH_CACHE.clear()
        sh = _SH_CACHE[studio] = sh9_project(studio)
    return sh


# -- the lights --------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class StudioLight:
    """Key, fill or rim: on, intensity (relative), direction in the studio frame (degrees), colour (Kelvin) and size
    (added to the specular alpha: the highlight's softness)."""

    on: bool = True
    intensity: float = 1.0
    azimuth: float = 0.0
    elevation: float = 0.0
    kelvin: float = 6500.0
    size: float = 0.1

    def colour(self) -> tuple[float, float, float]:
        if not self.on:
            return (0.0, 0.0, 0.0)
        return tuple(float(c) * self.intensity for c in kelvin_to_rgb(self.kelvin))


@dataclass(frozen=True)
class LookdevState:
    """The session studio (AD-038 §6): preset name, rotation (degrees about the vertical), environment intensity,
    exposure (EV), tone curve, the three lights, "Licht folgt Kamera", the studio content and the background (display
    values as picked: solid = bottom == top)."""

    preset: str
    studio: Studio
    key: StudioLight
    fill: StudioLight
    rim: StudioLight
    rotation: float = 0.0
    env_intensity: float = 1.0
    exposure: float = 0.0
    tone_curve: str = "reinhard"
    follow_camera: bool = False
    background: tuple[tuple[float, float, float], tuple[float, float, float]] = ((0.1, 0.1, 0.11), (0.1, 0.1, 0.11))
    background_gradient: bool = False

    def __post_init__(self) -> None:
        if self.tone_curve not in TONE_CURVES:
            raise ValueError(f"tone curve: {tuple(TONE_CURVES)}")

    def lights(self) -> tuple[StudioLight, StudioLight, StudioLight]:
        return (self.key, self.fill, self.rim)

    def background_colours(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """(bottom, top) as drawn: a solid background draws its bottom colour everywhere."""
        bottom, top = self.background
        return (tuple(bottom), tuple(top if self.background_gradient else bottom))


def studio_frame(state: LookdevState, camera=None) -> np.ndarray:
    """3x3, columns = the studio's X, Y, Z in world: the world (or the camera's frame with "Licht folgt Kamera" and a
    camera with `basis()`) turned by `rotation` about its Y."""
    if state.follow_camera and getattr(camera, "basis", None) is not None:
        forward, right, up = camera.basis()
        base = np.column_stack([np.asarray(right, float), np.asarray(up, float), -np.asarray(forward, float)])
    else:
        base = np.identity(3)
    a = math.radians(state.rotation)
    turn = np.array([[math.cos(a), 0.0, math.sin(a)], [0.0, 1.0, 0.0], [-math.sin(a), 0.0, math.cos(a)]])
    return base @ turn


def light_directions(state: LookdevState, camera=None) -> np.ndarray:
    """(3, 3): key, fill, rim toward the light, world, unit."""
    frame = studio_frame(state, camera)
    return np.stack([frame @ eo.local_direction(light.azimuth, light.elevation) for light in state.lights()])


def key_frame(key_dir) -> tuple[np.ndarray, np.ndarray]:
    """(up, right) of the key's own area frame (B5): right = world up x key, up = key x right."""
    k = np.asarray(key_dir, dtype=np.float64)
    ref = np.array([0.0, 1.0, 0.0]) if abs(k[1]) < 0.999 else np.array([1.0, 0.0, 0.0])
    right = np.cross(ref, k)
    right /= np.linalg.norm(right)
    return np.cross(k, right), right


def ld_wrap(ndl, w) -> np.ndarray:
    ndl = np.asarray(ndl, dtype=np.float64)[..., None]
    w = np.asarray(w, dtype=np.float64)
    return np.maximum((ndl + w) / (1.0 + w), 0.0)


def ld_diffuse(n, wrap, values: dict) -> np.ndarray:
    """GLSL `ld_diffuse` from a frame dict: SH9 (rotated, scaled) + the three lights with a per-channel wrap."""
    n = np.asarray(n, dtype=np.float64)
    rot = np.asarray(values["u_ld_env_rot"], dtype=np.float64).reshape(3, 3).T  # column-major -> row-major
    out = values["u_ld_env_intensity"] * sh9_eval(values["u_ld_sh"], n @ rot.T)
    for d, c in zip(values["u_ld_light_dir"], values["u_ld_light_color"]):
        out = out + np.asarray(c) * ld_wrap(np.sum(n * np.asarray(d), -1), wrap)
    return out


def ggx_d(n_dot_h, alpha):
    a2 = alpha * alpha
    d = n_dot_h * n_dot_h * (a2 - 1.0) + 1.0
    return a2 / (math.pi * d * d)


def smith_vis(n_dot_l, n_dot_v, alpha):
    a2 = alpha * alpha
    gv = n_dot_l * np.sqrt(n_dot_v * n_dot_v * (1.0 - a2) + a2)
    gl = n_dot_v * np.sqrt(n_dot_l * n_dot_l * (1.0 - a2) + a2)
    return 0.5 / np.maximum(gv + gl, 1e-12)


def direct_specular(n, v, l, roughness, f0) -> np.ndarray:
    """GLSL `direct_specular` (`eye_shaders.EYE_LIB_SRC`): GGX D x Smith V x N.L x Schlick F."""
    n, v, l = (np.asarray(x, dtype=np.float64) for x in (n, v, l))
    h = eo.normalize(v + l)
    nl = np.sum(n * l, -1)
    nv = np.maximum(np.sum(n * v, -1), 1e-4)
    r = np.maximum(roughness, eo.MIN_DIRECT_ROUGHNESS)
    a = r * r
    out = (ggx_d(np.maximum(np.sum(n * h, -1), 0.0), a) * smith_vis(nl, nv, a) * nl
           * eo.schlick_scalar(f0, np.maximum(np.sum(v * h, -1), 0.0)))
    return np.where(nl <= 0.0, 0.0, out)


def ld_lobe(roughness, size):
    return np.sqrt(np.minimum(np.asarray(roughness) ** 2 + size, 1.0))


def ld_specular(n, v, roughness, f0, values: dict) -> np.ndarray:
    """GLSL `ld_specular`: the three lights' GGX highlights, each lobe widened by the light's size."""
    out = 0.0
    for d, c, s in zip(values["u_ld_light_dir"], values["u_ld_light_color"], values["u_ld_light_size"]):
        out = out + np.asarray(c) * direct_specular(n, v, d, ld_lobe(roughness, s), f0)[..., None]
    return out


# -- the frame dict ----------------------------------------------------------------------------------------------------

def _vec(v) -> tuple[float, ...]:
    return tuple(float(c) for c in v)


def studio_uniforms(studio: Studio) -> dict:
    """The parametric studio's uniforms (studio frame), padded to `MAX_STUDIO` rectangles."""
    frames = studio.frames()
    pad = MAX_STUDIO - len(frames)
    return {
        "u_ld_studio_n": len(frames),
        "u_ld_studio_centre": [_vec(f[0]) for f in frames] + [(0.0, 0.0, 1.0)] * pad,
        "u_ld_studio_right": [_vec(f[1]) for f in frames] + [(1.0, 0.0, 0.0)] * pad,
        "u_ld_studio_up": [_vec(f[2]) for f in frames] + [(0.0, 1.0, 0.0)] * pad,
        "u_ld_studio_half": [_vec(f[3]) for f in frames] + [(0.1, 0.1)] * pad,
        "u_ld_studio_radiance": [_vec(f[4]) for f in frames] + [(0.0, 0.0, 0.0)] * pad,
        "u_ld_zenith": _vec(studio.zenith), "u_ld_horizon": _vec(studio.horizon), "u_ld_floor": _vec(studio.floor),
        "u_ld_horizon_width": float(studio.horizon_width), "u_ld_edge_sigma": float(studio.edge_sigma),
    }


def frame_uniforms(state: LookdevState, camera=None) -> dict:
    """Everything both LookDev passes read in one frame (resolved once per frame). The 7 Worklight names
    (`u_key_*`, `u_fill_*`, `u_ambient`) carry the LookDev key and fill with ambient 0 for the eye's LOOKDEV variant
    (D2, C5): its iris key table follows the LookDev key; diffuse wrap 0 (the eye's lit is Lambert + SH9)."""
    frame = studio_frame(state, camera)
    dirs = light_directions(state, camera)
    colours = [light.colour() for light in state.lights()]
    key_up, key_right = key_frame(dirs[0])
    values = {
        "u_ld_light_dir": [_vec(d) for d in dirs],
        "u_ld_light_color": [_vec(c) for c in colours],
        "u_ld_light_size": [float(light.size) for light in state.lights()],
        "u_ld_sh": [_vec(row) for row in project_cached(state.studio)],
        "u_ld_env_rot": _vec(frame.reshape(-1)),  # column-major of frame^T (world -> studio) = row-major of frame
        "u_ld_env_intensity": float(state.env_intensity),
        "u_ld_exposure": float(2.0 ** state.exposure),
        "u_ld_tone": TONE_CURVES[state.tone_curve],
        "u_ld_key_up": _vec(key_up), "u_ld_key_right": _vec(key_right),
        "u_key_dir": _vec(dirs[0]), "u_key_color": _vec(colours[0]), "u_key_wrap": 0.0,
        "u_fill_dir": _vec(dirs[1]), "u_fill_color": _vec(colours[1]), "u_fill_wrap": 0.0,
        "u_ambient": 0.0,
    }
    values.update(studio_uniforms(state.studio))
    return values

