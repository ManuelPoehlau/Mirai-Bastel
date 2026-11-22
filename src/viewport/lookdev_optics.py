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
- P3 (AD-039 §2.1): `LookdevEffects` (the effect switches, view state in `LookdevState.effects`), `effective` /
  `effect_reasons` (dependencies and missing features); S1 (§4): `shadow_frustum`, `shadow_view_projection`,
  `shadow_spacing`, `pcf_visibility` and `ld_key_shadowed`, the twins of `lookdev_shaders.LD_SHADOW_SRC` and the
  `SHADOW` block.

World frame as `light_rig` (Y up, the model faces +Z, azimuth from +Z toward +X). The studio's frame turns by
`rotation` degrees about Y; with "Licht folgt Kamera" it is the camera's (`right`, `up`, `-forward`), as
`light_rig.frame_for(SPACE_CAMERA)`. Lights and rectangles are given in that frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields

import numpy as np

from . import eye_optics as eo
from .light_rig import kelvin_to_rgb
from .lookdev_shaders import MAX_STUDIO, SHADOW_DEPTH_BIAS, TONE_CURVES

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


# -- P3 effect switches (AD-039 §2.1) -----------------------------------------------------------------------------------

@dataclass(frozen=True)
class LookdevEffects:
    """The P3 effects' on/off (view state, `view.lookdev.effects`, no Undo). A field joins with its slice, default on
    once the slice is built (AD-039 §2.1). `shadow` (S1): the key's shadow map on skin and teeth."""

    shadow: bool = True

    @classmethod
    def names(cls) -> tuple[str, ...]:
        return tuple(f.name for f in fields(cls))

    def as_dict(self) -> dict[str, bool]:
        return {name: bool(getattr(self, name)) for name in self.names()}


#: The feature each effect needs (`viewport.lookdev_features`), and the effect it depends on (AD-039 §2.1 / §2.2).
EFFECT_FEATURE = {"shadow": "depth_texture"}
EFFECT_NEEDS: dict[str, str] = {}
#: The panel's reasons for a greyed effect (German, the panel's language).
FEATURE_REASON = {"depth_texture": "Tiefentextur fehlt", "sampler_objects": "Sampler-Objekte fehlen",
                  "cube_rgba16f": "Cube-Ziel fehlt", "texture_units": "zu wenige Textureinheiten"}
EFFECT_LABEL = {"shadow": "Schatten"}


def effect_reasons(effects: LookdevEffects, features=None) -> dict[str, str | None]:
    """Why each effect is not available (None = it is): a missing feature (`features` a `FeatureReport` or None before
    the check ran: nothing known missing yet), or the effect it needs being off ("braucht Schatten")."""
    out: dict[str, str | None] = {}
    for name in LookdevEffects.names():
        feature = EFFECT_FEATURE.get(name)
        reason = None
        if feature is not None and features is not None and not getattr(features, feature, True):
            reason = FEATURE_REASON.get(feature, feature)
        needed = EFFECT_NEEDS.get(name)
        if reason is None and needed is not None and (not getattr(effects, needed) or out.get(needed)):
            reason = f"braucht {EFFECT_LABEL.get(needed, needed)}"
        out[name] = reason
    return out


def effective(effects: LookdevEffects, features=None) -> LookdevEffects:
    """The effects a frame draws: switched on, their feature present, the effect they need effective too."""
    reasons = effect_reasons(effects, features)
    return LookdevEffects(**{name: bool(getattr(effects, name)) and reasons[name] is None
                             for name in LookdevEffects.names()})


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
    exposure (EV), tone curve, the three lights, "Licht folgt Kamera", the studio content, the background (display
    values as picked: solid = bottom == top) and the P3 effect switches (AD-039 §2.1)."""

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
    #: AD-039 §2.1: the P3 effect switches (part of the state, so the frame cache key covers them).
    effects: LookdevEffects = field(default_factory=LookdevEffects)

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


# -- S1: the key shadow map (AD-039 §4) --------------------------------------------------------------------------------

#: `PROVISIONAL` fixed setting (AD-039 §4, Q-P3-3; P3-0 run 2 on the reference PC): 1024² DEPTH_COMPONENT24, 3 x 3
#: bilinear-compare fetches. LD-3's knobs later.
SHADOW_SIZE = 1024
SHADOW_GRID = 3
#: The caster bounds grow by this (AD-039 §4 "Frustum"), so a pose inside the margin does not move the map.
SHADOW_MARGIN = 0.15
#: The fetch spacing in texels: 1 + this x the key's size ("Weichheit", 0 .. 1) - PCF with a light-size radius.
SHADOW_SOFTNESS_TEXELS = 8.0
#: The normal offset of the lookup point, in texels of the map (world units = this x the texel's width).
SHADOW_NORMAL_OFFSET_TEXELS = 1.5
#: The depth pass's slope-scaled polygon offset (factor, units), as LD-0.
SHADOW_POLYGON_OFFSET = (2.0, 4.0)


def _box_corners(lo, hi) -> np.ndarray:
    lo, hi = np.asarray(lo, dtype=np.float64), np.asarray(hi, dtype=np.float64)
    return np.array([[(lo, hi)[i][0], (lo, hi)[j][1], (lo, hi)[k][2]] for i in (0, 1) for j in (0, 1) for k in (0, 1)])


def shadow_frustum(boxes, margin: float = SHADOW_MARGIN) -> tuple[tuple[float, float, float], float]:
    """(centre, radius) of the sphere the key's orthographic map covers: the union of the casters' world bounds, grown
    by `margin`. `boxes` = [(object min, object max, model 4x4 column-major or None)]; each box's 8 corners go through
    its model matrix. Recomputed only when the caster set or a layout changes (not per pose step), so a drag does not
    move the map."""
    corners = []
    for lo, hi, model in boxes:
        c = _box_corners(lo, hi)
        if model is not None and len(model) == 16:
            m = np.asarray(model, dtype=np.float64).reshape(4, 4).T  # column-major -> row-major
            c = c @ m[:3, :3].T + m[:3, 3]
        corners.append(c)
    if not corners:
        return (0.0, 0.0, 0.0), 1.0
    points = np.concatenate(corners)
    lo, hi = points.min(axis=0), points.max(axis=0)
    centre = (lo + hi) / 2.0
    radius = float(np.linalg.norm(hi - lo)) / 2.0 * (1.0 + margin)
    return tuple(float(v) for v in centre), max(radius, 1e-6)


def shadow_view_projection(key_dir, centre, radius: float) -> list[float]:
    """Column-major 4x4: the key's orthographic view-projection over the sphere (`centre`, `radius`): looking along
    -`key_dir` from `centre + radius * key_dir`, the box ±radius wide and 2 radius deep (depth 0 at the sphere's
    light side). The light frame is `key_frame` (the key's own area frame)."""
    k = np.asarray(key_dir, dtype=np.float64)
    k = k / np.linalg.norm(k)
    up, right = key_frame(k)
    eye = np.asarray(centre, dtype=np.float64) + k * radius
    view = np.identity(4)
    view[0, :3], view[1, :3], view[2, :3] = right, up, k  # the camera looks along -k
    view[:3, 3] = -view[:3, :3] @ eye
    near, far = 0.0, 2.0 * radius
    proj = np.identity(4)
    proj[0, 0] = proj[1, 1] = 1.0 / radius
    proj[2, 2] = -2.0 / (far - near)
    proj[2, 3] = -(far + near) / (far - near)
    return [float(v) for v in (proj @ view).T.reshape(-1)]


def shadow_spacing(size: float, map_size: int = SHADOW_SIZE) -> float:
    """The PCF fetch spacing in map UV units for the key's size ("Weichheit")."""
    return (1.0 + SHADOW_SOFTNESS_TEXELS * max(0.0, float(size))) / float(map_size)


def shadow_uniforms(view_projection, radius: float, key_size: float, map_size: int = SHADOW_SIZE) -> dict:
    """The `LD_SHADOW_SRC` uniforms (the sampler's unit is set by the pass)."""
    texel_world = 2.0 * radius / float(map_size)
    return {"u_ld_shadow_vp": tuple(float(v) for v in view_projection),
            "u_ld_shadow_radius": shadow_spacing(key_size, map_size),
            "u_ld_shadow_offset": SHADOW_NORMAL_OFFSET_TEXELS * texel_world}


def shadow_coords(p, n, view_projection, offset: float) -> np.ndarray:
    """GLSL `ld_key_visibility`'s map point (..., 3): (u, v, depth) in [0, 1] of the normal-offset world point."""
    p = np.asarray(p, dtype=np.float64) + np.asarray(n, dtype=np.float64) * offset
    m = np.asarray(view_projection, dtype=np.float64).reshape(4, 4).T
    clip = p @ m[:3, :3].T + m[:3, 3]
    return clip * 0.5 + 0.5  # orthographic: w = 1


def compare_bilinear(depth: np.ndarray, uv, ref) -> np.ndarray:
    """A `sampler2DShadow` fetch with GL_LINEAR, CLAMP_TO_BORDER (border depth 1.0) and LEQUAL: the four nearest
    texels compared (ref <= stored) and blended bilinearly. `depth` (h, w) row 0 = v 0."""
    uv = np.asarray(uv, dtype=np.float64)
    h, w = depth.shape
    x = uv[..., 0] * w - 0.5
    y = uv[..., 1] * h - 0.5
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    ref = np.asarray(ref, dtype=np.float64)

    def lit(ix, iy):
        inside = (ix >= 0) & (ix < w) & (iy >= 0) & (iy < h)
        stored = np.where(inside, depth[np.clip(iy, 0, h - 1), np.clip(ix, 0, w - 1)], 1.0)
        return (ref <= stored).astype(np.float64)

    return ((lit(x0, y0) * (1 - fx) + lit(x0 + 1, y0) * fx) * (1 - fy)
            + (lit(x0, y0 + 1) * (1 - fx) + lit(x0 + 1, y0 + 1) * fx) * fy)


def pcf_visibility(depth: np.ndarray, sp, spacing: float) -> np.ndarray:
    """GLSL `ld_key_visibility` from the map point `sp` (..., 3): 3 x 3 bilinear-compare fetches `spacing` (UV) apart,
    averaged; a point outside the map's box is lit."""
    sp = np.asarray(sp, dtype=np.float64)
    ref = sp[..., 2] - SHADOW_DEPTH_BIAS
    total = 0.0
    for y in (-1, 0, 1):
        for x in (-1, 0, 1):
            total = total + compare_bilinear(depth, sp[..., :2] + np.array([x, y]) * spacing, ref)
    inside = np.all((sp >= 0.0) & (sp <= 1.0), axis=-1)
    return np.where(inside, total / 9.0, 1.0)


def ld_key_shadowed(albedo, n, v, wrap, roughness, f0, values: dict, visibility) -> np.ndarray:
    """The skin's light with the `SHADOW` block (AD-039 §4): albedo x `ld_diffuse` + `ld_specular`, minus
    (1 - visibility) x the key's own diffuse and specular term - the key scaled by its visibility."""
    albedo = np.asarray(albedo, dtype=np.float64)
    colour = albedo * ld_diffuse(n, wrap, values) + ld_specular(n, v, roughness, f0, values)
    d, c, s = values["u_ld_light_dir"][0], values["u_ld_light_color"][0], values["u_ld_light_size"][0]
    key = np.asarray(c) * (albedo * ld_wrap(np.sum(np.asarray(n) * np.asarray(d), -1), wrap)
                           + direct_specular(n, v, d, ld_lobe(roughness, s), f0)[..., None])
    return colour - (1.0 - np.asarray(visibility, dtype=np.float64))[..., None] * key


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

