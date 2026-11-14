"""Shader-vs-NumPy parity cases for every function in `shaders.LIB_SRC` (GL-free half: inputs, reference values,
tolerances). Used by `tests/test_gl_parity.py` and by the probe's [P] section, so the reference PC checks the same
cases on its own driver.

Inputs are rounded to float32 before the reference is computed (the GPU sees float32), and the reference runs in
float64. Tolerance per case: `abs_tol + rel_tol · |reference|`. The relative part is float32-sized (1e-4 ... 1e-3);
GGX at a near-mirror peak is excluded from the random inputs on purpose: there `n·h² (a² - 1) + 1` cancels in float32
and the difference is the arithmetic's, not the formula's.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import eye_geometry as geo
from . import eye_math as em
from . import studio_env as se

N = 512


@dataclass
class Case:
    func: str
    inputs: np.ndarray  # (n, 12) float32
    reference: np.ndarray  # (n, 4) float64
    channels: int
    abs_tol: float
    rel_tol: float
    mask: np.ndarray | None = None  # (n,) True = compared

    def errors(self, measured: np.ndarray) -> tuple[float, float, int]:
        """(max abs error, max error / tolerance, failures) over the compared rows and channels."""
        m = measured[:, :self.channels]
        r = self.reference[:, :self.channels]
        rows = self.mask if self.mask is not None else np.ones(len(r), dtype=bool)
        diff = np.abs(m - r)[rows]
        tol = (self.abs_tol + self.rel_tol * np.abs(r))[rows]
        bad = int(np.sum(np.any(diff > tol, axis=-1)))
        return float(diff.max(initial=0.0)), float((diff / tol).max(initial=0.0)), bad


def _unit(rng, n):
    v = rng.normal(size=(n, 3))
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _pack(*cols) -> np.ndarray:
    data = np.zeros((len(cols[0]), 12))
    k = 0
    for col in cols:
        col = np.asarray(col, dtype=np.float64).reshape(len(data), -1)
        data[:, k:k + col.shape[1]] = col
        k += col.shape[1]
    return data.astype(np.float32)


def _ref(*cols) -> np.ndarray:
    out = np.zeros((len(cols[0]), 4))
    k = 0
    for col in cols:
        col = np.asarray(col, dtype=np.float64).reshape(len(out), -1)
        out[:, k:k + col.shape[1]] = col
        k += col.shape[1]
    return out


def cases(env: se.StudioEnv = se.DEFAULT_ENV, seed: int = 1) -> list[Case]:
    rng = np.random.default_rng(seed)
    out: list[Case] = []
    f = lambda x: np.asarray(x, dtype=np.float32).astype(np.float64)  # noqa: E731 - what the GPU receives

    c = rng.uniform(0.0, 1.0, (N, 3))
    c[:4] = [[0.0, 0.04045, 1.0], [0.0031308, 0.5, 0.2], [0.04, 0.05, 0.9], [0.001, 0.003, 0.01]]
    x = _pack(c)
    out.append(Case("srgb_decode", x, _ref(em.srgb_decode(f(x[:, :3]))), 3, 1e-6, 2e-5))
    x = _pack(rng.uniform(-0.1, 1.2, (N, 3)))
    out.append(Case("srgb_encode", x, _ref(em.srgb_encode(f(x[:, :3]))), 3, 1e-6, 2e-5))
    mode = rng.integers(0, 2, N)
    x = _pack(rng.uniform(0.0, 8.0, (N, 3)), mode)
    ref = np.where(mode[:, None] == 0, em.tonemap(f(x[:, :3]), 0), em.tonemap(f(x[:, :3]), 1))
    out.append(Case("tonemap", x, _ref(ref), 3, 1e-7, 1e-6))

    nh, alpha = rng.uniform(0.0, 0.995, N), rng.uniform(0.05, 1.0, N)
    nl, nv = rng.uniform(0.01, 1.0, N), rng.uniform(0.01, 1.0, N)
    f0, vh = rng.uniform(0.0, 1.0, N), rng.uniform(0.0, 1.0, N)
    x = _pack(nh, alpha, nl, nv, f0, vh)
    a = f(x)
    ref = _ref(em.ggx_d(a[:, 0], a[:, 1]), em.smith_vis(a[:, 2], a[:, 3], a[:, 1]), em.schlick(a[:, 4], a[:, 5]))
    out.append(Case("ggx_vis_schlick", x, ref, 3, 1e-6, 2e-4))

    n = _unit(rng, N)
    v = _unit(rng, N)
    v = np.where(np.sum(v * n, axis=-1, keepdims=True) < 0.05, -v, v)
    l = _unit(rng, N)
    rough = np.concatenate([rng.uniform(0.1, 1.0, N - 64), np.full(64, 0.0)])
    f0 = rng.uniform(0.02, 1.0, N)
    x = _pack(n, rough, v, f0, l)
    a = f(x)
    ref = em.direct_specular(a[:, 0:3], a[:, 4:7], a[:, 8:11], a[:, 3], np.repeat(a[:, 7:8], 3, axis=1))
    # Near-mirror peaks (n·h > 0.999 at alpha < 0.01) are float32-limited, not compared.
    h = a[:, 4:7] / np.linalg.norm(a[:, 4:7], axis=-1, keepdims=True) + a[:, 8:11]
    h /= np.linalg.norm(h, axis=-1, keepdims=True)
    peak = (np.sum(h * a[:, 0:3], axis=-1) > 0.999) & (np.maximum(a[:, 3], em.MIN_DIRECT_ROUGHNESS) < 0.1)
    out.append(Case("direct_specular", x, _ref(ref), 3, 1e-5, 1e-3, ~peak))

    x = _pack(rng.uniform(0.0, 1.0, N), rng.uniform(0.0, 1.0, N), rng.uniform(1e-4, 1.0, N))
    a = f(x)
    out.append(Case("env_brdf_approx", x, _ref(em.env_brdf_approx(np.repeat(a[:, 0:1], 3, axis=1), a[:, 1], a[:, 2])),
                     3, 1e-6, 1e-4))

    r, m, last = rng.uniform(0.0, 1.0, N), rng.integers(0, 2, N), rng.choice([5.0, 6.0, 7.0], N)
    xe = rng.uniform(-3.0, 3.0, N)
    xb, half, sig, r2 = (rng.uniform(-1.0, 1.0, N), rng.uniform(0.05, 0.5, N), rng.uniform(0.005, 0.5, N),
                         rng.uniform(0.0, 1.0, N))
    x = _pack(r, m, last, xe, xb, half, sig, r2)
    a = f(x)
    lod = np.where(a[:, 1] < 0.5, em.roughness_to_lod(a[:, 0], 0, a[:, 2]), em.roughness_to_lod(a[:, 0], 1, a[:, 2]))
    ref = _ref(lod, em.erf(a[:, 3]), em.box_profile(a[:, 4], a[:, 5], a[:, 6]), em.td_lobe(a[:, 7]))
    out.append(Case("lod_erf_box_lobe", x, ref, 4, 2e-6, 1e-4))

    d = _unit(rng, N)
    key_c = env.key().frame()[0]
    d[:N // 4] = key_c + rng.normal(scale=0.25, size=(N // 4, 3))  # around the softbox and its edges
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    sig, hw = rng.uniform(0.003, 0.3, N), rng.uniform(0.01, 0.3, N)
    x = _pack(d, np.zeros(N), sig, hw)  # a.xyz = direction, b.x = sigma, b.y = horizon width
    a = f(x)
    ref = np.stack([se.radiance(a[i:i + 1, 0:3], env, sigma=a[i, 4], horizon_width=a[i, 5])[0] for i in range(N)])
    out.append(Case("env_radiance", x, _ref(ref), 3, 2e-5, 3e-4))
    rough = rng.uniform(0.0, 1.0, N)
    x = _pack(d, rough)
    a = f(x)
    ref = np.stack([se.td_radiance(a[i:i + 1, 0:3], a[i, 3], env)[0] for i in range(N)])
    out.append(Case("td_env", x, _ref(ref), 3, 2e-5, 3e-4))

    origin = _unit(rng, N) * 3.0 + np.array([0.0, 0.0, 1.0])
    goal = rng.uniform(-0.6, 0.6, (N, 3)) + np.array([0.0, 0.0, 0.9])
    direction = goal - origin
    max_t = rng.uniform(1.0, 6.0, N)
    centre = np.tile([0.0, 0.0, geo.CORNEA_CENTRE_Z], (N, 1))
    x = _pack(origin, max_t, direction, np.full(N, geo.CORNEA_RADIUS), centre, np.full(N, geo.LIMBUS_Z))
    a = f(x)
    hit, p, _ = em.cornea_hit(a[:, 0:3], a[:, 4:7], a[:, 8:11], a[0, 7], a[0, 11], a[:, 3])
    ref = _ref(np.where(hit[:, None], p, 0.0), hit.astype(float))
    # Rays that graze the sphere, end at its surface or cross the limbus plane within float32 noise are not compared.
    o, dd = a[:, 0:3], a[:, 4:7] / np.linalg.norm(a[:, 4:7], axis=-1, keepdims=True)
    oc = o - a[:, 8:11]
    b = np.sum(oc * dd, axis=-1)
    disc = b * b - (np.sum(oc * oc, axis=-1) - a[0, 7] ** 2)
    t = -b - np.sqrt(np.maximum(disc, 0.0))
    pz = o[:, 2] + dd[:, 2] * t
    stable = (np.abs(disc) > 1e-3) & (np.abs(pz - a[0, 11]) > 1e-4) & (np.abs(t - a[:, 3]) > 1e-4)
    out.append(Case("cornea_hit", x, ref, 4, 2e-5, 1e-5, stable))

    mode = rng.integers(0, 2, N)
    x = _pack(rng.uniform(0.0, 4.0, (N, 3)), rng.uniform(0.25, 4.0, N), mode)
    a = f(x)
    ref = np.where(mode[:, None] == 0, em.display(a[:, 0:3] * a[:, 3:4], 1.0, 0),
                   em.display(a[:, 0:3] * a[:, 3:4], 1.0, 1))
    out.append(Case("display", x, _ref(ref), 3, 2e-6, 2e-5))
    return out
