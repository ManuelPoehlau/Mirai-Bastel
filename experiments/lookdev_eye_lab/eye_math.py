"""GL-free reference of every shading term the Eye Proof's shaders evaluate (P1, 2026-11-14).

Each function here has a GLSL twin in `shaders.py` with the same name and the same arithmetic; the parity tests
(`tests/test_gl_parity.py`) evaluate both on the same inputs and compare within float32 tolerance, the pattern of
`viewport.light_rig.shade` / `material.specular_term` for the Worklight. Change one, change the other.

NumPy only (float64), vectorised over leading axes. Units are scene-linear radiance; directions are unit vectors.

Conventions:
- **Roughness** `r` is perceptual roughness in [0, 1]; the GGX width is `alpha = r^2` (Burley / Karis). Direct light
  clamps `r` to `MIN_DIRECT_ROUGHNESS` first: a point light on a perfect mirror has an infinite, sub-pixel peak.
- **Direct specular** (T-B, T-C, T-D): GGX normal distribution, height-correlated Smith visibility, Schlick Fresnel:
  `f_spec · N·L · E` with `f_spec = D · Vis · F` (Vis already holds the 1 / (4 N·L N·V)).
- **Environment specular** (T-C, T-D): split sum. The prefiltered radiance (cube mip by roughness, or the analytic
  softbox for T-D) times `env_brdf_approx(F0, r, N·V)`, Karis' analytic fit of the pre-integrated BRDF ("Physically
  Based Shading on Mobile", 2014) - no 2D lookup texture needed.
- **Roughness -> LOD** (`roughness_to_lod`): "linear" `lod = r · N`, "sqrt" `lod = sqrt(r) · N`, N = the last mip
  index (the 2^2 level, RESULTS_REFERENCE_PC §8). The prefilter (`studio_env.prefilter`) stores at level L the
  roughness `lod_to_roughness(L)` of the same mapping, so each mapping has its own mip chain.
- **Colour path** (lab-local, D-L3 undecided): sRGB decode of the iris image, linear shading, exposure `2^EV`, then
  clamp or Reinhard per channel, then sRGB encode - all in the fragment shader; no `GL_FRAMEBUFFER_SRGB`.
- **T-D softbox**: a rectangle in angular coordinates around its centre direction whose edges are a Gaussian of
  width sigma (`box_profile`, an erf difference). The environment generator uses the same function with the edge
  width `StudioEnv.edge_sigma`; T-D widens it by the GGX lobe, `sigma = sqrt(edge^2 + lobe^2)` with
  `lobe = TD_SIGMA_SCALE · alpha^TD_SIGMA_POWER`. A Gaussian is only an approximation of the GGX lobe (no long tail);
  the constants were fitted (2026-11-14) to `studio_env.prefilter_level` at r = 0.1 ... 0.8, and
  `tests/test_eye_math.py::test_td_softbox_follows_the_prefiltered_cube` bounds the remaining error.
- **erf**: Abramowitz & Stegun 7.1.26 (max abs error 1.5e-7), used by both sides (GLSL 330 has no erf).
"""

from __future__ import annotations

import math

import numpy as np

MIN_DIRECT_ROUGHNESS = 0.03
#: T-D: Gaussian width (radians) of the reflected GGX lobe, `TD_SIGMA_SCALE · alpha^TD_SIGMA_POWER`; least max-error
#: fit against the cube prefilter of the studio environment (relative RMS over the lit texels: 9 % at r = 0.1,
#: 16 % at r = 0.8; a single power of alpha left 34 %).
TD_SIGMA_SCALE = 0.8
TD_SIGMA_POWER = 0.675
LOD_MAPPINGS = ("linear", "sqrt")
TONEMAPS = ("clamp", "reinhard")

_ERF_P = 0.3275911
_ERF_A = (0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429)


# -- colour path ---------------------------------------------------------------------------------------------------


def srgb_decode(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb_encode(c):
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1.0 / 2.4) - 0.055)


def tonemap(x, mode: int):
    """0 = clamp, 1 = Reinhard x / (1 + x), per channel."""
    x = np.maximum(np.asarray(x, dtype=np.float64), 0.0)
    return np.minimum(x, 1.0) if mode == 0 else x / (1.0 + x)


def display(linear, exposure: float, mode: int):
    """Scene-linear -> the 8-bit framebuffer's sRGB value: exposure (a linear factor, 2^EV), tonemap, encode."""
    return srgb_encode(tonemap(np.asarray(linear, dtype=np.float64) * exposure, mode))


# -- BRDF ----------------------------------------------------------------------------------------------------------


def f0_from_ior(n: float) -> float:
    """Normal-incidence reflectance against air: cornea 1.376 -> 0.0250."""
    return ((n - 1.0) / (n + 1.0)) ** 2


def ggx_d(n_dot_h, alpha):
    a2 = np.asarray(alpha, dtype=np.float64) ** 2
    d = np.asarray(n_dot_h, dtype=np.float64) ** 2 * (a2 - 1.0) + 1.0
    return a2 / (math.pi * d * d)


def smith_vis(n_dot_l, n_dot_v, alpha):
    """Height-correlated Smith GGX visibility G2 / (4 N·L N·V) (Heitz 2014)."""
    a2 = np.asarray(alpha, dtype=np.float64) ** 2
    nl, nv = np.asarray(n_dot_l, dtype=np.float64), np.asarray(n_dot_v, dtype=np.float64)
    gv = nl * np.sqrt(nv * nv * (1.0 - a2) + a2)
    gl = nv * np.sqrt(nl * nl * (1.0 - a2) + a2)
    return 0.5 / np.maximum(gv + gl, 1e-12)


def schlick(f0, v_dot_h):
    f0 = np.asarray(f0, dtype=np.float64)
    return f0 + (1.0 - f0) * (1.0 - np.clip(np.asarray(v_dot_h, dtype=np.float64), 0.0, 1.0)) ** 5


def _dot(a, b):
    return np.sum(np.asarray(a, dtype=np.float64) * np.asarray(b, dtype=np.float64), axis=-1)


def _normalize(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-20)


def direct_specular(n, v, l, roughness, f0):
    """GGX key-light specular per unit irradiance, including N·L: (..., 3) for an RGB `f0`. Zero where N·L <= 0."""
    n, v, l = _normalize(n), _normalize(v), _normalize(l)
    h = _normalize(v + l)
    nl = _dot(n, l)
    nv = np.maximum(_dot(n, v), 1e-4)
    nh = np.maximum(_dot(n, h), 0.0)
    vh = np.maximum(_dot(v, h), 0.0)
    a = np.maximum(np.asarray(roughness, dtype=np.float64), MIN_DIRECT_ROUGHNESS) ** 2
    value = ggx_d(nh, a) * smith_vis(np.maximum(nl, 0.0), nv, a) * np.maximum(nl, 0.0)
    f = schlick(np.asarray(f0, dtype=np.float64), vh[..., None])
    return np.where((nl > 0.0)[..., None], value[..., None] * f, 0.0)


def env_brdf_approx(f0, roughness, n_dot_v):
    """Karis' analytic split-sum term: the environment's weight F0 · A + B (RGB for an RGB `f0`)."""
    r = np.asarray(roughness, dtype=np.float64)[..., None]
    nv = np.asarray(n_dot_v, dtype=np.float64)[..., None]
    c0 = np.array([-1.0, -0.0275, -0.572, 0.022])
    c1 = np.array([1.0, 0.0425, 1.04, -0.04])
    q = r * c0 + c1
    a004 = np.minimum(q[..., 0] * q[..., 0], np.exp2(-9.28 * nv[..., 0])) * q[..., 0] + q[..., 1]
    a = -1.04 * a004 + q[..., 2]
    b = 1.04 * a004 + q[..., 3]
    return np.asarray(f0, dtype=np.float64) * a[..., None] + b[..., None]


def roughness_to_lod(roughness, mode: int, last_level: float):
    """0 = linear `r · N`, 1 = sqrt `sqrt(r) · N` (audit §5.4)."""
    r = np.clip(np.asarray(roughness, dtype=np.float64), 0.0, 1.0)
    return (r if mode == 0 else np.sqrt(r)) * last_level


def lod_to_roughness(lod, mode: int, last_level: float):
    x = np.clip(np.asarray(lod, dtype=np.float64) / last_level, 0.0, 1.0)
    return x if mode == 0 else x * x


# -- the analytic softbox (environment generator and T-D) ------------------------------------------------------------


def erf(x):
    x = np.asarray(x, dtype=np.float64)
    s = np.sign(x)
    a = np.abs(x)
    t = 1.0 / (1.0 + _ERF_P * a)
    a1, a2, a3, a4, a5 = _ERF_A
    poly = ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t
    return s * (1.0 - poly * np.exp(-a * a))


def box_profile(x, half_width, sigma):
    """A box of half-width `half_width` convolved with a unit-area Gaussian of width `sigma` (all in radians)."""
    k = 1.0 / (math.sqrt(2.0) * np.asarray(sigma, dtype=np.float64))
    x = np.asarray(x, dtype=np.float64)
    return 0.5 * (erf((x + half_width) * k) - erf((x - half_width) * k))


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, dtype=np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def rect_term(d, centre, right, up, half_w, half_h, sigma):
    """The unit-radiance weight of one rectangular light at directions `d` (..., 3): angular coordinates
    x = atan2(d·right, d·centre), y = atan2(d·up, d·centre), a Gaussian-edged box in each, faded out over the
    hemisphere behind the light so a wide sigma has no step at d·centre = 0."""
    dc, du, dv = _dot(d, centre), _dot(d, right), _dot(d, up)
    x, y = np.arctan2(du, dc + 1e-12), np.arctan2(dv, dc + 1e-12)  # + 1e-12: GLSL atan(0, 0) is undefined
    return box_profile(x, half_w, sigma) * box_profile(y, half_h, sigma) * smoothstep(0.0, 0.25, dc)


def backdrop(d, zenith, horizon, floor, horizon_width):
    """Neutral studio backdrop: floor below the horizon, a gradient from horizon to zenith above; `horizon_width`
    (in d.y) softens the floor line."""
    y = np.asarray(d, dtype=np.float64)[..., 1:2]
    sky = np.asarray(horizon) + (np.asarray(zenith) - np.asarray(horizon)) * np.clip(y, 0.0, 1.0)
    t = smoothstep(-horizon_width, horizon_width, y)
    return np.asarray(floor) + (sky - np.asarray(floor)) * t


def td_lobe(roughness):
    """T-D: the Gaussian width (radians) standing in for the reflected GGX lobe of `roughness`."""
    alpha = np.asarray(roughness, dtype=np.float64) ** 2
    return TD_SIGMA_SCALE * alpha ** TD_SIGMA_POWER


def td_sigma(edge_sigma: float, roughness):
    """T-D: the softbox edge width after the lobe (radians)."""
    return np.sqrt(edge_sigma ** 2 + td_lobe(roughness) ** 2)


# -- C1: the cornea as an analytic sphere ----------------------------------------------------------------------------


def cornea_hit(origin, direction, centre, radius, limbus_z, max_t):
    """Nearest intersection of the rays with the cornea sphere's cap (z >= `limbus_z` in eye space) before `max_t`.
    Returns (hit mask, hit point (..., 3), unit outward normal (..., 3))."""
    o, d = np.asarray(origin, dtype=np.float64), _normalize(direction)
    oc = o - np.asarray(centre, dtype=np.float64)
    b = _dot(oc, d)
    c = _dot(oc, oc) - radius * radius
    disc = b * b - c
    t = -b - np.sqrt(np.maximum(disc, 0.0))
    p = o + d * t[..., None]
    hit = (disc >= 0.0) & (t > 0.0) & (t < max_t) & (p[..., 2] >= limbus_z)
    return hit, p, (p - np.asarray(centre)) / radius


# -- framing ---------------------------------------------------------------------------------------------------------


def sphere_coverage(distance: float, radius: float, fov_degrees: float, width: int, height: int,
                    grid: int = 256) -> float:
    """The share of a perspective frame covered by a sphere of `radius` centred on the view axis at `distance`
    (pixel-centre rays on a grid of about `grid` columns; exact up to the grid)."""
    tan_half = math.tan(math.radians(fov_degrees) / 2.0)
    aspect = width / height
    cols = grid
    rows = max(1, round(grid / aspect))
    x = ((np.arange(cols) + 0.5) / cols * 2.0 - 1.0) * tan_half * aspect
    y = ((np.arange(rows) + 0.5) / rows * 2.0 - 1.0) * tan_half
    xx, yy = np.meshgrid(x, y)
    cos_angle = 1.0 / np.sqrt(1.0 + xx * xx + yy * yy)
    sin_limit = min(radius / distance, 1.0)
    return float(np.mean(cos_angle >= math.sqrt(1.0 - sin_limit * sin_limit)))


def distance_for_coverage(target: float, radius: float, fov_degrees: float, width: int, height: int) -> float:
    """Camera distance at which the sphere covers `target` of the frame (bisection on `sphere_coverage`)."""
    lo, hi = radius * 1.0001, radius * 200.0
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if sphere_coverage(mid, radius, fov_degrees, width, height) > target:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)
