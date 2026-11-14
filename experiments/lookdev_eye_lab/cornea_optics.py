"""P1b — the corneal refraction model (GL-free reference, NumPy float64). 2026-11-14.

Every ray function here has a GLSL twin of the same name in `refraction_shaders.py`; `tests/test_gl_refraction.py`
compares them on the GPU (the P1 parity pattern). This module also holds the metrics the lab reports before any
shader exists: magnification, virtual pupil position and pixel displacements per view (`optics_report.py`).

Units: 1 = 12 mm (the sclera radius, `eye_geometry`); `MM` converts. The eye looks down +Z.

**Variants** (P1b brief, Manu 2026-11-14):

| Id | What the ray does after it meets the anterior corneal surface |
|---|---|
| V1 | nothing: P1 as it is (the iris mesh is seen along straight rays; the cornea is P1's treatment C1 / C2 / C3) |
| V2 | refracts once, air -> `N_EFFECTIVE` = 1.3375 (the keratometric index: one surface standing in for the whole cornea), then runs straight to the iris |
| V3 | refracts twice: air 1.0 -> cornea `N_CORNEA` 1.376 at the anterior surface, cornea -> aqueous `N_AQUEOUS` 1.336 at the posterior surface, then to the iris |

**Geometry** (`CorneaGeometry`, coherent with P1's meshes):
- anterior surface = P1's cornea cap (sphere r 7.8 mm), rim = the sclera's limbus ring (r 0.49 = 5.88 mm);
- posterior surface: sphere r 6.6 mm, central thickness 0.55 mm; the thickness grows toward the limbus
  (`thickness_at`, about 0.8 mm at the rim) - Gullstrand-like values, not a measured eye;
- the anterior chamber is closed where the posterior sphere meets P1's iris cone (the chamber "angle", r ~ 5.5 mm);
- limbus transition: a ray that leaves the corneal tissue below the angle (or misses the posterior surface) ends
  in limbal tissue (kind `LIMBUS`), shaded opaque in the shader with a weight that blends from a dark limbal colour
  at the angle to the sclera at the anterior rim (`limbus_weight`). V2 uses the same posterior sphere only as that
  boundary (it does not bend there), so V2 and V3 hide the same tissue.
- iris = P1's cone `z = a + b r` (the root at r = `IRIS_RADIUS`, the pupil edge 0.03 further back); r < pupil
  radius = the pupil (kind `PUPIL`).

**Not modelled** (approximations, README P1b): the tear film as its own layer, dispersion, light refracted on its
way *to* the iris (the iris is lit as in P1, straight from the key), caustics and limbal shadowing, the lens behind the
pupil, the cornea's asphericity (it is a sphere here, real corneas flatten toward the periphery).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import eye_geometry as geo

MM = 1.0 / 12.0
N_AIR = 1.0
N_CORNEA = 1.376
N_AQUEOUS = 1.336
N_EFFECTIVE = 1.3375
VARIANTS = ("V1", "V2", "V3")
MISS, IRIS, PUPIL, LIMBUS = 0, 1, 2, 3
KIND_NAMES = {MISS: "miss", IRIS: "iris", PUPIL: "pupil", LIMBUS: "limbus"}
EPS = 1e-6


def _dot(a, b):
    return np.sum(np.asarray(a, dtype=np.float64) * np.asarray(b, dtype=np.float64), axis=-1)


def normalize(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-300)


@dataclass(frozen=True)
class CorneaGeometry:
    anterior_centre_z: float = geo.CORNEA_CENTRE_Z
    anterior_radius: float = geo.CORNEA_RADIUS
    posterior_radius: float = 6.6 * MM
    central_thickness: float = 0.55 * MM
    limbus_z: float = geo.LIMBUS_Z
    limbus_radius: float = geo.LIMBUS_RADIUS
    iris_radius: float = geo.IRIS_RADIUS
    pupil_radius: float = geo.PUPIL_RADIUS
    iris_root_z: float = geo.IRIS_ROOT_Z
    iris_concavity: float = geo.IRIS_CONCAVITY
    angle: tuple[float, float] = field(init=False)  # (r, z) where the posterior sphere meets the iris cone

    def __post_init__(self) -> None:
        lo, hi = 0.0, self.posterior_radius
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if self.posterior_z(mid) > self.iris_z(mid):
                lo = mid
            else:
                hi = mid
        object.__setattr__(self, "angle", (lo, self.iris_z(lo)))

    @property
    def apex_z(self) -> float:
        return self.anterior_centre_z + self.anterior_radius

    @property
    def posterior_centre_z(self) -> float:
        return self.apex_z - self.central_thickness - self.posterior_radius

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
        return self.posterior_centre_z + np.sqrt(np.maximum(self.posterior_radius ** 2 - r * r, 0.0))

    def anterior_z(self, r):
        r = np.asarray(r, dtype=np.float64)
        return self.anterior_centre_z + np.sqrt(np.maximum(self.anterior_radius ** 2 - r * r, 0.0))

    def thickness_at(self, r):
        """Corneal thickness along the anterior surface normal at anterior radius `r` (units)."""
        r = np.asarray(r, dtype=np.float64)
        p = np.stack([r, np.zeros_like(r), self.anterior_z(r)], axis=-1)
        return np.linalg.norm(p - np.array([0.0, 0.0, self.posterior_centre_z]), axis=-1) - self.posterior_radius


GEOMETRY = CorneaGeometry()


# -- primitives (GLSL twins) -----------------------------------------------------------------------------------------


def refract(i, n, eta):
    """GLSL `refract`: `i` unit incident direction, `n` unit normal facing against `i`, `eta` = n_from / n_to.
    Total internal reflection returns the zero vector."""
    i, n = np.asarray(i, dtype=np.float64), np.asarray(n, dtype=np.float64)
    eta = np.asarray(eta, dtype=np.float64)
    d = _dot(n, i)
    k = 1.0 - eta * eta * (1.0 - d * d)
    out = np.expand_dims(eta, -1) * i - np.expand_dims(eta * d + np.sqrt(np.maximum(k, 0.0)), -1) * n
    return np.where((k < 0.0)[..., None], 0.0, out)


def sphere_entry(o, d, centre, radius):
    """Nearest t > EPS where the ray o + t d (d unit) meets the sphere; (hit mask, t)."""
    oc = np.asarray(o, dtype=np.float64) - np.asarray(centre, dtype=np.float64)
    b = _dot(oc, d)
    c = _dot(oc, oc) - radius * radius
    disc = b * b - c
    s = np.sqrt(np.maximum(disc, 0.0))
    t0, t1 = -b - s, -b + s
    t = np.where(t0 > EPS, t0, t1)
    return (disc >= 0.0) & (t > EPS), t


def iris_cone_hit(o, d, g: CorneaGeometry = GEOMETRY):
    """First t > EPS where the ray meets P1's iris cone z = a + b r (extended to r = 0, so a ray through the pupil
    also hits it); (hit mask, t, r at the hit)."""
    o, d = np.asarray(o, dtype=np.float64), np.asarray(d, dtype=np.float64)
    a, b = g.iris_a, g.iris_b
    q0 = o[..., 2] - a
    A = d[..., 2] ** 2 - b * b * (d[..., 0] ** 2 + d[..., 1] ** 2)
    B = 2.0 * (q0 * d[..., 2] - b * b * (o[..., 0] * d[..., 0] + o[..., 1] * d[..., 1]))
    C = q0 * q0 - b * b * (o[..., 0] ** 2 + o[..., 1] ** 2)
    disc = B * B - 4.0 * A * C
    s = np.sqrt(np.maximum(disc, 0.0))
    safe = np.where(np.abs(A) > 1e-12, A, 1.0)
    r1, r2 = (-B - s) / (2.0 * safe), (-B + s) / (2.0 * safe)
    lin = np.where(np.abs(B) > 1e-12, -C / np.where(np.abs(B) > 1e-12, B, 1.0), -1.0)
    lo, hi = np.minimum(r1, r2), np.maximum(r1, r2)
    lo = np.where(np.abs(A) > 1e-12, lo, lin)
    hi = np.where(np.abs(A) > 1e-12, hi, lin)

    def valid(t):
        q = q0 + t * d[..., 2]
        return (t > EPS) & (q >= -1e-9) & ((disc >= 0.0) | (np.abs(A) <= 1e-12))

    t = np.where(valid(lo), lo, np.where(valid(hi), hi, -1.0))
    p = o + t[..., None] * d
    return t > EPS, t, np.hypot(p[..., 0], p[..., 1])


def schlick_scalar(f0: float, cos_theta):
    m = 1.0 - np.clip(np.asarray(cos_theta, dtype=np.float64), 0.0, 1.0)
    return f0 + (1.0 - f0) * m ** 5


def f0_between(n1: float, n2: float) -> float:
    return ((n2 - n1) / (n2 + n1)) ** 2


def limbus_weight(r_entry, g: CorneaGeometry = GEOMETRY):
    """0 at the chamber angle's radius .. 1 at the anterior rim: how much the limbal tissue at this anterior entry
    radius looks like sclera (smoothstep)."""
    t = np.clip((np.asarray(r_entry, dtype=np.float64) - g.angle[0]) / (g.limbus_radius - g.angle[0]), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


@dataclass
class Trace:
    kind: np.ndarray  # MISS / IRIS / PUPIL / LIMBUS
    entry: np.ndarray  # anterior entry point
    normal: np.ndarray  # anterior outward normal
    hit: np.ndarray  # iris-cone point (IRIS / PUPIL), else the entry point
    transmit_inner: np.ndarray  # 1 - F at the posterior interface (V3), else 1
    direction: np.ndarray  # the ray direction inside the eye after the last refraction


def trace(eye, d, variant: str, g: CorneaGeometry = GEOMETRY) -> Trace:
    """The view ray from `eye` along unit `d` through the cornea to the iris. V1 = straight (P1's geometry, no
    limbus tissue: P1 shows the iris mesh there); V2 / V3 as in the module docstring."""
    eye = np.broadcast_to(np.asarray(eye, dtype=np.float64), np.shape(d))
    d = normalize(d)
    ca = np.array([0.0, 0.0, g.anterior_centre_z])
    cp = np.array([0.0, 0.0, g.posterior_centre_z])
    hit_a, ta = sphere_entry(eye, d, ca, g.anterior_radius)
    entry = eye + ta[..., None] * d
    on_cap = hit_a & (entry[..., 2] >= g.limbus_z - 1e-9)
    normal = normalize(entry - ca)
    transmit = np.ones(np.shape(d)[:-1])
    if variant == "V1":
        t_dir = d
        tissue = np.zeros(np.shape(d)[:-1], dtype=bool)
    else:
        eta = N_AIR / (N_EFFECTIVE if variant == "V2" else N_CORNEA)
        t_dir = normalize(refract(d, normal, eta))
        hit_p, tp = sphere_entry(entry, t_dir, cp, g.posterior_radius)
        pp = entry + tp[..., None] * t_dir
        tissue = ~hit_p | (pp[..., 2] < g.angle[1])
        if variant == "V3":
            np_ = normalize(pp - cp)
            inner = refract(t_dir, np_, N_CORNEA / N_AQUEOUS)
            tir = np.linalg.norm(inner, axis=-1) < 0.5
            tissue = tissue | tir
            cos_b = np.clip(-_dot(np_, t_dir), 0.0, 1.0)
            transmit = np.where(tissue, 1.0, 1.0 - schlick_scalar(f0_between(N_CORNEA, N_AQUEOUS), cos_b))
            t_dir = np.where(tissue[..., None], t_dir, normalize(np.where(tir[..., None], t_dir, inner)))
            entry_inner = np.where(tissue[..., None], entry, pp)
        else:
            entry_inner = entry
    start = entry if variant != "V3" else entry_inner
    hit_i, ti, ri = iris_cone_hit(start, t_dir, g)
    hit = start + np.maximum(ti, 0.0)[..., None] * t_dir
    kind = np.where(~on_cap, MISS, np.where(tissue, LIMBUS,
                    np.where(~hit_i | (ri > g.iris_radius), LIMBUS, np.where(ri < g.pupil_radius, PUPIL, IRIS))))
    seen = (kind == IRIS) | (kind == PUPIL)
    hit = np.where(seen[..., None], hit, entry)
    transmit = np.where(seen, transmit, 1.0)  # limbal tissue / miss: no inner interface crossed
    return Trace(kind.astype(np.int64), entry, normal, hit, transmit, t_dir)


# -- metrics ---------------------------------------------------------------------------------------------------------


def paraxial_entrance_pupil(variant: str, g: CorneaGeometry = GEOMETRY) -> tuple[float, float]:
    """(magnification, apparent depth of the pupil plane below the apex) from paraxial ray-transfer matrices,
    pupil plane at the pupil edge's depth. A cross-check for the traced numbers."""
    depth = g.apex_z - float(g.iris_z(g.pupil_radius))
    if variant == "V1":
        return 1.0, depth

    def surface(n1, n2, radius):  # (y, n*u) refraction matrix, light travelling toward +z (out of the eye)
        return np.array([[1.0, 0.0], [-(n2 - n1) / radius, 1.0]])

    def gap(t, n):
        return np.array([[1.0, t / n], [0.0, 1.0]])

    # Light leaves the pupil plane toward the viewer: the surfaces are concave toward it (centres on the eye side,
    # radius < 0 in the usual convention).
    if variant == "V2":
        system = surface(N_EFFECTIVE, N_AIR, -g.anterior_radius) @ gap(depth, N_EFFECTIVE)
    else:
        aq = depth - g.central_thickness
        system = (surface(N_CORNEA, N_AIR, -g.anterior_radius) @ gap(g.central_thickness, N_CORNEA)
                  @ surface(N_AQUEOUS, N_CORNEA, -g.posterior_radius) @ gap(aq, N_AQUEOUS))
    (A, B), (C, D) = system
    # Image in air: y' = A y + B nu, nu' = C y + D nu. A virtual image of the plane at distance s behind the apex
    # satisfies y_img = y' + s * nu' independent of nu -> s = -B / D; magnification = A + s C.
    s = -B / D
    return A + s * C, -s  # the virtual image lies behind the apex: report that depth as positive


def apparent_pupil_radius(variant: str, distance: float, g: CorneaGeometry = GEOMETRY) -> float:
    """tan of the half-angle under which a camera on the axis at `distance` from the eye centre sees the pupil edge
    (bisection on the ray angle where PUPIL turns into IRIS)."""
    eye = np.array([0.0, 0.0, distance])
    lo, hi = 0.0, 0.5
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        d = normalize(np.array([mid, 0.0, -1.0]))
        kind = trace(eye, d[None], variant, g).kind[0]
        if kind == PUPIL:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def virtual_pupil(variant: str, g: CorneaGeometry = GEOMETRY, d1: float = 30.0, d2: float = 60.0) -> tuple[float, float]:
    """(radius, z) of the pupil edge's virtual image, triangulated from two on-axis cameras (the apparent edge rays
    of both meet at the virtual point)."""
    s1, s2 = apparent_pupil_radius(variant, d1, g), apparent_pupil_radius(variant, d2, g)
    # x = s1 (d1 - z) = s2 (d2 - z)
    z = (s1 * d1 - s2 * d2) / (s1 - s2)
    return s1 * (d1 - z), z


def camera_rays(camera, width: int, height: int):
    """(eye, unit directions (H, W, 3)) of an `OrbitCamera` frame, row 0 at the top (the read-back convention)."""
    forward, right, up = (np.array(v) for v in camera.basis())
    tan_half = math.tan(math.radians(camera.fov_degrees) / 2.0)
    aspect = width / height
    x = ((np.arange(width) + 0.5) / width * 2.0 - 1.0) * tan_half * aspect
    y = (1.0 - (np.arange(height) + 0.5) / height * 2.0) * tan_half
    xx, yy = np.meshgrid(x, y)
    d = forward + xx[..., None] * right + yy[..., None] * up
    return np.array(camera.eye()), normalize(d)


def iris_albedo_image(tr: Trace, image: np.ndarray) -> np.ndarray:
    """sRGB albedo (H, W, 3) the trace sees: the iris image at the planar UV of iris / pupil hits (bilinear),
    the image's outer colour for limbal tissue, 0 where the ray misses the cornea."""
    size = image.shape[0]
    u = 0.5 + tr.hit[..., 0] / (2.0 * geo.IRIS_RADIUS)
    v = 0.5 + tr.hit[..., 1] / (2.0 * geo.IRIS_RADIUS)
    x = np.clip(u * size - 0.5, 0, size - 1)
    y = np.clip((1.0 - v) * size - 0.5, 0, size - 1)  # row 0 = v 1 (eye_geometry.iris_image)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, size - 1), np.minimum(y0 + 1, size - 1)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    top = image[y0, x0] * (1 - fx) + image[y0, x1] * fx
    bottom = image[y1, x0] * (1 - fx) + image[y1, x1] * fx
    out = top * (1 - fy) + bottom * fy
    out = np.where((tr.kind == LIMBUS)[..., None], np.array([0.10, 0.11, 0.13]), out)
    return np.where((tr.kind == MISS)[..., None], 0.0, out)


def view_metrics(camera, width: int, height: int, image: np.ndarray, g: CorneaGeometry = GEOMETRY) -> dict:
    """Per view: pupil size and centroid, iris-feature displacement in pixels and albedo-image differences between
    the variants, over the pixels whose ray meets the cornea."""
    eye, d = camera_rays(camera, width, height)
    traces = {v: trace(eye, d, v, g) for v in VARIANTS}
    blocked = sclera_occludes(eye, d, g)
    for tr in traces.values():
        tr.kind = np.where(blocked, MISS, tr.kind)
    cornea = traces["V2"].kind != MISS
    out: dict = {"cornea_px": int(cornea.sum())}
    for v, tr in traces.items():
        pupil = tr.kind == PUPIL
        ys, xs = np.nonzero(pupil)
        out[v] = {"pupil_px": int(pupil.sum()),
                  "pupil_centroid": (float(xs.mean()), float(ys.mean())) if len(xs) else (float("nan"),) * 2,
                  "limbus_px": int((tr.kind == LIMBUS).sum()), "iris_px": int((tr.kind == IRIS).sum())}
    albedo = {v: np.round(iris_albedo_image(traces[v], image) * 255.0) for v in VARIANTS}
    for a, b in (("V1", "V2"), ("V2", "V3"), ("V1", "V3")):
        ta, tb = traces[a], traces[b]
        both = cornea & (ta.kind == IRIS) & (tb.kind == IRIS)
        # Local scale: iris distance between horizontally / vertically neighbouring pixels in variant b.
        dx = np.linalg.norm(np.diff(tb.hit, axis=1), axis=-1)
        dy = np.linalg.norm(np.diff(tb.hit, axis=0), axis=-1)
        total, count = np.zeros(cornea.shape), np.zeros(cornea.shape)
        total[:, :-1] += dx
        count[:, :-1] += 1
        total[:-1, :] += dy
        count[:-1, :] += 1
        step = np.where(count > 0, total / np.maximum(count, 1), np.nan)
        disp = np.linalg.norm(ta.hit - tb.hit, axis=-1) / step
        disp = disp[both & np.isfinite(disp) & (step > 0)]
        diff = np.abs(albedo[a] - albedo[b]).max(axis=-1)[cornea]
        ys_a = out[a]["pupil_centroid"]
        ys_b = out[b]["pupil_centroid"]
        out[f"{a}-{b}"] = {
            "disp_px_median": float(np.median(disp)) if disp.size else float("nan"),
            "disp_px_p95": float(np.percentile(disp, 95)) if disp.size else float("nan"),
            "disp_px_max": float(disp.max()) if disp.size else float("nan"),
            "kind_changed_px": int(np.sum(cornea & (ta.kind != tb.kind))),
            "albedo_mean": float(diff.mean()), "albedo_p95": float(np.percentile(diff, 95)),
            "albedo_max": float(diff.max()), "albedo_over_2_pct": float(100.0 * np.mean(diff > 2)),
            "pupil_scale": math.sqrt(out[b]["pupil_px"] / out[a]["pupil_px"]) if out[a]["pupil_px"] else float("nan"),
            "pupil_shift_px": float(math.hypot(ys_b[0] - ys_a[0], ys_b[1] - ys_a[1])),
        }
    return out


def sclera_occludes(eye, d, g: CorneaGeometry = GEOMETRY):
    """True where the opaque sclera (the unit sphere below the limbus plane) blocks the ray before it reaches the
    anterior corneal surface. In the GPU the depth test does this; the CPU metrics need it explicitly."""
    eye = np.broadcast_to(np.asarray(eye, dtype=np.float64), np.shape(d))
    hit_s, ts = sphere_entry(eye, d, np.zeros(3), geo.SCLERA_RADIUS)
    ps = eye + ts[..., None] * d
    hit_a, ta = sphere_entry(eye, d, np.array([0.0, 0.0, g.anterior_centre_z]), g.anterior_radius)
    # The sphere's near hit inside the limbus opening is the hole; then the far hit could still be sclera, but only
    # after the ray has passed through the cornea, so it does not occlude the entry.
    return hit_s & (ps[..., 2] < g.limbus_z) & (~hit_a | (ts < ta))


def _visible_kind(variant: str, kind: int, angle: float, distance: float, g: CorneaGeometry, n: int = 121) -> bool:
    a = math.radians(angle)
    eye = np.array([distance * math.sin(a), 0.0, distance * math.cos(a)])
    u = np.linspace(-g.limbus_radius * 1.05, g.limbus_radius * 1.05, n)
    pts = np.stack(np.meshgrid(u, u), axis=-1).reshape(-1, 2)
    targets = np.stack([pts[:, 0], pts[:, 1], np.full(len(pts), g.limbus_z)], axis=-1)
    d = normalize(targets - eye)
    tr = trace(eye, d, variant, g)
    return bool(np.any((tr.kind == kind) & ~sclera_occludes(eye, d, g)))


def visibility_limit(variant: str, kind: int, distance: float = 30.0, g: CorneaGeometry = GEOMETRY) -> float:
    """The largest camera angle off the eye's axis (degrees, orbiting about the eye centre in the x-z plane) at
    which some ray through the cornea, not blocked by the sclera, still reaches `kind` (PUPIL or IRIS): how far round
    the side the pupil stays visible. Coarse 2-degree scan, then bisection to 0.05 degrees (assumes one transition,
    which the scan would show as a later visible step)."""
    last = 0.0
    for angle in np.arange(0.0, 122.0, 2.0):
        if _visible_kind(variant, kind, float(angle), distance, g):
            last = float(angle)
    lo, hi = last, last + 2.0
    while hi - lo > 0.05:
        mid = 0.5 * (lo + hi)
        if _visible_kind(variant, kind, mid, distance, g):
            lo = mid
        else:
            hi = mid
    return lo
