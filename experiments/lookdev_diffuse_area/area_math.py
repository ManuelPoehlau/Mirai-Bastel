"""The diffuse response of a finite key light - NumPy models (GL-free), 2026-11-24.

Disposable research code for `docs/research/LOOKDEV_DIFFUSE_AREA_LIGHT_TERMINATOR_ASSESSMENT_2026-11-24.md`. Nothing in
`src/` imports it. Every function takes `c` = n . l to the light's *centre* (the value production's `ld_diffuse` uses)
and returns the light's diffuse factor in production's units: 1 at normal incidence, i.e. `u_ld_light_color` keeps
meaning "the illuminance the light delivers to a surface facing it" for every size (see `NORMALIZATION`).

The emitter is a uniform sphere (a disk facing the receiver): angular radius sigma, `s = sin(sigma)`. For a sphere the
on-axis illuminance does not depend on its radius at constant power, so "same light colour at every size" means "same
emitted power" - only the terminator band |c| < s changes.

Methods (the assessment's A / B / B2 / C):
- `lambert_wrap`  A, production today: max((c + w) / (1 + w), 0); no size.
- `area_quad`     B, the cheap analytic one: the sphere light's irradiance as the C1 quadratic between c = -s and
                  c = +s ((x + s)^2 / 4s, a horizon spline common in real-time engines), combined with the
                  material's wrap by shifting the cosine (x = c + w) and renormalizing by 1 + w.
- `area_exact`    B2, the sphere light's exact irradiance (Snyder 1996; the form of Lagarde & de Rousiers 2014, the
                  Frostbite notes) - acos, atan and three square roots; wrap combined as in B.
- `area_samples`  C, N deterministic directions on the emitter's cap (a Vogel spiral, uniform in solid angle), wrap
                  applied per direction - the "small sample" reference.
- `area_reference` the same with many directions (the ground truth for the shading term).
- `wrap_by_size`  A', the naive alternative: the size added to the wrap - only broadens Lambert (shown for contrast).

`size_to_sin(size)`: the candidate mapping of the normalized `StudioLight.size` (0..1) to s (`S_MAX` at size 1).
"""

from __future__ import annotations

import math

import numpy as np

#: Candidate mapping (assessment §3): s = sin(sigma) = size x S_MAX, sigma(1) = 40 degrees (a large softbox close to the
#: face); sigma(0.25) = 9.2, sigma(0.5) = 18.7. `PROVISIONAL` - the visual tests decide.
S_MAX = math.sin(math.radians(40.0))
#: Below this s the analytic band is skipped (a point light: Lambert / wrap exactly).
S_MIN = 1e-4
#: The documented energy convention.
NORMALIZATION = ("u_ld_light_color = illuminance at normal incidence, unchanged by the size; for a sphere emitter this "
                 "is constant emitted power. Only the band |n.l| < sin(sigma) changes.")
GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))


def size_to_sin(size, s_max: float = S_MAX) -> np.ndarray:
    return np.clip(np.asarray(size, dtype=np.float64), 0.0, 1.0) * s_max


def sigma_degrees(size, s_max: float = S_MAX) -> np.ndarray:
    return np.degrees(np.arcsin(size_to_sin(size, s_max)))


# -- A ------------------------------------------------------------------------------------------------------------------

def lambert_wrap(c, w=0.0) -> np.ndarray:
    c = np.asarray(c, dtype=np.float64)
    return np.maximum((c + w) / (1.0 + w), 0.0)


def wrap_by_size(c, w, s) -> np.ndarray:
    """A': the naive alternative - the light's s added to the material's wrap."""
    return lambert_wrap(c, np.asarray(w) + np.asarray(s))


# -- B ------------------------------------------------------------------------------------------------------------------

def horizon_quad(x, s) -> np.ndarray:
    """The sphere light's normalized irradiance as a C1 spline: x above s, 0 below -s, (x + s)^2 / 4s between (value s
    and slope 1 at +s, value and slope 0 at -s). Never below max(x, 0)."""
    x = np.asarray(x, dtype=np.float64)
    s = np.maximum(np.asarray(s, dtype=np.float64), S_MIN)
    band = np.square(np.maximum(x + s, 0.0)) / (4.0 * s)
    return np.where(x >= s, x, band)


def area_quad(c, s, w=0.0) -> np.ndarray:
    return horizon_quad(np.asarray(c, dtype=np.float64) + w, s) / (1.0 + np.asarray(w, dtype=np.float64))


# -- B2 -----------------------------------------------------------------------------------------------------------------

def sphere_irradiance(x, s) -> np.ndarray:
    """Exact irradiance of a uniform sphere light / (pi sin^2 sigma) (= x above the horizon): Snyder's formula in the
    form of the Frostbite notes. x = cos of the angle between normal and the light's centre."""
    x = np.clip(np.asarray(x, dtype=np.float64), -1.0, 1.0)
    s = np.maximum(np.asarray(s, dtype=np.float64), S_MIN)
    s2 = s * s
    sin_t = np.sqrt(np.maximum(1.0 - x * x, 1e-12))
    xx = np.sqrt(np.maximum(1.0 / s2 - 1.0, 0.0))
    y = np.clip(-xx * (x / sin_t), -1.0, 1.0)
    sty = sin_t * np.sqrt(np.maximum(1.0 - y * y, 0.0))
    partial = ((x * np.arccos(y) - xx * sty) * s2 + np.arctan2(sty, xx)) / (math.pi * s2)
    return np.where(x * x > s2, np.maximum(x, 0.0), np.maximum(partial, 0.0))


def area_exact(c, s, w=0.0) -> np.ndarray:
    # the shifted cosine c + w can exceed 1 on the lit side, where the light is fully above the horizon anyway
    x = np.asarray(c, dtype=np.float64) + w
    return np.where(x >= s, x, sphere_irradiance(x, s)) / (1.0 + np.asarray(w, dtype=np.float64))


# -- C ------------------------------------------------------------------------------------------------------------------

def cap_offsets(count: int) -> np.ndarray:
    """(count, 3): per direction (u, cos phi, sin phi) of a Vogel spiral on the cap, u in (0, 1) uniform in solid angle
    (cos alpha = 1 - u (1 - cos sigma))."""
    i = np.arange(count, dtype=np.float64)
    u = (i + 0.5) / count
    phi = i * GOLDEN_ANGLE
    return np.stack([u, np.cos(phi), np.sin(phi)], axis=-1)


def cap_directions(s: float, count: int) -> np.ndarray:
    """(count, 3) unit directions on the cap of half angle asin(s) around +Z."""
    cos_sigma = math.sqrt(max(1.0 - s * s, 0.0))
    off = cap_offsets(count)
    cos_a = 1.0 - off[:, 0] * (1.0 - cos_sigma)
    sin_a = np.sqrt(np.maximum(1.0 - cos_a * cos_a, 0.0))
    return np.stack([sin_a * off[:, 1], sin_a * off[:, 2], cos_a], axis=-1)


def area_samples(c, s: float, w=0.0, count: int = 16) -> np.ndarray:
    """C: the mean over `count` cap directions of the wrapped cosine, each cosine scaled by 2 / (1 + cos sigma) so the
    lit side stays Lambert (the cap's mean cosine is c (1 + cos sigma) / 2). The normal lies in the XZ plane at angle
    acos(c) from the centre (the cap's spiral is not rotationally symmetric: this is one azimuth of it)."""
    c = np.asarray(c, dtype=np.float64)
    if s < S_MIN:
        return lambert_wrap(c, w)
    d = cap_directions(s, count)
    norm = 2.0 / (1.0 + math.sqrt(1.0 - s * s))
    n = np.stack([np.sqrt(np.maximum(1.0 - c * c, 0.0)), np.zeros_like(c), c], axis=-1)
    ci = (n @ d.T) * norm
    return np.mean(np.maximum((ci + w) / (1.0 + w), 0.0), axis=-1)


def area_reference(c, s: float, w=0.0, count: int = 4096) -> np.ndarray:
    return area_samples(c, s, w, count)


# -- geometry: sphere and cylinder images (convex; the attached shadow only) -------------------------------------------

def sphere_normals(size: int) -> tuple[np.ndarray, np.ndarray]:
    """(normals (size, size, 3), mask): an orthographic unit sphere seen along -Z."""
    y, x = np.mgrid[1.0:-1.0:size * 1j, -1.0:1.0:size * 1j]
    r2 = x * x + y * y
    mask = r2 < 1.0
    z = np.sqrt(np.maximum(1.0 - r2, 0.0))
    return np.stack([x, y, z], axis=-1), mask


def cylinder_normals(size: int) -> tuple[np.ndarray, np.ndarray]:
    """A vertical cylinder (axis Y) filling the frame width, seen along -Z."""
    y, x = np.mgrid[1.0:-1.0:size * 1j, -1.0:1.0:size * 1j]
    mask = np.abs(x) < 1.0
    z = np.sqrt(np.maximum(1.0 - x * x, 0.0))
    return np.stack([x, np.zeros_like(x), z], axis=-1), mask


def direction(azimuth: float, elevation: float) -> np.ndarray:
    az, el = math.radians(azimuth), math.radians(elevation)
    return np.array([math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az)])


def frame_for(l) -> tuple[np.ndarray, np.ndarray]:
    """(right, up) around l (production's `key_frame`)."""
    l = np.asarray(l, dtype=np.float64)
    ref = np.array([0.0, 1.0, 0.0]) if abs(l[1]) < 0.999 else np.array([1.0, 0.0, 0.0])
    right = np.cross(ref, l)
    right /= np.linalg.norm(right)
    return right, np.cross(l, right)


def shade_normals(normals, light, method: str, size: float, wrap=0.0, count: int = 16) -> np.ndarray:
    """The light's diffuse factor per normal by `method` (A, A', B, B2, C, REF). C / REF sample the real cap around the
    light (3D, not one azimuth)."""
    n = np.asarray(normals, dtype=np.float64)
    c = n @ np.asarray(light, dtype=np.float64)
    s = float(size_to_sin(size))
    if method == "A":
        return lambert_wrap(c, wrap)
    if method == "A'":
        return wrap_by_size(c, wrap, s)
    if method == "B":
        return area_quad(c, s, wrap)
    if method == "B2":
        return area_exact(c, s, wrap)
    if method in ("C", "REF"):
        if s < S_MIN:
            return lambert_wrap(c, wrap)
        k = count if method == "C" else 2048
        local = cap_directions(s, k)
        right, up = frame_for(light)
        dirs = local[:, 0:1] * right + local[:, 1:2] * up + local[:, 2:3] * np.asarray(light)
        norm = 2.0 / (1.0 + math.sqrt(1.0 - s * s))
        out = np.zeros(c.shape)
        for d in dirs:
            out += np.maximum((n @ d * norm + wrap) / (1.0 + wrap), 0.0)
        return out / len(dirs)
    raise ValueError(method)


def mean_excess(s: float) -> float:
    """Relative brightness a uniformly lit sphere gains from the B band (all normals): (s^2 / 12) / (1 / 4) = s^2 / 3."""
    return s * s / 3.0
