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
from functools import lru_cache

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
        return _chamber_angle(self)


@lru_cache(maxsize=256)
def _chamber_angle(g: EyeGeometry) -> tuple[float, float]:
    """`EyeGeometry.angle`, once per anatomy: the eye pass asks for it for every eye on every frame, and the 80-step
    bisection was most of that pass's CPU time (reference PC, 2026-11-16: about 3.5 ms per eye and frame,
    `experiments/drag_cost/RESULTS_EYE_PREVIEW_REFERENCE_PC_2026-11-16.md`). The same numbers as before."""
    lo, hi = 0.0, POSTERIOR_RADIUS
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if float(g.posterior_z(mid)) > float(g.iris_z(mid)):
            lo = mid
        else:
            hi = mid
    return lo, float(g.iris_z(lo))


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


# -- the look (Eye LookDev phase 3; `core.EyeLook`, Manu I-5 / I-8 / I-10, 2026-11-16) ---------------------------------
# GLSL twins in `eye_shaders.LOOK_LIB_SRC`, drawn only in the "full" tier and only for an eye whose look has an amount
# above 0 (`look_active`). Every term is neutral at amount 0. All constants `PROVISIONAL`.

#: The irregularity texture (`film_noise`): tileable, NOISE_SIZE² RGB8 with mip maps. R / G: the gradient of a smooth
#: height field (its length has RMS 1; stored clipped to ±NOISE_GRADIENT_MAX), B: a smooth roughness noise in [-1, 1].
NOISE_SIZE = 256
NOISE_FEATURES = 16.0  # bumps across one tile
NOISE_SEED = 11
NOISE_GRADIENT_MAX = 3.0
#: The irregularity's roughness change (assessment §C.2: about 0.03-0.07 around the cornea's 0.04): + s (a + b nb) with
#: s = irregularity / IRREGULAR_FULL_DEG, at most 1.
IRREGULAR_ROUGHNESS = (0.01, 0.02)
IRREGULAR_FULL_DEG = 1.0
#: The lid band (I-10): the lash edge seen from the eye, (length in eye radii, angle above the forward axis in degrees)
#: from the lid margin. A reflected ray passing beyond that edge sees lid, lashes or brow (dark).
UPPER_LASH = (0.6, 25.0)
LOWER_LASH = (0.3, -25.0)
LID_BAND_SOFT = math.radians(6.0)
#: The soft key highlight (I-8): an area light at the Worklight key, the studio key softbox's aspect (18 : 13), half size
#: at softness 1 in degrees; the energy is the point highlight's (KEY_IRRADIANCE), so a larger area has a lower peak.
KEY_SOFT_HALF = (10.0, 7.2)
#: The amounts of `core.EyeLook` (neutral at 0).
LOOK_AMOUNTS = ("wet_sclera", "irregularity_deg", "highlight_softness", "lid_shadow", "lid_band")


def look_active(look) -> bool:
    """True when an `EyeLook` changes the picture (some amount above 0)."""
    return look is not None and any(getattr(look, name) > 0.0 for name in LOOK_AMOUNTS)


def lash_offset(lash) -> tuple[float, float]:
    """(dy, dz) of a lash edge from its margin."""
    length, angle = lash
    return length * math.sin(math.radians(angle)), length * math.cos(math.radians(angle))


def film_noise(size: int = NOISE_SIZE, features: float = NOISE_FEATURES, seed: int = NOISE_SEED) -> np.ndarray:
    """The irregularity texture as stored: uint8 (size, size, 3), row j / column i = the texel at t = (j + 0.5) / size,
    s = (i + 0.5) / size (the first row is the bottom one, as pyglet uploads it). Deterministic and tileable (periodic
    spectral synthesis)."""
    rng = np.random.default_rng(seed)
    k = np.fft.fftfreq(size) * size  # cycles per tile
    kx, ky = np.meshgrid(k, k)  # kx along s (columns), ky along t (rows)
    low = np.exp(-(np.hypot(kx, ky) / features) ** 2)
    height = np.fft.fft2(rng.random((size, size)) - 0.5) * low
    gx = np.real(np.fft.ifft2(2j * math.pi * kx * height))
    gy = np.real(np.fft.ifft2(2j * math.pi * ky * height))
    norm = math.sqrt(float(np.mean(gx * gx + gy * gy)))
    rough = np.real(np.fft.ifft2(np.fft.fft2(rng.random((size, size)) - 0.5) * np.exp(-(np.hypot(kx, ky) / (0.5 * features)) ** 2)))
    rough = np.clip(rough / (2.5 * float(np.std(rough))), -1.0, 1.0)
    channels = np.stack([np.clip(gx / norm / NOISE_GRADIENT_MAX, -1.0, 1.0),
                         np.clip(gy / norm / NOISE_GRADIENT_MAX, -1.0, 1.0), rough], -1)
    return np.round((0.5 + 0.5 * channels) * 255.0).astype(np.uint8)


def film_decode(texel) -> np.ndarray:
    """A texel as the shader reads it (`film_sample`): (gradient x, gradient y, roughness noise)."""
    t = np.asarray(texel, dtype=np.float64)
    return (t * 2.0 - 1.0) * np.array([NOISE_GRADIENT_MAX, NOISE_GRADIENT_MAX, 1.0])


_MASK64 = (1 << 64) - 1


def _splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & _MASK64
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & _MASK64
    return x ^ (x >> 31)


def noise_offset(variation: int, seed: int) -> tuple[float, float]:
    """Where an eye reads the shared irregularity texture: a fixed point of the tile per (object, look seed), so two eyes
    never show the same pattern (assessment §C.2 "per-eye variation") and a new seed gives a new one."""
    a = _splitmix64(((int(variation) & 0xFFFFFFFF) << 32) | (int(seed) & 0xFFFFFFFF))
    b = _splitmix64(a)
    return (a >> 11) / float(1 << 53), (b >> 11) / float(1 << 53)


def look_values(look, variation: int = 0) -> dict:
    """The look's derived numbers (GL-free; `eye_pass.look_uniforms` names them): tilt (tan), roughness share, noise
    scale and offset, lid (upper, lower, shadow width), soft highlight half size and radiance."""
    tilt = math.tan(math.radians(look.irregularity_deg))
    soft = look.highlight_softness
    half = (math.radians(KEY_SOFT_HALF[0]) * soft, math.radians(KEY_SOFT_HALF[1]) * soft)
    return {
        "tilt": tilt, "rough_s": min(look.irregularity_deg / IRREGULAR_FULL_DEG, 1.0),
        "noise_scale": 1.0 / (MM * look.irregularity_mm * NOISE_FEATURES), "noise_offset": noise_offset(variation, look.seed),
        "lid": (look.lid_upper, look.lid_lower, look.lid_shadow_mm * MM),
        "soft_half": half, "soft_radiance": KEY_IRRADIANCE / (4.0 * half[0] * half[1]) if soft > 0.0 else 0.0,
    }


def film_uv(p, scale: float, offset) -> np.ndarray:
    """Irregularity texture coordinates of eye-local surface points: the angle from the eye axis along the azimuth
    (an azimuthal equidistant map, continuous over the cornea, the limbus and the sclera), `scale` tiles per radian."""
    p = np.asarray(p, dtype=np.float64)
    rho = np.hypot(p[..., 0], p[..., 1])
    theta = np.arctan2(rho, p[..., 2])
    k = np.where(rho > 1e-6, theta / np.where(rho > 1e-6, rho, 1.0), 1.0 / np.maximum(p[..., 2], 1e-6))
    return p[..., :2] * (k * scale)[..., None] + np.asarray(offset, dtype=np.float64)


def film_frame(p):
    """(T_u, T_v): the surface directions of `film_uv`'s two axes at eye-local points `p` (on the sphere through p)."""
    s = normalize(p)
    rho = np.hypot(s[..., 0], s[..., 1])
    safe = np.where(rho > 1e-9, rho, 1.0)
    cphi = np.where(rho > 1e-9, s[..., 0] / safe, 1.0)
    sphi = np.where(rho > 1e-9, s[..., 1] / safe, 0.0)
    ct, st = s[..., 2], rho
    e_t = np.stack([ct * cphi, ct * sphi, -st], -1)
    e_p = np.stack([-sphi, cphi, np.zeros_like(cphi)], -1)
    return cphi[..., None] * e_t - sphi[..., None] * e_p, sphi[..., None] * e_t + cphi[..., None] * e_p


def film_normal(n, p, g, tilt: float) -> np.ndarray:
    """The reflection normal tilted by the irregularity gradient `g` (..., 2) at points `p`: n + tilt (g_u T_u + g_v T_v),
    normalized. Only the reflection uses it (assessment §C.2: perturbing the refraction would make the iris swim)."""
    tu, tv = film_frame(p)
    g = np.asarray(g, dtype=np.float64)
    return normalize(np.asarray(n, dtype=np.float64) + tilt * (g[..., :1] * tu + g[..., 1:2] * tv))


def film_roughness(base, nb, rough_s: float):
    return np.asarray(base, dtype=np.float64) + rough_s * (IRREGULAR_ROUGHNESS[0] + IRREGULAR_ROUGHNESS[1] * np.asarray(nb))


def lid_shadow_weight(p_rest, lid) -> np.ndarray:
    """I-10 lid shadow (rest frame): 0 more than the shadow width below the upper lid margin, 1 at and above it."""
    upper, _lower, width = lid
    return _smooth((np.asarray(p_rest, dtype=np.float64)[..., 1] - (upper - width)) / width)


def lid_margin_z(x, y, g: EyeGeometry):
    """z of the eyeball's front surface (cornea inside the limbus, else sclera) at eye-local (x, y)."""
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    r2 = x * x + y * y
    zs = np.sqrt(np.maximum(1.0 - r2, 0.0))
    zc = g.anterior_centre_z + np.sqrt(np.maximum(g.cornea_radius ** 2 - r2, 0.0))
    return np.where(r2 < g.limbus_radius ** 2, np.maximum(zs, zc), zs)


def _elevation(y, z):
    y, z = np.asarray(y, dtype=np.float64), np.asarray(z, dtype=np.float64)
    defined = (np.abs(y) + np.abs(z)) > 1e-6
    return np.where(defined, np.arctan2(y, z), 0.0)


def lid_occlusion(p_rest, r_rest, roughness, lid, g: EyeGeometry) -> np.ndarray:
    """I-10 lid band (rest frame): how much the lid / lashes hide what the reflected ray `r_rest` from `p_rest` would
    see, 0..1. The lid is a straight edge across the eye at the margin height, its lashes reaching to a lash edge
    (UPPER_LASH / LOWER_LASH); a ray rising above the upper edge (or falling below the lower one) as seen from the point
    is hidden, soft over LID_BAND_SOFT and the reflection's own blur. The elevations are taken in the y-z plane."""
    p, r = np.asarray(p_rest, dtype=np.float64), np.asarray(r_rest, dtype=np.float64)
    upper, lower, _width = lid
    lobe = TD_SIGMA_SCALE * (np.asarray(roughness, dtype=np.float64) ** 2) ** TD_SIGMA_POWER
    soft = np.sqrt(LID_BAND_SOFT ** 2 + lobe * lobe)
    e_r = _elevation(r[..., 1], r[..., 2])
    out = []
    for margin, lash, sign in ((upper, UPPER_LASH, 1.0), (lower, LOWER_LASH, -1.0)):
        dy, dz = lash_offset(lash)
        tip_y, tip_z = margin + dy, lid_margin_z(p[..., 0], margin, g) + dz
        e_tip = np.arctan2(tip_y - p[..., 1], tip_z - p[..., 2])
        t = np.clip((e_r - (e_tip - soft)) / (2.0 * soft), 0.0, 1.0)
        step = t * t * (3.0 - 2.0 * t)
        out.append(step if sign > 0 else 1.0 - step)
    return np.maximum(out[0], out[1])


def area_key(r, c, up_ref, roughness, half, radiance, right_ref=(1.0, 0.0, 0.0)) -> np.ndarray:
    """I-8 soft highlight: the radiance a lobe of `roughness` around the reflected direction `r` sees of a rectangular
    area light of half size `half` (radians) centred on the key direction `c`, oriented to `up_ref` (the view's up; the
    studio's softboxes are oriented the same way). `right_ref` stands in where the key is parallel to `up_ref`."""
    r, c, up_ref = (np.asarray(v, dtype=np.float64) for v in (r, c, up_ref))
    right = np.cross(up_ref, c)
    length = np.linalg.norm(right, axis=-1, keepdims=True)
    right = np.where(length > 1e-4, right / np.maximum(length, 1e-300), np.asarray(right_ref, dtype=np.float64))
    up = np.cross(c, right)
    lobe = TD_SIGMA_SCALE * (np.asarray(roughness, dtype=np.float64) ** 2) ** TD_SIGMA_POWER
    sigma = np.sqrt(STUDIO_EDGE_SIGMA ** 2 + lobe * lobe)
    dc = np.sum(r * c, -1)
    x = np.arctan2(np.sum(r * right, -1), dc + 1e-12)
    y = np.arctan2(np.sum(r * up, -1), dc + 1e-12)
    s = np.clip(dc / 0.25, 0.0, 1.0)

    def box(v, hw):
        k = 1.0 / (math.sqrt(2.0) * sigma)
        return 0.5 * (_erf((v + hw) * k) - _erf((v - hw) * k))

    return radiance * box(x, half[0]) * box(y, half[1]) * (s * s * (3.0 - 2.0 * s))


# -- the iris (Eye LookDev phase 4; `core.EyeIris`, Manu 2026-11-16: "1 go (v11), 2 go") ------------------------------
# GLSL twins in `eye_shaders.IRIS_LIB_SRC`, drawn only in the "full" tier and only for an eye whose iris values have an
# amount above 0 (`iris_active`). Every term is neutral at amount 0. All constants `PROVISIONAL`.

#: The key's path back from an iris point through the cornea (`iris_light_path`): incident ray, normal and refracted
#: ray lie in one plane through the cornea's centre, so the entry point is one angle in that plane, found by secant
#: steps from the straight path's exit (max. 2e-5 eye radii from the converged point after 6 steps over keys up to 85
#: degrees off the axis; a plain fixed-point iteration needed > 12 steps at grazing keys). A residual above
#: IRIS_LIGHT_TOLERANCE means no path: beyond the caustic, the key cannot reach the point (checked against a forward
#: ray trace, `test_eye_iris.py`).
IRIS_LIGHT_STEPS = 6
IRIS_LIGHT_TOLERANCE = 1e-4
#: The two neighbours of the finite difference start from the point's own solution (their planes differ by < 1e-2
#: rad): three secant steps leave < 1e-9 rad at p99, 1e-4 rad at worst (the concentration then within 1 %).
IRIS_LIGHT_WARM_STEPS = 3
IRIS_LIGHT_WARM_OFFSET = 1e-3
#: The finite-difference step (eye radii) of the beam's area at the iris (`iris_key_terms`): 0.12 mm.
IRIS_LIGHT_DELTA = 0.01
#: The concentration's cap (a caustic would be infinite) and the smallest cosine it divides by.
CRESCENT_MAX = 4.0
CRESCENT_MIN_COS = 0.2
#: The dark margin of the pupil (`pupil_margin`): its width beyond the pupil edge.
PUPIL_MARGIN_MM = 0.35
#: The height derived from the iris image's brightness (`iris_height`): the high-pass's Gaussian (share of the image
#: width), the RMS that maps to the full height, and the soft edge of the iris annulus (share of half the image width).
HEIGHT_HIGHPASS = 0.03
HEIGHT_RANGE = 2.5
HEIGHT_EDGE = 0.04
#: The amounts of `core.EyeIris` (neutral at 0).
IRIS_AMOUNTS = ("light", "crescent", "rim_shadow", "relief", "pupil_edge_mm", "pupil_margin")
IRIS_KEY_AMOUNTS = ("light", "crescent", "rim_shadow")


def iris_active(look) -> bool:
    """True when an `EyeLook`'s iris values change the picture (some amount above 0)."""
    iris = getattr(look, "iris", None)
    return iris is not None and any(getattr(iris, name) > 0.0 for name in IRIS_AMOUNTS)


def iris_values(iris, g: EyeGeometry, texture_width: int = 512) -> dict:
    """The iris's derived numbers (GL-free; `eye_pass.iris_uniforms` names them): the key terms' switch, the rim
    shadow's width, the relief's depth and step (one texel of the image at the planar mapping), the pupil edge."""
    return {
        "key": sum(getattr(iris, name) for name in IRIS_KEY_AMOUNTS),
        "rim_width": iris.rim_shadow_mm * MM,
        "relief_depth": iris.relief * iris.relief_mm * MM,
        "relief_step": 2.0 * g.iris_radius / max(int(texture_width), 1),
        "pupil_edge": iris.pupil_edge_mm * MM,
        "margin_width": PUPIL_MARGIN_MM * MM,
    }


def _light_miss(phi, hx, hy, g: EyeGeometry):
    """In the plane of the key `l` (x) and the point (y >= 0), the cornea's centre at the origin: how far the key
    refracted at the cornea's point at angle `phi` from `l` misses the point (h - E) x t."""
    c, s = np.cos(phi), np.sin(phi)
    eta = N_AIR / N_EFFECTIVE
    m = np.sqrt(np.maximum(1.0 - eta * eta * (1.0 - c * c), 0.0)) - eta * c
    return (hx - g.cornea_radius * c) * (-m * s) - (hy - g.cornea_radius * s) * (-eta - m * c)


def iris_light_path(hit, l, g: EyeGeometry, start=None):
    """The Worklight key's path to iris points `hit` (eye-local), back through the cornea (one surface, n 1.3375, as
    refraction V2): `l` the unit direction toward the key. Returns (valid, entry: where the light enters the cornea,
    d: the unit direction from the hit toward the entry, cos_in: the key's cosine at the entry, aperture: the radius at
    which the path crosses the limbus plane - beyond the limbus radius the sclera shades the point, phi: the entry's
    angle from `l` in the path's plane). Not valid: no path (the key cannot reach the point through the cornea).
    `start`: a neighbour's `phi` to start from (IRIS_LIGHT_WARM_STEPS steps) instead of the straight path."""
    hit = np.asarray(hit, dtype=np.float64)
    l = np.broadcast_to(np.asarray(l, dtype=np.float64), hit.shape)
    ca = np.array([0.0, 0.0, g.anterior_centre_z])
    radius, eta = g.cornea_radius, N_AIR / N_EFFECTIVE
    q = hit - ca
    hx = _dot(q, l)
    w = q - hx[..., None] * l
    hy = np.linalg.norm(w, axis=-1)
    other = np.where(np.abs(l[..., :1]) < 0.9, np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]))
    v = np.where((hy > 1e-9)[..., None], w / np.maximum(hy, 1e-12)[..., None], normalize(np.cross(l, other)))
    if start is None:
        # first guess: where the straight path leaves the cornea; second: one fixed-point step from there
        p0 = np.arctan2(hy, np.sqrt(np.maximum(radius * radius - hy * hy, 0.0)))
        c, s = np.cos(p0), np.sin(p0)
        m = np.sqrt(np.maximum(1.0 - eta * eta * (1.0 - c * c), 0.0)) - eta * c
        dx, dy = eta + m * c, m * s
        norm = np.maximum(np.hypot(dx, dy), 1e-12)
        dx, dy = dx / norm, dy / norm
        b = hx * dx + hy * dy
        t = -b + np.sqrt(np.maximum(b * b - (hx * hx + hy * hy - radius * radius), 0.0))
        p1 = np.arctan2(hy + t * dy, hx + t * dx)
        steps = IRIS_LIGHT_STEPS
    else:
        p0 = np.asarray(start, dtype=np.float64)
        p1 = p0 + IRIS_LIGHT_WARM_OFFSET
        steps = IRIS_LIGHT_WARM_STEPS
    f0, f1 = _light_miss(p0, hx, hy, g), _light_miss(p1, hx, hy, g)
    for _ in range(steps):
        den = f1 - f0
        safe = np.abs(den) > 1e-12
        p2 = np.where(safe, p1 - f1 * (p1 - p0) / np.where(safe, den, 1.0), p1)
        p0, f0 = p1, f1
        p1, f1 = p2, _light_miss(p2, hx, hy, g)
    c, s = np.cos(p1), np.sin(p1)
    n = c[..., None] * l + s[..., None] * v
    entry = ca + radius * n
    m = np.sqrt(np.maximum(1.0 - eta * eta * (1.0 - c * c), 0.0)) - eta * c
    t_in = -eta * l - m[..., None] * n
    d = normalize(entry - hit)
    ok = (np.abs(f1) < IRIS_LIGHT_TOLERANCE) & (c > 0.0) & (_dot(hit - entry, t_in) > 0.0)
    dz = d[..., 2]
    s_plane = (g.limbus_z - hit[..., 2]) / np.where(dz > 1e-6, dz, 1.0)
    cross = hit[..., :2] + s_plane[..., None] * d[..., :2]
    aperture = np.where(dz > 1e-6, np.hypot(cross[..., 0], cross[..., 1]), 1e3)
    return ok, entry, d, c, aperture, p1


def _cone_point(xy, g: EyeGeometry):
    r = np.hypot(xy[..., 0], xy[..., 1])
    return np.concatenate([xy, (g.iris_a + g.iris_b * r)[..., None]], -1)


def iris_key_terms(hit, l, rim_width: float, g: EyeGeometry, concentration: bool = True):
    """Phase 4 roadmap #4: the key light at iris points `hit` after the cornea (the point on the iris cone below
    `hit.xy`). Returns (d, T, C, S): d the direction toward the refracted key (for N·L), T the cornea's transmission
    (Schlick, IOR 1.376 as the reflection), C the concentration (the beam's cross-section at the cornea over its
    cross-section at the iris: the cornea's focusing, > 1 opposite the key - the crescent - and < 1 near it; capped;
    checked against a forward ray trace, `test_eye_iris.py`), S the rim shadow (1 where the path would cross the
    limbus plane outside the limbus, soft over `rim_width`). Without `concentration` (the shader: crescent 0) C is 1
    and the two neighbours' paths - the costly part - are not traced."""
    xy = np.asarray(hit, dtype=np.float64)[..., :2]
    l = np.broadcast_to(np.asarray(l, dtype=np.float64), xy.shape[:-1] + (3,))
    h0 = _cone_point(xy, g)
    h1 = _cone_point(xy + np.array([IRIS_LIGHT_DELTA, 0.0]), g)
    h2 = _cone_point(xy + np.array([0.0, IRIS_LIGHT_DELTA]), g)
    ok, e0, d, cos_in, aperture, phi = iris_light_path(h0, l, g)
    trans = np.where(ok, 1.0 - schlick_scalar(CORNEA_F0, cos_in), 0.0)
    shadow = np.where(ok, _smooth((aperture - g.limbus_radius) / rim_width + 0.5), 1.0)
    if not concentration:
        return d, trans, np.ones_like(trans), shadow
    ok1, e1, _d1, _c1, _a1, _p1 = iris_light_path(h1, l, g, phi)
    ok2, e2, _d2, _c2, _a2, _p2 = iris_light_path(h2, l, g, phi)
    beam = np.abs(_dot(np.cross(e1 - e0, e2 - e0), l))
    area = np.linalg.norm(np.cross(h1 - h0, h2 - h0), axis=-1)
    cos_iris = _dot(iris_cone_normal(h0, g), d)
    conc = np.clip(beam / (area * np.maximum(cos_iris, CRESCENT_MIN_COS)), 0.0, CRESCENT_MAX)
    return d, trans, np.where(ok & ok1 & ok2, conc, 1.0), shadow


#: The key's table (`iris_light_table`): texels across the iris disc (2 iris radii; 0.22 mm per texel at the reference
#: eye). Traced per pixel the path cost the reference PC +8 / +13 ms in the Eye Lab view (1024×768 / 1920×1080,
#: 2026-11-16): once per eye into this table, then one texel per pixel.
IRIS_TABLE_SIZE = 64


def iris_table_value(xy, l, rim_width: float, crescent: float, rim_shadow: float, g: EyeGeometry):
    """One texel of the key's table at iris points `xy` (..., 2): (d.x, d.y, T, the crescent and rim shadow factor
    mix(1, C, crescent) (1 - rim_shadow S)); where no path reaches the point (T 0) d is the key's own direction."""
    xy = np.asarray(xy, dtype=np.float64)
    hit = np.concatenate([xy, np.zeros(xy.shape[:-1] + (1,))], -1)
    l = np.broadcast_to(np.asarray(l, dtype=np.float64), hit.shape)
    d, trans, conc, shadow = iris_key_terms(hit, l, rim_width, g, concentration=crescent > 0.0)
    d = np.where((trans > 0.0)[..., None], d, l)
    factor = (1.0 - crescent + crescent * conc) * (1.0 - rim_shadow * shadow)
    return np.stack([d[..., 0], d[..., 1], trans, factor], -1)


def iris_light_table(l, rim_width: float, crescent: float, rim_shadow: float, g: EyeGeometry,
                     size: int = IRIS_TABLE_SIZE) -> np.ndarray:
    """The key's table as the pass bakes it: (size, size, 4), row j / column i = the texel at y / x =
    ((j or i) + 0.5) / size * 2 - 1 iris radii (the first row is the bottom one, as GL stores it)."""
    c = ((np.arange(size) + 0.5) / size * 2.0 - 1.0) * g.iris_radius
    y, x = np.meshgrid(c, c, indexing="ij")
    return iris_table_value(np.stack([x, y], -1), l, rim_width, crescent, rim_shadow, g)


def relief_normal(hit, grad, g: EyeGeometry):
    """Roadmap #5: the iris cone's normal tilted by a height gradient `grad` (..., 2; d height / d x, d y,
    eye-local)."""
    hit, grad = np.asarray(hit, dtype=np.float64), np.asarray(grad, dtype=np.float64)
    r = np.maximum(np.hypot(hit[..., 0], hit[..., 1]), 1e-6)
    return normalize(np.stack([-g.iris_b * hit[..., 0] / r - grad[..., 0], -g.iris_b * hit[..., 1] / r - grad[..., 1],
                               np.ones_like(r)], -1))


def pupil_weights(r, width, margin_width: float, g: EyeGeometry):
    """Roadmap #7 at iris radii `r`: (the pupil's share - a step at the pupil radius for `width` 0, else soft over
    `width` centred on it -, the dark margin's weight: 1 at the pupil edge, 0 `margin_width` beyond it)."""
    r, width = np.asarray(r, dtype=np.float64), np.asarray(width, dtype=np.float64)
    soft = 1.0 - _smooth((r - g.pupil_radius) / np.where(width > 0.0, width, 1.0) + 0.5)
    pupil = np.where(width > 0.0, soft, (r < g.pupil_radius).astype(np.float64))
    return pupil, 1.0 - _smooth((r - g.pupil_radius) / margin_width)


def _gaussian_blur(a: np.ndarray, sigma: float) -> np.ndarray:
    """Periodic Gaussian blur (FFT); `sigma` in pixels."""
    h, w = a.shape
    fy, fx = np.fft.fftfreq(h)[:, None], np.fft.fftfreq(w)[None, :]
    kernel = np.exp(-2.0 * (math.pi * sigma) ** 2 * (fx * fx + fy * fy))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * kernel))


def iris_height(rgb: np.ndarray, pupil_share: float, edge_share: float) -> np.ndarray:
    """Roadmap #5 without a height channel (Manu 2026-11-16, "2 go"): a height in [0, 1] (0.5 = flat) from the iris
    image's brightness - bright fibres and the collarette raised, dark crypts deep. A high-pass (Gaussian of
    HEIGHT_HIGHPASS of the width, normalized over the iris annulus only) keeps the fibres and crypts and drops the
    colour zones; the result is scaled by its RMS. Outside the annulus between the image's pupil edge and iris edge
    (shares of half the image width; the fit's landmarks) the height is flat, so neither the black pupil nor the
    background makes a cliff. `rgb` (h, w, 3) sRGB in [0, 1], row order irrelevant."""
    h, w = rgb.shape[:2]
    y, x = np.meshgrid((np.arange(h) + 0.5) / h * 2.0 - 1.0, (np.arange(w) + 0.5) / w * 2.0 - 1.0, indexing="ij")
    rho = np.hypot(x, y)
    mask = (_smooth((rho - pupil_share) / HEIGHT_EDGE - 0.5) * (1.0 - _smooth((rho - edge_share) / HEIGHT_EDGE + 0.5)))
    if not mask.any():
        return np.full((h, w), 0.5)
    luma = np.asarray(rgb, dtype=np.float64)[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
    sigma = HEIGHT_HIGHPASS * w
    mean = _gaussian_blur(luma * mask, sigma) / np.maximum(_gaussian_blur(mask, sigma), 1e-6)
    detail = (luma - mean) * mask
    rms = math.sqrt(float(np.sum(detail * detail) / max(float(np.sum(mask)), 1.0)))
    if rms <= 1e-9:
        return np.full((h, w), 0.5)
    return 0.5 + 0.5 * np.clip(detail / (HEIGHT_RANGE * rms), -1.0, 1.0) * mask


# -- the sclera's colour map (AD-035 M1, Manu 2026-11-17 S-1 / S-13): the limbus-anchored front disc ------------------

#: The limbus's radius in the map, a share of half its width (`mirai.sclera_map.LIMBUS_SHARE`).
SCLERA_LIMBUS_SHARE = 0.25
#: The map's inscribed circle lies this far (degrees) from the front pole; beyond it the rim is held (clamped).
SCLERA_RIM_DEG = 130.0
SCLERA_RIM = math.radians(SCLERA_RIM_DEG)


def sclera_st(p, theta_ring: float) -> np.ndarray:
    """Map coordinates (s right = eye-local +X, t up = +Y, as the iris image) of eye-local points `p` on the sclera or
    the cornea: the image is the eye seen from the front. The radius in the image (share of half its width) is linear in
    the angle θ from the front pole on each side of the limbus (`theta_ring` = asin(limbus radius) -> `SCLERA_LIMBUS_SHARE`,
    `SCLERA_RIM` -> 1), so the painted limbus stays on the anatomy's limbus; beyond the rim the rim's colour is held.
    One formula for both sides of the ring (continuous there); at the front pole the radius goes to 0 (no direction
    needed), at the back pole (beyond the rim) any direction lands on the rim circle."""
    p = np.asarray(p, dtype=np.float64)
    rho = np.hypot(p[..., 0], p[..., 1])
    theta = np.arctan2(rho, p[..., 2])
    inner = SCLERA_LIMBUS_SHARE * theta / theta_ring
    outer = SCLERA_LIMBUS_SHARE + (1.0 - SCLERA_LIMBUS_SHARE) * (theta - theta_ring) / (SCLERA_RIM - theta_ring)
    r = np.minimum(np.where(theta < theta_ring, inner, outer), 1.0)
    safe = np.where(rho > 1e-6, rho, 1.0)
    direction = np.where((rho > 1e-6)[..., None], p[..., :2] / safe[..., None], np.array([1.0, 0.0]))
    return 0.5 + 0.5 * r[..., None] * direction


def sclera_texel(image: np.ndarray, st) -> np.ndarray:
    """The map's colour at `st`, bilinear at full resolution with the edge held (the pass's sampler: CLAMP_TO_EDGE).
    `image` rows run top-down as a file is read (row 0 = the top, t = 1); RGB in 0..1."""
    st = np.asarray(st, dtype=np.float64)
    h, w = image.shape[:2]
    x = np.clip(st[..., 0] * w - 0.5, 0.0, w - 1.0)
    y = np.clip((1.0 - st[..., 1]) * h - 0.5, 0.0, h - 1.0)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    img = np.asarray(image, dtype=np.float64)
    top = img[y0, x0] * (1.0 - fx) + img[y0, x1] * fx
    bottom = img[y1, x0] * (1.0 - fx) + img[y1, x1] * fx
    return top * (1.0 - fy) + bottom * fy
