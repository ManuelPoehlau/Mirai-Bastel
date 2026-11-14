"""P1c parity cases: inputs, NumPy references (`limbus_model`) and tolerances for every function of
`limbus_shaders.LIMBUS_LIB_SRC` (GL-free). Used by `tests/test_gl_limbus.py` and the probe's [P] section.

Inputs are float32 (as the GPU sees them), the reference runs in float64 on those values. `PARAMS` sets the uniforms;
the asymmetry is on so `asym_shift` / `iris_cover` are exercised (with it off they are 0 by construction).
"""

from __future__ import annotations

import numpy as np

from . import cornea_optics as co
from . import limbus_model as lm
from .refraction_parity import N, Case, _f32, _pack

PARAMS = lm.LimbusParams(band_mm=1.2, strength=0.8, normal_mm=0.6, falloff=3.0, asym=True)


def _sclera_points(rng, n):
    """Points on the unit sphere around the limbus ring (polar angle 20 .. 45 degrees) - the band and both sides."""
    theta = np.radians(rng.uniform(20.0, 45.0, n))
    phi = rng.uniform(0.0, 2.0 * np.pi, n)
    return np.stack([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)], -1)


def cases(params: lm.LimbusParams = PARAMS, seed: int = 11) -> list[Case]:
    rng = np.random.default_rng(seed)
    out: list[Case] = []

    p = _sclera_points(rng, N)
    x = _pack(p)
    a = _f32(x)
    ref = np.stack([lm.sclera_u(a[:, 0:3]), lm.cornea_u(a[:, 0:3]), lm.asym_shift(a[:, 0:3], params.asym_units),
                    np.zeros(N)], -1)
    # acos near the ring (polar ~29 degrees) in float32: ~1e-6.
    out.append(Case("coords", x, ref, [0, 1, 2], 5e-6))

    u = rng.uniform(-0.06, 0.15, N)
    shift = rng.choice([0.0, params.asym_units, 0.5 * params.asym_units], N)
    x = _pack(u, u + rng.uniform(-0.02, 0.0, N), shift, rng.uniform(-0.06, 0.15, N))
    a = _f32(x)
    ref = np.stack([lm.colour_weight(a[:, 0], params.band), lm.iris_cover(a[:, 1], a[:, 2], params.asym_units),
                    lm.transmission(a[:, 3], params.band, params.falloff), np.zeros(N)], -1)
    out.append(Case("weights", x, ref, [0, 1, 2], 2e-5))

    pc = _sclera_points(rng, N)
    nc = co.normalize(pc - np.array([0.0, 0.0, co.GEOMETRY.anterior_centre_z]))
    u = rng.uniform(-0.08, 0.08, N)
    x = _pack(nc, 0.0 * u, pc, 0.0 * u, u)
    a = _f32(x)
    ref = np.concatenate([lm.normal_blend(co.normalize(a[:, 0:3]), co.normalize(a[:, 4:7]), a[:, 8],
                                          params.normal_w), np.zeros((N, 1))], -1)
    out.append(Case("normal_blend", x, ref, [0, 1, 2], 5e-6))

    # sclera_through: points on the sclera band, view rays from cameras in front (2..4 units, up to 70 degrees).
    ps = _sclera_points(rng, N)
    az, off, dist = rng.uniform(0, 2 * np.pi, N), np.radians(rng.uniform(0.0, 70.0, N)), rng.uniform(2.0, 4.0, N)
    eye = np.stack([dist * np.sin(off) * np.cos(az), dist * np.sin(off) * np.sin(az), dist * np.cos(off)], -1)
    d = co.normalize(ps - eye)
    x = _pack(ps, 0.0 * dist, d, 0.0 * dist, ps)
    a = _f32(x)
    hit, point = lm.sclera_through(a[:, 0:3], co.normalize(a[:, 4:7]), co.normalize(a[:, 8:11]))
    # A grazing cone hit or a hit on the iris rim radius flips under float32: compare where a tiny jitter agrees.
    stable = np.ones(N, dtype=bool)
    for k in range(3):
        for sign in (-1.0, 1.0):
            dd = a[:, 4:7].copy()
            dd[:, k] += sign * 2e-5
            stable &= lm.sclera_through(a[:, 0:3], co.normalize(dd), co.normalize(a[:, 8:11]))[0] == hit
    ref = np.concatenate([np.where(hit[:, None], point, 0.0), hit[:, None].astype(float)], -1)
    case = Case("sclera_through", x, ref, [0, 1, 2], 2e-4, stable, exact_channel=3)
    case.compare_point_only_on_hit = True
    out.append(case)

    w = rng.uniform(0.0, 1.0, N)
    limbal = rng.uniform(0.0, 1.0, (N, 3))
    sclera = rng.uniform(0.0, 1.0, (N, 3))
    yz = rng.uniform(-0.6, 0.6, (N, 2))
    x = _pack(w, yz, limbal, 0.0 * w, sclera)
    a = _f32(x)
    cone = lm.iris_cone_normal(np.stack([a[:, 1], a[:, 2], np.full(N, 0.8)], -1))
    ref = np.concatenate([lm.tint(a[:, 0], a[:, 4:7], a[:, 8:11], params.strength), cone[:, :1]], -1)
    out.append(Case("tint", x, ref, [0, 1, 2, 3], 5e-6))
    return out


def errors(case: Case, measured: np.ndarray) -> tuple[float, int, int]:
    """`Case.errors`, except that for `sclera_through` a miss's point is not compared (the GPU returns the point at
    t = 0, the reference zeroes it)."""
    if getattr(case, "compare_point_only_on_hit", False):
        measured = measured.copy()
        measured[:, 0:3] = np.where(measured[:, 3:4] > 0.5, measured[:, 0:3], 0.0)
    return case.errors(measured)
