"""P1c - the soft limbus transition: the GL-free reference (NumPy float64) of every limbus function (2026-11-14).

Manu's decisions of 2026-11-14 (plan `PLAN_P1c_LIMBUS_2026-11-14.md`): cumulative variants on top of P1b V2 (V3
selectable), shader-only (no geometry change), a limbal colour from a shader setting (default) or from the iris
image's own outer ring (a switch), a top / bottom asymmetry as an independent switch (default off).

| Level | Adds |
|---|---|
| L0 | nothing: P1b exactly (drawn by P1b's own code) |
| L1 | colour band: one gradient from the limbal colour at the chamber angle to the sclera albedo `band` outside the ring, on the cornea's limbal tissue and on the sclera (`colour_weight`, `tint`) |
| L2 | + shading normal blended from the cornea sphere's to the sclera sphere's across +-w around the ring (`normal_blend`); refraction keeps the true surface (geometry unchanged), only Fresnel / specular / lighting use the blended normal |
| L3 | + translucent limbus: limbal tissue and the sclera band transmit `transmission(u)` of what lies behind (the iris through the tissue / the sclera, `sclera_through`), falling to 0 at the band's outer edge |

**The limbus coordinate u** (lab units, 1 = 12 mm; 0 on the limbus ring, positive toward the sclera): on the sclera
the arc distance from the ring along the sphere (`sclera_u`), on the cornea the planar radius minus the ring's
(`cornea_u`, negative inside). Both are 0 on the shared ring vertices, so the band is continuous across the seam.
`U0` = the chamber angle's radius minus the ring's (-0.29 mm): where P1b's limbal tissue begins.

**Asymmetry** (switch, default off): the sclera reaches further over the cornea at top and bottom (visible iris
~11.7 mm wide, ~10.6 mm high: ~0.55 mm per side). `asym_shift` = A sin^2(azimuth) is added to u for the colour band
and the transmission, and cornea rays that still reach the iris are covered by tissue within that shift
(`iris_cover`, 0 everywhere while the switch is off).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import cornea_optics as co
from . import eye_geometry as geo
from . import eye_math as em

MM = co.MM
RING_RADIUS = geo.LIMBUS_RADIUS
THETA_RING = math.asin(geo.LIMBUS_RADIUS / geo.SCLERA_RADIUS)
U0 = co.GEOMETRY.angle[0] - RING_RADIUS
LEVELS = ("L0", "L1", "L2", "L3")
COLOUR_SOURCES = ("shader", "image")
#: Shader colour presets (sRGB): "P1b dark" is P1b's limbal colour (the procedural iris's outer colour), the default
#: so L1 starts from what L0 shows; the others are comparison points, not a choice.
SHADER_COLOURS = {"P1b dark": (0.10, 0.11, 0.13), "grey-blue": (0.36, 0.41, 0.48), "grey-brown": (0.40, 0.36, 0.32)}
#: Visible iris ~11.7 x 10.6 mm (horizontal x vertical): the sclera overlaps ~0.55 mm more at top and bottom.
ASYM_MM = 0.55


@dataclass(frozen=True)
class LimbusParams:
    """Every P1c parameter (PROVISIONAL working values; widths in mm)."""
    band_mm: float = 1.0  # the colour / transmission band's outer edge on the sclera
    strength: float = 1.0  # 0 = no tint, 1 = the full gradient
    normal_mm: float = 0.5  # half width of the normal blend
    falloff: float = 4.0  # transmission (1 - t)^falloff
    asym: bool = False
    asym_mm: float = ASYM_MM

    @property
    def band(self) -> float:
        return self.band_mm * MM

    @property
    def normal_w(self) -> float:
        return self.normal_mm * MM

    @property
    def asym_units(self) -> float:
        return self.asym_mm * MM if self.asym else 0.0


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def sclera_u(p):
    p = np.asarray(p, dtype=np.float64)
    # atan2 rather than acos: acos is badly conditioned and imprecise on GPUs (7.6e-5 in float32, 2026-11-14).
    return (np.arctan2(np.hypot(p[..., 0], p[..., 1]), p[..., 2]) - THETA_RING) * geo.SCLERA_RADIUS


def cornea_u(p):
    p = np.asarray(p, dtype=np.float64)
    return np.hypot(p[..., 0], p[..., 1]) - RING_RADIUS


def asym_shift(p, amount: float):
    p = np.asarray(p, dtype=np.float64)
    rr = p[..., 0] ** 2 + p[..., 1] ** 2
    return amount * p[..., 1] ** 2 / np.maximum(rr, 1e-12)


def colour_weight(u, band: float):
    """0 = the limbal colour (at the chamber angle) .. 1 = the sclera albedo (at `band` outside the ring)."""
    return _smooth((np.asarray(u, dtype=np.float64) - U0) / (band - U0))


def tint(weight, limbal, sclera, strength: float):
    w = np.asarray(weight, dtype=np.float64)[..., None]
    gradient = np.asarray(limbal) * (1.0 - w) + np.asarray(sclera) * w
    return np.asarray(sclera) * (1.0 - strength) + gradient * strength


def iris_cover(u, shift):
    """How much tissue covers a cornea ray that still reaches the iris (asymmetry only): 0 while `shift` is 0."""
    u, shift = np.asarray(u, dtype=np.float64), np.asarray(shift, dtype=np.float64)
    safe = np.maximum(shift, 1e-9)
    return np.where(shift > 1e-6, _smooth((u - (U0 - shift)) / safe), 0.0)


def normal_blend(n_cornea, n_sclera, u, w: float):
    """The shading normal: the cornea sphere's at u <= -w, the sclera sphere's at u >= w, halfway on the ring."""
    b = _smooth((np.asarray(u, dtype=np.float64) + w) / (2.0 * w))[..., None]
    return co.normalize(np.asarray(n_cornea) * (1.0 - b) + np.asarray(n_sclera) * b)


def transmission(u, band: float, falloff: float):
    """Share of what lies behind the limbal tissue that shows through: 1 at the chamber angle, 0 from `band` on."""
    t = np.clip((np.asarray(u, dtype=np.float64) - U0) / (band - U0), 0.0, 1.0)
    return (1.0 - t) ** falloff


def sclera_through(p, d, n_sclera, g: co.CorneaGeometry = co.GEOMETRY):
    """The view ray `d` refracted into the limbal sclera at `p` (index `N_CORNEA`, the surface normal `n_sclera`) and
    traced to the iris cone: (reaches the iris within its radius, the hit point)."""
    t_dir = co.normalize(co.refract(d, n_sclera, co.N_AIR / co.N_CORNEA))
    hit, t, r = co.iris_cone_hit(p, t_dir, g)
    point = np.asarray(p) + np.maximum(t, 0.0)[..., None] * t_dir
    return hit & (r <= g.iris_radius), point


def iris_cone_normal(hit, g: co.CorneaGeometry = co.GEOMETRY):
    hit = np.asarray(hit, dtype=np.float64)
    r = np.maximum(np.hypot(hit[..., 0], hit[..., 1]), 1e-6)
    return co.normalize(np.stack([-g.iris_b * hit[..., 0] / r, -g.iris_b * hit[..., 1] / r, np.ones_like(r)], -1))


# -- the limbal colour from the iris image ---------------------------------------------------------------------------


RING_WIDTH = 0.05  # image share


def image_limbal_colour(path: Path, fit=None) -> tuple[tuple[float, float, float] | None, str]:
    """Linear-light mean colour of the iris image's own outer ring (shares `edge - 0.05 .. edge`, edge = the fit's
    `limbus` or, without a fit, the lab's visible limbus share 0.819); (None, reason) if the image cannot be read.
    Reads the file only."""
    from . import iris_fit

    edge = fit.limbus if fit is not None else geo.LIMBUS_RADIUS / geo.IRIS_RADIUS
    try:
        rgb = iris_fit.read_png_rgb(path)
    except Exception as exc:  # noqa: BLE001 - any unreadable image falls back to the shader colour
        return None, f"image colour not available ({exc})"
    h, w = rgb.shape[:2]
    y, x = np.meshgrid((np.arange(h) + 0.5) / h * 2.0 - 1.0, (np.arange(w) + 0.5) / w * 2.0 - 1.0, indexing="ij")
    rho = np.hypot(x, y)
    ring = (rho >= edge - RING_WIDTH) & (rho < edge)
    if not ring.any():
        return None, "image colour not available (empty ring)"
    mean = em.srgb_decode(rgb[ring]).mean(axis=0)
    return tuple(float(v) for v in mean), f"image ring {edge - RING_WIDTH:.2f}-{edge:.2f}"
