"""P1b parity cases: inputs, NumPy references (`cornea_optics`) and tolerances for every function of
`refraction_shaders.REFRACTION_LIB_SRC` (GL-free). Used by `tests/test_gl_refraction.py` and the probe's [P] section.

Inputs are float32 (as the GPU sees them) and the reference runs in float64 on those values. Rays whose class would
change under a direction jitter of 2e-5 rad (a grazing hit, a hit on a class border) are compared only where both
sides agree on the class being stable: they are excluded and counted, not hidden.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import cornea_optics as co

N = 1024
G = co.GEOMETRY


@dataclass
class Case:
    func: str
    inputs: np.ndarray  # (n, 12) float32
    reference: np.ndarray  # (n, 4)
    channels: list[int]
    abs_tol: float
    mask: np.ndarray | None = None
    exact_channel: int | None = None  # compared for equality (a class id or a hit flag)
    rel_tol: float = 0.0  # tolerance = abs_tol + rel_tol * |reference|

    def errors(self, measured: np.ndarray) -> tuple[float, int, int]:
        """(max abs error over the compared channels, rows over tolerance or with a different class, rows compared)."""
        rows = self.mask if self.mask is not None else np.ones(len(measured), dtype=bool)
        m, r = measured[rows], self.reference[rows]
        bad = np.zeros(len(m), dtype=bool)
        if self.exact_channel is not None:
            same = np.round(m[:, self.exact_channel]) == np.round(r[:, self.exact_channel])
            bad |= ~same
        else:
            same = np.ones(len(m), dtype=bool)
        diff = np.abs(m[:, self.channels] - r[:, self.channels])
        diff = np.where(same[:, None], diff, 0.0)
        bad |= np.any(diff > self.abs_tol + self.rel_tol * np.abs(r[:, self.channels]), axis=-1)
        return float(diff.max(initial=0.0)), int(bad.sum()), int(rows.sum())


def _f32(x):
    return np.asarray(x, dtype=np.float32).astype(np.float64)


def _pack(*cols) -> np.ndarray:
    data = np.zeros((len(cols[0]), 12))
    k = 0
    for col in cols:
        col = np.asarray(col, dtype=np.float64).reshape(len(data), -1)
        data[:, k:k + col.shape[1]] = col
        k += col.shape[1]
    return data.astype(np.float32)


def eye_rays(rng, n: int):
    """Camera positions around the eye (distance 2..4, up to 80 degrees off-axis) aimed at points of the cornea cap."""
    az = rng.uniform(0.0, 2.0 * np.pi, n)
    off = np.radians(rng.uniform(0.0, 80.0, n))
    dist = rng.uniform(2.0, 4.0, n)
    eye = np.stack([dist * np.sin(off) * np.cos(az), dist * np.sin(off) * np.sin(az), dist * np.cos(off)], -1)
    r = G.limbus_radius * np.sqrt(rng.uniform(0.0, 1.0, n))
    phi = rng.uniform(0.0, 2.0 * np.pi, n)
    target = np.stack([r * np.cos(phi), r * np.sin(phi), G.anterior_z(r)], -1)
    return eye, co.normalize(target - eye)


def stable(eye, d, variant: str, jitter: float = 2e-5) -> np.ndarray:
    base = co.trace(eye, d, variant).kind
    ok = np.ones(len(d), dtype=bool)
    for axis in range(3):
        for sign in (-1.0, 1.0):
            dd = d.copy()
            dd[:, axis] += sign * jitter
            ok &= co.trace(eye, co.normalize(dd), variant).kind == base
    return ok


def cases(seed: int = 3) -> list[Case]:
    rng = np.random.default_rng(seed)
    out: list[Case] = []

    # refract: normal facing against the incident ray, several index ratios incl. total internal reflection.
    n = co.normalize(rng.normal(size=(N, 3)))
    i = co.normalize(rng.normal(size=(N, 3)))
    i = np.where((np.sum(i * n, -1) > 0)[:, None], -i, i)
    eta = rng.choice([1.0 / co.N_CORNEA, 1.0 / co.N_EFFECTIVE, co.N_CORNEA / co.N_AQUEOUS, co.N_CORNEA], N)
    x = _pack(i, 0.0 * eta, n, 0.0 * eta, eta)
    a = _f32(x)
    ref = co.refract(co.normalize(a[:, 0:3]), co.normalize(a[:, 4:7]), a[:, 8])
    k = 1.0 - a[:, 8] ** 2 * (1.0 - np.sum(co.normalize(a[:, 0:3]) * co.normalize(a[:, 4:7]), -1) ** 2)
    out.append(Case("refract", x, np.concatenate([ref, np.zeros((N, 1))], -1), [0, 1, 2], 5e-6, np.abs(k) > 1e-4))

    # sphere_entry: rays from outside and inside, hits, misses.
    o = rng.uniform(-3.0, 3.0, (N, 3))
    d = co.normalize(rng.normal(size=(N, 3)))
    c = rng.uniform(-0.5, 0.5, (N, 3))
    radius = rng.uniform(0.3, 2.0, N)
    x = _pack(o, radius, d, 0.0 * radius, c)
    a = _f32(x)
    hit, t = co.sphere_entry(a[:, 0:3], co.normalize(a[:, 4:7]), a[:, 8:11], a[:, 3])
    oc = a[:, 0:3] - a[:, 8:11]
    b = np.sum(oc * co.normalize(a[:, 4:7]), -1)
    disc = b * b - (np.sum(oc * oc, -1) - a[:, 3] ** 2)
    ref = np.stack([np.where(hit, t, -1.0), hit.astype(float), 0 * t, 0 * t], -1)
    out.append(Case("sphere_entry", x, ref, [0], 2e-5, np.abs(disc) > 1e-3, exact_channel=1))

    # iris_cone_hit: rays from the anterior chamber and from outside, mostly toward the iris.
    o = np.stack([rng.uniform(-0.5, 0.5, N), rng.uniform(-0.5, 0.5, N), rng.uniform(0.8, 1.2, N)], -1)
    d = co.normalize(np.stack([rng.uniform(-0.8, 0.8, N), rng.uniform(-0.8, 0.8, N), rng.uniform(-1.0, 0.2, N)], -1))
    x = _pack(o, 0.0 * o[:, 0], d)
    a = _f32(x)
    hit, t, rr = co.iris_cone_hit(a[:, 0:3], co.normalize(a[:, 4:7]))
    ref = np.stack([np.where(hit, t, -1.0), np.where(hit, rr, -1.0), hit.astype(float), 0 * t], -1)
    # Nearly horizontal rays meet the flat cone far away (t ~ 100): float32 keeps ~7 digits there, hence rel_tol.
    out.append(Case("iris_cone_hit", x, ref, [0, 1], 2e-5, exact_channel=2, rel_tol=1e-5))

    r = rng.uniform(0.3, 0.6, N)
    f0, cos = rng.uniform(0.0, 0.1, N), rng.uniform(-0.2, 1.2, N)
    x = _pack(r, f0, cos)
    a = _f32(x)
    ref = np.stack([co.limbus_weight(a[:, 0]), co.schlick_scalar(a[:, 1], a[:, 2]), 0 * r, 0 * r], -1)
    out.append(Case("limbus_schlick", x, ref, [0, 1], 2e-6))

    # The full trace, V2 and V3, from cameras around the eye.
    for variant, vid in (("V2", 2.0), ("V3", 3.0)):
        eye, d = eye_rays(rng, N)
        x = _pack(eye, 0.0 * eye[:, 0], d, 0.0 * eye[:, 0], np.full(N, vid))
        a = _f32(x)
        e, dd = a[:, 0:3], co.normalize(a[:, 4:7])
        tr = co.trace(e, dd, variant)
        ok = stable(e, dd, variant)
        out.append(Case("trace_hit", x, np.concatenate([tr.hit, tr.kind[:, None].astype(float)], -1), [0, 1, 2],
                        2e-4, ok & (tr.kind != co.MISS), exact_channel=3))
        # Grazing entries (discriminant < 0.01) cancel in float32: up to ~1e-4 units (1 micrometre, < 0.1 px).
        out.append(Case("trace_entry", x, np.concatenate([tr.entry, tr.transmit_inner[:, None]], -1), [0, 1, 2, 3],
                        2e-4, ok & (tr.kind != co.MISS)))
    return out
