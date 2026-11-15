"""The eye's optics (AD-033 §5): derived geometry and the NumPy references of every function the eye pass's GLSL
computes. GL-free. Promoted from `experiments/lookdev_eye_lab/` (`cornea_optics.py`, `iris_fit.py`,
`limbus_model.py`, Manu's go 2026-11-15, Q-E1); the lab stays frozen as the oracle and its tests compare it with this
module. Nothing here imports `experiments/` (AGENTS.md §8a).

Eye-local units: 1 = the sclera radius (the reference eye: 12 mm); the eye looks down +Z, centred at the origin.

**Geometry** (`EyeGeometry.from_values`): the anterior cornea is a sphere of `cornea_radius` whose rim is the limbus
circle (radius `limbus_radius`, on the unit sphere); the posterior cornea a sphere of 6.6 mm with 0.55 mm central
thickness; the iris a shallow cone `z = a + b r` from the pupil edge (`iris_concavity` behind the root) to its root
`iris_root_z`, its radius just inside the sclera wall; the chamber angle where the posterior sphere meets that cone.
These are the lab's values (P1b), unchanged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

MM = 1.0 / 12.0
N_AIR = 1.0
N_CORNEA = 1.376
N_AQUEOUS = 1.336
N_EFFECTIVE = 1.3375
POSTERIOR_RADIUS = 6.6 * MM
CENTRAL_THICKNESS = 0.55 * MM
#: The iris root sits this far inside the sclera wall (the lab's gap: a root on the wall poked through as a dark ring).
IRIS_ROOT_GAP = 0.002
MISS, IRIS, PUPIL, LIMBUS = 0, 1, 2, 3
EPS = 1e-6


@dataclass(frozen=True)
class EyeGeometry:
    cornea_radius: float
    limbus_radius: float
    iris_root_z: float
    iris_concavity: float
    pupil_radius: float

    @classmethod
    def from_values(cls, spec) -> "EyeGeometry":
        """From anything with the five anatomy fields (`core.EyeSpec`)."""
        return cls(spec.cornea_radius, spec.limbus_radius, spec.iris_root_z, spec.iris_concavity, spec.pupil_radius)

    @property
    def limbus_z(self) -> float:
        return math.sqrt(1.0 - self.limbus_radius ** 2)

    @property
    def anterior_centre_z(self) -> float:
        return self.limbus_z - math.sqrt(self.cornea_radius ** 2 - self.limbus_radius ** 2)

    @property
    def apex_z(self) -> float:
        return self.anterior_centre_z + self.cornea_radius

    @property
    def posterior_centre_z(self) -> float:
        return self.apex_z - CENTRAL_THICKNESS - POSTERIOR_RADIUS

    @property
    def iris_radius(self) -> float:
        return math.sqrt(1.0 - self.iris_root_z ** 2) - IRIS_ROOT_GAP

    @property
    def iris_b(self) -> float:
        return self.iris_concavity / (self.iris_radius - self.pupil_radius)

    @property
    def iris_a(self) -> float:
        return self.iris_root_z - self.iris_b * self.iris_radius

    def iris_z(self, r):
        return self.iris_a + self.iris_b * np.asarray(r, dtype=np.float64)

    def posterior_z(self, r):
        r = np.asarray(r, dtype=np.float64)
        return self.posterior_centre_z + np.sqrt(np.maximum(POSTERIOR_RADIUS ** 2 - r * r, 0.0))

    def anterior_z(self, r):
        r = np.asarray(r, dtype=np.float64)
        return self.anterior_centre_z + np.sqrt(np.maximum(self.cornea_radius ** 2 - r * r, 0.0))

    @property
    def angle(self) -> tuple[float, float]:
        """(r, z) where the posterior sphere meets the iris cone: the chamber angle (bisection, as the lab)."""
        lo, hi = 0.0, POSTERIOR_RADIUS
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if float(self.posterior_z(mid)) > float(self.iris_z(mid)):
                lo = mid
            else:
                hi = mid
        return lo, float(self.iris_z(lo))


# -- ray primitives (lab `cornea_optics`, GLSL twins in `eye_shaders.EYE_LIB_SRC`) -------------------------------------


def normalize(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-300)


def _dot(a, b):
    return np.sum(np.asarray(a, dtype=np.float64) * np.asarray(b, dtype=np.float64), axis=-1)


def refract(i, n, eta):
    """GLSL `refract`; total internal reflection gives the zero vector."""
    i, n = np.asarray(i, dtype=np.float64), np.asarray(n, dtype=np.float64)
    eta = np.asarray(eta, dtype=np.float64)
    d = _dot(n, i)
    k = 1.0 - eta * eta * (1.0 - d * d)
    out = np.expand_dims(eta, -1) * i - np.expand_dims(eta * d + np.sqrt(np.maximum(k, 0.0)), -1) * n
    return np.where((k < 0.0)[..., None], 0.0, out)


def sphere_entry(o, d, centre, radius):
    """Nearest t > EPS where o + t d (d unit) meets the sphere: (hit, t)."""
    oc = np.asarray(o, dtype=np.float64) - np.asarray(centre, dtype=np.float64)
    b = _dot(oc, d)
    c = _dot(oc, oc) - radius * radius
    disc = b * b - c
    s = np.sqrt(np.maximum(disc, 0.0))
    t0, t1 = -b - s, -b + s
    t = np.where(t0 > EPS, t0, t1)
    return (disc >= 0.0) & (t > EPS), t


def iris_cone_hit(o, d, g: EyeGeometry):
    """First t > EPS where the ray meets the iris cone z = a + b r (extended to r = 0): (hit, t, r at the hit)."""
    o, d = np.asarray(o, dtype=np.float64), np.asarray(d, dtype=np.float64)
    a, b = g.iris_a, g.iris_b
    q0 = o[..., 2] - a
    A = d[..., 2] ** 2 - b * b * (d[..., 0] ** 2 + d[..., 1] ** 2)
    B = 2.0 * (q0 * d[..., 2] - b * b * (o[..., 0] * d[..., 0] + o[..., 1] * d[..., 1]))
    C = q0 * q0 - b * b * (o[..., 0] ** 2 + o[..., 1] ** 2)
    disc = B * B - 4.0 * A * C
    s = np.sqrt(np.maximum(disc, 0.0))
    quadratic = np.abs(A) > 1e-12
    safe = np.where(quadratic, A, 1.0)
    r1, r2 = (-B - s) / (2.0 * safe), (-B + s) / (2.0 * safe)
    lin = np.where(np.abs(B) > 1e-12, -C / np.where(np.abs(B) > 1e-12, B, 1.0), -1.0)
    lo = np.where(quadratic, np.minimum(r1, r2), lin)
    hi = np.where(quadratic, np.maximum(r1, r2), lin)

    def valid(t):
        return (t > EPS) & (q0 + t * d[..., 2] >= -1e-9) & ((disc >= 0.0) | ~quadratic)

    t = np.where(valid(lo), lo, np.where(valid(hi), hi, -1.0))
    p = o + np.maximum(t, 0.0)[..., None] * d
    return t > EPS, t, np.hypot(p[..., 0], p[..., 1])


def schlick_scalar(f0: float, cos_theta):
    m = 1.0 - np.clip(np.asarray(cos_theta, dtype=np.float64), 0.0, 1.0)
    return f0 + (1.0 - f0) * m ** 5


def f0_between(n1: float, n2: float) -> float:
    return ((n2 - n1) / (n2 + n1)) ** 2


def limbus_weight(r_entry, g: EyeGeometry):
    """P1b's limbal tissue blend: 0 at the chamber angle's radius .. 1 at the rim (smoothstep)."""
    angle_r = g.angle[0]
    t = np.clip((np.asarray(r_entry, dtype=np.float64) - angle_r) / (g.limbus_radius - angle_r), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


@dataclass
class Trace:
    kind: np.ndarray
    entry: np.ndarray
    normal: np.ndarray
    hit: np.ndarray
    transmit_inner: np.ndarray


def trace(eye, d, variant: str, g: EyeGeometry) -> Trace:
    """The view ray from `eye` along `d` (eye-local) through the cornea to the iris: V2 (one surface, n 1.3375) or
    V3 (1.376 then 1.336 at the posterior sphere). The lab's `cornea_optics.trace` with the geometry as a parameter."""
    eye = np.broadcast_to(np.asarray(eye, dtype=np.float64), np.shape(d))
    d = normalize(d)
    ca = np.array([0.0, 0.0, g.anterior_centre_z])
    cp = np.array([0.0, 0.0, g.posterior_centre_z])
    hit_a, ta = sphere_entry(eye, d, ca, g.cornea_radius)
    entry = eye + ta[..., None] * d
    on_cap = hit_a & (entry[..., 2] >= g.limbus_z - 1e-9)
    normal = normalize(entry - ca)
    transmit = np.ones(np.shape(d)[:-1])
    eta = N_AIR / (N_EFFECTIVE if variant == "V2" else N_CORNEA)
    t_dir = normalize(refract(d, normal, eta))
    hit_p, tp = sphere_entry(entry, t_dir, cp, POSTERIOR_RADIUS)
    pp = entry + tp[..., None] * t_dir
    angle_z = g.angle[1]
    tissue = ~hit_p | (pp[..., 2] < angle_z)
    start = entry
    if variant == "V3":
        np_ = normalize(pp - cp)
        inner = refract(t_dir, np_, N_CORNEA / N_AQUEOUS)
        tir = np.linalg.norm(inner, axis=-1) < 0.5
        tissue = tissue | tir
        cos_b = np.clip(-_dot(np_, t_dir), 0.0, 1.0)
        transmit = np.where(tissue, 1.0, 1.0 - schlick_scalar(f0_between(N_CORNEA, N_AQUEOUS), cos_b))
        t_dir = np.where(tissue[..., None], t_dir, normalize(np.where(tir[..., None], t_dir, inner)))
        start = np.where(tissue[..., None], entry, pp)
    hit_i, ti, ri = iris_cone_hit(start, t_dir, g)
    hit = start + np.maximum(ti, 0.0)[..., None] * t_dir
    kind = np.where(~on_cap, MISS, np.where(tissue, LIMBUS,
                    np.where(~hit_i | (ri > g.iris_radius), LIMBUS, np.where(ri < g.pupil_radius, PUPIL, IRIS))))
    seen = (kind == IRIS) | (kind == PUPIL)
    return Trace(kind.astype(np.int64), entry, normal, np.where(seen[..., None], hit, entry),
                 np.where(seen, transmit, 1.0))


# -- the iris image's radial fit (lab `iris_fit`; AD-033: the target is the visible limbus, Manu's "A") -----------------


def fit_knots(spec, g: EyeGeometry) -> tuple[tuple[float, float], tuple[float, float, float]] | None:
    """((lab pupil share, lab target share), (image pupil, image iris edge, image share at the iris root)) or None for
    the planar mapping. Shares of the iris disc (`iris_radius`) resp. of half the image width."""
    if spec.fit_pupil is None:
        return None
    outer = spec.fit_limbus if spec.hold_outer_color else 1.0
    return (g.pupil_radius / g.iris_radius, g.limbus_radius / g.iris_radius), (spec.fit_pupil, spec.fit_limbus, outer)


def share_map(s, lab: tuple[float, float], img: tuple[float, float, float]):
    s = np.asarray(s, dtype=np.float64)
    lp, lt = lab
    pupil, limbus, outer = img
    inner = s * (pupil / lp)
    middle = pupil + (s - lp) * ((limbus - pupil) / (lt - lp))
    out = limbus + (s - lt) * ((outer - limbus) / (1.0 - lt))
    return np.where(s < lp, inner, np.where(s < lt, middle, out))


def iris_uv(xy, g: EyeGeometry, knots=None):
    """Eye-local iris position(s) (..., 2) -> texture coordinates: planar (`knots` None) or the radial fit."""
    xy = np.asarray(xy, dtype=np.float64)
    if knots is None:
        return 0.5 + xy / (2.0 * g.iris_radius)
    lab, img = knots
    s = np.linalg.norm(xy, axis=-1) / g.iris_radius
    safe = np.where(s > 1e-6, s, 1.0)
    scale = np.where(s > 1e-6, share_map(s, lab, img) / safe, img[0] / lab[0])
    return 0.5 + 0.5 * xy / g.iris_radius * scale[..., None]


# -- the soft limbus (lab `limbus_model`; AD-033: P1c's levels and settings) --------------------------------------------

ASYM_MM = 0.55
COVER_FADE = 0.25


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def limbus_u0(g: EyeGeometry) -> float:
    """The chamber angle's radius minus the limbus ring's: where P1b's limbal tissue begins (u < 0 on the cornea)."""
    return g.angle[0] - g.limbus_radius


def sclera_u(p, g: EyeGeometry):
    p = np.asarray(p, dtype=np.float64)
    return np.arctan2(np.hypot(p[..., 0], p[..., 1]), p[..., 2]) - math.asin(g.limbus_radius)


def cornea_u(p, g: EyeGeometry):
    p = np.asarray(p, dtype=np.float64)
    return np.hypot(p[..., 0], p[..., 1]) - g.limbus_radius


def asym_shift(p, amount: float, base: float = 0.0):
    p = np.asarray(p, dtype=np.float64)
    rr = p[..., 0] ** 2 + p[..., 1] ** 2
    return base + amount * p[..., 1] ** 2 / np.maximum(rr, 1e-12)


def colour_weight(u, band: float, u0: float):
    return _smooth((np.asarray(u, dtype=np.float64) - u0) / (band - u0))


def tint(weight, limbal, sclera, strength: float):
    w = np.asarray(weight, dtype=np.float64)[..., None]
    gradient = np.asarray(limbal) * (1.0 - w) + np.asarray(sclera) * w
    return np.asarray(sclera) * (1.0 - strength) + gradient * strength


def iris_cover(u, shift, amount: float, u0: float):
    u, shift = np.asarray(u, dtype=np.float64), np.asarray(shift, dtype=np.float64)
    if amount <= 0.0:
        return np.zeros(np.broadcast(u, shift).shape)
    ramp = _smooth((u - (u0 - shift)) / np.maximum(shift, 1e-9))
    return ramp * _smooth(shift / (COVER_FADE * amount))


def normal_blend(n_cornea, n_sclera, u, w: float):
    b = _smooth((np.asarray(u, dtype=np.float64) + w) / (2.0 * w))[..., None]
    return normalize(np.asarray(n_cornea) * (1.0 - b) + np.asarray(n_sclera) * b)


def transmission(u, band: float, falloff: float, u0: float):
    t = np.clip((np.asarray(u, dtype=np.float64) - u0) / (band - u0), 0.0, 1.0)
    return (1.0 - t) ** falloff


def sclera_through(p, d, n_sclera, g: EyeGeometry):
    t_dir = normalize(refract(d, n_sclera, N_AIR / N_CORNEA))
    hit, t, r = iris_cone_hit(p, t_dir, g)
    point = np.asarray(p) + np.maximum(t, 0.0)[..., None] * t_dir
    return hit & (r <= g.iris_radius), point


def iris_cone_normal(hit, g: EyeGeometry):
    hit = np.asarray(hit, dtype=np.float64)
    r = np.maximum(np.hypot(hit[..., 0], hit[..., 1]), 1e-6)
    return normalize(np.stack([-g.iris_b * hit[..., 0] / r, -g.iris_b * hit[..., 1] / r, np.ones_like(r)], -1))


# -- the limbal colour from the iris image (lab `limbus_model.image_limbal_colour`) -------------------------------------

RING_WIDTH = 0.05  # image share


def _srgb_decode(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _srgb_encode(c):
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, 1.0)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1.0 / 2.4) - 0.055)


def image_ring_colour(rgb: np.ndarray, edge: float) -> tuple[float, float, float] | None:
    """The iris image's own outer ring (shares `edge - 0.05 .. edge` of half the image width): the mean in linear light,
    returned sRGB-encoded (the eye pass's albedos are display-referred, like the Worklight's). `rgb` (h, w, 3) in
    [0, 1], row order irrelevant. None for an empty ring."""
    h, w = rgb.shape[:2]
    y, x = np.meshgrid((np.arange(h) + 0.5) / h * 2.0 - 1.0, (np.arange(w) + 0.5) / w * 2.0 - 1.0, indexing="ij")
    rho = np.hypot(x, y)
    ring = (rho >= edge - RING_WIDTH) & (rho < edge)
    if not ring.any():
        return None
    return tuple(float(v) for v in _srgb_encode(_srgb_decode(rgb[ring][:, :3]).mean(axis=0)))


# -- the procedural iris (the lab's `eye_geometry.iris_image`): the image of an eye without its own --------------------


def procedural_iris(g: EyeGeometry, size: int = 512, seed: int = 7) -> np.ndarray:
    """(size, size, 3) sRGB values in [0, 1], planar UV space (row 0 = v 1): radial fibres, a collarette, crypts, a dark
    limbal ring, black inside the pupil."""
    rng = np.random.default_rng(seed)
    c = (np.arange(size) + 0.5) / size * 2.0 - 1.0
    y, x = np.meshgrid(-c, c, indexing="ij")
    rho = np.sqrt(x * x + y * y)
    ang = np.arctan2(y, x)
    pupil = g.pupil_radius / g.iris_radius
    limbus = g.limbus_radius / g.iris_radius
    t = np.clip((rho - pupil) / (limbus - pupil), 0.0, 1.0)
    inner = np.array([0.55, 0.42, 0.22])
    outer = np.array([0.36, 0.48, 0.55])
    collarette = 1.0 / (1.0 + np.exp(-(t - 0.35) * 18.0))
    base = inner + (outer - inner) * collarette[..., None]
    fibres = np.zeros_like(rho)
    for k, (freq, amp) in enumerate(((37, 0.10), (71, 0.07), (113, 0.05), (173, 0.035))):
        phase = rng.uniform(0, 2 * math.pi)
        fibres += amp * np.sin(freq * ang + phase + 3.0 * np.sin(2.0 * ang + k) * t)
    crypts = np.zeros_like(rho)
    for _ in range(26):
        ca, ct = rng.uniform(-math.pi, math.pi), rng.uniform(0.2, 0.8)
        da = np.angle(np.exp(1j * (ang - ca)))
        crypts += np.exp(-((da * (pupil + t * (limbus - pupil)) / 0.03) ** 2 + ((t - ct) / 0.06) ** 2))
    shade = 1.0 + fibres - 0.35 * np.clip(crypts, 0.0, 1.0)
    shade *= 1.0 - 0.55 * np.exp(-((t - 1.0) / 0.10) ** 2)
    shade *= 1.0 - 0.45 * np.exp(-(t / 0.06) ** 2)
    rgb = np.clip(base * shade[..., None], 0.0, 1.0)
    rgb = np.where((rho > limbus * 1.04)[..., None], np.array([0.10, 0.11, 0.13]), rgb)
    return np.where((rho < pupil * 1.02)[..., None], np.array([0.012, 0.012, 0.012]), rgb)


# -- the analytic studio the cornea reflects (lab T-D: `studio_env` + `eye_math`; AD-033 §5.3) -------------------------
# Directions are view space (+Z toward the camera): the studio moves with the camera, like the Worklight's default
# camera-relative lights, so the wet highlight stays where the artist expects it while orbiting (`PROVISIONAL`).

MIN_DIRECT_ROUGHNESS = 0.03
TD_SIGMA_SCALE = 0.8
TD_SIGMA_POWER = 0.675
STUDIO_ZENITH = (0.20, 0.20, 0.20)
STUDIO_HORIZON = (0.12, 0.12, 0.12)
STUDIO_FLOOR = (0.035, 0.035, 0.035)
STUDIO_HORIZON_WIDTH = 0.05
STUDIO_EDGE_SIGMA = math.radians(0.5)
#: (azimuth, elevation, half width, half height in degrees; linear radiance): the key softbox and a rim strip.
STUDIO_LIGHTS = ((35.0, 25.0, 18.0, 13.0, (8.0, 8.0, 8.0)), (-115.0, 10.0, 4.0, 32.0, (4.0, 4.0, 4.0)))
#: The cornea's direct key highlight (the lab's key irradiance) and its roughness / F0 (IOR 1.376).
KEY_IRRADIANCE = 3.0
CORNEA_ROUGHNESS = 0.04
CORNEA_F0 = f0_between(N_AIR, N_CORNEA)


def local_direction(azimuth: float, elevation: float) -> np.ndarray:
    az, el = math.radians(azimuth), math.radians(elevation)
    return np.array([math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az)])


def studio_frames() -> list[tuple[np.ndarray, np.ndarray, np.ndarray, tuple[float, float], tuple]]:
    """(centre, right, up, (half width, half height) in radians, radiance) per studio light."""
    out = []
    for az, el, hw, hh, radiance in STUDIO_LIGHTS:
        c = local_direction(az, el)
        right = np.cross(np.array([0.0, 1.0, 0.0]), c)
        right /= np.linalg.norm(right)
        out.append((c, right, np.cross(c, right), (math.radians(hw), math.radians(hh)), radiance))
    return out


def _erf(x):
    x = np.asarray(x, dtype=np.float64)
    s, a = np.sign(x), np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * a)
    poly = ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t
    return s * (1.0 - poly * np.exp(-a * a))


def _box(x, half_width, sigma):
    k = 1.0 / (math.sqrt(2.0) * sigma)
    return 0.5 * (_erf((x + half_width) * k) - _erf((x - half_width) * k))


def td_env(d, roughness: float) -> np.ndarray:
    """Linear radiance (..., 3) of the studio toward view-space unit directions `d`, as a lobe of `roughness` sees it."""
    d = np.asarray(d, dtype=np.float64)
    lobe = TD_SIGMA_SCALE * (roughness * roughness) ** TD_SIGMA_POWER
    sigma = math.sqrt(STUDIO_EDGE_SIGMA ** 2 + lobe ** 2)
    width = math.sqrt(STUDIO_HORIZON_WIDTH ** 2 + lobe ** 2)
    y = d[..., 1]
    sky = np.asarray(STUDIO_HORIZON) + (np.asarray(STUDIO_ZENITH) - np.asarray(STUDIO_HORIZON)) * np.clip(y, 0, 1)[..., None]
    t = np.clip((y + width) / (2.0 * width), 0.0, 1.0)
    out = np.asarray(STUDIO_FLOOR) + (sky - np.asarray(STUDIO_FLOOR)) * (t * t * (3.0 - 2.0 * t))[..., None]
    for c, right, up, (hw, hh), radiance in studio_frames():
        dc = np.sum(d * c, axis=-1)
        x = np.arctan2(np.sum(d * right, axis=-1), dc + 1e-12)
        yy = np.arctan2(np.sum(d * up, axis=-1), dc + 1e-12)
        s = np.clip(dc / 0.25, 0.0, 1.0)
        w = _box(x, hw, sigma) * _box(yy, hh, sigma) * (s * s * (3.0 - 2.0 * s))
        out = out + w[..., None] * np.asarray(radiance)
    return out


def worklight_light(n, light: dict) -> np.ndarray:
    """The Worklight's diffuse light at world normals `n` (`gl_render_store.FRAGMENT_SRC`: ambient + key and fill
    with wrap), from `Viewport.light_uniforms()` - the eye's diffuse terms use it so an eye sits in the scene's light."""
    n = np.asarray(n, dtype=np.float64)

    def wrap(ndl, w):
        return np.maximum((ndl + w) / (1.0 + w), 0.0)

    key = wrap(np.sum(n * np.asarray(light["u_key_dir"]), -1), light["u_key_wrap"])[..., None]
    fill = wrap(np.sum(n * np.asarray(light["u_fill_dir"]), -1), light["u_fill_wrap"])[..., None]
    return light["u_ambient"] + np.asarray(light["u_key_color"]) * key + np.asarray(light["u_fill_color"]) * fill
